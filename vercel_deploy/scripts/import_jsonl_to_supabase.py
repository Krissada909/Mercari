"""Import exported JSONL + upload images to Supabase Storage."""
from __future__ import annotations

import json
import mimetypes
import os
import uuid
from pathlib import Path
from urllib import error, request

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
EXPORT = Path(__file__).resolve().parent / "export"
load_dotenv(ROOT / "vercel_deploy" / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
DB_URL = (
    os.getenv("POSTGRES_URL_NON_POOLING")
    or os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
)
BUCKET = "product-images"


def normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "?" in url:
        base, query = url.split("?", 1)
        keep = [p for p in query.split("&") if p.split("=", 1)[0] in {"sslmode", "connect_timeout"}]
        if not any(p.startswith("sslmode=") for p in keep):
            keep.append("sslmode=require")
        return base + "?" + "&".join(keep)
    return url + "?sslmode=require"


def read_jsonl(name: str) -> list[dict]:
    path = EXPORT / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def http_json(method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {SERVICE_KEY}")
    req.add_header("apikey", SERVICE_KEY)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")


def ensure_bucket():
    status, body = http_json("GET", f"{SUPABASE_URL}/storage/v1/bucket/{BUCKET}")
    if status == 200:
        print(f"bucket ok: {BUCKET}")
        return
    status, body = http_json(
        "POST",
        f"{SUPABASE_URL}/storage/v1/bucket",
        {"id": BUCKET, "name": BUCKET, "public": True},
    )
    print(f"create bucket -> {status} {body}")


def upload_file(local_path: Path, dest_name: str) -> str | None:
    if not local_path.is_file():
        print(f"MISS {local_path}")
        return None
    mime = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    req = request.Request(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{dest_name}",
        data=local_path.read_bytes(),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {SERVICE_KEY}")
    req.add_header("apikey", SERVICE_KEY)
    req.add_header("Content-Type", mime)
    req.add_header("x-upsert", "true")
    try:
        with request.urlopen(req) as resp:
            resp.read()
    except error.HTTPError as e:
        print(f"UPLOAD FAIL {local_path.name}: {e.read().decode('utf-8', errors='ignore')}")
        return None
    url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{dest_name}"
    print(f"OK {local_path.name}")
    return url


def find_local(stored: str) -> Path | None:
    if not stored:
        return None
    cleaned = stored.replace("\\", "/").lstrip("/")
    candidates = [
        ROOT / cleaned,
        ROOT / "static" / "images" / Path(cleaned).name,
        ROOT / "static" / "uploads" / Path(cleaned).name,
        ROOT / "static" / "slips" / Path(cleaned).name,
    ]
    for p in candidates:
        if p.is_file():
            return p
    name = Path(cleaned).name
    static_root = ROOT / "static"
    if static_root.exists():
        for folder in static_root.rglob("*"):
            if folder.is_file() and folder.name == name:
                return folder
    return None


def insert_rows(conn, table: str, rows: list[dict], columns: list[str]):
    conn.execute(text(f"DELETE FROM {table}"))
    if not rows:
        print(f"{table}: 0")
        return
    cols = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    stmt = text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})")
    for row in rows:
        payload = {c: row.get(c) for c in columns}
        conn.execute(stmt, payload)
    conn.execute(text(
        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
    ))
    print(f"{table}: {len(rows)}")


def main():
    if not DB_URL or not SUPABASE_URL or not SERVICE_KEY:
        raise SystemExit("Need DATABASE_URL / SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")

    products = read_jsonl("products.jsonl")
    orders = read_jsonl("orders.jsonl")
    items = read_jsonl("order_items.jsonl")
    settings = read_jsonl("settings.jsonl")

    engine = create_engine(normalize_db_url(DB_URL), poolclass=NullPool)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_slip_path VARCHAR"))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR PRIMARY KEY,
                value VARCHAR
            )
            """
        ))
        conn.execute(text("DELETE FROM order_items"))
        conn.execute(text("DELETE FROM orders"))
        conn.execute(text("DELETE FROM products"))

        insert_rows(conn, "products", products, [
            "id", "name", "mercari_link", "image_path", "qty",
            "price_jpy", "base_cost_thb", "weight_cost_thb", "unit_cost_thb", "created_at",
        ])
        insert_rows(conn, "orders", orders, [
            "id", "customer_name", "total_revenue", "total_cost", "profit",
            "created_at", "payment_slip_path",
        ])
        insert_rows(conn, "order_items", items, [
            "id", "order_id", "product_id", "sell_qty", "sell_price_per_unit",
        ])

        for s in settings:
            conn.execute(text(
                """
                INSERT INTO app_settings (key, value) VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """
            ), {"k": s["key"], "v": s["value"]})
        print(f"app_settings: {len(settings)}")

        print("Uploading images...")
        ensure_bucket()
        updated = 0
        for row in conn.execute(text("SELECT id, image_path FROM products")).mappings():
            path = row["image_path"]
            if not path or str(path).startswith("http"):
                continue
            local = find_local(str(path))
            if not local:
                print(f"product#{row['id']} missing file: {path}")
                continue
            dest = f"products/{row['id']}_{uuid.uuid4().hex[:8]}{local.suffix.lower() or '.jpg'}"
            url = upload_file(local, dest)
            if url:
                conn.execute(text("UPDATE products SET image_path=:u WHERE id=:id"), {"u": url, "id": row["id"]})
                updated += 1

        for row in conn.execute(text(
            "SELECT id, payment_slip_path FROM orders WHERE payment_slip_path IS NOT NULL"
        )).mappings():
            path = row["payment_slip_path"]
            if not path or str(path).startswith("http"):
                continue
            local = find_local(str(path))
            if not local:
                print(f"order#{row['id']} missing slip: {path}")
                continue
            dest = f"slips/{row['id']}_{uuid.uuid4().hex[:8]}{local.suffix.lower() or '.jpg'}"
            url = upload_file(local, dest)
            if url:
                conn.execute(
                    text("UPDATE orders SET payment_slip_path=:u WHERE id=:id"),
                    {"u": url, "id": row["id"]},
                )
                updated += 1
        print(f"urls updated: {updated}")

    print("DONE")


if __name__ == "__main__":
    main()

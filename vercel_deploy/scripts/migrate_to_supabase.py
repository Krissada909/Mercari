"""Restore stockdb.sql into Supabase via pooler, then upload images to Storage."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import uuid
from pathlib import Path
from urllib import error, request

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "vercel_deploy" / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tloenjfdzsjhrraaqlcy.supabase.co").rstrip("/")
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


def local_engine():
    return create_engine("postgresql://admin:admin@127.0.0.1:5432/stockdb", poolclass=NullPool)


def supabase_engine():
    if not DB_URL:
        raise SystemExit("Missing DATABASE_URL")
    # prefer session pooler :5432 on pooler host
    url = normalize_db_url(DB_URL)
    return create_engine(url, poolclass=NullPool)


def copy_table(local, remote, table: str, columns: list[str]):
    cols = ", ".join(columns)
    rows = local.execute(text(f"SELECT {cols} FROM {table} ORDER BY id")).mappings().all()
    remote.execute(text(f"DELETE FROM {table}"))
    if not rows:
        print(f"  {table}: 0 rows")
        return 0
    placeholders = ", ".join(f":{c}" for c in columns)
    stmt = text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})")
    for row in rows:
        remote.execute(stmt, dict(row))
    # reset sequence
    remote.execute(text(
        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
    ))
    print(f"  {table}: {len(rows)} rows")
    return len(rows)


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {SERVICE_KEY}")
    req.add_header("apikey", SERVICE_KEY)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        return e.code, raw


def ensure_bucket():
    status, body = http_json("GET", f"{SUPABASE_URL}/storage/v1/bucket/{BUCKET}")
    if status == 200:
        print(f"  bucket '{BUCKET}' exists")
        return
    status, body = http_json(
        "POST",
        f"{SUPABASE_URL}/storage/v1/bucket",
        {"id": BUCKET, "name": BUCKET, "public": True},
    )
    print(f"  create bucket -> {status} {body}")


def upload_file(local_path: Path, dest_name: str) -> str | None:
    if not local_path.is_file():
        print(f"  MISS file: {local_path}")
        return None
    mime = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    data = local_path.read_bytes()
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{dest_name}"
    req = request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {SERVICE_KEY}")
    req.add_header("apikey", SERVICE_KEY)
    req.add_header("Content-Type", mime)
    req.add_header("x-upsert", "true")
    try:
        with request.urlopen(req) as resp:
            resp.read()
    except error.HTTPError as e:
        print(f"  UPLOAD FAIL {local_path.name}: {e.read().decode('utf-8', errors='ignore')}")
        return None
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{dest_name}"
    print(f"  OK {local_path.name} -> {public_url}")
    return public_url


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
    # fuzzy: match by filename in static tree
    name = Path(cleaned).name
    for folder in (ROOT / "static").rglob("*"):
        if folder.is_file() and folder.name == name:
            return folder
    return None


def migrate_images(remote):
    ensure_bucket()
    updated = 0
    rows = remote.execute(text("SELECT id, image_path FROM products")).mappings().all()
    for row in rows:
        path = row["image_path"]
        if not path or str(path).startswith("http") or str(path).startswith("data:"):
            continue
        local = find_local(str(path))
        if not local:
            print(f"  product#{row['id']} missing: {path}")
            continue
        ext = local.suffix.lower() or ".jpg"
        dest = f"products/{row['id']}_{uuid.uuid4().hex[:8]}{ext}"
        url = upload_file(local, dest)
        if url:
            remote.execute(
                text("UPDATE products SET image_path = :u WHERE id = :id"),
                {"u": url, "id": row["id"]},
            )
            updated += 1

    slip_rows = remote.execute(text(
        "SELECT id, payment_slip_path FROM orders WHERE payment_slip_path IS NOT NULL"
    )).mappings().all()
    for row in slip_rows:
        path = row["payment_slip_path"]
        if not path or str(path).startswith("http") or str(path).startswith("data:"):
            continue
        local = find_local(str(path))
        if not local:
            print(f"  order#{row['id']} slip missing: {path}")
            continue
        ext = local.suffix.lower() or ".jpg"
        dest = f"slips/{row['id']}_{uuid.uuid4().hex[:8]}{ext}"
        url = upload_file(local, dest)
        if url:
            remote.execute(
                text("UPDATE orders SET payment_slip_path = :u WHERE id = :id"),
                {"u": url, "id": row["id"]},
            )
            updated += 1
    print(f"  image/slip urls updated: {updated}")


def main():
    if not SERVICE_KEY:
        # fallback from known deploy setup if missing in env
        print("WARN: SUPABASE_SERVICE_ROLE_KEY not in .env — set it before image upload")

    print("1) Copy data local Docker -> Supabase")
    with local_engine().begin() as local, supabase_engine().begin() as remote:
        # child tables first delete already handled by DELETE order
        remote.execute(text("DELETE FROM order_items"))
        remote.execute(text("DELETE FROM orders"))
        remote.execute(text("DELETE FROM products"))
        # ensure payment_slip_path exists
        remote.execute(text(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_slip_path VARCHAR"
        ))
        remote.execute(text(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR PRIMARY KEY,
                value VARCHAR
            )
            """
        ))

        copy_table(local, remote, "products", [
            "id", "name", "mercari_link", "image_path", "qty",
            "price_jpy", "base_cost_thb", "weight_cost_thb", "unit_cost_thb", "created_at",
        ])
        copy_table(local, remote, "orders", [
            "id", "customer_name", "total_revenue", "total_cost", "profit",
            "created_at", "payment_slip_path",
        ])
        copy_table(local, remote, "order_items", [
            "id", "order_id", "product_id", "sell_qty", "sell_price_per_unit",
        ])

        # map old settings -> app_settings if present
        try:
            settings = local.execute(text("SELECT key, value FROM settings")).mappings().all()
            for s in settings:
                remote.execute(text(
                    """
                    INSERT INTO app_settings (key, value) VALUES (:k, :v)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """
                ), {"k": s["key"], "v": s["value"]})
            print(f"  settings -> app_settings: {len(settings)} keys")
        except Exception as e:
            print(f"  settings skip: {e}")

        print("2) Upload images to Supabase Storage")
        if not SERVICE_KEY:
            raise SystemExit("Add SUPABASE_SERVICE_ROLE_KEY to vercel_deploy/.env then rerun")
        migrate_images(remote)

    print("DONE")


if __name__ == "__main__":
    main()

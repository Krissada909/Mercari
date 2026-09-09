"""
ย้ายรูปจากโฟลเดอร์ static/ ขึ้น Supabase DB (แปลงเป็น data URI)
ให้ path เก่า เช่น static/images/xxx.jpg ยังโชว์รูปได้บน Vercel

รันจากรากโปรเจกต์:
  python vercel_deploy/scripts/migrate_images_to_db.py
"""
from __future__ import annotations

import base64
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]  # stock_project/
SEARCH_DIRS = [
    ROOT / "static" / "images",
    ROOT / "static" / "slips",
    ROOT / "static" / "uploads",
    ROOT / "vercel_deploy" / "static" / "images",
    ROOT / "vercel_deploy" / "static" / "slips",
]


def resolve_db_url() -> str:
    load_dotenv(ROOT / "vercel_deploy" / ".env")
    load_dotenv(ROOT / ".env")
    url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_URL_NON_POOLING")
    )
    if not url:
        raise SystemExit("ไม่พบ DATABASE_URL ใน .env")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "?" in url:
        base, query = url.split("?", 1)
        keep = [p for p in query.split("&") if p.split("=", 1)[0] in {"sslmode", "connect_timeout"}]
        if not any(p.startswith("sslmode=") for p in keep):
            keep.append("sslmode=require")
        url = base + "?" + "&".join(keep)
    else:
        url += "?sslmode=require"
    return url


def find_local_file(stored: str) -> Path | None:
    if not stored or stored.startswith("data:") or stored.startswith("http"):
        return None
    cleaned = stored.replace("\\", "/").lstrip("/")
    candidates = [
        ROOT / cleaned,
        ROOT / "static" / "images" / Path(cleaned).name,
        ROOT / "static" / "slips" / Path(cleaned).name,
        ROOT / "static" / "uploads" / Path(cleaned).name,
    ]
    for folder in SEARCH_DIRS:
        candidates.append(folder / Path(cleaned).name)
    for path in candidates:
        if path.is_file():
            return path
    return None


def to_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def migrate_table(conn, table: str, column: str) -> tuple[int, int, int]:
    rows = conn.execute(text(f"SELECT id, {column} FROM {table}")).mappings().all()
    updated = missing = skipped = 0
    for row in rows:
        stored = row[column]
        if not stored:
            skipped += 1
            continue
        if str(stored).startswith("data:") or str(stored).startswith("http"):
            skipped += 1
            continue
        local = find_local_file(str(stored))
        if not local:
            print(f"  [MISS] {table}#{row['id']}: {stored}")
            missing += 1
            continue
        data_uri = to_data_uri(local)
        conn.execute(
            text(f"UPDATE {table} SET {column} = :val WHERE id = :id"),
            {"val": data_uri, "id": row["id"]},
        )
        print(f"  [OK]   {table}#{row['id']}: {local.name} ({local.stat().st_size // 1024} KB)")
        updated += 1
    return updated, missing, skipped


def main():
    url = resolve_db_url()
    # ใช้ pooler ก็ได้ แต่ session/non-pooling ชัวร์กว่าตอนอัปเดตจำนวนมาก
    print("Connecting to Supabase...")
    engine = create_engine(url, poolclass=NullPool)
    with engine.begin() as conn:
        print("\n== products.image_path ==")
        p_ok, p_miss, p_skip = migrate_table(conn, "products", "image_path")
        print("\n== orders.payment_slip_path ==")
        try:
            o_ok, o_miss, o_skip = migrate_table(conn, "orders", "payment_slip_path")
        except Exception as e:
            print(f"  (ข้าม orders: {e})")
            o_ok = o_miss = o_skip = 0

    print("\n==== สรุป ====")
    print(f"products updated={p_ok} missing={p_miss} skipped={p_skip}")
    print(f"orders   updated={o_ok} missing={o_miss} skipped={o_skip}")
    print("เสร็จแล้ว — รีเฟรชหน้าเว็บบน Vercel ได้เลย")


if __name__ == "__main__":
    main()

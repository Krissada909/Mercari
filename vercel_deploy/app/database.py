import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()


def _resolve_database_url() -> str:
    """รองรับทั้ง DATABASE_URL และชื่อ env ที่ Vercel/Supabase สร้างให้อัตโนมัติ"""
    url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRES_PRISMA_URL")
        or os.environ.get("POSTGRES_URL_NON_POOLING")
    )
    if not url:
        raise ValueError(
            "ไม่พบ DATABASE_URL / POSTGRES_URL — ตั้งค่า env จาก Supabase ก่อน"
        )

    # SQLAlchemy ต้องการ postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # ตัดพารามิเตอร์ที่ SQLAlchemy/psycopg2 ไม่รู้จัก
    if "?" in url:
        base, query = url.split("?", 1)
        keep = []
        for part in query.split("&"):
            key = part.split("=", 1)[0].lower()
            if key in {"sslmode", "connect_timeout", "application_name", "options"}:
                keep.append(part)
        if not any(p.startswith("sslmode=") for p in keep):
            keep.append("sslmode=require")
        url = base + (("?" + "&".join(keep)) if keep else "")
    else:
        url = url + "?sslmode=require"

    return url


DATABASE_URL = _resolve_database_url()

# Vercel serverless + Supabase Pooler (transaction mode)
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

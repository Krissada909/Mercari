import os
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()

Base = declarative_base()

_engine: Optional[Engine] = None
SessionLocal = None


def _resolve_database_url() -> str:
    """รองรับ env ที่ Vercel / Supabase สร้างให้"""
    url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL_NON_POOLING")  # ตรงต่อ DB เสถียรกว่าบน serverless
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRES_PRISMA_URL")
    )
    if not url:
        present = [k for k in (
            "DATABASE_URL",
            "POSTGRES_URL",
            "POSTGRES_PRISMA_URL",
            "POSTGRES_URL_NON_POOLING",
        ) if os.environ.get(k)]
        raise ValueError(
            "ไม่พบ DATABASE_URL / POSTGRES_URL ใน Environment Variables "
            f"(พบคีย์ที่เกี่ยวข้อง: {present or 'ไม่มีเลย'})"
        )

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # ตัดพารามิเตอร์ที่ psycopg2 ไม่รู้จัก (pgbouncer, supa, ...)
    if "?" in url:
        base, query = url.split("?", 1)
        keep = []
        for part in query.split("&"):
            key = part.split("=", 1)[0].lower()
            if key in {"sslmode", "connect_timeout", "application_name", "options"}:
                keep.append(part)
        if not any(p.startswith("sslmode=") for p in keep):
            keep.append("sslmode=require")
        url = base + "?" + "&".join(keep)
    else:
        url += "?sslmode=require"

    return url


def get_engine() -> Engine:
    global _engine, SessionLocal
    if _engine is None:
        url = _resolve_database_url()
        _engine = create_engine(
            url,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


# สร้าง engine ตอน import ถ้ามี env — ถ้าไม่มี จะ error ชัดตอนเรียกใช้
try:
    engine = get_engine()
except Exception as e:
    engine = None  # type: ignore
    print(f"[database] init deferred: {e}")


def get_db():
    if engine is None or SessionLocal is None:
        get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

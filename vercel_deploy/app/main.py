from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
import os
from .database import engine, Base
from .routers import products, orders, views, settings

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Stock Manager (Vercel)")


def init_db():
    """สร้างตารางเมื่อจำเป็น — ไม่ให้พังทั้งแอปตอน import ถ้า DB ยังไม่พร้อม"""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_slip_path VARCHAR"
        ))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR PRIMARY KEY,
                value VARCHAR
            )
            """
        ))


@app.on_event("startup")
def on_startup():
    try:
        init_db()
    except Exception as e:
        # log ไว้ดูใน Vercel Functions logs
        print(f"[startup] DB init failed: {e}")


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "db": "up"}
    except Exception as e:
        return {"ok": False, "db": "down", "error": str(e)}


# บน Vercel filesystem เป็น read-only — ห้าม mkdir
# รูป/สลิปเก็บเป็น data URI ใน DB อยู่แล้ว ไม่ต้องพึ่ง static upload
static_dir = BASE_DIR / "static"
if static_dir.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    except Exception as e:
        print(f"[static] skip mount: {e}")

app.include_router(views.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(settings.router)

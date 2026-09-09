from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from .database import engine, Base
from .routers import products, orders, views, settings

# สร้าง Table ใน DB ทันที
Base.metadata.create_all(bind=engine)

# เพิ่มคอลัมน์ใหม่ให้ตารางเดิม (create_all ไม่แก้ schema ที่มีอยู่แล้ว)
def ensure_schema():
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_slip_path VARCHAR"
        ))

ensure_schema()

app = FastAPI(title="Mercari Stock API")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(views.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(settings.router)
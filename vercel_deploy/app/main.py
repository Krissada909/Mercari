from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
from .database import engine, Base
from .routers import products, orders, views, settings

BASE_DIR = Path(__file__).resolve().parent.parent

# สร้าง Table ใน DB
Base.metadata.create_all(bind=engine)


def ensure_schema():
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


ensure_schema()

app = FastAPI(title="Stock Manager (Vercel)")

static_dir = BASE_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
(static_dir / "images").mkdir(exist_ok=True)
(static_dir / "slips").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(views.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(settings.router)

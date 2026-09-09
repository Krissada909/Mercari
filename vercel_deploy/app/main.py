from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
import traceback
from .database import engine, Base, get_engine
from .routers import products, orders, views, settings

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Stock Manager (Vercel)")


def init_db():
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)
    with eng.begin() as conn:
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
        print("[startup] DB ready")
    except Exception as e:
        print(f"[startup] DB init failed: {e}")
        traceback.print_exc()


@app.get("/api/health")
def health():
    import os
    env_keys = [
        k for k in (
            "DATABASE_URL",
            "POSTGRES_URL",
            "POSTGRES_PRISMA_URL",
            "POSTGRES_URL_NON_POOLING",
        )
        if os.environ.get(k)
    ]
    try:
        eng = engine or get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "db": "up", "env_keys": env_keys}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "db": "down", "env_keys": env_keys, "error": str(e)},
        )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    print(f"[error] {request.url.path}: {exc}")
    traceback.print_exc()
    return HTMLResponse(
        f"<h3>Server Error</h3><pre>{exc}</pre>",
        status_code=500,
    )


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

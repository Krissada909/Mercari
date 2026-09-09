import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from app.main import app  # noqa: F401
except Exception as e:
    # ถ้า import พัง ให้มี ASGI app โชว์ error แทน crash เงียบๆ
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import traceback

    app = FastAPI()
    err = traceback.format_exc()
    print(err)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def boot_error(path: str = ""):
        return HTMLResponse(
            f"<h2>App failed to start</h2><pre>{e}\n\n{err}</pre>",
            status_code=500,
        )

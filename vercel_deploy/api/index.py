import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app as fastapi_app


class VercelPathFix:
    """
    Vercel rewrite ไปที่ /api/index บางทีทำให้ path ที่ FastAPI เห็นไม่ใช่ /
    ต้องแปลงกลับเป็น path จริงของเว็บ
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            headers = {
                k.decode().lower(): v.decode()
                for k, v in scope.get("headers", [])
            }
            # ใช้ original path ถ้า Vercel ส่งมา
            original = (
                headers.get("x-forwarded-uri")
                or headers.get("x-invoke-path")
                or headers.get("x-vercel-forwarded-path")
            )
            if original:
                # x-forwarded-uri อาจเป็น full path + query
                original_path = original.split("?", 1)[0]
                scope = dict(scope)
                scope["path"] = original_path or "/"
                scope["raw_path"] = scope["path"].encode("utf-8")
            elif path in ("/api/index", "/api/index/", "/api/index.py", "/api"):
                scope = dict(scope)
                scope["path"] = "/"
                scope["raw_path"] = b"/"
            elif path.startswith("/api/index/"):
                scope = dict(scope)
                new_path = path[len("/api/index") :] or "/"
                scope["path"] = new_path
                scope["raw_path"] = new_path.encode("utf-8")

        await self.app(scope, receive, send)


# Vercel ต้องการ top-level ชื่อ app
app = VercelPathFix(fastapi_app)
application = app
handler = app

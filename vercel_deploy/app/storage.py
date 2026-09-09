import os
import uuid
import mimetypes
from typing import Optional
from urllib import request, error
from fastapi import UploadFile


def _supabase_config():
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET") or "product-images"
    return url, key, bucket


def upload_to_supabase_storage(file: UploadFile, folder: str = "products") -> Optional[str]:
    """อัปโหลดไฟล์ไป Supabase Storage แล้วคืน public URL"""
    supabase_url, service_key, bucket = _supabase_config()
    if not supabase_url or not service_key or not file or not file.filename:
        return None

    content = file.file.read()
    if hasattr(file.file, "seek"):
        file.file.seek(0)
    if not content:
        return None

    ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
    dest = f"{folder}/{uuid.uuid4().hex}{ext}"
    mime = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

    req = request.Request(
        f"{supabase_url}/storage/v1/object/{bucket}/{dest}",
        data=content,
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {service_key}")
    req.add_header("apikey", service_key)
    req.add_header("Content-Type", mime)
    req.add_header("x-upsert", "true")

    try:
        with request.urlopen(req) as resp:
            resp.read()
    except error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise ValueError(f"อัปโหลดรูปไม่สำเร็จ: {detail}") from e

    return f"{supabase_url}/storage/v1/object/public/{bucket}/{dest}"

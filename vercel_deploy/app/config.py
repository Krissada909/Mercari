import os
from typing import Optional
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models

CURRENCY_OPTIONS = {
    "JPY": {"symbol": "¥", "label": "เยน (JPY)", "default_rate": 0.23},
    "USD": {"symbol": "$", "label": "ดอลลาร์ (USD)", "default_rate": 35.0},
    "THB": {"symbol": "฿", "label": "บาท (THB)", "default_rate": 1.0},
}


def _get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    db: Session = SessionLocal()
    try:
        row = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
        if row and row.value is not None:
            return row.value
    except Exception:
        pass
    finally:
        db.close()
    return os.getenv(key, default)


def set_setting(key: str, value: str) -> None:
    db: Session = SessionLocal()
    try:
        row = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(models.AppSetting(key=key, value=value))
        db.commit()
        os.environ[key] = value
    finally:
        db.close()


def get_purchase_currency() -> str:
    currency = (_get_setting("PURCHASE_CURRENCY", "JPY") or "JPY").upper()
    return currency if currency in CURRENCY_OPTIONS else "JPY"


def get_exchange_rate() -> float:
    currency = get_purchase_currency()
    if currency == "THB":
        return 1.0
    raw = _get_setting("EXCHANGE_RATE") or _get_setting("JPY_EXCHANGE_RATE")
    if raw:
        return float(raw)
    return CURRENCY_OPTIONS[currency]["default_rate"]


def get_currency_meta() -> dict:
    currency = get_purchase_currency()
    meta = CURRENCY_OPTIONS[currency]
    return {
        "code": currency,
        "symbol": meta["symbol"],
        "label": meta["label"],
        "rate": get_exchange_rate(),
    }


def media_url(path: Optional[str]) -> str:
    """รองรับทั้ง path ธรรมดา และ data URI"""
    if not path:
        return ""
    if path.startswith("data:") or path.startswith("http://") or path.startswith("https://"):
        return path
    return "/" + path.lstrip("/")

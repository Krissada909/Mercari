import os

CURRENCY_OPTIONS = {
    "JPY": {"symbol": "¥", "label": "เยน (JPY)", "default_rate": 0.23},
    "USD": {"symbol": "$", "label": "ดอลลาร์ (USD)", "default_rate": 35.0},
    "THB": {"symbol": "฿", "label": "บาท (THB)", "default_rate": 1.0},
}


def get_purchase_currency() -> str:
    currency = os.getenv("PURCHASE_CURRENCY", "JPY").upper()
    return currency if currency in CURRENCY_OPTIONS else "JPY"


def get_exchange_rate() -> float:
    """อัตราแลกเปลี่ยนจากสกุลเงินรับเข้า → บาท (THB)"""
    currency = get_purchase_currency()
    if currency == "THB":
        return 1.0
    raw = os.getenv("EXCHANGE_RATE") or os.getenv("JPY_EXCHANGE_RATE")
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

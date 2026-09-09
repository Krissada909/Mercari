from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from ..database import get_db
from .. import config

router = APIRouter(prefix="", tags=["Settings"])
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/settings")
def settings_page(request: Request):
    meta = config.get_currency_meta()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "current_rate": meta["rate"],
        "purchase_currency": meta["code"],
        "currency_options": config.CURRENCY_OPTIONS,
        "currency_symbol": meta["symbol"],
        "currency_label": meta["label"],
    })


@router.post("/settings/save")
def save_settings(
    purchase_currency: str = Form(...),
    exchange_rate: float = Form(...),
    db: Session = Depends(get_db),
):
    try:
        currency = purchase_currency.upper()
        if currency not in config.CURRENCY_OPTIONS:
            currency = "JPY"

        rate = 1.0 if currency == "THB" else float(exchange_rate)

        # เก็บใน DB (Vercel เขียน .env ไม่ได้)
        config.set_setting("PURCHASE_CURRENCY", currency)
        config.set_setting("EXCHANGE_RATE", str(rate))
        if currency == "JPY":
            config.set_setting("JPY_EXCHANGE_RATE", str(rate))

        return RedirectResponse(url="/settings", status_code=303)
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse(url="/settings", status_code=303)

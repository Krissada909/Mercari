from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os
from .. import config

router = APIRouter(prefix="", tags=["Settings"])
templates = Jinja2Templates(directory="templates")


def _update_env_var(key: str, value: str):
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"\n{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    os.environ[key] = value


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
):
    try:
        currency = purchase_currency.upper()
        if currency not in config.CURRENCY_OPTIONS:
            currency = "JPY"

        rate = 1.0 if currency == "THB" else float(exchange_rate)

        _update_env_var("PURCHASE_CURRENCY", currency)
        _update_env_var("EXCHANGE_RATE", str(rate))
        if currency == "JPY":
            _update_env_var("JPY_EXCHANGE_RATE", str(rate))

        return RedirectResponse(url="/settings", status_code=303)
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse(url="/settings", status_code=303)

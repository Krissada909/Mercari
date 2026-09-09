from fastapi import APIRouter, Depends, Form, File, UploadFile, status, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from .. import services, models
from typing import Optional

router = APIRouter(prefix="/product", tags=["Products"])


@router.post("/add")
async def add_product(
    name: str = Form(...),
    mercari_link: Optional[str] = Form(""),
    price_jpy: float = Form(...),
    qty: int = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    try:
        services.create_product(db, name, mercari_link or None, price_jpy, qty, image)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{prod_id}/arrive")
async def product_arrive(prod_id: int, weight_cost_thb: float = Form(...), db: Session = Depends(get_db)):
    services.update_product_arrival(db, prod_id, weight_cost_thb)
    return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{prod_id}/update")
async def update_product(
    prod_id: int,
    name: str = Form(...),
    mercari_link: Optional[str] = Form(""),
    price_jpy: float = Form(...),
    qty: int = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    prod = db.query(models.Product).filter(models.Product.id == prod_id).first()
    if prod:
        prod.name = name
        prod.mercari_link = mercari_link or None
        prod.price_jpy = price_jpy
        prod.qty = qty

        if image and image.filename:
            try:
                prod.image_path = services._save_upload(image)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        exchange_rate = services.get_exchange_rate()
        prod.base_cost_thb = price_jpy * exchange_rate
        total_cost = prod.base_cost_thb + prod.weight_cost_thb
        prod.unit_cost_thb = total_cost / qty if qty > 0 else 0

        db.commit()

    return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/bulk-arrive")
async def bulk_arrive(data: str = Form(...), db: Session = Depends(get_db)):
    import json
    try:
        payload = json.loads(data)
        product_ids = payload.get("product_ids", [])
        weight_cost_thb = payload.get("weight_cost_thb", 0)

        for prod_id in product_ids:
            services.update_product_arrival(db, prod_id, weight_cost_thb)

        return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)
    except Exception:
        return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{prod_id}/delete")
async def delete_product(prod_id: int, db: Session = Depends(get_db)):
    prod = db.query(models.Product).filter(models.Product.id == prod_id).first()
    if prod:
        db.delete(prod)
        db.commit()

    return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)

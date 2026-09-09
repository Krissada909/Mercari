from fastapi import APIRouter, Depends, Form, File, UploadFile, status
from fastapi.responses import RedirectResponse  # <-- เพิ่มตัวนี้เข้ามา
from sqlalchemy.orm import Session
from ..database import get_db
from .. import services
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
    db: Session = Depends(get_db)
):
    services.create_product(db, name, mercari_link or None, price_jpy, qty, image)
    
    # เปลี่ยนจากการ return JSON เป็นการสั่งให้ Redirect กลับไปหน้า /stock
    return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{prod_id}/arrive")
async def product_arrive(prod_id: int, weight_cost_thb: float = Form(...), db: Session = Depends(get_db)):
    services.update_product_arrival(db, prod_id, weight_cost_thb)
    
    # อันนี้ก็ทำเหมือนกันครับ เวลากด "ถึงไทย" จะได้โหลดหน้าเดิมขึ้นมาใหม่
    return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{prod_id}/update")
async def update_product(
    prod_id: int,
    name: str = Form(...),
    mercari_link: Optional[str] = Form(""),
    price_jpy: float = Form(...),
    qty: int = Form(...),
    image: Optional[UploadFile] = File(None), # <--- ต้องเป็น Optional และ File(None)
    db: Session = Depends(get_db)
):
    prod = db.query(models.Product).filter(models.Product.id == prod_id).first()
    if prod:
        prod.name = name
        prod.mercari_link = mercari_link or None
        prod.price_jpy = price_jpy
        prod.qty = qty
        
        # ถ้ามีการอัปโหลดรูปใหม่เข้ามา
        if image and image.filename:
            # ใช้ service เดิมที่เรามีช่วยบันทึกรูป (มันจะคืนค่า path รูปใหม่มาให้)
            # เราต้อง import shutil หรือใช้ logic เดิมใน services.create_product มาประยุกต์
            import shutil
            import os
            
            upload_dir = "static/uploads"
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            
            file_path = f"{upload_dir}/{image.filename}"
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            
            prod.image_path = file_path # อัปเดต path ในฐานข้อมูลe

        # คำนวณต้นทุนใหม่
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
        product_ids = payload.get('product_ids', [])
        weight_cost_thb = payload.get('weight_cost_thb', 0)
        
        for prod_id in product_ids:
            services.update_product_arrival(db, prod_id, weight_cost_thb)
        
        return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{prod_id}/delete")
async def delete_product(prod_id: int, db: Session = Depends(get_db)):
    prod = db.query(models.Product).filter(models.Product.id == prod_id).first()
    if prod:
        # ลบไฟล์รูปถ้ามี
        if prod.image_path:
            import os
            try:
                if os.path.exists(prod.image_path):
                    os.remove(prod.image_path)
            except:
                pass
        
        db.delete(prod)
        db.commit()
    
    return RedirectResponse(url="/stock", status_code=status.HTTP_303_SEE_OTHER)

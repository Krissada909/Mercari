from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
import json
from ..database import get_db
from .. import schemas, services

router = APIRouter(prefix="/order", tags=["Orders"])


@router.post("/create")
async def create_order(
    customer_name: str = Form(...),
    items: str = Form(...),
    order_date: Optional[str] = Form(None),
    payment_slip: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    try:
        items_data = json.loads(items)
        parsed_date = date.fromisoformat(order_date) if order_date else None
        order_data = schemas.OrderSchema(
            customer_name=customer_name,
            items=items_data,
            order_date=parsed_date,
        )
        order = services.process_order(db, order_data, payment_slip=payment_slip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"รูปแบบข้อมูลไม่ถูกต้อง: {e}")
    return {"message": "Order created", "profit": order.profit}


@router.post("/delete/{order_id}")
async def delete_order(order_id: int, db: Session = Depends(get_db)):
    deleted = services.delete_order(db, order_id)
    if not deleted:
        return {"message": "ไม่พบออเดอร์", "success": False}
    return {"message": "ลบออเดอร์สำเร็จ", "success": True}

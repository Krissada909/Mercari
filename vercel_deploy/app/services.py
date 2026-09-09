from sqlalchemy.orm import Session
from fastapi import UploadFile
import base64
import mimetypes
from datetime import datetime, time
from typing import Optional
from . import models, schemas, config


def get_exchange_rate():
    return config.get_exchange_rate()


def _save_upload(file: Optional[UploadFile], folder: str = "") -> Optional[str]:
    """
    บน Vercel filesystem ไม่ถาวร — เก็บไฟล์เป็น data URI ใน DB แทน
    """
    if not file or not file.filename:
        return None

    content = file.file.read()
    if not content:
        return None

    # จำกัดขนาด ~1.5MB เพื่อไม่ให้ DB/payload ใหญ่เกิน
    if len(content) > 1_500_000:
        raise ValueError("ไฟล์ใหญ่เกิน 1.5MB กรุณาบีบอัดก่อนอัปโหลด")

    mime = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def create_product(db: Session, name: str, mercari_link: Optional[str], price_jpy: float, qty: int, image: UploadFile):
    image_path = _save_upload(image)

    exchange_rate = get_exchange_rate()
    base_cost_thb = price_jpy * exchange_rate
    unit_cost_thb = base_cost_thb / qty if qty > 0 else 0

    new_prod = models.Product(
        name=name,
        mercari_link=mercari_link or None,
        price_jpy=price_jpy,
        qty=qty,
        base_cost_thb=base_cost_thb,
        unit_cost_thb=unit_cost_thb,
        image_path=image_path,
    )
    db.add(new_prod)
    db.commit()
    return new_prod


def update_product_arrival(db: Session, prod_id: int, weight_cost_thb: float):
    prod = db.query(models.Product).filter(models.Product.id == prod_id).first()
    if prod:
        prod.weight_cost_thb = weight_cost_thb
        total_cost = prod.base_cost_thb + weight_cost_thb
        prod.unit_cost_thb = total_cost / prod.qty if prod.qty > 0 else 0
        db.commit()
    return prod


def process_order(db: Session, order_data: schemas.OrderSchema, payment_slip: Optional[UploadFile] = None):
    total_revenue = 0.0
    total_cost = 0.0

    for item in order_data.items:
        prod = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not prod:
            raise ValueError(f"ไม่พบสินค้า ID {item.product_id}")
        if prod.qty < item.sell_qty:
            raise ValueError(f"สต็อก '{prod.name}' ไม่พอ (เหลือ {prod.qty} ชิ้น)")

    order_kwargs = {"customer_name": order_data.customer_name}
    if order_data.order_date:
        order_kwargs["created_at"] = datetime.combine(order_data.order_date, time.min)

    slip_path = _save_upload(payment_slip)
    if slip_path:
        order_kwargs["payment_slip_path"] = slip_path

    new_order = models.Order(**order_kwargs)
    db.add(new_order)
    db.flush()

    for item in order_data.items:
        prod = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        prod.qty -= item.sell_qty

        item_revenue = item.sell_qty * item.sell_price
        item_cost = item.sell_qty * prod.unit_cost_thb

        total_revenue += item_revenue
        total_cost += item_cost

        db_order_item = models.OrderItem(
            order_id=new_order.id,
            product_id=prod.id,
            sell_qty=item.sell_qty,
            sell_price_per_unit=item.sell_price,
        )
        db.add(db_order_item)

    new_order.total_revenue = total_revenue
    new_order.total_cost = total_cost
    new_order.profit = total_revenue - total_cost

    db.commit()
    return new_order


def delete_order(db: Session, order_id: int):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        return None

    order_items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).all()

    for item in order_items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if product:
            product.qty += item.sell_qty
        db.delete(item)

    db.delete(order)
    db.commit()
    return order

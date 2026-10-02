from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import extract
from typing import Optional
from pathlib import Path
from ..database import get_db
from .. import models, schemas, config
from datetime import date, timedelta
from calendar import monthrange
import json

router = APIRouter(tags=["Views"])
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["media_url"] = config.media_url

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    orders = db.query(models.Order).all()
    
    # คำนวณสรุปยอดเดิม
    total_revenue = sum(o.total_revenue for o in orders)
    total_profit = sum(o.profit for o in orders)
    total_cost_sold = sum(o.total_cost for o in orders)
    total_items_in_stock = sum(p.qty for p in products)
    
    # คำนวณมูลค่าสต็อกคงเหลือ
    total_inventory_cost = sum(p.qty * p.unit_cost_thb for p in products if p.qty > 0)

    # --- ข้อมูลรายเดือน 6 เดือนย้อนหลัง สำหรับ Bar Chart ---
    today = date.today()
    monthly_labels = []
    monthly_revenue = []
    monthly_profit = []
    monthly_inventory = []
    
    for i in range(5, -1, -1):
        # คำนวณเดือนย้อนหลัง
        first_day = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        y, m = first_day.year, first_day.month
        
        label = first_day.strftime("%b %Y")  # เช่น Jan 2026
        
        month_orders = [o for o in orders 
                       if o.created_at and o.created_at.year == y and o.created_at.month == m]
        
        monthly_labels.append(label)
        monthly_revenue.append(round(sum(o.total_revenue for o in month_orders), 2))
        monthly_profit.append(round(sum(o.profit for o in month_orders), 2))

        # มูลค่าสต็อกสิ้นเดือน = สต็อกปัจจุบัน + ต้นทุนที่ขายไปหลังเดือนนั้น
        month_end = date(y, m, monthrange(y, m)[1])
        cost_after_month = sum(
            o.total_cost for o in orders
            if o.created_at and o.created_at.date() > month_end
        )
        monthly_inventory.append(round(total_inventory_cost + cost_after_month, 2))
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "total_revenue": total_revenue, 
        "total_profit": total_profit,
        "total_items_in_stock": total_items_in_stock,
        "total_inventory_cost": total_inventory_cost,
        "total_cost_sold": total_cost_sold,
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_revenue": json.dumps(monthly_revenue),
        "monthly_profit": json.dumps(monthly_profit),
        "monthly_inventory": json.dumps(monthly_inventory),
    })

@router.get("/stock", response_class=HTMLResponse)
async def stock_page(request: Request, db: Session = Depends(get_db)):
    products = db.query(models.Product).order_by(models.Product.id.desc()).all()
    currency = config.get_currency_meta()
    return templates.TemplateResponse("stock.html", {
        "request": request,
        "products": products,
        "currency": currency,
    })

@router.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, open_order: Optional[int] = None, db: Session = Depends(get_db)):
    # ดึงเฉพาะของที่ยังมีสต็อกมาแสดงใน Dropdown
    available_products = db.query(models.Product).filter(models.Product.qty > 0).all()
    orders = db.query(models.Order).order_by(models.Order.id.desc()).all()
    return templates.TemplateResponse("orders.html", {
        "request": request,
        "products": available_products,
        "orders": orders,
        "open_order_id": open_order,
    })

@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db)):
    # ดึงเฉพาะสินค้าที่ยังมีสต็อกเหลืออยู่ (qty > 0)
    available_products = db.query(models.Product).filter(models.Product.qty > 0).order_by(models.Product.name).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request, 
        "products": available_products
    })


@router.get("/profit-summary", response_class=HTMLResponse)
async def profit_summary(request: Request, month: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Order)
    
    # ถ้ามีการเลือกเดือน (รูปแบบจาก HTML คือ YYYY-MM เช่น 2026-03)
    if month:
        try:
            y, m = month.split('-')
            # ฟิลเตอร์เฉพาะปีและเดือนที่เลือก
            query = query.filter(
                extract('year', models.Order.created_at) == int(y),
                extract('month', models.Order.created_at) == int(m)
            )
        except ValueError:
            pass

    # ดึงออเดอร์และเรียงจากใหม่ไปเก่า
    orders = query.order_by(models.Order.created_at.desc()).all()
    
    # สรุปยอดรวมของเดือนนั้นๆ
    sum_revenue = sum(o.total_revenue for o in orders)
    sum_cost = sum(o.total_cost for o in orders)
    sum_profit = sum(o.profit for o in orders)
    
    return templates.TemplateResponse("profit_summary.html", {
        "request": request,
        "orders": orders,
        "sum_revenue": sum_revenue,
        "sum_cost": sum_cost,
        "sum_profit": sum_profit,
        "selected_month": month
    })


# ตรง payload เปลี่ยนเป็นรับค่าแบบ schemas.OrderUpdateRequest
@router.post("/order/update/{order_id}")
async def update_order(order_id: int, payload: schemas.OrderUpdateRequest, db: Session = Depends(get_db)):
    try:
        # 1. ค้นหาออเดอร์หลัก
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="ไม่พบออเดอร์นี้ในระบบ")

        # 2. วนลูปอัปเดตแต่ละรายการสินค้า
        for req_item in payload.items:
            item = db.query(models.OrderItem).filter(models.OrderItem.id == req_item.item_id).first()
            if item:
                product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
                if product:
                    # คำนวณคืน/ตัดสต็อก
                    qty_difference = req_item.sell_qty - item.sell_qty
                    if product.qty - qty_difference < 0:
                        raise HTTPException(status_code=400, detail=f"สินค้า '{product.name}' มีสต็อกไม่เพียงพอต่อการอัปเดต")
                    product.qty -= qty_difference

                # อัปเดตราคาและจำนวน
                item.sell_price_per_unit = req_item.sell_price
                item.sell_qty = req_item.sell_qty

        # 3. คำนวณยอดรวมของออเดอร์ใหม่ทั้งหมด
        new_total_revenue = 0.0
        new_total_cost = 0.0
        
        for order_item in order.items:
            new_total_revenue += (order_item.sell_qty * order_item.sell_price_per_unit)
            product = db.query(models.Product).filter(models.Product.id == order_item.product_id).first()
            if product:
                new_total_cost += (order_item.sell_qty * product.unit_cost_thb)

        order.total_revenue = new_total_revenue
        order.total_cost = new_total_cost
        order.profit = new_total_revenue - new_total_cost

        # 4. บันทึก
        db.commit()
        
        return {"success": True, "message": "บันทึกการแก้ไขออเดอร์เรียบร้อยแล้ว"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
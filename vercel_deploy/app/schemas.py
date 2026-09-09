from pydantic import BaseModel
from typing import List, Optional
from datetime import date

# ==========================================
# Schema เดิม (สำหรับการสร้างออเดอร์ใหม่)
# ==========================================
class OrderItemSchema(BaseModel):
    product_id: int
    sell_qty: int
    sell_price: float

class OrderSchema(BaseModel):
    customer_name: str
    items: List[OrderItemSchema]
    order_date: Optional[date] = None  # วันที่ขาย (ใช้จัดกลุ่มรายเดือน + ตัดต้นทุน)


# ==========================================
# Schema ใหม่ (สำหรับการแก้ไข/อัปเดตออเดอร์)
# ==========================================
class OrderItemUpdate(BaseModel):
    item_id: int       # ใช้ item_id แทน product_id เพื่อระบุบรรทัดที่แก้
    sell_price: float
    sell_qty: int

class OrderUpdateRequest(BaseModel):
    items: List[OrderItemUpdate]
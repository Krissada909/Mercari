from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy.sql import func

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    mercari_link = Column(String, nullable=True)
    image_path = Column(String, nullable=True)
    qty = Column(Integer, default=0)
    
    price_jpy = Column(Float, default=0.0)
    base_cost_thb = Column(Float, default=0.0)
    weight_cost_thb = Column(Float, default=0.0)
    unit_cost_thb = Column(Float, default=0.0)
    
    # เพิ่มบรรทัดนี้: ให้ระบบบันทึกเวลาที่เพิ่มของอัตโนมัติ
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=True)
    total_revenue = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    profit = Column(Float, default=0.0)
    
    # เพิ่มบรรทัดนี้: เก็บวันเวลาที่สร้างออเดอร์อัตโนมัติ
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    payment_slip_path = Column(String, nullable=True)  # สลิปโอนเงิน (ไม่บังคับ)
    
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    sell_qty = Column(Integer)
    sell_price_per_unit = Column(Float)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product")
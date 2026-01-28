"""SQLAlchemy models for Billing module"""
from sqlalchemy import Column, Integer, String, Text, Date, DECIMAL, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.models import Base

class BillingInvoiceModel(Base):
    """Billing invoice model"""
    __tablename__ = "billing_invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    invoice_number = Column(Text, nullable=False, unique=True)
    patient_id = Column(Integer, ForeignKey("patients_table.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    issue_date = Column(Date, nullable=False)
    purpose = Column(Text, nullable=False)
    total_amount = Column(DECIMAL(12, 2), nullable=False)
    outstanding_amount = Column(DECIMAL(12, 2), nullable=True)  # Generated column
    status = Column(Text, nullable=False)
    amount_paid = Column(DECIMAL(12, 2), nullable=False)
    payment_mode = Column(String(20), nullable=True)  # "UPI", "Card", "Cash", or None
    discount_amount = Column(DECIMAL(12, 2), nullable=False)
    coupon_code = Column(Text, nullable=True)
    tax_amount = Column(DECIMAL(12, 2), nullable=False)
    gst_percentage = Column(DECIMAL(5, 2), nullable=False)
    adjustments = Column(DECIMAL(12, 2), nullable=False)
    visit_charge = Column(DECIMAL(10, 2), default=0)
    medication_charge = Column(DECIMAL(10, 2), default=0)
    bill_type = Column(String(20), nullable=True, index=True)  # "doctor" or "pharmacy"
    related_invoice_id = Column(Integer, ForeignKey("billing_invoices.id", ondelete="SET NULL"), nullable=True, index=True)  # Link related bills
    
    # Relationships
    items = relationship("BillingItemModel", back_populates="invoice", cascade="all, delete-orphan")

class BillingItemModel(Base):
    """Billing item model"""
    __tablename__ = "billing_items"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("billing_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(12, 2), nullable=False)
    line_total = Column(DECIMAL(12, 2), nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True, index=True)
    expiry_date = Column(Date, nullable=True)  # Expiry date from inventory item
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    invoice = relationship("BillingInvoiceModel", back_populates="items")

class PharmacyWalkInBillModel(Base):
    """Pharmacy walk-in bill model - for customers without patient/appointment"""
    __tablename__ = "pharmacy_walk_in_bills"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    invoice_number = Column(Text, nullable=False, unique=True)
    customer_name = Column(Text, nullable=True)  # Optional customer name
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    issue_date = Column(Date, nullable=False)
    total_amount = Column(DECIMAL(12, 2), nullable=False)
    outstanding_amount = Column(DECIMAL(12, 2), nullable=True)  # Generated column
    status = Column(Text, nullable=False)
    amount_paid = Column(DECIMAL(12, 2), nullable=False)
    payment_mode = Column(String(20), nullable=True)  # "UPI", "Card", "Cash", or None
    discount_amount = Column(DECIMAL(12, 2), nullable=False)
    coupon_code = Column(Text, nullable=True)
    tax_amount = Column(DECIMAL(12, 2), nullable=False)
    gst_percentage = Column(DECIMAL(5, 2), nullable=False)
    adjustments = Column(DECIMAL(12, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    items = relationship("PharmacyWalkInItemModel", back_populates="bill", cascade="all, delete-orphan")

class PharmacyWalkInItemModel(Base):
    """Pharmacy walk-in item model"""
    __tablename__ = "pharmacy_walk_in_items"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    bill_id = Column(Integer, ForeignKey("pharmacy_walk_in_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(12, 2), nullable=False)
    line_total = Column(DECIMAL(12, 2), nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True, index=True)
    expiry_date = Column(Date, nullable=True)  # Expiry date from inventory item
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    bill = relationship("PharmacyWalkInBillModel", back_populates="items")

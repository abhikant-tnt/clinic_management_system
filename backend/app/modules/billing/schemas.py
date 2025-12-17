from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
import re

def validate_date_format(v: str) -> str:
    """Validate date: must be in dd/mm/yyyy format"""
    v = v.strip()
    if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
        raise ValueError("Date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
    try:
        day, month, year = map(int, v.split('/'))
        if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900:
            raise ValueError("Invalid date: day (1-31), month (1-12), year (>= 1900)")
        date(year, month, day)
    except ValueError as e:
        raise ValueError(f"Invalid date: {str(e)}")
    return v

class BillingItemCreate(BaseModel):
    """Schema for creating a billing item"""
    item_type: str  # "service" or "product"
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    inventory_item_id: Optional[str] = None  # UUID if linked to inventory

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v

    @field_validator('unit_price', 'line_total')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v

class BillingInvoiceCreate(BaseModel):
    """Schema for creating a billing invoice"""
    tenant_id: Optional[str] = None
    invoice_number: str
    patient_id: int
    appointment_id: int
    doctor_id: int
    issue_date: str  # dd/mm/yyyy format
    purpose: str
    total_amount: Decimal
    tax_amount: Decimal
    gst_percentage: Decimal  # 0, 5, 12, 18, etc.
    discount_amount: Decimal
    coupon_code: Optional[str] = None
    adjustments: Decimal  # Can be negative or positive
    amount_paid: Decimal
    status: str  # "paid", "partial", "pending", "refunded"
    created_by: int
    items: List[BillingItemCreate]  # List of billing items

    @field_validator('issue_date')
    @classmethod
    def validate_issue_date(cls, v: str) -> str:
        return validate_date_format(v)

    @field_validator('gst_percentage')
    @classmethod
    def validate_gst(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("GST percentage must be between 0 and 100")
        return v

    @field_validator('total_amount', 'tax_amount', 'discount_amount', 'adjustments', 'amount_paid')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0 and v != cls.model_fields.get('adjustments').default:
            raise ValueError("Amount cannot be negative")
        return v

class BillingInvoiceUpdate(BaseModel):
    """Schema for updating a billing invoice"""
    tax_amount: Optional[Decimal] = None
    gst_percentage: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    coupon_code: Optional[str] = None
    adjustments: Optional[Decimal] = None
    amount_paid: Optional[Decimal] = None
    status: Optional[str] = None

class BillingInvoice(BaseModel):
    """Schema for billing invoice output"""
    id: Optional[str] = None  # UUID
    tenant_id: Optional[str] = None
    invoice_number: str
    patient_id: int
    appointment_id: int
    doctor_id: int
    issue_date: Optional[date] = None
    purpose: str
    total_amount: Decimal
    tax_amount: Decimal
    gst_percentage: Decimal
    discount_amount: Decimal
    coupon_code: Optional[str] = None
    adjustments: Decimal
    amount_paid: Decimal
    outstanding_amount: Decimal  # Generated column
    status: str
    created_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class BillingItem(BaseModel):
    """Schema for billing item output"""
    id: Optional[str] = None  # UUID
    tenant_id: Optional[str] = None
    invoice_id: Optional[str] = None
    item_type: str
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    inventory_item_id: Optional[str] = None
    created_at: Optional[datetime] = None

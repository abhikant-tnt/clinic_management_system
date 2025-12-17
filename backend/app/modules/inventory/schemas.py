from pydantic import BaseModel, field_validator
from typing import Optional
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

def validate_phone(v: str) -> str:
    """Validate phone number: exactly 10 digits"""
    v = v.strip() if v else ""
    if not v or not v.isdigit() or len(v) != 10:
        raise ValueError("Phone number must contain exactly 10 digits")
    return v

class InventoryItemCreate(BaseModel):
    """Schema for creating an inventory item"""
    tenant_id: Optional[str] = None
    name: str
    category: str  # injectables, peels, retail, consumable
    unit: str  # pcs, ml, box, etc.
    current_stock: int
    min_stock_level: int
    unit_price: Decimal
    expiry_date: str  # dd/mm/yyyy format
    supplier_name: str
    supplier_phone: str

    @field_validator('name', 'category', 'unit', 'supplier_name')
    @classmethod
    def validate_required_string(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator('current_stock', 'min_stock_level')
    @classmethod
    def validate_stock(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Stock level cannot be negative")
        return v

    @field_validator('unit_price')
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Price cannot be negative")
        return v

    @field_validator('expiry_date')
    @classmethod
    def validate_expiry_date(cls, v: str) -> str:
        return validate_date_format(v)

    @field_validator('supplier_phone')
    @classmethod
    def validate_supplier_phone(cls, v: str) -> str:
        return validate_phone(v)

class InventoryItemUpdate(BaseModel):
    """Schema for updating an inventory item"""
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    current_stock: Optional[int] = None
    min_stock_level: Optional[int] = None
    unit_price: Optional[Decimal] = None
    expiry_date: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_phone: Optional[str] = None

    @field_validator('name', 'category', 'unit', 'supplier_name')
    @classmethod
    def validate_string(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Field cannot be empty")
        return v.strip() if v else v

    @field_validator('current_stock', 'min_stock_level')
    @classmethod
    def validate_stock(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Stock level cannot be negative")
        return v

    @field_validator('unit_price')
    @classmethod
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Price cannot be negative")
        return v

    @field_validator('expiry_date')
    @classmethod
    def validate_expiry_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_date_format(v)

    @field_validator('supplier_phone')
    @classmethod
    def validate_supplier_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone(v)

class InventoryItem(BaseModel):
    """Schema for inventory item output"""
    id: Optional[str] = None  # UUID
    tenant_id: Optional[str] = None
    name: str
    category: str
    unit: str
    current_stock: int
    min_stock_level: int
    unit_price: Decimal
    expiry_date: Optional[date] = None
    supplier_name: str
    supplier_phone: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

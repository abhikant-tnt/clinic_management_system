from pydantic import BaseModel, field_validator
from typing import Optional, Literal
from app.core.validators import validate_phone_number
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


class InventoryItemCreate(BaseModel):
    """Schema for creating an inventory item (CREATE SKU form)"""
    tenant_id: Optional[str] = None
    
    # Basic Information - Compulsory fields (marked with *)
    name: str  # Item Name * (Stock Name)
    product_type: Optional[str] = None  # Product Type * (Type: Consumable, Pharmaceutical, etc.)
    category: str  # Category * (Medical, Injectable, etc.)
    sku_code: Optional[str] = None  # Item Code / SKU *
    brand_name: Optional[str] = None  # Brand Name *
    manufacturer: Optional[str] = None  # Manufacturer *
    description: Optional[str] = None  # Description (optional)
    
    # Stock Configuration - Compulsory fields
    unit: str  # Unit of Measure * (vial, ml, box, tube, pcs, bottle)
    pack_size: Optional[int] = None  # Pack Size *
    current_stock: int  # Stock Available
    min_stock_level: int  # Minimum low-stock alert *
    storage_location: Optional[str] = None  # Storage Location * (Shelf / Fridge / Room)
    unit_price: Decimal
    
    # Batch and Expiry
    batch_number: Optional[str] = None  # Batch Number (from table view)
    expiry_date: Optional[str] = None  # Expiry Date (dd/mm/yyyy format, optional)
    
    # Status (can be calculated or provided)
    status: Optional[str] = None  # Status (Out of Stock, Expiring Soon, Normal)
    
    # Supplier Information - Compulsory
    supplier_name: str
    supplier_phone: str
    is_in_stock: Optional[bool] = None  # Auto-calculated if not provided
    
    # Consumable-Specific Fields - Compulsory if product_type is Consumable
    is_sterile: Optional[bool] = None  # Is Sterile *
    is_single_use: Optional[bool] = None  # Single Use *
    is_reusable: Optional[bool] = None  # Reusable *
    expiry_tracking_required: Optional[bool] = None  # Expiry Tracking Required *
    
    # Pharmaceutical-Specific Fields - Compulsory if product_type is Pharmaceutical
    dosage_strength: Optional[str] = None  # Dosage Strength * (e.g., 100U, 500mg)
    dosage_form: Optional[str] = None  # Dosage Form *
    route: Optional[str] = None  # Route * (oral, IM, IV)
    schedule_type: Optional[str] = None  # Schedule Type * (OTC / H / H1)
    prescription_required: Optional[bool] = None  # Prescription Required *

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Name cannot exceed 255 characters")
        return v
    
    @field_validator('supplier_name')
    @classmethod
    def validate_supplier_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Supplier name cannot be empty")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Supplier name cannot exceed 255 characters")
        return v

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
        if v > Decimal('999999.99'):
            raise ValueError("Price cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))

    @field_validator('expiry_date')
    @classmethod
    def validate_expiry_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate expiry date: not in past, and reasonable future date"""
        if v is None:
            return v
        v = validate_date_format(v)
        day, month, year = map(int, v.split('/'))
        expiry_date_obj = date(year, month, day)
        today = date.today()
        if expiry_date_obj < today:
            raise ValueError("Expiry date cannot be in the past")
        # Check if expiry date is more than 10 years in future (likely error)
        max_future_date = date(today.year + 10, today.month, today.day)
        if expiry_date_obj > max_future_date:
            raise ValueError("Expiry date cannot be more than 10 years in the future")
        return v
    
    @field_validator('pack_size')
    @classmethod
    def validate_pack_size(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("Pack size must be at least 1")
        return v
    
    @field_validator('sku_code', 'brand_name', 'manufacturer', 'batch_number', 'storage_location', 
                     'dosage_strength', 'dosage_form', 'route', 'schedule_type', 'description')
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("Field cannot exceed 500 characters")
        return v

    @field_validator('supplier_phone')
    @classmethod
    def validate_supplier_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone_number(v)

class InventoryItemUpdate(BaseModel):
    """Schema for updating an inventory item"""
    # Basic Information
    name: Optional[str] = None
    product_type: Optional[str] = None
    category: Optional[str] = None
    sku_code: Optional[str] = None
    brand_name: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    
    # Stock Configuration
    unit: Optional[str] = None
    pack_size: Optional[int] = None
    current_stock: Optional[int] = None
    min_stock_level: Optional[int] = None
    storage_location: Optional[str] = None
    unit_price: Optional[Decimal] = None
    
    # Batch and Expiry
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    
    # Supplier Information
    supplier_name: Optional[str] = None
    supplier_phone: Optional[str] = None
    is_in_stock: Optional[bool] = None
    
    # Consumable-Specific Fields
    is_sterile: Optional[bool] = None
    is_single_use: Optional[bool] = None
    is_reusable: Optional[bool] = None
    expiry_tracking_required: Optional[bool] = None
    
    # Pharmaceutical-Specific Fields
    dosage_strength: Optional[str] = None
    dosage_form: Optional[str] = None
    route: Optional[str] = None
    schedule_type: Optional[str] = None
    prescription_required: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Name cannot exceed 255 characters")
        return v
    
    @field_validator('supplier_name')
    @classmethod
    def validate_supplier_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v or not v.strip():
            raise ValueError("Supplier name cannot be empty")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Supplier name cannot exceed 255 characters")
        return v

    @field_validator('current_stock', 'min_stock_level')
    @classmethod
    def validate_stock(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Stock level cannot be negative")
        return v

    @field_validator('unit_price')
    @classmethod
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Price cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Price cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))

    @field_validator('expiry_date')
    @classmethod
    def validate_expiry_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate expiry date: not in past, and reasonable future date"""
        if v is None:
            return v
        v = validate_date_format(v)
        day, month, year = map(int, v.split('/'))
        expiry_date_obj = date(year, month, day)
        today = date.today()
        if expiry_date_obj < today:
            raise ValueError("Expiry date cannot be in the past")
        # Check if expiry date is more than 10 years in future (likely error)
        max_future_date = date(today.year + 10, today.month, today.day)
        if expiry_date_obj > max_future_date:
            raise ValueError("Expiry date cannot be more than 10 years in the future")
        return v

    @field_validator('supplier_phone')
    @classmethod
    def validate_supplier_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone(v)
    
    @field_validator('pack_size')
    @classmethod
    def validate_pack_size(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("Pack size must be at least 1")
        return v
    
    @field_validator('sku_code', 'brand_name', 'manufacturer', 'batch_number', 'storage_location',
                     'dosage_strength', 'dosage_form', 'route', 'schedule_type', 'description', 'product_type')
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("Field cannot exceed 500 characters")
        return v

class InventoryItem(BaseModel):
    """Schema for inventory item output (table view)"""
    id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    # Basic Information
    name: str  # Stock Name
    product_type: Optional[str] = None  # Type
    category: str  # Category
    sku_code: Optional[str] = None  # Item Code / SKU
    brand_name: Optional[str] = None  # Brand Name
    manufacturer: Optional[str] = None  # Manufacturer
    description: Optional[str] = None  # Description
    
    # Stock Configuration
    unit: str  # Unit
    pack_size: Optional[int] = None  # Pack Size
    current_stock: int  # Stock Available
    min_stock_level: int  # Minimum low-stock alert
    storage_location: Optional[str] = None  # Storage Location
    unit_price: Decimal
    
    # Batch and Expiry
    batch_number: Optional[str] = None  # Batch Number
    expiry_date: Optional[date] = None  # Expiry Date
    status: Optional[str] = None  # Status (Out of Stock, Expiring Soon, Normal)
    
    # Supplier Information
    supplier_name: str
    supplier_phone: str
    is_in_stock: Optional[bool] = True
    
    # Consumable-Specific Fields
    is_sterile: Optional[bool] = None
    is_single_use: Optional[bool] = None
    is_reusable: Optional[bool] = None
    expiry_tracking_required: Optional[bool] = None
    
    # Pharmaceutical-Specific Fields
    dosage_strength: Optional[str] = None
    dosage_form: Optional[str] = None
    route: Optional[str] = None
    schedule_type: Optional[str] = None
    prescription_required: Optional[bool] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None  # Last Updated

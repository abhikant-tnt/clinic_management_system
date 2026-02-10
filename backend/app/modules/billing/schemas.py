from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Literal
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
        raise ValueError(f"Invalid date: {str(e)}") from e
    return v

class BillingItemCreate(BaseModel):
    """Schema for creating a billing item"""
    item_type: Literal["service", "product"]
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    inventory_item_id: Optional[str] = None

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        if v > 1000:
            raise ValueError("Quantity cannot exceed 1000")
        return v

    @field_validator('unit_price', 'line_total')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Amount cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))
    
    @field_validator('line_total')
    @classmethod
    def validate_line_total(cls, v: Decimal, info) -> Decimal:
        """Validate line_total matches quantity * unit_price"""
        if hasattr(info, 'data'):
            quantity = info.data.get('quantity', 1)
            unit_price = info.data.get('unit_price', Decimal('0'))
            expected_total = (Decimal(str(quantity)) * unit_price).quantize(Decimal('0.01'))
            if abs(v - expected_total) > Decimal('0.01'):
                raise ValueError(f"Line total ({v}) must equal quantity ({quantity}) × unit price ({unit_price}) = {expected_total}")
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        if len(v) > 500:
            raise ValueError("Description cannot exceed 500 characters")
        return v.strip()

class BillingInvoiceCreate(BaseModel):
    """Schema for creating a billing invoice"""
    tenant_id: Optional[str] = None
    invoice_number: str
    patient_id: int
    appointment_id: int
    doctor_id: int
    issue_date: str
    purpose: str
    total_amount: Decimal
    tax_amount: Decimal
    gst_percentage: Decimal
    discount_amount: Decimal
    coupon_code: Optional[str] = None
    adjustments: Decimal
    amount_paid: Decimal
    payment_mode: Optional[Literal["UPI", "Card", "Cash"]] = None
    status: Literal["paid", "partial", "pending", "refunded"]
    visit_charge: Optional[Decimal] = Decimal('0.0')
    medication_charge: Optional[Decimal] = Decimal('0.0')
    items: List[BillingItemCreate]

    @field_validator('invoice_number')
    @classmethod
    def validate_invoice_number(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Invoice number cannot be empty")
        v = v.strip()
        if len(v) > 50:
            raise ValueError("Invoice number cannot exceed 50 characters")
        if not re.match(r'^[a-zA-Z0-9_\-/]+$', v):
            raise ValueError("Invoice number can only contain letters, numbers, hyphens, underscores, and slashes")
        return v

    @field_validator('issue_date')
    @classmethod
    def validate_issue_date(cls, v: str) -> str:
        """Validate issue date: not in future"""
        v = validate_date_format(v)
        day, month, year = map(int, v.split('/'))
        issue_date_obj = date(year, month, day)
        if issue_date_obj > date.today():
            raise ValueError("Issue date cannot be in the future")
        return v

    @field_validator('gst_percentage')
    @classmethod
    def validate_gst(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("GST percentage must be between 0 and 100")
        standard_rates = [Decimal('0'), Decimal('5'), Decimal('12'), Decimal('18'), Decimal('28')]
        if v not in standard_rates:
            raise ValueError("GST percentage should be a standard rate: 0, 5, 12, 18, or 28")
        return v

    @field_validator('total_amount', 'tax_amount', 'discount_amount', 'amount_paid')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Amount cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))
    
    @field_validator('adjustments')
    @classmethod
    def validate_adjustments(cls, v: Decimal) -> Decimal:
        if abs(v) > Decimal('999999.99'):
            raise ValueError("Adjustments cannot exceed 999999.99 in absolute value")
        return v.quantize(Decimal('0.01'))
    
    @model_validator(mode='after')
    def validate_invoice_totals(self) -> 'BillingInvoiceCreate':
        """Validate all totals and taxes match"""
        if self.items:
            sum_line_totals = sum(item.line_total for item in self.items)
            if abs(self.total_amount - sum_line_totals) > Decimal('0.01'):
                raise ValueError(f"Total amount ({self.total_amount}) must equal sum of line totals ({sum_line_totals})")
        
        expected_tax = (self.total_amount * self.gst_percentage / Decimal('100')).quantize(Decimal('0.01'))
        if abs(self.tax_amount - expected_tax) > Decimal('0.01'):
            raise ValueError(f"Tax amount ({self.tax_amount}) must equal (total_amount × GST%) / 100 = {expected_tax}")
        
        max_payable = self.total_amount + self.tax_amount + self.adjustments - self.discount_amount
        # Allow amount_paid to be less than max_payable for partial payments
        if self.amount_paid > max_payable + Decimal('0.01'):
            raise ValueError(f"Amount paid ({self.amount_paid}) cannot exceed total payable ({max_payable})")
        return self
    
    @field_validator('coupon_code')
    @classmethod
    def validate_coupon_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 50:
                raise ValueError("Coupon code cannot exceed 50 characters")
        return v
    
    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Purpose cannot be empty")
        if len(v) > 255:
            raise ValueError("Purpose cannot exceed 255 characters")
        return v.strip()
    
    @field_validator('items')
    @classmethod
    def validate_items(cls, v: List[BillingItemCreate]) -> List[BillingItemCreate]:
        if not v:
            raise ValueError("Invoice must have at least one item")
        if len(v) > 100:
            raise ValueError("Invoice cannot have more than 100 items")
        return v

class BillingInvoiceUpdate(BaseModel):
    """Schema for updating a billing invoice"""
    tax_amount: Optional[Decimal] = None
    gst_percentage: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    coupon_code: Optional[str] = None
    adjustments: Optional[Decimal] = None
    amount_paid: Optional[Decimal] = None
    payment_mode: Optional[Literal["UPI", "Card", "Cash"]] = None
    status: Optional[Literal["paid", "partial", "pending", "refunded"]] = None
    visit_charge: Optional[Decimal] = None
    medication_charge: Optional[Decimal] = None
    
    @field_validator('gst_percentage')
    @classmethod
    def validate_gst(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0 or v > 100:
            raise ValueError("GST percentage must be between 0 and 100")
        standard_rates = [Decimal('0'), Decimal('5'), Decimal('12'), Decimal('18'), Decimal('28')]
        if v not in standard_rates:
            raise ValueError("GST percentage should be a standard rate: 0, 5, 12, 18, or 28")
        return v
    
    @field_validator('tax_amount', 'discount_amount', 'amount_paid')
    @classmethod
    def validate_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Amount cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Amount cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))
    
    @field_validator('adjustments')
    @classmethod
    def validate_adjustments(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if abs(v) > Decimal('999999.99'):
            raise ValueError("Adjustments cannot exceed 999999.99 in absolute value")
        return v.quantize(Decimal('0.01'))
    
    @field_validator('coupon_code')
    @classmethod
    def validate_coupon_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 50:
                raise ValueError("Coupon code cannot exceed 50 characters")
        return v

class BillingInvoice(BaseModel):
    """Schema for billing invoice output"""
    id: Optional[str] = None
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
    payment_mode: Optional[str] = None
    outstanding_amount: Decimal
    status: str
    visit_charge: Optional[Decimal] = Decimal('0.0')
    medication_charge: Optional[Decimal] = Decimal('0.0')

class BillingItem(BaseModel):
    """Schema for billing item output"""
    id: Optional[str] = None
    tenant_id: Optional[str] = None
    invoice_id: Optional[str] = None
    item_type: str
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    inventory_item_id: Optional[str] = None
    created_at: Optional[datetime] = None

class PharmacyWalkInItemCreate(BaseModel):
    """Schema for creating a walk-in pharmacy item"""
    item_type: Literal["product"]
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    inventory_item_id: Optional[str] = None

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        if v > 1000:
            raise ValueError("Quantity cannot exceed 1000")
        return v

    @field_validator('unit_price', 'line_total')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Amount cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))
    
    @field_validator('line_total')
    @classmethod
    def validate_line_total(cls, v: Decimal, info) -> Decimal:
        """Validate line_total matches quantity * unit_price"""
        if hasattr(info, 'data'):
            quantity = info.data.get('quantity', 1)
            unit_price = info.data.get('unit_price', Decimal('0'))
            expected_total = (Decimal(str(quantity)) * unit_price).quantize(Decimal('0.01'))
            if abs(v - expected_total) > Decimal('0.01'):
                raise ValueError(f"Line total ({v}) must equal quantity ({quantity}) × unit price ({unit_price}) = {expected_total}")
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        if len(v) > 500:
            raise ValueError("Description cannot exceed 500 characters")
        return v.strip()

class PharmacyWalkInBillCreate(BaseModel):
    """Schema for creating a walk-in pharmacy bill"""
    tenant_id: Optional[str] = None
    invoice_number: str
    customer_name: Optional[str] = None
    issue_date: str
    total_amount: Decimal
    tax_amount: Decimal
    gst_percentage: Decimal
    discount_amount: Decimal
    coupon_code: Optional[str] = None
    adjustments: Decimal
    amount_paid: Decimal
    payment_mode: Optional[Literal["UPI", "Card", "Cash"]] = None
    status: Literal["paid", "partial", "pending", "refunded"]
    items: List[PharmacyWalkInItemCreate]

    @field_validator('invoice_number')
    @classmethod
    def validate_invoice_number(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Invoice number cannot be empty")
        v = v.strip()
        if len(v) > 50:
            raise ValueError("Invoice number cannot exceed 50 characters")
        if not re.match(r'^[a-zA-Z0-9_\-/]+$', v):
            raise ValueError("Invoice number can only contain letters, numbers, hyphens, underscores, and slashes")
        return v

    @field_validator('issue_date')
    @classmethod
    def validate_issue_date(cls, v: str) -> str:
        """Validate issue date: not in future"""
        v = validate_date_format(v)
        day, month, year = map(int, v.split('/'))
        issue_date_obj = date(year, month, day)
        if issue_date_obj > date.today():
            raise ValueError("Issue date cannot be in the future")
        return v

    @field_validator('gst_percentage')
    @classmethod
    def validate_gst(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("GST percentage must be between 0 and 100")
        standard_rates = [Decimal('0'), Decimal('5'), Decimal('12'), Decimal('18'), Decimal('28')]
        if v not in standard_rates:
            raise ValueError("GST percentage should be a standard rate: 0, 5, 12, 18, or 28")
        return v

    @field_validator('total_amount', 'tax_amount', 'discount_amount', 'amount_paid')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Amount cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))
    
    @field_validator('adjustments')
    @classmethod
    def validate_adjustments(cls, v: Decimal) -> Decimal:
        if abs(v) > Decimal('999999.99'):
            raise ValueError("Adjustments cannot exceed 999999.99 in absolute value")
        return v.quantize(Decimal('0.01'))
    
    @model_validator(mode='after')
    def validate_bill_totals(self) -> 'PharmacyWalkInBillCreate':
        """Validate all totals and taxes match"""
        if self.items:
            sum_line_totals = sum(item.line_total for item in self.items)
            if abs(self.total_amount - sum_line_totals) > Decimal('0.01'):
                raise ValueError(f"Total amount ({self.total_amount}) must equal sum of line totals ({sum_line_totals})")
        
        expected_tax = (self.total_amount * self.gst_percentage / Decimal('100')).quantize(Decimal('0.01'))
        if abs(self.tax_amount - expected_tax) > Decimal('0.01'):
            raise ValueError(f"Tax amount ({self.tax_amount}) must equal (total_amount × GST%) / 100 = {expected_tax}")
        
        max_payable = self.total_amount + self.tax_amount + self.adjustments - self.discount_amount
        if self.amount_paid > max_payable + Decimal('0.01'):
            raise ValueError(f"Amount paid ({self.amount_paid}) cannot exceed total payable ({max_payable})")
        return self
    
    @field_validator('coupon_code')
    @classmethod
    def validate_coupon_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 50:
                raise ValueError("Coupon code cannot exceed 50 characters")
        return v
    
    @field_validator('items')
    @classmethod
    def validate_items(cls, v: List[PharmacyWalkInItemCreate]) -> List[PharmacyWalkInItemCreate]:
        if not v:
            raise ValueError("Bill must have at least one item")
        if len(v) > 100:
            raise ValueError("Bill cannot have more than 100 items")
        return v

class PharmacyWalkInBillUpdate(BaseModel):
    """Schema for updating a walk-in pharmacy bill"""
    tax_amount: Optional[Decimal] = None
    gst_percentage: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    coupon_code: Optional[str] = None
    adjustments: Optional[Decimal] = None
    amount_paid: Optional[Decimal] = None
    payment_mode: Optional[Literal["UPI", "Card", "Cash"]] = None
    status: Optional[Literal["paid", "partial", "pending", "refunded"]] = None
    
    @field_validator('gst_percentage')
    @classmethod
    def validate_gst(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0 or v > 100:
            raise ValueError("GST percentage must be between 0 and 100")
        standard_rates = [Decimal('0'), Decimal('5'), Decimal('12'), Decimal('18'), Decimal('28')]
        if v not in standard_rates:
            raise ValueError("GST percentage should be a standard rate: 0, 5, 12, 18, or 28")
        return v
    
    @field_validator('tax_amount', 'discount_amount', 'amount_paid')
    @classmethod
    def validate_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Amount cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Amount cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))
    
    @field_validator('adjustments')
    @classmethod
    def validate_adjustments(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if abs(v) > Decimal('999999.99'):
            raise ValueError("Adjustments cannot exceed 999999.99 in absolute value")
        return v.quantize(Decimal('0.01'))
    
    @field_validator('coupon_code')
    @classmethod
    def validate_coupon_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 50:
                raise ValueError("Coupon code cannot exceed 50 characters")
        return v

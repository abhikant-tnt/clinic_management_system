from pydantic import BaseModel, field_validator
from typing import Optional, Literal, List
from datetime import datetime, date
from decimal import Decimal
import re

def parse_time_string(time_str: str) -> tuple:
    """Parse time string in formats like '2.00 pm', '9.00 am', '14:30', '2:00 PM' to (hour, minute)"""
    time_str = time_str.strip().lower()
    
    # Handle formats like "2.00 pm" or "9.00 am"
    if 'am' in time_str or 'pm' in time_str:
        # Remove am/pm
        time_part = time_str.replace('am', '').replace('pm', '').strip()
        # Replace dot with colon if needed
        time_part = time_part.replace('.', ':')
        
        # Parse hour and minute
        if ':' in time_part:
            hour_str, minute_str = time_part.split(':')
        else:
            hour_str = time_part
            minute_str = '00'
        
        hour = int(hour_str.strip())
        minute = int(minute_str.strip())
        
        # Convert to 24-hour format
        if 'pm' in time_str and hour != 12:
            hour += 12
        elif 'am' in time_str and hour == 12:
            hour = 0
        
        return (hour, minute)
    
    # Handle 24-hour format like "14:30"
    if ':' in time_str:
        hour, minute = map(int, time_str.split(':'))
        return (hour, minute)
    
    raise ValueError(f"Invalid time format: {time_str}")

class AppointmentCreate(BaseModel):
    """Schema for creating an appointment"""
    tenant_id: Optional[str] = None  # Will be set from settings if not provided
    patient_id: int
    doctor_id: int  # Required: FK to staff(id)
    appointment_date: str  # Required: dd/mm/yyyy format, cannot be in past
    appointment_time: str  # Required: formats like "2.00 pm", "9.00 am", or "14:30"
    status: Literal["In Progress", "Checked In", "No Show", "Checked Out", "Reschedule", "Scheduled", "Cancelled"] = "Scheduled"
    purpose: Literal["Schedule", "follow_up", "procedure"]  # Required: Fixed values
    interval: str  # Required: Appointment interval
    payment: Literal["Pending", "Paid", "Deferred"] = "Pending"  # Default is Pending
    follow_up_date: Optional[str] = None  # Optional: dd/mm/yyyy format

    @field_validator('appointment_date')
    @classmethod
    def validate_appointment_date(cls, v: str) -> str:
        """Validate appointment date: must be in dd/mm/yyyy format and not in past. Required field."""
        if v is None:
            raise ValueError("Appointment date is required")
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Appointment date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900:
                raise ValueError("Invalid date: day (1-31), month (1-12), year (>= 1900)")
            appointment_date_obj = date(year, month, day)
            # Allow today's date but not past dates for new appointments
            if appointment_date_obj < date.today():
                raise ValueError("Appointment date cannot be in the past")
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v
    
    @field_validator('appointment_time')
    @classmethod
    def validate_appointment_time(cls, v: str) -> str:
        """Validate appointment time: accepts formats like '2.00 pm', '9.00 am', '14:30', '2:00 PM'. Required field."""
        if v is None:
            raise ValueError("Appointment time is required")
        v = v.strip()
        
        try:
            hour, minute = parse_time_string(v)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time: hour (0-23), minute (0-59)")
        except ValueError as e:
            raise ValueError(f"Invalid time format. Use formats like '2.00 pm', '9.00 am', or '14:30': {str(e)}")
        
        return v

    @field_validator('follow_up_date')
    @classmethod
    def validate_follow_up_date(cls, v: Optional[str], info) -> Optional[str]:
        """Validate follow-up date: must be in dd/mm/yyyy format and after appointment date"""
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Follow-up date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900:
                raise ValueError("Invalid date: day (1-31), month (1-12), year (>= 1900)")
            follow_up_date_obj = date(year, month, day)
            # Check if appointment_date exists in the data
            if hasattr(info, 'data') and info.data.get('appointment_date'):
                appt_day, appt_month, appt_year = map(int, info.data['appointment_date'].split('/'))
                appt_date_obj = date(appt_year, appt_month, appt_day)
                if follow_up_date_obj <= appt_date_obj:
                    raise ValueError("Follow-up date must be after appointment date")
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v

class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment"""
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    status: Optional[Literal["In Progress", "Checked In", "No Show", "Checked Out", "Reschedule", "Scheduled", "Cancelled"]] = None
    doctor_id: Optional[int] = None
    purpose: Optional[Literal["Schedule", "follow_up", "procedure"]] = None
    interval: Optional[str] = None
    payment: Optional[Literal["Pending", "Paid", "Deferred"]] = None
    follow_up_date: Optional[str] = None

    @field_validator('appointment_date')
    @classmethod
    def validate_appointment_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate appointment date: must be in dd/mm/yyyy format"""
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Appointment date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900:
                raise ValueError("Invalid date: day (1-31), month (1-12), year (>= 1900)")
            date(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v
    
    @field_validator('appointment_time')
    @classmethod
    def validate_appointment_time(cls, v: Optional[str]) -> Optional[str]:
        """Validate appointment time: accepts formats like '2.00 pm', '9.00 am', '14:30', '2:00 PM'"""
        if v is None:
            return v
        v = v.strip()
        
        try:
            hour, minute = parse_time_string(v)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time: hour (0-23), minute (0-59)")
        except ValueError as e:
            raise ValueError(f"Invalid time format. Use formats like '2.00 pm', '9.00 am', or '14:30': {str(e)}")
        
        return v

    @field_validator('follow_up_date')
    @classmethod
    def validate_follow_up_date(cls, v: Optional[str], info) -> Optional[str]:
        """Validate follow-up date: must be in dd/mm/yyyy format and after appointment date if provided"""
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Follow-up date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900:
                raise ValueError("Invalid date: day (1-31), month (1-12), year (>= 1900)")
            follow_up_date_obj = date(year, month, day)
            # Check if appointment_date exists in the data
            if hasattr(info, 'data') and info.data.get('appointment_date'):
                appt_day, appt_month, appt_year = map(int, info.data['appointment_date'].split('/'))
                appt_date_obj = date(appt_year, appt_month, appt_day)
                if follow_up_date_obj <= appt_date_obj:
                    raise ValueError("Follow-up date must be after appointment date")
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v
    
class Appointment(BaseModel):
    """Schema for appointment output"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    patient_id: int
    patient: Optional[str] = None  # Patient name (from relationship)
    number: Optional[str] = None  # Patient phone number (from relationship)
    appointment_date: str
    appointment_time: Optional[str] = None  # Formatted date + time for table view (e.g., "01 Feb 2025 - 04:00 PM")
    status: Literal["In Progress", "Checked In", "No Show", "Checked Out", "Reschedule", "Scheduled", "Cancelled"]
    doctor_name: Optional[str] = None  # Doctor name from staff table
    purpose: Optional[str] = None  # Schedule, follow_up, procedure
    interval: Optional[str] = None
    payment: str  # Pending, Paid, Deferred
    follow_up_date: Optional[str] = None

# Prescription Schemas
class PrescriptionItemCreate(BaseModel):
    """Schema for creating a prescription item"""
    item_type: Literal["Service", "Product"]
    source: Literal["Inventory", "External"]
    item_name: str
    quantity: Optional[str] = None  # Text field for medical units (e.g., "10 tablets", "50 ml")
    inventory_item_id: Optional[int] = None  # If source is "Inventory"

    @field_validator('item_name')
    @classmethod
    def validate_item_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Item name cannot be empty")
        if len(v) > 500:
            raise ValueError("Item name cannot exceed 500 characters")
        return v.strip()

class PrescriptionCreate(BaseModel):
    """Schema for creating a prescription"""
    appointment_id: int
    bill_date: Optional[str] = None  # Auto-generated (today's date), optional in input
    description: Optional[str] = None  # Default None, doctor can add notes
    items: List[PrescriptionItemCreate]  # At least one item required

    @field_validator('items')
    @classmethod
    def validate_items(cls, v: List[PrescriptionItemCreate]) -> List[PrescriptionItemCreate]:
        if not v:
            raise ValueError("Prescription must have at least one item")
        if len(v) > 100:
            raise ValueError("Prescription cannot have more than 100 items")
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 2000:
            raise ValueError("Description cannot exceed 2000 characters")
        return v.strip() if v else None

class PrescriptionItemUpdate(BaseModel):
    """Schema for updating a prescription item"""
    item_type: Optional[Literal["Service", "Product"]] = None
    source: Optional[Literal["Inventory", "External"]] = None
    item_name: Optional[str] = None
    quantity: Optional[str] = None
    inventory_item_id: Optional[int] = None

    @field_validator('item_name')
    @classmethod
    def validate_item_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or not v.strip():
                raise ValueError("Item name cannot be empty")
            if len(v) > 500:
                raise ValueError("Item name cannot exceed 500 characters")
            return v.strip()
        return v

class PrescriptionUpdate(BaseModel):
    """Schema for updating a prescription"""
    bill_date: Optional[str] = None
    description: Optional[str] = None
    items: Optional[List[PrescriptionItemCreate]] = None  # Replace all items if provided

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 2000:
            raise ValueError("Description cannot exceed 2000 characters")
        return v.strip() if v else None

    @field_validator('items')
    @classmethod
    def validate_items(cls, v: Optional[List[PrescriptionItemCreate]]) -> Optional[List[PrescriptionItemCreate]]:
        if v is not None:
            if not v:
                raise ValueError("Prescription must have at least one item")
            if len(v) > 100:
                raise ValueError("Prescription cannot have more than 100 items")
        return v

class PrescriptionItemResponse(BaseModel):
    """Schema for prescription item response"""
    id: int
    item_type: str
    source: str
    item_name: str
    quantity: Optional[str] = None
    inventory_item_id: Optional[int] = None

class PrescriptionResponse(BaseModel):
    """Schema for prescription response"""
    id: int
    appointment_id: int
    bill_date: str
    description: Optional[str] = None
    items: List[PrescriptionItemResponse]
    created_at: Optional[str] = None

# Bill Payment Schemas
class BillItemInput(BaseModel):
    """Schema for bill item in Bill Payment form"""
    item_type: Literal["Service", "Product"]
    source: Literal["Inventory", "External"]
    item_name: str
    quantity: int
    unit_price: Decimal
    total: Decimal
    inventory_item_id: Optional[int] = None
    prescription_item_id: Optional[int] = None  # Reference to prescription item

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        if v > 1000:
            raise ValueError("Quantity cannot exceed 1000")
        return v

    @field_validator('unit_price', 'total')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Amount cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))

class BillPaymentCreate(BaseModel):
    """Schema for creating bill payment from prescription"""
    appointment_id: int
    bill_date: str  # Auto-generated (today)
    items: List[BillItemInput]
    promo_type: Optional[str] = None  # Text field (like coupon_code)
    promo_discount: Decimal = Decimal('0.0')  # Promotion discount amount
    prescription_id: Optional[int] = None  # Reference to prescription

    @field_validator('items')
    @classmethod
    def validate_items(cls, v: List[BillItemInput]) -> List[BillItemInput]:
        if not v:
            raise ValueError("Bill must have at least one item")
        if len(v) > 100:
            raise ValueError("Bill cannot have more than 100 items")
        return v

    @field_validator('promo_discount')
    @classmethod
    def validate_promo_discount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Promo discount cannot be negative")
        if v > Decimal('999999.99'):
            raise ValueError("Promo discount cannot exceed 999999.99")
        return v.quantize(Decimal('0.01'))

    @field_validator('promo_type')
    @classmethod
    def validate_promo_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 50:
                raise ValueError("Promo type cannot exceed 50 characters")
        return v

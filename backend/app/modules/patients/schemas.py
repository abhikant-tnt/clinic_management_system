from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Literal
from datetime import datetime, date
import re

def calculate_age(date_of_birth: str) -> int:
    """Calculate age from date_of_birth in dd/mm/yyyy format"""
    day, month, year = map(int, date_of_birth.split('/'))
    birth_date = date(year, month, day)
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def validate_phone(v: str) -> str:
    """Validate phone number: exactly 10 digits, only digits allowed"""
    v = v.strip() if v else ""
    if not v or not v.isdigit() or len(v) != 10:
        raise ValueError("Phone number must contain exactly 10 digits (numbers only)")
    return v

def validate_pincode(v: str) -> str:
    """Validate pincode: numbers only, no alphabets allowed"""
    v = v.strip() if v else ""
    if not v or not v.isdigit():
        raise ValueError("Pincode must contain only numbers, no alphabets allowed")
    return v

def validate_date_format(v: str) -> str:
    """Validate date: must be in dd/mm/yyyy format"""
    v = v.strip()
    if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
        raise ValueError("Date must be in dd/mm/yyyy format (e.g., 15/01/1994)")
    try:
        day, month, year = map(int, v.split('/'))
        current_year = date.today().year
        if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900 or year > current_year:
            raise ValueError(f"Invalid date: day (1-31), month (1-12), year (1900-{current_year})")
        date(year, month, day)
    except ValueError as e:
        raise ValueError(f"Invalid date: {str(e)}")
    return v

def to_lowercase(v: Optional[str]) -> Optional[str]:
    """Convert string to lowercase for case-insensitive storage"""
    return v.lower().strip() if v else v

class PatientCreate(BaseModel):
    """Schema for creating a patient"""
    tenant_id: Optional[str] = None
    title: Literal["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof"]  # Required dropdown
    firstname: str  # Required
    lastname: str  # Required
    date_of_birth: str  # Required - used to calculate age automatically
    gender: Literal["male", "female", "other"]
    phone: str  # Required: exactly 10 digits
    email: Optional[EmailStr] = None
    address1: str  # Required
    address2: Optional[str] = None  # Optional
    city: str  # Required
    state: str  # Required
    pincode: str  # Required: numbers only
    emergency_contact_name: str  # Required
    emergency_contact_phone: str  # Required: exactly 10 digits
    registration_date: str
    referral_source: Literal["doctor", "self", "friend", "online"]
    referral_subcategory: Optional[str] = None
    patient_status: Literal["Active", "Inactive", "VIP", "Do not treat", "Requires follow up"]
    important_notes: Optional[str] = None
    last_visit_date: Optional[str] = None  # Optional: dd/mm/yyyy format
    
    @field_validator('phone', 'emergency_contact_phone')
    @classmethod
    def validate_phone_fields(cls, v: str) -> str:
        return validate_phone(v)
    
    @field_validator('pincode')
    @classmethod
    def validate_pincode(cls, v: str) -> str:
        return validate_pincode(v)
    
    @field_validator('date_of_birth', 'last_visit_date')
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_date_format(v)
    
    @field_validator('firstname', 'lastname', 'city', 'state', 'emergency_contact_name', 'referral_subcategory')
    @classmethod
    def to_lowercase_fields(cls, v: Optional[str]) -> Optional[str]:
        return to_lowercase(v)
    
    @field_validator('address1', 'address2')
    @classmethod
    def to_lowercase_address(cls, v: Optional[str]) -> Optional[str]:
        return to_lowercase(v)

class PatientUpdate(BaseModel):
    """Schema for updating a patient"""
    title: Optional[Literal["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof"]] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    date_of_birth: Optional[str] = None  # If provided, age will be recalculated
    gender: Optional[Literal["male", "female", "other"]] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    registration_date: Optional[str] = None
    referral_source: Optional[Literal["doctor", "self", "friend", "online"]] = None
    referral_subcategory: Optional[str] = None
    patient_status: Optional[Literal["Active", "Inactive", "VIP", "Do not treat", "Requires follow up"]] = None
    important_notes: Optional[str] = None
    last_visit_date: Optional[str] = None
    
    @field_validator('phone', 'emergency_contact_phone')
    @classmethod
    def validate_phone_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone(v)
    
    @field_validator('pincode')
    @classmethod
    def validate_pincode(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_pincode(v)
    
    @field_validator('date_of_birth', 'last_visit_date')
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_date_format(v)
    
    @field_validator('firstname', 'lastname', 'city', 'state', 'emergency_contact_name', 'referral_subcategory')
    @classmethod
    def to_lowercase_fields(cls, v: Optional[str]) -> Optional[str]:
        return to_lowercase(v)
    
    @field_validator('address1', 'address2')
    @classmethod
    def to_lowercase_address(cls, v: Optional[str]) -> Optional[str]:
        return to_lowercase(v)

class PatientModel(BaseModel):
    """Schema for patient output - includes calculated age"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    title: str
    firstname: str
    lastname: str
    date_of_birth: str
    age: int  # Calculated from date_of_birth
    gender: Literal["male", "female", "other"]
    phone: str
    email: Optional[EmailStr] = None
    address1: str
    address2: Optional[str] = None
    city: str
    state: str
    pincode: str
    emergency_contact_name: str
    emergency_contact_phone: str
    referral_source: Literal["doctor", "self", "friend", "online"]
    referral_subcategory: Optional[str] = None
    patient_status: Literal["Active", "Inactive", "VIP", "Do not treat", "Requires follow up"]
    important_notes: Optional[str] = None
    last_visit_date: Optional[str] = None
    registration_date: str
    synced_to_main: Optional[bool] = False
    last_synced_at: Optional[datetime] = None
    
    @field_validator('age')
    @classmethod
    def validate_age(cls, v: int) -> int:
        """Validate age: must be between 1 and 110"""
        if v < 1 or v > 110:
            raise ValueError("Age must be between 1 and 110")
        return v

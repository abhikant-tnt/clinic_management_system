from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Literal
from datetime import datetime, date
import re

class Patient(BaseModel):
    id: Optional[int] = None #optional because it is not required to be provided when creating a patient
    tenant_id: Optional[str] = None  # Will be set from settings if not provided
    name: str
    age: int
    gender: Literal["male", "female", "other"]  # Gender field - validated by Literal type
    phone: str
    email: Optional[EmailStr] = None  # Optional email field with format validation
    date_of_birth: Optional[str] = None  # Optional DOB field (calendar widget on UI) - dd/mm/yyyy format
    address: Optional[str] = None  # Optional address field
    registration_date: str
    referral_source: Literal["doctor", "self", "friend", "online"]  # Referral source - validated by Literal type
    referral_subcategory: Optional[str] = None  # Optional subcategory (e.g., "Dr. Sharma", "Google", etc.)
    patient_status: Literal["Active", "Inactive", "VIP", "Do not treat", "Requires follow up"]  # Patient status - validated by Literal type
    important_notes: Optional[str] = None  # Optional notes - stored only in local server, not synced to main
    billed_amount: Optional[float] = 0.0  # Optional - generated after visits
    outstanding_amount: Optional[float] = 0.0  # Optional - generated after visits
    synced_to_main: Optional[bool] = False
    last_synced_at: Optional[datetime] = None
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number: exactly 10 digits, only digits allowed"""
        v = v.strip() if v else ""
        if not v or not v.isdigit() or len(v) != 10:
            raise ValueError("Phone number cannot be empty, must contain only digits, and exactly 10 digits")
        return v
    
    @field_validator('age')
    @classmethod
    def validate_age(cls, v: int) -> int:
        """Validate age: must be between 1 and 110, only digits"""
        if v < 1 or v > 110:
            raise ValueError("Age must be greater than 0 and 110 or less")
        return v
    
    @field_validator('date_of_birth')
    @classmethod
    def validate_date_of_birth(cls, v: Optional[str]) -> Optional[str]:
        """Validate date of birth: must be in dd/mm/yyyy format"""
        if v is None:
            return v
        
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Date of birth must be in dd/mm/yyyy format (e.g., 15/01/1994)")
        
        try:
            day, month, year = map(int, v.split('/'))
            current_year = date.today().year
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900 or year > current_year:
                raise ValueError(f"Invalid date: day (1-31), month (1-12), year (1900-{current_year})")
            date(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v
    

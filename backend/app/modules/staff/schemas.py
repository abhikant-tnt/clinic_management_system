from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
import re

def validate_phone(v: str) -> str:
    """Validate phone number: exactly 10 digits, only digits allowed"""
    v = v.strip() if v else ""
    if not v or not v.isdigit() or len(v) != 10:
        raise ValueError("Phone number must contain exactly 10 digits (numbers only)")
    return v

class StaffCreate(BaseModel):
    """Schema for creating staff"""
    tenant_id: Optional[str] = None
    firstname: str
    lastname: str
    speciality: Optional[str] = None
    phone: str

    @field_validator('firstname', 'lastname')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator('phone')
    @classmethod
    def validate_phone_field(cls, v: str) -> str:
        return validate_phone(v)

class StaffUpdate(BaseModel):
    """Schema for updating staff"""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    speciality: Optional[str] = None
    phone: Optional[str] = None

    @field_validator('firstname', 'lastname')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Name cannot be empty")
        return v.strip() if v else v

    @field_validator('phone')
    @classmethod
    def validate_phone_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone(v)

class Staff(BaseModel):
    """Schema for staff output"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    firstname: str
    lastname: str
    speciality: Optional[str] = None
    phone: str


from pydantic import BaseModel, field_validator
from typing import Optional
from app.core.validators import validate_phone_number


class UserCreate(BaseModel):
    """Schema for creating user"""
    tenant_id: Optional[str] = None
    firstname: str
    lastname: str
    speciality: Optional[str] = None
    phone: str
    username: Optional[str] = None
    password: Optional[str] = None
    user_type: Optional[str] = None  # owner, doctor, receptionist, staff

    @field_validator('firstname', 'lastname')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Name cannot exceed 255 characters")
        return v
    
    @field_validator('speciality')
    @classmethod
    def validate_speciality(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError("Speciality cannot exceed 255 characters")
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone_field(cls, v: str) -> str:
        return validate_phone_number(v)
    
    @field_validator('user_type')
    @classmethod
    def validate_user_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.lower().strip()
            allowed_types = ['owner', 'doctor', 'receptionist', 'staff', 'pharmacist']
            if v not in allowed_types:
                raise ValueError(f"user_type must be one of: {', '.join(allowed_types)}")
        return v

class UserUpdate(BaseModel):
    """Schema for updating user"""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    speciality: Optional[str] = None
    phone: Optional[str] = None
    user_type: Optional[str] = None

    @field_validator('firstname', 'lastname')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or not v.strip():
                raise ValueError("Name cannot be empty")
            v = v.strip()
            if len(v) > 255:
                raise ValueError("Name cannot exceed 255 characters")
        return v
    
    @field_validator('speciality')
    @classmethod
    def validate_speciality(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError("Speciality cannot exceed 255 characters")
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone_number(v)
    
    @field_validator('user_type')
    @classmethod
    def validate_user_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.lower().strip()
            allowed_types = ['owner', 'doctor', 'receptionist', 'staff', 'pharmacist']
            if v not in allowed_types:
                raise ValueError(f"user_type must be one of: {', '.join(allowed_types)}")
        return v

class User(BaseModel):
    """Schema for user output"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    firstname: str
    lastname: str
    speciality: Optional[str] = None
    phone: str
    user_type: Optional[str] = None
    is_active: Optional[bool] = None


class ProfileUpdate(BaseModel):
    """Schema for users to update their own profile"""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    speciality: Optional[str] = None
    phone: Optional[str] = None

    @field_validator('firstname', 'lastname')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v or not v.strip():
                raise ValueError("Name cannot be empty")
            v = v.strip()
            if len(v) > 255:
                raise ValueError("Name cannot exceed 255 characters")
        return v
    
    @field_validator('speciality')
    @classmethod
    def validate_speciality(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError("Speciality cannot exceed 255 characters")
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_phone_number(v)

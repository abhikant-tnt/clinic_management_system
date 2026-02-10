"""Authentication schemas for login and token management"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Literal
from datetime import datetime
import re
from app.core.validators import validate_phone_number


def validate_username_format(v: str) -> str:
    """Validate username: alphanumeric, underscore, hyphen only, no spaces"""
    v = v.strip()
    if not re.match(r'^[a-zA-Z0-9_-]+$', v):
        raise ValueError("Username can only contain letters, numbers, underscores, and hyphens. No spaces allowed.")
    return v

def validate_password_strength(v: str) -> str:
    """Validate password strength: min 8 chars, at least one uppercase, lowercase, and digit"""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r'[A-Z]', v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r'\d', v):
        raise ValueError("Password must contain at least one digit")
    return v


class UserLogin(BaseModel):
    """Schema for user login request"""
    username: str = Field(..., min_length=3, max_length=100, description="Username for login")
    password: str = Field(..., min_length=6, description="User password")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        return validate_username_format(v)


class Token(BaseModel):
    """Schema for authentication token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user_type: str = Field(..., description="User type: 'doctor' or 'staff'")
    user_id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    message: Optional[str] = Field(default="Login successful", description="Success message")


class UserRegister(BaseModel):
    """Schema for user registration (creates staff with login credentials)"""
    firstname: str = Field(..., min_length=1, max_length=255, description="First name")
    lastname: str = Field(..., min_length=1, max_length=255, description="Last name")
    phone: str = Field(..., description="Phone number (10 digits)")
    speciality: Optional[str] = Field(None, max_length=255, description="Speciality (for doctors)")
    username: str = Field(..., min_length=3, max_length=100, description="Username for login")
    password: str = Field(..., min_length=8, description="Password")
    user_type: Literal["owner", "doctor", "receptionist", "staff", "pharmacist"] = Field(..., description="User type")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        return validate_username_format(v)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)
    
    @field_validator('phone')
    @classmethod
    def validate_phone_field(cls, v: str) -> str:
        return validate_phone_number(v)
    
    @field_validator('firstname', 'lastname')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        if len(v.strip()) > 255:
            raise ValueError("Name cannot exceed 255 characters")
        return v.strip()
    
    @field_validator('speciality')
    @classmethod
    def validate_speciality(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError("Speciality cannot exceed 255 characters")
        return v


class UserResponse(BaseModel):
    """Schema for user information response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    username: str
    firstname: str
    lastname: str
    user_type: str
    speciality: Optional[str] = None
    phone: str
    is_active: bool
    tenant_id: Optional[str] = None
    last_login: Optional[datetime] = None


class ChangePasswordRequest(BaseModel):
    """Schema for changing user password"""
    current_password: str = Field(..., min_length=6, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ChangeUsernameRequest(BaseModel):
    """Schema for changing username"""
    current_password: str = Field(..., min_length=6, description="Password confirmation required")
    new_username: str = Field(..., min_length=3, max_length=100, description="New username")
    
    @field_validator('new_username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        return validate_username_format(v)


class UserDelete(BaseModel):
    """Schema for deleting current user's account"""
    password: str = Field(..., min_length=6, description="Password confirmation required for account deletion")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v
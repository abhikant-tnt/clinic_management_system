"""Authentication schemas for login and token management"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserLogin(BaseModel):
    """Schema for user login request"""
    username: str = Field(..., min_length=3, max_length=100, description="Username for login")
    password: str = Field(..., min_length=6, description="User password")


class Token(BaseModel):
    """Schema for authentication token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user_type: str = Field(..., description="User type: 'doctor' or 'staff'")
    user_id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")


class UserRegister(BaseModel):
    """Schema for user registration (creates staff with login credentials)"""
    firstname: str = Field(..., min_length=1, description="First name")
    lastname: str = Field(..., min_length=1, description="Last name")
    phone: str = Field(..., min_length=10, max_length=10, description="Phone number (10 digits)")
    speciality: Optional[str] = Field(None, description="Speciality (for doctors)")
    username: str = Field(..., min_length=3, max_length=100, description="Username for login")
    password: str = Field(..., min_length=6, description="Password")
    user_type: str = Field(..., description="User type: 'doctor' or 'staff'")


class UserResponse(BaseModel):
    """Schema for user information response"""
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

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating current user's account"""
    current_password: Optional[str] = Field(None, min_length=6, description="Current password (required if changing password)")
    new_password: Optional[str] = Field(None, min_length=6, description="New password")
    username: Optional[str] = Field(None, min_length=3, max_length=100, description="New username")


class UserDelete(BaseModel):
    """Schema for deleting current user's account"""
    password: str = Field(..., min_length=6, description="Password confirmation required for account deletion")
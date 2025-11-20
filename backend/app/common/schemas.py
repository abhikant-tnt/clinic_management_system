"""
Shared Pydantic schemas used across multiple modules
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BaseResponse(BaseModel):
    """Base response schema"""
    message: str
    success: bool = True

class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = 1
    page_size: int = 10
    
    class Config:
        from_attributes = True

class TimestampMixin(BaseModel):
    """Mixin for timestamps"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None



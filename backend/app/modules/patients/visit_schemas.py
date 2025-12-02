from pydantic import BaseModel, field_validator
from typing import Optional, Literal
from datetime import datetime, date
import re

class Visit(BaseModel):
    """Visit schema for response"""
    id: Optional[int] = None
    patient_id: int
    tenant_id: Optional[str] = None
    visit_date: str  # dd/mm/yyyy format
    visit_time: Optional[str] = None  # HH:MM format
    notes: Optional[str] = None  # Clinical notes
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    visit_status: Literal["Completed", "Cancelled", "Follow-up"] = "Completed"
    doctor_name: Optional[str] = None
    visit_charge: Optional[float] = 0.0  # Visit fee (can be waived = 0)
    medication_charge: Optional[float] = 0.0  # Medication cost (optional)
    total_charge: Optional[float] = 0.0  # Auto: visit_charge + medication_charge
    is_waived: Optional[bool] = False  # If visit charge is waived
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    synced_to_main: Optional[bool] = False
    last_synced_at: Optional[datetime] = None

    @field_validator('visit_date')
    @classmethod
    def validate_visit_date(cls, v: str) -> str:
        """Validate visit date: must be in dd/mm/yyyy format"""
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Visit date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            current_year = date.today().year
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900 or year > current_year:
                raise ValueError(f"Invalid date: day (1-31), month (1-12), year (1900-{current_year})")
            date(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v

    @field_validator('visit_time')
    @classmethod
    def validate_visit_time(cls, v: Optional[str]) -> Optional[str]:
        """Validate visit time: must be in HH:MM format"""
        if v is None:
            return v
        
        v = v.strip()
        if not re.match(r'^([01][0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError("Visit time must be in HH:MM format (e.g., 14:30)")
        
        return v

class VisitCreate(BaseModel):
    """Schema for creating a new visit"""
    patient_id: int
    visit_date: str
    visit_time: Optional[str] = None
    notes: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    visit_status: Literal["Completed", "Cancelled", "Follow-up"] = "Completed"
    doctor_name: Optional[str] = None
    visit_charge: Optional[float] = 0.0  # Visit fee (can be waived = 0)
    medication_charge: Optional[float] = 0.0  # Medication cost (optional)
    is_waived: Optional[bool] = False  # If visit charge is waived

    @field_validator('visit_date')
    @classmethod
    def validate_visit_date(cls, v: str) -> str:
        """Validate visit date: must be in dd/mm/yyyy format"""
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Visit date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            current_year = date.today().year
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900 or year > current_year:
                raise ValueError(f"Invalid date: day (1-31), month (1-12), year (1900-{current_year})")
            date(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v

    @field_validator('visit_time')
    @classmethod
    def validate_visit_time(cls, v: Optional[str]) -> Optional[str]:
        """Validate visit time: must be in HH:MM format"""
        if v is None:
            return v
        
        v = v.strip()
        if not re.match(r'^([01][0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError("Visit time must be in HH:MM format (e.g., 14:30)")
        
        return v

class VisitUpdate(BaseModel):
    """Schema for updating a visit"""
    visit_date: Optional[str] = None
    visit_time: Optional[str] = None
    notes: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    visit_status: Optional[Literal["Completed", "Cancelled", "Follow-up"]] = None
    doctor_name: Optional[str] = None
    visit_charge: Optional[float] = None  # Visit fee (can be waived = 0)
    medication_charge: Optional[float] = None  # Medication cost (optional)
    is_waived: Optional[bool] = None  # If visit charge is waived

    @field_validator('visit_date')
    @classmethod
    def validate_visit_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate visit date: must be in dd/mm/yyyy format"""
        if v is None:
            return v
        
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Visit date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            current_year = date.today().year
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900 or year > current_year:
                raise ValueError(f"Invalid date: day (1-31), month (1-12), year (1900-{current_year})")
            date(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v

    @field_validator('visit_time')
    @classmethod
    def validate_visit_time(cls, v: Optional[str]) -> Optional[str]:
        """Validate visit time: must be in HH:MM format"""
        if v is None:
            return v
        
        v = v.strip()
        if not re.match(r'^([01][0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError("Visit time must be in HH:MM format (e.g., 14:30)")
        
        return v


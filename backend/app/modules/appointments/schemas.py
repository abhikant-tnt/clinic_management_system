from pydantic import BaseModel, field_validator
from typing import Optional, Literal
from datetime import datetime, date
import re

class AppointmentCreate(BaseModel):
    """Schema for creating an appointment"""
    tenant_id: Optional[str] = None  # Will be set from settings if not provided
    patient_id: int
    doctor_id: int  # Required: FK to staff(id)
    appointment_date: str  # Required: dd/mm/yyyy format
    appointment_time: Optional[str] = None  # Optional: HH:MM format
    appointment_status: Literal["first time appointment", "follow up", "vip"] = "first time appointment"
    doctor_name: Optional[str] = None
    appointment_type: Optional[str] = None  # e.g., Consultation, Follow-up, Procedure)
    notes: Optional[str] = None
    payment_pending: bool = False
    follow_up_date: Optional[str] = None  # Optional: dd/mm/yyyy format
    # Clinical fields (only filled when status = "Completed")
    diagnosis: Optional[str] = None  # Optional diagnosis (treatment notes)
    treatment: Optional[str] = None  # Optional treatment details (treatment notes)
    visit_charge: Optional[float] = 0.0  # Visit fee (can be waived = 0)
    medication_charge: Optional[float] = 0.0  # Medication cost (optional)
    is_waived: Optional[bool] = False  # If visit charge is waived

    @field_validator('appointment_date')
    @classmethod
    def validate_appointment_date(cls, v: str) -> str:
        """Validate appointment date: must be in dd/mm/yyyy format"""
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
        """Validate appointment time: must be in HH:MM format"""
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^\d{2}:\d{2}$', v):
            raise ValueError("Appointment time must be in HH:MM format (e.g., 14:30)")
        
        try:
            hour, minute = map(int, v.split(':'))
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time: hour (0-23), minute (0-59)")
        except ValueError as e:
            raise ValueError(f"Invalid time: {str(e)}")
        
        return v

    @field_validator('follow_up_date')
    @classmethod
    def validate_follow_up_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate follow-up date: must be in dd/mm/yyyy format"""
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Follow-up date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900:
                raise ValueError("Invalid date: day (1-31), month (1-12), year (>= 1900)")
            date(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v

class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment"""
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_status: Optional[Literal["first time appointment", "follow up", "vip"]] = None
    doctor_name: Optional[str] = None
    appointment_type: Optional[str] = None
    notes: Optional[str] = None
    payment_pending: Optional[bool] = None
    follow_up_date: Optional[str] = None
    # Clinical fields (only filled when status = "Completed")
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    visit_charge: Optional[float] = None
    medication_charge: Optional[float] = None
    is_waived: Optional[bool] = None

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
        """Validate appointment time: must be in HH:MM format"""
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^\d{2}:\d{2}$', v):
            raise ValueError("Appointment time must be in HH:MM format (e.g., 14:30)")
        
        try:
            hour, minute = map(int, v.split(':'))
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time: hour (0-23), minute (0-59)")
        except ValueError as e:
            raise ValueError(f"Invalid time: {str(e)}")
        
        return v

    @field_validator('follow_up_date')
    @classmethod
    def validate_follow_up_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate follow-up date: must be in dd/mm/yyyy format"""
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', v):
            raise ValueError("Follow-up date must be in dd/mm/yyyy format (e.g., 15/01/2024)")
        
        try:
            day, month, year = map(int, v.split('/'))
            if day < 1 or day > 31 or month < 1 or month > 12 or year < 1900:
                raise ValueError("Invalid date: day (1-31), month (1-12), year (>= 1900)")
            date(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {str(e)}")
        
        return v

class Appointment(BaseModel):
    """Schema for appointment output"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    patient_id: int
    appointment_date: str
    appointment_time: Optional[str] = None
    appointment_status: Literal["first time appointment", "follow up", "vip"]
    doctor_name: Optional[str] = None
    appointment_type: Optional[str] = None
    notes: Optional[str] = None
    payment_pending: bool = False
    follow_up_date: Optional[str] = None
    # Clinical fields (only filled when status = "Completed")
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    visit_charge: Optional[float] = 0.0
    medication_charge: Optional[float] = 0.0
    total_charge: Optional[float] = 0.0  # Auto: visit_charge + medication_charge
    is_waived: Optional[bool] = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    synced_to_main: Optional[bool] = False
    last_synced_at: Optional[datetime] = None

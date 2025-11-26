from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

class Patient(BaseModel):
    id: Optional[int] = None #optional because it is not required to be provided when creating a patient
    tenant_id: Optional[str] = None  # Will be set from settings if not provided
    name: str
    age: int
    gender: Literal["male", "female", "other"]  # Gender field - validated by Literal type
    phone: str
    email: Optional[str] = None  # Optional email field
    date_of_birth: Optional[str] = None  # Optional DOB field (calendar widget on UI)
    address: Optional[str] = None  # Optional address field
    registration_date: str
    referral_source: Literal["doctor", "self", "friend", "online"]  # Referral source - validated by Literal type
    referral_subcategory: Optional[str] = None  # Optional subcategory (e.g., "Dr. Sharma", "Google", etc.)
    patient_status: Literal["Active", "Inactive", "VIP", "Do not treat", "Requires follow up"]  # Patient status - validated by Literal type
    important_notes: Optional[str] = None  # Optional notes - stored only in local server, not synced to main
    billed_amount: float
    outstanding_amount: float
    synced_to_main: Optional[bool] = False
    last_synced_at: Optional[datetime] = None
    

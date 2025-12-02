from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PatientDocument(BaseModel):
    """Patient document schema for response"""
    id: Optional[int] = None
    patient_id: int
    tenant_id: Optional[str] = None
    filename: str
    description: Optional[str] = None
    file_type: str
    file_size: int
    uploaded_at: Optional[datetime] = None
    synced_to_main: Optional[bool] = False
    last_synced_at: Optional[datetime] = None

class PatientDocumentCreate(BaseModel):
    """Schema for creating a document record"""
    patient_id: int
    filename: str
    description: Optional[str] = None
    file_type: str
    file_size: int


from pydantic import BaseModel
from typing import Optional

class Patient(BaseModel):
    id: Optional[int] = None #optional because it is not required to be provided when creating a patient
    name: str
    age: int
    phone: str
    email: Optional[str] = None  # Optional email field
    date_of_birth: Optional[str] = None  # Optional DOB field (calendar widget on UI)
    address: Optional[str] = None  # Optional address field
    registration_date: str
    billed_amount: float
    outstanding_amount: float
    

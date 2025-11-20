from pydantic import BaseModel
from typing import Optional

class Patient(BaseModel):
    id: Optional[int] = None #optional because it is not required to be provided when creating a patient
    name: str
    age: int
    phone: str
    registration_date: str
    billed_amount: float
    outstanding_amount: float
    

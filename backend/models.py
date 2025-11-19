from pydantic import BaseModel

class Patient(BaseModel):
    name: str
    age: int
    phone: str
    registration_date: str
    billed_amount: float
    outstanding_amount: float
    
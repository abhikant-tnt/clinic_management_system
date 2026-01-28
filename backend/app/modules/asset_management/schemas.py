from pydantic import BaseModel, field_validator
from typing import Optional

class RoomCreate(BaseModel):
    """Schema for Room - All fields are optional"""
    room_number: Optional[str] = None
    room_type: Optional[str] = None

    @field_validator('room_number')
    @classmethod
    def validate_room_no(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Room number cannot be empty if provided")
        return v

class MachineCreate(BaseModel):
    """Schema for Machine - All fields are optional"""
    name: Optional[str] = None
    status: Optional[str] = None
    room_id: Optional[int] = None

    @field_validator('name', 'status')
    @classmethod
    def validate_machine_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Field cannot be empty if provided")
        return v
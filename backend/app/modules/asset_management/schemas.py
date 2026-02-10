from pydantic import BaseModel, field_validator
from typing import Optional

class RoomCreate(BaseModel):
    """Schema for Room - Mandatory fields must be required"""
    room_number: str  # Required
    room_type: str    # Required

    @field_validator('room_number', 'room_type')
    @classmethod
    def validate_room_fields(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

class MachineCreate(BaseModel):
    """Schema for Machine - Mandatory fields must be required"""
    name: str    # Required
    status: str  # Required
    room_id: int # Required

    @field_validator('name', 'status')
    @classmethod
    def validate_machine_fields(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()
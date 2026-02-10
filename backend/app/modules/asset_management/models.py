"""SQLAlchemy models for Asset Management module"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.core.db_session import Base

class RoomModel(Base):
    __tablename__ = "procedure_rooms"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    room_number = Column(String, nullable=False)
    room_type = Column(String)  # e.g., 'Surgery', 'Consultation'
    is_available = Column(Boolean, default=True)

class MachineModel(Base):
    __tablename__ = "machines"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    name = Column(String, nullable=False)
    status = Column(String)  # e.g., 'Functional', 'Repair'
    room_id = Column(Integer, ForeignKey("procedure_rooms.id"), nullable=True)

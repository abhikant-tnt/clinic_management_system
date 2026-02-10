"""SQLAlchemy models for Appointments module"""
from sqlalchemy import Column, Integer, String, Text, Date, Time, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.db_session import Base

class AppointmentsModel(Base):
    """Appointment model"""
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients_table.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    appointment_date = Column(Date, nullable=False, index=True)
    appointment_time = Column(Time, nullable=True)
    status = Column(String(30), default="Scheduled", index=True)  # Default status when booking appointment
    doctor_name = Column(String(255), nullable=True, index=True)  # Kept for backward compatibility, but should use staff relationship
    purpose = Column(String(50), nullable=True)
    follow_up_date = Column(Date, nullable=True)
    payment = Column(String(20), default="Pending")
    interval = Column(String(20), nullable=True)  # Stores text value from UI dropdown
    # Relationships
    patient = relationship("PatientModel", back_populates="appointments")
    doctor = relationship("UserModel", foreign_keys=[doctor_id])

class PrescriptionModel(Base):
    """Prescription model"""
    __tablename__ = "prescriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_date = Column(Date, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    appointment = relationship("AppointmentsModel", backref="prescriptions")
    items = relationship("PrescriptionItemModel", back_populates="prescription", cascade="all, delete-orphan")

class PrescriptionItemModel(Base):
    """Prescription item model"""
    __tablename__ = "prescription_items"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(String(20), nullable=False)  # "Service" or "Product"
    source = Column(String(20), nullable=False)  # "Inventory" or "External"
    item_name = Column(Text, nullable=False)
    quantity = Column(Text, nullable=True)  # Text field for medical units (e.g., "10 tablets", "50 ml")
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Relationships
    prescription = relationship("PrescriptionModel", back_populates="items")
    inventory_item = relationship("InventoryItemModel")

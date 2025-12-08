"""SQLAlchemy models for the clinic management system"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, DECIMAL, ForeignKey, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class PatientModel(Base):
    """Patient model"""
    __tablename__ = "patients_table"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    title = Column(String(10), nullable=False)
    firstname = Column(String(255), nullable=False)
    lastname = Column(String(255), nullable=False)
    date_of_birth = Column(String(50), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    phone = Column(String(10), nullable=False)
    email = Column(String(255), nullable=True)
    address1 = Column(Text, nullable=False)
    address2 = Column(Text, nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    emergency_contact_name = Column(String(255), nullable=False)
    emergency_contact_phone = Column(String(10), nullable=False)
    referral_source = Column(String(20), nullable=False)
    referral_subcategory = Column(String(255), nullable=True)
    important_notes = Column(Text, nullable=True)
    patient_status = Column(String(30), nullable=False)
    last_visit_date = Column(String(50), nullable=True)
    registration_date = Column(String(50), nullable=False)
    synced_to_main = Column(Boolean, default=False)
    last_synced_at = Column(DateTime, nullable=True)
    # Relationships
    documents = relationship("DocumentsModel", back_populates="patient", cascade="all, delete-orphan")
    appointments = relationship("AppointmentsModel", back_populates="patient", cascade="all, delete-orphan")
    
    __table_args__ = (
        {'schema': None},  # Use default schema
    )

class AppointmentsModel(Base):
    """Appointment model"""
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients_table.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    appointment_date = Column(String(50), nullable=False, index=True)
    appointment_time = Column(String(10), nullable=True)
    status = Column(String(20), default="Active", index=True)
    doctor_name = Column(String(255), nullable=True, index=True)
    appointment_type = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    payment_pending = Column(Boolean, default=False)
    follow_up_date = Column(String(50), nullable=True)
    diagnosis = Column(Text, nullable=True)
    treatment = Column(Text, nullable=True)
    visit_charge = Column(DECIMAL(10, 2), default=0)
    medication_charge = Column(DECIMAL(10, 2), default=0)
    total_charge = Column(DECIMAL(10, 2), default=0)
    is_waived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    synced_to_main = Column(Boolean, default=False)
    last_synced_at = Column(DateTime, nullable=True)
    # Relationships
    patient = relationship("PatientModel", back_populates="appointments")

class DocumentsModel(Base):
    """Patient document model"""
    __tablename__ = "patient_documents"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients_table.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_type = Column(String(50), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.now, index=True)
    synced_to_main = Column(Boolean, default=False)
    last_synced_at = Column(DateTime, nullable=True)
    
    # Relationships
    patient = relationship("PatientModel", back_populates="documents")


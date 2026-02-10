"""SQLAlchemy models for Patients module"""
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.db_session import Base

class PatientModel(Base):
    """Patient model"""
    __tablename__ = "patients_table"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    firstname = Column(String(255), nullable=False)
    lastname = Column(String(255), nullable=False)
    dob = Column(Date, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    phone = Column(String(10), nullable=False)
    email = Column(String(255), nullable=False)  # Required field
    primary_doctor = Column(Integer, nullable=True)  # Staff ID (foreign key to staff table)
    blood_group = Column(String(10), nullable=True)
    status = Column(String(30), nullable=False)  # scheduled, no_show, cancelled, In progress, checked_in
    vip = Column(Boolean, nullable=True, default=False)  # VIP status
    address1 = Column(Text, nullable=False)
    address2 = Column(Text, nullable=True)
    country = Column(String(100), nullable=True)
    country2 = Column(String(100), nullable=True)  # Address 2 country
    city = Column(String(100), nullable=True)  # Made optional for dropdown
    city2 = Column(String(100), nullable=True)  # Address 2 city
    state = Column(String(100), nullable=True)  # Made optional for dropdown
    state2 = Column(String(100), nullable=True)  # Address 2 state
    pincode = Column(String(10), nullable=True)  # Made optional for dropdown
    pincode2 = Column(String(10), nullable=True)  # Address 2 pincode
    image = Column(String(255), nullable=True, default="None")  # Image upload field
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(10), nullable=True)
    referral_source = Column(String(20), nullable=True)
    referral_subcategory = Column(String(255), nullable=True)
    registration_date = Column(Date, nullable=False)
    past_medical_record = Column(Text, nullable=True, default="None")
    dermatological_history = Column(Text, nullable=True, default="None")
    medications = Column(Text, nullable=True, default="None")
    surgeries = Column(Text, nullable=True, default="None")
    hormonal_issues = Column(Text, nullable=True, default="None")
    allergies = Column(Text, nullable=True, default="None")
    lifestyle_assessment = Column(Text, nullable=True, default="None")
    # Billing Information - new fields
    billing_firstname = Column(String(255), nullable=True)
    billing_lastname = Column(String(255), nullable=True)
    billing_email = Column(String(255), nullable=True)
    billing_gstin = Column(String(50), nullable=True)
    billing_phone = Column(String(10), nullable=True)
    billing_address1 = Column(Text, nullable=True)
    billing_address2 = Column(Text, nullable=True)
    billing_country = Column(String(100), nullable=True)
    billing_country2 = Column(String(100), nullable=True)  # Billing address 2 country
    billing_state = Column(String(100), nullable=True)
    billing_state2 = Column(String(100), nullable=True)  # Billing address 2 state
    billing_city = Column(String(100), nullable=True)
    billing_city2 = Column(String(100), nullable=True)  # Billing address 2 city
    billing_pincode = Column(String(10), nullable=True)
    billing_pincode2 = Column(String(10), nullable=True)  # Billing address 2 pincode
    # Legacy billing fields (kept for backward compatibility)
    billing_name = Column(String(255), nullable=True)
    billing_address = Column(Text, nullable=True)
    # Relationships
    documents = relationship("DocumentsModel", back_populates="patient", cascade="all, delete-orphan")
    appointments = relationship("AppointmentsModel", back_populates="patient", cascade="all, delete-orphan")
    
    __table_args__ = (
        {'schema': None},  # Use default schema
    )

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
    
    # Relationships
    patient = relationship("PatientModel", back_populates="documents")

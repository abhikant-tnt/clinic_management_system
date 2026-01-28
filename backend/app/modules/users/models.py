"""SQLAlchemy models for Users module"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.core.models import Base

class UserModel(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    firstname = Column(String(255), nullable=False)
    lastname = Column(String(255), nullable=False)
    speciality = Column(String(255), nullable=True)
    phone = Column(String(10), nullable=False)
    username = Column(String(100), nullable=True, unique=True)
    password_hash = Column(String(255), nullable=True)
    user_type = Column(String(20), nullable=True, default='staff')  # platform_admin, owner, doctor, receptionist, staff, pharmacist
    is_active = Column(Boolean, nullable=True, default=True)
    last_login = Column(DateTime, nullable=True)

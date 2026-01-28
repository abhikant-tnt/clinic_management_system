"""SQLAlchemy Base and model imports for the clinic management system"""
from sqlalchemy.orm import declarative_base

# Create declarative base for all models
Base = declarative_base()

# Import all models from modules to ensure they're registered with Base
# This allows SQLAlchemy to discover all models for table creation
from app.modules.patients.models import PatientModel, DocumentsModel
from app.modules.appointments.models import AppointmentsModel, PrescriptionModel, PrescriptionItemModel
from app.modules.billing.models import BillingInvoiceModel, BillingItemModel
from app.modules.inventory.models import InventoryItemModel
from app.modules.users.models import UserModel
from app.modules.asset_management.models import RoomModel, MachineModel

# Export all models for convenience (backward compatibility)
__all__ = [
    "Base",
    "PatientModel",
    "DocumentsModel",
    "AppointmentsModel",
    "PrescriptionModel",
    "PrescriptionItemModel",
    "BillingInvoiceModel",
    "BillingItemModel",
    "PharmacyWalkInBillModel",
    "PharmacyWalkInItemModel",
    "InventoryItemModel",
    "UserModel",
    "RoomModel",
    "MachineModel",
]

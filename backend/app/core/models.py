from app.core.db_session import Base
from app.modules.patients.models import PatientModel, DocumentsModel
from app.modules.appointments.models import AppointmentsModel, PrescriptionModel, PrescriptionItemModel
from app.modules.billing.models import BillingInvoiceModel, BillingItemModel, PharmacyWalkInBillModel, PharmacyWalkInItemModel
from app.modules.inventory.models import InventoryItemModel
from app.modules.users.models import UserModel
from app.modules.asset_management.models import RoomModel, MachineModel

# Export all models for easy access and to ensure they're registered with Base
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

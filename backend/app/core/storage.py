"""File storage utilities for patient documents, photos, and prescriptions"""
from pathlib import Path
from typing import Optional
from app.core.config import settings
import shutil

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"

def get_patient_folder(patient_id: int, tenant_id: Optional[str] = None) -> Path:
    """Get folder path for patient: uploads/{tenant_id}/patients/id_{patient_id}"""
    return UPLOADS_DIR / (tenant_id or settings.TENANT_ID) / "patients" / f"id_{patient_id}"

def create_patient_folders(patient_id: int, tenant_id: Optional[str] = None) -> Path:
    """Create patient folder structure: photo/, documents/, prescriptions/"""
    folder = get_patient_folder(patient_id, tenant_id)
    for subfolder in ["photo", "documents", "prescriptions"]:
        (folder / subfolder).mkdir(parents=True, exist_ok=True)
    return folder

def get_patient_photo_path(patient_id: int, filename: str = "photo.jpg", tenant_id: Optional[str] = None) -> Path:
    """Get path for patient photo"""
    return get_patient_folder(patient_id, tenant_id) / "photo" / filename

def get_patient_document_path(patient_id: int, filename: str, tenant_id: Optional[str] = None) -> Path:
    """Get path for patient document"""
    return get_patient_folder(patient_id, tenant_id) / "documents" / filename

def get_patient_prescription_path(patient_id: int, filename: str, tenant_id: Optional[str] = None) -> Path:
    """Get path for patient prescription"""
    return get_patient_folder(patient_id, tenant_id) / "prescriptions" / filename

def get_visit_folder(patient_id: int, visit_id: int, tenant_id: Optional[str] = None) -> Path:
    """Get folder path for visit: uploads/{tenant_id}/patients/id_{patient_id}/visits/visit_{visit_id}"""
    return UPLOADS_DIR / (tenant_id or settings.TENANT_ID) / "patients" / f"id_{patient_id}" / "visits" / f"visit_{visit_id}"

def create_visit_folders(patient_id: int, visit_id: int, tenant_id: Optional[str] = None) -> Path:
    """Create visit folder structure: attachments/, prescription/"""
    folder = get_visit_folder(patient_id, visit_id, tenant_id)
    for subfolder in ["attachments", "prescription"]:
        (folder / subfolder).mkdir(parents=True, exist_ok=True)
    return folder

def get_visit_attachment_path(patient_id: int, visit_id: int, filename: str, tenant_id: Optional[str] = None) -> Path:
    """Get path for visit attachment"""
    return get_visit_folder(patient_id, visit_id, tenant_id) / "attachments" / filename

def get_visit_prescription_path(patient_id: int, visit_id: int, filename: str, tenant_id: Optional[str] = None) -> Path:
    """Get path for visit prescription"""
    return get_visit_folder(patient_id, visit_id, tenant_id) / "prescription" / filename

def delete_patient_folder(patient_id: int, tenant_id: Optional[str] = None) -> bool:
    """Delete patient folder and all contents"""
    try:
        folder = get_patient_folder(patient_id, tenant_id)
        if folder.exists():
            shutil.rmtree(folder)
            return True
        return False
    except Exception:  # pylint: disable=broad-except
        return False

def ensure_uploads_directory():
    """Ensure base uploads directory exists, create .gitkeep if needed"""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    gitkeep = UPLOADS_DIR / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()


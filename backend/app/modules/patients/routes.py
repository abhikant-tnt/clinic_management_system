from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import Optional
from app.modules.patients.schemas import Patient
from app.common.schemas import ErrorResponse
from app.core.database import (
    local_postgres_conn, 
    local_postgres_cursor, 
    prisma_client,
    sync_local_to_main
)
from app.core.config import settings
from app.core.storage import (
    create_patient_folders, 
    delete_patient_folder,
    get_patient_photo_path,
    get_patient_document_path,
    get_patient_folder,
    create_visit_folders,
    get_visit_attachment_path,
    get_visit_prescription_path,
    get_visit_folder
)
from app.modules.patients.visit_schemas import VisitCreate, VisitUpdate
from decimal import Decimal

router = APIRouter()

def get_tenant_id() -> str:
    """Get tenant ID from settings"""
    return settings.TENANT_ID

def patient_to_dict(patient) -> dict:
    """Convert patient object to dictionary"""
    if isinstance(patient, dict):
        return patient
    return {
                    "id": patient.id,
                    "tenant_id": patient.tenant_id,
                    "name": patient.name,
                    "age": patient.age,
                    "gender": patient.gender,
                    "phone": patient.phone,
                    "email": patient.email,
                    "date_of_birth": patient.date_of_birth,
                    "address": patient.address,
                    "registration_date": patient.registration_date,
                    "referral_source": patient.referral_source,
                    "referral_subcategory": patient.referral_subcategory,
                    "patient_status": patient.patient_status,
                    "important_notes": patient.important_notes,
                    "billed_amount": float(patient.billed_amount) if patient.billed_amount else 0.0,
                    "outstanding_amount": float(patient.outstanding_amount) if patient.outstanding_amount else 0.0
                }

def visit_to_dict(visit) -> dict:
    """Convert visit object to dictionary"""
    if isinstance(visit, dict):
        return visit
    return {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "tenant_id": visit.tenant_id,
        "visit_date": visit.visit_date,
        "visit_time": visit.visit_time,
        "notes": visit.notes,
        "diagnosis": visit.diagnosis,
        "treatment": visit.treatment,
        "visit_status": visit.visit_status,
        "doctor_name": visit.doctor_name,
        "visit_charge": float(visit.visit_charge) if visit.visit_charge else 0.0,
        "medication_charge": float(visit.medication_charge) if visit.medication_charge else 0.0,
        "total_charge": float(visit.total_charge) if visit.total_charge else 0.0,
        "is_waived": visit.is_waived if visit.is_waived else False,
        "created_at": visit.created_at.isoformat() if visit.created_at else None,
        "updated_at": visit.updated_at.isoformat() if visit.updated_at else None
    }

def check_patient_exists(patient_id: int, tenant_id: str) -> bool:
    """Check if patient exists"""
    if prisma_client:
        try:
            return prisma_client.patient.find_first(where={"id": patient_id, "tenant_id": tenant_id}) is not None
        except Exception:  # pylint: disable=broad-except
            return False
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT id FROM patients WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            return local_postgres_cursor.fetchone() is not None
        except Exception:  # pylint: disable=broad-except
            return False
    return False

def check_visit_exists(visit_id: int, patient_id: int, tenant_id: str) -> bool:
    """Check if visit exists"""
    if prisma_client:
        try:
            return prisma_client.visit.find_first(where={"id": visit_id, "patient_id": patient_id, "tenant_id": tenant_id}) is not None
        except Exception:  # pylint: disable=broad-except
            return False
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT id FROM visits WHERE id = %s AND patient_id = %s AND tenant_id = %s", (visit_id, patient_id, tenant_id))
            return local_postgres_cursor.fetchone() is not None
        except Exception:  # pylint: disable=broad-except
            return False
    return False

def get_patient_by_id(patient_id: int, tenant_id: str):
    """Get patient by ID, returns patient object or None"""
    if prisma_client:
        try:
            return prisma_client.patient.find_first(where={"id": patient_id, "tenant_id": tenant_id})
        except Exception:  # pylint: disable=broad-except
            return None
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT * FROM patients WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            record = local_postgres_cursor.fetchone()
            if record:
                columns = [desc[0] for desc in local_postgres_cursor.description]
                return dict(zip(columns, record))
        except Exception:  # pylint: disable=broad-except
            return None
    return None

def get_visit_by_id(visit_id: int, patient_id: int, tenant_id: str):
    """Get visit by ID, returns visit dict or None"""
    if prisma_client:
        try:
            visit = prisma_client.visit.find_first(where={"id": visit_id, "patient_id": patient_id, "tenant_id": tenant_id})
            return visit_to_dict(visit) if visit else None
        except Exception:  # pylint: disable=broad-except
            return None
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, patient_id, tenant_id, visit_date, visit_time, notes, diagnosis, 
                       treatment, visit_status, doctor_name, visit_charge, medication_charge, 
                       total_charge, is_waived, created_at, updated_at
                FROM visits WHERE id = %s AND patient_id = %s AND tenant_id = %s
            """, (visit_id, patient_id, tenant_id))
            record = local_postgres_cursor.fetchone()
            if record:
                columns = ["id", "patient_id", "tenant_id", "visit_date", "visit_time", "notes", 
                          "diagnosis", "treatment", "visit_status", "doctor_name", "visit_charge", 
                          "medication_charge", "total_charge", "is_waived", "created_at", "updated_at"]
                visit_dict = dict(zip(columns, record))
                visit_dict["created_at"] = visit_dict["created_at"].isoformat() if visit_dict.get("created_at") else None
                visit_dict["updated_at"] = visit_dict["updated_at"].isoformat() if visit_dict.get("updated_at") else None
                return visit_dict
        except Exception:  # pylint: disable=broad-except
            return None
    return None

def error_response(message: str, status_code: int = 400) -> JSONResponse:
    """Create standardized error response"""
    return JSONResponse(status_code=status_code, content=ErrorResponse(message=message).model_dump())

@router.get("/")
def get_patients(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    """Get all patients with pagination"""
    tenant_id = get_tenant_id()
    sync_local_to_main()
    
    patients_list = []
    if prisma_client:
        try:
            patients_list = [patient_to_dict(p) for p in prisma_client.patient.find_many(where={"tenant_id": tenant_id})]
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching patients (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT * FROM patients WHERE tenant_id = %s", (tenant_id,))
            columns = [desc[0] for desc in local_postgres_cursor.description]
            patients_list = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching patients: {e}")
    
    patients_list.sort(key=lambda x: x.get("id", 0))
    total = len(patients_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "patients": patients_list[(page - 1) * limit:page * limit],
        "pagination": {
            "total": total, "page": page, "limit": limit, "total_pages": total_pages,
            "has_next": page < total_pages, "has_prev": page > 1
        }
    } 

@router.get("/advanced-search")
def advanced_search_patients(
    q: Optional[str] = Query(None),
    age_min: Optional[int] = Query(None, ge=1, le=110),
    age_max: Optional[int] = Query(None, ge=1, le=110),
    gender: Optional[str] = Query(None),
    patient_status: Optional[str] = Query(None),
    last_visit_days: Optional[int] = Query(None, ge=1),
    sort_by: Optional[str] = Query("newest", regex="^(newest|oldest|alphabetic)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    """Advanced search with filters, sorting, and pagination"""
    tenant_id = get_tenant_id()
    
    # Build WHERE conditions
    conditions = ["tenant_id = %s"]
    params = [tenant_id]
    
    # Search filter
    if q and q.strip():
    search_term = q.strip()
        if search_term.isdigit():
            conditions.append("id = %s")
            params.append(int(search_term))
        else:
            conditions.append("(name ILIKE %s OR phone ILIKE %s OR email ILIKE %s)")
            params.extend([f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])
    
    # All filters
    if age_min is not None:
        conditions.append("age >= %s")
        params.append(age_min)
    if age_max is not None:
        conditions.append("age <= %s")
        params.append(age_max)
    if gender:
        conditions.append("gender = %s")
        params.append(gender)
    if patient_status:
        conditions.append("patient_status = %s")
        params.append(patient_status)
    
    # Fetch patients
    patients_list = []
    if prisma_client:
        try:
            all_patients = prisma_client.patient.find_many(where={"tenant_id": tenant_id})
            search_lower = q.strip().lower() if q and q.strip() else None
            
            for patient in all_patients:
                # Search filter
                if q and q.strip():
                    if q.strip().isdigit() and patient.id != int(q.strip()):
                        continue
                    elif not q.strip().isdigit():
                        if not ((patient.name and search_lower in patient.name.lower()) or
                               (patient.phone and search_lower in patient.phone.lower()) or
                               (patient.email and search_lower in (patient.email.lower() if patient.email else ""))):
                            continue
                
                # Apply other filters
                if age_min is not None and patient.age < age_min:
                    continue
                if age_max is not None and patient.age > age_max:
                    continue
                if gender and patient.gender != gender:
                    continue
                if patient_status and patient.patient_status != patient_status:
                    continue
                patients_list.append(patient_to_dict(patient))
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error searching (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            query = f"SELECT * FROM patients WHERE {' AND '.join(conditions)}"
            local_postgres_cursor.execute(query, params)
            columns = [desc[0] for desc in local_postgres_cursor.description]
            for record in local_postgres_cursor.fetchall():
                patients_list.append(dict(zip(columns, record)))
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error searching: {e}")
    
    # Last visit filter
    if last_visit_days:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=last_visit_days)
        filtered = []
        for patient in patients_list:
            patient_id = patient.get("id")
            try:
                if prisma_client:
                    last_visit = prisma_client.visit.find_first(
                        where={"patient_id": patient_id, "tenant_id": tenant_id},
                        order={"visit_date": "desc"}
                    )
                    if last_visit and last_visit.visit_date:
                        d, m, y = map(int, last_visit.visit_date.split('/'))
                        if datetime(y, m, d) >= cutoff:
                            filtered.append(patient)
                elif local_postgres_cursor:
                    local_postgres_cursor.execute(
                        "SELECT MAX(visit_date) FROM visits WHERE patient_id = %s AND tenant_id = %s",
                        (patient_id, tenant_id)
                    )
                    result = local_postgres_cursor.fetchone()
                    if result and result[0]:
                        d, m, y = map(int, result[0].split('/'))
                        if datetime(y, m, d) >= cutoff:
                            filtered.append(patient)
            except Exception:  # pylint: disable=broad-except
                pass
        patients_list = filtered
    
    # Sorting
    if sort_by == "newest":
        patients_list.sort(key=lambda x: x.get("id", 0), reverse=True)
    elif sort_by == "oldest":
        patients_list.sort(key=lambda x: x.get("id", 0))
    elif sort_by == "alphabetic":
        patients_list.sort(key=lambda x: x.get("name", "").lower())
    
    # Pagination
    total = len(patients_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    paginated = patients_list[(page - 1) * limit:page * limit]
    
    return {
        "patients": paginated,
        "pagination": {
            "total": total, "page": page, "limit": limit, "total_pages": total_pages,
            "has_next": page < total_pages, "has_prev": page > 1
        },
        "filters": {
            "search": q, "age_min": age_min, "age_max": age_max,
            "gender": gender, "patient_status": patient_status, "last_visit_days": last_visit_days
        },
        "sort_by": sort_by
    }

@router.get("/{patient_id}")
def get_patient(patient_id: int):
    """Get a single patient by ID for the current tenant"""
    tenant_id = get_tenant_id()
    patient = get_patient_by_id(patient_id, tenant_id)
            if patient:
        return {"database": "Local PostgreSQL", "patient": patient_to_dict(patient)}
    raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found.")

@router.post("/")
def create_patient(patient: Patient):
    """Create a new patient for the current tenant"""
    tenant_id = get_tenant_id()
    
    # Initial Validation
    # Note: Phone, age, email, and date_of_birth validation are handled by Pydantic validators in schemas.py
    # Phone must be exactly 10 digits, age must be 1-110, email format validated, date_of_birth must be dd/mm/yyyy
    if not patient.name:
        return error_response("Name cannot be empty", 400)
    # Handle optional amounts - default to 0.0 if not provided
    billed_amount = patient.billed_amount if patient.billed_amount is not None else 0.0
    outstanding_amount = patient.outstanding_amount if patient.outstanding_amount is not None else 0.0
    if billed_amount < 0 or outstanding_amount < 0:
        return error_response("Amounts cannot be negative", 400)
    # Gender validation is automatically handled by Pydantic Literal type

    # Check for existing phone number in local database
    postgres_existing = None
    if prisma_client:
        try:
            postgres_existing = prisma_client.patient.find_first(
                where={"phone": patient.phone, "tenant_id": tenant_id}
            )
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error checking phone in PostgreSQL (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute(
                "SELECT id FROM patients WHERE phone = %s AND tenant_id = %s", 
                (patient.phone, tenant_id)
            )
            postgres_existing = local_postgres_cursor.fetchone()
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error checking phone in PostgreSQL: {e}")
    
    if postgres_existing:
        return error_response("Patient with this phone number already exists for this tenant.", 400)
    
    # Set tenant_id if not provided
    if not patient.tenant_id:
        patient.tenant_id = tenant_id
    
    save_successful = False
    new_patient_id = None
    
    # Save to Local PostgreSQL
    if prisma_client:
        try:
            new_patient = prisma_client.patient.create(
                data={
                    "tenant_id": patient.tenant_id,
                    "name": patient.name,
                    "age": patient.age,
                    "gender": patient.gender,
                    "phone": patient.phone,
                    "email": patient.email,
                    "date_of_birth": patient.date_of_birth,
                    "address": patient.address,
                    "registration_date": patient.registration_date,
                    "referral_source": patient.referral_source,
                    "referral_subcategory": patient.referral_subcategory,
                    "patient_status": patient.patient_status,
                    "important_notes": patient.important_notes,
                    "billed_amount": Decimal(str(billed_amount)),
                    "outstanding_amount": Decimal(str(outstanding_amount)),
                    "synced_to_main": False
                }
            )
            new_patient_id = new_patient.id
            print(f"Patient successfully saved to Local PostgreSQL with ID {new_patient_id} (Prisma).")
            save_successful = True
        except Exception as e:  # pylint: disable=broad-except
            print(f"Local PostgreSQL save FAILED (Prisma). Error: {str(e)}.")
    elif local_postgres_cursor and local_postgres_conn:
        try:
            local_postgres_cursor.execute("""
                INSERT INTO patients (tenant_id, name, age, gender, phone, email, date_of_birth, address, 
                                    registration_date, referral_source, referral_subcategory, patient_status, 
                                    important_notes, billed_amount, outstanding_amount, synced_to_main)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                RETURNING id
            """, (
                patient.tenant_id, patient.name, patient.age, patient.gender, patient.phone, patient.email,
                patient.date_of_birth, patient.address, patient.registration_date,
                patient.referral_source, patient.referral_subcategory, patient.patient_status,
                patient.important_notes, billed_amount, outstanding_amount
            ))
            result = local_postgres_cursor.fetchone()
            new_patient_id = result[0] if result else None
            local_postgres_conn.commit()
            print(f"Patient successfully saved to Local PostgreSQL with ID {new_patient_id}.")
            save_successful = True
        except Exception as e:  # pylint: disable=broad-except
            print(f"Local PostgreSQL save FAILED. Error: {str(e)}.")
    
    # Sync to Main Server
    if save_successful and new_patient_id:
        sync_local_to_main()
        return {"message": f"Patient created successfully with ID {new_patient_id}."}
    else:
        raise HTTPException(
            status_code=503, 
            detail="Could not save patient. Local PostgreSQL is unavailable. Please check your database connections."
        )

@router.put("/{patient_id}")
def update_patient(patient_id: int, patient: Patient):
    """Update an existing patient for the current tenant"""
    tenant_id = get_tenant_id()
    
    # Validation
    # Note: Phone, age, email, and date_of_birth validation are handled by Pydantic validators in schemas.py
    if not patient.name:
        return error_response("Name cannot be empty", 400)
    
    # Handle optional amounts - default to existing values or 0.0
    billed_amount = patient.billed_amount if patient.billed_amount is not None else 0.0
    outstanding_amount = patient.outstanding_amount if patient.outstanding_amount is not None else 0.0
    if billed_amount < 0 or outstanding_amount < 0:
        return error_response("Amounts cannot be negative", 400)
    
    # Ensure tenant_id matches
    if not patient.tenant_id:
        patient.tenant_id = tenant_id
    
    # Update in Local PostgreSQL
    postgres_updated = False
    if prisma_client:
        try:
            prisma_client.patient.update(
                where={"id": patient_id, "tenant_id": tenant_id},
                data={
                    "name": patient.name,
                    "age": patient.age,
                    "gender": patient.gender,
                    "phone": patient.phone,
                    "email": patient.email,
                    "date_of_birth": patient.date_of_birth,
                    "address": patient.address,
                    "registration_date": patient.registration_date,
                    "referral_source": patient.referral_source,
                    "referral_subcategory": patient.referral_subcategory,
                    "patient_status": patient.patient_status,
                    "important_notes": patient.important_notes,
                    "billed_amount": Decimal(str(billed_amount)),
                    "outstanding_amount": Decimal(str(outstanding_amount)),
                    "synced_to_main": False  # Mark as unsynced after update
                }
            )
            print(f"Local PostgreSQL patient ID {patient_id} updated (Prisma).")
            postgres_updated = True
        except Exception as e:  # pylint: disable=broad-except
            print(f"Local PostgreSQL Update FAILED (Prisma). Error: {str(e)}.")
    elif local_postgres_cursor and local_postgres_conn:
        try:
            local_postgres_cursor.execute("""
                UPDATE patients
                SET name=%s, age=%s, gender=%s, phone=%s, email=%s, date_of_birth=%s, address=%s, 
                    registration_date=%s, referral_source=%s, referral_subcategory=%s, patient_status=%s, 
                    important_notes=%s, billed_amount=%s, outstanding_amount=%s, synced_to_main=FALSE
                WHERE id=%s AND tenant_id=%s
            """, (
                patient.name, patient.age, patient.gender, patient.phone, patient.email, patient.date_of_birth,
                patient.address, patient.registration_date, patient.referral_source, patient.referral_subcategory,
                patient.patient_status, patient.important_notes, billed_amount, outstanding_amount, 
                patient_id, tenant_id
            ))
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount == 1:
                print(f"Local PostgreSQL patient ID {patient_id} updated.")
                postgres_updated = True
        except Exception as e:  # pylint: disable=broad-except
            print(f"Local PostgreSQL Update FAILED. Error: {str(e)}.")
    
    # Sync to Main Server
    if postgres_updated:
        sync_local_to_main()
        return {"message": f"Patient with ID {patient_id} updated successfully in Local PostgreSQL."}
    else:
        raise HTTPException(
            status_code=404, 
            detail=f"Patient with ID {patient_id} not found for this tenant."
        )

@router.delete("/{patient_id}")
def delete_patient(patient_id: int):
    """Delete a patient by ID for the current tenant"""
    tenant_id = get_tenant_id()
    
    # Delete from Local PostgreSQL
    postgres_deleted = False
    if prisma_client:
        try:
            prisma_client.patient.delete(
                where={"id": patient_id, "tenant_id": tenant_id}
            )
            print(f"Patient with ID {patient_id} successfully deleted from Local PostgreSQL (Prisma).")
            postgres_deleted = True
        except Exception as e:  # pylint: disable=broad-except
            if "Record to delete does not exist" in str(e) or "not found" in str(e).lower():
                print(f"Patient with ID {patient_id} not found in Local PostgreSQL for deletion.")
            else:
                print(f"Error deleting patient from Local PostgreSQL (Prisma): {e}.")
    elif local_postgres_cursor and local_postgres_conn:
        try:
            local_postgres_cursor.execute(
                "DELETE FROM patients WHERE id = %s AND tenant_id = %s", 
                (patient_id, tenant_id)
            )
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount == 1:
                print(f"Patient with ID {patient_id} successfully deleted from Local PostgreSQL.")
                postgres_deleted = True
            else:
                print(f"Patient with ID {patient_id} not found in Local PostgreSQL for deletion.")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error deleting patient from Local PostgreSQL: {e}.")
    
    # Delete patient folder and all files
    if postgres_deleted:
        try:
            delete_patient_folder(patient_id, tenant_id)
            print(f"Patient folder deleted for ID {patient_id}")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Warning: Could not delete patient folder for ID {patient_id}: {e}")
        
        # Note: We don't delete from main server immediately - it will be handled by sync
        # or you can implement a separate endpoint for main server deletion if needed
        return {"message": f"Patient with ID {patient_id} deleted successfully from Local PostgreSQL."}
    else:
        raise HTTPException(
            status_code=404, 
            detail="Patient not found for this tenant to delete."
        )

# ============================================================
# File Upload/Download Endpoints
# ============================================================

@router.post("/{patient_id}/upload/photo")
async def upload_patient_photo(patient_id: int, file: UploadFile = File(...)):
    """Upload a patient photo. Accepts: JPG, PNG, JPEG"""
    tenant_id = get_tenant_id()
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, or JPEG images are allowed")
    
    # Validate patient exists
    try:
        if prisma_client:
            patient = prisma_client.patient.find_first(where={"id": patient_id, "tenant_id": tenant_id})
            if not patient:
                raise HTTPException(status_code=404, detail="Patient not found")
        elif local_postgres_cursor:
            local_postgres_cursor.execute("SELECT id FROM patients WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            if not local_postgres_cursor.fetchone():
                raise HTTPException(status_code=404, detail="Patient not found")
    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=f"Error checking patient: {str(e)}")
    
    # Get file extension
    file_ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if file_ext not in [".jpg", ".jpeg", ".png"]:
        file_ext = ".jpg"
    
    # Save file
    try:
        create_patient_folders(patient_id, tenant_id)
        photo_path = get_patient_photo_path(patient_id, f"photo{file_ext}", tenant_id)
        with open(photo_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {
            "message": "Photo uploaded successfully",
            "patient_id": patient_id,
            "filename": photo_path.name,
            "path": str(photo_path.relative_to(Path(__file__).parent.parent.parent.parent))
        }
    except Exception as e:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=f"Error uploading photo: {str(e)}")

@router.post("/{patient_id}/upload/document")
async def upload_patient_document(patient_id: int, file: UploadFile = File(...), description: str = Form(None)):
    """Upload a patient document (PDF, images, etc.) and save metadata to database"""
    tenant_id = get_tenant_id()
    
    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        return JSONResponse(status_code=400,
            content=ErrorResponse(message="Only PDF, JPG, PNG, or JPEG files are allowed").model_dump()
        )
    
    if not check_patient_exists(patient_id, tenant_id):
        return error_response("Patient not found", 404)
    
    # Generate safe filename
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_name = Path(file.filename).stem if file.filename else "document"
    file_ext = Path(file.filename).suffix if file.filename else ".pdf"
    safe_filename = f"{original_name}_{timestamp}{file_ext}"
    
    # Read file content and get size
    content = await file.read()
    file_size = len(content)
    
    # Determine file type
    file_type = "PDF" if file.content_type == "application/pdf" else "Image"
    
    # Save file
    try:
        create_patient_folders(patient_id, tenant_id)
        doc_path = get_patient_document_path(patient_id, safe_filename, tenant_id)
        with open(doc_path, "wb") as f:
            f.write(content)
        
        # Save metadata to database
        document_id = None
        if prisma_client:
            try:
                new_document = prisma_client.patientdocument.create(
                    data={
                        "patient_id": patient_id,
                        "tenant_id": tenant_id,
                        "filename": safe_filename,
                        "description": description,
                        "file_type": file_type,
                        "file_size": file_size,
                        "synced_to_main": False
                    }
                )
                document_id = new_document.id
            except Exception as e:  # pylint: disable=broad-except
                print(f"Error saving document metadata (Prisma): {e}")
        elif local_postgres_cursor and local_postgres_conn:
            try:
                local_postgres_cursor.execute("""
                    INSERT INTO patient_documents (patient_id, tenant_id, filename, description, file_type, file_size, synced_to_main)
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                    RETURNING id
                """, (patient_id, tenant_id, safe_filename, description, file_type, file_size))
                result = local_postgres_cursor.fetchone()
                document_id = result[0] if result else None
                local_postgres_conn.commit()
            except Exception as e:  # pylint: disable=broad-except
                print(f"Error saving document metadata: {e}")
        
        return {
            "message": "Document uploaded successfully",
            "document_id": document_id,
            "patient_id": patient_id,
            "filename": safe_filename,
            "description": description,
            "file_type": file_type,
            "file_size": file_size
        }
    except Exception as e:  # pylint: disable=broad-except
        return error_response(f"Error uploading document: {str(e)}", 500)

@router.get("/{patient_id}/files")
def list_patient_files(patient_id: int):
    """List all files for a patient (photo, documents from DB, prescriptions)"""
    tenant_id = get_tenant_id()
    
    if not check_patient_exists(patient_id, tenant_id):
        return error_response("Patient not found", 404)
    
    try:
        patient_folder = get_patient_folder(patient_id, tenant_id)
        files_list = {"photo": [], "documents": [], "prescriptions": []}
        
        # List photo files (from filesystem)
        photo_folder = patient_folder / "photo"
        if photo_folder.exists():
            files_list["photo"] = [f.name for f in photo_folder.iterdir() if f.is_file()]
        
        # List documents from database
        documents_list = []
        if prisma_client:
            try:
                documents = prisma_client.patientdocument.find_many(
                    where={"patient_id": patient_id, "tenant_id": tenant_id},
                    order={"uploaded_at": "desc"}
                )
                for doc in documents:
                    documents_list.append({
                        "id": doc.id,
                        "filename": doc.filename,
                        "description": doc.description,
                        "file_type": doc.file_type,
                        "file_size": doc.file_size,
                        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                    })
            except Exception as e:  # pylint: disable=broad-except
                print(f"Error fetching documents (Prisma): {e}")
        elif local_postgres_cursor:
            try:
                local_postgres_cursor.execute("""
                    SELECT id, filename, description, file_type, file_size, uploaded_at
                    FROM patient_documents
                    WHERE patient_id = %s AND tenant_id = %s
                    ORDER BY uploaded_at DESC
                """, (patient_id, tenant_id))
                columns = ["id", "filename", "description", "file_type", "file_size", "uploaded_at"]
                for record in local_postgres_cursor.fetchall():
                    doc_dict = dict(zip(columns, record))
                    doc_dict["uploaded_at"] = doc_dict["uploaded_at"].isoformat() if doc_dict["uploaded_at"] else None
                    documents_list.append(doc_dict)
            except Exception as e:  # pylint: disable=broad-except
                print(f"Error fetching documents: {e}")
        
        files_list["documents"] = documents_list
        
        # List prescription files (from filesystem)
        presc_folder = patient_folder / "prescriptions"
        if presc_folder.exists():
            files_list["prescriptions"] = [f.name for f in presc_folder.iterdir() if f.is_file()]
        
        return {"patient_id": patient_id, "files": files_list}
    except Exception as e:  # pylint: disable=broad-except
        return error_response(f"Error listing files: {str(e)}", 500)

@router.get("/{patient_id}/download/{file_type}/{filename}")
def download_patient_file(patient_id: int, file_type: str, filename: str):
    """Download a patient file. file_type: 'photo', 'documents', or 'prescriptions'"""
    tenant_id = get_tenant_id()
    
    if file_type not in ["photo", "documents", "prescriptions"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Use: photo, documents, or prescriptions")
    
    try:
        patient_folder = get_patient_folder(patient_id, tenant_id)
        file_path = patient_folder / file_type / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(path=str(file_path), filename=filename, media_type='application/octet-stream')
    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

# ============================================================
# Patient Visit History & Clinical Notes Endpoints
# ============================================================

@router.post("/{patient_id}/visits")
def create_visit(patient_id: int, visit: VisitCreate):
    """Create a new visit for a patient"""
    tenant_id = get_tenant_id()
    
    if not check_patient_exists(patient_id, tenant_id):
        return error_response(f"Patient with ID {patient_id} not found", 404)
    
    # Calculate total charge
    visit_charge = visit.visit_charge if visit.visit_charge is not None else 0.0
    medication_charge = visit.medication_charge if visit.medication_charge is not None else 0.0
    total_charge = visit_charge + medication_charge
    is_waived = visit.is_waived if visit.is_waived is not None else False
    
    # Create visit
    new_visit_id = None
    if prisma_client:
        try:
            new_visit = prisma_client.visit.create(
                data={
                    "patient_id": patient_id,
                    "tenant_id": tenant_id,
                    "visit_date": visit.visit_date,
                    "visit_time": visit.visit_time,
                    "notes": visit.notes,
                    "diagnosis": visit.diagnosis,
                    "treatment": visit.treatment,
                    "visit_status": visit.visit_status,
                    "doctor_name": visit.doctor_name,
                    "visit_charge": Decimal(str(visit_charge)),
                    "medication_charge": Decimal(str(medication_charge)),
                    "total_charge": Decimal(str(total_charge)),
                    "is_waived": is_waived,
                    "synced_to_main": False
                }
            )
            new_visit_id = new_visit.id
            create_visit_folders(patient_id, new_visit_id, tenant_id)
        except Exception as e:  # pylint: disable=broad-except
            return error_response(f"Error creating visit: {str(e)}", 500)
    elif local_postgres_cursor and local_postgres_conn:
        try:
            local_postgres_cursor.execute("""
                INSERT INTO visits (patient_id, tenant_id, visit_date, visit_time, notes, diagnosis, 
                                  treatment, visit_status, doctor_name, visit_charge, medication_charge, 
                                  total_charge, is_waived, synced_to_main)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                RETURNING id
            """, (
                patient_id, tenant_id, visit.visit_date, visit.visit_time, visit.notes,
                visit.diagnosis, visit.treatment, visit.visit_status, visit.doctor_name,
                visit_charge, medication_charge, total_charge, is_waived
            ))
            result = local_postgres_cursor.fetchone()
            new_visit_id = result[0] if result else None
            local_postgres_conn.commit()
            if new_visit_id:
                create_visit_folders(patient_id, new_visit_id, tenant_id)
        except Exception as e:  # pylint: disable=broad-except
            return error_response(f"Error creating visit: {str(e)}", 500)
    
    if new_visit_id:
        return {"message": f"Visit created successfully with ID {new_visit_id}", "visit_id": new_visit_id}
    else:
        return error_response("Failed to create visit", 500)

@router.get("/{patient_id}/visits")
def get_patient_visits(patient_id: int, page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    """Get all visits for a patient with pagination"""
    tenant_id = get_tenant_id()
    
    visits_list = []
    if prisma_client:
        try:
            visits = prisma_client.visit.find_many(
                where={"patient_id": patient_id, "tenant_id": tenant_id},
                order={"visit_date": "desc", "created_at": "desc"}
            )
            visits_list = [visit_to_dict(visit) for visit in visits]
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching visits (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, patient_id, tenant_id, visit_date, visit_time, notes, diagnosis, 
                       treatment, visit_status, doctor_name, visit_charge, medication_charge, 
                       total_charge, is_waived, created_at, updated_at
                FROM visits 
                WHERE patient_id = %s AND tenant_id = %s
                ORDER BY visit_date DESC, created_at DESC
            """, (patient_id, tenant_id))
            columns = ["id", "patient_id", "tenant_id", "visit_date", "visit_time", "notes", 
                      "diagnosis", "treatment", "visit_status", "doctor_name", "visit_charge", 
                      "medication_charge", "total_charge", "is_waived", "created_at", "updated_at"]
            for record in local_postgres_cursor.fetchall():
                visit_dict = dict(zip(columns, record))
                visit_dict["created_at"] = visit_dict["created_at"].isoformat() if visit_dict.get("created_at") else None
                visit_dict["updated_at"] = visit_dict["updated_at"].isoformat() if visit_dict.get("updated_at") else None
                visits_list.append(visit_dict)
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching visits: {e}")
    
    # Pagination
    total = len(visits_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    skip = (page - 1) * limit
    paginated_visits = visits_list[skip:skip + limit]
    
    return {
        "patient_id": patient_id,
        "visits": paginated_visits,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }

@router.get("/{patient_id}/visits/{visit_id}")
def get_visit(patient_id: int, visit_id: int):
    """Get a specific visit by ID"""
    tenant_id = get_tenant_id()
    visit_dict = get_visit_by_id(visit_id, patient_id, tenant_id)
    if visit_dict:
        return {"visit": visit_dict}
    return error_response(f"Visit with ID {visit_id} not found for patient {patient_id}", 404)

@router.put("/{patient_id}/visits/{visit_id}")
def update_visit(patient_id: int, visit_id: int, visit: VisitUpdate):
    """Update an existing visit"""
    tenant_id = get_tenant_id()
    
    # Build update data (only include fields that are provided)
    update_data = {}
    if visit.visit_date is not None:
        update_data["visit_date"] = visit.visit_date
    if visit.visit_time is not None:
        update_data["visit_time"] = visit.visit_time
    if visit.notes is not None:
        update_data["notes"] = visit.notes
    if visit.diagnosis is not None:
        update_data["diagnosis"] = visit.diagnosis
    if visit.treatment is not None:
        update_data["treatment"] = visit.treatment
    if visit.visit_status is not None:
        update_data["visit_status"] = visit.visit_status
    if visit.doctor_name is not None:
        update_data["doctor_name"] = visit.doctor_name
    if visit.visit_charge is not None:
        update_data["visit_charge"] = Decimal(str(visit.visit_charge))
    if visit.medication_charge is not None:
        update_data["medication_charge"] = Decimal(str(visit.medication_charge))
    if visit.is_waived is not None:
        update_data["is_waived"] = visit.is_waived
    
    # Recalculate total_charge if charge fields are updated
    if visit.visit_charge is not None or visit.medication_charge is not None:
        current_visit = get_visit_by_id(visit_id, patient_id, tenant_id) if (visit.visit_charge is None or visit.medication_charge is None) else None
        visit_charge = visit.visit_charge if visit.visit_charge is not None else (float(current_visit.get("visit_charge", 0)) if current_visit else 0.0)
        medication_charge = visit.medication_charge if visit.medication_charge is not None else (float(current_visit.get("medication_charge", 0)) if current_visit else 0.0)
        update_data["total_charge"] = Decimal(str(visit_charge + medication_charge))
    
    if not update_data:
        return error_response("No fields to update", 400)
    
    update_data["synced_to_main"] = False
    
    updated = False
    if prisma_client:
        try:
            prisma_client.visit.update(
                where={"id": visit_id, "patient_id": patient_id, "tenant_id": tenant_id},
                data=update_data
            )
            updated = True
        except Exception as e:  # pylint: disable=broad-except
            return error_response(f"Visit not found or update failed: {str(e)}", 404)
    elif local_postgres_cursor and local_postgres_conn:
        try:
            set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
            values = list(update_data.values()) + [visit_id, patient_id, tenant_id]
            local_postgres_cursor.execute(f"""
                UPDATE visits
                SET {set_clause}
                WHERE id = %s AND patient_id = %s AND tenant_id = %s
            """, values)
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount == 1:
                updated = True
        except Exception as e:  # pylint: disable=broad-except
            return error_response(f"Error updating visit: {str(e)}", 500)
    
    if updated:
        return {"message": f"Visit {visit_id} updated successfully"}
    else:
        return error_response(f"Visit with ID {visit_id} not found", 404)

@router.delete("/{patient_id}/visits/{visit_id}")
def delete_visit(patient_id: int, visit_id: int):
    """Delete a visit"""
    tenant_id = get_tenant_id()
    
    deleted = False
    if prisma_client:
        try:
            prisma_client.visit.delete(
                where={"id": visit_id, "patient_id": patient_id, "tenant_id": tenant_id}
            )
            deleted = True
        except Exception as e:  # pylint: disable=broad-except
            if "not found" in str(e).lower():
                return error_response(f"Visit with ID {visit_id} not found", 404)
    elif local_postgres_cursor and local_postgres_conn:
        try:
            local_postgres_cursor.execute(
                "DELETE FROM visits WHERE id = %s AND patient_id = %s AND tenant_id = %s",
                (visit_id, patient_id, tenant_id)
            )
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount == 1:
                deleted = True
        except Exception as e:  # pylint: disable=broad-except
            return error_response(f"Error deleting visit: {str(e)}", 500)
    
    if deleted:
        # Delete visit folder and all files
        try:
            visit_folder = get_visit_folder(patient_id, visit_id, tenant_id)
            if visit_folder.exists():
                import shutil
                shutil.rmtree(visit_folder)
        except Exception as e:  # pylint: disable=broad-except
            print(f"Warning: Could not delete visit folder: {e}")
        
        return {"message": f"Visit {visit_id} deleted successfully"}
    else:
        return error_response(f"Visit with ID {visit_id} not found", 404)

# ============================================================
# Visit File Upload/Download Endpoints
# ============================================================

@router.post("/{patient_id}/visits/{visit_id}/attachments")
async def upload_visit_attachment(patient_id: int, visit_id: int, file: UploadFile = File(...), description: str = Form(None)):
    """Upload an attachment for a visit (PDF, images, lab reports, etc.)"""
    tenant_id = get_tenant_id()
    
    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        return error_response("Only PDF, JPG, PNG, or JPEG files are allowed", 400)
    
    if not check_visit_exists(visit_id, patient_id, tenant_id):
        return error_response("Visit not found", 404)
    
    # Generate safe filename
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_name = Path(file.filename).stem if file.filename else "attachment"
    file_ext = Path(file.filename).suffix if file.filename else ".pdf"
    safe_filename = f"{original_name}_{timestamp}{file_ext}"
    
    # Save file
    try:
        create_visit_folders(patient_id, visit_id, tenant_id)
        attachment_path = get_visit_attachment_path(patient_id, visit_id, safe_filename, tenant_id)
        with open(attachment_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {
            "message": "Attachment uploaded successfully",
            "patient_id": patient_id,
            "visit_id": visit_id,
            "filename": safe_filename,
            "description": description
        }
    except Exception as e:  # pylint: disable=broad-except
        return error_response(f"Error uploading attachment: {str(e)}", 500)

@router.post("/{patient_id}/visits/{visit_id}/prescription")
async def upload_visit_prescription(patient_id: int, visit_id: int, file: UploadFile = File(...)):
    """Upload a prescription PDF for a visit"""
    tenant_id = get_tenant_id()
    
    # Validate file type (only PDF)
    if file.content_type != "application/pdf":
        return error_response("Only PDF files are allowed for prescriptions", 400)
    
    if not check_visit_exists(visit_id, patient_id, tenant_id):
        return error_response("Visit not found", 404)
    
    # Generate safe filename
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"prescription_{timestamp}.pdf"
    
    # Save file
    try:
        create_visit_folders(patient_id, visit_id, tenant_id)
        prescription_path = get_visit_prescription_path(patient_id, visit_id, safe_filename, tenant_id)
        with open(prescription_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {
            "message": "Prescription uploaded successfully",
            "patient_id": patient_id,
            "visit_id": visit_id,
            "filename": safe_filename
        }
    except Exception as e:  # pylint: disable=broad-except
        return error_response(f"Error uploading prescription: {str(e)}", 500)

@router.get("/{patient_id}/visits/{visit_id}/files")
def list_visit_files(patient_id: int, visit_id: int):
    """List all files for a visit (attachments and prescription)"""
    tenant_id = get_tenant_id()
    
    try:
        visit_folder = get_visit_folder(patient_id, visit_id, tenant_id)
        files_list = {"attachments": [], "prescription": []}
        
        # List attachment files
        attachments_folder = visit_folder / "attachments"
        if attachments_folder.exists():
            files_list["attachments"] = [f.name for f in attachments_folder.iterdir() if f.is_file()]
        
        # List prescription files
        prescription_folder = visit_folder / "prescription"
        if prescription_folder.exists():
            files_list["prescription"] = [f.name for f in prescription_folder.iterdir() if f.is_file()]
        
        return {"patient_id": patient_id, "visit_id": visit_id, "files": files_list}
    except Exception as e:  # pylint: disable=broad-except
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=f"Error listing files: {str(e)}").model_dump()
        )

@router.get("/{patient_id}/visits/{visit_id}/download/{file_type}/{filename}")
def download_visit_file(patient_id: int, visit_id: int, file_type: str, filename: str):
    """Download a visit file. file_type: 'attachments' or 'prescription'"""
    tenant_id = get_tenant_id()
    
    if file_type not in ["attachments", "prescription"]:
        return error_response("Invalid file type. Use: attachments or prescription", 400)
    
    try:
        if file_type == "attachments":
            file_path = get_visit_attachment_path(patient_id, visit_id, filename, tenant_id)
        else:
            file_path = get_visit_prescription_path(patient_id, visit_id, filename, tenant_id)
        
        if not file_path.exists():
            return error_response("File not found", 404)
        
        return FileResponse(path=str(file_path), filename=filename, media_type='application/octet-stream')
    except Exception as e:  # pylint: disable=broad-except
        return error_response(f"Error downloading file: {str(e)}", 500)

# ============================================================
# Patient Billing Summary Endpoints
# ============================================================

@router.get("/{patient_id}/billing/summary")
def get_patient_billing_summary(patient_id: int):
    """Get billing summary for a patient (total billed, total paid, total due, etc.)"""
    tenant_id = get_tenant_id()
    
    # Verify patient exists and get patient data
    patient_dict = None
    if prisma_client:
        try:
            patient = prisma_client.patient.find_first(
                where={"id": patient_id, "tenant_id": tenant_id}
            )
            if patient:
                patient_dict = {
                    "billed_amount": float(patient.billed_amount) if patient.billed_amount else 0.0,
                    "outstanding_amount": float(patient.outstanding_amount) if patient.outstanding_amount else 0.0
                }
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching patient (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute(
                "SELECT billed_amount, outstanding_amount FROM patients WHERE id = %s AND tenant_id = %s",
                (patient_id, tenant_id)
            )
            result = local_postgres_cursor.fetchone()
            if result:
                patient_dict = {
                    "billed_amount": float(result[0]) if result[0] else 0.0,
                    "outstanding_amount": float(result[1]) if result[1] else 0.0
                }
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching patient: {e}")
    
    if not patient_dict:
        return error_response(f"Patient with ID {patient_id} not found", 404)
    
    # Calculate total billed from visits
    total_billed_from_visits = 0.0
    visits_with_charges = 0
    if prisma_client:
        try:
            visits = prisma_client.visit.find_many(
                where={"patient_id": patient_id, "tenant_id": tenant_id}
            )
            for visit in visits:
                if visit.total_charge:
                    total_billed_from_visits += float(visit.total_charge)
                    visits_with_charges += 1
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching visits (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute(
                "SELECT total_charge FROM visits WHERE patient_id = %s AND tenant_id = %s",
                (patient_id, tenant_id)
            )
            for row in local_postgres_cursor.fetchall():
                if row[0]:
                    total_billed_from_visits += float(row[0])
                    visits_with_charges += 1
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error fetching visits: {e}")
    
    # Calculate totals
    total_billed = total_billed_from_visits  # Sum of all visit charges
    total_paid = patient_dict["billed_amount"]  # Manually set or auto-calculated
    total_due = patient_dict["outstanding_amount"]  # Manually set or auto-calculated
    
    # Last payment date - placeholder (null for now, will be from invoices table in future)
    last_payment_date = None
    
    # Invoice count - placeholder (0 for now, will be from invoices table in future)
    invoice_count = 0
    
    return {
        "patient_id": patient_id,
        "billing_summary": {
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_due": total_due,
            "last_payment_date": last_payment_date,
            "invoice_count": invoice_count,
            "visits_with_charges": visits_with_charges
        },
        "note": "Invoice table not implemented yet - using visit charges and patient billing fields"
    }

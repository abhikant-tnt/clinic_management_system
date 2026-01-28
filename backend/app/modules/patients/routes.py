from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import Optional, Any, Union, List
from datetime import date, timedelta
from app.modules.patients.schemas import PatientCreate, PatientUpdate, calculate_age
from app.common.schemas import ErrorResponse
from app.common.utils import validate_column_names, create_error_response, raise_not_found_error, raise_bad_request_error, raise_internal_server_error
from app.core.db_helper import check_exists, get_by_id
from app.core.date_helpers import string_to_date, date_to_string
from app.core.db_utils import get_db_session
from app.core.models import PatientModel, DocumentsModel, UserModel
from sqlalchemy import and_
from app.core.config import settings
from app.core.dependencies import get_current_active_user
from app.core.storage import (
    create_patient_folders, 
    delete_patient_folder,
    get_patient_photo_path,
    get_patient_document_path,
    get_patient_folder
)

router = APIRouter()

def get_tenant_id() -> str:
    return settings.TENANT_ID

@router.get("/users/doctors")
async def get_doctors_list(current_user: dict = Depends(get_current_active_user)):
    """Get list of staff members (doctors) for primary_doctor dropdown"""
    tenant_id = get_tenant_id()
    try:
        with get_db_session() as session:
            staff = session.query(UserModel).filter(
                and_(
                    UserModel.tenant_id == tenant_id,
                    UserModel.user_type.in_(['owner', 'doctor', 'receptionist'])
                )
            ).all()
            doctors = [{"id": s.id, "firstname": s.firstname, "lastname": s.lastname, "full_name": f"{s.firstname} {s.lastname}"} for s in staff]
        return {"doctors": doctors}
    except Exception as e:
        raise_internal_server_error(f"Error fetching doctors: {e}")

def patient_to_dict(patient_data: Any) -> dict:
    """Convert patient data to dict, handling DATE to string conversion"""
    if isinstance(patient_data, dict):
        # Convert DATE fields to string format for API response
        result = patient_data.copy()
        if "dob" in result and result["dob"] and not isinstance(result["dob"], str):
            result["dob"] = date_to_string(result["dob"])
        if "registration_date" in result and result["registration_date"] and not isinstance(result["registration_date"], str):
            result["registration_date"] = date_to_string(result["registration_date"])
        # Handle status field
        if "patient_status" in result and "status" not in result:
            result["status"] = result.get("patient_status")
        return result
    
    # Convert from model object
    dob_str = date_to_string(patient_data.dob) if hasattr(patient_data, 'dob') and patient_data.dob else None
    reg_date_str = date_to_string(patient_data.registration_date) if hasattr(patient_data, 'registration_date') and patient_data.registration_date else None
    
    # Get status (prefer new status field, fallback to patient_status for backward compatibility)
    status = getattr(patient_data, 'status', None) or getattr(patient_data, 'patient_status', None)
    
    return {
        "id": patient_data.id, "tenant_id": patient_data.tenant_id,
        "firstname": patient_data.firstname, "lastname": patient_data.lastname, 
        "dob": dob_str or (patient_data.dob if hasattr(patient_data, 'dob') else None),
        "age": patient_data.age, "gender": patient_data.gender, "phone": patient_data.phone,
        "email": patient_data.email, 
        "primary_doctor": getattr(patient_data, 'primary_doctor', None),  # Now stores staff ID
        "blood_group": getattr(patient_data, 'blood_group', None),
        "status": status,  # New field name
        "vip": getattr(patient_data, 'vip', False),
        "address1": patient_data.address1, "address2": getattr(patient_data, 'address2', None),
        "country": getattr(patient_data, 'country', None), "country2": getattr(patient_data, 'country2', None),
        "city": getattr(patient_data, 'city', None), "city2": getattr(patient_data, 'city2', None),
        "state": getattr(patient_data, 'state', None), "state2": getattr(patient_data, 'state2', None),
        "pincode": getattr(patient_data, 'pincode', None), "pincode2": getattr(patient_data, 'pincode2', None),
        "image": getattr(patient_data, 'image', "None"),
        "emergency_contact_name": getattr(patient_data, 'emergency_contact_name', None),
        "emergency_contact_phone": getattr(patient_data, 'emergency_contact_phone', None),
        "referral_source": getattr(patient_data, 'referral_source', None),
        "referral_subcategory": getattr(patient_data, 'referral_subcategory', None),
        "registration_date": reg_date_str or (patient_data.registration_date if hasattr(patient_data, 'registration_date') else None),
        "past_medical_record": getattr(patient_data, 'past_medical_record', "None"),
        "allergies": getattr(patient_data, 'allergies', "None"),
        "dermatological_history": getattr(patient_data, 'dermatological_history', "None"),
        "medications": getattr(patient_data, 'medications', "None"),
        "surgeries": getattr(patient_data, 'surgeries', "None"),
        "hormonal_issues": getattr(patient_data, 'hormonal_issues', "None"),
        "lifestyle_assessment": getattr(patient_data, 'lifestyle_assessment', "None"),
        # New billing fields
        "billing_firstname": getattr(patient_data, 'billing_firstname', None),
        "billing_lastname": getattr(patient_data, 'billing_lastname', None),
        "billing_email": getattr(patient_data, 'billing_email', None),
        "billing_gstin": getattr(patient_data, 'billing_gstin', None),
        "billing_phone": getattr(patient_data, 'billing_phone', None),
        "billing_address1": getattr(patient_data, 'billing_address1', None),
        "billing_address2": getattr(patient_data, 'billing_address2', None),
        "billing_country": getattr(patient_data, 'billing_country', None),
        "billing_country2": getattr(patient_data, 'billing_country2', None),
        "billing_state": getattr(patient_data, 'billing_state', None),
        "billing_state2": getattr(patient_data, 'billing_state2', None),
        "billing_city": getattr(patient_data, 'billing_city', None),
        "billing_city2": getattr(patient_data, 'billing_city2', None),
        "billing_pincode": getattr(patient_data, 'billing_pincode', None),
        "billing_pincode2": getattr(patient_data, 'billing_pincode2', None),
        # Legacy billing fields (for backward compatibility)
        "billing_name": getattr(patient_data, 'billing_name', None),
        "billing_address": getattr(patient_data, 'billing_address', None)
    }

def check_patient_exists(patient_id: int, tenant_id: str) -> bool:
    """Check if patient exists using database helper"""
    return check_exists(PatientModel, "patients_table", "id", patient_id, tenant_id)

def get_patient_by_id(patient_id: int, tenant_id: str) -> Union[dict, Any, None]:
    """Get patient by ID using database helper"""
    result = get_by_id(PatientModel, "patients_table", "id", patient_id, tenant_id)
    # If result is a dict, return it; if it's a model object, convert it
    if result and not isinstance(result, dict):
        return patient_to_dict(result)
    return result

# Use create_error_response from utils instead

def _insert_patient_sql(patient_data: PatientCreate, calculated_age: int, tenant_id_to_use: str) -> tuple:
    """Insert patient SQL with DATE conversion"""
    # Convert date strings to Date objects for database
    dob_date = string_to_date(patient_data.dob)
    if not dob_date:
        raise ValueError("Invalid date format. Use dd/mm/yyyy")
    reg_date = string_to_date(patient_data.registration_date) if patient_data.registration_date else None
    # Legacy SQL function - kept for reference but not used (ORM is used instead)
    insert_sql = """INSERT INTO patients_table (tenant_id, firstname, lastname, dob, age, gender, phone, email, primary_doctor, blood_group,
                    address1, address2, country, city, state, pincode, emergency_contact_name, emergency_contact_phone,
                    registration_date, referral_source, referral_subcategory, status, 
                    past_medical_record, dermatological_history,
                    medications, surgeries, hormonal_issues, allergies, lifestyle_assessment,
                    billing_name, billing_gstin, billing_phone, billing_state, billing_address)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id"""
    params = (tenant_id_to_use, patient_data.firstname.lower(), patient_data.lastname.lower(),
              dob_date, calculated_age, patient_data.gender.lower(), patient_data.phone,
              patient_data.email.lower() if patient_data.email else None,
              patient_data.primary_doctor,
              patient_data.blood_group,
              patient_data.address1.lower(), patient_data.address2.lower() if patient_data.address2 else None,
              patient_data.country.lower() if patient_data.country else None,
              patient_data.city.lower() if patient_data.city else None, patient_data.state.lower() if patient_data.state else None, patient_data.pincode,
              patient_data.emergency_contact_name.lower() if patient_data.emergency_contact_name else None, patient_data.emergency_contact_phone,
              reg_date, patient_data.referral_source.lower() if patient_data.referral_source else None,
              patient_data.referral_subcategory.lower() if patient_data.referral_subcategory else None,
              patient_data.status,
              patient_data.past_medical_record or "None", patient_data.dermatological_history or "None",
              patient_data.medications or "None", patient_data.surgeries or "None", patient_data.hormonal_issues or "None",
              patient_data.allergies or "None", patient_data.lifestyle_assessment or "None",
              patient_data.billing_name, patient_data.billing_gstin,
              patient_data.billing_phone, patient_data.billing_state.lower() if patient_data.billing_state else None,
              patient_data.billing_address.lower() if patient_data.billing_address else None)
    return insert_sql, params

@router.get("/")
async def get_patients(
    page: int = Query(1, ge=1), 
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    week_start: Optional[str] = Query(None, description="Week start date (dd/mm/yyyy). Defaults to current week"),
    current_user: dict = Depends(get_current_active_user)
):
    """Get patients for table view - default to current week, sorted by status (In progress first, then scheduled for today)"""
    tenant_id = get_tenant_id()
    
    # Calculate current week dates if not provided
    today = date.today()
    if week_start:
        try:
            week_start_date = string_to_date(week_start)
        except:
            week_start_date = today
    else:
        # Get start of current week (Monday)
        days_since_monday = today.weekday()
        week_start_date = today - timedelta(days=days_since_monday)
    
    week_end_date = week_start_date + timedelta(days=6)  # Sunday
    
    patients_list = []
    try:
        with get_db_session() as session:
            # Filter patients registered in current week
            patients = session.query(PatientModel).filter(
                and_(
                    PatientModel.tenant_id == tenant_id,
                    PatientModel.registration_date >= week_start_date,
                    PatientModel.registration_date <= week_end_date
                )
            ).all()
            patients_list = [patient_to_dict(p) for p in patients]
    except Exception as e:
        raise_internal_server_error(f"Error fetching patients: {e}")
    
    # Sort by status: In progress first, then scheduled for today, then others
    def sort_key(patient):
        status = patient.get("status", "").lower()
        reg_date = patient.get("registration_date")
        is_today = False
        if reg_date:
            try:
                if isinstance(reg_date, str):
                    reg_date_obj = string_to_date(reg_date)
                else:
                    reg_date_obj = reg_date
                is_today = reg_date_obj == today
            except:
                pass
        
        # Priority: In progress > scheduled for today > others
        if status == "in progress":
            return (0, 0 if is_today else 1, patient.get("id", 0))
        elif status == "scheduled" and is_today:
            return (1, 0, patient.get("id", 0))
        else:
            return (2, 0 if is_today else 1, patient.get("id", 0))
    
    patients_list.sort(key=sort_key)
    
    # Format for table view: Patient (name), Patient ID, Number, Email ID, Status, Photos, Allergies, Action
    table_patients = []
    for p in patients_list:
        # Check if patient has photos
        has_photos = False
        try:
            patient_folder = get_patient_folder(p["id"], tenant_id)
            photo_folder = patient_folder / "photo"
            if photo_folder.exists() and any(photo_folder.iterdir()):
                has_photos = True
        except:
            pass
        
        table_patients.append({
            "id": p["id"],
            "patient": f"{p.get('firstname', '')} {p.get('lastname', '')}".strip(),
            "patient_id": f"#{p.get('id', 0)}",
            "number": p.get("phone", ""),
            "email_id": p.get("email", ""),
            "status": p.get("status", ""),
            "photos": "View" if has_photos else "None",
            "allergies": "View" if p.get("allergies") and p.get("allergies") != "None" else "None",
            # Action buttons will be handled by frontend
        })
    
    total = len(table_patients)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "patients": table_patients[(page - 1) * limit:page * limit],
        "pagination": {
            "total": total, 
            "page": page, 
            "limit": limit, 
            "total_pages": total_pages, 
            "has_next": page < total_pages, 
            "has_prev": page > 1
        },
        "week_start": date_to_string(week_start_date),
        "week_end": date_to_string(week_end_date)
    } 

@router.get("/advanced-search")
async def advanced_search_patients(
    q: Optional[str] = Query(None),
    age_min: Optional[int] = Query(None, ge=1, le=110),
    age_max: Optional[int] = Query(None, ge=1, le=110),
    gender: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Filter by patient status"),
    last_visit_days: Optional[int] = Query(None, ge=1),
    sort_by: Optional[str] = Query("newest", pattern="^(newest|oldest|alphabetic)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    current_user: dict = Depends(get_current_active_user)
):
    tenant_id = get_tenant_id()
    conditions = ["tenant_id = %s"]
    params = [tenant_id]
    if q and q.strip():
        search_term = q.strip()
        if search_term.isdigit():
            conditions.append("id = %s")
            params.append(int(search_term))
        else:
            conditions.append("(firstname ILIKE %s OR lastname ILIKE %s OR phone ILIKE %s OR email ILIKE %s)")
            params.extend([f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])
    if age_min is not None:
        conditions.append("age >= %s")
        params.append(age_min)
    if age_max is not None:
        conditions.append("age <= %s")
        params.append(age_max)
    if gender:
        conditions.append("gender = %s")
        params.append(gender)
    if status:
        # Check both status and patient_status fields for backward compatibility
        conditions.append("(status = %s OR patient_status = %s)")
        params.extend([status, status])
    
    patients_list = []
    if postgres_cursor:
        try:
            postgres_cursor.execute("SELECT * FROM patients_table WHERE tenant_id = %s", (tenant_id,))
            columns = [desc[0] for desc in postgres_cursor.description]
            all_patients = [dict(zip(columns, r)) for r in postgres_cursor.fetchall()]
            search_lower = q.strip().lower() if q and q.strip() else None
            for patient_data in all_patients:
                if q and q.strip():
                    if q.strip().isdigit() and patient_data.id != int(q.strip()):
                        continue
                    elif not q.strip().isdigit():
                        firstname = (patient_data.firstname or "").lower() if hasattr(patient_data, 'firstname') else (patient_data.get("firstname") or "").lower()
                        lastname = (patient_data.lastname or "").lower() if hasattr(patient_data, 'lastname') else (patient_data.get("lastname") or "").lower()
                        phone = (patient_data.phone or "").lower() if hasattr(patient_data, 'phone') else (patient_data.get("phone") or "").lower()
                        email = (patient_data.email or "").lower() if hasattr(patient_data, 'email') else (patient_data.get("email") or "").lower()
                        if not (search_lower in firstname or search_lower in lastname or search_lower in phone or search_lower in email):
                            continue
                if age_min is not None and patient_data.age < age_min:
                    continue
                if age_max is not None and patient_data.age > age_max:
                    continue
                if gender and patient_data.gender != gender:
                    continue
                if status:
                    patient_status_val = getattr(patient_data, 'status', None) or getattr(patient_data, 'patient_status', None)
                    if patient_status_val != status:
                        continue
                patients_list.append(patient_to_dict(patient_data))
        except Exception as e:
            pass
    if postgres_cursor:
        try:
            query = f"SELECT * FROM patients_table WHERE {' AND '.join(conditions)}"
            postgres_cursor.execute(query, params)
            columns = [desc[0] for desc in postgres_cursor.description]
            for record in postgres_cursor.fetchall():
                patients_list.append(dict(zip(columns, record)))
        except Exception as e:
            pass
    if last_visit_days:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=last_visit_days)
        filtered = []
        for patient_data in patients_list:
            patient_id = patient_data.get("id")
            try:
                if postgres_cursor:
                    postgres_cursor.execute(
                        "SELECT MAX(visit_date) FROM visits WHERE patient_id = %s AND tenant_id = %s",
                        (patient_id, tenant_id)
                    )
                    result = postgres_cursor.fetchone()
                    if result and result[0]:
                        d, m, y = map(int, result[0].split('/'))
                        if datetime(y, m, d) >= cutoff:
                            filtered.append(patient_data)
            except Exception:
                pass
        patients_list = filtered
    if sort_by == "newest":
        patients_list.sort(key=lambda x: x.get("id", 0), reverse=True)
    elif sort_by == "oldest":
        patients_list.sort(key=lambda x: x.get("id", 0))
    elif sort_by == "alphabetic":
        patients_list.sort(key=lambda x: (x.get("firstname", "").lower(), x.get("lastname", "").lower()))
    total = len(patients_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    paginated = patients_list[(page - 1) * limit:page * limit]
    
    return {
        "patients": paginated,
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1},
        "filters": {"search": q, "age_min": age_min, "age_max": age_max, "gender": gender, "status": status, "last_visit_days": last_visit_days},
        "sort_by": sort_by
    }

@router.get("/{patient_id}")
async def get_patient(patient_id: int, current_user: dict = Depends(get_current_active_user)):
    tenant_id = get_tenant_id()
    patient_data = get_patient_by_id(patient_id, tenant_id)
    if patient_data:
        return {"database": "PostgreSQL", "patient": patient_to_dict(patient_data)}
    raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found.")

@router.post("/")
async def create_patient(patient_data: PatientCreate, current_user: dict = Depends(get_current_active_user)):
    """Create a new patient - auto-saves registration_date as today's date if not provided"""
    tenant_id = get_tenant_id()
    calculated_age = calculate_age(patient_data.dob)
    
    if not patient_data.firstname or not patient_data.firstname.strip():
        return create_error_response("Firstname cannot be empty", 400)
    if not patient_data.lastname or not patient_data.lastname.strip():
        return create_error_response("Lastname cannot be empty", 400)
    tenant_id_to_use = patient_data.tenant_id if patient_data.tenant_id else tenant_id
    
    # Convert date strings to Date objects
    dob_date = string_to_date(patient_data.dob)
    if not dob_date:
        return create_error_response("Invalid date format. Use dd/mm/yyyy", 400)
    
    # Auto-save registration_date as today's date if not provided
    if patient_data.registration_date:
        reg_date = string_to_date(patient_data.registration_date)
    else:
        reg_date = date.today()  # Auto-save today's date
    
    try:
        with get_db_session() as session:
            # Check if patient with same phone exists
            existing = session.query(PatientModel).filter(
                and_(PatientModel.phone == patient_data.phone, PatientModel.tenant_id == tenant_id_to_use)
            ).first()
            if existing:
                return create_error_response("Patient with this phone number already exists for this tenant.", 400)
            
            # Get primary_doctor - default to first doctor if not provided
            primary_doctor_id = patient_data.primary_doctor
            if not primary_doctor_id:
                # Get first doctor from users table (user_type='doctor' or 'owner', is_active=True, ORDER BY id ASC)
                first_doctor = session.query(UserModel).filter(
                    and_(
                        UserModel.tenant_id == tenant_id_to_use,
                        UserModel.is_active == True,
                        UserModel.user_type.in_(['owner', 'doctor', 'receptionist'])
                    )
                ).order_by(UserModel.id.asc()).first()
                
                if not first_doctor:
                    return create_error_response("No active doctor/user found. Please create a doctor/user first.", 400)
                primary_doctor_id = first_doctor.id
            
            # Validate primary_doctor exists
            doctor = session.query(UserModel).filter(
                and_(UserModel.id == primary_doctor_id, UserModel.tenant_id == tenant_id_to_use)
            ).first()
            if not doctor:
                return create_error_response(f"Doctor with ID {primary_doctor_id} not found.", 400)
            
            new_patient = PatientModel(
                tenant_id=tenant_id_to_use,
                firstname=patient_data.firstname.lower(),
                lastname=patient_data.lastname.lower(),
                dob=dob_date,
                age=calculated_age,
                gender=patient_data.gender.lower(),
                phone=patient_data.phone,
                email=patient_data.email.lower(),  # Required field
                primary_doctor=primary_doctor_id,  # Staff ID (integer) - defaults to first doctor
                blood_group=patient_data.blood_group,
                status=patient_data.status,  # New field name
                vip=patient_data.vip if patient_data.vip is not None else False,
                address1=patient_data.address1.lower(),
                address2=patient_data.address2.lower() if patient_data.address2 else None,
                country=patient_data.country.lower() if patient_data.country else None,
                country2=patient_data.country2.lower() if patient_data.country2 else None,
                city=patient_data.city.lower() if patient_data.city else None,
                city2=patient_data.city2.lower() if patient_data.city2 else None,
                state=patient_data.state.lower() if patient_data.state else None,
                state2=patient_data.state2.lower() if patient_data.state2 else None,
                pincode=patient_data.pincode,
                pincode2=patient_data.pincode2,
                image=patient_data.image or "None",
                emergency_contact_name=patient_data.emergency_contact_name.lower() if patient_data.emergency_contact_name else None,
                emergency_contact_phone=patient_data.emergency_contact_phone,
                registration_date=reg_date,  # Auto-saved as today if not provided
                referral_source=patient_data.referral_source.lower() if patient_data.referral_source else None,
                referral_subcategory=patient_data.referral_subcategory.lower() if patient_data.referral_subcategory else None,
                # Medical history in order: past_medical_record, allergies, dermatological_history, medications, surgeries, hormonal_issues, lifestyle_assessment
                past_medical_record=patient_data.past_medical_record or "None",
                allergies=patient_data.allergies or "None",
                dermatological_history=patient_data.dermatological_history or "None",
                medications=patient_data.medications or "None",
                surgeries=patient_data.surgeries or "None",
                hormonal_issues=patient_data.hormonal_issues or "None",
                lifestyle_assessment=patient_data.lifestyle_assessment or "None",
                # New billing fields
                billing_firstname=patient_data.billing_firstname.lower() if patient_data.billing_firstname else None,
                billing_lastname=patient_data.billing_lastname.lower() if patient_data.billing_lastname else None,
                billing_email=patient_data.billing_email.lower() if patient_data.billing_email else None,
                billing_gstin=patient_data.billing_gstin,
                billing_phone=patient_data.billing_phone,
                billing_address1=patient_data.billing_address1.lower() if patient_data.billing_address1 else None,
                billing_address2=patient_data.billing_address2.lower() if patient_data.billing_address2 else None,
                billing_country=patient_data.billing_country.lower() if patient_data.billing_country else None,
                billing_country2=patient_data.billing_country2.lower() if patient_data.billing_country2 else None,
                billing_state=patient_data.billing_state.lower() if patient_data.billing_state else None,
                billing_state2=patient_data.billing_state2.lower() if patient_data.billing_state2 else None,
                billing_city=patient_data.billing_city.lower() if patient_data.billing_city else None,
                billing_city2=patient_data.billing_city2.lower() if patient_data.billing_city2 else None,
                billing_pincode=patient_data.billing_pincode,
                billing_pincode2=patient_data.billing_pincode2
            )
            session.add(new_patient)
            session.commit()
            session.refresh(new_patient)
            new_patient_id = new_patient.id
        
        return {"message": f"Patient created successfully with ID {new_patient_id}.", "patient_id": new_patient_id, "registration_date": date_to_string(reg_date)}
    except Exception as e:
        raise_internal_server_error(f"Error creating patient: {e}")

@router.put("/{patient_id}")
async def update_patient(patient_id: int, patient_data: PatientUpdate, current_user: dict = Depends(get_current_active_user)):
    tenant_id = get_tenant_id()
    if not check_patient_exists(patient_id, tenant_id):
        raise_not_found_error("Patient", patient_id)
    
    calculated_age = calculate_age(patient_data.dob) if patient_data.dob else None
    update_data = {}
    if patient_data.firstname is not None:
        if not patient_data.firstname.strip():
            return create_error_response("Firstname cannot be empty", 400)
        update_data["firstname"] = patient_data.firstname.lower()
    if patient_data.lastname is not None:
        if not patient_data.lastname.strip():
            return create_error_response("Lastname cannot be empty", 400)
        update_data["lastname"] = patient_data.lastname.lower()
    if calculated_age is not None:
        update_data["age"] = calculated_age
    if patient_data.gender is not None:
        update_data["gender"] = patient_data.gender.lower()
    if patient_data.phone is not None:
        update_data["phone"] = patient_data.phone
    if patient_data.email is not None:
        update_data["email"] = patient_data.email.lower() if patient_data.email else None
    if patient_data.dob is not None:
        update_data["dob"] = patient_data.dob
    if patient_data.primary_doctor is not None:
        update_data["primary_doctor"] = patient_data.primary_doctor  # Staff ID (integer)
    if patient_data.blood_group is not None:
        update_data["blood_group"] = patient_data.blood_group
    if patient_data.status is not None:
        update_data["status"] = patient_data.status
    if patient_data.vip is not None:
        update_data["vip"] = patient_data.vip
    if patient_data.country is not None:
        update_data["country"] = patient_data.country.lower() if patient_data.country else None
    if patient_data.country2 is not None:
        update_data["country2"] = patient_data.country2.lower() if patient_data.country2 else None
    if patient_data.city2 is not None:
        update_data["city2"] = patient_data.city2.lower() if patient_data.city2 else None
    if patient_data.state2 is not None:
        update_data["state2"] = patient_data.state2.lower() if patient_data.state2 else None
    if patient_data.pincode2 is not None:
        update_data["pincode2"] = patient_data.pincode2
    if patient_data.image is not None:
        update_data["image"] = patient_data.image
    if patient_data.past_medical_record is not None:
        update_data["past_medical_record"] = patient_data.past_medical_record
    if patient_data.dermatological_history is not None:
        update_data["dermatological_history"] = patient_data.dermatological_history
    if patient_data.medications is not None:
        update_data["medications"] = patient_data.medications
    if patient_data.surgeries is not None:
        update_data["surgeries"] = patient_data.surgeries
    if patient_data.hormonal_issues is not None:
        update_data["hormonal_issues"] = patient_data.hormonal_issues
    if patient_data.allergies is not None:
        update_data["allergies"] = patient_data.allergies
    if patient_data.lifestyle_assessment is not None:
        update_data["lifestyle_assessment"] = patient_data.lifestyle_assessment
    # New billing fields
    if patient_data.billing_firstname is not None:
        update_data["billing_firstname"] = patient_data.billing_firstname.lower() if patient_data.billing_firstname else None
    if patient_data.billing_lastname is not None:
        update_data["billing_lastname"] = patient_data.billing_lastname.lower() if patient_data.billing_lastname else None
    if patient_data.billing_email is not None:
        update_data["billing_email"] = patient_data.billing_email.lower() if patient_data.billing_email else None
    if patient_data.billing_gstin is not None:
        update_data["billing_gstin"] = patient_data.billing_gstin
    if patient_data.billing_phone is not None:
        update_data["billing_phone"] = patient_data.billing_phone
    if patient_data.billing_address1 is not None:
        update_data["billing_address1"] = patient_data.billing_address1.lower() if patient_data.billing_address1 else None
    if patient_data.billing_address2 is not None:
        update_data["billing_address2"] = patient_data.billing_address2.lower() if patient_data.billing_address2 else None
    if patient_data.billing_country is not None:
        update_data["billing_country"] = patient_data.billing_country.lower() if patient_data.billing_country else None
    if patient_data.billing_country2 is not None:
        update_data["billing_country2"] = patient_data.billing_country2.lower() if patient_data.billing_country2 else None
    if patient_data.billing_state is not None:
        update_data["billing_state"] = patient_data.billing_state.lower() if patient_data.billing_state else None
    if patient_data.billing_state2 is not None:
        update_data["billing_state2"] = patient_data.billing_state2.lower() if patient_data.billing_state2 else None
    if patient_data.billing_city is not None:
        update_data["billing_city"] = patient_data.billing_city.lower() if patient_data.billing_city else None
    if patient_data.billing_city2 is not None:
        update_data["billing_city2"] = patient_data.billing_city2.lower() if patient_data.billing_city2 else None
    if patient_data.billing_pincode is not None:
        update_data["billing_pincode"] = patient_data.billing_pincode
    if patient_data.billing_pincode2 is not None:
        update_data["billing_pincode2"] = patient_data.billing_pincode2
    # Legacy billing fields
    if patient_data.billing_name is not None:
        update_data["billing_name"] = patient_data.billing_name
    if patient_data.billing_address is not None:
        update_data["billing_address"] = patient_data.billing_address.lower() if patient_data.billing_address else None
    if patient_data.address1 is not None:
        update_data["address1"] = patient_data.address1.lower()
    if patient_data.address2 is not None:
        update_data["address2"] = patient_data.address2.lower() if patient_data.address2 else None
    if patient_data.city is not None:
        update_data["city"] = patient_data.city.lower()
    if patient_data.state is not None:
        update_data["state"] = patient_data.state.lower()
    if patient_data.pincode is not None:
        update_data["pincode"] = patient_data.pincode
    if patient_data.emergency_contact_name is not None:
        update_data["emergency_contact_name"] = patient_data.emergency_contact_name.lower()
    if patient_data.emergency_contact_phone is not None:
        update_data["emergency_contact_phone"] = patient_data.emergency_contact_phone
    if patient_data.registration_date is not None:
        update_data["registration_date"] = patient_data.registration_date
    if patient_data.referral_source is not None:
        update_data["referral_source"] = patient_data.referral_source.lower()
    if patient_data.referral_subcategory is not None:
        update_data["referral_subcategory"] = patient_data.referral_subcategory.lower() if patient_data.referral_subcategory else None
    # Status field already handled above
    if not update_data:
        return create_error_response("No fields provided for update", 400)
    
    try:
        with get_db_session() as session:
            patient = session.query(PatientModel).filter(
                and_(PatientModel.id == patient_id, PatientModel.tenant_id == tenant_id)
            ).first()
            if not patient:
                raise_not_found_error(f"Patient with ID {patient_id} not found for this tenant.")
            for key, value in update_data.items():
                setattr(patient, key, value)
            
            session.commit()
            session.refresh(patient)
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"An unexpected error occurred while updating patient: {str(e)}")
    
    # Legacy SQL code removed - ORM only
    
    return {"message": f"Patient with ID {patient_id} updated successfully."}

@router.delete("/{patient_id}")
async def delete_patient(patient_id: int, current_user: dict = Depends(get_current_active_user)):
    tenant_id = get_tenant_id()
    
    if not check_patient_exists(patient_id, tenant_id):
        raise_not_found_error("Patient", patient_id)
    
    try:
        with get_db_session() as session:
            patient = session.query(PatientModel).filter(
                and_(PatientModel.id == patient_id, PatientModel.tenant_id == tenant_id)
            ).first()
            if patient:
                session.delete(patient)
                session.commit()
        
        # Delete patient files (non-critical, log errors but don't fail)
        try:
            delete_patient_folder(patient_id, tenant_id)
        except Exception as e:
            print(f"Warning: Failed to delete patient files: {e}")
        
        return {"message": f"Patient with ID {patient_id} deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_server_error(f"Error deleting patient: {e}")

@router.post("/{patient_id}/upload/photo")
async def upload_patient_photo(patient_id: int, file: UploadFile = File(...), current_user: dict = Depends(get_current_active_user)):  # upload a patient photo. accepts: JPG, PNG, JPEG
    tenant_id = get_tenant_id()
    allowed_types = ["image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, or JPEG images are allowed")
    
    # Validate patient exists
    try:
        if postgres_cursor:
            postgres_cursor.execute("SELECT id FROM patients_table WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            if not postgres_cursor.fetchone():
                raise HTTPException(status_code=404, detail="Patient not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error checking patient. Please try again or contact support.")
    file_ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if file_ext not in [".jpg", ".jpeg", ".png"]:
        file_ext = ".jpg"
    try:
        create_patient_folders(patient_id, tenant_id)
        photo_path = get_patient_photo_path(patient_id, f"photo{file_ext}", tenant_id)
        with open(photo_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {
            "message": "Photo uploaded successfully", "patient_id": patient_id, "filename": photo_path.name,
            "path": str(photo_path.relative_to(Path(__file__).parent.parent.parent.parent))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error uploading photo. Please try again or contact support.")

@router.post("/{patient_id}/upload/document")
async def upload_patient_document(patient_id: int, file: UploadFile = File(...), description: str = Form(None), current_user: dict = Depends(get_current_active_user)):  # upload a patient document (PDF, images, etc.) and save metadata to database
    tenant_id = get_tenant_id()
    
    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        return JSONResponse(status_code=400,
            content=ErrorResponse(message="Only PDF, JPG, PNG, or JPEG files are allowed").model_dump()
        )
    
    if not check_patient_exists(patient_id, tenant_id):
        raise_not_found_error("Patient", patient_id)
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_name = Path(file.filename).stem if file.filename else "document"
    file_ext = Path(file.filename).suffix if file.filename else ".pdf"
    safe_filename = f"{original_name}_{timestamp}{file_ext}"
    content = await file.read()
    file_size = len(content)
    file_type = "PDF" if file.content_type == "application/pdf" else "Image"
    try:
        create_patient_folders(patient_id, tenant_id)
        doc_path = get_patient_document_path(patient_id, safe_filename, tenant_id)
        with open(doc_path, "wb") as f:
            f.write(content)
        document_id = None
        try:
            with get_db_session() as session:
                doc = DocumentsModel(
                    patient_id=patient_id, tenant_id=tenant_id, filename=safe_filename,
                    description=description, file_type=file_type, file_size=file_size
                )
                session.add(doc)
                session.commit()
                session.refresh(doc)
                document_id = doc.id
        except Exception as e:
            raise_internal_server_error(f"An unexpected error occurred while uploading document: {str(e)}")
        
        # Legacy code removed - ORM only now
        if False:
            try:
                postgres_cursor.execute("""
                    INSERT INTO patient_documents (patient_id, tenant_id, filename, description, file_type, file_size)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (patient_id, tenant_id, safe_filename, description, file_type, file_size))
                result = postgres_cursor.fetchone()
                document_id = result[0] if result else None
                postgres_conn.commit()
            except Exception as e:
                pass
        return {
            "message": "Document uploaded successfully", "document_id": document_id, "patient_id": patient_id,
            "filename": safe_filename, "description": description, "file_type": file_type, "file_size": file_size
        }
    except Exception as e:
        raise_internal_server_error("Error uploading document. Please try again or contact support.")

@router.get("/{patient_id}/files")
async def list_patient_files(
    patient_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    current_user: dict = Depends(get_current_active_user)
):  # list all files for a patient (photo, documents from DB, prescriptions)
    tenant_id = get_tenant_id()
    
    if not check_patient_exists(patient_id, tenant_id):
        raise_not_found_error("Patient", patient_id)
    
    try:
        patient_folder = get_patient_folder(patient_id, tenant_id)
        files_list = {"photo": [], "documents": [], "prescriptions": []}
        
        # List photo files (from filesystem) - typically only 1 photo, no pagination needed
        photo_folder = patient_folder / "photo"
        if photo_folder.exists():
            files_list["photo"] = [f.name for f in photo_folder.iterdir() if f.is_file()]
        
        # Paginate documents from database
        documents_list = []
        total_docs = 0
        try:
            with get_db_session() as session:
                docs_query = session.query(DocumentsModel).filter(
                    and_(DocumentsModel.patient_id == patient_id, DocumentsModel.tenant_id == tenant_id)
                )
                
                # Get total count for pagination
                total_docs = docs_query.count()
                
                # Apply pagination
                docs = docs_query.order_by(DocumentsModel.uploaded_at.desc()).offset((page - 1) * limit).limit(limit).all()
                documents_list = [{
                    "id": doc.id, "filename": doc.filename, "description": doc.description,
                    "file_type": doc.file_type, "file_size": doc.file_size,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                } for doc in docs]
        except Exception as e:
            # Error fetching documents - return empty list
            pass
        
        files_list["documents"] = documents_list
        
        # List prescription files (from filesystem) - typically small, no pagination needed
        presc_folder = patient_folder / "prescriptions"
        if presc_folder.exists():
            files_list["prescriptions"] = [f.name for f in presc_folder.iterdir() if f.is_file()]
        
        total_pages = (total_docs + limit - 1) // limit if total_docs > 0 else 1
        
        return {
            "patient_id": patient_id,
            "files": files_list,
            "pagination": {
                "total": total_docs,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except Exception as e:
        raise_internal_server_error("Error listing files. Please try again or contact support.")

@router.get("/{patient_id}/download/{file_type}/{filename}")
async def download_patient_file(patient_id: int, file_type: str, filename: str, current_user: dict = Depends(get_current_active_user)):
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
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error downloading file. Please try again or contact support.")

@router.get("/{patient_id}/billing/summary")
async def get_patient_billing_summary(patient_id: int, current_user: dict = Depends(get_current_active_user)):
    tenant_id = get_tenant_id()
    if not check_patient_exists(patient_id, tenant_id):
        raise_not_found_error("Patient", patient_id)
    total_billed_from_appointments = 0.0
    appointments_with_charges = 0
    if postgres_cursor:
        try:
            postgres_cursor.execute(
                "SELECT total_charge FROM appointments WHERE patient_id = %s AND tenant_id = %s AND status = 'Completed'",
                (patient_id, tenant_id)
            )
            for row in postgres_cursor.fetchall():
                if row[0]:
                    total_billed_from_appointments += float(row[0])
                    appointments_with_charges += 1
        except Exception as e:
            pass
    last_payment_date = None
    invoice_count = 0
    
    return {
        "patient_id": patient_id,
        "billing_summary": {
            "total_billed_from_appointments": total_billed_from_appointments, "last_payment_date": last_payment_date,
            "invoice_count": invoice_count, "completed_appointments_with_charges": appointments_with_charges
        },
        "note": "Billing amounts removed from patient module. Will be handled in billing module. This shows appointment charges only."
    }

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import Optional, Any, Union
from app.modules.patients.schemas import PatientCreate, PatientUpdate, calculate_age
from app.common.schemas import ErrorResponse
from app.common.utils import validate_column_names, create_error_response, raise_not_found_error, raise_bad_request_error, raise_internal_server_error
from app.core.db_helper import check_exists, get_by_id
from app.core.date_helpers import string_to_date, date_to_string
from app.core.database import (
    postgres_conn, 
    postgres_cursor, 
    db_session,
    ensure_tables_exist
)
from app.core.models import PatientModel, DocumentsModel
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

def patient_to_dict(patient_data: Any) -> dict:
    """Convert patient data to dict, handling DATE to string conversion"""
    if isinstance(patient_data, dict):
        # Convert DATE fields to string format for API response
        result = patient_data.copy()
        if "dob" in result and result["dob"] and not isinstance(result["dob"], str):
            result["dob"] = date_to_string(result["dob"])
        if "last_visit_date" in result and result["last_visit_date"] and not isinstance(result["last_visit_date"], str):
            result["last_visit_date"] = date_to_string(result["last_visit_date"])
        if "registration_date" in result and result["registration_date"] and not isinstance(result["registration_date"], str):
            result["registration_date"] = date_to_string(result["registration_date"])
        return result
    
    # Convert from model object
    dob_str = date_to_string(patient_data.dob) if hasattr(patient_data, 'dob') and patient_data.dob else None
    last_visit_str = date_to_string(patient_data.last_visit_date) if hasattr(patient_data, 'last_visit_date') and patient_data.last_visit_date else None
    reg_date_str = date_to_string(patient_data.registration_date) if hasattr(patient_data, 'registration_date') and patient_data.registration_date else None
    
    return {
        "id": patient_data.id, "tenant_id": patient_data.tenant_id,
        "firstname": patient_data.firstname, "lastname": patient_data.lastname, "dob": dob_str or (patient_data.dob if hasattr(patient_data, 'dob') else None),
        "age": patient_data.age, "gender": patient_data.gender, "phone": patient_data.phone,
        "email": patient_data.email, "primary_doctor": patient_data.primary_doctor, "blood_group": getattr(patient_data, 'blood_group', None),
        "address1": patient_data.address1, "address2": patient_data.address2, "country": patient_data.country, "city": patient_data.city,
        "state": patient_data.state, "pincode": patient_data.pincode, "emergency_contact_name": patient_data.emergency_contact_name,
        "emergency_contact_phone": patient_data.emergency_contact_phone, "referral_source": patient_data.referral_source, "referral_subcategory": patient_data.referral_subcategory,
        "patient_status": patient_data.patient_status, "important_notes": patient_data.important_notes, "last_visit_date": last_visit_str or (patient_data.last_visit_date if hasattr(patient_data, 'last_visit_date') else None),
        "registration_date": reg_date_str or (patient_data.registration_date if hasattr(patient_data, 'registration_date') else None), "purpose": patient_data.purpose, "past_medical_record": patient_data.past_medical_record,
        "dermatological_history": patient_data.dermatological_history, "medications": patient_data.medications, "surgeries": patient_data.surgeries,
        "hormonal_issues": patient_data.hormonal_issues, "allergies": getattr(patient_data, 'allergies', None), "lifestyle_assessment": getattr(patient_data, 'lifestyle_assessment', None),
        "billing_name": getattr(patient_data, 'billing_name', None), "billing_gstin": getattr(patient_data, 'billing_gstin', None),
        "billing_phone": getattr(patient_data, 'billing_phone', None), "billing_state": getattr(patient_data, 'billing_state', None),
        "billing_address": getattr(patient_data, 'billing_address', None), "payment_method_cash": getattr(patient_data, 'payment_method_cash', None),
        "payment_method_gst": getattr(patient_data, 'payment_method_gst', None), "payment_method_card": getattr(patient_data, 'payment_method_card', None),
        "card_name": getattr(patient_data, 'card_name', None)
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
    last_visit = string_to_date(patient_data.last_visit_date) if patient_data.last_visit_date else None
    
    insert_sql = """INSERT INTO patients_table (tenant_id, firstname, lastname, dob, age, gender, phone, email, primary_doctor, blood_group,
                    address1, address2, country, city, state, pincode, emergency_contact_name, emergency_contact_phone,
                    registration_date, referral_source, referral_subcategory, patient_status, 
                    important_notes, last_visit_date, purpose, past_medical_record, dermatological_history,
                    medications, surgeries, hormonal_issues, allergies, lifestyle_assessment,
                    billing_name, billing_gstin, billing_phone, billing_state, billing_address,
                    payment_method_cash, payment_method_gst, payment_method_card, card_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id"""
    params = (tenant_id_to_use, patient_data.firstname.lower(), patient_data.lastname.lower(),
              dob_date, calculated_age, patient_data.gender.lower(), patient_data.phone,
              patient_data.email.lower() if patient_data.email else None,
              patient_data.primary_doctor.lower() if patient_data.primary_doctor else None,
              patient_data.blood_group,
              patient_data.address1.lower(), patient_data.address2.lower() if patient_data.address2 else None,
              patient_data.country.lower() if patient_data.country else None,
              patient_data.city.lower(), patient_data.state.lower(), patient_data.pincode,
              patient_data.emergency_contact_name.lower(), patient_data.emergency_contact_phone,
              patient_data.registration_date, patient_data.referral_source.lower(),
              patient_data.referral_subcategory.lower() if patient_data.referral_subcategory else None,
              patient_data.patient_status, patient_data.important_notes.lower() if patient_data.important_notes else None,
              last_visit, patient_data.purpose,
              patient_data.past_medical_record or "None", patient_data.dermatological_history or "None",
              patient_data.medications or "None", patient_data.surgeries or "None", patient_data.hormonal_issues or "None",
              patient_data.allergies or "None", patient_data.lifestyle_assessment or "None",
              patient_data.billing_name, patient_data.billing_gstin,
              patient_data.billing_phone, patient_data.billing_state.lower() if patient_data.billing_state else None,
              patient_data.billing_address.lower() if patient_data.billing_address else None,
              patient_data.payment_method_cash or False, patient_data.payment_method_gst or False,
              patient_data.payment_method_card or False, patient_data.card_name)
    return insert_sql, params

@router.get("/")
async def get_patients(
    page: int = Query(1, ge=1), 
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user)
):
    tenant_id = get_tenant_id()
    
    patients_list = []
    if db_session:
        try:
            patients = db_session.query(PatientModel).filter(PatientModel.tenant_id == tenant_id).all()
            patients_list = [patient_to_dict(p) for p in patients]
        except Exception as e:
            pass
    elif postgres_cursor:
        try:
            postgres_cursor.execute("SELECT * FROM patients_table WHERE tenant_id = %s", (tenant_id,))
            columns = [desc[0] for desc in postgres_cursor.description]
            patients_list = [dict(zip(columns, r)) for r in postgres_cursor.fetchall()]
        except Exception as e:
            pass
    patients_list.sort(key=lambda x: x.get("id", 0))
    total = len(patients_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "patients": patients_list[(page - 1) * limit:page * limit],
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}
    } 

@router.get("/advanced-search")
async def advanced_search_patients(
    q: Optional[str] = Query(None),
    age_min: Optional[int] = Query(None, ge=1, le=110),
    age_max: Optional[int] = Query(None, ge=1, le=110),
    gender: Optional[str] = Query(None),
    patient_status: Optional[str] = Query(None),
    last_visit_days: Optional[int] = Query(None, ge=1),
    sort_by: Optional[str] = Query("newest", regex="^(newest|oldest|alphabetic)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
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
    if patient_status:
        conditions.append("patient_status = %s")
        params.append(patient_status)
    
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
                if patient_status and patient_data.patient_status != patient_status:
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
        "filters": {"search": q, "age_min": age_min, "age_max": age_max, "gender": gender, "patient_status": patient_status, "last_visit_days": last_visit_days},
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
    tenant_id = get_tenant_id()
    calculated_age = calculate_age(patient_data.dob)
    
    if not patient_data.firstname or not patient_data.firstname.strip():
        return create_error_response("Firstname cannot be empty", 400)
    if not patient_data.lastname or not patient_data.lastname.strip():
        return create_error_response("Lastname cannot be empty", 400)
    tenant_id_to_use = patient_data.tenant_id if patient_data.tenant_id else tenant_id
    save_successful = False
    new_patient_id = None
    if db_session:
        try:
            existing = db_session.query(PatientModel).filter(
                and_(PatientModel.phone == patient_data.phone, PatientModel.tenant_id == tenant_id_to_use)
            ).first()
            if existing:
                return create_error_response("Patient with this phone number already exists for this tenant.", 400)
            # Convert date strings to Date objects
            dob_date = string_to_date(patient_data.dob)
            if not dob_date:
                return create_error_response("Invalid date format. Use dd/mm/yyyy", 400)
            reg_date = string_to_date(patient_data.registration_date) if patient_data.registration_date else None
            last_visit = string_to_date(patient_data.last_visit_date) if patient_data.last_visit_date else None
            
            new_patient = PatientModel(
                tenant_id=tenant_id_to_use, firstname=patient_data.firstname.lower(),
                lastname=patient_data.lastname.lower(), dob=dob_date, age=calculated_age,
                gender=patient_data.gender.lower(), phone=patient_data.phone, email=patient_data.email.lower() if patient_data.email else None,
                primary_doctor=patient_data.primary_doctor.lower() if patient_data.primary_doctor else None,
                blood_group=patient_data.blood_group, address1=patient_data.address1.lower(),
                address2=patient_data.address2.lower() if patient_data.address2 else None, country=patient_data.country.lower() if patient_data.country else None,
                city=patient_data.city.lower(), state=patient_data.state.lower(), pincode=patient_data.pincode,
                emergency_contact_name=patient_data.emergency_contact_name.lower(), emergency_contact_phone=patient_data.emergency_contact_phone,
                registration_date=reg_date or (string_to_date(patient_data.registration_date) if patient_data.registration_date else None), referral_source=patient_data.referral_source.lower(),
                referral_subcategory=patient_data.referral_subcategory.lower() if patient_data.referral_subcategory else None, patient_status=patient_data.patient_status,
                important_notes=patient_data.important_notes.lower() if patient_data.important_notes else None, last_visit_date=last_visit,
                purpose=patient_data.purpose, past_medical_record=patient_data.past_medical_record or "None",
                dermatological_history=patient_data.dermatological_history or "None", medications=patient_data.medications or "None",
                surgeries=patient_data.surgeries or "None", hormonal_issues=patient_data.hormonal_issues or "None",
                allergies=patient_data.allergies or "None", lifestyle_assessment=patient_data.lifestyle_assessment or "None",
                billing_name=patient_data.billing_name, billing_gstin=patient_data.billing_gstin,
                billing_phone=patient_data.billing_phone, billing_state=patient_data.billing_state.lower() if patient_data.billing_state else None,
                billing_address=patient_data.billing_address.lower() if patient_data.billing_address else None,
                payment_method_cash=patient_data.payment_method_cash or False, payment_method_gst=patient_data.payment_method_gst or False,
                payment_method_card=patient_data.payment_method_card or False, card_name=patient_data.card_name
            )
            db_session.add(new_patient)
            db_session.commit()
            db_session.refresh(new_patient)
            new_patient_id = new_patient.id
            save_successful = True
        except Exception:
            db_session.rollback()
            save_successful = False
    if not save_successful and postgres_cursor and postgres_conn:
        try:
            ensure_tables_exist()
            postgres_cursor.execute(
                "SELECT id FROM patients_table WHERE phone = %s AND tenant_id = %s", 
                (patient_data.phone, tenant_id_to_use)
            )
            if postgres_cursor.fetchone():
                return create_error_response("Patient with this phone number already exists for this tenant.", 400)
            
            insert_sql, params = _insert_patient_sql(patient_data, calculated_age, tenant_id_to_use)
            postgres_cursor.execute(insert_sql, params)
            result = postgres_cursor.fetchone()
            new_patient_id = result[0] if result else None
            postgres_conn.commit()
            save_successful = True
        except Exception:
            pass
            try:
                ensure_tables_exist()
                postgres_cursor.execute(
                    "SELECT id FROM patients_table WHERE phone = %s AND tenant_id = %s", 
                    (patient_data.phone, tenant_id_to_use)
                )
                if not postgres_cursor.fetchone():
                    insert_sql, params = _insert_patient_sql(patient_data, calculated_age, tenant_id_to_use)
                    postgres_cursor.execute(insert_sql, params)
                    result = postgres_cursor.fetchone()
                    new_patient_id = result[0] if result else None
                    postgres_conn.commit()
                    save_successful = True
            except Exception:
                pass
    if save_successful and new_patient_id:
        return {"message": f"Patient created successfully with ID {new_patient_id}."}
    else:
        raise HTTPException(
            status_code=503, 
            detail="Could not save patient. Database is unavailable. Please check your database connections."
        )

@router.put("/{patient_id}")
async def update_patient(patient_id: int, patient_data: PatientUpdate, current_user: dict = Depends(get_current_active_user)):
    tenant_id = get_tenant_id()
    existing_patient_obj = get_patient_by_id(patient_id, tenant_id)
    if not existing_patient_obj:
        raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found for this tenant.")
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
        update_data["primary_doctor"] = patient_data.primary_doctor.lower() if patient_data.primary_doctor else None
    if patient_data.blood_group is not None:
        update_data["blood_group"] = patient_data.blood_group
    if patient_data.country is not None:
        update_data["country"] = patient_data.country.lower() if patient_data.country else None
    if patient_data.purpose is not None:
        update_data["purpose"] = patient_data.purpose
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
    if patient_data.billing_name is not None:
        update_data["billing_name"] = patient_data.billing_name
    if patient_data.billing_gstin is not None:
        update_data["billing_gstin"] = patient_data.billing_gstin
    if patient_data.billing_phone is not None:
        update_data["billing_phone"] = patient_data.billing_phone
    if patient_data.billing_state is not None:
        update_data["billing_state"] = patient_data.billing_state.lower() if patient_data.billing_state else None
    if patient_data.billing_address is not None:
        update_data["billing_address"] = patient_data.billing_address.lower() if patient_data.billing_address else None
    if patient_data.payment_method_cash is not None:
        update_data["payment_method_cash"] = patient_data.payment_method_cash
    if patient_data.payment_method_gst is not None:
        update_data["payment_method_gst"] = patient_data.payment_method_gst
    if patient_data.payment_method_card is not None:
        update_data["payment_method_card"] = patient_data.payment_method_card
    if patient_data.card_name is not None:
        update_data["card_name"] = patient_data.card_name
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
    if patient_data.patient_status is not None:
        update_data["patient_status"] = patient_data.patient_status
    if patient_data.important_notes is not None:
        update_data["important_notes"] = patient_data.important_notes.lower() if patient_data.important_notes else None
    if patient_data.last_visit_date is not None:
        update_data["last_visit_date"] = patient_data.last_visit_date
    if not update_data:
        return create_error_response("No fields provided for update", 400)
    postgres_updated = False
    if db_session:
        try:
            patient = db_session.query(PatientModel).filter(
                and_(PatientModel.id == patient_id, PatientModel.tenant_id == tenant_id)
            ).first()
            if not patient:
                raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found for this tenant.")
            for key, value in update_data.items():
                setattr(patient, key, value)
            
            db_session.commit()
            db_session.refresh(patient)
            postgres_updated = True
        except HTTPException:
            raise
        except Exception:
            db_session.rollback()
    elif postgres_cursor and postgres_conn:
        try:
            # Validate column names to prevent SQL injection
            allowed_columns = {
                "firstname", "lastname", "age", "gender", "phone", "email", "dob",
                "primary_doctor", "blood_group", "country", "purpose", "past_medical_record",
                "dermatological_history", "medications", "surgeries", "hormonal_issues",
                "allergies", "lifestyle_assessment", "billing_name", "billing_gstin",
                "billing_phone", "billing_state", "billing_address", "payment_method_cash",
                "payment_method_gst", "payment_method_card", "card_name", "address1",
                "address2", "city", "state", "pincode", "emergency_contact_name",
                "emergency_contact_phone", "registration_date", "referral_source",
                "referral_subcategory", "patient_status", "important_notes", "last_visit_date"
            }
            validated_keys = validate_column_names(set(update_data.keys()), allowed_columns)
            set_clauses = []
            values = []
            for key in validated_keys:
                set_clauses.append(f"{key}=%s")
                values.append(update_data[key])
            values.extend([patient_id, tenant_id])
            
            query = f"""
                UPDATE patients_table
                SET {', '.join(set_clauses)}
                WHERE id=%s AND tenant_id=%s
            """
            postgres_cursor.execute(query, values)
            postgres_conn.commit()
            if postgres_cursor.rowcount == 1:
                postgres_updated = True
        except Exception:
            pass
    if postgres_updated:
        return {"message": f"Patient with ID {patient_id} updated successfully."}
    else:
        raise HTTPException(
            status_code=503, 
            detail="Could not update patient. Database is unavailable. Please check your database connections."
        )

@router.delete("/{patient_id}")
async def delete_patient(patient_id: int, current_user: dict = Depends(get_current_active_user)):
    tenant_id = get_tenant_id()
    postgres_deleted = False
    if db_session:
        try:
            patient = db_session.query(PatientModel).filter(
                and_(PatientModel.id == patient_id, PatientModel.tenant_id == tenant_id)
            ).first()
            if patient:
                db_session.delete(patient)
                db_session.commit()
                postgres_deleted = True
        except Exception:
            db_session.rollback()
    elif postgres_cursor and postgres_conn:
        try:
            postgres_cursor.execute(
                "DELETE FROM patients_table WHERE id = %s AND tenant_id = %s", 
                (patient_id, tenant_id)
            )
            postgres_conn.commit()
            if postgres_cursor.rowcount == 1:
                postgres_deleted = True
        except Exception:
            pass
    if postgres_deleted:
        try:
            delete_patient_folder(patient_id, tenant_id)
            pass
        except Exception:
            pass
        return {"message": f"Patient with ID {patient_id} deleted successfully from PostgreSQL."}
    else:
        raise HTTPException(
            status_code=404, 
            detail="Patient not found for this tenant to delete."
        )

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
        if db_session:
            try:
                doc = DocumentsModel(
                    patient_id=patient_id, tenant_id=tenant_id, filename=safe_filename,
                    description=description, file_type=file_type, file_size=file_size
                )
                db_session.add(doc)
                db_session.commit()
                db_session.refresh(doc)
                document_id = doc.id
            except Exception as e:
                db_session.rollback()
                pass
        elif postgres_cursor and postgres_conn:
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
async def list_patient_files(patient_id: int, current_user: dict = Depends(get_current_active_user)):  # list all files for a patient (photo, documents from DB, prescriptions)
    tenant_id = get_tenant_id()
    
    if not check_patient_exists(patient_id, tenant_id):
        raise_not_found_error("Patient", patient_id)
    
    try:
        patient_folder = get_patient_folder(patient_id, tenant_id)
        files_list = {"photo": [], "documents": [], "prescriptions": []}
        
        # List photo files (from filesystem)
        photo_folder = patient_folder / "photo"
        if photo_folder.exists():
            files_list["photo"] = [f.name for f in photo_folder.iterdir() if f.is_file()]
        documents_list = []
        if db_session:
            try:
                docs = db_session.query(DocumentsModel).filter(
                    and_(DocumentsModel.patient_id == patient_id, DocumentsModel.tenant_id == tenant_id)
                ).order_by(DocumentsModel.uploaded_at.desc()).all()
                documents_list = [{
                    "id": doc.id, "filename": doc.filename, "description": doc.description,
                    "file_type": doc.file_type, "file_size": doc.file_size,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                } for doc in docs]
            except Exception as e:
                pass
        elif postgres_cursor:
            try:
                postgres_cursor.execute("""
                    SELECT id, filename, description, file_type, file_size, uploaded_at
                    FROM patient_documents
                    WHERE patient_id = %s AND tenant_id = %s
                    ORDER BY uploaded_at DESC
                """, (patient_id, tenant_id))
                columns = ["id", "filename", "description", "file_type", "file_size", "uploaded_at"]
                for record in postgres_cursor.fetchall():
                    doc_dict = dict(zip(columns, record))
                    doc_dict["uploaded_at"] = doc_dict["uploaded_at"].isoformat() if doc_dict["uploaded_at"] else None
                    documents_list.append(doc_dict)
            except Exception as e:
                pass
        files_list["documents"] = documents_list
        presc_folder = patient_folder / "prescriptions"
        if presc_folder.exists():
            files_list["prescriptions"] = [f.name for f in presc_folder.iterdir() if f.is_file()]
        
        return {"patient_id": patient_id, "files": files_list}
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

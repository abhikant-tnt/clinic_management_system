from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import Optional
from app.modules.patients.schemas import PatientCreate, PatientUpdate, calculate_age
from app.common.schemas import ErrorResponse
from app.core.database import (
    local_postgres_conn, 
    local_postgres_cursor, 
    sync_local_to_main,
    db_session,
    ensure_tables_exist
)
from app.core.models import PatientModel, DocumentsModel
from sqlalchemy import and_
from app.core.config import settings
from app.core.storage import (
    create_patient_folders, 
    delete_patient_folder,
    get_patient_photo_path,
    get_patient_document_path,
    get_patient_folder
)

router = APIRouter()

def get_tenant_id() -> str:  # get tenant ID from settings
    return settings.TENANT_ID

def patient_to_dict(patient_data) -> dict:  # convert patient object to dictionary
    if isinstance(patient_data, dict):
        return patient_data
    return {
        "id": patient_data.id, "tenant_id": patient_data.tenant_id, "title": patient_data.title,
        "firstname": patient_data.firstname, "lastname": patient_data.lastname, "dob": patient_data.dob,
        "age": patient_data.age, "gender": patient_data.gender, "phone": patient_data.phone,
        "email": patient_data.email, "primary_doctor": patient_data.primary_doctor, "address1": patient_data.address1,
        "address2": patient_data.address2, "country": patient_data.country, "city": patient_data.city,
        "state": patient_data.state, "pincode": patient_data.pincode, "emergency_contact_name": patient_data.emergency_contact_name,
        "emergency_contact_phone": patient_data.emergency_contact_phone, "referral_source": patient_data.referral_source, "referral_subcategory": patient_data.referral_subcategory,
        "patient_status": patient_data.patient_status, "important_notes": patient_data.important_notes, "last_visit_date": patient_data.last_visit_date,
        "registration_date": patient_data.registration_date, "purpose": patient_data.purpose, "past_medical_record": patient_data.past_medical_record,
        "dermatological_history": patient_data.dermatological_history, "medications": patient_data.medications, "surgeries": patient_data.surgeries,
        "hormonal_issues": patient_data.hormonal_issues, "synced_to_main": patient_data.synced_to_main,
        "last_synced_at": patient_data.last_synced_at.isoformat() if patient_data.last_synced_at else None
    }

def check_patient_exists(patient_id: int, tenant_id: str) -> bool:  # check if patient exists
    if db_session:
        try:
            return db_session.query(PatientModel).filter(
                and_(PatientModel.id == patient_id, PatientModel.tenant_id == tenant_id)
            ).first() is not None
        except Exception:
            return False
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT id FROM patients_table WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            return local_postgres_cursor.fetchone() is not None
        except Exception:
            return False
    return False

def get_patient_by_id(patient_id: int, tenant_id: str):  # get patient by ID, returns patient object or dict
    if db_session:
        try:
            return db_session.query(PatientModel).filter(
                and_(PatientModel.id == patient_id, PatientModel.tenant_id == tenant_id)
            ).first()
        except Exception:
            return None
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT * FROM patients_table WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            record = local_postgres_cursor.fetchone()
            if record:
                columns = [desc[0] for desc in local_postgres_cursor.description]
                return dict(zip(columns, record))
        except Exception:
            return None
    return None

def error_response(message: str, status_code: int = 400) -> JSONResponse:  # create standardized error response
    return JSONResponse(status_code=status_code, content=ErrorResponse(message=message).model_dump())

def _insert_patient_sql(patient_data: PatientCreate, calculated_age: int, tenant_id_to_use: str) -> tuple:
    insert_sql = """INSERT INTO patients_table (tenant_id, title, firstname, lastname, dob, age, gender, phone, email, primary_doctor,
                    address1, address2, country, city, state, pincode, emergency_contact_name, emergency_contact_phone,
                    registration_date, referral_source, referral_subcategory, patient_status, 
                    important_notes, last_visit_date, purpose, past_medical_record, dermatological_history,
                    medications, surgeries, hormonal_issues, synced_to_main)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
                    RETURNING id"""
    params = (tenant_id_to_use, patient_data.title, patient_data.firstname.lower(), patient_data.lastname.lower(),
              patient_data.dob, calculated_age, patient_data.gender.lower(), patient_data.phone,
              patient_data.email.lower() if patient_data.email else None,
              patient_data.primary_doctor.lower() if patient_data.primary_doctor else None,
              patient_data.address1.lower(), patient_data.address2.lower() if patient_data.address2 else None,
              patient_data.country.lower() if patient_data.country else None,
              patient_data.city.lower(), patient_data.state.lower(), patient_data.pincode,
              patient_data.emergency_contact_name.lower(), patient_data.emergency_contact_phone,
              patient_data.registration_date, patient_data.referral_source.lower(),
              patient_data.referral_subcategory.lower() if patient_data.referral_subcategory else None,
              patient_data.patient_status, patient_data.important_notes.lower() if patient_data.important_notes else None,
              patient_data.last_visit_date, patient_data.purpose,
              patient_data.past_medical_record or "None", patient_data.dermatological_history or "None",
              patient_data.medications or "None", patient_data.surgeries or "None", patient_data.hormonal_issues or "None")
    return insert_sql, params

@router.get("/")
def get_patients(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):  # get all patients with pagination
    tenant_id = get_tenant_id()
    sync_local_to_main()
    
    patients_list = []
    if db_session:
        try:
            patients = db_session.query(PatientModel).filter(PatientModel.tenant_id == tenant_id).all()
            patients_list = [patient_to_dict(p) for p in patients]
        except Exception as e:
            print(f"Error fetching patients (SQLAlchemy): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT * FROM patients_table WHERE tenant_id = %s", (tenant_id,))
            columns = [desc[0] for desc in local_postgres_cursor.description]
            patients_list = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching patients: {e}")
    patients_list.sort(key=lambda x: x.get("id", 0))
    total = len(patients_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "patients": patients_list[(page - 1) * limit:page * limit],
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}
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
):  # advanced search with filters, sorting, and pagination
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
    
    # Fetch patients
    patients_list = []
    if local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT * FROM patients_table WHERE tenant_id = %s", (tenant_id,))
            columns = [desc[0] for desc in local_postgres_cursor.description]
            all_patients = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
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
            print(f"Error searching: {e}")
    if local_postgres_cursor:
        try:
            query = f"SELECT * FROM patients_table WHERE {' AND '.join(conditions)}"
            local_postgres_cursor.execute(query, params)
            columns = [desc[0] for desc in local_postgres_cursor.description]
            for record in local_postgres_cursor.fetchall():
                patients_list.append(dict(zip(columns, record)))
        except Exception as e:
            print(f"Error searching: {e}")
    if last_visit_days:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=last_visit_days)
        filtered = []
        for patient_data in patients_list:
            patient_id = patient_data.get("id")
            try:
                if local_postgres_cursor:
                    local_postgres_cursor.execute(
                        "SELECT MAX(visit_date) FROM visits WHERE patient_id = %s AND tenant_id = %s",
                        (patient_id, tenant_id)
                    )
                    result = local_postgres_cursor.fetchone()
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
def get_patient(patient_id: int):  # get a single patient by ID for the current tenant
    tenant_id = get_tenant_id()
    patient_data = get_patient_by_id(patient_id, tenant_id)
    if patient_data:
        return {"database": "Local PostgreSQL", "patient": patient_to_dict(patient_data)}
    raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found.")

@router.post("/")
def create_patient(patient_data: PatientCreate):  # create a new patient for the current tenant - age is calculated from dob
    tenant_id = get_tenant_id()
    calculated_age = calculate_age(patient_data.dob)
    
    # Validation
    if not patient_data.firstname or not patient_data.firstname.strip():
        return error_response("Firstname cannot be empty", 400)
    if not patient_data.lastname or not patient_data.lastname.strip():
        return error_response("Lastname cannot be empty", 400)
    tenant_id_to_use = patient_data.tenant_id if patient_data.tenant_id else tenant_id
    save_successful = False
    new_patient_id = None
    if db_session:
        try:
            existing = db_session.query(PatientModel).filter(
                and_(PatientModel.phone == patient_data.phone, PatientModel.tenant_id == tenant_id_to_use)
            ).first()
            if existing:
                return error_response("Patient with this phone number already exists for this tenant.", 400)
            new_patient = PatientModel(
                tenant_id=tenant_id_to_use, title=patient_data.title, firstname=patient_data.firstname.lower(),
                lastname=patient_data.lastname.lower(), dob=patient_data.dob, age=calculated_age,
                gender=patient_data.gender.lower(), phone=patient_data.phone, email=patient_data.email.lower() if patient_data.email else None,
                primary_doctor=patient_data.primary_doctor.lower() if patient_data.primary_doctor else None, address1=patient_data.address1.lower(),
                address2=patient_data.address2.lower() if patient_data.address2 else None, country=patient_data.country.lower() if patient_data.country else None,
                city=patient_data.city.lower(), state=patient_data.state.lower(), pincode=patient_data.pincode,
                emergency_contact_name=patient_data.emergency_contact_name.lower(), emergency_contact_phone=patient_data.emergency_contact_phone,
                registration_date=patient_data.registration_date, referral_source=patient_data.referral_source.lower(),
                referral_subcategory=patient_data.referral_subcategory.lower() if patient_data.referral_subcategory else None, patient_status=patient_data.patient_status,
                important_notes=patient_data.important_notes.lower() if patient_data.important_notes else None, last_visit_date=patient_data.last_visit_date,
                purpose=patient_data.purpose, past_medical_record=patient_data.past_medical_record or "None",
                dermatological_history=patient_data.dermatological_history or "None", medications=patient_data.medications or "None",
                surgeries=patient_data.surgeries or "None", hormonal_issues=patient_data.hormonal_issues or "None", synced_to_main=False
            )
            db_session.add(new_patient)
            db_session.commit()
            db_session.refresh(new_patient)
            new_patient_id = new_patient.id
            print(f"Patient successfully saved using SQLAlchemy with ID {new_patient_id}.")
            save_successful = True
        except Exception as e:
            db_session.rollback()
            print(f"SQLAlchemy save FAILED. Error: {str(e)}.")
            save_successful = False
    if not save_successful and local_postgres_cursor and local_postgres_conn:
        try:
            ensure_tables_exist()
            local_postgres_cursor.execute(
                "SELECT id FROM patients_table WHERE phone = %s AND tenant_id = %s", 
                (patient_data.phone, tenant_id_to_use)
            )
            if local_postgres_cursor.fetchone():
                return error_response("Patient with this phone number already exists for this tenant.", 400)
            
            insert_sql, params = _insert_patient_sql(patient_data, calculated_age, tenant_id_to_use)
            local_postgres_cursor.execute(insert_sql, params)
            result = local_postgres_cursor.fetchone()
            new_patient_id = result[0] if result else None
            local_postgres_conn.commit()
            print(f"Patient successfully saved to Local PostgreSQL with ID {new_patient_id}.")
            save_successful = True
        except Exception as e:
            print(f"Local PostgreSQL save FAILED. Error: {str(e)}.")
            try:
                ensure_tables_exist()
                local_postgres_cursor.execute(
                    "SELECT id FROM patients_table WHERE phone = %s AND tenant_id = %s", 
                    (patient_data.phone, tenant_id_to_use)
                )
                if not local_postgres_cursor.fetchone():
                    insert_sql, params = _insert_patient_sql(patient_data, calculated_age, tenant_id_to_use)
                    local_postgres_cursor.execute(insert_sql, params)
                    result = local_postgres_cursor.fetchone()
                    new_patient_id = result[0] if result else None
                    local_postgres_conn.commit()
                    print(f"Patient successfully saved to Local PostgreSQL with ID {new_patient_id} (after table recreation).")
                    save_successful = True
            except Exception as retry_e:
                print(f"Retry after table recreation also FAILED. Error: {str(retry_e)}.")
    if save_successful and new_patient_id:
        sync_local_to_main()
        return {"message": f"Patient created successfully with ID {new_patient_id}."}
    else:
        raise HTTPException(
            status_code=503, 
            detail="Could not save patient. Database is unavailable. Please check your database connections."
        )

@router.put("/{patient_id}")
def update_patient(patient_id: int, patient_data: PatientUpdate):  # update an existing patient for the current tenant - age is recalculated if dob is provided
    tenant_id = get_tenant_id()
    existing_patient_obj = get_patient_by_id(patient_id, tenant_id)
    if not existing_patient_obj:
        raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found for this tenant.")
    calculated_age = calculate_age(patient_data.dob) if patient_data.dob else None
    update_data = {}
    if patient_data.title is not None:
        update_data["title"] = patient_data.title
    if patient_data.firstname is not None:
        if not patient_data.firstname.strip():
            return error_response("Firstname cannot be empty", 400)
        update_data["firstname"] = patient_data.firstname.lower()
    if patient_data.lastname is not None:
        if not patient_data.lastname.strip():
            return error_response("Lastname cannot be empty", 400)
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
    update_data["synced_to_main"] = False
    if not update_data:
        return error_response("No fields provided for update", 400)
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
            print(f"SQLAlchemy patient ID {patient_id} updated.")
            postgres_updated = True
        except HTTPException:
            raise
        except Exception as e:
            db_session.rollback()
            print(f"SQLAlchemy update FAILED. Error: {str(e)}.")
    elif local_postgres_cursor and local_postgres_conn:
        try:
            set_clauses = []
            values = []
            for key, value in update_data.items():
                if key != "synced_to_main":
                    set_clauses.append(f"{key}=%s")
                    values.append(value)
            set_clauses.append("synced_to_main=FALSE")
            values.extend([patient_id, tenant_id])
            
            query = f"""
                UPDATE patients_table
                SET {', '.join(set_clauses)}
                WHERE id=%s AND tenant_id=%s
            """
            local_postgres_cursor.execute(query, values)
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount == 1:
                print(f"Local PostgreSQL patient ID {patient_id} updated.")
                postgres_updated = True
        except Exception as e:
            print(f"Local PostgreSQL Update FAILED. Error: {str(e)}.")
    if postgres_updated:
        sync_local_to_main()
        return {"message": f"Patient with ID {patient_id} updated successfully."}
    else:
        raise HTTPException(
            status_code=503, 
            detail="Could not update patient. Database is unavailable. Please check your database connections."
        )

@router.delete("/{patient_id}")
def delete_patient(patient_id: int):  # delete a patient by ID for the current tenant
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
                print(f"Patient with ID {patient_id} successfully deleted using SQLAlchemy.")
                postgres_deleted = True
            else:
                print(f"Patient with ID {patient_id} not found for deletion.")
        except Exception as e:
            db_session.rollback()
            print(f"Error deleting patient: {e}.")
    elif local_postgres_cursor and local_postgres_conn:
        try:
            local_postgres_cursor.execute(
                "DELETE FROM patients_table WHERE id = %s AND tenant_id = %s", 
                (patient_id, tenant_id)
            )
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount == 1:
                print(f"Patient with ID {patient_id} successfully deleted from Local PostgreSQL.")
                postgres_deleted = True
            else:
                print(f"Patient with ID {patient_id} not found in Local PostgreSQL for deletion.")
        except Exception as e:
            print(f"Error deleting patient from Local PostgreSQL: {e}.")
    if postgres_deleted:
        try:
            delete_patient_folder(patient_id, tenant_id)
            print(f"Patient folder deleted for ID {patient_id}")
        except Exception as e:
            print(f"Warning: Could not delete patient folder for ID {patient_id}: {e}")
        return {"message": f"Patient with ID {patient_id} deleted successfully from Local PostgreSQL."}
    else:
        raise HTTPException(
            status_code=404, 
            detail="Patient not found for this tenant to delete."
        )

@router.post("/{patient_id}/upload/photo")
async def upload_patient_photo(patient_id: int, file: UploadFile = File(...)):  # upload a patient photo. accepts: JPG, PNG, JPEG
    tenant_id = get_tenant_id()
    allowed_types = ["image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, or JPEG images are allowed")
    
    # Validate patient exists
    try:
        if local_postgres_cursor:
            local_postgres_cursor.execute("SELECT id FROM patients_table WHERE id = %s AND tenant_id = %s", (patient_id, tenant_id))
            if not local_postgres_cursor.fetchone():
                raise HTTPException(status_code=404, detail="Patient not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking patient: {str(e)}")
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
        raise HTTPException(status_code=500, detail=f"Error uploading photo: {str(e)}")

@router.post("/{patient_id}/upload/document")
async def upload_patient_document(patient_id: int, file: UploadFile = File(...), description: str = Form(None)):  # upload a patient document (PDF, images, etc.) and save metadata to database
    tenant_id = get_tenant_id()
    
    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        return JSONResponse(status_code=400,
            content=ErrorResponse(message="Only PDF, JPG, PNG, or JPEG files are allowed").model_dump()
        )
    
    if not check_patient_exists(patient_id, tenant_id):
        return error_response("Patient not found", 404)
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
                    description=description, file_type=file_type, file_size=file_size, synced_to_main=False
                )
                db_session.add(doc)
                db_session.commit()
                db_session.refresh(doc)
                document_id = doc.id
            except Exception as e:
                db_session.rollback()
                print(f"Error saving document metadata (SQLAlchemy): {e}")
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
            except Exception as e:
                print(f"Error saving document metadata: {e}")
        return {
            "message": "Document uploaded successfully", "document_id": document_id, "patient_id": patient_id,
            "filename": safe_filename, "description": description, "file_type": file_type, "file_size": file_size
        }
    except Exception as e:
        return error_response(f"Error uploading document: {str(e)}", 500)

@router.get("/{patient_id}/files")
def list_patient_files(patient_id: int):  # list all files for a patient (photo, documents from DB, prescriptions)
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
                print(f"Error fetching documents (SQLAlchemy): {e}")
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
            except Exception as e:
                print(f"Error fetching documents: {e}")
        files_list["documents"] = documents_list
        presc_folder = patient_folder / "prescriptions"
        if presc_folder.exists():
            files_list["prescriptions"] = [f.name for f in presc_folder.iterdir() if f.is_file()]
        
        return {"patient_id": patient_id, "files": files_list}
    except Exception as e:
        return error_response(f"Error listing files: {str(e)}", 500)

@router.get("/{patient_id}/download/{file_type}/{filename}")
def download_patient_file(patient_id: int, file_type: str, filename: str):  # download a patient file. file_type: 'photo', 'documents', or 'prescriptions'
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
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

@router.get("/{patient_id}/billing/summary")
def get_patient_billing_summary(patient_id: int):  # get billing summary for a patient (calculated from appointments only - billing module will handle amounts)
    tenant_id = get_tenant_id()
    if not check_patient_exists(patient_id, tenant_id):
        return error_response(f"Patient with ID {patient_id} not found", 404)
    total_billed_from_appointments = 0.0
    appointments_with_charges = 0
    if local_postgres_cursor:
        try:
            local_postgres_cursor.execute(
                "SELECT total_charge FROM appointments WHERE patient_id = %s AND tenant_id = %s AND status = 'Completed'",
                (patient_id, tenant_id)
            )
            for row in local_postgres_cursor.fetchall():
                if row[0]:
                    total_billed_from_appointments += float(row[0])
                    appointments_with_charges += 1
        except Exception as e:
            print(f"Error fetching appointments: {e}")
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

from fastapi import APIRouter, HTTPException, Query
from app.modules.patients.schemas import Patient
from app.core.database import (
    local_postgres_conn, 
    local_postgres_cursor, 
    prisma_client,
    sync_local_to_main
)
from app.core.config import settings
from decimal import Decimal
import psycopg2
from psycopg2 import Error as PostgresError

router = APIRouter()

def get_tenant_id() -> str:
    """Get tenant ID from settings"""
    return settings.TENANT_ID

@router.get("/")
def get_patients(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    """
    Get all patients with pagination for the current tenant.
    - page: Page number (starts from 1)
    - limit: Number of records per page (max 100, default 10)
    """
    tenant_id = get_tenant_id()
    
    # Sync Local → Main Server
    sync_local_to_main()
    
    # Fetching Local PostgreSQL data using Prisma (or fallback to raw SQL)
    postgres_patients = []
    if prisma_client:
        try:
            patients = prisma_client.patient.find_many(
                where={"tenant_id": tenant_id}
            )
            for patient in patients:
                patient_dict = {
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
                postgres_patients.append(patient_dict)
        except (AttributeError, RuntimeError, ValueError) as e:
            print(f"Error fetching data from PostgreSQL (Prisma): {e}. Skipping PostgreSQL.")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, tenant_id, name, age, gender, phone, email, date_of_birth, address, 
                    registration_date, referral_source, referral_subcategory, patient_status, 
                    important_notes, billed_amount, outstanding_amount 
                FROM patients 
                WHERE tenant_id = %s
            """, (tenant_id,))
            postgres_records = local_postgres_cursor.fetchall()
            columns = ["id", "tenant_id", "name", "age", "gender", "phone", "email", "date_of_birth", 
                    "address", "registration_date", "referral_source", "referral_subcategory", 
                    "patient_status", "important_notes", "billed_amount", "outstanding_amount"]
            for record in postgres_records:
                patient_dict = dict(zip(columns, record))
                postgres_patients.append(patient_dict)
        except (PostgresError, psycopg2.OperationalError) as e:
            print(f"Error fetching data from PostgreSQL: {e}. Skipping PostgreSQL.")
    
    # Convert to list and sort by ID for consistent pagination
    all_patients_list = postgres_patients
    all_patients_list.sort(key=lambda x: x.get("id", 0))
    
    # Calculate pagination
    total = len(all_patients_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1  # Ceiling division
    skip = (page - 1) * limit
    
    # Get paginated results
    paginated_patients = all_patients_list[skip:skip + limit]
    
    return {
        "patients": paginated_patients,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    } 

@router.get("/search")
def search_patients(q: str, page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    """
    Search patients by name, id, phone, or email with pagination for the current tenant.
    Supports partial matches for text fields.
    - q: Search query (required)
    - page: Page number (starts from 1, default 1)
    - limit: Number of records per page (max 100, default 10)
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    
    tenant_id = get_tenant_id()
    search_term = q.strip()
    results = []
    found_ids = set()
    
    # Check if search term is numeric (for ID search)
    is_numeric = search_term.isdigit()
    search_id = int(search_term) if is_numeric else None
    
    # PostgreSQL Search (using Prisma or fallback to raw SQL)
    if prisma_client:
        try:
            if is_numeric:
                # Search by ID (exact match)
                patient = prisma_client.patient.find_first(
                    where={"id": search_id, "tenant_id": tenant_id}
                )
                if patient:
                    patient_dict = {
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
                        "billed_amount": float(patient.billed_amount) if patient.billed_amount else 0.0,
                        "outstanding_amount": float(patient.outstanding_amount) if patient.outstanding_amount else 0.0
                    }
                    results.append(patient_dict)
                    found_ids.add(patient.id)
            else:
                # Search by name, phone, or email (partial match)
                patients = prisma_client.patient.find_many(
                    where={"tenant_id": tenant_id}
                )
                # Filter in Python for case-insensitive partial match
                search_term_lower = search_term.lower()
                patients = [
                    p for p in patients
                    if (p.name and search_term_lower in p.name.lower()) or
                    (p.phone and search_term_lower in p.phone.lower()) or
                    (p.email and search_term_lower in (p.email.lower() if p.email else ""))
                ]
                for patient in patients:
                    patient_dict = {
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
                        "billed_amount": float(patient.billed_amount) if patient.billed_amount else 0.0,
                        "outstanding_amount": float(patient.outstanding_amount) if patient.outstanding_amount else 0.0
                    }
                    if patient.id not in found_ids:
                        results.append(patient_dict)
                        found_ids.add(patient.id)
        except (AttributeError, RuntimeError, ValueError) as e:
            print(f"Error searching PostgreSQL (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            if is_numeric:
                # Search by ID (exact match)
                local_postgres_cursor.execute("""
                    SELECT id, tenant_id, name, age, gender, phone, email, date_of_birth, address, 
                        registration_date, referral_source, referral_subcategory, patient_status, 
                        important_notes, billed_amount, outstanding_amount 
                    FROM patients 
                    WHERE id = %s AND tenant_id = %s
                """, (search_id, tenant_id))
            else:
                # Search by name, phone, or email (partial match)
                local_postgres_cursor.execute("""
                    SELECT id, tenant_id, name, age, gender, phone, email, date_of_birth, address, 
                        registration_date, referral_source, referral_subcategory, patient_status, 
                        important_notes, billed_amount, outstanding_amount 
                    FROM patients 
                    WHERE tenant_id = %s AND (name LIKE %s OR phone LIKE %s OR email LIKE %s)
                """, (tenant_id, f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
            
            postgres_records = local_postgres_cursor.fetchall()
            columns = ["id", "tenant_id", "name", "age", "gender", "phone", "email", "date_of_birth", 
                    "address", "registration_date", "referral_source", "referral_subcategory", 
                    "patient_status", "important_notes", "billed_amount", "outstanding_amount"]
            
            for record in postgres_records:
                patient_dict = dict(zip(columns, record))
                patient_id = patient_dict.get("id")
                if patient_id and patient_id not in found_ids:
                    results.append(patient_dict)
                    found_ids.add(patient_id)
        except (PostgresError, psycopg2.OperationalError) as e:
            print(f"Error searching PostgreSQL: {e}")
    
    if not results:
        raise HTTPException(status_code=404, detail=f"No patients found matching '{search_term}'")
    
    # Sort results by ID for consistent pagination
    results.sort(key=lambda x: x.get("id", 0))
    
    # Calculate pagination
    total = len(results)
    total_pages = (total + limit - 1) // limit if total > 0 else 1  # Ceiling division
    skip = (page - 1) * limit
    
    # Get paginated results
    paginated_results = results[skip:skip + limit]
    
    return {
        "query": search_term,
        "patients": paginated_results,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }

@router.get("/{patient_id}")
def get_patient(patient_id: int):
    """Get a single patient by ID for the current tenant"""
    tenant_id = get_tenant_id()
    
    patient_dict = None
    
    if prisma_client:
        try:
            patient = prisma_client.patient.find_first(
                where={"id": patient_id, "tenant_id": tenant_id}
            )
            if patient:
                patient_dict = {
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
        except (AttributeError, RuntimeError, ValueError) as e:
            print(f"Error fetching patient from PostgreSQL (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, tenant_id, name, age, gender, phone, email, date_of_birth, address, 
                    registration_date, referral_source, referral_subcategory, patient_status, 
                    important_notes, billed_amount, outstanding_amount 
                FROM patients 
                WHERE id = %s AND tenant_id = %s
            """, (patient_id, tenant_id))
            postgres_patient = local_postgres_cursor.fetchone()
            if postgres_patient:
                columns = ["id", "tenant_id", "name", "age", "gender", "phone", "email", "date_of_birth", 
                        "address", "registration_date", "referral_source", "referral_subcategory", 
                        "patient_status", "important_notes", "billed_amount", "outstanding_amount"]
                patient_dict = dict(zip(columns, postgres_patient))
        except (PostgresError, psycopg2.OperationalError) as e:
            print(f"Error fetching patient from PostgreSQL: {e}")
    
    if patient_dict:
        return {"database": "Local PostgreSQL", "patient": patient_dict}
    
    raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found.")

@router.post("/")
def create_patient(patient: Patient):
    """Create a new patient for the current tenant"""
    tenant_id = get_tenant_id()
    
    # Initial Validation
    if not patient.name or not patient.phone:
        raise HTTPException(status_code=400, detail="Name and phone cannot be empty")
    if patient.age <= 0:
        raise HTTPException(status_code=400, detail="Age must be greater than 0")
    if patient.billed_amount < 0 or patient.outstanding_amount < 0:
        raise HTTPException(status_code=400, detail="Amounts cannot be negative")
    # Gender validation is automatically handled by Pydantic Literal type

    # Check for existing phone number in local database
    postgres_existing = None
    if prisma_client:
        try:
            postgres_existing = prisma_client.patient.find_first(
                where={"phone": patient.phone, "tenant_id": tenant_id}
            )
        except (AttributeError, RuntimeError, ValueError) as e:
            print(f"Error checking phone in PostgreSQL (Prisma): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute(
                "SELECT id FROM patients WHERE phone = %s AND tenant_id = %s", 
                (patient.phone, tenant_id)
            )
            postgres_existing = local_postgres_cursor.fetchone()
        except (PostgresError, psycopg2.OperationalError) as e:
            print(f"Error checking phone in PostgreSQL: {e}")
    
    if postgres_existing:
        raise HTTPException(
            status_code=400, 
            detail="Patient with this phone number already exists for this tenant."
        )
    
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
                    "billed_amount": Decimal(str(patient.billed_amount)),
                    "outstanding_amount": Decimal(str(patient.outstanding_amount)),
                    "synced_to_main": False
                }
            )
            new_patient_id = new_patient.id
            print(f"Patient successfully saved to Local PostgreSQL with ID {new_patient_id} (Prisma).")
            save_successful = True
        except (AttributeError, RuntimeError, ValueError, psycopg2.IntegrityError) as e:
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
                patient.important_notes, patient.billed_amount, patient.outstanding_amount
            ))
            result = local_postgres_cursor.fetchone()
            new_patient_id = result[0] if result else None
            local_postgres_conn.commit()
            print(f"Patient successfully saved to Local PostgreSQL with ID {new_patient_id}.")
            save_successful = True
        except (PostgresError, psycopg2.IntegrityError, psycopg2.OperationalError) as e:
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
    if not patient.name or not patient.phone:
        raise HTTPException(status_code=400, detail="Name and phone cannot be empty")
    
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
                    "billed_amount": Decimal(str(patient.billed_amount)),
                    "outstanding_amount": Decimal(str(patient.outstanding_amount)),
                    "synced_to_main": False  # Mark as unsynced after update
                }
            )
            print(f"Local PostgreSQL patient ID {patient_id} updated (Prisma).")
            postgres_updated = True
        except (AttributeError, RuntimeError, ValueError, psycopg2.IntegrityError) as e:
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
                patient.patient_status, patient.important_notes, patient.billed_amount, patient.outstanding_amount, 
                patient_id, tenant_id
            ))
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount == 1:
                print(f"Local PostgreSQL patient ID {patient_id} updated.")
                postgres_updated = True
        except (PostgresError, psycopg2.IntegrityError, psycopg2.OperationalError) as e:
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
        except (AttributeError, RuntimeError, ValueError) as e:
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
        except (PostgresError, psycopg2.OperationalError) as e:
            print(f"Error deleting patient from Local PostgreSQL: {e}.")
    
    # Note: We don't delete from main server immediately - it will be handled by sync
    # or you can implement a separate endpoint for main server deletion if needed
    
    if postgres_deleted:
        return {"message": f"Patient with ID {patient_id} deleted successfully from Local PostgreSQL."}
    else:
        raise HTTPException(
            status_code=404, 
            detail="Patient not found for this tenant to delete."
        )

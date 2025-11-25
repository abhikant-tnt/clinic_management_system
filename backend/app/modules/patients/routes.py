from fastapi import APIRouter, HTTPException, Query
from app.modules.patients.schemas import Patient
from app.core.database import collection, mongo_connected, postgres_conn, postgres_cursor, prisma_client
from decimal import Decimal

router = APIRouter()

def clean_mongo_document(doc):
    """Remove _id field from MongoDB document (safety net for projection)"""
    if doc and isinstance(doc, dict):
        doc.pop("_id", None)  # Remove _id if it exists (shouldn't with projection, but safety net)
    return doc

@router.get("/")
def get_patients(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    """
    Get all patients with pagination.
    - page: Page number (starts from 1)
    - limit: Number of records per page (max 100, default 10)
    """
    # Sync PostgreSQL → MongoDB (primary sync direction)
    # PostgreSQL is source of truth, MongoDB is backup
    if mongo_connected and collection is not None and (prisma_client or (postgres_cursor and postgres_conn)):
        from app.core.database import sync_postgres_to_mongo
        sync_postgres_to_mongo()
    
    # Fetching MongoDB Data
    mongo_patients = []
    mongo_ids = set()  # Track which IDs exist in MongoDB
    if mongo_connected and collection is not None:
        try:
            patients = list(collection.find({}, projection={"_id": 0})) # projection means explicitly exclude the MongoDB internal _id field
            # Clean all documents to ensure no ObjectId remains
            mongo_patients = [clean_mongo_document(p) for p in patients]
            mongo_ids = {p.get("id") for p in mongo_patients if p.get("id") is not None}  # Get all MongoDB IDs
        except Exception as e:
            print(f"Error fetching data from MongoDB: {e}. Skipping MongoDB.")

    # Fetching PostgreSQL data using Prisma (or fallback to raw SQL)
    postgres_patients = []
    if prisma_client:
        try:
            patients = prisma_client.patient.find_many()
            for patient in patients:
                patient_dict = {
                    "id": patient.id,
                    "name": patient.name,
                    "age": patient.age,
                    "phone": patient.phone,
                    "email": patient.email,
                    "date_of_birth": patient.date_of_birth,
                    "address": patient.address,
                    "registration_date": patient.registration_date,
                    "billed_amount": float(patient.billed_amount) if patient.billed_amount else 0.0,
                    "outstanding_amount": float(patient.outstanding_amount) if patient.outstanding_amount else 0.0
                }
                postgres_patients.append(patient_dict)
        except Exception as e:
            print(f"Error fetching data from PostgreSQL (Prisma): {e}. Skipping PostgreSQL.")
    elif postgres_cursor:
        try:
            postgres_cursor.execute("SELECT id,name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount FROM patients")
            postgres_records = postgres_cursor.fetchall()
            columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
            for record in postgres_records:
                patient_dict = dict(zip(columns, record))
                postgres_patients.append(patient_dict)
        except Exception as e:
            print(f"Error fetching data from PostgreSQL: {e}. Skipping PostgreSQL.")
    
    # PostgreSQL is source of truth - use PostgreSQL data primarily
    # MongoDB is only used as fallback if PostgreSQL is unavailable
    all_patients = {}
    
    # Primary: Use PostgreSQL data (source of truth)
    if postgres_patients:
        for patient in postgres_patients:
            patient_id = patient.get("id")
            if patient_id:
                all_patients[patient_id] = patient
    # Fallback: Use MongoDB only if PostgreSQL is unavailable
    elif mongo_patients:
        for patient in mongo_patients:
            patient_id = patient.get("id")
            if patient_id:
                all_patients[patient_id] = patient
    
    # Convert to list and sort by ID for consistent pagination
    all_patients_list = list(all_patients.values())
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
    Search patients by name, id, phone, or email with pagination.
    Supports partial matches for text fields.
    - q: Search query (required)
    - page: Page number (starts from 1, default 1)
    - limit: Number of records per page (max 100, default 10)
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    
    search_term = q.strip()
    results = []
    found_ids = set()
    
    # Check if search term is numeric (for ID search)
    is_numeric = search_term.isdigit()
    search_id = int(search_term) if is_numeric else None
    
    # 1. --- PostgreSQL Search (using Prisma or fallback to raw SQL) ---
    if prisma_client:
        try:
            if is_numeric:
                # Search by ID (exact match)
                patient = prisma_client.patient.find_unique(where={"id": search_id})
                if patient:
                    patient_dict = {
                        "id": patient.id,
                        "name": patient.name,
                        "age": patient.age,
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
                # Note: Prisma Python doesn't support case-insensitive search directly, so we'll fetch all and filter
                patients = prisma_client.patient.find_many()
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
                        "name": patient.name,
                        "age": patient.age,
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
        except Exception as e:
            print(f"Error searching PostgreSQL (Prisma): {e}")
    elif postgres_cursor:
        try:
            if is_numeric:
                # Search by ID (exact match)
                postgres_cursor.execute("""
                    SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount 
                    FROM patients 
                    WHERE id = %s
                """, (search_id,))
            else:
                # Search by name, phone, or email (partial match)
                postgres_cursor.execute("""
                    SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount 
                    FROM patients 
                    WHERE name LIKE %s OR phone LIKE %s OR email LIKE %s
                """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
            
            postgres_records = postgres_cursor.fetchall()
            columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
            
            for record in postgres_records:
                patient_dict = dict(zip(columns, record))
                patient_id = patient_dict.get("id")
                if patient_id and patient_id not in found_ids:
                    results.append(patient_dict)
                    found_ids.add(patient_id)
        except Exception as e:
            print(f"Error searching PostgreSQL: {e}")
    
    # 2. --- MongoDB Search ---
    if mongo_connected and collection is not None:
        try:
            if is_numeric:
                # Search by ID (exact match)
                mongo_query = {"id": search_id}
            else:
                # Search by name, phone, or email (case-insensitive partial match)
                mongo_query = {
                    "$or": [
                        {"name": {"$regex": search_term, "$options": "i"}},
                        {"phone": {"$regex": search_term, "$options": "i"}},
                        {"email": {"$regex": search_term, "$options": "i"}}
                    ]
                }
            
            mongo_patients = list(collection.find(mongo_query, projection={"_id": 0}))
            
            for patient in mongo_patients:
                patient = clean_mongo_document(patient)
                patient_id = patient.get("id")
                if patient_id and patient_id not in found_ids:
                    results.append(patient)
                    found_ids.add(patient_id)
        except Exception as e:
            print(f"Error searching MongoDB: {e}")
    
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
    # 1. --- PostgreSQL Search (using Prisma or fallback to raw SQL) ---
    postgres_patient = None
    patient_dict = None
    
    if prisma_client:
        try:
            patient = prisma_client.patient.find_unique(where={"id": patient_id})
            if patient:
                patient_dict = {
                    "id": patient.id,
                    "name": patient.name,
                    "age": patient.age,
                    "phone": patient.phone,
                    "email": patient.email,
                    "date_of_birth": patient.date_of_birth,
                    "address": patient.address,
                    "registration_date": patient.registration_date,
                    "billed_amount": float(patient.billed_amount) if patient.billed_amount else 0.0,
                    "outstanding_amount": float(patient.outstanding_amount) if patient.outstanding_amount else 0.0
                }
        except Exception as e:
            print(f"Error fetching patient from PostgreSQL (Prisma): {e}")
    elif postgres_cursor:
        try:
            postgres_cursor.execute("SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount FROM patients WHERE id = %s", (patient_id,))
            postgres_patient = postgres_cursor.fetchone()
            if postgres_patient:
                columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
                patient_dict = dict(zip(columns, postgres_patient))
        except Exception as e:
            print(f"Error fetching patient from PostgreSQL: {e}")
    
    if patient_dict:
        # Check if patient exists in MongoDB, if not, sync it
        if mongo_connected and collection is not None:
            try:
                mongo_patient = collection.find_one({"id": patient_id}, projection={"_id": 0})
                if not mongo_patient:
                    # Patient exists in PostgreSQL but not in MongoDB - sync it
                    try:
                        collection.insert_one(patient_dict)
                        print(f"Patient ID {patient_id} synced from PostgreSQL to MongoDB.")
                    except Exception as e:
                        print(f"Failed to sync patient ID {patient_id} to MongoDB: {e}")
            except Exception as e:
                print(f"Error checking MongoDB for patient ID {patient_id}: {e}")
        
        return {"database": "PostgreSQL", "patient": patient_dict}

    # 2. --- MongoDB Search ---
    if mongo_connected and collection is not None:
        try:
            mongo_patient = collection.find_one({"id": patient_id}, projection={"_id": 0}) # Search MongoDB using  custom 'id' integer field, and exclude _id
            if mongo_patient:
                mongo_patient = clean_mongo_document(mongo_patient)  # Clean ObjectId
                return {"database": "MongoDB", "patient": mongo_patient}
        except Exception as e:
            print(f"Error searching MongoDB: {e}")
    raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found in any database.")

@router.post("/")
def create_patient(patient: Patient):
    # Initial Validation (Always run first)
    if not patient.name or not patient.phone:
        raise HTTPException(status_code=400, detail="Name and phone cannot be empty")
    if patient.age <= 0:
        raise HTTPException(status_code=400, detail="Age must be greater than 0")
    if patient.billed_amount < 0 or patient.outstanding_amount < 0:
        raise HTTPException(status_code=400, detail="Amounts cannot be negative")

    # Check for existing phone number in both databases
    mongo_existing = None
    if mongo_connected and collection is not None:
        try:
            mongo_existing = collection.find_one({"phone": patient.phone}, projection={"_id": 0})
        except Exception as e:
            print(f"Error checking phone in MongoDB: {e}")
    
    postgres_existing = None
    if prisma_client:
        try:
            postgres_existing = prisma_client.patient.find_first(where={"phone": patient.phone})
        except Exception as e:
            print(f"Error checking phone in PostgreSQL (Prisma): {e}")
    elif postgres_cursor:
        try:
            postgres_cursor.execute("SELECT id FROM patients WHERE phone = %s", (patient.phone,))
            postgres_existing = postgres_cursor.fetchone()
        except Exception as e:
            print(f"Error checking phone in PostgreSQL: {e}")
    
    if mongo_existing or postgres_existing:
        raise HTTPException(status_code=400, detail="Patient with this phone number already exists (in MongoDB or PostgreSQL).")
    
    patient_data = patient.model_dump()
    patient_data.pop('id', None)  # Remove any existing id (will be set from database)
    save_successful = False
    new_patient_id = None
    
    # Attempt PostgreSQL save first (preferred - generates ID automatically)
    if prisma_client:
        try:
            new_patient = prisma_client.patient.create(
                data={
                    "name": patient.name,
                    "age": patient.age,
                    "phone": patient.phone,
                    "email": patient.email,
                    "date_of_birth": patient.date_of_birth,
                    "address": patient.address,
                    "registration_date": patient.registration_date,
                    "billed_amount": Decimal(str(patient.billed_amount)),
                    "outstanding_amount": Decimal(str(patient.outstanding_amount))
                }
            )
            new_patient_id = new_patient.id
            print(f"Patient successfully saved to PostgreSQL with ID {new_patient_id} (Prisma).")
            save_successful = True
        except Exception as e:
            print(f"PostgreSQL save FAILED (Prisma). Error: {str(e)}.")
    elif postgres_cursor and postgres_conn:
        try:
            # Use RETURNING clause to get the generated ID
            postgres_cursor.execute("""
                INSERT INTO patients (name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (patient.name, patient.age, patient.phone, patient.email, patient.date_of_birth, patient.address, patient.registration_date, patient.billed_amount, patient.outstanding_amount))
            result = postgres_cursor.fetchone()
            new_patient_id = result[0] if result else None
            postgres_conn.commit()
            print(f"Patient successfully saved to PostgreSQL with ID {new_patient_id}.")
            save_successful = True
        except Exception as e:
            print(f"PostgreSQL save FAILED. Error: {str(e)}.")
    
    # If PostgreSQL failed/unavailable, try MongoDB-only save
    # Only do this if PostgreSQL is truly unavailable
    # Note: MongoDB doesn't have auto-increment, but we'll use a simple counter
    # In production, consider using MongoDB's ObjectId or a proper sequence collection
    if not new_patient_id and not prisma_client and not postgres_cursor and mongo_connected and collection is not None:
        try:
            # For MongoDB fallback, use a simple counter approach
            # In production, consider using a proper sequence collection or ObjectId
            # This is a fallback only when PostgreSQL is completely unavailable
            max_id_doc = collection.find_one(sort=[("id", -1)], projection={"id": 1, "_id": 0})
            new_patient_id = (max_id_doc.get("id", 0) + 1) if max_id_doc and max_id_doc.get("id") else 1
            patient_data["id"] = new_patient_id
            collection.insert_one(patient_data)
            print(f"Patient successfully saved to MongoDB with ID {new_patient_id} (PostgreSQL unavailable).")
            print("⚠️  Note: MongoDB ID generation is not thread-safe. PostgreSQL is recommended.")
            save_successful = True
        except Exception as e:
            print(f"MongoDB save FAILED. Error: {str(e)}.")
    
    # If PostgreSQL succeeded, also save to MongoDB (sync)
    if new_patient_id and save_successful and mongo_connected and collection is not None:
        try:
            patient_data["id"] = new_patient_id
            # Use upsert to avoid duplicate key errors
            collection.update_one(
                {"id": new_patient_id},
                {"$set": patient_data},
                upsert=True
            )
            print(f"Patient successfully synced to MongoDB with ID {new_patient_id}.")
        except Exception as e:
            print(f"MongoDB sync FAILED (non-critical). Error: {str(e)}.")
    
    # Final Response
    if save_successful and new_patient_id:
        return {"message": f"Patient created successfully with ID {new_patient_id}."}
    else:
        raise HTTPException(status_code=503, detail="Could not save patient. Both databases are unavailable. Please check your database connections.")


@router.put("/{patient_id}")
def update_patient(patient_id: int, patient: Patient): # Now expects a simple INTEGER ID
    # Validation (for simplicity, assumed valid patient data)
    if not patient.name or not patient.phone:
        raise HTTPException(status_code=400, detail="Name and phone cannot be empty")
    update_data = patient.model_dump(exclude_none=True)
    update_data.pop('id', None)
    
    # 1. --- PostgreSQL Update (PRIMARY - source of truth) using Prisma or fallback to raw SQL ---
    postgres_updated = False
    if prisma_client:
        try:
            updated_patient = prisma_client.patient.update(
                where={"id": patient_id},
                data={
                    "name": patient.name,
                    "age": patient.age,
                    "phone": patient.phone,
                    "email": patient.email,
                    "date_of_birth": patient.date_of_birth,
                    "address": patient.address,
                    "registration_date": patient.registration_date,
                    "billed_amount": Decimal(str(patient.billed_amount)),
                    "outstanding_amount": Decimal(str(patient.outstanding_amount))
                }
            )
            print(f"PostgreSQL patient ID {patient_id} updated (primary, Prisma).")
            postgres_updated = True
            
            # Sync to MongoDB (backup)
            if mongo_connected and collection is not None:
                try:
                    patient_dict = {
                        "id": updated_patient.id,
                        "name": updated_patient.name,
                        "age": updated_patient.age,
                        "phone": updated_patient.phone,
                        "email": updated_patient.email,
                        "date_of_birth": updated_patient.date_of_birth,
                        "address": updated_patient.address,
                        "registration_date": updated_patient.registration_date,
                        "billed_amount": float(updated_patient.billed_amount) if updated_patient.billed_amount else 0.0,
                        "outstanding_amount": float(updated_patient.outstanding_amount) if updated_patient.outstanding_amount else 0.0
                    }
                    # Update or insert in MongoDB
                    collection.update_one(
                        {"id": patient_id},
                        {"$set": patient_dict},
                        upsert=True
                    )
                    print(f"Patient ID {patient_id} synced to MongoDB (backup).")
                except Exception as e:
                    print(f"Failed to sync patient ID {patient_id} to MongoDB: {e}")
        except Exception as e:
            print(f"PostgreSQL Update FAILED (Prisma). Error: {str(e)}.")
    elif postgres_cursor and postgres_conn:
        try:
            postgres_cursor.execute("""
                UPDATE patients
                SET name=%s, age=%s, phone=%s, email=%s, date_of_birth=%s, address=%s, registration_date=%s, billed_amount=%s, outstanding_amount=%s
                WHERE id=%s
            """, (patient.name, patient.age, patient.phone, patient.email, patient.date_of_birth, patient.address, patient.registration_date, 
                patient.billed_amount, patient.outstanding_amount, patient_id))
            postgres_conn.commit()
            if postgres_cursor.rowcount == 1:
                print(f"PostgreSQL patient ID {patient_id} updated (primary).")
                postgres_updated = True
                
                # Sync to MongoDB (backup)
                if mongo_connected and collection is not None:
                    try:
                        # Get the updated patient data from PostgreSQL
                        postgres_cursor.execute("SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount FROM patients WHERE id = %s", (patient_id,))
                        updated_patient = postgres_cursor.fetchone()
                        if updated_patient:
                            columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
                            patient_dict = dict(zip(columns, updated_patient))
                            # Update or insert in MongoDB
                            collection.update_one(
                                {"id": patient_id},
                                {"$set": patient_dict},
                                upsert=True
                            )
                            print(f"Patient ID {patient_id} synced to MongoDB (backup).")
                    except Exception as e:
                        print(f"Failed to sync patient ID {patient_id} to MongoDB: {e}")
        except Exception as e:
            print(f"PostgreSQL Update FAILED. Error: {str(e)}.")
    
    # 2. --- MongoDB Update (FALLBACK - only if PostgreSQL unavailable) ---
    mongo_updated = False
    if not postgres_updated and mongo_connected and collection is not None:
        try:
            result = collection.update_one({"id": patient_id}, {"$set": update_data})
            if result.matched_count == 1:
                print(f"MongoDB patient ID {patient_id} updated (PostgreSQL unavailable).")
                mongo_updated = True
        except Exception as e:
            print(f"MongoDB Update FAILED. Error: {str(e)}.")
        
    # Final Response
    if postgres_updated:
        return {"message": f"Patient with ID {patient_id} updated successfully in PostgreSQL (primary)."}
    elif mongo_updated:
        return {"message": f"Patient with ID {patient_id} updated in MongoDB (PostgreSQL unavailable)."}
    else:
        raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found in any database to update.")



@router.delete("/{patient_id}")
def delete_patient(patient_id: int):
    # 1. --- PostgreSQL Delete (PRIMARY - source of truth) using Prisma or fallback to raw SQL ---
    postgres_deleted = False
    if prisma_client:
        try:
            deleted_patient = prisma_client.patient.delete(where={"id": patient_id})
            print(f"Patient with ID {patient_id} successfully deleted from PostgreSQL (primary, Prisma).")
            postgres_deleted = True
            
            # Also delete from MongoDB (backup)
            if mongo_connected and collection is not None:
                try:
                    collection.delete_one({"id": patient_id})
                    print(f"Patient ID {patient_id} also deleted from MongoDB (backup).")
                except Exception as e:
                    print(f"Failed to delete patient ID {patient_id} from MongoDB: {e}")
        except Exception as e:
            if "Record to delete does not exist" in str(e) or "not found" in str(e).lower():
                print(f"Patient with ID {patient_id} not found in PostgreSQL for deletion.")
            else:
                print(f"Error deleting patient from PostgreSQL (Prisma): {e}.")
    elif postgres_cursor and postgres_conn:
        try:
            postgres_cursor.execute("DELETE FROM patients WHERE id = %s", (patient_id,))
            postgres_conn.commit()
            if postgres_cursor.rowcount == 1:
                print(f"Patient with ID {patient_id} successfully deleted from PostgreSQL (primary).")
                postgres_deleted = True
                
                # Also delete from MongoDB (backup)
                if mongo_connected and collection is not None:
                    try:
                        collection.delete_one({"id": patient_id})
                        print(f"Patient ID {patient_id} also deleted from MongoDB (backup).")
                    except Exception as e:
                        print(f"Failed to delete patient ID {patient_id} from MongoDB: {e}")
            else:
                print(f"Patient with ID {patient_id} not found in PostgreSQL for deletion.")
        except Exception as e:
            print(f"Error deleting patient from PostgreSQL: {e}.")
    
    # 2. --- MongoDB Delete (FALLBACK - only if PostgreSQL unavailable) ---
    mongo_deleted = False
    if not postgres_deleted and mongo_connected and collection is not None:
        try:
            result = collection.delete_one({"id": patient_id})
            if result.deleted_count == 1:
                print(f"Patient ID {patient_id} successfully deleted from MongoDB (PostgreSQL unavailable).")
                mongo_deleted = True
            else:
                print(f"Patient ID {patient_id} not found in MongoDB for deletion.")
        except Exception as e:
            print(f"Error deleting patient from MongoDB: {e}.")
    
    # Final Response
    if postgres_deleted:
        return {"message": f"Patient with ID {patient_id} deleted successfully from PostgreSQL (primary)."}
    elif mongo_deleted:
        return {"message": f"Patient with ID {patient_id} deleted from MongoDB (PostgreSQL unavailable)."}
    else:
        raise HTTPException(status_code=404, detail="Patient not found in any database to delete.")
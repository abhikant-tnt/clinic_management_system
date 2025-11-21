from fastapi import APIRouter, HTTPException, Query
from app.modules.patients.schemas import Patient
from app.core.database import collection, sqlite_conn, sqlite_cursor

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
    # Fetching MongoDB Data
    mongo_patients = []
    mongo_ids = set()  # Track which IDs exist in MongoDB
    try:
        patients = list(collection.find({}, projection={"_id": 0})) # projection means explicitly exclude the MongoDB internal _id field
        # Clean all documents to ensure no ObjectId remains
        mongo_patients = [clean_mongo_document(p) for p in patients]
        mongo_ids = {p.get("id") for p in mongo_patients if p.get("id") is not None}  # Get all MongoDB IDs
    except Exception as e:
        print(f"Error fetching data from MongoDB: {e}. Skipping MongoDB.")

    # Fetching sqlite3 data
    sqlite_cursor.execute("SELECT id,name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount FROM patients")
    sqlite_records = sqlite_cursor.fetchall()
    sqlite_patients = []
    columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
    for record in sqlite_records:
        patient_dict = dict(zip(columns, record))
        sqlite_patients.append(patient_dict)
        
        # Sync missing patients from SQLite to MongoDB
        patient_id = patient_dict.get("id")
        if patient_id and patient_id not in mongo_ids:
            try:
                collection.insert_one(patient_dict)
                print(f"Patient ID {patient_id} synced from SQLite to MongoDB.")
            except Exception as e:
                print(f"Failed to sync patient ID {patient_id} to MongoDB: {e}")
    
    # Deduplicate patients by ID (SQLite is source of truth, but include any MongoDB-only patients)
    all_patients = {}
    # First add SQLite patients (source of truth)
    for patient in sqlite_patients:
        patient_id = patient.get("id")
        if patient_id:
            all_patients[patient_id] = patient
    
    # Then add MongoDB patients that don't exist in SQLite (fallback)
    for patient in mongo_patients:
        patient_id = patient.get("id")
        if patient_id and patient_id not in all_patients:
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
    
    # 1. --- SQLite Search ---
    try:
        if is_numeric:
            # Search by ID (exact match)
            sqlite_cursor.execute("""
                SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount 
                FROM patients 
                WHERE id = ?
            """, (search_id,))
        else:
            # Search by name, phone, or email (partial match)
            sqlite_cursor.execute("""
                SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount 
                FROM patients 
                WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
            """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
        
        sqlite_records = sqlite_cursor.fetchall()
        columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
        
        for record in sqlite_records:
            patient_dict = dict(zip(columns, record))
            patient_id = patient_dict.get("id")
            if patient_id and patient_id not in found_ids:
                results.append(patient_dict)
                found_ids.add(patient_id)
    except Exception as e:
        print(f"Error searching SQLite: {e}")
    
    # 2. --- MongoDB Search ---
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
    # 1. --- SQLite Search ---
    sqlite_cursor.execute("SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount FROM patients WHERE id = ?", (patient_id,))
    sqlite_patient = sqlite_cursor.fetchone()
    
    if sqlite_patient:
        columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
        patient_dict = dict(zip(columns, sqlite_patient))
        
        # Check if patient exists in MongoDB, if not, sync it
        try:
            mongo_patient = collection.find_one({"id": patient_id}, projection={"_id": 0})
            if not mongo_patient:
                # Patient exists in SQLite but not in MongoDB - sync it
                try:
                    collection.insert_one(patient_dict)
                    print(f"Patient ID {patient_id} synced from SQLite to MongoDB.")
                except Exception as e:
                    print(f"Failed to sync patient ID {patient_id} to MongoDB: {e}")
        except Exception as e:
            print(f"Error checking MongoDB for patient ID {patient_id}: {e}")
        
        return {"database": "SQLite", "patient": patient_dict}

    # 2. --- MongoDB Search ---
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
    mongo_existing = collection.find_one({"phone": patient.phone}, projection={"_id": 0})
    sqlite_cursor.execute("SELECT id FROM patients WHERE phone = ?", (patient.phone,))
    sqlite_existing = sqlite_cursor.fetchone()
    if mongo_existing or sqlite_existing:
        raise HTTPException(status_code=400, detail="Patient with this phone number already exists (in MongoDB or SQLite).")
    patient_data = patient.model_dump()
    patient_data.pop('id', None)  # Remove any existing id (will be set from SQLite)
    save_successful = False
    new_patient_id = None
    
    # --- Simplified ID Generation: Let SQLite AUTO-INCREMENT generate the ID first ---
    # Attempt SQLite save (This must happen first to generate the ID)
    try:
        sqlite_cursor.execute("""
            INSERT INTO patients (name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (patient.name, patient.age, patient.phone, patient.email, patient.date_of_birth, patient.address, patient.registration_date, patient.billed_amount, patient.outstanding_amount))
        sqlite_conn.commit()
        new_patient_id = sqlite_cursor.lastrowid # Get the ID that SQLite just generated (this is the unified key)
        print(f"Patient successfully saved to SQLite with ID {new_patient_id}.")
        save_successful = True
    except Exception as e:
        print(f"SQLite save FAILED. Error: {str(e)}.")
        
    # Attempt MongoDB save (only if SQLite was successful and generated an ID)
    if new_patient_id:
        patient_data["id"] = new_patient_id # Add the unified ID from SQLite
        try:
            # MongoDB inserts the document including our custom 'id'
            collection.insert_one(patient_data)
            print(f"Patient successfully saved to MongoDB with ID {new_patient_id}.")
            save_successful = True # Keep true, as the previous successful save might have failed the MongoDB part
        except Exception as e:
            print(f"MongoDB save FAILED (Server Unavailable). Error: {str(e)}.")
            # If MongoDB fails, we keep the SQLite record but log the error.
            
    
    # Final Response --> Success if at least one database saved the data
    if save_successful:
        return {"message": f"Patient created successfully (in at least one database) with ID {new_patient_id}."}
    else:
        # If SQLite failed to save, then save_successful is False
        raise HTTPException(status_code=500, detail="FATAL: Could not save patient to any database. Check server logs.")


@router.put("/{patient_id}")
def update_patient(patient_id: int, patient: Patient): # Now expects a simple INTEGER ID
    # Validation (for simplicity, assumed valid patient data)
    if not patient.name or not patient.phone:
        raise HTTPException(status_code=400, detail="Name and phone cannot be empty")
    update_data = patient.model_dump(exclude_none=True)
    update_data.pop('id', None)
    
    # 1. --- MongoDB Update (by 'id' field) ---
    mongo_updated = False
    try:
        result = collection.update_one({"id": patient_id}, {"$set": update_data}) # Search by the unified 'id' field
        if result.matched_count == 1:
            print(f"MongoDB patient ID {patient_id} updated.")
            mongo_updated = True
        elif result.matched_count == 0:
            # Patient doesn't exist in MongoDB, but might exist in SQLite - sync it
            print(f"Patient ID {patient_id} not found in MongoDB, attempting to sync from SQLite...")
    except Exception as e:
        print(f"MongoDB Update FAILED. Error: {str(e)}.")

    # 2. --- SQLite Update (by 'id' column) ---
    sqlite_updated = False
    try:
        sqlite_cursor.execute("""
            UPDATE patients
            SET name=?, age=?, phone=?, email=?, date_of_birth=?, address=?, registration_date=?, billed_amount=?, outstanding_amount=?
            WHERE id=?
        """, (patient.name, patient.age, patient.phone, patient.email, patient.date_of_birth, patient.address, patient.registration_date, 
              patient.billed_amount, patient.outstanding_amount, patient_id)) # Search by 'id'
        sqlite_conn.commit()
        if sqlite_cursor.rowcount == 1:
            print(f"SQLite patient ID {patient_id} updated.")
            sqlite_updated = True 
            # If SQLite update succeeded but MongoDB doesn't have the record, sync it
            if not mongo_updated:
                try:
                    # Get the updated patient data from SQLite
                    sqlite_cursor.execute("SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount FROM patients WHERE id = ?", (patient_id,))
                    updated_patient = sqlite_cursor.fetchone()
                    if updated_patient:
                        columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
                        patient_dict = dict(zip(columns, updated_patient))
                        collection.insert_one(patient_dict)
                        print(f"Patient ID {patient_id} synced from SQLite to MongoDB after update.")
                        mongo_updated = True
                except Exception as e:
                    print(f"Failed to sync patient ID {patient_id} to MongoDB after update: {e}")
    except Exception as e:
        print(f"SQLite Update FAILED. Error: {str(e)}.")
        
    # Final Response
    if mongo_updated or sqlite_updated:
        return {"message": f"Patient with ID {patient_id} updated successfully (in at least one database)."}
    else:
        raise HTTPException(status_code=404, detail=f"Patient with ID {patient_id} not found in any database to update.")



@router.delete("/{patient_id}")
def delete_patient(patient_id: int):
    # 1. --- MongoDB Delete (by 'id' field) ---
    mongo_deleted = False
    try:
        result = collection.delete_one({"id": patient_id}) # Search by the unified 'id' field
        if result.deleted_count == 1:
            print(f"Patient ID {patient_id} successfully deleted from MongoDB.")
            mongo_deleted = True
        else:
            print(f"Patient ID {patient_id} not found in MongoDB for deletion.")
    except Exception as e:
        print(f"Error deleting patient from MongoDB: {e}.")


    # 2. --- SQLite Delete (by 'id' column) ---
    sqlite_deleted = False
    try:
        sqlite_cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,)) # Search by 'id'
        sqlite_conn.commit()
        if sqlite_cursor.rowcount == 1:
            print(f"Patient with ID {patient_id} successfully deleted from SQLite.")
            sqlite_deleted = True
        else:
            print(f"Patient with ID {patient_id} not found in SQLite for deletion.")
    except Exception as e:
        print(f"Error deleting patient from SQLite: {e}.")


    # Final Response
    if mongo_deleted or sqlite_deleted:
        return {"message": f"Patient with ID {patient_id} deleted successfully (from at least one database)."}
    else:
        raise HTTPException(status_code=404, detail="Patient not found in any database to delete.")
from pymongo import MongoClient
from fastapi import FastAPI, HTTPException
from datetime import datetime
from models import Patient
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

### connection to the database
client = MongoClient("mongodb://localhost:27017/")
conn = client["patients_database"]
collection = conn["records"]
app = FastAPI()

#new sqlite local database setup
try:
    # Connect to the SQLite database (it will be created if it doesn't exist)
    sqlite_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    sqlite_cursor = sqlite_conn.cursor()
    # Create the patient table if it doesn't exist
    sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            phone TEXT UNIQUE NOT NULL,
            registration_date TEXT,
            billed_amount REAL,
            outstanding_amount REAL
        )
    """)
    sqlite_conn.commit()
except Exception as e:
    print(f"Error setting up SQLite database: {e}")

@app.get("/api/patients/")
def get_patients():
    # Fetching MongoDB Data
    try:
        patients = list(collection.find({}))
        for patient in patients:
            # Convert the ObjectId object to a simple string
            patient["_id"] = str(patient["_id"])
        return {"patients": patients}
        mongo_patients = patients # Store the fetched data
    except Exception as e:
        print(f"Error fetching data from MongoDB: {e}. Skipping MongoDB.")

        
    # Fetching sqlite3 data
    sqlite_cursor.execute("SELECT name, age, phone, registration_date, billed_amount, outstanding_amount FROM patients")
    sqlite_records = sqlite_cursor.fetchall()
    sqlite_patients = []
    columns = ["name", "age", "phone", "registration_date", "billed_amount", "outstanding_amount"]
    for record in sqlite_records:
        sqlite_patients.append(dict(zip(columns, record)))

    # getting data  from both databases or either one 
    return {"patients": mongo_patients + sqlite_patients} 

@app.get("/")
def home():
    # This is what the server returns when you go to the root path (/)
    return {"message": "Welcome to the Patient API!"}

@app.post("/api/patients/")
def create_patient(patient: Patient):
    # Initial Validation (Always run first)
    if not patient.name or not patient.phone:
        raise HTTPException(status_code=400, detail="Name and phone cannot be empty")
    if patient.age <= 0:
        raise HTTPException(status_code=400, detail="Age must be greater than 0")
    if patient.billed_amount < 0 or patient.outstanding_amount < 0:
        raise HTTPException(status_code=400, detail="Amounts cannot be negative")

    # Check for existing phone number in both databases
    mongo_existing = collection.find_one({"phone": patient.phone})
    sqlite_cursor.execute("SELECT id FROM patients WHERE phone = ?", (patient.phone,))
    sqlite_existing = sqlite_cursor.fetchone()
    if mongo_existing or sqlite_existing:
        raise HTTPException(status_code=400, detail="Patient with this phone number already exists (in MongoDB or SQLite).")
    patient_data = patient.model_dump()
    save_successful = False
    
    # Attempt MongoDB save
    try:
        collection.insert_one(patient_data)
        print("Patient successfully saved to MongoDB.")
        save_successful = True
    except Exception as e:
        print(f"MongoDB save FAILED (Server Unavailable). Error: {str(e)}.")

    # Attempt SQLite save regardless of MongoDB result
    try:
        sqlite_cursor.execute("""
            INSERT INTO patients (name, age, phone, registration_date, billed_amount, outstanding_amount)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (patient.name, patient.age, patient.phone, patient.registration_date, patient.billed_amount, patient.outstanding_amount))
        sqlite_conn.commit()
        print("Patient successfully saved to SQLite.")
        save_successful = True
    except Exception as e:
        print(f"SQLite save FAILED. Error: {str(e)}.")
        
    
    # Final Response --> Success if at least one database saved the data
    if save_successful:
        return {"message": "Patient created successfully (in at least one database)."}
    else:
        raise HTTPException(status_code=500, detail="FATAL: Could not save patient to any database. Check server logs.")
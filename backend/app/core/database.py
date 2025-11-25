from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
import psycopg2
from psycopg2 import OperationalError as PostgresOperationalError
from app.core.config import settings
import os

# Set DATABASE_URL for Prisma (only if password is set)
try:
    os.environ["DATABASE_URL"] = settings.DATABASE_URL
except ValueError as e:
    print(f"⚠️  {e}")
    print("   Prisma will not be available until PostgreSQL password is configured.")

# Prisma client setup
prisma_client = None
try:
    from prisma import Prisma
    prisma_client = Prisma()
except ImportError:
    print("⚠️  Prisma not installed. Run: pip install prisma")
    prisma_client = None
except Exception as e:
    print(f"⚠️  Prisma initialization error: {e}")
    prisma_client = None

# MongoDB database setup
mongo_connected = False
client = None
conn = None
collection = None

print("\n" + "="*60)
print("DATABASE CONNECTION STATUS")
print("="*60)
print(f"PostgreSQL Config: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}, User: {settings.POSTGRES_USER}, DB: {settings.POSTGRES_DB}")

# Attempt MongoDB connection
try:
    client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=2000)  # 2 second timeout
    # Test connection
    client.admin.command('ping')
    conn = client[settings.MONGODB_DATABASE]
    collection = conn["records"]
    mongo_connected = True
    print(f"✅ MongoDB: CONNECTED (Database: {settings.MONGODB_DATABASE})")
except (ServerSelectionTimeoutError, ConnectionFailure, Exception) as e:
    mongo_connected = False
    print(f"❌ MongoDB: NOT CONNECTED - {str(e)}")
    print("   App will continue running, but MongoDB operations will be unavailable.")

# PostgreSQL database setup
postgres_conn = None
postgres_cursor = None

def try_postgres_connection(password=None):
    """Try to connect to PostgreSQL, first without password (trust auth), then with password"""
    # Convert port to int if it's a string
    port = int(settings.POSTGRES_PORT) if isinstance(settings.POSTGRES_PORT, str) else settings.POSTGRES_PORT
    connection_params = {
        "host": settings.POSTGRES_HOST,
        "port": port,
        "user": settings.POSTGRES_USER,
        "database": "postgres"
    }
    
    error_messages = []
    
    # First try: without password (for trust authentication)
    if password is None:
        try:
            conn = psycopg2.connect(**connection_params)
            return conn, "trust (no password)", None
        except Exception as e:
            error_messages.append(f"Trust auth failed: {str(e)}")
    
    # Second try: with password from .env
    if password:
        try:
            connection_params["password"] = password
            conn = psycopg2.connect(**connection_params)
            return conn, "password authentication", None
        except Exception as e:
            error_messages.append(f"Password auth failed: {str(e)}")
    
    return None, None, error_messages

# Step 1: Check if database exists, create if it doesn't
default_conn = None
auth_method = None
connection_errors = []

# Try connecting without password first (trust authentication)
default_conn, auth_method, errors = try_postgres_connection(password=None)
if errors:
    connection_errors.extend(errors)

# If that fails, try with password
if not default_conn:
    default_conn, auth_method, errors = try_postgres_connection(password=settings.POSTGRES_PASSWORD)
    if errors:
        connection_errors.extend(errors)

if default_conn:
    try:
        default_conn.autocommit = True
        default_cursor = default_conn.cursor()
        
        # Check if database exists
        default_cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (settings.POSTGRES_DB,)
        )
        db_exists = default_cursor.fetchone()
        
        if not db_exists:
            # Database doesn't exist, create it
            # Use identifier quoting to prevent SQL injection
            # PostgreSQL identifiers must be quoted if they contain special characters
            db_name_quoted = f'"{settings.POSTGRES_DB}"'
            print(f"   Database '{settings.POSTGRES_DB}' not found. Creating it...")
            # Note: CREATE DATABASE doesn't support parameterized queries, so we use identifier quoting
            # This is safe because we validate the database name format
            default_cursor.execute(f"CREATE DATABASE {db_name_quoted}")
            print(f"   Database '{settings.POSTGRES_DB}' created successfully.")
        else:
            print(f"   Database '{settings.POSTGRES_DB}' already exists.")
        
        default_cursor.close()
        default_conn.close()
        
        # Step 2: Connect to the target database (whether it existed or was just created)
        # Convert port to int if it's a string
        port = int(settings.POSTGRES_PORT) if isinstance(settings.POSTGRES_PORT, str) else settings.POSTGRES_PORT
        connection_params = {
            "host": settings.POSTGRES_HOST,
            "port": port,
            "user": settings.POSTGRES_USER,
            "database": settings.POSTGRES_DB
        }
        
        # Use the same authentication method that worked
        if auth_method == "password authentication":
            connection_params["password"] = settings.POSTGRES_PASSWORD
        
        postgres_conn = psycopg2.connect(**connection_params)
        postgres_conn.autocommit = True
        postgres_cursor = postgres_conn.cursor()
        print(f"✅ PostgreSQL: CONNECTED (Database: {settings.POSTGRES_DB}, Auth: {auth_method})")
        
    except Exception as e:
        print(f"❌ PostgreSQL: Connection established but error occurred - {str(e)}")
        postgres_conn = None
        postgres_cursor = None
else:
    print("❌ PostgreSQL: NOT CONNECTED")
    print("   Could not connect with or without password.")
    print("\n   Connection Details:")
    print(f"      Host: {settings.POSTGRES_HOST}")
    print(f"      Port: {settings.POSTGRES_PORT}")
    print(f"      User: {settings.POSTGRES_USER}")
    print(f"      Database: {settings.POSTGRES_DB}")
    if connection_errors:
        print("\n   Error Details:")
        for error in connection_errors:
            print(f"      - {error}")
    
    # Check if it's a "Connection refused" error (service not running)
    is_service_down = any("Connection refused" in str(err) for err in connection_errors)
    
    if is_service_down:
        print("\n   ⚠️  PostgreSQL service appears to be NOT RUNNING")
        print("   Action Required:")
        print("      1. Open Services (services.msc)")
        print("      2. Find 'PostgreSQL' service")
        print("      3. Right-click → Start (if stopped)")
        print("      4. Restart this application")
    else:
        # Connection refused not the issue - show manual setup instructions
        print("\n   Manual Setup Required:")
        print("      1. Verify PostgreSQL service is running")
        print("      2. Check POSTGRES_PORT and POSTGRES_PASSWORD in .env file")
        print("      3. Current settings:")
        print(f"         Port: {settings.POSTGRES_PORT}")
        print(f"         Password: {'*' * len(settings.POSTGRES_PASSWORD) if settings.POSTGRES_PASSWORD else 'Not set'}")
    
    print("\n   App will continue running, but PostgreSQL operations will be unavailable.\n")
    postgres_conn = None
    postgres_cursor = None

# Create the patient table if connection is successful
if postgres_conn and postgres_cursor:
    try:
        postgres_cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                age INTEGER,
                phone VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(255),
                date_of_birth VARCHAR(50),
                address TEXT,
                registration_date VARCHAR(50),
                billed_amount DECIMAL(10, 2),
                outstanding_amount DECIMAL(10, 2)
            )
        """)
        postgres_conn.commit()
        print("   Patients table created/verified successfully.")
        
        # Note: Use TRUNCATE ... RESTART IDENTITY when clearing the table to reset sequence
    except Exception as e:
        print(f"   Error creating patients table: {e}")


# PRIMARY SYNC: PostgreSQL (local) → MongoDB (server)
# This is the main sync direction - PostgreSQL is source of truth
def sync_postgres_to_mongo():
    """Sync PostgreSQL (primary) to MongoDB (backup) - runs regularly"""
    if not (mongo_connected and collection is not None):
        return
    
    # Use Prisma if available and connected, otherwise fall back to raw SQL
    # Check if Prisma client exists and is ready to use
    prisma_available = prisma_client is not None
    if prisma_available:
        try:
            # Get all patients from PostgreSQL using Prisma
            postgres_patients = prisma_client.patient.find_many()
            
            # Get existing MongoDB IDs
            mongo_patients = list(collection.find({}, projection={"_id": 0, "id": 1}))
            mongo_ids = {p.get("id") for p in mongo_patients if p.get("id")}
            
            # Sync PostgreSQL → MongoDB
            synced_count = 0
            for patient in postgres_patients:
                patient_id = patient.id
                if patient_id and patient_id not in mongo_ids:
                    try:
                        # Convert Prisma model to dict
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
                        # Use upsert to avoid duplicate key errors
                        collection.update_one(
                            {"id": patient_id},
                            {"$set": patient_dict},
                            upsert=True
                        )
                        synced_count += 1
                    except Exception as e:
                        print(f"   ⚠️  Failed to sync patient ID {patient_id} to MongoDB: {e}")
            
            if synced_count > 0:
                print(f"   ✅ Synced {synced_count} patient(s) from PostgreSQL → MongoDB (backup).")
        except Exception as e:
            print(f"   ⚠️  Error syncing PostgreSQL → MongoDB: {e}")
    elif postgres_conn and postgres_cursor:
        # Fallback to raw SQL if Prisma not available
        try:
            # Get all patients from PostgreSQL (source of truth)
            postgres_cursor.execute("SELECT id, name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount FROM patients")
            postgres_records = postgres_cursor.fetchall()
            columns = ["id", "name", "age", "phone", "email", "date_of_birth", "address", "registration_date", "billed_amount", "outstanding_amount"]
            postgres_patients = [dict(zip(columns, record)) for record in postgres_records]
            
            # Get existing MongoDB IDs
            mongo_patients = list(collection.find({}, projection={"_id": 0, "id": 1}))
            mongo_ids = {p.get("id") for p in mongo_patients if p.get("id")}
            
            # Sync PostgreSQL → MongoDB
            synced_count = 0
            for patient in postgres_patients:
                patient_id = patient.get("id")
                if patient_id and patient_id not in mongo_ids:
                    try:
                        # Use upsert to avoid duplicate key errors
                        collection.update_one(
                            {"id": patient_id},
                            {"$set": patient},
                            upsert=True
                        )
                        synced_count += 1
                    except Exception as e:
                        print(f"   ⚠️  Failed to sync patient ID {patient_id} to MongoDB: {e}")
            
            if synced_count > 0:
                print(f"   ✅ Synced {synced_count} patient(s) from PostgreSQL → MongoDB (backup).")
        except Exception as e:
            print(f"   ⚠️  Error syncing PostgreSQL → MongoDB: {e}")

# RECOVERY SYNC: MongoDB (server) → PostgreSQL (local)
# Only used for initial setup or recovery when local data is lost
def sync_mongo_to_postgres_recovery():
    """Recovery sync: MongoDB → PostgreSQL - only for initial setup/recovery"""
    if not (mongo_connected and collection is not None):
        return
    
    # Check if Prisma is available, or if raw SQL connection exists
    prisma_available = prisma_client is not None
    if not (prisma_available or (postgres_conn and postgres_cursor)):
        return
    
    try:
        print("\n🔄 Recovery sync: MongoDB → PostgreSQL (initial setup/recovery)...")
        
        # Get all MongoDB patients
        mongo_patients = list(collection.find({}, projection={"_id": 0}))
        
        if not mongo_patients:
            print("   No data in MongoDB to recover.")
            return
        
        # Get existing PostgreSQL IDs
        prisma_available = prisma_client is not None
        if prisma_available:
            existing_patients = prisma_client.patient.find_many(select={"id": True})
            existing_ids = {p.id for p in existing_patients}
        else:
            postgres_cursor.execute("SELECT id FROM patients")
            existing_ids = {row[0] for row in postgres_cursor.fetchall()}
        
        synced_count = 0
        skipped_count = 0
        
        for patient in mongo_patients:
            patient_id = patient.get("id")
            
            # Skip if already exists in PostgreSQL (PostgreSQL is source of truth)
            if patient_id and patient_id in existing_ids:
                skipped_count += 1
                continue
            
            # If no ID in MongoDB, let PostgreSQL generate it automatically via SERIAL
            # Don't manually generate IDs to avoid race conditions
            if not patient_id:
                patient_id = None  # Let PostgreSQL auto-generate via SERIAL
            
            # Insert into PostgreSQL
            # Let PostgreSQL auto-generate ID via SERIAL to avoid race conditions
            try:
                prisma_available = prisma_client is not None
                if prisma_available:
                    from decimal import Decimal
                    # Don't specify id - let PostgreSQL auto-generate
                    created_patient = prisma_client.patient.create(
                        name=patient.get("name", ""),
                        age=patient.get("age"),
                        phone=patient.get("phone", ""),
                        email=patient.get("email"),
                        date_of_birth=patient.get("date_of_birth"),
                        address=patient.get("address"),
                        registration_date=patient.get("registration_date", ""),
                        billed_amount=Decimal(str(patient.get("billed_amount", 0))),
                        outstanding_amount=Decimal(str(patient.get("outstanding_amount", 0)))
                    )
                    patient_id = created_patient.id  # Get the auto-generated ID
                else:
                    # Use raw SQL - let SERIAL auto-generate ID
                    postgres_cursor.execute("""
                        INSERT INTO patients (name, age, phone, email, date_of_birth, address, registration_date, billed_amount, outstanding_amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        patient.get("name"),
                        patient.get("age"),
                        patient.get("phone"),
                        patient.get("email"),
                        patient.get("date_of_birth"),
                        patient.get("address"),
                        patient.get("registration_date"),
                        patient.get("billed_amount", 0),
                        patient.get("outstanding_amount", 0)
                    ))
                    result = postgres_cursor.fetchone()
                    patient_id = result[0] if result else None
                    postgres_conn.commit()
                synced_count += 1
            except Exception as e:
                # Handle unique constraint on phone or other errors
                if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                    skipped_count += 1
                else:
                    print(f"   ⚠️  Failed to recover patient ID {patient_id}: {e}")
        
        if synced_count > 0:
            print(f"   ✅ Recovered {synced_count} patient(s) from MongoDB → PostgreSQL.")
        if skipped_count > 0:
            print(f"   ℹ️  Skipped {skipped_count} patient(s) (already exist in PostgreSQL).")
        if synced_count == 0 and skipped_count == 0:
            print("   ℹ️  No new data to recover.")
    except Exception as e:
        print(f"   ⚠️  Error during recovery sync: {e}")

# Initialize Prisma client if available (before sync functions)
# Prisma should connect independently, not based on psycopg2 cursor existence
if prisma_client:
    try:
        prisma_client.connect()
        print("✅ Prisma: CONNECTED")
    except Exception as e:
        print(f"⚠️  Prisma: Connection failed - {e}")
        prisma_client = None

# Run recovery sync on startup (only once, for initial setup)
# After this, PostgreSQL becomes the source of truth
# Note: Sync functions now check if prisma_client is connected before using it
if mongo_connected and collection is not None and (prisma_client or (postgres_conn and postgres_cursor)):
    sync_mongo_to_postgres_recovery()
    # Then sync PostgreSQL → MongoDB to ensure backup is up to date
    sync_postgres_to_mongo()

# Final status summary
print("="*60)
if mongo_connected and postgres_cursor:
    prisma_status = "✅" if prisma_client else "⚠️"
    print(f"{prisma_status} Both databases are connected. App is fully operational.")
elif mongo_connected:
    print("⚠️  Only MongoDB is connected. PostgreSQL operations unavailable.")
elif postgres_cursor:
    prisma_status = "✅" if prisma_client else "⚠️"
    print(f"{prisma_status} Only PostgreSQL is connected. MongoDB operations unavailable.")
else:
    print("❌ Neither database is connected. App will run but data operations will fail.")
    print("   Please check your database connections and restart the app.")
print("="*60 + "\n")



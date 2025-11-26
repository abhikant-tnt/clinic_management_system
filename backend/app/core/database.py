import psycopg2
from psycopg2 import Error as PostgresError
from psycopg2.pool import SimpleConnectionPool
from app.core.config import settings
import os
from datetime import datetime
from typing import Optional

# Set DATABASE_URL for Prisma (only if password is set)
try:
    os.environ["DATABASE_URL"] = settings.DATABASE_URL
except ValueError as e:
    print(f"⚠️  {e}")
    print("   Prisma will not be available until Local PostgreSQL password is configured.")

# Prisma client setup (for Local PostgreSQL)
prisma_client = None
try:
    from prisma import Prisma
    prisma_client = Prisma()
except ImportError:
    print("⚠️  Prisma not installed. Run: pip install prisma")
    prisma_client = None
except (AttributeError, RuntimeError, ValueError) as e:
    print(f"⚠️  Prisma initialization error: {e}")
    prisma_client = None

print("\n" + "="*60)
print("DATABASE CONNECTION STATUS")
print("="*60)
print(f"Tenant ID: {settings.TENANT_ID}")
print(f"Local PostgreSQL Config: {settings.LOCAL_POSTGRES_HOST}:{settings.LOCAL_POSTGRES_PORT}, User: {settings.LOCAL_POSTGRES_USER}, DB: {settings.LOCAL_POSTGRES_DB}")
print(f"Main Server PostgreSQL Config: {settings.MAIN_POSTGRES_HOST}:{settings.MAIN_POSTGRES_PORT}, User: {settings.MAIN_POSTGRES_USER}, DB: {settings.MAIN_POSTGRES_DB}")

# Local PostgreSQL database setup
local_postgres_conn = None
local_postgres_cursor = None

# Main Server PostgreSQL connection pool
main_postgres_pool: Optional[SimpleConnectionPool] = None
main_postgres_connected = False

def try_postgres_connection(host: str, port: str, user: str, database: str, password: Optional[str] = None):
    """Try to connect to PostgreSQL, first without password (trust auth), then with password"""
    port_int = int(port) if isinstance(port, str) else port
    connection_params = {
        "host": host,
        "port": port_int,
        "user": user,
        "database": database
    }
    
    error_messages = []
    
    # First try: without password (for trust authentication)
    if password is None or password == "":
        try:
            conn = psycopg2.connect(**connection_params)
            return conn, "trust (no password)", None
        except (PostgresError, psycopg2.OperationalError) as e:
            error_messages.append(f"Trust auth failed: {str(e)}")
    
    # Second try: with password
    if password:
        try:
            connection_params["password"] = password
            conn = psycopg2.connect(**connection_params)
            return conn, "password authentication", None
        except (PostgresError, psycopg2.OperationalError) as e:
            error_messages.append(f"Password auth failed: {str(e)}")
    
    return None, None, error_messages

def setup_local_postgres():
    """Setup Local PostgreSQL connection"""
    # pylint: disable=global-statement
    global local_postgres_conn, local_postgres_cursor
    
    # Step 1: Check if database exists, create if it doesn't
    default_conn = None
    auth_method = None
    connection_errors = []
    
    # Try connecting to 'postgres' database first to check/create target database
    default_conn, auth_method, errors = try_postgres_connection(
        settings.LOCAL_POSTGRES_HOST,
        settings.LOCAL_POSTGRES_PORT,
        settings.LOCAL_POSTGRES_USER,
        "postgres",
        settings.LOCAL_POSTGRES_PASSWORD if settings.LOCAL_POSTGRES_PASSWORD else None
    )
    if errors:
        connection_errors.extend(errors)
    
    if default_conn:
        try:
            default_conn.autocommit = True
            default_cursor = default_conn.cursor()
            
            # Check if database exists
            default_cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (settings.LOCAL_POSTGRES_DB,)
            )
            db_exists = default_cursor.fetchone()
            
            if not db_exists:
                db_name_quoted = f'"{settings.LOCAL_POSTGRES_DB}"'
                print(f"   Local Database '{settings.LOCAL_POSTGRES_DB}' not found. Creating it...")
                default_cursor.execute(f"CREATE DATABASE {db_name_quoted}")
                print(f"   Local Database '{settings.LOCAL_POSTGRES_DB}' created successfully.")
            else:
                print(f"   Local Database '{settings.LOCAL_POSTGRES_DB}' already exists.")
            
            default_cursor.close()
            default_conn.close()
            
            # Step 2: Connect to the target database
            port_int = int(settings.LOCAL_POSTGRES_PORT) if isinstance(settings.LOCAL_POSTGRES_PORT, str) else settings.LOCAL_POSTGRES_PORT
            connection_params = {
                "host": settings.LOCAL_POSTGRES_HOST,
                "port": port_int,
                "user": settings.LOCAL_POSTGRES_USER,
                "database": settings.LOCAL_POSTGRES_DB
            }
            
            if auth_method == "password authentication":
                connection_params["password"] = settings.LOCAL_POSTGRES_PASSWORD
            local_postgres_conn = psycopg2.connect(**connection_params)
            local_postgres_conn.autocommit = True
            local_postgres_cursor = local_postgres_conn.cursor()
            print(f"✅ Local PostgreSQL: CONNECTED (Database: {settings.LOCAL_POSTGRES_DB}, Auth: {auth_method})")
        except (PostgresError, psycopg2.OperationalError, psycopg2.ProgrammingError) as e:  # pylint: disable=broad-except
            print(f"❌ Local PostgreSQL: Connection established but error occurred - {str(e)}")
            local_postgres_conn = None
            local_postgres_cursor = None
    else:
        print("❌ Local PostgreSQL: NOT CONNECTED")
        if connection_errors:
            print("\n   Error Details:")
            for error in connection_errors:
                print(f"      - {error}")
        local_postgres_conn = None
        local_postgres_cursor = None

def setup_main_postgres():
    """Setup Main Server PostgreSQL connection pool"""
    # pylint: disable=global-statement
    global main_postgres_pool, main_postgres_connected
    
    try:
        port_int = int(settings.MAIN_POSTGRES_PORT) if isinstance(settings.MAIN_POSTGRES_PORT, str) else settings.MAIN_POSTGRES_PORT
        
        # Create connection pool for main server
        main_postgres_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=settings.MAIN_POSTGRES_HOST,
            port=port_int,
            user=settings.MAIN_POSTGRES_USER,
            password=settings.MAIN_POSTGRES_PASSWORD if settings.MAIN_POSTGRES_PASSWORD else None,
            database=settings.MAIN_POSTGRES_DB
        )
        
        # Test connection
        test_conn = main_postgres_pool.getconn()
        test_conn.close()
        main_postgres_pool.putconn(test_conn)
        
        main_postgres_connected = True
        print(f"✅ Main Server PostgreSQL: CONNECTED (Database: {settings.MAIN_POSTGRES_DB})")
    except (PostgresError, psycopg2.OperationalError, psycopg2.pool.PoolError) as e:
        main_postgres_connected = False
        print(f"⚠️  Main Server PostgreSQL: NOT CONNECTED - {str(e)}")
        print("   App will continue running, but synchronization to main server will be unavailable.")
        main_postgres_pool = None

# Setup Local PostgreSQL
setup_local_postgres()

# Setup Main Server PostgreSQL
setup_main_postgres()

# Create the patient table in Local PostgreSQL if connection is successful
if local_postgres_conn and local_postgres_cursor:
    try:
        local_postgres_cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100) NOT NULL,
                name VARCHAR(255) NOT NULL,
                age INTEGER,
                gender VARCHAR(10) NOT NULL,
                phone VARCHAR(50) NOT NULL,
                email VARCHAR(255),
                date_of_birth VARCHAR(50),
                address TEXT,
                registration_date VARCHAR(50),
                referral_source VARCHAR(20) NOT NULL,
                referral_subcategory VARCHAR(255),
                patient_status VARCHAR(30) NOT NULL,
                important_notes TEXT,
                billed_amount DECIMAL(10, 2),
                outstanding_amount DECIMAL(10, 2),
                synced_to_main BOOLEAN DEFAULT FALSE,
                last_synced_at TIMESTAMP,
                UNIQUE(tenant_id, phone)
            )
        """)
        local_postgres_cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_tenant_id ON patients(tenant_id)")
        local_postgres_conn.commit()
        print("   Local patients table created/verified successfully.")
    except (PostgresError, psycopg2.ProgrammingError) as e:
        print(f"   Error creating local patients table: {e}")

# Create the patient table in Main Server PostgreSQL if connection is successful
if main_postgres_connected and main_postgres_pool:
    try:
        main_conn = main_postgres_pool.getconn()
        main_cursor = main_conn.cursor()
        
        main_cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100) NOT NULL,
                name VARCHAR(255) NOT NULL,
                age INTEGER,
                gender VARCHAR(10) NOT NULL,
                phone VARCHAR(50) NOT NULL,
                email VARCHAR(255),
                date_of_birth VARCHAR(50),
                address TEXT,
                registration_date VARCHAR(50),
                referral_source VARCHAR(20) NOT NULL,
                referral_subcategory VARCHAR(255),
                patient_status VARCHAR(30) NOT NULL,
                billed_amount DECIMAL(10, 2),
                outstanding_amount DECIMAL(10, 2),
                synced_to_main BOOLEAN DEFAULT TRUE,
                last_synced_at TIMESTAMP,
                UNIQUE(tenant_id, phone)
            )
        """)
        main_cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_tenant_id ON patients(tenant_id)")
        main_conn.commit()
        main_cursor.close()
        main_postgres_pool.putconn(main_conn)
        print("   Main server patients table created/verified successfully.")
    except (PostgresError, psycopg2.ProgrammingError) as e:
        print(f"   Error creating main server patients table: {e}")

# Synchronization: Local PostgreSQL → Main Server PostgreSQL
def sync_local_to_main():
    """Sync data from Local PostgreSQL to Main Server PostgreSQL"""
    if not (main_postgres_connected and main_postgres_pool and local_postgres_conn and local_postgres_cursor):
        return
    
    try:
        # Get all unsynced patients from local database
        local_postgres_cursor.execute("""
            SELECT id, tenant_id, name, age, gender, phone, email, date_of_birth, address, 
                   registration_date, referral_source, referral_subcategory, patient_status, 
                   billed_amount, outstanding_amount
            FROM patients
            WHERE synced_to_main = FALSE OR synced_to_main IS NULL
        """)
        unsynced_patients = local_postgres_cursor.fetchall()
        
        if not unsynced_patients:
            return
        
        columns = ["id", "tenant_id", "name", "age", "gender", "phone", "email", "date_of_birth", 
                "address", "registration_date", "referral_source", "referral_subcategory", 
                "patient_status", "billed_amount", "outstanding_amount"]
        
        sync_conn = main_postgres_pool.getconn()
        sync_cursor = sync_conn.cursor()
        
        synced_count = 0
        try:
            for patient_row in unsynced_patients:
                patient_dict = dict(zip(columns, patient_row))
                patient_id = patient_dict["id"]
                tenant_id = patient_dict["tenant_id"]
                
                try:
                    # Insert or update in main server (upsert)
                    sync_cursor.execute("""
                        INSERT INTO patients (tenant_id, name, age, gender, phone, email, date_of_birth, 
                                            address, registration_date, referral_source, referral_subcategory,
                                            patient_status, billed_amount, outstanding_amount, 
                                            synced_to_main, last_synced_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
                        ON CONFLICT (tenant_id, phone) 
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            age = EXCLUDED.age,
                            gender = EXCLUDED.gender,
                            email = EXCLUDED.email,
                            date_of_birth = EXCLUDED.date_of_birth,
                            address = EXCLUDED.address,
                            registration_date = EXCLUDED.registration_date,
                            referral_source = EXCLUDED.referral_source,
                            referral_subcategory = EXCLUDED.referral_subcategory,
                            patient_status = EXCLUDED.patient_status,
                            billed_amount = EXCLUDED.billed_amount,
                            outstanding_amount = EXCLUDED.outstanding_amount,
                            synced_to_main = TRUE,
                            last_synced_at = EXCLUDED.last_synced_at
                    """, (
                        tenant_id, patient_dict["name"], patient_dict["age"], patient_dict["gender"],
                        patient_dict["phone"], patient_dict["email"], patient_dict["date_of_birth"],
                        patient_dict["address"], patient_dict["registration_date"], 
                        patient_dict["referral_source"], patient_dict["referral_subcategory"],
                        patient_dict["patient_status"], patient_dict["billed_amount"], 
                        patient_dict["outstanding_amount"], datetime.now()
                    ))
                    
                    # Mark as synced in local database
                    local_postgres_cursor.execute("""
                        UPDATE patients 
                        SET synced_to_main = TRUE, last_synced_at = %s
                        WHERE id = %s
                    """, (datetime.now(), patient_id))
                    
                    synced_count += 1
                except (PostgresError, psycopg2.IntegrityError, psycopg2.OperationalError) as e:
                    print(f"   ⚠️  Failed to sync patient ID {patient_id} to main server: {e}")
            
            sync_conn.commit()
        finally:
            sync_cursor.close()
            main_postgres_pool.putconn(sync_conn)
        
        local_postgres_conn.commit()
        
        if synced_count > 0:
            print(f"   ✅ Synced {synced_count} patient(s) from Local → Main Server.")
    except (PostgresError, psycopg2.OperationalError, psycopg2.pool.PoolError) as e:
        print(f"   ⚠️  Error syncing Local → Main Server: {e}")

# Initialize Prisma client if available
if prisma_client:
    try:
        prisma_client.connect()
        print("✅ Prisma: CONNECTED")
    except (RuntimeError, ConnectionError, AttributeError) as e:
        print(f"⚠️  Prisma: Connection failed - {e}")
        prisma_client = None

# Run initial sync on startup
if main_postgres_connected and local_postgres_cursor:
    sync_local_to_main()

# Final status summary
print("="*60)
if local_postgres_cursor and main_postgres_connected:
    prisma_status = "✅" if prisma_client else "⚠️"
    print(f"{prisma_status} Both Local and Main Server databases are connected. App is fully operational.")
elif local_postgres_cursor:
    prisma_status = "✅" if prisma_client else "⚠️"
    print(f"{prisma_status} Local PostgreSQL is connected. Main Server sync unavailable.")
else:
    print("❌ Local PostgreSQL is not connected. App will run but data operations will fail.")
    print("   Please check your database connections and restart the app.")
print("="*60 + "\n")

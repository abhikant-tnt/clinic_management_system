"""Database connection and table setup for Local and Main Server PostgreSQL"""
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from app.core.config import settings
import os
from datetime import datetime
from typing import Optional

# Set DATABASE_URL for Prisma
try:
    os.environ["DATABASE_URL"] = settings.DATABASE_URL
except ValueError as e:
    print(f"⚠️  {e} - Prisma unavailable until password configured")

# Prisma client setup
prisma_client = None
try:
    from prisma import Prisma
    prisma_client = Prisma()
except (ImportError, AttributeError, RuntimeError, ValueError) as e:
    msg = "Prisma not installed. Run: pip install prisma" if isinstance(e, ImportError) else f"Prisma error: {e}"
    print(f"⚠️  {msg}")
    prisma_client = None

print("\n" + "="*60)
print("DATABASE CONNECTION STATUS")
print("="*60)
print(f"Tenant ID: {settings.TENANT_ID}")
print(f"Local: {settings.LOCAL_POSTGRES_HOST}:{settings.LOCAL_POSTGRES_PORT}, User: {settings.LOCAL_POSTGRES_USER}, DB: {settings.LOCAL_POSTGRES_DB}")
print(f"Main: {settings.MAIN_POSTGRES_HOST}:{settings.MAIN_POSTGRES_PORT}, User: {settings.MAIN_POSTGRES_USER}, DB: {settings.MAIN_POSTGRES_DB}")

# Local PostgreSQL database setup
local_postgres_conn = None
local_postgres_cursor = None

# Main Server PostgreSQL connection pool
main_postgres_pool: Optional[SimpleConnectionPool] = None
main_postgres_connected = False

def try_postgres_connection(host: str, port: str, user: str, database: str, password: Optional[str] = None):
    """Try PostgreSQL connection: trust auth first, then password auth"""
    params = {"host": host, "port": int(port) if isinstance(port, str) else port, "user": user, "database": database}
    errors = []
    
    if not password:
        try:
            return psycopg2.connect(**params), "trust (no password)", None
        except Exception as e:  # pylint: disable=broad-except
            errors.append(f"Trust auth failed: {str(e)}")
    
    if password:
        try:
            return psycopg2.connect(**{**params, "password": password}), "password authentication", None
        except Exception as e:  # pylint: disable=broad-except
            errors.append(f"Password auth failed: {str(e)}")
    
    return None, None, errors

def setup_local_postgres():
    """Setup Local PostgreSQL connection"""
    # pylint: disable=global-statement
    global local_postgres_conn, local_postgres_cursor
    
    default_conn, auth_method, errors = try_postgres_connection(
        settings.LOCAL_POSTGRES_HOST, settings.LOCAL_POSTGRES_PORT,
        settings.LOCAL_POSTGRES_USER, "postgres", settings.LOCAL_POSTGRES_PASSWORD or None
    )
    
    if not default_conn:
        print("❌ Local PostgreSQL: NOT CONNECTED")
    if errors:
            print("\n   Error Details:")
            for error in errors:
                print(f"      - {error}")
        local_postgres_conn = local_postgres_cursor = None
        return
    
        try:
            default_conn.autocommit = True
        cursor = default_conn.cursor()
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.LOCAL_POSTGRES_DB,))
        
        if not cursor.fetchone():
            print(f"   Creating database '{settings.LOCAL_POSTGRES_DB}'...")
            cursor.execute(f'CREATE DATABASE "{settings.LOCAL_POSTGRES_DB}"')
            print("   Database created successfully.")
            
        cursor.close()
            default_conn.close()
            
        params = {
                "host": settings.LOCAL_POSTGRES_HOST,
            "port": int(settings.LOCAL_POSTGRES_PORT) if isinstance(settings.LOCAL_POSTGRES_PORT, str) else settings.LOCAL_POSTGRES_PORT,
                "user": settings.LOCAL_POSTGRES_USER,
                "database": settings.LOCAL_POSTGRES_DB
            }
        if auth_method == "password authentication":
            params["password"] = settings.LOCAL_POSTGRES_PASSWORD
            
        local_postgres_conn = psycopg2.connect(**params)
            local_postgres_conn.autocommit = True
            local_postgres_cursor = local_postgres_conn.cursor()
        print(f"✅ Local PostgreSQL: CONNECTED (DB: {settings.LOCAL_POSTGRES_DB}, Auth: {auth_method})")
        except Exception as e:  # pylint: disable=broad-except
        print(f"❌ Local PostgreSQL: Error - {str(e)}")
        local_postgres_conn = local_postgres_cursor = None

def setup_main_postgres():
    """Setup Main Server PostgreSQL connection pool"""
    # pylint: disable=global-statement
    global main_postgres_pool, main_postgres_connected
    
    try:
        main_postgres_pool = SimpleConnectionPool(
            minconn=1, maxconn=5,
            host=settings.MAIN_POSTGRES_HOST,
            port=int(settings.MAIN_POSTGRES_PORT) if isinstance(settings.MAIN_POSTGRES_PORT, str) else settings.MAIN_POSTGRES_PORT,
            user=settings.MAIN_POSTGRES_USER,
            password=settings.MAIN_POSTGRES_PASSWORD or None,
            database=settings.MAIN_POSTGRES_DB
        )
        test_conn = main_postgres_pool.getconn()
        test_conn.close()
        main_postgres_pool.putconn(test_conn)
        main_postgres_connected = True
        print(f"✅ Main Server PostgreSQL: CONNECTED (DB: {settings.MAIN_POSTGRES_DB})")
    except Exception as e:  # pylint: disable=broad-except
        main_postgres_connected = False
        main_postgres_pool = None
        print(f"⚠️  Main Server PostgreSQL: NOT CONNECTED - {str(e)}")
        print("   App continues but sync unavailable.")

def create_table(cursor, table_sql: str, indexes: list, table_name: str):
    """Create table and indexes"""
    try:
        cursor.execute(table_sql)
        for idx in indexes:
            cursor.execute(idx)
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"   Error creating {table_name} table: {e}")
        return False

def add_columns_if_missing(cursor, columns: list):
    """Add columns if they don't exist"""
    for col_sql in columns:
        try:
            cursor.execute(col_sql)
        except Exception:  # pylint: disable=broad-except
            pass

# Setup connections
setup_local_postgres()
setup_main_postgres()

# Table definitions
PATIENTS_TABLE_LOCAL = """
    CREATE TABLE IF NOT EXISTS patients (
        id SERIAL PRIMARY KEY, tenant_id VARCHAR(100) NOT NULL, name VARCHAR(255) NOT NULL,
        age INTEGER, gender VARCHAR(10) NOT NULL, phone VARCHAR(50) NOT NULL, email VARCHAR(255),
        date_of_birth VARCHAR(50), address TEXT, registration_date VARCHAR(50),
        referral_source VARCHAR(20) NOT NULL, referral_subcategory VARCHAR(255),
        patient_status VARCHAR(30) NOT NULL, important_notes TEXT,
        billed_amount DECIMAL(10, 2), outstanding_amount DECIMAL(10, 2),
        synced_to_main BOOLEAN DEFAULT FALSE, last_synced_at TIMESTAMP,
        UNIQUE(tenant_id, phone)
    )
"""

PATIENTS_TABLE_MAIN = PATIENTS_TABLE_LOCAL.replace("synced_to_main BOOLEAN DEFAULT FALSE", "synced_to_main BOOLEAN DEFAULT TRUE")

VISITS_TABLE = """
    CREATE TABLE IF NOT EXISTS visits (
        id SERIAL PRIMARY KEY, patient_id INTEGER NOT NULL, tenant_id VARCHAR(100) NOT NULL,
        visit_date VARCHAR(50) NOT NULL, visit_time VARCHAR(10), notes TEXT, diagnosis TEXT,
        treatment TEXT, visit_status VARCHAR(20) DEFAULT 'Completed', doctor_name VARCHAR(255),
        visit_charge DECIMAL(10, 2) DEFAULT 0, medication_charge DECIMAL(10, 2) DEFAULT 0,
        total_charge DECIMAL(10, 2) DEFAULT 0, is_waived BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        synced_to_main BOOLEAN DEFAULT {}, last_synced_at TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
    )
"""

PATIENT_DOCS_TABLE = """
    CREATE TABLE IF NOT EXISTS patient_documents (
        id SERIAL PRIMARY KEY, patient_id INTEGER NOT NULL, tenant_id VARCHAR(100) NOT NULL,
        filename VARCHAR(255) NOT NULL, description TEXT, file_type VARCHAR(50) NOT NULL,
        file_size BIGINT NOT NULL, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        synced_to_main BOOLEAN DEFAULT {}, last_synced_at TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
    )
"""

VISIT_CHARGE_COLS = [
    "ALTER TABLE visits ADD COLUMN IF NOT EXISTS visit_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE visits ADD COLUMN IF NOT EXISTS medication_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE visits ADD COLUMN IF NOT EXISTS total_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE visits ADD COLUMN IF NOT EXISTS is_waived BOOLEAN DEFAULT FALSE"
]

# Create tables in Local PostgreSQL
if local_postgres_conn and local_postgres_cursor:
    if create_table(local_postgres_cursor, PATIENTS_TABLE_LOCAL, 
                   ["CREATE INDEX IF NOT EXISTS idx_patients_tenant_id ON patients(tenant_id)"], "local patients"):
        local_postgres_conn.commit()
        print("   Local patients table created/verified successfully.")
    
    if create_table(local_postgres_cursor, VISITS_TABLE.format("FALSE"),
                   ["CREATE INDEX IF NOT EXISTS idx_visits_patient_id ON visits(patient_id)",
                    "CREATE INDEX IF NOT EXISTS idx_visits_tenant_id ON visits(tenant_id)",
                    "CREATE INDEX IF NOT EXISTS idx_visits_visit_date ON visits(visit_date)"], "local visits"):
        add_columns_if_missing(local_postgres_cursor, VISIT_CHARGE_COLS)
        local_postgres_conn.commit()
        print("   Local visits table created/verified successfully.")
    
    if create_table(local_postgres_cursor, PATIENT_DOCS_TABLE.format("FALSE"),
                   ["CREATE INDEX IF NOT EXISTS idx_patient_documents_patient_id ON patient_documents(patient_id)",
                    "CREATE INDEX IF NOT EXISTS idx_patient_documents_tenant_id ON patient_documents(tenant_id)",
                    "CREATE INDEX IF NOT EXISTS idx_patient_documents_uploaded_at ON patient_documents(uploaded_at)"], "local patient_documents"):
        local_postgres_conn.commit()
        print("   Local patient_documents table created/verified successfully.")

# Create tables in Main Server PostgreSQL
if main_postgres_connected and main_postgres_pool:
    try:
        main_conn = main_postgres_pool.getconn()
        main_cursor = main_conn.cursor()
        
        if create_table(main_cursor, PATIENTS_TABLE_MAIN,
                       ["CREATE INDEX IF NOT EXISTS idx_patients_tenant_id ON patients(tenant_id)"], "main patients"):
            main_conn.commit()
            print("   Main server patients table created/verified successfully.")
        
        if create_table(main_cursor, VISITS_TABLE.format("TRUE"),
                       ["CREATE INDEX IF NOT EXISTS idx_visits_patient_id ON visits(patient_id)",
                        "CREATE INDEX IF NOT EXISTS idx_visits_tenant_id ON visits(tenant_id)",
                        "CREATE INDEX IF NOT EXISTS idx_visits_visit_date ON visits(visit_date)"], "main visits"):
            add_columns_if_missing(main_cursor, VISIT_CHARGE_COLS)
            main_conn.commit()
            print("   Main server visits table created/verified successfully.")
        
        if create_table(main_cursor, PATIENT_DOCS_TABLE.format("TRUE"),
                       ["CREATE INDEX IF NOT EXISTS idx_patient_documents_patient_id ON patient_documents(patient_id)",
                        "CREATE INDEX IF NOT EXISTS idx_patient_documents_tenant_id ON patient_documents(tenant_id)",
                        "CREATE INDEX IF NOT EXISTS idx_patient_documents_uploaded_at ON patient_documents(uploaded_at)"], "main patient_documents"):
        main_conn.commit()
            print("   Main server patient_documents table created/verified successfully.")
        
        main_cursor.close()
        main_postgres_pool.putconn(main_conn)
    except Exception as e:  # pylint: disable=broad-except
        print(f"   Error creating main server tables: {e}")


def sync_local_to_main():
    """Sync unsynced patients from Local → Main Server"""
    if not (main_postgres_connected and main_postgres_pool and local_postgres_conn and local_postgres_cursor):
        return
    
    try:
        local_postgres_cursor.execute("""
            SELECT id, tenant_id, name, age, gender, phone, email, date_of_birth, address, 
                   registration_date, referral_source, referral_subcategory, patient_status, 
                   important_notes, billed_amount, outstanding_amount
            FROM patients WHERE synced_to_main = FALSE OR synced_to_main IS NULL
        """)
        unsynced = local_postgres_cursor.fetchall()
        if not unsynced:
            return
        
        columns = ["id", "tenant_id", "name", "age", "gender", "phone", "email", "date_of_birth", 
                "address", "registration_date", "referral_source", "referral_subcategory", 
                  "patient_status", "important_notes", "billed_amount", "outstanding_amount"]
        
        sync_conn = main_postgres_pool.getconn()
        sync_cursor = sync_conn.cursor()
        synced_count = 0
        now = datetime.now()
        
        try:
            for row in unsynced:
                p = dict(zip(columns, row))
                try:
                    sync_cursor.execute("""
                        INSERT INTO patients (tenant_id, name, age, gender, phone, email, date_of_birth, 
                                            address, registration_date, referral_source, referral_subcategory,
                                            patient_status, important_notes, billed_amount, outstanding_amount, 
                                            synced_to_main, last_synced_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
                        ON CONFLICT (tenant_id, phone) 
                        DO UPDATE SET name=EXCLUDED.name, age=EXCLUDED.age, gender=EXCLUDED.gender,
                            email=EXCLUDED.email, date_of_birth=EXCLUDED.date_of_birth, address=EXCLUDED.address,
                            registration_date=EXCLUDED.registration_date, referral_source=EXCLUDED.referral_source,
                            referral_subcategory=EXCLUDED.referral_subcategory, patient_status=EXCLUDED.patient_status,
                            important_notes=EXCLUDED.important_notes, billed_amount=EXCLUDED.billed_amount,
                            outstanding_amount=EXCLUDED.outstanding_amount, synced_to_main=TRUE,
                            last_synced_at=EXCLUDED.last_synced_at
                    """, (p["tenant_id"], p["name"], p["age"], p["gender"], p["phone"], p["email"], 
                         p["date_of_birth"], p["address"], p["registration_date"], p["referral_source"],
                         p["referral_subcategory"], p["patient_status"], p["important_notes"], 
                         p["billed_amount"], p["outstanding_amount"], now))
                    local_postgres_cursor.execute(
                        "UPDATE patients SET synced_to_main=TRUE, last_synced_at=%s WHERE id=%s", (now, p["id"])
                    )
                    synced_count += 1
                except Exception as e:  # pylint: disable=broad-except
                    print(f"   ⚠️  Failed to sync patient ID {p['id']}: {e}")
            
            sync_conn.commit()
        finally:
            sync_cursor.close()
            main_postgres_pool.putconn(sync_conn)
        
        local_postgres_conn.commit()
        if synced_count > 0:
            print(f"   ✅ Synced {synced_count} patient(s) from Local → Main Server.")
    except Exception as e:  # pylint: disable=broad-except
        print(f"   ⚠️  Error syncing Local → Main Server: {e}")

# Initialize Prisma
if prisma_client:
    try:
        prisma_client.connect()
        print("✅ Prisma: CONNECTED")
    except Exception as e:  # pylint: disable=broad-except
        print(f"⚠️  Prisma: Connection failed - {e}")
        prisma_client = None

# Initial sync and file storage
if main_postgres_connected and local_postgres_cursor:
    sync_local_to_main()

try:
    from app.core.storage import ensure_uploads_directory
    ensure_uploads_directory()
    print("✅ File storage directory initialized")
except Exception as e:  # pylint: disable=broad-except
    print(f"⚠️  File storage warning: {e}")

# Final status
print("="*60)
prisma_status = "✅" if prisma_client else "⚠️"
if local_postgres_cursor and main_postgres_connected:
    print(f"{prisma_status} Both databases connected. App fully operational.")
elif local_postgres_cursor:
    print(f"{prisma_status} Local PostgreSQL connected. Main Server sync unavailable.")
else:
    print("❌ Local PostgreSQL not connected. Data operations will fail.")
print("="*60 + "\n")

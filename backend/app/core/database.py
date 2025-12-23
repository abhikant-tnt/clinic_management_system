"""Database connection and table setup for PostgreSQL"""
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from app.core.config import settings
from typing import Optional

from app.modules.billing.tables import (
    BILLING_INVOICES_TABLE,
    BILLING_ITEMS_TABLE,
    BILLING_INVOICES_INDEXES,
    BILLING_ITEMS_INDEXES
)
from app.modules.inventory.tables import (
    INVENTORY_ITEMS_TABLE,
    INVENTORY_ITEMS_INDEXES
)

postgres_pool: Optional[SimpleConnectionPool] = None
postgres_connected = False

def try_postgres_connection(host: str, port: str, user: str, database: str, password: Optional[str] = None):
    """Try PostgreSQL connection: trust auth first, then password auth"""
    params = {"host": host, "port": int(port) if isinstance(port, str) else port, "user": user, "database": database}
    errors = []
    
    if not password:
        try:
            return psycopg2.connect(**params), "trust (no password)", None
        except Exception as e:
            errors.append(f"Trust auth failed: {str(e)}")
    
    if password:
        try:
            return psycopg2.connect(**{**params, "password": password}), "password authentication", None
        except Exception as e:
            errors.append(f"Password auth failed: {str(e)}")
    
    return None, None, errors

def setup_postgres():
    """Setup PostgreSQL connection pool"""
    global postgres_pool, postgres_connected
    
    default_conn, auth_method, errors = try_postgres_connection(
        settings.MAIN_POSTGRES_HOST, settings.MAIN_POSTGRES_PORT,
        settings.MAIN_POSTGRES_USER, "postgres", settings.MAIN_POSTGRES_PASSWORD or None
    )
    
    if default_conn:
        try:
            default_conn.autocommit = True
            cursor = default_conn.cursor()
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.MAIN_POSTGRES_DB,))
            
            if not cursor.fetchone():
                cursor.execute(f'CREATE DATABASE "{settings.MAIN_POSTGRES_DB}"')
            cursor.close()
            default_conn.close()
        except Exception as e:
            pass
    
    try:
        postgres_pool = SimpleConnectionPool(
            minconn=1, maxconn=5,
            host=settings.MAIN_POSTGRES_HOST,
            port=int(settings.MAIN_POSTGRES_PORT) if isinstance(settings.MAIN_POSTGRES_PORT, str) else settings.MAIN_POSTGRES_PORT,
            user=settings.MAIN_POSTGRES_USER,
            password=settings.MAIN_POSTGRES_PASSWORD or None,
            database=settings.MAIN_POSTGRES_DB
        )
        test_conn = postgres_pool.getconn()
        test_conn.close()
        postgres_pool.putconn(test_conn)
        postgres_connected = True
    except Exception:
        postgres_connected = False
        postgres_pool = None

def create_table(cursor, table_sql: str, indexes: list, table_name: str):
    """Create table and indexes. Returns (success, was_created)"""
    try:
        import re
        match = re.search(r'CREATE TABLE IF NOT EXISTS\s+(\w+)', table_sql, re.IGNORECASE)
        table_name_from_sql = match.group(1) if match else None
        
        table_exists = False
        if table_name_from_sql:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name_from_sql,))
            table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            cursor.execute(table_sql)
        
        if not table_exists:
            for idx in indexes:
                try:
                    cursor.execute(idx)
                except Exception:
                    pass
        
        return (True, not table_exists)
    except Exception as e:
        return (False, False)

def add_columns_if_missing(cursor, columns: list):
    """Add columns if they don't exist"""
    for col_sql in columns:
        try:
            cursor.execute(col_sql)
        except Exception:
            pass

def ensure_tables_exist():
    """Ensure all tables exist - useful after tables are dropped"""
    if not (postgres_connected and postgres_pool):
        return False
    
    try:
        conn = postgres_pool.getconn()
        cursor = conn.cursor()
        for tbl_name, tbl_sql, tbl_indexes, tbl_extra_cols in TABLE_CONFIGS:
            success, _ = create_table(cursor, tbl_sql, tbl_indexes, tbl_name)
            if success:
                if tbl_extra_cols:
                    add_columns_if_missing(cursor, tbl_extra_cols)
            conn.commit()
        cursor.close()
        postgres_pool.putconn(conn)
        return True
    except Exception as e:
        return False

setup_postgres()

PATIENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS patients_table (
        id SERIAL PRIMARY KEY, tenant_id VARCHAR(100) NOT NULL,
        title VARCHAR(10) NOT NULL, firstname VARCHAR(255) NOT NULL, lastname VARCHAR(255) NOT NULL,
        dob VARCHAR(50) NOT NULL, age INTEGER NOT NULL,
        gender VARCHAR(10) NOT NULL, phone VARCHAR(10) NOT NULL, email VARCHAR(255),
        primary_doctor VARCHAR(255),
        address1 TEXT NOT NULL, address2 TEXT, country VARCHAR(100),
        city VARCHAR(100) NOT NULL, state VARCHAR(100) NOT NULL, pincode VARCHAR(10) NOT NULL,
        emergency_contact_name VARCHAR(255) NOT NULL, emergency_contact_phone VARCHAR(10) NOT NULL,
        referral_source VARCHAR(20) NOT NULL, referral_subcategory VARCHAR(255),
        important_notes TEXT, patient_status VARCHAR(30) NOT NULL,
        last_visit_date VARCHAR(50), registration_date VARCHAR(50) NOT NULL,
        purpose VARCHAR(20),
        past_medical_record TEXT DEFAULT 'None',
        dermatological_history TEXT DEFAULT 'None',
        medications TEXT DEFAULT 'None',
        surgeries TEXT DEFAULT 'None',
        hormonal_issues TEXT DEFAULT 'None',
        UNIQUE(tenant_id, phone)
    )
"""

STAFF_TABLE = """
    CREATE TABLE IF NOT EXISTS staff (
        id SERIAL PRIMARY KEY, tenant_id VARCHAR(100) NOT NULL,
        firstname VARCHAR(255) NOT NULL, lastname VARCHAR(255) NOT NULL,
        speciality VARCHAR(255), phone VARCHAR(10) NOT NULL,
        username VARCHAR(100), password_hash VARCHAR(255),
        user_type VARCHAR(20) DEFAULT 'staff',
        is_active BOOLEAN DEFAULT TRUE,
        last_login TIMESTAMP
    )
"""

PATIENT_DOCS_TABLE = """
    CREATE TABLE IF NOT EXISTS patient_documents (
        id SERIAL PRIMARY KEY, patient_id INTEGER NOT NULL, tenant_id VARCHAR(100) NOT NULL,
        filename VARCHAR(255) NOT NULL, description TEXT, file_type VARCHAR(50) NOT NULL,
        file_size BIGINT NOT NULL, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients_table(id) ON DELETE CASCADE
    )
"""

APPOINTMENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS appointments (
        id SERIAL PRIMARY KEY, patient_id INTEGER NOT NULL, tenant_id VARCHAR(100) NOT NULL,
        appointment_date VARCHAR(50) NOT NULL, appointment_time VARCHAR(10),
        appointment_status VARCHAR(30) DEFAULT 'first time appointment', 
        doctor_id INTEGER NOT NULL, doctor_name VARCHAR(255),
        appointment_type VARCHAR(50), notes TEXT, payment_pending BOOLEAN DEFAULT FALSE,
        follow_up_date VARCHAR(50), diagnosis TEXT, treatment TEXT,
        visit_charge DECIMAL(10, 2) DEFAULT 0, medication_charge DECIMAL(10, 2) DEFAULT 0,
        total_charge DECIMAL(10, 2) DEFAULT 0, is_waived BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients_table(id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES staff(id) ON DELETE SET NULL
    )
"""

APPOINTMENT_CLINICAL_COLS = [
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS doctor_id INTEGER",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS diagnosis TEXT",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS treatment TEXT",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS visit_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS medication_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS total_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS is_waived BOOLEAN DEFAULT FALSE"
]

TABLE_CONFIGS = [
    ("staff", STAFF_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_staff_tenant_id ON staff(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_staff_phone ON staff(phone)",
        "CREATE INDEX IF NOT EXISTS idx_staff_username ON staff(username)",
        "CREATE INDEX IF NOT EXISTS idx_staff_user_type ON staff(user_type)"
    ], [
        "ALTER TABLE staff ADD COLUMN IF NOT EXISTS username VARCHAR(100)",
        "ALTER TABLE staff ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
        "ALTER TABLE staff ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT 'staff'",
        "ALTER TABLE staff ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE staff ADD COLUMN IF NOT EXISTS last_login TIMESTAMP"
    ]),
    ("patients_table", PATIENTS_TABLE, ["CREATE INDEX IF NOT EXISTS idx_patients_tenant_id ON patients_table(tenant_id)"], None),
    ("patient_documents", PATIENT_DOCS_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_patient_id ON patient_documents(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_tenant_id ON patient_documents(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_uploaded_at ON patient_documents(uploaded_at)"
    ], None),
    ("appointments", APPOINTMENTS_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_tenant_id ON appointments(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_doctor_id ON appointments(doctor_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_appointment_date ON appointments(appointment_date)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_appointment_status ON appointments(appointment_status)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_doctor_name ON appointments(doctor_name)"
    ], APPOINTMENT_CLINICAL_COLS),
    ("inventory_items", INVENTORY_ITEMS_TABLE, INVENTORY_ITEMS_INDEXES, None),
    ("billing_invoices", BILLING_INVOICES_TABLE, BILLING_INVOICES_INDEXES, None),
    ("billing_items", BILLING_ITEMS_TABLE, BILLING_ITEMS_INDEXES, None)
]

# Create tables in PostgreSQL
if postgres_connected and postgres_pool:
    try:
        conn = postgres_pool.getconn()
        cursor = conn.cursor()
        
        # Enable UUID extension if not already enabled (try both pgcrypto and uuid-ossp)
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            conn.commit()
        except Exception:
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
                conn.commit()
            except Exception:
                pass
        
        for tbl_name, tbl_sql, tbl_indexes, tbl_extra_cols in TABLE_CONFIGS:
            try:
                success, was_created = create_table(cursor, tbl_sql, [], tbl_name)
                if success:
                    if tbl_extra_cols:
                        for col_sql in tbl_extra_cols:
                            try:
                                cursor.execute(col_sql)
                            except Exception:
                                pass
                    
                    if tbl_name == "staff":
                        try:
                            cursor.execute("""
                                SELECT COUNT(*) FROM pg_constraint 
                                WHERE conrelid = 'staff'::regclass 
                                AND conname = 'staff_tenant_id_username_key'
                            """)
                            constraint_exists = cursor.fetchone()[0] > 0
                            if not constraint_exists:
                                cursor.execute("""
                                    ALTER TABLE staff 
                                    ADD CONSTRAINT staff_tenant_id_username_key 
                                    UNIQUE (tenant_id, username)
                                """)
                        except Exception:
                            pass
                    
                    if tbl_indexes:
                        for idx_sql in tbl_indexes:
                            try:
                                cursor.execute(idx_sql)
                            except Exception:
                                pass
                    conn.commit()
                else:
                    conn.rollback()
            except Exception as e:
                conn.rollback()
                continue
        cursor.close()
        postgres_pool.putconn(conn)
    except Exception:
        pass

postgres_conn = None
postgres_cursor = None

if postgres_connected and postgres_pool:
    try:
        postgres_conn = postgres_pool.getconn()
        postgres_conn.autocommit = True
        postgres_cursor = postgres_conn.cursor()
    except Exception as e:
        pass

try:
    from app.core.db_session import SessionLocal, init_db
    db_session = SessionLocal()
    init_db()
except Exception:
    db_session = None

try:
    from app.core.storage import ensure_uploads_directory
    ensure_uploads_directory()
except Exception:
    pass

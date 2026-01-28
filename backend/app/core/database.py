"""Database connection and table setup for PostgreSQL"""
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extensions import connection, cursor
from app.core.config import settings
from typing import Optional, Tuple, Any, List


from app.modules.inventory.tables import (
    INVENTORY_ITEMS_TABLE,
    INVENTORY_ITEMS_INDEXES
)

postgres_pool: Optional[SimpleConnectionPool] = None
postgres_connected = False

def try_postgres_connection(host: str, port: str, user: str, database: str, password: Optional[str] = None) -> Tuple[Optional[connection], Optional[str], Optional[List[str]]]:
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

def setup_postgres() -> None:
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
            # Database creation failed - log but don't raise (non-critical)
            print(f"Warning: Could not create database: {e}")
    
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
    except Exception as e:
        postgres_connected = False
        postgres_pool = None
        print(f"Error: Failed to setup PostgreSQL connection pool: {e}")

def create_table(cursor: Any, table_sql: str, indexes: List[str], table_name: str) -> Tuple[bool, bool]:
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
                except Exception as e:
                    # Index creation failed - log but continue
                    print(f"Warning: Could not create index: {e}")
        
        return (True, not table_exists)
    except Exception as e:
        return (False, False)

def add_columns_if_missing(cursor: Any, columns: List[str]) -> None:
    """Add columns if they don't exist"""
    for col_sql in columns:
        try:
            cursor.execute(col_sql)
        except Exception as e:
            # Column addition failed - log but continue
            print(f"Warning: Could not add column: {e}")

def ensure_tables_exist() -> bool:
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
        firstname VARCHAR(255) NOT NULL, lastname VARCHAR(255) NOT NULL,
        dob DATE NOT NULL, age INTEGER NOT NULL,
        gender VARCHAR(10) NOT NULL, phone VARCHAR(10) NOT NULL, 
        email VARCHAR(255) NOT NULL,
        primary_doctor INTEGER,
        blood_group VARCHAR(10),
        status VARCHAR(30) NOT NULL,
        vip BOOLEAN DEFAULT FALSE,
        address1 TEXT NOT NULL, address2 TEXT, 
        country VARCHAR(100), country2 VARCHAR(100),
        city VARCHAR(100), city2 VARCHAR(100),
        state VARCHAR(100), state2 VARCHAR(100),
        pincode VARCHAR(10), pincode2 VARCHAR(10),
        image VARCHAR(255) DEFAULT 'None',
        emergency_contact_name VARCHAR(255),
        emergency_contact_phone VARCHAR(10),
        referral_source VARCHAR(20),
        referral_subcategory VARCHAR(255),
        patient_status VARCHAR(30),
        registration_date DATE NOT NULL,
        past_medical_record TEXT DEFAULT 'None',
        dermatological_history TEXT DEFAULT 'None',
        medications TEXT DEFAULT 'None',
        surgeries TEXT DEFAULT 'None',
        hormonal_issues TEXT DEFAULT 'None',
        allergies TEXT DEFAULT 'None',
        lifestyle_assessment TEXT DEFAULT 'None',
        billing_firstname VARCHAR(255),
        billing_lastname VARCHAR(255),
        billing_email VARCHAR(255),
        billing_gstin VARCHAR(50),
        billing_phone VARCHAR(10),
        billing_address1 TEXT,
        billing_address2 TEXT,
        billing_country VARCHAR(100),
        billing_country2 VARCHAR(100),
        billing_state VARCHAR(100),
        billing_state2 VARCHAR(100),
        billing_city VARCHAR(100),
        billing_city2 VARCHAR(100),
        billing_pincode VARCHAR(10),
        billing_pincode2 VARCHAR(10),
        billing_name VARCHAR(255),
        billing_address TEXT,
        UNIQUE(tenant_id, phone)
    )
"""

USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
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
        appointment_date DATE NOT NULL, appointment_time TIME,
        status VARCHAR(30) DEFAULT 'Scheduled',
        doctor_id INTEGER NOT NULL, doctor_name VARCHAR(255),
        purpose VARCHAR(50), payment VARCHAR(20) DEFAULT 'Pending',
        interval VARCHAR(20), follow_up_date DATE,
        FOREIGN KEY (patient_id) REFERENCES patients_table(id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
    )
"""

PRESCRIPTIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS prescriptions (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        appointment_id INTEGER NOT NULL,
        bill_date DATE NOT NULL DEFAULT CURRENT_DATE,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE
    )
"""

PRESCRIPTION_ITEMS_TABLE = """
    CREATE TABLE IF NOT EXISTS prescription_items (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        prescription_id INTEGER NOT NULL,
        item_type VARCHAR(20) NOT NULL,
        source VARCHAR(20) NOT NULL,
        item_name TEXT NOT NULL,
        quantity TEXT,
        inventory_item_id INTEGER,
        FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id) ON DELETE SET NULL
    )
"""
PROCEDURE_ROOMS_TABLE = """
    CREATE TABLE IF NOT EXISTS procedure_rooms (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        room_number VARCHAR(100) NOT NULL,
        room_type VARCHAR(100),
        is_available BOOLEAN DEFAULT TRUE
    )
"""

MACHINES_TABLE = """
    CREATE TABLE IF NOT EXISTS machines (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        name VARCHAR(255) NOT NULL,
        status VARCHAR(100),
        room_id INTEGER REFERENCES procedure_rooms(id) ON DELETE SET NULL
    )
"""
BILLING_INVOICES_TABLE = """
    CREATE TABLE IF NOT EXISTS billing_invoices (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        invoice_number TEXT NOT NULL UNIQUE,
        patient_id INTEGER NOT NULL,
        appointment_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        issue_date DATE NOT NULL,
        purpose TEXT NOT NULL,
        total_amount NUMERIC(12,2) NOT NULL,
        outstanding_amount NUMERIC(12,2) GENERATED ALWAYS AS ((total_amount + tax_amount + adjustments) - discount_amount - amount_paid) STORED,
        status TEXT NOT NULL,
        amount_paid NUMERIC(12,2) NOT NULL,
        payment_mode VARCHAR(20),
        discount_amount NUMERIC(12,2) NOT NULL,
        coupon_code TEXT,
        tax_amount NUMERIC(12,2) NOT NULL,
        gst_percentage NUMERIC(5,2) NOT NULL,
        adjustments NUMERIC(12,2) NOT NULL,
        visit_charge NUMERIC(10,2) DEFAULT 0,
        medication_charge NUMERIC(10,2) DEFAULT 0,
        FOREIGN KEY (patient_id) REFERENCES patients_table(id) ON DELETE CASCADE,
        FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
    )
"""

# Billing Items Table - Links to invoice via invoice_id (can access patient_id, doctor_id, purpose through invoice)
BILLING_ITEMS_TABLE = """
    CREATE TABLE IF NOT EXISTS billing_items (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        invoice_id INTEGER NOT NULL,
        item_type TEXT NOT NULL,
        description TEXT NOT NULL,
        quantity INT NOT NULL,
        unit_price NUMERIC(12,2) NOT NULL,
        line_total NUMERIC(12,2) NOT NULL,
        inventory_item_id INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (invoice_id) REFERENCES billing_invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id) ON DELETE SET NULL
    )
"""

# Pharmacy Walk-In Bills Table - For walk-in customers (no patient/appointment required)
PHARMACY_WALK_IN_BILLS_TABLE = """
    CREATE TABLE IF NOT EXISTS pharmacy_walk_in_bills (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        invoice_number TEXT NOT NULL UNIQUE,
        customer_name TEXT,
        created_by INTEGER NOT NULL,
        issue_date DATE NOT NULL,
        total_amount NUMERIC(12,2) NOT NULL,
        outstanding_amount NUMERIC(12,2) GENERATED ALWAYS AS ((total_amount + tax_amount + adjustments) - discount_amount - amount_paid) STORED,
        status TEXT NOT NULL,
        amount_paid NUMERIC(12,2) NOT NULL,
        payment_mode VARCHAR(20),
        discount_amount NUMERIC(12,2) NOT NULL,
        coupon_code TEXT,
        tax_amount NUMERIC(12,2) NOT NULL,
        gst_percentage NUMERIC(5,2) NOT NULL,
        adjustments NUMERIC(12,2) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )
"""

# Pharmacy Walk-In Items Table - Items in walk-in bills
PHARMACY_WALK_IN_ITEMS_TABLE = """
    CREATE TABLE IF NOT EXISTS pharmacy_walk_in_items (
        id SERIAL PRIMARY KEY,
        tenant_id VARCHAR(100) NOT NULL,
        bill_id INTEGER NOT NULL,
        item_type TEXT NOT NULL,
        description TEXT NOT NULL,
        quantity INT NOT NULL,
        unit_price NUMERIC(12,2) NOT NULL,
        line_total NUMERIC(12,2) NOT NULL,
        inventory_item_id INTEGER,
        expiry_date DATE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bill_id) REFERENCES pharmacy_walk_in_bills(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id) ON DELETE SET NULL
    )
"""

# No migration columns needed - tables are created fresh with updated schema
APPOINTMENT_MIGRATION_COLS = []

TABLE_CONFIGS = [
    ("users", USERS_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS idx_users_user_type ON users(user_type)"
    ], None),
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
        "CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_doctor_name ON appointments(doctor_name)"
    ], APPOINTMENT_MIGRATION_COLS),
    ("inventory_items", INVENTORY_ITEMS_TABLE, INVENTORY_ITEMS_INDEXES, None),
    ("billing_invoices", BILLING_INVOICES_TABLE, ["CREATE INDEX IF NOT EXISTS idx_billing_invoices_tenant_id ON billing_invoices(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_patient_id ON billing_invoices(patient_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_appointment_id ON billing_invoices(appointment_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_doctor_id ON billing_invoices(doctor_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_invoices_invoice_number ON billing_invoices(invoice_number)"
    ], None),
    ("billing_items", BILLING_ITEMS_TABLE, ["CREATE INDEX IF NOT EXISTS idx_billing_items_tenant_id ON billing_items(tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_items_invoice_id ON billing_items(invoice_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_items_inventory_item_id ON billing_items(inventory_item_id)"
    ], None),
    ("prescriptions", PRESCRIPTIONS_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_prescriptions_tenant_id ON prescriptions(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_prescriptions_appointment_id ON prescriptions(appointment_id)",
        "CREATE INDEX IF NOT EXISTS idx_prescriptions_bill_date ON prescriptions(bill_date)"
    ], None),
    ("prescription_items", PRESCRIPTION_ITEMS_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_prescription_items_tenant_id ON prescription_items(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_prescription_items_prescription_id ON prescription_items(prescription_id)",
        "CREATE INDEX IF NOT EXISTS idx_prescription_items_inventory_item_id ON prescription_items(inventory_item_id)"
    ], None),
    ("procedure_rooms", PROCEDURE_ROOMS_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_rooms_tenant_id ON procedure_rooms(tenant_id)"
    ], None),
    ("machines", MACHINES_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_machines_tenant_id ON machines(tenant_id)"
    ], None),
    ("pharmacy_walk_in_bills", PHARMACY_WALK_IN_BILLS_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_pharmacy_walk_in_bills_tenant_id ON pharmacy_walk_in_bills(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_pharmacy_walk_in_bills_invoice_number ON pharmacy_walk_in_bills(invoice_number)",
        "CREATE INDEX IF NOT EXISTS idx_pharmacy_walk_in_bills_created_by ON pharmacy_walk_in_bills(created_by)",
        "CREATE INDEX IF NOT EXISTS idx_pharmacy_walk_in_bills_status ON pharmacy_walk_in_bills(status)",
        "CREATE INDEX IF NOT EXISTS idx_pharmacy_walk_in_bills_issue_date ON pharmacy_walk_in_bills(issue_date)"
    ], None),
    ("pharmacy_walk_in_items", PHARMACY_WALK_IN_ITEMS_TABLE, [
        "CREATE INDEX IF NOT EXISTS idx_pharmacy_walk_in_items_tenant_id ON pharmacy_walk_in_items(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_pharmacy_walk_in_items_bill_id ON pharmacy_walk_in_items(bill_id)",
        "CREATE INDEX IF NOT EXISTS idx_pharmacy_walk_in_items_inventory_item_id ON pharmacy_walk_in_items(inventory_item_id)"
    ], None)
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
    except Exception as e:
        # Table setup failed - log error
        print(f"Error: Failed to setup tables: {e}")

# Removed global connection to prevent connection leak
# Use get_postgres_connection() context manager instead

def get_postgres_connection() -> Any:
    """
    Get a PostgreSQL connection from the pool.
    Returns a context manager that automatically returns the connection.
    Usage:
        with get_postgres_connection() as (conn, cursor):
            cursor.execute("SELECT ...")
            conn.commit()
    """
    if not (postgres_connected and postgres_pool):
        raise RuntimeError("PostgreSQL connection pool not available")
    
    class ConnectionContext:
        def __init__(self):
            self.conn = None
            self.cursor = None
        
        def __enter__(self):
            self.conn = postgres_pool.getconn()
            self.conn.autocommit = False  # Use transactions properly
            self.cursor = self.conn.cursor()
            return (self.conn, self.cursor)
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.cursor:
                self.cursor.close()
            if self.conn:
                if exc_type:
                    self.conn.rollback()
                else:
                    self.conn.commit()
                postgres_pool.putconn(self.conn)
            return False
    
    return ConnectionContext()

# Legacy support - but should be migrated to get_postgres_connection()
# These are kept as None for backward compatibility with old imports
postgres_conn = None
postgres_cursor = None
db_session = None  # Deprecated: Use get_db_session() from db_utils instead

# Initialize database tables on startup
try:
    from app.core.db_session import SessionLocal, init_db
    # Create a temporary session just to initialize tables
    temp_session = SessionLocal()
    init_db()
    temp_session.close()
except Exception as e:
    print(f"Warning: Could not initialize database tables: {e}")

try:
    from app.core.storage import ensure_uploads_directory
    ensure_uploads_directory()
except Exception as e:
    print(f"Warning: Could not ensure uploads directory: {e}")

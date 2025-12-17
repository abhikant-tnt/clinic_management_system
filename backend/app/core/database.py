"""Database connection and table setup for Local and Main Server PostgreSQL"""
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from app.core.config import settings
from datetime import datetime
from typing import Optional

# Import table definitions from modules
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

print(
    f"\n{'='*60}\nDATABASE CONNECTION STATUS\n{'='*60}\n"
    f"Tenant ID: {settings.TENANT_ID}\n"
    f"Local: {settings.LOCAL_POSTGRES_HOST}:{settings.LOCAL_POSTGRES_PORT}, User: {settings.LOCAL_POSTGRES_USER}, DB: {settings.LOCAL_POSTGRES_DB}\n"
    f"Main: {settings.MAIN_POSTGRES_HOST}:{settings.MAIN_POSTGRES_PORT}, User: {settings.MAIN_POSTGRES_USER}, DB: {settings.MAIN_POSTGRES_DB}\n"
)

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
        except Exception as e:            errors.append(f"Trust auth failed: {str(e)}")
    
    if password:
        try:
            return psycopg2.connect(**{**params, "password": password}), "password authentication", None
        except Exception as e:            errors.append(f"Password auth failed: {str(e)}")
    
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
        if errors: print("\n   Error Details:", *[f"      - {e}" for e in errors], sep="\n")
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
        
        # Enable UUID extension if not already enabled (try both pgcrypto and uuid-ossp)
        try:
            local_postgres_cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            local_postgres_conn.commit()
        except Exception:
            try:
                local_postgres_cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
                local_postgres_conn.commit()
            except Exception: 
                pass  # UUID functions might be built-in (PostgreSQL 13+)
        
        print(f"✅ Local PostgreSQL: CONNECTED (DB: {settings.LOCAL_POSTGRES_DB}, Auth: {auth_method})")
    except Exception as e: 
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
    except Exception as e:
        main_postgres_connected = False
        main_postgres_pool = None
        print(f"⚠️  Main Server PostgreSQL: NOT CONNECTED - {e}. Sync unavailable.")

def create_table(cursor, table_sql: str, indexes: list, table_name: str):
    """Create table and indexes. Returns (success, was_created)"""
    try:
        # Extract table name from SQL to check if it exists
        # Handle both "CREATE TABLE IF NOT EXISTS table_name" and "CREATE TABLE IF NOT EXISTS table_name ("
        import re
        match = re.search(r'CREATE TABLE IF NOT EXISTS\s+(\w+)', table_sql, re.IGNORECASE)
        table_name_from_sql = match.group(1) if match else None
        
        table_exists = False
        if table_name_from_sql:
            # Check if table already exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name_from_sql,))
            table_exists = cursor.fetchone()[0]
        
        cursor.execute(table_sql)
        for idx in indexes:
            cursor.execute(idx)
        return (True, not table_exists)  # Return (success, was_created)
    except Exception as e:
        print(f"   Error creating {table_name} table: {e}")
        return (False, False)

def add_columns_if_missing(cursor, columns: list):
    """Add columns if they don't exist"""
    for col_sql in columns:
        try:
            cursor.execute(col_sql)
        except Exception:
            pass

def ensure_tables_exist():
    """Ensure all tables exist in local database - useful after tables are dropped"""
    if not (local_postgres_conn and local_postgres_cursor):
        return False
    
    try:
        for tbl_name, tbl_sql, tbl_indexes, tbl_extra_cols in TABLE_CONFIGS:
            success, _ = create_table(local_postgres_cursor, tbl_sql, tbl_indexes, f"local {tbl_name}")
            if success:
                if tbl_extra_cols:
                    add_columns_if_missing(local_postgres_cursor, tbl_extra_cols)
        local_postgres_conn.commit()
        return True
    except Exception as e:
        print(f"   Error ensuring tables exist: {e}")
        return False

# Setup connections
setup_local_postgres()
setup_main_postgres()

# Table definitions
PATIENTS_TABLE_LOCAL = """
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
        synced_to_main BOOLEAN DEFAULT FALSE, last_synced_at TIMESTAMP,
        UNIQUE(tenant_id, phone)
    )
"""

PATIENTS_TABLE_MAIN = PATIENTS_TABLE_LOCAL.replace("synced_to_main BOOLEAN DEFAULT FALSE", "synced_to_main BOOLEAN DEFAULT TRUE")

STAFF_TABLE = """
    CREATE TABLE IF NOT EXISTS staff (
        id SERIAL PRIMARY KEY, tenant_id VARCHAR(100) NOT NULL,
        firstname VARCHAR(255) NOT NULL, lastname VARCHAR(255) NOT NULL,
        speciality VARCHAR(255), phone VARCHAR(10) NOT NULL,
        synced_to_main BOOLEAN DEFAULT {}, last_synced_at TIMESTAMP
    )
"""

PATIENT_DOCS_TABLE = """
    CREATE TABLE IF NOT EXISTS patient_documents (
        id SERIAL PRIMARY KEY, patient_id INTEGER NOT NULL, tenant_id VARCHAR(100) NOT NULL,
        filename VARCHAR(255) NOT NULL, description TEXT, file_type VARCHAR(50) NOT NULL,
        file_size BIGINT NOT NULL, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        synced_to_main BOOLEAN DEFAULT {}, last_synced_at TIMESTAMP,
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
        synced_to_main BOOLEAN DEFAULT {}, last_synced_at TIMESTAMP,
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

# Note: outstanding_amount is now a GENERATED column in the table definition
# Formula: (total_amount + tax_amount + adjustments) - discount_amount - amount_paid
# No trigger needed - calculated automatically by PostgreSQL

# Table creation configs
TABLE_CONFIGS = [
    ("staff", STAFF_TABLE.format("FALSE"), [
        "CREATE INDEX IF NOT EXISTS idx_staff_tenant_id ON staff(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_staff_phone ON staff(phone)"
    ], None),
    ("patients_table", PATIENTS_TABLE_LOCAL, ["CREATE INDEX IF NOT EXISTS idx_patients_tenant_id ON patients_table(tenant_id)"], None),
    ("patient_documents", PATIENT_DOCS_TABLE.format("FALSE"), [
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_patient_id ON patient_documents(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_tenant_id ON patient_documents(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_uploaded_at ON patient_documents(uploaded_at)"
    ], None),
    ("appointments", APPOINTMENTS_TABLE.format("FALSE"), [
        "CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_tenant_id ON appointments(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_doctor_id ON appointments(doctor_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_appointment_date ON appointments(appointment_date)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_appointment_status ON appointments(appointment_status)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_doctor_name ON appointments(doctor_name)"
    ], APPOINTMENT_CLINICAL_COLS),
    ("inventory_items", INVENTORY_ITEMS_TABLE.format("FALSE"), INVENTORY_ITEMS_INDEXES, None),
    ("billing_invoices", BILLING_INVOICES_TABLE.format("FALSE"), BILLING_INVOICES_INDEXES, None),
    ("billing_items", BILLING_ITEMS_TABLE.format("FALSE"), BILLING_ITEMS_INDEXES, None)
]

# Create tables in Local PostgreSQL
if local_postgres_conn and local_postgres_cursor:
    for tbl_name, tbl_sql, tbl_indexes, tbl_extra_cols in TABLE_CONFIGS:
        success, was_created = create_table(local_postgres_cursor, tbl_sql, tbl_indexes, f"local {tbl_name}")
        if success:
            if tbl_extra_cols:
                add_columns_if_missing(local_postgres_cursor, tbl_extra_cols)
            local_postgres_conn.commit()
            if was_created:
                print(f"   Local {tbl_name} table created successfully.")

# Create tables in Main Server PostgreSQL
if main_postgres_connected and main_postgres_pool:
    try:
        main_conn = main_postgres_pool.getconn()
        main_cursor = main_conn.cursor()
        
        # Enable UUID extension if not already enabled (try both pgcrypto and uuid-ossp)
        try:
            main_cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            main_conn.commit()
        except Exception:
            try:
                main_cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
                main_conn.commit()
            except Exception:
                pass  # UUID functions might be built-in (PostgreSQL 13+)
        
        for tbl_name, tbl_sql, tbl_indexes, tbl_extra_cols in TABLE_CONFIGS:
            if tbl_name == "patients_table":
                main_sql = PATIENTS_TABLE_MAIN
            elif tbl_name == "staff":
                main_sql = STAFF_TABLE.format("TRUE")
            else:
                main_sql = tbl_sql.replace("FALSE", "TRUE")
            success, was_created = create_table(main_cursor, main_sql, tbl_indexes, f"main {tbl_name}")
            if success:
                if tbl_extra_cols:
                    add_columns_if_missing(main_cursor, tbl_extra_cols)
                main_conn.commit()
                if was_created:
                    print(f"   Main server {tbl_name} table created successfully.")
        main_cursor.close()
        main_postgres_pool.putconn(main_conn)
    except Exception as e:
        print(f"   Error creating main server tables: {e}")

# ============================================================================
# SYNC CONFIGURATION - Define how each table should be synced
# ============================================================================
# To add a new table for syncing, just add its configuration here!
# The generic sync function will handle it automatically.
SYNC_CONFIG = {
    "staff": {
        "order": 1,
        "columns": ["id", "tenant_id", "firstname", "lastname", "speciality", "phone"],
        "exclude_columns": [],
        "unique_constraint": None,  # No unique constraint on main server
        "conflict_resolution": "skip",  # Use skip since no unique constraint
        "foreign_keys": [],
        "custom_query": None
    },
    "patients_table": {
        "order": 2,
        "columns": ["id", "tenant_id", "title", "firstname", "lastname", "dob", "age",
                   "gender", "phone", "email", "primary_doctor", "address1", "address2", "country",
                   "city", "state", "pincode", "emergency_contact_name", "emergency_contact_phone",
                   "referral_source", "referral_subcategory", "patient_status", "last_visit_date",
                   "registration_date", "purpose", "past_medical_record", "dermatological_history",
                   "medications", "surgeries", "hormonal_issues"],
        "exclude_columns": ["important_notes"],
        "unique_constraint": ["tenant_id", "phone"],
        "conflict_resolution": "update",
        "foreign_keys": [],
        "custom_query": None
    },
    "appointments": {
        "order": 3,
        "columns": ["id", "patient_id", "doctor_id", "tenant_id", "appointment_date", "appointment_time", "appointment_status",
                "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                "created_at", "updated_at"],
        "exclude_columns": [],
        "conflict_resolution": "custom",
        "conflict_detection": ["patient_id", "tenant_id", "appointment_date", "appointment_time"],
        "conflict_exclude_update": ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "created_at"],
        "foreign_keys": [
            {
                "local_column": "patient_id",
                "reference_table": "patients_table",
                "match_by": ["tenant_id", "phone"],
                "join_columns": ["p.phone as patient_phone"]
            },
            {
                "local_column": "doctor_id",
                "reference_table": "staff",
                "match_by": ["tenant_id", "phone"],
                "join_columns": ["s.phone as doctor_phone"]
            }
        ],
        "custom_query": """
            SELECT a.id, a.patient_id, a.doctor_id, a.tenant_id, a.appointment_date, a.appointment_time, a.appointment_status,
                a.doctor_name, a.appointment_type, a.notes, a.payment_pending, a.follow_up_date,
                a.diagnosis, a.treatment, a.visit_charge, a.medication_charge, a.total_charge, a.is_waived,
                a.created_at, a.updated_at, p.phone as patient_phone, s.phone as doctor_phone
            FROM appointments a 
            INNER JOIN patients_table p ON a.patient_id = p.id
            INNER JOIN staff s ON a.doctor_id = s.id
            WHERE (a.synced_to_main = FALSE OR a.synced_to_main IS NULL)
            AND a.doctor_id IS NOT NULL
        """
    },
    "patient_documents": {
        "order": 4,
        "columns": ["id", "patient_id", "tenant_id", "filename", "description", "file_type", 
                "file_size", "uploaded_at"],
        "exclude_columns": [],
        "conflict_resolution": "custom",
        "conflict_detection": ["patient_id", "tenant_id", "filename"],
        "conflict_exclude_update": ["id", "patient_id", "tenant_id", "filename", "uploaded_at"],
        "foreign_keys": [{
            "local_column": "patient_id",
            "reference_table": "patients_table",
            "match_by": ["tenant_id", "phone"],
            "join_columns": ["p.phone as patient_phone"]
        }],
        "custom_query": """
            SELECT d.id, d.patient_id, d.tenant_id, d.filename, d.description, d.file_type, 
                d.file_size, d.uploaded_at, p.phone as patient_phone
            FROM patient_documents d INNER JOIN patients_table p ON d.patient_id = p.id
            WHERE d.synced_to_main = FALSE OR d.synced_to_main IS NULL
        """
    },
    "inventory_items": {
        "order": 5,
        "columns": ["id", "tenant_id", "name", "category", "unit", "current_stock", "min_stock_level",
                "unit_price", "expiry_date", "supplier_name", "supplier_phone", "created_at", "updated_at"],
        "exclude_columns": [],
        "unique_constraint": None,  # No unique constraint on main server
        "conflict_resolution": "skip",  # Use skip since no unique constraint
        "foreign_keys": [],
        "custom_query": None
    },
    "billing_invoices": {
        "order": 6,
        "columns": ["id", "tenant_id", "invoice_number", "patient_id", "appointment_id", "doctor_id",
                "issue_date", "purpose", "total_amount", "tax_amount", "gst_percentage",
                "discount_amount", "coupon_code", "adjustments", "amount_paid", "status",
                "created_by", "created_at", "updated_at"],
        "exclude_columns": ["outstanding_amount"],
        "unique_constraint": ["invoice_number"],
        "conflict_resolution": "update",
        "foreign_keys": [
            {
                "local_column": "patient_id",
                "reference_table": "patients_table",
                "match_by": ["tenant_id", "phone"]
            },
            {
                "local_column": "appointment_id",
                "reference_table": "appointments",
                "match_by": ["patient_id", "tenant_id", "appointment_date", "appointment_time"]
            },
            {
                "local_column": "doctor_id",
                "reference_table": "staff",
                "match_by": ["tenant_id", "phone"]
            }
        ],
        "custom_query": """
            SELECT bi.id, bi.tenant_id, bi.invoice_number, bi.patient_id, bi.appointment_id, bi.doctor_id,
                bi.issue_date, bi.purpose, bi.total_amount, bi.tax_amount, bi.gst_percentage,
                bi.discount_amount, bi.coupon_code, bi.adjustments, bi.amount_paid, bi.status,
                bi.created_by, bi.created_at, bi.updated_at,
                p.phone as patient_phone,
                s.phone as doctor_phone,
                a.appointment_date, a.appointment_time
            FROM billing_invoices bi 
            INNER JOIN patients_table p ON bi.patient_id = p.id
            INNER JOIN staff s ON bi.doctor_id = s.id
            INNER JOIN appointments a ON bi.appointment_id = a.id
            WHERE (bi.synced_to_main = FALSE OR bi.synced_to_main IS NULL)
        """
    },
    "billing_items": {
        "order": 7,
        "columns": ["id", "tenant_id", "invoice_id", "item_type", "description", "quantity",
                "unit_price", "line_total", "inventory_item_id", "created_at"],
        "exclude_columns": [],
        "unique_constraint": ["invoice_id", "description", "quantity"],
        "conflict_resolution": "update",
        "foreign_keys": [{
            "local_column": "invoice_id",
            "reference_table": "billing_invoices",
            "match_by": ["invoice_number"]
        }],
        "custom_query": """
            SELECT bi.id, bi.tenant_id, bi.invoice_id, bi.item_type, bi.description, bi.quantity,
                bi.unit_price, bi.line_total, bi.inventory_item_id, bi.created_at,
                inv.invoice_number as invoice_number
            FROM billing_items bi 
            INNER JOIN billing_invoices inv ON bi.invoice_id = inv.id
            WHERE (bi.synced_to_main = FALSE OR bi.synced_to_main IS NULL)
        """
    }
}


def _resolve_foreign_key(sync_cursor, fk_config: dict, local_row: dict, tenant_id: str):
    """Resolve foreign key - find parent record in main server"""
    match_by, ref_table = fk_config["match_by"], fk_config["reference_table"]
    local_col = fk_config.get("local_column", "")
    where_parts, where_vals = [], []
    
    for col in match_by:
        where_parts.append(f"{col} = %s")
        val = local_row.get(col)
        
        if col == "tenant_id":
            val = tenant_id
        elif col == "phone":
            # Try different possible phone field names based on context
            # For doctor_id resolution, prefer doctor_phone
            # For patient_id resolution, prefer patient_phone
            if local_col == "doctor_id":
                val = local_row.get("doctor_phone") or local_row.get("phone") or val
            elif local_col == "patient_id":
                val = local_row.get("patient_phone") or local_row.get("phone") or val
            else:
                # Try all possibilities
                val = (local_row.get("patient_phone") or 
                       local_row.get("doctor_phone") or 
                       local_row.get("phone") or 
                       val)
        elif col == "patient_id":
            # Use the resolved patient_id if available, otherwise use the local one
            val = local_row.get("patient_id") or val
        elif col in ["appointment_date", "appointment_time"]:
            # For appointment matching, use the values from the record
            val = local_row.get(col)
        elif col == "invoice_number":
            # Handle invoice_number field
            val = local_row.get("invoice_number") or val
        
        where_vals.append(val)
    
    if "tenant_id" not in match_by:
        where_parts.append("tenant_id = %s")
        where_vals.append(tenant_id)
    
    try:
        sync_cursor.execute(f"SELECT id FROM {ref_table} WHERE {' AND '.join(where_parts)}", tuple(where_vals))
        result = sync_cursor.fetchone()
        if result:
            return result[0]
        else:
            # Log the failure for debugging
            match_values = {}
            for col in match_by:
                if col == "tenant_id":
                    match_values[col] = tenant_id
                elif col == "phone":
                    if local_col == "doctor_id":
                        match_values[col] = local_row.get("doctor_phone") or local_row.get("phone") or "None"
                    elif local_col == "patient_id":
                        match_values[col] = local_row.get("patient_phone") or local_row.get("phone") or "None"
                    else:
                        match_values[col] = (local_row.get("patient_phone") or 
                                           local_row.get("doctor_phone") or 
                                           local_row.get("phone") or "None")
                else:
                    match_values[col] = local_row.get(col) or "None"
            print(f"      ⚠️  FK resolution failed: {local_col} -> {ref_table} (match_by: {match_values})")
            return None
    except Exception as e:
        print(f"      ⚠️  FK resolution error for {local_col} -> {ref_table}: {e}")
        return None


def _sync_table(table_name: str, config: dict, sync_cursor, tenant_id: str, now: datetime) -> int:
    """Sync a single table - minimal code"""
    columns = config["columns"]
    exclude_columns = config.get("exclude_columns", [])
    unique_constraint = config.get("unique_constraint")
    conflict_resolution = config.get("conflict_resolution", "skip")
    foreign_keys = config.get("foreign_keys", [])
    custom_query = config.get("custom_query")
    
    # Get unsynced records
    if custom_query:
        query = custom_query
    else:
        select_cols = [col for col in columns if col not in exclude_columns]
        query = f"SELECT {', '.join(select_cols)} FROM {table_name} WHERE synced_to_main = FALSE OR synced_to_main IS NULL"
    
    local_postgres_cursor.execute(query)
    records = local_postgres_cursor.fetchall()
    
    if not records:
        return 0
    
    # Get column names - use cursor description for accurate column names
    if custom_query:
        # Use cursor description to get actual column names (handles aliases correctly)
        column_names = [desc[0] for desc in local_postgres_cursor.description]
    else:
        column_names = [col for col in columns if col not in exclude_columns]
    
    synced_count = 0
    for row in records:
        record = dict(zip(column_names, row))
        
        try:
            # Resolve foreign keys in order
            fk_resolved = True
            if foreign_keys:
                for fk in foreign_keys:
                    local_col = fk["local_column"]
                    fk_record = record.copy()
                    
                    # Use already resolved FK values if available (e.g., use resolved patient_id when resolving appointment_id)
                    # Also handle field name variations (patient_id vs patient__id)
                    for key, value in record.items():
                        # Normalize key name (remove double underscores if any)
                        normalized_key = key.replace("__", "_")
                        if normalized_key in fk.get("match_by", []) and key.endswith("_id"):
                            fk_record[normalized_key] = value
                    
                    main_id = _resolve_foreign_key(sync_cursor, fk, fk_record, tenant_id)
                    if main_id is None:
                        fk_resolved = False
                        print(f"      ⚠️  Cannot resolve {local_col} for {table_name} record ID {record.get('id')}")
                        break  # Skip record if FK not found
                    record[local_col] = main_id
            
            if not fk_resolved:
                # Foreign key resolution failed - log and skip
                print(f"   ⚠️  Skipping {table_name} record ID {record.get('id')}: Foreign key resolution failed")
                continue
            
            # All FKs resolved (or no FKs), insert record
            insert_cols = [col for col in columns if col not in exclude_columns]
            insert_vals = [tenant_id if col == "tenant_id" else record.get(col) for col in insert_cols]
            
            # Check if record already exists in main server
            existing_id = None
            conflict_detection = config.get("conflict_detection")
            
            # Use conflict_detection if available (for "custom" resolution), otherwise use unique_constraint
            check_fields = conflict_detection if conflict_detection else unique_constraint
            
            if check_fields:
                where_parts = [f"{col} = %s" for col in check_fields]
                where_vals = [tenant_id if col == "tenant_id" else record.get(col) for col in check_fields]
                sync_cursor.execute(f"SELECT id FROM {table_name} WHERE {' AND '.join(where_parts)}", tuple(where_vals))
                existing = sync_cursor.fetchone()
                existing_id = existing[0] if existing else None
            
            if existing_id:
                if conflict_resolution == "update":
                    # Update existing record
                    exclude_from_update = config.get("conflict_exclude_update", unique_constraint or [])
                    update_cols = [col for col in insert_cols if col not in exclude_from_update]
                    update_vals = [record.get(col) for col in update_cols]
                    update_set = ", ".join([f"{col} = %s" for col in update_cols])
                    update_set += ", synced_to_main = TRUE, last_synced_at = %s"
                    update_vals.extend([True, now])
                    sync_cursor.execute(f"UPDATE {table_name} SET {update_set} WHERE id = %s", tuple(update_vals) + (existing_id,))
                    # Mark as synced
                    local_postgres_cursor.execute(f"UPDATE {table_name} SET synced_to_main=TRUE, last_synced_at=%s WHERE id=%s", (now, record["id"]))
                    synced_count += 1
                elif conflict_resolution == "custom":
                    # Custom conflict resolution - update with exclude list
                    exclude_from_update = config.get("conflict_exclude_update", [])
                    update_cols = [col for col in insert_cols if col not in exclude_from_update]
                    update_vals = [record.get(col) for col in update_cols]
                    update_set = ", ".join([f"{col} = %s" for col in update_cols])
                    update_set += ", synced_to_main = TRUE, last_synced_at = %s"
                    update_vals.extend([True, now])
                    sync_cursor.execute(f"UPDATE {table_name} SET {update_set} WHERE id = %s", tuple(update_vals) + (existing_id,))
                    # Mark as synced
                    local_postgres_cursor.execute(f"UPDATE {table_name} SET synced_to_main=TRUE, last_synced_at=%s WHERE id=%s", (now, record["id"]))
                    synced_count += 1
                elif conflict_resolution == "skip":
                    # Skip - just mark as synced since it already exists
                    local_postgres_cursor.execute(f"UPDATE {table_name} SET synced_to_main=TRUE, last_synced_at=%s WHERE id=%s", (now, record["id"]))
                    synced_count += 1
                else:
                    # Unknown conflict resolution - try to insert anyway (might fail with unique constraint)
                    insert_vals.extend([True, now])
                    insert_cols.extend(["synced_to_main", "last_synced_at"])
                    placeholders = ", ".join(["%s"] * len(insert_vals))
                    insert_query = f"INSERT INTO {table_name} ({', '.join(insert_cols)}) VALUES ({placeholders})"
                    sync_cursor.execute(insert_query, insert_vals)
                    local_postgres_cursor.execute(f"UPDATE {table_name} SET synced_to_main=TRUE, last_synced_at=%s WHERE id=%s", (now, record["id"]))
                    synced_count += 1
            else:
                # Insert new record
                insert_vals.extend([True, now])
                insert_cols.extend(["synced_to_main", "last_synced_at"])
                placeholders = ", ".join(["%s"] * len(insert_vals))
                insert_query = f"INSERT INTO {table_name} ({', '.join(insert_cols)}) VALUES ({placeholders})"
                sync_cursor.execute(insert_query, insert_vals)
                
                # Verify insert succeeded by checking if record exists
                if check_fields:
                    where_parts = [f"{col} = %s" for col in check_fields]
                    where_vals = [tenant_id if col == "tenant_id" else record.get(col) for col in check_fields]
                    sync_cursor.execute(f"SELECT id FROM {table_name} WHERE {' AND '.join(where_parts)}", tuple(where_vals))
                    verify = sync_cursor.fetchone()
                    if verify:
                        # Only mark as synced if record actually exists in main server
                        local_postgres_cursor.execute(f"UPDATE {table_name} SET synced_to_main=TRUE, last_synced_at=%s WHERE id=%s", (now, record["id"]))
                        synced_count += 1
                    else:
                        print(f"   ⚠️  Failed to sync {table_name} ID {record.get('id')}: Record not found in main server after insert")
                else:
                    # For tables without unique constraint or conflict detection, mark as synced after insert
                    local_postgres_cursor.execute(f"UPDATE {table_name} SET synced_to_main=TRUE, last_synced_at=%s WHERE id=%s", (now, record["id"]))
                    synced_count += 1
        except Exception as e:
            print(f"   ⚠️  Error syncing {table_name} record ID {record.get('id', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()
    
    return synced_count

def sync_local_to_main():
    """Sync all unsynced records from Local → Main Server - robust implementation"""
    if not (main_postgres_connected and main_postgres_pool and local_postgres_conn and local_postgres_cursor):
        return
    
    tenant_id = settings.TENANT_ID
    now = datetime.now()
    sync_conn = main_postgres_pool.getconn()
    sync_cursor = sync_conn.cursor()
    
    try:
        sorted_tables = sorted(SYNC_CONFIG.items(), key=lambda x: x[1].get("order", 999))
        for table_name, config in sorted_tables:
            try:
                savepoint_name = f"sp_{table_name}"
                sync_cursor.execute(f"SAVEPOINT {savepoint_name}")
                try:
                    count = _sync_table(table_name, config, sync_cursor, tenant_id, now)
                    if count > 0:
                        print(f"   ✅ Synced {count} record(s) from {table_name}")
                    sync_cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                    # Commit after each table to ensure data is persisted immediately
                    sync_conn.commit()
                    local_postgres_conn.commit()
                except Exception as e:
                    sync_cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    print(f"   ⚠️  Error syncing {table_name}: {e}")
                    import traceback
                    traceback.print_exc()
            except Exception as e:
                print(f"   ⚠️  Error setting up savepoint for {table_name}: {e}")
        
    except Exception as e:
        sync_conn.rollback()
        local_postgres_conn.rollback()
        print(f"   ⚠️  Sync error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sync_cursor.close()
        main_postgres_pool.putconn(sync_conn)

def update_schedule_to_dna():
    """Update patient_status from 'schedule' to 'DNA' for patients scheduled for today if not changed.
    This function will be called during sync operations."""
    # TODO: Implement logic to update status from 'schedule' to 'DNA' at end of day
    # This will be handled during sync to main server or cloud
    pass

# SQLAlchemy setup for ORM operations
try:
    from app.core.db_session import SessionLocal, init_db
    db_session = SessionLocal()
    # Initialize SQLAlchemy tables (creates tables if they don't exist)
    init_db()
    print("✅ SQLAlchemy: Tables initialized")
except Exception as e:
    print(f"⚠️  SQLAlchemy: Table initialization warning - {e}")
    db_session = None

# Initial sync and file storage
if main_postgres_connected and local_postgres_cursor:
    sync_local_to_main()

try:
    from app.core.storage import ensure_uploads_directory
    ensure_uploads_directory()
    print("✅ File storage directory initialized")
except Exception as e:
    print(f"⚠️  File storage warning: {e}")

# Final status
print("="*60)
if local_postgres_cursor and main_postgres_connected:
    print("✅ Both databases connected. App fully operational.")
elif local_postgres_cursor:
    print("✅ Local PostgreSQL connected. Main Server sync unavailable.")
else:
    print("❌ Local PostgreSQL not connected. Data operations will fail.")
print("="*60 + "\n")

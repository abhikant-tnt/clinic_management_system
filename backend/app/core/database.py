"""Database connection and table setup for Local and Main Server PostgreSQL"""
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from app.core.config import settings
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.models import Base

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
        print(f"⚠️  Main Server PostgreSQL: NOT CONNECTED - {e}. Sync unavailable.")

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
    CREATE TABLE IF NOT EXISTS patients_table (
        id SERIAL PRIMARY KEY, tenant_id VARCHAR(100) NOT NULL,
        title VARCHAR(10) NOT NULL, firstname VARCHAR(255) NOT NULL, lastname VARCHAR(255) NOT NULL,
        date_of_birth VARCHAR(50) NOT NULL, age INTEGER NOT NULL,
        gender VARCHAR(10) NOT NULL, phone VARCHAR(10) NOT NULL, email VARCHAR(255),
        address1 TEXT NOT NULL, address2 TEXT,
        city VARCHAR(100) NOT NULL, state VARCHAR(100) NOT NULL, pincode VARCHAR(10) NOT NULL,
        emergency_contact_name VARCHAR(255) NOT NULL, emergency_contact_phone VARCHAR(10) NOT NULL,
        referral_source VARCHAR(20) NOT NULL, referral_subcategory VARCHAR(255),
        important_notes TEXT, patient_status VARCHAR(30) NOT NULL,
        last_visit_date VARCHAR(50), registration_date VARCHAR(50) NOT NULL,
        synced_to_main BOOLEAN DEFAULT FALSE, last_synced_at TIMESTAMP,
        UNIQUE(tenant_id, phone)
    )
"""

PATIENTS_TABLE_MAIN = PATIENTS_TABLE_LOCAL.replace("synced_to_main BOOLEAN DEFAULT FALSE", "synced_to_main BOOLEAN DEFAULT TRUE")

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
        status VARCHAR(20) DEFAULT 'Active', doctor_name VARCHAR(255),
        appointment_type VARCHAR(50), notes TEXT, payment_pending BOOLEAN DEFAULT FALSE,
        follow_up_date VARCHAR(50), diagnosis TEXT, treatment TEXT,
        visit_charge DECIMAL(10, 2) DEFAULT 0, medication_charge DECIMAL(10, 2) DEFAULT 0,
        total_charge DECIMAL(10, 2) DEFAULT 0, is_waived BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        synced_to_main BOOLEAN DEFAULT {}, last_synced_at TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients_table(id) ON DELETE CASCADE
    )
"""

APPOINTMENT_CLINICAL_COLS = [
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS diagnosis TEXT",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS treatment TEXT",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS visit_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS medication_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS total_charge DECIMAL(10, 2) DEFAULT 0",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS is_waived BOOLEAN DEFAULT FALSE"
]

# Table creation configs
TABLE_CONFIGS = [
    ("patients_table", PATIENTS_TABLE_LOCAL, ["CREATE INDEX IF NOT EXISTS idx_patients_tenant_id ON patients_table(tenant_id)"], None),
    ("patient_documents", PATIENT_DOCS_TABLE.format("FALSE"), [
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_patient_id ON patient_documents(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_tenant_id ON patient_documents(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_patient_documents_uploaded_at ON patient_documents(uploaded_at)"
    ], None),
    ("appointments", APPOINTMENTS_TABLE.format("FALSE"), [
        "CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_tenant_id ON appointments(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_appointment_date ON appointments(appointment_date)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status)",
        "CREATE INDEX IF NOT EXISTS idx_appointments_doctor_name ON appointments(doctor_name)"
    ], APPOINTMENT_CLINICAL_COLS)
]

# Create tables in Local PostgreSQL
if local_postgres_conn and local_postgres_cursor:
    for tbl_name, tbl_sql, tbl_indexes, tbl_extra_cols in TABLE_CONFIGS:
        if create_table(local_postgres_cursor, tbl_sql, tbl_indexes, f"local {tbl_name}"):
            if tbl_extra_cols:
                add_columns_if_missing(local_postgres_cursor, tbl_extra_cols)
            local_postgres_conn.commit()
            print(f"   Local {tbl_name} table created/verified successfully.")

# Create tables in Main Server PostgreSQL
if main_postgres_connected and main_postgres_pool:
    try:
        main_conn = main_postgres_pool.getconn()
        main_cursor = main_conn.cursor()
        for tbl_name, tbl_sql, tbl_indexes, tbl_extra_cols in TABLE_CONFIGS:
            main_sql = PATIENTS_TABLE_MAIN if tbl_name == "patients_table" else tbl_sql.replace("FALSE", "TRUE")
            if create_table(main_cursor, main_sql, tbl_indexes, f"main {tbl_name}"):
                if tbl_extra_cols:
                    add_columns_if_missing(main_cursor, tbl_extra_cols)
                main_conn.commit()
                print(f"   Main server {tbl_name} table created/verified successfully.")
        main_cursor.close()
        main_postgres_pool.putconn(main_conn)
    except Exception as e:  # pylint: disable=broad-except
        print(f"   Error creating main server tables: {e}")


# ============================================================================
# SYNC CONFIGURATION - Define how each table should be synced
# ============================================================================
# To add a new table for syncing, just add its configuration here!
# The generic sync function will handle it automatically.
SYNC_CONFIG = {
    "patients_table": {
        "order": 1,
        "columns": ["id", "tenant_id", "title", "firstname", "lastname", "date_of_birth", "age",
                   "gender", "phone", "email", "address1", "address2", "city", "state", "pincode",
                   "emergency_contact_name", "emergency_contact_phone", "referral_source",
                   "referral_subcategory", "patient_status", "last_visit_date", "registration_date"],
        "exclude_columns": ["important_notes"],
        "unique_constraint": ["tenant_id", "phone"],
        "conflict_resolution": "update",
        "foreign_keys": [],
        "custom_query": None
    },
    "appointments": {
        "order": 2,
        "columns": ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "status",
                   "doctor_name", "appointment_type", "notes", "payment_pending", "follow_up_date",
                   "diagnosis", "treatment", "visit_charge", "medication_charge", "total_charge", "is_waived",
                   "created_at", "updated_at"],
        "exclude_columns": [],
        "conflict_resolution": "custom",
        "conflict_detection": ["patient_id", "tenant_id", "appointment_date", "appointment_time"],
        "conflict_exclude_update": ["id", "patient_id", "tenant_id", "appointment_date", "appointment_time", "created_at"],
        "foreign_keys": [{
            "local_column": "patient_id",
            "reference_table": "patients_table",
            "match_by": ["tenant_id", "phone"],
            "join_columns": ["p.phone as patient_phone"]
        }],
        "custom_query": """
            SELECT a.id, a.patient_id, a.tenant_id, a.appointment_date, a.appointment_time, a.status,
                   a.doctor_name, a.appointment_type, a.notes, a.payment_pending, a.follow_up_date,
                   a.diagnosis, a.treatment, a.visit_charge, a.medication_charge, a.total_charge, a.is_waived,
                   a.created_at, a.updated_at, p.phone as patient_phone
            FROM appointments a INNER JOIN patients_table p ON a.patient_id = p.id
            WHERE a.synced_to_main = FALSE OR a.synced_to_main IS NULL
        """
    },
    "patient_documents": {
        "order": 3,
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
    }
    # Add more tables here as you create them (auth, billing, calendar, dashboard, inventory, etc.)
    # Example:
    # "invoices": {
    #     "order": 4,
    #     "columns": ["id", "patient_id", "appointment_id", "tenant_id", "amount", ...],
    #     "exclude_columns": [],
    #     "unique_constraint": ["tenant_id", "invoice_number"],
    #     "conflict_resolution": "update",
    #     "foreign_keys": [
    #         {
    #             "local_column": "patient_id",
    #             "reference_table": "patients_table",
    #             "match_by": ["tenant_id", "phone"],
    #             "join_query": "INNER JOIN patients_table p ON i.patient_id = p.id",
    #             "join_columns": ["p.phone as patient_phone"]
    #         }
    #     ],
    #     "custom_query": None
    # }
}


def _resolve_foreign_key(sync_cursor, fk_config: dict, local_row: dict, tenant_id: str):
    """Resolve a foreign key by finding the parent record in main server"""
    match_by, ref_table = fk_config["match_by"], fk_config["reference_table"]
    join_cols = fk_config.get("join_columns", [])
    # Map match_by columns to join aliases (e.g., "phone" -> "patient_phone")
    col_map = {jc.lower().split(" as ")[0].split(".")[-1].strip(): jc.lower().split(" as ")[1].strip() 
               for jc in join_cols if " as " in jc.lower()}
    where_parts, where_vals = [], []
    for col in match_by:
        where_parts.append(f"{col} = %s")
        where_vals.append(local_row.get(col_map.get(col, col), tenant_id if col == "tenant_id" else None))
    if "tenant_id" not in match_by:
        where_parts.append("tenant_id = %s")
        where_vals.append(local_row.get("tenant_id", tenant_id))
    sync_cursor.execute(f"SELECT id FROM {ref_table} WHERE {' AND '.join(where_parts)}", tuple(where_vals))
    result = sync_cursor.fetchone()
    return result[0] if result else None


def _sync_table(table_name: str, config: dict, sync_cursor, tenant_id: str, now: datetime) -> int:
    """Generic function to sync a single table based on configuration"""
    columns = config["columns"]
    exclude_columns = config.get("exclude_columns", [])
    unique_constraint = config.get("unique_constraint")
    conflict_resolution = config.get("conflict_resolution", "skip")
    foreign_keys = config.get("foreign_keys", [])
    custom_query = config.get("custom_query")
    
    # Build SELECT query
    if custom_query:
        query = custom_query
    else:
        # Filter out excluded columns
        select_columns = [col for col in columns if col not in exclude_columns]
        query = f"""
            SELECT {', '.join(select_columns)}
            FROM {table_name}
            WHERE synced_to_main = FALSE OR synced_to_main IS NULL
        """
    
    local_postgres_cursor.execute(query)
    unsynced_records = local_postgres_cursor.fetchall()
    
    if not unsynced_records:
        return 0
    
    # Get column names
    if custom_query:
        select_part = custom_query.upper().split("FROM")[0].replace("SELECT", "").strip()
        column_names = []
        for item in [i.strip() for i in select_part.split(",")]:
            if " AS " in item:
                column_names.append(item.split(" AS ")[-1].strip().lower())
            elif "." in item:
                column_names.append(item.split(".")[-1].strip().lower())
            else:
                column_names.append(item.lower())
    else:
        column_names = [col for col in columns if col not in exclude_columns]
    
    synced_count = 0
    
    for row in unsynced_records:
        record = dict(zip(column_names, row))
        
        try:
            # Resolve foreign keys
            resolved_fks = {}
            for fk in foreign_keys:
                local_col = fk["local_column"]
                if local_col in record:
                    main_id = _resolve_foreign_key(sync_cursor, fk, record, tenant_id)
                    if main_id is None:
                        print(f"   ⚠️  Parent record not found in main server for {table_name} ID {record.get('id')} (FK: {local_col}). Skipping.")
                        continue
                    resolved_fks[local_col] = main_id
            
            # Replace local foreign key values with main server IDs
            for fk_col, main_id in resolved_fks.items():
                record[fk_col] = main_id
            
            # Prepare columns and values for INSERT (exclude join columns and excluded columns)
            insert_columns = [col for col in columns if col not in exclude_columns]
            insert_values = [record.get(col) for col in insert_columns]
            
            # Add sync metadata
            insert_columns.extend(["synced_to_main", "last_synced_at"])
            insert_values.extend([True, now])
            
            # Build INSERT query
            placeholders = ", ".join(["%s"] * len(insert_values))
            insert_query = f"""
                INSERT INTO {table_name} ({', '.join(insert_columns)})
                VALUES ({placeholders})
            """
            
            # Handle conflict resolution
            if unique_constraint and conflict_resolution == "update":
                conflict_cols = ", ".join(unique_constraint)
                exclude_from_update = unique_constraint + ["synced_to_main", "last_synced_at"]
                update_set = ", ".join([f"{col}=EXCLUDED.{col}" for col in insert_columns if col not in exclude_from_update])
                insert_query += f" ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set}, synced_to_main=TRUE, last_synced_at=EXCLUDED.last_synced_at"
                sync_cursor.execute(insert_query, insert_values)
            elif conflict_resolution == "custom":
                conflict_detection = config.get("conflict_detection", [])
                conflict_exclude = config.get("conflict_exclude_update", []) + ["synced_to_main", "last_synced_at"]
                where_parts, where_values = [], []
                for col in conflict_detection:
                    val = record.get(col)
                    if val is None:
                        where_parts.append(f"({col} IS NULL OR {col} = %s)")
                        where_values.extend([None, None])
                    else:
                        where_parts.append(f"{col} = %s")
                        where_values.append(val)
                if where_parts:
                    sync_cursor.execute(f"SELECT id FROM {table_name} WHERE {' AND '.join(where_parts)}", tuple(where_values))
                    existing = sync_cursor.fetchone()
                    if existing:
                        update_cols = [col for col in insert_columns if col not in conflict_exclude]
                        sync_cursor.execute(f"UPDATE {table_name} SET {', '.join([f'{c} = %s' for c in update_cols])}, synced_to_main = TRUE, last_synced_at = %s WHERE id = %s",
                                          [record.get(c) for c in update_cols] + [now, existing[0]])
                    else:
                        sync_cursor.execute(insert_query, insert_values)
                else:
                    sync_cursor.execute(insert_query, insert_values)
            else:
                sync_cursor.execute(insert_query, insert_values)
            
            # Mark as synced in local database
            local_postgres_cursor.execute(
                f"UPDATE {table_name} SET synced_to_main=TRUE, last_synced_at=%s WHERE id=%s",
                (now, record["id"])
            )
            synced_count += 1
            
        except Exception as e:  # pylint: disable=broad-except
            print(f"   ⚠️  Failed to sync {table_name} ID {record.get('id', 'unknown')}: {e}")
    
    return synced_count


def sync_local_to_main():
    """Generic sync function that syncs all tables from Local → Main Server based on SYNC_CONFIG"""
    if not (main_postgres_connected and main_postgres_pool and local_postgres_conn and local_postgres_cursor):
        return
    
    tenant_id = settings.TENANT_ID
    now = datetime.now()
    sync_conn = main_postgres_pool.getconn()
    sync_cursor = sync_conn.cursor()
    
    try:
        # Sort tables by order (to respect dependencies)
        sorted_tables = sorted(SYNC_CONFIG.items(), key=lambda x: x[1].get("order", 999))
        total_synced = {}
        
        for table_name, config in sorted_tables:
            try:
                synced_count = _sync_table(table_name, config, sync_cursor, tenant_id, now)
                if synced_count > 0:
                    total_synced[table_name] = synced_count
                    print(f"   ✅ Synced {synced_count} record(s) from {table_name} → Main Server.")
            except Exception as e:  # pylint: disable=broad-except
                print(f"   ⚠️  Error syncing {table_name}: {e}")
        sync_conn.commit()
        local_postgres_conn.commit()
        
        if total_synced:
            total = sum(total_synced.values())
            print(f"   ✅ Total: Synced {total} record(s) across {len(total_synced)} table(s).")
        
    except Exception as e:  # pylint: disable=broad-except
        print(f"   ⚠️  Error syncing Local → Main Server: {e}")
        sync_conn.rollback()
        local_postgres_conn.rollback()
    finally:
        sync_cursor.close()
        main_postgres_pool.putconn(sync_conn)

# SQLAlchemy setup for ORM operations
try:
    from app.core.db_session import SessionLocal, init_db
    db_session = SessionLocal()
    # Initialize SQLAlchemy tables (creates tables if they don't exist)
    init_db()
    print("✅ SQLAlchemy: Tables initialized")
except Exception as e:  # pylint: disable=broad-except
    print(f"⚠️  SQLAlchemy: Table initialization warning - {e}")
    db_session = None

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
if local_postgres_cursor and main_postgres_connected:
    print("✅ Both databases connected. App fully operational.")
elif local_postgres_cursor:
    print("✅ Local PostgreSQL connected. Main Server sync unavailable.")
else:
    print("❌ Local PostgreSQL not connected. Data operations will fail.")
print("="*60 + "\n")

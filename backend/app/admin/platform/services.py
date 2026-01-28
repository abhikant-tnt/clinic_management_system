"""Platform Admin services - System operations without PHI access"""
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any
import time
from app.core.database import get_postgres_connection, postgres_connected
from app.core.db_utils import get_db_session
from app.core.models import UserModel
from app.admin.platform.schemas import (
    SystemHealthResponse,
    TenantMetadata,
    AggregatedMetrics,
    SystemLogEntry,
    UserMetadata,
    AuditLogEntry
)
from sqlalchemy import text, func
from sqlalchemy.orm import Session


# In-memory audit log (in production, use a proper database table)
_audit_logs: List[Dict[str, Any]] = []


def log_platform_admin_action(
    platform_admin_id: int,
    platform_admin_username: str,
    endpoint: str,
    action: str,
    success: bool,
    details: Optional[Dict[str, Any]] = None
):
    """Log platform admin actions for audit trail"""
    log_entry = {
        "action": action,
        "platform_admin_id": platform_admin_id,
        "platform_admin_username": platform_admin_username,
        "endpoint": endpoint,
        "timestamp": datetime.now(UTC),
        "success": success,
        "details": details or {}
    }
    _audit_logs.append(log_entry)
    # Keep only last 1000 entries in memory
    if len(_audit_logs) > 1000:
        _audit_logs.pop(0)


def get_system_health() -> SystemHealthResponse:
    """Get system health status - no PHI"""
    database_connected = False
    response_time_ms = None
    
    if postgres_connected:
        try:
            start_time = time.time()
            with get_postgres_connection() as (conn, cursor):
                cursor.execute("SELECT 1")
                cursor.fetchone()
                response_time_ms = (time.time() - start_time) * 1000
                database_connected = True
        except Exception:
            database_connected = False
    
    return SystemHealthResponse(
        status="healthy" if database_connected else "unhealthy",
        database_connected=database_connected,
        database_response_time_ms=response_time_ms,
        api_version="1.0.0",
        timestamp=datetime.now(UTC)
    )


def get_tenants_metadata() -> List[TenantMetadata]:
    """Get tenant metadata - counts only, no PHI"""
    tenants_metadata = []
    
    if not postgres_connected:
        return tenants_metadata
    
    try:
        with get_postgres_connection() as (conn, cursor):
            # Get unique tenant IDs
            cursor.execute("SELECT DISTINCT tenant_id FROM users")
            tenant_ids = [row[0] for row in cursor.fetchall()]
            
            for tenant_id in tenant_ids:
                # Count users (clinic staff)
                cursor.execute(
                    "SELECT COUNT(*) FROM users WHERE tenant_id = %s",
                    (tenant_id,)
                )
                total_users = cursor.fetchone()[0]
                
                # Count patients (no PHI, just count)
                cursor.execute(
                    "SELECT COUNT(*) FROM patients_table WHERE tenant_id = %s",
                    (tenant_id,)
                )
                total_patients = cursor.fetchone()[0]
                
                # Count appointments (no PHI, just count)
                cursor.execute(
                    "SELECT COUNT(*) FROM appointments WHERE tenant_id = %s",
                    (tenant_id,)
                )
                total_appointments = cursor.fetchone()[0]
                
                # Count bills (no PHI, just count)
                cursor.execute(
                    "SELECT COUNT(*) FROM billing_invoices WHERE tenant_id = %s",
                    (tenant_id,)
                )
                total_bills = cursor.fetchone()[0]
                
                # Get last activity (most recent user login)
                cursor.execute(
                    """
                    SELECT MAX(last_login) FROM users 
                    WHERE tenant_id = %s AND last_login IS NOT NULL
                    """,
                    (tenant_id,)
                )
                last_activity_result = cursor.fetchone()
                last_activity = last_activity_result[0] if last_activity_result[0] else None
                
                # Determine if active (has activity in last 30 days)
                is_active = False
                if last_activity:
                    days_since_activity = (datetime.now(UTC) - last_activity).days
                    is_active = days_since_activity <= 30
                
                tenants_metadata.append(TenantMetadata(
                    tenant_id=tenant_id,
                    total_users=total_users,
                    total_patients_count=total_patients,
                    total_appointments_count=total_appointments,
                    total_bills_count=total_bills,
                    is_active=is_active,
                    last_activity=last_activity
                ))
    except Exception as e:
        print(f"Error fetching tenants metadata: {e}")
    
    return tenants_metadata


def get_aggregated_metrics() -> AggregatedMetrics:
    """Get aggregated system metrics - counts only, no PHI"""
    if not postgres_connected:
        return AggregatedMetrics(
            total_tenants=0,
            total_users=0,
            total_patients_count=0,
            total_appointments_count=0,
            total_bills_count=0,
            total_inventory_items=0,
            active_appointments_today=0,
            scheduled_appointments_tomorrow=0,
            timestamp=datetime.now(UTC)
        )
    
    try:
        with get_postgres_connection() as (conn, cursor):
            # Total tenants
            cursor.execute("SELECT COUNT(DISTINCT tenant_id) FROM users")
            total_tenants = cursor.fetchone()[0]
            
            # Total users (clinic staff)
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Total patients (count only)
            cursor.execute("SELECT COUNT(*) FROM patients_table")
            total_patients = cursor.fetchone()[0]
            
            # Total appointments (count only)
            cursor.execute("SELECT COUNT(*) FROM appointments")
            total_appointments = cursor.fetchone()[0]
            
            # Total bills (count only)
            cursor.execute("SELECT COUNT(*) FROM billing_invoices")
            total_bills = cursor.fetchone()[0]
            
            # Total inventory items
            cursor.execute("SELECT COUNT(*) FROM inventory_items")
            total_inventory = cursor.fetchone()[0]
            
            # Active appointments today
            today = datetime.now(UTC).date()
            cursor.execute(
                "SELECT COUNT(*) FROM appointments WHERE appointment_date = %s",
                (today,)
            )
            active_today = cursor.fetchone()[0]
            
            # Scheduled appointments tomorrow
            tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
            cursor.execute(
                "SELECT COUNT(*) FROM appointments WHERE appointment_date = %s",
                (tomorrow,)
            )
            scheduled_tomorrow = cursor.fetchone()[0]
            
            return AggregatedMetrics(
                total_tenants=total_tenants,
                total_users=total_users,
                total_patients_count=total_patients,
                total_appointments_count=total_appointments,
                total_bills_count=total_bills,
                total_inventory_items=total_inventory,
                active_appointments_today=active_today,
                scheduled_appointments_tomorrow=scheduled_tomorrow,
                timestamp=datetime.now(UTC)
            )
    except Exception as e:
        print(f"Error fetching aggregated metrics: {e}")
        return AggregatedMetrics(
            total_tenants=0,
            total_users=0,
            total_patients_count=0,
            total_appointments_count=0,
            total_bills_count=0,
            total_inventory_items=0,
            active_appointments_today=0,
            scheduled_appointments_tomorrow=0,
            timestamp=datetime.now(UTC)
        )


def get_system_logs(limit: int = 100) -> List[SystemLogEntry]:
    """
    Get system logs - sanitized, no PHI.
    Note: In production, implement proper log storage and sanitization.
    """
    # Placeholder - in production, read from actual log files/database
    # and sanitize any PHI (patient names, phone numbers, etc.)
    logs = []
    
    # Example: Return empty logs for now
    # In production, implement:
    # 1. Read from log files/database
    # 2. Mask any PHI: patient names, phone numbers, emails
    # 3. Return sanitized logs
    
    return logs


def get_users_metadata(tenant_id: Optional[str] = None) -> List[UserMetadata]:
    """Get users metadata - clinic staff only, no patient data, no PHI"""
    users_metadata = []
    
    try:
        with get_db_session() as session:
            query = session.query(UserModel)
            
            if tenant_id:
                query = query.filter(UserModel.tenant_id == tenant_id)
            
            users = query.all()
            
            for user in users:
                users_metadata.append(UserMetadata(
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    username=user.username,
                    user_type=user.user_type,
                    is_active=user.is_active,
                    last_login=user.last_login
                ))
    except Exception as e:
        print(f"Error fetching users metadata: {e}")
    
    return users_metadata


def get_audit_logs(limit: int = 100) -> List[AuditLogEntry]:
    """Get audit logs for platform admin actions"""
    # Return most recent logs
    recent_logs = _audit_logs[-limit:] if len(_audit_logs) > limit else _audit_logs
    return [
        AuditLogEntry(**log) for log in recent_logs
    ]

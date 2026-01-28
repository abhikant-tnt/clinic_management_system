"""Schemas for Platform Admin endpoints - No PHI (Protected Health Information)"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class SystemHealthResponse(BaseModel):
    """System health status - no PHI"""
    status: str
    database_connected: bool
    database_response_time_ms: Optional[float] = None
    api_version: str
    timestamp: datetime


class TenantMetadata(BaseModel):
    """Tenant/clinic metadata - no patient data"""
    tenant_id: str
    total_users: int
    total_patients_count: int  # Count only, no PHI
    total_appointments_count: int  # Count only, no PHI
    total_bills_count: int  # Count only, no PHI
    is_active: bool  # Based on recent activity
    last_activity: Optional[datetime] = None


class TenantsListResponse(BaseModel):
    """List of tenants with metadata only"""
    tenants: List[TenantMetadata]
    total_tenants: int


class AggregatedMetrics(BaseModel):
    """Aggregated system metrics - no PHI"""
    total_tenants: int
    total_users: int
    total_patients_count: int  # Count only
    total_appointments_count: int  # Count only
    total_bills_count: int  # Count only
    total_inventory_items: int
    active_appointments_today: int
    scheduled_appointments_tomorrow: int
    timestamp: datetime


class SystemLogEntry(BaseModel):
    """System log entry - sanitized, no PHI"""
    level: str
    message: str
    timestamp: datetime
    module: Optional[str] = None
    # Note: Patient IDs/names are masked in logs


class SystemLogsResponse(BaseModel):
    """System logs response - no PHI"""
    logs: List[SystemLogEntry]
    total_logs: int
    filtered: bool  # True if PHI was filtered out


class UserMetadata(BaseModel):
    """User metadata for platform admin - clinic staff only, no patient data"""
    user_id: int
    tenant_id: str
    username: Optional[str] = None
    user_type: str
    is_active: bool
    last_login: Optional[datetime] = None
    # Note: No firstname, lastname, phone, email to protect privacy


class UsersListResponse(BaseModel):
    """List of users (clinic staff) - metadata only"""
    users: List[UserMetadata]
    total_users: int
    tenant_id: Optional[str] = None  # If filtering by tenant


class AuditLogEntry(BaseModel):
    """Audit log for platform admin actions"""
    action: str
    platform_admin_id: int
    platform_admin_username: str
    endpoint: str
    timestamp: datetime
    success: bool
    details: Optional[Dict[str, Any]] = None


class AuditLogsResponse(BaseModel):
    """Audit logs response"""
    logs: List[AuditLogEntry]
    total_logs: int

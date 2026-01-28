"""Platform Admin routes - System management without PHI access"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_platform_admin
from app.admin.platform.schemas import (
    SystemHealthResponse,
    TenantsListResponse,
    AggregatedMetrics,
    SystemLogsResponse,
    UsersListResponse,
    AuditLogsResponse
)
from app.admin.platform.services import (
    get_system_health,
    get_tenants_metadata,
    get_aggregated_metrics,
    get_system_logs,
    get_users_metadata,
    get_audit_logs,
    log_platform_admin_action
)

router = APIRouter()


@router.get("/health", response_model=SystemHealthResponse, status_code=status.HTTP_200_OK)
async def get_system_health_endpoint(
    current_user: dict = Depends(require_platform_admin)
):
    """
    Get system health status.
    Platform admin only - no PHI access.
    """
    try:
        health = get_system_health()
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/health",
            action="get_system_health",
            success=True
        )
        return health
    except Exception as e:
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/health",
            action="get_system_health",
            success=False,
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system health"
        )


@router.get("/tenants", response_model=TenantsListResponse, status_code=status.HTTP_200_OK)
async def get_tenants_list(
    current_user: dict = Depends(require_platform_admin)
):
    """
    Get list of all tenants/clinics with metadata only.
    Platform admin only - no PHI (patient data excluded).
    Returns counts only, no patient names, medical records, or personal information.
    """
    try:
        tenants = get_tenants_metadata()
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/tenants",
            action="get_tenants_list",
            success=True,
            details={"tenant_count": len(tenants)}
        )
        return TenantsListResponse(
            tenants=tenants,
            total_tenants=len(tenants)
        )
    except Exception as e:
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/tenants",
            action="get_tenants_list",
            success=False,
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch tenants metadata"
        )


@router.get("/metrics", response_model=AggregatedMetrics, status_code=status.HTTP_200_OK)
async def get_aggregated_metrics_endpoint(
    current_user: dict = Depends(require_platform_admin)
):
    """
    Get aggregated system metrics.
    Platform admin only - no PHI (counts only, no patient data).
    """
    try:
        metrics = get_aggregated_metrics()
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/metrics",
            action="get_aggregated_metrics",
            success=True
        )
        return metrics
    except Exception as e:
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/metrics",
            action="get_aggregated_metrics",
            success=False,
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch aggregated metrics"
        )


@router.get("/logs", response_model=SystemLogsResponse, status_code=status.HTTP_200_OK)
async def get_system_logs_endpoint(
    current_user: dict = Depends(require_platform_admin),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return")
):
    """
    Get system logs - sanitized, no PHI.
    Platform admin only.
    Patient names, phone numbers, and other PHI are masked in logs.
    """
    try:
        logs = get_system_logs(limit=limit)
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/logs",
            action="get_system_logs",
            success=True,
            details={"limit": limit}
        )
        return SystemLogsResponse(
            logs=logs,
            total_logs=len(logs),
            filtered=True  # PHI is filtered out
        )
    except Exception as e:
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/logs",
            action="get_system_logs",
            success=False,
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system logs"
        )


@router.get("/users", response_model=UsersListResponse, status_code=status.HTTP_200_OK)
async def get_users_list(
    current_user: dict = Depends(require_platform_admin),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID")
):
    """
    Get list of users (clinic staff) - metadata only, no PHI.
    Platform admin only.
    Returns user IDs, types, and activity status only.
    No names, phone numbers, emails, or patient data.
    """
    try:
        users = get_users_metadata(tenant_id=tenant_id)
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/users",
            action="get_users_list",
            success=True,
            details={"tenant_id": tenant_id, "user_count": len(users)}
        )
        return UsersListResponse(
            users=users,
            total_users=len(users),
            tenant_id=tenant_id
        )
    except Exception as e:
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/users",
            action="get_users_list",
            success=False,
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users metadata"
        )


@router.get("/audit", response_model=AuditLogsResponse, status_code=status.HTTP_200_OK)
async def get_audit_logs_endpoint(
    current_user: dict = Depends(require_platform_admin),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of audit logs to return")
):
    """
    Get audit logs of platform admin actions.
    Platform admin only.
    Tracks all platform admin API access for compliance.
    """
    try:
        logs = get_audit_logs(limit=limit)
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/audit",
            action="get_audit_logs",
            success=True,
            details={"limit": limit}
        )
        return AuditLogsResponse(
            logs=logs,
            total_logs=len(logs)
        )
    except Exception as e:
        log_platform_admin_action(
            platform_admin_id=current_user["id"],
            platform_admin_username=current_user["username"],
            endpoint="/platform/audit",
            action="get_audit_logs",
            success=False,
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch audit logs"
        )

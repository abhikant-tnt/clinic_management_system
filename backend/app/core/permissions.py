"""Role-based access control (RBAC) permissions for clinic management system"""
from fastapi import Depends, HTTPException, status
from typing import List, Optional
from app.core.dependencies import get_current_active_user

from app.core.constants import (
    USER_TYPE_PLATFORM_ADMIN,
    USER_TYPE_OWNER,
    USER_TYPE_DOCTOR,
    USER_TYPE_RECEPTIONIST,
    USER_TYPE_STAFF,
    USER_TYPE_PHARMACIST,
    is_platform_admin
)

# Module names
MODULE_DASHBOARD = "dashboard"
MODULE_PATIENTS = "patients"
MODULE_APPOINTMENTS = "appointments"
MODULE_BILLING = "billing"
MODULE_INVENTORY = "inventory"
MODULE_CALENDAR = "calendar"
MODULE_SETTINGS = "settings"
MODULE_ASSET_MANAGEMENT = "asset_management"
MODULE_USERS = "users"

# Permission types
PERMISSION_VIEW = "view"
PERMISSION_CREATE = "create"
PERMISSION_UPDATE = "update"
PERMISSION_DELETE = "delete"
PERMISSION_FULL = "full"  # All permissions

# Access matrix: {user_type: {module: [permissions]}}
ACCESS_MATRIX = {
    USER_TYPE_PLATFORM_ADMIN: {
        MODULE_DASHBOARD: [PERMISSION_VIEW],  # View only for functionality testing
        MODULE_PATIENTS: [],  # NO ACCESS - PHI protection (use /platform endpoints instead)
        MODULE_APPOINTMENTS: [PERMISSION_VIEW],  # View only (contains patient references)
        MODULE_BILLING: [PERMISSION_VIEW],  # View only (contains patient billing data)
        MODULE_INVENTORY: [PERMISSION_FULL],  # Full access - no PHI
        MODULE_CALENDAR: [PERMISSION_VIEW],  # View only
        MODULE_SETTINGS: [PERMISSION_FULL],  # Full access - system settings
        MODULE_ASSET_MANAGEMENT: [PERMISSION_FULL],  # Full access - no PHI
        MODULE_USERS: [PERMISSION_FULL],  # Full access - clinic staff management
    },
    USER_TYPE_OWNER: {
        MODULE_DASHBOARD: [PERMISSION_FULL],
        MODULE_PATIENTS: [PERMISSION_FULL],
        MODULE_APPOINTMENTS: [PERMISSION_FULL],
        MODULE_BILLING: [PERMISSION_FULL],
        MODULE_INVENTORY: [PERMISSION_FULL],
        MODULE_CALENDAR: [PERMISSION_FULL],
        MODULE_SETTINGS: [PERMISSION_FULL],
        MODULE_ASSET_MANAGEMENT: [PERMISSION_FULL],
        MODULE_USERS: [PERMISSION_FULL],
    },
    USER_TYPE_DOCTOR: {
        MODULE_DASHBOARD: [PERMISSION_VIEW],
        MODULE_PATIENTS: [PERMISSION_FULL],  # Full CRUD - doctors can manage patients (works for clinics with/without receptionist)
        MODULE_APPOINTMENTS: [PERMISSION_FULL],  # Full CRUD - doctors can manage appointments (works for clinics with/without receptionist)
        MODULE_BILLING: [],  # No access
        MODULE_INVENTORY: [PERMISSION_VIEW],
        MODULE_CALENDAR: [PERMISSION_VIEW],
        MODULE_SETTINGS: [],  # Only own profile (handled separately)
        MODULE_ASSET_MANAGEMENT: [PERMISSION_VIEW],
        MODULE_USERS: [],  # No access
    },
    USER_TYPE_RECEPTIONIST: {
        MODULE_DASHBOARD: [PERMISSION_VIEW],
        MODULE_PATIENTS: [PERMISSION_FULL],
        MODULE_APPOINTMENTS: [PERMISSION_FULL],
        MODULE_BILLING: [PERMISSION_FULL],
        MODULE_INVENTORY: [PERMISSION_VIEW],
        MODULE_CALENDAR: [PERMISSION_FULL],
        MODULE_SETTINGS: [],  # Only own profile (handled separately)
        MODULE_ASSET_MANAGEMENT: [PERMISSION_VIEW],
        MODULE_USERS: [],  # No access
    },
    USER_TYPE_STAFF: {
        MODULE_DASHBOARD: [],  # No access
        MODULE_PATIENTS: [],  # No access
        MODULE_APPOINTMENTS: [PERMISSION_VIEW],  # View schedule only
        MODULE_BILLING: [],  # No access
        MODULE_INVENTORY: [PERMISSION_VIEW],
        MODULE_CALENDAR: [PERMISSION_VIEW],
        MODULE_SETTINGS: [],  # Only own profile (handled separately)
        MODULE_ASSET_MANAGEMENT: [PERMISSION_VIEW],
        MODULE_USERS: [],  # No access
    },
    USER_TYPE_PHARMACIST: {
        MODULE_DASHBOARD: [PERMISSION_VIEW],
        MODULE_PATIENTS: [PERMISSION_VIEW],  # View patients for prescription lookup
        MODULE_APPOINTMENTS: [],  # No access (walk-ins don't need appointments)
        MODULE_BILLING: [PERMISSION_FULL],  # Full access to create/view bills
        MODULE_INVENTORY: [PERMISSION_VIEW],  # View inventory to see medicines
        MODULE_CALENDAR: [],  # No access
        MODULE_SETTINGS: [],  # Only own profile (handled separately)
        MODULE_ASSET_MANAGEMENT: [],  # No access
        MODULE_USERS: [],  # No access
    },
}


def has_permission(user_type: str, module: str, permission: str) -> bool:
    """
    Check if a user type has a specific permission for a module.
    
    Args:
        user_type: The user type (platform_admin, owner, doctor, receptionist, staff, pharmacist)
        module: The module name
        permission: The permission type (view, create, update, delete, full)
    
    Returns:
        True if user has permission, False otherwise
    """
    if user_type not in ACCESS_MATRIX:
        return False
    
    module_permissions = ACCESS_MATRIX[user_type].get(module, [])
    
    # Full permission grants everything
    if PERMISSION_FULL in module_permissions:
        return True
    
    # Check specific permission
    return permission in module_permissions





def require_permission(module: str, permission: str):
    """
    Dependency factory to require specific permission for a module.
    
    Usage:
        @router.get("/")
        async def get_patients(
            current_user: dict = Depends(require_permission(MODULE_PATIENTS, PERMISSION_VIEW))
        ):
            ...
    """
    def permission_checker(current_user: dict = Depends(get_current_active_user)) -> dict:
        user_type = current_user.get("user_type")
        
        if not user_type:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User type not found"
            )
        
        if not has_permission(user_type, module, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. You don't have {permission} permission for {module}"
            )
        
        return current_user
    
    return permission_checker


def require_user_type(*allowed_types: str):
    """
    Dependency factory to require specific user types.
    
    Usage:
        @router.post("/")
        async def create_user(
            current_user: dict = Depends(require_user_type(USER_TYPE_OWNER))
        ):
            ...
    """
    def user_type_checker(current_user: dict = Depends(get_current_active_user)) -> dict:
        user_type = current_user.get("user_type")
        if user_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required user type: {', '.join(allowed_types)}"
            )
        return current_user
    return user_type_checker


# Convenience dependencies for common checks
require_platform_admin = require_user_type(USER_TYPE_PLATFORM_ADMIN)
require_owner = require_user_type(USER_TYPE_OWNER)
require_doctor = require_user_type(USER_TYPE_DOCTOR)
require_receptionist = require_user_type(USER_TYPE_RECEPTIONIST)
require_staff = require_user_type(USER_TYPE_STAFF)
require_pharmacist = require_user_type(USER_TYPE_PHARMACIST)
require_doctor_or_receptionist = require_user_type(USER_TYPE_DOCTOR, USER_TYPE_RECEPTIONIST)
require_owner_or_doctor = require_user_type(USER_TYPE_OWNER, USER_TYPE_DOCTOR)
require_owner_or_receptionist = require_user_type(USER_TYPE_OWNER, USER_TYPE_RECEPTIONIST)
require_platform_admin_or_owner = require_user_type(USER_TYPE_PLATFORM_ADMIN, USER_TYPE_OWNER)

# Module-specific permission dependencies
require_dashboard_access = require_permission(MODULE_DASHBOARD, PERMISSION_VIEW)
require_patients_view = require_permission(MODULE_PATIENTS, PERMISSION_VIEW)
require_patients_full = require_permission(MODULE_PATIENTS, PERMISSION_FULL)
require_appointments_view = require_permission(MODULE_APPOINTMENTS, PERMISSION_VIEW)
require_appointments_full = require_permission(MODULE_APPOINTMENTS, PERMISSION_FULL)
require_billing_full = require_permission(MODULE_BILLING, PERMISSION_FULL)
require_inventory_view = require_permission(MODULE_INVENTORY, PERMISSION_VIEW)
require_calendar_view = require_permission(MODULE_CALENDAR, PERMISSION_VIEW)
require_calendar_full = require_permission(MODULE_CALENDAR, PERMISSION_FULL)
require_settings_full = require_permission(MODULE_SETTINGS, PERMISSION_FULL)
require_asset_view = require_permission(MODULE_ASSET_MANAGEMENT, PERMISSION_VIEW)
require_users_full = require_permission(MODULE_USERS, PERMISSION_FULL)

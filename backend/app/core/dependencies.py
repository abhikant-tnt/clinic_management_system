"""Dependencies for API authentication and authorization"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from app.core.config import settings
from app.core.database import get_postgres_connection, postgres_connected
from app.core.db_utils import get_db_session
from app.modules.users.models import UserModel
from app.core.constants import is_platform_admin
from sqlalchemy import and_

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


def get_tenant_id() -> str:
    """Get tenant ID from settings"""
    return settings.TENANT_ID


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency to get current authenticated user from JWT token.
    Raises HTTPException if token is invalid or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        tenant_id: str = payload.get("tenant_id")
        user_type: str = payload.get("user_type")

        if username is None or user_id is None:
            raise credentials_exception
            
    except jwt.InvalidTokenError:
        raise credentials_exception
    
    user = None
    current_tenant_id = get_tenant_id()
    
    # Platform admin can access any tenant, regular users must match tenant
    is_platform_admin_user = is_platform_admin(user_type) if user_type else False
    
    if not is_platform_admin_user and tenant_id != current_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid tenant"
        )
    
    # For platform admin, use tenant_id from token (can be any tenant)
    # For regular users, use current_tenant_id
    lookup_tenant_id = tenant_id if is_platform_admin_user else current_tenant_id
    
    user_data = None
    try:
        with get_db_session() as session:
            # Platform admin lookup: match user_id and username, allow any tenant
            # Regular user lookup: match user_id, username, and tenant_id
            if is_platform_admin_user:
                user = session.query(UserModel).filter(
                    and_(
                        UserModel.id == user_id,
                        UserModel.username == username,
                        UserModel.is_active == True
                    )
                ).first()
            else:
                user = session.query(UserModel).filter(
                    and_(
                        UserModel.id == user_id,
                        UserModel.username == username,
                        UserModel.tenant_id == lookup_tenant_id,
                        UserModel.is_active == True
                    )
                ).first()
            
            if user:
                # Get tenant_id from user object or use from token/current tenant
                user_tenant_id = user.tenant_id or (tenant_id if is_platform_admin_user else current_tenant_id)
                user_data = {
                    "id": user.id,
                    "username": user.username,
                    "user_type": user.user_type,
                    "firstname": user.firstname,
                    "lastname": user.lastname,
                    "speciality": user.speciality,
                    "phone": user.phone,
                    "is_active": user.is_active,
                    "tenant_id": user_tenant_id,
                    "is_platform_admin": is_platform_admin_user
                }
    except Exception as e:
        print(f"Warning: Error looking up user in database: {e}")
    
    if not user_data and postgres_connected:
        try:
            with get_postgres_connection() as (_, cursor):
                if is_platform_admin_user:
                    cursor.execute("""
                        SELECT id, username, user_type, firstname, lastname, 
                               speciality, phone, is_active, tenant_id
                        FROM users 
                        WHERE id = %s AND username = %s AND is_active = TRUE
                    """, (user_id, username))
                else:
                    cursor.execute("""
                        SELECT id, username, user_type, firstname, lastname, 
                               speciality, phone, is_active, tenant_id
                        FROM users 
                        WHERE id = %s AND username = %s AND tenant_id = %s AND is_active = TRUE
                    """, (user_id, username, lookup_tenant_id))
                record = cursor.fetchone()
                if record:
                    columns = ["id", "username", "user_type", "firstname", 
                              "lastname", "speciality", "phone", "is_active", "tenant_id"]
                    user_data = dict(zip(columns, record))
                    # Ensure is_platform_admin is set
                    user_data["is_platform_admin"] = is_platform_admin_user
        except Exception:
            pass
    
    if not user_data:
        raise credentials_exception
    
    return user_data


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency to ensure current user is active.
    """
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


def require_user_type(*allowed_types: str):
    """Dependency factory to require specific user types"""
    def user_type_checker(current_user: dict = Depends(get_current_active_user)) -> dict:
        user_type = current_user.get("user_type")
        if user_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required user type: {', '.join(allowed_types)}"
            )
        return current_user
    return user_type_checker


# Import permission dependencies from permissions module
from app.core.permissions import (
    require_platform_admin,
    require_owner,
    require_doctor,
    require_receptionist,
    require_doctor_or_receptionist,
    require_owner_or_doctor,
    require_owner_or_receptionist,
    require_platform_admin_or_owner
)


"""Dependencies for API authentication and authorization"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from app.core.config import settings
from app.core.database import get_postgres_connection, postgres_connected
from app.core.db_utils import get_db_session
from app.core.models import StaffModel
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
        
        if username is None or user_id is None:
            raise credentials_exception
            
    except jwt.InvalidTokenError:
        raise credentials_exception
    
    user = None
    current_tenant_id = get_tenant_id()
    
    if tenant_id != current_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid tenant"
        )
    
    if not user:
        try:
            with get_db_session() as session:
                user = session.query(StaffModel).filter(
                    and_(
                        StaffModel.id == user_id,
                        StaffModel.username == username,
                        StaffModel.tenant_id == current_tenant_id,
                        StaffModel.is_active == True
                    )
                ).first()
        except Exception as e:
            print(f"Warning: Error looking up user in database: {e}")
    
    if not user and postgres_connected:
        try:
            with get_postgres_connection() as (_, cursor):
                cursor.execute("""
                    SELECT id, username, user_type, firstname, lastname, 
                           speciality, phone, is_active
                    FROM staff 
                    WHERE id = %s AND username = %s AND tenant_id = %s AND is_active = TRUE
                """, (user_id, username, current_tenant_id))
                record = cursor.fetchone()
                if record:
                    columns = ["id", "username", "user_type", "firstname", 
                              "lastname", "speciality", "phone", "is_active"]
                    user = dict(zip(columns, record))
        except Exception:
            pass
    
    if not user:
        raise credentials_exception
    
    if hasattr(user, 'id'):
        return {
            "id": user.id,
            "username": user.username,
            "user_type": user.user_type,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "speciality": user.speciality,
            "phone": user.phone,
            "is_active": user.is_active,
            "tenant_id": current_tenant_id
        }
    
    user["tenant_id"] = current_tenant_id
    return user


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


require_doctor = require_user_type("doctor")
require_staff = require_user_type("staff")
require_doctor_or_staff = require_user_type("doctor", "staff")


"""Authentication business logic"""
from datetime import datetime, timedelta, UTC
from typing import Optional
import jwt
import bcrypt
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.database import db_session
from app.core.db_utils import get_db_session
from app.core.models import StaffModel
from sqlalchemy import and_
from app.common.utils import validate_column_names


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    Raises ValueError if password exceeds bcrypt's 72-byte limit.
    """
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        raise ValueError(
            "Password exceeds maximum length of 72 bytes. "
            "Please use a shorter password."
        )
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    Raises ValueError if password exceeds bcrypt's 72-byte limit.
    """
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        raise ValueError(
            "Password exceeds maximum length of 72 bytes. "
            "Please use a shorter password."
        )
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def authenticate_user(username: str, password: str, tenant_id: str) -> Optional[dict]:
    """
    Authenticate a user by username and password.
    Returns user dict if authentication succeeds, None otherwise.
    """
    user = None
    
    if db_session:
        try:
            user = db_session.query(StaffModel).filter(
                and_(
                    StaffModel.username == username,
                    StaffModel.tenant_id == tenant_id,
                    StaffModel.is_active == True
                )
            ).first()
        except Exception as e:
            # User lookup failed - return None (user doesn't exist)
            print(f"Warning: Error looking up user: {e}")
    
    return None
    
    if not user:
        return None
    
    if hasattr(user, 'password_hash'):
        password_hash = user.password_hash
        user_dict = {
            "id": user.id,
            "username": user.username,
            "user_type": user.user_type,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "speciality": user.speciality,
            "phone": user.phone,
            "is_active": user.is_active,
            "last_login": user.last_login
        }
    else:
        password_hash = user.get("password_hash")
        user_dict = user
    
    if not password_hash or not verify_password(password, password_hash):
        return None
    
    # Update last login
    try:
        if hasattr(user, 'id'):
            # User is a model object
            with get_db_session() as session:
                db_user = session.query(StaffModel).filter(
                    and_(StaffModel.id == user.id, StaffModel.tenant_id == tenant_id)
                ).first()
                if db_user:
                    db_user.last_login = datetime.now(UTC)
                    session.commit()
        else:
            # User is a dict
            with get_db_session() as session:
                db_user = session.query(StaffModel).filter(
                    and_(StaffModel.id == user_dict["id"], StaffModel.tenant_id == tenant_id)
                ).first()
                if db_user:
                    db_user.last_login = datetime.now(UTC)
                    session.commit()
    except Exception as e:
        # Last login update failed - log but don't fail the request
        print(f"Warning: Failed to update last login: {e}")
    
    return user_dict


def get_user_by_username(username: str, tenant_id: str) -> Optional[dict]:
    """Get user by username"""
    try:
        with get_db_session() as session:
            user = session.query(StaffModel).filter(
                and_(
                    StaffModel.username == username,
                    StaffModel.tenant_id == tenant_id,
                    StaffModel.is_active == True
                )
            ).first()
            if user:
                return {
                    "id": user.id,
                    "username": user.username,
                    "password_hash": user.password_hash,
                    "user_type": user.user_type,
                    "firstname": user.firstname,
                    "lastname": user.lastname,
                    "speciality": user.speciality,
                    "phone": user.phone,
                    "is_active": user.is_active,
                    "last_login": user.last_login
                }
    except Exception as e:
        # User lookup failed - return None (user doesn't exist)
        print(f"Warning: Error looking up user: {e}")
    
    return None


def create_user_with_credentials(
    firstname: str,
    lastname: str,
    phone: str,
    username: str,
    password: str,
    user_type: str,
    tenant_id: str,
    speciality: Optional[str] = None
) -> Optional[int]:
    """
    Create a new staff member with login credentials.
    Returns staff_id if successful, None otherwise.
    """
    if get_user_by_username(username, tenant_id):
        return None
    
    password_hash = hash_password(password)
    
    try:
        with get_db_session() as session:
            # Check if phone already exists
            existing = session.query(StaffModel).filter(
                and_(StaffModel.phone == phone, StaffModel.tenant_id == tenant_id)
            ).first()
            if existing:
                return None
            
            new_staff = StaffModel(
                tenant_id=tenant_id,
                firstname=firstname.lower(),
                lastname=lastname.lower(),
                speciality=speciality.lower() if speciality else None,
                phone=phone,
                username=username,
                password_hash=password_hash,
                user_type=user_type,
                is_active=True
            )
            session.add(new_staff)
            session.commit()
            session.refresh(new_staff)
            return new_staff.id
    except Exception as e:
        print(f"Error creating user: {e}")
        return None


def get_user_by_id(user_id: int, tenant_id: str) -> Optional[dict]:
    """Get user by ID with password hash"""
    if db_session:
        try:
            user = db_session.query(StaffModel).filter(
                and_(
                    StaffModel.id == user_id,
                    StaffModel.tenant_id == tenant_id
                )
            ).first()
            if user:
                return {
                    "id": user.id,
                    "username": user.username,
                    "password_hash": user.password_hash,
                    "user_type": user.user_type,
                    "firstname": user.firstname,
                    "lastname": user.lastname,
                    "speciality": user.speciality,
                    "phone": user.phone,
                    "is_active": user.is_active,
                    "last_login": user.last_login
                }
        except Exception as e:
            # User lookup failed - return None (user doesn't exist)
            print(f"Warning: Error looking up user: {e}")


def update_user_account(
    user_id: int,
    tenant_id: str,
    current_password: Optional[str] = None,
    new_password: Optional[str] = None,
    username: Optional[str] = None
) -> bool:
    """
    Update user account (password and/or username).
    Returns True if successful, False otherwise.
    """
    user = get_user_by_id(user_id, tenant_id)
    if not user:
        return False
    
    # If changing password, verify current password
    if new_password:
        if not current_password:
            return False
        password_hash = user.get("password_hash")
        if not password_hash or not verify_password(current_password, password_hash):
            return False
    
    # If changing username, check if it's already taken
    if username and username != user.get("username"):
        if get_user_by_username(username, tenant_id):
            return False
    
    # Build update data
    update_data = {}
    if new_password:
        update_data["password_hash"] = hash_password(new_password)
    if username and username != user.get("username"):
        update_data["username"] = username
    
    if not update_data:
        return False
    
    # Update in database
    try:
        with get_db_session() as session:
            staff = session.query(StaffModel).filter(
                and_(StaffModel.id == user_id, StaffModel.tenant_id == tenant_id)
            ).first()
            if not staff:
                return False
            
            for key, value in update_data.items():
                setattr(staff, key, value)
            
            session.commit()
            session.refresh(staff)
            return True
    except Exception as e:
        print(f"Error updating user account: {e}")
        return False


def delete_user_account(user_id: int, tenant_id: str, password: str) -> bool:
    """
    Delete user account (staff record).
    Verifies password before deletion.
    Prevents deleting admin accounts.
    Returns True if successful, False otherwise.
    """
    user = get_user_by_id(user_id, tenant_id)
    if not user:
        return False
    
    # Prevent deleting admin
    if user.get("user_type") == "admin":
        return False
    
    # Verify password
    password_hash = user.get("password_hash")
    if not password_hash or not verify_password(password, password_hash):
        return False
    
    # Delete from database
    try:
        with get_db_session() as session:
            staff = session.query(StaffModel).filter(
                and_(StaffModel.id == user_id, StaffModel.tenant_id == tenant_id)
            ).first()
            if not staff:
                return False
            
            session.delete(staff)
            session.commit()
            return True
    except Exception as e:
        print(f"Error deleting user account: {e}")
        return False
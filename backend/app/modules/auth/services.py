"""Authentication business logic"""
from datetime import datetime, timedelta, UTC
from typing import Optional
import jwt
import bcrypt
from app.core.config import settings
from app.core.db_utils import get_db_session
from app.modules.users.models import UserModel
from app.core.permissions import USER_TYPE_PLATFORM_ADMIN, is_platform_admin
from sqlalchemy import and_


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
    Platform admins can authenticate with any tenant_id (cross-tenant access).
    Regular users must match the provided tenant_id.
    Returns user dict if authentication succeeds, None otherwise.
    """
    try:
        with get_db_session() as session:
            # First, try to find user (check if platform admin by looking without tenant restriction)
            # Platform admin can login with any tenant_id
            user = session.query(UserModel).filter(
                and_(
                    UserModel.username == username,
                    UserModel.is_active == True
                )
            ).first()
            
            # If user found, check if they're platform admin or match tenant
            if not user:
                return None
                
            if not is_platform_admin(user.user_type) and user.tenant_id != tenant_id:
                # Regular user - must match tenant_id
                return None

            # Now we have a valid user, get their data while session is open
            user_dict = {
                "id": user.id,
                "username": user.username,
                "user_type": user.user_type,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "speciality": user.speciality,
                "phone": user.phone,
                "is_active": user.is_active,
                "last_login": user.last_login,
                "tenant_id": user.tenant_id
            }
            password_hash = user.password_hash

            if not password_hash or not verify_password(password, password_hash):
                return None
            
            # Update last login
            user.last_login = datetime.now(UTC)
            session.commit()
            
            return user_dict

    except Exception as e:
        # User lookup failed - return None (user doesn't exist)
        print(f"Warning: Error during authentication: {e}")
        return None


def get_user_by_username(username: str, tenant_id: str) -> Optional[dict]:
    """Get user by username"""
    try:
        with get_db_session() as session:
            user = session.query(UserModel).filter(
                and_(
                    UserModel.username == username,
                    UserModel.tenant_id == tenant_id,
                    UserModel.is_active == True
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
            existing = session.query(UserModel).filter(
                and_(UserModel.phone == phone, UserModel.tenant_id == tenant_id)
            ).first()
            if existing:
                return None
            
            new_staff = UserModel(
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
    try:
        with get_db_session() as session:
            user = session.query(UserModel).filter(
                and_(
                    UserModel.id == user_id,
                    UserModel.tenant_id == tenant_id
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
    
    # Always verify current password if provided
    if current_password:
        password_hash = user.get("password_hash")
        if not password_hash or not verify_password(current_password, password_hash):
            return False
            
    # If changing password without current password (safety check)
    if new_password and not current_password:
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
            user = session.query(UserModel).filter(
                and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id)
            ).first()
            if not user:
                return False
            
            for key, value in update_data.items():
                setattr(user, key, value)
            
            session.commit()
            session.refresh(user)
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
    
    # Prevent deleting platform admin
    user_type = user.get("user_type")
    if user_type == USER_TYPE_PLATFORM_ADMIN:
        return False
    
    # Verify password
    password_hash = user.get("password_hash")
    if not password_hash or not verify_password(password, password_hash):
        return False
    
    # Delete from database
    try:
        with get_db_session() as session:
            user = session.query(UserModel).filter(
                and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id)
            ).first()
            if not user:
                return False
            
            session.delete(user)
            session.commit()
            return True
    except Exception as e:
        print(f"Error deleting user account: {e}")
        return False
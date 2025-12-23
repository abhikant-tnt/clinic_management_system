"""Authentication business logic"""
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.database import postgres_cursor, postgres_conn, db_session
from app.core.models import StaffModel
from sqlalchemy import and_


def hash_password(password: str) -> str:
    """Hash a password using bcrypt (handles bcrypt's 72-byte limit)"""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash (handles bcrypt's 72-byte limit)"""
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
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
        except Exception:
            pass
    
    if not user and postgres_cursor:
        try:
            postgres_cursor.execute("""
                SELECT id, username, password_hash, user_type, firstname, lastname, 
                       speciality, phone, is_active, last_login
                FROM staff 
                WHERE username = %s AND tenant_id = %s AND is_active = TRUE
            """, (username, tenant_id))
            record = postgres_cursor.fetchone()
            if record:
                columns = ["id", "username", "password_hash", "user_type", "firstname", 
                          "lastname", "speciality", "phone", "is_active", "last_login"]
                user = dict(zip(columns, record))
        except Exception:
            pass
    
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
    
    try:
        if db_session and hasattr(user, 'id'):
            user.last_login = datetime.utcnow()
            db_session.commit()
        elif postgres_cursor and postgres_conn:
            postgres_cursor.execute("""
                UPDATE staff SET last_login = %s WHERE id = %s AND tenant_id = %s
            """, (datetime.utcnow(), user_dict["id"], tenant_id))
            postgres_conn.commit()
    except Exception:
        pass
    
    return user_dict


def get_user_by_username(username: str, tenant_id: str) -> Optional[dict]:
    """Get user by username"""
    if db_session:
        try:
            user = db_session.query(StaffModel).filter(
                and_(
                    StaffModel.username == username,
                    StaffModel.tenant_id == tenant_id
                )
            ).first()
            if user:
                return {
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
        except Exception:
            pass
    
    if postgres_cursor:
        try:
            postgres_cursor.execute("""
                SELECT id, username, password_hash, user_type, firstname, lastname,
                       speciality, phone, is_active, last_login
                FROM staff 
                WHERE username = %s AND tenant_id = %s
            """, (username, tenant_id))
            record = postgres_cursor.fetchone()
            if record:
                columns = ["id", "username", "password_hash", "user_type", "firstname",
                          "lastname", "speciality", "phone", "is_active", "last_login"]
                return dict(zip(columns, record))
        except Exception:
            pass
    
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
    
    if db_session:
        try:
            existing = db_session.query(StaffModel).filter(
                and_(StaffModel.phone == phone, StaffModel.tenant_id == tenant_id)
            ).first()
            if existing:
                return None
        except Exception:
            pass
    
    if postgres_cursor:
        try:
            postgres_cursor.execute(
                "SELECT id FROM staff WHERE phone = %s AND tenant_id = %s",
                (phone, tenant_id)
            )
            if postgres_cursor.fetchone():
                return None
        except Exception:
            pass
    
    password_hash = hash_password(password)
    
    if db_session:
        try:
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
            db_session.add(new_staff)
            db_session.commit()
            db_session.refresh(new_staff)
            return new_staff.id
        except Exception as e:
            db_session.rollback()
            return None
    
    if postgres_cursor and postgres_conn:
        try:
            postgres_cursor.execute("""
                INSERT INTO staff (tenant_id, firstname, lastname, speciality, phone, 
                                 username, password_hash, user_type, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                tenant_id,
                firstname.lower(),
                lastname.lower(),
                speciality.lower() if speciality else None,
                phone,
                username,
                password_hash,
                user_type,
                True
            ))
            result = postgres_cursor.fetchone()
            postgres_conn.commit()
            return result[0] if result else None
        except Exception as e:
            postgres_conn.rollback()
            return None
    
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
        except Exception:
            pass
    
    if postgres_cursor:
        try:
            postgres_cursor.execute("""
                SELECT id, username, password_hash, user_type, firstname, lastname,
                       speciality, phone, is_active, last_login
                FROM staff 
                WHERE id = %s AND tenant_id = %s
            """, (user_id, tenant_id))
            record = postgres_cursor.fetchone()
            if record:
                columns = ["id", "username", "password_hash", "user_type", "firstname",
                          "lastname", "speciality", "phone", "is_active", "last_login"]
                return dict(zip(columns, record))
        except Exception:
            pass
    
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
    if db_session:
        try:
            staff = db_session.query(StaffModel).filter(
                and_(StaffModel.id == user_id, StaffModel.tenant_id == tenant_id)
            ).first()
            if not staff:
                return False
            for key, value in update_data.items():
                setattr(staff, key, value)
            db_session.commit()
            db_session.refresh(staff)
            return True
        except Exception:
            db_session.rollback()
            return False
    
    if postgres_cursor and postgres_conn:
        try:
            set_clauses = []
            values = []
            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                values.append(value)
            values.append(user_id)
            values.append(tenant_id)
            
            query = f"UPDATE staff SET {', '.join(set_clauses)} WHERE id = %s AND tenant_id = %s"
            postgres_cursor.execute(query, values)
            postgres_conn.commit()
            return postgres_cursor.rowcount > 0
        except Exception:
            postgres_conn.rollback()
            return False
    
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
    if db_session:
        try:
            staff = db_session.query(StaffModel).filter(
                and_(StaffModel.id == user_id, StaffModel.tenant_id == tenant_id)
            ).first()
            if staff:
                db_session.delete(staff)
                db_session.commit()
                return True
        except Exception:
            db_session.rollback()
            return False
    
    if postgres_cursor and postgres_conn:
        try:
            postgres_cursor.execute(
                "DELETE FROM staff WHERE id = %s AND tenant_id = %s",
                (user_id, tenant_id)
            )
            postgres_conn.commit()
            return postgres_cursor.rowcount > 0
        except Exception:
            postgres_conn.rollback()
            return False
    
    return False
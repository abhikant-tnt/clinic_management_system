from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Any, Union, Optional
from app.core.config import settings
from app.core.db_utils import get_db_session
from app.core.models import UserModel
from sqlalchemy import and_
from app.modules.users.schemas import UserCreate, UserUpdate, User
from app.core.dependencies import get_current_active_user
from app.core.db_helper import check_exists, get_by_id
from app.core.permissions import require_users_full, USER_TYPE_OWNER

router = APIRouter()

def get_tenant_id() -> str:
    return settings.TENANT_ID

def user_to_dict(user_data: Any) -> dict:
    if isinstance(user_data, dict):
        return user_data
    result = {
        "id": user_data.id,
        "tenant_id": user_data.tenant_id,
        "firstname": user_data.firstname,
        "lastname": user_data.lastname,
        "speciality": user_data.speciality,
        "phone": user_data.phone,
    }
    # Add user_type and is_active if available
    if hasattr(user_data, 'user_type'):
        result["user_type"] = user_data.user_type
    if hasattr(user_data, 'is_active'):
        result["is_active"] = user_data.is_active
    return result

def check_user_exists(user_id: int, tenant_id: str) -> bool:
    """Check if user exists using database helper"""
    return check_exists(UserModel, "users", "id", user_id, tenant_id)

def get_user_by_id(user_id: int, tenant_id: str) -> Union[dict, Any, None]:
    """Get user by ID using database helper"""
    columns = ["id", "tenant_id", "firstname", "lastname", "speciality", "phone", "username", "user_type", "is_active"]
    result = get_by_id(UserModel, "users", "id", user_id, tenant_id, columns)
    # If result is a model object, convert it
    if result and not isinstance(result, dict):
        return user_to_dict(result)
    return result

@router.get("/")
async def get_users(
    page: int = Query(1, ge=1), 
    limit: int = Query(10, ge=1, le=10),  # Max 10 per page as per requirements
    current_user: dict = Depends(require_users_full)
):
    """Get all users. Requires owner permission."""
    tenant_id = get_tenant_id()
    
    users_list = []
    try:
        with get_db_session() as session:
            users = session.query(UserModel).filter(
                UserModel.tenant_id == tenant_id
            ).all()
            users_list = [user_to_dict(u) for u in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {e}")
    
    users_list.sort(key=lambda x: x.get("id", 0))
    total = len(users_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "users": users_list[(page - 1) * limit:page * limit],
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}
    }

@router.get("/{user_id}")
async def get_user(
    user_id: int,
    current_user: dict = Depends(require_users_full)
):
    """Get user by ID. Requires owner permission."""
    tenant_id = get_tenant_id()
    user_data = get_user_by_id(user_id, tenant_id)
    if not user_data:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found for this tenant.")
    
    return user_to_dict(user_data)

@router.post("/")
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_users_full)
):
    """Create user. Requires owner permission."""
    tenant_id = get_tenant_id()
    tenant_id_to_use = user_data.tenant_id if user_data.tenant_id else tenant_id
    
    try:
        with get_db_session() as session:
            # Check if user with same phone exists
            existing = session.query(UserModel).filter(
                and_(UserModel.phone == user_data.phone, UserModel.tenant_id == tenant_id_to_use)
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="User with this phone number already exists for this tenant.")
            
            new_user = UserModel(
                tenant_id=tenant_id_to_use,
                firstname=user_data.firstname.lower(),
                lastname=user_data.lastname.lower(),
                speciality=user_data.speciality.lower() if user_data.speciality else None,
                phone=user_data.phone,
                user_type=user_data.user_type.lower() if user_data.user_type else 'staff',
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            new_user_id = new_user.id
        
        return {"message": f"User created successfully with ID {new_user_id}", "user_id": new_user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")

@router.put("/{user_id}")
async def update_user(
    user_id: int, 
    user_data: UserUpdate,
    current_user: dict = Depends(require_users_full)
):
    """Update user. Requires owner permission."""
    tenant_id = get_tenant_id()
    existing_user_obj = get_user_by_id(user_id, tenant_id)
    if not existing_user_obj:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found for this tenant.")
    
    # Prevent changing owner user_type
    if isinstance(existing_user_obj, dict):
        existing_user_type = existing_user_obj.get("user_type")
    else:
        existing_user_type = existing_user_obj.user_type if hasattr(existing_user_obj, 'user_type') else None
    
    if existing_user_type == USER_TYPE_OWNER and user_data.user_type and user_data.user_type != USER_TYPE_OWNER:
        raise HTTPException(
            status_code=403,
            detail="Cannot change owner user type"
        )
    
    update_data = {}
    if user_data.firstname is not None:
        update_data["firstname"] = user_data.firstname.lower()
    if user_data.lastname is not None:
        update_data["lastname"] = user_data.lastname.lower()
    if user_data.speciality is not None:
        update_data["speciality"] = user_data.speciality.lower()
    if user_data.phone is not None:
        update_data["phone"] = user_data.phone
    if user_data.user_type is not None:
        update_data["user_type"] = user_data.user_type.lower()
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    
    try:
        with get_db_session() as session:
            user = session.query(UserModel).filter(
                and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id)
            ).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found for this tenant.")
            
            # Update fields
            for key, value in update_data.items():
                setattr(user, key, value)
            
            session.commit()
            session.refresh(user)
        
        return {"message": f"User with ID {user_id} updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {e}")

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: dict = Depends(require_users_full)
):
    """Delete user. Requires owner permission. Cannot delete owner."""
    tenant_id = get_tenant_id()
    
    # Check if trying to delete owner
    user_data = get_user_by_id(user_id, tenant_id)
    if user_data:
        if isinstance(user_data, dict):
            user_type = user_data.get("user_type")
        else:
            user_type = user_data.user_type if hasattr(user_data, 'user_type') else None
        
        if user_type == USER_TYPE_OWNER:
            raise HTTPException(
                status_code=403, 
                detail="Cannot delete owner user"
            )
    
    try:
        with get_db_session() as session:
            user = session.query(UserModel).filter(
                and_(UserModel.id == user_id, UserModel.tenant_id == tenant_id)
            ).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found for this tenant.")
            
            session.delete(user)
            session.commit()
        
        return {"message": f"User with ID {user_id} deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {e}")

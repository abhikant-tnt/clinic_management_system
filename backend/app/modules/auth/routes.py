"""Authentication routes for login"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.modules.auth.schemas import UserLogin, Token, UserResponse, UserRegister, UserUpdate, UserDelete
from app.modules.auth.services import authenticate_user, create_access_token, create_user_with_credentials, update_user_account, delete_user_account
from app.core.config import settings
from app.core.dependencies import get_current_active_user

router = APIRouter()


def get_tenant_id() -> str:
    """Get tenant ID from settings"""
    return settings.TENANT_ID


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    User login endpoint.
    Accepts username and password, returns JWT token.
    """
    tenant_id = get_tenant_id()
    user = authenticate_user(form_data.username, form_data.password, tenant_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    access_token_expires = None
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["id"],
            "user_type": user["user_type"],
            "tenant_id": tenant_id
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user["user_type"],
        "user_id": user["id"],
        "username": user["username"]
    }


@router.post("/login-json", response_model=Token, status_code=status.HTTP_200_OK)
async def login_json(credentials: UserLogin):
    """
    User login endpoint (JSON body instead of form data).
    Accepts username and password in JSON, returns JWT token.
    """
    tenant_id = get_tenant_id()
    user = authenticate_user(credentials.username, credentials.password, tenant_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    access_token_expires = None
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["id"],
            "user_type": user["user_type"],
            "tenant_id": tenant_id
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user["user_type"],
        "user_id": user["id"],
        "username": user["username"]
    }


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """
    Get current authenticated user information.
    Requires valid JWT token in Authorization header.
    """
    return current_user


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Register a new user (creates staff with login credentials).
    Requires authentication - only logged-in users can create new users.
    """
    tenant_id = get_tenant_id()
    
    if user_data.user_type not in ["doctor", "staff"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_type must be 'doctor' or 'staff'"
        )
    
    if not user_data.phone.isdigit() or len(user_data.phone) != 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number must be exactly 10 digits"
        )
    
    staff_id = create_user_with_credentials(
        firstname=user_data.firstname,
        lastname=user_data.lastname,
        phone=user_data.phone,
        username=user_data.username,
        password=user_data.password,
        user_type=user_data.user_type,
        tenant_id=tenant_id,
        speciality=user_data.speciality
    )
    
    if not staff_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or phone number already exists"
        )
    
    return {
        "message": "User created successfully",
        "staff_id": staff_id,
        "username": user_data.username,
        "user_type": user_data.user_type
    }


@router.put("/me", status_code=status.HTTP_200_OK)
async def update_current_user(
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Update current user's account (password and/or username).
    Requires authentication.
    - To change password: provide current_password and new_password
    - To change username: provide username (must be unique)
    """
    tenant_id = get_tenant_id()
    user_id = current_user.get("id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found in token"
        )
    
    # Validate that at least one field is being updated
    if not update_data.new_password and not update_data.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (new_password or username) must be provided"
        )
    
    # If changing password, current_password is required
    if update_data.new_password and not update_data.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="current_password is required when changing password"
        )
    
    success = update_user_account(
        user_id=user_id,
        tenant_id=tenant_id,
        current_password=update_data.current_password,
        new_password=update_data.new_password,
        username=update_data.username
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update account. Check current password or username availability."
        )
    
    return {
        "message": "Account updated successfully",
        "updated_fields": {
            "password": update_data.new_password is not None,
            "username": update_data.username is not None
        }
    }


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_current_user(
    delete_data: UserDelete,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete current user's own account.
    Requires password confirmation.
    Prevents deleting admin accounts.
    """
    tenant_id = get_tenant_id()
    user_id = current_user.get("id")
    user_type = current_user.get("user_type")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found in token"
        )
    
    # Prevent deleting admin
    if user_type == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete admin account"
        )
    
    success = delete_user_account(
        user_id=user_id,
        tenant_id=tenant_id,
        password=delete_data.password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete account. Check password or account status."
        )
    
    return {
        "message": "Account deleted successfully"
    }

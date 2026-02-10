"""Authentication routes for login"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.modules.auth.schemas import Token, UserLogin, UserRegister, UserResponse, ChangePasswordRequest, ChangeUsernameRequest, UserDelete
from app.modules.auth.services import authenticate_user, create_access_token, create_user_with_credentials, update_user_account, delete_user_account
from app.core.config import settings
from app.core.dependencies import get_current_active_user
from app.core.permissions import USER_TYPE_PLATFORM_ADMIN, is_platform_admin
from app.core.db_utils import get_db_session
from app.modules.users.models import UserModel

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
    
    # For platform admin, use their actual tenant_id from user record
    # For regular users, use the current tenant_id
    token_tenant_id = user.get("tenant_id", tenant_id)
    if is_platform_admin(user.get("user_type")):
        # Platform admin token includes their actual tenant_id but can access any tenant
        token_tenant_id = user.get("tenant_id", tenant_id)
    
    access_token_expires = None
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["id"],
            "user_type": user["user_type"],
            "tenant_id": token_tenant_id
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user["user_type"],
        "user_id": user["id"],
        "username": user["username"],
        "message": "Login successful"
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
        "username": user["username"],
        "message": "Login successful"
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
    user_data: UserRegister
):
    """
    Register a new user. 
    - If no owner exists, only 'owner' role is allowed.
    - If an owner exists, 'owner' role is forbidden, and registration is public.
    """
    tenant_id = get_tenant_id()
    
    # Check database state for owners
    try:
        with get_db_session() as session:
            existing_owner = session.query(UserModel).filter(
                UserModel.tenant_id == tenant_id,
                UserModel.user_type == "owner"
            ).first()
            
            owner_exists = existing_owner is not None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Role guard based on owner existence
    if not owner_exists:
        if user_data.user_type != "owner":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="First user must be an owner. Please register as 'owner'."
            )
    else:
        # If owner exists, registration is closed. Staff must be added by Owner via /api/users/
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is closed for this clinic. Please contact the clinic owner to create an account for you."
        )

    # Basic validation for phone
    if not user_data.phone.isdigit() or len(user_data.phone) != 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter correct 10 digit number."
        )
    
    user_id = create_user_with_credentials(
        firstname=user_data.firstname,
        lastname=user_data.lastname,
        phone=user_data.phone,
        username=user_data.username,
        password=user_data.password,
        user_type=user_data.user_type,
        tenant_id=tenant_id,
        speciality=user_data.speciality or ("Owner" if user_data.user_type == "owner" else None)
    )
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or phone number already exists"
        )
    
    success_message = "User created successfully"
    if user_data.user_type == "owner":
        success_message = "Owner registration successful, please login."
    
    return {
        "message": success_message,
        "user_id": user_id,
        "username": user_data.username,
        "user_type": user_data.user_type
    }


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Change current user's password.
    Requires current password confirmation.
    """
    tenant_id = get_tenant_id()
    user_id = current_user.get("id")
    
    success = update_user_account(
        user_id=user_id,
        tenant_id=tenant_id,
        current_password=request_data.current_password,
        new_password=request_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wrong password.please enter correct password again"
        )
    
    return {"message": "Password changed successfully"}


@router.post("/change-username", status_code=status.HTTP_200_OK)
async def change_username(
    request_data: ChangeUsernameRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Change current user's username.
    Requires password confirmation for security.
    """
    tenant_id = get_tenant_id()
    user_id = current_user.get("id")
    
    success = update_user_account(
        user_id=user_id,
        tenant_id=tenant_id,
        current_password=request_data.current_password,
        username=request_data.new_username
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wrong password.please enter correct password again or check if username is already taken"
        )
    
    return {"message": "Username updated successfully"}


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
    
    # Prevent deleting platform admin
    if user_type == USER_TYPE_PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete platform admin account"
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

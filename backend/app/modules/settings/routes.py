from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_active_user

router = APIRouter()

@router.get("/")
async def get_settings(current_user: dict = Depends(get_current_active_user)):
    """Get settings"""
    return {"message": "Settings endpoint"}



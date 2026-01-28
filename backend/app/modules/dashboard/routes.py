from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_active_user

router = APIRouter()

@router.get("/")
async def get_dashboard(current_user: dict = Depends(get_current_active_user)):
    """Get dashboard data"""
    return {"message": "Dashboard endpoint"}



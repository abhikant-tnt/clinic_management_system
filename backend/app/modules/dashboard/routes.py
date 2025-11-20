from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_dashboard():
    """Get dashboard data"""
    return {"message": "Dashboard endpoint"}



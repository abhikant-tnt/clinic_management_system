from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_appointments():
    """Get appointments"""
    return {"message": "Appointments endpoint"}



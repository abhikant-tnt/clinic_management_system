from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_calendar():
    """Get calendar data"""
    return {"message": "Calendar endpoint"}



from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_settings():
    """Get settings"""
    return {"message": "Settings endpoint"}



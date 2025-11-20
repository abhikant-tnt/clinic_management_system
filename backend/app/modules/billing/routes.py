from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_billing():
    """Get billing data"""
    return {"message": "Billing endpoint"}



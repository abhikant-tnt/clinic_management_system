from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_inventory():
    """Get inventory data"""
    return {"message": "Inventory endpoint"}



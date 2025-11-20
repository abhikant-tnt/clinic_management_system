from fastapi import APIRouter

router = APIRouter()

@router.post("/signup")
def signup():
    """User sign up"""
    return {"message": "Sign up endpoint"}

@router.post("/signin")
def signin():
    """User sign in"""
    return {"message": "Sign in endpoint"}



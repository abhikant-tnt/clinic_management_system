from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core import settings
import app.core.database  # Initialize database connections

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Clinic Management System API"
)

@app.get("/")
def home():
    """API root endpoint"""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}!",
        "version": settings.VERSION,
        "docs": "/docs"
    }

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
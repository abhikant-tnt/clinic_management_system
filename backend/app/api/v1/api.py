from fastapi import APIRouter
from app.modules import dashboard, calendar, patients, appointments, billing, auth, settings, inventory

api_router = APIRouter()

# Register all module routers - Clean imports using __init__.py exports
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])


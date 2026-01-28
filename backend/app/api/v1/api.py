from fastapi import APIRouter
# Industry standard: Import routes directly to avoid circular dependencies
from app.modules.dashboard.routes import router as dashboard_router
from app.modules.calendar.routes import router as calendar_router
from app.modules.patients.routes import router as patients_router
from app.modules.appointments.routes import router as appointments_router
from app.modules.billing.routes import router as billing_router
from app.modules.auth.routes import router as auth_router
from app.modules.settings.routes import router as settings_router
from app.modules.inventory.routes import router as inventory_router
from app.modules.users.routes import router as users_router
from app.modules.asset_management.routes import router as asset_router
from app.admin.platform.routes import router as platform_router

api_router = APIRouter()

# Register all module routers - Direct imports prevent circular dependencies
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(calendar_router, prefix="/calendar", tags=["calendar"])
api_router.include_router(patients_router, prefix="/patients", tags=["patients"])
api_router.include_router(appointments_router, prefix="/appointments", tags=["appointments"])
api_router.include_router(billing_router, prefix="/billing", tags=["billing"])
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["inventory"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(asset_router, prefix="/assets", tags=["Asset Management"])
api_router.include_router(platform_router, prefix="/platform", tags=["Platform Admin"])

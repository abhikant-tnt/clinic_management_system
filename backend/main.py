from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from strawberry.fastapi import GraphQLRouter
from app.api.v1.api import api_router
from app.core import settings
from app.modules.patients.graphql_schema import schema
from app.common.schemas import ErrorResponse
import app.core.database  # Initialize database connections

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Clinic Management System API - REST and GraphQL"
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with consistent error response"""
    errors = [f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            message="Validation error",
            errors=errors
        ).model_dump()
    )

@app.get("/")
def home():
    """API root endpoint"""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}!",
        "version": settings.VERSION,
        "docs": "/docs",
        "graphql": "/graphql",
        "graphql_playground": "/graphql"
    }

@app.get("/health")
def health_check():
    """Check database connection status"""
    from app.core.database import postgres_connected
    status = "connected" if postgres_connected else "disconnected"
    
    return {
        "status": "healthy" if postgres_connected else "degraded",
        "tenant_id": settings.TENANT_ID,
        "database": {
            "status": status,
            "host": settings.MAIN_POSTGRES_HOST,
            "port": settings.MAIN_POSTGRES_PORT,
            "database": settings.MAIN_POSTGRES_DB
        }
    }

# Include REST API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Add GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
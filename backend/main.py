from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from strawberry import Schema
import strawberry
from datetime import datetime
from app.api.v1.api import api_router
from app.core import settings,models
from app.modules.patients.graphql_schema import Query as PatientsQuery, Mutation as PatientsMutation
from app.modules.appointments.graphql_schema import Query as AppointmentsQuery, Mutation as AppointmentsMutation
from app.modules.billing.graphql_schema import Query as BillingQuery, Mutation as BillingMutation
from app.modules.inventory.graphql_schema import Query as InventoryQuery, Mutation as InventoryMutation
from app.modules.users.graphql_schema import Query as UsersQuery, Mutation as UsersMutation
from app.modules.asset_management.graphql_schema import Query as AssetQuery, Mutation as AssetMutation
from app.common.schemas import ErrorResponse
import app.core.database
from app.core.db_session import engine,Base


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Clinic Management System API - REST and GraphQL"
)

from app.core.db_session import engine, Base
from app.core import models  # IMPORTANT: registers all models

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

from app.core.middleware import (
    RateLimitMiddleware,
    RequestTimeoutMiddleware,
    InputValidationMiddleware
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
    requests_per_hour=1000
)

app.add_middleware(
    RequestTimeoutMiddleware,
    timeout_seconds=30
)

app.add_middleware(InputValidationMiddleware)

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
async def health_check():
    """Enhanced health check for dependencies"""
    from app.core.database import postgres_connected, postgres_pool
    from app.core.db_session import engine
    import time
    
    health_status = {
        "status": "healthy",
        "tenant_id": settings.TENANT_ID,
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    db_status = "disconnected"
    db_response_time = None
    try:
        start_time = time.time()
        if postgres_connected and postgres_pool:
            with postgres_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            postgres_pool.putconn(conn)
            db_status = "connected"
        db_response_time = round((time.time() - start_time) * 1000, 2)
    except Exception as e:
        db_status = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    health_status["checks"]["database"] = {
        "status": db_status,
        "host": settings.MAIN_POSTGRES_HOST,
        "port": settings.MAIN_POSTGRES_PORT,
        "database": settings.MAIN_POSTGRES_DB,
        "response_time_ms": db_response_time
    }
    
    orm_status = "disconnected"
    orm_response_time = None
    try:
        start_time = time.time()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        orm_status = "connected"
        orm_response_time = round((time.time() - start_time) * 1000, 2)
    except Exception as e:
        orm_status = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    health_status["checks"]["orm"] = {
        "status": orm_status,
        "response_time_ms": orm_response_time
    }
    
    if health_status["status"] != "healthy":
        health_status["status"] = "degraded"
    
    return health_status

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Combine all GraphQL schemas
@strawberry.type
class Query(PatientsQuery, AppointmentsQuery, BillingQuery, InventoryQuery, UsersQuery, AssetQuery):
    """Combined GraphQL Query type from all modules"""
    pass

@strawberry.type
class Mutation(PatientsMutation, AppointmentsMutation, BillingMutation, InventoryMutation, UsersMutation,AssetMutation):
    """Combined GraphQL Mutation type from all modules"""
    pass

# Create combined schema
combined_schema = Schema(query=Query, mutation=Mutation)

graphql_app = GraphQLRouter(combined_schema)
app.include_router(graphql_app, prefix="/graphql")
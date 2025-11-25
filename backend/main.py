from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from app.api.v1.api import api_router
from app.core import settings
from app.modules.patients.graphql_schema import schema
import app.core.database  # Initialize database connections

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Clinic Management System API - REST and GraphQL"
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

# Include REST API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Add GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
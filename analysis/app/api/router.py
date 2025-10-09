from fastapi import APIRouter
from fastapi.security import HTTPBearer

from app.api.endpoints import data

# Create HTTPBearer instance for Swagger UI
bearer_scheme = HTTPBearer()

api_router = APIRouter()

# New data analysis endpoints only
api_router.include_router(data.router, prefix="/data", tags=["Data Analysis"])
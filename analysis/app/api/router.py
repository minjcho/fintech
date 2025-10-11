from fastapi import APIRouter
from fastapi.security import HTTPBearer

from app.api.endpoints import leak, baseline, doojo

# Create HTTPBearer instance for Swagger UI
bearer_scheme = HTTPBearer()

api_router = APIRouter()

# Data analysis endpoints split into focused modules
api_router.include_router(leak.router, prefix="/data", tags=["Data Analysis - Leak"])
api_router.include_router(baseline.router, prefix="/data", tags=["Data Analysis - Baseline"])
api_router.include_router(doojo.router, prefix="/data", tags=["Data Analysis - Doojo"])
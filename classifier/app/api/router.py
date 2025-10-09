from fastapi import APIRouter

from app.api.endpoints import classify

api_router = APIRouter()

api_router.include_router(classify.router, prefix="/classify", tags=["classification"])
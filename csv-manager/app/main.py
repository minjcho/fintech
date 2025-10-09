"""
CSV Manager Service - Dedicated service for CSV file management
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.endpoints import csv
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CSV Manager Service",
    description="Dedicated service for CSV file upload and management with MinIO/S3 storage",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "https://j13a409.p.ssafy.io",
        "https://j13a409.p.ssafy.io:3002"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include CSV router
app.include_router(csv.router)


@app.get("/")
async def root():
    """Root endpoint showing service information"""
    return {
        "service": "CSV Manager Service",
        "version": "1.0.0",
        "description": "CSV file management with MinIO/S3 storage",
        "endpoints": {
            "upload": "POST /api/ai/csv/upload",
            "delete": "DELETE /api/ai/csv/delete",
            "replace": "PUT /api/ai/csv/change",
            "status": "GET /api/ai/csv/status"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "csv-manager"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
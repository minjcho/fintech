"""
Leak analysis endpoints - Current month predictions
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status, Depends, BackgroundTasks
from datetime import datetime
from sqlalchemy.orm import Session
import uuid
import logging

from app.services.redis_client import RedisClient
from app.services.analysis.prophet_analysis import run_prophet_analysis
from app.db.database import get_db
from app.db import models
from app.api.endpoints.models import LeakDataResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
redis_client = RedisClient()


@router.post(
    "",
    response_model=LeakDataResponse,
    summary="Calculate monthly leak",
    description="Calculate financial leak and predict future spending using Prophet"
)
async def calculate_monthly_leak(
    background_tasks: BackgroundTasks,
    file_id: str = Query(..., description="File ID to analyze"),
    db: Session = Depends(get_db)
) -> LeakDataResponse:
    """
    Start Prophet analysis and return leak data.
    If data already exists, return it immediately.
    Otherwise, start analysis and return results.
    """
    # First check if we already have predictions
    year = datetime.now().year
    month = datetime.now().month

    predictions = db.query(models.Prediction).filter(
        models.Prediction.file_id == file_id,
        models.Prediction.prediction_date == f"{year}-{month:02d}-01"
    ).all()

    if predictions:
        # We already have predictions, return them immediately
        category_predictions = {}
        total_predicted = 0

        for pred in predictions:
            category_predictions[pred.category] = {
                "predicted_amount": float(pred.predicted_amount),
                "lower_bound": float(pred.lower_bound) if pred.lower_bound else None,
                "upper_bound": float(pred.upper_bound) if pred.upper_bound else None
            }
            total_predicted += pred.predicted_amount

        details = {
            "total_predicted": float(total_predicted),
            "categories_count": len(predictions),
            "category_predictions": category_predictions,
            "prediction_date": predictions[0].prediction_date.isoformat() if predictions else None,
            "created_at": predictions[0].created_at.isoformat() if predictions else None
        }

        leak_analysis = db.query(models.LeakAnalysis).filter(
            models.LeakAnalysis.file_id == file_id,
            models.LeakAnalysis.year == year,
            models.LeakAnalysis.month == month
        ).first()

        return LeakDataResponse(
            file_id=file_id,
            year=year,
            month=month,
            leak_amount=float(leak_analysis.leak_amount) if leak_analysis and leak_analysis.leak_amount else 0.0,
            transactions_count=len(predictions),
            details=details
        )

    # No predictions yet, need to run analysis
    # Check if file exists in Redis
    file_metadata = redis_client.get_file_metadata(file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found"
        )

    # Acquire analysis lock atomically to prevent concurrent analysis
    lock_token = redis_client.acquire_analysis_lock(file_id)
    if not lock_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is already in progress for this file"
        )

    # Create analysis job
    job_id = str(uuid.uuid4())
    job = models.AnalysisJob(
        job_id=job_id,
        file_id=file_id,
        status="pending"
    )
    db.add(job)
    db.commit()

    # Run analysis (current month sync, baseline in background)
    await run_prophet_analysis(file_id, job_id, db, background_tasks, lock_token)

    # Analysis completed, now get the results
    predictions = db.query(models.Prediction).filter(
        models.Prediction.file_id == file_id,
        models.Prediction.prediction_date == f"{year}-{month:02d}-01"
    ).all()

    if not predictions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis completed but no predictions found"
        )

    # Build response
    category_predictions = {}
    total_predicted = 0

    for pred in predictions:
        category_predictions[pred.category] = {
            "predicted_amount": float(pred.predicted_amount),
            "lower_bound": float(pred.lower_bound) if pred.lower_bound else None,
            "upper_bound": float(pred.upper_bound) if pred.upper_bound else None
        }
        total_predicted += pred.predicted_amount

    details = {
        "total_predicted": float(total_predicted),
        "categories_count": len(predictions),
        "category_predictions": category_predictions,
        "prediction_date": predictions[0].prediction_date.isoformat() if predictions else None,
        "created_at": predictions[0].created_at.isoformat() if predictions else None
    }

    leak_analysis = db.query(models.LeakAnalysis).filter(
        models.LeakAnalysis.file_id == file_id,
        models.LeakAnalysis.year == year,
        models.LeakAnalysis.month == month
    ).first()

    return LeakDataResponse(
        file_id=file_id,
        year=year,
        month=month,
        leak_amount=float(leak_analysis.leak_amount) if leak_analysis and leak_analysis.leak_amount else 0.0,
        transactions_count=len(predictions),
        details=details
    )


@router.get(
    "/leak",
    response_model=LeakDataResponse,
    summary="Get leak data",
    description="Retrieve spending predictions and leak analysis by category"
)
async def get_leak_data(
    file_id: str = Query(..., description="File ID"),
    category: Optional[str] = Query(None, description="Category to filter (optional)"),
    year: Optional[int] = Query(None, description="Year to query (default: current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month to query (1-12, default: current month)"),
    db: Session = Depends(get_db)
) -> LeakDataResponse:
    """
    Get spending predictions and leak analysis.

    Args:
        file_id: ID of the file
        year: Year to query (optional, defaults to current year)
        month: Month to query (optional, defaults to current month)
        db: Database session

    Returns:
        LeakDataResponse with predictions and leak analysis
    """
    # Use current date if not specified
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month

    # Build query based on whether category is specified
    query = db.query(models.Prediction).filter(
        models.Prediction.file_id == file_id,
        models.Prediction.prediction_date == f"{year}-{month:02d}-01"
    )

    if category:
        # Get specific category prediction
        query = query.filter(models.Prediction.category == category)
        predictions = query.all()
    else:
        # Get all category predictions
        predictions = query.all()

    if not predictions:
        # Check if analysis is in progress
        analysis_status = redis_client.get_csv_status(file_id)
        if analysis_status == 'analyzing':
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Analysis is still in progress. Please try again later."
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No prediction data found for {year}-{month:02d}. Please run analysis first."
        )

    # Get leak analysis if available
    leak_analysis = db.query(models.LeakAnalysis).filter(
        models.LeakAnalysis.file_id == file_id,
        models.LeakAnalysis.year == year,
        models.LeakAnalysis.month == month
    ).first()

    # Prepare response based on whether single category or all
    if category and len(predictions) == 1:
        # Single category response
        prediction = predictions[0]
        details = {
            "category": prediction.category,
            "predicted_amount": float(prediction.predicted_amount),
            "lower_bound": float(prediction.lower_bound) if prediction.lower_bound else None,
            "upper_bound": float(prediction.upper_bound) if prediction.upper_bound else None,
            "prediction_date": prediction.prediction_date.isoformat(),
            "created_at": prediction.created_at.isoformat()
        }
        total_predicted = prediction.predicted_amount
    else:
        # Multiple categories response
        category_predictions = {}
        total_predicted = 0

        for pred in predictions:
            category_predictions[pred.category] = {
                "predicted_amount": float(pred.predicted_amount),
                "lower_bound": float(pred.lower_bound) if pred.lower_bound else None,
                "upper_bound": float(pred.upper_bound) if pred.upper_bound else None
            }
            total_predicted += pred.predicted_amount

        details = {
            "total_predicted": float(total_predicted),
            "categories_count": len(predictions),
            "category_predictions": category_predictions,
            "prediction_date": predictions[0].prediction_date.isoformat() if predictions else None,
            "created_at": predictions[0].created_at.isoformat() if predictions else None
        }

    return LeakDataResponse(
        file_id=file_id,
        year=year,
        month=month,
        leak_amount=float(leak_analysis.leak_amount) if leak_analysis and leak_analysis.leak_amount else 0.0,
        transactions_count=len(predictions),  # Number of categories analyzed
        details=details
    )

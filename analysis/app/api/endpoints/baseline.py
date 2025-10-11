"""
Baseline predictions endpoints - Past 11 months
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status, Depends
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.services.redis_client import RedisClient
from app.db.database import get_db
from app.db import models
from app.core.constants import BASELINE_MONTHS_COUNT, PROPHET_MIN_DATA_DAYS, PROPHET_MIN_TRANSACTIONS

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
redis_client = RedisClient()


@router.get(
    "/baseline",
    summary="Get baseline predictions",
    description="Retrieve baseline predictions for past 11 months (소비 기준 금액)"
)
async def get_baseline_predictions(
    file_id: str = Query(..., description="File ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db)
):
    """
    Get baseline predictions (소비 기준 금액) for past 11 months
    Each month's prediction is calculated using only prior data
    """
    # Don't check Redis status - baseline runs in background
    # Just return what's available in the database

    # Build query
    query = db.query(models.BaselinePrediction).filter(
        models.BaselinePrediction.file_id == file_id
    )

    if category:
        query = query.filter(models.BaselinePrediction.category == category)

    # Order by year and month descending (most recent first)
    baselines = query.order_by(
        models.BaselinePrediction.year.desc(),
        models.BaselinePrediction.month.desc()
    ).all()

    # Get all unique categories from the data to ensure consistency
    all_categories_query = db.query(models.BaselinePrediction.category).filter(
        models.BaselinePrediction.file_id == file_id
    ).distinct()
    all_categories = set([cat.category for cat in all_categories_query.all()])

    # Check data availability and provide detailed feedback
    current_date = datetime.now()
    expected_months = []
    for i in range(BASELINE_MONTHS_COUNT, 0, -1):  # Past N months (from constants)
        calc_date = current_date - timedelta(days=30 * i)
        expected_months.append(f"{calc_date.year}-{calc_date.month:02d}")

    if not baselines:
        # Get file metadata to check data range
        file_metadata = redis_client.get_file_metadata(file_id)

        error_detail = {
            "error": "No baseline predictions available",
            "reason": "Insufficient historical data for baseline analysis",
            "requirements": {
                "minimum_days": PROPHET_MIN_DATA_DAYS,
                "minimum_transactions": PROPHET_MIN_TRANSACTIONS,
                "description": f"Baseline analysis requires at least {PROPHET_MIN_DATA_DAYS} days of historical data"
            },
            "expected_months": expected_months,
            "available_months": [],
            "suggestion": "Please upload a CSV file with at least 2-3 months of transaction history"
        }

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_detail
        )

    # If we don't have any categories yet, get them from a broader query or use default list
    if not all_categories and not baselines:
        # Try to get categories from predictions table as fallback
        pred_categories_query = db.query(models.Prediction.category).filter(
            models.Prediction.file_id == file_id
        ).distinct()
        pred_categories = [cat.category for cat in pred_categories_query.all()]

        if pred_categories:
            all_categories = set(pred_categories)
        else:
            # Default categories if no data exists yet
            all_categories = {
                "식비", "카페", "마트 / 편의점", "교통 / 차량", "주거 / 통신",
                "패션 / 미용", "문화생활", "건강 / 병원", "교육", "경조사 / 회비",
                "생활용품", "기타", "보험 / 세금"
            }

    # Group by month
    monthly_baselines = {}
    for baseline in baselines:
        month_key = f"{baseline.year}-{baseline.month:02d}"

        if month_key not in monthly_baselines:
            # Initialize with all categories set to 0
            monthly_baselines[month_key] = {
                "year": baseline.year,
                "month": baseline.month,
                "total": 0,
                "categories": {
                    cat: {
                        "predicted_amount": 0.0,
                        "lower_bound": 0.0,
                        "upper_bound": 0.0
                    }
                    for cat in all_categories
                },
                "training_cutoff": baseline.training_cutoff_date.isoformat() if baseline.training_cutoff_date else None
            }

        # Update with actual values (ensure no negative predictions)
        predicted = max(0.0, float(baseline.predicted_amount))  # Convert negative to 0
        monthly_baselines[month_key]["categories"][baseline.category] = {
            "predicted_amount": predicted,
            "lower_bound": float(baseline.lower_bound) if baseline.lower_bound else 0.0,
            "upper_bound": float(baseline.upper_bound) if baseline.upper_bound else 0.0
        }
        monthly_baselines[month_key]["total"] += predicted  # Use the non-negative value for total

    # Sort months chronologically
    sorted_months = sorted(monthly_baselines.keys(), reverse=True)

    # Check if we have all expected months
    missing_months = [month for month in expected_months if month not in monthly_baselines]

    # Add missing months with all zeros for all categories
    for missing_month in missing_months:
        year, month = missing_month.split('-')
        year = int(year)
        month = int(month)
        cutoff_date = datetime(year, month, 1) - timedelta(days=1)

        monthly_baselines[missing_month] = {
            "year": year,
            "month": month,
            "total": 0,
            "categories": {
                cat: {
                    "predicted_amount": 0.0,
                    "lower_bound": 0.0,
                    "upper_bound": 0.0
                }
                for cat in all_categories
            },
            "training_cutoff": cutoff_date.isoformat()
        }

    # Re-sort after adding missing months
    sorted_months = sorted(monthly_baselines.keys(), reverse=True)

    response = {
        "file_id": file_id,
        "baseline_months": [
            {
                "month": monthly_baselines[month]["month"],
                "year": monthly_baselines[month]["year"],
                "total_predicted": float(monthly_baselines[month]["total"]),
                "categories_count": len(all_categories),  # Always return total category count
                "category_predictions": monthly_baselines[month]["categories"] if not category else {
                    category: monthly_baselines[month]["categories"].get(category, {
                        "predicted_amount": 0.0,
                        "lower_bound": 0.0,
                        "upper_bound": 0.0
                    })
                },
                "training_data_until": monthly_baselines[month]["training_cutoff"]
            }
            for month in sorted_months
        ],
        "months_count": BASELINE_MONTHS_COUNT,  # Always N months (from constants)
        "category_filter": category
    }

    # No longer add warnings since we're filling missing data with zeros
    # All 11 months will always be present

    return response

"""
Prophet analysis service for current month predictions
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
import pandas as pd
import logging

from app.services.prophet_service import ProphetService
from app.services.redis_client import RedisClient
from app.services.s3_client import S3Client
from app.services.analysis.baseline_analysis import run_baseline_analysis
from app.db.database import get_db
from app.db import models
from app.repos.prediction_repo import PredictionRepository
from app.repos.leak_repo import LeakAnalysisRepository
from app.repos.doojo_repo import DoojoAnalysisRepository

logger = logging.getLogger(__name__)

# Initialize services
prophet_service = ProphetService()
redis_client = RedisClient()
s3_client = S3Client()


async def run_prophet_analysis(
    file_id: str,
    job_id: str,
    db: Session = None,
    background_tasks: BackgroundTasks = None,
    lock_token: Optional[str] = None
):
    """
    Run Prophet analysis - current month immediately, baseline in background

    Args:
        file_id: File ID
        job_id: Analysis job ID
        db: Database session (if None, will create a new session)
        background_tasks: FastAPI background tasks
        lock_token: Lock token for ownership verification
    """
    # Track whether we created the session (to know if we should close it)
    session_created = False

    try:
        # Get fresh DB session for task if not provided
        if db is None:
            db = next(get_db())
            session_created = True

        # Lock already acquired in calculate_monthly_leak
        # No need to set status here

        # Get file metadata from Redis
        file_metadata = redis_client.get_file_metadata(file_id)
        if not file_metadata:
            raise ValueError(f"File metadata not found for {file_id}")

        # Fetch CSV data from S3
        s3_key = file_metadata.get('s3_key')
        if not s3_key:
            raise ValueError(f"S3 key not found for {file_id}")

        csv_data = await s3_client.fetch_csv_data(file_id, s3_key)
        if csv_data is None:
            raise ValueError(f"Failed to fetch CSV data for {file_id}")

        # Calculate doojo statistics (min/max per category)
        # Use 'transaction_date_time' column instead of 'date' as per Prophet service expectations
        csv_data['year_month'] = pd.to_datetime(csv_data['transaction_date_time']).dt.to_period('M')
        monthly_spending = csv_data.groupby(['category', 'year_month'])['amount'].sum().reset_index()
        category_stats = monthly_spending.groupby('category')['amount'].agg(['min', 'max']).to_dict('index')

        # Get current month actual spending if available
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month
        current_period = f"{current_year}-{current_month:02d}"
        current_month_data = csv_data[csv_data['year_month'].astype(str) == current_period]
        current_month_actual = {}
        if not current_month_data.empty:
            current_month_actual = current_month_data.groupby('category')['amount'].sum().to_dict()

        # STEP 1: Run current month prediction first
        logger.info(f"Starting current month prediction for {file_id}")
        current_month_result = await prophet_service.predict_by_category(csv_data)

        # Process current month results first
        if current_month_result.get('prediction_id'):
            category_predictions = current_month_result.get('category_predictions', {})
            year = current_month_result.get('year')
            month = current_month_result.get('month')

            # Initialize repositories
            prediction_repo = PredictionRepository(db)
            leak_repo = LeakAnalysisRepository(db)
            doojo_repo = DoojoAnalysisRepository(db)

            # STEP 1: Bulk upsert predictions (1 query instead of N)
            prediction_repo.bulk_upsert_predictions(
                file_id=file_id,
                year=year,
                month=month,
                category_predictions=category_predictions
            )

            # STEP 2: Upsert leak analysis (1 query)
            # Calculate if any category has actual data
            has_actual_data = any(
                cat_data.get('current_month', {}).get('actual') is not None
                for cat_data in category_predictions.values()
                if 'error' not in cat_data
            )

            if has_actual_data:
                # Get first actual amount for leak analysis (aggregate later if needed)
                first_actual = next(
                    (cat_data.get('current_month', {}).get('actual')
                     for cat_data in category_predictions.values()
                     if 'error' not in cat_data and cat_data.get('current_month', {}).get('actual') is not None),
                    None
                )

                leak_repo.upsert_leak_analysis(
                    file_id=file_id,
                    year=year,
                    month=month,
                    actual_amount=first_actual,
                    predicted_amount=current_month_result.get('total_current_predicted', 0),
                    leak_amount=0,  # Calculate total leak later
                    analysis_data={'categories': category_predictions}
                )

            # STEP 3: Bulk upsert doojo analysis (1 query instead of N)
            doojo_data = []
            for category, cat_data in category_predictions.items():
                if 'error' in cat_data:
                    continue

                current_month = cat_data.get('current_month', {})
                if not current_month:
                    continue

                cat_stats = category_stats.get(category, {'min': 0, 'max': 0})
                real_amount = current_month_actual.get(category, None)
                result = None
                if real_amount is not None:
                    result = 'true' if real_amount > current_month.get('predicted', 0) else 'false'

                doojo_data.append({
                    'category': category,
                    'min_amount': float(cat_stats['min']),
                    'max_amount': float(cat_stats['max']),
                    'current_threshold': current_month.get('predicted', 0),
                    'real_amount': real_amount,
                    'result': result
                })

            if doojo_data:
                doojo_repo.bulk_upsert_doojo_analysis(
                    file_id=file_id,
                    year=year,
                    month=month,
                    category_data=doojo_data
                )

            # Next month predictions removed - no longer needed

            # Commit current month predictions first
            db.commit()
            logger.info(f"Current month predictions saved for {file_id}")

            # STEP 2: Start baseline calculation in background
            if background_tasks:
                try:
                    logger.info(f"Starting baseline calculation in background for {file_id}")
                    background_tasks.add_task(
                        run_baseline_analysis,
                        file_id,
                        csv_data,
                        lock_token
                    )
                except Exception as bg_error:
                    logger.error(f"Failed to schedule baseline task for {file_id}: {bg_error}")
                    # Release lock if background task scheduling failed
                    if lock_token:
                        redis_client.release_analysis_lock(file_id, lock_token)
            else:
                # Issue #1: If no background_tasks, release lock immediately
                # (baseline won't run, so we must release the lock here)
                logger.warning(f"No background_tasks available for {file_id}, releasing lock immediately")
                if lock_token:
                    redis_client.release_analysis_lock(file_id, lock_token)

            # Update job status
            job = db.query(models.AnalysisJob).filter(
                models.AnalysisJob.job_id == job_id
            ).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.now()
                job.job_metadata = {
                    'prediction_id': current_month_result.get('prediction_id'),
                    'categories_analyzed': current_month_result.get('categories_analyzed'),
                    'total_current_predicted': current_month_result.get('total_current_predicted'),
                    'trend': current_month_result.get('trend'),
                    'baseline_months_calculated': 0  # Baseline is calculated in background
                }

            db.commit()

            # Don't update Redis status here - wait for baseline to complete
            # redis_client.set_csv_status(file_id, "none")  # Moved to baseline completion

            # Store analysis metadata separately if needed
            if current_month_result:
                analysis_metadata = {
                    **current_month_result,
                    'baseline_predictions': None  # Will be updated when baseline completes
                }
                redis_client.set_analysis_metadata(file_id, analysis_metadata)

            logger.info(f"Current month analysis completed for {file_id}, baseline running in background")
        else:
            raise Exception("Prophet analysis failed - no prediction ID")

    except Exception as e:
        logger.error(f"Prophet analysis failed for {file_id}: {str(e)}")

        # Update job status to failed with dedicated session management
        job_session = None
        try:
            # Reuse existing session if available, otherwise create temporary one
            job_session = db if db is not None else next(get_db())

            job = job_session.query(models.AnalysisJob).filter(
                models.AnalysisJob.job_id == job_id
            ).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now()
            job_session.commit()
        except Exception as job_error:
            logger.error(f"Failed to update job status: {job_error}")
        finally:
            # Only close session if we created a temporary one for job update
            if job_session is not None and job_session != db:
                job_session.close()

        # Store error metadata for debugging
        redis_client.set_analysis_metadata(file_id, {"error": str(e)})

        # Release analysis lock on failure (since baseline won't run)
        if lock_token:
            redis_client.release_analysis_lock(file_id, lock_token)
    finally:
        # Only close the db connection if we created it in this function
        if session_created and db:
            db.close()

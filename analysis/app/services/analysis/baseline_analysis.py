"""
Baseline analysis service for past 11 months predictions
"""
from typing import Optional
import logging

from app.services.prophet_service import ProphetService
from app.services.redis_client import RedisClient
from app.db.database import get_db
from app.repos.baseline_repo import BaselinePredictionRepository

logger = logging.getLogger(__name__)

# Initialize services
prophet_service = ProphetService()
redis_client = RedisClient()


async def run_baseline_analysis(
    file_id: str,
    csv_data,
    lock_token: Optional[str] = None
):
    """
    Background task to run baseline analysis for past 11 months

    Args:
        file_id: File ID
        csv_data: CSV data
        lock_token: Lock token for ownership verification
    """
    db = None
    try:
        # Get fresh DB session for background task
        db = next(get_db())

        logger.info(f"Starting baseline calculation for past 11 months for {file_id}")
        baseline_predictions = await prophet_service.calculate_baseline_predictions_async(csv_data)

        if baseline_predictions and baseline_predictions.get('baseline_months'):
            logger.info(f"Saving {len(baseline_predictions['baseline_months'])} months of baseline data")

            # Initialize baseline repository
            baseline_repo = BaselinePredictionRepository(db)

            # Collect all baseline data for bulk upsert
            all_baseline_data = []

            for month_key, month_data in baseline_predictions['baseline_months'].items():
                if month_data['status'] != 'completed':
                    continue

                baseline_year = month_data['year']
                baseline_month = month_data['month']
                cutoff_date = month_data.get('training_data_until', '').split('T')[0] if month_data.get('training_data_until') else None

                # Collect baseline for each category
                for category, cat_baseline in month_data.get('categories', {}).items():
                    all_baseline_data.append({
                        'category': category,
                        'year': baseline_year,
                        'month': baseline_month,
                        'predicted_amount': cat_baseline.get('predicted', 0),
                        'lower_bound': cat_baseline.get('lower_bound'),
                        'upper_bound': cat_baseline.get('upper_bound'),
                        'training_cutoff_date': cutoff_date
                    })

            # Bulk upsert all baselines at once (1 query instead of N×M)
            if all_baseline_data:
                baseline_repo.bulk_upsert_baselines(
                    file_id=file_id,
                    baseline_data=all_baseline_data
                )

            db.commit()
            logger.info(f"Baseline predictions saved for {file_id} ({len(all_baseline_data)} records)")

        # Release analysis lock after baseline completion
        redis_client.release_analysis_lock(file_id, lock_token)
        logger.info(f"All analysis completed for {file_id}, lock released")

    except Exception as e:
        logger.error(f"Baseline analysis failed for {file_id}: {str(e)}")
        # Release analysis lock even on failure
        redis_client.release_analysis_lock(file_id, lock_token)
    finally:
        if db:
            db.close()

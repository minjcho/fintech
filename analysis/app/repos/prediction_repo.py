"""
Repository for Prediction model
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import date

from app.repos.base_repo import BaseRepository
from app.db.models import Prediction


class PredictionRepository(BaseRepository[Prediction]):
    """Repository for managing predictions"""

    def __init__(self, db: Session):
        super().__init__(Prediction, db)

    def get_by_file_and_category(
        self,
        file_id: str,
        category: str,
        prediction_date: date
    ) -> Optional[Prediction]:
        """Get prediction by file_id, category, and date"""
        return self.db.query(Prediction).filter(
            Prediction.file_id == file_id,
            Prediction.category == category,
            Prediction.prediction_date == prediction_date
        ).first()

    def bulk_upsert_predictions(
        self,
        file_id: str,
        year: int,
        month: int,
        category_predictions: Dict[str, Dict[str, Any]]
    ):
        """
        Bulk upsert predictions for multiple categories in one query

        Args:
            file_id: File ID
            year: Year
            month: Month
            category_predictions: Dict of category -> prediction data
                {
                    'Food': {
                        'predicted': 100000,
                        'lower_bound': 80000,
                        'upper_bound': 120000
                    },
                    ...
                }
        """
        prediction_date = f"{year}-{month:02d}-01"

        data = []
        for category, pred_data in category_predictions.items():
            # Skip categories with errors
            if 'error' in pred_data:
                continue

            current_month = pred_data.get('current_month', {})
            if not current_month:
                continue

            data.append({
                'file_id': file_id,
                'category': category,
                'prediction_date': prediction_date,
                'predicted_amount': current_month.get('predicted', 0),
                'lower_bound': current_month.get('lower_bound'),
                'upper_bound': current_month.get('upper_bound')
            })

        if data:
            self.bulk_upsert(
                data,
                unique_keys=['file_id', 'category', 'prediction_date']
            )

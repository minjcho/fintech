"""
Repository for BaselinePrediction model
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import date

from app.repos.base_repo import BaseRepository
from app.db.models import BaselinePrediction


class BaselinePredictionRepository(BaseRepository[BaselinePrediction]):
    """Repository for managing baseline predictions"""

    def __init__(self, db: Session):
        super().__init__(BaselinePrediction, db)

    def get_by_file_category_date(
        self,
        file_id: str,
        category: str,
        year: int,
        month: int
    ) -> Optional[BaselinePrediction]:
        """Get baseline prediction by file_id, category, year, and month"""
        return self.db.query(BaselinePrediction).filter(
            BaselinePrediction.file_id == file_id,
            BaselinePrediction.category == category,
            BaselinePrediction.year == year,
            BaselinePrediction.month == month
        ).first()

    def bulk_upsert_baselines(
        self,
        file_id: str,
        baseline_data: List[Dict[str, Any]]
    ):
        """
        Bulk upsert baseline predictions for multiple categories/months

        Args:
            file_id: File ID
            baseline_data: List of dicts with baseline prediction data
                [
                    {
                        'category': 'Food',
                        'year': 2024,
                        'month': 10,
                        'predicted_amount': 100000,
                        'lower_bound': 80000,
                        'upper_bound': 120000,
                        'training_cutoff_date': '2024-09-30'
                    },
                    ...
                ]
        """
        if not baseline_data:
            return

        data = []
        for baseline in baseline_data:
            # Ensure predicted amount is not negative
            predicted_amount = max(0.0, baseline.get('predicted_amount', 0))

            data.append({
                'file_id': file_id,
                'category': baseline['category'],
                'year': baseline['year'],
                'month': baseline['month'],
                'predicted_amount': predicted_amount,
                'lower_bound': baseline.get('lower_bound'),
                'upper_bound': baseline.get('upper_bound'),
                'training_cutoff_date': baseline.get('training_cutoff_date')
            })

        self.bulk_upsert(
            data,
            unique_keys=['file_id', 'category', 'year', 'month']
        )

"""
Repository for LeakAnalysis model
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.repos.base_repo import BaseRepository
from app.db.models import LeakAnalysis


class LeakAnalysisRepository(BaseRepository[LeakAnalysis]):
    """Repository for managing leak analysis"""

    def __init__(self, db: Session):
        super().__init__(LeakAnalysis, db)

    def get_by_file_and_date(
        self,
        file_id: str,
        year: int,
        month: int
    ) -> Optional[LeakAnalysis]:
        """Get leak analysis by file_id, year, and month"""
        return self.db.query(LeakAnalysis).filter(
            LeakAnalysis.file_id == file_id,
            LeakAnalysis.year == year,
            LeakAnalysis.month == month
        ).first()

    def upsert_leak_analysis(
        self,
        file_id: str,
        year: int,
        month: int,
        actual_amount: Optional[float],
        predicted_amount: float,
        leak_amount: float,
        analysis_data: Dict[str, Any]
    ):
        """
        Upsert single leak analysis record

        Args:
            file_id: File ID
            year: Year
            month: Month
            actual_amount: Actual spending amount
            predicted_amount: Predicted spending amount
            leak_amount: Leak amount
            analysis_data: JSON data with category predictions
        """
        data = [{
            'file_id': file_id,
            'year': year,
            'month': month,
            'actual_amount': actual_amount,
            'predicted_amount': predicted_amount,
            'leak_amount': leak_amount,
            'analysis_data': analysis_data
        }]

        self.bulk_upsert(
            data,
            unique_keys=['file_id', 'year', 'month']
        )

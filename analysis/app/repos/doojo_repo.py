"""
Repository for DoojoAnalysis model
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.repos.base_repo import BaseRepository
from app.db.models import DoojoAnalysis


class DoojoAnalysisRepository(BaseRepository[DoojoAnalysis]):
    """Repository for managing doojo (stamp breaking) analysis"""

    def __init__(self, db: Session):
        super().__init__(DoojoAnalysis, db)

    def get_by_file_category_date(
        self,
        file_id: str,
        category: str,
        year: int,
        month: int
    ) -> Optional[DoojoAnalysis]:
        """Get doojo analysis by file_id, category, year, and month"""
        return self.db.query(DoojoAnalysis).filter(
            DoojoAnalysis.file_id == file_id,
            DoojoAnalysis.category == category,
            DoojoAnalysis.year == year,
            DoojoAnalysis.month == month
        ).first()

    def bulk_upsert_doojo_analysis(
        self,
        file_id: str,
        year: int,
        month: int,
        category_data: List[Dict[str, Any]]
    ):
        """
        Bulk upsert doojo analysis for multiple categories

        Args:
            file_id: File ID
            year: Year
            month: Month
            category_data: List of dicts with category analysis data
                [
                    {
                        'category': 'Food',
                        'min_amount': 50000,
                        'max_amount': 150000,
                        'current_threshold': 100000,
                        'real_amount': 120000,
                        'result': 'true'
                    },
                    ...
                ]
        """
        if not category_data:
            return

        data = []
        for cat_data in category_data:
            data.append({
                'file_id': file_id,
                'category': cat_data['category'],
                'year': year,
                'month': month,
                'min_amount': cat_data['min_amount'],
                'max_amount': cat_data['max_amount'],
                'current_threshold': cat_data['current_threshold'],
                'real_amount': cat_data.get('real_amount'),
                'result': cat_data.get('result')
            })

        self.bulk_upsert(
            data,
            unique_keys=['file_id', 'category', 'year', 'month']
        )

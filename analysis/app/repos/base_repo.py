"""
Base repository with common database operations
"""
from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert
import logging

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Base repository with bulk operations for MySQL"""

    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get single record by ID"""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def bulk_insert(self, objects: List[ModelType]):
        """Batch INSERT - use when records definitely don't exist"""
        self.db.bulk_save_objects(objects)
        self.db.flush()

    def bulk_upsert(self, data: List[Dict[str, Any]], unique_keys: List[str]):
        """
        Batch UPSERT using MySQL ON DUPLICATE KEY UPDATE

        Args:
            data: List of dicts with column values
            unique_keys: List of column names that form the unique constraint

        Example:
            repo.bulk_upsert(
                [{'file_id': '123', 'category': 'Food', 'amount': 100}],
                unique_keys=['file_id', 'category']
            )
        """
        if not data:
            return

        # Create INSERT statement
        stmt = insert(self.model).values(data)

        # Build update dict (all columns except unique keys)
        update_dict = {
            c.name: stmt.inserted[c.name]
            for c in self.model.__table__.columns
            if c.name not in unique_keys and c.name != 'id' and c.name != 'created_at'
        }

        # Add ON DUPLICATE KEY UPDATE
        stmt = stmt.on_duplicate_key_update(update_dict)

        # Execute
        self.db.execute(stmt)
        logger.debug(f"Bulk upserted {len(data)} records to {self.model.__tablename__}")

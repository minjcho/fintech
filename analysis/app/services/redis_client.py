"""
Redis client for managing analysis job status
"""
import redis
import json
import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for status management"""
    
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(os.getenv("REDIS_DB", 0))
        
        try:
            self.client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True
            )
            self.client.ping()
            logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
    
    def set_analysis_metadata(self, file_id: str, metadata: Dict):
        """Set analysis metadata for a file"""
        if not self.client:
            logger.warning("Redis not available, skipping metadata update")
            return
        
        try:
            # Set metadata
            meta_key = f"analysis:metadata:{file_id}"
            self.client.set(meta_key, json.dumps(metadata))
            
            # Set expiry (24 hours)
            self.client.expire(meta_key, 86400)
            
            logger.info(f"Set analysis metadata for {file_id}")
        except Exception as e:
            logger.error(f"Failed to set metadata: {e}")
    
    def get_csv_status(self, file_id: str) -> Optional[str]:
        """Get CSV processing status for a file"""
        if not self.client:
            return None
        
        try:
            status_key = f"csv:status:{file_id}"
            return self.client.get(status_key)
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return None
    
    def get_analysis_metadata(self, file_id: str) -> Optional[Dict]:
        """Get analysis metadata for a file"""
        if not self.client:
            return None
        
        try:
            meta_key = f"analysis:metadata:{file_id}"
            data = self.client.get(meta_key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return None
    
    def set_csv_status(self, file_id: str, status: str):
        """Update CSV file status in csv-manager's Redis namespace"""
        if not self.client:
            logger.warning("Redis not available, skipping CSV status update")
            return
        
        try:
            # Update status in csv-manager's namespace
            status_key = f"csv:status:{file_id}"
            self.client.set(status_key, status)
            logger.info(f"Updated CSV status for {file_id}: {status}")
        except Exception as e:
            logger.error(f"Failed to update CSV status: {e}")
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get file metadata from csv-manager's Redis namespace"""
        if not self.client:
            return None
        
        try:
            # Try to get metadata by ID
            meta_key = f"csv:metadata:id:{file_id}"
            data = self.client.get(meta_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get file metadata: {e}")
            return None
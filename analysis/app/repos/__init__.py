"""
Repository pattern for database operations
"""
from app.repos.base_repo import BaseRepository
from app.repos.prediction_repo import PredictionRepository
from app.repos.leak_repo import LeakAnalysisRepository
from app.repos.doojo_repo import DoojoAnalysisRepository
from app.repos.baseline_repo import BaselinePredictionRepository

__all__ = [
    'BaseRepository',
    'PredictionRepository',
    'LeakAnalysisRepository',
    'DoojoAnalysisRepository',
    'BaselinePredictionRepository'
]

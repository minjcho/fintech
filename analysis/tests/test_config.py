"""
Unit tests for configuration settings
"""
import pytest
from unittest.mock import patch
from app.core.config import Settings


class TestDatabasePoolConfiguration:
    """Test database connection pool settings"""

    def test_pool_size_calculation_default(self):
        """Test pool size calculation with default workers (4)"""
        settings = Settings()
        assert settings.UVICORN_WORKERS == 4
        assert settings.DB_POOL_SIZE == 20  # 4 * 5
        assert settings.DB_MAX_OVERFLOW == 40  # 4 * 10

    def test_pool_size_calculation_with_2_workers(self):
        """Test pool size calculation with 2 workers"""
        with patch.dict('os.environ', {'UVICORN_WORKERS': '2'}):
            settings = Settings()
            assert settings.UVICORN_WORKERS == 2
            assert settings.DB_POOL_SIZE == 10  # 2 * 5
            assert settings.DB_MAX_OVERFLOW == 20  # 2 * 10

    def test_pool_size_calculation_with_8_workers(self):
        """Test pool size calculation with 8 workers"""
        with patch.dict('os.environ', {'UVICORN_WORKERS': '8'}):
            settings = Settings()
            assert settings.UVICORN_WORKERS == 8
            assert settings.DB_POOL_SIZE == 40  # 8 * 5
            assert settings.DB_MAX_OVERFLOW == 80  # 8 * 10

    def test_pool_size_minimum_values(self):
        """Test that pool size has minimum values even with 1 worker"""
        with patch.dict('os.environ', {'UVICORN_WORKERS': '1'}):
            settings = Settings()
            assert settings.UVICORN_WORKERS == 1
            # Minimum should be enforced by max() function
            assert settings.DB_POOL_SIZE == 10  # max(10, 1 * 5) = 10
            assert settings.DB_MAX_OVERFLOW == 20  # max(20, 1 * 10) = 20

    def test_total_connections_calculation(self):
        """Test total connections available"""
        settings = Settings()
        total_connections = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW

        # With 4 workers: 20 + 40 = 60 total connections
        assert total_connections == 60

        # Verify this is NOT multiplied by worker count
        # (pool is shared across workers)
        assert total_connections != settings.UVICORN_WORKERS * 60

    def test_pool_recycle_default(self):
        """Test pool recycle default is 1 hour"""
        settings = Settings()
        assert settings.DB_POOL_RECYCLE == 3600  # 1 hour

    def test_pool_timeout_default(self):
        """Test pool timeout default is 30 seconds"""
        settings = Settings()
        assert settings.DB_POOL_TIMEOUT == 30

    def test_connect_timeout_default(self):
        """Test connect timeout default is 10 seconds"""
        settings = Settings()
        assert settings.DB_CONNECT_TIMEOUT == 10

    def test_pool_settings_from_environment(self):
        """Test that pool settings can be overridden by environment variables"""
        with patch.dict('os.environ', {
            'DB_POOL_RECYCLE': '7200',
            'DB_POOL_TIMEOUT': '60',
            'DB_CONNECT_TIMEOUT': '20'
        }):
            settings = Settings()
            assert settings.DB_POOL_RECYCLE == 7200
            assert settings.DB_POOL_TIMEOUT == 60
            assert settings.DB_CONNECT_TIMEOUT == 20


class TestUvicornWorkerConfiguration:
    """Test Uvicorn worker settings"""

    def test_default_workers(self):
        """Test default number of workers is 4"""
        settings = Settings()
        assert settings.UVICORN_WORKERS == 4

    def test_workers_from_environment(self):
        """Test workers can be set from environment variable"""
        with patch.dict('os.environ', {'UVICORN_WORKERS': '8'}):
            settings = Settings()
            assert settings.UVICORN_WORKERS == 8

    def test_workers_affects_pool_size(self):
        """Test that changing workers affects pool size calculation"""
        # 2 workers
        with patch.dict('os.environ', {'UVICORN_WORKERS': '2'}):
            settings = Settings()
            pool_2workers = settings.DB_POOL_SIZE

        # 8 workers
        with patch.dict('os.environ', {'UVICORN_WORKERS': '8'}):
            settings = Settings()
            pool_8workers = settings.DB_POOL_SIZE

        # Pool size should be different
        assert pool_2workers < pool_8workers
        assert pool_8workers == pool_2workers * 4  # 10 vs 40

"""
Unit tests for database connection and pool configuration
"""
import pytest
from unittest.mock import patch, MagicMock
import ssl


class TestDatabaseEngineConfiguration:
    """Test database engine and pool setup"""

    @patch('app.db.database.create_engine')
    def test_engine_created_with_correct_pool_settings(self, mock_create_engine):
        """Test that engine is created with correct pool parameters"""
        # Mock the settings
        with patch('app.db.database.settings') as mock_settings:
            mock_settings.DATABASE_URL = "mysql+pymysql://test:test@localhost/test"
            mock_settings.DB_POOL_SIZE = 20
            mock_settings.DB_MAX_OVERFLOW = 40
            mock_settings.DB_POOL_RECYCLE = 3600
            mock_settings.DB_POOL_TIMEOUT = 30
            mock_settings.DB_CONNECT_TIMEOUT = 10

            # Import after patching to trigger engine creation
            import importlib
            import app.db.database as db_module
            importlib.reload(db_module)

            # Verify create_engine was called with correct parameters
            assert mock_create_engine.called
            call_args = mock_create_engine.call_args

            # Check pool_size and max_overflow
            assert call_args.kwargs['pool_size'] == 20
            assert call_args.kwargs['max_overflow'] == 40
            assert call_args.kwargs['pool_recycle'] == 3600
            assert call_args.kwargs['pool_timeout'] == 30

    @patch('app.db.database.os.getenv')
    def test_ssl_context_development_mode(self, mock_getenv):
        """Test SSL context is insecure in development mode"""
        mock_getenv.return_value = "development"

        # Re-import to trigger SSL context creation
        import importlib
        import app.db.database as db_module
        importlib.reload(db_module)

        ssl_context = db_module.ssl_context

        # In development, SSL verification should be disabled
        assert ssl_context.check_hostname == False
        assert ssl_context.verify_mode == ssl.CERT_NONE

    @patch('app.db.database.os.getenv')
    def test_ssl_context_production_mode(self, mock_getenv):
        """Test SSL context is secure in production mode"""
        mock_getenv.return_value = "production"

        # Re-import to trigger SSL context creation
        import importlib
        import app.db.database as db_module
        importlib.reload(db_module)

        ssl_context = db_module.ssl_context

        # In production, SSL verification should be enabled
        assert ssl_context.check_hostname == True
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED

    def test_pool_pre_ping_enabled(self):
        """Test that pool_pre_ping is enabled for connection health checks"""
        with patch('app.db.database.create_engine') as mock_create_engine:
            with patch('app.db.database.settings') as mock_settings:
                mock_settings.DATABASE_URL = "mysql+pymysql://test:test@localhost/test"
                mock_settings.DB_POOL_SIZE = 20
                mock_settings.DB_MAX_OVERFLOW = 40
                mock_settings.DB_POOL_RECYCLE = 3600
                mock_settings.DB_POOL_TIMEOUT = 30
                mock_settings.DB_CONNECT_TIMEOUT = 10

                import importlib
                import app.db.database as db_module
                importlib.reload(db_module)

                call_args = mock_create_engine.call_args
                assert call_args.kwargs['pool_pre_ping'] == True

    @patch('app.db.database.create_engine')
    def test_connect_timeout_in_connect_args(self, mock_create_engine):
        """Test that connect_timeout is passed in connect_args"""
        with patch('app.db.database.settings') as mock_settings:
            mock_settings.DATABASE_URL = "mysql+pymysql://test:test@localhost/test"
            mock_settings.DB_POOL_SIZE = 20
            mock_settings.DB_MAX_OVERFLOW = 40
            mock_settings.DB_POOL_RECYCLE = 3600
            mock_settings.DB_POOL_TIMEOUT = 30
            mock_settings.DB_CONNECT_TIMEOUT = 10

            import importlib
            import app.db.database as db_module
            importlib.reload(db_module)

            call_args = mock_create_engine.call_args
            connect_args = call_args.kwargs['connect_args']

            assert 'connect_timeout' in connect_args
            assert connect_args['connect_timeout'] == 10

    @patch('app.db.database.create_engine')
    @patch('app.db.database.logger')
    def test_logging_on_successful_engine_creation(self, mock_logger, mock_create_engine):
        """Test that configuration is logged on successful engine creation"""
        mock_create_engine.return_value = MagicMock()

        with patch('app.db.database.settings') as mock_settings:
            mock_settings.DATABASE_URL = "mysql+pymysql://test:test@localhost/test"
            mock_settings.DB_POOL_SIZE = 20
            mock_settings.DB_MAX_OVERFLOW = 40
            mock_settings.DB_POOL_RECYCLE = 3600
            mock_settings.DB_POOL_TIMEOUT = 30
            mock_settings.DB_CONNECT_TIMEOUT = 10

            import importlib
            import app.db.database as db_module
            importlib.reload(db_module)

            # Verify info logging was called
            assert mock_logger.info.called
            # Check that pool configuration was logged
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any('pool' in str(call).lower() for call in log_calls)

    @patch('app.db.database.create_engine')
    @patch('app.db.database.logger')
    def test_logging_on_engine_creation_failure(self, mock_logger, mock_create_engine):
        """Test that errors are logged when engine creation fails"""
        mock_create_engine.side_effect = Exception("Database connection failed")

        with patch('app.db.database.settings') as mock_settings:
            mock_settings.DATABASE_URL = "mysql+pymysql://invalid:invalid@localhost/test"
            mock_settings.DB_POOL_SIZE = 20
            mock_settings.DB_MAX_OVERFLOW = 40
            mock_settings.DB_POOL_RECYCLE = 3600
            mock_settings.DB_POOL_TIMEOUT = 30
            mock_settings.DB_CONNECT_TIMEOUT = 10

            with pytest.raises(Exception, match="Database connection failed"):
                import importlib
                import app.db.database as db_module
                importlib.reload(db_module)

            # Verify error logging was called
            assert mock_logger.error.called
            error_calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any('Failed to create database engine' in str(call) for call in error_calls)


class TestSessionFactory:
    """Test SQLAlchemy session factory"""

    @patch('app.db.database.engine')
    def test_session_factory_binds_to_engine(self, mock_engine):
        """Test that SessionLocal is bound to the engine"""
        with patch('app.db.database.sessionmaker') as mock_sessionmaker:
            import importlib
            import app.db.database as db_module
            importlib.reload(db_module)

            # Verify sessionmaker was called with correct parameters
            call_args = mock_sessionmaker.call_args
            assert call_args.kwargs['bind'] == mock_engine
            assert call_args.kwargs['autocommit'] == False
            assert call_args.kwargs['autoflush'] == False


class TestGetDbDependency:
    """Test the get_db dependency function"""

    @patch('app.db.database.SessionLocal')
    def test_get_db_yields_session(self, mock_session_local):
        """Test that get_db yields a database session"""
        from app.db.database import get_db

        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Use the generator
        gen = get_db()
        session = next(gen)

        assert session == mock_session

    @patch('app.db.database.SessionLocal')
    def test_get_db_closes_session_on_cleanup(self, mock_session_local):
        """Test that get_db closes the session in finally block"""
        from app.db.database import get_db

        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Use the generator and let it cleanup
        gen = get_db()
        session = next(gen)

        try:
            next(gen)
        except StopIteration:
            pass

        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch('app.db.database.SessionLocal')
    def test_get_db_closes_session_even_on_exception(self, mock_session_local):
        """Test that session is closed even if exception occurs"""
        from app.db.database import get_db

        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Simulate exception during session usage
        gen = get_db()
        session = next(gen)

        try:
            gen.throw(Exception("Simulated error"))
        except Exception:
            pass

        # Session should still be closed
        mock_session.close.assert_called_once()

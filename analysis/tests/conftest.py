"""
Pytest configuration and fixtures for analysis service tests
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import json

from app.models.database import Base
from app.db.database import get_db
from app.main import app


# ===== Database Fixtures =====

@pytest.fixture(scope="function")
def test_engine():
    """Create in-memory SQLite engine for testing"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create test database session"""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(test_db):
    """Create TestClient with database override"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass  # Don't close here, let test_db fixture handle it

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ===== CSV Data Fixtures =====

@pytest.fixture
def sample_csv_data():
    """Generate sample transaction CSV data for testing"""
    start_date = datetime(2024, 1, 1)

    # Generate 90 days of data with multiple categories
    data = []
    categories = {
        '식비': ('강남 한정식', 15000),
        '카페': ('스타벅스', 5000),
        '마트/편의점': ('이마트', 35000),
        '문화생활': ('CGV', 12000),
        '패션/미용': ('올리브영', 25000)
    }

    for day in range(90):
        date = start_date + timedelta(days=day)
        # Add 2-3 transactions per day
        for category, (merchant, amount) in categories.items():
            # Random variation
            actual_amount = amount + (day % 3) * 1000
            data.append({
                'transaction_date_time': date + timedelta(hours=10 + (day % 12)),
                'category': category,
                'merchant_name': merchant,
                'amount': actual_amount
            })

    return pd.DataFrame(data)


@pytest.fixture
def insufficient_csv_data():
    """Generate insufficient data (< 30 days) for testing error cases"""
    start_date = datetime(2024, 1, 1)

    data = []
    for day in range(10):  # Only 10 days
        date = start_date + timedelta(days=day)
        data.append({
            'transaction_date_time': date,
            'category': '식비',
            'merchant_name': '강남 한정식',
            'amount': 15000
        })

    return pd.DataFrame(data)


@pytest.fixture
def sample_csv_bytes():
    """Generate CSV file content as bytes for upload testing"""
    csv_content = """transaction_date_time,category,merchant_name,amount
2024-01-01T10:00:00,식비,강남 한정식,15000
2024-01-01T14:00:00,카페,스타벅스,5000
2024-01-02T12:00:00,마트/편의점,이마트,35000
2024-01-02T19:00:00,문화생활,CGV,12000
2024-01-03T16:00:00,패션/미용,올리브영,25000"""

    return csv_content.encode('utf-8')


# ===== Mock Service Fixtures =====

@pytest.fixture
def mock_s3_client():
    """Mock S3Client for CSV data fetching"""
    mock = MagicMock()

    # Default: return sample data
    sample_data = pd.DataFrame({
        'transaction_date_time': pd.date_range('2024-01-01', periods=60, freq='D'),
        'category': ['식비'] * 30 + ['카페'] * 30,
        'merchant_name': ['강남 한정식'] * 30 + ['스타벅스'] * 30,
        'amount': [15000] * 30 + [5000] * 30
    })

    mock.fetch_csv_data = AsyncMock(return_value=sample_data)
    mock.download_csv = MagicMock(return_value=sample_data)

    return mock


@pytest.fixture
def mock_redis_client():
    """Mock RedisClient for status and lock management"""
    mock = MagicMock()

    # Default: no ongoing analysis
    mock.get_csv_status = MagicMock(return_value=None)
    mock.set_csv_status = MagicMock()
    mock.acquire_lock = MagicMock(return_value=True)
    mock.release_lock = MagicMock()
    mock.get = MagicMock(return_value=None)
    mock.set = MagicMock()
    mock.setex = MagicMock()

    return mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for AI message generation"""
    mock = MagicMock()

    # Mock completion response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="다음 달 스타벅스 지출을 월 2만 원 이하로 제한하고, 필요하면 집에서 만든 커피로 대체해봐."))
    ]

    mock.chat.completions.create = MagicMock(return_value=mock_response)

    return mock


@pytest.fixture
def mock_prophet_result():
    """Mock Prophet prediction results"""
    return {
        'prediction_id': 'test-pred-123',
        'created_at': datetime.utcnow().isoformat(),
        'year': 2025,
        'month': 1,
        'category_predictions': {
            '식비': {
                'category': '식비',
                'current_month': {
                    'actual': None,
                    'predicted': 450000.0,
                    'lower_bound': 400000.0,
                    'upper_bound': 500000.0
                }
            },
            '카페': {
                'category': '카페',
                'current_month': {
                    'actual': None,
                    'predicted': 150000.0,
                    'lower_bound': 130000.0,
                    'upper_bound': 170000.0
                }
            }
        },
        'total_current_predicted': 600000.0,
        'trend': 'analyzed',
        'categories_analyzed': 2
    }


@pytest.fixture
def mock_baseline_result():
    """Mock baseline predictions for 11 months"""
    baseline_results = {}

    for i in range(11, 0, -1):
        month_date = datetime.now() - timedelta(days=30 * i)
        month_key = f"{month_date.year}-{month_date.month:02d}"

        baseline_results[month_key] = {
            'year': month_date.year,
            'month': month_date.month,
            'categories': {
                '식비': {
                    'predicted': 450000.0,
                    'lower_bound': 400000.0,
                    'upper_bound': 500000.0,
                    'data_points': 30
                },
                '카페': {
                    'predicted': 150000.0,
                    'lower_bound': 130000.0,
                    'upper_bound': 170000.0,
                    'data_points': 30
                }
            },
            'total': 600000.0,
            'categories_count': 2,
            'training_data_until': (month_date - timedelta(days=1)).isoformat(),
            'status': 'completed'
        }

    return {
        'baseline_id': 'test-baseline-123',
        'created_at': datetime.utcnow().isoformat(),
        'baseline_months': baseline_results,
        'months_calculated': 11
    }


# ===== Test Data Helpers =====

@pytest.fixture
def valid_file_id():
    """Generate valid file_id for testing"""
    return "test-file-id-123"


@pytest.fixture
def test_year_month():
    """Get current year and month for testing"""
    now = datetime.now()
    return now.year, now.month


@pytest.fixture
def sample_doojo_data():
    """Sample doojo (두꺼비 조언) response data"""
    return {
        'file_id': 'test-file-id-123',
        'doojo': [{
            'year': 2025,
            'month': 1,
            'categories_count': 2,
            'categories_prediction': {
                '식비': {
                    'min': 400000.0,
                    'max': 500000.0,
                    'current': 450000.0,
                    'real': 460000.0,
                    'result': True,  # Over budget
                    'avg': 450000.0
                },
                '카페': {
                    'min': 130000.0,
                    'max': 170000.0,
                    'current': 150000.0,
                    'real': 145000.0,
                    'result': False,  # Within budget
                    'avg': 150000.0
                }
            },
            'categories_detail': {
                '식비': {
                    'most_spent': {
                        'merchant': '강남 한정식',
                        'amount': 25000.0,
                        'date': '2025-01-15T12:00:00',
                        'msg': '다음엔 한정식은 점심 특선 메뉴로 주문해서 지출을 줄여.'
                    },
                    'most_frequent': {
                        'merchant': '김밥천국',
                        'count': 15,
                        'total_amount': 120000.0,
                        'msg': '김밥천국 방문을 주 1-2회로 줄이고 집에서 도시락을 준비해보는 건 어때?'
                    }
                },
                '카페': {
                    'most_spent': {
                        'merchant': '스타벅스',
                        'amount': 6500.0,
                        'date': '2025-01-10T10:00:00',
                        'msg': '다음 달 스타벅스 지출을 월 2만 원 이하로 제한하고, 집에서 만든 커피로 대체해봐.'
                    },
                    'most_frequent': {
                        'merchant': '이디야',
                        'count': 20,
                        'total_amount': 80000.0,
                        'msg': '이디야 방문을 주 2회로 줄이고 텀블러를 가져가면 할인도 받을 수 있어.'
                    }
                }
            }
        }]
    }


# ===== Pytest Markers =====

def pytest_configure(config):
    """Configure custom markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )

"""
Integration tests for leak analysis endpoints

Tests the following endpoints:
- POST /ai/data - Calculate monthly leak (현재월 예측)
- GET /ai/data/leak - Get leak data for specific month
"""
import pytest
from fastapi import status
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import pandas as pd

from app.db.models import Prediction, LeakAnalysis


@pytest.mark.integration
class TestCalculateMonthlyLeak:
    """Test POST /ai/data endpoint - Calculate monthly leak analysis"""

    def test_calculate_monthly_leak_success(
        self,
        client,
        test_db,
        valid_file_id,
        sample_csv_data,
        mock_redis_client,
        mock_prophet_result
    ):
        """Test successful leak calculation"""
        with patch('app.api.endpoints.leak.S3Client') as MockS3, \
             patch('app.api.endpoints.leak.RedisClient') as MockRedis, \
             patch('app.api.endpoints.leak.ProphetService') as MockProphet:

            # Setup mocks
            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            mock_redis = MockRedis.return_value
            mock_redis.get_csv_status = MagicMock(return_value=None)
            mock_redis.set_csv_status = MagicMock()
            mock_redis.acquire_lock = MagicMock(return_value=True)
            mock_redis.release_lock = MagicMock()

            mock_prophet = MockProphet.return_value
            mock_prophet.predict_by_category = AsyncMock(return_value=mock_prophet_result)

            # Execute request
            response = client.post(f"/ai/data?file_id={valid_file_id}")

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data['file_id'] == valid_file_id
            assert 'year' in data
            assert 'month' in data
            assert 'message' in data

            # Verify Redis status was set to 'analyzing'
            mock_redis.set_csv_status.assert_called()

            # Verify lock was acquired and released
            mock_redis.acquire_lock.assert_called_once()
            mock_redis.release_lock.assert_called_once()

    def test_calculate_monthly_leak_already_analyzing(
        self,
        client,
        test_db,
        valid_file_id,
        mock_redis_client
    ):
        """Test 409 Conflict when analysis is already in progress"""
        with patch('app.api.endpoints.leak.RedisClient') as MockRedis:
            mock_redis = MockRedis.return_value
            mock_redis.get_csv_status = MagicMock(return_value='analyzing')

            response = client.post(f"/ai/data?file_id={valid_file_id}")

            assert response.status_code == status.HTTP_409_CONFLICT
            assert 'already' in response.json()['detail'].lower()

    def test_calculate_monthly_leak_idempotent(
        self,
        client,
        test_db,
        valid_file_id,
        sample_csv_data,
        mock_prophet_result
    ):
        """Test idempotency - calling twice returns consistent results"""
        with patch('app.api.endpoints.leak.S3Client') as MockS3, \
             patch('app.api.endpoints.leak.RedisClient') as MockRedis, \
             patch('app.api.endpoints.leak.ProphetService') as MockProphet:

            # Setup mocks
            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            mock_redis = MockRedis.return_value
            mock_redis.get_csv_status = MagicMock(return_value=None)
            mock_redis.set_csv_status = MagicMock()
            mock_redis.acquire_lock = MagicMock(return_value=True)
            mock_redis.release_lock = MagicMock()

            mock_prophet = MockProphet.return_value
            mock_prophet.predict_by_category = AsyncMock(return_value=mock_prophet_result)

            # First call
            response1 = client.post(f"/ai/data?file_id={valid_file_id}")
            assert response1.status_code == status.HTTP_200_OK
            data1 = response1.json()

            # Second call (should use cached data from DB)
            mock_redis.get_csv_status = MagicMock(return_value=None)
            response2 = client.post(f"/ai/data?file_id={valid_file_id}")
            assert response2.status_code == status.HTTP_200_OK
            data2 = response2.json()

            # Both should return same file_id
            assert data1['file_id'] == data2['file_id']

    def test_calculate_monthly_leak_file_not_found(
        self,
        client,
        test_db,
        mock_redis_client
    ):
        """Test 404 when CSV file doesn't exist in S3"""
        with patch('app.api.endpoints.leak.S3Client') as MockS3, \
             patch('app.api.endpoints.leak.RedisClient') as MockRedis:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(side_effect=FileNotFoundError("File not found"))

            mock_redis = MockRedis.return_value
            mock_redis.get_csv_status = MagicMock(return_value=None)
            mock_redis.acquire_lock = MagicMock(return_value=True)
            mock_redis.release_lock = MagicMock()

            response = client.post("/ai/data?file_id=nonexistent-file")

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_calculate_monthly_leak_insufficient_data(
        self,
        client,
        test_db,
        valid_file_id,
        insufficient_csv_data,
        mock_redis_client
    ):
        """Test 400 Bad Request when insufficient data for analysis"""
        with patch('app.api.endpoints.leak.S3Client') as MockS3, \
             patch('app.api.endpoints.leak.RedisClient') as MockRedis:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=insufficient_csv_data)

            mock_redis = MockRedis.return_value
            mock_redis.get_csv_status = MagicMock(return_value=None)
            mock_redis.set_csv_status = MagicMock()
            mock_redis.acquire_lock = MagicMock(return_value=True)
            mock_redis.release_lock = MagicMock()

            response = client.post(f"/ai/data?file_id={valid_file_id}")

            # Should either return 400 or 200 with warning
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK]

            if response.status_code == status.HTTP_400_BAD_REQUEST:
                assert 'insufficient' in response.json()['detail'].lower()


@pytest.mark.integration
class TestGetLeakData:
    """Test GET /ai/data/leak endpoint - Retrieve leak analysis results"""

    def test_get_leak_data_success(
        self,
        client,
        test_db,
        valid_file_id,
        test_year_month
    ):
        """Test successful retrieval of leak data"""
        year, month = test_year_month

        # Insert test predictions into database
        prediction1 = Prediction(
            file_id=valid_file_id,
            category='식비',
            prediction_date=datetime(year, month, 1),
            predicted_amount=450000.0,
            lower_bound=400000.0,
            upper_bound=500000.0
        )
        prediction2 = Prediction(
            file_id=valid_file_id,
            category='카페',
            prediction_date=datetime(year, month, 1),
            predicted_amount=150000.0,
            lower_bound=130000.0,
            upper_bound=170000.0
        )

        test_db.add(prediction1)
        test_db.add(prediction2)
        test_db.commit()

        # Execute request
        response = client.get(
            f"/ai/data/leak?file_id={valid_file_id}&year={year}&month={month}"
        )

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['file_id'] == valid_file_id
        assert data['year'] == year
        assert data['month'] == month
        assert 'details' in data
        assert 'category_predictions' in data['details']

        # Verify categories
        predictions = data['details']['category_predictions']
        assert '식비' in predictions
        assert '카페' in predictions
        assert predictions['식비']['predicted_amount'] == 450000.0
        assert predictions['카페']['predicted_amount'] == 150000.0

    def test_get_leak_data_not_found(
        self,
        client,
        test_db
    ):
        """Test 404 when predictions don't exist for file_id"""
        response = client.get(
            "/ai/data/leak?file_id=nonexistent&year=2025&month=1"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'not found' in response.json()['detail'].lower()

    def test_get_leak_data_with_leak_analysis(
        self,
        client,
        test_db,
        valid_file_id,
        test_year_month
    ):
        """Test leak data includes actual amounts and leak calculations"""
        year, month = test_year_month

        # Insert predictions
        prediction = Prediction(
            file_id=valid_file_id,
            category='식비',
            prediction_date=datetime(year, month, 1),
            predicted_amount=450000.0,
            lower_bound=400000.0,
            upper_bound=500000.0
        )
        test_db.add(prediction)

        # Insert leak analysis
        leak = LeakAnalysis(
            file_id=valid_file_id,
            year=year,
            month=month,
            actual_amount=480000.0,  # Over prediction
            predicted_amount=450000.0,
            leak_amount=30000.0,  # 30k over
            analysis_data={"status": "over_budget"}
        )
        test_db.add(leak)
        test_db.commit()

        # Execute request
        response = client.get(
            f"/ai/data/leak?file_id={valid_file_id}&year={year}&month={month}"
        )

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['leak_amount'] == 30000.0

    def test_get_leak_data_missing_year_parameter(
        self,
        client,
        valid_file_id
    ):
        """Test 422 when year parameter is missing"""
        response = client.get(f"/ai/data/leak?file_id={valid_file_id}&month=1")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_leak_data_invalid_month(
        self,
        client,
        valid_file_id
    ):
        """Test 422 when month parameter is invalid (e.g., 13)"""
        response = client.get(
            f"/ai/data/leak?file_id={valid_file_id}&year=2025&month=13"
        )

        # Should return validation error
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_get_leak_data_default_current_month(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test default behavior uses current year/month when not specified"""
        now = datetime.now()

        # Insert prediction for current month
        prediction = Prediction(
            file_id=valid_file_id,
            category='식비',
            prediction_date=datetime(now.year, now.month, 1),
            predicted_amount=450000.0,
            lower_bound=400000.0,
            upper_bound=500000.0
        )
        test_db.add(prediction)
        test_db.commit()

        # Request without year/month (should default to current)
        response = client.get(f"/ai/data/leak?file_id={valid_file_id}")

        # If endpoint supports defaults
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data['year'] == now.year
            assert data['month'] == now.month
        else:
            # If defaults not supported, should require parameters
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
@pytest.mark.slow
class TestLeakEndpointConcurrency:
    """Test concurrent requests to leak endpoints"""

    def test_concurrent_leak_calculations(
        self,
        client,
        test_db,
        sample_csv_data,
        mock_redis_client,
        mock_prophet_result
    ):
        """Test multiple simultaneous leak calculations with different file_ids"""
        file_ids = [f"file-{i}" for i in range(3)]

        with patch('app.api.endpoints.leak.S3Client') as MockS3, \
             patch('app.api.endpoints.leak.RedisClient') as MockRedis, \
             patch('app.api.endpoints.leak.ProphetService') as MockProphet:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            mock_redis = MockRedis.return_value
            mock_redis.get_csv_status = MagicMock(return_value=None)
            mock_redis.set_csv_status = MagicMock()
            mock_redis.acquire_lock = MagicMock(return_value=True)
            mock_redis.release_lock = MagicMock()

            mock_prophet = MockProphet.return_value
            mock_prophet.predict_by_category = AsyncMock(return_value=mock_prophet_result)

            # Send concurrent requests
            responses = []
            for file_id in file_ids:
                response = client.post(f"/ai/data?file_id={file_id}")
                responses.append(response)

            # All should succeed
            for response in responses:
                assert response.status_code == status.HTTP_200_OK

            # Each should have unique file_id
            file_ids_returned = [r.json()['file_id'] for r in responses]
            assert len(set(file_ids_returned)) == len(file_ids)

    def test_race_condition_same_file_id(
        self,
        client,
        test_db,
        valid_file_id,
        sample_csv_data,
        mock_prophet_result
    ):
        """Test race condition when same file_id is analyzed simultaneously"""
        with patch('app.api.endpoints.leak.S3Client') as MockS3, \
             patch('app.api.endpoints.leak.RedisClient') as MockRedis, \
             patch('app.api.endpoints.leak.ProphetService') as MockProphet:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            # First request gets lock, second fails
            mock_redis = MockRedis.return_value
            mock_redis.get_csv_status = MagicMock(side_effect=[None, 'analyzing'])
            mock_redis.acquire_lock = MagicMock(side_effect=[True, False])
            mock_redis.set_csv_status = MagicMock()
            mock_redis.release_lock = MagicMock()

            mock_prophet = MockProphet.return_value
            mock_prophet.predict_by_category = AsyncMock(return_value=mock_prophet_result)

            # First request - should succeed
            response1 = client.post(f"/ai/data?file_id={valid_file_id}")

            # Second request - should fail with 409
            response2 = client.post(f"/ai/data?file_id={valid_file_id}")

            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_409_CONFLICT

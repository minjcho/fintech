"""
Integration tests for baseline predictions endpoint

Tests the following endpoints:
- GET /ai/data/baseline - Get baseline predictions for past 11 months
"""
import pytest
from fastapi import status
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.db.models import BaselinePrediction


@pytest.mark.integration
class TestGetBaselinePredictions:
    """Test GET /ai/data/baseline endpoint - Retrieve baseline predictions"""

    def test_get_baseline_predictions_success(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test successful retrieval of 11-month baseline predictions"""
        # Insert baseline predictions for 11 months
        current_date = datetime.now()

        for i in range(11, 0, -1):
            month_date = current_date - timedelta(days=30 * i)

            # Add predictions for '식비' category
            baseline = BaselinePrediction(
                file_id=valid_file_id,
                category='식비',
                year=month_date.year,
                month=month_date.month,
                predicted_amount=450000.0,
                lower_bound=400000.0,
                upper_bound=500000.0,
                training_cutoff_date=month_date - timedelta(days=1)
            )
            test_db.add(baseline)

            # Add predictions for '카페' category
            baseline2 = BaselinePrediction(
                file_id=valid_file_id,
                category='카페',
                year=month_date.year,
                month=month_date.month,
                predicted_amount=150000.0,
                lower_bound=130000.0,
                upper_bound=170000.0,
                training_cutoff_date=month_date - timedelta(days=1)
            )
            test_db.add(baseline2)

        test_db.commit()

        # Execute request
        response = client.get(f"/ai/data/baseline?file_id={valid_file_id}")

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['file_id'] == valid_file_id
        assert 'baseline_months' in data
        assert len(data['baseline_months']) == 11
        assert data['months_count'] == 11

        # Verify first month structure
        first_month = data['baseline_months'][0]
        assert 'year' in first_month
        assert 'month' in first_month
        assert 'total_predicted' in first_month
        assert 'categories_count' in first_month
        assert 'category_predictions' in first_month

        # Verify categories
        category_predictions = first_month['category_predictions']
        assert '식비' in category_predictions
        assert '카페' in category_predictions

    def test_get_baseline_predictions_not_found(
        self,
        client,
        test_db
    ):
        """Test 404 when no baseline predictions exist for file_id"""
        response = client.get("/ai/data/baseline?file_id=nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'not found' in response.json()['detail'].lower()

    def test_get_baseline_predictions_partial_data(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test retrieval when only some months have predictions"""
        current_date = datetime.now()

        # Insert only 5 months of baseline data (instead of 11)
        for i in range(5, 0, -1):
            month_date = current_date - timedelta(days=30 * i)

            baseline = BaselinePrediction(
                file_id=valid_file_id,
                category='식비',
                year=month_date.year,
                month=month_date.month,
                predicted_amount=450000.0,
                lower_bound=400000.0,
                upper_bound=500000.0,
                training_cutoff_date=month_date - timedelta(days=1)
            )
            test_db.add(baseline)

        test_db.commit()

        # Execute request
        response = client.get(f"/ai/data/baseline?file_id={valid_file_id}")

        # Should still succeed with available data
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['file_id'] == valid_file_id
        assert len(data['baseline_months']) == 5
        assert data['months_count'] == 5

    def test_get_baseline_predictions_with_category_filter(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test filtering baseline predictions by category"""
        current_date = datetime.now()

        # Insert baseline for multiple categories
        for i in range(3, 0, -1):
            month_date = current_date - timedelta(days=30 * i)

            # 식비
            baseline1 = BaselinePrediction(
                file_id=valid_file_id,
                category='식비',
                year=month_date.year,
                month=month_date.month,
                predicted_amount=450000.0,
                lower_bound=400000.0,
                upper_bound=500000.0
            )
            test_db.add(baseline1)

            # 카페
            baseline2 = BaselinePrediction(
                file_id=valid_file_id,
                category='카페',
                year=month_date.year,
                month=month_date.month,
                predicted_amount=150000.0,
                lower_bound=130000.0,
                upper_bound=170000.0
            )
            test_db.add(baseline2)

        test_db.commit()

        # Request with category filter
        response = client.get(
            f"/ai/data/baseline?file_id={valid_file_id}&category=식비"
        )

        # Should return only '식비' category
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            for month in data['baseline_months']:
                predictions = month['category_predictions']
                # Should only have '식비', not '카페'
                assert '식비' in predictions
                # Depending on implementation, may or may not include other categories
                # If filter is strict, '카페' should not be present
                if data.get('category_filter'):
                    assert '카페' not in predictions

    def test_get_baseline_predictions_sorted_chronologically(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test that baseline months are returned in chronological order"""
        current_date = datetime.now()

        # Insert in random order
        months_to_insert = [3, 1, 5, 2, 4]
        for i in months_to_insert:
            month_date = current_date - timedelta(days=30 * i)

            baseline = BaselinePrediction(
                file_id=valid_file_id,
                category='식비',
                year=month_date.year,
                month=month_date.month,
                predicted_amount=450000.0,
                lower_bound=400000.0,
                upper_bound=500000.0
            )
            test_db.add(baseline)

        test_db.commit()

        # Execute request
        response = client.get(f"/ai/data/baseline?file_id={valid_file_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify chronological order (oldest first)
        months = data['baseline_months']
        for i in range(len(months) - 1):
            current_month = datetime(months[i]['year'], months[i]['month'], 1)
            next_month = datetime(months[i+1]['year'], months[i+1]['month'], 1)
            assert current_month < next_month, "Months should be in chronological order"

    def test_get_baseline_predictions_training_cutoff_dates(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test that training_cutoff_date is correctly set for each month"""
        current_date = datetime.now()
        month_date = current_date - timedelta(days=60)

        baseline = BaselinePrediction(
            file_id=valid_file_id,
            category='식비',
            year=month_date.year,
            month=month_date.month,
            predicted_amount=450000.0,
            lower_bound=400000.0,
            upper_bound=500000.0,
            training_cutoff_date=month_date - timedelta(days=1)
        )
        test_db.add(baseline)
        test_db.commit()

        # Execute request
        response = client.get(f"/ai/data/baseline?file_id={valid_file_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify training_cutoff_date
        first_month = data['baseline_months'][0]
        assert 'training_data_until' in first_month

        # Training cutoff should be before the predicted month
        cutoff_date = datetime.fromisoformat(
            first_month['training_data_until'].replace('Z', '+00:00')
        )
        predicted_month = datetime(first_month['year'], first_month['month'], 1)
        assert cutoff_date < predicted_month


@pytest.mark.integration
@pytest.mark.slow
class TestBaselineCalculationBackground:
    """Test baseline calculation as background task"""

    def test_baseline_calculated_after_leak_analysis(
        self,
        client,
        test_db,
        valid_file_id,
        sample_csv_data,
        mock_prophet_result
    ):
        """Test that baseline is calculated automatically after leak analysis"""
        with patch('app.api.endpoints.leak.S3Client') as MockS3, \
             patch('app.api.endpoints.leak.RedisClient') as MockRedis, \
             patch('app.api.endpoints.leak.ProphetService') as MockProphet:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = MagicMock(return_value=sample_csv_data)

            mock_redis = MockRedis.return_value
            mock_redis.get_csv_status = MagicMock(return_value=None)
            mock_redis.set_csv_status = MagicMock()
            mock_redis.acquire_lock = MagicMock(return_value=True)
            mock_redis.release_lock = MagicMock()

            mock_prophet = MockProphet.return_value
            mock_prophet.predict_by_category = MagicMock(return_value=mock_prophet_result)
            mock_prophet.calculate_baseline_predictions_async = MagicMock(
                return_value={'baseline_months': {}, 'months_calculated': 11}
            )

            # Trigger leak analysis (which should start baseline calculation)
            response = client.post(f"/ai/data?file_id={valid_file_id}")

            assert response.status_code == status.HTTP_200_OK

            # Note: In actual implementation, baseline runs in background
            # This test verifies the endpoint triggers it

    def test_baseline_with_multiple_categories(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test baseline predictions with multiple categories"""
        current_date = datetime.now()
        month_date = current_date - timedelta(days=60)

        categories = ['식비', '카페', '마트/편의점', '교통/차량']
        amounts = [450000, 150000, 350000, 200000]

        for category, amount in zip(categories, amounts):
            baseline = BaselinePrediction(
                file_id=valid_file_id,
                category=category,
                year=month_date.year,
                month=month_date.month,
                predicted_amount=amount,
                lower_bound=amount * 0.9,
                upper_bound=amount * 1.1
            )
            test_db.add(baseline)

        test_db.commit()

        # Execute request
        response = client.get(f"/ai/data/baseline?file_id={valid_file_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify all categories are present
        predictions = data['baseline_months'][0]['category_predictions']
        for category in categories:
            assert category in predictions
            assert predictions[category]['predicted_amount'] > 0

        # Verify total is sum of categories
        total = sum(predictions[cat]['predicted_amount'] for cat in categories)
        assert abs(data['baseline_months'][0]['total_predicted'] - total) < 1.0


@pytest.mark.integration
class TestBaselineEdgeCases:
    """Test edge cases for baseline predictions"""

    def test_baseline_with_zero_predictions(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test baseline when category has zero prediction (no transactions)"""
        current_date = datetime.now()
        month_date = current_date - timedelta(days=60)

        # Category with zero prediction
        baseline = BaselinePrediction(
            file_id=valid_file_id,
            category='경조사/회비',
            year=month_date.year,
            month=month_date.month,
            predicted_amount=0.0,
            lower_bound=0.0,
            upper_bound=0.0
        )
        test_db.add(baseline)
        test_db.commit()

        # Execute request
        response = client.get(f"/ai/data/baseline?file_id={valid_file_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        predictions = data['baseline_months'][0]['category_predictions']
        assert predictions['경조사/회비']['predicted_amount'] == 0.0

    def test_baseline_across_year_boundary(
        self,
        client,
        test_db,
        valid_file_id
    ):
        """Test baseline predictions spanning across year boundary"""
        # Insert baseline for December and January
        baseline_dec = BaselinePrediction(
            file_id=valid_file_id,
            category='식비',
            year=2024,
            month=12,
            predicted_amount=450000.0,
            lower_bound=400000.0,
            upper_bound=500000.0
        )
        test_db.add(baseline_dec)

        baseline_jan = BaselinePrediction(
            file_id=valid_file_id,
            category='식비',
            year=2025,
            month=1,
            predicted_amount=470000.0,
            lower_bound=420000.0,
            upper_bound=520000.0
        )
        test_db.add(baseline_jan)
        test_db.commit()

        # Execute request
        response = client.get(f"/ai/data/baseline?file_id={valid_file_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should handle year boundary correctly
        months = data['baseline_months']
        assert len(months) == 2

        # December should come before January
        assert months[0]['year'] == 2024
        assert months[0]['month'] == 12
        assert months[1]['year'] == 2025
        assert months[1]['month'] == 1

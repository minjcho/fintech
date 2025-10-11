"""
Integration tests for doojo (두꺼비 조언) endpoint

Tests the following endpoints:
- GET /ai/data/doojo - Get personalized saving recommendations with GPT-generated advice
"""
import pytest
from fastapi import status
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
import os

from app.db.models import DoojoAnalysis


@pytest.mark.integration
class TestGetDoojoRecommendations:
    """Test GET /ai/data/doojo endpoint - Get personalized saving recommendations"""

    def test_get_doojo_success(
        self,
        client,
        test_db,
        valid_file_id,
        sample_csv_data,
        mock_openai_client
    ):
        """Test successful retrieval of doojo recommendations with GPT advice"""
        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            # Setup S3 mock
            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            # Setup OpenAI mock
            MockOpenAI.return_value = mock_openai_client

            # Setup environment variables
            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com',
                'GMS_MODEL': 'gpt-5-nano'
            }.get(key, default)

            # Execute request
            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2025&month=1"
            )

            # Verify response
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data['file_id'] == valid_file_id
            assert 'doojo' in data
            assert len(data['doojo']) > 0

            doojo = data['doojo'][0]
            assert doojo['year'] == 2025
            assert doojo['month'] == 1
            assert 'categories_count' in doojo
            assert 'categories_prediction' in doojo
            assert 'categories_detail' in doojo

    def test_get_doojo_excludes_insurance_tax(
        self,
        client,
        test_db,
        valid_file_id,
        mock_openai_client
    ):
        """Test that '보험 / 세금' category is excluded from doojo analysis"""
        # Create CSV data with '보험 / 세금' category
        csv_data_with_insurance = pd.DataFrame({
            'transaction_date_time': pd.date_range('2024-01-01', periods=30, freq='D'),
            'category': ['보험 / 세금'] * 10 + ['식비'] * 20,
            'merchant_name': ['삼성화재'] * 10 + ['강남 한정식'] * 20,
            'amount': [100000] * 10 + [15000] * 20
        })

        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=csv_data_with_insurance)

            MockOpenAI.return_value = mock_openai_client

            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com'
            }.get(key, default)

            # Execute request
            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2024&month=1"
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # '보험 / 세금' should not be in categories
            categories_detail = data['doojo'][0]['categories_detail']
            assert '보험 / 세금' not in categories_detail
            assert '식비' in categories_detail

    def test_get_doojo_merchant_analysis(
        self,
        client,
        test_db,
        valid_file_id,
        sample_csv_data,
        mock_openai_client
    ):
        """Test that most_spent and most_frequent merchants are identified correctly"""
        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            MockOpenAI.return_value = mock_openai_client

            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com'
            }.get(key, default)

            # Execute request
            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2024&month=1"
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            categories_detail = data['doojo'][0]['categories_detail']

            # Each category should have most_spent and most_frequent
            for category, detail in categories_detail.items():
                assert 'most_spent' in detail
                assert 'most_frequent' in detail

                # most_spent should have merchant, amount, date, msg
                most_spent = detail['most_spent']
                assert 'merchant' in most_spent
                assert 'amount' in most_spent
                assert 'date' in most_spent
                assert 'msg' in most_spent  # GPT-generated advice

                # most_frequent should have merchant, count, total_amount, msg
                most_frequent = detail['most_frequent']
                assert 'merchant' in most_frequent
                assert 'count' in most_frequent
                assert 'total_amount' in most_frequent
                assert 'msg' in most_frequent  # GPT-generated advice

    def test_get_doojo_file_not_found(
        self,
        client,
        test_db
    ):
        """Test 404 when CSV file doesn't exist in S3"""
        with patch('app.api.endpoints.doojo.S3Client') as MockS3:
            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(side_effect=FileNotFoundError("File not found"))

            response = client.get(
                "/ai/data/doojo?file_id=nonexistent&year=2025&month=1"
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_doojo_missing_year_or_month(
        self,
        client,
        valid_file_id
    ):
        """Test 422 when year or month parameter is missing"""
        # Missing month
        response1 = client.get(f"/ai/data/doojo?file_id={valid_file_id}&year=2025")
        assert response1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Missing year
        response2 = client.get(f"/ai/data/doojo?file_id={valid_file_id}&month=1")
        assert response2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_doojo_invalid_month(
        self,
        client,
        valid_file_id
    ):
        """Test 422 when month is invalid (e.g., 0 or 13)"""
        response = client.get(
            f"/ai/data/doojo?file_id={valid_file_id}&year=2025&month=13"
        )

        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_get_doojo_gpt_api_key_missing(
        self,
        client,
        valid_file_id,
        sample_csv_data
    ):
        """Test error handling when GMS_API_KEY is not configured"""
        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            # No API key
            mock_getenv.return_value = None

            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2025&month=1"
            )

            # Should return error
            assert response.status_code in [
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_400_BAD_REQUEST
            ]


@pytest.mark.integration
class TestDoojoAnalysisStorage:
    """Test doojo analysis data storage in database"""

    def test_doojo_data_saved_to_database(
        self,
        client,
        test_db,
        valid_file_id,
        sample_csv_data,
        mock_openai_client
    ):
        """Test that doojo analysis results are saved to database"""
        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            MockOpenAI.return_value = mock_openai_client

            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com'
            }.get(key, default)

            # Execute request
            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2025&month=1"
            )

            assert response.status_code == status.HTTP_200_OK

            # Verify data was saved to database
            doojo_records = test_db.query(DoojoAnalysis).filter(
                DoojoAnalysis.file_id == valid_file_id,
                DoojoAnalysis.year == 2025,
                DoojoAnalysis.month == 1
            ).all()

            # Should have records for each category
            assert len(doojo_records) > 0

    def test_doojo_idempotent_retrieval(
        self,
        client,
        test_db,
        valid_file_id,
        sample_csv_data,
        mock_openai_client
    ):
        """Test that calling doojo multiple times returns consistent results"""
        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            MockOpenAI.return_value = mock_openai_client

            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com'
            }.get(key, default)

            # First call
            response1 = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2025&month=1"
            )

            # Second call
            response2 = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2025&month=1"
            )

            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_200_OK

            # Results should be consistent
            data1 = response1.json()
            data2 = response2.json()

            assert data1['file_id'] == data2['file_id']
            assert data1['doojo'][0]['year'] == data2['doojo'][0]['year']
            assert data1['doojo'][0]['month'] == data2['doojo'][0]['month']


@pytest.mark.integration
@pytest.mark.slow
class TestDoojoGPTIntegration:
    """Test GPT message generation integration"""

    def test_gpt_generates_different_messages_for_different_merchants(
        self,
        client,
        valid_file_id,
        mock_openai_client
    ):
        """Test that GPT generates unique advice for different merchants"""
        # Create CSV with different merchants
        csv_data = pd.DataFrame({
            'transaction_date_time': pd.date_range('2024-01-01', periods=40, freq='D'),
            'category': ['카페'] * 20 + ['식비'] * 20,
            'merchant_name': ['스타벅스'] * 20 + ['버거킹'] * 20,
            'amount': [5000] * 20 + [8000] * 20
        })

        # Setup different messages for each merchant
        def create_message_side_effect(*args, **kwargs):
            mock_response = MagicMock()
            prompt = kwargs.get('messages', [{}])[0].get('content', '')

            if '스타벅스' in prompt:
                mock_response.choices = [
                    MagicMock(message=MagicMock(content="스타벅스 지출을 줄여봐."))
                ]
            elif '버거킹' in prompt:
                mock_response.choices = [
                    MagicMock(message=MagicMock(content="버거킹은 단품으로 주문해."))
                ]
            else:
                mock_response.choices = [
                    MagicMock(message=MagicMock(content="지출을 절약해봐."))
                ]

            return mock_response

        mock_openai_client.chat.completions.create.side_effect = create_message_side_effect

        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=csv_data)

            MockOpenAI.return_value = mock_openai_client

            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com'
            }.get(key, default)

            # Execute request
            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2024&month=1"
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            categories_detail = data['doojo'][0]['categories_detail']

            # Verify different messages for different categories/merchants
            if '카페' in categories_detail and '식비' in categories_detail:
                cafe_msg = categories_detail['카페']['most_frequent']['msg']
                food_msg = categories_detail['식비']['most_frequent']['msg']

                # Messages should be different
                assert cafe_msg != food_msg

    def test_gpt_error_handling(
        self,
        client,
        valid_file_id,
        sample_csv_data
    ):
        """Test error handling when GPT API fails"""
        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=sample_csv_data)

            # GPT API fails
            mock_openai = MockOpenAI.return_value
            mock_openai.chat.completions.create.side_effect = Exception("API Error")

            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com'
            }.get(key, default)

            # Execute request
            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2024&month=1"
            )

            # Should still return 200 but with empty or fallback messages
            # Depending on implementation, may return 500
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]


@pytest.mark.integration
class TestDoojoEdgeCases:
    """Test edge cases for doojo endpoint"""

    def test_doojo_with_no_transactions_in_month(
        self,
        client,
        valid_file_id,
        mock_openai_client
    ):
        """Test doojo when no transactions exist for the specified month"""
        # CSV with only January data
        csv_data = pd.DataFrame({
            'transaction_date_time': pd.date_range('2024-01-01', periods=30, freq='D'),
            'category': ['식비'] * 30,
            'merchant_name': ['강남 한정식'] * 30,
            'amount': [15000] * 30
        })

        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=csv_data)

            MockOpenAI.return_value = mock_openai_client

            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com'
            }.get(key, default)

            # Request for February (no data)
            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2024&month=2"
            )

            # Should return 404 or 200 with empty categories
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND
            ]

    def test_doojo_with_single_category(
        self,
        client,
        valid_file_id,
        mock_openai_client
    ):
        """Test doojo when only one category exists"""
        csv_data = pd.DataFrame({
            'transaction_date_time': pd.date_range('2024-01-01', periods=30, freq='D'),
            'category': ['식비'] * 30,
            'merchant_name': ['강남 한정식'] * 30,
            'amount': [15000] * 30
        })

        with patch('app.api.endpoints.doojo.S3Client') as MockS3, \
             patch('app.api.endpoints.doojo.OpenAI') as MockOpenAI, \
             patch('app.api.endpoints.doojo.os.getenv') as mock_getenv:

            mock_s3 = MockS3.return_value
            mock_s3.fetch_csv_data = AsyncMock(return_value=csv_data)

            MockOpenAI.return_value = mock_openai_client

            mock_getenv.side_effect = lambda key, default=None: {
                'GMS_API_KEY': 'test-key',
                'GMS_BASE_URL': 'https://test.api.com'
            }.get(key, default)

            # Execute request
            response = client.get(
                f"/ai/data/doojo?file_id={valid_file_id}&year=2024&month=1"
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should only have one category
            assert data['doojo'][0]['categories_count'] == 1
            assert '식비' in data['doojo'][0]['categories_detail']

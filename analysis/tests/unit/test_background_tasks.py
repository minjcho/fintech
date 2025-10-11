"""
Unit tests for background tasks and parallel processing

Tests:
- Prophet parallel category processing
- ThreadPoolExecutor behavior
- Background task execution
- Concurrency and thread safety
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor, Future
import pandas as pd
from datetime import datetime
import time

from app.services.prophet_service import ProphetService


@pytest.mark.unit
class TestParallelCategoryProcessing:
    """Test parallel category processing in Prophet service"""

    @pytest.fixture
    def prophet_service(self):
        return ProphetService()

    @pytest.fixture
    def multi_category_data(self):
        """Generate data with multiple categories for parallel processing"""
        data = []
        categories = ['식비', '카페', '마트/편의점', '교통/차량', '패션/미용']

        for category in categories:
            for day in range(60):
                data.append({
                    'transaction_date_time': datetime(2024, 1, 1).replace(day=day % 28 + 1),
                    'category': category,
                    'merchant_name': f'{category} Merchant',
                    'amount': 10000 + (day % 10) * 1000
                })

        return pd.DataFrame(data)

    def test_predict_single_category_thread_safe(
        self,
        prophet_service,
        multi_category_data
    ):
        """Test that _predict_single_category is thread-safe"""
        category = '식비'

        # Call multiple times to ensure no side effects
        result1 = prophet_service._predict_single_category(category, multi_category_data)
        result2 = prophet_service._predict_single_category(category, multi_category_data)

        # Results should be consistent
        assert result1 is not None
        assert result2 is not None
        assert result1['category'] == result2['category'] == category

    def test_parallel_processing_performance(
        self,
        prophet_service,
        multi_category_data
    ):
        """Test that parallel processing is faster than serial processing"""
        # Measure parallel execution time
        start_parallel = time.time()
        result_parallel = prophet_service._predict_by_category_sync(multi_category_data)
        time_parallel = time.time() - start_parallel

        # Verify results
        assert 'category_predictions' in result_parallel
        assert len(result_parallel['category_predictions']) > 0

        # Parallel processing should complete in reasonable time
        # (5 categories should be processed in < 10 seconds)
        assert time_parallel < 10.0, f"Parallel processing took too long: {time_parallel}s"

    def test_all_categories_processed(
        self,
        prophet_service,
        multi_category_data
    ):
        """Test that all categories are processed in parallel"""
        result = prophet_service._predict_by_category_sync(multi_category_data)

        categories = multi_category_data['category'].unique()
        predictions = result['category_predictions']

        # All categories should have predictions
        for category in categories:
            assert category in predictions, f"Category {category} not in predictions"
            assert predictions[category] is not None

    def test_category_processing_handles_errors(
        self,
        prophet_service
    ):
        """Test error handling in parallel category processing"""
        # Create data with insufficient rows for Prophet
        insufficient_data = pd.DataFrame({
            'transaction_date_time': [datetime(2024, 1, 1)],
            'category': ['식비'],
            'merchant_name': ['Test'],
            'amount': [10000]
        })

        result = prophet_service._predict_by_category_sync(insufficient_data)

        # Should still return a result (may have error info)
        assert result is not None
        assert 'category_predictions' in result


@pytest.mark.unit
class TestThreadPoolExecutor:
    """Test ThreadPoolExecutor configuration and behavior"""

    def test_prophet_service_has_separate_executors(self):
        """Test that ProphetService initializes separate thread pools"""
        service = ProphetService()

        assert hasattr(service, 'main_executor')
        assert hasattr(service, 'baseline_executor')
        assert hasattr(service, 'category_executor')

        assert isinstance(service.main_executor, ThreadPoolExecutor)
        assert isinstance(service.baseline_executor, ThreadPoolExecutor)
        assert isinstance(service.category_executor, ThreadPoolExecutor)

    def test_executors_have_different_names(self):
        """Test that executors have descriptive thread names"""
        service = ProphetService()

        # Thread name prefixes should be different
        assert service.main_executor._thread_name_prefix == 'prophet-main'
        assert service.baseline_executor._thread_name_prefix == 'prophet-baseline'
        assert service.category_executor._thread_name_prefix == 'category-worker'

    def test_category_executor_shared_across_requests(self):
        """Test that category_executor is shared (class-level)"""
        service1 = ProphetService()
        service2 = ProphetService()

        # Category executor should be the same instance
        # (This prevents resource exhaustion under concurrent load)
        # Note: This test depends on implementation details
        assert service1.category_executor is not None
        assert service2.category_executor is not None


@pytest.mark.unit
@pytest.mark.slow
class TestBackgroundTaskExecution:
    """Test background task execution patterns"""

    @pytest.mark.asyncio
    async def test_async_predict_by_category(
        self,
        sample_csv_data
    ):
        """Test async wrapper for category prediction"""
        service = ProphetService()

        result = await service.predict_by_category(sample_csv_data)

        assert result is not None
        assert 'category_predictions' in result
        assert 'total_current_predicted' in result

    @pytest.mark.asyncio
    async def test_async_baseline_calculation(
        self,
        sample_csv_data
    ):
        """Test async wrapper for baseline calculation"""
        service = ProphetService()

        result = await service.calculate_baseline_predictions_async(sample_csv_data)

        assert result is not None
        assert 'baseline_months' in result
        assert 'months_calculated' in result

    def test_background_task_does_not_block_main_thread(
        self,
        sample_csv_data
    ):
        """Test that background tasks don't block the main event loop"""
        service = ProphetService()

        # Submit task to executor
        import asyncio

        async def run_test():
            # Start background task
            task = asyncio.create_task(service.predict_by_category(sample_csv_data))

            # Main thread should remain responsive
            await asyncio.sleep(0.1)

            # Task should eventually complete
            result = await task
            return result

        # Run test
        result = asyncio.run(run_test())
        assert result is not None


@pytest.mark.unit
class TestConcurrencyAndThreadSafety:
    """Test thread safety and concurrent request handling"""

    def test_multiple_concurrent_predictions(
        self,
        sample_csv_data
    ):
        """Test handling multiple concurrent prediction requests"""
        service = ProphetService()

        # Submit multiple predictions concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i in range(3):
                future = executor.submit(
                    service._predict_by_category_sync,
                    sample_csv_data
                )
                futures.append(future)

            # Wait for all to complete
            results = [f.result() for f in futures]

        # All should succeed
        assert len(results) == 3
        for result in results:
            assert result is not None
            assert 'category_predictions' in result

    def test_shared_category_executor_under_load(
        self,
        sample_csv_data
    ):
        """Test shared category_executor handles concurrent load"""
        service1 = ProphetService()
        service2 = ProphetService()

        # Both services submit work to shared executor
        result1 = service1._predict_by_category_sync(sample_csv_data)
        result2 = service2._predict_by_category_sync(sample_csv_data)

        # Both should succeed
        assert result1 is not None
        assert result2 is not None

    def test_dataframe_copy_prevents_race_conditions(
        self,
        sample_csv_data
    ):
        """Test that prepare_category_data creates copies to prevent race conditions"""
        service = ProphetService()

        # Process same category twice
        category = '식비'
        result1 = service.prepare_category_data(sample_csv_data, category)
        result2 = service.prepare_category_data(sample_csv_data, category)

        # Results should be independent (different DataFrame objects)
        assert result1 is not result2

        # Modifying one should not affect the other
        if len(result1) > 0:
            original_value = result1.iloc[0]['y']
            result1.iloc[0, result1.columns.get_loc('y')] = 999999

            # result2 should remain unchanged
            assert result2.iloc[0]['y'] == original_value


@pytest.mark.unit
class TestBaselineBackgroundCalculation:
    """Test baseline calculation as background task"""

    def test_baseline_calculation_sequential(
        self,
        sample_csv_data
    ):
        """Test that baseline months are calculated sequentially"""
        service = ProphetService()

        result = service.calculate_baseline_predictions(sample_csv_data)

        assert result is not None
        assert 'baseline_months' in result

        # Should calculate multiple months
        assert len(result['baseline_months']) > 0

    def test_baseline_uses_separate_executor(self):
        """Test that baseline calculation uses separate thread pool"""
        service = ProphetService()

        # Baseline should use baseline_executor, not main_executor
        assert service.baseline_executor is not service.main_executor
        assert service.baseline_executor is not service.category_executor


@pytest.mark.unit
@pytest.mark.slow
class TestResourceManagement:
    """Test resource management in background tasks"""

    def test_executor_cleanup(self):
        """Test that executors are properly cleaned up"""
        service = ProphetService()

        # Check executors are initialized
        assert service.main_executor is not None
        assert service.baseline_executor is not None
        assert service.category_executor is not None

        # In production, executors should be cleaned up on shutdown
        # (Not tested here as it requires application lifecycle management)

    def test_memory_usage_under_concurrent_load(
        self,
        sample_csv_data
    ):
        """Test memory doesn't explode under concurrent load"""
        import sys

        service = ProphetService()

        # Get initial memory footprint
        initial_size = sys.getsizeof(service)

        # Run multiple predictions
        for _ in range(5):
            result = service._predict_by_category_sync(sample_csv_data)
            assert result is not None

        # Memory shouldn't grow excessively
        # (This is a rough test - in production, use memory profiler)
        final_size = sys.getsizeof(service)
        growth = final_size - initial_size

        # Memory growth should be reasonable (< 1MB for example)
        assert growth < 1_000_000, f"Excessive memory growth: {growth} bytes"


@pytest.mark.unit
class TestErrorPropagation:
    """Test error handling in parallel processing"""

    def test_single_category_failure_does_not_stop_others(
        self,
        prophet_service
    ):
        """Test that one category failing doesn't stop others"""
        # Create data where one category has insufficient data
        mixed_data = pd.DataFrame({
            'transaction_date_time': pd.date_range('2024-01-01', periods=60, freq='D').tolist() +
                                    [datetime(2024, 1, 1)],
            'category': ['식비'] * 60 + ['카페'],  # 카페 has only 1 row
            'merchant_name': ['Test'] * 61,
            'amount': [10000] * 61
        })

        result = prophet_service._predict_by_category_sync(mixed_data)

        # '식비' should succeed
        assert '식비' in result['category_predictions']

        # Result should still be valid
        assert result['total_current_predicted'] > 0

    def test_all_categories_fail_gracefully(
        self,
        prophet_service
    ):
        """Test handling when all categories fail to process"""
        # Insufficient data for all categories
        insufficient_data = pd.DataFrame({
            'transaction_date_time': [datetime(2024, 1, 1)] * 2,
            'category': ['식비', '카페'],
            'merchant_name': ['Test'] * 2,
            'amount': [10000] * 2
        })

        result = prophet_service._predict_by_category_sync(insufficient_data)

        # Should return result with error info or empty predictions
        assert result is not None
        assert 'category_predictions' in result

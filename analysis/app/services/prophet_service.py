"""
Prophet-based time series forecasting service for category-wise spending prediction
"""
import pandas as pd
import numpy as np
from prophet import Prophet
from datetime import datetime, timedelta
import logging
import json
from typing import Dict, Any, Optional, List
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
import os
import time
from app.core.constants import (
    PROPHET_MAIN_WORKERS,
    PROPHET_BASELINE_WORKERS,
    PROPHET_INTERVAL_WIDTH,
    PROPHET_FORECAST_PERIODS,
    PROPHET_MIN_DATA_DAYS,
    BASELINE_MONTHS_COUNT
)

logger = logging.getLogger(__name__)

class ProphetService:
    """Service for time series forecasting using Facebook Prophet - Category-wise"""
    
    def __init__(self):
        # Separate thread pools to prevent background tasks from blocking main requests
        self.main_executor = ThreadPoolExecutor(
            max_workers=PROPHET_MAIN_WORKERS,
            thread_name_prefix="prophet-main"
        )
        self.baseline_executor = ThreadPoolExecutor(
            max_workers=PROPHET_BASELINE_WORKERS,
            thread_name_prefix="prophet-baseline"
        )
        # Shared pool for category processing across all requests
        # This prevents resource exhaustion under concurrent load
        cpu_count = os.cpu_count() or 4
        self.category_executor = ThreadPoolExecutor(
            max_workers=min(cpu_count, 8),
            thread_name_prefix="category-worker"
        )
        
    def prepare_category_data(self, df: pd.DataFrame, category: str) -> pd.DataFrame:
        """
        Prepare data for Prophet model for a specific category
        
        Args:
            df: DataFrame with columns including 'transaction_date_time', 'amount', and 'category'
            category: Category to filter for
            
        Returns:
            DataFrame with 'ds' and 'y' columns required by Prophet
        """
        # Filter for specific category
        category_df = df[df['category'] == category].copy()
        
        # Convert timestamp to datetime
        category_df['ds'] = pd.to_datetime(category_df['transaction_date_time'])
        
        # Aggregate daily spending for this category
        daily_spending = category_df.groupby(category_df['ds'].dt.date)['amount'].sum().reset_index()
        daily_spending.columns = ['ds', 'y']
        
        # Ensure ds is datetime
        daily_spending['ds'] = pd.to_datetime(daily_spending['ds'])
        
        # Fill missing dates with 0
        if len(daily_spending) > 0:
            date_range = pd.date_range(
                start=daily_spending['ds'].min(),
                end=daily_spending['ds'].max(),
                freq='D'
            )
            full_df = pd.DataFrame({'ds': date_range})
            full_df = full_df.merge(daily_spending, on='ds', how='left')
            full_df['y'] = full_df['y'].fillna(0)
            return full_df
        
        return daily_spending
    
    def train_prophet_model(self, df: pd.DataFrame, category: str) -> Prophet:
        """
        Train Prophet model on historical data for a specific category
        
        Args:
            df: Prepared DataFrame with 'ds' and 'y' columns
            category: Category name (for custom seasonality adjustments)
            
        Returns:
            Trained Prophet model
        """
        # Skip if no data
        if len(df) == 0:
            return None
            
        # Initialize Prophet with custom parameters based on category
        if category in ['식비', 'Food & Dining', '카페', 'Cafe', "마트 / 편의점"]:
            # Food categories have strong weekly patterns
            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=False,
                seasonality_mode='additive',
                changepoint_prior_scale=0.1,
                interval_width=PROPHET_INTERVAL_WIDTH
            )
        elif category in ['교통 / 차량', 'Transportation']:
            # Transportation has monthly patterns
            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=False,
                yearly_seasonality=False,
                seasonality_mode='additive',
                changepoint_prior_scale=0.05,
                interval_width=PROPHET_INTERVAL_WIDTH
            )
            model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
        else:
            # Default settings for other categories
            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=False,
                seasonality_mode='multiplicative',
                changepoint_prior_scale=0.05,
                interval_width=PROPHET_INTERVAL_WIDTH
            )
        
        # Fit the model
        with np.errstate(divide='ignore', invalid='ignore'):
            model.fit(df)
        
        return model
    
    def make_predictions(self, model: Prophet, periods: int = 60) -> pd.DataFrame:
        """
        Make predictions for future periods
        
        Args:
            model: Trained Prophet model
            periods: Number of days to predict
            
        Returns:
            DataFrame with predictions
        """
        if model is None:
            return pd.DataFrame()
            
        # Create future dataframe
        future = model.make_future_dataframe(periods=periods)
        
        # Make predictions
        forecast = model.predict(future)
        
        return forecast
    
    def calculate_monthly_category_aggregates(
        self, 
        forecast: pd.DataFrame,
        actual_df: pd.DataFrame,
        category: str
    ) -> Dict[str, Any]:
        """
        Calculate monthly aggregates from daily predictions for a category
        
        Args:
            forecast: Prophet forecast DataFrame
            actual_df: Actual data DataFrame
            category: Category name
            
        Returns:
            Dictionary with monthly predictions for the category
        """
        if len(forecast) == 0:
            return {
                'category': category,
                'current_month': {'predicted': 0, 'lower_bound': 0, 'upper_bound': 0}
            }
        
        # Add month-year column to forecast
        forecast['month_year'] = pd.to_datetime(forecast['ds']).dt.to_period('M')
        
        # Get current month
        current_date = datetime.now()
        current_month = current_date.strftime('%Y-%m')
        
        # Calculate actual spending for current month if available
        current_month_actual = None
        if len(actual_df) > 0 and 'y' in actual_df.columns:
            actual_df['month_year'] = pd.to_datetime(actual_df['ds']).dt.to_period('M')
            current_actual = actual_df[
                actual_df['month_year'] == pd.Period(current_month, 'M')
            ]['y'].sum()
            if current_actual > 0:
                current_month_actual = float(current_actual)
        
        # Get monthly predictions
        monthly_forecast = forecast.groupby('month_year').agg({
            'yhat': 'sum',
            'yhat_lower': 'sum',
            'yhat_upper': 'sum'
        }).reset_index()
        
        # Extract current month predictions
        current_month_pred = monthly_forecast[
            monthly_forecast['month_year'] == pd.Period(current_month, 'M')
        ]

        return {
            'category': category,
            'current_month': {
                'actual': current_month_actual,
                'predicted': float(current_month_pred['yhat'].values[0]) if len(current_month_pred) > 0 else 0,
                'lower_bound': float(current_month_pred['yhat_lower'].values[0]) if len(current_month_pred) > 0 else 0,
                'upper_bound': float(current_month_pred['yhat_upper'].values[0]) if len(current_month_pred) > 0 else 0
            }
        }
    
    async def predict_spending_by_category(self, csv_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Main async method to predict spending by category using Prophet

        Args:
            csv_data: DataFrame with transaction data including 'category' column

        Returns:
            Dictionary with predictions for each category
        """
        loop = asyncio.get_event_loop()

        try:
            # Run Prophet prediction in thread pool (CPU-intensive)
            result = await loop.run_in_executor(
                self.main_executor,
                self._predict_by_category_sync,
                csv_data
            )
            return result
        except Exception as e:
            logger.error(f"Error in Prophet category prediction: {e}")
            raise
    
    def _predict_single_category(self, category: str, csv_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Predict spending for a single category (designed for parallel execution)

        Args:
            category: Category name to predict
            csv_data: DataFrame with transaction data

        Returns:
            Dictionary with prediction results for the category

        Note:
            Thread-safe: prepare_category_data() creates a copy of the category data,
            ensuring no conflicts when multiple threads process different categories
        """
        try:
            # Prepare data for this category (creates a copy for thread safety)
            prophet_data = self.prepare_category_data(csv_data, category)

            if len(prophet_data) < 2:
                logger.warning(f"Not enough data for category '{category}', skipping")
                return None

            # Train model for this category
            model = self.train_prophet_model(prophet_data, category)

            if model is None:
                return None

            # Make predictions
            forecast = self.make_predictions(model)

            # Calculate monthly aggregates
            results = self.calculate_monthly_category_aggregates(
                forecast,
                prophet_data,
                category
            )

            return results

        except Exception as e:
            logger.error(f"Error predicting for category '{category}': {e}")
            return {
                'category': category,
                'error': str(e),
                'current_month': {'predicted': 0}
            }

    def _predict_by_category_sync(self, csv_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Synchronous method for Prophet prediction by category with parallel processing

        Args:
            csv_data: DataFrame with transaction data

        Returns:
            Dictionary with category-wise predictions
        """
        # Get unique categories
        if 'category' not in csv_data.columns:
            logger.error("No 'category' column found in data")
            return {'error': 'No category column in data'}

        categories = csv_data['category'].unique()
        logger.info(f"Found {len(categories)} categories: {categories[:5]}...")

        # Store predictions for each category
        category_predictions = {}
        predictions_list = []  # Thread-safe collection for totals

        # Process categories in parallel using shared category_executor
        # Using class-level shared executor prevents resource exhaustion under concurrent load
        # (vs. creating new executor per request which could spawn 32+ threads)
        start_time = time.time()
        logger.info(f"Processing {len(categories)} categories in parallel using shared category_executor")

        # Submit all category prediction tasks to shared executor
        future_to_category = {
            self.category_executor.submit(self._predict_single_category, category, csv_data): category
            for category in categories
        }

        # Collect results as they complete
        completed_count = 0
        failed_count = 0

        for future in as_completed(future_to_category):
            category = future_to_category[future]
            try:
                result = future.result()

                if result is not None:
                    category_predictions[category] = result
                    # Collect predictions for thread-safe summation later
                    predictions_list.append(result['current_month']['predicted'])
                    completed_count += 1
                    logger.debug(f"[{completed_count}/{len(categories)}] Completed: {category}")
                else:
                    logger.warning(f"No prediction result for category '{category}'")
                    failed_count += 1

            except Exception as e:
                logger.error(f"Exception occurred for category '{category}': {e}")
                category_predictions[category] = {
                    'category': category,
                    'error': str(e),
                    'current_month': {'predicted': 0}
                }
                failed_count += 1

        # Calculate total after all results collected (thread-safe)
        total_current_predicted = sum(predictions_list)

        elapsed_time = time.time() - start_time
        logger.info(f"Parallel processing completed: {completed_count} succeeded, {failed_count} failed, {elapsed_time:.2f}s total")

        # Set trend status
        trend = "analyzed"

        # Get current date info
        current_date = datetime.now()

        return {
            'prediction_id': str(uuid.uuid4()),
            'created_at': datetime.utcnow().isoformat(),
            'year': current_date.year,
            'month': current_date.month,
            'category_predictions': category_predictions,
            'total_current_predicted': total_current_predicted,
            'trend': trend,
            'categories_analyzed': len(category_predictions)
        }
    
    def calculate_baseline_predictions(self, csv_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate baseline predictions for past 11 months using only prior data
        현재월 기준 과거 11개월에 대한 베이스라인 예측 (소비 기준 금액)

        Args:
            csv_data: Full transaction data

        Returns:
            Dictionary with monthly baseline predictions by category
        """
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month
        baseline_results = {}
        
        # Convert timestamp to datetime if needed
        if 'transaction_date_time' in csv_data.columns:
            csv_data['date'] = pd.to_datetime(csv_data['transaction_date_time'])
        elif 'date' not in csv_data.columns:
            logger.error("No date column found in data")
            return {'error': 'No date column'}
        
        # Get data range
        max_date = csv_data['date'].max()
        min_date = csv_data['date'].min()
        
        logger.info(f"Data range: {min_date} to {max_date}")
        
        # Calculate for past months from current month
        # 현재월 기준 과거 개월 계산
        months_to_calculate = []
        for i in range(BASELINE_MONTHS_COUNT, 0, -1):  # N개월 전부터 1개월 전까지
            calc_date = current_date - timedelta(days=30 * i)
            months_to_calculate.append((calc_date.year, calc_date.month))

        # Get all unique categories from the entire dataset for consistency
        all_categories = csv_data['category'].unique()

        for target_year, target_month in months_to_calculate:
            month_key = f"{target_year}-{target_month:02d}"

            # Get data up to the end of previous month
            cutoff_date = datetime(target_year, target_month, 1) - timedelta(days=1)
            train_data = csv_data[csv_data['date'] <= cutoff_date].copy()

            # Initialize month predictions with 0 for all categories
            month_predictions = {
                category: {
                    'predicted': 0.0,
                    'lower_bound': 0.0,
                    'upper_bound': 0.0,
                    'data_points': 0
                }
                for category in all_categories
            }

            if len(train_data) < PROPHET_MIN_DATA_DAYS:  # Need at least minimum days of data
                logger.warning(f"Not enough data for baseline {month_key} (need {PROPHET_MIN_DATA_DAYS} days) - returning zeros")
                baseline_results[month_key] = {
                    'year': target_year,
                    'month': target_month,
                    'categories': month_predictions,  # All zeros
                    'total': 0,
                    'categories_count': len(all_categories),
                    'training_data_until': cutoff_date.isoformat(),
                    'status': 'insufficient_data'
                }
                continue

            # Calculate predictions for each category
            categories = train_data['category'].unique()
            # month_predictions already initialized with zeros for all categories
            total_predicted = 0

            for category in categories:
                try:
                    # Prepare data for this category
                    category_train = train_data[train_data['category'] == category].copy()
                    
                    if len(category_train) < 7:  # Need at least a week of data
                        # Keep the zero values already set for this category
                        continue
                    
                    # Prepare Prophet data
                    prophet_data = self.prepare_category_data(category_train, category)
                    
                    if len(prophet_data) < 2:
                        # Keep the zero values already set for this category
                        continue

                    # Train model
                    model = self.train_prophet_model(prophet_data, category)

                    if model is None:
                        # Keep the zero values already set for this category
                        continue
                    
                    # Predict for target month
                    future = model.make_future_dataframe(periods=PROPHET_FORECAST_PERIODS * 2)
                    forecast = model.predict(future)
                    
                    # Filter for target month
                    forecast['year_month'] = forecast['ds'].dt.to_period('M')
                    target_period = pd.Period(f"{target_year}-{target_month:02d}", 'M')
                    month_forecast = forecast[forecast['year_month'] == target_period]
                    
                    if len(month_forecast) > 0:
                        predicted_amount = month_forecast['yhat'].sum()
                        lower_bound = month_forecast['yhat_lower'].sum()
                        upper_bound = month_forecast['yhat_upper'].sum()

                        # Ensure predicted amount is not negative
                        predicted_amount = max(0.0, predicted_amount)

                        # Update the prediction for this category (overwriting the zero values)
                        month_predictions[category] = {
                            'predicted': float(predicted_amount),
                            'lower_bound': float(lower_bound),
                            'upper_bound': float(upper_bound),
                            'data_points': len(category_train)
                        }
                        total_predicted += predicted_amount
                    # If no forecast, keep the zero values already set
                        
                except Exception as e:
                    logger.error(f"Error calculating baseline for {category} in {month_key}: {e}")
                    # Keep the zero values already set for this category on error
                    continue
            
            baseline_results[month_key] = {
                'year': target_year,
                'month': target_month,
                'categories': month_predictions,  # Now includes all categories with zeros for missing ones
                'total': float(total_predicted),
                'categories_count': len(month_predictions),
                'training_data_until': cutoff_date.isoformat(),
                'status': 'completed'
            }
        
        return {
            'baseline_id': str(uuid.uuid4()),
            'created_at': datetime.utcnow().isoformat(),
            'baseline_months': baseline_results,
            'months_calculated': len(baseline_results)
        }
    
    async def predict_by_category(self, csv_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Predict current month spending by category

        Args:
            csv_data: Transaction data

        Returns:
            Dictionary with current month predictions
        """
        loop = asyncio.get_event_loop()

        try:
            result = await loop.run_in_executor(
                self.main_executor,
                self._predict_by_category_sync,
                csv_data
            )
            return result
        except Exception as e:
            logger.error(f"Error in category prediction: {e}")
            raise

    async def calculate_baseline_predictions_async(self, csv_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate baseline predictions for past 11 months asynchronously

        Args:
            csv_data: Transaction data

        Returns:
            Dictionary with baseline predictions
        """
        loop = asyncio.get_event_loop()

        try:
            result = await loop.run_in_executor(
                self.baseline_executor,
                self.calculate_baseline_predictions,
                csv_data
            )
            return result
        except Exception as e:
            logger.error(f"Error in baseline calculation: {e}")
            raise
    
    def calculate_category_leak(
        self,
        actual_spending: float,
        predicted_spending: float,
        category: str,
        budget: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate spending leak (overspending) for a category
        
        Args:
            actual_spending: Actual amount spent
            predicted_spending: Predicted amount
            category: Category name
            budget: Optional budget for the category
            
        Returns:
            Dictionary with leak analysis
        """
        baseline = budget if budget else predicted_spending
        
        leak_amount = max(0, actual_spending - baseline)
        leak_percentage = (leak_amount / baseline * 100) if baseline > 0 else 0
        
        return {
            'category': category,
            'leak_amount': leak_amount,
            'leak_percentage': leak_percentage,
            'baseline': baseline,
            'actual': actual_spending
        }
"""
AI Data Preprocessing Tests
=============================

This module contains tests for the AI data preprocessing components
including DataLoader and DataPreprocessor classes.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import json

from trading.bots.swing_bot.ai.data import DataLoader, DataPreprocessor
from trading.bots.swing_bot.ai.features import FeatureEngine
from trading.bots.swing_bot.utils.validators import validate_data


class TestDataLoader:
    """Tests for DataLoader class."""

    def test_initialization(self, sample_market_data):
        """Test DataLoader initialization."""
        loader = DataLoader(data=sample_market_data)
        assert loader.data is not None
        assert not loader.data.empty
        assert len(loader.data) == len(sample_market_data)

    def test_init_with_path(self, temp_dir, sample_market_data):
        """Test DataLoader initialization with file path."""
        # Save sample data to CSV
        file_path = temp_dir / "test_data.csv"
        sample_market_data.to_csv(file_path, index=False)

        loader = DataLoader(file_path=file_path)
        assert loader.data is not None
        assert not loader.data.empty
        assert loader.data.shape == sample_market_data.shape

    def test_init_with_config(self, sample_market_data):
        """Test DataLoader with configuration."""
        config = {
            "data": {
                "features": ["open", "high", "low", "close", "volume"],
                "target": "close",
                "lookback": 10,
                "forecast_horizon": 1,
            }
        }
        loader = DataLoader(data=sample_market_data, config=config)
        assert loader.config == config["data"]

    def test_split_data(self, sample_market_data):
        """Test data splitting into train, validation, test sets."""
        loader = DataLoader(data=sample_market_data)
        train, val, test = loader.split_data(
            train_ratio=0.7,
            val_ratio=0.15,
            test_ratio=0.15,
            shuffle=False
        )

        total = len(sample_market_data)
        expected_train = int(total * 0.7)
        expected_val = int(total * 0.15)
        expected_test = total - expected_train - expected_val

        assert len(train) == expected_train
        assert len(val) == expected_val
        assert len(test) == expected_test

    def test_split_data_time_based(self, sample_market_data):
        """Test time-based data splitting."""
        loader = DataLoader(data=sample_market_data)
        train, val, test = loader.split_data(
            train_ratio=0.7,
            val_ratio=0.15,
            test_ratio=0.15,
            shuffle=False,
            time_based=True
        )

        # Verify that data is in chronological order
        assert train['timestamp'].max() < val['timestamp'].min()
        assert val['timestamp'].max() < test['timestamp'].min()

    def test_create_sequences(self, sample_market_data):
        """Test creating sequences for time series."""
        loader = DataLoader(
            data=sample_market_data,
            lookback=10,
            forecast_horizon=1
        )
        
        X, y = loader.create_sequences(
            feature_cols=['open', 'high', 'low', 'close', 'volume'],
            target_col='close'
        )

        expected_sequences = len(sample_market_data) - 10 - 1 + 1
        assert X.shape[0] == expected_sequences
        assert X.shape[1] == 10
        assert X.shape[2] == 5  # 5 features
        assert y.shape[0] == expected_sequences

    def test_create_sequences_with_target(self, sample_market_data):
        """Test creating sequences with specified target."""
        loader = DataLoader(data=sample_market_data, lookback=5)
        X, y = loader.create_sequences(
            feature_cols=['close', 'volume'],
            target_col='close'
        )

        assert X.shape[2] == 2  # 2 features
        assert y.shape[1] == 1  # 1 target

    def test_batch_generator(self, sample_market_data):
        """Test batch generator functionality."""
        loader = DataLoader(data=sample_market_data, batch_size=32)
        X, y = loader.create_sequences(
            feature_cols=['close'],
            target_col='close'
        )

        batches = list(loader.batch_generator(X, y))
        expected_batches = int(np.ceil(len(X) / 32))

        assert len(batches) == expected_batches
        for batch_X, batch_y in batches:
            assert batch_X.shape[0] <= 32
            assert batch_y.shape[0] <= 32
            assert batch_X.shape[1] == X.shape[1]
            assert batch_X.shape[2] == X.shape[2]

    def test_normalize_data(self, sample_market_data):
        """Test data normalization."""
        loader = DataLoader(data=sample_market_data)
        
        # Fit scaler on training data
        train = sample_market_data.iloc[:800]
        scaler = loader.fit_scaler(train, method='standard')
        
        assert scaler is not None
        assert hasattr(scaler, 'mean_')
        assert hasattr(scaler, 'scale_')

    def test_transform_data(self, sample_market_data):
        """Test data transformation using fitted scaler."""
        loader = DataLoader(data=sample_market_data)
        
        train = sample_market_data.iloc[:800]
        test = sample_market_data.iloc[800:]
        
        scaler = loader.fit_scaler(train)
        transformed = loader.transform_data(test, scaler)
        
        assert transformed is not None
        assert transformed.shape == test.shape

    def test_inverse_transform(self, sample_market_data):
        """Test inverse transformation."""
        loader = DataLoader(data=sample_market_data)
        
        train = sample_market_data.iloc[:800]
        scaler = loader.fit_scaler(train)
        
        # Transform and inverse transform
        transformed = loader.transform_data(train, scaler)
        inverse = loader.inverse_transform(transformed, scaler)
        
        # Should recover original values approximately
        np.testing.assert_array_almost_equal(
            inverse.values, train.values, decimal=5
        )

    def test_missing_data_handling(self):
        """Test handling of missing data."""
        # Create data with missing values
        data = pd.DataFrame({
            'open': [100, 101, np.nan, 103, 104],
            'high': [101, 102, 103, np.nan, 105],
            'low': [99, 100, 101, 102, 103],
            'close': [100, 101, 102, 103, 104],
            'volume': [1000, 1100, 1200, 1300, 1400]
        })
        
        loader = DataLoader(data=data)
        
        # Test drop method
        cleaned = loader.handle_missing(method='drop')
        assert len(cleaned) == 3  # Two rows dropped
        
        # Test fill method
        cleaned_fill = loader.handle_missing(method='fill', fill_value=0)
        assert cleaned_fill['open'].iloc[2] == 0
        assert cleaned_fill['high'].iloc[3] == 0

    def test_handle_outliers(self):
        """Test outlier handling."""
        data = pd.DataFrame({
            'close': [100, 101, 102, 103, 1000, 104, 105],
            'volume': [1000, 1100, 1200, 1300, 100000, 1400, 1500]
        })
        
        loader = DataLoader(data=data)
        
        # Test z-score method
        cleaned_z = loader.handle_outliers(method='zscore', threshold=3)
        assert len(cleaned_z) < len(data)  # Some outliers removed
        
        # Test IQR method
        cleaned_iqr = loader.handle_outliers(method='iqr')
        assert len(cleaned_iqr) < len(data)

    def test_resample_data(self, sample_market_data):
        """Test data resampling."""
        loader = DataLoader(data=sample_market_data)
        
        # Resample to lower frequency
        resampled = loader.resample_data(
            freq='W',  # Weekly
            agg_method={'open': 'first', 'high': 'max', 'low': 'min', 
                       'close': 'last', 'volume': 'sum'}
        )
        
        assert len(resampled) < len(sample_market_data)
        assert isinstance(resampled.index, pd.DatetimeIndex)

    def test_save_load_loader_state(self, temp_dir, sample_market_data):
        """Test saving and loading DataLoader state."""
        loader = DataLoader(data=sample_market_data)
        loader.lookback = 20
        loader.batch_size = 64
        
        # Save state
        save_path = temp_dir / "loader_state.pkl"
        loader.save_state(save_path)
        assert save_path.exists()
        
        # Load state
        new_loader = DataLoader()
        new_loader.load_state(save_path)
        
        assert new_loader.lookback == loader.lookback
        assert new_loader.batch_size == loader.batch_size
        assert new_loader.data.equals(loader.data)


class TestDataPreprocessor:
    """Tests for DataPreprocessor class."""

    def test_initialization(self):
        """Test DataPreprocessor initialization."""
        preprocessor = DataPreprocessor()
        assert preprocessor is not None
        assert preprocessor.scalers == {}

    def test_fit_scaler(self, sample_market_data):
        """Test fitting scaler on data."""
        preprocessor = DataPreprocessor()
        scaler = preprocessor.fit_scaler(
            sample_market_data[['close', 'volume']],
            method='standard'
        )
        assert scaler is not None
        assert hasattr(scaler, 'mean_')
        assert hasattr(scaler, 'scale_')

    def test_transform_scaler(self, sample_market_data):
        """Test transforming data with scaler."""
        preprocessor = DataPreprocessor()
        
        # Fit on training data
        train = sample_market_data.iloc[:800]
        scaler = preprocessor.fit_scaler(train[['close', 'volume']])
        
        # Transform test data
        test = sample_market_data.iloc[800:]
        transformed = preprocessor.transform_scaler(
            test[['close', 'volume']],
            scaler
        )
        
        assert transformed is not None
        assert transformed.shape[1] == 2
        assert transformed.values.std() > 0  # Should be scaled

    def test_pipeline_creation(self, sample_market_data):
        """Test creation of preprocessing pipeline."""
        preprocessor = DataPreprocessor()
        
        pipeline = preprocessor.create_pipeline([
            ('scale', 'standard'),
            ('pca', {'n_components': 2})
        ])
        
        assert pipeline is not None
        assert hasattr(pipeline, 'fit_transform')

    def test_feature_engineering(self, sample_market_data):
        """Test feature engineering methods."""
        preprocessor = DataPreprocessor()
        
        # Add technical indicators
        df = preprocessor.add_technical_indicators(sample_market_data)
        
        assert 'sma_20' in df.columns
        assert 'ema_10' in df.columns
        assert 'rsi' in df.columns
        assert 'macd' in df.columns
        
        # Add lag features
        df_lags = preprocessor.add_lag_features(
            sample_market_data,
            columns=['close'],
            lags=[1, 2, 3]
        )
        
        assert 'close_lag_1' in df_lags.columns
        assert 'close_lag_2' in df_lags.columns
        assert 'close_lag_3' in df_lags.columns

    def test_rolling_statistics(self, sample_market_data):
        """Test rolling statistics computation."""
        preprocessor = DataPreprocessor()
        
        df = preprocessor.add_rolling_statistics(
            sample_market_data,
            columns=['close'],
            windows=[5, 10, 20]
        )
        
        assert 'close_rolling_mean_5' in df.columns
        assert 'close_rolling_std_10' in df.columns
        assert 'close_rolling_min_20' in df.columns
        assert 'close_rolling_max_20' in df.columns

    def test_encoding_categorical(self):
        """Test encoding categorical variables."""
        data = pd.DataFrame({
            'symbol': ['AAPL', 'GOOGL', 'MSFT', 'AAPL', 'GOOGL'],
            'sector': ['Tech', 'Tech', 'Tech', 'Tech', 'Tech']
        })
        
        preprocessor = DataPreprocessor()
        
        # One-hot encoding
        encoded = preprocessor.encode_categorical(
            data,
            columns=['symbol'],
            method='onehot'
        )
        
        assert 'symbol_AAPL' in encoded.columns
        assert 'symbol_GOOGL' in encoded.columns
        assert 'symbol_MSFT' in encoded.columns
        
        # Label encoding
        encoded_label = preprocessor.encode_categorical(
            data,
            columns=['symbol'],
            method='label'
        )
        
        assert 'symbol' in encoded_label.columns
        assert encoded_label['symbol'].dtype == int

    def test_handle_missing_values(self):
        """Test handling missing values."""
        data = pd.DataFrame({
            'A': [1, 2, np.nan, 4, 5],
            'B': [10, np.nan, 30, 40, 50],
            'C': [100, 200, 300, 400, 500]
        })
        
        preprocessor = DataPreprocessor()
        
        # Drop missing
        dropped = preprocessor.handle_missing(data, method='drop')
        assert len(dropped) == 2  # Only rows without NaN
        
        # Fill with mean
        filled = preprocessor.handle_missing(data, method='fill', strategy='mean')
        assert filled['A'].iloc[2] == data['A'].mean()
        assert filled['B'].iloc[1] == data['B'].mean()
        
        # Fill with forward fill
        ffill = preprocessor.handle_missing(data, method='fill', strategy='ffill')
        assert ffill['A'].iloc[2] == 2  # forward fill

    def test_remove_outliers(self):
        """Test outlier removal."""
        data = pd.DataFrame({
            'close': [100, 101, 102, 103, 1000, 104, 105],
            'volume': [1000, 1100, 1200, 1300, 100000, 1400, 1500]
        })
        
        preprocessor = DataPreprocessor()
        
        # Remove using z-score
        cleaned = preprocessor.remove_outliers(
            data,
            method='zscore',
            threshold=3
        )
        assert len(cleaned) < len(data)  # Outliers removed

    def test_normalize_dataframe(self, sample_market_data):
        """Test DataFrame normalization."""
        preprocessor = DataPreprocessor()
        
        normalized = preprocessor.normalize_dataframe(
            sample_market_data[['close', 'volume']],
            method='minmax'
        )
        
        assert normalized['close'].min() >= 0
        assert normalized['close'].max() <= 1
        assert normalized['volume'].min() >= 0
        assert normalized['volume'].max() <= 1

    def test_standardize_dataframe(self, sample_market_data):
        """Test DataFrame standardization."""
        preprocessor = DataPreprocessor()
        
        standardized = preprocessor.standardize_dataframe(
            sample_market_data[['close', 'volume']]
        )
        
        # Should have mean ~0 and std ~1
        assert abs(standardized['close'].mean()) < 1e-6
        assert abs(standardized['volume'].mean()) < 1e-6
        assert abs(standardized['close'].std() - 1) < 1e-6

    def test_create_lags(self, sample_market_data):
        """Test lag feature creation."""
        preprocessor = DataPreprocessor()
        
        df_lags = preprocessor.create_lags(
            sample_market_data,
            columns=['close'],
            lags=[1, 2, 3, 5, 10]
        )
        
        for lag in [1, 2, 3, 5, 10]:
            assert f'close_lag_{lag}' in df_lags.columns

    def test_create_lags_with_different_columns(self, sample_market_data):
        """Test lag creation for multiple columns."""
        preprocessor = DataPreprocessor()
        
        df_lags = preprocessor.create_lags(
            sample_market_data,
            columns=['close', 'volume'],
            lags=[1, 2]
        )
        
        assert 'close_lag_1' in df_lags.columns
        assert 'close_lag_2' in df_lags.columns
        assert 'volume_lag_1' in df_lags.columns
        assert 'volume_lag_2' in df_lags.columns

    def test_add_technical_indicators_full(self, sample_market_data):
        """Test adding all technical indicators."""
        preprocessor = DataPreprocessor()
        
        df = preprocessor.add_technical_indicators(
            sample_market_data,
            include_all=True
        )
        
        # Check for some expected indicators
        expected_indicators = [
            'sma_10', 'sma_20', 'sma_50',
            'ema_10', 'ema_20',
            'rsi', 'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_middle', 'bb_lower',
            'atr', 'adx'
        ]
        
        for indicator in expected_indicators:
            assert indicator in df.columns

    def test_pca_reduction(self, sample_market_data):
        """Test PCA dimension reduction."""
        preprocessor = DataPreprocessor()
        
        # Prepare data
        features = ['open', 'high', 'low', 'close', 'volume']
        data = sample_market_data[features]
        
        # Apply PCA
        reduced = preprocessor.reduce_dimensions(
            data,
            method='pca',
            n_components=2
        )
        
        assert reduced.shape[1] == 2

    def test_save_load_preprocessor_state(self, temp_dir, sample_market_data):
        """Test saving and loading preprocessor state."""
        preprocessor = DataPreprocessor()
        
        # Fit some scalers
        preprocessor.fit_scaler(sample_market_data[['close']], name='close_scaler')
        preprocessor.fit_scaler(sample_market_data[['volume']], name='volume_scaler')
        
        # Save state
        save_path = temp_dir / "preprocessor_state.pkl"
        preprocessor.save_state(save_path)
        assert save_path.exists()
        
        # Load state
        new_preprocessor = DataPreprocessor()
        new_preprocessor.load_state(save_path)
        
        assert 'close_scaler' in new_preprocessor.scalers
        assert 'volume_scaler' in new_preprocessor.scalers

    def test_full_preprocessing_pipeline(self, sample_market_data):
        """Test the complete preprocessing pipeline."""
        preprocessor = DataPreprocessor()
        
        # Define pipeline steps
        pipeline = [
            ('handle_missing', {'method': 'fill', 'strategy': 'ffill'}),
            ('remove_outliers', {'method': 'zscore', 'threshold': 3}),
            ('add_technical_indicators', {}),
            ('create_lags', {'columns': ['close'], 'lags': [1, 2, 3]}),
            ('standardize', {})
        ]
        
        # Execute pipeline
        processed = preprocessor.run_pipeline(sample_market_data, pipeline)
        
        # Check that processing was applied
        assert processed is not None
        assert not processed.empty
        assert 'sma_20' in processed.columns
        assert 'close_lag_1' in processed.columns
        assert processed.shape[1] > sample_market_data.shape[1]

    def test_custom_transformer(self, sample_market_data):
        """Test adding and using a custom transformer."""
        preprocessor = DataPreprocessor()
        
        # Add custom transformer
        def custom_transformer(df):
            df['custom_feature'] = df['close'] / df['volume']
            return df
        
        preprocessor.add_transformer('custom_feature', custom_transformer)
        result = preprocessor.apply_transformer(sample_market_data, 'custom_feature')
        
        assert 'custom_feature' in result.columns
        assert (result['custom_feature'] == sample_market_data['close'] / sample_market_data['volume']).all()


# Integration tests
class TestDataLoaderIntegration:
    """Integration tests for DataLoader with Preprocessor."""

    def test_end_to_end_processing(self, sample_market_data):
        """Test end-to-end data processing pipeline."""
        # Create loader
        loader = DataLoader(data=sample_market_data)
        
        # Split data
        train, val, test = loader.split_data(train_ratio=0.7, val_ratio=0.15)
        
        # Create preprocessor
        preprocessor = DataPreprocessor()
        
        # Fit preprocessor on training data
        scaler = preprocessor.fit_scaler(train[['close', 'volume']])
        
        # Transform all sets
        train_scaled = preprocessor.transform_scaler(train[['close', 'volume']], scaler)
        val_scaled = preprocessor.transform_scaler(val[['close', 'volume']], scaler)
        test_scaled = preprocessor.transform_scaler(test[['close', 'volume']], scaler)
        
        # Create sequences
        X_train, y_train = loader.create_sequences(
            train_scaled,
            feature_cols=['close', 'volume'],
            target_col='close'
        )
        X_val, y_val = loader.create_sequences(
            val_scaled,
            feature_cols=['close', 'volume'],
            target_col='close'
        )
        X_test, y_test = loader.create_sequences(
            test_scaled,
            feature_cols=['close', 'volume'],
            target_col='close'
        )
        
        # Verify shapes
        assert X_train.shape[2] == 2
        assert X_val.shape[2] == 2
        assert X_test.shape[2] == 2
        
        # Batch creation
        batch_size = 32
        train_batches = list(loader.batch_generator(X_train, y_train, batch_size))
        assert len(train_batches) > 0


if __name__ == "__main__":
    pytest.main([__file__])

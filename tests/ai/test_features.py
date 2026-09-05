"""
AI Features Tests
===================

This module contains tests for the AI feature engineering components
including FeatureEngine, feature extraction, selection, and transformation.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock

from trading.bots.swing_bot.ai.features import FeatureEngine, FeatureSet
from trading.bots.swing_bot.ai.data import DataPreprocessor
from trading.bots.swing_bot.utils.validators import validate_data


class TestFeatureEngine:
    """Tests for FeatureEngine class."""

    @pytest.fixture
    def feature_engine(self):
        """Create a FeatureEngine instance."""
        return FeatureEngine()

    @pytest.fixture
    def sample_market_data(self):
        """Create sample market data for testing."""
        n = 100
        np.random.seed(42)
        dates = [datetime.now() - timedelta(days=i) for i in range(n)]
        close = 100 + np.cumsum(np.random.normal(0, 0.5, n))
        volume = np.random.uniform(100000, 1000000, n)
        
        return pd.DataFrame({
            'timestamp': dates,
            'open': close * (1 + np.random.uniform(-0.01, 0.01, n)),
            'high': close * (1 + np.random.uniform(0, 0.02, n)),
            'low': close * (1 - np.random.uniform(0, 0.02, n)),
            'close': close,
            'volume': volume,
            'symbol': 'AAPL'
        })

    def test_initialization(self, feature_engine):
        """Test FeatureEngine initialization."""
        assert feature_engine is not None
        assert feature_engine.scaler is None
        assert feature_engine.selected_features == []
        assert feature_engine.feature_importances == {}

    def test_add_feature(self, feature_engine):
        """Test adding a custom feature."""
        def custom_feature(df):
            return df['close'] / df['volume']

        feature_engine.add_feature('close_to_volume', custom_feature)
        assert 'close_to_volume' in feature_engine.feature_functions
        assert callable(feature_engine.feature_functions['close_to_volume'])

    def test_add_feature_duplicate(self, feature_engine):
        """Test adding duplicate feature."""
        def custom_feature(df):
            return df['close'] / df['volume']
        
        feature_engine.add_feature('test_feature', custom_feature)
        with pytest.raises(ValueError):
            feature_engine.add_feature('test_feature', custom_feature)

    def test_remove_feature(self, feature_engine):
        """Test removing a feature."""
        def custom_feature(df):
            return df['close'] / df['volume']
        
        feature_engine.add_feature('test_feature', custom_feature)
        feature_engine.remove_feature('test_feature')
        assert 'test_feature' not in feature_engine.feature_functions

    def test_get_price_features(self, feature_engine, sample_market_data):
        """Test price feature extraction."""
        features = feature_engine.get_price_features(sample_market_data)
        
        assert 'price_change_1' in features.columns
        assert 'price_change_5' in features.columns
        assert 'price_change_10' in features.columns
        assert 'price_high_low_ratio' in features.columns
        assert 'price_position' in features.columns

    def test_get_volume_features(self, feature_engine, sample_market_data):
        """Test volume feature extraction."""
        features = feature_engine.get_volume_features(sample_market_data)
        
        assert 'volume_ratio' in features.columns
        assert 'volume_change_1' in features.columns
        assert 'volume_change_5' in features.columns
        assert 'volume_velocity' in features.columns

    def test_get_volatility_features(self, feature_engine, sample_market_data):
        """Test volatility feature extraction."""
        features = feature_engine.get_volatility_features(sample_market_data)
        
        assert 'volatility_5' in features.columns
        assert 'volatility_10' in features.columns
        assert 'volatility_20' in features.columns
        assert 'volatility_ratio' in features.columns

    def test_get_momentum_features(self, feature_engine, sample_market_data):
        """Test momentum feature extraction."""
        features = feature_engine.get_momentum_features(sample_market_data)
        
        assert 'momentum_5' in features.columns
        assert 'momentum_10' in features.columns
        assert 'momentum_20' in features.columns
        assert 'momentum_velocity' in features.columns

    def test_get_technical_features(self, feature_engine, sample_market_data):
        """Test technical indicator features."""
        features = feature_engine.get_technical_features(sample_market_data)
        
        assert 'sma_10' in features.columns
        assert 'sma_20' in features.columns
        assert 'ema_10' in features.columns
        assert 'rsi' in features.columns
        assert 'macd' in features.columns
        assert 'bb_upper' in features.columns
        assert 'bb_middle' in features.columns
        assert 'bb_lower' in features.columns
        assert 'atr' in features.columns
        assert 'adx' in features.columns

    def test_get_technical_features_with_params(self, feature_engine, sample_market_data):
        """Test technical features with custom parameters."""
        params = {
            'sma_windows': [5, 15],
            'ema_windows': [8, 16],
            'rsi_period': 10,
            'macd_fast': 8,
            'macd_slow': 16,
            'bb_period': 15,
            'atr_period': 10,
        }
        features = feature_engine.get_technical_features(
            sample_market_data, **params
        )
        
        assert 'sma_5' in features.columns
        assert 'sma_15' in features.columns
        assert 'ema_8' in features.columns
        assert 'ema_16' in features.columns
        assert features['rsi'].notna().all()  # RSI should be computed

    def test_get_statistical_features(self, feature_engine, sample_market_data):
        """Test statistical feature extraction."""
        features = feature_engine.get_statistical_features(sample_market_data)
        
        assert 'returns_skew' in features.columns
        assert 'returns_kurtosis' in features.columns
        assert 'returns_autocorr' in features.columns
        assert 'price_zscore' in features.columns
        assert 'volume_zscore' in features.columns

    def test_get_time_features(self, feature_engine, sample_market_data):
        """Test time-based feature extraction."""
        features = feature_engine.get_time_features(sample_market_data)
        
        assert 'day_of_week' in features.columns
        assert 'month' in features.columns
        assert 'quarter' in features.columns
        assert 'day_of_year' in features.columns
        assert 'week_of_year' in features.columns

    def test_get_lag_features(self, feature_engine, sample_market_data):
        """Test lag feature creation."""
        features = feature_engine.get_lag_features(
            sample_market_data,
            columns=['close', 'volume'],
            lags=[1, 2, 3]
        )
        
        assert 'close_lag_1' in features.columns
        assert 'close_lag_2' in features.columns
        assert 'close_lag_3' in features.columns
        assert 'volume_lag_1' in features.columns
        assert 'volume_lag_2' in features.columns
        assert 'volume_lag_3' in features.columns

    def test_get_rolling_features(self, feature_engine, sample_market_data):
        """Test rolling window features."""
        features = feature_engine.get_rolling_features(
            sample_market_data,
            columns=['close'],
            windows=[5, 10, 20]
        )
        
        assert 'close_rolling_mean_5' in features.columns
        assert 'close_rolling_std_10' in features.columns
        assert 'close_rolling_min_20' in features.columns
        assert 'close_rolling_max_20' in features.columns

    def test_get_all_features(self, feature_engine, sample_market_data):
        """Test extraction of all features."""
        features = feature_engine.get_all_features(sample_market_data)
        
        # Should contain features from all categories
        assert 'price_change_1' in features.columns
        assert 'volume_ratio' in features.columns
        assert 'volatility_5' in features.columns
        assert 'momentum_5' in features.columns
        assert 'sma_10' in features.columns
        assert 'returns_skew' in features.columns
        assert 'day_of_week' in features.columns
        assert 'close_lag_1' in features.columns
        assert 'close_rolling_mean_5' in features.columns

    def test_feature_selection_correlation(self, feature_engine, sample_market_data):
        """Test correlation-based feature selection."""
        # Create many features
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        # Add target
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        selected = feature_engine.select_features(
            features, target,
            method='correlation',
            threshold=0.1,
            max_features=10
        )
        
        assert selected is not None
        assert len(selected.columns) <= 10
        assert all(col in features.columns for col in selected.columns)

    def test_feature_selection_mutual_info(self, feature_engine, sample_market_data):
        """Test mutual information feature selection."""
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        selected = feature_engine.select_features(
            features, target,
            method='mutual_info',
            max_features=8
        )
        
        assert selected is not None
        assert len(selected.columns) <= 8

    def test_feature_selection_rfe(self, feature_engine, sample_market_data):
        """Test recursive feature elimination."""
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        selected = feature_engine.select_features(
            features, target,
            method='rfe',
            max_features=8
        )
        
        assert selected is not None
        assert len(selected.columns) <= 8

    def test_feature_selection_l1(self, feature_engine, sample_market_data):
        """Test L1-based feature selection."""
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        selected = feature_engine.select_features(
            features, target,
            method='l1',
            max_features=10
        )
        
        assert selected is not None
        assert len(selected.columns) <= 10

    def test_feature_scaling(self, feature_engine, sample_market_data):
        """Test feature scaling."""
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        # Fit scaler
        feature_engine.fit_scaler(features, method='standard')
        assert feature_engine.scaler is not None
        
        # Transform
        scaled = feature_engine.transform_scaler(features)
        assert scaled is not None
        assert scaled.shape == features.shape
        
        # Check that scaled values have mean ~0 and std ~1
        assert abs(scaled.mean().mean()) < 1e-6
        assert abs(scaled.std().mean() - 1) < 0.1

    def test_feature_scaling_minmax(self, feature_engine, sample_market_data):
        """Test min-max feature scaling."""
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        feature_engine.fit_scaler(features, method='minmax')
        scaled = feature_engine.transform_scaler(features)
        
        # All values should be between 0 and 1
        assert scaled.min().min() >= 0
        assert scaled.max().max() <= 1

    def test_feature_importance_permutation(self, feature_engine, sample_market_data):
        """Test permutation feature importance."""
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        # Mock model
        model = Mock()
        model.predict = Mock(return_value=np.random.randn(len(features)))
        
        importance = feature_engine.calculate_feature_importance(
            features, target, model,
            method='permutation'
        )
        
        assert importance is not None
        assert len(importance) == features.shape[1]
        assert sum(importance.values()) > 0

    def test_feature_importance_shap(self, feature_engine, sample_market_data):
        """Test SHAP feature importance."""
        # This test may be skipped if shap is not installed
        try:
            import shap
        except ImportError:
            pytest.skip("shap not installed")
        
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        # Mock model
        model = Mock()
        model.predict = Mock(return_value=np.random.randn(len(features)))
        
        importance = feature_engine.calculate_feature_importance(
            features, target, model,
            method='shap'
        )
        
        assert importance is not None
        assert len(importance) == features.shape[1]

    def test_feature_pipeline(self, feature_engine, sample_market_data):
        """Test full feature pipeline."""
        pipeline = [
            ('get_price_features', {}),
            ('get_volume_features', {}),
            ('get_volatility_features', {}),
            ('get_momentum_features', {}),
            ('get_technical_features', {}),
            ('get_statistical_features', {}),
            ('get_time_features', {}),
            ('get_lag_features', {'columns': ['close'], 'lags': [1, 2, 3]}),
            ('get_rolling_features', {'columns': ['close'], 'windows': [5, 10]}),
        ]
        
        features = feature_engine.run_pipeline(sample_market_data, pipeline)
        
        assert features is not None
        assert not features.empty
        assert features.shape[1] > sample_market_data.shape[1]

    def test_feature_pipeline_with_scaling(self, feature_engine, sample_market_data):
        """Test feature pipeline with scaling step."""
        pipeline = [
            ('get_price_features', {}),
            ('get_volume_features', {}),
            ('scale', {'method': 'standard'}),
        ]
        
        features = feature_engine.run_pipeline(sample_market_data, pipeline)
        
        assert features is not None
        # Check that scaling was applied
        assert abs(features.mean().mean()) < 1e-6

    def test_save_load_feature_engine(self, feature_engine, sample_market_data, temp_dir):
        """Test saving and loading FeatureEngine state."""
        # Fit scaler
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        feature_engine.fit_scaler(features, method='standard')
        
        # Add feature functions
        def custom_feature(df):
            return df['close'] / df['volume']
        feature_engine.add_feature('custom', custom_feature)
        
        # Save state
        save_path = temp_dir / "feature_engine.pkl"
        feature_engine.save_state(save_path)
        assert save_path.exists()
        
        # Load state
        new_engine = FeatureEngine()
        new_engine.load_state(save_path)
        
        assert new_engine.scaler is not None
        assert 'custom' in new_engine.feature_functions

    def test_feature_set_creation(self, feature_engine, sample_market_data):
        """Test FeatureSet creation."""
        features = feature_engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        feature_set = feature_engine.create_feature_set(
            features, target,
            feature_names=features.columns.tolist(),
            description="Test feature set"
        )
        
        assert feature_set is not None
        assert isinstance(feature_set, FeatureSet)
        assert len(feature_set.feature_names) == features.shape[1]
        assert feature_set.description == "Test feature set"


class TestFeatureSet:
    """Tests for FeatureSet class."""

    @pytest.fixture
    def feature_set(self, sample_market_data):
        """Create a FeatureSet instance."""
        features = FeatureEngine().get_all_features(sample_market_data)
        features = features.dropna()
        
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        return FeatureSet(
            features=features,
            target=target,
            feature_names=features.columns.tolist(),
            description="Test set"
        )

    def test_initialization(self, feature_set):
        """Test FeatureSet initialization."""
        assert feature_set.features is not None
        assert feature_set.target is not None
        assert feature_set.feature_names is not None
        assert feature_set.description == "Test set"
        assert feature_set.metadata == {}

    def test_add_metadata(self, feature_set):
        """Test adding metadata."""
        feature_set.add_metadata('test_key', 'test_value')
        assert feature_set.metadata['test_key'] == 'test_value'

    def test_get_feature_data(self, feature_set):
        """Test getting feature data."""
        data = feature_set.get_feature_data()
        assert data is not None
        assert data.shape == feature_set.features.shape

    def test_get_target_data(self, feature_set):
        """Test getting target data."""
        data = feature_set.get_target_data()
        assert data is not None
        assert data.shape == feature_set.target.shape

    def test_split(self, feature_set):
        """Test splitting feature set."""
        train_set, val_set, test_set = feature_set.split(
            train_ratio=0.7, val_ratio=0.15, test_ratio=0.15
        )
        
        assert train_set is not None
        assert val_set is not None
        assert test_set is not None
        
        total = len(feature_set.features)
        assert len(train_set.features) == int(total * 0.7)
        assert len(val_set.features) == int(total * 0.15)
        assert len(test_set.features) == int(total * 0.15)

    def test_to_dict(self, feature_set):
        """Test conversion to dictionary."""
        data = feature_set.to_dict()
        assert 'feature_names' in data
        assert 'description' in data
        assert 'metadata' in data
        assert 'features_shape' in data

    def test_from_dict(self, feature_set):
        """Test creation from dictionary."""
        data = feature_set.to_dict()
        new_set = FeatureSet.from_dict(data)
        assert new_set.feature_names == feature_set.feature_names
        assert new_set.description == feature_set.description


class TestFeatureIntegration:
    """Integration tests for feature engineering."""

    def test_end_to_end_feature_pipeline(self, sample_market_data):
        """Test complete feature pipeline end-to-end."""
        engine = FeatureEngine()
        
        # 1. Extract all features
        features = engine.get_all_features(sample_market_data)
        features = features.dropna()
        
        # 2. Create target
        target = features['close'].shift(-1) > features['close']
        target = target.astype(int).dropna()
        features = features.iloc[:-1]
        
        # 3. Split data
        split_idx = int(len(features) * 0.8)
        train_features = features.iloc[:split_idx]
        train_target = target.iloc[:split_idx]
        test_features = features.iloc[split_idx:]
        test_target = target.iloc[split_idx:]
        
        # 4. Fit scaler
        engine.fit_scaler(train_features, method='standard')
        
        # 5. Scale all data
        train_scaled = engine.transform_scaler(train_features)
        test_scaled = engine.transform_scaler(test_features)
        
        # 6. Select features
        selected = engine.select_features(
            train_scaled, train_target,
            method='correlation',
            threshold=0.05,
            max_features=15
        )
        
        # 7. Create feature set
        feature_set = engine.create_feature_set(
            selected, train_target,
            description="End-to-end test"
        )
        
        assert feature_set is not None
        assert len(feature_set.feature_names) <= 15
        assert feature_set.features.shape[1] <= 15

    def test_custom_feature_pipeline(self, sample_market_data):
        """Test pipeline with custom features."""
        engine = FeatureEngine()
        
        # Add custom feature
        def custom_feature(df):
            return df['close'] * df['volume'] / 1e6
        
        engine.add_feature('custom_value', custom_feature)
        
        # Build pipeline
        pipeline = [
            ('get_price_features', {}),
            ('get_volume_features', {}),
            ('custom_value', {}),
            ('scale', {'method': 'standard'}),
        ]
        
        features = engine.run_pipeline(sample_market_data, pipeline)
        
        assert 'custom_value' in features.columns
        assert features.shape[1] > 0


if __name__ == "__main__":
    pytest.main([__file__])

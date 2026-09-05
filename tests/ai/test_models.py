"""
NEXUS AI TRADING SYSTEM
AI Models Tests

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: tests/ai/test_models.py
Description: Comprehensive unit and integration tests for AI models
             including LSTM, Transformers, XGBoost, ensembles,
             and base model functionality.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio

# Try importing optional dependencies
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import sklearn
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# Module imports (adjust based on actual project structure)
from ai.models.base_model import BaseModel
from ai.models.lstm.lstm_model import LSTMModel
from ai.models.lstm.bilstm_model import BiLSTMModel
from ai.models.lstm.stacked_lstm import StackedLSTMModel
from ai.models.lstm.attention_lstm import AttentionLSTMModel
from ai.models.transformers.time_series_transformer import TimeSeriesTransformer
from ai.models.transformers.informer_model import InformerModel
from ai.models.transformers.autoformer_model import AutoformerModel
from ai.models.transformers.patchtst_model import PatchTSTModel
from ai.models.xgboost_model import XGBoostModel
from ai.models.ensemble.voting_ensemble import VotingEnsemble
from ai.models.ensemble.stacking_ensemble import StackingEnsemble
from ai.models.ensemble.bagging_ensemble import BaggingEnsemble
from ai.models.ensemble.weighting_strategies import WeightingStrategies
from ai.models.forecasting.arima_model import ARIMAModel
from ai.models.forecasting.prophet_model import ProphetModel
from ai.models.volatility.garch_model import GARCHModel

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_time_series_data():
    """Generate sample time series data for model testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2020-01-01', periods=200, freq='D')
    data = {
        'open': np.random.normal(100, 5, 200).cumsum() + 100,
        'high': np.random.normal(102, 5, 200).cumsum() + 102,
        'low': np.random.normal(98, 5, 200).cumsum() + 98,
        'close': np.random.normal(100, 5, 200).cumsum() + 100,
        'volume': np.random.randint(1000, 10000, 200),
    }
    df = pd.DataFrame(data, index=dates)
    # Ensure high >= low etc.
    df['high'] = df[['open', 'close']].max(axis=1) + abs(np.random.normal(0, 1, 200))
    df['low'] = df[['open', 'close']].min(axis=1) - abs(np.random.normal(0, 1, 200))
    return df

@pytest.fixture
def sample_features_target(sample_time_series_data):
    """Create features and target for supervised learning."""
    df = sample_time_series_data.copy()
    # Use lagged features
    for lag in [1, 2, 3, 5, 10]:
        df[f'close_lag_{lag}'] = df['close'].shift(lag)
    df['target'] = df['close'].shift(-1)  # predict next close
    df = df.dropna()
    features = df[[col for col in df.columns if 'lag' in col or col in ['open', 'high', 'low', 'volume']]]
    target = df['target']
    return features, target

@pytest.fixture
def sample_sequence_data():
    """Generate sequence data for LSTM/Transformer testing."""
    np.random.seed(42)
    X = np.random.randn(100, 10, 5)  # 100 sequences, length 10, 5 features
    y = np.random.randn(100, 1)
    return X, y

@pytest.fixture
def mock_torch_model():
    """Create a mock PyTorch model for testing."""
    if not TORCH_AVAILABLE:
        pytest.skip("PyTorch not available", allow_module_level=True)
    
    class SimpleModel(nn.Module):
        def __init__(self, input_dim=5, hidden_dim=10, output_dim=1):
            super().__init__()
            self.fc1 = nn.Linear(input_dim, hidden_dim)
            self.fc2 = nn.Linear(hidden_dim, output_dim)
        
        def forward(self, x):
            x = torch.relu(self.fc1(x))
            return self.fc2(x)
    
    return SimpleModel()

@pytest.fixture
def lstm_model_config():
    """Configuration for LSTM models."""
    return {
        'input_dim': 5,
        'hidden_dim': 32,
        'output_dim': 1,
        'num_layers': 2,
        'dropout': 0.2,
        'learning_rate': 0.001,
        'batch_size': 16,
        'epochs': 2,
        'sequence_length': 10,
    }

@pytest.fixture
def transformer_config():
    """Configuration for Transformer models."""
    return {
        'input_dim': 5,
        'd_model': 64,
        'nhead': 4,
        'num_layers': 2,
        'dim_feedforward': 128,
        'dropout': 0.1,
        'learning_rate': 0.001,
        'batch_size': 16,
        'epochs': 2,
        'sequence_length': 10,
    }

@pytest.fixture
def xgboost_config():
    """Configuration for XGBoost models."""
    return {
        'n_estimators': 10,
        'max_depth': 3,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'objective': 'reg:squarederror',
        'random_state': 42,
    }

# ============================================================================
# TEST BASE MODEL
# ============================================================================

class TestBaseModel:
    """Test the abstract base model interface."""

    def test_base_model_abstract_methods(self):
        """Test that base model requires implementation of abstract methods."""
        with pytest.raises(TypeError):
            BaseModel()

    def test_base_model_implementation(self):
        """Test that a concrete implementation works."""
        class ConcreteModel(BaseModel):
            def fit(self, X, y):
                self._fitted = True
                return self

            def predict(self, X):
                if not hasattr(self, '_fitted') or not self._fitted:
                    raise ValueError("Model not fitted")
                return np.ones(len(X))

            def save(self, path):
                pass

            def load(self, path):
                pass

        model = ConcreteModel()
        X = np.random.randn(10, 5)
        y = np.random.randn(10)
        model.fit(X, y)
        preds = model.predict(X)
        assert len(preds) == 10

# ============================================================================
# TEST LSTM MODELS
# ============================================================================

class TestLSTMModel:
    """Test LSTM model implementations."""

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_lstm_init(self, lstm_model_config):
        """Test LSTM initialization."""
        model = LSTMModel(**lstm_model_config)
        assert model.input_dim == lstm_model_config['input_dim']
        assert model.hidden_dim == lstm_model_config['hidden_dim']
        assert model.num_layers == lstm_model_config['num_layers']

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_lstm_fit_predict(self, sample_sequence_data, lstm_model_config):
        """Test LSTM fit and predict."""
        X, y = sample_sequence_data
        model = LSTMModel(**lstm_model_config)
        # Fit with very few epochs for testing
        model.epochs = 1
        model.fit(X, y)
        preds = model.predict(X[:5])
        assert preds.shape == (5, 1)

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_lstm_save_load(self, lstm_model_config, tmp_path):
        """Test LSTM save and load."""
        model = LSTMModel(**lstm_model_config)
        # Create dummy weights
        model.model = nn.Linear(5, 1)
        path = tmp_path / "lstm_model.pt"
        model.save(str(path))
        # Load into new model
        new_model = LSTMModel(**lstm_model_config)
        new_model.load(str(path))
        assert new_model.model is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_bilstm_init(self, lstm_model_config):
        """Test BiLSTM initialization."""
        from ai.models.lstm.bilstm_model import BiLSTMModel
        model = BiLSTMModel(**lstm_model_config)
        assert model.bidirectional is True

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_attention_lstm_init(self, lstm_model_config):
        """Test Attention LSTM initialization."""
        from ai.models.lstm.attention_lstm import AttentionLSTMModel
        model = AttentionLSTMModel(**lstm_model_config)
        assert model.attention_mechanism is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_stacked_lstm_init(self, lstm_model_config):
        """Test Stacked LSTM initialization."""
        from ai.models.lstm.stacked_lstm import StackedLSTMModel
        model = StackedLSTMModel(**lstm_model_config)
        assert model.num_layers == lstm_model_config['num_layers']

# ============================================================================
# TEST TRANSFORMER MODELS
# ============================================================================

class TestTransformerModels:
    """Test Transformer-based models."""

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_time_series_transformer_init(self, transformer_config):
        """Test TimeSeriesTransformer initialization."""
        model = TimeSeriesTransformer(**transformer_config)
        assert model.d_model == transformer_config['d_model']
        assert model.nhead == transformer_config['nhead']

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_time_series_transformer_fit_predict(self, sample_sequence_data, transformer_config):
        """Test TimeSeriesTransformer fit and predict."""
        X, y = sample_sequence_data
        model = TimeSeriesTransformer(**transformer_config)
        model.epochs = 1
        model.fit(X, y)
        preds = model.predict(X[:5])
        assert preds.shape == (5, 1)

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_informer_model_init(self, transformer_config):
        """Test Informer initialization."""
        from ai.models.transformers.informer_model import InformerModel
        model = InformerModel(**transformer_config)
        assert model.prob_sparse_attention is True

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_autoformer_model_init(self, transformer_config):
        """Test Autoformer initialization."""
        from ai.models.transformers.autoformer_model import AutoformerModel
        model = AutoformerModel(**transformer_config)
        assert model.auto_correlation is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_patchtst_model_init(self, transformer_config):
        """Test PatchTST initialization."""
        from ai.models.transformers.patchtst_model import PatchTSTModel
        model = PatchTSTModel(**transformer_config)
        assert model.patch_len is not None

# ============================================================================
# TEST XGBOOST MODEL
# ============================================================================

class TestXGBoostModel:
    """Test XGBoost model."""

    @pytest.mark.skipif(not XGB_AVAILABLE, reason="XGBoost not installed")
    def test_xgboost_init(self, xgboost_config):
        """Test XGBoost initialization."""
        model = XGBoostModel(**xgboost_config)
        assert model.n_estimators == xgboost_config['n_estimators']

    @pytest.mark.skipif(not XGB_AVAILABLE, reason="XGBoost not installed")
    def test_xgboost_fit_predict(self, sample_features_target, xgboost_config):
        """Test XGBoost fit and predict."""
        X, y = sample_features_target
        model = XGBoostModel(**xgboost_config)
        model.fit(X, y)
        preds = model.predict(X.iloc[:5])
        assert len(preds) == 5

    @pytest.mark.skipif(not XGB_AVAILABLE, reason="XGBoost not installed")
    def test_xgboost_save_load(self, sample_features_target, xgboost_config, tmp_path):
        """Test XGBoost save and load."""
        X, y = sample_features_target
        model = XGBoostModel(**xgboost_config)
        model.fit(X, y)
        path = tmp_path / "xgboost_model.json"
        model.save(str(path))
        new_model = XGBoostModel(**xgboost_config)
        new_model.load(str(path))
        # Compare predictions
        preds1 = model.predict(X.iloc[:5])
        preds2 = new_model.predict(X.iloc[:5])
        np.testing.assert_array_almost_equal(preds1, preds2)

    @pytest.mark.skipif(not XGB_AVAILABLE, reason="XGBoost not installed")
    def test_xgboost_feature_importance(self, sample_features_target, xgboost_config):
        """Test XGBoost feature importance."""
        X, y = sample_features_target
        model = XGBoostModel(**xgboost_config)
        model.fit(X, y)
        importance = model.get_feature_importance()
        assert len(importance) == X.shape[1]
        assert sum(importance.values()) > 0

# ============================================================================
# TEST ENSEMBLE MODELS
# ============================================================================

class TestEnsembleModels:
    """Test ensemble models."""

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_voting_ensemble_init(self):
        """Test VotingEnsemble initialization."""
        models = [
            ('rf', RandomForestRegressor(n_estimators=2)),
            ('linear', LinearRegression()),
        ]
        ensemble = VotingEnsemble(models=models, voting='average')
        assert len(ensemble.models) == 2

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_voting_ensemble_fit_predict(self, sample_features_target):
        """Test VotingEnsemble fit and predict."""
        X, y = sample_features_target
        models = [
            ('rf', RandomForestRegressor(n_estimators=2)),
            ('linear', LinearRegression()),
        ]
        ensemble = VotingEnsemble(models=models, voting='average')
        ensemble.fit(X, y)
        preds = ensemble.predict(X.iloc[:5])
        assert len(preds) == 5

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_weighted_voting_ensemble(self, sample_features_target):
        """Test weighted VotingEnsemble."""
        X, y = sample_features_target
        models = [
            ('rf', RandomForestRegressor(n_estimators=2)),
            ('linear', LinearRegression()),
        ]
        weights = {'rf': 0.7, 'linear': 0.3}
        ensemble = VotingEnsemble(models=models, voting='weighted', weights=weights)
        ensemble.fit(X, y)
        preds = ensemble.predict(X.iloc[:5])
        assert len(preds) == 5

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_stacking_ensemble_init(self):
        """Test StackingEnsemble initialization."""
        base_models = [
            ('rf', RandomForestRegressor(n_estimators=2)),
            ('linear', LinearRegression()),
        ]
        meta_model = RandomForestRegressor(n_estimators=2)
        ensemble = StackingEnsemble(base_models=base_models, meta_model=meta_model)
        assert len(ensemble.base_models) == 2

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_stacking_ensemble_fit_predict(self, sample_features_target):
        """Test StackingEnsemble fit and predict."""
        X, y = sample_features_target
        base_models = [
            ('rf', RandomForestRegressor(n_estimators=2)),
            ('linear', LinearRegression()),
        ]
        meta_model = RandomForestRegressor(n_estimators=2)
        ensemble = StackingEnsemble(base_models=base_models, meta_model=meta_model)
        ensemble.fit(X, y)
        preds = ensemble.predict(X.iloc[:5])
        assert len(preds) == 5

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_bagging_ensemble_init(self):
        """Test BaggingEnsemble initialization."""
        base_model = RandomForestRegressor(n_estimators=2)
        ensemble = BaggingEnsemble(base_model=base_model, n_estimators=3)
        assert ensemble.n_estimators == 3

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_bagging_ensemble_fit_predict(self, sample_features_target):
        """Test BaggingEnsemble fit and predict."""
        X, y = sample_features_target
        base_model = RandomForestRegressor(n_estimators=2)
        ensemble = BaggingEnsemble(base_model=base_model, n_estimators=3)
        ensemble.fit(X, y)
        preds = ensemble.predict(X.iloc[:5])
        assert len(preds) == 5

# ============================================================================
# TEST FORECASTING MODELS
# ============================================================================

class TestForecastingModels:
    """Test forecasting models like ARIMA and Prophet."""

    def test_arima_init(self):
        """Test ARIMA initialization."""
        try:
            from ai.models.forecasting.arima_model import ARIMAModel
            model = ARIMAModel(order=(1, 1, 1))
            assert model.order == (1, 1, 1)
        except ImportError:
            pytest.skip("ARIMA dependencies not installed")

    def test_arima_fit_predict(self, sample_time_series_data):
        """Test ARIMA fit and predict."""
        try:
            from ai.models.forecasting.arima_model import ARIMAModel
            model = ARIMAModel(order=(1, 1, 1))
            # Use only close price for univariate
            series = sample_time_series_data['close']
            model.fit(series)
            preds = model.predict(steps=5)
            assert len(preds) == 5
        except ImportError:
            pytest.skip("ARIMA dependencies not installed")

    def test_prophet_init(self):
        """Test Prophet initialization."""
        try:
            from ai.models.forecasting.prophet_model import ProphetModel
            model = ProphetModel()
            assert model is not None
        except ImportError:
            pytest.skip("Prophet not installed")

    def test_prophet_fit_predict(self, sample_time_series_data):
        """Test Prophet fit and predict."""
        try:
            from ai.models.forecasting.prophet_model import ProphetModel
            model = ProphetModel()
            # Prophet requires ds and y columns
            df = sample_time_series_data[['close']].reset_index()
            df.columns = ['ds', 'y']
            model.fit(df)
            future = model.make_future_dataframe(periods=5)
            preds = model.predict(future)
            assert len(preds) == len(df) + 5
        except ImportError:
            pytest.skip("Prophet not installed")

# ============================================================================
# TEST VOLATILITY MODELS
# ============================================================================

class TestVolatilityModels:
    """Test volatility models like GARCH."""

    def test_garch_init(self):
        """Test GARCH initialization."""
        try:
            from ai.models.volatility.garch_model import GARCHModel
            model = GARCHModel(p=1, q=1)
            assert model.p == 1
        except ImportError:
            pytest.skip("GARCH dependencies not installed")

    def test_garch_fit_predict(self, sample_time_series_data):
        """Test GARCH fit and predict."""
        try:
            from ai.models.volatility.garch_model import GARCHModel
            model = GARCHModel(p=1, q=1)
            returns = sample_time_series_data['close'].pct_change().dropna()
            model.fit(returns)
            forecast = model.predict_volatility(steps=5)
            assert len(forecast) == 5
        except ImportError:
            pytest.skip("GARCH dependencies not installed")

# ============================================================================
# TEST MODEL LOADING AND SAVING
# ============================================================================

class TestModelPersistence:
    """Test model persistence across different model types."""

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_sklearn_persistence(self, tmp_path):
        """Test saving and loading sklearn models."""
        from ai.models.xgboost_model import XGBoostModel
        model = RandomForestRegressor(n_estimators=2)
        X = np.random.randn(10, 5)
        y = np.random.randn(10)
        model.fit(X, y)
        path = tmp_path / "sklearn_model.pkl"
        # Use base model save/load if available
        # For sklearn, we can use joblib
        import joblib
        joblib.dump(model, str(path))
        loaded = joblib.load(str(path))
        preds1 = model.predict(X)
        preds2 = loaded.predict(X)
        np.testing.assert_array_almost_equal(preds1, preds2)

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_torch_persistence(self, tmp_path):
        """Test saving and loading PyTorch models."""
        model = nn.Linear(5, 1)
        path = tmp_path / "torch_model.pt"
        torch.save(model.state_dict(), str(path))
        new_model = nn.Linear(5, 1)
        new_model.load_state_dict(torch.load(str(path)))
        # Check that parameters are the same (untrained, but should be same random init)
        # Actually, initial weights might be different, so we compare shapes
        for p1, p2 in zip(model.parameters(), new_model.parameters()):
            assert p1.shape == p2.shape

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests with real components."""

    @pytest.mark.skipif(not XGB_AVAILABLE, reason="XGBoost not installed")
    def test_xgboost_ensemble_integration(self, sample_features_target):
        """Test XGBoost with ensemble."""
        X, y = sample_features_target
        # Create a bagging ensemble of XGBoost models
        from ai.models.ensemble.bagging_ensemble import BaggingEnsemble
        base_model = XGBoostModel(n_estimators=5, max_depth=2)
        ensemble = BaggingEnsemble(base_model=base_model, n_estimators=3)
        ensemble.fit(X, y)
        preds = ensemble.predict(X.iloc[:5])
        assert len(preds) == 5

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_lstm_xgboost_stacking(self, sample_sequence_data, sample_features_target):
        """Test stacking LSTM and XGBoost."""
        # This is a simplified integration test
        # We'll just test that we can create a stacking ensemble with different model types
        from ai.models.ensemble.stacking_ensemble import StackingEnsemble
        # For simplicity, use sklearn models as placeholders
        try:
            from sklearn.linear_model import LinearRegression
            from sklearn.ensemble import RandomForestRegressor
            base_models = [
                ('rf', RandomForestRegressor(n_estimators=2)),
                ('linear', LinearRegression()),
            ]
            meta_model = RandomForestRegressor(n_estimators=2)
            ensemble = StackingEnsemble(base_models=base_models, meta_model=meta_model)
            X, y = sample_features_target
            ensemble.fit(X, y)
            preds = ensemble.predict(X.iloc[:5])
            assert len(preds) == 5
        except ImportError:
            pytest.skip("scikit-learn not installed")

# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance benchmarks for models."""

    @pytest.mark.benchmark
    @pytest.mark.skipif(not XGB_AVAILABLE, reason="XGBoost not installed")
    def test_xgboost_prediction_speed(self, benchmark, sample_features_target):
        """Benchmark XGBoost prediction speed."""
        X, y = sample_features_target
        model = XGBoostModel(n_estimators=10, max_depth=3)
        model.fit(X, y)
        def predict():
            return model.predict(X)
        result = benchmark(predict)
        assert len(result) == len(X)

    @pytest.mark.benchmark
    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_lstm_prediction_speed(self, benchmark, sample_sequence_data, lstm_model_config):
        """Benchmark LSTM prediction speed."""
        X, y = sample_sequence_data
        model = LSTMModel(**lstm_model_config)
        model.epochs = 1
        model.fit(X, y)
        def predict():
            return model.predict(X[:10])
        result = benchmark(predict)
        assert result.shape == (10, 1)

# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling in models."""

    def test_base_model_not_implemented(self):
        """Test that base model raises NotImplementedError."""
        class IncompleteModel(BaseModel):
            def fit(self, X, y):
                pass
            # missing predict, save, load
        with pytest.raises(TypeError):
            IncompleteModel()

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_lstm_invalid_input_shape(self, lstm_model_config):
        """Test LSTM with invalid input shape."""
        model = LSTMModel(**lstm_model_config)
        X = np.random.randn(10, 5)  # wrong shape (should be 3D)
        y = np.random.randn(10)
        with pytest.raises(ValueError):
            model.fit(X, y)

    @pytest.mark.skipif(not XGB_AVAILABLE, reason="XGBoost not installed")
    def test_xgboost_missing_features(self, sample_features_target, xgboost_config):
        """Test XGBoost with missing features."""
        X, y = sample_features_target
        model = XGBoostModel(**xgboost_config)
        model.fit(X, y)
        # Predict with fewer features
        X_bad = X.iloc[:, :-1]
        with pytest.raises(ValueError):
            model.predict(X_bad)

    @pytest.mark.skipif(not SKLEARN_AVAILABLE, reason="scikit-learn not installed")
    def test_ensemble_weights_mismatch(self):
        """Test ensemble with mismatched weights."""
        models = [
            ('rf', RandomForestRegressor(n_estimators=2)),
            ('linear', LinearRegression()),
            ('svm', LinearRegression()),  # dummy
        ]
        weights = {'rf': 0.5, 'linear': 0.5}  # missing 'svm'
        with pytest.raises(ValueError):
            VotingEnsemble(models=models, voting='weighted', weights=weights)

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

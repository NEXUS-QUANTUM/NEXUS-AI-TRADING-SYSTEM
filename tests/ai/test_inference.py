"""
NEXUS AI TRADING SYSTEM
AI Inference Tests

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: tests/ai/test_inference.py
Description: Comprehensive unit and integration tests for AI inference services,
             including model loading, prediction pipelines, and ensemble methods.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, Mock

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

from ai.prediction.prediction_pipeline import PredictionPipeline
from ai.prediction.ensemble_predictor import EnsemblePredictor
from ai.prediction.market_prediction import MarketPredictor
from ai.prediction.price_prediction import PricePredictor
from ai.prediction.trend_prediction import TrendPredictor
from ai.prediction.volatility_prediction import VolatilityPredictor
from ai.prediction.sentiment_prediction import SentimentPredictor
from ai.models.base_model import BaseModel
from ai.models.ensemble.voting_ensemble import VotingEnsemble
from ai.models.ensemble.stacking_ensemble import StackingEnsemble
from ai.models.ensemble.bagging_ensemble import BaggingEnsemble
from ai.models.lstm.lstm_model import LSTMModel
from ai.models.transformers.time_series_transformer import TimeSeriesTransformer
from ai.models.xgboost_model import XGBoostModel
from ai.datasets.data_loader import DataLoader
from ai.datasets.feature_engineering import FeatureEngineer
from ai.inference.inference_engine import InferenceEngine

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    data = {
        'open': np.random.normal(100, 5, 100),
        'high': np.random.normal(102, 5, 100),
        'low': np.random.normal(98, 5, 100),
        'close': np.random.normal(100, 5, 100),
        'volume': np.random.randint(1000, 10000, 100),
    }
    df = pd.DataFrame(data, index=dates)
    # Ensure high >= low, etc.
    df['high'] = df[['open', 'close']].max(axis=1) + abs(np.random.normal(0, 1, 100))
    df['low'] = df[['open', 'close']].min(axis=1) - abs(np.random.normal(0, 1, 100))
    return df

@pytest.fixture
def sample_features(sample_market_data):
    """Generate features from sample data."""
    engineer = FeatureEngineer()
    features = engineer.create_features(sample_market_data)
    return features

@pytest.fixture
def sample_labels(sample_market_data):
    """Generate labels for testing."""
    # Use future returns as labels
    returns = sample_market_data['close'].pct_change().shift(-1)
    labels = returns.dropna()
    return labels

@pytest.fixture
def mock_model():
    """Create a mock model for testing."""
    model = MagicMock(spec=BaseModel)
    model.predict.return_value = np.array([0.01, 0.02, -0.01])
    model.predict_proba.return_value = np.array([[0.6, 0.4], [0.3, 0.7], [0.5, 0.5]])
    model.load.return_value = None
    model.save.return_value = None
    return model

@pytest.fixture
def mock_models():
    """Create multiple mock models for ensemble testing."""
    models = []
    for i in range(3):
        m = MagicMock(spec=BaseModel)
        m.predict.return_value = np.array([0.01 + i*0.005, 0.02 + i*0.005, -0.01 + i*0.005])
        m.predict_proba.return_value = np.array([[0.6, 0.4], [0.3, 0.7], [0.5, 0.5]])
        m.load.return_value = None
        m.save.return_value = None
        models.append(m)
    return models

@pytest.fixture
def inference_engine(sample_market_data):
    """Create an inference engine with mock components."""
    engine = InferenceEngine(
        config={'model_dir': '/tmp/models', 'cache_enabled': True},
        data_loader=MagicMock(),
        feature_engineer=MagicMock(),
        ensemble_predictor=MagicMock(),
    )
    return engine

@pytest_asyncio.fixture
async def async_inference_engine():
    """Async inference engine for async tests."""
    engine = InferenceEngine(
        config={'model_dir': '/tmp/models', 'cache_enabled': True},
        data_loader=AsyncMock(),
        feature_engineer=AsyncMock(),
        ensemble_predictor=AsyncMock(),
    )
    yield engine
    await engine.close()

# ============================================================================
# TEST PREDICTION PIPELINE
# ============================================================================

class TestPredictionPipeline:
    """Test the prediction pipeline."""

    def test_init(self):
        """Test initialization."""
        pipeline = PredictionPipeline(config={'max_workers': 2})
        assert pipeline is not None
        assert pipeline.config['max_workers'] == 2

    def test_preprocess_data(self, sample_market_data):
        """Test data preprocessing."""
        pipeline = PredictionPipeline()
        processed = pipeline._preprocess_data(sample_market_data)
        assert isinstance(processed, pd.DataFrame)
        assert not processed.isnull().any().any()

    @patch('ai.prediction.prediction_pipeline.load_model')
    def test_load_models(self, mock_load, sample_market_data):
        """Test loading models."""
        mock_load.return_value = MagicMock()
        pipeline = PredictionPipeline(config={'model_paths': ['model1.pkl', 'model2.pkl']})
        models = pipeline._load_models()
        assert len(models) == 2

    def test_run_pipeline_sync(self, sample_market_data, mock_models):
        """Test synchronous pipeline execution."""
        pipeline = PredictionPipeline()
        with patch.object(pipeline, '_load_models', return_value=mock_models):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_market_data):
                predictions = pipeline.run(sample_market_data)
                assert len(predictions) == 3  # 3 models

    @pytest.mark.asyncio
    async def test_run_pipeline_async(self, sample_market_data, mock_models):
        """Test asynchronous pipeline execution."""
        pipeline = PredictionPipeline()
        with patch.object(pipeline, '_load_models_async', return_value=mock_models):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_market_data):
                predictions = await pipeline.run_async(sample_market_data)
                assert len(predictions) == 3

    def test_error_handling(self, sample_market_data):
        """Test error handling in pipeline."""
        pipeline = PredictionPipeline()
        with patch.object(pipeline, '_load_models', side_effect=Exception("Model load failed")):
            with pytest.raises(Exception):
                pipeline.run(sample_market_data)

    def test_cache(self, sample_market_data):
        """Test caching of predictions."""
        pipeline = PredictionPipeline(config={'cache_enabled': True, 'cache_ttl': 60})
        # First run should compute
        with patch.object(pipeline, '_load_models', return_value=[MagicMock()]):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_market_data):
                result1 = pipeline.run(sample_market_data)
                result2 = pipeline.run(sample_market_data)  # Should use cache
                assert result1 == result2

# ============================================================================
# TEST ENSEMBLE PREDICTOR
# ============================================================================

class TestEnsemblePredictor:
    """Test ensemble predictor functionality."""

    def test_init(self):
        """Test initialization."""
        ensemble = EnsemblePredictor(config={'method': 'voting'})
        assert ensemble.method == 'voting'

    def test_voting_ensemble(self, mock_models, sample_features):
        """Test voting ensemble prediction."""
        ensemble = EnsemblePredictor(config={'method': 'voting'})
        predictions = ensemble.predict(mock_models, sample_features)
        assert len(predictions) == len(sample_features)

    def test_weighted_voting(self, mock_models, sample_features):
        """Test weighted voting ensemble."""
        weights = [0.5, 0.3, 0.2]
        ensemble = EnsemblePredictor(config={'method': 'weighted_voting', 'weights': weights})
        predictions = ensemble.predict(mock_models, sample_features)
        assert len(predictions) == len(sample_features)

    def test_averaging_ensemble(self, mock_models, sample_features):
        """Test averaging ensemble."""
        ensemble = EnsemblePredictor(config={'method': 'average'})
        predictions = ensemble.predict(mock_models, sample_features)
        assert len(predictions) == len(sample_features)

    def test_stacking_ensemble(self, mock_models, sample_features, sample_labels):
        """Test stacking ensemble."""
        # Create a stacking ensemble with meta-model
        meta_model = LinearRegression()
        ensemble = EnsemblePredictor(
            config={'method': 'stacking', 'meta_model': meta_model}
        )
        # Fit meta-model
        ensemble.fit(mock_models, sample_features.iloc[:50], sample_labels.iloc[:50])
        predictions = ensemble.predict(mock_models, sample_features.iloc[50:])
        assert len(predictions) == len(sample_features.iloc[50:])

    def test_ensemble_with_weights_validation(self, mock_models, sample_features):
        """Test validation of weights for weighted voting."""
        ensemble = EnsemblePredictor(config={'method': 'weighted_voting', 'weights': [0.5, 0.5]})
        # Should work with 2 models
        predictions = ensemble.predict(mock_models[:2], sample_features)
        assert len(predictions) == len(sample_features)
        # Should raise error if weights count doesn't match models
        with pytest.raises(ValueError):
            ensemble.predict(mock_models, sample_features)

    def test_ensemble_confidence(self, mock_models, sample_features):
        """Test confidence calculation for ensemble predictions."""
        ensemble = EnsemblePredictor(config={'method': 'average'})
        predictions, confidence = ensemble.predict_with_confidence(mock_models, sample_features)
        assert len(predictions) == len(sample_features)
        assert len(confidence) == len(sample_features)
        assert all(0 <= c <= 1 for c in confidence)

# ============================================================================
# TEST MARKET PREDICTOR
# ============================================================================

class TestMarketPredictor:
    """Test market predictor."""

    def test_init(self):
        """Test initialization."""
        predictor = MarketPredictor(config={'lookback': 30})
        assert predictor.lookback == 30

    def test_predict_direction(self, sample_features):
        """Test direction prediction."""
        predictor = MarketPredictor()
        with patch.object(predictor, '_load_model', return_value=MagicMock()):
            direction = predictor.predict_direction(sample_features)
            assert direction in ['up', 'down', 'neutral']

    def test_predict_probability(self, sample_features):
        """Test probability prediction."""
        predictor = MarketPredictor()
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.7, 0.3], [0.4, 0.6]])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            probs = predictor.predict_probability(sample_features.iloc[:2])
            assert probs.shape == (2, 2)
            assert np.allclose(probs.sum(axis=1), 1.0)

    def test_predict_with_confidence(self, sample_features):
        """Test prediction with confidence."""
        predictor = MarketPredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([1, 0, 1])
        mock_model.predict_proba.return_value = np.array([[0.9, 0.1], [0.3, 0.7], [0.8, 0.2]])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            preds, confs = predictor.predict_with_confidence(sample_features.iloc[:3])
            assert len(preds) == 3
            assert len(confs) == 3
            assert all(0 <= c <= 1 for c in confs)

# ============================================================================
# TEST PRICE PREDICTOR
# ============================================================================

class TestPricePredictor:
    """Test price predictor."""

    def test_init(self):
        """Test initialization."""
        predictor = PricePredictor(config={'horizon': 5})
        assert predictor.horizon == 5

    def test_predict_price(self, sample_features):
        """Test price prediction."""
        predictor = PricePredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([101.0, 102.5, 103.2])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            prices = predictor.predict_price(sample_features.iloc[:3])
            assert len(prices) == 3
            assert all(isinstance(p, float) for p in prices)

    def test_predict_price_range(self, sample_features):
        """Test price range prediction."""
        predictor = PricePredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([100, 101, 102])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            lower, upper = predictor.predict_price_range(sample_features.iloc[:3], confidence=0.95)
            assert len(lower) == 3
            assert len(upper) == 3
            assert all(l < u for l, u in zip(lower, upper))

    def test_predict_returns(self, sample_features):
        """Test return prediction."""
        predictor = PricePredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.01, -0.02, 0.005])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            returns = predictor.predict_returns(sample_features.iloc[:3])
            assert len(returns) == 3

# ============================================================================
# TEST VOLATILITY PREDICTOR
# ============================================================================

class TestVolatilityPredictor:
    """Test volatility predictor."""

    def test_init(self):
        """Test initialization."""
        predictor = VolatilityPredictor(config={'horizon': 10})
        assert predictor.horizon == 10

    def test_predict_volatility(self, sample_features):
        """Test volatility prediction."""
        predictor = VolatilityPredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.02, 0.03, 0.015])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            vols = predictor.predict_volatility(sample_features.iloc[:3])
            assert len(vols) == 3
            assert all(v > 0 for v in vols)

    def test_predict_volatility_interval(self, sample_features):
        """Test volatility interval prediction."""
        predictor = VolatilityPredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.02, 0.03])
        mock_model.predict_std.return_value = np.array([0.005, 0.008])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            lower, upper = predictor.predict_volatility_interval(sample_features.iloc[:2])
            assert len(lower) == 2
            assert len(upper) == 2

# ============================================================================
# TEST SENTIMENT PREDICTOR
# ============================================================================

class TestSentimentPredictor:
    """Test sentiment predictor."""

    def test_init(self):
        """Test initialization."""
        predictor = SentimentPredictor(config={'model_type': 'finbert'})
        assert predictor.model_type == 'finbert'

    def test_predict_sentiment(self, sample_features):
        """Test sentiment prediction."""
        predictor = SentimentPredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.8, 0.2, 0.6])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            scores = predictor.predict_sentiment(["text1", "text2", "text3"])
            assert len(scores) == 3
            assert all(0 <= s <= 1 for s in scores)

    def test_predict_sentiment_label(self, sample_features):
        """Test sentiment label prediction."""
        predictor = SentimentPredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([1, 0, 2])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            labels = predictor.predict_sentiment_label(["text1", "text2", "text3"])
            assert len(labels) == 3
            assert all(l in ['positive', 'negative', 'neutral'] for l in labels)

# ============================================================================
# TEST TREND PREDICTOR
# ============================================================================

class TestTrendPredictor:
    """Test trend predictor."""

    def test_init(self):
        """Test initialization."""
        predictor = TrendPredictor(config={'horizon': 5})
        assert predictor.horizon == 5

    def test_predict_trend(self, sample_features):
        """Test trend prediction."""
        predictor = TrendPredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.5, -0.3, 0.1])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            trends = predictor.predict_trend(sample_features.iloc[:3])
            assert len(trends) == 3
            assert all(isinstance(t, float) for t in trends)

    def test_predict_trend_strength(self, sample_features):
        """Test trend strength prediction."""
        predictor = TrendPredictor()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.8, 0.2, 0.5])
        with patch.object(predictor, '_load_model', return_value=mock_model):
            strengths = predictor.predict_trend_strength(sample_features.iloc[:3])
            assert len(strengths) == 3
            assert all(0 <= s <= 1 for s in strengths)

# ============================================================================
# TEST INFERENCE ENGINE
# ============================================================================

class TestInferenceEngine:
    """Test the main inference engine."""

    @pytest.mark.asyncio
    async def test_predict_async(self, async_inference_engine, sample_features):
        """Test async prediction."""
        mock_predictor = AsyncMock()
        mock_predictor.predict.return_value = np.array([0.1, 0.2, -0.1])
        async_inference_engine.predictor = mock_predictor
        result = await async_inference_engine.predict(sample_features)
        assert result is not None

    def test_predict_sync(self, inference_engine, sample_features):
        """Test sync prediction."""
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = np.array([0.1, 0.2, -0.1])
        inference_engine.predictor = mock_predictor
        result = inference_engine.predict(sample_features)
        assert result is not None

    @patch('ai.inference.inference_engine.logger')
    def test_error_logging(self, mock_logger, inference_engine, sample_features):
        """Test error logging."""
        mock_predictor = MagicMock()
        mock_predictor.predict.side_effect = Exception("Test error")
        inference_engine.predictor = mock_predictor
        with pytest.raises(Exception):
            inference_engine.predict(sample_features)
        mock_logger.error.assert_called()

    def test_ensemble_prediction(self, inference_engine, sample_features, mock_models):
        """Test ensemble prediction in engine."""
        inference_engine.ensemble_predictor = MagicMock()
        inference_engine.ensemble_predictor.predict.return_value = np.array([0.1, 0.2])
        inference_engine.models = mock_models
        result = inference_engine.predict_ensemble(sample_features)
        assert result is not None

    def test_model_loading(self, inference_engine):
        """Test model loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy model file
            model_path = os.path.join(tmpdir, 'model.pkl')
            import pickle
            with open(model_path, 'wb') as f:
                pickle.dump({'dummy': 'model'}, f)
            inference_engine.config['model_dir'] = tmpdir
            with patch.object(inference_engine, '_load_model', return_value=MagicMock()):
                model = inference_engine.load_model('model.pkl')
                assert model is not None

    def test_preprocessing_hook(self, inference_engine, sample_features):
        """Test preprocessing hook."""
        def preprocess_hook(data):
            return data.dropna()
        inference_engine.add_preprocessing_hook(preprocess_hook)
        processed = inference_engine._apply_preprocessing(sample_features)
        assert len(processed) <= len(sample_features)

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for inference pipeline with real components."""

    @pytest.fixture
    def real_pipeline(self):
        """Create a real prediction pipeline with mock models."""
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.preprocessing import StandardScaler
        
        models = []
        for _ in range(3):
            model = RandomForestRegressor(n_estimators=5)
            models.append(model)
        
        pipeline = PredictionPipeline(config={'models': models})
        return pipeline

    def test_end_to_end_prediction(self, real_pipeline, sample_market_data):
        """Test end-to-end prediction."""
        # Preprocess
        pipeline = real_pipeline
        processed = pipeline._preprocess_data(sample_market_data)
        # Fit models on some data
        X = processed.iloc[:-10]
        y = sample_market_data['close'].shift(-1).iloc[:-10]
        for model in pipeline.models:
            model.fit(X, y)
        # Run prediction
        predictions = pipeline.run(sample_market_data.iloc[-10:])
        assert len(predictions) == len(pipeline.models)

    def test_ensemble_with_real_models(self, sample_features, sample_labels):
        """Test ensemble with real sklearn models."""
        models = [
            RandomForestRegressor(n_estimators=5),
            LinearRegression(),
            RandomForestRegressor(n_estimators=3),
        ]
        # Fit models
        for model in models:
            model.fit(sample_features.iloc[:50], sample_labels.iloc[:50])
        
        ensemble = EnsemblePredictor(config={'method': 'average'})
        preds = ensemble.predict(models, sample_features.iloc[50:])
        assert len(preds) == len(sample_features.iloc[50:])

    def test_stacking_with_real_models(self, sample_features, sample_labels):
        """Test stacking with real models."""
        base_models = [
            RandomForestRegressor(n_estimators=3),
            LinearRegression(),
        ]
        meta_model = RandomForestRegressor(n_estimators=3)
        ensemble = EnsemblePredictor(config={'method': 'stacking', 'meta_model': meta_model})
        # Fit on first half
        ensemble.fit(base_models, sample_features.iloc[:50], sample_labels.iloc[:50])
        preds = ensemble.predict(base_models, sample_features.iloc[50:])
        assert len(preds) == len(sample_features.iloc[50:])

    @pytest.mark.slow
    def test_lstm_integration(self, sample_market_data):
        """Test LSTM model integration (requires tensorflow)."""
        try:
            from ai.models.lstm.lstm_model import LSTMModel
            model = LSTMModel(input_shape=(10, 5))
            X = np.random.randn(20, 10, 5)
            y = np.random.randn(20)
            model.fit(X, y, epochs=1, batch_size=4)
            preds = model.predict(X[:5])
            assert preds.shape == (5,)
        except ImportError:
            pytest.skip("TensorFlow not installed")

# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance tests for inference."""

    @pytest.mark.benchmark
    def test_prediction_speed(self, benchmark, sample_features, mock_models):
        """Benchmark prediction speed."""
        ensemble = EnsemblePredictor(config={'method': 'average'})
        def run():
            return ensemble.predict(mock_models, sample_features)
        result = benchmark(run)
        assert result is not None

    @pytest.mark.benchmark
    def test_pipeline_throughput(self, benchmark, sample_market_data):
        """Benchmark pipeline throughput."""
        pipeline = PredictionPipeline(config={'models': [MagicMock() for _ in range(5)]})
        def run():
            return pipeline.run(sample_market_data)
        result = benchmark(run)
        assert result is not None

# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling in inference components."""

    def test_missing_model(self):
        """Test handling of missing model."""
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=None):
            with pytest.raises(ValueError):
                predictor.predict_price(pd.DataFrame())

    def test_invalid_data(self):
        """Test handling of invalid data."""
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=MagicMock()):
            with pytest.raises(ValueError):
                predictor.predict_price(None)

    def test_model_prediction_failure(self, sample_features):
        """Test handling of model prediction failure."""
        predictor = PricePredictor()
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Prediction failed")
        with patch.object(predictor, '_load_model', return_value=mock_model):
            with pytest.raises(RuntimeError):
                predictor.predict_price(sample_features)

    def test_ensemble_mismatch(self, mock_models, sample_features):
        """Test ensemble with mismatched model count."""
        ensemble = EnsemblePredictor(config={'method': 'average'})
        # Should work with any number of models
        preds = ensemble.predict(mock_models[:1], sample_features)
        assert len(preds) == len(sample_features)

# ============================================================================
# DATA VALIDATION TESTS
# ============================================================================

class TestDataValidation:
    """Test input data validation."""

    def test_validate_features(self, sample_features):
        """Test feature validation."""
        from ai.datasets.data_validator import DataValidator
        validator = DataValidator()
        is_valid = validator.validate_features(sample_features)
        assert is_valid is True

    def test_missing_columns(self, sample_features):
        """Test missing column detection."""
        from ai.datasets.data_validator import DataValidator
        validator = DataValidator(required_columns=['open', 'high', 'low', 'close'])
        missing = sample_features.drop(columns=['open'])
        is_valid = validator.validate_features(missing)
        assert is_valid is False

    def test_outlier_detection(self, sample_features):
        """Test outlier detection."""
        from ai.datasets.data_validator import DataValidator
        validator = DataValidator()
        outliers = validator.detect_outliers(sample_features)
        assert 'outliers' in outliers

# ============================================================================
# CUSTOM MODEL TEST
# ============================================================================

class TestCustomModel:
    """Test integration with custom models."""

    def test_custom_model_prediction(self, sample_features):
        """Test custom model class."""

        class MyCustomModel:
            def predict(self, X):
                return np.ones(len(X))

        model = MyCustomModel()
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=model):
            preds = predictor.predict_price(sample_features)
            assert np.all(preds == 1.0)

    def test_model_without_predict_method(self):
        """Test model that doesn't implement predict."""
        class BadModel:
            pass

        model = BadModel()
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=model):
            with pytest.raises(AttributeError):
                predictor.predict_price(pd.DataFrame())

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

"""
NEXUS AI TRADING SYSTEM
AI Predictions Tests

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: tests/ai/test_predictions.py
Description: Comprehensive unit and integration tests for AI prediction services
             including market prediction, price prediction, trend prediction,
             volatility prediction, sentiment prediction, and prediction pipelines.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio

from ai.prediction.market_prediction import MarketPredictor
from ai.prediction.price_prediction import PricePredictor
from ai.prediction.trend_prediction import TrendPredictor
from ai.prediction.volatility_prediction import VolatilityPredictor
from ai.prediction.sentiment_prediction import SentimentPredictor
from ai.prediction.prediction_pipeline import PredictionPipeline
from ai.prediction.ensemble_predictor import EnsemblePredictor
from ai.prediction.prediction_cache import PredictionCache
from ai.models.base_model import BaseModel

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_market_data():
    """Create sample market data for prediction tests."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    data = {
        'open': np.random.normal(100, 5, 100).cumsum() + 100,
        'high': np.random.normal(102, 5, 100).cumsum() + 102,
        'low': np.random.normal(98, 5, 100).cumsum() + 98,
        'close': np.random.normal(100, 5, 100).cumsum() + 100,
        'volume': np.random.randint(1000, 10000, 100),
    }
    df = pd.DataFrame(data, index=dates)
    # Ensure high >= low etc.
    df['high'] = df[['open', 'close']].max(axis=1) + abs(np.random.normal(0, 1, 100))
    df['low'] = df[['open', 'close']].min(axis=1) - abs(np.random.normal(0, 1, 100))
    return df

@pytest.fixture
def sample_features(sample_market_data):
    """Create features from market data."""
    df = sample_market_data.copy()
    # Simple lag features
    for lag in [1, 2, 3, 5, 10]:
        df[f'close_lag_{lag}'] = df['close'].shift(lag)
    df = df.dropna()
    return df

@pytest.fixture
def sample_sentiment_texts():
    """Sample text data for sentiment prediction."""
    return [
        "Bitcoin surges to new all-time high as institutional demand grows",
        "Market correction expected as inflation fears rise",
        "Ethereum upgrade successfully deployed, network fees drop",
        "Regulatory uncertainty weighs on crypto markets",
        "Strong earnings report boosts tech stocks",
    ]

@pytest.fixture
def mock_model():
    """Create a mock model for prediction."""
    model = MagicMock(spec=BaseModel)
    model.predict.return_value = np.array([0.01, -0.02, 0.03])
    model.predict_proba.return_value = np.array([[0.6, 0.4], [0.3, 0.7], [0.5, 0.5]])
    model.predict_std.return_value = np.array([0.005, 0.008, 0.006])
    model.load.return_value = None
    return model

@pytest.fixture
def mock_ensemble_model():
    """Mock ensemble model for ensemble predictor."""
    model = MagicMock()
    model.predict.return_value = np.array([0.015, -0.015, 0.025])
    model.predict_proba.return_value = np.array([[0.7, 0.3], [0.4, 0.6], [0.6, 0.4]])
    return model

@pytest.fixture
def prediction_cache():
    """Create a prediction cache instance."""
    cache = PredictionCache(config={'ttl': 60, 'max_size': 100})
    return cache

# ============================================================================
# TEST MARKET PREDICTOR
# ============================================================================

class TestMarketPredictor:
    """Test market predictor functionality."""

    def test_init(self):
        """Test initialization."""
        predictor = MarketPredictor(config={'lookback': 30})
        assert predictor.lookback == 30

    def test_predict_direction(self, sample_features, mock_model):
        """Test market direction prediction."""
        predictor = MarketPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            direction = predictor.predict_direction(sample_features.iloc[:10])
            assert direction in ['up', 'down', 'neutral']

    def test_predict_direction_binary(self, sample_features, mock_model):
        """Test binary direction prediction."""
        predictor = MarketPredictor(config={'binary_output': True})
        with patch.object(predictor, '_load_model', return_value=mock_model):
            # Mock model predict returns probabilities
            direction = predictor.predict_direction(sample_features.iloc[:10])
            # Should be 'up' or 'down'
            assert direction in ['up', 'down']

    def test_predict_probability(self, sample_features, mock_model):
        """Test probability prediction."""
        predictor = MarketPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            probs = predictor.predict_probability(sample_features.iloc[:3])
            assert probs.shape == (3, 2)
            assert np.allclose(probs.sum(axis=1), 1.0)

    def test_predict_with_confidence(self, sample_features, mock_model):
        """Test prediction with confidence."""
        predictor = MarketPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            pred, conf = predictor.predict_with_confidence(sample_features.iloc[:3])
            assert len(pred) == 3
            assert len(conf) == 3
            assert all(0 <= c <= 1 for c in conf)

    def test_predict_with_historical_context(self, sample_features, mock_model):
        """Test prediction with historical context."""
        predictor = MarketPredictor(config={'use_historical_context': True})
        with patch.object(predictor, '_load_model', return_value=mock_model):
            result = predictor.predict_with_context(sample_features.iloc[:10])
            assert 'direction' in result
            assert 'confidence' in result
            assert 'probability' in result
            assert 'historical_accuracy' in result

# ============================================================================
# TEST PRICE PREDICTOR
# ============================================================================

class TestPricePredictor:
    """Test price predictor functionality."""

    def test_init(self):
        """Test initialization."""
        predictor = PricePredictor(config={'horizon': 5})
        assert predictor.horizon == 5

    def test_predict_price(self, sample_features, mock_model):
        """Test price prediction."""
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            prices = predictor.predict_price(sample_features.iloc[:5])
            assert len(prices) == 5
            assert all(isinstance(p, float) for p in prices)

    def test_predict_price_range(self, sample_features, mock_model):
        """Test price range prediction."""
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            lower, upper = predictor.predict_price_range(
                sample_features.iloc[:5],
                confidence=0.95
            )
            assert len(lower) == 5
            assert len(upper) == 5
            assert all(l < u for l, u in zip(lower, upper))

    def test_predict_returns(self, sample_features, mock_model):
        """Test return prediction."""
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            returns = predictor.predict_returns(sample_features.iloc[:5])
            assert len(returns) == 5

    def test_predict_price_with_noise(self, sample_features, mock_model):
        """Test price prediction with noise estimation."""
        predictor = PricePredictor(config={'estimate_noise': True})
        with patch.object(predictor, '_load_model', return_value=mock_model):
            result = predictor.predict_with_noise(sample_features.iloc[:5])
            assert 'price' in result
            assert 'std' in result
            assert 'lower' in result
            assert 'upper' in result
            assert len(result['price']) == 5

# ============================================================================
# TEST TREND PREDICTOR
# ============================================================================

class TestTrendPredictor:
    """Test trend predictor functionality."""

    def test_init(self):
        """Test initialization."""
        predictor = TrendPredictor(config={'horizon': 5})
        assert predictor.horizon == 5

    def test_predict_trend(self, sample_features, mock_model):
        """Test trend prediction."""
        predictor = TrendPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            trends = predictor.predict_trend(sample_features.iloc[:5])
            assert len(trends) == 5
            assert all(isinstance(t, float) for t in trends)

    def test_predict_trend_strength(self, sample_features, mock_model):
        """Test trend strength prediction."""
        predictor = TrendPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            strengths = predictor.predict_trend_strength(sample_features.iloc[:5])
            assert len(strengths) == 5
            assert all(0 <= s <= 1 for s in strengths)

    def test_predict_trend_label(self, sample_features, mock_model):
        """Test trend label prediction."""
        predictor = TrendPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            labels = predictor.predict_trend_label(sample_features.iloc[:5])
            assert len(labels) == 5
            assert all(l in ['strong_up', 'up', 'neutral', 'down', 'strong_down'] for l in labels)

    def test_predict_trend_with_confidence(self, sample_features, mock_model):
        """Test trend prediction with confidence."""
        predictor = TrendPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            result = predictor.predict_with_confidence(sample_features.iloc[:5])
            assert 'trend' in result
            assert 'confidence' in result
            assert 'strength' in result

# ============================================================================
# TEST VOLATILITY PREDICTOR
# ============================================================================

class TestVolatilityPredictor:
    """Test volatility predictor functionality."""

    def test_init(self):
        """Test initialization."""
        predictor = VolatilityPredictor(config={'horizon': 10})
        assert predictor.horizon == 10

    def test_predict_volatility(self, sample_features, mock_model):
        """Test volatility prediction."""
        predictor = VolatilityPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            vols = predictor.predict_volatility(sample_features.iloc[:5])
            assert len(vols) == 5
            assert all(v > 0 for v in vols)

    def test_predict_volatility_interval(self, sample_features, mock_model):
        """Test volatility interval prediction."""
        predictor = VolatilityPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            lower, upper = predictor.predict_volatility_interval(
                sample_features.iloc[:5],
                confidence=0.95
            )
            assert len(lower) == 5
            assert len(upper) == 5
            assert all(0 <= l <= u for l, u in zip(lower, upper))

    def test_predict_volatility_regime(self, sample_features, mock_model):
        """Test volatility regime prediction."""
        predictor = VolatilityPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            regimes = predictor.predict_volatility_regime(sample_features.iloc[:5])
            assert len(regimes) == 5
            assert all(r in ['low', 'medium', 'high', 'extreme'] for r in regimes)

# ============================================================================
# TEST SENTIMENT PREDICTOR
# ============================================================================

class TestSentimentPredictor:
    """Test sentiment predictor functionality."""

    def test_init(self):
        """Test initialization."""
        predictor = SentimentPredictor(config={'model_type': 'finbert'})
        assert predictor.model_type == 'finbert'

    def test_predict_sentiment(self, sample_sentiment_texts, mock_model):
        """Test sentiment score prediction."""
        predictor = SentimentPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            scores = predictor.predict_sentiment(sample_sentiment_texts)
            assert len(scores) == len(sample_sentiment_texts)
            assert all(0 <= s <= 1 for s in scores)

    def test_predict_sentiment_label(self, sample_sentiment_texts, mock_model):
        """Test sentiment label prediction."""
        predictor = SentimentPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            labels = predictor.predict_sentiment_label(sample_sentiment_texts)
            assert len(labels) == len(sample_sentiment_texts)
            assert all(l in ['positive', 'negative', 'neutral'] for l in labels)

    def test_predict_sentiment_aggregate(self, sample_sentiment_texts, mock_model):
        """Test aggregate sentiment prediction."""
        predictor = SentimentPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            aggregate = predictor.predict_sentiment_aggregate(sample_sentiment_texts)
            assert 'overall_sentiment' in aggregate
            assert 'positive_ratio' in aggregate
            assert 'negative_ratio' in aggregate
            assert 'neutral_ratio' in aggregate
            assert 'average_score' in aggregate

    def test_predict_sentiment_with_context(self, sample_sentiment_texts, mock_model):
        """Test sentiment prediction with context."""
        predictor = SentimentPredictor(config={'use_context': True})
        with patch.object(predictor, '_load_model', return_value=mock_model):
            result = predictor.predict_with_context(sample_sentiment_texts)
            assert 'scores' in result
            assert 'labels' in result
            assert 'contextual_sentiment' in result

# ============================================================================
# TEST PREDICTION PIPELINE
# ============================================================================

class TestPredictionPipeline:
    """Test prediction pipeline functionality."""

    def test_init(self):
        """Test initialization."""
        pipeline = PredictionPipeline(config={'max_workers': 2})
        assert pipeline.max_workers == 2

    def test_run_pipeline_sync(self, sample_features, mock_model):
        """Test synchronous pipeline execution."""
        pipeline = PredictionPipeline()
        with patch.object(pipeline, '_load_models', return_value=[mock_model]):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_features):
                predictions = pipeline.run(sample_features)
                assert isinstance(predictions, list)
                assert len(predictions) == 1  # one model

    @pytest.mark.asyncio
    async def test_run_pipeline_async(self, sample_features, mock_model):
        """Test asynchronous pipeline execution."""
        pipeline = PredictionPipeline()
        with patch.object(pipeline, '_load_models_async', return_value=[mock_model]):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_features):
                predictions = await pipeline.run_async(sample_features)
                assert isinstance(predictions, list)
                assert len(predictions) == 1

    def test_pipeline_with_ensemble(self, sample_features, mock_ensemble_model):
        """Test pipeline with ensemble model."""
        pipeline = PredictionPipeline(config={'ensemble': True})
        with patch.object(pipeline, '_load_models', return_value=[mock_ensemble_model]):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_features):
                predictions = pipeline.run(sample_features)
                assert len(predictions) == 1

    def test_pipeline_cache(self, sample_features, mock_model, prediction_cache):
        """Test pipeline caching."""
        pipeline = PredictionPipeline(config={'cache_enabled': True})
        pipeline.cache = prediction_cache
        with patch.object(pipeline, '_load_models', return_value=[mock_model]):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_features):
                # First run should compute
                result1 = pipeline.run(sample_features)
                # Second run should use cache
                result2 = pipeline.run(sample_features)
                # If cache works, result2 should be same object or equal
                assert result1 == result2

    def test_pipeline_error_handling(self, sample_features):
        """Test pipeline error handling."""
        pipeline = PredictionPipeline()
        with patch.object(pipeline, '_load_models', side_effect=Exception("Model load failed")):
            with pytest.raises(Exception):
                pipeline.run(sample_features)

# ============================================================================
# TEST ENSEMBLE PREDICTOR
# ============================================================================

class TestEnsemblePredictor:
    """Test ensemble predictor functionality."""

    def test_init(self):
        """Test initialization."""
        ensemble = EnsemblePredictor(config={'method': 'voting'})
        assert ensemble.method == 'voting'

    def test_voting_ensemble(self, sample_features, mock_ensemble_model):
        """Test voting ensemble."""
        models = [mock_ensemble_model, mock_ensemble_model]
        ensemble = EnsemblePredictor(config={'method': 'voting'})
        predictions = ensemble.predict(models, sample_features.iloc[:5])
        assert len(predictions) == 5

    def test_weighted_voting(self, sample_features, mock_ensemble_model):
        """Test weighted voting ensemble."""
        models = [mock_ensemble_model, mock_ensemble_model]
        weights = [0.7, 0.3]
        ensemble = EnsemblePredictor(config={'method': 'weighted_voting', 'weights': weights})
        predictions = ensemble.predict(models, sample_features.iloc[:5])
        assert len(predictions) == 5

    def test_averaging_ensemble(self, sample_features, mock_ensemble_model):
        """Test averaging ensemble."""
        models = [mock_ensemble_model, mock_ensemble_model]
        ensemble = EnsemblePredictor(config={'method': 'average'})
        predictions = ensemble.predict(models, sample_features.iloc[:5])
        assert len(predictions) == 5

    def test_ensemble_with_confidence(self, sample_features, mock_ensemble_model):
        """Test ensemble prediction with confidence."""
        models = [mock_ensemble_model, mock_ensemble_model]
        ensemble = EnsemblePredictor(config={'method': 'average'})
        preds, confs = ensemble.predict_with_confidence(models, sample_features.iloc[:5])
        assert len(preds) == 5
        assert len(confs) == 5
        assert all(0 <= c <= 1 for c in confs)

# ============================================================================
# TEST PREDICTION CACHE
# ============================================================================

class TestPredictionCache:
    """Test prediction cache functionality."""

    def test_init(self):
        """Test cache initialization."""
        cache = PredictionCache(config={'ttl': 60, 'max_size': 10})
        assert cache.ttl == 60
        assert cache.max_size == 10

    def test_set_get(self, prediction_cache):
        """Test setting and getting cache values."""
        key = "test_key"
        value = {"prediction": 0.5}
        prediction_cache.set(key, value)
        result = prediction_cache.get(key)
        assert result == value

    def test_cache_expiry(self):
        """Test cache entry expiry."""
        cache = PredictionCache(config={'ttl': 1, 'max_size': 10})
        key = "expiry_key"
        cache.set(key, {"value": 1})
        import time
        time.sleep(1.1)
        result = cache.get(key)
        assert result is None

    def test_cache_max_size(self):
        """Test cache max size limit."""
        cache = PredictionCache(config={'ttl': 60, 'max_size': 2})
        cache.set("key1", {"value": 1})
        cache.set("key2", {"value": 2})
        cache.set("key3", {"value": 3})
        # Should evict oldest (key1)
        assert cache.get("key1") is None
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None

    def test_cache_clear(self, prediction_cache):
        """Test cache clearing."""
        prediction_cache.set("key1", {"value": 1})
        prediction_cache.clear()
        assert prediction_cache.get("key1") is None

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests with real components (mocked for speed)."""

    def test_end_to_end_price_prediction(self, sample_features, mock_model):
        """Test end-to-end price prediction workflow."""
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            prices = predictor.predict_price(sample_features.iloc[:5])
            # Also test range
            lower, upper = predictor.predict_price_range(sample_features.iloc[:5])
            assert len(prices) == 5
            assert len(lower) == 5
            assert len(upper) == 5

    def test_market_sentiment_integration(self, sample_features, sample_sentiment_texts, mock_model):
        """Test combining market data and sentiment."""
        market_pred = MarketPredictor()
        sent_pred = SentimentPredictor()
        with patch.object(market_pred, '_load_model', return_value=mock_model):
            with patch.object(sent_pred, '_load_model', return_value=mock_model):
                market_direction = market_pred.predict_direction(sample_features.iloc[:10])
                sentiment = sent_pred.predict_sentiment_aggregate(sample_sentiment_texts)
                # Combine logic (simplified)
                combined_score = 0.7 if market_direction == 'up' else 0.3
                if sentiment['overall_sentiment'] == 'positive':
                    combined_score += 0.2
                assert 0 <= combined_score <= 1

    def test_pipeline_with_multiple_predictors(self, sample_features, mock_model):
        """Test pipeline with multiple predictor types."""
        pipeline = PredictionPipeline(config={'models': [mock_model] * 3})
        with patch.object(pipeline, '_load_models', return_value=[mock_model] * 3):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_features):
                predictions = pipeline.run(sample_features)
                assert len(predictions) == 3

# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance benchmarks for predictions."""

    @pytest.mark.benchmark
    def test_market_prediction_speed(self, benchmark, sample_features, mock_model):
        """Benchmark market prediction speed."""
        predictor = MarketPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            def predict():
                return predictor.predict_direction(sample_features.iloc[:50])
            result = benchmark(predict)
            assert result in ['up', 'down', 'neutral']

    @pytest.mark.benchmark
    def test_sentiment_prediction_speed(self, benchmark, sample_sentiment_texts, mock_model):
        """Benchmark sentiment prediction speed."""
        predictor = SentimentPredictor()
        with patch.object(predictor, '_load_model', return_value=mock_model):
            def predict():
                return predictor.predict_sentiment(sample_sentiment_texts)
            result = benchmark(predict)
            assert len(result) == len(sample_sentiment_texts)

# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling in prediction components."""

    def test_market_predictor_no_model(self, sample_features):
        """Test market predictor without model."""
        predictor = MarketPredictor()
        with patch.object(predictor, '_load_model', return_value=None):
            with pytest.raises(ValueError, match="Model not loaded"):
                predictor.predict_direction(sample_features.iloc[:10])

    def test_price_predictor_invalid_data(self):
        """Test price predictor with invalid data."""
        predictor = PricePredictor()
        with patch.object(predictor, '_load_model', return_value=MagicMock()):
            with pytest.raises(ValueError):
                predictor.predict_price(None)

    def test_sentiment_predictor_empty_texts(self):
        """Test sentiment predictor with empty input."""
        predictor = SentimentPredictor()
        with patch.object(predictor, '_load_model', return_value=MagicMock()):
            result = predictor.predict_sentiment([])
            assert result == []

    def test_pipeline_worker_failure(self, sample_features):
        """Test pipeline handling of worker failures."""
        pipeline = PredictionPipeline(config={'max_workers': 2})
        with patch.object(pipeline, '_load_models', return_value=[MagicMock()]):
            with patch.object(pipeline, '_preprocess_data', return_value=sample_features):
                # Simulate worker failure in one model
                def faulty_predict(X):
                    raise RuntimeError("Prediction failed")
                pipeline.models[0].predict = faulty_predict
                with pytest.raises(RuntimeError):
                    pipeline.run(sample_features)

    def test_ensemble_weight_validation(self, sample_features):
        """Test ensemble weight validation."""
        models = [MagicMock(), MagicMock()]
        ensemble = EnsemblePredictor(config={'method': 'weighted_voting', 'weights': [0.7]})
        with pytest.raises(ValueError, match="Number of weights must match number of models"):
            ensemble.predict(models, sample_features.iloc[:5])

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

# trading/bots/ai_bot/tests/test_data_pipeline.py
"""
NEXUS AI TRADING SYSTEM - Data Pipeline Test Suite
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive test suite for the AI Bot data pipeline.
Tests include:
    - Data ingestion and validation
    - Feature engineering pipeline
    - Data preprocessing and normalization
    - Batch and streaming data processing
    - Data quality and integrity checks
    - Performance and scalability tests
    - Error handling and recovery
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Generator
import json
import logging
import asyncio
from dataclasses import dataclass, field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trading.bots.ai_bot.tests.fixtures import (
    NEXUS_FIXTURES,
    load_all_fixtures,
    get_test_symbols,
    get_test_timeframes,
    FIXTURES_DIR
)
from trading.bots.ai_bot.data_pipeline import (
    DataPipeline,
    DataIngestor,
    DataTransformer,
    FeatureEngine,
    DataValidator,
    DataCache,
    BatchProcessor,
    StreamingProcessor
)
from trading.bots.ai_bot.config import BotConfig
from trading.bots.ai_bot.market_data import MarketDataProvider

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test constants
NEXUS_QUANTUM = "NEXUS QUANTUM LTD"
COPYRIGHT = "Copyright © 2026 NEXUS QUANTUM LTD"
CEO = "Dr X..."
TEST_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD']
TEST_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d']
BATCH_SIZE = 1000
FEATURE_WINDOW = 100


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def fixtures():
    """Load all test fixtures."""
    return load_all_fixtures(force_reload=False)


@pytest.fixture
def test_data(fixtures):
    """Get test data."""
    return fixtures.test_data


@pytest.fixture
def test_config():
    """Create test configuration."""
    return {
        'pipeline': {
            'batch_size': BATCH_SIZE,
            'feature_window': FEATURE_WINDOW,
            'cache_enabled': True,
            'cache_ttl': 300,
            'validation_enabled': True,
            'normalization_enabled': True
        },
        'data': {
            'symbols': TEST_SYMBOLS,
            'timeframes': TEST_TIMEFRAMES,
            'max_history': 10000,
            'update_interval': 60
        },
        'features': {
            'technical': ['rsi', 'macd', 'bb_upper', 'bb_lower', 'sma_20', 'sma_50', 'ema_12'],
            'sentiment': ['news_sentiment', 'twitter_sentiment', 'reddit_sentiment'],
            'onchain': ['activity', 'whale_transactions', 'exchange_flows'],
            'market': ['volatility', 'volume', 'order_book_imbalance']
        },
        'validation': {
            'min_data_points': 100,
            'max_missing_ratio': 0.05,
            'outlier_threshold': 3.0,
            'required_columns': ['open', 'high', 'low', 'close', 'volume']
        },
        'trading': {
            'initial_capital': 100000.0,
            'max_positions': 5,
            'max_risk_per_trade': 0.02
        }
    }


@pytest.fixture
def mock_market_data():
    """Mock market data provider."""
    with patch('trading.bots.ai_bot.market_data.MarketDataProvider') as mock:
        provider = Mock()
        provider.get_current_price.return_value = 43000.0
        provider.get_historical_data.return_value = pd.DataFrame({
            'timestamp': pd.date_range(start='2026-07-16', periods=100, freq='1h'),
            'open': np.random.randn(100) * 100 + 42000,
            'high': np.random.randn(100) * 100 + 42200,
            'low': np.random.randn(100) * 100 + 41800,
            'close': np.random.randn(100) * 100 + 42500,
            'volume': np.random.randn(100) * 100000 + 1000000
        })
        provider.subscribe.return_value = True
        provider.unsubscribe.return_value = True
        mock.return_value = provider
        yield provider


@pytest.fixture
def data_pipeline(test_config, mock_market_data):
    """Create data pipeline instance."""
    config = BotConfig(**test_config)
    pipeline = DataPipeline(config)
    pipeline.market_data = mock_market_data
    return pipeline


# =============================================================================
# Data Pipeline Tests
# =============================================================================

class TestDataPipeline:
    """Main test class for data pipeline."""

    def test_pipeline_initialization(self, data_pipeline):
        """Test data pipeline initialization."""
        assert data_pipeline is not None
        assert data_pipeline.config is not None
        assert data_pipeline.ingestor is not None
        assert data_pipeline.transformer is not None
        assert data_pipeline.validator is not None
        assert data_pipeline.cache is not None
        assert data_pipeline.initialized is True

    def test_pipeline_config_validation(self, test_config):
        """Test pipeline configuration validation."""
        config = BotConfig(**test_config)
        pipeline = DataPipeline(config)
        assert pipeline.validate_config() is True
        
        # Test invalid config
        invalid_config = test_config.copy()
        invalid_config['pipeline']['batch_size'] = 0
        config = BotConfig(**invalid_config)
        pipeline = DataPipeline(config)
        with pytest.raises(ValueError):
            pipeline.validate_config()

    def test_data_ingestion(self, data_pipeline):
        """Test data ingestion functionality."""
        # Test single symbol ingestion
        data = data_pipeline.ingest_data('BTC-USD', '1h', limit=100)
        assert data is not None
        assert isinstance(data, pd.DataFrame)
        assert len(data) > 0
        
        # Test multiple symbols ingestion
        data = data_pipeline.ingest_data(
            symbols=TEST_SYMBOLS[:2],
            timeframe='1h',
            limit=100
        )
        assert data is not None
        assert isinstance(data, dict)
        assert len(data) == 2
        assert all(sym in data for sym in TEST_SYMBOLS[:2])

    def test_data_validation(self, data_pipeline):
        """Test data validation."""
        # Valid data
        valid_data = pd.DataFrame({
            'open': [42000.0, 42500.0],
            'high': [42500.0, 43000.0],
            'low': [41800.0, 42200.0],
            'close': [42300.0, 42800.0],
            'volume': [1000000.0, 1200000.0]
        })
        assert data_pipeline.validate_data(valid_data) is True
        
        # Invalid data - missing required columns
        invalid_data = pd.DataFrame({
            'open': [42000.0, 42500.0],
            'high': [42500.0, 43000.0]
        })
        assert data_pipeline.validate_data(invalid_data) is False
        
        # Invalid data - empty
        empty_data = pd.DataFrame()
        assert data_pipeline.validate_data(empty_data) is False

    def test_data_transformation(self, data_pipeline):
        """Test data transformation."""
        # Sample data
        data = pd.DataFrame({
            'timestamp': pd.date_range(start='2026-07-16', periods=10, freq='1h'),
            'open': np.random.randn(10) * 100 + 42000,
            'high': np.random.randn(10) * 100 + 42200,
            'low': np.random.randn(10) * 100 + 41800,
            'close': np.random.randn(10) * 100 + 42500,
            'volume': np.random.randn(10) * 100000 + 1000000
        })
        
        transformed = data_pipeline.transform_data(data)
        assert transformed is not None
        assert len(transformed) > 0
        
        # Check that technical indicators were added
        feature_columns = data_pipeline.config.get('features', {}).get('technical', [])
        for feature in feature_columns:
            if feature in data_pipeline.transformer.technical_indicators:
                assert feature in transformed.columns

    def test_feature_engineering(self, data_pipeline):
        """Test feature engineering."""
        # Sample data
        data = pd.DataFrame({
            'close': np.random.randn(100) * 100 + 42000,
            'volume': np.random.randn(100) * 100000 + 1000000
        })
        
        features = data_pipeline.engineer_features(data)
        assert features is not None
        assert len(features) > 0
        
        # Check feature types
        for feature_name, feature_values in features.items():
            if isinstance(feature_values, pd.Series):
                assert len(feature_values) == len(data)
            elif isinstance(feature_values, np.ndarray):
                assert feature_values.shape[0] == len(data)

    def test_data_normalization(self, data_pipeline):
        """Test data normalization."""
        # Sample data with different scales
        data = pd.DataFrame({
            'price': np.random.randn(100) * 1000 + 40000,
            'volume': np.random.randn(100) * 100000 + 1000000,
            'rsi': np.random.randn(100) * 20 + 50
        })
        
        normalized = data_pipeline.normalize_data(data)
        assert normalized is not None
        
        # Check normalization (should be in range [0, 1] or [-1, 1])
        for column in normalized.columns:
            if data_pipeline.config.get('normalization_enabled', True):
                assert normalized[column].min() >= -1
                assert normalized[column].max() <= 1

    def test_batch_processing(self, data_pipeline):
        """Test batch processing."""
        # Generate test data
        test_data = pd.DataFrame({
            'timestamp': pd.date_range(start='2026-07-16', periods=5000, freq='1min'),
            'open': np.random.randn(5000) * 100 + 42000,
            'high': np.random.randn(5000) * 100 + 42200,
            'low': np.random.randn(5000) * 100 + 41800,
            'close': np.random.randn(5000) * 100 + 42500,
            'volume': np.random.randn(5000) * 100000 + 1000000
        })
        
        # Process in batches
        batch_size = 100
        results = []
        
        for i in range(0, len(test_data), batch_size):
            batch = test_data.iloc[i:i+batch_size]
            processed = data_pipeline.process_batch(batch)
            results.append(processed)
        
        assert len(results) > 0
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_streaming_processing(self, data_pipeline):
        """Test streaming data processing."""
        # Start streaming
        await data_pipeline.start_streaming()
        assert data_pipeline.is_streaming() is True
        
        # Simulate data updates
        symbols = TEST_SYMBOLS[:2]
        for symbol in symbols:
            data = data_pipeline.market_data.get_historical_data(
                symbol, '1h', limit=10
            )
            await data_pipeline.process_stream_data(symbol, data)
        
        # Verify data was processed
        processed_data = data_pipeline.get_processed_data()
        assert processed_data is not None
        
        # Stop streaming
        await data_pipeline.stop_streaming()
        assert data_pipeline.is_streaming() is False

    def test_data_caching(self, data_pipeline):
        """Test data caching."""
        # Test cache set and get
        key = 'test_key'
        value = pd.DataFrame({'test': [1, 2, 3]})
        
        data_pipeline.cache.set(key, value)
        cached = data_pipeline.cache.get(key)
        assert cached is not None
        assert cached.equals(value)
        
        # Test cache expiry
        with patch('time.time') as mock_time:
            mock_time.return_value = 1000
            data_pipeline.cache.set(key, value, ttl=10)
            
            mock_time.return_value = 1020
            cached = data_pipeline.cache.get(key)
            assert cached is None
        
        # Test cache clear
        data_pipeline.cache.clear()
        assert data_pipeline.cache.get(key) is None

    def test_data_quality_checks(self, data_pipeline):
        """Test data quality checks."""
        # Data with missing values
        data_with_missing = pd.DataFrame({
            'open': [42000.0, np.nan, 42500.0],
            'high': [42500.0, 43000.0, np.nan],
            'low': [41800.0, 42200.0, 42000.0],
            'close': [42300.0, np.nan, 42800.0],
            'volume': [1000000.0, 1200000.0, 1100000.0]
        })
        
        quality_report = data_pipeline.check_data_quality(data_with_missing)
        assert quality_report is not None
        assert quality_report['missing_ratio'] > 0
        assert quality_report['is_valid'] is False
        
        # Clean data
        data_clean = data_with_missing.dropna()
        quality_report = data_pipeline.check_data_quality(data_clean)
        assert quality_report['missing_ratio'] == 0
        assert quality_report['is_valid'] is True

    def test_outlier_detection(self, data_pipeline):
        """Test outlier detection."""
        # Data with outliers
        data_with_outliers = pd.DataFrame({
            'close': [42000.0, 42500.0, 100000.0, 42800.0, 42000.0],
            'volume': [1000000.0, 1200000.0, 50000000.0, 1100000.0, 1050000.0]
        })
        
        outliers = data_pipeline.detect_outliers(data_with_outliers)
        assert outliers is not None
        assert len(outliers) > 0
        assert all(isinstance(idx, int) for idx in outliers)


class TestDataIngestor:
    """Test data ingestor component."""

    def test_ingestor_initialization(self, test_config):
        """Test ingestor initialization."""
        config = BotConfig(**test_config)
        ingestor = DataIngestor(config)
        assert ingestor is not None
        assert ingestor.config is not None

    def test_ingestor_single_symbol(self, test_config, mock_market_data):
        """Test ingesting single symbol data."""
        config = BotConfig(**test_config)
        ingestor = DataIngestor(config)
        ingestor.market_data = mock_market_data
        
        data = ingestor.ingest('BTC-USD', '1h', limit=100)
        assert data is not None
        assert isinstance(data, pd.DataFrame)
        assert len(data) > 0
        mock_market_data.get_historical_data.assert_called()

    def test_ingestor_multiple_symbols(self, test_config, mock_market_data):
        """Test ingesting multiple symbols data."""
        config = BotConfig(**test_config)
        ingestor = DataIngestor(config)
        ingestor.market_data = mock_market_data
        
        data = ingestor.ingest(
            symbols=TEST_SYMBOLS[:3],
            timeframe='1h',
            limit=100
        )
        assert data is not None
        assert isinstance(data, dict)
        assert len(data) == 3
        assert all(sym in data for sym in TEST_SYMBOLS[:3])

    def test_ingestor_with_validation(self, test_config, mock_market_data):
        """Test ingestor with validation enabled."""
        config = BotConfig(**test_config)
        config.validation_enabled = True
        ingestor = DataIngestor(config)
        ingestor.market_data = mock_market_data
        
        data = ingestor.ingest('BTC-USD', '1h', limit=100)
        assert data is not None
        assert ingestor.last_validation_status is True

    def test_ingestor_error_handling(self, test_config):
        """Test ingestor error handling."""
        config = BotConfig(**test_config)
        ingestor = DataIngestor(config)
        
        # Test with invalid symbol
        with pytest.raises(ValueError):
            ingestor.ingest('INVALID-SYMBOL', '1h', limit=100)


class TestDataTransformer:
    """Test data transformer component."""

    def test_transformer_initialization(self, test_config):
        """Test transformer initialization."""
        config = BotConfig(**test_config)
        transformer = DataTransformer(config)
        assert transformer is not None
        assert transformer.config is not None

    def test_technical_indicator_calculation(self, test_config):
        """Test technical indicator calculation."""
        config = BotConfig(**test_config)
        transformer = DataTransformer(config)
        
        # Generate sample data
        data = pd.DataFrame({
            'close': np.random.randn(100) * 100 + 42000,
            'high': np.random.randn(100) * 100 + 42200,
            'low': np.random.randn(100) * 100 + 41800,
            'volume': np.random.randn(100) * 100000 + 1000000
        })
        
        # Calculate RSI
        rsi = transformer.calculate_rsi(data['close'], period=14)
        assert rsi is not None
        assert len(rsi) == len(data)
        assert all(0 <= v <= 100 for v in rsi.dropna())
        
        # Calculate MACD
        macd, signal, hist = transformer.calculate_macd(data['close'])
        assert macd is not None
        assert signal is not None
        assert hist is not None
        
        # Calculate Bollinger Bands
        upper, middle, lower = transformer.calculate_bollinger_bands(data['close'])
        assert upper is not None
        assert middle is not None
        assert lower is not None

    def test_feature_extraction(self, test_config):
        """Test feature extraction."""
        config = BotConfig(**test_config)
        transformer = DataTransformer(config)
        
        data = pd.DataFrame({
            'close': np.random.randn(100) * 100 + 42000,
            'volume': np.random.randn(100) * 100000 + 1000000
        })
        
        features = transformer.extract_features(data)
        assert features is not None
        assert len(features) > 0
        
        # Check that required features exist
        feature_config = config.get('features', {})
        all_technical = feature_config.get('technical', [])
        for tech in all_technical:
            if tech in transformer.technical_indicators:
                assert tech in features.columns

    def test_data_normalization(self, test_config):
        """Test data normalization."""
        config = BotConfig(**test_config)
        transformer = DataTransformer(config)
        
        data = pd.DataFrame({
            'value1': np.random.randn(100) * 1000 + 40000,
            'value2': np.random.randn(100) * 100 + 50
        })
        
        normalized = transformer.normalize(data)
        assert normalized is not None
        assert normalized['value1'].min() >= -1
        assert normalized['value1'].max() <= 1
        assert normalized['value2'].min() >= -1
        assert normalized['value2'].max() <= 1

    def test_lagged_features(self, test_config):
        """Test lagged feature creation."""
        config = BotConfig(**test_config)
        transformer = DataTransformer(config)
        
        data = pd.DataFrame({
            'close': np.random.randn(100) * 100 + 42000
        })
        
        with_lags = transformer.create_lagged_features(data, lags=[1, 2, 3, 5, 10])
        assert with_lags is not None
        assert 'close_lag_1' in with_lags.columns
        assert 'close_lag_10' in with_lags.columns


class TestDataValidator:
    """Test data validator component."""

    def test_validator_initialization(self, test_config):
        """Test validator initialization."""
        config = BotConfig(**test_config)
        validator = DataValidator(config)
        assert validator is not None
        assert validator.config is not None

    def test_schema_validation(self, test_config):
        """Test schema validation."""
        config = BotConfig(**test_config)
        validator = DataValidator(config)
        
        # Valid schema
        valid_data = pd.DataFrame({
            'open': [42000.0],
            'high': [42500.0],
            'low': [41800.0],
            'close': [42300.0],
            'volume': [1000000.0]
        })
        assert validator.validate_schema(valid_data) is True
        
        # Invalid schema - missing column
        invalid_data = pd.DataFrame({
            'open': [42000.0],
            'high': [42500.0],
            'low': [41800.0]
        })
        assert validator.validate_schema(invalid_data) is False

    def test_range_validation(self, test_config):
        """Test range validation."""
        config = BotConfig(**test_config)
        validator = DataValidator(config)
        
        # Valid ranges
        valid_data = pd.DataFrame({
            'close': [42000.0, 43000.0, 42500.0],
            'volume': [1000000.0, 1200000.0, 1100000.0]
        })
        assert validator.validate_ranges(valid_data) is True
        
        # Invalid ranges - negative volume
        invalid_data = pd.DataFrame({
            'close': [42000.0, 43000.0, 42500.0],
            'volume': [-1000000.0, 1200000.0, 1100000.0]
        })
        assert validator.validate_ranges(invalid_data) is False

    def test_missing_value_validation(self, test_config):
        """Test missing value validation."""
        config = BotConfig(**test_config)
        validator = DataValidator(config)
        
        # Data with missing values within threshold
        data_with_missing = pd.DataFrame({
            'close': [42000.0, np.nan, 42500.0],
            'volume': [1000000.0, 1200000.0, 1100000.0]
        })
        result = validator.validate_missing_values(data_with_missing)
        assert result is True
        
        # Data with too many missing values
        data_with_many_missing = pd.DataFrame({
            'close': [np.nan, np.nan, np.nan],
            'volume': [1000000.0, 1200000.0, 1100000.0]
        })
        result = validator.validate_missing_values(data_with_many_missing)
        assert result is False

    def test_outlier_validation(self, test_config):
        """Test outlier validation."""
        config = BotConfig(**test_config)
        validator = DataValidator(config)
        
        # Data with outliers
        data_with_outliers = pd.DataFrame({
            'close': [42000.0, 42500.0, 100000.0, 42800.0],
            'volume': [1000000.0, 1200000.0, 50000000.0, 1100000.0]
        })
        outliers = validator.detect_outliers(data_with_outliers)
        assert len(outliers) > 0


class TestDataCache:
    """Test data cache component."""

    def test_cache_initialization(self, test_config):
        """Test cache initialization."""
        config = BotConfig(**test_config)
        cache = DataCache(config)
        assert cache is not None
        assert cache.config is not None
        assert cache.cache_enabled is True

    def test_cache_set_get(self, test_config):
        """Test cache set and get operations."""
        config = BotConfig(**test_config)
        cache = DataCache(config)
        
        key = 'test_key'
        value = pd.DataFrame({'test': [1, 2, 3]})
        
        cache.set(key, value)
        cached = cache.get(key)
        assert cached is not None
        assert cached.equals(value)

    def test_cache_expiry(self, test_config):
        """Test cache expiration."""
        config = BotConfig(**test_config)
        cache = DataCache(config)
        
        key = 'test_key'
        value = pd.DataFrame({'test': [1, 2, 3]})
        
        with patch('time.time') as mock_time:
            mock_time.return_value = 1000
            cache.set(key, value, ttl=10)
            
            mock_time.return_value = 1020
            cached = cache.get(key)
            assert cached is None

    def test_cache_clear(self, test_config):
        """Test cache clearing."""
        config = BotConfig(**test_config)
        cache = DataCache(config)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        assert len(cache._cache) == 3
        cache.clear()
        assert len(cache._cache) == 0

    def test_cache_invalidation(self, test_config):
        """Test cache invalidation by pattern."""
        config = BotConfig(**test_config)
        cache = DataCache(config)
        
        cache.set('BTC_USD_1h', 'data1')
        cache.set('BTC_USD_4h', 'data2')
        cache.set('ETH_USD_1h', 'data3')
        
        cache.invalidate_pattern('BTC_USD*')
        assert cache.get('BTC_USD_1h') is None
        assert cache.get('BTC_USD_4h') is None
        assert cache.get('ETH_USD_1h') is not None


class TestBatchProcessor:
    """Test batch processor component."""

    def test_batch_initialization(self, test_config):
        """Test batch processor initialization."""
        config = BotConfig(**test_config)
        processor = BatchProcessor(config)
        assert processor is not None
        assert processor.batch_size == BATCH_SIZE

    def test_batch_processing(self, test_config):
        """Test batch processing."""
        config = BotConfig(**test_config)
        processor = BatchProcessor(config)
        
        # Generate test data
        data = pd.DataFrame({
            'values': np.random.randn(5000)
        })
        
        batches = list(processor.process_batches(data))
        assert len(batches) > 0
        
        # Verify batch size
        for i, batch in enumerate(batches[:-1]):
            assert len(batch) == BATCH_SIZE
        
        # Last batch may be smaller
        if len(batches) > 1:
            assert len(batches[-1]) <= BATCH_SIZE

    def test_batch_parallel_processing(self, test_config):
        """Test parallel batch processing."""
        config = BotConfig(**test_config)
        processor = BatchProcessor(config)
        
        data = pd.DataFrame({
            'values': np.random.randn(1000)
        })
        
        results = processor.process_parallel(data, num_workers=4)
        assert len(results) > 0
        assert all(r is not None for r in results)


class TestStreamingProcessor:
    """Test streaming processor component."""

    def test_streaming_initialization(self, test_config):
        """Test streaming processor initialization."""
        config = BotConfig(**test_config)
        processor = StreamingProcessor(config)
        assert processor is not None
        assert processor.config is not None
        assert processor.is_running is False

    @pytest.mark.asyncio
    async def test_streaming_start_stop(self, test_config):
        """Test streaming start and stop."""
        config = BotConfig(**test_config)
        processor = StreamingProcessor(config)
        
        await processor.start()
        assert processor.is_running is True
        
        await processor.stop()
        assert processor.is_running is False

    @pytest.mark.asyncio
    async def test_streaming_data_processing(self, test_config):
        """Test streaming data processing."""
        config = BotConfig(**test_config)
        processor = StreamingProcessor(config)
        
        async def data_generator():
            for i in range(10):
                yield {'timestamp': datetime.now(), 'value': i}
                await asyncio.sleep(0.1)
        
        await processor.start()
        
        async for data in data_generator():
            await processor.process_data(data)
        
        await processor.stop()
        assert len(processor.processed_data) > 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for data pipeline."""

    def test_full_pipeline_flow(self, data_pipeline, test_data):
        """Test full data pipeline flow."""
        # Ingest data
        ingested = data_pipeline.ingest_data('BTC-USD', '1h', limit=1000)
        assert ingested is not None
        
        # Validate data
        assert data_pipeline.validate_data(ingested) is True
        
        # Transform data
        transformed = data_pipeline.transform_data(ingested)
        assert transformed is not None
        
        # Engineer features
        features = data_pipeline.engineer_features(transformed)
        assert features is not None
        assert len(features) > 0
        
        # Normalize data
        normalized = data_pipeline.normalize_data(transformed)
        assert normalized is not None
        
        # Cache data
        data_pipeline.cache.set('processed_data', normalized)
        cached = data_pipeline.cache.get('processed_data')
        assert cached is not None

    @pytest.mark.asyncio
    async def test_end_to_end_processing(self, data_pipeline):
        """Test end-to-end data processing."""
        # Start pipeline
        await data_pipeline.start()
        assert data_pipeline.is_running() is True
        
        # Process market data for multiple symbols
        for symbol in TEST_SYMBOLS[:2]:
            data = await data_pipeline.process_symbol(symbol, '1h')
            assert data is not None
            
            # Generate features
            features = data_pipeline.extract_features(data)
            assert features is not None
        
        # Stop pipeline
        await data_pipeline.stop()
        assert data_pipeline.is_running() is False


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for data pipeline."""

    def test_ingestion_speed(self, data_pipeline):
        """Test data ingestion speed."""
        import time
        
        iterations = 10
        symbols = TEST_SYMBOLS
        
        start_time = time.time()
        
        for _ in range(iterations):
            for symbol in symbols:
                data_pipeline.ingest_data(symbol, '1h', limit=100)
        
        elapsed = time.time() - start_time
        avg_time = elapsed / (iterations * len(symbols))
        
        # Should be under 100ms per ingestion
        assert avg_time < 0.1
        logger.info(f"Average ingestion time: {avg_time * 1000:.2f}ms")

    def test_feature_extraction_speed(self, data_pipeline):
        """Test feature extraction speed."""
        import time
        
        data = pd.DataFrame({
            'close': np.random.randn(1000) * 100 + 42000,
            'volume': np.random.randn(1000) * 100000 + 1000000,
            'high': np.random.randn(1000) * 100 + 42200,
            'low': np.random.randn(1000) * 100 + 41800
        })
        
        iterations = 100
        start_time = time.time()
        
        for _ in range(iterations):
            data_pipeline.engineer_features(data)
        
        elapsed = time.time() - start_time
        avg_time = elapsed / iterations
        
        # Should be under 10ms per feature extraction
        assert avg_time < 0.01
        logger.info(f"Average feature extraction time: {avg_time * 1000:.2f}ms")


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for data pipeline."""

    def test_empty_data_handling(self, data_pipeline):
        """Test handling of empty data."""
        empty_data = pd.DataFrame()
        result = data_pipeline.process_batch(empty_data)
        assert result is None or len(result) == 0

    def test_nan_handling(self, data_pipeline):
        """Test handling of NaN values."""
        data_with_nan = pd.DataFrame({
            'close': [42000.0, np.nan, 42500.0, 43000.0, np.nan],
            'volume': [1000000.0, 1200000.0, np.nan, 1100000.0, 1150000.0]
        })
        
        processed = data_pipeline.handle_missing_values(data_with_nan)
        assert processed is not None
        assert not processed.isnull().any().any()

    def test_inf_handling(self, data_pipeline):
        """Test handling of infinite values."""
        data_with_inf = pd.DataFrame({
            'close': [42000.0, np.inf, 42500.0, -np.inf, 43000.0],
            'volume': [1000000.0, 1200000.0, np.inf, 1100000.0, 1150000.0]
        })
        
        processed = data_pipeline.handle_infinite_values(data_with_inf)
        assert processed is not None
        assert not np.isinf(processed).any().any()

    def test_duplicate_timestamps(self, data_pipeline):
        """Test handling of duplicate timestamps."""
        timestamp = datetime.now()
        data_with_duplicates = pd.DataFrame({
            'timestamp': [timestamp, timestamp, timestamp + timedelta(hours=1)],
            'close': [42000.0, 42500.0, 43000.0]
        })
        
        cleaned = data_pipeline.deduplicate_data(data_with_duplicates)
        assert len(cleaned) == 2  # One duplicate removed


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    # Run pytest programmatically
    print("=" * 80)
    print("NEXUS AI TRADING SYSTEM - Data Pipeline Test Suite")
    print("=" * 80)
    print(f"Copyright: {COPYRIGHT}")
    print(f"CEO: {CEO}")
    print("-" * 80)
    
    # Run all tests
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--maxfail=1',
        '-x'
    ])
    
    print("\n" + "=" * 80)
    print("✅ Data Pipeline Test Suite Complete")
    print("=" * 80)

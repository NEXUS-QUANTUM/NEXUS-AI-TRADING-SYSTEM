# trading/bots/ai_bot/tests/fixtures/__init__.py
"""
NEXUS AI TRADING SYSTEM - Test Fixtures Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides test fixtures for the AI Bot trading system.
All fixtures are loaded from the fixtures directory and are used across
the test suite for consistent and reproducible testing.

Structure:
    - config_test.yaml: Test configuration settings
    - test_data.csv: Historical market data for backtesting
    - model_weights.pth: Pre-trained model weights for testing
    - model_metadata.json: Model metadata and hyperparameters
    - generate_model_weights.py: Script to generate test model weights
"""

import os
import json
import yaml
import pandas as pd
import torch
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Get the directory of this file
FIXTURES_DIR = Path(__file__).parent.absolute()

# Expose public API
__all__ = [
    'FIXTURES_DIR',
    'load_test_config',
    'load_test_data',
    'load_model_weights',
    'load_model_metadata',
    'get_fixture_path',
    'get_test_symbols',
    'get_test_timeframes',
    'load_all_fixtures',
    'generate_test_data',
    'TestFixtures',
    'FixturesLoader',
    'NEXUS_FIXTURES',
]


# Constants
NEXUS_QUANTUM = 'NEXUS QUANTUM LTD'
COPYRIGHT = 'Copyright © 2026 NEXUS QUANTUM LTD'
CEO = 'Dr X...'


@dataclass
class TestFixtures:
    """
    Test fixtures container for AI Bot testing.
    Loads and manages all test fixtures for the test suite.
    """
    config: Dict[str, Any] = field(default_factory=dict)
    test_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    model_weights: Optional[Dict[str, torch.Tensor]] = None
    model_metadata: Dict[str, Any] = field(default_factory=dict)
    symbols: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=list)
    loaded_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Initialize with default values if not provided."""
        if not self.symbols:
            self.symbols = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD']
        if not self.timeframes:
            self.timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']


class FixturesLoader:
    """
    Singleton loader for test fixtures.
    Ensures fixtures are loaded once and cached for performance.
    """
    _instance: Optional['FixturesLoader'] = None
    _fixtures: Optional[TestFixtures] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._fixtures = None
            logger.info("Initializing NEXUS AI Trading Test Fixtures Loader")

    @classmethod
    def get_instance(cls) -> 'FixturesLoader':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_all(self, force_reload: bool = False) -> TestFixtures:
        """
        Load all test fixtures.
        
        Args:
            force_reload: Force reload all fixtures even if cached.
            
        Returns:
            TestFixtures object containing all loaded fixtures.
        """
        if self._fixtures is not None and not force_reload:
            logger.debug("Returning cached fixtures")
            return self._fixtures

        logger.info("Loading all test fixtures...")
        self._fixtures = TestFixtures(
            config=load_test_config(),
            test_data=load_test_data(),
            model_weights=load_model_weights(),
            model_metadata=load_model_metadata(),
            symbols=get_test_symbols(),
            timeframes=get_test_timeframes()
        )
        logger.info(f"Fixtures loaded successfully at {self._fixtures.loaded_at}")
        return self._fixtures


def get_fixture_path(filename: str) -> Path:
    """
    Get the full path to a fixture file.
    
    Args:
        filename: Name of the fixture file.
        
    Returns:
        Path object pointing to the fixture file.
    """
    return FIXTURES_DIR / filename


def load_test_config() -> Dict[str, Any]:
    """
    Load test configuration from YAML file.
    
    Returns:
        Dictionary containing test configuration.
    """
    config_path = get_fixture_path('config_test.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.debug(f"Loaded test config from {config_path}")
        return config
    except FileNotFoundError:
        logger.warning(f"Config file not found at {config_path}, using default config")
        return _get_default_config()
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return _get_default_config()


def _get_default_config() -> Dict[str, Any]:
    """Return default test configuration."""
    return {
        'project': {
            'name': 'NEXUS AI TRADING SYSTEM',
            'version': '3.0.0',
            'copyright': '© 2026 NEXUS QUANTUM LTD',
            'ceo': 'Dr X...'
        },
        'test': {
            'enabled': True,
            'verbose': True,
            'parallel': False,
            'timeout': 30
        },
        'trading': {
            'symbols': ['BTC-USD', 'ETH-USD'],
            'timeframes': ['1h', '4h'],
            'initial_capital': 100000.0,
            'max_positions': 5,
            'max_risk_per_trade': 0.02
        },
        'ai': {
            'model': 'ensemble',
            'use_gpu': False,
            'batch_size': 32,
            'learning_rate': 0.001,
            'epochs': 10
        },
        'broker': {
            'type': 'paper',
            'slippage': 0.001,
            'commission': 0.001
        },
        'risk': {
            'max_drawdown': 0.20,
            'stop_loss': 0.02,
            'take_profit': 0.04,
            'risk_reward_ratio': 2.0
        }
    }


def load_test_data() -> pd.DataFrame:
    """
    Load test data from CSV file.
    
    Returns:
        DataFrame containing test market data.
    """
    data_path = get_fixture_path('test_data.csv')
    try:
        df = pd.read_csv(data_path, parse_dates=['timestamp'])
        logger.debug(f"Loaded test data with {len(df)} rows from {data_path}")
        return df
    except FileNotFoundError:
        logger.warning(f"Test data not found at {data_path}, generating sample data")
        return generate_test_data(n_rows=1000)
    except Exception as e:
        logger.error(f"Error loading test data: {e}")
        return generate_test_data(n_rows=100)


def generate_test_data(
    n_rows: int = 1000,
    symbol: str = 'BTC-USD',
    start_price: float = 42000.0,
    volatility: float = 0.02
) -> pd.DataFrame:
    """
    Generate synthetic test data when CSV is not available.
    
    Args:
        n_rows: Number of rows to generate.
        symbol: Trading symbol.
        start_price: Starting price.
        volatility: Daily volatility.
        
    Returns:
        DataFrame with synthetic market data.
    """
    import numpy as np
    from datetime import datetime, timedelta
    
    logger.info(f"Generating {n_rows} rows of synthetic test data for {symbol}")
    
    # Generate timestamps
    start_time = datetime(2026, 7, 16, 0, 0, 0)
    timestamps = [start_time + timedelta(hours=i) for i in range(n_rows)]
    
    # Generate prices with random walk
    np.random.seed(42)
    returns = np.random.normal(0, volatility / np.sqrt(252), n_rows)
    prices = start_price * np.exp(np.cumsum(returns))
    
    # Generate OHLC data
    open_prices = prices * (1 + np.random.normal(0, 0.001, n_rows))
    high_prices = prices * (1 + np.abs(np.random.normal(0.002, 0.001, n_rows)))
    low_prices = prices * (1 - np.abs(np.random.normal(0.002, 0.001, n_rows)))
    close_prices = prices * (1 + np.random.normal(0, 0.002, n_rows))
    
    # Generate volume
    volumes = np.abs(np.random.normal(1000000, 500000, n_rows))
    
    # Generate other indicators
    rsi = np.random.uniform(30, 70, n_rows)
    macd = np.random.normal(0, 0.01, n_rows)
    sentiment = np.random.uniform(0.3, 0.7, n_rows)
    volatility_actual = np.random.uniform(0.01, 0.05, n_rows)
    
    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'symbol': symbol,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes,
        'rsi': rsi,
        'macd': macd,
        'sentiment': sentiment,
        'volatility': volatility_actual
    })
    
    return df


def load_model_weights() -> Optional[Dict[str, torch.Tensor]]:
    """
    Load pre-trained model weights for testing.
    
    Returns:
        Dictionary of model parameters, or None if not available.
    """
    weights_path = get_fixture_path('model_weights.pth')
    try:
        if weights_path.exists():
            weights = torch.load(weights_path, map_location='cpu')
            logger.debug(f"Loaded model weights from {weights_path}")
            return weights
        else:
            logger.warning(f"Model weights not found at {weights_path}")
            return _generate_dummy_weights()
    except Exception as e:
        logger.error(f"Error loading model weights: {e}")
        return _generate_dummy_weights()


def _generate_dummy_weights() -> Dict[str, torch.Tensor]:
    """
    Generate dummy model weights for testing when file is not available.
    
    Returns:
        Dictionary of dummy tensor weights.
    """
    logger.info("Generating dummy model weights for testing")
    weights = {
        f'layer_{i}_weight': torch.randn(64, 64) / 10.0
        for i in range(5)
    }
    weights.update({
        f'layer_{i}_bias': torch.zeros(64)
        for i in range(5)
    })
    return weights


def load_model_metadata() -> Dict[str, Any]:
    """
    Load model metadata from JSON file.
    
    Returns:
        Dictionary containing model metadata.
    """
    metadata_path = get_fixture_path('model_metadata.json')
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        logger.debug(f"Loaded model metadata from {metadata_path}")
        return metadata
    except FileNotFoundError:
        logger.warning(f"Model metadata not found at {metadata_path}, using default")
        return _get_default_metadata()
    except Exception as e:
        logger.error(f"Error loading model metadata: {e}")
        return _get_default_metadata()


def _get_default_metadata() -> Dict[str, Any]:
    """Return default model metadata."""
    return {
        'model': {
            'name': 'NEXUS AI Trading Model',
            'version': '2.1.0',
            'type': 'ensemble',
            'architecture': 'transformer_lstm',
            'input_size': 128,
            'hidden_size': 256,
            'output_size': 3,
            'num_layers': 4,
            'dropout': 0.1
        },
        'training': {
            'dataset': 'nexus_training_v3',
            'epochs': 100,
            'batch_size': 64,
            'learning_rate': 0.001,
            'optimizer': 'adamw',
            'loss_function': 'cross_entropy',
            'early_stopping': True,
            'patience': 10
        },
        'performance': {
            'accuracy': 0.72,
            'precision': 0.71,
            'recall': 0.70,
            'f1_score': 0.705,
            'sharpe_ratio': 1.8,
            'max_drawdown': 0.15,
            'win_rate': 0.58
        },
        'features': {
            'technical': ['rsi', 'macd', 'bb_upper', 'bb_lower', 'sma_20', 'sma_50', 'ema_12'],
            'sentiment': ['news', 'twitter', 'reddit'],
            'onchain': ['activity', 'whale_transactions', 'exchange_flows'],
            'market': ['volatility', 'volume', 'order_book_imbalance']
        },
        'metadata': {
            'created_at': '2026-07-16T00:00:00Z',
            'created_by': 'NEXUS AI Training Pipeline',
            'copyright': '© 2026 NEXUS QUANTUM LTD',
            'ceo': 'Dr X...'
        }
    }


def get_test_symbols() -> List[str]:
    """
    Get list of test trading symbols.
    
    Returns:
        List of symbol strings.
    """
    config = load_test_config()
    symbols = config.get('trading', {}).get('symbols', [])
    return symbols or ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD']


def get_test_timeframes() -> List[str]:
    """
    Get list of test timeframes.
    
    Returns:
        List of timeframe strings.
    """
    config = load_test_config()
    timeframes = config.get('trading', {}).get('timeframes', [])
    return timeframes or ['1m', '5m', '15m', '1h', '4h', '1d']


def load_all_fixtures(force_reload: bool = False) -> TestFixtures:
    """
    Convenience function to load all test fixtures.
    
    Args:
        force_reload: Force reload all fixtures.
        
    Returns:
        TestFixtures object containing all loaded fixtures.
    """
    loader = FixturesLoader.get_instance()
    return loader.load_all(force_reload)


# Pre-loaded fixtures for convenience
NEXUS_FIXTURES: TestFixtures = load_all_fixtures()


# Export version
__version__ = '3.0.0'
__author__ = 'Dr X...'
__copyright__ = 'Copyright © 2026 NEXUS QUANTUM LTD'
__license__ = 'Proprietary - All Rights Reserved'


# Module docstring
__doc__ = f"""
{__name__} - NEXUS AI Trading System Test Fixtures

This module provides test fixtures for the NEXUS AI Trading System.
All fixtures are designed to be loaded once and reused across the test suite.

Copyright: {__copyright__}
CEO: {__author__}
Version: {__version__}

Usage:
    from trading.bots.ai_bot.tests.fixtures import load_all_fixtures, NEXUS_FIXTURES
    
    # Load all fixtures
    fixtures = load_all_fixtures()
    
    # Access specific fixtures
    config = fixtures.config
    test_data = fixtures.test_data
    model_weights = fixtures.model_weights
    
    # Or use pre-loaded fixtures
    config = NEXUS_FIXTURES.config
"""


if __name__ == '__main__':
    # Test the module
    print("=" * 80)
    print("NEXUS AI TRADING SYSTEM - Test Fixtures Module")
    print("=" * 80)
    print(f"Fixtures Directory: {FIXTURES_DIR}")
    print(f"Version: {__version__}")
    print(f"Copyright: {__copyright__}")
    print(f"CEO: {__author__}")
    print("-" * 80)
    
    # Load and display fixture information
    fixtures = load_all_fixtures()
    
    print("\nLoaded Fixtures:")
    print(f"  - Config keys: {len(fixtures.config)}")
    print(f"  - Test data rows: {len(fixtures.test_data)}")
    print(f"  - Model weights: {'Loaded' if fixtures.model_weights else 'None'}")
    print(f"  - Model metadata keys: {len(fixtures.model_metadata)}")
    print(f"  - Symbols: {fixtures.symbols}")
    print(f"  - Timeframes: {fixtures.timeframes}")
    print(f"  - Loaded at: {fixtures.loaded_at}")
    
    print("\n" + "=" * 80)
    print("✅ NEXUS AI Trading Test Fixtures Module Ready")
    print("=" * 80)

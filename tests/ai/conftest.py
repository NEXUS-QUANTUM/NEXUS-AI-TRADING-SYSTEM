"""
AI Module Test Configuration
=============================

This module provides pytest fixtures and configuration for testing
the AI components of the Swing Bot trading system.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil
import json
import yaml
from typing import Dict, List, Optional, Any, Generator
import logging
import os

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.bots.swing_bot.ai.models import ModelRegistry, BaseModel
from trading.bots.swing_bot.ai.prediction import PredictionService
from trading.bots.swing_bot.ai.inference import InferenceEngine
from trading.bots.swing_bot.ai.ensemble import EnsembleModel
from trading.bots.swing_bot.ai.features import FeatureEngine
from trading.bots.swing_bot.ai.training import Trainer
from trading.bots.swing_bot.ai.data import DataLoader, DataPreprocessor
from trading.bots.swing_bot.ai.config import ModelConfig, TrainingConfig


# ============================================================
# Test Configuration
# ============================================================

@pytest.fixture(scope="session")
def ai_test_config() -> Dict[str, Any]:
    """Provide AI test configuration."""
    return {
        "test_environment": "test",
        "debug": True,
        "log_level": "DEBUG",
        "data_dir": Path(__file__).parent / "data",
        "models_dir": Path(__file__).parent / "models",
        "checkpoints_dir": Path(__file__).parent / "checkpoints",
        "temp_dir": Path("/tmp/nexus_ai_tests"),
        "seed": 42,
        "test_data_size": 1000,
        "batch_size": 32,
        "epochs": 3,
    }


# ============================================================
# Directory Fixtures
# ============================================================

@pytest.fixture(scope="session")
def test_dirs(ai_test_config) -> Generator[Dict[str, Path], None, None]:
    """Create and clean up test directories."""
    dirs = {
        "data": ai_test_config["data_dir"],
        "models": ai_test_config["models_dir"],
        "checkpoints": ai_test_config["checkpoints_dir"],
        "temp": ai_test_config["temp_dir"],
    }
    
    # Create directories
    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    
    yield dirs
    
    # Cleanup temp directory only
    if dirs["temp"].exists():
        shutil.rmtree(dirs["temp"])


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================
# Data Fixtures
# ============================================================

@pytest.fixture
def sample_market_data(ai_test_config) -> pd.DataFrame:
    """
    Generate sample OHLCV data for testing.
    
    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    np.random.seed(ai_test_config["seed"])
    n = ai_test_config["test_data_size"]
    
    # Generate synthetic price data
    t = np.arange(n)
    trend = 0.001 * t
    noise = np.random.normal(0, 0.02, n)
    seasonal = 0.5 * np.sin(2 * np.pi * t / 50)
    
    base_price = 100.0
    close = base_price * (1 + trend + noise + seasonal)
    close = np.maximum(close, 1.0)  # Ensure positive prices
    
    # Generate OHLC
    high = close * (1 + np.random.uniform(0.005, 0.02, n))
    low = close * (1 - np.random.uniform(0.005, 0.02, n))
    open_price = close * (1 + np.random.uniform(-0.01, 0.01, n))
    
    # Volume
    volume = np.random.uniform(100000, 1000000, n).astype(int)
    
    # Dates
    start_date = datetime.now() - timedelta(days=n)
    dates = [start_date + timedelta(days=i) for i in range(n)]
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    
    # Add symbol column
    df['symbol'] = 'AAPL'
    
    return df


@pytest.fixture
def sample_returns(sample_market_data) -> np.ndarray:
    """Compute returns from sample market data."""
    return sample_market_data['close'].pct_change().dropna().values


@pytest.fixture
def sample_features(sample_market_data) -> pd.DataFrame:
    """
    Generate sample feature set for AI models.
    
    Returns:
        DataFrame with feature columns
    """
    df = sample_market_data.copy()
    
    # Simple features
    df['returns_1'] = df['close'].pct_change()
    df['returns_5'] = df['close'].pct_change(periods=5)
    df['returns_10'] = df['close'].pct_change(periods=10)
    df['volatility'] = df['returns_1'].rolling(10).std()
    df['volume_ratio'] = df['volume'] / df['volume'].rolling(10).mean()
    
    # Price position in range
    df['high_rolling'] = df['high'].rolling(20).max()
    df['low_rolling'] = df['low'].rolling(20).min()
    df['price_position'] = (df['close'] - df['low_rolling']) / (df['high_rolling'] - df['low_rolling'] + 1e-8)
    
    # Drop NaN
    df = df.dropna()
    
    return df


@pytest.fixture
def sample_target(sample_features) -> np.ndarray:
    """
    Generate target labels (next period returns).
    
    Returns:
        Array of binary labels or continuous returns
    """
    # Binary classification: 1 if next close > current close
    target = (sample_features['close'].shift(-1) > sample_features['close']).astype(int)
    return target.dropna().values


# ============================================================
# Model Fixtures
# ============================================================

@pytest.fixture
def model_registry() -> ModelRegistry:
    """Get a model registry instance for testing."""
    return ModelRegistry()


@pytest.fixture
def test_model_config() -> ModelConfig:
    """Create a simple test model configuration."""
    return ModelConfig(
        model_type="test_model",
        input_size=10,
        output_size=1,
        hidden_layers=[64, 32],
        activation="relu",
        learning_rate=0.001,
        batch_size=32,
        epochs=3,
        dropout_rate=0.2,
    )


@pytest.fixture
def test_training_config() -> TrainingConfig:
    """Create a simple training configuration."""
    return TrainingConfig(
        learning_rate=0.001,
        batch_size=32,
        epochs=3,
        validation_split=0.2,
        early_stopping_patience=2,
        checkpoint_interval=1,
        log_interval=1,
        save_best=True,
    )


# ============================================================
# Service Fixtures
# ============================================================

@pytest.fixture
def prediction_service(
    model_registry,
    test_model_config,
) -> PredictionService:
    """Create a prediction service for testing."""
    return PredictionService(
        model_registry=model_registry,
        config=test_model_config,
    )


@pytest.fixture
def inference_engine(
    model_registry,
    test_model_config,
) -> InferenceEngine:
    """Create an inference engine for testing."""
    return InferenceEngine(
        model_registry=model_registry,
        config=test_model_config,
    )


@pytest.fixture
def feature_engine() -> FeatureEngine:
    """Create a feature engine for testing."""
    return FeatureEngine()


@pytest.fixture
def trainer(
    model_registry,
    test_model_config,
    test_training_config,
) -> Trainer:
    """Create a trainer for testing."""
    return Trainer(
        model_registry=model_registry,
        model_config=test_model_config,
        training_config=test_training_config,
    )


# ============================================================
# Mock Model Fixtures
# ============================================================

@pytest.fixture
def mock_model() -> BaseModel:
    """Create a mock model that always returns a fixed prediction."""
    from trading.bots.swing_bot.ai.models import BaseModel
    
    class MockModel(BaseModel):
        def __init__(self, config):
            super().__init__(config)
            self.prediction_value = 0.5
        
        def predict(self, X):
            return np.full((len(X), 1), self.prediction_value)
        
        def train(self, X, y):
            return {"loss": 0.1, "accuracy": 0.8}
        
        def save(self, path):
            pass
        
        def load(self, path):
            pass
    
    return MockModel(test_model_config)


# ============================================================
# Config Fixtures
# ============================================================

@pytest.fixture
def ai_config_file(temp_dir) -> Path:
    """Create a temporary AI config file."""
    config_data = {
        "models": {
            "test_model": {
                "type": "test_model",
                "input_size": 10,
                "output_size": 1,
                "hidden_layers": [64, 32],
                "activation": "relu",
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 3,
                "dropout_rate": 0.2,
            }
        },
        "training": {
            "batch_size": 32,
            "epochs": 3,
            "validation_split": 0.2,
            "early_stopping_patience": 2,
            "checkpoint_interval": 1,
        },
        "data": {
            "features": ["returns_1", "returns_5", "volatility", "volume_ratio"],
            "target": "close",
            "lookback": 20,
            "forecast_horizon": 1,
        }
    }
    
    config_path = temp_dir / "ai_config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)
    
    return config_path


@pytest.fixture
def ai_config_json(temp_dir) -> Path:
    """Create a temporary AI config file in JSON."""
    config_data = {
        "models": {
            "test_model": {
                "type": "test_model",
                "input_size": 10,
                "output_size": 1,
                "hidden_layers": [64, 32],
                "activation": "relu",
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 3,
                "dropout_rate": 0.2,
            }
        }
    }
    
    config_path = temp_dir / "ai_config.json"
    with open(config_path, 'w') as f:
        json.dump(config_data, f)
    
    return config_path


# ============================================================
# Logging Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def setup_logging():
    """Setup logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    # Reduce verbosity of some loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("web3").setLevel(logging.WARNING)
    yield


# ============================================================
# Pytest Configuration
# ============================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "ai: mark test as AI-related"
    )
    config.addinivalue_line(
        "markers",
        "model: mark test as model-related"
    )
    config.addinivalue_line(
        "markers",
        "training: mark test as training-related"
    )
    config.addinivalue_line(
        "markers",
        "inference: mark test as inference-related"
    )


# ============================================================
# Helper Functions
# ============================================================

def generate_timeseries(
    n: int = 100,
    trend: float = 0.001,
    volatility: float = 0.02,
    seed: int = 42,
) -> np.ndarray:
    """Generate synthetic time series data."""
    np.random.seed(seed)
    t = np.arange(n)
    noise = np.random.normal(0, volatility, n)
    seasonal = 0.5 * np.sin(2 * np.pi * t / 50)
    return 100.0 * (1 + trend * t + noise + seasonal)


def create_test_df(
    n: int = 100,
    symbol: str = "AAPL",
) -> pd.DataFrame:
    """Create a simple test DataFrame with OHLCV columns."""
    close = generate_timeseries(n, seed=42)
    high = close * (1 + np.random.uniform(0.005, 0.02, n))
    low = close * (1 - np.random.uniform(0.005, 0.02, n))
    open_price = close * (1 + np.random.uniform(-0.01, 0.01, n))
    volume = np.random.uniform(100000, 1000000, n).astype(int)
    dates = [datetime.now() - timedelta(days=i) for i in range(n)]
    
    return pd.DataFrame({
        'timestamp': dates,
        'symbol': symbol,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })


# ============================================================
# Export fixtures for use in tests
# ============================================================

__all__ = [
    # Config
    'ai_test_config',
    'test_dirs',
    'temp_dir',
    'ai_config_file',
    'ai_config_json',
    
    # Data
    'sample_market_data',
    'sample_returns',
    'sample_features',
    'sample_target',
    'generate_timeseries',
    'create_test_df',
    
    # Models
    'model_registry',
    'test_model_config',
    'test_training_config',
    'mock_model',
    
    # Services
    'prediction_service',
    'inference_engine',
    'feature_engine',
    'trainer',
    
    # Setup
    'setup_logging',
    'pytest_configure',
]

# trading/bots/ai_bot/tests/test_models.py
"""
NEXUS AI TRADING SYSTEM - AI Models Test Suite
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive test suite for AI models used in the trading bot.
Tests include:
    - Model initialization and configuration
    - Model training and validation
    - Inference and prediction
    - Model persistence and loading
    - Ensemble methods
    - Performance metrics
    - Model optimization
    - Distributed training
    - Federated learning
    - Model versioning
"""

import os
import sys
import pytest
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
import json
import logging
import pickle
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trading.bots.ai_bot.tests.fixtures import (
    NEXUS_FIXTURES,
    load_all_fixtures,
    get_test_symbols,
    get_test_timeframes,
    FIXTURES_DIR
)
from trading.bots.ai_bot.models import (
    BaseModel,
    ModelFactory,
    ModelRegistry,
    ModelTrainer,
    ModelInference,
    ModelOptimizer,
    EnsembleModel,
    VotingEnsemble,
    StackingEnsemble,
    LSTMTimeSeries,
    GRUTimeSeries,
    TransformerModel,
    CNNModel,
    XGBoostModel,
    LightGBMModel,
    RandomForestModel,
    NeuralNetwork,
    ModelConfig,
    ModelCheckpoint,
    ModelMetrics,
    DistributedTrainer,
    FederatedLearning,
    HyperparameterOptimizer
)
from trading.bots.ai_bot.config import BotConfig

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test constants
NEXUS_QUANTUM = "NEXUS QUANTUM LTD"
COPYRIGHT = "Copyright © 2026 NEXUS QUANTUM LTD"
CEO = "Dr X..."
TEST_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD']
INPUT_SIZE = 128
HIDDEN_SIZE = 256
OUTPUT_SIZE = 3
BATCH_SIZE = 32
EPOCHS = 10
LEARNING_RATE = 0.001


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
def sample_features():
    """Generate sample features for testing."""
    np.random.seed(42)
    n_samples = 1000
    return np.random.randn(n_samples, INPUT_SIZE)


@pytest.fixture
def sample_labels():
    """Generate sample labels for testing."""
    np.random.seed(42)
    n_samples = 1000
    return np.random.randint(0, OUTPUT_SIZE, n_samples)


@pytest.fixture
def sample_time_series():
    """Generate sample time series data."""
    np.random.seed(42)
    n = 1000
    t = np.linspace(0, 100, n)
    trend = 42000 + t * 10
    cycle = 500 * np.sin(t / 10)
    noise = np.random.normal(0, 100, n)
    return trend + cycle + noise


@pytest.fixture
def model_config():
    """Create model configuration."""
    return {
        'model_type': 'lstm',
        'input_size': INPUT_SIZE,
        'hidden_size': HIDDEN_SIZE,
        'output_size': OUTPUT_SIZE,
        'num_layers': 2,
        'dropout': 0.1,
        'batch_size': BATCH_SIZE,
        'learning_rate': LEARNING_RATE,
        'epochs': EPOCHS,
        'optimizer': 'adamw',
        'loss_function': 'cross_entropy',
        'device': 'cpu',
        'use_gpu': False,
        'seed': 42
    }


@pytest.fixture
def lstm_model(model_config):
    """Create LSTM model for testing."""
    return LSTMTimeSeries(
        input_size=model_config['input_size'],
        hidden_size=model_config['hidden_size'],
        output_size=model_config['output_size'],
        num_layers=model_config['num_layers'],
        dropout=model_config['dropout']
    )


@pytest.fixture
def transformer_model(model_config):
    """Create Transformer model for testing."""
    return TransformerModel(
        input_size=model_config['input_size'],
        hidden_size=model_config['hidden_size'],
        output_size=model_config['output_size'],
        num_layers=model_config['num_layers'],
        num_heads=4,
        dropout=model_config['dropout']
    )


@pytest.fixture
def ensemble_model(model_config):
    """Create ensemble model for testing."""
    models = [
        LSTMTimeSeries(
            input_size=model_config['input_size'],
            hidden_size=model_config['hidden_size'],
            output_size=model_config['output_size'],
            num_layers=2
        ),
        TransformerModel(
            input_size=model_config['input_size'],
            hidden_size=model_config['hidden_size'],
            output_size=model_config['output_size'],
            num_layers=2,
            num_heads=4
        ),
        GRUTimeSeries(
            input_size=model_config['input_size'],
            hidden_size=model_config['hidden_size'],
            output_size=model_config['output_size'],
            num_layers=2
        )
    ]
    return VotingEnsemble(models)


@pytest.fixture
def model_trainer(model_config):
    """Create model trainer for testing."""
    return ModelTrainer(ModelConfig(**model_config))


# =============================================================================
# Base Model Tests
# =============================================================================

class TestBaseModel:
    """Test base model functionality."""

    def test_model_initialization(self):
        """Test model initialization."""
        model = BaseModel()
        assert model is not None
        assert model.metrics is not None

    def test_model_config_validation(self, model_config):
        """Test model configuration validation."""
        config = ModelConfig(**model_config)
        assert config is not None
        assert config.input_size == INPUT_SIZE
        assert config.hidden_size == HIDDEN_SIZE
        assert config.output_size == OUTPUT_SIZE

    def test_model_parameter_count(self, lstm_model):
        """Test model parameter count."""
        params = lstm_model.count_parameters()
        assert params > 0
        logger.info(f"LSTM model parameters: {params:,}")

    def test_model_device_placement(self, lstm_model):
        """Test model device placement."""
        device = lstm_model.get_device()
        assert device in ['cpu', 'cuda']
        assert lstm_model.device == device


# =============================================================================
# LSTM Model Tests
# =============================================================================

class TestLSTMTimeSeries:
    """Test LSTM time series model."""

    def test_lstm_initialization(self, lstm_model):
        """Test LSTM model initialization."""
        assert lstm_model is not None
        assert isinstance(lstm_model, nn.Module)
        assert hasattr(lstm_model, 'lstm')
        assert hasattr(lstm_model, 'fc')

    def test_lstm_forward_pass(self, lstm_model):
        """Test LSTM forward pass."""
        batch_size = 32
        seq_len = 50
        x = torch.randn(batch_size, seq_len, INPUT_SIZE)
        
        output = lstm_model(x)
        assert output is not None
        assert output.shape == (batch_size, OUTPUT_SIZE)

    def test_lstm_training_step(self, lstm_model, sample_features, sample_labels):
        """Test LSTM training step."""
        optimizer = torch.optim.Adam(lstm_model.parameters(), lr=LEARNING_RATE)
        criterion = nn.CrossEntropyLoss()
        
        # Convert to tensors
        x = torch.FloatTensor(sample_features[:BATCH_SIZE])
        y = torch.LongTensor(sample_labels[:BATCH_SIZE])
        
        # Forward pass
        output = lstm_model(x)
        loss = criterion(output, y)
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        assert loss.item() > 0
        assert not torch.isnan(loss)

    def test_lstm_prediction(self, lstm_model, sample_features):
        """Test LSTM prediction."""
        x = torch.FloatTensor(sample_features[:10])
        predictions = lstm_model.predict(x)
        
        assert predictions is not None
        assert predictions.shape == (10, OUTPUT_SIZE)
        assert (predictions >= 0).all() and (predictions <= 1).all()


# =============================================================================
# Transformer Model Tests
# =============================================================================

class TestTransformerModel:
    """Test Transformer model."""

    def test_transformer_initialization(self, transformer_model):
        """Test Transformer model initialization."""
        assert transformer_model is not None
        assert isinstance(transformer_model, nn.Module)
        assert hasattr(transformer_model, 'transformer')
        assert hasattr(transformer_model, 'fc')

    def test_transformer_forward_pass(self, transformer_model):
        """Test Transformer forward pass."""
        batch_size = 32
        seq_len = 50
        x = torch.randn(batch_size, seq_len, INPUT_SIZE)
        
        output = transformer_model(x)
        assert output is not None
        assert output.shape == (batch_size, OUTPUT_SIZE)

    def test_transformer_attention(self, transformer_model):
        """Test Transformer attention mechanism."""
        batch_size = 32
        seq_len = 50
        x = torch.randn(batch_size, seq_len, INPUT_SIZE)
        
        with torch.no_grad():
            output = transformer_model(x)
            assert output is not None
            
            # Test attention weights
            if hasattr(transformer_model, 'get_attention_weights'):
                attn_weights = transformer_model.get_attention_weights(x)
                assert attn_weights is not None


# =============================================================================
# Ensemble Model Tests
# =============================================================================

class TestEnsembleModel:
    """Test ensemble models."""

    def test_ensemble_initialization(self, ensemble_model):
        """Test ensemble model initialization."""
        assert ensemble_model is not None
        assert len(ensemble_model.models) > 1

    def test_voting_ensemble_prediction(self, ensemble_model, sample_features):
        """Test voting ensemble prediction."""
        x = torch.FloatTensor(sample_features[:10])
        predictions = ensemble_model.predict(x)
        
        assert predictions is not None
        assert predictions.shape == (10, OUTPUT_SIZE)

    def test_weighted_ensemble(self, model_config, sample_features):
        """Test weighted ensemble."""
        models = [
            LSTMTimeSeries(
                input_size=model_config['input_size'],
                hidden_size=model_config['hidden_size'],
                output_size=model_config['output_size'],
                num_layers=2
            ) for _ in range(3)
        ]
        
        weights = [0.5, 0.3, 0.2]
        ensemble = VotingEnsemble(models, weights)
        
        x = torch.FloatTensor(sample_features[:10])
        predictions = ensemble.predict(x)
        
        assert predictions is not None
        assert predictions.shape == (10, OUTPUT_SIZE)

    def test_stacking_ensemble(self, model_config, sample_features, sample_labels):
        """Test stacking ensemble."""
        base_models = [
            LSTMTimeSeries(
                input_size=model_config['input_size'],
                hidden_size=model_config['hidden_size'],
                output_size=model_config['output_size'],
                num_layers=2
            ) for _ in range(3)
        ]
        
        # Meta-model (simple linear layer for stacking)
        meta_model = nn.Linear(OUTPUT_SIZE * 3, OUTPUT_SIZE)
        
        ensemble = StackingEnsemble(base_models, meta_model)
        
        x = torch.FloatTensor(sample_features[:10])
        predictions = ensemble.predict(x)
        
        assert predictions is not None
        assert predictions.shape == (10, OUTPUT_SIZE)


# =============================================================================
# Model Training Tests
# =============================================================================

class TestModelTrainer:
    """Test model trainer functionality."""

    def test_trainer_initialization(self, model_trainer):
        """Test model trainer initialization."""
        assert model_trainer is not None
        assert model_trainer.config is not None

    def test_train_model(self, model_trainer, lstm_model, sample_features, sample_labels):
        """Test model training."""
        # Prepare data
        X_train = sample_features[:800]
        y_train = sample_labels[:800]
        X_val = sample_features[800:900]
        y_val = sample_labels[800:900]
        X_test = sample_features[900:]
        y_test = sample_labels[900:]
        
        # Train model
        history = model_trainer.train(
            lstm_model,
            X_train, y_train,
            X_val, y_val,
            epochs=3
        )
        
        assert history is not None
        assert 'train_loss' in history
        assert 'val_loss' in history

    def test_validate_model(self, model_trainer, lstm_model, sample_features, sample_labels):
        """Test model validation."""
        X_test = sample_features[:100]
        y_test = sample_labels[:100]
        
        metrics = model_trainer.validate(lstm_model, X_test, y_test)
        assert metrics is not None
        assert 'accuracy' in metrics
        assert 'precision' in metrics
        assert 'recall' in metrics

    def test_early_stopping(self, model_trainer, lstm_model, sample_features, sample_labels):
        """Test early stopping."""
        X_train = sample_features[:800]
        y_train = sample_labels[:800]
        X_val = sample_features[800:900]
        y_val = sample_labels[800:900]
        
        # Should stop early
        history = model_trainer.train(
            lstm_model,
            X_train, y_train,
            X_val, y_val,
            epochs=20,
            early_stopping_patience=3
        )
        
        assert history is not None
        assert len(history['train_loss']) < 20


# =============================================================================
# Model Inference Tests
# =============================================================================

class TestModelInference:
    """Test model inference functionality."""

    def test_inference_initialization(self, model_config):
        """Test inference initialization."""
        inference = ModelInference(ModelConfig(**model_config))
        assert inference is not None

    def test_batch_prediction(self, lstm_model, sample_features):
        """Test batch prediction."""
        x = torch.FloatTensor(sample_features[:100])
        predictions = lstm_model.predict(x)
        assert predictions is not None
        assert predictions.shape == (100, OUTPUT_SIZE)

    def test_prediction_confidence(self, lstm_model, sample_features):
        """Test prediction confidence."""
        x = torch.FloatTensor(sample_features[:10])
        predictions, confidence = lstm_model.predict_with_confidence(x)
        assert predictions is not None
        assert confidence is not None
        assert 0 <= confidence.mean() <= 1


# =============================================================================
# Model Persistence Tests
# =============================================================================

class TestModelPersistence:
    """Test model persistence functionality."""

    def test_model_save_load(self, lstm_model, sample_features):
        """Test model save and load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save model
            model_path = Path(tmpdir) / 'model.pth'
            torch.save(lstm_model.state_dict(), model_path)
            assert model_path.exists()
            
            # Load model
            loaded_model = LSTMTimeSeries(
                input_size=INPUT_SIZE,
                hidden_size=HIDDEN_SIZE,
                output_size=OUTPUT_SIZE
            )
            loaded_model.load_state_dict(torch.load(model_path))
            
            # Test loaded model
            x = torch.FloatTensor(sample_features[:10])
            output1 = lstm_model(x)
            output2 = loaded_model(x)
            
            # Outputs should be equal
            assert torch.allclose(output1, output2, rtol=1e-5)

    def test_checkpoint_save(self, model_trainer, lstm_model, sample_features, sample_labels):
        """Test model checkpoint saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = ModelCheckpoint(tmpdir)
            
            X_train = sample_features[:800]
            y_train = sample_labels[:800]
            
            # Train and save checkpoints
            history = model_trainer.train(
                lstm_model,
                X_train, y_train,
                epochs=3,
                checkpoint=checkpoint
            )
            
            # Check checkpoints were saved
            checkpoints = list(Path(tmpdir).glob('*.pth'))
            assert len(checkpoints) > 0

    def test_model_serialization(self, lstm_model):
        """Test model serialization."""
        # Serialize model
        serialized = pickle.dumps(lstm_model)
        assert serialized is not None
        
        # Deserialize model
        deserialized = pickle.loads(serialized)
        assert deserialized is not None
        assert isinstance(deserialized, LSTMTimeSeries)


# =============================================================================
# Model Registry Tests
# =============================================================================

class TestModelRegistry:
    """Test model registry functionality."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = ModelRegistry()
        assert registry is not None

    def test_model_registration(self):
        """Test model registration."""
        registry = ModelRegistry()
        
        # Register model
        registry.register('test_model', LSTMTimeSeries)
        assert 'test_model' in registry.get_available_models()

    def test_model_creation(self, model_config):
        """Test model creation from registry."""
        registry = ModelRegistry()
        
        # Create model from config
        model = registry.create_model('lstm', model_config)
        assert model is not None
        assert isinstance(model, LSTMTimeSeries)


# =============================================================================
# Model Optimization Tests
# =============================================================================

class TestModelOptimizer:
    """Test model optimization."""

    def test_optimizer_initialization(self, model_config):
        """Test optimizer initialization."""
        optimizer = ModelOptimizer(ModelConfig(**model_config))
        assert optimizer is not None

    def test_hyperparameter_optimization(self, model_config, sample_features, sample_labels):
        """Test hyperparameter optimization."""
        optimizer = HyperparameterOptimizer(ModelConfig(**model_config))
        
        param_grid = {
            'hidden_size': [128, 256],
            'num_layers': [2, 3],
            'learning_rate': [0.001, 0.01]
        }
        
        # Simple optimization
        best_params = optimizer.optimize(
            sample_features[:500],
            sample_labels[:500],
            param_grid,
            n_trials=2
        )
        
        assert best_params is not None
        assert 'hidden_size' in best_params

    def test_model_pruning(self, lstm_model):
        """Test model pruning."""
        optimizer = ModelOptimizer()
        
        # Prune model
        pruned_model = optimizer.prune_model(lstm_model, amount=0.2)
        assert pruned_model is not None
        
        # Check parameter reduction
        original_params = sum(p.numel() for p in lstm_model.parameters())
        pruned_params = sum(p.numel() for p in pruned_model.parameters())
        assert pruned_params < original_params

    def test_quantization(self, lstm_model, sample_features):
        """Test model quantization."""
        optimizer = ModelOptimizer()
        
        # Quantize model
        x = torch.FloatTensor(sample_features[:10])
        quantized_model = optimizer.quantize_model(lstm_model, x)
        assert quantized_model is not None


# =============================================================================
# Distributed Training Tests
# =============================================================================

class TestDistributedTraining:
    """Test distributed training functionality."""

    def test_distributed_initialization(self, model_config):
        """Test distributed trainer initialization."""
        trainer = DistributedTrainer(ModelConfig(**model_config))
        assert trainer is not None

    def test_distributed_training(self, model_config, sample_features, sample_labels):
        """Test distributed training."""
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")
        
        trainer = DistributedTrainer(ModelConfig(**model_config))
        model = LSTMTimeSeries(INPUT_SIZE, HIDDEN_SIZE, OUTPUT_SIZE)
        
        X_train = sample_features[:800]
        y_train = sample_labels[:800]
        
        # Simulate distributed training
        history = trainer.train_distributed(
            model,
            X_train, y_train,
            world_size=2
        )
        
        assert history is not None


# =============================================================================
# Federated Learning Tests
# =============================================================================

class TestFederatedLearning:
    """Test federated learning functionality."""

    def test_federated_initialization(self, model_config):
        """Test federated learning initialization."""
        fl = FederatedLearning(ModelConfig(**model_config))
        assert fl is not None

    def test_federated_aggregation(self, model_config, sample_features, sample_labels):
        """Test federated aggregation."""
        fl = FederatedLearning(ModelConfig(**model_config))
        
        # Create local models
        local_models = [
            LSTMTimeSeries(INPUT_SIZE, HIDDEN_SIZE, OUTPUT_SIZE)
            for _ in range(3)
        ]
        
        # Train local models
        for i, model in enumerate(local_models):
            start = i * 200
            end = (i + 1) * 200
            X = sample_features[start:end]
            y = sample_labels[start:end]
            
            optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
            X_tensor = torch.FloatTensor(X)
            y_tensor = torch.LongTensor(y)
            
            for _ in range(2):
                optimizer.zero_grad()
                output = model(X_tensor)
                loss = nn.CrossEntropyLoss()(output, y_tensor)
                loss.backward()
                optimizer.step()
        
        # Aggregate models
        global_model = fl.aggregate_models(local_models)
        assert global_model is not None
        assert isinstance(global_model, LSTMTimeSeries)


# =============================================================================
# Model Metrics Tests
# =============================================================================

class TestModelMetrics:
    """Test model metrics calculation."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = ModelMetrics()
        assert metrics is not None

    def test_classification_metrics(self, sample_labels):
        """Test classification metrics."""
        metrics = ModelMetrics()
        
        # Generate predictions
        np.random.seed(42)
        predictions = np.random.randint(0, OUTPUT_SIZE, len(sample_labels))
        
        # Calculate metrics
        results = metrics.calculate_classification_metrics(sample_labels, predictions)
        assert results is not None
        assert 'accuracy' in results
        assert 'precision' in results
        assert 'recall' in results
        assert 'f1_score' in results

    def test_regression_metrics(self):
        """Test regression metrics."""
        metrics = ModelMetrics()
        
        y_true = np.random.randn(100)
        y_pred = y_true + np.random.randn(100) * 0.1
        
        results = metrics.calculate_regression_metrics(y_true, y_pred)
        assert results is not None
        assert 'mse' in results
        assert 'rmse' in results
        assert 'mae' in results
        assert 'r2' in results


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for models."""

    def test_end_to_end_training_pipeline(self, model_config, sample_features, sample_labels):
        """Test end-to-end training pipeline."""
        config = ModelConfig(**model_config)
        trainer = ModelTrainer(config)
        model = LSTMTimeSeries(INPUT_SIZE, HIDDEN_SIZE, OUTPUT_SIZE)
        
        # Split data
        split = int(0.8 * len(sample_features))
        X_train = sample_features[:split]
        y_train = sample_labels[:split]
        X_val = sample_features[split:split+100]
        y_val = sample_labels[split:split+100]
        
        # Train model
        history = trainer.train(
            model,
            X_train, y_train,
            X_val, y_val,
            epochs=3
        )
        
        assert history is not None
        
        # Validate model
        metrics = trainer.validate(model, X_val, y_val)
        assert metrics is not None
        
        # Save model
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / 'model.pth'
            torch.save(model.state_dict(), model_path)
            assert model_path.exists()

    def test_model_ensemble_integration(self, model_config, sample_features, sample_labels):
        """Test model ensemble integration."""
        models = [
            LSTMTimeSeries(INPUT_SIZE, HIDDEN_SIZE, OUTPUT_SIZE),
            TransformerModel(INPUT_SIZE, HIDDEN_SIZE, OUTPUT_SIZE),
            GRUTimeSeries(INPUT_SIZE, HIDDEN_SIZE, OUTPUT_SIZE)
        ]
        
        ensemble = VotingEnsemble(models)
        
        # Train models individually
        for model in models:
            optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
            X = torch.FloatTensor(sample_features[:500])
            y = torch.LongTensor(sample_labels[:500])
            
            for _ in range(2):
                optimizer.zero_grad()
                output = model(X)
                loss = nn.CrossEntropyLoss()(output, y)
                loss.backward()
                optimizer.step()
        
        # Test ensemble prediction
        X_test = torch.FloatTensor(sample_features[900:])
        predictions = ensemble.predict(X_test)
        assert predictions is not None
        assert predictions.shape == (100, OUTPUT_SIZE)


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for models."""

    def test_model_inference_speed(self, lstm_model, sample_features):
        """Test model inference speed."""
        import time
        
        iterations = 100
        x = torch.FloatTensor(sample_features[:10])
        
        start_time = time.time()
        for _ in range(iterations):
            _ = lstm_model(x)
        elapsed = time.time() - start_time
        
        avg_time = elapsed / iterations
        assert avg_time < 0.01  # Less than 10ms per inference
        logger.info(f"Average inference time: {avg_time * 1000:.2f}ms")

    def test_training_speed(self, model_trainer, lstm_model, sample_features, sample_labels):
        """Test training speed."""
        import time
        
        X_train = sample_features[:500]
        y_train = sample_labels[:500]
        
        start_time = time.time()
        history = model_trainer.train(
            lstm_model,
            X_train, y_train,
            epochs=3,
            batch_size=32
        )
        elapsed = time.time() - start_time
        
        assert elapsed < 10  # Should train in less than 10 seconds
        logger.info(f"Training time: {elapsed:.2f}s")


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for models."""

    def test_empty_input(self, lstm_model):
        """Test handling of empty input."""
        x = torch.FloatTensor([])
        with pytest.raises(ValueError):
            lstm_model(x)

    def test_nan_input(self, lstm_model):
        """Test handling of NaN input."""
        x = torch.FloatTensor([[np.nan] * INPUT_SIZE])
        with pytest.raises(ValueError):
            lstm_model(x)

    def test_invalid_shapes(self, lstm_model):
        """Test handling of invalid tensor shapes."""
        x = torch.FloatTensor(np.random.randn(10, 10))
        with pytest.raises(ValueError):
            lstm_model(x)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    # Run pytest programmatically
    print("=" * 80)
    print("NEXUS AI TRADING SYSTEM - AI Models Test Suite")
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
    print("✅ AI Models Test Suite Complete")
    print("=" * 80)

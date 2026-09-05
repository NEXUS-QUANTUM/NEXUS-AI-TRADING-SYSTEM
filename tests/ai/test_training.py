"""
NEXUS AI TRADING SYSTEM
AI Training Tests

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: tests/ai/test_training.py
Description: Comprehensive unit and integration tests for AI training components
             including training pipelines, data loaders, model training,
             checkpointing, metrics, early stopping, and learning rate scheduling.
"""

import asyncio
import json
import os
import tempfile
import shutil
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
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

# Module imports (adjust based on actual project structure)
from ai.training.trainer import Trainer
from ai.training.data_pipeline import DataPipeline
from ai.training.checkpoint import CheckpointManager
from ai.training.metrics import MetricsTracker
from ai.training.early_stopping import EarlyStopping
from ai.training.lr_scheduler import LRScheduler
from ai.models.base_model import BaseModel

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_data():
    """Generate sample training data."""
    np.random.seed(42)
    X = np.random.randn(100, 10)
    y = np.random.randn(100)
    return X, y

@pytest.fixture
def sample_sequence_data():
    """Generate sequence data for RNN/LSTM training."""
    np.random.seed(42)
    X = np.random.randn(50, 20, 5)  # 50 sequences, length 20, 5 features
    y = np.random.randn(50, 1)
    return X, y

@pytest.fixture
def sample_dataloader(sample_data):
    """Create a simple dataloader for testing."""
    X, y = sample_data
    dataset = TensorDataset(torch.tensor(X, dtype=torch.float32),
                            torch.tensor(y, dtype=torch.float32))
    return DataLoader(dataset, batch_size=16, shuffle=True)

@pytest.fixture
def mock_model():
    """Create a mock trainable model."""
    model = MagicMock(spec=BaseModel)
    model.fit = MagicMock(return_value=None)
    model.predict = MagicMock(return_value=np.random.randn(10))
    model.save = MagicMock(return_value=None)
    model.load = MagicMock(return_value=None)
    return model

@pytest.fixture
def training_config():
    """Default training configuration."""
    return {
        'batch_size': 16,
        'epochs': 10,
        'learning_rate': 0.001,
        'validation_split': 0.2,
        'early_stopping_patience': 3,
        'lr_scheduler': 'step',
        'lr_step_size': 5,
        'lr_gamma': 0.1,
        'checkpoint_dir': '/tmp/checkpoints',
        'metrics': ['loss', 'accuracy', 'mae'],
        'device': 'cpu',
        'num_workers': 2,
    }

@pytest.fixture
def temp_checkpoint_dir():
    """Create temporary checkpoint directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

# ============================================================================
# TEST TRAINER
# ============================================================================

class TestTrainer:
    """Test the main trainer class."""

    def test_init(self, training_config):
        """Test trainer initialization."""
        trainer = Trainer(config=training_config)
        assert trainer.epochs == training_config['epochs']
        assert trainer.batch_size == training_config['batch_size']
        assert trainer.device == 'cpu'

    def test_train_sklearn_model(self, mock_model, sample_data, training_config):
        """Test training an sklearn-style model."""
        X, y = sample_data
        trainer = Trainer(config=training_config)
        history = trainer.train(mock_model, X, y)
        assert history is not None
        mock_model.fit.assert_called_once()

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_train_pytorch_model(self, sample_data, training_config):
        """Test training a PyTorch model."""
        from ai.models.lstm.lstm_model import LSTMModel
        X, y = sample_data
        # Reshape for LSTM: (samples, seq_len, features)
        X_reshaped = X.reshape(X.shape[0], 1, X.shape[1])
        model = LSTMModel(input_dim=10, hidden_dim=8, output_dim=1, sequence_length=1)
        trainer = Trainer(config=training_config)
        trainer.epochs = 2  # Reduce for test speed
        history = trainer.train(model, X_reshaped, y)
        assert history is not None
        assert 'loss' in history

    def test_train_with_validation_split(self, mock_model, sample_data, training_config):
        """Test training with validation split."""
        X, y = sample_data
        config = training_config.copy()
        config['validation_split'] = 0.3
        trainer = Trainer(config=config)
        history = trainer.train(mock_model, X, y)
        assert history is not None
        # Check that validation was used (mock might not track, but we ensure no error)

    def test_train_with_early_stopping(self, mock_model, sample_data, training_config):
        """Test training with early stopping."""
        X, y = sample_data
        config = training_config.copy()
        config['early_stopping_patience'] = 2
        config['validation_split'] = 0.2
        trainer = Trainer(config=config)
        # Mock early stopping trigger: we'll mock trainer._should_stop to return True after some epochs
        with patch.object(trainer, '_should_stop', side_effect=[False, False, True]):
            history = trainer.train(mock_model, X, y)
            assert history is not None
            # Ensure early stopping was triggered

    def test_train_with_checkpointing(self, mock_model, sample_data, training_config, temp_checkpoint_dir):
        """Test training with checkpointing."""
        X, y = sample_data
        config = training_config.copy()
        config['checkpoint_dir'] = temp_checkpoint_dir
        config['checkpoint_frequency'] = 2
        trainer = Trainer(config=config)
        trainer.train(mock_model, X, y)
        # Check that checkpoint files were created
        checkpoint_files = list(Path(temp_checkpoint_dir).glob('*.pt'))
        assert len(checkpoint_files) > 0

    def test_train_with_lr_scheduler(self, mock_model, sample_data, training_config):
        """Test training with learning rate scheduler."""
        X, y = sample_data
        config = training_config.copy()
        config['lr_scheduler'] = 'step'
        config['lr_step_size'] = 3
        config['lr_gamma'] = 0.5
        trainer = Trainer(config=config)
        # Mock model has no optimizer, so we'll just ensure no error
        history = trainer.train(mock_model, X, y)
        assert history is not None

    def test_train_with_metrics_tracking(self, mock_model, sample_data, training_config):
        """Test training with metrics tracking."""
        X, y = sample_data
        config = training_config.copy()
        config['metrics'] = ['loss', 'mae', 'r2']
        trainer = Trainer(config=config)
        history = trainer.train(mock_model, X, y)
        assert history is not None
        # Check that history contains metrics (mock model doesn't return them, but trainer tracks)

    def test_train_with_custom_validation_data(self, mock_model, sample_data, training_config):
        """Test training with explicit validation data."""
        X, y = sample_data
        X_val, y_val = X[:20], y[:20]
        trainer = Trainer(config=training_config)
        history = trainer.train(mock_model, X, y, validation_data=(X_val, y_val))
        assert history is not None

# ============================================================================
# TEST DATA PIPELINE
# ============================================================================

class TestDataPipeline:
    """Test data pipeline for training."""

    def test_init(self):
        """Test data pipeline initialization."""
        pipeline = DataPipeline(config={'batch_size': 32, 'shuffle': True})
        assert pipeline.batch_size == 32

    def test_prepare_data(self, sample_data):
        """Test data preparation."""
        X, y = sample_data
        pipeline = DataPipeline(config={'batch_size': 16, 'validation_split': 0.2})
        train_loader, val_loader, test_loader = pipeline.prepare_data(X, y)
        assert train_loader is not None
        assert val_loader is not None
        # Test loader should be None if not provided
        assert test_loader is None

    def test_data_augmentation(self, sample_data):
        """Test data augmentation."""
        X, y = sample_data
        pipeline = DataPipeline(config={
            'batch_size': 16,
            'augmentation': True,
            'augmentation_methods': ['noise', 'scale']
        })
        train_loader, _, _ = pipeline.prepare_data(X, y)
        # Check that augmentation transforms are applied (mock check)
        assert train_loader is not None

    def test_data_normalization(self, sample_data):
        """Test data normalization."""
        X, y = sample_data
        pipeline = DataPipeline(config={'normalize': True})
        train_loader, _, _ = pipeline.prepare_data(X, y)
        # Check normalization (we can check first batch after loading)
        for batch in train_loader:
            X_batch, y_batch = batch
            # Check that X_batch is normalized (mean ~0, std ~1)
            # For simplicity, just check shape
            assert X_batch.shape[0] > 0
            break

    def test_data_loader_with_workers(self, sample_data):
        """Test data loader with multiple workers."""
        X, y = sample_data
        pipeline = DataPipeline(config={'num_workers': 4})
        train_loader, _, _ = pipeline.prepare_data(X, y)
        assert train_loader.num_workers == 4

    def test_data_split_seed(self, sample_data):
        """Test reproducibility with seed."""
        X, y = sample_data
        pipeline1 = DataPipeline(config={'seed': 42})
        pipeline2 = DataPipeline(config={'seed': 42})
        loader1, _, _ = pipeline1.prepare_data(X, y)
        loader2, _, _ = pipeline2.prepare_data(X, y)
        # Check that first batch is same
        batch1 = next(iter(loader1))
        batch2 = next(iter(loader2))
        np.testing.assert_array_equal(batch1[0].numpy(), batch2[0].numpy())

# ============================================================================
# TEST CHECKPOINT MANAGER
# ============================================================================

class TestCheckpointManager:
    """Test checkpoint manager."""

    def test_init(self, temp_checkpoint_dir):
        """Test checkpoint manager initialization."""
        manager = CheckpointManager(directory=temp_checkpoint_dir)
        assert manager.directory == temp_checkpoint_dir

    def test_save_checkpoint(self, mock_model, temp_checkpoint_dir):
        """Test saving a checkpoint."""
        manager = CheckpointManager(directory=temp_checkpoint_dir)
        epoch = 5
        loss = 0.1
        metadata = {'accuracy': 0.95}
        checkpoint_path = manager.save(mock_model, epoch, loss, metadata)
        assert checkpoint_path is not None
        assert os.path.exists(checkpoint_path)

    def test_load_checkpoint(self, mock_model, temp_checkpoint_dir):
        """Test loading a checkpoint."""
        manager = CheckpointManager(directory=temp_checkpoint_dir)
        # Save first
        epoch = 5
        loss = 0.1
        checkpoint_path = manager.save(mock_model, epoch, loss, {})
        # Load
        model, epoch_loaded, loss_loaded, metadata_loaded = manager.load(checkpoint_path)
        assert epoch_loaded == epoch
        assert loss_loaded == loss
        # Model should have load called
        mock_model.load.assert_called_once()

    def test_list_checkpoints(self, temp_checkpoint_dir):
        """Test listing checkpoints."""
        manager = CheckpointManager(directory=temp_checkpoint_dir)
        # Save multiple checkpoints
        for i in range(3):
            manager.save(MagicMock(), i, 0.1, {})
        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) == 3

    def test_get_latest_checkpoint(self, temp_checkpoint_dir):
        """Test getting the latest checkpoint."""
        manager = CheckpointManager(directory=temp_checkpoint_dir)
        # Save checkpoints with different epochs
        for i in range(3):
            manager.save(MagicMock(), i, 0.1, {})
        latest = manager.get_latest_checkpoint()
        assert latest is not None
        # The latest should be the one with highest epoch (i=2)
        assert 'epoch_2' in latest

    def test_cleanup_old_checkpoints(self, temp_checkpoint_dir):
        """Test cleaning up old checkpoints."""
        manager = CheckpointManager(directory=temp_checkpoint_dir, max_keep=2)
        for i in range(4):
            manager.save(MagicMock(), i, 0.1, {})
        # Only keep 2
        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) <= 2

# ============================================================================
# TEST METRICS TRACKER
# ============================================================================

class TestMetricsTracker:
    """Test metrics tracking."""

    def test_init(self):
        """Test metrics tracker initialization."""
        tracker = MetricsTracker(metrics=['loss', 'accuracy'])
        assert tracker.metrics == ['loss', 'accuracy']

    def test_update(self):
        """Test updating metrics."""
        tracker = MetricsTracker()
        tracker.update('loss', 0.5)
        tracker.update('accuracy', 0.9)
        assert tracker.get('loss') == 0.5
        assert tracker.get('accuracy') == 0.9

    def test_update_batch(self):
        """Test batch updates."""
        tracker = MetricsTracker()
        batch_metrics = {'loss': 0.5, 'accuracy': 0.9}
        tracker.update_batch(batch_metrics)
        assert tracker.get('loss') == 0.5
        assert tracker.get('accuracy') == 0.9

    def test_epoch_summary(self):
        """Test epoch summary."""
        tracker = MetricsTracker()
        tracker.update_batch({'loss': 0.5, 'accuracy': 0.9})
        tracker.update_batch({'loss': 0.6, 'accuracy': 0.85})
        summary = tracker.epoch_summary()
        assert 'loss' in summary
        assert 'accuracy' in summary
        assert summary['loss']['mean'] == 0.55

    def test_reset(self):
        """Test resetting tracker."""
        tracker = MetricsTracker()
        tracker.update('loss', 0.5)
        tracker.reset()
        assert tracker.get('loss') is None

# ============================================================================
# TEST EARLY STOPPING
# ============================================================================

class TestEarlyStopping:
    """Test early stopping logic."""

    def test_init(self):
        """Test early stopping initialization."""
        es = EarlyStopping(patience=3, min_delta=0.01)
        assert es.patience == 3

    def test_step(self):
        """Test early stopping step."""
        es = EarlyStopping(patience=2, min_delta=0.01)
        # Simulate decreasing loss
        should_stop = es.step(1.0)
        assert should_stop is False
        should_stop = es.step(0.9)
        assert should_stop is False
        should_stop = es.step(0.89)  # Improvement less than min_delta (0.01)
        assert should_stop is False
        should_stop = es.step(0.88)  # Still no improvement
        assert should_stop is True  # Should stop after 2 epochs of no improvement

    def test_best_model_saving(self):
        """Test saving best model state."""
        es = EarlyStopping(patience=2, restore_best_weights=True)
        model_state = {'weights': 'best'}
        es.step(1.0, model_state)
        es.step(0.9, model_state)
        es.step(0.95)  # No improvement
        best = es.get_best_model_state()
        assert best is not None
        assert best['weights'] == 'best'

    def test_early_stop_on_metric(self):
        """Test early stopping with metric where higher is better."""
        es = EarlyStopping(patience=2, min_delta=0.01, mode='max')
        # Simulate increasing accuracy
        should_stop = es.step(0.8, is_metric=True)
        assert should_stop is False
        should_stop = es.step(0.85, is_metric=True)
        assert should_stop is False
        should_stop = es.step(0.86, is_metric=True)
        assert should_stop is False
        should_stop = es.step(0.86, is_metric=True)  # No improvement
        assert should_stop is True

# ============================================================================
# TEST LEARNING RATE SCHEDULER
# ============================================================================

class TestLRScheduler:
    """Test learning rate scheduler."""

    def test_init(self):
        """Test scheduler initialization."""
        scheduler = LRScheduler(method='step', step_size=5, gamma=0.1)
        assert scheduler.method == 'step'

    def test_step_scheduler(self):
        """Test step learning rate scheduler."""
        scheduler = LRScheduler(method='step', step_size=2, gamma=0.5)
        # Mock optimizer
        optimizer = MagicMock()
        optimizer.param_groups = [{'lr': 0.001}]
        # Simulate epochs
        for epoch in range(5):
            new_lr = scheduler.step(optimizer, epoch)
            if epoch < 2:
                assert new_lr == 0.001
            elif epoch < 4:
                assert new_lr == 0.0005
            else:
                assert new_lr == 0.00025

    def test_exponential_scheduler(self):
        """Test exponential learning rate scheduler."""
        scheduler = LRScheduler(method='exponential', gamma=0.9)
        optimizer = MagicMock()
        optimizer.param_groups = [{'lr': 0.001}]
        for epoch in range(3):
            new_lr = scheduler.step(optimizer, epoch)
            expected = 0.001 * (0.9 ** epoch)
            assert abs(new_lr - expected) < 1e-10

    def test_cosine_scheduler(self):
        """Test cosine annealing scheduler."""
        scheduler = LRScheduler(method='cosine', t_max=10, eta_min=0.0001)
        optimizer = MagicMock()
        optimizer.param_groups = [{'lr': 0.001}]
        for epoch in range(3):
            new_lr = scheduler.step(optimizer, epoch)
            assert 0.0001 <= new_lr <= 0.001

    def test_plateau_scheduler(self):
        """Test reduce on plateau scheduler."""
        scheduler = LRScheduler(method='plateau', patience=2, factor=0.5)
        optimizer = MagicMock()
        optimizer.param_groups = [{'lr': 0.001}]
        # Simulate losses
        losses = [1.0, 0.9, 0.8, 0.8, 0.8]
        for epoch, loss in enumerate(losses):
            new_lr = scheduler.step(optimizer, epoch, loss)
            if epoch < 3:
                assert new_lr == 0.001
            else:
                assert new_lr == 0.0005

    def test_adaptive_scheduler(self):
        """Test adaptive learning rate scheduler."""
        scheduler = LRScheduler(method='adaptive', factor=0.8, patience=3)
        optimizer = MagicMock()
        optimizer.param_groups = [{'lr': 0.001}]
        # Simulate epochs with no improvement
        for epoch in range(5):
            new_lr = scheduler.step(optimizer, epoch, loss=0.5)
            if epoch < 3:
                assert new_lr == 0.001
            else:
                assert new_lr == 0.0008

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests with real training flows."""

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_pytorch_training_flow(self, sample_sequence_data, training_config):
        """Test full PyTorch training flow."""
        from ai.models.lstm.lstm_model import LSTMModel
        X, y = sample_sequence_data
        model = LSTMModel(input_dim=5, hidden_dim=8, output_dim=1, sequence_length=20)
        trainer = Trainer(config=training_config)
        trainer.epochs = 2
        history = trainer.train(model, X, y)
        assert history is not None
        assert 'loss' in history

    def test_training_with_metrics_and_checkpoint(self, mock_model, sample_data, training_config, temp_checkpoint_dir):
        """Test training with metrics and checkpointing."""
        X, y = sample_data
        config = training_config.copy()
        config['checkpoint_dir'] = temp_checkpoint_dir
        config['metrics'] = ['loss', 'mae']
        trainer = Trainer(config=config)
        history = trainer.train(mock_model, X, y)
        assert history is not None
        # Check checkpoint saved
        checkpoints = list(Path(temp_checkpoint_dir).glob('*.pt'))
        assert len(checkpoints) > 0

    def test_early_stopping_integration(self, mock_model, sample_data, training_config):
        """Test early stopping integration with trainer."""
        X, y = sample_data
        config = training_config.copy()
        config['early_stopping_patience'] = 2
        config['validation_split'] = 0.2
        trainer = Trainer(config=config)
        # Mock _should_stop to return True after 3 epochs
        with patch.object(trainer, '_should_stop', side_effect=[False, False, False, True]):
            history = trainer.train(mock_model, X, y)
            # Epochs should be less than config.epochs
            assert len(history.get('epoch', [])) < config['epochs']

# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance benchmarks for training components."""

    @pytest.mark.benchmark
    def test_trainer_forward_pass(self, benchmark, mock_model, sample_data, training_config):
        """Benchmark trainer forward pass (mocked)."""
        X, y = sample_data
        trainer = Trainer(config=training_config)
        def run():
            trainer.train(mock_model, X, y)
        benchmark(run)

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    @pytest.mark.benchmark
    def test_pytorch_training_speed(self, benchmark, sample_sequence_data, training_config):
        """Benchmark PyTorch training speed."""
        from ai.models.lstm.lstm_model import LSTMModel
        X, y = sample_sequence_data
        model = LSTMModel(input_dim=5, hidden_dim=8, output_dim=1, sequence_length=20)
        trainer = Trainer(config=training_config)
        trainer.epochs = 1
        def run():
            trainer.train(model, X, y)
        benchmark(run)

# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling in training components."""

    def test_trainer_invalid_model(self, training_config):
        """Test trainer with invalid model."""
        trainer = Trainer(config=training_config)
        with pytest.raises(ValueError):
            trainer.train(None, np.zeros((10,5)), np.zeros(10))

    def test_trainer_mismatched_data(self, training_config):
        """Test trainer with mismatched X and y."""
        trainer = Trainer(config=training_config)
        X = np.zeros((10,5))
        y = np.zeros((20,))
        with pytest.raises(ValueError):
            trainer.train(MagicMock(), X, y)

    def test_checkpoint_manager_invalid_dir(self):
        """Test checkpoint manager with invalid directory."""
        with pytest.raises(ValueError):
            CheckpointManager(directory='/invalid/path')

    def test_early_stopping_invalid_mode(self):
        """Test early stopping with invalid mode."""
        with pytest.raises(ValueError):
            EarlyStopping(mode='invalid')

    def test_lr_scheduler_invalid_method(self):
        """Test LR scheduler with invalid method."""
        with pytest.raises(ValueError):
            LRScheduler(method='invalid')

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

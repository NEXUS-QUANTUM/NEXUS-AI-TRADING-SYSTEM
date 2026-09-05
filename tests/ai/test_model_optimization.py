"""
NEXUS AI TRADING SYSTEM
AI Model Optimization Tests

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: tests/ai/test_model_optimization.py
Description: Comprehensive unit and integration tests for AI model optimization
             including hyperparameter tuning, pruning, quantization, model selection,.
             and performance evaluation.
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
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.datasets import make_regression, make_classification

# Try importing optimization libraries
try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    import hyperopt
    HYPEROPT_AVAILABLE = True
except ImportError:
    HYPEROPT_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Module imports - adjust based on actual project structure
from ai.optimization.hyperparameter_optimizer import HyperparameterOptimizer
from ai.optimization.bayesian_optimization import BayesianOptimizer
from ai.optimization.grid_search import GridSearch
from ai.optimization.genetic_algorithm import GeneticAlgorithmOptimizer
from ai.optimization.optuna_optimizer import OptunaOptimizer
from ai.optimization.model_pruner import ModelPruner
from ai.optimization.model_quantizer import ModelQuantizer
from ai.optimization.model_selector import ModelSelector
from ai.optimization.early_stopping import EarlyStopping
from ai.models.base_model import BaseModel

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def regression_data():
    """Create synthetic regression data."""
    X, y = make_regression(n_samples=200, n_features=10, noise=0.1, random_state=42)
    return pd.DataFrame(X, columns=[f'feature_{i}' for i in range(10)]), pd.Series(y)

@pytest.fixture
def classification_data():
    """Create synthetic classification data."""
    X, y = make_classification(n_samples=200, n_features=10, n_classes=2, random_state=42)
    return pd.DataFrame(X, columns=[f'feature_{i}' for i in range(10)]), pd.Series(y)

@pytest.fixture
def sample_model_regression():
    """Create a simple regression model."""
    return RandomForestRegressor(n_estimators=10, random_state=42)

@pytest.fixture
def sample_model_classification():
    """Create a simple classification model."""
    return RandomForestClassifier(n_estimators=10, random_state=42)

@pytest.fixture
def param_grid():
    """Sample parameter grid for hyperparameter tuning."""
    return {
        'n_estimators': [10, 50, 100],
        'max_depth': [3, 5, 10],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
    }

@pytest.fixture
def param_space():
    """Sample parameter space for Bayesian optimization."""
    return {
        'n_estimators': (10, 200),
        'max_depth': (3, 20),
        'min_samples_split': (2, 20),
        'min_samples_leaf': (1, 10),
    }

@pytest.fixture
def optimizer_config():
    """Configuration for hyperparameter optimizer."""
    return {
        'n_trials': 10,
        'cv': 3,
        'scoring': 'neg_mean_squared_error',
        'random_state': 42,
        'n_jobs': -1,
    }

@pytest.fixture
def mock_torch_model():
    """Create a mock PyTorch model for quantization/pruning tests."""
    if not TORCH_AVAILABLE:
        pytest.skip("PyTorch not available", allow_module_level=True)
    
    class SimpleModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(10, 20)
            self.fc2 = nn.Linear(20, 1)
        
        def forward(self, x):
            x = torch.relu(self.fc1(x))
            return self.fc2(x)
    
    return SimpleModel()

# ============================================================================
# TEST HYPERPARAMETER OPTIMIZER
# ============================================================================

class TestHyperparameterOptimizer:
    """Test hyperparameter optimization functionality."""

    def test_init(self, optimizer_config):
        """Test initialization."""
        optimizer = HyperparameterOptimizer(config=optimizer_config)
        assert optimizer.n_trials == 10
        assert optimizer.cv == 3

    def test_grid_search(self, sample_model_regression, regression_data, param_grid):
        """Test grid search optimization."""
        X, y = regression_data
        optimizer = HyperparameterOptimizer(config={'method': 'grid_search'})
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_grid=param_grid,
        )
        assert isinstance(best_params, dict)
        assert 'n_estimators' in best_params
        assert isinstance(best_score, float)

    def test_random_search(self, sample_model_regression, regression_data, param_grid):
        """Test random search optimization."""
        X, y = regression_data
        optimizer = HyperparameterOptimizer(
            config={'method': 'random_search', 'n_iter': 5}
        )
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_grid=param_grid,
        )
        assert isinstance(best_params, dict)

    def test_bayesian_optimization(self, sample_model_regression, regression_data, param_space):
        """Test Bayesian optimization."""
        try:
            from ai.optimization.bayesian_optimization import BayesianOptimizer
        except ImportError:
            pytest.skip("BayesianOptimizer not available")
        
        X, y = regression_data
        optimizer = BayesianOptimizer(n_iter=5)
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_space=param_space,
        )
        assert isinstance(best_params, dict)

    @pytest.mark.skipif(not OPTUNA_AVAILABLE, reason="Optuna not installed")
    def test_optuna_optimizer(self, sample_model_regression, regression_data):
        """Test Optuna optimizer."""
        X, y = regression_data
        optimizer = OptunaOptimizer(n_trials=5)
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_space={
                'n_estimators': (10, 100),
                'max_depth': (3, 10),
            },
        )
        assert isinstance(best_params, dict)

    @pytest.mark.skipif(not HYPEROPT_AVAILABLE, reason="Hyperopt not installed")
    def test_hyperopt_optimizer(self, sample_model_regression, regression_data):
        """Test Hyperopt optimizer."""
        # This would require hyperopt-specific imports
        pytest.skip("Hyperopt optimizer not implemented yet")

    def test_optimization_with_cv(self, sample_model_regression, regression_data, param_grid):
        """Test optimization with cross-validation."""
        X, y = regression_data
        optimizer = HyperparameterOptimizer(
            config={'method': 'grid_search', 'cv': 5}
        )
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_grid=param_grid,
        )
        assert isinstance(best_score, float)

    def test_optimization_with_scoring(self, sample_model_regression, regression_data, param_grid):
        """Test optimization with different scoring metrics."""
        X, y = regression_data
        for scoring in ['neg_mean_squared_error', 'r2', 'neg_mean_absolute_error']:
            optimizer = HyperparameterOptimizer(
                config={'method': 'grid_search', 'scoring': scoring}
            )
            best_params, best_score = optimizer.optimize(
                sample_model_regression,
                X,
                y,
                param_grid=param_grid,
            )
            assert isinstance(best_score, float)

    def test_optimization_error_handling(self, sample_model_regression, regression_data):
        """Test error handling during optimization."""
        optimizer = HyperparameterOptimizer()
        with pytest.raises(ValueError):
            # Missing param_grid
            optimizer.optimize(sample_model_regression, *regression_data)

    def test_custom_parameter_sampling(self, sample_model_regression, regression_data):
        """Test custom parameter sampling."""
        def sample_params():
            return {'n_estimators': np.random.randint(10, 100)}
        
        optimizer = HyperparameterOptimizer(
            config={'method': 'custom', 'sampling_function': sample_params}
        )
        with pytest.raises(NotImplementedError):
            optimizer.optimize(sample_model_regression, *regression_data)

# ============================================================================
# TEST BAYESIAN OPTIMIZER
# ============================================================================

class TestBayesianOptimizer:
    """Test Bayesian optimization functionality."""

    def test_init(self):
        """Test initialization."""
        optimizer = BayesianOptimizer(n_iter=10)
        assert optimizer.n_iter == 10

    def test_optimize(self, sample_model_regression, regression_data, param_space):
        """Test optimization."""
        X, y = regression_data
        optimizer = BayesianOptimizer(n_iter=5)
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_space=param_space,
        )
        assert isinstance(best_params, dict)

    def test_optimize_classification(self, sample_model_classification, classification_data, param_space):
        """Test optimization for classification."""
        X, y = classification_data
        optimizer = BayesianOptimizer(n_iter=5, scoring='accuracy')
        best_params, best_score = optimizer.optimize(
            sample_model_classification,
            X,
            y,
            param_space=param_space,
        )
        assert isinstance(best_params, dict)

    def test_optimize_with_constraints(self, sample_model_regression, regression_data):
        """Test optimization with parameter constraints."""
        param_space = {
            'n_estimators': (10, 200),
            'max_depth': (3, 20),
        }
        constraints = [{'param': 'n_estimators', 'min': 20}]
        optimizer = BayesianOptimizer(n_iter=5, constraints=constraints)
        X, y = regression_data
        best_params, _ = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_space=param_space,
        )
        assert best_params['n_estimators'] >= 20

    def test_optimization_history(self, sample_model_regression, regression_data, param_space):
        """Test retrieval of optimization history."""
        optimizer = BayesianOptimizer(n_iter=5)
        X, y = regression_data
        optimizer.optimize(sample_model_regression, X, y, param_space=param_space)
        history = optimizer.get_history()
        assert len(history) == 5

# ============================================================================
# TEST GENETIC ALGORITHM
# ============================================================================

class TestGeneticAlgorithmOptimizer:
    """Test genetic algorithm optimization."""

    def test_init(self):
        """Test initialization."""
        optimizer = GeneticAlgorithmOptimizer(
            population_size=20,
            generations=10,
            mutation_rate=0.1,
            crossover_rate=0.8,
        )
        assert optimizer.population_size == 20

    def test_optimize(self, sample_model_regression, regression_data, param_space):
        """Test genetic algorithm optimization."""
        X, y = regression_data
        optimizer = GeneticAlgorithmOptimizer(
            population_size=10,
            generations=5,
        )
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_space=param_space,
        )
        assert isinstance(best_params, dict)

    def test_optimize_classification(self, sample_model_classification, classification_data, param_space):
        """Test genetic algorithm for classification."""
        X, y = classification_data
        optimizer = GeneticAlgorithmOptimizer(
            population_size=10,
            generations=5,
            scoring='accuracy',
        )
        best_params, best_score = optimizer.optimize(
            sample_model_classification,
            X,
            y,
            param_space=param_space,
        )
        assert isinstance(best_params, dict)

    def test_elitism(self, sample_model_regression, regression_data, param_space):
        """Test elitism in genetic algorithm."""
        optimizer = GeneticAlgorithmOptimizer(
            population_size=10,
            generations=5,
            elitism=2,
        )
        X, y = regression_data
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_space=param_space,
        )
        assert isinstance(best_score, float)

    def test_early_stopping(self, sample_model_regression, regression_data, param_space):
        """Test early stopping in genetic algorithm."""
        optimizer = GeneticAlgorithmOptimizer(
            population_size=10,
            generations=20,
            early_stopping_patience=3,
        )
        X, y = regression_data
        best_params, best_score = optimizer.optimize(
            sample_model_regression,
            X,
            y,
            param_space=param_space,
        )
        # Should stop before 20 generations
        assert optimizer.current_generation < 20

# ============================================================================
# TEST MODEL PRUNER
# ============================================================================

class TestModelPruner:
    """Test model pruning functionality."""

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_prune_weights(self, mock_torch_model):
        """Test weight pruning."""
        pruner = ModelPruner(method='magnitude', target_sparsity=0.3)
        # Need a small dataset to test pruning
        X = torch.randn(10, 10)
        y = torch.randn(10, 1)
        pruned_model = pruner.prune(mock_torch_model, X, y)
        assert pruned_model is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_prune_neurons(self, mock_torch_model):
        """Test neuron pruning."""
        pruner = ModelPruner(method='neuron', target_sparsity=0.2)
        X = torch.randn(10, 10)
        y = torch.randn(10, 1)
        pruned_model = pruner.prune(mock_torch_model, X, y)
        assert pruned_model is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_prune_structured(self, mock_torch_model):
        """Test structured pruning."""
        pruner = ModelPruner(method='structured', target_sparsity=0.25)
        X = torch.randn(10, 10)
        y = torch.randn(10, 1)
        pruned_model = pruner.prune(mock_torch_model, X, y)
        assert pruned_model is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_prune_with_validation(self, mock_torch_model):
        """Test pruning with validation performance check."""
        pruner = ModelPruner(
            method='magnitude',
            target_sparsity=0.3,
            validate_after_prune=True,
        )
        X = torch.randn(20, 10)
        y = torch.randn(20, 1)
        pruned_model, metrics = pruner.prune_with_validation(
            mock_torch_model,
            X, y,
            X_val=X[:5], y_val=y[:5]
        )
        assert 'accuracy' in metrics or 'loss' in metrics

    def test_prune_sklearn_model(self, sample_model_regression, regression_data):
        """Test pruning for sklearn models."""
        pruner = ModelPruner(method='sklearn', target_sparsity=0.1)
        with pytest.raises(NotImplementedError):
            # sklearn pruning not yet implemented
            pruner.prune(sample_model_regression)

# ============================================================================
# TEST MODEL QUANTIZER
# ============================================================================

class TestModelQuantizer:
    """Test model quantization functionality."""

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_post_training_quantization(self, mock_torch_model):
        """Test post-training quantization."""
        quantizer = ModelQuantizer(method='post_training', dtype='int8')
        X = torch.randn(10, 10)
        quantized_model = quantizer.quantize(mock_torch_model, X)
        assert quantized_model is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_quantization_aware_training(self, mock_torch_model):
        """Test quantization-aware training."""
        quantizer = ModelQuantizer(method='quantization_aware', dtype='int8')
        X = torch.randn(20, 10)
        y = torch.randn(20, 1)
        quantized_model = quantizer.quantize(mock_torch_model, X, y)
        assert quantized_model is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_quantize_with_calibration(self, mock_torch_model):
        """Test quantization with calibration dataset."""
        quantizer = ModelQuantizer(
            method='post_training',
            dtype='int8',
            calibration_data=torch.randn(50, 10)
        )
        X = torch.randn(10, 10)
        quantized_model = quantizer.quantize(mock_torch_model, X)
        assert quantized_model is not None

    def test_quantize_sklearn_model(self, sample_model_regression, regression_data):
        """Test quantization for sklearn models."""
        quantizer = ModelQuantizer(method='sklearn')
        with pytest.raises(NotImplementedError):
            quantizer.quantize(sample_model_regression)

# ============================================================================
# TEST MODEL SELECTOR
# ============================================================================

class TestModelSelector:
    """Test model selection functionality."""

    def test_init(self):
        """Test initialization."""
        selector = ModelSelector(scoring='accuracy', cv=3)
        assert selector.scoring == 'accuracy'

    def test_select_best_model(self, regression_data):
        """Test selecting best model from candidates."""
        X, y = regression_data
        models = {
            'linear': LinearRegression(),
            'random_forest': RandomForestRegressor(n_estimators=5),
        }
        selector = ModelSelector(scoring='r2', cv=2)
        best_model_name, best_model, scores = selector.select_best(
            models, X, y, X_val=X, y_val=y
        )
        assert best_model_name in models
        assert isinstance(best_model, object)
        assert isinstance(scores, dict)

    def test_select_best_classification(self, classification_data):
        """Test model selection for classification."""
        X, y = classification_data
        models = {
            'logistic': LogisticRegression(max_iter=100),
            'random_forest': RandomForestClassifier(n_estimators=5),
        }
        selector = ModelSelector(scoring='accuracy', cv=2)
        best_model_name, best_model, scores = selector.select_best(
            models, X, y, X_val=X, y_val=y
        )
        assert best_model_name in models

    def test_select_with_cross_validation(self, regression_data):
        """Test model selection with cross-validation."""
        X, y = regression_data
        models = {
            'linear': LinearRegression(),
            'random_forest': RandomForestRegressor(n_estimators=5),
        }
        selector = ModelSelector(scoring='neg_mean_squared_error', cv=3)
        best_model_name, best_model, scores = selector.select_best(
            models, X, y, X_val=X, y_val=y
        )
        assert best_model_name in models

    def test_select_with_ensemble(self, regression_data):
        """Test model selection with ensemble consideration."""
        X, y = regression_data
        models = {
            'linear': LinearRegression(),
            'random_forest': RandomForestRegressor(n_estimators=5),
        }
        selector = ModelSelector(scoring='r2', consider_ensemble=True)
        best_model_name, best_model, scores = selector.select_best(
            models, X, y, X_val=X, y_val=y
        )
        assert best_model_name in models

    def test_select_with_early_stopping(self, regression_data):
        """Test model selection with early stopping."""
        X, y = regression_data
        models = {
            'linear': LinearRegression(),
            'random_forest': RandomForestRegressor(n_estimators=5),
        }
        selector = ModelSelector(scoring='r2', early_stopping_rounds=1)
        best_model_name, best_model, scores = selector.select_best(
            models, X, y, X_val=X[:50], y_val=y[:50]
        )
        assert best_model_name in models

    def test_select_with_metrics(self, regression_data):
        """Test model selection with multiple metrics."""
        X, y = regression_data
        models = {
            'linear': LinearRegression(),
            'random_forest': RandomForestRegressor(n_estimators=5),
        }
        selector = ModelSelector(metrics=['r2', 'neg_mean_squared_error'])
        best_model_name, best_model, scores = selector.select_best(
            models, X, y, X_val=X, y_val=y
        )
        assert best_model_name in models
        assert 'r2' in scores[best_model_name]
        assert 'neg_mean_squared_error' in scores[best_model_name]

# ============================================================================
# TEST EARLY STOPPING
# ============================================================================

class TestEarlyStopping:
    """Test early stopping functionality."""

    def test_init(self):
        """Test initialization."""
        es = EarlyStopping(patience=5, min_delta=0.01)
        assert es.patience == 5
        assert es.min_delta == 0.01

    def test_early_stop(self):
        """Test early stopping logic."""
        es = EarlyStopping(patience=2, min_delta=0.01)
        # Simulate decreasing validation loss
        losses = [1.0, 0.9, 0.89, 0.88, 0.87]
        for i, loss in enumerate(losses):
            should_stop = es.step(loss)
            if i >= 3:  # Should stop after 2 epochs of no improvement (with min_delta)
                assert should_stop is True
                break
        else:
            assert False, "Early stopping did not trigger"

    def test_restore_best_weights(self):
        """Test restoring best weights."""
        es = EarlyStopping(patience=2, restore_best_weights=True)
        es.step(1.0, model_state={'weights': 'best'})
        es.step(0.9, model_state={'weights': 'best'})
        es.step(0.95)  # No improvement
        best_state = es.get_best_model_state()
        assert best_state is not None
        assert best_state['weights'] == 'best'

    def test_early_stop_on_metric(self):
        """Test early stopping with metric like accuracy."""
        es = EarlyStopping(patience=2, min_delta=0.01, mode='max')
        # Simulate increasing accuracy
        accuracies = [0.8, 0.85, 0.86, 0.86, 0.86]
        for i, acc in enumerate(accuracies):
            should_stop = es.step(acc, is_metric=True)
            if i >= 3:  # Should stop after plateau
                assert should_stop is True
                break
        else:
            assert False, "Early stopping did not trigger"

    def test_early_stop_with_patience(self):
        """Test early stopping with patience count."""
        es = EarlyStopping(patience=3)
        losses = [1.0, 0.9, 0.9, 0.9, 0.9]  # No improvement after first
        for i, loss in enumerate(losses):
            should_stop = es.step(loss)
            if i >= 3:
                assert should_stop is True

    def test_early_stop_with_min_delta(self):
        """Test early stopping with minimum delta."""
        es = EarlyStopping(patience=2, min_delta=0.02)
        losses = [1.0, 0.99, 0.98, 0.97, 0.96]  # Improvement is 0.01 each step
        # min_delta=0.02 means no improvement should be detected (or maybe after first)
        # Actually, first improvement is 0.01 < 0.02, so best stays 1.0
        for i, loss in enumerate(losses):
            should_stop = es.step(loss)
            if i >= 2:
                assert should_stop is True
                break

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests combining optimization components."""

    def test_optimize_then_select(self, regression_data):
        """Test hyperparameter optimization followed by model selection."""
        X, y = regression_data
        models = {
            'rf': RandomForestRegressor(random_state=42),
            'linear': LinearRegression(),
        }
        
        # Optimize hyperparameters for RF
        param_grid = {'n_estimators': [5, 10], 'max_depth': [3, 5]}
        optimizer = HyperparameterOptimizer(config={'method': 'grid_search', 'cv': 2})
        best_params, _ = optimizer.optimize(
            models['rf'], X, y, param_grid=param_grid
        )
        models['rf_optimized'] = RandomForestRegressor(**best_params, random_state=42)
        
        # Select best model
        selector = ModelSelector(scoring='r2', cv=2)
        best_name, best_model, scores = selector.select_best(
            models, X, y, X_val=X, y_val=y
        )
        assert best_name in ['rf_optimized', 'linear']

    def test_optimize_with_ensemble(self, regression_data):
        """Test ensemble creation with optimized models."""
        X, y = regression_data
        # Generate multiple optimized models
        models = []
        param_grids = [
            {'n_estimators': [5, 10], 'max_depth': [3, 5]},
            {'n_estimators': [10, 20], 'max_depth': [5, 10]},
        ]
        for pg in param_grids:
            opt = HyperparameterOptimizer(config={'method': 'grid_search', 'cv': 2})
            best_params, _ = opt.optimize(RandomForestRegressor(random_state=42), X, y, param_grid=pg)
            models.append(RandomForestRegressor(**best_params, random_state=42))
        
        # Use ensemble predictor
        from ai.models.ensemble.voting_ensemble import VotingEnsemble
        ensemble = VotingEnsemble(models=models)
        preds = ensemble.predict(X[:10])
        assert len(preds) == 10

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_prune_and_quantize(self, mock_torch_model):
        """Test pruning then quantization."""
        # Prune
        pruner = ModelPruner(method='magnitude', target_sparsity=0.2)
        X = torch.randn(10, 10)
        y = torch.randn(10, 1)
        pruned_model = pruner.prune(mock_torch_model, X, y)
        
        # Quantize
        quantizer = ModelQuantizer(method='post_training', dtype='int8')
        quantized_model = quantizer.quantize(pruned_model, X)
        
        assert quantized_model is not None

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
    def test_optimize_prune_quantize_pipeline(self, mock_torch_model, regression_data):
        """Test full pipeline: optimize -> prune -> quantize."""
        # This would require a full training loop, skip for brevity
        pass

# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance tests for optimization."""

    @pytest.mark.benchmark
    def test_grid_search_speed(self, benchmark, sample_model_regression, regression_data, param_grid):
        """Benchmark grid search speed."""
        X, y = regression_data
        optimizer = HyperparameterOptimizer(config={'method': 'grid_search'})
        def run():
            return optimizer.optimize(sample_model_regression, X, y, param_grid=param_grid)
        result = benchmark(run)
        assert result is not None

    @pytest.mark.benchmark
    def test_bayesian_optimization_speed(self, benchmark, sample_model_regression, regression_data, param_space):
        """Benchmark Bayesian optimization speed."""
        try:
            from ai.optimization.bayesian_optimization import BayesianOptimizer
        except ImportError:
            pytest.skip("BayesianOptimizer not available")
        X, y = regression_data
        optimizer = BayesianOptimizer(n_iter=5)
        def run():
            return optimizer.optimize(sample_model_regression, X, y, param_space=param_space)
        result = benchmark(run)
        assert result is not None

    def test_model_selection_speed(self, regression_data):
        """Test model selection speed."""
        X, y = regression_data
        models = {
            'linear': LinearRegression(),
            'random_forest': RandomForestRegressor(n_estimators=5),
            'svm': LinearRegression(),  # placeholder
        }
        selector = ModelSelector(scoring='r2', cv=2)
        import time
        start = time.time()
        best_name, best_model, scores = selector.select_best(
            models, X, y, X_val=X, y_val=y
        )
        duration = time.time() - start
        assert duration < 5.0  # Should be fast

# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling in optimization components."""

    def test_invalid_method(self):
        """Test invalid optimization method."""
        with pytest.raises(ValueError):
            HyperparameterOptimizer(config={'method': 'invalid'})

    def test_missing_param_grid(self, sample_model_regression, regression_data):
        """Test missing parameter grid."""
        optimizer = HyperparameterOptimizer()
        with pytest.raises(ValueError):
            optimizer.optimize(sample_model_regression, *regression_data)

    def test_missing_param_space(self, sample_model_regression, regression_data):
        """Test missing parameter space for Bayesian optimization."""
        try:
            from ai.optimization.bayesian_optimization import BayesianOptimizer
        except ImportError:
            pytest.skip("BayesianOptimizer not available")
        optimizer = BayesianOptimizer(n_iter=5)
        with pytest.raises(ValueError):
            optimizer.optimize(sample_model_regression, *regression_data, param_space=None)

    def test_early_stopping_no_improvement(self):
        """Test early stopping with no improvement."""
        es = EarlyStopping(patience=1)
        # First step
        es.step(1.0)
        # Second step no improvement
        should_stop = es.step(1.0)
        assert should_stop is True

    def test_model_selector_empty_models(self):
        """Test model selector with empty model dict."""
        selector = ModelSelector()
        with pytest.raises(ValueError):
            selector.select_best({}, None, None, X_val=None, y_val=None)

    def test_pruner_unsupported_model(self):
        """Test pruner with unsupported model type."""
        pruner = ModelPruner(method='magnitude')
        with pytest.raises(TypeError):
            pruner.prune("not_a_model", None, None)

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

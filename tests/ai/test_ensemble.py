"""
AI Ensemble Tests
===================

This module contains tests for the AI ensemble model components.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock

from trading.bots.swing_bot.ai.ensemble import EnsembleModel, EnsemblePrediction
from trading.bots.swing_bot.ai.models import BaseModel
from trading.bots.swing_bot.ai.config import ModelConfig


class TestEnsembleModel:
    """Tests for EnsembleModel class."""

    @pytest.fixture
    def ensemble_config(self):
        """Create ensemble configuration for testing."""
        return {
            'ensemble_method': 'weighted_average',
            'weights': {'model_1': 0.4, 'model_2': 0.3, 'model_3': 0.3},
            'min_models_required': 2,
            'confidence_threshold': 0.6,
            'diversity_weight': 0.5,
            'performance_weight': 0.5,
            'dynamic_weighting': True,
            'weight_decay': 0.9,
            'ensemble_size': 5,
        }

    @pytest.fixture
    def ensemble_model(self, ensemble_config):
        """Create EnsembleModel instance."""
        return EnsembleModel(config=ensemble_config)

    @pytest.fixture
    def mock_models(self):
        """Create mock models for testing."""
        models = []
        for i in range(3):
            model = Mock(spec=BaseModel)
            model.predict = Mock(return_value=np.array([0.5 + i * 0.1]))
            model.get_performance = Mock(return_value={'accuracy': 0.7 + i * 0.05})
            model.name = f"model_{i+1}"
            models.append(model)
        return models

    @pytest.fixture
    def sample_features(self):
        """Create sample feature data."""
        return np.random.randn(10, 5)

    def test_initialization(self, ensemble_config):
        """Test ensemble model initialization."""
        ensemble = EnsembleModel(config=ensemble_config)
        assert ensemble.ensemble_method == ensemble_config['ensemble_method']
        assert ensemble.weights == ensemble_config['weights']
        assert ensemble.min_models_required == ensemble_config['min_models_required']
        assert ensemble.models == []
        assert ensemble.model_performance == {}

    def test_add_model(self, ensemble_model, mock_models):
        """Test adding models to ensemble."""
        for model in mock_models:
            ensemble_model.add_model(model)

        assert len(ensemble_model.models) == 3
        assert ensemble_model.model_performance is not None

    def test_add_model_duplicate(self, ensemble_model, mock_models):
        """Test adding duplicate model."""
        model = mock_models[0]
        ensemble_model.add_model(model)
        with pytest.raises(ValueError):
            ensemble_model.add_model(model)

    def test_remove_model(self, ensemble_model, mock_models):
        """Test removing a model from ensemble."""
        for model in mock_models:
            ensemble_model.add_model(model)

        ensemble_model.remove_model('model_1')
        assert len(ensemble_model.models) == 2
        assert 'model_1' not in [m.name for m in ensemble_model.models]

    def test_remove_model_not_found(self, ensemble_model):
        """Test removing non-existent model."""
        with pytest.raises(ValueError):
            ensemble_model.remove_model('non_existent')

    def test_update_weights(self, ensemble_model, mock_models):
        """Test updating model weights."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Get initial weights
        initial_weights = ensemble_model.weights.copy()

        # Update with new performance data
        performance = {
            'model_1': {'accuracy': 0.85},
            'model_2': {'accuracy': 0.75},
            'model_3': {'accuracy': 0.65},
        }
        ensemble_model.update_weights(performance)

        # Weights should have changed
        assert ensemble_model.weights != initial_weights

    def test_predict_weighted_average(self, ensemble_model, mock_models, sample_features):
        """Test weighted average prediction."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Set specific predictions
        expected_values = [0.4, 0.6, 0.8]
        for i, model in enumerate(ensemble_model.models):
            model.predict = Mock(return_value=np.array([expected_values[i]]))

        predictions, confidence = ensemble_model.predict(sample_features)

        expected = np.array([0.4 * 0.4 + 0.6 * 0.3 + 0.8 * 0.3])
        np.testing.assert_almost_equal(predictions, expected)
        assert 0 <= confidence <= 1

    def test_predict_voting(self, ensemble_model, mock_models, sample_features):
        """Test voting ensemble prediction."""
        ensemble_model.ensemble_method = 'voting'
        for model in mock_models:
            ensemble_model.add_model(model)

        # Create predictions with majority buy
        predictions = [np.array([1]), np.array([1]), np.array([-1])]
        for i, model in enumerate(ensemble_model.models):
            model.predict = Mock(return_value=predictions[i])

        pred, confidence = ensemble_model.predict(sample_features)
        assert pred == 1  # Majority vote

    def test_predict_median(self, ensemble_model, mock_models, sample_features):
        """Test median ensemble prediction."""
        ensemble_model.ensemble_method = 'median'
        for model in mock_models:
            ensemble_model.add_model(model)

        # Set predictions
        expected_values = [0.3, 0.5, 0.7]
        for i, model in enumerate(ensemble_model.models):
            model.predict = Mock(return_value=np.array([expected_values[i]]))

        pred, confidence = ensemble_model.predict(sample_features)
        assert pred == 0.5  # Median

    def test_predict_stacking(self, ensemble_model, mock_models, sample_features):
        """Test stacking ensemble prediction."""
        ensemble_model.ensemble_method = 'stacking'
        
        # Add a meta-model
        meta_model = Mock(spec=BaseModel)
        meta_model.predict = Mock(return_value=np.array([0.55]))
        meta_model.name = "meta_model"
        ensemble_model.meta_model = meta_model

        for model in mock_models:
            ensemble_model.add_model(model)

        # Set base model predictions
        for i, model in enumerate(ensemble_model.models):
            model.predict = Mock(return_value=np.array([0.4 + i * 0.2]))

        pred, confidence = ensemble_model.predict(sample_features)
        assert pred == 0.55  # Meta-model prediction

    def test_predict_with_confidence(self, ensemble_model, mock_models, sample_features):
        """Test prediction confidence calculation."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Vary predictions to affect confidence
        predictions = [[0.45], [0.50], [0.55]]
        for i, model in enumerate(ensemble_model.models):
            model.predict = Mock(return_value=np.array(predictions[i]))
            model.get_confidence = Mock(return_value=0.8 - i * 0.1)

        pred, confidence = ensemble_model.predict(sample_features)
        assert confidence < 1.0  # Should be less than 1 due to variance

    def test_predict_with_uncertainty(self, ensemble_model, mock_models, sample_features):
        """Test prediction uncertainty estimation."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Add models with different confidence levels
        for i, model in enumerate(ensemble_model.models):
            model.get_uncertainty = Mock(return_value=0.1 + i * 0.1)

        pred, confidence = ensemble_model.predict(sample_features)
        assert confidence <= 1.0

    def test_predict_insufficient_models(self, ensemble_model, sample_features):
        """Test prediction with insufficient models."""
        # Add only one model
        model = Mock(spec=BaseModel)
        model.predict = Mock(return_value=np.array([0.5]))
        model.name = "model_1"
        ensemble_model.add_model(model)

        with pytest.raises(ValueError, match="Insufficient models for ensemble"):
            ensemble_model.predict(sample_features)

    def test_predict_with_dynamic_weights(self, ensemble_model, mock_models, sample_features):
        """Test prediction with dynamic weighting."""
        ensemble_model.dynamic_weighting = True
        for model in mock_models:
            ensemble_model.add_model(model)

        # Set model performances
        performance = {
            'model_1': {'accuracy': 0.9},
            'model_2': {'accuracy': 0.7},
            'model_3': {'accuracy': 0.5},
        }
        ensemble_model.update_weights(performance)

        # Predictions
        expected_values = [0.3, 0.5, 0.7]
        for i, model in enumerate(ensemble_model.models):
            model.predict = Mock(return_value=np.array([expected_values[i]]))

        pred, _ = ensemble_model.predict(sample_features)
        # Weighted average should favor model_1
        assert pred > 0.4  # Should be closer to 0.3 (model_1 has highest weight)

    def test_update_weights_auto(self, ensemble_model, mock_models):
        """Test automatic weight update based on performance."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Update performances
        performance = {
            'model_1': {'accuracy': 0.9},
            'model_2': {'accuracy': 0.8},
            'model_3': {'accuracy': 0.6},
        }
        ensemble_model.update_weights(performance)

        # Weights should reflect performance
        weights = ensemble_model.weights
        assert weights['model_1'] > weights['model_3']

    def test_apply_weight_decay(self, ensemble_model, mock_models):
        """Test weight decay application."""
        for model in mock_models:
            ensemble_model.add_model(model)

        initial_weights = ensemble_model.weights.copy()
        ensemble_model.apply_weight_decay(decay=0.5)

        # All weights should be decayed
        for key in initial_weights:
            assert ensemble_model.weights[key] <= initial_weights[key]

    def test_normalize_weights(self, ensemble_model):
        """Test weight normalization."""
        weights = {'a': 1.0, 'b': 2.0, 'c': 3.0}
        normalized = ensemble_model.normalize_weights(weights)

        assert sum(normalized.values()) == 1.0
        assert normalized['c'] > normalized['a']

    def test_get_ensemble_performance(self, ensemble_model, mock_models):
        """Test getting ensemble performance metrics."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Set model performances
        for i, model in enumerate(ensemble_model.models):
            model.get_performance = Mock(return_value={'accuracy': 0.7 + i * 0.1})

        performance = ensemble_model.get_ensemble_performance()
        assert 'accuracy' in performance
        assert 'model_count' in performance
        assert 'weights' in performance

    def test_get_model_performances(self, ensemble_model, mock_models):
        """Test getting individual model performances."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Set model performances
        for i, model in enumerate(ensemble_model.models):
            model.get_performance = Mock(return_value={'accuracy': 0.7 + i * 0.1})

        performances = ensemble_model.get_model_performances()
        assert len(performances) == 3
        assert 'model_1' in performances

    def test_ensemble_diversity(self, ensemble_model, mock_models):
        """Test ensemble diversity calculation."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Mock predictions with diversity
        predictions = [np.array([0.3]), np.array([0.5]), np.array([0.7])]
        for i, model in enumerate(ensemble_model.models):
            model.predict = Mock(return_value=predictions[i])

        diversity = ensemble_model.calculate_diversity(sample_features)
        assert 0 <= diversity <= 1
        assert diversity > 0

    def test_save_load_state(self, ensemble_model, mock_models, temp_dir):
        """Test saving and loading ensemble state."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Save state
        save_path = temp_dir / "ensemble_state.json"
        ensemble_model.save_state(save_path)
        assert save_path.exists()

        # Load state
        new_ensemble = EnsembleModel()
        new_ensemble.load_state(save_path)

        assert new_ensemble.ensemble_method == ensemble_model.ensemble_method
        assert new_ensemble.min_models_required == ensemble_model.min_models_required

    def test_ensemble_with_keras_models(self, ensemble_model, sample_features):
        """Test ensemble with mock Keras models."""
        # Create mock Keras models
        for i in range(2):
            model = Mock()
            model.predict = Mock(return_value=np.array([[0.5 + i * 0.2]]))
            model.name = f"keras_model_{i}"
            ensemble_model.add_model(model)

        pred, confidence = ensemble_model.predict(sample_features)
        assert pred is not None

    def test_ensemble_with_torch_models(self, ensemble_model, sample_features):
        """Test ensemble with mock PyTorch models."""
        # Create mock PyTorch models
        for i in range(2):
            model = Mock()
            model.predict = Mock(return_value=np.array([0.5 + i * 0.2]))
            model.name = f"torch_model_{i}"
            ensemble_model.add_model(model)

        # For torch models, need to handle tensor conversion
        # This is a simplified test
        pred, confidence = ensemble_model.predict(sample_features)
        assert pred is not None

    def test_ensemble_weights_update_based_on_performance(self, ensemble_model, mock_models):
        """Test weight update based on actual model performance."""
        for model in mock_models:
            ensemble_model.add_model(model)

        # Simulate validation data
        X_val = np.random.randn(10, 5)
        y_val = np.random.randn(10)

        # Set model predictions with different accuracy
        model_predictions = [
            np.array([0.8, 0.9, 0.7, 0.85, 0.75, 0.95, 0.65, 0.8, 0.85, 0.7]),
            np.array([0.5, 0.6, 0.4, 0.55, 0.45, 0.65, 0.35, 0.5, 0.55, 0.4]),
            np.array([0.3, 0.2, 0.4, 0.35, 0.25, 0.45, 0.15, 0.3, 0.35, 0.2]),
        ]
        for i, model in enumerate(ensemble_model.models):
            model.predict = Mock(return_value=model_predictions[i])
            model.name = f"model_{i+1}"

        # Update weights based on performance
        ensemble_model.update_weights_from_validation(X_val, y_val)

        # Model with better predictions should have higher weight
        assert ensemble_model.weights['model_1'] > ensemble_model.weights['model_3']


class TestEnsemblePrediction:
    """Tests for EnsemblePrediction class."""

    def test_initialization(self):
        """Test EnsemblePrediction initialization."""
        prediction = EnsemblePrediction(
            predictions={'model_1': 0.5, 'model_2': 0.6},
            aggregated=0.55,
            confidence=0.85,
            weights={'model_1': 0.4, 'model_2': 0.6}
        )
        assert prediction.predictions == {'model_1': 0.5, 'model_2': 0.6}
        assert prediction.aggregated == 0.55
        assert prediction.confidence == 0.85

    def test_to_dict(self):
        """Test conversion to dictionary."""
        prediction = EnsemblePrediction(
            predictions={'model_1': 0.5, 'model_2': 0.6},
            aggregated=0.55,
            confidence=0.85,
            weights={'model_1': 0.4, 'model_2': 0.6}
        )
        data = prediction.to_dict()
        assert 'predictions' in data
        assert 'aggregated' in data
        assert 'confidence' in data
        assert 'weights' in data

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'predictions': {'model_1': 0.5, 'model_2': 0.6},
            'aggregated': 0.55,
            'confidence': 0.85,
            'weights': {'model_1': 0.4, 'model_2': 0.6}
        }
        prediction = EnsemblePrediction.from_dict(data)
        assert prediction.predictions == data['predictions']
        assert prediction.aggregated == data['aggregated']
        assert prediction.confidence == data['confidence']


class TestEnsembleIntegration:
    """Integration tests for ensemble with real components."""

    def test_end_to_end_ensemble_flow(self, sample_features):
        """Test complete ensemble workflow."""
        # Create ensemble
        ensemble = EnsembleModel()

        # Create and add mock models
        for i in range(3):
            model = Mock(spec=BaseModel)
            model.predict = Mock(return_value=np.array([0.4 + i * 0.2]))
            model.get_performance = Mock(return_value={'accuracy': 0.7 + i * 0.05})
            model.name = f"model_{i+1}"
            ensemble.add_model(model)

        # Make prediction
        pred, confidence = ensemble.predict(sample_features)

        assert pred is not None
        assert 0 <= confidence <= 1

        # Update weights based on performance
        performance = {
            'model_1': {'accuracy': 0.85},
            'model_2': {'accuracy': 0.75},
            'model_3': {'accuracy': 0.65},
        }
        ensemble.update_weights(performance)

        # Get ensemble performance
        perf = ensemble.get_ensemble_performance()
        assert 'accuracy' in perf
        assert 'model_count' in perf

    def test_ensemble_with_realistic_predictions(self, sample_features):
        """Test ensemble with more realistic predictions."""
        ensemble = EnsembleModel()

        # Create models with different characteristics
        for i in range(3):
            model = Mock(spec=BaseModel)
            # Different prediction patterns
            if i == 0:
                pred = np.array([0.45, 0.46, 0.47, 0.48, 0.49, 0.50, 0.51, 0.52, 0.53, 0.54])
            elif i == 1:
                pred = np.array([0.48, 0.47, 0.46, 0.45, 0.44, 0.45, 0.46, 0.47, 0.48, 0.49])
            else:
                pred = np.array([0.42, 0.43, 0.44, 0.45, 0.46, 0.47, 0.48, 0.49, 0.50, 0.51])
            
            model.predict = Mock(return_value=pred)
            model.get_performance = Mock(return_value={'accuracy': 0.7 + i * 0.1})
            model.name = f"model_{i+1}"
            ensemble.add_model(model)

        # Test on sample data
        pred, confidence = ensemble.predict(sample_features)

        # Should be a valid prediction
        assert isinstance(pred, np.ndarray) or isinstance(pred, float)
        assert 0 <= confidence <= 1

        # Test ensemble diversity
        diversity = ensemble.calculate_diversity(sample_features)
        assert 0 <= diversity <= 1


if __name__ == "__main__":
    pytest.main([__file__])

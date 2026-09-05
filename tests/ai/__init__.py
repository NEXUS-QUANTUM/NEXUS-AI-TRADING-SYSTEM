# tests/ai/__init__.py
"""
AI Module Tests for the NEXUS AI Trading System.

This package contains all unit and integration tests for the AI submodules,
including data preprocessing, feature engineering, model training, ensemble
methods, inference, optimization, and registry management.

The test suite is designed to be run with pytest and covers:
- Data loading and preprocessing (test_data_preprocessing)
- Feature extraction and engineering (test_features)
- Model definition and architecture (test_models)
- Training pipelines (test_training)
- Ensemble strategies (test_ensemble)
- Inference and prediction (test_inference, test_predictions)
- Model optimization (test_model_optimization)
- Model registry and versioning (test_model_registry)

All tests adhere to the NEXUS development standards and use shared fixtures
from conftest.py.
"""

# Import test modules to make them available as submodules
from . import conftest
from . import test_data_preprocessing
from . import test_ensemble
from . import test_features
from . import test_inference
from . import test_model_optimization
from . import test_model_registry
from . import test_models
from . import test_predictions
from . import test_training

# Expose test modules for easy import
__all__ = [
    "conftest",
    "test_data_preprocessing",
    "test_ensemble",
    "test_features",
    "test_inference",
    "test_model_optimization",
    "test_model_registry",
    "test_models",
    "test_predictions",
    "test_training",
]

# Optional: package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"

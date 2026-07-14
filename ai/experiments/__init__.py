"""
NEXUS AI TRADING SYSTEM - Experiments Module
Copyright © 2026 NEXUS QUANTUM LTD

This module provides comprehensive experiment management capabilities including:
- Experiment lifecycle management
- Hyperparameter optimization
- Ablation studies
- Results comparison and analysis
- Statistical testing
- Visualization of results
- Experiment tracking with MLflow, W&B, and TensorBoard
- Reproducibility management
- Experiment templates
- Parameter sweeps
- Multi-run analysis
- Cross-validation integration
- Model evaluation
- Benchmarking
- Reporting and export
- Integration with distributed learning
- Resource monitoring
- Experiment scheduling
- Notification system
- Version control integration
- Artifact management

The experiments module enables:
- Systematic exploration of model architectures
- Hyperparameter tuning with Bayesian optimization
- Comprehensive ablation studies
- Rigorous statistical comparison of results
- Reproducible and trackable experiments
- Collaborative research and development
"""

import os
import sys
import json
import yaml
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Callable, Type
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

# ============================================
# Module Version and Metadata
# ============================================

__version__ = '3.0.0'
__author__ = 'NEXUS QUANTUM LTD'
__description__ = 'Experiments Module for NEXUS AI Trading System'
__license__ = 'Proprietary - Copyright © 2026 NEXUS QUANTUM LTD'

# ============================================
# Module Logger Configuration
# ============================================

logger = logging.getLogger(__name__)

# Create logs directory
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

# Configure module logger
if not logger.handlers:
    # File handler
    file_handler = logging.FileHandler(LOG_DIR / 'experiments.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)
    
    logger.setLevel(logging.INFO)

# ============================================
# Module Dependencies
# ============================================

DEPENDENCIES: Dict[str, str] = {
    'numpy': '>=1.24.0',
    'pandas': '>=2.0.0',
    'scipy': '>=1.10.0',
    'matplotlib': '>=3.7.0',
    'seaborn': '>=0.12.0',
    'scikit-learn': '>=1.3.0',
    'torch': '>=2.0.0',
    'optuna': '>=3.0.0',
    'mlflow': '>=2.0.0',
    'wandb': '>=0.15.0',
    'hyperopt': '>=0.2.7',
    'scikit-optimize': '>=0.9.0',
    'bayesian-optimization': '>=1.4.0',
    'tqdm': '>=4.65.0',
    'pyyaml': '>=6.0',
    'gitpython': '>=3.1.0',
    'psutil': '>=5.9.0',
}

# Optional dependencies
OPTIONAL_DEPENDENCIES: Dict[str, str] = {
    'jinja2': '>=3.1.0',
    'weasyprint': '>=60.0',
    'plotly': '>=5.14.0',
    'dash': '>=2.10.0',
    'streamlit': '>=1.25.0',
}

# ============================================
# Import Submodules
# ============================================

# Import experiment tracker
try:
    from .experiment_tracker import (
        ExperimentTracker,
        ExperimentConfig,
        ExperimentRun,
        ExperimentSummary,
        ExperimentStatus,
        ExperimentType,
        MetricType,
    )
except ImportError as e:
    logger.warning(f"Failed to import experiment_tracker: {e}")
    ExperimentTracker = None
    ExperimentConfig = None
    ExperimentRun = None
    ExperimentSummary = None
    ExperimentStatus = None
    ExperimentType = None
    MetricType = None

# Import hyperparameter optimizer
try:
    from .hyperparameter_optimizer import (
        HyperparameterOptimizer,
        OptimizationConfig,
        OptimizationResult,
        OptimizationStatus,
        OptimizationMethod,
        ParameterSpace,
        ParameterType,
    )
except ImportError as e:
    logger.warning(f"Failed to import hyperparameter_optimizer: {e}")
    HyperparameterOptimizer = None
    OptimizationConfig = None
    OptimizationResult = None
    OptimizationStatus = None
    OptimizationMethod = None
    ParameterSpace = None
    ParameterType = None

# Import ablation study
try:
    from .ablation_study import (
        AblationStudy,
        AblationConfig,
        AblationResult,
        AblationSummary,
        AblationStatus,
        AblationType,
        AblationStudyFactory,
    )
except ImportError as e:
    logger.warning(f"Failed to import ablation_study: {e}")
    AblationStudy = None
    AblationConfig = None
    AblationResult = None
    AblationSummary = None
    AblationStatus = None
    AblationType = None
    AblationStudyFactory = None

# Import results comparator
try:
    from .results_comparator import (
        ResultsComparator,
        ComparisonConfig,
        ComparisonResult,
        ComparisonType,
        StatisticalTest,
        EffectSize,
    )
except ImportError as e:
    logger.warning(f"Failed to import results_comparator: {e}")
    ResultsComparator = None
    ComparisonConfig = None
    ComparisonResult = None
    ComparisonType = None
    StatisticalTest = None
    EffectSize = None

# ============================================
# Module Exports
# ============================================

__all__ = [
    # Experiment Tracker
    'ExperimentTracker',
    'ExperimentConfig',
    'ExperimentRun',
    'ExperimentSummary',
    'ExperimentStatus',
    'ExperimentType',
    'MetricType',
    
    # Hyperparameter Optimizer
    'HyperparameterOptimizer',
    'OptimizationConfig',
    'OptimizationResult',
    'OptimizationStatus',
    'OptimizationMethod',
    'ParameterSpace',
    'ParameterType',
    
    # Ablation Study
    'AblationStudy',
    'AblationConfig',
    'AblationResult',
    'AblationSummary',
    'AblationStatus',
    'AblationType',
    'AblationStudyFactory',
    
    # Results Comparator
    'ResultsComparator',
    'ComparisonConfig',
    'ComparisonResult',
    'ComparisonType',
    'StatisticalTest',
    'EffectSize',
]

# ============================================
# Module Initialization
# ============================================

def check_dependencies() -> Tuple[bool, List[str]]:
    """
    Check if all required dependencies are installed.
    
    Returns:
        Tuple of (all_available, missing_dependencies)
    """
    missing = []
    for package_name, version_spec in DEPENDENCIES.items():
        try:
            import_name = package_name.replace('-', '_').replace('.', '_')
            if package_name == 'scikit-learn':
                import_name = 'sklearn'
            elif package_name == 'scikit-optimize':
                import_name = 'skopt'
            elif package_name == 'bayesian-optimization':
                import_name = 'bayes_opt'
            __import__(import_name)
        except ImportError:
            missing.append(f"{package_name}{version_spec}")
    
    if missing:
        logger.warning(f"Missing dependencies: {missing}")
        return False, missing
    
    logger.info("All dependencies are available")
    return True, []

def get_module_info() -> Dict[str, Any]:
    """
    Get comprehensive module information.
    
    Returns:
        Dictionary with module metadata
    """
    return {
        'name': __name__,
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'license': __license__,
        'dependencies': DEPENDENCIES,
        'optional_dependencies': OPTIONAL_DEPENDENCIES,
        'python_version': sys.version,
        'python_executable': sys.executable,
        'platform': sys.platform,
        'available_submodules': {
            'experiment_tracker': ExperimentTracker is not None,
            'hyperparameter_optimizer': HyperparameterOptimizer is not None,
            'ablation_study': AblationStudy is not None,
            'results_comparator': ResultsComparator is not None,
        },
        'log_level': logging.getLevelName(logger.level),
        'log_file': str(LOG_DIR / 'experiments.log'),
    }

def setup_environment(
    log_level: str = 'INFO',
    seed: Optional[int] = 42,
    output_dir: str = './experiments',
) -> None:
    """
    Set up the environment for experiments.
    
    Args:
        log_level: Logging level
        seed: Random seed for reproducibility
        output_dir: Output directory for experiment results
    """
    # Set logging level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
    
    # Set random seed
    if seed is not None:
        import random
        import numpy as np
        import torch
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        os.environ['PYTHONHASHSEED'] = str(seed)
        logger.info(f"Random seed set to {seed}")
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    subdirs = [
        'tracking',
        'hyperopt',
        'ablation',
        'comparisons',
        'reports',
        'checkpoints',
        'logs',
    ]
    for subdir in subdirs:
        Path(output_dir) / subdir / '.keep'
    
    logger.info(f"Environment setup complete. Output directory: {output_dir}")

# ============================================
# Convenience Functions
# ============================================

def create_experiment(
    name: str,
    description: str,
    experiment_type: str = 'training',
    parameters: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Any:
    """
    Create a new experiment.
    
    Args:
        name: Experiment name
        description: Experiment description
        experiment_type: Type of experiment
        parameters: Experiment parameters
        **kwargs: Additional configuration
        
    Returns:
        Experiment tracker instance
    """
    if ExperimentTracker is None:
        raise ImportError("ExperimentTracker not available")
    
    from .experiment_tracker import ExperimentType as ET
    
    type_map = {
        'training': ET.TRAINING,
        'evaluation': ET.EVALUATION,
        'hyperparameter_tuning': ET.HYPERPARAMETER_TUNING,
        'ablation': ET.ABLATION,
        'benchmark': ET.BENCHMARK,
        'inference': ET.INFERENCE,
    }
    
    exp_type = type_map.get(experiment_type, ET.TRAINING)
    
    tracker = ExperimentTracker(
        experiment_dir=kwargs.get('experiment_dir', './experiments'),
        experiment_name=name,
        tags=kwargs.get('tags', []),
    )
    
    exp_id = tracker.create_experiment(
        name=name,
        description=description,
        experiment_type=exp_type,
        parameters=parameters or {},
        tags=kwargs.get('tags', []),
        metadata=kwargs.get('metadata', {}),
    )
    
    return tracker

def optimize_hyperparameters(
    objective_function: Callable,
    parameter_space: List[Dict[str, Any]],
    name: str = "hyperparameter_optimization",
    method: str = "bayesian",
    n_trials: int = 100,
    objective_metric: str = "accuracy",
    direction: str = "maximize",
    **kwargs
) -> Any:
    """
    Run hyperparameter optimization.
    
    Args:
        objective_function: Function to optimize
        parameter_space: List of parameter definitions
        name: Optimization name
        method: Optimization method
        n_trials: Number of trials
        objective_metric: Metric to optimize
        direction: "maximize" or "minimize"
        **kwargs: Additional configuration
        
    Returns:
        Hyperparameter optimizer instance
    """
    if HyperparameterOptimizer is None:
        raise ImportError("HyperparameterOptimizer not available")
    
    from .hyperparameter_optimizer import ParameterSpace, ParameterType
    
    # Convert parameter space
    params = []
    for p in parameter_space:
        type_map = {
            'float': ParameterType.FLOAT,
            'int': ParameterType.INTEGER,
            'categorical': ParameterType.CATEGORICAL,
            'log_float': ParameterType.LOG_FLOAT,
            'log_int': ParameterType.LOG_INTEGER,
        }
        param_type = type_map.get(p.get('type', 'float'), ParameterType.FLOAT)
        
        param = ParameterSpace(
            name=p['name'],
            type=param_type,
            min=p.get('min'),
            max=p.get('max'),
            categories=p.get('categories'),
            default=p.get('default'),
            description=p.get('description'),
        )
        params.append(param)
    
    # Create config
    method_map = {
        'bayesian': OptimizationMethod.BAYESIAN,
        'random': OptimizationMethod.RANDOM,
        'grid': OptimizationMethod.GRID,
        'tpe': OptimizationMethod.TPE,
        'hyperband': OptimizationMethod.HYPERBAND,
        'cma_es': OptimizationMethod.CMA_ES,
        'skopt': OptimizationMethod.SKOPT,
    }
    opt_method = method_map.get(method, OptimizationMethod.BAYESIAN)
    
    config = OptimizationConfig(
        study_id=f"opt_{int(time.time())}",
        name=name,
        description=kwargs.get('description', ''),
        method=opt_method,
        parameter_space=params,
        objective_metric=objective_metric,
        direction=direction,
        n_trials=n_trials,
        n_initial_points=kwargs.get('n_initial_points', 10),
        early_stopping=kwargs.get('early_stopping', True),
        early_stopping_patience=kwargs.get('early_stopping_patience', 20),
        early_stopping_threshold=kwargs.get('early_stopping_threshold', 0.001),
        n_jobs=kwargs.get('n_jobs', 1),
        parallel=kwargs.get('parallel', False),
        timeout_seconds=kwargs.get('timeout_seconds', None),
        random_seed=kwargs.get('random_seed', 42),
        save_results=kwargs.get('save_results', True),
        output_dir=kwargs.get('output_dir', './experiments/hyperopt'),
        metadata=kwargs.get('metadata', {}),
    )
    
    optimizer = HyperparameterOptimizer(config, objective_function)
    optimizer.optimize()
    return optimizer

def run_ablation_study(
    base_config: Dict[str, Any],
    components: Dict[str, Any],
    name: str = "ablation_study",
    repetitions: int = 3,
    **kwargs
) -> Any:
    """
    Run an ablation study.
    
    Args:
        base_config: Base configuration
        components: Components to ablate
        name: Study name
        repetitions: Number of repetitions
        **kwargs: Additional configuration
        
    Returns:
        Ablation study instance
    """
    if AblationStudyFactory is None:
        raise ImportError("AblationStudyFactory not available")
    
    study = AblationStudyFactory.create_component_ablation(
        name=name,
        base_config=base_config,
        components=components,
        metrics=kwargs.get('metrics', ['accuracy', 'f1']),
        repetitions=repetitions,
        n_jobs=kwargs.get('n_jobs', 1),
        parallel=kwargs.get('parallel', False),
        random_seed=kwargs.get('random_seed', 42),
        output_dir=kwargs.get('output_dir', './experiments/ablation'),
        early_stop=kwargs.get('early_stop', False),
        cross_validation_folds=kwargs.get('cross_validation_folds', 5),
    )
    
    study.run()
    return study

def compare_results(
    data: Dict[str, List[float]],
    name: str = "comparison",
    statistical_tests: Optional[List[str]] = None,
    **kwargs
) -> Any:
    """
    Compare results from multiple groups.
    
    Args:
        data: Dictionary of group name to values
        name: Comparison name
        statistical_tests: List of statistical tests to run
        **kwargs: Additional configuration
        
    Returns:
        Results comparator instance
    """
    if ResultsComparator is None:
        raise ImportError("ResultsComparator not available")
    
    from .results_comparator import StatisticalTest
    
    test_map = {
        't_test': StatisticalTest.T_TEST,
        'welch_t_test': StatisticalTest.WELCH_T_TEST,
        'paired_t_test': StatisticalTest.PAIRED_T_TEST,
        'mann_whitney': StatisticalTest.MANN_WHITNEY,
        'wilcoxon': StatisticalTest.WILCOXON,
        'anova': StatisticalTest.ANOVA,
        'kruskal_wallis': StatisticalTest.KRUSKAL_WALLIS,
        'chi_square': StatisticalTest.CHI_SQUARE,
        'friedman': StatisticalTest.FRIEDMAN,
        'bayesian': StatisticalTest.BAYESIAN,
    }
    
    if statistical_tests is None:
        tests = [StatisticalTest.T_TEST, StatisticalTest.MANN_WHITNEY]
    else:
        tests = [test_map.get(t, StatisticalTest.T_TEST) for t in statistical_tests]
    
    config = ComparisonConfig(
        comparison_id=f"comp_{int(time.time())}",
        name=name,
        description=kwargs.get('description', ''),
        type=ComparisonType.MULTI_GROUP,
        groups={},
        metrics=['value'],
        statistical_tests=tests,
        significance_level=kwargs.get('significance_level', 0.05),
        correction_method=kwargs.get('correction_method', 'bonferroni'),
        n_bootstrap=kwargs.get('n_bootstrap', 1000),
        random_seed=kwargs.get('random_seed', 42),
        output_dir=kwargs.get('output_dir', './experiments/comparisons'),
        metadata=kwargs.get('metadata', {}),
    )
    
    comparator = ResultsComparator(config)
    result = comparator.compare(data)
    return comparator

# ============================================
# Module Documentation
# ============================================

MODULE_DOCSTRING = """
NEXUS AI Trading System - Experiments Module
=============================================

This module provides a complete framework for conducting and managing machine learning experiments.

Key Components:
---------------
1. Experiment Tracker (experiment_tracker.py)
   - Track experiments, runs, and metrics
   - Integration with MLflow, W&B, TensorBoard
   - Version control integration
   - Resource monitoring
   - Report generation

2. Hyperparameter Optimizer (hyperparameter_optimizer.py)
   - Bayesian optimization with Gaussian Processes
   - Random search and grid search
   - TPE optimization
   - Hyperband
   - CMA-ES
   - Parameter importance analysis

3. Ablation Study (ablation_study.py)
   - Component ablation
   - Feature ablation
   - Hyperparameter ablation
   - Architecture ablation
   - Interaction analysis
   - Statistical significance testing

4. Results Comparator (results_comparator.py)
   - Multi-group comparison
   - Statistical tests (t-test, ANOVA, Mann-Whitney, etc.)
   - Effect size calculation
   - Confidence intervals
   - Visualization
   - Report generation

Quick Start:
------------
1. Track an experiment:
   >>> from ai.experiments import create_experiment
   >>> tracker = create_experiment("My Experiment", "Testing new model")
   >>> run_id = tracker.start_run(experiment_id)
   >>> tracker.log_metric(run_id, "accuracy", 0.95)
   >>> tracker.end_run(run_id)

2. Optimize hyperparameters:
   >>> from ai.experiments import optimize_hyperparameters
   >>> def objective(params):
   ...     # Train and evaluate model
   ...     return {'accuracy': 0.95}
   >>> optimizer = optimize_hyperparameters(
   ...     objective_function=objective,
   ...     parameter_space=[{'name': 'lr', 'type': 'float', 'min': 0.0001, 'max': 0.1}],
   ...     n_trials=100
   ... )
   >>> best_params = optimizer.get_best_parameters()

3. Run ablation study:
   >>> from ai.experiments import run_ablation_study
   >>> study = run_ablation_study(
   ...     base_config={'layers': 4, 'hidden_size': 256},
   ...     components={'dropout': 0.5, 'batch_norm': True}
   ... )

4. Compare results:
   >>> from ai.experiments import compare_results
   >>> data = {
   ...     'Model A': [0.92, 0.93, 0.91, 0.94],
   ...     'Model B': [0.95, 0.96, 0.94, 0.97]
   ... }
   >>> comparator = compare_results(data, "Model Comparison")
"""

# ============================================
# Module Initialization Logging
# ============================================

logger.info(f"Experiments Module v{__version__} initialized")
logger.info(f"Python version: {sys.version}")
available = []
for name, available_sub in get_module_info()['available_submodules'].items():
    if available_sub:
        available.append(name)
logger.info(f"Available submodules: {', '.join(available)}")

# Check dependencies
available, missing = check_dependencies()
if not available:
    logger.warning(f"Missing dependencies: {missing}")
    logger.warning("Please install missing dependencies to use all features")

# ============================================
# Module Ready
# ============================================

logger.info("Module ready for use")

# ============================================
# Export Module
# ============================================

# Only export what's available
__all__ = __all__

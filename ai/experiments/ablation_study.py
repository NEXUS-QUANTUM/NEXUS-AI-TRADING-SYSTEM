"""
NEXUS AI TRADING SYSTEM - Ablation Study Module
Copyright © 2026 NEXUS QUANTUM LTD

This module provides comprehensive ablation study capabilities including:
- Systematic removal of model components
- Feature importance analysis
- Architecture ablation
- Hyperparameter sensitivity analysis
- Training configuration ablation
- Data augmentation ablation
- Loss function ablation
- Optimizer ablation
- Attention mechanism ablation
- Normalization layer ablation
- Activation function ablation
- Layer depth and width ablation
- Regularization ablation
- Ensemble component ablation
- Comprehensive experiment tracking
- Statistical analysis of results
- Visualization of ablation results
- Automated experiment execution
- Parallel experiment execution
- Result aggregation and comparison
- Significance testing
- Effect size calculation
- Multi-run averaging
- Cross-validation integration
- Reproducibility management
- Bayesian analysis
- Sensitivity analysis
- Interaction effect analysis
- Ranking and selection
- Report generation
- Export to multiple formats
"""

import os
import sys
import json
import yaml
import time
import logging
import hashlib
import pickle
import copy
import itertools
from typing import Dict, List, Optional, Tuple, Any, Union, Callable, Type, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from pathlib import Path
from collections import defaultdict, OrderedDict, Counter
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import ttest_ind, mannwhitneyu, f_oneway, wilcoxon, kruskal
from scipy.stats import spearmanr, pearsonr
from sklearn.model_selection import train_test_split, KFold, StratifiedKFold
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    mean_squared_error, mean_absolute_error, r2_score
)
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, Subset
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
from tqdm import tqdm
import warnings
import traceback
import gc
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ablation_study.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class AblationType(Enum):
    """Types of ablation studies."""
    COMPONENT = "component"
    FEATURE = "feature"
    HYPERPARAMETER = "hyperparameter"
    ARCHITECTURE = "architecture"
    TRAINING = "training"
    DATA = "data"
    LOSS = "loss"
    OPTIMIZER = "optimizer"
    REGULARIZATION = "regularization"
    ATTENTION = "attention"
    NORMALIZATION = "normalization"
    ACTIVATION = "activation"
    LAYER = "layer"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"
    INTERACTION = "interaction"
    SENSITIVITY = "sensitivity"


class AblationStatus(Enum):
    """Status of ablation experiments."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class SignificanceLevel(Enum):
    """Significance levels for statistical tests."""
    P_0_001 = 0.001
    P_0_01 = 0.01
    P_0_05 = 0.05
    P_0_1 = 0.1
    P_1 = 1.0


@dataclass
class AblationConfig:
    """Configuration for an ablation study."""
    study_id: str
    name: str
    description: str
    ablation_type: AblationType
    base_config: Dict[str, Any]
    variations: List[Dict[str, Any]]
    metrics: List[str]
    repetitions: int = 3
    random_seed: int = 42
    n_jobs: int = 1
    parallel: bool = False
    save_results: bool = True
    output_dir: str = "./results/ablation"
    timeout_seconds: int = 3600
    early_stop: bool = False
    early_stop_threshold: float = 0.99
    cross_validation_folds: int = 5
    use_bayesian: bool = False
    interaction_analysis: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AblationResult:
    """Results from an ablation experiment."""
    experiment_id: str
    study_id: str
    variation_id: str
    variation_name: str
    config: Dict[str, Any]
    metrics: Dict[str, float]
    train_metrics: Dict[str, List[float]]
    val_metrics: Dict[str, List[float]]
    test_metrics: Dict[str, float]
    cv_scores: List[Dict[str, float]]
    timestamp: float
    duration: float
    status: AblationStatus
    error: Optional[str] = None
    reproducibility: Dict[str, Any] = field(default_factory=dict)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    model_size: Optional[int] = None
    inference_time: Optional[float] = None


@dataclass
class AblationSummary:
    """Summary of ablation study results."""
    study_id: str
    name: str
    description: str
    ablation_type: str
    total_experiments: int
    completed_experiments: int
    failed_experiments: int
    best_variation: str
    baseline_variation: str
    importance_scores: Dict[str, float]
    statistical_tests: Dict[str, Any]
    effect_sizes: Dict[str, float]
    ranking: List[Dict[str, Any]]
    visualization_data: Dict[str, Any]
    bayesian_results: Optional[Dict[str, Any]] = None
    interaction_effects: Optional[Dict[str, Any]] = None
    sensitivity_analysis: Optional[Dict[str, Any]] = None
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================
# Ablation Study Engine
# ============================================

class AblationStudy:
    """
    Main engine for conducting ablation studies.
    
    This class manages the execution of ablation experiments including
    variation generation, experiment execution, result collection, and analysis.
    """
    
    def __init__(self, config: AblationConfig):
        """
        Initialize the ablation study.
        
        Args:
            config: Ablation configuration
        """
        self.config = config
        self.results: List[AblationResult] = []
        self.status: Dict[str, AblationStatus] = {}
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.logger = logging.getLogger(f"ablation.{config.study_id}")
        self._executor: Optional[ProcessPoolExecutor] = None
        
        # Create output directory
        self.output_dir = Path(config.output_dir) / config.study_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize random seed
        np.random.seed(config.random_seed)
        torch.manual_seed(config.random_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(config.random_seed)
        
        # Initialize results file
        self.results_file = self.output_dir / "results.json"
        self.summary_file = self.output_dir / "summary.json"
        
        # Metrics storage
        self.metrics_data = defaultdict(list)
        
        self.logger.info(f"Initialized ablation study: {config.name}")
        self.logger.info(f"Study ID: {config.study_id}")
        self.logger.info(f"Variations: {len(config.variations)}")
        self.logger.info(f"Repetitions: {config.repetitions}")
        self.logger.info(f"Total experiments: {len(config.variations) * config.repetitions}")
    
    # ============================================
    # Experiment Management
    # ============================================
    
    def generate_experiments(self) -> List[Dict[str, Any]]:
        """
        Generate all experiment configurations.
        
        Returns:
            List of experiment configurations
        """
        experiments = []
        
        for var_idx, variation in enumerate(self.config.variations):
            var_id = f"var_{var_idx:03d}"
            var_name = variation.get('name', f"Variation {var_idx + 1}")
            
            for rep in range(self.config.repetitions):
                experiment = {
                    'experiment_id': f"{self.config.study_id}_{var_id}_rep{rep:02d}",
                    'study_id': self.config.study_id,
                    'variation_id': var_id,
                    'variation_name': var_name,
                    'config': self._merge_configs(
                        self.config.base_config,
                        variation.get('changes', {})
                    ),
                    'repetition': rep,
                    'random_seed': self.config.random_seed + rep + var_idx * 100,
                    'timestamp': time.time(),
                    'metadata': variation.get('metadata', {}),
                }
                experiments.append(experiment)
        
        return experiments
    
    def _merge_configs(
        self,
        base: Dict[str, Any],
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge base configuration with changes.
        
        Args:
            base: Base configuration
            changes: Changes to apply
            
        Returns:
            Merged configuration
        """
        merged = copy.deepcopy(base)
        
        for key, value in changes.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    # ============================================
    # Experiment Execution
    # ============================================
    
    def run(self) -> None:
        """
        Run all ablation experiments.
        """
        self.start_time = time.time()
        experiments = self.generate_experiments()
        
        self.logger.info(f"Starting {len(experiments)} experiments")
        
        try:
            if self.config.parallel and self.config.n_jobs > 1:
                self._run_parallel(experiments)
            else:
                self._run_sequential(experiments)
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
            self._cancel_experiments()
        finally:
            self.end_time = time.time()
            self._save_results()
            self._generate_summary()
            self._generate_report()
        
        self.logger.info(
            f"Completed {len(self.results)} experiments in "
            f"{self.end_time - self.start_time:.2f}s"
        )
    
    def _run_sequential(self, experiments: List[Dict[str, Any]]) -> None:
        """
        Run experiments sequentially.
        
        Args:
            experiments: List of experiment configurations
        """
        for exp in tqdm(experiments, desc="Running experiments"):
            if self._should_stop():
                break
            result = self._run_single_experiment(exp)
            self.results.append(result)
            self._save_progress()
            self._update_metrics(result)
    
    def _run_parallel(self, experiments: List[Dict[str, Any]]) -> None:
        """
        Run experiments in parallel.
        
        Args:
            experiments: List of experiment configurations
        """
        with ProcessPoolExecutor(max_workers=self.config.n_jobs) as executor:
            self._executor = executor
            futures = []
            
            for exp in experiments:
                future = executor.submit(
                    self._run_single_experiment_wrapper,
                    exp,
                    self.config
                )
                futures.append(future)
            
            for future in tqdm(as_completed(futures), desc="Running experiments", total=len(futures)):
                if self._should_stop():
                    break
                try:
                    result = future.result(timeout=self.config.timeout_seconds)
                    self.results.append(result)
                    self._save_progress()
                    self._update_metrics(result)
                except Exception as e:
                    self.logger.error(f"Experiment failed: {e}")
                    self.results.append(self._create_failed_result(exp, str(e)))
    
    def _run_single_experiment_wrapper(
        self,
        experiment: Dict[str, Any],
        config: AblationConfig
    ) -> AblationResult:
        """
        Wrapper for running a single experiment in parallel.
        
        Args:
            experiment: Experiment configuration
            config: Ablation configuration
            
        Returns:
            Ablation result
        """
        # Create a new instance for parallel execution
        study = AblationStudy(config)
        return study._run_single_experiment(experiment)
    
    def _run_single_experiment(
        self,
        experiment: Dict[str, Any]
    ) -> AblationResult:
        """
        Run a single ablation experiment.
        
        Args:
            experiment: Experiment configuration
            
        Returns:
            Ablation result
        """
        start_time = time.time()
        experiment_id = experiment['experiment_id']
        
        try:
            self.logger.debug(f"Running experiment: {experiment_id}")
            
            # Set random seed for reproducibility
            seed = experiment.get('random_seed', self.config.random_seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False
            
            # Train and evaluate model
            train_metrics, val_metrics, test_metrics, cv_scores = self._train_and_evaluate(
                experiment['config'],
                seed
            )
            
            duration = time.time() - start_time
            
            # Calculate model size
            model_size = self._get_model_size(experiment['config'])
            
            result = AblationResult(
                experiment_id=experiment_id,
                study_id=experiment['study_id'],
                variation_id=experiment['variation_id'],
                variation_name=experiment['variation_name'],
                config=experiment['config'],
                metrics=test_metrics,
                train_metrics=train_metrics,
                val_metrics=val_metrics,
                test_metrics=test_metrics,
                cv_scores=cv_scores,
                timestamp=experiment['timestamp'],
                duration=duration,
                status=AblationStatus.COMPLETED,
                reproducibility={
                    'random_seed': seed,
                    'timestamp': datetime.now().isoformat(),
                    'python_version': sys.version,
                    'torch_version': torch.__version__,
                },
                hyperparameters=experiment['config'].get('hyperparameters', {}),
                model_size=model_size,
                inference_time=duration / 100,
            )
            
            self.logger.debug(f"Experiment {experiment_id} completed in {duration:.2f}s")
            return result
            
        except TimeoutError:
            self.logger.error(f"Experiment {experiment_id} timed out")
            return self._create_failed_result(experiment, "Timeout")
            
        except Exception as e:
            self.logger.error(f"Experiment {experiment_id} failed: {e}")
            traceback.print_exc()
            return self._create_failed_result(experiment, str(e))
    
    def _create_failed_result(
        self,
        experiment: Dict[str, Any],
        error: str
    ) -> AblationResult:
        """
        Create a failed result object.
        
        Args:
            experiment: Experiment configuration
            error: Error message
            
        Returns:
            Failed ablation result
        """
        return AblationResult(
            experiment_id=experiment['experiment_id'],
            study_id=experiment['study_id'],
            variation_id=experiment['variation_id'],
            variation_name=experiment['variation_name'],
            config=experiment['config'],
            metrics={},
            train_metrics={},
            val_metrics={},
            test_metrics={},
            cv_scores=[],
            timestamp=experiment['timestamp'],
            duration=0,
            status=AblationStatus.FAILED,
            error=error,
        )
    
    def _should_stop(self) -> bool:
        """
        Check if the study should stop early.
        
        Returns:
            True if should stop, False otherwise
        """
        if not self.config.early_stop:
            return False
        
        if len(self.results) < 3:
            return False
        
        # Check if best variation has reached threshold
        best_acc = max(r.test_metrics.get('accuracy', 0) for r in self.results if r.status == AblationStatus.COMPLETED)
        if best_acc >= self.config.early_stop_threshold:
            self.logger.info(f"Early stopping: best accuracy {best_acc:.4f} >= threshold {self.config.early_stop_threshold}")
            return True
        
        return False
    
    def _cancel_experiments(self) -> None:
        """Cancel running experiments."""
        if self._executor:
            self._executor.shutdown(wait=False)
            self.logger.info("Cancelled running experiments")
    
    def _train_and_evaluate(
        self,
        config: Dict[str, Any],
        seed: int
    ) -> Tuple[Dict[str, List[float]], Dict[str, List[float]], Dict[str, float], List[Dict[str, float]]]:
        """
        Train and evaluate a model with the given configuration.
        
        Args:
            config: Model configuration
            seed: Random seed
            
        Returns:
            Tuple of (train_metrics, val_metrics, test_metrics, cv_scores)
        """
        # This is a placeholder - in production, this would:
        # 1. Create model with the given configuration
        # 2. Train the model on training data
        # 3. Evaluate on validation and test sets
        # 4. Return metrics
        
        # For demonstration, simulate training with realistic patterns
        epochs = config.get('epochs', 10)
        batch_size = config.get('batch_size', 32)
        learning_rate = config.get('learning_rate', 0.001)
        
        # Simulate training with learning curve
        np.random.seed(seed)
        
        # Base metrics with random variation
        base_acc = config.get('base_accuracy', 0.7)
        base_loss = config.get('base_loss', 0.5)
        
        # Generate learning curves
        train_loss = []
        train_acc = []
        val_loss = []
        val_acc = []
        
        for epoch in range(epochs):
            # Progress factor
            progress = (epoch + 1) / epochs
            
            # Loss decreases over time
            loss_factor = np.exp(-progress * 2)
            current_loss = base_loss * loss_factor + np.random.exponential(0.02) * 0.1
            
            # Accuracy increases over time with plateau
            acc_factor = 1 - np.exp(-progress * 3)
            current_acc = base_acc + (0.25 - base_acc * 0.2) * acc_factor
            current_acc += np.random.normal(0, 0.01)
            current_acc = np.clip(current_acc, 0, 1)
            
            train_loss.append(current_loss)
            train_acc.append(current_acc)
            
            # Validation metrics (slightly worse than training)
            val_loss_factor = np.exp(-progress * 1.8)
            val_current_loss = base_loss * 1.1 * val_loss_factor + np.random.exponential(0.02) * 0.1
            val_current_acc = current_acc - np.random.uniform(0.01, 0.05)
            val_current_acc = np.clip(val_current_acc, 0, 1)
            
            val_loss.append(val_current_loss)
            val_acc.append(val_current_acc)
        
        # Final test metrics
        test_loss = val_loss[-1] * 0.9
        test_acc = val_acc[-1] * 1.02
        test_acc = np.clip(test_acc, 0, 1)
        
        test_precision = test_acc * np.random.uniform(0.9, 1.1)
        test_precision = np.clip(test_precision, 0, 1)
        test_recall = test_acc * np.random.uniform(0.9, 1.1)
        test_recall = np.clip(test_recall, 0, 1)
        test_f1 = 2 * test_precision * test_recall / (test_precision + test_recall + 1e-8)
        
        # Cross-validation scores
        cv_scores = []
        for fold in range(self.config.cross_validation_folds):
            fold_acc = test_acc + np.random.normal(0, 0.02)
            fold_acc = np.clip(fold_acc, 0, 1)
            cv_scores.append({
                'fold': fold,
                'accuracy': fold_acc,
                'f1': fold_acc * 0.95,
                'precision': fold_acc * 0.96,
                'recall': fold_acc * 0.94,
            })
        
        train_metrics = {
            'loss': train_loss,
            'accuracy': train_acc,
        }
        
        val_metrics = {
            'loss': val_loss,
            'accuracy': val_acc,
        }
        
        test_metrics = {
            'loss': test_loss,
            'accuracy': test_acc,
            'precision': test_precision,
            'recall': test_recall,
            'f1': test_f1,
        }
        
        return train_metrics, val_metrics, test_metrics, cv_scores
    
    def _get_model_size(self, config: Dict[str, Any]) -> int:
        """
        Estimate model size from configuration.
        
        Args:
            config: Model configuration
            
        Returns:
            Estimated model size in parameters
        """
        # This is a placeholder
        hidden_size = config.get('hidden_size', 256)
        num_layers = config.get('num_layers', 4)
        input_size = config.get('input_size', 100)
        output_size = config.get('output_size', 1)
        
        # Rough estimate of parameter count
        params = input_size * hidden_size
        params += hidden_size * hidden_size * (num_layers - 1)
        params += hidden_size * output_size
        params += hidden_size + output_size  # biases
        
        return params
    
    # ============================================
    # Result Management
    # ============================================
    
    def _save_progress(self) -> None:
        """Save current progress."""
        if self.config.save_results:
            self._save_results()
    
    def _save_results(self) -> None:
        """Save all results to file."""
        results_data = {
            'study_id': self.config.study_id,
            'name': self.config.name,
            'description': self.config.description,
            'ablation_type': self.config.ablation_type.value,
            'timestamp': datetime.now().isoformat(),
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_experiments': len(self.results),
            'completed_experiments': len([r for r in self.results if r.status == AblationStatus.COMPLETED]),
            'failed_experiments': len([r for r in self.results if r.status == AblationStatus.FAILED]),
            'results': [asdict(r) for r in self.results],
        }
        
        with open(self.results_file, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
    
    def _update_metrics(self, result: AblationResult) -> None:
        """
        Update metrics storage with new result.
        
        Args:
            result: Ablation result
        """
        if result.status != AblationStatus.COMPLETED:
            return
        
        self.metrics_data['accuracy'].append(result.test_metrics.get('accuracy', 0))
        self.metrics_data['f1'].append(result.test_metrics.get('f1', 0))
        self.metrics_data['precision'].append(result.test_metrics.get('precision', 0))
        self.metrics_data['recall'].append(result.test_metrics.get('recall', 0))
    
    def load_results(self) -> List[AblationResult]:
        """
        Load results from file.
        
        Returns:
            List of ablation results
        """
        if not self.results_file.exists():
            return []
        
        with open(self.results_file, 'r') as f:
            data = json.load(f)
        
        results = []
        for r in data.get('results', []):
            result = AblationResult(
                experiment_id=r['experiment_id'],
                study_id=r['study_id'],
                variation_id=r['variation_id'],
                variation_name=r['variation_name'],
                config=r['config'],
                metrics=r['metrics'],
                train_metrics=r['train_metrics'],
                val_metrics=r['val_metrics'],
                test_metrics=r['test_metrics'],
                cv_scores=r.get('cv_scores', []),
                timestamp=r['timestamp'],
                duration=r['duration'],
                status=AblationStatus(r['status']),
                error=r.get('error'),
                reproducibility=r.get('reproducibility', {}),
                hyperparameters=r.get('hyperparameters', {}),
                model_size=r.get('model_size'),
                inference_time=r.get('inference_time'),
            )
            results.append(result)
        
        return results
    
    # ============================================
    # Analysis and Summary
    # ============================================
    
    def _generate_summary(self) -> Optional[AblationSummary]:
        """
        Generate summary of ablation results.
        
        Returns:
            Ablation summary
        """
        if not self.results:
            self.logger.warning("No results to summarize")
            return None
        
        # Group results by variation
        variation_results = defaultdict(list)
        for result in self.results:
            if result.status == AblationStatus.COMPLETED:
                variation_results[result.variation_id].append(result)
        
        if not variation_results:
            self.logger.warning("No completed experiments to summarize")
            return None
        
        # Calculate metrics for each variation
        variation_metrics = {}
        for var_id, results in variation_results.items():
            # Aggregate metrics
            test_acc = [r.test_metrics.get('accuracy', 0) for r in results]
            test_f1 = [r.test_metrics.get('f1', 0) for r in results]
            test_precision = [r.test_metrics.get('precision', 0) for r in results]
            test_recall = [r.test_metrics.get('recall', 0) for r in results]
            durations = [r.duration for r in results]
            
            variation_metrics[var_id] = {
                'name': results[0].variation_name,
                'accuracy': np.mean(test_acc),
                'accuracy_std': np.std(test_acc) if len(test_acc) > 1 else 0,
                'accuracy_min': np.min(test_acc) if test_acc else 0,
                'accuracy_max': np.max(test_acc) if test_acc else 0,
                'f1': np.mean(test_f1),
                'f1_std': np.std(test_f1) if len(test_f1) > 1 else 0,
                'precision': np.mean(test_precision),
                'recall': np.mean(test_recall),
                'avg_duration': np.mean(durations) if durations else 0,
                'count': len(results),
                'results': results,
            }
        
        # Find best and baseline
        baseline_id = list(variation_results.keys())[0] if variation_results else None
        best_id = max(variation_metrics.keys(), key=lambda k: variation_metrics[k]['accuracy'])
        
        # Calculate importance scores
        importance_scores = {}
        if baseline_id and baseline_id in variation_metrics:
            baseline_acc = variation_metrics[baseline_id]['accuracy']
            for var_id, metrics in variation_metrics.items():
                if var_id != baseline_id:
                    importance_scores[var_id] = metrics['accuracy'] - baseline_acc
        
        # Statistical tests
        statistical_tests = {}
        effect_sizes = {}
        for var_id in variation_metrics.keys():
            if var_id != baseline_id and baseline_id in variation_metrics:
                # Get results for both variations
                baseline_results = [
                    r.test_metrics.get('accuracy', 0)
                    for r in variation_results[baseline_id]
                ]
                var_results = [
                    r.test_metrics.get('accuracy', 0)
                    for r in variation_results[var_id]
                ]
                
                if len(baseline_results) > 1 and len(var_results) > 1:
                    # T-test
                    t_stat, p_value = ttest_ind(baseline_results, var_results)
                    statistical_tests[var_id] = {
                        't_statistic': t_stat,
                        'p_value': p_value,
                        'significant': p_value < 0.05,
                        'test': 't-test',
                    }
                    
                    # Cohen's d effect size
                    pooled_std = np.sqrt(
                        (np.std(baseline_results) ** 2 + np.std(var_results) ** 2) / 2
                    )
                    effect_sizes[var_id] = (
                        np.mean(var_results) - np.mean(baseline_results)
                    ) / (pooled_std + 1e-8)
                elif len(baseline_results) > 1 and len(var_results) > 0:
                    # Mann-Whitney U test
                    u_stat, p_value = mannwhitneyu(baseline_results, var_results)
                    statistical_tests[var_id] = {
                        'u_statistic': u_stat,
                        'p_value': p_value,
                        'significant': p_value < 0.05,
                        'test': 'mann-whitney',
                    }
                    
                    # Effect size (r = Z / sqrt(n))
                    from scipy.stats import rankdata
                    n = len(baseline_results) + len(var_results)
                    z_score = (u_stat - len(baseline_results) * len(var_results) / 2) / np.sqrt(
                        len(baseline_results) * len(var_results) * (n + 1) / 12
                    )
                    effect_sizes[var_id] = abs(z_score) / np.sqrt(n)
        
        # Create ranking
        ranking = []
        for var_id, metrics in sorted(
            variation_metrics.items(),
            key=lambda x: x[1]['accuracy'],
            reverse=True
        ):
            ranking.append({
                'variation_id': var_id,
                'name': metrics['name'],
                'accuracy': metrics['accuracy'],
                'accuracy_std': metrics['accuracy_std'],
                'f1': metrics['f1'],
                'rank': len(ranking) + 1,
                'is_baseline': var_id == baseline_id,
                'is_best': var_id == best_id,
            })
        
        # Bayesian analysis if enabled
        bayesian_results = None
        if self.config.use_bayesian:
            bayesian_results = self._perform_bayesian_analysis(variation_metrics)
        
        # Interaction analysis if enabled
        interaction_effects = None
        if self.config.interaction_analysis:
            interaction_effects = self._analyze_interactions(variation_results)
        
        # Sensitivity analysis
        sensitivity_analysis = self._perform_sensitivity_analysis(variation_metrics)
        
        summary = AblationSummary(
            study_id=self.config.study_id,
            name=self.config.name,
            description=self.config.description,
            ablation_type=self.config.ablation_type.value,
            total_experiments=len(self.results),
            completed_experiments=len([r for r in self.results if r.status == AblationStatus.COMPLETED]),
            failed_experiments=len([r for r in self.results if r.status == AblationStatus.FAILED]),
            best_variation=best_id,
            baseline_variation=baseline_id,
            importance_scores=importance_scores,
            statistical_tests=statistical_tests,
            effect_sizes=effect_sizes,
            ranking=ranking,
            visualization_data=self._prepare_visualization_data(variation_metrics),
            bayesian_results=bayesian_results,
            interaction_effects=interaction_effects,
            sensitivity_analysis=sensitivity_analysis,
            timestamp=time.time(),
            metadata=self.config.metadata,
        )
        
        # Save summary
        with open(self.summary_file, 'w') as f:
            json.dump(asdict(summary), f, indent=2, default=str)
        
        self.logger.info(f"Summary saved to {self.summary_file}")
        return summary
    
    def _prepare_visualization_data(
        self,
        variation_metrics: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Prepare data for visualization.
        
        Args:
            variation_metrics: Variation metrics
            
        Returns:
            Visualization data
        """
        # Sort by accuracy for consistent ordering
        sorted_vars = sorted(
            variation_metrics.items(),
            key=lambda x: x[1]['accuracy'],
            reverse=True
        )
        
        data = {
            'variation_names': [],
            'variation_ids': [],
            'accuracies': [],
            'accuracy_stds': [],
            'f1_scores': [],
            'f1_stds': [],
            'precisions': [],
            'recalls': [],
            'durations': [],
            'counts': [],
            'is_baseline': [],
            'is_best': [],
        }
        
        for i, (var_id, metrics) in enumerate(sorted_vars):
            data['variation_names'].append(metrics['name'])
            data['variation_ids'].append(var_id)
            data['accuracies'].append(metrics['accuracy'])
            data['accuracy_stds'].append(metrics['accuracy_std'])
            data['f1_scores'].append(metrics.get('f1', 0))
            data['f1_stds'].append(metrics.get('f1_std', 0))
            data['precisions'].append(metrics.get('precision', 0))
            data['recalls'].append(metrics.get('recall', 0))
            data['durations'].append(metrics.get('avg_duration', 0))
            data['counts'].append(metrics.get('count', 0))
            data['is_baseline'].append(i == 0)
            data['is_best'].append(i == 0)
        
        return data
    
    def _perform_bayesian_analysis(
        self,
        variation_metrics: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Perform Bayesian analysis on ablation results.
        
        Args:
            variation_metrics: Variation metrics
            
        Returns:
            Bayesian analysis results
        """
        # This is a simplified Bayesian analysis
        # In production, use PyMC3 or similar for full Bayesian inference
        results = {}
        
        for var_id, metrics in variation_metrics.items():
            accuracies = [r.test_metrics.get('accuracy', 0) for r in metrics['results']]
            if not accuracies:
                continue
            
            # Simple Bayesian estimate with weak prior
            mean_acc = np.mean(accuracies)
            std_acc = np.std(accuracies) if len(accuracies) > 1 else 0.01
            
            # Posterior estimate (simplified)
            posterior_mean = mean_acc
            posterior_std = std_acc / np.sqrt(len(accuracies)) if len(accuracies) > 0 else 0.01
            
            # Credible interval (95%)
            lower_bound = posterior_mean - 1.96 * posterior_std
            upper_bound = posterior_mean + 1.96 * posterior_std
            
            results[var_id] = {
                'mean': posterior_mean,
                'std': posterior_std,
                'lower_95': max(0, lower_bound),
                'upper_95': min(1, upper_bound),
                'n_samples': len(accuracies),
            }
        
        return results
    
    def _analyze_interactions(
        self,
        variation_results: Dict[str, List[AblationResult]]
    ) -> Dict[str, Any]:
        """
        Analyze interaction effects between variations.
        
        Args:
            variation_results: Variation results
            
        Returns:
            Interaction analysis results
        """
        # This is a placeholder for interaction analysis
        # In production, use factorial ANOVA or similar
        interactions = {}
        
        var_ids = list(variation_results.keys())
        if len(var_ids) < 2:
            return {}
        
        # Simple pairwise interaction analysis
        for i in range(len(var_ids)):
            for j in range(i + 1, len(var_ids)):
                var1 = var_ids[i]
                var2 = var_ids[j]
                
                results1 = [r.test_metrics.get('accuracy', 0) for r in variation_results[var1]]
                results2 = [r.test_metrics.get('accuracy', 0) for r in variation_results[var2]]
                
                # Interaction effect (simplified)
                combined = results1 + results2
                mean_combined = np.mean(combined)
                mean1 = np.mean(results1)
                mean2 = np.mean(results2)
                
                # Interaction effect size
                interaction = (mean1 - mean_combined) * (mean2 - mean_combined) / (mean_combined + 1e-8)
                
                interactions[f"{var1}_{var2}"] = {
                    'var1': var1,
                    'var2': var2,
                    'interaction_effect': interaction,
                    'mean1': mean1,
                    'mean2': mean2,
                    'combined_mean': mean_combined,
                }
        
        return interactions
    
    def _perform_sensitivity_analysis(
        self,
        variation_metrics: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Perform sensitivity analysis on ablation results.
        
        Args:
            variation_metrics: Variation metrics
            
        Returns:
            Sensitivity analysis results
        """
        sensitivity = {}
        
        for var_id, metrics in variation_metrics.items():
            accuracies = [r.test_metrics.get('accuracy', 0) for r in metrics['results']]
            if not accuracies:
                continue
            
            # Compute sensitivity metrics
            mean_acc = np.mean(accuracies)
            std_acc = np.std(accuracies) if len(accuracies) > 1 else 0
            
            # Coefficient of variation
            cv = (std_acc / (mean_acc + 1e-8)) * 100
            
            # Range
            range_val = np.max(accuracies) - np.min(accuracies) if accuracies else 0
            
            # Confidence interval width (95%)
            ci_width = 1.96 * std_acc / np.sqrt(len(accuracies)) if len(accuracies) > 0 else 0
            
            sensitivity[var_id] = {
                'mean': mean_acc,
                'std': std_acc,
                'cv': cv,
                'range': range_val,
                'ci_width': ci_width,
                'n_samples': len(accuracies),
                'max': np.max(accuracies) if accuracies else 0,
                'min': np.min(accuracies) if accuracies else 0,
            }
        
        return sensitivity
    
    # ============================================
    # Report Generation
    # ============================================
    
    def _generate_report(self) -> None:
        """
        Generate comprehensive report of ablation results.
        """
        summary = self._generate_summary()
        if not summary:
            return
        
        report_file = self.output_dir / "report.md"
        
        with open(report_file, 'w') as f:
            f.write(f"# Ablation Study Report\n\n")
            f.write(f"## Study Information\n\n")
            f.write(f"- **Study ID:** {summary.study_id}\n")
            f.write(f"- **Name:** {summary.name}\n")
            f.write(f"- **Description:** {summary.description}\n")
            f.write(f"- **Type:** {summary.ablation_type}\n")
            f.write(f"- **Timestamp:** {datetime.fromtimestamp(summary.timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"## Experiment Summary\n\n")
            f.write(f"- **Total Experiments:** {summary.total_experiments}\n")
            f.write(f"- **Completed:** {summary.completed_experiments}\n")
            f.write(f"- **Failed:** {summary.failed_experiments}\n")
            f.write(f"- **Best Variation:** {summary.best_variation}\n")
            f.write(f"- **Baseline Variation:** {summary.baseline_variation}\n\n")
            
            f.write(f"## Ranking\n\n")
            f.write("| Rank | Variation | Accuracy | F1 Score | Baseline | Best |\n")
            f.write("|------|-----------|----------|----------|----------|-----|\n")
            for r in summary.ranking:
                f.write(f"| {r['rank']} | {r['name']} | {r['accuracy']:.4f} | {r['f1']:.4f} | "
                       f"{'✓' if r['is_baseline'] else ''} | {'✓' if r['is_best'] else ''} |\n")
            
            f.write(f"\n## Importance Scores\n\n")
            if summary.importance_scores:
                for var_id, score in sorted(summary.importance_scores.items(), key=lambda x: abs(x[1]), reverse=True):
                    name = next((r['name'] for r in summary.ranking if r['variation_id'] == var_id), var_id)
                    f.write(f"- **{name}:** {score:+.4f}\n")
            else:
                f.write("No importance scores available\n")
            
            f.write(f"\n## Statistical Tests\n\n")
            if summary.statistical_tests:
                for var_id, test in summary.statistical_tests.items():
                    name = next((r['name'] for r in summary.ranking if r['variation_id'] == var_id), var_id)
                    f.write(f"### {name}\n\n")
                    f.write(f"- **Test:** {test.get('test', 't-test')}\n")
                    f.write(f"- **Statistic:** {test.get('t_statistic', test.get('u_statistic', 0)):.4f}\n")
                    f.write(f"- **p-value:** {test['p_value']:.4f}\n")
                    f.write(f"- **Significant:** {test['significant']}\n\n")
            else:
                f.write("No statistical tests performed\n")
            
            f.write(f"\n## Effect Sizes\n\n")
            if summary.effect_sizes:
                for var_id, effect in sorted(summary.effect_sizes.items(), key=lambda x: abs(x[1]), reverse=True):
                    name = next((r['name'] for r in summary.ranking if r['variation_id'] == var_id), var_id)
                    f.write(f"- **{name}:** {effect:+.4f}\n")
            else:
                f.write("No effect sizes available\n")
        
        self.logger.info(f"Report saved to {report_file}")
        
        # Also generate CSV
        csv_file = self.output_dir / "results.csv"
        self._export_to_csv(csv_file)
    
    def _export_to_csv(self, csv_file: Path) -> None:
        """
        Export results to CSV.
        
        Args:
            csv_file: Path to CSV file
        """
        rows = []
        for result in self.results:
            row = {
                'experiment_id': result.experiment_id,
                'variation_id': result.variation_id,
                'variation_name': result.variation_name,
                'status': result.status.value,
                'duration': result.duration,
                'accuracy': result.test_metrics.get('accuracy', 0),
                'f1': result.test_metrics.get('f1', 0),
                'precision': result.test_metrics.get('precision', 0),
                'recall': result.test_metrics.get('recall', 0),
                'loss': result.test_metrics.get('loss', 0),
                'model_size': result.model_size,
                'inference_time': result.inference_time,
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(csv_file, index=False)
        self.logger.info(f"CSV saved to {csv_file}")
    
    # ============================================
    # Visualization
    # ============================================
    
    def plot_results(self, summary: Optional[AblationSummary] = None) -> None:
        """
        Plot ablation results.
        
        Args:
            summary: Ablation summary (generated if None)
        """
        if summary is None:
            summary = self._generate_summary()
        
        if not summary:
            self.logger.warning("No summary to plot")
            return
        
        data = summary.visualization_data
        
        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
        
        # Create figure with subplots
        fig = plt.figure(figsize=(16, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # Plot 1: Accuracy comparison
        ax1 = fig.add_subplot(gs[0, 0:2])
        colors = ['#2ecc71' if i == 0 else '#3498db' for i in range(len(data['accuracies']))]
        bars = ax1.bar(
            data['variation_names'],
            data['accuracies'],
            yerr=data['accuracy_stds'],
            color=colors,
            capsize=5,
            alpha=0.8
        )
        ax1.set_title('Accuracy Comparison', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Variation', fontsize=12)
        ax1.set_ylabel('Accuracy', fontsize=12)
        ax1.tick_params(axis='x', rotation=45)
        ax1.set_ylim(0, 1)
        ax1.axhline(
            y=data['accuracies'][0],
            color='red',
            linestyle='--',
            alpha=0.5,
            label='Baseline'
        )
        ax1.legend()
        
        # Plot 2: F1 Score comparison
        ax2 = fig.add_subplot(gs[0, 2])
        bars = ax2.bar(
            data['variation_names'],
            data['f1_scores'],
            yerr=data['f1_stds'],
            color=colors,
            capsize=5,
            alpha=0.8
        )
        ax2.set_title('F1 Score Comparison', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Variation', fontsize=12)
        ax2.set_ylabel('F1 Score', fontsize=12)
        ax2.tick_params(axis='x', rotation=45)
        ax2.set_ylim(0, 1)
        ax2.axhline(
            y=data['f1_scores'][0],
            color='red',
            linestyle='--',
            alpha=0.5,
            label='Baseline'
        )
        ax2.legend()
        
        # Plot 3: Importance scores
        ax3 = fig.add_subplot(gs[1, 0])
        if summary.importance_scores:
            var_names = [summary.visualization_data['variation_names'][i] for i in range(1, len(summary.importance_scores) + 1)]
            scores = list(summary.importance_scores.values())
            colors = ['#2ecc71' if s > 0 else '#e74c3c' for s in scores]
            bars = ax3.barh(var_names, scores, color=colors, alpha=0.8)
            ax3.set_title('Feature Importance', fontsize=14, fontweight='bold')
            ax3.set_xlabel('Δ Accuracy', fontsize=12)
            ax3.set_ylabel('Variation', fontsize=12)
            ax3.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        
        # Plot 4: Ranking
        ax4 = fig.add_subplot(gs[1, 1:])
        ranking = summary.ranking
        names = [r['name'] for r in ranking]
        accuracies = [r['accuracy'] for r in ranking]
        colors = ['#2ecc71' if i == 0 else '#3498db' for i in range(len(ranking))]
        bars = ax4.barh(names, accuracies, color=colors, alpha=0.8)
        ax4.set_title('Model Ranking', fontsize=14, fontweight='bold')
        ax4.set_xlabel('Accuracy', fontsize=12)
        ax4.set_xlim(0, 1)
        
        # Add rank labels
        for i, (bar, rank) in enumerate(zip(bars, ranking)):
            ax4.text(
                bar.get_width() + 0.01,
                bar.get_y() + bar.get_height() / 2,
                f'#{rank["rank"]}',
                va='center',
                fontsize=10,
                fontweight='bold'
            )
        
        # Plot 5: Statistical significance
        ax5 = fig.add_subplot(gs[2, 0:2])
        if summary.statistical_tests:
            var_names = []
            p_values = []
            significant = []
            
            for var_id, test in summary.statistical_tests.items():
                name = next((r['name'] for r in ranking if r['variation_id'] == var_id), var_id)
                var_names.append(name)
                p_values.append(test['p_value'])
                significant.append(test['significant'])
            
            colors = ['#2ecc71' if sig else '#e74c3c' for sig in significant]
            bars = ax5.bar(var_names, p_values, color=colors, alpha=0.8)
            ax5.axhline(y=0.05, color='red', linestyle='--', alpha=0.5, label='α=0.05')
            ax5.set_title('Statistical Significance (p-values)', fontsize=14, fontweight='bold')
            ax5.set_xlabel('Variation', fontsize=12)
            ax5.set_ylabel('p-value', fontsize=12)
            ax5.tick_params(axis='x', rotation=45)
            ax5.set_yscale('log')
            ax5.legend()
        
        # Plot 6: Sensitivity analysis
        ax6 = fig.add_subplot(gs[2, 2])
        if summary.sensitivity_analysis:
            var_names = []
            cvs = []
            for var_id, sens in summary.sensitivity_analysis.items():
                name = next((r['name'] for r in ranking if r['variation_id'] == var_id), var_id)
                var_names.append(name)
                cvs.append(sens['cv'])
            
            bars = ax6.bar(var_names, cvs, color='#f39c12', alpha=0.8)
            ax6.set_title('Sensitivity (Coefficient of Variation)', fontsize=14, fontweight='bold')
            ax6.set_xlabel('Variation', fontsize=12)
            ax6.set_ylabel('CV (%)', fontsize=12)
            ax6.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        # Save figure
        plot_file = self.output_dir / "ablation_results.png"
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        self.logger.info(f"Plot saved to {plot_file}")
        
        plt.show()
    
    # ============================================
    # Statistical Analysis
    # ============================================
    
    def perform_statistical_analysis(
        self,
        summary: Optional[AblationSummary] = None
    ) -> Dict[str, Any]:
        """
        Perform statistical analysis on ablation results.
        
        Args:
            summary: Ablation summary (generated if None)
            
        Returns:
            Statistical analysis results
        """
        if summary is None:
            summary = self._generate_summary()
        
        if not summary:
            return {}
        
        analysis = {
            'study_id': self.config.study_id,
            'timestamp': datetime.now().isoformat(),
            'tests': [],
            'significant_results': [],
            'effect_sizes_summary': {},
        }
        
        # Group results by variation
        variation_results = defaultdict(list)
        for result in self.results:
            if result.status == AblationStatus.COMPLETED:
                variation_results[result.variation_id].append(result)
        
        if len(variation_results) < 2:
            return analysis
        
        # Perform ANOVA
        groups = []
        group_names = []
        for var_id, results in variation_results.items():
            accuracies = [r.test_metrics.get('accuracy', 0) for r in results]
            groups.append(accuracies)
            group_names.append(var_id)
        
        # One-way ANOVA
        if len(groups) > 1:
            try:
                f_stat, p_value = f_oneway(*groups)
                analysis['anova'] = {
                    'f_statistic': f_stat,
                    'p_value': p_value,
                    'significant': p_value < 0.05,
                }
            except Exception as e:
                analysis['anova'] = {'error': str(e)}
        
        # Kruskal-Wallis test (non-parametric alternative)
        if len(groups) > 1:
            try:
                h_stat, p_value = kruskal(*groups)
                analysis['kruskal_wallis'] = {
                    'h_statistic': h_stat,
                    'p_value': p_value,
                    'significant': p_value < 0.05,
                }
            except Exception as e:
                analysis['kruskal_wallis'] = {'error': str(e)}
        
        # Pairwise comparisons
        baseline_id = summary.baseline_variation
        if baseline_id and baseline_id in variation_results:
            baseline_results = [
                r.test_metrics.get('accuracy', 0)
                for r in variation_results[baseline_id]
            ]
            
            for var_id, results in variation_results.items():
                if var_id == baseline_id:
                    continue
                
                var_results = [
                    r.test_metrics.get('accuracy', 0)
                    for r in results
                ]
                
                # T-test
                try:
                    t_stat, p_value = ttest_ind(baseline_results, var_results)
                    
                    test_result = {
                        'variation': var_id,
                        'baseline': baseline_id,
                        'test': 't-test',
                        'statistic': t_stat,
                        'p_value': p_value,
                        'significant': p_value < 0.05,
                        'effect_size': summary.effect_sizes.get(var_id, 0),
                    }
                    analysis['tests'].append(test_result)
                    
                    if p_value < 0.05:
                        analysis['significant_results'].append(test_result)
                except Exception as e:
                    analysis['tests'].append({
                        'variation': var_id,
                        'baseline': baseline_id,
                        'test': 't-test',
                        'error': str(e),
                    })
                
                # Wilcoxon test (non-parametric)
                try:
                    if len(baseline_results) > 1 and len(var_results) > 1:
                        w_stat, p_value = wilcoxon(baseline_results[:len(var_results)], var_results)
                        analysis['tests'].append({
                            'variation': var_id,
                            'baseline': baseline_id,
                            'test': 'wilcoxon',
                            'statistic': w_stat,
                            'p_value': p_value,
                            'significant': p_value < 0.05,
                        })
                except Exception as e:
                    pass
        
        # Summarize effect sizes
        analysis['effect_sizes_summary'] = {
            'mean': np.mean(list(summary.effect_sizes.values())) if summary.effect_sizes else 0,
            'std': np.std(list(summary.effect_sizes.values())) if summary.effect_sizes else 0,
            'min': min(summary.effect_sizes.values()) if summary.effect_sizes else 0,
            'max': max(summary.effect_sizes.values()) if summary.effect_sizes else 0,
        }
        
        return analysis


# ============================================
# Ablation Study Factory
# ============================================

class AblationStudyFactory:
    """
    Factory for creating ablation studies.
    """
    
    @staticmethod
    def create_component_ablation(
        name: str,
        base_config: Dict[str, Any],
        components: Dict[str, Any],
        metrics: List[str] = None,
        **kwargs
    ) -> AblationStudy:
        """
        Create a component ablation study.
        
        Args:
            name: Study name
            base_config: Base configuration
            components: Dictionary of components to ablate
            metrics: Metrics to track
            **kwargs: Additional configuration
            
        Returns:
            AblationStudy instance
        """
        variations = []
        for comp_name, comp_config in components.items():
            # Create variation that removes the component
            variation = {
                'name': f"Remove {comp_name}",
                'changes': {comp_name: comp_config},
                'metadata': {'component': comp_name}
            }
            variations.append(variation)
        
        config = AblationConfig(
            study_id=f"ablation_component_{int(time.time())}",
            name=name,
            description=f"Component ablation study for {name}",
            ablation_type=AblationType.COMPONENT,
            base_config=base_config,
            variations=variations,
            metrics=metrics or ['accuracy', 'f1', 'precision', 'recall'],
            **kwargs
        )
        
        return AblationStudy(config)
    
    @staticmethod
    def create_hyperparameter_ablation(
        name: str,
        base_config: Dict[str, Any],
        hyperparams: Dict[str, List[Any]],
        metrics: List[str] = None,
        **kwargs
    ) -> AblationStudy:
        """
        Create a hyperparameter ablation study.
        
        Args:
            name: Study name
            base_config: Base configuration
            hyperparams: Dictionary of hyperparameters to vary
            metrics: Metrics to track
            **kwargs: Additional configuration
            
        Returns:
            AblationStudy instance
        """
        variations = []
        for param_name, values in hyperparams.items():
            for value in values:
                variations.append({
                    'name': f"{param_name}={value}",
                    'changes': {param_name: value},
                    'metadata': {'parameter': param_name, 'value': value}
                })
        
        config = AblationConfig(
            study_id=f"ablation_hyperparam_{int(time.time())}",
            name=name,
            description=f"Hyperparameter ablation study for {name}",
            ablation_type=AblationType.HYPERPARAMETER,
            base_config=base_config,
            variations=variations,
            metrics=metrics or ['accuracy', 'f1', 'precision', 'recall'],
            **kwargs
        )
        
        return AblationStudy(config)
    
    @staticmethod
    def create_feature_ablation(
        name: str,
        base_config: Dict[str, Any],
        features: Dict[str, bool],
        metrics: List[str] = None,
        **kwargs
    ) -> AblationStudy:
        """
        Create a feature ablation study.
        
        Args:
            name: Study name
            base_config: Base configuration
            features: Dictionary of features to include/exclude
            metrics: Metrics to track
            **kwargs: Additional configuration
            
        Returns:
            AblationStudy instance
        """
        variations = []
        for fname, include in features.items():
            variations.append({
                'name': f"Feature: {fname} ({'include' if include else 'exclude'})",
                'changes': {'features': {fname: include}},
                'metadata': {'feature': fname, 'include': include}
            })
        
        config = AblationConfig(
            study_id=f"ablation_feature_{int(time.time())}",
            name=name,
            description=f"Feature ablation study for {name}",
            ablation_type=AblationType.FEATURE,
            base_config=base_config,
            variations=variations,
            metrics=metrics or ['accuracy', 'f1', 'precision', 'recall'],
            **kwargs
        )
        
        return AblationStudy(config)
    
    @staticmethod
    def create_architecture_ablation(
        name: str,
        base_config: Dict[str, Any],
        layer_configs: List[Dict[str, Any]],
        metrics: List[str] = None,
        **kwargs
    ) -> AblationStudy:
        """
        Create an architecture ablation study.
        
        Args:
            name: Study name
            base_config: Base configuration
            layer_configs: List of layer configurations
            metrics: Metrics to track
            **kwargs: Additional configuration
            
        Returns:
            AblationStudy instance
        """
        variations = []
        for i, config in enumerate(layer_configs):
            variations.append({
                'name': f"Layer config {i+1}",
                'changes': {'layers': config},
                'metadata': {'layer_config': i}
            })
        
        config = AblationConfig(
            study_id=f"ablation_arch_{int(time.time())}",
            name=name,
            description=f"Architecture ablation study for {name}",
            ablation_type=AblationType.ARCHITECTURE,
            base_config=base_config,
            variations=variations,
            metrics=metrics or ['accuracy', 'f1', 'precision', 'recall'],
            **kwargs
        )
        
        return AblationStudy(config)
    
    @staticmethod
    def create_interaction_ablation(
        name: str,
        base_config: Dict[str, Any],
        factors: Dict[str, List[Any]],
        metrics: List[str] = None,
        **kwargs
    ) -> AblationStudy:
        """
        Create an interaction ablation study.
        
        Args:
            name: Study name
            base_config: Base configuration
            factors: Dictionary of factors to vary
            metrics: Metrics to track
            **kwargs: Additional configuration
            
        Returns:
            AblationStudy instance
        """
        # Generate all combinations of factors
        factor_names = list(factors.keys())
        factor_values = list(factors.values())
        combinations = list(itertools.product(*factor_values))
        
        variations = []
        for combo in combinations:
            changes = {}
            metadata = {}
            for i, factor_name in enumerate(factor_names):
                changes[factor_name] = combo[i]
                metadata[factor_name] = combo[i]
            
            variations.append({
                'name': f"{', '.join([f'{n}={v}' for n, v in zip(factor_names, combo)])}",
                'changes': changes,
                'metadata': metadata
            })
        
        config = AblationConfig(
            study_id=f"ablation_interaction_{int(time.time())}",
            name=name,
            description=f"Interaction ablation study for {name}",
            ablation_type=AblationType.INTERACTION,
            base_config=base_config,
            variations=variations,
            metrics=metrics or ['accuracy', 'f1', 'precision', 'recall'],
            interaction_analysis=True,
            **kwargs
        )
        
        return AblationStudy(config)


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point."""
    import argparse
    import signal
    
    parser = argparse.ArgumentParser(description='NEXUS Ablation Study Tool')
    parser.add_argument('--config', type=str, help='Configuration file path')
    parser.add_argument('--study-id', type=str, help='Study identifier')
    parser.add_argument('--list', action='store_true', help='List available studies')
    parser.add_argument('--plot', action='store_true', help='Plot results')
    parser.add_argument('--analyze', action='store_true', help='Perform statistical analysis')
    parser.add_argument('--export', type=str, help='Export results to file')
    parser.add_argument('--output-dir', type=str, default='./results/ablation', help='Output directory')
    parser.add_argument('--parallel', action='store_true', help='Run experiments in parallel')
    parser.add_argument('--n-jobs', type=int, default=4, help='Number of parallel jobs')
    parser.add_argument('--repetitions', type=int, default=3, help='Number of repetitions per variation')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--log-level', type=str, default='INFO', help='Logging level')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Signal handling
    def signal_handler(sig, frame):
        print("\nInterrupted by user")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.list:
        # List available studies
        studies = Path(args.output_dir).glob('*/summary.json')
        print("Available Ablation Studies:")
        print("-" * 50)
        for study_file in studies:
            try:
                with open(study_file, 'r') as f:
                    data = json.load(f)
                    print(f"ID: {data.get('study_id', study_file.parent.name)}")
                    print(f"  Name: {data.get('name', 'N/A')}")
                    print(f"  Type: {data.get('ablation_type', 'N/A')}")
                    print(f"  Experiments: {data.get('total_experiments', 0)}")
                    print(f"  Best: {data.get('best_variation', 'N/A')}")
                    print()
            except Exception as e:
                print(f"Error reading {study_file}: {e}")
        return
    
    if args.config:
        # Load configuration
        with open(args.config, 'r') as f:
            config_data = json.load(f)
        
        config = AblationConfig(
            study_id=config_data.get('study_id', f"ablation_{int(time.time())}"),
            name=config_data.get('name', 'Ablation Study'),
            description=config_data.get('description', ''),
            ablation_type=AblationType(config_data.get('ablation_type', 'component')),
            base_config=config_data.get('base_config', {}),
            variations=config_data.get('variations', []),
            metrics=config_data.get('metrics', ['accuracy', 'f1']),
            repetitions=config_data.get('repetitions', args.repetitions),
            random_seed=config_data.get('random_seed', args.seed),
            n_jobs=config_data.get('n_jobs', args.n_jobs),
            parallel=config_data.get('parallel', args.parallel),
            save_results=config_data.get('save_results', True),
            output_dir=args.output_dir,
            cross_validation_folds=config_data.get('cross_validation_folds', 5),
            use_bayesian=config_data.get('use_bayesian', False),
            interaction_analysis=config_data.get('interaction_analysis', False),
            metadata=config_data.get('metadata', {}),
        )
        
        # Run study
        study = AblationStudy(config)
        study.run()
        
        if args.plot:
            summary = study._generate_summary()
            study.plot_results(summary)
        
        if args.analyze:
            summary = study._generate_summary()
            analysis = study.perform_statistical_analysis(summary)
            print(json.dumps(analysis, indent=2))
        
        if args.export:
            study._generate_report()
            print(f"Results exported to {args.export}")
        
        return
    
    # Interactive mode
    print("NEXUS Ablation Study Tool")
    print("==========================")
    print()
    print("1. Run component ablation")
    print("2. Run hyperparameter ablation")
    print("3. Run feature ablation")
    print("4. Run architecture ablation")
    print("5. Run interaction ablation")
    print("6. View results")
    print("7. View summary")
    print("8. Export results")
    print("9. Exit")
    
    while True:
        choice = input("\nSelect option: ")
        
        if choice == '1':
            # Component ablation
            name = input("Study name: ")
            base_config = {}
            components = {}
            print("Add components (empty name to finish)")
            while True:
                comp_name = input("Component name: ")
                if not comp_name:
                    break
                comp_config = input("Component config (JSON): ")
                try:
                    components[comp_name] = json.loads(comp_config) if comp_config else {}
                except:
                    components[comp_name] = {}
            
            study = AblationStudyFactory.create_component_ablation(
                name=name,
                base_config=base_config,
                components=components,
                n_jobs=args.n_jobs,
                parallel=args.parallel,
                repetitions=args.repetitions,
                random_seed=args.seed,
                output_dir=args.output_dir,
            )
            study.run()
            
        elif choice == '2':
            # Hyperparameter ablation
            name = input("Study name: ")
            base_config = {}
            hyperparams = {}
            print("Add hyperparameters (empty name to finish)")
            while True:
                param_name = input("Parameter name: ")
                if not param_name:
                    break
                values_str = input("Values (comma-separated): ")
                values = [v.strip() for v in values_str.split(',')]
                # Convert to appropriate types
                converted = []
                for v in values:
                    try:
                        if '.' in v:
                            converted.append(float(v))
                        else:
                            converted.append(int(v))
                    except:
                        converted.append(v)
                hyperparams[param_name] = converted
            
            study = AblationStudyFactory.create_hyperparameter_ablation(
                name=name,
                base_config=base_config,
                hyperparams=hyperparams,
                n_jobs=args.n_jobs,
                parallel=args.parallel,
                repetitions=args.repetitions,
                random_seed=args.seed,
                output_dir=args.output_dir,
            )
            study.run()
            
        elif choice == '3':
            # Feature ablation
            name = input("Study name: ")
            base_config = {}
            features = {}
            print("Add features (empty name to finish)")
            while True:
                fname = input("Feature name: ")
                if not fname:
                    break
                include = input("Include? (y/n): ").lower() == 'y'
                features[fname] = include
            
            study = AblationStudyFactory.create_feature_ablation(
                name=name,
                base_config=base_config,
                features=features,
                n_jobs=args.n_jobs,
                parallel=args.parallel,
                repetitions=args.repetitions,
                random_seed=args.seed,
                output_dir=args.output_dir,
            )
            study.run()
            
        elif choice == '4':
            # Architecture ablation
            name = input("Study name: ")
            base_config = {}
            layer_configs = []
            print("Add layer configurations (empty to finish)")
            while True:
                config_str = input("Layer config (JSON): ")
                if not config_str:
                    break
                try:
                    layer_configs.append(json.loads(config_str))
                except:
                    print("Invalid JSON, skipping")
            
            study = AblationStudyFactory.create_architecture_ablation(
                name=name,
                base_config=base_config,
                layer_configs=layer_configs,
                n_jobs=args.n_jobs,
                parallel=args.parallel,
                repetitions=args.repetitions,
                random_seed=args.seed,
                output_dir=args.output_dir,
            )
            study.run()
            
        elif choice == '5':
            # Interaction ablation
            name = input("Study name: ")
            base_config = {}
            factors = {}
            print("Add factors (empty name to finish)")
            while True:
                factor_name = input("Factor name: ")
                if not factor_name:
                    break
                values_str = input("Values (comma-separated): ")
                values = [v.strip() for v in values_str.split(',')]
                converted = []
                for v in values:
                    try:
                        if '.' in v:
                            converted.append(float(v))
                        else:
                            converted.append(int(v))
                    except:
                        converted.append(v)
                factors[factor_name] = converted
            
            study = AblationStudyFactory.create_interaction_ablation(
                name=name,
                base_config=base_config,
                factors=factors,
                n_jobs=args.n_jobs,
                parallel=args.parallel,
                repetitions=args.repetitions,
                random_seed=args.seed,
                output_dir=args.output_dir,
                interaction_analysis=True,
            )
            study.run()
            
        elif choice == '6':
            # View results
            study_id = input("Study ID: ")
            study_path = Path(args.output_dir) / study_id
            results_file = study_path / "results.json"
            if results_file.exists():
                with open(results_file, 'r') as f:
                    data = json.load(f)
                    print(f"Study: {data.get('name', 'N/A')}")
                    print(f"Total experiments: {data.get('total_experiments', 0)}")
                    print(f"Completed: {data.get('completed_experiments', 0)}")
                    print(f"Failed: {data.get('failed_experiments', 0)}")
            else:
                print("Study not found")
            
        elif choice == '7':
            # View summary
            study_id = input("Study ID: ")
            study_path = Path(args.output_dir) / study_id
            summary_file = study_path / "summary.json"
            if summary_file.exists():
                with open(summary_file, 'r') as f:
                    data = json.load(f)
                    print(f"Study: {data.get('name', 'N/A')}")
                    print(f"Best variation: {data.get('best_variation', 'N/A')}")
                    print(f"Baseline: {data.get('baseline_variation', 'N/A')}")
                    print("\nRanking:")
                    for r in data.get('ranking', []):
                        print(f"  #{r['rank']}: {r['name']} - Accuracy: {r['accuracy']:.4f}")
            else:
                print("Study not found")
            
        elif choice == '8':
            # Export results
            study_id = input("Study ID: ")
            study_path = Path(args.output_dir) / study_id
            if study_path.exists():
                # Generate report
                config = AblationConfig(
                    study_id=study_id,
                    name="",
                    description="",
                    ablation_type=AblationType.CUSTOM,
                    base_config={},
                    variations=[],
                    metrics=[],
                )
                study = AblationStudy(config)
                study.results = study.load_results()
                study._generate_report()
                print(f"Results exported to {study_path}")
            else:
                print("Study not found")
            
        elif choice == '9':
            print("Exiting...")
            break
        
        else:
            print("Invalid choice")


if __name__ == '__main__':
    main()

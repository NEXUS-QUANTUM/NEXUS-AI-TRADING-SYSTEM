"""
NEXUS AI TRADING SYSTEM - Results Comparator Module
Copyright © 2026 NEXUS QUANTUM LTD

This module provides comprehensive results comparison capabilities including:
- Multi-experiment comparison
- Statistical significance testing
- Performance visualization
- Ranking and selection
- Confidence interval calculation
- Effect size analysis
- Pairwise comparison
- ANOVA and post-hoc tests
- Metric aggregation
- Visualization of results
- Report generation
- Export to multiple formats
- Interactive comparison dashboard
- Reproducibility validation
- Outlier detection
- Trend analysis
- Correlation analysis
- Sensitivity analysis
- Benchmark comparison
- Historical comparison
- Multi-metric evaluation
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
import warnings
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
from scipy.stats import (
    ttest_ind, ttest_rel, mannwhitneyu, wilcoxon, 
    f_oneway, kruskal, chi2_contingency,
    pearsonr, spearmanr, pointbiserialr
)
from scipy.stats import norm, sem, t
from scipy import integrate
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import torch
import torch.nn as nn
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
        logging.FileHandler('logs/results_comparator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class ComparisonType(Enum):
    """Types of comparisons."""
    PAIRWISE = "pairwise"
    MULTI_GROUP = "multi_group"
    BEFORE_AFTER = "before_after"
    TIME_SERIES = "time_series"
    CROSS_VALIDATION = "cross_validation"
    ENSEMBLE = "ensemble"
    BENCHMARK = "benchmark"


class StatisticalTest(Enum):
    """Statistical tests for comparison."""
    T_TEST = "t_test"
    WELCH_T_TEST = "welch_t_test"
    PAIRED_T_TEST = "paired_t_test"
    MANN_WHITNEY = "mann_whitney"
    WILCOXON = "wilcoxon"
    ANOVA = "anova"
    KRUSKAL_WALLIS = "kruskal_wallis"
    CHI_SQUARE = "chi_square"
    FRIEDMAN = "friedman"
    BAYESIAN = "bayesian"


class EffectSize(Enum):
    """Effect size measures."""
    COHENS_D = "cohens_d"
    HEDGES_G = "hedges_g"
    GLASS_DELTA = "glass_delta"
    RANK_BISERIAL = "rank_biserial"
    CLIFFS_DELTA = "cliffs_delta"
    ETA_SQUARED = "eta_squared"
    OMEGA_SQUARED = "omega_squared"


@dataclass
class ComparisonResult:
    """Result of a comparison."""
    comparison_id: str
    type: ComparisonType
    name: str
    description: str
    groups: Dict[str, List[float]]
    statistics: Dict[str, Any]
    effect_sizes: Dict[str, float]
    p_values: Dict[str, float]
    confidence_intervals: Dict[str, Tuple[float, float]]
    rankings: Dict[str, int]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonConfig:
    """Configuration for comparison."""
    comparison_id: str
    name: str
    description: str
    type: ComparisonType
    groups: Dict[str, Any]
    metrics: List[str]
    statistical_tests: List[StatisticalTest]
    significance_level: float = 0.05
    correction_method: str = "bonferroni"  # "bonferroni", "holm", "fdr"
    n_bootstrap: int = 1000
    random_seed: int = 42
    output_dir: str = "./results/comparisons"
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================
# Results Comparator Implementation
# ============================================

class ResultsComparator:
    """
    Comprehensive results comparison engine.
    
    This class manages comparison of experiment results including
    statistical testing, visualization, and reporting.
    """
    
    def __init__(self, config: ComparisonConfig):
        """
        Initialize the results comparator.
        
        Args:
            config: Comparison configuration
        """
        self.config = config
        self.results: Optional[ComparisonResult] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # Create output directory
        self.output_dir = Path(config.output_dir) / config.comparison_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set random seed
        np.random.seed(config.random_seed)
        
        self.logger = logging.getLogger(f"comparator.{config.comparison_id}")
        self.logger.info(f"Initialized results comparator: {config.name}")
        self.logger.info(f"Groups: {len(config.groups)}")
        self.logger.info(f"Metrics: {config.metrics}")
        self.logger.info(f"Tests: {[t.value for t in config.statistical_tests]}")
    
    # ============================================
    # Data Preparation
    # ============================================
    
    def prepare_data(self, data: Dict[str, Any]) -> Dict[str, List[float]]:
        """
        Prepare data for comparison.
        
        Args:
            data: Raw data
            
        Returns:
            Prepared data dictionary
        """
        prepared = {}
        
        for group_name, group_data in data.items():
            if isinstance(group_data, list):
                prepared[group_name] = group_data
            elif isinstance(group_data, dict):
                # Extract metrics
                if self.config.metrics:
                    values = []
                    for item in group_data:
                        if isinstance(item, dict):
                            for metric in self.config.metrics:
                                if metric in item:
                                    values.append(item[metric])
                        else:
                            values.append(item)
                    prepared[group_name] = values
                else:
                    prepared[group_name] = list(group_data.values())
            else:
                prepared[group_name] = [group_data]
        
        return prepared
    
    # ============================================
    # Statistical Tests
    # ============================================
    
    def run_statistical_tests(
        self,
        data: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Run statistical tests on the data.
        
        Args:
            data: Prepared data
            
        Returns:
            Test results
        """
        results = {}
        group_names = list(data.keys())
        
        if len(group_names) < 2:
            return results
        
        for test in self.config.statistical_tests:
            if test == StatisticalTest.T_TEST:
                results['t_test'] = self._run_ttest(data)
            elif test == StatisticalTest.WELCH_T_TEST:
                results['welch_t_test'] = self._run_welch_ttest(data)
            elif test == StatisticalTest.PAIRED_T_TEST:
                results['paired_t_test'] = self._run_paired_ttest(data)
            elif test == StatisticalTest.MANN_WHITNEY:
                results['mann_whitney'] = self._run_mann_whitney(data)
            elif test == StatisticalTest.WILCOXON:
                results['wilcoxon'] = self._run_wilcoxon(data)
            elif test == StatisticalTest.ANOVA:
                results['anova'] = self._run_anova(data)
            elif test == StatisticalTest.KRUSKAL_WALLIS:
                results['kruskal_wallis'] = self._run_kruskal_wallis(data)
            elif test == StatisticalTest.CHI_SQUARE:
                results['chi_square'] = self._run_chi_square(data)
            elif test == StatisticalTest.FRIEDMAN:
                results['friedman'] = self._run_friedman(data)
            elif test == StatisticalTest.BAYESIAN:
                results['bayesian'] = self._run_bayesian(data)
        
        return results
    
    def _run_ttest(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Run independent t-test.
        
        Args:
            data: Prepared data
            
        Returns:
            T-test results
        """
        group_names = list(data.keys())
        results = {}
        
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                data1 = data[group1]
                data2 = data[group2]
                
                if len(data1) > 1 and len(data2) > 1:
                    stat, p = ttest_ind(data1, data2)
                    key = f"{group1}_vs_{group2}"
                    results[key] = {
                        'statistic': stat,
                        'p_value': p,
                        'significant': p < self.config.significance_level,
                        'group1': group1,
                        'group2': group2,
                        'n1': len(data1),
                        'n2': len(data2),
                        'mean1': np.mean(data1),
                        'mean2': np.mean(data2),
                        'std1': np.std(data1),
                        'std2': np.std(data2),
                    }
        
        return results
    
    def _run_welch_ttest(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Run Welch's t-test (unequal variance)."""
        group_names = list(data.keys())
        results = {}
        
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                data1 = data[group1]
                data2 = data[group2]
                
                if len(data1) > 1 and len(data2) > 1:
                    stat, p = ttest_ind(data1, data2, equal_var=False)
                    key = f"{group1}_vs_{group2}"
                    results[key] = {
                        'statistic': stat,
                        'p_value': p,
                        'significant': p < self.config.significance_level,
                        'group1': group1,
                        'group2': group2,
                        'n1': len(data1),
                        'n2': len(data2),
                        'mean1': np.mean(data1),
                        'mean2': np.mean(data2),
                    }
        
        return results
    
    def _run_paired_ttest(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Run paired t-test."""
        group_names = list(data.keys())
        results = {}
        
        if len(group_names) != 2:
            return results
        
        group1 = group_names[0]
        group2 = group_names[1]
        data1 = data[group1]
        data2 = data[group2]
        
        if len(data1) > 1 and len(data2) > 1 and len(data1) == len(data2):
            stat, p = ttest_rel(data1, data2)
            results[f"{group1}_vs_{group2}"] = {
                'statistic': stat,
                'p_value': p,
                'significant': p < self.config.significance_level,
                'group1': group1,
                'group2': group2,
                'n': len(data1),
                'mean1': np.mean(data1),
                'mean2': np.mean(data2),
                'diff': np.mean(np.array(data1) - np.array(data2)),
            }
        
        return results
    
    def _run_mann_whitney(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Run Mann-Whitney U test."""
        group_names = list(data.keys())
        results = {}
        
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                data1 = data[group1]
                data2 = data[group2]
                
                if len(data1) > 1 and len(data2) > 1:
                    stat, p = mannwhitneyu(data1, data2, alternative='two-sided')
                    key = f"{group1}_vs_{group2}"
                    results[key] = {
                        'statistic': stat,
                        'p_value': p,
                        'significant': p < self.config.significance_level,
                        'group1': group1,
                        'group2': group2,
                        'n1': len(data1),
                        'n2': len(data2),
                        'median1': np.median(data1),
                        'median2': np.median(data2),
                    }
        
        return results
    
    def _run_wilcoxon(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Run Wilcoxon signed-rank test."""
        group_names = list(data.keys())
        results = {}
        
        if len(group_names) != 2:
            return results
        
        group1 = group_names[0]
        group2 = group_names[1]
        data1 = data[group1]
        data2 = data[group2]
        
        if len(data1) > 1 and len(data2) > 1 and len(data1) == len(data2):
            stat, p = wilcoxon(data1, data2)
            results[f"{group1}_vs_{group2}"] = {
                'statistic': stat,
                'p_value': p,
                'significant': p < self.config.significance_level,
                'group1': group1,
                'group2': group2,
                'n': len(data1),
                'median1': np.median(data1),
                'median2': np.median(data2),
            }
        
        return results
    
    def _run_anova(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Run one-way ANOVA."""
        group_names = list(data.keys())
        groups = [data[group] for group in group_names]
        
        if len(groups) < 2:
            return {}
        
        # Check if all groups have at least 2 samples
        if any(len(g) < 2 for g in groups):
            return {'error': 'All groups must have at least 2 samples'}
        
        try:
            stat, p = f_oneway(*groups)
            return {
                'f_statistic': stat,
                'p_value': p,
                'significant': p < self.config.significance_level,
                'groups': group_names,
                'n': [len(g) for g in groups],
                'means': [np.mean(g) for g in groups],
                'stds': [np.std(g) for g in groups],
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _run_kruskal_wallis(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Run Kruskal-Wallis H test."""
        group_names = list(data.keys())
        groups = [data[group] for group in group_names]
        
        if len(groups) < 2:
            return {}
        
        try:
            stat, p = kruskal(*groups)
            return {
                'h_statistic': stat,
                'p_value': p,
                'significant': p < self.config.significance_level,
                'groups': group_names,
                'n': [len(g) for g in groups],
                'medians': [np.median(g) for g in groups],
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _run_chi_square(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Run chi-square test."""
        group_names = list(data.keys())
        
        if len(group_names) < 2:
            return {}
        
        # Convert to categories for chi-square
        # For simplicity, bin the data
        all_values = []
        for group in data.values():
            all_values.extend(group)
        
        if len(all_values) < 10:
            return {'error': 'Not enough data for chi-square test'}
        
        try:
            # Create contingency table
            bins = np.histogram_bin_edges(all_values, bins='auto')
            contingency = []
            for group in group_names:
                hist, _ = np.histogram(data[group], bins=bins)
                contingency.append(hist)
            
            chi2, p, dof, expected = chi2_contingency(contingency)
            
            return {
                'chi2_statistic': chi2,
                'p_value': p,
                'significant': p < self.config.significance_level,
                'dof': dof,
                'groups': group_names,
                'expected': expected.tolist(),
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _run_friedman(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """Run Friedman test (non-parametric repeated measures)."""
        group_names = list(data.keys())
        groups = [data[group] for group in group_names]
        
        if len(groups) < 2:
            return {}
        
        # Check if all groups have same length
        lengths = [len(g) for g in groups]
        if len(set(lengths)) != 1:
            return {'error': 'All groups must have the same length'}
        
        try:
            from scipy.stats import friedmanchisquare
            stat, p = friedmanchisquare(*groups)
            return {
                'statistic': stat,
                'p_value': p,
                'significant': p < self.config.significance_level,
                'groups': group_names,
                'n': len(groups[0]),
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _run_bayesian(self, data: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Run Bayesian analysis.
        
        Args:
            data: Prepared data
            
        Returns:
            Bayesian analysis results
        """
        group_names = list(data.keys())
        results = {}
        
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                data1 = data[group1]
                data2 = data[group2]
                
                if len(data1) > 1 and len(data2) > 1:
                    # Simple Bayesian comparison
                    # Estimate posterior probability that mean1 > mean2
                    n1, n2 = len(data1), len(data2)
                    mean1, mean2 = np.mean(data1), np.mean(data2)
                    std1, std2 = np.std(data1), np.std(data2)
                    
                    # Use Bayesian t-test approximation
                    pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
                    effect = (mean1 - mean2) / pooled_std
                    
                    # Compute posterior probability (simplified)
                    # Using normal approximation
                    se = pooled_std * np.sqrt(1/n1 + 1/n2)
                    posterior_mean = effect / se
                    
                    # Probability that effect > 0
                    p_effect = 1 - norm.cdf(0, posterior_mean, 1)
                    
                    key = f"{group1}_vs_{group2}"
                    results[key] = {
                        'effect_size': effect,
                        'posterior_mean': posterior_mean,
                        'p_effect_positive': p_effect,
                        'p_effect_negative': 1 - p_effect,
                        'group1': group1,
                        'group2': group2,
                        'n1': n1,
                        'n2': n2,
                        'mean1': mean1,
                        'mean2': mean2,
                    }
        
        return results
    
    # ============================================
    # Effect Size Calculation
    # ============================================
    
    def calculate_effect_sizes(
        self,
        data: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Calculate effect sizes for comparisons.
        
        Args:
            data: Prepared data
            
        Returns:
            Effect size results
        """
        effect_sizes = {}
        group_names = list(data.keys())
        
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                data1 = data[group1]
                data2 = data[group2]
                key = f"{group1}_vs_{group2}"
                
                effect_sizes[key] = {
                    'cohens_d': self._cohens_d(data1, data2),
                    'hedges_g': self._hedges_g(data1, data2),
                    'glass_delta': self._glass_delta(data1, data2),
                    'rank_biserial': self._rank_biserial(data1, data2),
                    'cliffs_delta': self._cliffs_delta(data1, data2),
                    'eta_squared': self._eta_squared(data1, data2),
                }
        
        return effect_sizes
    
    def _cohens_d(self, data1: List[float], data2: List[float]) -> float:
        """Calculate Cohen's d effect size."""
        n1, n2 = len(data1), len(data2)
        mean1, mean2 = np.mean(data1), np.mean(data2)
        std1, std2 = np.std(data1), np.std(data2)
        
        pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
        if pooled_std == 0:
            return 0
        
        return (mean1 - mean2) / pooled_std
    
    def _hedges_g(self, data1: List[float], data2: List[float]) -> float:
        """Calculate Hedges' g effect size."""
        d = self._cohens_d(data1, data2)
        n1, n2 = len(data1), len(data2)
        correction = 1 - 3 / (4 * (n1 + n2) - 9)
        return d * correction
    
    def _glass_delta(self, data1: List[float], data2: List[float]) -> float:
        """Calculate Glass's delta effect size."""
        mean1, mean2 = np.mean(data1), np.mean(data2)
        std1 = np.std(data1)
        if std1 == 0:
            return 0
        return (mean1 - mean2) / std1
    
    def _rank_biserial(self, data1: List[float], data2: List[float]) -> float:
        """Calculate rank-biserial correlation effect size."""
        from scipy.stats import rankdata
        
        combined = data1 + data2
        ranks = rankdata(combined)
        n1, n2 = len(data1), len(data2)
        
        # Mean rank for each group
        mean_rank1 = np.mean(ranks[:n1])
        mean_rank2 = np.mean(ranks[n1:])
        
        return 2 * (mean_rank1 - mean_rank2) / (n1 + n2)
    
    def _cliffs_delta(self, data1: List[float], data2: List[float]) -> float:
        """Calculate Cliff's delta effect size."""
        n1, n2 = len(data1), len(data2)
        if n1 == 0 or n2 == 0:
            return 0
        
        # Count pairs where x > y and x < y
        greater = 0
        less = 0
        for x in data1:
            for y in data2:
                if x > y:
                    greater += 1
                elif x < y:
                    less += 1
        
        return (greater - less) / (n1 * n2)
    
    def _eta_squared(self, data1: List[float], data2: List[float]) -> float:
        """Calculate eta-squared effect size."""
        # For two groups, eta-squared is equivalent to squared Cohen's d
        d = self._cohens_d(data1, data2)
        return d**2 / (d**2 + 4)
    
    # ============================================
    # Confidence Intervals
    # ============================================
    
    def calculate_confidence_intervals(
        self,
        data: Dict[str, List[float]],
        confidence_level: float = 0.95
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate confidence intervals for each group.
        
        Args:
            data: Prepared data
            confidence_level: Confidence level
            
        Returns:
            Confidence intervals
        """
        intervals = {}
        
        for group_name, values in data.items():
            if not values:
                continue
            
            mean = np.mean(values)
            std = np.std(values)
            n = len(values)
            
            # Standard error
            se = std / np.sqrt(n)
            
            # Critical value for t distribution
            dof = n - 1
            t_critical = t.ppf((1 + confidence_level) / 2, dof)
            
            margin = t_critical * se
            intervals[group_name] = (mean - margin, mean + margin)
        
        return intervals
    
    # ============================================
    # Ranking
    # ============================================
    
    def rank_groups(
        self,
        data: Dict[str, List[float]],
        metric: str = "mean",
        ascending: bool = False
    ) -> Dict[str, int]:
        """
        Rank groups based on performance.
        
        Args:
            data: Prepared data
            metric: Metric to rank by ("mean", "median", "max", "min")
            ascending: Sort ascending
            
        Returns:
            Rankings
        """
        if metric == "mean":
            scores = {k: np.mean(v) for k, v in data.items()}
        elif metric == "median":
            scores = {k: np.median(v) for k, v in data.items()}
        elif metric == "max":
            scores = {k: np.max(v) for k, v in data.items()}
        elif metric == "min":
            scores = {k: np.min(v) for k, v in data.items()}
        else:
            scores = {k: np.mean(v) for k, v in data.items()}
        
        sorted_groups = sorted(scores.items(), key=lambda x: x[1], reverse=not ascending)
        rankings = {}
        for i, (group, _) in enumerate(sorted_groups):
            rankings[group] = i + 1
        
        return rankings
    
    # ============================================
    # Comparison Execution
    # ============================================
    
    def compare(self, data: Dict[str, Any]) -> ComparisonResult:
        """
        Run the comparison.
        
        Args:
            data: Data to compare
            
        Returns:
            Comparison result
        """
        self.start_time = time.time()
        
        self.logger.info(f"Starting comparison: {self.config.name}")
        
        # Prepare data
        prepared_data = self.prepare_data(data)
        
        # Run statistical tests
        statistics = self.run_statistical_tests(prepared_data)
        
        # Calculate effect sizes
        effect_sizes = self.calculate_effect_sizes(prepared_data)
        
        # Calculate confidence intervals
        confidence_intervals = self.calculate_confidence_intervals(prepared_data)
        
        # Rank groups
        rankings = self.rank_groups(prepared_data)
        
        # Extract p-values
        p_values = {}
        for test_name, test_results in statistics.items():
            if isinstance(test_results, dict):
                for key, result in test_results.items():
                    if isinstance(result, dict) and 'p_value' in result:
                        p_values[f"{test_name}_{key}"] = result['p_value']
        
        # Apply multiple comparison correction
        if self.config.correction_method != "none":
            p_values = self._apply_correction(p_values)
        
        # Create result
        result = ComparisonResult(
            comparison_id=self.config.comparison_id,
            type=self.config.type,
            name=self.config.name,
            description=self.config.description,
            groups=prepared_data,
            statistics=statistics,
            effect_sizes=effect_sizes,
            p_values=p_values,
            confidence_intervals=confidence_intervals,
            rankings=rankings,
            timestamp=time.time(),
            metadata=self.config.metadata,
        )
        
        self.results = result
        self.end_time = time.time()
        
        # Save results
        self._save_results()
        self._generate_summary()
        self._plot_results()
        
        self.logger.info(f"Comparison completed in {self.end_time - self.start_time:.2f}s")
        
        return result
    
    def _apply_correction(self, p_values: Dict[str, float]) -> Dict[str, float]:
        """
        Apply multiple comparison correction to p-values.
        
        Args:
            p_values: Dictionary of p-values
            
        Returns:
            Corrected p-values
        """
        if not p_values:
            return p_values
        
        p_list = list(p_values.values())
        keys = list(p_values.keys())
        
        if self.config.correction_method == "bonferroni":
            # Bonferroni correction
            m = len(p_list)
            corrected = [min(p * m, 1.0) for p in p_list]
        elif self.config.correction_method == "holm":
            # Holm-Bonferroni correction
            sorted_indices = np.argsort(p_list)
            sorted_p = [p_list[i] for i in sorted_indices]
            m = len(sorted_p)
            corrected_p = []
            for i, p in enumerate(sorted_p):
                corrected_p.append(min(p * (m - i), 1.0))
            # Restore order
            corrected = [0] * m
            for i, idx in enumerate(sorted_indices):
                corrected[idx] = corrected_p[i]
        elif self.config.correction_method == "fdr":
            # Benjamini-Hochberg FDR
            sorted_indices = np.argsort(p_list)
            sorted_p = [p_list[i] for i in sorted_indices]
            m = len(sorted_p)
            corrected_p = []
            for i, p in enumerate(sorted_p):
                corrected_p.append(min(p * m / (i + 1), 1.0))
            # Restore order
            corrected = [0] * m
            for i, idx in enumerate(sorted_indices):
                corrected[idx] = corrected_p[i]
        else:
            corrected = p_list
        
        return {key: corrected[i] for i, key in enumerate(keys)}
    
    # ============================================
    # Result Management
    # ============================================
    
    def _save_results(self) -> None:
        """Save results to disk."""
        if not self.results:
            return
        
        results_file = self.output_dir / "results.json"
        with open(results_file, 'w') as f:
            json.dump(asdict(self.results), f, indent=2, default=str)
        
        self.logger.info(f"Results saved to {results_file}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """
        Generate summary of comparison results.
        
        Returns:
            Summary dictionary
        """
        if not self.results:
            return {}
        
        summary = {
            'comparison_id': self.config.comparison_id,
            'name': self.config.name,
            'groups': list(self.results.groups.keys()),
            'n_groups': len(self.results.groups),
            'rankings': self.results.rankings,
            'significant_results': [],
            'timestamp': time.time(),
        }
        
        # Extract significant results
        for test_name, test_results in self.results.statistics.items():
            if isinstance(test_results, dict):
                for key, result in test_results.items():
                    if isinstance(result, dict):
                        if result.get('significant', False):
                            summary['significant_results'].append({
                                'test': test_name,
                                'comparison': key,
                                'p_value': result.get('p_value'),
                                'effect_size': result.get('effect_size'),
                            })
        
        # Save summary
        summary_file = self.output_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        return summary
    
    # ============================================
    # Visualization
    # ============================================
    
    def _plot_results(self) -> None:
        """Plot comparison results."""
        if not self.results:
            return
        
        data = self.results.groups
        group_names = list(data.keys())
        n_groups = len(group_names)
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # Plot 1: Box plot
        ax1 = axes[0, 0]
        if n_groups <= 10:
            ax1.boxplot([data[g] for g in group_names], labels=group_names)
            ax1.set_title('Distribution by Group')
            ax1.set_xlabel('Group')
            ax1.set_ylabel('Value')
            ax1.tick_params(axis='x', rotation=45)
        
        # Plot 2: Bar plot with confidence intervals
        ax2 = axes[0, 1]
        means = [np.mean(data[g]) for g in group_names]
        stds = [np.std(data[g]) for g in group_names]
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, n_groups))
        bars = ax2.bar(group_names, means, yerr=stds, color=colors, capsize=5, alpha=0.7)
        ax2.set_title('Mean Values with Standard Deviation')
        ax2.set_xlabel('Group')
        ax2.set_ylabel('Mean Value')
        ax2.tick_params(axis='x', rotation=45)
        
        # Plot 3: Scatter plot of individual points
        ax3 = axes[1, 0]
        for i, group in enumerate(group_names):
            x = np.random.normal(i + 1, 0.04, len(data[group]))
            ax3.scatter(x, data[group], alpha=0.5, label=group)
        ax3.set_xticks(range(1, n_groups + 1))
        ax3.set_xticklabels(group_names)
        ax3.set_title('Individual Data Points')
        ax3.set_xlabel('Group')
        ax3.set_ylabel('Value')
        ax3.legend()
        
        # Plot 4: Heatmap of p-values
        ax4 = axes[1, 1]
        if self.results.p_values:
            p_values = self.results.p_values
            # Extract pairwise comparisons
            pairwise = {}
            for key, p in p_values.items():
                if 'vs' in key:
                    parts = key.split('_vs_')
                    if len(parts) == 2:
                        g1, g2 = parts[0], parts[1]
                        if g1 in group_names and g2 in group_names:
                            pairwise[(g1, g2)] = p
            
            if pairwise:
                # Create matrix
                matrix = np.zeros((n_groups, n_groups))
                for i, g1 in enumerate(group_names):
                    for j, g2 in enumerate(group_names):
                        if i != j:
                            key = (g1, g2)
                            if key in pairwise:
                                matrix[i, j] = pairwise[key]
                            else:
                                key = (g2, g1)
                                if key in pairwise:
                                    matrix[i, j] = pairwise[key]
                
                im = ax4.imshow(matrix, cmap='RdYlGn_r', vmin=0, vmax=0.05)
                ax4.set_xticks(range(n_groups))
                ax4.set_yticks(range(n_groups))
                ax4.set_xticklabels(group_names, rotation=45)
                ax4.set_yticklabels(group_names)
                ax4.set_title('P-values Matrix')
                plt.colorbar(im, ax=ax4)
        
        plt.tight_layout()
        
        # Save figure
        plot_file = self.output_dir / "comparison_results.png"
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        self.logger.info(f"Plot saved to {plot_file}")
        
        plt.show()
    
    # ============================================
    # Export
    # ============================================
    
    def export_report(self, format: str = "html") -> str:
        """
        Export comparison report.
        
        Args:
            format: Report format ("html", "md", "pdf")
            
        Returns:
            Report file path
        """
        if not self.results:
            return ""
        
        report_file = self.output_dir / f"report.{format}"
        
        if format == "html":
            self._export_html_report(report_file)
        elif format == "md":
            self._export_markdown_report(report_file)
        elif format == "pdf":
            self._export_pdf_report(report_file)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self.logger.info(f"Report exported to {report_file}")
        return str(report_file)
    
    def _export_html_report(self, output_path: Path) -> None:
        """Export HTML report."""
        if not self.results:
            return
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Comparison Report: {self.config.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
                h2 {{ color: #555; margin-top: 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #4CAF50; color: white; }}
                .significant {{ color: #4CAF50; font-weight: bold; }}
                .not-significant {{ color: #999; }}
                .effect-large {{ color: #2ecc71; }}
                .effect-medium {{ color: #f1c40f; }}
                .effect-small {{ color: #e74c3c; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Comparison Report: {self.config.name}</h1>
                <p><strong>ID:</strong> {self.config.comparison_id}</p>
                <p><strong>Description:</strong> {self.config.description}</p>
                <p><strong>Type:</strong> {self.config.type.value}</p>
                <p><strong>Groups:</strong> {', '.join(self.results.groups.keys())}</p>
                <p><strong>Completed:</strong> {datetime.now().isoformat()}</p>
        """
        
        # Add rankings
        html += "<h2>Rankings</h2><table><tr><th>Rank</th><th>Group</th></tr>"
        for group, rank in sorted(self.results.rankings.items(), key=lambda x: x[1]):
            html += f"<tr><td>{rank}</td><td>{group}</td></tr>"
        html += "</table>"
        
        # Add statistical test results
        html += "<h2>Statistical Tests</h2>"
        for test_name, test_results in self.results.statistics.items():
            if isinstance(test_results, dict):
                html += f"<h3>{test_name}</h3>"
                html += "<table><tr><th>Comparison</th><th>Statistic</th><th>P-value</th><th>Significant</th></tr>"
                for key, result in test_results.items():
                    if isinstance(result, dict):
                        stat = result.get('statistic', result.get('f_statistic', result.get('h_statistic', 'N/A')))
                        p = result.get('p_value', 'N/A')
                        sig = result.get('significant', False)
                        html += f"<tr><td>{key}</td><td>{stat:.4f if isinstance(stat, float) else stat}</td>"
                        html += f"<td>{p:.4f if isinstance(p, float) else p}</td>"
                        html += f"<td class=\"{'significant' if sig else 'not-significant'}\">{sig}</td></tr>"
                html += "</table>"
        
        # Add effect sizes
        html += "<h2>Effect Sizes</h2>"
        html += "<table><tr><th>Comparison</th><th>Cohen's d</th><th>Hedges' g</th><th>Interpretation</th></tr>"
        for key, effects in self.results.effect_sizes.items():
            d = effects.get('cohens_d', 0)
            g = effects.get('hedges_g', 0)
            if abs(d) < 0.2:
                interpretation = "Negligible"
                cls = "effect-small"
            elif abs(d) < 0.5:
                interpretation = "Small"
                cls = "effect-medium"
            elif abs(d) < 0.8:
                interpretation = "Medium"
                cls = "effect-medium"
            else:
                interpretation = "Large"
                cls = "effect-large"
            html += f"<tr><td>{key}</td><td>{d:.3f}</td><td>{g:.3f}</td>"
            html += f"<td class=\"{cls}\">{interpretation}</td></tr>"
        html += "</table>"
        
        # Add confidence intervals
        html += "<h2>Confidence Intervals (95%)</h2>"
        html += "<table><tr><th>Group</th><th>Lower</th><th>Upper</th><th>Width</th></tr>"
        for group, (lower, upper) in self.results.confidence_intervals.items():
            html += f"<tr><td>{group}</td><td>{lower:.4f}</td><td>{upper:.4f}</td><td>{upper - lower:.4f}</td></tr>"
        html += "</table>"
        
        html += """
            </div>
        </body>
        </html>
        """
        
        with open(output_path, 'w') as f:
            f.write(html)
    
    def _export_markdown_report(self, output_path: Path) -> None:
        """Export Markdown report."""
        if not self.results:
            return
        
        lines = [
            f"# Comparison Report: {self.config.name}",
            "",
            f"**ID:** {self.config.comparison_id}",
            f"**Description:** {self.config.description}",
            f"**Type:** {self.config.type.value}",
            f"**Groups:** {', '.join(self.results.groups.keys())}",
            f"**Completed:** {datetime.now().isoformat()}",
            "",
            "## Rankings",
            "",
            "| Rank | Group |",
            "|------|-------|",
        ]
        
        for group, rank in sorted(self.results.rankings.items(), key=lambda x: x[1]):
            lines.append(f"| {rank} | {group} |")
        
        lines.append("")
        lines.append("## Statistical Tests")
        
        for test_name, test_results in self.results.statistics.items():
            if isinstance(test_results, dict):
                lines.append(f"")
                lines.append(f"### {test_name}")
                lines.append("")
                lines.append("| Comparison | Statistic | P-value | Significant |")
                lines.append("|------------|-----------|---------|-------------|")
                for key, result in test_results.items():
                    if isinstance(result, dict):
                        stat = result.get('statistic', result.get('f_statistic', result.get('h_statistic', 'N/A')))
                        p = result.get('p_value', 'N/A')
                        sig = 'Yes' if result.get('significant', False) else 'No'
                        lines.append(f"| {key} | {stat:.4f if isinstance(stat, float) else stat} | {p:.4f if isinstance(p, float) else p} | {sig} |")
        
        lines.append("")
        lines.append("## Effect Sizes")
        lines.append("")
        lines.append("| Comparison | Cohen's d | Hedges' g | Interpretation |")
        lines.append("|------------|-----------|-----------|----------------|")
        for key, effects in self.results.effect_sizes.items():
            d = effects.get('cohens_d', 0)
            g = effects.get('hedges_g', 0)
            if abs(d) < 0.2:
                interpretation = "Negligible"
            elif abs(d) < 0.5:
                interpretation = "Small"
            elif abs(d) < 0.8:
                interpretation = "Medium"
            else:
                interpretation = "Large"
            lines.append(f"| {key} | {d:.3f} | {g:.3f} | {interpretation} |")
        
        lines.append("")
        lines.append("## Confidence Intervals")
        lines.append("")
        lines.append("| Group | Lower | Upper | Width |")
        lines.append("|-------|-------|-------|-------|")
        for group, (lower, upper) in self.results.confidence_intervals.items():
            lines.append(f"| {group} | {lower:.4f} | {upper:.4f} | {upper - lower:.4f} |")
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
    
    def _export_pdf_report(self, output_path: Path) -> None:
        """Export PDF report."""
        # Use matplotlib to create a PDF report
        fig, axes = plt.subplots(3, 2, figsize=(14, 16))
        fig.suptitle(f"Comparison Report: {self.config.name}", fontsize=16, fontweight='bold')
        
        # Plot 1: Box plot
        ax1 = axes[0, 0]
        if self.results.groups:
            ax1.boxplot(self.results.groups.values(), labels=self.results.groups.keys())
            ax1.set_title('Distribution by Group')
            ax1.set_xlabel('Group')
            ax1.set_ylabel('Value')
            ax1.tick_params(axis='x', rotation=45)
        
        # Plot 2: Bar plot with confidence intervals
        ax2 = axes[0, 1]
        means = [np.mean(v) for v in self.results.groups.values()]
        stds = [np.std(v) for v in self.results.groups.values()]
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(self.results.groups)))
        bars = ax2.bar(self.results.groups.keys(), means, yerr=stds, color=colors, capsize=5, alpha=0.7)
        ax2.set_title('Mean Values with Standard Deviation')
        ax2.set_xlabel('Group')
        ax2.set_ylabel('Mean Value')
        ax2.tick_params(axis='x', rotation=45)
        
        # Plot 3: Scatter plot
        ax3 = axes[1, 0]
        for i, (group, values) in enumerate(self.results.groups.items()):
            x = np.random.normal(i + 1, 0.04, len(values))
            ax3.scatter(x, values, alpha=0.5, label=group)
        ax3.set_xticks(range(1, len(self.results.groups) + 1))
        ax3.set_xticklabels(self.results.groups.keys())
        ax3.set_title('Individual Data Points')
        ax3.set_xlabel('Group')
        ax3.set_ylabel('Value')
        ax3.legend()
        
        # Plot 4: Rankings
        ax4 = axes[1, 1]
        rankings = self.results.rankings
        if rankings:
            groups = list(rankings.keys())
            ranks = list(rankings.values())
            ax4.bar(groups, ranks, color='skyblue', alpha=0.7)
            ax4.set_title('Group Rankings')
            ax4.set_xlabel('Group')
            ax4.set_ylabel('Rank (1 = Best)')
            ax4.tick_params(axis='x', rotation=45)
            ax4.invert_yaxis()
        
        # Plot 5: Effect sizes
        ax5 = axes[2, 0]
        effect_sizes = self.results.effect_sizes
        if effect_sizes:
            comparisons = list(effect_sizes.keys())
            cohens_d = [e.get('cohens_d', 0) for e in effect_sizes.values()]
            bars = ax5.bar(comparisons, cohens_d, color='lightcoral', alpha=0.7)
            ax5.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax5.axhline(y=0.2, color='blue', linestyle='--', alpha=0.3, label='Small')
            ax5.axhline(y=0.5, color='orange', linestyle='--', alpha=0.3, label='Medium')
            ax5.axhline(y=0.8, color='red', linestyle='--', alpha=0.3, label='Large')
            ax5.set_title("Cohen's d Effect Sizes")
            ax5.set_xlabel('Comparison')
            ax5.set_ylabel("Cohen's d")
            ax5.legend()
            ax5.tick_params(axis='x', rotation=45)
        
        # Plot 6: P-value heatmap
        ax6 = axes[2, 1]
        p_values = self.results.p_values
        if p_values:
            # Extract pairwise comparisons
            pairwise = {}
            for key, p in p_values.items():
                if 'vs' in key:
                    parts = key.split('_vs_')
                    if len(parts) == 2:
                        g1, g2 = parts[0], parts[1]
                        if g1 in self.results.groups and g2 in self.results.groups:
                            pairwise[(g1, g2)] = p
            
            if pairwise:
                group_names = list(self.results.groups.keys())
                n_groups = len(group_names)
                matrix = np.zeros((n_groups, n_groups))
                for i, g1 in enumerate(group_names):
                    for j, g2 in enumerate(group_names):
                        if i != j:
                            key = (g1, g2)
                            if key in pairwise:
                                matrix[i, j] = pairwise[key]
                            else:
                                key = (g2, g1)
                                if key in pairwise:
                                    matrix[i, j] = pairwise[key]
                
                im = ax6.imshow(matrix, cmap='RdYlGn_r', vmin=0, vmax=0.05)
                ax6.set_xticks(range(n_groups))
                ax6.set_yticks(range(n_groups))
                ax6.set_xticklabels(group_names, rotation=45)
                ax6.set_yticklabels(group_names)
                ax6.set_title('P-values Matrix')
                plt.colorbar(im, ax=ax6)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Results Comparator')
    parser.add_argument('--config', type=str, help='Configuration file')
    parser.add_argument('--data', type=str, help='Data file')
    parser.add_argument('--comparison-id', type=str, help='Comparison identifier')
    parser.add_argument('--list', action='store_true', help='List comparisons')
    parser.add_argument('--export', type=str, help='Export format (html, md, pdf)')
    parser.add_argument('--output-dir', type=str, default='./results/comparisons', help='Output directory')
    parser.add_argument('--log-level', type=str, default='INFO', help='Logging level')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.list:
        # List comparisons
        comparisons = Path(args.output_dir).glob('*/summary.json')
        print("Available Comparisons:")
        print("-" * 60)
        for comp_file in comparisons:
            try:
                with open(comp_file, 'r') as f:
                    data = json.load(f)
                    print(f"ID: {data.get('comparison_id', comp_file.parent.name)}")
                    print(f"  Name: {data.get('name', 'N/A')}")
                    print(f"  Groups: {len(data.get('groups', []))}")
                    print(f"  Significant: {len(data.get('significant_results', []))}")
                    print()
            except:
                pass
        return
    
    if args.config and args.data:
        # Load configuration
        with open(args.config, 'r') as f:
            config_data = json.load(f)
        
        # Load data
        with open(args.data, 'r') as f:
            data = json.load(f)
        
        # Create config
        config = ComparisonConfig(
            comparison_id=config_data.get('comparison_id', f"comp_{int(time.time())}"),
            name=config_data.get('name', 'Comparison'),
            description=config_data.get('description', ''),
            type=ComparisonType(config_data.get('type', 'pairwise')),
            groups=config_data.get('groups', {}),
            metrics=config_data.get('metrics', ['value']),
            statistical_tests=[StatisticalTest(t) for t in config_data.get('statistical_tests', ['t_test'])],
            significance_level=config_data.get('significance_level', 0.05),
            correction_method=config_data.get('correction_method', 'bonferroni'),
            n_bootstrap=config_data.get('n_bootstrap', 1000),
            random_seed=config_data.get('random_seed', 42),
            output_dir=args.output_dir,
            metadata=config_data.get('metadata', {}),
        )
        
        # Run comparison
        comparator = ResultsComparator(config)
        result = comparator.compare(data)
        
        # Export if requested
        if args.export:
            comparator.export_report(args.export)
        
        # Print summary
        print("\nComparison Results:")
        print("-" * 40)
        print(f"Rankings:")
        for group, rank in sorted(result.rankings.items(), key=lambda x: x[1]):
            print(f"  {rank}. {group}")
        
        significant = [k for k, v in result.p_values.items() if v < config.significance_level]
        if significant:
            print(f"\nSignificant Results: {len(significant)}")
            for key in significant:
                print(f"  {key}")
        
        return
    
    # Interactive mode
    print("NEXUS Results Comparator")
    print("========================")
    print()
    print("1. Compare two groups")
    print("2. Compare multiple groups")
    print("3. View comparisons")
    print("4. Export report")
    print("5. Exit")
    
    while True:
        choice = input("\nSelect option: ")
        
        if choice == '1':
            # Two group comparison
            name = input("Comparison name: ")
            group1_name = input("Group 1 name: ")
            group1_values = input("Group 1 values (comma-separated): ")
            group2_name = input("Group 2 name: ")
            group2_values = input("Group 2 values (comma-separated): ")
            
            data = {
                group1_name: [float(x.strip()) for x in group1_values.split(',')],
                group2_name: [float(x.strip()) for x in group2_values.split(',')],
            }
            
            config = ComparisonConfig(
                comparison_id=f"comp_{int(time.time())}",
                name=name,
                description=f"Comparison of {group1_name} vs {group2_name}",
                type=ComparisonType.PAIRWISE,
                groups={},
                metrics=['value'],
                statistical_tests=[StatisticalTest.T_TEST, StatisticalTest.MANN_WHITNEY],
                output_dir=args.output_dir,
            )
            
            comparator = ResultsComparator(config)
            result = comparator.compare(data)
            comparator.export_report("html")
            
            print("\nResults:")
            print(f"  {group1_name}: mean={np.mean(data[group1_name]):.4f}, std={np.std(data[group1_name]):.4f}")
            print(f"  {group2_name}: mean={np.mean(data[group2_name]):.4f}, std={np.std(data[group2_name]):.4f}")
            print(f"  Cohen's d: {result.effect_sizes[f'{group1_name}_vs_{group2_name}']['cohens_d']:.4f}")
            
        elif choice == '2':
            # Multi-group comparison
            name = input("Comparison name: ")
            groups = {}
            print("Add groups (empty name to finish)")
            while True:
                group_name = input("Group name: ")
                if not group_name:
                    break
                values_str = input("Values (comma-separated): ")
                groups[group_name] = [float(x.strip()) for x in values_str.split(',')]
            
            config = ComparisonConfig(
                comparison_id=f"comp_{int(time.time())}",
                name=name,
                description="Multi-group comparison",
                type=ComparisonType.MULTI_GROUP,
                groups={},
                metrics=['value'],
                statistical_tests=[StatisticalTest.ANOVA, StatisticalTest.KRUSKAL_WALLIS],
                output_dir=args.output_dir,
            )
            
            comparator = ResultsComparator(config)
            result = comparator.compare(groups)
            comparator.export_report("html")
            
            print("\nRankings:")
            for group, rank in sorted(result.rankings.items(), key=lambda x: x[1]):
                print(f"  {rank}. {group}")
            
        elif choice == '3':
            # View comparisons
            comparisons = Path(args.output_dir).glob('*/summary.json')
            print("\nAvailable Comparisons:")
            for comp_file in comparisons:
                try:
                    with open(comp_file, 'r') as f:
                        data = json.load(f)
                        print(f"  {data.get('name', comp_file.parent.name)} ({data.get('comparison_id', 'N/A')})")
                except:
                    pass
            
        elif choice == '4':
            # Export report
            comp_id = input("Comparison ID: ")
            comp_path = Path(args.output_dir) / comp_id
            if comp_path.exists():
                # Load comparison
                results_file = comp_path / "results.json"
                if results_file.exists():
                    with open(results_file, 'r') as f:
                        data = json.load(f)
                    
                    # Recreate comparator
                    config = ComparisonConfig(
                        comparison_id=data.get('comparison_id', comp_id),
                        name=data.get('name', 'Comparison'),
                        description=data.get('description', ''),
                        type=ComparisonType(data.get('type', 'pairwise')),
                        groups={},
                        metrics=['value'],
                        statistical_tests=[],
                        output_dir=args.output_dir,
                    )
                    
                    comparator = ResultsComparator(config)
                    comparator.results = ComparisonResult(**data)
                    comparator.export_report("html")
                    print(f"Report exported to {comp_path / 'report.html'}")
                else:
                    print("Results file not found")
            else:
                print("Comparison not found")
            
        elif choice == '5':
            print("Exiting...")
            break
        
        else:
            print("Invalid choice")


if __name__ == '__main__':
    main()

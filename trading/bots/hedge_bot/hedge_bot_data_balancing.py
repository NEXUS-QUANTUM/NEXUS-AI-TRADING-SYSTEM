# trading/bots/hedge_bot/hedge_bot_data_balancing.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Balancing Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Balancing Module

This module provides comprehensive data balancing capabilities for the
NEXUS Hedge Bot system. It handles dataset balancing, resampling, and
synthetic data generation to address class imbalance issues.

The module covers:
- Class Imbalance Detection
- Oversampling Techniques
- Undersampling Techniques
- SMOTE (Synthetic Minority Oversampling)
- ADASYN (Adaptive Synthetic Sampling)
- Random Oversampling
- Random Undersampling
- Cluster-Based Sampling
- Synthetic Data Generation
- Data Augmentation
- Weight Balancing
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import Counter
import random

# Try to import ML libraries
try:
    from sklearn.utils import resample
    from sklearn.neighbors import NearestNeighbors
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)


# ============================================================
# DATA BALANCING ENUMS
# ============================================================

class BalancingMethod(Enum):
    """Balancing methods"""
    RANDOM_OVERSAMPLE = "random_oversample"
    RANDOM_UNDERSAMPLE = "random_undersample"
    SMOTE = "smote"
    ADASYN = "adasyn"
    CLUSTER = "cluster"
    WEIGHTED = "weighted"
    AUGMENTATION = "augmentation"


class ImbalanceLevel(Enum):
    """Imbalance levels"""
    SEVERE = "severe"
    MODERATE = "moderate"
    MILD = "mild"
    BALANCED = "balanced"


@dataclass
class BalancingResult:
    """Balancing result"""
    original_shape: Tuple[int, int]
    balanced_shape: Tuple[int, int]
    original_distribution: Dict[str, int]
    balanced_distribution: Dict[str, int]
    method: BalancingMethod
    transformation: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "original_shape": self.original_shape,
            "balanced_shape": self.balanced_shape,
            "original_distribution": self.original_distribution,
            "balanced_distribution": self.balanced_distribution,
            "method": self.method.value,
            "transformation": self.transformation,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ImbalanceReport:
    """Imbalance report"""
    dataset_name: str
    target_column: str
    distribution: Dict[str, int]
    imbalance_ratio: float
    level: ImbalanceLevel
    majority_class: str
    minority_class: str
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "dataset_name": self.dataset_name,
            "target_column": self.target_column,
            "distribution": self.distribution,
            "imbalance_ratio": self.imbalance_ratio,
            "level": self.level.value,
            "majority_class": self.majority_class,
            "minority_class": self.minority_class,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# DATA BALANCING ENGINE
# ============================================================

class DataBalancingEngine:
    """
    Comprehensive data balancing engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data balancing engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.random_seed = self.config.get("random_seed", 42)
        self.sampling_strategy = self.config.get("sampling_strategy", "auto")
        
        # Set random seed
        random.seed(self.random_seed)
        np.random.seed(self.random_seed)
        if HAS_SKLEARN:
            import sklearn
            sklearn.set_config(random_state=self.random_seed)
        
        # State
        self.balancing_results: List[BalancingResult] = []
        self.imbalance_reports: List[ImbalanceReport] = []
        
        logger.info("Data balancing engine initialized")
    
    # ============================================================
    # IMBALANCE DETECTION
    # ============================================================
    
    def detect_imbalance(
        self,
        data: pd.DataFrame,
        target_column: str,
        dataset_name: str = "dataset"
    ) -> ImbalanceReport:
        """
        Detect class imbalance in dataset
        
        Args:
            data: DataFrame
            target_column: Target column name
            dataset_name: Dataset name
            
        Returns:
            ImbalanceReport
        """
        if target_column not in data.columns:
            raise ValueError(f"Target column not found: {target_column}")
        
        # Get distribution
        distribution = data[target_column].value_counts().to_dict()
        
        # Calculate imbalance ratio
        counts = list(distribution.values())
        max_count = max(counts)
        min_count = min(counts)
        imbalance_ratio = max_count / min_count if min_count > 0 else 0
        
        # Determine level
        if imbalance_ratio > 10:
            level = ImbalanceLevel.SEVERE
        elif imbalance_ratio > 3:
            level = ImbalanceLevel.MODERATE
        elif imbalance_ratio > 1.5:
            level = ImbalanceLevel.MILD
        else:
            level = ImbalanceLevel.BALANCED
        
        # Identify classes
        majority_class = max(distribution, key=distribution.get)
        minority_class = min(distribution, key=distribution.get)
        
        # Generate recommendations
        recommendations = []
        if level in [ImbalanceLevel.SEVERE, ImbalanceLevel.MODERATE]:
            recommendations.append(f"Consider using oversampling for {minority_class}")
            recommendations.append(f"Consider using undersampling for {majority_class}")
            recommendations.append("Consider SMOTE or ADASYN for synthetic data generation")
        if level == ImbalanceLevel.SEVERE:
            recommendations.append("Strongly recommend balancing before model training")
            recommendations.append("Consider collecting more data for minority class")
        
        report = ImbalanceReport(
            dataset_name=dataset_name,
            target_column=target_column,
            distribution=distribution,
            imbalance_ratio=imbalance_ratio,
            level=level,
            majority_class=majority_class,
            minority_class=minority_class,
            recommendations=recommendations,
            timestamp=datetime.now(),
        )
        
        self.imbalance_reports.append(report)
        return report
    
    # ============================================================
    # RANDOM OVERSAMPLING
    # ============================================================
    
    def random_oversample(
        self,
        data: pd.DataFrame,
        target_column: str,
        target_ratio: Optional[float] = None
    ) -> BalancingResult:
        """
        Perform random oversampling
        
        Args:
            data: DataFrame
            target_column: Target column
            target_ratio: Target ratio (majority/minority)
            
        Returns:
            BalancingResult
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn is required for random sampling")
        
        original_shape = data.shape
        original_distribution = data[target_column].value_counts().to_dict()
        
        # Separate features and target
        X = data.drop(columns=[target_column])
        y = data[target_column]
        
        # Get classes
        classes = y.unique()
        majority_class = max(y.value_counts().items(), key=lambda x: x[1])[0]
        minority_class = min(y.value_counts().items(), key=lambda x: x[1])[0]
        
        # Determine target distribution
        if target_ratio is None:
            target_ratio = 1.0
        
        # Separate majority and minority
        majority_idx = y[y == majority_class].index
        minority_idx = y[y == minority_class].index
        
        # Oversample minority class
        n_minority = len(minority_idx)
        n_majority = len(majority_idx)
        
        if target_ratio == 1.0:
            target_minority = n_majority
        else:
            target_minority = int(n_majority / target_ratio)
        
        # Resample minority
        minority_oversampled = resample(
            data.loc[minority_idx],
            replace=True,
            n_samples=target_minority,
            random_state=self.random_seed
        )
        
        # Combine
        majority_data = data.loc[majority_idx]
        balanced_data = pd.concat([majority_data, minority_oversampled])
        
        # Shuffle
        balanced_data = balanced_data.sample(frac=1, random_state=self.random_seed)
        
        balanced_distribution = balanced_data[target_column].value_counts().to_dict()
        
        result = BalancingResult(
            original_shape=original_shape,
            balanced_shape=balanced_data.shape,
            original_distribution=original_distribution,
            balanced_distribution=balanced_distribution,
            method=BalancingMethod.RANDOM_OVERSAMPLE,
            transformation={
                "target_column": target_column,
                "target_ratio": target_ratio,
                "oversampled_class": minority_class,
            },
            metadata={
                "n_majority": n_majority,
                "n_minority": n_minority,
                "target_minority": target_minority,
            },
        )
        
        self.balancing_results.append(result)
        return result
    
    # ============================================================
    # RANDOM UNDERSAMPLING
    # ============================================================
    
    def random_undersample(
        self,
        data: pd.DataFrame,
        target_column: str,
        target_ratio: Optional[float] = None
    ) -> BalancingResult:
        """
        Perform random undersampling
        
        Args:
            data: DataFrame
            target_column: Target column
            target_ratio: Target ratio (majority/minority)
            
        Returns:
            BalancingResult
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn is required for random sampling")
        
        original_shape = data.shape
        original_distribution = data[target_column].value_counts().to_dict()
        
        # Get classes
        y = data[target_column]
        majority_class = max(y.value_counts().items(), key=lambda x: x[1])[0]
        minority_class = min(y.value_counts().items(), key=lambda x: x[1])[0]
        
        # Determine target distribution
        if target_ratio is None:
            target_ratio = 1.0
        
        # Separate majority and minority
        majority_idx = y[y == majority_class].index
        minority_idx = y[y == minority_class].index
        
        # Undersample majority class
        n_minority = len(minority_idx)
        
        if target_ratio == 1.0:
            target_majority = n_minority
        else:
            target_majority = int(n_minority * target_ratio)
        
        # Resample majority
        majority_undersampled = resample(
            data.loc[majority_idx],
            replace=False,
            n_samples=target_majority,
            random_state=self.random_seed
        )
        
        # Combine
        minority_data = data.loc[minority_idx]
        balanced_data = pd.concat([majority_undersampled, minority_data])
        
        # Shuffle
        balanced_data = balanced_data.sample(frac=1, random_state=self.random_seed)
        
        balanced_distribution = balanced_data[target_column].value_counts().to_dict()
        
        result = BalancingResult(
            original_shape=original_shape,
            balanced_shape=balanced_data.shape,
            original_distribution=original_distribution,
            balanced_distribution=balanced_distribution,
            method=BalancingMethod.RANDOM_UNDERSAMPLE,
            transformation={
                "target_column": target_column,
                "target_ratio": target_ratio,
                "undersampled_class": majority_class,
            },
            metadata={
                "n_majority": len(majority_idx),
                "n_minority": n_minority,
                "target_majority": target_majority,
            },
        )
        
        self.balancing_results.append(result)
        return result
    
    # ============================================================
    # SMOTE (Synthetic Minority Oversampling)
    # ============================================================
    
    def smote(
        self,
        data: pd.DataFrame,
        target_column: str,
        k_neighbors: int = 5,
        target_ratio: Optional[float] = None
    ) -> BalancingResult:
        """
        Perform SMOTE oversampling
        
        Args:
            data: DataFrame
            target_column: Target column
            k_neighbors: Number of neighbors
            target_ratio: Target ratio
            
        Returns:
            BalancingResult
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn is required for SMOTE")
        
        original_shape = data.shape
        original_distribution = data[target_column].value_counts().to_dict()
        
        # Separate features and target
        X = data.drop(columns=[target_column])
        y = data[target_column]
        
        # Get classes
        majority_class = max(y.value_counts().items(), key=lambda x: x[1])[0]
        minority_class = min(y.value_counts().items(), key=lambda x: x[1])[0]
        
        # Determine target distribution
        if target_ratio is None:
            target_ratio = 1.0
        
        # Separate majority and minority
        minority_data = data[data[target_column] == minority_class]
        minority_X = minority_data.drop(columns=[target_column])
        
        n_minority = len(minority_data)
        n_majority = len(data[data[target_column] == majority_class])
        
        if target_ratio == 1.0:
            n_synthetic = n_majority - n_minority
        else:
            n_synthetic = int(n_majority / target_ratio) - n_minority
        
        if n_synthetic <= 0:
            # No need for SMOTE
            return self.random_oversample(data, target_column, target_ratio)
        
        # Perform SMOTE
        synthetic_samples = self._generate_smote_samples(
            minority_X.values,
            n_synthetic,
            k_neighbors
        )
        
        # Create synthetic data
        synthetic_df = pd.DataFrame(
            synthetic_samples,
            columns=minority_X.columns
        )
        synthetic_df[target_column] = minority_class
        
        # Combine
        balanced_data = pd.concat([data, synthetic_df])
        balanced_data = balanced_data.sample(frac=1, random_state=self.random_seed)
        
        balanced_distribution = balanced_data[target_column].value_counts().to_dict()
        
        result = BalancingResult(
            original_shape=original_shape,
            balanced_shape=balanced_data.shape,
            original_distribution=original_distribution,
            balanced_distribution=balanced_distribution,
            method=BalancingMethod.SMOTE,
            transformation={
                "target_column": target_column,
                "k_neighbors": k_neighbors,
                "target_ratio": target_ratio,
                "n_synthetic": n_synthetic,
                "synthetic_class": minority_class,
            },
            metadata={
                "n_minority": n_minority,
                "n_majority": n_majority,
            },
        )
        
        self.balancing_results.append(result)
        return result
    
    def _generate_smote_samples(
        self,
        X: np.ndarray,
        n_samples: int,
        k_neighbors: int = 5
    ) -> np.ndarray:
        """
        Generate synthetic samples using SMOTE
        
        Args:
            X: Feature matrix
            n_samples: Number of samples to generate
            k_neighbors: Number of neighbors
            
        Returns:
            Synthetic samples
        """
        if len(X) == 0:
            return np.array([])
        
        # Find nearest neighbors
        nn = NearestNeighbors(n_neighbors=k_neighbors + 1)
        nn.fit(X)
        distances, indices = nn.kneighbors(X)
        
        # Generate synthetic samples
        synthetic = []
        for _ in range(n_samples):
            # Randomly select a point
            idx = np.random.randint(0, len(X))
            
            # Randomly select one of its neighbors
            neighbor_idx = np.random.randint(1, k_neighbors + 1)
            neighbor = X[indices[idx][neighbor_idx]]
            
            # Interpolate
            diff = neighbor - X[idx]
            gap = np.random.random()
            synthetic_sample = X[idx] + gap * diff
            
            synthetic.append(synthetic_sample)
        
        return np.array(synthetic)
    
    # ============================================================
    # WEIGHTED BALANCING
    # ============================================================
    
    def weighted_balancing(
        self,
        data: pd.DataFrame,
        target_column: str,
        weights: Optional[Dict[str, float]] = None
    ) -> BalancingResult:
        """
        Apply weighted balancing
        
        Args:
            data: DataFrame
            target_column: Target column
            weights: Class weights
            
        Returns:
            BalancingResult
        """
        original_shape = data.shape
        original_distribution = data[target_column].value_counts().to_dict()
        
        # Calculate weights if not provided
        if weights is None:
            distribution = data[target_column].value_counts()
            total = len(data)
            weights = {cls: total / (len(distribution) * count) for cls, count in distribution.items()}
        
        # Apply weights
        weighted_data = data.copy()
        weighted_data['weight'] = weighted_data[target_column].map(weights)
        
        # Sample with weights
        balanced_data = weighted_data.sample(
            n=len(data),
            weights='weight',
            replace=True,
            random_state=self.random_seed
        ).drop(columns=['weight'])
        
        balanced_distribution = balanced_data[target_column].value_counts().to_dict()
        
        result = BalancingResult(
            original_shape=original_shape,
            balanced_shape=balanced_data.shape,
            original_distribution=original_distribution,
            balanced_distribution=balanced_distribution,
            method=BalancingMethod.WEIGHTED,
            transformation={
                "target_column": target_column,
                "weights": weights,
            },
        )
        
        self.balancing_results.append(result)
        return result
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get balancing statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_balancing_operations": len(self.balancing_results),
            "total_imbalance_reports": len(self.imbalance_reports),
            "methods_used": {
                m.value: len([r for r in self.balancing_results if r.method == m])
                for m in BalancingMethod
            },
            "last_operation": self.balancing_results[-1].to_dict() if self.balancing_results else None,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "BalancingMethod",
    "ImbalanceLevel",
    
    # Dataclasses
    "BalancingResult",
    "ImbalanceReport",
    
    # Classes
    "DataBalancingEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

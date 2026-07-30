# trading/bots/hedge_bot/hedge_bot_data_cleaning.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Cleaning Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Cleaning Module

This module provides comprehensive data cleaning and preprocessing
capabilities for the NEXUS Hedge Bot system. It handles missing values,
outliers, duplicates, and data quality issues.

The module covers:
- Missing Value Handling
- Outlier Detection and Removal
- Duplicate Removal
- Data Normalization
- Data Standardization
- Data Transformation
- Data Validation
- Data Quality Scoring
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from scipy import stats

logger = logging.getLogger(__name__)


# ============================================================
# DATA CLEANING ENUMS
# ============================================================

class MissingValueMethod(Enum):
    """Missing value handling methods"""
    DROP = "drop"
    FILL_MEAN = "fill_mean"
    FILL_MEDIAN = "fill_median"
    FILL_MODE = "fill_mode"
    FILL_CONSTANT = "fill_constant"
    INTERPOLATE = "interpolate"
    FORWARD_FILL = "forward_fill"
    BACKWARD_FILL = "backward_fill"


class OutlierMethod(Enum):
    """Outlier detection methods"""
    ZSCORE = "zscore"
    IQR = "iqr"
    MAD = "mad"
    PERCENTILE = "percentile"
    ISOLATION_FOREST = "isolation_forest"


class NormalizationMethod(Enum):
    """Normalization methods"""
    MINMAX = "minmax"
    ZSCORE = "zscore"
    ROBUST = "robust"
    MAXABS = "maxabs"
    MEAN = "mean"


@dataclass
class CleaningResult:
    """Cleaning result"""
    original_shape: Tuple[int, int]
    cleaned_shape: Tuple[int, int]
    rows_removed: int
    columns_removed: int
    values_imputed: int
    outliers_removed: int
    duplicates_removed: int
    transformations: List[Dict[str, Any]]
    quality_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "original_shape": self.original_shape,
            "cleaned_shape": self.cleaned_shape,
            "rows_removed": self.rows_removed,
            "columns_removed": self.columns_removed,
            "values_imputed": self.values_imputed,
            "outliers_removed": self.outliers_removed,
            "duplicates_removed": self.duplicates_removed,
            "transformations": self.transformations,
            "quality_score": self.quality_score,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# DATA CLEANING ENGINE
# ============================================================

class DataCleaningEngine:
    """
    Comprehensive data cleaning engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data cleaning engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_missing_method = self.config.get("default_missing_method", MissingValueMethod.FILL_MEAN)
        self.default_outlier_method = self.config.get("default_outlier_method", OutlierMethod.IQR)
        self.default_normalization = self.config.get("default_normalization", NormalizationMethod.MINMAX)
        
        # State
        self.cleaning_history: List[CleaningResult] = []
        
        logger.info("Data cleaning engine initialized")
    
    # ============================================================
    # MISSING VALUE HANDLING
    # ============================================================
    
    def handle_missing_values(
        self,
        data: pd.DataFrame,
        method: MissingValueMethod = MissingValueMethod.FILL_MEAN,
        columns: Optional[List[str]] = None,
        constant_value: Optional[Any] = None
    ) -> Tuple[pd.DataFrame, int]:
        """
        Handle missing values
        
        Args:
            data: DataFrame
            method: Handling method
            columns: Columns to process
            constant_value: Constant value for filling
            
        Returns:
            (Cleaned DataFrame, number of imputed values)
        """
        df = data.copy()
        imputed_count = 0
        
        if columns is None:
            columns = df.columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == MissingValueMethod.DROP:
                df = df.dropna(subset=[col])
            
            elif method == MissingValueMethod.FILL_MEAN:
                if pd.api.types.is_numeric_dtype(df[col]):
                    value = df[col].mean()
                    imputed = df[col].isna().sum()
                    df[col] = df[col].fillna(value)
                    imputed_count += imputed
            
            elif method == MissingValueMethod.FILL_MEDIAN:
                if pd.api.types.is_numeric_dtype(df[col]):
                    value = df[col].median()
                    imputed = df[col].isna().sum()
                    df[col] = df[col].fillna(value)
                    imputed_count += imputed
            
            elif method == MissingValueMethod.FILL_MODE:
                value = df[col].mode()[0] if not df[col].mode().empty else None
                if value is not None:
                    imputed = df[col].isna().sum()
                    df[col] = df[col].fillna(value)
                    imputed_count += imputed
            
            elif method == MissingValueMethod.FILL_CONSTANT:
                if constant_value is not None:
                    imputed = df[col].isna().sum()
                    df[col] = df[col].fillna(constant_value)
                    imputed_count += imputed
            
            elif method == MissingValueMethod.INTERPOLATE:
                imputed = df[col].isna().sum()
                df[col] = df[col].interpolate(method='linear', limit_direction='both')
                imputed_count += imputed
            
            elif method == MissingValueMethod.FORWARD_FILL:
                imputed = df[col].isna().sum()
                df[col] = df[col].fillna(method='ffill')
                imputed_count += imputed
            
            elif method == MissingValueMethod.BACKWARD_FILL:
                imputed = df[col].isna().sum()
                df[col] = df[col].fillna(method='bfill')
                imputed_count += imputed
        
        return df, imputed_count
    
    # ============================================================
    # OUTLIER DETECTION AND REMOVAL
    # ============================================================
    
    def remove_outliers(
        self,
        data: pd.DataFrame,
        method: OutlierMethod = OutlierMethod.IQR,
        columns: Optional[List[str]] = None,
        threshold: float = 3.0
    ) -> Tuple[pd.DataFrame, int]:
        """
        Remove outliers
        
        Args:
            data: DataFrame
            method: Detection method
            columns: Columns to process
            threshold: Threshold for detection
            
        Returns:
            (Cleaned DataFrame, number of outliers removed)
        """
        df = data.copy()
        outliers_removed = 0
        
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == OutlierMethod.ZSCORE:
                zscore = np.abs(stats.zscore(df[col].dropna()))
                outlier_mask = zscore > threshold
                outlier_indices = zscore.index[outlier_mask]
                df = df.drop(outlier_indices)
                outliers_removed += len(outlier_indices)
            
            elif method == OutlierMethod.IQR:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
                df = df[~outlier_mask]
                outliers_removed += outlier_mask.sum()
            
            elif method == OutlierMethod.MAD:
                median = df[col].median()
                mad = np.median(np.abs(df[col] - median))
                if mad > 0:
                    modified_zscore = 0.6745 * (df[col] - median) / mad
                    outlier_mask = np.abs(modified_zscore) > threshold
                    df = df[~outlier_mask]
                    outliers_removed += outlier_mask.sum()
            
            elif method == OutlierMethod.PERCENTILE:
                lower_percentile = threshold / 100
                upper_percentile = 1 - threshold / 100
                lower_bound = df[col].quantile(lower_percentile)
                upper_bound = df[col].quantile(upper_percentile)
                outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
                df = df[~outlier_mask]
                outliers_removed += outlier_mask.sum()
        
        return df, outliers_removed
    
    # ============================================================
    # DUPLICATE REMOVAL
    # ============================================================
    
    def remove_duplicates(
        self,
        data: pd.DataFrame,
        subset: Optional[List[str]] = None,
        keep: str = 'first'
    ) -> Tuple[pd.DataFrame, int]:
        """
        Remove duplicates
        
        Args:
            data: DataFrame
            subset: Columns to consider
            keep: Which duplicates to keep
            
        Returns:
            (Cleaned DataFrame, number of duplicates removed)
        """
        df = data.copy()
        original_len = len(df)
        df = df.drop_duplicates(subset=subset, keep=keep)
        duplicates_removed = original_len - len(df)
        return df, duplicates_removed
    
    # ============================================================
    # DATA NORMALIZATION
    # ============================================================
    
    def normalize_data(
        self,
        data: pd.DataFrame,
        method: NormalizationMethod = NormalizationMethod.MINMAX,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Normalize data
        
        Args:
            data: DataFrame
            method: Normalization method
            columns: Columns to process
            
        Returns:
            Normalized DataFrame
        """
        df = data.copy()
        
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == NormalizationMethod.MINMAX:
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val != min_val:
                    df[col] = (df[col] - min_val) / (max_val - min_val)
            
            elif method == NormalizationMethod.ZSCORE:
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    df[col] = (df[col] - mean) / std
            
            elif method == NormalizationMethod.ROBUST:
                median = df[col].median()
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    df[col] = (df[col] - median) / iqr
            
            elif method == NormalizationMethod.MAXABS:
                max_abs = df[col].abs().max()
                if max_abs > 0:
                    df[col] = df[col] / max_abs
            
            elif method == NormalizationMethod.MEAN:
                mean = df[col].mean()
                if mean != 0:
                    df[col] = df[col] / mean
        
        return df
    
    # ============================================================
    # DATA QUALITY SCORING
    # ============================================================
    
    def score_data_quality(self, data: pd.DataFrame) -> float:
        """
        Score data quality
        
        Args:
            data: DataFrame
            
        Returns:
            Quality score (0-1)
        """
        scores = []
        
        # Completeness score
        total_cells = data.shape[0] * data.shape[1]
        non_null_cells = data.count().sum()
        completeness = non_null_cells / total_cells if total_cells > 0 else 0
        scores.append(completeness * 0.3)
        
        # Duplicate score
        duplicate_count = data.duplicated().sum()
        duplicate_rate = duplicate_count / len(data) if len(data) > 0 else 0
        duplicate_score = 1 - duplicate_rate
        scores.append(duplicate_score * 0.2)
        
        # Outlier score
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        outlier_scores = []
        for col in numeric_cols:
            if col in data.columns:
                q1 = data[col].quantile(0.25)
                q3 = data[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                outliers = ((data[col] < lower_bound) | (data[col] > upper_bound)).sum()
                outlier_rate = outliers / len(data) if len(data) > 0 else 0
                outlier_scores.append(1 - outlier_rate)
        
        if outlier_scores:
            outlier_score = np.mean(outlier_scores)
        else:
            outlier_score = 1.0
        scores.append(outlier_score * 0.25)
        
        # Consistency score
        type_consistency = []
        for col in data.columns:
            if data[col].dtype == 'object':
                # Check string consistency
                if len(data[col]) > 0:
                    lengths = data[col].str.len()
                    if lengths.std() / (lengths.mean() + 0.001) < 0.5:
                        type_consistency.append(1.0)
                    else:
                        type_consistency.append(0.5)
                else:
                    type_consistency.append(1.0)
            else:
                type_consistency.append(1.0)
        
        consistency_score = np.mean(type_consistency) if type_consistency else 1.0
        scores.append(consistency_score * 0.25)
        
        return sum(scores)
    
    # ============================================================
    # COMPLETE CLEANING PIPELINE
    # ============================================================
    
    def clean_data(
        self,
        data: pd.DataFrame,
        handle_missing: bool = True,
        remove_outliers: bool = True,
        remove_duplicates: bool = True,
        normalize: bool = False,
        missing_method: Optional[MissingValueMethod] = None,
        outlier_method: Optional[OutlierMethod] = None,
        normalization_method: Optional[NormalizationMethod] = None
    ) -> CleaningResult:
        """
        Run complete cleaning pipeline
        
        Args:
            data: DataFrame to clean
            handle_missing: Handle missing values
            remove_outliers: Remove outliers
            remove_duplicates: Remove duplicates
            normalize: Normalize data
            missing_method: Missing value method
            outlier_method: Outlier detection method
            normalization_method: Normalization method
            
        Returns:
            CleaningResult
        """
        original_shape = data.shape
        df = data.copy()
        transformations = []
        values_imputed = 0
        outliers_removed = 0
        duplicates_removed = 0
        
        # Handle missing values
        if handle_missing:
            method = missing_method or self.default_missing_method
            df, imputed = self.handle_missing_values(df, method)
            values_imputed += imputed
            transformations.append({
                "type": "handle_missing",
                "method": method.value,
                "imputed": imputed,
            })
        
        # Remove outliers
        if remove_outliers:
            method = outlier_method or self.default_outlier_method
            df, removed = self.remove_outliers(df, method)
            outliers_removed += removed
            transformations.append({
                "type": "remove_outliers",
                "method": method.value,
                "removed": removed,
            })
        
        # Remove duplicates
        if remove_duplicates:
            df, removed = self.remove_duplicates(df)
            duplicates_removed += removed
            transformations.append({
                "type": "remove_duplicates",
                "removed": removed,
            })
        
        # Normalize
        if normalize:
            method = normalization_method or self.default_normalization
            df = self.normalize_data(df, method)
            transformations.append({
                "type": "normalize",
                "method": method.value,
            })
        
        # Calculate quality score
        quality_score = self.score_data_quality(df)
        
        result = CleaningResult(
            original_shape=original_shape,
            cleaned_shape=df.shape,
            rows_removed=original_shape[0] - df.shape[0],
            columns_removed=original_shape[1] - df.shape[1],
            values_imputed=values_imputed,
            outliers_removed=outliers_removed,
            duplicates_removed=duplicates_removed,
            transformations=transformations,
            quality_score=quality_score,
            timestamp=datetime.now(),
        )
        
        self.cleaning_history.append(result)
        return result
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cleaning statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_cleaning_operations": len(self.cleaning_history),
            "total_rows_removed": sum(r.rows_removed for r in self.cleaning_history),
            "total_columns_removed": sum(r.columns_removed for r in self.cleaning_history),
            "total_values_imputed": sum(r.values_imputed for r in self.cleaning_history),
            "total_outliers_removed": sum(r.outliers_removed for r in self.cleaning_history),
            "total_duplicates_removed": sum(r.duplicates_removed for r in self.cleaning_history),
            "average_quality_score": sum(r.quality_score for r in self.cleaning_history) / len(self.cleaning_history) if self.cleaning_history else 0,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "MissingValueMethod",
    "OutlierMethod",
    "NormalizationMethod",
    
    # Dataclasses
    "CleaningResult",
    
    # Classes
    "DataCleaningEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

# trading/bots/hedge_bot/hedge_bot_cleaner.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Cleaner Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Cleaner Module

This module provides comprehensive data cleaning and preprocessing
capabilities for the NEXUS Hedge Bot system. It handles data quality
issues, removes noise, and prepares data for analysis.

The module covers:
- Missing Value Handling
- Outlier Detection and Removal
- Data Normalization
- Data Smoothing
- Noise Reduction
- Duplicate Removal
- Data Imputation
- Data Validation
- Data Transformation
- Data Standardization
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
from scipy.signal import savgol_filter, medfilt

logger = logging.getLogger(__name__)


# ============================================================
# CLEANER ENUMS
# ============================================================

class CleanerMethod(Enum):
    """Cleaning methods"""
    REMOVE = "remove"
    IMPUTE = "impute"
    FILL = "fill"
    INTERPOLATE = "interpolate"
    SMOOTH = "smooth"
    FILTER = "filter"
    NORMALIZE = "normalize"
    STANDARDIZE = "standardize"


class ImputationMethod(Enum):
    """Imputation methods"""
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"
    LINEAR = "linear"
    POLYNOMIAL = "polynomial"
    KNN = "knn"
    ITERATIVE = "iterative"
    CONSTANT = "constant"


class OutlierMethod(Enum):
    """Outlier detection methods"""
    ZSCORE = "zscore"
    IQR = "iqr"
    MAD = "mad"
    PERCENTILE = "percentile"
    ISOLATION_FOREST = "isolation_forest"
    DBSCAN = "dbscan"


@dataclass
class CleaningConfig:
    """Cleaning configuration"""
    method: CleanerMethod
    parameters: Dict[str, Any]
    columns: List[str]
    target: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "method": self.method.value,
            "parameters": self.parameters,
            "columns": self.columns,
            "target": self.target,
        }


@dataclass
class CleaningResult:
    """Cleaning result"""
    cleaned_data: pd.DataFrame
    removed_rows: int
    imputed_values: int
    outliers_removed: int
    duplicates_removed: int
    transformations: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "removed_rows": self.removed_rows,
            "imputed_values": self.imputed_values,
            "outliers_removed": self.outliers_removed,
            "duplicates_removed": self.duplicates_removed,
            "transformations": self.transformations,
            "metrics": self.metrics,
        }


# ============================================================
# DATA CLEANER
# ============================================================

class DataCleaner:
    """
    Comprehensive data cleaner for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data cleaner
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_method = self.config.get("default_method", "remove")
        self.verbose = self.config.get("verbose", False)
        
        # Metrics tracking
        self.cleaning_history: List[CleaningResult] = []
        self.total_cleaned_rows: int = 0
        
        logger.info("Data cleaner initialized")
    
    # ============================================================
    # MISSING VALUE HANDLING
    # ============================================================
    
    def handle_missing_values(
        self,
        data: pd.DataFrame,
        method: ImputationMethod = ImputationMethod.MEAN,
        columns: Optional[List[str]] = None,
        constant_value: Optional[Any] = None
    ) -> pd.DataFrame:
        """
        Handle missing values
        
        Args:
            data: DataFrame
            method: Imputation method
            columns: Columns to process
            constant_value: Constant value for imputation
            
        Returns:
            Cleaned DataFrame
        """
        df = data.copy()
        processed = 0
        
        if columns is None:
            columns = df.columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == ImputationMethod.MEAN:
                if pd.api.types.is_numeric_dtype(df[col]):
                    value = df[col].mean()
                    df[col] = df[col].fillna(value)
                    processed += df[col].isna().sum()
            
            elif method == ImputationMethod.MEDIAN:
                if pd.api.types.is_numeric_dtype(df[col]):
                    value = df[col].median()
                    df[col] = df[col].fillna(value)
                    processed += df[col].isna().sum()
            
            elif method == ImputationMethod.MODE:
                value = df[col].mode()[0] if not df[col].mode().empty else None
                if value is not None:
                    df[col] = df[col].fillna(value)
                    processed += df[col].isna().sum()
            
            elif method == ImputationMethod.LINEAR:
                df[col] = df[col].interpolate(method='linear', limit_direction='both')
                processed += df[col].isna().sum()
            
            elif method == ImputationMethod.POLYNOMIAL:
                df[col] = df[col].interpolate(method='polynomial', order=2, limit_direction='both')
                processed += df[col].isna().sum()
            
            elif method == ImputationMethod.CONSTANT:
                if constant_value is not None:
                    df[col] = df[col].fillna(constant_value)
                    processed += df[col].isna().sum()
            
            elif method == ImputationMethod.KNN:
                # Simple KNN imputation
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 1:
                    from sklearn.impute import KNNImputer
                    imputer = KNNImputer(n_neighbors=5)
                    df[numeric_cols] = imputer.fit_transform(df[numeric_cols])
                    processed += df[col].isna().sum()
        
        return df
    
    # ============================================================
    # OUTLIER DETECTION AND REMOVAL
    # ============================================================
    
    def remove_outliers(
        self,
        data: pd.DataFrame,
        method: OutlierMethod = OutlierMethod.IQR,
        columns: Optional[List[str]] = None,
        threshold: float = 3.0
    ) -> pd.DataFrame:
        """
        Remove outliers from data
        
        Args:
            data: DataFrame
            method: Outlier detection method
            columns: Columns to process
            threshold: Threshold for outlier detection
            
        Returns:
            Cleaned DataFrame
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
        
        return df
    
    # ============================================================
    # DATA SMOOTHING
    # ============================================================
    
    def smooth_data(
        self,
        data: pd.DataFrame,
        method: str = "savgol",
        window_length: int = 11,
        polyorder: int = 2,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Smooth data
        
        Args:
            data: DataFrame
            method: Smoothing method (savgol, median, moving_average)
            window_length: Window length for smoothing
            polyorder: Polynomial order for Savitzky-Golay
            columns: Columns to process
            
        Returns:
            Smoothed DataFrame
        """
        df = data.copy()
        
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            values = df[col].values
            if len(values) < window_length:
                continue
            
            if method == "savgol":
                try:
                    df[col] = savgol_filter(values, window_length, polyorder)
                except:
                    pass
            
            elif method == "median":
                df[col] = medfilt(values, window_length if window_length % 2 == 1 else window_length + 1)
            
            elif method == "moving_average":
                df[col] = df[col].rolling(window=window_length, center=True).mean()
                df[col] = df[col].fillna(method='bfill').fillna(method='ffill')
        
        return df
    
    # ============================================================
    # DATA NORMALIZATION
    # ============================================================
    
    def normalize_data(
        self,
        data: pd.DataFrame,
        method: str = "minmax",
        columns: Optional[List[str]] = None,
        range_min: float = 0.0,
        range_max: float = 1.0
    ) -> pd.DataFrame:
        """
        Normalize data
        
        Args:
            data: DataFrame
            method: Normalization method (minmax, zscore, robust)
            columns: Columns to process
            range_min: Minimum value for minmax normalization
            range_max: Maximum value for minmax normalization
            
        Returns:
            Normalized DataFrame
        """
        df = data.copy()
        
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == "minmax":
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val != min_val:
                    df[col] = (df[col] - min_val) / (max_val - min_val) * (range_max - range_min) + range_min
            
            elif method == "zscore":
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    df[col] = (df[col] - mean) / std
            
            elif method == "robust":
                median = df[col].median()
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    df[col] = (df[col] - median) / iqr
        
        return df
    
    # ============================================================
    # DUPLICATE REMOVAL
    # ============================================================
    
    def remove_duplicates(
        self,
        data: pd.DataFrame,
        subset: Optional[List[str]] = None,
        keep: str = 'first'
    ) -> pd.DataFrame:
        """
        Remove duplicates
        
        Args:
            data: DataFrame
            subset: Columns to consider for duplication
            keep: Which duplicates to keep
            
        Returns:
            DataFrame with duplicates removed
        """
        df = data.copy()
        duplicates_removed = len(df) - len(df.drop_duplicates(subset=subset, keep=keep))
        df = df.drop_duplicates(subset=subset, keep=keep)
        return df
    
    # ============================================================
    # COMPLETE CLEANING PIPELINE
    # ============================================================
    
    def clean(
        self,
        data: pd.DataFrame,
        config: CleaningConfig
    ) -> CleaningResult:
        """
        Apply complete cleaning pipeline
        
        Args:
            data: DataFrame to clean
            config: Cleaning configuration
            
        Returns:
            CleaningResult
        """
        df = data.copy()
        transformations = []
        metrics = {}
        
        # Track initial state
        initial_rows = len(df)
        initial_nulls = df.isnull().sum().sum()
        
        # Apply cleaning steps
        if config.method == CleanerMethod.REMOVE:
            # Remove outliers
            method = config.parameters.get("outlier_method", OutlierMethod.IQR)
            threshold = config.parameters.get("threshold", 3.0)
            df = self.remove_outliers(df, method, config.columns, threshold)
            transformations.append({
                "step": "remove_outliers",
                "method": method.value,
                "threshold": threshold,
            })
        
        elif config.method == CleanerMethod.IMPUTE:
            # Handle missing values
            method = config.parameters.get("imputation_method", ImputationMethod.MEAN)
            constant = config.parameters.get("constant_value")
            df = self.handle_missing_values(df, method, config.columns, constant)
            transformations.append({
                "step": "handle_missing_values",
                "method": method.value,
            })
        
        elif config.method == CleanerMethod.SMOOTH:
            # Smooth data
            method = config.parameters.get("smooth_method", "savgol")
            window = config.parameters.get("window_length", 11)
            poly = config.parameters.get("polyorder", 2)
            df = self.smooth_data(df, method, window, poly, config.columns)
            transformations.append({
                "step": "smooth_data",
                "method": method,
                "window_length": window,
            })
        
        elif config.method == CleanerMethod.NORMALIZE:
            # Normalize data
            method = config.parameters.get("normalize_method", "minmax")
            df = self.normalize_data(df, method, config.columns)
            transformations.append({
                "step": "normalize_data",
                "method": method,
            })
        
        elif config.method == CleanerMethod.STANDARDIZE:
            # Standardize data
            df = self.normalize_data(df, "zscore", config.columns)
            transformations.append({
                "step": "standardize_data",
                "method": "zscore",
            })
        
        elif config.method == CleanerMethod.FILTER:
            # Apply filter
            pass
        
        # Always remove duplicates if configured
        if config.parameters.get("remove_duplicates", True):
            subset = config.parameters.get("duplicate_subset")
            df = self.remove_duplicates(df, subset)
            transformations.append({
                "step": "remove_duplicates",
                "subset": subset,
            })
        
        # Calculate metrics
        final_rows = len(df)
        final_nulls = df.isnull().sum().sum()
        
        metrics = {
            "initial_rows": initial_rows,
            "final_rows": final_rows,
            "rows_removed": initial_rows - final_rows,
            "initial_nulls": initial_nulls,
            "final_nulls": final_nulls,
            "nulls_removed": initial_nulls - final_nulls,
        }
        
        result = CleaningResult(
            cleaned_data=df,
            removed_rows=initial_rows - final_rows,
            imputed_values=initial_nulls - final_nulls,
            outliers_removed=0,
            duplicates_removed=0,
            transformations=transformations,
            metrics=metrics,
        )
        
        self.cleaning_history.append(result)
        self.total_cleaned_rows += result.removed_rows
        
        return result
    
    # ============================================================
    # DATA QUALITY REPORT
    # ============================================================
    
    def generate_quality_report(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate data quality report
        
        Args:
            data: DataFrame to analyze
            
        Returns:
            Quality report
        """
        report = {
            "shape": {
                "rows": len(data),
                "columns": len(data.columns),
            },
            "nulls": {},
            "types": {},
            "duplicates": len(data) - len(data.drop_duplicates()),
            "outliers": {},
            "summary": {},
        }
        
        for col in data.columns:
            # Null counts
            null_count = data[col].isnull().sum()
            report["nulls"][col] = {
                "count": null_count,
                "percentage": null_count / len(data) if len(data) > 0 else 0,
            }
            
            # Data type
            report["types"][col] = str(data[col].dtype)
            
            # Summary statistics for numeric columns
            if pd.api.types.is_numeric_dtype(data[col]):
                report["summary"][col] = {
                    "min": data[col].min(),
                    "max": data[col].max(),
                    "mean": data[col].mean(),
                    "median": data[col].median(),
                    "std": data[col].std(),
                    "skew": data[col].skew(),
                    "kurtosis": data[col].kurtosis(),
                }
        
        return report
    
    # ============================================================
    # GETTER METHODS
    # ============================================================
    
    def get_cleaning_history(self) -> List[CleaningResult]:
        """
        Get cleaning history
        
        Returns:
            List of cleaning results
        """
        return self.cleaning_history
    
    def get_total_cleaned(self) -> int:
        """
        Get total rows cleaned
        
        Returns:
            Total rows cleaned
        """
        return self.total_cleaned_rows
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cleaner statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_cleaning_operations": len(self.cleaning_history),
            "total_rows_cleaned": self.total_cleaned_rows,
            "average_cleaned_per_operation": self.total_cleaned_rows / len(self.cleaning_history) if self.cleaning_history else 0,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "CleanerMethod",
    "ImputationMethod",
    "OutlierMethod",
    
    # Dataclasses
    "CleaningConfig",
    "CleaningResult",
    
    # Classes
    "DataCleaner",
]

# ============================================================
# END OF MODULE
# ============================================================

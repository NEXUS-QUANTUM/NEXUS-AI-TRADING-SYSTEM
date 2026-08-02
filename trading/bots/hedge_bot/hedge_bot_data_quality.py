# trading/bots/hedge_bot/hedge_bot_data_quality.py

import asyncio
import logging
import time
import json
import hashlib
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque
import re
import statistics
from scipy import stats
from scipy.stats import zscore, iqr, skew, kurtosis
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.covariance import EllipticEnvelope
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class QualityDimension(str, Enum):
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    VALIDITY = "validity"
    UNIQUENESS = "uniqueness"
    INTEGRITY = "integrity"
    PRECISION = "precision"
    RELIABILITY = "reliability"
    AVAILABILITY = "availability"
    RELEVANCY = "relevancy"
    USABILITY = "usability"
    TRUSTWORTHINESS = "trustworthiness"
    REPUTATION = "reputation"
    OBJECTIVITY = "objectivity"


class AnomalyType(str, Enum):
    OUTLIER = "outlier"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    INCONSISTENT = "inconsistent"
    CORRUPTED = "corrupted"
    STALE = "stale"
    BIASED = "biased"
    NOISY = "noisy"
    SEASONAL = "seasonal"
    TREND = "trend"
    SHIFT = "shift"
    SPIKE = "spike"
    DROP = "drop"
    LEVEL_CHANGE = "level_change"
    VARIANCE_CHANGE = "variance_change"


class ImputationMethod(str, Enum):
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"
    CONSTANT = "constant"
    INTERPOLATE = "interpolate"
    FORWARD_FILL = "forward_fill"
    BACKWARD_FILL = "backward_fill"
    LINEAR = "linear"
    POLYNOMIAL = "polynomial"
    SPLINE = "spline"
    KNN = "knn"
    REGRESSION = "regression"
    RANDOM = "random"
    ZERO = "zero"
    MIN = "min"
    MAX = "max"


@dataclass
class QualityMetric:
    dimension: QualityDimension
    name: str
    value: float
    threshold: Optional[float] = None
    passed: bool = True
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class QualityReport:
    id: str
    dataset_name: str
    timestamp: float
    metrics: List[QualityMetric]
    overall_score: float
    dimensions_scores: Dict[str, float]
    anomalies: List[Dict[str, Any]]
    recommendations: List[str]
    details: Dict[str, Any] = field(default_factory=dict)
    passed: bool = True


@dataclass
class Anomaly:
    id: str
    type: AnomalyType
    location: Any
    value: Any
    expected_value: Optional[Any] = None
    severity: float = 1.0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False


@dataclass
class QualityThreshold:
    dimension: QualityDimension
    metric: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    target_value: Optional[float] = None
    tolerance: float = 0.05
    severity: str = "warning"


class DataQualityManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._metrics: Dict[str, List[QualityMetric]] = defaultdict(list)
        self._reports: Dict[str, QualityReport] = {}
        self._anomalies: Dict[str, Anomaly] = {}
        self._thresholds: Dict[str, QualityThreshold] = {}
        self._data_cache: Dict[str, Any] = {}
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._alerts: List[Dict[str, Any]] = []
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        
        self._initialize_default_thresholds()
        self._initialize_quality_checks()

    def _initialize_default_thresholds(self) -> None:
        default_thresholds = [
            QualityThreshold(
                dimension=QualityDimension.ACCURACY,
                metric="accuracy_score",
                min_value=0.90,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.COMPLETENESS,
                metric="completeness_rate",
                min_value=0.95,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.CONSISTENCY,
                metric="consistency_score",
                min_value=0.90,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.TIMELINESS,
                metric="timeliness_score",
                min_value=0.85,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.VALIDITY,
                metric="validity_rate",
                min_value=0.95,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.UNIQUENESS,
                metric="uniqueness_rate",
                min_value=0.98,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.INTEGRITY,
                metric="integrity_score",
                min_value=0.98,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.PRECISION,
                metric="precision_score",
                min_value=0.85,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.RELIABILITY,
                metric="reliability_score",
                min_value=0.90,
                max_value=1.0
            ),
            QualityThreshold(
                dimension=QualityDimension.AVAILABILITY,
                metric="availability_rate",
                min_value=0.95,
                max_value=1.0
            )
        ]
        
        for threshold in default_thresholds:
            key = f"{threshold.dimension.value}:{threshold.metric}"
            self._thresholds[key] = threshold

    def _initialize_quality_checks(self) -> None:
        self._quality_checks = {
            "accuracy": self._check_accuracy,
            "completeness": self._check_completeness,
            "consistency": self._check_consistency,
            "timeliness": self._check_timeliness,
            "validity": self._check_validity,
            "uniqueness": self._check_uniqueness,
            "integrity": self._check_integrity,
            "precision": self._check_precision,
            "reliability": self._check_reliability,
            "availability": self._check_availability
        }

    async def assess_quality(
        self,
        data: Union[pd.DataFrame, Dict[str, Any], List[Any]],
        dataset_name: str,
        dimensions: Optional[List[QualityDimension]] = None
    ) -> QualityReport:
        async with self._lock:
            report_id = hashlib.md5(f"{dataset_name}_{time.time()}".encode()).hexdigest()
            
            if isinstance(data, dict):
                data = pd.DataFrame([data])
            elif isinstance(data, list):
                data = pd.DataFrame(data)
            elif not isinstance(data, pd.DataFrame):
                raise ValueError("Data must be DataFrame, dict, or list")
            
            dimensions = dimensions or list(QualityDimension)
            metrics = []
            anomalies = []
            recommendations = []
            dimensions_scores = {}
            
            for dimension in dimensions:
                dimension_metrics = []
                
                if dimension == QualityDimension.ACCURACY:
                    accuracy_metrics = await self._assess_accuracy(data)
                    dimension_metrics.extend(accuracy_metrics)
                    
                elif dimension == QualityDimension.COMPLETENESS:
                    completeness_metrics = await self._assess_completeness(data)
                    dimension_metrics.extend(completeness_metrics)
                    
                elif dimension == QualityDimension.CONSISTENCY:
                    consistency_metrics = await self._assess_consistency(data)
                    dimension_metrics.extend(consistency_metrics)
                    
                elif dimension == QualityDimension.TIMELINESS:
                    timeliness_metrics = await self._assess_timeliness(data)
                    dimension_metrics.extend(timeliness_metrics)
                    
                elif dimension == QualityDimension.VALIDITY:
                    validity_metrics = await self._assess_validity(data)
                    dimension_metrics.extend(validity_metrics)
                    
                elif dimension == QualityDimension.UNIQUENESS:
                    uniqueness_metrics = await self._assess_uniqueness(data)
                    dimension_metrics.extend(uniqueness_metrics)
                    
                elif dimension == QualityDimension.INTEGRITY:
                    integrity_metrics = await self._assess_integrity(data)
                    dimension_metrics.extend(integrity_metrics)
                    
                elif dimension == QualityDimension.PRECISION:
                    precision_metrics = await self._assess_precision(data)
                    dimension_metrics.extend(precision_metrics)
                    
                elif dimension == QualityDimension.RELIABILITY:
                    reliability_metrics = await self._assess_reliability(data)
                    dimension_metrics.extend(reliability_metrics)
                    
                elif dimension == QualityDimension.AVAILABILITY:
                    availability_metrics = await self._assess_availability(data)
                    dimension_metrics.extend(availability_metrics)
                
                dimension_score = sum(m.value for m in dimension_metrics) / len(dimension_metrics) if dimension_metrics else 0
                dimensions_scores[dimension.value] = dimension_score
                metrics.extend(dimension_metrics)
                
                if dimension_score < 0.8:
                    recommendations.append(f"Improve {dimension.value}: score is {dimension_score:.2f}")
            
            overall_score = sum(dimensions_scores.values()) / len(dimensions_scores) if dimensions_scores else 0
            
            anomaly_results = await self._detect_anomalies(data)
            anomalies.extend(anomaly_results)
            
            report = QualityReport(
                id=report_id,
                dataset_name=dataset_name,
                timestamp=time.time(),
                metrics=metrics,
                overall_score=overall_score,
                dimensions_scores=dimensions_scores,
                anomalies=anomalies,
                recommendations=recommendations,
                passed=overall_score >= 0.8
            )
            
            self._reports[report_id] = report
            await self._store_metrics(report)
            
            if not report.passed:
                await self._trigger_alert(report)
            
            return report

    async def _assess_accuracy(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            missing_count = data.isnull().sum().sum()
            total_cells = data.size
            completeness_rate = 1 - (missing_count / total_cells) if total_cells > 0 else 0
            
            duplicate_count = data.duplicated().sum()
            duplicate_rate = duplicate_count / len(data) if len(data) > 0 else 0
            
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                means = data[numeric_cols].mean()
                stds = data[numeric_cols].std()
                outliers = 0
                for col in numeric_cols:
                    z_scores = np.abs(zscore(data[col].dropna()))
                    outliers += (z_scores > 3).sum()
                
                outlier_rate = outliers / (len(numeric_cols) * len(data)) if len(data) > 0 else 0
            else:
                outlier_rate = 0
            
            accuracy_score = 1 - (duplicate_rate * 0.3 + outlier_rate * 0.7)
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.ACCURACY,
                    name="accuracy_score",
                    value=max(0, min(1, accuracy_score)),
                    threshold=0.90,
                    passed=accuracy_score >= 0.90,
                    details={
                        "duplicate_rate": duplicate_rate,
                        "outlier_rate": outlier_rate,
                        "completeness_rate": completeness_rate
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Error assessing accuracy: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.ACCURACY,
                    name="accuracy_score",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_completeness(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            total_cells = data.size
            missing_count = data.isnull().sum().sum()
            completeness_rate = 1 - (missing_count / total_cells) if total_cells > 0 else 0
            
            column_completeness = {}
            for col in data.columns:
                col_missing = data[col].isnull().sum()
                col_total = len(data)
                col_rate = 1 - (col_missing / col_total) if col_total > 0 else 0
                column_completeness[col] = col_rate
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.COMPLETENESS,
                    name="completeness_rate",
                    value=completeness_rate,
                    threshold=0.95,
                    passed=completeness_rate >= 0.95,
                    details={
                        "missing_count": int(missing_count),
                        "total_cells": int(total_cells),
                        "column_completeness": column_completeness
                    }
                )
            )
            
            for col, rate in column_completeness.items():
                if rate < 0.8:
                    metrics.append(
                        QualityMetric(
                            dimension=QualityDimension.COMPLETENESS,
                            name=f"completeness_{col}",
                            value=rate,
                            threshold=0.8,
                            passed=rate >= 0.8,
                            details={"column": col}
                        )
                    )
            
        except Exception as e:
            logger.error(f"Error assessing completeness: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.COMPLETENESS,
                    name="completeness_rate",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_consistency(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            consistency_scores = {}
            
            for col in numeric_cols:
                if len(data[col].dropna()) > 1:
                    std = data[col].std()
                    mean = data[col].mean()
                    cv = std / mean if mean != 0 else 0
                    consistency_scores[col] = 1 / (1 + cv) if cv > 0 else 1
            
            avg_consistency = sum(consistency_scores.values()) / len(consistency_scores) if consistency_scores else 0
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.CONSISTENCY,
                    name="consistency_score",
                    value=avg_consistency,
                    threshold=0.90,
                    passed=avg_consistency >= 0.90,
                    details={
                        "column_scores": consistency_scores,
                        "columns_analyzed": len(consistency_scores)
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Error assessing consistency: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.CONSISTENCY,
                    name="consistency_score",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_timeliness(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            if 'timestamp' in data.columns or 'date' in data.columns or 'time' in data.columns:
                time_col = None
                for col in ['timestamp', 'date', 'time', 'datetime']:
                    if col in data.columns:
                        time_col = col
                        break
                
                if time_col:
                    times = pd.to_datetime(data[time_col])
                    if len(times) > 1:
                        time_diff = times.diff().dropna()
                        avg_delay = time_diff.mean().total_seconds()
                        max_delay = time_diff.max().total_seconds()
                        
                        expected_interval = self.config.get("expected_interval", 60)
                        timeliness_score = max(0, 1 - (avg_delay / expected_interval))
                        
                        metrics.append(
                            QualityMetric(
                                dimension=QualityDimension.TIMELINESS,
                                name="timeliness_score",
                                value=timeliness_score,
                                threshold=0.85,
                                passed=timeliness_score >= 0.85,
                                details={
                                    "avg_delay_seconds": avg_delay,
                                    "max_delay_seconds": max_delay,
                                    "expected_interval": expected_interval
                                }
                            )
                        )
            else:
                metrics.append(
                    QualityMetric(
                        dimension=QualityDimension.TIMELINESS,
                        name="timeliness_score",
                        value=1.0,
                        passed=True,
                        details={"note": "No timestamp column found"}
                    )
                )
            
        except Exception as e:
            logger.error(f"Error assessing timeliness: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.TIMELINESS,
                    name="timeliness_score",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_validity(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            invalid_count = 0
            total_values = 0
            
            for col in data.columns:
                col_data = data[col].dropna()
                total_values += len(col_data)
                
                if pd.api.types.is_numeric_dtype(col_data):
                    invalid = col_data[~np.isfinite(col_data)].count()
                    invalid_count += invalid
                elif pd.api.types.is_string_dtype(col_data):
                    invalid = col_data.str.match(r'^[^\x00-\x1F\x7F]*$').sum()
                    invalid_count += invalid
            
            validity_rate = 1 - (invalid_count / total_values) if total_values > 0 else 0
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.VALIDITY,
                    name="validity_rate",
                    value=validity_rate,
                    threshold=0.95,
                    passed=validity_rate >= 0.95,
                    details={
                        "invalid_count": int(invalid_count),
                        "total_values": int(total_values)
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Error assessing validity: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.VALIDITY,
                    name="validity_rate",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_uniqueness(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            if len(data) > 0:
                duplicate_count = data.duplicated().sum()
                uniqueness_rate = 1 - (duplicate_count / len(data))
            else:
                uniqueness_rate = 1.0
            
            if 'id' in data.columns or 'unique_id' in data.columns:
                id_col = 'id' if 'id' in data.columns else 'unique_id'
                unique_ids = data[id_col].nunique()
                total_ids = len(data)
                id_uniqueness = unique_ids / total_ids if total_ids > 0 else 0
            else:
                id_uniqueness = 1.0
            
            overall_uniqueness = (uniqueness_rate + id_uniqueness) / 2
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.UNIQUENESS,
                    name="uniqueness_rate",
                    value=overall_uniqueness,
                    threshold=0.98,
                    passed=overall_uniqueness >= 0.98,
                    details={
                        "duplicate_count": int(duplicate_count),
                        "id_uniqueness": id_uniqueness,
                        "total_rows": len(data)
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Error assessing uniqueness: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.UNIQUENESS,
                    name="uniqueness_rate",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_integrity(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            integrity_violations = 0
            total_checks = 0
            
            if 'id' in data.columns:
                total_checks += 1
                if data['id'].isnull().sum() > 0:
                    integrity_violations += 1
            
            if 'timestamp' in data.columns or 'date' in data.columns:
                total_checks += 1
                time_col = 'timestamp' if 'timestamp' in data.columns else 'date'
                if data[time_col].isnull().sum() > 0:
                    integrity_violations += 1
            
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if data[col].isnull().sum() > len(data) * 0.5:
                    integrity_violations += 1
                    total_checks += 1
            
            integrity_score = 1 - (integrity_violations / max(1, total_checks))
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.INTEGRITY,
                    name="integrity_score",
                    value=integrity_score,
                    threshold=0.98,
                    passed=integrity_score >= 0.98,
                    details={
                        "violations": integrity_violations,
                        "checks": total_checks
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Error assessing integrity: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.INTEGRITY,
                    name="integrity_score",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_precision(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            precision_scores = {}
            
            for col in numeric_cols:
                if len(data[col].dropna()) > 0:
                    unique_vals = data[col].nunique()
                    total_vals = len(data[col].dropna())
                    precision = unique_vals / total_vals if total_vals > 0 else 0
                    precision_scores[col] = precision
            
            avg_precision = sum(precision_scores.values()) / len(precision_scores) if precision_scores else 0
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.PRECISION,
                    name="precision_score",
                    value=avg_precision,
                    threshold=0.85,
                    passed=avg_precision >= 0.85,
                    details={
                        "column_scores": precision_scores,
                        "columns_analyzed": len(precision_scores)
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Error assessing precision: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.PRECISION,
                    name="precision_score",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_reliability(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            if len(data) > 1:
                numeric_cols = data.select_dtypes(include=[np.number]).columns
                reliability_scores = {}
                
                for col in numeric_cols:
                    if len(data[col].dropna()) > 1:
                        std = data[col].std()
                        mean = data[col].mean()
                        if mean != 0:
                            cv = std / abs(mean)
                            reliability = 1 / (1 + cv)
                        else:
                            reliability = 0.5
                        reliability_scores[col] = min(1, max(0, reliability))
                
                avg_reliability = sum(reliability_scores.values()) / len(reliability_scores) if reliability_scores else 0
            else:
                avg_reliability = 1.0
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.RELIABILITY,
                    name="reliability_score",
                    value=avg_reliability,
                    threshold=0.90,
                    passed=avg_reliability >= 0.90,
                    details={
                        "column_scores": reliability_scores,
                        "columns_analyzed": len(reliability_scores)
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Error assessing reliability: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.RELIABILITY,
                    name="reliability_score",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _assess_availability(self, data: pd.DataFrame) -> List[QualityMetric]:
        metrics = []
        
        try:
            total_cells = data.size
            available_cells = data.count().sum()
            availability_rate = available_cells / total_cells if total_cells > 0 else 0
            
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.AVAILABILITY,
                    name="availability_rate",
                    value=availability_rate,
                    threshold=0.95,
                    passed=availability_rate >= 0.95,
                    details={
                        "available_cells": int(available_cells),
                        "total_cells": int(total_cells)
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Error assessing availability: {e}")
            metrics.append(
                QualityMetric(
                    dimension=QualityDimension.AVAILABILITY,
                    name="availability_rate",
                    value=0.0,
                    passed=False,
                    details={"error": str(e)}
                )
            )
        
        return metrics

    async def _detect_anomalies(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        anomalies = []
        
        try:
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            
            for col in numeric_cols:
                col_data = data[col].dropna()
                if len(col_data) > 0:
                    z_scores = np.abs(zscore(col_data))
                    outlier_indices = np.where(z_scores > 3)[0]
                    
                    for idx in outlier_indices:
                        original_idx = col_data.index[idx]
                        anomalies.append({
                            "type": AnomalyType.OUTLIER.value,
                            "location": f"{col}[{original_idx}]",
                            "value": float(col_data.iloc[idx]),
                            "expected_value": float(col_data.mean()),
                            "severity": float(z_scores[idx] / 3),
                            "description": f"Outlier in column {col}",
                            "metadata": {
                                "column": col,
                                "index": original_idx,
                                "z_score": float(z_scores[idx])
                            }
                        })
            
            if len(data) > 0:
                duplicates = data.duplicated()
                duplicate_indices = data[duplicates].index.tolist()
                
                for idx in duplicate_indices[:10]:
                    anomalies.append({
                        "type": AnomalyType.DUPLICATE.value,
                        "location": f"row[{idx}]",
                        "value": data.iloc[idx].to_dict(),
                        "severity": 0.5,
                        "description": "Duplicate row detected",
                        "metadata": {"index": idx}
                    })
            
            missing_cols = data.columns[data.isnull().any()].tolist()
            for col in missing_cols:
                missing_count = data[col].isnull().sum()
                if missing_count > 0:
                    anomalies.append({
                        "type": AnomalyType.MISSING.value,
                        "location": col,
                        "value": None,
                        "expected_value": len(data),
                        "severity": min(1, missing_count / len(data)),
                        "description": f"Missing values in column {col}",
                        "metadata": {
                            "column": col,
                            "missing_count": int(missing_count),
                            "total_count": len(data)
                        }
                    })
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
        
        return anomalies

    async def _store_metrics(self, report: QualityReport) -> None:
        for metric in report.metrics:
            key = f"{metric.dimension.value}:{metric.name}"
            self._metrics[key].append(metric)
            if len(self._metrics[key]) > 1000:
                self._metrics[key] = self._metrics[key][-1000:]

    async def _trigger_alert(self, report: QualityReport) -> None:
        alert = {
            "timestamp": time.time(),
            "report_id": report.id,
            "dataset": report.dataset_name,
            "overall_score": report.overall_score,
            "failed_dimensions": [
                dim for dim, score in report.dimensions_scores.items()
                if score < 0.8
            ],
            "recommendations": report.recommendations
        }
        
        self._alerts.append(alert)
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]
        
        logger.warning(f"Data quality alert: {json.dumps(alert, default=str)}")

    async def get_quality_report(self, report_id: str) -> Optional[QualityReport]:
        return self._reports.get(report_id)

    async def get_latest_report(self, dataset_name: str) -> Optional[QualityReport]:
        reports = [
            r for r in self._reports.values()
            if r.dataset_name == dataset_name
        ]
        if reports:
            return max(reports, key=lambda r: r.timestamp)
        return None

    async def get_metrics_history(
        self,
        dimension: QualityDimension,
        metric_name: str,
        limit: int = 100
    ) -> List[QualityMetric]:
        key = f"{dimension.value}:{metric_name}"
        return list(self._metrics.get(key, []))[-limit:]

    async def get_anomalies(
        self,
        limit: int = 100,
        resolved: bool = False
    ) -> List[Anomaly]:
        anomalies = [a for a in self._anomalies.values() if a.resolved == resolved]
        return sorted(anomalies, key=lambda a: a.timestamp, reverse=True)[:limit]

    async def add_threshold(self, threshold: QualityThreshold) -> None:
        key = f"{threshold.dimension.value}:{threshold.metric}"
        self._thresholds[key] = threshold

    async def remove_threshold(self, dimension: QualityDimension, metric: str) -> bool:
        key = f"{dimension.value}:{metric}"
        if key in self._thresholds:
            del self._thresholds[key]
            return True
        return False

    async def get_thresholds(self) -> List[QualityThreshold]:
        return list(self._thresholds.values())

    async def validate_against_thresholds(self, metric: QualityMetric) -> bool:
        key = f"{metric.dimension.value}:{metric.name}"
        threshold = self._thresholds.get(key)
        
        if not threshold:
            return True
        
        if threshold.min_value is not None and metric.value < threshold.min_value:
            return False
        
        if threshold.max_value is not None and metric.value > threshold.max_value:
            return False
        
        if threshold.target_value is not None:
            if abs(metric.value - threshold.target_value) > threshold.tolerance * threshold.target_value:
                return False
        
        return True

    async def impute_missing_values(
        self,
        data: pd.DataFrame,
        method: ImputationMethod = ImputationMethod.MEAN,
        columns: Optional[List[str]] = None,
        constant_value: Any = None
    ) -> pd.DataFrame:
        df = data.copy()
        columns = columns or df.columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if df[col].isnull().sum() == 0:
                continue
            
            if method == ImputationMethod.MEAN:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col].fillna(df[col].mean(), inplace=True)
                else:
                    df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else '', inplace=True)
            
            elif method == ImputationMethod.MEDIAN:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col].fillna(df[col].median(), inplace=True)
                else:
                    df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else '', inplace=True)
            
            elif method == ImputationMethod.MODE:
                df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else '', inplace=True)
            
            elif method == ImputationMethod.CONSTANT:
                df[col].fillna(constant_value, inplace=True)
            
            elif method == ImputationMethod.FORWARD_FILL:
                df[col].fillna(method='ffill', inplace=True)
            
            elif method == ImputationMethod.BACKWARD_FILL:
                df[col].fillna(method='bfill', inplace=True)
            
            elif method == ImputationMethod.INTERPOLATE:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col].interpolate(method='linear', inplace=True)
            
            elif method == ImputationMethod.ZERO:
                df[col].fillna(0, inplace=True)
            
            elif method == ImputationMethod.MIN:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col].fillna(df[col].min(), inplace=True)
            
            elif method == ImputationMethod.MAX:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col].fillna(df[col].max(), inplace=True)
            
            elif method == ImputationMethod.RANDOM:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col].fillna(np.random.choice(df[col].dropna()), inplace=True)
                else:
                    df[col].fillna(np.random.choice(df[col].dropna()), inplace=True)
        
        return df

    async def remove_outliers(
        self,
        data: pd.DataFrame,
        columns: Optional[List[str]] = None,
        method: str = "zscore",
        threshold: float = 3.0
    ) -> pd.DataFrame:
        df = data.copy()
        columns = columns or df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            col_data = df[col].dropna()
            if len(col_data) < 2:
                continue
            
            if method == "zscore":
                z_scores = np.abs(zscore(col_data))
                mask = z_scores <= threshold
                df.loc[col_data.index[~mask], col] = np.nan
            
            elif method == "iqr":
                q1 = col_data.quantile(0.25)
                q3 = col_data.quantile(0.75)
                iqr_val = q3 - q1
                lower_bound = q1 - 1.5 * iqr_val
                upper_bound = q3 + 1.5 * iqr_val
                mask = (col_data >= lower_bound) & (col_data <= upper_bound)
                df.loc[col_data.index[~mask], col] = np.nan
            
            elif method == "percentile":
                lower = col_data.quantile(0.01)
                upper = col_data.quantile(0.99)
                mask = (col_data >= lower) & (col_data <= upper)
                df.loc[col_data.index[~mask], col] = np.nan
        
        return df

    async def detect_anomalies_ml(
        self,
        data: pd.DataFrame,
        columns: Optional[List[str]] = None,
        algorithm: str = "isolation_forest",
        contamination: float = 0.1
    ) -> pd.Series:
        df = data.copy()
        columns = columns or df.select_dtypes(include=[np.number]).columns.tolist()
        
        if not columns:
            return pd.Series([False] * len(df))
        
        X = df[columns].fillna(df[columns].mean())
        
        if algorithm == "isolation_forest":
            model = IsolationForest(contamination=contamination, random_state=42)
            predictions = model.fit_predict(X)
            anomalies = predictions == -1
        
        elif algorithm == "lof":
            model = LocalOutlierFactor(contamination=contamination)
            predictions = model.fit_predict(X)
            anomalies = predictions == -1
        
        elif algorithm == "elliptic_envelope":
            model = EllipticEnvelope(contamination=contamination, random_state=42)
            predictions = model.fit_predict(X)
            anomalies = predictions == -1
        
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        return pd.Series(anomalies, index=df.index)

    async def standardize_data(
        self,
        data: pd.DataFrame,
        columns: Optional[List[str]] = None,
        method: str = "standard"
    ) -> pd.DataFrame:
        df = data.copy()
        columns = columns or df.select_dtypes(include=[np.number]).columns.tolist()
        
        if not columns:
            return df
        
        X = df[columns].fillna(df[columns].mean())
        
        if method == "standard":
            scaler = StandardScaler()
            df[columns] = scaler.fit_transform(X)
        
        elif method == "robust":
            scaler = RobustScaler()
            df[columns] = scaler.fit_transform(X)
        
        elif method == "minmax":
            scaler = MinMaxScaler()
            df[columns] = scaler.fit_transform(X)
        
        return df

    def get_stats(self) -> Dict[str, Any]:
        return {
            "reports": len(self._reports),
            "metrics": sum(len(v) for v in self._metrics.values()),
            "anomalies": len(self._anomalies),
            "alerts": len(self._alerts),
            "thresholds": len(self._thresholds),
            "running": self._running,
            "monitoring_tasks": len(self._monitoring_tasks)
        }

    def clear_old_reports(self, days: int = 30) -> int:
        cutoff = time.time() - days * 86400
        to_remove = [
            rid for rid, report in self._reports.items()
            if report.timestamp < cutoff
        ]
        for rid in to_remove:
            del self._reports[rid]
        return len(to_remove)

    def clear_old_metrics(self, days: int = 30) -> int:
        cutoff = time.time() - days * 86400
        removed = 0
        for key in list(self._metrics.keys()):
            self._metrics[key] = [
                m for m in self._metrics[key]
                if m.timestamp >= cutoff
            ]
            removed += len(self._metrics[key])
        return removed


__all__ = [
    "QualityDimension",
    "AnomalyType",
    "ImputationMethod",
    "QualityMetric",
    "QualityReport",
    "Anomaly",
    "QualityThreshold",
    "DataQualityManager"
]

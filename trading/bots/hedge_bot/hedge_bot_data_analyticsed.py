# trading/bots/hedge_bot/hedge_bot_data_analyticsed.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Analytics (Enhanced) Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Analytics (Enhanced) Module

This module provides enhanced data analytics and business intelligence
capabilities for the NEXUS Hedge Bot system. It extends the base analytics
with advanced statistical methods, machine learning, and visualization.

The module covers:
- Advanced Statistical Analytics
- Machine Learning Analytics
- Time Series Analytics
- Predictive Modeling
- Anomaly Detection
- Pattern Recognition
- Trend Analysis
- Seasonality Detection
- Correlation Analysis
- Feature Engineering
- Model Evaluation
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
from scipy import stats
from scipy.signal import find_peaks
from scipy.fft import fft, fftfreq
import warnings
warnings.filterwarnings("ignore")

# Try to import ML libraries
try:
    from sklearn.ensemble import RandomForestRegressor, IsolationForest
    from sklearn.linear_model import LinearRegression, Ridge, Lasso
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, r2_score
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)


# ============================================================
# DATA ANALYTICSED ENUMS
# ============================================================

class AdvancedAnalyticsType(Enum):
    """Advanced analytics types"""
    STATISTICAL = "statistical"
    MACHINE_LEARNING = "machine_learning"
    TIME_SERIES = "time_series"
    ANOMALY_DETECTION = "anomaly_detection"
    PATTERN_RECOGNITION = "pattern_recognition"
    PREDICTIVE = "predictive"


class MLModelType(Enum):
    """Machine learning model types"""
    RANDOM_FOREST = "random_forest"
    LINEAR_REGRESSION = "linear_regression"
    RIDGE = "ridge"
    LASSO = "lasso"
    ISOLATION_FOREST = "isolation_forest"


@dataclass
class AdvancedAnalyticsResult:
    """Advanced analytics result"""
    name: str
    type: AdvancedAnalyticsType
    results: Dict[str, Any]
    metrics: Dict[str, float]
    insights: List[str]
    recommendations: List[str]
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "type": self.type.value,
            "results": self.results,
            "metrics": self.metrics,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class MLModel:
    """Machine learning model"""
    id: str
    name: str
    type: MLModelType
    model: Any
    features: List[str]
    target: str
    metrics: Dict[str, float]
    created_at: datetime
    trained_at: Optional[datetime] = None
    is_trained: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "features": self.features,
            "target": self.target,
            "metrics": self.metrics,
            "created_at": self.created_at.isoformat(),
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "is_trained": self.is_trained,
        }


# ============================================================
# DATA ANALYTICSED ENGINE
# ============================================================

class DataAnalyticsedEngine:
    """
    Enhanced data analytics engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data analyticsed engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_period = self.config.get("default_period", 30)  # days
        self.random_seed = self.config.get("random_seed", 42)
        
        # State
        self.analytics_results: List[AdvancedAnalyticsResult] = []
        self.models: Dict[str, MLModel] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        
        # Set random seed
        np.random.seed(self.random_seed)
        if HAS_SKLEARN:
            import sklearn
            sklearn.set_config(random_state=self.random_seed)
        
        logger.info("Data analyticsed engine initialized")
    
    # ============================================================
    # STATISTICAL ANALYTICS
    # ============================================================
    
    def analyze_statistics(
        self,
        data: Union[List[float], np.ndarray],
        name: str = "statistical_analysis"
    ) -> AdvancedAnalyticsResult:
        """
        Perform statistical analysis
        
        Args:
            data: Input data
            name: Analysis name
            
        Returns:
            AdvancedAnalyticsResult
        """
        if isinstance(data, list):
            data = np.array(data)
        
        if len(data) < 3:
            return AdvancedAnalyticsResult(
                name=name,
                type=AdvancedAnalyticsType.STATISTICAL,
                results={},
                metrics={},
                insights=["Insufficient data for statistical analysis"],
                recommendations=["Collect more data points"],
                timestamp=datetime.now(),
            )
        
        # Calculate statistics
        stats_data = {
            "mean": np.mean(data),
            "median": np.median(data),
            "std": np.std(data),
            "var": np.var(data),
            "min": np.min(data),
            "max": np.max(data),
            "range": np.max(data) - np.min(data),
            "q1": np.percentile(data, 25),
            "q3": np.percentile(data, 75),
            "iqr": np.percentile(data, 75) - np.percentile(data, 25),
            "skewness": stats.skew(data),
            "kurtosis": stats.kurtosis(data),
            "n": len(data),
        }
        
        # Test for normality
        _, p_value = stats.normaltest(data)
        is_normal = p_value > 0.05
        
        # Generate insights
        insights = []
        if is_normal:
            insights.append("Data appears to be normally distributed")
        else:
            insights.append("Data does not appear to be normally distributed")
        
        if abs(stats_data["skewness"]) > 1:
            insights.append("Data has significant skewness")
        if abs(stats_data["kurtosis"]) > 3:
            insights.append("Data has significant kurtosis (heavy tails)")
        
        # Generate recommendations
        recommendations = []
        if stats_data["n"] < 30:
            recommendations.append("Consider collecting more data for better statistical significance")
        if not is_normal:
            recommendations.append("Consider non-parametric tests for hypothesis testing")
        
        # Calculate confidence intervals
        n = len(data)
        mean = stats_data["mean"]
        std = stats_data["std"]
        se = std / np.sqrt(n)
        ci_95 = stats.norm.interval(0.95, loc=mean, scale=se)
        ci_99 = stats.norm.interval(0.99, loc=mean, scale=se)
        
        stats_data["ci_95_lower"] = ci_95[0]
        stats_data["ci_95_upper"] = ci_95[1]
        stats_data["ci_99_lower"] = ci_99[0]
        stats_data["ci_99_upper"] = ci_99[1]
        
        result = AdvancedAnalyticsResult(
            name=name,
            type=AdvancedAnalyticsType.STATISTICAL,
            results=stats_data,
            metrics={
                "mean": mean,
                "median": stats_data["median"],
                "std": std,
                "n": n,
            },
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # TIME SERIES ANALYTICS
    # ============================================================
    
    def analyze_time_series(
        self,
        data: Union[List[float], np.ndarray],
        name: str = "time_series_analysis"
    ) -> AdvancedAnalyticsResult:
        """
        Perform time series analysis
        
        Args:
            data: Time series data
            name: Analysis name
            
        Returns:
            AdvancedAnalyticsResult
        """
        if isinstance(data, list):
            data = np.array(data)
        
        if len(data) < 10:
            return AdvancedAnalyticsResult(
                name=name,
                type=AdvancedAnalyticsType.TIME_SERIES,
                results={},
                metrics={},
                insights=["Insufficient data for time series analysis"],
                recommendations=["Collect more time series data"],
                timestamp=datetime.now(),
            )
        
        # Decompose time series
        results = {}
        
        # Trend decomposition using moving average
        window = min(5, len(data) // 2)
        if window > 0:
            trend = np.convolve(data, np.ones(window)/window, mode='valid')
            results["trend"] = trend.tolist()
        
        # Calculate autocorrelation
        if len(data) > 2:
            autocorr = [np.correlate(data[:-i], data[i:], mode='valid') for i in range(1, min(10, len(data)-1))]
            results["autocorrelation"] = [float(np.mean(c)) for c in autocorr if len(c) > 0]
        
        # Detect seasonality using FFT
        if len(data) > 20:
            fft_data = fft(data)
            freqs = fftfreq(len(data))
            magnitudes = np.abs(fft_data)
            
            # Find dominant frequencies
            peak_indices, _ = find_peaks(magnitudes[1:len(magnitudes)//2], height=0.1*np.max(magnitudes))
            if len(peak_indices) > 0:
                dominant_freqs = freqs[peak_indices + 1]
                results["dominant_frequencies"] = dominant_freqs.tolist()
                results["dominant_periods"] = (1 / dominant_freqs).tolist()
        
        # Calculate trends
        if len(data) > 5:
            x = np.arange(len(data))
            slope, intercept = np.polyfit(x, data, 1)
            results["slope"] = slope
            results["intercept"] = intercept
            results["trend_direction"] = "up" if slope > 0 else "down"
            
            # Trend strength (R-squared)
            predicted = slope * x + intercept
            ss_res = np.sum((data - predicted) ** 2)
            ss_tot = np.sum((data - np.mean(data)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            results["trend_strength"] = r_squared
        
        # Generate insights
        insights = []
        if results.get("trend_direction") == "up":
            insights.append("Time series shows upward trend")
        else:
            insights.append("Time series shows downward trend")
        
        if results.get("trend_strength", 0) > 0.7:
            insights.append("Strong trend detected")
        elif results.get("trend_strength", 0) > 0.4:
            insights.append("Moderate trend detected")
        else:
            insights.append("Weak or no clear trend")
        
        if results.get("dominant_periods"):
            insights.append(f"Seasonality detected with period {results['dominant_periods'][0]:.0f} days")
        
        # Generate recommendations
        recommendations = []
        if results.get("trend_strength", 0) < 0.3:
            recommendations.append("Consider detrending the data before analysis")
        
        result = AdvancedAnalyticsResult(
            name=name,
            type=AdvancedAnalyticsType.TIME_SERIES,
            results=results,
            metrics={
                "trend_strength": results.get("trend_strength", 0),
                "slope": results.get("slope", 0),
            },
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # ANOMALY DETECTION
    # ============================================================
    
    def detect_anomalies(
        self,
        data: Union[List[float], np.ndarray],
        method: str = "zscore",
        threshold: float = 3.0,
        name: str = "anomaly_detection"
    ) -> AdvancedAnalyticsResult:
        """
        Detect anomalies in data
        
        Args:
            data: Input data
            method: Detection method (zscore, iqr, isolation_forest)
            threshold: Anomaly threshold
            name: Analysis name
            
        Returns:
            AdvancedAnalyticsResult
        """
        if isinstance(data, list):
            data = np.array(data)
        
        if len(data) < 5:
            return AdvancedAnalyticsResult(
                name=name,
                type=AdvancedAnalyticsType.ANOMALY_DETECTION,
                results={},
                metrics={},
                insights=["Insufficient data for anomaly detection"],
                recommendations=["Collect more data"],
                timestamp=datetime.now(),
            )
        
        anomalies = []
        anomaly_scores = []
        
        if method == "zscore":
            # Z-score method
            mean = np.mean(data)
            std = np.std(data)
            if std > 0:
                z_scores = np.abs((data - mean) / std)
                anomaly_indices = np.where(z_scores > threshold)[0]
                anomalies = anomaly_indices.tolist()
                anomaly_scores = z_scores.tolist()
        
        elif method == "iqr":
            # IQR method
            q1 = np.percentile(data, 25)
            q3 = np.percentile(data, 75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            anomaly_indices = np.where((data < lower_bound) | (data > upper_bound))[0]
            anomalies = anomaly_indices.tolist()
            
            # Calculate anomaly scores
            for i, val in enumerate(data):
                if val < lower_bound:
                    anomaly_scores.append(abs((val - lower_bound) / iqr) if iqr > 0 else 0)
                elif val > upper_bound:
                    anomaly_scores.append(abs((val - upper_bound) / iqr) if iqr > 0 else 0)
                else:
                    anomaly_scores.append(0)
        
        elif method == "isolation_forest" and HAS_SKLEARN:
            # Isolation Forest
            X = data.reshape(-1, 1)
            iso_forest = IsolationForest(contamination=0.1, random_state=self.random_seed)
            predictions = iso_forest.fit_predict(X)
            anomaly_indices = np.where(predictions == -1)[0]
            anomalies = anomaly_indices.tolist()
            anomaly_scores = iso_forest.score_samples(X).tolist()
        
        else:
            # Fallback to zscore
            mean = np.mean(data)
            std = np.std(data)
            if std > 0:
                z_scores = np.abs((data - mean) / std)
                anomaly_indices = np.where(z_scores > threshold)[0]
                anomalies = anomaly_indices.tolist()
                anomaly_scores = z_scores.tolist()
        
        results = {
            "anomaly_indices": anomalies,
            "anomaly_scores": anomaly_scores,
            "anomaly_count": len(anomalies),
            "anomaly_percentage": len(anomalies) / len(data),
            "method": method,
            "threshold": threshold,
        }
        
        # Generate insights
        insights = []
        if len(anomalies) > 0:
            insights.append(f"Found {len(anomalies)} anomalies in the data")
            insights.append(f"Anomalies represent {len(anomalies)/len(data)*100:.1f}% of data")
        else:
            insights.append("No anomalies detected in the data")
        
        if len(anomalies) > len(data) * 0.1:
            insights.append("High number of anomalies - data quality may be an issue")
        
        # Generate recommendations
        recommendations = []
        if len(anomalies) > 0:
            recommendations.append("Investigate anomalies to identify root causes")
            recommendations.append("Consider removing or correcting anomalous data points")
        
        metrics = {
            "anomaly_count": len(anomalies),
            "anomaly_percentage": len(anomalies) / len(data),
        }
        
        result = AdvancedAnalyticsResult(
            name=name,
            type=AdvancedAnalyticsType.ANOMALY_DETECTION,
            results=results,
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # PATTERN RECOGNITION
    # ============================================================
    
    def detect_patterns(
        self,
        data: Union[List[float], np.ndarray],
        pattern_type: str = "price_patterns",
        name: str = "pattern_detection"
    ) -> AdvancedAnalyticsResult:
        """
        Detect patterns in data
        
        Args:
            data: Input data
            pattern_type: Type of patterns to detect
            name: Analysis name
            
        Returns:
            AdvancedAnalyticsResult
        """
        if isinstance(data, list):
            data = np.array(data)
        
        if len(data) < 20:
            return AdvancedAnalyticsResult(
                name=name,
                type=AdvancedAnalyticsType.PATTERN_RECOGNITION,
                results={},
                metrics={},
                insights=["Insufficient data for pattern detection"],
                recommendations=["Collect more data"],
                timestamp=datetime.now(),
            )
        
        patterns = []
        pattern_details = []
        
        # Detect peaks and troughs
        peaks, _ = find_peaks(data, distance=5)
        troughs, _ = find_peaks(-data, distance=5)
        
        # Detect common patterns
        if pattern_type == "price_patterns":
            # Double top detection
            if len(peaks) >= 2:
                last_two_peaks = peaks[-2:]
                peak_values = data[last_two_peaks]
                if abs(peak_values[0] - peak_values[1]) / peak_values[0] < 0.02:
                    patterns.append("double_top")
                    pattern_details.append({
                        "peak1": float(peak_values[0]),
                        "peak2": float(peak_values[1]),
                        "index1": int(last_two_peaks[0]),
                        "index2": int(last_two_peaks[1]),
                        "similarity": float(abs(peak_values[0] - peak_values[1]) / peak_values[0]),
                    })
            
            # Double bottom detection
            if len(troughs) >= 2:
                last_two_troughs = troughs[-2:]
                trough_values = data[last_two_troughs]
                if abs(trough_values[0] - trough_values[1]) / trough_values[0] < 0.02:
                    patterns.append("double_bottom")
                    pattern_details.append({
                        "bottom1": float(trough_values[0]),
                        "bottom2": float(trough_values[1]),
                        "index1": int(last_two_troughs[0]),
                        "index2": int(last_two_troughs[1]),
                        "similarity": float(abs(trough_values[0] - trough_values[1]) / trough_values[0]),
                    })
            
            # Head and shoulders detection
            if len(peaks) >= 3:
                last_three_peaks = peaks[-3:]
                peak_values = data[last_three_peaks]
                left_shoulder, head, right_shoulder = peak_values[0], peak_values[1], peak_values[2]
                if head > left_shoulder and head > right_shoulder:
                    if abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
                        patterns.append("head_and_shoulders")
                        pattern_details.append({
                            "left_shoulder": float(left_shoulder),
                            "head": float(head),
                            "right_shoulder": float(right_shoulder),
                            "index1": int(last_three_peaks[0]),
                            "index2": int(last_three_peaks[1]),
                            "index3": int(last_three_peaks[2]),
                            "pattern_type": "bearish",
                        })
        
        results = {
            "patterns_found": patterns,
            "pattern_details": pattern_details,
            "total_patterns": len(patterns),
            "peaks": peaks.tolist(),
            "troughs": troughs.tolist(),
        }
        
        # Generate insights
        insights = []
        if patterns:
            insights.append(f"Found {len(patterns)} patterns: {', '.join(patterns)}")
        else:
            insights.append("No significant patterns detected")
        
        if "double_top" in patterns:
            insights.append("Double top pattern detected - potential trend reversal (bearish)")
        if "double_bottom" in patterns:
            insights.append("Double bottom pattern detected - potential trend reversal (bullish)")
        if "head_and_shoulders" in patterns:
            insights.append("Head and shoulders pattern detected - potential trend reversal")
        
        # Generate recommendations
        recommendations = []
        if patterns:
            recommendations.append("Consider using pattern confirmation with other indicators")
            recommendations.append("Monitor for breakout/breakdown following pattern completion")
        
        metrics = {
            "total_patterns": len(patterns),
        }
        
        result = AdvancedAnalyticsResult(
            name=name,
            type=AdvancedAnalyticsType.PATTERN_RECOGNITION,
            results=results,
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
            timestamp=datetime.now(),
        )
        
        self.analytics_results.append(result)
        return result
    
    # ============================================================
    # MACHINE LEARNING PREDICTIVE
    # ============================================================
    
    def create_ml_model(
        self,
        name: str,
        model_type: MLModelType,
        features: List[str],
        target: str
    ) -> MLModel:
        """
        Create a machine learning model
        
        Args:
            name: Model name
            model_type: Model type
            features: Feature columns
            target: Target column
            
        Returns:
            MLModel
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn is required for ML models")
        
        # Create model based on type
        if model_type == MLModelType.RANDOM_FOREST:
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=self.random_seed
            )
        elif model_type == MLModelType.LINEAR_REGRESSION:
            model = LinearRegression()
        elif model_type == MLModelType.RIDGE:
            model = Ridge(alpha=1.0)
        elif model_type == MLModelType.LASSO:
            model = Lasso(alpha=0.01)
        else:
            model = RandomForestRegressor(
                n_estimators=100,
                random_state=self.random_seed
            )
        
        ml_model = MLModel(
            id=f"model_{int(time.time())}_{len(self.models)}",
            name=name,
            type=model_type,
            model=model,
            features=features,
            target=target,
            metrics={},
            created_at=datetime.now(),
            is_trained=False,
        )
        
        self.models[ml_model.id] = ml_model
        logger.info(f"Created ML model: {name} ({model_type.value})")
        return ml_model
    
    def train_ml_model(
        self,
        model_id: str,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Train a machine learning model
        
        Args:
            model_id: Model ID
            X: Features DataFrame
            y: Target Series
            test_size: Test split size
            
        Returns:
            Training results
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn is required for ML training")
        
        ml_model = self.models.get(model_id)
        if not ml_model:
            raise ValueError(f"Model not found: {model_id}")
        
        # Prepare data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_seed
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Store scaler
        self.scalers[model_id] = scaler
        
        # Train model
        ml_model.model.fit(X_train_scaled, y_train)
        ml_model.is_trained = True
        ml_model.trained_at = datetime.now()
        
        # Evaluate model
        y_pred_train = ml_model.model.predict(X_train_scaled)
        y_pred_test = ml_model.model.predict(X_test_scaled)
        
        metrics = {
            "train_r2": r2_score(y_train, y_pred_train),
            "test_r2": r2_score(y_test, y_pred_test),
            "train_rmse": np.sqrt(mean_squared_error(y_train, y_pred_train)),
            "test_rmse": np.sqrt(mean_squared_error(y_test, y_pred_test)),
        }
        
        ml_model.metrics = metrics
        
        # Generate insights
        insights = []
        if metrics["test_r2"] > 0.8:
            insights.append("Excellent model performance (R² > 0.8)")
        elif metrics["test_r2"] > 0.6:
            insights.append("Good model performance (R² > 0.6)")
        elif metrics["test_r2"] > 0.4:
            insights.append("Moderate model performance (R² > 0.4)")
        else:
            insights.append("Model may need improvement (R² < 0.4)")
        
        if abs(metrics["train_r2"] - metrics["test_r2"]) > 0.2:
            insights.append("Significant overfitting detected")
        
        return {
            "model_id": model_id,
            "metrics": metrics,
            "insights": insights,
            "train_size": len(X_train),
            "test_size": len(X_test),
        }
    
    def predict_with_ml(
        self,
        model_id: str,
        X: pd.DataFrame
    ) -> np.ndarray:
        """
        Make predictions with a trained model
        
        Args:
            model_id: Model ID
            X: Features DataFrame
            
        Returns:
            Predictions
        """
        ml_model = self.models.get(model_id)
        if not ml_model:
            raise ValueError(f"Model not found: {model_id}")
        
        if not ml_model.is_trained:
            raise ValueError(f"Model not trained: {model_id}")
        
        # Scale features
        scaler = self.scalers.get(model_id)
        if not scaler:
            raise ValueError(f"Scaler not found for model: {model_id}")
        
        X_scaled = scaler.transform(X)
        
        # Make predictions
        predictions = ml_model.model.predict(X_scaled)
        return predictions
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get analytics statistics
        
        Returns:
            Statistics dictionary
        """
        trained_models = [m for m in self.models.values() if m.is_trained]
        
        return {
            "total_analyses": len(self.analytics_results),
            "total_models": len(self.models),
            "trained_models": len(trained_models),
            "analysis_types": {
                t.value: len([r for r in self.analytics_results if r.type == t])
                for t in AdvancedAnalyticsType
            },
            "last_analysis": self.analytics_results[-1].to_dict() if self.analytics_results else None,
            "model_metrics": {
                m.id: m.metrics for m in trained_models
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AdvancedAnalyticsType",
    "MLModelType",
    
    # Dataclasses
    "AdvancedAnalyticsResult",
    "MLModel",
    
    # Classes
    "DataAnalyticsedEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

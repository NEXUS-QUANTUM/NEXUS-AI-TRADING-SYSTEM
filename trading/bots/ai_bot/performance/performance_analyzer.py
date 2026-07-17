"""
NEXUS AI TRADING SYSTEM - Performance Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced performance analysis system for trading bots, models, and system
components with real-time monitoring, historical analysis, and optimization
recommendations.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
import psutil
import yaml
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
PERFORMANCE_ANALYSIS_COUNTER = Counter(
    "nexus_performance_analyses_total",
    "Total number of performance analyses",
    ["analysis_type", "component"],
)
PERFORMANCE_ANALYSIS_DURATION = Histogram(
    "nexus_performance_analysis_duration_seconds",
    "Duration of performance analysis",
    ["analysis_type"],
)
PERFORMANCE_SCORE_GAUGE = Gauge(
    "nexus_performance_score",
    "Performance score of components",
    ["component", "metric"],
)


class PerformanceMetric(Enum):
    """Performance metrics."""

    # System metrics
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    LATENCY = "latency"
    THROUGHPUT = "throughput"

    # Trading metrics
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    AVERAGE_RETURN = "average_return"
    VOLATILITY = "volatility"

    # Model metrics
    INFERENCE_TIME = "inference_time"
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    AUC_ROC = "auc_roc"
    R2_SCORE = "r2_score"
    RMSE = "rmse"
    MAE = "mae"
    MAPE = "mape"

    # Bot metrics
    ORDER_EXECUTION_TIME = "order_execution_time"
    ORDER_FILL_RATE = "order_fill_rate"
    TRADE_SLIPPAGE = "trade_slippage"
    POSITION_TURNOVER = "position_turnover"


class AnalysisType(Enum):
    """Types of performance analysis."""

    REAL_TIME = "realtime"
    HISTORICAL = "historical"
    COMPARATIVE = "comparative"
    TREND = "trend"
    BENCHMARK = "benchmark"
    ANOMALY = "anomaly"
    PREDICTIVE = "predictive"


@dataclass
class PerformancePoint:
    """Single performance data point."""

    timestamp: datetime
    value: float
    metric: PerformanceMetric
    component: str
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "metric": self.metric.value,
            "component": self.component,
            "labels": self.labels,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformancePoint":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            value=data["value"],
            metric=PerformanceMetric(data["metric"]),
            component=data["component"],
            labels=data.get("labels", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PerformanceReport:
    """Performance analysis report."""

    id: str
    component: str
    analysis_type: AnalysisType
    time_range: Tuple[datetime, datetime]
    summary: Dict[str, Any]
    metrics: Dict[str, Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    trends: List[Dict[str, Any]]
    score: float
    grade: str
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "component": self.component,
            "analysis_type": self.analysis_type.value,
            "time_range": {
                "start": self.time_range[0].isoformat(),
                "end": self.time_range[1].isoformat(),
            },
            "summary": self.summary,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "anomalies": self.anomalies,
            "trends": self.trends,
            "score": self.score,
            "grade": self.grade,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceReport":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            component=data["component"],
            analysis_type=AnalysisType(data["analysis_type"]),
            time_range=(
                datetime.fromisoformat(data["time_range"]["start"]),
                datetime.fromisoformat(data["time_range"]["end"]),
            ),
            summary=data["summary"],
            metrics=data["metrics"],
            recommendations=data.get("recommendations", []),
            anomalies=data.get("anomalies", []),
            trends=data.get("trends", []),
            score=data["score"],
            grade=data["grade"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class PerformanceAnalyzer:
    """
    Advanced performance analysis system for trading operations.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the performance analyzer.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._performance_data: Dict[str, List[PerformancePoint]] = {}
        self._reports: Dict[str, PerformanceReport] = {}
        self._collectors: Dict[str, Callable] = {}
        self._collector_task: Optional[asyncio.Task] = None
        self._analysis_task: Optional[asyncio.Task] = None

        # Load configuration
        self.perf_config = self.config.get("performance_analyzer", {})
        self.data_retention_days = self.perf_config.get("data_retention_days", 30)
        self.collect_interval = self.perf_config.get("collect_interval", 60)
        self.analysis_interval = self.perf_config.get("analysis_interval", 300)
        self.max_data_points = self.perf_config.get("max_data_points", 10000)
        self.report_history_size = self.perf_config.get("report_history_size", 100)

        # Register default collectors
        self._register_default_collectors()

        # Start background tasks
        self._start_background_tasks()

        logger.info("PerformanceAnalyzer initialized")

    def _register_default_collectors(self):
        """Register default performance collectors."""
        self.register_collector("system", self._collect_system_performance)
        self.register_collector("trading", self._collect_trading_performance)
        self.register_collector("model", self._collect_model_performance)
        self.register_collector("bot", self._collect_bot_performance)

    def register_collector(self, name: str, collector_func: Callable):
        """
        Register a performance collector.

        Args:
            name: Collector name
            collector_func: Async function that returns performance data
        """
        self._collectors[name] = collector_func
        logger.info(f"Registered performance collector: {name}")

    def _start_background_tasks(self):
        """Start background tasks."""
        if self._collector_task is None:
            self._collector_task = asyncio.create_task(self._collector_loop())

        if self._analysis_task is None:
            self._analysis_task = asyncio.create_task(self._analysis_loop())

    async def _collector_loop(self):
        """Background loop for performance data collection."""
        while True:
            try:
                await self._collect_performance_data()
                await asyncio.sleep(self.collect_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in collector loop: {e}")
                await asyncio.sleep(5)

    async def _analysis_loop(self):
        """Background loop for performance analysis."""
        while True:
            try:
                await self._analyze_performance()
                await asyncio.sleep(self.analysis_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(10)

    async def _collect_performance_data(self):
        """Collect performance data from all collectors."""
        timestamp = datetime.utcnow()

        for name, collector in self._collectors.items():
            try:
                if asyncio.iscoroutinefunction(collector):
                    data = await collector()
                else:
                    data = collector()

                if data:
                    await self._process_performance_data(data, timestamp, source=name)

            except Exception as e:
                logger.error(f"Error in collector {name}: {e}")

    async def _process_performance_data(
        self,
        data: Dict[str, Any],
        timestamp: datetime,
        source: str = "system",
    ):
        """
        Process collected performance data.

        Args:
            data: Performance data dictionary
            timestamp: Data timestamp
            source: Data source
        """
        for metric_name, value in data.items():
            try:
                metric = PerformanceMetric(metric_name)
                point = PerformancePoint(
                    timestamp=timestamp,
                    value=value,
                    metric=metric,
                    component=source,
                )

                # Add to storage
                async with self._lock:
                    if source not in self._performance_data:
                        self._performance_data[source] = []

                    self._performance_data[source].append(point)

                    # Limit data points
                    if len(self._performance_data[source]) > self.max_data_points:
                        self._performance_data[source] = (
                            self._performance_data[source][-self.max_data_points:]
                        )

                # Update metrics
                PERFORMANCE_ANALYSIS_COUNTER.labels(
                    analysis_type="collection",
                    component=source,
                ).inc()

            except ValueError:
                # Skip unknown metrics
                continue

    async def analyze_performance(
        self,
        component: str,
        metrics: Optional[List[Union[PerformanceMetric, str]]] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        analysis_type: Union[AnalysisType, str] = AnalysisType.HISTORICAL,
    ) -> PerformanceReport:
        """
        Analyze performance of a component.

        Args:
            component: Component to analyze
            metrics: Specific metrics to analyze
            time_range: Time range for analysis
            analysis_type: Type of analysis

        Returns:
            Performance report
        """
        start_time = time.time()

        if isinstance(analysis_type, str):
            analysis_type = AnalysisType(analysis_type)

        # Get data
        data = await self._get_performance_data(component, metrics, time_range)

        if not data:
            raise ValueError(f"No performance data found for {component}")

        # Analyze based on type
        if analysis_type == AnalysisType.REAL_TIME:
            results = await self._analyze_realtime(data)
        elif analysis_type == AnalysisType.HISTORICAL:
            results = await self._analyze_historical(data)
        elif analysis_type == AnalysisType.COMPARATIVE:
            results = await self._analyze_comparative(data)
        elif analysis_type == AnalysisType.TREND:
            results = await self._analyze_trend(data)
        elif analysis_type == AnalysisType.BENCHMARK:
            results = await self._analyze_benchmark(data)
        elif analysis_type == AnalysisType.ANOMALY:
            results = await self._analyze_anomalies(data)
        elif analysis_type == AnalysisType.PREDICTIVE:
            results = await self._analyze_predictive(data)
        else:
            raise ValueError(f"Unsupported analysis type: {analysis_type}")

        # Calculate performance score
        score, grade = await self._calculate_performance_score(results)

        # Create report
        report_id = f"perf_{component}_{int(time.time())}"
        report = PerformanceReport(
            id=report_id,
            component=component,
            analysis_type=analysis_type,
            time_range=(
                data[0].timestamp if data else datetime.utcnow(),
                data[-1].timestamp if data else datetime.utcnow(),
            ),
            summary=results.get("summary", {}),
            metrics=results.get("metrics", {}),
            recommendations=results.get("recommendations", []),
            anomalies=results.get("anomalies", []),
            trends=results.get("trends", []),
            score=score,
            grade=grade,
            created_at=datetime.utcnow(),
        )

        # Store report
        async with self._lock:
            self._reports[report_id] = report

            # Limit report history
            if len(self._reports) > self.report_history_size:
                oldest = sorted(self._reports.keys())[0]
                del self._reports[oldest]

        # Update metrics
        PERFORMANCE_ANALYSIS_DURATION.labels(
            analysis_type=analysis_type.value
        ).observe(time.time() - start_time)

        PERFORMANCE_SCORE_GAUGE.labels(
            component=component,
            metric="overall_score",
        ).set(score)

        logger.info(f"Performance analysis completed for {component}: {grade} ({score:.2f})")

        return report

    async def _get_performance_data(
        self,
        component: str,
        metrics: Optional[List[Union[PerformanceMetric, str]]] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> List[PerformancePoint]:
        """
        Get performance data for analysis.

        Args:
            component: Component to analyze
            metrics: Specific metrics to include
            time_range: Time range for data

        Returns:
            List of performance points
        """
        async with self._lock:
            data = self._performance_data.get(component, [])

        if metrics:
            parsed_metrics = []
            for metric in metrics:
                if isinstance(metric, str):
                    parsed_metrics.append(PerformanceMetric(metric))
                else:
                    parsed_metrics.append(metric)

            data = [p for p in data if p.metric in parsed_metrics]

        if time_range:
            start, end = time_range
            data = [p for p in data if start <= p.timestamp <= end]

        return data

    async def _analyze_realtime(self, data: List[PerformancePoint]) -> Dict[str, Any]:
        """Analyze real-time performance."""
        if not data:
            return {}

        # Get latest values
        latest = {}
        for point in data:
            if point.metric.value not in latest or point.timestamp > latest[point.metric.value].timestamp:
                latest[point.metric.value] = point

        return {
            "summary": {
                "type": "realtime",
                "points_count": len(data),
                "time_range": {
                    "start": data[0].timestamp.isoformat(),
                    "end": data[-1].timestamp.isoformat(),
                },
            },
            "metrics": {
                "latest": {k: v.value for k, v in latest.items()},
            },
            "recommendations": [],
            "anomalies": [],
            "trends": [],
        }

    async def _analyze_historical(self, data: List[PerformancePoint]) -> Dict[str, Any]:
        """Analyze historical performance."""
        if not data:
            return {}

        # Group by metric
        metrics_data = {}
        for point in data:
            if point.metric not in metrics_data:
                metrics_data[point.metric] = []
            metrics_data[point.metric].append(point)

        # Calculate statistics
        results = {}
        for metric, points in metrics_data.items():
            values = [p.value for p in points]
            results[metric.value] = {
                "count": len(values),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "median": float(np.median(values)),
                "p95": float(np.percentile(values, 95)),
                "p99": float(np.percentile(values, 99)),
                "trend": self._calculate_trend(values),
            }

        return {
            "summary": {
                "type": "historical",
                "points_count": len(data),
                "metrics_count": len(metrics_data),
                "time_range": {
                    "start": data[0].timestamp.isoformat(),
                    "end": data[-1].timestamp.isoformat(),
                },
            },
            "metrics": results,
            "recommendations": self._generate_recommendations(results),
            "anomalies": [],
            "trends": [],
        }

    async def _analyze_comparative(self, data: List[PerformancePoint]) -> Dict[str, Any]:
        """Analyze comparative performance."""
        # Group by component and metric
        components_data = {}
        for point in data:
            if point.component not in components_data:
                components_data[point.component] = {}
            if point.metric not in components_data[point.component]:
                components_data[point.component][point.metric] = []
            components_data[point.component][point.metric].append(point)

        # Calculate statistics
        comparison = {}
        for component, metrics in components_data.items():
            comparison[component] = {}
            for metric, points in metrics.items():
                values = [p.value for p in points]
                comparison[component][metric.value] = {
                    "mean": float(np.mean(values)),
                    "median": float(np.median(values)),
                    "p95": float(np.percentile(values, 95)),
                }

        return {
            "summary": {
                "type": "comparative",
                "components": list(components_data.keys()),
                "metrics_count": len(comparison),
            },
            "metrics": comparison,
            "recommendations": [],
            "anomalies": [],
            "trends": [],
        }

    async def _analyze_trend(self, data: List[PerformancePoint]) -> Dict[str, Any]:
        """Analyze performance trends."""
        if len(data) < 3:
            return {"summary": {"trend": "insufficient_data"}}

        # Group by metric
        metrics_data = {}
        for point in data:
            if point.metric not in metrics_data:
                metrics_data[point.metric] = []
            metrics_data[point.metric].append(point)

        # Calculate trends
        trends = {}
        for metric, points in metrics_data.items():
            if len(points) < 3:
                continue

            values = [p.value for p in points]
            trend = self._calculate_trend(values)

            trends[metric.value] = {
                "direction": trend,
                "magnitude": float(np.abs(trend)),
                "values": values[-10:],  # Last 10 values
            }

        return {
            "summary": {
                "type": "trend",
                "points_count": len(data),
                "trends_count": len(trends),
            },
            "metrics": trends,
            "recommendations": self._generate_trend_recommendations(trends),
            "anomalies": [],
            "trends": list(trends.keys()),
        }

    async def _analyze_benchmark(self, data: List[PerformancePoint]) -> Dict[str, Any]:
        """Analyze performance against benchmarks."""
        # TODO: Implement benchmark analysis
        return {
            "summary": {"type": "benchmark", "status": "not_implemented"},
            "metrics": {},
            "recommendations": [],
            "anomalies": [],
            "trends": [],
        }

    async def _analyze_anomalies(self, data: List[PerformancePoint]) -> Dict[str, Any]:
        """Detect performance anomalies."""
        if len(data) < 10:
            return {"summary": {"type": "anomaly", "status": "insufficient_data"}}

        # Group by metric
        metrics_data = {}
        for point in data:
            if point.metric not in metrics_data:
                metrics_data[point.metric] = []
            metrics_data[point.metric].append(point)

        # Detect anomalies
        anomalies = []
        for metric, points in metrics_data.items():
            if len(points) < 5:
                continue

            values = [p.value for p in points]
            mean = np.mean(values)
            std = np.std(values)

            for point in points:
                z_score = (point.value - mean) / (std if std > 0 else 1)
                if abs(z_score) > 3:  # 3 sigma threshold
                    anomalies.append({
                        "metric": metric.value,
                        "timestamp": point.timestamp.isoformat(),
                        "value": point.value,
                        "z_score": float(z_score),
                        "expected_range": {
                            "min": float(mean - 3 * std),
                            "max": float(mean + 3 * std),
                        },
                    })

        return {
            "summary": {
                "type": "anomaly",
                "points_count": len(data),
                "anomalies_count": len(anomalies),
            },
            "metrics": {},
            "recommendations": [],
            "anomalies": anomalies,
            "trends": [],
        }

    async def _analyze_predictive(self, data: List[PerformancePoint]) -> Dict[str, Any]:
        """Predict future performance trends."""
        if len(data) < 20:
            return {"summary": {"type": "predictive", "status": "insufficient_data"}}

        # Group by metric
        metrics_data = {}
        for point in data:
            if point.metric not in metrics_data:
                metrics_data[point.metric] = []
            metrics_data[point.metric].append(point)

        # Simple linear regression for prediction
        predictions = {}
        for metric, points in metrics_data.items():
            if len(points) < 5:
                continue

            values = [p.value for p in points]
            x = np.arange(len(values))
            coefficients = np.polyfit(x, values, 1)
            trend_line = np.poly1d(coefficients)

            # Predict next 10 points
            next_x = np.arange(len(values), len(values) + 10)
            predicted_values = trend_line(next_x)

            predictions[metric.value] = {
                "slope": float(coefficients[0]),
                "intercept": float(coefficients[1]),
                "predictions": [float(v) for v in predicted_values],
                "confidence": 0.7,  # Fixed confidence for now
            }

        return {
            "summary": {
                "type": "predictive",
                "points_count": len(data),
                "predictions_count": len(predictions),
            },
            "metrics": predictions,
            "recommendations": self._generate_predictive_recommendations(predictions),
            "anomalies": [],
            "trends": [],
        }

    def _calculate_trend(self, values: List[float]) -> float:
        """
        Calculate trend direction and magnitude.

        Args:
            values: List of values

        Returns:
            Trend coefficient (-1 to 1)
        """
        if len(values) < 3:
            return 0.0

        x = np.arange(len(values))
        coefficients = np.polyfit(x, values, 1)
        slope = coefficients[0]

        # Normalize to -1 to 1 range
        mean = np.mean(values)
        if mean != 0:
            normalized = slope / (mean + 1e-8)
            return float(np.clip(normalized, -1, 1))

        return 0.0

    async def _calculate_performance_score(
        self,
        results: Dict[str, Any],
    ) -> Tuple[float, str]:
        """
        Calculate overall performance score.

        Args:
            results: Analysis results

        Returns:
            Score (0-100) and grade (A-F)
        """
        metrics = results.get("metrics", {})

        if not metrics:
            return 0.0, "F"

        # Calculate weighted average score
        total_weight = 0
        weighted_score = 0

        for metric_name, metric_data in metrics.items():
            if isinstance(metric_data, dict):
                # Use mean or latest value
                if "mean" in metric_data:
                    value = metric_data["mean"]
                elif "latest" in metric_data:
                    value = metric_data["latest"]
                else:
                    continue

                # Normalize value to 0-100 scale
                # This is a simplified normalization
                normalized = self._normalize_metric_value(metric_name, value)
                weight = self._get_metric_weight(metric_name)

                weighted_score += normalized * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0, "F"

        score = weighted_score / total_weight

        # Determine grade
        if score >= 90:
            grade = "A"
        elif score >= 75:
            grade = "B"
        elif score >= 60:
            grade = "C"
        elif score >= 45:
            grade = "D"
        else:
            grade = "F"

        return float(score), grade

    def _normalize_metric_value(self, metric_name: str, value: float) -> float:
        """
        Normalize a metric value to 0-100 scale.

        Args:
            metric_name: Metric name
            value: Metric value

        Returns:
            Normalized value
        """
        # Define normalization ranges for different metrics
        ranges = {
            "sharpe_ratio": (0, 3),
            "sortino_ratio": (0, 3),
            "calmar_ratio": (0, 3),
            "win_rate": (0, 100),
            "profit_factor": (0, 3),
            "accuracy": (0, 100),
            "precision": (0, 100),
            "recall": (0, 100),
            "f1_score": (0, 100),
            "r2_score": (0, 100),
            "order_fill_rate": (0, 100),
        }

        # For metrics where lower is better
        inverse_metrics = {
            "max_drawdown",
            "rmse",
            "mae",
            "mape",
            "inference_time",
            "order_execution_time",
            "trade_slippage",
        }

        if metric_name in ranges:
            min_val, max_val = ranges[metric_name]
            if max_val == min_val:
                return 50.0

            if metric_name in inverse_metrics:
                # Higher is worse
                normalized = 100 * (1 - (value - min_val) / (max_val - min_val))
            else:
                normalized = 100 * (value - min_val) / (max_val - min_val)

            return float(np.clip(normalized, 0, 100))

        # Default normalization
        if metric_name in inverse_metrics:
            return float(np.clip(100 / (value + 1), 0, 100))
        else:
            return float(np.clip(value * 10, 0, 100))

    def _get_metric_weight(self, metric_name: str) -> float:
        """
        Get weight for a metric.

        Args:
            metric_name: Metric name

        Returns:
            Weight value
        """
        weights = {
            "sharpe_ratio": 20,
            "sortino_ratio": 15,
            "win_rate": 15,
            "profit_factor": 10,
            "max_drawdown": 15,
            "accuracy": 10,
            "f1_score": 10,
            "rmse": 5,
        }
        return weights.get(metric_name, 5)

    def _generate_recommendations(
        self,
        metrics: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate performance recommendations.

        Args:
            metrics: Metrics data

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check for poor performance
        poor_metrics = []
        for metric_name, data in metrics.items():
            if "mean" in data:
                if metric_name in ["sharpe_ratio", "sortino_ratio"] and data["mean"] < 0.5:
                    poor_metrics.append((metric_name, "low", f"{data['mean']:.2f}"))
                elif metric_name == "win_rate" and data["mean"] < 40:
                    poor_metrics.append((metric_name, "low", f"{data['mean']:.1f}%"))
                elif metric_name == "max_drawdown" and data["mean"] > 20:
                    poor_metrics.append((metric_name, "high", f"{data['mean']:.1f}%"))

        for metric_name, issue, value in poor_metrics:
            recommendations.append({
                "metric": metric_name,
                "issue": f"{metric_name} is too {issue}: {value}",
                "severity": "high" if issue in ["low", "high"] else "medium",
                "suggestion": self._get_suggestion(metric_name, issue),
            })

        return recommendations

    def _get_suggestion(self, metric_name: str, issue: str) -> str:
        """Get suggestion for a metric issue."""
        suggestions = {
            "sharpe_ratio": "Consider reducing risk exposure or improving risk management",
            "sortino_ratio": "Focus on reducing downside volatility",
            "win_rate": "Review trading strategy and entry conditions",
            "max_drawdown": "Implement stricter stop-loss and position sizing",
            "accuracy": "Improve feature engineering or model architecture",
            "rmse": "Add more training data or tune hyperparameters",
        }
        return suggestions.get(metric_name, "Review and optimize performance")

    def _generate_trend_recommendations(
        self,
        trends: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on trends.

        Args:
            trends: Trend data

        Returns:
            List of recommendations
        """
        recommendations = []

        for metric_name, data in trends.items():
            direction = data.get("direction", 0)
            magnitude = data.get("magnitude", 0)

            if abs(direction) < 0.01:
                continue

            if direction > 0:
                if magnitude > 0.1:
                    recommendations.append({
                        "metric": metric_name,
                        "issue": f"Strong upward trend in {metric_name}",
                        "severity": "info",
                        "suggestion": f"Maintain current strategy for {metric_name}",
                    })
            else:
                if magnitude > 0.1:
                    recommendations.append({
                        "metric": metric_name,
                        "issue": f"Strong downward trend in {metric_name}",
                        "severity": "warning",
                        "suggestion": f"Investigate and address declining {metric_name}",
                    })

        return recommendations

    def _generate_predictive_recommendations(
        self,
        predictions: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on predictions.

        Args:
            predictions: Prediction data

        Returns:
            List of recommendations
        """
        recommendations = []

        for metric_name, data in predictions.items():
            slope = data.get("slope", 0)
            pred_values = data.get("predictions", [])

            if pred_values and slope > 0.5:
                recommendations.append({
                    "metric": metric_name,
                    "issue": f"Positive predicted trend for {metric_name}",
                    "severity": "info",
                    "suggestion": f"Expect improvement in {metric_name} in near term",
                })
            elif pred_values and slope < -0.5:
                recommendations.append({
                    "metric": metric_name,
                    "issue": f"Negative predicted trend for {metric_name}",
                    "severity": "warning",
                    "suggestion": f"Prepare for potential decline in {metric_name}",
                })

        return recommendations

    # Default Collectors

    async def _collect_system_performance(self) -> Dict[str, float]:
        """Collect system performance metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "disk_io": disk.percent,
            }
        except Exception as e:
            logger.error(f"Error collecting system performance: {e}")
            return {}

    async def _collect_trading_performance(self) -> Dict[str, float]:
        """Collect trading performance metrics."""
        # TODO: Implement trading performance collection
        return {}

    async def _collect_model_performance(self) -> Dict[str, float]:
        """Collect model performance metrics."""
        # TODO: Implement model performance collection
        return {}

    async def _collect_bot_performance(self) -> Dict[str, float]:
        """Collect bot performance metrics."""
        # TODO: Implement bot performance collection
        return {}

    async def get_reports(
        self,
        component: Optional[str] = None,
        limit: int = 10,
    ) -> List[PerformanceReport]:
        """
        Get performance reports.

        Args:
            component: Filter by component
            limit: Maximum number of reports

        Returns:
            List of performance reports
        """
        async with self._lock:
            reports = list(self._reports.values())

            if component:
                reports = [r for r in reports if r.component == component]

            reports.sort(key=lambda x: x.created_at, reverse=True)

            return reports[:limit]

    async def get_latest_report(self, component: str) -> Optional[PerformanceReport]:
        """
        Get latest performance report for a component.

        Args:
            component: Component name

        Returns:
            Latest report or None
        """
        reports = await self.get_reports(component, limit=1)
        return reports[0] if reports else None

    async def export_report(
        self,
        report_id: str,
        output_path: Union[str, Path],
        format: str = "json",
    ):
        """
        Export a performance report.

        Args:
            report_id: Report ID
            output_path: Output path
            format: Export format ("json", "yaml")
        """
        report = self._reports.get(report_id)

        if not report:
            raise ValueError(f"Report not found: {report_id}")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = report.to_dict()

        if format == "json":
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2)
        elif format == "yaml":
            with open(output_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Report exported to {output_path}")

    async def shutdown(self):
        """Shutdown the performance analyzer."""
        if self._collector_task:
            self._collector_task.cancel()
            try:
                await self._collector_task
            except asyncio.CancelledError:
                pass

        if self._analysis_task:
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass

        logger.info("PerformanceAnalyzer shut down")


# Export singleton
performance_analyzer = PerformanceAnalyzer()

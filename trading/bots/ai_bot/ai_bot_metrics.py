# trading/bots/ai_bot/ai_bot_metrics.py
# NEXUS AI TRADING SYSTEM - AI Bot Metrics & Performance Analytics
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
AI Bot Metrics & Performance Analytics for NEXUS AI Trading System.
Provides comprehensive metrics collection, analysis, and reporting including:
- Trading performance metrics (PnL, win rate, Sharpe ratio, etc.)
- Risk metrics (drawdown, VaR, volatility, etc.)
- AI model metrics (accuracy, precision, recall, F1, etc.)
- System metrics (latency, throughput, resource usage, etc.)
- Real-time metric streaming
- Historical metric storage and analysis
- Metric alerting and anomaly detection
- Custom metric definitions
- Performance benchmarking
- Dashboard integration
"""

import asyncio
import json
import logging
import math
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats

# NEXUS Imports
from trading.bots.ai_bot.config.bot_configs import BotConfig
from trading.bots.ai_bot.data.data_storage import DataStorage
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.bot.metrics")


# ============================================================================
# Enums & Constants
# ============================================================================

class MetricType(str, Enum):
    """Types of metrics."""
    TRADING = "trading"
    RISK = "risk"
    PERFORMANCE = "performance"
    AI = "ai"
    SYSTEM = "system"
    CUSTOM = "custom"


class MetricCategory(str, Enum):
    """Metric categories."""
    PNL = "pnl"
    RETURNS = "returns"
    RISK_ADJUSTED = "risk_adjusted"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    WIN_RATE = "win_rate"
    TRADE_COUNT = "trade_count"
    EXECUTION = "execution"
    MODEL_ACCURACY = "model_accuracy"
    MODEL_PRECISION = "model_precision"
    MODEL_RECALL = "model_recall"
    MODEL_F1 = "model_f1"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RESOURCE_USAGE = "resource_usage"
    CUSTOM = "custom"


class MetricAggregation(str, Enum):
    """Metric aggregation methods."""
    SUM = "sum"
    AVG = "avg"
    MAX = "max"
    MIN = "min"
    COUNT = "count"
    LAST = "last"
    FIRST = "first"
    STD = "std"
    MEDIAN = "median"
    PERCENTILE = "percentile"


@dataclass
class MetricDefinition:
    """Metric definition."""
    name: str
    metric_type: MetricType
    category: MetricCategory
    description: str
    unit: str
    aggregation: MetricAggregation
    calculation: Callable
    dependencies: List[str] = field(default_factory=list)
    is_active: bool = True
    tags: List[str] = field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    alert_threshold: Optional[float] = None
    alert_direction: str = "above"  # above, below, both


@dataclass
class MetricValue:
    """Metric value."""
    name: str
    value: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class MetricSeries:
    """Time series of metric values."""
    name: str
    values: List[MetricValue]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    interval: int = 60  # seconds


@dataclass
class MetricAlert:
    """Metric alert."""
    metric_name: str
    value: float
    threshold: float
    direction: str
    severity: str
    timestamp: datetime
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceSummary:
    """Performance summary."""
    total_pnl: float
    total_pnl_percent: float
    win_rate: float
    win_count: int
    loss_count: int
    total_trades: int
    average_win: float
    average_loss: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_percent: float
    volatility: float
    var_95: float
    var_99: float
    expected_shortfall: float
    average_trade_duration: float
    total_fees: float
    net_pnl: float
    gross_pnl: float
    timestamp: datetime


# ============================================================================
# Metrics Engine
# ============================================================================

class MetricsEngine:
    """
    Comprehensive Metrics Engine for NEXUS AI Trading Bot.
    """

    def __init__(
        self,
        config: BotConfig,
        data_storage: DataStorage,
    ):
        """
        Initialize metrics engine.

        Args:
            config: Bot configuration
            data_storage: Data storage instance
        """
        self.config = config
        self.data_storage = data_storage

        # Metric storage
        self._metrics: Dict[str, MetricValue] = {}
        self._metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._metric_definitions: Dict[str, MetricDefinition] = {}

        # Alert storage
        self._alerts: List[MetricAlert] = []
        self._alert_history: deque = deque(maxlen=1000)

        # Performance cache
        self._performance_cache: Dict[str, PerformanceSummary] = {}
        self._last_performance_update: Optional[datetime] = None

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "metric_update": [],
            "alert": [],
            "performance_update": [],
        }

        # Performance metrics
        self._performance = {
            "metrics_collected": 0,
            "alerts_triggered": 0,
            "performance_calculations": 0,
            "avg_calculation_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Register default metrics
        self._register_default_metrics()

        logger.info(
            "MetricsEngine initialized",
            extra={
                "metrics_registered": len(self._metric_definitions),
                "storage_available": data_storage is not None,
            }
        )

    # -----------------------------------------------------------------------
    # Metric Registration
    # -----------------------------------------------------------------------

    def register_metric(self, definition: MetricDefinition) -> bool:
        """
        Register a new metric.

        Args:
            definition: Metric definition

        Returns:
            True if registered successfully
        """
        if definition.name in self._metric_definitions:
            logger.warning(f"Metric {definition.name} already registered")
            return False

        self._metric_definitions[definition.name] = definition
        logger.info(f"Metric registered: {definition.name}")
        return True

    def register_metrics(self, definitions: List[MetricDefinition]) -> int:
        """
        Register multiple metrics.

        Args:
            definitions: List of metric definitions

        Returns:
            Number of metrics registered
        """
        count = 0
        for definition in definitions:
            if self.register_metric(definition):
                count += 1
        return count

    def unregister_metric(self, name: str) -> bool:
        """
        Unregister a metric.

        Args:
            name: Metric name

        Returns:
            True if unregistered successfully
        """
        if name not in self._metric_definitions:
            logger.warning(f"Metric {name} not found")
            return False

        del self._metric_definitions[name]
        self._metrics.pop(name, None)
        self._metric_history.pop(name, None)
        logger.info(f"Metric unregistered: {name}")
        return True

    # -----------------------------------------------------------------------
    # Metric Collection
    # -----------------------------------------------------------------------

    async def collect_metric(
        self,
        name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[MetricValue]:
        """
        Collect a metric value.

        Args:
            name: Metric name
            value: Metric value
            metadata: Additional metadata
            tags: Metric tags

        Returns:
            MetricValue or None
        """
        if name not in self._metric_definitions:
            logger.warning(f"Metric {name} not registered")
            return None

        definition = self._metric_definitions[name]

        if not definition.is_active:
            return None

        # Validate value
        if definition.min_value is not None and value < definition.min_value:
            logger.debug(f"Metric {name} value below minimum: {value} < {definition.min_value}")
            return None

        if definition.max_value is not None and value > definition.max_value:
            logger.debug(f"Metric {name} value above maximum: {value} > {definition.max_value}")
            return None

        # Create metric value
        metric_value = MetricValue(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
            tags=tags or [],
        )

        # Store metric
        self._metrics[name] = metric_value
        self._metric_history[name].append(metric_value)

        self._performance["metrics_collected"] += 1

        # Check for alert
        await self._check_alert(metric_value)

        # Emit event
        self._emit_event("metric_update", metric_value)

        return metric_value

    async def collect_metrics(
        self,
        metrics: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[MetricValue]:
        """
        Collect multiple metrics.

        Args:
            metrics: Dict of metric name -> value
            metadata: Additional metadata
            tags: Metric tags

        Returns:
            List of MetricValue
        """
        results = []
        for name, value in metrics.items():
            result = await self.collect_metric(name, value, metadata, tags)
            if result:
                results.append(result)
        return results

    # -----------------------------------------------------------------------
    # Metric Queries
    # -----------------------------------------------------------------------

    def get_metric(self, name: str) -> Optional[MetricValue]:
        """
        Get current metric value.

        Args:
            name: Metric name

        Returns:
            MetricValue or None
        """
        return self._metrics.get(name)

    def get_metrics(self, names: List[str]) -> Dict[str, Optional[MetricValue]]:
        """
        Get current metric values.

        Args:
            names: List of metric names

        Returns:
            Dict of metric name -> MetricValue
        """
        return {name: self.get_metric(name) for name in names}

    def get_metric_history(
        self,
        name: str,
        hours: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[MetricValue]:
        """
        Get metric history.

        Args:
            name: Metric name
            hours: Hours to look back
            limit: Maximum number of values

        Returns:
            List of MetricValue
        """
        if name not in self._metric_history:
            return []

        history = list(self._metric_history[name])

        if hours:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            history = [h for h in history if h.timestamp >= cutoff]

        if limit:
            history = history[-limit:]

        return history

    def get_metrics_by_type(self, metric_type: MetricType) -> List[MetricValue]:
        """
        Get metrics by type.

        Args:
            metric_type: Metric type

        Returns:
            List of MetricValue
        """
        return [
            self._metrics[name]
            for name, definition in self._metric_definitions.items()
            if definition.metric_type == metric_type and name in self._metrics
        ]

    def get_metrics_by_category(self, category: MetricCategory) -> List[MetricValue]:
        """
        Get metrics by category.

        Args:
            category: Metric category

        Returns:
            List of MetricValue
        """
        return [
            self._metrics[name]
            for name, definition in self._metric_definitions.items()
            if definition.category == category and name in self._metrics
        ]

    # -----------------------------------------------------------------------
    # Metric Aggregation
    # -----------------------------------------------------------------------

    def aggregate_metric(
        self,
        name: str,
        aggregation: MetricAggregation,
        hours: Optional[int] = None,
    ) -> Optional[float]:
        """
        Aggregate metric values.

        Args:
            name: Metric name
            aggregation: Aggregation method
            hours: Hours to look back

        Returns:
            Aggregated value or None
        """
        history = self.get_metric_history(name, hours)

        if not history:
            return None

        values = [m.value for m in history]

        if aggregation == MetricAggregation.SUM:
            return sum(values)
        elif aggregation == MetricAggregation.AVG:
            return np.mean(values)
        elif aggregation == MetricAggregation.MAX:
            return max(values)
        elif aggregation == MetricAggregation.MIN:
            return min(values)
        elif aggregation == MetricAggregation.COUNT:
            return len(values)
        elif aggregation == MetricAggregation.LAST:
            return values[-1]
        elif aggregation == MetricAggregation.FIRST:
            return values[0]
        elif aggregation == MetricAggregation.STD:
            return np.std(values)
        elif aggregation == MetricAggregation.MEDIAN:
            return np.median(values)
        elif aggregation == MetricAggregation.PERCENTILE:
            return np.percentile(values, 95)
        else:
            return None

    # -----------------------------------------------------------------------
    # Trading Performance Metrics
    # -----------------------------------------------------------------------

    async def calculate_performance_metrics(
        self,
        trades: List[Dict[str, Any]],
        initial_balance: Optional[float] = None,
        risk_free_rate: float = 0.02,
    ) -> PerformanceSummary:
        """
        Calculate comprehensive performance metrics.

        Args:
            trades: List of trade data
            initial_balance: Initial balance
            risk_free_rate: Risk-free rate

        Returns:
            PerformanceSummary
        """
        start_time = time.time()

        if not trades:
            return PerformanceSummary(
                total_pnl=0,
                total_pnl_percent=0,
                win_rate=0,
                win_count=0,
                loss_count=0,
                total_trades=0,
                average_win=0,
                average_loss=0,
                profit_factor=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                calmar_ratio=0,
                max_drawdown=0,
                max_drawdown_percent=0,
                volatility=0,
                var_95=0,
                var_99=0,
                expected_shortfall=0,
                average_trade_duration=0,
                total_fees=0,
                net_pnl=0,
                gross_pnl=0,
                timestamp=datetime.utcnow(),
            )

        # Extract PnL
        pnls = [t.get("pnl", 0) for t in trades]
        gross_pnl = sum(pnls)
        total_fees = sum(t.get("fees", 0) for t in trades)
        net_pnl = gross_pnl - total_fees

        # Win/loss stats
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        win_count = len(wins)
        loss_count = len(losses)
        total_trades = len(trades)

        win_rate = win_count / total_trades if total_trades > 0 else 0

        avg_win = sum(wins) / win_count if win_count > 0 else 0
        avg_loss = abs(sum(losses) / loss_count) if loss_count > 0 else 0

        profit_factor = sum(wins) / abs(sum(losses)) if loss_count > 0 else float('inf')

        # Returns calculation
        if initial_balance and initial_balance > 0:
            total_pnl_percent = (net_pnl / initial_balance) * 100
            returns = [p / initial_balance for p in pnls]
        else:
            total_pnl_percent = 0
            returns = pnls

        # Volatility
        volatility = np.std(returns) if returns else 0

        # Sharpe ratio
        if volatility > 0:
            excess_return = np.mean(returns) - risk_free_rate / 252
            sharpe_ratio = excess_return / volatility * np.sqrt(252)
        else:
            sharpe_ratio = 0

        # Sortino ratio
        downside_returns = [r for r in returns if r < 0]
        downside_deviation = np.std(downside_returns) if downside_returns else 0
        if downside_deviation > 0:
            sortino_ratio = (np.mean(returns) - risk_free_rate / 252) / downside_deviation * np.sqrt(252)
        else:
            sortino_ratio = 0

        # Drawdown
        cumulative_returns = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative_returns)
        drawdown = (peak - cumulative_returns) / (peak + 1e-10)
        max_drawdown = np.max(drawdown)
        max_drawdown_percent = max_drawdown * 100

        # Calmar ratio
        if max_drawdown > 0:
            calmar_ratio = (np.mean(returns) * 252) / max_drawdown
        else:
            calmar_ratio = 0

        # Value at Risk
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)

        # Expected Shortfall
        expected_shortfall = np.mean([r for r in returns if r <= var_95]) if returns else 0

        # Average trade duration
        durations = [
            (t.get("exit_time", datetime.utcnow()) - t.get("entry_time", datetime.utcnow())).total_seconds()
            for t in trades
            if t.get("entry_time") and t.get("exit_time")
        ]
        avg_duration = np.mean(durations) if durations else 0

        summary = PerformanceSummary(
            total_pnl=net_pnl,
            total_pnl_percent=total_pnl_percent,
            win_rate=win_rate,
            win_count=win_count,
            loss_count=loss_count,
            total_trades=total_trades,
            average_win=avg_win,
            average_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_percent=max_drawdown_percent,
            volatility=volatility,
            var_95=var_95,
            var_99=var_99,
            expected_shortfall=expected_shortfall,
            average_trade_duration=avg_duration,
            total_fees=total_fees,
            net_pnl=net_pnl,
            gross_pnl=gross_pnl,
            timestamp=datetime.utcnow(),
        )

        # Update performance
        self._performance["performance_calculations"] += 1
        elapsed_ms = (time.time() - start_time) * 1000
        self._performance["avg_calculation_time_ms"] = (
            (self._performance["avg_calculation_time_ms"] *
             (self._performance["performance_calculations"] - 1) +
             elapsed_ms) / self._performance["performance_calculations"]
        )

        self._last_performance_update = datetime.utcnow()

        # Emit event
        self._emit_event("performance_update", summary)

        return summary

    # -----------------------------------------------------------------------
    # AI Model Metrics
    # -----------------------------------------------------------------------

    async def calculate_model_metrics(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
    ) -> Dict[str, float]:
        """
        Calculate AI model performance metrics.

        Args:
            predictions: Model predictions
            targets: Target values

        Returns:
            Dict of metrics
        """
        try:
            # Ensure arrays are numpy
            pred = np.array(predictions)
            targ = np.array(targets)

            # Basic metrics
            mse = np.mean((pred - targ) ** 2)
            rmse = np.sqrt(mse)
            mae = np.mean(np.abs(pred - targ))
            mape = np.mean(np.abs((pred - targ) / (targ + 1e-10))) * 100

            # R-squared
            ss_res = np.sum((pred - targ) ** 2)
            ss_tot = np.sum((targ - np.mean(targ)) ** 2)
            r2 = 1 - (ss_res / (ss_tot + 1e-10))

            # Directional accuracy
            pred_direction = np.sign(pred)
            true_direction = np.sign(targ)
            directional_accuracy = np.mean(pred_direction == true_direction)

            # Metrics for binary classification (if applicable)
            if len(np.unique(targ)) <= 2:
                from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

                # Convert to binary
                threshold = 0
                pred_binary = (pred > threshold).astype(int)
                targ_binary = (targ > threshold).astype(int)

                accuracy = accuracy_score(targ_binary, pred_binary)
                precision = precision_score(targ_binary, pred_binary, zero_division=0)
                recall = recall_score(targ_binary, pred_binary, zero_division=0)
                f1 = f1_score(targ_binary, pred_binary, zero_division=0)
            else:
                accuracy = 0
                precision = 0
                recall = 0
                f1 = 0

            metrics = {
                "mse": mse,
                "rmse": rmse,
                "mae": mae,
                "mape": mape,
                "r2": r2,
                "directional_accuracy": directional_accuracy,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
            }

            # Collect metrics
            for name, value in metrics.items():
                await self.collect_metric(
                    f"model_{name}",
                    value,
                    metadata={"type": "model_performance"},
                )

            return metrics

        except Exception as e:
            logger.error(f"Error calculating model metrics: {e}")
            return {}

    # -----------------------------------------------------------------------
    # Alert System
    # -----------------------------------------------------------------------

    async def _check_alert(self, metric: MetricValue) -> None:
        """
        Check metric against alert thresholds.

        Args:
            metric: MetricValue
        """
        definition = self._metric_definitions.get(metric.name)

        if not definition or definition.alert_threshold is None:
            return

        threshold = definition.alert_threshold
        direction = definition.alert_direction

        triggered = False
        severity = "info"

        if direction == "above" and metric.value > threshold:
            triggered = True
            severity = "warning"
        elif direction == "below" and metric.value < threshold:
            triggered = True
            severity = "warning"
        elif direction == "both" and abs(metric.value) > threshold:
            triggered = True
            severity = "warning"

        if triggered:
            alert = MetricAlert(
                metric_name=metric.name,
                value=metric.value,
                threshold=threshold,
                direction=direction,
                severity=severity,
                timestamp=datetime.utcnow(),
                message=f"Metric {metric.name} {direction} threshold: {metric.value} > {threshold}",
                metadata=metric.metadata,
            )

            self._alerts.append(alert)
            self._alert_history.append(alert)
            self._performance["alerts_triggered"] += 1

            self._emit_event("alert", alert)

    def get_alerts(
        self,
        hours: Optional[int] = None,
        min_severity: str = "info",
    ) -> List[MetricAlert]:
        """
        Get alerts.

        Args:
            hours: Hours to look back
            min_severity: Minimum severity

        Returns:
            List of MetricAlert
        """
        alerts = self._alerts

        if hours:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            alerts = [a for a in alerts if a.timestamp >= cutoff]

        severity_order = {"critical": 3, "warning": 2, "info": 1}
        min_level = severity_order.get(min_severity, 0)

        alerts = [a for a in alerts if severity_order.get(a.severity, 0) >= min_level]

        return alerts

    # -----------------------------------------------------------------------
    # Metric Persistence
    # -----------------------------------------------------------------------

    async def save_metrics(self, hours: int = 24) -> bool:
        """
        Save metrics to storage.

        Args:
            hours: Hours of metrics to save

        Returns:
            True if saved successfully
        """
        if not self.data_storage:
            logger.warning("No data storage available")
            return False

        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            for name, history in self._metric_history.items():
                values = [h for h in history if h.timestamp >= cutoff]

                if not values:
                    continue

                data = {
                    "name": name,
                    "values": [
                        {
                            "value": v.value,
                            "timestamp": v.timestamp.isoformat(),
                            "metadata": v.metadata,
                            "tags": v.tags,
                        }
                        for v in values
                    ],
                }

                key = f"metrics:{name}:{cutoff.isoformat()}"
                await self.data_storage.save_data(key, data)

            logger.info(f"Saved metrics for {len(self._metric_history)} metrics")
            return True

        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
            return False

    async def load_metrics(self, hours: int = 24) -> bool:
        """
        Load metrics from storage.

        Args:
            hours: Hours of metrics to load

        Returns:
            True if loaded successfully
        """
        if not self.data_storage:
            logger.warning("No data storage available")
            return False

        try:
            # List all metric keys
            keys = await self.data_storage.list_keys("metrics:*")

            if not keys:
                return True

            cutoff = datetime.utcnow() - timedelta(hours=hours)

            for key in keys:
                data = await self.data_storage.load_data(key)

                if not data:
                    continue

                name = data.get("name")
                if not name:
                    continue

                for v in data.get("values", []):
                    timestamp = datetime.fromisoformat(v.get("timestamp"))
                    if timestamp < cutoff:
                        continue

                    metric_value = MetricValue(
                        name=name,
                        value=v.get("value", 0),
                        timestamp=timestamp,
                        metadata=v.get("metadata", {}),
                        tags=v.get("tags", []),
                    )

                    self._metrics[name] = metric_value
                    self._metric_history[name].append(metric_value)

            logger.info(f"Loaded metrics for {len(self._metrics)} metrics")
            return True

        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
            return False

    # -----------------------------------------------------------------------
    # Event System
    # -----------------------------------------------------------------------

    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """
        Remove an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    def _emit_event(self, event: str, data: Any) -> None:
        """
        Emit an event.

        Args:
            event: Event name
            data: Event data
        """
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

    # -----------------------------------------------------------------------
    # Default Metrics
    # -----------------------------------------------------------------------

    def _register_default_metrics(self) -> None:
        """Register default metrics."""
        # Trading metrics
        self.register_metric(MetricDefinition(
            name="total_pnl",
            metric_type=MetricType.TRADING,
            category=MetricCategory.PNL,
            description="Total profit/loss",
            unit="$",
            aggregation=MetricAggregation.SUM,
            calculation=lambda: 0,
        ))

        self.register_metric(MetricDefinition(
            name="win_rate",
            metric_type=MetricType.TRADING,
            category=MetricCategory.WIN_RATE,
            description="Win rate percentage",
            unit="%",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        self.register_metric(MetricDefinition(
            name="total_trades",
            metric_type=MetricType.TRADING,
            category=MetricCategory.TRADE_COUNT,
            description="Total number of trades",
            unit="trades",
            aggregation=MetricAggregation.COUNT,
            calculation=lambda: 0,
        ))

        # Risk metrics
        self.register_metric(MetricDefinition(
            name="max_drawdown",
            metric_type=MetricType.RISK,
            category=MetricCategory.DRAWDOWN,
            description="Maximum drawdown",
            unit="%",
            aggregation=MetricAggregation.MAX,
            calculation=lambda: 0,
            alert_threshold=10,
            alert_direction="above",
        ))

        self.register_metric(MetricDefinition(
            name="sharpe_ratio",
            metric_type=MetricType.RISK,
            category=MetricCategory.RISK_ADJUSTED,
            description="Sharpe ratio",
            unit="",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        self.register_metric(MetricDefinition(
            name="volatility",
            metric_type=MetricType.RISK,
            category=MetricCategory.VOLATILITY,
            description="Return volatility",
            unit="%",
            aggregation=MetricAggregation.STD,
            calculation=lambda: 0,
        ))

        # Performance metrics
        self.register_metric(MetricDefinition(
            name="sharpe_ratio_annual",
            metric_type=MetricType.PERFORMANCE,
            category=MetricCategory.RISK_ADJUSTED,
            description="Annualized Sharpe ratio",
            unit="",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        self.register_metric(MetricDefinition(
            name="sortino_ratio",
            metric_type=MetricType.PERFORMANCE,
            category=MetricCategory.RISK_ADJUSTED,
            description="Sortino ratio",
            unit="",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        self.register_metric(MetricDefinition(
            name="calmar_ratio",
            metric_type=MetricType.PERFORMANCE,
            category=MetricCategory.RISK_ADJUSTED,
            description="Calmar ratio",
            unit="",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        # AI model metrics
        self.register_metric(MetricDefinition(
            name="model_accuracy",
            metric_type=MetricType.AI,
            category=MetricCategory.MODEL_ACCURACY,
            description="Model accuracy",
            unit="%",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        self.register_metric(MetricDefinition(
            name="model_precision",
            metric_type=MetricType.AI,
            category=MetricCategory.MODEL_PRECISION,
            description="Model precision",
            unit="%",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        self.register_metric(MetricDefinition(
            name="model_recall",
            metric_type=MetricType.AI,
            category=MetricCategory.MODEL_RECALL,
            description="Model recall",
            unit="%",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        self.register_metric(MetricDefinition(
            name="model_f1",
            metric_type=MetricType.AI,
            category=MetricCategory.MODEL_F1,
            description="Model F1 score",
            unit="%",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        # System metrics
        self.register_metric(MetricDefinition(
            name="cpu_usage",
            metric_type=MetricType.SYSTEM,
            category=MetricCategory.RESOURCE_USAGE,
            description="CPU usage percentage",
            unit="%",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
            alert_threshold=80,
            alert_direction="above",
        ))

        self.register_metric(MetricDefinition(
            name="memory_usage",
            metric_type=MetricType.SYSTEM,
            category=MetricCategory.RESOURCE_USAGE,
            description="Memory usage percentage",
            unit="%",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
            alert_threshold=85,
            alert_direction="above",
        ))

        self.register_metric(MetricDefinition(
            name="latency_ms",
            metric_type=MetricType.SYSTEM,
            category=MetricCategory.LATENCY,
            description="API latency in milliseconds",
            unit="ms",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
            alert_threshold=500,
            alert_direction="above",
        ))

        self.register_metric(MetricDefinition(
            name="throughput_rps",
            metric_type=MetricType.SYSTEM,
            category=MetricCategory.THROUGHPUT,
            description="Requests per second",
            unit="rps",
            aggregation=MetricAggregation.AVG,
            calculation=lambda: 0,
        ))

        logger.info(f"Registered {len(self._metric_definitions)} default metrics")

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_metric_definitions(self) -> Dict[str, MetricDefinition]:
        """
        Get all metric definitions.

        Returns:
            Dict of metric name -> MetricDefinition
        """
        return self._metric_definitions

    def get_metric_statistics(self) -> Dict[str, Any]:
        """
        Get metric statistics.

        Returns:
            Metric statistics
        """
        return {
            "total_metrics": len(self._metric_definitions),
            "active_metrics": sum(1 for d in self._metric_definitions.values() if d.is_active),
            "metrics_with_history": len(self._metric_history),
            "total_alerts": len(self._alerts),
            "unresolved_alerts": sum(1 for a in self._alerts if a.severity in ["warning", "critical"]),
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "metric_count": len(self._metrics),
            "history_size": sum(len(h) for h in self._metric_history.values()),
            "alert_count": len(self._alerts),
        }

    def clear_history(self) -> None:
        """Clear metric history."""
        self._metric_history.clear()
        self._alerts.clear()
        self._alert_history.clear()
        logger.info("Metric history cleared")

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the metrics engine."""
        logger.info("MetricsEngine started")

    async def stop(self) -> None:
        """Stop the metrics engine."""
        self.clear_history()
        logger.info("MetricsEngine stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_metrics_engine(
    config: BotConfig,
    data_storage: DataStorage,
) -> MetricsEngine:
    """
    Factory function to create a MetricsEngine instance.

    Args:
        config: Bot configuration
        data_storage: Data storage instance

    Returns:
        MetricsEngine instance
    """
    return MetricsEngine(
        config=config,
        data_storage=data_storage,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the metrics engine
    pass

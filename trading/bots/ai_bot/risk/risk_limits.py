"""
NEXUS AI TRADING SYSTEM - Risk Limits
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced risk limit management system for defining, enforcing, and monitoring
trading risk limits across portfolios, strategies, and trading operations.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import yaml
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
RISK_LIMIT_COUNTER = Counter(
    "nexus_risk_limits_checked_total",
    "Total number of risk limit checks",
    ["limit_type", "status"],
)
RISK_LIMIT_VIOLATION_COUNTER = Counter(
    "nexus_risk_limit_violations_total",
    "Total number of risk limit violations",
    ["limit_type", "severity"],
)
RISK_LIMIT_GAUGE = Gauge(
    "nexus_risk_limit_usage",
    "Current risk limit usage percentage",
    ["limit_type", "portfolio"],
)
RISK_LIMIT_ACTIVE_VIOLATIONS = Gauge(
    "nexus_risk_limit_active_violations",
    "Number of active risk limit violations",
    ["portfolio"],
)


class LimitType(Enum):
    """Types of risk limits."""

    # Position limits
    MAX_POSITION_SIZE = "max_position_size"
    MAX_POSITION_VALUE = "max_position_value"
    MAX_POSITION_PERCENT = "max_position_percent"
    MIN_POSITION_SIZE = "min_position_size"

    # Portfolio limits
    MAX_PORTFOLIO_VALUE = "max_portfolio_value"
    MAX_PORTFOLIO_RISK = "max_portfolio_risk"
    MAX_PORTFOLIO_VAR = "max_portfolio_var"
    MAX_PORTFOLIO_CVAR = "max_portfolio_cvar"
    MAX_PORTFOLIO_DRAWDOWN = "max_portfolio_drawdown"

    # Leverage limits
    MAX_LEVERAGE = "max_leverage"
    MAX_NOTIONAL = "max_notional"

    # Risk metric limits
    MAX_VAR = "max_var"
    MAX_CVAR = "max_cvar"
    MAX_EXPOSURE = "max_exposure"
    MAX_CORRELATION = "max_correlation"

    # Trading limits
    MAX_DAILY_LOSS = "max_daily_loss"
    MAX_DAILY_TRADES = "max_daily_trades"
    MAX_DAILY_VOLUME = "max_daily_volume"
    MAX_WEEKLY_LOSS = "max_weekly_loss"
    MAX_MONTHLY_LOSS = "max_monthly_loss"

    # Concentration limits
    MAX_SECTOR_EXPOSURE = "max_sector_exposure"
    MAX_SYMBOL_CONCENTRATION = "max_symbol_concentration"

    # Counterparty limits
    MAX_COUNTERPARTY_EXPOSURE = "max_counterparty_exposure"
    MAX_BROKER_EXPOSURE = "max_broker_exposure"

    # Time limits
    MAX_HOLDING_PERIOD = "max_holding_period"
    MAX_TRADE_DURATION = "max_trade_duration"


class LimitSeverity(Enum):
    """Severity levels for limit violations."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class LimitAction(Enum):
    """Actions to take on limit violation."""

    NONE = "none"
    LOG_ONLY = "log_only"
    ALERT = "alert"
    REDUCE_POSITION = "reduce_position"
    HALT_TRADING = "halt_trading"
    CLOSE_POSITION = "close_position"
    LIQUIDATE = "liquidate"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class RiskLimit:
    """Risk limit definition."""

    id: str
    name: str
    limit_type: LimitType
    limit_value: float
    current_value: float = 0.0
    utilization: float = 0.0
    severity: LimitSeverity = LimitSeverity.WARNING
    action: LimitAction = LimitAction.ALERT
    enabled: bool = True
    description: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_violation_at: Optional[datetime] = None
    violation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "limit_type": self.limit_type.value,
            "limit_value": self.limit_value,
            "current_value": self.current_value,
            "utilization": self.utilization,
            "severity": self.severity.value,
            "action": self.action.value,
            "enabled": self.enabled,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_violation_at": self.last_violation_at.isoformat() if self.last_violation_at else None,
            "violation_count": self.violation_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskLimit":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            limit_type=LimitType(data["limit_type"]),
            limit_value=data["limit_value"],
            severity=LimitSeverity(data.get("severity", "warning")),
            action=LimitAction(data.get("action", "alert")),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
        )


@dataclass
class LimitViolation:
    """Risk limit violation record."""

    limit_id: str
    limit_type: LimitType
    limit_value: float
    actual_value: float
    severity: LimitSeverity
    action: LimitAction
    action_taken: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "limit_id": self.limit_id,
            "limit_type": self.limit_type.value,
            "limit_value": self.limit_value,
            "actual_value": self.actual_value,
            "severity": self.severity.value,
            "action": self.action.value,
            "action_taken": self.action_taken,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "metadata": self.metadata,
        }


class RiskLimitsManager:
    """
    Advanced risk limit management system.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        alert_manager: Optional[Any] = None,
    ):
        """
        Initialize the risk limits manager.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
            alert_manager: Alert manager instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.alert_manager = alert_manager
        self._lock = asyncio.Lock()
        self._limits: Dict[str, RiskLimit] = {}
        self._violations: List[LimitViolation] = []
        self._limit_handlers: Dict[LimitAction, Callable] = {}
        self._monitor_task: Optional[asyncio.Task] = None

        # Load configuration
        self.limits_config = self.config.get("risk_limits", {})
        self.limits_file = Path(self.limits_config.get("limits_file", "./configs/risk/limits.yaml"))
        self.max_violations_history = self.limits_config.get("max_violations_history", 1000)
        self.monitor_interval = self.limits_config.get("monitor_interval", 60)
        self.auto_reset_daily = self.limits_config.get("auto_reset_daily", True)

        # Register default handlers
        self._register_default_handlers()

        # Load limits
        self._load_limits()

        # Start monitoring
        self._start_monitoring()

        logger.info(f"RiskLimitsManager initialized with {len(self._limits)} limits")

    def _register_default_handlers(self):
        """Register default action handlers."""
        self.register_limit_handler(LimitAction.NONE, self._handle_none)
        self.register_limit_handler(LimitAction.LOG_ONLY, self._handle_log_only)
        self.register_limit_handler(LimitAction.ALERT, self._handle_alert)
        self.register_limit_handler(LimitAction.REDUCE_POSITION, self._handle_reduce_position)
        self.register_limit_handler(LimitAction.HALT_TRADING, self._handle_halt_trading)
        self.register_limit_handler(LimitAction.CLOSE_POSITION, self._handle_close_position)
        self.register_limit_handler(LimitAction.LIQUIDATE, self._handle_liquidate)
        self.register_limit_handler(LimitAction.EMERGENCY_STOP, self._handle_emergency_stop)

    def register_limit_handler(self, action: LimitAction, handler: Callable):
        """
        Register a limit action handler.

        Args:
            action: Action type
            handler: Handler function
        """
        self._limit_handlers[action] = handler
        logger.info(f"Registered handler for action: {action.value}")

    def _load_limits(self):
        """Load risk limits from configuration."""
        try:
            if self.limits_file.exists():
                with open(self.limits_file, "r") as f:
                    data = yaml.safe_load(f)
                    for limit_data in data.get("limits", []):
                        limit = RiskLimit.from_dict(limit_data)
                        self._limits[limit.id] = limit
                logger.info(f"Loaded {len(self._limits)} risk limits from {self.limits_file}")
            else:
                self._load_default_limits()
        except Exception as e:
            logger.error(f"Error loading risk limits: {e}")
            self._load_default_limits()

    def _load_default_limits(self):
        """Load default risk limits."""
        default_limits = [
            RiskLimit(
                id="max_position_size",
                name="Max Position Size",
                limit_type=LimitType.MAX_POSITION_SIZE,
                limit_value=1000.0,
                severity=LimitSeverity.WARNING,
                action=LimitAction.ALERT,
                description="Maximum position size in units",
                category="position",
            ),
            RiskLimit(
                id="max_position_value",
                name="Max Position Value",
                limit_type=LimitType.MAX_POSITION_VALUE,
                limit_value=100000.0,
                severity=LimitSeverity.ERROR,
                action=LimitAction.REDUCE_POSITION,
                description="Maximum position value in USD",
                category="position",
            ),
            RiskLimit(
                id="max_portfolio_risk",
                name="Max Portfolio Risk",
                limit_type=LimitType.MAX_PORTFOLIO_RISK,
                limit_value=0.05,
                severity=LimitSeverity.CRITICAL,
                action=LimitAction.HALT_TRADING,
                description="Maximum portfolio risk (VaR 95%)",
                category="portfolio",
            ),
            RiskLimit(
                id="max_portfolio_drawdown",
                name="Max Portfolio Drawdown",
                limit_type=LimitType.MAX_PORTFOLIO_DRAWDOWN,
                limit_value=0.15,
                severity=LimitSeverity.CRITICAL,
                action=LimitAction.CLOSE_POSITION,
                description="Maximum portfolio drawdown",
                category="portfolio",
            ),
            RiskLimit(
                id="max_leverage",
                name="Max Leverage",
                limit_type=LimitType.MAX_LEVERAGE,
                limit_value=2.0,
                severity=LimitSeverity.ERROR,
                action=LimitAction.REDUCE_POSITION,
                description="Maximum leverage ratio",
                category="leverage",
            ),
            RiskLimit(
                id="max_daily_loss",
                name="Max Daily Loss",
                limit_type=LimitType.MAX_DAILY_LOSS,
                limit_value=5000.0,
                severity=LimitSeverity.ERROR,
                action=LimitAction.HALT_TRADING,
                description="Maximum daily loss in USD",
                category="trading",
            ),
            RiskLimit(
                id="max_daily_trades",
                name="Max Daily Trades",
                limit_type=LimitType.MAX_DAILY_TRADES,
                limit_value=100,
                severity=LimitSeverity.WARNING,
                action=LimitAction.ALERT,
                description="Maximum number of trades per day",
                category="trading",
            ),
            RiskLimit(
                id="max_sector_exposure",
                name="Max Sector Exposure",
                limit_type=LimitType.MAX_SECTOR_EXPOSURE,
                limit_value=0.30,
                severity=LimitSeverity.ERROR,
                action=LimitAction.REDUCE_POSITION,
                description="Maximum exposure to any sector",
                category="concentration",
            ),
            RiskLimit(
                id="max_symbol_concentration",
                name="Max Symbol Concentration",
                limit_type=LimitType.MAX_SYMBOL_CONCENTRATION,
                limit_value=0.20,
                severity=LimitSeverity.ERROR,
                action=LimitAction.REDUCE_POSITION,
                description="Maximum concentration in any symbol",
                category="concentration",
            ),
        ]

        for limit in default_limits:
            self._limits[limit.id] = limit

        logger.info(f"Loaded {len(self._limits)} default risk limits")

    def _start_monitoring(self):
        """Start the monitoring task."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """Background loop for monitoring risk limits."""
        while True:
            try:
                # Reset daily limits if needed
                if self.auto_reset_daily:
                    await self._reset_daily_limits()

                # Monitor limits
                await self._check_all_limits()

                await asyncio.sleep(self.monitor_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def _reset_daily_limits(self):
        """Reset daily limits at midnight."""
        now = datetime.utcnow()
        if now.hour == 0 and now.minute < 5:
            # Reset daily limits
            for limit in self._limits.values():
                if limit.limit_type in [
                    LimitType.MAX_DAILY_LOSS,
                    LimitType.MAX_DAILY_TRADES,
                    LimitType.MAX_DAILY_VOLUME,
                ]:
                    limit.current_value = 0.0
                    limit.violation_count = 0
                    limit.last_violation_at = None
                    logger.debug(f"Reset daily limit: {limit.id}")

    async def _check_all_limits(self):
        """Check all risk limits."""
        for limit in self._limits.values():
            if not limit.enabled:
                continue

            try:
                # Get current value (should be set by external system)
                # This is a placeholder - actual values should be updated by the system
                current_value = limit.current_value

                if current_value > limit.limit_value:
                    await self._handle_violation(limit, current_value)

            except Exception as e:
                logger.error(f"Error checking limit {limit.id}: {e}")

    async def check_limit(
        self,
        limit_id: str,
        current_value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check a specific risk limit.

        Args:
            limit_id: Limit ID
            current_value: Current value
            metadata: Additional metadata

        Returns:
            True if limit is not violated
        """
        async with self._lock:
            limit = self._limits.get(limit_id)

            if not limit or not limit.enabled:
                return True

            # Update current value
            limit.current_value = current_value
            limit.utilization = (current_value / limit.limit_value) * 100
            limit.updated_at = datetime.utcnow()

            # Check violation
            if current_value > limit.limit_value:
                await self._handle_violation(limit, current_value, metadata)
                return False

            # Update metric
            RISK_LIMIT_GAUGE.labels(
                limit_type=limit.limit_type.value,
                portfolio="default",
            ).set(limit.utilization)

            RISK_LIMIT_COUNTER.labels(
                limit_type=limit.limit_type.value,
                status="passed",
            ).inc()

            return True

    async def _handle_violation(
        self,
        limit: RiskLimit,
        current_value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Handle a risk limit violation.

        Args:
            limit: Risk limit
            current_value: Current value
            metadata: Additional metadata
        """
        # Create violation record
        violation = LimitViolation(
            limit_id=limit.id,
            limit_type=limit.limit_type,
            limit_value=limit.limit_value,
            actual_value=current_value,
            severity=limit.severity,
            action=limit.action,
            message=f"Limit {limit.name} violated: {current_value:.2f} > {limit.limit_value:.2f}",
            metadata=metadata or {},
        )

        # Update limit
        limit.last_violation_at = datetime.utcnow()
        limit.violation_count += 1

        # Store violation
        async with self._lock:
            self._violations.append(violation)
            if len(self._violations) > self.max_violations_history:
                self._violations = self._violations[-self.max_violations_history:]

        # Update metrics
        RISK_LIMIT_VIOLATION_COUNTER.labels(
            limit_type=limit.limit_type.value,
            severity=limit.severity.value,
        ).inc()
        RISK_LIMIT_ACTIVE_VIOLATIONS.labels(portfolio="default").inc()

        # Log violation
        logger.warning(
            f"Risk limit violation: {limit.name} - "
            f"{current_value:.2f} > {limit.limit_value:.2f} "
            f"(severity: {limit.severity.value})"
        )

        # Execute action
        await self._execute_action(limit, violation)

    async def _execute_action(self, limit: RiskLimit, violation: LimitViolation):
        """
        Execute the action for a limit violation.

        Args:
            limit: Risk limit
            violation: Violation record
        """
        action = limit.action

        if action == LimitAction.NONE:
            await self._handle_none(limit, violation)
        elif action == LimitAction.LOG_ONLY:
            await self._handle_log_only(limit, violation)
        elif action == LimitAction.ALERT:
            await self._handle_alert(limit, violation)
        elif action == LimitAction.REDUCE_POSITION:
            await self._handle_reduce_position(limit, violation)
        elif action == LimitAction.HALT_TRADING:
            await self._handle_halt_trading(limit, violation)
        elif action == LimitAction.CLOSE_POSITION:
            await self._handle_close_position(limit, violation)
        elif action == LimitAction.LIQUIDATE:
            await self._handle_liquidate(limit, violation)
        elif action == LimitAction.EMERGENCY_STOP:
            await self._handle_emergency_stop(limit, violation)

        violation.action_taken = True

    # Action Handlers

    async def _handle_none(self, limit: RiskLimit, violation: LimitViolation):
        """Handle NONE action."""
        pass

    async def _handle_log_only(self, limit: RiskLimit, violation: LimitViolation):
        """Handle LOG_ONLY action."""
        logger.info(f"Limit violation logged: {limit.id}")

    async def _handle_alert(self, limit: RiskLimit, violation: LimitViolation):
        """Handle ALERT action."""
        if self.alert_manager:
            await self.alert_manager.evaluate_rules({
                "limit_id": limit.id,
                "limit_name": limit.name,
                "limit_type": limit.limit_type.value,
                "limit_value": limit.limit_value,
                "current_value": violation.actual_value,
                "severity": limit.severity.value,
                "violation_time": violation.timestamp.isoformat(),
            }, source="risk_limits")
        logger.info(f"Alert sent for limit violation: {limit.id}")

    async def _handle_reduce_position(self, limit: RiskLimit, violation: LimitViolation):
        """Handle REDUCE_POSITION action."""
        logger.warning(f"Reducing positions for limit violation: {limit.id}")

        # Calculate reduction amount
        excess = (violation.actual_value - limit.limit_value) / limit.limit_value
        reduction_percent = min(1.0, excess * 1.5)  # Reduce by 150% of excess

        # Apply reduction
        await self._apply_position_reduction(reduction_percent, limit, violation)

    async def _handle_halt_trading(self, limit: RiskLimit, violation: LimitViolation):
        """Handle HALT_TRADING action."""
        logger.critical(f"HALTING TRADING due to limit violation: {limit.id}")
        await self._apply_trading_halt(limit, violation)

    async def _handle_close_position(self, limit: RiskLimit, violation: LimitViolation):
        """Handle CLOSE_POSITION action."""
        logger.critical(f"CLOSING POSITIONS due to limit violation: {limit.id}")
        await self._apply_position_close(limit, violation)

    async def _handle_liquidate(self, limit: RiskLimit, violation: LimitViolation):
        """Handle LIQUIDATE action."""
        logger.critical(f"LIQUIDATING PORTFOLIO due to limit violation: {limit.id}")
        await self._apply_liquidation(limit, violation)

    async def _handle_emergency_stop(self, limit: RiskLimit, violation: LimitViolation):
        """Handle EMERGENCY_STOP action."""
        logger.critical(f"EMERGENCY STOP due to limit violation: {limit.id}")
        await self._apply_emergency_stop(limit, violation)

    # Action Implementations

    async def _apply_position_reduction(
        self,
        reduction_percent: float,
        limit: RiskLimit,
        violation: LimitViolation,
    ):
        """Apply position reduction."""
        # This is a placeholder - actual implementation would interact with trading system
        logger.info(
            f"Position reduction applied: {reduction_percent:.2%} "
            f"for limit {limit.id}"
        )

    async def _apply_trading_halt(self, limit: RiskLimit, violation: LimitViolation):
        """Apply trading halt."""
        # This is a placeholder - actual implementation would interact with trading system
        logger.info(f"Trading halt applied for limit {limit.id}")

    async def _apply_position_close(self, limit: RiskLimit, violation: LimitViolation):
        """Apply position close."""
        # This is a placeholder - actual implementation would interact with trading system
        logger.info(f"Positions closed for limit {limit.id}")

    async def _apply_liquidation(self, limit: RiskLimit, violation: LimitViolation):
        """Apply liquidation."""
        # This is a placeholder - actual implementation would interact with trading system
        logger.info(f"Liquidation applied for limit {limit.id}")

    async def _apply_emergency_stop(self, limit: RiskLimit, violation: LimitViolation):
        """Apply emergency stop."""
        # This is a placeholder - actual implementation would interact with trading system
        logger.info(f"Emergency stop applied for limit {limit.id}")

    async def update_limit_value(
        self,
        limit_id: str,
        value: float,
        update_current: bool = False,
    ):
        """
        Update a risk limit value.

        Args:
            limit_id: Limit ID
            value: New value
            update_current: Whether to update current value instead of limit
        """
        async with self._lock:
            limit = self._limits.get(limit_id)

            if not limit:
                return False

            if update_current:
                limit.current_value = value
            else:
                limit.limit_value = value

            limit.updated_at = datetime.utcnow()

            # Recalculate utilization
            if limit.limit_value > 0:
                limit.utilization = (limit.current_value / limit.limit_value) * 100

            logger.info(f"Updated limit {limit_id}: value={value}")
            return True

    async def add_limit(self, limit: RiskLimit) -> bool:
        """
        Add a new risk limit.

        Args:
            limit: Risk limit to add

        Returns:
            True if added
        """
        async with self._lock:
            if limit.id in self._limits:
                return False

            self._limits[limit.id] = limit
            await self._save_limits()
            logger.info(f"Added risk limit: {limit.id} - {limit.name}")
            return True

    async def update_limit(self, limit_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a risk limit.

        Args:
            limit_id: Limit ID
            updates: Updates to apply

        Returns:
            True if updated
        """
        async with self._lock:
            if limit_id not in self._limits:
                return False

            limit = self._limits[limit_id]

            for key, value in updates.items():
                if key == "limit_type":
                    value = LimitType(value)
                elif key == "severity":
                    value = LimitSeverity(value)
                elif key == "action":
                    value = LimitAction(value)
                setattr(limit, key, value)

            limit.updated_at = datetime.utcnow()
            await self._save_limits()
            logger.info(f"Updated risk limit: {limit_id}")
            return True

    async def delete_limit(self, limit_id: str) -> bool:
        """
        Delete a risk limit.

        Args:
            limit_id: Limit ID

        Returns:
            True if deleted
        """
        async with self._lock:
            if limit_id not in self._limits:
                return False

            del self._limits[limit_id]
            await self._save_limits()
            logger.info(f"Deleted risk limit: {limit_id}")
            return True

    async def _save_limits(self):
        """Save limits to file."""
        try:
            data = {
                "limits": [
                    {
                        "id": l.id,
                        "name": l.name,
                        "limit_type": l.limit_type.value,
                        "limit_value": l.limit_value,
                        "severity": l.severity.value,
                        "action": l.action.value,
                        "enabled": l.enabled,
                        "description": l.description,
                        "category": l.category,
                        "tags": l.tags,
                        "metadata": l.metadata,
                    }
                    for l in self._limits.values()
                ]
            }

            with open(self.limits_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False)

        except Exception as e:
            logger.error(f"Error saving limits: {e}")

    async def get_limit(self, limit_id: str) -> Optional[RiskLimit]:
        """
        Get a risk limit.

        Args:
            limit_id: Limit ID

        Returns:
            Risk limit or None
        """
        async with self._lock:
            return self._limits.get(limit_id)

    async def get_limits(
        self,
        limit_type: Optional[Union[LimitType, str]] = None,
        category: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[RiskLimit]:
        """
        Get risk limits.

        Args:
            limit_type: Filter by limit type
            category: Filter by category
            enabled_only: Only return enabled limits

        Returns:
            List of risk limits
        """
        async with self._lock:
            limits = list(self._limits.values())

            if limit_type:
                if isinstance(limit_type, str):
                    limit_type = LimitType(limit_type)
                limits = [l for l in limits if l.limit_type == limit_type]

            if category:
                limits = [l for l in limits if l.category == category]

            if enabled_only:
                limits = [l for l in limits if l.enabled]

            return limits

    async def get_violations(
        self,
        limit_id: Optional[str] = None,
        severity: Optional[Union[LimitSeverity, str]] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[LimitViolation]:
        """
        Get limit violations.

        Args:
            limit_id: Filter by limit ID
            severity: Filter by severity
            since: Filter since date
            limit: Maximum number of violations

        Returns:
            List of violations
        """
        async with self._lock:
            violations = self._violations

            if limit_id:
                violations = [v for v in violations if v.limit_id == limit_id]

            if severity:
                if isinstance(severity, str):
                    severity = LimitSeverity(severity)
                violations = [v for v in violations if v.severity == severity]

            if since:
                violations = [v for v in violations if v.timestamp >= since]

            violations.sort(key=lambda x: x.timestamp, reverse=True)
            return violations[:limit]

    async def get_limits_summary(self) -> Dict[str, Any]:
        """
        Get risk limits summary.

        Returns:
            Risk limits summary
        """
        async with self._lock:
            total_limits = len(self._limits)
            enabled_limits = sum(1 for l in self._limits.values() if l.enabled)
            active_violations = sum(1 for l in self._limits.values() if l.current_value > l.limit_value)

            return {
                "total_limits": total_limits,
                "enabled_limits": enabled_limits,
                "active_violations": active_violations,
                "limits_by_type": {
                    "position": sum(1 for l in self._limits.values() if l.category == "position"),
                    "portfolio": sum(1 for l in self._limits.values() if l.category == "portfolio"),
                    "trading": sum(1 for l in self._limits.values() if l.category == "trading"),
                    "leverage": sum(1 for l in self._limits.values() if l.category == "leverage"),
                    "concentration": sum(1 for l in self._limits.values() if l.category == "concentration"),
                },
                "violations_by_severity": {
                    "warning": sum(1 for v in self._violations[-100:] if v.severity == LimitSeverity.WARNING),
                    "error": sum(1 for v in self._violations[-100:] if v.severity == LimitSeverity.ERROR),
                    "critical": sum(1 for v in self._violations[-100:] if v.severity == LimitSeverity.CRITICAL),
                    "fatal": sum(1 for v in self._violations[-100:] if v.severity == LimitSeverity.FATAL),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def reset_limit(self, limit_id: str):
        """
        Reset a risk limit.

        Args:
            limit_id: Limit ID
        """
        async with self._lock:
            limit = self._limits.get(limit_id)

            if limit:
                limit.current_value = 0.0
                limit.utilization = 0.0
                limit.violation_count = 0
                limit.last_violation_at = None
                limit.updated_at = datetime.utcnow()
                logger.info(f"Reset limit: {limit_id}")

    async def reset_all_limits(self):
        """Reset all risk limits."""
        async with self._lock:
            for limit in self._limits.values():
                if limit.limit_type in [
                    LimitType.MAX_DAILY_LOSS,
                    LimitType.MAX_DAILY_TRADES,
                    LimitType.MAX_DAILY_VOLUME,
                ]:
                    limit.current_value = 0.0
                    limit.utilization = 0.0
                    limit.violation_count = 0
                    limit.last_violation_at = None
                    limit.updated_at = datetime.utcnow()

            logger.info("Reset all daily limits")

    async def shutdown(self):
        """Shutdown the risk limits manager."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("RiskLimitsManager shut down")


# Export singleton
risk_limits_manager = RiskLimitsManager()

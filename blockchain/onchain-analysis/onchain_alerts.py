# blockchain/onchain-analysis/onchain_alerts.py
# NEXUS AI TRADING SYSTEM - Advanced On-Chain Alerts Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
On-Chain Alert System for NEXUS Trading IA.
Provides real-time monitoring and alerting for on-chain events,
including whale movements, smart money activity, and protocol anomalies.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict, deque

import aiohttp
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator

# NEXUS Imports
from blockchain.onchain_analysis.base_analyzer import BaseOnChainAnalyzer
from blockchain.onchain_analysis.whale_tracker import WhaleTracker
from blockchain.onchain_analysis.smart_money import SmartMoneyAnalyzer
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.date_helpers import parse_timestamp
from shared.utilities.logger import get_logger

logger = get_logger("nexus.onchain.alerts")


# ============================================================================
# Enums & Constants
# ============================================================================

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertCategory(str, Enum):
    """Categories of on-chain alerts."""
    WHALE_MOVEMENT = "whale_movement"
    SMART_MONEY = "smart_money"
    PROTOCOL_ANOMALY = "protocol_anomaly"
    TOKEN_UNLOCK = "token_unlock"
    LARGE_TRANSACTION = "large_transaction"
    EXCHANGE_FLOW = "exchange_flow"
    GAS_ANOMALY = "gas_anomaly"
    CONTRACT_INTERACTION = "contract_interaction"
    LIQUIDATION = "liquidation"
    BRIDGE_ACTIVITY = "bridge_activity"
    STAKING_CHANGE = "staking_change"
    GOVERNANCE_VOTE = "governance_vote"
    PRICE_IMPACT = "price_impact"
    MEV_ACTIVITY = "mev_activity"


class AlertStatus(str, Enum):
    """Alert processing status."""
    PENDING = "pending"
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertChannel(str, Enum):
    """Delivery channels for alerts."""
    WEBSOCKET = "websocket"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    PUSH = "push"


# ============================================================================
# Data Models
# ============================================================================

class AlertRule(BaseModel):
    """Configuration for an on-chain alert rule."""
    rule_id: str
    name: str
    category: AlertCategory
    severity: AlertSeverity
    enabled: bool = True
    cooldown_seconds: int = 300  # 5 minutes default
    threshold: Optional[float] = None
    condition: Dict[str, Any] = Field(default_factory=dict)
    channels: List[AlertChannel] = [AlertChannel.WEBSOCKET, AlertChannel.TELEGRAM]
    message_template: str
    tags: List[str] = Field(default_factory=list)
    suppress_duplicates: bool = True
    max_trigger_count: Optional[int] = None
    time_window_seconds: Optional[int] = None

    @validator("cooldown_seconds")
    def validate_cooldown(cls, v):
        if v < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        return v


class OnChainAlert(BaseModel):
    """Complete on-chain alert data structure."""
    alert_id: str
    rule_id: str
    category: AlertCategory
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.PENDING
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    chain: str
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    token_address: Optional[str] = None
    amount: Optional[float] = None
    amount_usd: Optional[float] = None
    value: Optional[float] = None  # In native currency
    value_usd: Optional[float] = None
    message: str
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    triggered_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    delivered_to: List[AlertChannel] = Field(default_factory=list)
    retry_count: int = 0

    class Config:
        arbitrary_types_allowed = True


class AlertEvent(BaseModel):
    """Event representation for alert processing."""
    timestamp: datetime
    chain: str
    event_type: str
    data: Dict[str, Any]
    importance_score: float = 0.0


@dataclass
class AlertState:
    """Internal state tracking for alert suppression."""
    last_trigger_time: float = 0.0
    trigger_count: int = 0
    last_value: Any = None
    suppressed_until: float = 0.0


# ============================================================================
# Core Alert Engine
# ============================================================================

class OnChainAlertEngine:
    """
    Advanced on-chain alert engine with multi-condition evaluation,
    suppression logic, and multi-channel delivery.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        whale_tracker: WhaleTracker,
        smart_money_analyzer: SmartMoneyAnalyzer,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.whale_tracker = whale_tracker
        self.smart_money_analyzer = smart_money_analyzer
        self.config = config or {}

        # Core components
        self.rules: Dict[str, AlertRule] = {}
        self.alert_states: Dict[str, AlertState] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.pending_alerts: List[OnChainAlert] = []

        # Callback registry
        self._callbacks: Dict[AlertCategory, List[Callable]] = defaultdict(list)
        self._global_callbacks: List[Callable] = []

        # Async tasks
        self._tasks: Set[asyncio.Task] = set()
        self._running: bool = False
        self._lock = asyncio.Lock()

        # Performance tracking
        self._metrics: Dict[str, Any] = {
            "alerts_processed": 0,
            "alerts_triggered": 0,
            "alerts_delivered": 0,
            "alerts_suppressed": 0,
            "avg_processing_time": 0.0,
            "rule_performance": defaultdict(lambda: {"triggers": 0, "avg_ms": 0.0}),
        }

        # Pre-defined condition evaluators
        self._condition_evaluators: Dict[str, Callable] = {
            "gt": lambda val, threshold: val > threshold,
            "gte": lambda val, threshold: val >= threshold,
            "lt": lambda val, threshold: val < threshold,
            "lte": lambda val, threshold: val <= threshold,
            "eq": lambda val, threshold: val == threshold,
            "neq": lambda val, threshold: val != threshold,
            "between": lambda val, threshold: threshold[0] <= val <= threshold[1],
            "outside": lambda val, threshold: val < threshold[0] or val > threshold[1],
            "increase_pct": self._evaluate_percentage_change,
            "decrease_pct": self._evaluate_percentage_change,
            "contains": lambda val, threshold: threshold in val,
            "in": lambda val, threshold: val in threshold,
            "not_in": lambda val, threshold: val not in threshold,
        }

        # Initialize default rules if config provided
        if config:
            self._load_rules_from_config(config)

        logger.info(
            "OnChainAlertEngine initialized",
            extra={
                "chain": web3_client.chain_name,
                "rules_loaded": len(self.rules),
            }
        )

    # -----------------------------------------------------------------------
    # Rule Management
    # -----------------------------------------------------------------------

    def add_rule(self, rule: AlertRule) -> None:
        """Add or update an alert rule."""
        if rule.rule_id in self.rules:
            logger.info(f"Updating existing rule: {rule.rule_id}")
        else:
            logger.info(f"Adding new rule: {rule.rule_id}")

        self.rules[rule.rule_id] = rule
        self.alert_states[rule.rule_id] = AlertState()

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule by ID."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self.alert_states.pop(rule_id, None)
            logger.info(f"Removed rule: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a specific rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            logger.info(f"Enabled rule: {rule_id}")
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a specific rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            logger.info(f"Disabled rule: {rule_id}")
            return True
        return False

    def _load_rules_from_config(self, config: Dict[str, Any]) -> None:
        """Load alert rules from configuration."""
        rules_config = config.get("rules", [])
        for rule_data in rules_config:
            try:
                rule = AlertRule(**rule_data)
                self.add_rule(rule)
            except Exception as e:
                logger.error(f"Failed to load rule: {e}", extra={"rule_data": rule_data})

    # -----------------------------------------------------------------------
    # Condition Evaluation
    # -----------------------------------------------------------------------

    def _evaluate_percentage_change(self, current: float, threshold: float) -> bool:
        """Evaluate percentage change condition."""
        # Expected: current contains previous and current values
        if not isinstance(current, (list, tuple)) or len(current) < 2:
            return False
        prev_val, curr_val = current[0], current[1]
        if prev_val == 0:
            return False
        pct_change = ((curr_val - prev_val) / abs(prev_val)) * 100
        return abs(pct_change) >= threshold

    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Tuple[bool, Optional[float]]:
        """
        Evaluate a single condition against data.
        Returns (triggered, importance_score).
        """
        operator = condition.get("operator")
        field = condition.get("field")
        threshold = condition.get("threshold")
        importance_score = condition.get("importance_score", 0.0)

        if not operator or not field:
            return False, 0.0

        # Get value from nested data
        value = self._get_nested_value(data, field)
        if value is None:
            return False, 0.0

        # Lookup evaluator
        evaluator = self._condition_evaluators.get(operator)
        if not evaluator:
            logger.warning(f"Unknown operator: {operator}")
            return False, 0.0

        try:
            result = evaluator(value, threshold)
            return result, importance_score if result else 0.0
        except Exception as e:
            logger.debug(f"Condition evaluation error: {e}")
            return False, 0.0

    def _evaluate_rule(
        self,
        rule: AlertRule,
        event: AlertEvent
    ) -> Tuple[bool, Optional[float]]:
        """
        Evaluate all conditions for a rule.
        Returns (triggered, total_importance_score).
        """
        conditions = rule.condition.get("conditions", [])
        logic = rule.condition.get("logic", "AND")

        if not conditions:
            # Simple threshold check
            if rule.threshold is not None:
                data_value = self._get_nested_value(
                    event.data, rule.condition.get("field", "value")
                )
                if data_value is not None:
                    return data_value >= rule.threshold, data_value if data_value >= rule.threshold else 0.0
            return False, 0.0

        triggered = []
        importance_scores = []

        for condition in conditions:
            result, score = self._evaluate_condition(condition, event.data)
            triggered.append(result)
            importance_scores.append(score)

        if logic == "AND":
            all_triggered = all(triggered)
            total_score = sum(importance_scores) if all_triggered else 0.0
            return all_triggered, total_score
        elif logic == "OR":
            any_triggered = any(triggered)
            total_score = sum(importance_scores) if any_triggered else 0.0
            return any_triggered, total_score
        elif logic == "XOR":
            xor_triggered = sum(triggered) == 1
            total_score = sum(importance_scores) if xor_triggered else 0.0
            return xor_triggered, total_score

        return False, 0.0

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Optional[Any]:
        """Get nested value using dot notation path."""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    idx = int(key)
                    current = current[idx] if 0 <= idx < len(current) else None
                except ValueError:
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    # -----------------------------------------------------------------------
    # Suppression & Cooldown
    # -----------------------------------------------------------------------

    def _check_suppression(
        self,
        rule: AlertRule,
        event: AlertEvent,
        state: AlertState,
        importance_score: float
    ) -> Tuple[bool, bool]:
        """
        Check if alert should be suppressed based on cooldown, duplicates,
        and count limits. Returns (is_suppressed, should_update_state).
        """
        now = time.time()
        should_update = False

        # Check cooldown
        if rule.cooldown_seconds > 0:
            if now - state.last_trigger_time < rule.cooldown_seconds:
                return True, False

        # Check duplicate suppression
        if rule.suppress_duplicates and state.last_value is not None:
            current_value = self._get_nested_value(event.data, "value")
            if current_value is not None and current_value == state.last_value:
                return True, False

        # Check max trigger count
        if rule.max_trigger_count is not None:
            if state.trigger_count >= rule.max_trigger_count:
                return True, False

        # Check time window
        if rule.time_window_seconds is not None and rule.max_trigger_count is not None:
            # This would require more complex tracking
            pass

        return False, True

    # -----------------------------------------------------------------------
    # Alert Generation
    # -----------------------------------------------------------------------

    def _create_alert(
        self,
        rule: AlertRule,
        event: AlertEvent,
        importance_score: float
    ) -> OnChainAlert:
        """Create an alert from a triggered rule and event."""
        # Generate alert ID
        alert_id = f"onchain_{int(time.time() * 1000)}_{rule.rule_id}"

        # Determine amount/value from event data
        amount = event.data.get("amount")
        amount_usd = event.data.get("amount_usd")
        value = event.data.get("value")
        value_usd = event.data.get("value_usd")

        # Format message using template
        try:
            message = rule.message_template.format(**event.data)
        except (KeyError, ValueError):
            message = rule.message_template

        # Build alert
        return OnChainAlert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            category=rule.category,
            severity=rule.severity,
            chain=event.chain,
            transaction_hash=event.data.get("transaction_hash"),
            block_number=event.data.get("block_number"),
            from_address=event.data.get("from_address"),
            to_address=event.data.get("to_address"),
            token_address=event.data.get("token_address"),
            amount=amount,
            amount_usd=amount_usd,
            value=value,
            value_usd=value_usd,
            message=message,
            raw_data=event.data,
            metadata={
                "importance_score": importance_score,
                "event_type": event.event_type,
                "origin_timestamp": event.timestamp.isoformat(),
            },
        )

    # -----------------------------------------------------------------------
    # Event Processing
    # -----------------------------------------------------------------------

    async def process_event(self, event: AlertEvent) -> Optional[OnChainAlert]:
        """
        Process an incoming on-chain event and generate alerts.
        Returns the generated alert or None if no rule triggered.
        """
        start_time = time.time()

        if not self._running:
            logger.debug("Alert engine not running, skipping event")
            return None

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            state = self.alert_states.get(rule_id)
            if state is None:
                state = AlertState()
                self.alert_states[rule_id] = state

            # Evaluate conditions
            triggered, importance_score = self._evaluate_rule(rule, event)

            if not triggered:
                continue

            # Check suppression
            is_suppressed, should_update = self._check_suppression(
                rule, event, state, importance_score
            )

            if is_suppressed:
                self._metrics["alerts_suppressed"] += 1
                logger.debug(
                    f"Alert suppressed for rule: {rule_id}",
                    extra={"rule": rule_id, "event_type": event.event_type}
                )
                continue

            # Create and process alert
            alert = self._create_alert(rule, event, importance_score)
            alert.status = AlertStatus.TRIGGERED

            # Update state
            if should_update:
                state.last_trigger_time = time.time()
                state.trigger_count += 1
                state.last_value = self._get_nested_value(event.data, "value")

            # Store and track
            async with self._lock:
                self.alert_history.append(alert)
                self.pending_alerts.append(alert)

            self._metrics["alerts_triggered"] += 1
            self._metrics["rule_performance"][rule_id]["triggers"] += 1

            # Execute callbacks
            await self._execute_callbacks(alert)

            # Deliver alert
            await self._deliver_alert(alert)

            processing_time = (time.time() - start_time) * 1000
            self._metrics["rule_performance"][rule_id]["avg_ms"] = (
                (self._metrics["rule_performance"][rule_id]["avg_ms"] + processing_time) / 2
            )
            self._metrics["avg_processing_time"] = (
                (self._metrics["avg_processing_time"] + processing_time) / 2
            )

            logger.info(
                f"Alert triggered: {alert.alert_id}",
                extra={
                    "rule_id": rule_id,
                    "category": rule.category.value,
                    "severity": rule.severity.value,
                    "processing_ms": processing_time,
                }
            )

            return alert

        return None

    async def process_events_batch(self, events: List[AlertEvent]) -> List[OnChainAlert]:
        """Process a batch of events concurrently."""
        tasks = [self.process_event(event) for event in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        alerts = []
        for result in results:
            if isinstance(result, OnChainAlert):
                alerts.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Error processing event: {result}")

        return alerts

    # -----------------------------------------------------------------------
    # Alert Delivery
    # -----------------------------------------------------------------------

    async def _deliver_alert(self, alert: OnChainAlert) -> None:
        """Deliver alert to configured channels."""
        rule = self.rules.get(alert.rule_id)
        if not rule:
            return

        delivery_tasks = []
        for channel in rule.channels:
            if channel in alert.delivered_to:
                continue
            delivery_tasks.append(self._deliver_to_channel(alert, channel))

        if delivery_tasks:
            results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
            delivered_channels = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Failed to deliver alert to channel: {rule.channels[i]}",
                        extra={"error": str(result), "alert_id": alert.alert_id}
                    )
                    alert.retry_count += 1
                else:
                    delivered_channels.append(rule.channels[i])

            alert.delivered_to.extend(delivered_channels)
            self._metrics["alerts_delivered"] += len(delivered_channels)

    async def _deliver_to_channel(self, alert: OnChainAlert, channel: AlertChannel) -> bool:
        """Deliver alert to a specific channel."""
        # In production, this would integrate with actual delivery systems
        # For now, we'll simulate delivery

        if channel == AlertChannel.WEBSOCKET:
            # Broadcast via WebSocket service
            pass
        elif channel == AlertChannel.TELEGRAM:
            # Send via Telegram bot
            pass
        elif channel == AlertChannel.DISCORD:
            # Send via Discord webhook
            pass
        elif channel == AlertChannel.SLACK:
            # Send via Slack webhook
            pass
        elif channel == AlertChannel.EMAIL:
            # Send via email service
            pass
        elif channel == AlertChannel.SMS:
            # Send via SMS service
            pass
        elif channel == AlertChannel.WEBHOOK:
            # Send to configured webhook
            pass

        # Log for now
        logger.debug(f"Alert delivered to {channel.value}: {alert.alert_id}")
        return True

    # -----------------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------------

    def register_callback(
        self,
        category: Optional[AlertCategory],
        callback: Callable[[OnChainAlert], Any],
        global_callback: bool = False,
    ) -> None:
        """Register a callback for alert processing."""
        if global_callback:
            self._global_callbacks.append(callback)
        elif category:
            self._callbacks[category].append(callback)
        else:
            raise ValueError("Must specify either category or global_callback=True")

    def unregister_callback(self, callback: Callable) -> bool:
        """Unregister a callback."""
        for category, callbacks in self._callbacks.items():
            if callback in callbacks:
                callbacks.remove(callback)
                return True
        if callback in self._global_callbacks:
            self._global_callbacks.remove(callback)
            return True
        return False

    async def _execute_callbacks(self, alert: OnChainAlert) -> None:
        """Execute registered callbacks for an alert."""
        tasks = []

        # Category-specific callbacks
        for callback in self._callbacks.get(alert.category, []):
            tasks.append(asyncio.create_task(self._safe_callback(callback, alert)))

        # Global callbacks
        for callback in self._global_callbacks:
            tasks.append(asyncio.create_task(self._safe_callback(callback, alert)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_callback(self, callback: Callable, alert: OnChainAlert) -> None:
        """Execute a callback safely, catching exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(alert)
            else:
                callback(alert)
        except Exception as e:
            logger.error(f"Error in callback: {e}", exc_info=True)

    # -----------------------------------------------------------------------
    # Alert Management
    # -----------------------------------------------------------------------

    async def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alert_history:
            if alert.alert_id == alert_id and alert.status in [AlertStatus.TRIGGERED, AlertStatus.PENDING]:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.utcnow()
                alert.metadata["acknowledged_by"] = user
                logger.info(f"Alert acknowledged: {alert_id}", extra={"by": user})
                return True
        return False

    async def resolve_alert(self, alert_id: str, resolution: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self.alert_history:
            if alert.alert_id == alert_id and alert.status in [AlertStatus.TRIGGERED, AlertStatus.ACKNOWLEDGED]:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()
                alert.metadata["resolution"] = resolution
                logger.info(f"Alert resolved: {alert_id}")
                return True
        return False

    async def get_active_alerts(self) -> List[OnChainAlert]:
        """Get all active (non-resolved) alerts."""
        return [
            alert for alert in self.alert_history
            if alert.status in [AlertStatus.PENDING, AlertStatus.TRIGGERED, AlertStatus.ACKNOWLEDGED]
        ]

    async def get_alerts_by_severity(self, severity: AlertSeverity) -> List[OnChainAlert]:
        """Get alerts by severity level."""
        return [alert for alert in self.alert_history if alert.severity == severity]

    async def get_alerts_by_category(self, category: AlertCategory) -> List[OnChainAlert]:
        """Get alerts by category."""
        return [alert for alert in self.alert_history if alert.category == category]

    # -----------------------------------------------------------------------
    # Engine Lifecycle
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the alert engine."""
        if self._running:
            logger.warning("Alert engine already running")
            return

        self._running = True
        logger.info("OnChainAlertEngine started")

        # Start background tasks
        self._tasks.add(asyncio.create_task(self._process_pending_alerts_loop()))
        self._tasks.add(asyncio.create_task(self._monitor_metrics_loop()))

    async def stop(self, graceful: bool = True) -> None:
        """Stop the alert engine."""
        self._running = False

        if graceful:
            # Wait for pending tasks
            await asyncio.sleep(2)

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        logger.info("OnChainAlertEngine stopped")

    async def _process_pending_alerts_loop(self) -> None:
        """Background task for processing pending alerts."""
        while self._running:
            try:
                # Process any pending alerts that need retry
                retry_alerts = [
                    alert for alert in self.pending_alerts
                    if alert.status == AlertStatus.TRIGGERED and alert.retry_count > 0
                ]

                for alert in retry_alerts:
                    if alert.retry_count < 3:  # Max retries
                        await self._deliver_alert(alert)
                        alert.retry_count += 1

                # Clean up old pending alerts
                current_time = datetime.utcnow()
                self.pending_alerts = [
                    alert for alert in self.pending_alerts
                    if (current_time - alert.timestamp).total_seconds() < 3600
                ]

            except Exception as e:
                logger.error(f"Error in pending alerts loop: {e}", exc_info=True)

            await asyncio.sleep(5)

    async def _monitor_metrics_loop(self) -> None:
        """Background task for monitoring and reporting metrics."""
        while self._running:
            try:
                # Log metrics periodically
                logger.debug(
                    "Alert engine metrics",
                    extra={
                        "total_alerts": len(self.alert_history),
                        "pending": len(self.pending_alerts),
                        "triggered": self._metrics["alerts_triggered"],
                        "suppressed": self._metrics["alerts_suppressed"],
                        "avg_processing_ms": self._metrics["avg_processing_time"],
                    }
                )

                # Update Prometheus metrics (if available)
                # self._update_prometheus_metrics()

            except Exception as e:
                logger.error(f"Error in metrics loop: {e}", exc_info=True)

            await asyncio.sleep(60)  # Every minute

    # -----------------------------------------------------------------------
    # Alert Events from Various Sources
    # -----------------------------------------------------------------------

    async def on_new_transaction(self, tx_data: Dict[str, Any]) -> None:
        """Process a new transaction."""
        event = AlertEvent(
            timestamp=datetime.utcnow(),
            chain=self.web3_client.chain_name,
            event_type="transaction",
            data=tx_data,
            importance_score=self._calculate_transaction_importance(tx_data),
        )
        await self.process_event(event)

    async def on_new_block(self, block_data: Dict[str, Any]) -> None:
        """Process a new block."""
        event = AlertEvent(
            timestamp=datetime.utcnow(),
            chain=self.web3_client.chain_name,
            event_type="block",
            data=block_data,
        )
        await self.process_event(event)

    async def on_whale_movement(self, whale_data: Dict[str, Any]) -> None:
        """Process whale movement detection."""
        event = AlertEvent(
            timestamp=datetime.utcnow(),
            chain=self.web3_client.chain_name,
            event_type="whale_movement",
            data=whale_data,
            importance_score=self._calculate_whale_importance(whale_data),
        )
        await self.process_event(event)

    async def on_smart_money_activity(self, smart_money_data: Dict[str, Any]) -> None:
        """Process smart money activity."""
        event = AlertEvent(
            timestamp=datetime.utcnow(),
            chain=self.web3_client.chain_name,
            event_type="smart_money",
            data=smart_money_data,
            importance_score=smart_money_data.get("confidence_score", 0.5),
        )
        await self.process_event(event)

    async def on_protocol_event(self, protocol_data: Dict[str, Any]) -> None:
        """Process protocol-specific event."""
        event = AlertEvent(
            timestamp=datetime.utcnow(),
            chain=self.web3_client.chain_name,
            event_type=protocol_data.get("event_type", "protocol_event"),
            data=protocol_data,
            importance_score=protocol_data.get("importance", 0.5),
        )
        await self.process_event(event)

    # -----------------------------------------------------------------------
    # Importance Scoring
    # -----------------------------------------------------------------------

    def _calculate_transaction_importance(self, tx_data: Dict[str, Any]) -> float:
        """Calculate importance score for a transaction."""
        score = 0.0
        value = tx_data.get("value", 0)
        gas_price = tx_data.get("gas_price", 0)
        gas_used = tx_data.get("gas_used", 0)

        # Value-based importance
        if value > 0:
            if value > 1_000_000_000_000_000_000:  # > 1 ETH
                score += 0.5
            elif value > 100_000_000_000_000_000:  # > 0.1 ETH
                score += 0.3
            elif value > 10_000_000_000_000_000:  # > 0.01 ETH
                score += 0.1

        # Gas-based importance (more gas = more complex contract interaction)
        if gas_used > 0:
            gas_spent = gas_price * gas_used
            if gas_spent > 10_000_000_000_000_000:  # > 0.01 ETH in gas
                score += 0.3
            elif gas_spent > 1_000_000_000_000_000:
                score += 0.1

        # Contract interaction importance
        if tx_data.get("to") and tx_data.get("to") != tx_data.get("from"):
            score += 0.2

        return min(score, 1.0)

    def _calculate_whale_importance(self, whale_data: Dict[str, Any]) -> float:
        """Calculate importance score for whale movement."""
        score = 0.0

        amount_usd = whale_data.get("amount_usd", 0)
        percentage = whale_data.get("percentage_of_supply", 0)

        # Amount-based importance
        if amount_usd > 10_000_000:  # > $10M
            score += 0.5
        elif amount_usd > 1_000_000:
            score += 0.3
        elif amount_usd > 100_000:
            score += 0.1

        # Percentage-based importance
        if percentage > 5:  # > 5% of supply
            score += 0.5
        elif percentage > 1:
            score += 0.3

        # Direction importance (incoming to exchange is often more important)
        if whale_data.get("direction") == "incoming_exchange":
            score += 0.3
        elif whale_data.get("direction") == "outgoing_exchange":
            score += 0.2

        return min(score, 1.0)

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics."""
        return {
            **self._metrics,
            "total_alerts": len(self.alert_history),
            "pending_alerts": len(self.pending_alerts),
            "rules_enabled": sum(1 for r in self.rules.values() if r.enabled),
            "rules_total": len(self.rules),
        }

    def get_rule_status(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a specific rule."""
        rule = self.rules.get(rule_id)
        if not rule:
            return None

        state = self.alert_states.get(rule_id)
        return {
            "rule_id": rule_id,
            "enabled": rule.enabled,
            "severity": rule.severity.value,
            "category": rule.category.value,
            "last_trigger": state.last_trigger_time if state else 0,
            "trigger_count": state.trigger_count if state else 0,
            "performance": self._metrics["rule_performance"].get(rule_id, {}),
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_onchain_alert_engine(
    web3_client: Web3Client,
    whale_tracker: WhaleTracker,
    smart_money_analyzer: SmartMoneyAnalyzer,
    config_file: Optional[str] = None,
) -> OnChainAlertEngine:
    """Factory function to create an OnChainAlertEngine instance."""
    config = {}
    if config_file:
        try:
            with open(config_file, 'r') as f:
                import yaml
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
    return OnChainAlertEngine(
        web3_client=web3_client,
        whale_tracker=whale_tracker,
        smart_money_analyzer=smart_money_analyzer,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the alert engine
    pass

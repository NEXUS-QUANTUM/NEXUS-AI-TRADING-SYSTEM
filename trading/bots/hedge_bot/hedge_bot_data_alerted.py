# trading/bots/hedge_bot/hedge_bot_data_alerted.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Alerted Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Alerted Module

This module provides comprehensive data-driven alerting capabilities for the
NEXUS Hedge Bot system. It monitors data streams, detects anomalies, and
generates alerts based on configurable conditions.

The module covers:
- Data Condition Monitoring
- Anomaly Detection
- Threshold Alerts
- Trend Alerts
- Pattern Alerts
- Real-time Alerts
- Alert Routing
- Alert Escalation
- Alert Aggregation
- Alert Suppression
"""

import os
import sys
import json
import logging
import time
import threading
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


# ============================================================
# DATA ALERTED ENUMS
# ============================================================

class AlertCondition(Enum):
    """Alert conditions"""
    THRESHOLD = "threshold"
    TREND = "trend"
    ANOMALY = "anomaly"
    PATTERN = "pattern"
    CHANGE = "change"
    CUSTOM = "custom"


class AlertSeverity(Enum):
    """Alert severity"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"


@dataclass
class AlertRule:
    """Alert rule"""
    id: str
    name: str
    condition: AlertCondition
    field: str
    threshold: float
    severity: AlertSeverity
    description: str
    enabled: bool = True
    cooldown: int = 60  # seconds
    aggregation: Optional[str] = None
    window: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "condition": self.condition.value,
            "field": self.field,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "description": self.description,
            "enabled": self.enabled,
            "cooldown": self.cooldown,
            "aggregation": self.aggregation,
            "window": self.window,
        }


@dataclass
class DataAlert:
    """Data alert"""
    id: str
    rule_id: str
    field: str
    value: float
    threshold: float
    severity: AlertSeverity
    status: AlertStatus
    message: str
    data: Dict[str, Any]
    timestamp: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "field": self.field,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None,
        }


# ============================================================
# DATA ALERTED ENGINE
# ============================================================

class DataAlertedEngine:
    """
    Comprehensive data alerting engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data alerting engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_severity = self.config.get("default_severity", AlertSeverity.WARNING)
        self.max_alerts = self.config.get("max_alerts", 1000)
        self.alert_history_days = self.config.get("alert_history_days", 30)
        
        # State
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: List[DataAlert] = []
        self.active_alerts: Dict[str, DataAlert] = {}
        self.alert_history: deque = deque(maxlen=self.max_alerts)
        
        # Handlers
        self.alert_handlers: List[Callable] = []
        self.escalation_handlers: List[Callable] = []
        
        # Alert counters
        self.alert_counters: Dict[str, int] = {}
        
        # Register default rules
        self._register_default_rules()
        
        logger.info("Data alerting engine initialized")
    
    # ============================================================
    # DEFAULT RULES
    # ============================================================
    
    def _register_default_rules(self) -> None:
        """Register default alert rules"""
        default_rules = [
            AlertRule(
                id="alert_price_spike",
                name="Price Spike Alert",
                condition=AlertCondition.THRESHOLD,
                field="price",
                threshold=0.05,
                severity=AlertSeverity.WARNING,
                description="Alert when price changes more than 5%",
            ),
            AlertRule(
                id="alert_volume_spike",
                name="Volume Spike Alert",
                condition=AlertCondition.THRESHOLD,
                field="volume",
                threshold=2.0,
                severity=AlertSeverity.INFO,
                description="Alert when volume doubles",
            ),
            AlertRule(
                id="alert_drawdown",
                name="Drawdown Alert",
                condition=AlertCondition.THRESHOLD,
                field="drawdown",
                threshold=0.10,
                severity=AlertSeverity.CRITICAL,
                description="Alert when drawdown exceeds 10%",
            ),
            AlertRule(
                id="alert_var_breach",
                name="VaR Breach Alert",
                condition=AlertCondition.THRESHOLD,
                field="var_95",
                threshold=0.05,
                severity=AlertSeverity.CRITICAL,
                description="Alert when VaR is breached",
            ),
        ]
        
        for rule in default_rules:
            self.rules[rule.id] = rule
        
        logger.info(f"Registered {len(default_rules)} default alert rules")
    
    # ============================================================
    # RULE MANAGEMENT
    # ============================================================
    
    def create_rule(
        self,
        name: str,
        condition: AlertCondition,
        field: str,
        threshold: float,
        severity: Optional[AlertSeverity] = None,
        description: str = "",
        cooldown: int = 60,
        enabled: bool = True
    ) -> AlertRule:
        """
        Create an alert rule
        
        Args:
            name: Rule name
            condition: Alert condition
            field: Data field
            threshold: Threshold value
            severity: Alert severity
            description: Rule description
            cooldown: Cooldown period in seconds
            enabled: Rule enabled
            
        Returns:
            AlertRule
        """
        if severity is None:
            severity = self.default_severity
        
        rule = AlertRule(
            id=f"rule_{int(time.time())}_{len(self.rules)}",
            name=name,
            condition=condition,
            field=field,
            threshold=threshold,
            severity=severity,
            description=description or f"{name} alert",
            enabled=enabled,
            cooldown=cooldown,
        )
        
        self.rules[rule.id] = rule
        logger.info(f"Created alert rule: {name}")
        return rule
    
    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> Optional[AlertRule]:
        """
        Update an alert rule
        
        Args:
            rule_id: Rule ID
            updates: Updates to apply
            
        Returns:
            Updated rule or None
        """
        rule = self.rules.get(rule_id)
        if not rule:
            return None
        
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        logger.info(f"Updated alert rule: {rule.name}")
        return rule
    
    def delete_rule(self, rule_id: str) -> bool:
        """
        Delete an alert rule
        
        Args:
            rule_id: Rule ID
            
        Returns:
            True if deleted
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Deleted alert rule: {rule_id}")
            return True
        return False
    
    def get_rules(self) -> List[AlertRule]:
        """
        Get all alert rules
        
        Returns:
            List of rules
        """
        return list(self.rules.values())
    
    # ============================================================
    # ALERT EVALUATION
    # ============================================================
    
    def evaluate_data(self, data: Dict[str, Any]) -> List[DataAlert]:
        """
        Evaluate data against all rules
        
        Args:
            data: Data to evaluate
            
        Returns:
            List of alerts generated
        """
        alerts = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            # Check if field exists
            if rule.field not in data:
                continue
            
            value = data[rule.field]
            
            # Evaluate condition
            condition_met = self._evaluate_condition(rule, value, data)
            
            if condition_met:
                alert = self._create_alert(rule, value, data)
                alerts.append(alert)
                self._process_alert(alert)
        
        return alerts
    
    def _evaluate_condition(
        self,
        rule: AlertRule,
        value: Any,
        data: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a condition
        
        Args:
            rule: Alert rule
            value: Field value
            data: Full data
            
        Returns:
            True if condition met
        """
        if rule.condition == AlertCondition.THRESHOLD:
            # Simple threshold check
            return abs(value) > rule.threshold
        
        elif rule.condition == AlertCondition.TREND:
            # Check if value is trending in a direction
            if "history" in data and isinstance(data["history"], list):
                if len(data["history"]) > 1:
                    trend = data["history"][-1] - data["history"][-2]
                    return abs(trend) > rule.threshold
            return False
        
        elif rule.condition == AlertCondition.ANOMALY:
            # Check if value is an anomaly
            if "history" in data and isinstance(data["history"], list):
                if len(data["history"]) > 3:
                    mean = np.mean(data["history"])
                    std = np.std(data["history"])
                    if std > 0:
                        zscore = (value - mean) / std
                        return abs(zscore) > rule.threshold
            return False
        
        elif rule.condition == AlertCondition.PATTERN:
            # Check for specific patterns
            if "history" in data and isinstance(data["history"], list):
                if len(data["history"]) >= 5:
                    # Simple pattern detection
                    last_values = data["history"][-5:]
                    if rule.threshold > 0:
                        # Uptrend pattern
                        return all(last_values[i] < last_values[i+1] for i in range(len(last_values)-1))
                    else:
                        # Downtrend pattern
                        return all(last_values[i] > last_values[i+1] for i in range(len(last_values)-1))
            return False
        
        elif rule.condition == AlertCondition.CHANGE:
            # Check percentage change
            if "previous_value" in data:
                prev = data["previous_value"]
                if prev != 0:
                    change = abs((value - prev) / prev)
                    return change > rule.threshold
            return False
        
        elif rule.condition == AlertCondition.CUSTOM:
            # Custom condition evaluation
            if "custom_evaluator" in data:
                evaluator = data["custom_evaluator"]
                if callable(evaluator):
                    return evaluator(rule, value, data)
            return False
        
        return False
    
    def _create_alert(
        self,
        rule: AlertRule,
        value: Any,
        data: Dict[str, Any]
    ) -> DataAlert:
        """
        Create an alert
        
        Args:
            rule: Alert rule
            value: Field value
            data: Full data
            
        Returns:
            DataAlert
        """
        alert_id = f"alert_{int(time.time())}_{len(self.alerts)}"
        
        alert = DataAlert(
            id=alert_id,
            rule_id=rule.id,
            field=rule.field,
            value=value,
            threshold=rule.threshold,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=f"{rule.name}: {rule.field}={value:.4f} (threshold: {rule.threshold})",
            data=data,
            timestamp=datetime.now(),
        )
        
        return alert
    
    def _process_alert(self, alert: DataAlert) -> None:
        """
        Process an alert
        
        Args:
            alert: DataAlert
        """
        # Check cooldown
        if alert.rule_id in self.alert_counters:
            last_time = self.alert_counters.get(f"{alert.rule_id}_last")
            if last_time:
                cooldown = self.rules.get(alert.rule_id, AlertRule(
                    id="", name="", condition=AlertCondition.THRESHOLD,
                    field="", threshold=0, severity=AlertSeverity.INFO,
                    description="", cooldown=60
                )).cooldown
                if (datetime.now() - last_time).total_seconds() < cooldown:
                    return
        
        # Add to alerts
        self.alerts.append(alert)
        self.active_alerts[alert.id] = alert
        self.alert_history.append(alert)
        
        # Update counter
        self.alert_counters[alert.rule_id] = self.alert_counters.get(alert.rule_id, 0) + 1
        self.alert_counters[f"{alert.rule_id}_last"] = datetime.now()
        
        # Notify handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
        
        # Check escalation
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
            for handler in self.escalation_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Escalation handler failed: {e}")
        
        logger.info(f"Alert triggered: {alert.message}")
    
    # ============================================================
    # ALERT MANAGEMENT
    # ============================================================
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert
        
        Args:
            alert_id: Alert ID
            
        Returns:
            True if acknowledged
        """
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now()
        return True
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert
        
        Args:
            alert_id: Alert ID
            
        Returns:
            True if resolved
        """
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False
        
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        del self.active_alerts[alert_id]
        return True
    
    def suppress_alert(self, alert_id: str) -> bool:
        """
        Suppress an alert
        
        Args:
            alert_id: Alert ID
            
        Returns:
            True if suppressed
        """
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False
        
        alert.status = AlertStatus.SUPPRESSED
        return True
    
    def get_active_alerts(self) -> List[DataAlert]:
        """
        Get active alerts
        
        Returns:
            List of active alerts
        """
        return list(self.active_alerts.values())
    
    def get_alert_history(
        self,
        severity: Optional[AlertSeverity] = None,
        limit: int = 100
    ) -> List[DataAlert]:
        """
        Get alert history
        
        Args:
            severity: Filter by severity
            limit: Maximum number of alerts
            
        Returns:
            List of alerts
        """
        alerts = list(self.alert_history)
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return alerts[-limit:]
    
    # ============================================================
    # HANDLER MANAGEMENT
    # ============================================================
    
    def add_alert_handler(self, handler: Callable[[DataAlert], None]) -> None:
        """
        Add an alert handler
        
        Args:
            handler: Alert handler function
        """
        self.alert_handlers.append(handler)
    
    def add_escalation_handler(self, handler: Callable[[DataAlert], None]) -> None:
        """
        Add an escalation handler
        
        Args:
            handler: Escalation handler function
        """
        self.escalation_handlers.append(handler)
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get alert statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_rules": len(self.rules),
            "active_rules": len([r for r in self.rules.values() if r.enabled]),
            "total_alerts": len(self.alerts),
            "active_alerts": len(self.active_alerts),
            "alert_counters": self.alert_counters,
            "alert_handlers": len(self.alert_handlers),
            "escalation_handlers": len(self.escalation_handlers),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AlertCondition",
    "AlertSeverity",
    "AlertStatus",
    
    # Dataclasses
    "AlertRule",
    "DataAlert",
    
    # Classes
    "DataAlertedEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

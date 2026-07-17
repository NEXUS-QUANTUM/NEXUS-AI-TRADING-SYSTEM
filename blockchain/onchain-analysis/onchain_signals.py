# blockchain/onchain-analysis/onchain_signals.py
# NEXUS AI TRADING SYSTEM - Advanced On-Chain Signal Generation
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced on-chain signal generation engine for trading and investment decisions.
Generates actionable trading signals based on comprehensive on-chain data analysis
including whale movements, smart money activity, exchange flows, and network metrics.
"""

import asyncio
import json
import logging
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator

# NEXUS Imports
from blockchain.onchain_analysis.base_analyzer import BaseOnChainAnalyzer
from blockchain.onchain_analysis.onchain_metrics import OnChainMetrics
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.date_helpers import parse_timestamp
from shared.utilities.logger import get_logger

logger = get_logger("nexus.onchain.signals")


# ============================================================================
# Enums & Constants
# ============================================================================

class SignalType(str, Enum):
    """Types of trading signals."""
    BUY = "buy"
    SELL = "sell"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    NEUTRAL = "neutral"
    ACCUMULATE = "accumulate"
    DISTRIBUTE = "distribute"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"


class SignalStrength(str, Enum):
    """Strength of a trading signal."""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"
    EXTREME = "extreme"


class SignalCategory(str, Enum):
    """Category of signal source."""
    WHALE = "whale"
    SMART_MONEY = "smart_money"
    EXCHANGE_FLOW = "exchange_flow"
    HOLDER = "holder"
    VOLUME = "volume"
    GAS = "gas"
    MEMPOOL = "mempool"
    DEFI = "defi"
    TOKEN = "token"
    METRICS = "metrics"
    COMPOSITE = "composite"
    TECHNICAL = "technical"  # On-chain technical indicators
    SENTIMENT = "sentiment"


class SignalStatus(str, Enum):
    """Status of a signal."""
    GENERATED = "generated"
    ACTIVE = "active"
    EXPIRED = "expired"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    CONFIRMED = "confirmed"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class SignalDefinition:
    """Definition of a signal generation rule."""
    signal_id: str
    name: str
    category: SignalCategory
    signal_type: SignalType
    strength: SignalStrength
    description: str
    conditions: List[Dict[str, Any]]
    confirmation_required: bool = False
    min_confidence: float = 0.6
    expiry_minutes: int = 60
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    weight: float = 1.0


@dataclass
class OnChainSignal:
    """A generated on-chain trading signal."""
    signal_id: str
    signal_type: SignalType
    strength: SignalStrength
    category: SignalCategory
    token: Optional[str] = None
    chain: str
    price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    confidence: float = 0.0
    generated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    status: SignalStatus = SignalStatus.GENERATED
    reason: str = ""
    supporting_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    source_signals: List[str] = field(default_factory=list)


@dataclass
class SignalAggregation:
    """Aggregated signal from multiple sources."""
    overall_type: SignalType
    overall_strength: SignalStrength
    confidence: float
    buy_signals: int
    sell_signals: int
    neutral_signals: int
    weighted_score: float
    components: List[OnChainSignal]
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# Core Signal Engine
# ============================================================================

class OnChainSignalGenerator(BaseOnChainAnalyzer):
    """
    Advanced on-chain signal generation engine.
    Combines multiple data sources to generate actionable trading signals.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        metrics_engine: Optional[OnChainMetrics] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(web3_client)
        self.metrics_engine = metrics_engine
        self.config = config or {}

        # Signal storage
        self._signals: Dict[str, OnChainSignal] = {}
        self._signal_history: deque = deque(maxlen=10000)
        self._active_signals: Dict[str, OnChainSignal] = {}
        self._signal_definitions: Dict[str, SignalDefinition] = {}

        # Signal aggregation
        self._aggregation_cache: Dict[str, SignalAggregation] = {}
        self._last_aggregation: Dict[str, datetime] = {}

        # State management
        self._running = False
        self._lock = asyncio.Lock()

        # Performance tracking
        self._performance = {
            "signals_generated": 0,
            "signals_executed": 0,
            "signals_expired": 0,
            "false_positives": 0,
            "avg_confidence": 0.0,
            "success_rate": 0.0,
        }

        # Register default signal definitions
        self._register_default_definitions()

        logger.info(
            "OnChainSignalGenerator initialized",
            extra={
                "chain": web3_client.chain_name,
                "definitions": len(self._signal_definitions),
            }
        )

    # -----------------------------------------------------------------------
    # Signal Definition Management
    # -----------------------------------------------------------------------

    def register_definition(self, definition: SignalDefinition) -> bool:
        """Register a signal definition."""
        if definition.signal_id in self._signal_definitions:
            logger.warning(f"Signal definition already exists: {definition.signal_id}")
            return False

        self._signal_definitions[definition.signal_id] = definition
        logger.info(f"Registered signal definition: {definition.signal_id}")
        return True

    def unregister_definition(self, signal_id: str) -> bool:
        """Unregister a signal definition."""
        if signal_id in self._signal_definitions:
            del self._signal_definitions[signal_id]
            logger.info(f"Unregistered signal definition: {signal_id}")
            return True
        return False

    def enable_definition(self, signal_id: str) -> bool:
        """Enable a signal definition."""
        if signal_id in self._signal_definitions:
            self._signal_definitions[signal_id].enabled = True
            return True
        return False

    def disable_definition(self, signal_id: str) -> bool:
        """Disable a signal definition."""
        if signal_id in self._signal_definitions:
            self._signal_definitions[signal_id].enabled = False
            return True
        return False

    def _register_default_definitions(self) -> None:
        """Register default signal definitions."""
        # Whale accumulation signal
        self.register_definition(SignalDefinition(
            signal_id="whale_accumulation",
            name="Whale Accumulation",
            category=SignalCategory.WHALE,
            signal_type=SignalType.BUY,
            strength=SignalStrength.STRONG,
            description="Large whale accumulation detected",
            conditions=[
                {"metric": "whale.accumulation", "operator": "gt", "threshold": 0.7},
                {"metric": "whale.concentration", "operator": "lt", "threshold": 0.3},
            ],
            confirmation_required=True,
            min_confidence=0.7,
        ))

        # Whale distribution signal
        self.register_definition(SignalDefinition(
            signal_id="whale_distribution",
            name="Whale Distribution",
            category=SignalCategory.WHALE,
            signal_type=SignalType.SELL,
            strength=SignalStrength.STRONG,
            description="Large whale distribution detected",
            conditions=[
                {"metric": "whale.distribution", "operator": "gt", "threshold": 0.7},
                {"metric": "whale.concentration", "operator": "gt", "threshold": 0.5},
            ],
            confirmation_required=True,
            min_confidence=0.7,
        ))

        # Smart money buy signal
        self.register_definition(SignalDefinition(
            signal_id="smart_money_buy",
            name="Smart Money Buying",
            category=SignalCategory.SMART_MONEY,
            signal_type=SignalType.STRONG_BUY,
            strength=SignalStrength.STRONG,
            description="Smart money accumulation detected",
            conditions=[
                {"metric": "smart_money.buy_sell_ratio", "operator": "gt", "threshold": 2.0},
                {"metric": "smart_money.confidence", "operator": "gt", "threshold": 0.8},
            ],
            confirmation_required=True,
            min_confidence=0.8,
        ))

        # Smart money sell signal
        self.register_definition(SignalDefinition(
            signal_id="smart_money_sell",
            name="Smart Money Selling",
            category=SignalCategory.SMART_MONEY,
            signal_type=SignalType.SELL,
            strength=SignalStrength.MODERATE,
            description="Smart money distribution detected",
            conditions=[
                {"metric": "smart_money.buy_sell_ratio", "operator": "lt", "threshold": 0.5},
                {"metric": "smart_money.confidence", "operator": "gt", "threshold": 0.7},
            ],
            confirmation_required=True,
            min_confidence=0.7,
        ))

        # Exchange outflow signal (bullish)
        self.register_definition(SignalDefinition(
            signal_id="exchange_outflow",
            name="Exchange Outflow",
            category=SignalCategory.EXCHANGE_FLOW,
            signal_type=SignalType.BUY,
            strength=SignalStrength.MODERATE,
            description="Large exchange outflow (accumulation)",
            conditions=[
                {"metric": "exchange_flow.net_flow", "operator": "lt", "threshold": -1000000},
                {"metric": "exchange_flow.outflow_ratio", "operator": "gt", "threshold": 0.6},
            ],
            min_confidence=0.6,
        ))

        # Exchange inflow signal (bearish)
        self.register_definition(SignalDefinition(
            signal_id="exchange_inflow",
            name="Exchange Inflow",
            category=SignalCategory.EXCHANGE_FLOW,
            signal_type=SignalType.SELL,
            strength=SignalStrength.MODERATE,
            description="Large exchange inflow (distribution)",
            conditions=[
                {"metric": "exchange_flow.net_flow", "operator": "gt", "threshold": 1000000},
                {"metric": "exchange_flow.inflow_ratio", "operator": "gt", "threshold": 0.6},
            ],
            min_confidence=0.6,
        ))

        # Holder growth signal (bullish)
        self.register_definition(SignalDefinition(
            signal_id="holder_growth",
            name="Holder Growth",
            category=SignalCategory.HOLDER,
            signal_type=SignalType.BUY,
            strength=SignalStrength.WEAK,
            description="Significant holder growth",
            conditions=[
                {"metric": "holder.net_growth", "operator": "gt", "threshold": 0.05},
                {"metric": "holder.new_holders", "operator": "gt", "threshold": 100},
            ],
            min_confidence=0.5,
        ))

        # Volume spike signal
        self.register_definition(SignalDefinition(
            signal_id="volume_spike",
            name="Volume Spike",
            category=SignalCategory.VOLUME,
            signal_type=SignalType.NEUTRAL,
            strength=SignalStrength.MODERATE,
            description="Significant volume spike detected",
            conditions=[
                {"metric": "volume.change_24h", "operator": "gt", "threshold": 200},
                {"metric": "volume.absolute", "operator": "gt", "threshold": 1000000},
            ],
            min_confidence=0.5,
        ))

        # DeFi TVL growth
        self.register_definition(SignalDefinition(
            signal_id="defi_tvl_growth",
            name="DeFi TVL Growth",
            category=SignalCategory.DEFI,
            signal_type=SignalType.BUY,
            strength=SignalStrength.MODERATE,
            description="DeFi TVL increasing",
            conditions=[
                {"metric": "defi.tvl_change", "operator": "gt", "threshold": 0.1},
                {"metric": "defi.health_score", "operator": "gt", "threshold": 0.7},
            ],
            min_confidence=0.6,
        ))

        # Network congestion signal
        self.register_definition(SignalDefinition(
            signal_id="network_congestion",
            name="Network Congestion",
            category=SignalCategory.GAS,
            signal_type=SignalType.NEUTRAL,
            strength=SignalStrength.WEAK,
            description="High network congestion",
            conditions=[
                {"metric": "network.congestion", "operator": "gt", "threshold": 80},
                {"metric": "network.gas_price", "operator": "gt", "threshold": 100},
            ],
            min_confidence=0.4,
        ))

        # Mempool backlog signal
        self.register_definition(SignalDefinition(
            signal_id="mempool_backlog",
            name="Mempool Backlog",
            category=SignalCategory.MEMPOOL,
            signal_type=SignalType.NEUTRAL,
            strength=SignalStrength.WEAK,
            description="Large mempool backlog",
            conditions=[
                {"metric": "mempool.pending_count", "operator": "gt", "threshold": 5000},
            ],
            min_confidence=0.3,
        ))

        # Composite bullish signal
        self.register_definition(SignalDefinition(
            signal_id="composite_bullish",
            name="Composite Bullish",
            category=SignalCategory.COMPOSITE,
            signal_type=SignalType.STRONG_BUY,
            strength=SignalStrength.STRONG,
            description="Multiple bullish signals aligning",
            conditions=[
                {"metric": "composite.bullish_index", "operator": "gt", "threshold": 70},
                {"metric": "composite.overall_score", "operator": "gt", "threshold": 60},
                {"metric": "sentiment.general", "operator": "gt", "threshold": 0.3},
            ],
            confirmation_required=True,
            min_confidence=0.8,
            weight=1.5,
        ))

        # Composite bearish signal
        self.register_definition(SignalDefinition(
            signal_id="composite_bearish",
            name="Composite Bearish",
            category=SignalCategory.COMPOSITE,
            signal_type=SignalType.STRONG_SELL,
            strength=SignalStrength.STRONG,
            description="Multiple bearish signals aligning",
            conditions=[
                {"metric": "composite.bullish_index", "operator": "lt", "threshold": 30},
                {"metric": "composite.overall_score", "operator": "lt", "threshold": 40},
                {"metric": "sentiment.general", "operator": "lt", "threshold": -0.3},
            ],
            confirmation_required=True,
            min_confidence=0.8,
            weight=1.5,
        ))

        # Take profit signal
        self.register_definition(SignalDefinition(
            signal_id="take_profit",
            name="Take Profit",
            category=SignalCategory.COMPOSITE,
            signal_type=SignalType.TAKE_PROFIT,
            strength=SignalStrength.MODERATE,
            description="Take profit based on on-chain metrics",
            conditions=[
                {"metric": "composite.overall_score", "operator": "gt", "threshold": 80},
                {"metric": "whale.concentration", "operator": "gt", "threshold": 0.6},
            ],
            min_confidence=0.6,
        ))

    # -----------------------------------------------------------------------
    # Signal Generation
    # -----------------------------------------------------------------------

    async def generate_signal(
        self,
        definition_id: str,
        token: Optional[str] = None,
        token_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[OnChainSignal]:
        """Generate a signal from a definition."""
        definition = self._signal_definitions.get(definition_id)
        if not definition or not definition.enabled:
            return None

        try:
            # Evaluate conditions
            conditions_met, confidence, supporting_data = await self._evaluate_conditions(
                definition.conditions,
                token_data or {}
            )

            if not conditions_met or confidence < definition.min_confidence:
                return None

            # Create signal
            signal = OnChainSignal(
                signal_id=f"{definition_id}_{int(time.time())}_{token or 'global'}",
                signal_type=definition.signal_type,
                strength=definition.strength,
                category=definition.category,
                token=token,
                chain=self.web3_client.chain_name,
                confidence=confidence,
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=definition.expiry_minutes),
                reason=definition.description,
                supporting_data=supporting_data,
                weight=definition.weight,
                source_signals=[],
            )

            # Store signal
            async with self._lock:
                self._signals[signal.signal_id] = signal
                self._signal_history.append(signal)
                if signal.status == SignalStatus.GENERATED:
                    self._active_signals[signal.signal_id] = signal

            self._performance["signals_generated"] += 1
            self._performance["avg_confidence"] = (
                (self._performance["avg_confidence"] * (self._performance["signals_generated"] - 1) +
                 confidence) / self._performance["signals_generated"]
            )

            logger.info(
                f"Signal generated: {signal.signal_id}",
                extra={
                    "type": signal.signal_type.value,
                    "strength": signal.strength.value,
                    "confidence": signal.confidence,
                    "category": signal.category.value,
                }
            )

            return signal

        except Exception as e:
            logger.error(f"Error generating signal {definition_id}: {e}")
            return None

    async def _evaluate_conditions(
        self,
        conditions: List[Dict[str, Any]],
        token_data: Dict[str, Any]
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Evaluate signal conditions."""
        conditions_met = True
        confidences = []
        supporting_data = {}

        for condition in conditions:
            metric = condition.get("metric")
            operator = condition.get("operator")
            threshold = condition.get("threshold")

            if not metric:
                continue

            # Get metric value
            value = await self._get_metric_value(metric, token_data)

            if value is None:
                logger.debug(f"Metric {metric} not available")
                conditions_met = False
                break

            supporting_data[metric] = value

            # Evaluate condition
            met = self._evaluate_condition(value, operator, threshold)
            if not met:
                conditions_met = False
                break

            # Calculate confidence contribution
            confidence = self._calculate_confidence_for_condition(value, threshold, operator)
            confidences.append(confidence)

        if conditions_met and confidences:
            overall_confidence = np.mean(confidences)
            return True, overall_confidence, supporting_data

        return False, 0.0, supporting_data

    def _evaluate_condition(
        self,
        value: float,
        operator: str,
        threshold: Any
    ) -> bool:
        """Evaluate a single condition."""
        try:
            if operator == "gt":
                return value > threshold
            elif operator == "gte":
                return value >= threshold
            elif operator == "lt":
                return value < threshold
            elif operator == "lte":
                return value <= threshold
            elif operator == "eq":
                return value == threshold
            elif operator == "neq":
                return value != threshold
            elif operator == "between":
                if isinstance(threshold, (list, tuple)) and len(threshold) == 2:
                    return threshold[0] <= value <= threshold[1]
                return False
            elif operator == "outside":
                if isinstance(threshold, (list, tuple)) and len(threshold) == 2:
                    return value < threshold[0] or value > threshold[1]
                return False
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except Exception as e:
            logger.debug(f"Error evaluating condition: {e}")
            return False

    def _calculate_confidence_for_condition(
        self,
        value: float,
        threshold: Any,
        operator: str
    ) -> float:
        """Calculate confidence for a condition."""
        confidence = 0.6  # Base confidence

        try:
            if operator in ["gt", "gte"]:
                # Higher value = higher confidence
                if isinstance(threshold, (int, float)):
                    ratio = value / max(threshold, 0.001)
                    confidence = min(0.95, 0.6 + (ratio - 1) * 0.2)

            elif operator in ["lt", "lte"]:
                # Lower value = higher confidence
                if isinstance(threshold, (int, float)):
                    ratio = threshold / max(value, 0.001)
                    confidence = min(0.95, 0.6 + (ratio - 1) * 0.2)

            elif operator == "between":
                if isinstance(threshold, (list, tuple)) and len(threshold) == 2:
                    # Closer to center = higher confidence
                    center = (threshold[0] + threshold[1]) / 2
                    half_range = (threshold[1] - threshold[0]) / 2
                    if half_range > 0:
                        distance = abs(value - center) / half_range
                        confidence = 0.6 + (1 - min(distance, 1)) * 0.3

            elif operator == "eq":
                confidence = 0.8

        except Exception:
            pass

        return max(0.5, min(0.95, confidence))

    async def _get_metric_value(
        self,
        metric: str,
        token_data: Dict[str, Any]
    ) -> Optional[float]:
        """Get metric value from various sources."""
        # First check token_data
        if metric in token_data:
            return float(token_data[metric])

        # Check if it's a nested key (e.g., "whale.accumulation")
        parts = metric.split(".")
        if len(parts) > 1:
            current = token_data
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    current = None
                    break
            if current is not None:
                return float(current)

        # Check metrics engine
        if self.metrics_engine:
            try:
                value = await self.metrics_engine.get_metric(metric)
                if value:
                    return value.value
            except Exception:
                pass

        return None

    # -----------------------------------------------------------------------
    # Signal Aggregation
    # -----------------------------------------------------------------------

    async def aggregate_signals(
        self,
        token: Optional[str] = None,
        min_confidence: float = 0.5,
        max_age_seconds: int = 300,
    ) -> SignalAggregation:
        """Aggregate signals from all sources."""
        # Get recent signals
        cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
        recent_signals = []

        async with self._lock:
            for signal in self._signal_history:
                if token and signal.token != token:
                    continue
                if signal.generated_at < cutoff:
                    continue
                if signal.confidence < min_confidence:
                    continue
                if signal.status not in [SignalStatus.GENERATED, SignalStatus.ACTIVE]:
                    continue
                recent_signals.append(signal)

        # Count signals by type
        buy_signals = [s for s in recent_signals if s.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]]
        sell_signals = [s for s in recent_signals if s.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]]
        neutral_signals = [s for s in recent_signals if s.signal_type == SignalType.NEUTRAL]

        # Calculate weighted scores
        buy_score = sum(s.confidence * s.weight for s in buy_signals)
        sell_score = sum(s.confidence * s.weight for s in sell_signals)

        # Normalize scores
        total_score = buy_score + sell_score
        if total_score == 0:
            score_ratio = 0.5
        else:
            score_ratio = buy_score / total_score

        # Determine overall signal type
        if score_ratio > 0.7 and len(buy_signals) > 2:
            overall_type = SignalType.STRONG_BUY if score_ratio > 0.85 else SignalType.BUY
        elif score_ratio < 0.3 and len(sell_signals) > 2:
            overall_type = SignalType.STRONG_SELL if score_ratio < 0.15 else SignalType.SELL
        else:
            overall_type = SignalType.NEUTRAL

        # Determine overall strength
        total_signals = len(recent_signals)
        if total_signals >= 5 and (len(buy_signals) >= 4 or len(sell_signals) >= 4):
            overall_strength = SignalStrength.STRONG
        elif total_signals >= 3 and (len(buy_signals) >= 2 or len(sell_signals) >= 2):
            overall_strength = SignalStrength.MODERATE
        elif total_signals >= 1:
            overall_strength = SignalStrength.WEAK
        else:
            overall_strength = SignalStrength.VERY_WEAK

        # Calculate overall confidence
        if total_signals > 0:
            avg_confidence = np.mean([s.confidence for s in recent_signals])
            confidence = min(0.95, avg_confidence * (1 + min(total_signals / 10, 0.3)))
        else:
            confidence = 0.0

        # Generate aggregation
        aggregation = SignalAggregation(
            overall_type=overall_type,
            overall_strength=overall_strength,
            confidence=confidence,
            buy_signals=len(buy_signals),
            sell_signals=len(sell_signals),
            neutral_signals=len(neutral_signals),
            weighted_score=score_ratio,
            components=recent_signals,
            timestamp=datetime.utcnow(),
        )

        # Cache aggregation
        cache_key = f"{token or 'global'}_{int(time.time() / 60)}"
        self._aggregation_cache[cache_key] = aggregation
        self._last_aggregation[token or "global"] = datetime.utcnow()

        return aggregation

    # -----------------------------------------------------------------------
    # Signal Management
    # -----------------------------------------------------------------------

    async def confirm_signal(self, signal_id: str) -> bool:
        """Confirm a signal (move from generated to active)."""
        signal = self._signals.get(signal_id)
        if not signal or signal.status != SignalStatus.GENERATED:
            return False

        signal.status = SignalStatus.CONFIRMED
        signal.confidence = min(0.99, signal.confidence * 1.1)  # Increase confidence

        async with self._lock:
            self._active_signals[signal_id] = signal

        logger.info(f"Signal confirmed: {signal_id}")
        return True

    async def execute_signal(self, signal_id: str) -> bool:
        """Mark a signal as executed."""
        signal = self._signals.get(signal_id)
        if not signal or signal.status not in [SignalStatus.GENERATED, SignalStatus.CONFIRMED, SignalStatus.ACTIVE]:
            return False

        signal.status = SignalStatus.EXECUTED
        self._performance["signals_executed"] += 1

        async with self._lock:
            if signal_id in self._active_signals:
                del self._active_signals[signal_id]

        logger.info(f"Signal executed: {signal_id}")
        return True

    async def cancel_signal(self, signal_id: str, reason: str = "Cancelled") -> bool:
        """Cancel a signal."""
        signal = self._signals.get(signal_id)
        if not signal or signal.status in [SignalStatus.EXECUTED, SignalStatus.EXPIRED]:
            return False

        signal.status = SignalStatus.CANCELLED
        signal.metadata["cancellation_reason"] = reason

        async with self._lock:
            if signal_id in self._active_signals:
                del self._active_signals[signal_id]

        logger.info(f"Signal cancelled: {signal_id} - {reason}")
        return True

    async def expire_signals(self) -> int:
        """Expire old signals."""
        now = datetime.utcnow()
        expired = 0

        async with self._lock:
            for signal_id, signal in list(self._active_signals.items()):
                if signal.expires_at and signal.expires_at < now:
                    signal.status = SignalStatus.EXPIRED
                    del self._active_signals[signal_id]
                    expired += 1
                    self._performance["signals_expired"] += 1

        if expired > 0:
            logger.info(f"Expired {expired} signals")

        return expired

    # -----------------------------------------------------------------------
    # Signal Analysis
    # -----------------------------------------------------------------------

    def get_signal_distribution(self, hours: int = 24) -> Dict[str, Any]:
        """Get distribution of signals over time."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        signals = [
            s for s in self._signal_history
            if s.generated_at >= cutoff
        ]

        distribution = {
            "total": len(signals),
            "by_type": defaultdict(int),
            "by_strength": defaultdict(int),
            "by_category": defaultdict(int),
            "by_status": defaultdict(int),
            "average_confidence": 0.0,
            "success_rate": 0.0,
        }

        if signals:
            for signal in signals:
                distribution["by_type"][signal.signal_type.value] += 1
                distribution["by_strength"][signal.strength.value] += 1
                distribution["by_category"][signal.category.value] += 1
                distribution["by_status"][signal.status.value] += 1

            distribution["average_confidence"] = np.mean([s.confidence for s in signals])

            # Calculate rough success rate based on executed vs total
            executed = sum(1 for s in signals if s.status == SignalStatus.EXECUTED)
            if len(signals) > 0:
                distribution["success_rate"] = executed / len(signals)

        return distribution

    def get_best_signals(
        self,
        limit: int = 10,
        min_confidence: float = 0.7,
    ) -> List[OnChainSignal]:
        """Get the best signals based on confidence and strength."""
        signals = [
            s for s in self._signal_history
            if s.confidence >= min_confidence
            and s.status in [SignalStatus.GENERATED, SignalStatus.CONFIRMED, SignalStatus.ACTIVE]
        ]

        # Sort by confidence * weight
        signals.sort(key=lambda s: s.confidence * s.weight, reverse=True)
        return signals[:limit]

    def get_signals_for_token(
        self,
        token: str,
        hours: int = 24,
        include_expired: bool = False,
    ) -> List[OnChainSignal]:
        """Get signals for a specific token."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        signals = [
            s for s in self._signal_history
            if s.token == token
            and s.generated_at >= cutoff
            and (include_expired or s.status != SignalStatus.EXPIRED)
        ]

        return sorted(signals, key=lambda s: s.generated_at, reverse=True)

    # -----------------------------------------------------------------------
    # Performance Tracking
    # -----------------------------------------------------------------------

    def record_outcome(self, signal_id: str, successful: bool) -> None:
        """Record the outcome of a signal."""
        signal = self._signals.get(signal_id)
        if not signal:
            return

        signal.metadata["outcome"] = "successful" if successful else "failed"
        signal.metadata["evaluated_at"] = datetime.utcnow().isoformat()

        if not successful:
            self._performance["false_positives"] += 1

        # Update success rate
        total = self._performance["signals_executed"] + self._performance["false_positives"]
        if total > 0:
            self._performance["success_rate"] = (
                self._performance["signals_executed"] / total
            )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics."""
        return {
            **self._performance,
            "active_signals": len(self._active_signals),
            "total_signals": len(self._signals),
            "definitions": len(self._signal_definitions),
            "enabled_definitions": sum(1 for d in self._signal_definitions.values() if d.enabled),
        }

    # -----------------------------------------------------------------------
    # Signal Export
    # -----------------------------------------------------------------------

    def export_signals(
        self,
        format: str = "json",
        hours: int = 24,
    ) -> Union[str, pd.DataFrame]:
        """Export signals in various formats."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        signals = [s for s in self._signal_history if s.generated_at >= cutoff]

        if not signals:
            return "" if format == "json" else pd.DataFrame()

        if format == "json":
            data = []
            for s in signals:
                data.append({
                    "signal_id": s.signal_id,
                    "type": s.signal_type.value,
                    "strength": s.strength.value,
                    "category": s.category.value,
                    "token": s.token,
                    "chain": s.chain,
                    "price": s.price,
                    "target_price": s.target_price,
                    "stop_loss": s.stop_loss,
                    "confidence": s.confidence,
                    "generated_at": s.generated_at.isoformat(),
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "status": s.status.value,
                    "reason": s.reason,
                })
            return json.dumps(data, indent=2)

        elif format == "dataframe":
            df_data = []
            for s in signals:
                df_data.append({
                    "signal_id": s.signal_id,
                    "type": s.signal_type.value,
                    "strength": s.strength.value,
                    "category": s.category.value,
                    "token": s.token,
                    "confidence": s.confidence,
                    "generated_at": s.generated_at,
                    "status": s.status.value,
                })
            return pd.DataFrame(df_data)

        return ""

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the signal generator."""
        if self._running:
            return

        self._running = True

        # Start background tasks
        asyncio.create_task(self._expire_signals_loop())
        asyncio.create_task(self._periodic_aggregation())

        logger.info("OnChainSignalGenerator started")

    async def stop(self) -> None:
        """Stop the signal generator."""
        self._running = False
        logger.info("OnChainSignalGenerator stopped")

    async def _expire_signals_loop(self) -> None:
        """Background task to expire old signals."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.expire_signals()
            except Exception as e:
                logger.error(f"Error in expire loop: {e}")

    async def _periodic_aggregation(self) -> None:
        """Background task for periodic signal aggregation."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                # Aggregate for all tokens
                tokens = set()
                for signal in self._signal_history:
                    if signal.token:
                        tokens.add(signal.token)

                # Also do global aggregation
                await self.aggregate_signals()

                for token in tokens:
                    await self.aggregate_signals(token)

            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")


# ============================================================================
# Factory Function
# ============================================================================

def create_onchain_signal_generator(
    web3_client: Web3Client,
    metrics_engine: Optional[OnChainMetrics] = None,
    config: Optional[Dict[str, Any]] = None,
) -> OnChainSignalGenerator:
    """Factory function to create an OnChainSignalGenerator instance."""
    return OnChainSignalGenerator(
        web3_client=web3_client,
        metrics_engine=metrics_engine,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the signal generator
    pass

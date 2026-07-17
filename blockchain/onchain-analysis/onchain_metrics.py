# blockchain/onchain-analysis/onchain_metrics.py
# NEXUS AI TRADING SYSTEM - Advanced On-Chain Metrics Collection
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Comprehensive on-chain metrics collection and calculation engine.
Provides advanced quantitative metrics for blockchain analysis including
network health, economic indicators, and token-specific measurements.
"""

import asyncio
import json
import logging
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import aiohttp
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator

# NEXUS Imports
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.date_helpers import parse_timestamp
from shared.utilities.logger import get_logger

logger = get_logger("nexus.onchain.metrics")


# ============================================================================
# Enums & Constants
# ============================================================================

class MetricCategory(str, Enum):
    """Categories of on-chain metrics."""
    NETWORK = "network"
    ECONOMIC = "economic"
    TOKEN = "token"
    ACTIVITY = "activity"
    HEALTH = "health"
    SECURITY = "security"
    DEFI = "defi"
    WHALE = "whale"
    SENTIMENT = "sentiment"
    COMPOSITE = "composite"


class MetricFrequency(str, Enum):
    """Update frequency for metrics."""
    REAL_TIME = "real_time"  # Updated every block
    HIGH = "high"  # Updated every minute
    MEDIUM = "medium"  # Updated every 5 minutes
    LOW = "low"  # Updated every hour
    DAILY = "daily"  # Updated daily
    WEEKLY = "weekly"  # Updated weekly


class MetricStatus(str, Enum):
    """Status of a metric."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DEPRECATED = "deprecated"


@dataclass
class MetricDefinition:
    """Definition of an on-chain metric."""
    metric_id: str
    name: str
    category: MetricCategory
    frequency: MetricFrequency
    description: str
    unit: str
    calculation: Callable
    dependencies: List[str] = field(default_factory=list)
    status: MetricStatus = MetricStatus.ACTIVE
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    requires_historical: bool = False
    history_window_days: int = 30


@dataclass
class MetricValue:
    """Value of a metric at a specific time."""
    metric_id: str
    value: float
    timestamp: datetime
    block_number: Optional[int] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSnapshot:
    """Snapshot of all metrics at a point in time."""
    timestamp: datetime
    block_number: int
    metrics: Dict[str, MetricValue]
    chain: str
    health_score: float
    confidence_score: float


# ============================================================================
# Core Metrics Engine
# ============================================================================

class OnChainMetrics:
    """
    Advanced on-chain metrics collection and calculation engine.
    Provides real-time and historical metrics for blockchain analysis.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.config = config or {}

        # Metric storage
        self._metrics: Dict[str, MetricDefinition] = {}
        self._metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._current_values: Dict[str, MetricValue] = {}
        self._snapshots: deque = deque(maxlen=1000)

        # State management
        self._running = False
        self._lock = asyncio.Lock()
        self._last_update = None
        self._update_count = 0

        # Performance tracking
        self._performance = {
            "calculations": 0,
            "errors": 0,
            "avg_calculation_ms": 0.0,
            "last_calculation_time": None,
            "metrics_by_category": defaultdict(int),
        }

        # Register default metrics
        self._register_default_metrics()

        logger.info(
            "OnChainMetrics initialized",
            extra={
                "chain": web3_client.chain_name,
                "registered_metrics": len(self._metrics),
            }
        )

    # -----------------------------------------------------------------------
    # Metric Registration
    # -----------------------------------------------------------------------

    def register_metric(self, definition: MetricDefinition) -> bool:
        """Register a new metric definition."""
        if definition.metric_id in self._metrics:
            logger.warning(f"Metric already registered: {definition.metric_id}")
            return False

        self._metrics[definition.metric_id] = definition
        self._performance["metrics_by_category"][definition.category.value] += 1
        logger.info(f"Registered metric: {definition.metric_id}")
        return True

    def unregister_metric(self, metric_id: str) -> bool:
        """Unregister a metric."""
        if metric_id in self._metrics:
            del self._metrics[metric_id]
            self._metric_history.pop(metric_id, None)
            self._current_values.pop(metric_id, None)
            logger.info(f"Unregistered metric: {metric_id}")
            return True
        return False

    def _register_default_metrics(self) -> None:
        """Register the default set of on-chain metrics."""
        # Network metrics
        self.register_metric(MetricDefinition(
            metric_id="network.block_time",
            name="Average Block Time",
            category=MetricCategory.NETWORK,
            frequency=MetricFrequency.HIGH,
            description="Average time between blocks in seconds",
            unit="seconds",
            calculation=self._calculate_block_time,
            dependencies=["network.latest_block"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="network.hash_rate",
            name="Network Hash Rate",
            category=MetricCategory.NETWORK,
            frequency=MetricFrequency.HIGH,
            description="Total computational power of the network",
            unit="TH/s",
            calculation=self._calculate_hash_rate,
            dependencies=["network.latest_block"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="network.difficulty",
            name="Network Difficulty",
            category=MetricCategory.NETWORK,
            frequency=MetricFrequency.HIGH,
            description="Current network difficulty",
            unit="difficulty",
            calculation=self._calculate_difficulty,
            dependencies=["network.latest_block"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="network.gas_price",
            name="Current Gas Price",
            category=MetricCategory.NETWORK,
            frequency=MetricFrequency.REAL_TIME,
            description="Current gas price in gwei",
            unit="gwei",
            calculation=self._calculate_gas_price,
            dependencies=["web3_client.get_gas_price"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="network.congestion",
            name="Network Congestion Level",
            category=MetricCategory.NETWORK,
            frequency=MetricFrequency.HIGH,
            description="Network congestion level (0-100)",
            unit="%",
            calculation=self._calculate_congestion,
            dependencies=["network.gas_price", "network.block_time"],
        ))

        # Economic metrics
        self.register_metric(MetricDefinition(
            metric_id="economic.tvl",
            name="Total Value Locked",
            category=MetricCategory.ECONOMIC,
            frequency=MetricFrequency.MEDIUM,
            description="Total value locked in DeFi protocols",
            unit="USD",
            calculation=self._calculate_tvl,
            dependencies=["defi.protocols"],
            requires_historical=True,
        ))

        self.register_metric(MetricDefinition(
            metric_id="economic.daily_volume",
            name="Daily On-Chain Volume",
            category=MetricCategory.ECONOMIC,
            frequency=MetricFrequency.LOW,
            description="Total daily transaction volume",
            unit="USD",
            calculation=self._calculate_daily_volume,
            dependencies=["network.transactions"],
            requires_historical=True,
        ))

        self.register_metric(MetricDefinition(
            metric_id="economic.active_addresses",
            name="Active Addresses",
            category=MetricCategory.ECONOMIC,
            frequency=MetricFrequency.MEDIUM,
            description="Number of active addresses in the last 24 hours",
            unit="addresses",
            calculation=self._calculate_active_addresses,
            dependencies=["network.transactions"],
            requires_historical=True,
        ))

        self.register_metric(MetricDefinition(
            metric_id="economic.network_velocity",
            name="Network Velocity",
            category=MetricCategory.ECONOMIC,
            frequency=MetricFrequency.LOW,
            description="Network velocity (turnover of tokens)",
            unit="tokens/day",
            calculation=self._calculate_network_velocity,
            dependencies=["economic.daily_volume", "economic.tvl"],
            requires_historical=True,
        ))

        self.register_metric(MetricDefinition(
            metric_id="economic.network_growth",
            name="Network Growth Rate",
            category=MetricCategory.ECONOMIC,
            frequency=MetricFrequency.LOW,
            description="Growth rate of the network",
            unit="%",
            calculation=self._calculate_network_growth,
            dependencies=["economic.active_addresses"],
            requires_historical=True,
        ))

        # Token metrics
        self.register_metric(MetricDefinition(
            metric_id="token.supply",
            name="Token Supply",
            category=MetricCategory.TOKEN,
            frequency=MetricFrequency.HIGH,
            description="Total token supply",
            unit="tokens",
            calculation=self._calculate_token_supply,
            dependencies=["web3_client.get_token_supply"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="token.circulating_supply",
            name="Circulating Supply",
            category=MetricCategory.TOKEN,
            frequency=MetricFrequency.HIGH,
            description="Circulating token supply",
            unit="tokens",
            calculation=self._calculate_circulating_supply,
            dependencies=["token.supply", "web3_client.get_locked_tokens"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="token.holder_count",
            name="Number of Holders",
            category=MetricCategory.TOKEN,
            frequency=MetricFrequency.MEDIUM,
            description="Total number of token holders",
            unit="holders",
            calculation=self._calculate_holder_count,
            dependencies=["web3_client.get_token_holders"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="token.concentration",
            name="Token Concentration",
            category=MetricCategory.TOKEN,
            frequency=MetricFrequency.LOW,
            description="Token concentration score (0-1)",
            unit="score",
            calculation=self._calculate_concentration,
            dependencies=["web3_client.get_token_holders"],
            requires_historical=True,
        ))

        # Activity metrics
        self.register_metric(MetricDefinition(
            metric_id="activity.tx_count",
            name="Transaction Count",
            category=MetricCategory.ACTIVITY,
            frequency=MetricFrequency.HIGH,
            description="Number of recent transactions",
            unit="txs",
            calculation=self._calculate_tx_count,
            dependencies=["network.latest_block"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="activity.unique_addresses",
            name="Unique Addresses",
            category=MetricCategory.ACTIVITY,
            frequency=MetricFrequency.MEDIUM,
            description="Number of unique addresses",
            unit="addresses",
            calculation=self._calculate_unique_addresses,
            dependencies=["network.transactions"],
            requires_historical=True,
        ))

        self.register_metric(MetricDefinition(
            metric_id="activity.contract_interactions",
            name="Contract Interactions",
            category=MetricCategory.ACTIVITY,
            frequency=MetricFrequency.MEDIUM,
            description="Number of contract interactions",
            unit="interactions",
            calculation=self._calculate_contract_interactions,
            dependencies=["network.transactions"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="activity.new_contracts",
            name="New Contracts",
            category=MetricCategory.ACTIVITY,
            frequency=MetricFrequency.MEDIUM,
            description="Number of newly deployed contracts",
            unit="contracts",
            calculation=self._calculate_new_contracts,
            dependencies=["network.transactions"],
        ))

        # Health metrics
        self.register_metric(MetricDefinition(
            metric_id="health.network_health",
            name="Network Health Score",
            category=MetricCategory.HEALTH,
            frequency=MetricFrequency.HIGH,
            description="Overall network health score (0-100)",
            unit="score",
            calculation=self._calculate_network_health,
            dependencies=[
                "network.congestion",
                "network.gas_price",
                "economic.active_addresses",
                "economic.tvl",
            ],
        ))

        self.register_metric(MetricDefinition(
            metric_id="health.security_score",
            name="Security Score",
            category=MetricCategory.HEALTH,
            frequency=MetricFrequency.LOW,
            description="Network security score",
            unit="score",
            calculation=self._calculate_security_score,
            dependencies=["network.hash_rate", "network.difficulty"],
        ))

        # Whale metrics
        self.register_metric(MetricDefinition(
            metric_id="whale.concentration",
            name="Whale Concentration",
            category=MetricCategory.WHALE,
            frequency=MetricFrequency.LOW,
            description="Whale concentration score",
            unit="score",
            calculation=self._calculate_whale_concentration,
            dependencies=["web3_client.get_token_holders"],
        ))

        self.register_metric(MetricDefinition(
            metric_id="whale.accumulation",
            name="Whale Accumulation Score",
            category=MetricCategory.WHALE,
            frequency=MetricFrequency.MEDIUM,
            description="Whale accumulation score",
            unit="score",
            calculation=self._calculate_whale_accumulation,
            dependencies=["web3_client.get_token_holders"],
            requires_historical=True,
        ))

        self.register_metric(MetricDefinition(
            metric_id="whale.distribution",
            name="Whale Distribution Score",
            category=MetricCategory.WHALE,
            frequency=MetricFrequency.MEDIUM,
            description="Whale distribution score",
            unit="score",
            calculation=self._calculate_whale_distribution,
            dependencies=["web3_client.get_token_holders"],
            requires_historical=True,
        ))

        # Sentiment metrics
        self.register_metric(MetricDefinition(
            metric_id="sentiment.general",
            name="General Sentiment",
            category=MetricCategory.SENTIMENT,
            frequency=MetricFrequency.MEDIUM,
            description="General sentiment score (-1 to 1)",
            unit="score",
            calculation=self._calculate_general_sentiment,
            dependencies=[
                "whale.accumulation",
                "whale.distribution",
                "economic.network_growth",
                "network.congestion",
            ],
        ))

        self.register_metric(MetricDefinition(
            metric_id="sentiment.bullish_index",
            name="Bullish Index",
            category=MetricCategory.SENTIMENT,
            frequency=MetricFrequency.MEDIUM,
            description="Bullish sentiment index (0-100)",
            unit="%",
            calculation=self._calculate_bullish_index,
            dependencies=["sentiment.general"],
        ))

        # Composite metrics
        self.register_metric(MetricDefinition(
            metric_id="composite.overall_score",
            name="Overall Score",
            category=MetricCategory.COMPOSITE,
            frequency=MetricFrequency.HIGH,
            description="Overall on-chain score (0-100)",
            unit="score",
            calculation=self._calculate_overall_score,
            dependencies=[
                "health.network_health",
                "economic.network_growth",
                "whale.accumulation",
                "sentiment.general",
            ],
        ))

        self.register_metric(MetricDefinition(
            metric_id="composite.investment_index",
            name="Investment Index",
            category=MetricCategory.COMPOSITE,
            frequency=MetricFrequency.MEDIUM,
            description="Investment attractiveness index",
            unit="score",
            calculation=self._calculate_investment_index,
            dependencies=[
                "composite.overall_score",
                "whale.concentration",
                "economic.network_velocity",
            ],
        ))

    # -----------------------------------------------------------------------
    # Metric Calculation Methods
    # -----------------------------------------------------------------------

    async def _calculate_block_time(self) -> float:
        """Calculate average block time."""
        try:
            latest = await self.web3_client.get_block('latest')
            if latest and 'timestamp' in latest:
                # Get previous block
                prev = await self.web3_client.get_block(latest['number'] - 1)
                if prev and 'timestamp' in prev:
                    diff = latest['timestamp'] - prev['timestamp']
                    return float(diff)
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating block time: {e}")
            return 0.0

    async def _calculate_hash_rate(self) -> float:
        """Calculate network hash rate."""
        try:
            # Simplified - in production would use network data
            difficulty = await self._calculate_difficulty()
            block_time = await self._calculate_block_time()
            if block_time > 0:
                return difficulty / block_time
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating hash rate: {e}")
            return 0.0

    async def _calculate_difficulty(self) -> float:
        """Calculate network difficulty."""
        try:
            latest = await self.web3_client.get_block('latest')
            if latest and 'difficulty' in latest:
                return float(latest['difficulty'])
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating difficulty: {e}")
            return 0.0

    async def _calculate_gas_price(self) -> float:
        """Calculate current gas price."""
        try:
            gas_price = await self.web3_client.get_gas_price()
            return float(gas_price) / 1e9  # Convert to gwei
        except Exception as e:
            logger.error(f"Error calculating gas price: {e}")
            return 0.0

    async def _calculate_congestion(self) -> float:
        """Calculate network congestion level."""
        try:
            gas_price = await self._calculate_gas_price()
            block_time = await self._calculate_block_time()
            if gas_price > 0 and block_time > 0:
                # Higher gas price + lower block time = more congestion
                congestion = min(100, (gas_price / 50) * (1 / block_time) * 10)
                return min(congestion, 100)
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating congestion: {e}")
            return 0.0

    async def _calculate_tvl(self) -> float:
        """Calculate total value locked."""
        try:
            # In production, would aggregate from DeFi protocols
            # For now, return a placeholder calculation
            active_addresses = await self._calculate_active_addresses()
            return active_addresses * 1000  # Simple approximation
        except Exception as e:
            logger.error(f"Error calculating TVL: {e}")
            return 0.0

    async def _calculate_daily_volume(self) -> float:
        """Calculate daily on-chain volume."""
        try:
            # In production, would aggregate transaction values
            # For now, use a placeholder
            tx_count = await self._calculate_tx_count()
            return tx_count * 500  # Simple approximation
        except Exception as e:
            logger.error(f"Error calculating daily volume: {e}")
            return 0.0

    async def _calculate_active_addresses(self) -> float:
        """Calculate active addresses."""
        try:
            # In production, would count unique addresses in transactions
            # For now, use a placeholder based on tx count
            tx_count = await self._calculate_tx_count()
            return tx_count * 0.3  # Simple approximation
        except Exception as e:
            logger.error(f"Error calculating active addresses: {e}")
            return 0.0

    async def _calculate_network_velocity(self) -> float:
        """Calculate network velocity."""
        try:
            volume = await self._calculate_daily_volume()
            tvl = await self._calculate_tvl()
            if tvl > 0:
                return volume / tvl
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating network velocity: {e}")
            return 0.0

    async def _calculate_network_growth(self) -> float:
        """Calculate network growth rate."""
        try:
            current = await self._calculate_active_addresses()
            historical = self.get_historical_values("economic.active_addresses", hours=24)
            if historical and len(historical) > 0:
                previous = historical[-1].value if historical else current
                if previous > 0:
                    return ((current - previous) / previous) * 100
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating network growth: {e}")
            return 0.0

    async def _calculate_token_supply(self) -> float:
        """Calculate token supply."""
        try:
            # In production, would get from contract
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating token supply: {e}")
            return 0.0

    async def _calculate_circulating_supply(self) -> float:
        """Calculate circulating supply."""
        try:
            total = await self._calculate_token_supply()
            # In production, would subtract locked tokens
            return total * 0.8  # Simplified
        except Exception as e:
            logger.error(f"Error calculating circulating supply: {e}")
            return 0.0

    async def _calculate_holder_count(self) -> float:
        """Calculate number of holders."""
        try:
            # In production, would get from contract
            return 1000  # Placeholder
        except Exception as e:
            logger.error(f"Error calculating holder count: {e}")
            return 0.0

    async def _calculate_concentration(self) -> float:
        """Calculate token concentration."""
        try:
            holder_count = await self._calculate_holder_count()
            # Simplified Gini coefficient approximation
            return 0.5
        except Exception as e:
            logger.error(f"Error calculating concentration: {e}")
            return 0.0

    async def _calculate_tx_count(self) -> float:
        """Calculate transaction count."""
        try:
            latest = await self.web3_client.get_block('latest')
            if latest and 'transactions' in latest:
                return float(len(latest['transactions']))
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating tx count: {e}")
            return 0.0

    async def _calculate_unique_addresses(self) -> float:
        """Calculate unique addresses."""
        try:
            # In production, would track unique addresses
            return await self._calculate_active_addresses()
        except Exception as e:
            logger.error(f"Error calculating unique addresses: {e}")
            return 0.0

    async def _calculate_contract_interactions(self) -> float:
        """Calculate contract interactions."""
        try:
            # In production, would count contract calls
            tx_count = await self._calculate_tx_count()
            return tx_count * 0.4  # Simplified
        except Exception as e:
            logger.error(f"Error calculating contract interactions: {e}")
            return 0.0

    async def _calculate_new_contracts(self) -> float:
        """Calculate new contracts."""
        try:
            # In production, would count contract creations
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating new contracts: {e}")
            return 0.0

    async def _calculate_network_health(self) -> float:
        """Calculate network health score."""
        try:
            congestion = await self._calculate_congestion()
            gas_price = await self._calculate_gas_price()
            active = await self._calculate_active_addresses()

            # Health is better when congestion is low, gas is reasonable, and activity is high
            congestion_score = max(0, 100 - congestion)
            gas_score = max(0, 100 - (gas_price / 200) * 100)
            activity_score = min(100, (active / 10000) * 100)

            health = (congestion_score * 0.4 + gas_score * 0.3 + activity_score * 0.3)
            return min(max(health, 0), 100)
        except Exception as e:
            logger.error(f"Error calculating network health: {e}")
            return 50.0

    async def _calculate_security_score(self) -> float:
        """Calculate security score."""
        try:
            hash_rate = await self._calculate_hash_rate()
            difficulty = await self._calculate_difficulty()

            # Higher hash rate and difficulty = more secure
            hash_score = min(100, hash_rate / 1000000 * 100)
            diff_score = min(100, difficulty / 1000000000000 * 100)

            return (hash_score * 0.6 + diff_score * 0.4)
        except Exception as e:
            logger.error(f"Error calculating security score: {e}")
            return 50.0

    async def _calculate_whale_concentration(self) -> float:
        """Calculate whale concentration."""
        try:
            # In production, would calculate from top holders
            return 0.3
        except Exception as e:
            logger.error(f"Error calculating whale concentration: {e}")
            return 0.0

    async def _calculate_whale_accumulation(self) -> float:
        """Calculate whale accumulation score."""
        try:
            # In production, would track whale wallet balances
            historical = self.get_historical_values("whale.concentration", hours=24)
            if historical and len(historical) > 0:
                current = await self._calculate_whale_concentration()
                previous = historical[-1].value if historical else current
                # Accumulation if concentration is increasing
                if previous > 0:
                    change = ((current - previous) / previous)
                    return max(0, min(1, change * 10 + 0.5))
            return 0.5
        except Exception as e:
            logger.error(f"Error calculating whale accumulation: {e}")
            return 0.5

    async def _calculate_whale_distribution(self) -> float:
        """Calculate whale distribution score."""
        try:
            # Inverse of accumulation
            accumulation = await self._calculate_whale_accumulation()
            return 1 - accumulation
        except Exception as e:
            logger.error(f"Error calculating whale distribution: {e}")
            return 0.5

    async def _calculate_general_sentiment(self) -> float:
        """Calculate general sentiment score."""
        try:
            accumulation = await self._calculate_whale_accumulation()
            distribution = await self._calculate_whale_distribution()
            growth = await self._calculate_network_growth()
            congestion = await self._calculate_congestion()

            # Sentiment is positive with accumulation, growth, and low congestion
            sentiment = (
                accumulation * 0.3 +
                (1 - distribution) * 0.2 +
                (growth / 100) * 0.25 +
                (1 - congestion / 100) * 0.25
            )
            return max(-1, min(1, sentiment * 2 - 0.5))
        except Exception as e:
            logger.error(f"Error calculating general sentiment: {e}")
            return 0.0

    async def _calculate_bullish_index(self) -> float:
        """Calculate bullish index."""
        try:
            sentiment = await self._calculate_general_sentiment()
            # Convert -1 to 1 scale to 0 to 100
            return max(0, min(100, (sentiment + 1) * 50))
        except Exception as e:
            logger.error(f"Error calculating bullish index: {e}")
            return 50.0

    async def _calculate_overall_score(self) -> float:
        """Calculate overall on-chain score."""
        try:
            health = await self._calculate_network_health()
            growth = await self._calculate_network_growth()
            sentiment = await self._calculate_general_sentiment()

            # Convert sentiment to 0-100 scale
            sentiment_score = (sentiment + 1) * 50

            overall = (
                health * 0.35 +
                max(0, min(100, growth + 50)) * 0.3 +
                sentiment_score * 0.35
            )
            return max(0, min(100, overall))
        except Exception as e:
            logger.error(f"Error calculating overall score: {e}")
            return 50.0

    async def _calculate_investment_index(self) -> float:
        """Calculate investment index."""
        try:
            overall = await self._calculate_overall_score()
            concentration = await self._calculate_whale_concentration()
            velocity = await self._calculate_network_velocity()

            # Higher concentration = lower investment index
            concentration_penalty = concentration * 30

            investment = (
                overall * 0.5 +
                min(100, velocity * 10) * 0.3 -
                concentration_penalty * 0.2
            )
            return max(0, min(100, investment))
        except Exception as e:
            logger.error(f"Error calculating investment index: {e}")
            return 50.0

    # -----------------------------------------------------------------------
    # Metric Access Methods
    # -----------------------------------------------------------------------

    async def get_metric(
        self,
        metric_id: str,
        force_update: bool = False
    ) -> Optional[MetricValue]:
        """Get current value of a metric."""
        if metric_id not in self._metrics:
            logger.warning(f"Unknown metric: {metric_id}")
            return None

        if force_update or metric_id not in self._current_values:
            await self._update_metric(metric_id)

        return self._current_values.get(metric_id)

    async def get_metrics(
        self,
        metric_ids: List[str],
        force_update: bool = False
    ) -> Dict[str, Optional[MetricValue]]:
        """Get current values of multiple metrics."""
        results = {}
        for metric_id in metric_ids:
            results[metric_id] = await self.get_metric(metric_id, force_update)
        return results

    async def get_metrics_by_category(
        self,
        category: MetricCategory,
        force_update: bool = False
    ) -> Dict[str, MetricValue]:
        """Get all metrics in a category."""
        results = {}
        for metric_id, definition in self._metrics.items():
            if definition.category == category:
                value = await self.get_metric(metric_id, force_update)
                if value:
                    results[metric_id] = value
        return results

    def get_historical_values(
        self,
        metric_id: str,
        hours: int = 24,
        limit: Optional[int] = None
    ) -> List[MetricValue]:
        """Get historical values for a metric."""
        if metric_id not in self._metric_history:
            return []

        history = list(self._metric_history[metric_id])
        if hours > 0:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            history = [h for h in history if h.timestamp >= cutoff]

        if limit:
            history = history[-limit:]

        return history

    async def get_snapshot(self) -> MetricSnapshot:
        """Get a snapshot of all current metrics."""
        async with self._lock:
            # Update all metrics
            tasks = []
            for metric_id in self._metrics:
                tasks.append(self._update_metric(metric_id))

            await asyncio.gather(*tasks, return_exceptions=True)

            # Create snapshot
            metrics = self._current_values.copy()
            block = await self.web3_client.get_block('latest')

            # Calculate health and confidence
            health = await self._calculate_network_health()
            confidence = self._calculate_snapshot_confidence(metrics)

            snapshot = MetricSnapshot(
                timestamp=datetime.utcnow(),
                block_number=block.get('number', 0),
                metrics=metrics,
                chain=self.web3_client.chain_name,
                health_score=health,
                confidence_score=confidence,
            )

            self._snapshots.append(snapshot)
            return snapshot

    # -----------------------------------------------------------------------
    # Internal Methods
    # -----------------------------------------------------------------------

    async def _update_metric(self, metric_id: str) -> None:
        """Update a single metric."""
        if metric_id not in self._metrics:
            return

        definition = self._metrics[metric_id]
        start_time = time.time()

        try:
            # Check if dependencies are available
            for dep in definition.dependencies:
                if dep not in self._current_values:
                    await self._update_metric(dep)

            # Calculate metric
            value = await definition.calculation()

            # Validate value
            if definition.min_value is not None and value < definition.min_value:
                value = definition.min_value
            if definition.max_value is not None and value > definition.max_value:
                value = definition.max_value

            # Get block number if available
            block = await self.web3_client.get_block('latest')

            # Create metric value
            metric_value = MetricValue(
                metric_id=metric_id,
                value=float(value),
                timestamp=datetime.utcnow(),
                block_number=block.get('number', 0),
                confidence=self._calculate_confidence(metric_id, value),
            )

            # Store
            self._current_values[metric_id] = metric_value
            self._metric_history[metric_id].append(metric_value)

            # Update performance
            elapsed = (time.time() - start_time) * 1000
            self._performance["calculations"] += 1
            self._performance["avg_calculation_ms"] = (
                (self._performance["avg_calculation_ms"] * (self._performance["calculations"] - 1) + elapsed)
                / self._performance["calculations"]
            )
            self._performance["last_calculation_time"] = datetime.utcnow()

        except Exception as e:
            self._performance["errors"] += 1
            logger.error(f"Error updating metric {metric_id}: {e}")

    def _calculate_confidence(
        self,
        metric_id: str,
        value: float
    ) -> float:
        """Calculate confidence in a metric value."""
        # Base confidence
        confidence = 1.0

        # Reduce confidence if we have no historical data
        if metric_id in self._metric_history and len(self._metric_history[metric_id]) < 10:
            confidence *= 0.8

        # Check for outliers
        if metric_id in self._metric_history and len(self._metric_history[metric_id]) > 0:
            history = [h.value for h in self._metric_history[metric_id]]
            if len(history) > 5:
                mean = np.mean(history[-20:])
                std = np.std(history[-20:])
                if std > 0:
                    deviation = abs(value - mean) / std
                    if deviation > 3:
                        confidence *= 0.5  # Outlier

        # Recent metrics have higher confidence
        if metric_id in self._current_values:
            age = (datetime.utcnow() - self._current_values[metric_id].timestamp).total_seconds()
            if age > 300:  # 5 minutes
                confidence *= 0.9

        return max(0.5, min(1.0, confidence))

    def _calculate_snapshot_confidence(
        self,
        metrics: Dict[str, MetricValue]
    ) -> float:
        """Calculate overall confidence of a snapshot."""
        if not metrics:
            return 0.0

        confidences = [m.confidence for m in metrics.values()]
        return np.mean(confidences)

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    async def refresh_all(self) -> None:
        """Refresh all metrics."""
        async with self._lock:
            tasks = [self._update_metric(metric_id) for metric_id in self._metrics]
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_registered_metrics(self) -> List[str]:
        """Get list of registered metric IDs."""
        return list(self._metrics.keys())

    def get_metric_definition(self, metric_id: str) -> Optional[MetricDefinition]:
        """Get definition of a specific metric."""
        return self._metrics.get(metric_id)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics of the engine."""
        return {
            **self._performance,
            "registered_metrics": len(self._metrics),
            "cached_values": len(self._current_values),
            "historical_stored": sum(len(h) for h in self._metric_history.values()),
            "snapshots_stored": len(self._snapshots),
            "running": self._running,
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the metrics engine."""
        if self._running:
            return

        self._running = True
        await self.refresh_all()
        logger.info("OnChainMetrics started")

    async def stop(self) -> None:
        """Stop the metrics engine."""
        self._running = False
        logger.info("OnChainMetrics stopped")

    def __repr__(self) -> str:
        return f"OnChainMetrics(chain={self.web3_client.chain_name}, metrics={len(self._metrics)})"


# ============================================================================
# Factory Function
# ============================================================================

def create_onchain_metrics(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> OnChainMetrics:
    """Factory function to create an OnChainMetrics instance."""
    return OnChainMetrics(
        web3_client=web3_client,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the metrics engine
    pass

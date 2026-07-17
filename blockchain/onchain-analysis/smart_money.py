# blockchain/onchain-analysis/smart_money.py
# NEXUS AI TRADING SYSTEM - Advanced Smart Money Analysis Engine
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced Smart Money Analysis Engine for tracking and analyzing
sophisticated market participants including institutional investors,
whales, and high-frequency traders. Provides insights into smart money
movements, accumulation patterns, and market positioning.
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
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.date_helpers import parse_timestamp
from shared.utilities.logger import get_logger

logger = get_logger("nexus.onchain.smart_money")


# ============================================================================
# Enums & Constants
# ============================================================================

class SmartMoneyType(str, Enum):
    """Types of smart money entities."""
    INSTITUTIONAL = "institutional"
    WHALE = "whale"
    MARKET_MAKER = "market_maker"
    HIGH_FREQUENCY = "high_frequency"
    VENTURE_CAPITAL = "venture_capital"
    PROTOCOL_TREASURY = "protocol_treasury"
    EXCHANGE = "exchange"
    MINER = "miner"
    STAKER = "staker"
    GOVERNANCE = "governance"


class SmartMoneyAction(str, Enum):
    """Actions performed by smart money."""
    ACCUMULATE = "accumulate"
    DISTRIBUTE = "distribute"
    HODL = "hodl"
    REBALANCE = "rebalance"
    ARBITRAGE = "arbitrage"
    LIQUIDATE = "liquidate"
    STAKE = "stake"
    UNSTAKE = "unstake"
    LEND = "lend"
    BORROW = "borrow"
    SWAP = "swap"
    BRIDGE = "bridge"
    GOVERNANCE_VOTE = "governance_vote"


class SmartMoneyConfidence(str, Enum):
    """Confidence levels for smart money analysis."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CONFIRMED = "confirmed"


@dataclass
class SmartMoneyEntity:
    """Represents a smart money entity."""
    address: str
    entity_type: SmartMoneyType
    name: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    total_transactions: int = 0
    total_volume_usd: float = 0.0
    current_balance_usd: float = 0.0
    portfolio: Dict[str, float] = field(default_factory=dict)
    reputation_score: float = 0.5
    reliability_score: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartMoneyActivity:
    """Records smart money activity."""
    timestamp: datetime
    entity_address: str
    entity_type: SmartMoneyType
    action: SmartMoneyAction
    token: str
    amount: float
    amount_usd: float
    price: float
    source: Optional[str] = None
    destination: Optional[str] = None
    transaction_hash: Optional[str] = None
    confidence: SmartMoneyConfidence = SmartMoneyConfidence.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartMoneyCluster:
    """Cluster of related smart money entities."""
    cluster_id: str
    name: Optional[str] = None
    entities: List[SmartMoneyEntity] = field(default_factory=list)
    total_volume_usd: float = 0.0
    collective_action: Optional[SmartMoneyAction] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartMoneySignal:
    """Trading signal derived from smart money analysis."""
    signal_id: str
    action: SmartMoneyAction
    confidence: float
    token: str
    price: Optional[float] = None
    amount: Optional[float] = None
    entities_involved: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expiration: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Core Smart Money Analyzer
# ============================================================================

class SmartMoneyAnalyzer:
    """
    Advanced Smart Money Analysis Engine.
    Tracks, analyzes, and provides insights on smart money movements.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.config = config or {}

        # Entity tracking
        self._entities: Dict[str, SmartMoneyEntity] = {}
        self._entity_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._activities: deque = deque(maxlen=50000)
        self._clusters: Dict[str, SmartMoneyCluster] = {}

        # Known smart money addresses (will be populated)
        self._known_addresses: Dict[str, SmartMoneyEntity] = {}

        # State management
        self._running = False
        self._lock = asyncio.Lock()
        self._signals: List[SmartMoneySignal] = []

        # Performance metrics
        self._performance = {
            "entities_tracked": 0,
            "activities_processed": 0,
            "clusters_identified": 0,
            "signals_generated": 0,
            "avg_processing_time_ms": 0.0,
            "false_positives": 0,
            "accuracy": 0.0,
        }

        # Load known smart money addresses
        self._load_known_addresses()

        # Callbacks
        self._activity_callbacks: List[Callable] = []
        self._signal_callbacks: List[Callable] = []

        logger.info(
            "SmartMoneyAnalyzer initialized",
            extra={
                "chain": web3_client.chain_name,
                "known_addresses": len(self._known_addresses),
            }
        )

    # -----------------------------------------------------------------------
    # Entity Management
    # -----------------------------------------------------------------------

    def add_known_entity(
        self,
        address: str,
        entity_type: SmartMoneyType,
        name: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> None:
        """Add a known smart money entity."""
        entity = SmartMoneyEntity(
            address=address,
            entity_type=entity_type,
            name=name,
            labels=labels or [],
            first_seen=datetime.utcnow(),
        )
        self._known_addresses[address.lower()] = entity
        self._entities[address.lower()] = entity

        logger.info(
            f"Added known entity: {address}",
            extra={"type": entity_type.value, "name": name}
        )

    def get_entity(self, address: str) -> Optional[SmartMoneyEntity]:
        """Get entity by address."""
        return self._entities.get(address.lower())

    def get_entities_by_type(
        self,
        entity_type: SmartMoneyType
    ) -> List[SmartMoneyEntity]:
        """Get all entities of a specific type."""
        return [
            e for e in self._entities.values()
            if e.entity_type == entity_type
        ]

    def update_entity(
        self,
        address: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update an entity's information."""
        address = address.lower()
        if address not in self._entities:
            return False

        entity = self._entities[address]
        for key, value in updates.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        self._entities[address] = entity
        return True

    # -----------------------------------------------------------------------
    # Activity Tracking
    # -----------------------------------------------------------------------

    async def process_transaction(
        self,
        tx_data: Dict[str, Any]
    ) -> Optional[SmartMoneyActivity]:
        """Process a transaction to detect smart money activity."""
        start_time = time.time()

        try:
            # Extract basic transaction info
            from_addr = tx_data.get("from", "").lower()
            to_addr = tx_data.get("to", "").lower()

            # Check if either address is known smart money
            entity = None
            if from_addr in self._entities:
                entity = self._entities[from_addr]
            elif to_addr in self._entities:
                entity = self._entities[to_addr]

            if not entity:
                return None

            # Determine action
            action = self._determine_action(tx_data, entity)
            if not action:
                return None

            # Calculate amount and value
            amount = tx_data.get("value", 0)
            amount_usd = self._calculate_value_usd(amount, tx_data.get("token", "ETH"))
            price = tx_data.get("price", 0) or self._get_price(tx_data.get("token", "ETH"))

            # Create activity record
            activity = SmartMoneyActivity(
                timestamp=datetime.utcnow(),
                entity_address=entity.address,
                entity_type=entity.entity_type,
                action=action,
                token=tx_data.get("token", "ETH"),
                amount=amount,
                amount_usd=amount_usd,
                price=price,
                source=from_addr,
                destination=to_addr,
                transaction_hash=tx_data.get("hash"),
                confidence=self._calculate_confidence(tx_data, entity),
                metadata={
                    "gas_price": tx_data.get("gas_price"),
                    "gas_used": tx_data.get("gas_used"),
                    "block_number": tx_data.get("block_number"),
                },
            )

            # Store activity
            async with self._lock:
                self._activities.append(activity)
                self._entity_history[entity.address].append(activity)

                # Update entity stats
                entity.total_transactions += 1
                entity.total_volume_usd += amount_usd
                entity.last_seen = activity.timestamp

            # Update performance
            self._performance["activities_processed"] += 1
            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["avg_processing_time_ms"] = (
                (self._performance["avg_processing_time_ms"] *
                 (self._performance["activities_processed"] - 1) +
                 elapsed_ms) / self._performance["activities_processed"]
            )

            # Execute callbacks
            await self._execute_callbacks(activity)

            # Check for signal generation
            signal = await self._generate_signal_from_activity(activity)
            if signal:
                self._signals.append(signal)
                self._performance["signals_generated"] += 1
                await self._execute_signal_callbacks(signal)

            return activity

        except Exception as e:
            logger.error(f"Error processing transaction: {e}", exc_info=True)
            return None

    def _determine_action(
        self,
        tx_data: Dict[str, Any],
        entity: SmartMoneyEntity
    ) -> Optional[SmartMoneyAction]:
        """Determine the action from transaction data."""
        # Analyze transaction patterns
        from_addr = tx_data.get("from", "").lower()
        to_addr = tx_data.get("to", "").lower()

        # Check if it's to/from exchange
        if self._is_exchange_address(to_addr):
            return SmartMoneyAction.DISTRIBUTE
        elif self._is_exchange_address(from_addr):
            return SmartMoneyAction.ACCUMULATE

        # Check for DeFi interactions
        if self._is_defi_protocol(to_addr):
            method = tx_data.get("method", "")
            if "stake" in method.lower():
                return SmartMoneyAction.STAKE
            elif "unstake" in method.lower():
                return SmartMoneyAction.UNSTAKE
            elif "lend" in method.lower():
                return SmartMoneyAction.LEND
            elif "borrow" in method.lower():
                return SmartMoneyAction.BORROW

        # Check for swaps
        if self._is_dex(to_addr) or self._is_aggregator(to_addr):
            return SmartMoneyAction.SWAP

        # Check for bridging
        if self._is_bridge(to_addr):
            return SmartMoneyAction.BRIDGE

        # Default to accumulation if large amount
        amount = tx_data.get("value", 0)
        if amount > 1000000000000000000:  # > 1 ETH
            return SmartMoneyAction.ACCUMULATE

        return None

    def _is_exchange_address(self, address: str) -> bool:
        """Check if address belongs to an exchange."""
        # Would be replaced with actual exchange address list
        exchange_prefixes = ["0xexchange", "0xbinance", "0xcoinbase", "0xkraken"]
        return any(address.startswith(prefix) for prefix in exchange_prefixes)

    def _is_defi_protocol(self, address: str) -> bool:
        """Check if address belongs to a DeFi protocol."""
        # Would be replaced with actual protocol address list
        defi_prefixes = ["0xaave", "0xcompound", "0xmaker", "0xuniswap"]
        return any(address.startswith(prefix) for prefix in defi_prefixes)

    def _is_dex(self, address: str) -> bool:
        """Check if address belongs to a DEX."""
        dex_prefixes = ["0xuniswap", "0xcurve", "0xbalancer", "0x1inch"]
        return any(address.startswith(prefix) for prefix in dex_prefixes)

    def _is_aggregator(self, address: str) -> bool:
        """Check if address belongs to an aggregator."""
        aggregator_prefixes = ["0x1inch", "0xparaswap", "0x0x"]
        return any(address.startswith(prefix) for prefix in aggregator_prefixes)

    def _is_bridge(self, address: str) -> bool:
        """Check if address belongs to a bridge."""
        bridge_prefixes = ["0xbridge", "0xwormhole", "0xaxelar"]
        return any(address.startswith(prefix) for prefix in bridge_prefixes)

    def _calculate_confidence(
        self,
        tx_data: Dict[str, Any],
        entity: SmartMoneyEntity
    ) -> SmartMoneyConfidence:
        """Calculate confidence in the activity detection."""
        # Base confidence from entity reliability
        confidence_value = entity.reliability_score

        # Adjust based on transaction size
        amount = tx_data.get("value", 0)
        if amount > 10000000000000000000:  # > 10 ETH
            confidence_value += 0.2
        elif amount > 1000000000000000000:  # > 1 ETH
            confidence_value += 0.1

        # Adjust based on gas price (higher gas = more urgent = higher confidence)
        gas_price = tx_data.get("gas_price", 0)
        if gas_price > 100000000000:  # > 100 gwei
            confidence_value += 0.1

        # Cap and convert to enum
        confidence_value = min(1.0, max(0.0, confidence_value))

        if confidence_value >= 0.9:
            return SmartMoneyConfidence.CONFIRMED
        elif confidence_value >= 0.8:
            return SmartMoneyConfidence.VERY_HIGH
        elif confidence_value >= 0.65:
            return SmartMoneyConfidence.HIGH
        elif confidence_value >= 0.5:
            return SmartMoneyConfidence.MEDIUM
        elif confidence_value >= 0.35:
            return SmartMoneyConfidence.LOW
        else:
            return SmartMoneyConfidence.VERY_LOW

    def _calculate_value_usd(self, amount: float, token: str) -> float:
        """Calculate USD value of an amount."""
        # Would use price oracle in production
        price = self._get_price(token)
        return amount * price if price else 0.0

    def _get_price(self, token: str) -> float:
        """Get current price of a token."""
        # Would use price feed in production
        prices = {
            "ETH": 3500.0,
            "BTC": 65000.0,
            "USDC": 1.0,
            "USDT": 1.0,
            "DAI": 1.0,
        }
        return prices.get(token, 0.0)

    # -----------------------------------------------------------------------
    # Cluster Analysis
    # -----------------------------------------------------------------------

    async def identify_clusters(self) -> List[SmartMoneyCluster]:
        """Identify clusters of related smart money entities."""
        clusters = []
        processed = set()

        for address, entity in self._entities.items():
            if address in processed:
                continue

            # Find related entities
            cluster = await self._find_related_entities(entity)
            if len(cluster) >= 2:
                cluster_id = f"cluster_{len(clusters)}_{int(time.time())}"
                cluster_obj = SmartMoneyCluster(
                    cluster_id=cluster_id,
                    entities=cluster,
                    total_volume_usd=sum(e.total_volume_usd for e in cluster),
                    collective_action=self._determine_collective_action(cluster),
                    confidence=self._calculate_cluster_confidence(cluster),
                )
                clusters.append(cluster_obj)

                # Mark entities as processed
                for e in cluster:
                    processed.add(e.address)

        self._clusters = {c.cluster_id: c for c in clusters}
        self._performance["clusters_identified"] = len(clusters)

        return clusters

    async def _find_related_entities(
        self,
        entity: SmartMoneyEntity
    ) -> List[SmartMoneyEntity]:
        """Find entities related to a given entity."""
        related = [entity]
        threshold = 0.7  # Similarity threshold

        # Get entity's transaction history
        if entity.address in self._entity_history:
            activities = list(self._entity_history[entity.address])

            # Find other entities with similar activity patterns
            for other_address, other_entity in self._entities.items():
                if other_address == entity.address:
                    continue

                if other_address in self._entity_history:
                    other_activities = list(self._entity_history[other_address])
                    similarity = self._calculate_similarity(activities, other_activities)
                    if similarity >= threshold:
                        related.append(other_entity)

        return related

    def _calculate_similarity(
        self,
        activities1: List[SmartMoneyActivity],
        activities2: List[SmartMoneyActivity]
    ) -> float:
        """Calculate similarity between two sets of activities."""
        if not activities1 or not activities2:
            return 0.0

        # Calculate Jaccard similarity of tokens
        tokens1 = {a.token for a in activities1}
        tokens2 = {a.token for a in activities2}
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        if union == 0:
            return 0.0

        token_similarity = intersection / union

        # Calculate action similarity
        actions1 = {a.action for a in activities1}
        actions2 = {a.action for a in activities2}
        action_intersection = len(actions1 & actions2)
        action_union = len(actions1 | actions2)
        action_similarity = action_intersection / action_union if action_union > 0 else 0.0

        return (token_similarity * 0.6 + action_similarity * 0.4)

    def _determine_collective_action(
        self,
        entities: List[SmartMoneyEntity]
    ) -> Optional[SmartMoneyAction]:
        """Determine the collective action of a cluster."""
        actions = []
        for entity in entities:
            if entity.address in self._entity_history:
                last_activity = list(self._entity_history[entity.address])[-1] if self._entity_history[entity.address] else None
                if last_activity:
                    actions.append(last_activity.action)

        if not actions:
            return None

        # Find most common action
        from collections import Counter
        action_counts = Counter(actions)
        most_common = action_counts.most_common(1)

        if most_common:
            action, count = most_common[0]
            if count / len(actions) >= 0.6:  # 60% consensus
                return action

        return None

    def _calculate_cluster_confidence(self, entities: List[SmartMoneyEntity]) -> float:
        """Calculate confidence in a cluster."""
        if not entities:
            return 0.0

        # Average reliability
        avg_reliability = sum(e.reliability_score for e in entities) / len(entities)

        # Number of entities (more = higher confidence)
        size_factor = min(1.0, len(entities) / 5)

        return avg_reliability * 0.7 + size_factor * 0.3

    # -----------------------------------------------------------------------
    # Signal Generation
    # -----------------------------------------------------------------------

    async def _generate_signal_from_activity(
        self,
        activity: SmartMoneyActivity
    ) -> Optional[SmartMoneySignal]:
        """Generate a trading signal from an activity."""
        # Only generate signals for high confidence activities
        if activity.confidence in [SmartMoneyConfidence.LOW, SmartMoneyConfidence.VERY_LOW]:
            return None

        # Determine signal
        signal_id = f"smart_money_{int(time.time())}_{activity.entity_address[:8]}"

        # Check if this is a significant action
        if activity.action == SmartMoneyAction.ACCUMULATE:
            if activity.amount_usd > 100000:  # > $100k
                return SmartMoneySignal(
                    signal_id=signal_id,
                    action=SmartMoneyAction.ACCUMULATE,
                    confidence=self._confidence_to_float(activity.confidence),
                    token=activity.token,
                    price=activity.price,
                    amount=activity.amount,
                    entities_involved=[activity.entity_address],
                    metadata={
                        "action": "accumulate",
                        "strength": "strong" if activity.amount_usd > 500000 else "moderate",
                        "reason": f"Smart money accumulation of {activity.amount:.2f} {activity.token}",
                    }
                )

        elif activity.action == SmartMoneyAction.DISTRIBUTE:
            if activity.amount_usd > 100000:
                return SmartMoneySignal(
                    signal_id=signal_id,
                    action=SmartMoneyAction.DISTRIBUTE,
                    confidence=self._confidence_to_float(activity.confidence),
                    token=activity.token,
                    price=activity.price,
                    amount=activity.amount,
                    entities_involved=[activity.entity_address],
                    metadata={
                        "action": "distribute",
                        "strength": "strong" if activity.amount_usd > 500000 else "moderate",
                        "reason": f"Smart money distribution of {activity.amount:.2f} {activity.token}",
                    }
                )

        # Follow the smart money - if they stake, consider bullish
        elif activity.action == SmartMoneyAction.STAKE:
            if activity.amount_usd > 50000:
                return SmartMoneySignal(
                    signal_id=signal_id,
                    action=SmartMoneyAction.STAKE,
                    confidence=self._confidence_to_float(activity.confidence),
                    token=activity.token,
                    price=activity.price,
                    amount=activity.amount,
                    entities_involved=[activity.entity_address],
                    metadata={
                        "action": "stake",
                        "strength": "moderate",
                        "reason": f"Smart money staking {activity.amount:.2f} {activity.token}",
                    }
                )

        return None

    def _confidence_to_float(self, confidence: SmartMoneyConfidence) -> float:
        """Convert confidence enum to float."""
        mapping = {
            SmartMoneyConfidence.VERY_LOW: 0.1,
            SmartMoneyConfidence.LOW: 0.25,
            SmartMoneyConfidence.MEDIUM: 0.5,
            SmartMoneyConfidence.HIGH: 0.75,
            SmartMoneyConfidence.VERY_HIGH: 0.9,
            SmartMoneyConfidence.CONFIRMED: 0.98,
        }
        return mapping.get(confidence, 0.5)

    # -----------------------------------------------------------------------
    # Analysis Methods
    # -----------------------------------------------------------------------

    async def get_smart_money_sentiment(
        self,
        token: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get smart money sentiment for a token."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Filter activities
        activities = [
            a for a in self._activities
            if a.timestamp >= cutoff
            and (not token or a.token == token)
        ]

        if not activities:
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "activities": 0,
                "confidence": 0.0,
            }

        # Calculate sentiment
        buy_activities = [a for a in activities if a.action == SmartMoneyAction.ACCUMULATE]
        sell_activities = [a for a in activities if a.action == SmartMoneyAction.DISTRIBUTE]

        buy_volume = sum(a.amount_usd for a in buy_activities)
        sell_volume = sum(a.amount_usd for a in sell_activities)

        total_volume = buy_volume + sell_volume
        if total_volume == 0:
            sentiment_score = 0.0
        else:
            sentiment_score = (buy_volume - sell_volume) / total_volume

        # Determine sentiment label
        if sentiment_score > 0.3:
            sentiment = "bullish"
        elif sentiment_score < -0.3:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        # Calculate confidence
        confidence = min(1.0, len(activities) / 100) * 0.8

        return {
            "sentiment": sentiment,
            "score": sentiment_score,
            "activities": len(activities),
            "buy_activities": len(buy_activities),
            "sell_activities": len(sell_activities),
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "confidence": confidence,
            "top_entities": self._get_top_entities(activities, limit=5),
        }

    def _get_top_entities(
        self,
        activities: List[SmartMoneyActivity],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top entities from activities."""
        entity_volume = defaultdict(float)
        for activity in activities:
            entity_volume[activity.entity_address] += activity.amount_usd

        top_entities = sorted(
            entity_volume.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {
                "address": addr,
                "volume_usd": volume,
                "entity": self._entities.get(addr).__dict__ if addr in self._entities else None,
            }
            for addr, volume in top_entities
        ]

    async def get_accumulation_pattern(
        self,
        token: str,
        hours: int = 48
    ) -> Dict[str, Any]:
        """Detect accumulation patterns for a token."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        activities = [
            a for a in self._activities
            if a.timestamp >= cutoff
            and a.token == token
            and a.action in [SmartMoneyAction.ACCUMULATE, SmartMoneyAction.DISTRIBUTE]
        ]

        if not activities:
            return {
                "detected": False,
                "pattern": "none",
                "confidence": 0.0,
            }

        # Analyze time series
        df = pd.DataFrame([
            {
                "timestamp": a.timestamp,
                "amount_usd": a.amount_usd,
                "action": a.action.value,
            }
            for a in activities
        ])

        df = df.sort_values("timestamp")

        # Check for acceleration
        if len(df) >= 10:
            df["cumulative"] = df.apply(
                lambda row: row["amount_usd"] if row["action"] == "accumulate" else -row["amount_usd"],
                axis=1
            ).cumsum()

            # Check if cumulative sum is increasing
            if len(df) >= 5:
                recent = df.tail(5)["cumulative"].values
                if len(recent) >= 2:
                    increasing = all(recent[i] <= recent[i+1] for i in range(len(recent)-1))
                    if increasing:
                        return {
                            "detected": True,
                            "pattern": "accelerating_accumulation",
                            "confidence": min(1.0, len(activities) / 50),
                            "cumulative_volume": df["cumulative"].iloc[-1],
                            "entity_count": len(set(a.entity_address for a in activities)),
                        }

        # Check for consistent accumulation
        accumulation_count = sum(1 for a in activities if a.action == SmartMoneyAction.ACCUMULATE)
        distribution_count = sum(1 for a in activities if a.action == SmartMoneyAction.DISTRIBUTE)

        if accumulation_count > distribution_count * 2:
            return {
                "detected": True,
                "pattern": "consistent_accumulation",
                "confidence": min(1.0, accumulation_count / 20),
                "accumulation_count": accumulation_count,
                "distribution_count": distribution_count,
                "entity_count": len(set(a.entity_address for a in activities)),
            }

        return {
            "detected": False,
            "pattern": "none",
            "confidence": 0.0,
        }

    async def get_smart_money_flow(
        self,
        token: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get smart money flow analysis."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        activities = [
            a for a in self._activities
            if a.timestamp >= cutoff
            and (not token or a.token == token)
        ]

        if not activities:
            return {
                "inflow": 0.0,
                "outflow": 0.0,
                "net_flow": 0.0,
                "entities": 0,
                "confidence": 0.0,
            }

        inflow = sum(a.amount_usd for a in activities if a.action == SmartMoneyAction.ACCUMULATE)
        outflow = sum(a.amount_usd for a in activities if a.action == SmartMoneyAction.DISTRIBUTE)
        net_flow = inflow - outflow

        entities = len(set(a.entity_address for a in activities))

        return {
            "inflow": inflow,
            "outflow": outflow,
            "net_flow": net_flow,
            "entities": entities,
            "confidence": min(1.0, len(activities) / 100),
            "top_entities": self._get_top_entities(activities, limit=5),
        }

    # -----------------------------------------------------------------------
    # Known Addresses Loading
    # -----------------------------------------------------------------------

    def _load_known_addresses(self) -> None:
        """Load known smart money addresses."""
        # In production, this would load from a database or configuration file
        # These are placeholder examples

        known = {
            # Institutional addresses
            "0x123...": {
                "type": SmartMoneyType.INSTITUTIONAL,
                "name": "Example Institution",
                "labels": ["institutional", "large_cap"],
            },
            # Whale addresses
            "0x456...": {
                "type": SmartMoneyType.WHALE,
                "name": "Example Whale",
                "labels": ["whale", "early_adopter"],
            },
            # Market maker addresses
            "0x789...": {
                "type": SmartMoneyType.MARKET_MAKER,
                "name": "Example Market Maker",
                "labels": ["market_maker", "high_frequency"],
            },
        }

        for address, info in known.items():
            self.add_known_entity(
                address=address,
                entity_type=info["type"],
                name=info.get("name"),
                labels=info.get("labels", []),
            )

    # -----------------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------------

    def register_activity_callback(self, callback: Callable) -> None:
        """Register a callback for new activities."""
        self._activity_callbacks.append(callback)

    def register_signal_callback(self, callback: Callable) -> None:
        """Register a callback for new signals."""
        self._signal_callbacks.append(callback)

    async def _execute_callbacks(self, activity: SmartMoneyActivity) -> None:
        """Execute activity callbacks."""
        for callback in self._activity_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(activity)
                else:
                    callback(activity)
            except Exception as e:
                logger.error(f"Error in activity callback: {e}")

    async def _execute_signal_callbacks(self, signal: SmartMoneySignal) -> None:
        """Execute signal callbacks."""
        for callback in self._signal_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                logger.error(f"Error in signal callback: {e}")

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_entity_activity(
        self,
        address: str,
        hours: int = 24
    ) -> List[SmartMoneyActivity]:
        """Get activity for a specific entity."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            a for a in self._activities
            if a.entity_address == address.lower()
            and a.timestamp >= cutoff
        ]

    def get_token_activities(
        self,
        token: str,
        hours: int = 24
    ) -> List[SmartMoneyActivity]:
        """Get activities for a specific token."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            a for a in self._activities
            if a.token == token
            and a.timestamp >= cutoff
        ]

    def get_recent_signals(
        self,
        hours: int = 24,
        min_confidence: float = 0.5
    ) -> List[SmartMoneySignal]:
        """Get recent signals."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            s for s in self._signals
            if s.timestamp >= cutoff
            and s.confidence >= min_confidence
        ]

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "active_entities": len(self._entities),
            "total_activities": len(self._activities),
            "total_signals": len(self._signals),
            "clusters": len(self._clusters),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the analyzer."""
        if self._running:
            return

        self._running = True

        # Start background tasks
        asyncio.create_task(self._periodic_analysis())

        logger.info("SmartMoneyAnalyzer started")

    async def stop(self) -> None:
        """Stop the analyzer."""
        self._running = False
        logger.info("SmartMoneyAnalyzer stopped")

    async def _periodic_analysis(self) -> None:
        """Perform periodic analysis."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour

                # Identify new clusters
                await self.identify_clusters()

                # Analyze accumulation patterns for tracked tokens
                tokens = set()
                for activity in self._activities:
                    tokens.add(activity.token)

                for token in tokens:
                    await self.get_accumulation_pattern(token)

            except Exception as e:
                logger.error(f"Error in periodic analysis: {e}")


# ============================================================================
# Factory Function
# ============================================================================

def create_smart_money_analyzer(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> SmartMoneyAnalyzer:
    """Factory function to create a SmartMoneyAnalyzer instance."""
    return SmartMoneyAnalyzer(
        web3_client=web3_client,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the smart money analyzer
    pass

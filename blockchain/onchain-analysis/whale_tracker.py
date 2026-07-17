# blockchain/onchain-analysis/whale_tracker.py
# NEXUS AI TRADING SYSTEM - Advanced Whale Tracking Engine
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced whale tracking engine for monitoring large holders and their movements.
Detects whale accumulation, distribution, and provides early warning signals
for significant market moves.
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
from web3 import Web3

# NEXUS Imports
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.date_helpers import parse_timestamp
from shared.utilities.logger import get_logger

logger = get_logger("nexus.onchain.whale_tracker")


# ============================================================================
# Enums & Constants
# ============================================================================

class WhaleType(str, Enum):
    """Types of whales."""
    INSTITUTIONAL = "institutional"
    EXCHANGE = "exchange"
    EARLY_ADOPTER = "early_adopter"
    MINER = "miner"
    STAKER = "staker"
    TREASURY = "treasury"
    VENTURE_CAPITAL = "venture_capital"
    MARKET_MAKER = "market_maker"
    PROTOCOL = "protocol"
    MYSTERY = "mystery"


class WhaleAction(str, Enum):
    """Actions performed by whales."""
    BUY = "buy"
    SELL = "sell"
    TRANSFER = "transfer"
    STAKE = "stake"
    UNSTAKE = "unstake"
    LEND = "lend"
    BORROW = "borrow"
    SWAP = "swap"
    BRIDGE = "bridge"
    HODL = "hodl"
    ACCUMULATE = "accumulate"
    DISTRIBUTE = "distribute"


class WhaleConfidence(str, Enum):
    """Confidence in whale detection."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CONFIRMED = "confirmed"


@dataclass
class Whale:
    """Represents a whale entity."""
    address: str
    whale_type: WhaleType
    name: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    total_transactions: int = 0
    total_volume_usd: float = 0.0
    current_balance: float = 0.0
    current_balance_usd: float = 0.0
    portfolio: Dict[str, float] = field(default_factory=dict)  # token -> balance
    portfolio_usd: Dict[str, float] = field(default_factory=dict)  # token -> usd value
    historical_balances: deque = field(default_factory=lambda: deque(maxlen=1000))
    reputation_score: float = 0.5
    confidence: WhaleConfidence = WhaleConfidence.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WhaleTransaction:
    """Records a whale transaction."""
    timestamp: datetime
    whale_address: str
    token: str
    amount: float
    amount_usd: float
    price: float
    action: WhaleAction
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None
    confidence: WhaleConfidence = WhaleConfidence.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WhaleAlert:
    """Alert generated from whale activity."""
    alert_id: str
    whale_address: str
    whale_type: WhaleType
    action: WhaleAction
    token: str
    amount: float
    amount_usd: float
    severity: str  # "low", "medium", "high", "critical"
    confidence: WhaleConfidence
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WhaleCluster:
    """Cluster of related whales."""
    cluster_id: str
    name: Optional[str] = None
    whales: List[Whale] = field(default_factory=list)
    combined_balance_usd: float = 0.0
    collective_action: Optional[WhaleAction] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Core Whale Tracker
# ============================================================================

class WhaleTracker:
    """
    Advanced whale tracking engine for monitoring large holders.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.config = config or {}

        # Whale storage
        self._whales: Dict[str, Whale] = {}
        self._whale_transactions: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._alerts: List[WhaleAlert] = []
        self._clusters: Dict[str, WhaleCluster] = {}

        # Configuration thresholds
        self._whale_threshold_usd = self.config.get("whale_threshold_usd", 1_000_000)
        self._min_whale_balance_usd = self.config.get("min_whale_balance_usd", 500_000)
        self._significant_move_threshold = self.config.get("significant_move_threshold", 0.1)  # 10% of balance

        # State management
        self._running = False
        self._lock = asyncio.Lock()
        self._known_whales: Set[str] = set()

        # Performance metrics
        self._performance = {
            "whales_tracked": 0,
            "transactions_processed": 0,
            "alerts_generated": 0,
            "clusters_identified": 0,
            "avg_processing_time_ms": 0.0,
        }

        # Known whale addresses (will be populated)
        self._load_known_whales()

        # Callbacks
        self._whale_callbacks: List[Callable] = []
        self._alert_callbacks: List[Callable] = []

        logger.info(
            "WhaleTracker initialized",
            extra={
                "chain": web3_client.chain_name,
                "known_whales": len(self._known_whales),
                "threshold_usd": self._whale_threshold_usd,
            }
        )

    # -----------------------------------------------------------------------
    # Whale Management
    # -----------------------------------------------------------------------

    def add_whale(
        self,
        address: str,
        whale_type: WhaleType,
        name: Optional[str] = None,
        labels: Optional[List[str]] = None,
        initial_balance: float = 0.0,
    ) -> Whale:
        """Add a new whale to track."""
        address = Web3.to_checksum_address(address)

        whale = Whale(
            address=address,
            whale_type=whale_type,
            name=name,
            labels=labels or [],
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            current_balance=initial_balance,
            reputation_score=0.7 if whale_type == WhaleType.INSTITUTIONAL else 0.5,
            confidence=WhaleConfidence.HIGH if name else WhaleConfidence.MEDIUM,
        )

        self._whales[address] = whale
        self._known_whales.add(address)
        self._performance["whales_tracked"] += 1

        logger.info(
            f"Added whale: {address}",
            extra={"type": whale_type.value, "name": name}
        )

        return whale

    def remove_whale(self, address: str) -> bool:
        """Remove a whale from tracking."""
        address = Web3.to_checksum_address(address)
        if address in self._whales:
            del self._whales[address]
            self._known_whales.discard(address)
            logger.info(f"Removed whale: {address}")
            return True
        return False

    def get_whale(self, address: str) -> Optional[Whale]:
        """Get whale by address."""
        address = Web3.to_checksum_address(address)
        return self._whales.get(address)

    def get_all_whales(self) -> List[Whale]:
        """Get all tracked whales."""
        return list(self._whales.values())

    def get_whales_by_type(self, whale_type: WhaleType) -> List[Whale]:
        """Get whales by type."""
        return [w for w in self._whales.values() if w.whale_type == whale_type]

    async def update_whale_balance(
        self,
        address: str,
        token: str,
        balance: float,
        price: Optional[float] = None,
    ) -> Optional[Whale]:
        """Update a whale's balance."""
        address = Web3.to_checksum_address(address)
        whale = self._whales.get(address)

        if not whale:
            return None

        # Store historical balance
        whale.historical_balances.append({
            "timestamp": datetime.utcnow(),
            "token": token,
            "balance": balance,
            "price": price,
        })

        # Update current balance
        if token in whale.portfolio:
            old_balance = whale.portfolio[token]
            whale.portfolio[token] = balance

            # Check for significant moves
            if old_balance > 0:
                change = abs(balance - old_balance) / old_balance
                if change > self._significant_move_threshold:
                    await self._handle_significant_move(whale, token, old_balance, balance, price)

        else:
            whale.portfolio[token] = balance

        # Update USD value
        if price:
            whale.portfolio_usd[token] = balance * price
            whale.current_balance_usd = sum(whale.portfolio_usd.values())

        whale.last_seen = datetime.utcnow()
        whale.total_transactions += 1

        return whale

    # -----------------------------------------------------------------------
    # Transaction Processing
    # -----------------------------------------------------------------------

    async def process_transaction(
        self,
        tx_data: Dict[str, Any]
    ) -> Optional[WhaleTransaction]:
        """Process a transaction to detect whale activity."""
        start_time = time.time()

        try:
            from_addr = Web3.to_checksum_address(tx_data.get("from", ""))
            to_addr = Web3.to_checksum_address(tx_data.get("to", ""))

            # Check if transaction involves known whales
            whale_addr = None
            if from_addr in self._whales:
                whale_addr = from_addr
            elif to_addr in self._whales:
                whale_addr = to_addr

            if not whale_addr:
                return None

            whale = self._whales[whale_addr]
            amount = float(tx_data.get("value", 0))
            token = tx_data.get("token", "ETH")
            price = tx_data.get("price", 0) or self._get_price(token)
            amount_usd = amount * price if price else 0

            # Check if this is a significant transaction
            if amount_usd < self._min_whale_balance_usd:
                return None

            # Determine action
            action = self._determine_action(tx_data, whale_addr, from_addr, to_addr)

            # Create transaction record
            whale_tx = WhaleTransaction(
                timestamp=datetime.utcnow(),
                whale_address=whale_addr,
                token=token,
                amount=amount,
                amount_usd=amount_usd,
                price=price,
                action=action,
                from_address=from_addr,
                to_address=to_addr,
                transaction_hash=tx_data.get("hash"),
                block_number=tx_data.get("block_number"),
                confidence=self._calculate_confidence(tx_data, whale),
                metadata={
                    "gas_price": tx_data.get("gas_price"),
                    "gas_used": tx_data.get("gas_used"),
                }
            )

            # Store transaction
            self._whale_transactions[whale_addr].append(whale_tx)

            # Update whale stats
            whale.total_volume_usd += amount_usd
            whale.total_transactions += 1
            whale.last_seen = whale_tx.timestamp

            # Check for alerts
            await self._check_alert_conditions(whale, whale_tx)

            # Update performance
            self._performance["transactions_processed"] += 1
            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["avg_processing_time_ms"] = (
                (self._performance["avg_processing_time_ms"] *
                 (self._performance["transactions_processed"] - 1) +
                 elapsed_ms) / self._performance["transactions_processed"]
            )

            # Execute callbacks
            await self._execute_whale_callbacks(whale_tx)

            return whale_tx

        except Exception as e:
            logger.error(f"Error processing whale transaction: {e}", exc_info=True)
            return None

    def _determine_action(
        self,
        tx_data: Dict[str, Any],
        whale_addr: str,
        from_addr: str,
        to_addr: str
    ) -> WhaleAction:
        """Determine the action type."""
        if whale_addr == from_addr:
            if self._is_exchange_address(to_addr):
                return WhaleAction.SELL
            elif self._is_defi_protocol(to_addr):
                method = tx_data.get("method", "")
                if "stake" in method.lower():
                    return WhaleAction.STAKE
                elif "lend" in method.lower():
                    return WhaleAction.LEND
            elif self._is_bridge(to_addr):
                return WhaleAction.BRIDGE
            return WhaleAction.TRANSFER
        else:
            if self._is_exchange_address(from_addr):
                return WhaleAction.BUY
            elif self._is_defi_protocol(from_addr):
                method = tx_data.get("method", "")
                if "unstake" in method.lower():
                    return WhaleAction.UNSTAKE
                elif "borrow" in method.lower():
                    return WhaleAction.BORROW
            return WhaleAction.TRANSFER

    def _is_exchange_address(self, address: str) -> bool:
        """Check if address belongs to an exchange."""
        # Would be replaced with actual exchange address list
        exchange_prefixes = ["0xexchange", "0xbinance", "0xcoinbase", "0xkraken", "0xbybit", "0xokx"]
        return any(address.startswith(prefix) for prefix in exchange_prefixes)

    def _is_defi_protocol(self, address: str) -> bool:
        """Check if address belongs to a DeFi protocol."""
        defi_prefixes = ["0xaave", "0xcompound", "0xmaker", "0xuniswap", "0xcurve", "0xbalancer"]
        return any(address.startswith(prefix) for prefix in defi_prefixes)

    def _is_bridge(self, address: str) -> bool:
        """Check if address belongs to a bridge."""
        bridge_prefixes = ["0xbridge", "0xwormhole", "0xaxelar", "0xacross"]
        return any(address.startswith(prefix) for prefix in bridge_prefixes)

    def _calculate_confidence(
        self,
        tx_data: Dict[str, Any],
        whale: Whale
    ) -> WhaleConfidence:
        """Calculate confidence in the transaction detection."""
        confidence_value = whale.reputation_score

        # Increase confidence for large amounts
        amount = float(tx_data.get("value", 0))
        amount_usd = amount * self._get_price(tx_data.get("token", "ETH"))
        if amount_usd > 10_000_000:
            confidence_value += 0.2
        elif amount_usd > 5_000_000:
            confidence_value += 0.1

        # Known whale increases confidence
        if whale.name:
            confidence_value += 0.1

        confidence_value = min(1.0, max(0.0, confidence_value))

        if confidence_value >= 0.9:
            return WhaleConfidence.CONFIRMED
        elif confidence_value >= 0.8:
            return WhaleConfidence.VERY_HIGH
        elif confidence_value >= 0.65:
            return WhaleConfidence.HIGH
        elif confidence_value >= 0.5:
            return WhaleConfidence.MEDIUM
        elif confidence_value >= 0.35:
            return WhaleConfidence.LOW
        else:
            return WhaleConfidence.VERY_LOW

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
    # Whale Alert System
    # -----------------------------------------------------------------------

    async def _check_alert_conditions(
        self,
        whale: Whale,
        transaction: WhaleTransaction
    ) -> None:
        """Check if transaction triggers an alert."""
        alerts = []

        # Large transaction alert
        if transaction.amount_usd > 10_000_000:
            alerts.append(self._create_alert(
                whale=whale,
                transaction=transaction,
                severity="critical",
                message=f"Massive whale movement: {transaction.amount:.2f} {transaction.token} (${transaction.amount_usd:,.0f})",
            ))
        elif transaction.amount_usd > 5_000_000:
            alerts.append(self._create_alert(
                whale=whale,
                transaction=transaction,
                severity="high",
                message=f"Large whale movement: {transaction.amount:.2f} {transaction.token} (${transaction.amount_usd:,.0f})",
            ))
        elif transaction.amount_usd > 1_000_000:
            alerts.append(self._create_alert(
                whale=whale,
                transaction=transaction,
                severity="medium",
                message=f"Whale movement: {transaction.amount:.2f} {transaction.token} (${transaction.amount_usd:,.0f})",
            ))

        # Exchange flow alerts
        if transaction.action in [WhaleAction.BUY, WhaleAction.SELL]:
            exchange_type = "to" if transaction.action == WhaleAction.SELL else "from"
            alerts.append(self._create_alert(
                whale=whale,
                transaction=transaction,
                severity="high",
                message=f"Whale {transaction.action.value} on exchange: {transaction.amount:.2f} {transaction.token}",
            ))

        # Accumulation/ Distribution pattern
        if self._detect_pattern(whale, transaction):
            alerts.append(self._create_alert(
                whale=whale,
                transaction=transaction,
                severity="high",
                message=f"Whale {transaction.action.value} pattern detected: {whale.address[:8]}...",
            ))

        # Store alerts
        self._alerts.extend(alerts)
        self._performance["alerts_generated"] += len(alerts)

        # Execute alert callbacks
        for alert in alerts:
            await self._execute_alert_callbacks(alert)

    def _create_alert(
        self,
        whale: Whale,
        transaction: WhaleTransaction,
        severity: str,
        message: str
    ) -> WhaleAlert:
        """Create a whale alert."""
        alert_id = f"whale_alert_{int(time.time() * 1000)}_{whale.address[:8]}"

        return WhaleAlert(
            alert_id=alert_id,
            whale_address=whale.address,
            whale_type=whale.whale_type,
            action=transaction.action,
            token=transaction.token,
            amount=transaction.amount,
            amount_usd=transaction.amount_usd,
            severity=severity,
            confidence=transaction.confidence,
            message=message,
            metadata={
                "transaction_hash": transaction.transaction_hash,
                "block_number": transaction.block_number,
                "whale_name": whale.name,
                "current_balance": whale.current_balance,
                "current_balance_usd": whale.current_balance_usd,
            }
        )

    def _detect_pattern(
        self,
        whale: Whale,
        transaction: WhaleTransaction
    ) -> bool:
        """Detect whale patterns (accumulation/distribution)."""
        transactions = list(self._whale_transactions[whale.address])

        if len(transactions) < 5:
            return False

        recent = transactions[-5:]

        # Check for accumulation (multiple buys)
        buys = [t for t in recent if t.action in [WhaleAction.BUY, WhaleAction.ACCUMULATE]]
        if len(buys) >= 3:
            return True

        # Check for distribution (multiple sells)
        sells = [t for t in recent if t.action in [WhaleAction.SELL, WhaleAction.DISTRIBUTE]]
        if len(sells) >= 3:
            return True

        return False

    async def _handle_significant_move(
        self,
        whale: Whale,
        token: str,
        old_balance: float,
        new_balance: float,
        price: Optional[float]
    ) -> None:
        """Handle significant balance changes."""
        change = new_balance - old_balance
        change_usd = change * (price or self._get_price(token))

        # Determine action
        action = WhaleAction.ACCUMULATE if change > 0 else WhaleAction.DISTRIBUTE

        # Create transaction
        tx = WhaleTransaction(
            timestamp=datetime.utcnow(),
            whale_address=whale.address,
            token=token,
            amount=abs(change),
            amount_usd=abs(change_usd),
            price=price or self._get_price(token),
            action=action,
            confidence=WhaleConfidence.HIGH,
            metadata={
                "old_balance": old_balance,
                "new_balance": new_balance,
                "change_percentage": (abs(change) / old_balance * 100) if old_balance > 0 else 0,
            }
        )

        # Store and process
        self._whale_transactions[whale.address].append(tx)
        await self._check_alert_conditions(whale, tx)

    # -----------------------------------------------------------------------
    # Whale Clustering
    # -----------------------------------------------------------------------

    async def identify_clusters(self) -> List[WhaleCluster]:
        """Identify clusters of related whales."""
        clusters = []
        processed = set()

        for address, whale in self._whales.items():
            if address in processed:
                continue

            # Find related whales
            cluster = await self._find_related_whales(whale)
            if len(cluster) >= 2:
                cluster_id = f"cluster_{len(clusters)}_{int(time.time())}"
                cluster_obj = WhaleCluster(
                    cluster_id=cluster_id,
                    whales=cluster,
                    combined_balance_usd=sum(w.current_balance_usd for w in cluster),
                    collective_action=self._determine_collective_action(cluster),
                    confidence=self._calculate_cluster_confidence(cluster),
                )
                clusters.append(cluster_obj)

                for w in cluster:
                    processed.add(w.address)

        self._clusters = {c.cluster_id: c for c in clusters}
        self._performance["clusters_identified"] = len(clusters)

        return clusters

    async def _find_related_whales(self, whale: Whale) -> List[Whale]:
        """Find whales related to a given whale."""
        related = [whale]
        threshold = 0.6

        transactions = list(self._whale_transactions.get(whale.address, []))

        for other_addr, other_whale in self._whales.items():
            if other_addr == whale.address:
                continue

            other_tx = list(self._whale_transactions.get(other_addr, []))
            similarity = self._calculate_similarity(transactions, other_tx)

            if similarity >= threshold:
                related.append(other_whale)

        return related

    def _calculate_similarity(
        self,
        tx1: List[WhaleTransaction],
        tx2: List[WhaleTransaction]
    ) -> float:
        """Calculate similarity between two sets of transactions."""
        if not tx1 or not tx2:
            return 0.0

        # Token overlap
        tokens1 = {t.token for t in tx1}
        tokens2 = {t.token for t in tx2}
        token_overlap = len(tokens1 & tokens2) / len(tokens1 | tokens2) if tokens1 or tokens2 else 0

        # Action overlap
        actions1 = {t.action for t in tx1}
        actions2 = {t.action for t in tx2}
        action_overlap = len(actions1 & actions2) / len(actions1 | actions2) if actions1 or actions2 else 0

        # Timing overlap (same time periods)
        times1 = [t.timestamp.hour for t in tx1]
        times2 = [t.timestamp.hour for t in tx2]
        time_overlap = len(set(times1) & set(times2)) / len(set(times1) | set(times2)) if times1 or times2 else 0

        return (token_overlap * 0.4 + action_overlap * 0.3 + time_overlap * 0.3)

    def _determine_collective_action(
        self,
        whales: List[Whale]
    ) -> Optional[WhaleAction]:
        """Determine collective action of a cluster."""
        actions = []
        for whale in whales:
            if whale.address in self._whale_transactions:
                last_tx = list(self._whale_transactions[whale.address])[-1] if self._whale_transactions[whale.address] else None
                if last_tx:
                    actions.append(last_tx.action)

        if not actions:
            return None

        from collections import Counter
        action_counts = Counter(actions)
        most_common = action_counts.most_common(1)

        if most_common:
            action, count = most_common[0]
            if count / len(actions) >= 0.6:
                return action

        return None

    def _calculate_cluster_confidence(self, whales: List[Whale]) -> float:
        """Calculate confidence in a cluster."""
        if not whales:
            return 0.0

        avg_reputation = sum(w.reputation_score for w in whales) / len(whales)
        size_factor = min(1.0, len(whales) / 5)

        return avg_reputation * 0.7 + size_factor * 0.3

    # -----------------------------------------------------------------------
    # Analysis Methods
    # -----------------------------------------------------------------------

    async def analyze_whale_activity(
        self,
        token: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Analyze whale activity."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Collect transactions
        all_tx = []
        for address, tx_list in self._whale_transactions.items():
            for tx in tx_list:
                if tx.timestamp >= cutoff and (not token or tx.token == token):
                    all_tx.append(tx)

        if not all_tx:
            return {
                "total_whales": 0,
                "total_volume_usd": 0,
                "buy_volume": 0,
                "sell_volume": 0,
                "net_flow": 0,
                "top_whales": [],
            }

        # Calculate metrics
        buy_volume = sum(t.amount_usd for t in all_tx if t.action in [WhaleAction.BUY, WhaleAction.ACCUMULATE])
        sell_volume = sum(t.amount_usd for t in all_tx if t.action in [WhaleAction.SELL, WhaleAction.DISTRIBUTE])
        net_flow = buy_volume - sell_volume

        # Top whales by volume
        whale_volume = defaultdict(float)
        for tx in all_tx:
            whale_volume[tx.whale_address] += tx.amount_usd

        top_whales = sorted(
            whale_volume.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        top_whales_data = []
        for address, volume in top_whales:
            whale = self._whales.get(address)
            top_whales_data.append({
                "address": address,
                "volume_usd": volume,
                "name": whale.name if whale else None,
                "type": whale.whale_type.value if whale else None,
            })

        return {
            "total_whales": len(set(t.whale_address for t in all_tx)),
            "total_transactions": len(all_tx),
            "total_volume_usd": sum(t.amount_usd for t in all_tx),
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "net_flow": net_flow,
            "buy_ratio": buy_volume / (buy_volume + sell_volume) if (buy_volume + sell_volume) > 0 else 0,
            "top_whales": top_whales_data,
            "network_sentiment": self._calculate_network_sentiment(all_tx),
        }

    def _calculate_network_sentiment(self, transactions: List[WhaleTransaction]) -> str:
        """Calculate overall network sentiment from whale activity."""
        if not transactions:
            return "neutral"

        buy_tx = sum(1 for t in transactions if t.action in [WhaleAction.BUY, WhaleAction.ACCUMULATE])
        sell_tx = sum(1 for t in transactions if t.action in [WhaleAction.SELL, WhaleAction.DISTRIBUTE])

        ratio = buy_tx / (buy_tx + sell_tx) if (buy_tx + sell_tx) > 0 else 0.5

        if ratio > 0.7:
            return "bullish"
        elif ratio < 0.3:
            return "bearish"
        else:
            return "neutral"

    async def get_whale_movements(
        self,
        token: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get recent whale movements."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        movements = []
        for address, tx_list in self._whale_transactions.items():
            whale = self._whales.get(address)
            for tx in tx_list:
                if tx.timestamp >= cutoff and (not token or tx.token == token):
                    movements.append({
                        "timestamp": tx.timestamp.isoformat(),
                        "address": address,
                        "name": whale.name if whale else None,
                        "type": whale.whale_type.value if whale else None,
                        "token": tx.token,
                        "amount": tx.amount,
                        "amount_usd": tx.amount_usd,
                        "action": tx.action.value,
                        "confidence": tx.confidence.value,
                        "hash": tx.transaction_hash,
                    })

        return sorted(movements, key=lambda x: x["timestamp"], reverse=True)

    # -----------------------------------------------------------------------
    # Known Whales Loading
    # -----------------------------------------------------------------------

    def _load_known_whales(self) -> None:
        """Load known whale addresses."""
        # In production, this would load from a database or configuration file
        # These are placeholder examples

        known = {
            # Institutional whales
            "0x1234567890123456789012345678901234567890": {
                "type": WhaleType.INSTITUTIONAL,
                "name": "Institutional Whale 1",
                "labels": ["institutional", "large_cap"],
            },
            "0x2345678901234567890123456789012345678901": {
                "type": WhaleType.INSTITUTIONAL,
                "name": "Institutional Whale 2",
                "labels": ["institutional", "hedge_fund"],
            },
            # Exchange whales
            "0x3456789012345678901234567890123456789012": {
                "type": WhaleType.EXCHANGE,
                "name": "Exchange Whale 1",
                "labels": ["exchange", "binance"],
            },
            "0x4567890123456789012345678901234567890123": {
                "type": WhaleType.EXCHANGE,
                "name": "Exchange Whale 2",
                "labels": ["exchange", "coinbase"],
            },
            # VC whales
            "0x5678901234567890123456789012345678901234": {
                "type": WhaleType.VENTURE_CAPITAL,
                "name": "VC Firm 1",
                "labels": ["vc", "early_stage"],
            },
            # Treasury whales
            "0x6789012345678901234567890123456789012345": {
                "type": WhaleType.TREASURY,
                "name": "Protocol Treasury 1",
                "labels": ["treasury", "protocol"],
            },
        }

        for address, info in known.items():
            self.add_whale(
                address=address,
                whale_type=info["type"],
                name=info.get("name"),
                labels=info.get("labels", []),
            )

    # -----------------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------------

    def register_whale_callback(self, callback: Callable) -> None:
        """Register a callback for whale transactions."""
        self._whale_callbacks.append(callback)

    def register_alert_callback(self, callback: Callable) -> None:
        """Register a callback for whale alerts."""
        self._alert_callbacks.append(callback)

    async def _execute_whale_callbacks(self, transaction: WhaleTransaction) -> None:
        """Execute whale transaction callbacks."""
        for callback in self._whale_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(transaction)
                else:
                    callback(transaction)
            except Exception as e:
                logger.error(f"Error in whale callback: {e}")

    async def _execute_alert_callbacks(self, alert: WhaleAlert) -> None:
        """Execute alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge a whale alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.acknowledged:
                alert.acknowledged = True
                logger.info(f"Alert acknowledged: {alert_id}")
                return True
        return False

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve a whale alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id and alert.acknowledged and not alert.resolved:
                alert.resolved = True
                logger.info(f"Alert resolved: {alert_id}")
                return True
        return False

    def get_recent_alerts(
        self,
        hours: int = 24,
        min_severity: str = "medium"
    ) -> List[WhaleAlert]:
        """Get recent alerts."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}

        alerts = [
            a for a in self._alerts
            if a.timestamp >= cutoff
            and severity_order.get(a.severity, 0) >= severity_order.get(min_severity, 0)
        ]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "active_whales": len(self._whales),
            "total_transactions": sum(len(tx) for tx in self._whale_transactions.values()),
            "total_alerts": len(self._alerts),
            "unacknowledged_alerts": sum(1 for a in self._alerts if not a.acknowledged and not a.resolved),
            "clusters": len(self._clusters),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the whale tracker."""
        if self._running:
            return

        self._running = True

        # Start background tasks
        asyncio.create_task(self._periodic_analysis())

        logger.info("WhaleTracker started")

    async def stop(self) -> None:
        """Stop the whale tracker."""
        self._running = False
        logger.info("WhaleTracker stopped")

    async def _periodic_analysis(self) -> None:
        """Perform periodic analysis."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour

                # Identify new clusters
                await self.identify_clusters()

                # Clean up old alerts
                cutoff = datetime.utcnow() - timedelta(days=7)
                self._alerts = [a for a in self._alerts if a.timestamp >= cutoff]

            except Exception as e:
                logger.error(f"Error in periodic analysis: {e}")


# ============================================================================
# Factory Function
# ============================================================================

def create_whale_tracker(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> WhaleTracker:
    """Factory function to create a WhaleTracker instance."""
    return WhaleTracker(
        web3_client=web3_client,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the whale tracker
    pass

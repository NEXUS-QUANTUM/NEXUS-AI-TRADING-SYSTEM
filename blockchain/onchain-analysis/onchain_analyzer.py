# blockchain/onchain-analysis/onchain_analyzer.py
# NEXUS AI TRADING SYSTEM - Advanced On-Chain Analysis Engine
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Comprehensive on-chain analytics engine for blockchain data analysis.
Provides advanced metrics, anomaly detection, and predictive insights
from on-chain data across multiple chains.
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
from blockchain.onchain_analysis.base_analyzer import BaseOnChainAnalyzer
from blockchain.onchain_analysis.defi_analyzer import DeFiAnalyzer
from blockchain.onchain_analysis.exchange_flow import ExchangeFlowAnalyzer
from blockchain.onchain_analysis.gas_analyzer import GasAnalyzer
from blockchain.onchain_analysis.holder_analyzer import HolderAnalyzer
from blockchain.onchain_analysis.mempool_analyzer import MempoolAnalyzer
from blockchain.onchain_analysis.nft_analyzer import NFTAnalyzer
from blockchain.onchain_analysis.onchain_metrics import OnChainMetrics
from blockchain.onchain_analysis.onchain_signals import OnChainSignalGenerator
from blockchain.onchain_analysis.smart_money import SmartMoneyAnalyzer
from blockchain.onchain_analysis.token_analyzer import TokenAnalyzer
from blockchain.onchain_analysis.volume_analyzer import VolumeAnalyzer
from blockchain.onchain_analysis.whale_tracker import WhaleTracker
from blockchain.web3.web3_client import Web3Client
from shared.constants.error_constants import ErrorSeverity
from shared.helpers.date_helpers import parse_timestamp
from shared.utilities.logger import get_logger

logger = get_logger("nexus.onchain.analyzer")


# ============================================================================
# Enums & Constants
# ============================================================================

class AnalysisType(str, Enum):
    """Types of on-chain analysis."""
    WHALE = "whale"
    SMART_MONEY = "smart_money"
    EXCHANGE_FLOW = "exchange_flow"
    HOLDER = "holder"
    VOLUME = "volume"
    GAS = "gas"
    MEMPOOL = "mempool"
    DEFI = "defi"
    NFT = "nft"
    TOKEN = "token"
    METRICS = "metrics"
    SIGNALS = "signals"
    COMPOSITE = "composite"


class MarketSentiment(str, Enum):
    """Market sentiment derived from on-chain data."""
    EXTREMELY_BULLISH = "extremely_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    EXTREMELY_BEARISH = "extremely_bearish"
    VOLATILE = "volatile"


class OnChainRiskLevel(str, Enum):
    """Risk levels derived from on-chain data."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


# ============================================================================
# Data Models
# ============================================================================

class OnChainAnalysisConfig(BaseModel):
    """Configuration for on-chain analysis."""
    chain: str
    tokens: List[str] = Field(default_factory=list)
    analysis_types: List[AnalysisType] = Field(default_factory=list)
    lookback_days: int = 30
    update_interval_seconds: int = 60
    min_transaction_threshold: int = 10
    whale_threshold_usd: float = 1_000_000
    smart_money_threshold_usd: float = 500_000
    anomaly_threshold_std: float = 3.0
    sentiment_weight: float = 0.7
    enable_auto_analysis: bool = True
    max_stored_results: int = 1000


@dataclass
class OnChainAnalysisResult:
    """Complete result of on-chain analysis."""
    timestamp: datetime
    chain: str
    token: Optional[str] = None
    analysis_type: Optional[AnalysisType] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    signals: List[Dict[str, Any]] = field(default_factory=list)
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    sentiment: Optional[MarketSentiment] = None
    risk_level: Optional[OnChainRiskLevel] = None
    confidence_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0


@dataclass
class OnChainSnapshot:
    """Point-in-time snapshot of on-chain state."""
    timestamp: datetime
    chain: str
    block_number: int
    block_hash: str
    total_supply: float
    circulating_supply: float
    holders: int
    top_holders: List[Dict[str, Any]]
    exchange_balances: Dict[str, float]
    total_value_locked: float
    daily_volume: float
    active_addresses: int
    new_addresses: int
    gas_price: float
    transaction_count: int
    average_transaction_value: float
    unique_interactions: int
    contract_creations: int
    token_transfers: int
    dex_swaps: int
    bridge_transfers: int
    stablecoin_flows: Dict[str, float]


class AnomalyDetectionResult(BaseModel):
    """Result of anomaly detection."""
    detected: bool
    severity: float  # 0-1
    metric: str
    current_value: float
    expected_range: Tuple[float, float]
    deviation_std: float
    explanation: str
    timestamp: datetime


# ============================================================================
# Core Analyzer
# ============================================================================

class OnChainAnalyzer(BaseOnChainAnalyzer):
    """
    Advanced on-chain data analysis engine.
    Integrates all sub-analyzers and provides unified insights.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[OnChainAnalysisConfig] = None,
    ):
        super().__init__(web3_client)
        self.config = config or OnChainAnalysisConfig(chain=web3_client.chain_name)

        # Initialize sub-analyzers
        self.gas_analyzer = GasAnalyzer(web3_client)
        self.holder_analyzer = HolderAnalyzer(web3_client)
        self.whale_tracker = WhaleTracker(web3_client)
        self.smart_money_analyzer = SmartMoneyAnalyzer(web3_client)
        self.exchange_flow_analyzer = ExchangeFlowAnalyzer(web3_client)
        self.volume_analyzer = VolumeAnalyzer(web3_client)
        self.token_analyzer = TokenAnalyzer(web3_client)
        self.mempool_analyzer = MempoolAnalyzer(web3_client)
        self.defi_analyzer = DeFiAnalyzer(web3_client)
        self.nft_analyzer = NFTAnalyzer(web3_client)
        self.metrics_collector = OnChainMetrics(web3_client)
        self.signal_generator = OnChainSignalGenerator(web3_client)

        # State management
        self._results_cache: Dict[str, OnChainAnalysisResult] = {}
        self._historical_results: deque = deque(maxlen=self.config.max_stored_results)
        self._snapshots: deque = deque(maxlen=100)
        self._anomalies: List[AnomalyDetectionResult] = []
        self._running = False
        self._lock = asyncio.Lock()

        # Performance metrics
        self._metrics: Dict[str, Any] = {
            "analyzes_performed": 0,
            "avg_analysis_time_ms": 0.0,
            "anomalies_detected": 0,
            "signals_generated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Callbacks
        self._analysis_callbacks: List[Callable] = []
        self._anomaly_callbacks: List[Callable] = []

        logger.info(
            "OnChainAnalyzer initialized",
            extra={
                "chain": web3_client.chain_name,
                "config": self.config.dict(),
            }
        )

    # -----------------------------------------------------------------------
    # Analysis Methods
    # -----------------------------------------------------------------------

    async def analyze_whale_movements(
        self,
        token_address: Optional[str] = None,
        min_usd: Optional[float] = None,
        lookback_hours: int = 24
    ) -> OnChainAnalysisResult:
        """Analyze whale movements on the chain."""
        start_time = time.time()
        min_usd = min_usd or self.config.whale_threshold_usd

        try:
            movements = await self.whale_tracker.get_recent_movements(
                token_address=token_address,
                min_usd=min_usd,
                lookback_hours=lookback_hours
            )

            metrics = {
                "total_movements": len(movements),
                "total_value_usd": sum(m.get("value_usd", 0) for m in movements),
                "average_value_usd": np.mean([m.get("value_usd", 0) for m in movements]) if movements else 0,
                "max_value_usd": max([m.get("value_usd", 0) for m in movements]) if movements else 0,
                "buy_volume": sum(m.get("value_usd", 0) for m in movements if m.get("direction") == "buy"),
                "sell_volume": sum(m.get("value_usd", 0) for m in movements if m.get("direction") == "sell"),
                "exchange_inflows": sum(m.get("value_usd", 0) for m in movements if m.get("direction") == "exchange_in"),
                "exchange_outflows": sum(m.get("value_usd", 0) for m in movements if m.get("direction") == "exchange_out"),
            }

            # Identify significant patterns
            signals = []
            if metrics["total_value_usd"] > 10_000_000:
                signals.append({
                    "type": "high_whale_activity",
                    "severity": "high",
                    "message": f"High whale activity detected: ${metrics['total_value_usd']:,.0f} in last {lookback_hours}h"
                })

            if metrics["exchange_inflows"] > metrics["exchange_outflows"] * 1.5:
                signals.append({
                    "type": "exchange_inflow",
                    "severity": "medium",
                    "message": f"Large exchange inflow: ${metrics['exchange_inflows']:,.0f} vs ${metrics['exchange_outflows']:,.0f} outflow"
                })

            if metrics["buy_volume"] > metrics["sell_volume"] * 2:
                signals.append({
                    "type": "whale_accumulation",
                    "severity": "high",
                    "message": "Strong whale accumulation detected"
                })

            return self._create_result(
                analysis_type=AnalysisType.WHALE,
                token=token_address,
                metrics=metrics,
                signals=signals,
                raw_data={"movements": movements},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing whale movements: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.WHALE,
                token=token_address,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_smart_money(
        self,
        token_address: Optional[str] = None,
        lookback_hours: int = 24
    ) -> OnChainAnalysisResult:
        """Analyze smart money activity."""
        start_time = time.time()

        try:
            activity = await self.smart_money_analyzer.get_recent_activity(
                token_address=token_address,
                lookback_hours=lookback_hours
            )

            metrics = {
                "total_activities": len(activity),
                "buys": sum(1 for a in activity if a.get("action") == "buy"),
                "sells": sum(1 for a in activity if a.get("action") == "sell"),
                "total_buy_value": sum(a.get("value_usd", 0) for a in activity if a.get("action") == "buy"),
                "total_sell_value": sum(a.get("value_usd", 0) for a in activity if a.get("action") == "sell"),
                "confidence_score": self.smart_money_analyzer.get_confidence_score(token_address),
                "top_smart_wallets": activity[:10] if activity else [],
                "buy_sell_ratio": 0
            }

            if metrics["sells"] > 0:
                metrics["buy_sell_ratio"] = metrics["buys"] / max(metrics["sells"], 1)

            signals = []
            if metrics["confidence_score"] > 0.8:
                signals.append({
                    "type": "high_confidence_smart_money",
                    "severity": "high",
                    "message": f"High confidence smart money activity: {metrics['confidence_score']:.2%}"
                })

            if metrics["buy_sell_ratio"] > 2:
                signals.append({
                    "type": "smart_money_accumulation",
                    "severity": "high",
                    "message": "Smart money accumulation detected"
                })

            if metrics["buy_sell_ratio"] < 0.5:
                signals.append({
                    "type": "smart_money_distribution",
                    "severity": "medium",
                    "message": "Smart money distribution detected"
                })

            return self._create_result(
                analysis_type=AnalysisType.SMART_MONEY,
                token=token_address,
                metrics=metrics,
                signals=signals,
                raw_data={"activity": activity},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing smart money: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.SMART_MONEY,
                token=token_address,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_exchange_flows(
        self,
        token_address: Optional[str] = None,
        lookback_hours: int = 24
    ) -> OnChainAnalysisResult:
        """Analyze exchange flows."""
        start_time = time.time()

        try:
            flows = await self.exchange_flow_analyzer.get_flows(
                token_address=token_address,
                lookback_hours=lookback_hours
            )

            metrics = {
                "inflows": flows.get("inflows", []),
                "outflows": flows.get("outflows", []),
                "total_inflow": flows.get("total_inflow", 0),
                "total_outflow": flows.get("total_outflow", 0),
                "net_flow": flows.get("net_flow", 0),
                "exchanges_involved": flows.get("exchanges", []),
                "largest_inflow": flows.get("largest_inflow", {}),
                "largest_outflow": flows.get("largest_outflow", {}),
            }

            signals = []
            if metrics["net_flow"] > 10_000_000:
                signals.append({
                    "type": "large_net_inflow",
                    "severity": "high",
                    "message": f"Large net exchange inflow: ${metrics['net_flow']:,.0f}"
                })
            elif metrics["net_flow"] < -10_000_000:
                signals.append({
                    "type": "large_net_outflow",
                    "severity": "high",
                    "message": f"Large net exchange outflow: ${abs(metrics['net_flow']):,.0f}"
                })

            return self._create_result(
                analysis_type=AnalysisType.EXCHANGE_FLOW,
                token=token_address,
                metrics=metrics,
                signals=signals,
                raw_data={"flows": flows},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing exchange flows: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.EXCHANGE_FLOW,
                token=token_address,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_holders(
        self,
        token_address: str,
        lookback_days: int = 30
    ) -> OnChainAnalysisResult:
        """Analyze token holders."""
        start_time = time.time()

        try:
            holder_data = await self.holder_analyzer.get_holder_analysis(
                token_address=token_address,
                lookback_days=lookback_days
            )

            metrics = {
                "total_holders": holder_data.get("total_holders", 0),
                "top_holders": holder_data.get("top_holders", []),
                "holder_distribution": holder_data.get("distribution", {}),
                "concentration": holder_data.get("concentration", {}),
                "new_holders": holder_data.get("new_holders", 0),
                "lost_holders": holder_data.get("lost_holders", 0),
                "net_holder_change": holder_data.get("net_holder_change", 0),
                "average_holding": holder_data.get("average_holding", 0),
                "median_holding": holder_data.get("median_holding", 0),
            }

            signals = []
            concentration = metrics["concentration"].get("top_10_percent", 0)
            if concentration > 0.8:
                signals.append({
                    "type": "high_concentration",
                    "severity": "medium",
                    "message": f"High holder concentration: top 10% hold {concentration:.1%}"
                })

            if metrics["net_holder_change"] > 0:
                signals.append({
                    "type": "holder_growth",
                    "severity": "low",
                    "message": f"Holder growth: +{metrics['net_holder_change']} new holders"
                })

            return self._create_result(
                analysis_type=AnalysisType.HOLDER,
                token=token_address,
                metrics=metrics,
                signals=signals,
                raw_data={"holder_data": holder_data},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing holders: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.HOLDER,
                token=token_address,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_volume(
        self,
        token_address: Optional[str] = None,
        lookback_days: int = 30
    ) -> OnChainAnalysisResult:
        """Analyze trading volume."""
        start_time = time.time()

        try:
            volume_data = await self.volume_analyzer.get_volume_analysis(
                token_address=token_address,
                lookback_days=lookback_days
            )

            metrics = {
                "total_volume_24h": volume_data.get("volume_24h", 0),
                "total_volume_7d": volume_data.get("volume_7d", 0),
                "average_daily_volume": volume_data.get("average_daily_volume", 0),
                "volume_change_24h": volume_data.get("volume_change_24h", 0),
                "volume_change_7d": volume_data.get("volume_change_7d", 0),
                "peak_daily_volume": volume_data.get("peak_daily_volume", 0),
                "volume_distribution": volume_data.get("distribution", {}),
                "dex_volume": volume_data.get("dex_volume", 0),
                "cex_volume": volume_data.get("cex_volume", 0),
                "unusual_activity": volume_data.get("unusual_activity", False),
            }

            signals = []
            if metrics["volume_change_24h"] > 200:
                signals.append({
                    "type": "volume_spike",
                    "severity": "high",
                    "message": f"Massive volume spike: +{metrics['volume_change_24h']:.0f}% in 24h"
                })
            elif metrics["volume_change_24h"] > 100:
                signals.append({
                    "type": "volume_increase",
                    "severity": "medium",
                    "message": f"Significant volume increase: +{metrics['volume_change_24h']:.0f}%"
                })

            if metrics["unusual_activity"]:
                signals.append({
                    "type": "unusual_volume",
                    "severity": "medium",
                    "message": "Unusual volume patterns detected"
                })

            return self._create_result(
                analysis_type=AnalysisType.VOLUME,
                token=token_address,
                metrics=metrics,
                signals=signals,
                raw_data={"volume_data": volume_data},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing volume: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.VOLUME,
                token=token_address,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_gas(self, lookback_hours: int = 24) -> OnChainAnalysisResult:
        """Analyze gas usage patterns."""
        start_time = time.time()

        try:
            gas_data = await self.gas_analyzer.get_gas_analysis(
                lookback_hours=lookback_hours
            )

            metrics = {
                "current_gas_price": gas_data.get("current_price", 0),
                "average_price": gas_data.get("average_price", 0),
                "min_price": gas_data.get("min_price", 0),
                "max_price": gas_data.get("max_price", 0),
                "price_percentile_25": gas_data.get("p25", 0),
                "price_percentile_75": gas_data.get("p75", 0),
                "network_congestion": gas_data.get("congestion", "low"),
                "gas_spikes": gas_data.get("spikes", []),
                "peak_usage_hours": gas_data.get("peak_hours", []),
                "average_block_utilization": gas_data.get("block_utilization", 0),
            }

            signals = []
            if metrics["current_gas_price"] > metrics["average_price"] * 2:
                signals.append({
                    "type": "gas_spike",
                    "severity": "high",
                    "message": f"Gas price spike: {metrics['current_gas_price']} gwei (avg: {metrics['average_price']:.1f})"
                })

            if metrics["network_congestion"] == "high":
                signals.append({
                    "type": "network_congestion",
                    "severity": "medium",
                    "message": "High network congestion detected"
                })

            return self._create_result(
                analysis_type=AnalysisType.GAS,
                metrics=metrics,
                signals=signals,
                raw_data={"gas_data": gas_data},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing gas: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.GAS,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_mempool(self) -> OnChainAnalysisResult:
        """Analyze mempool conditions."""
        start_time = time.time()

        try:
            mempool_data = await self.mempool_analyzer.get_mempool_analysis()

            metrics = {
                "total_pending_tx": mempool_data.get("pending_count", 0),
                "high_gas_pending": mempool_data.get("high_gas_count", 0),
                "average_wait_time": mempool_data.get("avg_wait_time", 0),
                "backlog_age": mempool_data.get("backlog_age", 0),
                "pending_by_priority": mempool_data.get("by_priority", {}),
                "expected_confirmation_time": mempool_data.get("expected_time", 0),
            }

            signals = []
            if metrics["total_pending_tx"] > 5000:
                signals.append({
                    "type": "mempool_backlog",
                    "severity": "medium",
                    "message": f"Large mempool backlog: {metrics['total_pending_tx']} pending transactions"
                })

            return self._create_result(
                analysis_type=AnalysisType.MEMPOOL,
                metrics=metrics,
                signals=signals,
                raw_data={"mempool_data": mempool_data},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing mempool: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.MEMPOOL,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_defi(self, protocol: Optional[str] = None) -> OnChainAnalysisResult:
        """Analyze DeFi protocol activity."""
        start_time = time.time()

        try:
            defi_data = await self.defi_analyzer.get_protocol_analysis(
                protocol=protocol
            )

            metrics = {
                "total_value_locked": defi_data.get("tvl", 0),
                "tvl_change_24h": defi_data.get("tvl_change_24h", 0),
                "active_users": defi_data.get("active_users", 0),
                "total_volume": defi_data.get("volume", 0),
                "volume_change_24h": defi_data.get("volume_change_24h", 0),
                "protocol_health_score": defi_data.get("health_score", 0),
                "liquidation_volume": defi_data.get("liquidations", 0),
                "borrow_utilization": defi_data.get("borrow_utilization", 0),
                "protocols": defi_data.get("protocols", []),
            }

            signals = []
            if metrics["protocol_health_score"] < 0.5:
                signals.append({
                    "type": "protocol_risk",
                    "severity": "high",
                    "message": f"Low protocol health score: {metrics['protocol_health_score']:.2f}"
                })

            if metrics["liquidation_volume"] > 1_000_000:
                signals.append({
                    "type": "high_liquidations",
                    "severity": "medium",
                    "message": f"High liquidation volume: ${metrics['liquidation_volume']:,.0f}"
                })

            return self._create_result(
                analysis_type=AnalysisType.DEFI,
                metrics=metrics,
                signals=signals,
                raw_data={"defi_data": defi_data},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing DeFi: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.DEFI,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_token(
        self,
        token_address: str,
        deep_analysis: bool = False
    ) -> OnChainAnalysisResult:
        """Comprehensive token analysis."""
        start_time = time.time()

        try:
            # Run all token-specific analyses
            holder_result = await self.analyze_holders(token_address)
            whale_result = await self.analyze_whale_movements(token_address)
            volume_result = await self.analyze_volume(token_address)
            exchange_result = await self.analyze_exchange_flows(token_address)

            token_data = await self.token_analyzer.get_token_analysis(
                token_address=token_address
            )

            # Compile comprehensive metrics
            metrics = {
                "token_info": token_data.get("token_info", {}),
                "price": token_data.get("price", {}),
                "supply": token_data.get("supply", {}),
                "holders": holder_result.metrics if holder_result else {},
                "whale_activity": whale_result.metrics if whale_result else {},
                "volume": volume_result.metrics if volume_result else {},
                "exchange_flows": exchange_result.metrics if exchange_result else {},
                "overall_health_score": self._calculate_health_score(
                    holder_result, whale_result, volume_result, exchange_result, token_data
                ),
            }

            # Generate comprehensive signals
            signals = []
            signals.extend(holder_result.signals if holder_result else [])
            signals.extend(whale_result.signals if whale_result else [])
            signals.extend(volume_result.signals if volume_result else [])
            signals.extend(exchange_result.signals if exchange_result else [])

            # Add overall signals
            health_score = metrics["overall_health_score"]
            if health_score > 0.8:
                signals.append({
                    "type": "strong_token_health",
                    "severity": "low",
                    "message": "Token shows strong on-chain health"
                })
            elif health_score < 0.3:
                signals.append({
                    "type": "weak_token_health",
                    "severity": "high",
                    "message": "Token shows weak on-chain health"
                })

            return self._create_result(
                analysis_type=AnalysisType.TOKEN,
                token=token_address,
                metrics=metrics,
                signals=signals,
                raw_data={"token_data": token_data},
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Error analyzing token: {e}", exc_info=True)
            return self._create_result(
                analysis_type=AnalysisType.TOKEN,
                token=token_address,
                metrics={"error": str(e)},
                processing_time=time.time() - start_time
            )

    async def analyze_composite(
        self,
        tokens: List[str],
        include_metrics: List[AnalysisType] = None
    ) -> OnChainAnalysisResult:
        """Composite analysis across multiple tokens and metrics."""
        start_time = time.time()

        include_metrics = include_metrics or [
            AnalysisType.WHALE,
            AnalysisType.SMART_MONEY,
            AnalysisType.EXCHANGE_FLOW,
            AnalysisType.HOLDER,
            AnalysisType.VOLUME,
            AnalysisType.GAS,
        ]

        all_results = {}
        combined_signals = []
        combined_metrics = {}

        for token in tokens:
            token_results = []
            for analysis_type in include_metrics:
                if analysis_type == AnalysisType.WHALE:
                    result = await self.analyze_whale_movements(token)
                elif analysis_type == AnalysisType.SMART_MONEY:
                    result = await self.analyze_smart_money(token)
                elif analysis_type == AnalysisType.EXCHANGE_FLOW:
                    result = await self.analyze_exchange_flows(token)
                elif analysis_type == AnalysisType.HOLDER:
                    result = await self.analyze_holders(token)
                elif analysis_type == AnalysisType.VOLUME:
                    result = await self.analyze_volume(token)
                else:
                    continue
                token_results.append(result)
                combined_signals.extend(result.signals)

            all_results[token] = token_results

            # Collect metrics for this token
            token_metrics = {}
            for result in token_results:
                token_metrics.update(result.metrics)
            combined_metrics[token] = token_metrics

        # Calculate overall metrics
        overall_metrics = {
            "tokens_analyzed": len(tokens),
            "analysis_types": [t.value for t in include_metrics],
            "total_signals": len(combined_signals),
            "tokens_with_alerts": len([t for t in all_results if any(r.signals for r in all_results[t])]),
            "token_metrics": combined_metrics,
        }

        # Deduplicate and prioritize signals
        unique_signals = self._deduplicate_signals(combined_signals)

        return self._create_result(
            analysis_type=AnalysisType.COMPOSITE,
            metrics=overall_metrics,
            signals=unique_signals,
            raw_data={"all_results": all_results},
            processing_time=time.time() - start_time
        )

    # -----------------------------------------------------------------------
    # Convenience Methods
    # -----------------------------------------------------------------------

    async def get_market_sentiment(
        self,
        token_address: Optional[str] = None
    ) -> Tuple[MarketSentiment, float]:
        """
        Derive market sentiment from on-chain data.
        Returns (sentiment, confidence_score).
        """
        try:
            if token_address:
                result = await self.analyze_token(token_address)
            else:
                # Use general metrics
                gas_result = await self.analyze_gas()
                mempool_result = await self.analyze_mempool()
                result = self._create_result(
                    analysis_type=AnalysisType.METRICS,
                    metrics={
                        "gas": gas_result.metrics,
                        "mempool": mempool_result.metrics,
                    }
                )

            sentiment_score = self._calculate_sentiment_score(result)
            confidence = self._calculate_sentiment_confidence(result)

            sentiment = self._score_to_sentiment(sentiment_score)

            return sentiment, confidence

        except Exception as e:
            logger.error(f"Error calculating market sentiment: {e}", exc_info=True)
            return MarketSentiment.NEUTRAL, 0.0

    async def get_risk_assessment(
        self,
        token_address: str
    ) -> Tuple[OnChainRiskLevel, float, List[str]]:
        """
        Assess risk level for a token.
        Returns (risk_level, risk_score, risk_factors).
        """
        try:
            result = await self.analyze_token(token_address)

            risk_factors = []
            risk_score = 0.0

            # Check concentration risk
            concentration = result.metrics.get("holders", {}).get("concentration", {}).get("top_10_percent", 0)
            if concentration > 0.8:
                risk_score += 0.3
                risk_factors.append(f"High concentration: {concentration:.1%} in top 10%")
            elif concentration > 0.6:
                risk_score += 0.15
                risk_factors.append(f"Moderate concentration: {concentration:.1%} in top 10%")

            # Check whale activity
            whale_metrics = result.metrics.get("whale_activity", {})
            total_whale_value = whale_metrics.get("total_value_usd", 0)
            if total_whale_value > 10_000_000:
                risk_score += 0.2
                risk_factors.append(f"High whale activity: ${total_whale_value:,.0f}")
            elif total_whale_value > 5_000_000:
                risk_score += 0.1
                risk_factors.append(f"Moderate whale activity: ${total_whale_value:,.0f}")

            # Check exchange flow
            exchange_metrics = result.metrics.get("exchange_flows", {})
            net_flow = exchange_metrics.get("net_flow", 0)
            if abs(net_flow) > 5_000_000:
                risk_score += 0.15
                risk_factors.append(f"Significant exchange flow: ${abs(net_flow):,.0f}")

            # Check volume anomalies
            volume_metrics = result.metrics.get("volume", {})
            if volume_metrics.get("unusual_activity", False):
                risk_score += 0.15
                risk_factors.append("Unusual volume patterns detected")

            # Determine risk level
            if risk_score >= 0.7:
                risk_level = OnChainRiskLevel.CRITICAL
            elif risk_score >= 0.5:
                risk_level = OnChainRiskLevel.HIGH
            elif risk_score >= 0.3:
                risk_level = OnChainRiskLevel.MEDIUM
            elif risk_score >= 0.15:
                risk_level = OnChainRiskLevel.LOW
            else:
                risk_level = OnChainRiskLevel.VERY_LOW

            return risk_level, risk_score, risk_factors

        except Exception as e:
            logger.error(f"Error assessing risk: {e}", exc_info=True)
            return OnChainRiskLevel.HIGH, 0.5, ["Error in risk assessment"]

    # -----------------------------------------------------------------------
    # Anomaly Detection
    # -----------------------------------------------------------------------

    async def detect_anomalies(
        self,
        metric: str,
        current_value: float,
        historical_data: List[float]
    ) -> Optional[AnomalyDetectionResult]:
        """
        Detect anomalies in on-chain metrics.
        """
        if len(historical_data) < 10:
            return None

        try:
            mean = np.mean(historical_data)
            std = np.std(historical_data)

            if std == 0:
                return None

            deviation = abs(current_value - mean) / std
            threshold = self.config.anomaly_threshold_std

            if deviation > threshold:
                # Calculate severity (normalized to 0-1)
                severity = min(deviation / (threshold * 2), 1.0)

                # Determine expected range
                expected_range = (
                    mean - threshold * std,
                    mean + threshold * std
                )

                return AnomalyDetectionResult(
                    detected=True,
                    severity=severity,
                    metric=metric,
                    current_value=current_value,
                    expected_range=expected_range,
                    deviation_std=deviation,
                    explanation=self._generate_anomaly_explanation(
                        metric, current_value, mean, std, deviation
                    ),
                    timestamp=datetime.utcnow()
                )

            return None

        except Exception as e:
            logger.error(f"Error detecting anomaly: {e}", exc_info=True)
            return None

    # -----------------------------------------------------------------------
    # Snapshot Management
    # -----------------------------------------------------------------------

    async def capture_snapshot(self) -> OnChainSnapshot:
        """
        Capture a point-in-time snapshot of the chain state.
        """
        try:
            current_block = await self.web3_client.get_block('latest')

            # Collect data from sub-analyzers
            gas_data = await self.gas_analyzer.get_current_gas_price()
            holder_data = await self.holder_analyzer.get_current_holders()
            exchange_data = await self.exchange_flow_analyzer.get_exchange_balances()
            volume_data = await self.volume_analyzer.get_24h_volume()

            snapshot = OnChainSnapshot(
                timestamp=datetime.utcnow(),
                chain=self.web3_client.chain_name,
                block_number=current_block['number'],
                block_hash=current_block['hash'],
                total_supply=0,  # Would be fetched from contract
                circulating_supply=0,  # Would be fetched from contract
                holders=len(holder_data.get("holders", [])),
                top_holders=holder_data.get("top_holders", [])[:10],
                exchange_balances=exchange_data.get("balances", {}),
                total_value_locked=exchange_data.get("total_locked", 0),
                daily_volume=volume_data.get("volume_24h", 0),
                active_addresses=0,  # Would be calculated from blocks
                new_addresses=0,
                gas_price=gas_data.get("gas_price", 0),
                transaction_count=0,
                average_transaction_value=0,
                unique_interactions=0,
                contract_creations=0,
                token_transfers=0,
                dex_swaps=0,
                bridge_transfers=0,
                stablecoin_flows=exchange_data.get("stablecoin_flows", {})
            )

            self._snapshots.append(snapshot)
            return snapshot

        except Exception as e:
            logger.error(f"Error capturing snapshot: {e}", exc_info=True)
            raise

    # -----------------------------------------------------------------------
    # Helper Methods
    # -----------------------------------------------------------------------

    def _create_result(
        self,
        analysis_type: AnalysisType,
        metrics: Dict[str, Any],
        signals: List[Dict[str, Any]] = None,
        anomalies: List[Dict[str, Any]] = None,
        token: Optional[str] = None,
        raw_data: Dict[str, Any] = None,
        processing_time: float = 0.0
    ) -> OnChainAnalysisResult:
        """Create a standardized analysis result."""
        signals = signals or []
        anomalies = anomalies or []
        raw_data = raw_data or {}

        # Calculate sentiment and risk if not already provided
        sentiment = None
        risk_level = None
        confidence = 0.0

        if analysis_type in [AnalysisType.TOKEN, AnalysisType.COMPOSITE]:
            sentiment, _ = self._calculate_sentiment_from_metrics(metrics)
            risk_level, confidence, _ = self._calculate_risk_from_metrics(metrics)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            analysis_type, metrics, signals, anomalies
        )

        result = OnChainAnalysisResult(
            timestamp=datetime.utcnow(),
            chain=self.web3_client.chain_name,
            token=token,
            analysis_type=analysis_type,
            metrics=metrics,
            signals=signals,
            anomalies=anomalies,
            sentiment=sentiment,
            risk_level=risk_level,
            confidence_score=confidence,
            recommendations=recommendations,
            raw_data=raw_data,
            processing_time_ms=processing_time * 1000
        )

        # Store in cache
        cache_key = f"{analysis_type.value}_{token or 'global'}_{int(time.time() / 300)}"
        self._results_cache[cache_key] = result
        self._historical_results.append(result)

        self._metrics["analyzes_performed"] += 1
        self._metrics["avg_analysis_time_ms"] = (
            (self._metrics["avg_analysis_time_ms"] * (self._metrics["analyzes_performed"] - 1) +
             processing_time * 1000) / self._metrics["analyzes_performed"]
        )

        return result

    def _calculate_health_score(
        self,
        holder_result: Optional[OnChainAnalysisResult],
        whale_result: Optional[OnChainAnalysisResult],
        volume_result: Optional[OnChainAnalysisResult],
        exchange_result: Optional[OnChainAnalysisResult],
        token_data: Dict[str, Any]
    ) -> float:
        """Calculate a comprehensive health score for a token."""
        scores = []

        # Holder health
        if holder_result:
            holder_metrics = holder_result.metrics
            concentration = holder_metrics.get("concentration", {}).get("top_10_percent", 0.5)
            holder_growth = holder_metrics.get("net_holder_change", 0)

            holder_score = 1.0 - concentration
            if holder_growth > 0:
                holder_score = min(holder_score + 0.1, 1.0)
            scores.append(holder_score)

        # Whale activity health
        if whale_result:
            whale_metrics = whale_result.metrics
            total_value = whale_metrics.get("total_value_usd", 0)
            # Lower score if high whale activity
            whale_score = 1.0 - min(total_value / 10_000_000, 0.5)
            scores.append(whale_score)

        # Volume health
        if volume_result:
            volume_metrics = volume_result.metrics
            volume_change = volume_metrics.get("volume_change_7d", 0)
            # Positive volume growth is good
            volume_score = 0.5 + min(volume_change / 100, 0.5)
            volume_score = max(0, min(volume_score, 1.0))
            scores.append(volume_score)

        # Exchange flow health
        if exchange_result:
            exchange_metrics = exchange_result.metrics
            net_flow = exchange_metrics.get("net_flow", 0)
            # Negative net flow (out of exchanges) is generally bullish
            flow_score = 0.5 + max(min(-net_flow / 5_000_000, 0.5), -0.5)
            scores.append(flow_score)

        # Token data health
        if token_data:
            price_change = token_data.get("price", {}).get("change_24h", 0)
            # Positive price change is good
            price_score = 0.5 + max(min(price_change / 20, 0.5), -0.5)
            scores.append(price_score)

        return np.mean(scores) if scores else 0.5

    def _calculate_sentiment_score(self, result: OnChainAnalysisResult) -> float:
        """Calculate sentiment score from analysis result."""
        score = 0.0
        weight_sum = 0.0

        metrics = result.metrics

        # Whale activity
        whale_metrics = metrics.get("whale_activity", {})
        if whale_metrics:
            buy_volume = whale_metrics.get("buy_volume", 0)
            sell_volume = whale_metrics.get("sell_volume", 0)
            total = buy_volume + sell_volume
            if total > 0:
                whale_sentiment = (buy_volume - sell_volume) / total
                score += whale_sentiment * 0.25
                weight_sum += 0.25

        # Exchange flow
        exchange_metrics = metrics.get("exchange_flows", {})
        if exchange_metrics:
            net_flow = exchange_metrics.get("net_flow", 0)
            # Negative net flow (out of exchanges) is bullish
            exchange_sentiment = -max(min(net_flow / 5_000_000, 1), -1)
            score += exchange_sentiment * 0.2
            weight_sum += 0.2

        # Holder growth
        holder_metrics = metrics.get("holders", {})
        if holder_metrics:
            net_change = holder_metrics.get("net_holder_change", 0)
            if net_change > 100:
                holder_sentiment = min(net_change / 1000, 0.5)
            else:
                holder_sentiment = -0.5
            score += holder_sentiment * 0.15
            weight_sum += 0.15

        # Volume
        volume_metrics = metrics.get("volume", {})
        if volume_metrics:
            change_24h = volume_metrics.get("volume_change_24h", 0)
            volume_sentiment = max(min(change_24h / 50, 0.5), -0.5)
            score += volume_sentiment * 0.15
            weight_sum += 0.15

        # Gas (high gas = network activity = bullish)
        gas_metrics = metrics.get("gas", {})
        if gas_metrics:
            gas_price = gas_metrics.get("current_gas_price", 0)
            avg_gas = gas_metrics.get("average_price", gas_price)
            if avg_gas > 0:
                gas_sentiment = max(min((gas_price - avg_gas) / avg_gas, 0.3), -0.3)
                score += gas_sentiment * 0.1
                weight_sum += 0.1

        # Default to neutral
        if weight_sum > 0:
            score = score / weight_sum
        else:
            score = 0.0

        return max(min(score, 1.0), -1.0)

    def _score_to_sentiment(self, score: float) -> MarketSentiment:
        """Convert sentiment score to MarketSentiment enum."""
        if score >= 0.8:
            return MarketSentiment.EXTREMELY_BULLISH
        elif score >= 0.4:
            return MarketSentiment.BULLISH
        elif score >= -0.4:
            return MarketSentiment.NEUTRAL
        elif score >= -0.8:
            return MarketSentiment.BEARISH
        else:
            return MarketSentiment.EXTREMELY_BEARISH

    def _calculate_sentiment_confidence(self, result: OnChainAnalysisResult) -> float:
        """Calculate confidence in sentiment assessment."""
        # Confidence based on data availability and consistency
        metrics = result.metrics
        has_data_count = sum(
            1 for key in ["whale_activity", "exchange_flows", "holders", "volume", "gas"]
            if key in metrics and metrics[key]
        )

        confidence = min(has_data_count / 5, 0.8)  # Max 80% confidence

        # Adjust based on signal consistency
        signals = result.signals
        bullish_signals = sum(1 for s in signals if s.get("type") in [
            "whale_accumulation", "smart_money_accumulation", "holder_growth"
        ])
        bearish_signals = sum(1 for s in signals if s.get("type") in [
            "exchange_inflow", "smart_money_distribution"
        ])

        if bullish_signals > 0 and bearish_signals > 0:
            confidence *= 0.7  # Conflicting signals reduce confidence
        elif bullish_signals > 0 or bearish_signals > 0:
            confidence *= 1.1  # Confirming signals increase confidence

        return min(confidence, 1.0)

    def _calculate_risk_from_metrics(self, metrics: Dict[str, Any]) -> Tuple[OnChainRiskLevel, float, List[str]]:
        """Calculate risk level from metrics."""
        risk_score = 0.0
        factors = []

        # Check various risk factors
        whale_metrics = metrics.get("whale_activity", {})
        if whale_metrics:
            total_value = whale_metrics.get("total_value_usd", 0)
            if total_value > 10_000_000:
                risk_score += 0.3
                factors.append("Extreme whale activity")
            elif total_value > 5_000_000:
                risk_score += 0.15
                factors.append("High whale activity")

        exchange_metrics = metrics.get("exchange_flows", {})
        if exchange_metrics:
            net_flow = exchange_metrics.get("net_flow", 0)
            if abs(net_flow) > 5_000_000:
                risk_score += 0.2
                factors.append(f"Large exchange flow: ${abs(net_flow):,.0f}")

        holder_metrics = metrics.get("holders", {})
        concentration = holder_metrics.get("concentration", {}).get("top_10_percent", 0)
        if concentration > 0.8:
            risk_score += 0.2
            factors.append("High holder concentration")
        elif concentration > 0.6:
            risk_score += 0.1

        volume_metrics = metrics.get("volume", {})
        if volume_metrics.get("unusual_activity", False):
            risk_score += 0.15
            factors.append("Unusual volume patterns")

        # Determine level
        if risk_score >= 0.7:
            risk_level = OnChainRiskLevel.CRITICAL
        elif risk_score >= 0.5:
            risk_level = OnChainRiskLevel.HIGH
        elif risk_score >= 0.3:
            risk_level = OnChainRiskLevel.MEDIUM
        elif risk_score >= 0.15:
            risk_level = OnChainRiskLevel.LOW
        else:
            risk_level = OnChainRiskLevel.VERY_LOW

        return risk_level, risk_score, factors

    def _generate_recommendations(
        self,
        analysis_type: AnalysisType,
        metrics: Dict[str, Any],
        signals: List[Dict[str, Any]],
        anomalies: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable recommendations from analysis."""
        recommendations = []

        # High-level recommendations based on findings
        for signal in signals:
            if signal.get("type") == "whale_accumulation":
                recommendations.append("Consider accumulating as whales are buying")
            elif signal.get("type") == "smart_money_accumulation":
                recommendations.append("Smart money is accumulating - watch for potential upward movement")
            elif signal.get("type") == "large_net_inflow":
                recommendations.append("Large exchange inflow detected - may indicate impending selling pressure")
            elif signal.get("type") == "large_net_outflow":
                recommendations.append("Large exchange outflow detected - may indicate accumulation")
            elif signal.get("type") == "high_concentration":
                recommendations.append("High holder concentration - consider profit taking")
            elif signal.get("type") == "volume_spike":
                recommendations.append("Volume spike detected - monitor for price action")
            elif signal.get("type") == "gas_spike":
                recommendations.append("Gas spike detected - network congestion may affect trading")

        # Risk-based recommendations
        risk_level = metrics.get("risk_level")
        if risk_level in [OnChainRiskLevel.HIGH, OnChainRiskLevel.CRITICAL]:
            recommendations.append("High on-chain risk detected - consider reducing position size")
        elif risk_level == OnChainRiskLevel.MEDIUM:
            recommendations.append("Moderate on-chain risk - maintain normal position sizing")

        # Anomaly-based recommendations
        for anomaly in anomalies:
            recommendations.append(f"Anomaly detected in {anomaly.get('metric')}: {anomaly.get('explanation')}")

        return recommendations

    def _generate_anomaly_explanation(
        self,
        metric: str,
        current_value: float,
        mean: float,
        std: float,
        deviation: float
    ) -> str:
        """Generate human-readable anomaly explanation."""
        return (
            f"{metric} deviates significantly from normal (deviation: {deviation:.2f}σ). "
            f"Current: {current_value:.2f}, Expected range: {mean - 2*std:.2f} - {mean + 2*std:.2f}"
        )

    def _deduplicate_signals(
        self,
        signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate signals and prioritize."""
        unique_signals = []
        seen_types = set()

        # Sort by severity (high > medium > low)
        severity_order = {"high": 3, "medium": 2, "low": 1}
        signals.sort(
            key=lambda s: severity_order.get(s.get("severity", "low"), 0),
            reverse=True
        )

        for signal in signals:
            signal_type = signal.get("type")
            if signal_type and signal_type not in seen_types:
                seen_types.add(signal_type)
                unique_signals.append(signal)

        return unique_signals

    def _calculate_sentiment_from_metrics(self, metrics: Dict[str, Any]) -> Tuple[MarketSentiment, float]:
        """Calculate sentiment from metrics."""
        # Placeholder - uses same logic as above
        return MarketSentiment.NEUTRAL, 0.0

    # -----------------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------------

    def register_analysis_callback(self, callback: Callable) -> None:
        """Register a callback for analysis results."""
        self._analysis_callbacks.append(callback)

    def register_anomaly_callback(self, callback: Callable) -> None:
        """Register a callback for anomaly detection."""
        self._anomaly_callbacks.append(callback)

    async def _notify_callbacks(
        self,
        callbacks: List[Callable],
        data: Any
    ) -> None:
        """Execute registered callbacks."""
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in callback: {e}")

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the analyzer and sub-analyzers."""
        self._running = True

        # Start sub-analyzers
        await self.gas_analyzer.start()
        await self.holder_analyzer.start()
        await self.whale_tracker.start()
        await self.smart_money_analyzer.start()

        logger.info("OnChainAnalyzer started")

    async def stop(self) -> None:
        """Stop the analyzer and sub-analyzers."""
        self._running = False

        # Stop sub-analyzers
        await self.gas_analyzer.stop()
        await self.holder_analyzer.stop()
        await self.whale_tracker.stop()
        await self.smart_money_analyzer.stop()

        logger.info("OnChainAnalyzer stopped")

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._metrics,
            "cache_size": len(self._results_cache),
            "historical_results": len(self._historical_results),
            "snapshots": len(self._snapshots),
            "sub_analyzers": {
                "gas": self.gas_analyzer.get_metrics() if hasattr(self.gas_analyzer, 'get_metrics') else {},
                "whale": self.whale_tracker.get_metrics() if hasattr(self.whale_tracker, 'get_metrics') else {},
                "smart_money": self.smart_money_analyzer.get_metrics() if hasattr(self.smart_money_analyzer, 'get_metrics') else {},
            }
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_onchain_analyzer(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> OnChainAnalyzer:
    """Factory function to create an OnChainAnalyzer instance."""
    if config:
        parsed_config = OnChainAnalysisConfig(**config)
    else:
        parsed_config = OnChainAnalysisConfig(chain=web3_client.chain_name)

    return OnChainAnalyzer(
        web3_client=web3_client,
        config=parsed_config
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the on-chain analyzer
    pass

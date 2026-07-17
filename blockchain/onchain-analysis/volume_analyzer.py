# blockchain/onchain-analysis/volume_analyzer.py
# NEXUS AI TRADING SYSTEM - Advanced On-Chain Volume Analysis Engine
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced on-chain volume analysis engine for detecting volume patterns,
anomalies, and trends across tokens, exchanges, and timeframes.
Provides real-time volume analytics for trading decisions.
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

logger = get_logger("nexus.onchain.volume_analyzer")


# ============================================================================
# Enums & Constants
# ============================================================================

class VolumeType(str, Enum):
    """Types of volume analysis."""
    TRANSACTION_VOLUME = "transaction_volume"
    TRADING_VOLUME = "trading_volume"
    EXCHANGE_VOLUME = "exchange_volume"
    PROTOCOL_VOLUME = "protocol_volume"
    WHALE_VOLUME = "whale_volume"
    RETAIL_VOLUME = "retail_volume"
    NETWORK_VOLUME = "network_volume"
    DEFI_VOLUME = "defi_volume"


class VolumePattern(str, Enum):
    """Volume patterns detected."""
    SPIKE = "spike"
    DROP = "drop"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    CHOPPY = "choppy"
    STEADY = "steady"
    BREAKOUT = "breakout"
    FAKEOUT = "fakeout"
    EXHAUSTION = "exhaustion"


class VolumeConfidence(str, Enum):
    """Confidence level for volume analysis."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CONFIRMED = "confirmed"


@dataclass
class VolumeDataPoint:
    """Single volume data point."""
    timestamp: datetime
    volume: float
    volume_usd: float
    count: int
    average_size: float
    unique_addresses: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VolumeAnalysis:
    """Complete volume analysis result."""
    timestamp: datetime
    token: Optional[str] = None
    volume_type: VolumeType
    total_volume_usd: float
    average_volume_usd: float
    median_volume_usd: float
    volume_change_24h: float
    volume_change_7d: float
    volatility: float
    pattern: VolumePattern
    confidence: VolumeConfidence
    anomalies: List[Dict[str, Any]]
    breakdown: Dict[str, float]
    historical_stats: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VolumeBreakdown:
    """Breakdown of volume by category."""
    by_hour: Dict[int, float]
    by_day: Dict[str, float]
    by_exchange: Dict[str, float]
    by_token: Dict[str, float]
    by_address_type: Dict[str, float]
    by_transaction_size: Dict[str, float]


@dataclass
class VolumeAnomaly:
    """Volume anomaly detection result."""
    detected: bool
    severity: float
    metric: str
    current_value: float
    expected_range: Tuple[float, float]
    deviation_std: float
    pattern: VolumePattern
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Core Volume Analyzer
# ============================================================================

class VolumeAnalyzer:
    """
    Advanced on-chain volume analysis engine.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.config = config or {}

        # Volume data storage
        self._volume_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._volume_aggregates: Dict[str, Dict[str, Any]] = {}
        self._anomalies: List[VolumeAnomaly] = []
        self._analysis_cache: Dict[str, VolumeAnalysis] = {}

        # State management
        self._running = False
        self._lock = asyncio.Lock()

        # Performance metrics
        self._performance = {
            "data_points_collected": 0,
            "analyses_performed": 0,
            "anomalies_detected": 0,
            "avg_analysis_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        logger.info(
            "VolumeAnalyzer initialized",
            extra={"chain": web3_client.chain_name}
        )

    # -----------------------------------------------------------------------
    # Volume Data Collection
    # -----------------------------------------------------------------------

    async def add_volume_data(
        self,
        key: str,
        volume: float,
        volume_usd: float,
        count: int = 1,
        unique_addresses: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a volume data point."""
        timestamp = timestamp or datetime.utcnow()

        data_point = VolumeDataPoint(
            timestamp=timestamp,
            volume=volume,
            volume_usd=volume_usd,
            count=count,
            average_size=volume / count if count > 0 else 0,
            unique_addresses=unique_addresses or count,
            metadata=metadata or {},
        )

        async with self._lock:
            self._volume_history[key].append(data_point)
            self._performance["data_points_collected"] += 1

            # Invalidate cache for this key
            if key in self._analysis_cache:
                del self._analysis_cache[key]

        # Check for anomalies
        await self._detect_anomalies(key)

    async def add_batch_volume_data(
        self,
        key: str,
        data_points: List[Dict[str, Any]]
    ) -> None:
        """Add multiple volume data points."""
        for point in data_points:
            await self.add_volume_data(
                key=key,
                volume=point.get("volume", 0),
                volume_usd=point.get("volume_usd", 0),
                count=point.get("count", 1),
                unique_addresses=point.get("unique_addresses"),
                metadata=point.get("metadata"),
                timestamp=point.get("timestamp"),
            )

    # -----------------------------------------------------------------------
    # Volume Analysis
    # -----------------------------------------------------------------------

    async def analyze_volume(
        self,
        key: str,
        hours: int = 24,
        force_refresh: bool = False,
        volume_type: VolumeType = VolumeType.TRADING_VOLUME,
    ) -> Optional[VolumeAnalysis]:
        """Analyze volume for a specific key."""
        cache_key = f"{key}_{hours}_{volume_type.value}"

        if not force_refresh and cache_key in self._analysis_cache:
            self._performance["cache_hits"] += 1
            return self._analysis_cache[cache_key]

        self._performance["cache_misses"] += 1
        start_time = time.time()

        try:
            data = list(self._volume_history.get(key, []))
            if not data:
                return None

            # Filter by time
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            recent_data = [d for d in data if d.timestamp >= cutoff]

            if not recent_data:
                return None

            # Calculate metrics
            total_volume = sum(d.volume_usd for d in recent_data)
            volumes = [d.volume_usd for d in recent_data]
            avg_volume = np.mean(volumes) if volumes else 0
            median_volume = np.median(volumes) if volumes else 0

            # Calculate historical metrics
            older_data = [d for d in data if d.timestamp < cutoff]
            older_volumes = [d.volume_usd for d in older_data] if older_data else []

            # Calculate changes
            volume_change_24h = self._calculate_change(
                recent_data,
                [d for d in data if d.timestamp >= cutoff - timedelta(hours=48) and d.timestamp < cutoff]
            )

            volume_change_7d = self._calculate_change(
                recent_data,
                [d for d in data if d.timestamp >= cutoff - timedelta(days=7) and d.timestamp < cutoff]
            )

            # Calculate volatility
            volatility = np.std(volumes) / (avg_volume + 1e-10) if volumes else 0

            # Detect pattern
            pattern, confidence = self._detect_volume_pattern(volumes)

            # Analyze breakdown
            breakdown = self._analyze_breakdown(recent_data)

            # Detect anomalies
            anomalies = await self._detect_anomalies(key, return_results=True)

            # Create analysis result
            analysis = VolumeAnalysis(
                timestamp=datetime.utcnow(),
                token=key.split(":")[0] if ":" in key else None,
                volume_type=volume_type,
                total_volume_usd=total_volume,
                average_volume_usd=avg_volume,
                median_volume_usd=median_volume,
                volume_change_24h=volume_change_24h,
                volume_change_7d=volume_change_7d,
                volatility=volatility,
                pattern=pattern,
                confidence=confidence,
                anomalies=[a.__dict__ for a in anomalies],
                breakdown=breakdown,
                historical_stats={
                    "data_points": len(recent_data),
                    "max_volume": max(volumes) if volumes else 0,
                    "min_volume": min(volumes) if volumes else 0,
                    "std_dev": np.std(volumes) if volumes else 0,
                },
                metadata={
                    "key": key,
                    "hours": hours,
                    "data_points_collected": len(data),
                    "recent_data_points": len(recent_data),
                }
            )

            # Cache result
            self._analysis_cache[cache_key] = analysis
            self._performance["analyses_performed"] += 1

            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["avg_analysis_time_ms"] = (
                (self._performance["avg_analysis_time_ms"] *
                 (self._performance["analyses_performed"] - 1) +
                 elapsed_ms) / self._performance["analyses_performed"]
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing volume for {key}: {e}")
            return None

    def _calculate_change(
        self,
        current_data: List[VolumeDataPoint],
        previous_data: List[VolumeDataPoint]
    ) -> float:
        """Calculate percentage change between two periods."""
        if not current_data or not previous_data:
            return 0.0

        current_total = sum(d.volume_usd for d in current_data)
        previous_total = sum(d.volume_usd for d in previous_data)

        if previous_total == 0:
            return 100.0 if current_total > 0 else 0.0

        return ((current_total - previous_total) / previous_total) * 100

    def _detect_volume_pattern(
        self,
        volumes: List[float]
    ) -> Tuple[VolumePattern, VolumeConfidence]:
        """Detect volume pattern from time series."""
        if len(volumes) < 10:
            return VolumePattern.STEADY, VolumeConfidence.VERY_LOW

        # Calculate statistics
        mean = np.mean(volumes)
        std = np.std(volumes)

        # Calculate trend
        trend = self._calculate_trend(volumes)

        # Check for spikes
        max_volume = max(volumes)
        if max_volume > mean + 3 * std:
            return VolumePattern.SPIKE, VolumeConfidence.HIGH

        # Check for drops
        min_volume = min(volumes)
        if min_volume < mean - 2 * std:
            return VolumePattern.DROP, VolumeConfidence.MEDIUM

        # Check for trends
        if abs(trend) > 0.3:
            if trend > 0:
                # Check if it's accumulation or just trending up
                if self._is_accumulation_pattern(volumes):
                    return VolumePattern.ACCUMULATION, VolumeConfidence.MEDIUM
                return VolumePattern.TRENDING_UP, VolumeConfidence.MEDIUM
            else:
                if self._is_distribution_pattern(volumes):
                    return VolumePattern.DISTRIBUTION, VolumeConfidence.MEDIUM
                return VolumePattern.TRENDING_DOWN, VolumeConfidence.MEDIUM

        # Check for choppiness
        if std / mean > 0.5:
            return VolumePattern.CHOPPY, VolumeConfidence.LOW

        # Check for breakout
        if self._is_breakout_pattern(volumes):
            return VolumePattern.BREAKOUT, VolumeConfidence.MEDIUM

        return VolumePattern.STEADY, VolumeConfidence.MEDIUM

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend using linear regression."""
        if len(values) < 2:
            return 0.0

        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)

        # Normalize slope by mean
        mean = np.mean(values)
        if mean == 0:
            return 0.0

        return slope / mean

    def _is_accumulation_pattern(self, values: List[float]) -> bool:
        """Check if volume pattern indicates accumulation."""
        if len(values) < 20:
            return False

        # Increasing volume with decreasing volatility
        recent = values[-10:]
        earlier = values[-20:-10]

        if len(recent) >= 5 and len(earlier) >= 5:
            recent_avg = np.mean(recent)
            earlier_avg = np.mean(earlier)

            if recent_avg > earlier_avg * 1.2:
                recent_std = np.std(recent)
                earlier_std = np.std(earlier)
                if recent_std < earlier_std * 0.8:
                    return True

        return False

    def _is_distribution_pattern(self, values: List[float]) -> bool:
        """Check if volume pattern indicates distribution."""
        if len(values) < 20:
            return False

        # Decreasing volume with increasing volatility
        recent = values[-10:]
        earlier = values[-20:-10]

        if len(recent) >= 5 and len(earlier) >= 5:
            recent_avg = np.mean(recent)
            earlier_avg = np.mean(earlier)

            if recent_avg < earlier_avg * 0.8:
                recent_std = np.std(recent)
                earlier_std = np.std(earlier)
                if recent_std > earlier_std * 1.2:
                    return True

        return False

    def _is_breakout_pattern(self, values: List[float]) -> bool:
        """Check if volume pattern indicates breakout."""
        if len(values) < 30:
            return False

        # Look for consolidation followed by volume increase
        recent = values[-5:]
        consolidation = values[-30:-5]

        if len(recent) >= 3 and len(consolidation) >= 10:
            recent_avg = np.mean(recent)
            cons_avg = np.mean(consolidation)
            cons_std = np.std(consolidation)

            if recent_avg > cons_avg + 2 * cons_std:
                # Check if volume increased
                recent_vol_avg = np.mean([values[-5:]])
                prev_vol_avg = np.mean([values[-15:-5]])
                if recent_vol_avg > prev_vol_avg * 1.5:
                    return True

        return False

    def _analyze_breakdown(
        self,
        data_points: List[VolumeDataPoint]
    ) -> Dict[str, float]:
        """Analyze volume breakdown."""
        breakdown = {
            "by_address_type": defaultdict(float),
            "by_transaction_size": defaultdict(float),
        }

        for point in data_points:
            # By address type (metadata assumed to contain type)
            addr_type = point.metadata.get("address_type", "unknown")
            breakdown["by_address_type"][addr_type] += point.volume_usd

            # By transaction size
            size = point.volume_usd / point.count if point.count > 0 else 0
            if size < 1000:
                size_category = "micro"
            elif size < 10000:
                size_category = "small"
            elif size < 100000:
                size_category = "medium"
            elif size < 1000000:
                size_category = "large"
            else:
                size_category = "whale"
            breakdown["by_transaction_size"][size_category] += point.volume_usd

        return {k: dict(v) for k, v in breakdown.items()}

    # -----------------------------------------------------------------------
    # Anomaly Detection
    # -----------------------------------------------------------------------

    async def _detect_anomalies(
        self,
        key: str,
        return_results: bool = False
    ) -> List[VolumeAnomaly]:
        """Detect volume anomalies."""
        anomalies = []
        data = list(self._volume_history.get(key, []))

        if len(data) < 20:
            return anomalies

        # Get recent data
        recent = data[-10:]
        historical = data[:-10]

        if not historical:
            return anomalies

        # Calculate historical stats
        hist_volumes = [d.volume_usd for d in historical]
        mean = np.mean(hist_volumes)
        std = np.std(hist_volumes)

        if std == 0:
            return anomalies

        # Check each recent point
        for point in recent:
            z_score = (point.volume_usd - mean) / std

            if abs(z_score) > 3:
                anomaly = VolumeAnomaly(
                    detected=True,
                    severity=min(1.0, abs(z_score) / 6),
                    metric="volume_usd",
                    current_value=point.volume_usd,
                    expected_range=(
                        mean - 2 * std,
                        mean + 2 * std
                    ),
                    deviation_std=z_score,
                    pattern=VolumePattern.SPIKE if z_score > 0 else VolumePattern.DROP,
                    timestamp=point.timestamp,
                    metadata={
                        "key": key,
                        "z_score": z_score,
                        "historical_mean": mean,
                        "historical_std": std,
                    }
                )
                anomalies.append(anomaly)
                self._performance["anomalies_detected"] += 1

        # Store anomalies
        self._anomalies.extend(anomalies)

        # Clean up old anomalies
        cutoff = datetime.utcnow() - timedelta(days=7)
        self._anomalies = [a for a in self._anomalies if a.timestamp >= cutoff]

        return anomalies

    # -----------------------------------------------------------------------
    # Advanced Volume Metrics
    # -----------------------------------------------------------------------

    async def calculate_volume_metrics(
        self,
        key: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Calculate advanced volume metrics."""
        data = list(self._volume_history.get(key, []))
        if not data:
            return {}

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [d for d in data if d.timestamp >= cutoff]

        if not recent:
            return {}

        volumes = [d.volume_usd for d in recent]

        # Calculate VWAP (Volume Weighted Average Price)
        # Assuming we have price data in metadata
        total_value = 0
        total_volume = 0
        for point in recent:
            price = point.metadata.get("price", 0)
            if price > 0:
                total_value += point.volume_usd * price
                total_volume += point.volume_usd

        vwap = total_value / total_volume if total_volume > 0 else 0

        # Calculate volume profile
        volume_profile = self._calculate_volume_profile(volumes)

        return {
            "vwap": vwap,
            "volume_profile": volume_profile,
            "volume_skew": self._calculate_volume_skew(volumes),
            "volume_kurtosis": self._calculate_volume_kurtosis(volumes),
            "volume_momentum": self._calculate_volume_momentum(volumes),
            "volume_entropy": self._calculate_volume_entropy(volumes),
        }

    def _calculate_volume_profile(self, volumes: List[float]) -> Dict[str, Any]:
        """Calculate volume profile distribution."""
        if not volumes:
            return {}

        sorted_volumes = sorted(volumes)
        n = len(sorted_volumes)

        return {
            "percentile_25": np.percentile(sorted_volumes, 25),
            "percentile_50": np.percentile(sorted_volumes, 50),
            "percentile_75": np.percentile(sorted_volumes, 75),
            "percentile_90": np.percentile(sorted_volumes, 90),
            "percentile_95": np.percentile(sorted_volumes, 95),
            "iqr": np.percentile(sorted_volumes, 75) - np.percentile(sorted_volumes, 25),
        }

    def _calculate_volume_skew(self, volumes: List[float]) -> float:
        """Calculate volume skew (asymmetry)."""
        if len(volumes) < 3:
            return 0.0

        mean = np.mean(volumes)
        std = np.std(volumes)
        if std == 0:
            return 0.0

        skew = np.mean(((volumes - mean) / std) ** 3)
        return float(skew)

    def _calculate_volume_kurtosis(self, volumes: List[float]) -> float:
        """Calculate volume kurtosis (tailedness)."""
        if len(volumes) < 4:
            return 0.0

        mean = np.mean(volumes)
        std = np.std(volumes)
        if std == 0:
            return 0.0

        kurtosis = np.mean(((volumes - mean) / std) ** 4) - 3
        return float(kurtosis)

    def _calculate_volume_momentum(self, volumes: List[float]) -> float:
        """Calculate volume momentum."""
        if len(volumes) < 20:
            return 0.0

        # Compare recent volume to historical average
        recent = volumes[-5:]
        historical = volumes[:-5]

        recent_avg = np.mean(recent)
        hist_avg = np.mean(historical)

        if hist_avg == 0:
            return 0.0

        return (recent_avg - hist_avg) / hist_avg

    def _calculate_volume_entropy(self, volumes: List[float]) -> float:
        """Calculate volume entropy (randomness)."""
        if len(volumes) < 10:
            return 0.0

        # Normalize volumes to probability distribution
        total = sum(volumes)
        if total == 0:
            return 0.0

        probs = [v / total for v in volumes if v > 0]

        # Calculate Shannon entropy
        entropy = -sum(p * math.log(p) for p in probs)
        max_entropy = math.log(len(probs))

        return entropy / max_entropy if max_entropy > 0 else 0.0

    # -----------------------------------------------------------------------
    # Volume Comparison
    # -----------------------------------------------------------------------

    async def compare_volumes(
        self,
        keys: List[str],
        hours: int = 24
    ) -> Dict[str, Any]:
        """Compare volumes across multiple keys."""
        results = {}

        for key in keys:
            analysis = await self.analyze_volume(key, hours)
            if analysis:
                results[key] = {
                    "total_volume": analysis.total_volume_usd,
                    "average_volume": analysis.average_volume_usd,
                    "change_24h": analysis.volume_change_24h,
                    "pattern": analysis.pattern.value,
                    "volatility": analysis.volatility,
                }

        if not results:
            return {}

        # Calculate rankings
        sorted_by_volume = sorted(
            results.items(),
            key=lambda x: x[1]["total_volume"],
            reverse=True
        )

        sorted_by_change = sorted(
            results.items(),
            key=lambda x: x[1]["change_24h"],
            reverse=True
        )

        # Calculate aggregate metrics
        total_volume = sum(r["total_volume"] for r in results.values())
        avg_volume = np.mean([r["total_volume"] for r in results.values()])

        return {
            "rankings": {
                "by_volume": [{"key": k, "volume": v["total_volume"]} for k, v in sorted_by_volume],
                "by_change": [{"key": k, "change": v["change_24h"]} for k, v in sorted_by_change],
            },
            "aggregates": {
                "total_volume": total_volume,
                "average_volume": avg_volume,
                "active_keys": len(results),
                "keys_with_growth": sum(1 for r in results.values() if r["change_24h"] > 0),
                "keys_with_decline": sum(1 for r in results.values() if r["change_24h"] < 0),
            },
            "dominance": {
                k: v["total_volume"] / total_volume if total_volume > 0 else 0
                for k, v in results.items()
            },
        }

    # -----------------------------------------------------------------------
    # Volume Prediction
    # -----------------------------------------------------------------------

    async def predict_volume(
        self,
        key: str,
        hours_ahead: int = 1
    ) -> Dict[str, Any]:
        """Predict future volume."""
        data = list(self._volume_history.get(key, []))
        if len(data) < 50:
            return {
                "predicted_volume": 0,
                "confidence": 0.0,
                "range_low": 0,
                "range_high": 0,
            }

        # Use time series forecasting
        volumes = [d.volume_usd for d in data]

        # Simple moving average
        window = min(12, len(volumes) // 4)  # Use last 25% of data
        recent_volumes = volumes[-window:]

        # Calculate weighted average (more weight to recent)
        weights = np.linspace(0.5, 1.0, len(recent_volumes))
        weights = weights / weights.sum()
        predicted = np.average(recent_volumes, weights=weights)

        # Calculate confidence based on volatility
        std = np.std(recent_volumes)
        confidence = max(0, 1 - (std / (predicted + 1e-10)))

        # Adjust for trend
        if len(volumes) >= 20:
            trend = self._calculate_trend(volumes[-20:])
            predicted *= (1 + trend)

        return {
            "predicted_volume": predicted,
            "confidence": min(1.0, confidence),
            "range_low": max(0, predicted - 2 * std),
            "range_high": predicted + 2 * std,
            "trend": self._calculate_trend(volumes[-20:]) if len(volumes) >= 20 else 0,
            "volatility": std / (predicted + 1e-10),
        }

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_volume_history(
        self,
        key: str,
        hours: Optional[int] = None
    ) -> List[VolumeDataPoint]:
        """Get volume history for a key."""
        data = list(self._volume_history.get(key, []))

        if hours:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            data = [d for d in data if d.timestamp >= cutoff]

        return data

    def clear_cache(self) -> None:
        """Clear analysis cache."""
        self._analysis_cache.clear()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "unique_keys": len(self._volume_history),
            "total_data_points": sum(len(d) for d in self._volume_history.values()),
            "cached_analyses": len(self._analysis_cache),
            "stored_anomalies": len(self._anomalies),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the analyzer."""
        self._running = True
        logger.info("VolumeAnalyzer started")

    async def stop(self) -> None:
        """Stop the analyzer."""
        self._running = False
        logger.info("VolumeAnalyzer stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_volume_analyzer(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> VolumeAnalyzer:
    """Factory function to create a VolumeAnalyzer instance."""
    return VolumeAnalyzer(
        web3_client=web3_client,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the volume analyzer
    pass

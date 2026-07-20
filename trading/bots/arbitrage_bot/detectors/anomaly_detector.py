"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Anomaly Detector
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced anomaly detection system for arbitrage with:
- Price anomaly detection (statistical, ML-based)
- Volume anomaly detection
- Spread anomaly detection
- Order book anomaly detection
- Multi-dimensional anomaly detection
- Real-time anomaly scoring
- Anomaly pattern recognition
- Alert generation and management
"""

import asyncio
import json
import logging
import math
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import numpy as np

# Optional imports for advanced ML
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    stats = None

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    from sklearn.covariance import EllipticEnvelope
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    IsolationForest = None
    StandardScaler = None
    EllipticEnvelope = None

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    F = None

# Local imports
from ..data.base import BaseDetector
from ..data.exceptions import (
    DetectorError,
    DetectionError,
    DataNotFoundError,
)
from ..data.price_manager import PriceManager, PriceSource, NormalizedPrice, PriceSnapshot
from ..data.volume_manager import VolumeManager, VolumeData, VolumeSnapshot
from ..data.spread_manager import SpreadManager, SpreadData, SpreadSnapshot
from ..data.order_book_manager import OrderBookManager, OrderBook, OrderBookSnapshot
from .config import AnomalyDetectorConfig
from .constants import (
    ANOMALY_SCORE_THRESHOLD,
    ANOMALY_WINDOW_SIZE,
    ANOMALY_TRAINING_SIZE,
    PRICE_ANOMALY_WEIGHT,
    VOLUME_ANOMALY_WEIGHT,
    SPREAD_ANOMALY_WEIGHT,
    ORDER_BOOK_ANOMALY_WEIGHT,
    PATTERN_ANOMALY_WEIGHT,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class AnomalyType(str, Enum):
    """Types of anomalies."""
    PRICE = "price"
    VOLUME = "volume"
    SPREAD = "spread"
    ORDER_BOOK = "order_book"
    PATTERN = "pattern"
    MULTIDIMENSIONAL = "multidimensional"
    SEASONAL = "seasonal"
    TREND = "trend"
    SPIK = "spike"
    DROP = "drop"
    FLASH_CRASH = "flash_crash"
    PUMP = "pump"
    DUMP = "dump"
    LIQUIDITY = "liquidity"
    ARBITRAGE = "arbitrage"


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(str, Enum):
    """Status of anomaly detection."""
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"
    INVESTIGATING = "investigating"


class DetectionMethod(str, Enum):
    """Methods for anomaly detection."""
    ZSCORE = "zscore"
    IQR = "iqr"
    MAD = "mad"  # Median Absolute Deviation
    ISOLATION_FOREST = "isolation_forest"
    ELLIPTIC_ENVELOPE = "elliptic_envelope"
    AUTOENCODER = "autoencoder"
    LSTM = "lstm"
    WAVELET = "wavelet"
    HODRICK_PRESCOTT = "hodrick_prescott"
    GRUBBS = "grubbs"
    EWMA = "ewma"
    CUSUM = "cusum"
    BAYESIAN = "bayesian"
    ENSEMBLE = "ensemble"


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection."""
    
    id: str = field(default_factory=lambda: f"anomaly_{int(time.time() * 1000)}")
    symbol: str
    exchange: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    score: float
    detection_method: DetectionMethod
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    deviation: Optional[float] = None
    threshold: float = ANOMALY_SCORE_THRESHOLD
    status: AnomalyStatus = AnomalyStatus.DETECTED
    metadata: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, float] = field(default_factory=dict)
    patterns: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'anomaly_type': self.anomaly_type.value if isinstance(self.anomaly_type, AnomalyType) else self.anomaly_type,
            'severity': self.severity.value if isinstance(self.severity, AnomalySeverity) else self.severity,
            'score': self.score,
            'detection_method': self.detection_method.value if isinstance(self.detection_method, DetectionMethod) else self.detection_method,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'expected_value': self.expected_value,
            'actual_value': self.actual_value,
            'deviation': self.deviation,
            'threshold': self.threshold,
            'status': self.status.value if isinstance(self.status, AnomalyStatus) else self.status,
            'metadata': self.metadata,
            'features': self.features,
            'patterns': self.patterns,
            'context': self.context,
        }


@dataclass
class AnomalyPattern:
    """Identified anomaly pattern."""
    
    pattern_id: str = field(default_factory=lambda: f"pattern_{int(time.time() * 1000)}")
    symbol: str
    exchange: str
    pattern_type: str
    start_time: datetime
    end_time: datetime
    confidence: float
    data_points: List[Dict[str, Any]]
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pattern_id': self.pattern_id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'pattern_type': self.pattern_type,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'confidence': self.confidence,
            'data_points': self.data_points,
            'description': self.description,
            'metadata': self.metadata,
        }


@dataclass
class AnomalyAlert:
    """Alert for detected anomaly."""
    
    alert_id: str = field(default_factory=lambda: f"alert_{int(time.time() * 1000)}")
    anomaly: AnomalyDetectionResult
    message: str
    severity: AnomalySeverity
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    channels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'anomaly': self.anomaly.to_dict(),
            'message': self.message,
            'severity': self.severity.value if isinstance(self.severity, AnomalySeverity) else self.severity,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'acknowledged_by': self.acknowledged_by,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_notes': self.resolution_notes,
            'channels': self.channels,
        }


@dataclass
class AnomalyStatistics:
    """Statistics for anomaly detection."""
    
    symbol: str
    exchange: str
    total_detections: int = 0
    confirmed_anomalies: int = 0
    false_positives: int = 0
    resolution_rate: float = 0.0
    avg_severity: float = 0.0
    avg_score: float = 0.0
    detection_distribution: Dict[str, int] = field(default_factory=dict)
    last_detection: Optional[datetime] = None
    detection_rate_per_hour: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'total_detections': self.total_detections,
            'confirmed_anomalies': self.confirmed_anomalies,
            'false_positives': self.false_positives,
            'resolution_rate': self.resolution_rate,
            'avg_severity': self.avg_severity,
            'avg_score': self.avg_score,
            'detection_distribution': self.detection_distribution,
            'last_detection': self.last_detection.isoformat() if self.last_detection else None,
            'detection_rate_per_hour': self.detection_rate_per_hour,
            'timestamp': self.timestamp.isoformat(),
        }


# ============================================================
# ANOMALY DETECTOR IMPLEMENTATION
# ============================================================

class AnomalyDetector(BaseDetector):
    """
    Advanced anomaly detector with:
    - Multi-type anomaly detection
    - Statistical and ML-based methods
    - Pattern recognition
    - Real-time scoring
    - Alert management
    """

    def __init__(
        self,
        price_manager: PriceManager,
        volume_manager: Optional[VolumeManager] = None,
        spread_manager: Optional[SpreadManager] = None,
        order_book_manager: Optional[OrderBookManager] = None,
        config: Optional[AnomalyDetectorConfig] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize anomaly detector.

        Args:
            price_manager: PriceManager instance
            volume_manager: VolumeManager instance (optional)
            spread_manager: SpreadManager instance (optional)
            order_book_manager: OrderBookManager instance (optional)
            config: Configuration instance
            redis_client: Redis client for caching
        """
        self.price_manager = price_manager
        self.volume_manager = volume_manager
        self.spread_manager = spread_manager
        self.order_book_manager = order_book_manager
        self.config = config or AnomalyDetectorConfig()
        self.redis = redis_client

        # Storage
        self._detections: List[AnomalyDetectionResult] = []
        self._patterns: List[AnomalyPattern] = []
        self._alerts: List[AnomalyAlert] = []
        self._statistics: Dict[str, Dict[str, AnomalyStatistics]] = {}

        # History buffers
        self._price_history: Dict[str, Dict[str, deque]] = {}
        self._volume_history: Dict[str, Dict[str, deque]] = {}
        self._spread_history: Dict[str, Dict[str, deque]] = {}

        # ML models
        self._isolation_forests: Dict[str, Dict[str, IsolationForest]] = {}
        self._elliptic_envelopes: Dict[str, Dict[str, EllipticEnvelope]] = {}
        self._autoencoders: Dict[str, Dict[str, Any]] = {}
        self._scalers: Dict[str, Dict[str, StandardScaler]] = {}

        # Metrics
        self._metrics = {
            'total_detections': 0,
            'confirmed_anomalies': 0,
            'false_positives': 0,
            'avg_detection_time_ms': 0,
            'detections_per_second': 0,
            'last_detection_timestamp': None,
        }

        # Lock
        self._lock = asyncio.Lock()

        # Event handlers
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)

        logger.info("AnomalyDetector initialized")

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    async def detect_price_anomaly(
        self,
        exchange: str,
        symbol: str,
        price: Optional[Union[float, Decimal]] = None,
        method: DetectionMethod = DetectionMethod.ENSEMBLE,
    ) -> Optional[AnomalyDetectionResult]:
        """
        Detect price anomalies.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            price: Current price (optional)
            method: Detection method

        Returns:
            AnomalyDetectionResult or None
        """
        start_time = time.perf_counter()

        try:
            # Get price data
            if price is None:
                price_source = await self.price_manager.get_price(exchange, symbol)
                if price_source is None:
                    return None
                price = float(price_source.price)

            # Get price history
            history = await self._get_price_history(exchange, symbol, limit=100)
            if len(history) < ANOMALY_TRAINING_SIZE:
                return None

            # Detect anomalies
            result = await self._detect_price_anomaly(
                exchange, symbol, price, history, method
            )

            if result:
                await self._store_detection(result)
                await self._update_statistics(result)

            # Update metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._metrics['avg_detection_time_ms'] = (
                self._metrics['avg_detection_time_ms'] * 0.9 + elapsed_ms * 0.1
            )
            self._metrics['last_detection_timestamp'] = datetime.utcnow().isoformat()

            if result:
                await self._emit_event('anomaly_detected', result)

            return result

        except Exception as e:
            logger.error(f"Price anomaly detection failed for {exchange}:{symbol}: {e}")
            return None

    async def detect_volume_anomaly(
        self,
        exchange: str,
        symbol: str,
        volume: Optional[Union[float, Decimal]] = None,
        method: DetectionMethod = DetectionMethod.ENSEMBLE,
    ) -> Optional[AnomalyDetectionResult]:
        """
        Detect volume anomalies.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            volume: Current volume (optional)
            method: Detection method

        Returns:
            AnomalyDetectionResult or None
        """
        try:
            if self.volume_manager is None:
                return None

            # Get volume data
            if volume is None:
                volume_data = await self.volume_manager.get_volume(exchange, symbol)
                if volume_data is None:
                    return None
                volume = float(volume_data.volume)

            # Get volume history
            history = await self.volume_manager.get_volume_history(exchange, symbol, limit=100)
            if len(history) < ANOMALY_TRAINING_SIZE:
                return None

            # Convert history to floats
            volume_history = [float(v.volume) for v in history]

            # Detect anomalies
            result = await self._detect_volume_anomaly(
                exchange, symbol, volume, volume_history, method
            )

            if result:
                await self._store_detection(result)
                await self._update_statistics(result)
                await self._emit_event('anomaly_detected', result)

            return result

        except Exception as e:
            logger.error(f"Volume anomaly detection failed for {exchange}:{symbol}: {e}")
            return None

    async def detect_spread_anomaly(
        self,
        exchange: str,
        symbol: str,
        spread_pct: Optional[float] = None,
        method: DetectionMethod = DetectionMethod.ENSEMBLE,
    ) -> Optional[AnomalyDetectionResult]:
        """
        Detect spread anomalies.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            spread_pct: Current spread percentage (optional)
            method: Detection method

        Returns:
            AnomalyDetectionResult or None
        """
        try:
            if self.spread_manager is None:
                return None

            # Get spread data
            if spread_pct is None:
                spread_data = await self.spread_manager.get_spread(exchange, symbol)
                if spread_data is None:
                    return None
                spread_pct = spread_data.spread_pct

            # Get spread history
            history = await self.spread_manager.get_spread_history(exchange, symbol, limit=100)
            if len(history) < ANOMALY_TRAINING_SIZE:
                return None

            # Convert history to floats
            spread_history = [s.spread_pct for s in history]

            # Detect anomalies
            result = await self._detect_spread_anomaly(
                exchange, symbol, spread_pct, spread_history, method
            )

            if result:
                await self._store_detection(result)
                await self._update_statistics(result)
                await self._emit_event('anomaly_detected', result)

            return result

        except Exception as e:
            logger.error(f"Spread anomaly detection failed for {exchange}:{symbol}: {e}")
            return None

    async def detect_order_book_anomaly(
        self,
        exchange: str,
        symbol: str,
        method: DetectionMethod = DetectionMethod.ENSEMBLE,
    ) -> Optional[AnomalyDetectionResult]:
        """
        Detect order book anomalies.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            method: Detection method

        Returns:
            AnomalyDetectionResult or None
        """
        try:
            if self.order_book_manager is None:
                return None

            # Get order book snapshot
            snapshot = await self.order_book_manager.get_snapshot(exchange, symbol)
            if snapshot is None:
                return None

            # Extract features
            features = self._extract_order_book_features(snapshot)

            # Detect anomalies
            result = await self._detect_order_book_anomaly(
                exchange, symbol, features, method
            )

            if result:
                await self._store_detection(result)
                await self._update_statistics(result)
                await self._emit_event('anomaly_detected', result)

            return result

        except Exception as e:
            logger.error(f"Order book anomaly detection failed for {exchange}:{symbol}: {e}")
            return None

    async def detect_multidimensional_anomaly(
        self,
        exchange: str,
        symbol: str,
        features: Dict[str, float],
        method: DetectionMethod = DetectionMethod.ENSEMBLE,
    ) -> Optional[AnomalyDetectionResult]:
        """
        Detect multidimensional anomalies.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            features: Feature dictionary
            method: Detection method

        Returns:
            AnomalyDetectionResult or None
        """
        try:
            # Ensure we have enough features
            if len(features) < 3:
                return None

            # Get historical features
            historical_features = await self._get_historical_features(exchange, symbol)

            # Detect anomalies
            result = await self._detect_multidimensional_anomaly(
                exchange, symbol, features, historical_features, method
            )

            if result:
                await self._store_detection(result)
                await self._update_statistics(result)
                await self._emit_event('anomaly_detected', result)

            return result

        except Exception as e:
            logger.error(f"Multidimensional anomaly detection failed for {exchange}:{symbol}: {e}")
            return None

    async def detect_patterns(
        self,
        exchange: str,
        symbol: str,
        data: List[Dict[str, Any]],
        min_pattern_length: int = 5,
        similarity_threshold: float = 0.8,
    ) -> List[AnomalyPattern]:
        """
        Detect patterns in data.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            data: Data points
            min_pattern_length: Minimum pattern length
            similarity_threshold: Similarity threshold

        Returns:
            List of AnomalyPattern
        """
        try:
            patterns = []

            # Extract patterns using sliding window
            for i in range(len(data) - min_pattern_length):
                window = data[i:i + min_pattern_length]
                pattern_type = await self._identify_pattern_type(window)

                if pattern_type:
                    # Look for similar patterns
                    similar_patterns = await self._find_similar_patterns(
                        window, pattern_type, similarity_threshold
                    )

                    if similar_patterns:
                        pattern = AnomalyPattern(
                            symbol=symbol,
                            exchange=exchange,
                            pattern_type=pattern_type,
                            start_time=datetime.fromtimestamp(window[0].get('timestamp', time.time())),
                            end_time=datetime.fromtimestamp(window[-1].get('timestamp', time.time())),
                            confidence=await self._calculate_pattern_confidence(window, similar_patterns),
                            data_points=window,
                            description=f"Detected {pattern_type} pattern",
                        )
                        patterns.append(pattern)

            # Store patterns
            for pattern in patterns:
                self._patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.error(f"Pattern detection failed for {exchange}:{symbol}: {e}")
            return []

    async def get_detections(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        anomaly_type: Optional[Union[str, AnomalyType]] = None,
        severity: Optional[Union[str, AnomalySeverity]] = None,
        limit: int = 100,
    ) -> List[AnomalyDetectionResult]:
        """
        Get anomaly detections.

        Args:
            symbol: Symbol filter
            exchange: Exchange filter
            anomaly_type: Anomaly type filter
            severity: Severity filter
            limit: Maximum results

        Returns:
            List of AnomalyDetectionResult
        """
        results = self._detections.copy()

        if symbol:
            results = [r for r in results if r.symbol == symbol]
        if exchange:
            results = [r for r in results if r.exchange == exchange]
        if anomaly_type:
            if isinstance(anomaly_type, str):
                anomaly_type = AnomalyType(anomaly_type)
            results = [r for r in results if r.anomaly_type == anomaly_type]
        if severity:
            if isinstance(severity, str):
                severity = AnomalySeverity(severity)
            results = [r for r in results if r.severity == severity]

        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    async def get_alerts(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        severity: Optional[Union[str, AnomalySeverity]] = None,
        acknowledged: Optional[bool] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[AnomalyAlert]:
        """
        Get anomaly alerts.

        Args:
            symbol: Symbol filter
            exchange: Exchange filter
            severity: Severity filter
            acknowledged: Acknowledged status filter
            resolved: Resolved status filter
            limit: Maximum results

        Returns:
            List of AnomalyAlert
        """
        alerts = self._alerts.copy()

        if symbol:
            alerts = [a for a in alerts if a.anomaly.symbol == symbol]
        if exchange:
            alerts = [a for a in alerts if a.anomaly.exchange == exchange]
        if severity:
            if isinstance(severity, str):
                severity = AnomalySeverity(severity)
            alerts = [a for a in alerts if a.severity == severity]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]

        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        return alerts[:limit]

    async def get_statistics(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get anomaly statistics.

        Args:
            symbol: Symbol filter
            exchange: Exchange filter

        Returns:
            Dictionary with statistics
        """
        if symbol and exchange:
            stats = self._statistics.get(exchange, {}).get(symbol)
            return stats.to_dict() if stats else {}

        if symbol:
            stats_dict = {}
            for exchange_stats in self._statistics.values():
                if symbol in exchange_stats:
                    key = f"{exchange_stats[symbol].exchange}:{symbol}"
                    stats_dict[key] = exchange_stats[symbol].to_dict()
            return stats_dict

        if exchange:
            return {
                symbol: stats.to_dict()
                for symbol, stats in self._statistics.get(exchange, {}).items()
            }

        return {
            f"{e}:{s}": stats.to_dict()
            for e, symbols in self._statistics.items()
            for s, stats in symbols.items()
        }

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert ID
            acknowledged_by: Person acknowledging

        Returns:
            True if acknowledged
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.utcnow()
                alert.acknowledged_by = acknowledged_by
                await self._emit_event('alert_acknowledged', alert)
                return True
        return False

    async def resolve_alert(
        self,
        alert_id: str,
        resolution_notes: Optional[str] = None,
    ) -> bool:
        """
        Resolve an alert.

        Args:
            alert_id: Alert ID
            resolution_notes: Resolution notes

        Returns:
            True if resolved
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                alert.resolution_notes = resolution_notes
                await self._emit_event('alert_resolved', alert)
                return True
        return False

    def register_handler(
        self,
        event_type: str,
        handler: Callable,
    ) -> None:
        """
        Register an event handler.

        Args:
            event_type: Event type
            handler: Handler function
        """
        self._handlers[event_type].append(handler)

    async def clear(self) -> None:
        """Clear all stored data."""
        async with self._lock:
            self._detections.clear()
            self._patterns.clear()
            self._alerts.clear()
            self._statistics.clear()
            self._price_history.clear()
            self._volume_history.clear()
            self._spread_history.clear()
            self._isolation_forests.clear()
            self._elliptic_envelopes.clear()
            self._autoencoders.clear()
            self._scalers.clear()

        logger.info("AnomalyDetector cleared")

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    async def _get_price_history(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
    ) -> List[float]:
        """Get price history."""
        if exchange not in self._price_history:
            self._price_history[exchange] = {}
        if symbol not in self._price_history[exchange]:
            self._price_history[exchange][symbol] = deque(maxlen=1000)

        # Get from price manager if not enough data
        if len(self._price_history[exchange][symbol]) < limit:
            history = await self.price_manager.get_price_history(exchange, symbol, limit)
            for price in history:
                self._price_history[exchange][symbol].append(float(price))

        return list(self._price_history[exchange][symbol])

    async def _detect_price_anomaly(
        self,
        exchange: str,
        symbol: str,
        price: float,
        history: List[float],
        method: DetectionMethod,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect price anomalies using specified method."""
        if method == DetectionMethod.ZSCORE:
            return await self._detect_zscore_anomaly(
                exchange, symbol, price, history, AnomalyType.PRICE
            )
        elif method == DetectionMethod.IQR:
            return await self._detect_iqr_anomaly(
                exchange, symbol, price, history, AnomalyType.PRICE
            )
        elif method == DetectionMethod.MAD:
            return await self._detect_mad_anomaly(
                exchange, symbol, price, history, AnomalyType.PRICE
            )
        elif method == DetectionMethod.ISOLATION_FOREST:
            return await self._detect_isolation_forest_anomaly(
                exchange, symbol, price, history, AnomalyType.PRICE
            )
        elif method == DetectionMethod.ENSEMBLE:
            return await self._detect_ensemble_anomaly(
                exchange, symbol, price, history, AnomalyType.PRICE
            )
        else:
            return None

    async def _detect_volume_anomaly(
        self,
        exchange: str,
        symbol: str,
        volume: float,
        history: List[float],
        method: DetectionMethod,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect volume anomalies using specified method."""
        if method == DetectionMethod.ZSCORE:
            return await self._detect_zscore_anomaly(
                exchange, symbol, volume, history, AnomalyType.VOLUME
            )
        elif method == DetectionMethod.IQR:
            return await self._detect_iqr_anomaly(
                exchange, symbol, volume, history, AnomalyType.VOLUME
            )
        elif method == DetectionMethod.MAD:
            return await self._detect_mad_anomaly(
                exchange, symbol, volume, history, AnomalyType.VOLUME
            )
        elif method == DetectionMethod.ENSEMBLE:
            return await self._detect_ensemble_anomaly(
                exchange, symbol, volume, history, AnomalyType.VOLUME
            )
        else:
            return None

    async def _detect_spread_anomaly(
        self,
        exchange: str,
        symbol: str,
        spread_pct: float,
        history: List[float],
        method: DetectionMethod,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect spread anomalies using specified method."""
        if method == DetectionMethod.ZSCORE:
            return await self._detect_zscore_anomaly(
                exchange, symbol, spread_pct, history, AnomalyType.SPREAD
            )
        elif method == DetectionMethod.IQR:
            return await self._detect_iqr_anomaly(
                exchange, symbol, spread_pct, history, AnomalyType.SPREAD
            )
        elif method == DetectionMethod.ENSEMBLE:
            return await self._detect_ensemble_anomaly(
                exchange, symbol, spread_pct, history, AnomalyType.SPREAD
            )
        else:
            return None

    async def _detect_zscore_anomaly(
        self,
        exchange: str,
        symbol: str,
        value: float,
        history: List[float],
        anomaly_type: AnomalyType,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect anomaly using z-score method."""
        if len(history) < 10:
            return None

        mean = statistics.mean(history[-50:])
        std = statistics.stdev(history[-50:]) if len(history[-50:]) > 1 else 0

        if std == 0:
            return None

        zscore = abs((value - mean) / std)

        if zscore > 3.0:
            severity = AnomalySeverity.MEDIUM
            if zscore > 5.0:
                severity = AnomalySeverity.HIGH
            elif zscore > 8.0:
                severity = AnomalySeverity.CRITICAL

            return AnomalyDetectionResult(
                symbol=symbol,
                exchange=exchange,
                anomaly_type=anomaly_type,
                severity=severity,
                score=zscore,
                detection_method=DetectionMethod.ZSCORE,
                data={'value': value, 'mean': mean, 'std': std},
                expected_value=mean,
                actual_value=value,
                deviation=(value - mean) / mean * 100 if mean != 0 else 0,
                threshold=3.0,
                features={'zscore': zscore, 'value': value, 'mean': mean, 'std': std},
                patterns=['zscore_anomaly'],
            )

        return None

    async def _detect_iqr_anomaly(
        self,
        exchange: str,
        symbol: str,
        value: float,
        history: List[float],
        anomaly_type: AnomalyType,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect anomaly using IQR method."""
        if len(history) < 10:
            return None

        q1 = np.percentile(history[-50:], 25)
        q3 = np.percentile(history[-50:], 75)
        iqr = q3 - q1

        if iqr == 0:
            return None

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        if value < lower_bound or value > upper_bound:
            severity = AnomalySeverity.MEDIUM
            if value < lower_bound - 3 * iqr or value > upper_bound + 3 * iqr:
                severity = AnomalySeverity.HIGH

            return AnomalyDetectionResult(
                symbol=symbol,
                exchange=exchange,
                anomaly_type=anomaly_type,
                severity=severity,
                score=abs(value - (q1 + q3) / 2) / iqr if iqr != 0 else 0,
                detection_method=DetectionMethod.IQR,
                data={'value': value, 'q1': q1, 'q3': q3, 'iqr': iqr},
                expected_value=(q1 + q3) / 2,
                actual_value=value,
                deviation=(value - (q1 + q3) / 2) / ((q1 + q3) / 2) * 100 if (q1 + q3) != 0 else 0,
                threshold=1.5,
                features={'iqr': iqr, 'value': value, 'q1': q1, 'q3': q3},
                patterns=['iqr_anomaly'],
            )

        return None

    async def _detect_mad_anomaly(
        self,
        exchange: str,
        symbol: str,
        value: float,
        history: List[float],
        anomaly_type: AnomalyType,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect anomaly using MAD method."""
        if len(history) < 10:
            return None

        median = statistics.median(history[-50:])
        mad = statistics.median([abs(x - median) for x in history[-50:]])

        if mad == 0:
            return None

        modified_zscore = 0.6745 * abs(value - median) / mad

        if modified_zscore > 3.5:
            severity = AnomalySeverity.MEDIUM
            if modified_zscore > 5.0:
                severity = AnomalySeverity.HIGH
            elif modified_zscore > 7.0:
                severity = AnomalySeverity.CRITICAL

            return AnomalyDetectionResult(
                symbol=symbol,
                exchange=exchange,
                anomaly_type=anomaly_type,
                severity=severity,
                score=modified_zscore,
                detection_method=DetectionMethod.MAD,
                data={'value': value, 'median': median, 'mad': mad},
                expected_value=median,
                actual_value=value,
                deviation=(value - median) / median * 100 if median != 0 else 0,
                threshold=3.5,
                features={'modified_zscore': modified_zscore, 'value': value, 'median': median},
                patterns=['mad_anomaly'],
            )

        return None

    async def _detect_isolation_forest_anomaly(
        self,
        exchange: str,
        symbol: str,
        value: float,
        history: List[float],
        anomaly_type: AnomalyType,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect anomaly using Isolation Forest."""
        if not SKLEARN_AVAILABLE or IsolationForest is None:
            return None

        if len(history) < 50:
            return None

        # Get or create model
        model_key = f"{exchange}:{symbol}"
        if model_key not in self._isolation_forests:
            self._isolation_forests[model_key] = {}

        if anomaly_type.value not in self._isolation_forests[model_key]:
            # Train model
            X = np.array(history[-50:]).reshape(-1, 1)
            model = IsolationForest(contamination=0.05, random_state=42)
            model.fit(X)
            self._isolation_forests[model_key][anomaly_type.value] = model

        model = self._isolation_forests[model_key][anomaly_type.value]

        # Predict
        X_pred = np.array([value]).reshape(-1, 1)
        prediction = model.predict(X_pred)
        score = model.decision_function(X_pred)[0]

        if prediction[0] == -1:
            severity = AnomalySeverity.MEDIUM
            if score < -0.5:
                severity = AnomalySeverity.HIGH
            elif score < -0.8:
                severity = AnomalySeverity.CRITICAL

            return AnomalyDetectionResult(
                symbol=symbol,
                exchange=exchange,
                anomaly_type=anomaly_type,
                severity=severity,
                score=abs(score),
                detection_method=DetectionMethod.ISOLATION_FOREST,
                data={'value': value, 'score': score},
                expected_value=statistics.mean(history[-50:]),
                actual_value=value,
                deviation=(value - statistics.mean(history[-50:])) / statistics.mean(history[-50:]) * 100 if statistics.mean(history[-50:]) != 0 else 0,
                threshold=0.05,
                features={'score': score, 'value': value},
                patterns=['isolation_forest_anomaly'],
            )

        return None

    async def _detect_ensemble_anomaly(
        self,
        exchange: str,
        symbol: str,
        value: float,
        history: List[float],
        anomaly_type: AnomalyType,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect anomaly using ensemble of methods."""
        if len(history) < 20:
            return None

        results = []

        # Run multiple detectors
        zscore_result = await self._detect_zscore_anomaly(
            exchange, symbol, value, history, anomaly_type
        )
        if zscore_result:
            results.append(zscore_result)

        iqr_result = await self._detect_iqr_anomaly(
            exchange, symbol, value, history, anomaly_type
        )
        if iqr_result:
            results.append(iqr_result)

        mad_result = await self._detect_mad_anomaly(
            exchange, symbol, value, history, anomaly_type
        )
        if mad_result:
            results.append(mad_result)

        if SKLEARN_AVAILABLE and IsolationForest:
            if_result = await self._detect_isolation_forest_anomaly(
                exchange, symbol, value, history, anomaly_type
            )
            if if_result:
                results.append(if_result)

        if not results:
            return None

        # Aggregate results
        avg_score = sum(r.score for r in results) / len(results)
        avg_severity = max(r.severity for r in results)

        # Combine features
        combined_features = {}
        for result in results:
            combined_features.update(result.features)

        return AnomalyDetectionResult(
            symbol=symbol,
            exchange=exchange,
            anomaly_type=anomaly_type,
            severity=avg_severity,
            score=avg_score,
            detection_method=DetectionMethod.ENSEMBLE,
            data={'value': value, 'detections': [r.to_dict() for r in results]},
            expected_value=statistics.mean(history[-30:]),
            actual_value=value,
            deviation=(value - statistics.mean(history[-30:])) / statistics.mean(history[-30:]) * 100 if statistics.mean(history[-30:]) != 0 else 0,
            threshold=ANOMALY_SCORE_THRESHOLD,
            features=combined_features,
            patterns=['ensemble_anomaly'] + [f"{r.detection_method.value}_anomaly" for r in results],
        )

    async def _detect_order_book_anomaly(
        self,
        exchange: str,
        symbol: str,
        features: Dict[str, float],
        method: DetectionMethod,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect order book anomalies."""
        # For now, use z-score on spread depth
        depth = features.get('depth_imbalance', 0)
        spread = features.get('spread_pct', 0)

        if depth == 0 and spread == 0:
            return None

        # Get historical features
        historical_features = await self._get_historical_features(exchange, symbol)

        if len(historical_features) < 20:
            return None

        # Calculate anomaly score
        depth_history = [f.get('depth_imbalance', 0) for f in historical_features]
        spread_history = [f.get('spread_pct', 0) for f in historical_features]

        depth_anomaly = await self._detect_zscore_anomaly(
            exchange, symbol, depth, depth_history, AnomalyType.ORDER_BOOK
        )
        spread_anomaly = await self._detect_zscore_anomaly(
            exchange, symbol, spread, spread_history, AnomalyType.ORDER_BOOK
        )

        if depth_anomaly or spread_anomaly:
            return AnomalyDetectionResult(
                symbol=symbol,
                exchange=exchange,
                anomaly_type=AnomalyType.ORDER_BOOK,
                severity=AnomalySeverity.MEDIUM,
                score=max(depth_anomaly.score if depth_anomaly else 0, spread_anomaly.score if spread_anomaly else 0),
                detection_method=DetectionMethod.ENSEMBLE,
                data=features,
                expected_value=statistics.mean([f.get('spread_pct', 0) for f in historical_features[-20:]]),
                actual_value=spread,
                deviation=(spread - statistics.mean([f.get('spread_pct', 0) for f in historical_features[-20:]])) / 
                          statistics.mean([f.get('spread_pct', 0) for f in historical_features[-20:]]) * 100 if statistics.mean([f.get('spread_pct', 0) for f in historical_features[-20:]]) != 0 else 0,
                threshold=3.0,
                features=features,
                patterns=['order_book_anomaly'],
            )

        return None

    async def _detect_multidimensional_anomaly(
        self,
        exchange: str,
        symbol: str,
        features: Dict[str, float],
        historical_features: List[Dict[str, float]],
        method: DetectionMethod,
    ) -> Optional[AnomalyDetectionResult]:
        """Detect multidimensional anomalies."""
        if len(historical_features) < 30:
            return None

        # Convert to feature vectors
        feature_names = list(features.keys())
        X_historical = np.array([[f.get(name, 0) for name in feature_names] for f in historical_features])
        X_current = np.array([[features.get(name, 0) for name in feature_names]])

        # Use Isolation Forest for multidimensional detection
        if SKLEARN_AVAILABLE and IsolationForest:
            model_key = f"{exchange}:{symbol}"
            if model_key not in self._isolation_forests:
                self._isolation_forests[model_key] = {}

            if 'multidimensional' not in self._isolation_forests[model_key]:
                model = IsolationForest(contamination=0.05, random_state=42)
                model.fit(X_historical)
                self._isolation_forests[model_key]['multidimensional'] = model

            model = self._isolation_forests[model_key]['multidimensional']
            prediction = model.predict(X_current)
            score = model.decision_function(X_current)[0]

            if prediction[0] == -1:
                return AnomalyDetectionResult(
                    symbol=symbol,
                    exchange=exchange,
                    anomaly_type=AnomalyType.MULTIDIMENSIONAL,
                    severity=AnomalySeverity.MEDIUM if score > -0.5 else AnomalySeverity.HIGH,
                    score=abs(score),
                    detection_method=DetectionMethod.ISOLATION_FOREST,
                    data=features,
                    expected_value=None,
                    actual_value=None,
                    deviation=None,
                    threshold=0.05,
                    features=features,
                    patterns=['multidimensional_anomaly'],
                )

        return None

    async def _identify_pattern_type(self, window: List[Dict[str, Any]]) -> Optional[str]:
        """Identify pattern type from window."""
        if len(window) < 5:
            return None

        values = [d.get('value', d.get('price', 0)) for d in window]

        # Calculate differences
        diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
        avg_change = statistics.mean(diffs) if diffs else 0
        std_change = statistics.stdev(diffs) if len(diffs) > 1 else 0

        # Identify pattern
        if avg_change > 0 and std_change < abs(avg_change) * 0.5:
            return "trend_up"
        elif avg_change < 0 and std_change < abs(avg_change) * 0.5:
            return "trend_down"
        elif std_change > abs(avg_change) * 2:
            return "volatile"
        elif len([d for d in diffs if d > 0]) > len(diffs) * 0.8:
            return "strong_up"
        elif len([d for d in diffs if d < 0]) > len(diffs) * 0.8:
            return "strong_down"
        else:
            return "sideways"

    async def _find_similar_patterns(
        self,
        window: List[Dict[str, Any]],
        pattern_type: str,
        similarity_threshold: float,
    ) -> List[Dict[str, Any]]:
        """Find similar patterns."""
        # For now, return empty list
        return []

    async def _calculate_pattern_confidence(
        self,
        window: List[Dict[str, Any]],
        similar_patterns: List[Dict[str, Any]],
    ) -> float:
        """Calculate pattern confidence."""
        return 0.8  # Default confidence

    async def _get_historical_features(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
    ) -> List[Dict[str, float]]:
        """Get historical features."""
        # For now, return empty list
        return []

    def _extract_order_book_features(self, snapshot: Any) -> Dict[str, float]:
        """Extract order book features."""
        features = {}

        try:
            # Spread
            if hasattr(snapshot, 'spread_pct'):
                features['spread_pct'] = snapshot.spread_pct

            # Depth imbalance
            if hasattr(snapshot, 'bid_depth') and hasattr(snapshot, 'ask_depth'):
                total_depth = snapshot.bid_depth + snapshot.ask_depth
                if total_depth > 0:
                    features['depth_imbalance'] = (snapshot.bid_depth - snapshot.ask_depth) / total_depth

            # Price levels
            if hasattr(snapshot, 'bid_price') and hasattr(snapshot, 'ask_price'):
                features['price_spread'] = snapshot.ask_price - snapshot.bid_price

            # Volume
            if hasattr(snapshot, 'volume'):
                features['volume'] = float(snapshot.volume)

            # Order count
            if hasattr(snapshot, 'bid_count') and hasattr(snapshot, 'ask_count'):
                features['order_imbalance'] = (snapshot.bid_count - snapshot.ask_count) / (snapshot.bid_count + snapshot.ask_count + 1)

        except Exception as e:
            logger.warning(f"Failed to extract order book features: {e}")

        return features

    async def _store_detection(self, detection: AnomalyDetectionResult) -> None:
        """Store anomaly detection."""
        async with self._lock:
            self._detections.append(detection)
            self._metrics['total_detections'] += 1

            # Keep only last 1000 detections
            if len(self._detections) > 1000:
                self._detections = self._detections[-1000:]

            # Create alert for high severity
            if detection.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
                alert = AnomalyAlert(
                    anomaly=detection,
                    message=f"{detection.anomaly_type.value} anomaly detected for {detection.symbol} on {detection.exchange}",
                    severity=detection.severity,
                )
                self._alerts.append(alert)
                await self._emit_event('alert_created', alert)

    async def _update_statistics(self, detection: AnomalyDetectionResult) -> None:
        """Update statistics."""
        if detection.exchange not in self._statistics:
            self._statistics[detection.exchange] = {}

        if detection.symbol not in self._statistics[detection.exchange]:
            self._statistics[detection.exchange][detection.symbol] = AnomalyStatistics(
                symbol=detection.symbol,
                exchange=detection.exchange,
            )

        stats = self._statistics[detection.exchange][detection.symbol]
        stats.total_detections += 1

        # Update distribution
        type_key = detection.anomaly_type.value
        stats.detection_distribution[type_key] = stats.detection_distribution.get(type_key, 0) + 1

        # Update averages
        stats.avg_score = (stats.avg_score * (stats.total_detections - 1) + detection.score) / stats.total_detections

        # Severity
        severity_weights = {
            AnomalySeverity.LOW: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.HIGH: 3,
            AnomalySeverity.CRITICAL: 4,
        }
        weight = severity_weights.get(detection.severity, 1)
        stats.avg_severity = (stats.avg_severity * (stats.total_detections - 1) + weight) / stats.total_detections

        stats.last_detection = detection.timestamp

        # Calculate detection rate
        if stats.last_detection:
            hours = (datetime.utcnow() - stats.last_detection).total_seconds() / 3600
            if hours > 0:
                stats.detection_rate_per_hour = stats.total_detections / hours

    async def _emit_event(self, event_type: str, data: Any) -> None:
        """Emit an event."""
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================

    async def start(self) -> None:
        """Start the anomaly detector."""
        self._running = True
        logger.info("AnomalyDetector started")

    async def stop(self) -> None:
        """Stop the anomaly detector."""
        self._running = False
        await self.clear()
        logger.info("AnomalyDetector stopped")

    async def __aenter__(self) -> 'AnomalyDetector':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_anomaly_detector(
    price_manager: PriceManager,
    volume_manager: Optional[VolumeManager] = None,
    spread_manager: Optional[SpreadManager] = None,
    order_book_manager: Optional[OrderBookManager] = None,
    config: Optional[AnomalyDetectorConfig] = None,
    redis_client: Optional[Any] = None,
) -> AnomalyDetector:
    """
    Create an anomaly detector instance.

    Args:
        price_manager: PriceManager instance
        volume_manager: VolumeManager instance (optional)
        spread_manager: SpreadManager instance (optional)
        order_book_manager: OrderBookManager instance (optional)
        config: Configuration instance
        redis_client: Redis client for caching

    Returns:
        AnomalyDetector instance
    """
    return AnomalyDetector(
        price_manager=price_manager,
        volume_manager=volume_manager,
        spread_manager=spread_manager,
        order_book_manager=order_book_manager,
        config=config,
        redis_client=redis_client,
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the anomaly detector.
    """
    import asyncio
    import json

    async def main():
        # Setup logging
        logging.basicConfig(level=logging.DEBUG)

        # Import required managers
        from ..data.price_manager import create_price_manager
        from ..data.volume_manager import create_volume_manager
        from ..data.spread_manager import create_spread_manager

        # Create managers
        price_manager = create_price_manager()
        volume_manager = create_volume_manager(price_manager)
        spread_manager = create_spread_manager(price_manager)

        # Create anomaly detector
        detector = create_anomaly_detector(
            price_manager=price_manager,
            volume_manager=volume_manager,
            spread_manager=spread_manager,
        )

        # Update some data
        await price_manager.update_price(
            exchange="binance",
            symbol="BTC-USDT",
            price=45000.0,
            bid=44990.0,
            ask=45010.0,
            volume=123.45,
        )

        # Detect anomalies
        result = await detector.detect_price_anomaly("binance", "BTC-USDT", 45000.0)
        if result:
            print(f"Anomaly detected: {json.dumps(result.to_dict(), indent=2, default=str)}")

        # Get statistics
        stats = await detector.get_statistics("BTC-USDT", "binance")
        print(f"Statistics: {json.dumps(stats, indent=2, default=str)}")

        await detector.stop()
        await price_manager.stop()

    asyncio.run(main())

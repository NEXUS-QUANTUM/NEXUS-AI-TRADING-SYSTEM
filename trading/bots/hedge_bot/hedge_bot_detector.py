# trading/bots/hedge_bot/hedge_bot_detector.py

import asyncio
import logging
import time
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger(__name__)


class DetectionType(str, Enum):
    ANOMALY = "anomaly"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    DIVERGENCE = "divergence"
    PATTERN = "pattern"
    TREND = "trend"
    VOLATILITY = "volatility"
    MOMENTUM = "momentum"
    SUPPORT_RESISTANCE = "support_resistance"
    OVERBOUGHT = "overbought"
    OVERSOLD = "oversold"
    LIQUIDITY = "liquidity"
    MANIPULATION = "manipulation"
    FRONT_RUNNING = "front_running"
    SPOOFING = "spoofing"
    WASH_TRADING = "wash_trading"
    LAYERING = "layering"
    PUMP_DUMP = "pump_dump"


class DetectionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ACTIVE = "active"
    RESOLVED = "resolved"


class DetectionConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class Detection:
    id: str
    type: DetectionType
    symbol: str
    timestamp: float
    price: float
    confidence: DetectionConfidence
    status: DetectionStatus = DetectionStatus.PENDING
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    expiry: Optional[float] = None
    confirmed_at: Optional[float] = None
    rejected_at: Optional[float] = None


@dataclass
class DetectionPattern:
    id: str
    name: str
    type: str
    description: str
    conditions: Dict[str, Any]
    confidence_threshold: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionResult:
    id: str
    pattern_id: str
    detection_id: str
    confidence: float
    score: float
    indicators: Dict[str, float]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DetectorManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._detections: Dict[str, Detection] = {}
        self._patterns: Dict[str, DetectionPattern] = {}
        self._results: Dict[str, DetectionResult] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_patterns()

    def _initialize_default_patterns(self) -> None:
        default_patterns = [
            DetectionPattern(
                id="head_shoulders",
                name="Head and Shoulders",
                type="pattern",
                description="Classic reversal pattern",
                conditions={
                    "left_shoulder": True,
                    "head": True,
                    "right_shoulder": True,
                    "neckline": True
                },
                confidence_threshold=0.7
            ),
            DetectionPattern(
                id="double_top",
                name="Double Top",
                type="pattern",
                description="Reversal pattern with two peaks",
                conditions={
                    "first_peak": True,
                    "second_peak": True,
                    "valley": True
                },
                confidence_threshold=0.7
            ),
            DetectionPattern(
                id="double_bottom",
                name="Double Bottom",
                type="pattern",
                description="Reversal pattern with two valleys",
                conditions={
                    "first_valley": True,
                    "second_valley": True,
                    "peak": True
                },
                confidence_threshold=0.7
            ),
            DetectionPattern(
                id="bull_flag",
                name="Bull Flag",
                type="pattern",
                description="Continuation pattern in uptrend",
                conditions={
                    "flagpole": True,
                    "flag": True,
                    "breakout": True
                },
                confidence_threshold=0.6
            ),
            DetectionPattern(
                id="bear_flag",
                name="Bear Flag",
                type="pattern",
                description="Continuation pattern in downtrend",
                conditions={
                    "flagpole": True,
                    "flag": True,
                    "breakout": True
                },
                confidence_threshold=0.6
            ),
            DetectionPattern(
                id="ascending_triangle",
                name="Ascending Triangle",
                type="pattern",
                description="Bullish continuation pattern",
                conditions={
                    "horizontal_resistance": True,
                    "ascending_support": True,
                    "breakout": True
                },
                confidence_threshold=0.7
            ),
            DetectionPattern(
                id="descending_triangle",
                name="Descending Triangle",
                type="pattern",
                description="Bearish continuation pattern",
                conditions={
                    "horizontal_support": True,
                    "descending_resistance": True,
                    "breakout": True
                },
                confidence_threshold=0.7
            ),
            DetectionPattern(
                id="symmetrical_triangle",
                name="Symmetrical Triangle",
                type="pattern",
                description="Continuation pattern with converging trendlines",
                conditions={
                    "descending_resistance": True,
                    "ascending_support": True,
                    "breakout": True
                },
                confidence_threshold=0.6
            ),
            DetectionPattern(
                id="bullish_divergence",
                name="Bullish Divergence",
                type="divergence",
                description="Price makes lower low, indicator makes higher low",
                conditions={
                    "price_lower_low": True,
                    "indicator_higher_low": True
                },
                confidence_threshold=0.7
            ),
            DetectionPattern(
                id="bearish_divergence",
                name="Bearish Divergence",
                type="divergence",
                description="Price makes higher high, indicator makes lower high",
                conditions={
                    "price_higher_high": True,
                    "indicator_lower_high": True
                },
                confidence_threshold=0.7
            ),
            DetectionPattern(
                id="rsi_overbought",
                name="RSI Overbought",
                type="overbought",
                description="RSI indicates overbought condition",
                conditions={
                    "rsi_value": 70
                },
                confidence_threshold=0.6
            ),
            DetectionPattern(
                id="rsi_oversold",
                name="RSI Oversold",
                type="oversold",
                description="RSI indicates oversold condition",
                conditions={
                    "rsi_value": 30
                },
                confidence_threshold=0.6
            )
        ]
        
        for pattern in default_patterns:
            self._patterns[pattern.id] = pattern

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_pattern(
        self,
        name: str,
        type: str,
        description: str,
        conditions: Dict[str, Any],
        confidence_threshold: float = 0.7,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DetectionPattern:
        async with self._lock:
            pattern_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            pattern = DetectionPattern(
                id=pattern_id,
                name=name,
                type=type,
                description=description,
                conditions=conditions,
                confidence_threshold=confidence_threshold,
                metadata=metadata or {}
            )
            
            self._patterns[pattern_id] = pattern
            await self._notify_observers("pattern_added", pattern)
            return pattern

    async def detect(
        self,
        symbol: str,
        data: pd.DataFrame,
        pattern_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Detection]:
        async with self._lock:
            detections = []
            
            patterns_to_check = pattern_ids or list(self._patterns.keys())
            
            for pattern_id in patterns_to_check:
                if pattern_id not in self._patterns:
                    continue
                
                pattern = self._patterns[pattern_id]
                result = await self._check_pattern(pattern, symbol, data)
                
                if result and result.confidence >= pattern.confidence_threshold:
                    detection = await self._create_detection(
                        symbol=symbol,
                        detection_type=DetectionType(pattern.type),
                        price=data['close'].iloc[-1],
                        confidence=self._get_confidence_level(result.confidence),
                        details={
                            "pattern_id": pattern.id,
                            "pattern_name": pattern.name,
                            "score": result.score,
                            "confidence": result.confidence,
                            "indicators": result.indicators
                        },
                        metadata=metadata or {}
                    )
                    
                    detections.append(detection)
                    self._results[result.id] = result
            
            return detections

    async def _check_pattern(
        self,
        pattern: DetectionPattern,
        symbol: str,
        data: pd.DataFrame
    ) -> Optional[DetectionResult]:
        if len(data) < 50:
            return None
        
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values
        volume = data['volume'].values
        
        if pattern.id == "head_shoulders":
            result = await self._check_head_shoulders(close, high, low)
        elif pattern.id == "double_top":
            result = await self._check_double_top(close, high)
        elif pattern.id == "double_bottom":
            result = await self._check_double_bottom(close, low)
        elif pattern.id == "bull_flag":
            result = await self._check_bull_flag(close, high, low)
        elif pattern.id == "bear_flag":
            result = await self._check_bear_flag(close, high, low)
        elif pattern.id == "ascending_triangle":
            result = await self._check_ascending_triangle(close, high, low)
        elif pattern.id == "descending_triangle":
            result = await self._check_descending_triangle(close, high, low)
        elif pattern.id == "symmetrical_triangle":
            result = await self._check_symmetrical_triangle(close, high, low)
        elif pattern.id == "bullish_divergence":
            result = await self._check_bullish_divergence(close, high, low, volume)
        elif pattern.id == "bearish_divergence":
            result = await self._check_bearish_divergence(close, high, low, volume)
        elif pattern.id == "rsi_overbought":
            result = await self._check_rsi(close, 70)
        elif pattern.id == "rsi_oversold":
            result = await self._check_rsi(close, 30)
        else:
            return None
        
        if result:
            result_id = hashlib.md5(f"{pattern.id}_{time.time()}".encode()).hexdigest()
            result.id = result_id
            result.pattern_id = pattern.id
        
        return result

    async def _check_head_shoulders(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray
    ) -> Optional[DetectionResult]:
        n = len(close)
        if n < 30:
            return None
        
        peaks = self._find_peaks(high, order=5)
        valleys = self._find_valleys(low, order=5)
        
        if len(peaks) < 3 or len(valleys) < 2:
            return None
        
        left_shoulder = peaks[-3] if len(peaks) >= 3 else None
        head = peaks[-2] if len(peaks) >= 2 else None
        right_shoulder = peaks[-1]
        
        if left_shoulder is None or head is None:
            return None
        
        if close[left_shoulder] < close[head] and close[right_shoulder] < close[head]:
            neckline = (close[valleys[-2]] + close[valleys[-1]]) / 2
            confidence = 0.8 if close[right_shoulder] < neckline else 0.6
            
            return DetectionResult(
                id="",
                pattern_id="",
                detection_id="",
                confidence=confidence,
                score=confidence,
                indicators={
                    "left_shoulder": close[left_shoulder],
                    "head": close[head],
                    "right_shoulder": close[right_shoulder],
                    "neckline": neckline
                },
                timestamp=time.time()
            )
        
        return None

    async def _check_double_top(
        self,
        close: np.ndarray,
        high: np.ndarray
    ) -> Optional[DetectionResult]:
        peaks = self._find_peaks(high, order=5)
        
        if len(peaks) < 2:
            return None
        
        first_peak = peaks[-2]
        second_peak = peaks[-1]
        
        valley = self._find_valleys(close[first_peak:second_peak], order=3)
        
        if valley is None:
            return None
        
        if abs(close[first_peak] - close[second_peak]) / close[first_peak] < 0.03:
            confidence = 0.8
        else:
            confidence = 0.6
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "first_peak": close[first_peak],
                "second_peak": close[second_peak],
                "valley": close[valley + first_peak]
            },
            timestamp=time.time()
        )

    async def _check_double_bottom(
        self,
        close: np.ndarray,
        low: np.ndarray
    ) -> Optional[DetectionResult]:
        valleys = self._find_valleys(low, order=5)
        
        if len(valleys) < 2:
            return None
        
        first_valley = valleys[-2]
        second_valley = valleys[-1]
        
        peak = self._find_peaks(close[first_valley:second_valley], order=3)
        
        if peak is None:
            return None
        
        if abs(close[first_valley] - close[second_valley]) / close[first_valley] < 0.03:
            confidence = 0.8
        else:
            confidence = 0.6
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "first_valley": close[first_valley],
                "second_valley": close[second_valley],
                "peak": close[peak + first_valley]
            },
            timestamp=time.time()
        )

    async def _check_bull_flag(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray
    ) -> Optional[DetectionResult]:
        n = len(close)
        if n < 20:
            return None
        
        trend = np.polyfit(range(n), close, 1)[0]
        if trend < 0:
            return None
        
        high_peaks = self._find_peaks(high, order=3)
        low_valleys = self._find_valleys(low, order=3)
        
        if len(high_peaks) < 2 or len(low_valleys) < 2:
            return None
        
        confidence = 0.7
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "trend": trend,
                "peaks": len(high_peaks),
                "valleys": len(low_valleys)
            },
            timestamp=time.time()
        )

    async def _check_bear_flag(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray
    ) -> Optional[DetectionResult]:
        n = len(close)
        if n < 20:
            return None
        
        trend = np.polyfit(range(n), close, 1)[0]
        if trend > 0:
            return None
        
        high_peaks = self._find_peaks(high, order=3)
        low_valleys = self._find_valleys(low, order=3)
        
        if len(high_peaks) < 2 or len(low_valleys) < 2:
            return None
        
        confidence = 0.7
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "trend": trend,
                "peaks": len(high_peaks),
                "valleys": len(low_valleys)
            },
            timestamp=time.time()
        )

    async def _check_ascending_triangle(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray
    ) -> Optional[DetectionResult]:
        n = len(close)
        if n < 20:
            return None
        
        high_peaks = self._find_peaks(high, order=3)
        low_valleys = self._find_valleys(low, order=3)
        
        if len(high_peaks) < 2 or len(low_valleys) < 2:
            return None
        
        trend = np.polyfit(range(len(low_valleys)), [low[i] for i in low_valleys], 1)[0]
        
        if trend > 0:
            confidence = 0.7
        else:
            confidence = 0.5
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "trend": trend,
                "peaks": len(high_peaks),
                "valleys": len(low_valleys)
            },
            timestamp=time.time()
        )

    async def _check_descending_triangle(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray
    ) -> Optional[DetectionResult]:
        n = len(close)
        if n < 20:
            return None
        
        high_peaks = self._find_peaks(high, order=3)
        low_valleys = self._find_valleys(low, order=3)
        
        if len(high_peaks) < 2 or len(low_valleys) < 2:
            return None
        
        trend = np.polyfit(range(len(high_peaks)), [high[i] for i in high_peaks], 1)[0]
        
        if trend < 0:
            confidence = 0.7
        else:
            confidence = 0.5
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "trend": trend,
                "peaks": len(high_peaks),
                "valleys": len(low_valleys)
            },
            timestamp=time.time()
        )

    async def _check_symmetrical_triangle(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray
    ) -> Optional[DetectionResult]:
        n = len(close)
        if n < 20:
            return None
        
        high_peaks = self._find_peaks(high, order=3)
        low_valleys = self._find_valleys(low, order=3)
        
        if len(high_peaks) < 2 or len(low_valleys) < 2:
            return None
        
        high_trend = np.polyfit(range(len(high_peaks)), [high[i] for i in high_peaks], 1)[0]
        low_trend = np.polyfit(range(len(low_valleys)), [low[i] for i in low_valleys], 1)[0]
        
        if high_trend < 0 and low_trend > 0:
            confidence = 0.7
        else:
            confidence = 0.5
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "high_trend": high_trend,
                "low_trend": low_trend
            },
            timestamp=time.time()
        )

    async def _check_bullish_divergence(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray
    ) -> Optional[DetectionResult]:
        n = len(close)
        if n < 20:
            return None
        
        rsi = self._calculate_rsi(close, 14)
        
        price_lows = self._find_valleys(close, order=5)
        rsi_lows = self._find_valleys(rsi, order=5)
        
        if len(price_lows) < 2 or len(rsi_lows) < 2:
            return None
        
        if close[price_lows[-2]] < close[price_lows[-1]]:
            if rsi[rsi_lows[-2]] > rsi[rsi_lows[-1]]:
                confidence = 0.8
            else:
                confidence = 0.5
        else:
            return None
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "price_lows": [close[i] for i in price_lows[-2:]],
                "rsi_lows": [rsi[i] for i in rsi_lows[-2:]]
            },
            timestamp=time.time()
        )

    async def _check_bearish_divergence(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray
    ) -> Optional[DetectionResult]:
        n = len(close)
        if n < 20:
            return None
        
        rsi = self._calculate_rsi(close, 14)
        
        price_highs = self._find_peaks(close, order=5)
        rsi_highs = self._find_peaks(rsi, order=5)
        
        if len(price_highs) < 2 or len(rsi_highs) < 2:
            return None
        
        if close[price_highs[-2]] > close[price_highs[-1]]:
            if rsi[rsi_highs[-2]] < rsi[rsi_highs[-1]]:
                confidence = 0.8
            else:
                confidence = 0.5
        else:
            return None
        
        return DetectionResult(
            id="",
            pattern_id="",
            detection_id="",
            confidence=confidence,
            score=confidence,
            indicators={
                "price_highs": [close[i] for i in price_highs[-2:]],
                "rsi_highs": [rsi[i] for i in rsi_highs[-2:]]
            },
            timestamp=time.time()
        )

    async def _check_rsi(
        self,
        close: np.ndarray,
        threshold: float
    ) -> Optional[DetectionResult]:
        rsi = self._calculate_rsi(close, 14)
        
        if rsi[-1] > threshold:
            return DetectionResult(
                id="",
                pattern_id="",
                detection_id="",
                confidence=0.7,
                score=0.7,
                indicators={"rsi": rsi[-1], "threshold": threshold},
                timestamp=time.time()
            )
        
        return None

    def _find_peaks(self, data: np.ndarray, order: int = 3) -> List[int]:
        peaks = []
        for i in range(order, len(data) - order):
            if data[i] == max(data[i-order:i+order+1]):
                peaks.append(i)
        return peaks

    def _find_valleys(self, data: np.ndarray, order: int = 3) -> List[int]:
        valleys = []
        for i in range(order, len(data) - order):
            if data[i] == min(data[i-order:i+order+1]):
                valleys.append(i)
        return valleys

    def _calculate_rsi(self, close: np.ndarray, period: int = 14) -> np.ndarray:
        deltas = np.diff(close)
        seed = deltas[:period+1]
        up = seed[seed > 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down
        rsi = np.zeros_like(close)
        rsi[:period] = 100 - 100 / (1 + rs)
        
        for i in range(period, len(close)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0
            else:
                upval = 0
                downval = -delta
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / down
            rsi[i] = 100 - 100 / (1 + rs)
        
        return rsi

    def _get_confidence_level(self, confidence: float) -> DetectionConfidence:
        if confidence >= 0.9:
            return DetectionConfidence.VERY_HIGH
        elif confidence >= 0.7:
            return DetectionConfidence.HIGH
        elif confidence >= 0.5:
            return DetectionConfidence.MEDIUM
        else:
            return DetectionConfidence.LOW

    async def _create_detection(
        self,
        symbol: str,
        detection_type: DetectionType,
        price: float,
        confidence: DetectionConfidence,
        details: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Detection:
        detection_id = hashlib.md5(f"{symbol}_{detection_type.value}_{time.time()}".encode()).hexdigest()
        
        detection = Detection(
            id=detection_id,
            type=detection_type,
            symbol=symbol,
            timestamp=time.time(),
            price=price,
            confidence=confidence,
            status=DetectionStatus.ACTIVE,
            details=details,
            metadata=metadata or {},
            expiry=time.time() + 3600
        )
        
        self._detections[detection_id] = detection
        await self._notify_observers("detection_created", detection)
        return detection

    async def confirm_detection(self, detection_id: str) -> bool:
        if detection_id in self._detections:
            self._detections[detection_id].status = DetectionStatus.CONFIRMED
            self._detections[detection_id].confirmed_at = time.time()
            await self._notify_observers("detection_confirmed", detection_id)
            return True
        return False

    async def reject_detection(self, detection_id: str) -> bool:
        if detection_id in self._detections:
            self._detections[detection_id].status = DetectionStatus.REJECTED
            self._detections[detection_id].rejected_at = time.time()
            await self._notify_observers("detection_rejected", detection_id)
            return True
        return False

    async def get_detection(self, detection_id: str) -> Optional[Detection]:
        return self._detections.get(detection_id)

    async def get_detections(
        self,
        symbol: Optional[str] = None,
        status: Optional[DetectionStatus] = None,
        detection_type: Optional[DetectionType] = None,
        limit: int = 100
    ) -> List[Detection]:
        detections = list(self._detections.values())
        
        if symbol:
            detections = [d for d in detections if d.symbol == symbol]
        
        if status:
            detections = [d for d in detections if d.status == status]
        
        if detection_type:
            detections = [d for d in detections if d.type == detection_type]
        
        detections.sort(key=lambda d: d.timestamp, reverse=True)
        return detections[:limit]

    async def get_pattern(self, pattern_id: str) -> Optional[DetectionPattern]:
        return self._patterns.get(pattern_id)

    async def get_patterns(self) -> List[DetectionPattern]:
        return list(self._patterns.values())

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "detections": len(self._detections),
            "patterns": len(self._patterns),
            "results": len(self._results),
            "active_detections": len([d for d in self._detections.values() if d.status == DetectionStatus.ACTIVE]),
            "confirmed_detections": len([d for d in self._detections.values() if d.status == DetectionStatus.CONFIRMED]),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "DetectionType",
    "DetectionStatus",
    "DetectionConfidence",
    "Detection",
    "DetectionPattern",
    "DetectionResult",
    "DetectorManager"
]

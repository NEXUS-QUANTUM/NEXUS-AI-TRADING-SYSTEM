# trading/bots/hedge_bot/hedge_bot_data_sensor.py

import asyncio
import logging
import time
import json
import hashlib
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class SensorType(str, Enum):
    PRICE = "price"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    SPREAD = "spread"
    LIQUIDITY = "liquidity"
    SENTIMENT = "sentiment"
    MOMENTUM = "momentum"
    TREND = "trend"
    SUPPORT = "support"
    RESISTANCE = "resistance"
    PATTERN = "pattern"
    ANOMALY = "anomaly"
    CORRELATION = "correlation"
    DIVERGENCE = "divergence"
    SIGNAL = "signal"
    NOISE = "noise"
    FLOW = "flow"
    IMBALANCE = "imbalance"
    STRESS = "stress"
    REGIME = "regime"


class SensorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CALIBRATING = "calibrating"
    ERROR = "error"
    PAUSED = "paused"
    SLEEPING = "sleeping"


class SensitivityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"
    ADAPTIVE = "adaptive"


@dataclass
class SensorConfig:
    id: str
    name: str
    type: SensorType
    sensitivity: SensitivityLevel
    threshold: float = 0.5
    window_size: int = 100
    sample_interval: float = 1.0
    min_samples: int = 10
    max_samples: int = 10000
    calibration_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorReading:
    id: str
    sensor_id: str
    value: float
    timestamp: float
    raw_value: Any
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorData:
    id: str
    sensor_id: str
    values: List[float]
    timestamps: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: float = field(default_factory=time.time)


@dataclass
class SensorAlert:
    id: str
    sensor_id: str
    type: str
    message: str
    severity: str
    value: float
    threshold: float
    timestamp: float
    acknowledged: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorStats:
    id: str
    sensor_id: str
    readings_count: int
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    last_reading: float
    last_update: float
    alerts_count: int
    error_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataSensorManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._sensors: Dict[str, SensorConfig] = {}
        self._readings: Dict[str, List[SensorReading]] = defaultdict(list)
        self._sensor_data: Dict[str, SensorData] = {}
        self._alerts: Dict[str, SensorAlert] = {}
        self._stats: Dict[str, SensorStats] = {}
        self._handlers: Dict[SensorType, Callable] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._processing_task: Optional[asyncio.Task] = None
        
        self._initialize_handlers()

    def _initialize_handlers(self) -> None:
        self.register_handler(SensorType.PRICE, self._process_price)
        self.register_handler(SensorType.VOLUME, self._process_volume)
        self.register_handler(SensorType.VOLATILITY, self._process_volatility)
        self.register_handler(SensorType.SPREAD, self._process_spread)
        self.register_handler(SensorType.LIQUIDITY, self._process_liquidity)
        self.register_handler(SensorType.SENTIMENT, self._process_sentiment)
        self.register_handler(SensorType.MOMENTUM, self._process_momentum)
        self.register_handler(SensorType.TREND, self._process_trend)
        self.register_handler(SensorType.SUPPORT, self._process_support)
        self.register_handler(SensorType.RESISTANCE, self._process_resistance)
        self.register_handler(SensorType.PATTERN, self._process_pattern)
        self.register_handler(SensorType.ANOMALY, self._process_anomaly)
        self.register_handler(SensorType.CORRELATION, self._process_correlation)
        self.register_handler(SensorType.DIVERGENCE, self._process_divergence)
        self.register_handler(SensorType.SIGNAL, self._process_signal)
        self.register_handler(SensorType.NOISE, self._process_noise)
        self.register_handler(SensorType.FLOW, self._process_flow)
        self.register_handler(SensorType.IMBALANCE, self._process_imbalance)
        self.register_handler(SensorType.STRESS, self._process_stress)
        self.register_handler(SensorType.REGIME, self._process_regime)

    def register_handler(self, sensor_type: SensorType, handler: Callable) -> None:
        self._handlers[sensor_type] = handler

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_sensor(
        self,
        name: str,
        sensor_type: SensorType,
        sensitivity: SensitivityLevel = SensitivityLevel.MEDIUM,
        threshold: float = 0.5,
        window_size: int = 100,
        sample_interval: float = 1.0,
        calibration_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SensorConfig:
        async with self._lock:
            sensor_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            sensor = SensorConfig(
                id=sensor_id,
                name=name,
                type=sensor_type,
                sensitivity=sensitivity,
                threshold=threshold,
                window_size=window_size,
                sample_interval=sample_interval,
                calibration_data=calibration_data or {},
                metadata=metadata or {}
            )
            
            self._sensors[sensor_id] = sensor
            self._readings[sensor_id] = []
            self._stats[sensor_id] = SensorStats(
                id=hashlib.md5(f"{sensor_id}_{time.time()}".encode()).hexdigest(),
                sensor_id=sensor_id,
                readings_count=0,
                min_value=0,
                max_value=0,
                mean_value=0,
                std_value=0,
                last_reading=0,
                last_update=time.time(),
                alerts_count=0,
                error_count=0
            )
            
            await self._notify_observers("sensor_created", sensor)
            return sensor

    async def ingest_reading(
        self,
        sensor_id: str,
        value: float,
        raw_value: Any = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SensorReading]:
        async with self._lock:
            if sensor_id not in self._sensors:
                return None
            
            sensor = self._sensors[sensor_id]
            
            reading = SensorReading(
                id=hashlib.md5(f"{sensor_id}_{time.time()}".encode()).hexdigest(),
                sensor_id=sensor_id,
                value=value,
                timestamp=time.time(),
                raw_value=raw_value or value,
                confidence=confidence,
                metadata=metadata or {}
            )
            
            self._readings[sensor_id].append(reading)
            
            if len(self._readings[sensor_id]) > sensor.max_samples:
                self._readings[sensor_id] = self._readings[sensor_id][-sensor.max_samples:]
            
            await self._process_reading(reading)
            await self._update_stats(reading)
            
            await self._notify_observers("reading_ingested", reading)
            return reading

    async def _process_reading(self, reading: SensorReading) -> None:
        sensor = self._sensors.get(reading.sensor_id)
        if not sensor:
            return
        
        handler = self._handlers.get(sensor.type)
        if not handler:
            return
        
        try:
            result = await handler(reading, sensor)
            if result:
                alert = SensorAlert(
                    id=hashlib.md5(f"{sensor.id}_{time.time()}".encode()).hexdigest(),
                    sensor_id=sensor.id,
                    type=result.get("type", "alert"),
                    message=result.get("message", ""),
                    severity=result.get("severity", "warning"),
                    value=reading.value,
                    threshold=sensor.threshold,
                    timestamp=time.time(),
                    metadata=result.get("metadata", {})
                )
                self._alerts[alert.id] = alert
                await self._notify_observers("alert_triggered", alert)
        except Exception as e:
            logger.error(f"Error processing reading: {e}")

    async def _update_stats(self, reading: SensorReading) -> None:
        if reading.sensor_id not in self._stats:
            return
        
        stats = self._stats[reading.sensor_id]
        readings = self._readings[reading.sensor_id]
        
        values = [r.value for r in readings]
        stats.readings_count = len(readings)
        stats.min_value = min(values) if values else 0
        stats.max_value = max(values) if values else 0
        stats.mean_value = np.mean(values) if values else 0
        stats.std_value = np.std(values) if values else 0
        stats.last_reading = reading.value
        stats.last_update = time.time()

    async def _process_price(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        mean = np.mean(values)
        std = np.std(values)
        
        z_score = (reading.value - mean) / std if std > 0 else 0
        
        if abs(z_score) > sensor.threshold * 3:
            return {
                "type": "price_alert",
                "message": f"Price {reading.value} is {z_score:.2f} std from mean",
                "severity": "high" if abs(z_score) > 5 else "medium",
                "metadata": {"z_score": z_score}
            }
        
        return None

    async def _process_volume(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        mean = np.mean(values)
        volume_ratio = reading.value / mean if mean > 0 else 0
        
        if volume_ratio > sensor.threshold * 4:
            return {
                "type": "volume_alert",
                "message": f"Volume spike: {reading.value} ({volume_ratio:.2f}x avg)",
                "severity": "high" if volume_ratio > 10 else "medium",
                "metadata": {"volume_ratio": volume_ratio}
            }
        
        return None

    async def _process_volatility(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        vol = np.std(values)
        
        if vol > sensor.threshold * 2:
            return {
                "type": "volatility_alert",
                "message": f"High volatility: {vol:.4f}",
                "severity": "high" if vol > sensor.threshold * 4 else "medium",
                "metadata": {"volatility": vol}
            }
        
        return None

    async def _process_spread(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        mean = np.mean(values)
        spread_ratio = reading.value / mean if mean > 0 else 0
        
        if spread_ratio > sensor.threshold * 3:
            return {
                "type": "spread_alert",
                "message": f"Wide spread: {reading.value}",
                "severity": "medium",
                "metadata": {"spread_ratio": spread_ratio}
            }
        
        return None

    async def _process_liquidity(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        if reading.value < sensor.threshold:
            return {
                "type": "liquidity_alert",
                "message": f"Low liquidity: {reading.value}",
                "severity": "high",
                "metadata": {"liquidity": reading.value}
            }
        
        return None

    async def _process_sentiment(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        if abs(reading.value) > sensor.threshold:
            direction = "positive" if reading.value > 0 else "negative"
            return {
                "type": "sentiment_alert",
                "message": f"Strong {direction} sentiment: {reading.value}",
                "severity": "medium",
                "metadata": {"sentiment": reading.value}
            }
        
        return None

    async def _process_momentum(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        momentum = reading.value
        if abs(momentum) > sensor.threshold * 2:
            direction = "up" if momentum > 0 else "down"
            return {
                "type": "momentum_alert",
                "message": f"Strong {direction} momentum: {momentum}",
                "severity": "medium",
                "metadata": {"momentum": momentum}
            }
        
        return None

    async def _process_trend(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        if abs(slope) > sensor.threshold:
            direction = "up" if slope > 0 else "down"
            return {
                "type": "trend_alert",
                "message": f"Strong {direction} trend: {slope:.4f}",
                "severity": "medium",
                "metadata": {"slope": slope}
            }
        
        return None

    async def _process_support(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        min_value = min(values)
        if reading.value <= min_value * (1 + sensor.threshold):
            return {
                "type": "support_alert",
                "message": f"Price near support: {reading.value}",
                "severity": "medium",
                "metadata": {"support": min_value}
            }
        
        return None

    async def _process_resistance(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        max_value = max(values)
        if reading.value >= max_value * (1 - sensor.threshold):
            return {
                "type": "resistance_alert",
                "message": f"Price near resistance: {reading.value}",
                "severity": "medium",
                "metadata": {"resistance": max_value}
            }
        
        return None

    async def _process_pattern(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        patterns = []
        n = len(values)
        
        if n >= 5:
            if values[-1] > values[-2] > values[-3] and values[-4] < values[-3]:
                patterns.append("ascending_triangle")
            elif values[-1] < values[-2] < values[-3] and values[-4] > values[-3]:
                patterns.append("descending_triangle")
        
        if n >= 3:
            if values[-1] > values[-2] and values[-2] < values[-3]:
                patterns.append("hammer")
            elif values[-1] < values[-2] and values[-2] > values[-3]:
                patterns.append("shooting_star")
        
        if patterns:
            return {
                "type": "pattern_alert",
                "message": f"Pattern detected: {', '.join(patterns)}",
                "severity": "medium",
                "metadata": {"patterns": patterns}
            }
        
        return None

    async def _process_anomaly(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        mean = np.mean(values)
        std = np.std(values)
        z_score = (reading.value - mean) / std if std > 0 else 0
        
        if abs(z_score) > sensor.threshold * 3:
            return {
                "type": "anomaly_alert",
                "message": f"Anomaly detected: z-score={z_score:.2f}",
                "severity": "high" if abs(z_score) > 5 else "medium",
                "metadata": {"z_score": z_score}
            }
        
        return None

    async def _process_correlation(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        values = [r.value for r in self._readings[sensor.id][-sensor.window_size:]]
        
        if len(values) < sensor.min_samples:
            return None
        
        if abs(reading.value) > sensor.threshold:
            direction = "positive" if reading.value > 0 else "negative"
            return {
                "type": "correlation_alert",
                "message": f"Strong {direction} correlation: {reading.value}",
                "severity": "medium",
                "metadata": {"correlation": reading.value}
            }
        
        return None

    async def _process_divergence(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        if abs(reading.value) > sensor.threshold:
            return {
                "type": "divergence_alert",
                "message": f"Divergence detected: {reading.value}",
                "severity": "high",
                "metadata": {"divergence": reading.value}
            }
        
        return None

    async def _process_signal(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        if abs(reading.value) > sensor.threshold:
            direction = "buy" if reading.value > 0 else "sell"
            return {
                "type": "signal_alert",
                "message": f"{direction.upper()} signal: {reading.value}",
                "severity": "high",
                "metadata": {"signal": reading.value}
            }
        
        return None

    async def _process_noise(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        if reading.value > sensor.threshold:
            return {
                "type": "noise_alert",
                "message": f"High noise level: {reading.value}",
                "severity": "medium",
                "metadata": {"noise": reading.value}
            }
        
        return None

    async def _process_flow(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        if abs(reading.value) > sensor.threshold:
            direction = "inflow" if reading.value > 0 else "outflow"
            return {
                "type": "flow_alert",
                "message": f"Strong {direction}: {reading.value}",
                "severity": "medium",
                "metadata": {"flow": reading.value}
            }
        
        return None

    async def _process_imbalance(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        if abs(reading.value) > sensor.threshold:
            direction = "buy" if reading.value > 0 else "sell"
            return {
                "type": "imbalance_alert",
                "message": f"Strong {direction} imbalance: {reading.value}",
                "severity": "high",
                "metadata": {"imbalance": reading.value}
            }
        
        return None

    async def _process_stress(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        if reading.value > sensor.threshold:
            return {
                "type": "stress_alert",
                "message": f"High stress level: {reading.value}",
                "severity": "high",
                "metadata": {"stress": reading.value}
            }
        
        return None

    async def _process_regime(self, reading: SensorReading, sensor: SensorConfig) -> Optional[Dict]:
        regimes = ["bull", "bear", "sideways", "volatile", "stable"]
        regime_index = int(reading.value) % len(regimes)
        regime = regimes[regime_index]
        
        return {
            "type": "regime_alert",
            "message": f"Market regime: {regime}",
            "severity": "info",
            "metadata": {"regime": regime}
        }

    async def get_readings(
        self,
        sensor_id: str,
        limit: int = 100,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[SensorReading]:
        if sensor_id not in self._readings:
            return []
        
        readings = self._readings[sensor_id]
        
        if start_time:
            readings = [r for r in readings if r.timestamp >= start_time]
        
        if end_time:
            readings = [r for r in readings if r.timestamp <= end_time]
        
        return readings[-limit:]

    async def get_stats(self, sensor_id: str) -> Optional[SensorStats]:
        return self._stats.get(sensor_id)

    async def get_alerts(
        self,
        sensor_id: Optional[str] = None,
        acknowledged: bool = False,
        limit: int = 100
    ) -> List[SensorAlert]:
        alerts = list(self._alerts.values())
        
        if sensor_id:
            alerts = [a for a in alerts if a.sensor_id == sensor_id]
        
        alerts = [a for a in alerts if a.acknowledged == acknowledged]
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        
        return alerts[:limit]

    async def acknowledge_alert(self, alert_id: str) -> bool:
        if alert_id in self._alerts:
            self._alerts[alert_id].acknowledged = True
            await self._notify_observers("alert_acknowledged", alert_id)
            return True
        return False

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
        total_readings = sum(len(r) for r in self._readings.values())
        total_alerts = len(self._alerts)
        
        return {
            "sensors": len(self._sensors),
            "readings": total_readings,
            "alerts": total_alerts,
            "handlers": len(self._handlers),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "SensorType",
    "SensorStatus",
    "SensitivityLevel",
    "SensorConfig",
    "SensorReading",
    "SensorData",
    "SensorAlert",
    "SensorStats",
    "DataSensorManager"
]

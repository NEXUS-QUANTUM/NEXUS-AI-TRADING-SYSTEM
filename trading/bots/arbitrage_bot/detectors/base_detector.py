"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Base Detector
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Base detector class for all detection modules with:
- Common interface for all detectors
- Event handling
- Metrics collection
- Configuration management
- Data validation
- Async support
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable

from ..data.exceptions import DetectorError, ValidationError, DataNotFoundError
from ..data.config import DetectorConfig

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class DetectorState(str, Enum):
    """State of the detector."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class DetectionType(str, Enum):
    """Types of detection."""
    ANOMALY = "anomaly"
    PATTERN = "pattern"
    SIGNAL = "signal"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    TREND = "trend"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"


class DetectionPriority(str, Enum):
    """Priority levels for detection."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class DetectionResult:
    """Base detection result."""
    
    id: str = field(default_factory=lambda: f"detection_{int(time.time() * 1000)}")
    type: DetectionType
    priority: DetectionPriority = DetectionPriority.MEDIUM
    score: float = 0.0
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'type': self.type.value if isinstance(self.type, DetectionType) else self.type,
            'priority': self.priority.value if isinstance(self.priority, DetectionPriority) else self.priority,
            'score': self.score,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'metadata': self.metadata,
            'source': self.source,
            'description': self.description,
        }


@dataclass
class DetectionMetrics:
    """Metrics for detection performance."""
    
    total_detections: int = 0
    successful_detections: int = 0
    failed_detections: int = 0
    false_positives: int = 0
    true_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    avg_detection_time_ms: float = 0.0
    min_detection_time_ms: float = float('inf')
    max_detection_time_ms: float = 0.0
    last_detection_time: Optional[datetime] = None
    detection_rate_per_second: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    
    def update(self, success: bool, detection_time_ms: float) -> None:
        """Update metrics with a detection result."""
        self.total_detections += 1
        if success:
            self.successful_detections += 1
            self.true_positives += 1
        else:
            self.failed_detections += 1
            self.false_positives += 1
        
        self.avg_detection_time_ms = (
            self.avg_detection_time_ms * (self.total_detections - 1) + detection_time_ms
        ) / self.total_detections
        self.min_detection_time_ms = min(self.min_detection_time_ms, detection_time_ms)
        self.max_detection_time_ms = max(self.max_detection_time_ms, detection_time_ms)
        self.last_detection_time = datetime.utcnow()
        
        # Calculate rates
        if self.last_detection_time:
            elapsed_seconds = (datetime.utcnow() - self.last_detection_time).total_seconds()
            if elapsed_seconds > 0:
                self.detection_rate_per_second = self.total_detections / elapsed_seconds
        
        # Calculate metrics
        if self.true_positives + self.false_positives > 0:
            self.precision = self.true_positives / (self.true_positives + self.false_positives)
        if self.true_positives + self.false_negatives > 0:
            self.recall = self.true_positives / (self.true_positives + self.false_negatives)
        if self.precision + self.recall > 0:
            self.f1_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_detections': self.total_detections,
            'successful_detections': self.successful_detections,
            'failed_detections': self.failed_detections,
            'false_positives': self.false_positives,
            'true_positives': self.true_positives,
            'false_negatives': self.false_negatives,
            'true_negatives': self.true_negatives,
            'avg_detection_time_ms': self.avg_detection_time_ms,
            'min_detection_time_ms': self.min_detection_time_ms if self.min_detection_time_ms != float('inf') else 0,
            'max_detection_time_ms': self.max_detection_time_ms,
            'last_detection_time': self.last_detection_time.isoformat() if self.last_detection_time else None,
            'detection_rate_per_second': self.detection_rate_per_second,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
        }


# ============================================================
# BASE DETECTOR CLASS
# ============================================================

class BaseDetector(ABC):
    """
    Base detector class providing common functionality for all detectors.
    
    Features:
    - Common interface for detection
    - Event handling system
    - Metrics collection
    - Configuration management
    - Async support
    - State management
    """
    
    def __init__(
        self,
        config: Optional[DetectorConfig] = None,
        name: Optional[str] = None,
    ):
        """
        Initialize the detector.
        
        Args:
            config: Detector configuration
            name: Detector name
        """
        self.config = config or DetectorConfig()
        self.name = name or self.__class__.__name__
        self.state = DetectorState.IDLE
        self.metrics = DetectionMetrics()
        self._handlers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._start_time: Optional[datetime] = None
        
        logger.info(f"Detector {self.name} initialized")
    
    # ============================================================
    # ABSTRACT METHODS
    # ============================================================
    
    @abstractmethod
    async def detect(self, data: Dict[str, Any]) -> Optional[DetectionResult]:
        """
        Perform detection on input data.
        
        Args:
            data: Input data for detection
            
        Returns:
            DetectionResult or None if no detection
        """
        pass
    
    @abstractmethod
    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate input data.
        
        Args:
            data: Input data to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_required_fields(self) -> List[str]:
        """
        Get required fields for detection.
        
        Returns:
            List of required field names
        """
        return []
    
    # ============================================================
    # PUBLIC METHODS
    # ============================================================
    
    async def detect_with_validation(self, data: Dict[str, Any]) -> Optional[DetectionResult]:
        """
        Perform detection with validation.
        
        Args:
            data: Input data for detection
            
        Returns:
            DetectionResult or None
        """
        start_time = time.perf_counter()
        
        try:
            # Validate state
            if self.state not in [DetectorState.RUNNING, DetectorState.IDLE]:
                logger.warning(f"Detector {self.name} is not running (state: {self.state})")
                return None
            
            # Validate data
            if not await self.validate_data(data):
                logger.warning(f"Invalid data for detector {self.name}")
                self.metrics.false_positives += 1
                return None
            
            # Perform detection
            result = await self.detect(data)
            
            # Update metrics
            detection_time_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.update(result is not None, detection_time_ms)
            
            if result:
                # Emit event
                await self._emit_event('detection', result)
                await self._emit_event(f'detection:{result.type.value}', result)
                logger.debug(f"Detection found by {self.name}: {result.type.value}")
            
            return result
            
        except Exception as e:
            self.metrics.failed_detections += 1
            logger.error(f"Detection failed for {self.name}: {e}")
            return None
    
    async def detect_batch(
        self,
        data_list: List[Dict[str, Any]],
        max_concurrent: int = 10,
    ) -> List[Optional[DetectionResult]]:
        """
        Perform detection on multiple data items.
        
        Args:
            data_list: List of input data
            max_concurrent: Maximum concurrent detections
            
        Returns:
            List of DetectionResult or None
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def detect_one(data: Dict[str, Any]) -> Optional[DetectionResult]:
            async with semaphore:
                return await self.detect_with_validation(data)
        
        tasks = [detect_one(data) for data in data_list]
        return await asyncio.gather(*tasks)
    
    async def train(self, data: Dict[str, Any]) -> bool:
        """
        Train the detector if applicable.
        
        Args:
            data: Training data
            
        Returns:
            True if training successful
        """
        # Default implementation - override in subclasses
        return True
    
    async def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update detector configuration.
        
        Args:
            config: New configuration
        """
        async with self._lock:
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        logger.info(f"Config updated for {self.name}")
    
    def register_handler(self, event_type: str, handler: Callable) -> None:
        """
        Register an event handler.
        
        Args:
            event_type: Event type (e.g., 'detection', 'detection:anomaly')
            handler: Handler function (sync or async)
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def unregister_handler(self, event_type: str, handler: Callable) -> None:
        """
        Unregister an event handler.
        
        Args:
            event_type: Event type
            handler: Handler function to remove
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get detector metrics.
        
        Returns:
            Dictionary with metrics
        """
        return {
            'name': self.name,
            'state': self.state.value if isinstance(self.state, DetectorState) else self.state,
            'uptime_seconds': (
                (datetime.utcnow() - self._start_time).total_seconds()
                if self._start_time else 0
            ),
            'metrics': self.metrics.to_dict(),
            'config': self.config.to_dict() if hasattr(self.config, 'to_dict') else {},
        }
    
    async def get_state(self) -> DetectorState:
        """
        Get current state.
        
        Returns:
            Current detector state
        """
        return self.state
    
    async def start(self) -> None:
        """
        Start the detector.
        """
        async with self._lock:
            if self.state == DetectorState.RUNNING:
                return
            
            self.state = DetectorState.RUNNING
            self._running = True
            self._start_time = datetime.utcnow()
            logger.info(f"Detector {self.name} started")
    
    async def stop(self) -> None:
        """
        Stop the detector.
        """
        async with self._lock:
            if self.state == DetectorState.STOPPED:
                return
            
            self.state = DetectorState.STOPPED
            self._running = False
            logger.info(f"Detector {self.name} stopped")
    
    async def pause(self) -> None:
        """
        Pause the detector.
        """
        async with self._lock:
            if self.state == DetectorState.PAUSED:
                return
            
            self.state = DetectorState.PAUSED
            logger.info(f"Detector {self.name} paused")
    
    async def resume(self) -> None:
        """
        Resume the detector.
        """
        async with self._lock:
            if self.state != DetectorState.PAUSED:
                return
            
            self.state = DetectorState.RUNNING
            logger.info(f"Detector {self.name} resumed")
    
    async def clear(self) -> None:
        """
        Clear detector data.
        """
        async with self._lock:
            self.metrics = DetectionMetrics()
            self._handlers.clear()
        logger.info(f"Detector {self.name} cleared")
    
    # ============================================================
    # PROTECTED METHODS
    # ============================================================
    
    async def _emit_event(self, event_type: str, data: Any) -> None:
        """
        Emit an event to registered handlers.
        
        Args:
            event_type: Event type
            data: Event data
        """
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")
    
    async def _check_threshold(
        self,
        value: float,
        threshold: float,
        operator: str = 'gt',
    ) -> bool:
        """
        Check if value exceeds threshold.
        
        Args:
            value: Value to check
            threshold: Threshold value
            operator: Comparison operator ('gt', 'lt', 'ge', 'le', 'eq')
            
        Returns:
            True if condition met
        """
        if operator == 'gt':
            return value > threshold
        elif operator == 'lt':
            return value < threshold
        elif operator == 'ge':
            return value >= threshold
        elif operator == 'le':
            return value <= threshold
        elif operator == 'eq':
            return value == threshold
        else:
            raise ValueError(f"Unknown operator: {operator}")
    
    async def _calculate_confidence(
        self,
        score: float,
        max_score: float = 100.0,
        min_score: float = 0.0,
    ) -> float:
        """
        Calculate confidence from score.
        
        Args:
            score: Detection score
            max_score: Maximum possible score
            min_score: Minimum possible score
            
        Returns:
            Confidence value between 0 and 1
        """
        if max_score == min_score:
            return 1.0
        return max(0.0, min(1.0, (score - min_score) / (max_score - min_score)))
    
    async def _merge_detections(
        self,
        detections: List[DetectionResult],
        merge_threshold: float = 0.5,
    ) -> List[DetectionResult]:
        """
        Merge overlapping detections.
        
        Args:
            detections: List of detections
            merge_threshold: Similarity threshold for merging
            
        Returns:
            Merged list of detections
        """
        if not detections:
            return []
        
        # Sort by score descending
        sorted_detections = sorted(detections, key=lambda x: x.score, reverse=True)
        
        merged = []
        for detection in sorted_detections:
            # Check if similar to existing merged
            should_merge = False
            for existing in merged:
                # Simple merge based on type and proximity
                if (detection.type == existing.type and
                    detection.score / existing.score > merge_threshold and
                    existing.score / detection.score > merge_threshold):
                    should_merge = True
                    # Merge data
                    existing.data.update(detection.data)
                    existing.metadata.update(detection.metadata)
                    existing.score = max(existing.score, detection.score)
                    existing.confidence = max(existing.confidence, detection.confidence)
                    break
            
            if not should_merge:
                merged.append(detection)
        
        return merged
    
    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================
    
    async def __aenter__(self) -> 'BaseDetector':
        """Enter context manager."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        await self.stop()
    
    # ============================================================
    # DUNDER METHODS
    # ============================================================
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', state='{self.state}')"


# ============================================================
# DETECTOR FACTORY
# ============================================================

class DetectorFactory:
    """
    Factory for creating and managing detectors.
    
    Features:
    - Detector registration and creation
    - Detector management
    - Dependency injection
    """
    
    def __init__(self):
        """Initialize factory."""
        self._detectors: Dict[str, type] = {}
        self._instances: Dict[str, BaseDetector] = {}
        self._lock = asyncio.Lock()
    
    def register(self, name: str, detector_class: type) -> None:
        """
        Register a detector class.
        
        Args:
            name: Detector name
            detector_class: Detector class
        """
        self._detectors[name] = detector_class
        logger.info(f"Registered detector: {name}")
    
    def unregister(self, name: str) -> None:
        """
        Unregister a detector class.
        
        Args:
            name: Detector name
        """
        if name in self._detectors:
            del self._detectors[name]
            logger.info(f"Unregistered detector: {name}")
    
    async def create(
        self,
        name: str,
        config: Optional[DetectorConfig] = None,
        **kwargs,
    ) -> BaseDetector:
        """
        Create a detector instance.
        
        Args:
            name: Detector name
            config: Detector configuration
            **kwargs: Additional arguments
            
        Returns:
            Detector instance
        """
        if name not in self._detectors:
            raise ValueError(f"Detector not registered: {name}")
        
        detector_class = self._detectors[name]
        instance = detector_class(config=config, **kwargs)
        
        async with self._lock:
            self._instances[f"{name}_{id(instance)}"] = instance
        
        return instance
    
    async def get(self, name: str) -> Optional[BaseDetector]:
        """
        Get a detector instance by name.
        
        Args:
            name: Detector name
            
        Returns:
            Detector instance or None
        """
        for key, instance in self._instances.items():
            if key.startswith(f"{name}_"):
                return instance
        return None
    
    async def get_all(self) -> List[BaseDetector]:
        """
        Get all detector instances.
        
        Returns:
            List of detector instances
        """
        return list(self._instances.values())
    
    async def start_all(self) -> None:
        """Start all detectors."""
        for instance in self._instances.values():
            await instance.start()
    
    async def stop_all(self) -> None:
        """Stop all detectors."""
        for instance in self._instances.values():
            await instance.stop()
    
    async def clear_all(self) -> None:
        """Clear all detectors."""
        for instance in self._instances.values():
            await instance.clear()
    
    def __repr__(self) -> str:
        return f"DetectorFactory(registered={len(self._detectors)}, instances={len(self._instances)})"


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of base detector.
    """
    import asyncio
    
    class ExampleDetector(BaseDetector):
        """Example detector implementation."""
        
        async def detect(self, data: Dict[str, Any]) -> Optional[DetectionResult]:
            """Simple threshold-based detection."""
            value = data.get('value', 0)
            
            if value > 100:
                return DetectionResult(
                    type=DetectionType.ANOMALY,
                    priority=DetectionPriority.HIGH,
                    score=value,
                    confidence=0.9,
                    data={'value': value},
                    description=f"Value {value} exceeds threshold",
                )
            return None
        
        async def validate_data(self, data: Dict[str, Any]) -> bool:
            """Validate input data."""
            return 'value' in data and isinstance(data['value'], (int, float))
        
        async def get_required_fields(self) -> List[str]:
            """Get required fields."""
            return ['value']
    
    async def main():
        # Create detector
        detector = ExampleDetector()
        
        # Register handler
        def on_detection(result: DetectionResult):
            print(f"Detection: {result.type} - {result.description}")
        
        detector.register_handler('detection', on_detection)
        
        # Start detector
        await detector.start()
        
        # Test detection
        result = await detector.detect_with_validation({'value': 150})
        if result:
            print(f"Result: {result.to_dict()}")
        
        result = await detector.detect_with_validation({'value': 50})
        if not result:
            print("No detection (expected)")
        
        # Get metrics
        metrics = await detector.get_metrics()
        print(f"Metrics: {metrics}")
        
        # Stop detector
        await detector.stop()
    
    asyncio.run(main())

"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Detector Factory
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Factory pattern for creating and managing detectors with:
- Detector registration and discovery
- Dependency injection
- Configuration management
- Lifecycle management
- Performance tracking
- Dynamic loading
"""

import asyncio
import importlib
import inspect
import logging
import time
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union, Callable

from .base_detector import BaseDetector, DetectorState, DetectionResult
from .anomaly_detector import AnomalyDetector
from .cross_chain_detector import CrossChainDetector
from .cross_exchange_detector import CrossExchangeDetector
from .pattern_detector import PatternDetector
from .signal_detector import SignalDetector
from .trend_detector import TrendDetector
from ..data.price_manager import PriceManager
from ..data.volume_manager import VolumeManager
from ..data.spread_manager import SpreadManager
from ..data.order_book_manager import OrderBookManager
from ..data.exceptions import DetectorError, ConfigurationError

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class DetectorCategory(str, Enum):
    """Categories of detectors."""
    ANOMALY = "anomaly"
    OPPORTUNITY = "opportunity"
    PATTERN = "pattern"
    SIGNAL = "signal"
    TREND = "trend"
    RISK = "risk"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"


class DetectorPriority(str, Enum):
    """Priority levels for detectors."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class DetectorMetadata:
    """Metadata for a detector."""
    
    name: str
    detector_class: Type[BaseDetector]
    category: DetectorCategory
    priority: DetectorPriority
    dependencies: List[str]
    config_schema: Dict[str, Any]
    version: str
    author: str
    description: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DetectorInstance:
    """Running detector instance."""
    
    metadata: DetectorMetadata
    instance: BaseDetector
    start_time: Optional[datetime] = None
    last_detection: Optional[datetime] = None
    detection_count: int = 0
    error_count: int = 0
    avg_detection_time_ms: float = 0.0
    status: DetectorState = DetectorState.IDLE


@dataclass
class DetectorMetrics:
    """Aggregated detector metrics."""
    
    total_detectors: int = 0
    active_detectors: int = 0
    total_detections: int = 0
    total_errors: int = 0
    avg_detection_time_ms: float = 0.0
    detector_statuses: Dict[str, DetectorState] = field(default_factory=dict)
    category_counts: Dict[str, int] = field(default_factory=dict)
    last_detection: Optional[datetime] = None
    uptime_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_detectors': self.total_detectors,
            'active_detectors': self.active_detectors,
            'total_detections': self.total_detections,
            'total_errors': self.total_errors,
            'avg_detection_time_ms': self.avg_detection_time_ms,
            'detector_statuses': {
                k: v.value if isinstance(v, DetectorState) else v
                for k, v in self.detector_statuses.items()
            },
            'category_counts': self.category_counts,
            'last_detection': self.last_detection.isoformat() if self.last_detection else None,
            'uptime_seconds': self.uptime_seconds,
            'timestamp': self.timestamp.isoformat(),
        }


# ============================================================
# DETECTOR FACTORY IMPLEMENTATION
# ============================================================

class DetectorFactory:
    """
    Factory for creating and managing detectors.
    
    Features:
    - Detector registration and discovery
    - Dependency injection
    - Configuration management
    - Lifecycle management
    - Performance tracking
    - Dynamic loading
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        price_manager: Optional[PriceManager] = None,
        volume_manager: Optional[VolumeManager] = None,
        spread_manager: Optional[SpreadManager] = None,
        order_book_manager: Optional[OrderBookManager] = None,
    ):
        """
        Initialize detector factory.

        Args:
            config: Configuration dictionary
            price_manager: PriceManager instance
            volume_manager: VolumeManager instance
            spread_manager: SpreadManager instance
            order_book_manager: OrderBookManager instance
        """
        self.config = config or {}
        self.price_manager = price_manager
        self.volume_manager = volume_manager
        self.spread_manager = spread_manager
        self.order_book_manager = order_book_manager
        
        # Registry
        self._registry: Dict[str, DetectorMetadata] = {}
        self._instances: Dict[str, DetectorInstance] = {}
        self._categories: Dict[DetectorCategory, List[str]] = defaultdict(list)
        
        # Metrics
        self._metrics = DetectorMetrics()
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Initialize with default detectors
        self._register_default_detectors()
        
        logger.info("DetectorFactory initialized")

    # ============================================================
    # REGISTRATION METHODS
    # ============================================================

    def register_detector(
        self,
        detector_class: Type[BaseDetector],
        category: DetectorCategory,
        priority: DetectorPriority = DetectorPriority.MEDIUM,
        dependencies: Optional[List[str]] = None,
        config_schema: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
        author: str = "NEXUS QUANTUM LTD",
        description: str = "",
    ) -> None:
        """
        Register a detector class.

        Args:
            detector_class: Detector class to register
            category: Detector category
            priority: Detector priority
            dependencies: List of dependency names
            config_schema: Configuration schema
            version: Detector version
            author: Detector author
            description: Detector description
        """
        name = detector_class.__name__
        
        metadata = DetectorMetadata(
            name=name,
            detector_class=detector_class,
            category=category,
            priority=priority,
            dependencies=dependencies or [],
            config_schema=config_schema or {},
            version=version,
            author=author,
            description=description or f"{name} detector",
        )
        
        self._registry[name] = metadata
        self._categories[category].append(name)
        
        logger.info(f"Registered detector: {name} ({category.value})")

    def register_detectors_from_module(self, module_path: str) -> None:
        """
        Register all detector classes from a module.

        Args:
            module_path: Module path to import
        """
        try:
            module = importlib.import_module(module_path)
            
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseDetector) and 
                    obj != BaseDetector):
                    # Try to determine category from name
                    category = self._infer_category(name)
                    self.register_detector(
                        detector_class=obj,
                        category=category,
                    )
            
            logger.info(f"Registered detectors from module: {module_path}")
            
        except ImportError as e:
            logger.error(f"Failed to import module {module_path}: {e}")
            raise

    def _register_default_detectors(self) -> None:
        """Register default detectors."""
        # Register built-in detectors
        self.register_detector(
            detector_class=AnomalyDetector,
            category=DetectorCategory.ANOMALY,
            priority=DetectorPriority.HIGH,
            description="Detects anomalies in market data",
        )
        
        self.register_detector(
            detector_class=CrossExchangeDetector,
            category=DetectorCategory.OPPORTUNITY,
            priority=DetectorPriority.HIGH,
            description="Detects cross-exchange arbitrage opportunities",
        )
        
        self.register_detector(
            detector_class=CrossChainDetector,
            category=DetectorCategory.OPPORTUNITY,
            priority=DetectorPriority.MEDIUM,
            description="Detects cross-chain arbitrage opportunities",
        )
        
        self.register_detector(
            detector_class=PatternDetector,
            category=DetectorCategory.PATTERN,
            priority=DetectorPriority.MEDIUM,
            description="Detects chart patterns",
        )
        
        self.register_detector(
            detector_class=SignalDetector,
            category=DetectorCategory.SIGNAL,
            priority=DetectorPriority.HIGH,
            description="Detects trading signals",
        )
        
        self.register_detector(
            detector_class=TrendDetector,
            category=DetectorCategory.TREND,
            priority=DetectorPriority.MEDIUM,
            description="Detects market trends",
        )

    # ============================================================
    # CREATION METHODS
    # ============================================================

    async def create_detector(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
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
        if name not in self._registry:
            raise ValueError(f"Detector not registered: {name}")
        
        metadata = self._registry[name]
        
        # Check dependencies
        for dep in metadata.dependencies:
            if dep not in self._instances:
                raise ValueError(f"Missing dependency: {dep} for {name}")
        
        # Prepare arguments
        detector_kwargs = {
            'config': config or {},
            'name': name,
        }
        
        # Inject dependencies
        if metadata.dependencies:
            for dep in metadata.dependencies:
                if dep == 'price_manager':
                    detector_kwargs['price_manager'] = self.price_manager
                elif dep == 'volume_manager':
                    detector_kwargs['volume_manager'] = self.volume_manager
                elif dep == 'spread_manager':
                    detector_kwargs['spread_manager'] = self.spread_manager
                elif dep == 'order_book_manager':
                    detector_kwargs['order_book_manager'] = self.order_book_manager
        
        # Override with provided kwargs
        detector_kwargs.update(kwargs)
        
        # Create instance
        try:
            instance = metadata.detector_class(**detector_kwargs)
        except Exception as e:
            raise DetectorError(f"Failed to create detector {name}: {e}")
        
        # Store instance
        detector_instance = DetectorInstance(
            metadata=metadata,
            instance=instance,
        )
        
        async with self._lock:
            self._instances[name] = detector_instance
        
        logger.info(f"Created detector: {name}")
        
        return instance

    async def create_all_detectors(
        self,
        configs: Optional[Dict[str, Dict[str, Any]]] = None,
        **kwargs,
    ) -> Dict[str, BaseDetector]:
        """
        Create all registered detectors.

        Args:
            configs: Detector configurations
            **kwargs: Additional arguments

        Returns:
            Dictionary of detector instances
        """
        configs = configs or {}
        detectors = {}
        
        for name in self._registry:
            try:
                detector = await self.create_detector(
                    name,
                    config=configs.get(name, {}),
                    **kwargs,
                )
                detectors[name] = detector
            except Exception as e:
                logger.error(f"Failed to create detector {name}: {e}")
        
        return detectors

    # ============================================================
    # LIFECYCLE METHODS
    # ============================================================

    async def start_detector(self, name: str) -> bool:
        """
        Start a detector.

        Args:
            name: Detector name

        Returns:
            True if started successfully
        """
        if name not in self._instances:
            return False
        
        instance = self._instances[name]
        
        try:
            await instance.instance.start()
            instance.status = DetectorState.RUNNING
            instance.start_time = datetime.utcnow()
            
            logger.info(f"Started detector: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start detector {name}: {e}")
            instance.status = DetectorState.ERROR
            return False

    async def start_all_detectors(self) -> Dict[str, bool]:
        """
        Start all detectors.

        Returns:
            Dictionary of start results
        """
        results = {}
        for name in self._instances:
            results[name] = await self.start_detector(name)
        return results

    async def stop_detector(self, name: str) -> bool:
        """
        Stop a detector.

        Args:
            name: Detector name

        Returns:
            True if stopped successfully
        """
        if name not in self._instances:
            return False
        
        instance = self._instances[name]
        
        try:
            await instance.instance.stop()
            instance.status = DetectorState.STOPPED
            
            logger.info(f"Stopped detector: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop detector {name}: {e}")
            return False

    async def stop_all_detectors(self) -> Dict[str, bool]:
        """
        Stop all detectors.

        Returns:
            Dictionary of stop results
        """
        results = {}
        for name in self._instances:
            results[name] = await self.stop_detector(name)
        return results

    async def pause_detector(self, name: str) -> bool:
        """
        Pause a detector.

        Args:
            name: Detector name

        Returns:
            True if paused successfully
        """
        if name not in self._instances:
            return False
        
        instance = self._instances[name]
        
        try:
            await instance.instance.pause()
            instance.status = DetectorState.PAUSED
            
            logger.info(f"Paused detector: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause detector {name}: {e}")
            return False

    async def resume_detector(self, name: str) -> bool:
        """
        Resume a detector.

        Args:
            name: Detector name

        Returns:
            True if resumed successfully
        """
        if name not in self._instances:
            return False
        
        instance = self._instances[name]
        
        try:
            await instance.instance.resume()
            instance.status = DetectorState.RUNNING
            
            logger.info(f"Resumed detector: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resume detector {name}: {e}")
            return False

    # ============================================================
    # DETECTION METHODS
    # ============================================================

    async def detect(
        self,
        data: Dict[str, Any],
        detectors: Optional[List[str]] = None,
    ) -> List[DetectionResult]:
        """
        Run detection on all or specified detectors.

        Args:
            data: Input data
            detectors: List of detector names to run

        Returns:
            List of DetectionResult
        """
        results = []
        detector_names = detectors or list(self._instances.keys())
        
        for name in detector_names:
            if name not in self._instances:
                continue
            
            instance = self._instances[name]
            
            if instance.status != DetectorState.RUNNING:
                continue
            
            start_time = time.perf_counter()
            
            try:
                result = await instance.instance.detect_with_validation(data)
                
                if result:
                    results.append(result)
                    instance.detection_count += 1
                    instance.last_detection = datetime.utcnow()
                    
                    # Update metrics
                    self._metrics.total_detections += 1
                    self._metrics.last_detection = datetime.utcnow()
                
                # Update detection time
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                instance.avg_detection_time_ms = (
                    instance.avg_detection_time_ms * 0.9 + elapsed_ms * 0.1
                )
                
                # Update metrics
                self._metrics.avg_detection_time_ms = (
                    self._metrics.avg_detection_time_ms * 0.9 + elapsed_ms * 0.1
                )
                
            except Exception as e:
                instance.error_count += 1
                self._metrics.total_errors += 1
                logger.error(f"Detection failed for {name}: {e}")
        
        return results

    async def detect_batch(
        self,
        data_list: List[Dict[str, Any]],
        detectors: Optional[List[str]] = None,
        max_concurrent: int = 10,
    ) -> List[List[DetectionResult]]:
        """
        Run detection on multiple data items.

        Args:
            data_list: List of input data
            detectors: List of detector names
            max_concurrent: Maximum concurrent detections

        Returns:
            List of detection results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def detect_one(data: Dict[str, Any]) -> List[DetectionResult]:
            async with semaphore:
                return await self.detect(data, detectors)
        
        tasks = [detect_one(data) for data in data_list]
        return await asyncio.gather(*tasks)

    # ============================================================
    # QUERY METHODS
    # ============================================================

    async def get_detector(self, name: str) -> Optional[BaseDetector]:
        """
        Get a detector instance.

        Args:
            name: Detector name

        Returns:
            Detector instance or None
        """
        if name in self._instances:
            return self._instances[name].instance
        return None

    async def get_detector_metadata(self, name: str) -> Optional[DetectorMetadata]:
        """
        Get detector metadata.

        Args:
            name: Detector name

        Returns:
            DetectorMetadata or None
        """
        return self._registry.get(name)

    async def get_detector_instances(self) -> Dict[str, DetectorInstance]:
        """
        Get all detector instances.

        Returns:
            Dictionary of detector instances
        """
        return dict(self._instances)

    async def get_detectors_by_category(
        self,
        category: DetectorCategory,
    ) -> List[BaseDetector]:
        """
        Get all detectors in a category.

        Args:
            category: Detector category

        Returns:
            List of detector instances
        """
        names = self._categories.get(category, [])
        return [
            self._instances[name].instance
            for name in names
            if name in self._instances
        ]

    async def get_detectors_by_priority(
        self,
        priority: DetectorPriority,
    ) -> List[BaseDetector]:
        """
        Get all detectors with a priority.

        Args:
            priority: Detector priority

        Returns:
            List of detector instances
        """
        results = []
        for name, instance in self._instances.items():
            if instance.metadata.priority == priority:
                results.append(instance.instance)
        return results

    async def get_detectors_by_status(
        self,
        status: DetectorState,
    ) -> List[BaseDetector]:
        """
        Get all detectors with a status.

        Args:
            status: Detector state

        Returns:
            List of detector instances
        """
        results = []
        for name, instance in self._instances.items():
            if instance.status == status:
                results.append(instance.instance)
        return results

    # ============================================================
    # METRICS METHODS
    # ============================================================

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get factory metrics.

        Returns:
            Dictionary with metrics
        """
        async with self._lock:
            # Update metrics
            self._metrics.total_detectors = len(self._registry)
            self._metrics.active_detectors = len([
                i for i in self._instances.values()
                if i.status == DetectorState.RUNNING
            ])
            
            self._metrics.detector_statuses = {
                name: i.status
                for name, i in self._instances.items()
            }
            
            self._metrics.category_counts = {
                category.value: len(names)
                for category, names in self._categories.items()
            }
            
            # Calculate uptime
            if self._metrics.last_detection:
                uptime = (datetime.utcnow() - self._metrics.last_detection).total_seconds()
                self._metrics.uptime_seconds += uptime
            
            return self._metrics.to_dict()

    async def get_detector_metrics(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get metrics for a specific detector.

        Args:
            name: Detector name

        Returns:
            Dictionary with detector metrics
        """
        if name not in self._instances:
            return None
        
        instance = self._instances[name]
        
        return {
            'name': name,
            'category': instance.metadata.category.value,
            'priority': instance.metadata.priority.value,
            'status': instance.status.value if isinstance(instance.status, DetectorState) else instance.status,
            'start_time': instance.start_time.isoformat() if instance.start_time else None,
            'last_detection': instance.last_detection.isoformat() if instance.last_detection else None,
            'detection_count': instance.detection_count,
            'error_count': instance.error_count,
            'avg_detection_time_ms': instance.avg_detection_time_ms,
        }

    # ============================================================
    # CONFIGURATION METHODS
    # ============================================================

    async def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update factory configuration.

        Args:
            config: New configuration
        """
        self.config.update(config)
        
        # Update all detectors
        for name, instance in self._instances.items():
            detector_config = config.get(name, {})
            if detector_config:
                await instance.instance.update_config(detector_config)
        
        logger.info("Factory configuration updated")

    # ============================================================
    # EVENT HANDLING
    # ============================================================

    def register_event_handler(
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
        self._event_handlers[event_type].append(handler)

    async def _emit_event(self, event_type: str, data: Any) -> None:
        """
        Emit an event.

        Args:
            event_type: Event type
            data: Event data
        """
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _infer_category(self, name: str) -> DetectorCategory:
        """Infer detector category from name."""
        name_lower = name.lower()
        
        if 'anomaly' in name_lower:
            return DetectorCategory.ANOMALY
        elif 'opportunity' in name_lower or 'arbitrage' in name_lower:
            return DetectorCategory.OPPORTUNITY
        elif 'pattern' in name_lower:
            return DetectorCategory.PATTERN
        elif 'signal' in name_lower:
            return DetectorCategory.SIGNAL
        elif 'trend' in name_lower:
            return DetectorCategory.TREND
        elif 'risk' in name_lower:
            return DetectorCategory.RISK
        elif 'performance' in name_lower:
            return DetectorCategory.PERFORMANCE
        elif 'compliance' in name_lower:
            return DetectorCategory.COMPLIANCE
        else:
            return DetectorCategory.SIGNAL

    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================

    async def start(self) -> None:
        """Start the factory."""
        logger.info("DetectorFactory started")

    async def stop(self) -> None:
        """Stop the factory."""
        await self.stop_all_detectors()
        logger.info("DetectorFactory stopped")

    async def clear(self) -> None:
        """Clear all data."""
        async with self._lock:
            self._instances.clear()
            self._metrics = DetectorMetrics()
        logger.info("DetectorFactory cleared")

    async def __aenter__(self) -> 'DetectorFactory':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================
# FACTORY BUILDER
# ============================================================

class DetectorFactoryBuilder:
    """
    Builder for DetectorFactory with fluent interface.
    """
    
    def __init__(self):
        """Initialize builder."""
        self._config: Dict[str, Any] = {}
        self._price_manager: Optional[PriceManager] = None
        self._volume_manager: Optional[VolumeManager] = None
        self._spread_manager: Optional[SpreadManager] = None
        self._order_book_manager: Optional[OrderBookManager] = None
        self._detectors: List[Tuple[Type[BaseDetector], DetectorCategory, Dict[str, Any]]] = []
    
    def with_config(self, config: Dict[str, Any]) -> 'DetectorFactoryBuilder':
        """Set configuration."""
        self._config = config
        return self
    
    def with_price_manager(self, price_manager: PriceManager) -> 'DetectorFactoryBuilder':
        """Set price manager."""
        self._price_manager = price_manager
        return self
    
    def with_volume_manager(self, volume_manager: VolumeManager) -> 'DetectorFactoryBuilder':
        """Set volume manager."""
        self._volume_manager = volume_manager
        return self
    
    def with_spread_manager(self, spread_manager: SpreadManager) -> 'DetectorFactoryBuilder':
        """Set spread manager."""
        self._spread_manager = spread_manager
        return self
    
    def with_order_book_manager(
        self,
        order_book_manager: OrderBookManager,
    ) -> 'DetectorFactoryBuilder':
        """Set order book manager."""
        self._order_book_manager = order_book_manager
        return self
    
    def add_detector(
        self,
        detector_class: Type[BaseDetector],
        category: DetectorCategory,
        config: Optional[Dict[str, Any]] = None,
    ) -> 'DetectorFactoryBuilder':
        """Add a detector to register."""
        self._detectors.append((detector_class, category, config or {}))
        return self
    
    def build(self) -> DetectorFactory:
        """Build the factory."""
        factory = DetectorFactory(
            config=self._config,
            price_manager=self._price_manager,
            volume_manager=self._volume_manager,
            spread_manager=self._spread_manager,
            order_book_manager=self._order_book_manager,
        )
        
        # Register additional detectors
        for detector_class, category, config in self._detectors:
            factory.register_detector(
                detector_class=detector_class,
                category=category,
            )
        
        return factory


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the detector factory.
    """
    import asyncio
    import json

    async def main():
        # Setup logging
        logging.basicConfig(level=logging.DEBUG)

        # Initialize managers
        from ..data.price_manager import create_price_manager
        from ..data.volume_manager import create_volume_manager
        from ..data.spread_manager import create_spread_manager
        from ..data.order_book_manager import create_order_book_manager

        price_manager = create_price_manager()
        volume_manager = create_volume_manager(price_manager)
        spread_manager = create_spread_manager(price_manager)
        order_book_manager = create_order_book_manager()

        # Create factory with builder
        factory = (
            DetectorFactoryBuilder()
            .with_price_manager(price_manager)
            .with_volume_manager(volume_manager)
            .with_spread_manager(spread_manager)
            .with_order_book_manager(order_book_manager)
            .with_config({
                'AnomalyDetector': {
                    'min_confidence': 0.6,
                    'anomaly_threshold': 3.0,
                },
                'CrossExchangeDetector': {
                    'min_profit_pct': 0.1,
                    'min_confidence': 0.5,
                },
            })
            .build()
        )

        # Add custom detectors
        # factory.register_detector(
        #     detector_class=MyCustomDetector,
        #     category=DetectorCategory.SIGNAL,
        #     priority=DetectorPriority.HIGH,
        # )

        # Create all detectors
        await factory.create_all_detectors()

        # Start all detectors
        await factory.start_all_detectors()

        # Update some prices
        await price_manager.update_price(
            exchange="binance",
            symbol="BTC-USDT",
            price=45000.0,
            bid=44990.0,
            ask=45010.0,
            volume=123.45,
        )

        await price_manager.update_price(
            exchange="bybit",
            symbol="BTC-USDT",
            price=45020.0,
            bid=45010.0,
            ask=45030.0,
            volume=67.89,
        )

        # Run detection
        results = await factory.detect({
            'exchanges': ['binance', 'bybit'],
            'symbols': ['BTC-USDT'],
        })

        for result in results:
            print(f"Detection: {result.type.value} - {result.description}")
            print(f"  Score: {result.score:.2f}")
            print(f"  Confidence: {result.confidence:.2f}")

        # Get metrics
        metrics = await factory.get_metrics()
        print(f"\nFactory metrics: {json.dumps(metrics, indent=2, default=str)}")

        # Get detector metrics
        detector_metrics = await factory.get_detector_metrics('CrossExchangeDetector')
        print(f"\nDetector metrics: {json.dumps(detector_metrics, indent=2, default=str)}")

        # Cleanup
        await factory.stop()
        await price_manager.stop()

    asyncio.run(main())

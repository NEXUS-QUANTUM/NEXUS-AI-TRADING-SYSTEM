# trading/bots/arbitrage_bot/detectors/__init__.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Complete Arbitrage Detectors Package

"""
Arbitrage Detectors Package

This package provides a comprehensive suite of arbitrage detection modules
for the NEXUS AI Trading System. It includes detectors for various types
of arbitrage opportunities across multiple markets and protocols.

Architecture:
    - Base Classes: Abstract interfaces for all detectors
    - Strategy-Specific Detectors: Specialized implementations
    - Factory Pattern: Dynamic detector instantiation
    - Scanner: Multi-detector orchestration
    - Analytics: Performance metrics and monitoring

Detectors Included:
    1. Base Detector (base_detector.py) - Abstract base class
    2. Anomaly Detector (anomaly_detector.py) - Market anomaly detection
    3. Cross-Chain Detector (cross_chain_detector.py) - Cross-chain arbitrage
    4. Cross-Exchange Detector (cross_exchange_detector.py) - Exchange arbitrage
    5. DEX Detector (dex_detector.py) - Decentralized exchange arbitrage
    6. Flash Loan Detector (flash_loan_detector.py) - Flash loan arbitrage
    7. Futures-Spot Detector (futures_spot_detector.py) - Basis trading
    8. Mixed Detector (mixed_detector.py) - Multi-strategy arbitrage
    9. Opportunity Scanner (opportunity_scanner.py) - Unified scanning
    10. Price Detector (price_detector.py) - Price analysis
    11. Signal Detector (signal_detector.py) - Signal detection
    12. Spread Detector (spread_detector.py) - Spread analysis
    13. Statistical Detector (statistical_detector.py) - Statistical arbitrage
    14. Triangular Detector (triangular_detector.py) - Triangular arbitrage
    15. Volume Detector (volume_detector.py) - Volume analysis

Exports:
    - All detector classes
    - Factory function for detector creation
    - Scanner for multi-detector coordination
    - Utility functions and constants
"""

import logging
from typing import Dict, List, Optional, Type, Any, Union, Tuple, Set, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import threading
import time
from functools import wraps
from contextlib import contextmanager

# Import all detectors with error handling
try:
    from .base_detector import (
        BaseDetector,
        DetectorConfig,
        DetectorType,
        DetectorStatus,
        DetectionResult,
        DetectionConfidence,
        DetectorEvent,
        DetectorEventListener,
        DetectorMetrics,
    )
except ImportError:
    # Define base classes if import fails (for standalone usage)
    class BaseDetector:
        pass
    class DetectorConfig:
        pass
    class DetectorType(Enum):
        pass
    class DetectorStatus(Enum):
        pass
    class DetectionResult:
        pass
    class DetectionConfidence:
        pass
    class DetectorEvent:
        pass
    class DetectorEventListener:
        pass
    class DetectorMetrics:
        pass

try:
    from .anomaly_detector import (
        AnomalyDetector,
        MarketAnomaly,
        AnomalyType,
        AnomalySeverity,
        AnomalyDetectionResult,
        AnomalyDetectorConfig,
    )
except ImportError:
    class AnomalyDetector:
        pass
    class MarketAnomaly:
        pass
    class AnomalyType(Enum):
        pass
    class AnomalySeverity(Enum):
        pass
    class AnomalyDetectionResult:
        pass
    class AnomalyDetectorConfig:
        pass

try:
    from .cross_chain_detector import (
        CrossChainDetector,
        CrossChainOpportunity,
        BridgeProtocol,
        ChainType,
        CrossChainArbitragePath,
        CrossChainDetectorConfig,
    )
except ImportError:
    class CrossChainDetector:
        pass
    class CrossChainOpportunity:
        pass
    class BridgeProtocol(Enum):
        pass
    class ChainType(Enum):
        pass
    class CrossChainArbitragePath:
        pass
    class CrossChainDetectorConfig:
        pass

try:
    from .cross_exchange_detector import (
        CrossExchangeDetector,
        CrossExchangeOpportunity,
        ExchangeType,
        CrossExchangeArbitragePath,
        CrossExchangeDetectorConfig,
    )
except ImportError:
    class CrossExchangeDetector:
        pass
    class CrossExchangeOpportunity:
        pass
    class ExchangeType(Enum):
        pass
    class CrossExchangeArbitragePath:
        pass
    class CrossExchangeDetectorConfig:
        pass

try:
    from .dex_detector import (
        DexDetector,
        DexOpportunity,
        DEXProtocol,
        LiquidityPoolInfo,
        DexArbitragePath,
        DexDetectorConfig,
    )
except ImportError:
    class DexDetector:
        pass
    class DexOpportunity:
        pass
    class DEXProtocol(Enum):
        pass
    class LiquidityPoolInfo:
        pass
    class DexArbitragePath:
        pass
    class DexDetectorConfig:
        pass

try:
    from .flash_loan_detector import (
        FlashLoanDetector,
        FlashLoanOpportunity,
        FlashLoanProtocol,
        FlashLoanInfo,
        FlashLoanExecutionPlan,
        FlashLoanDetectorConfig,
    )
except ImportError:
    class FlashLoanDetector:
        pass
    class FlashLoanOpportunity:
        pass
    class FlashLoanProtocol(Enum):
        pass
    class FlashLoanInfo:
        pass
    class FlashLoanExecutionPlan:
        pass
    class FlashLoanDetectorConfig:
        pass

try:
    from .futures_spot_detector import (
        FuturesSpotDetector,
        FuturesSpotOpportunity,
        ContractType,
        MarketType,
        BasisData,
        FuturesSpotDetectorConfig,
    )
except ImportError:
    class FuturesSpotDetector:
        pass
    class FuturesSpotOpportunity:
        pass
    class ContractType(Enum):
        pass
    class MarketType(Enum):
        pass
    class BasisData:
        pass
    class FuturesSpotDetectorConfig:
        pass

try:
    from .mixed_detector import (
        MixedDetector,
        MixedArbitrageOpportunity,
        ArbitrageStrategy,
        StrategyCategory,
        MixedArbitrageLeg,
        ExecutionPlan,
        MixedDetectorConfig,
    )
except ImportError:
    class MixedDetector:
        pass
    class MixedArbitrageOpportunity:
        pass
    class ArbitrageStrategy(Enum):
        pass
    class StrategyCategory(Enum):
        pass
    class MixedArbitrageLeg:
        pass
    class ExecutionPlan:
        pass
    class MixedDetectorConfig:
        pass

try:
    from .opportunity_scanner import (
        OpportunityScanner,
        ScannerConfig,
        ScannerMetrics,
        ScannerHealth,
        ScanResult,
        Priority,
        ScannerStatus,
    )
except ImportError:
    class OpportunityScanner:
        pass
    class ScannerConfig:
        pass
    class ScannerMetrics:
        pass
    class ScannerHealth:
        pass
    class ScanResult:
        pass
    class Priority(Enum):
        pass
    class ScannerStatus(Enum):
        pass

try:
    from .price_detector import (
        PriceDetector,
        PriceData,
        AggregatedPrice,
        PriceAnomaly,
        PricePrediction,
        VolatilityMetrics,
        PriceSourceType,
        PriceDetectorConfig,
    )
except ImportError:
    class PriceDetector:
        pass
    class PriceData:
        pass
    class AggregatedPrice:
        pass
    class PriceAnomaly:
        pass
    class PricePrediction:
        pass
    class VolatilityMetrics:
        pass
    class PriceSourceType(Enum):
        pass
    class PriceDetectorConfig:
        pass

try:
    from .signal_detector import (
        SignalDetector,
        Signal,
        SignalType,
        SignalPriority,
        Timeframe,
        IndicatorData,
        PatternData,
        DivergenceData,
        SignalDetectorConfig,
    )
except ImportError:
    class SignalDetector:
        pass
    class Signal:
        pass
    class SignalType(Enum):
        pass
    class SignalPriority(Enum):
        pass
    class Timeframe(Enum):
        pass
    class IndicatorData:
        pass
    class PatternData:
        pass
    class DivergenceData:
        pass
    class SignalDetectorConfig:
        pass

try:
    from .spread_detector import (
        SpreadDetector,
        SpreadData,
        SpreadAnalysis,
        SpreadArbitrageOpportunity,
        SpreadType,
        SpreadStatus,
        SpreadDetectorConfig,
    )
except ImportError:
    class SpreadDetector:
        pass
    class SpreadData:
        pass
    class SpreadAnalysis:
        pass
    class SpreadArbitrageOpportunity:
        pass
    class SpreadType(Enum):
        pass
    class SpreadStatus(Enum):
        pass
    class SpreadDetectorConfig:
        pass

try:
    from .statistical_detector import (
        StatisticalDetector,
        StatisticalPair,
        SpreadModel,
        KalmanState,
        ArbitrageSignal,
        StatisticalMethod,
        RegimeType,
        StatisticalDetectorConfig,
    )
except ImportError:
    class StatisticalDetector:
        pass
    class StatisticalPair:
        pass
    class SpreadModel:
        pass
    class KalmanState:
        pass
    class ArbitrageSignal:
        pass
    class StatisticalMethod(Enum):
        pass
    class RegimeType(Enum):
        pass
    class StatisticalDetectorConfig:
        pass

try:
    from .triangular_detector import (
        TriangularDetector,
        TriangularPath,
        TradingPair,
        ArbitrageOpportunity,
        PathType,
        ExchangeType as TriangularExchangeType,
        TriangularDetectorConfig,
    )
except ImportError:
    class TriangularDetector:
        pass
    class TriangularPath:
        pass
    class TradingPair:
        pass
    class ArbitrageOpportunity:
        pass
    class PathType(Enum):
        pass
    class TriangularExchangeType(Enum):
        pass
    class TriangularDetectorConfig:
        pass

try:
    from .volume_detector import (
        VolumeDetector,
        VolumeData,
        VolumeAnomaly,
        OrderFlowAnalysis,
        WhaleTransaction,
        VolumeArbitrageOpportunity,
        VolumeType,
        OrderFlowType,
        WhaleType,
        VolumeDetectorConfig,
    )
except ImportError:
    class VolumeDetector:
        pass
    class VolumeData:
        pass
    class VolumeAnomaly:
        pass
    class OrderFlowAnalysis:
        pass
    class WhaleTransaction:
        pass
    class VolumeArbitrageOpportunity:
        pass
    class VolumeType(Enum):
        pass
    class OrderFlowType(Enum):
        pass
    class WhaleType(Enum):
        pass
    class VolumeDetectorConfig:
        pass

# Detector factory
try:
    from .detector_factory import DetectorFactory
except ImportError:
    class DetectorFactory:
        @staticmethod
        def create_detector(detector_type: str, config: Optional[Dict] = None) -> Optional[BaseDetector]:
            return None
        @staticmethod
        def list_detectors() -> List[str]:
            return []

# Logger setup
logger = logging.getLogger(__name__)

# Version information
__version__ = "4.2.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package metadata
PACKAGE_METADATA = {
    "name": "detectors",
    "version": __version__,
    "description": "Advanced Arbitrage Detection Engine",
    "author": __author__,
    "copyright": __copyright__,
    "detectors_count": 15,
    "supported_strategies": [
        "dex_arbitrage",
        "flash_loan_arbitrage",
        "futures_spot_arbitrage",
        "cross_exchange_arbitrage",
        "triangular_arbitrage",
        "statistical_arbitrage",
        "cross_chain_arbitrage",
        "mixed_arbitrage",
        "spread_arbitrage",
        "volume_arbitrage",
        "price_arbitrage",
        "signal_arbitrage",
        "anomaly_detection",
    ],
    "supported_exchanges": [
        "binance",
        "bybit",
        "coinbase",
        "kraken",
        "okx",
        "gateio",
        "kucoin",
        "huobi",
    ],
    "supported_protocols": [
        "uniswap_v2",
        "uniswap_v3",
        "sushiswap",
        "pancakeswap",
        "curve",
        "balancer",
        "aave",
        "dydx",
    ],
}

# Public API - All detectors
__all__ = [
    # Base classes
    'BaseDetector',
    'DetectorConfig',
    'DetectorType',
    'DetectorStatus',
    'DetectionResult',
    'DetectionConfidence',
    'DetectorEvent',
    'DetectorEventListener',
    'DetectorMetrics',
    
    # Anomaly Detector
    'AnomalyDetector',
    'MarketAnomaly',
    'AnomalyType',
    'AnomalySeverity',
    'AnomalyDetectionResult',
    'AnomalyDetectorConfig',
    
    # Cross-Chain Detector
    'CrossChainDetector',
    'CrossChainOpportunity',
    'BridgeProtocol',
    'ChainType',
    'CrossChainArbitragePath',
    'CrossChainDetectorConfig',
    
    # Cross-Exchange Detector
    'CrossExchangeDetector',
    'CrossExchangeOpportunity',
    'ExchangeType',
    'CrossExchangeArbitragePath',
    'CrossExchangeDetectorConfig',
    
    # DEX Detector
    'DexDetector',
    'DexOpportunity',
    'DEXProtocol',
    'LiquidityPoolInfo',
    'DexArbitragePath',
    'DexDetectorConfig',
    
    # Flash Loan Detector
    'FlashLoanDetector',
    'FlashLoanOpportunity',
    'FlashLoanProtocol',
    'FlashLoanInfo',
    'FlashLoanExecutionPlan',
    'FlashLoanDetectorConfig',
    
    # Futures-Spot Detector
    'FuturesSpotDetector',
    'FuturesSpotOpportunity',
    'ContractType',
    'MarketType',
    'BasisData',
    'FuturesSpotDetectorConfig',
    
    # Mixed Detector
    'MixedDetector',
    'MixedArbitrageOpportunity',
    'ArbitrageStrategy',
    'StrategyCategory',
    'MixedArbitrageLeg',
    'ExecutionPlan',
    'MixedDetectorConfig',
    
    # Opportunity Scanner
    'OpportunityScanner',
    'ScannerConfig',
    'ScannerMetrics',
    'ScannerHealth',
    'ScanResult',
    'Priority',
    'ScannerStatus',
    
    # Price Detector
    'PriceDetector',
    'PriceData',
    'AggregatedPrice',
    'PriceAnomaly',
    'PricePrediction',
    'VolatilityMetrics',
    'PriceSourceType',
    'PriceDetectorConfig',
    
    # Signal Detector
    'SignalDetector',
    'Signal',
    'SignalType',
    'SignalPriority',
    'Timeframe',
    'IndicatorData',
    'PatternData',
    'DivergenceData',
    'SignalDetectorConfig',
    
    # Spread Detector
    'SpreadDetector',
    'SpreadData',
    'SpreadAnalysis',
    'SpreadArbitrageOpportunity',
    'SpreadType',
    'SpreadStatus',
    'SpreadDetectorConfig',
    
    # Statistical Detector
    'StatisticalDetector',
    'StatisticalPair',
    'SpreadModel',
    'KalmanState',
    'ArbitrageSignal',
    'StatisticalMethod',
    'RegimeType',
    'StatisticalDetectorConfig',
    
    # Triangular Detector
    'TriangularDetector',
    'TriangularPath',
    'TradingPair',
    'ArbitrageOpportunity',
    'PathType',
    'TriangularExchangeType',
    'TriangularDetectorConfig',
    
    # Volume Detector
    'VolumeDetector',
    'VolumeData',
    'VolumeAnomaly',
    'OrderFlowAnalysis',
    'WhaleTransaction',
    'VolumeArbitrageOpportunity',
    'VolumeType',
    'OrderFlowType',
    'WhaleType',
    'VolumeDetectorConfig',
    
    # Factory
    'DetectorFactory',
    
    # Metadata
    'PACKAGE_METADATA',
    'get_version',
    'get_metadata',
    'list_detectors',
    'create_detector',
    'get_detector',
    'get_all_detectors',
    'detector_registry',
]


class DetectorEventType(Enum):
    """Types of detector events."""
    STARTED = "started"
    STOPPED = "stopped"
    OPPORTUNITY_FOUND = "opportunity_found"
    OPPORTUNITY_EXECUTED = "opportunity_executed"
    ERROR = "error"
    WARNING = "warning"
    METRICS_UPDATED = "metrics_updated"
    STATUS_CHANGED = "status_changed"
    RECOVERY_ATTEMPTED = "recovery_attempted"
    RECOVERY_SUCCESS = "recovery_success"
    RECOVERY_FAILED = "recovery_failed"


@dataclass
class DetectorEvent:
    """Event emitted by detectors."""
    event_type: DetectorEventType
    detector_name: str
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None


class DetectorRegistry:
    """
    Registry for managing all available detectors.
    
    This class provides centralized management of detector instances,
    including creation, configuration, and lifecycle management.
    
    Features:
    - Singleton pattern for global access
    - Detector registration and retrieval
    - Lifecycle management (start/stop)
    - Event system for detector notifications
    - Metrics aggregation
    - Health monitoring
    """
    
    _instance = None
    _detectors: Dict[str, BaseDetector] = {}
    _configs: Dict[str, DetectorConfig] = {}
    _listeners: List[Callable[[DetectorEvent], None]] = []
    _event_history: List[DetectorEvent] = []
    _max_event_history: int = 1000
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the registry."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.logger = logging.getLogger(f"{__name__}.Registry")
            self._lock = threading.Lock()
            self._detector_metadata = {}
            self._register_detector_metadata()
            self.logger.info("DetectorRegistry initialized")
    
    def _register_detector_metadata(self) -> None:
        """Register metadata for all detectors."""
        self._detector_metadata = {
            'anomaly': {
                'class': AnomalyDetector,
                'description': 'Market anomaly and outlier detection',
                'enabled': True,
                'priority': 5,
                'category': 'analysis',
                'requires_data': True,
                'min_interval': 1.0,
            },
            'cross_chain': {
                'class': CrossChainDetector,
                'description': 'Cross-chain arbitrage detection',
                'enabled': True,
                'priority': 4,
                'category': 'arbitrage',
                'requires_data': True,
                'min_interval': 2.0,
            },
            'cross_exchange': {
                'class': CrossExchangeDetector,
                'description': 'Cross-exchange arbitrage detection',
                'enabled': True,
                'priority': 4,
                'category': 'arbitrage',
                'requires_data': True,
                'min_interval': 1.0,
            },
            'dex': {
                'class': DexDetector,
                'description': 'Decentralized exchange arbitrage',
                'enabled': True,
                'priority': 3,
                'category': 'arbitrage',
                'requires_data': True,
                'min_interval': 1.0,
            },
            'flash_loan': {
                'class': FlashLoanDetector,
                'description': 'Flash loan arbitrage detection',
                'enabled': True,
                'priority': 3,
                'category': 'arbitrage',
                'requires_data': True,
                'min_interval': 2.0,
            },
            'futures_spot': {
                'class': FuturesSpotDetector,
                'description': 'Futures-spot basis arbitrage',
                'enabled': True,
                'priority': 3,
                'category': 'arbitrage',
                'requires_data': True,
                'min_interval': 1.0,
            },
            'mixed': {
                'class': MixedDetector,
                'description': 'Mixed strategy arbitrage',
                'enabled': True,
                'priority': 2,
                'category': 'composite',
                'requires_data': True,
                'min_interval': 2.0,
            },
            'price': {
                'class': PriceDetector,
                'description': 'Price analysis and detection',
                'enabled': True,
                'priority': 1,
                'category': 'analysis',
                'requires_data': True,
                'min_interval': 0.5,
            },
            'signal': {
                'class': SignalDetector,
                'description': 'Trading signal detection',
                'enabled': True,
                'priority': 2,
                'category': 'analysis',
                'requires_data': True,
                'min_interval': 1.0,
            },
            'spread': {
                'class': SpreadDetector,
                'description': 'Spread analysis and detection',
                'enabled': True,
                'priority': 2,
                'category': 'analysis',
                'requires_data': True,
                'min_interval': 0.5,
            },
            'statistical': {
                'class': StatisticalDetector,
                'description': 'Statistical arbitrage detection',
                'enabled': True,
                'priority': 3,
                'category': 'arbitrage',
                'requires_data': True,
                'min_interval': 2.0,
            },
            'triangular': {
                'class': TriangularDetector,
                'description': 'Triangular arbitrage detection',
                'enabled': True,
                'priority': 3,
                'category': 'arbitrage',
                'requires_data': True,
                'min_interval': 0.5,
            },
            'volume': {
                'class': VolumeDetector,
                'description': 'Volume analysis and detection',
                'enabled': True,
                'priority': 2,
                'category': 'analysis',
                'requires_data': True,
                'min_interval': 1.0,
            },
        }
    
    def register_detector(
        self,
        name: str,
        detector: BaseDetector,
        config: Optional[DetectorConfig] = None
    ) -> None:
        """
        Register a detector instance.
        
        Args:
            name: Detector name
            detector: Detector instance
            config: Optional configuration
        """
        with self._lock:
            self._detectors[name] = detector
            if config:
                self._configs[name] = config
            self._emit_event(DetectorEventType.STARTED, name, {'config': config})
            self.logger.info(f"Registered detector: {name}")
    
    def unregister_detector(self, name: str) -> None:
        """
        Unregister a detector instance.
        
        Args:
            name: Detector name
        """
        with self._lock:
            if name in self._detectors:
                try:
                    if hasattr(self._detectors[name], 'stop'):
                        self._detectors[name].stop()
                except Exception as e:
                    self.logger.error(f"Error stopping {name}: {e}")
                del self._detectors[name]
                if name in self._configs:
                    del self._configs[name]
                self._emit_event(DetectorEventType.STOPPED, name)
                self.logger.info(f"Unregistered detector: {name}")
    
    def get_detector(self, name: str) -> Optional[BaseDetector]:
        """
        Get a detector by name.
        
        Args:
            name: Detector name
            
        Returns:
            Detector instance or None
        """
        with self._lock:
            return self._detectors.get(name)
    
    def get_all_detectors(self) -> Dict[str, BaseDetector]:
        """
        Get all registered detectors.
        
        Returns:
            Dictionary of detector name to instance
        """
        with self._lock:
            return self._detectors.copy()
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a detector.
        
        Args:
            name: Detector name
            
        Returns:
            Metadata dictionary or None
        """
        return self._detector_metadata.get(name)
    
    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all detectors.
        
        Returns:
            Dictionary of detector name to metadata
        """
        return self._detector_metadata.copy()
    
    def create_detector(
        self,
        detector_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[BaseDetector]:
        """
        Create a detector using the factory.
        
        Args:
            detector_type: Type of detector to create
            config: Optional configuration
            
        Returns:
            Detector instance or None
        """
        return DetectorFactory.create_detector(detector_type, config)
    
    def start_all(self) -> Dict[str, bool]:
        """
        Start all registered detectors.
        
        Returns:
            Dictionary of detector name to success status
        """
        results = {}
        for name, detector in self._detectors.items():
            try:
                if hasattr(detector, 'start'):
                    detector.start()
                    results[name] = True
                    self._emit_event(DetectorEventType.STARTED, name)
                    self.logger.info(f"Started detector: {name}")
                else:
                    results[name] = False
                    self.logger.warning(f"Detector {name} has no start method")
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to start {name}: {e}")
                self._emit_event(DetectorEventType.ERROR, name, {'error': str(e)}, e)
        return results
    
    def stop_all(self) -> Dict[str, bool]:
        """
        Stop all registered detectors.
        
        Returns:
            Dictionary of detector name to success status
        """
        results = {}
        for name, detector in self._detectors.items():
            try:
                if hasattr(detector, 'stop'):
                    detector.stop()
                    results[name] = True
                    self._emit_event(DetectorEventType.STOPPED, name)
                    self.logger.info(f"Stopped detector: {name}")
                else:
                    results[name] = False
                    self.logger.warning(f"Detector {name} has no stop method")
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to stop {name}: {e}")
                self._emit_event(DetectorEventType.ERROR, name, {'error': str(e)}, e)
        return results
    
    def get_status_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all detectors.
        
        Returns:
            Dictionary of detector name to status
        """
        status = {}
        for name, detector in self._detectors.items():
            try:
                metrics = None
                if hasattr(detector, 'get_metrics'):
                    metrics = detector.get_metrics()
                status[name] = {
                    'running': True,
                    'registered': True,
                    'metrics': metrics,
                    'has_metrics': metrics is not None,
                }
            except Exception as e:
                status[name] = {
                    'running': False,
                    'registered': True,
                    'metrics': None,
                    'error': str(e),
                }
        return status
    
    def add_listener(self, listener: Callable[[DetectorEvent], None]) -> None:
        """
        Add an event listener.
        
        Args:
            listener: Callback function for events
        """
        with self._lock:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[DetectorEvent], None]) -> None:
        """
        Remove an event listener.
        
        Args:
            listener: Callback function to remove
        """
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
    
    def _emit_event(
        self,
        event_type: DetectorEventType,
        detector_name: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ) -> None:
        """
        Emit an event to all listeners.
        
        Args:
            event_type: Type of event
            detector_name: Name of the detector
            data: Optional event data
            error: Optional error
        """
        event = DetectorEvent(
            event_type=event_type,
            detector_name=detector_name,
            timestamp=datetime.utcnow(),
            data=data,
            error=error,
        )
        
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_event_history:
                self._event_history = self._event_history[-self._max_event_history:]
            
            for listener in self._listeners:
                try:
                    listener(event)
                except Exception as e:
                    self.logger.error(f"Listener error: {e}")
    
    def get_event_history(
        self,
        limit: int = 100,
        detector_name: Optional[str] = None,
        event_type: Optional[DetectorEventType] = None
    ) -> List[DetectorEvent]:
        """
        Get event history.
        
        Args:
            limit: Maximum number of events
            detector_name: Filter by detector name
            event_type: Filter by event type
            
        Returns:
            List of events
        """
        with self._lock:
            events = self._event_history.copy()
        
        if detector_name:
            events = [e for e in events if e.detector_name == detector_name]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics from all detectors.
        
        Returns:
            Aggregated metrics dictionary
        """
        aggregated = {
            'total_detectors': len(self._detectors),
            'active_detectors': 0,
            'total_opportunities': 0,
            'total_profit': 0.0,
            'total_errors': 0,
            'detectors': {},
        }
        
        for name, detector in self._detectors.items():
            try:
                if hasattr(detector, 'get_metrics'):
                    metrics = detector.get_metrics()
                    if metrics:
                        aggregated['detectors'][name] = metrics
                        if metrics.get('is_running', False):
                            aggregated['active_detectors'] += 1
                        aggregated['total_opportunities'] += metrics.get('opportunities_found', 0)
                        aggregated['total_profit'] += float(metrics.get('total_profit', 0))
                        aggregated['total_errors'] += metrics.get('errors', 0)
            except Exception as e:
                self.logger.error(f"Error getting metrics for {name}: {e}")
        
        return aggregated


# Global registry instance
detector_registry = DetectorRegistry()


# Utility functions
def get_detector(name: str) -> Optional[BaseDetector]:
    """
    Get a detector by name from the registry.
    
    Args:
        name: Detector name
        
    Returns:
        Detector instance or None
    """
    return detector_registry.get_detector(name)


def get_all_detectors() -> Dict[str, BaseDetector]:
    """
    Get all detectors from the registry.
    
    Returns:
        Dictionary of detector name to instance
    """
    return detector_registry.get_all_detectors()


def create_detector(
    detector_type: str,
    config: Optional[Dict[str, Any]] = None
) -> Optional[BaseDetector]:
    """
    Create a detector.
    
    Args:
        detector_type: Type of detector to create
        config: Optional configuration
        
    Returns:
        Detector instance or None
    """
    return DetectorFactory.create_detector(detector_type, config)


def list_detectors() -> List[str]:
    """
    List all available detector types.
    
    Returns:
        List of detector type names
    """
    return DetectorFactory.list_detectors()


def get_version() -> str:
    """Get package version."""
    return __version__


def get_metadata() -> Dict[str, Any]:
    """Get package metadata."""
    return PACKAGE_METADATA


def start_all_detectors() -> Dict[str, bool]:
    """
    Start all registered detectors.
    
    Returns:
        Dictionary of detector name to success status
    """
    return detector_registry.start_all()


def stop_all_detectors() -> Dict[str, bool]:
    """
    Stop all registered detectors.
    
    Returns:
        Dictionary of detector name to success status
    """
    return detector_registry.stop_all()


def get_all_status() -> Dict[str, Dict[str, Any]]:
    """
    Get status of all detectors.
    
    Returns:
        Dictionary of detector name to status
    """
    return detector_registry.get_status_all()


def get_aggregated_metrics() -> Dict[str, Any]:
    """
    Get aggregated metrics from all detectors.
    
    Returns:
        Aggregated metrics dictionary
    """
    return detector_registry.get_aggregated_metrics()


# Context manager for detector lifecycle
@contextmanager
def detector_context(detector_name: str, config: Optional[Dict[str, Any]] = None):
    """
    Context manager for detector lifecycle.
    
    Args:
        detector_name: Name of the detector
        config: Optional configuration
        
    Yields:
        Detector instance
    """
    detector = create_detector(detector_name, config)
    if not detector:
        raise ValueError(f"Failed to create detector: {detector_name}")
    
    try:
        if hasattr(detector, 'start'):
            detector.start()
        yield detector
    finally:
        if hasattr(detector, 'stop'):
            detector.stop()


# Decorator for detector error handling
def handle_detector_errors(func: Callable) -> Callable:
    """
    Decorator for handling detector errors.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper


# Package initialization
logger.info(f"Initializing Detectors Package v{__version__}")
logger.info(f"Registered {len(detector_registry.get_all_metadata())} detector types")
logger.info(f"Package metadata: {PACKAGE_METADATA}")

# Auto-register available detectors
try:
    # Create and register default detectors if they exist
    for detector_type in ['price', 'spread', 'volume', 'signal']:
        try:
            detector = create_detector(detector_type)
            if detector:
                detector_registry.register_detector(detector_type, detector)
        except Exception as e:
            logger.debug(f"Failed to auto-register {detector_type}: {e}")
except Exception as e:
    logger.debug(f"Auto-registration failed: {e}")


# Lazy imports for circular dependency resolution
def __getattr__(name: str) -> Any:
    """
    Lazy import for submodules.
    
    This allows for clean imports while avoiding circular dependencies.
    """
    if name in ['anomaly_detector', 'cross_chain_detector', 'cross_exchange_detector',
                'dex_detector', 'flash_loan_detector', 'futures_spot_detector',
                'mixed_detector', 'opportunity_scanner', 'price_detector',
                'signal_detector', 'spread_detector', 'statistical_detector',
                'triangular_detector', 'volume_detector', 'base_detector',
                'detector_factory']:
        raise AttributeError(f"Module {name} not loaded. Please import directly.")
    raise AttributeError(f"module {__name__} has no attribute {name}")

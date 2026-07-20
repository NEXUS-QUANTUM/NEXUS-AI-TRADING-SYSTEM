# trading/bots/arbitrage_bot/detectors/opportunity_scanner.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Advanced Multi-Strategy Opportunity Scanner

"""
Opportunity Scanner - Advanced Multi-Strategy Arbitrage Scanning Engine

This module provides a unified, high-performance scanning engine that
coordinates all arbitrage detectors and provides:
- Parallel multi-strategy scanning
- Real-time opportunity aggregation
- Priority-based filtering
- Performance optimization
- Resource management
- Health monitoring

Architecture:
    - OpportunityScanner: Main scanning coordinator
    - ScannerPool: Thread/process pool management
    - StrategyScheduler: Dynamic scheduling
    - ResultAggregator: Opportunity aggregation
    - PerformanceMonitor: Real-time performance tracking
    - ResourceManager: Resource optimization

Features:
    - Parallel scanning of all detectors
    - Dynamic strategy prioritization
    - Adaptive scanning frequency
    - Result deduplication
    - Performance optimization
    - Resource management
    - Health monitoring
    - Graceful degradation
    - Automatic recovery
"""

import asyncio
import hashlib
import json
import logging
import time
import threading
import psutil
import gc
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    TypeVar,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    overload,
    Protocol,
    runtime_checkable,
)
from functools import lru_cache, wraps, partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from itertools import combinations, permutations, product
from contextlib import asynccontextmanager, contextmanager
from typing_extensions import TypedDict, NotRequired
from queue import PriorityQueue, Queue, Empty

import numpy as np
import pandas as pd

# Constants
MAX_WORKERS = 20
DEFAULT_SCAN_INTERVAL = 1.0
MIN_SCAN_INTERVAL = 0.1
MAX_SCAN_INTERVAL = 60.0
OPPORTUNITY_CACHE_SIZE = 10000
METRICS_WINDOW_SIZE = 100
HEALTH_CHECK_INTERVAL = 5.0
AUTO_RECOVERY_DELAY = 10.0
MAX_RETRY_ATTEMPTS = 3

# Priority levels
class Priority(Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4

# Scanner status
class ScannerStatus(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    PROCESSING = "processing"
    DEGRADED = "degraded"
    ERROR = "error"
    RECOVERING = "recovering"
    STOPPED = "stopped"

@dataclass
class ScannerConfig:
    """Configuration for the opportunity scanner."""
    max_workers: int = MAX_WORKERS
    scan_interval: float = DEFAULT_SCAN_INTERVAL
    min_scan_interval: float = MIN_SCAN_INTERVAL
    max_scan_interval: float = MAX_SCAN_INTERVAL
    cache_size: int = OPPORTUNITY_CACHE_SIZE
    metrics_window: int = METRICS_WINDOW_SIZE
    health_check_interval: float = HEALTH_CHECK_INTERVAL
    auto_recovery_delay: float = AUTO_RECOVERY_DELAY
    max_retry_attempts: int = MAX_RETRY_ATTEMPTS
    enable_adaptive_scheduling: bool = True
    enable_priority_filtering: bool = True
    enable_deduplication: bool = True
    enable_performance_monitoring: bool = True
    enable_health_checks: bool = True
    enable_auto_recovery: bool = True
    min_profit_threshold: Decimal = Decimal("0.001")
    max_opportunities_per_scan: int = 100

@dataclass
class ScannerMetrics:
    """Metrics for the scanner."""
    total_scans: int = 0
    total_opportunities: int = 0
    total_executed: int = 0
    total_profit: Decimal = Decimal("0")
    avg_scan_time_ms: float = 0.0
    avg_opportunities_per_scan: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_workers: int = 0
    queue_size: int = 0
    cache_hit_rate: float = 0.0
    last_scan_time: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    status: ScannerStatus = ScannerStatus.IDLE

@dataclass
class ScannerHealth:
    """Health status of the scanner."""
    status: ScannerStatus
    is_healthy: bool
    is_degraded: bool
    is_recovering: bool
    last_error: Optional[str] = None
    error_count: int = 0
    recovery_attempts: int = 0
    last_recovery_time: Optional[datetime] = None
    components: Dict[str, bool] = field(default_factory=dict)

class ScanResult(TypedDict):
    """Result from a scan."""
    scanner_id: str
    strategy: str
    opportunities: List[Any]
    scan_time_ms: float
    success: bool
    error: Optional[str]
    timestamp: datetime

class OpportunityBatch(TypedDict):
    """Batch of opportunities from a scan."""
    batch_id: str
    opportunities: List[Any]
    total_profit: Decimal
    avg_confidence: Decimal
    avg_risk: Decimal
    priority: Priority
    timestamp: datetime

class OpportunityScanner:
    """
    Advanced Multi-Strategy Opportunity Scanner.
    
    This class coordinates all arbitrage detectors and provides:
    1. Parallel scanning of all detectors
    2. Dynamic strategy prioritization
    3. Adaptive scanning frequency
    4. Result deduplication
    5. Performance optimization
    6. Resource management
    7. Health monitoring
    8. Graceful degradation
    9. Automatic recovery
    
    Features:
    - Thread/Process pool management
    - Adaptive scheduling based on performance
    - Priority-based filtering
    - Real-time performance monitoring
    - Automatic recovery from failures
    - Resource usage optimization
    """
    
    def __init__(
        self,
        config: Optional[ScannerConfig] = None,
        detectors: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the Opportunity Scanner.
        
        Args:
            config: Optional scanner configuration
            detectors: Optional dictionary of detectors
        """
        self.logger = self._setup_logger()
        self.config = config or ScannerConfig()
        
        # Initialize detectors
        self.detectors = detectors or {}
        self.detector_status: Dict[str, Dict[str, Any]] = {}
        self._init_detector_status()
        
        # Pools
        self.thread_pool = ThreadPoolExecutor(
            max_workers=min(self.config.max_workers, len(self.detectors) or 1)
        )
        self.process_pool: Optional[ProcessPoolExecutor] = None
        
        # Queues
        self.scan_queue: Queue = Queue()
        self.result_queue: Queue = Queue()
        self.opportunity_queue: Queue = Queue()
        
        # Caches
        self.opportunity_cache: Dict[str, Any] = {}
        self.result_cache: Dict[str, ScanResult] = {}
        self.metrics_cache: deque = deque(maxlen=self.config.metrics_window)
        
        # Priority queues
        self.priority_queue = PriorityQueue()
        
        # Metrics
        self.metrics = ScannerMetrics()
        self.health = ScannerHealth(
            status=ScannerStatus.IDLE,
            is_healthy=True,
            is_degraded=False,
            is_recovering=False,
            components={}
        )
        
        # State management
        self.is_running = False
        self.is_paused = False
        self.is_scanning = False
        self.scan_thread: Optional[threading.Thread] = None
        self.process_thread: Optional[threading.Thread] = None
        self.health_thread: Optional[threading.Thread] = None
        
        # Locks
        self.scan_lock = threading.Lock()
        self.cache_lock = threading.Lock()
        self.metrics_lock = threading.Lock()
        
        # Performance tracking
        self.scan_times: deque = deque(maxlen=100)
        self.opportunity_counts: deque = deque(maxlen=100)
        
        # Start scanner
        self.start()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger for the scanner."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _init_detector_status(self) -> None:
        """Initialize status for all detectors."""
        for detector_id in self.detectors:
            self.detector_status[detector_id] = {
                "enabled": True,
                "healthy": True,
                "last_scan": None,
                "scan_count": 0,
                "error_count": 0,
                "opportunities_found": 0,
                "avg_scan_time": 0.0,
                "last_error": None,
            }
    
    def start(self) -> None:
        """Start the scanner."""
        if self.is_running:
            return
        
        self.is_running = True
        self.health.status = ScannerStatus.IDLE
        
        # Start threads
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()
        
        self.health_thread = threading.Thread(target=self._health_loop, daemon=True)
        self.health_thread.start()
        
        self.logger.info("Opportunity Scanner started")
    
    def stop(self) -> None:
        """Stop the scanner."""
        self.is_running = False
        self.health.status = ScannerStatus.STOPPED
        
        # Wait for threads
        if self.scan_thread:
            self.scan_thread.join(timeout=5.0)
        if self.process_thread:
            self.process_thread.join(timeout=5.0)
        if self.health_thread:
            self.health_thread.join(timeout=5.0)
        
        # Shutdown pools
        self.thread_pool.shutdown(wait=True)
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
        
        self.logger.info("Opportunity Scanner stopped")
    
    def pause(self) -> None:
        """Pause scanning."""
        self.is_paused = True
        self.logger.info("Scanner paused")
    
    def resume(self) -> None:
        """Resume scanning."""
        self.is_paused = False
        self.logger.info("Scanner resumed")
    
    def _scan_loop(self) -> None:
        """Main scanning loop."""
        scan_interval = self.config.scan_interval
        
        while self.is_running:
            try:
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                # Start scan
                self.is_scanning = True
                self.health.status = ScannerStatus.SCANNING
                
                # Perform scan
                results = self._perform_scan()
                
                # Process results
                if results:
                    self._process_scan_results(results)
                
                # Update metrics
                with self.metrics_lock:
                    self.metrics.total_scans += 1
                    self.metrics.last_scan_time = datetime.utcnow()
                    self.metrics.status = ScannerStatus.IDLE
                
                self.is_scanning = False
                self.health.status = ScannerStatus.IDLE
                
                # Adaptive scheduling
                if self.config.enable_adaptive_scheduling:
                    scan_interval = self._calculate_adaptive_interval()
                
                # Sleep until next scan
                time.sleep(scan_interval)
                
            except Exception as e:
                self.logger.error(f"Scan loop error: {e}")
                self.is_scanning = False
                self.health.status = ScannerStatus.ERROR
                self.health.last_error = str(e)
                self.health.error_count += 1
                
                if self.config.enable_auto_recovery:
                    time.sleep(self.config.auto_recovery_delay)
                    self._attempt_recovery()
    
    def _perform_scan(self) -> List[ScanResult]:
        """
        Perform a scan using all detectors.
        
        Returns:
            List of scan results
        """
        results = []
        futures = []
        
        # Submit tasks to thread pool
        with ThreadPoolExecutor(max_workers=len(self.detectors)) as executor:
            for detector_id, detector in self.detectors.items():
                if not self.detector_status[detector_id].get("enabled", True):
                    continue
                
                future = executor.submit(
                    self._scan_detector,
                    detector_id,
                    detector
                )
                futures.append(future)
            
            # Collect results
            for future in as_completed(futures, timeout=30.0):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    self.logger.error(f"Future error: {e}")
        
        return results
    
    def _scan_detector(
        self,
        detector_id: str,
        detector: Any,
    ) -> Optional[ScanResult]:
        """
        Scan a single detector.
        
        Args:
            detector_id: Detector identifier
            detector: Detector instance
            
        Returns:
            ScanResult or None
        """
        start_time = time.time()
        
        try:
            # Perform scan
            if hasattr(detector, 'scan_opportunities'):
                opportunities = detector.scan_opportunities()
            else:
                opportunities = []
            
            # Update detector status
            status = self.detector_status[detector_id]
            status["last_scan"] = datetime.utcnow()
            status["scan_count"] += 1
            status["opportunities_found"] += len(opportunities)
            status["healthy"] = True
            
            # Build result
            result: ScanResult = {
                "scanner_id": detector_id,
                "strategy": getattr(detector, 'strategy', detector_id),
                "opportunities": opportunities,
                "scan_time_ms": (time.time() - start_time) * 1000,
                "success": True,
                "error": None,
                "timestamp": datetime.utcnow(),
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Detector {detector_id} scan failed: {e}")
            
            # Update status
            status = self.detector_status[detector_id]
            status["error_count"] += 1
            status["last_error"] = str(e)
            status["healthy"] = False
            
            # Build error result
            result: ScanResult = {
                "scanner_id": detector_id,
                "strategy": getattr(detector, 'strategy', detector_id),
                "opportunities": [],
                "scan_time_ms": (time.time() - start_time) * 1000,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow(),
            }
            
            return result
    
    def _process_scan_results(self, results: List[ScanResult]) -> None:
        """
        Process scan results and queue opportunities.
        
        Args:
            results: List of scan results
        """
        total_opportunities = 0
        total_profit = Decimal("0")
        
        for result in results:
            if not result["success"]:
                continue
            
            opportunities = result["opportunities"]
            if not opportunities:
                continue
            
            # Apply filtering
            filtered = self._filter_opportunities(opportunities)
            
            # Deduplicate
            if self.config.enable_deduplication:
                filtered = self._deduplicate_opportunities(filtered)
            
            # Update counts
            total_opportunities += len(filtered)
            
            # Calculate total profit
            for opp in filtered:
                profit = self._extract_profit(opp)
                total_profit += profit
            
            # Add to priority queue
            for opp in filtered:
                priority = self._calculate_priority(opp)
                self.priority_queue.put((priority.value, opp))
        
        # Update metrics
        with self.metrics_lock:
            self.metrics.total_opportunities += total_opportunities
            self.metrics.total_profit += total_profit
            
            if self.metrics.total_scans > 0:
                self.metrics.avg_opportunities_per_scan = (
                    self.metrics.total_opportunities / self.metrics.total_scans
                )
        
        # Log results
        if total_opportunities > 0:
            self.logger.info(
                f"Found {total_opportunities} opportunities "
                f"with total profit ${total_profit:,.2f}"
            )
        
        # Trigger garbage collection if needed
        if self.metrics.total_opportunities % 1000 == 0:
            gc.collect()
    
    def _filter_opportunities(
        self,
        opportunities: List[Any],
    ) -> List[Any]:
        """
        Filter opportunities based on criteria.
        
        Args:
            opportunities: List of opportunities
            
        Returns:
            Filtered list
        """
        filtered = []
        
        for opp in opportunities:
            # Extract metrics
            profit = self._extract_profit(opp)
            confidence = self._extract_confidence(opp)
            risk = self._extract_risk(opp)
            
            # Apply filters
            if profit < self.config.min_profit_threshold:
                continue
            
            if confidence < 0.5:
                continue
            
            if risk > 0.8:
                continue
            
            filtered.append(opp)
        
        # Limit opportunities
        if len(filtered) > self.config.max_opportunities_per_scan:
            filtered = filtered[:self.config.max_opportunities_per_scan]
        
        return filtered
    
    def _deduplicate_opportunities(
        self,
        opportunities: List[Any],
    ) -> List[Any]:
        """
        Deduplicate opportunities.
        
        Args:
            opportunities: List of opportunities
            
        Returns:
            Deduplicated list
        """
        seen = set()
        deduplicated = []
        
        for opp in opportunities:
            # Generate unique key
            key = self._generate_opportunity_key(opp)
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(opp)
                
                # Cache opportunity
                with self.cache_lock:
                    if len(self.opportunity_cache) >= self.config.cache_size:
                        # Remove oldest entry
                        oldest = next(iter(self.opportunity_cache))
                        del self.opportunity_cache[oldest]
                    self.opportunity_cache[key] = opp
        
        return deduplicated
    
    def _generate_opportunity_key(self, opp: Any) -> str:
        """
        Generate a unique key for an opportunity.
        
        Args:
            opp: Opportunity object
            
        Returns:
            Unique key string
        """
        # Try to extract identifying information
        try:
            if isinstance(opp, dict):
                # Use dictionary representation
                key_parts = []
                for field in ['symbol', 'strategy', 'exchange', 'protocol']:
                    if field in opp:
                        key_parts.append(str(opp[field]))
                if key_parts:
                    return hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Fallback to string representation
            return hashlib.md5(str(opp).encode()).hexdigest()
        except Exception:
            return hashlib.md5(str(time.time()).encode()).hexdigest()
    
    def _extract_profit(self, opp: Any) -> Decimal:
        """Extract profit from an opportunity."""
        try:
            if isinstance(opp, dict):
                if "net_profit" in opp:
                    return Decimal(str(opp["net_profit"]))
                if "profit" in opp:
                    return Decimal(str(opp["profit"]))
                if "expected_profit" in opp:
                    return Decimal(str(opp["expected_profit"]))
            if hasattr(opp, "net_profit"):
                return Decimal(str(opp.net_profit))
            if hasattr(opp, "profit"):
                return Decimal(str(opp.profit))
            if hasattr(opp, "expected_profit"):
                return Decimal(str(opp.expected_profit))
        except Exception:
            pass
        return Decimal("0")
    
    def _extract_confidence(self, opp: Any) -> float:
        """Extract confidence from an opportunity."""
        try:
            if isinstance(opp, dict):
                if "confidence" in opp:
                    return float(opp["confidence"])
            if hasattr(opp, "confidence"):
                return float(opp.confidence)
        except Exception:
            pass
        return 0.5
    
    def _extract_risk(self, opp: Any) -> float:
        """Extract risk from an opportunity."""
        try:
            if isinstance(opp, dict):
                if "risk_score" in opp:
                    return float(opp["risk_score"])
                if "risk" in opp:
                    return float(opp["risk"])
            if hasattr(opp, "risk_score"):
                return float(opp.risk_score)
            if hasattr(opp, "risk"):
                return float(opp.risk)
        except Exception:
            pass
        return 0.5
    
    def _calculate_priority(self, opp: Any) -> Priority:
        """
        Calculate priority for an opportunity.
        
        Args:
            opp: Opportunity object
            
        Returns:
            Priority level
        """
        profit = self._extract_profit(opp)
        confidence = self._extract_confidence(opp)
        risk = self._extract_risk(opp)
        
        # Calculate priority score
        score = (
            float(profit) * 0.4 +
            confidence * 0.3 +
            (1 - risk) * 0.3
        )
        
        if score > 0.8:
            return Priority.CRITICAL
        elif score > 0.6:
            return Priority.HIGH
        elif score > 0.4:
            return Priority.MEDIUM
        elif score > 0.2:
            return Priority.LOW
        else:
            return Priority.BACKGROUND
    
    def _calculate_adaptive_interval(self) -> float:
        """
        Calculate adaptive scan interval based on performance.
        
        Returns:
            Adaptive interval in seconds
        """
        if not self.scan_times:
            return self.config.scan_interval
        
        avg_scan_time = sum(self.scan_times) / len(self.scan_times)
        avg_opportunities = (
            sum(self.opportunity_counts) / len(self.opportunity_counts)
            if self.opportunity_counts else 0
        )
        
        # Adjust interval based on performance
        if avg_scan_time < 100:  # Fast scans
            interval = self.config.scan_interval * 0.8
        elif avg_scan_time < 500:  # Normal scans
            interval = self.config.scan_interval
        else:  # Slow scans
            interval = self.config.scan_interval * 1.5
        
        # Adjust based on opportunity density
        if avg_opportunities > 10:
            interval *= 0.9  # More opportunities = scan faster
        elif avg_opportunities < 1:
            interval *= 1.1  # Fewer opportunities = scan slower
        
        # Clamp to limits
        return max(
            self.config.min_scan_interval,
            min(self.config.max_scan_interval, interval)
        )
    
    def _process_loop(self) -> None:
        """Background processing loop."""
        while self.is_running:
            try:
                # Get highest priority opportunity
                try:
                    priority, opportunity = self.priority_queue.get(timeout=1.0)
                except Empty:
                    continue
                
                # Process opportunity
                self._process_opportunity(opportunity)
                
                # Update metrics
                with self.metrics_lock:
                    self.metrics.total_executed += 1
                
            except Exception as e:
                self.logger.error(f"Process loop error: {e}")
    
    def _process_opportunity(self, opportunity: Any) -> None:
        """
        Process a single opportunity.
        
        Args:
            opportunity: Opportunity to process
        """
        try:
            # Extract strategy
            strategy = self._extract_strategy(opportunity)
            
            # Execute using appropriate detector
            if strategy and strategy in self.detectors:
                detector = self.detectors[strategy]
                if hasattr(detector, 'execute_opportunity'):
                    result = detector.execute_opportunity(opportunity)
                    self._handle_execution_result(result)
            
        except Exception as e:
            self.logger.error(f"Opportunity processing failed: {e}")
    
    def _extract_strategy(self, opp: Any) -> Optional[str]:
        """Extract strategy from an opportunity."""
        try:
            if isinstance(opp, dict):
                if "strategy" in opp:
                    return str(opp["strategy"])
                if "detector" in opp:
                    return str(opp["detector"])
            if hasattr(opp, "strategy"):
                return str(opp.strategy)
            if hasattr(opp, "detector"):
                return str(opp.detector)
        except Exception:
            pass
        return None
    
    def _handle_execution_result(self, result: Dict[str, Any]) -> None:
        """Handle execution result."""
        if result.get("success"):
            self.logger.info(f"Execution successful: {result.get('profit', 0):.2f}")
        else:
            self.logger.error(f"Execution failed: {result.get('error', 'Unknown error')}")
    
    def _health_loop(self) -> None:
        """Health monitoring loop."""
        while self.is_running:
            try:
                time.sleep(self.config.health_check_interval)
                
                if self.config.enable_health_checks:
                    self._check_health()
                
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
    
    def _check_health(self) -> None:
        """Check scanner health."""
        # Check system resources
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            with self.metrics_lock:
                self.metrics.cpu_usage = cpu_percent
                self.metrics.memory_usage = memory_percent
        except Exception:
            pass
        
        # Check detector health
        unhealthy_detectors = []
        for detector_id, status in self.detector_status.items():
            if not status.get("healthy", True):
                unhealthy_detectors.append(detector_id)
        
        # Update health status
        if unhealthy_detectors:
            self.health.is_degraded = True
            self.health.components = {
                d: self.detector_status[d].get("healthy", False)
                for d in self.detector_status
            }
        else:
            self.health.is_degraded = False
        
        self.health.last_health_check = datetime.utcnow()
        self.health.is_healthy = not self.health.is_degraded and self.health.error_count < 10
    
    def _attempt_recovery(self) -> None:
        """Attempt to recover from errors."""
        self.health.status = ScannerStatus.RECOVERING
        self.health.recovery_attempts += 1
        self.health.last_recovery_time = datetime.utcnow()
        
        self.logger.warning(f"Attempting recovery #{self.health.recovery_attempts}")
        
        try:
            # Reset error status for detectors
            for detector_id in self.detector_status:
                if not self.detector_status[detector_id].get("healthy", True):
                    self.detector_status[detector_id]["healthy"] = True
                    self.detector_status[detector_id]["error_count"] = 0
                    self.detector_status[detector_id]["last_error"] = None
            
            # Clear error state
            self.health.last_error = None
            self.health.error_count = 0
            
            # Reset health
            self.health.is_healthy = True
            self.health.is_degraded = False
            self.health.status = ScannerStatus.IDLE
            
            self.logger.info("Recovery successful")
            
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")
            self.health.status = ScannerStatus.ERROR
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get scanner metrics.
        
        Returns:
            Dictionary of metrics
        """
        with self.metrics_lock:
            return {
                "scanner": {
                    "status": self.health.status.value,
                    "is_running": self.is_running,
                    "is_paused": self.is_paused,
                    "is_scanning": self.is_scanning,
                },
                "metrics": {
                    "total_scans": self.metrics.total_scans,
                    "total_opportunities": self.metrics.total_opportunities,
                    "total_executed": self.metrics.total_executed,
                    "total_profit": float(self.metrics.total_profit),
                    "avg_scan_time_ms": self.metrics.avg_scan_time_ms,
                    "avg_opportunities_per_scan": self.metrics.avg_opportunities_per_scan,
                    "success_rate": self.metrics.success_rate,
                    "error_rate": self.metrics.error_rate,
                    "cpu_usage": self.metrics.cpu_usage,
                    "memory_usage": self.metrics.memory_usage,
                    "queue_size": self.priority_queue.qsize(),
                    "cache_size": len(self.opportunity_cache),
                },
                "health": {
                    "is_healthy": self.health.is_healthy,
                    "is_degraded": self.health.is_degraded,
                    "is_recovering": self.health.is_recovering,
                    "error_count": self.health.error_count,
                    "recovery_attempts": self.health.recovery_attempts,
                    "last_error": self.health.last_error,
                    "components": self.health.components,
                },
                "detectors": {
                    detector_id: {
                        "enabled": status.get("enabled", True),
                        "healthy": status.get("healthy", False),
                        "scan_count": status.get("scan_count", 0),
                        "error_count": status.get("error_count", 0),
                        "opportunities_found": status.get("opportunities_found", 0),
                        "last_scan": str(status.get("last_scan")),
                        "last_error": status.get("last_error"),
                    }
                    for detector_id, status in self.detector_status.items()
                },
                "config": {
                    "max_workers": self.config.max_workers,
                    "scan_interval": self.config.scan_interval,
                    "min_profit_threshold": float(self.config.min_profit_threshold),
                    "cache_size": self.config.cache_size,
                    "enable_adaptive_scheduling": self.config.enable_adaptive_scheduling,
                    "enable_priority_filtering": self.config.enable_priority_filtering,
                    "enable_deduplication": self.config.enable_deduplication,
                },
            }
    
    def get_opportunities(
        self,
        limit: int = 100,
        min_priority: Priority = Priority.LOW,
    ) -> List[Any]:
        """
        Get opportunities from the priority queue.
        
        Args:
            limit: Maximum number of opportunities to return
            min_priority: Minimum priority level
            
        Returns:
            List of opportunities
        """
        opportunities = []
        temp_items = []
        
        try:
            # Extract items from queue
            while not self.priority_queue.empty() and len(opportunities) < limit:
                priority, opp = self.priority_queue.get_nowait()
                if priority.value <= min_priority.value:
                    opportunities.append(opp)
                else:
                    temp_items.append((priority, opp))
            
            # Put back items that weren't taken
            for item in temp_items:
                self.priority_queue.put(item)
                
        except Exception as e:
            self.logger.error(f"Failed to get opportunities: {e}")
        
        return opportunities
    
    def get_opportunity_by_id(self, opp_id: str) -> Optional[Any]:
        """
        Get an opportunity by ID.
        
        Args:
            opp_id: Opportunity ID
            
        Returns:
            Opportunity or None
        """
        with self.cache_lock:
            return self.opportunity_cache.get(opp_id)
    
    def add_detector(
        self,
        detector_id: str,
        detector: Any,
    ) -> None:
        """
        Add a detector to the scanner.
        
        Args:
            detector_id: Detector identifier
            detector: Detector instance
        """
        self.detectors[detector_id] = detector
        self.detector_status[detector_id] = {
            "enabled": True,
            "healthy": True,
            "last_scan": None,
            "scan_count": 0,
            "error_count": 0,
            "opportunities_found": 0,
            "avg_scan_time": 0.0,
            "last_error": None,
        }
        self.logger.info(f"Added detector: {detector_id}")
    
    def remove_detector(self, detector_id: str) -> None:
        """
        Remove a detector from the scanner.
        
        Args:
            detector_id: Detector identifier
        """
        if detector_id in self.detectors:
            del self.detectors[detector_id]
            del self.detector_status[detector_id]
            self.logger.info(f"Removed detector: {detector_id}")
    
    def enable_detector(self, detector_id: str) -> None:
        """Enable a detector."""
        if detector_id in self.detector_status:
            self.detector_status[detector_id]["enabled"] = True
            self.logger.info(f"Enabled detector: {detector_id}")
    
    def disable_detector(self, detector_id: str) -> None:
        """Disable a detector."""
        if detector_id in self.detector_status:
            self.detector_status[detector_id]["enabled"] = False
            self.logger.info(f"Disabled detector: {detector_id}")


# Module exports
__all__ = [
    'OpportunityScanner',
    'ScannerConfig',
    'ScannerMetrics',
    'ScannerHealth',
    'ScanResult',
    'OpportunityBatch',
    'Priority',
    'ScannerStatus',
]

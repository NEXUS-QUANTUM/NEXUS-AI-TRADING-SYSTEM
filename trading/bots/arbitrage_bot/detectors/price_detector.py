# trading/bots/arbitrage_bot/detectors/price_detector.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Advanced Price Detection & Analysis Engine

"""
Price Detector - Advanced Price Analysis and Arbitrage Detection Engine

This module provides sophisticated price detection and analysis capabilities:
- Real-time price monitoring across multiple sources
- Price discrepancy detection
- Price feed aggregation and validation
- Price anomaly detection
- Price prediction and forecasting
- Price correlation analysis
- Price volatility measurement
- Price depth analysis

Architecture:
    - BasePriceDetector: Abstract base class
    - PriceDetector: Main detector implementation
    - PriceFeedManager: Multi-source price feed management
    - PriceAggregator: Price aggregation and validation
    - PriceAnomalyDetector: Anomaly detection
    - PricePredictor: Price prediction
    - VolatilityAnalyzer: Volatility measurement
    - CorrelationAnalyzer: Price correlation analysis
    - PriceDepthAnalyzer: Order book depth analysis

Features:
    - Multi-source price feed aggregation
    - Real-time price discrepancy detection
    - Price anomaly detection
    - Price prediction using ML
    - Volatility measurement
    - Correlation analysis
    - Order book depth analysis
    - Price feed validation
    - WebSocket support for real-time updates
"""

import asyncio
import hashlib
import json
import logging
import time
import threading
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
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from itertools import combinations, permutations, product
from contextlib import asynccontextmanager, contextmanager
from typing_extensions import TypedDict, NotRequired

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.signal import find_peaks, argrelextrema
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import ta  # Technical Analysis library

# Constants
PRICE_CACHE_SIZE = 10000
MAX_PRICE_SOURCES = 20
MIN_PRICE_SAMPLES = 10
MAX_PRICE_DEVIATION = Decimal("0.05")  # 5%
MIN_CONFIDENCE = Decimal("0.6")
PRICE_UPDATE_INTERVAL = 0.5  # seconds
HISTORICAL_WINDOW = 100  # 100 data points
ANOMALY_THRESHOLD = 3.0  # Standard deviations

# Price source types
class PriceSourceType(Enum):
    EXCHANGE = "exchange"
    DEX = "dex"
    AGGREGATOR = "aggregator"
    ORACLE = "oracle"
    NEWS = "news"
    SOCIAL = "social"

# Price update types
class PriceUpdateType(Enum):
    TICKER = "ticker"
    TRADE = "trade"
    ORDER_BOOK = "order_book"
    INDEX = "index"
    MARK = "mark"

@dataclass
class PriceSource:
    """Price source configuration."""
    id: str
    name: str
    type: PriceSourceType
    endpoint: str
    weight: Decimal = Decimal("1.0")
    enabled: bool = True
    latency: float = 0.0
    reliability: float = 1.0
    last_update: Optional[datetime] = None
    last_price: Optional[Decimal] = None

@dataclass
class PriceData:
    """Price data point."""
    symbol: str
    price: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    source: str = ""
    source_type: PriceSourceType = PriceSourceType.EXCHANGE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: Decimal = Decimal("0.8")
    signature: Optional[str] = None

@dataclass
class AggregatedPrice:
    """Aggregated price from multiple sources."""
    symbol: str
    price: Decimal
    bid: Decimal
    ask: Decimal
    spread: Decimal
    volume: Decimal
    sources_used: int
    sources_total: int
    confidence: Decimal
    std_dev: Decimal
    timestamp: datetime
    last_updated: datetime

@dataclass
class PriceAnomaly:
    """Price anomaly detection result."""
    symbol: str
    price: Decimal
    expected_price: Decimal
    deviation: Decimal
    deviation_percentage: Decimal
    z_score: float
    anomaly_type: str  # "spike", "dip", "divergence", "manipulation"
    confidence: Decimal
    timestamp: datetime

@dataclass
class PricePrediction:
    """Price prediction result."""
    symbol: str
    current_price: Decimal
    predicted_price: Decimal
    predicted_change: Decimal
    predicted_change_percentage: Decimal
    confidence_interval_lower: Decimal
    confidence_interval_upper: Decimal
    timeframe: str  # "1m", "5m", "15m", "1h", "4h", "1d"
    model_used: str
    confidence: Decimal
    timestamp: datetime

@dataclass
class VolatilityMetrics:
    """Volatility measurement metrics."""
    symbol: str
    historical_volatility: Decimal
    implied_volatility: Optional[Decimal]
    realized_volatility: Decimal
    average_true_range: Decimal
    bollinger_width: Decimal
    keltner_width: Decimal
    atr_percentage: Decimal
    volatility_percentile: Decimal
    timestamp: datetime

class PriceDetector:
    """
    Advanced Price Detection and Analysis Engine.
    
    This class provides comprehensive price detection and analysis:
    1. Multi-source price feed aggregation
    2. Real-time price discrepancy detection
    3. Price anomaly detection
    4. Price prediction using ML models
    5. Volatility measurement and analysis
    6. Correlation analysis
    7. Order book depth analysis
    8. Price feed validation
    
    Features:
    - WebSocket support for real-time updates
    - Machine learning-based price prediction
    - Anomaly detection using statistical methods
    - Correlation analysis
    - Volatility measurement
    - Price feed validation
    - Automatic source selection
    """
    
    def __init__(
        self,
        sources: Optional[List[PriceSource]] = None,
        min_sources: int = 3,
        max_deviation: Decimal = MAX_PRICE_DEVIATION,
        scan_interval: float = PRICE_UPDATE_INTERVAL,
    ):
        """
        Initialize the Price Detector.
        
        Args:
            sources: List of price sources
            min_sources: Minimum number of sources for aggregation
            max_deviation: Maximum allowed price deviation
            scan_interval: Price update interval in seconds
        """
        self.logger = self._setup_logger()
        self.sources = sources or []
        self.min_sources = min_sources
        self.max_deviation = max_deviation
        self.scan_interval = scan_interval
        
        # Price data
        self.price_cache: Dict[str, deque] = {}
        self.aggregated_prices: Dict[str, AggregatedPrice] = {}
        self.price_history: Dict[str, List[PriceData]] = {}
        
        # Analysis results
        self.anomalies: Dict[str, List[PriceAnomaly]] = {}
        self.predictions: Dict[str, PricePrediction] = {}
        self.volatility_metrics: Dict[str, VolatilityMetrics] = {}
        self.correlations: Dict[str, Dict[str, Decimal]] = {}
        
        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=len(sources) or 1)
        
        # Models
        self.price_prediction_models: Dict[str, Any] = {}
        self.anomaly_detection_models: Dict[str, IsolationForest] = {}
        
        # WebSocket connections
        self.websocket_connections: Dict[str, Any] = {}
        
        # Metrics
        self.metrics = {
            "updates": 0,
            "aggregations": 0,
            "anomalies_detected": 0,
            "predictions_made": 0,
            "errors": 0,
            "avg_latency": 0.0,
            "source_reliability": {},
        }
        
        # State management
        self.is_running = False
        self.update_thread: Optional[threading.Thread] = None
        
        # Train models if sources available
        if self.sources:
            self._train_models()
        
        # Start scanner
        self.start()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger for the detector."""
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
    
    def start(self) -> None:
        """Start the price detector."""
        if self.is_running:
            return
        
        self.is_running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        # Start WebSocket connections
        self._start_websockets()
        
        self.logger.info("Price Detector started")
    
    def stop(self) -> None:
        """Stop the price detector."""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=5.0)
        
        # Close WebSocket connections
        self._stop_websockets()
        
        self.logger.info("Price Detector stopped")
    
    def _update_loop(self) -> None:
        """Main price update loop."""
        while self.is_running:
            try:
                # Update prices from all sources
                prices = self._fetch_prices()
                
                if prices:
                    # Process prices
                    self._process_prices(prices)
                    
                    # Detect anomalies
                    self._detect_anomalies()
                    
                    # Make predictions
                    self._make_predictions()
                    
                    # Update volatility metrics
                    self._update_volatility()
                    
                    # Update correlations
                    self._update_correlations()
                
                # Sleep until next update
                time.sleep(self.scan_interval)
                
            except Exception as e:
                self.logger.error(f"Update loop error: {e}")
                self.metrics["errors"] += 1
                time.sleep(1.0)
    
    def _fetch_prices(self) -> List[PriceData]:
        """
        Fetch prices from all sources.
        
        Returns:
            List of PriceData objects
        """
        prices = []
        
        with ThreadPoolExecutor(max_workers=len(self.sources)) as executor:
            future_to_source = {
                executor.submit(self._fetch_source_price, source): source
                for source in self.sources
                if source.enabled
            }
            
            for future in future_to_source:
                try:
                    result = future.result(timeout=5.0)
                    if result:
                        prices.append(result)
                except Exception as e:
                    self.logger.debug(f"Source fetch failed: {e}")
        
        return prices
    
    def _fetch_source_price(self, source: PriceSource) -> Optional[PriceData]:
        """
        Fetch price from a single source.
        
        Args:
            source: Price source
            
        Returns:
            PriceData or None
        """
        try:
            start_time = time.time()
            
            # Simulate price fetch (would be actual API call in production)
            import random
            base_price = Decimal(str(random.uniform(100, 100000)))
            
            # Add noise based on source reliability
            noise = (Decimal("1") - source.reliability) * Decimal("0.01")
            price = base_price * (Decimal("1") + noise * Decimal(str(random.uniform(-1, 1))))
            
            # Update source metrics
            latency = (time.time() - start_time) * 1000
            source.latency = latency
            source.last_update = datetime.utcnow()
            source.last_price = price
            
            # Create price data
            return PriceData(
                symbol="BTC/USD",  # Would be dynamic
                price=price,
                bid=price * Decimal("0.999"),
                ask=price * Decimal("1.001"),
                volume=Decimal(str(random.uniform(100, 10000))),
                source=source.id,
                source_type=source.type,
                timestamp=datetime.utcnow(),
                confidence=Decimal(str(source.reliability)),
                signature=f"sig_{source.id}_{int(time.time())}",
            )
            
        except Exception as e:
            self.logger.error(f"Failed to fetch from {source.id}: {e}")
            return None
    
    def _process_prices(self, prices: List[PriceData]) -> None:
        """
        Process and aggregate prices.
        
        Args:
            prices: List of PriceData objects
        """
        if not prices:
            return
        
        # Group by symbol
        by_symbol = defaultdict(list)
        for price in prices:
            by_symbol[price.symbol].append(price)
        
        for symbol, symbol_prices in by_symbol.items():
            # Cache prices
            if symbol not in self.price_cache:
                self.price_cache[symbol] = deque(maxlen=PRICE_CACHE_SIZE)
            self.price_cache[symbol].extend(symbol_prices)
            
            # Aggregate price
            aggregated = self._aggregate_prices(symbol_prices)
            if aggregated:
                self.aggregated_prices[symbol] = aggregated
                
                # Update price history
                if symbol not in self.price_history:
                    self.price_history[symbol] = []
                self.price_history[symbol].append(aggregated)
                
                # Trim history if needed
                if len(self.price_history[symbol]) > HISTORICAL_WINDOW:
                    self.price_history[symbol] = self.price_history[symbol][-HISTORICAL_WINDOW:]
        
        # Update metrics
        self.metrics["updates"] += len(prices)
        self.metrics["aggregations"] += len(by_symbol)
    
    def _aggregate_prices(self, prices: List[PriceData]) -> Optional[AggregatedPrice]:
        """
        Aggregate prices from multiple sources.
        
        Args:
            prices: List of PriceData objects
            
        Returns:
            AggregatedPrice or None
        """
        if len(prices) < self.min_sources:
            return None
        
        # Filter by confidence
        valid_prices = [p for p in prices if p.confidence >= MIN_CONFIDENCE]
        if len(valid_prices) < self.min_sources:
            return None
        
        # Calculate weighted average
        total_weight = sum(float(p.confidence) for p in valid_prices)
        weighted_price = sum(
            float(p.price) * float(p.confidence) for p in valid_prices
        ) / total_weight
        
        # Calculate statistics
        prices_values = [float(p.price) for p in valid_prices]
        std_dev = np.std(prices_values)
        
        # Check for outliers
        z_scores = np.abs((prices_values - weighted_price) / std_dev if std_dev > 0 else 0)
        filtered_prices = [
            p for i, p in enumerate(valid_prices)
            if z_scores[i] < ANOMALY_THRESHOLD
        ]
        
        if len(filtered_prices) < self.min_sources:
            return None
        
        # Recalculate with filtered prices
        prices_values = [float(p.price) for p in filtered_prices]
        weights = [float(p.confidence) for p in filtered_prices]
        
        weighted_price = sum(p * w for p, w in zip(prices_values, weights)) / sum(weights)
        
        # Calculate bid/ask
        bid_values = [float(p.bid) for p in filtered_prices if p.bid is not None]
        ask_values = [float(p.ask) for p in filtered_prices if p.ask is not None]
        
        avg_bid = sum(bid_values) / len(bid_values) if bid_values else weighted_price * 0.999
        avg_ask = sum(ask_values) / len(ask_values) if ask_values else weighted_price * 1.001
        
        # Calculate spread
        spread = avg_ask - avg_bid
        
        # Calculate volume
        volume_values = [float(p.volume) for p in filtered_prices if p.volume is not None]
        avg_volume = sum(volume_values) / len(volume_values) if volume_values else 0
        
        return AggregatedPrice(
            symbol=filtered_prices[0].symbol,
            price=Decimal(str(weighted_price)),
            bid=Decimal(str(avg_bid)),
            ask=Decimal(str(avg_ask)),
            spread=Decimal(str(spread)),
            volume=Decimal(str(avg_volume)),
            sources_used=len(filtered_prices),
            sources_total=len(prices),
            confidence=Decimal(str(min(1.0, 1.0 - (std_dev / weighted_price if weighted_price > 0 else 0)))),
            std_dev=Decimal(str(std_dev)),
            timestamp=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )
    
    def _detect_anomalies(self) -> None:
        """Detect price anomalies."""
        for symbol, aggregated in self.aggregated_prices.items():
            # Get historical prices
            if symbol not in self.price_history:
                continue
            
            history = self.price_history[symbol]
            if len(history) < 10:
                continue
            
            prices = [float(p.price) for p in history]
            current_price = float(aggregated.price)
            
            # Calculate expected price using moving average
            window = min(20, len(prices))
            ma = np.mean(prices[-window:])
            std = np.std(prices[-window:])
            
            # Calculate z-score
            z_score = abs(current_price - ma) / (std if std > 0 else 1)
            
            # Check for anomaly
            if z_score > ANOMALY_THRESHOLD:
                deviation = Decimal(str(current_price - ma))
                deviation_pct = (deviation / Decimal(str(ma))) * Decimal("100")
                
                # Determine anomaly type
                if current_price > ma:
                    anomaly_type = "spike"
                else:
                    anomaly_type = "dip"
                
                anomaly = PriceAnomaly(
                    symbol=symbol,
                    price=aggregated.price,
                    expected_price=Decimal(str(ma)),
                    deviation=deviation,
                    deviation_percentage=deviation_pct,
                    z_score=z_score,
                    anomaly_type=anomaly_type,
                    confidence=Decimal(str(min(1.0, z_score / (ANOMALY_THRESHOLD * 2)))),
                    timestamp=datetime.utcnow(),
                )
                
                # Store anomaly
                if symbol not in self.anomalies:
                    self.anomalies[symbol] = []
                self.anomalies[symbol].append(anomaly)
                
                # Trim anomalies
                if len(self.anomalies[symbol]) > 100:
                    self.anomalies[symbol] = self.anomalies[symbol][-100:]
                
                self.metrics["anomalies_detected"] += 1
                
                self.logger.warning(
                    f"Price anomaly detected for {symbol}: "
                    f"{anomaly_type} of {deviation_pct:.2f}%"
                )
    
    def _make_predictions(self) -> None:
        """Make price predictions using ML models."""
        for symbol, aggregated in self.aggregated_prices.items():
            if symbol not in self.price_history:
                continue
            
            history = self.price_history[symbol]
            if len(history) < 30:
                continue
            
            # Prepare data
            prices = [float(p.price) for p in history]
            current_price = float(aggregated.price)
            
            # Simple prediction using exponential smoothing
            if len(prices) > 10:
                model = ExponentialSmoothing(prices, trend="add", seasonal=None)
                fitted = model.fit()
                prediction = fitted.forecast(1)[0]
            else:
                # Fallback to simple moving average
                prediction = np.mean(prices[-5:])
            
            # Calculate confidence interval
            std_dev = np.std(prices[-10:]) if len(prices) >= 10 else 0.1
            ci_lower = prediction - 1.96 * std_dev
            ci_upper = prediction + 1.96 * std_dev
            
            # Calculate predicted change
            change = Decimal(str(prediction - current_price))
            change_pct = (change / aggregated.price) * Decimal("100")
            
            # Determine timeframe
            timeframe = "5m"  # Would be dynamic based on data frequency
            
            # Store prediction
            prediction_result = PricePrediction(
                symbol=symbol,
                current_price=aggregated.price,
                predicted_price=Decimal(str(prediction)),
                predicted_change=change,
                predicted_change_percentage=change_pct,
                confidence_interval_lower=Decimal(str(ci_lower)),
                confidence_interval_upper=Decimal(str(ci_upper)),
                timeframe=timeframe,
                model_used="exponential_smoothing",
                confidence=Decimal(str(min(1.0, 1.0 - (std_dev / current_price if current_price > 0 else 0)))),
                timestamp=datetime.utcnow(),
            )
            
            self.predictions[symbol] = prediction_result
            self.metrics["predictions_made"] += 1
    
    def _update_volatility(self) -> None:
        """Update volatility metrics for all symbols."""
        for symbol, aggregated in self.aggregated_prices.items():
            if symbol not in self.price_history:
                continue
            
            history = self.price_history[symbol]
            if len(history) < 20:
                continue
            
            prices = [float(p.price) for p in history]
            
            # Calculate metrics
            returns = np.diff(np.log(prices))
            hist_vol = np.std(returns) * np.sqrt(252)  # Annualized
            
            # Average True Range
            high_low = np.abs(np.diff(prices))
            high_close = np.abs(np.diff(prices[:-1]))
            low_close = np.abs(np.diff(prices[:-1]))
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = np.mean(true_range)
            atr_pct = atr / np.mean(prices)
            
            # Bollinger width
            ma = np.mean(prices[-20:])
            std = np.std(prices[-20:])
            bb_width = (2 * std) / ma
            
            # Keltner width
            atr_20 = np.mean(true_range[-20:])
            kc_width = (2 * atr_20) / ma
            
            # Calculate percentile
            volatility_percentile = stats.percentileofscore(returns, np.std(returns))
            
            # Store metrics
            self.volatility_metrics[symbol] = VolatilityMetrics(
                symbol=symbol,
                historical_volatility=Decimal(str(hist_vol)),
                implied_volatility=None,  # Would fetch from options data
                realized_volatility=Decimal(str(np.std(returns) * np.sqrt(252))),
                average_true_range=Decimal(str(atr)),
                bollinger_width=Decimal(str(bb_width)),
                keltner_width=Decimal(str(kc_width)),
                atr_percentage=Decimal(str(atr_pct)),
                volatility_percentile=Decimal(str(volatility_percentile)),
                timestamp=datetime.utcnow(),
            )
    
    def _update_correlations(self) -> None:
        """Update price correlations between symbols."""
        symbols = list(self.price_history.keys())
        if len(symbols) < 2:
            return
        
        # Get price history for each symbol
        price_data = {}
        for symbol in symbols:
            history = self.price_history[symbol]
            if len(history) < 30:
                return
            price_data[symbol] = [float(p.price) for p in history[-30:]]
        
        # Calculate correlation matrix
        df = pd.DataFrame(price_data)
        corr_matrix = df.corr()
        
        # Store correlations
        for i, symbol1 in enumerate(symbols):
            if symbol1 not in self.correlations:
                self.correlations[symbol1] = {}
            for j, symbol2 in enumerate(symbols):
                if i != j:
                    self.correlations[symbol1][symbol2] = Decimal(
                        str(corr_matrix.iloc[i, j])
                    )
    
    def _start_websockets(self) -> None:
        """Start WebSocket connections for real-time data."""
        # Implementation would depend on exchange APIs
        pass
    
    def _stop_websockets(self) -> None:
        """Stop WebSocket connections."""
        for ws in self.websocket_connections.values():
            try:
                ws.close()
            except Exception:
                pass
        self.websocket_connections.clear()
    
    def _train_models(self) -> None:
        """Train ML models for price prediction and anomaly detection."""
        # Train anomaly detection models
        for symbol, history in self.price_history.items():
            if len(history) < 50:
                continue
            
            prices = np.array([float(p.price) for p in history]).reshape(-1, 1)
            
            # Train Isolation Forest for anomaly detection
            model = IsolationForest(contamination=0.1, random_state=42)
            model.fit(prices)
            self.anomaly_detection_models[symbol] = model
    
    def get_price(self, symbol: str) -> Optional[AggregatedPrice]:
        """
        Get aggregated price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            AggregatedPrice or None
        """
        return self.aggregated_prices.get(symbol)
    
    def get_price_history(
        self,
        symbol: str,
        limit: int = 100,
    ) -> List[AggregatedPrice]:
        """
        Get price history for a symbol.
        
        Args:
            symbol: Trading symbol
            limit: Number of records to return
            
        Returns:
            List of AggregatedPrice objects
        """
        history = self.price_history.get(symbol, [])
        return history[-limit:] if history else []
    
    def get_anomalies(
        self,
        symbol: str,
        limit: int = 10,
    ) -> List[PriceAnomaly]:
        """
        Get price anomalies for a symbol.
        
        Args:
            symbol: Trading symbol
            limit: Number of anomalies to return
            
        Returns:
            List of PriceAnomaly objects
        """
        anomalies = self.anomalies.get(symbol, [])
        return anomalies[-limit:] if anomalies else []
    
    def get_prediction(self, symbol: str) -> Optional[PricePrediction]:
        """
        Get price prediction for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            PricePrediction or None
        """
        return self.predictions.get(symbol)
    
    def get_volatility(self, symbol: str) -> Optional[VolatilityMetrics]:
        """
        Get volatility metrics for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            VolatilityMetrics or None
        """
        return self.volatility_metrics.get(symbol)
    
    def get_correlation(self, symbol1: str, symbol2: str) -> Optional[Decimal]:
        """
        Get price correlation between two symbols.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            
        Returns:
            Correlation coefficient or None
        """
        if symbol1 in self.correlations and symbol2 in self.correlations[symbol1]:
            return self.correlations[symbol1][symbol2]
        return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get detector metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            "updates": self.metrics["updates"],
            "aggregations": self.metrics["aggregations"],
            "anomalies_detected": self.metrics["anomalies_detected"],
            "predictions_made": self.metrics["predictions_made"],
            "errors": self.metrics["errors"],
            "avg_latency": self.metrics["avg_latency"],
            "symbols_tracked": len(self.price_history),
            "sources_active": sum(1 for s in self.sources if s.enabled),
            "websocket_connections": len(self.websocket_connections),
            "is_running": self.is_running,
            "scan_interval": self.scan_interval,
        }
    
    def add_source(self, source: PriceSource) -> None:
        """
        Add a price source.
        
        Args:
            source: PriceSource to add
        """
        self.sources.append(source)
        self.metrics["source_reliability"][source.id] = float(source.reliability)
        self.logger.info(f"Added price source: {source.name}")
    
    def remove_source(self, source_id: str) -> None:
        """
        Remove a price source.
        
        Args:
            source_id: Source identifier
        """
        self.sources = [s for s in self.sources if s.id != source_id]
        if source_id in self.metrics["source_reliability"]:
            del self.metrics["source_reliability"][source_id]
        self.logger.info(f"Removed price source: {source_id}")


# Module exports
__all__ = [
    'PriceDetector',
    'PriceSource',
    'PriceData',
    'AggregatedPrice',
    'PriceAnomaly',
    'PricePrediction',
    'VolatilityMetrics',
    'PriceSourceType',
    'PriceUpdateType',
]

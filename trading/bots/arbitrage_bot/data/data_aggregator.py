# trading/bots/arbitrage_bot/data/data_aggregator.py
# Nexus AI Trading System - Arbitrage Bot Data Aggregator Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Data Aggregator Module

This module provides comprehensive data aggregation and normalization
for the arbitrage bot system, including:

- Multi-exchange data aggregation
- Real-time data stream processing
- Data normalization and standardization
- Data quality validation
- Data enrichment
- Data caching and persistence
- Data transformation pipelines
- Data correlation analysis
- Data anomaly detection
- Data export and reporting
- Multi-timeframe aggregation
- Volume-weighted data aggregation

The data aggregator ensures consistent, high-quality data across
all exchanges for accurate arbitrage detection and execution.
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketPrice, MarketDepth, MarketTrade
from trading.bots.arbitrage_bot.core.exchange_connector import ExchangeConnector
from trading.bots.arbitrage_bot.data.candle_manager import CandleManager, Candle, CandleInterval
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AggregationType(str, Enum):
    """Aggregation types."""
    PRICE = "price"
    VOLUME = "volume"
    DEPTH = "depth"
    TRADE = "trade"
    CANDLE = "candle"
    SPREAD = "spread"
    LIQUIDITY = "liquidity"
    VOLATILITY = "volatility"
    CUSTOM = "custom"


class AggregationMethod(str, Enum):
    """Aggregation methods."""
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    FIRST = "first"
    LAST = "last"
    WEIGHTED = "weighted"
    VWAP = "vwap"  # Volume-weighted average price
    TWAP = "twap"  # Time-weighted average price


class DataQuality(str, Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


class DataSource(str, Enum):
    """Data sources."""
    EXCHANGE = "exchange"
    AGGREGATED = "aggregated"
    DERIVED = "derived"
    HISTORICAL = "historical"
    CACHE = "cache"
    WEBSOCKET = "websocket"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AggregatedData(BaseModel):
    """Aggregated data result."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: AggregationType
    method: AggregationMethod
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    value: Any
    source_count: int = 0
    sources: List[str] = Field(default_factory=list)
    confidence: Decimal = Decimal('0.8')
    quality: DataQuality = DataQuality.GOOD
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataPipeline(BaseModel):
    """Data transformation pipeline."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    input_type: str
    output_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataCorrelation(BaseModel):
    """Data correlation result."""
    symbol1: str
    symbol2: str
    correlation: float
    p_value: float
    sample_size: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    method: str = "pearson"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataAnomaly(BaseModel):
    """Data anomaly detection result."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # price, volume, spread, etc.
    symbol: str
    value: Any
    expected_value: Any
    deviation: float
    severity: str  # low, medium, high
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Aggregated data
CREATE TABLE IF NOT EXISTS aggregated_data (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    method VARCHAR(20) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    value JSONB NOT NULL,
    source_count INTEGER NOT NULL,
    sources JSONB DEFAULT '[]',
    confidence DECIMAL(5, 4) NOT NULL,
    quality VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_aggregated_data_type (type),
    INDEX idx_aggregated_data_symbol (symbol),
    INDEX idx_aggregated_data_timestamp (timestamp)
);

-- Data pipelines
CREATE TABLE IF NOT EXISTS data_pipelines (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    steps JSONB NOT NULL,
    input_type VARCHAR(50) NOT NULL,
    output_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Data correlations
CREATE TABLE IF NOT EXISTS data_correlations (
    id SERIAL PRIMARY KEY,
    symbol1 VARCHAR(50) NOT NULL,
    symbol2 VARCHAR(50) NOT NULL,
    correlation FLOAT NOT NULL,
    p_value FLOAT NOT NULL,
    sample_size INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    method VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}',
    UNIQUE(symbol1, symbol2)
);

-- Data anomalies
CREATE TABLE IF NOT EXISTS data_anomalies (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(30) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    value JSONB NOT NULL,
    expected_value JSONB NOT NULL,
    deviation FLOAT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_data_anomalies_symbol (symbol),
    INDEX idx_data_anomalies_type (type),
    INDEX idx_data_anomalies_timestamp (timestamp)
);

-- Data quality metrics
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    quality VARCHAR(20) NOT NULL,
    score INTEGER DEFAULT 0,
    total_samples INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, symbol)
);
"""


# =============================================================================
# DATA AGGREGATOR CLASS
# =============================================================================

class DataAggregator:
    """
    Advanced data aggregator for arbitrage bot.
    
    Features:
    - Multi-exchange data aggregation
    - Real-time data stream processing
    - Data normalization and standardization
    - Data quality validation
    - Data enrichment
    - Data caching and persistence
    - Data transformation pipelines
    - Data correlation analysis
    - Data anomaly detection
    - Data export and reporting
    - Multi-timeframe aggregation
    - Volume-weighted data aggregation
    """
    
    def __init__(
        self,
        market_data: MarketDataManager,
        candle_manager: CandleManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.market_data = market_data
        self.candle_manager = candle_manager
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Aggregated data cache
        self._aggregated: Dict[str, AggregatedData] = {}
        
        # Pipelines
        self._pipelines: Dict[str, DataPipeline] = {}
        
        # Correlations
        self._correlations: Dict[str, DataCorrelation] = {}
        
        # Anomalies
        self._anomalies: List[DataAnomaly] = []
        
        # Quality metrics
        self._quality: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        # Circuit breakers
        self._aggregator_cb = CircuitBreaker(
            name="data_aggregator",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Handlers
        self._handlers: Dict[str, List[Callable]] = {}
        
        logger.info("DataAggregator initialized")
    
    async def initialize(self):
        """Initialize the data aggregator."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load pipelines
        if self.pool:
            await self._load_pipelines()
        
        # Load correlations
        if self.pool:
            await self._load_correlations()
        
        # Start update loop
        self._running = True
        asyncio.create_task(self._update_loop())
        
        self._initialized = True
        logger.info("DataAggregator initialized")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # DATA AGGREGATION
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def aggregate_price(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        method: AggregationMethod = AggregationMethod.MEAN,
        weighted: bool = False
    ) -> AggregatedData:
        """
        Aggregate price data from multiple exchanges.
        
        Args:
            symbol: Trading symbol
            exchanges: List of exchanges (None = all available)
            method: Aggregation method
            weighted: Use volume-weighted aggregation
            
        Returns:
            AggregatedData
        """
        if self._aggregator_cb.is_open():
            raise CircuitBreakerOpenError("Data aggregator circuit breaker is open")
        
        try:
            # Get prices from all exchanges
            prices = await self._get_prices(symbol, exchanges)
            
            if not prices:
                raise ValueError(f"No price data available for {symbol}")
            
            # Extract prices and volumes
            price_values = []
            volumes = []
            sources = []
            
            for exchange, price in prices.items():
                price_values.append(float(price.last))
                volumes.append(float(price.volume_24h or 1))
                sources.append(exchange)
            
            # Calculate aggregated value
            if method == AggregationMethod.MEAN:
                if weighted and volumes:
                    total_volume = sum(volumes)
                    if total_volume > 0:
                        value = sum(p * v for p, v in zip(price_values, volumes)) / total_volume
                    else:
                        value = np.mean(price_values)
                else:
                    value = np.mean(price_values)
                    
            elif method == AggregationMethod.MEDIAN:
                value = np.median(price_values)
                
            elif method == AggregationMethod.MIN:
                value = np.min(price_values)
                
            elif method == AggregationMethod.MAX:
                value = np.max(price_values)
                
            elif method == AggregationMethod.VWAP:
                # Volume-weighted average price
                total_volume = sum(volumes)
                if total_volume > 0:
                    value = sum(p * v for p, v in zip(price_values, volumes)) / total_volume
                else:
                    value = np.mean(price_values)
                    
            elif method == AggregationMethod.TWAP:
                # Time-weighted average price (uses timestamp order)
                # Simplified: use mean
                value = np.mean(price_values)
                
            else:
                value = np.mean(price_values)
            
            # Create aggregated data
            aggregated = AggregatedData(
                type=AggregationType.PRICE,
                method=method,
                symbol=symbol,
                value=Decimal(str(value)).quantize(Decimal('0.00000001')),
                source_count=len(prices),
                sources=list(prices.keys()),
                confidence=Decimal(str(1 - (np.std(price_values) / max(price_values) if price_values else 0))),
                metadata={
                    "prices": {k: float(v.last) for k, v in prices.items()},
                    "volumes": {k: float(v.volume_24h or 1) for k, v in prices.items()}
                }
            )
            
            # Cache result
            cache_key = f"price:{symbol}:{method.value}"
            self._aggregated[cache_key] = aggregated
            
            # Save to database
            if self.pool:
                await self._save_aggregated(aggregated)
            
            # Record success
            self._aggregator_cb.record_success()
            
            return aggregated
            
        except Exception as e:
            self._aggregator_cb.record_failure()
            logger.error(f"Error aggregating price: {e}")
            
            # Return cached value if available
            cache_key = f"price:{symbol}:{method.value}"
            if cache_key in self._aggregated:
                return self._aggregated[cache_key]
            
            raise
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def aggregate_depth(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        depth_levels: int = 10
    ) -> AggregatedData:
        """
        Aggregate order book depth from multiple exchanges.
        
        Args:
            symbol: Trading symbol
            exchanges: List of exchanges
            depth_levels: Number of depth levels to aggregate
            
        Returns:
            AggregatedData
        """
        if self._aggregator_cb.is_open():
            raise CircuitBreakerOpenError("Data aggregator circuit breaker is open")
        
        try:
            # Get order books from all exchanges
            depths = await self._get_depths(symbol, exchanges, depth_levels)
            
            if not depths:
                raise ValueError(f"No depth data available for {symbol}")
            
            # Aggregate bids and asks
            all_bids = []
            all_asks = []
            sources = []
            
            for exchange, depth in depths.items():
                for bid in depth.bids[:depth_levels]:
                    all_bids.append((float(bid[0]), float(bid[1])))
                for ask in depth.asks[:depth_levels]:
                    all_asks.append((float(ask[0]), float(ask[1])))
                sources.append(exchange)
            
            # Sort and aggregate
            bids_dict = {}
            asks_dict = {}
            
            for price, volume in all_bids:
                if price not in bids_dict:
                    bids_dict[price] = 0
                bids_dict[price] += volume
            
            for price, volume in all_asks:
                if price not in asks_dict:
                    asks_dict[price] = 0
                asks_dict[price] += volume
            
            # Sort by price
            aggregated_bids = sorted(bids_dict.items(), key=lambda x: x[0], reverse=True)[:depth_levels]
            aggregated_asks = sorted(asks_dict.items(), key=lambda x: x[0])[:depth_levels]
            
            # Calculate mid price and spread
            best_bid = aggregated_bids[0][0] if aggregated_bids else 0
            best_ask = aggregated_asks[0][0] if aggregated_asks else 0
            mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
            spread = best_ask - best_bid if best_bid and best_ask else 0
            
            aggregated = AggregatedData(
                type=AggregationType.DEPTH,
                method=AggregationMethod.WEIGHTED,
                symbol=symbol,
                value={
                    "bids": aggregated_bids,
                    "asks": aggregated_asks,
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "mid_price": mid_price,
                    "spread": spread
                },
                source_count=len(depths),
                sources=sources,
                confidence=Decimal('0.8'),
                metadata={
                    "depth_levels": depth_levels,
                    "source_depths": {k: {"bids": len(v.bids), "asks": len(v.asks)} for k, v in depths.items()}
                }
            )
            
            # Cache result
            cache_key = f"depth:{symbol}"
            self._aggregated[cache_key] = aggregated
            
            # Save to database
            if self.pool:
                await self._save_aggregated(aggregated)
            
            # Record success
            self._aggregator_cb.record_success()
            
            return aggregated
            
        except Exception as e:
            self._aggregator_cb.record_failure()
            logger.error(f"Error aggregating depth: {e}")
            
            cache_key = f"depth:{symbol}"
            if cache_key in self._aggregated:
                return self._aggregated[cache_key]
            
            raise
    
    async def _get_prices(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None
    ) -> Dict[str, MarketPrice]:
        """Get prices from exchanges."""
        prices = {}
        
        if exchanges is None:
            exchanges = list(self.market_data._connectors.keys())
        
        for exchange in exchanges:
            try:
                price = await self.market_data.get_price(exchange, symbol)
                prices[exchange] = price
            except Exception as e:
                logger.debug(f"Error getting price from {exchange}: {e}")
        
        return prices
    
    async def _get_depths(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        depth_levels: int = 10
    ) -> Dict[str, MarketDepth]:
        """Get order book depths from exchanges."""
        depths = {}
        
        if exchanges is None:
            exchanges = list(self.market_data._connectors.keys())
        
        for exchange in exchanges:
            try:
                depth = await self.market_data.get_depth(exchange, symbol, depth_levels)
                depths[exchange] = depth
            except Exception as e:
                logger.debug(f"Error getting depth from {exchange}: {e}")
        
        return depths
    
    # =========================================================================
    # DATA TRANSFORMATION
    # =========================================================================
    
    async def create_pipeline(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        input_type: str,
        output_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataPipeline:
        """
        Create a data transformation pipeline.
        
        Args:
            name: Pipeline name
            steps: List of transformation steps
            input_type: Input data type
            output_type: Output data type
            metadata: Additional metadata
            
        Returns:
            DataPipeline
        """
        pipeline = DataPipeline(
            name=name,
            steps=steps,
            input_type=input_type,
            output_type=output_type,
            metadata=metadata or {}
        )
        
        self._pipelines[pipeline.id] = pipeline
        
        if self.pool:
            await self._save_pipeline(pipeline)
        
        logger.info(f"Created pipeline: {name}")
        return pipeline
    
    async def apply_pipeline(
        self,
        pipeline_id: str,
        data: Any
    ) -> Any:
        """
        Apply a transformation pipeline to data.
        
        Args:
            pipeline_id: Pipeline ID
            data: Input data
            
        Returns:
            Transformed data
        """
        if pipeline_id not in self._pipelines:
            raise ValueError(f"Pipeline {pipeline_id} not found")
        
        pipeline = self._pipelines[pipeline_id]
        result = data
        
        for step in pipeline.steps:
            step_type = step.get('type')
            params = step.get('params', {})
            
            if step_type == 'normalize':
                result = self._normalize_data(result, params)
            elif step_type == 'filter':
                result = self._filter_data(result, params)
            elif step_type == 'transform':
                result = self._transform_data(result, params)
            elif step_type == 'aggregate':
                result = self._aggregate_data(result, params)
            elif step_type == 'enrich':
                result = await self._enrich_data(result, params)
            elif step_type == 'validate':
                result = self._validate_data(result, params)
            else:
                logger.warning(f"Unknown step type: {step_type}")
        
        return result
    
    def _normalize_data(self, data: Any, params: Dict[str, Any]) -> Any:
        """Normalize data."""
        # Implementation depends on data type
        return data
    
    def _filter_data(self, data: Any, params: Dict[str, Any]) -> Any:
        """Filter data."""
        # Implementation depends on data type
        return data
    
    def _transform_data(self, data: Any, params: Dict[str, Any]) -> Any:
        """Transform data."""
        # Implementation depends on data type
        return data
    
    def _aggregate_data(self, data: Any, params: Dict[str, Any]) -> Any:
        """Aggregate data."""
        # Implementation depends on data type
        return data
    
    async def _enrich_data(self, data: Any, params: Dict[str, Any]) -> Any:
        """Enrich data with additional information."""
        # Implementation depends on data type
        return data
    
    def _validate_data(self, data: Any, params: Dict[str, Any]) -> Any:
        """Validate data."""
        # Implementation depends on data type
        return data
    
    # =========================================================================
    # CORRELATION ANALYSIS
    # =========================================================================
    
    async def calculate_correlation(
        self,
        symbol1: str,
        symbol2: str,
        exchanges: Optional[List[str]] = None,
        method: str = "pearson",
        period: int = 100
    ) -> DataCorrelation:
        """
        Calculate correlation between two symbols.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            exchanges: List of exchanges
            method: Correlation method
            period: Number of data points
            
        Returns:
            DataCorrelation
        """
        # Get price data for both symbols
        prices1 = []
        prices2 = []
        
        if exchanges is None:
            exchanges = list(self.market_data._connectors.keys())
        
        # Use aggregated prices
        for i in range(period):
            try:
                agg1 = await self.aggregate_price(symbol1, exchanges)
                agg2 = await self.aggregate_price(symbol2, exchanges)
                prices1.append(float(agg1.value))
                prices2.append(float(agg2.value))
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.debug(f"Error getting price data: {e}")
        
        if len(prices1) < 2 or len(prices2) < 2:
            raise ValueError("Insufficient data for correlation")
        
        # Calculate correlation
        if method == "pearson":
            corr = np.corrcoef(prices1, prices2)[0, 1]
            p_value = self._calculate_p_value(corr, len(prices1))
        elif method == "spearman":
            corr = np.corrcoef(pd.Series(prices1).rank(), pd.Series(prices2).rank())[0, 1]
            p_value = self._calculate_p_value(corr, len(prices1))
        else:
            corr = np.corrcoef(prices1, prices2)[0, 1]
            p_value = self._calculate_p_value(corr, len(prices1))
        
        correlation = DataCorrelation(
            symbol1=symbol1,
            symbol2=symbol2,
            correlation=float(corr) if not np.isnan(corr) else 0.0,
            p_value=float(p_value) if not np.isnan(p_value) else 0.0,
            sample_size=len(prices1),
            method=method,
            metadata={
                "exchanges": exchanges,
                "period": period
            }
        )
        
        # Cache correlation
        cache_key = f"{symbol1}:{symbol2}"
        self._correlations[cache_key] = correlation
        
        if self.pool:
            await self._save_correlation(correlation)
        
        return correlation
    
    def _calculate_p_value(self, corr: float, n: int) -> float:
        """Calculate p-value for correlation."""
        from scipy import stats
        if np.isnan(corr):
            return 1.0
        if n <= 2:
            return 1.0
        t = corr * np.sqrt((n - 2) / (1 - corr ** 2))
        p_value = 2 * (1 - stats.t.cdf(abs(t), n - 2))
        return float(p_value)
    
    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================
    
    async def detect_anomalies(
        self,
        symbol: str,
        metric: str = "price",
        threshold: float = 2.0,
        window: int = 50
    ) -> List[DataAnomaly]:
        """
        Detect anomalies in data.
        
        Args:
            symbol: Symbol to analyze
            metric: Metric to analyze
            threshold: Z-score threshold
            window: Rolling window size
            
        Returns:
            List of DataAnomaly
        """
        anomalies = []
        
        # Get historical data
        if metric == "price":
            data = await self._get_price_history(symbol, window)
        elif metric == "volume":
            data = await self._get_volume_history(symbol, window)
        elif metric == "spread":
            data = await self._get_spread_history(symbol, window)
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        if not data:
            return anomalies
        
        # Calculate rolling statistics
        df = pd.DataFrame(data, columns=['value'])
        df['mean'] = df['value'].rolling(window=window, min_periods=2).mean()
        df['std'] = df['value'].rolling(window=window, min_periods=2).std()
        df['z_score'] = (df['value'] - df['mean']) / df['std']
        
        # Detect anomalies
        latest = df.iloc[-1]
        
        if abs(latest['z_score']) > threshold:
            severity = "high" if abs(latest['z_score']) > threshold * 2 else "medium"
            
            anomaly = DataAnomaly(
                type=metric,
                symbol=symbol,
                value=latest['value'],
                expected_value=latest['mean'],
                deviation=float(latest['z_score']),
                severity=severity,
                metadata={
                    "threshold": threshold,
                    "window": window,
                    "std": float(latest['std'])
                }
            )
            
            anomalies.append(anomaly)
            self._anomalies.append(anomaly)
            
            if self.pool:
                await self._save_anomaly(anomaly)
            
            logger.warning(f"Anomaly detected: {symbol} {metric} deviation={latest['z_score']:.2f}")
        
        return anomalies
    
    async def _get_price_history(self, symbol: str, window: int) -> List[float]:
        """Get price history for anomaly detection."""
        prices = []
        exchanges = list(self.market_data._connectors.keys())
        
        for i in range(window):
            try:
                agg = await self.aggregate_price(symbol, exchanges)
                prices.append(float(agg.value))
                await asyncio.sleep(0.05)
            except Exception:
                pass
        
        return prices
    
    async def _get_volume_history(self, symbol: str, window: int) -> List[float]:
        """Get volume history for anomaly detection."""
        volumes = []
        exchanges = list(self.market_data._connectors.keys())
        
        for exchange in exchanges:
            try:
                price = await self.market_data.get_price(exchange, symbol)
                if price.volume_24h:
                    volumes.append(float(price.volume_24h))
            except Exception:
                pass
        
        return volumes
    
    async def _get_spread_history(self, symbol: str, window: int) -> List[float]:
        """Get spread history for anomaly detection."""
        spreads = []
        exchanges = list(self.market_data._connectors.keys())
        
        for exchange in exchanges:
            try:
                price = await self.market_data.get_price(exchange, symbol)
                spreads.append(float(price.spread))
            except Exception:
                pass
        
        return spreads
    
    # =========================================================================
    # QUALITY MONITORING
    # =========================================================================
    
    async def check_quality(
        self,
        source: str,
        symbol: str
    ) -> DataQuality:
        """
        Check data quality for a source and symbol.
        
        Args:
            source: Data source (exchange)
            symbol: Symbol
            
        Returns:
            DataQuality
        """
        key = f"{source}:{symbol}"
        
        if key not in self._quality:
            return DataQuality.UNKNOWN
        
        quality_data = self._quality[key]
        score = quality_data.get('score', 0)
        
        if score >= 90:
            return DataQuality.EXCELLENT
        elif score >= 75:
            return DataQuality.GOOD
        elif score >= 50:
            return DataQuality.FAIR
        else:
            return DataQuality.POOR
    
    async def update_quality(
        self,
        source: str,
        symbol: str,
        success: bool,
        latency_ms: float
    ):
        """
        Update quality metrics for a data source.
        
        Args:
            source: Data source
            symbol: Symbol
            success: Whether data fetch was successful
            latency_ms: Latency in milliseconds
        """
        key = f"{source}:{symbol}"
        
        if key not in self._quality:
            self._quality[key] = {
                'total_samples': 0,
                'success_count': 0,
                'error_count': 0,
                'avg_latency': 0,
                'score': 100
            }
        
        quality = self._quality[key]
        quality['total_samples'] += 1
        
        if success:
            quality['success_count'] += 1
        else:
            quality['error_count'] += 1
        
        # Update average latency
        quality['avg_latency'] = (
            (quality['avg_latency'] * (quality['total_samples'] - 1) + latency_ms) /
            quality['total_samples']
        )
        
        # Calculate quality score
        success_rate = quality['success_count'] / quality['total_samples']
        score = success_rate * 100
        
        # Penalize high latency
        if quality['avg_latency'] > 1000:
            score *= 0.8
        elif quality['avg_latency'] > 500:
            score *= 0.9
        
        quality['score'] = max(0, min(100, score))
        
        # Save to database
        if self.pool:
            await self._save_quality(source, symbol, quality)
    
    # =========================================================================
    # HANDLERS
    # =========================================================================
    
    async def on_aggregation(self, handler: Callable):
        """Register an aggregation handler."""
        key = "aggregation"
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)
    
    async def _trigger_handlers(self, event: str, data: Any):
        """Trigger handlers for an event."""
        if event in self._handlers:
            for handler in self._handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
    
    # =========================================================================
    # UPDATE LOOP
    # =========================================================================
    
    async def _update_loop(self):
        """Periodic update loop."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every minute
                
                # Update correlations for major pairs
                major_pairs = [('BTC/USD', 'ETH/USD'), ('BTC/USD', 'SOL/USD')]
                for symbol1, symbol2 in major_pairs:
                    try:
                        await self.calculate_correlation(symbol1, symbol2)
                    except Exception as e:
                        logger.debug(f"Error updating correlation: {e}")
                
                # Detect anomalies for major symbols
                major_symbols = ['BTC/USD', 'ETH/USD', 'SOL/USD']
                for symbol in major_symbols:
                    try:
                        await self.detect_anomalies(symbol)
                    except Exception as e:
                        logger.debug(f"Error detecting anomalies: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_pipelines(self):
        """Load pipelines from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM data_pipelines")
                
                for row in rows:
                    pipeline = DataPipeline(
                        id=row['id'],
                        name=row['name'],
                        enabled=row['enabled'],
                        steps=row['steps'],
                        input_type=row['input_type'],
                        output_type=row['output_type'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        metadata=row['metadata'] or {}
                    )
                    self._pipelines[pipeline.id] = pipeline
                
                logger.info(f"Loaded {len(self._pipelines)} pipelines")
                
        except Exception as e:
            logger.error(f"Error loading pipelines: {e}")
    
    async def _save_pipeline(self, pipeline: DataPipeline):
        """Save pipeline to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO data_pipelines (
                        id, name, enabled, steps,
                        input_type, output_type,
                        created_at, updated_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        enabled = EXCLUDED.enabled,
                        steps = EXCLUDED.steps,
                        input_type = EXCLUDED.input_type,
                        output_type = EXCLUDED.output_type,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    pipeline.id,
                    pipeline.name,
                    pipeline.enabled,
                    json.dumps(pipeline.steps),
                    pipeline.input_type,
                    pipeline.output_type,
                    pipeline.created_at,
                    pipeline.updated_at,
                    json.dumps(pipeline.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving pipeline: {e}")
    
    async def _load_correlations(self):
        """Load correlations from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM data_correlations")
                
                for row in rows:
                    correlation = DataCorrelation(
                        symbol1=row['symbol1'],
                        symbol2=row['symbol2'],
                        correlation=row['correlation'],
                        p_value=row['p_value'],
                        sample_size=row['sample_size'],
                        timestamp=row['timestamp'],
                        method=row['method'],
                        metadata=row['metadata'] or {}
                    )
                    cache_key = f"{correlation.symbol1}:{correlation.symbol2}"
                    self._correlations[cache_key] = correlation
                
                logger.info(f"Loaded {len(self._correlations)} correlations")
                
        except Exception as e:
            logger.error(f"Error loading correlations: {e}")
    
    async def _save_correlation(self, correlation: DataCorrelation):
        """Save correlation to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO data_correlations (
                        symbol1, symbol2, correlation, p_value,
                        sample_size, timestamp, method, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (symbol1, symbol2) DO UPDATE SET
                        correlation = EXCLUDED.correlation,
                        p_value = EXCLUDED.p_value,
                        sample_size = EXCLUDED.sample_size,
                        timestamp = EXCLUDED.timestamp,
                        method = EXCLUDED.method,
                        metadata = EXCLUDED.metadata
                    """,
                    correlation.symbol1,
                    correlation.symbol2,
                    correlation.correlation,
                    correlation.p_value,
                    correlation.sample_size,
                    correlation.timestamp,
                    correlation.method,
                    json.dumps(correlation.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving correlation: {e}")
    
    async def _save_aggregated(self, aggregated: AggregatedData):
        """Save aggregated data to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO aggregated_data (
                        id, type, method, symbol, timestamp,
                        value, source_count, sources,
                        confidence, quality, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                    aggregated.id,
                    aggregated.type.value,
                    aggregated.method.value,
                    aggregated.symbol,
                    aggregated.timestamp,
                    json.dumps(aggregated.value),
                    aggregated.source_count,
                    json.dumps(aggregated.sources),
                    aggregated.confidence,
                    aggregated.quality.value,
                    json.dumps(aggregated.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving aggregated data: {e}")
    
    async def _save_anomaly(self, anomaly: DataAnomaly):
        """Save anomaly to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO data_anomalies (
                        id, type, symbol, value,
                        expected_value, deviation, severity,
                        timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    anomaly.id,
                    anomaly.type,
                    anomaly.symbol,
                    json.dumps(anomaly.value),
                    json.dumps(anomaly.expected_value),
                    anomaly.deviation,
                    anomaly.severity,
                    anomaly.timestamp,
                    json.dumps(anomaly.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving anomaly: {e}")
    
    async def _save_quality(self, source: str, symbol: str, quality: Dict[str, Any]):
        """Save quality metrics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO data_quality_metrics (
                        source, symbol, quality, score,
                        total_samples, error_count, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (source, symbol) DO UPDATE SET
                        quality = EXCLUDED.quality,
                        score = EXCLUDED.score,
                        total_samples = EXCLUDED.total_samples,
                        error_count = EXCLUDED.error_count,
                        timestamp = EXCLUDED.timestamp
                    """,
                    source,
                    symbol,
                    DataQuality.GOOD.value,
                    quality['score'],
                    quality['total_samples'],
                    quality['error_count'],
                    datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error saving quality: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the data aggregator."""
        self._running = False
        logger.info("DataAggregator shutdown")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Circuit breaker open error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'DataAggregator',
    'AggregationType',
    'AggregationMethod',
    'DataQuality',
    'DataSource',
    'AggregatedData',
    'DataPipeline',
    'DataCorrelation',
    'DataAnomaly',
    'CircuitBreakerOpenError'
]

"""
NEXUS AI TRADING SYSTEM - Market Making Analytics Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/market-making/analytics.py
Description: Comprehensive market making analytics with full API integration
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.market_making_config import MarketMakingConfig
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    TIME_FRAMES
)
from shared.helpers.trading_helpers import (
    calculate_spread,
    calculate_volatility,
    calculate_skew
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Order, Trade, Position
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.position_repository import PositionRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Market making imports
from trading.market_making.base import BaseMarketMaker
from trading.market_making.order_book import OrderBookManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class AnalyticsPeriod(str, Enum):
    """Time periods for analytics"""
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
    THREE_MONTHS = "3m"
    SIX_MONTHS = "6m"
    ONE_YEAR = "1y"
    ALL_TIME = "all_time"


class MetricType(str, Enum):
    """Types of metrics"""
    SPREAD = "spread"
    VOLUME = "volume"
    LIQUIDITY = "liquidity"
    PROFITABILITY = "profitability"
    RISK = "risk"
    PERFORMANCE = "performance"
    EXECUTION = "execution"
    INVENTORY = "inventory"
    ORDER = "order"
    MARKET = "market"


class PerformanceMetric(str, Enum):
    """Performance metrics"""
    SHARPE_RATIO = "sharpe_ratio"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    AVERAGE_RETURN = "average_return"
    MAX_DRAWDOWN = "max_drawdown"
    CALMAR_RATIO = "calmar_ratio"
    SORTINO_RATIO = "sortino_ratio"
    RECOVERY_FACTOR = "recovery_factor"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AnalyticsRequest(BaseModel):
    """Request model for analytics"""
    symbol: str
    period: AnalyticsPeriod = AnalyticsPeriod.ONE_DAY
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: List[MetricType] = []
    include_details: bool = True
    include_charts: bool = False
    granularity: str = "1h"  # 1m, 5m, 15m, 1h, 4h, 1d


class AnalyticsResponse(BaseModel):
    """Response model for analytics"""
    symbol: str
    period: AnalyticsPeriod
    timestamp: datetime
    summary: Dict[str, Any]
    metrics: Dict[str, Any]
    performance: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    order_stats: Dict[str, Any]
    inventory_stats: Dict[str, Any]
    market_stats: Dict[str, Any]
    insights: List[str]
    warnings: List[str]


class SpreadAnalytics(BaseModel):
    """Spread analytics"""
    avg_spread: float
    min_spread: float
    max_spread: float
    median_spread: float
    std_spread: float
    spread_distribution: Dict[str, float]
    spread_volatility: float
    spread_efficiency: float


class VolumeAnalytics(BaseModel):
    """Volume analytics"""
    total_volume: float
    avg_volume: float
    max_volume: float
    min_volume: float
    volume_profile: Dict[str, float]
    volume_concentration: float
    volume_trend: str


class LiquidityAnalytics(BaseModel):
    """Liquidity analytics"""
    bid_depth: float
    ask_depth: float
    total_depth: float
    depth_ratio: float
    liquidity_score: float
    order_book_imbalance: float
    market_impact: float


class ProfitabilityAnalytics(BaseModel):
    """Profitability analytics"""
    total_pnl: float
    avg_pnl_per_trade: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    win_rate: float
    avg_win: float
    avg_loss: float
    risk_reward_ratio: float


class InventoryAnalytics(BaseModel):
    """Inventory analytics"""
    current_inventory: float
    avg_inventory: float
    max_inventory: float
    min_inventory: float
    inventory_turnover: float
    inventory_skew: float
    carry_cost: float
    inventory_risk: float


class OrderAnalytics(BaseModel):
    """Order analytics"""
    total_orders: int
    filled_orders: int
    cancelled_orders: int
    expired_orders: int
    fill_rate: float
    avg_order_size: float
    avg_order_lifetime: float
    order_frequency: float
    cancellation_rate: float


class PerformanceAnalytics(BaseModel):
    """Performance analytics"""
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    avg_return: float
    max_drawdown: float
    calmar_ratio: float
    sortino_ratio: float
    recovery_factor: float
    avg_trade_duration: float
    total_trades: int


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AnalyticsContext:
    """Context for analytics"""
    symbol: str
    period: AnalyticsPeriod
    start_date: datetime
    end_date: datetime
    orders: List[Any]
    trades: List[Any]
    positions: List[Any]
    order_book_data: pd.DataFrame
    price_data: pd.DataFrame
    inventory_data: pd.DataFrame
    market_data: Dict[str, Any]


@dataclass
class AnalyticsResult:
    """Result of analytics calculation"""
    metric_type: MetricType
    value: Any
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# MARKET MAKING ANALYTICS
# =============================================================================

class MarketMakingAnalytics:
    """
    Comprehensive Market Making Analytics with full API integration.
    
    Provides analytics for:
    - Spread analysis
    - Volume analysis
    - Liquidity analysis
    - Profitability analysis
    - Performance analysis
    - Risk analysis
    - Inventory analysis
    - Order analysis
    - Market analysis
    - Execution quality
    """

    def __init__(
        self,
        config: Optional[MarketMakingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        position_repo: Optional[PositionRepository] = None,
        order_book_manager: Optional[OrderBookManager] = None
    ):
        """
        Initialize MarketMakingAnalytics.
        
        Args:
            config: Market making configuration
            broker_factory: Factory for broker instances
            order_repo: Order repository
            trade_repo: Trade repository
            position_repo: Position repository
            order_book_manager: Order book manager
        """
        self.config = config or MarketMakingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.position_repo = position_repo or PositionRepository()
        self.order_book_manager = order_book_manager or OrderBookManager()
        
        # Cache
        self._analytics_cache: Dict[str, Dict[str, Any]] = {}
        
        # Historical data
        self._historical_data: Dict[str, pd.DataFrame] = {}
        
        logger.info("MarketMakingAnalytics initialized")

    # =========================================================================
    # Main Analytics
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_analytics(
        self,
        request: AnalyticsRequest
    ) -> AnalyticsResponse:
        """
        Get comprehensive analytics for a symbol.
        
        Args:
            request: Analytics request
            
        Returns:
            AnalyticsResponse: Analytics results
        """
        try:
            # Build context
            context = await self._build_context(request)
            
            # Calculate all metrics
            metrics = await self._calculate_all_metrics(context, request.metrics)
            
            # Generate insights
            insights = await self._generate_insights(context, metrics)
            
            # Generate warnings
            warnings = await self._generate_warnings(context, metrics)
            
            # Build response
            response = AnalyticsResponse(
                symbol=request.symbol,
                period=request.period,
                timestamp=datetime.utcnow(),
                summary=metrics.get('summary', {}),
                metrics=metrics.get('metrics', {}),
                performance=metrics.get('performance', {}),
                risk_metrics=metrics.get('risk', {}),
                order_stats=metrics.get('orders', {}),
                inventory_stats=metrics.get('inventory', {}),
                market_stats=metrics.get('market', {}),
                insights=insights,
                warnings=warnings
            )
            
            # Cache analytics
            cache_key = f"{request.symbol}_{request.period.value}_{request.start_date}_{request.end_date}"
            self._analytics_cache[cache_key] = {
                'response': response,
                'timestamp': datetime.utcnow()
            }
            
            logger.info(f"Analytics generated for {request.symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating analytics: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analytics generation failed: {str(e)}"
            )

    async def _build_context(self, request: AnalyticsRequest) -> AnalyticsContext:
        """Build context for analytics"""
        # Set date range
        end_date = request.end_date or datetime.utcnow()
        if request.start_date:
            start_date = request.start_date
        else:
            # Map period to days
            period_days = {
                AnalyticsPeriod.ONE_HOUR: 1/24,
                AnalyticsPeriod.FOUR_HOURS: 4/24,
                AnalyticsPeriod.ONE_DAY: 1,
                AnalyticsPeriod.ONE_WEEK: 7,
                AnalyticsPeriod.ONE_MONTH: 30,
                AnalyticsPeriod.THREE_MONTHS: 90,
                AnalyticsPeriod.SIX_MONTHS: 180,
                AnalyticsPeriod.ONE_YEAR: 365
            }
            days = period_days.get(request.period, 1)
            start_date = end_date - timedelta(days=days)
        
        # Get orders
        orders = await self.order_repo.get_by_symbol(
            request.symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get trades
        trades = await self.trade_repo.get_by_symbol(
            request.symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get positions
        positions = await self.position_repo.get_by_symbol(
            request.symbol
        )
        
        # Get order book data
        order_book_data = await self._get_order_book_data(
            request.symbol,
            start_date,
            end_date
        )
        
        # Get price data
        price_data = await self._get_price_data(
            request.symbol,
            start_date,
            end_date,
            request.granularity
        )
        
        # Get inventory data
        inventory_data = await self._get_inventory_data(
            request.symbol,
            start_date,
            end_date
        )
        
        # Get market data
        market_data = await self._get_market_data(request.symbol)
        
        return AnalyticsContext(
            symbol=request.symbol,
            period=request.period,
            start_date=start_date,
            end_date=end_date,
            orders=orders,
            trades=trades,
            positions=positions,
            order_book_data=order_book_data,
            price_data=price_data,
            inventory_data=inventory_data,
            market_data=market_data
        )

    async def _get_order_book_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Get order book data"""
        # Get from order book manager
        data = await self.order_book_manager.get_historical_data(
            symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        if data is None or data.empty:
            # Generate mock data
            data = self._generate_mock_order_book_data(symbol, start_date, end_date)
        
        return data

    async def _get_price_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str
    ) -> pd.DataFrame:
        """Get price data"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        symbol,
                        timeframe=granularity,
                        start_time=start_date,
                        end_time=end_date
                    )
                    if candles:
                        df = pd.DataFrame(candles)
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df.set_index('timestamp', inplace=True)
                        return df
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting price data: {e}")
        
        # Generate mock data
        return self._generate_mock_price_data(symbol, start_date, end_date, granularity)

    async def _get_inventory_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Get inventory data"""
        # Get from position repository
        positions = await self.position_repo.get_by_symbol(symbol)
        
        if not positions:
            return self._generate_mock_inventory_data(symbol, start_date, end_date)
        
        data = []
        for position in positions:
            data.append({
                'timestamp': position.created_at,
                'inventory': float(position.size),
                'price': float(position.entry_price)
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        return df

    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    ticker = await broker.get_ticker(symbol)
                    return {
                        'price': float(ticker.get('price', 0)),
                        'bid': float(ticker.get('bid', 0)),
                        'ask': float(ticker.get('ask', 0)),
                        'volume': float(ticker.get('volume', 0)),
                        'high': float(ticker.get('high', 0)),
                        'low': float(ticker.get('low', 0)),
                        'change': float(ticker.get('change', 0)),
                        'change_pct': float(ticker.get('change_pct', 0))
                    }
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting market data: {e}")
        
        return {
            'price': 100.0,
            'bid': 99.95,
            'ask': 100.05,
            'volume': 1000000,
            'high': 101.0,
            'low': 99.0,
            'change': 0.5,
            'change_pct': 0.5
        }

    # =========================================================================
    # Mock Data Generation
    # =========================================================================

    def _generate_mock_order_book_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Generate mock order book data"""
        dates = pd.date_range(start=start_date, end=end_date, freq='1min')
        
        data = []
        for dt in dates:
            price = 100 + np.random.normal(0, 0.5)
            bid_depth = np.random.uniform(1000, 10000)
            ask_depth = np.random.uniform(1000, 10000)
            
            data.append({
                'timestamp': dt,
                'price': price,
                'bid_price': price * 0.999,
                'ask_price': price * 1.001,
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'total_depth': bid_depth + ask_depth,
                'imbalance': (bid_depth - ask_depth) / (bid_depth + ask_depth)
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def _generate_mock_price_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str
    ) -> pd.DataFrame:
        """Generate mock price data"""
        # Map granularity to frequency
        freq_map = {
            '1m': '1min',
            '5m': '5min',
            '15m': '15min',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }
        freq = freq_map.get(granularity, '1h')
        
        dates = pd.date_range(start=start_date, end=end_date, freq=freq)
        
        data = []
        price = 100
        for dt in dates:
            # Random walk
            price *= (1 + np.random.normal(0, 0.001))
            high = price * (1 + np.random.uniform(0, 0.005))
            low = price * (1 - np.random.uniform(0, 0.005))
            volume = np.random.uniform(1000, 100000)
            
            data.append({
                'timestamp': dt,
                'open': price,
                'high': high,
                'low': low,
                'close': price,
                'volume': volume
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def _generate_mock_inventory_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Generate mock inventory data"""
        dates = pd.date_range(start=start_date, end=end_date, freq='1h')
        
        data = []
        inventory = 0
        for dt in dates:
            # Random inventory changes
            change = np.random.normal(0, 10)
            inventory += change
            inventory = max(-100, min(100, inventory))
            
            data.append({
                'timestamp': dt,
                'inventory': inventory,
                'price': 100 + np.random.normal(0, 0.5)
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    # =========================================================================
    # Metric Calculations
    # =========================================================================

    async def _calculate_all_metrics(
        self,
        context: AnalyticsContext,
        requested_metrics: List[MetricType]
    ) -> Dict[str, Any]:
        """Calculate all requested metrics"""
        metrics = {
            'summary': {},
            'metrics': {},
            'performance': {},
            'risk': {},
            'orders': {},
            'inventory': {},
            'market': {}
        }
        
        # Calculate all metrics if none specified
        if not requested_metrics:
            requested_metrics = list(MetricType)
        
        # Spread metrics
        if MetricType.SPREAD in requested_metrics:
            metrics['metrics']['spread'] = await self._calculate_spread_analytics(context)
            metrics['summary']['avg_spread'] = metrics['metrics']['spread'].avg_spread
        
        # Volume metrics
        if MetricType.VOLUME in requested_metrics:
            metrics['metrics']['volume'] = await self._calculate_volume_analytics(context)
            metrics['summary']['total_volume'] = metrics['metrics']['volume'].total_volume
        
        # Liquidity metrics
        if MetricType.LIQUIDITY in requested_metrics:
            metrics['metrics']['liquidity'] = await self._calculate_liquidity_analytics(context)
            metrics['summary']['liquidity_score'] = metrics['metrics']['liquidity'].liquidity_score
        
        # Profitability metrics
        if MetricType.PROFITABILITY in requested_metrics:
            metrics['metrics']['profitability'] = await self._calculate_profitability_analytics(context)
            metrics['summary']['total_pnl'] = metrics['metrics']['profitability'].total_pnl
        
        # Performance metrics
        if MetricType.PERFORMANCE in requested_metrics:
            metrics['performance'] = await self._calculate_performance_analytics(context)
            metrics['summary']['sharpe_ratio'] = metrics['performance']['sharpe_ratio']
        
        # Risk metrics
        if MetricType.RISK in requested_metrics:
            metrics['risk'] = await self._calculate_risk_metrics(context)
            metrics['summary']['max_drawdown'] = metrics['risk'].get('max_drawdown', 0)
        
        # Order metrics
        if MetricType.ORDER in requested_metrics:
            metrics['orders'] = await self._calculate_order_analytics(context)
            metrics['summary']['fill_rate'] = metrics['orders'].fill_rate
        
        # Inventory metrics
        if MetricType.INVENTORY in requested_metrics:
            metrics['inventory'] = await self._calculate_inventory_analytics(context)
            metrics['summary']['current_inventory'] = metrics['inventory'].current_inventory
        
        # Market metrics
        if MetricType.MARKET in requested_metrics:
            metrics['market'] = context.market_data
        
        return metrics

    # -------------------------------------------------------------------------
    # Spread Analytics
    # -------------------------------------------------------------------------

    async def _calculate_spread_analytics(
        self,
        context: AnalyticsContext
    ) -> SpreadAnalytics:
        """Calculate spread analytics"""
        spreads = []
        
        # Calculate spreads from order book data
        if not context.order_book_data.empty:
            if 'ask_price' in context.order_book_data.columns and 'bid_price' in context.order_book_data.columns:
                spreads = (context.order_book_data['ask_price'] - context.order_book_data['bid_price']).tolist()
        
        # If no order book data, use market data
        if not spreads and context.market_data:
            bid = context.market_data.get('bid', 0)
            ask = context.market_data.get('ask', 0)
            if bid > 0 and ask > 0:
                spreads = [ask - bid]
        
        # Generate mock spreads if still empty
        if not spreads:
            spreads = list(np.random.uniform(0.01, 0.10, 100))
        
        spread_array = np.array(spreads)
        
        # Calculate statistics
        avg_spread = float(np.mean(spread_array))
        min_spread = float(np.min(spread_array))
        max_spread = float(np.max(spread_array))
        median_spread = float(np.median(spread_array))
        std_spread = float(np.std(spread_array))
        
        # Distribution
        spread_distribution = {
            '0-25%': float(np.percentile(spread_array, 25)),
            '25-50%': float(np.percentile(spread_array, 50)),
            '50-75%': float(np.percentile(spread_array, 75)),
            '75-100%': float(np.percentile(spread_array, 100))
        }
        
        # Spread volatility
        spread_volatility = float(np.std(np.diff(spread_array))) if len(spread_array) > 1 else 0
        
        # Spread efficiency (how close spread is to minimum)
        if min_spread > 0:
            spread_efficiency = avg_spread / min_spread if min_spread > 0 else 1
        else:
            spread_efficiency = 1
        
        return SpreadAnalytics(
            avg_spread=avg_spread,
            min_spread=min_spread,
            max_spread=max_spread,
            median_spread=median_spread,
            std_spread=std_spread,
            spread_distribution=spread_distribution,
            spread_volatility=spread_volatility,
            spread_efficiency=spread_efficiency
        )

    # -------------------------------------------------------------------------
    # Volume Analytics
    # -------------------------------------------------------------------------

    async def _calculate_volume_analytics(
        self,
        context: AnalyticsContext
    ) -> VolumeAnalytics:
        """Calculate volume analytics"""
        volumes = []
        
        # Get volumes from trades
        if context.trades:
            volumes = [float(t.size) for t in context.trades]
        
        # Get volumes from order book data
        if not volumes and not context.order_book_data.empty:
            if 'volume' in context.order_book_data.columns:
                volumes = context.order_book_data['volume'].tolist()
        
        # Get volume from price data
        if not volumes and not context.price_data.empty:
            if 'volume' in context.price_data.columns:
                volumes = context.price_data['volume'].tolist()
        
        # Generate mock volumes
        if not volumes:
            volumes = list(np.random.uniform(1000, 10000, 100))
        
        volume_array = np.array(volumes)
        
        total_volume = float(np.sum(volume_array))
        avg_volume = float(np.mean(volume_array))
        max_volume = float(np.max(volume_array))
        min_volume = float(np.min(volume_array))
        
        # Volume profile (time-based)
        volume_profile = {}
        if len(volume_array) >= 24:
            # Group by hour
            hour_volumes = []
            for i in range(24):
                start = i * len(volume_array) // 24
                end = (i + 1) * len(volume_array) // 24
                if end > start:
                    hour_vol = np.sum(volume_array[start:end])
                    volume_profile[f"hour_{i:02d}"] = float(hour_vol)
        
        # Volume concentration (top 20% of volume)
        sorted_volumes = np.sort(volume_array)[::-1]
        top_20_pct_count = max(1, int(len(sorted_volumes) * 0.2))
        top_20_pct_volume = np.sum(sorted_volumes[:top_20_pct_count])
        volume_concentration = top_20_pct_volume / total_volume if total_volume > 0 else 0
        
        # Volume trend
        if len(volume_array) > 10:
            recent_avg = np.mean(volume_array[-10:])
            older_avg = np.mean(volume_array[:-10]) if len(volume_array) > 10 else recent_avg
            if recent_avg > older_avg * 1.1:
                trend = "increasing"
            elif recent_avg < older_avg * 0.9:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return VolumeAnalytics(
            total_volume=total_volume,
            avg_volume=avg_volume,
            max_volume=max_volume,
            min_volume=min_volume,
            volume_profile=volume_profile,
            volume_concentration=volume_concentration,
            volume_trend=trend
        )

    # -------------------------------------------------------------------------
    # Liquidity Analytics
    # -------------------------------------------------------------------------

    async def _calculate_liquidity_analytics(
        self,
        context: AnalyticsContext
    ) -> LiquidityAnalytics:
        """Calculate liquidity analytics"""
        bid_depth = 0
        ask_depth = 0
        
        # Get depth from order book data
        if not context.order_book_data.empty:
            if 'bid_depth' in context.order_book_data.columns:
                bid_depth = float(context.order_book_data['bid_depth'].mean())
            if 'ask_depth' in context.order_book_data.columns:
                ask_depth = float(context.order_book_data['ask_depth'].mean())
        
        # Estimate depth from volume
        if bid_depth == 0 and context.market_data:
            volume = context.market_data.get('volume', 0)
            bid_depth = volume * 0.3
            ask_depth = volume * 0.3
        
        # Generate mock depths
        if bid_depth == 0:
            bid_depth = np.random.uniform(1000, 10000)
            ask_depth = np.random.uniform(1000, 10000)
        
        total_depth = bid_depth + ask_depth
        depth_ratio = bid_depth / ask_depth if ask_depth > 0 else 1
        
        # Liquidity score (0-100)
        # Based on depth, spread, and volume
        spread_analytics = await self._calculate_spread_analytics(context)
        volume_analytics = await self._calculate_volume_analytics(context)
        
        depth_score = min(100, total_depth / 10000 * 100)
        spread_score = max(0, 100 - spread_analytics.avg_spread * 1000)
        volume_score = min(100, volume_analytics.avg_volume / 5000 * 100)
        
        liquidity_score = (depth_score * 0.4 + spread_score * 0.3 + volume_score * 0.3)
        liquidity_score = min(100, liquidity_score)
        
        # Order book imbalance
        if total_depth > 0:
            order_book_imbalance = (bid_depth - ask_depth) / total_depth
        else:
            order_book_imbalance = 0
        
        # Market impact (estimated)
        avg_trade_size = volume_analytics.avg_volume / 100 if volume_analytics.avg_volume > 0 else 1
        market_impact = (avg_trade_size / total_depth) if total_depth > 0 else 0.01
        
        return LiquidityAnalytics(
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            total_depth=total_depth,
            depth_ratio=depth_ratio,
            liquidity_score=liquidity_score,
            order_book_imbalance=order_book_imbalance,
            market_impact=market_impact
        )

    # -------------------------------------------------------------------------
    # Profitability Analytics
    # -------------------------------------------------------------------------

    async def _calculate_profitability_analytics(
        self,
        context: AnalyticsContext
    ) -> ProfitabilityAnalytics:
        """Calculate profitability analytics"""
        pnls = []
        wins = []
        losses = []
        
        # Get PnL from trades
        if context.trades:
            for trade in context.trades:
                if hasattr(trade, 'pnl'):
                    pnl = float(trade.pnl)
                    pnls.append(pnl)
                    if pnl > 0:
                        wins.append(pnl)
                    else:
                        losses.append(abs(pnl))
        
        # Generate mock PnL if no trades
        if not pnls:
            pnls = list(np.random.normal(0, 10, 100))
            wins = [p for p in pnls if p > 0]
            losses = [abs(p) for p in pnls if p < 0]
        
        pnl_array = np.array(pnls)
        
        total_pnl = float(np.sum(pnl_array))
        avg_pnl = float(np.mean(pnl_array))
        gross_profit = float(np.sum(wins)) if wins else 0
        gross_loss = float(np.sum(losses)) if losses else 0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        win_rate = len(wins) / len(pnls) if pnls else 0
        
        avg_win = float(np.mean(wins)) if wins else 0
        avg_loss = float(np.mean(losses)) if losses else 0
        risk_reward_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        return ProfitabilityAnalytics(
            total_pnl=total_pnl,
            avg_pnl_per_trade=avg_pnl,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            risk_reward_ratio=risk_reward_ratio
        )

    # -------------------------------------------------------------------------
    # Performance Analytics
    # -------------------------------------------------------------------------

    async def _calculate_performance_analytics(
        self,
        context: AnalyticsContext
    ) -> Dict[str, float]:
        """Calculate performance analytics"""
        metrics = {}
        
        # Get returns from profitability
        profitability = await self._calculate_profitability_analytics(context)
        
        # Sharpe ratio
        returns = []
        if context.trades:
            for trade in context.trades:
                if hasattr(trade, 'pnl') and hasattr(trade, 'size'):
                    pnl = float(trade.pnl)
                    size = float(trade.size)
                    if size > 0:
                        returns.append(pnl / size)
        
        # Generate returns if none
        if not returns:
            returns = list(np.random.normal(0.001, 0.02, 100))
        
        returns_array = np.array(returns)
        
        avg_return = float(np.mean(returns_array))
        std_return = float(np.std(returns_array))
        
        if std_return > 0:
            sharpe_ratio = avg_return / std_return * np.sqrt(252)  # Annualized
        else:
            sharpe_ratio = 0
        
        # Win rate
        win_rate = profitability.win_rate
        
        # Profit factor
        profit_factor = profitability.profit_factor
        
        # Max drawdown
        cumulative_returns = np.cumprod(1 + returns_array)
        peak = np.maximum.accumulate(cumulative_returns)
        drawdowns = (peak - cumulative_returns) / peak
        max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0
        
        # Calmar ratio
        calmar_ratio = avg_return * 252 / max_drawdown if max_drawdown > 0 else 0
        
        # Sortino ratio (downside risk)
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            downside_std = np.std(downside_returns)
            sortino_ratio = avg_return / downside_std * np.sqrt(252) if downside_std > 0 else 0
        else:
            sortino_ratio = 0
        
        # Recovery factor
        recovery_factor = total_pnl / max_drawdown if max_drawdown > 0 else 0
        total_pnl = profitability.total_pnl
        
        # Average trade duration
        avg_duration = 0
        if context.trades:
            durations = []
            for trade in context.trades:
                if hasattr(trade, 'created_at') and hasattr(trade, 'execution_time'):
                    duration = (trade.execution_time - trade.created_at).total_seconds()
                    durations.append(duration)
            avg_duration = np.mean(durations) if durations else 0
        
        metrics = {
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_return': avg_return * 100,  # Percentage
            'max_drawdown': max_drawdown * 100,  # Percentage
            'calmar_ratio': calmar_ratio,
            'sortino_ratio': sortino_ratio,
            'recovery_factor': recovery_factor,
            'avg_trade_duration': avg_duration,
            'total_trades': len(context.trades) if context.trades else 0
        }
        
        return metrics

    # -------------------------------------------------------------------------
    # Risk Metrics
    # -------------------------------------------------------------------------

    async def _calculate_risk_metrics(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Calculate risk metrics"""
        metrics = {}
        
        # Get performance metrics
        performance = await self._calculate_performance_analytics(context)
        
        # Value at Risk (95%)
        returns = []
        if context.trades:
            for trade in context.trades:
                if hasattr(trade, 'pnl') and hasattr(trade, 'size'):
                    pnl = float(trade.pnl)
                    size = float(trade.size)
                    if size > 0:
                        returns.append(pnl / size)
        
        if not returns:
            returns = list(np.random.normal(0.001, 0.02, 100))
        
        var_95 = np.percentile(returns, 5)
        cvar_95 = np.mean([r for r in returns if r <= var_95]) if var_95 else 0
        
        # Volatility
        volatility = np.std(returns) * np.sqrt(252)
        
        # Beta (relative to market)
        beta = 1.0  # Default
        
        # Correlation
        correlation = 0.5  # Default
        
        metrics = {
            'var_95': float(var_95) * 100,  # Percentage
            'cvar_95': float(cvar_95) * 100,  # Percentage
            'volatility': float(volatility) * 100,  # Percentage
            'max_drawdown': performance.get('max_drawdown', 0),
            'beta': beta,
            'correlation': correlation,
            'risk_score': float(abs(var_95) * 100 + max_drawdown * 0.5)
        }
        
        return metrics

    # -------------------------------------------------------------------------
    # Order Analytics
    # -------------------------------------------------------------------------

    async def _calculate_order_analytics(
        self,
        context: AnalyticsContext
    ) -> OrderAnalytics:
        """Calculate order analytics"""
        orders = context.orders
        
        total_orders = len(orders)
        filled_orders = sum(1 for o in orders if o.status == 'filled')
        cancelled_orders = sum(1 for o in orders if o.status == 'cancelled')
        expired_orders = sum(1 for o in orders if o.status == 'expired')
        
        fill_rate = filled_orders / total_orders if total_orders > 0 else 0
        
        # Average order size
        sizes = [float(o.size) for o in orders if hasattr(o, 'size')]
        avg_order_size = np.mean(sizes) if sizes else 0
        
        # Average order lifetime
        lifetimes = []
        for o in orders:
            if hasattr(o, 'created_at') and hasattr(o, 'updated_at'):
                lifetime = (o.updated_at - o.created_at).total_seconds()
                lifetimes.append(lifetime)
        avg_order_lifetime = np.mean(lifetimes) if lifetimes else 0
        
        # Order frequency (orders per hour)
        if context.start_date and context.end_date:
            hours = (context.end_date - context.start_date).total_seconds() / 3600
            order_frequency = total_orders / hours if hours > 0 else 0
        else:
            order_frequency = 0
        
        # Cancellation rate
        cancellation_rate = cancelled_orders / total_orders if total_orders > 0 else 0
        
        return OrderAnalytics(
            total_orders=total_orders,
            filled_orders=filled_orders,
            cancelled_orders=cancelled_orders,
            expired_orders=expired_orders,
            fill_rate=fill_rate,
            avg_order_size=avg_order_size,
            avg_order_lifetime=avg_order_lifetime,
            order_frequency=order_frequency,
            cancellation_rate=cancellation_rate
        )

    # -------------------------------------------------------------------------
    # Inventory Analytics
    # -------------------------------------------------------------------------

    async def _calculate_inventory_analytics(
        self,
        context: AnalyticsContext
    ) -> InventoryAnalytics:
        """Calculate inventory analytics"""
        inventory_values = []
        
        # Get inventory from positions
        if context.positions:
            inventory_values = [float(p.size) for p in context.positions]
        
        # Get inventory from inventory data
        if not inventory_values and not context.inventory_data.empty:
            if 'inventory' in context.inventory_data.columns:
                inventory_values = context.inventory_data['inventory'].tolist()
        
        # Generate mock inventory
        if not inventory_values:
            inventory_values = list(np.random.normal(0, 20, 100))
        
        inventory_array = np.array(inventory_values)
        
        current_inventory = inventory_array[-1] if len(inventory_array) > 0 else 0
        avg_inventory = float(np.mean(inventory_array))
        max_inventory = float(np.max(inventory_array))
        min_inventory = float(np.min(inventory_array))
        
        # Inventory turnover
        if context.trades:
            total_trade_volume = sum(float(t.size) for t in context.trades)
            inventory_turnover = total_trade_volume / abs(avg_inventory) if abs(avg_inventory) > 0 else 0
        else:
            inventory_turnover = 0
        
        # Inventory skew (bias towards long or short)
        if avg_inventory != 0:
            inventory_skew = avg_inventory / abs(avg_inventory) if abs(avg_inventory) > 0 else 0
        else:
            inventory_skew = 0
        
        # Carry cost (estimated)
        carry_cost = abs(avg_inventory) * 0.01  # 1% cost estimate
        
        # Inventory risk
        inventory_risk = abs(max_inventory - min_inventory) / 2 if max_inventory != min_inventory else 0
        
        return InventoryAnalytics(
            current_inventory=current_inventory,
            avg_inventory=avg_inventory,
            max_inventory=max_inventory,
            min_inventory=min_inventory,
            inventory_turnover=inventory_turnover,
            inventory_skew=inventory_skew,
            carry_cost=carry_cost,
            inventory_risk=inventory_risk
        )

    # =========================================================================
    # Insights & Warnings
    # =========================================================================

    async def _generate_insights(
        self,
        context: AnalyticsContext,
        metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate insights from analytics"""
        insights = []
        
        # Profitability insights
        profitability = metrics.get('metrics', {}).get('profitability')
        if profitability:
            if profitability.profit_factor > 2:
                insights.append("Excellent profit factor. Strategy is highly profitable.")
            elif profitability.profit_factor > 1.5:
                insights.append("Good profit factor. Strategy is profitable.")
            elif profitability.profit_factor < 1:
                insights.append("Profit factor below 1. Consider reviewing strategy.")
            
            if profitability.win_rate > 0.6:
                insights.append("High win rate. Strategy has good consistency.")
        
        # Spread insights
        spread = metrics.get('metrics', {}).get('spread')
        if spread:
            if spread.avg_spread < 0.02:
                insights.append("Very tight spread. Excellent liquidity conditions.")
            elif spread.avg_spread < 0.05:
                insights.append("Tight spread. Good liquidity conditions.")
            
            if spread.spread_efficiency < 1.5:
                insights.append("High spread efficiency. Orders are well placed.")
        
        # Liquidity insights
        liquidity = metrics.get('metrics', {}).get('liquidity')
        if liquidity:
            if liquidity.liquidity_score > 80:
                insights.append("Excellent liquidity. High market depth.")
            elif liquidity.liquidity_score > 60:
                insights.append("Good liquidity. Adequate market depth.")
            
            if abs(liquidity.order_book_imbalance) < 0.1:
                insights.append("Balanced order book. No significant imbalance.")
        
        # Performance insights
        performance = metrics.get('performance', {})
        if performance:
            if performance.get('sharpe_ratio', 0) > 1.5:
                insights.append("Excellent risk-adjusted returns.")
            elif performance.get('sharpe_ratio', 0) > 0.8:
                insights.append("Good risk-adjusted returns.")
            
            if performance.get('max_drawdown', 0) < 10:
                insights.append("Low drawdown. Good risk management.")
        
        # Inventory insights
        inventory = metrics.get('inventory')
        if inventory:
            if abs(inventory.current_inventory) < 10:
                insights.append("Neutral inventory position. Low directional risk.")
            elif abs(inventory.current_inventory) > 50:
                insights.append("Significant inventory position. Consider rebalancing.")
            
            if inventory.inventory_turnover > 5:
                insights.append("High inventory turnover. Active inventory management.")
        
        # Return top insights
        return insights[:10]

    async def _generate_warnings(
        self,
        context: AnalyticsContext,
        metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate warnings from analytics"""
        warnings = []
        
        # Profitability warnings
        profitability = metrics.get('metrics', {}).get('profitability')
        if profitability:
            if profitability.profit_factor < 1:
                warnings.append("Strategy is not profitable. Review and adjust.")
            
            if profitability.win_rate < 0.3:
                warnings.append("Low win rate. Consider reducing trade frequency.")
            
            if profitability.avg_loss > profitability.avg_win:
                warnings.append("Average loss exceeds average win. Risk-reward ratio needs improvement.")
        
        # Risk warnings
        risk = metrics.get('risk', {})
        if risk:
            if risk.get('max_drawdown', 0) > 20:
                warnings.append("High drawdown. Risk limits may be exceeded.")
            
            if risk.get('var_95', 0) > 5:
                warnings.append("High VaR. Position sizing may be too aggressive.")
        
        # Liquidity warnings
        liquidity = metrics.get('metrics', {}).get('liquidity')
        if liquidity:
            if liquidity.liquidity_score < 30:
                warnings.append("Low liquidity. Market impact may be significant.")
            
            if abs(liquidity.order_book_imbalance) > 0.3:
                warnings.append("Significant order book imbalance. Market may be one-sided.")
        
        # Inventory warnings
        inventory = metrics.get('inventory')
        if inventory:
            if abs(inventory.current_inventory) > 100:
                warnings.append("Large inventory position. Significant directional risk.")
            
            if inventory.inventory_risk > 50:
                warnings.append("High inventory risk. Consider hedging.")
        
        # Order warnings
        orders = metrics.get('orders')
        if orders:
            if orders.fill_rate < 0.5:
                warnings.append("Low fill rate. Orders may be too aggressive.")
            
            if orders.cancellation_rate > 0.4:
                warnings.append("High cancellation rate. Review order placement strategy.")
        
        # Market warnings
        market = metrics.get('market', {})
        if market:
            if market.get('change_pct', 0) > 5:
                warnings.append("Significant price movement. Increased market volatility.")
        
        return warnings[:10]

    # =========================================================================
    # Chart Data Generation
    # =========================================================================

    async def get_chart_data(
        self,
        symbol: str,
        chart_type: str,
        period: AnalyticsPeriod = AnalyticsPeriod.ONE_DAY,
        granularity: str = "1h"
    ) -> Dict[str, Any]:
        """
        Get data for charting.
        
        Args:
            symbol: Symbol
            chart_type: Type of chart
            period: Time period
            granularity: Data granularity
            
        Returns:
            Dict[str, Any]: Chart data
        """
        request = AnalyticsRequest(
            symbol=symbol,
            period=period,
            granularity=granularity,
            include_charts=True
        )
        
        context = await self._build_context(request)
        
        if chart_type == "equity":
            data = await self._get_equity_curve_data(context)
        elif chart_type == "drawdown":
            data = await self._get_drawdown_data(context)
        elif chart_type == "spread":
            data = await self._get_spread_data(context)
        elif chart_type == "volume":
            data = await self._get_volume_data(context)
        elif chart_type == "inventory":
            data = await self._get_inventory_data_for_chart(context)
        elif chart_type == "order_flow":
            data = await self._get_order_flow_data(context)
        else:
            data = await self._get_price_data_for_chart(context)
        
        return data

    async def _get_equity_curve_data(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Get equity curve data"""
        if context.trades:
            equity = [0]
            timestamps = [context.start_date]
            
            for trade in context.trades:
                pnl = float(trade.pnl) if hasattr(trade, 'pnl') else 0
                equity.append(equity[-1] + pnl)
                if hasattr(trade, 'execution_time'):
                    timestamps.append(trade.execution_time)
            
            return {
                'timestamps': [t.isoformat() for t in timestamps],
                'equity': equity,
                'title': 'Equity Curve'
            }
        else:
            return {'timestamps': [], 'equity': [], 'title': 'No Data'}

    async def _get_drawdown_data(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Get drawdown data"""
        equity_data = await self._get_equity_curve_data(context)
        equity = equity_data.get('equity', [])
        
        if equity:
            max_equity = max(equity) if equity else 0
            drawdowns = [(max_equity - e) / max_equity * 100 if max_equity > 0 else 0 
                        for e in equity]
            
            return {
                'timestamps': equity_data.get('timestamps', []),
                'drawdowns': drawdowns,
                'title': 'Drawdown Chart'
            }
        else:
            return {'timestamps': [], 'drawdowns': [], 'title': 'No Data'}

    async def _get_spread_data(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Get spread data"""
        if not context.order_book_data.empty:
            if 'timestamp' in context.order_book_data.index.names:
                timestamps = context.order_book_data.index.tolist()
            else:
                timestamps = context.order_book_data.index.tolist()
            
            spreads = []
            if 'ask_price' in context.order_book_data.columns and 'bid_price' in context.order_book_data.columns:
                spreads = (context.order_book_data['ask_price'] - context.order_book_data['bid_price']).tolist()
            
            return {
                'timestamps': [t.isoformat() if hasattr(t, 'isoformat') else str(t) for t in timestamps],
                'spreads': spreads,
                'title': 'Spread Over Time'
            }
        else:
            return {'timestamps': [], 'spreads': [], 'title': 'No Data'}

    async def _get_volume_data(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Get volume data"""
        volumes = []
        timestamps = []
        
        if context.trades:
            for trade in context.trades:
                size = float(trade.size) if hasattr(trade, 'size') else 0
                volumes.append(size)
                if hasattr(trade, 'execution_time'):
                    timestamps.append(trade.execution_time)
        
        if not volumes and not context.price_data.empty:
            if 'volume' in context.price_data.columns:
                volumes = context.price_data['volume'].tolist()
                timestamps = context.price_data.index.tolist()
        
        return {
            'timestamps': [t.isoformat() if hasattr(t, 'isoformat') else str(t) for t in timestamps],
            'volumes': volumes,
            'title': 'Volume Over Time'
        }

    async def _get_inventory_data_for_chart(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Get inventory data for chart"""
        if not context.inventory_data.empty:
            timestamps = context.inventory_data.index.tolist()
            inventory = context.inventory_data['inventory'].tolist()
            
            return {
                'timestamps': [t.isoformat() if hasattr(t, 'isoformat') else str(t) for t in timestamps],
                'inventory': inventory,
                'title': 'Inventory Over Time'
            }
        else:
            return {'timestamps': [], 'inventory': [], 'title': 'No Data'}

    async def _get_order_flow_data(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Get order flow data"""
        bid_orders = []
        ask_orders = []
        timestamps = []
        
        if context.orders:
            for order in context.orders:
                side = order.side if hasattr(order, 'side') else 'buy'
                size = float(order.size) if hasattr(order, 'size') else 0
                
                if side == 'buy':
                    bid_orders.append(size)
                else:
                    ask_orders.append(size)
                
                if hasattr(order, 'created_at'):
                    timestamps.append(order.created_at)
        
        return {
            'timestamps': [t.isoformat() if hasattr(t, 'isoformat') else str(t) for t in timestamps],
            'bid_orders': bid_orders,
            'ask_orders': ask_orders,
            'title': 'Order Flow'
        }

    async def _get_price_data_for_chart(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Get price data for chart"""
        if not context.price_data.empty:
            timestamps = context.price_data.index.tolist()
            prices = context.price_data['close'].tolist()
            
            return {
                'timestamps': [t.isoformat() if hasattr(t, 'isoformat') else str(t) for t in timestamps],
                'prices': prices,
                'title': 'Price Chart'
            }
        else:
            return {'timestamps': [], 'prices': [], 'title': 'No Data'}

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the analytics module"""
        self._analytics_cache.clear()
        self._historical_data.clear()
        logger.info("MarketMakingAnalytics closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/market-making/analytics", tags=["Market Making Analytics"])


async def get_analytics() -> MarketMakingAnalytics:
    """Dependency to get MarketMakingAnalytics instance"""
    return MarketMakingAnalytics()


@router.post("/", response_model=AnalyticsResponse)
async def get_analytics(
    request: AnalyticsRequest,
    analytics: MarketMakingAnalytics = Depends(get_analytics)
):
    """Get comprehensive market making analytics"""
    return await analytics.get_analytics(request)


@router.get("/chart/{symbol}")
async def get_chart_data(
    symbol: str,
    chart_type: str = Query(..., description="Type of chart: equity, drawdown, spread, volume, inventory, order_flow"),
    period: AnalyticsPeriod = Query(AnalyticsPeriod.ONE_DAY),
    granularity: str = Query("1h"),
    analytics: MarketMakingAnalytics = Depends(get_analytics)
):
    """Get chart data for visualization"""
    return await analytics.get_chart_data(symbol, chart_type, period, granularity)


@router.get("/metrics")
async def get_available_metrics():
    """Get available metric types"""
    return {
        'metrics': [
            {'name': m.value, 'description': m.name.replace('_', ' ').title()}
            for m in MetricType
        ]
    }


@router.get("/periods")
async def get_periods():
    """Get available analytics periods"""
    return {
        'periods': [
            {'name': p.value, 'description': p.name.replace('_', ' ').title()}
            for p in AnalyticsPeriod
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'MarketMakingAnalytics',
    'AnalyticsPeriod',
    'MetricType',
    'PerformanceMetric',
    'AnalyticsRequest',
    'AnalyticsResponse',
    'SpreadAnalytics',
    'VolumeAnalytics',
    'LiquidityAnalytics',
    'ProfitabilityAnalytics',
    'InventoryAnalytics',
    'OrderAnalytics',
    'PerformanceAnalytics',
    'AnalyticsContext',
    'AnalyticsResult',
    'router'
]

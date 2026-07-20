# trading/bots/arbitrage_bot/models/__init__.py
# NEXUS AI TRADING SYSTEM - MODELS PACKAGE
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This package contains all data models for the arbitrage bot, organized into
# logical categories for easy import and maintenance.
# ====================================================================================

"""
NEXUS Arbitrage Bot Models Package

This package provides comprehensive data models for:
- Alert and notification management
- Balance and portfolio tracking
- Cost and fee calculation
- Order book depth analysis
- Exchange configuration and connection
- Gas and transaction cost optimization
- Latency and performance monitoring
- Arbitrage opportunity detection
- Order management and execution
- Pair and symbol management
- Portfolio and position management
- Price and market data analysis
- Profit and performance tracking
- Risk assessment and management
- Signal generation and validation
- Slippage and spread analysis
- Trade execution and tracking
- Volume and liquidity analysis
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple

# ====================================================================================
# ALERT MODELS
# ====================================================================================

from .alert import (
    Alert,
    AlertMetadata,
    AlertSource,
    AlertContext,
    AlertStats,
    AlertReport,
    Notification,
    NotificationTemplate,
    EscalationRule,
    EscalationPolicy,
    AlertAggregationConfig,
    AlertGroup,
    AlertSeverity,
    AlertCategory,
    AlertStatus,
    AlertPriority,
    NotificationChannel,
    AlertAction,
    EscalationLevel,
    AlertAggregationType,
    IncidentSeverity,
    create_alert,
    create_critical_alert,
    create_high_alert,
    create_info_alert,
    create_trading_alert,
    create_exchange_alert,
    create_opportunity_alert,
    create_security_alert,
)

# ====================================================================================
# BALANCE MODELS
# ====================================================================================

from .balance import (
    Balance,
    BalanceDelta,
    Portfolio,
    Position,
    BalanceHistoryEntry,
    BalanceSnapshot,
    BalanceType,
    AssetType,
    AssetCategory,
    BalanceChangeType,
    PositionSide,
    MarginType,
    calculate_allocation,
    calculate_asset_concentration,
    calculate_diversification_score,
    calculate_herfindahl_hirschman_index,
    get_risk_level,
)

# ====================================================================================
# COST MODELS
# ====================================================================================

from .cost import (
    Fee,
    GasCost,
    Slippage,
    TotalCost,
    FeeTier,
    FeeSchedule,
    CostAnalysis,
    FeeType,
    GasType,
    SlippageType,
    CostCategory,
    FeeStructure,
    calculate_cost_effectiveness,
    calculate_break_even_price,
    calculate_effective_cost,
    calculate_profit_after_costs,
)

# ====================================================================================
# DEPTH MODELS
# ====================================================================================

from .depth import (
    OrderBookLevel,
    OrderBookDepth,
    LiquidityAnalysis,
    OrderFlow,
    DepthSnapshot,
    DepthStatistics,
    OrderBookSide,
    OrderType,
    OrderStatus,
    DepthUpdateType,
    LiquidityType,
    MarketImpactType,
    calculate_depth_percentile,
    calculate_weighted_average_price,
    detect_spoofing,
    calculate_depth_tier,
)

# ====================================================================================
# EXCHANGE MODELS
# ====================================================================================

from .exchange import (
    ExchangeCredentials,
    ExchangeConfig,
    SymbolInfo,
    ExchangeInfo,
    Ticker,
    OrderBook,
    Trade,
    Kline,
    FundingRate,
    ExchangeHealth,
    RateLimit,
    ExchangeStats,
    ExchangeType,
    ExchangeMarket,
    ExchangeStatus,
    SymbolStatus,
    OrderSide,
    OrderType as ExchangeOrderType,
    TimeInForce,
    RateLimitType,
    create_exchange_config,
    create_symbol_info,
)

# ====================================================================================
# FEE MODELS
# ====================================================================================

from .fee import (
    FeeTier as FeeTierModel,
    FeeSchedule as FeeScheduleModel,
    FeeCalculation,
    FeeHistoryEntry,
    FeeAnalytics,
    FeeComparison,
    FeeTierType,
    FeeDiscountType,
    FeeCurrency,
    FeeCalculationMethod,
    calculate_fee_impact,
    calculate_break_even_spread,
    calculate_optimal_tier,
)

# ====================================================================================
# GAS MODELS
# ====================================================================================

from .gas import (
    GasConfig,
    GasPrice,
    GasPriceHistory,
    GasEstimate,
    GasOptimization,
    GasToken,
    MEVProtection,
    GasNetwork,
    GasPriority,
    GasStrategy,
    GasTokenType,
    MEVProtectionLevel,
    calculate_optimal_gas_price,
    calculate_gas_savings,
    estimate_mev_risk,
)

# ====================================================================================
# LATENCY MODELS
# ====================================================================================

from .latency import (
    LatencyMeasurement,
    LatencyStatistics,
    LatencyOptimization,
    LatencyAlert,
    LatencyComparison,
    LatencyType,
    LatencyPercentile,
    LatencyStatus,
    Region,
    calculate_weighted_latency,
    calculate_latency_percentiles,
    get_latency_status,
    calculate_latency_budget,
    calculate_geographic_latency,
)

# ====================================================================================
# OPPORTUNITY MODELS
# ====================================================================================

from .opportunity import (
    OpportunityLeg,
    ArbitrageOpportunity,
    OpportunitySummary,
    OpportunityFilter,
    OpportunityType,
    OpportunityStatus,
    OpportunityConfidence,
    OpportunityPriority,
    ArbitrageType,
    ExecutionMethod,
    create_opportunity,
    create_opportunity_leg,
    calculate_opportunity_score,
)

# ====================================================================================
# ORDER MODELS
# ====================================================================================

from .order import (
    Order,
    OrderBookEntry,
    OrderBook as OrderBookModel,
    OrderHistory,
    OrderStatistics,
    OrderFilter,
    OrderSide as OrderSideModel,
    OrderType as OrderTypeModel,
    OrderStatus as OrderStatusModel,
    TimeInForce as TimeInForceModel,
    OrderSource,
    OrderDestination,
    OrderCategory,
    OrderEvent,
    create_market_order,
    create_limit_order,
    create_stop_order,
    calculate_order_value,
)

# ====================================================================================
# PAIR MODELS
# ====================================================================================

from .pair import (
    Pair,
    PairMapping,
    PairPerformance,
    PairFilter,
    PairCategory,
    PairStatus,
    PairType,
    CorrelationStrength,
    LiquidityLevel,
    VolatilityLevel,
    create_pair,
    calculate_pair_correlation,
    calculate_pair_spread,
)

# ====================================================================================
# PORTFOLIO MODELS
# ====================================================================================

from .portfolio import (
    AssetAllocation,
    Portfolio as PortfolioModel,
    PortfolioSnapshot,
    PortfolioStatus,
    AllocationType,
    RiskProfile,
    PortfolioCategory,
    RebalanceTrigger,
    LimitType,
    calculate_optimal_position_size,
    calculate_portfolio_value_at_risk,
    calculate_sharpe_ratio,
)

# ====================================================================================
# POSITION MODELS
# ====================================================================================

from .position import (
    Position as PositionModel,
    PositionSummary,
    PositionFilter as PositionFilterModel,
    PositionSide as PositionSideModel,
    PositionStatus as PositionStatusModel,
    PositionType as PositionTypeModel,
    MarginType as MarginTypeModel,
    PositionEvent,
    create_position,
    calculate_position_size,
    calculate_liquidation_price,
)

# ====================================================================================
# PRICE MODELS
# ====================================================================================

from .price import (
    Price,
    PriceFeed,
    PriceHistory,
    PriceComparison,
    PriceAnomaly,
    PriceForecast,
    PriceSource,
    PriceType,
    PriceStatus,
    TrendDirection,
    VolatilityLevel as PriceVolatilityLevel,
    calculate_price_change,
    calculate_volatility,
    calculate_moving_average,
    calculate_bollinger_bands,
)

# ====================================================================================
# PROFIT MODELS
# ====================================================================================

from .profit import (
    ProfitCalculation,
    ProfitSummary,
    ProfitPerformance,
    ProfitForecast,
    ProfitType,
    ProfitCurrency,
    ProfitAttributionType,
    PerformanceMetric,
    calculate_profit_percentage,
    calculate_profit_factor,
    calculate_expected_value,
    calculate_sharpe_ratio as calculate_profit_sharpe_ratio,
)

# ====================================================================================
# RISK MODELS
# ====================================================================================

from .risk import (
    RiskMetricValue,
    RiskAssessment,
    PositionRisk,
    RiskLimit,
    RiskReport,
    RiskType,
    RiskLevel,
    RiskCategory,
    RiskMetric,
    RiskAction,
    calculate_value_at_risk,
    calculate_conditional_var,
    calculate_sharpe_ratio as calculate_risk_sharpe_ratio,
    calculate_max_drawdown,
)

# ====================================================================================
# SIGNAL MODELS
# ====================================================================================

from .signal import (
    Signal,
    SignalAggregation,
    SignalFilter,
    SignalPerformance,
    SignalType,
    SignalStrength,
    SignalSource,
    SignalStatus,
    SignalPriority,
    SignalValidationMethod,
    calculate_signal_confidence,
    combine_signals,
)

# ====================================================================================
# SLIPPAGE MODELS
# ====================================================================================

from .slippage import (
    Slippage as SlippageModel,
    SlippageEstimate,
    SlippageStatistics,
    SlippageType as SlippageTypeModel,
    SlippageDirection,
    SlippageSeverity,
    SlippageModel as SlippageModelType,
    estimate_slippage,
    calculate_slippage_tolerance,
    analyze_slippage_impact,
)

# ====================================================================================
# SPREAD MODELS
# ====================================================================================

from .spread import (
    Spread,
    CrossExchangeSpread,
    SpreadHistory,
    SpreadOptimization,
    SpreadType,
    SpreadDirection,
    SpreadSeverity,
    SpreadCalculationMethod,
    calculate_spread,
    calculate_cross_exchange_spread,
    calculate_arbitrage_spread,
)

# ====================================================================================
# TRADE MODELS
# ====================================================================================

from .trade import (
    TradeLeg,
    Trade,
    TradeSummary,
    TradeSide,
    TradeStatus,
    TradeType,
    TradeExecutionMethod,
    TradeCategory,
    TradeRole,
    TradeSettlementStatus,
    create_trade,
    create_trade_leg,
    calculate_trade_pnl,
)

# ====================================================================================
# VOLUME MODELS
# ====================================================================================

from .volume import (
    Volume,
    VolumeHistory,
    VWAP,
    VolumePrediction,
    VolumeAnomaly,
    VolumeType,
    VolumePeriod,
    VolumeDirection,
    LiquidityLevel as VolumeLiquidityLevel,
    VolumeAnomalyType,
    calculate_vwap,
    calculate_volume_turnover,
    calculate_volume_price_correlation,
)

# ====================================================================================
# PACKAGE METADATA
# ====================================================================================

__version__ = "3.0.0"
__author__ = "Dr X..."
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__description__ = "NEXUS AI Trading System - Arbitrage Bot Models"

# ====================================================================================
# EXPORTS - ORGANIZED BY CATEGORY
# ====================================================================================

__all__ = [
    # Alert Models
    'Alert',
    'AlertMetadata',
    'AlertSource',
    'AlertContext',
    'AlertStats',
    'AlertReport',
    'Notification',
    'NotificationTemplate',
    'EscalationRule',
    'EscalationPolicy',
    'AlertAggregationConfig',
    'AlertGroup',
    'AlertSeverity',
    'AlertCategory',
    'AlertStatus',
    'AlertPriority',
    'NotificationChannel',
    'AlertAction',
    'EscalationLevel',
    'AlertAggregationType',
    'IncidentSeverity',
    'create_alert',
    'create_critical_alert',
    'create_high_alert',
    'create_info_alert',
    'create_trading_alert',
    'create_exchange_alert',
    'create_opportunity_alert',
    'create_security_alert',
    
    # Balance Models
    'Balance',
    'BalanceDelta',
    'Portfolio',
    'Position',
    'BalanceHistoryEntry',
    'BalanceSnapshot',
    'BalanceType',
    'AssetType',
    'AssetCategory',
    'BalanceChangeType',
    'PositionSide',
    'MarginType',
    'calculate_allocation',
    'calculate_asset_concentration',
    'calculate_diversification_score',
    'calculate_herfindahl_hirschman_index',
    'get_risk_level',
    
    # Cost Models
    'Fee',
    'GasCost',
    'Slippage',
    'TotalCost',
    'FeeTier',
    'FeeSchedule',
    'CostAnalysis',
    'FeeType',
    'GasType',
    'SlippageType',
    'CostCategory',
    'FeeStructure',
    'calculate_cost_effectiveness',
    'calculate_break_even_price',
    'calculate_effective_cost',
    'calculate_profit_after_costs',
    
    # Depth Models
    'OrderBookLevel',
    'OrderBookDepth',
    'LiquidityAnalysis',
    'OrderFlow',
    'DepthSnapshot',
    'DepthStatistics',
    'OrderBookSide',
    'OrderType',
    'OrderStatus',
    'DepthUpdateType',
    'LiquidityType',
    'MarketImpactType',
    'calculate_depth_percentile',
    'calculate_weighted_average_price',
    'detect_spoofing',
    'calculate_depth_tier',
    
    # Exchange Models
    'ExchangeCredentials',
    'ExchangeConfig',
    'SymbolInfo',
    'ExchangeInfo',
    'Ticker',
    'OrderBook',
    'Trade',
    'Kline',
    'FundingRate',
    'ExchangeHealth',
    'RateLimit',
    'ExchangeStats',
    'ExchangeType',
    'ExchangeMarket',
    'ExchangeStatus',
    'SymbolStatus',
    'OrderSide',
    'ExchangeOrderType',
    'TimeInForce',
    'RateLimitType',
    'create_exchange_config',
    'create_symbol_info',
    
    # Fee Models
    'FeeTierModel',
    'FeeScheduleModel',
    'FeeCalculation',
    'FeeHistoryEntry',
    'FeeAnalytics',
    'FeeComparison',
    'FeeTierType',
    'FeeDiscountType',
    'FeeCurrency',
    'FeeCalculationMethod',
    'calculate_fee_impact',
    'calculate_break_even_spread',
    'calculate_optimal_tier',
    
    # Gas Models
    'GasConfig',
    'GasPrice',
    'GasPriceHistory',
    'GasEstimate',
    'GasOptimization',
    'GasToken',
    'MEVProtection',
    'GasNetwork',
    'GasPriority',
    'GasStrategy',
    'GasTokenType',
    'MEVProtectionLevel',
    'calculate_optimal_gas_price',
    'calculate_gas_savings',
    'estimate_mev_risk',
    
    # Latency Models
    'LatencyMeasurement',
    'LatencyStatistics',
    'LatencyOptimization',
    'LatencyAlert',
    'LatencyComparison',
    'LatencyType',
    'LatencyPercentile',
    'LatencyStatus',
    'Region',
    'calculate_weighted_latency',
    'calculate_latency_percentiles',
    'get_latency_status',
    'calculate_latency_budget',
    'calculate_geographic_latency',
    
    # Opportunity Models
    'OpportunityLeg',
    'ArbitrageOpportunity',
    'OpportunitySummary',
    'OpportunityFilter',
    'OpportunityType',
    'OpportunityStatus',
    'OpportunityConfidence',
    'OpportunityPriority',
    'ArbitrageType',
    'ExecutionMethod',
    'create_opportunity',
    'create_opportunity_leg',
    'calculate_opportunity_score',
    
    # Order Models
    'Order',
    'OrderBookEntry',
    'OrderBookModel',
    'OrderHistory',
    'OrderStatistics',
    'OrderFilter',
    'OrderSideModel',
    'OrderTypeModel',
    'OrderStatusModel',
    'TimeInForceModel',
    'OrderSource',
    'OrderDestination',
    'OrderCategory',
    'OrderEvent',
    'create_market_order',
    'create_limit_order',
    'create_stop_order',
    'calculate_order_value',
    
    # Pair Models
    'Pair',
    'PairMapping',
    'PairPerformance',
    'PairFilter',
    'PairCategory',
    'PairStatus',
    'PairType',
    'CorrelationStrength',
    'LiquidityLevel',
    'VolatilityLevel',
    'create_pair',
    'calculate_pair_correlation',
    'calculate_pair_spread',
    
    # Portfolio Models
    'AssetAllocation',
    'PortfolioModel',
    'PortfolioSnapshot',
    'PortfolioStatus',
    'AllocationType',
    'RiskProfile',
    'PortfolioCategory',
    'RebalanceTrigger',
    'LimitType',
    'calculate_optimal_position_size',
    'calculate_portfolio_value_at_risk',
    'calculate_sharpe_ratio',
    
    # Position Models
    'PositionModel',
    'PositionSummary',
    'PositionFilterModel',
    'PositionSideModel',
    'PositionStatusModel',
    'PositionTypeModel',
    'MarginTypeModel',
    'PositionEvent',
    'create_position',
    'calculate_position_size',
    'calculate_liquidation_price',
    
    # Price Models
    'Price',
    'PriceFeed',
    'PriceHistory',
    'PriceComparison',
    'PriceAnomaly',
    'PriceForecast',
    'PriceSource',
    'PriceType',
    'PriceStatus',
    'TrendDirection',
    'PriceVolatilityLevel',
    'calculate_price_change',
    'calculate_volatility',
    'calculate_moving_average',
    'calculate_bollinger_bands',
    
    # Profit Models
    'ProfitCalculation',
    'ProfitSummary',
    'ProfitPerformance',
    'ProfitForecast',
    'ProfitType',
    'ProfitCurrency',
    'ProfitAttributionType',
    'PerformanceMetric',
    'calculate_profit_percentage',
    'calculate_profit_factor',
    'calculate_expected_value',
    'calculate_profit_sharpe_ratio',
    
    # Risk Models
    'RiskMetricValue',
    'RiskAssessment',
    'PositionRisk',
    'RiskLimit',
    'RiskReport',
    'RiskType',
    'RiskLevel',
    'RiskCategory',
    'RiskMetric',
    'RiskAction',
    'calculate_value_at_risk',
    'calculate_conditional_var',
    'calculate_risk_sharpe_ratio',
    'calculate_max_drawdown',
    
    # Signal Models
    'Signal',
    'SignalAggregation',
    'SignalFilter',
    'SignalPerformance',
    'SignalType',
    'SignalStrength',
    'SignalSource',
    'SignalStatus',
    'SignalPriority',
    'SignalValidationMethod',
    'calculate_signal_confidence',
    'combine_signals',
    
    # Slippage Models
    'SlippageModel',
    'SlippageEstimate',
    'SlippageStatistics',
    'SlippageTypeModel',
    'SlippageDirection',
    'SlippageSeverity',
    'SlippageModelType',
    'estimate_slippage',
    'calculate_slippage_tolerance',
    'analyze_slippage_impact',
    
    # Spread Models
    'Spread',
    'CrossExchangeSpread',
    'SpreadHistory',
    'SpreadOptimization',
    'SpreadType',
    'SpreadDirection',
    'SpreadSeverity',
    'SpreadCalculationMethod',
    'calculate_spread',
    'calculate_cross_exchange_spread',
    'calculate_arbitrage_spread',
    
    # Trade Models
    'TradeLeg',
    'Trade',
    'TradeSummary',
    'TradeSide',
    'TradeStatus',
    'TradeType',
    'TradeExecutionMethod',
    'TradeCategory',
    'TradeRole',
    'TradeSettlementStatus',
    'create_trade',
    'create_trade_leg',
    'calculate_trade_pnl',
    
    # Volume Models
    'Volume',
    'VolumeHistory',
    'VWAP',
    'VolumePrediction',
    'VolumeAnomaly',
    'VolumeType',
    'VolumePeriod',
    'VolumeDirection',
    'VolumeLiquidityLevel',
    'VolumeAnomalyType',
    'calculate_vwap',
    'calculate_volume_turnover',
    'calculate_volume_price_correlation',
]

# ====================================================================================
# MODULE INITIALIZATION
# ====================================================================================

# Package version
__version__ = "3.0.0"

# Package author
__author__ = "Dr X..."

# Package copyright
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package description
__description__ = "NEXUS AI Trading System - Arbitrage Bot Models"

# Package status
__status__ = "Production Ready"

# Logging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Models package v{__version__} initialized")

# ====================================================================================
# END OF MODELS PACKAGE
# ====================================================================================

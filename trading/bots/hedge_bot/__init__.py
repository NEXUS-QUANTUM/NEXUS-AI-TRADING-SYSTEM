# trading/bots/hedge_bot/__init__.py

"""
NEXUS AI TRADING SYSTEM - Hedge Bot Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Hedge Bot is an advanced automated trading bot designed for sophisticated 
hedging strategies across multiple markets and instruments.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path

# Version
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package metadata
PACKAGE_NAME = "nexus_hedge_bot"
PACKAGE_VERSION = __version__

# Logging setup
logger = logging.getLogger(__name__)

# Import core components
from .hedge_bot import HedgeBot
from .hedge_bot_config import HedgeBotConfig, load_config
from .hedge_bot_logger import HedgeBotLogger, setup_logging

# Core modules
from .core.base_hedge import BaseHedge
from .core.hedge_engine import HedgeEngine
from .core.hedge_types import HedgeType, HedgePosition, HedgeSignal
from .core.accounting_manager import AccountingManager
from .core.asset_allocator import AssetAllocator
from .core.audit_manager import AuditManager
from .core.backup_manager import BackupManager
from .core.beta_calculator import BetaCalculator
from .core.billing_manager import BillingManager
from .core.breakeven_manager import BreakevenManager
from .core.collateral_manager import CollateralManager
from .core.compliance_manager import ComplianceManager
from .core.concentration_manager import ConcentrationManager
from .core.correlation_analyzer import CorrelationAnalyzer
from .core.delta_calculator import DeltaCalculator
from .core.diversification_manager import DiversificationManager
from .core.drawdown_controller import DrawdownController
from .core.emergency_manager import EmergencyManager
from .core.exposure_manager import ExposureManager
from .core.futures_manager import FuturesManager
from .core.gamma_calculator import GammaCalculator
from .core.invoicing_manager import InvoicingManager
from .core.leverage_manager import LeverageManager
from .core.liquidation_manager import LiquidationManager
from .core.margin_manager import MarginManager
from .core.options_pricer import OptionsPricer
from .core.payment_manager import PaymentManager
from .core.perpetual_manager import PerpetualManager
from .core.portfolio_optimizer import PortfolioOptimizer
from .core.position_sizer import PositionSizer
from .core.pricing_manager import PricingManager
from .core.profit_target_manager import ProfitTargetManager
from .core.recovery_manager import RecoveryManager
from .core.regulatory_manager import RegulatoryManager
from .core.risk_calculator import RiskCalculator
from .core.risk_reward_manager import RiskRewardManager
from .core.scenario_manager import ScenarioManager
from .core.sensitivity_manager import SensitivityManager
from .core.spot_manager import SpotManager
from .core.stop_loss_manager import StopLossManager
from .core.subscription_manager import SubscriptionManager
from .core.take_profit_manager import TakeProfitManager
from .core.tax_manager import TaxManager
from .core.theta_calculator import ThetaCalculator
from .core.trailing_stop_manager import TrailingStopManager
from .core.vega_calculator import VegaCalculator
from .core.volatility_analyzer import VolatilityAnalyzer

# Strategy imports
from .strategies.base_strategy import BaseHedgeStrategy
from .strategies.strategy_factory import StrategyFactory
from .strategies.delta_hedge import DeltaHedgeStrategy
from .strategies.gamma_hedge import GammaHedgeStrategy
from .strategies.vega_hedge import VegaHedgeStrategy
from .strategies.theta_hedge import ThetaHedgeStrategy
from .strategies.beta_hedge import BetaHedgeStrategy
from .strategies.correlation_hedge import CorrelationHedgeStrategy
from .strategies.volatility_hedge import VolatilityHedgeStrategy
from .strategies.arbitrage_hedge import ArbitrageHedgeStrategy
from .strategies.portfolio_hedge import PortfolioHedgeStrategy
from .strategies.dynamic_hedge import DynamicHedgeStrategy
from .strategies.statistical_hedge import StatisticalHedgeStrategy
from .strategies.futures_hedge import FuturesHedgeStrategy
from .strategies.option_hedge import OptionHedgeStrategy
from .strategies.perpetual_hedge import PerpetualHedgeStrategy
from .strategies.basket_hedge import BasketHedgeStrategy
from .strategies.cross_hedge import CrossHedgeStrategy
from .strategies.tail_hedge import TailHedgeStrategy
from .strategies.protection_hedge import ProtectionHedgeStrategy
from .strategies.defensive_hedge import DefensiveHedgeStrategy
from .strategies.offensive_hedge import OffensiveHedgeStrategy
from .strategies.hybrid_hedge import HybridHedgeStrategy
from .strategies.concave_hedge import ConcaveHedgeStrategy
from .strategies.convex_hedge import ConvexHedgeStrategy
from .strategies.diversification_hedge import DiversificationHedgeStrategy
from .strategies.insurance_hedge import InsuranceHedgeStrategy
from .strategies.pair_hedge import PairHedgeStrategy
from .strategies.ratio_hedge import RatioHedgeStrategy
from .strategies.spread_hedge import SpreadHedgeStrategy
from .strategies.static_hedge import StaticHedgeStrategy
from .strategies.synthetic_hedge import SyntheticHedgeStrategy

# Risk management
from .hedge_bot_risk_manager import RiskManager
from .hedge_bot_stop_loss_manager import StopLossManager
from .hedge_bot_take_profit_manager import TakeProfitManager
from .hedge_bot_trailing_stop_manager import TrailingStopManager
from .hedge_bot_drawdown_controller import DrawdownController
from .hedge_bot_exposure import ExposureManager
from .hedge_bot_emergency_stop import EmergencyStopManager

# Position management
from .hedge_bot_position_manager import PositionManager
from .hedge_bot_position_sizer import PositionSizer
from .hedge_bot_order_manager import OrderManager

# Portfolio management
from .hedge_bot_portfolio import PortfolioManager
from .hedge_bot_rebalancer import Rebalancer
from .hedge_bot_diversification import DiversificationManager

# Performance & analytics
from .hedge_bot_metrics import MetricsCollector
from .hedge_bot_analytics import AnalyticsEngine
from .hedge_bot_analyzer import Analyzer
from .hedge_bot_backtest import BacktestEngine
from .hedge_bot_performance import PerformanceTracker

# Data management
from .hedge_bot_market_data import MarketDataProvider
from .hedge_bot_real_time_data import RealTimeDataHandler
from .hedge_bot_streaming_data import StreamingDataManager
from .hedge_bot_historical_data import HistoricalDataManager
from .hedge_bot_batch_data import BatchDataProcessor
from .hedge_bot_data_collector import DataCollector

# Data storage
from .hedge_bot_data_redis import RedisDataManager
from .hedge_bot_data_warehouse import DataWarehouseManager
from .hedge_bot_data_cache import CacheManager
from .hedge_bot_data_persistence import PersistenceManager

# Data processing
from .hedge_bot_data_transformation import DataTransformationManager
from .hedge_bot_data_validation import DataValidationManager
from .hedge_bot_data_quality import DataQualityManager
from .hedge_bot_data_standardization import DataStandardizationManager
from .hedge_bot_data_normalization import DataNormalizationManager

# Data streaming & queue
from .hedge_bot_data_stream import DataStreamManager
from .hedge_bot_data_queue import DataQueueManager
from .hedge_bot_data_pulsar import PulsarManager
from .hedge_bot_data_rabbitmq import RabbitMQManager
from .hedge_bot_data_kafka import KafkaManager
from .hedge_bot_data_pubsub import PubSubManager

# Search & query
from .hedge_bot_data_search import DataSearchManager
from .hedge_bot_data_query import DataQueryEngine
from .hedge_bot_data_sql import SQLQueryEngine

# Visualization
from .hedge_bot_data_visualization import DataVisualizationManager
from .hedge_bot_data_visualized import DataVisualizedManager
from .hedge_bot_dashboard import DashboardManager

# Security
from .hedge_bot_encryptor import DataEncryptor
from .hedge_bot_decryptor import DataDecryptor
from .hedge_bot_hasher import DataHasher
from .hedge_bot_signer import DataSigner
from .hedge_bot_verifier import DataVerifier
from .hedge_bot_authenticator import Authenticator
from .hedge_bot_authorizer import Authorizer

# Compliance & auditing
from .hedge_bot_compliance import ComplianceManager
from .hedge_bot_auditor import Auditor
from .hedge_bot_audit_trail import AuditTrail
from .hedge_bot_regulatory import RegulatoryManager
from .hedge_bot_sovereign import DataSovereigntyManager

# Notification & alerting
from .hedge_bot_notifier import Notifier
from .hedge_bot_alert_manager import AlertManager
from .hedge_bot_notification_service import NotificationService

# Monitoring
from .hedge_bot_monitor import SystemMonitor
from .hedge_bot_health import HealthChecker
from .hedge_bot_metrics_collector import MetricsCollector
from .hedge_bot_log_analyzer import LogAnalyzer
from .hedge_bot_performance_monitor import PerformanceMonitor

# Execution
from .hedge_bot_executor import HedgeBotExecutor
from .hedge_bot_execution_engine import ExecutionEngine
from .hedge_bot_smart_order_routing import SmartOrderRouter

# Risk metrics
from .hedge_bot_var import VaRCalculator
from .hedge_bot_cvar import CVaRCalculator
from .hedge_bot_stress_tester import StressTester
from .hedge_bot_scenario_analyzer import ScenarioAnalyzer
from .hedge_bot_sensitivity import SensitivityAnalyzer

# Optimization
from .hedge_bot_optimizer import Optimizer
from .hedge_bot_sharpe_optimizer import SharpeOptimizer
from .hedge_bot_kelly_criterion import KellyCriterion
from .hedge_bot_portfolio_optimizer import PortfolioOptimizer

# Utilities
from .hedge_bot_helpers import Helpers
from .hedge_bot_validators import Validators
from .hedge_bot_converters import Converters
from .hedge_bot_formatters import Formatters

# Models
from .models.position import Position, PositionType, PositionStatus
from .models.order import Order, OrderType, OrderSide, OrderStatus
from .models.trade import Trade, TradeType
from .models.portfolio import Portfolio, PortfolioAllocation
from .models.risk import RiskMetrics, VaR, CVaR
from .models.accounting import AccountingEntry, AccountingType
from .models.billing import BillingRecord, Invoice, Payment
from .models.tax import TaxRecord, TaxType
from .models.audit import AuditLog, AuditEvent
from .models.backup import BackupRecord, BackupStatus
from .models.beta import BetaMetrics
from .models.breakeven import BreakevenAnalysis
from .models.collateral import CollateralRecord
from .models.concentration import ConcentrationMetrics
from .models.correlation import CorrelationMatrix
from .models.delta import DeltaMetrics
from .models.diversification import DiversificationMetrics
from .models.drawdown import DrawdownMetrics
from .models.emergency import EmergencyRecord
from .models.exposure import ExposureMetrics
from .models.future import FutureContract
from .models.gamma import GammaMetrics
from .models.invoice import InvoiceRecord
from .models.leverage import LeverageMetrics
from .models.liquidation import LiquidationMetrics
from .models.margin import MarginRecord
from .models.option import OptionContract
from .models.perpetual import PerpetualContract
from .models.pricing import PricingModel
from .models.profit_target import ProfitTarget
from .models.recovery import RecoveryPlan
from .models.regulatory import RegulatoryReport
from .models.risk_reward import RiskRewardRatio
from .models.scenario import ScenarioAnalysis
from .models.sensitivity import SensitivityMetrics
from .models.stop_loss import StopLossOrder
from .models.subscription import SubscriptionPlan
from .models.take_profit import TakeProfitOrder
from .models.theta import ThetaMetrics
from .models.trailing_stop import TrailingStopOrder
from .models.vega import VegaMetrics
from .models.volatility import VolatilityMetrics

# Constants
from .constants import (
    DEFAULT_CONFIG,
    SUPPORTED_EXCHANGES,
    SUPPORTED_ASSETS,
    TIMEFRAMES,
    RISK_LEVELS,
    POSITION_DIRECTIONS,
    HEDGE_TYPES,
    ORDER_TYPES,
    STATUS_CODES,
    ERROR_CODES,
    API_ENDPOINTS,
    WEBSOCKET_URLS,
    RETRY_CONFIG,
    TIMEOUT_CONFIG,
    LOG_CONFIG
)

# Package exports
__all__ = [
    # Main
    "HedgeBot",
    "HedgeBotConfig",
    "load_config",
    "HedgeBotLogger",
    "setup_logging",
    
    # Core
    "BaseHedge",
    "HedgeEngine",
    "HedgeType",
    "HedgePosition",
    "HedgeSignal",
    "AccountingManager",
    "AssetAllocator",
    "AuditManager",
    "BackupManager",
    "BetaCalculator",
    "BillingManager",
    "BreakevenManager",
    "CollateralManager",
    "ComplianceManager",
    "ConcentrationManager",
    "CorrelationAnalyzer",
    "DeltaCalculator",
    "DiversificationManager",
    "DrawdownController",
    "EmergencyManager",
    "ExposureManager",
    "FuturesManager",
    "GammaCalculator",
    "InvoicingManager",
    "LeverageManager",
    "LiquidationManager",
    "MarginManager",
    "OptionsPricer",
    "PaymentManager",
    "PerpetualManager",
    "PortfolioOptimizer",
    "PositionSizer",
    "PricingManager",
    "ProfitTargetManager",
    "RecoveryManager",
    "RegulatoryManager",
    "RiskCalculator",
    "RiskRewardManager",
    "ScenarioManager",
    "SensitivityManager",
    "SpotManager",
    "StopLossManager",
    "SubscriptionManager",
    "TakeProfitManager",
    "TaxManager",
    "ThetaCalculator",
    "TrailingStopManager",
    "VegaCalculator",
    "VolatilityAnalyzer",
    
    # Strategies
    "BaseHedgeStrategy",
    "StrategyFactory",
    "DeltaHedgeStrategy",
    "GammaHedgeStrategy",
    "VegaHedgeStrategy",
    "ThetaHedgeStrategy",
    "BetaHedgeStrategy",
    "CorrelationHedgeStrategy",
    "VolatilityHedgeStrategy",
    "ArbitrageHedgeStrategy",
    "PortfolioHedgeStrategy",
    "DynamicHedgeStrategy",
    "StatisticalHedgeStrategy",
    "FuturesHedgeStrategy",
    "OptionHedgeStrategy",
    "PerpetualHedgeStrategy",
    "BasketHedgeStrategy",
    "CrossHedgeStrategy",
    "TailHedgeStrategy",
    "ProtectionHedgeStrategy",
    "DefensiveHedgeStrategy",
    "OffensiveHedgeStrategy",
    "HybridHedgeStrategy",
    "ConcaveHedgeStrategy",
    "ConvexHedgeStrategy",
    "DiversificationHedgeStrategy",
    "InsuranceHedgeStrategy",
    "PairHedgeStrategy",
    "RatioHedgeStrategy",
    "SpreadHedgeStrategy",
    "StaticHedgeStrategy",
    "SyntheticHedgeStrategy",
    
    # Risk Management
    "RiskManager",
    "StopLossManager",
    "TakeProfitManager",
    "TrailingStopManager",
    "DrawdownController",
    "ExposureManager",
    "EmergencyStopManager",
    "VaRCalculator",
    "CVaRCalculator",
    "StressTester",
    "ScenarioAnalyzer",
    "SensitivityAnalyzer",
    
    # Position Management
    "PositionManager",
    "PositionSizer",
    "OrderManager",
    
    # Portfolio
    "PortfolioManager",
    "Rebalancer",
    "DiversificationManager",
    "PortfolioOptimizer",
    
    # Performance & Analytics
    "MetricsCollector",
    "AnalyticsEngine",
    "Analyzer",
    "BacktestEngine",
    "PerformanceTracker",
    "SharpeOptimizer",
    "KellyCriterion",
    
    # Data Management
    "MarketDataProvider",
    "RealTimeDataHandler",
    "StreamingDataManager",
    "HistoricalDataManager",
    "BatchDataProcessor",
    "DataCollector",
    "RedisDataManager",
    "DataWarehouseManager",
    "CacheManager",
    "PersistenceManager",
    "DataTransformationManager",
    "DataValidationManager",
    "DataQualityManager",
    "DataStandardizationManager",
    "DataNormalizationManager",
    "DataStreamManager",
    "DataQueueManager",
    "PulsarManager",
    "RabbitMQManager",
    "KafkaManager",
    "PubSubManager",
    "DataSearchManager",
    "DataQueryEngine",
    "SQLQueryEngine",
    
    # Visualization
    "DataVisualizationManager",
    "DataVisualizedManager",
    "DashboardManager",
    
    # Security
    "DataEncryptor",
    "DataDecryptor",
    "DataHasher",
    "DataSigner",
    "DataVerifier",
    "Authenticator",
    "Authorizer",
    
    # Compliance & Auditing
    "ComplianceManager",
    "Auditor",
    "AuditTrail",
    "RegulatoryManager",
    "DataSovereigntyManager",
    
    # Notification & Alerting
    "Notifier",
    "AlertManager",
    "NotificationService",
    
    # Monitoring
    "SystemMonitor",
    "HealthChecker",
    "PerformanceMonitor",
    "LogAnalyzer",
    
    # Execution
    "HedgeBotExecutor",
    "ExecutionEngine",
    "SmartOrderRouter",
    
    # Optimization
    "Optimizer",
    
    # Utilities
    "Helpers",
    "Validators",
    "Converters",
    "Formatters",
    
    # Models - Position
    "Position",
    "PositionType",
    "PositionStatus",
    
    # Models - Order
    "Order",
    "OrderType",
    "OrderSide",
    "OrderStatus",
    
    # Models - Trade
    "Trade",
    "TradeType",
    
    # Models - Portfolio
    "Portfolio",
    "PortfolioAllocation",
    
    # Models - Risk
    "RiskMetrics",
    "VaR",
    "CVaR",
    
    # Models - Accounting
    "AccountingEntry",
    "AccountingType",
    
    # Models - Billing
    "BillingRecord",
    "Invoice",
    "Payment",
    
    # Models - Tax
    "TaxRecord",
    "TaxType",
    
    # Models - Audit
    "AuditLog",
    "AuditEvent",
    
    # Models - Backup
    "BackupRecord",
    "BackupStatus",
    
    # Models - Beta
    "BetaMetrics",
    
    # Models - Breakeven
    "BreakevenAnalysis",
    
    # Models - Collateral
    "CollateralRecord",
    
    # Models - Concentration
    "ConcentrationMetrics",
    
    # Models - Correlation
    "CorrelationMatrix",
    
    # Models - Delta
    "DeltaMetrics",
    
    # Models - Diversification
    "DiversificationMetrics",
    
    # Models - Drawdown
    "DrawdownMetrics",
    
    # Models - Emergency
    "EmergencyRecord",
    
    # Models - Exposure
    "ExposureMetrics",
    
    # Models - Future
    "FutureContract",
    
    # Models - Gamma
    "GammaMetrics",
    
    # Models - Invoice
    "InvoiceRecord",
    
    # Models - Leverage
    "LeverageMetrics",
    
    # Models - Liquidation
    "LiquidationMetrics",
    
    # Models - Margin
    "MarginRecord",
    
    # Models - Option
    "OptionContract",
    
    # Models - Perpetual
    "PerpetualContract",
    
    # Models - Pricing
    "PricingModel",
    
    # Models - Profit Target
    "ProfitTarget",
    
    # Models - Recovery
    "RecoveryPlan",
    
    # Models - Regulatory
    "RegulatoryReport",
    
    # Models - Risk Reward
    "RiskRewardRatio",
    
    # Models - Scenario
    "ScenarioAnalysis",
    
    # Models - Sensitivity
    "SensitivityMetrics",
    
    # Models - Stop Loss
    "StopLossOrder",
    
    # Models - Subscription
    "SubscriptionPlan",
    
    # Models - Take Profit
    "TakeProfitOrder",
    
    # Models - Theta
    "ThetaMetrics",
    
    # Models - Trailing Stop
    "TrailingStopOrder",
    
    # Models - Vega
    "VegaMetrics",
    
    # Models - Volatility
    "VolatilityMetrics",
    
    # Constants
    "DEFAULT_CONFIG",
    "SUPPORTED_EXCHANGES",
    "SUPPORTED_ASSETS",
    "TIMEFRAMES",
    "RISK_LEVELS",
    "POSITION_DIRECTIONS",
    "HEDGE_TYPES",
    "ORDER_TYPES",
    "STATUS_CODES",
    "ERROR_CODES",
    "API_ENDPOINTS",
    "WEBSOCKET_URLS",
    "RETRY_CONFIG",
    "TIMEOUT_CONFIG",
    "LOG_CONFIG",
]

# Version info
VERSION_INFO = {
    "version": __version__,
    "author": __author__,
    "copyright": __copyright__,
    "package": PACKAGE_NAME,
}

# Default configuration path
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "default_config.yaml"

# Initialize package
def init_package(config_path: Optional[str] = None) -> None:
    """Initialize the Hedge Bot package with optional config."""
    if config_path:
        config = load_config(config_path)
    else:
        config = DEFAULT_CONFIG
    
    # Setup logging
    setup_logging(config.get("logging", {}))
    
    # Initialize core components
    logger.info(f"Initializing Hedge Bot v{__version__}")
    logger.info(f"Package: {PACKAGE_NAME}")
    
    # Create instance
    bot = HedgeBot(config)
    logger.info("Hedge Bot initialized successfully")

# Cleanup
def cleanup_package() -> None:
    """Cleanup the Hedge Bot package."""
    logger.info("Cleaning up Hedge Bot package")
    # Add cleanup logic here

# Package metadata
__all__ = sorted(__all__)

# Version check
if sys.version_info < (3, 8):
    raise RuntimeError("Python 3.8+ required for Hedge Bot")

# Main entry point
if __name__ == "__main__":
    init_package()
    logger.info("Hedge Bot package loaded successfully")

# Export main class
__all__.append("HedgeBot")

# Module docstring
__doc__ = """
Hedge Bot - Advanced Automated Trading Bot for Hedging Strategies

The Hedge Bot is a sophisticated automated trading system designed for 
institutional-grade hedging strategies across multiple markets and instruments.

Key Features:
- Multi-market hedging (spot, futures, options, perpetuals)
- Advanced risk management with real-time monitoring
- Machine learning-based signal generation
- High-frequency execution with low latency
- Comprehensive data management and analytics
- Enterprise-grade security and compliance
- Scalable microservices architecture
- Real-time monitoring and alerting
- Backtesting and strategy optimization
- Portfolio management and rebalancing
- Integration with major exchanges and brokers

For more information, see:
- GitHub: https://github.com/NEXUS-QUANTUM/NEXUS-AI-TRADING-SYSTEM
- Documentation: https://docs.nexustradingia.com
- Support: support@nexustradingia.com
"""

# Constants for module
MODULE_CONSTANTS = {
    "VERSION": __version__,
    "AUTHOR": __author__,
    "COPYRIGHT": __copyright__,
    "PACKAGE_NAME": PACKAGE_NAME,
    "PACKAGE_VERSION": PACKAGE_VERSION,
    "SUPPORTED_EXCHANGES": SUPPORTED_EXCHANGES,
    "SUPPORTED_ASSETS": SUPPORTED_ASSETS,
    "TIMEFRAMES": TIMEFRAMES,
    "RISK_LEVELS": RISK_LEVELS,
    "POSITION_DIRECTIONS": POSITION_DIRECTIONS,
    "HEDGE_TYPES": HEDGE_TYPES,
    "ORDER_TYPES": ORDER_TYPES,
    "STATUS_CODES": STATUS_CODES,
    "ERROR_CODES": ERROR_CODES,
}

# Add module constants to __all__
__all__.extend(["MODULE_CONSTANTS", "VERSION_INFO", "DEFAULT_CONFIG_PATH"])

# Public API
PUBLIC_API = [
    "HedgeBot",
    "HedgeBotConfig",
    "load_config",
    "setup_logging",
    "init_package",
    "cleanup_package"
]

# Add public API to __all__
__all__.extend(PUBLIC_API)

# Version string
VERSION_STRING = f"nexus-hedge-bot=={__version__}"

# Package info
PACKAGE_INFO = {
    "name": PACKAGE_NAME,
    "version": __version__,
    "author": __author__,
    "copyright": __copyright__,
    "python_version": sys.version,
    "platform": sys.platform,
    "package_path": str(Path(__file__).parent)
}

# Export package info
__all__.append("PACKAGE_INFO")

# Clean up namespace
del Path, sys, os

# End of __init__.py

"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Package principal du bot d'arbitrage NEXUS
"""

# ============================================================
# PACKAGE METADATA
# ============================================================
__version__ = "2.0.0"
__author__ = "NEXUS QUANTUM TEAM"
__description__ = "Bot d'arbitrage algorithmique avancé NEXUS"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__license__ = "Proprietary"

# ============================================================
# PACKAGE EXPORTS
# ============================================================

# --- Core Components ---
from .arbitrage_bot import ArbitrageBot
from .arbitrage_bot_api import ArbitrageBotAPI, ArbitrageBotAPIClient
from .arbitrage_bot_analyzer import ArbitrageBotAnalyzer
from .arbitrage_bot_backtest import BacktestEngine
from .arbitrage_bot_config import ConfigManager, get_config_manager
from .arbitrage_bot_dashboard import ArbitrageBotDashboard, DashboardClient
from .arbitrage_bot_data_collector import ArbitrageBotDataCollector
from .arbitrage_bot_detector import ArbitrageBotDetector
from .arbitrage_bot_executor import ArbitrageBotExecutor
from .arbitrage_bot_health import ArbitrageBotHealth, HealthCheckResult, SystemInfo
from .arbitrage_bot_logger import (
    ArbitrageBotLogger,
    LogLevel,
    LogFormat,
    LogCategory,
    LogEntry,
    LogConfig,
    get_logger
)
from .arbitrage_bot_metrics import (
    ArbitrageBotMetrics,
    MetricType,
    MetricUnit,
    Metric,
    MetricSnapshot,
    get_metrics
)
from .arbitrage_bot_monitor import (
    ArbitrageBotMonitor,
    MonitorStatus,
    AlertSeverity,
    MonitorEventType,
    MonitorEvent,
    ResourceUsage,
    PerformanceMetrics,
    get_monitor
)
from .arbitrage_bot_notifier import (
    ArbitrageBotNotifier,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
    Notification,
    NotificationTemplate,
    get_notifier
)
from .arbitrage_bot_optimizer import StrategyOptimizer
from .arbitrage_bot_order_manager import OrderManager
from .arbitrage_bot_position_manager import PositionManager
from .arbitrage_bot_risk_manager import RiskManager
from .arbitrage_bot_signal import SignalGenerator
from .arbitrage_bot_state import StateManager

# --- Core Modules ---
from .core import (
    ArbitrageEngine,
    ArbitrageTypes,
    BalanceManager,
    BaseArbitrage,
    CircuitBreaker,
    ExchangeConnector,
    ExecutionTimer,
    FeeCalculator,
    GasCalculator,
    LatencyMonitor,
    MarketData,
    OrderRouter,
    OrderScheduler,
    OrderSplitter,
    OrderValidator,
    PortfolioManager,
    PositionTracker,
    ProfitCalculator,
    RateLimiter,
    RiskCalculator,
    SlippageCalculator,
)

# --- Exchanges ---
from .exchanges import (
    BaseExchange,
    ExchangeFactory,
    BinanceExchange,
    BybitExchange,
    CoinbaseExchange,
    KrakenExchange,
    KuCoinExchange,
    OKXExchange,
    GateioExchange,
    HuobiExchange,
    MexcExchange,
    BitgetExchange,
    UniswapExchange,
    PancakeSwapExchange,
    SushiSwapExchange,
    CurveExchange,
    BalancerExchange,
    OneInchExchange,
    DyDxExchange,
)

# --- Strategies ---
from .strategies import (
    BaseStrategy,
    StrategyFactory,
    CrossExchangeStrategy,
    TriangularStrategy,
    StatisticalStrategy,
    FlashLoanStrategy,
    CrossChainStrategy,
    AdaptiveStrategy,
    HybridStrategy,
    MeanReversionArbitrage,
    MomentumArbitrage,
    DexStrategy,
    FuturesSpotStrategy,
    MixedStrategy,
)

# --- Detectors ---
from .detectors import (
    BaseDetector,
    DetectorFactory,
    CrossExchangeDetector,
    TriangularDetector,
    StatisticalDetector,
    FlashLoanDetector,
    CrossChainDetector,
    AnomalyDetector,
    OpportunityScanner,
    PriceDetector,
    SignalDetector,
    SpreadDetector,
    VolumeDetector,
)

# --- Executors ---
from .executors import (
    BaseExecutor,
    ExecutorFactory,
    MarketExecutor,
    LimitExecutor,
    SmartExecutor,
    BatchExecutor,
    CrossExchangeExecutor,
    TriangularExecutor,
    StatisticalExecutor,
    FlashLoanExecutor,
    CrossChainExecutor,
    DexExecutor,
    FuturesSpotExecutor,
    MixedExecutor,
    ParallelExecutor,
    SequentialExecutor,
    OrderExecutor,
)

# --- Models ---
from .models import (
    Alert,
    Balance,
    Cost,
    Depth,
    Exchange,
    Fee,
    Gas,
    Latency,
    Opportunity,
    Order,
    Pair,
    Portfolio,
    Position,
    Price,
    Profit,
    Risk,
    Signal,
    Slippage,
    Spread,
    Trade,
    Volume,
)

# --- Utils ---
from .utils import (
    # Async
    async_to_sync,
    sync_to_async,
    async_retry,
    async_timeout,
    async_lock,
    async_semaphore,
    TaskManager,
    AsyncQueue,
    AsyncPool,
    EventLoopManager,
    get_event_loop_manager,
    
    # Backoff
    BackoffStrategy,
    BackoffConfig,
    BackoffCalculator,
    RetryIterator,
    AsyncRetryIterator,
    RetryManager,
    retry,
    retry_async,
    
    # Cache
    CacheStrategy,
    CacheConfig,
    BaseCache,
    CacheManager,
    cache_result,
    cache_result_async,
    get_cache_manager,
    
    # Converters
    NumberConverter,
    DateTimeConverter,
    StringConverter,
    DataFormatConverter,
    CaseConverter,
    
    # Crypto
    HashUtils,
    EncryptionUtils,
    JWTUtils,
    OTPUtils,
    RandomUtils,
    
    # Date
    TimezoneUtils,
    DateUtils,
    DateRangeUtils,
    DurationUtils,
    SECONDS_IN_MINUTE,
    SECONDS_IN_HOUR,
    SECONDS_IN_DAY,
    SECONDS_IN_WEEK,
    SECONDS_IN_MONTH,
    SECONDS_IN_YEAR,
    DATE_FORMATS,
    
    # Decorators
    timer,
    async_timer,
    log_call,
    async_log_call,
    timeout,
    async_timeout,
    singleton,
    synchronized,
    async_synchronized,
    cached_property,
    lazy_property,
    timeit,
    suppress,
    catch_all,
    validate_args,
    validate_return,
    
    # File
    FileMode,
    FileType,
    FileUtils,
    AsyncFileUtils,
    open_file,
    async_open_file,
    temporary_file,
    temporary_directory,
    
    # Formatters
    CurrencyFormatter,
    NumberFormatter,
    DateTimeFormatter,
    JSONFormatter,
    TableFormatter,
    LogFormatter,
    
    # Helpers
    IDGenerator,
    HashHelpers,
    ValidationHelpers,
    StringHelpers,
    DictHelpers,
    ListHelpers,
    ContextHelpers,
    
    # Locks
    LockType,
    BaseLock,
    ReentrantLock,
    ReadWriteLock,
    StripedLock,
    FairLock,
    LockManager,
    get_lock_manager,
    
    # Math
    DecimalUtils,
    StatisticsUtils,
    FinancialMathUtils,
    SignalProcessingUtils,
    OptimizationUtils,
    PHI,
    EULER,
    PI,
    TAU,
    DEFAULT_PRECISION,
    
    # Network
    HTTPMethod,
    NetworkProtocol,
    HTTPClient,
    WebSocketClient,
    NetworkUtils,
    
    # Pools
    PoolType,
    PoolStatus,
    BasePool,
    ThreadPool,
    AsyncPool,
    ConnectionPool,
    PoolManager,
    get_pool_manager,
    
    # Queues
    QueueType,
    QueueStatus,
    BaseQueue,
    DelayedQueue,
    ScheduledQueue,
    BatchQueue,
    QueueManager,
    get_queue_manager,
    
    # Retry
    RetryStrategy,
    RetryResult,
    RetryConfig,
    RetryContext,
    retry_context,
    async_retry_context,
    
    # String
    CaseType,
    StringFilter,
    StringUtils,
    JSONUtils,
    HTMLUtils,
    XMLUtils,
    EncodingUtils,
    
    # Threads
    ThreadStatus,
    ThreadPriority,
    BaseThread,
    ThreadPool as ThreadPoolUtil,
    ThreadManager,
    get_thread_manager,
    
    # Timers
    TimerType,
    TimerStatus,
    BaseTimer,
    Stopwatch,
    TimerManager,
    retry_with_timeout,
    get_timer_manager,
    
    # Validators
    ValidationSeverity,
    ValidationRuleType,
    ValidationResult,
    ValidationRule,
    BaseValidator,
    ComparisonValidator,
    ConditionalValidator,
    SchemaValidator,
)

# ============================================================
# PACKAGE INITIALIZATION
# ============================================================

# Créer les instances singleton par défaut
_logger = None
_metrics = None
_monitor = None
_notifier = None

def get_default_logger():
    """Récupère le logger par défaut"""
    global _logger
    if _logger is None:
        _logger = get_logger()
    return _logger

def get_default_metrics():
    """Récupère les métriques par défaut"""
    global _metrics
    if _metrics is None:
        _metrics = get_metrics()
    return _metrics

def get_default_monitor():
    """Récupère le monitor par défaut"""
    global _monitor
    if _monitor is None:
        _monitor = get_monitor()
    return _monitor

def get_default_notifier():
    """Récupère le notifier par défaut"""
    global _notifier
    if _notifier is None:
        _notifier = get_notifier()
    return _notifier

# ============================================================
# PACKAGE FUNCTIONS
# ============================================================

def get_version() -> str:
    """Récupère la version du package"""
    return __version__

def get_info() -> Dict[str, str]:
    """Récupère les informations du package"""
    return {
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "copyright": __copyright__,
        "license": __license__,
    }

def get_modules() -> List[str]:
    """Récupère la liste des modules du package"""
    return [
        "core",
        "exchanges",
        "strategies",
        "detectors",
        "executors",
        "models",
        "utils",
        "data",
        "monitoring",
        "config",
        "docs",
        "tests",
    ]

def get_components() -> List[Dict[str, str]]:
    """Récupère la liste des composants du package"""
    return [
        {
            "name": "ArbitrageBot",
            "module": "arbitrage_bot",
            "description": "Bot principal d'arbitrage"
        },
        {
            "name": "ArbitrageBotAPI",
            "module": "arbitrage_bot_api",
            "description": "API REST du bot"
        },
        {
            "name": "ArbitrageBotAnalyzer",
            "module": "arbitrage_bot_analyzer",
            "description": "Analyseur de performance"
        },
        {
            "name": "BacktestEngine",
            "module": "arbitrage_bot_backtest",
            "description": "Moteur de backtest"
        },
        {
            "name": "ConfigManager",
            "module": "arbitrage_bot_config",
            "description": "Gestionnaire de configuration"
        },
        {
            "name": "ArbitrageBotDashboard",
            "module": "arbitrage_bot_dashboard",
            "description": "Tableau de bord"
        },
        {
            "name": "ArbitrageBotDataCollector",
            "module": "arbitrage_bot_data_collector",
            "description": "Collecteur de données"
        },
        {
            "name": "ArbitrageBotDetector",
            "module": "arbitrage_bot_detector",
            "description": "Détecteur d'opportunités"
        },
        {
            "name": "ArbitrageBotExecutor",
            "module": "arbitrage_bot_executor",
            "description": "Exécuteur d'ordres"
        },
        {
            "name": "ArbitrageBotHealth",
            "module": "arbitrage_bot_health",
            "description": "Health check"
        },
        {
            "name": "ArbitrageBotLogger",
            "module": "arbitrage_bot_logger",
            "description": "Système de logging"
        },
        {
            "name": "ArbitrageBotMetrics",
            "module": "arbitrage_bot_metrics",
            "description": "Système de métriques"
        },
        {
            "name": "ArbitrageBotMonitor",
            "module": "arbitrage_bot_monitor",
            "description": "Système de monitoring"
        },
        {
            "name": "ArbitrageBotNotifier",
            "module": "arbitrage_bot_notifier",
            "description": "Système de notifications"
        },
        {
            "name": "ArbitrageBotOptimizer",
            "module": "arbitrage_bot_optimizer",
            "description": "Optimiseur de stratégies"
        },
        {
            "name": "OrderManager",
            "module": "arbitrage_bot_order_manager",
            "description": "Gestionnaire d'ordres"
        },
        {
            "name": "PositionManager",
            "module": "arbitrage_bot_position_manager",
            "description": "Gestionnaire de positions"
        },
        {
            "name": "RiskManager",
            "module": "arbitrage_bot_risk_manager",
            "description": "Gestionnaire de risques"
        },
        {
            "name": "SignalGenerator",
            "module": "arbitrage_bot_signal",
            "description": "Générateur de signaux"
        },
        {
            "name": "StateManager",
            "module": "arbitrage_bot_state",
            "description": "Gestionnaire d'état"
        },
    ]

# ============================================================
# DEPENDENCY CHECK
# ============================================================

def check_dependencies() -> Dict[str, Any]:
    """Vérifie les dépendances du package"""
    import sys
    import importlib
    
    dependencies = {
        "python": sys.version_info,
        "packages": {}
    }
    
    required_packages = [
        "asyncio",
        "aiohttp",
        "websockets",
        "fastapi",
        "uvicorn",
        "pydantic",
        "sqlalchemy",
        "redis",
        "psycopg2",
        "numpy",
        "pandas",
        "torch",
        "scikit-learn",
        "plotly",
        "prometheus_client",
        "grafana",
        "loki",
        "tempo",
    ]
    
    for package in required_packages:
        try:
            module = importlib.import_module(package)
            dependencies["packages"][package] = {
                "installed": True,
                "version": getattr(module, "__version__", "unknown")
            }
        except ImportError:
            dependencies["packages"][package] = {
                "installed": False,
                "version": None
            }
    
    return dependencies

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal du package"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot")
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"NEXUS Arbitrage Bot v{__version__}"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Affiche les informations du package"
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Vérifie les dépendances"
    )
    
    args = parser.parse_args()
    
    if args.info:
        print("=" * 60)
        print("NEXUS AI Trading System - Arbitrage Bot")
        print("=" * 60)
        print(f"Version:     {__version__}")
        print(f"Author:      {__author__}")
        print(f"Description: {__description__}")
        print(f"Copyright:   {__copyright__}")
        print(f"License:     {__license__}")
        print("=" * 60)
        print("\nComponents:")
        for comp in get_components():
            print(f"  - {comp['name']}: {comp['description']}")
    
    if args.check_deps:
        deps = check_dependencies()
        print("\n" + "=" * 60)
        print("Dependencies Check")
        print("=" * 60)
        print(f"Python: {deps['python'].major}.{deps['python'].minor}.{deps['python'].micro}")
        print("\nPackages:")
        for name, info in deps["packages"].items():
            status = "✅" if info["installed"] else "❌"
            version = info["version"] if info["installed"] else "not installed"
            print(f"  {status} {name}: {version}")

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Version
    '__version__',
    '__author__',
    '__description__',
    '__copyright__',
    '__license__',
    
    # Bot
    'ArbitrageBot',
    'ArbitrageBotAPI',
    'ArbitrageBotAPIClient',
    'ArbitrageBotAnalyzer',
    'BacktestEngine',
    'ConfigManager',
    'get_config_manager',
    'ArbitrageBotDashboard',
    'DashboardClient',
    'ArbitrageBotDataCollector',
    'ArbitrageBotDetector',
    'ArbitrageBotExecutor',
    'ArbitrageBotHealth',
    'HealthCheckResult',
    'SystemInfo',
    'ArbitrageBotLogger',
    'LogLevel',
    'LogFormat',
    'LogCategory',
    'LogEntry',
    'LogConfig',
    'get_logger',
    'ArbitrageBotMetrics',
    'MetricType',
    'MetricUnit',
    'Metric',
    'MetricSnapshot',
    'get_metrics',
    'ArbitrageBotMonitor',
    'MonitorStatus',
    'AlertSeverity',
    'MonitorEventType',
    'MonitorEvent',
    'ResourceUsage',
    'PerformanceMetrics',
    'get_monitor',
    'ArbitrageBotNotifier',
    'NotificationType',
    'NotificationChannel',
    'NotificationPriority',
    'Notification',
    'NotificationTemplate',
    'get_notifier',
    'StrategyOptimizer',
    'OrderManager',
    'PositionManager',
    'RiskManager',
    'SignalGenerator',
    'StateManager',
    
    # Core
    'ArbitrageEngine',
    'ArbitrageTypes',
    'BalanceManager',
    'BaseArbitrage',
    'CircuitBreaker',
    'ExchangeConnector',
    'ExecutionTimer',
    'FeeCalculator',
    'GasCalculator',
    'LatencyMonitor',
    'MarketData',
    'OrderRouter',
    'OrderScheduler',
    'OrderSplitter',
    'OrderValidator',
    'PortfolioManager',
    'PositionTracker',
    'ProfitCalculator',
    'RateLimiter',
    'RiskCalculator',
    'SlippageCalculator',
    
    # Exchanges
    'BaseExchange',
    'ExchangeFactory',
    'BinanceExchange',
    'BybitExchange',
    'CoinbaseExchange',
    'KrakenExchange',
    'KuCoinExchange',
    'OKXExchange',
    'GateioExchange',
    'HuobiExchange',
    'MexcExchange',
    'BitgetExchange',
    'UniswapExchange',
    'PancakeSwapExchange',
    'SushiSwapExchange',
    'CurveExchange',
    'BalancerExchange',
    'OneInchExchange',
    'DyDxExchange',
    
    # Strategies
    'BaseStrategy',
    'StrategyFactory',
    'CrossExchangeStrategy',
    'TriangularStrategy',
    'StatisticalStrategy',
    'FlashLoanStrategy',
    'CrossChainStrategy',
    'AdaptiveStrategy',
    'HybridStrategy',
    'MeanReversionArbitrage',
    'MomentumArbitrage',
    'DexStrategy',
    'FuturesSpotStrategy',
    'MixedStrategy',
    
    # Detectors
    'BaseDetector',
    'DetectorFactory',
    'CrossExchangeDetector',
    'TriangularDetector',
    'StatisticalDetector',
    'FlashLoanDetector',
    'CrossChainDetector',
    'AnomalyDetector',
    'OpportunityScanner',
    'PriceDetector',
    'SignalDetector',
    'SpreadDetector',
    'VolumeDetector',
    
    # Executors
    'BaseExecutor',
    'ExecutorFactory',
    'MarketExecutor',
    'LimitExecutor',
    'SmartExecutor',
    'BatchExecutor',
    'CrossExchangeExecutor',
    'TriangularExecutor',
    'StatisticalExecutor',
    'FlashLoanExecutor',
    'CrossChainExecutor',
    'DexExecutor',
    'FuturesSpotExecutor',
    'MixedExecutor',
    'ParallelExecutor',
    'SequentialExecutor',
    'OrderExecutor',
    
    # Models
    'Alert',
    'Balance',
    'Cost',
    'Depth',
    'Exchange',
    'Fee',
    'Gas',
    'Latency',
    'Opportunity',
    'Order',
    'Pair',
    'Portfolio',
    'Position',
    'Price',
    'Profit',
    'Risk',
    'Signal',
    'Slippage',
    'Spread',
    'Trade',
    'Volume',
    
    # Utils
    'async_to_sync',
    'sync_to_async',
    'async_retry',
    'async_timeout',
    'async_lock',
    'async_semaphore',
    'TaskManager',
    'AsyncQueue',
    'AsyncPool',
    'EventLoopManager',
    'get_event_loop_manager',
    'BackoffStrategy',
    'BackoffConfig',
    'BackoffCalculator',
    'RetryIterator',
    'AsyncRetryIterator',
    'RetryManager',
    'retry',
    'retry_async',
    'CacheStrategy',
    'CacheConfig',
    'BaseCache',
    'CacheManager',
    'cache_result',
    'cache_result_async',
    'get_cache_manager',
    'NumberConverter',
    'DateTimeConverter',
    'StringConverter',
    'DataFormatConverter',
    'CaseConverter',
    'HashUtils',
    'EncryptionUtils',
    'JWTUtils',
    'OTPUtils',
    'RandomUtils',
    'TimezoneUtils',
    'DateUtils',
    'DateRangeUtils',
    'DurationUtils',
    'SECONDS_IN_MINUTE',
    'SECONDS_IN_HOUR',
    'SECONDS_IN_DAY',
    'SECONDS_IN_WEEK',
    'SECONDS_IN_MONTH',
    'SECONDS_IN_YEAR',
    'DATE_FORMATS',
    'timer',
    'async_timer',
    'log_call',
    'async_log_call',
    'timeout',
    'async_timeout',
    'singleton',
    'synchronized',
    'async_synchronized',
    'cached_property',
    'lazy_property',
    'timeit',
    'suppress',
    'catch_all',
    'validate_args',
    'validate_return',
    'FileMode',
    'FileType',
    'FileUtils',
    'AsyncFileUtils',
    'open_file',
    'async_open_file',
    'temporary_file',
    'temporary_directory',
    'CurrencyFormatter',
    'NumberFormatter',
    'DateTimeFormatter',
    'JSONFormatter',
    'TableFormatter',
    'LogFormatter',
    'IDGenerator',
    'HashHelpers',
    'ValidationHelpers',
    'StringHelpers',
    'DictHelpers',
    'ListHelpers',
    'ContextHelpers',
    'LockType',
    'BaseLock',
    'ReentrantLock',
    'ReadWriteLock',
    'StripedLock',
    'FairLock',
    'LockManager',
    'get_lock_manager',
    'DecimalUtils',
    'StatisticsUtils',
    'FinancialMathUtils',
    'SignalProcessingUtils',
    'OptimizationUtils',
    'PHI',
    'EULER',
    'PI',
    'TAU',
    'DEFAULT_PRECISION',
    'HTTPMethod',
    'NetworkProtocol',
    'HTTPClient',
    'WebSocketClient',
    'NetworkUtils',
    'PoolType',
    'PoolStatus',
    'BasePool',
    'ThreadPool',
    'AsyncPool',
    'ConnectionPool',
    'PoolManager',
    'get_pool_manager',
    'QueueType',
    'QueueStatus',
    'BaseQueue',
    'DelayedQueue',
    'ScheduledQueue',
    'BatchQueue',
    'QueueManager',
    'get_queue_manager',
    'RetryStrategy',
    'RetryResult',
    'RetryConfig',
    'RetryContext',
    'retry_context',
    'async_retry_context',
    'CaseType',
    'StringFilter',
    'StringUtils',
    'JSONUtils',
    'HTMLUtils',
    'XMLUtils',
    'EncodingUtils',
    'ThreadStatus',
    'ThreadPriority',
    'BaseThread',
    'ThreadPoolUtil',
    'ThreadManager',
    'get_thread_manager',
    'TimerType',
    'TimerStatus',
    'BaseTimer',
    'Stopwatch',
    'TimerManager',
    'retry_with_timeout',
    'get_timer_manager',
    'ValidationSeverity',
    'ValidationRuleType',
    'ValidationResult',
    'ValidationRule',
    'BaseValidator',
    'ComparisonValidator',
    'ConditionalValidator',
    'SchemaValidator',
    
    # Package Functions
    'get_version',
    'get_info',
    'get_modules',
    'get_components',
    'check_dependencies',
    'get_default_logger',
    'get_default_metrics',
    'get_default_monitor',
    'get_default_notifier',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

import logging
logger = logging.getLogger(__name__)
logger.info(f"NEXUS Arbitrage Bot package v{__version__} initialized")

# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

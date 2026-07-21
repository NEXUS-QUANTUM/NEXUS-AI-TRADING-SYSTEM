"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Module d'utilitaires pour le bot d'arbitrage
"""

# ============================================================
# PACKAGE METADATA
# ============================================================
__version__ = "2.0.0"
__author__ = "NEXUS QUANTUM TEAM"
__description__ = "Utilitaires pour le bot d'arbitrage NEXUS"

# ============================================================
# IMPORTS
# ============================================================
import os
import sys
import logging
from typing import Any, Dict, List, Optional, Union, Tuple, Callable

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# UTILITY MODULES
# ============================================================

# --- Async Utilities ---
from .async_utils import (
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
)

# --- Backoff Utilities ---
from .backoff import (
    BackoffStrategy,
    BackoffConfig,
    BackoffContext,
    RetryContext,
    BackoffCalculator,
    RetryIterator,
    AsyncRetryIterator,
    RetryManager,
    retry,
    retry_async,
)

# --- Cache Utilities ---
from .cache import (
    CacheStrategy,
    CacheConfig,
    CacheStats,
    CacheEntry,
    BaseCache,
    CacheManager,
    cache_result,
    cache_result_async,
    get_cache_manager,
)

# --- Converters ---
from .converters import (
    NumberConverter,
    DateTimeConverter,
    StringConverter,
    DataFormatConverter,
    CaseConverter,
)

# --- Crypto Utilities ---
from .crypto_utils import (
    HashUtils,
    EncryptionUtils,
    JWTUtils,
    OTPUtils,
    RandomUtils,
)

# --- Date Utilities ---
from .date_utils import (
    SECONDS_IN_MINUTE,
    SECONDS_IN_HOUR,
    SECONDS_IN_DAY,
    SECONDS_IN_WEEK,
    SECONDS_IN_MONTH,
    SECONDS_IN_YEAR,
    MS_IN_SECOND,
    MS_IN_MINUTE,
    MS_IN_HOUR,
    MS_IN_DAY,
    MS_IN_WEEK,
    DATE_FORMATS,
    TimezoneUtils,
    DateUtils,
    DateRangeUtils,
    DurationUtils,
)

# --- Decorators ---
from .decorators import (
    timer,
    async_timer,
    log_call,
    async_log_call,
    retry,
    async_retry,
    timeout,
    async_timeout,
    singleton,
    synchronized,
    async_synchronized,
    dataclass_with_validation,
    singleton_class,
    timeit,
    suppress,
    catch_all,
    cached_property,
    lazy_property,
    classmethod_with_logging,
    staticmethod_with_logging,
    validate_args,
    validate_return,
)

# --- File Utilities ---
from .file_utils import (
    FileMode,
    FileType,
    FileUtils,
    AsyncFileUtils,
    open_file,
    async_open_file,
    temporary_file,
    temporary_directory,
)

# --- Formatters ---
from .formatters import (
    CurrencyFormatter,
    NumberFormatter,
    DateTimeFormatter,
    JSONFormatter,
    TableFormatter,
    LogFormatter,
)

# --- Helpers ---
from .helpers import (
    IDGenerator,
    HashHelpers,
    ValidationHelpers,
    StringHelpers,
    DictHelpers,
    ListHelpers,
    ContextHelpers,
)

# --- Locks ---
from .locks import (
    LockType,
    LockAcquireResult,
    BaseLock,
    ReentrantLock,
    ReadWriteLock,
    StripedLock,
    FairLock,
    LockManager,
    get_lock_manager,
)

# --- Math Utilities ---
from .math_utils import (
    PHI,
    EULER,
    PI,
    TAU,
    DEFAULT_PRECISION,
    DecimalUtils,
    StatisticsUtils,
    FinancialMathUtils,
    SignalProcessingUtils,
    OptimizationUtils,
)

# --- Network Utilities ---
from .network_utils import (
    HTTPMethod,
    NetworkProtocol,
    HTTPClient,
    WebSocketClient,
    NetworkUtils,
)

# --- Pools ---
from .pools import (
    PoolType,
    PoolStatus,
    BasePool,
    ThreadPool,
    AsyncPool,
    ConnectionPool,
    PoolManager,
    get_pool_manager,
)

# --- Queues ---
from .queues import (
    QueueType,
    QueueStatus,
    BaseQueue,
    DelayedQueue,
    ScheduledQueue,
    BatchQueue,
    QueueManager,
    get_queue_manager,
)

# --- Retry Utilities ---
from .retry import (
    RetryStrategy,
    RetryResult,
    RetryConfig,
    RetryContext,
    RetryIterator,
    AsyncRetryIterator,
    RetryManager,
    retry,
    retry_async,
    retry_context,
    async_retry_context,
)

# --- String Utilities ---
from .string_utils import (
    CaseType,
    StringFilter,
    StringUtils,
    JSONUtils,
    HTMLUtils,
    XMLUtils,
    EncodingUtils,
)

# --- Threads ---
from .threads import (
    ThreadStatus,
    ThreadPriority,
    ThreadInfo,
    BaseThread,
    ThreadPool,
    ThreadManager,
    get_thread_manager,
)

# --- Timers ---
from .timers import (
    TimerType,
    TimerStatus,
    TimerInfo,
    BaseTimer,
    Stopwatch,
    TimerManager,
    timeout,
    async_timeout,
    retry_with_timeout,
    get_timer_manager,
)

# --- Validators ---
from .validators import (
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
# UTILITY FUNCTIONS
# ============================================================

def get_all_utils() -> Dict[str, List[str]]:
    """
    Récupère la liste de tous les utilitaires disponibles
    
    Returns:
        Dict[str, List[str]]: Utilitaires par catégorie
    """
    return {
        'async': [
            'async_to_sync', 'sync_to_async', 'async_retry', 'async_timeout',
            'async_lock', 'async_semaphore', 'TaskManager', 'AsyncQueue',
            'AsyncPool', 'EventLoopManager', 'get_event_loop_manager'
        ],
        'backoff': [
            'BackoffStrategy', 'BackoffConfig', 'BackoffCalculator',
            'RetryIterator', 'AsyncRetryIterator', 'RetryManager'
        ],
        'cache': [
            'CacheStrategy', 'CacheConfig', 'BaseCache', 'CacheManager',
            'cache_result', 'cache_result_async', 'get_cache_manager'
        ],
        'converters': [
            'NumberConverter', 'DateTimeConverter', 'StringConverter',
            'DataFormatConverter', 'CaseConverter'
        ],
        'crypto': [
            'HashUtils', 'EncryptionUtils', 'JWTUtils', 'OTPUtils', 'RandomUtils'
        ],
        'date': [
            'TimezoneUtils', 'DateUtils', 'DateRangeUtils', 'DurationUtils'
        ],
        'decorators': [
            'timer', 'async_timer', 'log_call', 'async_log_call',
            'timeout', 'async_timeout', 'singleton', 'synchronized',
            'async_synchronized', 'cached_property', 'lazy_property'
        ],
        'file': [
            'FileMode', 'FileType', 'FileUtils', 'AsyncFileUtils',
            'open_file', 'async_open_file', 'temporary_file', 'temporary_directory'
        ],
        'formatters': [
            'CurrencyFormatter', 'NumberFormatter', 'DateTimeFormatter',
            'JSONFormatter', 'TableFormatter', 'LogFormatter'
        ],
        'helpers': [
            'IDGenerator', 'HashHelpers', 'ValidationHelpers',
            'StringHelpers', 'DictHelpers', 'ListHelpers', 'ContextHelpers'
        ],
        'locks': [
            'LockType', 'BaseLock', 'ReentrantLock', 'ReadWriteLock',
            'StripedLock', 'FairLock', 'LockManager', 'get_lock_manager'
        ],
        'math': [
            'DecimalUtils', 'StatisticsUtils', 'FinancialMathUtils',
            'SignalProcessingUtils', 'OptimizationUtils'
        ],
        'network': [
            'HTTPMethod', 'NetworkProtocol', 'HTTPClient',
            'WebSocketClient', 'NetworkUtils'
        ],
        'pools': [
            'PoolType', 'PoolStatus', 'BasePool', 'ThreadPool',
            'AsyncPool', 'ConnectionPool', 'PoolManager', 'get_pool_manager'
        ],
        'queues': [
            'QueueType', 'QueueStatus', 'BaseQueue', 'DelayedQueue',
            'ScheduledQueue', 'BatchQueue', 'QueueManager', 'get_queue_manager'
        ],
        'retry': [
            'RetryStrategy', 'RetryConfig', 'RetryContext',
            'RetryIterator', 'AsyncRetryIterator', 'RetryManager'
        ],
        'string': [
            'CaseType', 'StringFilter', 'StringUtils', 'JSONUtils',
            'HTMLUtils', 'XMLUtils', 'EncodingUtils'
        ],
        'threads': [
            'ThreadStatus', 'ThreadPriority', 'BaseThread',
            'ThreadPool', 'ThreadManager', 'get_thread_manager'
        ],
        'timers': [
            'TimerType', 'TimerStatus', 'BaseTimer', 'Stopwatch',
            'TimerManager', 'get_timer_manager'
        ],
        'validators': [
            'ValidationSeverity', 'ValidationRuleType', 'ValidationResult',
            'ValidationRule', 'BaseValidator', 'ComparisonValidator',
            'ConditionalValidator', 'SchemaValidator'
        ],
    }

def get_utility_module(module_name: str):
    """
    Récupère un module d'utilitaires par nom
    
    Args:
        module_name: Nom du module
        
    Returns:
        Module: Module d'utilitaires
    """
    module_map = {
        'async': async_utils,
        'backoff': backoff,
        'cache': cache,
        'converters': converters,
        'crypto': crypto_utils,
        'date': date_utils,
        'decorators': decorators,
        'file': file_utils,
        'formatters': formatters,
        'helpers': helpers,
        'locks': locks,
        'math': math_utils,
        'network': network_utils,
        'pools': pools,
        'queues': queues,
        'retry': retry,
        'string': string_utils,
        'threads': threads,
        'timers': timers,
        'validators': validators,
    }
    
    return module_map.get(module_name)

# ============================================================
# PACKAGE EXPORTS
# ============================================================

__all__ = [
    # Version
    '__version__',
    '__author__',
    '__description__',
    
    # Async
    'async_to_sync', 'sync_to_async', 'async_retry', 'async_timeout',
    'async_lock', 'async_semaphore', 'TaskManager', 'AsyncQueue',
    'AsyncPool', 'EventLoopManager', 'get_event_loop_manager',
    
    # Backoff
    'BackoffStrategy', 'BackoffConfig', 'BackoffCalculator',
    'RetryIterator', 'AsyncRetryIterator', 'RetryManager',
    
    # Cache
    'CacheStrategy', 'CacheConfig', 'BaseCache', 'CacheManager',
    'cache_result', 'cache_result_async', 'get_cache_manager',
    
    # Converters
    'NumberConverter', 'DateTimeConverter', 'StringConverter',
    'DataFormatConverter', 'CaseConverter',
    
    # Crypto
    'HashUtils', 'EncryptionUtils', 'JWTUtils', 'OTPUtils', 'RandomUtils',
    
    # Date
    'TimezoneUtils', 'DateUtils', 'DateRangeUtils', 'DurationUtils',
    'SECONDS_IN_MINUTE', 'SECONDS_IN_HOUR', 'SECONDS_IN_DAY',
    'SECONDS_IN_WEEK', 'SECONDS_IN_MONTH', 'SECONDS_IN_YEAR',
    'DATE_FORMATS',
    
    # Decorators
    'timer', 'async_timer', 'log_call', 'async_log_call',
    'timeout', 'async_timeout', 'singleton', 'synchronized',
    'async_synchronized', 'cached_property', 'lazy_property',
    'timeit', 'suppress', 'catch_all',
    'dataclass_with_validation', 'singleton_class',
    'classmethod_with_logging', 'staticmethod_with_logging',
    'validate_args', 'validate_return',
    
    # File
    'FileMode', 'FileType', 'FileUtils', 'AsyncFileUtils',
    'open_file', 'async_open_file', 'temporary_file', 'temporary_directory',
    
    # Formatters
    'CurrencyFormatter', 'NumberFormatter', 'DateTimeFormatter',
    'JSONFormatter', 'TableFormatter', 'LogFormatter',
    
    # Helpers
    'IDGenerator', 'HashHelpers', 'ValidationHelpers',
    'StringHelpers', 'DictHelpers', 'ListHelpers', 'ContextHelpers',
    
    # Locks
    'LockType', 'BaseLock', 'ReentrantLock', 'ReadWriteLock',
    'StripedLock', 'FairLock', 'LockManager', 'get_lock_manager',
    
    # Math
    'PHI', 'EULER', 'PI', 'TAU', 'DEFAULT_PRECISION',
    'DecimalUtils', 'StatisticsUtils', 'FinancialMathUtils',
    'SignalProcessingUtils', 'OptimizationUtils',
    
    # Network
    'HTTPMethod', 'NetworkProtocol', 'HTTPClient',
    'WebSocketClient', 'NetworkUtils',
    
    # Pools
    'PoolType', 'PoolStatus', 'BasePool', 'ThreadPool',
    'AsyncPool', 'ConnectionPool', 'PoolManager', 'get_pool_manager',
    
    # Queues
    'QueueType', 'QueueStatus', 'BaseQueue', 'DelayedQueue',
    'ScheduledQueue', 'BatchQueue', 'QueueManager', 'get_queue_manager',
    
    # Retry
    'RetryStrategy', 'RetryConfig', 'RetryContext',
    'RetryIterator', 'AsyncRetryIterator', 'RetryManager',
    'retry', 'retry_async', 'retry_context', 'async_retry_context',
    
    # String
    'CaseType', 'StringFilter', 'StringUtils', 'JSONUtils',
    'HTMLUtils', 'XMLUtils', 'EncodingUtils',
    
    # Threads
    'ThreadStatus', 'ThreadPriority', 'BaseThread',
    'ThreadPool', 'ThreadManager', 'get_thread_manager',
    
    # Timers
    'TimerType', 'TimerStatus', 'BaseTimer', 'Stopwatch',
    'TimerManager', 'get_timer_manager',
    'retry_with_timeout',
    
    # Validators
    'ValidationSeverity', 'ValidationRuleType', 'ValidationResult',
    'ValidationRule', 'BaseValidator', 'ComparisonValidator',
    'ConditionalValidator', 'SchemaValidator',
    
    # Functions
    'get_all_utils', 'get_utility_module',
]

# ============================================================
# MODULE INITIALIZATION
# ============================================================

logger.info(f"Utils module initialized (v{__version__})")
logger.debug(f"Available utility categories: {list(get_all_utils().keys())}")

"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Configuration Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Module de configuration pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import os
import sys
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

# ============================================================
# LOGGING CONFIGURATION
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================
class Environment(Enum):
    """Environnements supportés"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

class LogLevel(Enum):
    """Niveaux de log supportés"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class StrategyType(Enum):
    """Types de stratégies supportées"""
    CROSS_EXCHANGE = "cross_exchange"
    TRIANGULAR = "triangular"
    STATISTICAL = "statistical"
    FLASH_LOAN = "flash_loan"
    CROSS_CHAIN = "cross_chain"

class ExchangeType(Enum):
    """Types d'exchanges supportés"""
    CEX = "cex"
    DEX = "dex"
    FOREX = "forex"
    STOCKS = "stocks"

class RiskLevel(Enum):
    """Niveaux de risque"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    AGGRESSIVE = "aggressive"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class BotConfig:
    """Configuration du bot"""
    id: str = "arbitrage-bot-001"
    name: str = "NEXUS Arbitrage Bot"
    version: str = "2.0.0"
    description: str = "Bot d'arbitrage algorithmique avancé"
    environment: str = "production"
    instance: str = "prod-001"
    deployment: str = "kubernetes"
    region: str = "eu-west-1"
    cluster: str = "nexus-prod"

@dataclass
class GeneralConfig:
    """Configuration générale"""
    enabled: bool = True
    debug: bool = False
    log_level: str = "info"
    timezone: str = "UTC"
    locale: str = "en_US"
    max_concurrent_operations: int = 20
    operation_timeout: int = 30
    retry_attempts: int = 5
    retry_delay: int = 5
    shutdown_timeout: int = 30
    startup_timeout: int = 60
    health_check_interval: int = 10
    enable_profiling: bool = False
    enable_metrics: bool = True
    enable_tracing: bool = True
    graceful_shutdown: bool = True
    emergency_stop: bool = True

@dataclass
class ExchangeAPIConfig:
    """Configuration API d'un exchange"""
    key: str = ""
    secret: str = ""
    passphrase: str = ""

@dataclass
class ExchangeRateLimitConfig:
    """Configuration des rate limits"""
    requests_per_second: int = 10
    orders_per_second: int = 5
    websocket_connections: int = 5
    websocket_subscriptions: int = 100

@dataclass
class ExchangeOptionsConfig:
    """Options d'un exchange"""
    use_spot: bool = True
    use_futures: bool = False
    use_margin: bool = False
    use_options: bool = False
    use_swap: bool = False
    use_linear: bool = False
    use_inverse: bool = False

@dataclass
class ExchangeFeeConfig:
    """Configuration des frais"""
    maker: float = 0.001
    taker: float = 0.001
    futures_maker: float = 0.0002
    futures_taker: float = 0.0004
    discount: float = 0.0
    discount_asset: str = ""

@dataclass
class ExchangeSecurityConfig:
    """Configuration sécurité"""
    withdraw_whitelist: bool = False
    ip_whitelist: bool = False
    api_key_permissions: List[str] = field(default_factory=list)

@dataclass
class ExchangeConfig:
    """Configuration complète d'un exchange"""
    enabled: bool = False
    name: str = ""
    type: str = "cex"
    website: str = ""
    description: str = ""
    priority: int = 1
    tier: str = "standard"
    production_ready: bool = False
    
    api: ExchangeAPIConfig = field(default_factory=ExchangeAPIConfig)
    endpoints: Dict[str, str] = field(default_factory=dict)
    rate_limits: ExchangeRateLimitConfig = field(default_factory=ExchangeRateLimitConfig)
    options: ExchangeOptionsConfig = field(default_factory=ExchangeOptionsConfig)
    trading_pairs: Dict[str, List[str]] = field(default_factory=dict)
    fee: ExchangeFeeConfig = field(default_factory=ExchangeFeeConfig)
    min_order_size: Dict[str, float] = field(default_factory=dict)
    lot_size: Dict[str, float] = field(default_factory=dict)
    quote_precision: Dict[str, int] = field(default_factory=dict)
    base_precision: Dict[str, int] = field(default_factory=dict)
    security: ExchangeSecurityConfig = field(default_factory=ExchangeSecurityConfig)
    markets: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    websocket_streams: List[str] = field(default_factory=list)
    klines: Dict[str, Any] = field(default_factory=dict)
    maintenance: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StrategyPairConfig:
    """Configuration d'une paire de trading"""
    pair: str = ""
    min_profit: float = 0.01
    max_spread: float = 0.20
    min_volume: float = 1000
    max_position: float = 10000
    priority: int = 1
    exchanges: List[str] = field(default_factory=list)

@dataclass
class StrategyConfig:
    """Configuration d'une stratégie"""
    enabled: bool = False
    name: str = ""
    description: str = ""
    type: str = "arbitrage"
    priority: int = 1
    
    parameters: Dict[str, Any] = field(default_factory=dict)
    pairs: List[StrategyPairConfig] = field(default_factory=list)
    exchanges: Dict[str, Any] = field(default_factory=dict)
    risk: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    monitoring: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PositionSizingConfig:
    """Configuration du position sizing"""
    strategy: str = "adaptive"
    fixed_size: float = 1000
    max_position_size: float = 50000
    min_position_size: float = 100
    kelly_fraction: float = 0.25
    volatility_factor: float = 0.5
    adaptive_factor: float = 0.3

@dataclass
class StopLossConfig:
    """Configuration du stop loss"""
    enabled: bool = True
    type: str = "trailing"
    percentage: float = 0.02
    trailing_offset: float = 0.01
    min_trailing: float = 0.005
    max_trailing: float = 0.05
    dynamic_factor: float = 0.5

@dataclass
class TakeProfitConfig:
    """Configuration du take profit"""
    enabled: bool = True
    type: str = "multiple"
    targets: List[float] = field(default_factory=lambda: [0.01, 0.02, 0.03])
    allocation: List[float] = field(default_factory=lambda: [0.33, 0.33, 0.34])
    trailing_activation: float = 0.015

@dataclass
class CircuitBreakerConfig:
    """Configuration du circuit breaker"""
    enabled: bool = True
    consecutive_failures: int = 5
    failure_window: int = 60
    cooldown_period: int = 300
    max_failures_per_hour: int = 20
    max_failures_per_day: int = 100

@dataclass
class DrawdownProtectionConfig:
    """Configuration de la protection contre les drawdowns"""
    enabled: bool = True
    max_drawdown_daily: float = 0.05
    max_drawdown_weekly: float = 0.10
    max_drawdown_monthly: float = 0.15
    action: str = "reduce"
    reduce_factor: float = 0.5
    recovery_threshold: float = 0.03

@dataclass
class RiskManagementConfig:
    """Configuration complète de la gestion des risques"""
    enabled: bool = True
    max_drawdown: float = 0.15
    daily_loss_limit: float = 0.05
    weekly_loss_limit: float = 0.10
    max_positions: int = 10
    max_positions_per_pair: int = 3
    max_positions_per_exchange: int = 5
    
    position_sizing: PositionSizingConfig = field(default_factory=PositionSizingConfig)
    stop_loss: StopLossConfig = field(default_factory=StopLossConfig)
    take_profit: TakeProfitConfig = field(default_factory=TakeProfitConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    drawdown_protection: DrawdownProtectionConfig = field(default_factory=DrawdownProtectionConfig)

@dataclass
class ExecutionConfig:
    """Configuration de l'exécution"""
    enabled: bool = True
    mode: str = "smart"
    order_types: List[str] = field(default_factory=lambda: ["market", "limit"])
    order_routing: Dict[str, Any] = field(default_factory=dict)
    batch_execution: Dict[str, Any] = field(default_factory=dict)
    timeout: Dict[str, int] = field(default_factory=dict)
    retry: Dict[str, Any] = field(default_factory=dict)
    validation: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MarketDataConfig:
    """Configuration des données de marché"""
    enabled: bool = True
    source: str = "aggregated"
    providers: List[str] = field(default_factory=list)
    tickers: Dict[str, Any] = field(default_factory=dict)
    order_book: Dict[str, Any] = field(default_factory=dict)
    candles: Dict[str, Any] = field(default_factory=dict)
    websocket: Dict[str, Any] = field(default_factory=dict)
    quality: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MetricsConfig:
    """Configuration des métriques"""
    enabled: bool = True
    collection_interval: int = 10
    retention: int = 86400
    aggregation_interval: int = 60
    metrics: List[str] = field(default_factory=list)
    reporting: Dict[str, Any] = field(default_factory=dict)
    alerts: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LoggingOutputConfig:
    """Configuration d'un output de logging"""
    type: str = "console"
    enabled: bool = True
    path: str = ""
    max_size: int = 10485760
    max_files: int = 10
    format: str = "json"
    compress: bool = False
    colorize: bool = False

@dataclass
class LoggingConfig:
    """Configuration du logging"""
    enabled: bool = True
    level: str = "info"
    format: str = "json"
    colorize: bool = False
    outputs: List[LoggingOutputConfig] = field(default_factory=list)
    fields: Dict[str, str] = field(default_factory=dict)
    filters: List[str] = field(default_factory=list)

@dataclass
class DatabaseConfig:
    """Configuration de la base de données"""
    enabled: bool = False
    type: str = "postgres"
    host: str = "localhost"
    port: int = 5432
    name: str = "nexus_arbitrage"
    user: str = "postgres"
    password: str = ""
    pool_size: int = 5
    max_overflow: int = 10
    timeout: int = 15
    pool_recycle: int = 3600
    pool_pre_ping: bool = False
    ssl: Dict[str, Any] = field(default_factory=dict)
    backups: Dict[str, Any] = field(default_factory=dict)
    migrations: Dict[str, Any] = field(default_factory=dict)
    queries: Dict[str, Any] = field(default_factory=dict)
    timescaledb: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CacheConfig:
    """Configuration du cache"""
    enabled: bool = False
    type: str = "memory"
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    pool: Dict[str, int] = field(default_factory=dict)
    ttl: Dict[str, int] = field(default_factory=dict)
    compression: Dict[str, Any] = field(default_factory=dict)
    invalidation: Dict[str, Any] = field(default_factory=dict)
    monitoring: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NotificationChannelConfig:
    """Configuration d'un canal de notification"""
    enabled: bool = False
    name: str = ""
    type: str = ""
    priority: int = 1
    config: Dict[str, Any] = field(default_factory=dict)
    templates: Dict[str, str] = field(default_factory=dict)

@dataclass
class NotificationConfig:
    """Configuration des notifications"""
    enabled: bool = False
    default_channel: str = "telegram"
    timezone: str = "UTC"
    locale: str = "en_US"
    max_retry: int = 3
    retry_delay: int = 5
    queue_size: int = 1000
    batch_size: int = 10
    flush_interval: int = 5
    deduplication: Dict[str, Any] = field(default_factory=dict)
    channels: Dict[str, NotificationChannelConfig] = field(default_factory=dict)
    events: Dict[str, Any] = field(default_factory=dict)
    rules: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)

@dataclass
class APIConfig:
    """Configuration de l'API"""
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    prefix: str = "/api/v1"
    workers: int = 1
    reload: bool = False
    cors: Dict[str, Any] = field(default_factory=dict)
    rate_limit: Dict[str, Any] = field(default_factory=dict)
    authentication: Dict[str, Any] = field(default_factory=dict)
    documentation: Dict[str, Any] = field(default_factory=dict)
    debug_endpoints: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WebSocketConfig:
    """Configuration du WebSocket"""
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8001
    path: str = "/ws"
    max_connections: int = 100
    max_message_size: int = 1048576
    ping_interval: int = 30
    ping_timeout: int = 10
    max_pong_latency: int = 20
    authentication: Dict[str, Any] = field(default_factory=dict)
    channels: List[str] = field(default_factory=list)
    compression: Dict[str, Any] = field(default_factory=dict)
    monitoring: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MonitoringConfig:
    """Configuration du monitoring"""
    enabled: bool = False
    prometheus: Dict[str, Any] = field(default_factory=dict)
    grafana: Dict[str, Any] = field(default_factory=dict)
    health_check: Dict[str, Any] = field(default_factory=dict)
    alerts: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SchedulerJobConfig:
    """Configuration d'un job du scheduler"""
    name: str = ""
    enabled: bool = False
    interval: int = 60
    schedule: str = ""
    timeout: int = 60
    max_retries: int = 3
    priority: int = 1
    description: str = ""

@dataclass
class SchedulerConfig:
    """Configuration du scheduler"""
    enabled: bool = False
    timezone: str = "UTC"
    max_workers: int = 5
    thread_pool: int = 10
    jobs: List[SchedulerJobConfig] = field(default_factory=list)

@dataclass
class SecurityConfig:
    """Configuration de la sécurité"""
    enabled: bool = False
    encryption: Dict[str, Any] = field(default_factory=dict)
    api_keys: Dict[str, Any] = field(default_factory=dict)
    ip_whitelist: Dict[str, Any] = field(default_factory=dict)
    user_agent: Dict[str, Any] = field(default_factory=dict)
    rate_limiting: Dict[str, Any] = field(default_factory=dict)
    ssl: Dict[str, Any] = field(default_factory=dict)
    audit: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComplianceConfig:
    """Configuration de la conformité"""
    enabled: bool = False
    regulations: List[str] = field(default_factory=list)
    reporting: Dict[str, Any] = field(default_factory=dict)
    audit: Dict[str, Any] = field(default_factory=dict)
    limits: Dict[str, float] = field(default_factory=dict)

@dataclass
class DevelopmentConfig:
    """Configuration de développement"""
    enabled: bool = True
    mock_data: bool = True
    simulate_latency: bool = True
    simulate_errors: bool = True
    simulate_market_conditions: bool = False
    error_rate: float = 0.05
    latency_min: int = 10
    latency_max: int = 100
    hot_reload: bool = True
    debug_endpoints: bool = False
    verbose_logging: bool = True
    trace_logging: bool = False
    profile_code: bool = False
    test_mode: bool = True
    fake_orders: bool = True
    fake_balances: bool = True
    fake_market_data: bool = True
    profiling: Dict[str, Any] = field(default_factory=dict)
    testing: Dict[str, Any] = field(default_factory=dict)
    sandbox: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FullConfig:
    """Configuration complète du bot"""
    bot: BotConfig = field(default_factory=BotConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)
    exchanges: Dict[str, ExchangeConfig] = field(default_factory=dict)
    strategies: Dict[str, StrategyConfig] = field(default_factory=dict)
    risk_management: RiskManagementConfig = field(default_factory=RiskManagementConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    api: APIConfig = field(default_factory=APIConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    development: DevelopmentConfig = field(default_factory=DevelopmentConfig)

# ============================================================
# CONFIGURATION LOADER
# ============================================================

class ConfigLoader:
    """Chargeur de configuration"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config: Optional[FullConfig] = None
        self.env = os.environ.get("NEXUS_ENV", "production")
        self.config_dir = Path(__file__).parent
        self._loaded_files = []
        
    def load(self) -> FullConfig:
        """Charge la configuration complète"""
        if self.config_path:
            config_file = Path(self.config_path)
            if not config_file.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
            self.config = self._load_file(config_file)
        else:
            self.config = self._load_default_config()
        
        # Appliquer les overrides d'environnement
        self._apply_env_overrides()
        
        # Valider la configuration
        self._validate_config()
        
        return self.config
    
    def _load_default_config(self) -> FullConfig:
        """Charge la configuration par défaut"""
        # Charger le fichier par défaut
        default_file = self.config_dir / "default_config.yaml"
        if default_file.exists():
            return self._load_file(default_file)
        return FullConfig()
    
    def _load_file(self, file_path: Path) -> FullConfig:
        """Charge un fichier de configuration"""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        self._loaded_files.append(str(file_path))
        
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif file_path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        # Convertir en dataclass
        return self._dict_to_dataclass(data)
    
    def _dict_to_dataclass(self, data: Dict[str, Any]) -> FullConfig:
        """Convertit un dictionnaire en dataclass"""
        # Configurer les exchanges
        exchanges = {}
        if 'exchanges' in data:
            for name, exchange_data in data['exchanges'].items():
                exchanges[name] = self._dict_to_exchange_config(exchange_data)
        
        # Configurer les stratégies
        strategies = {}
        if 'strategies' in data:
            for name, strategy_data in data['strategies'].items():
                strategies[name] = self._dict_to_strategy_config(strategy_data)
        
        # Créer la configuration complète
        config = FullConfig(
            bot=self._dict_to_bot_config(data.get('bot', {})),
            general=self._dict_to_general_config(data.get('general', {})),
            exchanges=exchanges,
            strategies=strategies,
            risk_management=self._dict_to_risk_config(data.get('risk_management', {})),
            execution=self._dict_to_execution_config(data.get('execution', {})),
            market_data=self._dict_to_market_data_config(data.get('market_data', {})),
            metrics=self._dict_to_metrics_config(data.get('metrics', {})),
            logging=self._dict_to_logging_config(data.get('logging', {})),
            database=self._dict_to_database_config(data.get('database', {})),
            cache=self._dict_to_cache_config(data.get('cache', {})),
            notifications=self._dict_to_notification_config(data.get('notifications', {})),
            api=self._dict_to_api_config(data.get('api', {})),
            websocket=self._dict_to_websocket_config(data.get('websocket', {})),
            monitoring=self._dict_to_monitoring_config(data.get('monitoring', {})),
            scheduler=self._dict_to_scheduler_config(data.get('scheduler', {})),
            security=self._dict_to_security_config(data.get('security', {})),
            compliance=self._dict_to_compliance_config(data.get('compliance', {})),
            development=self._dict_to_development_config(data.get('development', {}))
        )
        
        return config
    
    def _dict_to_bot_config(self, data: Dict[str, Any]) -> BotConfig:
        """Convertit en BotConfig"""
        return BotConfig(**{k: v for k, v in data.items() if k in BotConfig.__annotations__})
    
    def _dict_to_general_config(self, data: Dict[str, Any]) -> GeneralConfig:
        """Convertit en GeneralConfig"""
        return GeneralConfig(**{k: v for k, v in data.items() if k in GeneralConfig.__annotations__})
    
    def _dict_to_exchange_config(self, data: Dict[str, Any]) -> ExchangeConfig:
        """Convertit en ExchangeConfig"""
        config = ExchangeConfig()
        
        for key, value in data.items():
            if key == 'api':
                config.api = ExchangeAPIConfig(**value)
            elif key == 'rate_limits':
                config.rate_limits = ExchangeRateLimitConfig(**value)
            elif key == 'options':
                config.options = ExchangeOptionsConfig(**value)
            elif key == 'fee':
                config.fee = ExchangeFeeConfig(**value)
            elif key == 'security':
                config.security = ExchangeSecurityConfig(**value)
            elif hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _dict_to_strategy_config(self, data: Dict[str, Any]) -> StrategyConfig:
        """Convertit en StrategyConfig"""
        config = StrategyConfig()
        
        for key, value in data.items():
            if key == 'pairs':
                config.pairs = [StrategyPairConfig(**p) for p in value]
            elif hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _dict_to_risk_config(self, data: Dict[str, Any]) -> RiskManagementConfig:
        """Convertit en RiskManagementConfig"""
        config = RiskManagementConfig()
        
        for key, value in data.items():
            if key == 'position_sizing':
                config.position_sizing = PositionSizingConfig(**value)
            elif key == 'stop_loss':
                config.stop_loss = StopLossConfig(**value)
            elif key == 'take_profit':
                config.take_profit = TakeProfitConfig(**value)
            elif key == 'circuit_breaker':
                config.circuit_breaker = CircuitBreakerConfig(**value)
            elif key == 'drawdown_protection':
                config.drawdown_protection = DrawdownProtectionConfig(**value)
            elif hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _dict_to_execution_config(self, data: Dict[str, Any]) -> ExecutionConfig:
        """Convertit en ExecutionConfig"""
        return ExecutionConfig(**{k: v for k, v in data.items() if k in ExecutionConfig.__annotations__})
    
    def _dict_to_market_data_config(self, data: Dict[str, Any]) -> MarketDataConfig:
        """Convertit en MarketDataConfig"""
        return MarketDataConfig(**{k: v for k, v in data.items() if k in MarketDataConfig.__annotations__})
    
    def _dict_to_metrics_config(self, data: Dict[str, Any]) -> MetricsConfig:
        """Convertit en MetricsConfig"""
        return MetricsConfig(**{k: v for k, v in data.items() if k in MetricsConfig.__annotations__})
    
    def _dict_to_logging_config(self, data: Dict[str, Any]) -> LoggingConfig:
        """Convertit en LoggingConfig"""
        config = LoggingConfig()
        
        for key, value in data.items():
            if key == 'outputs':
                config.outputs = [LoggingOutputConfig(**o) for o in value]
            elif hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _dict_to_database_config(self, data: Dict[str, Any]) -> DatabaseConfig:
        """Convertit en DatabaseConfig"""
        return DatabaseConfig(**{k: v for k, v in data.items() if k in DatabaseConfig.__annotations__})
    
    def _dict_to_cache_config(self, data: Dict[str, Any]) -> CacheConfig:
        """Convertit en CacheConfig"""
        return CacheConfig(**{k: v for k, v in data.items() if k in CacheConfig.__annotations__})
    
    def _dict_to_notification_config(self, data: Dict[str, Any]) -> NotificationConfig:
        """Convertit en NotificationConfig"""
        config = NotificationConfig()
        
        for key, value in data.items():
            if key == 'channels':
                config.channels = {
                    name: NotificationChannelConfig(**channel_data)
                    for name, channel_data in value.items()
                }
            elif hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _dict_to_api_config(self, data: Dict[str, Any]) -> APIConfig:
        """Convertit en APIConfig"""
        return APIConfig(**{k: v for k, v in data.items() if k in APIConfig.__annotations__})
    
    def _dict_to_websocket_config(self, data: Dict[str, Any]) -> WebSocketConfig:
        """Convertit en WebSocketConfig"""
        return WebSocketConfig(**{k: v for k, v in data.items() if k in WebSocketConfig.__annotations__})
    
    def _dict_to_monitoring_config(self, data: Dict[str, Any]) -> MonitoringConfig:
        """Convertit en MonitoringConfig"""
        return MonitoringConfig(**{k: v for k, v in data.items() if k in MonitoringConfig.__annotations__})
    
    def _dict_to_scheduler_config(self, data: Dict[str, Any]) -> SchedulerConfig:
        """Convertit en SchedulerConfig"""
        config = SchedulerConfig()
        
        for key, value in data.items():
            if key == 'jobs':
                config.jobs = [SchedulerJobConfig(**j) for j in value]
            elif hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def _dict_to_security_config(self, data: Dict[str, Any]) -> SecurityConfig:
        """Convertit en SecurityConfig"""
        return SecurityConfig(**{k: v for k, v in data.items() if k in SecurityConfig.__annotations__})
    
    def _dict_to_compliance_config(self, data: Dict[str, Any]) -> ComplianceConfig:
        """Convertit en ComplianceConfig"""
        return ComplianceConfig(**{k: v for k, v in data.items() if k in ComplianceConfig.__annotations__})
    
    def _dict_to_development_config(self, data: Dict[str, Any]) -> DevelopmentConfig:
        """Convertit en DevelopmentConfig"""
        return DevelopmentConfig(**{k: v for k, v in data.items() if k in DevelopmentConfig.__annotations__})
    
    def _apply_env_overrides(self):
        """Applique les overrides via variables d'environnement"""
        if not self.config:
            return
        
        # Override général
        if os.getenv("NEXUS_ENV"):
            self.config.bot.environment = os.getenv("NEXUS_ENV")
        
        if os.getenv("NEXUS_LOG_LEVEL"):
            self.config.general.log_level = os.getenv("NEXUS_LOG_LEVEL")
        
        if os.getenv("NEXUS_DEBUG"):
            self.config.general.debug = os.getenv("NEXUS_DEBUG").lower() == "true"
        
        # Override base de données
        if os.getenv("DB_HOST"):
            self.config.database.host = os.getenv("DB_HOST")
        if os.getenv("DB_PORT"):
            self.config.database.port = int(os.getenv("DB_PORT"))
        if os.getenv("DB_NAME"):
            self.config.database.name = os.getenv("DB_NAME")
        if os.getenv("DB_USER"):
            self.config.database.user = os.getenv("DB_USER")
        if os.getenv("DB_PASSWORD"):
            self.config.database.password = os.getenv("DB_PASSWORD")
        
        # Override Redis
        if os.getenv("REDIS_HOST"):
            self.config.cache.host = os.getenv("REDIS_HOST")
        if os.getenv("REDIS_PORT"):
            self.config.cache.port = int(os.getenv("REDIS_PORT"))
        if os.getenv("REDIS_PASSWORD"):
            self.config.cache.password = os.getenv("REDIS_PASSWORD")
        
        # Override API
        if os.getenv("API_HOST"):
            self.config.api.host = os.getenv("API_HOST")
        if os.getenv("API_PORT"):
            self.config.api.port = int(os.getenv("API_PORT"))
    
    def _validate_config(self):
        """Valide la configuration"""
        if not self.config:
            raise ValueError("Configuration not loaded")
        
        # Vérifier que les clés API ne sont pas vides en production
        if self.config.bot.environment == Environment.PRODUCTION.value:
            for name, exchange in self.config.exchanges.items():
                if exchange.enabled:
                    if not exchange.api.key:
                        raise ValueError(f"API key missing for exchange: {name}")
                    if not exchange.api.secret:
                        raise ValueError(f"API secret missing for exchange: {name}")
        
        # Vérifier qu'au moins une stratégie est activée
        if self.config.general.enabled:
            has_enabled_strategy = any(
                strategy.enabled for strategy in self.config.strategies.values()
            )
            if not has_enabled_strategy:
                logger.warning("No strategy is enabled")
        
        logger.info(f"Configuration validated successfully from {len(self._loaded_files)} files")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la configuration en dictionnaire"""
        if not self.config:
            return {}
        return asdict(self.config)
    
    def to_json(self) -> str:
        """Convertit la configuration en JSON"""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def to_yaml(self) -> str:
        """Convertit la configuration en YAML"""
        return yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)
    
    def save(self, file_path: str):
        """Sauvegarde la configuration dans un fichier"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            if path.suffix in ['.yaml', '.yml']:
                f.write(self.to_yaml())
            elif path.suffix == '.json':
                f.write(self.to_json())
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")
        
        logger.info(f"Configuration saved to: {file_path}")

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_config_loader: Optional[ConfigLoader] = None

def get_config(config_path: Optional[str] = None) -> FullConfig:
    """Récupère la configuration (singleton)"""
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader(config_path)
    
    if _config_loader.config is None:
        _config_loader.load()
    
    return _config_loader.config

def reload_config(config_path: Optional[str] = None) -> FullConfig:
    """Recharge la configuration"""
    global _config_loader
    
    _config_loader = ConfigLoader(config_path)
    return _config_loader.load()

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'Environment',
    'LogLevel',
    'StrategyType',
    'ExchangeType',
    'RiskLevel',
    
    # Data Classes
    'BotConfig',
    'GeneralConfig',
    'ExchangeConfig',
    'ExchangeAPIConfig',
    'ExchangeRateLimitConfig',
    'ExchangeOptionsConfig',
    'ExchangeFeeConfig',
    'ExchangeSecurityConfig',
    'StrategyConfig',
    'StrategyPairConfig',
    'RiskManagementConfig',
    'PositionSizingConfig',
    'StopLossConfig',
    'TakeProfitConfig',
    'CircuitBreakerConfig',
    'DrawdownProtectionConfig',
    'ExecutionConfig',
    'MarketDataConfig',
    'MetricsConfig',
    'LoggingConfig',
    'LoggingOutputConfig',
    'DatabaseConfig',
    'CacheConfig',
    'NotificationConfig',
    'NotificationChannelConfig',
    'APIConfig',
    'WebSocketConfig',
    'MonitoringConfig',
    'SchedulerConfig',
    'SchedulerJobConfig',
    'SecurityConfig',
    'ComplianceConfig',
    'DevelopmentConfig',
    'FullConfig',
    
    # Classes
    'ConfigLoader',
    
    # Functions
    'get_config',
    'reload_config',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Configuration module initialized")

# trading/bots/hedge_bot/config/__init__.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Configuration Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Hedge Bot Configuration Module

This module provides comprehensive configuration management for the NEXUS Hedge Bot.
It loads and manages all configuration files for the hedge bot system,
including strategy parameters, risk limits, exchange settings, and more.

The configuration system supports:
- YAML configuration files
- Environment variable overrides
- Dynamic configuration updates
- Configuration validation
- Multi-environment support (development, staging, production, demo)
- Hot reloading
- Configuration versioning
- Schema validation
- Secret management integration
- Configuration change tracking
- Distributed configuration support
"""

import os
import sys
import yaml
import json
import logging
import hashlib
import inspect
from typing import Dict, Any, Optional, List, Union, Callable, TypeVar, Generic, Set
from pathlib import Path
from dataclasses import dataclass, field, asdict, fields
from functools import lru_cache, wraps
from datetime import datetime, timedelta
from enum import Enum
import threading
import re
from collections.abc import MutableMapping
from contextlib import contextmanager
import warnings

# Try to import optional dependencies
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

try:
    from pydantic import BaseModel, Field, validator, root_validator, ValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

from ...core.logging import LoggerManager
from ...core.exceptions import ConfigurationError
from ...core.utils import deep_merge, safe_get, safe_set

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS AND CONFIGURATION
# ============================================================

CONFIG_DIR = Path(__file__).parent
CONFIG_VERSION = "2.0.0"
CONFIG_SCHEMA_VERSION = "2.0.0"

# Configuration file mapping
CONFIG_FILES = {
    "accounting": "accounting_configs.yaml",
    "asset": "asset_configs.yaml",
    "audit": "audit_configs.yaml",
    "backup": "backup_configs.yaml",
    "beta": "beta_configs.yaml",
    "billing": "billing_configs.yaml",
    "breakeven": "breakeven_configs.yaml",
    "collateral": "collateral_configs.yaml",
    "compliance": "compliance_configs.yaml",
    "concentration": "concentration_configs.yaml",
    "correlation": "correlation_configs.yaml",
    "default": "default_config.yaml",
    "delta": "delta_configs.yaml",
    "development": "development_config.yaml",
    "diversification": "diversification_configs.yaml",
    "drawdown": "drawdown_configs.yaml",
    "emergency": "emergency_configs.yaml",
    "exposure": "exposure_configs.yaml",
    "futures": "futures_configs.yaml",
    "gamma": "gamma_configs.yaml",
    "hedge": "hedge_config.yaml",
    "invoicing": "invoicing_configs.yaml",
    "leverage": "leverage_configs.yaml",
    "liquidation": "liquidation_configs.yaml",
    "margin": "margin_configs.yaml",
    "options": "options_configs.yaml",
    "payment": "payment_configs.yaml",
    "perpetual": "perpetual_configs.yaml",
    "position_sizing": "position_sizing_configs.yaml",
    "pricing": "pricing_configs.yaml",
    "production": "production_config.yaml",
    "profit_target": "profit_target_configs.yaml",
    "recovery": "recovery_configs.yaml",
    "regulatory": "regulatory_configs.yaml",
    "risk": "risk_configs.yaml",
    "risk_reward": "risk_reward_configs.yaml",
    "scenario": "scenario_configs.yaml",
    "sensitivity": "sensitivity_configs.yaml",
    "stop_loss": "stop_loss_configs.yaml",
    "strategy": "strategy_configs.yaml",
    "subscription": "subscription_configs.yaml",
    "take_profit": "take_profit_configs.yaml",
    "tax": "tax_configs.yaml",
    "theta": "theta_configs.yaml",
    "trailing_stop": "trailing_stop_configs.yaml",
    "vega": "vega_configs.yaml",
    "volatility": "volatility_configs.yaml",
}

# Environment variable mapping with nested key support
ENV_MAPPING = {
    # Bot Configuration
    "NEXUS_ENVIRONMENT": "bot.environment",
    "NEXUS_LOG_LEVEL": "bot.log_level",
    "NEXUS_DEBUG_MODE": "bot.debug_mode",
    "NEXUS_BOT_ENABLED": "bot.enabled",
    "NEXUS_BOT_ACTIVE": "bot.active",
    "NEXUS_BOT_VERSION": "bot.version",
    
    # Exchange Configuration
    "NEXUS_EXCHANGE_NAME": "exchange.name",
    "NEXUS_EXCHANGE_TYPE": "exchange.type",
    "NEXUS_EXCHANGE_SANDBOX": "exchange.sandbox",
    "NEXUS_EXCHANGE_API_KEY": "exchange.api.key",
    "NEXUS_EXCHANGE_API_SECRET": "exchange.api.secret",
    "NEXUS_EXCHANGE_API_PASSPHRASE": "exchange.api.passphrase",
    "NEXUS_EXCHANGE_TIMEOUT": "exchange.api.timeout",
    "NEXUS_EXCHANGE_RETRY_ATTEMPTS": "exchange.api.retry_attempts",
    "NEXUS_EXCHANGE_RATE_LIMIT": "exchange.api.rate_limit",
    
    # Database Configuration
    "NEXUS_DATABASE_HOST": "data.storage.database.host",
    "NEXUS_DATABASE_PORT": "data.storage.database.port",
    "NEXUS_DATABASE_NAME": "data.storage.database.database",
    "NEXUS_DATABASE_USER": "data.storage.database.username",
    "NEXUS_DATABASE_PASSWORD": "data.storage.database.password",
    "NEXUS_DATABASE_SSL": "data.storage.database.ssl",
    "NEXUS_DATABASE_POOL_SIZE": "data.storage.database.pool_size",
    
    # Redis Configuration
    "NEXUS_REDIS_HOST": "data.storage.cache.host",
    "NEXUS_REDIS_PORT": "data.storage.cache.port",
    "NEXUS_REDIS_PASSWORD": "data.storage.cache.password",
    "NEXUS_REDIS_DB": "data.storage.cache.db",
    "NEXUS_REDIS_SSL": "data.storage.cache.ssl",
    "NEXUS_REDIS_POOL_SIZE": "data.storage.cache.pool_size",
    
    # Notification Configuration
    "NEXUS_SLACK_WEBHOOK_URL": "notifications.channels.slack.webhook_url",
    "NEXUS_TELEGRAM_BOT_TOKEN": "notifications.channels.telegram.bot_token",
    "NEXUS_TELEGRAM_CHAT_ID": "notifications.channels.telegram.chat_id",
    "NEXUS_EMAIL_USERNAME": "notifications.channels.email.username",
    "NEXUS_EMAIL_PASSWORD": "notifications.channels.email.password",
    "NEXUS_EMAIL_SMTP_SERVER": "notifications.channels.email.smtp_server",
    "NEXUS_EMAIL_SMTP_PORT": "notifications.channels.email.smtp_port",
    "NEXUS_PUSH_APP_ID": "notifications.channels.push.app_id",
    "NEXUS_PUSH_API_KEY": "notifications.channels.push.api_key",
    "NEXUS_PAGERDUTY_INTEGRATION_KEY": "notifications.channels.pagerduty.integration_key",
    
    # Payment Configuration
    "NEXUS_STRIPE_API_KEY": "payment.gateways.stripe.api_key",
    "NEXUS_STRIPE_WEBHOOK_SECRET": "payment.gateways.stripe.webhook_secret",
    "NEXUS_PAYPAL_CLIENT_ID": "payment.gateways.paypal.client_id",
    "NEXUS_PAYPAL_CLIENT_SECRET": "payment.gateways.paypal.client_secret",
    "NEXUS_PAYPAL_WEBHOOK_ID": "payment.gateways.paypal.webhook_id",
    "NEXUS_COINBASE_API_KEY": "payment.gateways.coinbase.api_key",
    "NEXUS_COINBASE_WEBHOOK_SECRET": "payment.gateways.coinbase.webhook_secret",
    
    # Cloud Storage Configuration
    "NEXUS_AWS_ACCESS_KEY": "backup.storage.aws.access_key",
    "NEXUS_AWS_SECRET_KEY": "backup.storage.aws.secret_key",
    "NEXUS_AWS_REGION": "backup.storage.aws.region",
    "NEXUS_AWS_BUCKET": "backup.storage.aws.bucket_name",
    "NEXUS_GCP_PROJECT_ID": "backup.storage.gcp.project_id",
    "NEXUS_GCP_CREDENTIALS": "backup.storage.gcp.credentials",
    "NEXUS_AZURE_ACCOUNT_NAME": "backup.storage.azure.account_name",
    "NEXUS_AZURE_ACCOUNT_KEY": "backup.storage.azure.account_key",
    
    # AI/ML Configuration
    "NEXUS_MODEL_PATH": "ai_ml.config.model_path",
    "NEXUS_MODEL_TYPE": "ai_ml.config.model_type",
    "NEXUS_INFERENCE_BATCH_SIZE": "ai_ml.config.inference_batch_size",
    "NEXUS_PREDICTION_HORIZON": "ai_ml.config.prediction_horizon",
    "NEXUS_CONFIDENCE_THRESHOLD": "ai_ml.config.confidence_threshold",
    "NEXUS_USE_GPU": "ai_ml.config.use_gpu",
    "NEXUS_USE_CUDA": "ai_ml.config.use_cuda",
    
    # Logging Configuration
    "NEXUS_LOG_FILE": "logging.files.main_log",
    "NEXUS_LOG_LEVEL": "logging.config.log_level",
    "NEXUS_LOG_FORMAT": "logging.config.log_format",
    "NEXUS_LOG_ROTATION": "logging.config.log_rotation",
    "NEXUS_LOG_COMPRESSION": "logging.config.log_compression",
    "NEXUS_LOG_RETENTION_DAYS": "logging.config.retention_days",
    
    # Trading Configuration
    "NEXUS_MAX_POSITIONS": "trading.position.max_positions",
    "NEXUS_MAX_LEVERAGE": "trading.position.max_leverage",
    "NEXUS_TARGET_HEDGE_RATIO": "trading.position.target_hedge_ratio",
    "NEXUS_MIN_HEDGE_RATIO": "trading.position.min_hedge_ratio",
    "NEXUS_MAX_HEDGE_RATIO": "trading.position.max_hedge_ratio",
    "NEXUS_MAX_ORDER_SIZE": "trading.order.max_order_size",
    "NEXUS_MIN_ORDER_SIZE": "trading.order.min_order_size",
    "NEXUS_SLIPPAGE_TOLERANCE": "trading.order.slippage_tolerance",
    
    # Risk Configuration
    "NEXUS_MAX_DRAWDOWN": "risk_management.limits.max_drawdown",
    "NEXUS_DAILY_LOSS_LIMIT": "risk_management.limits.daily_loss_limit",
    "NEXUS_WEEKLY_LOSS_LIMIT": "risk_management.limits.weekly_loss_limit",
    "NEXUS_MONTHLY_LOSS_LIMIT": "risk_management.limits.monthly_loss_limit",
    "NEXUS_MAX_CORRELATION": "risk_management.limits.max_correlation",
    "NEXUS_MAX_EXPOSURE": "risk_management.limits.max_exposure",
    "NEXUS_MAX_RISK_PER_TRADE": "risk_management.limits.max_risk_per_trade",
    
    # Monitoring Configuration
    "NEXUS_MONITORING_ENABLED": "monitoring.config.enabled",
    "NEXUS_MONITORING_FREQUENCY": "monitoring.config.monitoring_frequency",
    "NEXUS_HEALTH_CHECK_INTERVAL": "monitoring.health.check_interval",
    "NEXUS_AUTO_RECOVERY": "monitoring.health.auto_recovery",
    "NEXUS_MAX_FAILURES": "monitoring.health.max_failures",
    "NEXUS_RECOVERY_TIMEOUT": "monitoring.health.recovery_timeout",
    
    # Security Configuration
    "NEXUS_SECURITY_ENABLED": "security.enabled",
    "NEXUS_ENCRYPTION_METHOD": "security.encryption_method",
    "NEXUS_KEY_ROTATION_DAYS": "security.key_rotation_days",
    "NEXUS_TOKEN_EXPIRY": "security.auth.token_expiry",
    "NEXUS_REFRESH_TOKEN_EXPIRY": "security.auth.refresh_token_expiry",
    "NEXUS_RATE_LIMITING": "security.api.rate_limiting",
    "NEXUS_MAX_REQUESTS_PER_MINUTE": "security.api.max_requests_per_minute",
    "NEXUS_API_KEY_ROTATION": "security.api.api_key_rotation",
    
    # Backup Configuration
    "NEXUS_BACKUP_ENABLED": "backup.enabled",
    "NEXUS_BACKUP_SCHEDULE": "backup.schedule",
    "NEXUS_BACKUP_TIME": "backup.time",
    "NEXUS_BACKUP_RETENTION_DAYS": "backup.retention_days",
    "NEXUS_BACKUP_COMPRESSION": "backup.compression",
    "NEXUS_BACKUP_ENCRYPTION": "backup.encryption",
    
    # Performance Configuration
    "NEXUS_MAX_WORKERS": "performance.max_workers",
    "NEXUS_BATCH_SIZE": "performance.batch_size",
    "NEXUS_QUEUE_SIZE": "performance.queue_size",
    "NEXUS_USE_ASYNC": "performance.use_async",
    "NEXUS_USE_CACHING": "performance.use_caching",
    "NEXUS_CACHE_TTL": "performance.cache_ttl",
    "NEXUS_MAX_MEMORY_MB": "performance.resources.max_memory_mb",
    "NEXUS_MAX_CPU_CORES": "performance.resources.max_cpu_cores",
    "NEXUS_MAX_CONCURRENT_TRADES": "performance.resources.max_concurrent_trades",
    "NEXUS_MAX_ORDER_RATE": "performance.resources.max_order_rate",
    
    # Compliance Configuration
    "NEXUS_COMPLIANCE_ENABLED": "compliance.enabled",
    "NEXUS_REGULATORY_FRAMEWORK": "compliance.regulatory_framework",
    "NEXUS_COMPLIANCE_LEVEL": "compliance.compliance_level",
    "NEXUS_AUTO_REMEDIATION": "compliance.auto_remediation",
    "NEXUS_AUDIT_TRAIL": "compliance.audit_trail",
    
    # Portfolio Configuration
    "NEXUS_PORTFOLIO_CURRENCY": "portfolio.currency",
    "NEXUS_PORTFOLIO_INITIAL_BALANCE": "portfolio.initial_balance",
    "NEXUS_PORTFOLIO_MAX_SINGLE_ASSET": "portfolio.allocation.max_single_asset",
    "NEXUS_PORTFOLIO_MAX_SECTOR": "portfolio.allocation.max_sector",
    "NEXUS_PORTFOLIO_MAX_ASSET_CLASS": "portfolio.allocation.max_asset_class",
    "NEXUS_PORTFOLIO_MIN_ASSETS": "portfolio.allocation.min_assets",
    "NEXUS_PORTFOLIO_TARGET_ASSETS": "portfolio.allocation.target_assets",
    "NEXUS_PORTFOLIO_REBALANCE_FREQUENCY": "portfolio.allocation.rebalance_frequency",
    "NEXUS_PORTFOLIO_REBALANCE_THRESHOLD": "portfolio.allocation.rebalance_threshold",
}

# ============================================================
# ENUMS AND TYPES
# ============================================================

class Environment(Enum):
    """Valid environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DEMO = "demo"
    TESTING = "testing"
    
    @classmethod
    def from_string(cls, value: str) -> "Environment":
        """Create enum from string"""
        value = value.lower()
        for env in cls:
            if env.value == value:
                return env
        raise ValueError(f"Invalid environment: {value}")


class ConfigSource(Enum):
    """Configuration source types"""
    FILE = "file"
    ENV = "environment"
    DEFAULT = "default"
    USER = "user"
    SYSTEM = "system"
    REMOTE = "remote"
    MEMORY = "memory"


class ConfigChangeType(Enum):
    """Configuration change types"""
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"
    REPLACE = "replace"


# ============================================================
# PYDANTIC MODELS (if available)
# ============================================================

if HAS_PYDANTIC:
    class BotConfigModel(BaseModel):
        """Bot configuration model"""
        id: str = "nexus_hedge_bot"
        name: str = "NEXUS Hedge Bot"
        version: str = "2.0.0"
        description: str = "Advanced hedging bot for portfolio protection"
        enabled: bool = True
        active: bool = True
        environment: str = "development"
        mode: str = "automatic"
        debug_mode: bool = False
        log_level: str = "INFO"
        
        @validator("environment")
        def validate_environment(cls, v: str) -> str:
            """Validate environment"""
            valid = ["development", "staging", "production", "demo", "testing"]
            if v not in valid:
                raise ValueError(f"Invalid environment: {v}. Must be one of {valid}")
            return v
        
        @validator("log_level")
        def validate_log_level(cls, v: str) -> str:
            """Validate log level"""
            valid = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if v not in valid:
                raise ValueError(f"Invalid log level: {v}. Must be one of {valid}")
            return v
    
    class ExchangeConfigModel(BaseModel):
        """Exchange configuration model"""
        name: str = "binance"
        type: str = "spot"
        sandbox: bool = True
        testnet: bool = False
        api: Dict[str, Any] = Field(default_factory=lambda: {
            "key": "",
            "secret": "",
            "passphrase": "",
            "timeout": 30,
            "retry_attempts": 3,
            "rate_limit": 1200,
            "use_hmac": True,
            "use_signing": True,
        })
        settings: Dict[str, Any] = Field(default_factory=lambda: {
            "use_mock_data": False,
            "use_websocket": True,
            "websocket_reconnect": True,
            "websocket_timeout": 30,
        })
        pairs: List[str] = Field(default_factory=lambda: [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOT/USDT"
        ])
        
        @validator("name")
        def validate_exchange(cls, v: str) -> str:
            """Validate exchange name"""
            valid = ["binance", "bybit", "coinbase", "kraken", "okx", "deribit"]
            if v not in valid:
                raise ValueError(f"Invalid exchange: {v}. Must be one of {valid}")
            return v
        
        @validator("type")
        def validate_exchange_type(cls, v: str) -> str:
            """Validate exchange type"""
            valid = ["spot", "futures", "perpetual", "options"]
            if v not in valid:
                raise ValueError(f"Invalid exchange type: {v}. Must be one of {valid}")
            return v
    
    class RiskConfigModel(BaseModel):
        """Risk management configuration model"""
        enabled: bool = True
        risk_level: str = "moderate"
        max_risk_per_trade: float = 0.02
        max_risk_per_day: float = 0.05
        max_risk_per_month: float = 0.15
        position_sizing: Dict[str, Any] = Field(default_factory=lambda: {
            "method": "risk_based",
            "risk_per_trade": 0.01,
            "max_position_size": 10000,
            "min_position_size": 100,
            "use_correlation_adj": True,
            "use_volatility_adj": True,
            "kelly_fraction": 0.25,
        })
        limits: Dict[str, Any] = Field(default_factory=lambda: {
            "max_drawdown": 0.15,
            "daily_loss_limit": 0.05,
            "weekly_loss_limit": 0.10,
            "monthly_loss_limit": 0.15,
            "max_correlation": 0.70,
            "max_leverage": 3.0,
            "max_exposure": 1000000,
            "max_position_size": 10000,
        })
        
        @validator("risk_level")
        def validate_risk_level(cls, v: str) -> str:
            """Validate risk level"""
            valid = ["conservative", "moderate", "aggressive", "extreme"]
            if v not in valid:
                raise ValueError(f"Invalid risk level: {v}. Must be one of {valid}")
            return v


# ============================================================
# CONFIGURATION DATACLASSES
# ============================================================

@dataclass
class ConfigChange:
    """Configuration change record"""
    key: str
    old_value: Any
    new_value: Any
    change_type: ConfigChangeType
    source: ConfigSource
    timestamp: datetime = field(default_factory=datetime.now)
    user: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class ConfigVersion:
    """Configuration version record"""
    version: str
    hash: str
    timestamp: datetime = field(default_factory=datetime.now)
    changes: List[ConfigChange] = field(default_factory=list)
    snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigMetadata:
    """Configuration metadata"""
    version: str = CONFIG_VERSION
    schema_version: str = CONFIG_SCHEMA_VERSION
    environment: str = "development"
    loaded_at: datetime = field(default_factory=datetime.now)
    loaded_from: List[str] = field(default_factory=list)
    sources: Dict[str, ConfigSource] = field(default_factory=dict)
    hash: str = ""
    size: int = 0


@dataclass
class HedgeBotConfig:
    """
    Main Hedge Bot Configuration
    
    This dataclass holds all configuration for the hedge bot.
    It provides methods for accessing, modifying, and validating configuration.
    """
    
    # Version and Metadata
    version: str = CONFIG_VERSION
    metadata: ConfigMetadata = field(default_factory=ConfigMetadata)
    
    # Core Configuration
    bot: Dict[str, Any] = field(default_factory=dict)
    exchange: Dict[str, Any] = field(default_factory=dict)
    trading: Dict[str, Any] = field(default_factory=dict)
    
    # Strategy Configuration
    hedge_strategy: Dict[str, Any] = field(default_factory=dict)
    hedging_strategies: Dict[str, Any] = field(default_factory=dict)
    directional_strategies: Dict[str, Any] = field(default_factory=dict)
    arbitrage_strategies: Dict[str, Any] = field(default_factory=dict)
    risk_management_strategies: Dict[str, Any] = field(default_factory=dict)
    strategy_execution: Dict[str, Any] = field(default_factory=dict)
    strategy_optimization: Dict[str, Any] = field(default_factory=dict)
    strategy_performance: Dict[str, Any] = field(default_factory=dict)
    
    # Risk Management
    risk_management: Dict[str, Any] = field(default_factory=dict)
    risk_limits: Dict[str, Any] = field(default_factory=dict)
    risk_monitoring: Dict[str, Any] = field(default_factory=dict)
    
    # Portfolio Management
    portfolio: Dict[str, Any] = field(default_factory=dict)
    allocation: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)
    
    # Data Configuration
    data: Dict[str, Any] = field(default_factory=dict)
    data_sources: Dict[str, Any] = field(default_factory=dict)
    data_storage: Dict[str, Any] = field(default_factory=dict)
    data_quality: Dict[str, Any] = field(default_factory=dict)
    
    # AI/ML Configuration
    ai_ml: Dict[str, Any] = field(default_factory=dict)
    training: Dict[str, Any] = field(default_factory=dict)
    prediction: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, Any] = field(default_factory=dict)
    
    # Monitoring & Logging
    monitoring: Dict[str, Any] = field(default_factory=dict)
    logging: Dict[str, Any] = field(default_factory=dict)
    
    # Security & Compliance
    security: Dict[str, Any] = field(default_factory=dict)
    compliance: Dict[str, Any] = field(default_factory=dict)
    
    # Notifications
    notifications: Dict[str, Any] = field(default_factory=dict)
    
    # Backup & Recovery
    backup: Dict[str, Any] = field(default_factory=dict)
    recovery: Dict[str, Any] = field(default_factory=dict)
    
    # Performance
    performance: Dict[str, Any] = field(default_factory=dict)
    
    # Environment-specific overrides
    environments: Dict[str, Any] = field(default_factory=dict)
    
    # Change Tracking
    _changes: List[ConfigChange] = field(default_factory=list, repr=False)
    _versions: List[ConfigVersion] = field(default_factory=list, repr=False)
    _subscribers: List[Callable] = field(default_factory=list, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    
    def __post_init__(self):
        """Initialize metadata"""
        if not self.metadata:
            self.metadata = ConfigMetadata()
        self.metadata.version = self.version
        self.metadata.environment = self.bot.get("environment", "development")
        
        # Calculate initial hash
        self._update_hash()
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "HedgeBotConfig":
        """Create configuration from dictionary"""
        return cls(
            version=config_dict.get("version", CONFIG_VERSION),
            bot=config_dict.get("bot", {}),
            exchange=config_dict.get("exchange", {}),
            trading=config_dict.get("trading", {}),
            hedge_strategy=config_dict.get("hedge_strategy", {}),
            hedging_strategies=config_dict.get("hedging_strategies", {}),
            directional_strategies=config_dict.get("directional_strategies", {}),
            arbitrage_strategies=config_dict.get("arbitrage_strategies", {}),
            risk_management_strategies=config_dict.get("risk_management_strategies", {}),
            strategy_execution=config_dict.get("strategy_execution", {}),
            strategy_optimization=config_dict.get("strategy_optimization", {}),
            strategy_performance=config_dict.get("strategy_performance", {}),
            risk_management=config_dict.get("risk_management", {}),
            risk_limits=config_dict.get("risk_limits", {}),
            risk_monitoring=config_dict.get("risk_monitoring", {}),
            portfolio=config_dict.get("portfolio", {}),
            allocation=config_dict.get("allocation", {}),
            performance=config_dict.get("performance", {}),
            data=config_dict.get("data", {}),
            data_sources=config_dict.get("data_sources", {}),
            data_storage=config_dict.get("data_storage", {}),
            data_quality=config_dict.get("data_quality", {}),
            ai_ml=config_dict.get("ai_ml", {}),
            training=config_dict.get("training", {}),
            prediction=config_dict.get("prediction", {}),
            features=config_dict.get("features", {}),
            monitoring=config_dict.get("monitoring", {}),
            logging=config_dict.get("logging", {}),
            security=config_dict.get("security", {}),
            compliance=config_dict.get("compliance", {}),
            notifications=config_dict.get("notifications", {}),
            backup=config_dict.get("backup", {}),
            recovery=config_dict.get("recovery", {}),
            performance=config_dict.get("performance", {}),
            environments=config_dict.get("environments", {}),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "version": self.version,
            "bot": self.bot,
            "exchange": self.exchange,
            "trading": self.trading,
            "hedge_strategy": self.hedge_strategy,
            "hedging_strategies": self.hedging_strategies,
            "directional_strategies": self.directional_strategies,
            "arbitrage_strategies": self.arbitrage_strategies,
            "risk_management_strategies": self.risk_management_strategies,
            "strategy_execution": self.strategy_execution,
            "strategy_optimization": self.strategy_optimization,
            "strategy_performance": self.strategy_performance,
            "risk_management": self.risk_management,
            "risk_limits": self.risk_limits,
            "risk_monitoring": self.risk_monitoring,
            "portfolio": self.portfolio,
            "allocation": self.allocation,
            "performance": self.performance,
            "data": self.data,
            "data_sources": self.data_sources,
            "data_storage": self.data_storage,
            "data_quality": self.data_quality,
            "ai_ml": self.ai_ml,
            "training": self.training,
            "prediction": self.prediction,
            "features": self.features,
            "monitoring": self.monitoring,
            "logging": self.logging,
            "security": self.security,
            "compliance": self.compliance,
            "notifications": self.notifications,
            "backup": self.backup,
            "recovery": self.recovery,
            "performance": self.performance,
            "environments": self.environments,
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot notation key
        
        Args:
            key: Dot notation key (e.g., "bot.environment")
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        with self._lock:
            return safe_get(self.to_dict(), key, default)
    
    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.USER,
            reason: Optional[str] = None) -> None:
        """
        Set configuration value by dot notation key
        
        Args:
            key: Dot notation key (e.g., "bot.environment")
            value: Value to set
            source: Source of the change
            reason: Reason for the change
        """
        with self._lock:
            old_value = self.get(key)
            config_dict = self.to_dict()
            safe_set(config_dict, key, value)
            
            # Record change
            change = ConfigChange(
                key=key,
                old_value=old_value,
                new_value=value,
                change_type=ConfigChangeType.MODIFY if old_value is not None else ConfigChangeType.ADD,
                source=source,
                reason=reason
            )
            self._changes.append(change)
            
            # Update metadata
            self._update_hash()
            
            # Notify subscribers
            self._notify_subscribers(change)
    
    def delete(self, key: str, source: ConfigSource = ConfigSource.USER,
               reason: Optional[str] = None) -> None:
        """
        Delete configuration value by dot notation key
        
        Args:
            key: Dot notation key (e.g., "bot.environment")
            source: Source of the change
            reason: Reason for the change
        """
        with self._lock:
            old_value = self.get(key)
            config_dict = self.to_dict()
            keys = key.split(".")
            target = config_dict
            for k in keys[:-1]:
                if k not in target:
                    return
                target = target[k]
            if keys[-1] in target:
                del target[keys[-1]]
            
            # Record change
            change = ConfigChange(
                key=key,
                old_value=old_value,
                new_value=None,
                change_type=ConfigChangeType.DELETE,
                source=source,
                reason=reason
            )
            self._changes.append(change)
            
            # Update metadata
            self._update_hash()
            
            # Notify subscribers
            self._notify_subscribers(change)
    
    def subscribe(self, callback: Callable[[ConfigChange], None]) -> None:
        """Subscribe to configuration changes"""
        with self._lock:
            self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[ConfigChange], None]) -> None:
        """Unsubscribe from configuration changes"""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)
    
    def _notify_subscribers(self, change: ConfigChange) -> None:
        """Notify subscribers of configuration change"""
        for callback in self._subscribers:
            try:
                callback(change)
            except Exception as e:
                logger.error(f"Error in config subscriber: {e}")
    
    def _update_hash(self) -> None:
        """Update configuration hash"""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        self.metadata.hash = hashlib.sha256(config_str.encode()).hexdigest()
        self.metadata.size = len(config_str)
    
    def get_hash(self) -> str:
        """Get current configuration hash"""
        return self.metadata.hash
    
    def get_changes(self, limit: Optional[int] = None) -> List[ConfigChange]:
        """Get configuration changes"""
        with self._lock:
            changes = self._changes.copy()
            if limit is not None:
                changes = changes[-limit:]
            return changes
    
    def get_version(self) -> Optional[ConfigVersion]:
        """Get latest configuration version"""
        with self._lock:
            if self._versions:
                return self._versions[-1]
            return None
    
    def save_version(self, reason: Optional[str] = None) -> ConfigVersion:
        """Save current configuration as a version"""
        with self._lock:
            version = ConfigVersion(
                version=f"{self.version}.{len(self._versions) + 1}",
                hash=self.get_hash(),
                snapshot=self.to_dict(),
                changes=self._changes.copy()
            )
            self._versions.append(version)
            return version
    
    def rollback(self, version: Union[int, str]) -> bool:
        """
        Rollback to a previous configuration version
        
        Args:
            version: Version number (int) or version string
            
        Returns:
            bool: True if rollback was successful
        """
        with self._lock:
            if isinstance(version, str):
                # Find version by string
                for v in self._versions:
                    if v.version == version:
                        target_version = v
                        break
                else:
                    return False
            else:
                if version < 0 or version >= len(self._versions):
                    return False
                target_version = self._versions[version]
            
            # Apply snapshot
            for key, value in target_version.snapshot.items():
                safe_set(self, key, value)
            
            # Record rollback change
            change = ConfigChange(
                key="*",
                old_value=None,
                new_value=None,
                change_type=ConfigChangeType.REPLACE,
                source=ConfigSource.SYSTEM,
                reason=f"Rollback to version {target_version.version}"
            )
            self._changes.append(change)
            self._update_hash()
            self._notify_subscribers(change)
            
            return True
    
    def validate(self, schema: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Validate configuration against schema
        
        Args:
            schema: JSON schema to validate against
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Basic validation
        if not self.bot:
            errors.append("Missing 'bot' configuration")
        if not self.exchange:
            errors.append("Missing 'exchange' configuration")
        if not self.trading:
            errors.append("Missing 'trading' configuration")
        if not self.risk_management:
            errors.append("Missing 'risk_management' configuration")
        
        # Environment validation
        environment = self.bot.get("environment", "development")
        valid_environments = ["development", "staging", "production", "demo", "testing"]
        if environment not in valid_environments:
            errors.append(f"Invalid environment: {environment}")
        
        # Exchange validation
        exchange = self.exchange.get("name", "binance")
        valid_exchanges = ["binance", "bybit", "coinbase", "kraken", "okx", "deribit"]
        if exchange not in valid_exchanges:
            errors.append(f"Invalid exchange: {exchange}")
        
        # Leverage validation
        leverage = self.trading.get("position", {}).get("max_leverage", 1.0)
        if leverage < 1.0 or leverage > 10.0:
            errors.append(f"Invalid max_leverage: {leverage}")
        
        # Drawdown validation
        drawdown = self.risk_management.get("limits", {}).get("max_drawdown", 0.15)
        if drawdown < 0 or drawdown > 1.0:
            errors.append(f"Invalid max_drawdown: {drawdown}")
        
        # Schema validation if schema provided
        if schema and HAS_JSONSCHEMA:
            try:
                jsonschema.validate(self.to_dict(), schema)
            except jsonschema.ValidationError as e:
                errors.append(str(e))
        
        # Pydantic validation if available
        if HAS_PYDANTIC:
            try:
                # Validate bot config
                BotConfigModel(**self.bot)
                # Validate exchange config
                ExchangeConfigModel(**self.exchange)
                # Validate risk config
                RiskConfigModel(**self.risk_management)
            except ValidationError as e:
                errors.extend([str(err) for err in e.errors()])
        
        return errors
    
    def get_config_for_environment(self, environment: str) -> Dict[str, Any]:
        """Get configuration merged with environment-specific overrides"""
        config_dict = self.to_dict()
        env_overrides = self.environments.get(environment, {})
        return deep_merge(config_dict, env_overrides)
    
    def export(self, format: str = "json") -> str:
        """Export configuration in specified format"""
        config_dict = self.to_dict()
        if format == "json":
            return json.dumps(config_dict, indent=2, default=str)
        elif format == "yaml":
            return yaml.dump(config_dict, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    @classmethod
    def import_config(cls, data: str, format: str = "json") -> "HedgeBotConfig":
        """Import configuration from string"""
        if format == "json":
            config_dict = json.loads(data)
        elif format == "yaml":
            config_dict = yaml.safe_load(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
        return cls.from_dict(config_dict)


# ============================================================
# CONFIGURATION LOADER
# ============================================================

class HedgeBotConfigLoader:
    """
    Hedge Bot Configuration Loader
    
    Loads and manages all configuration files for the hedge bot.
    Supports YAML files, environment variables, and dynamic updates.
    """
    
    _instance = None
    _config: Optional[HedgeBotConfig] = None
    _loaded_files: List[str] = []
    _file_watchers: Dict[str, datetime] = {}
    _load_time: Optional[datetime] = None
    _lock: threading.RLock = threading.RLock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self._config = None
        self._loaded_files = []
        self._file_watchers = {}
        self._load_time = None
        self._config_dir = CONFIG_DIR
        self._loaded_hashes: Dict[str, str] = {}
        self._listeners: List[Callable] = []
        self._config_version = CONFIG_VERSION
        self._schema = None
        
        # Load .env file if available
        if HAS_DOTENV:
            load_dotenv()
    
    def load(self, environment: str = "development") -> HedgeBotConfig:
        """
        Load configuration for the specified environment
        
        Args:
            environment: Environment name (development, staging, production, demo, testing)
            
        Returns:
            HedgeBotConfig: Loaded configuration
            
        Raises:
            ConfigurationError: If configuration fails to load
        """
        logger.info(f"Loading hedge bot configuration for environment: {environment}")
        
        with self._lock:
            try:
                # Load base configuration
                base_config = self._load_base_config()
                
                # Load environment-specific configuration
                env_config = self._load_environment_config(environment)
                
                # Merge configurations
                merged_config = deep_merge(base_config, env_config)
                
                # Load additional configuration files
                merged_config = self._load_additional_configs(merged_config)
                
                # Apply environment variable overrides
                merged_config = self._apply_env_overrides(merged_config)
                
                # Validate configuration
                self._validate_config(merged_config)
                
                # Create config object
                self._config = HedgeBotConfig.from_dict(merged_config)
                self._config.metadata.environment = environment
                self._config.metadata.loaded_at = datetime.now()
                self._config.metadata.loaded_from = self._loaded_files.copy()
                
                # Track loaded files
                for file_path in self._loaded_files:
                    if file_path:
                        self._file_watchers[file_path] = datetime.now()
                
                # Update load time
                self._load_time = datetime.now()
                
                logger.info(f"Configuration loaded successfully. Loaded files: {self._loaded_files}")
                
                return self._config
                
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                raise ConfigurationError(f"Failed to load configuration: {e}") from e
    
    def _load_base_config(self) -> Dict[str, Any]:
        """Load base configuration from default_config.yaml"""
        config = {}
        config_path = self._config_dir / "default_config.yaml"
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f) or {}
                    self._loaded_files.append(str(config_path))
                    self._loaded_hashes[str(config_path)] = self._calculate_file_hash(config_path)
                    logger.debug(f"Loaded base config from: {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load base config from {config_path}: {e}")
        else:
            logger.warning(f"Base config file not found: {config_path}")
        
        return config
    
    def _load_environment_config(self, environment: str) -> Dict[str, Any]:
        """Load environment-specific configuration"""
        config = {}
        env_file = f"{environment}_config.yaml"
        config_path = self._config_dir / env_file
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f) or {}
                    self._loaded_files.append(str(config_path))
                    self._loaded_hashes[str(config_path)] = self._calculate_file_hash(config_path)
                    logger.debug(f"Loaded environment config from: {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load environment config from {config_path}: {e}")
        else:
            logger.warning(f"Environment config file not found: {config_path}")
        
        return config
    
    def _load_additional_configs(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Load additional configuration files"""
        config = base_config
        excluded_files = ["default_config.yaml", "development_config.yaml", 
                         "staging_config.yaml", "production_config.yaml", "demo_config.yaml"]
        
        for config_name, file_name in CONFIG_FILES.items():
            if config_name in ["default", "development", "staging", "production", "demo"]:
                continue
            
            config_path = self._config_dir / file_name
            if config_path.exists():
                try:
                    with open(config_path, "r") as f:
                        file_config = yaml.safe_load(f) or {}
                        config = deep_merge(config, file_config)
                        self._loaded_files.append(str(config_path))
                        self._loaded_hashes[str(config_path)] = self._calculate_file_hash(config_path)
                        logger.debug(f"Loaded additional config from: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return config
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration"""
        for env_var, config_path in ENV_MAPPING.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Parse value (handle booleans, numbers, lists, dicts)
                parsed_value = self._parse_env_value(value)
                safe_set(config, config_path, parsed_value)
                logger.debug(f"Applied env override: {env_var} -> {config_path} = {parsed_value}")
        
        return config
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value"""
        # Boolean values
        if value.lower() in ["true", "1", "yes", "on", "enabled", "active"]:
            return True
        if value.lower() in ["false", "0", "no", "off", "disabled", "inactive"]:
            return False
        
        # Numeric values
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # JSON values
        if value.startswith("{") or value.startswith("["):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # String values
        return value
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate file hash for change detection"""
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration"""
        errors = []
        
        # Required fields
        required_fields = [
            "bot",
            "exchange",
            "trading",
            "risk_management",
            "portfolio",
            "data",
            "logging",
        ]
        
        for field in required_fields:
            if field not in config:
                errors.append(f"Required configuration field missing: {field}")
                logger.warning(f"Required configuration field missing: {field}")
        
        # Validate environment
        environment = config.get("bot", {}).get("environment", "development")
        valid_environments = ["development", "staging", "production", "demo", "testing"]
        if environment not in valid_environments:
            logger.warning(f"Invalid environment: {environment}. Using default.")
            if "bot" not in config:
                config["bot"] = {}
            config["bot"]["environment"] = "development"
        
        # Validate exchange
        exchange = config.get("exchange", {}).get("name", "binance")
        valid_exchanges = ["binance", "bybit", "coinbase", "kraken", "okx", "deribit"]
        if exchange not in valid_exchanges:
            logger.warning(f"Invalid exchange: {exchange}. Using default (binance).")
            if "exchange" not in config:
                config["exchange"] = {}
            config["exchange"]["name"] = "binance"
        
        # Validate leverage
        leverage = config.get("trading", {}).get("position", {}).get("max_leverage", 1.0)
        if leverage < 1.0 or leverage > 10.0:
            logger.warning(f"Invalid max_leverage: {leverage}. Using default (1.0).")
            if "trading" not in config:
                config["trading"] = {}
            if "position" not in config["trading"]:
                config["trading"]["position"] = {}
            config["trading"]["position"]["max_leverage"] = 1.0
        
        # Validate drawdown
        drawdown = config.get("risk_management", {}).get("limits", {}).get("max_drawdown", 0.15)
        if drawdown < 0 or drawdown > 1.0:
            logger.warning(f"Invalid max_drawdown: {drawdown}. Using default (0.15).")
            if "risk_management" not in config:
                config["risk_management"] = {}
            if "limits" not in config["risk_management"]:
                config["risk_management"]["limits"] = {}
            config["risk_management"]["limits"]["max_drawdown"] = 0.15
        
        if errors:
            logger.warning(f"Configuration validation found {len(errors)} issues")
        
        logger.debug("Configuration validation completed")
    
    @lru_cache(maxsize=1)
    def get_config(self) -> HedgeBotConfig:
        """Get cached configuration"""
        with self._lock:
            if self._config is None:
                environment = os.environ.get("NEXUS_ENVIRONMENT", "development")
                self.load(environment)
            return self._config
    
    def reload(self) -> HedgeBotConfig:
        """Reload configuration"""
        with self._lock:
            self._config = None
            self._loaded_files = []
            self._loaded_hashes = {}
            self._load_time = None
            environment = os.environ.get("NEXUS_ENVIRONMENT", "development")
            return self.load(environment)
    
    def reload_if_changed(self) -> Optional[HedgeBotConfig]:
        """Reload configuration if any file has changed"""
        with self._lock:
            changed = False
            
            # Check if any loaded file has changed
            for file_path in self._loaded_files:
                if file_path:
                    path = Path(file_path)
                    if path.exists():
                        current_hash = self._calculate_file_hash(path)
                        old_hash = self._loaded_hashes.get(file_path, "")
                        if current_hash != old_hash:
                            changed = True
                            logger.info(f"Configuration file changed: {file_path}")
                            break
            
            # Also check if new files are available
            for config_name, file_name in CONFIG_FILES.items():
                config_path = self._config_dir / file_name
                if config_path.exists():
                    file_str = str(config_path)
                    if file_str not in self._loaded_files:
                        changed = True
                        logger.info(f"New configuration file detected: {file_str}")
                        break
            
            if changed:
                logger.info("Configuration changed, reloading...")
                return self.reload()
            
            return self._config
    
    def get_loaded_files(self) -> List[str]:
        """Get list of loaded configuration files"""
        return self._loaded_files
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key"""
        config = self.get_config()
        return config.get(key, default)
    
    def set_config_value(self, key: str, value: Any, reason: Optional[str] = None) -> None:
        """Set configuration value and save"""
        config = self.get_config()
        config.set(key, value, source=ConfigSource.USER, reason=reason)
        self._save_config_changes()
    
    def _save_config_changes(self) -> None:
        """Save configuration changes to file"""
        # This would save changes back to the config file
        # Implementation would depend on the deployment environment
        logger.debug("Configuration changes saved")
    
    def add_listener(self, callback: Callable[[ConfigChange], None]) -> None:
        """Add configuration change listener"""
        self._listeners.append(callback)
        config = self.get_config()
        config.subscribe(callback)
    
    def remove_listener(self, callback: Callable[[ConfigChange], None]) -> None:
        """Remove configuration change listener"""
        if callback in self._listeners:
            self._listeners.remove(callback)
        config = self.get_config()
        config.unsubscribe(callback)
    
    def get_load_time(self) -> Optional[datetime]:
        """Get configuration load time"""
        return self._load_time
    
    def get_config_version(self) -> str:
        """Get configuration version"""
        return self._config_version
    
    def get_environment(self) -> str:
        """Get current environment"""
        config = self.get_config()
        return config.bot.get("environment", "development")


# ============================================================
# CONFIGURATION SCHEMA
# ============================================================

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "bot": {"type": "object"},
        "exchange": {"type": "object"},
        "trading": {"type": "object"},
        "hedge_strategy": {"type": "object"},
        "risk_management": {"type": "object"},
        "portfolio": {"type": "object"},
        "data": {"type": "object"},
        "ai_ml": {"type": "object"},
        "monitoring": {"type": "object"},
        "logging": {"type": "object"},
        "security": {"type": "object"},
        "compliance": {"type": "object"},
        "notifications": {"type": "object"},
        "backup": {"type": "object"},
        "recovery": {"type": "object"},
        "performance": {"type": "object"},
        "environments": {"type": "object"},
    },
    "required": ["bot", "exchange", "trading", "risk_management", "portfolio", "data", "logging"],
    "additionalProperties": True
}


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def load_hedge_bot_config(environment: str = "development") -> HedgeBotConfig:
    """
    Load hedge bot configuration
    
    Args:
        environment: Environment name
        
    Returns:
        HedgeBotConfig: Loaded configuration
    """
    loader = HedgeBotConfigLoader()
    return loader.load(environment)


def get_hedge_bot_config() -> HedgeBotConfig:
    """Get cached hedge bot configuration"""
    loader = HedgeBotConfigLoader()
    return loader.get_config()


def reload_hedge_bot_config() -> HedgeBotConfig:
    """Reload hedge bot configuration"""
    loader = HedgeBotConfigLoader()
    return loader.reload()


def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value by dot notation key"""
    loader = HedgeBotConfigLoader()
    return loader.get_config_value(key, default)


def set_config_value(key: str, value: Any, reason: Optional[str] = None) -> None:
    """Set configuration value"""
    loader = HedgeBotConfigLoader()
    loader.set_config_value(key, value, reason)


def get_exchange_config() -> Dict[str, Any]:
    """Get exchange configuration"""
    config = get_hedge_bot_config()
    return config.exchange


def get_trading_config() -> Dict[str, Any]:
    """Get trading configuration"""
    config = get_hedge_bot_config()
    return config.trading


def get_risk_config() -> Dict[str, Any]:
    """Get risk management configuration"""
    config = get_hedge_bot_config()
    return config.risk_management


def get_strategy_config(strategy_type: str = "hedge") -> Dict[str, Any]:
    """
    Get strategy configuration
    
    Args:
        strategy_type: Strategy type (hedge, directional, arbitrage, risk_management)
        
    Returns:
        Strategy configuration
    """
    config = get_hedge_bot_config()
    strategy_map = {
        "hedge": config.hedge_strategy,
        "hedging": config.hedging_strategies,
        "directional": config.directional_strategies,
        "arbitrage": config.arbitrage_strategies,
        "risk_management": config.risk_management_strategies,
    }
    return strategy_map.get(strategy_type, {})


def get_volatility_config() -> Dict[str, Any]:
    """Get volatility configuration"""
    config = get_hedge_bot_config()
    return config.get("volatility", {})


def get_environment() -> str:
    """Get current environment"""
    return get_config_value("bot.environment", "development")


def is_production() -> bool:
    """Check if running in production environment"""
    return get_environment() == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return get_environment() == "development"


def is_staging() -> bool:
    """Check if running in staging environment"""
    return get_environment() == "staging"


def is_demo() -> bool:
    """Check if running in demo environment"""
    return get_environment() == "demo"


def is_testing() -> bool:
    """Check if running in testing environment"""
    return get_environment() == "testing"


def get_config_path() -> Path:
    """Get configuration directory path"""
    return CONFIG_DIR


def get_config_schema() -> Dict[str, Any]:
    """Get configuration JSON schema"""
    return CONFIG_SCHEMA


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate configuration against schema
    
    Args:
        config: Configuration dictionary
        
    Returns:
        List of validation errors
    """
    temp_config = HedgeBotConfig.from_dict(config)
    return temp_config.validate(CONFIG_SCHEMA)


def export_config(format: str = "json") -> str:
    """Export current configuration"""
    config = get_hedge_bot_config()
    return config.export(format)


# ============================================================
# DECORATORS
# ============================================================

def with_config(func: Callable) -> Callable:
    """
    Decorator to inject configuration into function
    
    Usage:
        @with_config
        def my_function(config, *args, **kwargs):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        config = get_hedge_bot_config()
        return func(config, *args, **kwargs)
    return wrapper


def config_required(func: Callable) -> Callable:
    """
    Decorator to ensure configuration is loaded before function execution
    
    Usage:
        @config_required
        def my_function(*args, **kwargs):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        get_hedge_bot_config()  # Ensures config is loaded
        return func(*args, **kwargs)
    return wrapper


def on_config_change(func: Callable) -> Callable:
    """
    Decorator to register function as configuration change listener
    
    Usage:
        @on_config_change
        def my_change_handler(change):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        loader = HedgeBotConfigLoader()
        loader.add_listener(func)
        return func(*args, **kwargs)
    return wrapper


# ============================================================
# CONTEXT MANAGERS
# ============================================================

@contextmanager
def temp_config_override(key: str, value: Any):
    """
    Temporarily override configuration value
    
    Usage:
        with temp_config_override("bot.environment", "testing"):
            # Configuration is overridden within this block
            ...
    """
    config = get_hedge_bot_config()
    old_value = config.get(key)
    config.set(key, value, source=ConfigSource.SYSTEM, reason="Temporary override")
    try:
        yield
    finally:
        if old_value is not None:
            config.set(key, old_value, source=ConfigSource.SYSTEM, reason="Restore override")
        else:
            config.delete(key, source=ConfigSource.SYSTEM, reason="Remove override")


@contextmanager
def environment_context(environment: str):
    """
    Context manager to temporarily switch environment
    
    Usage:
        with environment_context("staging"):
            # Configuration is loaded from staging environment
            ...
    """
    old_env = os.environ.get("NEXUS_ENVIRONMENT", "development")
    os.environ["NEXUS_ENVIRONMENT"] = environment
    loader = HedgeBotConfigLoader()
    loader.reload()
    try:
        yield
    finally:
        os.environ["NEXUS_ENVIRONMENT"] = old_env
        loader.reload()


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "Environment",
    "ConfigSource",
    "ConfigChangeType",
    
    # Dataclasses
    "ConfigChange",
    "ConfigVersion",
    "ConfigMetadata",
    "HedgeBotConfig",
    
    # Classes
    "HedgeBotConfigLoader",
    
    # Pydantic models (if available)
    "BotConfigModel",
    "ExchangeConfigModel",
    "RiskConfigModel",
    
    # Convenience functions
    "load_hedge_bot_config",
    "get_hedge_bot_config",
    "reload_hedge_bot_config",
    "get_config_value",
    "set_config_value",
    "get_exchange_config",
    "get_trading_config",
    "get_risk_config",
    "get_strategy_config",
    "get_volatility_config",
    "get_environment",
    "is_production",
    "is_development",
    "is_staging",
    "is_demo",
    "is_testing",
    "get_config_path",
    "get_config_schema",
    "validate_config",
    "export_config",
    
    # Decorators
    "with_config",
    "config_required",
    "on_config_change",
    
    # Context managers
    "temp_config_override",
    "environment_context",
    
    # Constants
    "CONFIG_DIR",
    "CONFIG_FILES",
    "ENV_MAPPING",
    "CONFIG_VERSION",
    "CONFIG_SCHEMA_VERSION",
    "CONFIG_SCHEMA",
]

# ============================================================
# INITIALIZATION
# ============================================================

# Auto-load configuration on module import
try:
    _environment = os.environ.get("NEXUS_ENVIRONMENT", "development")
    _default_config = load_hedge_bot_config(_environment)
    logger.info(f"Hedge bot configuration auto-loaded successfully for environment: {_environment}")
except Exception as e:
    logger.error(f"Failed to auto-load hedge bot configuration: {e}")
    _default_config = None


# ============================================================
# END OF MODULE
# ============================================================

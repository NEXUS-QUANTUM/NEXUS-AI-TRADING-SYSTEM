# trading/bots/ai_bot/config/__init__.py
# NEXUS AI TRADING SYSTEM - Configuration Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Configuration Module for NEXUS AI Trading Bot.

This module provides comprehensive configuration management including:
- Configuration loading and parsing
- Environment-based configuration
- Configuration validation
- Configuration hot-reloading
- Secret management
- Configuration versioning
- Type-safe configuration access
- Configuration merging and overrides
- CLI configuration support
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

# Version
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Module logger
logger = logging.getLogger("nexus.trading.bot.config")

# ============================================================================
# Configuration Types
# ============================================================================

class ConfigMode(str, Enum):
    """Configuration modes."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class ConfigSource(str, Enum):
    """Configuration sources."""
    FILE = "file"
    ENVIRONMENT = "environment"
    COMMAND_LINE = "command_line"
    DEFAULT = "default"
    REMOTE = "remote"


# ============================================================================
# Configuration Dataclasses
# ============================================================================

@dataclass
class BotConfig:
    """Bot configuration."""
    name: str = "NEXUS AI Trading Bot"
    version: str = "3.0.0"
    enabled: bool = True
    mode: str = "paper"
    symbols: List[str] = field(default_factory=lambda: ["BTC-USD", "ETH-USD", "SOL-USD"])
    timeframe: str = "1h"
    initial_capital: float = 10000.0
    description: str = "Advanced AI-powered trading bot"


@dataclass
class TradingConfig:
    """Trading configuration."""
    max_positions: int = 5
    max_position_size: float = 1000.0
    min_position_size: float = 10.0
    max_leverage: float = 2.0
    default_order_type: str = "limit"
    default_time_in_force: str = "GTC"
    max_slippage: float = 0.005
    execution_timeout: int = 30
    symbols: Dict[str, List[str]] = field(default_factory=dict)
    schedule: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    active: str = "hybrid"
    min_confidence: float = 0.6
    position_sizing: str = "percentage"
    rebalance_threshold: float = 0.1
    enable_auto_compounding: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_drawdown: float = 0.10
    risk_per_trade: float = 0.02
    stop_loss: float = 0.02
    take_profit: float = 0.04
    trailing_stop: float = 0.015
    use_trailing_stop: bool = True
    max_risk_percent: float = 10.0
    max_risk_amount: float = 1000.0
    circuit_breakers: Dict[str, Any] = field(default_factory=dict)
    position_sizing: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelConfig:
    """AI model configuration."""
    active: List[str] = field(default_factory=lambda: ["lstm", "transformer", "xgboost", "ensemble"])
    min_confidence: float = 0.6
    retraining_frequency: str = "weekly"
    ensemble_weights: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataConfig:
    """Data configuration."""
    lookback_days: int = 365
    update_interval: int = 60
    cache_size: int = 1000
    max_history: int = 10000
    sources: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    enabled: bool = True
    interval: int = 60
    alert_thresholds: Dict[str, float] = field(default_factory=dict)
    health_checks: List[str] = field(default_factory=list)


@dataclass
class NotificationConfig:
    """Notification configuration."""
    enabled: bool = True
    channels: List[str] = field(default_factory=lambda: ["websocket", "telegram"])
    events: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIConfig:
    """API configuration."""
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    cors_enabled: bool = True
    rate_limit: Dict[str, Any] = field(default_factory=dict)
    auth: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    name: str = "nexus_trading"
    user: str = "nexus_user"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False
    ssl_mode: str = "prefer"


@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    decode_responses: bool = True
    max_connections: int = 20
    socket_timeout: int = 5


@dataclass
class StorageConfig:
    """Storage configuration."""
    local: Dict[str, Any] = field(default_factory=dict)
    cloud: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityConfig:
    """Security configuration."""
    encryption_enabled: bool = True
    encryption_key: str = ""
    jwt: Dict[str, Any] = field(default_factory=dict)
    ssl: Dict[str, Any] = field(default_factory=dict)
    cors: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FullConfig:
    """Complete configuration."""
    environment: str = "development"
    debug: bool = False
    test_mode: bool = False
    log_level: str = "INFO"
    
    bot: BotConfig = field(default_factory=BotConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    api: APIConfig = field(default_factory=APIConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    features: Dict[str, bool] = field(default_factory=dict)


# ============================================================================
# Configuration Manager
# ============================================================================

class ConfigManager:
    """
    Configuration Manager for NEXUS AI Trading Bot.
    Handles loading, parsing, and validating configurations.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Configuration directory path
        """
        self.config_dir = config_dir or Path(__file__).parent
        self._config: Optional[FullConfig] = None
        self._config_paths: Dict[str, Path] = {}
        self._loaded_sources: List[ConfigSource] = []
        self._watchers: List[Any] = []

        # Default config paths
        self._default_configs = {
            "default": self.config_dir / "default_config.yaml",
            "development": self.config_dir / "development_config.yaml",
            "staging": self.config_dir / "staging_config.yaml",
            "production": self.config_dir / "production_config.yaml",
            "testing": self.config_dir / "testing_config.yaml",
            "bot": self.config_dir / "bot_configs.yaml",
            "model": self.config_dir / "model_configs.yaml",
            "risk": self.config_dir / "risk_configs.yaml",
            "strategy": self.config_dir / "strategy_configs.yaml",
        }

        logger.info(f"ConfigManager initialized with config_dir: {self.config_dir}")

    # ========================================================================
    # Configuration Loading
    # ========================================================================

    def load_config(
        self,
        mode: Optional[ConfigMode] = None,
        config_path: Optional[Path] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> FullConfig:
        """
        Load configuration from files.

        Args:
            mode: Configuration mode
            config_path: Custom config file path
            overrides: Configuration overrides

        Returns:
            FullConfig instance
        """
        mode = mode or ConfigMode.DEVELOPMENT
        
        # Start with default config
        config_data = self._load_yaml(self._default_configs["default"])
        
        # Load environment-specific config
        env_config_path = self._default_configs.get(mode.value)
        if env_config_path and env_config_path.exists():
            env_data = self._load_yaml(env_config_path)
            config_data = self._merge_configs(config_data, env_data)
            self._loaded_sources.append(ConfigSource.FILE)

        # Load custom config if provided
        if config_path and config_path.exists():
            custom_data = self._load_yaml(config_path)
            config_data = self._merge_configs(config_data, custom_data)
            self._loaded_sources.append(ConfigSource.FILE)

        # Load environment variables
        env_data = self._load_environment()
        config_data = self._merge_configs(config_data, env_data)
        self._loaded_sources.append(ConfigSource.ENVIRONMENT)

        # Apply overrides
        if overrides:
            config_data = self._merge_configs(config_data, overrides)
            self._loaded_sources.append(ConfigSource.COMMAND_LINE)

        # Create config object
        self._config = self._parse_config(config_data)
        
        # Validate config
        self._validate_config(self._config)

        logger.info(f"Configuration loaded (mode: {mode.value}, sources: {[s.value for s in self._loaded_sources]})")
        return self._config

    def reload(self) -> Optional[FullConfig]:
        """
        Reload configuration from files.

        Returns:
            Reloaded FullConfig or None
        """
        if not self._config:
            return None

        logger.info("Reloading configuration...")
        return self.load_config(
            mode=ConfigMode(self._config.environment),
            overrides=self._get_current_overrides(),
        )

    # ========================================================================
    # Configuration Access
    # ========================================================================

    def get_config(self) -> Optional[FullConfig]:
        """Get the current configuration."""
        return self._config

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-notation path.

        Args:
            path: Dot-notation path (e.g., "bot.name")
            default: Default value if not found

        Returns:
            Configuration value
        """
        if not self._config:
            return default

        parts = path.split('.')
        value = self._config
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return default
                
        return value if value is not None else default

    def set(self, path: str, value: Any) -> bool:
        """
        Set a configuration value by dot-notation path.

        Args:
            path: Dot-notation path
            value: Value to set

        Returns:
            True if set successfully
        """
        if not self._config:
            return False

        parts = path.split('.')
        target = self._config
        
        for part in parts[:-1]:
            if isinstance(target, dict):
                if part not in target:
                    target[part] = {}
                target = target[part]
            elif hasattr(target, part):
                target = getattr(target, part)
            else:
                return False
                
        last_part = parts[-1]
        if isinstance(target, dict):
            target[last_part] = value
        elif hasattr(target, last_part):
            setattr(target, last_part, value)
        else:
            return False
            
        return True

    # ========================================================================
    # Configuration Saving
    # ========================================================================

    def save_config(self, path: Optional[Path] = None) -> bool:
        """
        Save configuration to file.

        Args:
            path: Output path

        Returns:
            True if saved successfully
        """
        if not self._config:
            return False

        path = path or self.config_dir / "config_export.yaml"
        
        try:
            config_data = self._serialize_config(self._config)
            with open(path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
            logger.info(f"Configuration saved to: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    # ========================================================================
    # Configuration Validation
    # ========================================================================

    def _validate_config(self, config: FullConfig) -> None:
        """
        Validate configuration.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If validation fails
        """
        errors = []

        # Validate bot configuration
        if not config.bot.name:
            errors.append("Bot name is required")
        if config.bot.initial_capital <= 0:
            errors.append("Initial capital must be positive")
        if not config.bot.symbols:
            errors.append("At least one symbol is required")

        # Validate trading configuration
        if config.trading.max_positions < 1:
            errors.append("max_positions must be at least 1")
        if config.trading.max_position_size <= 0:
            errors.append("max_position_size must be positive")
        if config.trading.max_slippage < 0 or config.trading.max_slippage > 1:
            errors.append("max_slippage must be between 0 and 1")

        # Validate risk configuration
        if config.risk.max_drawdown < 0 or config.risk.max_drawdown > 1:
            errors.append("max_drawdown must be between 0 and 1")
        if config.risk.risk_per_trade < 0 or config.risk.risk_per_trade > 1:
            errors.append("risk_per_trade must be between 0 and 1")
        if config.risk.stop_loss < 0 or config.risk.stop_loss > 1:
            errors.append("stop_loss must be between 0 and 1")

        # Validate model configuration
        if not config.models.active:
            errors.append("At least one model must be active")
        if config.models.min_confidence < 0 or config.models.min_confidence > 1:
            errors.append("min_confidence must be between 0 and 1")

        # Validate monitoring configuration
        if config.monitoring.interval < 1:
            errors.append("monitoring interval must be positive")

        # Validate API configuration
        if config.api.port < 1 or config.api.port > 65535:
            errors.append("API port must be between 1 and 65535")
        if config.api.workers < 1:
            errors.append("API workers must be at least 1")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """
        Load YAML file.

        Args:
            path: File path

        Returns:
            Dictionary of configuration data
        """
        try:
            if not path.exists():
                return {}
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading YAML from {path}: {e}")
            return {}

    def _load_environment(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.

        Returns:
            Dictionary of configuration data
        """
        config = {}
        prefix = "NEXUS_"
        
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
                
            # Remove prefix and convert to lowercase
            config_key = key[len(prefix):].lower()
            
            # Convert to nested dict
            parts = config_key.split('__')
            current = config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = self._parse_env_value(value)
            
        return config

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value."""
        # Boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
            
        # Number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
            
        # List
        if value.startswith('[') and value.endswith(']'):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
                
        return value

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two configuration dictionaries.

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged configuration
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
                
        return result

    def _parse_config(self, data: Dict[str, Any]) -> FullConfig:
        """
        Parse configuration data into FullConfig object.

        Args:
            data: Configuration data

        Returns:
            FullConfig instance
        """
        # Create config objects from data
        bot = BotConfig(**data.get('bot', {}))
        trading = TradingConfig(**data.get('trading', {}))
        strategy = StrategyConfig(**data.get('strategy', {}))
        risk = RiskConfig(**data.get('risk', {}))
        models = ModelConfig(**data.get('models', {}))
        data_config = DataConfig(**data.get('data', {}))
        monitoring = MonitoringConfig(**data.get('monitoring', {}))
        notifications = NotificationConfig(**data.get('notifications', {}))
        api = APIConfig(**data.get('api', {}))
        database = DatabaseConfig(**data.get('database', {}))
        redis = RedisConfig(**data.get('redis', {}))
        storage = StorageConfig(**data.get('storage', {}))
        security = SecurityConfig(**data.get('security', {}))
        features = data.get('features', {})

        return FullConfig(
            environment=data.get('environment', 'development'),
            debug=data.get('debug', False),
            test_mode=data.get('test_mode', False),
            log_level=data.get('log_level', 'INFO'),
            bot=bot,
            trading=trading,
            strategy=strategy,
            risk=risk,
            models=models,
            data=data_config,
            monitoring=monitoring,
            notifications=notifications,
            api=api,
            database=database,
            redis=redis,
            storage=storage,
            security=security,
            features=features,
        )

    def _serialize_config(self, config: FullConfig) -> Dict[str, Any]:
        """
        Serialize FullConfig to dictionary.

        Args:
            config: FullConfig instance

        Returns:
            Dictionary of configuration data
        """
        data = {
            'environment': config.environment,
            'debug': config.debug,
            'test_mode': config.test_mode,
            'log_level': config.log_level,
            'bot': config.bot.__dict__,
            'trading': config.trading.__dict__,
            'strategy': config.strategy.__dict__,
            'risk': config.risk.__dict__,
            'models': config.models.__dict__,
            'data': config.data.__dict__,
            'monitoring': config.monitoring.__dict__,
            'notifications': config.notifications.__dict__,
            'api': config.api.__dict__,
            'database': config.database.__dict__,
            'redis': config.redis.__dict__,
            'storage': config.storage.__dict__,
            'security': config.security.__dict__,
            'features': config.features,
        }
        return data

    def _get_current_overrides(self) -> Dict[str, Any]:
        """Get current configuration overrides."""
        if not self._config:
            return {}
        return self._serialize_config(self._config)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_environment(self) -> str:
        """Get current environment."""
        return self._config.environment if self._config else "unknown"

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.get_environment() == "production"

    def is_development(self) -> bool:
        """Check if running in development."""
        return self.get_environment() == "development"

    def is_testing(self) -> bool:
        """Check if running in testing."""
        return self.get_environment() == "testing"

    def get_log_level(self) -> str:
        """Get log level."""
        return self._config.log_level if self._config else "INFO"


# ============================================================================
# Singleton Access
# ============================================================================

_config_manager = None


def get_config_manager() -> ConfigManager:
    """
    Get the global configuration manager instance.

    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def load_config(
    mode: Optional[ConfigMode] = None,
    config_path: Optional[Path] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> FullConfig:
    """
    Quick access function to load configuration.

    Args:
        mode: Configuration mode
        config_path: Custom config file path
        overrides: Configuration overrides

    Returns:
        FullConfig instance
    """
    manager = get_config_manager()
    return manager.load_config(mode, config_path, overrides)


def get_config() -> Optional[FullConfig]:
    """
    Quick access function to get current configuration.

    Returns:
        FullConfig instance or None
    """
    manager = get_config_manager()
    return manager.get_config()


def get_config_value(path: str, default: Any = None) -> Any:
    """
    Quick access function to get a configuration value.

    Args:
        path: Dot-notation path
        default: Default value

    Returns:
        Configuration value
    """
    manager = get_config_manager()
    return manager.get(path, default)


# ============================================================================
# Module Information
# ============================================================================

MODULE_INFO = {
    "name": "Configuration",
    "version": __version__,
    "author": __author__,
    "copyright": __copyright__,
    "description": "Configuration management for NEXUS AI Trading Bot",
    "config_files": [
        "default_config.yaml",
        "development_config.yaml",
        "staging_config.yaml",
        "production_config.yaml",
        "testing_config.yaml",
        "bot_configs.yaml",
        "model_configs.yaml",
        "risk_configs.yaml",
        "strategy_configs.yaml",
    ],
}


def get_module_info() -> Dict[str, Any]:
    """Get module information."""
    return MODULE_INFO


def get_version() -> str:
    """Get module version."""
    return __version__


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Print module info
    print(f"Configuration Module v{__version__}")
    print(f"Author: {__author__}")
    print("\nAvailable Config Files:")
    for name in MODULE_INFO["config_files"]:
        print(f"  - {name}")

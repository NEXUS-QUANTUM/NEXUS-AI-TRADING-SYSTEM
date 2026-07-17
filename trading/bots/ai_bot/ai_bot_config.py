# trading/bots/ai_bot/ai_bot_config.py
"""
NEXUS AI TRADING SYSTEM - Configuration Management
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements comprehensive configuration management for the AI Trading Bot.
Provides:
    - Configuration loading and validation
    - Environment-based configuration
    - Dynamic configuration updates
    - Configuration versioning
    - Secret management
    - Configuration schema validation
    - Multi-environment support
    - Configuration inheritance and overrides
    - Configuration export and import
    - Configuration monitoring and hot-reload
"""

import os
import sys
import json
import yaml
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set, Tuple
from dataclasses import dataclass, field, asdict, fields
from enum import Enum
from datetime import datetime, timedelta
from copy import deepcopy
import re
import base64
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class Environment(Enum):
    """Environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
    DEMO = "demo"

class ConfigSource(Enum):
    """Configuration source enumeration."""
    DEFAULT = "default"
    FILE = "file"
    ENVIRONMENT = "environment"
    DATABASE = "database"
    API = "api"
    USER = "user"
    RUNTIME = "runtime"

class ConfigStatus(Enum):
    """Configuration status enumeration."""
    LOADED = "loaded"
    VALIDATED = "validated"
    ACTIVE = "active"
    UPDATED = "updated"
    ERROR = "error"
    PENDING = "pending"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ConfigMeta:
    """Configuration metadata."""
    version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    source: ConfigSource = ConfigSource.DEFAULT
    checksum: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class ConfigValidationResult:
    """Configuration validation result."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_keys: List[str] = field(default_factory=list)
    invalid_values: List[Tuple[str, Any]] = field(default_factory=list)


# =============================================================================
# Configuration Manager
# =============================================================================

class ConfigManager:
    """
    Comprehensive configuration manager for the AI Trading Bot.
    
    This class handles all aspects of configuration management including:
        - Loading from multiple sources
        - Validation against schema
        - Environment-specific overrides
        - Secret management
        - Dynamic updates
        - Versioning
        - Export and import
    
    Usage:
        # Create config manager
        manager = ConfigManager()
        
        # Load configuration
        manager.load_config('config.yaml')
        
        # Get configuration value
        value = manager.get('trading.max_positions')
        
        # Update configuration
        manager.set('trading.max_positions', 10)
        
        # Save configuration
        manager.save_config('updated_config.yaml')
    """
    
    # Default configuration schema
    DEFAULT_SCHEMA = {
        'name': {'type': 'str', 'required': True},
        'version': {'type': 'str', 'default': '3.0.0'},
        'mode': {'type': 'str', 'default': 'paper', 'allowed': ['live', 'paper', 'backtest', 'simulation', 'demo']},
        'enabled': {'type': 'bool', 'default': True},
        'symbols': {'type': 'list', 'required': True, 'min_items': 1},
        'timeframes': {'type': 'list', 'default': ['1h', '4h', '1d']},
        'initial_capital': {'type': 'float', 'default': 100000.0, 'min': 0},
        'max_positions': {'type': 'int', 'default': 5, 'min': 1},
        'max_risk_per_trade': {'type': 'float', 'default': 0.02, 'min': 0, 'max': 0.5},
        'stop_loss': {'type': 'float', 'default': 0.02, 'min': 0, 'max': 0.5},
        'take_profit': {'type': 'float', 'default': 0.04, 'min': 0, 'max': 1.0},
        'risk_reward_ratio': {'type': 'float', 'default': 2.0, 'min': 0.1},
        'commission': {'type': 'float', 'default': 0.001, 'min': 0},
        'slippage': {'type': 'float', 'default': 0.001, 'min': 0},
        'model': {'type': 'dict', 'default': {}},
        'strategy': {'type': 'dict', 'default': {}},
        'risk': {'type': 'dict', 'default': {}},
        'execution': {'type': 'dict', 'default': {}},
        'data': {'type': 'dict', 'default': {}},
        'monitoring': {'type': 'dict', 'default': {}},
        'api': {'type': 'dict', 'default': {}},
        'security': {'type': 'dict', 'default': {}},
        'logging': {'type': 'dict', 'default': {}},
        'performance': {'type': 'dict', 'default': {}}
    }
    
    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        environment: Union[str, Environment] = Environment.DEVELOPMENT,
        auto_load: bool = False,
        secret_key: Optional[str] = None
    ):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to configuration file
            environment: Environment type
            auto_load: Automatically load configuration
            secret_key: Secret key for encryption
        """
        self.config = {}
        self.meta = ConfigMeta(environment=Environment(environment) if isinstance(environment, str) else environment)
        self.schema = deepcopy(self.DEFAULT_SCHEMA)
        self._flat_config = {}
        self._history = []
        self._validators = []
        self._listeners = []
        
        # Set up encryption
        self.secret_key = secret_key or os.environ.get('NEXUS_SECRET_KEY')
        self.fernet = None
        if self.secret_key:
            self._init_encryption()
        
        # Config file monitoring
        self.config_path = Path(config_path) if config_path else None
        self._file_hash = None
        self._last_modified = None
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load configuration if requested
        if auto_load and config_path:
            self.load_from_file(config_path)
        elif auto_load:
            self.load_defaults()
        
        self.logger.info(f"Configuration manager initialized ({self.meta.environment.value})")
    
    # =========================================================================
    # Encryption Methods
    # =========================================================================
    
    def _init_encryption(self) -> None:
        """Initialize encryption for sensitive data."""
        try:
            if self.secret_key:
                # Derive encryption key
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'nexus_salt',
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))
                self.fernet = Fernet(key)
                self.logger.debug("Encryption initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize encryption: {e}")
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value."""
        if not self.fernet:
            return value
        try:
            return self.fernet.encrypt(value.encode()).decode()
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            return value
    
    def decrypt_value(self, encrypted: str) -> str:
        """Decrypt an encrypted value."""
        if not self.fernet:
            return encrypted
        try:
            return self.fernet.decrypt(encrypted.encode()).decode()
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            return encrypted
    
    # =========================================================================
    # Configuration Loading
    # =========================================================================
    
    def load_defaults(self) -> Dict[str, Any]:
        """
        Load default configuration values.
        
        Returns:
            Default configuration dictionary
        """
        default_config = {
            'name': 'NEXUS AI Trading Bot',
            'version': self.meta.version,
            'mode': 'paper' if self.meta.environment != Environment.PRODUCTION else 'live',
            'enabled': True,
            'symbols': ['BTC-USD', 'ETH-USD'],
            'timeframes': ['1h', '4h', '1d'],
            'initial_capital': 100000.0,
            'max_positions': 5,
            'max_risk_per_trade': 0.02,
            'stop_loss': 0.02,
            'take_profit': 0.04,
            'risk_reward_ratio': 2.0,
            'commission': 0.001,
            'slippage': 0.001,
            'model': {
                'type': 'ensemble',
                'path': None,
                'load_on_start': True
            },
            'strategy': {
                'type': 'adaptive',
                'parameters': {}
            },
            'risk': {
                'max_drawdown': 0.20,
                'daily_loss_limit': 0.05,
                'position_concentration': 0.25,
                'max_leverage': 1.0
            },
            'execution': {
                'order_timeout': 10,
                'retry_attempts': 3,
                'max_slippage': 0.005
            },
            'data': {
                'batch_size': 1000,
                'feature_window': 100,
                'cache_enabled': True
            },
            'monitoring': {
                'metrics_interval': 60,
                'log_level': 'INFO',
                'alert_channels': ['email', 'slack']
            },
            'api': {
                'host': '0.0.0.0',
                'port': 8000,
                'enable_docs': True
            },
            'security': {
                'jwt_expiry': 3600,
                'rate_limit': 100,
                'enable_2fa': True
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'performance': {
                'latency_threshold_ms': 100,
                'throughput_threshold': 1000
            }
        }
        
        self.config = default_config
        self._flat_config = self._flatten_config(default_config)
        self.meta.source = ConfigSource.DEFAULT
        self.meta.checksum = self._calculate_checksum()
        self.meta.updated_at = datetime.now()
        self._add_history('load_defaults', default_config)
        
        self.logger.info("Default configuration loaded")
        return default_config
    
    def load_from_file(
        self,
        file_path: Union[str, Path],
        merge: bool = True
    ) -> Dict[str, Any]:
        """
        Load configuration from a file.
        
        Args:
            file_path: Path to configuration file
            merge: Merge with existing configuration
            
        Returns:
            Loaded configuration dictionary
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        self.logger.info(f"Loading configuration from {file_path}")
        
        # Read file
        with open(file_path, 'r') as f:
            if file_path.suffix in ['.yaml', '.yml']:
                loaded_config = yaml.safe_load(f)
            elif file_path.suffix == '.json':
                loaded_config = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        # Merge or replace
        if merge:
            self.config = self._merge_config(self.config, loaded_config)
        else:
            self.config = loaded_config
        
        self._flat_config = self._flatten_config(self.config)
        self.config_path = file_path
        self.meta.source = ConfigSource.FILE
        self.meta.checksum = self._calculate_checksum()
        self.meta.updated_at = datetime.now()
        self._file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
        self._last_modified = file_path.stat().st_mtime
        self._add_history('load_file', file_path)
        
        self.logger.info("Configuration loaded successfully")
        return self.config
    
    def load_from_environment(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        Environment variables should be prefixed with NEXUS_ and use underscores.
        
        Returns:
            Configuration dictionary from environment
        """
        env_config = {}
        prefix = 'NEXUS_'
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert NEXUS_TRADING_MAX_POSITIONS -> trading.max_positions
                path = key[len(prefix):].lower().split('_')
                if len(path) > 1:
                    # Handle nested keys
                    current = env_config
                    for part in path[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    
                    # Parse value
                    try:
                        if value.lower() == 'true':
                            current[path[-1]] = True
                        elif value.lower() == 'false':
                            current[path[-1]] = False
                        elif value.isdigit():
                            current[path[-1]] = int(value)
                        elif value.replace('.', '').isdigit():
                            current[path[-1]] = float(value)
                        else:
                            current[path[-1]] = value
                    except:
                        current[path[-1]] = value
        
        if env_config:
            self.config = self._merge_config(self.config, env_config)
            self._flat_config = self._flatten_config(self.config)
            self.meta.source = ConfigSource.ENVIRONMENT
            self.meta.updated_at = datetime.now()
            self._add_history('load_environment', env_config)
            self.logger.info(f"Environment configuration loaded: {len(env_config)} variables")
        
        return env_config
    
    def load_from_dict(
        self,
        config_dict: Dict[str, Any],
        source: ConfigSource = ConfigSource.USER,
        merge: bool = True
    ) -> Dict[str, Any]:
        """
        Load configuration from dictionary.
        
        Args:
            config_dict: Configuration dictionary
            source: Source of configuration
            merge: Merge with existing configuration
            
        Returns:
            Loaded configuration dictionary
        """
        if merge:
            self.config = self._merge_config(self.config, config_dict)
        else:
            self.config = config_dict
        
        self._flat_config = self._flatten_config(self.config)
        self.meta.source = source
        self.meta.checksum = self._calculate_checksum()
        self.meta.updated_at = datetime.now()
        self._add_history('load_dict', config_dict)
        
        self.logger.info(f"Configuration loaded from dictionary ({source.value})")
        return self.config
    
    def load_multi_source(
        self,
        file_path: Optional[Union[str, Path]] = None,
        load_env: bool = True,
        defaults_first: bool = True
    ) -> Dict[str, Any]:
        """
        Load configuration from multiple sources.
        
        Args:
            file_path: Path to configuration file
            load_env: Load from environment variables
            defaults_first: Apply defaults before other sources
            
        Returns:
            Merged configuration dictionary
        """
        # Start with defaults
        if defaults_first:
            config = self.load_defaults()
        else:
            config = {}
        
        # Load from file
        if file_path:
            file_config = self.load_from_file(file_path, merge=False)
            config = self._merge_config(config, file_config)
        
        # Load from environment
        if load_env:
            env_config = {}
            for key, value in os.environ.items():
                if key.startswith('NEXUS_'):
                    # Parse environment variables
                    path = key[6:].lower().split('_')
                    current = env_config
                    for part in path[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    
                    try:
                        if value.lower() == 'true':
                            current[path[-1]] = True
                        elif value.lower() == 'false':
                            current[path[-1]] = False
                        elif value.isdigit():
                            current[path[-1]] = int(value)
                        elif value.replace('.', '').isdigit():
                            current[path[-1]] = float(value)
                        else:
                            current[path[-1]] = value
                    except:
                        current[path[-1]] = value
            
            config = self._merge_config(config, env_config)
        
        # Apply environment overrides
        if defaults_first and not file_path:
            self.config = config
            self._flat_config = self._flatten_config(config)
            self.meta.updated_at = datetime.now()
            self._add_history('load_multi', config)
        
        self.logger.info("Multi-source configuration loaded")
        return config
    
    # =========================================================================
    # Configuration Access
    # =========================================================================
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-notation key.
        
        Args:
            key: Dot-notation key (e.g., 'trading.max_positions')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                    if value is None:
                        return default
                else:
                    return default
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.RUNTIME) -> bool:
        """
        Set a configuration value by dot-notation key.
        
        Args:
            key: Dot-notation key (e.g., 'trading.max_positions')
            value: Value to set
            source: Source of the update
            
        Returns:
            True if successful
        """
        try:
            keys = key.split('.')
            target = self.config
            
            # Navigate to the correct level
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                if not isinstance(target[k], dict):
                    target[k] = {}
                target = target[k]
            
            # Set the value
            target[keys[-1]] = value
            
            # Update flat config
            self._flat_config = self._flatten_config(self.config)
            self.meta.source = source
            self.meta.checksum = self._calculate_checksum()
            self.meta.updated_at = datetime.now()
            
            self._add_history('set', {key: value})
            self._notify_listeners(key, value)
            
            self.logger.debug(f"Configuration updated: {key} = {value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set configuration: {e}")
            return False
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get a configuration section.
        
        Args:
            section: Section name
            
        Returns:
            Section configuration dictionary
        """
        return self.get(section, {})
    
    def get_flat(self) -> Dict[str, Any]:
        """
        Get flattened configuration.
        
        Returns:
            Flattened configuration dictionary
        """
        return self._flat_config.copy()
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration.
        
        Returns:
            Full configuration dictionary
        """
        return self.config.copy()
    
    # =========================================================================
    # Configuration Validation
    # =========================================================================
    
    def validate(
        self,
        config: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None
    ) -> ConfigValidationResult:
        """
        Validate configuration against schema.
        
        Args:
            config: Configuration to validate (uses self.config if None)
            schema: Schema to validate against (uses self.schema if None)
            
        Returns:
            ValidationResult object
        """
        target = config or self.config
        schema = schema or self.schema
        
        errors = []
        warnings = []
        missing_keys = []
        invalid_values = []
        
        for key, rules in schema.items():
            value = self._get_nested_value(target, key)
            
            # Check required
            if rules.get('required', False):
                if value is None:
                    errors.append(f"Required key missing: {key}")
                    missing_keys.append(key)
                    continue
            
            if value is None:
                continue
            
            # Check type
            expected_type = rules.get('type')
            if expected_type:
                type_map = {
                    'str': str, 'int': int, 'float': float,
                    'bool': bool, 'list': list, 'dict': dict
                }
                python_type = type_map.get(expected_type)
                if python_type and not isinstance(value, python_type):
                    errors.append(f"Invalid type for {key}: expected {expected_type}, got {type(value).__name__}")
                    invalid_values.append((key, value))
                    continue
            
            # Check allowed values
            allowed = rules.get('allowed')
            if allowed and value not in allowed:
                warnings.append(f"Unexpected value for {key}: {value} (allowed: {allowed})")
            
            # Check range for numeric values
            if isinstance(value, (int, float)):
                min_val = rules.get('min')
                max_val = rules.get('max')
                if min_val is not None and value < min_val:
                    errors.append(f"{key} ({value}) below minimum: {min_val}")
                if max_val is not None and value > max_val:
                    errors.append(f"{key} ({value}) above maximum: {max_val}")
            
            # Check list items
            if isinstance(value, list):
                min_items = rules.get('min_items')
                max_items = rules.get('max_items')
                if min_items is not None and len(value) < min_items:
                    errors.append(f"{key} has {len(value)} items, minimum: {min_items}")
                if max_items is not None and len(value) > max_items:
                    errors.append(f"{key} has {len(value)} items, maximum: {max_items}")
        
        is_valid = len(errors) == 0
        
        return ConfigValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            missing_keys=missing_keys,
            invalid_values=invalid_values
        )
    
    def validate_and_repair(self) -> ConfigValidationResult:
        """
        Validate configuration and attempt to repair common issues.
        
        Returns:
            ValidationResult object
        """
        result = self.validate()
        
        if not result.is_valid:
            self.logger.warning(f"Configuration validation failed: {len(result.errors)} errors")
            
            # Attempt to repair
            for key in result.missing_keys:
                default = self._get_nested_value(self._get_default_config(), key)
                if default is not None:
                    self.set(key, default)
                    self.logger.info(f"Repaired missing key: {key}")
            
            # Re-validate
            result = self.validate()
        
        return result
    
    def register_validator(self, validator: Callable) -> None:
        """
        Register a custom validator function.
        
        Args:
            validator: Validation function
        """
        self._validators.append(validator)
        self.logger.debug(f"Registered validator: {validator.__name__}")
    
    # =========================================================================
    # Configuration History
    # =========================================================================
    
    def _add_history(self, action: str, data: Any) -> None:
        """Add an entry to configuration history."""
        self._history.append({
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'data': data,
            'checksum': self.meta.checksum
        })
        
        # Limit history size
        if len(self._history) > 100:
            self._history = self._history[-100:]
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get configuration change history.
        
        Args:
            limit: Maximum number of history entries
            
        Returns:
            List of history entries
        """
        return self._history[-limit:]
    
    def get_version(self) -> str:
        """
        Get configuration version.
        
        Returns:
            Version string
        """
        return self.meta.version
    
    # =========================================================================
    # Configuration Comparison
    # =========================================================================
    
    def compare(self, other_config: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
        """
        Compare current configuration with another configuration.
        
        Args:
            other_config: Configuration to compare with
            
        Returns:
            Dictionary of differences (key -> (old, new))
        """
        differences = {}
        current_flat = self._flatten_config(self.config)
        other_flat = self._flatten_config(other_config)
        
        all_keys = set(current_flat.keys()) | set(other_flat.keys())
        
        for key in all_keys:
            current_value = current_flat.get(key)
            other_value = other_flat.get(key)
            if current_value != other_value:
                differences[key] = (current_value, other_value)
        
        return differences
    
    # =========================================================================
    # Configuration Export
    # =========================================================================
    
    def save_to_file(
        self,
        file_path: Union[str, Path],
        format: str = None,
        sanitize: bool = True
    ) -> bool:
        """
        Save configuration to file.
        
        Args:
            file_path: Path to save configuration
            format: File format ('json' or 'yaml')
            sanitize: Remove sensitive information
            
        Returns:
            True if successful
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine format from extension if not specified
        if format is None:
            if file_path.suffix in ['.yaml', '.yml']:
                format = 'yaml'
            elif file_path.suffix == '.json':
                format = 'json'
            else:
                raise ValueError(f"Unsupported file extension: {file_path.suffix}")
        
        # Prepare config
        config_to_save = self.config.copy()
        if sanitize:
            config_to_save = self._sanitize_config(config_to_save)
        
        try:
            with open(file_path, 'w') as f:
                if format == 'json':
                    json.dump(config_to_save, f, indent=2, default=str)
                elif format == 'yaml':
                    yaml.dump(config_to_save, f, default_flow_style=False)
            
            self.logger.info(f"Configuration saved to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False
    
    def export_env(self) -> Dict[str, str]:
        """
        Export configuration as environment variables.
        
        Returns:
            Dictionary of environment variables
        """
        env_vars = {}
        prefix = 'NEXUS_'
        
        for key, value in self._flat_config.items():
            env_key = prefix + key.upper().replace('.', '_')
            if isinstance(value, bool):
                env_vars[env_key] = str(value).lower()
            elif isinstance(value, (int, float)):
                env_vars[env_key] = str(value)
            else:
                env_vars[env_key] = str(value)
        
        return env_vars
    
    # =========================================================================
    # Configuration Utilities
    # =========================================================================
    
    def _flatten_config(
        self,
        config: Dict[str, Any],
        prefix: str = '',
        separator: str = '.'
    ) -> Dict[str, Any]:
        """Flatten a nested configuration dictionary."""
        result = {}
        
        for key, value in config.items():
            new_key = f"{prefix}{separator}{key}" if prefix else key
            
            if isinstance(value, dict):
                result.update(self._flatten_config(value, new_key, separator))
            else:
                result[new_key] = value
        
        return result
    
    def _merge_config(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two configuration dictionaries with override taking precedence."""
        result = deepcopy(base)
        
        for key, value in override.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = deepcopy(value)
        
        return result
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """Get a nested value from configuration."""
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return None
            else:
                return None
        
        return value
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration dictionary."""
        default = {}
        for key, rules in self.schema.items():
            if 'default' in rules:
                default[key] = rules['default']
        return default
    
    def _calculate_checksum(self) -> str:
        """Calculate configuration checksum."""
        config_str = json.dumps(self.config, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def _sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from configuration."""
        sensitive_keys = ['password', 'secret', 'key', 'token', 'auth', 'credential']
        sanitized = deepcopy(config)
        
        def sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in list(d.items()):
                if any(s in key.lower() for s in sensitive_keys) and isinstance(value, str):
                    d[key] = '***REDACTED***'
                elif isinstance(value, dict):
                    sanitize_dict(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            sanitize_dict(item)
            return d
        
        return sanitize_dict(sanitized)
    
    def _notify_listeners(self, key: str, value: Any) -> None:
        """Notify configuration listeners of changes."""
        for listener in self._listeners:
            try:
                listener(key, value)
            except Exception as e:
                self.logger.error(f"Listener error: {e}")
    
    # =========================================================================
    # Event Management
    # =========================================================================
    
    def add_listener(self, listener: Callable) -> None:
        """
        Add a configuration change listener.
        
        Args:
            listener: Callback function (key, value)
        """
        self._listeners.append(listener)
        self.logger.debug(f"Added listener: {listener.__name__}")
    
    def remove_listener(self, listener: Callable) -> bool:
        """
        Remove a configuration change listener.
        
        Args:
            listener: Callback function
            
        Returns:
            True if removed
        """
        if listener in self._listeners:
            self._listeners.remove(listener)
            self.logger.debug(f"Removed listener: {listener.__name__}")
            return True
        return False
    
    # =========================================================================
    # Configuration Monitoring
    # =========================================================================
    
    def check_file_changes(self) -> bool:
        """
        Check if the configuration file has changed.
        
        Returns:
            True if file has changed
        """
        if not self.config_path or not self.config_path.exists():
            return False
        
        try:
            current_hash = hashlib.md5(open(self.config_path, 'rb').read()).hexdigest()
            if current_hash != self._file_hash:
                self._file_hash = current_hash
                self._last_modified = self.config_path.stat().st_mtime
                return True
        except Exception as e:
            self.logger.error(f"Error checking file changes: {e}")
        
        return False
    
    def reload_if_changed(self) -> bool:
        """
        Reload configuration if file has changed.
        
        Returns:
            True if reloaded
        """
        if self.check_file_changes():
            self.logger.info("Configuration file changed, reloading...")
            self.load_from_file(self.config_path)
            return True
        return False


# =============================================================================
# Factory Function
# =============================================================================

def create_config_manager(
    config_path: Optional[Union[str, Path]] = None,
    environment: Union[str, Environment] = Environment.DEVELOPMENT,
    auto_load: bool = True,
    secret_key: Optional[str] = None
) -> ConfigManager:
    """
    Factory function to create a configuration manager.
    
    Args:
        config_path: Path to configuration file
        environment: Environment type
        auto_load: Automatically load configuration
        secret_key: Secret key for encryption
        
    Returns:
        ConfigManager instance
    """
    return ConfigManager(
        config_path=config_path,
        environment=environment,
        auto_load=auto_load,
        secret_key=secret_key
    )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'ConfigManager',
    'ConfigMeta',
    'ConfigValidationResult',
    'Environment',
    'ConfigSource',
    'ConfigStatus',
    'create_config_manager'
]


# =============================================================================
# Module Docstring
# =============================================================================

__doc__ = f"""
{__name__} - NEXUS AI Trading Bot Configuration Management

This module provides comprehensive configuration management for the
NEXUS AI Trading Bot, supporting multiple environments, sources,
and dynamic updates.

Copyright: {__copyright__}
CEO: {__author__}
Version: {__version__}

Features:
    - Multi-source configuration loading
    - Environment variable integration
    - Configuration validation
    - Secret management
    - Dynamic updates
    - Change history
    - Hot-reload support
"""

# Log module initialization
logger.info(f"Configuration manager module loaded (version {__version__})")

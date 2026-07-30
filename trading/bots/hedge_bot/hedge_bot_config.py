# trading/bots/hedge_bot/hedge_bot_config.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Config Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Config Module

This module provides comprehensive configuration management capabilities
for the NEXUS Hedge Bot system. It handles configuration loading, validation,
and dynamic updates.

The module covers:
- Configuration Loading
- Configuration Validation
- Dynamic Configuration Updates
- Configuration Schema Validation
- Environment Variable Integration
- Configuration Caching
- Configuration Hot Reload
- Configuration Versioning
- Configuration Export/Import
"""

import os
import sys
import json
import yaml
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import copy
import re

logger = logging.getLogger(__name__)


# ============================================================
# CONFIG ENUMS
# ============================================================

class ConfigLevel(Enum):
    """Configuration levels"""
    DEFAULT = "default"
    ENVIRONMENT = "environment"
    USER = "user"
    RUNTIME = "runtime"
    OVERRIDE = "override"


class ConfigStatus(Enum):
    """Configuration status"""
    LOADED = "loaded"
    VALID = "valid"
    INVALID = "invalid"
    UPDATED = "updated"
    RELOADED = "reloaded"
    ERROR = "error"


@dataclass
class ConfigValidationResult:
    """Configuration validation result"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# CONFIG SCHEMA
# ============================================================

CONFIG_SCHEMA = {
    "bot": {
        "type": "dict",
        "required": True,
        "schema": {
            "id": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "version": {"type": "str", "required": True},
            "environment": {"type": "str", "required": True, "allowed": ["development", "staging", "production", "demo", "testing"]},
            "enabled": {"type": "bool", "required": True},
            "active": {"type": "bool", "required": True},
            "debug_mode": {"type": "bool", "required": False},
            "log_level": {"type": "str", "required": False, "allowed": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
        }
    },
    "exchange": {
        "type": "dict",
        "required": True,
        "schema": {
            "name": {"type": "str", "required": True, "allowed": ["binance", "bybit", "coinbase", "kraken", "okx", "deribit"]},
            "type": {"type": "str", "required": True, "allowed": ["spot", "futures", "perpetual", "options"]},
            "sandbox": {"type": "bool", "required": True},
            "api": {
                "type": "dict",
                "required": True,
                "schema": {
                    "key": {"type": "str", "required": True},
                    "secret": {"type": "str", "required": True},
                    "passphrase": {"type": "str", "required": False},
                }
            }
        }
    },
    "trading": {
        "type": "dict",
        "required": True,
        "schema": {
            "order": {
                "type": "dict",
                "required": True,
                "schema": {
                    "type": {"type": "str", "required": True, "allowed": ["limit", "market", "stop_limit", "trailing_stop"]},
                    "time_in_force": {"type": "str", "required": True, "allowed": ["GTC", "IOC", "FOK", "DAY"]},
                    "max_order_size": {"type": "float", "required": True, "min": 0},
                    "min_order_size": {"type": "float", "required": True, "min": 0},
                    "slippage_tolerance": {"type": "float", "required": True, "min": 0, "max": 1},
                }
            },
            "position": {
                "type": "dict",
                "required": True,
                "schema": {
                    "max_positions": {"type": "int", "required": True, "min": 0},
                    "max_leverage": {"type": "float", "required": True, "min": 1, "max": 10},
                    "target_hedge_ratio": {"type": "float", "required": True, "min": 0, "max": 1},
                }
            }
        }
    },
    "risk_management": {
        "type": "dict",
        "required": True,
        "schema": {
            "limits": {
                "type": "dict",
                "required": True,
                "schema": {
                    "max_drawdown": {"type": "float", "required": True, "min": 0, "max": 1},
                    "daily_loss_limit": {"type": "float", "required": True, "min": 0, "max": 1},
                    "max_leverage": {"type": "float", "required": True, "min": 1, "max": 10},
                }
            }
        }
    },
    "portfolio": {
        "type": "dict",
        "required": True,
        "schema": {
            "currency": {"type": "str", "required": True},
            "initial_balance": {"type": "float", "required": True, "min": 0},
        }
    },
    "data": {
        "type": "dict",
        "required": True,
        "schema": {
            "sources": {
                "type": "dict",
                "required": True,
                "schema": {
                    "market_data": {
                        "type": "dict",
                        "required": True,
                        "schema": {
                            "provider": {"type": "str", "required": True},
                        }
                    }
                }
            }
        }
    },
    "logging": {
        "type": "dict",
        "required": True,
        "schema": {
            "config": {
                "type": "dict",
                "required": True,
                "schema": {
                    "enabled": {"type": "bool", "required": True},
                    "log_level": {"type": "str", "required": True, "allowed": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                }
            }
        }
    }
}


# ============================================================
# CONFIG MANAGER
# ============================================================

class ConfigManager:
    """
    Comprehensive configuration manager for the hedge bot
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the configuration manager
        
        Args:
            config: Configuration dictionary
        """
        if hasattr(self, '_initialized'):
            return
        
        self.config_dir = Path(config.get("config_dir", "config")) if config else Path("config")
        self.environment = config.get("environment", "development") if config else "development"
        self.auto_reload = config.get("auto_reload", True) if config else True
        self.reload_interval = config.get("reload_interval", 60) if config else 60
        
        # Create config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self.config: Dict[str, Any] = {}
        self.original_config: Dict[str, Any] = {}
        self.config_version: str = "1.0"
        self.loaded_files: List[str] = []
        self.last_load_time: Optional[datetime] = None
        self.config_hash: str = ""
        
        # Schema
        self.schema = CONFIG_SCHEMA
        
        # Load configuration
        self.load()
        
        self._initialized = True
        logger.info("Config manager initialized")
    
    # ============================================================
    # CONFIG LOADING
    # ============================================================
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from files
        
        Returns:
            Configuration dictionary
        """
        self.loaded_files = []
        config = {}
        
        # Load default config
        default_path = self.config_dir / "default_config.yaml"
        if default_path.exists():
            with open(default_path, "r") as f:
                default_config = yaml.safe_load(f) or {}
                config = self._merge_config(config, default_config)
                self.loaded_files.append(str(default_path))
        
        # Load environment config
        env_path = self.config_dir / f"{self.environment}_config.yaml"
        if env_path.exists():
            with open(env_path, "r") as f:
                env_config = yaml.safe_load(f) or {}
                config = self._merge_config(config, env_config)
                self.loaded_files.append(str(env_path))
        
        # Load additional configs
        for file_path in self.config_dir.glob("*_configs.yaml"):
            if file_path.stem not in ["default", self.environment]:
                with open(file_path, "r") as f:
                    file_config = yaml.safe_load(f) or {}
                    config = self._merge_config(config, file_config)
                    self.loaded_files.append(str(file_path))
        
        # Load user config
        user_path = self.config_dir / "user_config.yaml"
        if user_path.exists():
            with open(user_path, "r") as f:
                user_config = yaml.safe_load(f) or {}
                config = self._merge_config(config, user_config)
                self.loaded_files.append(str(user_path))
        
        # Apply environment variables
        config = self._apply_env_vars(config)
        
        # Validate config
        validation = self.validate(config)
        if not validation.valid:
            logger.warning(f"Configuration validation failed: {validation.errors}")
        
        # Update state
        self.original_config = copy.deepcopy(config)
        self.config = config
        self.last_load_time = datetime.now()
        self.config_hash = self._calculate_hash(config)
        
        logger.info(f"Configuration loaded from {len(self.loaded_files)} files")
        return config
    
    def reload(self) -> Dict[str, Any]:
        """
        Reload configuration
        
        Returns:
            Reloaded configuration
        """
        logger.info("Reloading configuration...")
        return self.load()
    
    def _merge_config(self, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two configurations
        
        Args:
            base: Base configuration
            override: Override configuration
            
        Returns:
            Merged configuration
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variables to configuration
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Updated configuration
        """
        env_prefix = "NEXUS_"
        
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                # Convert NEXUS_EXCHANGE_API_KEY to exchange.api.key
                path = key[len(env_prefix):].lower().replace("_", ".")
                self._set_nested_value(config, path, value)
        
        return config
    
    def _set_nested_value(self, config: Dict, path: str, value: Any) -> None:
        """Set nested value using dot notation"""
        parts = path.split(".")
        current = config
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Try to parse value
        if value.lower() in ["true", "yes", "on"]:
            value = True
        elif value.lower() in ["false", "no", "off"]:
            value = False
        
        current[parts[-1]] = value
    
    # ============================================================
    # CONFIG VALIDATION
    # ============================================================
    
    def validate(self, config: Optional[Dict[str, Any]] = None) -> ConfigValidationResult:
        """
        Validate configuration against schema
        
        Args:
            config: Configuration to validate
            
        Returns:
            ConfigValidationResult
        """
        if config is None:
            config = self.config
        
        errors = []
        warnings = []
        
        if not config:
            errors.append("Configuration is empty")
            return ConfigValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
            )
        
        # Validate against schema
        self._validate_schema(config, self.schema, errors, warnings)
        
        return ConfigValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def _validate_schema(
        self,
        config: Dict,
        schema: Dict,
        errors: List[str],
        warnings: List[str],
        path: str = ""
    ) -> None:
        """Validate configuration against schema recursively"""
        for key, rules in schema.items():
            current_path = f"{path}.{key}" if path else key
            
            # Check required
            if rules.get("required", False) and key not in config:
                errors.append(f"Required field missing: {current_path}")
                continue
            
            if key not in config:
                continue
            
            value = config[key]
            
            # Check type
            expected_type = rules.get("type")
            if expected_type:
                if expected_type == "str" and not isinstance(value, str):
                    errors.append(f"Field {current_path} should be str, got {type(value).__name__}")
                elif expected_type == "int" and not isinstance(value, int):
                    errors.append(f"Field {current_path} should be int, got {type(value).__name__}")
                elif expected_type == "float" and not isinstance(value, (int, float)):
                    errors.append(f"Field {current_path} should be float, got {type(value).__name__}")
                elif expected_type == "bool" and not isinstance(value, bool):
                    errors.append(f"Field {current_path} should be bool, got {type(value).__name__}")
                elif expected_type == "dict" and not isinstance(value, dict):
                    errors.append(f"Field {current_path} should be dict, got {type(value).__name__}")
                elif expected_type == "list" and not isinstance(value, list):
                    errors.append(f"Field {current_path} should be list, got {type(value).__name__}")
            
            # Check allowed values
            allowed = rules.get("allowed")
            if allowed and value not in allowed:
                errors.append(f"Field {current_path} has invalid value: {value}. Allowed: {allowed}")
            
            # Check min/max
            min_val = rules.get("min")
            if min_val is not None and value < min_val:
                errors.append(f"Field {current_path} is below minimum: {value} < {min_val}")
            
            max_val = rules.get("max")
            if max_val is not None and value > max_val:
                errors.append(f"Field {current_path} is above maximum: {value} > {max_val}")
            
            # Validate nested schema
            if expected_type == "dict" and "schema" in rules:
                self._validate_schema(value, rules["schema"], errors, warnings, current_path)
    
    # ============================================================
    # CONFIG ACCESS
    # ============================================================
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value
        
        Args:
            key: Dot notation key
            default: Default value
            
        Returns:
            Configuration value
        """
        return self._get_nested_value(self.config, key, default)
    
    def _get_nested_value(self, config: Dict, key: str, default: Any = None) -> Any:
        """Get nested value using dot notation"""
        parts = key.split(".")
        current = config
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        return current
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value
        
        Args:
            key: Dot notation key
            value: Value to set
        """
        self._set_nested_value(self.config, key, value)
        self.config_hash = self._calculate_hash(self.config)
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get configuration section
        
        Args:
            section: Section name
            
        Returns:
            Section configuration
        """
        return self.get(section, {})
    
    def get_environment(self) -> str:
        """
        Get current environment
        
        Returns:
            Environment name
        """
        return self.get("bot.environment", "development")
    
    def is_debug(self) -> bool:
        """
        Check if debug mode is enabled
        
        Returns:
            True if debug mode
        """
        return self.get("bot.debug_mode", False)
    
    # ============================================================
    # CONFIG EXPORT/IMPORT
    # ============================================================
    
    def export(self, format: str = "json") -> str:
        """
        Export configuration
        
        Args:
            format: Export format (json, yaml)
            
        Returns:
            Exported configuration
        """
        if format == "json":
            return json.dumps(self.config, indent=2)
        elif format == "yaml":
            return yaml.dump(self.config, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_config(self, data: str, format: str = "json") -> bool:
        """
        Import configuration
        
        Args:
            data: Configuration data
            format: Data format
            
        Returns:
            True if imported
        """
        try:
            if format == "json":
                config = json.loads(data)
            elif format == "yaml":
                config = yaml.safe_load(data)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            # Validate
            validation = self.validate(config)
            if not validation.valid:
                logger.error(f"Configuration validation failed: {validation.errors}")
                return False
            
            # Update
            self.config = config
            self.config_hash = self._calculate_hash(config)
            return True
            
        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            return False
    
    # ============================================================
    # CONFIG MONITORING
    # ============================================================
    
    def has_changed(self) -> bool:
        """
        Check if configuration has changed on disk
        
        Returns:
            True if changed
        """
        current_hash = self._calculate_hash(self.config)
        return current_hash != self.config_hash
    
    def is_reload_required(self) -> bool:
        """
        Check if reload is required
        
        Returns:
            True if reload required
        """
        if not self.auto_reload:
            return False
        
        if self.last_load_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_load_time).total_seconds()
        return elapsed >= self.reload_interval
    
    def _calculate_hash(self, config: Dict[str, Any]) -> str:
        """Calculate configuration hash"""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get configuration statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "loaded_files": self.loaded_files,
            "last_load_time": self.last_load_time.isoformat() if self.last_load_time else None,
            "environment": self.get_environment(),
            "config_hash": self.config_hash,
            "validation": self.validate().to_dict(),
            "schema_version": self.config_version,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "ConfigLevel",
    "ConfigStatus",
    
    # Dataclasses
    "ConfigValidationResult",
    
    # Classes
    "ConfigManager",
]

# ============================================================
# END OF MODULE
# ============================================================

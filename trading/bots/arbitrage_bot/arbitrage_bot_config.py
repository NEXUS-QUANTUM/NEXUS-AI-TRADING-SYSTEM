"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Configuration Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de configuration pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import os
import json
import yaml
import copy
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import re
import sys

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class ConfigEnvironment(Enum):
    """Environnements de configuration"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

class ConfigSource(Enum):
    """Sources de configuration"""
    FILE = "file"
    ENV = "environment"
    CLI = "command_line"
    DEFAULT = "default"
    DATABASE = "database"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ConfigOverride:
    """Override de configuration"""
    path: str
    value: Any
    source: ConfigSource
    timestamp: float = field(default_factory=lambda: time.time())
    
@dataclass
class ConfigValidationRule:
    """Règle de validation de configuration"""
    path: str
    field_type: type
    required: bool = False
    default: Any = None
    validator: Optional[callable] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    pattern: Optional[str] = None
    enum_values: Optional[List[Any]] = None

@dataclass
class ConfigSchema:
    """Schéma de configuration"""
    version: str
    description: str
    rules: List[ConfigValidationRule]

# ============================================================
# CONFIGURATION MANAGER
# ============================================================

class ConfigManager:
    """
    Gestionnaire de configuration
    
    Gère le chargement, la validation, la mise à jour et la persistance
    de la configuration du bot d'arbitrage
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        environment: Optional[str] = None,
        schema_path: Optional[str] = None,
        auto_save: bool = True
    ):
        """
        Initialise le gestionnaire de configuration
        
        Args:
            config_path: Chemin du fichier de configuration
            environment: Environnement
            schema_path: Chemin du schéma de validation
            auto_save: Sauvegarder automatiquement les modifications
        """
        self.config_path = Path(config_path) if config_path else Path("config/arbitrage_config.yaml")
        self.environment = environment or os.environ.get("NEXUS_ENV", "production")
        self.schema_path = Path(schema_path) if schema_path else Path("config/schema.yaml")
        self.auto_save = auto_save
        
        self.config: Dict[str, Any] = {}
        self.original_config: Dict[str, Any] = {}
        self.overrides: List[ConfigOverride] = []
        self.schema: Optional[ConfigSchema] = None
        
        self._loaded_from: Optional[ConfigSource] = None
        self._modified = False
        
        # Charger le schéma
        self._load_schema()
        
        # Charger la configuration
        self.load()
        
        logger.info(f"ConfigManager initialized (env: {self.environment})")
    
    # ============================================================
    # LOADING
    # ============================================================
    
    def load(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Charge la configuration
        
        Args:
            force_reload: Forcer le rechargement
            
        Returns:
            Dict[str, Any]: Configuration chargée
        """
        if self.config and not force_reload:
            return self.config
        
        # 1. Configuration par défaut
        config = self._get_default_config()
        self._loaded_from = ConfigSource.DEFAULT
        
        # 2. Configuration depuis le fichier
        file_config = self._load_from_file()
        if file_config:
            config = self._deep_merge(config, file_config)
            self._loaded_from = ConfigSource.FILE
        
        # 3. Configuration depuis l'environnement
        env_config = self._load_from_environment()
        if env_config:
            config = self._deep_merge(config, env_config)
            self._loaded_from = ConfigSource.ENV
        
        # 4. Configuration depuis la ligne de commande
        cli_config = self._load_from_cli()
        if cli_config:
            config = self._deep_merge(config, cli_config)
            self._loaded_from = ConfigSource.CLI
        
        # 5. Appliquer les overrides
        for override in self.overrides:
            self._set_nested_value(config, override.path, override.value)
        
        # 6. Valider la configuration
        self._validate_config(config)
        
        # Sauvegarder
        self.config = config
        self.original_config = copy.deepcopy(config)
        self._modified = False
        
        logger.info(f"Configuration loaded from {self._loaded_from.value}")
        return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Récupère la configuration par défaut"""
        return {
            "bot": {
                "id": "arbitrage-bot-001",
                "name": "NEXUS Arbitrage Bot",
                "version": "2.0.0",
                "environment": self.environment,
                "debug": False,
            },
            "general": {
                "enabled": True,
                "log_level": "info",
                "timezone": "UTC",
                "locale": "en_US",
                "max_concurrent_operations": 10,
                "operation_timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 5,
                "shutdown_timeout": 30,
            },
            "exchanges": {},
            "strategies": {},
            "risk_management": {
                "enabled": True,
                "max_drawdown": 0.15,
                "daily_loss_limit": 0.05,
                "max_positions": 10,
                "position_sizing": {
                    "strategy": "adaptive",
                    "max_position_size": 50000,
                    "min_position_size": 100,
                },
                "stop_loss": {
                    "enabled": True,
                    "type": "trailing",
                    "percentage": 0.02,
                },
                "take_profit": {
                    "enabled": True,
                    "type": "multiple",
                    "targets": [0.01, 0.02, 0.03],
                    "allocation": [0.33, 0.33, 0.34],
                },
            },
            "execution": {
                "enabled": True,
                "mode": "smart",
                "order_types": ["market", "limit"],
                "order_routing": {
                    "enabled": True,
                    "strategy": "smart",
                    "max_slippage": 0.005,
                },
                "batch_execution": {
                    "enabled": True,
                    "max_batch_size": 10,
                    "batch_timeout": 5,
                },
                "timeout": {
                    "order": 30,
                    "execution": 60,
                    "settlement": 120,
                },
                "retry": {
                    "enabled": True,
                    "max_attempts": 3,
                    "delay": 2,
                    "backoff": 2.0,
                },
            },
            "market_data": {
                "enabled": True,
                "source": "aggregated",
                "providers": ["binance", "bybit", "coinbase"],
                "tickers": {
                    "update_interval": 1,
                    "batch_size": 100,
                },
                "order_book": {
                    "update_interval": 5,
                    "depth": 100,
                },
                "candles": {
                    "enabled": True,
                    "intervals": ["1m", "5m", "15m", "1h", "4h", "1d"],
                    "retention": 1000,
                },
                "websocket": {
                    "enabled": True,
                    "reconnect_attempts": 10,
                    "reconnect_delay": 5,
                    "heartbeat_interval": 30,
                },
            },
            "metrics": {
                "enabled": True,
                "collection_interval": 10,
                "retention": 86400,
                "metrics": [
                    "pnl", "trades", "volume", "win_rate", 
                    "sharpe_ratio", "max_drawdown", "profit_factor"
                ],
                "reporting": {
                    "enabled": True,
                    "interval": 3600,
                    "format": "json",
                },
                "alerts": {
                    "enabled": True,
                    "channels": ["telegram", "email"],
                    "min_interval": 60,
                },
            },
            "logging": {
                "enabled": True,
                "level": "info",
                "format": "json",
                "outputs": [
                    {
                        "type": "console",
                        "enabled": True,
                    },
                    {
                        "type": "file",
                        "enabled": True,
                        "path": "/var/log/nexus/arbitrage.log",
                        "max_size": 104857600,
                        "max_files": 30,
                    },
                ],
            },
            "database": {
                "enabled": True,
                "type": "timescaledb",
                "host": "localhost",
                "port": 5432,
                "name": "nexus_arbitrage",
                "user": "postgres",
                "password": "",
                "pool_size": 20,
                "timeout": 30,
                "ssl": {
                    "enabled": True,
                    "mode": "verify-full",
                },
                "backups": {
                    "enabled": True,
                    "interval": 86400,
                    "retention": 30,
                    "compress": True,
                    "encryption": True,
                },
                "migrations": {
                    "enabled": True,
                    "auto_run": False,
                    "path": "./migrations/prod",
                },
            },
            "cache": {
                "enabled": True,
                "type": "redis",
                "host": "localhost",
                "port": 6379,
                "password": "",
                "db": 0,
                "ttl": {
                    "tickers": 60,
                    "order_books": 30,
                    "candles": 300,
                    "opportunities": 10,
                    "metrics": 300,
                    "config": 600,
                },
                "compression": {
                    "enabled": True,
                    "algorithm": "zstd",
                    "level": 3,
                },
            },
            "notifications": {
                "enabled": True,
                "channels": {
                    "telegram": {
                        "enabled": False,
                        "bot_token": "",
                        "chat_id": "",
                        "parse_mode": "HTML",
                    },
                    "slack": {
                        "enabled": False,
                        "webhook_url": "",
                        "channel": "#arbitrage",
                        "username": "Nexus Arbitrage Bot",
                    },
                    "email": {
                        "enabled": False,
                        "smtp_host": "",
                        "smtp_port": 587,
                        "username": "",
                        "password": "",
                        "from": "arbitrage@nexustradingia.com",
                        "to": [],
                    },
                },
                "events": [
                    "opportunity", "execution", "alert", 
                    "error", "status_change", "daily_report"
                ],
            },
            "api": {
                "enabled": True,
                "host": "0.0.0.0",
                "port": 8000,
                "prefix": "/api/v1",
                "workers": 4,
                "cors": {
                    "enabled": True,
                    "origins": ["*"],
                    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                },
                "rate_limit": {
                    "enabled": True,
                    "requests_per_minute": 120,
                    "burst": 30,
                },
                "authentication": {
                    "enabled": True,
                    "type": "jwt",
                    "token_expiry": 3600,
                    "refresh_token_expiry": 86400,
                },
                "documentation": {
                    "enabled": True,
                    "path": "/docs",
                    "title": "NEXUS Arbitrage Bot API",
                },
            },
            "websocket": {
                "enabled": True,
                "host": "0.0.0.0",
                "port": 8001,
                "path": "/ws",
                "max_connections": 1000,
                "ping_interval": 30,
                "ping_timeout": 10,
                "channels": [
                    "opportunities", "executions", "metrics", 
                    "alerts", "status", "performance", "risk"
                ],
                "compression": {
                    "enabled": True,
                    "algorithm": "permessage-deflate",
                    "level": 3,
                },
            },
            "monitoring": {
                "enabled": True,
                "prometheus": {
                    "enabled": True,
                    "port": 9090,
                    "path": "/metrics",
                },
                "grafana": {
                    "enabled": False,
                    "host": "localhost",
                    "port": 3000,
                },
                "health_check": {
                    "enabled": True,
                    "interval": 15,
                    "path": "/health",
                    "timeout": 10,
                },
                "alerts": {
                    "enabled": True,
                    "rules": [
                        {
                            "name": "high_latency",
                            "condition": "execution_latency > 1000ms",
                            "severity": "warning",
                            "duration": "1m",
                        },
                        {
                            "name": "high_error_rate",
                            "condition": "error_rate > 0.05",
                            "severity": "critical",
                            "duration": "1m",
                        },
                        {
                            "name": "high_drawdown",
                            "condition": "drawdown > 0.10",
                            "severity": "warning",
                            "duration": "5m",
                        },
                    ],
                    "cooldown": 60,
                },
            },
            "scheduler": {
                "enabled": True,
                "timezone": "UTC",
                "max_workers": 5,
                "thread_pool": 10,
                "jobs": [
                    {
                        "name": "opportunity_scanner",
                        "enabled": True,
                        "interval": 1,
                        "timeout": 30,
                        "max_retries": 3,
                        "priority": 1,
                    },
                    {
                        "name": "performance_reporter",
                        "enabled": True,
                        "schedule": "0 */6 * * *",
                        "timeout": 300,
                        "max_retries": 3,
                        "priority": 2,
                    },
                    {
                        "name": "daily_cleanup",
                        "enabled": True,
                        "schedule": "0 0 * * *",
                        "timeout": 600,
                        "max_retries": 3,
                        "priority": 3,
                    },
                    {
                        "name": "health_check",
                        "enabled": True,
                        "interval": 60,
                        "timeout": 30,
                        "max_retries": 3,
                        "priority": 1,
                    },
                    {
                        "name": "backup_rotation",
                        "enabled": True,
                        "schedule": "0 2 * * *",
                        "timeout": 1800,
                        "max_retries": 3,
                        "priority": 3,
                    },
                ],
            },
            "security": {
                "enabled": True,
                "encryption": {
                    "enabled": True,
                    "algorithm": "AES-256-GCM",
                    "key_rotation_days": 90,
                },
                "api_keys": {
                    "encryption": True,
                    "rotation": 90,
                    "min_length": 32,
                    "max_length": 64,
                },
                "ip_whitelist": {
                    "enabled": True,
                    "ips": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
                },
                "rate_limiting": {
                    "enabled": True,
                    "requests_per_minute": 120,
                    "burst_limit": 60,
                },
                "ssl": {
                    "enabled": True,
                    "cert": "/etc/ssl/certs/nexus.crt",
                    "key": "/etc/ssl/private/nexus.key",
                    "ca": "/etc/ssl/certs/ca-bundle.crt",
                },
                "audit": {
                    "enabled": True,
                    "log_level": "info",
                    "retention": 2555,
                    "path": "/var/log/nexus/audit.log",
                    "encryption": True,
                },
            },
            "compliance": {
                "enabled": True,
                "regulations": ["MIFID_II", "KYC", "AML", "GDPR"],
                "reporting": {
                    "enabled": True,
                    "interval": "daily",
                    "format": "pdf",
                    "encryption": True,
                },
                "audit": {
                    "enabled": True,
                    "log_level": "info",
                    "retention": 2555,
                    "encryption": True,
                    "signing": True,
                },
                "limits": {
                    "max_trade_size": 50000,
                    "max_daily_trades": 100,
                    "max_position_size": 100000,
                    "max_daily_volume": 1000000,
                    "max_leverage": 3,
                },
            },
            "development": {
                "enabled": False,
                "mock_data": False,
                "simulate_latency": False,
                "simulate_errors": False,
                "hot_reload": False,
                "debug_endpoints": False,
                "verbose_logging": False,
                "profile_code": False,
                "testing": {
                    "mode": "unit",
                    "coverage": False,
                    "coverage_threshold": 80,
                },
                "sandbox": {
                    "enabled": False,
                    "mode": "simulation",
                    "limits": {
                        "max_balance": 10000,
                        "max_trade_size": 1000,
                        "max_positions": 3,
                    },
                },
            },
        }
    
    def _load_from_file(self) -> Optional[Dict[str, Any]]:
        """Charge la configuration depuis un fichier"""
        if not self.config_path.exists():
            return None
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif self.config_path.suffix == '.json':
                    config = json.load(f)
                else:
                    logger.warning(f"Unsupported config file format: {self.config_path.suffix}")
                    return None
            
            # Charger la configuration spécifique à l'environnement
            env_config_path = self.config_path.parent / f"{self.config_path.stem}_{self.environment}{self.config_path.suffix}"
            if env_config_path.exists():
                with open(env_config_path, 'r', encoding='utf-8') as f:
                    if env_config_path.suffix in ['.yaml', '.yml']:
                        env_config = yaml.safe_load(f)
                    elif env_config_path.suffix == '.json':
                        env_config = json.load(f)
                    else:
                        env_config = {}
                
                config = self._deep_merge(config, env_config)
                logger.info(f"Loaded environment config from {env_config_path}")
            
            logger.info(f"Loaded config from {self.config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config from file: {e}")
            return None
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """Charge la configuration depuis les variables d'environnement"""
        config = {}
        
        # Variables d'environnement NEXUS_*
        prefix = "NEXUS_"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # Convertir en chemin de configuration
            path = key[len(prefix):].lower().replace("__", ".").replace("_", ".")
            path_parts = path.split(".")
            
            # Convertir la valeur
            if value.lower() in ["true", "false"]:
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "").isdigit():
                value = float(value)
            
            self._set_nested_value(config, path, value)
        
        return config
    
    def _load_from_cli(self) -> Dict[str, Any]:
        """Charge la configuration depuis la ligne de commande"""
        config = {}
        
        # Arguments de la ligne de commande
        args = sys.argv[1:]
        
        for i, arg in enumerate(args):
            if arg.startswith("--config-") and "=" in arg:
                _, path_value = arg.split("=", 1)
                path, value = path_value.split("=", 1)
                path = path.replace("--config-", "")
                self._set_nested_value(config, path, value)
            elif arg.startswith("--") and i + 1 < len(args):
                path = arg[2:]
                value = args[i + 1]
                self._set_nested_value(config, path, value)
        
        return config
    
    def _load_schema(self):
        """Charge le schéma de validation"""
        if not self.schema_path.exists():
            logger.warning(f"Schema file not found: {self.schema_path}")
            return
        
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                if self.schema_path.suffix in ['.yaml', '.yml']:
                    schema_data = yaml.safe_load(f)
                elif self.schema_path.suffix == '.json':
                    schema_data = json.load(f)
                else:
                    logger.warning(f"Unsupported schema file format: {self.schema_path.suffix}")
                    return
            
            rules = []
            for rule_data in schema_data.get('rules', []):
                rules.append(ConfigValidationRule(
                    path=rule_data.get('path', ''),
                    field_type=self._get_type(rule_data.get('type', 'str')),
                    required=rule_data.get('required', False),
                    default=rule_data.get('default'),
                    min_value=rule_data.get('min_value'),
                    max_value=rule_data.get('max_value'),
                    pattern=rule_data.get('pattern'),
                    enum_values=rule_data.get('enum'),
                ))
            
            self.schema = ConfigSchema(
                version=schema_data.get('version', '1.0'),
                description=schema_data.get('description', ''),
                rules=rules
            )
            
            logger.info(f"Loaded schema from {self.schema_path}")
            
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
    
    def _get_type(self, type_name: str) -> type:
        """Convertit un nom de type en type Python"""
        type_map = {
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'any': Any,
        }
        return type_map.get(type_name, str)
    
    # ============================================================
    # VALIDATION
    # ============================================================
    
    def _validate_config(self, config: Dict[str, Any]):
        """Valide la configuration"""
        if not self.schema:
            return
        
        errors = []
        warnings = []
        
        for rule in self.schema.rules:
            value = self._get_nested_value(config, rule.path)
            
            # Vérifier si requis
            if rule.required and value is None:
                errors.append(f"Required field missing: {rule.path}")
                continue
            
            if value is None:
                continue
            
            # Valider le type
            if rule.field_type != Any and not isinstance(value, rule.field_type):
                errors.append(
                    f"Field {rule.path} must be of type {rule.field_type.__name__}, "
                    f"got {type(value).__name__}"
                )
                continue
            
            # Valider les valeurs numériques
            if isinstance(value, (int, float)):
                if rule.min_value is not None and value < rule.min_value:
                    errors.append(
                        f"Field {rule.path} must be >= {rule.min_value}, got {value}"
                    )
                if rule.max_value is not None and value > rule.max_value:
                    errors.append(
                        f"Field {rule.path} must be <= {rule.max_value}, got {value}"
                    )
            
            # Valider le pattern (chaînes)
            if isinstance(value, str) and rule.pattern:
                if not re.match(rule.pattern, value):
                    errors.append(
                        f"Field {rule.path} does not match pattern: {rule.pattern}"
                    )
            
            # Valider les valeurs enum
            if rule.enum_values is not None and value not in rule.enum_values:
                errors.append(
                    f"Field {rule.path} must be one of {rule.enum_values}, got {value}"
                )
        
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(errors))
        
        if warnings:
            logger.warning(f"Configuration warnings:\n" + "\n".join(warnings))
    
    # ============================================================
    # ACCESS METHODS
    # ============================================================
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration
        
        Args:
            path: Chemin (ex: "bot.name")
            default: Valeur par défaut
            
        Returns:
            Any: Valeur de configuration
        """
        return self._get_nested_value(self.config, path, default)
    
    def set(self, path: str, value: Any, source: ConfigSource = ConfigSource.CLI, save: bool = True):
        """
        Définit une valeur de configuration
        
        Args:
            path: Chemin (ex: "bot.name")
            value: Valeur à définir
            source: Source de la modification
            save: Sauvegarder dans le fichier
        """
        # Appliquer la modification
        self._set_nested_value(self.config, path, value)
        
        # Enregistrer l'override
        self.overrides.append(ConfigOverride(path, value, source))
        self._modified = True
        
        # Sauvegarder si nécessaire
        if save and self.auto_save:
            self.save()
        
        logger.info(f"Configuration updated: {path} = {value} (source: {source.value})")
    
    def update(self, updates: Dict[str, Any], source: ConfigSource = ConfigSource.CLI, save: bool = True):
        """
        Met à jour plusieurs valeurs de configuration
        
        Args:
            updates: Dictionnaire des mises à jour
            source: Source des modifications
            save: Sauvegarder dans le fichier
        """
        for path, value in updates.items():
            self.set(path, value, source, save=False)
        
        if save and self.auto_save:
            self.save()
        
        logger.info(f"Configuration updated with {len(updates)} changes")
    
    def reset(self, path: Optional[str] = None):
        """
        Réinitialise la configuration
        
        Args:
            path: Chemin à réinitialiser (None pour tout réinitialiser)
        """
        if path is None:
            # Réinitialiser complètement
            self.config = copy.deepcopy(self.original_config)
            self.overrides = []
            self._modified = False
            logger.info("Configuration reset to original")
        else:
            # Réinitialiser une valeur spécifique
            original_value = self._get_nested_value(self.original_config, path)
            self._set_nested_value(self.config, path, original_value)
            self.overrides = [o for o in self.overrides if o.path != path]
            logger.info(f"Configuration reset: {path}")
    
    def save(self, file_path: Optional[str] = None) -> bool:
        """
        Sauvegarde la configuration dans un fichier
        
        Args:
            file_path: Chemin de sauvegarde
            
        Returns:
            bool: True si sauvegardé
        """
        path = Path(file_path) if file_path else self.config_path
        
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Préparer la configuration à sauvegarder
            config_to_save = copy.deepcopy(self.config)
            
            # Supprimer les valeurs sensibles
            self._cleanse_config(config_to_save)
            
            with open(path, 'w', encoding='utf-8') as f:
                if path.suffix in ['.yaml', '.yml']:
                    yaml.dump(config_to_save, f, default_flow_style=False, allow_unicode=True)
                elif path.suffix == '.json':
                    json.dump(config_to_save, f, indent=2, default=str)
                else:
                    logger.warning(f"Unsupported config file format: {path.suffix}")
                    return False
            
            self._modified = False
            logger.info(f"Configuration saved to {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def export(self, format: str = 'json') -> str:
        """
        Exporte la configuration
        
        Args:
            format: Format d'export ('json', 'yaml')
            
        Returns:
            str: Configuration exportée
        """
        if format == 'json':
            return json.dumps(self.config, indent=2, default=str)
        elif format == 'yaml':
            return yaml.dump(self.config, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_diff(self) -> Dict[str, Any]:
        """
        Récupère les différences entre la configuration actuelle et originale
        
        Returns:
            Dict[str, Any]: Différences
        """
        diff = {}
        self._get_diff_recursive(self.original_config, self.config, diff)
        return diff
    
    def _get_diff_recursive(self, original: Any, current: Any, diff: Dict[str, Any], path: str = ''):
        """Récupère récursivement les différences"""
        if original == current:
            return
        
        if isinstance(original, dict) and isinstance(current, dict):
            for key in set(original.keys()) | set(current.keys()):
                new_path = f"{path}.{key}" if path else key
                if key not in original:
                    diff[new_path] = {'old': None, 'new': current[key]}
                elif key not in current:
                    diff[new_path] = {'old': original[key], 'new': None}
                else:
                    self._get_diff_recursive(original[key], current[key], diff, new_path)
        else:
            diff[path] = {'old': original, 'new': current}
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _deep_merge(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Fusionne deux dictionnaires en profondeur"""
        result = copy.deepcopy(dict1)
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        
        return result
    
    def _get_nested_value(self, obj: Any, path: str, default: Any = None) -> Any:
        """Récupère une valeur imbriquée"""
        if not path:
            return obj
        
        parts = path.split('.')
        current = obj
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        return current
    
    def _set_nested_value(self, obj: Any, path: str, value: Any):
        """Définit une valeur imbriquée"""
        parts = path.split('.')
        current = obj
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
    
    def _cleanse_config(self, config: Dict[str, Any]):
        """Nettoie la configuration (supprime les valeurs sensibles)"""
        # Supprimer les clés sensibles
        sensitive_keys = ['password', 'secret', 'key', 'token', 'api_key']
        
        for key, value in list(config.items()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                config[key] = '***REDACTED***'
            elif isinstance(value, dict):
                self._cleanse_config(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._cleanse_config(item)
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques de configuration
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'environment': self.environment,
            'loaded_from': self._loaded_from.value,
            'modified': self._modified,
            'config_path': str(self.config_path) if self.config_path else None,
            'overrides_count': len(self.overrides),
            'schema_loaded': self.schema is not None,
            'config_size': len(str(self.config)),
            'total_keys': self._count_keys(self.config),
        }
    
    def _count_keys(self, obj: Any) -> int:
        """Compte le nombre de clés dans une structure imbriquée"""
        if isinstance(obj, dict):
            count = len(obj)
            for value in obj.values():
                if isinstance(value, dict):
                    count += self._count_keys(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            count += self._count_keys(item)
            return count
        return 0

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_config_manager: Optional[ConfigManager] = None

def get_config_manager(
    config_path: Optional[str] = None,
    environment: Optional[str] = None,
    force_new: bool = False
) -> ConfigManager:
    """
    Récupère le gestionnaire de configuration (singleton)
    
    Args:
        config_path: Chemin du fichier de configuration
        environment: Environnement
        force_new: Forcer la création d'une nouvelle instance
        
    Returns:
        ConfigManager: Gestionnaire de configuration
    """
    global _config_manager
    
    if _config_manager is None or force_new:
        _config_manager = ConfigManager(
            config_path=config_path,
            environment=environment
        )
    
    return _config_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ConfigEnvironment',
    'ConfigSource',
    'ConfigOverride',
    'ConfigValidationRule',
    'ConfigSchema',
    'ConfigManager',
    'get_config_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

import time
logger.info("Configuration manager module initialized")

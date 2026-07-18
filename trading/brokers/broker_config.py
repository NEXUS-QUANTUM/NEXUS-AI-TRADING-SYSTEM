# trading/brokers/broker_config.py
"""
NEXUS AI TRADING SYSTEM - Broker Configuration Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides configuration management for broker connections,
including loading from environment variables, YAML files, and runtime
configuration validation.
"""

import os
import json
import yaml
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import logging

from pydantic import BaseModel, Field, validator, root_validator, SecretStr
from cryptography.fernet import Fernet

from shared.utilities.logger import get_logger
from .base import BrokerName, AccountType, BrokerConfig

logger = get_logger(__name__)


# ============================================================================
# CONFIGURATION ENUMS AND MODELS
# ============================================================================

class EnvironmentType(str, Enum):
    """Environment types for broker configuration"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class BrokerEndpointConfig(BaseModel):
    """Configuration for broker API endpoints"""
    base_url: str
    websocket_url: Optional[str] = None
    sandbox_base_url: Optional[str] = None
    sandbox_websocket_url: Optional[str] = None
    api_version: Optional[str] = None
    endpoints: Dict[str, str] = Field(default_factory=dict)


class BrokerAuthConfig(BaseModel):
    """Configuration for broker authentication"""
    api_key: Optional[SecretStr] = None
    api_secret: Optional[SecretStr] = None
    api_passphrase: Optional[SecretStr] = None
    client_id: Optional[str] = None
    access_token: Optional[SecretStr] = None
    refresh_token: Optional[SecretStr] = None
    token_expires_at: Optional[datetime] = None
    oauth2_config: Dict[str, Any] = Field(default_factory=dict)
    auth_method: str = "api_key"  # api_key, oauth2, jwt, etc.
    
    @validator("api_key", pre=True)
    def validate_api_key_structure(cls, v, values):
        """Validate API key format based on broker type"""
        if v:
            # Basic validation - ensure it's not empty string
            if isinstance(v, str) and len(v.strip()) == 0:
                raise ValueError("API key cannot be empty")
        return v
    
    @validator("api_secret", pre=True)
    def validate_api_secret_structure(cls, v, values):
        """Validate API secret format based on broker type"""
        if v:
            if isinstance(v, str) and len(v.strip()) == 0:
                raise ValueError("API secret cannot be empty")
        return v
    
    class Config:
        arbitrary_types_allowed = True


class BrokerRateLimitConfig(BaseModel):
    """Configuration for rate limiting"""
    max_requests_per_second: Optional[int] = None
    max_requests_per_minute: Optional[int] = None
    max_requests_per_hour: Optional[int] = None
    max_requests_per_day: Optional[int] = None
    burst_allowance: int = 5
    retry_after: int = 60


class BrokerRetryConfig(BaseModel):
    """Configuration for retry behavior"""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
    retry_on_status_codes: List[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry_on_exceptions: List[str] = Field(
        default_factory=lambda: [
            "BrokerTimeoutError",
            "BrokerRateLimitError",
            "ConnectionError",
            "TimeoutError",
        ]
    )


class BrokerCircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker pattern"""
    enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    half_open_max_calls: int = 3


class BrokerTimeoutConfig(BaseModel):
    """Configuration for timeouts"""
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 30
    pool_timeout: int = 60


class BrokerMarketConfig(BaseModel):
    """Configuration for market data"""
    default_symbols: List[str] = Field(default_factory=list)
    default_timeframe: str = "1m"
    max_candles_per_request: int = 1000
    batch_size: int = 100
    websocket_reconnect_delay: float = 5.0
    data_feed_compression: bool = True


class BrokerOrderConfig(BaseModel):
    """Configuration for order management"""
    default_order_type: str = "limit"
    default_time_in_force: str = "GTC"
    max_order_size: Optional[float] = None
    min_order_size: Optional[float] = None
    order_size_step: Optional[float] = None
    price_step: Optional[float] = None
    allow_market_orders: bool = True
    allow_stop_orders: bool = True
    allow_trailing_stops: bool = False
    require_client_order_id: bool = True
    max_open_orders: Optional[int] = None


class BrokerRiskConfig(BaseModel):
    """Configuration for risk management"""
    max_leverage: float = 1.0
    max_position_size: Optional[float] = None
    max_portfolio_concentration: Optional[float] = None
    allowed_symbols: List[str] = Field(default_factory=list)
    blocked_symbols: List[str] = Field(default_factory=list)
    min_balance_required: Optional[float] = None
    margin_call_threshold: float = 0.7
    liquidation_threshold: float = 0.5


class BrokerLoggingConfig(BaseModel):
    """Configuration for logging"""
    log_requests: bool = True
    log_responses: bool = True
    log_headers: bool = False
    log_sensitive_data: bool = False
    mask_headers: List[str] = Field(default_factory=lambda: ["Authorization", "X-API-KEY", "API-SECRET"])
    request_log_format: str = "json"
    response_log_format: str = "json"


class BrokerSecurityConfig(BaseModel):
    """Configuration for security"""
    use_ssl_verification: bool = True
    encrypt_secrets: bool = True
    encryption_key: Optional[str] = None
    allowed_ips: List[str] = Field(default_factory=list)
    webhook_signature_key: Optional[str] = None
    ip_whitelist: List[str] = Field(default_factory=list)


class BrokerConfigComplete(BaseModel):
    """
    Complete broker configuration model.
    Contains all configuration sections for a broker connection.
    """
    # Core identification
    id: str = Field(default="default")
    name: BrokerName
    environment: EnvironmentType = EnvironmentType.DEVELOPMENT
    account_type: AccountType = AccountType.PAPER
    sandbox_mode: bool = True
    enabled: bool = True
    priority: int = 0  # For multi-broker setups
    
    # Configuration sections
    auth: BrokerAuthConfig = Field(default_factory=BrokerAuthConfig)
    endpoints: BrokerEndpointConfig = Field(default_factory=BrokerEndpointConfig)
    rate_limit: BrokerRateLimitConfig = Field(default_factory=BrokerRateLimitConfig)
    retry: BrokerRetryConfig = Field(default_factory=BrokerRetryConfig)
    circuit_breaker: BrokerCircuitBreakerConfig = Field(default_factory=BrokerCircuitBreakerConfig)
    timeout: BrokerTimeoutConfig = Field(default_factory=BrokerTimeoutConfig)
    market: BrokerMarketConfig = Field(default_factory=BrokerMarketConfig)
    order: BrokerOrderConfig = Field(default_factory=BrokerOrderConfig)
    risk: BrokerRiskConfig = Field(default_factory=BrokerRiskConfig)
    logging: BrokerLoggingConfig = Field(default_factory=BrokerLoggingConfig)
    security: BrokerSecurityConfig = Field(default_factory=BrokerSecurityConfig)
    
    # Additional settings
    extra: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @root_validator
    def validate_config(cls, values):
        """Validate the complete configuration"""
        # Check that sandbox endpoints are provided when in sandbox mode
        if values.get("sandbox_mode", True):
            endpoints = values.get("endpoints")
            if endpoints and not endpoints.sandbox_base_url:
                logger.warning(f"Sandbox base URL not configured for {values.get('name')}")
        
        # Validate allowed/blocked symbols are mutually exclusive in risk config
        risk = values.get("risk")
        if risk:
            if risk.allowed_symbols and risk.blocked_symbols:
                logger.warning("Both allowed_symbols and blocked_symbols are configured - allowed_symbols takes precedence")
        
        return values
    
    def to_broker_config(self) -> BrokerConfig:
        """
        Convert to simple BrokerConfig for broker instantiation.
        
        Returns:
            BrokerConfig: Simple configuration
        """
        base_url = self.endpoints.base_url
        if self.sandbox_mode and self.endpoints.sandbox_base_url:
            base_url = self.endpoints.sandbox_base_url
        
        websocket_url = self.endpoints.websocket_url
        if self.sandbox_mode and self.endpoints.sandbox_websocket_url:
            websocket_url = self.endpoints.sandbox_websocket_url
        
        return BrokerConfig(
            broker_name=self.name,
            api_key=self.auth.api_key.get_secret_value() if self.auth.api_key else None,
            api_secret=self.auth.api_secret.get_secret_value() if self.auth.api_secret else None,
            api_passphrase=self.auth.api_passphrase.get_secret_value() if self.auth.api_passphrase else None,
            sandbox_mode=self.sandbox_mode,
            account_type=self.account_type,
            timeout=self.timeout.read_timeout,
            max_retries=self.retry.max_retries,
            retry_delay=self.retry.initial_delay,
            rate_limit_per_second=self.rate_limit.max_requests_per_second,
            base_url=base_url,
            websocket_url=websocket_url,
            use_ssl_verification=self.security.use_ssl_verification,
            extra_params={
                "id": self.id,
                "environment": self.environment.value,
                "priority": self.priority,
                **self.extra,
            },
        )
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            SecretStr: lambda v: "***REDACTED***" if v else None,
        }


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================

class BrokerConfigLoader:
    """
    Loads and manages broker configurations from various sources.
    
    Supports:
    - Environment variables
    - YAML files
    - JSON files
    - Encrypted secrets
    - Runtime configuration
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir or Path("configs/brokers")
        self.configs: Dict[str, BrokerConfigComplete] = {}
        self._default_config: Optional[BrokerConfigComplete] = None
        self._encryption_key: Optional[str] = None
        self._fernet: Optional[Fernet] = None
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_fernet(self) -> Fernet:
        """Get or create Fernet instance for encryption"""
        if not self._fernet:
            key = self._encryption_key or os.getenv("NEXUS_SECRET_KEY")
            if not key:
                logger.warning("No encryption key found - secrets will not be encrypted")
                return None
            
            # Ensure key is valid Fernet key (base64 url-safe, 32 bytes)
            try:
                if len(key) < 32:
                    # Use as seed to generate deterministic key
                    key = base64.urlsafe_b64encode(key.encode().ljust(32)[:32])
                elif len(key) != 44:
                    # Try to decode as base64
                    try:
                        key = base64.urlsafe_b64decode(key + "=" * (4 - len(key) % 4))
                        key = base64.urlsafe_b64encode(key)
                    except:
                        key = base64.urlsafe_b64encode(key.encode().ljust(32)[:32])
                
                self._fernet = Fernet(key)
            except Exception as e:
                logger.error(f"Failed to create Fernet instance: {e}")
                return None
        
        return self._fernet
    
    def _decrypt_secret(self, encrypted_value: Union[str, SecretStr]) -> Optional[SecretStr]:
        """
        Decrypt an encrypted secret value.
        
        Args:
            encrypted_value: Encrypted value as string or SecretStr
            
        Returns:
            Optional[SecretStr]: Decrypted value as SecretStr
        """
        if not encrypted_value:
            return None
        
        fernet = self._get_fernet()
        if not fernet:
            return None
        
        try:
            if isinstance(encrypted_value, SecretStr):
                encrypted_value = encrypted_value.get_secret_value()
            
            # Remove any whitespace or quotes
            encrypted_value = encrypted_value.strip().strip('"').strip("'")
            
            decrypted = fernet.decrypt(encrypted_value.encode()).decode()
            return SecretStr(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            return None
    
    def _encrypt_secret(self, value: Union[str, SecretStr]) -> Optional[str]:
        """
        Encrypt a secret value.
        
        Args:
            value: Value to encrypt
            
        Returns:
            Optional[str]: Encrypted value as string
        """
        if not value:
            return None
        
        fernet = self._get_fernet()
        if not fernet:
            return None
        
        try:
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            
            encrypted = fernet.encrypt(value.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt secret: {e}")
            return None
    
    def _process_secrets(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and decrypt secrets in the configuration.
        
        Handles:
        - Encrypted values in auth section
        - Nested dictionaries
        - Lists
        """
        if not isinstance(config, dict):
            return config
        
        result = {}
        for key, value in config.items():
            if key == "encryption_key":
                result[key] = value
                continue
            
            if isinstance(value, dict):
                result[key] = self._process_secrets(value)
            elif isinstance(value, list):
                result[key] = [
                    self._process_secrets(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, str):
                # Check if it's an encrypted value (starts with "encrypted:")
                if value.startswith("encrypted:"):
                    encrypted_part = value.replace("encrypted:", "", 1)
                    decrypted = self._decrypt_secret(encrypted_part)
                    result[key] = decrypted.get_secret_value() if decrypted else None
                elif "SECRET" in key.upper() or "KEY" in key.upper():
                    # Might be a secret - keep as is (will be converted to SecretStr later)
                    result[key] = value
                else:
                    result[key] = value
            else:
                result[key] = value
        
        return result
    
    def load_from_env(self, prefix: str = "NEXUS_BROKER_") -> List[BrokerConfigComplete]:
        """
        Load broker configuration from environment variables.
        
        Environment variables format:
        NEXUS_BROKER_{BROKER_NAME}_API_KEY=xxx
        NEXUS_BROKER_{BROKER_NAME}_API_SECRET=xxx
        NEXUS_BROKER_{BROKER_NAME}_SANDBOX=true/false
        NEXUS_BROKER_{BROKER_NAME}_BASE_URL=xxx
        """
        configs = []
        
        # Group environment variables by broker
        broker_vars: Dict[str, Dict[str, Any]] = {}
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(prefix):
                continue
            
            # Parse key: NEXUS_BROKER_BINANCE_API_KEY -> (BINANCE, API_KEY)
            parts = env_key[len(prefix):].split("_", 1)
            if len(parts) != 2:
                continue
            
            broker_name, param_name = parts
            broker_name = broker_name.lower()
            
            if broker_name not in broker_vars:
                broker_vars[broker_name] = {}
            
            # Handle special parameters
            if param_name == "API_KEY":
                broker_vars[broker_name]["api_key"] = env_value
            elif param_name == "API_SECRET":
                broker_vars[broker_name]["api_secret"] = env_value
            elif param_name == "API_PASSPHRASE":
                broker_vars[broker_name]["api_passphrase"] = env_value
            elif param_name == "SANDBOX":
                broker_vars[broker_name]["sandbox_mode"] = env_value.lower() == "true"
            elif param_name == "BASE_URL":
                broker_vars[broker_name]["base_url"] = env_value
            elif param_name == "WEBSOCKET_URL":
                broker_vars[broker_name]["websocket_url"] = env_value
            elif param_name == "ENVIRONMENT":
                broker_vars[broker_name]["environment"] = env_value
            elif param_name == "ACCOUNT_TYPE":
                broker_vars[broker_name]["account_type"] = env_value
            else:
                # Store other parameters in extra
                if "extra" not in broker_vars[broker_name]:
                    broker_vars[broker_name]["extra"] = {}
                broker_vars[broker_name]["extra"][param_name] = env_value
        
        # Create configuration for each broker
        for broker_name, vars_dict in broker_vars.items():
            try:
                config = self._create_config_from_env(broker_name, vars_dict)
                if config:
                    configs.append(config)
            except Exception as e:
                logger.error(f"Failed to load config for broker {broker_name}: {e}")
        
        return configs
    
    def _create_config_from_env(self, broker_name: str, vars_dict: Dict[str, Any]) -> Optional[BrokerConfigComplete]:
        """
        Create a configuration object from environment variables.
        
        Args:
            broker_name: Name of the broker
            vars_dict: Dictionary of configuration variables
            
        Returns:
            Optional[BrokerConfigComplete]: Configuration object
        """
        try:
            # Parse broker name
            try:
                broker_enum = BrokerName(broker_name.lower())
            except ValueError:
                logger.warning(f"Unknown broker name: {broker_name}")
                return None
            
            # Build configuration
            config = BrokerConfigComplete(
                name=broker_enum,
                id=os.getenv(f"NEXUS_BROKER_{broker_name.upper()}_ID", broker_name),
                environment=EnvironmentType(vars_dict.get("environment", "development")),
                account_type=AccountType(vars_dict.get("account_type", "paper")),
                sandbox_mode=vars_dict.get("sandbox_mode", True),
                auth=BrokerAuthConfig(
                    api_key=SecretStr(vars_dict.get("api_key", "")) if vars_dict.get("api_key") else None,
                    api_secret=SecretStr(vars_dict.get("api_secret", "")) if vars_dict.get("api_secret") else None,
                    api_passphrase=SecretStr(vars_dict.get("api_passphrase", "")) if vars_dict.get("api_passphrase") else None,
                ),
                endpoints=BrokerEndpointConfig(
                    base_url=vars_dict.get("base_url", ""),
                    websocket_url=vars_dict.get("websocket_url", ""),
                ),
                extra=vars_dict.get("extra", {}),
            )
            
            return config
        except Exception as e:
            logger.error(f"Failed to create config from env for {broker_name}: {e}")
            return None
    
    def load_from_file(self, file_path: Union[str, Path]) -> List[BrokerConfigComplete]:
        """
        Load broker configuration from a file.
        
        Supported formats:
        - YAML (.yaml, .yml)
        - JSON (.json)
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            List[BrokerConfigComplete]: List of configuration objects
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"Config file not found: {file_path}")
            return []
        
        configs = []
        
        try:
            with open(file_path, "r") as f:
                if file_path.suffix in [".yaml", ".yml"]:
                    data = yaml.safe_load(f)
                elif file_path.suffix == ".json":
                    data = json.load(f)
                else:
                    logger.warning(f"Unsupported file format: {file_path.suffix}")
                    return []
            
            # Handle single broker config or list of configs
            if isinstance(data, dict):
                data = [data]
            
            for config_data in data:
                try:
                    # Process any encrypted secrets
                    config_data = self._process_secrets(config_data)
                    
                    # Convert string broker names to enum
                    if "name" in config_data and isinstance(config_data["name"], str):
                        config_data["name"] = BrokerName(config_data["name"].lower())
                    
                    # Convert environment string to enum
                    if "environment" in config_data and isinstance(config_data["environment"], str):
                        config_data["environment"] = EnvironmentType(config_data["environment"].lower())
                    
                    # Convert account_type string to enum
                    if "account_type" in config_data and isinstance(config_data["account_type"], str):
                        config_data["account_type"] = AccountType(config_data["account_type"].lower())
                    
                    config = BrokerConfigComplete(**config_data)
                    configs.append(config)
                except Exception as e:
                    logger.error(f"Failed to parse config from {file_path}: {e}")
                    if file_path.suffix in [".yaml", ".yml"]:
                        import traceback
                        logger.debug(traceback.format_exc())
        
        except Exception as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
        
        return configs
    
    def load_from_directory(self, directory: Optional[Path] = None) -> List[BrokerConfigComplete]:
        """
        Load all broker configurations from a directory.
        
        Args:
            directory: Directory containing configuration files
            
        Returns:
            List[BrokerConfigComplete]: List of configuration objects
        """
        directory = directory or self.config_dir
        configs = []
        
        # Load all config files from directory
        for file_path in directory.glob("*"):
            if file_path.is_dir():
                continue
            
            if file_path.suffix in [".yaml", ".yml", ".json"]:
                try:
                    loaded = self.load_from_file(file_path)
                    configs.extend(loaded)
                except Exception as e:
                    logger.error(f"Failed to load {file_path}: {e}")
        
        return configs
    
    def load_all(self) -> Dict[str, BrokerConfigComplete]:
        """
        Load all configurations from all sources.
        
        Sources in order of precedence (later overrides earlier):
        1. Files from config directory
        2. Environment variables
        
        Returns:
            Dict[str, BrokerConfigComplete]: Dictionary of broker configurations
        """
        # First load from files
        configs = self.load_from_directory()
        
        # Then load from environment (overrides file configs)
        env_configs = self.load_from_env()
        
        # Merge configurations
        merged = {}
        for config in configs:
            merged[config.id] = config
        
        for config in env_configs:
            if config.id in merged:
                # Merge with existing config (prefer environment values)
                existing = merged[config.id]
                # Update only if environment values are present
                if config.auth.api_key:
                    existing.auth.api_key = config.auth.api_key
                if config.auth.api_secret:
                    existing.auth.api_secret = config.auth.api_secret
                if config.sandbox_mode != existing.sandbox_mode:
                    existing.sandbox_mode = config.sandbox_mode
                # ... merge other fields
            else:
                merged[config.id] = config
        
        self.configs = merged
        return merged
    
    def get_config(self, broker_id: str) -> Optional[BrokerConfigComplete]:
        """
        Get a specific broker configuration by ID.
        
        Args:
            broker_id: Broker configuration ID
            
        Returns:
            Optional[BrokerConfigComplete]: Configuration or None if not found
        """
        return self.configs.get(broker_id)
    
    def get_config_for_broker(self, broker_name: BrokerName) -> List[BrokerConfigComplete]:
        """
        Get all configurations for a specific broker type.
        
        Args:
            broker_name: Name of the broker
            
        Returns:
            List[BrokerConfigComplete]: List of matching configurations
        """
        return [
            config for config in self.configs.values()
            if config.name == broker_name and config.enabled
        ]
    
    def get_default_config(self) -> Optional[BrokerConfigComplete]:
        """
        Get the default broker configuration.
        
        Returns:
            Optional[BrokerConfigComplete]: Default configuration or None
        """
        if self._default_config:
            return self._default_config
        
        # Find the first enabled configuration
        for config in self.configs.values():
            if config.enabled:
                self._default_config = config
                return config
        
        return None
    
    def set_default_config(self, broker_id: str) -> bool:
        """
        Set the default broker configuration.
        
        Args:
            broker_id: ID of the configuration to set as default
            
        Returns:
            bool: True if configuration was found and set
        """
        config = self.get_config(broker_id)
        if config:
            self._default_config = config
            return True
        return False
    
    def save_config(self, config: BrokerConfigComplete, file_path: Optional[Path] = None) -> bool:
        """
        Save a broker configuration to a file.
        
        Args:
            config: Configuration to save
            file_path: Path to save to (defaults to config_dir/{config.id}.yaml)
            
        Returns:
            bool: True if save was successful
        """
        try:
            if not file_path:
                file_path = self.config_dir / f"{config.id}.yaml"
            
            # Convert to dict for serialization
            config_dict = config.dict()
            
            # Convert SecretStr to string (or encrypt it)
            self._serialize_secrets(config_dict)
            
            # Save as YAML
            with open(file_path, "w") as f:
                yaml.dump(config_dict, f, default_flow_style=False)
            
            logger.info(f"Saved broker config to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def _serialize_secrets(self, data: Union[Dict, Any]) -> Any:
        """
        Serialize secrets in the configuration.
        
        Args:
            data: Data to serialize
            
        Returns:
            Any: Serialized data with secrets processed
        """
        if isinstance(data, dict):
            for key, value in list(data.items()):
                if isinstance(value, SecretStr):
                    data[key] = "***REDACTED***"  # Don't save raw secrets
                elif isinstance(value, dict):
                    self._serialize_secrets(value)
                elif isinstance(value, list):
                    for item in value:
                        self._serialize_secrets(item)
        return data
    
    def create_default_config(
        self,
        broker_name: BrokerName,
        api_key: str = "",
        api_secret: str = "",
        sandbox_mode: bool = True,
    ) -> BrokerConfigComplete:
        """
        Create a default configuration for a broker.
        
        Args:
            broker_name: Name of the broker
            api_key: API key
            api_secret: API secret
            sandbox_mode: Whether to use sandbox mode
            
        Returns:
            BrokerConfigComplete: Default configuration
        """
        # Get default endpoint URLs based on broker
        endpoints = self._get_default_endpoints(broker_name)
        
        return BrokerConfigComplete(
            id=f"{broker_name.value}_default",
            name=broker_name,
            environment=EnvironmentType.DEVELOPMENT,
            account_type=AccountType.PAPER if sandbox_mode else AccountType.LIVE,
            sandbox_mode=sandbox_mode,
            auth=BrokerAuthConfig(
                api_key=SecretStr(api_key) if api_key else None,
                api_secret=SecretStr(api_secret) if api_secret else None,
            ),
            endpoints=endpoints,
            order=BrokerOrderConfig(
                default_order_type="limit",
                default_time_in_force="GTC",
                allow_market_orders=True,
                allow_stop_orders=True,
            ),
            risk=BrokerRiskConfig(
                max_leverage=1.0,
            ),
        )
    
    def _get_default_endpoints(self, broker_name: BrokerName) -> BrokerEndpointConfig:
        """
        Get default endpoints for a broker.
        
        Args:
            broker_name: Name of the broker
            
        Returns:
            BrokerEndpointConfig: Default endpoints
        """
        default_endpoints = {
            BrokerName.BINANCE: BrokerEndpointConfig(
                base_url="https://api.binance.com/api/v3",
                sandbox_base_url="https://testnet.binance.vision/api/v3",
                websocket_url="wss://stream.binance.com:9443/ws",
                sandbox_websocket_url="wss://testnet.binance.vision/ws",
                endpoints={
                    "account": "/account",
                    "order": "/order",
                    "open_orders": "/openOrders",
                    "ticker": "/ticker/price",
                    "klines": "/klines",
                },
            ),
            BrokerName.BYBIT: BrokerEndpointConfig(
                base_url="https://api.bybit.com/v5",
                sandbox_base_url="https://api-testnet.bybit.com/v5",
                websocket_url="wss://stream.bybit.com/v5/public/spot",
                sandbox_websocket_url="wss://stream-testnet.bybit.com/v5/public/spot",
                endpoints={
                    "account": "/account/info",
                    "order": "/order/create",
                    "open_orders": "/order/realtime",
                    "ticker": "/market/tickers",
                    "klines": "/market/kline",
                },
            ),
            BrokerName.COINBASE: BrokerEndpointConfig(
                base_url="https://api.coinbase.com/api/v3",
                sandbox_base_url="https://api-public.sandbox.coinbase.com/api/v3",
                websocket_url="wss://ws-feed.coinbase.com",
                sandbox_websocket_url="wss://ws-feed-public.sandbox.coinbase.com",
                endpoints={
                    "account": "/accounts",
                    "order": "/orders",
                    "open_orders": "/orders/open",
                    "ticker": "/prices",
                    "klines": "/candles",
                },
            ),
            BrokerName.KRAKEN: BrokerEndpointConfig(
                base_url="https://api.kraken.com/0",
                sandbox_base_url="https://api.kraken.com/0",
                websocket_url="wss://ws.kraken.com",
                sandbox_websocket_url="wss://ws.kraken.com",
                endpoints={
                    "account": "/private/Balance",
                    "order": "/private/AddOrder",
                    "open_orders": "/private/OpenOrders",
                    "ticker": "/public/Ticker",
                    "klines": "/public/OHLC",
                },
            ),
            BrokerName.ALPACA: BrokerEndpointConfig(
                base_url="https://api.alpaca.markets",
                sandbox_base_url="https://paper-api.alpaca.markets",
                websocket_url="wss://stream.data.alpaca.markets/v2/iex",
                sandbox_websocket_url="wss://stream.data.alpaca.markets/v2/iex",
                endpoints={
                    "account": "/v2/account",
                    "order": "/v2/orders",
                    "open_orders": "/v2/orders?status=open",
                    "ticker": "/v2/stocks/trades",
                    "klines": "/v2/stocks/bars",
                },
            ),
            BrokerName.PAPER: BrokerEndpointConfig(
                base_url="",
                websocket_url="",
            ),
            BrokerName.WEBHOOK: BrokerEndpointConfig(
                base_url="",
                websocket_url="",
            ),
        }
        
        return default_endpoints.get(broker_name, BrokerEndpointConfig())
    
    def validate_configuration(self, config: BrokerConfigComplete) -> List[str]:
        """
        Validate a broker configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required fields for live trading
        if config.account_type == AccountType.LIVE:
            if not config.auth.api_key:
                errors.append("API key is required for live trading")
            if not config.auth.api_secret:
                errors.append("API secret is required for live trading")
        
        # Check endpoint URLs
        if config.name != BrokerName.PAPER and config.name != BrokerName.WEBHOOK:
            if config.sandbox_mode and not config.endpoints.sandbox_base_url:
                errors.append("Sandbox base URL is required for sandbox mode")
            elif not config.sandbox_mode and not config.endpoints.base_url:
                errors.append("Base URL is required for live mode")
        
        # Check rate limit configuration
        if config.rate_limit.max_requests_per_second:
            if config.rate_limit.max_requests_per_second <= 0:
                errors.append("Rate limit per second must be positive")
        
        # Check risk configuration
        if config.risk.max_leverage <= 0:
            errors.append("Max leverage must be positive")
        if config.risk.max_leverage > 10:
            errors.append("Max leverage is too high (max 10x)")
        
        return errors


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "EnvironmentType",
    
    # Models
    "BrokerEndpointConfig",
    "BrokerAuthConfig",
    "BrokerRateLimitConfig",
    "BrokerRetryConfig",
    "BrokerCircuitBreakerConfig",
    "BrokerTimeoutConfig",
    "BrokerMarketConfig",
    "BrokerOrderConfig",
    "BrokerRiskConfig",
    "BrokerLoggingConfig",
    "BrokerSecurityConfig",
    "BrokerConfigComplete",
    
    # Loader
    "BrokerConfigLoader",
]

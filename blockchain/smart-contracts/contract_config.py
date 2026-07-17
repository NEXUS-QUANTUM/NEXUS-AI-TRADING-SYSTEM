# blockchain/smart-contracts/contract_config.py
# NEXUS AI TRADING SYSTEM - Smart Contract Configuration Management
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Comprehensive Smart Contract Configuration Management System.
Provides configuration management for smart contracts across multiple chains,
protocols, and deployment environments. Supports versioning, validation,
and dynamic configuration updates.
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml
from pydantic import BaseModel, Field, validator
from web3 import Web3

# NEXUS Imports
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.config")


# ============================================================================
# Enums & Constants
# ============================================================================

class NetworkType(str, Enum):
    """Network types."""
    MAINNET = "mainnet"
    TESTNET = "testnet"
    DEVNET = "devnet"
    LOCAL = "local"
    CUSTOM = "custom"


class ContractState(str, Enum):
    """Contract deployment state."""
    DRAFT = "draft"
    DEPLOYED = "deployed"
    VERIFIED = "verified"
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ContractType(str, Enum):
    """Contract types."""
    TOKEN = "token"
    DEX = "dex"
    LENDING = "lending"
    STAKING = "staking"
    GOVERNANCE = "governance"
    VAULT = "vault"
    ORACLE = "oracle"
    BRIDGE = "bridge"
    AGGREGATOR = "aggregator"
    PROXY = "proxy"
    IMPLEMENTATION = "implementation"
    FACTORY = "factory"
    UTILITY = "utility"


class ConfigSource(str, Enum):
    """Configuration source."""
    FILE = "file"
    ENVIRONMENT = "environment"
    DATABASE = "database"
    REMOTE = "remote"
    CACHE = "cache"
    DEFAULT = "default"


@dataclass
class ContractConfig:
    """Contract configuration."""
    address: str
    name: str
    chain_id: int
    network: NetworkType
    contract_type: ContractType
    state: ContractState
    abi: Optional[List[Dict[str, Any]]] = None
    bytecode: Optional[str] = None
    deployed_at: Optional[datetime] = None
    deployed_by: Optional[str] = None
    version: str = "1.0.0"
    implementation: Optional[str] = None
    proxy: Optional[str] = None
    factory: Optional[str] = None
    block_number: Optional[int] = None
    transaction_hash: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    permissions: Dict[str, List[str]] = field(default_factory=dict)
    features: Dict[str, bool] = field(default_factory=dict)
    limits: Dict[str, Any] = field(default_factory=dict)
    security: Dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


@dataclass
class EnvironmentConfig:
    """Environment configuration."""
    name: str
    network: NetworkType
    chain_id: int
    rpc_urls: List[str]
    ws_urls: List[str]
    explorer_urls: List[str]
    gas_config: Dict[str, Any]
    contracts: Dict[str, ContractConfig]
    global_params: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, bool] = field(default_factory=dict)
    security_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentConfig:
    """Deployment configuration."""
    environment: str
    contracts: List[Dict[str, Any]]
    order: List[str]
    params: Dict[str, Any]
    gas_config: Dict[str, Any]
    verification: Dict[str, Any]
    hooks: Dict[str, Any]


# ============================================================================
# Configuration Manager
# ============================================================================

class ContractConfigManager:
    """
    Smart Contract Configuration Management System.
    Provides configuration management for contracts across multiple chains.
    """

    # Default configurations
    DEFAULT_CONFIG = {
        "environment": "development",
        "network": "local",
        "chain_id": 31337,
        "gas_config": {
            "gas_price": "auto",
            "gas_limit": "auto",
            "priority_fee": "auto",
        },
        "verification": {
            "enabled": False,
            "explorer": "etherscan",
            "api_key": None,
        },
    }

    # Chain configurations
    CHAIN_CONFIGS = {
        1: {"name": "Ethereum", "network": NetworkType.MAINNET, "currency": "ETH"},
        5: {"name": "Goerli", "network": NetworkType.TESTNET, "currency": "ETH"},
        11155111: {"name": "Sepolia", "network": NetworkType.TESTNET, "currency": "ETH"},
        56: {"name": "BNB Chain", "network": NetworkType.MAINNET, "currency": "BNB"},
        97: {"name": "BSC Testnet", "network": NetworkType.TESTNET, "currency": "BNB"},
        137: {"name": "Polygon", "network": NetworkType.MAINNET, "currency": "MATIC"},
        80001: {"name": "Mumbai", "network": NetworkType.TESTNET, "currency": "MATIC"},
        42161: {"name": "Arbitrum", "network": NetworkType.MAINNET, "currency": "ETH"},
        421613: {"name": "Arbitrum Goerli", "network": NetworkType.TESTNET, "currency": "ETH"},
        10: {"name": "Optimism", "network": NetworkType.MAINNET, "currency": "ETH"},
        420: {"name": "Optimism Goerli", "network": NetworkType.TESTNET, "currency": "ETH"},
        43114: {"name": "Avalanche", "network": NetworkType.MAINNET, "currency": "AVAX"},
        43113: {"name": "Fuji", "network": NetworkType.TESTNET, "currency": "AVAX"},
        250: {"name": "Fantom", "network": NetworkType.MAINNET, "currency": "FTM"},
        4002: {"name": "Fantom Testnet", "network": NetworkType.TESTNET, "currency": "FTM"},
        31337: {"name": "Hardhat Local", "network": NetworkType.LOCAL, "currency": "ETH"},
    }

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config_dir = config_dir or Path("configs/blockchain")
        self.config = config or {}

        # Configuration storage
        self._configs: Dict[str, ContractConfig] = {}
        self._environments: Dict[str, EnvironmentConfig] = {}
        self._deployments: Dict[str, DeploymentConfig] = {}

        # Chain configurations
        self._chain_configs = self.CHAIN_CONFIGS.copy()

        # State management
        self._loaded = False
        self._lock = asyncio.Lock()

        # Validation schemas
        self._schemas = self._load_schemas()

        # Performance metrics
        self._performance = {
            "configs_loaded": 0,
            "configs_updated": 0,
            "validations_performed": 0,
            "validation_errors": 0,
        }

        logger.info("ContractConfigManager initialized")

    # -----------------------------------------------------------------------
    # Configuration Loading
    # -----------------------------------------------------------------------

    async def load_configuration(
        self,
        environment: Optional[str] = None,
        force_reload: bool = False,
    ) -> bool:
        """
        Load configuration from files.

        Args:
            environment: Environment name
            force_reload: Force reload

        Returns:
            True if successful
        """
        if self._loaded and not force_reload:
            return True

        async with self._lock:
            try:
                # Load global config
                global_config = await self._load_global_config()

                # Load environment config
                env = environment or global_config.get("environment", "development")
                env_config = await self._load_environment_config(env)

                if env_config:
                    self._environments[env] = env_config

                # Load contract configs
                await self._load_contract_configs(env)

                # Load deployment configs
                await self._load_deployment_configs(env)

                self._loaded = True
                self._performance["configs_loaded"] += 1

                logger.info(
                    f"Configuration loaded",
                    extra={
                        "environment": env,
                        "contracts": len(self._configs),
                    }
                )

                return True

            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                return False

    async def _load_global_config(self) -> Dict[str, Any]:
        """Load global configuration."""
        global_config = self.DEFAULT_CONFIG.copy()

        # Check for global config file
        global_file = self.config_dir / "global.yaml"
        if global_file.exists():
            try:
                with open(global_file, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        global_config.update(file_config)
            except Exception as e:
                logger.error(f"Error loading global config: {e}")

        return global_config

    async def _load_environment_config(
        self,
        environment: str,
    ) -> Optional[EnvironmentConfig]:
        """Load environment configuration."""
        env_file = self.config_dir / f"{environment}.yaml"

        if not env_file.exists():
            logger.warning(f"Environment config not found: {environment}")
            return None

        try:
            with open(env_file, 'r') as f:
                data = yaml.safe_load(f)

            # Get chain config
            chain_id = data.get("chain_id", 1)
            chain_config = self._chain_configs.get(chain_id, {})

            # Build environment config
            return EnvironmentConfig(
                name=environment,
                network=NetworkType(data.get("network", chain_config.get("network", "mainnet"))),
                chain_id=chain_id,
                rpc_urls=data.get("rpc_urls", []),
                ws_urls=data.get("ws_urls", []),
                explorer_urls=data.get("explorer_urls", []),
                gas_config=data.get("gas_config", {}),
                contracts={},
                global_params=data.get("params", {}),
                features=data.get("features", {}),
                security_config=data.get("security", {}),
            )

        except Exception as e:
            logger.error(f"Error loading environment config: {e}")
            return None

    async def _load_contract_configs(self, environment: str) -> None:
        """Load contract configurations."""
        contracts_dir = self.config_dir / "contracts" / environment

        if not contracts_dir.exists():
            logger.warning(f"Contracts directory not found: {contracts_dir}")
            return

        for contract_file in contracts_dir.glob("*.yaml"):
            try:
                with open(contract_file, 'r') as f:
                    data = yaml.safe_load(f)

                if not data:
                    continue

                # Create contract config
                config = ContractConfig(
                    address=data.get("address", ""),
                    name=data.get("name", contract_file.stem),
                    chain_id=data.get("chain_id", 1),
                    network=NetworkType(data.get("network", "mainnet")),
                    contract_type=ContractType(data.get("type", "utility")),
                    state=ContractState(data.get("state", "draft")),
                    abi=data.get("abi"),
                    bytecode=data.get("bytecode"),
                    version=data.get("version", "1.0.0"),
                    implementation=data.get("implementation"),
                    proxy=data.get("proxy"),
                    factory=data.get("factory"),
                    block_number=data.get("block_number"),
                    transaction_hash=data.get("transaction_hash"),
                    params=data.get("params", {}),
                    metadata=data.get("metadata", {}),
                    tags=data.get("tags", []),
                    dependencies=data.get("dependencies", {}),
                    permissions=data.get("permissions", {}),
                    features=data.get("features", {}),
                    limits=data.get("limits", {}),
                    security=data.get("security", {}),
                )

                self._configs[config.name] = config

            except Exception as e:
                logger.error(f"Error loading contract config {contract_file}: {e}")

    async def _load_deployment_configs(self, environment: str) -> None:
        """Load deployment configurations."""
        deploy_file = self.config_dir / "deployments" / f"{environment}.yaml"

        if not deploy_file.exists():
            return

        try:
            with open(deploy_file, 'r') as f:
                data = yaml.safe_load(f)

            self._deployments[environment] = DeploymentConfig(
                environment=environment,
                contracts=data.get("contracts", []),
                order=data.get("order", []),
                params=data.get("params", {}),
                gas_config=data.get("gas", {}),
                verification=data.get("verification", {}),
                hooks=data.get("hooks", {}),
            )

        except Exception as e:
            logger.error(f"Error loading deployment config: {e}")

    # -----------------------------------------------------------------------
    # Configuration Management
    # -----------------------------------------------------------------------

    def get_contract_config(
        self,
        name: str,
        raise_on_error: bool = False,
    ) -> Optional[ContractConfig]:
        """
        Get contract configuration by name.

        Args:
            name: Contract name
            raise_on_error: Raise exception if not found

        Returns:
            ContractConfig or None
        """
        config = self._configs.get(name)

        if not config and raise_on_error:
            raise ValueError(f"Contract config not found: {name}")

        return config

    def get_contract_config_by_address(
        self,
        address: str,
    ) -> Optional[ContractConfig]:
        """
        Get contract configuration by address.

        Args:
            address: Contract address

        Returns:
            ContractConfig or None
        """
        address = Web3.to_checksum_address(address)

        for config in self._configs.values():
            if config.address and Web3.to_checksum_address(config.address) == address:
                return config

        return None

    def get_contracts_by_type(
        self,
        contract_type: ContractType,
    ) -> List[ContractConfig]:
        """
        Get contracts by type.

        Args:
            contract_type: Contract type

        Returns:
            List of ContractConfig
        """
        return [
            config for config in self._configs.values()
            if config.contract_type == contract_type
        ]

    def get_contracts_by_state(
        self,
        state: ContractState,
    ) -> List[ContractConfig]:
        """
        Get contracts by state.

        Args:
            state: Contract state

        Returns:
            List of ContractConfig
        """
        return [
            config for config in self._configs.values()
            if config.state == state
        ]

    def get_contracts_by_tag(
        self,
        tag: str,
    ) -> List[ContractConfig]:
        """
        Get contracts by tag.

        Args:
            tag: Tag name

        Returns:
            List of ContractConfig
        """
        return [
            config for config in self._configs.values()
            if tag in config.tags
        ]

    async def add_contract_config(
        self,
        config: ContractConfig,
        overwrite: bool = False,
    ) -> bool:
        """
        Add a contract configuration.

        Args:
            config: ContractConfig
            overwrite: Overwrite existing

        Returns:
            True if successful
        """
        async with self._lock:
            if config.name in self._configs and not overwrite:
                logger.warning(f"Contract config already exists: {config.name}")
                return False

            # Validate config
            if not await self.validate_contract_config(config):
                logger.error(f"Invalid contract config: {config.name}")
                return False

            self._configs[config.name] = config
            self._performance["configs_updated"] += 1

            logger.info(f"Added contract config: {config.name}")
            return True

    async def update_contract_config(
        self,
        name: str,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Update a contract configuration.

        Args:
            name: Contract name
            updates: Updates to apply

        Returns:
            True if successful
        """
        async with self._lock:
            config = self._configs.get(name)

            if not config:
                logger.error(f"Contract config not found: {name}")
                return False

            # Apply updates
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            # Validate updated config
            if not await self.validate_contract_config(config):
                logger.error(f"Invalid contract config after update: {name}")
                return False

            config.updated_at = datetime.utcnow()
            self._performance["configs_updated"] += 1

            logger.info(f"Updated contract config: {name}")
            return True

    async def delete_contract_config(self, name: str) -> bool:
        """
        Delete a contract configuration.

        Args:
            name: Contract name

        Returns:
            True if successful
        """
        async with self._lock:
            if name not in self._configs:
                logger.warning(f"Contract config not found: {name}")
                return False

            del self._configs[name]
            logger.info(f"Deleted contract config: {name}")
            return True

    # -----------------------------------------------------------------------
    # Configuration Validation
    # -----------------------------------------------------------------------

    async def validate_contract_config(
        self,
        config: ContractConfig,
    ) -> bool:
        """
        Validate a contract configuration.

        Args:
            config: ContractConfig

        Returns:
            True if valid
        """
        self._performance["validations_performed"] += 1

        try:
            # Required fields
            if not config.name:
                self._performance["validation_errors"] += 1
                return False

            if not config.address:
                self._performance["validation_errors"] += 1
                return False

            # Validate address
            try:
                Web3.to_checksum_address(config.address)
            except:
                self._performance["validation_errors"] += 1
                return False

            # Validate chain_id
            if config.chain_id not in self._chain_configs:
                self._performance["validation_errors"] += 1
                return False

            # Validate version format
            if not re.match(r'^\d+\.\d+\.\d+$', config.version):
                self._performance["validation_errors"] += 1
                return False

            # Validate ABI if present
            if config.abi and not isinstance(config.abi, list):
                self._performance["validation_errors"] += 1
                return False

            return True

        except Exception as e:
            self._performance["validation_errors"] += 1
            logger.error(f"Validation error: {e}")
            return False

    def _load_schemas(self) -> Dict[str, Any]:
        """Load validation schemas."""
        return {
            "contract": {
                "required": ["name", "address", "chain_id", "contract_type"],
                "types": {
                    "name": str,
                    "address": str,
                    "chain_id": int,
                    "contract_type": str,
                    "state": str,
                    "version": str,
                },
            },
            "environment": {
                "required": ["name", "chain_id", "rpc_urls"],
                "types": {
                    "name": str,
                    "chain_id": int,
                    "network": str,
                },
            },
        }

    # -----------------------------------------------------------------------
    # Configuration Export/Import
    # -----------------------------------------------------------------------

    async def export_configuration(
        self,
        format: str = "yaml",
        include_abis: bool = False,
    ) -> str:
        """
        Export all configurations.

        Args:
            format: Export format (yaml, json)
            include_abis: Include ABIs

        Returns:
            Serialized configuration
        """
        data = {
            "version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "contracts": {},
            "environments": {},
            "deployments": {},
        }

        # Export contracts
        for name, config in self._configs.items():
            contract_data = {
                "name": config.name,
                "address": config.address,
                "chain_id": config.chain_id,
                "network": config.network.value,
                "type": config.contract_type.value,
                "state": config.state.value,
                "version": config.version,
                "params": config.params,
                "metadata": config.metadata,
                "tags": config.tags,
                "dependencies": config.dependencies,
                "features": config.features,
                "limits": config.limits,
                "security": config.security,
            }

            if include_abis and config.abi:
                contract_data["abi"] = config.abi

            if config.bytecode:
                contract_data["bytecode"] = config.bytecode

            data["contracts"][name] = contract_data

        # Export environments
        for name, env in self._environments.items():
            data["environments"][name] = {
                "name": env.name,
                "network": env.network.value,
                "chain_id": env.chain_id,
                "rpc_urls": env.rpc_urls,
                "ws_urls": env.ws_urls,
                "explorer_urls": env.explorer_urls,
                "gas_config": env.gas_config,
                "global_params": env.global_params,
                "features": env.features,
                "security_config": env.security_config,
            }

        # Export deployments
        for name, deployment in self._deployments.items():
            data["deployments"][name] = {
                "environment": deployment.environment,
                "contracts": deployment.contracts,
                "order": deployment.order,
                "params": deployment.params,
                "gas_config": deployment.gas_config,
                "verification": deployment.verification,
                "hooks": deployment.hooks,
            }

        if format.lower() == "json":
            return json.dumps(data, indent=2, default=str)
        else:
            return yaml.dump(data, default_flow_style=False)

    async def import_configuration(
        self,
        data: Union[str, Dict[str, Any]],
        format: str = "auto",
    ) -> bool:
        """
        Import configuration.

        Args:
            data: Configuration data
            format: Data format

        Returns:
            True if successful
        """
        try:
            # Parse data
            if isinstance(data, str):
                if format == "auto":
                    if data.strip().startswith("{"):
                        parsed = json.loads(data)
                    else:
                        parsed = yaml.safe_load(data)
                elif format == "json":
                    parsed = json.loads(data)
                else:
                    parsed = yaml.safe_load(data)
            else:
                parsed = data

            if not parsed:
                return False

            # Import contracts
            contracts = parsed.get("contracts", {})
            for name, contract_data in contracts.items():
                # Create config from data
                config = ContractConfig(
                    name=name,
                    address=contract_data.get("address", ""),
                    chain_id=contract_data.get("chain_id", 1),
                    network=NetworkType(contract_data.get("network", "mainnet")),
                    contract_type=ContractType(contract_data.get("type", "utility")),
                    state=ContractState(contract_data.get("state", "draft")),
                    version=contract_data.get("version", "1.0.0"),
                    abi=contract_data.get("abi"),
                    bytecode=contract_data.get("bytecode"),
                    params=contract_data.get("params", {}),
                    metadata=contract_data.get("metadata", {}),
                    tags=contract_data.get("tags", []),
                    dependencies=contract_data.get("dependencies", {}),
                    features=contract_data.get("features", {}),
                    limits=contract_data.get("limits", {}),
                    security=contract_data.get("security", {}),
                )

                await self.add_contract_config(config, overwrite=True)

            logger.info(
                f"Imported {len(contracts)} contract configurations"
            )
            return True

        except Exception as e:
            logger.error(f"Error importing configuration: {e}")
            return False

    # -----------------------------------------------------------------------
    # Chain Management
    # -----------------------------------------------------------------------

    def get_chain_config(
        self,
        chain_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get chain configuration.

        Args:
            chain_id: Chain ID

        Returns:
            Chain configuration or None
        """
        return self._chain_configs.get(chain_id)

    def get_all_chains(self) -> List[Dict[str, Any]]:
        """
        Get all chain configurations.

        Returns:
            List of chain configurations
        """
        return [
            {"chain_id": chain_id, **config}
            for chain_id, config in self._chain_configs.items()
        ]

    async def add_chain_config(
        self,
        chain_id: int,
        name: str,
        network: NetworkType,
        currency: str,
    ) -> bool:
        """
        Add a chain configuration.

        Args:
            chain_id: Chain ID
            name: Chain name
            network: Network type
            currency: Native currency

        Returns:
            True if successful
        """
        if chain_id in self._chain_configs:
            logger.warning(f"Chain config already exists: {chain_id}")
            return False

        self._chain_configs[chain_id] = {
            "name": name,
            "network": network,
            "currency": currency,
        }

        logger.info(f"Added chain config: {chain_id} ({name})")
        return True

    # -----------------------------------------------------------------------
    # Configuration Resolution
    # -----------------------------------------------------------------------

    def resolve_config(
        self,
        name: str,
        environment: Optional[str] = None,
    ) -> Optional[ContractConfig]:
        """
        Resolve configuration with inheritance.

        Args:
            name: Contract name
            environment: Environment name

        Returns:
            Resolved ContractConfig or None
        """
        config = self.get_contract_config(name)

        if not config:
            return None

        # Apply environment overrides
        if environment and environment in self._environments:
            env_config = self._environments[environment]

            # Override network configs
            if env_config.global_params:
                config.params.update(env_config.global_params)

            # Override features
            if env_config.features:
                config.features.update(env_config.features)

        return config

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_environment(self, name: str) -> Optional[EnvironmentConfig]:
        """Get environment configuration."""
        return self._environments.get(name)

    def get_deployment(self, name: str) -> Optional[DeploymentConfig]:
        """Get deployment configuration."""
        return self._deployments.get(name)

    def list_contracts(self) -> List[str]:
        """List all contract names."""
        return list(self._configs.keys())

    def list_environments(self) -> List[str]:
        """List all environments."""
        return list(self._environments.keys())

    def list_deployments(self) -> List[str]:
        """List all deployments."""
        return list(self._deployments.keys())

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "total_contracts": len(self._configs),
            "total_environments": len(self._environments),
            "total_deployments": len(self._deployments),
            "loaded": self._loaded,
        }

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    async def save_configuration(self) -> bool:
        """
        Save configuration to files.

        Returns:
            True if successful
        """
        try:
            # Ensure directories exist
            self.config_dir.mkdir(parents=True, exist_ok=True)
            (self.config_dir / "contracts").mkdir(exist_ok=True)
            (self.config_dir / "deployments").mkdir(exist_ok=True)

            # Save global config
            global_file = self.config_dir / "global.yaml"
            with open(global_file, 'w') as f:
                yaml.dump(self.DEFAULT_CONFIG, f, default_flow_style=False)

            # Save environment configs
            for name, env in self._environments.items():
                env_file = self.config_dir / f"{name}.yaml"
                env_data = {
                    "network": env.network.value,
                    "chain_id": env.chain_id,
                    "rpc_urls": env.rpc_urls,
                    "ws_urls": env.ws_urls,
                    "explorer_urls": env.explorer_urls,
                    "gas_config": env.gas_config,
                    "params": env.global_params,
                    "features": env.features,
                    "security": env.security_config,
                }
                with open(env_file, 'w') as f:
                    yaml.dump(env_data, f, default_flow_style=False)

            # Save contract configs
            for name, config in self._configs.items():
                contract_dir = self.config_dir / "contracts" / config.network.value
                contract_dir.mkdir(parents=True, exist_ok=True)

                contract_file = contract_dir / f"{name}.yaml"
                contract_data = {
                    "address": config.address,
                    "name": config.name,
                    "chain_id": config.chain_id,
                    "network": config.network.value,
                    "type": config.contract_type.value,
                    "state": config.state.value,
                    "version": config.version,
                    "params": config.params,
                    "metadata": config.metadata,
                    "tags": config.tags,
                    "dependencies": config.dependencies,
                    "features": config.features,
                    "limits": config.limits,
                    "security": config.security,
                }

                if config.abi:
                    contract_data["abi"] = config.abi

                if config.bytecode:
                    contract_data["bytecode"] = config.bytecode

                with open(contract_file, 'w') as f:
                    yaml.dump(contract_data, f, default_flow_style=False)

            # Save deployment configs
            for name, deployment in self._deployments.items():
                deploy_file = self.config_dir / "deployments" / f"{name}.yaml"
                deploy_data = {
                    "environment": deployment.environment,
                    "contracts": deployment.contracts,
                    "order": deployment.order,
                    "params": deployment.params,
                    "gas": deployment.gas_config,
                    "verification": deployment.verification,
                    "hooks": deployment.hooks,
                }
                with open(deploy_file, 'w') as f:
                    yaml.dump(deploy_data, f, default_flow_style=False)

            logger.info("Configuration saved successfully")
            return True

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the configuration manager."""
        logger.info("ContractConfigManager started")

    async def stop(self) -> None:
        """Stop the configuration manager."""
        logger.info("ContractConfigManager stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_config_manager(
    config_dir: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ContractConfigManager:
    """
    Factory function to create a ContractConfigManager instance.

    Args:
        config_dir: Configuration directory
        config: Configuration dictionary

    Returns:
        ContractConfigManager instance
    """
    return ContractConfigManager(
        config_dir=config_dir,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the configuration manager
    pass

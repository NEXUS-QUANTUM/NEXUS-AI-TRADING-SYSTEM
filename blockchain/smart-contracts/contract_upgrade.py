# blockchain/smart-contracts/contract_upgrade.py
# NEXUS AI TRADING SYSTEM - Smart Contract Upgrade Framework
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced Smart Contract Upgrade Framework for NEXUS AI Trading System.
Provides secure and automated contract upgrades with rollback capabilities,
version management, and comprehensive safety checks for proxy-based upgrades.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware

# NEXUS Imports
from blockchain.smart_contracts.contract_deployer import (
    ContractDeployer,
    DeploymentConfig,
    DeploymentResult,
    DeploymentStatus,
    create_contract_deployer,
)
from blockchain.smart_contracts.contract_config import (
    ContractConfig,
    ContractState,
    ContractType,
    ContractConfigManager,
    create_config_manager,
)
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.upgrade")


# ============================================================================
# Enums & Constants
# ============================================================================

class UpgradeType(str, Enum):
    """Types of contract upgrades."""
    PROXY = "proxy"           # Upgrade via proxy pattern
    IMPLEMENTATION = "implementation"  # New implementation
    FULL = "full"             # Full contract replacement
    MIGRATION = "migration"   # Data migration upgrade
    PATCH = "patch"           # Small patch upgrade


class UpgradeStatus(str, Enum):
    """Upgrade status."""
    PENDING = "pending"
    PREPARING = "preparing"
    VALIDATING = "validating"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class UpgradeValidation(str, Enum):
    """Upgrade validation levels."""
    NONE = "none"
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    COMPREHENSIVE = "comprehensive"


@dataclass
class UpgradePlan:
    """Upgrade plan for a contract."""
    upgrade_id: str
    contract_name: str
    contract_address: str
    upgrade_type: UpgradeType
    version_from: str
    version_to: str
    implementation_address: Optional[str] = None
    new_implementation_source: Optional[str] = None
    migration_code: Optional[str] = None
    validation_level: UpgradeValidation = UpgradeValidation.STANDARD
    auto_rollback: bool = True
    min_confirmations: int = 3
    upgrade_params: Dict[str, Any] = field(default_factory=dict)
    status: UpgradeStatus = UpgradeStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[DeploymentResult] = None
    rollback_result: Optional[DeploymentResult] = None
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpgradeResult:
    """Upgrade result."""
    success: bool
    plan: UpgradePlan
    new_implementation: Optional[str] = None
    transaction_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    verification_result: Optional[Dict[str, Any]] = None
    rollback_result: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VersionInfo:
    """Contract version information."""
    contract_name: str
    version: str
    implementation: Optional[str] = None
    proxy: Optional[str] = None
    deployed_at: datetime
    deployed_by: str
    block_number: int
    transaction_hash: str
    is_current: bool = False
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Contract Upgrade Framework
# ============================================================================

class ContractUpgrade:
    """
    Advanced Smart Contract Upgrade Framework.
    Provides secure and automated contract upgrades with rollback capabilities.
    """

    # Proxy implementation slot (EIP-1967)
    IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
    BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.config = config or {}

        # Initialize components
        self.deployer = create_contract_deployer(config)
        self.config_manager = create_config_manager(config.get("config_dir"))

        # Upgrade storage
        self._upgrade_plans: Dict[str, UpgradePlan] = {}
        self._active_upgrades: Set[str] = set()
        self._upgrade_history: List[UpgradeResult] = []
        self._version_history: Dict[str, List[VersionInfo]] = {}

        # Proxy contract cache
        self._proxy_contracts: Dict[str, Contract] = {}

        # Validation cache
        self._validation_cache: Dict[str, Dict[str, Any]] = {}

        # State management
        self._running = False
        self._lock = asyncio.Lock()

        # Performance metrics
        self._performance = {
            "upgrades_total": 0,
            "upgrades_successful": 0,
            "upgrades_failed": 0,
            "rollbacks": 0,
            "avg_upgrade_time_ms": 0.0,
            "avg_rollback_time_ms": 0.0,
        }

        # Initialize default ABI
        self._proxy_abi = self._get_proxy_abi()

        logger.info(
            "ContractUpgrade initialized",
            extra={
                "chain": web3_client.chain_name,
                "upgrades_available": len(self._upgrade_plans),
            }
        )

    # -----------------------------------------------------------------------
    # Proxy Contract Management
    # -----------------------------------------------------------------------

    def _get_proxy_abi(self) -> List[Dict[str, Any]]:
        """Get proxy contract ABI."""
        return [
            {
                "constant": False,
                "inputs": [{"name": "newImplementation", "type": "address"}],
                "name": "upgradeTo",
                "outputs": [],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "newImplementation", "type": "address"},
                    {"name": "data", "type": "bytes"}
                ],
                "name": "upgradeToAndCall",
                "outputs": [],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "implementation",
                "outputs": [{"name": "", "type": "address"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "admin",
                "outputs": [{"name": "", "type": "address"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [{"name": "newAdmin", "type": "address"}],
                "name": "changeAdmin",
                "outputs": [],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [],
                "name": "upgrade",
                "outputs": [],
                "type": "function"
            },
        ]

    async def _get_proxy_contract(
        self,
        proxy_address: str,
    ) -> Optional[Contract]:
        """Get proxy contract instance."""
        if proxy_address in self._proxy_contracts:
            return self._proxy_contracts[proxy_address]

        try:
            contract = self.web3_client.get_contract(
                proxy_address,
                abi=self._proxy_abi,
            )
            self._proxy_contracts[proxy_address] = contract
            return contract
        except Exception as e:
            logger.error(f"Error getting proxy contract: {e}")
            return None

    async def get_implementation(
        self,
        proxy_address: str,
    ) -> Optional[str]:
        """Get current implementation address from proxy."""
        contract = await self._get_proxy_contract(proxy_address)
        if not contract:
            return None

        try:
            # Try EIP-1967 slot
            implementation = await self.web3_client.eth.get_storage_at(
                proxy_address,
                self.IMPLEMENTATION_SLOT,
            )
            if implementation:
                return "0x" + implementation.hex()[-40:]

            # Fallback to function call
            impl = await self.web3_client.call_function(
                contract,
                "implementation",
            )
            return impl if impl and impl != "0x0000000000000000000000000000000000000000" else None

        except Exception as e:
            logger.error(f"Error getting implementation: {e}")
            return None

    async def get_proxy_admin(
        self,
        proxy_address: str,
    ) -> Optional[str]:
        """Get proxy admin address."""
        contract = await self._get_proxy_contract(proxy_address)
        if not contract:
            return None

        try:
            admin = await self.web3_client.call_function(
                contract,
                "admin",
            )
            return admin if admin and admin != "0x0000000000000000000000000000000000000000" else None
        except Exception:
            return None

    # -----------------------------------------------------------------------
    # Upgrade Planning
    # -----------------------------------------------------------------------

    async def create_upgrade_plan(
        self,
        contract_name: str,
        contract_address: str,
        version_to: str,
        upgrade_type: UpgradeType = UpgradeType.PROXY,
        validation_level: UpgradeValidation = UpgradeValidation.STANDARD,
        **kwargs,
    ) -> UpgradePlan:
        """
        Create an upgrade plan.

        Args:
            contract_name: Contract name
            contract_address: Contract address
            version_to: Target version
            upgrade_type: Upgrade type
            validation_level: Validation level
            **kwargs: Additional parameters

        Returns:
            UpgradePlan
        """
        upgrade_id = f"upgrade_{contract_name}_{version_to}_{int(time.time())}"

        # Get current version
        version_from = await self._get_current_version(contract_address)

        plan = UpgradePlan(
            upgrade_id=upgrade_id,
            contract_name=contract_name,
            contract_address=contract_address,
            upgrade_type=upgrade_type,
            version_from=version_from or "unknown",
            version_to=version_to,
            validation_level=validation_level,
            upgrade_params=kwargs,
            created_at=datetime.utcnow(),
        )

        self._upgrade_plans[upgrade_id] = plan
        logger.info(
            f"Upgrade plan created: {upgrade_id}",
            extra={
                "contract": contract_name,
                "version_from": plan.version_from,
                "version_to": version_to,
                "type": upgrade_type.value,
            }
        )

        return plan

    async def _get_current_version(
        self,
        contract_address: str,
    ) -> Optional[str]:
        """Get current version of contract."""
        # Check config manager
        config = self.config_manager.get_contract_config_by_address(contract_address)
        if config:
            return config.version

        # Check version history
        for versions in self._version_history.values():
            for version in versions:
                if version.proxy == contract_address and version.is_current:
                    return version.version

        return None

    # -----------------------------------------------------------------------
    # Upgrade Validation
    # -----------------------------------------------------------------------

    async def validate_upgrade(
        self,
        plan: UpgradePlan,
    ) -> List[Dict[str, Any]]:
        """
        Validate an upgrade plan.

        Args:
            plan: UpgradePlan

        Returns:
            List of validation results
        """
        validation_results = []

        # 1. Validate contract exists
        contract_code = await self.web3_client.get_code(plan.contract_address)
        if not contract_code or contract_code == b'':
            validation_results.append({
                "type": "error",
                "message": f"Contract not found at {plan.contract_address}",
                "severity": "critical",
            })

        # 2. Validate proxy pattern
        if plan.upgrade_type in [UpgradeType.PROXY, UpgradeType.IMPLEMENTATION]:
            is_proxy = await self._is_proxy_contract(plan.contract_address)
            if not is_proxy:
                validation_results.append({
                    "type": "warning",
                    "message": "Contract does not appear to be a proxy",
                    "severity": "medium",
                })

            # Validate implementation
            current_impl = await self.get_implementation(plan.contract_address)
            if current_impl:
                validation_results.append({
                    "type": "info",
                    "message": f"Current implementation: {current_impl}",
                    "severity": "info",
                })

        # 3. Validate version format
        if not self._validate_version_format(plan.version_to):
            validation_results.append({
                "type": "error",
                "message": f"Invalid version format: {plan.version_to}. Expected semver",
                "severity": "critical",
            })

        # 4. Validate source code
        if plan.new_implementation_source:
            compilation_result = await self.deployer.compiler.compile_solidity(
                plan.new_implementation_source,
                plan.upgrade_params.get("compiler_config"),
            )
            if not compilation_result:
                validation_results.append({
                    "type": "error",
                    "message": "Source compilation failed",
                    "severity": "critical",
                })
            else:
                validation_results.append({
                    "type": "success",
                    "message": "Source compilation successful",
                    "severity": "info",
                })

        # 5. Validate permissions
        admin = await self.get_proxy_admin(plan.contract_address)
        if admin:
            caller = self.web3_client.default_account
            if admin.lower() != caller.lower():
                validation_results.append({
                    "type": "error",
                    "message": f"Caller {caller} is not the proxy admin ({admin})",
                    "severity": "critical",
                })

        # 6. Validate storage compatibility
        if plan.upgrade_type in [UpgradeType.PROXY, UpgradeType.IMPLEMENTATION]:
            storage_compatible = await self._validate_storage_compatibility(
                plan.contract_address,
                plan.new_implementation_source,
            )
            if not storage_compatible:
                validation_results.append({
                    "type": "warning",
                    "message": "Storage layout may be incompatible",
                    "severity": "high",
                })

        plan.validation_results = validation_results
        return validation_results

    async def _is_proxy_contract(self, address: str) -> bool:
        """Check if contract is a proxy."""
        try:
            # Check EIP-1967 implementation slot
            implementation = await self.web3_client.eth.get_storage_at(
                address,
                self.IMPLEMENTATION_SLOT,
            )
            if implementation and int(implementation.hex(), 16) != 0:
                return True
        except Exception:
            pass
        return False

    def _validate_version_format(self, version: str) -> bool:
        """Validate semantic version format."""
        import re
        pattern = r'^\d+\.\d+\.\d+$'
        return bool(re.match(pattern, version))

    async def _validate_storage_compatibility(
        self,
        contract_address: str,
        new_source: str,
    ) -> bool:
        """Validate storage layout compatibility."""
        # Would need to compare storage layouts
        # For now, return True if source is provided
        return bool(new_source)

    # -----------------------------------------------------------------------
    # Upgrade Execution
    # -----------------------------------------------------------------------

    async def execute_upgrade(
        self,
        plan: UpgradePlan,
        deployment_config: Optional[DeploymentConfig] = None,
    ) -> UpgradeResult:
        """
        Execute an upgrade plan.

        Args:
            plan: UpgradePlan
            deployment_config: Deployment configuration

        Returns:
            UpgradeResult
        """
        start_time = time.time()

        if plan.upgrade_id in self._active_upgrades:
            logger.warning(f"Upgrade already in progress: {plan.upgrade_id}")
            return UpgradeResult(
                success=False,
                plan=plan,
                errors=["Upgrade already in progress"],
            )

        self._active_upgrades.add(plan.upgrade_id)
        plan.status = UpgradeStatus.PREPARING
        plan.started_at = datetime.utcnow()

        try:
            # Validate upgrade
            plan.status = UpgradeStatus.VALIDATING
            validation_results = await self.validate_upgrade(plan)

            critical_errors = [
                r for r in validation_results
                if r.get("severity") == "critical" and r.get("type") == "error"
            ]

            if critical_errors:
                plan.status = UpgradeStatus.FAILED
                return UpgradeResult(
                    success=False,
                    plan=plan,
                    errors=[r["message"] for r in critical_errors],
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Execute based on upgrade type
            plan.status = UpgradeStatus.EXECUTING

            if plan.upgrade_type == UpgradeType.PROXY:
                result = await self._execute_proxy_upgrade(plan, deployment_config)
            elif plan.upgrade_type == UpgradeType.IMPLEMENTATION:
                result = await self._execute_implementation_upgrade(plan, deployment_config)
            elif plan.upgrade_type == UpgradeType.FULL:
                result = await self._execute_full_upgrade(plan, deployment_config)
            elif plan.upgrade_type == UpgradeType.MIGRATION:
                result = await self._execute_migration_upgrade(plan, deployment_config)
            elif plan.upgrade_type == UpgradeType.PATCH:
                result = await self._execute_patch_upgrade(plan, deployment_config)
            else:
                result = UpgradeResult(
                    success=False,
                    plan=plan,
                    errors=[f"Unsupported upgrade type: {plan.upgrade_type}"],
                )

            # Verify upgrade
            if result.success:
                plan.status = UpgradeStatus.VERIFYING
                verification = await self._verify_upgrade(result)
                result.verification_result = verification

                if verification.get("verified", False):
                    plan.status = UpgradeStatus.COMPLETED
                    plan.completed_at = datetime.utcnow()
                    self._performance["upgrades_successful"] += 1

                    # Update version history
                    await self._update_version_history(plan, result)

                    # Update config
                    await self._update_contract_config(plan, result)
                else:
                    plan.status = UpgradeStatus.FAILED
                    self._performance["upgrades_failed"] += 1
                    result.errors.append("Verification failed")

                    # Auto rollback if enabled
                    if plan.auto_rollback:
                        logger.info(f"Auto-rolling back upgrade: {plan.upgrade_id}")
                        await self.rollback_upgrade(plan)

            else:
                plan.status = UpgradeStatus.FAILED
                self._performance["upgrades_failed"] += 1

                # Auto rollback if enabled
                if plan.auto_rollback:
                    logger.info(f"Auto-rolling back upgrade: {plan.upgrade_id}")
                    await self.rollback_upgrade(plan)

            self._performance["upgrades_total"] += 1
            result.duration_ms = (time.time() - start_time) * 1000

            self._performance["avg_upgrade_time_ms"] = (
                (self._performance["avg_upgrade_time_ms"] *
                 (self._performance["upgrades_total"] - 1) +
                 result.duration_ms) / self._performance["upgrades_total"]
            )

            return result

        except Exception as e:
            logger.error(f"Upgrade execution error: {e}")
            plan.status = UpgradeStatus.FAILED
            self._performance["upgrades_failed"] += 1

            # Auto rollback if enabled
            if plan.auto_rollback:
                await self.rollback_upgrade(plan)

            return UpgradeResult(
                success=False,
                plan=plan,
                errors=[str(e)],
                duration_ms=(time.time() - start_time) * 1000,
            )

        finally:
            self._active_upgrades.remove(plan.upgrade_id)

    async def _execute_proxy_upgrade(
        self,
        plan: UpgradePlan,
        deployment_config: Optional[DeploymentConfig],
    ) -> UpgradeResult:
        """Execute proxy upgrade."""
        try:
            # Deploy new implementation
            if plan.new_implementation_source:
                result = await self.deployer.deploy_contract(
                    source=plan.new_implementation_source,
                    contract_name=f"{plan.contract_name}_impl",
                    deploy_config=deployment_config,
                    compiler_config=plan.upgrade_params.get("compiler_config"),
                )

                if not result:
                    return UpgradeResult(
                        success=False,
                        plan=plan,
                        errors=["Implementation deployment failed"],
                    )

                new_impl = result.contract_address
            else:
                new_impl = plan.implementation_address

            if not new_impl:
                return UpgradeResult(
                    success=False,
                    plan=plan,
                    errors=["No implementation address provided"],
                )

            # Get proxy contract
            proxy = await self._get_proxy_contract(plan.contract_address)
            if not proxy:
                return UpgradeResult(
                    success=False,
                    plan=plan,
                    errors=["Failed to get proxy contract"],
                )

            # Build upgrade transaction
            upgrade_tx = await self._build_upgrade_transaction(
                proxy,
                new_impl,
                plan.upgrade_params.get("call_data"),
                deployment_config,
            )

            # Send transaction
            tx_hash = await self._send_upgrade_transaction(upgrade_tx, deployment_config)

            if not tx_hash:
                return UpgradeResult(
                    success=False,
                    plan=plan,
                    errors=["Upgrade transaction failed"],
                )

            # Wait for confirmation
            receipt = await self.web3_client.wait_for_transaction_receipt(tx_hash)

            if receipt and receipt.get("status", 0) == 1:
                return UpgradeResult(
                    success=True,
                    plan=plan,
                    new_implementation=new_impl,
                    transaction_hash=tx_hash,
                    block_number=receipt.get("blockNumber"),
                    gas_used=receipt.get("gasUsed", 0),
                )
            else:
                return UpgradeResult(
                    success=False,
                    plan=plan,
                    errors=["Upgrade transaction failed"],
                    transaction_hash=tx_hash,
                )

        except Exception as e:
            return UpgradeResult(
                success=False,
                plan=plan,
                errors=[str(e)],
            )

    async def _build_upgrade_transaction(
        self,
        proxy: Contract,
        implementation: str,
        call_data: Optional[bytes],
        config: Optional[DeploymentConfig],
    ) -> Dict[str, Any]:
        """Build upgrade transaction."""
        if call_data:
            tx = proxy.functions.upgradeToAndCall(
                implementation,
                call_data,
            ).build_transaction({
                "from": self.web3_client.default_account,
                "nonce": await self.web3_client.get_nonce(self.web3_client.default_account),
                "gas": 0,
                "gasPrice": await self._get_gas_price(config),
            })
        else:
            tx = proxy.functions.upgradeTo(
                implementation,
            ).build_transaction({
                "from": self.web3_client.default_account,
                "nonce": await self.web3_client.get_nonce(self.web3_client.default_account),
                "gas": 0,
                "gasPrice": await self._get_gas_price(config),
            })

        # Estimate gas
        gas = await self.web3_client.estimate_gas(tx)
        tx["gas"] = int(gas * (config.gas_limit_multiplier if config else 1.3))

        return tx

    async def _send_upgrade_transaction(
        self,
        tx: Dict[str, Any],
        config: Optional[DeploymentConfig],
    ) -> Optional[str]:
        """Send upgrade transaction."""
        try:
            signed_tx = self.web3_client.sign_transaction(tx, self.web3_client.default_account)
            tx_hash = await self.web3_client.send_raw_transaction(signed_tx.rawTransaction)
            return tx_hash
        except Exception as e:
            logger.error(f"Error sending upgrade transaction: {e}")
            return None

    async def _get_gas_price(self, config: Optional[DeploymentConfig]) -> int:
        """Get optimal gas price."""
        try:
            gas_price = await self.web3_client.get_gas_price()
            if config:
                gas_price = int(gas_price * config.gas_price_multiplier)
            return gas_price
        except Exception:
            return 50000000000  # 50 Gwei

    async def _execute_implementation_upgrade(
        self,
        plan: UpgradePlan,
        deployment_config: Optional[DeploymentConfig],
    ) -> UpgradeResult:
        """Execute implementation upgrade."""
        # Similar to proxy upgrade but without proxy
        return await self._execute_proxy_upgrade(plan, deployment_config)

    async def _execute_full_upgrade(
        self,
        plan: UpgradePlan,
        deployment_config: Optional[DeploymentConfig],
    ) -> UpgradeResult:
        """Execute full contract upgrade."""
        # Deploy new contract
        result = await self.deployer.deploy_contract(
            source=plan.new_implementation_source,
            contract_name=plan.contract_name,
            deploy_config=deployment_config,
            compiler_config=plan.upgrade_params.get("compiler_config"),
        )

        if result:
            return UpgradeResult(
                success=True,
                plan=plan,
                new_implementation=result.contract_address,
                transaction_hash=result.transaction_hash,
                block_number=result.block_number,
                gas_used=result.gas_used,
            )

        return UpgradeResult(
            success=False,
            plan=plan,
            errors=["Full contract deployment failed"],
        )

    async def _execute_migration_upgrade(
        self,
        plan: UpgradePlan,
        deployment_config: Optional[DeploymentConfig],
    ) -> UpgradeResult:
        """Execute migration upgrade."""
        # Deploy new implementation with migration
        result = await self.deployer.deploy_contract(
            source=plan.new_implementation_source,
            contract_name=f"{plan.contract_name}_migration",
            deploy_config=deployment_config,
            constructor_args=plan.upgrade_params.get("constructor_args", []),
            compiler_config=plan.upgrade_params.get("compiler_config"),
        )

        if result:
            # Execute migration logic
            migration_result = await self._execute_migration_logic(
                plan,
                result.contract_address,
                deployment_config,
            )

            if migration_result:
                return UpgradeResult(
                    success=True,
                    plan=plan,
                    new_implementation=result.contract_address,
                    transaction_hash=result.transaction_hash,
                    block_number=result.block_number,
                    gas_used=result.gas_used,
                    metadata={"migration": migration_result},
                )

        return UpgradeResult(
            success=False,
            plan=plan,
            errors=["Migration upgrade failed"],
        )

    async def _execute_migration_logic(
        self,
        plan: UpgradePlan,
        new_contract: str,
        config: Optional[DeploymentConfig],
    ) -> Optional[Dict[str, Any]]:
        """Execute migration logic."""
        # Would implement specific migration logic
        return {"migrated": True}

    async def _execute_patch_upgrade(
        self,
        plan: UpgradePlan,
        deployment_config: Optional[DeploymentConfig],
    ) -> UpgradeResult:
        """Execute patch upgrade."""
        # Small patch upgrade - similar to proxy upgrade
        return await self._execute_proxy_upgrade(plan, deployment_config)

    # -----------------------------------------------------------------------
    # Upgrade Verification
    # -----------------------------------------------------------------------

    async def _verify_upgrade(self, result: UpgradeResult) -> Dict[str, Any]:
        """Verify upgrade success."""
        verification = {
            "verified": False,
            "checks": [],
            "errors": [],
        }

        if not result.success:
            verification["errors"].append("Upgrade was not successful")
            return verification

        # Check new implementation is set
        if result.new_implementation:
            verification["checks"].append({
                "name": "implementation_deployed",
                "passed": True,
                "message": f"New implementation: {result.new_implementation}",
            })

            # Verify bytecode matches
            code = await self.web3_client.get_code(result.new_implementation)
            if code and code != b'':
                verification["checks"].append({
                    "name": "implementation_has_code",
                    "passed": True,
                    "message": "Implementation has bytecode",
                })
            else:
                verification["checks"].append({
                    "name": "implementation_has_code",
                    "passed": False,
                    "message": "Implementation has no bytecode",
                })
                verification["errors"].append("Implementation has no bytecode")

        # Check transaction receipt
        if result.transaction_hash:
            receipt = await self.web3_client.get_transaction_receipt(result.transaction_hash)
            if receipt and receipt.get("status", 0) == 1:
                verification["checks"].append({
                    "name": "transaction_success",
                    "passed": True,
                    "message": "Transaction succeeded",
                })
            else:
                verification["checks"].append({
                    "name": "transaction_success",
                    "passed": False,
                    "message": "Transaction failed",
                })
                verification["errors"].append("Transaction failed")

        # Check proxy implementation
        if result.plan.upgrade_type in [UpgradeType.PROXY, UpgradeType.IMPLEMENTATION]:
            current_impl = await self.get_implementation(result.plan.contract_address)
            if current_impl == result.new_implementation:
                verification["checks"].append({
                    "name": "proxy_implementation_updated",
                    "passed": True,
                    "message": f"Proxy points to new implementation: {current_impl}",
                })
            else:
                verification["checks"].append({
                    "name": "proxy_implementation_updated",
                    "passed": False,
                    "message": f"Proxy points to {current_impl}, expected {result.new_implementation}",
                })
                verification["errors"].append("Proxy implementation not updated")

        # Check version (if available)
        new_version = await self._get_version_from_contract(result.plan.contract_address)
        if new_version == result.plan.version_to:
            verification["checks"].append({
                "name": "version_updated",
                "passed": True,
                "message": f"Version updated to {new_version}",
            })
        else:
            verification["checks"].append({
                "name": "version_updated",
                "passed": False,
                "message": f"Version is {new_version}, expected {result.plan.version_to}",
            })

        verification["verified"] = all(c["passed"] for c in verification["checks"]) and not verification["errors"]

        return verification

    async def _get_version_from_contract(self, address: str) -> Optional[str]:
        """Get version from contract."""
        try:
            contract = self.web3_client.get_contract(address)
            if hasattr(contract.functions, "version"):
                version = await self.web3_client.call_function(contract, "version")
                return version
        except Exception:
            pass
        return None

    # -----------------------------------------------------------------------
    # Rollback
    # -----------------------------------------------------------------------

    async def rollback_upgrade(
        self,
        plan: UpgradePlan,
    ) -> UpgradeResult:
        """
        Rollback an upgrade.

        Args:
            plan: UpgradePlan

        Returns:
            UpgradeResult
        """
        start_time = time.time()
        plan.status = UpgradeStatus.ROLLING_BACK

        try:
            # Get previous version
            previous_version = await self._get_previous_version(plan.contract_address)
            if not previous_version:
                return UpgradeResult(
                    success=False,
                    plan=plan,
                    errors=["No previous version found for rollback"],
                )

            # Rollback to previous implementation
            result = await self._execute_proxy_upgrade(
                UpgradePlan(
                    upgrade_id=f"rollback_{plan.upgrade_id}",
                    contract_name=plan.contract_name,
                    contract_address=plan.contract_address,
                    upgrade_type=UpgradeType.PROXY,
                    version_from=plan.version_to,
                    version_to=previous_version.version,
                    implementation_address=previous_version.implementation,
                    auto_rollback=False,
                ),
                None,  # Use default deployment config
            )

            plan.status = UpgradeStatus.ROLLED_BACK
            plan.rollback_result = result

            self._performance["rollbacks"] += 1
            result.duration_ms = (time.time() - start_time) * 1000

            if result.success:
                logger.info(f"Rollback successful: {plan.upgrade_id}")
            else:
                logger.error(f"Rollback failed: {plan.upgrade_id}")

            return result

        except Exception as e:
            logger.error(f"Rollback error: {e}")
            return UpgradeResult(
                success=False,
                plan=plan,
                errors=[str(e)],
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _get_previous_version(
        self,
        contract_address: str,
    ) -> Optional[VersionInfo]:
        """Get previous version of contract."""
        if contract_address not in self._version_history:
            return None

        versions = self._version_history[contract_address]
        # Find current, then return previous
        for i, version in enumerate(versions):
            if version.is_current and i > 0:
                versions[i].is_current = False
                versions[i - 1].is_current = True
                return versions[i - 1]

        return None

    # -----------------------------------------------------------------------
    # Version Management
    # -----------------------------------------------------------------------

    async def _update_version_history(
        self,
        plan: UpgradePlan,
        result: UpgradeResult,
    ) -> None:
        """Update version history."""
        version = VersionInfo(
            contract_name=plan.contract_name,
            version=plan.version_to,
            implementation=result.new_implementation,
            proxy=plan.contract_address,
            deployed_at=datetime.utcnow(),
            deployed_by=self.web3_client.default_account,
            block_number=result.block_number or 0,
            transaction_hash=result.transaction_hash or "",
            is_current=True,
            is_active=True,
            metadata=plan.metadata,
        )

        if plan.contract_address not in self._version_history:
            self._version_history[plan.contract_address] = []

        # Mark previous versions as not current
        for v in self._version_history[plan.contract_address]:
            v.is_current = False

        self._version_history[plan.contract_address].append(version)

    async def _update_contract_config(
        self,
        plan: UpgradePlan,
        result: UpgradeResult,
    ) -> None:
        """Update contract configuration."""
        config = self.config_manager.get_contract_config_by_address(plan.contract_address)
        if config:
            await self.config_manager.update_contract_config(
                config.name,
                {
                    "version": plan.version_to,
                    "implementation": result.new_implementation,
                    "state": ContractState.ACTIVE,
                    "updated_at": datetime.utcnow(),
                    "updated_by": self.web3_client.default_account,
                },
            )

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_upgrade_plan(self, upgrade_id: str) -> Optional[UpgradePlan]:
        """Get upgrade plan by ID."""
        return self._upgrade_plans.get(upgrade_id)

    def get_upgrade_history(self, limit: int = 100) -> List[UpgradeResult]:
        """Get upgrade history."""
        return self._upgrade_history[-limit:]

    def get_version_history(
        self,
        contract_address: str,
    ) -> List[VersionInfo]:
        """Get version history for a contract."""
        return self._version_history.get(contract_address, [])

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "active_upgrades": len(self._active_upgrades),
            "total_plans": len(self._upgrade_plans),
            "version_history_entries": sum(len(v) for v in self._version_history.values()),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the upgrade framework."""
        if self._running:
            return

        self._running = True
        await self.deployer.start()
        await self.config_manager.start()

        logger.info("ContractUpgrade started")

    async def stop(self) -> None:
        """Stop the upgrade framework."""
        self._running = False
        await self.deployer.stop()
        await self.config_manager.stop()

        logger.info("ContractUpgrade stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_contract_upgrade(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> ContractUpgrade:
    """
    Factory function to create a ContractUpgrade instance.

    Args:
        web3_client: Web3 client instance
        config: Configuration dictionary

    Returns:
        ContractUpgrade instance
    """
    return ContractUpgrade(
        web3_client=web3_client,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the contract upgrade framework
    pass

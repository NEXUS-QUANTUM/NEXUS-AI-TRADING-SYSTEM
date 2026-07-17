# blockchain/smart-contracts/contract_deployer.py
# NEXUS AI TRADING SYSTEM - Smart Contract Deployment Framework
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced Smart Contract Deployment Framework for NEXUS AI Trading System.
Provides automated deployment, verification, and management of smart contracts
across multiple chains and networks with comprehensive safety features.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
from eth_account import Account
from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware

# NEXUS Imports
from blockchain.smart_contracts.contract_compiler import (
    CompilationResult,
    CompilerConfig,
    ContractCompiler,
    create_contract_compiler,
)
from blockchain.smart_contracts.contract_config import (
    ContractConfig,
    ContractConfigManager,
    ContractState,
    ContractType,
    create_config_manager,
)
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.deployer")


# ============================================================================
# Enums & Constants
# ============================================================================

class DeploymentStatus(str, Enum):
    """Deployment status."""
    PENDING = "pending"
    PREPARING = "preparing"
    COMPILING = "compiling"
    DEPLOYING = "deploying"
    VERIFYING = "verifying"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"
    PAUSED = "paused"


class VerificationProvider(str, Enum):
    """Contract verification providers."""
    ETHERSCAN = "etherscan"
    BSCSCAN = "bscscan"
    POLYGONSCAN = "polygonscan"
    ARBISCAN = "arbiscan"
    OPTIMISTIC = "optimistic"
    SNOWTRACE = "snowtrace"
    FTMSACN = "ftmscan"
    SOURCIFY = "sourcify"


@dataclass
class DeploymentConfig:
    """Deployment configuration."""
    network: str
    chain_id: int
    rpc_url: str
    private_key: str
    gas_price_multiplier: float = 1.2
    gas_limit_multiplier: float = 1.3
    max_gas_price: Optional[int] = None
    min_gas_price: Optional[int] = None
    priority_fee: Optional[int] = None
    max_priority_fee: Optional[int] = None
    confirmation_blocks: int = 1
    timeout_seconds: int = 300
    verify_contracts: bool = False
    verification_provider: VerificationProvider = VerificationProvider.ETHERSCAN
    verification_api_key: Optional[str] = None
    save_artifacts: bool = True
    artifacts_dir: str = "artifacts"
    allow_revert: bool = False
    skip_if_exists: bool = False


@dataclass
class DeploymentResult:
    """Deployment result."""
    contract_name: str
    contract_address: str
    transaction_hash: str
    block_number: int
    deployment_status: DeploymentStatus
    gas_used: int
    gas_price: int
    total_cost_wei: int
    total_cost_eth: float
    deployed_at: datetime
    implementation: Optional[str] = None
    proxy: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentPlan:
    """Deployment plan for multiple contracts."""
    name: str
    contracts: List[Dict[str, Any]]
    order: List[str]
    params: Dict[str, Any]
    dependencies: Dict[str, List[str]]
    config: DeploymentConfig
    status: DeploymentStatus = DeploymentStatus.PENDING
    results: Dict[str, DeploymentResult] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================================
# Contract Deployer
# ============================================================================

class ContractDeployer:
    """
    Advanced Smart Contract Deployment Framework.
    Provides automated deployment, verification, and management of contracts.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or {}

        # Initialize components
        self.compiler = create_contract_compiler(config)
        self.config_manager = create_config_manager(config.get("config_dir"))

        # Web3 clients cache
        self._web3_clients: Dict[int, Web3Client] = {}

        # Deployment state
        self._deployments: Dict[str, DeploymentPlan] = {}
        self._active_deployments: Set[str] = set()
        self._lock = asyncio.Lock()

        # Performance metrics
        self._performance = {
            "deployments_total": 0,
            "deployments_successful": 0,
            "deployments_failed": 0,
            "avg_deployment_time_ms": 0.0,
            "contracts_deployed": 0,
            "contracts_verified": 0,
        }

        # Verification cache
        self._verification_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("ContractDeployer initialized")

    # -----------------------------------------------------------------------
    # Web3 Client Management
    # -----------------------------------------------------------------------

    async def _get_web3_client(
        self,
        config: DeploymentConfig,
    ) -> Web3Client:
        """Get or create Web3 client for a chain."""
        if config.chain_id not in self._web3_clients:
            # Create Web3 client
            web3_client = Web3Client(
                rpc_url=config.rpc_url,
                private_key=config.private_key,
                chain_id=config.chain_id,
                config={
                    "gas_price_multiplier": config.gas_price_multiplier,
                    "gas_limit_multiplier": config.gas_limit_multiplier,
                }
            )
            await web3_client.start()
            self._web3_clients[config.chain_id] = web3_client

        return self._web3_clients[config.chain_id]

    # -----------------------------------------------------------------------
    # Contract Compilation
    # -----------------------------------------------------------------------

    async def _compile_contract(
        self,
        source: str,
        contract_name: str,
        config: Optional[CompilerConfig] = None,
    ) -> Optional[CompilationResult]:
        """Compile a contract."""
        return await self.compiler.compile_solidity(source, config)

    # -----------------------------------------------------------------------
    # Contract Deployment
    # -----------------------------------------------------------------------

    async def deploy_contract(
        self,
        source: str,
        contract_name: str,
        deploy_config: DeploymentConfig,
        constructor_args: Optional[List[Any]] = None,
        compiler_config: Optional[CompilerConfig] = None,
        contract_config: Optional[ContractConfig] = None,
        verify: bool = False,
    ) -> Optional[DeploymentResult]:
        """
        Deploy a single contract.

        Args:
            source: Contract source code
            contract_name: Contract name
            deploy_config: Deployment configuration
            constructor_args: Constructor arguments
            compiler_config: Compiler configuration
            contract_config: Contract configuration
            verify: Verify after deployment

        Returns:
            DeploymentResult or None if error
        """
        start_time = time.time()

        try:
            # Compile contract
            compilation_result = await self._compile_contract(
                source,
                contract_name,
                compiler_config,
            )

            if not compilation_result or compilation_result.status.value != "success":
                logger.error(f"Compilation failed for {contract_name}")
                return None

            # Get Web3 client
            web3_client = await self._get_web3_client(deploy_config)

            # Build constructor args
            if constructor_args:
                encoded_args = self._encode_constructor_args(
                    compilation_result.abi,
                    constructor_args,
                )
                bytecode = compilation_result.bytecode + encoded_args
            else:
                bytecode = compilation_result.bytecode

            if not bytecode:
                logger.error(f"No bytecode for {contract_name}")
                return None

            # Deploy contract
            tx_hash, contract_address = await self._deploy_raw(
                web3_client,
                bytecode,
                deploy_config,
            )

            if not contract_address:
                logger.error(f"Deployment failed for {contract_name}")
                return None

            # Get receipt
            receipt = await web3_client.wait_for_transaction_receipt(tx_hash)

            # Create deployment result
            result = DeploymentResult(
                contract_name=contract_name,
                contract_address=contract_address,
                transaction_hash=tx_hash,
                block_number=receipt.get("blockNumber", 0),
                deployment_status=DeploymentStatus.SUCCESS,
                gas_used=receipt.get("gasUsed", 0),
                gas_price=receipt.get("effectiveGasPrice", 0),
                total_cost_wei=receipt.get("gasUsed", 0) * receipt.get("effectiveGasPrice", 0),
                total_cost_eth=0,  # Calculate from gas cost
                deployed_at=datetime.utcnow(),
                metadata={
                    "compiler_version": compilation_result.compiler_version,
                    "optimization": compiler_config.optimization_level if compiler_config else None,
                }
            )

            # Calculate ETH cost
            if web3_client.chain_id == 1:
                # Would get ETH price from oracle
                result.total_cost_eth = result.total_cost_wei / 1e18

            # Save contract config
            if contract_config:
                contract_config.address = contract_address
                contract_config.state = ContractState.DEPLOYED
                contract_config.deployed_at = result.deployed_at
                contract_config.transaction_hash = tx_hash
                contract_config.block_number = result.block_number
                await self.config_manager.add_contract_config(contract_config)

            # Verify contract
            if verify or deploy_config.verify_contracts:
                verification_result = await self._verify_contract(
                    contract_address,
                    source,
                    contract_name,
                    deploy_config,
                    compilation_result,
                )
                result.verification_result = verification_result
                if verification_result and verification_result.get("verified"):
                    self._performance["contracts_verified"] += 1

            # Update performance
            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["contracts_deployed"] += 1
            self._performance["avg_deployment_time_ms"] = (
                (self._performance["avg_deployment_time_ms"] *
                 (self._performance["contracts_deployed"] - 1) +
                 elapsed_ms) / self._performance["contracts_deployed"]
            )

            logger.info(
                f"Contract deployed: {contract_name} @ {contract_address}",
                extra={
                    "tx_hash": tx_hash,
                    "gas_used": result.gas_used,
                    "duration_ms": elapsed_ms,
                }
            )

            return result

        except Exception as e:
            logger.error(f"Deployment error for {contract_name}: {e}")
            return None

    async def _deploy_raw(
        self,
        web3_client: Web3Client,
        bytecode: str,
        config: DeploymentConfig,
    ) -> Tuple[str, str]:
        """
        Deploy raw bytecode.

        Args:
            web3_client: Web3 client
            bytecode: Contract bytecode
            config: Deployment config

        Returns:
            Tuple of (transaction_hash, contract_address)
        """
        try:
            # Build transaction
            tx = {
                "from": web3_client.default_account,
                "data": bytecode,
                "nonce": await web3_client.get_nonce(web3_client.default_account),
                "gas": 0,  # Will be estimated
                "gasPrice": await self._get_gas_price(web3_client, config),
            }

            # Estimate gas
            gas = await web3_client.estimate_gas(tx)
            tx["gas"] = int(gas * config.gas_limit_multiplier)

            # Send transaction
            signed_tx = web3_client.sign_transaction(tx, web3_client.default_account)
            tx_hash = await web3_client.send_raw_transaction(signed_tx.rawTransaction)

            # Wait for receipt
            receipt = await web3_client.wait_for_transaction_receipt(tx_hash)

            if receipt and receipt.get("status", 0) == 1:
                contract_address = receipt.get("contractAddress")
                return tx_hash, contract_address
            else:
                return tx_hash, None

        except Exception as e:
            logger.error(f"Raw deployment error: {e}")
            raise

    # -----------------------------------------------------------------------
    # Contract Verification
    # -----------------------------------------------------------------------

    async def _verify_contract(
        self,
        contract_address: str,
        source: str,
        contract_name: str,
        config: DeploymentConfig,
        compilation_result: CompilationResult,
    ) -> Dict[str, Any]:
        """
        Verify contract on block explorer.

        Args:
            contract_address: Contract address
            source: Source code
            contract_name: Contract name
            config: Deployment config
            compilation_result: Compilation result

        Returns:
            Verification result
        """
        try:
            if config.verification_provider == VerificationProvider.SOURCIFY:
                return await self._verify_sourcify(
                    contract_address,
                    source,
                    contract_name,
                    config,
                    compilation_result,
                )
            else:
                return await self._verify_explorer(
                    contract_address,
                    source,
                    contract_name,
                    config,
                    compilation_result,
                )

        except Exception as e:
            logger.error(f"Verification error: {e}")
            return {"verified": False, "error": str(e)}

    async def _verify_sourcify(
        self,
        contract_address: str,
        source: str,
        contract_name: str,
        config: DeploymentConfig,
        compilation_result: CompilationResult,
    ) -> Dict[str, Any]:
        """Verify using Sourcify."""
        try:
            # Prepare verification data
            data = {
                "address": contract_address,
                "chain": str(config.chain_id),
                "contracts": {
                    contract_name: {
                        "source": source,
                        "compiler": compilation_result.compiler_version,
                    }
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://sourcify.dev/api/verify",
                    json=data,
                    timeout=30,
                ) as response:
                    result = await response.json()
                    return {
                        "verified": result.get("status") == "ok",
                        "provider": "sourcify",
                        "result": result,
                    }

        except Exception as e:
            return {"verified": False, "error": str(e)}

    async def _verify_explorer(
        self,
        contract_address: str,
        source: str,
        contract_name: str,
        config: DeploymentConfig,
        compilation_result: CompilationResult,
    ) -> Dict[str, Any]:
        """Verify using block explorer API."""
        try:
            # Determine explorer API URL
            api_urls = {
                VerificationProvider.ETHERSCAN: "https://api.etherscan.io/api",
                VerificationProvider.BSCSCAN: "https://api.bscscan.com/api",
                VerificationProvider.POLYGONSCAN: "https://api.polygonscan.com/api",
                VerificationProvider.ARBISCAN: "https://api.arbiscan.io/api",
                VerificationProvider.OPTIMISTIC: "https://api-optimistic.etherscan.io/api",
                VerificationProvider.SNOWTRACE: "https://api.snowtrace.io/api",
                VerificationProvider.FTMSACN: "https://api.ftmscan.com/api",
            }

            api_url = api_urls.get(config.verification_provider)
            if not api_url:
                return {"verified": False, "error": "Unsupported explorer"}

            # Build request
            params = {
                "module": "contract",
                "action": "verifysourcecode",
                "address": contract_address,
                "sourceCode": source,
                "contractname": contract_name,
                "compilerversion": compilation_result.compiler_version,
                "optimizationUsed": "1",
                "runs": "200",
                "apikey": config.verification_api_key or "",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params, timeout=30) as response:
                    result = await response.json()

                    if result.get("status") == "1":
                        return {
                            "verified": True,
                            "provider": config.verification_provider.value,
                            "guid": result.get("result"),
                        }
                    else:
                        return {
                            "verified": False,
                            "error": result.get("result", "Unknown error"),
                        }

        except Exception as e:
            return {"verified": False, "error": str(e)}

    # -----------------------------------------------------------------------
    # Multi-Contract Deployment
    # -----------------------------------------------------------------------

    async def deploy_plan(
        self,
        plan: DeploymentPlan,
    ) -> DeploymentPlan:
        """
        Execute a deployment plan.

        Args:
            plan: DeploymentPlan

        Returns:
            Updated DeploymentPlan
        """
        plan.status = DeploymentStatus.PREPARING
        plan.started_at = datetime.utcnow()

        async with self._lock:
            if plan.name in self._active_deployments:
                logger.warning(f"Deployment already active: {plan.name}")
                return plan

            self._active_deployments.add(plan.name)

        try:
            # Validate plan
            if not await self._validate_plan(plan):
                plan.status = DeploymentStatus.FAILED
                return plan

            # Deploy contracts in order
            for contract_name in plan.order:
                contract_data = next(
                    (c for c in plan.contracts if c.get("name") == contract_name),
                    None,
                )

                if not contract_data:
                    logger.warning(f"Contract not found in plan: {contract_name}")
                    continue

                # Check dependencies
                if not await self._check_dependencies(plan, contract_name):
                    logger.error(f"Dependencies not met for: {contract_name}")
                    continue

                # Deploy contract
                result = await self.deploy_contract(
                    source=contract_data.get("source", ""),
                    contract_name=contract_name,
                    deploy_config=plan.config,
                    constructor_args=contract_data.get("constructor_args", []),
                    compiler_config=contract_data.get("compiler_config"),
                    contract_config=contract_data.get("contract_config"),
                    verify=contract_data.get("verify", False),
                )

                if result:
                    plan.results[contract_name] = result
                    self._performance["deployments_successful"] += 1
                else:
                    plan.status = DeploymentStatus.FAILED
                    self._performance["deployments_failed"] += 1
                    break

            if plan.status != DeploymentStatus.FAILED:
                plan.status = DeploymentStatus.SUCCESS

        except Exception as e:
            logger.error(f"Deployment plan error: {e}")
            plan.status = DeploymentStatus.FAILED

        finally:
            plan.completed_at = datetime.utcnow()
            self._active_deployments.remove(plan.name)
            self._deployments[plan.name] = plan

        logger.info(
            f"Deployment plan completed: {plan.name}",
            extra={
                "status": plan.status.value,
                "deployed": len(plan.results),
                "duration": (plan.completed_at - plan.started_at).total_seconds(),
            }
        )

        return plan

    async def _validate_plan(self, plan: DeploymentPlan) -> bool:
        """Validate a deployment plan."""
        # Check all contracts have sources
        for contract in plan.contracts:
            if not contract.get("source"):
                logger.error(f"No source for contract: {contract.get('name')}")
                return False

        # Check all order items exist
        for name in plan.order:
            if not any(c.get("name") == name for c in plan.contracts):
                logger.error(f"Contract in order not in contracts: {name}")
                return False

        return True

    async def _check_dependencies(
        self,
        plan: DeploymentPlan,
        contract_name: str,
    ) -> bool:
        """Check contract dependencies."""
        dependencies = plan.dependencies.get(contract_name, [])

        for dep in dependencies:
            if dep not in plan.results:
                logger.error(f"Dependency not deployed: {dep} for {contract_name}")
                return False

            result = plan.results[dep]
            if result.deployment_status != DeploymentStatus.SUCCESS:
                logger.error(f"Dependency failed: {dep} for {contract_name}")
                return False

        return True

    # -----------------------------------------------------------------------
    # Contract Upgrade
    # -----------------------------------------------------------------------

    async def upgrade_contract(
        self,
        proxy_address: str,
        implementation_source: str,
        implementation_name: str,
        deploy_config: DeploymentConfig,
        compiler_config: Optional[CompilerConfig] = None,
    ) -> Optional[DeploymentResult]:
        """
        Upgrade a proxy contract.

        Args:
            proxy_address: Proxy contract address
            implementation_source: New implementation source
            implementation_name: Implementation name
            deploy_config: Deployment config
            compiler_config: Compiler config

        Returns:
            DeploymentResult or None
        """
        try:
            # Deploy new implementation
            impl_result = await self.deploy_contract(
                source=implementation_source,
                contract_name=f"{implementation_name}_new",
                deploy_config=deploy_config,
                compiler_config=compiler_config,
            )

            if not impl_result:
                logger.error("Implementation deployment failed")
                return None

            # Get Web3 client
            web3_client = await self._get_web3_client(deploy_config)

            # Build upgrade transaction
            proxy_contract = web3_client.get_contract(
                proxy_address,
                abi=self._get_proxy_abi(),
            )

            upgrade_tx = proxy_contract.functions.upgradeTo(
                impl_result.contract_address
            ).build_transaction({
                "from": web3_client.default_account,
                "nonce": await web3_client.get_nonce(web3_client.default_account),
                "gas": 0,
                "gasPrice": await self._get_gas_price(web3_client, deploy_config),
            })

            # Estimate gas
            gas = await web3_client.estimate_gas(upgrade_tx)
            upgrade_tx["gas"] = int(gas * deploy_config.gas_limit_multiplier)

            # Send upgrade transaction
            signed_tx = web3_client.sign_transaction(upgrade_tx, web3_client.default_account)
            tx_hash = await web3_client.send_raw_transaction(signed_tx.rawTransaction)

            # Wait for receipt
            receipt = await web3_client.wait_for_transaction_receipt(tx_hash)

            if receipt and receipt.get("status", 0) == 1:
                logger.info(
                    f"Contract upgraded: {proxy_address} -> {impl_result.contract_address}",
                    extra={"tx_hash": tx_hash}
                )

                # Update result
                impl_result.metadata["upgrade_tx_hash"] = tx_hash
                impl_result.metadata["proxy_address"] = proxy_address
                impl_result.metadata["upgrade_type"] = "proxy_upgrade"

                return impl_result
            else:
                logger.error(f"Upgrade transaction failed: {tx_hash}")
                return None

        except Exception as e:
            logger.error(f"Upgrade error: {e}")
            return None

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
                "constant": True,
                "inputs": [],
                "name": "implementation",
                "outputs": [{"name": "", "type": "address"}],
                "type": "function"
            }
        ]

    # -----------------------------------------------------------------------
    # Gas Management
    # -----------------------------------------------------------------------

    async def _get_gas_price(
        self,
        web3_client: Web3Client,
        config: DeploymentConfig,
    ) -> int:
        """Get optimal gas price."""
        try:
            gas_price = await web3_client.get_gas_price()

            # Apply multiplier
            adjusted_price = int(gas_price * config.gas_price_multiplier)

            # Apply limits
            if config.max_gas_price and adjusted_price > config.max_gas_price:
                adjusted_price = config.max_gas_price

            if config.min_gas_price and adjusted_price < config.min_gas_price:
                adjusted_price = config.min_gas_price

            return adjusted_price

        except Exception as e:
            logger.warning(f"Error getting gas price: {e}, using default")
            return 50000000000  # 50 Gwei

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def _encode_constructor_args(
        self,
        abi: Optional[List[Dict[str, Any]]],
        args: List[Any],
    ) -> str:
        """Encode constructor arguments."""
        if not abi or not args:
            return ""

        # Find constructor
        constructor = next(
            (item for item in abi if item.get("type") == "constructor"),
            None,
        )

        if not constructor:
            return ""

        # Encode arguments
        # Would use web3.eth.abi.encode_abi in production
        return ""

    def get_deployment(self, name: str) -> Optional[DeploymentPlan]:
        """Get deployment plan by name."""
        return self._deployments.get(name)

    def get_active_deployments(self) -> List[str]:
        """Get active deployment names."""
        return list(self._active_deployments)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "active_deployments": len(self._active_deployments),
            "total_deployments": len(self._deployments),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the deployer."""
        await self.compiler.start()
        await self.config_manager.start()
        logger.info("ContractDeployer started")

    async def stop(self) -> None:
        """Stop the deployer."""
        await self.compiler.stop()
        await self.config_manager.stop()

        # Close Web3 clients
        for client in self._web3_clients.values():
            await client.stop()

        logger.info("ContractDeployer stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_contract_deployer(
    config: Optional[Dict[str, Any]] = None,
) -> ContractDeployer:
    """
    Factory function to create a ContractDeployer instance.

    Args:
        config: Configuration dictionary

    Returns:
        ContractDeployer instance
    """
    return ContractDeployer(config=config)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the contract deployer
    pass

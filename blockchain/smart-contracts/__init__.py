# blockchain/smart-contracts/__init__.py
# NEXUS AI TRADING SYSTEM - Smart Contracts Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Smart Contracts Module for NEXUS AI TRADING SYSTEM.

This module provides comprehensive smart contract integration capabilities including:
- Contract deployment and management
- Contract compilation and verification
- ABI management and bytecode analysis
- Contract upgrade and migration
- Security auditing and interception
- Multi-protocol support (Aave, Compound, Uniswap, PancakeSwap, etc.)
- ERC standards (ERC20, ERC721, ERC1155)
- Configuration management
- Deployment orchestration
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

# Version
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Module logger
logger = logging.getLogger("nexus.blockchain.contracts")

# ============================================================================
# Base Contract
# ============================================================================

from blockchain.smart_contracts.base_contract import (
    BaseContract,
    ContractStatus,
    EventData,
    TransactionReceipt,
    ContractMetadata,
)

# ============================================================================
# Contract ABI
# ============================================================================

from blockchain.smart_contracts.contract_abi import (
    ABIParameter,
    ABIFunction,
    ABIEvent,
    ABIError,
    ContractABI,
    ContractStandard,
    ProtocolType,
    FunctionType,
    ABIRegistry,
    get_abi_registry,
    get_abi,
    get_abi_dict,
    get_abi_json,
    register_abi,
    list_abis,
)

# ============================================================================
# Contract Bytecode
# ============================================================================

from blockchain.smart_contracts.contract_bytecode import (
    OpCode,
    BytecodePattern,
    BytecodeRiskLevel,
    Instruction,
    BasicBlock,
    ControlFlowGraph,
    ContractAnalysis,
    BytecodeAnalyzer,
    create_bytecode_analyzer,
)

# ============================================================================
# Contract Compiler
# ============================================================================

from blockchain.smart_contracts.contract_compiler import (
    CompilerType,
    OptimizationLevel,
    OutputFormat,
    CompilerStatus,
    CompilerConfig,
    CompilationResult,
    ContractSource,
    ContractCompiler,
    create_contract_compiler,
)

# ============================================================================
# Contract Config
# ============================================================================

from blockchain.smart_contracts.contract_config import (
    NetworkType,
    ContractState,
    ContractType,
    ConfigSource,
    ContractConfig,
    EnvironmentConfig,
    DeploymentConfig,
    ContractConfigManager,
    create_config_manager,
)

# ============================================================================
# Contract Deployer
# ============================================================================

from blockchain.smart_contracts.contract_deployer import (
    DeploymentStatus,
    VerificationProvider,
    DeploymentConfig as DeployConfig,
    DeploymentResult,
    DeploymentPlan,
    ContractDeployer,
    create_contract_deployer,
)

# ============================================================================
# Contract Interceptor
# ============================================================================

from blockchain.smart_contracts.contract_interceptor import (
    InterceptAction,
    InterceptLevel,
    CallType,
    InterceptContext,
    InterceptResult,
    InterceptRule,
    ContractInterceptor,
    create_contract_interceptor,
)

# ============================================================================
# Contract Manager
# ============================================================================

from blockchain.smart_contracts.contract_manager import (
    ContractManager,
    ContractRegistry,
    ContractInstance,
    create_contract_manager,
)

# ============================================================================
# Contract Upgrade
# ============================================================================

from blockchain.smart_contracts.contract_upgrade import (
    UpgradeType,
    UpgradeStatus,
    UpgradeValidation,
    UpgradePlan,
    UpgradeResult,
    VersionInfo,
    ContractUpgrade,
    create_contract_upgrade,
)

# ============================================================================
# Contract Verifier
# ============================================================================

from blockchain.smart_contracts.contract_verifier import (
    VerificationProvider as VerifierProvider,
    VerificationStatus,
    VerificationType,
    VerificationResult,
    VerificationConfig,
    ContractVerifier,
    create_contract_verifier,
)

# ============================================================================
# Contract Audit
# ============================================================================

from blockchain.smart_contracts.contract_audit import (
    VulnerabilitySeverity,
    VulnerabilityType,
    AuditStatus,
    ComplianceStandard,
    Vulnerability,
    AuditResult,
    ComplianceResult,
    ContractAuditor,
    create_contract_auditor,
)

# ============================================================================
# ERC20 Contract
# ============================================================================

from blockchain.smart_contracts.erc20_contract import (
    ERC20Action,
    TokenInfo,
    Allowance,
    Transfer,
    PermitData,
    ERC20Contract,
    create_erc20_contract,
)

# ============================================================================
# ERC721 Contract
# ============================================================================

from blockchain.smart_contracts.erc721_contract import (
    ERC721Action,
    NFTMetadata,
    NFTInfo,
    RoyaltyInfo,
    TransferEvent,
    ERC721Contract,
    create_erc721_contract,
)

# ============================================================================
# ERC1155 Contract
# ============================================================================

from blockchain.smart_contracts.erc1155_contract import (
    ERC1155Action,
    TokenInfo as ERC1155TokenInfo,
    TokenBalance,
    TransferData,
    ERC1155Contract,
    create_erc1155_contract,
)

# ============================================================================
# Aave Contract
# ============================================================================

from blockchain.smart_contracts.aave_contract import (
    AaveVersion,
    AaveAction,
    AaveRiskLevel,
    AaveReserveData,
    AavePosition,
    AaveTransaction,
    FlashLoanParams,
    AaveContract,
    create_aave_contract,
)

# ============================================================================
# Compound Contract
# ============================================================================

from blockchain.smart_contracts.compound_contract import (
    CompoundVersion,
    CompoundAction,
    CompoundRiskLevel,
    CTokenData,
    CompoundPosition,
    CompoundTransaction,
    InterestRateModel,
    CompoundContract,
    create_compound_contract,
)

# ============================================================================
# Uniswap Contract
# ============================================================================

from blockchain.smart_contracts.uniswap_contract import (
    UniswapVersion,
    UniswapAction,
    FeeTier,
    PoolInfo,
    PositionInfo,
    SwapQuote,
    UniswapContract,
    create_uniswap_contract,
)

# ============================================================================
# PancakeSwap Contract
# ============================================================================

from blockchain.smart_contracts.pancake_contract import (
    PancakeAction,
    FarmType,
    PairInfo,
    LiquidityPosition,
    FarmPosition,
    SwapQuote as PancakeSwapQuote,
    PancakeContract,
    create_pancake_contract,
)

# ============================================================================
# Module Information
# ============================================================================

MODULE_INFO = {
    "name": "Smart Contracts",
    "version": __version__,
    "author": __author__,
    "copyright": __copyright__,
    "description": "Comprehensive smart contract integration for NEXUS AI Trading System",
    "components": [
        "Base Contract",
        "Contract ABI",
        "Contract Bytecode",
        "Contract Compiler",
        "Contract Config",
        "Contract Deployer",
        "Contract Interceptor",
        "Contract Manager",
        "Contract Upgrade",
        "Contract Verifier",
        "Contract Audit",
        "ERC20 Contract",
        "ERC721 Contract",
        "ERC1155 Contract",
        "Aave Contract",
        "Compound Contract",
        "Uniswap Contract",
        "PancakeSwap Contract",
    ],
    "supported_standards": [
        "ERC20",
        "ERC721",
        "ERC1155",
        "ERC4626",
        "ERC3156",
        "ERC2612",
    ],
    "supported_protocols": [
        "Aave (V2, V3)",
        "Compound (V2, V3)",
        "Uniswap (V2, V3)",
        "PancakeSwap (V2, V3)",
    ],
}


def get_module_info() -> Dict[str, Any]:
    """Get module information."""
    return MODULE_INFO


def get_version() -> str:
    """Get module version."""
    return __version__


# ============================================================================
# Module Initialization
# ============================================================================

def initialize_module(
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Initialize the smart contracts module.

    Args:
        config: Configuration dictionary for the module

    Returns:
        Dictionary containing initialized components
    """
    logger.info("Initializing Smart Contracts Module...")

    config = config or {}

    # Components that will be initialized
    components = {}

    try:
        # Initialize ABI registry
        components["abi_registry"] = get_abi_registry()

        # Initialize contract manager
        components["contract_manager"] = create_contract_manager(config)

        # Initialize contract compiler
        components["compiler"] = create_contract_compiler(config)

        # Initialize contract config manager
        components["config_manager"] = create_config_manager(
            config.get("config_dir")
        )

        # Initialize contract deployer
        components["deployer"] = create_contract_deployer(config)

        # Initialize contract verifier
        components["verifier"] = create_contract_verifier(
            config.get("web3_client"),
            config.get("verification_config"),
        )

        # Initialize contract auditor
        components["auditor"] = create_contract_auditor(
            config.get("web3_client"),
            config.get("audit_config"),
        )

        # Initialize contract upgrade
        components["upgrade"] = create_contract_upgrade(
            config.get("web3_client"),
            config.get("upgrade_config"),
        )

        # Initialize contract interceptor
        components["interceptor"] = create_contract_interceptor(
            config.get("web3_client"),
            config.get("interceptor_config"),
        )

        # Initialize contract bytecode analyzer
        components["bytecode_analyzer"] = create_bytecode_analyzer(
            config.get("web3_client"),
            config.get("bytecode_config"),
        )

        logger.info("Smart Contracts Module initialized successfully")
        logger.info(f"  - ABI Registry: {len(list_abis())} ABIs registered")
        logger.info("  - Contract Manager: Initialized")
        logger.info("  - Contract Compiler: Initialized")
        logger.info("  - Contract Deployer: Initialized")
        logger.info("  - Contract Verifier: Initialized")
        logger.info("  - Contract Auditor: Initialized")
        logger.info("  - Contract Upgrader: Initialized")
        logger.info("  - Contract Interceptor: Initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Smart Contracts Module: {e}")
        raise

    return components


# ============================================================================
# Quick Access Functions
# ============================================================================

def create_contract(
    web3_client,
    contract_address: str,
    contract_type: str,
    config: Optional[Dict[str, Any]] = None,
) -> BaseContract:
    """
    Create a contract instance by type.

    Args:
        web3_client: Web3 client instance
        contract_address: Contract address
        contract_type: Contract type (e.g., "ERC20", "ERC721", "Aave")
        config: Configuration dictionary

    Returns:
        Contract instance
    """
    contract_type = contract_type.lower()
    config = config or {}

    if contract_type == "erc20":
        return create_erc20_contract(web3_client, contract_address, config)
    elif contract_type == "erc721":
        return create_erc721_contract(web3_client, contract_address, config)
    elif contract_type == "erc1155":
        return create_erc1155_contract(web3_client, contract_address, config)
    elif contract_type in ["aave", "aave_v3"]:
        return create_aave_contract(web3_client, config.get("version", "v3"), config)
    elif contract_type in ["compound", "compound_v2"]:
        return create_compound_contract(web3_client, config.get("version", "v2"), config)
    elif contract_type in ["uniswap", "uniswap_v3"]:
        return create_uniswap_contract(web3_client, config.get("version", "v3"), config)
    elif contract_type in ["pancake", "pancakeswap", "pancake_v2"]:
        return create_pancake_contract(web3_client, config.get("version", "v2"), config)
    else:
        raise ValueError(f"Unknown contract type: {contract_type}")


def get_supported_contracts() -> Dict[str, str]:
    """
    Get list of supported contract types.

    Returns:
        Dictionary of supported contract types
    """
    return {
        "erc20": "ERC20 Token",
        "erc721": "ERC721 NFT",
        "erc1155": "ERC1155 Multi-Token",
        "aave_v3": "Aave V3",
        "compound_v2": "Compound V2",
        "uniswap_v3": "Uniswap V3",
        "pancake_v2": "PancakeSwap V2",
    }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Print module info
    print(f"Smart Contracts Module v{__version__}")
    print(f"Author: {__author__}")
    print(f"\nSupported Components:")
    for component in MODULE_INFO["components"]:
        print(f"  - {component}")
    print(f"\nSupported Standards:")
    for standard in MODULE_INFO["supported_standards"]:
        print(f"  - {standard}")
    print(f"\nSupported Protocols:")
    for protocol in MODULE_INFO["supported_protocols"]:
        print(f"  - {protocol}")

    # Print available ABIs
    print(f"\nRegistered ABIs:")
    for abi_name in list_abis():
        print(f"  - {abi_name}")

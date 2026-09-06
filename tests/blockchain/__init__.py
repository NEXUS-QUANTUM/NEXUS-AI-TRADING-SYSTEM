# tests/blockchain/__init__.py
"""
Blockchain Module Tests for the NEXUS AI Trading System.

This package contains all unit and integration tests for the blockchain
services, including web3 client, wallet management, smart contracts,
DeFi protocols, NFTs, staking, bridges, and on-chain analytics.

All tests adhere to the NEXUS development standards and use shared fixtures
from conftest.py.
"""

# Import test modules to make them available as submodules
from . import conftest
from . import test_blockchain_integration
from . import test_bridges
from . import test_defi_protocols
from . import test_nft_manager
from . import test_onchain_analysis
from . import test_smart_contracts
from . import test_staking
from . import test_wallet_manager
from . import test_web3_client

# Expose test modules for easy import
__all__ = [
    "conftest",
    "test_blockchain_integration",
    "test_bridges",
    "test_defi_protocols",
    "test_nft_manager",
    "test_onchain_analysis",
    "test_smart_contracts",
    "test_staking",
    "test_wallet_manager",
    "test_web3_client",
]

# Optional: package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"

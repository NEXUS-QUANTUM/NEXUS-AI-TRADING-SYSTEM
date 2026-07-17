# blockchain/smart-contracts/contract_abi.py
# NEXUS AI TRADING SYSTEM - Smart Contract ABI Definitions and Management
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Comprehensive Smart Contract ABI definitions and management system.
Provides standardized ABI definitions for all major DeFi protocols,
ERC standards, and custom contract interfaces used in the NEXUS ecosystem.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

# NEXUS Imports
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.abi")


# ============================================================================
# Enums & Constants
# ============================================================================

class ContractStandard(str, Enum):
    """Smart contract standards."""
    ERC20 = "ERC20"
    ERC721 = "ERC721"
    ERC1155 = "ERC1155"
    ERC4626 = "ERC4626"
    ERC777 = "ERC777"
    ERC1363 = "ERC1363"
    ERC223 = "ERC223"
    ERC3156 = "ERC3156"  # Flash Loans
    ERC2612 = "ERC2612"  # Permit
    ERC1271 = "ERC1271"  # Signature Validation


class ProtocolType(str, Enum):
    """DeFi protocol types."""
    LENDING = "lending"
    DEX = "dex"
    YIELD = "yield"
    STAKING = "staking"
    DERIVATIVES = "derivatives"
    INSURANCE = "insurance"
    ORACLE = "oracle"
    GOVERNANCE = "governance"
    BRIDGE = "bridge"
    AGGREGATOR = "aggregator"


class FunctionType(str, Enum):
    """Function types."""
    VIEW = "view"
    PURE = "pure"
    NONPAYABLE = "nonpayable"
    PAYABLE = "payable"


@dataclass
class ABIParameter:
    """ABI parameter definition."""
    name: str
    type: str
    internal_type: Optional[str] = None
    components: Optional[List["ABIParameter"]] = None


@dataclass
class ABIFunction:
    """ABI function definition."""
    name: str
    type: str = "function"
    inputs: List[ABIParameter] = field(default_factory=list)
    outputs: List[ABIParameter] = field(default_factory=list)
    state_mutability: str = FunctionType.NONPAYABLE
    payable: bool = False
    constant: bool = False
    anonymous: bool = False
    indexed: bool = False


@dataclass
class ABIEvent:
    """ABI event definition."""
    name: str
    type: str = "event"
    inputs: List[ABIParameter] = field(default_factory=list)
    anonymous: bool = False


@dataclass
class ABIError:
    """ABI error definition."""
    name: str
    type: str = "error"
    inputs: List[ABIParameter] = field(default_factory=list)


@dataclass
class ContractABI:
    """Complete contract ABI definition."""
    contract_name: str
    standard: Optional[ContractStandard] = None
    protocol: Optional[ProtocolType] = None
    version: str = "1.0.0"
    functions: List[ABIFunction] = field(default_factory=list)
    events: List[ABIEvent] = field(default_factory=list)
    errors: List[ABIError] = field(default_factory=list)
    constructor: Optional[ABIFunction] = None
    fallback: Optional[ABIFunction] = None
    receive: Optional[ABIFunction] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> List[Dict[str, Any]]:
        """Convert to dictionary format for web3.py."""
        abi = []

        # Add functions
        for func in self.functions:
            abi.append({
                "name": func.name,
                "type": func.type,
                "inputs": self._params_to_dict(func.inputs),
                "outputs": self._params_to_dict(func.outputs),
                "stateMutability": func.state_mutability,
                "payable": func.payable,
                "constant": func.constant,
                "anonymous": func.anonymous,
                "indexed": func.indexed,
            })

        # Add events
        for event in self.events:
            abi.append({
                "name": event.name,
                "type": event.type,
                "inputs": self._params_to_dict(event.inputs),
                "anonymous": event.anonymous,
            })

        # Add errors
        for error in self.errors:
            abi.append({
                "name": error.name,
                "type": error.type,
                "inputs": self._params_to_dict(error.inputs),
            })

        # Add constructor
        if self.constructor:
            abi.append({
                "name": self.constructor.name,
                "type": "constructor",
                "inputs": self._params_to_dict(self.constructor.inputs),
                "stateMutability": self.constructor.state_mutability,
            })

        # Add fallback
        if self.fallback:
            abi.append({
                "name": "fallback",
                "type": "fallback",
                "stateMutability": self.fallback.state_mutability,
            })

        # Add receive
        if self.receive:
            abi.append({
                "name": "receive",
                "type": "receive",
                "stateMutability": self.receive.state_mutability,
            })

        return abi

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @staticmethod
    def _params_to_dict(params: List[ABIParameter]) -> List[Dict[str, Any]]:
        """Convert parameters to dictionary."""
        result = []
        for param in params:
            param_dict = {
                "name": param.name,
                "type": param.type,
            }
            if param.internal_type:
                param_dict["internalType"] = param.internal_type
            if param.components:
                param_dict["components"] = ContractABI._params_to_dict(param.components)
            result.append(param_dict)
        return result


# ============================================================================
# ABI Registry
# ============================================================================

class ABIRegistry:
    """
    Central registry for smart contract ABIs.
    Provides access to pre-defined ABIs for common contracts and standards.
    """

    _instance = None
    _abis: Dict[str, ContractABI] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the registry with built-in ABIs."""
        self._register_erc20()
        self._register_erc721()
        self._register_erc1155()
        self._register_erc4626()
        self._register_uniswap_v2()
        self._register_uniswap_v3()
        self._register_aave_v3()
        self._register_compound_v2()
        self._register_curve()
        self._register_balancer()
        self._register_chainlink()
        self._register_staking()
        self._register_governance()
        self._register_flash_loan()
        self._register_multi_call()

    def get_abi(self, name: str) -> Optional[ContractABI]:
        """Get ABI by name."""
        return self._abis.get(name)

    def get_abi_dict(self, name: str) -> Optional[List[Dict[str, Any]]]:
        """Get ABI as dictionary."""
        abi = self.get_abi(name)
        return abi.to_dict() if abi else None

    def get_abi_json(self, name: str, indent: int = 2) -> Optional[str]:
        """Get ABI as JSON string."""
        abi = self.get_abi(name)
        return abi.to_json(indent) if abi else None

    def register_abi(self, name: str, abi: ContractABI) -> None:
        """Register a new ABI."""
        self._abis[name] = abi
        logger.info(f"Registered ABI: {name}")

    def list_abis(self) -> List[str]:
        """List all registered ABI names."""
        return list(self._abis.keys())

    # -----------------------------------------------------------------------
    # ABI Definitions
    # -----------------------------------------------------------------------

    def _register_erc20(self) -> None:
        """Register ERC20 standard ABI."""
        abi = ContractABI(
            contract_name="ERC20",
            standard=ContractStandard.ERC20,
            description="Standard ERC20 Token Interface",
        )

        # View functions
        abi.functions.extend([
            ABIFunction(
                name="name",
                state_mutability=FunctionType.VIEW,
                outputs=[ABIParameter(name="", type="string")]
            ),
            ABIFunction(
                name="symbol",
                state_mutability=FunctionType.VIEW,
                outputs=[ABIParameter(name="", type="string")]
            ),
            ABIFunction(
                name="decimals",
                state_mutability=FunctionType.VIEW,
                outputs=[ABIParameter(name="", type="uint8")]
            ),
            ABIFunction(
                name="totalSupply",
                state_mutability=FunctionType.VIEW,
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="balanceOf",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="account", type="address")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="allowance",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="owner", type="address"),
                    ABIParameter(name="spender", type="address")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
        ])

        # Write functions
        abi.functions.extend([
            ABIFunction(
                name="transfer",
                inputs=[
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="amount", type="uint256")
                ],
                outputs=[ABIParameter(name="", type="bool")]
            ),
            ABIFunction(
                name="transferFrom",
                inputs=[
                    ABIParameter(name="from", type="address"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="amount", type="uint256")
                ],
                outputs=[ABIParameter(name="", type="bool")]
            ),
            ABIFunction(
                name="approve",
                inputs=[
                    ABIParameter(name="spender", type="address"),
                    ABIParameter(name="amount", type="uint256")
                ],
                outputs=[ABIParameter(name="", type="bool")]
            ),
        ])

        # Events
        abi.events.extend([
            ABIEvent(
                name="Transfer",
                inputs=[
                    ABIParameter(name="from", type="address", indexed=True),
                    ABIParameter(name="to", type="address", indexed=True),
                    ABIParameter(name="value", type="uint256")
                ]
            ),
            ABIEvent(
                name="Approval",
                inputs=[
                    ABIParameter(name="owner", type="address", indexed=True),
                    ABIParameter(name="spender", type="address", indexed=True),
                    ABIParameter(name="value", type="uint256")
                ]
            ),
        ])

        self.register_abi("ERC20", abi)

    def _register_erc721(self) -> None:
        """Register ERC721 standard ABI."""
        abi = ContractABI(
            contract_name="ERC721",
            standard=ContractStandard.ERC721,
            description="Standard ERC721 NFT Interface",
        )

        # View functions
        abi.functions.extend([
            ABIFunction(
                name="balanceOf",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="owner", type="address")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="ownerOf",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="tokenId", type="uint256")],
                outputs=[ABIParameter(name="", type="address")]
            ),
            ABIFunction(
                name="getApproved",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="tokenId", type="uint256")],
                outputs=[ABIParameter(name="", type="address")]
            ),
            ABIFunction(
                name="isApprovedForAll",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="owner", type="address"),
                    ABIParameter(name="operator", type="address")
                ],
                outputs=[ABIParameter(name="", type="bool")]
            ),
        ])

        # Write functions
        abi.functions.extend([
            ABIFunction(
                name="transferFrom",
                inputs=[
                    ABIParameter(name="from", type="address"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="tokenId", type="uint256")
                ]
            ),
            ABIFunction(
                name="safeTransferFrom",
                inputs=[
                    ABIParameter(name="from", type="address"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="tokenId", type="uint256")
                ],
                state_mutability=FunctionType.PAYABLE
            ),
            ABIFunction(
                name="approve",
                inputs=[
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="tokenId", type="uint256")
                ]
            ),
            ABIFunction(
                name="setApprovalForAll",
                inputs=[
                    ABIParameter(name="operator", type="address"),
                    ABIParameter(name="approved", type="bool")
                ]
            ),
        ])

        # Events
        abi.events.extend([
            ABIEvent(
                name="Transfer",
                inputs=[
                    ABIParameter(name="from", type="address", indexed=True),
                    ABIParameter(name="to", type="address", indexed=True),
                    ABIParameter(name="tokenId", type="uint256", indexed=True)
                ]
            ),
            ABIEvent(
                name="Approval",
                inputs=[
                    ABIParameter(name="owner", type="address", indexed=True),
                    ABIParameter(name="approved", type="address", indexed=True),
                    ABIParameter(name="tokenId", type="uint256", indexed=True)
                ]
            ),
            ABIEvent(
                name="ApprovalForAll",
                inputs=[
                    ABIParameter(name="owner", type="address", indexed=True),
                    ABIParameter(name="operator", type="address", indexed=True),
                    ABIParameter(name="approved", type="bool")
                ]
            ),
        ])

        self.register_abi("ERC721", abi)

    def _register_erc1155(self) -> None:
        """Register ERC1155 standard ABI."""
        abi = ContractABI(
            contract_name="ERC1155",
            standard=ContractStandard.ERC1155,
            description="Standard ERC1155 Multi-Token Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="balanceOf",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="account", type="address"),
                    ABIParameter(name="id", type="uint256")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="balanceOfBatch",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="accounts", type="address[]"),
                    ABIParameter(name="ids", type="uint256[]")
                ],
                outputs=[ABIParameter(name="", type="uint256[]")]
            ),
            ABIFunction(
                name="isApprovedForAll",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="account", type="address"),
                    ABIParameter(name="operator", type="address")
                ],
                outputs=[ABIParameter(name="", type="bool")]
            ),
            ABIFunction(
                name="safeTransferFrom",
                inputs=[
                    ABIParameter(name="from", type="address"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="id", type="uint256"),
                    ABIParameter(name="amount", type="uint256"),
                    ABIParameter(name="data", type="bytes")
                ]
            ),
            ABIFunction(
                name="safeBatchTransferFrom",
                inputs=[
                    ABIParameter(name="from", type="address"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="ids", type="uint256[]"),
                    ABIParameter(name="amounts", type="uint256[]"),
                    ABIParameter(name="data", type="bytes")
                ]
            ),
            ABIFunction(
                name="setApprovalForAll",
                inputs=[
                    ABIParameter(name="operator", type="address"),
                    ABIParameter(name="approved", type="bool")
                ]
            ),
            ABIFunction(
                name="uri",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="id", type="uint256")],
                outputs=[ABIParameter(name="", type="string")]
            ),
        ])

        abi.events.extend([
            ABIEvent(
                name="TransferSingle",
                inputs=[
                    ABIParameter(name="operator", type="address", indexed=True),
                    ABIParameter(name="from", type="address", indexed=True),
                    ABIParameter(name="to", type="address", indexed=True),
                    ABIParameter(name="id", type="uint256"),
                    ABIParameter(name="value", type="uint256")
                ]
            ),
            ABIEvent(
                name="TransferBatch",
                inputs=[
                    ABIParameter(name="operator", type="address", indexed=True),
                    ABIParameter(name="from", type="address", indexed=True),
                    ABIParameter(name="to", type="address", indexed=True),
                    ABIParameter(name="ids", type="uint256[]"),
                    ABIParameter(name="values", type="uint256[]")
                ]
            ),
            ABIEvent(
                name="ApprovalForAll",
                inputs=[
                    ABIParameter(name="account", type="address", indexed=True),
                    ABIParameter(name="operator", type="address", indexed=True),
                    ABIParameter(name="approved", type="bool")
                ]
            ),
        ])

        self.register_abi("ERC1155", abi)

    def _register_erc4626(self) -> None:
        """Register ERC4626 Tokenized Vault standard ABI."""
        abi = ContractABI(
            contract_name="ERC4626",
            standard=ContractStandard.ERC4626,
            description="Standard ERC4626 Tokenized Vault Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="asset",
                state_mutability=FunctionType.VIEW,
                outputs=[ABIParameter(name="", type="address")]
            ),
            ABIFunction(
                name="totalAssets",
                state_mutability=FunctionType.VIEW,
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="convertToShares",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="assets", type="uint256")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="convertToAssets",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="shares", type="uint256")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="maxDeposit",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="receiver", type="address")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="previewDeposit",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="assets", type="uint256")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="deposit",
                state_mutability=FunctionType.PAYABLE,
                inputs=[
                    ABIParameter(name="assets", type="uint256"),
                    ABIParameter(name="receiver", type="address")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="redeem",
                inputs=[
                    ABIParameter(name="shares", type="uint256"),
                    ABIParameter(name="receiver", type="address"),
                    ABIParameter(name="owner", type="address")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="withdraw",
                inputs=[
                    ABIParameter(name="assets", type="uint256"),
                    ABIParameter(name="receiver", type="address"),
                    ABIParameter(name="owner", type="address")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
        ])

        self.register_abi("ERC4626", abi)

    def _register_uniswap_v2(self) -> None:
        """Register Uniswap V2 ABI."""
        abi = ContractABI(
            contract_name="UniswapV2",
            protocol=ProtocolType.DEX,
            version="2.0.0",
            description="Uniswap V2 Router and Factory Interface",
        )

        # Router functions
        abi.functions.extend([
            ABIFunction(
                name="addLiquidity",
                inputs=[
                    ABIParameter(name="tokenA", type="address"),
                    ABIParameter(name="tokenB", type="address"),
                    ABIParameter(name="amountADesired", type="uint256"),
                    ABIParameter(name="amountBDesired", type="uint256"),
                    ABIParameter(name="amountAMin", type="uint256"),
                    ABIParameter(name="amountBMin", type="uint256"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="deadline", type="uint256")
                ],
                outputs=[
                    ABIParameter(name="amountA", type="uint256"),
                    ABIParameter(name="amountB", type="uint256"),
                    ABIParameter(name="liquidity", type="uint256")
                ]
            ),
            ABIFunction(
                name="removeLiquidity",
                inputs=[
                    ABIParameter(name="tokenA", type="address"),
                    ABIParameter(name="tokenB", type="address"),
                    ABIParameter(name="liquidity", type="uint256"),
                    ABIParameter(name="amountAMin", type="uint256"),
                    ABIParameter(name="amountBMin", type="uint256"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="deadline", type="uint256")
                ],
                outputs=[
                    ABIParameter(name="amountA", type="uint256"),
                    ABIParameter(name="amountB", type="uint256")
                ]
            ),
            ABIFunction(
                name="swapExactTokensForTokens",
                inputs=[
                    ABIParameter(name="amountIn", type="uint256"),
                    ABIParameter(name="amountOutMin", type="uint256"),
                    ABIParameter(name="path", type="address[]"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="deadline", type="uint256")
                ],
                outputs=[ABIParameter(name="amounts", type="uint256[]")]
            ),
            ABIFunction(
                name="swapTokensForExactTokens",
                inputs=[
                    ABIParameter(name="amountOut", type="uint256"),
                    ABIParameter(name="amountInMax", type="uint256"),
                    ABIParameter(name="path", type="address[]"),
                    ABIParameter(name="to", type="address"),
                    ABIParameter(name="deadline", type="uint256")
                ],
                outputs=[ABIParameter(name="amounts", type="uint256[]")]
            ),
            ABIFunction(
                name="getAmountsOut",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="amountIn", type="uint256"),
                    ABIParameter(name="path", type="address[]")
                ],
                outputs=[ABIParameter(name="amounts", type="uint256[]")]
            ),
            ABIFunction(
                name="getAmountsIn",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="amountOut", type="uint256"),
                    ABIParameter(name="path", type="address[]")
                ],
                outputs=[ABIParameter(name="amounts", type="uint256[]")]
            ),
        ])

        self.register_abi("UniswapV2", abi)

    def _register_uniswap_v3(self) -> None:
        """Register Uniswap V3 ABI."""
        abi = ContractABI(
            contract_name="UniswapV3",
            protocol=ProtocolType.DEX,
            version="3.0.0",
            description="Uniswap V3 Router and Pool Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="exactInputSingle",
                inputs=[
                    ABIParameter(
                        name="params",
                        type="tuple",
                        components=[
                            ABIParameter(name="tokenIn", type="address"),
                            ABIParameter(name="tokenOut", type="address"),
                            ABIParameter(name="fee", type="uint24"),
                            ABIParameter(name="recipient", type="address"),
                            ABIParameter(name="deadline", type="uint256"),
                            ABIParameter(name="amountIn", type="uint256"),
                            ABIParameter(name="amountOutMinimum", type="uint256"),
                            ABIParameter(name="sqrtPriceLimitX96", type="uint160"),
                        ]
                    )
                ],
                outputs=[ABIParameter(name="amountOut", type="uint256")]
            ),
            ABIFunction(
                name="exactOutputSingle",
                inputs=[
                    ABIParameter(
                        name="params",
                        type="tuple",
                        components=[
                            ABIParameter(name="tokenIn", type="address"),
                            ABIParameter(name="tokenOut", type="address"),
                            ABIParameter(name="fee", type="uint24"),
                            ABIParameter(name="recipient", type="address"),
                            ABIParameter(name="deadline", type="uint256"),
                            ABIParameter(name="amountOut", type="uint256"),
                            ABIParameter(name="amountInMaximum", type="uint256"),
                            ABIParameter(name="sqrtPriceLimitX96", type="uint160"),
                        ]
                    )
                ],
                outputs=[ABIParameter(name="amountIn", type="uint256")]
            ),
            ABIFunction(
                name="exactInput",
                inputs=[
                    ABIParameter(
                        name="params",
                        type="tuple",
                        components=[
                            ABIParameter(name="path", type="bytes"),
                            ABIParameter(name="recipient", type="address"),
                            ABIParameter(name="deadline", type="uint256"),
                            ABIParameter(name="amountIn", type="uint256"),
                            ABIParameter(name="amountOutMinimum", type="uint256"),
                        ]
                    )
                ],
                outputs=[ABIParameter(name="amountOut", type="uint256")]
            ),
            ABIFunction(
                name="exactOutput",
                inputs=[
                    ABIParameter(
                        name="params",
                        type="tuple",
                        components=[
                            ABIParameter(name="path", type="bytes"),
                            ABIParameter(name="recipient", type="address"),
                            ABIParameter(name="deadline", type="uint256"),
                            ABIParameter(name="amountOut", type="uint256"),
                            ABIParameter(name="amountInMaximum", type="uint256"),
                        ]
                    )
                ],
                outputs=[ABIParameter(name="amountIn", type="uint256")]
            ),
        ])

        self.register_abi("UniswapV3", abi)

    def _register_aave_v3(self) -> None:
        """Register Aave V3 ABI."""
        abi = ContractABI(
            contract_name="AaveV3",
            protocol=ProtocolType.LENDING,
            version="3.0.0",
            description="Aave V3 Lending Pool Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="supply",
                inputs=[
                    ABIParameter(name="asset", type="address"),
                    ABIParameter(name="amount", type="uint256"),
                    ABIParameter(name="onBehalfOf", type="address"),
                    ABIParameter(name="referralCode", type="uint16")
                ],
                outputs=[]
            ),
            ABIFunction(
                name="withdraw",
                inputs=[
                    ABIParameter(name="asset", type="address"),
                    ABIParameter(name="amount", type="uint256"),
                    ABIParameter(name="to", type="address")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="borrow",
                inputs=[
                    ABIParameter(name="asset", type="address"),
                    ABIParameter(name="amount", type="uint256"),
                    ABIParameter(name="interestRateMode", type="uint256"),
                    ABIParameter(name="referralCode", type="uint16"),
                    ABIParameter(name="onBehalfOf", type="address")
                ],
                outputs=[]
            ),
            ABIFunction(
                name="repay",
                inputs=[
                    ABIParameter(name="asset", type="address"),
                    ABIParameter(name="amount", type="uint256"),
                    ABIParameter(name="interestRateMode", type="uint256"),
                    ABIParameter(name="onBehalfOf", type="address")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="getUserAccountData",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="user", type="address")],
                outputs=[
                    ABIParameter(name="totalCollateralBase", type="uint256"),
                    ABIParameter(name="totalDebtBase", type="uint256"),
                    ABIParameter(name="availableBorrowsBase", type="uint256"),
                    ABIParameter(name="currentLiquidationThreshold", type="uint256"),
                    ABIParameter(name="ltv", type="uint256"),
                    ABIParameter(name="healthFactor", type="uint256"),
                ]
            ),
            ABIFunction(
                name="getReserveData",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="asset", type="address")],
                outputs=[
                    ABIParameter(
                        name="data",
                        type="tuple",
                        components=[
                            ABIParameter(name="configuration", type="uint256"),
                            ABIParameter(name="liquidityIndex", type="uint128"),
                            ABIParameter(name="variableBorrowIndex", type="uint128"),
                            ABIParameter(name="liquidityRate", type="uint128"),
                            ABIParameter(name="variableBorrowRate", type="uint128"),
                            ABIParameter(name="stableBorrowRate", type="uint128"),
                            ABIParameter(name="averageStableBorrowRate", type="uint128"),
                            ABIParameter(name="lastUpdateTimestamp", type="uint40"),
                        ]
                    )
                ]
            ),
            ABIFunction(
                name="flashLoan",
                inputs=[
                    ABIParameter(name="receiver", type="address"),
                    ABIParameter(name="assets", type="address[]"),
                    ABIParameter(name="amounts", type="uint256[]"),
                    ABIParameter(name="modes", type="uint256[]"),
                    ABIParameter(name="onBehalfOf", type="address"),
                    ABIParameter(name="params", type="bytes"),
                    ABIParameter(name="referralCode", type="uint16")
                ],
                outputs=[]
            ),
        ])

        self.register_abi("AaveV3", abi)

    def _register_compound_v2(self) -> None:
        """Register Compound V2 ABI."""
        abi = ContractABI(
            contract_name="CompoundV2",
            protocol=ProtocolType.LENDING,
            version="2.0.0",
            description="Compound V2 Comptroller and cToken Interface",
        )

        # Comptroller functions
        abi.functions.extend([
            ABIFunction(
                name="enterMarkets",
                inputs=[ABIParameter(name="cTokens", type="address[]")],
                outputs=[ABIParameter(name="", type="uint256[]")]
            ),
            ABIFunction(
                name="exitMarket",
                inputs=[ABIParameter(name="cTokenAddress", type="address")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="getAccountLiquidity",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="account", type="address")],
                outputs=[
                    ABIParameter(name="err", type="uint256"),
                    ABIParameter(name="liquidity", type="uint256"),
                    ABIParameter(name="shortfall", type="uint256"),
                ]
            ),
            ABIFunction(
                name="getAllMarkets",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="address[]")]
            ),
        ])

        # cToken functions
        abi.functions.extend([
            ABIFunction(
                name="mint",
                inputs=[ABIParameter(name="mintAmount", type="uint256")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="redeem",
                inputs=[ABIParameter(name="redeemTokens", type="uint256")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="redeemUnderlying",
                inputs=[ABIParameter(name="redeemAmount", type="uint256")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="borrow",
                inputs=[ABIParameter(name="borrowAmount", type="uint256")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="repayBorrow",
                inputs=[ABIParameter(name="repayAmount", type="uint256")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="liquidateBorrow",
                inputs=[
                    ABIParameter(name="borrower", type="address"),
                    ABIParameter(name="repayAmount", type="uint256"),
                    ABIParameter(name="cTokenCollateral", type="address")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="exchangeRateStored",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="borrowRatePerBlock",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="supplyRatePerBlock",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
        ])

        self.register_abi("CompoundV2", abi)

    def _register_curve(self) -> None:
        """Register Curve Protocol ABI."""
        abi = ContractABI(
            contract_name="Curve",
            protocol=ProtocolType.DEX,
            version="2.0.0",
            description="Curve StableSwap Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="get_virtual_price",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="get_dy",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="i", type="int128"),
                    ABIParameter(name="j", type="int128"),
                    ABIParameter(name="dx", type="uint256")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="exchange",
                inputs=[
                    ABIParameter(name="i", type="int128"),
                    ABIParameter(name="j", type="int128"),
                    ABIParameter(name="dx", type="uint256"),
                    ABIParameter(name="min_dy", type="uint256")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="add_liquidity",
                inputs=[
                    ABIParameter(name="amounts", type="uint256[]"),
                    ABIParameter(name="min_mint_amount", type="uint256")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="remove_liquidity",
                inputs=[
                    ABIParameter(name="_amount", type="uint256"),
                    ABIParameter(name="min_amounts", type="uint256[]")
                ],
                outputs=[ABIParameter(name="", type="uint256[]")]
            ),
            ABIFunction(
                name="get_lp_price",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
        ])

        self.register_abi("Curve", abi)

    def _register_balancer(self) -> None:
        """Register Balancer Protocol ABI."""
        abi = ContractABI(
            contract_name="Balancer",
            protocol=ProtocolType.DEX,
            version="2.0.0",
            description="Balancer V2 Vault Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="batchSwap",
                inputs=[
                    ABIParameter(name="kind", type="uint8"),
                    ABIParameter(
                        name="swaps",
                        type="tuple[]",
                        components=[
                            ABIParameter(name="poolId", type="bytes32"),
                            ABIParameter(name="assetInIndex", type="uint256"),
                            ABIParameter(name="assetOutIndex", type="uint256"),
                            ABIParameter(name="amount", type="uint256"),
                            ABIParameter(name="userData", type="bytes"),
                        ]
                    ),
                    ABIParameter(name="assets", type="address[]"),
                    ABIParameter(name="funds", type="tuple"),
                    ABIParameter(name="limits", type="int256[]"),
                    ABIParameter(name="deadline", type="uint256")
                ],
                outputs=[
                    ABIParameter(name="delta", type="int256[]"),
                    ABIParameter(name="assetDeltas", type="int256[]")
                ]
            ),
            ABIFunction(
                name="joinPool",
                inputs=[
                    ABIParameter(name="poolId", type="bytes32"),
                    ABIParameter(name="sender", type="address"),
                    ABIParameter(name="recipient", type="address"),
                    ABIParameter(
                        name="joinPoolRequest",
                        type="tuple",
                        components=[
                            ABIParameter(name="assets", type="address[]"),
                            ABIParameter(name="maxAmountsIn", type="uint256[]"),
                            ABIParameter(name="userData", type="bytes"),
                            ABIParameter(name="fromInternalBalance", type="bool"),
                        ]
                    )
                ],
                outputs=[]
            ),
            ABIFunction(
                name="exitPool",
                inputs=[
                    ABIParameter(name="poolId", type="bytes32"),
                    ABIParameter(name="sender", type="address"),
                    ABIParameter(name="recipient", type="address"),
                    ABIParameter(
                        name="exitPoolRequest",
                        type="tuple",
                        components=[
                            ABIParameter(name="assets", type="address[]"),
                            ABIParameter(name="minAmountsOut", type="uint256[]"),
                            ABIParameter(name="userData", type="bytes"),
                            ABIParameter(name="toInternalBalance", type="bool"),
                        ]
                    )
                ],
                outputs=[]
            ),
        ])

        self.register_abi("Balancer", abi)

    def _register_chainlink(self) -> None:
        """Register Chainlink Oracle ABI."""
        abi = ContractABI(
            contract_name="Chainlink",
            protocol=ProtocolType.ORACLE,
            version="1.0.0",
            description="Chainlink Price Feed Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="latestRoundData",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[
                    ABIParameter(name="roundId", type="uint80"),
                    ABIParameter(name="answer", type="int256"),
                    ABIParameter(name="startedAt", type="uint256"),
                    ABIParameter(name="updatedAt", type="uint256"),
                    ABIParameter(name="answeredInRound", type="uint80"),
                ]
            ),
            ABIFunction(
                name="getRoundData",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="_roundId", type="uint80")],
                outputs=[
                    ABIParameter(name="roundId", type="uint80"),
                    ABIParameter(name="answer", type="int256"),
                    ABIParameter(name="startedAt", type="uint256"),
                    ABIParameter(name="updatedAt", type="uint256"),
                    ABIParameter(name="answeredInRound", type="uint80"),
                ]
            ),
            ABIFunction(
                name="decimals",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="uint8")]
            ),
            ABIFunction(
                name="description",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="string")]
            ),
        ])

        self.register_abi("Chainlink", abi)

    def _register_staking(self) -> None:
        """Register Staking Contract ABI."""
        abi = ContractABI(
            contract_name="Staking",
            protocol=ProtocolType.STAKING,
            version="1.0.0",
            description="Standard Staking Contract Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="stake",
                state_mutability=FunctionType.PAYABLE,
                inputs=[ABIParameter(name="amount", type="uint256")],
                outputs=[]
            ),
            ABIFunction(
                name="unstake",
                inputs=[ABIParameter(name="amount", type="uint256")],
                outputs=[]
            ),
            ABIFunction(
                name="claimRewards",
                inputs=[],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="getRewardRate",
                state_mutability=FunctionType.VIEW,
                inputs=[],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="getStakedBalance",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="user", type="address")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="getRewardsBalance",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="user", type="address")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
        ])

        self.register_abi("Staking", abi)

    def _register_governance(self) -> None:
        """Register Governance Contract ABI."""
        abi = ContractABI(
            contract_name="Governance",
            protocol=ProtocolType.GOVERNANCE,
            version="1.0.0",
            description="Standard Governance Contract Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="propose",
                inputs=[
                    ABIParameter(name="targets", type="address[]"),
                    ABIParameter(name="values", type="uint256[]"),
                    ABIParameter(name="calldatas", type="bytes[]"),
                    ABIParameter(name="description", type="string")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="execute",
                inputs=[
                    ABIParameter(name="proposalId", type="uint256"),
                    ABIParameter(name="targets", type="address[]"),
                    ABIParameter(name="values", type="uint256[]"),
                    ABIParameter(name="calldatas", type="bytes[]"),
                    ABIParameter(name="description", type="string")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="cancel",
                inputs=[ABIParameter(name="proposalId", type="uint256")],
                outputs=[]
            ),
            ABIFunction(
                name="castVote",
                inputs=[
                    ABIParameter(name="proposalId", type="uint256"),
                    ABIParameter(name="support", type="uint8")
                ],
                outputs=[]
            ),
            ABIFunction(
                name="getProposalState",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="proposalId", type="uint256")],
                outputs=[ABIParameter(name="", type="uint8")]
            ),
        ])

        self.register_abi("Governance", abi)

    def _register_flash_loan(self) -> None:
        """Register Flash Loan Contract ABI."""
        abi = ContractABI(
            contract_name="FlashLoan",
            protocol=ProtocolType.LENDING,
            version="1.0.0",
            description="ERC3156 Flash Loan Interface",
        )

        abi.functions.extend([
            ABIFunction(
                name="flashLoan",
                inputs=[
                    ABIParameter(name="receiver", type="address"),
                    ABIParameter(name="token", type="address"),
                    ABIParameter(name="amount", type="uint256"),
                    ABIParameter(name="data", type="bytes")
                ],
                outputs=[
                    ABIParameter(name="", type="bool"),
                    ABIParameter(name="", type="uint256"),
                ]
            ),
            ABIFunction(
                name="maxFlashLoan",
                state_mutability=FunctionType.VIEW,
                inputs=[ABIParameter(name="token", type="address")],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
            ABIFunction(
                name="flashFee",
                state_mutability=FunctionType.VIEW,
                inputs=[
                    ABIParameter(name="token", type="address"),
                    ABIParameter(name="amount", type="uint256")
                ],
                outputs=[ABIParameter(name="", type="uint256")]
            ),
        ])

        self.register_abi("FlashLoan", abi)

    def _register_multi_call(self) -> None:
        """Register MultiCall Contract ABI."""
        abi = ContractABI(
            contract_name="MultiCall",
            description="MultiCall Contract for Batch Operations",
        )

        abi.functions.extend([
            ABIFunction(
                name="aggregate",
                inputs=[
                    ABIParameter(
                        name="calls",
                        type="tuple[]",
                        components=[
                            ABIParameter(name="target", type="address"),
                            ABIParameter(name="callData", type="bytes"),
                        ]
                    )
                ],
                outputs=[
                    ABIParameter(name="blockNumber", type="uint256"),
                    ABIParameter(name="returnData", type="bytes[]"),
                ]
            ),
            ABIFunction(
                name="tryAggregate",
                inputs=[
                    ABIParameter(name="requireSuccess", type="bool"),
                    ABIParameter(
                        name="calls",
                        type="tuple[]",
                        components=[
                            ABIParameter(name="target", type="address"),
                            ABIParameter(name="callData", type="bytes"),
                        ]
                    )
                ],
                outputs=[
                    ABIParameter(
                        name="returnData",
                        type="tuple[]",
                        components=[
                            ABIParameter(name="success", type="bool"),
                            ABIParameter(name="returnData", type="bytes"),
                        ]
                    )
                ]
            ),
        ])

        self.register_abi("MultiCall", abi)


# ============================================================================
# Singleton Access
# ============================================================================

_registry_instance = None


def get_abi_registry() -> ABIRegistry:
    """Get the global ABI registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ABIRegistry()
    return _registry_instance


def get_abi(name: str) -> Optional[ContractABI]:
    """Get ABI by name from the registry."""
    return get_abi_registry().get_abi(name)


def get_abi_dict(name: str) -> Optional[List[Dict[str, Any]]]:
    """Get ABI as dictionary from the registry."""
    return get_abi_registry().get_abi_dict(name)


def get_abi_json(name: str, indent: int = 2) -> Optional[str]:
    """Get ABI as JSON string from the registry."""
    return get_abi_registry().get_abi_json(name, indent)


def register_abi(name: str, abi: ContractABI) -> None:
    """Register a new ABI in the registry."""
    get_abi_registry().register_abi(name, abi)


def list_abis() -> List[str]:
    """List all registered ABI names."""
    return get_abi_registry().list_abis()


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Print available ABIs
    print("Available ABIs:")
    for abi_name in list_abis():
        print(f"  - {abi_name}")

    # Get ERC20 ABI
    erc20_abi = get_abi("ERC20")
    if erc20_abi:
        print(f"\nERC20 ABI has {len(erc20_abi.functions)} functions and {len(erc20_abi.events)} events")

    # Get ABI as JSON
    erc20_json = get_abi_json("ERC20")
    if erc20_json:
        print("\nERC20 ABI JSON (first 200 chars):")
        print(erc20_json[:200] + "...")

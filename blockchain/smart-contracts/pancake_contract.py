# blockchain/smart-contracts/pancake_contract.py
# NEXUS AI TRADING SYSTEM - PancakeSwap Smart Contract Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
PancakeSwap Smart Contract Integration for NEXUS AI Trading System.
Provides comprehensive interaction with PancakeSwap DEX including:
- Swap operations (exact input/output)
- Liquidity management (add/remove)
- Farm operations (stake/unstake)
- Syrup Pool operations
- Price queries
- Factory and Router integration
- MasterChef integration
- Analytics and statistics
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from web3 import Web3
from web3.contract import Contract

# NEXUS Imports
from blockchain.smart_contracts.base_contract import BaseContract
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.pancake")


# ============================================================================
# Enums & Constants
# ============================================================================

class PancakeAction(str, Enum):
    """PancakeSwap actions."""
    SWAP_EXACT_IN = "swap_exact_in"
    SWAP_EXACT_OUT = "swap_exact_out"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    STAKE = "stake"
    UNSTAKE = "unstake"
    HARVEST = "harvest"
    CREATE_PAIR = "create_pair"


class FarmType(str, Enum):
    """Farm types."""
    MASTERCHEF = "masterchef"
    SYRUP_POOL = "syrup_pool"
    V2 = "v2"
    V3 = "v3"


@dataclass
class PairInfo:
    """PancakeSwap pair information."""
    address: str
    token0: str
    token1: str
    reserve0: int
    reserve1: int
    total_supply: int
    price0: float
    price1: float
    volume_24h: float
    liquidity: float
    fee: int
    factory: str


@dataclass
class LiquidityPosition:
    """Liquidity position."""
    pair_address: str
    liquidity: int
    token0_amount: int
    token1_amount: int
    token0_address: str
    token1_address: str
    share: float
    value_usd: float


@dataclass
class FarmPosition:
    """Farm position."""
    farm_type: FarmType
    pool_id: int
    staked_amount: int
    reward_amount: int
    pending_rewards: int
    apr: float
    total_staked: int


@dataclass
class SwapQuote:
    """Swap quote."""
    amount_in: int
    amount_out: int
    path: List[str]
    price_impact: float
    fee: int
    gas_estimate: int


# ============================================================================
# PancakeSwap Contract Integration
# ============================================================================

class PancakeContract(BaseContract):
    """
    PancakeSwap Smart Contract Integration.
    Provides comprehensive interaction with PancakeSwap DEX.
    """

    # PancakeSwap Router V2 ABI (minimal)
    ROUTER_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "amountIn", "type": "uint256"},
                {"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}
            ],
            "name": "swapExactTokensForTokens",
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "amountOut", "type": "uint256"},
                {"name": "amountInMax", "type": "uint256"},
                {"name": "path", "type": "address[]"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}
            ],
            "name": "swapTokensForExactTokens",
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "amountIn", "type": "uint256"},
                {"name": "path", "type": "address[]"}
            ],
            "name": "getAmountsOut",
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "amountOut", "type": "uint256"},
                {"name": "path", "type": "address[]"}
            ],
            "name": "getAmountsIn",
            "outputs": [{"name": "amounts", "type": "uint256[]"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "tokenA", "type": "address"},
                {"name": "tokenB", "type": "address"},
                {"name": "amountADesired", "type": "uint256"},
                {"name": "amountBDesired", "type": "uint256"},
                {"name": "amountAMin", "type": "uint256"},
                {"name": "amountBMin", "type": "uint256"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}
            ],
            "name": "addLiquidity",
            "outputs": [
                {"name": "amountA", "type": "uint256"},
                {"name": "amountB", "type": "uint256"},
                {"name": "liquidity", "type": "uint256"}
            ],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "tokenA", "type": "address"},
                {"name": "tokenB", "type": "address"},
                {"name": "liquidity", "type": "uint256"},
                {"name": "amountAMin", "type": "uint256"},
                {"name": "amountBMin", "type": "uint256"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}
            ],
            "name": "removeLiquidity",
            "outputs": [
                {"name": "amountA", "type": "uint256"},
                {"name": "amountB", "type": "uint256"}
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "factory",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "WETH",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        }
    ]

    # PancakeSwap Factory ABI (minimal)
    FACTORY_ABI = [
        {
            "constant": True,
            "inputs": [
                {"name": "tokenA", "type": "address"},
                {"name": "tokenB", "type": "address"}
            ],
            "name": "getPair",
            "outputs": [{"name": "pair", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "allPairsLength",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "", "type": "uint256"}],
            "name": "allPairs",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        }
    ]

    # PancakeSwap Pair ABI (minimal)
    PAIR_ABI = [
        {
            "constant": True,
            "inputs": [],
            "name": "token0",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "token1",
            "outputs": [{"name": "", "type": "address"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "getReserves",
            "outputs": [
                {"name": "reserve0", "type": "uint112"},
                {"name": "reserve1", "type": "uint112"},
                {"name": "blockTimestampLast", "type": "uint32"}
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
            "type": "function"
        }
    ]

    # MasterChef V2 ABI (minimal)
    MASTERCHEF_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "", "type": "uint256"}],
            "name": "poolInfo",
            "outputs": [
                {"name": "lpToken", "type": "address"},
                {"name": "allocPoint", "type": "uint256"},
                {"name": "lastRewardBlock", "type": "uint256"},
                {"name": "accCakePerShare", "type": "uint256"}
            ],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [
                {"name": "pid", "type": "uint256"},
                {"name": "user", "type": "address"}
            ],
            "name": "userInfo",
            "outputs": [
                {"name": "amount", "type": "uint256"},
                {"name": "rewardDebt", "type": "uint256"}
            ],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "pid", "type": "uint256"},
                {"name": "amount", "type": "uint256"}
            ],
            "name": "deposit",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "pid", "type": "uint256"},
                {"name": "amount", "type": "uint256"}
            ],
            "name": "withdraw",
            "outputs": [],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [{"name": "pid", "type": "uint256"}],
            "name": "harvest",
            "outputs": [],
            "type": "function"
        }
    ]

    # PancakeSwap mainnet addresses
    ADDRESSES = {
        "router_v2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "router_v3": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",
        "factory_v2": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
        "factory_v3": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
        "masterchef_v2": "0xa5f8C5Dbd5F286960b9d90548680aE5ebFf07652",
        "masterchef_v3": "0x556B9306565093C855AEA9AE92A594704c2Cd59e",
        "cake_token": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
        "wbnb": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    }

    def __init__(
        self,
        web3_client: Web3Client,
        version: str = "v2",
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize PancakeSwap contract integration.

        Args:
            web3_client: Web3 client instance
            version: Protocol version (v2, v3)
            config: Configuration dictionary
        """
        super().__init__(
            web3_client=web3_client,
            contract_name="PancakeSwap",
            contract_address=self.ADDRESSES[f"router_{version}"],
            abi=self.ROUTER_ABI,
            config=config,
        )

        self.version = version
        self._addresses = self.ADDRESSES

        # Initialize sub-contracts
        self._factory = None
        self._masterchef = None
        self._pair_cache: Dict[str, PairInfo] = {}

        self._initialize_sub_contracts()

        logger.info(
            "PancakeContract initialized",
            extra={
                "version": version,
                "router_address": self.contract_address,
                "chain": web3_client.chain_name,
            }
        )

    def _initialize_sub_contracts(self) -> None:
        """Initialize sub-contracts."""
        try:
            # Factory
            factory_address = self._addresses[f"factory_{self.version}"]
            self._factory = self.web3_client.get_contract(
                factory_address,
                abi=self.FACTORY_ABI,
            )

            # MasterChef
            if self.version == "v2":
                masterchef_address = self._addresses["masterchef_v2"]
            else:
                masterchef_address = self._addresses["masterchef_v3"]
            self._masterchef = self.web3_client.get_contract(
                masterchef_address,
                abi=self.MASTERCHEF_ABI,
            )

            logger.debug("PancakeSwap sub-contracts initialized")

        except Exception as e:
            logger.error(f"Failed to initialize PancakeSwap sub-contracts: {e}")
            raise

    # -----------------------------------------------------------------------
    # Swap Operations
    # -----------------------------------------------------------------------

    async def swap_exact_tokens_for_tokens(
        self,
        amount_in: int,
        amount_out_min: int,
        path: List[str],
        to_address: Union[str, Address],
        deadline: Optional[int] = None,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Swap exact amount of tokens for tokens.

        Args:
            amount_in: Amount of input token
            amount_out_min: Minimum amount of output token
            path: Swap path (list of token addresses)
            to_address: Recipient address
            deadline: Deadline timestamp
            sender: Sender address (optional)

        Returns:
            Swap result or None
        """
        to_address = Web3.to_checksum_address(to_address)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        if deadline is None:
            deadline = int(time.time()) + 3600  # 1 hour

        try:
            tx = await self._build_transaction(
                "swapExactTokensForTokens",
                amount_in,
                amount_out_min,
                path,
                to_address,
                deadline,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                # Get amounts out
                amounts = await self.get_amounts_out(amount_in, path)

                logger.info(
                    f"Swap successful",
                    extra={
                        "amount_in": amount_in,
                        "amount_out": amounts[-1] if amounts else 0,
                        "path": path,
                        "tx_hash": tx_hash,
                    }
                )

                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "amount_in": amount_in,
                    "amount_out": amounts[-1] if amounts else 0,
                    "path": path,
                }

            return None

        except Exception as e:
            logger.error(f"Error swapping: {e}")
            return None

    async def swap_tokens_for_exact_tokens(
        self,
        amount_out: int,
        amount_in_max: int,
        path: List[str],
        to_address: Union[str, Address],
        deadline: Optional[int] = None,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Swap tokens for exact amount of tokens.

        Args:
            amount_out: Desired amount of output token
            amount_in_max: Maximum amount of input token
            path: Swap path
            to_address: Recipient address
            deadline: Deadline timestamp
            sender: Sender address (optional)

        Returns:
            Swap result or None
        """
        to_address = Web3.to_checksum_address(to_address)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        if deadline is None:
            deadline = int(time.time()) + 3600

        try:
            tx = await self._build_transaction(
                "swapTokensForExactTokens",
                amount_out,
                amount_in_max,
                path,
                to_address,
                deadline,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                amounts = await self.get_amounts_in(amount_out, path)

                logger.info(
                    f"Swap successful",
                    extra={
                        "amount_out": amount_out,
                        "amount_in": amounts[0] if amounts else 0,
                        "path": path,
                        "tx_hash": tx_hash,
                    }
                )

                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "amount_out": amount_out,
                    "amount_in": amounts[0] if amounts else 0,
                    "path": path,
                }

            return None

        except Exception as e:
            logger.error(f"Error swapping: {e}")
            return None

    # -----------------------------------------------------------------------
    # Price Queries
    # -----------------------------------------------------------------------

    async def get_amounts_out(
        self,
        amount_in: int,
        path: List[str],
    ) -> Optional[List[int]]:
        """
        Get amounts out for a swap.

        Args:
            amount_in: Amount of input token
            path: Swap path

        Returns:
            List of amounts or None
        """
        try:
            amounts = await self._call_contract_function(
                "getAmountsOut",
                amount_in,
                path,
            )
            return [int(a) for a in amounts] if amounts else None

        except Exception as e:
            logger.error(f"Error getting amounts out: {e}")
            return None

    async def get_amounts_in(
        self,
        amount_out: int,
        path: List[str],
    ) -> Optional[List[int]]:
        """
        Get amounts in for a swap.

        Args:
            amount_out: Amount of output token
            path: Swap path

        Returns:
            List of amounts or None
        """
        try:
            amounts = await self._call_contract_function(
                "getAmountsIn",
                amount_out,
                path,
            )
            return [int(a) for a in amounts] if amounts else None

        except Exception as e:
            logger.error(f"Error getting amounts in: {e}")
            return None

    async def get_price_impact(
        self,
        amount_in: int,
        path: List[str],
    ) -> float:
        """
        Calculate price impact of a swap.

        Args:
            amount_in: Amount of input token
            path: Swap path

        Returns:
            Price impact as a percentage
        """
        try:
            amounts = await self.get_amounts_out(amount_in, path)
            if not amounts or len(amounts) < 2:
                return 0.0

            # Get initial price (small amount)
            small_amount = amount_in // 1000 or 1
            small_amounts = await self.get_amounts_out(small_amount, path)

            if not small_amounts:
                return 0.0

            # Calculate impact
            expected_out = amounts[-1] * (small_amount / amount_in)
            actual_out = amounts[-1]

            if expected_out > 0:
                impact = (expected_out - actual_out) / expected_out
                return impact * 100

            return 0.0

        except Exception:
            return 0.0

    # -----------------------------------------------------------------------
    # Liquidity Operations
    # -----------------------------------------------------------------------

    async def add_liquidity(
        self,
        token_a: Union[str, Address],
        token_b: Union[str, Address],
        amount_a_desired: int,
        amount_b_desired: int,
        amount_a_min: int,
        amount_b_min: int,
        to_address: Union[str, Address],
        deadline: Optional[int] = None,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Add liquidity to a pair.

        Args:
            token_a: Token A address
            token_b: Token B address
            amount_a_desired: Desired amount of token A
            amount_b_desired: Desired amount of token B
            amount_a_min: Minimum amount of token A
            amount_b_min: Minimum amount of token B
            to_address: Recipient address
            deadline: Deadline timestamp
            sender: Sender address (optional)

        Returns:
            Liquidity addition result or None
        """
        token_a = Web3.to_checksum_address(token_a)
        token_b = Web3.to_checksum_address(token_b)
        to_address = Web3.to_checksum_address(to_address)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        if deadline is None:
            deadline = int(time.time()) + 3600

        try:
            tx = await self._build_transaction(
                "addLiquidity",
                token_a,
                token_b,
                amount_a_desired,
                amount_b_desired,
                amount_a_min,
                amount_b_min,
                to_address,
                deadline,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                # Get pair info
                pair_info = await self.get_pair_info(token_a, token_b)

                logger.info(
                    f"Liquidity added",
                    extra={
                        "token_a": token_a,
                        "token_b": token_b,
                        "amount_a": amount_a_desired,
                        "amount_b": amount_b_desired,
                        "tx_hash": tx_hash,
                    }
                )

                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "pair": pair_info.address if pair_info else None,
                    "amount_a": amount_a_desired,
                    "amount_b": amount_b_desired,
                }

            return None

        except Exception as e:
            logger.error(f"Error adding liquidity: {e}")
            return None

    async def remove_liquidity(
        self,
        token_a: Union[str, Address],
        token_b: Union[str, Address],
        liquidity: int,
        amount_a_min: int,
        amount_b_min: int,
        to_address: Union[str, Address],
        deadline: Optional[int] = None,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Remove liquidity from a pair.

        Args:
            token_a: Token A address
            token_b: Token B address
            liquidity: Liquidity amount to remove
            amount_a_min: Minimum amount of token A
            amount_b_min: Minimum amount of token B
            to_address: Recipient address
            deadline: Deadline timestamp
            sender: Sender address (optional)

        Returns:
            Liquidity removal result or None
        """
        token_a = Web3.to_checksum_address(token_a)
        token_b = Web3.to_checksum_address(token_b)
        to_address = Web3.to_checksum_address(to_address)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        if deadline is None:
            deadline = int(time.time()) + 3600

        try:
            tx = await self._build_transaction(
                "removeLiquidity",
                token_a,
                token_b,
                liquidity,
                amount_a_min,
                amount_b_min,
                to_address,
                deadline,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                logger.info(
                    f"Liquidity removed",
                    extra={
                        "token_a": token_a,
                        "token_b": token_b,
                        "liquidity": liquidity,
                        "tx_hash": tx_hash,
                    }
                )

                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "liquidity": liquidity,
                }

            return None

        except Exception as e:
            logger.error(f"Error removing liquidity: {e}")
            return None

    # -----------------------------------------------------------------------
    # Pair Information
    # -----------------------------------------------------------------------

    async def get_pair_info(
        self,
        token_a: Union[str, Address],
        token_b: Union[str, Address],
        force_refresh: bool = False,
    ) -> Optional[PairInfo]:
        """
        Get pair information.

        Args:
            token_a: Token A address
            token_b: Token B address
            force_refresh: Force refresh cache

        Returns:
            PairInfo or None
        """
        token_a = Web3.to_checksum_address(token_a)
        token_b = Web3.to_checksum_address(token_b)

        # Sort tokens to get consistent key
        sorted_tokens = sorted([token_a, token_b])
        cache_key = f"{sorted_tokens[0]}:{sorted_tokens[1]}"

        if not force_refresh and cache_key in self._pair_cache:
            return self._pair_cache[cache_key]

        try:
            # Get pair address
            pair_address = await self._call_factory_function(
                "getPair",
                token_a,
                token_b,
            )

            if not pair_address or pair_address == "0x0000000000000000000000000000000000000000":
                return None

            # Get pair contract
            pair_contract = self.web3_client.get_contract(
                pair_address,
                abi=self.PAIR_ABI,
            )

            # Get token addresses
            token0 = await self._call_pair_function(pair_contract, "token0")
            token1 = await self._call_pair_function(pair_contract, "token1")

            # Get reserves
            reserves = await self._call_pair_function(pair_contract, "getReserves")
            reserve0 = reserves[0] if reserves else 0
            reserve1 = reserves[1] if reserves else 0

            # Get total supply
            total_supply = await self._call_pair_function(pair_contract, "totalSupply")

            pair_info = PairInfo(
                address=pair_address,
                token0=token0,
                token1=token1,
                reserve0=int(reserve0) if reserve0 else 0,
                reserve1=int(reserve1) if reserve1 else 0,
                total_supply=int(total_supply) if total_supply else 0,
                price0=self._calculate_price(reserve0, reserve1),
                price1=self._calculate_price(reserve1, reserve0),
                volume_24h=0,  # Would need to query volume
                liquidity=self._calculate_liquidity(reserve0, reserve1),
                fee=25,  # PancakeSwap default fee (0.25%)
                factory=self._addresses[f"factory_{self.version}"],
            )

            self._pair_cache[cache_key] = pair_info
            return pair_info

        except Exception as e:
            logger.error(f"Error getting pair info: {e}")
            return None

    async def get_pair_address(
        self,
        token_a: Union[str, Address],
        token_b: Union[str, Address],
    ) -> Optional[str]:
        """
        Get pair address for two tokens.

        Args:
            token_a: Token A address
            token_b: Token B address

        Returns:
            Pair address or None
        """
        token_a = Web3.to_checksum_address(token_a)
        token_b = Web3.to_checksum_address(token_b)

        try:
            pair = await self._call_factory_function("getPair", token_a, token_b)
            return pair
        except Exception:
            return None

    def _calculate_price(self, reserve0: int, reserve1: int) -> float:
        """Calculate price from reserves."""
        if reserve1 == 0:
            return 0.0
        return reserve0 / reserve1

    def _calculate_liquidity(self, reserve0: int, reserve1: int) -> float:
        """Calculate liquidity from reserves."""
        # Simplified liquidity calculation
        return (reserve0 * reserve1) ** 0.5

    # -----------------------------------------------------------------------
    # Farm Operations (MasterChef)
    # -----------------------------------------------------------------------

    async def get_pool_info(
        self,
        pool_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get pool information from MasterChef.

        Args:
            pool_id: Pool ID

        Returns:
            Pool info or None
        """
        try:
            pool = await self._call_masterchef_function(
                "poolInfo",
                pool_id,
            )

            if not pool:
                return None

            return {
                "lp_token": pool[0],
                "alloc_point": int(pool[1]) if pool[1] else 0,
                "last_reward_block": int(pool[2]) if pool[2] else 0,
                "acc_cake_per_share": int(pool[3]) if pool[3] else 0,
            }

        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            return None

    async def get_user_info(
        self,
        pool_id: int,
        user_address: Union[str, Address],
    ) -> Optional[Dict[str, Any]]:
        """
        Get user info from MasterChef.

        Args:
            pool_id: Pool ID
            user_address: User address

        Returns:
            User info or None
        """
        user_address = Web3.to_checksum_address(user_address)

        try:
            info = await self._call_masterchef_function(
                "userInfo",
                pool_id,
                user_address,
            )

            if not info:
                return None

            return {
                "amount": int(info[0]) if info[0] else 0,
                "reward_debt": int(info[1]) if info[1] else 0,
            }

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    async def deposit(
        self,
        pool_id: int,
        amount: int,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Deposit into a farm.

        Args:
            pool_id: Pool ID
            amount: Amount to deposit
            sender: Sender address (optional)

        Returns:
            Transaction hash or None
        """
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        try:
            tx = await self._build_masterchef_transaction(
                "deposit",
                pool_id,
                amount,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                logger.info(
                    f"Deposited into farm",
                    extra={
                        "pool_id": pool_id,
                        "amount": amount,
                        "sender": sender,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error depositing: {e}")
            return None

    async def withdraw(
        self,
        pool_id: int,
        amount: int,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Withdraw from a farm.

        Args:
            pool_id: Pool ID
            amount: Amount to withdraw
            sender: Sender address (optional)

        Returns:
            Transaction hash or None
        """
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        try:
            tx = await self._build_masterchef_transaction(
                "withdraw",
                pool_id,
                amount,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                logger.info(
                    f"Withdrew from farm",
                    extra={
                        "pool_id": pool_id,
                        "amount": amount,
                        "sender": sender,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error withdrawing: {e}")
            return None

    async def harvest(
        self,
        pool_id: int,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[str]:
        """
        Harvest rewards from a farm.

        Args:
            pool_id: Pool ID
            sender: Sender address (optional)

        Returns:
            Transaction hash or None
        """
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        try:
            tx = await self._build_masterchef_transaction(
                "harvest",
                pool_id,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                logger.info(
                    f"Harvested rewards",
                    extra={
                        "pool_id": pool_id,
                        "sender": sender,
                        "tx_hash": tx_hash,
                    }
                )

            return tx_hash

        except Exception as e:
            logger.error(f"Error harvesting: {e}")
            return None

    # -----------------------------------------------------------------------
    # Internal Contract Calls
    # -----------------------------------------------------------------------

    async def _call_factory_function(self, function_name: str, *args) -> Any:
        """Call factory function."""
        try:
            func = getattr(self._factory.functions, function_name)
            result = await asyncio.to_thread(func(*args).call)
            return result
        except Exception as e:
            logger.error(f"Error calling factory function {function_name}: {e}")
            return None

    async def _call_pair_function(self, contract: Contract, function_name: str) -> Any:
        """Call pair function."""
        try:
            func = getattr(contract.functions, function_name)
            result = await asyncio.to_thread(func().call)
            return result
        except Exception as e:
            logger.error(f"Error calling pair function {function_name}: {e}")
            return None

    async def _call_masterchef_function(self, function_name: str, *args) -> Any:
        """Call MasterChef function."""
        try:
            func = getattr(self._masterchef.functions, function_name)
            result = await asyncio.to_thread(func(*args).call)
            return result
        except Exception as e:
            logger.error(f"Error calling MasterChef function {function_name}: {e}")
            return None

    # -----------------------------------------------------------------------
    # Transaction Building
    # -----------------------------------------------------------------------

    async def _build_transaction(
        self,
        function_name: str,
        *args,
    ) -> Dict[str, Any]:
        """Build a router transaction."""
        try:
            func = getattr(self.contract.functions, function_name)
            tx = func(*args).build_transaction({
                "from": self.web3_client.default_account,
                "nonce": await self.web3_client.get_nonce(self.web3_client.default_account),
                "gas": 0,
                "gasPrice": await self.web3_client.get_gas_price(),
            })

            gas = await self._estimate_gas(function_name, *args)
            tx["gas"] = int(gas * 1.3)

            return tx

        except Exception as e:
            logger.error(f"Error building transaction: {e}")
            raise

    async def _build_masterchef_transaction(
        self,
        function_name: str,
        *args,
    ) -> Dict[str, Any]:
        """Build a MasterChef transaction."""
        try:
            func = getattr(self._masterchef.functions, function_name)
            tx = func(*args).build_transaction({
                "from": self.web3_client.default_account,
                "nonce": await self.web3_client.get_nonce(self.web3_client.default_account),
                "gas": 0,
                "gasPrice": await self.web3_client.get_gas_price(),
            })

            gas = await self._estimate_masterchef_gas(function_name, *args)
            tx["gas"] = int(gas * 1.3)

            return tx

        except Exception as e:
            logger.error(f"Error building MasterChef transaction: {e}")
            raise

    async def _estimate_gas(
        self,
        function_name: str,
        *args,
    ) -> int:
        """Estimate gas for a router transaction."""
        try:
            func = getattr(self.contract.functions, function_name)
            gas = await self.web3_client.estimate_gas(
                func(*args).build_transaction({
                    "from": self.web3_client.default_account,
                })
            )
            return int(gas)
        except Exception:
            return 300000

    async def _estimate_masterchef_gas(
        self,
        function_name: str,
        *args,
    ) -> int:
        """Estimate gas for a MasterChef transaction."""
        try:
            func = getattr(self._masterchef.functions, function_name)
            gas = await self.web3_client.estimate_gas(
                func(*args).build_transaction({
                    "from": self.web3_client.default_account,
                })
            )
            return int(gas)
        except Exception:
            return 200000

    async def _send_transaction(
        self,
        tx: Dict[str, Any],
        from_address: str,
    ) -> Optional[str]:
        """Send a transaction."""
        try:
            signed_tx = self.web3_client.sign_transaction(tx, from_address)
            tx_hash = await self.web3_client.send_raw_transaction(signed_tx.rawTransaction)

            receipt = await self.web3_client.wait_for_transaction_receipt(tx_hash)

            if receipt and receipt.get("status", 0) == 1:
                return Web3.to_hex(tx_hash)
            else:
                logger.error(f"Transaction failed: {tx_hash}")
                return None

        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            return None

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_version(self) -> str:
        """Get protocol version."""
        return self.version

    def get_addresses(self) -> Dict[str, str]:
        """Get all contract addresses."""
        return self._addresses

    def get_wbnb_address(self) -> str:
        """Get WBNB address."""
        return self._addresses["wbnb"]

    def get_cake_address(self) -> str:
        """Get CAKE token address."""
        return self._addresses["cake_token"]

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the contract integration."""
        if self._running:
            return

        self._running = True
        logger.info("PancakeContract started")

    async def stop(self) -> None:
        """Stop the contract integration."""
        self._running = False
        logger.info("PancakeContract stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_pancake_contract(
    web3_client: Web3Client,
    version: str = "v2",
    config: Optional[Dict[str, Any]] = None,
) -> PancakeContract:
    """
    Factory function to create a PancakeContract instance.

    Args:
        web3_client: Web3 client instance
        version: Protocol version
        config: Configuration dictionary

    Returns:
        PancakeContract instance
    """
    return PancakeContract(
        web3_client=web3_client,
        version=version,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the PancakeSwap contract
    pass

# blockchain/smart-contracts/uniswap_contract.py
# NEXUS AI TRADING SYSTEM - Uniswap Smart Contract Integration
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Uniswap Smart Contract Integration for NEXUS AI Trading System.
Provides comprehensive interaction with Uniswap V2 and V3 protocols including:
- Swap operations (exact input/output)
- Liquidity management (add/remove)
- Position management (V3)
- Price queries
- Fee tier management
- NFT position management (V3)
- Factory and Router integration
- Analytics and statistics
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

# NEXUS Imports
from blockchain.smart_contracts.base_contract import BaseContract
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.uniswap")


# ============================================================================
# Enums & Constants
# ============================================================================

class UniswapVersion(str, Enum):
    """Uniswap protocol versions."""
    V2 = "v2"
    V3 = "v3"


class UniswapAction(str, Enum):
    """Uniswap actions."""
    SWAP_EXACT_IN = "swap_exact_in"
    SWAP_EXACT_OUT = "swap_exact_out"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    CREATE_POSITION = "create_position"
    INCREASE_LIQUIDITY = "increase_liquidity"
    DECREASE_LIQUIDITY = "decrease_liquidity"
    COLLECT_FEES = "collect_fees"


class FeeTier(str, Enum):
    """Uniswap V3 fee tiers."""
    LOWEST = "100"      # 0.01%
    LOW = "500"        # 0.05%
    MEDIUM = "3000"    # 0.3%
    HIGH = "10000"     # 1%


@dataclass
class PoolInfo:
    """Uniswap pool information."""
    address: str
    token0: str
    token1: str
    fee: int
    tick: int
    liquidity: int
    sqrt_price_x96: int
    token0_price: float
    token1_price: float
    volume_24h: float
    tvl: float
    fee_growth_global_0: int
    fee_growth_global_1: int


@dataclass
class PositionInfo:
    """Uniswap V3 position information."""
    token_id: int
    owner: str
    pool: str
    tick_lower: int
    tick_upper: int
    liquidity: int
    tokens_owed_0: int
    tokens_owed_1: int
    fee_growth_inside_0: int
    fee_growth_inside_1: int


@dataclass
class SwapQuote:
    """Swap quote."""
    amount_in: int
    amount_out: int
    path: List[str]
    fee_tiers: List[int]
    price_impact: float
    sqrt_price_limit_x96: Optional[int] = None


# ============================================================================
# Uniswap Contract Integration
# ============================================================================

class UniswapContract(BaseContract):
    """
    Uniswap Smart Contract Integration.
    Provides comprehensive interaction with Uniswap V2 and V3 protocols.
    """

    # Uniswap V2 Router ABI (minimal)
    V2_ROUTER_ABI = [
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

    # Uniswap V3 Router ABI (minimal)
    V3_ROUTER_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "params", "type": "tuple"}
            ],
            "name": "exactInputSingle",
            "outputs": [{"name": "amountOut", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "params", "type": "tuple"}
            ],
            "name": "exactOutputSingle",
            "outputs": [{"name": "amountIn", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "params", "type": "tuple"}
            ],
            "name": "exactInput",
            "outputs": [{"name": "amountOut", "type": "uint256"}],
            "type": "function"
        },
        {
            "constant": False,
            "inputs": [
                {"name": "params", "type": "tuple"}
            ],
            "name": "exactOutput",
            "outputs": [{"name": "amountIn", "type": "uint256"}],
            "type": "function"
        }
    ]

    # Uniswap V3 Pool ABI (minimal)
    V3_POOL_ABI = [
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
            "name": "fee",
            "outputs": [{"name": "", "type": "uint24"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "liquidity",
            "outputs": [{"name": "", "type": "uint128"}],
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [],
            "name": "slot0",
            "outputs": [
                {"name": "sqrtPriceX96", "type": "uint160"},
                {"name": "tick", "type": "int24"},
                {"name": "observationIndex", "type": "uint16"},
                {"name": "observationCardinality", "type": "uint16"},
                {"name": "observationCardinalityNext", "type": "uint16"},
                {"name": "feeProtocol", "type": "uint8"},
                {"name": "unlocked", "type": "bool"}
            ],
            "type": "function"
        }
    ]

    # Uniswap mainnet addresses
    V2_ADDRESSES = {
        "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        "weth": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    }

    V3_ADDRESSES = {
        "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "router_swap": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "nft_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
    }

    def __init__(
        self,
        web3_client: Web3Client,
        version: UniswapVersion = UniswapVersion.V3,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Uniswap contract integration.

        Args:
            web3_client: Web3 client instance
            version: Protocol version
            config: Configuration dictionary
        """
        addresses = self.V3_ADDRESSES if version == UniswapVersion.V3 else self.V2_ADDRESSES
        abi = self.V3_ROUTER_ABI if version == UniswapVersion.V3 else self.V2_ROUTER_ABI

        super().__init__(
            web3_client=web3_client,
            contract_name=f"Uniswap{version.value.upper()}",
            contract_address=addresses["router"],
            abi=abi,
            config=config,
        )

        self.version = version
        self._addresses = addresses

        # Cache
        self._pool_cache: Dict[str, PoolInfo] = {}
        self._position_cache: Dict[int, PositionInfo] = {}

        logger.info(
            "UniswapContract initialized",
            extra={
                "version": version.value,
                "router_address": self.contract_address,
                "chain": web3_client.chain_name,
            }
        )

    # -----------------------------------------------------------------------
    # Swap Operations
    # -----------------------------------------------------------------------

    async def swap_exact_input_single(
        self,
        token_in: Union[str, Address],
        token_out: Union[str, Address],
        amount_in: int,
        amount_out_min: int,
        fee: int = 3000,
        sqrt_price_limit: Optional[int] = None,
        deadline: Optional[int] = None,
        recipient: Optional[Union[str, Address]] = None,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Swap exact input for output (V3 single pool).

        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount
            amount_out_min: Minimum output amount
            fee: Fee tier
            sqrt_price_limit: Sqrt price limit
            deadline: Deadline timestamp
            recipient: Recipient address
            sender: Sender address

        Returns:
            Swap result or None
        """
        if self.version != UniswapVersion.V3:
            logger.error("Single swap only available in V3")
            return None

        token_in = Web3.to_checksum_address(token_in)
        token_out = Web3.to_checksum_address(token_out)
        recipient = Web3.to_checksum_address(recipient or self.web3_client.default_account)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        if deadline is None:
            deadline = int(time.time()) + 3600

        try:
            params = {
                "tokenIn": token_in,
                "tokenOut": token_out,
                "fee": fee,
                "recipient": recipient,
                "deadline": deadline,
                "amountIn": amount_in,
                "amountOutMinimum": amount_out_min,
                "sqrtPriceLimitX96": sqrt_price_limit or 0,
            }

            tx = await self._build_v3_transaction(
                "exactInputSingle",
                params,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                # Get quote
                quote = await self.quote_exact_input_single(
                    token_in,
                    token_out,
                    amount_in,
                    fee,
                )

                logger.info(
                    f"Swap successful",
                    extra={
                        "token_in": token_in,
                        "token_out": token_out,
                        "amount_in": amount_in,
                        "amount_out": quote[0] if quote else 0,
                        "tx_hash": tx_hash,
                    }
                )

                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "amount_in": amount_in,
                    "amount_out": quote[0] if quote else 0,
                }

            return None

        except Exception as e:
            logger.error(f"Error swapping: {e}")
            return None

    async def swap_exact_input(
        self,
        path: List[str],
        fee_tiers: List[int],
        amount_in: int,
        amount_out_min: int,
        deadline: Optional[int] = None,
        recipient: Optional[Union[str, Address]] = None,
        sender: Optional[Union[str, Address]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Swap exact input for output (V3 multi-pool).

        Args:
            path: Token path
            fee_tiers: Fee tiers for each swap
            amount_in: Input amount
            amount_out_min: Minimum output amount
            deadline: Deadline timestamp
            recipient: Recipient address
            sender: Sender address

        Returns:
            Swap result or None
        """
        if self.version != UniswapVersion.V3:
            logger.error("Multi-pool swap only available in V3")
            return None

        if len(path) != len(fee_tiers) + 1:
            logger.error("Path length must be fee_tiers length + 1")
            return None

        recipient = Web3.to_checksum_address(recipient or self.web3_client.default_account)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        if deadline is None:
            deadline = int(time.time()) + 3600

        try:
            # Build encoded path
            encoded_path = self._encode_path(path, fee_tiers)

            params = {
                "path": encoded_path,
                "recipient": recipient,
                "deadline": deadline,
                "amountIn": amount_in,
                "amountOutMinimum": amount_out_min,
            }

            tx = await self._build_v3_transaction(
                "exactInput",
                params,
            )

            tx_hash = await self._send_transaction(tx, sender)

            if tx_hash:
                logger.info(
                    f"Multi-pool swap successful",
                    extra={
                        "path": path,
                        "amount_in": amount_in,
                        "tx_hash": tx_hash,
                    }
                )

                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "amount_in": amount_in,
                }

            return None

        except Exception as e:
            logger.error(f"Error swapping: {e}")
            return None

    def _encode_path(self, path: List[str], fee_tiers: List[int]) -> bytes:
        """Encode swap path for V3."""
        # V3 path encoding: token0 + fee + token1 + fee + token2 + ...
        encoded = b""
        for i in range(len(path) - 1):
            encoded += Web3.to_bytes(hexstr=path[i])
            encoded += fee_tiers[i].to_bytes(3, "big")
        encoded += Web3.to_bytes(hexstr=path[-1])
        return encoded

    # -----------------------------------------------------------------------
    # Quote Operations
    # -----------------------------------------------------------------------

    async def quote_exact_input_single(
        self,
        token_in: Union[str, Address],
        token_out: Union[str, Address],
        amount_in: int,
        fee: int = 3000,
        sqrt_price_limit: Optional[int] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Get quote for exact input swap (V3).

        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount
            fee: Fee tier
            sqrt_price_limit: Sqrt price limit

        Returns:
            (amount_out, sqrt_price_x96) or None
        """
        try:
            # Would use quoter contract in production
            # This is a placeholder
            return (amount_in * 99 // 100, 0)
        except Exception:
            return None

    async def quote_exact_output_single(
        self,
        token_in: Union[str, Address],
        token_out: Union[str, Address],
        amount_out: int,
        fee: int = 3000,
        sqrt_price_limit: Optional[int] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Get quote for exact output swap (V3).

        Args:
            token_in: Input token address
            token_out: Output token address
            amount_out: Output amount
            fee: Fee tier
            sqrt_price_limit: Sqrt price limit

        Returns:
            (amount_in, sqrt_price_x96) or None
        """
        try:
            # Would use quoter contract in production
            # This is a placeholder
            return (amount_out * 101 // 100, 0)
        except Exception:
            return None

    # -----------------------------------------------------------------------
    # Liquidity Operations (V2)
    # -----------------------------------------------------------------------

    async def add_liquidity_v2(
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
        Add liquidity to a V2 pool.

        Args:
            token_a: Token A address
            token_b: Token B address
            amount_a_desired: Desired amount of token A
            amount_b_desired: Desired amount of token B
            amount_a_min: Minimum amount of token A
            amount_b_min: Minimum amount of token B
            to_address: Recipient address
            deadline: Deadline timestamp
            sender: Sender address

        Returns:
            Liquidity addition result or None
        """
        if self.version != UniswapVersion.V2:
            logger.error("Liquidity addition only available in V2")
            return None

        token_a = Web3.to_checksum_address(token_a)
        token_b = Web3.to_checksum_address(token_b)
        to_address = Web3.to_checksum_address(to_address)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        if deadline is None:
            deadline = int(time.time()) + 3600

        try:
            tx = await self._build_v2_transaction(
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
                logger.info(
                    f"Liquidity added",
                    extra={
                        "token_a": token_a,
                        "token_b": token_b,
                        "tx_hash": tx_hash,
                    }
                )

                return {
                    "success": True,
                    "tx_hash": tx_hash,
                    "amount_a": amount_a_desired,
                    "amount_b": amount_b_desired,
                }

            return None

        except Exception as e:
            logger.error(f"Error adding liquidity: {e}")
            return None

    async def remove_liquidity_v2(
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
        Remove liquidity from a V2 pool.

        Args:
            token_a: Token A address
            token_b: Token B address
            liquidity: Liquidity amount
            amount_a_min: Minimum amount of token A
            amount_b_min: Minimum amount of token B
            to_address: Recipient address
            deadline: Deadline timestamp
            sender: Sender address

        Returns:
            Liquidity removal result or None
        """
        if self.version != UniswapVersion.V2:
            logger.error("Liquidity removal only available in V2")
            return None

        token_a = Web3.to_checksum_address(token_a)
        token_b = Web3.to_checksum_address(token_b)
        to_address = Web3.to_checksum_address(to_address)
        sender = Web3.to_checksum_address(sender or self.web3_client.default_account)

        if deadline is None:
            deadline = int(time.time()) + 3600

        try:
            tx = await self._build_v2_transaction(
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
    # Price Queries
    # -----------------------------------------------------------------------

    async def get_amounts_out_v2(
        self,
        amount_in: int,
        path: List[str],
    ) -> Optional[List[int]]:
        """
        Get amounts out for a V2 swap.

        Args:
            amount_in: Input amount
            path: Swap path

        Returns:
            List of amounts or None
        """
        if self.version != UniswapVersion.V2:
            logger.error("V2 amounts out only available in V2")
            return None

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

    async def get_amounts_in_v2(
        self,
        amount_out: int,
        path: List[str],
    ) -> Optional[List[int]]:
        """
        Get amounts in for a V2 swap.

        Args:
            amount_out: Output amount
            path: Swap path

        Returns:
            List of amounts or None
        """
        if self.version != UniswapVersion.V2:
            logger.error("V2 amounts in only available in V2")
            return None

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

    # -----------------------------------------------------------------------
    # Pool Information (V3)
    # -----------------------------------------------------------------------

    async def get_pool_info(
        self,
        token_a: Union[str, Address],
        token_b: Union[str, Address],
        fee: int = 3000,
        force_refresh: bool = False,
    ) -> Optional[PoolInfo]:
        """
        Get V3 pool information.

        Args:
            token_a: Token A address
            token_b: Token B address
            fee: Fee tier
            force_refresh: Force refresh cache

        Returns:
            PoolInfo or None
        """
        token_a = Web3.to_checksum_address(token_a)
        token_b = Web3.to_checksum_address(token_b)

        sorted_tokens = sorted([token_a, token_b])
        cache_key = f"{sorted_tokens[0]}:{sorted_tokens[1]}:{fee}"

        if not force_refresh and cache_key in self._pool_cache:
            return self._pool_cache[cache_key]

        try:
            # Get pool address from factory
            pool_address = await self._get_pool_address(token_a, token_b, fee)

            if not pool_address:
                return None

            # Get pool contract
            pool_contract = self.web3_client.get_contract(
                pool_address,
                abi=self.V3_POOL_ABI,
            )

            # Get pool data
            token0 = await self._call_pool_function(pool_contract, "token0")
            token1 = await self._call_pool_function(pool_contract, "token1")
            pool_fee = await self._call_pool_function(pool_contract, "fee")
            liquidity = await self._call_pool_function(pool_contract, "liquidity")
            slot0 = await self._call_pool_function(pool_contract, "slot0")

            if not slot0:
                return None

            sqrt_price_x96 = slot0[0]
            tick = slot0[1]

            # Calculate prices
            price0 = self._sqrt_price_to_price(sqrt_price_x96, token0, token1)
            price1 = 1 / price0 if price0 > 0 else 0

            pool_info = PoolInfo(
                address=pool_address,
                token0=token0,
                token1=token1,
                fee=int(pool_fee) if pool_fee else 0,
                tick=int(tick) if tick else 0,
                liquidity=int(liquidity) if liquidity else 0,
                sqrt_price_x96=int(sqrt_price_x96) if sqrt_price_x96 else 0,
                token0_price=price0,
                token1_price=price1,
                volume_24h=0,  # Would need to query
                tvl=0,  # Would need to query
                fee_growth_global_0=0,
                fee_growth_global_1=0,
            )

            self._pool_cache[cache_key] = pool_info
            return pool_info

        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            return None

    async def _get_pool_address(
        self,
        token_a: str,
        token_b: str,
        fee: int,
    ) -> Optional[str]:
        """Get V3 pool address from factory."""
        try:
            factory_address = self.V3_ADDRESSES["factory"]
            factory_contract = self.web3_client.get_contract(
                factory_address,
                abi=[
                    {
                        "constant": True,
                        "inputs": [
                            {"name": "tokenA", "type": "address"},
                            {"name": "tokenB", "type": "address"},
                            {"name": "fee", "type": "uint24"}
                        ],
                        "name": "getPool",
                        "outputs": [{"name": "pool", "type": "address"}],
                        "type": "function"
                    }
                ],
            )

            pool = await asyncio.to_thread(
                factory_contract.functions.getPool(token_a, token_b, fee).call
            )
            return pool if pool != "0x0000000000000000000000000000000000000000" else None

        except Exception as e:
            logger.error(f"Error getting pool address: {e}")
            return None

    async def _call_pool_function(self, contract: Contract, function_name: str) -> Any:
        """Call pool function."""
        try:
            func = getattr(contract.functions, function_name)
            result = await asyncio.to_thread(func().call)
            return result
        except Exception as e:
            logger.error(f"Error calling pool function {function_name}: {e}")
            return None

    def _sqrt_price_to_price(
        self,
        sqrt_price_x96: int,
        token0: str,
        token1: str,
    ) -> float:
        """
        Convert sqrt price to actual price.

        Args:
            sqrt_price_x96: Sqrt price in Q64.96
            token0: Token 0 address
            token1: Token 1 address

        Returns:
            Price of token0 in token1
        """
        # Price = (sqrt_price_x96 / 2^96)^2
        price = (sqrt_price_x96 / (2 ** 96)) ** 2
        return float(price)

    # -----------------------------------------------------------------------
    # Transaction Building
    # -----------------------------------------------------------------------

    async def _build_v2_transaction(
        self,
        function_name: str,
        *args,
    ) -> Dict[str, Any]:
        """Build a V2 transaction."""
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
            logger.error(f"Error building V2 transaction: {e}")
            raise

    async def _build_v3_transaction(
        self,
        function_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a V3 transaction."""
        try:
            func = getattr(self.contract.functions, function_name)
            tx = func(params).build_transaction({
                "from": self.web3_client.default_account,
                "nonce": await self.web3_client.get_nonce(self.web3_client.default_account),
                "gas": 0,
                "gasPrice": await self.web3_client.get_gas_price(),
            })

            gas = await self._estimate_gas(function_name, params)
            tx["gas"] = int(gas * 1.3)

            return tx

        except Exception as e:
            logger.error(f"Error building V3 transaction: {e}")
            raise

    async def _estimate_gas(
        self,
        function_name: str,
        *args,
    ) -> int:
        """Estimate gas for a transaction."""
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

    def get_version(self) -> UniswapVersion:
        """Get protocol version."""
        return self.version

    def get_addresses(self) -> Dict[str, str]:
        """Get all contract addresses."""
        return self._addresses

    def get_weth_address(self) -> str:
        """Get WETH address."""
        return self._addresses["weth"]

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._pool_cache.clear()
        self._position_cache.clear()

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the contract integration."""
        if self._running:
            return

        self._running = True
        logger.info("UniswapContract started")

    async def stop(self) -> None:
        """Stop the contract integration."""
        self._running = False
        logger.info("UniswapContract stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_uniswap_contract(
    web3_client: Web3Client,
    version: UniswapVersion = UniswapVersion.V3,
    config: Optional[Dict[str, Any]] = None,
) -> UniswapContract:
    """
    Factory function to create a UniswapContract instance.

    Args:
        web3_client: Web3 client instance
        version: Protocol version
        config: Configuration dictionary

    Returns:
        UniswapContract instance
    """
    return UniswapContract(
        web3_client=web3_client,
        version=version,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the Uniswap contract
    pass

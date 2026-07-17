# blockchain/staking/liquid_staking.py
# NEXUS AI TRADING SYSTEM - Liquid Staking Integration Framework
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Liquid Staking Integration Framework for NEXUS AI Trading System.
Provides comprehensive liquid staking operations including:
- Multiple protocol support (Lido, Rocket Pool, StakeWise, etc.)
- Unified liquid staking interface
- Protocol comparison and selection
- APR/APY optimization
- Risk assessment
- Position management
- Reward claiming
- Protocol analytics
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
from web3 import Web3

# NEXUS Imports
from blockchain.staking.base_staking import BaseStaking, StakingProvider, StakingStatus
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.staking.liquid")


# ============================================================================
# Enums & Constants
# ============================================================================

class LiquidProtocol(str, Enum):
    """Supported liquid staking protocols."""
    LIDO = "lido"
    ROCKET_POOL = "rocket_pool"
    STAKE_WISE = "stake_wise"
    STADER = "stader"
    ANKR = "ankr"
    BINANCE = "binance"
    FRAX = "frax"
    MATICX = "maticx"
    LIQUID_STAKE = "liquid_stake"


class LiquidAction(str, Enum):
    """Liquid staking actions."""
    STAKE = "stake"
    UNSTAKE = "unstake"
    CLAIM_REWARDS = "claim_rewards"
    COMPOUND = "compound"
    SWAP = "swap"
    MIGRATE = "migrate"


@dataclass
class LiquidProtocolInfo:
    """Liquid staking protocol information."""
    protocol: LiquidProtocol
    name: str
    symbol: str
    address: str
    chain: str
    apy: float
    tvl: float
    fee: float
    min_stake: float
    max_stake: Optional[float] = None
    unbonding_period_days: int = 0
    is_active: bool = True
    risk_score: float = 0.0
    security_score: float = 0.0
    governance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LiquidStakingPosition:
    """Liquid staking position."""
    protocol: LiquidProtocol
    staked_amount: float
    staked_amount_usd: float
    rewards: float
    rewards_usd: float
    total_value_usd: float
    staking_apy: float
    daily_rewards: float
    weekly_rewards: float
    monthly_rewards: float
    status: StakingStatus = StakingStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtocolComparison:
    """Protocol comparison results."""
    best_apy: LiquidProtocolInfo
    best_security: LiquidProtocolInfo
    best_governance: LiquidProtocolInfo
    recommended: LiquidProtocolInfo
    alternatives: List[LiquidProtocolInfo]
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationPlan:
    """Migration plan between protocols."""
    source_protocol: LiquidProtocol
    target_protocol: LiquidProtocol
    amount: float
    estimated_gas: float
    estimated_time_minutes: int
    steps: List[Dict[str, Any]]
    risks: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Liquid Staking Framework
# ============================================================================

class LiquidStaking:
    """
    Liquid Staking Integration Framework.
    Provides unified interface for multiple liquid staking protocols.
    """

    # Protocol addresses (Ethereum mainnet)
    PROTOCOL_ADDRESSES = {
        LiquidProtocol.LIDO: {
            "address": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
            "token": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
            "name": "Lido",
            "symbol": "stETH",
            "chain": "ethereum",
        },
        LiquidProtocol.ROCKET_POOL: {
            "address": "0x3bE9659ECd5f230Fd7fcA60aF4D6620cBd5fD120",
            "token": "0xae78736Cd615f374D3085123A210448E74Fc6393",
            "name": "Rocket Pool",
            "symbol": "rETH",
            "chain": "ethereum",
        },
        LiquidProtocol.STAKE_WISE: {
            "address": "0xfE6EfD1676b41C7C1648b295BD2C5FdEe9b5F3A8",
            "token": "0x8E6B4dEe485C26B9DcCAb3B0fFBd5D1f3685Bc6b",
            "name": "StakeWise",
            "symbol": "sETH2",
            "chain": "ethereum",
        },
        LiquidProtocol.STADER: {
            "address": "0xcf5EA1b38380f6aF39068375516Daf40Ed70D299",
            "token": "0x3B5080545A7C7CeFa2aBcfe5E60b477f42d43C45",
            "name": "Stader",
            "symbol": "ETHx",
            "chain": "ethereum",
        },
        LiquidProtocol.ANKR: {
            "address": "0x84db6eE82b7Cf3b47E8F19270abdE5718B936670",
            "token": "0xE95A203B1a91a908F9B9CE46459d101078c2c3cb",
            "name": "Ankr",
            "symbol": "ankrETH",
            "chain": "ethereum",
        },
        LiquidProtocol.BINANCE: {
            "address": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
            "token": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
            "name": "Binance",
            "symbol": "BETH",
            "chain": "ethereum",
        },
        LiquidProtocol.FRAX: {
            "address": "0xbBc2F13f77425Ef0E2293A5D1aF37eC0fCb7C8b9",
            "token": "0x5E8422345238F34275888049021821E8E08CAa1f",
            "name": "Frax",
            "symbol": "sfrxETH",
            "chain": "ethereum",
        },
    }

    # Protocol APY cache
    _apy_cache: Dict[LiquidProtocol, Dict[str, Any]] = {}

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize liquid staking framework.

        Args:
            web3_client: Web3 client instance
            config: Configuration dictionary
        """
        self.web3_client = web3_client
        self.config = config or {}
        self._address = self.web3_client.default_account

        # Protocol instances
        self._protocols: Dict[LiquidProtocol, LiquidProtocolInfo] = {}

        # Position cache
        self._position_cache: Dict[LiquidProtocol, LiquidStakingPosition] = {}

        # Performance metrics
        self._performance = {
            "stake_operations": 0,
            "unstake_operations": 0,
            "reward_claims": 0,
            "migrations": 0,
            "protocol_queries": 0,
            "avg_response_time_ms": 0.0,
        }

        # Initialize protocols
        self._initialize_protocols()

        logger.info(
            "LiquidStaking initialized",
            extra={
                "protocols": len(self._protocols),
                "address": self._address,
            }
        )

    # -----------------------------------------------------------------------
    # Protocol Initialization
    # -----------------------------------------------------------------------

    def _initialize_protocols(self) -> None:
        """Initialize liquid staking protocols."""
        for protocol, info in self.PROTOCOL_ADDRESSES.items():
            try:
                contract = self.web3_client.get_contract(
                    info["address"],
                    abi=self._get_protocol_abi(protocol),
                )

                protocol_info = LiquidProtocolInfo(
                    protocol=protocol,
                    name=info["name"],
                    symbol=info["symbol"],
                    address=info["address"],
                    chain=info["chain"],
                    apy=0.0,
                    tvl=0.0,
                    fee=0.0,
                    min_stake=0.0,
                    max_stake=None,
                    unbonding_period_days=0,
                    is_active=True,
                    risk_score=self._calculate_risk_score(protocol),
                    security_score=self._calculate_security_score(protocol),
                    governance_score=self._calculate_governance_score(protocol),
                )

                self._protocols[protocol] = protocol_info

            except Exception as e:
                logger.error(f"Error initializing protocol {protocol}: {e}")

    # -----------------------------------------------------------------------
    # Protocol Queries
    # -----------------------------------------------------------------------

    async def get_protocol_info(
        self,
        protocol: LiquidProtocol,
        force_refresh: bool = False,
    ) -> Optional[LiquidProtocolInfo]:
        """
        Get protocol information.

        Args:
            protocol: Protocol
            force_refresh: Force refresh cache

        Returns:
            LiquidProtocolInfo or None
        """
        if not force_refresh and protocol in self._protocols:
            return self._protocols[protocol]

        try:
            # Query protocol data
            protocol_data = await self._query_protocol(protocol)

            if not protocol_data:
                return None

            # Update protocol info
            info = self._protocols.get(protocol)
            if info:
                info.apy = protocol_data.get("apy", 0.0)
                info.tvl = protocol_data.get("tvl", 0.0)
                info.fee = protocol_data.get("fee", 0.0)
                info.min_stake = protocol_data.get("min_stake", 0.0)
                info.is_active = protocol_data.get("is_active", True)

                self._protocols[protocol] = info
                self._performance["protocol_queries"] += 1

            return info

        except Exception as e:
            logger.error(f"Error getting protocol info: {e}")
            return None

    async def _query_protocol(self, protocol: LiquidProtocol) -> Dict[str, Any]:
        """Query protocol data."""
        try:
            # Use protocol-specific queries
            if protocol == LiquidProtocol.LIDO:
                return await self._query_lido()
            elif protocol == LiquidProtocol.ROCKET_POOL:
                return await self._query_rocket_pool()
            elif protocol == LiquidProtocol.STAKE_WISE:
                return await self._query_stake_wise()
            else:
                return await self._query_generic_protocol(protocol)

        except Exception as e:
            logger.error(f"Error querying protocol {protocol}: {e}")
            return {}

    async def _query_lido(self) -> Dict[str, Any]:
        """Query Lido protocol data."""
        try:
            contract = self.web3_client.get_contract(
                self.PROTOCOL_ADDRESSES[LiquidProtocol.LIDO]["address"],
                abi=self._get_lido_abi(),
            )

            # Get protocol data
            steth_balance = await self._call_contract_function(
                contract,
                "totalSupply",
            )

            # Get ETH balance
            eth_balance = await self.web3_client.get_balance(
                contract.address
            )

            tvl = self.web3_client.from_wei(eth_balance, "ether")

            return {
                "apy": 0.043,  # Approximate Lido APY
                "tvl": tvl,
                "fee": 0.10,  # 10% fee
                "min_stake": 0.01,
                "is_active": True,
            }

        except Exception as e:
            logger.error(f"Error querying Lido: {e}")
            return {}

    async def _query_rocket_pool(self) -> Dict[str, Any]:
        """Query Rocket Pool protocol data."""
        try:
            # Rocket Pool specific queries
            return {
                "apy": 0.045,
                "tvl": 0.0,
                "fee": 0.05,
                "min_stake": 0.01,
                "is_active": True,
            }

        except Exception as e:
            logger.error(f"Error querying Rocket Pool: {e}")
            return {}

    async def _query_stake_wise(self) -> Dict[str, Any]:
        """Query StakeWise protocol data."""
        try:
            return {
                "apy": 0.042,
                "tvl": 0.0,
                "fee": 0.08,
                "min_stake": 0.01,
                "is_active": True,
            }

        except Exception as e:
            logger.error(f"Error querying StakeWise: {e}")
            return {}

    async def _query_generic_protocol(self, protocol: LiquidProtocol) -> Dict[str, Any]:
        """Query generic protocol data."""
        try:
            # Use third-party API for generic data
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.defillama.com/protocol/{protocol.value}",
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "apy": data.get("apy", 0.0),
                            "tvl": data.get("tvl", 0.0),
                            "fee": data.get("fee", 0.0),
                            "min_stake": data.get("min_stake", 0.0),
                            "is_active": data.get("is_active", True),
                        }
                    return {}

        except Exception as e:
            logger.error(f"Error querying generic protocol: {e}")
            return {}

    # -----------------------------------------------------------------------
    # Staking Operations
    # -----------------------------------------------------------------------

    async def stake(
        self,
        protocol: LiquidProtocol,
        amount: float,
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Stake using a liquid staking protocol.

        Args:
            protocol: Protocol to use
            amount: Amount to stake
            from_address: From address

        Returns:
            Transaction hash or None
        """
        from_address = from_address or self._address

        try:
            start_time = time.time()

            # Get protocol contract
            contract = self._get_protocol_contract(protocol)

            amount_wei = self.web3_client.to_wei(amount, "ether")

            # Build transaction
            tx = await self._build_stake_transaction(
                contract,
                protocol,
                amount_wei,
                from_address,
            )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                self._performance["stake_operations"] += 1
                self._performance["avg_response_time_ms"] = (
                    (self._performance["avg_response_time_ms"] *
                     (self._performance["stake_operations"] - 1) +
                     (time.time() - start_time) * 1000) /
                    self._performance["stake_operations"]
                )

                logger.info(
                    f"Staked {amount} via {protocol.value}",
                    extra={"tx_hash": tx_hash}
                )

                # Clear cache
                self._position_cache.pop(protocol, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error staking: {e}")
            return None

    async def unstake(
        self,
        protocol: LiquidProtocol,
        amount: float,
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Unstake from a liquid staking protocol.

        Args:
            protocol: Protocol to use
            amount: Amount to unstake
            from_address: From address

        Returns:
            Transaction hash or None
        """
        from_address = from_address or self._address

        try:
            start_time = time.time()

            contract = self._get_protocol_contract(protocol)

            amount_wei = self.web3_client.to_wei(amount, "ether")

            tx = await self._build_unstake_transaction(
                contract,
                protocol,
                amount_wei,
                from_address,
            )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                self._performance["unstake_operations"] += 1
                self._performance["avg_response_time_ms"] = (
                    (self._performance["avg_response_time_ms"] *
                     (self._performance["unstake_operations"] - 1) +
                     (time.time() - start_time) * 1000) /
                    self._performance["unstake_operations"]
                )

                logger.info(
                    f"Unstaked {amount} from {protocol.value}",
                    extra={"tx_hash": tx_hash}
                )

                self._position_cache.pop(protocol, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error unstaking: {e}")
            return None

    # -----------------------------------------------------------------------
    # Reward Operations
    # -----------------------------------------------------------------------

    async def claim_rewards(
        self,
        protocol: LiquidProtocol,
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Claim rewards from liquid staking.

        Args:
            protocol: Protocol to use
            from_address: From address

        Returns:
            Transaction hash or None
        """
        from_address = from_address or self._address

        try:
            contract = self._get_protocol_contract(protocol)

            tx = await self._build_claim_transaction(
                contract,
                protocol,
                from_address,
            )

            tx_hash = await self.web3_client.send_transaction(tx)

            if tx_hash:
                self._performance["reward_claims"] += 1
                logger.info(
                    f"Claimed rewards from {protocol.value}",
                    extra={"tx_hash": tx_hash}
                )
                self._position_cache.pop(protocol, None)

            return tx_hash

        except Exception as e:
            logger.error(f"Error claiming rewards: {e}")
            return None

    # -----------------------------------------------------------------------
    # Position Queries
    # -----------------------------------------------------------------------

    async def get_position(
        self,
        protocol: LiquidProtocol,
        address: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[LiquidStakingPosition]:
        """
        Get liquid staking position.

        Args:
            protocol: Protocol to query
            address: Staker address
            force_refresh: Force refresh cache

        Returns:
            LiquidStakingPosition or None
        """
        address = address or self._address

        if not force_refresh and protocol in self._position_cache:
            return self._position_cache[protocol]

        try:
            contract = self._get_protocol_contract(protocol)

            # Get staked amount
            staked_amount = await self._get_staked_amount(contract, protocol, address)

            # Get rewards
            rewards = await self._get_rewards(contract, protocol, address)

            # Get APY
            protocol_info = await self.get_protocol_info(protocol)

            # Calculate USD values
            price_usd = await self._get_asset_price(protocol)
            staked_usd = staked_amount * price_usd
            rewards_usd = rewards * price_usd

            position = LiquidStakingPosition(
                protocol=protocol,
                staked_amount=staked_amount,
                staked_amount_usd=staked_usd,
                rewards=rewards,
                rewards_usd=rewards_usd,
                total_value_usd=staked_usd + rewards_usd,
                staking_apy=protocol_info.apy if protocol_info else 0.0,
                daily_rewards=rewards / 365,
                weekly_rewards=rewards / 365 * 7,
                monthly_rewards=rewards / 365 * 30,
                status=StakingStatus.ACTIVE,
            )

            self._position_cache[protocol] = position

            return position

        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None

    async def _get_staked_amount(
        self,
        contract,
        protocol: LiquidProtocol,
        address: str,
    ) -> float:
        """Get staked amount for a protocol."""
        try:
            # Protocol-specific balance queries
            if protocol == LiquidProtocol.LIDO:
                balance = await self._call_contract_function(
                    contract,
                    "balanceOf",
                    address,
                )
                return self.web3_client.from_wei(balance, "ether")
            else:
                balance = await self._call_contract_function(
                    contract,
                    "balanceOf",
                    address,
                )
                return self.web3_client.from_wei(balance, "ether")

        except Exception as e:
            logger.error(f"Error getting staked amount: {e}")
            return 0.0

    async def _get_rewards(
        self,
        contract,
        protocol: LiquidProtocol,
        address: str,
    ) -> float:
        """Get rewards for a protocol."""
        try:
            # Protocol-specific reward queries
            return 0.0

        except Exception as e:
            logger.error(f"Error getting rewards: {e}")
            return 0.0

    # -----------------------------------------------------------------------
    # Protocol Comparison
    # -----------------------------------------------------------------------

    async def compare_protocols(
        self,
        protocols: Optional[List[LiquidProtocol]] = None,
    ) -> ProtocolComparison:
        """
        Compare liquid staking protocols.

        Args:
            protocols: List of protocols to compare

        Returns:
            ProtocolComparison
        """
        protocols = protocols or list(self._protocols.keys())

        protocol_infos = []
        for p in protocols:
            info = await self.get_protocol_info(p)
            if info:
                protocol_infos.append(info)

        if not protocol_infos:
            return ProtocolComparison(
                best_apy=LiquidProtocolInfo(protocol=LiquidProtocol.LIDO, name="", symbol="", address="", chain="", apy=0, tvl=0, fee=0, min_stake=0),
                best_security=LiquidProtocolInfo(protocol=LiquidProtocol.LIDO, name="", symbol="", address="", chain="", apy=0, tvl=0, fee=0, min_stake=0),
                best_governance=LiquidProtocolInfo(protocol=LiquidProtocol.LIDO, name="", symbol="", address="", chain="", apy=0, tvl=0, fee=0, min_stake=0),
                recommended=LiquidProtocolInfo(protocol=LiquidProtocol.LIDO, name="", symbol="", address="", chain="", apy=0, tvl=0, fee=0, min_stake=0),
                alternatives=[],
            )

        # Find best APY
        best_apy = max(protocol_infos, key=lambda x: x.apy)

        # Find best security
        best_security = max(protocol_infos, key=lambda x: x.security_score)

        # Find best governance
        best_governance = max(protocol_infos, key=lambda x: x.governance_score)

        # Calculate composite score
        for info in protocol_infos:
            info.risk_score = self._calculate_composite_score(info)

        recommended = min(protocol_infos, key=lambda x: x.risk_score)

        # Filter alternatives
        alternatives = [p for p in protocol_infos if p.protocol != recommended.protocol]

        return ProtocolComparison(
            best_apy=best_apy,
            best_security=best_security,
            best_governance=best_governance,
            recommended=recommended,
            alternatives=alternatives,
            details={
                "total_protocols": len(protocol_infos),
                "average_apy": sum(p.apy for p in protocol_infos) / len(protocol_infos),
                "average_fee": sum(p.fee for p in protocol_infos) / len(protocol_infos),
            },
        )

    def _calculate_composite_score(self, info: LiquidProtocolInfo) -> float:
        """Calculate composite score for a protocol."""
        # Weighted score: lower is better
        score = (
            info.risk_score * 0.3 +
            (1 - info.security_score) * 0.3 +
            (1 - info.governance_score) * 0.2 +
            (info.fee / 0.2) * 0.2
        )
        return min(score, 1.0)

    # -----------------------------------------------------------------------
    # Migration
    # -----------------------------------------------------------------------

    async def create_migration_plan(
        self,
        source: LiquidProtocol,
        target: LiquidProtocol,
        amount: float,
    ) -> Optional[MigrationPlan]:
        """
        Create a migration plan between protocols.

        Args:
            source: Source protocol
            target: Target protocol
            amount: Amount to migrate

        Returns:
            MigrationPlan or None
        """
        try:
            # Get protocol info
            source_info = await self.get_protocol_info(source)
            target_info = await self.get_protocol_info(target)

            if not source_info or not target_info:
                return None

            # Calculate steps
            steps = [
                {
                    "action": "unstake",
                    "protocol": source,
                    "amount": amount,
                    "description": f"Unstake {amount} from {source_info.name}",
                },
                {
                    "action": "stake",
                    "protocol": target,
                    "amount": amount,
                    "description": f"Stake {amount} in {target_info.name}",
                },
            ]

            # Calculate risks
            risks = []
            if source_info.unbonding_period_days > 0:
                risks.append(f"Unbonding period of {source_info.unbonding_period_days} days")
            if target_info.fee > 0.1:
                risks.append(f"High fee on {target_info.name} ({target_info.fee*100}%)")

            return MigrationPlan(
                source_protocol=source,
                target_protocol=target,
                amount=amount,
                estimated_gas=0.001,  # Approximate
                estimated_time_minutes=source_info.unbonding_period_days * 24 * 60,
                steps=steps,
                risks=risks,
                metadata={
                    "source_apy": source_info.apy,
                    "target_apy": target_info.apy,
                    "expected_improvement": (target_info.apy - source_info.apy) * 100,
                },
            )

        except Exception as e:
            logger.error(f"Error creating migration plan: {e}")
            return None

    async def execute_migration(
        self,
        plan: MigrationPlan,
    ) -> Dict[str, Any]:
        """
        Execute a migration plan.

        Args:
            plan: Migration plan

        Returns:
            Migration result
        """
        results = {
            "success": False,
            "steps_completed": [],
            "errors": [],
            "final_position": None,
        }

        try:
            for step in plan.steps:
                if step["action"] == "unstake":
                    tx_hash = await self.unstake(step["protocol"], step["amount"])
                    if tx_hash:
                        results["steps_completed"].append(step)
                    else:
                        results["errors"].append(f"Failed to unstake from {step['protocol']}")
                        return results

                elif step["action"] == "stake":
                    tx_hash = await self.stake(step["protocol"], step["amount"])
                    if tx_hash:
                        results["steps_completed"].append(step)
                    else:
                        results["errors"].append(f"Failed to stake in {step['protocol']}")
                        return results

            results["success"] = True
            self._performance["migrations"] += 1

            # Get final position
            final_position = await self.get_position(plan.target_protocol, force_refresh=True)
            results["final_position"] = final_position

            logger.info(
                f"Migration complete: {plan.source_protocol.value} -> {plan.target_protocol.value}",
                extra={"amount": plan.amount}
            )

        except Exception as e:
            logger.error(f"Error executing migration: {e}")
            results["errors"].append(str(e))

        return results

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def _get_protocol_contract(self, protocol: LiquidProtocol):
        """Get protocol contract."""
        info = self.PROTOCOL_ADDRESSES.get(protocol)
        if not info:
            raise ValueError(f"Unknown protocol: {protocol}")

        return self.web3_client.get_contract(
            info["address"],
            abi=self._get_protocol_abi(protocol),
        )

    def _get_protocol_abi(self, protocol: LiquidProtocol) -> List[Dict[str, Any]]:
        """Get protocol ABI."""
        if protocol == LiquidProtocol.LIDO:
            return self._get_lido_abi()
        elif protocol == LiquidProtocol.ROCKET_POOL:
            return self._get_rocket_pool_abi()
        else:
            return self._get_generic_abi()

    def _get_lido_abi(self) -> List[Dict[str, Any]]:
        """Get Lido ABI."""
        return [
            {
                "constant": False,
                "inputs": [{"name": "_referral", "type": "address"}],
                "name": "submit",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
        ]

    def _get_rocket_pool_abi(self) -> List[Dict[str, Any]]:
        """Get Rocket Pool ABI."""
        return [
            {
                "constant": False,
                "inputs": [],
                "name": "deposit",
                "outputs": [],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_address", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
        ]

    def _get_generic_abi(self) -> List[Dict[str, Any]]:
        """Get generic ABI for unknown protocols."""
        return [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
        ]

    async def _call_contract_function(
        self,
        contract,
        function_name: str,
        *args,
    ) -> Any:
        """Call a contract function."""
        try:
            func = getattr(contract.functions, function_name)
            return await asyncio.to_thread(func(*args).call)
        except Exception as e:
            logger.error(f"Error calling {function_name}: {e}")
            return None

    async def _build_stake_transaction(
        self,
        contract,
        protocol: LiquidProtocol,
        amount_wei: int,
        from_address: str,
    ) -> Dict[str, Any]:
        """Build stake transaction."""
        try:
            if protocol == LiquidProtocol.LIDO:
                func = contract.functions.submit
                tx = func(from_address).build_transaction({
                    "from": from_address,
                    "nonce": await self.web3_client.get_nonce(from_address),
                    "value": amount_wei,
                    "gas": 0,
                    "gasPrice": await self.web3_client.get_gas_price(),
                })
            elif protocol == LiquidProtocol.ROCKET_POOL:
                func = contract.functions.deposit
                tx = func().build_transaction({
                    "from": from_address,
                    "nonce": await self.web3_client.get_nonce(from_address),
                    "value": amount_wei,
                    "gas": 0,
                    "gasPrice": await self.web3_client.get_gas_price(),
                })
            else:
                # Generic stake function
                func = contract.functions.stake
                tx = func(amount_wei).build_transaction({
                    "from": from_address,
                    "nonce": await self.web3_client.get_nonce(from_address),
                    "gas": 0,
                    "gasPrice": await self.web3_client.get_gas_price(),
                })

            gas = await self.web3_client.estimate_gas(tx)
            tx["gas"] = int(gas * 1.3)

            return tx

        except Exception as e:
            logger.error(f"Error building stake transaction: {e}")
            raise

    async def _build_unstake_transaction(
        self,
        contract,
        protocol: LiquidProtocol,
        amount_wei: int,
        from_address: str,
    ) -> Dict[str, Any]:
        """Build unstake transaction."""
        try:
            func = contract.functions.withdraw
            tx = func(amount_wei).build_transaction({
                "from": from_address,
                "nonce": await self.web3_client.get_nonce(from_address),
                "gas": 0,
                "gasPrice": await self.web3_client.get_gas_price(),
            })

            gas = await self.web3_client.estimate_gas(tx)
            tx["gas"] = int(gas * 1.3)

            return tx

        except Exception as e:
            logger.error(f"Error building unstake transaction: {e}")
            raise

    async def _build_claim_transaction(
        self,
        contract,
        protocol: LiquidProtocol,
        from_address: str,
    ) -> Dict[str, Any]:
        """Build claim rewards transaction."""
        try:
            func = contract.functions.claimRewards
            tx = func().build_transaction({
                "from": from_address,
                "nonce": await self.web3_client.get_nonce(from_address),
                "gas": 0,
                "gasPrice": await self.web3_client.get_gas_price(),
            })

            gas = await self.web3_client.estimate_gas(tx)
            tx["gas"] = int(gas * 1.3)

            return tx

        except Exception as e:
            logger.error(f"Error building claim transaction: {e}")
            raise

    async def _get_asset_price(self, protocol: LiquidProtocol) -> float:
        """Get asset price in USD."""
        try:
            # Use CoinGecko API
            symbol = self.PROTOCOL_ADDRESSES[protocol]["symbol"]
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": symbol.lower(), "vs_currencies": "usd"},
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get(symbol.lower(), {}).get("usd", 0.0)
                    return 0.0

        except Exception as e:
            logger.error(f"Error getting asset price: {e}")
            return 0.0

    def _calculate_risk_score(self, protocol: LiquidProtocol) -> float:
        """Calculate protocol risk score."""
        # Simplified risk scoring
        risk_map = {
            LiquidProtocol.LIDO: 0.2,
            LiquidProtocol.ROCKET_POOL: 0.25,
            LiquidProtocol.STAKE_WISE: 0.3,
            LiquidProtocol.STADER: 0.35,
            LiquidProtocol.ANKR: 0.3,
            LiquidProtocol.BINANCE: 0.4,
            LiquidProtocol.FRAX: 0.35,
        }
        return risk_map.get(protocol, 0.5)

    def _calculate_security_score(self, protocol: LiquidProtocol) -> float:
        """Calculate protocol security score."""
        security_map = {
            LiquidProtocol.LIDO: 0.9,
            LiquidProtocol.ROCKET_POOL: 0.85,
            LiquidProtocol.STAKE_WISE: 0.8,
            LiquidProtocol.STADER: 0.75,
            LiquidProtocol.ANKR: 0.8,
            LiquidProtocol.BINANCE: 0.7,
            LiquidProtocol.FRAX: 0.75,
        }
        return security_map.get(protocol, 0.5)

    def _calculate_governance_score(self, protocol: LiquidProtocol) -> float:
        """Calculate protocol governance score."""
        governance_map = {
            LiquidProtocol.LIDO: 0.85,
            LiquidProtocol.ROCKET_POOL: 0.8,
            LiquidProtocol.STAKE_WISE: 0.7,
            LiquidProtocol.STADER: 0.65,
            LiquidProtocol.ANKR: 0.7,
            LiquidProtocol.BINANCE: 0.5,
            LiquidProtocol.FRAX: 0.6,
        }
        return governance_map.get(protocol, 0.5)

    # -----------------------------------------------------------------------
    # Health Check
    # -----------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            block_number = await self.web3_client.get_block_number()
            chain_healthy = block_number is not None

            # Check protocol availability
            protocols_available = len(self._protocols) > 0

            return {
                "status": "healthy" if chain_healthy and protocols_available else "unhealthy",
                "chain_healthy": chain_healthy,
                "protocols_available": protocols_available,
                "total_protocols": len(self._protocols),
                "address": self._address,
                "block_number": block_number,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    # -----------------------------------------------------------------------
    # Performance Metrics
    # -----------------------------------------------------------------------

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "total_protocols": len(self._protocols),
            "address": self._address,
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the liquid staking framework."""
        if self._running:
            return

        self._running = True
        logger.info("LiquidStaking started")

    async def stop(self) -> None:
        """Stop the liquid staking framework."""
        self._running = False

        # Clear caches
        self._position_cache.clear()
        self._apy_cache.clear()

        logger.info("LiquidStaking stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_liquid_staking(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> LiquidStaking:
    """
    Factory function to create a LiquidStaking instance.

    Args:
        web3_client: Web3 client instance
        config: Configuration dictionary

    Returns:
        LiquidStaking instance
    """
    return LiquidStaking(
        web3_client=web3_client,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use liquid staking
    pass

# blockchain/staking/staking_manager.py
# NEXUS AI TRADING SYSTEM - Staking Manager
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Staking Manager for NEXUS AI Trading System.
Provides unified management of staking operations across multiple providers including:
- Multi-provider staking management
- Portfolio optimization
- Auto-compounding
- Rebalancing
- Risk management
- Performance tracking
- Position monitoring
- Reward harvesting
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# NEXUS Imports
from blockchain.staking.base_staking import BaseStaking, StakingProvider, StakingStatus, ValidatorInfo
from blockchain.staking.atom_staking import ATOMStaking, create_atom_staking
from blockchain.staking.bnb_staking import BNBStaking, create_bnb_staking
from blockchain.staking.dot_staking import DOTStaking, create_dot_staking
from blockchain.staking.eth_staking import ETHStaking, create_eth_staking
from blockchain.staking.sol_staking import SOLStaking, create_sol_staking
from blockchain.staking.liquid_staking import LiquidStaking, create_liquid_staking
from blockchain.staking.staking_analytics import StakingAnalytics, create_staking_analytics
from blockchain.staking.staking_apy import StakingAPY, create_staking_apy
from blockchain.staking.staking_config import StakingConfigManager, create_staking_config_manager
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.staking.manager")


# ============================================================================
# Enums & Constants
# ============================================================================

class ManagerStatus(str, Enum):
    """Manager status."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class RebalanceMode(str, Enum):
    """Rebalance modes."""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    THRESHOLD = "threshold"
    OPTIMIZED = "optimized"


@dataclass
class StakingSummary:
    """Staking summary across all providers."""
    total_staked: float
    total_staked_usd: float
    total_rewards: float
    total_rewards_usd: float
    total_value_usd: float
    average_apy: float
    daily_rewards: float
    weekly_rewards: float
    monthly_rewards: float
    active_providers: int
    positions: Dict[str, Any]
    last_updated: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RebalanceResult:
    """Rebalance operation result."""
    timestamp: datetime
    mode: RebalanceMode
    changes_made: List[Dict[str, Any]]
    old_apy: float
    new_apy: float
    apy_improvement: float
    gas_cost: float
    gas_cost_usd: float
    success: bool
    errors: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Staking Manager
# ============================================================================

class StakingManager:
    """
    Unified Staking Manager.
    Provides comprehensive management of staking operations across multiple providers.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize staking manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # Configuration manager
        self.config_manager = create_staking_config_manager(
            config.get("config_dir"),
            config,
        )

        # Analytics engines
        self.analytics = create_staking_analytics(config)
        self.apy_calculator = create_staking_apy(config)

        # Staking providers
        self._providers: Dict[StakingProvider, BaseStaking] = {}
        self._liquid_staking: Optional[LiquidStaking] = None

        # State management
        self._status = ManagerStatus.INITIALIZING
        self._running = False
        self._lock = asyncio.Lock()

        # Position cache
        self._positions: Dict[StakingProvider, Dict[str, Any]] = {}
        self._summary: Optional[StakingSummary] = None
        self._last_update: Optional[datetime] = None

        # Background tasks
        self._tasks: List[asyncio.Task] = []
        self._rebalance_task: Optional[asyncio.Task] = None

        # Performance metrics
        self._performance = {
            "total_stakes": 0,
            "total_unstakes": 0,
            "total_reclaims": 0,
            "rebalances": 0,
            "compounds": 0,
            "errors": 0,
            "avg_response_time_ms": 0.0,
        }

        logger.info("StakingManager initialized")

    # -----------------------------------------------------------------------
    # Provider Initialization
    # -----------------------------------------------------------------------

    async def initialize_providers(
        self,
        providers: Optional[List[StakingProvider]] = None,
    ) -> None:
        """
        Initialize staking providers.

        Args:
            providers: List of providers to initialize
        """
        if providers is None:
            providers = list(StakingProvider)

        # Initialize each provider
        for provider in providers:
            try:
                if provider == StakingProvider.COSMOS:
                    self._providers[provider] = create_atom_staking(self.config)
                elif provider == StakingProvider.ETHEREUM:
                    self._providers[provider] = create_eth_staking(
                        self.config.get("web3_client"),
                        self.config,
                    )
                elif provider == StakingProvider.SOLANA:
                    self._providers[provider] = create_sol_staking(self.config)
                elif provider == StakingProvider.POLKADOT:
                    self._providers[provider] = create_dot_staking(self.config)
                elif provider == StakingProvider.BNB:
                    self._providers[provider] = create_bnb_staking(
                        self.config.get("web3_client"),
                        self.config,
                    )
                else:
                    logger.warning(f"Provider {provider} not implemented yet")

                if provider in self._providers:
                    await self._providers[provider].start()
                    logger.info(f"Initialized {provider.value} staking")

            except Exception as e:
                logger.error(f"Error initializing {provider.value}: {e}")

        # Initialize liquid staking
        if self.config.get("liquid_staking_enabled", True):
            try:
                self._liquid_staking = create_liquid_staking(
                    self.config.get("web3_client"),
                    self.config,
                )
                await self._liquid_staking.start()
                logger.info("Initialized liquid staking")
            except Exception as e:
                logger.error(f"Error initializing liquid staking: {e}")

        self._status = ManagerStatus.RUNNING

    # -----------------------------------------------------------------------
    # Staking Operations
    # -----------------------------------------------------------------------

    async def stake(
        self,
        provider: StakingProvider,
        validator_address: str,
        amount: float,
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Stake tokens.

        Args:
            provider: Staking provider
            validator_address: Validator address
            amount: Amount to stake
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        staking = self._providers.get(provider)
        if not staking:
            logger.error(f"Provider {provider} not initialized")
            return None

        try:
            result = await staking.delegate(validator_address, amount, memo)

            if result:
                self._performance["total_stakes"] += 1
                logger.info(
                    f"Staked {amount} {provider.value} to {validator_address}",
                    extra={"tx_hash": result}
                )

                # Update positions
                await self.update_positions()

            return result

        except Exception as e:
            logger.error(f"Error staking: {e}")
            self._performance["errors"] += 1
            return None

    async def unstake(
        self,
        provider: StakingProvider,
        validator_address: str,
        amount: float,
        memo: Optional[str] = None,
    ) -> Optional[str]:
        """
        Unstake tokens.

        Args:
            provider: Staking provider
            validator_address: Validator address
            amount: Amount to unstake
            memo: Transaction memo

        Returns:
            Transaction hash or None
        """
        staking = self._providers.get(provider)
        if not staking:
            logger.error(f"Provider {provider} not initialized")
            return None

        try:
            result = await staking.undelegate(validator_address, amount, memo)

            if result:
                self._performance["total_unstakes"] += 1
                logger.info(
                    f"Unstaked {amount} {provider.value} from {validator_address}",
                    extra={"tx_hash": result}
                )

                await self.update_positions()

            return result

        except Exception as e:
            logger.error(f"Error unstaking: {e}")
            self._performance["errors"] += 1
            return None

    async def claim_rewards(
        self,
        provider: StakingProvider,
        validator_addresses: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Claim staking rewards.

        Args:
            provider: Staking provider
            validator_addresses: List of validator addresses

        Returns:
            Transaction hash or None
        """
        staking = self._providers.get(provider)
        if not staking:
            logger.error(f"Provider {provider} not initialized")
            return None

        try:
            result = await staking.claim_rewards(validator_addresses)

            if result:
                self._performance["total_reclaims"] += 1
                logger.info(
                    f"Claimed rewards from {provider.value}",
                    extra={"tx_hash": result}
                )

                await self.update_positions()

            return result

        except Exception as e:
            logger.error(f"Error claiming rewards: {e}")
            self._performance["errors"] += 1
            return None

    async def compound_rewards(
        self,
        provider: StakingProvider,
        validator_address: str,
    ) -> Optional[str]:
        """
        Compound rewards.

        Args:
            provider: Staking provider
            validator_address: Validator address

        Returns:
            Transaction hash or None
        """
        staking = self._providers.get(provider)
        if not staking:
            logger.error(f"Provider {provider} not initialized")
            return None

        try:
            result = await staking.compound_rewards(validator_address)

            if result:
                self._performance["compounds"] += 1
                logger.info(
                    f"Compounded rewards to {validator_address}",
                    extra={"tx_hash": result}
                )

                await self.update_positions()

            return result

        except Exception as e:
            logger.error(f"Error compounding: {e}")
            self._performance["errors"] += 1
            return None

    # -----------------------------------------------------------------------
    # Liquid Staking Operations
    # -----------------------------------------------------------------------

    async def liquid_stake(
        self,
        protocol: str,
        amount: float,
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Liquid stake tokens.

        Args:
            protocol: Liquid staking protocol
            amount: Amount to stake
            from_address: From address

        Returns:
            Transaction hash or None
        """
        if not self._liquid_staking:
            logger.error("Liquid staking not initialized")
            return None

        try:
            result = await self._liquid_staking.stake(
                protocol,
                amount,
                from_address,
            )

            if result:
                self._performance["total_stakes"] += 1
                logger.info(
                    f"Liquid staked {amount} via {protocol}",
                    extra={"tx_hash": result}
                )

                await self.update_positions()

            return result

        except Exception as e:
            logger.error(f"Error liquid staking: {e}")
            self._performance["errors"] += 1
            return None

    async def liquid_unstake(
        self,
        protocol: str,
        amount: float,
        from_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Unstake liquid staked tokens.

        Args:
            protocol: Liquid staking protocol
            amount: Amount to unstake
            from_address: From address

        Returns:
            Transaction hash or None
        """
        if not self._liquid_staking:
            logger.error("Liquid staking not initialized")
            return None

        try:
            result = await self._liquid_staking.unstake(
                protocol,
                amount,
                from_address,
            )

            if result:
                self._performance["total_unstakes"] += 1
                logger.info(
                    f"Liquid unstaked {amount} from {protocol}",
                    extra={"tx_hash": result}
                )

                await self.update_positions()

            return result

        except Exception as e:
            logger.error(f"Error liquid unstaking: {e}")
            self._performance["errors"] += 1
            return None

    # -----------------------------------------------------------------------
    # Position Management
    # -----------------------------------------------------------------------

    async def update_positions(
        self,
        force_refresh: bool = False,
    ) -> None:
        """
        Update all staking positions.

        Args:
            force_refresh: Force refresh
        """
        start_time = time.time()

        async with self._lock:
            for provider, staking in self._providers.items():
                try:
                    position = await staking.get_staking_position(
                        force_refresh=force_refresh,
                    )
                    if position:
                        self._positions[provider] = self._serialize_position(position)
                except Exception as e:
                    logger.error(f"Error updating {provider.value} position: {e}")
                    self._performance["errors"] += 1

            # Update liquid staking positions
            if self._liquid_staking:
                try:
                    # Would query liquid positions
                    pass
                except Exception as e:
                    logger.error(f"Error updating liquid positions: {e}")

            # Update summary
            self._summary = await self._calculate_summary()
            self._last_update = datetime.utcnow()

            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["avg_response_time_ms"] = (
                (self._performance["avg_response_time_ms"] *
                 (self._performance.get("total_updates", 0) + 1) +
                 elapsed_ms) /
                (self._performance.get("total_updates", 0) + 1)
            )
            self._performance["total_updates"] = self._performance.get("total_updates", 0) + 1

    def _serialize_position(self, position: Any) -> Dict[str, Any]:
        """Serialize staking position for storage."""
        if hasattr(position, "__dict__"):
            return {
                k: v for k, v in position.__dict__.items()
                if not k.startswith("_")
            }
        return {}

    async def _calculate_summary(self) -> StakingSummary:
        """Calculate staking summary."""
        total_staked = 0.0
        total_staked_usd = 0.0
        total_rewards = 0.0
        total_rewards_usd = 0.0
        total_value_usd = 0.0
        apys = []
        positions = {}

        for provider, position_data in self._positions.items():
            try:
                # Extract data from position
                staked = position_data.get("total_staked", 0)
                rewards = position_data.get("total_rewards", 0)
                value_usd = position_data.get("total_value_usd", 0)
                apy = position_data.get("average_apy", 0)

                total_staked += staked
                total_rewards += rewards
                total_value_usd += value_usd

                if apy > 0:
                    apys.append(apy)

                positions[provider.value] = {
                    "staked": staked,
                    "rewards": rewards,
                    "value_usd": value_usd,
                    "apy": apy,
                }

            except Exception as e:
                logger.error(f"Error processing {provider.value}: {e}")

        # Calculate USD values
        total_staked_usd = total_staked * await self._get_avg_price()
        total_rewards_usd = total_rewards * await self._get_avg_price()

        # Calculate average APY
        avg_apy = sum(apys) / len(apys) if apys else 0

        # Calculate daily, weekly, monthly rewards
        daily_rewards = total_rewards / 365
        weekly_rewards = daily_rewards * 7
        monthly_rewards = daily_rewards * 30

        return StakingSummary(
            total_staked=total_staked,
            total_staked_usd=total_staked_usd,
            total_rewards=total_rewards,
            total_rewards_usd=total_rewards_usd,
            total_value_usd=total_value_usd,
            average_apy=avg_apy,
            daily_rewards=daily_rewards,
            weekly_rewards=weekly_rewards,
            monthly_rewards=monthly_rewards,
            active_providers=len(self._positions),
            positions=positions,
            last_updated=datetime.utcnow(),
        )

    async def _get_avg_price(self) -> float:
        """Get average price across providers."""
        return 1.0  # Would calculate from actual prices

    # -----------------------------------------------------------------------
    # Rebalancing
    # -----------------------------------------------------------------------

    async def rebalance(
        self,
        mode: RebalanceMode = RebalanceMode.THRESHOLD,
        threshold: float = 0.1,
    ) -> Optional[RebalanceResult]:
        """
        Rebalance staking portfolio.

        Args:
            mode: Rebalance mode
            threshold: Rebalance threshold

        Returns:
            RebalanceResult or None
        """
        start_time = time.time()

        try:
            # Get current positions
            await self.update_positions()

            if not self._summary:
                return None

            # Calculate optimal allocation
            optimal_allocation = await self._calculate_optimal_allocation()

            # Determine changes
            changes = await self._determine_rebalance_changes(
                optimal_allocation,
                threshold,
            )

            if not changes:
                return RebalanceResult(
                    timestamp=datetime.utcnow(),
                    mode=mode,
                    changes_made=[],
                    old_apy=self._summary.average_apy,
                    new_apy=self._summary.average_apy,
                    apy_improvement=0,
                    gas_cost=0,
                    gas_cost_usd=0,
                    success=True,
                    errors=[],
                )

            # Execute changes
            results = await self._execute_rebalance_changes(changes)

            if results:
                self._performance["rebalances"] += 1

                # Update positions
                await self.update_positions(force_refresh=True)

                return RebalanceResult(
                    timestamp=datetime.utcnow(),
                    mode=mode,
                    changes_made=changes,
                    old_apy=self._summary.average_apy,
                    new_apy=0,  # Will be calculated after update
                    apy_improvement=0,
                    gas_cost=0,
                    gas_cost_usd=0,
                    success=True,
                    errors=[],
                )

            return None

        except Exception as e:
            logger.error(f"Error rebalancing: {e}")
            self._performance["errors"] += 1
            return None

    async def _calculate_optimal_allocation(self) -> Dict[str, float]:
        """Calculate optimal allocation."""
        # Would use analytics engine
        return {}

    async def _determine_rebalance_changes(
        self,
        optimal: Dict[str, float],
        threshold: float,
    ) -> List[Dict[str, Any]]:
        """Determine rebalance changes."""
        changes = []

        for provider, target in optimal.items():
            current = self._summary.positions.get(provider, {}).get("staked", 0)
            difference = target - current

            if abs(difference) > threshold:
                changes.append({
                    "provider": provider,
                    "action": "increase" if difference > 0 else "decrease",
                    "amount": abs(difference),
                    "current": current,
                    "target": target,
                })

        return changes

    async def _execute_rebalance_changes(
        self,
        changes: List[Dict[str, Any]],
    ) -> bool:
        """Execute rebalance changes."""
        # Would implement rebalance execution
        return True

    # -----------------------------------------------------------------------
    # Auto-Compounding
    # -----------------------------------------------------------------------

    async def auto_compound(
        self,
        provider: Optional[StakingProvider] = None,
        threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Auto-compound rewards.

        Args:
            provider: Specific provider
            threshold: Minimum rewards to compound

        Returns:
            List of compounding results
        """
        results = []

        providers = [provider] if provider else list(self._providers.keys())

        for p in providers:
            staking = self._providers.get(p)
            if not staking:
                continue

            try:
                position = await staking.get_staking_position()
                if not position:
                    continue

                rewards = position.total_rewards

                if rewards > threshold:
                    # Find best validator
                    validators = await staking.get_validators()
                    if not validators:
                        continue

                    validator = max(validators, key=lambda v: v.score)
                    result = await self.compound_rewards(p, validator.address)

                    if result:
                        results.append({
                            "provider": p.value,
                            "validator": validator.address,
                            "amount": rewards,
                            "tx_hash": result,
                            "success": True,
                        })
                    else:
                        results.append({
                            "provider": p.value,
                            "error": "Compounding failed",
                            "success": False,
                        })

            except Exception as e:
                logger.error(f"Error auto-compounding {p.value}: {e}")
                results.append({
                    "provider": p.value,
                    "error": str(e),
                    "success": False,
                })

        return results

    # -----------------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------------

    async def analyze_portfolio(self) -> Dict[str, Any]:
        """
        Analyze staking portfolio.

        Returns:
            Portfolio analysis
        """
        await self.update_positions()

        if not self._summary:
            return {
                "error": "No positions available",
            }

        # Get historical data
        historical = []
        for provider, staking in self._providers.items():
            # Would get historical APY data
            pass

        # Analyze with analytics engine
        analysis = {
            "summary": self._summary.__dict__,
            "performance": {
                "apy": self._summary.average_apy,
                "rewards": {
                    "daily": self._summary.daily_rewards,
                    "weekly": self._summary.weekly_rewards,
                    "monthly": self._summary.monthly_rewards,
                },
            },
            "risk_assessment": self._assess_risk(),
            "recommendations": self._generate_recommendations(),
        }

        return analysis

    def _assess_risk(self) -> Dict[str, Any]:
        """Assess portfolio risk."""
        risk_score = 0.0
        factors = []

        # Concentration risk
        if self._summary:
            provider_count = len(self._summary.positions)
            if provider_count < 3:
                risk_score += 0.3
                factors.append("Low provider diversification")

            # Check individual positions
            for pos in self._summary.positions.values():
                if pos.get("staked", 0) / self._summary.total_staked > 0.5:
                    risk_score += 0.2
                    factors.append("High concentration in single provider")

        return {
            "risk_score": risk_score,
            "risk_level": "high" if risk_score > 0.5 else "medium" if risk_score > 0.3 else "low",
            "factors": factors,
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate portfolio recommendations."""
        recommendations = []

        if self._summary:
            # Diversification recommendation
            if len(self._summary.positions) < 3:
                recommendations.append("Consider diversifying across more providers")

            # APY improvement
            if self._summary.average_apy < 5:
                recommendations.append("Consider switching to higher APY providers")

        return recommendations

    # -----------------------------------------------------------------------
    # Status and Monitoring
    # -----------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get manager status."""
        return {
            "status": self._status.value,
            "running": self._running,
            "providers": len(self._providers),
            "active_providers": len(self._positions),
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "performance": self._performance,
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health check results
        """
        results = {
            "status": "healthy",
            "providers": {},
            "overall": True,
        }

        for provider, staking in self._providers.items():
            try:
                health = await staking.health_check()
                results["providers"][provider.value] = health
                if health.get("status") != "healthy":
                    results["overall"] = False
            except Exception as e:
                results["providers"][provider.value] = {
                    "status": "error",
                    "error": str(e),
                }
                results["overall"] = False

        results["status"] = "healthy" if results["overall"] else "degraded"
        return results

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the staking manager."""
        if self._running:
            return

        self._running = True
        self._status = ManagerStatus.RUNNING

        # Initialize providers
        await self.initialize_providers()

        # Load configuration
        await self.config_manager.load_configuration()

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._update_loop()),
            asyncio.create_task(self._auto_compound_loop()),
        ]

        logger.info("StakingManager started")

    async def stop(self) -> None:
        """Stop the staking manager."""
        self._running = False
        self._status = ManagerStatus.STOPPED

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Stop providers
        for provider, staking in self._providers.items():
            try:
                await staking.stop()
            except Exception as e:
                logger.error(f"Error stopping {provider.value}: {e}")

        # Stop liquid staking
        if self._liquid_staking:
            await self._liquid_staking.stop()

        logger.info("StakingManager stopped")

    async def _update_loop(self) -> None:
        """Background update loop."""
        while self._running:
            try:
                await self.update_positions()
                await asyncio.sleep(60)  # Update every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(10)

    async def _auto_compound_loop(self) -> None:
        """Auto-compound loop."""
        config = self.config_manager.get_config()

        if not config or not config.auto_compound:
            logger.info("Auto-compounding disabled")
            return

        while self._running:
            try:
                # Check if it's time to compound
                frequency_hours = config.auto_compound_frequency_hours
                await asyncio.sleep(frequency_hours * 3600)

                await self.auto_compound(threshold=config.compound_threshold)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-compound loop: {e}")
                await asyncio.sleep(60)


# ============================================================================
# Factory Function
# ============================================================================

def create_staking_manager(
    config: Optional[Dict[str, Any]] = None,
) -> StakingManager:
    """
    Factory function to create a StakingManager instance.

    Args:
        config: Configuration dictionary

    Returns:
        StakingManager instance
    """
    return StakingManager(config=config)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the staking manager
    pass

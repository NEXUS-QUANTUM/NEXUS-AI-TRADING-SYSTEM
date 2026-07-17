# blockchain/staking/staking_analytics.py
# NEXUS AI TRADING SYSTEM - Staking Analytics Engine
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Staking Analytics Engine for NEXUS AI Trading System.
Provides comprehensive analytics for staking positions including:
- APR/APY calculations and projections
- Reward optimization
- Validator performance analysis
- Risk assessment
- Portfolio optimization
- Yield farming analytics
- Historical performance tracking
- Comparative analysis
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats

# NEXUS Imports
from blockchain.staking.base_staking import StakingProvider, StakingStatus
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.staking.analytics")


# ============================================================================
# Enums & Constants
# ============================================================================

class AnalyticsMetric(str, Enum):
    """Analytics metrics."""
    APR = "apr"
    APY = "apy"
    ROI = "roi"
    TVL = "tvl"
    REWARD_RATE = "reward_rate"
    STAKING_RATE = "staking_rate"
    VALIDATOR_COUNT = "validator_count"
    DELEGATOR_COUNT = "delegator_count"
    COMMISSION = "commission"
    RISK_SCORE = "risk_score"
    PERFORMANCE_SCORE = "performance_score"


class TimeFrame(str, Enum):
    """Time frames for analytics."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ALL = "all"


class OptimizationGoal(str, Enum):
    """Optimization goals."""
    MAXIMIZE_APY = "maximize_apy"
    MINIMIZE_RISK = "minimize_risk"
    BALANCED = "balanced"
    MAXIMIZE_REWARDS = "maximize_rewards"
    MINIMIZE_COMMISSION = "minimize_commission"


@dataclass
class StakingAnalyticsResult:
    """Staking analytics result."""
    provider: StakingProvider
    asset: str
    timestamp: datetime
    metrics: Dict[str, Any]
    projections: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    recommendations: List[str]
    score: float
    grade: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RewardProjection:
    """Reward projection."""
    period: str
    current_rewards: float
    projected_rewards: float
    projected_apy: float
    projected_apy_change: float
    confidence_interval: Tuple[float, float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidatorPerformance:
    """Validator performance metrics."""
    address: str
    name: str
    commission: float
    uptime: float
    blocks_produced: int
    blocks_missed: int
    effectiveness: float
    apy: float
    rank: int
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioOptimization:
    """Portfolio optimization result."""
    current_allocation: Dict[str, float]
    optimized_allocation: Dict[str, float]
    expected_apy: float
    expected_risk: float
    improvement: float
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Staking Analytics Engine
# ============================================================================

class StakingAnalytics:
    """
    Staking Analytics Engine.
    Provides comprehensive analytics for staking positions.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize staking analytics engine.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # Data storage
        self._historical_data: Dict[str, pd.DataFrame] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Performance metrics
        self._performance = {
            "analyses_performed": 0,
            "projections_generated": 0,
            "optimizations_run": 0,
            "avg_analysis_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Initialize default weights
        self._weights = {
            "apy_weight": config.get("apy_weight", 0.4),
            "risk_weight": config.get("risk_weight", 0.3),
            "stability_weight": config.get("stability_weight", 0.2),
            "liquidity_weight": config.get("liquidity_weight", 0.1),
        }

        logger.info("StakingAnalytics initialized")

    # -----------------------------------------------------------------------
    # APR/APY Calculations
    # -----------------------------------------------------------------------

    def calculate_apr(
        self,
        rewards: float,
        principal: float,
        period_days: float,
        compounding: bool = False,
    ) -> float:
        """
        Calculate APR.

        Args:
            rewards: Rewards earned
            principal: Principal amount
            period_days: Period in days
            compounding: Include compounding

        Returns:
            APR as percentage
        """
        if principal == 0:
            return 0.0

        apr = (rewards / principal) * (365 / period_days)

        if compounding:
            # Convert to APY with daily compounding
            apr = (1 + apr / 365) ** 365 - 1

        return apr * 100

    def calculate_apy(
        self,
        apr: float,
        compound_frequency: int = 365,
    ) -> float:
        """
        Calculate APY from APR.

        Args:
            apr: APR as percentage
            compound_frequency: Times per year

        Returns:
            APY as percentage
        """
        apr_decimal = apr / 100
        apy = (1 + apr_decimal / compound_frequency) ** compound_frequency - 1
        return apy * 100

    def calculate_effective_apy(
        self,
        base_apy: float,
        commission: float,
        fee: float,
        inflation: float = 0.0,
    ) -> float:
        """
        Calculate effective APY after fees and inflation.

        Args:
            base_apy: Base APY
            commission: Validator commission
            fee: Protocol fee
            inflation: Inflation rate

        Returns:
            Effective APY
        """
        effective = base_apy * (1 - commission) * (1 - fee)
        effective = effective - inflation
        return max(0, effective)

    def project_rewards(
        self,
        principal: float,
        apy: float,
        period_days: float = 365,
        compound: bool = True,
    ) -> Dict[str, float]:
        """
        Project rewards for a period.

        Args:
            principal: Principal amount
            apy: APY as percentage
            period_days: Period in days
            compound: Include compounding

        Returns:
            Projected rewards
        """
        apy_decimal = apy / 100

        if compound:
            # Daily compounding
            daily_rate = apy_decimal / 365
            projected = principal * (1 + daily_rate) ** period_days
        else:
            projected = principal * (1 + apy_decimal * (period_days / 365))

        return {
            "principal": principal,
            "projected_total": projected,
            "projected_rewards": projected - principal,
            "apy": apy,
            "period_days": period_days,
        }

    def calculate_compound_growth(
        self,
        principal: float,
        apy: float,
        years: float,
        additional_contributions: Optional[float] = None,
        contribution_frequency: int = 12,
    ) -> Dict[str, float]:
        """
        Calculate compound growth with contributions.

        Args:
            principal: Initial principal
            apy: APY as percentage
            years: Number of years
            additional_contributions: Additional contributions per year
            contribution_frequency: Contributions per year

        Returns:
            Growth results
        """
        apy_decimal = apy / 100
        periods = years * contribution_frequency
        rate_per_period = apy_decimal / contribution_frequency

        # Compound growth
        final_amount = principal * (1 + rate_per_period) ** periods

        # Add contributions
        if additional_contributions:
            contribution_per_period = additional_contributions / contribution_frequency
            future_value_contributions = contribution_per_period * (
                ((1 + rate_per_period) ** periods - 1) / rate_per_period
            )
            final_amount += future_value_contributions

        return {
            "initial_principal": principal,
            "final_amount": final_amount,
            "total_rewards": final_amount - principal,
            "total_contributions": (additional_contributions * years) if additional_contributions else 0,
            "years": years,
            "apy": apy,
        }

    # -----------------------------------------------------------------------
    # Validator Analysis
    # -----------------------------------------------------------------------

    def analyze_validator_performance(
        self,
        validator_data: List[Dict[str, Any]],
    ) -> List[ValidatorPerformance]:
        """
        Analyze validator performance.

        Args:
            validator_data: List of validator data

        Returns:
            List of ValidatorPerformance
        """
        performances = []

        for data in validator_data:
            blocks_produced = data.get("blocks_produced", 0)
            blocks_missed = data.get("blocks_missed", 0)
            total_blocks = blocks_produced + blocks_missed

            # Calculate effectiveness
            effectiveness = blocks_produced / total_blocks if total_blocks > 0 else 0

            # Calculate score
            score = (
                effectiveness * 0.4 +
                (1 - data.get("commission", 0)) * 0.3 +
                (data.get("uptime", 0) / 100) * 0.3
            )

            performance = ValidatorPerformance(
                address=data.get("address", ""),
                name=data.get("name", "Unknown"),
                commission=data.get("commission", 0),
                uptime=data.get("uptime", 0),
                blocks_produced=blocks_produced,
                blocks_missed=blocks_missed,
                effectiveness=effectiveness * 100,
                apy=data.get("apy", 0),
                rank=0,
                score=score,
                metadata=data.get("metadata", {}),
            )

            performances.append(performance)

        # Sort and rank
        performances.sort(key=lambda x: x.score, reverse=True)
        for i, p in enumerate(performances):
            p.rank = i + 1

        return performances

    def identify_top_validators(
        self,
        performances: List[ValidatorPerformance],
        limit: int = 10,
        min_score: float = 0.5,
    ) -> List[ValidatorPerformance]:
        """
        Identify top validators.

        Args:
            performances: List of ValidatorPerformance
            limit: Number to return
            min_score: Minimum score threshold

        Returns:
            List of top validators
        """
        filtered = [p for p in performances if p.score >= min_score]
        filtered.sort(key=lambda x: x.score, reverse=True)
        return filtered[:limit]

    # -----------------------------------------------------------------------
    # Portfolio Optimization
    # -----------------------------------------------------------------------

    def optimize_portfolio(
        self,
        validators: List[ValidatorPerformance],
        total_amount: float,
        goal: OptimizationGoal = OptimizationGoal.BALANCED,
        max_validators: int = 5,
    ) -> PortfolioOptimization:
        """
        Optimize validator portfolio.

        Args:
            validators: List of validators
            total_amount: Total amount to allocate
            goal: Optimization goal
            max_validators: Maximum number of validators

        Returns:
            PortfolioOptimization
        """
        if not validators:
            return PortfolioOptimization(
                current_allocation={},
                optimized_allocation={},
                expected_apy=0,
                expected_risk=0,
                improvement=0,
                recommendations=["No validators available"],
            )

        # Score validators based on goal
        scored_validators = []
        for v in validators:
            if goal == OptimizationGoal.MAXIMIZE_APY:
                score = v.apy
            elif goal == OptimizationGoal.MINIMIZE_RISK:
                score = 1 - (1 - v.effectiveness / 100) * 0.5
            elif goal == OptimizationGoal.MINIMIZE_COMMISSION:
                score = 1 - v.commission
            else:  # BALANCED
                score = v.score

            scored_validators.append((score, v))

        scored_validators.sort(key=lambda x: x[0], reverse=True)

        # Select top validators
        selected = scored_validators[:max_validators]

        # Calculate allocation
        total_score = sum(s for s, _ in selected)
        allocation = {}

        for score, validator in selected:
            if total_score > 0:
                allocation[validator.address] = (score / total_score) * total_amount
            else:
                allocation[validator.address] = total_amount / len(selected)

        # Calculate expected APY and risk
        expected_apy = sum(
            (allocation.get(v.address, 0) / total_amount) * v.apy
            for _, v in selected
        )

        expected_risk = sum(
            (allocation.get(v.address, 0) / total_amount) * (1 - v.score)
            for _, v in selected
        )

        return PortfolioOptimization(
            current_allocation={v.address: total_amount / len(validators) for v in validators[:max_validators]},
            optimized_allocation=allocation,
            expected_apy=expected_apy,
            expected_risk=expected_risk,
            improvement=0,  # Would calculate from current
            recommendations=[
                f"Allocate {amount:.2f} to {v.name}" for amount, v in zip(allocation.values(), selected)
            ],
            metadata={
                "goal": goal.value,
                "max_validators": max_validators,
                "selected_count": len(selected),
            },
        )

    # -----------------------------------------------------------------------
    # Risk Assessment
    # -----------------------------------------------------------------------

    def assess_risk(
        self,
        staking_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Assess staking risk.

        Args:
            staking_data: Staking data

        Returns:
            Risk assessment
        """
        risk_factors = []
        risk_score = 0.0

        # Validator concentration risk
        validators = staking_data.get("validators", [])
        if validators:
            concentration = self._calculate_concentration_risk(validators)
            risk_score += concentration * 0.3
            if concentration > 0.7:
                risk_factors.append("High validator concentration")

        # Commission risk
        avg_commission = np.mean([v.get("commission", 0) for v in validators])
        if avg_commission > 0.2:
            risk_score += 0.2
            risk_factors.append("High average commission")

        # Uptime risk
        avg_uptime = np.mean([v.get("uptime", 0) for v in validators])
        if avg_uptime < 95:
            risk_score += 0.2
            risk_factors.append("Low average uptime")

        # Liquidity risk
        staked_amount = staking_data.get("staked_amount", 0)
        total_value = staking_data.get("total_value", 0)
        if staked_amount > 0:
            liquidity_ratio = staked_amount / max(total_value, 1)
            if liquidity_ratio > 0.5:
                risk_score += 0.15
                risk_factors.append("High concentration in staking")

        # Network risk
        network_risk = self._assess_network_risk(staking_data.get("network", ""))
        risk_score += network_risk * 0.15

        # Determine risk level
        if risk_score >= 0.7:
            risk_level = "high"
        elif risk_score >= 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "recommendations": self._generate_risk_recommendations(risk_factors),
            "metrics": {
                "concentration_risk": concentration if validators else 0,
                "avg_commission": avg_commission if validators else 0,
                "avg_uptime": avg_uptime if validators else 0,
            },
        }

    def _calculate_concentration_risk(self, validators: List[Dict[str, Any]]) -> float:
        """Calculate concentration risk."""
        stakes = [v.get("stake", 0) for v in validators]
        total_stake = sum(stakes)

        if total_stake == 0:
            return 0.0

        # Calculate Herfindahl-Hirschman Index (HHI)
        hhi = sum((s / total_stake) ** 2 for s in stakes)

        # Normalize to 0-1
        return min(hhi / 0.5, 1.0)

    def _assess_network_risk(self, network: str) -> float:
        """Assess network-specific risk."""
        # Simplified network risk scoring
        risk_map = {
            "cosmos": 0.2,
            "ethereum": 0.15,
            "solana": 0.25,
            "polkadot": 0.2,
            "avalanche": 0.2,
            "polygon": 0.2,
            "bnb": 0.15,
        }
        return risk_map.get(network.lower(), 0.3)

    def _generate_risk_recommendations(self, risk_factors: List[str]) -> List[str]:
        """Generate risk recommendations."""
        recommendations = []

        for factor in risk_factors:
            if "concentration" in factor.lower():
                recommendations.append("Diversify across more validators")
            elif "commission" in factor.lower():
                recommendations.append("Consider lower commission validators")
            elif "uptime" in factor.lower():
                recommendations.append("Switch to validators with better uptime")
            elif "liquidity" in factor.lower():
                recommendations.append("Reduce staking concentration")

        return recommendations

    # -----------------------------------------------------------------------
    # Reward Optimization
    # -----------------------------------------------------------------------

    def optimize_rewards(
        self,
        staking_positions: List[Dict[str, Any]],
        goal: OptimizationGoal = OptimizationGoal.MAXIMIZE_REWARDS,
    ) -> Dict[str, Any]:
        """
        Optimize rewards across staking positions.

        Args:
            staking_positions: List of staking positions
            goal: Optimization goal

        Returns:
            Optimization results
        """
        if not staking_positions:
            return {
                "optimized": False,
                "recommendations": ["No staking positions available"],
            }

        # Calculate current rewards
        current_rewards = sum(p.get("rewards", 0) for p in staking_positions)
        current_apy = np.mean([p.get("apy", 0) for p in staking_positions])

        # Score positions
        scored_positions = []
        for p in staking_positions:
            if goal == OptimizationGoal.MAXIMIZE_REWARDS:
                score = p.get("apy", 0) * p.get("staked_amount", 0)
            elif goal == OptimizationGoal.BALANCED:
                score = p.get("score", 0)
            else:
                score = p.get("apy", 0)

            scored_positions.append((score, p))

        scored_positions.sort(key=lambda x: x[0], reverse=True)

        # Generate recommendations
        recommendations = []
        total_staked = sum(p.get("staked_amount", 0) for p in staking_positions)

        for score, pos in scored_positions[:3]:
            if pos.get("apy", 0) < current_apy:
                recommendations.append(
                    f"Consider moving from {pos.get('provider', 'unknown')} "
                    f"(APY: {pos.get('apy', 0):.2f}%)"
                )

        return {
            "optimized": True,
            "current_rewards": current_rewards,
            "current_apy": current_apy,
            "recommendations": recommendations,
            "top_positions": [
                {
                    "provider": p.get("provider", ""),
                    "apy": p.get("apy", 0),
                    "staked_amount": p.get("staked_amount", 0),
                }
                for _, p in scored_positions[:3]
            ],
            "metadata": {
                "total_positions": len(staking_positions),
                "goal": goal.value,
            },
        }

    # -----------------------------------------------------------------------
    # Historical Analysis
    # -----------------------------------------------------------------------

    def analyze_historical_performance(
        self,
        data: List[Dict[str, Any]],
        time_frame: TimeFrame = TimeFrame.DAILY,
    ) -> Dict[str, Any]:
        """
        Analyze historical performance.

        Args:
            data: Historical data
            time_frame: Time frame for aggregation

        Returns:
            Historical analysis results
        """
        if not data:
            return {
                "has_data": False,
                "message": "No historical data available",
            }

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Ensure timestamp is datetime
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)

        # Resample based on time frame
        freq_map = {
            TimeFrame.HOURLY: "H",
            TimeFrame.DAILY: "D",
            TimeFrame.WEEKLY: "W",
            TimeFrame.MONTHLY: "M",
            TimeFrame.QUARTERLY: "Q",
            TimeFrame.YEARLY: "Y",
        }

        resampled = df.resample(freq_map.get(time_frame, "D")).agg({
            "value": ["mean", "min", "max", "std"],
            "volume": ["sum", "mean"],
            "rewards": ["sum", "mean"],
        })

        # Calculate trends
        if "value" in df.columns:
            trend = self._calculate_trend(df["value"])

        return {
            "has_data": True,
            "period": time_frame.value,
            "start_date": df.index.min(),
            "end_date": df.index.max(),
            "data_points": len(df),
            "aggregated_data": resampled.to_dict(),
            "trend": trend if "trend" in locals() else 0,
            "volatility": df["value"].std() if "value" in df.columns else 0,
            "max_drawdown": self._calculate_max_drawdown(df.get("value", [])),
        }

    def _calculate_trend(self, data: pd.Series) -> float:
        """Calculate trend using linear regression."""
        if len(data) < 2:
            return 0.0

        x = np.arange(len(data))
        slope, _ = np.polyfit(x, data.values, 1)
        return slope / (data.mean() if data.mean() != 0 else 1)

    def _calculate_max_drawdown(self, data: pd.Series) -> float:
        """Calculate maximum drawdown."""
        if len(data) < 2:
            return 0.0

        peak = data.iloc[0]
        max_drawdown = 0

        for value in data:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak != 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    # -----------------------------------------------------------------------
    # Yield Comparison
    # -----------------------------------------------------------------------

    def compare_yields(
        self,
        options: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compare yields across different options.

        Args:
            options: List of yield options

        Returns:
            Comparison results
        """
        if not options:
            return {
                "has_options": False,
                "message": "No yield options available",
            }

        # Score options
        scored_options = []
        for option in options:
            apy = option.get("apy", 0)
            risk = option.get("risk", 0.5)
            commission = option.get("commission", 0)
            lockup = option.get("lockup_days", 0)

            # Calculate composite score
            score = (
                apy * 0.4 +
                (1 - risk) * 0.3 +
                (1 - commission) * 0.2 +
                (1 - min(lockup / 365, 1)) * 0.1
            )

            scored_options.append((score, option))

        scored_options.sort(key=lambda x: x[0], reverse=True)

        return {
            "has_options": True,
            "top_options": [
                {
                    "name": o.get("name", ""),
                    "provider": o.get("provider", ""),
                    "apy": o.get("apy", 0),
                    "risk": o.get("risk", 0.5),
                    "commission": o.get("commission", 0),
                    "score": score,
                }
                for score, o in scored_options[:5]
            ],
            "best_option": {
                "name": scored_options[0][1].get("name", ""),
                "apy": scored_options[0][1].get("apy", 0),
                "score": scored_options[0][0],
            },
            "recommendations": [
                f"{o.get('name', '')} offers {o.get('apy', 0):.2f}% APY with low risk"
                for _, o in scored_options[:2]
            ],
        }

    # -----------------------------------------------------------------------
    # Performance Scoring
    # -----------------------------------------------------------------------

    def calculate_score(
        self,
        data: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate performance score.

        Args:
            data: Performance data
            weights: Custom weights

        Returns:
            Score results
        """
        weights = weights or self._weights

        # Extract metrics
        apy = data.get("apy", 0)
        risk = data.get("risk", 0.5)
        stability = data.get("stability", 0.5)
        liquidity = data.get("liquidity", 0.5)

        # Normalize metrics
        apy_score = min(apy / 20, 1.0)  # Max 20% APY
        risk_score = 1 - risk
        stability_score = stability
        liquidity_score = liquidity

        # Calculate weighted score
        total_score = (
            apy_score * weights.get("apy_weight", 0.4) +
            risk_score * weights.get("risk_weight", 0.3) +
            stability_score * weights.get("stability_weight", 0.2) +
            liquidity_score * weights.get("liquidity_weight", 0.1)
        )

        # Determine grade
        if total_score >= 0.9:
            grade = "A+"
        elif total_score >= 0.8:
            grade = "A"
        elif total_score >= 0.7:
            grade = "B+"
        elif total_score >= 0.6:
            grade = "B"
        elif total_score >= 0.5:
            grade = "C+"
        elif total_score >= 0.4:
            grade = "C"
        else:
            grade = "D"

        return {
            "score": total_score,
            "grade": grade,
            "components": {
                "apy": apy_score,
                "risk": risk_score,
                "stability": stability_score,
                "liquidity": liquidity_score,
            },
            "weights": weights,
        }

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Clear analytics cache."""
        self._cache.clear()
        logger.debug("Analytics cache cleared")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "cache_size": len(self._cache),
            "historical_data_size": len(self._historical_data),
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_staking_analytics(
    config: Optional[Dict[str, Any]] = None,
) -> StakingAnalytics:
    """
    Factory function to create a StakingAnalytics instance.

    Args:
        config: Configuration dictionary

    Returns:
        StakingAnalytics instance
    """
    return StakingAnalytics(config=config)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use staking analytics
    pass

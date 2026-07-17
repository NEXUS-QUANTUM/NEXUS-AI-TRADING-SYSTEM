# blockchain/staking/staking_apy.py
# NEXUS AI TRADING SYSTEM - Staking APY Calculation Engine
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Staking APY Calculation Engine for NEXUS AI Trading System.
Provides advanced APY/APR calculations across multiple blockchain networks
and staking protocols including:
- Real-time APY calculations
- Historical APY analysis
- APY projections and forecasting
- Protocol comparison
- Yield optimization
- Risk-adjusted returns
- Compound APY calculations
"""

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

# NEXUS Imports
from blockchain.staking.base_staking import StakingProvider
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.staking.apy")


# ============================================================================
# Enums & Constants
# ============================================================================

class APYType(str, Enum):
    """APY calculation types."""
    SIMPLE = "simple"
    COMPOUND = "compound"
    EFFECTIVE = "effective"
    NOMINAL = "nominal"
    REAL = "real"


class CalculationMethod(str, Enum):
    """Calculation methods."""
    STATIC = "static"
    HISTORICAL = "historical"
    FORECAST = "forecast"
    DYNAMIC = "dynamic"
    WEIGHTED = "weighted"


@dataclass
class APYResult:
    """APY calculation result."""
    apy: float
    apr: float
    apy_type: APYType
    calculation_method: CalculationMethod
    period: str
    confidence: float
    components: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APYHistory:
    """APY historical data."""
    timestamp: datetime
    apy: float
    apr: float
    rewards_earned: float
    staked_amount: float
    period_days: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APYProjection:
    """APY projection."""
    current_apy: float
    projected_apy: float
    confidence_interval: Tuple[float, float]
    timeframe_days: int
    trend: str
    factors: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# APY Calculation Engine
# ============================================================================

class StakingAPY:
    """
    Staking APY Calculation Engine.
    Provides advanced APY/APR calculations for staking positions.
    """

    # Network-specific parameters
    NETWORK_PARAMS = {
        StakingProvider.COSMOS: {
            "blocks_per_year": 6_500_000,
            "inflation_rate": 0.10,
            "commission_avg": 0.05,
        },
        StakingProvider.ETHEREUM: {
            "blocks_per_year": 2_100_000,
            "inflation_rate": 0.0,
            "commission_avg": 0.0,
        },
        StakingProvider.SOLANA: {
            "epochs_per_year": 365,
            "inflation_rate": 0.08,
            "commission_avg": 0.07,
        },
        StakingProvider.POLKADOT: {
            "eras_per_year": 365,
            "inflation_rate": 0.10,
            "commission_avg": 0.05,
        },
        StakingProvider.BNB: {
            "blocks_per_year": 10_000_000,
            "inflation_rate": 0.05,
            "commission_avg": 0.05,
        },
        StakingProvider.AVALANCHE: {
            "blocks_per_year": 6_500_000,
            "inflation_rate": 0.09,
            "commission_avg": 0.04,
        },
        StakingProvider.POLYGON: {
            "blocks_per_year": 20_000_000,
            "inflation_rate": 0.04,
            "commission_avg": 0.03,
        },
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize APY calculation engine.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # Data storage
        self._historical_apy: Dict[str, List[APYHistory]] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Performance metrics
        self._performance = {
            "calculations_performed": 0,
            "historical_analyses": 0,
            "projections_generated": 0,
            "avg_calculation_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        logger.info("StakingAPY initialized")

    # -----------------------------------------------------------------------
    # Core APY Calculations
    # -----------------------------------------------------------------------

    def calculate_apy(
        self,
        rewards: float,
        principal: float,
        period_days: float,
        method: APYType = APYType.COMPOUND,
        compound_frequency: Optional[int] = None,
    ) -> APYResult:
        """
        Calculate APY from rewards.

        Args:
            rewards: Rewards earned
            principal: Principal amount
            period_days: Period in days
            method: APY calculation method
            compound_frequency: Compound frequency per year

        Returns:
            APYResult
        """
        start_time = time.time()

        if principal == 0:
            return APYResult(
                apy=0,
                apr=0,
                apy_type=method,
                calculation_method=CalculationMethod.STATIC,
                period=f"{period_days}d",
                confidence=0.0,
                components={},
            )

        # Calculate APR
        apr = (rewards / principal) * (365 / period_days)

        # Calculate APY based on method
        if method == APYType.SIMPLE:
            apy = apr
        elif method == APYType.COMPOUND:
            freq = compound_frequency or 365
            apy = (1 + apr / freq) ** freq - 1
        elif method == APYType.EFFECTIVE:
            apy = (1 + apr / 365) ** 365 - 1
        elif method == APYType.NOMINAL:
            apy = apr * (1 + apr)  # Simple nominal conversion
        elif method == APYType.REAL:
            inflation = self.config.get("inflation_rate", 0.0)
            apy = ((1 + apr) / (1 + inflation)) - 1
        else:
            apy = apr

        # Calculate components
        components = {
            "rewards": rewards,
            "principal": principal,
            "period_days": period_days,
            "apr": apr * 100,
            "apy": apy * 100,
        }

        # Determine calculation method
        calc_method = CalculationMethod.STATIC

        result = APYResult(
            apy=apy * 100,
            apr=apr * 100,
            apy_type=method,
            calculation_method=calc_method,
            period=f"{period_days}d",
            confidence=1.0,
            components=components,
        )

        self._performance["calculations_performed"] += 1
        elapsed_ms = (time.time() - start_time) * 1000
        self._performance["avg_calculation_time_ms"] = (
            (self._performance["avg_calculation_time_ms"] *
             (self._performance["calculations_performed"] - 1) +
             elapsed_ms) / self._performance["calculations_performed"]
        )

        return result

    def calculate_network_apy(
        self,
        provider: StakingProvider,
        commission: Optional[float] = None,
        staked_percentage: Optional[float] = None,
    ) -> APYResult:
        """
        Calculate network-specific APY.

        Args:
            provider: Staking provider
            commission: Validator commission (optional)
            staked_percentage: Percentage of supply staked

        Returns:
            APYResult
        """
        params = self.NETWORK_PARAMS.get(provider, {})
        commission = commission or params.get("commission_avg", 0.05)
        staked_percentage = staked_percentage or 0.5

        # Base yield from inflation
        inflation = params.get("inflation_rate", 0.08)

        # Calculate staking yield
        if staked_percentage > 0:
            base_yield = inflation / staked_percentage
        else:
            base_yield = inflation

        # Apply commission
        net_yield = base_yield * (1 - commission)

        # Convert to APY
        apy = net_yield * 100
        apr = net_yield * 100

        return APYResult(
            apy=apy,
            apr=apr,
            apy_type=APYType.EFFECTIVE,
            calculation_method=CalculationMethod.DYNAMIC,
            period="yearly",
            confidence=0.8,
            components={
                "inflation_rate": inflation,
                "commission": commission,
                "staked_percentage": staked_percentage,
                "base_yield": base_yield * 100,
                "net_yield": net_yield * 100,
            },
            metadata={
                "provider": provider.value,
                "network_params": params,
            },
        )

    # -----------------------------------------------------------------------
    # Historical APY Analysis
    # -----------------------------------------------------------------------

    def analyze_historical_apy(
        self,
        history: List[APYHistory],
        window_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Analyze historical APY.

        Args:
            history: Historical APY data
            window_days: Analysis window in days

        Returns:
            Historical analysis results
        """
        if not history:
            return {
                "has_data": False,
                "message": "No historical data available",
            }

        self._performance["historical_analyses"] += 1

        # Filter by window
        if window_days:
            cutoff = datetime.utcnow() - timedelta(days=window_days)
            history = [h for h in history if h.timestamp >= cutoff]

        if not history:
            return {
                "has_data": False,
                "message": "No data in selected window",
            }

        # Extract APY values
        apy_values = [h.apy for h in history]
        timestamps = [h.timestamp for h in history]

        # Calculate statistics
        stats_results = {
            "has_data": True,
            "start_date": timestamps[0],
            "end_date": timestamps[-1],
            "data_points": len(history),
            "current_apy": apy_values[-1],
            "average_apy": np.mean(apy_values),
            "median_apy": np.median(apy_values),
            "min_apy": min(apy_values),
            "max_apy": max(apy_values),
            "std_dev": np.std(apy_values),
            "volatility": np.std(apy_values) / np.mean(apy_values) if np.mean(apy_values) > 0 else 0,
        }

        # Calculate trend
        if len(apy_values) >= 2:
            x = np.arange(len(apy_values))
            slope, intercept = np.polyfit(x, apy_values, 1)
            stats_results["trend"] = slope
            stats_results["trend_direction"] = "up" if slope > 0 else "down" if slope < 0 else "stable"

            # Forecast
            forecast_window = 7
            last_value = apy_values[-1]
            forecast_values = [last_value + slope * i for i in range(forecast_window)]

            stats_results["forecast"] = {
                "days": forecast_window,
                "values": forecast_values,
                "end_apy": forecast_values[-1],
                "change": ((forecast_values[-1] - last_value) / last_value * 100) if last_value > 0 else 0,
            }

        # Calculate percentile distribution
        percentiles = [10, 25, 50, 75, 90]
        stats_results["percentiles"] = {
            str(p): np.percentile(apy_values, p) for p in percentiles
        }

        # Find best and worst periods
        if len(history) > 1:
            max_idx = np.argmax(apy_values)
            min_idx = np.argmin(apy_values)
            stats_results["best_period"] = {
                "date": timestamps[max_idx],
                "apy": apy_values[max_idx],
            }
            stats_results["worst_period"] = {
                "date": timestamps[min_idx],
                "apy": apy_values[min_idx],
            }

        return stats_results

    # -----------------------------------------------------------------------
    # APY Projections
    # -----------------------------------------------------------------------

    def project_apy(
        self,
        current_apy: float,
        history: Optional[List[APYHistory]] = None,
        days_ahead: int = 30,
        confidence_level: float = 0.95,
    ) -> APYProjection:
        """
        Project future APY.

        Args:
            current_apy: Current APY
            history: Historical APY data
            days_ahead: Projection horizon in days
            confidence_level: Confidence level for interval

        Returns:
            APYProjection
        """
        self._performance["projections_generated"] += 1

        if history and len(history) > 0:
            # Use historical data for projection
            return self._project_from_history(
                current_apy,
                history,
                days_ahead,
                confidence_level,
            )
        else:
            # Use simple projection
            return self._project_simple(
                current_apy,
                days_ahead,
                confidence_level,
            )

    def _project_from_history(
        self,
        current_apy: float,
        history: List[APYHistory],
        days_ahead: int,
        confidence_level: float,
    ) -> APYProjection:
        """Project APY from historical data."""
        # Extract historical values
        apy_values = [h.apy for h in history]

        if len(apy_values) < 2:
            return self._project_simple(current_apy, days_ahead, confidence_level)

        # Calculate trend
        x = np.arange(len(apy_values))
        slope, intercept = np.polyfit(x, apy_values, 1)

        # Project forward
        last_value = apy_values[-1]
        days_projected = days_ahead / (365 / len(apy_values))
        projected_apy = last_value + slope * days_projected

        # Calculate confidence interval
        residuals = apy_values - (slope * x + intercept)
        std_residuals = np.std(residuals)

        # Adjust for future uncertainty
        uncertainty_factor = 1 + (days_ahead / 365) * 0.5
        adjusted_std = std_residuals * uncertainty_factor

        # Calculate Z-score for confidence level
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        margin = z_score * adjusted_std

        # Determine trend
        if slope > 0.05:
            trend = "increasing"
        elif slope < -0.05:
            trend = "decreasing"
        else:
            trend = "stable"

        # Identify factors
        factors = [
            {"factor": "historical_trend", "value": slope, "impact": "positive" if slope > 0 else "negative"},
            {"factor": "volatility", "value": std_residuals, "impact": "neutral"},
        ]

        return APYProjection(
            current_apy=current_apy,
            projected_apy=projected_apy,
            confidence_interval=(projected_apy - margin, projected_apy + margin),
            timeframe_days=days_ahead,
            trend=trend,
            factors=factors,
            metadata={
                "historical_data_points": len(history),
                "confidence_level": confidence_level,
                "projection_method": "historical_trend",
            },
        )

    def _project_simple(
        self,
        current_apy: float,
        days_ahead: int,
        confidence_level: float,
    ) -> APYProjection:
        """Simple APY projection."""
        # Assume small decay over time
        decay_factor = 0.01 * (days_ahead / 365)
        projected_apy = current_apy * (1 - decay_factor)

        # Wider confidence interval for simple projection
        margin = projected_apy * 0.2

        return APYProjection(
            current_apy=current_apy,
            projected_apy=projected_apy,
            confidence_interval=(projected_apy - margin, projected_apy + margin),
            timeframe_days=days_ahead,
            trend="stable",
            factors=[
                {"factor": "decay", "value": decay_factor, "impact": "negative"},
                {"factor": "uncertainty", "value": 0.2, "impact": "neutral"},
            ],
            metadata={
                "projection_method": "simple_decay",
                "confidence_level": confidence_level,
            },
        )

    # -----------------------------------------------------------------------
    # APY Comparison
    # -----------------------------------------------------------------------

    def compare_apy(
        self,
        apy_results: Dict[str, APYResult],
    ) -> Dict[str, Any]:
        """
        Compare APY across different protocols.

        Args:
            apy_results: Dict of protocol -> APYResult

        Returns:
            Comparison results
        """
        if not apy_results:
            return {
                "has_data": False,
                "message": "No APY data to compare",
            }

        # Sort by APY
        sorted_results = sorted(
            apy_results.items(),
            key=lambda x: x[1].apy,
            reverse=True,
        )

        # Calculate statistics
        apy_values = [r.apy for _, r in sorted_results]

        return {
            "has_data": True,
            "best_protocol": {
                "name": sorted_results[0][0],
                "apy": sorted_results[0][1].apy,
                "apr": sorted_results[0][1].apr,
            },
            "worst_protocol": {
                "name": sorted_results[-1][0],
                "apy": sorted_results[-1][1].apy,
                "apr": sorted_results[-1][1].apr,
            },
            "ranking": [
                {
                    "rank": i + 1,
                    "protocol": name,
                    "apy": result.apy,
                    "apr": result.apr,
                    "confidence": result.confidence,
                }
                for i, (name, result) in enumerate(sorted_results)
            ],
            "statistics": {
                "average_apy": np.mean(apy_values),
                "median_apy": np.median(apy_values),
                "min_apy": min(apy_values),
                "max_apy": max(apy_values),
                "std_dev": np.std(apy_values),
            },
            "recommendations": [
                f"Best APY: {sorted_results[0][0]} at {sorted_results[0][1].apy:.2f}%",
                f"Consider {sorted_results[1][0]} as alternative at {sorted_results[1][1].apy:.2f}%",
            ],
        }

    # -----------------------------------------------------------------------
    # Risk-Adjusted APY
    # -----------------------------------------------------------------------

    def calculate_risk_adjusted_apy(
        self,
        apy: float,
        risk_score: float,
        risk_free_rate: float = 0.02,
    ) -> Dict[str, float]:
        """
        Calculate risk-adjusted APY.

        Args:
            apy: Raw APY
            risk_score: Risk score (0-1)
            risk_free_rate: Risk-free rate

        Returns:
            Risk-adjusted metrics
        """
        # Sharpe ratio (simplified)
        excess_return = (apy / 100) - risk_free_rate
        sharpe = excess_return / max(risk_score, 0.01)

        # Sortino ratio (focus on downside risk)
        downside_risk = risk_score * 0.5  # Simplified
        sortino = excess_return / max(downside_risk, 0.01)

        # Risk-adjusted APY
        risk_adjusted = apy * (1 - risk_score)

        return {
            "raw_apy": apy,
            "risk_adjusted_apy": risk_adjusted,
            "risk_score": risk_score,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "excess_return": excess_return * 100,
            "risk_free_rate": risk_free_rate * 100,
        }

    # -----------------------------------------------------------------------
    # Compound APY Calculations
    # -----------------------------------------------------------------------

    def calculate_compound_apy(
        self,
        base_apy: float,
        compounding_frequency: int = 365,
        reinvestment_rate: float = 1.0,
    ) -> APYResult:
        """
        Calculate compound APY.

        Args:
            base_apy: Base APY
            compounding_frequency: Times per year
            reinvestment_rate: Rate of reinvestment (0-1)

        Returns:
            APYResult
        """
        base_rate = base_apy / 100
        adjusted_rate = base_rate * reinvestment_rate

        # Compound formula
        compound_apy = (1 + adjusted_rate / compounding_frequency) ** compounding_frequency - 1

        # Calculate effect of compounding
        compounding_effect = (compound_apy - base_rate) * 100

        return APYResult(
            apy=compound_apy * 100,
            apr=base_apy,
            apy_type=APYType.COMPOUND,
            calculation_method=CalculationMethod.DYNAMIC,
            period="yearly",
            confidence=0.9,
            components={
                "base_apy": base_apy,
                "compounding_frequency": compounding_frequency,
                "reinvestment_rate": reinvestment_rate,
                "compounding_effect": compounding_effect,
            },
            metadata={
                "formula": "compound",
                "frequency": compounding_frequency,
            },
        )

    def calculate_yearly_compound(
        self,
        initial_stake: float,
        apy: float,
        years: int,
        compound_frequency: int = 365,
        additional_stake: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculate yearly compound growth.

        Args:
            initial_stake: Initial stake amount
            apy: Annual percentage yield
            years: Number of years
            compound_frequency: Times to compound per year
            additional_stake: Additional stake per period

        Returns:
            Compound growth results
        """
        rate = apy / 100
        periods = years * compound_frequency
        rate_per_period = rate / compound_frequency

        # Calculate future value
        if additional_stake:
            # With additional contributions
            fv_initial = initial_stake * (1 + rate_per_period) ** periods
            fv_contributions = additional_stake * (
                ((1 + rate_per_period) ** periods - 1) / rate_per_period
            )
            future_value = fv_initial + fv_contributions
        else:
            future_value = initial_stake * (1 + rate_per_period) ** periods

        # Calculate rewards
        total_rewards = future_value - initial_stake
        if additional_stake:
            total_contributions = additional_stake * periods
            total_rewards = future_value - initial_stake - total_contributions

        # Calculate effective APY
        effective_apy = ((future_value / initial_stake) ** (1 / years) - 1) * 100

        return {
            "initial_stake": initial_stake,
            "future_value": future_value,
            "total_rewards": total_rewards,
            "effective_apy": effective_apy,
            "years": years,
            "compound_frequency": compound_frequency,
            "periods": periods,
            "additional_stake": additional_stake,
            "metadata": {
                "formula": "compound_with_contributions" if additional_stake else "compound",
            },
        }

    # -----------------------------------------------------------------------
    # APY Optimization
    # -----------------------------------------------------------------------

    def optimize_apy(
        self,
        options: List[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Optimize APY across options.

        Args:
            options: List of options with APY and constraints
            constraints: Optimization constraints

        Returns:
            Optimization results
        """
        if not options:
            return {
                "optimized": False,
                "message": "No options available",
            }

        constraints = constraints or {}

        # Prepare optimization data
        apys = [opt.get("apy", 0) for opt in options]
        risks = [opt.get("risk", 0.5) for opt in options]
        weights = [1.0 / len(options)] * len(options)

        # Objective: maximize APY with risk constraints
        def objective(w):
            weighted_apy = sum(w[i] * apys[i] for i in range(len(w)))
            weighted_risk = sum(w[i] * risks[i] for i in range(len(w)))
            return -(weighted_apy - constraints.get("risk_penalty", 0.5) * weighted_risk)

        # Constraints
        cons = (
            {"type": "eq", "fun": lambda w: sum(w) - 1}  # Sum of weights = 1
        )

        # Bounds
        bounds = [(0, 1)] * len(options)

        # Optimize
        result = minimize(
            objective,
            weights,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
        )

        if result.success:
            optimal_weights = result.x
            optimal_apy = sum(optimal_weights[i] * apys[i] for i in range(len(options)))
            optimal_risk = sum(optimal_weights[i] * risks[i] for i in range(len(options)))

            return {
                "optimized": True,
                "optimal_weights": {
                    opt.get("name", f"option_{i}"): w
                    for i, (opt, w) in enumerate(zip(options, optimal_weights))
                    if w > 0.01
                },
                "optimal_apy": optimal_apy,
                "optimal_risk": optimal_risk,
                "original_apy": sum(weights[i] * apys[i] for i in range(len(options))),
                "improvement": optimal_apy - sum(weights[i] * apys[i] for i in range(len(options))),
                "recommendations": [
                    f"Allocate {w:.1%} to {options[i].get('name', f'Option {i}')}"
                    for i, w in enumerate(optimal_weights)
                    if w > 0.05
                ],
            }
        else:
            return {
                "optimized": False,
                "message": "Optimization failed",
                "details": result.message,
            }

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def add_historical_apy(
        self,
        provider: StakingProvider,
        apy: float,
        rewards: float,
        staked_amount: float,
        period_days: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add historical APY data.

        Args:
            provider: Staking provider
            apy: APY value
            rewards: Rewards earned
            staked_amount: Staked amount
            period_days: Period in days
            metadata: Additional metadata
        """
        key = provider.value

        if key not in self._historical_apy:
            self._historical_apy[key] = []

        history = APYHistory(
            timestamp=datetime.utcnow(),
            apy=apy,
            apr=apy,  # Simplified
            rewards_earned=rewards,
            staked_amount=staked_amount,
            period_days=period_days,
            metadata=metadata or {},
        )

        self._historical_apy[key].append(history)

        # Limit history size
        if len(self._historical_apy[key]) > 10000:
            self._historical_apy[key] = self._historical_apy[key][-10000:]

    def get_historical_apy(
        self,
        provider: StakingProvider,
        hours: Optional[int] = None,
    ) -> List[APYHistory]:
        """
        Get historical APY data.

        Args:
            provider: Staking provider
            hours: Hours to look back

        Returns:
            List of APYHistory
        """
        key = provider.value

        if key not in self._historical_apy:
            return []

        history = self._historical_apy[key]

        if hours:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            history = [h for h in history if h.timestamp >= cutoff]

        return history

    def clear_cache(self) -> None:
        """Clear calculation cache."""
        self._cache.clear()
        logger.debug("APY cache cleared")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "cache_size": len(self._cache),
            "historical_data_size": sum(len(h) for h in self._historical_apy.values()),
            "providers_tracked": len(self._historical_apy),
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_staking_apy(
    config: Optional[Dict[str, Any]] = None,
) -> StakingAPY:
    """
    Factory function to create a StakingAPY instance.

    Args:
        config: Configuration dictionary

    Returns:
        StakingAPY instance
    """
    return StakingAPY(config=config)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the staking APY engine
    pass

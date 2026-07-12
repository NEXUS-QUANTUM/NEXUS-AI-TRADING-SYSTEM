"""
NEXUS AI TRADING SYSTEM - Monte Carlo Simulator
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Monte Carlo Simulator system with:
- Multiple simulation methods (Historical, Parametric, Bootstrapping)
- Random walk simulations
- Geometric Brownian Motion
- Jump diffusion models
- Portfolio simulations
- Risk metrics
- Probability distributions
- Confidence intervals
- Performance analytics
- Visualization
- Export capabilities
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pydantic import BaseModel, Field, validator
from scipy import stats
from scipy.optimize import minimize

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import MonteCarloError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class SimulationMethod(str, Enum):
    """Simulation methods"""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    BOOTSTRAP = "bootstrap"
    GBM = "geometric_brownian_motion"
    JUMP_DIFFUSION = "jump_diffusion"
    MONTE_CARLO = "monte_carlo"


class DistributionType(str, Enum):
    """Distribution types"""
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    T = "t"
    CAUCHY = "cauchy"
    SKEWED_T = "skewed_t"
    GENERALIZED = "generalized"
    EMPIRICAL = "empirical"


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    method: SimulationMethod
    iterations: int
    initial_value: float
    final_values: List[float]
    paths: List[List[float]]
    returns: List[float]
    statistics: Dict[str, Any] = field(default_factory=dict)
    confidence_intervals: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    probability_metrics: Dict[str, float] = field(default_factory=dict)
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    percentiles: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonteCarloStats:
    """Monte Carlo statistics"""
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    min: float = 0.0
    max: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    expected_shortfall: float = 0.0


class MonteCarloConfig(BaseModel):
    """Monte Carlo configuration"""
    method: SimulationMethod = SimulationMethod.HISTORICAL
    distribution: DistributionType = DistributionType.NORMAL
    iterations: int = Field(default=10000, gt=0, le=1000000)
    simulation_days: int = Field(default=252, gt=0)
    confidence_level: float = Field(default=0.95, ge=0, le=1)
    random_seed: Optional[int] = None
    use_volatility_surface: bool = False
    correlation_matrix: Optional[List[List[float]]] = None
    drift: Optional[float] = None
    volatility: Optional[float] = None
    jump_intensity: float = Field(default=0.0, ge=0)
    jump_mean: float = Field(default=0.0)
    jump_std: float = Field(default=0.1, gt=0)
    mean_reversion: bool = False
    mean_reversion_speed: float = Field(default=0.1, gt=0)
    mean_reversion_level: float = Field(default=0.0)
    parallel_workers: int = Field(default=4, gt=0)
    cache_results: bool = True
    cache_ttl: int = Field(default=3600, gt=0)
    log_level: str = "info"


# ========================================
# MONTE CARLO SIMULATOR
# ========================================

class MonteCarloSimulator:
    """
    Complete Monte Carlo simulator for trading strategies.
    
    Features:
    - Multiple simulation methods
    - Random walk simulations
    - Geometric Brownian Motion
    - Jump diffusion models
    - Portfolio simulations
    - Risk metrics
    - Probability distributions
    - Confidence intervals
    - Performance analytics
    - Visualization
    - Export capabilities
    - Health monitoring
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = MonteCarloConfig(**(config or {}))
        self.redis = get_redis()
        
        # Set random seed
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)
        
        # Cache
        self._cache: Dict[str, Tuple[MonteCarloResult, datetime]] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_simulations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_simulation_time": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.MonteCarloSimulator")
        self.logger.info("MonteCarloSimulator initialized")
    
    # ========================================
    # MAIN SIMULATION
    # ========================================
    
    async def simulate(
        self,
        returns: Optional[List[float]] = None,
        prices: Optional[List[float]] = None,
        initial_value: float = 100000.0,
        method: Optional[SimulationMethod] = None,
        iterations: Optional[int] = None,
        simulation_days: Optional[int] = None
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.
        
        Args:
            returns: Historical returns
            prices: Historical prices
            initial_value: Initial portfolio value
            method: Simulation method
            iterations: Number of iterations
            simulation_days: Simulation days
            
        Returns:
            MonteCarloResult: Simulation result
        """
        start_time = time.time()
        
        # Use config defaults
        method = method or self.config.method
        iterations = iterations or self.config.iterations
        simulation_days = simulation_days or self.config.simulation_days
        
        # Check cache
        cache_key = self._generate_cache_key(
            returns,
            prices,
            initial_value,
            method,
            iterations,
            simulation_days
        )
        
        if self.config.cache_results:
            cached = self._get_cached_result(cache_key)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        self._metrics["cache_misses"] += 1
        
        try:
            # Prepare data
            if prices is not None:
                returns = self._calculate_returns_from_prices(prices)
            
            if returns is None:
                raise MonteCarloError("No returns or prices provided")
            
            # Run simulation based on method
            if method == SimulationMethod.HISTORICAL:
                result = await self._simulate_historical(
                    returns,
                    initial_value,
                    iterations,
                    simulation_days
                )
            elif method == SimulationMethod.PARAMETRIC:
                result = await self._simulate_parametric(
                    returns,
                    initial_value,
                    iterations,
                    simulation_days
                )
            elif method == SimulationMethod.BOOTSTRAP:
                result = await self._simulate_bootstrap(
                    returns,
                    initial_value,
                    iterations,
                    simulation_days
                )
            elif method == SimulationMethod.GBM:
                result = await self._simulate_gbm(
                    returns,
                    initial_value,
                    iterations,
                    simulation_days
                )
            elif method == SimulationMethod.JUMP_DIFFUSION:
                result = await self._simulate_jump_diffusion(
                    returns,
                    initial_value,
                    iterations,
                    simulation_days
                )
            else:
                result = await self._simulate_historical(
                    returns,
                    initial_value,
                    iterations,
                    simulation_days
                )
            
            # Calculate statistics
            result = await self._calculate_statistics(result)
            
            # Calculate probability metrics
            result = await self._calculate_probability_metrics(
                result,
                initial_value
            )
            
            # Calculate risk metrics
            result = await self._calculate_risk_metrics(result)
            
            # Cache result
            if self.config.cache_results:
                self._set_cached_result(cache_key, result)
            
            # Update metrics
            elapsed = time.time() - start_time
            self._metrics["total_simulations"] += 1
            self._metrics["avg_simulation_time"] = (
                self._metrics["avg_simulation_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(
                f"Simulation completed in {elapsed:.2f}s "
                f"({iterations} iterations, {simulation_days} days)"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Simulation failed: {e}")
            raise MonteCarloError(f"Simulation failed: {e}")
    
    # ========================================
    # SIMULATION METHODS
    # ========================================
    
    async def _simulate_historical(
        self,
        returns: List[float],
        initial_value: float,
        iterations: int,
        simulation_days: int
    ) -> MonteCarloResult:
        """Historical simulation"""
        # Calculate statistics
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Generate paths
        paths = []
        final_values = []
        
        for _ in range(iterations):
            path = [initial_value]
            current = initial_value
            
            for _ in range(simulation_days):
                # Randomly select historical return
                ret = np.random.choice(returns)
                current *= (1 + ret)
                path.append(current)
            
            paths.append(path)
            final_values.append(current)
        
        result = MonteCarloResult(
            method=SimulationMethod.HISTORICAL,
            iterations=iterations,
            initial_value=initial_value,
            final_values=final_values,
            paths=paths,
            returns=returns,
            metadata={
                'mean_return': mean_return,
                'std_return': std_return,
                'simulation_days': simulation_days
            }
        )
        
        return result
    
    async def _simulate_parametric(
        self,
        returns: List[float],
        initial_value: float,
        iterations: int,
        simulation_days: int
    ) -> MonteCarloResult:
        """Parametric simulation"""
        # Calculate statistics
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Generate paths
        paths = []
        final_values = []
        
        # Determine distribution
        if self.config.distribution == DistributionType.NORMAL:
            dist = stats.norm(mean_return, std_return)
        elif self.config.distribution == DistributionType.T:
            dist = stats.t(df=5, loc=mean_return, scale=std_return)
        else:
            dist = stats.norm(mean_return, std_return)
        
        for _ in range(iterations):
            path = [initial_value]
            current = initial_value
            
            for _ in range(simulation_days):
                ret = dist.rvs()
                current *= (1 + ret)
                path.append(current)
            
            paths.append(path)
            final_values.append(current)
        
        result = MonteCarloResult(
            method=SimulationMethod.PARAMETRIC,
            iterations=iterations,
            initial_value=initial_value,
            final_values=final_values,
            paths=paths,
            returns=returns,
            metadata={
                'mean_return': mean_return,
                'std_return': std_return,
                'distribution': self.config.distribution.value,
                'simulation_days': simulation_days
            }
        )
        
        return result
    
    async def _simulate_bootstrap(
        self,
        returns: List[float],
        initial_value: float,
        iterations: int,
        simulation_days: int
    ) -> MonteCarloResult:
        """Bootstrap simulation"""
        # Generate paths using bootstrap resampling
        paths = []
        final_values = []
        
        for _ in range(iterations):
            # Resample returns with replacement
            sampled_returns = np.random.choice(returns, size=simulation_days, replace=True)
            
            path = [initial_value]
            current = initial_value
            
            for ret in sampled_returns:
                current *= (1 + ret)
                path.append(current)
            
            paths.append(path)
            final_values.append(current)
        
        result = MonteCarloResult(
            method=SimulationMethod.BOOTSTRAP,
            iterations=iterations,
            initial_value=initial_value,
            final_values=final_values,
            paths=paths,
            returns=returns,
            metadata={
                'simulation_days': simulation_days
            }
        )
        
        return result
    
    async def _simulate_gbm(
        self,
        returns: List[float],
        initial_value: float,
        iterations: int,
        simulation_days: int
    ) -> MonteCarloResult:
        """Geometric Brownian Motion simulation"""
        # Calculate parameters
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Use drift if provided
        drift = self.config.drift if self.config.drift is not None else mean_return
        
        # Use volatility if provided
        volatility = self.config.volatility if self.config.volatility is not None else std_return
        
        # Calculate GBM parameters
        mu = drift - 0.5 * volatility ** 2
        
        # Generate paths
        paths = []
        final_values = []
        
        for _ in range(iterations):
            path = [initial_value]
            current = initial_value
            
            # Generate random normal variables
            z = np.random.normal(0, 1, simulation_days)
            
            for i in range(simulation_days):
                ret = mu + volatility * z[i]
                current *= (1 + ret)
                path.append(current)
            
            paths.append(path)
            final_values.append(current)
        
        result = MonteCarloResult(
            method=SimulationMethod.GBM,
            iterations=iterations,
            initial_value=initial_value,
            final_values=final_values,
            paths=paths,
            returns=returns,
            metadata={
                'drift': drift,
                'volatility': volatility,
                'mu': mu,
                'simulation_days': simulation_days
            }
        )
        
        return result
    
    async def _simulate_jump_diffusion(
        self,
        returns: List[float],
        initial_value: float,
        iterations: int,
        simulation_days: int
    ) -> MonteCarloResult:
        """Jump diffusion simulation"""
        # Calculate parameters
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Use drift if provided
        drift = self.config.drift if self.config.drift is not None else mean_return
        
        # Use volatility if provided
        volatility = self.config.volatility if self.config.volatility is not None else std_return
        
        # Jump parameters
        jump_intensity = self.config.jump_intensity
        jump_mean = self.config.jump_mean
        jump_std = self.config.jump_std
        
        # Generate paths
        paths = []
        final_values = []
        
        for _ in range(iterations):
            path = [initial_value]
            current = initial_value
            
            # Generate random variables
            z = np.random.normal(0, 1, simulation_days)
            jump_events = np.random.poisson(jump_intensity, simulation_days)
            jump_sizes = np.random.normal(jump_mean, jump_std, simulation_days)
            
            for i in range(simulation_days):
                ret = drift + volatility * z[i]
                
                # Add jumps
                if jump_events[i] > 0:
                    ret += jump_sizes[i]
                
                current *= (1 + ret)
                path.append(current)
            
            paths.append(path)
            final_values.append(current)
        
        result = MonteCarloResult(
            method=SimulationMethod.JUMP_DIFFUSION,
            iterations=iterations,
            initial_value=initial_value,
            final_values=final_values,
            paths=paths,
            returns=returns,
            metadata={
                'drift': drift,
                'volatility': volatility,
                'jump_intensity': jump_intensity,
                'jump_mean': jump_mean,
                'jump_std': jump_std,
                'simulation_days': simulation_days
            }
        )
        
        return result
    
    # ========================================
    # STATISTICS CALCULATION
    # ========================================
    
    async def _calculate_statistics(
        self,
        result: MonteCarloResult
    ) -> MonteCarloResult:
        """Calculate statistics from simulation results"""
        final_values = result.final_values
        
        if not final_values:
            return result
        
        # Basic statistics
        stats = MonteCarloStats()
        stats.mean = np.mean(final_values)
        stats.median = np.median(final_values)
        stats.std = np.std(final_values)
        stats.min = np.min(final_values)
        stats.max = np.max(final_values)
        stats.skewness = stats.skew(final_values)
        stats.kurtosis = stats.kurtosis(final_values)
        
        # VaR
        confidence = self.config.confidence_level
        stats.var_95 = np.percentile(final_values, (1 - 0.95) * 100)
        stats.var_99 = np.percentile(final_values, (1 - 0.99) * 100)
        
        # CVaR
        var_95 = stats.var_95
        cvar_95_values = [v for v in final_values if v <= var_95]
        stats.cvar_95 = np.mean(cvar_95_values) if cvar_95_values else var_95
        
        var_99 = stats.var_99
        cvar_99_values = [v for v in final_values if v <= var_99]
        stats.cvar_99 = np.mean(cvar_99_values) if cvar_99_values else var_99
        
        # Expected shortfall
        stats.expected_shortfall = stats.cvar_95
        
        # Percentiles
        percentiles = {}
        for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
            percentiles[f'p{p}'] = np.percentile(final_values, p)
        
        # Confidence intervals
        confidence_intervals = {
            '90%': (np.percentile(final_values, 5), np.percentile(final_values, 95)),
            '95%': (np.percentile(final_values, 2.5), np.percentile(final_values, 97.5)),
            '99%': (np.percentile(final_values, 0.5), np.percentile(final_values, 99.5))
        }
        
        # Update result
        result.statistics = stats.__dict__
        result.percentiles = percentiles
        result.confidence_intervals = confidence_intervals
        
        return result
    
    async def _calculate_probability_metrics(
        self,
        result: MonteCarloResult,
        initial_value: float
    ) -> MonteCarloResult:
        """Calculate probability metrics"""
        final_values = result.final_values
        
        if not final_values:
            return result
        
        probability_metrics = {}
        
        # Probability of profit
        probability_metrics['prob_profit'] = sum(1 for v in final_values if v > initial_value) / len(final_values)
        
        # Probability of loss
        probability_metrics['prob_loss'] = sum(1 for v in final_values if v < initial_value) / len(final_values)
        
        # Probability of >10% return
        probability_metrics['prob_return_gt_10'] = sum(1 for v in final_values if v > initial_value * 1.1) / len(final_values)
        
        # Probability of >20% return
        probability_metrics['prob_return_gt_20'] = sum(1 for v in final_values if v > initial_value * 1.2) / len(final_values)
        
        # Probability of >50% return
        probability_metrics['prob_return_gt_50'] = sum(1 for v in final_values if v > initial_value * 1.5) / len(final_values)
        
        # Probability of >100% return
        probability_metrics['prob_return_gt_100'] = sum(1 for v in final_values if v > initial_value * 2) / len(final_values)
        
        # Probability of >10% loss
        probability_metrics['prob_loss_gt_10'] = sum(1 for v in final_values if v < initial_value * 0.9) / len(final_values)
        
        # Probability of >20% loss
        probability_metrics['prob_loss_gt_20'] = sum(1 for v in final_values if v < initial_value * 0.8) / len(final_values)
        
        # Probability of >50% loss
        probability_metrics['prob_loss_gt_50'] = sum(1 for v in final_values if v < initial_value * 0.5) / len(final_values)
        
        result.probability_metrics = probability_metrics
        
        return result
    
    async def _calculate_risk_metrics(
        self,
        result: MonteCarloResult
    ) -> MonteCarloResult:
        """Calculate risk metrics"""
        final_values = result.final_values
        
        if not final_values:
            return result
        
        risk_metrics = {}
        
        # VaR (absolute)
        risk_metrics['var_95_abs'] = result.statistics.get('var_95', 0)
        risk_metrics['var_99_abs'] = result.statistics.get('var_99', 0)
        
        # CVaR (absolute)
        risk_metrics['cvar_95_abs'] = result.statistics.get('cvar_95', 0)
        risk_metrics['cvar_99_abs'] = result.statistics.get('cvar_99', 0)
        
        # Expected shortfall (absolute)
        risk_metrics['expected_shortfall_abs'] = result.statistics.get('expected_shortfall', 0)
        
        # VaR (%)
        initial_value = result.initial_value
        risk_metrics['var_95_pct'] = risk_metrics['var_95_abs'] / initial_value if initial_value != 0 else 0
        risk_metrics['var_99_pct'] = risk_metrics['var_99_abs'] / initial_value if initial_value != 0 else 0
        
        # CVaR (%)
        risk_metrics['cvar_95_pct'] = risk_metrics['cvar_95_abs'] / initial_value if initial_value != 0 else 0
        risk_metrics['cvar_99_pct'] = risk_metrics['cvar_99_abs'] / initial_value if initial_value != 0 else 0
        
        # Expected shortfall (%)
        risk_metrics['expected_shortfall_pct'] = risk_metrics['expected_shortfall_abs'] / initial_value if initial_value != 0 else 0
        
        # Maximum loss
        risk_metrics['max_loss'] = result.statistics.get('min', 0)
        
        # Maximum loss (%)
        risk_metrics['max_loss_pct'] = risk_metrics['max_loss'] / initial_value if initial_value != 0 else 0
        
        result.risk_metrics = risk_metrics
        
        return result
    
    # ========================================
    # HELPERS
    # ========================================
    
    def _calculate_returns_from_prices(self, prices: List[float]) -> List[float]:
        """Calculate returns from price series"""
        if len(prices) < 2:
            return []
        
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] != 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
            else:
                returns.append(0.0)
        
        return returns
    
    def _generate_cache_key(
        self,
        returns: Optional[List[float]],
        prices: Optional[List[float]],
        initial_value: float,
        method: SimulationMethod,
        iterations: int,
        simulation_days: int
    ) -> str:
        """Generate cache key"""
        import hashlib
        
        key_data = {
            'returns_len': len(returns) if returns else 0,
            'prices_len': len(prices) if prices else 0,
            'initial_value': initial_value,
            'method': method.value,
            'iterations': iterations,
            'simulation_days': simulation_days,
            'config': self.config.dict()
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached_result(
        self,
        key: str
    ) -> Optional[MonteCarloResult]:
        """Get cached result"""
        if key in self._cache:
            result, timestamp = self._cache[key]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < self.config.cache_ttl:
                return result
        
        # Check Redis cache
        try:
            cached = self.redis.get(f"monte_carlo:{key}")
            if cached:
                data = json.loads(cached)
                return MonteCarloResult(**data)
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def _set_cached_result(
        self,
        key: str,
        result: MonteCarloResult
    ) -> None:
        """Cache result"""
        self._cache[key] = (result, datetime.utcnow())
        
        # Store in Redis
        try:
            self.redis.setex(
                f"monte_carlo:{key}",
                self.config.cache_ttl,
                json.dumps(result.__dict__, default=str)
            )
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
    
    # ========================================
    # VISUALIZATION
    # ========================================
    
    async def create_charts(
        self,
        result: MonteCarloResult,
        show_individual_paths: bool = False
    ) -> Dict[str, str]:
        """
        Create visual charts for Monte Carlo results.
        
        Args:
            result: Monte Carlo result
            show_individual_paths: Show individual paths
            
        Returns:
            Dict[str, str]: Chart data URLs
        """
        charts = {}
        
        # Distribution chart
        fig1 = go.Figure()
        fig1.add_trace(go.Histogram(
            x=result.final_values,
            nbinsx=50,
            name='Distribution',
            opacity=0.7,
            marker_color='blue'
        ))
        fig1.add_vline(
            x=result.initial_value,
            line_dash="dash",
            line_color="green",
            annotation_text="Initial Value",
            annotation_position="top"
        )
        fig1.update_layout(
            title='Distribution of Final Values',
            xaxis_title='Final Value',
            yaxis_title='Frequency',
            template='plotly_dark' if settings.THEME == 'dark' else 'plotly_white'
        )
        charts['distribution'] = fig1.to_html()
        
        # Paths chart
        if show_individual_paths and result.paths:
            fig2 = go.Figure()
            
            # Show only first 100 paths for visibility
            paths_to_show = min(100, len(result.paths))
            
            for i in range(paths_to_show):
                path = result.paths[i]
                fig2.add_trace(go.Scatter(
                    y=path,
                    mode='lines',
                    name=f'Path {i+1}',
                    line=dict(width=0.5),
                    opacity=0.3
                ))
            
            # Add mean path
            if result.paths:
                mean_path = np.mean(result.paths, axis=0)
                fig2.add_trace(go.Scatter(
                    y=mean_path,
                    mode='lines',
                    name='Mean Path',
                    line=dict(color='red', width=2)
                ))
            
            fig2.update_layout(
                title='Simulation Paths',
                xaxis_title='Time',
                yaxis_title='Value',
                template='plotly_dark' if settings.THEME == 'dark' else 'plotly_white',
                showlegend=False
            )
            charts['paths'] = fig2.to_html()
        
        # Percentile chart
        if result.percentiles:
            fig3 = go.Figure()
            
            percentiles = [5, 25, 50, 75, 95]
            colors = ['rgba(255,0,0,0.3)', 'rgba(255,165,0,0.3)', 'rgba(0,0,255,0.3)', 'rgba(255,165,0,0.3)', 'rgba(255,0,0,0.3)']
            
            for p, color in zip(percentiles, colors):
                values = [result.percentiles.get(f'p{p}', 0) for _ in range(len(result.paths[0]) if result.paths else 1)]
                fig3.add_trace(go.Scatter(
                    y=values,
                    mode='lines',
                    name=f'{p}th Percentile',
                    line=dict(color=color, width=1),
                    opacity=0.7
                ))
            
            fig3.update_layout(
                title='Percentile Bands',
                xaxis_title='Time',
                yaxis_title='Value',
                template='plotly_dark' if settings.THEME == 'dark' else 'plotly_white'
            )
            charts['percentiles'] = fig3.to_html()
        
        return charts
    
    # ========================================
    # EXPORT
    # ========================================
    
    async def export_results(
        self,
        result: MonteCarloResult,
        format: str = 'json'
    ) -> str:
        """
        Export simulation results.
        
        Args:
            result: Monte Carlo result
            format: Export format ('json', 'csv')
            
        Returns:
            str: Exported data
        """
        if format == 'json':
            return json.dumps(result.__dict__, default=str, indent=2)
        elif format == 'csv':
            return self._export_csv(result)
        else:
            raise MonteCarloError(f"Unsupported format: {format}")
    
    def _export_csv(self, result: MonteCarloResult) -> str:
        """Export as CSV"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Iteration', 'Final_Value'])
        
        # Write data
        for i, value in enumerate(result.final_values):
            writer.writerow([i+1, value])
        
        # Write statistics
        writer.writerow([])
        writer.writerow(['Statistic', 'Value'])
        for key, value in result.statistics.items():
            writer.writerow([key, value])
        
        return output.getvalue()
    
    # ========================================
    # PORTFOLIO SIMULATION
    # ========================================
    
    async def simulate_portfolio(
        self,
        assets: List[Dict[str, Any]],
        weights: List[float],
        initial_value: float = 100000.0,
        iterations: Optional[int] = None,
        simulation_days: Optional[int] = None
    ) -> MonteCarloResult:
        """
        Simulate a portfolio of multiple assets.
        
        Args:
            assets: List of asset data with returns
            weights: Asset weights
            initial_value: Initial portfolio value
            iterations: Number of iterations
            simulation_days: Simulation days
            
        Returns:
            MonteCarloResult: Simulation result
        """
        # Validate inputs
        if len(assets) != len(weights):
            raise MonteCarloError("Assets and weights length mismatch")
        
        if sum(weights) != 1.0:
            # Normalize weights
            weights = np.array(weights) / np.sum(weights)
        
        # Extract returns
        asset_returns = []
        for asset in assets:
            if 'returns' in asset:
                asset_returns.append(asset['returns'])
            elif 'prices' in asset:
                returns = self._calculate_returns_from_prices(asset['prices'])
                asset_returns.append(returns)
            else:
                raise MonteCarloError(f"Asset {asset.get('name', 'unknown')} has no returns or prices")
        
        # Calculate portfolio returns
        min_len = min(len(r) for r in asset_returns)
        portfolio_returns = []
        
        for i in range(min_len):
            ret = sum(weights[j] * asset_returns[j][i] for j in range(len(assets)))
            portfolio_returns.append(ret)
        
        # Run simulation
        result = await self.simulate(
            returns=portfolio_returns,
            initial_value=initial_value,
            iterations=iterations,
            simulation_days=simulation_days
        )
        
        # Add portfolio metadata
        result.metadata['portfolio'] = {
            'assets': [a.get('name', f'Asset_{i}') for i, a in enumerate(assets)],
            'weights': weights.tolist(),
            'num_assets': len(assets)
        }
        
        return result
    
    # ========================================
    # STRESS TEST
    # ========================================
    
    async def run_stress_test(
        self,
        returns: List[float],
        scenarios: List[Dict[str, Any]],
        initial_value: float = 100000.0
    ) -> Dict[str, MonteCarloResult]:
        """
        Run stress test scenarios.
        
        Args:
            returns: Historical returns
            scenarios: List of stress scenarios
            initial_value: Initial value
            
        Returns:
            Dict[str, MonteCarloResult]: Results by scenario
        """
        results = {}
        
        for scenario in scenarios:
            name = scenario.get('name', 'Unnamed')
            
            # Apply scenario modification
            modified_returns = self._apply_scenario(returns, scenario)
            
            result = await self.simulate(
                returns=modified_returns,
                initial_value=initial_value,
                iterations=self.config.iterations
            )
            
            results[name] = result
        
        return results
    
    def _apply_scenario(
        self,
        returns: List[float],
        scenario: Dict[str, Any]
    ) -> List[float]:
        """Apply stress scenario to returns"""
        modified_returns = returns.copy()
        
        scenario_type = scenario.get('type', '')
        
        if scenario_type == 'market_crash':
            # Apply sudden drop
            drop = scenario.get('drop', 0.3)
            crash_point = len(modified_returns) // 2
            modified_returns[crash_point:] = [r - drop for r in modified_returns[crash_point:]]
        
        elif scenario_type == 'flash_crash':
            # Apply temporary drop
            drop = scenario.get('drop', 0.5)
            flash_point = len(modified_returns) // 2
            flash_duration = scenario.get('duration', 5)
            for i in range(flash_point, min(flash_point + flash_duration, len(modified_returns))):
                modified_returns[i] -= drop
        
        elif scenario_type == 'volatility_shock':
            # Increase volatility
            multiplier = scenario.get('multiplier', 2.0)
            for i in range(len(modified_returns)):
                modified_returns[i] *= multiplier
        
        elif scenario_type == 'gradual_decline':
            # Gradual decline
            drop = scenario.get('drop', 0.2)
            duration = scenario.get('duration', 30)
            start_idx = len(modified_returns) - duration
            for i in range(start_idx, len(modified_returns)):
                decline = drop * (i - start_idx) / duration
                modified_returns[i] -= decline
        
        return modified_returns
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the simulator"""
        self._running = True
        self.logger.info("MonteCarloSimulator started")
    
    async def stop(self) -> None:
        """Stop the simulator"""
        self._running = False
        self.logger.info("MonteCarloSimulator stopped")
    
    async def health_check(self) -> bool:
        """Check simulator health"""
        try:
            self.redis.ping()
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False


# ========================================
# DEPENDENCY INJECTION
# ========================================

_monte_carlo: Optional[MonteCarloSimulator] = None


def get_monte_carlo() -> MonteCarloSimulator:
    """Get singleton instance of MonteCarloSimulator"""
    global _monte_carlo
    if _monte_carlo is None:
        _monte_carlo = MonteCarloSimulator()
    return _monte_carlo


def reset_monte_carlo() -> None:
    """Reset the Monte Carlo simulator (for testing)"""
    global _monte_carlo
    if _monte_carlo:
        asyncio.create_task(_monte_carlo.stop())
    _monte_carlo = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'MonteCarloSimulator',
    'MonteCarloConfig',
    'SimulationMethod',
    'DistributionType',
    'MonteCarloResult',
    'MonteCarloStats',
    'get_monte_carlo',
    'reset_monte_carlo'
]

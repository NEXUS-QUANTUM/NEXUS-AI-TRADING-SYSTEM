# trading/bots/hedge_bot/hedge_bot_data_simulate.py

import asyncio
import logging
import time
import math
import random
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger(__name__)


class SimulationType(str, Enum):
    MONTE_CARLO = "monte_carlo"
    HISTORICAL = "historical"
    BOOTSTRAP = "bootstrap"
    MARKOV = "markov"
    GBM = "geometric_brownian_motion"
    HESTON = "heston"
    SABR = "sabr"
    JUMP_DIFFUSION = "jump_diffusion"
    VASICEK = "vasicek"
    COX_INGERSOLL_ROSS = "cox_ingersoll_ross"
    BLACK_SCHOLES = "black_scholes"
    BINOMIAL = "binomial"
    TRINOMIAL = "trinomial"
    MONTE_CARLO_OPTION = "monte_carlo_option"
    MONTE_CARLO_STRESS = "monte_carlo_stress"


class SimulationOutput(str, Enum):
    PRICES = "prices"
    RETURNS = "returns"
    VOLATILITY = "volatility"
    VAR = "var"
    CVAR = "cvar"
    OPTION_PRICE = "option_price"
    GREEKS = "greeks"
    PORTFOLIO = "portfolio"
    TRADES = "trades"
    METRICS = "metrics"
    FULL = "full"


@dataclass
class SimulationConfig:
    id: str
    type: SimulationType
    symbol: str
    start_price: float
    end_time: float
    time_steps: int
    num_paths: int = 1000
    volatility: float = 0.2
    drift: float = 0.05
    risk_free_rate: float = 0.02
    dividend_yield: float = 0.0
    jump_intensity: float = 0.0
    jump_mean: float = 0.0
    jump_std: float = 0.0
    mean_reversion: float = 0.0
    long_term_mean: float = 0.0
    correlation: float = 0.0
    seed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationResult:
    id: str
    config_id: str
    type: SimulationType
    paths: np.ndarray
    final_prices: np.ndarray
    mean_final: float
    std_final: float
    min_final: float
    max_final: float
    percentiles: Dict[float, float]
    execution_time: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationMetrics:
    id: str
    result_id: str
    mean_return: float
    std_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    expected_shortfall: float
    max_drawdown: float
    recovery_factor: float
    timestamp: float = field(default_factory=time.time)


class DataSimulator:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._configs: Dict[str, SimulationConfig] = {}
        self._results: Dict[str, SimulationResult] = {}
        self._metrics: Dict[str, SimulationMetrics] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_simulators()

    def _initialize_simulators(self) -> None:
        pass

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_config(
        self,
        type: SimulationType,
        symbol: str,
        start_price: float,
        end_time: float,
        time_steps: int,
        num_paths: int = 1000,
        volatility: float = 0.2,
        drift: float = 0.05,
        risk_free_rate: float = 0.02,
        dividend_yield: float = 0.0,
        jump_intensity: float = 0.0,
        jump_mean: float = 0.0,
        jump_std: float = 0.0,
        mean_reversion: float = 0.0,
        long_term_mean: float = 0.0,
        correlation: float = 0.0,
        seed: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SimulationConfig:
        async with self._lock:
            config_id = hashlib.md5(f"{type.value}_{symbol}_{time.time()}".encode()).hexdigest()
            
            config = SimulationConfig(
                id=config_id,
                type=type,
                symbol=symbol,
                start_price=start_price,
                end_time=end_time,
                time_steps=time_steps,
                num_paths=num_paths,
                volatility=volatility,
                drift=drift,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
                jump_intensity=jump_intensity,
                jump_mean=jump_mean,
                jump_std=jump_std,
                mean_reversion=mean_reversion,
                long_term_mean=long_term_mean,
                correlation=correlation,
                seed=seed,
                metadata=metadata or {}
            )
            
            self._configs[config_id] = config
            return config

    async def simulate(self, config_id: str) -> Optional[SimulationResult]:
        async with self._lock:
            if config_id not in self._configs:
                return None
            
            config = self._configs[config_id]
            
            if config.seed is not None:
                np.random.seed(config.seed)
                random.seed(config.seed)
            
            start_time = time.time()
            
            paths = await self._run_simulation(config)
            
            execution_time = time.time() - start_time
            
            final_prices = paths[:, -1]
            
            result = SimulationResult(
                id=hashlib.md5(f"{config_id}_{time.time()}".encode()).hexdigest(),
                config_id=config_id,
                type=config.type,
                paths=paths,
                final_prices=final_prices,
                mean_final=np.mean(final_prices),
                std_final=np.std(final_prices),
                min_final=np.min(final_prices),
                max_final=np.max(final_prices),
                percentiles={
                    0.01: np.percentile(final_prices, 1),
                    0.05: np.percentile(final_prices, 5),
                    0.25: np.percentile(final_prices, 25),
                    0.50: np.percentile(final_prices, 50),
                    0.75: np.percentile(final_prices, 75),
                    0.95: np.percentile(final_prices, 95),
                    0.99: np.percentile(final_prices, 99)
                },
                execution_time=execution_time,
                metadata=config.metadata
            )
            
            self._results[result.id] = result
            
            metrics = await self._compute_metrics(result)
            if metrics:
                self._metrics[metrics.id] = metrics
                result.metadata["metrics_id"] = metrics.id
            
            await self._notify_observers("simulation_completed", result)
            return result

    async def _run_simulation(self, config: SimulationConfig) -> np.ndarray:
        if config.type == SimulationType.GBM:
            return await self._simulate_gbm(config)
        elif config.type == SimulationType.HESTON:
            return await self._simulate_heston(config)
        elif config.type == SimulationType.JUMP_DIFFUSION:
            return await self._simulate_jump_diffusion(config)
        elif config.type == SimulationType.VASICEK:
            return await self._simulate_vasicek(config)
        elif config.type == SimulationType.COX_INGERSOLL_ROSS:
            return await self._simulate_cir(config)
        elif config.type == SimulationType.MONTE_CARLO:
            return await self._simulate_monte_carlo(config)
        elif config.type == SimulationType.BINOMIAL:
            return await self._simulate_binomial(config)
        elif config.type == SimulationType.TRINOMIAL:
            return await self._simulate_trinomial(config)
        elif config.type == SimulationType.BOOTSTRAP:
            return await self._simulate_bootstrap(config)
        elif config.type == SimulationType.HISTORICAL:
            return await self._simulate_historical(config)
        elif config.type == SimulationType.MARKOV:
            return await self._simulate_markov(config)
        else:
            return await self._simulate_gbm(config)

    async def _simulate_gbm(self, config: SimulationConfig) -> np.ndarray:
        dt = config.end_time / config.time_steps
        n = config.num_paths
        m = config.time_steps + 1
        
        paths = np.zeros((n, m))
        paths[:, 0] = config.start_price
        
        drift = config.drift - config.dividend_yield - 0.5 * config.volatility ** 2
        
        for t in range(1, m):
            z = np.random.normal(0, 1, n)
            paths[:, t] = paths[:, t-1] * np.exp(
                drift * dt + config.volatility * np.sqrt(dt) * z
            )
        
        return paths

    async def _simulate_heston(self, config: SimulationConfig) -> np.ndarray:
        dt = config.end_time / config.time_steps
        n = config.num_paths
        m = config.time_steps + 1
        
        paths = np.zeros((n, m))
        paths[:, 0] = config.start_price
        
        kappa = config.mean_reversion or 2.0
        theta = config.long_term_mean or 0.04
        xi = config.volatility * 0.5
        rho = config.correlation or -0.7
        
        v = np.ones(n) * theta
        
        for t in range(1, m):
            z1 = np.random.normal(0, 1, n)
            z2 = rho * z1 + np.sqrt(1 - rho**2) * np.random.normal(0, 1, n)
            
            v = np.maximum(v + kappa * (theta - v) * dt + xi * np.sqrt(v) * np.sqrt(dt) * z1, 0)
            
            paths[:, t] = paths[:, t-1] * np.exp(
                (config.drift - config.dividend_yield - 0.5 * v) * dt + np.sqrt(v) * np.sqrt(dt) * z2
            )
        
        return paths

    async def _simulate_jump_diffusion(self, config: SimulationConfig) -> np.ndarray:
        dt = config.end_time / config.time_steps
        n = config.num_paths
        m = config.time_steps + 1
        
        paths = np.zeros((n, m))
        paths[:, 0] = config.start_price
        
        lambda_jump = config.jump_intensity or 0.1
        mu_j = config.jump_mean or 0.0
        sigma_j = config.jump_std or 0.1
        
        drift = config.drift - config.dividend_yield - 0.5 * config.volatility ** 2
        
        for t in range(1, m):
            z = np.random.normal(0, 1, n)
            poisson = np.random.poisson(lambda_jump * dt, n)
            jump = np.random.normal(mu_j, sigma_j, n) * poisson
            
            paths[:, t] = paths[:, t-1] * np.exp(
                drift * dt + config.volatility * np.sqrt(dt) * z + jump
            )
        
        return paths

    async def _simulate_vasicek(self, config: SimulationConfig) -> np.ndarray:
        dt = config.end_time / config.time_steps
        n = config.num_paths
        m = config.time_steps + 1
        
        kappa = config.mean_reversion or 0.5
        theta = config.long_term_mean or 0.05
        sigma = config.volatility
        
        rates = np.zeros((n, m))
        rates[:, 0] = config.start_price
        
        for t in range(1, m):
            z = np.random.normal(0, 1, n)
            rates[:, t] = rates[:, t-1] + kappa * (theta - rates[:, t-1]) * dt + sigma * np.sqrt(dt) * z
        
        return rates

    async def _simulate_cir(self, config: SimulationConfig) -> np.ndarray:
        dt = config.end_time / config.time_steps
        n = config.num_paths
        m = config.time_steps + 1
        
        kappa = config.mean_reversion or 0.5
        theta = config.long_term_mean or 0.05
        sigma = config.volatility
        
        rates = np.zeros((n, m))
        rates[:, 0] = config.start_price
        
        for t in range(1, m):
            z = np.random.normal(0, 1, n)
            rates[:, t] = np.maximum(
                rates[:, t-1] + kappa * (theta - rates[:, t-1]) * dt + sigma * np.sqrt(rates[:, t-1]) * np.sqrt(dt) * z,
                0
            )
        
        return rates

    async def _simulate_monte_carlo(self, config: SimulationConfig) -> np.ndarray:
        return await self._simulate_gbm(config)

    async def _simulate_binomial(self, config: SimulationConfig) -> np.ndarray:
        dt = config.end_time / config.time_steps
        n = config.num_paths
        m = config.time_steps + 1
        
        u = np.exp(config.volatility * np.sqrt(dt))
        d = 1 / u
        p = (np.exp((config.drift - config.dividend_yield) * dt) - d) / (u - d)
        
        paths = np.zeros((n, m))
        paths[:, 0] = config.start_price
        
        for path in range(n):
            for t in range(1, m):
                if random.random() < p:
                    paths[path, t] = paths[path, t-1] * u
                else:
                    paths[path, t] = paths[path, t-1] * d
        
        return paths

    async def _simulate_trinomial(self, config: SimulationConfig) -> np.ndarray:
        dt = config.end_time / config.time_steps
        n = config.num_paths
        m = config.time_steps + 1
        
        u = np.exp(config.volatility * np.sqrt(2 * dt))
        d = 1 / u
        
        p_u = ((np.exp((config.drift - config.dividend_yield) * dt / 2) - np.exp(-config.volatility * np.sqrt(dt / 2))) /
               (np.exp(config.volatility * np.sqrt(dt / 2)) - np.exp(-config.volatility * np.sqrt(dt / 2)))) ** 2
        p_d = ((np.exp(config.volatility * np.sqrt(dt / 2)) - np.exp((config.drift - config.dividend_yield) * dt / 2)) /
               (np.exp(config.volatility * np.sqrt(dt / 2)) - np.exp(-config.volatility * np.sqrt(dt / 2)))) ** 2
        p_m = 1 - p_u - p_d
        
        paths = np.zeros((n, m))
        paths[:, 0] = config.start_price
        
        for path in range(n):
            for t in range(1, m):
                r = random.random()
                if r < p_u:
                    paths[path, t] = paths[path, t-1] * u
                elif r < p_u + p_m:
                    paths[path, t] = paths[path, t-1]
                else:
                    paths[path, t] = paths[path, t-1] * d
        
        return paths

    async def _simulate_bootstrap(self, config: SimulationConfig) -> np.ndarray:
        if not hasattr(config, 'historical_data') or config.historical_data is None:
            return await self._simulate_gbm(config)
        
        historical = config.historical_data
        returns = np.diff(np.log(historical))
        
        n = config.num_paths
        m = config.time_steps + 1
        
        paths = np.zeros((n, m))
        paths[:, 0] = config.start_price
        
        for path in range(n):
            sampled_returns = np.random.choice(returns, config.time_steps, replace=True)
            paths[path, 1:] = config.start_price * np.exp(np.cumsum(sampled_returns))
        
        return paths

    async def _simulate_historical(self, config: SimulationConfig) -> np.ndarray:
        if not hasattr(config, 'historical_data') or config.historical_data is None:
            return await self._simulate_gbm(config)
        
        historical = config.historical_data
        
        n = config.num_paths
        m = config.time_steps + 1
        
        if len(historical) < m:
            return await self._simulate_gbm(config)
        
        paths = np.zeros((n, m))
        
        for path in range(n):
            start_idx = random.randint(0, len(historical) - m)
            paths[path] = historical[start_idx:start_idx + m]
        
        return paths

    async def _simulate_markov(self, config: SimulationConfig) -> np.ndarray:
        if not hasattr(config, 'transition_matrix') or config.transition_matrix is None:
            return await self._simulate_gbm(config)
        
        n = config.num_paths
        m = config.time_steps + 1
        
        states = list(config.transition_matrix.keys())
        paths = np.zeros((n, m))
        paths[:, 0] = config.start_price
        
        for path in range(n):
            current_state = random.choice(states)
            for t in range(1, m):
                next_state = np.random.choice(
                    states,
                    p=config.transition_matrix[current_state]
                )
                paths[path, t] = paths[path, t-1] * (1 + next_state)
                current_state = next_state
        
        return paths

    async def _compute_metrics(self, result: SimulationResult) -> Optional[SimulationMetrics]:
        if result.paths.size == 0:
            return None
        
        final_prices = result.final_prices
        returns = (final_prices - result.paths[:, 0]) / result.paths[:, 0]
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        sharpe_ratio = (mean_return - 0.02) / std_return if std_return > 0 else 0
        
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0
        sortino_ratio = (mean_return - 0.02) / downside_std if downside_std > 0 else 0
        
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        
        cvar_95 = np.mean(returns[returns <= var_95]) if len(returns[returns <= var_95]) > 0 else var_95
        cvar_99 = np.mean(returns[returns <= var_99]) if len(returns[returns <= var_99]) > 0 else var_99
        
        max_drawdown = 0
        for path in result.paths:
            peak = path[0]
            for price in path:
                if price > peak:
                    peak = price
                drawdown = (peak - price) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        recovery_factor = (result.mean_final / result.paths[:, 0].mean()) if result.paths[:, 0].mean() > 0 else 1
        
        metrics = SimulationMetrics(
            id=hashlib.md5(f"{result.id}_{time.time()}".encode()).hexdigest(),
            result_id=result.id,
            mean_return=mean_return,
            std_return=std_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=mean_return / max_drawdown if max_drawdown > 0 else 0,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            expected_shortfall=cvar_95,
            max_drawdown=max_drawdown,
            recovery_factor=recovery_factor,
            timestamp=time.time()
        )
        
        return metrics

    async def get_config(self, config_id: str) -> Optional[SimulationConfig]:
        return self._configs.get(config_id)

    async def get_result(self, result_id: str) -> Optional[SimulationResult]:
        return self._results.get(result_id)

    async def get_metrics(self, metrics_id: str) -> Optional[SimulationMetrics]:
        return self._metrics.get(metrics_id)

    async def get_results_by_config(self, config_id: str) -> List[SimulationResult]:
        return [r for r in self._results.values() if r.config_id == config_id]

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "configs": len(self._configs),
            "results": len(self._results),
            "metrics": len(self._metrics),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "SimulationType",
    "SimulationOutput",
    "SimulationConfig",
    "SimulationResult",
    "SimulationMetrics",
    "DataSimulator"
]

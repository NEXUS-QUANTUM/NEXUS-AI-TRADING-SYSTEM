# trading/bots/hedge_bot/hedge_bot_kelly_criterion.py

import asyncio
import logging
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import deque
import scipy.stats as stats
from scipy.optimize import minimize, minimize_scalar
from scipy.special import erf, erfc

logger = logging.getLogger(__name__)


class KellyMethod(str, Enum):
    CLASSIC = "classic"
    FRACTIONAL = "fractional"
    OPTIMAL_F = "optimal_f"
    KELLY_F = "kelly_f"
    VARIANCE_ADJUSTED = "variance_adjusted"
    THIRD_MOMENT = "third_moment"
    KURTOSIS_ADJUSTED = "kurtosis_adjusted"
    KELLY_C = "kelly_c"
    EXPONENTIAL = "exponential"
    LOG_NORMAL = "log_normal"
    BAYESIAN = "bayesian"
    ROBUST = "robust"
    ADAPTIVE = "adaptive"


class BetType(str, Enum):
    WIN_LOSS = "win_loss"
    MULTI_OUTCOME = "multi_outcome"
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    BINARY = "binary"


@dataclass
class KellyResult:
    method: KellyMethod
    bet_type: BetType
    optimal_f: float
    fractional_kelly: float
    fraction: float
    expected_growth: float
    expected_log_growth: float
    risk_of_ruin: float
    confidence_interval: Tuple[float, float]
    probability: float
    odds: float
    edge: float
    standard_error: float
    total_bets: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    current_drawdown: float
    volatility: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeHistory:
    trades: List[Dict[str, Any]]
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    avg_trade: float
    total_pnl: float
    total_win: float
    total_loss: float
    profit_factor: float
    largest_win: float
    largest_loss: float
    consecutive_wins: int
    consecutive_losses: int
    max_consecutive_wins: int
    max_consecutive_losses: int
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    current_drawdown: float
    expected_value: float
    variance: float
    std_dev: float
    skewness: float
    kurtosis: float
    timestamp: float


@dataclass
class MarketConditions:
    volatility: float
    trend_strength: float
    momentum: float
    correlation: float
    liquidity: float
    spread: float
    volume: float
    price_level: float
    support: float
    resistance: float
    regime: str
    timestamp: float


class KellyCriterion:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._history: deque = deque(maxlen=10000)
        self._trade_history: Optional[TradeHistory] = None
        self._market_conditions: Optional[MarketConditions] = None
        self._results_cache: Dict[str, KellyResult] = {}
        self._cache_ttl = 60
        self._last_calculation = 0
        self._default_fraction = 0.25
        self._max_fraction = 0.5
        self._min_fraction = 0.01
        self._risk_of_ruin_threshold = 0.01
        
        self._initialize_default_config()

    def _initialize_default_config(self) -> None:
        self.config.setdefault("fraction", 0.25)
        self.config.setdefault("max_fraction", 0.5)
        self.config.setdefault("min_fraction", 0.01)
        self.config.setdefault("method", KellyMethod.FRACTIONAL)
        self.config.setdefault("risk_free_rate", 0.02)
        self.config.setdefault("confidence_level", 0.95)
        self.config.setdefault("num_simulations", 10000)
        self.config.setdefault("max_drawdown_limit", 0.2)
        self.config.setdefault("min_win_rate", 0.4)

    async def calculate_kelly(
        self,
        trade_history: TradeHistory,
        method: KellyMethod = None,
        fraction: float = None,
        market_conditions: Optional[MarketConditions] = None
    ) -> KellyResult:
        async with self._lock:
            method = method or self.config.get("method", KellyMethod.FRACTIONAL)
            fraction = fraction or self.config.get("fraction", 0.25)
            
            self._trade_history = trade_history
            self._market_conditions = market_conditions
            
            if method == KellyMethod.CLASSIC:
                result = await self._calculate_classic_kelly(trade_history)
            elif method == KellyMethod.FRACTIONAL:
                result = await self._calculate_fractional_kelly(trade_history, fraction)
            elif method == KellyMethod.OPTIMAL_F:
                result = await self._calculate_optimal_f(trade_history)
            elif method == KellyMethod.KELLY_F:
                result = await self._calculate_kelly_f(trade_history)
            elif method == KellyMethod.VARIANCE_ADJUSTED:
                result = await self._calculate_variance_adjusted(trade_history)
            elif method == KellyMethod.THIRD_MOMENT:
                result = await self._calculate_third_moment(trade_history)
            elif method == KellyMethod.KURTOSIS_ADJUSTED:
                result = await self._calculate_kurtosis_adjusted(trade_history)
            elif method == KellyMethod.KELLY_C:
                result = await self._calculate_kelly_c(trade_history)
            elif method == KellyMethod.EXPONENTIAL:
                result = await self._calculate_exponential_kelly(trade_history)
            elif method == KellyMethod.LOG_NORMAL:
                result = await self._calculate_log_normal_kelly(trade_history)
            elif method == KellyMethod.BAYESIAN:
                result = await self._calculate_bayesian_kelly(trade_history)
            elif method == KellyMethod.ROBUST:
                result = await self._calculate_robust_kelly(trade_history)
            elif method == KellyMethod.ADAPTIVE:
                result = await self._calculate_adaptive_kelly(trade_history, market_conditions)
            else:
                result = await self._calculate_classic_kelly(trade_history)
            
            self._results_cache[method.value] = result
            self._last_calculation = time.time()
            
            return result

    async def _calculate_classic_kelly(self, trade_history: TradeHistory) -> KellyResult:
        win_rate = trade_history.win_rate
        avg_win = trade_history.avg_win
        avg_loss = abs(trade_history.avg_loss) if trade_history.avg_loss else 0
        
        if avg_loss == 0:
            avg_loss = 1e-10
        
        odds = avg_win / avg_loss
        p = win_rate
        q = 1 - p
        
        if odds > 0:
            f = (p * odds - q) / odds
        else:
            f = 0
        
        f = max(0, min(f, 1))
        
        expected_growth = p * math.log(1 + f * odds) + q * math.log(1 - f)
        expected_log_growth = expected_growth / (1 if not trade_history.trades else len(trade_history.trades))
        
        risk_of_ruin = self._calculate_risk_of_ruin(f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f)
        
        return self._create_result(
            method=KellyMethod.CLASSIC,
            bet_type=BetType.WIN_LOSS,
            optimal_f=f,
            fractional_kelly=f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f),
            total_bets=trade_history.total_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={"method": "classic"}
        )

    async def _calculate_fractional_kelly(self, trade_history: TradeHistory, fraction: float) -> KellyResult:
        classic_result = await self._calculate_classic_kelly(trade_history)
        
        f = classic_result.optimal_f * fraction
        f = max(0, min(f, 1))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = classic_result.odds
        
        expected_growth = p * math.log(1 + f * odds) + q * math.log(1 - f)
        expected_log_growth = expected_growth / (1 if not trade_history.trades else len(trade_history.trades))
        
        risk_of_ruin = self._calculate_risk_of_ruin(f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f)
        
        return self._create_result(
            method=KellyMethod.FRACTIONAL,
            bet_type=BetType.WIN_LOSS,
            optimal_f=classic_result.optimal_f,
            fractional_kelly=f,
            fraction=fraction,
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={"fraction": fraction}
        )

    async def _calculate_optimal_f(self, trade_history: TradeHistory) -> KellyResult:
        trades = [t.get("pnl", 0) for t in trade_history.trades]
        
        def objective(f):
            if f <= 0 or f >= 1:
                return float('inf')
            
            growth = 0
            for trade in trades:
                if trade > 0:
                    growth += math.log(1 + f * (trade / abs(trade)))
                elif trade < 0:
                    growth += math.log(1 - f)
            return -growth
        
        result = minimize_scalar(objective, bounds=(0.001, 0.999), method='bounded')
        f = result.x if result.success else 0.25
        
        p = trade_history.win_rate
        q = 1 - p
        odds = await self._calculate_odds(trade_history)
        
        expected_growth = p * math.log(1 + f * odds) + q * math.log(1 - f)
        expected_log_growth = expected_growth / (1 if not trade_history.trades else len(trade_history.trades))
        
        risk_of_ruin = self._calculate_risk_of_ruin(f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f)
        
        return self._create_result(
            method=KellyMethod.OPTIMAL_F,
            bet_type=BetType.CONTINUOUS,
            optimal_f=f,
            fractional_kelly=f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={"method": "optimal_f"}
        )

    async def _calculate_kelly_f(self, trade_history: TradeHistory) -> KellyResult:
        trades = [t.get("pnl", 0) for t in trade_history.trades]
        
        if not trades:
            return await self._calculate_classic_kelly(trade_history)
        
        winning_trades = [t for t in trades if t > 0]
        losing_trades = [t for t in trades if t < 0]
        
        if not winning_trades or not losing_trades:
            return await self._calculate_classic_kelly(trade_history)
        
        avg_win = np.mean(winning_trades)
        avg_loss = abs(np.mean(losing_trades))
        
        if avg_loss == 0:
            avg_loss = 1e-10
        
        win_ratio = len(winning_trades) / len(trades)
        loss_ratio = 1 - win_ratio
        
        f = (win_ratio * avg_win - loss_ratio * avg_loss) / (avg_win * avg_loss)
        f = max(0, min(f, 1))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = avg_win / avg_loss
        
        expected_growth = p * math.log(1 + f * odds) + q * math.log(1 - f)
        expected_log_growth = expected_growth / len(trades)
        
        risk_of_ruin = self._calculate_risk_of_ruin(f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f)
        
        return self._create_result(
            method=KellyMethod.KELLY_F,
            bet_type=BetType.CONTINUOUS,
            optimal_f=f,
            fractional_kelly=f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={"method": "kelly_f"}
        )

    async def _calculate_variance_adjusted(self, trade_history: TradeHistory) -> KellyResult:
        classic_result = await self._calculate_classic_kelly(trade_history)
        
        variance = trade_history.variance
        if variance == 0:
            variance = 1e-10
        
        f = classic_result.optimal_f
        adjustment = 1 / (1 + variance / (f ** 2))
        adjusted_f = f * adjustment
        adjusted_f = max(0, min(adjusted_f, 1))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = classic_result.odds
        
        expected_growth = p * math.log(1 + adjusted_f * odds) + q * math.log(1 - adjusted_f)
        expected_log_growth = expected_growth / (1 if not trade_history.trades else len(trade_history.trades))
        
        risk_of_ruin = self._calculate_risk_of_ruin(adjusted_f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, adjusted_f)
        
        return self._create_result(
            method=KellyMethod.VARIANCE_ADJUSTED,
            bet_type=BetType.WIN_LOSS,
            optimal_f=adjusted_f,
            fractional_kelly=adjusted_f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, adjusted_f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={
                "adjustment": adjustment,
                "variance": variance
            }
        )

    async def _calculate_third_moment(self, trade_history: TradeHistory) -> KellyResult:
        trades = [t.get("pnl", 0) for t in trade_history.trades]
        
        if len(trades) < 3:
            return await self._calculate_classic_kelly(trade_history)
        
        skewness = trade_history.skewness
        classic_result = await self._calculate_classic_kelly(trade_history)
        
        f = classic_result.optimal_f
        adjustment = 1 + skewness * f / 3
        adjusted_f = f * max(0.5, min(adjustment, 1.5))
        adjusted_f = max(0, min(adjusted_f, 1))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = classic_result.odds
        
        expected_growth = p * math.log(1 + adjusted_f * odds) + q * math.log(1 - adjusted_f)
        expected_log_growth = expected_growth / len(trades)
        
        risk_of_ruin = self._calculate_risk_of_ruin(adjusted_f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, adjusted_f)
        
        return self._create_result(
            method=KellyMethod.THIRD_MOMENT,
            bet_type=BetType.CONTINUOUS,
            optimal_f=adjusted_f,
            fractional_kelly=adjusted_f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, adjusted_f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={
                "skewness": skewness,
                "adjustment": adjustment
            }
        )

    async def _calculate_kurtosis_adjusted(self, trade_history: TradeHistory) -> KellyResult:
        trades = [t.get("pnl", 0) for t in trade_history.trades]
        
        if len(trades) < 4:
            return await self._calculate_classic_kelly(trade_history)
        
        kurtosis = trade_history.kurtosis
        classic_result = await self._calculate_classic_kelly(trade_history)
        
        f = classic_result.optimal_f
        adjustment = 1 - (kurtosis - 3) * f ** 2 / 12
        adjusted_f = f * max(0.3, min(adjustment, 1.5))
        adjusted_f = max(0, min(adjusted_f, 1))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = classic_result.odds
        
        expected_growth = p * math.log(1 + adjusted_f * odds) + q * math.log(1 - adjusted_f)
        expected_log_growth = expected_growth / len(trades)
        
        risk_of_ruin = self._calculate_risk_of_ruin(adjusted_f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, adjusted_f)
        
        return self._create_result(
            method=KellyMethod.KURTOSIS_ADJUSTED,
            bet_type=BetType.CONTINUOUS,
            optimal_f=adjusted_f,
            fractional_kelly=adjusted_f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, adjusted_f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={
                "kurtosis": kurtosis,
                "adjustment": adjustment
            }
        )

    async def _calculate_kelly_c(self, trade_history: TradeHistory) -> KellyResult:
        trades = [t.get("pnl", 0) for t in trade_history.trades]
        
        if not trades:
            return await self._calculate_classic_kelly(trade_history)
        
        n = len(trades)
        mean = np.mean(trades)
        std = np.std(trades)
        
        if std == 0:
            std = 1e-10
        
        f = mean / (std ** 2)
        f = max(0, min(f, 1))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = await self._calculate_odds(trade_history)
        
        expected_growth = p * math.log(1 + f * odds) + q * math.log(1 - f)
        expected_log_growth = expected_growth / n
        
        risk_of_ruin = self._calculate_risk_of_ruin(f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f)
        
        return self._create_result(
            method=KellyMethod.KELLY_C,
            bet_type=BetType.CONTINUOUS,
            optimal_f=f,
            fractional_kelly=f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={
                "mean": mean,
                "std": std
            }
        )

    async def _calculate_exponential_kelly(self, trade_history: TradeHistory) -> KellyResult:
        trades = [t.get("pnl", 0) for t in trade_history.trades]
        
        if not trades:
            return await self._calculate_classic_kelly(trade_history)
        
        exp_weights = [math.exp(-0.1 * i) for i in range(len(trades))]
        exp_weights = [w / sum(exp_weights) for w in exp_weights]
        
        weighted_win_rate = 0
        weighted_avg_win = 0
        weighted_avg_loss = 0
        total_weighted_win = 0
        total_weighted_loss = 0
        
        for i, trade in enumerate(trades):
            weight = exp_weights[i] if i < len(exp_weights) else 0
            if trade > 0:
                weighted_win_rate += weight
                weighted_avg_win += trade * weight
                total_weighted_win += trade * weight
            elif trade < 0:
                weighted_avg_loss += abs(trade) * weight
                total_weighted_loss += abs(trade) * weight
        
        weighted_win_rate = max(0.01, weighted_win_rate)
        weighted_avg_loss = max(0.0001, weighted_avg_loss)
        weighted_avg_win = max(0.0001, weighted_avg_win / weighted_win_rate) if weighted_win_rate > 0 else 0
        weighted_avg_loss = max(0.0001, weighted_avg_loss / (1 - weighted_win_rate)) if weighted_win_rate < 1 else 0.0001
        
        odds = weighted_avg_win / weighted_avg_loss
        p = weighted_win_rate
        q = 1 - p
        
        f = (p * odds - q) / odds if odds > 0 else 0
        f = max(0, min(f, 1))
        
        expected_growth = p * math.log(1 + f * odds) + q * math.log(1 - f)
        expected_log_growth = expected_growth / len(trades)
        
        risk_of_ruin = self._calculate_risk_of_ruin(f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f)
        
        return self._create_result(
            method=KellyMethod.EXPONENTIAL,
            bet_type=BetType.WIN_LOSS,
            optimal_f=f,
            fractional_kelly=f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={"weighting": "exponential"}
        )

    async def _calculate_log_normal_kelly(self, trade_history: TradeHistory) -> KellyResult:
        trades = [t.get("pnl", 0) for t in trade_history.trades]
        
        if not trades:
            return await self._calculate_classic_kelly(trade_history)
        
        log_returns = [math.log(1 + t / 100) for t in trades if t > -100]
        if not log_returns:
            return await self._calculate_classic_kelly(trade_history)
        
        mu = np.mean(log_returns)
        sigma = np.std(log_returns)
        
        if sigma == 0:
            sigma = 1e-10
        
        f = mu / (sigma ** 2)
        f = max(0, min(f, 1))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = await self._calculate_odds(trade_history)
        
        expected_growth = p * math.log(1 + f * odds) + q * math.log(1 - f)
        expected_log_growth = expected_growth / len(trades)
        
        risk_of_ruin = self._calculate_risk_of_ruin(f, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f)
        
        return self._create_result(
            method=KellyMethod.LOG_NORMAL,
            bet_type=BetType.CONTINUOUS,
            optimal_f=f,
            fractional_kelly=f * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={
                "mu": mu,
                "sigma": sigma
            }
        )

    async def _calculate_bayesian_kelly(self, trade_history: TradeHistory) -> KellyResult:
        classic_result = await self._calculate_classic_kelly(trade_history)
        
        n = trade_history.total_trades
        wins = trade_history.winning_trades
        
        alpha = wins + 1
        beta = n - wins + 1
        
        p_mean = alpha / (alpha + beta)
        p_std = math.sqrt(alpha * beta / ((alpha + beta) ** 2 * (alpha + beta + 1)))
        
        p_lower = stats.beta.ppf(0.025, alpha, beta)
        p_upper = stats.beta.ppf(0.975, alpha, beta)
        
        odds = classic_result.odds
        
        f_mean = (p_mean * odds - (1 - p_mean)) / odds if odds > 0 else 0
        f_lower = (p_lower * odds - (1 - p_lower)) / odds if odds > 0 else 0
        f_upper = (p_upper * odds - (1 - p_upper)) / odds if odds > 0 else 0
        
        f_mean = max(0, min(f_mean, 1))
        f_lower = max(0, min(f_lower, 1))
        f_upper = max(0, min(f_upper, 1))
        
        p = trade_history.win_rate
        q = 1 - p
        
        expected_growth = p * math.log(1 + f_mean * odds) + q * math.log(1 - f_mean)
        expected_log_growth = expected_growth / n
        
        risk_of_ruin = self._calculate_risk_of_ruin(f_mean, p_mean, 1 - p_mean)
        
        confidence_interval = (f_lower, f_upper)
        
        return self._create_result(
            method=KellyMethod.BAYESIAN,
            bet_type=BetType.WIN_LOSS,
            optimal_f=f_mean,
            fractional_kelly=f_mean * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p_mean,
            odds=odds,
            edge=p_mean * odds - (1 - p_mean),
            standard_error=self._calculate_standard_error(trade_history, f_mean),
            total_bets=n,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={
                "alpha": alpha,
                "beta": beta,
                "p_mean": p_mean,
                "p_std": p_std
            }
        )

    async def _calculate_robust_kelly(self, trade_history: TradeHistory) -> KellyResult:
        classic_result = await self._calculate_classic_kelly(trade_history)
        
        f = classic_result.optimal_f
        
        p = trade_history.win_rate
        q = 1 - p
        odds = classic_result.odds
        
        risk_free_rate = self.config.get("risk_free_rate", 0.02)
        
        f_robust = f * math.exp(-trade_history.volatility)
        f_robust = max(0, min(f_robust, 1))
        
        expected_growth = p * math.log(1 + f_robust * odds) + q * math.log(1 - f_robust)
        expected_log_growth = expected_growth / (1 if not trade_history.trades else len(trade_history.trades))
        
        risk_of_ruin = self._calculate_risk_of_ruin(f_robust, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f_robust)
        
        return self._create_result(
            method=KellyMethod.ROBUST,
            bet_type=BetType.WIN_LOSS,
            optimal_f=f_robust,
            fractional_kelly=f_robust * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f_robust),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={"risk_free_rate": risk_free_rate}
        )

    async def _calculate_adaptive_kelly(
        self,
        trade_history: TradeHistory,
        market_conditions: Optional[MarketConditions]
    ) -> KellyResult:
        base_result = await self._calculate_classic_kelly(trade_history)
        f = base_result.optimal_f
        
        if market_conditions:
            volatility_factor = 1 - market_conditions.volatility * 0.5
            trend_factor = 1 + market_conditions.trend_strength * 0.2
            momentum_factor = 1 + abs(market_conditions.momentum) * 0.1
            correlation_factor = 1 - abs(market_conditions.correlation) * 0.3
            
            f_adaptive = f * volatility_factor * trend_factor * momentum_factor * correlation_factor
        else:
            f_adaptive = f * 0.5
        
        f_adaptive = max(self._min_fraction, min(f_adaptive, self._max_fraction))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = base_result.odds
        
        expected_growth = p * math.log(1 + f_adaptive * odds) + q * math.log(1 - f_adaptive)
        expected_log_growth = expected_growth / (1 if not trade_history.trades else len(trade_history.trades))
        
        risk_of_ruin = self._calculate_risk_of_ruin(f_adaptive, p, q)
        
        confidence_interval = self._calculate_confidence_interval(trade_history, f_adaptive)
        
        return self._create_result(
            method=KellyMethod.ADAPTIVE,
            bet_type=BetType.WIN_LOSS,
            optimal_f=f_adaptive,
            fractional_kelly=f_adaptive * self.config.get("fraction", 0.25),
            fraction=self.config.get("fraction", 0.25),
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=p,
            odds=odds,
            edge=p * odds - q,
            standard_error=self._calculate_standard_error(trade_history, f_adaptive),
            total_bets=trade_history.total_trades,
            win_rate=trade_history.win_rate,
            avg_win=trade_history.avg_win,
            avg_loss=trade_history.avg_loss,
            profit_factor=trade_history.profit_factor,
            sharpe_ratio=trade_history.sharpe_ratio,
            sortino_ratio=trade_history.sortino_ratio,
            calmar_ratio=trade_history.calmar_ratio,
            max_drawdown=trade_history.max_drawdown,
            current_drawdown=trade_history.current_drawdown,
            volatility=trade_history.volatility,
            timestamp=time.time(),
            metadata={
                "volatility_factor": 1 - market_conditions.volatility * 0.5 if market_conditions else 0.5,
                "trend_factor": 1 + market_conditions.trend_strength * 0.2 if market_conditions else 1,
                "momentum_factor": 1 + abs(market_conditions.momentum) * 0.1 if market_conditions else 1,
                "correlation_factor": 1 - abs(market_conditions.correlation) * 0.3 if market_conditions else 1
            }
        )

    def _calculate_risk_of_ruin(self, f: float, p: float, q: float) -> float:
        if f >= 1 or p <= 0:
            return 1.0
        
        if q == 0 or p == 1:
            return 0.0
        
        try:
            log_term = (1 - f) / (1 + f * (p / q - 1))
            return log_term ** (1 / f) if log_term > 0 else 1.0
        except:
            return 1.0

    def _calculate_confidence_interval(
        self,
        trade_history: TradeHistory,
        f: float
    ) -> Tuple[float, float]:
        n = trade_history.total_trades
        if n < 2:
            return (max(0, f - 0.1), min(1, f + 0.1))
        
        p = trade_history.win_rate
        q = 1 - p
        odds = max(0.0001, trade_history.avg_win / max(0.0001, abs(trade_history.avg_loss)))
        
        variance = (p * (1 - p) / n) * ((1 + odds) ** 2)
        std_error = math.sqrt(variance)
        
        z_score = stats.norm.ppf(0.975)
        lower = max(0, f - z_score * std_error)
        upper = min(1, f + z_score * std_error)
        
        return (lower, upper)

    def _calculate_standard_error(self, trade_history: TradeHistory, f: float) -> float:
        n = trade_history.total_trades
        if n < 2:
            return 0.0
        
        p = trade_history.win_rate
        q = 1 - p
        odds = max(0.0001, trade_history.avg_win / max(0.0001, abs(trade_history.avg_loss)))
        
        variance = (p * (1 - p) / n) * ((1 + odds) ** 2)
        return math.sqrt(variance)

    async def _calculate_odds(self, trade_history: TradeHistory) -> float:
        if trade_history.avg_loss == 0:
            return 1.0
        return trade_history.avg_win / abs(trade_history.avg_loss) if trade_history.avg_win > 0 else 0

    def _create_result(
        self,
        method: KellyMethod,
        bet_type: BetType,
        optimal_f: float,
        fractional_kelly: float,
        fraction: float,
        expected_growth: float,
        expected_log_growth: float,
        risk_of_ruin: float,
        confidence_interval: Tuple[float, float],
        probability: float,
        odds: float,
        edge: float,
        standard_error: float,
        total_bets: int,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        profit_factor: float,
        sharpe_ratio: float,
        sortino_ratio: float,
        calmar_ratio: float,
        max_drawdown: float,
        current_drawdown: float,
        volatility: float,
        timestamp: float,
        metadata: Dict[str, Any] = None
    ) -> KellyResult:
        return KellyResult(
            method=method,
            bet_type=bet_type,
            optimal_f=optimal_f,
            fractional_kelly=fractional_kelly,
            fraction=fraction,
            expected_growth=expected_growth,
            expected_log_growth=expected_log_growth,
            risk_of_ruin=risk_of_ruin,
            confidence_interval=confidence_interval,
            probability=probability,
            odds=odds,
            edge=edge,
            standard_error=standard_error,
            total_bets=total_bets,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            volatility=volatility,
            timestamp=timestamp,
            metadata=metadata or {}
        )

    async def analyze_trade_history(self, trades: List[Dict[str, Any]]) -> TradeHistory:
        if not trades:
            return TradeHistory(
                trades=[],
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                breakeven_trades=0,
                win_rate=0,
                avg_win=0,
                avg_loss=0,
                avg_trade=0,
                total_pnl=0,
                total_win=0,
                total_loss=0,
                profit_factor=0,
                largest_win=0,
                largest_loss=0,
                consecutive_wins=0,
                consecutive_losses=0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                volatility=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                calmar_ratio=0,
                max_drawdown=0,
                current_drawdown=0,
                expected_value=0,
                variance=0,
                std_dev=0,
                skewness=0,
                kurtosis=0,
                timestamp=time.time()
            )
        
        pnls = [t.get("pnl", 0) for t in trades]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]
        breakeven = [p for p in pnls if p == 0]
        
        total_trades = len(pnls)
        winning_trades = len(winning)
        losing_trades = len(losing)
        breakeven_trades = len(breakeven)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        avg_win = np.mean(winning) if winning else 0
        avg_loss = abs(np.mean(losing)) if losing else 0
        avg_trade = np.mean(pnls) if pnls else 0
        
        total_pnl = sum(pnls)
        total_win = sum(winning) if winning else 0
        total_loss = abs(sum(losing)) if losing else 0
        profit_factor = total_win / total_loss if total_loss > 0 else float('inf')
        
        largest_win = max(winning) if winning else 0
        largest_loss = min(losing) if losing else 0
        
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_win_streak = 0
        current_loss_streak = 0
        
        for pnl in pnls:
            if pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_consecutive_wins = max(max_consecutive_wins, current_win_streak)
            elif pnl < 0:
                current_loss_streak += 1
                current_win_streak = 0
                max_consecutive_losses = max(max_consecutive_losses, current_loss_streak)
            else:
                current_win_streak = 0
                current_loss_streak = 0
        
        consecutive_wins = current_win_streak
        consecutive_losses = current_loss_streak
        
        volatility = np.std(pnls) if pnls else 0
        expected_value = np.mean(pnls) if pnls else 0
        variance = np.var(pnls) if pnls else 0
        std_dev = np.std(pnls) if pnls else 0
        
        skewness = stats.skew(pnls) if len(pnls) > 2 else 0
        kurtosis = stats.kurtosis(pnls) if len(pnls) > 3 else 0
        
        risk_free_rate = self.config.get("risk_free_rate", 0.02)
        
        if volatility > 0:
            sharpe_ratio = (expected_value - risk_free_rate) / volatility
        else:
            sharpe_ratio = 0
        
        downside_returns = [p for p in pnls if p < 0]
        downside_std = np.std(downside_returns) if downside_returns else 0
        if downside_std > 0:
            sortino_ratio = (expected_value - risk_free_rate) / downside_std
        else:
            sortino_ratio = 0
        
        drawdown_series = []
        peak = 0
        max_drawdown = 0
        current_drawdown = 0
        
        for pnl in pnls:
            if pnl > 0:
                peak += pnl
            drawdown = (peak - (peak + pnl)) / peak if peak > 0 else 0
            drawdown_series.append(drawdown)
            max_drawdown = max(max_drawdown, drawdown)
        
        if drawdown_series:
            current_drawdown = drawdown_series[-1] if drawdown_series else 0
        
        if max_drawdown > 0:
            calmar_ratio = (total_pnl / total_trades) / max_drawdown if total_trades > 0 else 0
        else:
            calmar_ratio = 0
        
        return TradeHistory(
            trades=trades,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade=avg_trade,
            total_pnl=total_pnl,
            total_win=total_win,
            total_loss=total_loss,
            profit_factor=profit_factor,
            largest_win=largest_win,
            largest_loss=largest_loss,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            expected_value=expected_value,
            variance=variance,
            std_dev=std_dev,
            skewness=skewness,
            kurtosis=kurtosis,
            timestamp=time.time()
        )

    async def get_optimal_position_size(
        self,
        capital: float,
        kelly_result: KellyResult,
        max_capital_risk: float = 0.02
    ) -> float:
        f = kelly_result.fractional_kelly
        
        if f <= 0:
            return 0
        
        position_size = capital * f
        max_position = capital * max_capital_risk
        
        return min(position_size, max_position)

    async def get_all_methods(
        self,
        trade_history: TradeHistory,
        fraction: float = None
    ) -> Dict[str, KellyResult]:
        methods = list(KellyMethod)
        results = {}
        
        for method in methods:
            try:
                result = await self.calculate_kelly(
                    trade_history,
                    method=method,
                    fraction=fraction or self.config.get("fraction", 0.25)
                )
                results[method.value] = result
            except Exception as e:
                logger.error(f"Error calculating {method}: {e}")
                results[method.value] = None
        
        return results

    async def get_best_method(
        self,
        trade_history: TradeHistory,
        metric: str = "sharpe_ratio"
    ) -> Tuple[KellyMethod, KellyResult]:
        results = await self.get_all_methods(trade_history)
        
        best_method = None
        best_value = -float('inf')
        
        for method, result in results.items():
            if result is None:
                continue
            
            if metric == "sharpe_ratio":
                value = result.sharpe_ratio
            elif metric == "sortino_ratio":
                value = result.sortino_ratio
            elif metric == "calmar_ratio":
                value = result.calmar_ratio
            elif metric == "expected_growth":
                value = result.expected_growth
            elif metric == "profit_factor":
                value = result.profit_factor
            elif metric == "win_rate":
                value = result.win_rate
            elif metric == "risk_of_ruin":
                value = -result.risk_of_ruin
            else:
                value = result.sharpe_ratio
            
            if value > best_value:
                best_value = value
                best_method = method
        
        if best_method:
            return (KellyMethod(best_method), results[best_method])
        else:
            return (KellyMethod.FRACTIONAL, results.get("fractional", None))

    def clear_cache(self) -> None:
        self._results_cache.clear()
        self._last_calculation = 0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "cache_size": len(self._results_cache),
            "cache_ttl": self._cache_ttl,
            "last_calculation": self._last_calculation,
            "default_fraction": self._default_fraction,
            "max_fraction": self._max_fraction,
            "min_fraction": self._min_fraction,
            "risk_of_ruin_threshold": self._risk_of_ruin_threshold,
            "history_size": len(self._history),
            "methods": [m.value for m in KellyMethod],
            "config": self.config
        }


__all__ = [
    "KellyMethod",
    "BetType",
    "KellyResult",
    "TradeHistory",
    "MarketConditions",
    "KellyCriterion"
]

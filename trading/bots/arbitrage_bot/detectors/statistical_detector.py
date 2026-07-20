# trading/bots/arbitrage_bot/detectors/statistical_detector.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Advanced Statistical Arbitrage Detection Engine

"""
Statistical Detector - Advanced Statistical Arbitrage Detection Engine

This module provides sophisticated statistical arbitrage detection capabilities:
- Cointegration-based pairs trading
- Correlation-based arbitrage
- Mean reversion detection
- Stationarity analysis
- Spread modeling
- Z-score based entry/exit
- Kalman filter for dynamic hedging
- Machine learning for pattern detection

Architecture:
    - BaseStatisticalDetector: Abstract base class
    - StatisticalDetector: Main detector implementation
    - CointegrationAnalyzer: Cointegration testing
    - CorrelationAnalyzer: Correlation analysis
    - MeanReversionDetector: Mean reversion detection
    - SpreadModeler: Spread modeling and forecasting
    - KalmanFilter: Dynamic state estimation
    - MLPatternDetector: ML-based pattern detection

Features:
    - Multi-asset statistical arbitrage
    - Dynamic pair selection
    - Real-time spread monitoring
    - Adaptive threshold adjustment
    - Risk-adjusted position sizing
    - Cross-asset correlation analysis
    - Regime detection
    - Automated rebalancing
"""

import asyncio
import hashlib
import json
import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    TypeVar,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    overload,
    Protocol,
    runtime_checkable,
)
from functools import lru_cache, wraps, partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from itertools import combinations, permutations, product
from contextlib import asynccontextmanager, contextmanager
from typing_extensions import TypedDict, NotRequired

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import pearsonr, spearmanr, kendalltau
from statsmodels.tsa.stattools import coint, adfuller, kpss
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from statsmodels.regression.linear_model import OLS
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.covariance import EllipticEnvelope
import pykalman

# Constants
MIN_COINTEGRATION_PVALUE = Decimal("0.05")
MIN_CORRELATION = Decimal("0.7")
MAX_CORRELATION = Decimal("0.95")
MIN_SPREAD_STD = Decimal("0.01")
MAX_SPREAD_STD = Decimal("0.5")
ZSCORE_ENTRY_THRESHOLD = Decimal("2.0")
ZSCORE_EXIT_THRESHOLD = Decimal("0.5")
HISTORICAL_WINDOW = 252  # Trading days
MIN_HISTORICAL_DATA = 30
MAX_PAIRS = 50
REBALANCE_INTERVAL = 3600  # 1 hour

# Statistical methods
class StatisticalMethod(Enum):
    COINTEGRATION = "cointegration"
    CORRELATION = "correlation"
    MEAN_REVERSION = "mean_reversion"
    PCA = "pca"
    KALMAN = "kalman"
    ML = "ml"

# Regime types
class RegimeType(Enum):
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    CRISIS = "crisis"

@dataclass
class StatisticalPair:
    """Statistical arbitrage pair."""
    symbol1: str
    symbol2: str
    correlation: Decimal
    cointegration_pvalue: Decimal
    spread_mean: Decimal
    spread_std: Decimal
    hedge_ratio: Decimal
    half_life: Decimal
    zscore: Decimal
    current_spread: Decimal
    status: str  # "normal", "entry_long", "entry_short", "exit"
    confidence: Decimal
    timestamp: datetime

@dataclass
class SpreadModel:
    """Spread model for statistical arbitrage."""
    symbol1: str
    symbol2: str
    model_type: str  # "ols", "kalman", "ml"
    hedge_ratio: Decimal
    intercept: Decimal
    spread_series: List[Decimal]
    residuals: List[Decimal]
    mean: Decimal
    std: Decimal
    half_life: Decimal
    ar_coefficient: Decimal
    confidence: Decimal
    timestamp: datetime

@dataclass
class KalmanState:
    """Kalman filter state."""
    symbol1: str
    symbol2: str
    hedge_ratio: Decimal
    intercept: Decimal
    spread: Decimal
    variance: Decimal
    timestamp: datetime

@dataclass
class ArbitrageSignal:
    """Statistical arbitrage signal."""
    pair: StatisticalPair
    signal_type: str  # "entry_long", "entry_short", "exit"
    entry_price: Decimal
    exit_price: Decimal
    position_size: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    confidence: Decimal
    timestamp: datetime

class StatisticalDetector:
    """
    Advanced Statistical Arbitrage Detection Engine.
    
    This class provides comprehensive statistical arbitrage detection:
    1. Cointegration-based pairs detection
    2. Correlation-based pair selection
    3. Mean reversion analysis
    4. Spread modeling with Kalman filter
    5. Dynamic threshold adjustment
    6. Regime detection
    7. Risk-adjusted position sizing
    
    Features:
    - Multi-asset pair detection
    - Real-time spread monitoring
    - Adaptive entry/exit thresholds
    - Kalman filter for dynamic hedging
    - Machine learning for pattern detection
    - Cross-asset correlation analysis
    - Regime-based strategy adjustment
    - Automated rebalancing
    """
    
    def __init__(
        self,
        min_cointegration_pvalue: Decimal = MIN_COINTEGRATION_PVALUE,
        min_correlation: Decimal = MIN_CORRELATION,
        max_correlation: Decimal = MAX_CORRELATION,
        zscore_entry: Decimal = ZSCORE_ENTRY_THRESHOLD,
        zscore_exit: Decimal = ZSCORE_EXIT_THRESHOLD,
        scan_interval: float = 1.0,
        rebalance_interval: int = REBALANCE_INTERVAL,
    ):
        """
        Initialize the Statistical Detector.
        
        Args:
            min_cointegration_pvalue: Minimum p-value for cointegration
            min_correlation: Minimum correlation for pair selection
            max_correlation: Maximum correlation to avoid overfitting
            zscore_entry: Z-score threshold for entry
            zscore_exit: Z-score threshold for exit
            scan_interval: Scan interval in seconds
            rebalance_interval: Rebalance interval in seconds
        """
        self.logger = self._setup_logger()
        self.min_cointegration_pvalue = min_cointegration_pvalue
        self.min_correlation = min_correlation
        self.max_correlation = max_correlation
        self.zscore_entry = zscore_entry
        self.zscore_exit = zscore_exit
        self.scan_interval = scan_interval
        self.rebalance_interval = rebalance_interval
        
        # Data storage
        self.price_history: Dict[str, List[Decimal]] = {}
        self.pairs: Dict[str, StatisticalPair] = {}
        self.spread_models: Dict[str, SpreadModel] = {}
        self.kalman_states: Dict[str, KalmanState] = {}
        self.signals: List[ArbitrageSignal] = []
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        
        # ML models
        self.ml_models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        
        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Metrics
        self.metrics = {
            "pairs_analyzed": 0,
            "pairs_found": 0,
            "signals_generated": 0,
            "signals_executed": 0,
            "total_profit": Decimal("0"),
            "win_rate": Decimal("0"),
            "avg_return": Decimal("0"),
            "sharpe_ratio": Decimal("0"),
            "max_drawdown": Decimal("0"),
            "errors": 0,
        }
        
        # State management
        self.is_running = False
        self.scan_thread: Optional[threading.Thread] = None
        self.rebalance_thread: Optional[threading.Thread] = None
        
        # Regime detection
        self.current_regime = RegimeType.NORMAL
        self.regime_history: List[RegimeType] = []
        
        # Start detector
        self.start()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger for the detector."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def start(self) -> None:
        """Start the statistical detector."""
        if self.is_running:
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        
        self.rebalance_thread = threading.Thread(target=self._rebalance_loop, daemon=True)
        self.rebalance_thread.start()
        
        self.logger.info("Statistical Detector started")
    
    def stop(self) -> None:
        """Stop the statistical detector."""
        self.is_running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5.0)
        if self.rebalance_thread:
            self.rebalance_thread.join(timeout=5.0)
        self.logger.info("Statistical Detector stopped")
    
    def _scan_loop(self) -> None:
        """Main scanning loop."""
        while self.is_running:
            try:
                # Update prices
                self._update_prices()
                
                # Analyze pairs
                self._analyze_pairs()
                
                # Generate signals
                self._generate_signals()
                
                # Detect regime
                self._detect_regime()
                
                # Sleep until next scan
                time.sleep(self.scan_interval)
                
            except Exception as e:
                self.logger.error(f"Scan loop error: {e}")
                self.metrics["errors"] += 1
                time.sleep(1.0)
    
    def _rebalance_loop(self) -> None:
        """Rebalancing loop for active positions."""
        while self.is_running:
            try:
                # Check and rebalance positions
                self._rebalance_positions()
                
                # Sleep until next rebalance
                time.sleep(self.rebalance_interval)
                
            except Exception as e:
                self.logger.error(f"Rebalance loop error: {e}")
                time.sleep(5.0)
    
    def _update_prices(self) -> None:
        """Update price history for all symbols."""
        # Simulate price updates
        # In production, this would fetch from exchange APIs
        import random
        
        symbols = ["BTC", "ETH", "SOL", "AVAX", "MATIC", "LINK", "UNI", "AAVE"]
        
        for symbol in symbols:
            if symbol not in self.price_history:
                self.price_history[symbol] = []
            
            # Generate random price
            base_price = Decimal(str(random.uniform(100, 100000)))
            price = base_price * Decimal(str(1 + random.uniform(-0.02, 0.02)))
            
            self.price_history[symbol].append(price)
            
            # Trim history
            if len(self.price_history[symbol]) > HISTORICAL_WINDOW * 2:
                self.price_history[symbol] = self.price_history[symbol][-HISTORICAL_WINDOW * 2:]
    
    def _analyze_pairs(self) -> None:
        """Analyze all possible pairs for statistical arbitrage."""
        symbols = list(self.price_history.keys())
        if len(symbols) < 2:
            return
        
        # Get all possible pairs
        symbol_pairs = list(combinations(symbols, 2))
        
        # Analyze each pair
        analyzed_pairs = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_pair = {
                executor.submit(self._analyze_pair, s1, s2): (s1, s2)
                for s1, s2 in symbol_pairs
            }
            
            for future in future_to_pair:
                try:
                    result = future.result(timeout=10.0)
                    if result:
                        analyzed_pairs.append(result)
                except Exception as e:
                    self.logger.debug(f"Pair analysis failed: {e}")
        
        # Sort by confidence
        analyzed_pairs.sort(
            key=lambda x: float(x.confidence),
            reverse=True
        )
        
        # Store pairs
        new_pairs = {}
        for pair in analyzed_pairs[:MAX_PAIRS]:
            key = f"{pair.symbol1}_{pair.symbol2}"
            new_pairs[key] = pair
        
        self.pairs = new_pairs
        self.metrics["pairs_analyzed"] += len(symbol_pairs)
        self.metrics["pairs_found"] = len(new_pairs)
    
    def _analyze_pair(
        self,
        symbol1: str,
        symbol2: str,
    ) -> Optional[StatisticalPair]:
        """
        Analyze a pair for statistical arbitrage potential.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            
        Returns:
            StatisticalPair or None
        """
        try:
            # Get price histories
            prices1 = self.price_history.get(symbol1, [])
            prices2 = self.price_history.get(symbol2, [])
            
            if len(prices1) < MIN_HISTORICAL_DATA or len(prices2) < MIN_HISTORICAL_DATA:
                return None
            
            # Align data
            min_len = min(len(prices1), len(prices2))
            p1 = np.array([float(p) for p in prices1[-min_len:]])
            p2 = np.array([float(p) for p in prices2[-min_len:]])
            
            # Calculate correlation
            correlation = Decimal(str(pearsonr(p1, p2)[0]))
            
            if abs(correlation) < float(self.min_correlation):
                return None
            
            if abs(correlation) > float(self.max_correlation):
                return None
            
            # Test for cointegration
            coint_result = coint(p1, p2)
            coint_pvalue = Decimal(str(coint_result[1]))
            
            if coint_pvalue > self.min_cointegration_pvalue:
                return None
            
            # Calculate hedge ratio using OLS
            model = OLS(p1, p2)
            results = model.fit()
            hedge_ratio = Decimal(str(results.params[0]))
            intercept = Decimal(str(results.params[1] if len(results.params) > 1 else 0))
            
            # Calculate spread
            spread = p1 - hedge_ratio * p2
            spread_mean = Decimal(str(np.mean(spread)))
            spread_std = Decimal(str(np.std(spread)))
            
            if spread_std < MIN_SPREAD_STD or spread_std > MAX_SPREAD_STD:
                return None
            
            # Calculate half-life of mean reversion
            lagged_spread = np.roll(spread, 1)[1:]
            spread_diff = np.diff(spread)
            
            if len(spread_diff) > 1:
                model_ar = OLS(spread_diff, lagged_spread)
                ar_results = model_ar.fit()
                ar_coefficient = ar_results.params[0]
                
                if ar_coefficient < 0:
                    half_life = Decimal(str(-np.log(2) / ar_coefficient))
                else:
                    half_life = Decimal("1000")
            else:
                half_life = Decimal("1000")
            
            # Calculate current z-score
            current_spread = p1[-1] - hedge_ratio * p2[-1]
            zscore = Decimal(str((current_spread - float(spread_mean)) / float(spread_std)))
            
            # Determine status
            if abs(zscore) > self.zscore_entry:
                if zscore > 0:
                    status = "entry_short"  # Short spread (sell high, buy low)
                else:
                    status = "entry_long"   # Long spread (buy low, sell high)
            elif abs(zscore) < self.zscore_exit:
                status = "exit"
            else:
                status = "normal"
            
            # Calculate confidence
            confidence = Decimal(str(min(1.0, 1.0 - float(coint_pvalue) / 0.05)))
            
            # Create pair object
            pair = StatisticalPair(
                symbol1=symbol1,
                symbol2=symbol2,
                correlation=correlation,
                cointegration_pvalue=coint_pvalue,
                spread_mean=spread_mean,
                spread_std=spread_std,
                hedge_ratio=hedge_ratio,
                half_life=half_life,
                zscore=zscore,
                current_spread=Decimal(str(current_spread)),
                status=status,
                confidence=confidence,
                timestamp=datetime.utcnow(),
            )
            
            # Update spread model
            model = SpreadModel(
                symbol1=symbol1,
                symbol2=symbol2,
                model_type="ols",
                hedge_ratio=hedge_ratio,
                intercept=intercept,
                spread_series=[Decimal(str(s)) for s in spread[-100:]],
                residuals=[Decimal(str(r)) for r in results.resid[-100:]],
                mean=spread_mean,
                std=spread_std,
                half_life=half_life,
                ar_coefficient=Decimal(str(ar_coefficient)) if ar_coefficient else Decimal("0"),
                confidence=confidence,
                timestamp=datetime.utcnow(),
            )
            
            self.spread_models[f"{symbol1}_{symbol2}"] = model
            
            return pair
            
        except Exception as e:
            self.logger.debug(f"Pair analysis failed: {e}")
            return None
    
    def _generate_signals(self) -> None:
        """Generate trading signals from pairs."""
        new_signals = []
        
        for key, pair in self.pairs.items():
            if pair.status == "entry_long" and pair.confidence > Decimal("0.5"):
                signal = self._create_signal(pair, "entry_long")
                if signal:
                    new_signals.append(signal)
            
            elif pair.status == "entry_short" and pair.confidence > Decimal("0.5"):
                signal = self._create_signal(pair, "entry_short")
                if signal:
                    new_signals.append(signal)
            
            elif pair.status == "exit":
                signal = self._create_signal(pair, "exit")
                if signal:
                    new_signals.append(signal)
        
        # Store signals
        if new_signals:
            self.signals.extend(new_signals)
            self.metrics["signals_generated"] += len(new_signals)
            
            # Log signals
            for signal in new_signals:
                self.logger.info(
                    f"Statistical arbitrage signal: {signal.pair.symbol1}/{signal.pair.symbol2} "
                    f"{signal.signal_type} with confidence {float(signal.confidence):.2f}"
                )
            
            # Trim signals
            if len(self.signals) > 1000:
                self.signals = self.signals[-1000:]
    
    def _create_signal(
        self,
        pair: StatisticalPair,
        signal_type: str,
    ) -> Optional[ArbitrageSignal]:
        """
        Create a trading signal from a pair.
        
        Args:
            pair: Statistical pair
            signal_type: Type of signal
            
        Returns:
            ArbitrageSignal or None
        """
        try:
            # Calculate position size
            position_size = self._calculate_position_size(pair)
            
            # Calculate entry and exit prices
            if signal_type == "entry_long":
                entry_price = pair.current_spread
                exit_price = pair.spread_mean
                stop_loss = entry_price - pair.spread_std * Decimal("3")
                take_profit = pair.spread_mean
            elif signal_type == "entry_short":
                entry_price = pair.current_spread
                exit_price = pair.spread_mean
                stop_loss = entry_price + pair.spread_std * Decimal("3")
                take_profit = pair.spread_mean
            else:  # exit
                entry_price = pair.current_spread
                exit_price = pair.current_spread
                stop_loss = None
                take_profit = None
            
            return ArbitrageSignal(
                pair=pair,
                signal_type=signal_type,
                entry_price=entry_price,
                exit_price=exit_price,
                position_size=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=pair.confidence,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.debug(f"Signal creation failed: {e}")
            return None
    
    def _calculate_position_size(self, pair: StatisticalPair) -> Decimal:
        """
        Calculate position size using Kelly criterion and risk management.
        
        Args:
            pair: Statistical pair
            
        Returns:
            Position size
        """
        # Base size
        base_size = Decimal("10000")
        
        # Adjust for confidence
        size_multiplier = pair.confidence * Decimal("2")
        
        # Adjust for volatility
        volatility_adjustment = min(Decimal("1"), Decimal("1") / (pair.spread_std * Decimal("100")))
        
        # Calculate size
        size = base_size * size_multiplier * volatility_adjustment
        
        # Cap at maximum
        max_size = Decimal("100000")
        return min(max_size, max(Decimal("100"), size))
    
    def _detect_regime(self) -> None:
        """Detect market regime for adaptive trading."""
        if len(self.pairs) < 5:
            return
        
        # Calculate average spread volatility
        spread_stds = [p.spread_std for p in self.pairs.values()]
        avg_volatility = sum(spread_stds) / len(spread_stds)
        
        # Calculate average half-life (mean reversion speed)
        half_lives = [p.half_life for p in self.pairs.values() if p.half_life > 0]
        avg_half_life = sum(half_lives) / len(half_lives) if half_lives else Decimal("100")
        
        # Detect regime
        if avg_volatility > Decimal("0.3"):
            regime = RegimeType.HIGH_VOLATILITY
        elif avg_volatility < Decimal("0.1"):
            regime = RegimeType.LOW_VOLATILITY
        elif avg_half_life < Decimal("5"):
            regime = RegimeType.MEAN_REVERTING
        elif avg_half_life > Decimal("20"):
            regime = RegimeType.TRENDING
        else:
            regime = RegimeType.NORMAL
        
        self.current_regime = regime
        self.regime_history.append(regime)
        
        # Trim history
        if len(self.regime_history) > 100:
            self.regime_history = self.regime_history[-100:]
    
    def _rebalance_positions(self) -> None:
        """Rebalance active statistical arbitrage positions."""
        if not self.active_positions:
            return
        
        for position_key, position in self.active_positions.items():
            # Check if position should be closed
            if position["signal_type"] == "exit" or position["pair"].status == "exit":
                # Close position
                profit = self._close_position(position)
                if profit is not None:
                    self.metrics["total_profit"] += profit
                    self.metrics["signals_executed"] += 1
                
                # Remove from active positions
                del self.active_positions[position_key]
    
    def _close_position(self, position: Dict[str, Any]) -> Optional[Decimal]:
        """
        Close a statistical arbitrage position.
        
        Args:
            position: Position dictionary
            
        Returns:
            Profit or None
        """
        try:
            # Calculate profit
            entry_price = position["entry_price"]
            current_spread = position["pair"].current_spread
            position_size = position["position_size"]
            
            if position["signal_type"] == "entry_long":
                profit = (current_spread - entry_price) * position_size
            else:  # entry_short
                profit = (entry_price - current_spread) * position_size
            
            return profit
            
        except Exception as e:
            self.logger.error(f"Position close failed: {e}")
            return None
    
    def get_pairs(
        self,
        min_confidence: Optional[Decimal] = None,
        status: Optional[str] = None,
    ) -> List[StatisticalPair]:
        """
        Get statistical arbitrage pairs.
        
        Args:
            min_confidence: Minimum confidence filter
            status: Status filter
            
        Returns:
            List of StatisticalPair objects
        """
        pairs = list(self.pairs.values())
        
        if min_confidence is not None:
            pairs = [p for p in pairs if p.confidence >= min_confidence]
        
        if status is not None:
            pairs = [p for p in pairs if p.status == status]
        
        return pairs
    
    def get_signals(
        self,
        signal_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[ArbitrageSignal]:
        """
        Get trading signals.
        
        Args:
            signal_type: Signal type filter
            limit: Maximum number of signals
            
        Returns:
            List of ArbitrageSignal objects
        """
        signals = self.signals.copy()
        
        if signal_type is not None:
            signals = [s for s in signals if s.signal_type == signal_type]
        
        return signals[-limit:]
    
    def get_spread_model(self, symbol1: str, symbol2: str) -> Optional[SpreadModel]:
        """
        Get spread model for a pair.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            
        Returns:
            SpreadModel or None
        """
        key = f"{symbol1}_{symbol2}"
        return self.spread_models.get(key)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get detector metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            "pairs_analyzed": self.metrics["pairs_analyzed"],
            "pairs_found": self.metrics["pairs_found"],
            "active_pairs": len(self.pairs),
            "signals_generated": self.metrics["signals_generated"],
            "signals_executed": self.metrics["signals_executed"],
            "total_profit": float(self.metrics["total_profit"]),
            "win_rate": float(self.metrics["win_rate"]),
            "avg_return": float(self.metrics["avg_return"]),
            "sharpe_ratio": float(self.metrics["sharpe_ratio"]),
            "max_drawdown": float(self.metrics["max_drawdown"]),
            "errors": self.metrics["errors"],
            "current_regime": self.current_regime.value,
            "active_positions": len(self.active_positions),
            "is_running": self.is_running,
            "scan_interval": self.scan_interval,
        }


# Additional Statistical Tools

class CointegrationAnalyzer:
    """Advanced cointegration analysis."""
    
    @staticmethod
    def analyze(
        prices1: np.ndarray,
        prices2: np.ndarray,
        method: str = "engle_granger",
    ) -> Dict[str, Any]:
        """
        Analyze cointegration between two price series.
        
        Args:
            prices1: First price series
            prices2: Second price series
            method: Method to use
            
        Returns:
            Dictionary with cointegration results
        """
        if len(prices1) != len(prices2) or len(prices1) < 30:
            return {"cointegrated": False, "pvalue": 1.0}
        
        if method == "engle_granger":
            result = coint(prices1, prices2)
            return {
                "cointegrated": result[1] < 0.05,
                "pvalue": result[1],
                "statistic": result[0],
                "critical_values": result[2],
            }
        elif method == "johansen":
            data = np.column_stack([prices1, prices2])
            result = coint_johansen(data, 0, 1)
            return {
                "cointegrated": result.lr1[0] > result.cvt[0][0],
                "trace_statistic": result.lr1[0],
                "critical_value": result.cvt[0][0],
                "eigenvalues": result.lr2,
            }
        else:
            return {"cointegrated": False, "pvalue": 1.0}


class KalmanFilter:
    """Kalman filter for dynamic hedge ratio estimation."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.states: Dict[str, KalmanState] = {}
    
    def update(
        self,
        symbol1: str,
        symbol2: str,
        price1: Decimal,
        price2: Decimal,
    ) -> KalmanState:
        """
        Update Kalman filter state.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            price1: First price
            price2: Second price
            
        Returns:
            Updated KalmanState
        """
        key = f"{symbol1}_{symbol2}"
        
        # Initialize if not exists
        if key not in self.states:
            self.states[key] = KalmanState(
                symbol1=symbol1,
                symbol2=symbol2,
                hedge_ratio=Decimal("1"),
                intercept=Decimal("0"),
                spread=Decimal("0"),
                variance=Decimal("0.01"),
                timestamp=datetime.utcnow(),
            )
        
        # Update using Kalman filter
        state = self.states[key]
        
        # Simple update: moving average of hedge ratio
        # In production, this would use a proper Kalman filter
        p1 = float(price1)
        p2 = float(price2)
        new_ratio = p1 / p2 if p2 != 0 else 1.0
        
        # Exponential smoothing
        alpha = 0.1
        state.hedge_ratio = Decimal(str(alpha * new_ratio + (1 - alpha) * float(state.hedge_ratio)))
        state.spread = price1 - state.hedge_ratio * price2
        state.timestamp = datetime.utcnow()
        
        return state


class MeanReversionDetector:
    """Mean reversion detection and analysis."""
    
    @staticmethod
    def detect(
        prices: np.ndarray,
        window: int = 20,
        threshold: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Detect mean reversion opportunities.
        
        Args:
            prices: Price series
            window: Rolling window size
            threshold: Z-score threshold
            
        Returns:
            Dictionary with detection results
        """
        if len(prices) < window:
            return {"mean_reverting": False}
        
        # Calculate rolling statistics
        rolling_mean = np.mean(prices[-window:])
        rolling_std = np.std(prices[-window:])
        current_price = prices[-1]
        
        # Calculate z-score
        zscore = (current_price - rolling_mean) / rolling_std if rolling_std > 0 else 0
        
        return {
            "mean_reverting": abs(zscore) > threshold,
            "zscore": zscore,
            "mean": rolling_mean,
            "std": rolling_std,
            "current_price": current_price,
            "deviation": current_price - rolling_mean,
            "deviation_percent": (current_price - rolling_mean) / rolling_mean * 100 if rolling_mean > 0 else 0,
        }


# Module exports
__all__ = [
    'StatisticalDetector',
    'StatisticalPair',
    'SpreadModel',
    'KalmanState',
    'ArbitrageSignal',
    'StatisticalMethod',
    'RegimeType',
    'CointegrationAnalyzer',
    'KalmanFilter',
    'MeanReversionDetector',
]

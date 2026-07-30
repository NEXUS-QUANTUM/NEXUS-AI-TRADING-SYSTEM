# trading/bots/hedge_bot/hedge_bot_volatility.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Volatility Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Volatility Module

This module provides comprehensive volatility analysis and management
capabilities for the NEXUS Hedge Bot system. It includes historical,
implied, realized, and forecasted volatility calculations.

The module covers:
- Historical Volatility
- Implied Volatility
- Realized Volatility
- EWMA Volatility
- GARCH Volatility
- Volatility Forecasting
- Volatility Surface
- Volatility Skew
- Volatility Regimes
- Volatility Risk Management
- Volatility-based Position Sizing
- Volatility-based Stop Loss
- Volatility-based Hedging
"""

import os
import sys
import math
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm

# Try to import optional dependencies
try:
    from arch import arch_model
    HAS_ARCH = True
except ImportError:
    HAS_ARCH = False

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)

# ============================================================
# VOLATILITY DATACLASSES
# ============================================================

@dataclass
class VolatilityMetrics:
    """Volatility metrics"""
    historical: float = 0.0
    implied: float = 0.0
    realized: float = 0.0
    ewma: float = 0.0
    garch: float = 0.0
    forecast: float = 0.0
    volatility_of_volatility: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "historical": self.historical,
            "implied": self.implied,
            "realized": self.realized,
            "ewma": self.ewma,
            "garch": self.garch,
            "forecast": self.forecast,
            "volatility_of_volatility": self.volatility_of_volatility,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VolatilityRegime:
    """Volatility regime"""
    name: str
    threshold: float
    description: str
    color: str
    risk_multiplier: float
    position_sizing_multiplier: float
    hedge_ratio_multiplier: float
    stop_loss_multiplier: float
    take_profit_multiplier: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "threshold": self.threshold,
            "description": self.description,
            "color": self.color,
            "risk_multiplier": self.risk_multiplier,
            "position_sizing_multiplier": self.position_sizing_multiplier,
            "hedge_ratio_multiplier": self.hedge_ratio_multiplier,
            "stop_loss_multiplier": self.stop_loss_multiplier,
            "take_profit_multiplier": self.take_profit_multiplier,
        }


@dataclass
class VolatilitySurface:
    """Volatility surface"""
    tenors: List[str]
    strikes: List[float]
    implied_vols: np.ndarray
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tenors": self.tenors,
            "strikes": self.strikes,
            "implied_vols": self.implied_vols.tolist() if hasattr(self.implied_vols, 'tolist') else self.implied_vols,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# VOLATILITY CALCULATOR
# ============================================================

class VolatilityCalculator:
    """
    Comprehensive volatility calculator
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_lookback = self.config.get("lookback", 30)
        self.default_annualization = self.config.get("annualization", 252)
        self.default_lambda = self.config.get("lambda", 0.94)
        self.default_confidence = self.config.get("confidence", 0.95)
        self.metrics_cache = {}
    
    # ============================================================
    # HISTORICAL VOLATILITY
    # ============================================================
    
    def calculate_historical_volatility(
        self,
        prices: Union[List[float], pd.Series, np.ndarray],
        lookback: Optional[int] = None,
        annualize: bool = True
    ) -> float:
        """
        Calculate historical volatility
        
        Args:
            prices: Price series
            lookback: Lookback period
            annualize: Annualize the volatility
            
        Returns:
            Historical volatility
        """
        if lookback is None:
            lookback = self.default_lookback
        
        # Convert to numpy array
        if isinstance(prices, list):
            prices = np.array(prices)
        elif isinstance(prices, pd.Series):
            prices = prices.values
        
        # Calculate returns
        returns = np.diff(np.log(prices))
        
        # Use only the last lookback period
        if len(returns) > lookback:
            returns = returns[-lookback:]
        
        # Calculate standard deviation
        vol = np.std(returns)
        
        # Annualize if requested
        if annualize:
            vol = vol * np.sqrt(self.default_annualization)
        
        return float(vol)
    
    def calculate_historical_volatility_multi(
        self,
        prices_dict: Dict[str, Union[List[float], pd.Series, np.ndarray]],
        lookback: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Calculate historical volatility for multiple assets
        
        Args:
            prices_dict: Dictionary of price series
            lookback: Lookback period
            
        Returns:
            Dictionary of volatilities
        """
        results = {}
        for symbol, prices in prices_dict.items():
            results[symbol] = self.calculate_historical_volatility(prices, lookback)
        return results
    
    # ============================================================
    # REALIZED VOLATILITY
    # ============================================================
    
    def calculate_realized_volatility(
        self,
        prices: Union[List[float], pd.Series, np.ndarray],
        method: str = "parkinson",
        lookback: Optional[int] = None
    ) -> float:
        """
        Calculate realized volatility using various methods
        
        Args:
            prices: Price series (OHLC data)
            method: Calculation method (parkinson, garman_klass, rogers_satchell, yang_zhang)
            lookback: Lookback period
            
        Returns:
            Realized volatility
        """
        if lookback is None:
            lookback = self.default_lookback
        
        # Convert to DataFrame if needed
        if isinstance(prices, dict):
            df = pd.DataFrame(prices)
        elif isinstance(prices, list) and len(prices) > 0 and isinstance(prices[0], dict):
            df = pd.DataFrame(prices)
        else:
            # Assume simple price series
            df = pd.DataFrame({"close": prices})
        
        # Ensure we have required columns
        if "close" not in df.columns:
            # Create OHLC from close with some assumptions
            df["open"] = df["close"].shift(1)
            df["high"] = df["close"] * (1 + 0.01)
            df["low"] = df["close"] * (1 - 0.01)
            df["close"] = df["close"]
        
        # Use only the last lookback period
        if len(df) > lookback:
            df = df.tail(lookback)
        
        # Calculate returns
        if "open" in df.columns and "close" in df.columns:
            close = df["close"].values
            open_price = df["open"].values
            
            # Simple returns
            returns = np.diff(np.log(close))
            
            # Calculate volatility based on method
            if method == "parkinson":
                # Parkinson volatility
                high = df["high"].values[1:]
                low = df["low"].values[1:]
                vol = np.sqrt(np.mean(0.5 * np.log(high / low) ** 2))
            elif method == "garman_klass":
                # Garman-Klass volatility
                high = df["high"].values[1:]
                low = df["low"].values[1:]
                close_prev = df["close"].values[:-1]
                vol = np.sqrt(np.mean(
                    0.5 * np.log(high / low) ** 2 -
                    (2 * np.log(2) - 1) * np.log(close / close_prev) ** 2
                ))
            elif method == "rogers_satchell":
                # Rogers-Satchell volatility
                high = df["high"].values[1:]
                low = df["low"].values[1:]
                open_price = df["open"].values[1:]
                close_prev = df["close"].values[:-1]
                vol = np.sqrt(np.mean(
                    np.log(high / close_prev) * np.log(high / open_price) +
                    np.log(low / close_prev) * np.log(low / open_price)
                ))
            elif method == "yang_zhang":
                # Yang-Zhang volatility
                high = df["high"].values[1:]
                low = df["low"].values[1:]
                open_price = df["open"].values[1:]
                close_prev = df["close"].values[:-1]
                
                # Calculate components
                overnight = np.log(open_price / close_prev)
                close_vol = np.log(close_prev / open_price)
                high_low = np.log(high / low)
                
                k = 0.34 / (1.34 + (len(returns) + 1) / (len(returns) - 1))
                vol = np.sqrt(
                    np.var(overnight) +
                    k * np.var(close_vol) +
                    (1 - k) * np.var(high_low)
                )
            else:
                # Default to standard deviation
                vol = np.std(returns)
        else:
            vol = np.std(np.diff(np.log(df["close"].values)))
        
        # Annualize
        vol = vol * np.sqrt(self.default_annualization)
        
        return float(vol)
    
    # ============================================================
    # EWMA VOLATILITY
    # ============================================================
    
    def calculate_ewma_volatility(
        self,
        prices: Union[List[float], pd.Series, np.ndarray],
        lambda_value: Optional[float] = None,
        lookback: Optional[int] = None
    ) -> float:
        """
        Calculate EWMA volatility
        
        Args:
            prices: Price series
            lambda_value: Decay factor (0 < lambda < 1)
            lookback: Lookback period
            
        Returns:
            EWMA volatility
        """
        if lambda_value is None:
            lambda_value = self.default_lambda
        
        if lookback is None:
            lookback = self.default_lookback
        
        # Convert to numpy array
        if isinstance(prices, list):
            prices = np.array(prices)
        elif isinstance(prices, pd.Series):
            prices = prices.values
        
        # Calculate returns
        returns = np.diff(np.log(prices))
        
        # Use only the last lookback period
        if len(returns) > lookback:
            returns = returns[-lookback:]
        
        # Calculate EWMA variance
        variance = np.var(returns)
        for ret in returns:
            variance = lambda_value * variance + (1 - lambda_value) * ret ** 2
        
        vol = np.sqrt(variance)
        vol = vol * np.sqrt(self.default_annualization)
        
        return float(vol)
    
    # ============================================================
    # GARCH VOLATILITY
    # ============================================================
    
    def calculate_garch_volatility(
        self,
        prices: Union[List[float], pd.Series, np.ndarray],
        p: int = 1,
        q: int = 1,
        forecast_horizon: int = 1
    ) -> float:
        """
        Calculate GARCH volatility
        
        Args:
            prices: Price series
            p: GARCH p parameter
            q: GARCH q parameter
            forecast_horizon: Forecast horizon
            
        Returns:
            GARCH volatility
        """
        if not HAS_ARCH:
            logger.warning("arch package not installed, using fallback method")
            return self.calculate_historical_volatility(prices)
        
        # Convert to numpy array
        if isinstance(prices, list):
            prices = np.array(prices)
        elif isinstance(prices, pd.Series):
            prices = prices.values
        
        # Calculate returns
        returns = np.diff(np.log(prices)) * 100  # Scale for better convergence
        
        # Fit GARCH model
        model = arch_model(returns, p=p, q=q, vol="Garch", dist="normal")
        result = model.fit(disp="off")
        
        # Forecast volatility
        forecast = result.forecast(horizon=forecast_horizon)
        variance = forecast.variance.iloc[-1, :].values[0]
        
        # Convert back to decimal scale
        vol = np.sqrt(variance) / 100
        vol = vol * np.sqrt(self.default_annualization)
        
        return float(vol)
    
    # ============================================================
    # IMPLIED VOLATILITY
    # ============================================================
    
    def calculate_implied_volatility(
        self,
        option_price: float,
        underlying_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float = 0.04,
        dividend_yield: float = 0.01,
        option_type: str = "call"
    ) -> float:
        """
        Calculate implied volatility using Black-Scholes
        
        Args:
            option_price: Option price
            underlying_price: Underlying asset price
            strike_price: Strike price
            time_to_expiry: Time to expiry in years
            risk_free_rate: Risk-free rate
            dividend_yield: Dividend yield
            option_type: Option type (call or put)
            
        Returns:
            Implied volatility
        """
        def black_scholes_price(vol):
            """Black-Scholes option price"""
            d1 = (np.log(underlying_price / strike_price) + 
                  (risk_free_rate - dividend_yield + 0.5 * vol ** 2) * time_to_expiry) / (vol * np.sqrt(time_to_expiry))
            d2 = d1 - vol * np.sqrt(time_to_expiry)
            
            if option_type.lower() == "call":
                price = (underlying_price * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1) -
                        strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2))
            else:
                price = (strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) -
                        underlying_price * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1))
            
            return price
        
        # Use Brent's method to find implied vol
        try:
            from scipy.optimize import brentq
            implied_vol = brentq(
                lambda vol: black_scholes_price(vol) - option_price,
                0.001, 5.0
            )
        except:
            # Fallback to a simple method
            implied_vol = 0.2
            
        return float(implied_vol)
    
    # ============================================================
    # VOLATILITY FORECASTING
    # ============================================================
    
    def forecast_volatility(
        self,
        prices: Union[List[float], pd.Series, np.ndarray],
        horizon: int = 10,
        method: str = "ensemble"
    ) -> float:
        """
        Forecast future volatility
        
        Args:
            prices: Price series
            horizon: Forecast horizon in days
            method: Forecasting method (historical, ewma, garch, ensemble)
            
        Returns:
            Forecasted volatility
        """
        if method == "historical":
            return self.calculate_historical_volatility(prices)
        elif method == "ewma":
            return self.calculate_ewma_volatility(prices)
        elif method == "garch":
            return self.calculate_garch_volatility(prices, forecast_horizon=horizon)
        elif method == "ensemble":
            # Combine multiple methods
            hist_vol = self.calculate_historical_volatility(prices)
            ewma_vol = self.calculate_ewma_volatility(prices)
            
            try:
                garch_vol = self.calculate_garch_volatility(prices, forecast_horizon=horizon)
            except:
                garch_vol = hist_vol
            
            # Weighted ensemble
            weights = [0.3, 0.3, 0.4]
            vol = weights[0] * hist_vol + weights[1] * ewma_vol + weights[2] * garch_vol
            
            return float(vol)
        else:
            raise ValueError(f"Unknown forecasting method: {method}")
    
    # ============================================================
    # VOLATILITY OF VOLATILITY
    # ============================================================
    
    def calculate_volatility_of_volatility(
        self,
        prices: Union[List[float], pd.Series, np.ndarray],
        window: int = 20
    ) -> float:
        """
        Calculate volatility of volatility
        
        Args:
            prices: Price series
            window: Rolling window
            
        Returns:
            Volatility of volatility
        """
        if isinstance(prices, list):
            prices = np.array(prices)
        
        # Calculate rolling volatilities
        vols = []
        for i in range(window, len(prices)):
            vol = self.calculate_historical_volatility(
                prices[i - window:i + 1],
                lookback=window,
                annualize=False
            )
            vols.append(vol)
        
        # Calculate volatility of volatilities
        if len(vols) > 1:
            vol_of_vol = np.std(vols) * np.sqrt(self.default_annualization)
        else:
            vol_of_vol = 0.0
        
        return float(vol_of_vol)
    
    # ============================================================
    # VOLATILITY SURFACE
    # ============================================================
    
    def calculate_volatility_surface(
        self,
        option_data: Dict[str, Any],
        underlying_price: float,
        risk_free_rate: float = 0.04,
        dividend_yield: float = 0.01
    ) -> VolatilitySurface:
        """
        Calculate volatility surface
        
        Args:
            option_data: Option data by tenor and strike
            underlying_price: Underlying asset price
            risk_free_rate: Risk-free rate
            dividend_yield: Dividend yield
            
        Returns:
            VolatilitySurface object
        """
        tenors = sorted(option_data.keys())
        strikes = sorted(option_data[tenors[0]].keys())
        
        implied_vols = np.zeros((len(tenors), len(strikes)))
        
        for i, tenor in enumerate(tenors):
            time_to_expiry = self._parse_tenor(tenor)
            for j, strike in enumerate(strikes):
                option_price = option_data[tenor][strike]
                implied_vols[i, j] = self.calculate_implied_volatility(
                    option_price=option_price,
                    underlying_price=underlying_price,
                    strike_price=strike,
                    time_to_expiry=time_to_expiry,
                    risk_free_rate=risk_free_rate,
                    dividend_yield=dividend_yield
                )
        
        return VolatilitySurface(
            tenors=tenors,
            strikes=strikes,
            implied_vols=implied_vols,
            timestamp=datetime.now()
        )
    
    def _parse_tenor(self, tenor: str) -> float:
        """Parse tenor string to years"""
        if tenor.endswith("D"):
            return int(tenor[:-1]) / 365
        elif tenor.endswith("W"):
            return int(tenor[:-1]) / 52
        elif tenor.endswith("M"):
            return int(tenor[:-1]) / 12
        elif tenor.endswith("Y"):
            return int(tenor[:-1])
        else:
            return 1.0
    
    # ============================================================
    # VOLATILITY SKEW
    # ============================================================
    
    def calculate_volatility_skew(
        self,
        call_vols: Dict[float, float],
        put_vols: Dict[float, float],
        atm_strike: float
    ) -> Dict[str, float]:
        """
        Calculate volatility skew
        
        Args:
            call_vols: Call option volatilities by strike
            put_vols: Put option volatilities by strike
            atm_strike: At-the-money strike
            
        Returns:
            Skew metrics
        """
        skew_metrics = {}
        
        # Put-call skew
        if atm_strike in put_vols and atm_strike in call_vols:
            skew_metrics["put_call_skew"] = put_vols[atm_strike] - call_vols[atm_strike]
        
        # Smile skew (25-delta)
        strikes = sorted(call_vols.keys())
        if len(strikes) >= 3:
            # Calculate skew at different strike points
            ootm_call_strike = strikes[-1] if strikes else atm_strike
            ootm_put_strike = strikes[0] if strikes else atm_strike
            
            if ootm_call_strike in call_vols and atm_strike in call_vols:
                skew_metrics["call_skew"] = call_vols[ootm_call_strike] - call_vols[atm_strike]
            
            if ootm_put_strike in put_vols and atm_strike in put_vols:
                skew_metrics["put_skew"] = put_vols[ootm_put_strike] - put_vols[atm_strike]
        
        # Butterfly skew
        if len(strikes) >= 5:
            mid_idx = len(strikes) // 2
            low_strike = strikes[mid_idx - 1]
            high_strike = strikes[mid_idx + 1]
            
            if low_strike in call_vols and high_strike in call_vols:
                butterfly = call_vols[low_strike] - 2 * call_vols[atm_strike] + call_vols[high_strike]
                skew_metrics["butterfly_skew"] = butterfly
        
        return skew_metrics
    
    # ============================================================
    # VOLATILITY REGIMES
    # ============================================================
    
    def detect_volatility_regime(
        self,
        volatility: float,
        historical_vols: Optional[List[float]] = None
    ) -> VolatilityRegime:
        """
        Detect current volatility regime
        
        Args:
            volatility: Current volatility
            historical_vols: Historical volatility series
            
        Returns:
            VolatilityRegime object
        """
        # Define regimes
        regimes = {
            "extremely_low": VolatilityRegime(
                name="extremely_low",
                threshold=0.05,
                description="Extremely Low Volatility",
                color="#00FF00",
                risk_multiplier=0.5,
                position_sizing_multiplier=1.5,
                hedge_ratio_multiplier=0.5,
                stop_loss_multiplier=0.7,
                take_profit_multiplier=0.7,
            ),
            "very_low": VolatilityRegime(
                name="very_low",
                threshold=0.08,
                description="Very Low Volatility",
                color="#33CC33",
                risk_multiplier=0.7,
                position_sizing_multiplier=1.3,
                hedge_ratio_multiplier=0.6,
                stop_loss_multiplier=0.8,
                take_profit_multiplier=0.8,
            ),
            "low": VolatilityRegime(
                name="low",
                threshold=0.12,
                description="Low Volatility",
                color="#66CC66",
                risk_multiplier=0.8,
                position_sizing_multiplier=1.1,
                hedge_ratio_multiplier=0.7,
                stop_loss_multiplier=0.9,
                take_profit_multiplier=0.9,
            ),
            "normal": VolatilityRegime(
                name="normal",
                threshold=0.20,
                description="Normal Volatility",
                color="#FFCC00",
                risk_multiplier=1.0,
                position_sizing_multiplier=1.0,
                hedge_ratio_multiplier=1.0,
                stop_loss_multiplier=1.0,
                take_profit_multiplier=1.0,
            ),
            "high": VolatilityRegime(
                name="high",
                threshold=0.30,
                description="High Volatility",
                color="#FF6600",
                risk_multiplier=1.3,
                position_sizing_multiplier=0.7,
                hedge_ratio_multiplier=1.5,
                stop_loss_multiplier=1.3,
                take_profit_multiplier=1.3,
            ),
            "very_high": VolatilityRegime(
                name="very_high",
                threshold=0.40,
                description="Very High Volatility",
                color="#FF3300",
                risk_multiplier=1.6,
                position_sizing_multiplier=0.5,
                hedge_ratio_multiplier=2.0,
                stop_loss_multiplier=1.6,
                take_profit_multiplier=1.6,
            ),
            "extremely_high": VolatilityRegime(
                name="extremely_high",
                threshold=0.50,
                description="Extremely High Volatility",
                color="#FF0000",
                risk_multiplier=2.0,
                position_sizing_multiplier=0.3,
                hedge_ratio_multiplier=2.5,
                stop_loss_multiplier=2.0,
                take_profit_multiplier=2.0,
            ),
        }
        
        # Find the appropriate regime
        current_regime = regimes["normal"]
        for name, regime in regimes.items():
            if volatility <= regime.threshold:
                current_regime = regime
                break
        
        # If we have historical data, consider trend
        if historical_vols and len(historical_vols) > 10:
            recent_avg = np.mean(historical_vols[-10:])
            long_term_avg = np.mean(historical_vols)
            
            # If volatility is increasing
            if recent_avg > long_term_avg * 1.2:
                # Move one regime higher
                regime_order = list(regimes.keys())
                current_idx = regime_order.index(current_regime.name)
                if current_idx < len(regime_order) - 1:
                    current_regime = regimes[regime_order[current_idx + 1]]
            
            # If volatility is decreasing
            elif recent_avg < long_term_avg * 0.8:
                # Move one regime lower
                regime_order = list(regimes.keys())
                current_idx = regime_order.index(current_regime.name)
                if current_idx > 0:
                    current_regime = regimes[regime_order[current_idx - 1]]
        
        return current_regime
    
    # ============================================================
    # VOLATILITY-BASED POSITION SIZING
    # ============================================================
    
    def calculate_volatility_position_size(
        self,
        portfolio_value: float,
        target_volatility: float,
        asset_volatility: float,
        correlation: float = 0.0,
        max_position: Optional[float] = None,
        min_position: Optional[float] = None
    ) -> float:
        """
        Calculate position size based on volatility
        
        Args:
            portfolio_value: Total portfolio value
            target_volatility: Target portfolio volatility
            asset_volatility: Asset volatility
            correlation: Correlation with portfolio
            max_position: Maximum position size
            min_position: Minimum position size
            
        Returns:
            Position size
        """
        # Calculate position size
        position_size = (portfolio_value * target_volatility) / (asset_volatility * (1 - correlation))
        
        # Apply limits
        if max_position is not None:
            position_size = min(position_size, max_position)
        if min_position is not None:
            position_size = max(position_size, min_position)
        
        return float(position_size)
    
    # ============================================================
    # VOLATILITY-BASED STOP LOSS
    # ============================================================
    
    def calculate_volatility_stop_loss(
        self,
        entry_price: float,
        volatility: float,
        multiplier: float = 1.5,
        min_stop: Optional[float] = None,
        max_stop: Optional[float] = None
    ) -> float:
        """
        Calculate stop loss based on volatility
        
        Args:
            entry_price: Entry price
            volatility: Asset volatility
            multiplier: Multiplier for volatility
            min_stop: Minimum stop distance
            max_stop: Maximum stop distance
            
        Returns:
            Stop loss price
        """
        # Calculate stop distance
        stop_distance = entry_price * volatility * multiplier
        
        # Apply limits
        if min_stop is not None:
            stop_distance = max(stop_distance, min_stop)
        if max_stop is not None:
            stop_distance = min(stop_distance, max_stop)
        
        return entry_price - stop_distance
    
    # ============================================================
    # VOLATILITY-BASED TAKE PROFIT
    # ============================================================
    
    def calculate_volatility_take_profit(
        self,
        entry_price: float,
        volatility: float,
        multiplier: float = 2.0,
        min_profit: Optional[float] = None,
        max_profit: Optional[float] = None
    ) -> float:
        """
        Calculate take profit based on volatility
        
        Args:
            entry_price: Entry price
            volatility: Asset volatility
            multiplier: Multiplier for volatility
            min_profit: Minimum profit distance
            max_profit: Maximum profit distance
            
        Returns:
            Take profit price
        """
        # Calculate profit distance
        profit_distance = entry_price * volatility * multiplier
        
        # Apply limits
        if min_profit is not None:
            profit_distance = max(profit_distance, min_profit)
        if max_profit is not None:
            profit_distance = min(profit_distance, max_profit)
        
        return entry_price + profit_distance
    
    # ============================================================
    # RISK METRICS
    # ============================================================
    
    def calculate_var(
        self,
        returns: Union[List[float], np.ndarray],
        confidence: float = 0.95,
        horizon: int = 1
    ) -> float:
        """
        Calculate Value at Risk
        
        Args:
            returns: Return series
            confidence: Confidence level
            horizon: Time horizon in days
            
        Returns:
            VaR value
        """
        if isinstance(returns, list):
            returns = np.array(returns)
        
        var = np.percentile(returns, (1 - confidence) * 100)
        var = var * np.sqrt(horizon)
        
        return abs(float(var))
    
    def calculate_cvar(
        self,
        returns: Union[List[float], np.ndarray],
        confidence: float = 0.95,
        horizon: int = 1
    ) -> float:
        """
        Calculate Conditional VaR (CVaR)
        
        Args:
            returns: Return series
            confidence: Confidence level
            horizon: Time horizon in days
            
        Returns:
            CVaR value
        """
        if isinstance(returns, list):
            returns = np.array(returns)
        
        var = np.percentile(returns, (1 - confidence) * 100)
        cvar = np.mean(returns[returns <= var])
        cvar = cvar * np.sqrt(horizon)
        
        return abs(float(cvar))


# ============================================================
# VOLATILITY ANALYZER
# ============================================================

class VolatilityAnalyzer:
    """
    Comprehensive volatility analyzer
    """
    
    def __init__(self, calculator: Optional[VolatilityCalculator] = None):
        self.calculator = calculator or VolatilityCalculator()
        self.historical_data = {}
        self.volatility_series = {}
        self.regime_history = []
    
    def analyze_asset_volatility(
        self,
        prices: Union[List[float], pd.Series, np.ndarray],
        symbol: str,
        lookback: Optional[int] = None
    ) -> VolatilityMetrics:
        """
        Analyze volatility for a single asset
        
        Args:
            prices: Price series
            symbol: Asset symbol
            lookback: Lookback period
            
        Returns:
            VolatilityMetrics object
        """
        if lookback is None:
            lookback = self.calculator.default_lookback
        
        # Calculate various volatility metrics
        hist_vol = self.calculator.calculate_historical_volatility(prices, lookback)
        ewma_vol = self.calculator.calculate_ewma_volatility(prices, lookback=lookback)
        realized_vol = self.calculator.calculate_realized_volatility(prices, lookback=lookback)
        
        try:
            garch_vol = self.calculator.calculate_garch_volatility(prices)
        except:
            garch_vol = hist_vol
        
        forecast_vol = self.calculator.forecast_volatility(prices, horizon=10)
        vol_of_vol = self.calculator.calculate_volatility_of_volatility(prices)
        
        # Calculate returns for risk metrics
        if isinstance(prices, list):
            prices_array = np.array(prices)
        elif isinstance(prices, pd.Series):
            prices_array = prices.values
        else:
            prices_array = prices
        
        returns = np.diff(np.log(prices_array))
        skewness = stats.skew(returns)
        kurtosis = stats.kurtosis(returns)
        var_95 = self.calculator.calculate_var(returns, confidence=0.95)
        var_99 = self.calculator.calculate_var(returns, confidence=0.99)
        cvar_95 = self.calculator.calculate_cvar(returns, confidence=0.95)
        
        # Store historical data
        self.historical_data[symbol] = prices
        self.volatility_series[symbol] = {
            "hist_vol": hist_vol,
            "ewma_vol": ewma_vol,
            "realized_vol": realized_vol,
            "garch_vol": garch_vol,
            "forecast_vol": forecast_vol,
            "timestamp": datetime.now(),
        }
        
        return VolatilityMetrics(
            historical=hist_vol,
            implied=0.0,  # Would need option data
            realized=realized_vol,
            ewma=ewma_vol,
            garch=garch_vol,
            forecast=forecast_vol,
            volatility_of_volatility=vol_of_vol,
            skewness=skewness,
            kurtosis=kurtosis,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            timestamp=datetime.now()
        )
    
    def analyze_portfolio_volatility(
        self,
        prices_dict: Dict[str, Union[List[float], pd.Series, np.ndarray]],
        weights: Dict[str, float],
        lookback: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Analyze portfolio volatility
        
        Args:
            prices_dict: Dictionary of price series by symbol
            weights: Portfolio weights
            lookback: Lookback period
            
        Returns:
            Portfolio volatility analysis
        """
        if lookback is None:
            lookback = self.calculator.default_lookback
        
        # Calculate individual volatilities
        volatilities = {}
        returns_dict = {}
        
        for symbol, prices in prices_dict.items():
            if isinstance(prices, list):
                prices_array = np.array(prices)
            elif isinstance(prices, pd.Series):
                prices_array = prices.values
            else:
                prices_array = prices
            
            returns_dict[symbol] = np.diff(np.log(prices_array))
            volatilities[symbol] = self.calculator.calculate_historical_volatility(prices, lookback)
        
        # Calculate portfolio volatility
        returns_matrix = np.column_stack([returns_dict[symbol] for symbol in weights.keys()])
        
        # Calculate correlation matrix
        corr_matrix = np.corrcoef(returns_matrix.T)
        
        # Calculate portfolio volatility
        weights_array = np.array([weights[symbol] for symbol in weights.keys()])
        portfolio_var = weights_array.T @ corr_matrix @ weights_array
        portfolio_vol = np.sqrt(portfolio_var) * np.sqrt(self.calculator.default_annualization)
        
        # Calculate diversification ratio
        weighted_vols = np.array([volatilities[symbol] * weights[symbol] for symbol in weights.keys()])
        diversification_ratio = np.sum(weighted_vols) / portfolio_vol
        
        return {
            "portfolio_volatility": float(portfolio_vol),
            "asset_volatilities": volatilities,
            "correlation_matrix": corr_matrix.tolist(),
            "diversification_ratio": float(diversification_ratio),
            "weights": weights,
            "timestamp": datetime.now(),
        }
    
    def detect_volatility_regime_change(
        self,
        symbol: str,
        current_volatility: float,
        window: int = 20
    ) -> Dict[str, Any]:
        """
        Detect volatility regime changes
        
        Args:
            symbol: Asset symbol
            current_volatility: Current volatility
            window: Lookback window
            
        Returns:
            Regime change analysis
        """
        # Get historical volatilities
        if symbol not in self.volatility_series:
            return {
                "regime_changed": False,
                "reason": "No historical data available"
            }
        
        # Get recent volatilities
        recent_vols = []
        for key, data in self.volatility_series.items():
            if key == symbol:
                recent_vols.append(data["hist_vol"])
        
        if len(recent_vols) < window:
            return {
                "regime_changed": False,
                "reason": "Insufficient historical data"
            }
        
        # Calculate statistics
        recent_avg = np.mean(recent_vols[-window:])
        long_term_avg = np.mean(recent_vols)
        
        # Detect change
        change_detected = False
        change_direction = "none"
        change_magnitude = 0.0
        
        if current_volatility > long_term_avg * 1.5:
            change_detected = True
            change_direction = "increase"
            change_magnitude = (current_volatility - long_term_avg) / long_term_avg
        
        elif current_volatility < long_term_avg * 0.5:
            change_detected = True
            change_direction = "decrease"
            change_magnitude = (long_term_avg - current_volatility) / long_term_avg
        
        # Update regime history
        regime = self.calculator.detect_volatility_regime(current_volatility, recent_vols)
        self.regime_history.append({
            "symbol": symbol,
            "volatility": current_volatility,
            "regime": regime.name,
            "timestamp": datetime.now(),
            "change_detected": change_detected,
            "change_direction": change_direction,
            "change_magnitude": change_magnitude,
        })
        
        return {
            "regime_changed": change_detected,
            "direction": change_direction,
            "magnitude": change_magnitude,
            "current_regime": regime.name,
            "previous_regime": self.regime_history[-2]["regime"] if len(self.regime_history) > 1 else "unknown",
            "timestamp": datetime.now(),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Dataclasses
    "VolatilityMetrics",
    "VolatilityRegime",
    "VolatilitySurface",
    
    # Classes
    "VolatilityCalculator",
    "VolatilityAnalyzer",
]

# ============================================================
# END OF MODULE
# ============================================================

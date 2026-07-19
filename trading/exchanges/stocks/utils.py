# trading/exchanges/stocks/utils.py
# Nexus AI Trading System - Stock Exchange Utilities Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Stock Exchange - Utilities Module

This module provides comprehensive utility functions for stock trading across
multiple brokers including Alpaca, Interactive Brokers, TD Ameritrade, Robinhood,
E*TRADE, Fidelity, Schwab, TradeStation, and Tradier.

It includes:

- Symbol normalization and validation
- Price and volume calculations
- Position sizing and risk management
- Technical indicator calculations
- Portfolio analytics
- Risk metrics
- Performance metrics
- Data formatting and parsing
- Time conversion utilities
- Market status detection
- Trading session management
- Order validation utilities
- Fee calculation utilities
- Margin requirement calculations
- Dividend and corporate action utilities
- News and sentiment utilities
- Watchlist management utilities
- Arbitrage detection utilities
- Correlation and covariance calculations
- Backtesting utilities
- Monte Carlo simulation
- Performance attribution
"""

import asyncio
import math
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Union, Tuple, Set
from enum import Enum
import json
import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import minimize

# Nexus imports
from shared.helpers.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Stock exchanges
STOCK_EXCHANGES = {
    'NYSE': 'New York Stock Exchange',
    'NASDAQ': 'NASDAQ',
    'AMEX': 'American Stock Exchange',
    'ARCA': 'NYSE Arca',
    'BATS': 'BATS Global Markets',
    'CBOE': 'Chicago Board Options Exchange',
    'OTC': 'Over-the-Counter',
    'PINK': 'Pink Sheets',
    'LSE': 'London Stock Exchange',
    'TSE': 'Tokyo Stock Exchange',
    'HKEX': 'Hong Kong Stock Exchange',
    'EURONEXT': 'Euronext',
    'TSX': 'Toronto Stock Exchange',
    'ASX': 'Australian Securities Exchange',
}

# US holidays for market closure
US_HOLIDAYS = {
    'New Year\'s Day': datetime(2024, 1, 1),
    'Martin Luther King Jr. Day': datetime(2024, 1, 15),
    'Presidents\' Day': datetime(2024, 2, 19),
    'Good Friday': datetime(2024, 3, 29),
    'Memorial Day': datetime(2024, 5, 27),
    'Juneteenth': datetime(2024, 6, 19),
    'Independence Day': datetime(2024, 7, 4),
    'Labor Day': datetime(2024, 9, 2),
    'Thanksgiving Day': datetime(2024, 11, 28),
    'Christmas Day': datetime(2024, 12, 25),
}

# Trading hours by exchange
TRADING_HOURS = {
    'NYSE': {'open': '09:30', 'close': '16:00', 'timezone': 'America/New_York'},
    'NASDAQ': {'open': '09:30', 'close': '16:00', 'timezone': 'America/New_York'},
    'AMEX': {'open': '09:30', 'close': '16:00', 'timezone': 'America/New_York'},
    'ARCA': {'open': '09:30', 'close': '16:00', 'timezone': 'America/New_York'},
    'LSE': {'open': '08:00', 'close': '16:30', 'timezone': 'Europe/London'},
    'TSE': {'open': '09:00', 'close': '15:00', 'timezone': 'Asia/Tokyo'},
    'HKEX': {'open': '09:30', 'close': '16:00', 'timezone': 'Asia/Hong_Kong'},
}

# Pre-market and after-hours trading hours
EXTENDED_HOURS = {
    'pre_market': {'open': '04:00', 'close': '09:30'},
    'after_hours': {'open': '16:00', 'close': '20:00'},
}

# Standard stock order types
ORDER_TYPES = {
    'market': 'Market order - immediate execution at best available price',
    'limit': 'Limit order - execute at specified price or better',
    'stop': 'Stop order - becomes market order when stop price is hit',
    'stop_limit': 'Stop-limit order - becomes limit order when stop price is hit',
    'trailing_stop': 'Trailing stop - stop price trails the market price',
    'market_on_close': 'Market on close - executed at closing price',
    'limit_on_close': 'Limit on close - limit order at closing',
    'bracket': 'Bracket order - OCO with stop-loss and take-profit',
    'oco': 'One Cancels Other - linked orders where one cancels the other',
    'oto': 'One Triggers Other - order triggers another order',
}

# Stock position sides
POSITION_SIDES = {
    'long': 'Long position - owns the asset',
    'short': 'Short position - borrowed asset sold',
}

# Time in force
TIME_IN_FORCE = {
    'day': 'Day - order valid only for the trading day',
    'gtc': 'Good Till Cancelled - order valid until cancelled',
    'opg': 'Opening - order valid at market open',
    'cls': 'Closing - order valid at market close',
    'ioc': 'Immediate Or Cancel - order fills immediately or is cancelled',
    'fok': 'Fill Or Kill - order must fill completely or be cancelled',
    'gtd': 'Good Till Date - order valid until specified date',
}

# =============================================================================
# SYMBOL UTILITIES
# =============================================================================

def normalize_symbol(symbol: str, exchange: Optional[str] = None) -> str:
    """
    Normalize a stock symbol.
    
    Args:
        symbol: Stock symbol to normalize
        exchange: Exchange for formatting
        
    Returns:
        Normalized symbol
    """
    if not symbol:
        return ''
    
    # Clean symbol
    symbol = symbol.upper().strip()
    
    # Remove common suffixes
    symbol = re.sub(r'\.[A-Z]{1,3}$', '', symbol)
    symbol = re.sub(r'[^A-Z0-9.]', '', symbol)
    
    # Handle exchange-specific formatting
    if exchange:
        exchange = exchange.upper()
        if exchange == 'LSE':
            symbol = f'{symbol}.L'
        elif exchange == 'TSE':
            symbol = f'{symbol}.T'
        elif exchange == 'HKEX':
            symbol = f'{symbol}.HK'
    
    return symbol


def validate_symbol(symbol: str) -> bool:
    """
    Validate a stock symbol.
    
    Args:
        symbol: Symbol to validate
        
    Returns:
        True if valid
    """
    if not symbol:
        return False
    
    # Check symbol format
    pattern = re.compile(r'^[A-Z]{1,5}$')
    return bool(pattern.match(symbol.upper().strip()))


def split_symbol(symbol: str) -> Tuple[str, Optional[str]]:
    """
    Split symbol into base and exchange suffix.
    
    Args:
        symbol: Full symbol
        
    Returns:
        Tuple of (base_symbol, exchange)
    """
    if not symbol:
        return '', None
    
    parts = symbol.split('.')
    if len(parts) > 1:
        return parts[0], parts[1]
    return symbol, None


def get_exchange_from_symbol(symbol: str) -> Optional[str]:
    """
    Get exchange from symbol suffix.
    
    Args:
        symbol: Symbol with exchange suffix
        
    Returns:
        Exchange code or None
    """
    _, exchange = split_symbol(symbol)
    return exchange


# =============================================================================
# PRICE AND VOLUME UTILITIES
# =============================================================================

def calculate_pip_value(symbol: str, price: Decimal) -> Decimal:
    """
    Calculate pip value for a stock.
    
    Args:
        symbol: Stock symbol
        price: Current price
        
    Returns:
        Pip value
    """
    if not symbol or price <= 0:
        return Decimal('0')
    
    # For most US stocks, pip value is $0.01
    return Decimal('0.01')


def calculate_position_size(
    account_equity: Decimal,
    risk_percentage: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    risk_per_share: Optional[Decimal] = None
) -> Decimal:
    """
    Calculate position size based on risk management.
    
    Args:
        account_equity: Total account equity
        risk_percentage: Risk percentage of account (e.g., 0.02 for 2%)
        entry_price: Entry price
        stop_loss_price: Stop loss price
        risk_per_share: Risk per share (alternative to stop loss)
        
    Returns:
        Position size in shares
    """
    if account_equity <= 0 or risk_percentage <= 0:
        return Decimal('0')
    
    # Calculate risk amount
    risk_amount = account_equity * risk_percentage
    
    # Calculate risk per share
    if risk_per_share is not None and risk_per_share > 0:
        rps = risk_per_share
    elif entry_price > 0 and stop_loss_price > 0:
        rps = abs(entry_price - stop_loss_price)
    else:
        return Decimal('0')
    
    if rps <= 0:
        return Decimal('0')
    
    # Calculate position size
    return (risk_amount / rps).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)


def calculate_risk_reward_ratio(
    entry_price: Decimal,
    exit_price: Decimal,
    stop_loss_price: Decimal
) -> Decimal:
    """
    Calculate risk-reward ratio.
    
    Args:
        entry_price: Entry price
        exit_price: Exit price (take profit)
        stop_loss_price: Stop loss price
        
    Returns:
        Risk-reward ratio
    """
    if entry_price <= 0 or exit_price <= 0 or stop_loss_price <= 0:
        return Decimal('0')
    
    risk = abs(entry_price - stop_loss_price)
    reward = abs(exit_price - entry_price)
    
    if risk == 0:
        return Decimal('0')
    
    return (reward / risk).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_slippage(
    expected_price: Decimal,
    actual_price: Decimal
) -> Decimal:
    """
    Calculate slippage.
    
    Args:
        expected_price: Expected execution price
        actual_price: Actual execution price
        
    Returns:
        Slippage amount
    """
    if expected_price == 0:
        return Decimal('0')
    return (actual_price - expected_price).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_slippage_percent(
    expected_price: Decimal,
    actual_price: Decimal
) -> Decimal:
    """
    Calculate slippage percentage.
    
    Args:
        expected_price: Expected execution price
        actual_price: Actual execution price
        
    Returns:
        Slippage percentage
    """
    if expected_price == 0:
        return Decimal('0')
    slippage = (actual_price - expected_price) / expected_price
    return (slippage * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# =============================================================================
# TECHNICAL INDICATORS
# =============================================================================

def calculate_sma(data: List[float], period: int) -> List[float]:
    """
    Calculate Simple Moving Average.
    
    Args:
        data: Price data
        period: Moving average period
        
    Returns:
        SMA values
    """
    if len(data) < period:
        return []
    
    sma = []
    for i in range(period - 1, len(data)):
        sma.append(sum(data[i - period + 1:i + 1]) / period)
    
    return sma


def calculate_ema(data: List[float], period: int) -> List[float]:
    """
    Calculate Exponential Moving Average.
    
    Args:
        data: Price data
        period: Moving average period
        
    Returns:
        EMA values
    """
    if len(data) < period:
        return []
    
    multiplier = 2 / (period + 1)
    ema = [data[0]]
    
    for price in data[1:]:
        ema.append(price * multiplier + ema[-1] * (1 - multiplier))
    
    return ema


def calculate_rsi(data: List[float], period: int = 14) -> List[float]:
    """
    Calculate Relative Strength Index.
    
    Args:
        data: Price data
        period: RSI period
        
    Returns:
        RSI values
    """
    if len(data) < period + 1:
        return []
    
    rsi_values = []
    
    for i in range(period, len(data)):
        gains = 0
        losses = 0
        
        for j in range(i - period + 1, i + 1):
            change = data[j] - data[j - 1]
            if change > 0:
                gains += change
            else:
                losses -= change
        
        avg_gain = gains / period
        avg_loss = losses / period
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        rsi_values.append(rsi)
    
    return rsi_values


def calculate_macd(
    data: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[List[float], List[float], List[float]]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        data: Price data
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period
        
    Returns:
        Tuple of (MACD line, Signal line, Histogram)
    """
    if len(data) < slow:
        return [], [], []
    
    fast_ema = calculate_ema(data, fast)
    slow_ema = calculate_ema(data, slow)
    
    # Align data
    min_len = min(len(fast_ema), len(slow_ema))
    fast_ema = fast_ema[-min_len:]
    slow_ema = slow_ema[-min_len:]
    
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = calculate_ema(macd_line, signal)
    
    if len(signal_line) < len(macd_line):
        signal_line = [0] * (len(macd_line) - len(signal_line)) + signal_line
    
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    data: List[float],
    period: int = 20,
    std_multiplier: float = 2
) -> Tuple[List[float], List[float], List[float]]:
    """
    Calculate Bollinger Bands.
    
    Args:
        data: Price data
        period: Moving average period
        std_multiplier: Standard deviation multiplier
        
    Returns:
        Tuple of (Upper band, Middle band, Lower band)
    """
    if len(data) < period:
        return [], [], []
    
    middle = []
    upper = []
    lower = []
    
    for i in range(period - 1, len(data)):
        window = data[i - period + 1:i + 1]
        mean = sum(window) / period
        std = math.sqrt(sum((x - mean) ** 2 for x in window) / period)
        
        middle.append(mean)
        upper.append(mean + std_multiplier * std)
        lower.append(mean - std_multiplier * std)
    
    return upper, middle, lower


def calculate_atr(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14
) -> List[float]:
    """
    Calculate Average True Range.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period
        
    Returns:
        ATR values
    """
    if len(high) < period + 1:
        return []
    
    tr_values = []
    for i in range(1, len(high)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        )
        tr_values.append(tr)
    
    if len(tr_values) < period:
        return []
    
    atr = []
    for i in range(period - 1, len(tr_values)):
        atr.append(sum(tr_values[i - period + 1:i + 1]) / period)
    
    return atr


# =============================================================================
# PORTFOLIO ANALYTICS
# =============================================================================

def calculate_portfolio_value(positions: Dict[str, Dict[str, Any]]) -> Decimal:
    """
    Calculate total portfolio value.
    
    Args:
        positions: Dict mapping symbol to position data
        
    Returns:
        Total portfolio value
    """
    total = Decimal('0')
    for position in positions.values():
        quantity = Decimal(str(position.get('quantity', 0)))
        price = Decimal(str(position.get('current_price', 0)))
        total += quantity * price
    return total


def calculate_portfolio_pnl(positions: Dict[str, Dict[str, Any]]) -> Dict[str, Decimal]:
    """
    Calculate portfolio P&L.
    
    Args:
        positions: Dict mapping symbol to position data
        
    Returns:
        Dict with total, realized, and unrealized P&L
    """
    total_pnl = Decimal('0')
    realized_pnl = Decimal('0')
    unrealized_pnl = Decimal('0')
    
    for position in positions.values():
        quantity = Decimal(str(position.get('quantity', 0)))
        avg_price = Decimal(str(position.get('avg_price', 0)))
        current_price = Decimal(str(position.get('current_price', 0)))
        
        market_value = quantity * current_price
        cost_basis = quantity * avg_price
        
        pnl = market_value - cost_basis
        unrealized_pnl += pnl
        
        if position.get('realized_pnl'):
            realized_pnl += Decimal(str(position.get('realized_pnl', 0)))
    
    total_pnl = realized_pnl + unrealized_pnl
    
    return {
        'total': total_pnl,
        'realized': realized_pnl,
        'unrealized': unrealized_pnl
    }


def calculate_portfolio_weights(positions: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate portfolio weights.
    
    Args:
        positions: Dict mapping symbol to position data
        
    Returns:
        Dict mapping symbol to weight
    """
    if not positions:
        return {}
    
    total_value = float(calculate_portfolio_value(positions))
    if total_value == 0:
        return {}
    
    weights = {}
    for symbol, position in positions.items():
        quantity = float(position.get('quantity', 0))
        price = float(position.get('current_price', 0))
        value = quantity * price
        weights[symbol] = value / total_value
    
    return weights


def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        returns: List of returns
        risk_free_rate: Risk-free rate (annualized)
        
    Returns:
        Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0
    
    # Convert annual risk-free rate to daily
    daily_rf = risk_free_rate / 252
    
    avg_return = np.mean(returns) - daily_rf
    std_return = np.std(returns)
    
    if std_return == 0:
        return 0.0
    
    # Annualize the Sharpe ratio
    return (avg_return / std_return) * np.sqrt(252)


def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sortino ratio.
    
    Args:
        returns: List of returns
        risk_free_rate: Risk-free rate (annualized)
        
    Returns:
        Sortino ratio
    """
    if len(returns) < 2:
        return 0.0
    
    # Convert annual risk-free rate to daily
    daily_rf = risk_free_rate / 252
    
    avg_return = np.mean(returns) - daily_rf
    
    # Calculate downside deviation
    downside_returns = [r for r in returns if r < 0]
    if not downside_returns:
        return float('inf') if avg_return > 0 else 0.0
    
    downside_dev = np.std(downside_returns)
    if downside_dev == 0:
        return 0.0
    
    # Annualize
    return (avg_return / downside_dev) * np.sqrt(252)


def calculate_calmar_ratio(returns: List[float], max_drawdown: float) -> float:
    """
    Calculate Calmar ratio.
    
    Args:
        returns: List of returns
        max_drawdown: Maximum drawdown (negative value)
        
    Returns:
        Calmar ratio
    """
    if max_drawdown >= 0:
        return 0.0
    
    # Annualize returns
    avg_return = np.mean(returns) * 252
    
    return avg_return / abs(max_drawdown)


def calculate_max_drawdown(returns: List[float]) -> float:
    """
    Calculate maximum drawdown.
    
    Args:
        returns: List of returns
        
    Returns:
        Maximum drawdown (negative value)
    """
    if not returns:
        return 0.0
    
    cumulative = np.cumprod(1 + np.array(returns))
    peak = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - peak) / peak
    max_drawdown = np.min(drawdown)
    
    return float(max_drawdown)


def calculate_var(returns: List[float], confidence_level: float = 0.95) -> float:
    """
    Calculate Value at Risk.
    
    Args:
        returns: List of returns
        confidence_level: Confidence level (e.g., 0.95 for 95%)
        
    Returns:
        VaR value
    """
    if not returns:
        return 0.0
    
    return float(np.percentile(returns, (1 - confidence_level) * 100))


def calculate_cvar(returns: List[float], confidence_level: float = 0.95) -> float:
    """
    Calculate Conditional Value at Risk (Expected Shortfall).
    
    Args:
        returns: List of returns
        confidence_level: Confidence level (e.g., 0.95 for 95%)
        
    Returns:
        CVaR value
    """
    if not returns:
        return 0.0
    
    var = calculate_var(returns, confidence_level)
    tail_returns = [r for r in returns if r <= var]
    
    if not tail_returns:
        return var
    
    return float(np.mean(tail_returns))


# =============================================================================
# RISK MANAGEMENT
# =============================================================================

def calculate_beta(
    asset_returns: List[float],
    market_returns: List[float]
) -> float:
    """
    Calculate beta coefficient.
    
    Args:
        asset_returns: Asset returns
        market_returns: Market returns
        
    Returns:
        Beta coefficient
    """
    if len(asset_returns) != len(market_returns) or len(asset_returns) < 2:
        return 0.0
    
    asset_returns = np.array(asset_returns)
    market_returns = np.array(market_returns)
    
    covariance = np.cov(asset_returns, market_returns)[0, 1]
    variance = np.var(market_returns)
    
    if variance == 0:
        return 0.0
    
    return float(covariance / variance)


def calculate_correlation(
    returns1: List[float],
    returns2: List[float]
) -> float:
    """
    Calculate correlation coefficient.
    
    Args:
        returns1: First series of returns
        returns2: Second series of returns
        
    Returns:
        Correlation coefficient
    """
    if len(returns1) != len(returns2) or len(returns1) < 2:
        return 0.0
    
    returns1 = np.array(returns1)
    returns2 = np.array(returns2)
    
    return float(np.corrcoef(returns1, returns2)[0, 1])


def calculate_correlation_matrix(returns_data: Dict[str, List[float]]) -> pd.DataFrame:
    """
    Calculate correlation matrix for multiple assets.
    
    Args:
        returns_data: Dict mapping symbol to returns list
        
    Returns:
        Correlation matrix as DataFrame
    """
    if not returns_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(returns_data)
    return df.corr()


# =============================================================================
# OPTIMIZATION
# =============================================================================

def optimize_portfolio(
    returns_data: Dict[str, List[float]],
    risk_free_rate: float = 0.02,
    method: str = 'max_sharpe'
) -> Dict[str, float]:
    """
    Optimize portfolio allocation.
    
    Args:
        returns_data: Dict mapping symbol to returns list
        risk_free_rate: Risk-free rate
        method: Optimization method ('max_sharpe', 'min_volatility', 'max_return')
        
    Returns:
        Dict mapping symbol to weight
    """
    if not returns_data or len(returns_data) < 2:
        return {}
    
    symbols = list(returns_data.keys())
    returns = np.array([returns_data[s] for s in symbols])
    
    # Calculate mean returns and covariance
    mean_returns = np.mean(returns, axis=1)
    cov_matrix = np.cov(returns)
    n_assets = len(symbols)
    
    def portfolio_stats(weights):
        portfolio_return = np.sum(mean_returns * weights)
        portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe = (portfolio_return - risk_free_rate) / portfolio_volatility
        return portfolio_return, portfolio_volatility, sharpe
    
    def objective_max_sharpe(weights):
        return -portfolio_stats(weights)[2]
    
    def objective_min_volatility(weights):
        return portfolio_stats(weights)[1]
    
    def objective_max_return(weights):
        return -portfolio_stats(weights)[0]
    
    # Constraints and bounds
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    bounds = tuple((0, 1) for _ in range(n_assets))
    initial_weights = np.array([1/n_assets] * n_assets)
    
    objective = {
        'max_sharpe': objective_max_sharpe,
        'min_volatility': objective_min_volatility,
        'max_return': objective_max_return
    }.get(method, objective_max_sharpe)
    
    result = minimize(objective, initial_weights, method='SLSQP',
                     bounds=bounds, constraints=constraints)
    
    if result.success:
        weights = result.x
        return {symbol: float(weight) for symbol, weight in zip(symbols, weights)}
    
    return {}


# =============================================================================
# MARKET STATUS
# =============================================================================

def is_market_open(
    exchange: str = 'NYSE',
    datetime_obj: Optional[datetime] = None
) -> bool:
    """
    Check if the market is open.
    
    Args:
        exchange: Exchange code
        datetime_obj: Datetime to check (default: now)
        
    Returns:
        True if market is open
    """
    if datetime_obj is None:
        datetime_obj = datetime.now()
    
    # Check if weekday
    if datetime_obj.weekday() >= 5:
        return False
    
    # Check if holiday
    if exchange in ['NYSE', 'NASDAQ', 'AMEX']:
        for holiday_name, holiday_date in US_HOLIDAYS.items():
            if datetime_obj.date() == holiday_date.date():
                return False
    
    # Get trading hours
    hours = TRADING_HOURS.get(exchange, TRADING_HOURS['NYSE'])
    
    # Parse times
    open_time = datetime.strptime(hours['open'], '%H:%M').time()
    close_time = datetime.strptime(hours['close'], '%H:%M').time()
    
    current_time = datetime_obj.time()
    
    return open_time <= current_time <= close_time


def get_next_market_open(
    exchange: str = 'NYSE',
    datetime_obj: Optional[datetime] = None
) -> datetime:
    """
    Get the next market open time.
    
    Args:
        exchange: Exchange code
        datetime_obj: Starting datetime (default: now)
        
    Returns:
        Next market open datetime
    """
    if datetime_obj is None:
        datetime_obj = datetime.now()
    
    # Get trading hours
    hours = TRADING_HOURS.get(exchange, TRADING_HOURS['NYSE'])
    open_time_str = hours['open']
    
    # Find next open
    candidate = datetime_obj.replace(
        hour=int(open_time_str[:2]),
        minute=int(open_time_str[3:]),
        second=0,
        microsecond=0
    )
    
    # If current time is after open, try next day
    if candidate <= datetime_obj:
        candidate += timedelta(days=1)
    
    # Find next business day
    while True:
        if is_market_open(exchange, candidate):
            return candidate
        candidate += timedelta(days=1)
    
    return candidate


def get_market_session(
    datetime_obj: Optional[datetime] = None,
    exchange: str = 'NYSE'
) -> str:
    """
    Get current market session.
    
    Args:
        datetime_obj: Datetime to check (default: now)
        exchange: Exchange code
        
    Returns:
        Session name: 'pre_market', 'regular', 'after_hours', 'closed'
    """
    if datetime_obj is None:
        datetime_obj = datetime.now()
    
    # Get hours
    hours = TRADING_HOURS.get(exchange, TRADING_HOURS['NYSE'])
    pre_open = datetime.strptime('04:00', '%H:%M').time()
    open_time = datetime.strptime(hours['open'], '%H:%M').time()
    close_time = datetime.strptime(hours['close'], '%H:%M').time()
    after_close = datetime.strptime('20:00', '%H:%M').time()
    
    current_time = datetime_obj.time()
    
    # Check session
    if pre_open <= current_time < open_time:
        return 'pre_market'
    elif open_time <= current_time <= close_time:
        return 'regular'
    elif close_time < current_time <= after_close:
        return 'after_hours'
    else:
        return 'closed'


# =============================================================================
# DATA FORMATTING
# =============================================================================

def format_price(price: Union[Decimal, float, str], decimals: int = 2) -> str:
    """
    Format price for display.
    
    Args:
        price: Price value
        decimals: Number of decimal places
        
    Returns:
        Formatted price string
    """
    if isinstance(price, str):
        price = Decimal(price)
    elif isinstance(price, float):
        price = Decimal(str(price))
    
    return f"${price:.{decimals}f}"


def format_volume(volume: Union[Decimal, float, str]) -> str:
    """
    Format volume for display.
    
    Args:
        volume: Volume value
        
    Returns:
        Formatted volume string
    """
    if isinstance(volume, str):
        volume = Decimal(volume)
    elif isinstance(price, float):
        volume = Decimal(str(volume))
    
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"{volume / 1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"{volume / 1_000:.2f}K"
    else:
        return str(volume)


def format_percent(value: Union[Decimal, float, str], decimals: int = 2) -> str:
    """
    Format percentage for display.
    
    Args:
        value: Percentage value
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    if isinstance(value, str):
        value = Decimal(value)
    elif isinstance(value, float):
        value = Decimal(str(value))
    
    return f"{value:.{decimals}f}%"


def parse_timestamp(timestamp: Union[str, int, float, datetime]) -> datetime:
    """
    Parse timestamp to datetime.
    
    Args:
        timestamp: Timestamp in various formats
        
    Returns:
        datetime object
    """
    if isinstance(timestamp, datetime):
        return timestamp
    
    if isinstance(timestamp, (int, float)):
        if timestamp > 1e12:  # Milliseconds
            return datetime.fromtimestamp(timestamp / 1000)
        return datetime.fromtimestamp(timestamp)
    
    if isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            try:
                return datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
                except ValueError:
                    return datetime.utcnow()
    
    return datetime.utcnow()


# =============================================================================
# FEE AND COMMISSION CALCULATIONS
# =============================================================================

def calculate_commission(
    order_value: Decimal,
    commission_rate: Decimal = Decimal('0.0065'),  # 0.65% typical
    min_commission: Decimal = Decimal('0.50'),
    max_commission: Optional[Decimal] = None
) -> Decimal:
    """
    Calculate commission for a trade.
    
    Args:
        order_value: Order value
        commission_rate: Commission rate (e.g., 0.0065 for 0.65%)
        min_commission: Minimum commission
        max_commission: Maximum commission (optional)
        
    Returns:
        Commission amount
    """
    commission = order_value * commission_rate
    
    if commission < min_commission:
        commission = min_commission
    
    if max_commission and commission > max_commission:
        commission = max_commission
    
    return commission.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_margin_requirement(
    order_value: Decimal,
    margin_rate: Decimal = Decimal('0.5')  # 50% typical
) -> Decimal:
    """
    Calculate margin requirement.
    
    Args:
        order_value: Order value
        margin_rate: Margin requirement rate
        
    Returns:
        Margin requirement
    """
    return (order_value * margin_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_net_order_value(
    order_value: Decimal,
    commission: Decimal,
    fees: Decimal = Decimal('0')
) -> Decimal:
    """
    Calculate net order value including fees.
    
    Args:
        order_value: Order value
        commission: Commission
        fees: Additional fees
        
    Returns:
        Net order value
    """
    return (order_value + commission + fees).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# =============================================================================
# DIVIDEND AND CORPORATE ACTIONS
# =============================================================================

def calculate_dividend_yield(
    annual_dividend: Decimal,
    current_price: Decimal
) -> Decimal:
    """
    Calculate dividend yield.
    
    Args:
        annual_dividend: Annual dividend per share
        current_price: Current stock price
        
    Returns:
        Dividend yield percentage
    """
    if current_price == 0:
        return Decimal('0')
    return (annual_dividend / current_price * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_adjusted_price(
    price: Decimal,
    split_ratio: Decimal,
    dividend: Optional[Decimal] = None
) -> Decimal:
    """
    Calculate adjusted price for split/dividend.
    
    Args:
        price: Original price
        split_ratio: Split ratio (e.g., 2 for 2:1 split)
        dividend: Dividend amount (optional)
        
    Returns:
        Adjusted price
    """
    adjusted = price / split_ratio
    if dividend:
        adjusted -= dividend
    return adjusted.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


# =============================================================================
# ORDER VALIDATION
# =============================================================================

def validate_order_quantity(
    quantity: Union[Decimal, float],
    min_quantity: Union[Decimal, float] = Decimal('1'),
    max_quantity: Optional[Union[Decimal, float]] = None
) -> Tuple[bool, str]:
    """
    Validate order quantity.
    
    Args:
        quantity: Order quantity
        min_quantity: Minimum quantity
        max_quantity: Maximum quantity
        
    Returns:
        Tuple of (is_valid, message)
    """
    quantity = Decimal(str(quantity))
    min_qty = Decimal(str(min_quantity))
    
    if quantity <= 0:
        return False, "Quantity must be positive"
    
    if quantity < min_qty:
        return False, f"Quantity {quantity} is below minimum {min_qty}"
    
    if max_quantity and quantity > Decimal(str(max_quantity)):
        return False, f"Quantity {quantity} exceeds maximum {max_quantity}"
    
    return True, "Valid"


def validate_order_price(
    price: Union[Decimal, float],
    min_price: Optional[Union[Decimal, float]] = None,
    max_price: Optional[Union[Decimal, float]] = None
) -> Tuple[bool, str]:
    """
    Validate order price.
    
    Args:
        price: Order price
        min_price: Minimum price
        max_price: Maximum price
        
    Returns:
        Tuple of (is_valid, message)
    """
    price = Decimal(str(price))
    
    if price <= 0:
        return False, "Price must be positive"
    
    if min_price and price < Decimal(str(min_price)):
        return False, f"Price {price} is below minimum {min_price}"
    
    if max_price and price > Decimal(str(max_price)):
        return False, f"Price {price} exceeds maximum {max_price}"
    
    return True, "Valid"


# =============================================================================
# MONTE CARLO SIMULATION
# =============================================================================

def monte_carlo_simulation(
    initial_price: Decimal,
    expected_return: float,
    volatility: float,
    days: int = 252,
    simulations: int = 1000,
    random_seed: Optional[int] = None
) -> List[List[float]]:
    """
    Run Monte Carlo simulation for stock prices.
    
    Args:
        initial_price: Initial stock price
        expected_return: Expected annual return
        volatility: Annual volatility
        days: Number of days to simulate
        simulations: Number of simulations
        random_seed: Random seed for reproducibility
        
    Returns:
        List of simulation paths
    """
    if random_seed is not None:
        np.random.seed(random_seed)
    
    initial_price = float(initial_price)
    dt = 1 / 252  # Daily time step
    
    # Generate random returns
    random_returns = np.random.normal(
        (expected_return - 0.5 * volatility ** 2) * dt,
        volatility * np.sqrt(dt),
        (simulations, days)
    )
    
    # Calculate price paths
    price_paths = []
    for i in range(simulations):
        path = [initial_price]
        for j in range(days):
            path.append(path[-1] * np.exp(random_returns[i][j]))
        price_paths.append(path)
    
    return price_paths


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Constants
    'STOCK_EXCHANGES',
    'US_HOLIDAYS',
    'TRADING_HOURS',
    'EXTENDED_HOURS',
    'ORDER_TYPES',
    'POSITION_SIDES',
    'TIME_IN_FORCE',
    
    # Symbol utilities
    'normalize_symbol',
    'validate_symbol',
    'split_symbol',
    'get_exchange_from_symbol',
    
    # Price and volume utilities
    'calculate_pip_value',
    'calculate_position_size',
    'calculate_risk_reward_ratio',
    'calculate_slippage',
    'calculate_slippage_percent',
    
    # Technical indicators
    'calculate_sma',
    'calculate_ema',
    'calculate_rsi',
    'calculate_macd',
    'calculate_bollinger_bands',
    'calculate_atr',
    
    # Portfolio analytics
    'calculate_portfolio_value',
    'calculate_portfolio_pnl',
    'calculate_portfolio_weights',
    'calculate_sharpe_ratio',
    'calculate_sortino_ratio',
    'calculate_calmar_ratio',
    'calculate_max_drawdown',
    'calculate_var',
    'calculate_cvar',
    
    # Risk management
    'calculate_beta',
    'calculate_correlation',
    'calculate_correlation_matrix',
    
    # Optimization
    'optimize_portfolio',
    
    # Market status
    'is_market_open',
    'get_next_market_open',
    'get_market_session',
    
    # Data formatting
    'format_price',
    'format_volume',
    'format_percent',
    'parse_timestamp',
    
    # Fee and commission calculations
    'calculate_commission',
    'calculate_margin_requirement',
    'calculate_net_order_value',
    
    # Dividend and corporate actions
    'calculate_dividend_yield',
    'calculate_adjusted_price',
    
    # Order validation
    'validate_order_quantity',
    'validate_order_price',
    
    # Monte Carlo simulation
    'monte_carlo_simulation',
]

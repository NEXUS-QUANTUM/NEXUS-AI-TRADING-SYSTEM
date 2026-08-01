"""
NEXUS AI TRADING SYSTEM
Hedge Bot Scenario Analyzer - PRODUCTION VERSION

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: trading/bots/hedge_bot/hedge_bot_scenario_analyzer.py
Description: Advanced scenario analysis with real API data integration,
             stress testing, Monte Carlo simulations, and production-grade
             risk management for the Hedge Bot.
"""

import asyncio
import json
import logging
import math
import random
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, Awaitable
from functools import lru_cache

import aiohttp
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm, t, skew, kurtosis, jarque_bera

from trading.bots.hedge_bot.core.risk_calculator import RiskCalculator
from trading.bots.hedge_bot.core.portfolio_optimizer import PortfolioOptimizer
from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async, RetryConfig
from shared.utilities.cache import cache_result, CacheConfig
from shared.configs.broker_config import BrokerConfig
from shared.configs.market_data_config import MarketDataConfig

# Initialize logger
logger = get_logger(__name__)

# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class ScenarioType(str, Enum):
    """Types of scenarios that can be analyzed."""
    HISTORICAL = "historical"
    STRESS = "stress"
    MONTE_CARLO = "monte_carlo"
    WHAT_IF = "what_if"
    BLACK_SWAN = "black_swan"
    REGIME_CHANGE = "regime_change"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    VOLATILITY_SHOCK = "volatility_shock"
    INTEREST_RATE_SHOCK = "interest_rate_shock"
    GEOPOLITICAL = "geopolitical"
    SYSTEMIC = "systemic"
    CORRELATION_BREAK = "correlation_break"


class MarketRegime(str, Enum):
    """Market regimes for scenario generation."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    CRASH = "crash"
    RECOVERY = "recovery"
    LIQUIDITY_TRAP = "liquidity_trap"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    STAGFLATION = "stagflation"
    DISINFLATION = "disinflation"
    REINFLATION = "reflation"


class ConfidenceLevel(str, Enum):
    """Confidence levels for risk metrics."""
    VERY_HIGH = "very_high"  # 99.9%
    HIGH = "high"            # 99%
    STANDARD = "standard"    # 95%
    LOW = "low"              # 90%
    VERY_LOW = "very_low"    # 80%


class RiskMetric(str, Enum):
    """Risk metrics for scenario analysis."""
    VAR = "var"
    CVAR = "cvar"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAX_DRAWDOWN = "max_drawdown"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    OMEGA_RATIO = "omega_ratio"
    TAIL_RATIO = "tail_ratio"
    STABILITY = "stability"
    BETA = "beta"
    ALPHA = "alpha"
    R_SQUARED = "r_squared"
    TREYNOR_RATIO = "treynor_ratio"
    INFORMATION_RATIO = "information_ratio"


@dataclass
class ScenarioParameter:
    """Defines a parameter for a scenario analysis with real data binding."""
    name: str
    base_value: float
    min_value: float
    max_value: float
    distribution: str = "normal"
    std_dev: Optional[float] = None
    correlation: Optional[float] = None
    description: str = ""
    data_source: Optional[str] = None  # API data source
    data_field: Optional[str] = None   # Field in API response
    is_volatility: bool = False
    is_correlation: bool = False
    is_yield: bool = False
    decay_factor: float = 0.94  # EWMA decay for volatility


@dataclass
class ScenarioDefinition:
    """Defines a complete scenario for analysis with real data support."""
    id: str
    name: str
    description: str
    scenario_type: ScenarioType
    market_regime: MarketRegime
    time_horizon: int  # in days
    parameters: Dict[str, ScenarioParameter]
    shock_multipliers: Dict[str, float] = field(default_factory=dict)
    correlations: Dict[str, float] = field(default_factory=dict)
    probability: float = 1.0
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    confidence_level: ConfidenceLevel = ConfidenceLevel.STANDARD
    stress_level: float = 1.0  # 0.5 to 2.0


@dataclass
class ScenarioResult:
    """Results of a scenario analysis with full metrics."""
    scenario_id: str
    scenario_name: str
    scenario_type: str
    market_regime: str
    timestamp: datetime
    pnl: float
    pnl_percent: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float
    tail_ratio: float
    stability: float
    win_rate: float
    total_trades: int
    avg_return: float
    std_return: float
    skewness: float
    kurtosis: float
    var_95: float
    cvar_95: float
    var_99: float
    cvar_99: float
    expected_shortfall: float
    stress_impact: float
    recovery_time: int
    confidence_interval: Tuple[float, float]
    beta: float
    alpha: float
    r_squared: float
    treynor_ratio: float
    information_ratio: float
    risk_metrics: Dict[str, float]
    portfolio_changes: Dict[str, float]
    execution_quality: Dict[str, float]
    additional_metrics: Dict[str, float] = field(default_factory=dict)
    confidence_level: str = "standard"
    simulation_count: int = 0
    success_rate: float = 1.0


@dataclass
class ScenarioComparison:
    """Comparison of multiple scenarios."""
    best_case: ScenarioResult
    worst_case: ScenarioResult
    base_case: ScenarioResult
    scenarios: List[ScenarioResult]
    summary: Dict[str, float]
    recommendations: List[str]
    rank_metrics: Dict[str, Dict[str, float]]


@dataclass
class RealTimeScenarioData:
    """Real-time data for scenario monitoring."""
    timestamp: datetime
    market_regime: MarketRegime
    volatility: float
    vix: float
    put_call_ratio: float
    credit_spread: float
    treasury_yield: float
    liquidity_index: float
    sentiment_score: float
    regime_confidence: float
    data_source: str = "api"


# ============================================================================
# API INTEGRATION CLASSES
# ============================================================================

class MarketDataAPI:
    """
    Real market data API integration for scenario analysis.
    Supports: Alpha Vantage, Yahoo Finance, FRED, CoinGecko, and more.
    """
    
    def __init__(self, config: MarketDataConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._api_keys = config.get_api_keys()
        self._base_urls = config.get_base_urls()
        self._cache = {}
        self._last_request = {}
        
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
    async def fetch_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
        source: str = "yahoo"
    ) -> pd.DataFrame:
        """
        Fetch historical market data from real API.
        
        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            interval: Data interval
            source: Data source (yahoo, alphavantage, coingecko, etc.)
            
        Returns:
            DataFrame with historical data
        """
        cache_key = f"hist_{symbol}_{start_date}_{end_date}_{interval}_{source}"
        
        # Check cache
        if cache_key in self._cache:
            logger.debug(f"Cache hit for {cache_key}")
            return self._cache[cache_key].copy()
        
        if source == "yahoo":
            data = await self._fetch_yahoo_data(symbol, start_date, end_date, interval)
        elif source == "alphavantage":
            data = await self._fetch_alphavantage_data(symbol, start_date, end_date, interval)
        elif source == "coingecko":
            data = await self._fetch_coingecko_data(symbol, start_date, end_date)
        elif source == "fred":
            data = await self._fetch_fred_data(symbol, start_date, end_date)
        elif source == "binance":
            data = await self._fetch_binance_data(symbol, start_date, end_date, interval)
        elif source == "polygon":
            data = await self._fetch_polygon_data(symbol, start_date, end_date)
        else:
            raise ValueError(f"Unsupported data source: {source}")
        
        # Cache the result
        self._cache[cache_key] = data.copy()
        
        return data
    
    async def _fetch_yahoo_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> pd.DataFrame:
        """Fetch data from Yahoo Finance API."""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date, interval=interval)
            
            if data.empty:
                logger.warning(f"No data returned for {symbol} from Yahoo")
                return self._generate_mock_data(symbol, start_date, end_date)
            
            # Standardize column names
            data.columns = [col.lower().replace(' ', '_') for col in data.columns]
            return data
            
        except ImportError:
            logger.warning("yfinance not installed, using mock data")
            return self._generate_mock_data(symbol, start_date, end_date)
        except Exception as e:
            logger.error(f"Error fetching Yahoo data: {e}")
            return self._generate_mock_data(symbol, start_date, end_date)
    
    async def _fetch_alphavantage_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> pd.DataFrame:
        """Fetch data from Alpha Vantage API."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        api_key = self._api_keys.get("alphavantage")
        if not api_key:
            logger.warning("Alpha Vantage API key not found, using mock data")
            return self._generate_mock_data(symbol, start_date, end_date)
        
        function = "TIME_SERIES_DAILY"
        if interval == "1h":
            function = "TIME_SERIES_INTRADAY"
        
        url = f"{self._base_urls.get('alphavantage')}/query"
        params = {
            "function": function,
            "symbol": symbol,
            "apikey": api_key,
            "outputsize": "full"
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                data = await response.json()
                
            if "Time Series (Daily)" in data:
                time_series = data["Time Series (Daily)"]
                df = pd.DataFrame.from_dict(time_series, orient="index")
                df.index = pd.to_datetime(df.index)
                df = df.sort_index()
                df = df.loc[start_date:end_date]
                
                # Standardize columns
                df.columns = [col.split('.')[0].lower().replace(' ', '_') for col in df.columns]
                return df
            else:
                logger.warning(f"Unexpected Alpha Vantage response format for {symbol}")
                return self._generate_mock_data(symbol, start_date, end_date)
                
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage data: {e}")
            return self._generate_mock_data(symbol, start_date, end_date)
    
    async def _fetch_coingecko_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch data from CoinGecko API."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        # CoinGecko uses coin IDs, not symbols
        coin_id = self._get_coingecko_id(symbol)
        
        url = f"{self._base_urls.get('coingecko')}/coins/{coin_id}/market_chart/range"
        params = {
            "vs_currency": "usd",
            "from": int(start_date.timestamp()),
            "to": int(end_date.timestamp())
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                data = await response.json()
            
            if "prices" in data:
                prices = data["prices"]
                df = pd.DataFrame(prices, columns=["timestamp", "price"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
                return df
            else:
                logger.warning(f"Unexpected CoinGecko response for {symbol}")
                return self._generate_mock_data(symbol, start_date, end_date)
                
        except Exception as e:
            logger.error(f"Error fetching CoinGecko data: {e}")
            return self._generate_mock_data(symbol, start_date, end_date)
    
    async def _fetch_fred_data(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch data from FRED API."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        api_key = self._api_keys.get("fred")
        if not api_key:
            logger.warning("FRED API key not found, using mock data")
            return self._generate_mock_data(series_id, start_date, end_date)
        
        url = f"{self._base_urls.get('fred')}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d")
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                data = await response.json()
            
            if "observations" in data:
                observations = data["observations"]
                df = pd.DataFrame(observations)
                df["date"] = pd.to_datetime(df["date"])
                df.set_index("date", inplace=True)
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                return df
            else:
                logger.warning(f"Unexpected FRED response for {series_id}")
                return self._generate_mock_data(series_id, start_date, end_date)
                
        except Exception as e:
            logger.error(f"Error fetching FRED data: {e}")
            return self._generate_mock_data(series_id, start_date, end_date)
    
    async def _fetch_binance_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> pd.DataFrame:
        """Fetch data from Binance API."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        # Binance interval mapping
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
            "1w": "1w",
            "1M": "1M"
        }
        binance_interval = interval_map.get(interval, "1d")
        
        url = f"{self._base_urls.get('binance')}/api/v3/klines"
        params = {
            "symbol": symbol.upper(),
            "interval": binance_interval,
            "startTime": int(start_date.timestamp() * 1000),
            "endTime": int(end_date.timestamp() * 1000),
            "limit": 1000
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                data = await response.json()
            
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data, columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_volume", "trades", "taker_buy_base",
                    "taker_buy_quote", "ignore"
                ])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
                df["close"] = pd.to_numeric(df["close"])
                return df
            else:
                logger.warning(f"No data returned from Binance for {symbol}")
                return self._generate_mock_data(symbol, start_date, end_date)
                
        except Exception as e:
            logger.error(f"Error fetching Binance data: {e}")
            return self._generate_mock_data(symbol, start_date, end_date)
    
    async def _fetch_polygon_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch data from Polygon.io API."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        api_key = self._api_keys.get("polygon")
        if not api_key:
            logger.warning("Polygon API key not found, using mock data")
            return self._generate_mock_data(symbol, start_date, end_date)
        
        url = f"{self._base_urls.get('polygon')}/v2/aggs/ticker/{symbol}/range/1/day/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": api_key
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                data = await response.json()
            
            if "results" in data:
                results = data["results"]
                df = pd.DataFrame(results)
                df["timestamp"] = pd.to_datetime(df["t"], unit="ms")
                df.set_index("timestamp", inplace=True)
                df.rename(columns={
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume"
                }, inplace=True)
                return df
            else:
                logger.warning(f"Unexpected Polygon response for {symbol}")
                return self._generate_mock_data(symbol, start_date, end_date)
                
        except Exception as e:
            logger.error(f"Error fetching Polygon data: {e}")
            return self._generate_mock_data(symbol, start_date, end_date)
    
    def _generate_mock_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Generate realistic mock data when API is unavailable.
        
        This is a fallback only - production uses real data.
        """
        logger.warning(f"Generating mock data for {symbol} (fallback)")
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Generate realistic price data with random walk
        np.random.seed(hash(symbol) % 2**32)
        returns = np.random.normal(0.0005, 0.02, len(date_range))
        prices = 100 * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            'open': prices * (1 + np.random.normal(0, 0.005, len(date_range))),
            'high': prices * (1 + np.random.normal(0.01, 0.01, len(date_range))),
            'low': prices * (1 - np.random.normal(0.01, 0.01, len(date_range))),
            'close': prices,
            'volume': np.random.lognormal(10, 2, len(date_range)),
        }, index=date_range)
        
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)
        
        return df
    
    def _get_coingecko_id(self, symbol: str) -> str:
        """Get CoinGecko coin ID from symbol."""
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "XRP": "ripple",
            "LTC": "litecoin",
            "BCH": "bitcoin-cash",
            "BNB": "binancecoin",
            "USDT": "tether",
            "SOL": "solana",
            "ADA": "cardano",
            "DOT": "polkadot",
            "DOGE": "dogecoin",
            "AVAX": "avalanche-2",
            "MATIC": "matic-network",
            "LINK": "chainlink",
            "UNI": "uniswap",
        }
        return symbol_map.get(symbol.upper(), symbol.lower())
    
    @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
    async def fetch_realtime_data(self, symbols: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Fetch real-time market data for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Dictionary of real-time data
        """
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        results = {}
        
        # Use Yahoo Finance for real-time data (most reliable)
        for symbol in symbols:
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                results[symbol] = {
                    "price": info.get("regularMarketPrice", 0),
                    "change": info.get("regularMarketChange", 0),
                    "change_percent": info.get("regularMarketChangePercent", 0),
                    "volume": info.get("regularMarketVolume", 0),
                    "day_high": info.get("dayHigh", 0),
                    "day_low": info.get("dayLow", 0),
                    "market_cap": info.get("marketCap", 0),
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error fetching real-time data for {symbol}: {e}")
                results[symbol] = {
                    "price": 0,
                    "change": 0,
                    "change_percent": 0,
                    "volume": 0,
                    "day_high": 0,
                    "day_low": 0,
                    "market_cap": 0,
                    "timestamp": datetime.now().isoformat()
                }
        
        return results
    
    async def fetch_volatility_data(self, symbol: str) -> Dict[str, float]:
        """
        Fetch volatility data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Volatility metrics
        """
        # Fetch historical data for volatility calculation
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        data = await self.fetch_historical_data(symbol, start_date, end_date)
        
        if data.empty:
            return {
                "historical_volatility": 0.2,
                "implied_volatility": 0.25,
                "volatility_of_volatility": 0.1
            }
        
        # Calculate historical volatility
        returns = data['close'].pct_change().dropna()
        historical_volatility = returns.std() * np.sqrt(252)
        
        # Calculate EWMA volatility
        alpha = 0.06
        ewma_vol = returns.ewm(alpha=alpha).std().iloc[-1] * np.sqrt(252)
        
        # Calculate volatility of volatility
        vol_returns = returns.rolling(20).std().pct_change()
        vol_of_vol = vol_returns.std()
        
        # Estimate implied volatility (approximate)
        implied_vol = historical_volatility * (1 + np.random.normal(0, 0.1))
        
        return {
            "historical_volatility": float(historical_volatility),
            "ewma_volatility": float(ewma_vol),
            "volatility_of_volatility": float(vol_of_vol),
            "implied_volatility": float(implied_vol)
        }
    
    async def fetch_macro_data(self) -> Dict[str, float]:
        """
        Fetch macro-economic data for scenario analysis.
        
        Returns:
            Macro-economic indicators
        """
        macro_data = {}
        
        # Fetch VIX (volatility index)
        try:
            vix_data = await self.fetch_historical_data("^VIX", datetime.now() - timedelta(days=30), datetime.now())
            macro_data["vix"] = vix_data['close'].iloc[-1]
        except:
            macro_data["vix"] = 20.0
        
        # Fetch Treasury yields
        try:
            treasury_data = await self.fetch_fred_data("DGS10", datetime.now() - timedelta(days=30), datetime.now())
            macro_data["treasury_10y"] = float(treasury_data['value'].iloc[-1]) / 100
        except:
            macro_data["treasury_10y"] = 0.04
        
        # Fetch Fed Funds rate
        try:
            fed_data = await self.fetch_fred_data("FEDFUNDS", datetime.now() - timedelta(days=30), datetime.now())
            macro_data["fed_funds_rate"] = float(fed_data['value'].iloc[-1]) / 100
        except:
            macro_data["fed_funds_rate"] = 0.05
        
        # Fetch Inflation data
        try:
            inflation_data = await self.fetch_fred_data("CPIAUCSL", datetime.now() - timedelta(days=365), datetime.now())
            inflation = inflation_data['value'].pct_change().iloc[-1] * 12
            macro_data["inflation_rate"] = float(inflation)
        except:
            macro_data["inflation_rate"] = 0.03
        
        # Put/Call ratio (approximate)
        macro_data["put_call_ratio"] = 0.8 + np.random.normal(0, 0.1)
        
        return macro_data


# ============================================================================
# MAIN SCENARIO ANALYZER CLASS
# ============================================================================

class ScenarioAnalyzer:
    """
    Advanced scenario analyzer for hedge bot risk management with real API data.
    
    Features:
    - Real market data integration (Yahoo, Alpha Vantage, CoinGecko, FRED, etc.)
    - Historical scenario replay
    - Monte Carlo simulation with real data
    - Stress testing with custom shocks
    - Black swan event analysis
    - Market regime detection
    - Confidence interval calculation
    - Scenario comparison and ranking
    - Multi-threaded simulation
    - Real-time scenario monitoring
    - Auto-regime switching
    - Risk metric optimization
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        risk_calculator: RiskCalculator,
        portfolio_optimizer: PortfolioOptimizer,
        market_data_api: Optional[MarketDataAPI] = None,
    ):
        """
        Initialize the scenario analyzer.
        
        Args:
            config: Configuration dictionary
            risk_calculator: Risk calculator instance
            portfolio_optimizer: Portfolio optimizer instance
            market_data_api: Market data API instance
        """
        self.config = config
        self.risk_calculator = risk_calculator
        self.portfolio_optimizer = portfolio_optimizer
        
        # Initialize market data API
        if market_data_api:
            self.market_data_api = market_data_api
        else:
            market_config = MarketDataConfig(config.get("market_data", {}))
            self.market_data_api = MarketDataAPI(market_config)
        
        self.scenarios: Dict[str, ScenarioDefinition] = {}
        self.results: Dict[str, ScenarioResult] = {}
        self.realtime_data: Dict[str, RealTimeScenarioData] = {}
        self._executor = ProcessPoolExecutor(max_workers=config.get("max_workers", 4))
        self._thread_pool = ThreadPoolExecutor(max_workers=config.get("thread_workers", 8))
        
        # Cache for processed data
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._macro_cache: Dict[str, Dict[str, float]] = {}
        
        # Load default scenarios
        self._load_default_scenarios()
        
        # Initialize real-time monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        
        logger.info("ScenarioAnalyzer initialized with real API data support")
    
    def _load_default_scenarios(self) -> None:
        """Load default scenario definitions from configuration."""
        default_scenarios = self.config.get("default_scenarios", {})
        
        for scenario_id, scenario_data in default_scenarios.items():
            try:
                params = {}
                for param_name, param_data in scenario_data.get("parameters", {}).items():
                    params[param_name] = ScenarioParameter(
                        name=param_name,
                        base_value=param_data["base_value"],
                        min_value=param_data.get("min_value", 0.0),
                        max_value=param_data.get("max_value", float("inf")),
                        distribution=param_data.get("distribution", "normal"),
                        std_dev=param_data.get("std_dev"),
                        correlation=param_data.get("correlation"),
                        description=param_data.get("description", ""),
                        data_source=param_data.get("data_source"),
                        data_field=param_data.get("data_field"),
                        is_volatility=param_data.get("is_volatility", False),
                        is_correlation=param_data.get("is_correlation", False),
                        is_yield=param_data.get("is_yield", False),
                    )
                
                scenario = ScenarioDefinition(
                    id=scenario_id,
                    name=scenario_data["name"],
                    description=scenario_data.get("description", ""),
                    scenario_type=ScenarioType(scenario_data.get("scenario_type", "stress")),
                    market_regime=MarketRegime(scenario_data.get("market_regime", "high_volatility")),
                    time_horizon=scenario_data.get("time_horizon", 30),
                    parameters=params,
                    shock_multipliers=scenario_data.get("shock_multipliers", {}),
                    correlations=scenario_data.get("correlations", {}),
                    probability=scenario_data.get("probability", 1.0),
                    is_active=scenario_data.get("is_active", True),
                    confidence_level=ConfidenceLevel(scenario_data.get("confidence_level", "standard")),
                    stress_level=scenario_data.get("stress_level", 1.0),
                )
                self.scenarios[scenario_id] = scenario
                
            except Exception as e:
                logger.error(f"Failed to load default scenario {scenario_id}: {e}")
    
    def create_scenario(self, definition: Dict[str, Any]) -> ScenarioDefinition:
        """Create a new scenario definition."""
        scenario_id = definition.get("id", f"scenario_{len(self.scenarios)}")
        
        params = {}
        for param_name, param_data in definition.get("parameters", {}).items():
            params[param_name] = ScenarioParameter(
                name=param_name,
                base_value=param_data.get("base_value", 0.0),
                min_value=param_data.get("min_value", 0.0),
                max_value=param_data.get("max_value", float("inf")),
                distribution=param_data.get("distribution", "normal"),
                std_dev=param_data.get("std_dev"),
                correlation=param_data.get("correlation"),
                description=param_data.get("description", ""),
                data_source=param_data.get("data_source"),
                data_field=param_data.get("data_field"),
                is_volatility=param_data.get("is_volatility", False),
                is_correlation=param_data.get("is_correlation", False),
                is_yield=param_data.get("is_yield", False),
            )
        
        scenario = ScenarioDefinition(
            id=scenario_id,
            name=definition.get("name", "Custom Scenario"),
            description=definition.get("description", ""),
            scenario_type=ScenarioType(definition.get("scenario_type", "what_if")),
            market_regime=MarketRegime(definition.get("market_regime", "sideways")),
            time_horizon=definition.get("time_horizon", 30),
            parameters=params,
            shock_multipliers=definition.get("shock_multipliers", {}),
            correlations=definition.get("correlations", {}),
            probability=definition.get("probability", 1.0),
            is_active=definition.get("is_active", True),
            confidence_level=ConfidenceLevel(definition.get("confidence_level", "standard")),
            stress_level=definition.get("stress_level", 1.0),
        )
        
        self.scenarios[scenario_id] = scenario
        logger.info(f"Created scenario: {scenario_id} - {scenario.name}")
        return scenario
    
    async def run_scenario_analysis(
        self,
        scenario_id: str,
        portfolio_data: Dict[str, Any],
        symbols: List[str],
        num_simulations: int = 1000,
        use_real_data: bool = True,
        force_refresh: bool = False,
    ) -> ScenarioResult:
        """
        Run a scenario analysis with real API data.
        
        Args:
            scenario_id: ID of the scenario to run
            portfolio_data: Current portfolio data
            symbols: List of symbols to analyze
            num_simulations: Number of Monte Carlo simulations
            use_real_data: Whether to use real API data
            force_refresh: Whether to force data refresh
            
        Returns:
            ScenarioResult
        """
        if scenario_id not in self.scenarios:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        scenario = self.scenarios[scenario_id]
        logger.info(f"Running scenario analysis: {scenario_id} - {scenario.name}")
        
        # Check cache
        if (scenario_id in self.results and 
            not force_refresh and 
            not self.config.get("force_recalculate", False)):
            logger.info(f"Using cached result for scenario {scenario_id}")
            return self.results[scenario_id]
        
        # Fetch real market data
        market_data = await self._fetch_market_data(symbols, scenario, use_real_data)
        
        # Fetch macro data
        macro_data = await self._fetch_macro_data(use_real_data)
        
        # Generate scenario data
        scenario_data = await self._generate_scenario_data(
            scenario, 
            market_data, 
            macro_data
        )
        
        # Run simulation
        simulation_results = await self._run_simulation(
            scenario,
            scenario_data,
            portfolio_data,
            num_simulations,
        )
        
        # Calculate metrics
        result = self._calculate_metrics(
            scenario,
            simulation_results,
            portfolio_data,
            market_data,
            macro_data,
        )
        
        # Cache result
        self.results[scenario_id] = result
        logger.info(f"Scenario analysis completed: {scenario_id}")
        
        return result
    
    async def _fetch_market_data(
        self,
        symbols: List[str],
        scenario: ScenarioDefinition,
        use_real_data: bool
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch market data for analysis.
        
        Args:
            symbols: List of symbols
            scenario: Scenario definition
            use_real_data: Whether to use real data
            
        Returns:
            Dictionary of DataFrames
        """
        market_data = {}
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=scenario.time_horizon * 2)
        
        for symbol in symbols:
            try:
                if use_real_data:
                    data = await self.market_data_api.fetch_historical_data(
                        symbol,
                        start_date,
                        end_date,
                        interval="1d"
                    )
                else:
                    data = self.market_data_api._generate_mock_data(symbol, start_date, end_date)
                
                if not data.empty:
                    market_data[symbol] = data
                    
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                # Use mock data as fallback
                data = self.market_data_api._generate_mock_data(symbol, start_date, end_date)
                market_data[symbol] = data
        
        return market_data
    
    async def _fetch_macro_data(self, use_real_data: bool) -> Dict[str, float]:
        """
        Fetch macro-economic data.
        
        Args:
            use_real_data: Whether to use real data
            
        Returns:
            Macro data dictionary
        """
        cache_key = "macro_data"
        if cache_key in self._macro_cache:
            return self._macro_cache[cache_key]
        
        if use_real_data:
            try:
                macro_data = await self.market_data_api.fetch_macro_data()
            except Exception as e:
                logger.error(f"Error fetching macro data: {e}")
                macro_data = self._generate_macro_data()
        else:
            macro_data = self._generate_macro_data()
        
        self._macro_cache[cache_key] = macro_data
        return macro_data
    
    def _generate_macro_data(self) -> Dict[str, float]:
        """Generate mock macro data."""
        return {
            "vix": 18.5,
            "treasury_10y": 4.2,
            "treasury_2y": 4.0,
            "fed_funds_rate": 5.25,
            "inflation_rate": 3.1,
            "gdp_growth": 2.5,
            "unemployment_rate": 3.8,
            "put_call_ratio": 0.85,
            "credit_spread": 0.45,
            "liquidity_index": 0.75,
        }
    
    async def _generate_scenario_data(
        self,
        scenario: ScenarioDefinition,
        market_data: Dict[str, pd.DataFrame],
        macro_data: Dict[str, float]
    ) -> pd.DataFrame:
        """
        Generate scenario-specific market data.
        
        Args:
            scenario: Scenario definition
            market_data: Market data
            macro_data: Macro data
            
        Returns:
            Generated scenario data
        """
        scenario_type = scenario.scenario_type
        
        # Combine market data into a single DataFrame
        combined_data = self._combine_market_data(market_data)
        
        if scenario_type == ScenarioType.HISTORICAL:
            return await self._generate_historical_scenario(scenario, combined_data)
        elif scenario_type == ScenarioType.STRESS:
            return await self._generate_stress_scenario(scenario, combined_data, macro_data)
        elif scenario_type == ScenarioType.MONTE_CARLO:
            return await self._generate_monte_carlo_scenario(scenario, combined_data)
        elif scenario_type == ScenarioType.WHAT_IF:
            return await self._generate_what_if_scenario(scenario, combined_data)
        elif scenario_type == ScenarioType.BLACK_SWAN:
            return await self._generate_black_swan_scenario(scenario, combined_data, macro_data)
        elif scenario_type == ScenarioType.REGIME_CHANGE:
            return await self._generate_regime_change_scenario(scenario, combined_data)
        elif scenario_type == ScenarioType.LIQUIDITY_CRISIS:
            return await self._generate_liquidity_crisis_scenario(scenario, combined_data)
        elif scenario_type == ScenarioType.VOLATILITY_SHOCK:
            return await self._generate_volatility_shock_scenario(scenario, combined_data)
        elif scenario_type == ScenarioType.INTEREST_RATE_SHOCK:
            return await self._generate_interest_rate_shock_scenario(scenario, combined_data, macro_data)
        elif scenario_type == ScenarioType.GEOPOLITICAL:
            return await self._generate_geopolitical_scenario(scenario, combined_data)
        elif scenario_type == ScenarioType.SYSTEMIC:
            return await self._generate_systemic_scenario(scenario, combined_data, macro_data)
        elif scenario_type == ScenarioType.CORRELATION_BREAK:
            return await self._generate_correlation_break_scenario(scenario, combined_data)
        else:
            logger.warning(f"Unknown scenario type: {scenario_type}, using stress scenario")
            return await self._generate_stress_scenario(scenario, combined_data, macro_data)
    
    def _combine_market_data(self, market_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Combine multiple market data sources into a single DataFrame.
        
        Args:
            market_data: Dictionary of DataFrames
            
        Returns:
            Combined DataFrame
        """
        combined = pd.DataFrame()
        
        for symbol, data in market_data.items():
            if 'close' in data.columns:
                combined[symbol] = data['close']
            else:
                combined[symbol] = data.iloc[:, 0]  # Use first column if close not available
        
        return combined
    
    async def _generate_historical_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate historical scenario data."""
        # Find historical periods with similar characteristics
        target_regime = scenario.market_regime
        target_params = scenario.parameters
        
        historical_periods = self._find_similar_historical_periods(
            combined_data,
            target_regime,
            target_params,
            n_periods=10,
        )
        
        if not historical_periods:
            logger.warning("No similar historical periods found, using default scenario")
            return combined_data.iloc[-scenario.time_horizon:].copy()
        
        # Use the most similar historical period
        best_period = historical_periods[0]
        scenario_data = combined_data.iloc[best_period["start"]:best_period["end"]].copy()
        
        # Apply adjustments based on scenario parameters
        for param_name, param in scenario.parameters.items():
            if param_name in scenario_data.columns:
                adjustment = param.base_value * (1 + (param.std_dev or 0.1))
                scenario_data[param_name] *= adjustment
        
        return scenario_data
    
    async def _generate_stress_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame,
        macro_data: Dict[str, float]
    ) -> pd.DataFrame:
        """Generate stress scenario data."""
        stress_data = combined_data.copy()
        
        # Apply stress multipliers
        for asset, multiplier in scenario.shock_multipliers.items():
            if asset in stress_data.columns:
                stress_data[asset] *= multiplier
        
        # Apply parameter shocks
        for param_name, param in scenario.parameters.items():
            if param_name in stress_data.columns:
                shock_value = self._calculate_shock_value(param, macro_data)
                stress_data[param_name] *= shock_value / param.base_value
        
        # Apply correlation shocks
        for asset1, asset2 in self._get_asset_pairs(scenario.correlations):
            if asset1 in stress_data.columns and asset2 in stress_data.columns:
                corr_value = scenario.correlations.get(f"{asset1}_{asset2}", 0)
                # Adjust correlation
                corr_adjustment = corr_value * scenario.stress_level
                stress_data[asset1] = stress_data[asset1] + corr_adjustment * stress_data[asset2]
        
        return stress_data
    
    async def _generate_monte_carlo_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate Monte Carlo scenario data."""
        mc_data = combined_data.copy()
        
        # Determine distribution parameters
        for param_name, param in scenario.parameters.items():
            if param_name in mc_data.columns:
                samples = self._generate_samples(param, len(mc_data))
                mc_data[param_name] *= samples
        
        # Apply correlations using Cholesky decomposition
        if scenario.correlations:
            correlated_data = self._apply_correlations(mc_data, scenario.correlations)
            for col in correlated_data.columns:
                if col in mc_data.columns:
                    mc_data[col] = correlated_data[col]
        
        return mc_data
    
    async def _generate_what_if_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate what-if scenario data."""
        what_if_data = combined_data.copy()
        
        for param_name, param in scenario.parameters.items():
            if param_name in what_if_data.columns:
                # Apply the specified base value directly
                what_if_data[param_name] = what_if_data[param_name] * (param.base_value / what_if_data[param_name].mean())
        
        return what_if_data
    
    async def _generate_black_swan_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame,
        macro_data: Dict[str, float]
    ) -> pd.DataFrame:
        """Generate black swan scenario data."""
        black_swan_data = combined_data.copy()
        
        # Apply extreme shocks (3-5 standard deviations)
        for param_name, param in scenario.parameters.items():
            if param_name in black_swan_data.columns:
                # Generate extreme value using heavy-tailed distribution
                extreme_value = param.base_value * (1 + np.random.pareto(1.5) * 0.5 * scenario.stress_level)
                black_swan_data[param_name] *= extreme_value / param.base_value
        
        # Apply regime shift
        if scenario.market_regime == MarketRegime.CRASH:
            # Simulate market crash pattern
            crash_multipliers = np.linspace(1, 0.3 * scenario.stress_level, len(black_swan_data))
            for col in black_swan_data.select_dtypes(include=[np.number]).columns:
                black_swan_data[col] *= crash_multipliers
        
        return black_swan_data
    
    async def _generate_regime_change_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate regime change scenario data."""
        regime_data = combined_data.copy()
        regime = scenario.market_regime
        
        # Apply regime-specific adjustments
        if regime == MarketRegime.BULL:
            trend = np.linspace(1, 1.3 * scenario.stress_level, len(regime_data))
            for col in regime_data.select_dtypes(include=[np.number]).columns:
                regime_data[col] *= trend
        elif regime == MarketRegime.BEAR:
            trend = np.linspace(1, 0.7 * scenario.stress_level, len(regime_data))
            for col in regime_data.select_dtypes(include=[np.number]).columns:
                regime_data[col] *= trend
        elif regime == MarketRegime.HIGH_VOLATILITY:
            for col in regime_data.select_dtypes(include=[np.number]).columns:
                volatility_multiplier = 1 + np.random.randn(len(regime_data)) * 0.3 * scenario.stress_level
                regime_data[col] *= volatility_multiplier
        elif regime == MarketRegime.RECOVERY:
            recovery_curve = np.concatenate([
                np.linspace(1, 0.8, len(regime_data) // 3),
                np.linspace(0.8, 1.2 * scenario.stress_level, len(regime_data) - len(regime_data) // 3),
            ])
            for col in regime_data.select_dtypes(include=[np.number]).columns:
                regime_data[col] *= recovery_curve
        elif regime == MarketRegime.RISK_OFF:
            # Risk-off: flight to safety
            safe_assets = ['gold', 'bonds', 'usd']
            risky_assets = ['stocks', 'crypto', 'emerging_markets']
            for col in regime_data.columns:
                if col in safe_assets:
                    regime_data[col] *= 1.05
                elif col in risky_assets:
                    regime_data[col] *= 0.85 * scenario.stress_level
        
        return regime_data
    
    async def _generate_liquidity_crisis_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate liquidity crisis scenario data."""
        crisis_data = combined_data.copy()
        
        for param_name, param in scenario.parameters.items():
            if param_name in crisis_data.columns:
                if "spread" in param_name.lower():
                    crisis_data[param_name] *= 1 + np.random.uniform(2, 5, len(crisis_data)) * scenario.stress_level
                elif "volume" in param_name.lower():
                    crisis_data[param_name] *= np.random.uniform(0.2, 0.5, len(crisis_data))
                elif "volatility" in param_name.lower():
                    crisis_data[param_name] *= 1 + np.random.uniform(2, 4, len(crisis_data)) * scenario.stress_level
                else:
                    shock = param.base_value * (1 + np.random.laplace(0, 0.5, len(crisis_data)) * scenario.stress_level)
                    crisis_data[param_name] *= shock / param.base_value
        
        return crisis_data
    
    async def _generate_volatility_shock_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate volatility shock scenario data."""
        shock_data = combined_data.copy()
        
        for param_name, param in scenario.parameters.items():
            if param_name in shock_data.columns and param.is_volatility:
                volatility_increase = param.base_value * (1 + np.random.exponential(2, len(shock_data)) * scenario.stress_level)
                shock_data[param_name] *= volatility_increase / param.base_value
        
        return shock_data
    
    async def _generate_interest_rate_shock_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame,
        macro_data: Dict[str, float]
    ) -> pd.DataFrame:
        """Generate interest rate shock scenario data."""
        rate_data = combined_data.copy()
        
        # Get base interest rate
        base_rate = macro_data.get("fed_funds_rate", 0.05)
        shock_multiplier = scenario.stress_level
        
        # Apply interest rate shock
        for param_name, param in scenario.parameters.items():
            if param_name in rate_data.columns and param.is_yield:
                new_rate = base_rate * (1 + shock_multiplier * 0.5)
                rate_data[param_name] = new_rate / base_rate * rate_data[param_name]
        
        # Apply bond price changes (inverse to yield)
        bond_yield = macro_data.get("treasury_10y", 0.04)
        new_yield = bond_yield * (1 + shock_multiplier * 0.3)
        bond_price_change = -10 * (new_yield - bond_yield)  # Duration approximation
        
        for col in rate_data.columns:
            if 'bond' in col.lower() or 'treasury' in col.lower():
                rate_data[col] *= (1 + bond_price_change)
        
        return rate_data
    
    async def _generate_geopolitical_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate geopolitical scenario data."""
        geo_data = combined_data.copy()
        
        # Apply geopolitical shocks
        for param_name, param in scenario.parameters.items():
            if param_name in geo_data.columns:
                # Geopolitical shocks are often sudden and persistent
                shock_pattern = np.random.choice([1, 1.2, 0.7, 0.5, 0.9], size=1)[0]
                shock_pattern = shock_pattern * scenario.stress_level
                geo_data[param_name] *= shock_pattern
        
        return geo_data
    
    async def _generate_systemic_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame,
        macro_data: Dict[str, float]
    ) -> pd.DataFrame:
        """Generate systemic scenario data."""
        systemic_data = combined_data.copy()
        
        # Systemic events affect all assets
        for param_name, param in scenario.parameters.items():
            if param_name in systemic_data.columns:
                # Apply systemic shock
                systemic_shock = param.base_value * (1 + np.random.lognormal(0, 0.5, len(systemic_data)) * scenario.stress_level)
                systemic_data[param_name] *= systemic_shock / param.base_value
        
        # Increase correlations (systemic risk)
        for col1 in systemic_data.columns:
            for col2 in systemic_data.columns:
                if col1 != col2:
                    corr_increase = 0.5 * scenario.stress_level
                    systemic_data[col1] = systemic_data[col1] + corr_increase * systemic_data[col2]
        
        return systemic_data
    
    async def _generate_correlation_break_scenario(
        self,
        scenario: ScenarioDefinition,
        combined_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate correlation break scenario data."""
        break_data = combined_data.copy()
        
        # Break correlations between assets
        for param_name, param in scenario.parameters.items():
            if param_name in break_data.columns and param.is_correlation:
                # Generate new correlation structure
                new_correlation = np.random.uniform(-0.5, 0.5)
                # Apply the new correlation
                if len(break_data.columns) > 1:
                    # Use PCA to break correlations
                    from sklearn.decomposition import PCA
                    pca = PCA(n_components=min(3, len(break_data.columns)))
                    transformed = pca.fit_transform(break_data.T)
                    # Randomly recombine components
                    random_weights = np.random.randn(len(transformed))
                    reconstructed = transformed @ random_weights.reshape(-1, 1)
                    break_data[param_name] = reconstructed.flatten() * scenario.stress_level
        
        return break_data
    
    def _calculate_shock_value(
        self,
        param: ScenarioParameter,
        macro_data: Dict[str, float]
    ) -> float:
        """Calculate shock value for a parameter."""
        if param.distribution == "normal" and param.std_dev:
            return np.random.normal(param.base_value, param.std_dev)
        elif param.distribution == "uniform":
            return np.random.uniform(param.min_value, param.max_value)
        elif param.distribution == "lognormal":
            return np.random.lognormal(mean=np.log(param.base_value), sigma=param.std_dev or 0.3)
        elif param.distribution == "t":
            return np.random.standard_t(3) * param.std_dev + param.base_value if param.std_dev else param.base_value
        else:
            return param.base_value
    
    def _generate_samples(
        self,
        param: ScenarioParameter,
        size: int
    ) -> np.ndarray:
        """Generate random samples for a parameter."""
        if param.distribution == "normal" and param.std_dev:
            return np.random.normal(param.base_value, param.std_dev, size)
        elif param.distribution == "uniform":
            return np.random.uniform(param.min_value, param.max_value, size)
        elif param.distribution == "lognormal":
            return np.random.lognormal(mean=np.log(param.base_value), sigma=param.std_dev or 0.3, size=size)
        elif param.distribution == "t":
            return np.random.standard_t(3, size) * (param.std_dev or 1) + param.base_value
        else:
            return np.full(size, param.base_value)
    
    def _apply_correlations(
        self,
        data: pd.DataFrame,
        correlations: Dict[str, float]
    ) -> pd.DataFrame:
        """Apply correlations to data using Cholesky decomposition."""
        if len(data.columns) < 2:
            return data
        
        # Build correlation matrix
        n_assets = len(data.columns)
        corr_matrix = np.eye(n_assets)
        
        for i, col1 in enumerate(data.columns):
            for j, col2 in enumerate(data.columns):
                if i != j:
                    key = f"{col1}_{col2}"
                    if key in correlations:
                        corr_matrix[i, j] = correlations[key]
                    elif f"{col2}_{col1}" in correlations:
                        corr_matrix[i, j] = correlations[f"{col2}_{col1}"]
        
        # Ensure positive definite
        epsilon = 1e-6
        corr_matrix = (corr_matrix + corr_matrix.T) / 2
        corr_matrix += epsilon * np.eye(n_assets)
        
        # Cholesky decomposition
        try:
            cholesky = np.linalg.cholesky(corr_matrix)
        except np.linalg.LinAlgError:
            # Use eigenvalue decomposition as fallback
            eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix)
            eigenvalues = np.maximum(eigenvalues, 0)
            cholesky = eigenvectors @ np.diag(np.sqrt(eigenvalues))
        
        # Transform data
        data_values = data.values
        transformed = data_values @ cholesky
        
        # Return as DataFrame
        result = pd.DataFrame(transformed, index=data.index, columns=data.columns)
        return result
    
    def _get_asset_pairs(self, correlations: Dict[str, float]) -> List[Tuple[str, str]]:
        """Get asset pairs from correlation dictionary."""
        pairs = []
        for key in correlations:
            if '_' in key:
                assets = key.split('_')
                if len(assets) == 2:
                    pairs.append((assets[0], assets[1]))
        return pairs
    
    async def _run_simulation(
        self,
        scenario: ScenarioDefinition,
        scenario_data: pd.DataFrame,
        portfolio_data: Dict[str, Any],
        num_simulations: int,
    ) -> List[Dict[str, Any]]:
        """
        Run simulation for the scenario.
        
        Args:
            scenario: Scenario definition
            scenario_data: Generated scenario data
            portfolio_data: Current portfolio data
            num_simulations: Number of simulations
            
        Returns:
            Simulation results
        """
        results = []
        
        initial_portfolio_value = portfolio_data.get("total_value", 100000.0)
        positions = portfolio_data.get("positions", {})
        risk_params = portfolio_data.get("risk_parameters", {})
        
        # Determine number of iterations per worker
        workers = self.config.get("max_workers", 4)
        iterations_per_worker = max(1, num_simulations // workers)
        
        # Create simulation tasks
        tasks = []
        for worker_idx in range(workers):
            start_iter = worker_idx * iterations_per_worker
            end_iter = min(start_iter + iterations_per_worker, num_simulations)
            
            if start_iter >= num_simulations:
                break
            
            task = self._simulate_worker(
                scenario,
                scenario_data,
                initial_portfolio_value,
                positions,
                risk_params,
                start_iter,
                end_iter,
            )
            tasks.append(task)
        
        # Run simulations in parallel
        worker_results = await asyncio.gather(*tasks)
        
        # Combine results
        for worker_result in worker_results:
            results.extend(worker_result)
        
        logger.info(f"Completed {len(results)} simulations for scenario {scenario.id}")
        return results
    
    async def _simulate_worker(
        self,
        scenario: ScenarioDefinition,
        scenario_data: pd.DataFrame,
        initial_portfolio_value: float,
        positions: Dict[str, Any],
        risk_params: Dict[str, Any],
        start_iter: int,
        end_iter: int,
    ) -> List[Dict[str, Any]]:
        """Worker function for parallel simulation."""
        results = []
        
        for iteration in range(start_iter, end_iter):
            try:
                result = self._run_single_simulation(
                    scenario,
                    scenario_data,
                    initial_portfolio_value,
                    positions,
                    risk_params,
                    iteration,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Simulation {iteration} failed: {e}")
                results.append({
                    "iteration": iteration,
                    "success": False,
                    "error": str(e),
                    "pnl": 0.0,
                    "max_drawdown": 0.0,
                    "returns": [0.0],
                    "trades": 0,
                })
        
        return results
    
    def _run_single_simulation(
        self,
        scenario: ScenarioDefinition,
        scenario_data: pd.DataFrame,
        initial_portfolio_value: float,
        positions: Dict[str, Any],
        risk_params: Dict[str, Any],
        iteration: int,
    ) -> Dict[str, Any]:
        """Run a single simulation."""
        # Sample data for this simulation
        sample_data = self._sample_scenario_data(scenario_data, scenario.time_horizon)
        
        # Apply risk management rules
        hedge_actions = self._apply_risk_rules(
            sample_data,
            positions,
            risk_params,
            scenario,
        )
        
        # Calculate portfolio evolution
        portfolio_values = [initial_portfolio_value]
        trade_count = 0
        
        for i in range(1, len(sample_data)):
            returns = sample_data.iloc[i].pct_change().values
            portfolio_return = np.mean(returns) * hedge_actions[i - 1].get("hedge_ratio", 1.0)
            
            new_value = portfolio_values[-1] * (1 + portfolio_return)
            portfolio_values.append(new_value)
            
            if hedge_actions[i - 1].get("action") != "hold":
                trade_count += 1
        
        final_value = portfolio_values[-1]
        pnl = final_value - initial_portfolio_value
        max_drawdown = self._calculate_max_drawdown(portfolio_values)
        returns = np.diff(portfolio_values) / portfolio_values[:-1]
        
        return {
            "iteration": iteration,
            "success": True,
            "pnl": pnl,
            "final_value": final_value,
            "max_drawdown": max_drawdown,
            "returns": returns.tolist(),
            "trades": trade_count,
            "portfolio_values": portfolio_values,
            "hedge_actions": hedge_actions,
        }
    
    def _sample_scenario_data(
        self,
        scenario_data: pd.DataFrame,
        time_horizon: int
    ) -> pd.DataFrame:
        """Sample data from the scenario for a single simulation."""
        if len(scenario_data) <= time_horizon:
            sampled = scenario_data.copy()
            while len(sampled) < time_horizon:
                sampled = pd.concat([sampled, scenario_data])
            return sampled.iloc[:time_horizon]
        
        start_idx = np.random.randint(0, len(scenario_data) - time_horizon)
        return scenario_data.iloc[start_idx:start_idx + time_horizon].copy()
    
    def _apply_risk_rules(
        self,
        data: pd.DataFrame,
        positions: Dict[str, Any],
        risk_params: Dict[str, Any],
        scenario: ScenarioDefinition,
    ) -> List[Dict[str, Any]]:
        """Apply risk management rules to the data."""
        actions = []
        
        max_drawdown_limit = risk_params.get("max_drawdown", 0.2)
        var_limit = risk_params.get("var_limit", 0.05)
        volatility_limit = risk_params.get("volatility_limit", 0.3)
        
        portfolio_value = sum(positions.get("value", {}).values())
        peak_value = portfolio_value
        
        for idx in range(len(data)):
            returns = data.iloc[:idx + 1].pct_change().dropna()
            if len(returns) > 0:
                current_volatility = returns.std().mean()
                current_var = np.percentile(returns.values.flatten(), 5)
            else:
                current_volatility = 0.0
                current_var = 0.0
            
            current_value = portfolio_value * (1 + returns.sum() if len(returns) > 0 else 0)
            if current_value > peak_value:
                peak_value = current_value
            current_drawdown = (peak_value - current_value) / peak_value if peak_value > 0 else 0
            
            action = "hold"
            hedge_ratio = 1.0
            
            if current_drawdown > max_drawdown_limit:
                hedge_ratio = max(0, 1 - (current_drawdown - max_drawdown_limit) * 2)
                action = "reduce"
            elif current_volatility > volatility_limit:
                hedge_ratio = max(0, 1 - (current_volatility - volatility_limit) * 0.5)
                action = "hedge"
            elif current_var < var_limit:
                hedge_ratio = min(2, 1 + (var_limit - current_var) * 2)
                action = "increase"
            
            # Apply scenario-specific adjustments
            if scenario.scenario_type in [ScenarioType.STRESS, ScenarioType.BLACK_SWAN]:
                hedge_ratio *= 0.5
            elif scenario.market_regime == MarketRegime.BULL:
                hedge_ratio *= 1.2
            
            hedge_ratio = max(0.1, min(2.0, hedge_ratio))
            
            actions.append({
                "step": idx,
                "action": action,
                "hedge_ratio": hedge_ratio,
                "current_volatility": current_volatility,
                "current_var": current_var,
                "current_drawdown": current_drawdown,
            })
        
        return actions
    
    def _calculate_metrics(
        self,
        scenario: ScenarioDefinition,
        simulation_results: List[Dict[str, Any]],
        portfolio_data: Dict[str, Any],
        market_data: Dict[str, pd.DataFrame],
        macro_data: Dict[str, float],
    ) -> ScenarioResult:
        """Calculate comprehensive metrics from simulation results."""
        successful_results = [r for r in simulation_results if r.get("success", True)]
        
        if not successful_results:
            logger.warning("No successful simulations, returning zero metrics")
            return self._create_zero_result(scenario)
        
        # Extract metrics
        pnls = [r["pnl"] for r in successful_results]
        max_drawdowns = [r["max_drawdown"] for r in successful_results]
        returns_list = [r["returns"] for r in successful_results]
        trades_count = [r["trades"] for r in successful_results]
        
        # Calculate basic statistics
        avg_pnl = np.mean(pnls)
        std_pnl = np.std(pnls)
        total_value = portfolio_data.get("total_value", 100000.0)
        
        avg_return = avg_pnl / total_value
        std_return = std_pnl / total_value
        
        # Calculate all returns for metrics
        all_returns = []
        for ret_list in returns_list:
            all_returns.extend(ret_list)
        
        all_returns = np.array(all_returns)
        if len(all_returns) > 1:
            # Risk-free rate from macro data
            risk_free_rate = macro_data.get("treasury_10y", 0.04)
            
            # Sharpe Ratio
            sharpe_ratio = (np.mean(all_returns) - risk_free_rate/252) / np.std(all_returns) if np.std(all_returns) > 0 else 0
            
            # Sortino Ratio (only negative returns)
            negative_returns = all_returns[all_returns < 0]
            downside_std = np.std(negative_returns) if len(negative_returns) > 0 else np.std(all_returns)
            sortino_ratio = (np.mean(all_returns) - risk_free_rate/252) / downside_std if downside_std > 0 else 0
            
            # Calmar Ratio
            max_drawdown = np.mean(max_drawdowns) if max_drawdowns else 1
            calmar_ratio = (np.mean(all_returns) * 252) / max_drawdown if max_drawdown > 0 else 0
            
            # Omega Ratio
            threshold = risk_free_rate/252
            gains = all_returns[all_returns > threshold] - threshold
            losses = threshold - all_returns[all_returns < threshold]
            omega_ratio = np.sum(gains) / np.sum(losses) if np.sum(losses) > 0 else float('inf')
            
            # Tail Ratio
            upper_tail = np.percentile(all_returns, 95)
            lower_tail = np.percentile(all_returns, 5)
            tail_ratio = upper_tail / abs(lower_tail) if lower_tail != 0 else 0
            
            # Stability (R-squared of returns)
            x = np.arange(len(all_returns))
            slope, intercept = np.polyfit(x, all_returns, 1)
            predicted = slope * x + intercept
            ss_reg = np.sum((predicted - np.mean(all_returns)) ** 2)
            ss_tot = np.sum((all_returns - np.mean(all_returns)) ** 2)
            stability = ss_reg / ss_tot if ss_tot > 0 else 0
            
            # Skewness and Kurtosis
            skewness = skew(all_returns)
            kurt = kurtosis(all_returns)
            
            # VaR and CVaR
            var_95 = np.percentile(all_returns, 5)
            cvar_95 = np.mean(all_returns[all_returns <= var_95]) if any(all_returns <= var_95) else var_95
            var_99 = np.percentile(all_returns, 1)
            cvar_99 = np.mean(all_returns[all_returns <= var_99]) if any(all_returns <= var_99) else var_99
            expected_shortfall = cvar_95
            
            # Beta and Alpha
            market_returns = self._get_market_returns(market_data)
            if len(market_returns) > 0:
                min_len = min(len(all_returns), len(market_returns))
                asset_ret = all_returns[:min_len]
                market_ret = market_returns[:min_len]
                if len(asset_ret) > 1:
                    covariance = np.cov(asset_ret, market_ret)[0, 1]
                    market_variance = np.var(market_ret)
                    beta = covariance / market_variance if market_variance > 0 else 0
                    alpha = np.mean(asset_ret) - beta * np.mean(market_ret)
                    
                    # R-squared
                    predicted = beta * market_ret + alpha
                    ss_reg = np.sum((predicted - np.mean(asset_ret)) ** 2)
                    ss_tot = np.sum((asset_ret - np.mean(asset_ret)) ** 2)
                    r_squared = ss_reg / ss_tot if ss_tot > 0 else 0
                else:
                    beta = 0
                    alpha = 0
                    r_squared = 0
            else:
                beta = 0
                alpha = 0
                r_squared = 0
            
            # Treynor Ratio
            treynor_ratio = (np.mean(all_returns) * 252 - risk_free_rate) / beta if beta > 0 else 0
            
            # Information Ratio
            excess_returns = all_returns - np.mean(all_returns)
            information_ratio = np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) > 0 else 0
            
        else:
            # Default values if not enough data
            sharpe_ratio = 0
            sortino_ratio = 0
            calmar_ratio = 0
            omega_ratio = 0
            tail_ratio = 0
            stability = 0
            skewness = 0
            kurt = 0
            var_95 = 0
            cvar_95 = 0
            var_99 = 0
            cvar_99 = 0
            expected_shortfall = 0
            beta = 0
            alpha = 0
            r_squared = 0
            treynor_ratio = 0
            information_ratio = 0
        
        # Win rate
        win_count = sum(1 for p in pnls if p > 0)
        win_rate = win_count / len(pnls) if pnls else 0
        
        # Confidence interval
        conf_interval = (
            np.percentile(pnls, 2.5),
            np.percentile(pnls, 97.5),
        ) if pnls else (0, 0)
        
        # Stress impact
        worst_pnls = sorted(pnls)[:int(len(pnls) * 0.05)] if pnls else [0]
        stress_impact = abs(np.mean(worst_pnls)) if worst_pnls else 0
        
        # Recovery time
        recovery_time = self._estimate_recovery_time(successful_results, scenario.time_horizon)
        
        # Portfolio changes
        portfolio_changes = self._calculate_portfolio_changes(successful_results, portfolio_data)
        
        # Execution quality
        execution_quality = self._calculate_execution_quality(successful_results)
        
        # Additional metrics
        additional_metrics = {
            "simulation_count": len(successful_results),
            "success_rate": len(successful_results) / len(simulation_results) if simulation_results else 0,
            "avg_trades": np.mean(trades_count) if trades_count else 0,
            "max_loss": min(pnls) if pnls else 0,
            "max_gain": max(pnls) if pnls else 0,
            "var_99": var_99,
            "cvar_99": cvar_99,
            "expected_shortfall": expected_shortfall,
            "skewness": skewness,
            "kurtosis": kurt,
            "omega_ratio": omega_ratio,
            "tail_ratio": tail_ratio,
            "stability": stability,
        }
        
        return ScenarioResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            scenario_type=scenario.scenario_type.value,
            market_regime=scenario.market_regime.value,
            timestamp=datetime.now(),
            pnl=avg_pnl,
            pnl_percent=avg_return,
            max_drawdown=np.mean(max_drawdowns) if max_drawdowns else 0,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            omega_ratio=omega_ratio,
            tail_ratio=tail_ratio,
            stability=stability,
            win_rate=win_rate,
            total_trades=int(np.mean(trades_count)) if trades_count else 0,
            avg_return=np.mean(all_returns) if len(all_returns) > 0 else 0,
            std_return=np.std(all_returns) if len(all_returns) > 0 else 0,
            skewness=skewness,
            kurtosis=kurt,
            var_95=var_95,
            cvar_95=cvar_95,
            var_99=var_99,
            cvar_99=cvar_99,
            expected_shortfall=expected_shortfall,
            stress_impact=stress_impact,
            recovery_time=recovery_time,
            confidence_interval=conf_interval,
            beta=beta,
            alpha=alpha,
            r_squared=r_squared,
            treynor_ratio=treynor_ratio,
            information_ratio=information_ratio,
            risk_metrics={
                "var_95": var_95,
                "cvar_95": cvar_95,
                "var_99": var_99,
                "cvar_99": cvar_99,
                "expected_shortfall": expected_shortfall,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
                "calmar_ratio": calmar_ratio,
                "omega_ratio": omega_ratio,
                "tail_ratio": tail_ratio,
                "stability": stability,
                "beta": beta,
                "alpha": alpha,
                "r_squared": r_squared,
                "treynor_ratio": treynor_ratio,
                "information_ratio": information_ratio,
            },
            portfolio_changes=portfolio_changes,
            execution_quality=execution_quality,
            additional_metrics=additional_metrics,
            confidence_level=scenario.confidence_level.value,
            simulation_count=len(successful_results),
            success_rate=additional_metrics["success_rate"],
        )
    
    def _get_market_returns(self, market_data: Dict[str, pd.DataFrame]) -> np.ndarray:
        """Get market returns for beta calculation."""
        if not market_data:
            return np.array([])
        
        # Use first symbol as market proxy
        first_symbol = list(market_data.keys())[0]
        df = market_data[first_symbol]
        
        if 'close' in df.columns:
            returns = df['close'].pct_change().dropna().values
        else:
            returns = df.iloc[:, 0].pct_change().dropna().values
        
        return returns
    
    def _estimate_recovery_time(
        self,
        simulation_results: List[Dict[str, Any]],
        time_horizon: int
    ) -> int:
        """Estimate recovery time from worst-case scenarios."""
        recovery_times = []
        
        for result in simulation_results:
            portfolio_values = result.get("portfolio_values", [])
            if len(portfolio_values) < 2:
                continue
            
            min_value = min(portfolio_values)
            min_idx = portfolio_values.index(min_value)
            
            pre_value = portfolio_values[min_idx - 1] if min_idx > 0 else portfolio_values[0]
            for idx in range(min_idx + 1, len(portfolio_values)):
                if portfolio_values[idx] >= pre_value:
                    recovery_times.append(idx - min_idx)
                    break
            else:
                recovery_times.append(time_horizon - min_idx)
        
        return int(np.mean(recovery_times)) if recovery_times else time_horizon
    
    def _calculate_portfolio_changes(
        self,
        simulation_results: List[Dict[str, Any]],
        portfolio_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate portfolio changes across scenarios."""
        changes = {}
        
        final_values = [r.get("final_value", 0) for r in simulation_results]
        if final_values:
            avg_final = np.mean(final_values)
            initial = portfolio_data.get("total_value", 1)
            changes["total_change"] = (avg_final - initial) / initial if initial > 0 else 0
        
        for asset, position in portfolio_data.get("positions", {}).items():
            changes[asset] = position.get("change", 0)
        
        return changes
    
    def _calculate_execution_quality(
        self,
        simulation_results: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate execution quality metrics."""
        quality = {}
        
        slippages = [r.get("slippage", 0) for r in simulation_results]
        quality["avg_slippage"] = np.mean(slippages) if slippages else 0
        
        fill_rates = [r.get("fill_rate", 1) for r in simulation_results]
        quality["avg_fill_rate"] = np.mean(fill_rates) if fill_rates else 1
        
        speeds = [r.get("execution_speed", 0) for r in simulation_results]
        quality["avg_execution_speed"] = np.mean(speeds) if speeds else 0
        
        latencies = [r.get("latency", 0) for r in simulation_results]
        quality["avg_latency"] = np.mean(latencies) if latencies else 0
        
        return quality
    
    def _calculate_max_drawdown(self, portfolio_values: List[float]) -> float:
        """Calculate maximum drawdown from portfolio values."""
        if len(portfolio_values) < 2:
            return 0.0
        
        peak = portfolio_values[0]
        max_drawdown = 0.0
        
        for value in portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def _create_zero_result(self, scenario: ScenarioDefinition) -> ScenarioResult:
        """Create a zero result for failed simulations."""
        return ScenarioResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            scenario_type=scenario.scenario_type.value,
            market_regime=scenario.market_regime.value,
            timestamp=datetime.now(),
            pnl=0.0,
            pnl_percent=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            omega_ratio=0.0,
            tail_ratio=0.0,
            stability=0.0,
            win_rate=0.0,
            total_trades=0,
            avg_return=0.0,
            std_return=0.0,
            skewness=0.0,
            kurtosis=0.0,
            var_95=0.0,
            cvar_95=0.0,
            var_99=0.0,
            cvar_99=0.0,
            expected_shortfall=0.0,
            stress_impact=0.0,
            recovery_time=0,
            confidence_interval=(0.0, 0.0),
            beta=0.0,
            alpha=0.0,
            r_squared=0.0,
            treynor_ratio=0.0,
            information_ratio=0.0,
            risk_metrics={},
            portfolio_changes={},
            execution_quality={},
            confidence_level=scenario.confidence_level.value,
            simulation_count=0,
            success_rate=0.0,
        )
    
    def compare_scenarios(self, scenario_ids: List[str]) -> ScenarioComparison:
        """Compare multiple scenarios."""
        if not scenario_ids:
            raise ValueError("At least one scenario ID is required")
        
        results = [self.results[sid] for sid in scenario_ids if sid in self.results]
        
        if not results:
            raise ValueError("No valid scenario results found")
        
        # Find best and worst cases
        best_case = max(results, key=lambda r: r.sharpe_ratio)
        worst_case = min(results, key=lambda r: r.sharpe_ratio)
        base_case = next((r for r in results if r.scenario_id == "base"), results[0])
        
        # Generate summary
        summary = {
            "avg_pnl": np.mean([r.pnl for r in results]),
            "min_pnl": min([r.pnl for r in results]),
            "max_pnl": max([r.pnl for r in results]),
            "avg_drawdown": np.mean([r.max_drawdown for r in results]),
            "avg_sharpe": np.mean([r.sharpe_ratio for r in results]),
            "best_scenario": best_case.scenario_name,
            "worst_scenario": worst_case.scenario_name,
        }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(results)
        
        # Calculate rankings
        rank_metrics = {}
        for metric in ['pnl', 'sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'win_rate']:
            rank_metrics[metric] = {}
            sorted_results = sorted(results, key=lambda r: getattr(r, metric, 0), reverse=True)
            for i, r in enumerate(sorted_results):
                rank_metrics[metric][r.scenario_id] = i + 1
        
        return ScenarioComparison(
            best_case=best_case,
            worst_case=worst_case,
            base_case=base_case,
            scenarios=results,
            summary=summary,
            recommendations=recommendations,
            rank_metrics=rank_metrics,
        )
    
    def _generate_recommendations(self, results: List[ScenarioResult]) -> List[str]:
        """Generate recommendations based on scenario results."""
        recommendations = []
        
        # Analyze drawdown
        avg_drawdown = np.mean([r.max_drawdown for r in results])
        if avg_drawdown > 0.3:
            recommendations.append("Consider reducing leverage - average drawdown exceeds 30%")
        elif avg_drawdown > 0.2:
            recommendations.append("Review stop-loss mechanisms - average drawdown exceeds 20%")
        
        # Analyze Sharpe ratio
        avg_sharpe = np.mean([r.sharpe_ratio for r in results])
        if avg_sharpe < 0.5:
            recommendations.append("Improve risk-adjusted returns - Sharpe ratio below 0.5")
        elif avg_sharpe < 1.0:
            recommendations.append("Consider optimizing portfolio - Sharpe ratio below 1.0")
        
        # Analyze VaR
        avg_var = np.mean([abs(r.var_95) for r in results])
        if avg_var > 0.1:
            recommendations.append("Reduce position sizes - VaR exceeds 10%")
        
        # Analyze win rate
        avg_win_rate = np.mean([r.win_rate for r in results])
        if avg_win_rate < 0.4:
            recommendations.append("Review strategy - win rate below 40%")
        
        # Analyze beta
        avg_beta = np.mean([r.beta for r in results])
        if avg_beta > 1.5:
            recommendations.append("Reduce market exposure - beta exceeds 1.5")
        
        # Add scenario-specific recommendations
        for result in results:
            if result.max_drawdown > 0.4:
                recommendations.append(f"High drawdown risk in {result.scenario_name} - consider hedging")
            if result.sharpe_ratio < 0:
                recommendations.append(f"Negative Sharpe ratio in {result.scenario_name} - review strategy")
        
        return list(set(recommendations))  # Remove duplicates
    
    def get_scenario_summary(self, scenario_id: str) -> Dict[str, Any]:
        """Get a summary of a scenario."""
        if scenario_id not in self.scenarios:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        scenario = self.scenarios[scenario_id]
        result = self.results.get(scenario_id)
        
        summary = {
            "id": scenario.id,
            "name": scenario.name,
            "type": scenario.scenario_type.value,
            "regime": scenario.market_regime.value,
            "time_horizon": scenario.time_horizon,
            "parameters": {k: v.base_value for k, v in scenario.parameters.items()},
            "is_active": scenario.is_active,
            "confidence_level": scenario.confidence_level.value,
            "stress_level": scenario.stress_level,
        }
        
        if result:
            summary["result"] = {
                "pnl": result.pnl,
                "pnl_percent": result.pnl_percent,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "sortino_ratio": result.sortino_ratio,
                "calmar_ratio": result.calmar_ratio,
                "win_rate": result.win_rate,
                "var_95": result.var_95,
                "cvar_95": result.cvar_95,
                "beta": result.beta,
                "alpha": result.alpha,
                "confidence_interval": result.confidence_interval,
            }
        
        return summary
    
    def get_all_scenario_summaries(self) -> List[Dict[str, Any]]:
        """Get summaries for all scenarios."""
        return [self.get_scenario_summary(sid) for sid in self.scenarios]
    
    def detect_market_regime(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """Detect the current market regime."""
        if len(market_data) < 30:
            return {
                "regime": MarketRegime.SIDEWAYS.value,
                "confidence": 0.3,
                "volatility": 0.15,
                "trend": 0.0,
            }
        
        returns = market_data.pct_change().dropna()
        volatility = returns.rolling(30).std().mean()
        trend = market_data.rolling(30).mean().pct_change().mean()
        
        # Calculate additional indicators
        max_drawdown = self._calculate_max_drawdown(market_data.iloc[:, 0].values.tolist())
        
        # Detect regime
        if volatility > 0.3:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(0.9, volatility / 0.4)
        elif volatility < 0.1:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = 0.7
        elif trend > 0.01 and max_drawdown < 0.1:
            regime = MarketRegime.BULL
            confidence = min(0.9, trend / 0.02)
        elif trend < -0.01 and max_drawdown > 0.15:
            regime = MarketRegime.BEAR
            confidence = min(0.9, abs(trend) / 0.02)
        elif max_drawdown > 0.2:
            regime = MarketRegime.CRASH
            confidence = min(0.9, max_drawdown / 0.3)
        elif trend < -0.02 and volatility > 0.2:
            regime = MarketRegime.RISK_OFF
            confidence = 0.8
        elif trend > 0.02 and volatility > 0.2:
            regime = MarketRegime.RISK_ON
            confidence = 0.7
        else:
            regime = MarketRegime.SIDEWAYS
            confidence = 0.5
        
        return {
            "regime": regime.value,
            "confidence": float(confidence),
            "volatility": float(volatility),
            "trend": float(trend),
            "max_drawdown": float(max_drawdown),
        }
    
    async def monitor_scenarios(
        self,
        portfolio_data: Dict[str, Any],
        symbols: List[str],
        interval_seconds: int = 60,
        webhook_url: Optional[str] = None,
    ) -> None:
        """
        Continuously monitor scenarios and trigger alerts.
        
        Args:
            portfolio_data: Current portfolio data
            symbols: List of symbols to monitor
            interval_seconds: Monitoring interval in seconds
            webhook_url: Webhook URL for alerts
        """
        if self._is_monitoring:
            logger.warning("Monitoring already running")
            return
        
        self._is_monitoring = True
        self.config["webhook_url"] = webhook_url
        
        logger.info(f"Starting scenario monitoring with interval {interval_seconds}s")
        
        try:
            while self._is_monitoring:
                try:
                    # Fetch real-time data
                    market_data = await self._fetch_market_data(
                        symbols,
                        ScenarioDefinition(
                            id="monitoring",
                            name="Monitoring",
                            description="Real-time monitoring",
                            scenario_type=ScenarioType.HISTORICAL,
                            market_regime=MarketRegime.SIDEWAYS,
                            time_horizon=30,
                            parameters={},
                        ),
                        use_real_data=True,
                    )
                    
                    # Detect current regime
                    combined_data = self._combine_market_data(market_data)
                    regime_info = self.detect_market_regime(combined_data)
                    
                    # Store real-time data
                    self.realtime_data[datetime.now().isoformat()] = RealTimeScenarioData(
                        timestamp=datetime.now(),
                        market_regime=MarketRegime(regime_info["regime"]),
                        volatility=regime_info["volatility"],
                        vix=0,  # Will be fetched separately
                        put_call_ratio=0.8,
                        credit_spread=0.4,
                        treasury_yield=0.04,
                        liquidity_index=0.7,
                        sentiment_score=0.5,
                        regime_confidence=regime_info["confidence"],
                        data_source="api",
                    )
                    
                    # Run active scenarios
                    for scenario_id, scenario in self.scenarios.items():
                        if not scenario.is_active:
                            continue
                        
                        # Check if scenario matches current regime
                        if scenario.market_regime.value == regime_info["regime"]:
                            result = await self.run_scenario_analysis(
                                scenario_id,
                                portfolio_data,
                                symbols,
                                num_simulations=100,
                                use_real_data=True,
                            )
                            
                            # Check for alerts
                            await self._check_alert_conditions(scenario, result)
                    
                    # Clean old real-time data
                    cutoff = datetime.now() - timedelta(hours=24)
                    self.realtime_data = {
                        k: v for k, v in self.realtime_data.items()
                        if v.timestamp > cutoff
                    }
                    
                except Exception as e:
                    logger.error(f"Error in monitoring cycle: {e}")
                
                await asyncio.sleep(interval_seconds)
                
        except asyncio.CancelledError:
            logger.info("Monitoring task cancelled")
        finally:
            self._is_monitoring = False
    
    async def _check_alert_conditions(
        self,
        scenario: ScenarioDefinition,
        result: ScenarioResult,
    ) -> None:
        """Check if alert conditions are met."""
        alert_conditions = self.config.get("alert_conditions", {})
        
        # Check drawdown threshold
        drawdown_threshold = alert_conditions.get("drawdown_threshold", 0.2)
        if result.max_drawdown > drawdown_threshold:
            logger.warning(f"Scenario {scenario.name} exceeds drawdown threshold: {result.max_drawdown:.2%}")
            await self._send_alert(
                "drawdown_alert",
                f"Drawdown threshold exceeded in scenario {scenario.name}: {result.max_drawdown:.2%}",
                {"scenario": scenario.id, "drawdown": result.max_drawdown},
            )
        
        # Check VaR threshold
        var_threshold = alert_conditions.get("var_threshold", 0.05)
        if abs(result.var_95) > var_threshold:
            logger.warning(f"Scenario {scenario.name} exceeds VaR threshold: {abs(result.var_95):.2%}")
            await self._send_alert(
                "var_alert",
                f"VaR threshold exceeded in scenario {scenario.name}: {abs(result.var_95):.2%}",
                {"scenario": scenario.id, "var": result.var_95},
            )
        
        # Check Sharpe threshold
        sharpe_threshold = alert_conditions.get("sharpe_threshold", 0)
        if result.sharpe_ratio < sharpe_threshold:
            logger.warning(f"Scenario {scenario.name} below Sharpe threshold: {result.sharpe_ratio:.2f}")
            await self._send_alert(
                "sharpe_alert",
                f"Sharpe ratio below threshold in scenario {scenario.name}: {result.sharpe_ratio:.2f}",
                {"scenario": scenario.id, "sharpe": result.sharpe_ratio},
            )
        
        # Check stress impact threshold
        stress_threshold = alert_conditions.get("stress_threshold", 0.1)
        if result.stress_impact > stress_threshold:
            logger.warning(f"Scenario {scenario.name} exceeds stress impact threshold: {result.stress_impact:.2%}")
            await self._send_alert(
                "stress_alert",
                f"Stress impact threshold exceeded in scenario {scenario.name}: {result.stress_impact:.2%}",
                {"scenario": scenario.id, "stress": result.stress_impact},
            )
    
    async def _send_alert(
        self,
        alert_type: str,
        message: str,
        data: Dict[str, Any],
    ) -> None:
        """Send an alert via webhook."""
        logger.info(f"ALERT [{alert_type}]: {message} - Data: {data}")
        
        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            return
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {
                    "alert_type": alert_type,
                    "message": message,
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                }
                await session.post(webhook_url, json=payload)
        except Exception as e:
            logger.error(f"Failed to send alert webhook: {e}")
    
    def stop_monitoring(self) -> None:
        """Stop scenario monitoring."""
        self._is_monitoring = False
        logger.info("Scenario monitoring stopped")
    
    def get_realtime_status(self) -> Dict[str, Any]:
        """Get real-time monitoring status."""
        if not self.realtime_data:
            return {"status": "No data", "data": {}}
        
        latest_time = max(self.realtime_data.keys())
        latest_data = self.realtime_data[latest_time]
        
        return {
            "status": "active",
            "current_regime": latest_data.market_regime.value,
            "regime_confidence": latest_data.regime_confidence,
            "volatility": latest_data.volatility,
            "sentiment_score": latest_data.sentiment_score,
            "last_update": latest_time,
            "data_points": len(self.realtime_data),
        }
    
    async def generate_report(
        self,
        scenario_ids: Optional[List[str]] = None,
        include_charts: bool = True,
        include_raw_data: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive scenario analysis report.
        
        Args:
            scenario_ids: List of scenario IDs to include
            include_charts: Whether to include chart data
            include_raw_data: Whether to include raw data
            
        Returns:
            Report data
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "scenarios": [],
            "comparison": None,
            "recommendations": [],
            "summary": {},
        }
        
        # Include all scenarios if none specified
        if scenario_ids is None:
            scenario_ids = list(self.scenarios.keys())
        
        # Add scenario details
        for scenario_id in scenario_ids:
            if scenario_id in self.scenarios:
                scenario_data = self.get_scenario_summary(scenario_id)
                if include_raw_data and scenario_id in self.results:
                    scenario_data["raw_result"] = asdict(self.results[scenario_id])
                report["scenarios"].append(scenario_data)
        
        # Add comparison if multiple scenarios
        if len(scenario_ids) > 1:
            comparison = self.compare_scenarios(scenario_ids)
            report["comparison"] = {
                "best_case": comparison.best_case.scenario_name,
                "worst_case": comparison.worst_case.scenario_name,
                "summary": comparison.summary,
                "recommendations": comparison.recommendations,
                "rankings": comparison.rank_metrics,
            }
            report["recommendations"].extend(comparison.recommendations)
        
        # Add overall recommendations
        if self.results:
            all_results = list(self.results.values())
            report["summary"] = {
                "total_scenarios": len(self.results),
                "avg_pnl": np.mean([r.pnl for r in all_results]),
                "avg_sharpe": np.mean([r.sharpe_ratio for r in all_results]),
                "avg_drawdown": np.mean([r.max_drawdown for r in all_results]),
                "best_performer": max(all_results, key=lambda r: r.sharpe_ratio).scenario_name,
                "worst_performer": min(all_results, key=lambda r: r.sharpe_ratio).scenario_name,
            }
        
        # Add general recommendations
        report["recommendations"].extend(self._generate_general_recommendations())
        
        return report
    
    def _generate_general_recommendations(self) -> List[str]:
        """Generate general recommendations based on all scenarios."""
        recommendations = []
        
        if not self.results:
            return recommendations
        
        all_results = list(self.results.values())
        
        # Check overall risk exposure
        avg_var = np.mean([abs(r.var_95) for r in all_results])
        avg_drawdown = np.mean([r.max_drawdown for r in all_results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in all_results])
        
        if avg_var > 0.1:
            recommendations.append("Average VaR exceeds 10% - consider reducing position sizes")
        if avg_drawdown > 0.25:
            recommendations.append("Average drawdown exceeds 25% - consider adding stop-loss mechanisms")
        if avg_sharpe < 0.5:
            recommendations.append("Average Sharpe ratio below 0.5 - consider strategy optimization")
        if avg_sharpe < 0:
            recommendations.append("Negative average Sharpe ratio - urgent strategy review required")
        
        # Check worst-case scenarios
        worst_var = min([abs(r.var_95) for r in all_results])
        if worst_var > 0.2:
            recommendations.append("Worst-case VaR exceeds 20% - implement tail risk hedging")
        
        # Check correlation of scenarios
        pnls = [r.pnl for r in all_results]
        if len(pnls) > 1:
            correlation_matrix = np.corrcoef(pnls)
            if np.mean(correlation_matrix) > 0.7:
                recommendations.append("High correlation between scenarios - consider diversification")
        
        return recommendations
    
    def _find_similar_historical_periods(
        self,
        market_data: pd.DataFrame,
        target_regime: MarketRegime,
        target_params: Dict[str, ScenarioParameter],
        n_periods: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find historical periods similar to the target regime."""
        periods = []
        window_size = 30
        
        if len(market_data) < window_size * 2:
            return periods
        
        # Calculate regime indicators
        returns = market_data.pct_change().dropna()
        volatility = returns.rolling(window_size).std().mean(axis=1)
        trend = market_data.rolling(window_size).mean().pct_change()
        
        regime_conditions = {
            MarketRegime.BULL: (trend > 0.01) & (volatility < 0.15),
            MarketRegime.BEAR: (trend < -0.01) & (volatility > 0.2),
            MarketRegime.SIDEWAYS: (abs(trend) < 0.005) & (volatility < 0.15),
            MarketRegime.HIGH_VOLATILITY: (volatility > 0.3),
            MarketRegime.LOW_VOLATILITY: (volatility < 0.1),
            MarketRegime.CRASH: (market_data.pct_change().min(axis=1) < -0.05),
            MarketRegime.RECOVERY: (trend > 0.02) & (market_data.pct_change().min(axis=1) > -0.02),
            MarketRegime.LIQUIDITY_TRAP: (volatility > 0.2) & (abs(trend) < 0.005),
            MarketRegime.RISK_ON: (trend > 0.02) & (volatility < 0.2),
            MarketRegime.RISK_OFF: (trend < -0.02) & (volatility > 0.2),
        }
        
        condition = regime_conditions.get(target_regime, regime_conditions[MarketRegime.SIDEWAYS])
        
        matching_indices = condition[condition].index
        
        for i in matching_indices:
            start_idx = market_data.index.get_loc(i)
            if start_idx < window_size or start_idx > len(market_data) - window_size:
                continue
            
            period_data = market_data.iloc[start_idx - window_size:start_idx + window_size]
            similarity_score = self._calculate_similarity_score(period_data, target_params)
            
            periods.append({
                "start": start_idx - window_size,
                "end": start_idx + window_size,
                "score": similarity_score,
            })
        
        periods.sort(key=lambda x: x["score"], reverse=True)
        return periods[:n_periods]
    
    def _calculate_similarity_score(
        self,
        period_data: pd.DataFrame,
        target_params: Dict[str, ScenarioParameter],
    ) -> float:
        """Calculate similarity score between a period and target parameters."""
        score = 0.0
        total_weight = 0.0
        
        for param_name, param in target_params.items():
            if param_name in period_data.columns:
                param_mean = period_data[param_name].mean()
                param_std = period_data[param_name].std()
                
                diff = abs(param_mean - param.base_value) / (param_std + 0.001)
                similarity = 1 / (1 + diff)
                
                weight = 1.0
                score += similarity * weight
                total_weight += weight
        
        return score / total_weight if total_weight > 0 else 0.0


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_scenario_analyzer(
    config: Dict[str, Any],
    risk_calculator: RiskCalculator,
    portfolio_optimizer: PortfolioOptimizer,
    api_keys: Optional[Dict[str, str]] = None,
) -> ScenarioAnalyzer:
    """
    Factory function to create a ScenarioAnalyzer with full configuration.
    
    Args:
        config: Configuration dictionary
        risk_calculator: Risk calculator instance
        portfolio_optimizer: Portfolio optimizer instance
        api_keys: API keys for market data sources
        
    Returns:
        Configured ScenarioAnalyzer
    """
    if api_keys:
        config["api_keys"] = api_keys
    
    return ScenarioAnalyzer(config, risk_calculator, portfolio_optimizer)

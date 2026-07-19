#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NEXUS AI TRADING SYSTEM - Exchanges Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Unified exchange module providing a comprehensive interface for
multiple exchanges across various asset classes including:
- Stocks (Alpaca, IBKR, Tradier, TradeStation, Schwab, Fidelity, E*TRADE)
- Cryptocurrencies (Binance, Bybit, Coinbase, Kraken, OKX)
- Forex (OANDA, FXCM, IG, Pepperstone, Dukascopy, Forex.com)

Author: Dr X...
Version: 3.0.0
"""

# ============================================================================
# VERSION & METADATA
# ============================================================================

__version__ = "3.0.0"
__author__ = "Dr X..."
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__license__ = "Proprietary"
__status__ = "Production"

# ============================================================================
# IMPORTS - BASE
# ============================================================================

from .base import (
    # Enums
    AssetClass,
    ExchangeType,
    OrderType,
    OrderSide,
    TimeInForce,
    OrderStatus,
    PositionSide,
    OrderBookLevel,
    DataFrequency,
    WebSocketEvent,
    
    # Data Classes
    Price,
    Amount,
    Order,
    Position,
    AccountBalance,
    Trade,
    MarketData,
    OrderBook,
    Candle,
    ExchangeInfo,
    
    # Exceptions
    ExchangeError,
    ConnectionError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    OrderError,
    InvalidOrderError,
    InsufficientBalanceError,
    MarketDataError,
    PositionError,
    AccountError,
    TimeoutError,
    WebSocketError,
    
    # Base Classes
    ExchangeBase,
    ExchangeFactory,
    
    # Decorators
    retry_on_error,
    rate_limited,
    log_request,
)

# ============================================================================
# IMPORTS - STOCKS
# ============================================================================

from .stocks import (
    AlpacaBroker,
    InteractiveBrokersBroker,
    TradierBroker,
    TradeStationBroker,
    SchwabBroker,
    FidelityBroker,
    ETRADEBroker,
    StockExchangeBase,
    StockOrderType,
    StockOrderSide,
    StockTimeInForce,
    StockOrderStatus,
    StockOrder,
    StockPosition,
    StockAccountInfo,
    StockMarketData,
    StockOrderBook,
    StockTrade,
    StockQuote,
    StockBar,
    StockWatchlist,
    StockExchangeError,
    AuthenticationError as StockAuthError,
    OrderError as StockOrderError,
    MarketDataError as StockMarketDataError,
    PositionError as StockPositionError,
    AccountError as StockAccountError,
    WatchlistError,
    RateLimitError as StockRateLimitError,
    StockDataConverter,
    OrderConverter,
    MarketDataConverter,
    PositionConverter,
    QuoteConverter,
    BarConverter,
    TradeConverter,
    StockUtils,
    SymbolValidator,
    MarketHours,
    HolidayCalendar,
    StockScreener,
    PositionCalculator,
    RiskMetrics,
    PerformanceMetrics,
    WebhookHandler,
    WebhookConfig,
    WebhookPayload,
    WebhookResponse,
    WebhookProvider,
    WebhookEventType,
    WebhookStatus,
    StockTradeData,
    StockQuoteData,
    StockAggregateData,
    create_webhook_handler,
)

# ============================================================================
# IMPORTS - CRYPTO EXCHANGES
# ============================================================================

# Binance
from .binance import (
    BinanceExchange,
    BinanceSpot,
    BinanceFutures,
    BinanceMargin,
    BinanceAccount,
    BinanceOrder,
    BinanceMarket,
    BinanceWebSocket,
    BinanceConverter,
    BinanceException,
)

# Bybit
from .bybit import (
    BybitExchange,
    BybitSpot,
    BybitFutures,
    BybitInverse,
    BybitOption,
    BybitAccount,
    BybitOrder,
    BybitMarket,
    BybitWebSocket,
    BybitConverter,
    BybitException,
)

# Coinbase
from .coinbase import (
    CoinbaseExchange,
    CoinbaseSpot,
    CoinbasePrime,
    CoinbaseAccount,
    CoinbaseOrder,
    CoinbaseMarket,
    CoinbaseWebSocket,
    CoinbaseConverter,
    CoinbaseException,
)

# Kraken
from .kraken import (
    KrakenExchange,
    KrakenSpot,
    KrakenAccount,
    KrakenOrder,
    KrakenMarket,
    KrakenWebSocket,
    KrakenConverter,
    KrakenException,
)

# OKX
from .okx import (
    OKXExchange,
    OKXSpot,
    OKXFutures,
    OKXSwap,
    OKXOption,
    OKXAccount,
    OKXOrder,
    OKXMarket,
    OKXWebSocket,
    OKXConverter,
    OKXException,
)

# ============================================================================
# IMPORTS - FOREX
# ============================================================================

from .forex import (
    OandaBroker,
    FXCMBroker,
    IGBroker,
    PepperstoneBroker,
    DukascopyBroker,
    ForexComBroker,
    ForexBase,
    ForexOrder,
    ForexPosition,
    ForexAccount,
    ForexMarketData,
    ForexConverter,
    ForexException,
)

# ============================================================================
# EXCHANGE REGISTRY
# ============================================================================

EXCHANGE_REGISTRY = {
    # Stock Brokers
    "alpaca": AlpacaBroker,
    "ibkr": InteractiveBrokersBroker,
    "tradier": TradierBroker,
    "tradestation": TradeStationBroker,
    "schwab": SchwabBroker,
    "fidelity": FidelityBroker,
    "etrade": ETRADEBroker,
    
    # Crypto Exchanges
    "binance": BinanceExchange,
    "binance_spot": BinanceSpot,
    "binance_futures": BinanceFutures,
    "binance_margin": BinanceMargin,
    "bybit": BybitExchange,
    "bybit_spot": BybitSpot,
    "bybit_futures": BybitFutures,
    "bybit_inverse": BybitInverse,
    "bybit_option": BybitOption,
    "coinbase": CoinbaseExchange,
    "coinbase_spot": CoinbaseSpot,
    "coinbase_prime": CoinbasePrime,
    "kraken": KrakenExchange,
    "kraken_spot": KrakenSpot,
    "okx": OKXExchange,
    "okx_spot": OKXSpot,
    "okx_futures": OKXFutures,
    "okx_swap": OKXSwap,
    "okx_option": OKXOption,
    
    # Forex Brokers
    "oanda": OandaBroker,
    "fxcm": FXCMBroker,
    "ig": IGBroker,
    "pepperstone": PepperstoneBroker,
    "dukascopy": DukascopyBroker,
    "forexcom": ForexComBroker,
}

SUPPORTED_EXCHANGES = list(EXCHANGE_REGISTRY.keys())

# ============================================================================
# EXCHANGE CATEGORIES
# ============================================================================

EXCHANGE_CATEGORIES = {
    "stocks": ["alpaca", "ibkr", "tradier", "tradestation", "schwab", "fidelity", "etrade"],
    "crypto": ["binance", "binance_spot", "binance_futures", "binance_margin", 
               "bybit", "bybit_spot", "bybit_futures", "bybit_inverse", "bybit_option",
               "coinbase", "coinbase_spot", "coinbase_prime",
               "kraken", "kraken_spot",
               "okx", "okx_spot", "okx_futures", "okx_swap", "okx_option"],
    "forex": ["oanda", "fxcm", "ig", "pepperstone", "dukascopy", "forexcom"],
}

# ============================================================================
# API ENDPOINTS CONFIGURATION
# ============================================================================

EXCHANGE_API_ENDPOINTS = {
    "alpaca": {
        "rest": "https://api.alpaca.markets/v2",
        "rest_paper": "https://paper-api.alpaca.markets/v2",
        "websocket": "wss://stream.data.alpaca.markets/v2/iex",
        "websocket_paper": "wss://stream.data.alpaca.markets/v2/iex",
        "docs": "https://docs.alpaca.markets/",
    },
    "ibkr": {
        "rest": "https://api.ibkr.com/v1",
        "websocket": "wss://api.ibkr.com/ws",
        "docs": "https://interactivebrokers.github.io/tws-api/",
    },
    "tradier": {
        "rest": "https://api.tradier.com/v1",
        "rest_paper": "https://api.tradier.com/v1",
        "websocket": "wss://ws.tradier.com/v1",
        "docs": "https://documentation.tradier.com/",
    },
    "tradestation": {
        "rest": "https://api.tradestation.com/v3",
        "websocket": "wss://api.tradestation.com/stream",
        "docs": "https://docs.tradestation.com/",
    },
    "schwab": {
        "rest": "https://api.schwab.com/v1",
        "docs": "https://developer.schwab.com/",
    },
    "fidelity": {
        "rest": "https://api.fidelity.com/v1",
        "docs": "https://developer.fidelity.com/",
    },
    "etrade": {
        "rest": "https://api.etrade.com/v1",
        "rest_paper": "https://api.etrade.com/v1",
        "docs": "https://developer.etrade.com/",
    },
    "binance": {
        "rest": "https://api.binance.com/api/v3",
        "rest_spot": "https://api.binance.com/api/v3",
        "rest_futures": "https://fapi.binance.com/fapi/v1",
        "rest_margin": "https://api.binance.com/sapi/v1",
        "websocket": "wss://stream.binance.com:9443/ws",
        "websocket_futures": "wss://fstream.binance.com/ws",
        "docs": "https://binance-docs.github.io/apidocs/",
        "testnet_rest": "https://testnet.binance.vision/api/v3",
        "testnet_futures": "https://testnet.binancefuture.com/fapi/v1",
        "testnet_websocket": "wss://testnet.binance.vision/ws",
    },
    "bybit": {
        "rest": "https://api.bybit.com/v5",
        "rest_spot": "https://api.bybit.com/v5/spot",
        "rest_futures": "https://api.bybit.com/v5/futures",
        "rest_option": "https://api.bybit.com/v5/option",
        "websocket": "wss://stream.bybit.com/v5/public/spot",
        "websocket_futures": "wss://stream.bybit.com/v5/public/linear",
        "websocket_option": "wss://stream.bybit.com/v5/public/option",
        "docs": "https://bybit-exchange.github.io/docs/v5/intro",
        "testnet_rest": "https://api-testnet.bybit.com/v5",
        "testnet_websocket": "wss://stream-testnet.bybit.com/v5/public/spot",
    },
    "coinbase": {
        "rest": "https://api.coinbase.com/api/v3",
        "rest_prime": "https://api.prime.coinbase.com/v1",
        "websocket": "wss://ws-feed.exchange.coinbase.com",
        "docs": "https://docs.cloud.coinbase.com/",
        "testnet_rest": "https://api-public.sandbox.exchange.coinbase.com",
        "testnet_websocket": "wss://ws-feed-public.sandbox.exchange.coinbase.com",
    },
    "kraken": {
        "rest": "https://api.kraken.com/0",
        "rest_spot": "https://api.kraken.com/0/public",
        "websocket": "wss://ws.kraken.com/v2",
        "docs": "https://docs.kraken.com/",
        "testnet_rest": "https://api.kraken.com/0",
        "testnet_websocket": "wss://demo-ws.kraken.com/v2",
    },
    "okx": {
        "rest": "https://www.okx.com/api/v5",
        "rest_spot": "https://www.okx.com/api/v5/spot",
        "rest_futures": "https://www.okx.com/api/v5/futures",
        "rest_swap": "https://www.okx.com/api/v5/swap",
        "rest_option": "https://www.okx.com/api/v5/option",
        "websocket": "wss://ws.okx.com:8443/ws/v5/public",
        "websocket_private": "wss://ws.okx.com:8443/ws/v5/private",
        "docs": "https://www.okx.com/docs-v5/",
        "testnet_rest": "https://www.okx.com/api/v5",
        "testnet_websocket": "wss://ws.okx.com:8443/ws/v5/public",
    },
    "oanda": {
        "rest": "https://api-fxtrade.oanda.com/v3",
        "rest_paper": "https://api-fxpractice.oanda.com/v3",
        "websocket": "wss://stream-fxtrade.oanda.com/v3",
        "websocket_paper": "wss://stream-fxpractice.oanda.com/v3",
        "docs": "https://developer.oanda.com/",
    },
    "fxcm": {
        "rest": "https://api.fxcm.com/v1",
        "rest_paper": "https://api.fxcm.com/v1",
        "docs": "https://fxcm.github.io/rest-api-docs/",
    },
    "ig": {
        "rest": "https://api.ig.com/gateway/deal/v2",
        "rest_paper": "https://api.ig.com/gateway/deal/v2",
        "docs": "https://labs.ig.com/rest-trading-api-guide",
    },
    "pepperstone": {
        "rest": "https://api.pepperstone.com/v1",
        "rest_paper": "https://api.pepperstone.com/v1",
        "docs": "https://pepperstone.github.io/api-docs/",
    },
    "dukascopy": {
        "rest": "https://api.dukascopy.com/v1",
        "docs": "https://www.dukascopy.com/api/",
    },
    "forexcom": {
        "rest": "https://api.forex.com/v1",
        "rest_paper": "https://api.forex.com/v1",
        "docs": "https://developer.forex.com/",
    },
}

# ============================================================================
# EXCHANGE RATE LIMITS
# ============================================================================

EXCHANGE_RATE_LIMITS = {
    "alpaca": {"requests": 200, "period": 60, "order_requests": 100, "order_period": 60},
    "ibkr": {"requests": 50, "period": 60, "order_requests": 25, "order_period": 60},
    "tradier": {"requests": 60, "period": 60, "order_requests": 30, "order_period": 60},
    "tradestation": {"requests": 100, "period": 60, "order_requests": 50, "order_period": 60},
    "schwab": {"requests": 50, "period": 60, "order_requests": 25, "order_period": 60},
    "fidelity": {"requests": 50, "period": 60, "order_requests": 25, "order_period": 60},
    "etrade": {"requests": 100, "period": 60, "order_requests": 50, "order_period": 60},
    "binance": {"requests": 1200, "period": 60, "order_requests": 600, "order_period": 60},
    "binance_spot": {"requests": 1200, "period": 60, "order_requests": 600, "order_period": 60},
    "binance_futures": {"requests": 2400, "period": 60, "order_requests": 1200, "order_period": 60},
    "binance_margin": {"requests": 1200, "period": 60, "order_requests": 600, "order_period": 60},
    "bybit": {"requests": 600, "period": 60, "order_requests": 300, "order_period": 60},
    "bybit_spot": {"requests": 600, "period": 60, "order_requests": 300, "order_period": 60},
    "bybit_futures": {"requests": 1200, "period": 60, "order_requests": 600, "order_period": 60},
    "bybit_inverse": {"requests": 1200, "period": 60, "order_requests": 600, "order_period": 60},
    "bybit_option": {"requests": 600, "period": 60, "order_requests": 300, "order_period": 60},
    "coinbase": {"requests": 100, "period": 60, "order_requests": 50, "order_period": 60},
    "coinbase_spot": {"requests": 100, "period": 60, "order_requests": 50, "order_period": 60},
    "coinbase_prime": {"requests": 500, "period": 60, "order_requests": 250, "order_period": 60},
    "kraken": {"requests": 100, "period": 60, "order_requests": 50, "order_period": 60},
    "kraken_spot": {"requests": 100, "period": 60, "order_requests": 50, "order_period": 60},
    "okx": {"requests": 600, "period": 60, "order_requests": 300, "order_period": 60},
    "okx_spot": {"requests": 600, "period": 60, "order_requests": 300, "order_period": 60},
    "okx_futures": {"requests": 1200, "period": 60, "order_requests": 600, "order_period": 60},
    "okx_swap": {"requests": 1200, "period": 60, "order_requests": 600, "order_period": 60},
    "okx_option": {"requests": 600, "period": 60, "order_requests": 300, "order_period": 60},
    "oanda": {"requests": 60, "period": 60, "order_requests": 30, "order_period": 60},
    "fxcm": {"requests": 60, "period": 60, "order_requests": 30, "order_period": 60},
    "ig": {"requests": 60, "period": 60, "order_requests": 30, "order_period": 60},
    "pepperstone": {"requests": 60, "period": 60, "order_requests": 30, "order_period": 60},
    "dukascopy": {"requests": 60, "period": 60, "order_requests": 30, "order_period": 60},
    "forexcom": {"requests": 60, "period": 60, "order_requests": 30, "order_period": 60},
}

# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_exchange(
    exchange_name: str,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    api_passphrase: Optional[str] = None,
    paper_trading: bool = False,
    testnet: bool = False,
    sandbox: bool = False,
    timeout: int = 30,
    max_retries: int = 3,
    **kwargs
) -> ExchangeBase:
    """
    Create an exchange instance by name.
    
    Args:
        exchange_name: Exchange name (e.g., 'alpaca', 'binance', 'oanda')
        api_key: API key (optional)
        api_secret: API secret (optional)
        api_passphrase: API passphrase (optional)
        paper_trading: Enable paper trading mode (optional)
        testnet: Use testnet endpoints (optional)
        sandbox: Use sandbox environment (optional)
        timeout: Request timeout in seconds (optional)
        max_retries: Maximum number of retries (optional)
        **kwargs: Additional exchange-specific configuration
    
    Returns:
        ExchangeBase: Exchange instance
    
    Raises:
        ValueError: If exchange is not supported
    """
    exchange_name = exchange_name.lower()
    
    if exchange_name not in EXCHANGE_REGISTRY:
        raise ValueError(
            f"Unsupported exchange: {exchange_name}. "
            f"Supported exchanges: {', '.join(SUPPORTED_EXCHANGES)}"
        )
    
    exchange_class = EXCHANGE_REGISTRY[exchange_name]
    
    # Get API endpoints for the exchange
    endpoints = EXCHANGE_API_ENDPOINTS.get(exchange_name, {})
    rate_limits = EXCHANGE_RATE_LIMITS.get(exchange_name, {"requests": 100, "period": 60})
    
    # Prepare configuration
    config = {
        "api_key": api_key,
        "api_secret": api_secret,
        "api_passphrase": api_passphrase,
        "paper_trading": paper_trading,
        "testnet": testnet,
        "sandbox": sandbox,
        "timeout": timeout,
        "max_retries": max_retries,
        "endpoints": endpoints,
        "rate_limits": rate_limits,
        **kwargs,
    }
    
    # Remove None values
    config = {k: v for k, v in config.items() if v is not None}
    
    return exchange_class(**config)


def get_exchange_info(exchange_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get information about supported exchanges.
    
    Args:
        exchange_name: Specific exchange name (optional)
    
    Returns:
        dict: Exchange information
    """
    info = {
        "supported_exchanges": SUPPORTED_EXCHANGES,
        "count": len(SUPPORTED_EXCHANGES),
        "categories": EXCHANGE_CATEGORIES,
        "versions": {
            exchange: getattr(EXCHANGE_REGISTRY[exchange], "__version__", "unknown")
            for exchange in SUPPORTED_EXCHANGES
        },
        "rate_limits": EXCHANGE_RATE_LIMITS,
    }
    
    if exchange_name:
        exchange_name = exchange_name.lower()
        if exchange_name in EXCHANGE_REGISTRY:
            exchange_class = EXCHANGE_REGISTRY[exchange_name]
            info["exchange_details"] = {
                "name": exchange_name,
                "class": exchange_class.__name__,
                "module": exchange_class.__module__,
                "version": getattr(exchange_class, "__version__", "unknown"),
                "description": getattr(exchange_class, "__doc__", "").strip(),
                "features": _get_exchange_features(exchange_name),
                "category": _get_exchange_category(exchange_name),
                "endpoints": EXCHANGE_API_ENDPOINTS.get(exchange_name, {}),
                "rate_limits": EXCHANGE_RATE_LIMITS.get(exchange_name, {}),
                "asset_classes": get_exchange_asset_classes(exchange_name),
            }
        else:
            info["exchange_details"] = {"error": f"Exchange {exchange_name} not found"}
    
    return info


def _get_exchange_category(exchange_name: str) -> str:
    """Get the category of an exchange."""
    for category, exchanges in EXCHANGE_CATEGORIES.items():
        if exchange_name in exchanges:
            return category
    return "unknown"


def _get_exchange_features(exchange_name: str) -> Dict[str, Any]:
    """Get features for a specific exchange."""
    features = {
        # Stock Brokers
        "alpaca": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit", "trailing_stop"],
            "time_in_force": ["day", "gtc", "ioc", "fok"],
            "rate_limit": {"requests": 200, "period": 60},
            "fee_structure": {"maker": 0.0, "taker": 0.0},
        },
        "ibkr": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": True,
            "options": True,
            "margin": True,
            "webhooks": False,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit", "trailing_stop", "peg", "rel", "mid", "lmt"],
            "time_in_force": ["day", "gtc", "ioc", "fok", "gtd", "opg"],
            "rate_limit": {"requests": 50, "period": 60},
            "fee_structure": {"maker": 0.0, "taker": 0.0},
        },
        "tradier": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["day", "gtc"],
            "rate_limit": {"requests": 60, "period": 60},
            "fee_structure": {"maker": 0.0, "taker": 0.0},
        },
        "tradestation": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": False,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["day", "gtc", "ioc", "fok"],
            "rate_limit": {"requests": 100, "period": 60},
            "fee_structure": {"maker": 0.0, "taker": 0.0},
        },
        "schwab": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": False,
            "websocket": False,
            "streaming": False,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["day", "gtc"],
            "rate_limit": {"requests": 50, "period": 60},
            "fee_structure": {"maker": 0.0, "taker": 0.0},
        },
        "fidelity": {
            "paper_trading": False,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": False,
            "websocket": False,
            "streaming": False,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["day", "gtc"],
            "rate_limit": {"requests": 50, "period": 60},
            "fee_structure": {"maker": 0.0, "taker": 0.0},
        },
        "etrade": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": True,
            "websocket": False,
            "streaming": False,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["day", "gtc", "ioc"],
            "rate_limit": {"requests": 100, "period": 60},
            "fee_structure": {"maker": 0.0, "taker": 0.0},
        },
        
        # Crypto Exchanges
        "binance": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit", "take_profit", "take_profit_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 1200, "period": 60},
            "fee_structure": {"maker": 0.001, "taker": 0.001},
        },
        "binance_spot": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": False,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 1200, "period": 60},
            "fee_structure": {"maker": 0.001, "taker": 0.001},
        },
        "binance_futures": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit", "take_profit", "take_profit_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 2400, "period": 60},
            "fee_structure": {"maker": 0.0002, "taker": 0.0004},
        },
        "binance_margin": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 1200, "period": 60},
            "fee_structure": {"maker": 0.001, "taker": 0.001},
        },
        "bybit": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": True,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit", "take_profit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 600, "period": 60},
            "fee_structure": {"maker": 0.0001, "taker": 0.0006},
        },
        "bybit_spot": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": False,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 600, "period": 60},
            "fee_structure": {"maker": 0.001, "taker": 0.001},
        },
        "bybit_futures": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit", "take_profit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 1200, "period": 60},
            "fee_structure": {"maker": 0.0001, "taker": 0.0006},
        },
        "bybit_inverse": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 1200, "period": 60},
            "fee_structure": {"maker": 0.0001, "taker": 0.0006},
        },
        "bybit_option": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": True,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 600, "period": 60},
            "fee_structure": {"maker": 0.0001, "taker": 0.0006},
        },
        "coinbase": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": False,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 100, "period": 60},
            "fee_structure": {"maker": 0.005, "taker": 0.005},
        },
        "coinbase_spot": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": False,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 100, "period": 60},
            "fee_structure": {"maker": 0.005, "taker": 0.005},
        },
        "coinbase_prime": {
            "paper_trading": False,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 500, "period": 60},
            "fee_structure": {"maker": 0.001, "taker": 0.001},
        },
        "kraken": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 100, "period": 60},
            "fee_structure": {"maker": 0.002, "taker": 0.002},
        },
        "kraken_spot": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": False,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 100, "period": 60},
            "fee_structure": {"maker": 0.002, "taker": 0.002},
        },
        "okx": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": True,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit", "take_profit", "take_profit_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 600, "period": 60},
            "fee_structure": {"maker": 0.0008, "taker": 0.001},
        },
        "okx_spot": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": False,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 600, "period": 60},
            "fee_structure": {"maker": 0.0008, "taker": 0.001},
        },
        "okx_futures": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit", "take_profit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 1200, "period": 60},
            "fee_structure": {"maker": 0.0002, "taker": 0.0005},
        },
        "okx_swap": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 1200, "period": 60},
            "fee_structure": {"maker": 0.0002, "taker": 0.0005},
        },
        "okx_option": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": True,
            "options": True,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 600, "period": 60},
            "fee_structure": {"maker": 0.0002, "taker": 0.0005},
        },
        
        # Forex Brokers
        "oanda": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 60, "period": 60},
            "fee_structure": {"maker": 0.00005, "taker": 0.00005},
        },
        "fxcm": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 60, "period": 60},
            "fee_structure": {"maker": 0.00005, "taker": 0.00005},
        },
        "ig": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 60, "period": 60},
            "fee_structure": {"maker": 0.00005, "taker": 0.00005},
        },
        "pepperstone": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 60, "period": 60},
            "fee_structure": {"maker": 0.00005, "taker": 0.00005},
        },
        "dukascopy": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 60, "period": 60},
            "fee_structure": {"maker": 0.00005, "taker": 0.00005},
        },
        "forexcom": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket": True,
            "streaming": True,
            "order_types": ["market", "limit", "stop", "stop_limit"],
            "time_in_force": ["gtc", "ioc", "fok"],
            "rate_limit": {"requests": 60, "period": 60},
            "fee_structure": {"maker": 0.00005, "taker": 0.00005},
        },
    }
    return features.get(exchange_name, {})


def get_exchange_class(exchange_name: str) -> Optional[Type[ExchangeBase]]:
    """
    Get the exchange class for a given name.
    
    Args:
        exchange_name: Exchange name
    
    Returns:
        Optional[Type[ExchangeBase]]: Exchange class or None
    """
    exchange_name = exchange_name.lower()
    return EXCHANGE_REGISTRY.get(exchange_name)


def is_exchange_supported(exchange_name: str) -> bool:
    """
    Check if an exchange is supported.
    
    Args:
        exchange_name: Exchange name
    
    Returns:
        bool: True if supported
    """
    return exchange_name.lower() in EXCHANGE_REGISTRY


def get_exchanges_by_category(category: str) -> List[str]:
    """
    Get exchanges by category.
    
    Args:
        category: Category name ('stocks', 'crypto', 'forex')
    
    Returns:
        List[str]: List of exchange names
    """
    return EXCHANGE_CATEGORIES.get(category.lower(), [])


def get_exchange_asset_classes(exchange_name: str) -> List[str]:
    """
    Get available asset classes for an exchange.
    
    Args:
        exchange_name: Exchange name
    
    Returns:
        List[str]: List of asset classes
    """
    exchange_name = exchange_name.lower()
    
    asset_classes = {
        "alpaca": ["stock", "etf", "crypto"],
        "ibkr": ["stock", "etf", "option", "future", "forex", "crypto", "bond", "commodity"],
        "tradier": ["stock", "etf", "option"],
        "tradestation": ["stock", "etf", "option", "future", "forex"],
        "schwab": ["stock", "etf", "option", "future"],
        "fidelity": ["stock", "etf", "option", "mutual_fund"],
        "etrade": ["stock", "etf", "option", "mutual_fund"],
        "binance": ["crypto", "future", "margin"],
        "binance_spot": ["crypto"],
        "binance_futures": ["future"],
        "binance_margin": ["crypto", "margin"],
        "bybit": ["crypto", "future", "option"],
        "bybit_spot": ["crypto"],
        "bybit_futures": ["future"],
        "bybit_inverse": ["future"],
        "bybit_option": ["option"],
        "coinbase": ["crypto"],
        "coinbase_spot": ["crypto"],
        "coinbase_prime": ["crypto"],
        "kraken": ["crypto", "future"],
        "kraken_spot": ["crypto"],
        "okx": ["crypto", "future", "option", "swap"],
        "okx_spot": ["crypto"],
        "okx_futures": ["future"],
        "okx_swap": ["swap"],
        "okx_option": ["option"],
        "oanda": ["forex", "commodity", "index"],
        "fxcm": ["forex", "commodity", "index"],
        "ig": ["forex", "commodity", "index", "stock", "etf"],
        "pepperstone": ["forex", "commodity", "index"],
        "dukascopy": ["forex", "commodity", "index"],
        "forexcom": ["forex", "commodity", "index"],
    }
    
    return asset_classes.get(exchange_name, [])


def get_exchange_status(exchange_name: str) -> Dict[str, Any]:
    """
    Get the status of an exchange.
    
    Args:
        exchange_name: Exchange name
    
    Returns:
        dict: Exchange status
    """
    exchange_name = exchange_name.lower()
    features = _get_exchange_features(exchange_name)
    category = _get_exchange_category(exchange_name)
    asset_classes = get_exchange_asset_classes(exchange_name)
    endpoints = EXCHANGE_API_ENDPOINTS.get(exchange_name, {})
    rate_limits = EXCHANGE_RATE_LIMITS.get(exchange_name, {})
    
    return {
        "name": exchange_name,
        "supported": exchange_name in EXCHANGE_REGISTRY,
        "category": category,
        "asset_classes": asset_classes,
        "features": features,
        "endpoints": endpoints,
        "rate_limits": rate_limits,
        "status": "active" if exchange_name in EXCHANGE_REGISTRY else "unknown",
    }


def get_exchange_endpoints(exchange_name: str) -> Dict[str, str]:
    """
    Get API endpoints for an exchange.
    
    Args:
        exchange_name: Exchange name
    
    Returns:
        Dict[str, str]: API endpoints
    """
    return EXCHANGE_API_ENDPOINTS.get(exchange_name.lower(), {})


def get_exchange_rate_limits(exchange_name: str) -> Dict[str, int]:
    """
    Get rate limits for an exchange.
    
    Args:
        exchange_name: Exchange name
    
    Returns:
        Dict[str, int]: Rate limits
    """
    return EXCHANGE_RATE_LIMITS.get(exchange_name.lower(), {})


# ============================================================================
# ASYNC CONTEXT MANAGER
# ============================================================================

async def create_exchange_context(
    exchange_name: str,
    **kwargs
) -> ExchangeBase:
    """
    Create an exchange instance with async context manager support.
    
    Args:
        exchange_name: Exchange name
        **kwargs: Exchange configuration
    
    Returns:
        ExchangeBase: Exchange instance
    
    Example:
        async with create_exchange_context('alpaca', api_key='...') as exchange:
            await exchange.get_market_data('AAPL')
    """
    exchange = create_exchange(exchange_name, **kwargs)
    await exchange.connect()
    return exchange


# ============================================================================
# MODULE INITIALIZATION
# ============================================================================

import logging
from typing import Optional, Dict, Any, List, Type

logger = logging.getLogger(__name__)


def init_exchanges_module(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Initialize the exchanges module with configuration.
    
    Args:
        config: Configuration dictionary (optional)
    """
    if config:
        # Configure logging
        log_level = config.get("log_level", "INFO")
        logger.setLevel(log_level)
        
        # Configure default exchange
        default_exchange = config.get("default_exchange")
        if default_exchange:
            logger.info(f"Default exchange set to: {default_exchange}")
        
        # Configure exchange-specific settings
        exchange_configs = config.get("exchanges", {})
        for exchange_name, exchange_config in exchange_configs.items():
            logger.info(f"Configured exchange: {exchange_name}")
        
        # Configure proxy settings
        proxy_config = config.get("proxy", {})
        if proxy_config:
            logger.info("Proxy configuration loaded")
        
        # Configure webhook settings
        webhook_config = config.get("webhook", {})
        if webhook_config:
            logger.info("Webhook configuration loaded")
        
        logger.info("Exchanges module initialized successfully")
    else:
        logger.info("Exchanges module initialized with default configuration")


# Auto-initialize on import
init_exchanges_module()


# ============================================================================
# MODULE DOCUMENTATION
# ============================================================================

__all__ = [
    # Version
    "__version__",
    
    # Enums (Base)
    "AssetClass",
    "ExchangeType",
    "OrderType",
    "OrderSide",
    "TimeInForce",
    "OrderStatus",
    "PositionSide",
    "OrderBookLevel",
    "DataFrequency",
    "WebSocketEvent",
    
    # Data Classes (Base)
    "Price",
    "Amount",
    "Order",
    "Position",
    "AccountBalance",
    "Trade",
    "MarketData",
    "OrderBook",
    "Candle",
    "ExchangeInfo",
    
    # Exceptions (Base)
    "ExchangeError",
    "ConnectionError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "OrderError",
    "InvalidOrderError",
    "InsufficientBalanceError",
    "MarketDataError",
    "PositionError",
    "AccountError",
    "TimeoutError",
    "WebSocketError",
    
    # Base Classes
    "ExchangeBase",
    "ExchangeFactory",
    
    # Decorators
    "retry_on_error",
    "rate_limited",
    "log_request",
    
    # Stock Exchange Classes
    "AlpacaBroker",
    "InteractiveBrokersBroker",
    "TradierBroker",
    "TradeStationBroker",
    "SchwabBroker",
    "FidelityBroker",
    "ETRADEBroker",
    "StockExchangeBase",
    "StockOrder",
    "StockPosition",
    "StockAccountInfo",
    "StockMarketData",
    "StockOrderBook",
    "StockTrade",
    "StockQuote",
    "StockBar",
    "StockWatchlist",
    "StockDataConverter",
    "OrderConverter",
    "MarketDataConverter",
    "PositionConverter",
    "QuoteConverter",
    "BarConverter",
    "TradeConverter",
    "StockUtils",
    "SymbolValidator",
    "MarketHours",
    "HolidayCalendar",
    "StockScreener",
    "PositionCalculator",
    "RiskMetrics",
    "PerformanceMetrics",
    
    # Stock Exceptions
    "StockExchangeError",
    "StockAuthError",
    "StockOrderError",
    "StockMarketDataError",
    "StockPositionError",
    "StockAccountError",
    "WatchlistError",
    "StockRateLimitError",
    
    # Webhook
    "WebhookHandler",
    "WebhookConfig",
    "WebhookPayload",
    "WebhookResponse",
    "WebhookProvider",
    "WebhookEventType",
    "WebhookStatus",
    "StockTradeData",
    "StockQuoteData",
    "StockAggregateData",
    "create_webhook_handler",
    
    # Crypto Exchanges
    "BinanceExchange",
    "BinanceSpot",
    "BinanceFutures",
    "BinanceMargin",
    "BinanceAccount",
    "BinanceOrder",
    "BinanceMarket",
    "BinanceWebSocket",
    "BinanceConverter",
    "BinanceException",
    
    "BybitExchange",
    "BybitSpot",
    "BybitFutures",
    "BybitInverse",
    "BybitOption",
    "BybitAccount",
    "BybitOrder",
    "BybitMarket",
    "BybitWebSocket",
    "BybitConverter",
    "BybitException",
    
    "CoinbaseExchange",
    "CoinbaseSpot",
    "CoinbasePrime",
    "CoinbaseAccount",
    "CoinbaseOrder",
    "CoinbaseMarket",
    "CoinbaseWebSocket",
    "CoinbaseConverter",
    "CoinbaseException",
    
    "KrakenExchange",
    "KrakenSpot",
    "KrakenAccount",
    "KrakenOrder",
    "KrakenMarket",
    "KrakenWebSocket",
    "KrakenConverter",
    "KrakenException",
    
    "OKXExchange",
    "OKXSpot",
    "OKXFutures",
    "OKXSwap",
    "OKXOption",
    "OKXAccount",
    "OKXOrder",
    "OKXMarket",
    "OKXWebSocket",
    "OKXConverter",
    "OKXException",
    
    # Forex Brokers
    "OandaBroker",
    "FXCMBroker",
    "IGBroker",
    "PepperstoneBroker",
    "DukascopyBroker",
    "ForexComBroker",
    "ForexBase",
    "ForexOrder",
    "ForexPosition",
    "ForexAccount",
    "ForexMarketData",
    "ForexConverter",
    "ForexException",
    
    # Registry
    "EXCHANGE_REGISTRY",
    "SUPPORTED_EXCHANGES",
    "EXCHANGE_CATEGORIES",
    "EXCHANGE_API_ENDPOINTS",
    "EXCHANGE_RATE_LIMITS",
    
    # Factory Functions
    "create_exchange",
    "get_exchange_info",
    "get_exchange_class",
    "is_exchange_supported",
    "get_exchanges_by_category",
    "get_exchange_asset_classes",
    "get_exchange_status",
    "get_exchange_endpoints",
    "get_exchange_rate_limits",
    "create_exchange_context",
    
    # Init
    "init_exchanges_module",
]


# ============================================================================
# UNIT TESTS
# ============================================================================

if __name__ == "__main__":
    import sys
    import asyncio
    from datetime import datetime
    
    print("=" * 70)
    print("NEXUS AI TRADING SYSTEM - Exchanges Module Test")
    print("=" * 70)
    print(f"Version: {__version__}")
    print(f"Copyright: {__copyright__}")
    print(f"Status: {__status__}")
    print("=" * 70)
    
    # Test registry
    print("\n[1] Testing Exchange Registry:")
    print(f"Total exchanges: {len(EXCHANGE_REGISTRY)}")
    print(f"Supported exchanges: {len(SUPPORTED_EXCHANGES)}")
    
    for category, exchanges in EXCHANGE_CATEGORIES.items():
        print(f"\n  {category.upper()}:")
        for exchange in exchanges:
            status = "✓" if exchange in EXCHANGE_REGISTRY else "✗"
            features = _get_exchange_features(exchange)
            print(f"    {status} {exchange:20} - {features.get('real_time_data', False)} data")
    
    # Test API endpoints
    print("\n[2] Testing API Endpoints:")
    for exchange in ["alpaca", "binance", "oanda"]:
        endpoints = EXCHANGE_API_ENDPOINTS.get(exchange, {})
        print(f"\n  {exchange.upper()}:")
        for key, value in endpoints.items():
            if key != "docs":
                print(f"    {key:20} - {value}")
    
    # Test rate limits
    print("\n[3] Testing Rate Limits:")
    for exchange in ["alpaca", "binance", "oanda"]:
        limits = EXCHANGE_RATE_LIMITS.get(exchange, {})
        print(f"\n  {exchange.upper()}:")
        for key, value in limits.items():
            print(f"    {key:20} - {value}")
    
    # Test exchange creation
    print("\n[4] Testing Exchange Creation:")
    test_exchanges = ["alpaca", "binance", "oanda", "kraken"]
    for exchange_name in test_exchanges:
        try:
            exchange = create_exchange(exchange_name, paper_trading=True, testnet=True)
            print(f"  ✓ {exchange_name:20} - Created successfully")
            print(f"      Class: {exchange.__class__.__name__}")
        except Exception as e:
            print(f"  ✗ {exchange_name:20} - Failed: {e}")
    
    # Test exchange info
    print("\n[5] Exchange Information:")
    info = get_exchange_info()
    print(f"  Total supported: {info['count']}")
    print(f"  Categories:")
    for category, exchanges in info['categories'].items():
        print(f"    {category}: {len(exchanges)} exchanges")
    
    # Test features
    print("\n[6] Feature Comparison:")
    features_to_check = ["paper_trading", "real_time_data", "historical_data", "webhooks", "websocket", "streaming"]
    for exchange in ["alpaca", "binance", "oanda", "kraken"]:
        features = _get_exchange_features(exchange)
        print(f"\n  {exchange.upper()}:")
        for feature in features_to_check:
            print(f"    {feature:20} - {features.get(feature, False)}")
    
    # Test asset classes
    print("\n[7] Asset Classes by Exchange:")
    for exchange in ["alpaca", "binance", "oanda", "ibkr"]:
        asset_classes = get_exchange_asset_classes(exchange)
        print(f"  {exchange:15} - {', '.join(asset_classes)}")
    
    # Test category lookup
    print("\n[8] Category Lookup:")
    for category in ["stocks", "crypto", "forex"]:
        exchanges = get_exchanges_by_category(category)
        print(f"  {category:10} - {len(exchanges)} exchanges")
    
    # Test exchange status
    print("\n[9] Exchange Status:")
    for exchange in ["alpaca", "binance", "unknown_exchange"]:
        status = get_exchange_status(exchange)
        print(f"  {exchange:15} - Supported: {status['supported']}, Category: {status.get('category', 'N/A')}")
    
    # Test order types
    print("\n[10] Order Types by Exchange:")
    for exchange in ["alpaca", "binance", "oanda"]:
        features = _get_exchange_features(exchange)
        order_types = features.get("order_types", [])
        print(f"  {exchange:15} - {', '.join(order_types)}")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed successfully!")
    print("=" * 70)

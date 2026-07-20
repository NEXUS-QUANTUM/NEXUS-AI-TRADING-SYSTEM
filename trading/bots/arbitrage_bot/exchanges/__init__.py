# trading/bots/arbitrage_bot/exchanges/__init__.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Complete Exchanges Package

"""
Exchanges Package - Complete Exchange Integration Suite

This package provides a comprehensive suite of exchange integrations
for the NEXUS AI Trading System. It includes adapters for centralized
exchanges (CEX), decentralized exchanges (DEX), and aggregators.

Architecture:
    - Base Classes: Abstract interfaces for all exchanges
    - Exchange-Specific Adapters: Specialized implementations
    - Factory Pattern: Dynamic exchange instantiation
    - WebSocket Support: Real-time data streaming
    - Rate Limiting: API rate limit management
    - Error Handling: Comprehensive error handling

Exchanges Included:
    1. Base Exchange (base_exchange.py) - Abstract base class
    2. Binance (binance.py) - Full Binance integration
    3. Bybit (bybit.py) - Full Bybit integration
    4. OKX (okx.py) - Full OKX integration
    5. KuCoin (kucoin.py) - Full KuCoin integration
    6. MEXC (mexc.py) - Full MEXC integration
    7. Kraken (kraken.py) - Full Kraken integration
    8. Coinbase (coinbase.py) - Full Coinbase integration
    9. Gate.io (gateio.py) - Full Gate.io integration
    10. Huobi (huobi.py) - Full Huobi integration
    11. Bitget (bitget.py) - Full Bitget integration
    12. Uniswap (uniswap.py) - Uniswap V2/V3 integration
    13. PancakeSwap (pancakeswap.py) - PancakeSwap integration
    14. SushiSwap (sushiswap.py) - SushiSwap integration
    15. Curve (curve.py) - Curve Finance integration
    16. Balancer (balancer.py) - Balancer integration
    17. 1inch (1inch.py) - 1inch aggregator integration
    18. dYdX (dydx.py) - dYdX integration

Exports:
    - All exchange classes
    - Factory function for exchange creation
    - Base exchange classes
    - Utility functions and constants
"""

import asyncio
import logging
import threading
from typing import Dict, List, Optional, Type, Any, Union, Tuple, Set, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

# Import base exchange
from .base_exchange import (
    BaseExchange,
    ExchangeConfig,
    ExchangeType,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    MarketType,
    Interval,
    Balance,
    Ticker,
    OHLCV,
    Order,
    OrderBook,
    Position,
    Trade,
    DepositWithdrawal,
    FundingRate,
    ExchangeWebSocket,
    ExchangeFactory as BaseExchangeFactory,
)

# Import exchange implementations with error handling
try:
    from .binance import BinanceExchange, BinanceWebSocket
except ImportError:
    class BinanceExchange(BaseExchange):
        pass
    class BinanceWebSocket:
        pass

try:
    from .bybit import BybitExchange, BybitWebSocket
except ImportError:
    class BybitExchange(BaseExchange):
        pass
    class BybitWebSocket:
        pass

try:
    from .okx import OKXExchange, OKXWebSocket
except ImportError:
    class OKXExchange(BaseExchange):
        pass
    class OKXWebSocket:
        pass

try:
    from .kucoin import KuCoinExchange, KuCoinWebSocket
except ImportError:
    class KuCoinExchange(BaseExchange):
        pass
    class KuCoinWebSocket:
        pass

try:
    from .mexc import MEXCExchange, MEXCWebSocket
except ImportError:
    class MEXCExchange(BaseExchange):
        pass
    class MEXCWebSocket:
        pass

try:
    from .kraken import KrakenExchange, KrakenWebSocket
except ImportError:
    class KrakenExchange(BaseExchange):
        pass
    class KrakenWebSocket:
        pass

try:
    from .coinbase import CoinbaseExchange, CoinbaseWebSocket
except ImportError:
    class CoinbaseExchange(BaseExchange):
        pass
    class CoinbaseWebSocket:
        pass

try:
    from .gateio import GateIOExchange, GateIOWebSocket
except ImportError:
    class GateIOExchange(BaseExchange):
        pass
    class GateIOWebSocket:
        pass

try:
    from .huobi import HuobiExchange, HuobiWebSocket
except ImportError:
    class HuobiExchange(BaseExchange):
        pass
    class HuobiWebSocket:
        pass

try:
    from .bitget import BitgetExchange, BitgetWebSocket
except ImportError:
    class BitgetExchange(BaseExchange):
        pass
    class BitgetWebSocket:
        pass

# DEX imports
try:
    from .uniswap import (
        UniswapExchange,
        UniswapChain,
        FeeTier,
        V3PoolInfo,
        V3Position,
        SwapQuote as UniswapSwapQuote,
        SwapResult as UniswapSwapResult,
    )
except ImportError:
    class UniswapExchange(BaseExchange):
        pass
    class UniswapChain(Enum):
        pass
    class FeeTier(Enum):
        pass
    class V3PoolInfo:
        pass
    class V3Position:
        pass
    class UniswapSwapQuote:
        pass
    class UniswapSwapResult:
        pass

try:
    from .pancakeswap import (
        PancakeSwapExchange,
        PancakeChain,
        PairInfo as PancakePairInfo,
        FarmPool,
        SyrupPool,
        SwapQuote as PancakeSwapQuote,
        SwapResult as PancakeSwapResult,
        LiquidityPosition as PancakeLiquidityPosition,
    )
except ImportError:
    class PancakeSwapExchange(BaseExchange):
        pass
    class PancakeChain(Enum):
        pass
    class PancakePairInfo:
        pass
    class FarmPool:
        pass
    class SyrupPool:
        pass
    class PancakeSwapQuote:
        pass
    class PancakeSwapResult:
        pass
    class PancakeLiquidityPosition:
        pass

try:
    from .sushiswap import (
        SushiSwapExchange,
        SushiChain,
        PairInfo as SushiPairInfo,
        OnsenFarm,
        KashiLending,
        BentoBoxVault,
        SwapQuote as SushiSwapQuote,
        SwapResult as SushiSwapResult,
    )
except ImportError:
    class SushiSwapExchange(BaseExchange):
        pass
    class SushiChain(Enum):
        pass
    class SushiPairInfo:
        pass
    class OnsenFarm:
        pass
    class KashiLending:
        pass
    class BentoBoxVault:
        pass
    class SushiSwapQuote:
        pass
    class SushiSwapResult:
        pass

try:
    from .curve import CurveExchange, CurveChain
except ImportError:
    class CurveExchange(BaseExchange):
        pass
    class CurveChain(Enum):
        pass

try:
    from .balancer import (
        BalancerExchange,
        BalancerChain,
        PoolType,
        SwapType,
        PoolStatus,
        BalancerPool,
        SwapQuote as BalancerSwapQuote,
        SwapResult as BalancerSwapResult,
        FlashLoanInfo,
        LiquidityPosition as BalancerLiquidityPosition,
        GaugeInfo,
    )
except ImportError:
    class BalancerExchange(BaseExchange):
        pass
    class BalancerChain(Enum):
        pass
    class PoolType(Enum):
        pass
    class SwapType(Enum):
        pass
    class PoolStatus(Enum):
        pass
    class BalancerPool:
        pass
    class BalancerSwapQuote:
        pass
    class BalancerSwapResult:
        pass
    class FlashLoanInfo:
        pass
    class BalancerLiquidityPosition:
        pass
    class GaugeInfo:
        pass

try:
    from .oneinch import (
        OneInchExchange,
        OneInchExchangeSync,
        Chain as OneInchChain,
        OrderType as OneInchOrderType,
        SwapMode,
        FusionMode,
        TokenInfo,
        QuoteResult,
        SwapResult as OneInchSwapResult,
        ProtocolInfo,
        FusionAuction,
    )
except ImportError:
    class OneInchExchange:
        pass
    class OneInchExchangeSync:
        pass
    class OneInchChain(Enum):
        pass
    class OneInchOrderType(Enum):
        pass
    class SwapMode(Enum):
        pass
    class FusionMode(Enum):
        pass
    class TokenInfo:
        pass
    class QuoteResult:
        pass
    class OneInchSwapResult:
        pass
    class ProtocolInfo:
        pass
    class FusionAuction:
        pass

try:
    from .dydx import DydxExchange, DydxChain
except ImportError:
    class DydxExchange(BaseExchange):
        pass
    class DydxChain(Enum):
        pass

# Import factory
from .exchange_factory import ExchangeFactory, create_exchange, list_exchanges

# Logger setup
logger = logging.getLogger(__name__)

# Version information
__version__ = "4.2.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package metadata
PACKAGE_METADATA = {
    "name": "exchanges",
    "version": __version__,
    "description": "Complete Exchange Integration Suite",
    "author": __author__,
    "copyright": __copyright__,
    "exchanges_count": 18,
    "supported_exchanges": [
        "binance",
        "bybit",
        "okx",
        "kucoin",
        "mexc",
        "kraken",
        "coinbase",
        "gateio",
        "huobi",
        "bitget",
        "uniswap",
        "pancakeswap",
        "sushiswap",
        "curve",
        "balancer",
        "1inch",
        "dydx",
    ],
    "supported_markets": [
        "spot",
        "futures",
        "perpetual",
        "option",
        "margin",
        "leveraged",
    ],
    "supported_chains": [
        "ethereum",
        "polygon",
        "arbitrum",
        "optimism",
        "avalanche",
        "bsc",
        "fantom",
        "base",
        "celo",
        "gnosis",
        "harmony",
        "heco",
        "xdai",
        "moonbeam",
        "moonriver",
        "boba",
        "aurora",
        "zksync",
        "linea",
    ],
}

# Public API - All exchanges
__all__ = [
    # Base classes
    'BaseExchange',
    'ExchangeConfig',
    'ExchangeType',
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'TimeInForce',
    'MarketType',
    'Interval',
    'Balance',
    'Ticker',
    'OHLCV',
    'Order',
    'OrderBook',
    'Position',
    'Trade',
    'DepositWithdrawal',
    'FundingRate',
    'ExchangeWebSocket',
    'BaseExchangeFactory',
    
    # CEX Exchanges
    'BinanceExchange',
    'BinanceWebSocket',
    'BybitExchange',
    'BybitWebSocket',
    'OKXExchange',
    'OKXWebSocket',
    'KuCoinExchange',
    'KuCoinWebSocket',
    'MEXCExchange',
    'MEXCWebSocket',
    'KrakenExchange',
    'KrakenWebSocket',
    'CoinbaseExchange',
    'CoinbaseWebSocket',
    'GateIOExchange',
    'GateIOWebSocket',
    'HuobiExchange',
    'HuobiWebSocket',
    'BitgetExchange',
    'BitgetWebSocket',
    
    # DEX Exchanges
    'UniswapExchange',
    'UniswapChain',
    'FeeTier',
    'V3PoolInfo',
    'V3Position',
    'UniswapSwapQuote',
    'UniswapSwapResult',
    'PancakeSwapExchange',
    'PancakeChain',
    'PancakePairInfo',
    'FarmPool',
    'SyrupPool',
    'PancakeSwapQuote',
    'PancakeSwapResult',
    'PancakeLiquidityPosition',
    'SushiSwapExchange',
    'SushiChain',
    'SushiPairInfo',
    'OnsenFarm',
    'KashiLending',
    'BentoBoxVault',
    'SushiSwapQuote',
    'SushiSwapResult',
    'CurveExchange',
    'CurveChain',
    'BalancerExchange',
    'BalancerChain',
    'PoolType',
    'SwapType',
    'PoolStatus',
    'BalancerPool',
    'BalancerSwapQuote',
    'BalancerSwapResult',
    'FlashLoanInfo',
    'BalancerLiquidityPosition',
    'GaugeInfo',
    
    # Aggregators
    'OneInchExchange',
    'OneInchExchangeSync',
    'OneInchChain',
    'OneInchOrderType',
    'SwapMode',
    'FusionMode',
    'TokenInfo',
    'QuoteResult',
    'OneInchSwapResult',
    'ProtocolInfo',
    'FusionAuction',
    'DydxExchange',
    'DydxChain',
    
    # Factory
    'ExchangeFactory',
    'create_exchange',
    'list_exchanges',
    
    # Metadata
    'PACKAGE_METADATA',
    'get_version',
    'get_metadata',
    'get_exchange_types',
    'get_supported_exchanges',
]


class ExchangeEventType(Enum):
    """Exchange event types."""
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    WARNING = "warning"
    ORDER_PLACED = "order_placed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FILLED = "order_filled"
    BALANCE_UPDATED = "balance_updated"
    POSITION_UPDATED = "position_updated"
    TRADE_EXECUTED = "trade_executed"


@dataclass
class ExchangeEvent:
    """Exchange event."""
    event_type: ExchangeEventType
    exchange_name: str
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None


class ExchangeRegistry:
    """
    Registry for managing all exchange instances.
    
    This class provides centralized management of exchange instances,
    including creation, configuration, and lifecycle management.
    
    Features:
    - Singleton pattern for global access
    - Exchange registration and retrieval
    - Lifecycle management (connect/disconnect)
    - Event system for exchange notifications
    - Metrics aggregation
    - Health monitoring
    """
    
    _instance = None
    _exchanges: Dict[str, BaseExchange] = {}
    _configs: Dict[str, ExchangeConfig] = {}
    _listeners: List[Callable[[ExchangeEvent], None]] = []
    _event_history: List[ExchangeEvent] = []
    _max_event_history: int = 1000
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the registry."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.logger = logging.getLogger(f"{__name__}.Registry")
            self._lock = threading.Lock()
            self._exchange_metadata = {}
            self._register_exchange_metadata()
            self.logger.info("ExchangeRegistry initialized")
    
    def _register_exchange_metadata(self) -> None:
        """Register metadata for all exchanges."""
        self._exchange_metadata = {
            "binance": {
                "name": "Binance",
                "type": "cex",
                "markets": ["spot", "futures", "perpetual", "margin"],
                "websocket": True,
                "rate_limit": 1200,
                "priority": 1,
                "description": "Binance Exchange - Largest CEX by volume",
                "website": "https://www.binance.com",
            },
            "bybit": {
                "name": "Bybit",
                "type": "cex",
                "markets": ["spot", "futures", "perpetual"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 1,
                "description": "Bybit Exchange - Leading derivatives exchange",
                "website": "https://www.bybit.com",
            },
            "okx": {
                "name": "OKX",
                "type": "cex",
                "markets": ["spot", "futures", "perpetual", "option"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 1,
                "description": "OKX Exchange - Full-featured trading platform",
                "website": "https://www.okx.com",
            },
            "kucoin": {
                "name": "KuCoin",
                "type": "cex",
                "markets": ["spot", "futures", "perpetual"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 1,
                "description": "KuCoin Exchange - Global cryptocurrency exchange",
                "website": "https://www.kucoin.com",
            },
            "mexc": {
                "name": "MEXC",
                "type": "cex",
                "markets": ["spot", "futures"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 2,
                "description": "MEXC Exchange - Fast-growing crypto exchange",
                "website": "https://www.mexc.com",
            },
            "kraken": {
                "name": "Kraken",
                "type": "cex",
                "markets": ["spot", "futures"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 2,
                "description": "Kraken Exchange - Secure and trusted exchange",
                "website": "https://www.kraken.com",
            },
            "coinbase": {
                "name": "Coinbase",
                "type": "cex",
                "markets": ["spot", "futures"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 2,
                "description": "Coinbase Exchange - US-based regulated exchange",
                "website": "https://www.coinbase.com",
            },
            "gateio": {
                "name": "Gate.io",
                "type": "cex",
                "markets": ["spot", "futures"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 2,
                "description": "Gate.io Exchange - Comprehensive crypto platform",
                "website": "https://www.gate.io",
            },
            "huobi": {
                "name": "Huobi",
                "type": "cex",
                "markets": ["spot", "futures"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 2,
                "description": "Huobi Exchange - Established global exchange",
                "website": "https://www.huobi.com",
            },
            "bitget": {
                "name": "Bitget",
                "type": "cex",
                "markets": ["spot", "futures"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 2,
                "description": "Bitget Exchange - Fast-growing derivatives platform",
                "website": "https://www.bitget.com",
            },
            "uniswap": {
                "name": "Uniswap",
                "type": "dex",
                "markets": ["spot"],
                "websocket": False,
                "rate_limit": 1000,
                "priority": 1,
                "description": "Uniswap DEX - Leading decentralized exchange",
                "website": "https://uniswap.org",
            },
            "pancakeswap": {
                "name": "PancakeSwap",
                "type": "dex",
                "markets": ["spot"],
                "websocket": False,
                "rate_limit": 1000,
                "priority": 2,
                "description": "PancakeSwap DEX - BSC's leading DEX",
                "website": "https://pancakeswap.finance",
            },
            "sushiswap": {
                "name": "SushiSwap",
                "type": "dex",
                "markets": ["spot"],
                "websocket": False,
                "rate_limit": 1000,
                "priority": 2,
                "description": "SushiSwap DEX - Multi-chain DEX",
                "website": "https://sushi.com",
            },
            "curve": {
                "name": "Curve",
                "type": "dex",
                "markets": ["spot"],
                "websocket": False,
                "rate_limit": 1000,
                "priority": 2,
                "description": "Curve Finance - Stablecoin DEX",
                "website": "https://curve.fi",
            },
            "balancer": {
                "name": "Balancer",
                "type": "dex",
                "markets": ["spot"],
                "websocket": False,
                "rate_limit": 1000,
                "priority": 2,
                "description": "Balancer Protocol - Weighted pool DEX",
                "website": "https://balancer.fi",
            },
            "1inch": {
                "name": "1inch",
                "type": "aggregator",
                "markets": ["spot"],
                "websocket": False,
                "rate_limit": 1000,
                "priority": 1,
                "description": "1inch Aggregator - DEX aggregator",
                "website": "https://1inch.io",
            },
            "dydx": {
                "name": "dYdX",
                "type": "dex",
                "markets": ["perpetual"],
                "websocket": True,
                "rate_limit": 1000,
                "priority": 2,
                "description": "dYdX Protocol - Perpetual DEX",
                "website": "https://dydx.exchange",
            },
        }
    
    def register_exchange(
        self,
        name: str,
        exchange: BaseExchange,
        config: Optional[ExchangeConfig] = None
    ) -> None:
        """
        Register an exchange instance.
        
        Args:
            name: Exchange name
            exchange: Exchange instance
            config: Optional configuration
        """
        with self._lock:
            self._exchanges[name] = exchange
            if config:
                self._configs[name] = config
            self._emit_event(ExchangeEventType.REGISTERED, name)
            self.logger.info(f"Registered exchange: {name}")
    
    def unregister_exchange(self, name: str) -> None:
        """
        Unregister an exchange instance.
        
        Args:
            name: Exchange name
        """
        with self._lock:
            if name in self._exchanges:
                try:
                    if hasattr(self._exchanges[name], 'close'):
                        loop = asyncio.new_event_loop()
                        try:
                            loop.run_until_complete(self._exchanges[name].close())
                        finally:
                            loop.close()
                except Exception as e:
                    self.logger.error(f"Error closing {name}: {e}")
                del self._exchanges[name]
                if name in self._configs:
                    del self._configs[name]
                self._emit_event(ExchangeEventType.UNREGISTERED, name)
                self.logger.info(f"Unregistered exchange: {name}")
    
    def get_exchange(self, name: str) -> Optional[BaseExchange]:
        """
        Get an exchange by name.
        
        Args:
            name: Exchange name
            
        Returns:
            Exchange instance or None
        """
        with self._lock:
            return self._exchanges.get(name)
    
    def get_all_exchanges(self) -> Dict[str, BaseExchange]:
        """
        Get all registered exchanges.
        
        Returns:
            Dictionary of exchange name to instance
        """
        with self._lock:
            return self._exchanges.copy()
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for an exchange.
        
        Args:
            name: Exchange name
            
        Returns:
            Metadata dictionary or None
        """
        return self._exchange_metadata.get(name)
    
    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all exchanges.
        
        Returns:
            Dictionary of exchange name to metadata
        """
        return self._exchange_metadata.copy()
    
    def connect_all(self) -> Dict[str, bool]:
        """
        Connect to all registered exchanges.
        
        Returns:
            Dictionary of exchange name to connection status
        """
        results = {}
        for name, exchange in self._exchanges.items():
            try:
                if hasattr(exchange, 'connect'):
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(exchange.connect())
                        results[name] = True
                        self._emit_event(ExchangeEventType.CONNECTED, name)
                        self.logger.info(f"Connected exchange: {name}")
                    finally:
                        loop.close()
                else:
                    results[name] = False
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to connect {name}: {e}")
                self._emit_event(ExchangeEventType.ERROR, name, error=e)
        return results
    
    def disconnect_all(self) -> Dict[str, bool]:
        """
        Disconnect from all registered exchanges.
        
        Returns:
            Dictionary of exchange name to disconnection status
        """
        results = {}
        for name, exchange in self._exchanges.items():
            try:
                if hasattr(exchange, 'disconnect'):
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(exchange.disconnect())
                        results[name] = True
                        self._emit_event(ExchangeEventType.DISCONNECTED, name)
                        self.logger.info(f"Disconnected exchange: {name}")
                    finally:
                        loop.close()
                else:
                    results[name] = False
            except Exception as e:
                results[name] = False
                self.logger.error(f"Failed to disconnect {name}: {e}")
                self._emit_event(ExchangeEventType.ERROR, name, error=e)
        return results
    
    def add_listener(self, listener: Callable[[ExchangeEvent], None]) -> None:
        """
        Add an event listener.
        
        Args:
            listener: Callback function for events
        """
        with self._lock:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[ExchangeEvent], None]) -> None:
        """
        Remove an event listener.
        
        Args:
            listener: Callback function to remove
        """
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
    
    def _emit_event(
        self,
        event_type: ExchangeEventType,
        exchange_name: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ) -> None:
        """
        Emit an event to all listeners.
        
        Args:
            event_type: Type of event
            exchange_name: Name of the exchange
            data: Optional event data
            error: Optional error
        """
        event = ExchangeEvent(
            event_type=event_type,
            exchange_name=exchange_name,
            timestamp=datetime.utcnow(),
            data=data,
            error=error,
        )
        
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_event_history:
                self._event_history = self._event_history[-self._max_event_history:]
            
            for listener in self._listeners:
                try:
                    listener(event)
                except Exception as e:
                    self.logger.error(f"Listener error: {e}")
    
    def get_event_history(
        self,
        limit: int = 100,
        exchange_name: Optional[str] = None,
        event_type: Optional[ExchangeEventType] = None
    ) -> List[ExchangeEvent]:
        """
        Get event history.
        
        Args:
            limit: Maximum number of events
            exchange_name: Filter by exchange name
            event_type: Filter by event type
            
        Returns:
            List of events
        """
        with self._lock:
            events = self._event_history.copy()
        
        if exchange_name:
            events = [e for e in events if e.exchange_name == exchange_name]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics from all exchanges.
        
        Returns:
            Aggregated metrics dictionary
        """
        aggregated = {
            "total_exchanges": len(self._exchanges),
            "connected_exchanges": 0,
            "total_volume": Decimal("0"),
            "total_fees": Decimal("0"),
            "total_trades": 0,
            "total_orders": 0,
            "exchanges": {},
        }
        
        for name, exchange in self._exchanges.items():
            try:
                if hasattr(exchange, 'get_metrics'):
                    metrics = exchange.get_metrics()
                    if metrics:
                        aggregated["exchanges"][name] = metrics
                        if metrics.get("is_connected", False):
                            aggregated["connected_exchanges"] += 1
                        aggregated["total_volume"] += Decimal(str(metrics.get("total_volume", 0)))
                        aggregated["total_fees"] += Decimal(str(metrics.get("total_fees", 0)))
                        aggregated["total_trades"] += metrics.get("swaps_executed", 0)
                        aggregated["total_orders"] += metrics.get("orders_placed", 0)
            except Exception as e:
                self.logger.error(f"Error getting metrics for {name}: {e}")
        
        return aggregated
    
    def get_status_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all exchanges.
        
        Returns:
            Dictionary of exchange name to status
        """
        status = {}
        for name, exchange in self._exchanges.items():
            try:
                metrics = None
                if hasattr(exchange, 'get_metrics'):
                    metrics = exchange.get_metrics()
                status[name] = {
                    'registered': True,
                    'connected': metrics.get("is_connected", False) if metrics else False,
                    'metrics': metrics,
                    'has_metrics': metrics is not None,
                }
            except Exception as e:
                status[name] = {
                    'registered': True,
                    'connected': False,
                    'metrics': None,
                    'error': str(e),
                }
        return status
    
    def get_healthy_exchanges(self) -> List[str]:
        """
        Get list of healthy exchanges.
        
        Returns:
            List of exchange names
        """
        healthy = []
        for name, exchange in self._exchanges.items():
            try:
                if hasattr(exchange, 'ping'):
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(exchange.ping())
                        if result:
                            healthy.append(name)
                    finally:
                        loop.close()
            except Exception:
                pass
        return healthy


# Global registry instance
exchange_registry = ExchangeRegistry()


# Utility functions
def get_exchange(name: str) -> Optional[BaseExchange]:
    """
    Get an exchange by name from the registry.
    
    Args:
        name: Exchange name
        
    Returns:
        Exchange instance or None
    """
    return exchange_registry.get_exchange(name)


def get_all_exchanges() -> Dict[str, BaseExchange]:
    """
    Get all exchanges from the registry.
    
    Returns:
        Dictionary of exchange name to instance
    """
    return exchange_registry.get_all_exchanges()


def create_exchange(
    exchange_type: Union[str, ExchangeType],
    config: Optional[Dict[str, Any]] = None
) -> Optional[BaseExchange]:
    """
    Create an exchange using the factory.
    
    Args:
        exchange_type: Type of exchange to create
        config: Optional configuration
        
    Returns:
        Exchange instance or None
    """
    return ExchangeFactory.create_exchange(exchange_type, config)


def list_exchanges() -> List[str]:
    """
    List all available exchange types.
    
    Returns:
        List of exchange type names
    """
    return ExchangeFactory.list_exchanges()


def get_version() -> str:
    """Get package version."""
    return __version__


def get_metadata() -> Dict[str, Any]:
    """Get package metadata."""
    return PACKAGE_METADATA


def get_exchange_types() -> Dict[str, str]:
    """
    Get all exchange types with descriptions.
    
    Returns:
        Dictionary of exchange type to description
    """
    return {
        "binance": "Binance Exchange - Full CEX integration",
        "bybit": "Bybit Exchange - Full CEX integration",
        "okx": "OKX Exchange - Full CEX integration",
        "kucoin": "KuCoin Exchange - Full CEX integration",
        "mexc": "MEXC Exchange - Full CEX integration",
        "kraken": "Kraken Exchange - Full CEX integration",
        "coinbase": "Coinbase Exchange - Full CEX integration",
        "gateio": "Gate.io Exchange - Full CEX integration",
        "huobi": "Huobi Exchange - Full CEX integration",
        "bitget": "Bitget Exchange - Full CEX integration",
        "uniswap": "Uniswap DEX - V2 & V3 integration",
        "pancakeswap": "PancakeSwap DEX - Full integration",
        "sushiswap": "SushiSwap DEX - Full integration",
        "curve": "Curve Finance - Stablecoin DEX",
        "balancer": "Balancer Protocol - Full integration",
        "1inch": "1inch Aggregator - Full integration",
        "dydx": "dYdX Protocol - Perpetual DEX",
    }


def get_supported_exchanges() -> List[str]:
    """
    Get list of supported exchanges.
    
    Returns:
        List of exchange names
    """
    return list(exchange_registry.get_all_metadata().keys())


def connect_all_exchanges() -> Dict[str, bool]:
    """
    Connect to all registered exchanges.
    
    Returns:
        Dictionary of exchange name to connection status
    """
    return exchange_registry.connect_all()


def disconnect_all_exchanges() -> Dict[str, bool]:
    """
    Disconnect from all registered exchanges.
    
    Returns:
        Dictionary of exchange name to disconnection status
    """
    return exchange_registry.disconnect_all()


def get_exchange_status() -> Dict[str, Dict[str, Any]]:
    """
    Get status of all exchanges.
    
    Returns:
        Dictionary of exchange name to status
    """
    return exchange_registry.get_status_all()


def get_healthy_exchanges() -> List[str]:
    """
    Get list of healthy exchanges.
    
    Returns:
        List of exchange names
    """
    return exchange_registry.get_healthy_exchanges()


def get_aggregated_metrics() -> Dict[str, Any]:
    """
    Get aggregated metrics from all exchanges.
    
    Returns:
        Aggregated metrics dictionary
    """
    return exchange_registry.get_aggregated_metrics()


def add_exchange_listener(listener: Callable[[ExchangeEvent], None]) -> None:
    """
    Add an exchange event listener.
    
    Args:
        listener: Callback function for events
    """
    exchange_registry.add_listener(listener)


def remove_exchange_listener(listener: Callable[[ExchangeEvent], None]) -> None:
    """
    Remove an exchange event listener.
    
    Args:
        listener: Callback function to remove
    """
    exchange_registry.remove_listener(listener)


# Context manager for exchange lifecycle
@contextmanager
def exchange_context(exchange_name: str, config: Optional[Dict[str, Any]] = None):
    """
    Context manager for exchange lifecycle.
    
    Args:
        exchange_name: Name of the exchange
        config: Optional configuration
        
    Yields:
        Exchange instance
    """
    exchange = create_exchange(exchange_name, config)
    if not exchange:
        raise ValueError(f"Failed to create exchange: {exchange_name}")
    
    try:
        if hasattr(exchange, 'connect'):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(exchange.connect())
            finally:
                loop.close()
        yield exchange
    finally:
        if hasattr(exchange, 'disconnect'):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(exchange.disconnect())
            finally:
                loop.close()


# Package initialization
logger.info(f"Initializing Exchanges Package v{__version__}")
logger.info(f"Registered {len(exchange_registry.get_all_metadata())} exchange types")
logger.info(f"Package metadata: {PACKAGE_METADATA}")

# Auto-register available exchanges
try:
    for exchange_type in ['binance', 'bybit', 'okx', 'kucoin', 'uniswap']:
        try:
            exchange = create_exchange(exchange_type)
            if exchange:
                exchange_registry.register_exchange(exchange_type, exchange)
        except Exception as e:
            logger.debug(f"Failed to auto-register {exchange_type}: {e}")
except Exception as e:
    logger.debug(f"Auto-registration failed: {e}")


# Lazy imports for circular dependency resolution
def __getattr__(name: str) -> Any:
    """
    Lazy import for submodules.
    
    This allows for clean imports while avoiding circular dependencies.
    """
    if name in ['binance', 'bybit', 'okx', 'kucoin', 'mexc', 'kraken',
                'coinbase', 'gateio', 'huobi', 'bitget', 'uniswap',
                'pancakeswap', 'sushiswap', 'curve', 'balancer',
                '1inch', 'dydx', 'base_exchange', 'exchange_factory']:
        raise AttributeError(f"Module {name} not loaded. Please import directly.")
    raise AttributeError(f"module {__name__} has no attribute {name}")

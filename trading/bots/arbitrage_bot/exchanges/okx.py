# trading/bots/arbitrage_bot/exchanges/okx.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - OKX Exchange Integration

"""
OKX Exchange Integration - Complete OKX Exchange Adapter

This module provides comprehensive integration with the OKX exchange:
- Spot trading
- Futures trading (USDⓈ-M and COIN-M)
- Perpetual trading
- Options trading
- Margin trading
- WebSocket streams
- Market data
- Account management
- Order management
- Risk management

Features:
- Full REST API support (V5)
- WebSocket stream support (V5)
- Rate limiting
- Error handling
- Automatic retry
- Order management
- Position management
- Balance management
- Market data
- OHLCV data
- Ticker data
- Order book data
- Trade data
- Funding rate data
- Options data
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Callable, AsyncIterator
from urllib.parse import urlencode

import aiohttp
import aiohttp.client_exceptions

from .base_exchange import (
    BaseExchange,
    ExchangeType,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    MarketType,
    Interval,
    ExchangeConfig,
    Balance,
    Ticker,
    OHLCV,
    Order,
    OrderBook,
    Position,
    Trade,
    FundingRate,
    ExchangeWebSocket,
)

# Constants
OKX_API_BASE = "https://www.okx.com"
OKX_API_V5 = "/api/v5"
OKX_WS_BASE = "wss://ws.okx.com:8443/ws/v5"
OKX_WS_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"

# Endpoints V5
ENDPOINTS = {
    "ping": "/api/v5/public/time",
    "time": "/api/v5/public/time",
    "exchange_info": "/api/v5/public/instruments",
    "depth": "/api/v5/market/books",
    "ticker": "/api/v5/market/ticker",
    "tickers": "/api/v5/market/tickers",
    "klines": "/api/v5/market/candles",
    "account": "/api/v5/account/balance",
    "positions": "/api/v5/account/positions",
    "order": "/api/v5/trade/order",
    "batch_orders": "/api/v5/trade/batch-orders",
    "open_orders": "/api/v5/trade/orders-pending",
    "order_history": "/api/v5/trade/orders-history",
    "trade_list": "/api/v5/trade/fills",
    "funding_rate": "/api/v5/public/funding-rate",
    "funding_rate_history": "/api/v5/public/funding-rate-history",
    "leverage": "/api/v5/account/set-leverage",
    "position_risk": "/api/v5/account/position-risk",
    "interest_accrued": "/api/v5/account/interest-accrued",
    "settlement_history": "/api/v5/account/settlement-history",
}

# Instrument types
class InstrumentType(Enum):
    SPOT = "SPOT"
    FUTURES = "FUTURES"
    PERPETUAL = "SWAP"
    OPTION = "OPTION"


class OKXWebSocket(ExchangeWebSocket):
    """OKX WebSocket implementation (V5)."""
    
    def __init__(self, exchange: 'OKXExchange', url: str):
        self.exchange = exchange
        self.url = url
        self.logger = exchange.logger
        self._ws = None
        self._is_connected = False
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._listen_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._should_reconnect = True
        self._lock = asyncio.Lock()
        self._ping_interval = 30
        self._last_ping = 0
        self._login_sent = False
        self._authenticated = False
    
    async def connect(self) -> None:
        """Connect to WebSocket."""
        if self._is_connected:
            return
        
        try:
            from websockets import connect as ws_connect
            
            self._ws = await ws_connect(
                self.url,
                ping_interval=self._ping_interval,
                ping_timeout=10,
            )
            self._is_connected = True
            
            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            # Send login if authenticated
            if self.exchange.config.api_key:
                await self._login()
            
            self.logger.info(f"Connected to OKX WebSocket: {self.url}")
            
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._should_reconnect = False
        self._is_connected = False
        
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except Exception:
                pass
        
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except Exception:
                pass
        
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        
        self.logger.info("Disconnected from OKX WebSocket")
    
    async def subscribe(
        self,
        channel: str,
        symbols: List[str],
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Subscribe to a WebSocket channel."""
        async with self._lock:
            for symbol in symbols:
                stream_name = self._get_stream_name(channel, symbol)
                if stream_name not in self._subscriptions:
                    self._subscriptions[stream_name] = []
                self._subscriptions[stream_name].append(callback)
        
        if self._is_connected:
            await self._subscribe_streams()
    
    async def unsubscribe(self, channel: str, symbols: List[str]) -> None:
        """Unsubscribe from a WebSocket channel."""
        async with self._lock:
            for symbol in symbols:
                stream_name = self._get_stream_name(channel, symbol)
                if stream_name in self._subscriptions:
                    del self._subscriptions[stream_name]
        
        if self._is_connected:
            await self._unsubscribe_streams()
    
    async def listen(self) -> AsyncIterator[Dict[str, Any]]:
        """Listen for WebSocket messages."""
        if not self._is_connected:
            await self.connect()
        
        self._listen_task = asyncio.create_task(self._listen_loop())
        
        try:
            async for message in self._listen_task:
                yield message
        except asyncio.CancelledError:
            pass
        finally:
            self._listen_task = None
    
    def _get_stream_name(self, channel: str, symbol: str) -> str:
        """Get stream name for a channel and symbol."""
        # OKX uses format: "channel:instrument"
        if self.exchange.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
            # Futures/perpetual format
            if channel == "ticker":
                return f"tickers:{symbol}"
            elif channel == "depth":
                return f"books:{symbol}"
            elif channel == "trade":
                return f"trades:{symbol}"
            elif channel == "kline":
                return f"candle1m:{symbol}"
            elif channel == "funding_rate":
                return f"funding-rate:{symbol}"
            elif channel == "mark_price":
                return f"mark-price:{symbol}"
            elif channel == "position":
                return f"positions:{symbol}"
            else:
                return f"tickers:{symbol}"
        else:
            # Spot format
            if channel == "ticker":
                return f"tickers:{symbol}"
            elif channel == "depth":
                return f"books:{symbol}"
            elif channel == "trade":
                return f"trades:{symbol}"
            elif channel == "kline":
                return f"candle1m:{symbol}"
            else:
                return f"tickers:{symbol}"
    
    async def _login(self) -> None:
        """Login to private WebSocket."""
        if not self.exchange.config.api_key:
            return
        
        if self._login_sent:
            return
        
        timestamp = str(int(time.time()))
        method = "GET"
        request_path = "/users/self/verify"
        
        signature = base64.b64encode(
            hmac.new(
                self.exchange.config.api_secret.encode('utf-8'),
                f"{timestamp}{method}{request_path}".encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        login_msg = {
            "op": "login",
            "args": [{
                "apiKey": self.exchange.config.api_key,
                "passphrase": self.exchange.config.api_passphrase or "",
                "timestamp": timestamp,
                "sign": signature,
            }]
        }
        
        try:
            await self._ws.send(json.dumps(login_msg))
            self._login_sent = True
            self.logger.info("WebSocket login sent")
        except Exception as e:
            self.logger.error(f"WebSocket login failed: {e}")
    
    async def _subscribe_streams(self) -> None:
        """Subscribe to streams."""
        if not self._ws or not self._is_connected:
            return
        
        streams = list(self._subscriptions.keys())
        if not streams:
            return
        
        # Group channels by type
        channels = {}
        for stream in streams:
            parts = stream.split(":")
            if len(parts) == 2:
                channel, symbol = parts
                if channel not in channels:
                    channels[channel] = []
                channels[channel].append(symbol)
        
        for channel, symbols in channels.items():
            subscribe_msg = {
                "op": "subscribe",
                "args": [{"channel": channel, "instId": s} for s in symbols]
            }
            
            try:
                await self._ws.send(json.dumps(subscribe_msg))
                self.logger.debug(f"Subscribed to {channel}: {symbols}")
                await asyncio.sleep(0.1)  # Rate limit
            except Exception as e:
                self.logger.error(f"Failed to subscribe to {channel}: {e}")
    
    async def _unsubscribe_streams(self) -> None:
        """Unsubscribe from streams."""
        if not self._ws or not self._is_connected:
            return
        
        streams = list(self._subscriptions.keys())
        if not streams:
            return
        
        # Group channels by type
        channels = {}
        for stream in streams:
            parts = stream.split(":")
            if len(parts) == 2:
                channel, symbol = parts
                if channel not in channels:
                    channels[channel] = []
                channels[channel].append(symbol)
        
        for channel, symbols in channels.items():
            unsubscribe_msg = {
                "op": "unsubscribe",
                "args": [{"channel": channel, "instId": s} for s in symbols]
            }
            
            try:
                await self._ws.send(json.dumps(unsubscribe_msg))
                self.logger.debug(f"Unsubscribed from {channel}: {symbols}")
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Failed to unsubscribe from {channel}: {e}")
    
    async def _listen_loop(self) -> None:
        """Listen for WebSocket messages."""
        while self._is_connected and self._should_reconnect:
            try:
                if not self._ws:
                    await self.connect()
                
                async for message in self._ws:
                    try:
                        data = json.loads(message)
                        
                        # Handle ping/pong
                        if data.get("event") == "ping":
                            await self._send_pong(data.get("data", {}))
                            continue
                        
                        # Handle login response
                        if data.get("event") == "login":
                            self._authenticated = data.get("code") == "0"
                            if self._authenticated:
                                self.logger.info("WebSocket authenticated")
                            else:
                                self.logger.error(f"WebSocket auth failed: {data}")
                            continue
                        
                        # Handle subscription response
                        if data.get("event") == "subscribe":
                            self.logger.debug(f"Subscribed: {data}")
                            continue
                        
                        # Handle error
                        if data.get("event") == "error":
                            self.logger.error(f"WebSocket error: {data}")
                            continue
                        
                        # Handle data message
                        if "data" in data and "arg" in data:
                            channel = data["arg"].get("channel", "")
                            stream = f"{channel}:{data['arg'].get('instId', '')}"
                            if stream in self._subscriptions:
                                for callback in self._subscriptions[stream]:
                                    try:
                                        callback(data["data"])
                                    except Exception as e:
                                        self.logger.error(f"Callback error: {e}")
                            else:
                                self.logger.debug(f"Received message: {data}")
                        else:
                            self.logger.debug(f"Received message: {data}")
                            
                    except json.JSONDecodeError:
                        self.logger.error(f"Invalid JSON: {message}")
                    except Exception as e:
                        self.logger.error(f"Message processing error: {e}")
                        
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                if self._should_reconnect:
                    await asyncio.sleep(5)
                    await self._reconnect()
    
    async def _reconnect(self) -> None:
        """Reconnect WebSocket."""
        self._is_connected = False
        self._login_sent = False
        self._authenticated = False
        await asyncio.sleep(5)
        if self._should_reconnect:
            try:
                await self.connect()
                await self._subscribe_streams()
            except Exception as e:
                self.logger.error(f"Reconnection failed: {e}")
    
    async def _send_pong(self, data: Any) -> None:
        """Send pong response."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({"op": "pong", "data": data}))
            except Exception as e:
                self.logger.debug(f"Pong send error: {e}")
    
    async def _ping_loop(self) -> None:
        """Send ping messages to keep connection alive."""
        while self._is_connected and self._should_reconnect:
            try:
                await asyncio.sleep(self._ping_interval)
                if self._ws:
                    await self._ws.send(json.dumps({"op": "ping"}))
            except Exception as e:
                self.logger.debug(f"Ping loop error: {e}")
                break


class OKXExchange(BaseExchange):
    """
    OKX Exchange Integration (V5 API).
    
    This class provides comprehensive integration with the OKX exchange:
    1. Spot trading
    2. Futures trading (USDⓈ-M and COIN-M)
    3. Perpetual trading
    4. Options trading
    5. Margin trading
    6. WebSocket streams
    
    Features:
    - Full REST API V5 support
    - WebSocket stream V5 support
    - Rate limiting
    - Error handling
    - Automatic retry
    - Comprehensive order management
    - Position management
    - Balance management
    - Market data
    - OHLCV data
    - Ticker data
    - Order book data
    - Funding rate data
    - Options data
    """
    
    def __init__(
        self,
        config: ExchangeConfig,
        market_type: MarketType = MarketType.SPOT,
    ):
        """
        Initialize the OKX exchange adapter.
        
        Args:
            config: Exchange configuration
            market_type: Market type (spot, futures, etc.)
        """
        super().__init__(config)
        self.market_type = market_type
        self.api_base = OKX_API_BASE
        self.api_version = "v5"
        
        # Map market types to OKX instrument types
        self.instrument_type_map = {
            MarketType.SPOT: "SPOT",
            MarketType.FUTURES: "FUTURES",
            MarketType.PERPETUAL: "SWAP",
            MarketType.OPTION: "OPTION",
        }
        self.instrument_type = self.instrument_type_map.get(
            market_type, "SPOT"
        )
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        
        # WebSocket
        self._ws: Optional[OKXWebSocket] = None
        self._ws_private: Optional[OKXWebSocket] = None
        
        # Cache
        self._symbols_cache: Optional[List[str]] = None
        self._instrument_cache: Dict[str, Dict] = {}
        
        self.logger.info(f"Initialized OKX {market_type.value} exchange")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
                    self._session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                    )
        return self._session
    
    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        
        if self._ws:
            await self._ws.disconnect()
            self._ws = None
        
        if self._ws_private:
            await self._ws_private.disconnect()
            self._ws_private = None
    
    def _get_headers(self, method: str, request_path: str, body: str = "") -> Dict[str, str]:
        """Get request headers with signature."""
        timestamp = str(int(time.time()))
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "OK-ACCESS-KEY": self.config.api_key or "",
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.config.api_passphrase or "",
        }
        
        if self.config.api_key and self.config.api_secret:
            # Generate signature
            signature = base64.b64encode(
                hmac.new(
                    self.config.api_secret.encode('utf-8'),
                    f"{timestamp}{method}{request_path}{body}".encode('utf-8'),
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')
            headers["OK-ACCESS-SIGN"] = signature
        
        return headers
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """
        Make a request to the OKX API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            signed: Whether the request needs to be signed
            
        Returns:
            API response
        """
        self._check_rate_limit()
        self.metrics["requests_total"] += 1
        
        url = f"{self.api_base}{endpoint}"
        
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        
        # Build request body
        body = json.dumps(data) if data else ""
        
        # Get headers
        headers = self._get_headers(method, endpoint, body if signed else "")
        
        session = await self._get_session()
        
        try:
            async with session.request(
                method,
                url,
                params=params,
                json=data,
                headers=headers,
            ) as response:
                self._request_count += 1
                
                if response.status == 429:
                    self.metrics["requests_failed"] += 1
                    retry_after = int(response.headers.get("Retry-After", 10))
                    self.logger.warning(f"Rate limited, retry after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return await self._request(method, endpoint, params, data, signed)
                
                if response.status != 200:
                    error_text = await response.text()
                    self.metrics["requests_failed"] += 1
                    self.logger.error(f"API error {response.status}: {error_text}")
                    raise self.ExchangeError(f"API error {response.status}: {error_text}")
                
                result = await response.json()
                
                # Check OKX response code
                code = result.get("code", "1")
                if code != "0":
                    error_msg = result.get("msg", "Unknown error")
                    self.metrics["requests_failed"] += 1
                    raise self.ExchangeError(f"OKX error [{code}]: {error_msg}")
                
                self.metrics["requests_success"] += 1
                return result.get("data", [{}])[0] if result.get("data") else {}
                
        except asyncio.TimeoutError:
            self.metrics["requests_failed"] += 1
            self.metrics["errors"] += 1
            raise self.ExchangeError("Request timeout")
        except Exception as e:
            self.metrics["requests_failed"] += 1
            self.metrics["errors"] += 1
            raise
    
    async def _get_instruments(self) -> List[Dict]:
        """Get instrument information."""
        try:
            endpoint = "/api/v5/public/instruments"
            
            result = await self._request(
                "GET",
                endpoint,
                {"instType": self.instrument_type}
            )
            
            if result and isinstance(result, list):
                return result
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to get instruments: {e}")
            return []
    
    # Market Data Methods
    
    async def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get ticker information for a symbol."""
        try:
            endpoint = "/api/v5/market/ticker"
            
            result = await self._request(
                "GET",
                endpoint,
                {"instId": symbol}
            )
            
            if not result:
                return None
            
            return Ticker(
                symbol=symbol,
                bid=Decimal(result.get("bidPx", 0)),
                ask=Decimal(result.get("askPx", 0)),
                last=Decimal(result.get("last", 0)),
                high=Decimal(result.get("high24h", 0)),
                low=Decimal(result.get("low24h", 0)),
                volume=Decimal(result.get("vol24h", 0)),
                volume_usd=Decimal(result.get("volCcy24h", 0)),
                change_24h=Decimal(result.get("last", 0)) - Decimal(result.get("open24h", 0)),
                change_percent_24h=Decimal(result.get("last", 0)) / Decimal(result.get("open24h", 1)) * 100 - 100,
                timestamp=datetime.utcnow(),
            )
        except Exception as e:
            self.logger.error(f"Failed to get ticker for {symbol}: {e}")
            return None
    
    async def get_order_book(
        self,
        symbol: str,
        limit: int = 100,
    ) -> Optional[OrderBook]:
        """Get order book for a symbol."""
        try:
            endpoint = "/api/v5/market/books"
            
            result = await self._request(
                "GET",
                endpoint,
                {"instId": symbol, "sz": limit}
            )
            
            if not result:
                return None
            
            bids = [
                (Decimal(b[0]), Decimal(b[1]))
                for b in result.get("bids", [])[:limit]
            ]
            asks = [
                (Decimal(a[0]), Decimal(a[1]))
                for a in result.get("asks", [])[:limit]
            ]
            
            return OrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow(),
            )
        except Exception as e:
            self.logger.error(f"Failed to get order book for {symbol}: {e}")
            return None
    
    async def get_ohlcv(
        self,
        symbol: str,
        interval: Interval,
        limit: int = 100,
    ) -> List[OHLCV]:
        """Get OHLCV candlestick data."""
        try:
            interval_map = {
                Interval.M1: "1m", Interval.M3: "3m", Interval.M5: "5m",
                Interval.M15: "15m", Interval.M30: "30m",
                Interval.H1: "1H", Interval.H2: "2H", Interval.H4: "4H",
                Interval.H6: "6H", Interval.H8: "8H", Interval.H12: "12H",
                Interval.D1: "1D", Interval.D3: "3D",
                Interval.W1: "1W", Interval.MN1: "1M",
            }
            
            endpoint = "/api/v5/market/candles"
            
            result = await self._request(
                "GET",
                endpoint,
                {
                    "instId": symbol,
                    "bar": interval_map[interval],
                    "limit": limit,
                }
            )
            
            if not result or not isinstance(result, list):
                return []
            
            ohlcv_list = []
            for candle in result:
                ohlcv_list.append(OHLCV(
                    symbol=symbol,
                    interval=interval,
                    open=Decimal(candle[1]),
                    high=Decimal(candle[2]),
                    low=Decimal(candle[3]),
                    close=Decimal(candle[4]),
                    volume=Decimal(candle[5]),
                    timestamp=datetime.fromtimestamp(int(candle[0]) / 1000),
                    close_time=datetime.fromtimestamp(int(candle[0]) / 1000),
                ))
            
            return ohlcv_list
        except Exception as e:
            self.logger.error(f"Failed to get OHLCV for {symbol}: {e}")
            return []
    
    async def get_historical_prices(
        self,
        symbol: str,
        interval: Interval,
        start_time: datetime,
        end_time: datetime,
    ) -> List[OHLCV]:
        """Get historical prices for a time range."""
        interval_map = {
            Interval.M1: "1m", Interval.M5: "5m",
            Interval.H1: "1H", Interval.H4: "4H",
            Interval.D1: "1D", Interval.W1: "1W",
        }
        
        all_candles = []
        current_time = start_time
        limit = 100
        
        while current_time < end_time:
            params = {
                "instId": symbol,
                "bar": interval_map.get(interval, "1m"),
                "after": int(current_time.timestamp() * 1000),
                "limit": limit,
            }
            
            result = await self._request("GET", "/api/v5/market/candles", params)
            if not result or not isinstance(result, list):
                break
            
            for candle in result:
                candle_time = datetime.fromtimestamp(int(candle[0]) / 1000)
                if candle_time > end_time:
                    continue
                if candle_time < start_time:
                    continue
                    
                all_candles.append(OHLCV(
                    symbol=symbol,
                    interval=interval,
                    open=Decimal(candle[1]),
                    high=Decimal(candle[2]),
                    low=Decimal(candle[3]),
                    close=Decimal(candle[4]),
                    volume=Decimal(candle[5]),
                    timestamp=candle_time,
                    close_time=candle_time,
                ))
            
            if len(result) < limit:
                break
            
            current_time = datetime.fromtimestamp(int(result[-1][0]) / 1000) + timedelta(seconds=1)
            await asyncio.sleep(0.1)
        
        return all_candles
    
    # Order Management Methods
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        reduce_only: bool = False,
        post_only: bool = False,
        client_order_id: Optional[str] = None,
        **kwargs,
    ) -> Optional[Order]:
        """Place an order."""
        try:
            endpoint = "/api/v5/trade/order"
            
            # Build parameters
            side_map = {
                OrderSide.BUY: "buy",
                OrderSide.SELL: "sell",
            }
            
            order_type_map = {
                OrderType.MARKET: "market",
                OrderType.LIMIT: "limit",
                OrderType.STOP: "stop",
                OrderType.STOP_LIMIT: "stop_limit",
            }
            
            time_in_force_map = {
                TimeInForce.GTC: "GTC",
                TimeInForce.IOC: "IOC",
                TimeInForce.FOK: "FOK",
                TimeInForce.POST_ONLY: "post_only",
            }
            
            data = {
                "instId": symbol,
                "side": side_map[side],
                "ordType": order_type_map.get(order_type, "limit"),
                "sz": str(float(quantity)),
                "tdMode": "cash" if self.market_type == MarketType.SPOT else "cross",
            }
            
            if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if price is None:
                    raise ValueError("Price required for limit orders")
                data["px"] = str(float(price))
                data["tgtCcy"] = "base_ccy"
            
            if order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                if stop_price is None:
                    raise ValueError("Stop price required for stop orders")
                data["stopPx"] = str(float(stop_price))
            
            if time_in_force != TimeInForce.GTC:
                data["timeInForce"] = time_in_force_map.get(time_in_force, "GTC")
            
            if reduce_only:
                data["reduceOnly"] = "true"
            
            if post_only:
                data["postOnly"] = "true"
            
            if client_order_id:
                data["clOrdId"] = client_order_id
            else:
                data["clOrdId"] = f"nexus_{int(time.time() * 1000)}"
            
            # Place order
            result = await self._request("POST", endpoint, data=data, signed=True)
            
            if not result:
                return None
            
            status_map = {
                "live": OrderStatus.OPEN,
                "partially_filled": OrderStatus.PARTIALLY_FILLED,
                "filled": OrderStatus.FILLED,
                "canceled": OrderStatus.CANCELLED,
                "rejected": OrderStatus.REJECTED,
                "expired": OrderStatus.EXPIRED,
            }
            
            order = Order(
                order_id=result.get("ordId", ""),
                exchange=self.exchange_type,
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=price,
                quantity=quantity,
                filled_quantity=Decimal(result.get("accFillSz", 0)),
                remaining_quantity=quantity - Decimal(result.get("accFillSz", 0)),
                status=status_map.get(result.get("state", ""), OrderStatus.PENDING),
                created_at=datetime.utcnow(),
                client_order_id=data["clOrdId"],
            )
            
            self.metrics["orders_placed"] += 1
            return order
            
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            self.metrics["errors"] += 1
            return None
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        try:
            endpoint = "/api/v5/trade/cancel-order"
            
            data = {
                "instId": symbol,
                "ordId": order_id,
            }
            
            await self._request("POST", endpoint, data=data, signed=True)
            self.metrics["orders_cancelled"] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all orders for a symbol."""
        try:
            endpoint = "/api/v5/trade/cancel-all-orders"
            
            data = {"instId": symbol}
            
            await self._request("POST", endpoint, data=data, signed=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel all orders for {symbol}: {e}")
            return False
    
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Get order status."""
        try:
            endpoint = "/api/v5/trade/order"
            
            result = await self._request(
                "GET",
                endpoint,
                {"instId": symbol, "ordId": order_id},
                signed=True
            )
            
            if not result:
                return None
            
            status_map = {
                "live": OrderStatus.OPEN,
                "partially_filled": OrderStatus.PARTIALLY_FILLED,
                "filled": OrderStatus.FILLED,
                "canceled": OrderStatus.CANCELLED,
                "rejected": OrderStatus.REJECTED,
                "expired": OrderStatus.EXPIRED,
            }
            
            return Order(
                order_id=result.get("ordId", ""),
                exchange=self.exchange_type,
                symbol=result.get("instId", ""),
                side=OrderSide(result.get("side", "").lower()),
                order_type=OrderType(result.get("ordType", "").lower()),
                price=Decimal(result.get("px", 0)) if result.get("px") else None,
                quantity=Decimal(result.get("sz", 0)),
                filled_quantity=Decimal(result.get("accFillSz", 0)),
                remaining_quantity=Decimal(result.get("sz", 0)) - Decimal(result.get("accFillSz", 0)),
                status=status_map.get(result.get("state", ""), OrderStatus.PENDING),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                client_order_id=result.get("clOrdId"),
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    async def get_open_orders(self, symbol: str) -> List[Order]:
        """Get open orders for a symbol."""
        try:
            endpoint = "/api/v5/trade/orders-pending"
            
            result = await self._request(
                "GET",
                endpoint,
                {"instId": symbol},
                signed=True
            )
            
            if not result or not isinstance(result, list):
                return []
            
            orders = []
            for item in result:
                status_map = {
                    "live": OrderStatus.OPEN,
                    "partially_filled": OrderStatus.PARTIALLY_FILLED,
                }
                
                orders.append(Order(
                    order_id=item.get("ordId", ""),
                    exchange=self.exchange_type,
                    symbol=item.get("instId", ""),
                    side=OrderSide(item.get("side", "").lower()),
                    order_type=OrderType(item.get("ordType", "").lower()),
                    price=Decimal(item.get("px", 0)) if item.get("px") else None,
                    quantity=Decimal(item.get("sz", 0)),
                    filled_quantity=Decimal(item.get("accFillSz", 0)),
                    remaining_quantity=Decimal(item.get("sz", 0)) - Decimal(item.get("accFillSz", 0)),
                    status=status_map.get(item.get("state", ""), OrderStatus.PENDING),
                    created_at=datetime.utcnow(),
                    client_order_id=item.get("clOrdId"),
                ))
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Failed to get open orders for {symbol}: {e}")
            return []
    
    async def get_order_history(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Order]:
        """Get order history."""
        try:
            endpoint = "/api/v5/trade/orders-history"
            
            params = {
                "instId": symbol,
                "limit": limit,
            }
            
            if start_time:
                params["after"] = int(start_time.timestamp() * 1000)
            if end_time:
                params["before"] = int(end_time.timestamp() * 1000)
            
            result = await self._request("GET", endpoint, params, signed=True)
            
            if not result or not isinstance(result, list):
                return []
            
            orders = []
            for item in result:
                status_map = {
                    "filled": OrderStatus.FILLED,
                    "canceled": OrderStatus.CANCELLED,
                    "rejected": OrderStatus.REJECTED,
                    "expired": OrderStatus.EXPIRED,
                }
                
                orders.append(Order(
                    order_id=item.get("ordId", ""),
                    exchange=self.exchange_type,
                    symbol=item.get("instId", ""),
                    side=OrderSide(item.get("side", "").lower()),
                    order_type=OrderType(item.get("ordType", "").lower()),
                    price=Decimal(item.get("px", 0)) if item.get("px") else None,
                    quantity=Decimal(item.get("sz", 0)),
                    filled_quantity=Decimal(item.get("accFillSz", 0)),
                    remaining_quantity=Decimal(item.get("sz", 0)) - Decimal(item.get("accFillSz", 0)),
                    status=status_map.get(item.get("state", ""), OrderStatus.FILLED),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    client_order_id=item.get("clOrdId"),
                ))
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Failed to get order history for {symbol}: {e}")
            return []
    
    # Account Management Methods
    
    async def get_balances(self) -> Dict[str, Balance]:
        """Get account balances."""
        try:
            endpoint = "/api/v5/account/balance"
            
            result = await self._request("GET", endpoint, signed=True)
            
            if not result:
                return {}
            
            balances = {}
            for item in result.get("details", []):
                asset = item.get("ccy", "")
                balances[asset] = Balance(
                    asset=asset,
                    free=Decimal(item.get("cashBal", 0)),
                    locked=Decimal(item.get("frozenBal", 0)),
                    total=Decimal(item.get("eq", 0)),
                    usd_value=Decimal(item.get("eqUsd", 0)),
                    timestamp=datetime.utcnow(),
                )
            
            return balances
            
        except Exception as e:
            self.logger.error(f"Failed to get balances: {e}")
            return {}
    
    async def get_balance(self, asset: str) -> Optional[Balance]:
        """Get balance for a specific asset."""
        balances = await self.get_balances()
        return balances.get(asset.upper())
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        try:
            if self.market_type == MarketType.SPOT:
                return []
            
            endpoint = "/api/v5/account/positions"
            
            result = await self._request("GET", endpoint, signed=True)
            
            if not result or not isinstance(result, list):
                return []
            
            positions = []
            for item in result:
                if Decimal(item.get("pos", 0)) == 0:
                    continue
                
                side = OrderSide.LONG if item.get("posSide") == "long" else OrderSide.SHORT
                positions.append(Position(
                    symbol=item.get("instId", ""),
                    side=side,
                    size=abs(Decimal(item.get("pos", 0))),
                    entry_price=Decimal(item.get("avgPx", 0)),
                    current_price=Decimal(item.get("markPx", 0)),
                    mark_price=Decimal(item.get("markPx", 0)),
                    liquidation_price=Decimal(item.get("liqPx", 0)),
                    unrealized_pnl=Decimal(item.get("upl", 0)),
                    realized_pnl=Decimal(item.get("realizedPnl", 0)),
                    leverage=Decimal(item.get("lever", 1)),
                    margin=Decimal(item.get("margin", 0)),
                    maintenance_margin=Decimal(item.get("maintMargin", 0)),
                    timestamp=datetime.utcnow(),
                ))
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return []
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        positions = await self.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None
    
    # Additional Methods
    
    async def get_symbols(self) -> List[str]:
        """Get all available trading symbols."""
        try:
            endpoint = "/api/v5/public/instruments"
            
            result = await self._request(
                "GET",
                endpoint,
                {"instType": self.instrument_type}
            )
            
            if not result or not isinstance(result, list):
                return []
            
            symbols = []
            for item in result:
                symbol = item.get("instId", "")
                if symbol and item.get("state") == "live":
                    symbols.append(symbol)
            
            return symbols
            
        except Exception as e:
            self.logger.error(f"Failed to get symbols: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get funding rate for a perpetual symbol."""
        try:
            if self.market_type != MarketType.PERPETUAL:
                return None
            
            endpoint = "/api/v5/public/funding-rate"
            
            result = await self._request(
                "GET",
                endpoint,
                {"instId": symbol}
            )
            
            if not result:
                return None
            
            return FundingRate(
                symbol=symbol,
                funding_rate=Decimal(result.get("fundingRate", 0)),
                predicted_rate=Decimal(result.get("nextFundingRate", 0)),
                next_funding_time=datetime.utcnow(),
                interval_hours=8,
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get funding rate for {symbol}: {e}")
            return None
    
    # WebSocket Methods
    
    async def connect_websocket(self, private: bool = False) -> bool:
        """Connect to WebSocket stream."""
        try:
            ws_url = OKX_WS_PRIVATE if private else OKX_WS_BASE
            ws = OKXWebSocket(self, ws_url)
            
            if private:
                self._ws_private = ws
            else:
                self._ws = ws
            
            await ws.connect()
            return True
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
            return False
    
    async def disconnect_websocket(self, private: bool = False) -> bool:
        """Disconnect from WebSocket stream."""
        ws = self._ws_private if private else self._ws
        if ws:
            await ws.disconnect()
            if private:
                self._ws_private = None
            else:
                self._ws = None
            return True
        return False
    
    async def subscribe_ticker(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None],
    ) -> bool:
        """Subscribe to ticker updates."""
        if not self._ws:
            return False
        
        await self._ws.subscribe("ticker", symbols, callback)
        return True
    
    async def subscribe_order_book(
        self,
        symbols: List[str],
        callback: Callable[[OrderBook], None],
    ) -> bool:
        """Subscribe to order book updates."""
        if not self._ws:
            return False
        
        await self._ws.subscribe("depth", symbols, callback)
        return True
    
    async def subscribe_trades(
        self,
        symbols: List[str],
        callback: Callable[[Trade], None],
    ) -> bool:
        """Subscribe to trade updates."""
        if not self._ws:
            return False
        
        await self._ws.subscribe("trade", symbols, callback)
        return True
    
    async def subscribe_user_data(
        self,
        callback: Callable[[Dict[str, Any]], None],
    ) -> bool:
        """Subscribe to user data updates."""
        if not self._ws_private:
            await self.connect_websocket(private=True)
        
        if not self._ws_private:
            return False
        
        await self._ws_private.subscribe("account", ["ALL"], callback)
        await self._ws_private.subscribe("positions", ["ALL"], callback)
        await self._ws_private.subscribe("orders", ["ALL"], callback)
        return True
    
    # Utility Methods
    
    async def ping(self) -> bool:
        """Ping the exchange to check connectivity."""
        try:
            endpoint = "/api/v5/public/time"
            result = await self._request("GET", endpoint)
            return result is not None
        except Exception:
            return False
    
    async def get_server_time(self) -> datetime:
        """Get server time."""
        try:
            endpoint = "/api/v5/public/time"
            result = await self._request("GET", endpoint)
            if result and "ts" in result:
                return datetime.fromtimestamp(int(result["ts"]) / 1000)
        except Exception:
            pass
        return datetime.utcnow()
    
    def _parse_order_status(self, status: str) -> OrderStatus:
        """Parse order status string."""
        status_map = {
            "live": OrderStatus.OPEN,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
            "expired": OrderStatus.EXPIRED,
        }
        return status_map.get(status.lower(), OrderStatus.PENDING)

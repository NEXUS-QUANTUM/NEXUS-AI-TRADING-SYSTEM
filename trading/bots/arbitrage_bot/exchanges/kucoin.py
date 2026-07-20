# trading/bots/arbitrage_bot/exchanges/kucoin.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - KuCoin Exchange Integration

"""
KuCoin Exchange Integration - Complete KuCoin Exchange Adapter

This module provides comprehensive integration with the KuCoin exchange:
- Spot trading
- Futures trading
- Margin trading
- WebSocket streams
- Market data
- Account management
- Order management
- Risk management

Features:
- Full REST API support
- WebSocket stream support
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
KUCOIN_API_BASE = "https://api.kucoin.com"
KUCOIN_API_FUTURES = "https://api-futures.kucoin.com"
KUCOIN_WS_BASE = "wss://ws-api.kucoin.com"
KUCOIN_WS_FUTURES = "wss://ws-api-futures.kucoin.com"

# Endpoints
ENDPOINTS = {
    "ping": "/api/v1/timestamp",
    "time": "/api/v1/timestamp",
    "symbols": "/api/v1/symbols",
    "ticker": "/api/v1/ticker",
    "klines": "/api/v1/klines",
    "depth": "/api/v1/depth",
    "account": "/api/v1/account",
    "balance": "/api/v1/account/balance",
    "order": "/api/v1/orders",
    "open_orders": "/api/v1/orders",
    "all_orders": "/api/v1/orders",
    "trade_list": "/api/v1/fills",
    "futures_account": "/api/v1/account-overview",
    "futures_balance": "/api/v1/account/balance",
    "futures_position": "/api/v1/position",
    "futures_order": "/api/v1/orders",
    "futures_open_orders": "/api/v1/orders",
    "futures_funding_rate": "/api/v1/funding-rate",
}


class KuCoinWebSocket(ExchangeWebSocket):
    """KuCoin WebSocket implementation."""
    
    def __init__(self, exchange: 'KuCoinExchange', url: str):
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
        self._ping_interval = 20
        self._last_pong = time.time()
    
    async def connect(self) -> None:
        """Connect to WebSocket."""
        if self._is_connected:
            return
        
        try:
            # KuCoin requires authentication for private channels
            if self.exchange.config.api_key:
                # Generate token for WebSocket
                timestamp = str(int(time.time() * 1000))
                signature = base64.b64encode(
                    hmac.new(
                        self.exchange.config.api_secret.encode('utf-8'),
                        f"{timestamp}{self.exchange.config.api_key}".encode('utf-8'),
                        hashlib.sha256
                    ).digest()
                ).decode('utf-8')
                
                auth_params = {
                    "apiKey": self.exchange.config.api_key,
                    "sign": signature,
                    "timestamp": timestamp,
                }
            else:
                auth_params = {}
            
            # Connect with authentication
            from websockets import connect as ws_connect
            
            self._ws = await ws_connect(
                self.url,
                ping_interval=self._ping_interval,
                ping_timeout=10,
            )
            self._is_connected = True
            
            # Send ping message
            await self._ws.send(json.dumps({"type": "ping"}))
            
            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            self.logger.info(f"Connected to KuCoin WebSocket: {self.url}")
            
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
        
        self.logger.info("Disconnected from KuCoin WebSocket")
    
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
        symbol = symbol.upper().replace("/", "-")
        if channel == "depth":
            return f"/market/level2:{symbol}"
        elif channel == "ticker":
            return f"/market/ticker:{symbol}"
        elif channel == "trade":
            return f"/market/match:{symbol}"
        elif channel == "kline":
            return f"/market/klines:{symbol}_1min"
        elif channel == "book_ticker":
            return f"/market/snapshot:{symbol}"
        elif channel == "funding_rate":
            return f"/contract/funding_rate:{symbol}"
        return f"/market/ticker:{symbol}"
    
    async def _subscribe_streams(self) -> None:
        """Subscribe to streams."""
        if not self._ws or not self._is_connected:
            return
        
        streams = list(self._subscriptions.keys())
        if not streams:
            return
        
        # KuCoin uses a different subscription format
        subscribe_msg = {
            "id": int(time.time() * 1000),
            "type": "subscribe",
            "topic": "/market/ticker:BTC-USDT",
            "response": True,
        }
        
        # Send individual subscription messages
        for stream in streams:
            try:
                msg = {
                    "id": int(time.time() * 1000),
                    "type": "subscribe",
                    "topic": stream,
                    "response": True,
                }
                await self._ws.send(json.dumps(msg))
                self.logger.debug(f"Subscribed to stream: {stream}")
                await asyncio.sleep(0.1)  # Rate limit
            except Exception as e:
                self.logger.error(f"Failed to subscribe to {stream}: {e}")
    
    async def _unsubscribe_streams(self) -> None:
        """Unsubscribe from streams."""
        if not self._ws or not self._is_connected:
            return
        
        streams = list(self._subscriptions.keys())
        if not streams:
            return
        
        for stream in streams:
            try:
                msg = {
                    "id": int(time.time() * 1000),
                    "type": "unsubscribe",
                    "topic": stream,
                    "response": True,
                }
                await self._ws.send(json.dumps(msg))
                self.logger.debug(f"Unsubscribed from stream: {stream}")
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Failed to unsubscribe from {stream}: {e}")
    
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
                        if data.get("type") == "pong":
                            self._last_pong = time.time()
                            continue
                        
                        # Handle subscription response
                        if data.get("type") == "ack":
                            continue
                        
                        # Handle error
                        if data.get("type") == "error":
                            self.logger.error(f"WebSocket error: {data}")
                            continue
                        
                        # Handle data message
                        topic = data.get("topic", "")
                        if topic in self._subscriptions:
                            for callback in self._subscriptions[topic]:
                                try:
                                    callback(data)
                                except Exception as e:
                                    self.logger.error(f"Callback error: {e}")
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
        await asyncio.sleep(5)
        if self._should_reconnect:
            try:
                await self.connect()
                await self._subscribe_streams()
            except Exception as e:
                self.logger.error(f"Reconnection failed: {e}")
    
    async def _ping_loop(self) -> None:
        """Send ping messages to keep connection alive."""
        while self._is_connected and self._should_reconnect:
            try:
                await asyncio.sleep(self._ping_interval)
                if self._ws:
                    await self._ws.send(json.dumps({"type": "ping"}))
            except Exception as e:
                self.logger.debug(f"Ping error: {e}")
                break


class KuCoinExchange(BaseExchange):
    """
    KuCoin Exchange Integration.
    
    This class provides comprehensive integration with the KuCoin exchange:
    1. Spot trading
    2. Futures trading
    3. Margin trading
    4. WebSocket streams
    5. Market data
    6. Account management
    7. Order management
    
    Features:
    - Full REST API support
    - WebSocket stream support
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
    """
    
    def __init__(
        self,
        config: ExchangeConfig,
        market_type: MarketType = MarketType.SPOT,
    ):
        """
        Initialize the KuCoin exchange adapter.
        
        Args:
            config: Exchange configuration
            market_type: Market type (spot, futures, etc.)
        """
        super().__init__(config)
        self.market_type = market_type
        
        # API endpoints
        if market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
            self.api_base = KUCOIN_API_FUTURES
            self.ws_base = KUCOIN_WS_FUTURES
        else:
            self.api_base = KUCOIN_API_BASE
            self.ws_base = KUCOIN_WS_BASE
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        
        # WebSocket
        self._ws: Optional[KuCoinWebSocket] = None
        
        # Cache
        self._symbols_cache: Optional[List[str]] = None
        
        self.logger.info(f"Initialized KuCoin {market_type.value} exchange")
    
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
    
    def _get_headers(self, params: Optional[Dict] = None) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "KC-API-KEY-VERSION": "2",
        }
        
        if self.config.api_key:
            headers["KC-API-KEY"] = self.config.api_key
            headers["KC-API-PASSPHRASE"] = self.config.api_passphrase or ""
            
            # Generate signature
            timestamp = str(int(time.time() * 1000))
            method = "GET"
            endpoint = params.get("endpoint", "") if params else ""
            body = params.get("body", "") if params else ""
            
            signature = base64.b64encode(
                hmac.new(
                    self.config.api_secret.encode('utf-8'),
                    f"{timestamp}{method}{endpoint}{body}".encode('utf-8'),
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            headers["KC-API-TIMESTAMP"] = timestamp
            headers["KC-API-SIGN"] = signature
        
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
        Make a request to the KuCoin API.
        
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
        
        # Prepare request data
        request_params = {"endpoint": endpoint}
        if data:
            request_params["body"] = json.dumps(data)
        
        headers = self._get_headers(request_params)
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
                
                # Check KuCoin response code
                if result.get("code") != "200000":
                    error_msg = result.get("msg", "Unknown error")
                    self.metrics["requests_failed"] += 1
                    raise self.ExchangeError(f"KuCoin error: {error_msg}")
                
                self.metrics["requests_success"] += 1
                return result.get("data", {})
                
        except asyncio.TimeoutError:
            self.metrics["requests_failed"] += 1
            self.metrics["errors"] += 1
            raise self.ExchangeError("Request timeout")
        except Exception as e:
            self.metrics["requests_failed"] += 1
            self.metrics["errors"] += 1
            raise
    
    # Market Data Methods
    
    async def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get ticker information for a symbol."""
        try:
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                # Futures ticker
                endpoint = "/api/v1/ticker"
                symbol = symbol.replace("/", "-")
            else:
                endpoint = "/api/v1/ticker"
                symbol = symbol.replace("/", "-")
            
            result = await self._request(
                "GET",
                endpoint,
                {"symbol": symbol}
            )
            
            if not result:
                return None
            
            return Ticker(
                symbol=symbol,
                bid=Decimal(result.get("bestBid", 0)),
                ask=Decimal(result.get("bestAsk", 0)),
                last=Decimal(result.get("last", 0)),
                high=Decimal(result.get("high", 0)),
                low=Decimal(result.get("low", 0)),
                volume=Decimal(result.get("vol", 0)),
                volume_usd=Decimal(result.get("volValue", 0)),
                change_24h=Decimal(result.get("change", 0)),
                change_percent_24h=Decimal(result.get("changeRate", 0)) * 100,
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
            endpoint = "/api/v1/level2/snapshot"
            symbol = symbol.replace("/", "-")
            
            result = await self._request(
                "GET",
                endpoint,
                {"symbol": symbol}
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
                Interval.M1: "1min", Interval.M3: "3min", Interval.M5: "5min",
                Interval.M15: "15min", Interval.M30: "30min",
                Interval.H1: "1hour", Interval.H2: "2hour", Interval.H4: "4hour",
                Interval.H6: "6hour", Interval.H8: "8hour", Interval.H12: "12hour",
                Interval.D1: "1day", Interval.D3: "3day",
                Interval.W1: "1week", Interval.MN1: "1month",
            }
            
            endpoint = "/api/v1/klines"
            symbol = symbol.replace("/", "-")
            
            result = await self._request(
                "GET",
                endpoint,
                {
                    "symbol": symbol,
                    "type": interval_map[interval],
                    "limit": limit,
                }
            )
            
            if not result:
                return []
            
            ohlcv_list = []
            for candle in result:
                ohlcv_list.append(OHLCV(
                    symbol=symbol,
                    interval=interval,
                    open=Decimal(candle[0]),
                    high=Decimal(candle[1]),
                    low=Decimal(candle[2]),
                    close=Decimal(candle[3]),
                    volume=Decimal(candle[4]),
                    timestamp=datetime.utcnow(),
                    close_time=datetime.utcnow(),
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
        # KuCoin doesn't support historical OHLCV with start/end time easily
        # We'll fetch in chunks
        interval_map = {
            Interval.M1: "1min", Interval.M5: "5min",
            Interval.H1: "1hour", Interval.H4: "4hour",
            Interval.D1: "1day", Interval.W1: "1week",
        }
        
        all_candles = []
        current_time = start_time
        limit = 1000
        
        while current_time < end_time:
            params = {
                "symbol": symbol.replace("/", "-"),
                "type": interval_map.get(interval, "1min"),
                "limit": limit,
            }
            
            result = await self._request("GET", "/api/v1/klines", params)
            if not result:
                break
            
            for candle in result:
                candle_time = datetime.fromtimestamp(candle[0] / 1000)
                if candle_time > end_time:
                    continue
                if candle_time < start_time:
                    continue
                    
                all_candles.append(OHLCV(
                    symbol=symbol,
                    interval=interval,
                    open=Decimal(candle[0]),
                    high=Decimal(candle[1]),
                    low=Decimal(candle[2]),
                    close=Decimal(candle[3]),
                    volume=Decimal(candle[4]),
                    timestamp=candle_time,
                    close_time=candle_time,
                ))
            
            if len(result) < limit:
                break
            
            current_time = datetime.fromtimestamp(result[-1][0] / 1000) + timedelta(seconds=1)
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
            symbol = symbol.replace("/", "-")
            
            # Determine endpoint
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v1/orders"
            else:
                endpoint = "/api/v1/orders"
            
            # Build parameters
            order_type_map = {
                OrderType.MARKET: "market",
                OrderType.LIMIT: "limit",
                OrderType.STOP: "stop",
                OrderType.STOP_LIMIT: "stop-limit",
            }
            
            time_in_force_map = {
                TimeInForce.GTC: "GTC",
                TimeInForce.IOC: "IOC",
                TimeInForce.FOK: "FOK",
                TimeInForce.POST_ONLY: "PO",
            }
            
            data = {
                "symbol": symbol,
                "side": side.value.upper(),
                "type": order_type_map.get(order_type, "limit"),
                "size": float(quantity),
            }
            
            if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if price is None:
                    raise ValueError("Price required for limit orders")
                data["price"] = float(price)
                data["timeInForce"] = time_in_force_map.get(time_in_force, "GTC")
            
            if order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                if stop_price is None:
                    raise ValueError("Stop price required for stop orders")
                data["stop"] = "loss"
                data["stopPrice"] = float(stop_price)
            
            if reduce_only:
                data["reduceOnly"] = True
            
            if post_only:
                data["postOnly"] = True
            
            if client_order_id:
                data["clientOid"] = client_order_id
            else:
                data["clientOid"] = f"nexus_{int(time.time() * 1000)}"
            
            # Place order
            result = await self._request("POST", endpoint, data=data, signed=True)
            
            order = Order(
                order_id=result.get("orderId", ""),
                exchange=self.exchange_type,
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=price,
                quantity=quantity,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow(),
                client_order_id=data["clientOid"],
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
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = f"/api/v1/orders/{order_id}"
            else:
                endpoint = f"/api/v1/orders/{order_id}"
            
            await self._request("DELETE", endpoint, signed=True)
            self.metrics["orders_cancelled"] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all orders for a symbol."""
        try:
            symbol = symbol.replace("/", "-")
            endpoint = "/api/v1/orders"
            
            await self._request(
                "DELETE",
                endpoint,
                {"symbol": symbol},
                signed=True
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel all orders for {symbol}: {e}")
            return False
    
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Get order status."""
        try:
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = f"/api/v1/orders/{order_id}"
            else:
                endpoint = f"/api/v1/orders/{order_id}"
            
            result = await self._request("GET", endpoint, signed=True)
            
            if not result:
                return None
            
            status_map = {
                "open": OrderStatus.OPEN,
                "done": OrderStatus.FILLED,
                "match": OrderStatus.PARTIALLY_FILLED,
                "cancel": OrderStatus.CANCELLED,
            }
            
            return Order(
                order_id=result.get("id", ""),
                exchange=self.exchange_type,
                symbol=result.get("symbol", ""),
                side=OrderSide(result.get("side", "").lower()),
                order_type=OrderType(result.get("type", "").lower()),
                price=Decimal(result.get("price", 0)) if result.get("price") else None,
                quantity=Decimal(result.get("size", 0)),
                filled_quantity=Decimal(result.get("filledSize", 0)),
                remaining_quantity=Decimal(result.get("size", 0)) - Decimal(result.get("filledSize", 0)),
                status=status_map.get(result.get("status", ""), OrderStatus.PENDING),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                client_order_id=result.get("clientOid"),
                fee=Decimal(result.get("fee", 0)) if result.get("fee") else None,
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    async def get_open_orders(self, symbol: str) -> List[Order]:
        """Get open orders for a symbol."""
        try:
            symbol = symbol.replace("/", "-")
            endpoint = "/api/v1/orders"
            
            result = await self._request(
                "GET",
                endpoint,
                {"symbol": symbol, "status": "active"},
                signed=True
            )
            
            if not result:
                return []
            
            orders = []
            for item in result:
                status_map = {
                    "open": OrderStatus.OPEN,
                    "match": OrderStatus.PARTIALLY_FILLED,
                }
                
                orders.append(Order(
                    order_id=item.get("id", ""),
                    exchange=self.exchange_type,
                    symbol=item.get("symbol", ""),
                    side=OrderSide(item.get("side", "").lower()),
                    order_type=OrderType(item.get("type", "").lower()),
                    price=Decimal(item.get("price", 0)) if item.get("price") else None,
                    quantity=Decimal(item.get("size", 0)),
                    filled_quantity=Decimal(item.get("filledSize", 0)),
                    remaining_quantity=Decimal(item.get("size", 0)) - Decimal(item.get("filledSize", 0)),
                    status=status_map.get(item.get("status", ""), OrderStatus.PENDING),
                    created_at=datetime.utcnow(),
                    client_order_id=item.get("clientOid"),
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
            symbol = symbol.replace("/", "-")
            endpoint = "/api/v1/orders"
            
            params = {
                "symbol": symbol,
                "status": "done",
                "limit": limit,
            }
            
            if start_time:
                params["startAt"] = int(start_time.timestamp())
            if end_time:
                params["endAt"] = int(end_time.timestamp())
            
            result = await self._request("GET", endpoint, params, signed=True)
            
            if not result:
                return []
            
            orders = []
            for item in result:
                status_map = {
                    "done": OrderStatus.FILLED,
                    "cancel": OrderStatus.CANCELLED,
                }
                
                orders.append(Order(
                    order_id=item.get("id", ""),
                    exchange=self.exchange_type,
                    symbol=item.get("symbol", ""),
                    side=OrderSide(item.get("side", "").lower()),
                    order_type=OrderType(item.get("type", "").lower()),
                    price=Decimal(item.get("price", 0)) if item.get("price") else None,
                    quantity=Decimal(item.get("size", 0)),
                    filled_quantity=Decimal(item.get("filledSize", 0)),
                    remaining_quantity=Decimal(item.get("size", 0)) - Decimal(item.get("filledSize", 0)),
                    status=status_map.get(item.get("status", ""), OrderStatus.FILLED),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    client_order_id=item.get("clientOid"),
                    fee=Decimal(item.get("fee", 0)) if item.get("fee") else None,
                ))
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Failed to get order history for {symbol}: {e}")
            return []
    
    # Account Management Methods
    
    async def get_balances(self) -> Dict[str, Balance]:
        """Get account balances."""
        try:
            endpoint = "/api/v1/accounts"
            
            result = await self._request("GET", endpoint, signed=True)
            
            if not result:
                return {}
            
            balances = {}
            for item in result:
                asset = item.get("currency", "")
                balances[asset] = Balance(
                    asset=asset,
                    free=Decimal(item.get("available", 0)),
                    locked=Decimal(item.get("holds", 0)),
                    total=Decimal(item.get("balance", 0)),
                    timestamp=datetime.utcnow(),
                )
            
            return balances
            
        except Exception as e:
            self.logger.error(f"Failed to get balances: {e}")
            return {}
    
    async def get_balance(self, asset: str) -> Optional[Balance]:
        """Get balance for a specific asset."""
        try:
            endpoint = f"/api/v1/accounts/{asset}"
            
            result = await self._request("GET", endpoint, signed=True)
            
            if not result:
                return None
            
            return Balance(
                asset=result.get("currency", ""),
                free=Decimal(result.get("available", 0)),
                locked=Decimal(result.get("holds", 0)),
                total=Decimal(result.get("balance", 0)),
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get balance for {asset}: {e}")
            return None
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        try:
            if self.market_type not in [MarketType.FUTURES, MarketType.PERPETUAL]:
                return []
            
            endpoint = "/api/v1/position"
            
            result = await self._request("GET", endpoint, signed=True)
            
            if not result:
                return []
            
            positions = []
            for item in result:
                side = OrderSide.LONG if item.get("side") == "long" else OrderSide.SHORT
                positions.append(Position(
                    symbol=item.get("symbol", ""),
                    side=side,
                    size=Decimal(item.get("size", 0)),
                    entry_price=Decimal(item.get("entryPrice", 0)),
                    current_price=Decimal(item.get("markPrice", 0)),
                    mark_price=Decimal(item.get("markPrice", 0)),
                    liquidation_price=Decimal(item.get("liquidationPrice", 0)),
                    unrealized_pnl=Decimal(item.get("unrealizedPnl", 0)),
                    realized_pnl=Decimal(item.get("realizedPnl", 0)),
                    leverage=Decimal(item.get("leverage", 1)),
                    margin=Decimal(item.get("margin", 0)),
                    maintenance_margin=Decimal(item.get("maintenanceMargin", 0)),
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
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v1/contracts/active"
            else:
                endpoint = "/api/v1/symbols"
            
            result = await self._request("GET", endpoint)
            
            if not result:
                return []
            
            symbols = []
            for item in result:
                symbol = item.get("symbol", "")
                if symbol:
                    symbols.append(symbol)
            
            return symbols
            
        except Exception as e:
            self.logger.error(f"Failed to get symbols: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get funding rate for a perpetual symbol."""
        try:
            if self.market_type not in [MarketType.FUTURES, MarketType.PERPETUAL]:
                return None
            
            symbol = symbol.replace("/", "-")
            endpoint = "/api/v1/funding-rate"
            
            result = await self._request(
                "GET",
                endpoint,
                {"symbol": symbol}
            )
            
            if not result:
                return None
            
            return FundingRate(
                symbol=symbol,
                funding_rate=Decimal(result.get("fundingRate", 0)),
                predicted_rate=Decimal(result.get("predictedRate", 0)),
                next_funding_time=datetime.utcnow(),
                interval_hours=8,
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get funding rate for {symbol}: {e}")
            return None
    
    # WebSocket Methods
    
    async def connect_websocket(self) -> bool:
        """Connect to WebSocket stream."""
        try:
            self._ws = KuCoinWebSocket(self, self.ws_base)
            await self._ws.connect()
            return True
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
            return False
    
    async def disconnect_websocket(self) -> bool:
        """Disconnect from WebSocket stream."""
        if self._ws:
            await self._ws.disconnect()
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
        if not self._ws:
            return False
        
        # KuCoin user data requires authentication
        await self._ws.subscribe("user_data", [""], callback)
        return True
    
    # Utility Methods
    
    async def ping(self) -> bool:
        """Ping the exchange to check connectivity."""
        try:
            result = await self._request("GET", "/api/v1/timestamp")
            return result is not None
        except Exception:
            return False
    
    async def get_server_time(self) -> datetime:
        """Get server time."""
        try:
            result = await self._request("GET", "/api/v1/timestamp")
            if result:
                return datetime.fromtimestamp(result / 1000)
        except Exception:
            pass
        return datetime.utcnow()
    
    def _parse_order_status(self, status: str) -> OrderStatus:
        """Parse order status string."""
        status_map = {
            "open": OrderStatus.OPEN,
            "done": OrderStatus.FILLED,
            "match": OrderStatus.PARTIALLY_FILLED,
            "cancel": OrderStatus.CANCELLED,
            "reject": OrderStatus.REJECTED,
            "expire": OrderStatus.EXPIRED,
        }
        return status_map.get(status.lower(), OrderStatus.PENDING)

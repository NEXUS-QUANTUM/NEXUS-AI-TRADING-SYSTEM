# trading/bots/arbitrage_bot/exchanges/mexc.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - MEXC Exchange Integration

"""
MEXC Exchange Integration - Complete MEXC Exchange Adapter

This module provides comprehensive integration with the MEXC exchange:
- Spot trading
- Futures trading (USDⓈ-M)
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
MEXC_API_BASE = "https://api.mexc.com"
MEXC_API_FUTURES = "https://api.mexc.com/api/v3"
MEXC_WS_BASE = "wss://wbs.mexc.com/ws"
MEXC_WS_FUTURES = "wss://wbs.mexc.com/ws/futures"

# Endpoints
ENDPOINTS = {
    "ping": "/api/v3/ping",
    "time": "/api/v3/time",
    "exchange_info": "/api/v3/exchangeInfo",
    "depth": "/api/v3/depth",
    "ticker": "/api/v3/ticker/24hr",
    "ticker_price": "/api/v3/ticker/price",
    "klines": "/api/v3/klines",
    "account": "/api/v3/account",
    "balance": "/api/v3/account",
    "order": "/api/v3/order",
    "open_orders": "/api/v3/openOrders",
    "all_orders": "/api/v3/allOrders",
    "trade_list": "/api/v3/myTrades",
    "futures_account": "/api/v3/futures/account",
    "futures_balance": "/api/v3/futures/balance",
    "futures_position": "/api/v3/futures/position",
    "futures_order": "/api/v3/futures/order",
    "futures_open_orders": "/api/v3/futures/openOrders",
    "futures_all_orders": "/api/v3/futures/allOrders",
    "futures_funding_rate": "/api/v3/futures/fundingRate",
    "futures_leverage": "/api/v3/futures/leverage",
}


class MEXCWebSocket(ExchangeWebSocket):
    """MEXC WebSocket implementation."""
    
    def __init__(self, exchange: 'MEXCExchange', url: str):
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
            
            # Send initial ping
            await self._send_ping()
            
            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            self.logger.info(f"Connected to MEXC WebSocket: {self.url}")
            
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
        
        self.logger.info("Disconnected from MEXC WebSocket")
    
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
        symbol = symbol.upper().replace("/", "")
        if channel == "depth":
            return f"{symbol}@depth"
        elif channel == "ticker":
            return f"{symbol}@ticker"
        elif channel == "trade":
            return f"{symbol}@trade"
        elif channel == "kline":
            return f"{symbol}@kline_1m"
        elif channel == "book_ticker":
            return f"{symbol}@bookTicker"
        elif channel == "funding_rate":
            return f"{symbol}@fundingRate"
        return f"{symbol}@ticker"
    
    async def _subscribe_streams(self) -> None:
        """Subscribe to streams."""
        if not self._ws or not self._is_connected:
            return
        
        streams = list(self._subscriptions.keys())
        if not streams:
            return
        
        subscribe_msg = {
            "method": "SUBSCRIPTION",
            "params": streams,
            "id": int(time.time() * 1000),
        }
        
        try:
            await self._ws.send(json.dumps(subscribe_msg))
            self.logger.debug(f"Subscribed to streams: {streams}")
        except Exception as e:
            self.logger.error(f"Failed to subscribe: {e}")
    
    async def _unsubscribe_streams(self) -> None:
        """Unsubscribe from streams."""
        if not self._ws or not self._is_connected:
            return
        
        streams = list(self._subscriptions.keys())
        if not streams:
            return
        
        unsubscribe_msg = {
            "method": "UNSUBSCRIPTION",
            "params": streams,
            "id": int(time.time() * 1000),
        }
        
        try:
            await self._ws.send(json.dumps(unsubscribe_msg))
            self.logger.debug(f"Unsubscribed from streams: {streams}")
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe: {e}")
    
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
                        if data.get("ping"):
                            await self._send_pong(data["ping"])
                            continue
                        
                        # Handle subscription response
                        if data.get("id") and data.get("result"):
                            continue
                        
                        # Handle error
                        if data.get("code") and data.get("code") != 0:
                            self.logger.error(f"WebSocket error: {data}")
                            continue
                        
                        # Handle data message
                        stream = data.get("stream", "")
                        if stream in self._subscriptions:
                            for callback in self._subscriptions[stream]:
                                try:
                                    callback(data.get("data", {}))
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
    
    async def _send_ping(self) -> None:
        """Send ping message."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({"ping": int(time.time() * 1000)}))
                self._last_ping = time.time()
            except Exception as e:
                self.logger.debug(f"Ping send error: {e}")
    
    async def _send_pong(self, ping_id: Any) -> None:
        """Send pong response."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({"pong": ping_id}))
            except Exception as e:
                self.logger.debug(f"Pong send error: {e}")
    
    async def _ping_loop(self) -> None:
        """Send ping messages to keep connection alive."""
        while self._is_connected and self._should_reconnect:
            try:
                await asyncio.sleep(self._ping_interval)
                await self._send_ping()
            except Exception as e:
                self.logger.debug(f"Ping loop error: {e}")
                break


class MEXCExchange(BaseExchange):
    """
    MEXC Exchange Integration.
    
    This class provides comprehensive integration with the MEXC exchange:
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
        Initialize the MEXC exchange adapter.
        
        Args:
            config: Exchange configuration
            market_type: Market type (spot, futures, etc.)
        """
        super().__init__(config)
        self.market_type = market_type
        
        # API endpoints
        if market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
            self.api_base = MEXC_API_FUTURES
            self.ws_base = MEXC_WS_FUTURES
        else:
            self.api_base = MEXC_API_BASE
            self.ws_base = MEXC_WS_BASE
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        
        # WebSocket
        self._ws: Optional[MEXCWebSocket] = None
        
        # Cache
        self._symbols_cache: Optional[List[str]] = None
        
        self.logger.info(f"Initialized MEXC {market_type.value} exchange")
    
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
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if self.config.api_key:
            headers["X-MEXC-APIKEY"] = self.config.api_key
        
        return headers
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature."""
        if not self.config.api_secret:
            raise ValueError("API secret required")
        
        query_string = urlencode(params)
        signature = hmac.new(
            self.config.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """
        Make a request to the MEXC API.
        
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
        headers = self._get_headers()
        
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        else:
            params = {}
        
        # Add timestamp for signed requests
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 5000
            
            # Generate signature
            params["signature"] = self._generate_signature(params)
            headers["X-MEXC-APIKEY"] = self.config.api_key
        
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
                self.metrics["requests_success"] += 1
                return result
                
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
            endpoint = "/api/v3/ticker/24hr"
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/ticker/24hr"
            
            result = await self._request(
                "GET",
                endpoint,
                {"symbol": symbol.upper()}
            )
            
            if not result:
                return None
            
            return Ticker(
                symbol=symbol.upper(),
                bid=Decimal(result.get("bidPrice", 0)),
                ask=Decimal(result.get("askPrice", 0)),
                last=Decimal(result.get("lastPrice", 0)),
                high=Decimal(result.get("highPrice", 0)),
                low=Decimal(result.get("lowPrice", 0)),
                volume=Decimal(result.get("volume", 0)),
                volume_usd=Decimal(result.get("quoteVolume", 0)),
                change_24h=Decimal(result.get("priceChange", 0)),
                change_percent_24h=Decimal(result.get("priceChangePercent", 0)),
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
            endpoint = "/api/v3/depth"
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/depth"
            
            result = await self._request(
                "GET",
                endpoint,
                {"symbol": symbol.upper(), "limit": limit}
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
                symbol=symbol.upper(),
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
                Interval.H1: "1h", Interval.H2: "2h", Interval.H4: "4h",
                Interval.H6: "6h", Interval.H8: "8h", Interval.H12: "12h",
                Interval.D1: "1d", Interval.D3: "3d",
                Interval.W1: "1w", Interval.MN1: "1M",
            }
            
            endpoint = "/api/v3/klines"
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/klines"
            
            result = await self._request(
                "GET",
                endpoint,
                {
                    "symbol": symbol.upper(),
                    "interval": interval_map[interval],
                    "limit": limit,
                }
            )
            
            if not result:
                return []
            
            ohlcv_list = []
            for candle in result:
                ohlcv_list.append(OHLCV(
                    symbol=symbol.upper(),
                    interval=interval,
                    open=Decimal(candle[1]),
                    high=Decimal(candle[2]),
                    low=Decimal(candle[3]),
                    close=Decimal(candle[4]),
                    volume=Decimal(candle[5]),
                    timestamp=datetime.fromtimestamp(candle[0] / 1000),
                    close_time=datetime.fromtimestamp(candle[6] / 1000),
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
            Interval.H1: "1h", Interval.H4: "4h",
            Interval.D1: "1d", Interval.W1: "1w",
        }
        
        all_candles = []
        current_time = start_time
        limit = 1000
        
        while current_time < end_time:
            params = {
                "symbol": symbol.upper(),
                "interval": interval_map.get(interval, "1m"),
                "startTime": int(current_time.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000),
                "limit": limit,
            }
            
            result = await self._request("GET", "/api/v3/klines", params)
            if not result:
                break
            
            for candle in result:
                ohlcv_list.append(OHLCV(
                    symbol=symbol.upper(),
                    interval=interval,
                    open=Decimal(candle[1]),
                    high=Decimal(candle[2]),
                    low=Decimal(candle[3]),
                    close=Decimal(candle[4]),
                    volume=Decimal(candle[5]),
                    timestamp=datetime.fromtimestamp(candle[0] / 1000),
                    close_time=datetime.fromtimestamp(candle[6] / 1000),
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
            symbol = symbol.upper()
            
            # Determine endpoint
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/futures/order"
            else:
                endpoint = "/api/v3/order"
            
            # Build parameters
            params = {
                "symbol": symbol,
                "side": side.value.upper(),
                "type": order_type.value.upper(),
                "quantity": float(quantity),
            }
            
            if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if price is None:
                    raise ValueError("Price required for limit orders")
                params["price"] = float(price)
                params["timeInForce"] = time_in_force.value.upper()
            
            if order_type == OrderType.STOP_LIMIT:
                if stop_price is None:
                    raise ValueError("Stop price required for stop-limit orders")
                params["stopPrice"] = float(stop_price)
            
            if order_type == OrderType.STOP:
                if stop_price is None:
                    raise ValueError("Stop price required for stop orders")
                params["stopPrice"] = float(stop_price)
            
            if reduce_only:
                params["reduceOnly"] = "true"
            
            if post_only:
                params["postOnly"] = "true"
            
            if client_order_id:
                params["newClientOrderId"] = client_order_id
            
            # Place order
            result = await self._request("POST", endpoint, params, signed=True)
            
            if not result:
                return None
            
            order = Order(
                order_id=result.get("orderId", ""),
                exchange=self.exchange_type,
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=Decimal(result.get("price", 0)) if result.get("price") else None,
                quantity=Decimal(result.get("origQty", 0)),
                filled_quantity=Decimal(result.get("executedQty", 0)),
                remaining_quantity=Decimal(result.get("origQty", 0)) - Decimal(result.get("executedQty", 0)),
                status=self._parse_order_status(result.get("status", "")),
                created_at=datetime.utcnow(),
                client_order_id=result.get("clientOrderId"),
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
                endpoint = "/api/v3/futures/order"
            else:
                endpoint = "/api/v3/order"
            
            params = {
                "symbol": symbol.upper(),
                "orderId": order_id,
            }
            
            await self._request("DELETE", endpoint, params, signed=True)
            self.metrics["orders_cancelled"] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all orders for a symbol."""
        try:
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/futures/openOrders"
            else:
                endpoint = "/api/v3/openOrders"
            
            params = {"symbol": symbol.upper()}
            
            await self._request("DELETE", endpoint, params, signed=True)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel all orders for {symbol}: {e}")
            return False
    
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Get order status."""
        try:
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/futures/order"
            else:
                endpoint = "/api/v3/order"
            
            params = {
                "symbol": symbol.upper(),
                "orderId": order_id,
            }
            
            result = await self._request("GET", endpoint, params, signed=True)
            
            if not result:
                return None
            
            return Order(
                order_id=result.get("orderId", ""),
                exchange=self.exchange_type,
                symbol=result.get("symbol", ""),
                side=OrderSide(result.get("side", "").lower()),
                order_type=OrderType(result.get("type", "").lower()),
                price=Decimal(result.get("price", 0)) if result.get("price") else None,
                quantity=Decimal(result.get("origQty", 0)),
                filled_quantity=Decimal(result.get("executedQty", 0)),
                remaining_quantity=Decimal(result.get("origQty", 0)) - Decimal(result.get("executedQty", 0)),
                status=self._parse_order_status(result.get("status", "")),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                client_order_id=result.get("clientOrderId"),
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    async def get_open_orders(self, symbol: str) -> List[Order]:
        """Get open orders for a symbol."""
        try:
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/futures/openOrders"
            else:
                endpoint = "/api/v3/openOrders"
            
            params = {"symbol": symbol.upper()}
            
            result = await self._request("GET", endpoint, params, signed=True)
            
            if not result:
                return []
            
            orders = []
            for item in result:
                orders.append(Order(
                    order_id=item.get("orderId", ""),
                    exchange=self.exchange_type,
                    symbol=item.get("symbol", ""),
                    side=OrderSide(item.get("side", "").lower()),
                    order_type=OrderType(item.get("type", "").lower()),
                    price=Decimal(item.get("price", 0)) if item.get("price") else None,
                    quantity=Decimal(item.get("origQty", 0)),
                    filled_quantity=Decimal(item.get("executedQty", 0)),
                    remaining_quantity=Decimal(item.get("origQty", 0)) - Decimal(item.get("executedQty", 0)),
                    status=self._parse_order_status(item.get("status", "")),
                    created_at=datetime.utcnow(),
                    client_order_id=item.get("clientOrderId"),
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
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/futures/allOrders"
            else:
                endpoint = "/api/v3/allOrders"
            
            params = {
                "symbol": symbol.upper(),
                "limit": limit,
            }
            
            if start_time:
                params["startTime"] = int(start_time.timestamp() * 1000)
            if end_time:
                params["endTime"] = int(end_time.timestamp() * 1000)
            
            result = await self._request("GET", endpoint, params, signed=True)
            
            if not result:
                return []
            
            orders = []
            for item in result:
                orders.append(Order(
                    order_id=item.get("orderId", ""),
                    exchange=self.exchange_type,
                    symbol=item.get("symbol", ""),
                    side=OrderSide(item.get("side", "").lower()),
                    order_type=OrderType(item.get("type", "").lower()),
                    price=Decimal(item.get("price", 0)) if item.get("price") else None,
                    quantity=Decimal(item.get("origQty", 0)),
                    filled_quantity=Decimal(item.get("executedQty", 0)),
                    remaining_quantity=Decimal(item.get("origQty", 0)) - Decimal(item.get("executedQty", 0)),
                    status=self._parse_order_status(item.get("status", "")),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    client_order_id=item.get("clientOrderId"),
                ))
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Failed to get order history for {symbol}: {e}")
            return []
    
    # Account Management Methods
    
    async def get_balances(self) -> Dict[str, Balance]:
        """Get account balances."""
        try:
            endpoint = "/api/v3/account"
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/futures/account"
            
            result = await self._request("GET", endpoint, signed=True)
            
            if not result:
                return {}
            
            balances = {}
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                # Futures account
                for item in result.get("assets", []):
                    asset = item.get("asset", "")
                    balances[asset] = Balance(
                        asset=asset,
                        free=Decimal(item.get("free", 0)),
                        locked=Decimal(item.get("locked", 0)),
                        total=Decimal(item.get("balance", 0)),
                        timestamp=datetime.utcnow(),
                    )
            else:
                # Spot account
                for item in result.get("balances", []):
                    asset = item.get("asset", "")
                    balances[asset] = Balance(
                        asset=asset,
                        free=Decimal(item.get("free", 0)),
                        locked=Decimal(item.get("locked", 0)),
                        total=Decimal(item.get("free", 0)) + Decimal(item.get("locked", 0)),
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
            if self.market_type not in [MarketType.FUTURES, MarketType.PERPETUAL]:
                return []
            
            endpoint = "/api/v3/futures/position"
            
            result = await self._request("GET", endpoint, signed=True)
            
            if not result:
                return []
            
            positions = []
            for item in result:
                side = OrderSide.LONG if Decimal(item.get("positionAmt", 0)) > 0 else OrderSide.SHORT
                positions.append(Position(
                    symbol=item.get("symbol", ""),
                    side=side,
                    size=abs(Decimal(item.get("positionAmt", 0))),
                    entry_price=Decimal(item.get("entryPrice", 0)),
                    current_price=Decimal(item.get("markPrice", 0)),
                    mark_price=Decimal(item.get("markPrice", 0)),
                    liquidation_price=Decimal(item.get("liquidationPrice", 0)),
                    unrealized_pnl=Decimal(item.get("unRealizedProfit", 0)),
                    realized_pnl=Decimal(item.get("realizedProfit", 0)),
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
            endpoint = "/api/v3/exchangeInfo"
            if self.market_type in [MarketType.FUTURES, MarketType.PERPETUAL]:
                endpoint = "/api/v3/exchangeInfo"
            
            result = await self._request("GET", endpoint)
            
            if not result:
                return []
            
            symbols = []
            for item in result.get("symbols", []):
                symbol = item.get("symbol", "")
                if symbol and item.get("status") == "TRADING":
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
            
            endpoint = "/api/v3/futures/fundingRate"
            
            result = await self._request(
                "GET",
                endpoint,
                {"symbol": symbol.upper()}
            )
            
            if not result:
                return None
            
            return FundingRate(
                symbol=symbol.upper(),
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
            self._ws = MEXCWebSocket(self, self.ws_base)
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
        
        await self._ws.subscribe("user_data", [""], callback)
        return True
    
    # Utility Methods
    
    async def ping(self) -> bool:
        """Ping the exchange to check connectivity."""
        try:
            result = await self._request("GET", "/api/v3/ping")
            return result is not None
        except Exception:
            return False
    
    async def get_server_time(self) -> datetime:
        """Get server time."""
        try:
            result = await self._request("GET", "/api/v3/time")
            if result:
                return datetime.fromtimestamp(result / 1000)
        except Exception:
            pass
        return datetime.utcnow()
    
    def _parse_order_status(self, status: str) -> OrderStatus:
        """Parse order status string."""
        status_map = {
            "NEW": OrderStatus.OPEN,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
        }
        return status_map.get(status.upper(), OrderStatus.PENDING)

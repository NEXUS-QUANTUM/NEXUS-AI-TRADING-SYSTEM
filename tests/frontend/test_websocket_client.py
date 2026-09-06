"""
tests/frontend/test_websocket_client.py

NEXUS AI Trading System - Frontend WebSocket Client Tests (Python)

This test suite verifies the WebSocket client functionality used by the frontend
or by backend microservices that communicate via WebSockets.

Tests cover:
- Connection establishment and authentication
- Subscription to market data channels
- Receiving and parsing messages
- Automatic reconnection and backoff
- Error handling and logging
- Heartbeat/ping-pong mechanism
- Cleanup and resource management

Uses `websockets` library and `pytest-asyncio` with a mock server.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, AsyncMock, patch, call

import pytest
import websockets
from websockets.exceptions import ConnectionClosed

from nexus_websocket_client import NexusWebSocketClient, WsMessageType, WsMessage

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
WS_URL = "ws://localhost:8765/ws"
TEST_TOKEN = "test-jwt-token"
TEST_SYMBOL = "BTC/USD"
PING_INTERVAL = 0.1  # seconds
PONG_TIMEOUT = 0.2


@pytest.fixture
def mock_server():
    """Create a mock WebSocket server that can be controlled in tests."""
    # This is a simplified mock; we'll use a real server in a thread.
    # For simplicity, we'll use pytest-asyncio with websockets.serve.
    # We'll keep a reference to the server and the connected client.
    # We'll use a global event loop fixture.
    pass


@pytest.fixture
def client():
    """Create a client instance with default settings."""
    return NexusWebSocketClient(
        url=WS_URL,
        token=TEST_TOKEN,
        reconnect=True,
        reconnect_interval=0.1,
        max_reconnect_attempts=3,
        ping_interval=PING_INTERVAL,
        pong_timeout=PONG_TIMEOUT,
    )


@pytest.fixture
async def connected_client(client, mock_server):
    """Connect the client and ensure it is authenticated."""
    # This will need to start a mock server and connect.
    # We'll implement a fixture that starts a websockets server.
    pass


class TestWebSocketClient:
    """Test suite for NexusWebSocketClient."""

    @pytest.mark.asyncio
    async def test_connection_success(self, client):
        """Test successful connection and authentication."""
        # Start a mock server that accepts and echoes auth
        async def handler(websocket, path):
            # Wait for auth message
            msg = await websocket.recv()
            data = json.loads(msg)
            assert data["type"] == WsMessageType.AUTH
            assert data["token"] == TEST_TOKEN
            # Send auth success
            await websocket.send(json.dumps({
                "type": WsMessageType.AUTH_SUCCESS,
                "timestamp": time.time(),
                "data": {"userId": "123"}
            }))
            # Keep connection open
            await asyncio.Future()  # wait forever

        # Start server
        server = await websockets.serve(handler, "localhost", 8765)
        try:
            # Connect
            await client.connect()
            # Wait for connection and auth
            await asyncio.sleep(0.1)
            assert client.is_connected()
            assert client.ready_state == WebSocket.OPEN  # Assuming enum
        finally:
            server.close()
            await server.wait_closed()
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_auth_failure(self, client):
        """Test handling of authentication failure."""
        async def handler(websocket, path):
            msg = await websocket.recv()
            # Send error
            await websocket.send(json.dumps({
                "type": WsMessageType.ERROR,
                "code": "AUTH_FAILED",
                "message": "Invalid token"
            }))
            await websocket.close()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            # Spy on error callback
            error_callback = Mock()
            client.on_error(error_callback)

            await client.connect()
            await asyncio.sleep(0.1)

            error_callback.assert_called_once()
            # Check that client is disconnected or in error state
            assert not client.is_connected()
        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_subscribe_market_data(self, client):
        """Test sending subscribe message for market data."""
        received_messages = []

        async def handler(websocket, path):
            # Auth
            msg = await websocket.recv()
            await websocket.send(json.dumps({"type": WsMessageType.AUTH_SUCCESS}))
            # Wait for subscription
            msg = await websocket.recv()
            received_messages.append(json.loads(msg))
            # Keep open
            await asyncio.Future()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            await client.connect()
            await asyncio.sleep(0.1)

            # Subscribe
            await client.subscribe_market_data(TEST_SYMBOL)
            await asyncio.sleep(0.1)

            assert len(received_messages) == 2  # auth + subscribe
            sub_msg = received_messages[1]
            assert sub_msg["type"] == WsMessageType.SUBSCRIBE
            assert sub_msg["channel"] == "market_data"
            assert sub_msg["symbol"] == TEST_SYMBOL
        finally:
            server.close()
            await server.wait_closed()
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_receive_market_data(self, client):
        """Test receiving market data messages from server."""
        price = 50000.25
        volume = 123.45
        symbol = TEST_SYMBOL

        async def handler(websocket, path):
            # Auth
            await websocket.recv()
            await websocket.send(json.dumps({"type": WsMessageType.AUTH_SUCCESS}))
            # Send market data
            await websocket.send(json.dumps({
                "type": WsMessageType.MARKET_DATA,
                "timestamp": time.time(),
                "data": {
                    "symbol": symbol,
                    "price": price,
                    "volume": volume,
                    "timestamp": time.time()
                }
            }))
            await asyncio.Future()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            data_handler = Mock()
            client.on_market_data(data_handler)

            await client.connect()
            await asyncio.sleep(0.1)

            # Wait for message processing
            await asyncio.sleep(0.1)

            data_handler.assert_called_once()
            args = data_handler.call_args[0][0]
            assert args["symbol"] == symbol
            assert args["price"] == price
            assert args["volume"] == volume
        finally:
            server.close()
            await server.wait_closed()
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_unsubscribe(self, client):
        """Test sending unsubscribe message."""
        received_messages = []

        async def handler(websocket, path):
            # Auth
            await websocket.recv()
            await websocket.send(json.dumps({"type": WsMessageType.AUTH_SUCCESS}))
            # Subscribe
            msg = await websocket.recv()
            received_messages.append(json.loads(msg))
            # Unsubscribe
            msg = await websocket.recv()
            received_messages.append(json.loads(msg))
            await asyncio.Future()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            await client.connect()
            await asyncio.sleep(0.1)

            await client.subscribe_market_data(TEST_SYMBOL)
            await asyncio.sleep(0.05)
            await client.unsubscribe("market_data", TEST_SYMBOL)
            await asyncio.sleep(0.05)

            # Check last message is unsubscribe
            unsub_msg = received_messages[-1]
            assert unsub_msg["type"] == WsMessageType.UNSUBSCRIBE
            assert unsub_msg["channel"] == "market_data"
            assert unsub_msg["symbol"] == TEST_SYMBOL
        finally:
            server.close()
            await server.wait_closed()
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_ping_pong(self, client):
        """Test heartbeat ping/pong mechanism."""
        ping_received = False

        async def handler(websocket, path):
            nonlocal ping_received
            # Auth
            await websocket.recv()
            await websocket.send(json.dumps({"type": WsMessageType.AUTH_SUCCESS}))
            # Expect ping
            msg = await websocket.recv()
            data = json.loads(msg)
            if data.get("type") == WsMessageType.PING:
                ping_received = True
                await websocket.send(json.dumps({"type": WsMessageType.PONG, "timestamp": time.time()}))
            await asyncio.Future()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            # Set very short intervals
            client.ping_interval = 0.05
            client.pong_timeout = 0.2

            pong_handler = Mock()
            client.on_pong(pong_handler)

            await client.connect()
            await asyncio.sleep(0.2)

            assert ping_received, "Ping was not sent by client"
            pong_handler.assert_called()
        finally:
            server.close()
            await server.wait_closed()
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_reconnection(self, client):
        """Test automatic reconnection when connection drops."""
        connection_count = 0

        async def handler(websocket, path):
            nonlocal connection_count
            connection_count += 1
            # Auth
            await websocket.recv()
            await websocket.send(json.dumps({"type": WsMessageType.AUTH_SUCCESS}))
            # Close after a moment to simulate disconnection
            await asyncio.sleep(0.1)
            await websocket.close()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            # Set reconnect interval low
            client.reconnect_interval = 0.05
            client.max_reconnect_attempts = 3

            reconnect_callback = Mock()
            client.on_reconnect(reconnect_callback)

            await client.connect()
            # Wait for reconnections to happen
            await asyncio.sleep(0.5)

            # We should have had at least 2 connection attempts (initial + reconnect)
            assert connection_count >= 2
            # reconnect_callback should have been called
            reconnect_callback.assert_called()
        finally:
            server.close()
            await server.wait_closed()
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_max_reconnect_attempts(self, client):
        """Test that reconnection stops after max attempts."""
        async def handler(websocket, path):
            # Immediately close to force failure
            await websocket.close()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            client.reconnect_interval = 0.05
            client.max_reconnect_attempts = 2

            error_callback = Mock()
            client.on_error(error_callback)

            await client.connect()
            await asyncio.sleep(0.4)

            # Should have logged max attempts and fired error
            # We'll check that error_callback was called with MAX_RECONNECT
            error_callback.assert_called_with(
                {"code": "MAX_RECONNECT", "message": "Max reconnection attempts reached"}
            )
            # Client should be disconnected
            assert not client.is_connected()
        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_message_dispatch(self, client):
        """Test that messages are dispatched to correct handlers based on type."""
        async def handler(websocket, path):
            # Auth
            await websocket.recv()
            await websocket.send(json.dumps({"type": WsMessageType.AUTH_SUCCESS}))
            # Send various messages
            await websocket.send(json.dumps({"type": WsMessageType.MARKET_DATA, "data": {"price": 100}}))
            await websocket.send(json.dumps({"type": WsMessageType.ORDER_UPDATE, "data": {"orderId": "123"}}))
            await websocket.send(json.dumps({"type": WsMessageType.ERROR, "data": {"message": "Error"}}))
            await asyncio.Future()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            market_handler = Mock()
            order_handler = Mock()
            error_handler = Mock()
            client.on_market_data(market_handler)
            client.on_order_update(order_handler)
            client.on_error(error_handler)

            await client.connect()
            await asyncio.sleep(0.2)

            market_handler.assert_called_once()
            order_handler.assert_called_once()
            error_handler.assert_called_once()
        finally:
            server.close()
            await server.wait_closed()
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_malformed_json(self, client):
        """Test handling of malformed JSON messages."""
        async def handler(websocket, path):
            # Auth
            await websocket.recv()
            await websocket.send(json.dumps({"type": WsMessageType.AUTH_SUCCESS}))
            # Send invalid JSON
            await websocket.send("{invalid json")
            await asyncio.Future()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            error_handler = Mock()
            client.on_error(error_handler)

            await client.connect()
            await asyncio.sleep(0.1)

            # Should log error but not disconnect
            # Check that client is still connected
            assert client.is_connected()
            # error_handler might be called with parse error? Or just log.
            # We'll check that the client didn't crash.
        finally:
            server.close()
            await server.wait_closed()
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_clean_disconnect(self, client):
        """Test that disconnect closes connection cleanly."""
        async def handler(websocket, path):
            # Keep open
            await asyncio.Future()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            await client.connect()
            await asyncio.sleep(0.1)
            assert client.is_connected()

            await client.disconnect()
            await asyncio.sleep(0.1)
            assert not client.is_connected()
            # Check that the socket is closed
        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_manual_disconnect_prevents_reconnect(self, client):
        """Test that after manual disconnect, reconnect is not attempted."""
        async def handler(websocket, path):
            # Keep open
            await asyncio.Future()

        server = await websockets.serve(handler, "localhost", 8765)
        try:
            client.reconnect = True
            client.reconnect_interval = 0.05

            await client.connect()
            await asyncio.sleep(0.1)

            # Manually disconnect
            await client.disconnect()

            # Wait a bit to see if reconnection happens
            await asyncio.sleep(0.3)

            # Client should still be disconnected
            assert not client.is_connected()
            # There should be no connection attempts (no new server connections)
        finally:
            server.close()
            await server.wait_closed()


# Additional tests for specific edge cases
@pytest.mark.asyncio
async def test_multiple_subscriptions_unsubscriptions():
    """Test handling multiple subscribe/unsubscribe calls."""
    # Similar to the TypeScript version, but implemented in Python.
    pass


# If you want to run the tests with pytest, ensure you have pytest-asyncio installed.
# Use: pytest tests/frontend/test_websocket_client.py -v

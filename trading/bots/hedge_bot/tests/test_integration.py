# trading/bots/hedge_bot/tests/test_integration.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Integration Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Integration Tests

This module provides comprehensive integration tests for the NEXUS Hedge Bot
system. It tests the interaction between different components, the complete
workflow, and end-to-end functionality.

The test suite covers:
- Full system initialization
- Strategy execution with real components
- Risk management integration
- Trading execution flow
- Portfolio management workflow
- Data pipeline integration
- AI/ML integration
- WebSocket communication
- API endpoints
- Database operations
- Cache management
- Error handling and recovery
- Performance under load
- Security and compliance
"""

import os
import sys
import json
import time
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock

import pytest
import pytest_asyncio
import sqlite3
import redis

# Import module under test
from trading.bots.hedge_bot.main import HedgeBot
from trading.bots.hedge_bot.core.engine import HedgeEngine
from trading.bots.hedge_bot.strategies.delta_hedge import DeltaHedgingStrategy
from trading.bots.hedge_bot.strategies.gamma_hedge import GammaHedgingStrategy
from trading.bots.hedge_bot.strategies.cross_hedge import CrossHedgingStrategy
from trading.bots.hedge_bot.risk.risk_manager import RiskManager
from trading.bots.hedge_bot.execution.execution_engine import ExecutionEngine
from trading.bots.hedge_bot.portfolio.portfolio_manager import PortfolioManager
from trading.bots.hedge_bot.data.market_data import MarketDataProvider
from trading.bots.hedge_bot.ai.predictor import MarketPredictor
from trading.bots.hedge_bot.websocket.manager import WebSocketManager
from trading.bots.hedge_bot.api.main import app
from trading.bots.hedge_bot.database.manager import DatabaseManager
from trading.bots.hedge_bot.cache.manager import CacheManager

# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def test_db_path() -> Path:
    """Get test database path"""
    return Path(__file__).parent / "test_integration.db"


@pytest.fixture(scope="session")
def test_config_path() -> Path:
    """Get test config path"""
    return Path(__file__).parent / "fixtures" / "config_test.yaml"


@pytest.fixture
def test_config(test_config_path: Path) -> Dict[str, Any]:
    """Load test configuration"""
    import yaml
    with open(test_config_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def test_db(test_db_path: Path) -> sqlite3.Connection:
    """Create test database"""
    # Remove existing database
    if test_db_path.exists():
        test_db_path.unlink()
    
    # Create database
    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            symbol TEXT,
            side TEXT,
            quantity REAL,
            price REAL,
            status TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            side TEXT,
            quantity REAL,
            entry_price REAL,
            current_price REAL,
            unrealized_pnl REAL,
            status TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            currency TEXT,
            balance REAL,
            total_value REAL,
            total_pnl REAL,
            updated_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    yield conn
    
    # Cleanup
    conn.close()
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def test_redis() -> redis.Redis:
    """Create test Redis connection"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=15, decode_responses=True)
        r.ping()
        r.flushdb()  # Clear test database
        return r
    except redis.ConnectionError:
        # Skip Redis tests if not available
        return None


@pytest.fixture
def hedge_bot(test_config: Dict[str, Any], test_db_path: Path) -> HedgeBot:
    """Create hedge bot instance with test config"""
    # Update config with test database
    test_config["database"] = {
        "path": str(test_db_path),
        "type": "sqlite"
    }
    return HedgeBot(test_config)


@pytest.fixture
async def running_hedge_bot(hedge_bot: HedgeBot) -> HedgeBot:
    """Create and start hedge bot"""
    await hedge_bot.start_async()
    yield hedge_bot
    await hedge_bot.stop_async()


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestFullSystemIntegration:
    """
    Full system integration tests
    """

    @pytest.mark.asyncio
    async def test_system_initialization(self, hedge_bot: HedgeBot) -> None:
        """Test full system initialization"""
        # Initialize all components
        await hedge_bot.initialize_async()
        
        # Verify all components are initialized
        assert hedge_bot.engine is not None
        assert hedge_bot.strategy_manager is not None
        assert hedge_bot.risk_manager is not None
        assert hedge_bot.execution_engine is not None
        assert hedge_bot.portfolio_manager is not None
        assert hedge_bot.market_data is not None
        assert hedge_bot.ai_predictor is not None
        assert hedge_bot.database_manager is not None
        assert hedge_bot.cache_manager is not None
        assert hedge_bot.websocket_manager is not None
        
        # Verify components are connected
        assert hedge_bot.engine.is_initialized is True
        assert hedge_bot.market_data.is_initialized is True
        assert hedge_bot.database_manager.is_connected is True

    @pytest.mark.asyncio
    async def test_full_trading_workflow(self, running_hedge_bot: HedgeBot) -> None:
        """Test complete trading workflow"""
        bot = running_hedge_bot
        
        # 1. Get market data
        market_data = await bot.market_data.get_price_async("BTC/USDT")
        assert market_data is not None
        
        # 2. Generate signal
        signal = await bot.strategy_manager.generate_signal_async("BTC/USDT")
        assert signal is not None
        
        # 3. Check risk
        risk_check = await bot.risk_manager.check_limits_async()
        assert risk_check["status"] in ["healthy", "warning"]
        
        # 4. Execute trade
        if signal["action"] != "hold":
            order = await bot.execution_engine.place_order_async({
                "symbol": "BTC/USDT",
                "side": signal["action"],
                "quantity": signal["quantity"],
                "price": signal["price"],
            })
            assert order is not None
            
            # 5. Update portfolio
            await bot.portfolio_manager.update_async(order)
        
        # 6. Verify database
        trades = await bot.database_manager.get_trades_async()
        assert trades is not None

    @pytest.mark.asyncio
    async def test_strategy_with_risk_integration(self, running_hedge_bot: HedgeBot) -> None:
        """Test strategy integration with risk management"""
        bot = running_hedge_bot
        
        # Create strategy
        strategy = DeltaHedgingStrategy({
            "hedge_ratio": 0.50,
            "target_delta": 0.0,
            "delta_tolerance": 0.01,
        })
        await strategy.initialize_async(bot)
        
        # Get market data
        price = await bot.market_data.get_price_async("BTC/USDT")
        
        # Calculate hedge
        hedge_ratio = await strategy.calculate_hedge_ratio_async({
            "symbol": "BTC/USDT",
            "quantity": 1.0,
            "price": price,
        })
        
        # Check risk
        risk_metrics = await bot.risk_manager.calculate_metrics_async()
        assert risk_metrics["var_95"] is not None
        
        # Execute hedge if within limits
        if risk_metrics["risk_score"] < 0.5:
            result = await strategy.execute_hedge_async({
                "hedge_ratio": hedge_ratio,
                "symbol": "BTC/USDT",
            })
            assert result is not None

    @pytest.mark.asyncio
    async def test_multi_strategy_execution(self, running_hedge_bot: HedgeBot) -> None:
        """Test multiple strategies execution"""
        bot = running_hedge_bot
        
        # Create multiple strategies
        strategies = [
            DeltaHedgingStrategy({"hedge_ratio": 0.50}),
            GammaHedgingStrategy({"gamma_threshold": 0.0001}),
            CrossHedgingStrategy({"correlation_threshold": 0.70}),
        ]
        
        # Initialize and execute each strategy
        for strategy in strategies:
            await strategy.initialize_async(bot)
            
            # Get signal
            signal = await strategy.generate_signal_async()
            
            # Check risk before execution
            risk_check = await bot.risk_manager.check_limits_async()
            if risk_check["status"] == "healthy":
                # Execute strategy
                result = await strategy.execute_async()
                assert result is not None
            
            # Stop strategy
            await strategy.stop_async()

    @pytest.mark.asyncio
    async def test_data_pipeline_integration(self, running_hedge_bot: HedgeBot) -> None:
        """Test data pipeline integration"""
        bot = running_hedge_bot
        
        # 1. Get real-time data
        realtime_data = await bot.market_data.get_realtime_async(["BTC/USDT", "ETH/USDT"])
        assert len(realtime_data) > 0
        
        # 2. Get historical data
        historical_data = await bot.market_data.get_historical_async("BTC/USDT", days=30)
        assert len(historical_data) > 0
        
        # 3. Calculate indicators
        indicators = await bot.market_data.calculate_indicators_async(historical_data)
        assert "rsi" in indicators
        assert "macd" in indicators
        assert "bollinger_bands" in indicators
        
        # 4. Update cache
        await bot.cache_manager.set_async("BTC/USDT/price", realtime_data[0]["price"])
        cached_price = await bot.cache_manager.get_async("BTC/USDT/price")
        assert cached_price is not None

    @pytest.mark.asyncio
    async def test_ai_integration(self, running_hedge_bot: HedgeBot) -> None:
        """Test AI/ML integration"""
        bot = running_hedge_bot
        
        # 1. Get prediction
        prediction = await bot.ai_predictor.predict_async("BTC/USDT")
        assert prediction["direction"] in ["up", "down", "neutral"]
        assert 0 <= prediction["confidence"] <= 1
        
        # 2. Train model
        training_data = await bot.market_data.get_training_data_async()
        await bot.ai_predictor.train_async(training_data)
        
        # 3. Get ensemble prediction
        ensemble_prediction = await bot.ai_predictor.predict_ensemble_async("BTC/USDT")
        assert ensemble_prediction["price"] is not None
        assert ensemble_prediction["volatility"] is not None
        
        # 4. Update model
        await bot.ai_predictor.update_model_async()

    @pytest.mark.asyncio
    async def test_database_integration(self, running_hedge_bot: HedgeBot, test_db: sqlite3.Connection) -> None:
        """Test database integration"""
        bot = running_hedge_bot
        
        # 1. Insert trade
        trade = {
            "order_id": "ord_test_001",
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 1.0,
            "price": 50000.0,
            "status": "filled",
        }
        await bot.database_manager.insert_trade_async(trade)
        
        # 2. Insert position
        position = {
            "symbol": "BTC/USDT",
            "side": "long",
            "quantity": 1.0,
            "entry_price": 50000.0,
            "current_price": 52000.0,
            "unrealized_pnl": 2000.0,
            "status": "open",
        }
        await bot.database_manager.insert_position_async(position)
        
        # 3. Query trades
        trades = await bot.database_manager.get_trades_async(limit=10)
        assert len(trades) > 0
        assert trades[0]["order_id"] == "ord_test_001"
        
        # 4. Query positions
        positions = await bot.database_manager.get_positions_async(status="open")
        assert len(positions) > 0
        assert positions[0]["symbol"] == "BTC/USDT"
        
        # 5. Update position
        await bot.database_manager.update_position_async(
            position_id=positions[0]["id"],
            updates={"current_price": 53000.0, "unrealized_pnl": 3000.0}
        )

    @pytest.mark.asyncio
    async def test_cache_integration(self, running_hedge_bot: HedgeBot, test_redis: redis.Redis) -> None:
        """Test cache integration"""
        if test_redis is None:
            pytest.skip("Redis not available")
        
        bot = running_hedge_bot
        
        # 1. Set cache
        await bot.cache_manager.set_async("test_key", "test_value", ttl=60)
        
        # 2. Get cache
        value = await bot.cache_manager.get_async("test_key")
        assert value == "test_value"
        
        # 3. Set complex data
        complex_data = {"key1": "value1", "key2": 123, "key3": [1, 2, 3]}
        await bot.cache_manager.set_async("complex_key", complex_data)
        
        # 4. Get complex data
        retrieved = await bot.cache_manager.get_async("complex_key")
        assert retrieved["key1"] == "value1"
        assert retrieved["key2"] == 123
        assert retrieved["key3"] == [1, 2, 3]
        
        # 5. Delete cache
        await bot.cache_manager.delete_async("test_key")
        value = await bot.cache_manager.get_async("test_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_websocket_integration(self, running_hedge_bot: HedgeBot) -> None:
        """Test WebSocket integration"""
        bot = running_hedge_bot
        
        # 1. Connect WebSocket
        await bot.websocket_manager.connect_async()
        assert bot.websocket_manager.is_connected is True
        
        # 2. Subscribe to channel
        await bot.websocket_manager.subscribe_async("market_data")
        subscriptions = bot.websocket_manager.get_subscriptions()
        assert "market_data" in subscriptions
        
        # 3. Send message
        message = {"type": "ping", "data": "test"}
        await bot.websocket_manager.send_message_async(message)
        
        # 4. Receive message
        received = await bot.websocket_manager.receive_message_async(timeout=1)
        if received:
            assert received is not None
        
        # 5. Unsubscribe
        await bot.websocket_manager.unsubscribe_async("market_data")
        subscriptions = bot.websocket_manager.get_subscriptions()
        assert "market_data" not in subscriptions
        
        # 6. Disconnect
        await bot.websocket_manager.disconnect_async()
        assert bot.websocket_manager.is_connected is False

    @pytest.mark.asyncio
    async def test_api_integration(self, running_hedge_bot: HedgeBot) -> None:
        """Test API integration"""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # 1. Health check
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        
        # 2. Get portfolio
        response = client.get("/portfolio/summary")
        assert response.status_code == 200
        assert "total_value" in response.json()
        
        # 3. Get positions
        response = client.get("/trading/positions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        
        # 4. Place order
        order = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 1.0,
            "price": 50000.0,
        }
        response = client.post("/trading/orders", json=order)
        assert response.status_code == 200
        assert "order_id" in response.json()
        
        # 5. Get strategy status
        response = client.get("/strategy/status")
        assert response.status_code == 200
        assert "status" in response.json()

    @pytest.mark.asyncio
    async def test_error_recovery_integration(self, running_hedge_bot: HedgeBot) -> None:
        """Test error recovery integration"""
        bot = running_hedge_bot
        
        # 1. Simulate exchange error
        with patch.object(bot.market_data, '_fetch_price_async', side_effect=Exception("Exchange error")):
            try:
                await bot.market_data.get_price_async("BTC/USDT")
            except Exception:
                pass
            
            # Verify error handling
            assert bot.market_data.error_count > 0
            assert bot.market_data.last_error is not None
        
        # 2. Test recovery
        await bot.market_data.recover_async()
        assert bot.market_data.is_healthy is True
        
        # 3. Verify component still works
        price = await bot.market_data.get_price_async("BTC/USDT", use_cache=True)
        assert price is not None

    @pytest.mark.asyncio
    async def test_high_load_integration(self, running_hedge_bot: HedgeBot) -> None:
        """Test system under high load"""
        bot = running_hedge_bot
        
        # 1. Execute multiple operations concurrently
        tasks = []
        for i in range(50):
            tasks.append(bot.market_data.get_price_async("BTC/USDT"))
            tasks.append(bot.market_data.get_price_async("ETH/USDT"))
            tasks.append(bot.market_data.get_price_async("SOL/USDT"))
        
        # 2. Run tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. Verify results
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        assert success_count > 100  # Most operations should succeed
        
        # 4. Check system health
        health = await bot.health_check_async()
        assert health["status"] == "healthy"
        assert health["components"]["database"]["status"] == "healthy"
        assert health["components"]["cache"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_security_integration(self, running_hedge_bot: HedgeBot) -> None:
        """Test security and compliance integration"""
        bot = running_hedge_bot
        
        # 1. Authentication
        token = await bot.security_manager.authenticate_async("test_user", "test_password")
        assert token is not None
        
        # 2. Authorization
        is_authorized = await bot.security_manager.authorize_async(
            user="test_user",
            action="trade",
            resource="BTC/USDT"
        )
        assert is_authorized is True
        
        # 3. Rate limiting
        for i in range(10):
            await bot.rate_limiter.check_async("test_user")
        
        # 4. Audit log
        await bot.audit_logger.log_async({
            "user": "test_user",
            "action": "trade",
            "details": {"symbol": "BTC/USDT", "quantity": 1.0},
        })
        
        # 5. Compliance check
        compliance = await bot.compliance_manager.check_async()
        assert compliance["status"] == "compliant"


# ============================================================
# END-TO-END TESTS
# ============================================================

class TestEndToEnd:
    """
    End-to-end test scenarios
    """

    @pytest.mark.asyncio
    async def test_complete_trading_scenario(self, running_hedge_bot: HedgeBot) -> None:
        """Test complete trading scenario"""
        bot = running_hedge_bot
        
        # 1. Market analysis
        analysis = await bot.analyze_market_async("BTC/USDT")
        assert analysis["trend"] in ["bullish", "bearish", "neutral"]
        assert "signals" in analysis
        
        # 2. Generate trading plan
        plan = await bot.generate_trading_plan_async(analysis)
        assert plan["strategy"] is not None
        assert plan["entry_price"] is not None
        assert plan["stop_loss"] is not None
        assert plan["take_profit"] is not None
        
        # 3. Execute plan
        execution = await bot.execute_plan_async(plan)
        assert execution["orders"] is not None
        assert execution["status"] in ["success", "partial", "failed"]
        
        # 4. Monitor positions
        positions = await bot.monitor_positions_async()
        assert positions is not None
        
        # 5. Risk management
        risk = await bot.monitor_risk_async()
        assert risk["var_95"] is not None
        assert risk["drawdown"] is not None
        
        # 6. Performance report
        report = await bot.generate_performance_report_async()
        assert report["pnl"] is not None
        assert report["win_rate"] is not None
        assert report["sharpe_ratio"] is not None

    @pytest.mark.asyncio
    async def test_hedging_scenario(self, running_hedge_bot: HedgeBot) -> None:
        """Test hedging scenario"""
        bot = running_hedge_bot
        
        # 1. Identify hedging need
        exposure = await bot.calculate_exposure_async()
        assert exposure["total"] is not None
        assert exposure["net"] is not None
        
        # 2. Select hedging strategy
        hedge_strategy = await bot.select_hedge_strategy_async(exposure)
        assert hedge_strategy["type"] in ["delta", "gamma", "cross", "basis"]
        
        # 3. Execute hedge
        hedge_execution = await bot.execute_hedge_async(hedge_strategy)
        assert hedge_execution["status"] == "success"
        
        # 4. Verify hedge effectiveness
        effectiveness = await bot.calculate_hedge_effectiveness_async()
        assert effectiveness["ratio"] >= 0.0
        assert effectiveness["effectiveness"] >= 0.0
        
        # 5. Monitor and adjust
        for i in range(5):
            await asyncio.sleep(1)
            adjustment = await bot.adjust_hedge_async()
            if adjustment["action"] != "none":
                assert adjustment["status"] == "success"

    @pytest.mark.asyncio
    async def test_market_making_scenario(self, running_hedge_bot: HedgeBot) -> None:
        """Test market making scenario"""
        bot = running_hedge_bot
        
        # 1. Analyze market making opportunity
        opportunity = await bot.analyze_market_making_async("BTC/USDT")
        assert opportunity["spread"] is not None
        assert opportunity["volume"] is not None
        assert opportunity["profit_potential"] is not None
        
        # 2. Place market making orders
        orders = await bot.place_market_making_orders_async(opportunity)
        assert len(orders) > 0
        
        # 3. Monitor order book
        order_book = await bot.monitor_order_book_async("BTC/USDT")
        assert order_book["bids"] is not None
        assert order_book["asks"] is not None
        
        # 4. Adjust orders
        adjustments = await bot.adjust_market_making_orders_async(order_book)
        assert adjustments["updated"] is not None


# ============================================================
# PERFORMANCE AND STRESS TESTS
# ============================================================

class TestPerformanceAndStress:
    """
    Performance and stress tests
    """

    @pytest.mark.asyncio
    async def test_system_performance(self, running_hedge_bot: HedgeBot) -> None:
        """Test system performance under load"""
        bot = running_hedge_bot
        
        # Measure performance
        start_time = time.time()
        
        # Execute 100 trades
        trades_executed = 0
        for i in range(100):
            try:
                order = {
                    "symbol": "BTC/USDT",
                    "side": "buy" if i % 2 == 0 else "sell",
                    "quantity": 0.01,
                    "price": 50000.0 + i * 10,
                }
                result = await bot.execution_engine.place_order_async(order)
                if result:
                    trades_executed += 1
            except Exception:
                pass
        
        duration = time.time() - start_time
        tps = trades_executed / duration
        
        # Verify performance
        assert tps > 0.5, f"Too slow: {tps:.2f} trades/sec"
        assert trades_executed > 50, "Too many failures"

    @pytest.mark.asyncio
    async def test_memory_usage(self, running_hedge_bot: HedgeBot) -> None:
        """Test memory usage"""
        import psutil
        
        bot = running_hedge_bot
        process = psutil.Process()
        
        # Record initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Perform operations that allocate memory
        for i in range(1000):
            await bot.market_data.get_price_async("BTC/USDT")
            await bot.cache_manager.set_async(f"key_{i}", f"value_{i}")
        
        # Record final memory
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # Verify memory usage
        assert memory_increase < 50, f"Memory leak: {memory_increase:.2f}MB"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, running_hedge_bot: HedgeBot) -> None:
        """Test concurrent operations"""
        bot = running_hedge_bot
        
        # Create many concurrent tasks
        tasks = []
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOT/USDT"]
        
        for _ in range(100):
            symbol = symbols[random.randint(0, 4)]
            tasks.append(bot.market_data.get_price_async(symbol))
            tasks.append(bot.risk_manager.calculate_metrics_async())
            tasks.append(bot.portfolio_manager.get_total_value_async())
        
        # Run all tasks
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.time() - start_time
        
        # Verify results
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        assert success_count > 200, "Too many failures"
        assert duration < 10, f"Too slow: {duration:.2f}s"


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "TestFullSystemIntegration",
    "TestEndToEnd",
    "TestPerformanceAndStress",
]

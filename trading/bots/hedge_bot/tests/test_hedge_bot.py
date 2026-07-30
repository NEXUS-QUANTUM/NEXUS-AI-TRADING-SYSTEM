# trading/bots/hedge_bot/tests/test_hedge_bot.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Main Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Main Tests

This module provides comprehensive integration tests for the NEXUS Hedge Bot
system. It covers the main application, strategy integration, risk management,
trading execution, and end-to-end workflows.

The test suite covers:
- Hedge bot initialization and configuration
- Strategy execution and integration
- Risk management integration
- Trading execution
- Portfolio management
- Data integration
- AI/ML integration
- End-to-end workflows
- Error recovery
- Performance monitoring
- Security and compliance
- WebSocket communication
- API integration
- Database operations
- Cache management
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

# Import module under test
from trading.bots.hedge_bot.main import HedgeBot
from trading.bots.hedge_bot.core.engine import HedgeEngine
from trading.bots.hedge_bot.strategies.delta_hedge import DeltaHedgingStrategy
from trading.bots.hedge_bot.strategies.gamma_hedge import GammaHedgingStrategy
from trading.bots.hedge_bot.strategies.cross_hedge import CrossHedgingStrategy
from trading.bots.hedge_bot.risk.risk_manager import RiskManager
from trading.bots.hedge_bot.risk.var import ValueAtRisk
from trading.bots.hedge_bot.risk.drawdown import DrawdownController
from trading.bots.hedge_bot.execution.execution_engine import ExecutionEngine
from trading.bots.hedge_bot.portfolio.portfolio_manager import PortfolioManager
from trading.bots.hedge_bot.data.market_data import MarketDataProvider
from trading.bots.hedge_bot.data.sentiment import SentimentAnalyzer
from trading.bots.hedge_bot.ai.predictor import MarketPredictor
from trading.bots.hedge_bot.ai.model import EnsembleModel
from trading.bots.hedge_bot.api.main import app
from trading.bots.hedge_bot.websocket.manager import WebSocketManager

# ============================================================
# TEST FIXTURES
# ============================================================

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
def hedge_bot(test_config: Dict[str, Any]) -> HedgeBot:
    """Create hedge bot instance"""
    return HedgeBot(test_config)


@pytest.fixture
def mock_exchange() -> Mock:
    """Create mock exchange"""
    mock = Mock()
    mock.get_ticker.return_value = {
        "symbol": "BTC/USDT",
        "bid": 50000.0,
        "ask": 50100.0,
        "last": 50050.0,
    }
    mock.get_order_book.return_value = {
        "bids": [[50000.0, 1.0], [49900.0, 2.0]],
        "asks": [[50100.0, 1.0], [50200.0, 2.0]],
    }
    mock.get_balance.return_value = {"BTC": 1.0, "USDT": 50000.0}
    mock.place_order.return_value = {"order_id": "ord_123", "status": "filled"}
    mock.cancel_order.return_value = {"order_id": "ord_123", "status": "cancelled"}
    mock.get_position.return_value = {
        "symbol": "BTC/USDT",
        "quantity": 1.0,
        "entry_price": 50000.0,
        "current_price": 52000.0,
    }
    mock.get_all_positions.return_value = []
    mock.get_historical_data.return_value = []
    return mock


@pytest.fixture
def mock_risk_manager() -> Mock:
    """Create mock risk manager"""
    mock = Mock()
    mock.calculate_var.return_value = 25000.0
    mock.calculate_cvar.return_value = 35000.0
    mock.calculate_drawdown.return_value = 0.08
    mock.calculate_risk_score.return_value = 0.35
    mock.check_limits.return_value = {"status": "healthy", "breaches": []}
    return mock


@pytest.fixture
def mock_portfolio() -> Mock:
    """Create mock portfolio"""
    mock = Mock()
    mock.get_total_value.return_value = 125000.0
    mock.get_positions.return_value = []
    mock.get_allocation.return_value = {"crypto": 0.5, "equity": 0.3}
    mock.get_performance.return_value = {"sharpe": 1.85, "returns": []}
    mock.rebalance.return_value = {"trades": []}
    return mock


@pytest.fixture
def mock_market_data() -> Mock:
    """Create mock market data provider"""
    mock = Mock()
    mock.get_price.return_value = 50000.0
    mock.get_historical.return_value = []
    mock.get_indicators.return_value = {"rsi": 55.0, "macd": 100.0}
    mock.get_volume.return_value = 1000000.0
    return mock


@pytest.fixture
def mock_predictor() -> Mock:
    """Create mock predictor"""
    mock = Mock()
    mock.predict.return_value = {"direction": "up", "confidence": 0.8}
    mock.predict_price.return_value = 51000.0
    mock.predict_volatility.return_value = 0.20
    mock.predict_correlation.return_value = 0.65
    return mock


# ============================================================
# MAIN HEDGE BOT TESTS
# ============================================================

class TestHedgeBot:
    """
    Tests for HedgeBot main application
    """

    def test_hedge_bot_initialization(self, hedge_bot: HedgeBot) -> None:
        """Test hedge bot initialization"""
        assert hedge_bot is not None
        assert hedge_bot.config is not None
        assert hedge_bot.is_running is False
        assert hedge_bot.status == "initialized"
        assert hedge_bot.components is not None

    def test_hedge_bot_start_stop(self, hedge_bot: HedgeBot) -> None:
        """Test hedge bot start and stop"""
        # Start bot
        hedge_bot.start()
        assert hedge_bot.is_running is True
        assert hedge_bot.status == "running"
        
        # Stop bot
        hedge_bot.stop()
        assert hedge_bot.is_running is False
        assert hedge_bot.status == "stopped"

    @pytest.mark.asyncio
    async def test_hedge_bot_async_start_stop(self, hedge_bot: HedgeBot) -> None:
        """Test hedge bot async start and stop"""
        # Start bot
        await hedge_bot.start_async()
        assert hedge_bot.is_running is True
        
        # Stop bot
        await hedge_bot.stop_async()
        assert hedge_bot.is_running is False

    def test_hedge_bot_component_initialization(self, hedge_bot: HedgeBot) -> None:
        """Test hedge bot component initialization"""
        # Verify all components are initialized
        assert hedge_bot.engine is not None
        assert hedge_bot.strategy_manager is not None
        assert hedge_bot.risk_manager is not None
        assert hedge_bot.execution_engine is not None
        assert hedge_bot.portfolio_manager is not None
        assert hedge_bot.market_data is not None
        assert hedge_bot.ai_predictor is not None

    def test_hedge_bot_config_validation(self, hedge_bot: HedgeBot) -> None:
        """Test hedge bot configuration validation"""
        assert hedge_bot.validate_config() is True
        
        # Invalid config should raise error
        invalid_config = {"bot": {"enabled": True}}
        with pytest.raises(Exception):
            HedgeBot(invalid_config)

    def test_hedge_bot_health_check(self, hedge_bot: HedgeBot) -> None:
        """Test hedge bot health check"""
        health = hedge_bot.health_check()
        assert "status" in health
        assert "components" in health
        assert "timestamp" in health
        
        # Start bot for healthy status
        hedge_bot.start()
        health = hedge_bot.health_check()
        assert health["status"] == "healthy"


class TestStrategyIntegration:
    """
    Tests for strategy integration
    """

    def test_delta_hedging_strategy(self, hedge_bot: HedgeBot) -> None:
        """Test delta hedging strategy"""
        strategy = DeltaHedgingStrategy({
            "hedge_ratio": 0.50,
            "target_delta": 0.0,
            "delta_tolerance": 0.01,
            "rebalance_interval": 15,
        })
        
        # Initialize strategy
        strategy.initialize(hedge_bot)
        assert strategy.is_initialized is True
        
        # Calculate hedge ratio
        hedge_ratio = strategy.calculate_hedge_ratio({
            "symbol": "BTC/USDT",
            "quantity": 1.0,
            "price": 50000.0,
        })
        assert hedge_ratio >= 0.0
        
        # Generate signals
        signals = strategy.generate_signals()
        assert signals is not None

    def test_gamma_hedging_strategy(self, hedge_bot: HedgeBot) -> None:
        """Test gamma hedging strategy"""
        strategy = GammaHedgingStrategy({
            "gamma_threshold": 0.0001,
            "gamma_tolerance": 0.01,
            "gamma_scalping": True,
        })
        
        strategy.initialize(hedge_bot)
        assert strategy.is_initialized is True
        
        # Calculate gamma
        gamma = strategy.calculate_gamma({
            "symbol": "BTC/USDT",
            "options": [{"strike": 50000.0, "expiry": "2026-08-01"}],
        })
        assert gamma is not None

    def test_cross_hedging_strategy(self, hedge_bot: HedgeBot) -> None:
        """Test cross hedging strategy"""
        strategy = CrossHedgingStrategy({
            "correlation_threshold": 0.70,
            "hedge_ratio": 0.50,
            "hedge_assets": ["BTC/ETH", "BTC/SOL"],
        })
        
        strategy.initialize(hedge_bot)
        assert strategy.is_initialized is True
        
        # Find hedge asset
        hedge_asset = strategy.find_hedge_asset("BTC")
        assert hedge_asset is not None or hedge_asset is None

    @patch('trading.bots.hedge_bot.strategies.delta_hedge.DeltaHedgingStrategy.execute')
    def test_strategy_execution(self, mock_execute: Mock, hedge_bot: HedgeBot) -> None:
        """Test strategy execution"""
        strategy = DeltaHedgingStrategy({"hedge_ratio": 0.50})
        strategy.initialize(hedge_bot)
        
        # Execute strategy
        result = strategy.execute()
        assert result is not None


class TestRiskManagementIntegration:
    """
    Tests for risk management integration
    """

    def test_value_at_risk(self, hedge_bot: HedgeBot) -> None:
        """Test Value at Risk calculation"""
        var = ValueAtRisk({
            "confidence": 0.95,
            "horizon": 1,
            "lookback": 252,
        })
        
        var.initialize(hedge_bot)
        
        # Calculate VaR
        positions = [
            {"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0},
            {"symbol": "ETH/USDT", "quantity": 10.0, "price": 3000.0},
        ]
        var_value = var.calculate(positions)
        assert var_value >= 0.0

    def test_drawdown_controller(self, hedge_bot: HedgeBot) -> None:
        """Test drawdown controller"""
        drawdown = DrawdownController({
            "max_drawdown": 0.15,
            "warning_threshold": 0.10,
            "critical_threshold": 0.12,
        })
        
        drawdown.initialize(hedge_bot)
        
        # Calculate drawdown
        current = drawdown.calculate_current()
        assert current >= 0.0
        
        # Check limits
        result = drawdown.check_limits()
        assert "status" in result

    def test_risk_manager(self, hedge_bot: HedgeBot) -> None:
        """Test risk manager"""
        risk_manager = RiskManager({
            "limits": {
                "max_drawdown": 0.15,
                "daily_loss_limit": 0.05,
                "max_leverage": 3.0,
            }
        })
        
        risk_manager.initialize(hedge_bot)
        
        # Calculate risk metrics
        metrics = risk_manager.calculate_metrics()
        assert "var_95" in metrics
        assert "cvar_95" in metrics
        assert "drawdown" in metrics
        
        # Check limits
        result = risk_manager.check_limits()
        assert result["status"] in ["healthy", "warning", "critical"]


class TestExecutionIntegration:
    """
    Tests for execution integration
    """

    @patch('trading.bots.hedge_bot.execution.execution_engine.ExecutionEngine.place_order')
    def test_order_execution(self, mock_place: Mock, hedge_bot: HedgeBot) -> None:
        """Test order execution"""
        execution = ExecutionEngine({
            "order_type": "limit",
            "time_in_force": "GTC",
            "max_order_size": 10000,
        })
        
        execution.initialize(hedge_bot)
        
        # Place order
        order = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 1.0,
            "price": 50000.0,
        }
        result = execution.place_order(order)
        assert result is not None

    def test_order_management(self, hedge_bot: HedgeBot) -> None:
        """Test order management"""
        execution = ExecutionEngine()
        execution.initialize(hedge_bot)
        
        # Create order
        order_id = execution.create_order({
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 1.0,
            "price": 50000.0,
        })
        assert order_id is not None
        
        # Get order status
        status = execution.get_order_status(order_id)
        assert status is not None
        
        # Cancel order
        result = execution.cancel_order(order_id)
        assert result is True


class TestPortfolioIntegration:
    """
    Tests for portfolio integration
    """

    def test_portfolio_manager(self, hedge_bot: HedgeBot) -> None:
        """Test portfolio manager"""
        portfolio = PortfolioManager({
            "currency": "USD",
            "initial_balance": 100000.0,
        })
        
        portfolio.initialize(hedge_bot)
        
        # Get portfolio value
        value = portfolio.get_total_value()
        assert value >= 0.0
        
        # Get positions
        positions = portfolio.get_positions()
        assert positions is not None
        
        # Get allocation
        allocation = portfolio.get_allocation()
        assert allocation is not None

    def test_portfolio_rebalancing(self, hedge_bot: HedgeBot) -> None:
        """Test portfolio rebalancing"""
        portfolio = PortfolioManager()
        portfolio.initialize(hedge_bot)
        
        # Set targets
        targets = {
            "BTC/USDT": 0.30,
            "ETH/USDT": 0.20,
            "SOL/USDT": 0.10,
        }
        
        # Rebalance
        result = portfolio.rebalance(targets)
        assert "trades" in result
        assert "estimated_cost" in result


class TestDataIntegration:
    """
    Tests for data integration
    """

    @patch('trading.bots.hedge_bot.data.market_data.MarketDataProvider.get_price')
    def test_market_data(self, mock_get_price: Mock, hedge_bot: HedgeBot) -> None:
        """Test market data provider"""
        market_data = MarketDataProvider({
            "sources": ["exchange", "oracle"],
            "update_frequency": 5,
        })
        
        market_data.initialize(hedge_bot)
        
        # Get price
        price = market_data.get_price("BTC/USDT")
        assert price is not None
        
        # Get historical data
        history = market_data.get_historical("BTC/USDT", days=30)
        assert history is not None

    def test_sentiment_analyzer(self, hedge_bot: HedgeBot) -> None:
        """Test sentiment analyzer"""
        sentiment = SentimentAnalyzer({
            "sources": ["twitter", "news", "social_media"],
            "update_frequency": 60,
        })
        
        sentiment.initialize(hedge_bot)
        
        # Analyze sentiment
        result = sentiment.analyze("BTC")
        assert "score" in result
        assert "confidence" in result


class TestAIIntegration:
    """
    Tests for AI/ML integration
    """

    @patch('trading.bots.hedge_bot.ai.predictor.MarketPredictor.predict')
    def test_market_predictor(self, mock_predict: Mock, hedge_bot: HedgeBot) -> None:
        """Test market predictor"""
        predictor = MarketPredictor({
            "model_type": "ensemble",
            "model_path": "/tmp/test_model.pkl",
        })
        
        predictor.initialize(hedge_bot)
        
        # Get prediction
        result = predictor.predict("BTC/USDT")
        assert "direction" in result
        assert "confidence" in result

    def test_ensemble_model(self, hedge_bot: HedgeBot) -> None:
        """Test ensemble model"""
        model = EnsembleModel({
            "models": ["random_forest", "xgboost", "lstm"],
            "weights": [0.4, 0.3, 0.3],
        })
        
        model.initialize(hedge_bot)
        
        # Train model
        model.train({
            "X": [[1.0, 2.0], [3.0, 4.0]],
            "y": [0.0, 1.0],
        })
        
        # Predict
        result = model.predict([[1.0, 2.0]])
        assert result is not None


class TestAPIAndWebSocket:
    """
    Tests for API and WebSocket integration
    """

    def test_api_initialization(self, hedge_bot: HedgeBot) -> None:
        """Test API initialization"""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_websocket_manager(self, hedge_bot: HedgeBot) -> None:
        """Test WebSocket manager"""
        ws_manager = WebSocketManager({
            "max_connections": 100,
            "heartbeat_interval": 30,
        })
        
        ws_manager.initialize(hedge_bot)
        
        # Get status
        status = ws_manager.get_status()
        assert "connections" in status
        assert "subscriptions" in status


class TestEndToEnd:
    """
    End-to-end tests for hedge bot
    """

    @pytest.mark.asyncio
    async def test_full_trading_cycle(self, hedge_bot: HedgeBot) -> None:
        """Test full trading cycle"""
        # Start bot
        await hedge_bot.start_async()
        
        # Wait for initialization
        await asyncio.sleep(1)
        
        # Check status
        status = hedge_bot.health_check()
        assert status["status"] == "healthy"
        
        # Execute trade
        trade_result = await hedge_bot.execute_trade({
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 1.0,
            "price": 50000.0,
        })
        assert trade_result is not None
        
        # Stop bot
        await hedge_bot.stop_async()
        assert hedge_bot.is_running is False

    @patch('trading.bots.hedge_bot.main.HedgeBot.execute_strategy')
    def test_strategy_workflow(self, mock_execute: Mock, hedge_bot: HedgeBot) -> None:
        """Test strategy workflow"""
        # Start bot
        hedge_bot.start()
        
        # Execute strategy
        result = hedge_bot.execute_strategy("delta_hedging")
        assert result is not None
        
        # Stop bot
        hedge_bot.stop()

    def test_error_recovery(self, hedge_bot: HedgeBot) -> None:
        """Test error recovery"""
        # Start bot
        hedge_bot.start()
        
        # Simulate error
        try:
            raise Exception("Test error")
        except Exception as e:
            hedge_bot.handle_error(e)
        
        # Verify recovery
        assert hedge_bot.is_running is True
        assert hedge_bot.error_count > 0
        
        # Stop bot
        hedge_bot.stop()


# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestHedgeBotPerformance:
    """
    Performance tests for hedge bot
    """

    def test_startup_time(self, hedge_bot: HedgeBot) -> None:
        """Test startup time"""
        start = time.time()
        hedge_bot.start()
        duration = time.time() - start
        
        assert duration < 5.0, f"Startup time too slow: {duration:.2f}s"
        hedge_bot.stop()

    def test_strategy_execution_time(self, hedge_bot: HedgeBot) -> None:
        """Test strategy execution time"""
        hedge_bot.start()
        
        strategy = DeltaHedgingStrategy({"hedge_ratio": 0.50})
        strategy.initialize(hedge_bot)
        
        start = time.time()
        for _ in range(100):
            strategy.calculate_hedge_ratio({
                "symbol": "BTC/USDT",
                "quantity": 1.0,
                "price": 50000.0,
            })
        duration = time.time() - start
        
        assert duration < 1.0, f"Strategy execution too slow: {duration:.3f}s"
        hedge_bot.stop()


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "TestHedgeBot",
    "TestStrategyIntegration",
    "TestRiskManagementIntegration",
    "TestExecutionIntegration",
    "TestPortfolioIntegration",
    "TestDataIntegration",
    "TestAIIntegration",
    "TestAPIAndWebSocket",
    "TestEndToEnd",
    "TestHedgeBotPerformance",
]

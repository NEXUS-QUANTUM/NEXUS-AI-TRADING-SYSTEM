"""
Swing Bot Sniper Bot Tests
===========================

This module contains unit tests for the Sniper Bot component of the Swing Bot trading system.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from trading.bots.swing_bot.bots.sniper_bot import SniperBot
from trading.bots.swing_bot.core import Signal, SignalType, OrderSide, OrderType
from trading.bots.swing_bot.risk_management import RiskManager
from trading.bots.swing_bot.execution_engine import ExecutionEngine
from trading.bots.swing_bot.utils.validators import validate_data

from .fixtures import get_market_data_fixture, get_config_fixture


class TestSniperBot:
    """Tests for SniperBot."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_fixture()
    
    @pytest.fixture
    def risk_manager(self):
        """Create a mock risk manager."""
        risk_manager = Mock(spec=RiskManager)
        risk_manager.check_risk = AsyncMock(return_value=True)
        risk_manager.calculate_position_size = Mock(return_value=100)
        return risk_manager
    
    @pytest.fixture
    def execution_engine(self):
        """Create a mock execution engine."""
        execution_engine = Mock(spec=ExecutionEngine)
        execution_engine.execute_order = AsyncMock(return_value={"order_id": "test_123"})
        return execution_engine
    
    @pytest.fixture
    def bot(self, config, risk_manager, execution_engine):
        """Create a SniperBot instance."""
        return SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL",
            precision_threshold=0.01,
            entry_timeout=10,
            max_spread=0.005
        )
    
    def test_initialization(self, bot):
        """Test bot initialization."""
        assert bot.symbol == "AAPL"
        assert bot.precision_threshold == 0.01
        assert bot.entry_timeout == 10
        assert bot.max_spread == 0.005
        assert bot.is_running is False
    
    def test_start_stop(self, bot):
        """Test starting and stopping the bot."""
        # Start the bot
        bot.start()
        assert bot.is_running is True
        
        # Stop the bot
        bot.stop()
        assert bot.is_running is False
    
    @pytest.mark.asyncio
    async def test_process_market_data(self, bot, market_data):
        """Test processing market data."""
        # Convert list to DataFrame
        df = pd.DataFrame(market_data)
        
        # Start the bot
        bot.start()
        
        # Process market data
        result = await bot.process_market_data(df)
        
        assert result is not None
        assert isinstance(result, dict)
        assert "signals" in result
        
        # Stop the bot
        bot.stop()
    
    @pytest.mark.asyncio
    async def test_generate_signals(self, bot, market_data):
        """Test signal generation."""
        # Convert list to DataFrame
        df = pd.DataFrame(market_data)
        
        # Generate signals
        signals = await bot._generate_signals(df)
        
        assert signals is not None
        assert isinstance(signals, list)
        
        # Check signal structure
        if signals:
            signal = signals[0]
            assert hasattr(signal, "symbol")
            assert hasattr(signal, "signal_type")
            assert hasattr(signal, "price")
            assert hasattr(signal, "confidence")
    
    @pytest.mark.asyncio
    async def test_entry_conditions(self, bot):
        """Test entry condition checking."""
        # Create test data
        df = pd.DataFrame({
            'timestamp': [datetime.now()] * 10,
            'open': np.random.randn(10) * 5 + 100,
            'high': np.random.randn(10) * 5 + 102,
            'low': np.random.randn(10) * 5 + 98,
            'close': np.random.randn(10) * 5 + 100,
            'volume': np.random.randint(100000, 1000000, 10)
        })
        
        # Check entry conditions
        result = await bot._check_entry_conditions(df.iloc[-1])
        
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_execute_trade(self, bot):
        """Test trade execution."""
        # Create a test signal
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85,
            timestamp=datetime.now()
        )
        
        # Execute trade
        result = await bot._execute_trade(signal)
        
        assert result is not None
        assert "order_id" in result
        assert result["order_id"] == "test_123"
    
    @pytest.mark.asyncio
    async def test_risk_management(self, bot, risk_manager):
        """Test risk management integration."""
        # Create a test signal
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85,
            timestamp=datetime.now()
        )
        
        # Check risk
        risk_check = await bot._check_risk(signal)
        assert risk_check is True
        
        # Calculate position size
        position_size = bot._calculate_position_size(signal)
        assert position_size == 100
    
    def test_precision_threshold(self, bot):
        """Test precision threshold checking."""
        # Test within threshold
        assert bot._check_precision(150.0, 150.01) is True
        
        # Test outside threshold
        assert bot._check_precision(150.0, 150.02) is False
    
    def test_spread_check(self, bot):
        """Test spread checking."""
        # Test within max spread
        assert bot._check_spread(150.0, 150.002) is True
        
        # Test exceeding max spread
        assert bot._check_spread(150.0, 150.01) is False
    
    def test_entry_timeout(self, bot):
        """Test entry timeout checking."""
        # Create a time in the past
        past_time = datetime.now() - timedelta(seconds=20)
        
        # Test timeout exceeded
        assert bot._check_timeout(past_time) is True
        
        # Test within timeout
        recent_time = datetime.now() - timedelta(seconds=5)
        assert bot._check_timeout(recent_time) is False
    
    @pytest.mark.asyncio
    async def test_error_handling(self, bot, market_data):
        """Test error handling."""
        # Test with invalid data
        with pytest.raises(ValueError):
            await bot.process_market_data(None)
        
        # Test with empty data
        result = await bot.process_market_data(pd.DataFrame())
        assert result is not None
        assert "errors" in result
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self, bot, market_data):
        """Test performance metrics calculation."""
        # Convert list to DataFrame
        df = pd.DataFrame(market_data)
        
        # Process market data
        await bot.process_market_data(df)
        
        # Get metrics
        metrics = bot.get_metrics()
        
        assert metrics is not None
        assert "total_signals" in metrics
        assert "total_trades" in metrics
        assert "win_rate" in metrics
        assert "average_return" in metrics
    
    def test_config_validation(self, bot):
        """Test configuration validation."""
        # Test valid config
        assert bot._validate_config() is True
        
        # Test invalid config
        bot.precision_threshold = -1.0
        with pytest.raises(ValueError):
            bot._validate_config()
    
    @pytest.mark.asyncio
    async def test_market_data_update(self, bot, market_data):
        """Test market data update."""
        # Convert list to DataFrame
        df = pd.DataFrame(market_data)
        
        # Initial update
        initial_signals = await bot.process_market_data(df)
        
        # Update with new data
        new_data = pd.DataFrame(market_data[-5:])
        new_signals = await bot.process_market_data(new_data)
        
        assert initial_signals != new_signals
    
    @pytest.mark.asyncio
    async def test_multiple_symbols(self, bot):
        """Test handling multiple symbols."""
        # Test with different symbol
        bot.symbol = "GOOGL"
        
        assert bot.symbol == "GOOGL"
        
        # Create test data for new symbol
        df = pd.DataFrame({
            'symbol': ['GOOGL'] * 10,
            'timestamp': [datetime.now()] * 10,
            'open': np.random.randn(10) * 5 + 2500,
            'high': np.random.randn(10) * 5 + 2505,
            'low': np.random.randn(10) * 5 + 2495,
            'close': np.random.randn(10) * 5 + 2500,
            'volume': np.random.randint(100000, 1000000, 10)
        })
        
        # Process market data
        result = await bot.process_market_data(df)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, bot, market_data):
        """Test concurrent operations."""
        import asyncio
        
        # Convert list to DataFrame
        df = pd.DataFrame(market_data)
        
        # Run multiple operations concurrently
        tasks = [
            bot.process_market_data(df),
            bot.process_market_data(df),
            bot.process_market_data(df)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        assert all(r is not None for r in results)


class TestSniperBotIntegration:
    """Integration tests for SniperBot."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def bot(self, config):
        """Create a real SniperBot instance with mocks."""
        risk_manager = Mock(spec=RiskManager)
        risk_manager.check_risk = AsyncMock(return_value=True)
        risk_manager.calculate_position_size = Mock(return_value=100)
        
        execution_engine = Mock(spec=ExecutionEngine)
        execution_engine.execute_order = AsyncMock(return_value={"order_id": "test_123"})
        
        return SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
    
    @pytest.mark.asyncio
    async def test_end_to_end(self, bot):
        """Test end-to-end flow."""
        # Create test data
        df = pd.DataFrame({
            'timestamp': [datetime.now() + timedelta(minutes=i) for i in range(50)],
            'open': np.random.randn(50) * 5 + 100,
            'high': np.random.randn(50) * 5 + 102,
            'low': np.random.randn(50) * 5 + 98,
            'close': np.random.randn(50) * 5 + 100,
            'volume': np.random.randint(100000, 1000000, 50)
        })
        
        # Start bot
        bot.start()
        
        # Process data
        result = await bot.process_market_data(df)
        
        # Verify result
        assert result is not None
        assert "signals" in result
        assert "metrics" in result
        
        # Stop bot
        bot.stop()
    
    @pytest.mark.asyncio
    async def test_performance_benchmark(self, bot):
        """Test performance benchmarking."""
        import time
        
        # Create large test data
        n_rows = 1000
        df = pd.DataFrame({
            'timestamp': [datetime.now() + timedelta(seconds=i) for i in range(n_rows)],
            'open': np.random.randn(n_rows) * 5 + 100,
            'high': np.random.randn(n_rows) * 5 + 102,
            'low': np.random.randn(n_rows) * 5 + 98,
            'close': np.random.randn(n_rows) * 5 + 100,
            'volume': np.random.randint(100000, 1000000, n_rows)
        })
        
        # Start bot
        bot.start()
        
        # Measure processing time
        start_time = time.time()
        result = await bot.process_market_data(df)
        elapsed_time = time.time() - start_time
        
        # Verify performance
        assert elapsed_time < 10.0  # Should process in less than 10 seconds
        assert result is not None
        
        # Stop bot
        bot.stop()


if __name__ == "__main__":
    pytest.main([__file__])

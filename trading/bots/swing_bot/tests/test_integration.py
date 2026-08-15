"""
Swing Bot Integration Tests.
============================

This module contains integration tests for the Swing Bot trading system.
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from trading.bots.swing_bot.core import (
    Engine,
    Signal,
    SignalType,
    OrderSide,
    OrderType,
    Position,
    Trade,
    Portfolio
)
from trading.bots.swing_bot.strategies import (
    MomentumStrategy,
    MeanReversionStrategy,
    BreakoutStrategy
)
from trading.bots.swing_bot.risk_management import RiskManager
from trading.bots.swing_bot.execution_engine import ExecutionEngine
from trading.bots.swing_bot.bots.sniper_bot import SniperBot
from trading.bots.swing_bot.monitoring import MonitoringService

from .fixtures import get_config_fixture, get_market_data_fixture


class TestIntegration:
    """Integration tests for the trading system."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_fixture()
    
    @pytest.fixture
    def engine(self, config):
        """Create a trading engine instance."""
        return Engine(config=config)
    
    @pytest.mark.asyncio
    async def test_end_to_end_trading_flow(self, config, market_data):
        """Test complete end-to-end trading flow."""
        # Convert to DataFrame
        df = pd.DataFrame(market_data)
        
        # Create strategies
        momentum = MomentumStrategy()
        mean_reversion = MeanReversionStrategy()
        breakout = BreakoutStrategy()
        
        # Create risk manager
        risk_manager = RiskManager(config=config)
        
        # Create execution engine
        execution_engine = ExecutionEngine(config=config)
        
        # Create bot
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        # Start bot
        bot.start()
        
        # Process market data
        result = await bot.process_market_data(df)
        
        assert result is not None
        assert "signals" in result
        assert "metrics" in result
        
        # Stop bot
        bot.stop()
    
    @pytest.mark.asyncio
    async def test_strategy_chain_execution(self, market_data):
        """Test execution of multiple strategies in sequence."""
        df = pd.DataFrame(market_data)
        
        # Create strategies
        momentum = MomentumStrategy()
        mean_reversion = MeanReversionStrategy()
        
        # Generate signals
        momentum_signals = momentum.generate_signals(df)
        mean_reversion_signals = mean_reversion.generate_signals(df)
        
        # Combine signals
        all_signals = momentum_signals + mean_reversion_signals
        
        # Filter and rank signals
        filtered_signals = [s for s in all_signals if s.confidence is not None and s.confidence > 0.7]
        ranked_signals = sorted(filtered_signals, key=lambda s: s.confidence, reverse=True)
        
        assert len(ranked_signals) > 0
        assert ranked_signals[0].confidence >= 0.7
    
    @pytest.mark.asyncio
    async def test_risk_execution_flow(self, config, market_data):
        """Test risk management and execution flow."""
        df = pd.DataFrame(market_data)
        
        # Create risk manager
        risk_manager = RiskManager(config=config)
        
        # Create execution engine
        execution_engine = ExecutionEngine(config=config)
        
        # Generate a test signal
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=df['close'].iloc[-1],
            confidence=0.85,
            timestamp=datetime.now()
        )
        
        # Check risk
        risk_check = await risk_manager.check_risk(signal)
        assert risk_check is True
        
        # Calculate position size
        position_size = await risk_manager.calculate_position_size(signal)
        assert position_size > 0
        
        # Execute trade
        order_result = await execution_engine.execute_order(
            symbol=signal.symbol,
            side=OrderSide.BUY,
            quantity=position_size,
            order_type=OrderType.MARKET
        )
        
        assert order_result is not None
        assert "order_id" in order_result
    
    @pytest.mark.asyncio
    async def test_portfolio_management(self, config, market_data):
        """Test portfolio management."""
        # Create portfolio
        portfolio = Portfolio(
            account_id="TEST_ACC",
            cash=100000.0,
            positions=[]
        )
        
        # Create positions
        for symbol in ["AAPL", "GOOGL", "MSFT"]:
            position = Position(
                symbol=symbol,
                quantity=100,
                entry_price=100.0,
                current_price=105.0
            )
            portfolio.add_position(position)
        
        # Test portfolio calculations
        total_value = portfolio.calculate_total_value()
        total_pnl = portfolio.calculate_total_pnl()
        
        assert total_value > 0
        assert total_pnl > 0
        
        # Test risk limits
        risk_manager = RiskManager(config=config)
        risk_check = await risk_manager.check_portfolio_risk(portfolio)
        assert risk_check is True
    
    def test_market_data_pipeline(self, market_data):
        """Test market data processing pipeline."""
        df = pd.DataFrame(market_data)
        
        # Data validation
        assert not df.empty
        assert all(col in df.columns for col in ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Data cleaning
        df = df.dropna()
        df = df[df['volume'] > 0]
        
        assert not df.empty
        
        # Feature engineering
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['volatility'] = df['returns'].rolling(20).std()
        
        assert 'returns' in df.columns
        assert 'log_returns' in df.columns
        assert 'volatility' in df.columns
    
    @pytest.mark.asyncio
    async def test_monitoring_integration(self, config, market_data):
        """Test monitoring integration."""
        df = pd.DataFrame(market_data)
        
        # Create monitoring service
        monitoring = MonitoringService(config=config)
        monitoring.start()
        
        # Create and run bot
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        bot.start()
        
        # Process data and collect metrics
        start_time = datetime.now()
        result = await bot.process_market_data(df)
        
        # Collect metrics
        monitoring.collect_system_metrics()
        monitoring.track_metric("trading_result", result)
        
        # Stop services
        bot.stop()
        monitoring.stop()
        
        assert result is not None
        assert monitoring.metrics is not None
    
    def test_configuration_loading(self, config):
        """Test configuration loading and validation."""
        # Check required config sections
        assert "trading" in config
        assert "risk" in config
        assert "logging" in config
        assert "monitoring" in config
        
        # Check trading config
        trading_config = config.get("trading", {})
        assert "enabled" in trading_config
        assert "mode" in trading_config
        assert "initial_capital" in trading_config
        
        # Check risk config
        risk_config = config.get("risk", {})
        assert "enabled" in risk_config
        assert "var_confidence" in risk_config
        assert "max_leverage" in risk_config
    
    @pytest.mark.asyncio
    async def test_concurrent_trading(self, config, market_data):
        """Test concurrent trading operations."""
        df = pd.DataFrame(market_data)
        
        # Create multiple bots
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        
        symbols = ["AAPL", "GOOGL", "MSFT"]
        bots = []
        
        for symbol in symbols:
            bot = SniperBot(
                config=config,
                risk_manager=risk_manager,
                execution_engine=execution_engine,
                symbol=symbol
            )
            bot.start()
            bots.append(bot)
        
        # Process data concurrently
        tasks = [bot.process_market_data(df) for bot in bots]
        results = await asyncio.gather(*tasks)
        
        # Stop bots
        for bot in bots:
            bot.stop()
        
        assert len(results) == len(symbols)
        assert all(r is not None for r in results)
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, config):
        """Test error recovery and retry mechanisms."""
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        
        # Create bot with invalid config
        with pytest.raises(ValueError):
            SniperBot(
                config=config,
                risk_manager=risk_manager,
                execution_engine=execution_engine,
                symbol="",
                precision_threshold=-1.0
            )
        
        # Test graceful error handling
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        # Test with invalid data
        result = await bot.process_market_data(pd.DataFrame())
        assert result is not None
        assert "errors" in result
    
    @pytest.mark.asyncio
    async def test_performance_scaling(self, config):
        """Test performance scaling with data size."""
        risk_manager = RiskManager(config=config)
        execution_engine = ExecutionEngine(config=config)
        
        bot = SniperBot(
            config=config,
            risk_manager=risk_manager,
            execution_engine=execution_engine,
            symbol="AAPL"
        )
        
        bot.start()
        
        # Test with increasing data sizes
        sizes = [100, 500, 1000, 5000]
        results = []
        
        for size in sizes:
            df = pd.DataFrame({
                'timestamp': [datetime.now() + timedelta(seconds=i) for i in range(size)],
                'open': np.random.randn(size) * 5 + 100,
                'high': np.random.randn(size) * 5 + 102,
                'low': np.random.randn(size) * 5 + 98,
                'close': np.random.randn(size) * 5 + 100,
                'volume': np.random.randint(100000, 1000000, size)
            })
            
            result = await bot.process_market_data(df)
            results.append(result)
        
        bot.stop()
        
        assert len(results) == len(sizes)
        assert all(r is not None for r in results)
    
    @pytest.mark.asyncio
    async def test_cross_strategy_integration(self, market_data):
        """Test integration between different strategies."""
        df = pd.DataFrame(market_data)
        
        # Create strategies
        momentum = MomentumStrategy()
        mean_reversion = MeanReversionStrategy()
        breakout = BreakoutStrategy()
        
        # Generate signals
        momentum_signals = momentum.generate_signals(df)
        mean_reversion_signals = mean_reversion.generate_signals(df)
        breakout_signals = breakout.generate_signals(df)
        
        # Validate signals
        for signal in momentum_signals:
            assert signal.symbol == "AAPL"
            assert signal.signal_type in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        
        for signal in mean_reversion_signals:
            assert signal.symbol == "AAPL"
            assert signal.signal_type in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        
        for signal in breakout_signals:
            assert signal.symbol == "AAPL"
            assert signal.signal_type in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]
        
        # Check signal confidence
        all_signals = momentum_signals + mean_reversion_signals + breakout_signals
        for signal in all_signals:
            if signal.confidence is not None:
                assert 0.0 <= signal.confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__])

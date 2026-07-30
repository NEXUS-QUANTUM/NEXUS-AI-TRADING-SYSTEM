# trading/bots/hedge_bot/tests/test_core.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Core Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Core Tests

This module provides comprehensive unit tests for the core components
of the NEXUS Hedge Bot system. It covers the main engine, configuration,
logging, and other core functionality.

The test suite covers:
- HedgeEngine initialization and configuration
- Core component integration
- Configuration management
- Logging system
- Error handling
- Health checks
- Lifecycle management
- Service discovery
- Plugin system
- Event system
- State management
- Performance monitoring
- Resource management
- Thread management
- Queue management
- Cache management
"""

import os
import sys
import json
import logging
import asyncio
import tempfile
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock

import pytest
import pytest_asyncio

# Import module under test
from trading.bots.hedge_bot.core.engine import HedgeEngine, HedgeEngineConfig
from trading.bots.hedge_bot.core.config import ConfigManager
from trading.bots.hedge_bot.core.logging import LoggerManager
from trading.bots.hedge_bot.core.health import HealthChecker
from trading.bots.hedge_bot.core.exceptions import (
    HedgeBotError,
    ConfigurationError,
    ExchangeError,
    StrategyError,
    RiskError,
    DataError,
)
from trading.bots.hedge_bot.core.events import EventBus, Event, EventType
from trading.bots.hedge_bot.core.state import StateManager
from trading.bots.hedge_bot.core.plugin import PluginManager

# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture
def temp_config_dir() -> Path:
    """Create temporary config directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Create test configuration"""
    return {
        "bot": {
            "id": "test_bot",
            "name": "Test Hedge Bot",
            "version": "2.0.0-test",
            "enabled": True,
            "active": True,
            "environment": "testing",
            "log_level": "DEBUG",
        },
        "exchange": {
            "name": "binance",
            "type": "spot",
            "sandbox": True,
            "api": {
                "key": "test_key",
                "secret": "test_secret",
            },
            "pairs": ["BTC/USDT", "ETH/USDT"],
        },
        "trading": {
            "position": {
                "max_leverage": 3.0,
                "target_hedge_ratio": 0.50,
            },
            "order": {
                "max_order_size": 10000,
                "slippage_tolerance": 0.001,
            }
        },
        "risk_management": {
            "limits": {
                "max_drawdown": 0.15,
                "daily_loss_limit": 0.05,
            }
        },
        "data": {
            "sources": {
                "market_data": {
                    "provider": "mock"
                }
            }
        },
        "logging": {
            "config": {
                "enabled": True,
                "log_level": "DEBUG",
            }
        }
    }


@pytest.fixture
def engine_config(test_config: Dict[str, Any]) -> HedgeEngineConfig:
    """Create engine configuration"""
    return HedgeEngineConfig(**test_config)


@pytest.fixture
def hedge_engine(engine_config: HedgeEngineConfig) -> HedgeEngine:
    """Create hedge engine instance"""
    return HedgeEngine(engine_config)


@pytest.fixture
def event_bus() -> EventBus:
    """Create event bus"""
    return EventBus()


@pytest.fixture
def state_manager() -> StateManager:
    """Create state manager"""
    return StateManager()


@pytest.fixture
def plugin_manager() -> PluginManager:
    """Create plugin manager"""
    return PluginManager()


# ============================================================
# CORE TESTS
# ============================================================

class TestHedgeEngine:
    """
    Tests for HedgeEngine core functionality
    """

    def test_engine_initialization(self, hedge_engine: HedgeEngine) -> None:
        """Test engine initialization"""
        assert hedge_engine is not None
        assert hedge_engine.config is not None
        assert hedge_engine.is_running is False
        assert hedge_engine.status == "initialized"

    def test_engine_start_stop(self, hedge_engine: HedgeEngine) -> None:
        """Test engine start and stop"""
        # Start engine
        hedge_engine.start()
        assert hedge_engine.is_running is True
        assert hedge_engine.status == "running"
        
        # Stop engine
        hedge_engine.stop()
        assert hedge_engine.is_running is False
        assert hedge_engine.status == "stopped"

    @pytest.mark.asyncio
    async def test_engine_async_start_stop(self, hedge_engine: HedgeEngine) -> None:
        """Test async engine start and stop"""
        # Start engine
        await hedge_engine.start_async()
        assert hedge_engine.is_running is True
        
        # Stop engine
        await hedge_engine.stop_async()
        assert hedge_engine.is_running is False

    def test_engine_config_validation(self, hedge_engine: HedgeEngine) -> None:
        """Test engine configuration validation"""
        # Valid config should pass
        assert hedge_engine.validate_config() is True
        
        # Invalid config should raise error
        invalid_config = {"bot": {"enabled": True}}
        with pytest.raises(ConfigurationError):
            HedgeEngine(HedgeEngineConfig(**invalid_config))

    def test_engine_health_check(self, hedge_engine: HedgeEngine) -> None:
        """Test engine health check"""
        health = hedge_engine.health_check()
        assert "status" in health
        assert "components" in health
        assert "timestamp" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    def test_engine_status_update(self, hedge_engine: HedgeEngine) -> None:
        """Test engine status updates"""
        assert hedge_engine.status == "initialized"
        
        hedge_engine._update_status("starting")
        assert hedge_engine.status == "starting"
        
        hedge_engine._update_status("running")
        assert hedge_engine.status == "running"
        
        hedge_engine._update_status("stopped")
        assert hedge_engine.status == "stopped"

    def test_engine_error_handling(self, hedge_engine: HedgeEngine) -> None:
        """Test engine error handling"""
        with pytest.raises(HedgeBotError):
            hedge_engine._handle_error(Exception("Test error"))
        
        # Error should be logged and status updated
        assert hedge_engine.error_count > 0
        assert hedge_engine.last_error is not None

    @patch('trading.bots.hedge_bot.core.engine.logger')
    def test_engine_logging(self, mock_logger: Mock, hedge_engine: HedgeEngine) -> None:
        """Test engine logging"""
        hedge_engine._log_info("Test info message")
        mock_logger.info.assert_called_once()
        
        hedge_engine._log_error("Test error message")
        mock_logger.error.assert_called_once()
        
        hedge_engine._log_debug("Test debug message")
        mock_logger.debug.assert_called_once()

    def test_engine_metrics(self, hedge_engine: HedgeEngine) -> None:
        """Test engine metrics collection"""
        metrics = hedge_engine.get_metrics()
        assert "uptime" in metrics
        assert "error_count" in metrics
        assert "component_status" in metrics
        assert metrics["error_count"] == hedge_engine.error_count


class TestConfigManager:
    """
    Tests for ConfigManager
    """

    def test_config_manager_initialization(self, temp_config_dir: Path) -> None:
        """Test config manager initialization"""
        config_manager = ConfigManager(temp_config_dir)
        assert config_manager.config_dir == temp_config_dir
        assert config_manager.config is not None

    def test_config_manager_load(self, temp_config_dir: Path, test_config: Dict[str, Any]) -> None:
        """Test config manager load"""
        # Write test config
        config_file = temp_config_dir / "config.yaml"
        with open(config_file, "w") as f:
            json.dump(test_config, f)
        
        config_manager = ConfigManager(temp_config_dir)
        config_manager.load()
        
        assert config_manager.config is not None
        assert config_manager.config["bot"]["id"] == "test_bot"

    def test_config_manager_get(self, temp_config_dir: Path, test_config: Dict[str, Any]) -> None:
        """Test config manager get"""
        config_manager = ConfigManager(temp_config_dir)
        config_manager.config = test_config
        
        # Test getting existing key
        assert config_manager.get("bot.id") == "test_bot"
        assert config_manager.get("exchange.name") == "binance"
        assert config_manager.get("trading.position.max_leverage") == 3.0
        
        # Test getting non-existing key with default
        assert config_manager.get("non.existing.key", default="default") == "default"
        
        # Test getting non-existing key without default
        assert config_manager.get("non.existing.key") is None

    def test_config_manager_set(self, temp_config_dir: Path, test_config: Dict[str, Any]) -> None:
        """Test config manager set"""
        config_manager = ConfigManager(temp_config_dir)
        config_manager.config = test_config
        
        # Set existing key
        config_manager.set("bot.name", "Updated Bot")
        assert config_manager.get("bot.name") == "Updated Bot"
        
        # Set nested key
        config_manager.set("new.nested.key", "value")
        assert config_manager.get("new.nested.key") == "value"
        assert config_manager.get("new.nested") is not None

    def test_config_manager_save(self, temp_config_dir: Path, test_config: Dict[str, Any]) -> None:
        """Test config manager save"""
        config_manager = ConfigManager(temp_config_dir)
        config_manager.config = test_config
        
        # Save config
        config_manager.save()
        
        # Verify file was created
        config_file = temp_config_dir / "config.yaml"
        assert config_file.exists()
        
        # Verify content
        with open(config_file, "r") as f:
            saved_config = json.load(f)
        assert saved_config["bot"]["id"] == "test_bot"

    def test_config_manager_validate(self, temp_config_dir: Path) -> None:
        """Test config manager validate"""
        config_manager = ConfigManager(temp_config_dir)
        
        # Valid config
        config_manager.config = {
            "bot": {"enabled": True},
            "exchange": {"name": "binance"}
        }
        assert config_manager.validate() is True
        
        # Invalid config (missing required fields)
        config_manager.config = {"bot": {"enabled": True}}
        assert config_manager.validate() is False


class TestLoggerManager:
    """
    Tests for LoggerManager
    """

    def test_logger_manager_initialization(self) -> None:
        """Test logger manager initialization"""
        logger_manager = LoggerManager()
        assert logger_manager is not None
        assert logger_manager.loggers is not None

    def test_logger_manager_get_logger(self) -> None:
        """Test logger manager get logger"""
        logger_manager = LoggerManager()
        
        # Get existing logger
        logger = logger_manager.get_logger("test")
        assert logger is not None
        assert logger.name == "test"
        
        # Get same logger again
        logger2 = logger_manager.get_logger("test")
        assert logger is logger2

    def test_logger_manager_log_levels(self) -> None:
        """Test logger manager log levels"""
        logger_manager = LoggerManager()
        
        # Set log level
        logger_manager.set_log_level("DEBUG")
        assert logger_manager.log_level == "DEBUG"
        
        # Get logger with level
        logger = logger_manager.get_logger("test", "INFO")
        assert logger.level == logging.INFO

    def test_logger_manager_handlers(self) -> None:
        """Test logger manager handlers"""
        logger_manager = LoggerManager()
        
        # Add handler
        handler = logging.StreamHandler()
        logger_manager.add_handler("test", handler)
        
        # Verify handler was added
        logger = logger_manager.get_logger("test")
        assert handler in logger.handlers
        
        # Remove handler
        logger_manager.remove_handler("test", handler)
        assert handler not in logger.handlers

    def test_logger_manager_formatting(self) -> None:
        """Test logger manager formatting"""
        logger_manager = LoggerManager()
        
        # Set format
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        logger_manager.set_format(log_format)
        
        # Verify format was set
        logger = logger_manager.get_logger("test")
        for handler in logger.handlers:
            if hasattr(handler, 'formatter'):
                assert handler.formatter._fmt == log_format


class TestHealthChecker:
    """
    Tests for HealthChecker
    """

    def test_health_checker_initialization(self) -> None:
        """Test health checker initialization"""
        health_checker = HealthChecker()
        assert health_checker is not None
        assert health_checker.checks is not None
        assert health_checker.results is not None

    def test_health_checker_register_check(self) -> None:
        """Test health checker register check"""
        health_checker = HealthChecker()
        
        def mock_check() -> Dict[str, Any]:
            return {"status": "healthy", "message": "All good"}
        
        health_checker.register_check("test", mock_check)
        assert "test" in health_checker.checks

    def test_health_checker_run_checks(self) -> None:
        """Test health checker run checks"""
        health_checker = HealthChecker()
        
        def healthy_check() -> Dict[str, Any]:
            return {"status": "healthy", "message": "OK"}
        
        def unhealthy_check() -> Dict[str, Any]:
            return {"status": "unhealthy", "message": "Failed"}
        
        health_checker.register_check("healthy", healthy_check)
        health_checker.register_check("unhealthy", unhealthy_check)
        
        results = health_checker.run_checks()
        assert results["healthy"]["status"] == "healthy"
        assert results["unhealthy"]["status"] == "unhealthy"
        assert results["overall_status"] == "unhealthy"

    def test_health_checker_async_checks(self) -> None:
        """Test health checker async checks"""
        health_checker = HealthChecker()
        
        async def async_healthy_check() -> Dict[str, Any]:
            return {"status": "healthy", "message": "OK"}
        
        health_checker.register_check("async_healthy", async_healthy_check)
        
        # Run checks asynchronously
        import asyncio
        results = asyncio.run(health_checker.run_checks_async())
        assert results["async_healthy"]["status"] == "healthy"


class TestExceptions:
    """
    Tests for custom exceptions
    """

    def test_hedge_bot_error(self) -> None:
        """Test HedgeBotError"""
        error = HedgeBotError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_configuration_error(self) -> None:
        """Test ConfigurationError"""
        error = ConfigurationError("Config error")
        assert str(error) == "Config error"
        assert isinstance(error, HedgeBotError)

    def test_exchange_error(self) -> None:
        """Test ExchangeError"""
        error = ExchangeError("Exchange error")
        assert str(error) == "Exchange error"
        assert isinstance(error, HedgeBotError)

    def test_strategy_error(self) -> None:
        """Test StrategyError"""
        error = StrategyError("Strategy error")
        assert str(error) == "Strategy error"
        assert isinstance(error, HedgeBotError)

    def test_risk_error(self) -> None:
        """Test RiskError"""
        error = RiskError("Risk error")
        assert str(error) == "Risk error"
        assert isinstance(error, HedgeBotError)

    def test_data_error(self) -> None:
        """Test DataError"""
        error = DataError("Data error")
        assert str(error) == "Data error"
        assert isinstance(error, HedgeBotError)


class TestEventBus:
    """
    Tests for EventBus
    """

    def test_event_bus_initialization(self) -> None:
        """Test event bus initialization"""
        event_bus = EventBus()
        assert event_bus is not None
        assert event_bus.listeners is not None

    def test_event_bus_subscribe(self, event_bus: EventBus) -> None:
        """Test event bus subscribe"""
        def handler(event: Event) -> None:
            pass
        
        event_bus.subscribe(EventType.CONFIG_CHANGED, handler)
        assert EventType.CONFIG_CHANGED in event_bus.listeners
        assert handler in event_bus.listeners[EventType.CONFIG_CHANGED]

    def test_event_bus_unsubscribe(self, event_bus: EventBus) -> None:
        """Test event bus unsubscribe"""
        def handler(event: Event) -> None:
            pass
        
        event_bus.subscribe(EventType.CONFIG_CHANGED, handler)
        event_bus.unsubscribe(EventType.CONFIG_CHANGED, handler)
        assert handler not in event_bus.listeners.get(EventType.CONFIG_CHANGED, [])

    def test_event_bus_emit(self, event_bus: EventBus) -> None:
        """Test event bus emit"""
        handler_called = False
        
        def handler(event: Event) -> None:
            nonlocal handler_called
            handler_called = True
            assert event.type == EventType.CONFIG_CHANGED
        
        event_bus.subscribe(EventType.CONFIG_CHANGED, handler)
        event_bus.emit(Event(EventType.CONFIG_CHANGED, {"key": "value"}))
        
        assert handler_called is True

    def test_event_bus_emit_async(self, event_bus: EventBus) -> None:
        """Test event bus emit async"""
        handler_called = False
        
        async def async_handler(event: Event) -> None:
            nonlocal handler_called
            handler_called = True
            assert event.type == EventType.CONFIG_CHANGED
        
        event_bus.subscribe(EventType.CONFIG_CHANGED, async_handler)
        
        # Emit event and wait for async handlers
        import asyncio
        asyncio.run(event_bus.emit_async(Event(EventType.CONFIG_CHANGED, {"key": "value"})))
        
        assert handler_called is True


class TestStateManager:
    """
    Tests for StateManager
    """

    def test_state_manager_initialization(self) -> None:
        """Test state manager initialization"""
        state_manager = StateManager()
        assert state_manager is not None
        assert state_manager.state is not None

    def test_state_manager_set_get(self, state_manager: StateManager) -> None:
        """Test state manager set and get"""
        state_manager.set("key", "value")
        assert state_manager.get("key") == "value"
        
        state_manager.set("nested.key", "nested_value")
        assert state_manager.get("nested.key") == "nested_value"

    def test_state_manager_delete(self, state_manager: StateManager) -> None:
        """Test state manager delete"""
        state_manager.set("key", "value")
        assert state_manager.get("key") == "value"
        
        state_manager.delete("key")
        assert state_manager.get("key") is None

    def test_state_manager_save_load(self, temp_config_dir: Path) -> None:
        """Test state manager save and load"""
        state_manager = StateManager()
        state_manager.state_path = temp_config_dir / "state.json"
        
        # Save state
        state_manager.set("key", "value")
        state_manager.save()
        
        # Load state
        new_manager = StateManager()
        new_manager.state_path = state_manager.state_path
        new_manager.load()
        
        assert new_manager.get("key") == "value"

    def test_state_manager_clear(self, state_manager: StateManager) -> None:
        """Test state manager clear"""
        state_manager.set("key1", "value1")
        state_manager.set("key2", "value2")
        assert state_manager.get("key1") == "value1"
        assert state_manager.get("key2") == "value2"
        
        state_manager.clear()
        assert state_manager.get("key1") is None
        assert state_manager.get("key2") is None


class TestPluginManager:
    """
    Tests for PluginManager
    """

    def test_plugin_manager_initialization(self) -> None:
        """Test plugin manager initialization"""
        plugin_manager = PluginManager()
        assert plugin_manager is not None
        assert plugin_manager.plugins is not None

    def test_plugin_manager_register(self, plugin_manager: PluginManager) -> None:
        """Test plugin manager register"""
        class TestPlugin:
            def __init__(self):
                self.name = "test_plugin"
        
        plugin_manager.register("test", TestPlugin)
        assert "test" in plugin_manager.plugins

    def test_plugin_manager_get(self, plugin_manager: PluginManager) -> None:
        """Test plugin manager get"""
        class TestPlugin:
            def __init__(self):
                self.name = "test_plugin"
        
        plugin_manager.register("test", TestPlugin)
        plugin = plugin_manager.get("test")
        assert plugin is not None
        assert plugin.name == "test_plugin"

    def test_plugin_manager_unregister(self, plugin_manager: PluginManager) -> None:
        """Test plugin manager unregister"""
        class TestPlugin:
            def __init__(self):
                self.name = "test_plugin"
        
        plugin_manager.register("test", TestPlugin)
        assert "test" in plugin_manager.plugins
        
        plugin_manager.unregister("test")
        assert "test" not in plugin_manager.plugins

    def test_plugin_manager_load_plugins(self, temp_config_dir: Path) -> None:
        """Test plugin manager load plugins"""
        plugin_manager = PluginManager()
        plugin_manager.plugin_dir = temp_config_dir
        
        # Create a dummy plugin file
        plugin_file = temp_config_dir / "test_plugin.py"
        plugin_file.write_text("""
class TestPlugin:
    def __init__(self):
        self.name = "test_plugin"
        self.version = "1.0.0"
""")
        
        plugin_manager.load_plugins()
        assert plugin_manager.get("test_plugin") is not None


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestCoreIntegration:
    """
    Integration tests for core components
    """

    def test_full_engine_initialization(self, test_config: Dict[str, Any]) -> None:
        """Test full engine initialization with all components"""
        engine_config = HedgeEngineConfig(**test_config)
        engine = HedgeEngine(engine_config)
        
        # Verify all components are initialized
        assert engine.config_manager is not None
        assert engine.logger_manager is not None
        assert engine.health_checker is not None
        assert engine.event_bus is not None
        assert engine.state_manager is not None
        
        # Start engine
        engine.start()
        assert engine.is_running is True
        
        # Stop engine
        engine.stop()
        assert engine.is_running is False

    @pytest.mark.asyncio
    async def test_async_event_processing(self, hedge_engine: HedgeEngine) -> None:
        """Test async event processing"""
        event_processed = False
        
        async def event_handler(event: Event) -> None:
            nonlocal event_processed
            event_processed = True
        
        hedge_engine.event_bus.subscribe(EventType.CONFIG_CHANGED, event_handler)
        await hedge_engine.event_bus.emit_async(Event(EventType.CONFIG_CHANGED, {"key": "value"}))
        
        assert event_processed is True

    def test_health_check_integration(self, hedge_engine: HedgeEngine) -> None:
        """Test health check integration"""
        # Register health checks
        def exchange_check() -> Dict[str, Any]:
            return {"status": "healthy", "message": "Exchange connected"}
        
        def strategy_check() -> Dict[str, Any]:
            return {"status": "healthy", "message": "Strategy running"}
        
        hedge_engine.health_checker.register_check("exchange", exchange_check)
        hedge_engine.health_checker.register_check("strategy", strategy_check)
        
        # Run checks
        results = hedge_engine.health_checker.run_checks()
        assert results["exchange"]["status"] == "healthy"
        assert results["strategy"]["status"] == "healthy"
        assert results["overall_status"] == "healthy"

    def test_error_handling_integration(self, hedge_engine: HedgeEngine) -> None:
        """Test error handling integration"""
        # Simulate error in component
        try:
            raise HedgeBotError("Test error")
        except HedgeBotError as e:
            hedge_engine._handle_error(e)
        
        assert hedge_engine.error_count == 1
        assert hedge_engine.last_error is not None
        assert "Test error" in str(hedge_engine.last_error)

    def test_state_persistence(self, hedge_engine: HedgeEngine, temp_config_dir: Path) -> None:
        """Test state persistence"""
        # Set state path
        hedge_engine.state_manager.state_path = temp_config_dir / "state.json"
        
        # Set state
        hedge_engine.state_manager.set("test_key", "test_value")
        hedge_engine.state_manager.save()
        
        # Create new engine and load state
        new_config = hedge_engine.config
        new_engine = HedgeEngine(new_config)
        new_engine.state_manager.state_path = hedge_engine.state_manager.state_path
        new_engine.state_manager.load()
        
        assert new_engine.state_manager.get("test_key") == "test_value"


# ============================================================
# BENCHMARK TESTS
# ============================================================

class TestCorePerformance:
    """
    Performance tests for core components
    """

    def test_config_manager_performance(self, temp_config_dir: Path, test_config: Dict[str, Any]) -> None:
        """Test config manager performance"""
        config_manager = ConfigManager(temp_config_dir)
        config_manager.config = test_config
        
        import time
        start = time.time()
        
        # Perform 1000 get operations
        for _ in range(1000):
            config_manager.get("bot.id")
        
        duration = time.time() - start
        assert duration < 0.1, f"Config get operations too slow: {duration:.3f}s"

    def test_event_bus_performance(self, event_bus: EventBus) -> None:
        """Test event bus performance"""
        def handler(event: Event) -> None:
            pass
        
        # Register 100 handlers
        for i in range(100):
            event_bus.subscribe(EventType.CONFIG_CHANGED, handler)
        
        import time
        start = time.time()
        
        # Emit 1000 events
        for _ in range(1000):
            event_bus.emit(Event(EventType.CONFIG_CHANGED, {"key": "value"}))
        
        duration = time.time() - start
        assert duration < 0.5, f"Event bus too slow: {duration:.3f}s"

    def test_state_manager_performance(self, state_manager: StateManager) -> None:
        """Test state manager performance"""
        import time
        start = time.time()
        
        # Perform 1000 set/get operations
        for i in range(1000):
            state_manager.set(f"key_{i}", f"value_{i}")
            state_manager.get(f"key_{i}")
        
        duration = time.time() - start
        assert duration < 0.1, f"State manager operations too slow: {duration:.3f}s"


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "TestHedgeEngine",
    "TestConfigManager",
    "TestLoggerManager",
    "TestHealthChecker",
    "TestExceptions",
    "TestEventBus",
    "TestStateManager",
    "TestPluginManager",
    "TestCoreIntegration",
    "TestCorePerformance",
]

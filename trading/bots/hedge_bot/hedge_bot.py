# trading/bots/hedge_bot/hedge_bot.py
# NEXUS AI TRADING SYSTEM - Main Hedge Bot Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot - Main Module

This is the main entry point for the NEXUS Hedge Bot system. It orchestrates
all components including strategy execution, risk management, portfolio
management, and trading execution.

The hedge bot provides:
- Automated hedging strategies
- Real-time risk management
- Portfolio optimization
- Multi-asset support
- Multi-exchange support
- AI/ML-powered predictions
- Advanced order execution
- Comprehensive monitoring
- Performance analytics
"""

import os
import sys
import json
import time
import asyncio
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field

# Import internal modules
from .core.config import ConfigManager
from .core.logging import LoggerManager
from .core.engine import HedgeEngine
from .core.events import EventBus, Event, EventType
from .core.state import StateManager
from .core.health import HealthChecker
from .core.exceptions import HedgeBotError, ConfigurationError

from .strategies.delta_hedge import DeltaHedgingStrategy
from .strategies.gamma_hedge import GammaHedgingStrategy
from .strategies.vega_hedge import VegaHedgingStrategy
from .strategies.cross_hedge import CrossHedgingStrategy
from .strategies.basis_hedge import BasisHedgingStrategy
from .strategies.trend import TrendFollowingStrategy
from .strategies.mean_reversion import MeanReversionStrategy
from .strategies.momentum import MomentumStrategy
from .strategies.arbitrage import ArbitrageStrategy

from .risk.risk_manager import RiskManager
from .risk.var import ValueAtRisk
from .risk.drawdown import DrawdownController
from .risk.position_sizer import PositionSizer
from .risk.limits import RiskLimits

from .execution.execution_engine import ExecutionEngine
from .portfolio.portfolio_manager import PortfolioManager
from .data.market_data import MarketDataProvider
from .data.sentiment import SentimentAnalyzer
from .ai.predictor import MarketPredictor
from .ai.model import EnsembleModel

from .monitoring.metrics import MetricsCollector
from .monitoring.alerts import AlertManager
from .monitoring.performance import PerformanceMonitor
from .monitoring.dashboard import DashboardGenerator

from .api.main import app
from .websocket.manager import WebSocketManager
from .database.manager import DatabaseManager
from .cache.manager import CacheManager

logger = logging.getLogger(__name__)


# ============================================================
# HEDGE BOT DATACLASSES
# ============================================================

@dataclass
class HedgeBotConfig:
    """Hedge bot configuration"""
    bot_id: str = "nexus_hedge_bot"
    name: str = "NEXUS Hedge Bot"
    version: str = "2.0.0"
    environment: str = "development"
    enabled: bool = True
    active: bool = True
    debug_mode: bool = False
    log_level: str = "INFO"
    
    # Component flags
    enable_strategies: bool = True
    enable_risk: bool = True
    enable_execution: bool = True
    enable_portfolio: bool = True
    enable_market_data: bool = True
    enable_ai: bool = True
    enable_monitoring: bool = True
    enable_api: bool = True
    enable_websocket: bool = True
    enable_database: bool = True
    enable_cache: bool = True
    
    # Strategy configuration
    active_strategies: List[str] = field(default_factory=lambda: ["delta_hedging"])
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    
    # Risk configuration
    max_drawdown: float = 0.15
    daily_loss_limit: float = 0.05
    max_leverage: float = 3.0
    max_position_size: float = 10000.0
    
    # Trading configuration
    max_orders_per_second: int = 10
    max_positions: int = 20
    default_slippage: float = 0.001
    
    # Data configuration
    market_data_provider: str = "exchange"
    update_interval: int = 5  # seconds
    
    # AI configuration
    ai_model_type: str = "ensemble"
    ai_prediction_horizon: int = 60  # minutes
    
    # Monitoring configuration
    metrics_interval: int = 60  # seconds
    alert_channels: List[str] = field(default_factory=lambda: ["console"])


# ============================================================
# HEDGE BOT MAIN CLASS
# ============================================================

class HedgeBot:
    """
    Main Hedge Bot class orchestrating all components
    """
    
    def __init__(self, config: Optional[Union[Dict[str, Any], HedgeBotConfig]] = None):
        """
        Initialize the Hedge Bot
        
        Args:
            config: Configuration dictionary or HedgeBotConfig object
        """
        # Load configuration
        if isinstance(config, dict):
            self.config = HedgeBotConfig(**config)
        elif isinstance(config, HedgeBotConfig):
            self.config = config
        else:
            self.config = HedgeBotConfig()
        
        # Initialize state
        self.is_initialized = False
        self.is_running = False
        self.status = "initializing"
        self.start_time = None
        self.error_count = 0
        self.last_error = None
        
        # Initialize components
        self.components: Dict[str, Any] = {}
        self.strategies: Dict[str, Any] = {}
        
        # Initialize logging
        self._setup_logging()
        
        # Initialize core components
        self._init_core_components()
        
        # Initialize feature components
        self._init_feature_components()
        
        # Set up event handlers
        self._setup_event_handlers()
        
        logger.info(f"Hedge Bot initialized: {self.config.name} v{self.config.version}")
        self.status = "initialized"
    
    # ============================================================
    # INITIALIZATION METHODS
    # ============================================================
    
    def _setup_logging(self) -> None:
        """Setup logging configuration"""
        self.logger_manager = LoggerManager()
        self.logger_manager.set_log_level(self.config.log_level)
        
        if self.config.debug_mode:
            self.logger_manager.set_log_level("DEBUG")
    
    def _init_core_components(self) -> None:
        """Initialize core components"""
        # Config Manager
        self.config_manager = ConfigManager()
        self.components["config_manager"] = self.config_manager
        
        # State Manager
        self.state_manager = StateManager()
        self.components["state_manager"] = self.state_manager
        
        # Event Bus
        self.event_bus = EventBus()
        self.components["event_bus"] = self.event_bus
        
        # Health Checker
        self.health_checker = HealthChecker()
        self.components["health_checker"] = self.health_checker
        
        # Hedge Engine
        self.engine = HedgeEngine({
            "config": self.config,
            "event_bus": self.event_bus,
            "state_manager": self.state_manager,
        })
        self.components["engine"] = self.engine
        
        logger.debug("Core components initialized")
    
    def _init_feature_components(self) -> None:
        """Initialize feature components"""
        # Database Manager
        if self.config.enable_database:
            self.database_manager = DatabaseManager()
            self.components["database_manager"] = self.database_manager
        
        # Cache Manager
        if self.config.enable_cache:
            self.cache_manager = CacheManager()
            self.components["cache_manager"] = self.cache_manager
        
        # Market Data Provider
        if self.config.enable_market_data:
            self.market_data = MarketDataProvider({
                "provider": self.config.market_data_provider,
                "update_interval": self.config.update_interval,
            })
            self.components["market_data"] = self.market_data
        
        # Sentiment Analyzer
        if self.config.enable_market_data:
            self.sentiment_analyzer = SentimentAnalyzer()
            self.components["sentiment_analyzer"] = self.sentiment_analyzer
        
        # Market Predictor
        if self.config.enable_ai:
            self.ai_predictor = MarketPredictor({
                "model_type": self.config.ai_model_type,
                "prediction_horizon": self.config.ai_prediction_horizon,
            })
            self.components["ai_predictor"] = self.ai_predictor
        
        # Risk Manager
        if self.config.enable_risk:
            self.risk_manager = RiskManager({
                "max_drawdown": self.config.max_drawdown,
                "daily_loss_limit": self.config.daily_loss_limit,
                "max_leverage": self.config.max_leverage,
                "max_position_size": self.config.max_position_size,
            })
            self.components["risk_manager"] = self.risk_manager
        
        # Portfolio Manager
        if self.config.enable_portfolio:
            self.portfolio_manager = PortfolioManager()
            self.components["portfolio_manager"] = self.portfolio_manager
        
        # Execution Engine
        if self.config.enable_execution:
            self.execution_engine = ExecutionEngine({
                "max_orders_per_second": self.config.max_orders_per_second,
                "default_slippage": self.config.default_slippage,
            })
            self.components["execution_engine"] = self.execution_engine
        
        # Strategies
        if self.config.enable_strategies:
            self._init_strategies()
        
        # Monitoring
        if self.config.enable_monitoring:
            self.metrics_collector = MetricsCollector()
            self.components["metrics_collector"] = self.metrics_collector
            
            self.alert_manager = AlertManager({
                "channels": self.config.alert_channels,
            })
            self.components["alert_manager"] = self.alert_manager
            
            self.performance_monitor = PerformanceMonitor()
            self.components["performance_monitor"] = self.performance_monitor
            
            self.dashboard_generator = DashboardGenerator()
            self.components["dashboard_generator"] = self.dashboard_generator
        
        # WebSocket Manager
        if self.config.enable_websocket:
            self.websocket_manager = WebSocketManager()
            self.components["websocket_manager"] = self.websocket_manager
        
        logger.debug("Feature components initialized")
    
    def _init_strategies(self) -> None:
        """Initialize trading strategies"""
        strategy_map = {
            "delta_hedging": DeltaHedgingStrategy,
            "gamma_hedging": GammaHedgingStrategy,
            "vega_hedging": VegaHedgingStrategy,
            "cross_hedging": CrossHedgingStrategy,
            "basis_hedging": BasisHedgingStrategy,
            "trend_following": TrendFollowingStrategy,
            "mean_reversion": MeanReversionStrategy,
            "momentum": MomentumStrategy,
            "arbitrage": ArbitrageStrategy,
        }
        
        for strategy_name in self.config.active_strategies:
            if strategy_name in strategy_map:
                params = self.config.strategy_params.get(strategy_name, {})
                strategy_class = strategy_map[strategy_name]
                strategy = strategy_class(params)
                self.strategies[strategy_name] = strategy
                logger.debug(f"Initialized strategy: {strategy_name}")
            else:
                logger.warning(f"Unknown strategy: {strategy_name}")
        
        self.components["strategies"] = self.strategies
    
    def _setup_event_handlers(self) -> None:
        """Setup event handlers"""
        # Handle configuration changes
        self.event_bus.subscribe(EventType.CONFIG_CHANGED, self._handle_config_change)
        
        # Handle strategy events
        self.event_bus.subscribe(EventType.STRATEGY_SIGNAL, self._handle_strategy_signal)
        self.event_bus.subscribe(EventType.STRATEGY_EXECUTED, self._handle_strategy_executed)
        
        # Handle risk events
        self.event_bus.subscribe(EventType.RISK_BREACH, self._handle_risk_breach)
        self.event_bus.subscribe(EventType.RISK_LIMIT, self._handle_risk_limit)
        
        # Handle execution events
        self.event_bus.subscribe(EventType.ORDER_PLACED, self._handle_order_placed)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._handle_order_filled)
        self.event_bus.subscribe(EventType.ORDER_CANCELLED, self._handle_order_cancelled)
        
        # Handle portfolio events
        self.event_bus.subscribe(EventType.PORTFOLIO_UPDATED, self._handle_portfolio_update)
        self.event_bus.subscribe(EventType.POSITION_OPENED, self._handle_position_opened)
        self.event_bus.subscribe(EventType.POSITION_CLOSED, self._handle_position_closed)
        
        # Handle data events
        self.event_bus.subscribe(EventType.MARKET_DATA_UPDATE, self._handle_market_data_update)
        self.event_bus.subscribe(EventType.PREDICTION_UPDATE, self._handle_prediction_update)
        
        # Handle system events
        self.event_bus.subscribe(EventType.SYSTEM_ERROR, self._handle_system_error)
        self.event_bus.subscribe(EventType.SYSTEM_WARNING, self._handle_system_warning)
        
        logger.debug("Event handlers setup complete")
    
    # ============================================================
    # EVENT HANDLERS
    # ============================================================
    
    def _handle_config_change(self, event: Event) -> None:
        """Handle configuration change event"""
        logger.info(f"Configuration changed: {event.data}")
        self.reload_config()
    
    def _handle_strategy_signal(self, event: Event) -> None:
        """Handle strategy signal event"""
        logger.debug(f"Strategy signal: {event.data}")
        # Process signal
        signal = event.data
        self._process_signal(signal)
    
    def _handle_strategy_executed(self, event: Event) -> None:
        """Handle strategy execution event"""
        logger.info(f"Strategy executed: {event.data}")
    
    def _handle_risk_breach(self, event: Event) -> None:
        """Handle risk breach event"""
        logger.warning(f"Risk breach: {event.data}")
        self._handle_risk_event(event.data)
    
    def _handle_risk_limit(self, event: Event) -> None:
        """Handle risk limit event"""
        logger.info(f"Risk limit: {event.data}")
    
    def _handle_order_placed(self, event: Event) -> None:
        """Handle order placed event"""
        logger.info(f"Order placed: {event.data}")
    
    def _handle_order_filled(self, event: Event) -> None:
        """Handle order filled event"""
        logger.info(f"Order filled: {event.data}")
        # Update portfolio
        self._update_portfolio_after_fill(event.data)
    
    def _handle_order_cancelled(self, event: Event) -> None:
        """Handle order cancelled event"""
        logger.info(f"Order cancelled: {event.data}")
    
    def _handle_portfolio_update(self, event: Event) -> None:
        """Handle portfolio update event"""
        logger.debug(f"Portfolio updated: {event.data}")
    
    def _handle_position_opened(self, event: Event) -> None:
        """Handle position opened event"""
        logger.info(f"Position opened: {event.data}")
    
    def _handle_position_closed(self, event: Event) -> None:
        """Handle position closed event"""
        logger.info(f"Position closed: {event.data}")
    
    def _handle_market_data_update(self, event: Event) -> None:
        """Handle market data update event"""
        logger.debug(f"Market data updated: {event.data}")
    
    def _handle_prediction_update(self, event: Event) -> None:
        """Handle prediction update event"""
        logger.debug(f"Prediction updated: {event.data}")
    
    def _handle_system_error(self, event: Event) -> None:
        """Handle system error event"""
        logger.error(f"System error: {event.data}")
        self.error_count += 1
        self.last_error = event.data
    
    def _handle_system_warning(self, event: Event) -> None:
        """Handle system warning event"""
        logger.warning(f"System warning: {event.data}")
    
    # ============================================================
    # CORE OPERATIONS
    # ============================================================
    
    def start(self) -> None:
        """
        Start the hedge bot (synchronous)
        """
        if self.is_running:
            logger.warning("Hedge bot is already running")
            return
        
        logger.info("Starting hedge bot...")
        
        try:
            # Initialize all components
            self._initialize_components()
            
            # Start all components
            self._start_components()
            
            self.is_running = True
            self.status = "running"
            self.start_time = datetime.now()
            
            logger.info(f"Hedge bot started successfully at {self.start_time}")
            self.event_bus.emit(Event(EventType.SYSTEM_STARTED, {
                "start_time": self.start_time,
                "status": self.status,
            }))
            
        except Exception as e:
            logger.error(f"Failed to start hedge bot: {e}")
            self.status = "error"
            self.last_error = str(e)
            raise HedgeBotError(f"Start failed: {e}")
    
    def start_async(self) -> None:
        """
        Start the hedge bot (asynchronous)
        
        This method runs the bot in a separate thread or event loop.
        """
        import threading
        thread = threading.Thread(target=self.start)
        thread.daemon = True
        thread.start()
    
    async def start_async_await(self) -> None:
        """
        Start the hedge bot using asyncio
        
        This method runs the bot in an async context.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.start)
    
    def stop(self) -> None:
        """
        Stop the hedge bot (synchronous)
        """
        if not self.is_running:
            logger.warning("Hedge bot is not running")
            return
        
        logger.info("Stopping hedge bot...")
        
        try:
            # Stop all components
            self._stop_components()
            
            self.is_running = False
            self.status = "stopped"
            
            elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            logger.info(f"Hedge bot stopped. Elapsed time: {elapsed:.2f}s")
            
            self.event_bus.emit(Event(EventType.SYSTEM_STOPPED, {
                "stop_time": datetime.now(),
                "elapsed": elapsed,
            }))
            
        except Exception as e:
            logger.error(f"Failed to stop hedge bot: {e}")
            self.status = "error"
            self.last_error = str(e)
            raise HedgeBotError(f"Stop failed: {e}")
    
    async def stop_async(self) -> None:
        """
        Stop the hedge bot (asynchronous)
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.stop)
    
    def reload(self) -> None:
        """
        Reload the hedge bot configuration
        """
        logger.info("Reloading hedge bot...")
        
        try:
            # Stop components
            self._stop_components()
            
            # Reload configuration
            self.reload_config()
            
            # Re-initialize components
            self._initialize_components()
            
            # Start components
            if self.is_running:
                self._start_components()
            
            logger.info("Hedge bot reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload hedge bot: {e}")
            raise HedgeBotError(f"Reload failed: {e}")
    
    def reload_config(self) -> None:
        """
        Reload configuration from file
        """
        logger.info("Reloading configuration...")
        
        try:
            # Reload from config manager
            self.config_manager.load()
            
            # Update config
            new_config = self.config_manager.get_config()
            if new_config:
                self.config = HedgeBotConfig(**new_config)
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            raise ConfigurationError(f"Config reload failed: {e}")
    
    # ============================================================
    # COMPONENT MANAGEMENT
    # ============================================================
    
    def _initialize_components(self) -> None:
        """Initialize all components"""
        for name, component in self.components.items():
            if hasattr(component, 'initialize'):
                try:
                    component.initialize()
                    logger.debug(f"Initialized component: {name}")
                except Exception as e:
                    logger.error(f"Failed to initialize component {name}: {e}")
                    raise
    
    def _start_components(self) -> None:
        """Start all components"""
        for name, component in self.components.items():
            if hasattr(component, 'start'):
                try:
                    component.start()
                    logger.debug(f"Started component: {name}")
                except Exception as e:
                    logger.error(f"Failed to start component {name}: {e}")
                    raise
    
    def _stop_components(self) -> None:
        """Stop all components"""
        for name, component in self.components.items():
            if hasattr(component, 'stop'):
                try:
                    component.stop()
                    logger.debug(f"Stopped component: {name}")
                except Exception as e:
                    logger.error(f"Failed to stop component {name}: {e}")
    
    def get_component(self, name: str) -> Optional[Any]:
        """
        Get a component by name
        
        Args:
            name: Component name
            
        Returns:
            Component instance or None
        """
        return self.components.get(name)
    
    def get_strategy(self, name: str) -> Optional[Any]:
        """
        Get a strategy by name
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy instance or None
        """
        return self.strategies.get(name)
    
    # ============================================================
    # BUSINESS LOGIC
    # ============================================================
    
    def _process_signal(self, signal: Dict[str, Any]) -> None:
        """
        Process a trading signal
        
        Args:
            signal: Signal dictionary
        """
        if not self.is_running:
            logger.warning("Cannot process signal: bot is not running")
            return
        
        try:
            # Validate signal
            if not self._validate_signal(signal):
                return
            
            # Check risk
            if not self._check_risk_limits(signal):
                return
            
            # Execute signal
            self._execute_signal(signal)
            
        except Exception as e:
            logger.error(f"Failed to process signal: {e}")
            self.event_bus.emit(Event(EventType.SYSTEM_ERROR, {
                "error": str(e),
                "signal": signal,
            }))
    
    def _validate_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Validate a trading signal
        
        Args:
            signal: Signal dictionary
            
        Returns:
            True if valid
        """
        required_fields = ["symbol", "action", "quantity"]
        
        for field in required_fields:
            if field not in signal:
                logger.warning(f"Signal missing required field: {field}")
                return False
        
        # Validate action
        if signal["action"] not in ["buy", "sell", "hold"]:
            logger.warning(f"Invalid action: {signal['action']}")
            return False
        
        # Validate quantity
        if signal["quantity"] <= 0:
            logger.warning(f"Invalid quantity: {signal['quantity']}")
            return False
        
        return True
    
    def _check_risk_limits(self, signal: Dict[str, Any]) -> bool:
        """
        Check risk limits for a signal
        
        Args:
            signal: Signal dictionary
            
        Returns:
            True if within limits
        """
        if not self.config.enable_risk:
            return True
        
        try:
            # Check position limits
            if not self.risk_manager.check_position_limit(signal):
                logger.warning("Position limit exceeded")
                return False
            
            # Check drawdown limit
            if self.risk_manager.check_drawdown_limit():
                logger.warning("Drawdown limit exceeded")
                return False
            
            # Check daily loss limit
            if self.risk_manager.check_daily_loss_limit():
                logger.warning("Daily loss limit exceeded")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Risk check failed: {e}")
            return False
    
    def _execute_signal(self, signal: Dict[str, Any]) -> None:
        """
        Execute a trading signal
        
        Args:
            signal: Signal dictionary
        """
        if signal["action"] == "hold":
            return
        
        try:
            # Get market data
            market_data = self.market_data.get_price(signal["symbol"])
            
            # Determine order price
            price = market_data.get("ask") if signal["action"] == "buy" else market_data.get("bid")
            
            # Place order
            order = self.execution_engine.place_order({
                "symbol": signal["symbol"],
                "side": signal["action"],
                "quantity": signal["quantity"],
                "price": price,
                "time_in_force": signal.get("time_in_force", "GTC"),
            })
            
            logger.info(f"Executed signal: {signal['action']} {signal['quantity']} {signal['symbol']}")
            
        except Exception as e:
            logger.error(f"Failed to execute signal: {e}")
            raise
    
    def _update_portfolio_after_fill(self, order: Dict[str, Any]) -> None:
        """
        Update portfolio after order fill
        
        Args:
            order: Filled order
        """
        try:
            # Update position
            self.portfolio_manager.update_position(order)
            
            # Update portfolio metrics
            self.portfolio_manager.update_metrics()
            
            # Emit portfolio update event
            self.event_bus.emit(Event(EventType.PORTFOLIO_UPDATED, {
                "order": order,
                "portfolio": self.portfolio_manager.get_summary(),
            }))
            
        except Exception as e:
            logger.error(f"Failed to update portfolio: {e}")
    
    def _handle_risk_event(self, event_data: Dict[str, Any]) -> None:
        """
        Handle a risk event
        
        Args:
            event_data: Risk event data
        """
        action = event_data.get("action", "alert")
        
        if action == "reduce_position":
            self._reduce_positions()
        elif action == "close_position":
            self._close_positions()
        elif action == "stop_trading":
            self._stop_trading()
        elif action == "alert":
            self._send_alert(event_data)
    
    def _reduce_positions(self) -> None:
        """Reduce all positions by 50%"""
        try:
            positions = self.portfolio_manager.get_positions()
            for position in positions:
                reduce_quantity = position["quantity"] * 0.5
                self.execution_engine.place_order({
                    "symbol": position["symbol"],
                    "side": "sell" if position["side"] == "long" else "buy",
                    "quantity": reduce_quantity,
                    "time_in_force": "IOC",
                })
            logger.info("Positions reduced by 50%")
            
        except Exception as e:
            logger.error(f"Failed to reduce positions: {e}")
    
    def _close_positions(self) -> None:
        """Close all positions"""
        try:
            positions = self.portfolio_manager.get_positions()
            for position in positions:
                self.execution_engine.place_order({
                    "symbol": position["symbol"],
                    "side": "sell" if position["side"] == "long" else "buy",
                    "quantity": position["quantity"],
                    "time_in_force": "IOC",
                })
            logger.info("All positions closed")
            
        except Exception as e:
            logger.error(f"Failed to close positions: {e}")
    
    def _stop_trading(self) -> None:
        """Stop all trading activity"""
        try:
            self.is_running = False
            self.status = "paused"
            logger.warning("Trading stopped due to risk event")
            
        except Exception as e:
            logger.error(f"Failed to stop trading: {e}")
    
    def _send_alert(self, event_data: Dict[str, Any]) -> None:
        """
        Send an alert
        
        Args:
            event_data: Alert data
        """
        try:
            self.alert_manager.send_alert(
                severity=event_data.get("severity", "warning"),
                message=event_data.get("message", "Risk event occurred"),
                data=event_data,
            )
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    # ============================================================
    # STATUS AND HEALTH
    # ============================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get bot status
        
        Returns:
            Status dictionary
        """
        return {
            "status": self.status,
            "is_running": self.is_running,
            "is_initialized": self.is_initialized,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "components": {name: self._get_component_status(name) for name in self.components.keys()},
            "strategies": {name: self._get_strategy_status(name) for name in self.strategies.keys()},
        }
    
    def _get_component_status(self, name: str) -> Dict[str, Any]:
        """Get component status"""
        component = self.components.get(name)
        if hasattr(component, 'get_status'):
            return component.get_status()
        return {"status": "active" if self.is_running else "inactive"}
    
    def _get_strategy_status(self, name: str) -> Dict[str, Any]:
        """Get strategy status"""
        strategy = self.strategies.get(name)
        if hasattr(strategy, 'get_status'):
            return strategy.get_status()
        return {"status": "active" if self.is_running else "inactive"}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check
        
        Returns:
            Health status dictionary
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {},
        }
        
        # Check each component
        for name, component in self.components.items():
            if hasattr(component, 'health_check'):
                try:
                    health["components"][name] = component.health_check()
                except Exception as e:
                    health["components"][name] = {"status": "unhealthy", "error": str(e)}
                    health["status"] = "degraded"
        
        # Overall status
        if health["status"] == "healthy" and not self.is_running:
            health["status"] = "stopped"
        elif health["status"] == "healthy" and self.is_running:
            health["status"] = "running"
        
        return health
    
    # ============================================================
    # METRICS AND PERFORMANCE
    # ============================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get bot metrics
        
        Returns:
            Metrics dictionary
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "status": self.status,
            "uptime": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
        }
        
        # Add component metrics
        for name, component in self.components.items():
            if hasattr(component, 'get_metrics'):
                try:
                    metrics[name] = component.get_metrics()
                except Exception as e:
                    metrics[name] = {"error": str(e)}
        
        return metrics
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get performance report
        
        Returns:
            Performance report dictionary
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "bot": {
                "name": self.config.name,
                "version": self.config.version,
                "uptime": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            },
            "performance": {},
        }
        
        # Add portfolio performance
        if self.portfolio_manager:
            report["performance"]["portfolio"] = self.portfolio_manager.get_performance()
        
        # Add strategy performance
        if self.strategies:
            report["performance"]["strategies"] = {}
            for name, strategy in self.strategies.items():
                if hasattr(strategy, 'get_performance'):
                    report["performance"]["strategies"][name] = strategy.get_performance()
        
        return report
    
    # ============================================================
    # DASHBOARD
    # ============================================================
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get dashboard data
        
        Returns:
            Dashboard data dictionary
        """
        return {
            "status": self.get_status(),
            "metrics": self.get_metrics(),
            "portfolio": self.portfolio_manager.get_summary() if self.portfolio_manager else {},
            "positions": self.portfolio_manager.get_positions() if self.portfolio_manager else [],
            "orders": self.execution_engine.get_orders() if self.execution_engine else [],
            "strategies": {
                name: strategy.get_status() if hasattr(strategy, 'get_status') else {}
                for name, strategy in self.strategies.items()
            },
            "risk": self.risk_manager.get_summary() if self.risk_manager else {},
        }


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_hedge_bot(config: Optional[Dict[str, Any]] = None) -> HedgeBot:
    """
    Create a new Hedge Bot instance
    
    Args:
        config: Configuration dictionary
        
    Returns:
        HedgeBot instance
    """
    return HedgeBot(config)


def create_default_hedge_bot() -> HedgeBot:
    """
    Create a Hedge Bot with default configuration
    
    Returns:
        HedgeBot instance
    """
    return HedgeBot()


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    # This allows the bot to be run directly
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Hedge Bot")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")
    parser.add_argument("--env", "-e", default="development", help="Environment")
    
    args = parser.parse_args()
    
    # Load configuration
    config = {
        "environment": args.env,
        "debug_mode": args.debug,
    }
    
    if args.config:
        with open(args.config, "r") as f:
            file_config = json.load(f)
            config.update(file_config)
    
    # Create and start bot
    bot = create_hedge_bot(config)
    bot.start()
    
    try:
        # Keep running until interrupted
        while bot.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        bot.stop()


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "HedgeBot",
    "HedgeBotConfig",
    "create_hedge_bot",
    "create_default_hedge_bot",
]

# ============================================================
# END OF MODULE
# ============================================================

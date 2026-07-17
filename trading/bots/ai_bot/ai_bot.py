# trading/bots/ai_bot/ai_bot.py
"""
NEXUS AI TRADING SYSTEM - Core AI Bot Implementation
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements the core AI trading bot functionality including:
    - Bot lifecycle management (start, stop, pause, resume)
    - Market data processing and analysis
    - Signal generation from AI models
    - Trade execution and order management
    - Risk management and position sizing
    - Performance monitoring and metrics
    - Strategy management and selection
    - Model management and inference
    - Data pipeline integration
    - Error handling and recovery

Architecture Overview:
    The AI Bot follows a modular microservices architecture with the following
    core components:
    
    1. Data Pipeline: Ingests and processes market data
    2. Feature Engine: Extracts and engineers features
    3. Model Manager: Handles AI model inference
    4. Strategy Engine: Implements trading strategies
    5. Signal Generator: Creates trading signals
    6. Risk Manager: Manages position risk
    7. Execution Engine: Executes trades
    8. Performance Tracker: Monitors bot performance
    9. Alert System: Manages notifications
    10. Health Checker: Monitors system health
"""

import os
import sys
import json
import yaml
import asyncio
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from enum import Enum
import numpy as np
import pandas as pd
import torch

# Import bot components
from trading.bots.ai_bot.config import BotConfig
from trading.bots.ai_bot.data_pipeline import DataPipeline
from trading.bots.ai_bot.feature_engine import FeatureEngine
from trading.bots.ai_bot.model_manager import ModelManager
from trading.bots.ai_bot.strategy_engine import StrategyEngine
from trading.bots.ai_bot.signal_generator import SignalGenerator
from trading.bots.ai_bot.risk_manager import RiskManager
from trading.bots.ai_bot.execution_engine import ExecutionEngine
from trading.bots.ai_bot.position_manager import PositionManager
from trading.bots.ai_bot.performance_tracker import PerformanceTracker
from trading.bots.ai_bot.alert_manager import AlertManager
from trading.bots.ai_bot.health_checker import HealthChecker
from trading.bots.ai_bot.metrics_collector import MetricsCollector

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class BotStatus(Enum):
    """Bot status enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    STOPPING = "stopping"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class BotMode(Enum):
    """Bot operation mode."""
    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"
    SIMULATION = "simulation"
    DEMO = "demo"


class BotConfig:
    """Bot configuration container."""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self.raw_config = config_dict
        self.mode = BotMode(config_dict.get('mode', 'paper'))
        self.name = config_dict.get('name', 'NEXUS AI Bot')
        self.version = config_dict.get('version', '3.0.0')
        self.enabled = config_dict.get('enabled', True)
        self.symbols = config_dict.get('symbols', ['BTC-USD', 'ETH-USD'])
        self.timeframes = config_dict.get('timeframes', ['1h', '4h', '1d'])
        self.initial_capital = config_dict.get('initial_capital', 100000.0)
        self.max_positions = config_dict.get('max_positions', 5)
        self.max_risk_per_trade = config_dict.get('max_risk_per_trade', 0.02)
        self.stop_loss = config_dict.get('stop_loss', 0.02)
        self.take_profit = config_dict.get('take_profit', 0.04)
        self.risk_reward_ratio = config_dict.get('risk_reward_ratio', 2.0)
        self.model_config = config_dict.get('model', {})
        self.strategy_config = config_dict.get('strategy', {})
        self.risk_config = config_dict.get('risk', {})
        self.execution_config = config_dict.get('execution', {})
        self.data_config = config_dict.get('data', {})
        self.monitoring_config = config_dict.get('monitoring', {})
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'mode': self.mode.value,
            'name': self.name,
            'version': self.version,
            'enabled': self.enabled,
            'symbols': self.symbols,
            'timeframes': self.timeframes,
            'initial_capital': self.initial_capital,
            'max_positions': self.max_positions,
            'max_risk_per_trade': self.max_risk_per_trade,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'risk_reward_ratio': self.risk_reward_ratio,
            'model_config': self.model_config,
            'strategy_config': self.strategy_config,
            'risk_config': self.risk_config,
            'execution_config': self.execution_config,
            'data_config': self.data_config,
            'monitoring_config': self.monitoring_config
        }


# =============================================================================
# AI Bot Core Class
# =============================================================================

class AIBot:
    """
    Core AI Trading Bot Implementation.
    
    The AIBot class orchestrates all components of the trading system:
        - Data ingestion and processing
        - Feature engineering
        - AI model inference
        - Strategy execution
        - Signal generation
        - Risk management
        - Order execution
        - Performance tracking
        - Alert management
        - Health monitoring
    
    Usage:
        # Initialize bot with configuration
        config = {
            'name': 'NEXUS AI Bot',
            'mode': 'paper',
            'symbols': ['BTC-USD', 'ETH-USD'],
            'initial_capital': 100000.0
        }
        bot = AIBot(config)
        
        # Start the bot
        await bot.start()
        
        # Run trading cycle
        await bot.trade_cycle()
        
        # Stop the bot
        await bot.stop()
    """
    
    # =========================================================================
    # Initialization
    # =========================================================================
    
    def __init__(
        self,
        config: Union[Dict[str, Any], BotConfig],
        auto_start: bool = False
    ):
        """
        Initialize the AI Trading Bot.
        
        Args:
            config: Bot configuration dictionary or BotConfig instance
            auto_start: Automatically start the bot on initialization
        """
        # Initialize configuration
        if isinstance(config, dict):
            self.config = BotConfig(config)
        elif isinstance(config, BotConfig):
            self.config = config
        else:
            raise ValueError("config must be dict or BotConfig")
        
        # Set core attributes
        self.bot_id = f"NEXUS_BOT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.status = BotStatus.STOPPED
        self.mode = self.config.mode
        self.created_at = datetime.now()
        self.started_at = None
        self.stopped_at = None
        
        # Initialize components
        self.components = {}
        self._initialize_components()
        
        # Set up event loop
        self.loop = asyncio.get_event_loop()
        self.tasks = []
        self.running = False
        
        # Performance tracking
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'total_volume': 0.0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0,
            'profit_factor': 0.0
        }
        
        # Trade history
        self.trade_history = []
        self.order_history = []
        
        # Alert queue
        self.alerts = []
        self.alert_handlers = []
        
        # Health status
        self.health_status = {
            'overall': 'unknown',
            'components': {},
            'last_check': None,
            'errors': []
        }
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.{self.bot_id}")
        self.logger.info(f"Initialized AI Bot: {self.bot_id}")
        self.logger.info(f"Mode: {self.mode.value}")
        self.logger.info(f"Symbols: {self.config.symbols}")
        
        # Auto-start if requested
        if auto_start:
            self.loop.run_until_complete(self.start())
    
    # =========================================================================
    # Component Initialization
    # =========================================================================
    
    def _initialize_components(self) -> None:
        """Initialize all bot components."""
        self.logger.info("Initializing bot components...")
        
        try:
            # Initialize data pipeline
            self.components['data_pipeline'] = DataPipeline(self.config)
            self.logger.debug("Data pipeline initialized")
            
            # Initialize feature engine
            self.components['feature_engine'] = FeatureEngine(self.config)
            self.logger.debug("Feature engine initialized")
            
            # Initialize model manager
            self.components['model_manager'] = ModelManager(self.config)
            self.logger.debug("Model manager initialized")
            
            # Initialize strategy engine
            self.components['strategy_engine'] = StrategyEngine(self.config)
            self.logger.debug("Strategy engine initialized")
            
            # Initialize signal generator
            self.components['signal_generator'] = SignalGenerator(self.config)
            self.logger.debug("Signal generator initialized")
            
            # Initialize risk manager
            self.components['risk_manager'] = RiskManager(self.config)
            self.logger.debug("Risk manager initialized")
            
            # Initialize execution engine
            self.components['execution_engine'] = ExecutionEngine(self.config)
            self.logger.debug("Execution engine initialized")
            
            # Initialize position manager
            self.components['position_manager'] = PositionManager(self.config)
            self.logger.debug("Position manager initialized")
            
            # Initialize performance tracker
            self.components['performance_tracker'] = PerformanceTracker(self.config)
            self.logger.debug("Performance tracker initialized")
            
            # Initialize alert manager
            self.components['alert_manager'] = AlertManager(self.config)
            self.logger.debug("Alert manager initialized")
            
            # Initialize health checker
            self.components['health_checker'] = HealthChecker(self.config)
            self.logger.debug("Health checker initialized")
            
            # Initialize metrics collector
            self.components['metrics_collector'] = MetricsCollector(self.config)
            self.logger.debug("Metrics collector initialized")
            
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
    
    def get_component(self, name: str) -> Any:
        """
        Get a component by name.
        
        Args:
            name: Component name
            
        Returns:
            Component instance
        """
        return self.components.get(name)
    
    # =========================================================================
    # Lifecycle Management
    # =========================================================================
    
    async def start(self) -> bool:
        """
        Start the AI trading bot.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.status == BotStatus.RUNNING:
            self.logger.warning("Bot is already running")
            return True
        
        self.logger.info("Starting AI Bot...")
        self.status = BotStatus.STARTING
        
        try:
            # Start all components
            for name, component in self.components.items():
                if hasattr(component, 'start'):
                    self.logger.debug(f"Starting component: {name}")
                    await component.start()
            
            # Initialize model
            await self._initialize_model()
            
            # Initialize strategy
            await self._initialize_strategy()
            
            # Update status
            self.status = BotStatus.RUNNING
            self.started_at = datetime.now()
            self.running = True
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Send startup alert
            await self._send_alert({
                'severity': 'info',
                'message': f'Bot {self.bot_id} started successfully',
                'component': 'core'
            })
            
            self.logger.info(f"Bot {self.bot_id} started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start bot: {e}")
            self.status = BotStatus.ERROR
            return False
    
    async def stop(self) -> bool:
        """
        Stop the AI trading bot.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if self.status == BotStatus.STOPPED:
            self.logger.warning("Bot is already stopped")
            return True
        
        self.logger.info("Stopping AI Bot...")
        self.status = BotStatus.STOPPING
        self.running = False
        
        try:
            # Cancel background tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self.tasks:
                await asyncio.gather(*self.tasks, return_exceptions=True)
            
            # Stop all components
            for name, component in self.components.items():
                if hasattr(component, 'stop'):
                    self.logger.debug(f"Stopping component: {name}")
                    await component.stop()
            
            # Update status
            self.status = BotStatus.STOPPED
            self.stopped_at = datetime.now()
            
            # Send stop alert
            await self._send_alert({
                'severity': 'info',
                'message': f'Bot {self.bot_id} stopped',
                'component': 'core'
            })
            
            self.logger.info(f"Bot {self.bot_id} stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop bot: {e}")
            self.status = BotStatus.ERROR
            return False
    
    async def pause(self) -> bool:
        """
        Pause the AI trading bot.
        
        Returns:
            True if paused successfully, False otherwise
        """
        if self.status != BotStatus.RUNNING:
            self.logger.warning("Bot must be running to pause")
            return False
        
        self.logger.info("Pausing AI Bot...")
        self.status = BotStatus.PAUSING
        
        try:
            # Pause all components
            for name, component in self.components.items():
                if hasattr(component, 'pause'):
                    await component.pause()
            
            self.status = BotStatus.PAUSED
            self.logger.info("Bot paused successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to pause bot: {e}")
            self.status = BotStatus.ERROR
            return False
    
    async def resume(self) -> bool:
        """
        Resume the AI trading bot.
        
        Returns:
            True if resumed successfully, False otherwise
        """
        if self.status != BotStatus.PAUSED:
            self.logger.warning("Bot must be paused to resume")
            return False
        
        self.logger.info("Resuming AI Bot...")
        self.status = BotStatus.RESUMING
        
        try:
            # Resume all components
            for name, component in self.components.items():
                if hasattr(component, 'resume'):
                    await component.resume()
            
            self.status = BotStatus.RUNNING
            self.logger.info("Bot resumed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to resume bot: {e}")
            self.status = BotStatus.ERROR
            return False
    
    # =========================================================================
    # Trading Cycle
    # =========================================================================
    
    async def trade_cycle(self) -> Dict[str, Any]:
        """
        Execute one complete trading cycle.
        
        Returns:
            Dictionary with trade cycle results
        """
        if self.status != BotStatus.RUNNING:
            self.logger.warning("Bot is not running, cannot execute trade cycle")
            return {'status': 'error', 'message': 'Bot not running'}
        
        self.logger.debug("Starting trade cycle...")
        results = {
            'timestamp': datetime.now().isoformat(),
            'status': 'success',
            'symbols_processed': 0,
            'signals_generated': 0,
            'trades_executed': 0,
            'errors': []
        }
        
        try:
            # Process each symbol
            for symbol in self.config.symbols:
                try:
                    # 1. Get market data
                    market_data = await self._get_market_data(symbol)
                    if market_data is None:
                        continue
                    
                    # 2. Extract features
                    features = await self._extract_features(market_data)
                    if features is None:
                        continue
                    
                    # 3. Generate prediction
                    prediction = await self._predict(features)
                    if prediction is None:
                        continue
                    
                    # 4. Generate signal
                    signal = await self._generate_signal(prediction, market_data)
                    if signal is None or signal.get('signal') == 'hold':
                        continue
                    
                    results['signals_generated'] += 1
                    
                    # 5. Validate trade
                    is_valid, errors = await self._validate_trade(signal)
                    if not is_valid:
                        results['errors'].extend(errors)
                        continue
                    
                    # 6. Execute trade
                    trade = await self._execute_trade(signal)
                    if trade:
                        results['trades_executed'] += 1
                        await self._update_metrics(trade)
                    
                    results['symbols_processed'] += 1
                    
                except Exception as e:
                    error_msg = f"Error processing {symbol}: {e}"
                    self.logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # Update performance metrics
            await self._update_performance_metrics()
            
            # Check risk limits
            await self._check_risk_limits()
            
            self.logger.debug(f"Trade cycle complete: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"Trade cycle failed: {e}")
            results['status'] = 'error'
            results['message'] = str(e)
            return results
    
    # =========================================================================
    # Component Methods
    # =========================================================================
    
    async def _get_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get market data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Market data DataFrame or None
        """
        try:
            pipeline = self.get_component('data_pipeline')
            if pipeline is None:
                self.logger.error("Data pipeline not available")
                return None
            
            # Get data for all timeframes
            data = {}
            for timeframe in self.config.timeframes:
                df = await pipeline.get_data(symbol, timeframe)
                if df is not None:
                    data[timeframe] = df
            
            return data if data else None
            
        except Exception as e:
            self.logger.error(f"Failed to get market data for {symbol}: {e}")
            return None
    
    async def _extract_features(
        self, 
        market_data: pd.DataFrame
    ) -> Optional[np.ndarray]:
        """
        Extract features from market data.
        
        Args:
            market_data: Market data DataFrame
            
        Returns:
            Feature array or None
        """
        try:
            feature_engine = self.get_component('feature_engine')
            if feature_engine is None:
                self.logger.error("Feature engine not available")
                return None
            
            features = await feature_engine.extract(market_data)
            return features
            
        except Exception as e:
            self.logger.error(f"Failed to extract features: {e}")
            return None
    
    async def _predict(
        self, 
        features: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """
        Generate prediction from features.
        
        Args:
            features: Feature array
            
        Returns:
            Prediction dictionary or None
        """
        try:
            model_manager = self.get_component('model_manager')
            if model_manager is None:
                self.logger.error("Model manager not available")
                return None
            
            prediction = await model_manager.predict(features)
            return prediction
            
        except Exception as e:
            self.logger.error(f"Failed to predict: {e}")
            return None
    
    async def _generate_signal(
        self,
        prediction: Dict[str, Any],
        market_data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal from prediction.
        
        Args:
            prediction: Prediction dictionary
            market_data: Market data DataFrame
            
        Returns:
            Signal dictionary or None
        """
        try:
            signal_gen = self.get_component('signal_generator')
            if signal_gen is None:
                self.logger.error("Signal generator not available")
                return None
            
            signal = await signal_gen.generate(prediction, market_data)
            return signal
            
        except Exception as e:
            self.logger.error(f"Failed to generate signal: {e}")
            return None
    
    async def _validate_trade(
        self,
        signal: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate a trading signal.
        
        Args:
            signal: Trading signal dictionary
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            risk_manager = self.get_component('risk_manager')
            if risk_manager is None:
                self.logger.error("Risk manager not available")
                return False, ['Risk manager not available']
            
            is_valid, errors = await risk_manager.validate(signal)
            return is_valid, errors
            
        except Exception as e:
            self.logger.error(f"Failed to validate trade: {e}")
            return False, [str(e)]
    
    async def _execute_trade(
        self,
        signal: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a trade from signal.
        
        Args:
            signal: Trading signal dictionary
            
        Returns:
            Trade result dictionary or None
        """
        try:
            execution_engine = self.get_component('execution_engine')
            if execution_engine is None:
                self.logger.error("Execution engine not available")
                return None
            
            # Convert signal to order
            order = await execution_engine.signal_to_order(signal)
            if order is None:
                return None
            
            # Place order
            trade_result = await execution_engine.place_order(order)
            return trade_result
            
        except Exception as e:
            self.logger.error(f"Failed to execute trade: {e}")
            return None
    
    async def _update_metrics(self, trade: Dict[str, Any]) -> None:
        """
        Update bot metrics after trade.
        
        Args:
            trade: Trade result dictionary
        """
        try:
            metrics = self.get_component('metrics_collector')
            if metrics is None:
                self.logger.error("Metrics collector not available")
                return
            
            await metrics.record_trade(trade)
            
            # Update local metrics
            self.metrics['total_trades'] += 1
            if trade.get('pnl', 0) > 0:
                self.metrics['winning_trades'] += 1
            else:
                self.metrics['losing_trades'] += 1
            
            self.metrics['total_pnl'] += trade.get('pnl', 0)
            self.metrics['total_volume'] += trade.get('volume', 0)
            
        except Exception as e:
            self.logger.error(f"Failed to update metrics: {e}")
    
    async def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        try:
            tracker = self.get_component('performance_tracker')
            if tracker is None:
                return
            
            performance = await tracker.get_metrics()
            if performance:
                self.metrics.update(performance)
                
        except Exception as e:
            self.logger.error(f"Failed to update performance metrics: {e}")
    
    async def _check_risk_limits(self) -> None:
        """Check risk limits and trigger alerts if needed."""
        try:
            risk_manager = self.get_component('risk_manager')
            if risk_manager is None:
                return
            
            risk_status = await risk_manager.check_limits()
            
            if risk_status.get('warning'):
                await self._send_alert({
                    'severity': 'warning',
                    'message': risk_status['warning'],
                    'component': 'risk_manager'
                })
            
            if risk_status.get('critical'):
                await self._send_alert({
                    'severity': 'critical',
                    'message': risk_status['critical'],
                    'component': 'risk_manager'
                })
                # Pause bot if critical risk
                if risk_status.get('should_pause', False):
                    await self.pause()
                    
        except Exception as e:
            self.logger.error(f"Failed to check risk limits: {e}")
    
    async def _initialize_model(self) -> None:
        """Initialize AI models."""
        try:
            model_manager = self.get_component('model_manager')
            if model_manager is None:
                self.logger.error("Model manager not available")
                return
            
            await model_manager.initialize()
            self.logger.info("Models initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize models: {e}")
            raise
    
    async def _initialize_strategy(self) -> None:
        """Initialize trading strategies."""
        try:
            strategy_engine = self.get_component('strategy_engine')
            if strategy_engine is None:
                self.logger.error("Strategy engine not available")
                return
            
            await strategy_engine.initialize()
            self.logger.info("Strategies initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize strategies: {e}")
            raise
    
    # =========================================================================
    # Background Tasks
    # =========================================================================
    
    async def _start_background_tasks(self) -> None:
        """Start background monitoring and maintenance tasks."""
        self.tasks = [
            asyncio.create_task(self._monitor_health()),
            asyncio.create_task(self._collect_metrics()),
            asyncio.create_task(self._process_alerts()),
            asyncio.create_task(self._update_positions()),
            asyncio.create_task(self._refresh_data())
        ]
        self.logger.info(f"Started {len(self.tasks)} background tasks")
    
    async def _monitor_health(self) -> None:
        """Monitor bot health periodically."""
        while self.running:
            try:
                health_checker = self.get_component('health_checker')
                if health_checker:
                    self.health_status = await health_checker.check_all()
                    
                    if self.health_status.get('overall') == 'unhealthy':
                        await self._send_alert({
                            'severity': 'critical',
                            'message': 'Bot health check failed',
                            'component': 'health_checker',
                            'details': self.health_status
                        })
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _collect_metrics(self) -> None:
        """Collect metrics periodically."""
        while self.running:
            try:
                metrics = self.get_component('metrics_collector')
                if metrics:
                    await metrics.collect()
                    await self._update_performance_metrics()
                
                await asyncio.sleep(60)  # Collect every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(60)
    
    async def _process_alerts(self) -> None:
        """Process alert queue periodically."""
        while self.running:
            try:
                if self.alerts:
                    await self._send_alert(self.alerts.pop(0))
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Alert processing error: {e}")
                await asyncio.sleep(10)
    
    async def _update_positions(self) -> None:
        """Update positions periodically."""
        while self.running:
            try:
                position_manager = self.get_component('position_manager')
                if position_manager:
                    await position_manager.update_all()
                
                await asyncio.sleep(10)  # Update every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Position update error: {e}")
                await asyncio.sleep(30)
    
    async def _refresh_data(self) -> None:
        """Refresh market data periodically."""
        while self.running:
            try:
                data_pipeline = self.get_component('data_pipeline')
                if data_pipeline:
                    for symbol in self.config.symbols:
                        await data_pipeline.refresh(symbol)
                
                await asyncio.sleep(60)  # Refresh every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Data refresh error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # Alert System
    # =========================================================================
    
    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """
        Send an alert.
        
        Args:
            alert: Alert dictionary
        """
        try:
            alert_manager = self.get_component('alert_manager')
            if alert_manager:
                await alert_manager.send(alert)
            else:
                # Log alert if no manager
                self.logger.warning(f"Alert: {alert}")
                
        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}")
    
    def register_alert_handler(
        self,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Register an alert handler.
        
        Args:
            handler: Async function that handles alerts
        """
        self.alert_handlers.append(handler)
    
    # =========================================================================
    # Status and Information
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get bot status.
        
        Returns:
            Status dictionary
        """
        return {
            'bot_id': self.bot_id,
            'status': self.status.value,
            'mode': self.mode.value,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'created_at': self.created_at.isoformat(),
            'uptime': (datetime.now() - self.started_at).total_seconds() if self.started_at else 0,
            'components': {name: self._get_component_status(name) for name in self.components},
            'metrics': self.metrics,
            'health': self.health_status
        }
    
    def _get_component_status(self, name: str) -> str:
        """
        Get component status.
        
        Args:
            name: Component name
            
        Returns:
            Status string
        """
        component = self.components.get(name)
        if component is None:
            return 'not_initialized'
        
        if hasattr(component, 'is_initialized'):
            return 'initialized' if component.is_initialized() else 'not_initialized'
        
        if hasattr(component, 'is_running'):
            return 'running' if component.is_running() else 'stopped'
        
        return 'unknown'
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get bot metrics.
        
        Returns:
            Metrics dictionary
        """
        return self.metrics.copy()
    
    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get trade history.
        
        Args:
            limit: Maximum number of trades to return
            
        Returns:
            List of trades
        """
        return self.trade_history[-limit:] if self.trade_history else []
    
    def get_order_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get order history.
        
        Args:
            limit: Maximum number of orders to return
            
        Returns:
            List of orders
        """
        return self.order_history[-limit:] if self.order_history else []
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions.
        
        Returns:
            List of positions
        """
        position_manager = self.get_component('position_manager')
        if position_manager:
            return position_manager.get_positions()
        return []
    
    def get_balance(self) -> Dict[str, float]:
        """
        Get account balance.
        
        Returns:
            Balance dictionary
        """
        execution_engine = self.get_component('execution_engine')
        if execution_engine:
            return execution_engine.get_balance()
        return {'total': 0, 'available': 0, 'locked': 0}
    
    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    def update_config(self, config_updates: Dict[str, Any]) -> bool:
        """
        Update bot configuration.
        
        Args:
            config_updates: Configuration updates
            
        Returns:
            True if updated successfully
        """
        try:
            for key, value in config_updates.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            # Update components
            for component in self.components.values():
                if hasattr(component, 'update_config'):
                    component.update_config(self.config.to_dict())
            
            self.logger.info("Configuration updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {e}")
            return False
    
    # =========================================================================
    # Component Management
    # =========================================================================
    
    def add_component(self, name: str, component: Any) -> None:
        """
        Add a custom component.
        
        Args:
            name: Component name
            component: Component instance
        """
        self.components[name] = component
        self.logger.info(f"Added component: {name}")
    
    def remove_component(self, name: str) -> bool:
        """
        Remove a component.
        
        Args:
            name: Component name
            
        Returns:
            True if removed successfully
        """
        if name in self.components:
            del self.components[name]
            self.logger.info(f"Removed component: {name}")
            return True
        return False
    
    # =========================================================================
    # Static Methods and Utilities
    # =========================================================================
    
    @staticmethod
    def load_config_from_file(config_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        if config_path.suffix in ['.yaml', '.yml']:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        elif config_path.suffix == '.json':
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            raise ValueError(f"Unsupported config file format: {config_path.suffix}")
    
    @staticmethod
    def save_config_to_file(
        config: Dict[str, Any],
        config_path: Union[str, Path]
    ) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration dictionary
            config_path: Path to save configuration
        """
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        if config_path.suffix in ['.yaml', '.yml']:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
        elif config_path.suffix == '.json':
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
        else:
            raise ValueError(f"Unsupported config file format: {config_path.suffix}")


# =============================================================================
# Context Managers
# =============================================================================

class BotContext:
    """
    Context manager for AI Bot.
    
    Usage:
        with BotContext(config) as bot:
            await bot.trade_cycle()
    """
    
    def __init__(self, config: Union[Dict[str, Any], BotConfig]):
        self.bot = AIBot(config)
    
    async def __aenter__(self):
        await self.bot.start()
        return self.bot
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.bot.stop()


# =============================================================================
# Factory Function
# =============================================================================

def create_ai_bot(
    config: Union[Dict[str, Any], BotConfig, str, Path],
    auto_start: bool = False
) -> AIBot:
    """
    Factory function to create an AI Bot instance.
    
    Args:
        config: Configuration dictionary, BotConfig instance, or path to config file
        auto_start: Automatically start the bot
        
    Returns:
        AIBot instance
    """
    # Load config if path provided
    if isinstance(config, (str, Path)):
        config = AIBot.load_config_from_file(config)
    
    # Create and return bot
    return AIBot(config, auto_start=auto_start)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'AIBot',
    'BotConfig',
    'BotStatus',
    'BotMode',
    'BotContext',
    'create_ai_bot'
]


# =============================================================================
# Module Docstring
# =============================================================================

__doc__ = f"""
{__name__} - NEXUS AI Trading Bot Core Implementation

This module provides the core AI trading bot functionality for the NEXUS
AI Trading System. It orchestrates all components of the trading system
including data processing, model inference, strategy execution, risk
management, and trade execution.

Copyright: {__copyright__}
CEO: {__author__}
Version: {__version__}

Usage:
    # Create and start a bot
    bot = AIBot({
        'name': 'My Trading Bot',
        'mode': 'paper',
        'symbols': ['BTC-USD', 'ETH-USD'],
        'initial_capital': 100000.0
    })
    await bot.start()
    
    # Execute a trade cycle
    result = await bot.trade_cycle()
    
    # Get status and metrics
    status = bot.get_status()
    metrics = bot.get_metrics()
    
    # Stop the bot
    await bot.stop()
"""

# Log module initialization
logger.info(f"AI Bot module loaded (version {__version__})")

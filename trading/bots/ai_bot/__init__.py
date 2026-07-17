# trading/bots/ai_bot/__init__.py
# NEXUS AI TRADING SYSTEM - AI Bot Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
AI Bot Module for NEXUS AI Trading System.

This module provides a complete AI-powered trading bot with:
- Advanced machine learning models (LSTM, Transformer, XGBoost, Ensemble)
- Real-time data processing and feature engineering
- Multi-strategy execution (Trend, Momentum, Mean Reversion, Breakout, Hybrid)
- Risk management and position sizing
- Order execution and management
- Performance monitoring and metrics
- Backtesting and optimization
- WebSocket and REST API interfaces
- Dashboard and visualization
- Reinforcement learning strategies
- On-chain and sentiment analysis integration
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

# Version information
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Module logger
logger = logging.getLogger("nexus.trading.bot.ai_bot")

# ============================================================================
# Core Bot Class
# ============================================================================

from trading.bots.ai_bot.ai_bot import AIBot, BotStatus, BotMode, BotState

# ============================================================================
# Configuration
# ============================================================================

from trading.bots.ai_bot.ai_bot_config import (
    BotConfig,
    ConfigLoader,
    ConfigValidator,
    ConfigManager,
    load_config,
    validate_config,
    get_config,
)

# ============================================================================
# API
# ============================================================================

from trading.bots.ai_bot.ai_bot_api import (
    AIBotAPI,
    APIHandler,
    APIResponse,
    Route,
    WebSocketHandler,
    create_api_app,
)

# ============================================================================
# Backtesting
# ============================================================================

from trading.bots.ai_bot.ai_bot_backtest import (
    BacktestEngine,
    BacktestResult,
    BacktestConfig,
    BacktestAnalyzer,
    run_backtest,
    analyze_backtest,
)

# ============================================================================
# Dashboard
# ============================================================================

from trading.bots.ai_bot.ai_bot_dashboard import (
    Dashboard,
    DashboardWidget,
    DashboardLayout,
    DashboardData,
    DashboardAPI,
    create_dashboard,
)

# ============================================================================
# Data Collection
# ============================================================================

from trading.bots.ai_bot.ai_bot_data_collector import (
    DataCollector,
    DataSource,
    DataStream,
    DataValidator,
    MarketDataCollector,
    OnChainDataCollector,
    SentimentDataCollector,
    create_data_collector,
)

# ============================================================================
# Ensemble
# ============================================================================

from trading.bots.ai_bot.ai_bot_ensemble import (
    EnsembleManager,
    EnsembleConfig,
    EnsembleStrategy,
    VotingStrategy,
    WeightingStrategy,
    create_ensemble,
)

# ============================================================================
# Feature Engineering
# ============================================================================

from trading.bots.ai_bot.ai_bot_feature_engine import (
    FeatureEngineeringEngine,
    FeatureDefinition,
    FeatureType,
    FeatureTransform,
    FeatureSelection,
    FeatureSet,
    FeatureImportance,
    create_feature_engineering_engine,
)

# ============================================================================
# Metrics
# ============================================================================

from trading.bots.ai_bot.ai_bot_metrics import (
    MetricsEngine,
    MetricDefinition,
    MetricType,
    MetricCategory,
    MetricAggregation,
    MetricValue,
    MetricSeries,
    MetricAlert,
    PerformanceSummary,
    create_metrics_engine,
)

# ============================================================================
# Model Manager
# ============================================================================

from trading.bots.ai_bot.ai_bot_model_manager import (
    ModelManager,
    ModelInfo,
    ModelStatus,
    ModelType,
    ModelFormat,
    ModelDeployment,
    ModelVersion,
    TrainingJob,
    ModelComparison,
    create_model_manager,
)

# ============================================================================
# Monitor
# ============================================================================

from trading.bots.ai_bot.ai_bot_monitor import (
    AIBotMonitor,
    MonitorStatus,
    HealthCheck,
    SystemMetrics,
    Alert,
    AlertSeverity,
    AlertCategory,
    Incident,
    IncidentStatus,
    create_ai_bot_monitor,
)

# ============================================================================
# Optimizer
# ============================================================================

from trading.bots.ai_bot.ai_bot_optimizer import (
    AIBotOptimizer,
    OptimizationMethod,
    OptimizationObjective,
    OptimizationStatus,
    OptimizationParameter,
    OptimizationConfig,
    OptimizationResult,
    ParameterImportance,
    create_ai_bot_optimizer,
)

# ============================================================================
# Order Manager
# ============================================================================

from trading.bots.ai_bot.ai_bot_order_manager import (
    OrderManager,
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    OrderBatch,
    OrderBook,
    create_order_manager,
)

# ============================================================================
# Position Manager
# ============================================================================

from trading.bots.ai_bot.ai_bot_position_manager import (
    PositionManager,
    Position,
    PositionSide,
    PositionStatus,
    PositionType,
    PositionSummary,
    create_position_manager,
)

# ============================================================================
# Predictor
# ============================================================================

from trading.bots.ai_bot.ai_bot_predictor import (
    AIBotPredictor,
    Prediction,
    PredictionType,
    PredictionHorizon,
    ConfidenceLevel,
    PredictionSummary,
    create_ai_bot_predictor,
)

# ============================================================================
# Data Module
# ============================================================================

from trading.bots.ai_bot.data import (
    DataProcessor,
    DataStorage,
    DataPipeline,
    DataValidator as DataValidatorV2,
    DataNormalizer,
    DataAugmentation,
    DataFeeder,
    create_data_pipeline,
)

# ============================================================================
# Execution Module
# ============================================================================

from trading.bots.ai_bot.execution import (
    OrderExecutor,
    OrderValidator as OrderValidatorV2,
    OrderRouter,
    OrderSplitter,
    ExecutionMonitor,
    ExecutionReport,
    create_order_executor,
)

# ============================================================================
# Indicators Module
# ============================================================================

from trading.bots.ai_bot.indicators import (
    IndicatorFactory,
    IndicatorCalculator,
    IndicatorCache,
    BaseIndicator,
    CustomIndicator,
    create_indicator_factory,
)

# ============================================================================
# Models Module
# ============================================================================

from trading.bots.ai_bot.models import (
    ModelFactory,
    ModelEvaluator,
    ModelTrainer,
    ModelLoader,
    ModelSaver,
    ModelRegistry,
    ModelPredictor as ModelPredictorV2,
    BaseModel,
    LSTMModel,
    TransformerModel,
    XGBoostModel,
    EnsembleModel,
    create_model_factory,
)

# ============================================================================
# Monitoring Module
# ============================================================================

from trading.bots.ai_bot.monitoring import (
    AlertManager,
    HealthChecker,
    IncidentManager,
    LogAnalyzer,
    MetricCollector,
    NotificationService,
    DashboardAPI as MonitoringDashboardAPI,
    create_monitoring_service,
)

# ============================================================================
# Performance Module
# ============================================================================

from trading.bots.ai_bot.performance import (
    PerformanceAnalyzer,
    PerformanceMetrics,
    PerformanceOptimizer,
    PerformanceReport,
    PerformanceTracker,
    create_performance_analyzer,
)

# ============================================================================
# Risk Module
# ============================================================================

from trading.bots.ai_bot.risk import (
    RiskManager,
    RiskAnalyzer,
    RiskCalculator,
    RiskLimits,
    RiskMonitor,
    DrawdownController,
    PositionSizer,
    StopLossManager,
    TakeProfitManager,
    VaRCalculator,
    create_risk_manager,
)

# ============================================================================
# Strategies Module
# ============================================================================

from trading.bots.ai_bot.strategies import (
    BaseStrategy,
    StrategyFactory,
    StrategyExecutor,
    StrategySelector,
    TrendFollowingStrategy,
    MomentumStrategy,
    MeanReversionStrategy,
    BreakoutStrategy,
    HybridStrategy,
    ArbitrageStrategy,
    ReinforcementStrategy,
    create_strategy,
)

# ============================================================================
# Module Information
# ============================================================================

MODULE_INFO = {
    "name": "AI Bot",
    "version": __version__,
    "author": __author__,
    "copyright": __copyright__,
    "description": "AI-powered trading bot for NEXUS AI Trading System",
    "components": [
        "Core Bot",
        "API",
        "Backtesting",
        "Dashboard",
        "Data Collection",
        "Ensemble",
        "Feature Engineering",
        "Metrics",
        "Model Manager",
        "Monitor",
        "Optimizer",
        "Order Manager",
        "Position Manager",
        "Predictor",
        "Data Processing",
        "Execution",
        "Indicators",
        "Models",
        "Monitoring",
        "Performance",
        "Risk",
        "Strategies",
    ],
    "features": [
        "Multi-model AI predictions (LSTM, Transformer, XGBoost, Ensemble)",
        "Real-time market data processing",
        "Advanced feature engineering",
        "Multi-strategy execution",
        "Risk management and position sizing",
        "Order execution and management",
        "Performance monitoring and metrics",
        "Backtesting and optimization",
        "WebSocket and REST API",
        "Dashboard and visualization",
        "Reinforcement learning strategies",
        "On-chain and sentiment analysis",
        "Multi-exchange support",
        "Auto-trading and paper trading",
    ],
}


def get_module_info() -> Dict[str, Any]:
    """Get module information."""
    return MODULE_INFO


def get_version() -> str:
    """Get module version."""
    return __version__


# ============================================================================
# Module Initialization
# ============================================================================

async def initialize_module(
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Initialize the AI Bot module.

    Args:
        config: Configuration dictionary for the module

    Returns:
        Dictionary containing initialized components
    """
    logger.info("Initializing AI Bot Module...")

    config = config or {}
    components = {}

    try:
        # Initialize configuration
        config_manager = ConfigManager()
        if config:
            config_manager.load_from_dict(config)
        components["config_manager"] = config_manager

        # Initialize data storage
        data_storage = DataStorage(config.get("storage_config", {}))
        await data_storage.start()
        components["data_storage"] = data_storage

        # Initialize data processor
        data_processor = DataProcessor(config.get("processor_config", {}))
        components["data_processor"] = data_processor

        # Initialize indicator factory
        indicator_factory = IndicatorFactory(config.get("indicator_config", {}))
        components["indicator_factory"] = indicator_factory

        # Initialize feature engineering engine
        feature_engine = FeatureEngineeringEngine(
            config=BotConfig(config.get("bot_config", {})),
            data_processor=data_processor,
            data_storage=data_storage,
            cache_manager=None,
            indicator_factory=indicator_factory,
        )
        components["feature_engine"] = feature_engine

        # Initialize model factory
        model_factory = ModelFactory(config.get("model_config", {}))
        components["model_factory"] = model_factory

        # Initialize model evaluator
        model_evaluator = ModelEvaluator(config.get("evaluator_config", {}))
        components["model_evaluator"] = model_evaluator

        # Initialize model trainer
        model_trainer = ModelTrainer(config.get("trainer_config", {}))
        components["model_trainer"] = model_trainer

        # Initialize model predictor
        model_predictor = ModelPredictorV2(config.get("predictor_config", {}))
        components["model_predictor"] = model_predictor

        # Initialize metrics engine
        metrics_engine = MetricsEngine(
            config=BotConfig(config.get("bot_config", {})),
            data_storage=data_storage,
        )
        components["metrics_engine"] = metrics_engine

        # Initialize risk manager
        risk_manager = RiskManager(config.get("risk_config", {}))
        components["risk_manager"] = risk_manager

        # Initialize order executor
        order_executor = OrderExecutor(config.get("executor_config", {}))
        components["order_executor"] = order_executor

        # Initialize order validator
        order_validator = OrderValidatorV2(config.get("validator_config", {}))
        components["order_validator"] = order_validator

        # Initialize order manager
        order_manager = OrderManager(
            config=BotConfig(config.get("bot_config", {})),
            order_executor=order_executor,
            order_validator=order_validator,
            risk_manager=risk_manager,
            data_storage=data_storage,
            metrics_engine=metrics_engine,
        )
        components["order_manager"] = order_manager

        # Initialize position manager
        position_manager = PositionManager(
            config=BotConfig(config.get("bot_config", {})),
            risk_manager=risk_manager,
            order_executor=order_executor,
            data_storage=data_storage,
            metrics_engine=metrics_engine,
        )
        components["position_manager"] = position_manager

        # Initialize model manager
        model_manager = ModelManager(
            config=BotConfig(config.get("bot_config", {})),
            model_factory=model_factory,
            model_evaluator=model_evaluator,
            model_trainer=model_trainer,
            data_storage=data_storage,
            metrics_engine=metrics_engine,
            cache_manager=None,
        )
        components["model_manager"] = model_manager

        # Initialize AI bot predictor
        ai_predictor = AIBotPredictor(
            config=BotConfig(config.get("bot_config", {})),
            model_factory=model_factory,
            model_predictor=model_predictor,
            feature_engine=feature_engine,
            data_storage=data_storage,
            metrics_engine=metrics_engine,
            cache_manager=None,
        )
        components["ai_predictor"] = ai_predictor

        # Initialize AI bot optimizer
        ai_optimizer = AIBotOptimizer(
            config=BotConfig(config.get("bot_config", {})),
            model_factory=model_factory,
            model_evaluator=model_evaluator,
            data_storage=data_storage,
            metrics_engine=metrics_engine,
        )
        components["ai_optimizer"] = ai_optimizer

        # Initialize AI bot monitor
        ai_monitor = AIBotMonitor(
            config=BotConfig(config.get("bot_config", {})),
            metrics_engine=metrics_engine,
            data_storage=data_storage,
        )
        components["ai_monitor"] = ai_monitor

        # Initialize strategy factory
        strategy_factory = StrategyFactory()
        components["strategy_factory"] = strategy_factory

        # Initialize strategy executor
        strategy_executor = StrategyExecutor(
            order_manager=order_manager,
            risk_manager=risk_manager,
            market_data_provider=None,
            config=config.get("executor_config", {}),
        )
        components["strategy_executor"] = strategy_executor

        # Initialize AI bot
        ai_bot = AIBot(
            config=BotConfig(config.get("bot_config", {})),
            model_manager=model_manager,
            predictor=ai_predictor,
            optimizer=ai_optimizer,
            monitor=ai_monitor,
            order_manager=order_manager,
            position_manager=position_manager,
            strategy_executor=strategy_executor,
            metrics_engine=metrics_engine,
        )
        components["ai_bot"] = ai_bot

        # Initialize API
        api = AIBotAPI(ai_bot)
        components["api"] = api

        # Initialize dashboard
        dashboard = Dashboard(ai_bot)
        components["dashboard"] = dashboard

        # Initialize backtest engine
        backtest_engine = BacktestEngine(
            config=BacktestConfig(),
            strategy_executor=strategy_executor,
            data_storage=data_storage,
        )
        components["backtest_engine"] = backtest_engine

        # Start components
        await data_storage.start()
        await metrics_engine.start()
        await model_manager.start()
        await ai_predictor.start()
        await ai_optimizer.start()
        await ai_monitor.start()
        await order_manager.start()
        await position_manager.start()
        await ai_bot.start()

        logger.info("AI Bot Module initialized successfully")
        logger.info(f"  - Version: {__version__}")
        logger.info(f"  - Models: {len(model_factory.get_available_models())}")
        logger.info(f"  - Strategies: {len(strategy_factory.get_strategies())}")
        logger.info(f"  - Features: {len(feature_engine._feature_definitions)}")

    except Exception as e:
        logger.error(f"Failed to initialize AI Bot Module: {e}")
        raise

    return components


# ============================================================================
# Quick Access Functions
# ============================================================================

def create_ai_bot(config: Dict[str, Any]) -> AIBot:
    """
    Quick access function to create an AI Bot instance.

    Args:
        config: Bot configuration

    Returns:
        AIBot instance
    """
    # Initialize components
    bot_config = BotConfig(config)

    # Create storage
    data_storage = DataStorage(config.get("storage_config", {}))

    # Create metrics engine
    metrics_engine = MetricsEngine(bot_config, data_storage)

    # Create risk manager
    risk_manager = RiskManager(config.get("risk_config", {}))

    # Create order executor
    order_executor = OrderExecutor(config.get("executor_config", {}))

    # Create order validator
    order_validator = OrderValidatorV2(config.get("validator_config", {}))

    # Create order manager
    order_manager = OrderManager(
        config=bot_config,
        order_executor=order_executor,
        order_validator=order_validator,
        risk_manager=risk_manager,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
    )

    # Create position manager
    position_manager = PositionManager(
        config=bot_config,
        risk_manager=risk_manager,
        order_executor=order_executor,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
    )

    # Create model manager
    model_factory = ModelFactory(config.get("model_config", {}))
    model_evaluator = ModelEvaluator(config.get("evaluator_config", {}))
    model_trainer = ModelTrainer(config.get("trainer_config", {}))
    model_predictor = ModelPredictorV2(config.get("predictor_config", {}))

    model_manager = ModelManager(
        config=bot_config,
        model_factory=model_factory,
        model_evaluator=model_evaluator,
        model_trainer=model_trainer,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
        cache_manager=None,
    )

    # Create predictor
    feature_engine = FeatureEngineeringEngine(
        config=bot_config,
        data_processor=DataProcessor(config.get("processor_config", {})),
        data_storage=data_storage,
        cache_manager=None,
        indicator_factory=IndicatorFactory(config.get("indicator_config", {})),
    )

    predictor = AIBotPredictor(
        config=bot_config,
        model_factory=model_factory,
        model_predictor=model_predictor,
        feature_engine=feature_engine,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
        cache_manager=None,
    )

    # Create optimizer
    optimizer = AIBotOptimizer(
        config=bot_config,
        model_factory=model_factory,
        model_evaluator=model_evaluator,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
    )

    # Create monitor
    monitor = AIBotMonitor(
        config=bot_config,
        metrics_engine=metrics_engine,
        data_storage=data_storage,
    )

    # Create strategy executor
    strategy_executor = StrategyExecutor(
        order_manager=order_manager,
        risk_manager=risk_manager,
        market_data_provider=None,
        config=config.get("executor_config", {}),
    )

    # Create AI Bot
    return AIBot(
        config=bot_config,
        model_manager=model_manager,
        predictor=predictor,
        optimizer=optimizer,
        monitor=monitor,
        order_manager=order_manager,
        position_manager=position_manager,
        strategy_executor=strategy_executor,
        metrics_engine=metrics_engine,
    )


def run_bot(
    config: Dict[str, Any],
    mode: str = "paper",
    symbols: Optional[List[str]] = None,
) -> None:
    """
    Quick access function to run an AI Bot.

    Args:
        config: Bot configuration
        mode: Bot mode (paper, live, backtest)
        symbols: Trading symbols
    """
    import asyncio

    if symbols:
        config["symbols"] = symbols

    if mode:
        config["mode"] = mode

    bot = create_ai_bot(config)

    # Run bot
    asyncio.run(bot.start())

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        asyncio.run(bot.stop())


def get_available_strategies() -> List[str]:
    """
    Get available trading strategies.

    Returns:
        List of strategy names
    """
    factory = StrategyFactory()
    return factory.get_strategy_names()


def get_available_models() -> List[str]:
    """
    Get available AI models.

    Returns:
        List of model names
    """
    factory = ModelFactory({})
    return factory.get_available_models()


def get_available_indicators() -> List[str]:
    """
    Get available technical indicators.

    Returns:
        List of indicator names
    """
    factory = IndicatorFactory({})
    return factory.get_available_indicators()


# ============================================================================
# CLI Integration
# ============================================================================

def main() -> None:
    """CLI entry point for the AI Bot."""
    import argparse

    parser = argparse.ArgumentParser(description="NEXUS AI Trading Bot")
    parser.add_argument("--config", "-c", type=str, help="Path to configuration file")
    parser.add_argument("--mode", "-m", choices=["paper", "live", "backtest"], default="paper")
    parser.add_argument("--symbols", "-s", type=str, help="Comma-separated symbols")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")

    args = parser.parse_args()

    if args.version:
        print(f"NEXUS AI Trading Bot v{__version__}")
        return

    config = {}
    if args.config:
        import yaml
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)

    if args.symbols:
        config["symbols"] = args.symbols.split(",")

    run_bot(config, args.mode)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print(f"NEXUS AI Trading Bot v{__version__}")
    print(f"Author: {__author__}")
    print("\nAvailable Strategies:")
    for strategy in get_available_strategies():
        print(f"  - {strategy}")
    print("\nAvailable Models:")
    for model in get_available_models():
        print(f"  - {model}")
    print("\nAvailable Indicators:")
    for indicator in get_available_indicators():
        print(f"  - {indicator}")

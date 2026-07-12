"""
NEXUS AI TRADING SYSTEM - AI Agents Package
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

This package contains all AI agents for the NEXUS trading system.
Complete agent ecosystem with:
- 6 specialized trading agents
- Collaboration and consensus mechanisms
- Real-time market analysis
- Risk management
- Sentiment analysis
- Performance monitoring
- Event-driven architecture
- Health checks
- Metrics collection
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type

# ========================================
# VERSION
# ========================================

__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# ========================================
# BASE AGENT
# ========================================

from ai.agents.base_agent import (
    BaseAgent,
    AgentConfig,
    AgentContext,
    AgentEvent,
    AgentStatus,
    AgentHealth,
    AgentPriority,
    CircuitBreaker,
    CircuitBreakerError,
    RateLimiter,
    AgentFactory
)

# ========================================
# AGENT CAPABILITIES
# ========================================

from ai.agents.agent_capabilities import (
    AgentCapability,
    CapabilityRegistry,
    capability_registry
)

# ========================================
# AGENT METRICS
# ========================================

from ai.agents.agent_metrics import (
    AgentMetrics,
    MetricType,
    MetricAggregation
)

# ========================================
# AGENT REGISTRY
# ========================================

from ai.agents.agent_registry import (
    AgentRegistry,
    AgentInfo,
    AgentRegistration,
    AgentHeartbeat,
    AgentQuery,
    get_agent_registry,
    reset_agent_registry,
    provide_agent_registry
)

# ========================================
# AGENT EVENTS
# ========================================

from ai.agents.agent_events import (
    AgentEventType,
    AgentEvent,
    EventBus,
    get_event_bus
)

# ========================================
# COLLABORATION MANAGER
# ========================================

from ai.agents.collaboration_manager import (
    CollaborationManager,
    CollaborationStrategy,
    TaskStatus,
    ConsensusType,
    ConflictResolution,
    Task,
    ConsensusVote,
    CollaborationSession,
    AgentCapabilityScore,
    get_collaboration_manager,
    reset_collaboration_manager
)

# ========================================
# TRADING AGENTS
# ========================================

# Arbitrage Agent
from ai.agents.arbitrage_agent import (
    ArbitrageAgent,
    ArbitrageConfig,
    ArbitrageOpportunity,
    ArbitrageExecution,
    ArbitrageType,
    ArbitrageStatus,
    ArbitrageRiskLevel,
    ExchangePrice,
    create_arbitrage_agent
)

# Market Making Agent
from ai.agents.market_making_agent import (
    MarketMakingAgent,
    MarketMakingConfig,
    MarketMakingStrategy,
    PriceAdjustmentMethod,
    OrderBookSnapshot,
    MarketMakingPosition,
    MarketMakingStats,
    create_market_making_agent
)

# Mean Reversion Agent
from ai.agents.mean_reversion_agent import (
    MeanReversionAgent,
    MeanReversionConfig,
    MeanReversionStrategy,
    SignalType,
    MeanReversionSignal,
    BollingerBands,
    PairsTrade,
    MeanReversionPosition,
    MeanReversionStats,
    create_mean_reversion_agent
)

# Momentum Agent
from ai.agents.momentum_agent import (
    MomentumAgent,
    MomentumConfig,
    MomentumStrategy,
    TrendType,
    BreakoutType,
    MomentumSignal,
    MovingAverageData,
    MACDData,
    TrendData,
    MomentumPosition,
    MomentumStats,
    create_momentum_agent
)

# Risk Agent
from ai.agents.risk_agent import (
    RiskAgent,
    RiskConfig,
    RiskMetric,
    RiskLevel,
    RiskStatus,
    PositionRisk,
    PortfolioRisk,
    RiskEvent,
    RiskLimit,
    RiskModel,
    create_risk_agent
)

# Sentiment Agent
from ai.agents.sentiment_agent import (
    SentimentAgent,
    SentimentConfig,
    SentimentSource,
    SentimentType,
    SentimentModelType,
    SentimentItem,
    SentimentAggregation,
    SentimentAlert,
    BaseSentimentModel,
    FinBERTModel,
    TextBlobModel,
    VADERModel,
    EnsembleModel,
    create_sentiment_agent
)

# ========================================
# AGENT TYPES REGISTRY
# ========================================

AGENT_TYPES: Dict[str, Type[BaseAgent]] = {
    'arbitrage': ArbitrageAgent,
    'market_making': MarketMakingAgent,
    'mean_reversion': MeanReversionAgent,
    'momentum': MomentumAgent,
    'risk': RiskAgent,
    'sentiment': SentimentAgent,
}

# ========================================
# AGENT CONFIGURATION SCHEMAS
# ========================================

AGENT_CONFIG_SCHEMAS: Dict[str, Any] = {
    'arbitrage': ArbitrageConfig,
    'market_making': MarketMakingConfig,
    'mean_reversion': MeanReversionConfig,
    'momentum': MomentumConfig,
    'risk': RiskConfig,
    'sentiment': SentimentConfig,
}

# ========================================
# EXPORTS
# ========================================

__all__ = [
    # Base Agent
    'BaseAgent',
    'AgentConfig',
    'AgentContext',
    'AgentEvent',
    'AgentStatus',
    'AgentHealth',
    'AgentPriority',
    'CircuitBreaker',
    'CircuitBreakerError',
    'RateLimiter',
    'AgentFactory',
    
    # Agent Capabilities
    'AgentCapability',
    'CapabilityRegistry',
    'capability_registry',
    
    # Agent Metrics
    'AgentMetrics',
    'MetricType',
    'MetricAggregation',
    
    # Agent Registry
    'AgentRegistry',
    'AgentInfo',
    'AgentRegistration',
    'AgentHeartbeat',
    'AgentQuery',
    'get_agent_registry',
    'reset_agent_registry',
    'provide_agent_registry',
    
    # Agent Events
    'AgentEventType',
    'AgentEvent',
    'EventBus',
    'get_event_bus',
    
    # Collaboration Manager
    'CollaborationManager',
    'CollaborationStrategy',
    'TaskStatus',
    'ConsensusType',
    'ConflictResolution',
    'Task',
    'ConsensusVote',
    'CollaborationSession',
    'AgentCapabilityScore',
    'get_collaboration_manager',
    'reset_collaboration_manager',
    
    # Arbitrage Agent
    'ArbitrageAgent',
    'ArbitrageConfig',
    'ArbitrageOpportunity',
    'ArbitrageExecution',
    'ArbitrageType',
    'ArbitrageStatus',
    'ArbitrageRiskLevel',
    'ExchangePrice',
    'create_arbitrage_agent',
    
    # Market Making Agent
    'MarketMakingAgent',
    'MarketMakingConfig',
    'MarketMakingStrategy',
    'PriceAdjustmentMethod',
    'OrderBookSnapshot',
    'MarketMakingPosition',
    'MarketMakingStats',
    'create_market_making_agent',
    
    # Mean Reversion Agent
    'MeanReversionAgent',
    'MeanReversionConfig',
    'MeanReversionStrategy',
    'SignalType',
    'MeanReversionSignal',
    'BollingerBands',
    'PairsTrade',
    'MeanReversionPosition',
    'MeanReversionStats',
    'create_mean_reversion_agent',
    
    # Momentum Agent
    'MomentumAgent',
    'MomentumConfig',
    'MomentumStrategy',
    'TrendType',
    'BreakoutType',
    'MomentumSignal',
    'MovingAverageData',
    'MACDData',
    'TrendData',
    'MomentumPosition',
    'MomentumStats',
    'create_momentum_agent',
    
    # Risk Agent
    'RiskAgent',
    'RiskConfig',
    'RiskMetric',
    'RiskLevel',
    'RiskStatus',
    'PositionRisk',
    'PortfolioRisk',
    'RiskEvent',
    'RiskLimit',
    'RiskModel',
    'create_risk_agent',
    
    # Sentiment Agent
    'SentimentAgent',
    'SentimentConfig',
    'SentimentSource',
    'SentimentType',
    'SentimentModelType',
    'SentimentItem',
    'SentimentAggregation',
    'SentimentAlert',
    'BaseSentimentModel',
    'FinBERTModel',
    'TextBlobModel',
    'VADERModel',
    'EnsembleModel',
    'create_sentiment_agent',
    
    # Registry
    'AGENT_TYPES',
    'AGENT_CONFIG_SCHEMAS',
    
    # Version
    '__version__',
    '__author__',
    '__copyright__'
]

# ========================================
# AGENT REGISTRATION
# ========================================

def register_agents() -> None:
    """Register all agents with the agent factory"""
    for agent_type, agent_class in AGENT_TYPES.items():
        AgentFactory.register(agent_type, agent_class)
    
    logging.getLogger(__name__).info(f"Registered {len(AGENT_TYPES)} agent types")


# ========================================
# AGENT FACTORY HELPER
# ========================================

def create_agent(
    agent_type: str,
    config: Dict[str, Any]
) -> BaseAgent:
    """
    Create an agent instance.
    
    Args:
        agent_type: Type of agent to create
        config: Agent configuration
        
    Returns:
        BaseAgent: Agent instance
        
    Raises:
        ValueError: If agent type is not found
    """
    if agent_type not in AGENT_TYPES:
        raise ValueError(f"Unknown agent type: {agent_type}")
    
    return AGENT_TYPES[agent_type](config)


def get_agent_config_schema(agent_type: str) -> Any:
    """
    Get the configuration schema for an agent type.
    
    Args:
        agent_type: Type of agent
        
    Returns:
        Any: Configuration schema class
    """
    if agent_type not in AGENT_CONFIG_SCHEMAS:
        raise ValueError(f"Unknown agent type: {agent_type}")
    
    return AGENT_CONFIG_SCHEMAS[agent_type]


def validate_agent_config(agent_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate agent configuration.
    
    Args:
        agent_type: Type of agent
        config: Configuration dictionary
        
    Returns:
        Dict[str, Any]: Validated configuration
        
    Raises:
        ValueError: If validation fails
    """
    schema = get_agent_config_schema(agent_type)
    try:
        validated = schema(**config)
        return validated.dict()
    except Exception as e:
        raise ValueError(f"Invalid configuration for {agent_type}: {e}")


def list_agent_types() -> List[str]:
    """
    List all available agent types.
    
    Returns:
        List[str]: List of agent type names
    """
    return list(AGENT_TYPES.keys())


def get_agent_capabilities(agent_type: str) -> List[AgentCapability]:
    """
    Get capabilities for an agent type.
    
    Args:
        agent_type: Type of agent
        
    Returns:
        List[AgentCapability]: List of capabilities
    """
    if agent_type == 'arbitrage':
        return [
            AgentCapability.ARBITRAGE,
            AgentCapability.MARKET_DATA,
            AgentCapability.ORDER_EXECUTION,
            AgentCapability.RISK_MANAGEMENT
        ]
    elif agent_type == 'market_making':
        return [
            AgentCapability.MARKET_MAKING,
            AgentCapability.ORDER_EXECUTION,
            AgentCapability.MARKET_DATA,
            AgentCapability.RISK_MANAGEMENT
        ]
    elif agent_type == 'mean_reversion':
        return [
            AgentCapability.MEAN_REVERSION,
            AgentCapability.STATISTICAL_ARBITRAGE,
            AgentCapability.ORDER_EXECUTION,
            AgentCapability.MARKET_DATA,
            AgentCapability.RISK_MANAGEMENT
        ]
    elif agent_type == 'momentum':
        return [
            AgentCapability.MOMENTUM_TRADING,
            AgentCapability.TREND_FOLLOWING,
            AgentCapability.ORDER_EXECUTION,
            AgentCapability.MARKET_DATA,
            AgentCapability.RISK_MANAGEMENT
        ]
    elif agent_type == 'risk':
        return [
            AgentCapability.RISK_MANAGEMENT,
            AgentCapability.PORTFOLIO_ANALYTICS,
            AgentCapability.ORDER_EXECUTION
        ]
    elif agent_type == 'sentiment':
        return [
            AgentCapability.SENTIMENT_ANALYSIS,
            AgentCapability.NLP,
            AgentCapability.MARKET_INSIGHTS
        ]
    else:
        return []


# ========================================
# AGENT INITIALIZATION
# ========================================

# Register agents on import
register_agents()

# ========================================
# LOGGING CONFIGURATION
# ========================================

logger = logging.getLogger(__name__)
logger.info(f"NEXUS AI Agents Package v{__version__} initialized")
logger.info(f"Registered {len(AGENT_TYPES)} agent types: {list(AGENT_TYPES.keys())}")

# ========================================
# END OF PACKAGE
# ========================================"""
NEXUS AI TRADING SYSTEM
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder
"""


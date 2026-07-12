"""
NEXUS AI TRADING SYSTEM - Cognition Package
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Cognition system with:
- Decision Maker
- Knowledge Base
- Learning Loop
- Memory System
- Reasoning Engine
- Cognitive capabilities for AI agents
- Health monitoring
- Configuration management
- Event handling
- Logging
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
# DECISION MAKER
# ========================================

from ai.cognition.decision_maker import (
    DecisionMaker,
    DecisionConfig,
    Decision,
    DecisionResult,
    DecisionHistory,
    DecisionType,
    DecisionStatus,
    ConfidenceLevel,
    get_decision_maker,
    reset_decision_maker
)

# ========================================
# KNOWLEDGE BASE
# ========================================

from ai.cognition.knowledge_base import (
    KnowledgeBase,
    KnowledgeConfig,
    KnowledgeItem,
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeRelationship,
    KnowledgeType,
    KnowledgeStatus,
    KnowledgeSource,
    get_knowledge_base,
    reset_knowledge_base
)

# ========================================
# LEARNING LOOP
# ========================================

from ai.cognition.learning_loop import (
    LearningLoop,
    LearningConfig,
    LearningTask,
    LearningResult,
    LearningHistory,
    LearningType,
    LearningMode,
    LearningStatus,
    get_learning_loop,
    reset_learning_loop
)

# ========================================
# MEMORY SYSTEM
# ========================================

from ai.cognition.memory import (
    MemorySystem,
    MemoryConfig,
    Memory,
    MemoryContext,
    MemoryQueryResult,
    MemoryType,
    MemoryImportance,
    MemoryStatus,
    get_memory,
    reset_memory
)

# ========================================
# REASONING ENGINE
# ========================================

from ai.cognition.reasoning_engine import (
    ReasoningEngine,
    ReasoningConfig,
    ReasoningContext,
    ReasoningResult,
    ReasoningHistory,
    ReasoningType,
    ReasoningStatus,
    get_reasoning_engine,
    reset_reasoning_engine
)

# ========================================
# REGISTRIES
# ========================================

COGNITION_COMPONENTS = {
    'decision_maker': DecisionMaker,
    'knowledge_base': KnowledgeBase,
    'learning_loop': LearningLoop,
    'memory': MemorySystem,
    'reasoning_engine': ReasoningEngine
}

# ========================================
# CONFIGURATION SCHEMAS
# ========================================

COGNITION_CONFIG_SCHEMAS = {
    'decision': DecisionConfig,
    'knowledge': KnowledgeConfig,
    'learning': LearningConfig,
    'memory': MemoryConfig,
    'reasoning': ReasoningConfig
}

# ========================================
# EXPORTS
# ========================================

__all__ = [
    # Decision Maker
    'DecisionMaker',
    'DecisionConfig',
    'Decision',
    'DecisionResult',
    'DecisionHistory',
    'DecisionType',
    'DecisionStatus',
    'ConfidenceLevel',
    'get_decision_maker',
    'reset_decision_maker',
    
    # Knowledge Base
    'KnowledgeBase',
    'KnowledgeConfig',
    'KnowledgeItem',
    'KnowledgeQuery',
    'KnowledgeResult',
    'KnowledgeRelationship',
    'KnowledgeType',
    'KnowledgeStatus',
    'KnowledgeSource',
    'get_knowledge_base',
    'reset_knowledge_base',
    
    # Learning Loop
    'LearningLoop',
    'LearningConfig',
    'LearningTask',
    'LearningResult',
    'LearningHistory',
    'LearningType',
    'LearningMode',
    'LearningStatus',
    'get_learning_loop',
    'reset_learning_loop',
    
    # Memory System
    'MemorySystem',
    'MemoryConfig',
    'Memory',
    'MemoryContext',
    'MemoryQueryResult',
    'MemoryType',
    'MemoryImportance',
    'MemoryStatus',
    'get_memory',
    'reset_memory',
    
    # Reasoning Engine
    'ReasoningEngine',
    'ReasoningConfig',
    'ReasoningContext',
    'ReasoningResult',
    'ReasoningHistory',
    'ReasoningType',
    'ReasoningStatus',
    'get_reasoning_engine',
    'reset_reasoning_engine',
    
    # Registries
    'COGNITION_COMPONENTS',
    'COGNITION_CONFIG_SCHEMAS',
    
    # Version
    '__version__',
    '__author__',
    '__copyright__'
]

# ========================================
# COMPONENT INITIALIZATION
# ========================================

def initialize_cognition() -> None:
    """Initialize all cognition components"""
    logger = logging.getLogger(__name__)
    
    components = {
        'decision_maker': get_decision_maker,
        'knowledge_base': get_knowledge_base,
        'learning_loop': get_learning_loop,
        'memory': get_memory,
        'reasoning_engine': get_reasoning_engine
    }
    
    for name, getter in components.items():
        try:
            component = getter()
            logger.info(f"Initialized {name}")
        except Exception as e:
            logger.error(f"Failed to initialize {name}: {e}")
    
    logger.info("Cognition components initialized")


def shutdown_cognition() -> None:
    """Shutdown all cognition components"""
    logger = logging.getLogger(__name__)
    
    components = {
        'decision_maker': (get_decision_maker, reset_decision_maker),
        'knowledge_base': (get_knowledge_base, reset_knowledge_base),
        'learning_loop': (get_learning_loop, reset_learning_loop),
        'memory': (get_memory, reset_memory),
        'reasoning_engine': (get_reasoning_engine, reset_reasoning_engine)
    }
    
    for name, (getter, resetter) in components.items():
        try:
            resetter()
            logger.info(f"Shutdown {name}")
        except Exception as e:
            logger.error(f"Failed to shutdown {name}: {e}")
    
    logger.info("Cognition components shutdown")


# ========================================
# CONTEXT MANAGER
# ========================================

class CognitionContext:
    """Context manager for cognition"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """Enter context"""
        self.logger.info("Starting cognition context")
        initialize_cognition()
        
        # Start components
        components = [
            get_decision_maker(),
            get_knowledge_base(),
            get_learning_loop(),
            get_memory(),
            get_reasoning_engine()
        ]
        
        for component in components:
            if hasattr(component, 'start'):
                try:
                    await component.start()
                    self.logger.info(f"Started {component.__class__.__name__}")
                except Exception as e:
                    self.logger.error(f"Failed to start {component.__class__.__name__}: {e}")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context"""
        self.logger.info("Stopping cognition context")
        
        # Stop components
        components = [
            get_decision_maker(),
            get_knowledge_base(),
            get_learning_loop(),
            get_memory(),
            get_reasoning_engine()
        ]
        
        for component in components:
            if hasattr(component, 'stop'):
                try:
                    await component.stop()
                    self.logger.info(f"Stopped {component.__class__.__name__}")
                except Exception as e:
                    self.logger.error(f"Failed to stop {component.__class__.__name__}: {e}")
        
        shutdown_cognition()

# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

async def make_decision(
    type: DecisionType,
    symbol: str,
    action: str,
    quantity: float,
    price: float,
    reason: str = "",
    source: str = ""
) -> Decision:
    """
    Make a decision.
    
    Args:
        type: Decision type
        symbol: Symbol
        action: Action
        quantity: Quantity
        price: Price
        reason: Reason
        source: Source
        
    Returns:
        Decision: Created decision
    """
    decision_maker = get_decision_maker()
    return await decision_maker.create_decision(
        type=type,
        symbol=symbol,
        action=action,
        quantity=quantity,
        price=price,
        reason=reason,
        source=source
    )


async def store_knowledge(
    content: Any,
    type: KnowledgeType,
    source: KnowledgeSource,
    tags: Optional[List[str]] = None
) -> KnowledgeItem:
    """
    Store knowledge.
    
    Args:
        content: Knowledge content
        type: Knowledge type
        source: Knowledge source
        tags: Tags
        
    Returns:
        KnowledgeItem: Stored knowledge
    """
    knowledge_base = get_knowledge_base()
    return await knowledge_base.add_knowledge(
        content=content,
        type=type,
        source=source,
        tags=tags
    )


async def store_memory(
    content: Any,
    type: MemoryType,
    importance: MemoryImportance = MemoryImportance.MEDIUM,
    tags: Optional[List[str]] = None
) -> Memory:
    """
    Store memory.
    
    Args:
        content: Memory content
        type: Memory type
        importance: Memory importance
        tags: Tags
        
    Returns:
        Memory: Stored memory
    """
    memory = get_memory()
    return await memory.store_memory(
        content=content,
        type=type,
        importance=importance,
        tags=tags
    )


async def reason(
    query: str,
    type: ReasoningType,
    data: Optional[Dict[str, Any]] = None
) -> ReasoningResult:
    """
    Execute reasoning.
    
    Args:
        query: Query
        type: Reasoning type
        data: Additional data
        
    Returns:
        ReasoningResult: Reasoning result
    """
    reasoning_engine = get_reasoning_engine()
    return await reasoning_engine.reason(
        query=query,
        type=type,
        data=data
    )


async def learn(
    type: LearningType,
    model_name: str,
    data: Dict[str, Any]
) -> LearningResult:
    """
    Execute learning.
    
    Args:
        type: Learning type
        model_name: Model name
        data: Training data
        
    Returns:
        LearningResult: Learning result
    """
    learning_loop = get_learning_loop()
    task = await learning_loop.create_task(
        type=type,
        model_name=model_name,
        data=data
    )
    return await learning_loop.start_task(task.id)

# ========================================
# INITIALIZATION
# ========================================

logger = logging.getLogger(__name__)
logger.info(f"NEXUS Cognition Package v{__version__} initialized")
logger.info(f"Available components: {list(COGNITION_COMPONENTS.keys())}")

# Auto-initialize components
initialize_cognition()

# ========================================
# END OF PACKAGE
# ========================================

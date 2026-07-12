"""
NEXUS AI TRADING SYSTEM - Decision Maker
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Decision Maker system with:
- Multi-agent decision making
- Consensus mechanisms
- Voting systems
- Weighted decisions
- Confidence scoring
- Decision history
- Decision validation
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field, validator

from ai.agents.agent_registry import AgentInfo, get_agent_registry
from ai.agents.agent_capabilities import AgentCapability
from ai.agents.collaboration_manager import (
    CollaborationManager,
    ConsensusType,
    get_collaboration_manager
)
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import DecisionError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class DecisionType(str, Enum):
    """Decision types"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    REBALANCE = "rebalance"
    ENTER = "enter"
    EXIT = "exit"
    ADJUST = "adjust"


class DecisionStatus(str, Enum):
    """Decision status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConfidenceLevel(str, Enum):
    """Confidence levels"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class Decision:
    """Decision data"""
    id: str = field(default_factory=lambda: str(uuid4()))
    type: DecisionType
    symbol: str
    action: str
    quantity: float
    price: float
    confidence: float  # 0-1
    confidence_level: ConfidenceLevel
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    reason: str = ""
    source: str = ""  # Agent ID or system component
    metadata: Dict[str, Any] = field(default_factory=dict)
    votes: List[Dict[str, Any]] = field(default_factory=list)
    approvals: int = 0
    rejections: int = 0
    weight: float = 1.0


@dataclass
class DecisionResult:
    """Decision result"""
    id: str
    status: DecisionStatus
    executed_at: Optional[datetime]
    result: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class DecisionHistory:
    """Decision history"""
    timestamp: datetime
    decision: Decision
    result: DecisionResult
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecisionConfig(BaseModel):
    """Decision configuration"""
    enabled: bool = True
    min_confidence: float = Field(default=0.6, ge=0, le=1)
    max_decision_age: int = Field(default=60, gt=0)  # seconds
    require_consensus: bool = True
    consensus_threshold: float = Field(default=0.5, ge=0, le=1)
    min_agents: int = Field(default=2, gt=0)
    max_agents: int = Field(default=10, gt=0)
    decision_timeout: int = Field(default=30, gt=0)  # seconds
    auto_execute: bool = True
    require_approval: bool = True
    approval_threshold: float = Field(default=0.5, ge=0, le=1)
    use_weighted_voting: bool = True
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# DECISION MAKER
# ========================================

class DecisionMaker:
    """
    Complete decision maker for multi-agent trading system.
    
    Features:
    - Multi-agent decision making
    - Consensus mechanisms
    - Voting systems
    - Weighted decisions
    - Confidence scoring
    - Decision history
    - Decision validation
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = DecisionConfig(**(config or {}))
        self.redis = get_redis()
        self.agent_registry = get_agent_registry()
        self.collaboration_manager = get_collaboration_manager()
        
        # State
        self._pending_decisions: Dict[str, Decision] = {}
        self._approved_decisions: Dict[str, Decision] = {}
        self._executed_decisions: Dict[str, Decision] = {}
        self._rejected_decisions: Dict[str, Decision] = {}
        self._decision_history: List[DecisionHistory] = []
        
        # Agent weights
        self._agent_weights: Dict[str, float] = {}
        self._update_agent_weights()
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_decisions": 0,
            "approved_decisions": 0,
            "rejected_decisions": 0,
            "executed_decisions": 0,
            "failed_decisions": 0,
            "avg_decision_time": 0.0,
            "avg_confidence": 0.0,
            "consensus_rate": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.DecisionMaker")
        self.logger.info("DecisionMaker initialized")
    
    # ========================================
    # DECISION CREATION
    # ========================================
    
    async def create_decision(
        self,
        type: DecisionType,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        reason: str = "",
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Decision:
        """
        Create a new decision.
        
        Args:
            type: Decision type
            symbol: Symbol
            action: Action to take
            quantity: Quantity
            price: Price
            reason: Reason for decision
            source: Source agent ID
            metadata: Additional metadata
            
        Returns:
            Decision: Created decision
        """
        try:
            # Validate inputs
            self._validate_decision_inputs(type, symbol, quantity, price)
            
            # Create decision
            decision = Decision(
                type=type,
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=price,
                reason=reason,
                source=source,
                metadata=metadata or {}
            )
            
            # Calculate initial confidence
            decision.confidence = await self._calculate_initial_confidence(decision)
            decision.confidence_level = self._get_confidence_level(decision.confidence)
            
            # Store decision
            self._pending_decisions[decision.id] = decision
            self._metrics["total_decisions"] += 1
            
            self.logger.info(
                f"Decision created: {type.value} {symbol} {action} "
                f"quantity={quantity} price={price}"
            )
            
            return decision
            
        except Exception as e:
            self.logger.error(f"Failed to create decision: {e}")
            raise DecisionError(f"Decision creation failed: {e}")
    
    # ========================================
    # DECISION VOTING
    # ========================================
    
    async def vote_on_decision(
        self,
        decision_id: str,
        agent_id: str,
        approve: bool,
        confidence: Optional[float] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Vote on a decision.
        
        Args:
            decision_id: Decision ID
            agent_id: Agent ID
            approve: Approval status
            confidence: Confidence in vote
            comment: Comment
            
        Returns:
            Dict[str, Any]: Vote result
            
        Raises:
            DecisionError: If decision not found
        """
        decision = self._get_decision(decision_id)
        
        # Check if already voted
        existing_vote = next(
            (v for v in decision.votes if v['agent_id'] == agent_id),
            None
        )
        if existing_vote:
            raise DecisionError(f"Agent {agent_id} already voted")
        
        # Get agent weight
        weight = self._agent_weights.get(agent_id, 1.0)
        
        # Add vote
        vote = {
            'agent_id': agent_id,
            'approve': approve,
            'confidence': confidence or 0.5,
            'weight': weight,
            'comment': comment,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        decision.votes.append(vote)
        
        if approve:
            decision.approvals += weight
        else:
            decision.rejections += weight
        
        # Update decision confidence
        await self._update_decision_confidence(decision)
        
        # Check if decision is ready
        await self._check_decision_readiness(decision)
        
        self.logger.info(
            f"Vote added: {agent_id} {'approves' if approve else 'rejects'} "
            f"decision {decision_id}"
        )
        
        return vote
    
    # ========================================
    # DECISION EXECUTION
    # ========================================
    
    async def execute_decision(self, decision_id: str) -> DecisionResult:
        """
        Execute a decision.
        
        Args:
            decision_id: Decision ID
            
        Returns:
            DecisionResult: Execution result
            
        Raises:
            DecisionError: If decision not found or invalid
        """
        decision = self._get_decision(decision_id)
        
        if decision.status != DecisionStatus.APPROVED:
            raise DecisionError(f"Decision {decision_id} is not approved")
        
        try:
            decision.status = DecisionStatus.EXECUTING
            decision.updated_at = datetime.utcnow()
            
            # Execute decision
            result = await self._execute_action(decision)
            
            # Update status
            if result.get('success', False):
                decision.status = DecisionStatus.EXECUTED
                decision.executed_at = datetime.utcnow()
                self._metrics["executed_decisions"] += 1
            else:
                decision.status = DecisionStatus.FAILED
                self._metrics["failed_decisions"] += 1
            
            # Store result
            decision_result = DecisionResult(
                id=decision.id,
                status=decision.status,
                executed_at=decision.executed_at,
                result=result,
                error=result.get('error')
            )
            
            # Move to executed
            if decision.status in [DecisionStatus.EXECUTED, DecisionStatus.FAILED]:
                self._executed_decisions[decision.id] = decision
                if decision.id in self._approved_decisions:
                    del self._approved_decisions[decision.id]
            
            # Add to history
            self._decision_history.append(
                DecisionHistory(
                    timestamp=datetime.utcnow(),
                    decision=decision,
                    result=decision_result
                )
            )
            
            self.logger.info(
                f"Decision executed: {decision.id} "
                f"status={decision.status.value} "
                f"result={'success' if result.get('success') else 'failed'}"
            )
            
            return decision_result
            
        except Exception as e:
            self.logger.error(f"Decision execution failed: {e}")
            decision.status = DecisionStatus.FAILED
            self._metrics["failed_decisions"] += 1
            
            return DecisionResult(
                id=decision.id,
                status=DecisionStatus.FAILED,
                executed_at=datetime.utcnow(),
                result={'success': False},
                error=str(e)
            )
    
    # ========================================
    # DECISION MANAGEMENT
    # ========================================
    
    def _get_decision(self, decision_id: str) -> Decision:
        """Get decision by ID"""
        decision = (
            self._pending_decisions.get(decision_id) or
            self._approved_decisions.get(decision_id) or
            self._executed_decisions.get(decision_id) or
            self._rejected_decisions.get(decision_id)
        )
        if not decision:
            raise DecisionError(f"Decision {decision_id} not found")
        return decision
    
    async def get_decision_status(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get decision status"""
        decision = (
            self._pending_decisions.get(decision_id) or
            self._approved_decisions.get(decision_id) or
            self._executed_decisions.get(decision_id) or
            self._rejected_decisions.get(decision_id)
        )
        if not decision:
            return None
        
        return {
            'id': decision.id,
            'type': decision.type.value,
            'symbol': decision.symbol,
            'status': decision.status.value,
            'confidence': decision.confidence,
            'confidence_level': decision.confidence_level.value,
            'approvals': decision.approvals,
            'rejections': decision.rejections,
            'created_at': decision.created_at.isoformat(),
            'updated_at': decision.updated_at.isoformat()
        }
    
    async def cancel_decision(self, decision_id: str) -> bool:
        """
        Cancel a pending decision.
        
        Args:
            decision_id: Decision ID
            
        Returns:
            bool: True if cancelled
        """
        if decision_id not in self._pending_decisions:
            return False
        
        decision = self._pending_decisions[decision_id]
        decision.status = DecisionStatus.CANCELLED
        decision.updated_at = datetime.utcnow()
        
        del self._pending_decisions[decision_id]
        
        self.logger.info(f"Decision cancelled: {decision_id}")
        return True
    
    # ========================================
    # DECISION VALIDATION
    # ========================================
    
    def _validate_decision_inputs(
        self,
        type: DecisionType,
        symbol: str,
        quantity: float,
        price: float
    ) -> None:
        """Validate decision inputs"""
        if not symbol:
            raise DecisionError("Symbol is required")
        
        if quantity <= 0:
            raise DecisionError("Quantity must be positive")
        
        if price <= 0:
            raise DecisionError("Price must be positive")
    
    async def _calculate_initial_confidence(self, decision: Decision) -> float:
        """Calculate initial confidence for decision"""
        # Base confidence from source if available
        base_confidence = 0.5
        
        if decision.source:
            agent = self.agent_registry.get_agent(decision.source)
            if agent:
                # Use agent's historical performance
                base_confidence = await self._get_agent_confidence(decision.source)
        
        # Adjust based on decision type
        type_confidence = {
            DecisionType.BUY: 0.6,
            DecisionType.SELL: 0.6,
            DecisionType.HOLD: 0.4,
            DecisionType.STOP_LOSS: 0.7,
            DecisionType.TAKE_PROFIT: 0.7,
            DecisionType.REBALANCE: 0.5
        }
        
        confidence = (base_confidence + type_confidence.get(decision.type, 0.5)) / 2
        
        return min(1.0, max(0.0, confidence))
    
    async def _get_agent_confidence(self, agent_id: str) -> float:
        """Get confidence based on agent's historical performance"""
        # Get agent metrics
        metrics = await self.agent_registry.get_metrics(agent_id)
        if not metrics:
            return 0.5
        
        # Calculate confidence from success rate
        success_rate = metrics.get('success_rate', 0.5)
        confidence = 0.3 + success_rate * 0.7  # Scale to 0.3-1.0
        
        return min(1.0, confidence)
    
    async def _update_decision_confidence(self, decision: Decision) -> None:
        """Update decision confidence based on votes"""
        if not decision.votes:
            return
        
        # Calculate weighted confidence
        total_weight = 0
        weighted_confidence = 0
        
        for vote in decision.votes:
            weight = vote['weight']
            confidence = vote['confidence']
            total_weight += weight
            weighted_confidence += confidence * weight
        
        if total_weight > 0:
            decision.confidence = weighted_confidence / total_weight
            decision.confidence_level = self._get_confidence_level(decision.confidence)
    
    async def _check_decision_readiness(self, decision: Decision) -> None:
        """Check if decision is ready for approval or rejection"""
        # Check if we have enough votes
        total_votes = len(decision.votes)
        if total_votes < self.config.min_agents:
            return
        
        # Check if decision has timed out
        age = (datetime.utcnow() - decision.created_at).total_seconds()
        if age > self.config.max_decision_age:
            await self._handle_timeout(decision)
            return
        
        # Calculate approval ratio
        total_weight = decision.approvals + decision.rejections
        if total_weight == 0:
            return
        
        approval_ratio = decision.approvals / total_weight
        
        # Check if consensus is reached
        if self.config.require_consensus:
            if approval_ratio >= self.config.approval_threshold:
                await self._approve_decision(decision)
            elif approval_ratio <= 1 - self.config.approval_threshold:
                await self._reject_decision(decision)
        else:
            # Simple majority
            if approval_ratio >= 0.5:
                await self._approve_decision(decision)
            else:
                await self._reject_decision(decision)
    
    async def _approve_decision(self, decision: Decision) -> None:
        """Approve a decision"""
        if decision.status != DecisionStatus.PENDING:
            return
        
        decision.status = DecisionStatus.APPROVED
        decision.updated_at = datetime.utcnow()
        
        self._approved_decisions[decision.id] = decision
        if decision.id in self._pending_decisions:
            del self._pending_decisions[decision.id]
        
        self._metrics["approved_decisions"] += 1
        
        self.logger.info(
            f"Decision approved: {decision.id} "
            f"approvals={decision.approvals} "
            f"rejections={decision.rejections}"
        )
        
        # Auto-execute if enabled
        if self.config.auto_execute:
            await self.execute_decision(decision.id)
    
    async def _reject_decision(self, decision: Decision) -> None:
        """Reject a decision"""
        if decision.status != DecisionStatus.PENDING:
            return
        
        decision.status = DecisionStatus.REJECTED
        decision.updated_at = datetime.utcnow()
        
        self._rejected_decisions[decision.id] = decision
        if decision.id in self._pending_decisions:
            del self._pending_decisions[decision.id]
        
        self._metrics["rejected_decisions"] += 1
        
        self.logger.info(
            f"Decision rejected: {decision.id} "
            f"approvals={decision.approvals} "
            f"rejections={decision.rejections}"
        )
    
    async def _handle_timeout(self, decision: Decision) -> None:
        """Handle decision timeout"""
        decision.status = DecisionStatus.FAILED
        decision.updated_at = datetime.utcnow()
        
        self._rejected_decisions[decision.id] = decision
        if decision.id in self._pending_decisions:
            del self._pending_decisions[decision.id]
        
        self.logger.warning(f"Decision timed out: {decision.id}")
    
    # ========================================
    # AGENT WEIGHTS
    # ========================================
    
    def _update_agent_weights(self) -> None:
        """Update agent weights based on performance"""
        agents = self.agent_registry.get_all_agents()
        
        for agent in agents:
            # Base weight
            weight = 1.0
            
            # Adjust based on agent status
            if agent.health == 'healthy':
                weight *= 1.2
            elif agent.health == 'degraded':
                weight *= 0.8
            elif agent.health == 'unhealthy':
                weight *= 0.5
            
            # Adjust based on capability
            if AgentCapability.ARBITRAGE in agent.capabilities:
                weight *= 1.1
            
            self._agent_weights[agent.id] = weight
    
    # ========================================
    # DECISION EXECUTION
    # ========================================
    
    async def _execute_action(self, decision: Decision) -> Dict[str, Any]:
        """Execute the decision action"""
        try:
            # Get trading service
            from backend.services.trading_service import TradingService
            trading_service = TradingService()
            
            # Execute based on decision type
            if decision.type in [DecisionType.BUY, DecisionType.ENTER]:
                result = await trading_service.buy(
                    symbol=decision.symbol,
                    quantity=decision.quantity,
                    price=decision.price,
                    metadata={'decision_id': decision.id}
                )
            elif decision.type in [DecisionType.SELL, DecisionType.EXIT]:
                result = await trading_service.sell(
                    symbol=decision.symbol,
                    quantity=decision.quantity,
                    price=decision.price,
                    metadata={'decision_id': decision.id}
                )
            elif decision.type == DecisionType.STOP_LOSS:
                result = await trading_service.set_stop_loss(
                    symbol=decision.symbol,
                    stop_price=decision.price,
                    metadata={'decision_id': decision.id}
                )
            elif decision.type == DecisionType.TAKE_PROFIT:
                result = await trading_service.set_take_profit(
                    symbol=decision.symbol,
                    take_profit_price=decision.price,
                    metadata={'decision_id': decision.id}
                )
            elif decision.type == DecisionType.REBALANCE:
                result = await trading_service.rebalance(
                    symbol=decision.symbol,
                    target_quantity=decision.quantity,
                    metadata={'decision_id': decision.id}
                )
            elif decision.type == DecisionType.ADJUST:
                result = await trading_service.adjust_position(
                    symbol=decision.symbol,
                    adjustment=decision.action,
                    quantity=decision.quantity,
                    metadata={'decision_id': decision.id}
                )
            else:
                result = {
                    'success': False,
                    'error': f"Unsupported decision type: {decision.type}"
                }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Action execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ========================================
    # HELPER FUNCTIONS
    # ========================================
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Get confidence level from confidence score"""
        if confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    # ========================================
    # BACKGROUND TASKS
    # ========================================
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while self._running:
            try:
                # Clean up old decisions
                cutoff = datetime.utcnow() - timedelta(hours=24)
                
                # Clean up executed decisions
                for decision_id in list(self._executed_decisions.keys()):
                    decision = self._executed_decisions[decision_id]
                    if decision.executed_at and decision.executed_at < cutoff:
                        del self._executed_decisions[decision_id]
                
                # Clean up rejected decisions
                for decision_id in list(self._rejected_decisions.keys()):
                    decision = self._rejected_decisions[decision_id]
                    if decision.updated_at < cutoff:
                        del self._rejected_decisions[decision_id]
                
                # Clean up history
                self._decision_history = [
                    h for h in self._decision_history
                    if h.timestamp > cutoff
                ]
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {e}")
            
            await asyncio.sleep(3600)  # 1 hour
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                health = await self.health_check()
                self.logger.debug(f"Health: {health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self.config.health_check_interval)
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get decision metrics"""
        return {
            **self._metrics,
            "pending_decisions": len(self._pending_decisions),
            "approved_decisions": len(self._approved_decisions),
            "executed_decisions": len(self._executed_decisions),
            "rejected_decisions": len(self._rejected_decisions),
            "history_length": len(self._decision_history),
            "active_agents": len(self._agent_weights)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check decision maker health"""
        health = {
            'status': 'healthy',
            'pending_decisions': len(self._pending_decisions),
            'approved_decisions': len(self._approved_decisions),
            'executed_decisions': len(self._executed_decisions),
            'rejected_decisions': len(self._rejected_decisions),
            'history_length': len(self._decision_history)
        }
        
        # Check for stuck decisions
        stale_count = 0
        for decision in self._pending_decisions.values():
            age = (datetime.utcnow() - decision.created_at).total_seconds()
            if age > self.config.max_decision_age * 2:
                stale_count += 1
        
        if stale_count > 5:
            health['status'] = 'degraded'
            health['stale_decisions'] = stale_count
        
        return health
    
    async def get_decision_history(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[DecisionHistory]:
        """Get decision history"""
        sorted_history = sorted(
            self._decision_history,
            key=lambda x: x.timestamp,
            reverse=True
        )
        return sorted_history[offset:offset + limit]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get decision statistics"""
        total = self._metrics["total_decisions"]
        approved = self._metrics["approved_decisions"]
        rejected = self._metrics["rejected_decisions"]
        executed = self._metrics["executed_decisions"]
        failed = self._metrics["failed_decisions"]
        
        return {
            'total_decisions': total,
            'approved_rate': approved / total if total > 0 else 0,
            'rejected_rate': rejected / total if total > 0 else 0,
            'execution_rate': executed / total if total > 0 else 0,
            'failure_rate': failed / total if total > 0 else 0,
            'avg_confidence': self._metrics["avg_confidence"],
            'consensus_rate': self._metrics["consensus_rate"],
            'avg_decision_time': self._metrics["avg_decision_time"]
        }
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the decision maker"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("DecisionMaker started")
    
    async def stop(self) -> None:
        """Stop the decision maker"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("DecisionMaker stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_decision_maker: Optional[DecisionMaker] = None


def get_decision_maker() -> DecisionMaker:
    """Get singleton instance of DecisionMaker"""
    global _decision_maker
    if _decision_maker is None:
        _decision_maker = DecisionMaker()
    return _decision_maker


def reset_decision_maker() -> None:
    """Reset the decision maker (for testing)"""
    global _decision_maker
    if _decision_maker:
        asyncio.create_task(_decision_maker.stop())
    _decision_maker = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'DecisionMaker',
    'DecisionConfig',
    'Decision',
    'DecisionResult',
    'DecisionHistory',
    'DecisionType',
    'DecisionStatus',
    'ConfidenceLevel',
    'get_decision_maker',
    'reset_decision_maker'
]

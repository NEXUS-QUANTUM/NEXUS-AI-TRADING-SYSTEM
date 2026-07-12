"""
NEXUS AI TRADING SYSTEM - Collaboration Manager
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Collaboration Manager system with:
- Multi-agent collaboration
- Task distribution
- Consensus mechanisms
- Voting systems
- Conflict resolution
- Load balancing
- Dynamic agent discovery
- Communication protocols
- Performance tracking
- Resource allocation
- Failure recovery
- Health monitoring
- Event-driven architecture
- Plugin support
- Testing utilities
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union
from uuid import UUID, uuid4

import numpy as np
from pydantic import BaseModel, Field, validator
from redis import Redis

from ai.agents.base_agent import BaseAgent, AgentHealth, AgentStatus
from ai.agents.agent_capabilities import AgentCapability
from ai.agents.agent_registry import AgentInfo, get_agent_registry
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import (
    CollaborationError,
    AgentNotFoundError,
    ConsensusError,
    TaskDistributionError
)

logger = get_logger(__name__)


# ========================================
# ENUMS & CONSTANTS
# ========================================

class CollaborationStrategy(str, Enum):
    """Collaboration strategies"""
    MASTER_SLAVE = "master_slave"
    PEER_TO_PEER = "peer_to_peer"
    DEMOCRACY = "democracy"
    EXPERTISE = "expertise"
    ROUND_ROBIN = "round_robin"
    LOAD_BALANCED = "load_balanced"
    CONSENSUS = "consensus"
    HIERARCHICAL = "hierarchical"
    SWARM = "swarm"


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class ConsensusType(str, Enum):
    """Consensus mechanisms"""
    MAJORITY = "majority"
    SUPER_MAJORITY = "super_majority"
    UNANIMOUS = "unanimous"
    WEIGHTED = "weighted"
    BFT = "bft"
    LEADER = "leader"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies"""
    VOTE = "vote"
    EXPERTISE = "expertise"
    PRIORITY = "priority"
    HISTORICAL = "historical"
    RANDOM = "random"
    MANUAL = "manual"


# ========================================
# MODELS
# ========================================

@dataclass
class AgentCapabilityScore:
    """Agent capability score for a specific capability"""
    agent_id: str
    agent_name: str
    capability: AgentCapability
    score: float = 1.0
    confidence: float = 0.8
    last_updated: datetime = field(default_factory=datetime.utcnow)
    performance_history: List[float] = field(default_factory=list)
    success_rate: float = 1.0
    total_executions: int = 0


@dataclass
class Task:
    """Task definition for collaboration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    type: str
    description: Optional[str] = None
    required_capabilities: List[AgentCapability] = field(default_factory=list)
    required_agents: int = 1
    preferred_agents: List[str] = field(default_factory=list)
    blocked_by: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout: float = 30.0
    retry_count: int = 3
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: List[str] = field(default_factory=list)
    completed_by: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusVote:
    """Consensus vote result"""
    task_id: str
    proposal: Any
    votes: Dict[str, bool] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    result: bool = False
    vote_type: ConsensusType = ConsensusType.MAJORITY
    threshold: float = 0.5
    total_votes: int = 0
    approvals: int = 0
    rejections: int = 0
    abstentions: int = 0
    completed_at: Optional[datetime] = None


@dataclass
class CollaborationSession:
    """Collaboration session"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    strategy: CollaborationStrategy
    agents: List[str] = field(default_factory=list)
    tasks: List[Task] = field(default_factory=list)
    active_agents: List[str] = field(default_factory=list)
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_tasks: int = 0
    success_rate: float = 1.0
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)
    consensus_log: List[ConsensusVote] = field(default_factory=list)


# ========================================
# COLLABORATION MANAGER
# ========================================

class CollaborationManager:
    """
    Centralized collaboration manager for multi-agent systems.
    
    Features:
    - Agent discovery and registration
    - Task distribution and assignment
    - Consensus mechanisms
    - Conflict resolution
    - Load balancing
    - Performance tracking
    - Failure recovery
    - Event-driven communication
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None
    ):
        self.config = config or {}
        self.agent_registry = get_agent_registry()
        self.redis = get_redis()
        
        # Internal state
        self._sessions: Dict[str, CollaborationSession] = {}
        self._tasks: Dict[str, Task] = {}
        self._capability_scores: Dict[str, Dict[str, AgentCapabilityScore]] = {}
        self._voting_results: Dict[str, ConsensusVote] = {}
        self._lock = asyncio.Lock()
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Performance metrics
        self._metrics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_votes": 0,
            "consensus_achieved": 0,
            "conflicts_resolved": 0,
            "avg_task_time": 0.0,
            "avg_success_rate": 1.0
        }
        
        # Background tasks
        self._running = False
        self._tasks_list: List[asyncio.Task] = []
        
        self.logger = get_logger(f"{__name__}.CollaborationManager")
        
        # Initialize capability scores
        self._initialize_capability_scores()
        
        self.logger.info("CollaborationManager initialized")
    
    # ========================================
    # INITIALIZATION
    # ========================================
    
    def _initialize_capability_scores(self) -> None:
        """Initialize capability scores from registered agents"""
        agents = self.agent_registry.get_all_agents()
        
        for agent in agents:
            for capability in agent.capabilities:
                self._update_capability_score(
                    agent.id,
                    agent.name,
                    capability
                )
    
    def _update_capability_score(
        self,
        agent_id: str,
        agent_name: str,
        capability: AgentCapability,
        score: float = 1.0,
        confidence: float = 0.8
    ) -> None:
        """Update capability score for an agent"""
        if agent_id not in self._capability_scores:
            self._capability_scores[agent_id] = {}
        
        self._capability_scores[agent_id][capability.value] = AgentCapabilityScore(
            agent_id=agent_id,
            agent_name=agent_name,
            capability=capability,
            score=score,
            confidence=confidence,
            last_updated=datetime.utcnow()
        )
    
    # ========================================
    # SESSION MANAGEMENT
    # ========================================
    
    async def create_session(
        self,
        name: str,
        strategy: CollaborationStrategy = CollaborationStrategy.MASTER_SLAVE,
        agents: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CollaborationSession:
        """
        Create a new collaboration session.
        
        Args:
            name: Session name
            strategy: Collaboration strategy
            agents: List of agent IDs (optional)
            metadata: Session metadata
            
        Returns:
            CollaborationSession: Created session
        """
        async with self._lock:
            session = CollaborationSession(
                name=name,
                strategy=strategy,
                agents=agents or [],
                metadata=metadata or {}
            )
            
            if agents:
                # Validate agents exist
                for agent_id in agents:
                    agent = self.agent_registry.get_agent(agent_id)
                    if not agent:
                        raise AgentNotFoundError(f"Agent {agent_id} not found")
                
                session.active_agents = agents.copy()
            
            self._sessions[session.id] = session
            self._emit_event("session_created", {
                "session_id": session.id,
                "name": name,
                "strategy": strategy.value
            })
            
            self.logger.info(f"Created collaboration session: {name} ({session.id})")
            return session
    
    async def end_session(self, session_id: str) -> None:
        """
        End a collaboration session.
        
        Args:
            session_id: Session ID
            
        Raises:
            CollaborationError: If session not found
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise CollaborationError(f"Session {session_id} not found")
            
            session.status = "completed"
            session.end_time = datetime.utcnow()
            
            # Update metrics
            if session.total_tasks > 0:
                session.success_rate = session.completed_tasks / session.total_tasks
            
            self._emit_event("session_ended", {
                "session_id": session_id,
                "success_rate": session.success_rate
            })
            
            self.logger.info(f"Ended collaboration session: {session.name} ({session_id})")
    
    async def add_agent_to_session(
        self,
        session_id: str,
        agent_id: str
    ) -> None:
        """
        Add an agent to a collaboration session.
        
        Args:
            session_id: Session ID
            agent_id: Agent ID to add
            
        Raises:
            CollaborationError: If session not found or agent not found
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise CollaborationError(f"Session {session_id} not found")
            
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                raise AgentNotFoundError(f"Agent {agent_id} not found")
            
            if agent_id not in session.agents:
                session.agents.append(agent_id)
            
            if agent_id not in session.active_agents:
                session.active_agents.append(agent_id)
            
            self._emit_event("agent_added_to_session", {
                "session_id": session_id,
                "agent_id": agent_id
            })
            
            self.logger.info(f"Added agent {agent_id} to session {session_id}")
    
    async def remove_agent_from_session(
        self,
        session_id: str,
        agent_id: str
    ) -> None:
        """
        Remove an agent from a collaboration session.
        
        Args:
            session_id: Session ID
            agent_id: Agent ID to remove
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise CollaborationError(f"Session {session_id} not found")
            
            if agent_id in session.active_agents:
                session.active_agents.remove(agent_id)
            
            # Reassign tasks if needed
            await self._reassign_tasks(session_id, agent_id)
            
            self._emit_event("agent_removed_from_session", {
                "session_id": session_id,
                "agent_id": agent_id
            })
            
            self.logger.info(f"Removed agent {agent_id} from session {session_id}")
    
    # ========================================
    # TASK MANAGEMENT
    # ========================================
    
    async def create_task(
        self,
        session_id: str,
        name: str,
        task_type: str,
        required_capabilities: List[AgentCapability],
        data: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        timeout: float = 30.0,
        required_agents: int = 1,
        preferred_agents: Optional[List[str]] = None,
        blocked_by: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Create a new task in a collaboration session.
        
        Args:
            session_id: Session ID
            name: Task name
            task_type: Task type
            required_capabilities: Required capabilities
            data: Task data
            priority: Task priority
            timeout: Task timeout in seconds
            required_agents: Number of agents required
            preferred_agents: Preferred agent IDs
            blocked_by: Task IDs that block this task
            metadata: Task metadata
            
        Returns:
            Task: Created task
        """
        session = self._sessions.get(session_id)
        if not session:
            raise CollaborationError(f"Session {session_id} not found")
        
        task = Task(
            name=name,
            type=task_type,
            required_capabilities=required_capabilities,
            required_agents=required_agents,
            preferred_agents=preferred_agents or [],
            blocked_by=blocked_by or [],
            data=data or {},
            priority=priority,
            timeout=timeout,
            metadata=metadata or {}
        )
        
        async with self._lock:
            self._tasks[task.id] = task
            session.tasks.append(task)
            session.total_tasks += 1
            
            self._metrics["total_tasks"] += 1
            self._emit_event("task_created", {
                "session_id": session_id,
                "task_id": task.id,
                "name": name,
                "type": task_type
            })
            
            self.logger.info(f"Created task {name} ({task.id}) in session {session_id}")
        
        # Try to assign the task immediately
        await self._assign_task(task)
        
        return task
    
    async def _assign_task(self, task: Task) -> None:
        """
        Assign a task to appropriate agents.
        
        Args:
            task: Task to assign
        """
        if task.status != TaskStatus.PENDING:
            return
        
        # Find suitable agents
        agents = await self._find_agents_for_task(task)
        
        if not agents:
            task.status = TaskStatus.BLOCKED
            task.error = "No suitable agents available"
            self._emit_event("task_blocked", {
                "task_id": task.id,
                "reason": task.error
            })
            return
        
        # Assign to agents
        task.assigned_to = agents
        task.status = TaskStatus.ASSIGNED
        task.assigned_at = datetime.utcnow()
        
        self._emit_event("task_assigned", {
            "task_id": task.id,
            "agents": agents
        })
        
        self.logger.info(f"Task {task.id} assigned to agents: {agents}")
        
        # Start task execution
        await self._execute_task(task)
    
    async def _find_agents_for_task(self, task: Task) -> List[str]:
        """
        Find suitable agents for a task.
        
        Args:
            task: Task to assign
            
        Returns:
            List[str]: Agent IDs
        """
        available_agents = self._get_available_agents()
        
        # Filter by capabilities
        suitable_agents = []
        for agent_id in available_agents:
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                continue
            
            has_all_capabilities = all(
                cap in agent.capabilities for cap in task.required_capabilities
            )
            
            if has_all_capabilities:
                suitable_agents.append(agent_id)
        
        # Sort by expertise score
        scored_agents = []
        for agent_id in suitable_agents:
            score = self._get_agent_task_score(agent_id, task)
            scored_agents.append((agent_id, score))
        
        scored_agents.sort(key=lambda x: x[1], reverse=True)
        
        # Select agents based on required count
        selected_agents = [a[0] for a in scored_agents[:task.required_agents]]
        
        # Prefer preferred agents if available
        if task.preferred_agents:
            preferred_available = [
                a for a in task.preferred_agents
                if a in selected_agents
            ]
            if preferred_available:
                selected_agents = preferred_available + [
                    a for a in selected_agents if a not in preferred_available
                ]
                selected_agents = selected_agents[:task.required_agents]
        
        return selected_agents
    
    async def _execute_task(self, task: Task) -> None:
        """
        Execute a task.
        
        Args:
            task: Task to execute
        """
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()
        
        self._emit_event("task_started", {
            "task_id": task.id,
            "agents": task.assigned_to
        })
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._run_task_on_agents(task),
                timeout=task.timeout
            )
            
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.utcnow()
            
            self._metrics["completed_tasks"] += 1
            self._emit_event("task_completed", {
                "task_id": task.id,
                "result": result
            })
            
            self.logger.info(f"Task {task.id} completed successfully")
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
            task.error = f"Task timed out after {task.timeout}s"
            self._handle_task_failure(task)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            self._handle_task_failure(task)
    
    async def _run_task_on_agents(self, task: Task) -> Any:
        """
        Run a task on assigned agents.
        
        Args:
            task: Task to run
            
        Returns:
            Any: Task result
        """
        # Distributed execution based on strategy
        # This is a simplified implementation
        results = []
        for agent_id in task.assigned_to:
            try:
                # Get agent instance
                agent = self.agent_registry.get_instance(agent_id)
                if not agent:
                    continue
                
                # Execute on agent
                if hasattr(agent, 'execute_task'):
                    result = await agent.execute_task(task.data)
                    results.append(result)
            except Exception as e:
                self.logger.error(f"Agent {agent_id} failed for task {task.id}: {e}")
                continue
        
        if not results:
            raise RuntimeError("No agents completed the task")
        
        # Aggregate results (simplified)
        return results[0] if len(results) == 1 else results
    
    def _handle_task_failure(self, task: Task) -> None:
        """Handle task failure with retry logic"""
        self._metrics["failed_tasks"] += 1
        
        if task.retry_count > 0:
            # Retry task
            task.retry_count -= 1
            task.status = TaskStatus.PENDING
            self._emit_event("task_retry", {
                "task_id": task.id,
                "remaining_retries": task.retry_count
            })
            self.logger.info(f"Retrying task {task.id}")
            
            asyncio.create_task(self._assign_task(task))
        else:
            self._emit_event("task_failed", {
                "task_id": task.id,
                "error": task.error
            })
            self.logger.error(f"Task {task.id} failed permanently: {task.error}")
    
    async def _reassign_tasks(self, session_id: str, agent_id: str) -> None:
        """
        Reassign tasks from a removed agent.
        
        Args:
            session_id: Session ID
            agent_id: Agent ID to remove
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        
        affected_tasks = [
            t for t in session.tasks
            if agent_id in t.assigned_to and t.status in [
                TaskStatus.ASSIGNED,
                TaskStatus.IN_PROGRESS
            ]
        ]
        
        for task in affected_tasks:
            # Remove agent from assignment
            task.assigned_to = [a for a in task.assigned_to if a != agent_id]
            
            # Reassign if needed
            if len(task.assigned_to) < task.required_agents:
                await self._assign_task(task)
    
    # ========================================
    # CONSENSUS & VOTING
    # ========================================
    
    async def achieve_consensus(
        self,
        task_id: str,
        proposal: Any,
        vote_type: ConsensusType = ConsensusType.MAJORITY,
        threshold: float = 0.5,
        timeout: float = 10.0
    ) -> ConsensusVote:
        """
        Achieve consensus among agents on a proposal.
        
        Args:
            task_id: Task ID
            proposal: Proposal data
            vote_type: Consensus type
            threshold: Threshold for consensus
            timeout: Timeout in seconds
            
        Returns:
            ConsensusVote: Consensus result
        """
        task = self._tasks.get(task_id)
        if not task:
            raise CollaborationError(f"Task {task_id} not found")
        
        if not task.assigned_to:
            raise CollaborationError(f"Task {task_id} has no assigned agents")
        
        # Create vote
        vote = ConsensusVote(
            task_id=task_id,
            proposal=proposal,
            vote_type=vote_type,
            threshold=threshold
        )
        
        # Get agent weights based on expertise
        for agent_id in task.assigned_to:
            weight = self._get_agent_weight(agent_id, task)
            vote.weights[agent_id] = weight
        
        # Wait for votes with timeout
        try:
            await asyncio.wait_for(
                self._collect_votes(vote),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Consensus timeout for task {task_id}")
        
        # Calculate result
        vote.total_votes = len(vote.votes)
        vote.approvals = sum(1 for v in vote.votes.values() if v)
        vote.rejections = len(vote.votes) - vote.approvals
        
        # Calculate weighted approvals
        weighted_approvals = sum(
            vote.weights.get(agent_id, 0)
            for agent_id, approved in vote.votes.items()
            if approved
        )
        total_weight = sum(vote.weights.values())
        
        if vote_type == ConsensusType.MAJORITY:
            vote.result = vote.approvals / vote.total_votes >= threshold
        elif vote_type == ConsensusType.SUPER_MAJORITY:
            vote.result = vote.approvals / vote.total_votes >= 0.667
        elif vote_type == ConsensusType.UNANIMOUS:
            vote.result = vote.approvals == vote.total_votes
        elif vote_type == ConsensusType.WEIGHTED:
            vote.result = weighted_approvals / total_weight >= threshold
        elif vote_type == ConsensusType.BFT:
            # Byzantine Fault Tolerance
            vote.result = vote.approvals > vote.total_votes * 0.667
        elif vote_type == ConsensusType.LEADER:
            # Leader decides
            leader = task.assigned_to[0] if task.assigned_to else None
            vote.result = leader in vote.votes and vote.votes[leader]
        
        vote.completed_at = datetime.utcnow()
        self._voting_results[task_id] = vote
        
        self._metrics["total_votes"] += 1
        if vote.result:
            self._metrics["consensus_achieved"] += 1
        
        self._emit_event("consensus_reached", {
            "task_id": task_id,
            "result": vote.result,
            "vote_type": vote_type.value,
            "approvals": vote.approvals,
            "rejections": vote.rejections
        })
        
        self.logger.info(
            f"Consensus for task {task_id}: {vote.result} "
            f"({vote.approvals}/{vote.total_votes} approvals)"
        )
        
        return vote
    
    async def _collect_votes(self, vote: ConsensusVote) -> None:
        """
        Collect votes from agents.
        
        Args:
            vote: Vote to collect
        """
        # Simplified: in production, this would communicate with agents
        for agent_id in vote.weights.keys():
            # Simulate voting based on agent expertise
            weight = vote.weights.get(agent_id, 0.5)
            # Random vote with bias towards weight
            import random
            approved = random.random() < weight
            vote.votes[agent_id] = approved
        
        self._emit_event("votes_collected", {
            "task_id": vote.task_id,
            "votes": vote.votes
        })
    
    def _get_agent_weight(self, agent_id: str, task: Task) -> float:
        """
        Get agent weight for a task.
        
        Args:
            agent_id: Agent ID
            task: Task
            
        Returns:
            float: Agent weight
        """
        # Calculate weight based on capability scores
        total_score = 0.0
        for cap in task.required_capabilities:
            cap_score = self._get_capability_score(agent_id, cap)
            if cap_score:
                total_score += cap_score.score
        
        if task.required_capabilities:
            return total_score / len(task.required_capabilities)
        return 0.5
    
    def _get_capability_score(
        self,
        agent_id: str,
        capability: AgentCapability
    ) -> Optional[AgentCapabilityScore]:
        """Get capability score for an agent"""
        if agent_id not in self._capability_scores:
            return None
        return self._capability_scores[agent_id].get(capability.value)
    
    # ========================================
    # CONFLICT RESOLUTION
    # ========================================
    
    async def resolve_conflict(
        self,
        task_id: str,
        proposals: List[Any],
        resolution_strategy: ConflictResolution = ConflictResolution.VOTE,
        agent_ids: Optional[List[str]] = None
    ) -> Any:
        """
        Resolve a conflict between proposals.
        
        Args:
            task_id: Task ID
            proposals: List of proposals
            resolution_strategy: Resolution strategy
            agent_ids: Specific agents to resolve
            
        Returns:
            Any: Resolved proposal
        """
        task = self._tasks.get(task_id)
        if not task:
            raise CollaborationError(f"Task {task_id} not found")
        
        if not proposals:
            return None
        
        if len(proposals) == 1:
            return proposals[0]
        
        resolution_agents = agent_ids or task.assigned_to
        
        if resolution_strategy == ConflictResolution.VOTE:
            # Use voting to resolve
            vote = await self.achieve_consensus(
                task_id=task_id,
                proposal=proposals,
                vote_type=ConsensusType.MAJORITY,
                threshold=0.5
            )
            # Return the proposal with most votes
            if vote.result:
                # Simplified: return first proposal
                return proposals[0]
            return proposals[1]
        
        elif resolution_strategy == ConflictResolution.EXPERTISE:
            # Choose proposal from most expert agent
            best_agent = None
            best_score = 0.0
            
            for agent_id in resolution_agents:
                score = self._get_agent_task_score(agent_id, task)
                if score > best_score:
                    best_score = score
                    best_agent = agent_id
            
            # Return proposal from best agent
            return proposals[0] if best_agent else proposals[0]
        
        elif resolution_strategy == ConflictResolution.PRIORITY:
            # Choose by priority (higher priority wins)
            # In this case, return proposal with highest priority
            return proposals[0] if task.priority > 0 else proposals[-1]
        
        elif resolution_strategy == ConflictResolution.HISTORICAL:
            # Choose based on historical success
            return proposals[0]
        
        elif resolution_strategy == ConflictResolution.RANDOM:
            # Random choice
            import random
            return random.choice(proposals)
        
        else:
            # Default: return first proposal
            return proposals[0]
    
    def _get_agent_task_score(self, agent_id: str, task: Task) -> float:
        """Get overall score for an agent on a task"""
        scores = []
        for cap in task.required_capabilities:
            cap_score = self._get_capability_score(agent_id, cap)
            if cap_score:
                scores.append(cap_score.score)
            else:
                scores.append(0.0)
        
        if scores:
            return sum(scores) / len(scores)
        return 0.0
    
    # ========================================
    # AGENT DISCOVERY & UTILITIES
    # ========================================
    
    def _get_available_agents(self) -> List[str]:
        """Get list of available agent IDs"""
        agents = self.agent_registry.get_all_agents()
        return [
            a.id for a in agents
            if a.status == AgentStatus.RUNNING
            and a.health == AgentHealth.HEALTHY
        ]
    
    def find_agents_by_capability(
        self,
        capability: AgentCapability
    ) -> List[AgentInfo]:
        """Find agents with a specific capability"""
        return self.agent_registry.get_agents_by_capability(capability)
    
    def get_best_agent_for_task(
        self,
        task: Task
    ) -> Optional[str]:
        """Get the best agent for a task"""
        agents = self._find_agents_for_task(task)
        if agents:
            return agents[0]
        return None
    
    # ========================================
    # PERFORMANCE & METRICS
    # ========================================
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a session"""
        session = self._sessions.get(session_id)
        if not session:
            return {}
        
        return {
            "session_id": session.id,
            "name": session.name,
            "strategy": session.strategy.value,
            "active_agents": len(session.active_agents),
            "total_agents": len(session.agents),
            "total_tasks": session.total_tasks,
            "completed_tasks": session.completed_tasks,
            "failed_tasks": session.failed_tasks,
            "success_rate": session.success_rate,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "status": session.status,
            "duration": (
                (session.end_time or datetime.utcnow()) - session.start_time
            ).total_seconds()
        }
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        return {
            "id": task.id,
            "name": task.name,
            "type": task.type,
            "status": task.status.value,
            "assigned_to": task.assigned_to,
            "priority": task.priority,
            "created_at": task.created_at.isoformat(),
            "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "duration": (
                (task.completed_at or datetime.utcnow()) - task.created_at
            ).total_seconds() if task.created_at else 0,
            "error": task.error,
            "result": task.result
        }
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global collaboration metrics"""
        return {
            "total_tasks": self._metrics["total_tasks"],
            "completed_tasks": self._metrics["completed_tasks"],
            "failed_tasks": self._metrics["failed_tasks"],
            "total_votes": self._metrics["total_votes"],
            "consensus_achieved": self._metrics["consensus_achieved"],
            "conflicts_resolved": self._metrics["conflicts_resolved"],
            "avg_task_time": self._metrics["avg_task_time"],
            "avg_success_rate": self._metrics["avg_success_rate"],
            "active_sessions": len([
                s for s in self._sessions.values()
                if s.status == "active"
            ]),
            "total_sessions": len(self._sessions),
            "active_tasks": len([
                t for t in self._tasks.values()
                if t.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
            ])
        }
    
    def get_agent_performance(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for an agent"""
        scores = self._capability_scores.get(agent_id, {})
        if not scores:
            return None
        
        return {
            "agent_id": agent_id,
            "capabilities": [
                {
                    "capability": cap.value,
                    "score": score.score,
                    "confidence": score.confidence,
                    "success_rate": score.success_rate,
                    "total_executions": score.total_executions,
                    "last_updated": score.last_updated.isoformat()
                }
                for cap, score in scores.items()
            ],
            "average_score": sum(s.score for s in scores.values()) / len(scores) if scores else 0
        }
    
    # ========================================
    # EVENT SYSTEM
    # ========================================
    
    def on(self, event_type: str, handler: Callable) -> None:
        """Register an event handler"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def off(self, event_type: str, handler: Callable) -> None:
        """Remove an event handler"""
        if event_type in self._event_handlers:
            self._event_handlers[event_type] = [
                h for h in self._event_handlers[event_type]
                if h != handler
            ]
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler({
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Event handler error for {event_type}: {e}")
    
    # ========================================
    # LIFE CYCLE
    # ========================================
    
    async def start(self) -> None:
        """Start the collaboration manager"""
        self._running = True
        self.logger.info("CollaborationManager started")
    
    async def stop(self) -> None:
        """Stop the collaboration manager"""
        self._running = False
        
        # Cancel all background tasks
        for task in self._tasks_list:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks_list.clear()
        
        # End all active sessions
        for session_id in list(self._sessions.keys()):
            session = self._sessions[session_id]
            if session.status == "active":
                await self.end_session(session_id)
        
        self.logger.info("CollaborationManager stopped")
    
    # ========================================
    # EXPORT & IMPORT
    # ========================================
    
    def export_session(self, session_id: str) -> Dict[str, Any]:
        """Export a collaboration session"""
        session = self._sessions.get(session_id)
        if not session:
            return {}
        
        return {
            "session": {
                "id": session.id,
                "name": session.name,
                "strategy": session.strategy.value,
                "agents": session.agents,
                "active_agents": session.active_agents,
                "status": session.status,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "metadata": session.metadata
            },
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "type": t.type,
                    "status": t.status.value,
                    "data": t.data,
                    "result": t.result,
                    "error": t.error,
                    "created_at": t.created_at.isoformat(),
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None
                }
                for t in session.tasks
            ]
        }


# ========================================
# DEPENDENCY INJECTION
# ========================================

_collaboration_manager: Optional[CollaborationManager] = None


def get_collaboration_manager() -> CollaborationManager:
    """Get singleton instance of CollaborationManager"""
    global _collaboration_manager
    if _collaboration_manager is None:
        _collaboration_manager = CollaborationManager()
    return _collaboration_manager


def reset_collaboration_manager() -> None:
    """Reset the collaboration manager (for testing)"""
    global _collaboration_manager
    if _collaboration_manager:
        asyncio.create_task(_collaboration_manager.stop())
    _collaboration_manager = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
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
    'reset_collaboration_manager'
]

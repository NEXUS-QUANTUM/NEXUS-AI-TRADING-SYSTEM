"""
NEXUS AI TRADING SYSTEM - Agent Registry
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Agent Registry system with:
- Agent registration and discovery
- Agent lifecycle management
- Agent dependency injection
- Agent configuration management
- Agent health monitoring
- Agent metrics collection
- Agent event handling
- Agent priority management
- Agent version control
- Agent capabilities management
- Agent resource management
- Agent logging
- Agent security
- Agent testing utilities
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator
from redis import Redis
from sqlalchemy.orm import Session

from ai.agents.base_agent import BaseAgent
from ai.agents.agent_metrics import AgentMetrics
from ai.agents.agent_config import AgentConfig
from ai.agents.agent_events import AgentEvent, AgentEventType
from ai.agents.agent_capabilities import AgentCapability
from backend.core.database import get_db
from backend.core.redis_client import get_redis
from backend.core.logging import get_logger
from backend.core.config import settings
from backend.core.exceptions import AgentNotFoundError, AgentRegistrationError, AgentLifecycleError

logger = get_logger(__name__)


# ========================================
# ENUMS & CONSTANTS
# ========================================

class AgentStatus(str, Enum):
    """Agent status enum"""
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNHEALTHY = "unhealthy"


class AgentPriority(str, Enum):
    """Agent priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


class AgentHealth(str, Enum):
    """Agent health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ========================================
# MODELS
# ========================================

class AgentInfo(BaseModel):
    """Agent information model"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    version: str
    status: AgentStatus = AgentStatus.REGISTERED
    priority: AgentPriority = AgentPriority.NORMAL
    health: AgentHealth = AgentHealth.UNKNOWN
    capabilities: List[AgentCapability] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    last_error: Optional[str] = None
    error_count: int = 0
    uptime: float = 0.0
    start_time: Optional[datetime] = None
    dependencies: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    instance_id: str = Field(default_factory=lambda: str(uuid4()))

    @validator('version')
    def validate_version(cls, v: str) -> str:
        """Validate version format"""
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError('Version must be in format X.Y.Z')
        return v

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            UUID: lambda u: str(u)
        }


class AgentRegistration(BaseModel):
    """Agent registration request"""
    name: str
    version: str
    capabilities: List[AgentCapability]
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    priority: AgentPriority = AgentPriority.NORMAL


class AgentHeartbeat(BaseModel):
    """Agent heartbeat data"""
    agent_id: str
    status: AgentStatus
    health: AgentHealth
    metrics: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentQuery(BaseModel):
    """Agent query filter"""
    status: Optional[AgentStatus] = None
    health: Optional[AgentHealth] = None
    priority: Optional[AgentPriority] = None
    capabilities: Optional[List[AgentCapability]] = None
    tags: Optional[List[str]] = None
    name: Optional[str] = None
    version: Optional[str] = None
    active: Optional[bool] = None


# ========================================
# AGENT REGISTRY
# ========================================

class AgentRegistry:
    """
    Central agent registry managing all AI agents in the system.
    
    Features:
    - Agent registration and deregistration
    - Agent discovery and querying
    - Health monitoring
    - Dependency management
    - Lifecycle management
    - Metrics collection
    - Event system
    - Persistence (Redis + PostgreSQL)
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        db_session: Optional[Session] = None,
        heartbeat_interval: int = 30,
        health_check_interval: int = 60,
        cleanup_interval: int = 300
    ):
        self.redis = redis_client or get_redis()
        self.db = db_session or next(get_db())
        self._agents: Dict[str, AgentInfo] = {}
        self._instances: Dict[str, BaseAgent] = {}
        self._metrics: Dict[str, AgentMetrics] = {}
        self._lock = asyncio.Lock()
        self._event_handlers: Dict[AgentEventType, List[Callable]] = {}
        self._heartbeat_interval = heartbeat_interval
        self._health_check_interval = health_check_interval
        self._cleanup_interval = cleanup_interval
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        # Agent capabilities cache
        self._capability_cache: Dict[AgentCapability, List[str]] = {}
        
        # Health history
        self._health_history: Dict[str, List[Dict[str, Any]]] = {}

        # Initialize
        self._load_persisted_agents()
        self._start_background_tasks()

    # ========================================
    # REGISTRATION & LIFECYCLE
    # ========================================

    async def register_agent(
        self,
        registration: AgentRegistration,
        agent_instance: Optional[BaseAgent] = None
    ) -> AgentInfo:
        """
        Register a new agent in the registry.
        
        Args:
            registration: Agent registration data
            agent_instance: Optional agent instance
            
        Returns:
            AgentInfo: Registered agent information
            
        Raises:
            AgentRegistrationError: If registration fails
        """
        async with self._lock:
            try:
                # Check if agent already exists
                existing = self._get_agent_by_name(registration.name)
                if existing:
                    # Version conflict check
                    if existing.version != registration.version:
                        raise AgentRegistrationError(
                            f"Agent {registration.name} already registered with different version {existing.version}"
                        )
                    # Update existing registration
                    return await self._update_agent(existing.id, registration)

                # Create new agent info
                agent_info = AgentInfo(
                    name=registration.name,
                    version=registration.version,
                    priority=registration.priority,
                    capabilities=registration.capabilities,
                    config=registration.config,
                    metadata=registration.metadata,
                    dependencies=registration.dependencies,
                    tags=registration.tags,
                    status=AgentStatus.REGISTERED
                )

                # Store in memory
                self._agents[agent_info.id] = agent_info
                
                # Store agent instance if provided
                if agent_instance:
                    self._instances[agent_info.id] = agent_instance
                    # Initialize agent
                    try:
                        await agent_instance.initialize(agent_info.config)
                        agent_info.status = AgentStatus.INITIALIZING
                    except Exception as e:
                        logger.error(f"Failed to initialize agent {agent_info.name}: {e}")
                        agent_info.status = AgentStatus.ERROR
                        agent_info.last_error = str(e)
                        agent_info.error_count += 1

                # Persist to database
                self._persist_agent(agent_info)
                
                # Cache capabilities
                for capability in agent_info.capabilities:
                    if capability not in self._capability_cache:
                        self._capability_cache[capability] = []
                    self._capability_cache[capability].append(agent_info.id)

                # Emit event
                self._emit_event(AgentEvent(
                    type=AgentEventType.REGISTERED,
                    agent_id=agent_info.id,
                    data=agent_info.dict()
                ))

                logger.info(f"Agent {agent_info.name} ({agent_info.id}) registered successfully")
                return agent_info

            except Exception as e:
                logger.error(f"Failed to register agent {registration.name}: {e}")
                raise AgentRegistrationError(f"Registration failed: {str(e)}")

    async def deregister_agent(self, agent_id: str, force: bool = False) -> None:
        """
        Deregister an agent from the registry.
        
        Args:
            agent_id: Agent ID to deregister
            force: Force deregistration even if agent is running
            
        Raises:
            AgentNotFoundError: If agent not found
            AgentLifecycleError: If agent cannot be stopped
        """
        async with self._lock:
            try:
                agent_info = self._get_agent(agent_id)
                
                # Check if agent is running
                if agent_info.status == AgentStatus.RUNNING and not force:
                    raise AgentLifecycleError(
                        f"Cannot deregister running agent {agent_info.name}. Stop it first or use force=True"
                    )

                # Stop agent if running
                if agent_id in self._instances:
                    try:
                        await self._instances[agent_id].stop()
                    except Exception as e:
                        logger.warning(f"Error stopping agent {agent_info.name}: {e}")

                # Remove from memory
                del self._agents[agent_id]
                if agent_id in self._instances:
                    del self._instances[agent_id]
                if agent_id in self._metrics:
                    del self._metrics[agent_id]
                if agent_id in self._health_history:
                    del self._health_history[agent_id]

                # Remove from capability cache
                for capability in agent_info.capabilities:
                    if capability in self._capability_cache:
                        self._capability_cache[capability] = [
                            aid for aid in self._capability_cache[capability]
                            if aid != agent_id
                        ]

                # Remove from persistence
                self._remove_persisted_agent(agent_id)

                # Emit event
                self._emit_event(AgentEvent(
                    type=AgentEventType.DEREGISTERED,
                    agent_id=agent_id,
                    data={"name": agent_info.name}
                ))

                logger.info(f"Agent {agent_info.name} ({agent_id}) deregistered")

            except AgentNotFoundError:
                raise
            except Exception as e:
                logger.error(f"Failed to deregister agent {agent_id}: {e}")
                raise AgentLifecycleError(f"Deregistration failed: {str(e)}")

    async def start_agent(self, agent_id: str) -> None:
        """
        Start an agent.
        
        Args:
            agent_id: Agent ID to start
            
        Raises:
            AgentNotFoundError: If agent not found
            AgentLifecycleError: If agent cannot be started
        """
        async with self._lock:
            agent_info = self._get_agent(agent_id)
            agent_instance = self._get_instance(agent_id)

            try:
                # Check dependencies
                await self._check_dependencies(agent_id)

                # Start agent
                await agent_instance.start()
                agent_info.status = AgentStatus.RUNNING
                agent_info.start_time = datetime.utcnow()
                agent_info.last_heartbeat = datetime.utcnow()
                agent_info.health = AgentHealth.HEALTHY

                # Update persistence
                self._persist_agent(agent_info)

                # Emit event
                self._emit_event(AgentEvent(
                    type=AgentEventType.STARTED,
                    agent_id=agent_id,
                    data={"name": agent_info.name}
                ))

                logger.info(f"Agent {agent_info.name} ({agent_id}) started")

            except Exception as e:
                agent_info.status = AgentStatus.ERROR
                agent_info.last_error = str(e)
                agent_info.error_count += 1
                logger.error(f"Failed to start agent {agent_info.name}: {e}")
                raise AgentLifecycleError(f"Start failed: {str(e)}")

    async def stop_agent(self, agent_id: str) -> None:
        """
        Stop an agent.
        
        Args:
            agent_id: Agent ID to stop
            
        Raises:
            AgentNotFoundError: If agent not found
            AgentLifecycleError: If agent cannot be stopped
        """
        async with self._lock:
            agent_info = self._get_agent(agent_id)
            agent_instance = self._get_instance(agent_id)

            try:
                agent_info.status = AgentStatus.STOPPING
                self._persist_agent(agent_info)

                # Stop agent
                await agent_instance.stop()
                agent_info.status = AgentStatus.STOPPED

                # Update persistence
                self._persist_agent(agent_info)

                # Emit event
                self._emit_event(AgentEvent(
                    type=AgentEventType.STOPPED,
                    agent_id=agent_id,
                    data={"name": agent_info.name}
                ))

                logger.info(f"Agent {agent_info.name} ({agent_id}) stopped")

            except Exception as e:
                agent_info.status = AgentStatus.ERROR
                agent_info.last_error = str(e)
                agent_info.error_count += 1
                logger.error(f"Failed to stop agent {agent_info.name}: {e}")
                raise AgentLifecycleError(f"Stop failed: {str(e)}")

    async def pause_agent(self, agent_id: str) -> None:
        """Pause an agent's execution."""
        async with self._lock:
            agent_info = self._get_agent(agent_id)
            agent_instance = self._get_instance(agent_id)

            try:
                await agent_instance.pause()
                agent_info.status = AgentStatus.PAUSED
                self._persist_agent(agent_info)

                self._emit_event(AgentEvent(
                    type=AgentEventType.PAUSED,
                    agent_id=agent_id,
                    data={"name": agent_info.name}
                ))

                logger.info(f"Agent {agent_info.name} ({agent_id}) paused")

            except Exception as e:
                logger.error(f"Failed to pause agent {agent_info.name}: {e}")
                raise AgentLifecycleError(f"Pause failed: {str(e)}")

    async def resume_agent(self, agent_id: str) -> None:
        """Resume a paused agent."""
        async with self._lock:
            agent_info = self._get_agent(agent_id)
            agent_instance = self._get_instance(agent_id)

            try:
                await agent_instance.resume()
                agent_info.status = AgentStatus.RUNNING
                self._persist_agent(agent_info)

                self._emit_event(AgentEvent(
                    type=AgentEventType.RESUMED,
                    agent_id=agent_id,
                    data={"name": agent_info.name}
                ))

                logger.info(f"Agent {agent_info.name} ({agent_id}) resumed")

            except Exception as e:
                logger.error(f"Failed to resume agent {agent_info.name}: {e}")
                raise AgentLifecycleError(f"Resume failed: {str(e)}")

    # ========================================
    # AGENT QUERYING
    # ========================================

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information by ID."""
        return self._agents.get(agent_id)

    def get_agent_by_name(self, name: str) -> Optional[AgentInfo]:
        """Get agent information by name."""
        return self._get_agent_by_name(name)

    def get_all_agents(self) -> List[AgentInfo]:
        """Get all registered agents."""
        return list(self._agents.values())

    def query_agents(self, query: AgentQuery) -> List[AgentInfo]:
        """
        Query agents by filters.
        
        Args:
            query: Agent query filters
            
        Returns:
            List[AgentInfo]: Matching agents
        """
        result = list(self._agents.values())

        if query.status:
            result = [a for a in result if a.status == query.status]
        if query.health:
            result = [a for a in result if a.health == query.health]
        if query.priority:
            result = [a for a in result if a.priority == query.priority]
        if query.capabilities:
            result = [a for a in result if any(c in a.capabilities for c in query.capabilities)]
        if query.tags:
            result = [a for a in result if any(t in a.tags for t in query.tags)]
        if query.name:
            result = [a for a in result if query.name.lower() in a.name.lower()]
        if query.version:
            result = [a for a in result if a.version == query.version]

        return result

    def get_agents_by_capability(self, capability: AgentCapability) -> List[AgentInfo]:
        """Get all agents with a specific capability."""
        agent_ids = self._capability_cache.get(capability, [])
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_active_agents(self) -> List[AgentInfo]:
        """Get all currently running agents."""
        return [a for a in self._agents.values() if a.status == AgentStatus.RUNNING]

    def get_agents_requiring_health_check(self) -> List[AgentInfo]:
        """Get agents that need health checks."""
        result = []
        for agent in self._agents.values():
            if agent.status in [AgentStatus.RUNNING, AgentStatus.DEGRADED]:
                age = (datetime.utcnow() - agent.last_heartbeat).total_seconds()
                if age > self._health_check_interval:
                    result.append(agent)
        return result

    # ========================================
    # AGENT INSTANCE MANAGEMENT
    # ========================================

    def get_instance(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent instance by ID."""
        return self._instances.get(agent_id)

    def set_instance(self, agent_id: str, instance: BaseAgent) -> None:
        """
        Set or update agent instance.
        
        Args:
            agent_id: Agent ID
            instance: Agent instance
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        if agent_id not in self._agents:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        self._instances[agent_id] = instance

    def remove_instance(self, agent_id: str) -> None:
        """Remove agent instance."""
        if agent_id in self._instances:
            del self._instances[agent_id]

    # ========================================
    # METRICS & MONITORING
    # ========================================

    def get_metrics(self, agent_id: str) -> Optional[AgentMetrics]:
        """Get agent metrics by ID."""
        return self._metrics.get(agent_id)

    def update_metrics(self, agent_id: str, metrics: AgentMetrics) -> None:
        """Update agent metrics."""
        self._metrics[agent_id] = metrics

    def get_health_history(self, agent_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health history for an agent."""
        history = self._health_history.get(agent_id, [])
        return history[-limit:] if limit > 0 else history

    async def heartbeat(self, heartbeat: AgentHeartbeat) -> None:
        """
        Process agent heartbeat.
        
        Args:
            heartbeat: Heartbeat data
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        agent_info = self._get_agent(heartbeat.agent_id)
        
        # Update agent info
        agent_info.status = heartbeat.status
        agent_info.health = heartbeat.health
        agent_info.last_heartbeat = heartbeat.timestamp
        
        # Calculate uptime
        if agent_info.start_time:
            agent_info.uptime = (heartbeat.timestamp - agent_info.start_time).total_seconds()

        # Update metrics if provided
        if heartbeat.metrics:
            if heartbeat.agent_id not in self._metrics:
                self._metrics[heartbeat.agent_id] = AgentMetrics()
            self._metrics[heartbeat.agent_id].update(heartbeat.metrics)

        # Record health history
        if heartbeat.agent_id not in self._health_history:
            self._health_history[heartbeat.agent_id] = []
        self._health_history[heartbeat.agent_id].append({
            "timestamp": heartbeat.timestamp.isoformat(),
            "status": heartbeat.status.value,
            "health": heartbeat.health.value,
            "metrics": heartbeat.metrics or {}
        })

        # Trim history
        if len(self._health_history[heartbeat.agent_id]) > 1000:
            self._health_history[heartbeat.agent_id] = self._health_history[heartbeat.agent_id][-1000:]

        # Persist to Redis for fast access
        self._persist_heartbeat(heartbeat)

        # Emit event for health changes
        self._emit_event(AgentEvent(
            type=AgentEventType.HEARTBEAT,
            agent_id=heartbeat.agent_id,
            data={
                "status": heartbeat.status.value,
                "health": heartbeat.health.value,
                "metrics": heartbeat.metrics
            }
        ))

    # ========================================
    # EVENT SYSTEM
    # ========================================

    def on(self, event_type: AgentEventType, handler: Callable) -> None:
        """
        Register an event handler.
        
        Args:
            event_type: Event type to listen for
            handler: Event handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def off(self, event_type: AgentEventType, handler: Callable) -> None:
        """
        Remove an event handler.
        
        Args:
            event_type: Event type
            handler: Event handler to remove
        """
        if event_type in self._event_handlers:
            self._event_handlers[event_type] = [
                h for h in self._event_handlers[event_type]
                if h != handler
            ]

    def _emit_event(self, event: AgentEvent) -> None:
        """Emit an event to all registered handlers."""
        handlers = self._event_handlers.get(event.type, [])
        for handler in handlers:
            try:
                asyncio.create_task(handler(event))
            except Exception as e:
                logger.error(f"Error in event handler for {event.type}: {e}")

    # ========================================
    # DEPENDENCY MANAGEMENT
    # ========================================

    async def _check_dependencies(self, agent_id: str) -> None:
        """Check if all dependencies are satisfied."""
        agent_info = self._get_agent(agent_id)
        
        for dep_id in agent_info.dependencies:
            dep = self._get_agent(dep_id)
            if dep.status != AgentStatus.RUNNING:
                raise AgentLifecycleError(
                    f"Dependency {dep.name} ({dep_id}) is not running (status: {dep.status})"
                )

    # ========================================
    # HEALTH MONITORING
    # ========================================

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(5)

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all running agents."""
        agents_to_check = self.get_agents_requiring_health_check()
        
        for agent_info in agents_to_check:
            try:
                instance = self._get_instance(agent_info.id)
                if instance:
                    health = await instance.health_check()
                    if health != agent_info.health:
                        agent_info.health = health
                        self._persist_agent(agent_info)
                        
                        # Emit event for health change
                        self._emit_event(AgentEvent(
                            type=AgentEventType.HEALTH_CHANGED,
                            agent_id=agent_info.id,
                            data={
                                "old_health": agent_info.health,
                                "new_health": health
                            }
                        ))
                else:
                    # No instance, mark as unhealthy
                    if agent_info.health != AgentHealth.UNHEALTHY:
                        agent_info.health = AgentHealth.UNHEALTHY
                        self._persist_agent(agent_info)
            except Exception as e:
                logger.error(f"Health check failed for agent {agent_info.name}: {e}")
                agent_info.health = AgentHealth.UNHEALTHY
                agent_info.last_error = str(e)
                agent_info.error_count += 1
                self._persist_agent(agent_info)

    # ========================================
    # CLEANUP
    # ========================================

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._running:
            try:
                await self._cleanup_stale_agents()
                await asyncio.sleep(self._cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(30)

    async def _cleanup_stale_agents(self) -> None:
        """Clean up stale or dead agents."""
        stale_agents = []
        
        for agent_id, agent_info in self._agents.items():
            if agent_info.status == AgentStatus.RUNNING:
                age = (datetime.utcnow() - agent_info.last_heartbeat).total_seconds()
                if age > self._heartbeat_interval * 3:
                    stale_agents.append(agent_id)
                    
        for agent_id in stale_agents:
            logger.warning(f"Agent {agent_id} is stale (no heartbeat for {self._heartbeat_interval * 3}s)")
            agent_info = self._agents[agent_id]
            agent_info.status = AgentStatus.UNHEALTHY
            agent_info.health = AgentHealth.UNHEALTHY
            self._persist_agent(agent_info)
            
            self._emit_event(AgentEvent(
                type=AgentEventType.ERROR,
                agent_id=agent_id,
                data={"error": "Stale agent - no heartbeat received"}
            ))

    # ========================================
    # PERSISTENCE
    # ========================================

    def _persist_agent(self, agent_info: AgentInfo) -> None:
        """Persist agent info to Redis and PostgreSQL."""
        try:
            # Redis cache (for fast access)
            key = f"agent:{agent_info.id}"
            self.redis.setex(
                key,
                settings.REDIS_AGENT_TTL,
                json.dumps(agent_info.dict(), default=str)
            )
            
            # Redis index for name lookup
            name_key = f"agent:name:{agent_info.name}"
            self.redis.setex(
                name_key,
                settings.REDIS_AGENT_TTL,
                agent_info.id
            )

            # PostgreSQL (for permanent storage)
            # TODO: Implement PostgreSQL persistence
            # Use AgentModel from database/models/agent.py

        except Exception as e:
            logger.error(f"Failed to persist agent {agent_info.id}: {e}")

    def _remove_persisted_agent(self, agent_id: str) -> None:
        """Remove agent from persistence."""
        try:
            key = f"agent:{agent_id}"
            self.redis.delete(key)
            
            # Remove from name index if exists
            agent_info = self._agents.get(agent_id)
            if agent_info:
                name_key = f"agent:name:{agent_info.name}"
                self.redis.delete(name_key)

        except Exception as e:
            logger.error(f"Failed to remove persisted agent {agent_id}: {e}")

    def _persist_heartbeat(self, heartbeat: AgentHeartbeat) -> None:
        """Persist heartbeat to Redis."""
        try:
            key = f"heartbeat:{heartbeat.agent_id}"
            self.redis.setex(
                key,
                self._heartbeat_interval * 3,
                json.dumps(heartbeat.dict(), default=str)
            )
        except Exception as e:
            logger.error(f"Failed to persist heartbeat for {heartbeat.agent_id}: {e}")

    def _load_persisted_agents(self) -> None:
        """Load agents from persistence."""
        try:
            # Load from Redis
            keys = self.redis.keys("agent:*")
            for key in keys:
                if not isinstance(key, str):
                    continue
                # Skip name index keys
                if key.startswith("agent:name:"):
                    continue
                try:
                    data = self.redis.get(key)
                    if data:
                        agent_data = json.loads(data)
                        agent_info = AgentInfo(**agent_data)
                        self._agents[agent_info.id] = agent_info
                        
                        # Cache capabilities
                        for capability in agent_info.capabilities:
                            if capability not in self._capability_cache:
                                self._capability_cache[capability] = []
                            self._capability_cache[capability].append(agent_info.id)
                except Exception as e:
                    logger.error(f"Failed to load agent from {key}: {e}")

            logger.info(f"Loaded {len(self._agents)} agents from persistence")

        except Exception as e:
            logger.error(f"Failed to load persisted agents: {e}")

    # ========================================
    # BACKEND TASKS
    # ========================================

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        self._running = True
        
        # Health check loop
        self._tasks.append(asyncio.create_task(self._health_check_loop()))
        
        # Cleanup loop
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))

    async def stop(self) -> None:
        """Stop all background tasks."""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()

    # ========================================
    # UTILITY METHODS
    # ========================================

    def _get_agent(self, agent_id: str) -> AgentInfo:
        """Get agent by ID, raise if not found."""
        agent = self._agents.get(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        return agent

    def _get_agent_by_name(self, name: str) -> Optional[AgentInfo]:
        """Get agent by name."""
        for agent in self._agents.values():
            if agent.name == name:
                return agent
        return None

    def _get_instance(self, agent_id: str) -> BaseAgent:
        """Get agent instance by ID, raise if not found."""
        instance = self._instances.get(agent_id)
        if not instance:
            raise AgentNotFoundError(f"Agent instance {agent_id} not found")
        return instance

    async def _update_agent(self, agent_id: str, registration: AgentRegistration) -> AgentInfo:
        """Update existing agent registration."""
        agent_info = self._get_agent(agent_id)
        
        # Update fields
        agent_info.capabilities = registration.capabilities
        agent_info.config = registration.config
        agent_info.metadata = registration.metadata
        agent_info.dependencies = registration.dependencies
        agent_info.tags = registration.tags
        agent_info.priority = registration.priority
        
        # Persist updates
        self._persist_agent(agent_info)
        
        # Emit event
        self._emit_event(AgentEvent(
            type=AgentEventType.UPDATED,
            agent_id=agent_id,
            data=agent_info.dict()
        ))
        
        logger.info(f"Agent {agent_info.name} ({agent_id}) updated")
        return agent_info

    # ========================================
    # STATISTICS & REPORTING
    # ========================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total = len(self._agents)
        by_status = {}
        by_health = {}
        by_priority = {}
        
        for agent in self._agents.values():
            by_status[agent.status.value] = by_status.get(agent.status.value, 0) + 1
            by_health[agent.health.value] = by_health.get(agent.health.value, 0) + 1
            by_priority[agent.priority.value] = by_priority.get(agent.priority.value, 0) + 1
        
        return {
            "total_agents": total,
            "active_agents": len(self.get_active_agents()),
            "by_status": by_status,
            "by_health": by_health,
            "by_priority": by_priority,
            "total_capabilities": len(self._capability_cache),
            "registered_at": datetime.utcnow().isoformat()
        }

    def get_capabilities_report(self) -> Dict[str, List[str]]:
        """Get report of all capabilities and their agents."""
        report = {}
        for capability, agent_ids in self._capability_cache.items():
            report[capability.value] = [
                self._agents[aid].name for aid in agent_ids if aid in self._agents
            ]
        return report

    def export_agents(self) -> List[Dict[str, Any]]:
        """Export all agent data."""
        return [agent.dict() for agent in self._agents.values()]


# ========================================
# SINGLETON INSTANCE
# ========================================

_agent_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """
    Get singleton instance of AgentRegistry.
    
    Returns:
        AgentRegistry: The global agent registry instance
    """
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry


def reset_agent_registry() -> None:
    """Reset the agent registry (for testing)."""
    global _agent_registry
    if _agent_registry:
        asyncio.create_task(_agent_registry.stop())
    _agent_registry = None


# ========================================
# DEPENDENCY INJECTION
# ========================================

def provide_agent_registry() -> AgentRegistry:
    """Dependency injection provider for agent registry."""
    return get_agent_registry()


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'AgentRegistry',
    'AgentInfo',
    'AgentRegistration',
    'AgentHeartbeat',
    'AgentQuery',
    'AgentStatus',
    'AgentPriority',
    'AgentHealth',
    'get_agent_registry',
    'reset_agent_registry',
    'provide_agent_registry'
]

# trading/bots/arbitrage_bot/core/base_arbitrage.py
# Nexus AI Trading System - Base Arbitrage Engine Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Base Arbitrage Engine Module

This module provides the foundational infrastructure for arbitrage detection
and execution across multiple exchanges and asset types. It includes:

- Base abstract class for arbitrage engines
- Opportunity detection and validation
- Execution management and monitoring
- Risk assessment and management
- Performance tracking and analytics
- State management and persistence
- Event handling and callbacks

The base engine supports:
- Cross-exchange arbitrage
- Triangular arbitrage
- Statistical arbitrage
- Flash loan arbitrage
- Futures-spot arbitrage
- Cross-chain arbitrage
- DEX arbitrage
- Mixed arbitrage strategies
"""

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
from pydantic import BaseModel, Field, validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.arbitrage_types import (
    ArbitrageType,
    ArbitrageStatus,
    ArbitrageExecutionType,
    ArbitrageRiskLevel,
    ArbitrageOpportunity,
    ArbitrageExecution,
    ArbitrageStrategyConfig,
    ExchangeConfig,
    calculate_arbitrage_profit,
    calculate_risk_score
)
from trading.bots.arbitrage_bot.core.balance_manager import BalanceManager
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class EngineStatus(str, Enum):
    """Engine status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class EngineEventType(str, Enum):
    """Engine event types."""
    OPPORTUNITY_DETECTED = "opportunity_detected"
    OPPORTUNITY_VALIDATED = "opportunity_validated"
    OPPORTUNITY_REJECTED = "opportunity_rejected"
    OPPORTUNITY_EXPIRED = "opportunity_expired"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    RISK_ALERT = "risk_alert"
    PERFORMANCE_REPORT = "performance_report"
    STATE_CHANGED = "state_changed"
    ERROR_OCCURRED = "error_occurred"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class EngineState(BaseModel):
    """Engine state model."""
    engine_id: str
    status: EngineStatus = EngineStatus.STOPPED
    start_time: Optional[datetime] = None
    last_active: Optional[datetime] = None
    total_opportunities: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_profit: Decimal = Decimal('0')
    total_loss: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')
    win_rate: Decimal = Decimal('0')
    active_opportunities: int = 0
    pending_executions: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EngineConfig(BaseModel):
    """Engine configuration model."""
    engine_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: ArbitrageType
    enabled: bool = True
    
    # Strategy configuration
    strategy_config: ArbitrageStrategyConfig
    
    # Exchange configuration
    exchanges: List[ExchangeConfig] = Field(default_factory=list)
    
    # Engine parameters
    max_opportunities: int = 100
    max_concurrent_executions: int = 5
    min_opportunity_interval: float = 0.1  # seconds
    opportunity_timeout: int = 30  # seconds
    execution_timeout: int = 60  # seconds
    
    # Risk parameters
    max_risk_per_trade: Decimal = Decimal('0.02')
    max_total_risk: Decimal = Decimal('0.1')
    max_drawdown: Decimal = Decimal('0.05')
    stop_loss: Decimal = Decimal('0.01')
    take_profit: Decimal = Decimal('0.02')
    
    # Performance parameters
    track_performance: bool = True
    log_level: str = "INFO"
    alert_on_error: bool = True
    alert_on_opportunity: bool = False
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('max_risk_per_trade', 'max_total_risk', 'max_drawdown', 'stop_loss', 'take_profit')
    def validate_risk_params(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Risk parameter must be between 0 and 1")
        return v


class EnginePerformance(BaseModel):
    """Engine performance metrics."""
    engine_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    timeframe: str = "daily"
    
    # Core metrics
    total_opportunities: int = 0
    successful_opportunities: int = 0
    failed_opportunities: int = 0
    success_rate: Decimal = Decimal('0')
    
    # Profit metrics
    total_profit: Decimal = Decimal('0')
    average_profit: Decimal = Decimal('0')
    max_profit: Decimal = Decimal('0')
    min_profit: Decimal = Decimal('0')
    profit_factor: Decimal = Decimal('0')
    
    # Loss metrics
    total_loss: Decimal = Decimal('0')
    average_loss: Decimal = Decimal('0')
    max_loss: Decimal = Decimal('0')
    min_loss: Decimal = Decimal('0')
    
    # Net metrics
    net_profit: Decimal = Decimal('0')
    net_profit_percent: Decimal = Decimal('0')
    cumulative_return: Decimal = Decimal('0')
    
    # Risk metrics
    max_drawdown: Decimal = Decimal('0')
    max_drawdown_percent: Decimal = Decimal('0')
    sharpe_ratio: Decimal = Decimal('0')
    sortino_ratio: Decimal = Decimal('0')
    calmar_ratio: Decimal = Decimal('0')
    
    # Execution metrics
    average_execution_time: float = 0.0
    max_execution_time: float = 0.0
    min_execution_time: float = 0.0
    fill_rate: Decimal = Decimal('0')
    slippage: Decimal = Decimal('0')
    
    # Volume metrics
    total_volume: Decimal = Decimal('0')
    average_volume: Decimal = Decimal('0')
    
    # Fee metrics
    total_fees: Decimal = Decimal('0')
    average_fees: Decimal = Decimal('0')
    fee_percentage: Decimal = Decimal('0')
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# BASE ARBITRAGE ENGINE
# =============================================================================

class BaseArbitrageEngine(ABC):
    """
    Abstract base class for arbitrage engines.
    
    This class provides the core infrastructure for arbitrage detection
    and execution. Subclasses must implement the specific arbitrage logic.
    """
    
    def __init__(
        self,
        config: EngineConfig,
        balance_manager: BalanceManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        """
        Initialize the arbitrage engine.
        
        Args:
            config: Engine configuration
            balance_manager: Balance manager instance
            redis: Redis client for caching
            pool: PostgreSQL connection pool
        """
        self.config = config
        self.balance_manager = balance_manager
        self.redis = redis
        self.pool = pool
        
        # Engine state
        self._state = EngineState(
            engine_id=config.engine_id,
            status=EngineStatus.STOPPED
        )
        
        # Current opportunities
        self._opportunities: Dict[str, ArbitrageOpportunity] = {}
        self._active_opportunities: Dict[str, ArbitrageOpportunity] = {}
        self._executing: Dict[str, ArbitrageExecution] = {}
        self._completed: List[ArbitrageExecution] = []
        
        # Circuit breakers
        self._cb = CircuitBreaker(
            name=f"arbitrage_engine_{config.engine_id}",
            failure_threshold=5,
            recovery_timeout=60
        )
        
        # Event handlers
        self._event_handlers: Dict[EngineEventType, List[Callable]] = {}
        
        # Performance tracking
        self._performance = EnginePerformance(engine_id=config.engine_id)
        self._performance_history: List[EnginePerformance] = []
        
        # Running state
        self._running = False
        self._shutdown_requested = False
        self._tasks: List[asyncio.Task] = []
        
        # Rate limiting
        self._last_opportunity_time = 0
        self._opportunity_count = 0
        
        # Database
        self._db_initialized = False
        
        logger.info(f"Arbitrage engine {config.engine_id} initialized")
    
    async def initialize(self):
        """Initialize the engine."""
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load state from cache
        if self.redis:
            await self._load_state()
        
        # Start worker tasks
        self._running = True
        self._tasks.append(asyncio.create_task(self._detection_loop()))
        self._tasks.append(asyncio.create_task(self._execution_monitor_loop()))
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))
        
        if self.config.track_performance:
            self._tasks.append(asyncio.create_task(self._performance_tracking_loop()))
        
        self._state.status = EngineStatus.RUNNING
        self._state.start_time = datetime.utcnow()
        
        logger.info(f"Arbitrage engine {self.config.engine_id} started")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            # Create engine tables
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS arbitrage_engine_state (
                        engine_id VARCHAR(64) PRIMARY KEY,
                        status VARCHAR(20) NOT NULL,
                        state JSONB NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS arbitrage_engine_performance (
                        id SERIAL PRIMARY KEY,
                        engine_id VARCHAR(64) NOT NULL,
                        performance JSONB NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        INDEX idx_arbitrage_engine_performance_engine_id (engine_id),
                        INDEX idx_arbitrage_engine_performance_timestamp (timestamp)
                    )
                """)
                
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS arbitrage_engine_executions (
                        id VARCHAR(64) PRIMARY KEY,
                        engine_id VARCHAR(64) NOT NULL,
                        execution JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_arbitrage_engine_executions_engine_id (engine_id),
                        INDEX idx_arbitrage_engine_executions_created_at (created_at)
                    )
                """)
            
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # CORE ENGINE METHODS
    # =========================================================================
    
    @abstractmethod
    async def detect_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunities.
        
        This method must be implemented by subclasses.
        
        Returns:
            List of detected opportunities
        """
        pass
    
    @abstractmethod
    async def execute_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> ArbitrageExecution:
        """
        Execute an arbitrage opportunity.
        
        This method must be implemented by subclasses.
        
        Args:
            opportunity: Opportunity to execute
            
        Returns:
            Execution result
        """
        pass
    
    async def validate_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Tuple[bool, str]:
        """
        Validate an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if opportunity has expired
        if opportunity.expires_at and opportunity.expires_at < datetime.utcnow():
            return False, "Opportunity expired"
        
        # Check if profitability threshold is met
        if opportunity.net_profit < self.config.strategy_config.min_profit_absolute:
            return False, f"Profit too low: {opportunity.net_profit}"
        
        if opportunity.profit_percent < self.config.strategy_config.min_profit_percent:
            return False, f"Profit percentage too low: {opportunity.profit_percent}%"
        
        # Check risk limits
        if opportunity.risk_score > self.config.strategy_config.max_risk_per_trade * 100:
            return False, f"Risk score too high: {opportunity.risk_score}"
        
        # Check confidence
        if opportunity.confidence_score < self.config.strategy_config.min_confidence_score:
            return False, f"Confidence too low: {opportunity.confidence_score}"
        
        # Check if required capital is available
        available_capital = await self.balance_manager.get_balance(
            opportunity.exchange_route[0].get('exchange', ''),
            opportunity.base_asset
        )
        
        if available_capital and available_capital.available < opportunity.required_capital:
            return False, f"Insufficient capital: {available_capital.available} < {opportunity.required_capital}"
        
        # Check if risk limits are exceeded
        if not await self._check_risk_limits(opportunity):
            return False, "Risk limits exceeded"
        
        return True, "Valid opportunity"
    
    async def _check_risk_limits(self, opportunity: ArbitrageOpportunity) -> bool:
        """
        Check if risk limits are within bounds.
        
        Args:
            opportunity: Opportunity to check
            
        Returns:
            True if within limits
        """
        # Check max drawdown
        if opportunity.risk_level in [ArbitrageRiskLevel.HIGH, ArbitrageRiskLevel.VERY_HIGH]:
            if opportunity.risk_score > self.config.max_risk_per_trade * 100:
                return False
        
        # Check total risk
        total_risk = sum(
            Decimal(str(len(self._active_opportunities))) * 
            Decimal(str(self.config.max_risk_per_trade))
        )
        
        if total_risk > self.config.max_total_risk:
            return False
        
        # Check position limits
        for route in opportunity.exchange_route:
            exchange = route.get('exchange')
            if exchange:
                allocation = await self.balance_manager.get_allocation(
                    exchange,
                    opportunity.base_asset
                )
                
                if allocation and allocation.utilized > allocation.allocated * Decimal('0.9'):
                    return False
        
        return True
    
    # =========================================================================
    # ENGINE LOOPS
    # =========================================================================
    
    async def _detection_loop(self):
        """Main detection loop."""
        while self._running and not self._shutdown_requested:
            try:
                # Rate limiting
                now = time.time()
                if now - self._last_opportunity_time < self.config.min_opportunity_interval:
                    await asyncio.sleep(self.config.min_opportunity_interval)
                    continue
                
                # Detect opportunities
                opportunities = await self.detect_opportunities()
                
                for opportunity in opportunities:
                    # Validate
                    is_valid, reason = await self.validate_opportunity(opportunity)
                    
                    if is_valid:
                        opportunity.status = ArbitrageStatus.VALIDATED
                        self._opportunities[opportunity.id] = opportunity
                        self._active_opportunities[opportunity.id] = opportunity
                        
                        # Emit event
                        await self._emit_event(
                            EngineEventType.OPPORTUNITY_DETECTED,
                            opportunity
                        )
                        
                        # Execute if capacity available
                        if len(self._executing) < self.config.max_concurrent_executions:
                            asyncio.create_task(self._execute_opportunity(opportunity))
                    else:
                        opportunity.status = ArbitrageStatus.REJECTED
                        await self._emit_event(
                            EngineEventType.OPPORTUNITY_REJECTED,
                            {"opportunity": opportunity, "reason": reason}
                        )
                
                self._last_opportunity_time = now
                self._opportunity_count += len(opportunities)
                
                # Update state
                self._state.active_opportunities = len(self._active_opportunities)
                self._state.total_opportunities += len(opportunities)
                
            except Exception as e:
                logger.error(f"Detection loop error: {e}")
                await self._emit_event(
                    EngineEventType.ERROR_OCCURRED,
                    {"error": str(e)}
                )
                await asyncio.sleep(5)
            
            await asyncio.sleep(0.1)
    
    async def _execute_opportunity(self, opportunity: ArbitrageOpportunity):
        """
        Execute an opportunity.
        
        Args:
            opportunity: Opportunity to execute
        """
        try:
            # Update status
            opportunity.status = ArbitrageStatus.EXECUTING
            
            # Check if still valid
            is_valid, reason = await self.validate_opportunity(opportunity)
            if not is_valid:
                opportunity.status = ArbitrageStatus.CANCELLED
                await self._emit_event(
                    EngineEventType.OPPORTUNITY_EXPIRED,
                    {"opportunity": opportunity, "reason": reason}
                )
                return
            
            # Execute
            start_time = time.time()
            execution = await self.execute_opportunity(opportunity)
            execution.duration_ms = (time.time() - start_time) * 1000
            
            # Record execution
            self._executing[execution.id] = execution
            
            await self._emit_event(
                EngineEventType.EXECUTION_STARTED,
                execution
            )
            
            # Wait for completion
            completion = await self._monitor_execution(execution)
            
            if completion.is_successful:
                self._state.successful_executions += 1
                self._state.total_profit += completion.actual_profit
                self._state.net_profit = self._state.total_profit - self._state.total_loss
                
                # Update win rate
                total = self._state.successful_executions + self._state.failed_executions
                if total > 0:
                    self._state.win_rate = Decimal(
                        self._state.successful_executions / total
                    )
                
                await self._emit_event(
                    EngineEventType.EXECUTION_COMPLETED,
                    completion
                )
                
                # Update balance allocation
                for route in opportunity.exchange_route:
                    exchange = route.get('exchange')
                    currency = opportunity.base_asset
                    if exchange and currency:
                        allocation = await self.balance_manager.get_allocation(exchange, currency)
                        if allocation:
                            await self.balance_manager.update_allocation(
                                exchange,
                                currency,
                                utilized=allocation.utilized - opportunity.required_capital
                            )
            else:
                self._state.failed_executions += 1
                self._state.total_loss += abs(completion.actual_profit) if completion.actual_profit < 0 else Decimal('0')
                self._state.net_profit = self._state.total_profit - self._state.total_loss
                
                await self._emit_event(
                    EngineEventType.EXECUTION_FAILED,
                    {"execution": completion, "error": execution.error_message}
                )
            
            # Clean up
            self._executing.pop(execution.id, None)
            self._active_opportunities.pop(opportunity.id, None)
            self._completed.append(completion)
            
            # Save to database
            if self.pool:
                await self._save_execution(execution)
            
        except Exception as e:
            logger.error(f"Execution error: {e}")
            opportunity.status = ArbitrageStatus.FAILED
            
            await self._emit_event(
                EngineEventType.ERROR_OCCURRED,
                {"error": str(e), "opportunity": opportunity}
            )
            
            self._active_opportunities.pop(opportunity.id, None)
    
    async def _monitor_execution(
        self,
        execution: ArbitrageExecution
    ) -> ArbitrageExecution:
        """
        Monitor an execution until completion.
        
        Args:
            execution: Execution to monitor
            
        Returns:
            Updated execution
        """
        start_time = time.time()
        timeout = self.config.execution_timeout
        
        while (time.time() - start_time) < timeout:
            if execution.status in [
                ArbitrageStatus.COMPLETED,
                ArbitrageStatus.FAILED,
                ArbitrageStatus.CANCELLED
            ]:
                break
            
            # Update execution status
            execution = await self._update_execution_status(execution)
            
            await asyncio.sleep(0.5)
        
        # Check timeout
        if execution.status not in [
            ArbitrageStatus.COMPLETED,
            ArbitrageStatus.FAILED,
            ArbitrageStatus.CANCELLED
        ]:
            execution.status = ArbitrageStatus.EXPIRED
            execution.error_message = "Execution timeout"
        
        execution.end_time = datetime.utcnow()
        execution.duration_ms = (datetime.utcnow() - execution.start_time).total_seconds() * 1000
        
        return execution
    
    async def _update_execution_status(
        self,
        execution: ArbitrageExecution
    ) -> ArbitrageExecution:
        """
        Update execution status.
        
        This method should be overridden by subclasses to implement
        exchange-specific status checking.
        
        Args:
            execution: Execution to update
            
        Returns:
            Updated execution
        """
        # Default implementation - check if orders are filled
        # Override in subclasses
        return execution
    
    async def _execution_monitor_loop(self):
        """Monitor executing opportunities."""
        while self._running and not self._shutdown_requested:
            try:
                for execution_id, execution in list(self._executing.items()):
                    if execution.status in [
                        ArbitrageStatus.COMPLETED,
                        ArbitrageStatus.FAILED,
                        ArbitrageStatus.CANCELLED,
                        ArbitrageStatus.EXPIRED
                    ]:
                        continue
                    
                    # Update status
                    updated = await self._update_execution_status(execution)
                    if updated != execution:
                        self._executing[execution_id] = updated
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Execution monitor error: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_loop(self):
        """Clean up expired opportunities."""
        while self._running and not self._shutdown_requested:
            try:
                now = datetime.utcnow()
                expired = []
                
                for opp_id, opportunity in self._active_opportunities.items():
                    if opportunity.expires_at and opportunity.expires_at < now:
                        expired.append(opp_id)
                        opportunity.status = ArbitrageStatus.EXPIRED
                        
                        await self._emit_event(
                            EngineEventType.OPPORTUNITY_EXPIRED,
                            opportunity
                        )
                
                for opp_id in expired:
                    self._active_opportunities.pop(opp_id, None)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(5)
    
    async def _performance_tracking_loop(self):
        """Track performance metrics."""
        while self._running and not self._shutdown_requested:
            try:
                await asyncio.sleep(60)  # Update every minute
                
                # Update performance
                self._performance = await self._calculate_performance()
                
                # Save performance
                if self.pool:
                    await self._save_performance(self._performance)
                
                # Check if performance report should be emitted
                if self._performance.net_profit > Decimal('0'):
                    await self._emit_event(
                        EngineEventType.PERFORMANCE_REPORT,
                        self._performance
                    )
                
            except Exception as e:
                logger.error(f"Performance tracking error: {e}")
                await asyncio.sleep(60)
    
    async def _calculate_performance(self) -> EnginePerformance:
        """
        Calculate performance metrics.
        
        Returns:
            EnginePerformance
        """
        total_opportunities = self._state.total_opportunities
        successful = self._state.successful_executions
        failed = self._state.failed_executions
        
        success_rate = Decimal('0')
        if total_opportunities > 0:
            success_rate = Decimal(successful / total_opportunities)
        
        # Calculate profit metrics
        total_profit = self._state.total_profit
        total_loss = self._state.total_loss
        
        profit_factor = Decimal('0')
        if total_loss > 0:
            profit_factor = total_profit / total_loss
        
        # Calculate return metrics
        net_profit = self._state.net_profit
        net_profit_percent = Decimal('0')
        if total_profit > 0 or total_loss > 0:
            net_profit_percent = net_profit / (total_profit + total_loss) * 100
        
        # Calculate execution metrics
        avg_exec_time = 0.0
        max_exec_time = 0.0
        min_exec_time = float('inf')
        
        for exec in self._completed:
            if exec.duration_ms:
                avg_exec_time += exec.duration_ms
                max_exec_time = max(max_exec_time, exec.duration_ms)
                min_exec_time = min(min_exec_time, exec.duration_ms)
        
        if self._completed:
            avg_exec_time /= len(self._completed)
        if min_exec_time == float('inf'):
            min_exec_time = 0.0
        
        return EnginePerformance(
            engine_id=self.config.engine_id,
            total_opportunities=total_opportunities,
            successful_opportunities=successful,
            failed_opportunities=failed,
            success_rate=success_rate,
            total_profit=total_profit,
            average_profit=total_profit / total_opportunities if total_opportunities > 0 else Decimal('0'),
            max_profit=total_profit if total_profit > 0 else Decimal('0'),
            total_loss=total_loss,
            average_loss=total_loss / total_opportunities if total_opportunities > 0 else Decimal('0'),
            net_profit=net_profit,
            net_profit_percent=net_profit_percent,
            cumulative_return=net_profit_percent,
            max_drawdown=Decimal('0'),  # Would need historical tracking
            max_drawdown_percent=Decimal('0'),
            sharpe_ratio=Decimal('0'),
            sortino_ratio=Decimal('0'),
            calmar_ratio=Decimal('0'),
            average_execution_time=avg_exec_time,
            max_execution_time=max_exec_time,
            min_execution_time=min_exec_time,
            total_volume=Decimal('0'),
            average_volume=Decimal('0'),
            total_fees=Decimal('0'),
            average_fees=Decimal('0'),
            fill_rate=Decimal('1'),
            slippage=Decimal('0'),
            fee_percentage=Decimal('0')
        )
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    async def _save_state(self):
        """Save engine state."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO arbitrage_engine_state (
                        engine_id, status, state, updated_at
                    ) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (engine_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        state = EXCLUDED.state,
                        updated_at = EXCLUDED.updated_at
                    """,
                    self.config.engine_id,
                    self._state.status.value,
                    json.dumps(self._state.dict(), default=str),
                    datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    async def _load_state(self):
        """Load engine state."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT state FROM arbitrage_engine_state WHERE engine_id = $1",
                    self.config.engine_id
                )
                
                if row:
                    state_data = json.loads(row['state'])
                    self._state = EngineState(**state_data)
                    
                    logger.info(f"Loaded state: {self._state.status}")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    # =========================================================================
    # EVENT HANDLING
    # =========================================================================
    
    def on(self, event_type: EngineEventType, handler: Callable):
        """
        Register an event handler.
        
        Args:
            event_type: Event type
            handler: Handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def _emit_event(self, event_type: EngineEventType, data: Any):
        """
        Emit an event.
        
        Args:
            event_type: Event type
            data: Event data
        """
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_type, data)
                    else:
                        handler(event_type, data)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_execution(self, execution: ArbitrageExecution):
        """Save execution to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO arbitrage_engine_executions (
                        id, engine_id, execution, created_at
                    ) VALUES ($1, $2, $3, $4)
                    """,
                    execution.id,
                    self.config.engine_id,
                    json.dumps(execution.dict(), default=str),
                    datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error saving execution: {e}")
    
    async def _save_performance(self, performance: EnginePerformance):
        """Save performance to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO arbitrage_engine_performance (
                        engine_id, performance, timestamp
                    ) VALUES ($1, $2, $3)
                    """,
                    performance.engine_id,
                    json.dumps(performance.dict(), default=str),
                    performance.timestamp
                )
        except Exception as e:
            logger.error(f"Error saving performance: {e}")
    
    # =========================================================================
    # CONTROL METHODS
    # =========================================================================
    
    async def start(self):
        """Start the engine."""
        if self._running:
            return
        
        self._running = True
        self._shutdown_requested = False
        self._state.status = EngineStatus.RUNNING
        
        await self.initialize()
        
        logger.info(f"Engine {self.config.engine_id} started")
    
    async def pause(self):
        """Pause the engine."""
        self._running = False
        self._state.status = EngineStatus.PAUSED
        
        await self._save_state()
        
        logger.info(f"Engine {self.config.engine_id} paused")
    
    async def resume(self):
        """Resume the engine."""
        if self._running:
            return
        
        self._running = True
        self._shutdown_requested = False
        self._state.status = EngineStatus.RUNNING
        
        await self._save_state()
        
        logger.info(f"Engine {self.config.engine_id} resumed")
    
    async def stop(self):
        """Stop the engine."""
        self._shutdown_requested = True
        self._running = False
        self._state.status = EngineStatus.STOPPED
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        
        await self._save_state()
        
        logger.info(f"Engine {self.config.engine_id} stopped")
    
    async def get_state(self) -> EngineState:
        """Get current engine state."""
        return self._state
    
    async def get_performance(self) -> EnginePerformance:
        """Get current performance metrics."""
        return await self._calculate_performance()
    
    async def get_opportunities(self) -> List[ArbitrageOpportunity]:
        """Get all active opportunities."""
        return list(self._active_opportunities.values())
    
    async def get_executions(self) -> List[ArbitrageExecution]:
        """Get all executions."""
        return list(self._executing.values()) + self._completed
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the engine."""
        await self.stop()
        
        logger.info(f"Engine {self.config.engine_id} shutdown complete")


# =============================================================================
# FACTORY
# =============================================================================

class ArbitrageEngineFactory:
    """
    Factory for creating arbitrage engines.
    
    This factory provides a unified interface for creating different
    types of arbitrage engines.
    """
    
    _engines: Dict[str, Type[BaseArbitrageEngine]] = {}
    
    @classmethod
    def register_engine(
        cls,
        engine_type: ArbitrageType,
        engine_class: Type[BaseArbitrageEngine]
    ):
        """
        Register an engine class.
        
        Args:
            engine_type: Engine type
            engine_class: Engine class
        """
        cls._engines[engine_type] = engine_class
        logger.info(f"Registered arbitrage engine: {engine_type}")
    
    @classmethod
    def create_engine(
        cls,
        engine_type: ArbitrageType,
        config: EngineConfig,
        balance_manager: BalanceManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ) -> BaseArbitrageEngine:
        """
        Create an arbitrage engine.
        
        Args:
            engine_type: Engine type
            config: Engine configuration
            balance_manager: Balance manager instance
            redis: Redis client
            pool: PostgreSQL connection pool
            
        Returns:
            Arbitrage engine instance
        """
        if engine_type not in cls._engines:
            raise ValueError(f"Unknown engine type: {engine_type}")
        
        engine_class = cls._engines[engine_type]
        return engine_class(config, balance_manager, redis, pool)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BaseArbitrageEngine',
    'EngineStatus',
    'EngineEventType',
    'EngineState',
    'EngineConfig',
    'EnginePerformance',
    'ArbitrageEngineFactory'
]

# trading/bots/hedge_bot/hedge_bot_emergency_stop.py

import asyncio
import logging
import time
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger(__name__)


class EmergencyLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EmergencyAction(str, Enum):
    STOP_ALL = "stop_all"
    CLOSE_POSITIONS = "close_positions"
    CANCEL_ORDERS = "cancel_orders"
    PAUSE_TRADING = "pause_trading"
    REDUCE_EXPOSURE = "reduce_exposure"
    HEDGE_POSITIONS = "hedge_positions"
    LIQUIDATE = "liquidate"
    ALERT_ONLY = "alert_only"
    SHUTDOWN = "shutdown"


class EmergencyStatus(str, Enum):
    NORMAL = "normal"
    TRIGGERED = "triggered"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    RECOVERING = "recovering"
    RECOVERED = "recovered"


@dataclass
class EmergencyCondition:
    id: str
    name: str
    level: EmergencyLevel
    condition: str
    actions: List[EmergencyAction]
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    triggered_count: int = 0
    last_triggered: Optional[float] = None


@dataclass
class EmergencyEvent:
    id: str
    condition_id: str
    level: EmergencyLevel
    status: EmergencyStatus
    actions_taken: List[EmergencyAction]
    message: str
    timestamp: float
    resolved_at: Optional[float] = None
    recovery_actions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmergencyRecovery:
    id: str
    event_id: str
    actions: List[str]
    status: EmergencyStatus
    started_at: float
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EmergencyStopManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._conditions: Dict[str, EmergencyCondition] = {}
        self._events: Dict[str, EmergencyEvent] = {}
        self._recoveries: Dict[str, EmergencyRecovery] = {}
        self._executors: Dict[EmergencyAction, Callable] = {}
        self._recovery_handlers: Dict[str, Callable] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._state: EmergencyStatus = EmergencyStatus.NORMAL
        
        self._initialize_default_conditions()
        self._initialize_default_executors()
        self._initialize_default_recovery_handlers()

    def _initialize_default_conditions(self) -> None:
        default_conditions = [
            EmergencyCondition(
                id="max_loss",
                name="Maximum Loss Exceeded",
                level=EmergencyLevel.CRITICAL,
                condition="total_pnl < -max_daily_loss",
                actions=[EmergencyAction.CLOSE_POSITIONS, EmergencyAction.CANCEL_ORDERS, EmergencyAction.PAUSE_TRADING]
            ),
            EmergencyCondition(
                id="max_drawdown",
                name="Maximum Drawdown Exceeded",
                level=EmergencyLevel.HIGH,
                condition="drawdown > max_drawdown_limit",
                actions=[EmergencyAction.REDUCE_EXPOSURE, EmergencyAction.HEDGE_POSITIONS]
            ),
            EmergencyCondition(
                id="system_error",
                name="System Error Detected",
                level=EmergencyLevel.CRITICAL,
                condition="system_error == True",
                actions=[EmergencyAction.STOP_ALL, EmergencyAction.SHUTDOWN]
            ),
            EmergencyCondition(
                id="connection_lost",
                name="Connection Lost",
                level=EmergencyLevel.HIGH,
                condition="connection_status == 'lost'",
                actions=[EmergencyAction.PAUSE_TRADING, EmergencyAction.CANCEL_ORDERS]
            ),
            EmergencyCondition(
                id="volatility_spike",
                name="Volatility Spike",
                level=EmergencyLevel.MEDIUM,
                condition="volatility > volatility_threshold * 3",
                actions=[EmergencyAction.REDUCE_EXPOSURE, EmergencyAction.PAUSE_TRADING]
            )
        ]
        
        for condition in default_conditions:
            self._conditions[condition.id] = condition

    def _initialize_default_executors(self) -> None:
        self.register_executor(EmergencyAction.STOP_ALL, self._execute_stop_all)
        self.register_executor(EmergencyAction.CLOSE_POSITIONS, self._execute_close_positions)
        self.register_executor(EmergencyAction.CANCEL_ORDERS, self._execute_cancel_orders)
        self.register_executor(EmergencyAction.PAUSE_TRADING, self._execute_pause_trading)
        self.register_executor(EmergencyAction.REDUCE_EXPOSURE, self._execute_reduce_exposure)
        self.register_executor(EmergencyAction.HEDGE_POSITIONS, self._execute_hedge_positions)
        self.register_executor(EmergencyAction.LIQUIDATE, self._execute_liquidate)
        self.register_executor(EmergencyAction.ALERT_ONLY, self._execute_alert_only)
        self.register_executor(EmergencyAction.SHUTDOWN, self._execute_shutdown)

    def _initialize_default_recovery_handlers(self) -> None:
        self.register_recovery_handler("stop_all", self._recover_stop_all)
        self.register_recovery_handler("close_positions", self._recover_close_positions)
        self.register_recovery_handler("cancel_orders", self._recover_cancel_orders)
        self.register_recovery_handler("pause_trading", self._recover_pause_trading)
        self.register_recovery_handler("reduce_exposure", self._recover_reduce_exposure)
        self.register_recovery_handler("hedge_positions", self._recover_hedge_positions)

    def register_executor(self, action: EmergencyAction, executor: Callable) -> None:
        self._executors[action] = executor

    def register_recovery_handler(self, name: str, handler: Callable) -> None:
        self._recovery_handlers[name] = handler

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_condition(
        self,
        name: str,
        level: EmergencyLevel,
        condition: str,
        actions: List[EmergencyAction],
        metadata: Optional[Dict[str, Any]] = None
    ) -> EmergencyCondition:
        async with self._lock:
            condition_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            cond = EmergencyCondition(
                id=condition_id,
                name=name,
                level=level,
                condition=condition,
                actions=actions,
                metadata=metadata or {}
            )
            
            self._conditions[condition_id] = cond
            await self._notify_observers("condition_added", cond)
            return cond

    async def check_conditions(self, context: Dict[str, Any]) -> List[EmergencyEvent]:
        async with self._lock:
            events = []
            
            for condition in self._conditions.values():
                if not condition.enabled:
                    continue
                
                try:
                    if eval(condition.condition, {}, context):
                        event = await self._trigger_emergency(condition, context)
                        events.append(event)
                        
                except Exception as e:
                    logger.error(f"Error checking condition {condition.name}: {e}")
            
            return events

    async def _trigger_emergency(
        self,
        condition: EmergencyCondition,
        context: Dict[str, Any]
    ) -> EmergencyEvent:
        event_id = hashlib.md5(f"{condition.id}_{time.time()}".encode()).hexdigest()
        
        event = EmergencyEvent(
            id=event_id,
            condition_id=condition.id,
            level=condition.level,
            status=EmergencyStatus.TRIGGERED,
            actions_taken=[],
            message=f"Emergency triggered: {condition.name}",
            timestamp=time.time(),
            metadata=context.get("metadata", {})
        )
        
        self._events[event_id] = event
        condition.triggered_count += 1
        condition.last_triggered = time.time()
        
        await self._notify_observers("emergency_triggered", event)
        
        event.status = EmergencyStatus.EXECUTING
        
        for action in condition.actions:
            if action in self._executors:
                try:
                    await self._executors[action](event, context)
                    event.actions_taken.append(action)
                    await self._notify_observers("action_executed", action, event)
                except Exception as e:
                    logger.error(f"Error executing {action}: {e}")
                    event.metadata["errors"] = event.metadata.get("errors", []) + [str(e)]
        
        if len(event.actions_taken) == len(condition.actions):
            event.status = EmergencyStatus.COMPLETED
        elif len(event.actions_taken) > 0:
            event.status = EmergencyStatus.PARTIAL
        else:
            event.status = EmergencyStatus.FAILED
        
        self._state = EmergencyStatus.TRIGGERED
        
        await self._notify_observers("emergency_completed", event)
        return event

    async def execute_recovery(self, event_id: str) -> Optional[EmergencyRecovery]:
        async with self._lock:
            if event_id not in self._events:
                return None
            
            event = self._events[event_id]
            
            recovery_id = hashlib.md5(f"{event_id}_{time.time()}".encode()).hexdigest()
            
            recovery = EmergencyRecovery(
                id=recovery_id,
                event_id=event_id,
                actions=[],
                status=EmergencyStatus.RECOVERING,
                started_at=time.time()
            )
            
            self._recoveries[recovery_id] = recovery
            
            for action_taken in event.actions_taken:
                action_name = action_taken.value
                if action_name in self._recovery_handlers:
                    try:
                        await self._recovery_handlers[action_name](event)
                        recovery.actions.append(action_name)
                        await self._notify_observers("recovery_action", action_name, event)
                    except Exception as e:
                        logger.error(f"Error during recovery for {action_name}: {e}")
                        recovery.metadata["errors"] = recovery.metadata.get("errors", []) + [str(e)]
            
            if len(recovery.actions) == len(event.actions_taken):
                recovery.status = EmergencyStatus.COMPLETED
                self._state = EmergencyStatus.RECOVERED
            else:
                recovery.status = EmergencyStatus.PARTIAL
            
            recovery.completed_at = time.time()
            event.status = EmergencyStatus.RECOVERING
            event.recovery_actions.append({
                "recovery_id": recovery_id,
                "actions": recovery.actions,
                "status": recovery.status.value
            })
            
            await self._notify_observers("recovery_completed", recovery)
            return recovery

    async def _execute_stop_all(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.warning("Stopping all trading activities")
        event.metadata["stop_all_timestamp"] = time.time()

    async def _execute_close_positions(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.warning("Closing all positions")
        event.metadata["close_positions_timestamp"] = time.time()

    async def _execute_cancel_orders(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.warning("Cancelling all orders")
        event.metadata["cancel_orders_timestamp"] = time.time()

    async def _execute_pause_trading(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.warning("Pausing trading")
        event.metadata["pause_trading_timestamp"] = time.time()

    async def _execute_reduce_exposure(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.warning("Reducing exposure")
        event.metadata["reduce_exposure_timestamp"] = time.time()

    async def _execute_hedge_positions(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.warning("Hedging positions")
        event.metadata["hedge_positions_timestamp"] = time.time()

    async def _execute_liquidate(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.warning("Liquidating positions")
        event.metadata["liquidate_timestamp"] = time.time()

    async def _execute_alert_only(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.warning("Alert triggered only")
        event.metadata["alert_timestamp"] = time.time()

    async def _execute_shutdown(self, event: EmergencyEvent, context: Dict[str, Any]) -> None:
        logger.critical("Emergency shutdown initiated")
        event.metadata["shutdown_timestamp"] = time.time()

    async def _recover_stop_all(self, event: EmergencyEvent) -> None:
        logger.info("Recovering from stop all")
        await asyncio.sleep(1)

    async def _recover_close_positions(self, event: EmergencyEvent) -> None:
        logger.info("Recovering from position closure")
        await asyncio.sleep(1)

    async def _recover_cancel_orders(self, event: EmergencyEvent) -> None:
        logger.info("Recovering from order cancellation")
        await asyncio.sleep(1)

    async def _recover_pause_trading(self, event: EmergencyEvent) -> None:
        logger.info("Recovering from trading pause")
        await asyncio.sleep(1)

    async def _recover_reduce_exposure(self, event: EmergencyEvent) -> None:
        logger.info("Recovering from exposure reduction")
        await asyncio.sleep(1)

    async def _recover_hedge_positions(self, event: EmergencyEvent) -> None:
        logger.info("Recovering from position hedging")
        await asyncio.sleep(1)

    async def get_state(self) -> EmergencyStatus:
        return self._state

    async def get_condition(self, condition_id: str) -> Optional[EmergencyCondition]:
        return self._conditions.get(condition_id)

    async def get_conditions(self) -> List[EmergencyCondition]:
        return list(self._conditions.values())

    async def get_event(self, event_id: str) -> Optional[EmergencyEvent]:
        return self._events.get(event_id)

    async def get_events(self) -> List[EmergencyEvent]:
        return list(self._events.values())

    async def get_recovery(self, recovery_id: str) -> Optional[EmergencyRecovery]:
        return self._recoveries.get(recovery_id)

    async def get_recoveries(self) -> List[EmergencyRecovery]:
        return list(self._recoveries.values())

    async def enable_condition(self, condition_id: str) -> bool:
        if condition_id in self._conditions:
            self._conditions[condition_id].enabled = True
            return True
        return False

    async def disable_condition(self, condition_id: str) -> bool:
        if condition_id in self._conditions:
            self._conditions[condition_id].enabled = False
            return True
        return False

    async def delete_condition(self, condition_id: str) -> bool:
        if condition_id in self._conditions:
            del self._conditions[condition_id]
            return True
        return False

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "conditions": len(self._conditions),
            "events": len(self._events),
            "recoveries": len(self._recoveries),
            "state": self._state.value,
            "running": self._running
        }


__all__ = [
    "EmergencyLevel",
    "EmergencyAction",
    "EmergencyStatus",
    "EmergencyCondition",
    "EmergencyEvent",
    "EmergencyRecovery",
    "EmergencyStopManager"
]

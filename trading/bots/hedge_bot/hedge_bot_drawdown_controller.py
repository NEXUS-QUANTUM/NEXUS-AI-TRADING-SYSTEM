# trading/bots/hedge_bot/hedge_bot_drawdown_controller.py

import asyncio
import logging
import time
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class DrawdownStatus(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    MAXIMUM = "maximum"
    RECOVERING = "recovering"


class DrawdownAction(str, Enum):
    NONE = "none"
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    HEDGE = "hedge"
    PAUSE = "pause"
    STOP = "stop"
    REVERSE = "reverse"
    SCALE_IN = "scale_in"


@dataclass
class DrawdownState:
    id: str
    current_drawdown: float
    max_drawdown: float
    peak_value: float
    current_value: float
    status: DrawdownStatus
    recovery_factor: float
    consecutive_losses: int
    loss_streak: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DrawdownAlert:
    id: str
    level: str
    message: str
    current_drawdown: float
    threshold: float
    timestamp: float
    acknowledged: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DrawdownRecovery:
    id: str
    start_time: float
    end_time: Optional[float] = None
    initial_drawdown: float
    recovered_amount: float = 0.0
    recovery_rate: float = 0.0
    status: DrawdownStatus = DrawdownStatus.RECOVERING
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DrawdownActionPlan:
    id: str
    name: str
    threshold: float
    action: DrawdownAction
    parameters: Dict[str, Any]
    priority: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class DrawdownController:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._state: Optional[DrawdownState] = None
        self._alerts: Dict[str, DrawdownAlert] = {}
        self._recoveries: Dict[str, DrawdownRecovery] = {}
        self._action_plans: Dict[str, DrawdownActionPlan] = {}
        self._history: deque = deque(maxlen=10000)
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        self._initialize_default_action_plans()

    def _initialize_default_action_plans(self) -> None:
        default_plans = [
            DrawdownActionPlan(
                id="warning_reduce",
                name="Warning Level Position Reduction",
                threshold=0.10,
                action=DrawdownAction.REDUCE_POSITION,
                parameters={"reduction_percent": 0.3},
                priority=1
            ),
            DrawdownActionPlan(
                id="critical_pause",
                name="Critical Level Trading Pause",
                threshold=0.20,
                action=DrawdownAction.PAUSE,
                parameters={"duration": 3600},
                priority=2
            ),
            DrawdownActionPlan(
                id="maximum_stop",
                name="Maximum Level Trading Stop",
                threshold=0.30,
                action=DrawdownAction.STOP,
                parameters={"stop_duration": 86400},
                priority=3
            )
        ]
        
        for plan in default_plans:
            self._action_plans[plan.id] = plan

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def update_state(
        self,
        current_value: float,
        peak_value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DrawdownState:
        async with self._lock:
            if self._state is None:
                peak_value = peak_value or current_value
                self._state = DrawdownState(
                    id=hashlib.md5(f"{time.time()}".encode()).hexdigest(),
                    current_drawdown=0.0,
                    max_drawdown=0.0,
                    peak_value=peak_value,
                    current_value=current_value,
                    status=DrawdownStatus.NORMAL,
                    recovery_factor=1.0,
                    consecutive_losses=0,
                    loss_streak=0.0,
                    timestamp=time.time(),
                    metadata=metadata or {}
                )
                return self._state
            
            if peak_value is not None and peak_value > self._state.peak_value:
                self._state.peak_value = peak_value
            
            self._state.current_value = current_value
            
            if current_value > self._state.peak_value:
                self._state.peak_value = current_value
            
            drawdown = (self._state.peak_value - current_value) / self._state.peak_value if self._state.peak_value > 0 else 0
            
            self._state.current_drawdown = drawdown
            
            if drawdown > self._state.max_drawdown:
                self._state.max_drawdown = drawdown
            
            self._state.recovery_factor = 1 - drawdown
            
            if drawdown > 0.30:
                self._state.status = DrawdownStatus.MAXIMUM
            elif drawdown > 0.20:
                self._state.status = DrawdownStatus.CRITICAL
            elif drawdown > 0.10:
                self._state.status = DrawdownStatus.WARNING
            else:
                self._state.status = DrawdownStatus.NORMAL
            
            if metadata:
                self._state.metadata.update(metadata)
            
            self._state.timestamp = time.time()
            self._history.append({
                "timestamp": self._state.timestamp,
                "drawdown": drawdown,
                "value": current_value,
                "peak": self._state.peak_value,
                "status": self._state.status.value
            })
            
            await self._check_alerts()
            await self._check_action_plans()
            
            await self._notify_observers("state_updated", self._state)
            return self._state

    async def _check_alerts(self) -> None:
        if not self._state:
            return
        
        drawdown = self._state.current_drawdown
        
        thresholds = [
            (0.10, "warning"),
            (0.15, "warning_high"),
            (0.20, "critical"),
            (0.25, "critical_high"),
            (0.30, "maximum")
        ]
        
        for threshold, level in thresholds:
            if drawdown >= threshold:
                alert = DrawdownAlert(
                    id=hashlib.md5(f"{level}_{time.time()}".encode()).hexdigest(),
                    level=level,
                    message=f"Drawdown reached {drawdown:.2%}",
                    current_drawdown=drawdown,
                    threshold=threshold,
                    timestamp=time.time()
                )
                
                self._alerts[alert.id] = alert
                await self._notify_observers("alert_triggered", alert)

    async def _check_action_plans(self) -> None:
        if not self._state:
            return
        
        drawdown = self._state.current_drawdown
        
        for plan in sorted(self._action_plans.values(), key=lambda p: p.priority):
            if not plan.enabled:
                continue
            
            if drawdown >= plan.threshold:
                await self._execute_action_plan(plan)

    async def _execute_action_plan(self, plan: DrawdownActionPlan) -> None:
        logger.info(f"Executing action plan: {plan.name}")
        
        if plan.action == DrawdownAction.REDUCE_POSITION:
            reduction = plan.parameters.get("reduction_percent", 0.3)
            await self._reduce_positions(reduction)
        
        elif plan.action == DrawdownAction.CLOSE_POSITION:
            await self._close_positions()
        
        elif plan.action == DrawdownAction.HEDGE:
            await self._hedge_positions()
        
        elif plan.action == DrawdownAction.PAUSE:
            duration = plan.parameters.get("duration", 3600)
            await self._pause_trading(duration)
        
        elif plan.action == DrawdownAction.STOP:
            duration = plan.parameters.get("stop_duration", 86400)
            await self._stop_trading(duration)
        
        elif plan.action == DrawdownAction.REVERSE:
            await self._reverse_positions()
        
        elif plan.action == DrawdownAction.SCALE_IN:
            await self._scale_in()

    async def _reduce_positions(self, reduction_percent: float) -> None:
        logger.info(f"Reducing positions by {reduction_percent:.0%}")
        await self._notify_observers("reduce_positions", reduction_percent)

    async def _close_positions(self) -> None:
        logger.info("Closing all positions")
        await self._notify_observers("close_positions")

    async def _hedge_positions(self) -> None:
        logger.info("Hedging positions")
        await self._notify_observers("hedge_positions")

    async def _pause_trading(self, duration: int) -> None:
        logger.info(f"Pausing trading for {duration} seconds")
        await self._notify_observers("pause_trading", duration)

    async def _stop_trading(self, duration: int) -> None:
        logger.info(f"Stopping trading for {duration} seconds")
        await self._notify_observers("stop_trading", duration)

    async def _reverse_positions(self) -> None:
        logger.info("Reversing positions")
        await self._notify_observers("reverse_positions")

    async def _scale_in(self) -> None:
        logger.info("Scaling in positions")
        await self._notify_observers("scale_in")

    async def add_action_plan(
        self,
        name: str,
        threshold: float,
        action: DrawdownAction,
        parameters: Dict[str, Any],
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DrawdownActionPlan:
        async with self._lock:
            plan_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            plan = DrawdownActionPlan(
                id=plan_id,
                name=name,
                threshold=threshold,
                action=action,
                parameters=parameters,
                priority=priority,
                metadata=metadata or {}
            )
            
            self._action_plans[plan_id] = plan
            await self._notify_observers("action_plan_added", plan)
            return plan

    async def get_state(self) -> Optional[DrawdownState]:
        return self._state

    async def get_alerts(
        self,
        acknowledged: bool = False,
        level: Optional[str] = None,
        limit: int = 100
    ) -> List[DrawdownAlert]:
        alerts = [a for a in self._alerts.values() if a.acknowledged == acknowledged]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return alerts[:limit]

    async def acknowledge_alert(self, alert_id: str) -> bool:
        if alert_id in self._alerts:
            self._alerts[alert_id].acknowledged = True
            await self._notify_observers("alert_acknowledged", alert_id)
            return True
        return False

    async def get_action_plan(self, plan_id: str) -> Optional[DrawdownActionPlan]:
        return self._action_plans.get(plan_id)

    async def get_action_plans(self) -> List[DrawdownActionPlan]:
        return list(self._action_plans.values())

    async def enable_action_plan(self, plan_id: str) -> bool:
        if plan_id in self._action_plans:
            self._action_plans[plan_id].enabled = True
            return True
        return False

    async def disable_action_plan(self, plan_id: str) -> bool:
        if plan_id in self._action_plans:
            self._action_plans[plan_id].enabled = False
            return True
        return False

    async def delete_action_plan(self, plan_id: str) -> bool:
        if plan_id in self._action_plans:
            del self._action_plans[plan_id]
            return True
        return False

    async def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(self._history)[-limit:]

    async def compute_metrics(self) -> Dict[str, Any]:
        if not self._state:
            return {}
        
        total_points = len(self._history)
        if total_points == 0:
            return {}
        
        values = [h["value"] for h in self._history]
        returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
        
        avg_return = np.mean(returns) if returns else 0
        std_return = np.std(returns) if returns else 0
        
        avg_drawdown = np.mean([h["drawdown"] for h in self._history])
        max_drawdown = max([h["drawdown"] for h in self._history])
        
        drawdown_duration = 0
        current_streak = 0
        max_streak = 0
        
        for h in self._history:
            if h["drawdown"] > 0.01:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return {
            "total_points": total_points,
            "avg_return": avg_return,
            "std_return": std_return,
            "current_drawdown": self._state.current_drawdown,
            "max_drawdown": max_drawdown,
            "avg_drawdown": avg_drawdown,
            "drawdown_duration": drawdown_duration,
            "max_drawdown_streak": max_streak,
            "recovery_factor": self._state.recovery_factor,
            "consecutive_losses": self._state.consecutive_losses,
            "status": self._state.status.value
        }

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
            "alerts": len(self._alerts),
            "action_plans": len(self._action_plans),
            "history_size": len(self._history),
            "running": self._running
        }


__all__ = [
    "DrawdownStatus",
    "DrawdownAction",
    "DrawdownState",
    "DrawdownAlert",
    "DrawdownRecovery",
    "DrawdownActionPlan",
    "DrawdownController"
]

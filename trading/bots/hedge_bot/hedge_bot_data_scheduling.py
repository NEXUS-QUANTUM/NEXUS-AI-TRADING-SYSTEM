# trading/bots/hedge_bot/hedge_bot_data_scheduling.py

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
import croniter
import schedule

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    EVENT_DRIVEN = "event_driven"
    CONDITIONAL = "conditional"


class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PENDING = "pending"
    RUNNING = "running"


class SchedulePriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


@dataclass
class ScheduleTask:
    id: str
    name: str
    description: str
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]
    priority: SchedulePriority = SchedulePriority.MEDIUM
    status: ScheduleStatus = ScheduleStatus.PENDING
    max_retries: int = 3
    retry_delay: float = 5.0
    timeout: int = 300
    concurrent: bool = False
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    runs: List[Dict[str, Any]] = field(default_factory=list)
    handler: Optional[Callable] = None
    error_handler: Optional[Callable] = None


@dataclass
class ScheduleJob:
    id: str
    task_id: str
    scheduled_time: float
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    status: ScheduleStatus = ScheduleStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleTrigger:
    id: str
    name: str
    condition: str
    action: str
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class DataSchedulingManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._tasks: Dict[str, ScheduleTask] = {}
        self._jobs: Dict[str, ScheduleJob] = {}
        self._triggers: Dict[str, ScheduleTrigger] = {}
        self._handlers: Dict[str, Callable] = {}
        self._error_handlers: Dict[str, Callable] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._job_queue: asyncio.Queue = asyncio.Queue()
        self._active_jobs: Set[str] = set()
        self._job_history: deque = deque(maxlen=10000)
        self._worker_tasks: List[asyncio.Task] = []
        self._num_workers = self.config.get("num_workers", 4)
        
        self._initialize_default_tasks()

    def _initialize_default_tasks(self) -> None:
        default_tasks = [
            ScheduleTask(
                id="market_data_fetch",
                name="Market Data Fetch",
                description="Fetch latest market data",
                schedule_type=ScheduleType.INTERVAL,
                schedule_config={"interval_seconds": 60},
                priority=SchedulePriority.HIGH
            ),
            ScheduleTask(
                id="position_update",
                name="Position Update",
                description="Update positions and PnL",
                schedule_type=ScheduleType.INTERVAL,
                schedule_config={"interval_seconds": 30},
                priority=SchedulePriority.HIGH
            ),
            ScheduleTask(
                id="risk_analysis",
                name="Risk Analysis",
                description="Perform risk analysis",
                schedule_type=ScheduleType.INTERVAL,
                schedule_config={"interval_seconds": 300},
                priority=SchedulePriority.MEDIUM
            ),
            ScheduleTask(
                id="daily_summary",
                name="Daily Summary",
                description="Generate daily summary report",
                schedule_type=ScheduleType.DAILY,
                schedule_config={"time": "23:59"},
                priority=SchedulePriority.LOW
            ),
            ScheduleTask(
                id="data_cleanup",
                name="Data Cleanup",
                description="Cleanup old data",
                schedule_type=ScheduleType.WEEKLY,
                schedule_config={"day": "sunday", "time": "00:00"},
                priority=SchedulePriority.LOW
            )
        ]
        
        for task in default_tasks:
            self._tasks[task.id] = task

    def register_handler(self, task_id: str, handler: Callable) -> None:
        self._handlers[task_id] = handler

    def register_error_handler(self, task_id: str, handler: Callable) -> None:
        self._error_handlers[task_id] = handler

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_task(
        self,
        name: str,
        description: str,
        schedule_type: ScheduleType,
        schedule_config: Dict[str, Any],
        handler: Optional[Callable] = None,
        priority: SchedulePriority = SchedulePriority.MEDIUM,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        timeout: int = 300,
        concurrent: bool = False,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ScheduleTask:
        async with self._lock:
            task_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            task = ScheduleTask(
                id=task_id,
                name=name,
                description=description,
                schedule_type=schedule_type,
                schedule_config=schedule_config,
                priority=priority,
                status=ScheduleStatus.PENDING,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
                concurrent=concurrent,
                dependencies=dependencies or [],
                metadata=metadata or {}
            )
            
            if handler:
                self._handlers[task_id] = handler
            
            task.next_run = await self._calculate_next_run(task)
            self._tasks[task_id] = task
            
            await self._notify_observers("task_created", task)
            return task

    async def schedule_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            task.status = ScheduleStatus.ACTIVE
            task.next_run = await self._calculate_next_run(task)
            task.updated_at = time.time()
            
            await self._notify_observers("task_scheduled", task)
            return True

    async def pause_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            task.status = ScheduleStatus.PAUSED
            task.updated_at = time.time()
            
            await self._notify_observers("task_paused", task)
            return True

    async def resume_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            task.status = ScheduleStatus.ACTIVE
            task.next_run = await self._calculate_next_run(task)
            task.updated_at = time.time()
            
            await self._notify_observers("task_resumed", task)
            return True

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            task.status = ScheduleStatus.CANCELLED
            task.updated_at = time.time()
            
            await self._notify_observers("task_cancelled", task)
            return True

    async def _calculate_next_run(self, task: ScheduleTask) -> Optional[float]:
        now = time.time()
        
        if task.schedule_type == ScheduleType.CRON:
            cron_expr = task.schedule_config.get("expression")
            if cron_expr:
                cron = croniter.croniter(cron_expr, datetime.now())
                return cron.get_next().timestamp()
        
        elif task.schedule_type == ScheduleType.INTERVAL:
            interval = task.schedule_config.get("interval_seconds", 60)
            if task.last_run:
                return task.last_run + interval
            return now + interval
        
        elif task.schedule_type == ScheduleType.ONCE:
            scheduled_time = task.schedule_config.get("timestamp")
            if scheduled_time:
                return scheduled_time
        
        elif task.schedule_type == ScheduleType.DAILY:
            time_str = task.schedule_config.get("time", "00:00")
            hour, minute = map(int, time_str.split(':'))
            next_run = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run.timestamp() <= now:
                next_run += timedelta(days=1)
            return next_run.timestamp()
        
        elif task.schedule_type == ScheduleType.WEEKLY:
            day = task.schedule_config.get("day", "monday")
            time_str = task.schedule_config.get("time", "00:00")
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            target_day = days.index(day.lower())
            hour, minute = map(int, time_str.split(':'))
            now_dt = datetime.now()
            current_day = now_dt.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now_dt + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_run.timestamp()
        
        elif task.schedule_type == ScheduleType.MONTHLY:
            day = task.schedule_config.get("day", 1)
            time_str = task.schedule_config.get("time", "00:00")
            hour, minute = map(int, time_str.split(':'))
            now_dt = datetime.now()
            if now_dt.day < day:
                next_run = now_dt.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
            else:
                next_month = now_dt.replace(day=1) + timedelta(days=32)
                next_run = next_month.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
            return next_run.timestamp()
        
        return None

    async def _check_dependencies(self, task: ScheduleTask) -> bool:
        if not task.dependencies:
            return True
        
        for dep_id in task.dependencies:
            if dep_id in self._tasks:
                dep_task = self._tasks[dep_id]
                if dep_task.status != ScheduleStatus.COMPLETED:
                    return False
        
        return True

    async def _execute_task(self, job: ScheduleJob) -> None:
        task = self._tasks.get(job.task_id)
        if not task:
            return
        
        if task.id in self._active_jobs and not task.concurrent:
            return
        
        self._active_jobs.add(task.id)
        job.start_time = time.time()
        job.status = ScheduleStatus.RUNNING
        
        await self._notify_observers("job_started", job)
        
        try:
            handler = self._handlers.get(task.id)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(handler(task, job), timeout=task.timeout)
                else:
                    result = handler(task, job)
                job.result = result
                job.status = ScheduleStatus.COMPLETED
            else:
                job.status = ScheduleStatus.COMPLETED
                
        except asyncio.TimeoutError:
            job.status = ScheduleStatus.FAILED
            job.error = "Timeout"
            await self._handle_error(task, job)
            
        except Exception as e:
            job.status = ScheduleStatus.FAILED
            job.error = str(e)
            await self._handle_error(task, job)
            
        finally:
            job.end_time = time.time()
            task.last_run = job.end_time
            task.next_run = await self._calculate_next_run(task)
            task.updated_at = time.time()
            
            if job.status == ScheduleStatus.COMPLETED:
                task.runs.append({
                    "job_id": job.id,
                    "start_time": job.start_time,
                    "end_time": job.end_time,
                    "status": job.status.value
                })
            
            if task.id in self._active_jobs:
                self._active_jobs.remove(task.id)
            
            self._job_history.append(job)
            await self._notify_observers("job_completed", job)

    async def _handle_error(self, task: ScheduleTask, job: ScheduleJob) -> None:
        job.retry_count += 1
        
        if job.retry_count < task.max_retries:
            job.status = ScheduleStatus.PENDING
            job.scheduled_time = time.time() + task.retry_delay
            
            error_handler = self._error_handlers.get(task.id)
            if error_handler:
                try:
                    if asyncio.iscoroutinefunction(error_handler):
                        await error_handler(task, job)
                    else:
                        error_handler(task, job)
                except Exception as e:
                    logger.error(f"Error handler failed: {e}")
            
            await self._notify_observers("job_retrying", job)
            
        else:
            job.status = ScheduleStatus.FAILED
            task.status = ScheduleStatus.FAILED
            await self._notify_observers("job_failed", job)

    async def _scheduler_loop(self) -> None:
        while self._running:
            try:
                now = time.time()
                
                for task in self._tasks.values():
                    if task.status != ScheduleStatus.ACTIVE:
                        continue
                    
                    if task.next_run and task.next_run <= now:
                        if await self._check_dependencies(task):
                            job = ScheduleJob(
                                id=hashlib.md5(f"{task.id}_{time.time()}".encode()).hexdigest(),
                                task_id=task.id,
                                scheduled_time=now
                            )
                            
                            self._jobs[job.id] = job
                            await self._job_queue.put(job)
                            
                            if task.schedule_type != ScheduleType.ONCE:
                                task.next_run = await self._calculate_next_run(task)
                            else:
                                task.status = ScheduleStatus.COMPLETED
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(5)

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                job = await self._job_queue.get()
                await self._execute_task(job)
                self._job_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            
            self._running = True
            
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            
            for i in range(self._num_workers):
                worker_task = asyncio.create_task(self._worker_loop(i))
                self._worker_tasks.append(worker_task)
            
            logger.info(f"Scheduler started with {self._num_workers} workers")

    async def stop(self) -> None:
        async with self._lock:
            self._running = False
            
            if self._scheduler_task:
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
                self._scheduler_task = None
            
            for task in self._worker_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._worker_tasks.clear()
            
            logger.info("Scheduler stopped")

    async def get_task(self, task_id: str) -> Optional[ScheduleTask]:
        return self._tasks.get(task_id)

    async def get_tasks(
        self,
        status: Optional[ScheduleStatus] = None,
        priority: Optional[SchedulePriority] = None
    ) -> List[ScheduleTask]:
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        
        return tasks

    async def get_job(self, job_id: str) -> Optional[ScheduleJob]:
        return self._jobs.get(job_id)

    async def get_jobs(
        self,
        task_id: Optional[str] = None,
        status: Optional[ScheduleStatus] = None,
        limit: int = 100
    ) -> List[ScheduleJob]:
        jobs = list(self._jobs.values())
        
        if task_id:
            jobs = [j for j in jobs if j.task_id == task_id]
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        jobs.sort(key=lambda j: j.scheduled_time, reverse=True)
        return jobs[:limit]

    async def get_job_history(self, limit: int = 100) -> List[ScheduleJob]:
        return list(self._job_history)[-limit:]

    async def run_now(self, task_id: str) -> Optional[str]:
        async with self._lock:
            if task_id not in self._tasks:
                return None
            
            task = self._tasks[task_id]
            
            if task.status != ScheduleStatus.ACTIVE:
                return None
            
            job = ScheduleJob(
                id=hashlib.md5(f"{task_id}_{time.time()}".encode()).hexdigest(),
                task_id=task_id,
                scheduled_time=time.time()
            )
            
            self._jobs[job.id] = job
            await self._job_queue.put(job)
            
            return job.id

    async def create_trigger(
        self,
        name: str,
        condition: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ScheduleTrigger:
        trigger_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
        
        trigger = ScheduleTrigger(
            id=trigger_id,
            name=name,
            condition=condition,
            action=action,
            enabled=True,
            metadata=metadata or {}
        )
        
        self._triggers[trigger_id] = trigger
        return trigger

    async def evaluate_triggers(self, context: Dict[str, Any]) -> List[str]:
        triggered = []
        
        for trigger in self._triggers.values():
            if not trigger.enabled:
                continue
            
            try:
                if await self._evaluate_condition(trigger.condition, context):
                    triggered.append(trigger.id)
                    await self._execute_trigger(trigger, context)
            except Exception as e:
                logger.error(f"Trigger evaluation error: {e}")
        
        return triggered

    async def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        try:
            return eval(condition, {"__builtins__": {}}, context)
        except:
            return False

    async def _execute_trigger(self, trigger: ScheduleTrigger, context: Dict[str, Any]) -> None:
        action = trigger.action
        
        if action.startswith("task:"):
            task_id = action[5:]
            if task_id in self._tasks:
                await self.run_now(task_id)
        
        await self._notify_observers("trigger_executed", trigger, context)

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
        active_tasks = len([t for t in self._tasks.values() if t.status == ScheduleStatus.ACTIVE])
        running_jobs = len(self._active_jobs)
        pending_jobs = self._job_queue.qsize()
        completed_jobs = len([j for j in self._jobs.values() if j.status == ScheduleStatus.COMPLETED])
        failed_jobs = len([j for j in self._jobs.values() if j.status == ScheduleStatus.FAILED])
        
        return {
            "tasks": len(self._tasks),
            "active_tasks": active_tasks,
            "jobs": len(self._jobs),
            "running_jobs": running_jobs,
            "pending_jobs": pending_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "triggers": len(self._triggers),
            "workers": self._num_workers,
            "running": self._running,
            "job_history": len(self._job_history)
        }


__all__ = [
    "ScheduleType",
    "ScheduleStatus",
    "SchedulePriority",
    "ScheduleTask",
    "ScheduleJob",
    "ScheduleTrigger",
    "DataSchedulingManager"
]

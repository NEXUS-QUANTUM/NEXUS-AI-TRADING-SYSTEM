# trading/bots/hedge_bot/hedge_bot_data_orchestration.py
# Advanced Data Orchestration & Workflow Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Orchestration Module - Module avancé d'orchestration des données et de gestion
des workflows pour le Hedge Bot. Gère les pipelines de données, l'automatisation des workflows,
la coordination des tâches, les dépendances et l'exécution des processus de données.
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
from collections import defaultdict, deque
import hashlib
import pickle
import zlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_orchestration")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class WorkflowType(Enum):
    """Types de workflows."""
    ETL = "etl"                        # Extract, Transform, Load
    DATA_PIPELINE = "data_pipeline"    # Pipeline de données
    BATCH_PROCESS = "batch_process"    # Traitement par batch
    STREAM_PROCESS = "stream_process"  # Traitement de flux
    ANALYTICS = "analytics"            # Analytique
    REPORTING = "reporting"            # Reporting
    ML_PIPELINE = "ml_pipeline"        # Pipeline ML
    TRAINING = "training"              # Entraînement
    VALIDATION = "validation"          # Validation
    MONITORING = "monitoring"          # Monitoring


class WorkflowStatus(Enum):
    """Statuts des workflows."""
    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SCHEDULED = "scheduled"


class TaskStatus(Enum):
    """Statuts des tâches."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class TaskDependency(Enum):
    """Types de dépendances."""
    SEQUENTIAL = "sequential"          # Séquentielle
    PARALLEL = "parallel"              # Parallèle
    CONDITIONAL = "conditional"        # Conditionnelle
    OR = "or"                          # OR
    AND = "and"                        # AND
    TIMEOUT = "timeout"                # Timeout


# ============== DATA MODELS ==============

@dataclass
class Workflow:
    """Modèle de workflow."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    workflow_type: WorkflowType = WorkflowType.DATA_PIPELINE
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    schedule: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.CREATED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Task:
    """Modèle de tâche."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    name: str = ""
    task_type: str = ""
    action: Callable = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: float = 0.0
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class WorkflowExecution:
    """Exécution de workflow."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.RUNNING
    tasks: List[Task] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration: float = 0.0
    logs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowTrigger:
    """Trigger de workflow."""
    trigger_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    trigger_type: str = ""  # schedule, event, manual
    schedule: Optional[str] = None
    event: Optional[str] = None
    condition: Optional[str] = None
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class OrchestrationEngineInterface(ABC):
    """Interface abstraite pour le moteur d'orchestration."""
    
    @abstractmethod
    async def create_workflow(self, workflow: Workflow) -> str:
        """Crée un workflow."""
        pass
    
    @abstractmethod
    async def execute_workflow(self, workflow_id: str) -> WorkflowExecution:
        """Exécute un workflow."""
        pass
    
    @abstractmethod
    async def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Récupère une exécution de workflow."""
        pass


# ============== IMPLÉMENTATION ==============

class OrchestrationEngine(OrchestrationEngineInterface):
    """
    Moteur d'orchestration avancé pour le Hedge Bot.
    Gère les workflows, les tâches, les dépendances et l'exécution.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des workflows
        self._workflows: Dict[str, Workflow] = {}
        self._workflows_lock = threading.RLock()
        
        # Gestion des tâches
        self._tasks: Dict[str, Task] = {}
        self._tasks_lock = threading.RLock()
        
        # Gestion des exécutions
        self._executions: Dict[str, WorkflowExecution] = {}
        self._exec_lock = threading.RLock()
        
        # Gestion des triggers
        self._triggers: Dict[str, WorkflowTrigger] = {}
        self._trigger_lock = threading.RLock()
        
        # Queue d'exécution
        self._execution_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("OrchestrationEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "max_parallel_tasks": 10,
            "default_timeout": 3600,
            "default_retries": 3,
            "retry_delay": 5,
            "execution_timeout": 86400,
            "enable_parallel": True,
            "enable_dependency_validation": True,
            "max_executions": 1000,
            "schedule_check_interval": 60,
            "cache_size": 100,
            "log_retention_days": 30
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'orchestration."""
        logger.info("OrchestrationEngine starting...")
        self._is_running = True
        
        # Chargement des workflows
        await self._load_workflows()
        
        # Chargement des triggers
        await self._load_triggers()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._execution_processor())
        asyncio.create_task(self._scheduler_loop())
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("OrchestrationEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'orchestration."""
        logger.info("OrchestrationEngine stopping...")
        self._is_running = False
        
        # Attente des exécutions en cours
        await self._drain_queue()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("OrchestrationEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_workflow(self, workflow: Workflow) -> str:
        """Crée un workflow."""
        # Validation des tâches
        for task_config in workflow.tasks:
            if "action" not in task_config:
                raise ValueError(f"Task {task_config.get('name', 'unknown')} missing action")
        
        with self._workflows_lock:
            self._workflows[workflow.workflow_id] = workflow
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"orchestration:workflow:{workflow.workflow_id}",
                workflow.to_dict(),
                DataType.WORKFLOW
            )
        
        logger.info(f"Workflow created: {workflow.name} (id={workflow.workflow_id})")
        return workflow.workflow_id
    
    async def execute_workflow(self, workflow_id: str) -> WorkflowExecution:
        """Exécute un workflow."""
        with self._workflows_lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")
        
        # Création de l'exécution
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            tasks=await self._create_tasks(workflow)
        )
        
        with self._exec_lock:
            self._executions[execution.execution_id] = execution
        
        # Mise en queue
        await self._execution_queue.put((execution.execution_id, workflow))
        
        # Attente du résultat
        while execution.status in [WorkflowStatus.RUNNING, WorkflowStatus.PENDING]:
            await asyncio.sleep(0.1)
        
        return execution
    
    async def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Récupère une exécution de workflow."""
        with self._exec_lock:
            return self._executions.get(execution_id)
    
    # ========== MÉTHODES PRIVÉES - EXÉCUTION ==========
    
    async def _execution_processor(self) -> None:
        """Traite les exécutions de workflows."""
        while self._is_running:
            try:
                execution_id, workflow = await self._execution_queue.get()
                
                # Exécution du workflow
                asyncio.create_task(self._run_workflow(execution_id, workflow))
                
            except Exception as e:
                logger.error(f"Execution processor error: {e}")
                await asyncio.sleep(1)
    
    async def _run_workflow(self, execution_id: str, workflow: Workflow) -> None:
        """Exécute un workflow."""
        with self._exec_lock:
            execution = self._executions.get(execution_id)
            if not execution:
                return
        
        try:
            execution.status = WorkflowStatus.RUNNING
            execution.start_time = datetime.now(timezone.utc)
            
            # Topological sort des tâches
            sorted_tasks = await self._topological_sort(execution.tasks, workflow)
            
            # Exécution parallèle
            semaphore = asyncio.Semaphore(self.config["max_parallel_tasks"])
            
            async def execute_task(task: Task) -> None:
                async with semaphore:
                    await self._execute_task(task)
            
            tasks = [execute_task(task) for task in sorted_tasks]
            await asyncio.gather(*tasks)
            
            # Vérification du statut final
            failed = any(t.status == TaskStatus.FAILED for t in execution.tasks)
            
            if failed:
                execution.status = WorkflowStatus.FAILED
            else:
                execution.status = WorkflowStatus.COMPLETED
            
            execution.end_time = datetime.now(timezone.utc)
            execution.duration = (execution.end_time - execution.start_time).total_seconds()
            
            logger.info(f"Workflow executed: {workflow.name} status={execution.status.value}")
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.end_time = datetime.now(timezone.utc)
            execution.logs.append(f"Workflow execution failed: {str(e)}")
            logger.error(f"Workflow execution error: {e}")
    
    async def _create_tasks(self, workflow: Workflow) -> List[Task]:
        """Crée les tâches d'un workflow."""
        tasks = []
        
        for task_config in workflow.tasks:
            task = Task(
                workflow_id=workflow.workflow_id,
                name=task_config.get("name", f"Task_{uuid.uuid4().hex[:8]}"),
                task_type=task_config.get("type", "default"),
                action=task_config.get("action"),
                parameters=task_config.get("parameters", {}),
                dependencies=task_config.get("dependencies", []),
                max_retries=task_config.get("max_retries", 3),
                timeout=task_config.get("timeout", 300),
                metadata=task_config.get("metadata", {}),
                tags=task_config.get("tags", [])
            )
            tasks.append(task)
        
        return tasks
    
    async def _execute_task(self, task: Task) -> None:
        """Exécute une tâche."""
        task.start_time = datetime.now(timezone.utc)
        task.status = TaskStatus.RUNNING
        
        try:
            # Vérification des dépendances
            if not await self._check_dependencies(task):
                task.status = TaskStatus.SKIPPED
                return
            
            # Exécution de l'action
            if asyncio.iscoroutinefunction(task.action):
                result = await asyncio.wait_for(
                    task.action(**task.parameters),
                    timeout=task.timeout
                )
            else:
                result = task.action(**task.parameters)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
            task.error = f"Task timed out after {task.timeout}s"
            
            if task.retry_count < task.max_retries:
                await self._retry_task(task)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            
            if task.retry_count < task.max_retries:
                await self._retry_task(task)
            
        finally:
            task.end_time = datetime.now(timezone.utc)
            task.duration = (task.end_time - task.start_time).total_seconds()
            
            logger.debug(f"Task {task.name} completed: {task.status.value}")
    
    async def _retry_task(self, task: Task) -> None:
        """Réessaie une tâche échouée."""
        task.retry_count += 1
        task.status = TaskStatus.PENDING
        
        # Attente avant de réessayer
        await asyncio.sleep(self.config["retry_delay"])
        
        # Réexécution
        await self._execute_task(task)
    
    async def _check_dependencies(self, task: Task) -> bool:
        """Vérifie les dépendances d'une tâche."""
        if not task.dependencies:
            return True
        
        with self._tasks_lock:
            for dep_id in task.dependencies:
                dep_task = self._tasks.get(dep_id)
                if not dep_task:
                    return False
                
                if dep_task.status != TaskStatus.COMPLETED:
                    return False
        
        return True
    
    async def _topological_sort(self, tasks: List[Task], workflow: Workflow) -> List[Task]:
        """Tri topologique des tâches."""
        # Création du graphe de dépendances
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        for task in tasks:
            in_degree[task.task_id] = 0
        
        for task in tasks:
            for dep_id in task.dependencies:
                graph[dep_id].append(task.task_id)
                in_degree[task.task_id] += 1
        
        # Tri topologique
        queue = deque([t for t in tasks if in_degree[t.task_id] == 0])
        sorted_tasks = []
        
        while queue:
            task = queue.popleft()
            sorted_tasks.append(task)
            
            for neighbor_id in graph[task.task_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    neighbor = next(t for t in tasks if t.task_id == neighbor_id)
                    queue.append(neighbor)
        
        return sorted_tasks
    
    # ========== MÉTHODES PRIVÉES - SCHEDULER ==========
    
    async def _scheduler_loop(self) -> None:
        """Boucle de planification des workflows."""
        while self._is_running:
            await asyncio.sleep(self.config["schedule_check_interval"])
            
            try:
                now = datetime.now(timezone.utc)
                
                with self._trigger_lock:
                    for trigger in self._triggers.values():
                        if not trigger.active:
                            continue
                        
                        if trigger.trigger_type == "schedule":
                            # Vérification du planning
                            if await self._should_run(trigger, now):
                                with self._workflows_lock:
                                    workflow = self._workflows.get(trigger.workflow_id)
                                    if workflow:
                                        await self.execute_workflow(workflow.workflow_id)
                
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
    
    def _should_run(self, trigger: WorkflowTrigger, now: datetime) -> bool:
        """Vérifie si le trigger doit s'exécuter."""
        # Simulation de planning
        return False
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["log_retention_days"])
                
                with self._exec_lock:
                    old_executions = [
                        eid for eid, exec in self._executions.items()
                        if exec.end_time and exec.end_time < cutoff
                    ]
                    
                    for eid in old_executions:
                        del self._executions[eid]
                
                if old_executions:
                    logger.debug(f"Cleaned up {len(old_executions)} old executions")
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la queue d'exécution."""
        while not self._execution_queue.empty():
            try:
                execution_id, workflow = await self._execution_queue.get()
                with self._exec_lock:
                    if execution_id in self._executions:
                        self._executions[execution_id].status = WorkflowStatus.CANCELLED
            except Exception:
                break
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._workflows_lock:
                    self._stats["total_workflows"] = len(self._workflows)
                    active_workflows = len([w for w in self._workflows.values() if w.active])
                    self._stats["active_workflows"] = active_workflows
                
                with self._exec_lock:
                    self._stats["total_executions"] = len(self._executions)
                    running_executions = len([e for e in self._executions.values() if e.status == WorkflowStatus.RUNNING])
                    self._stats["running_executions"] = running_executions
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "orchestration:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_workflows(self) -> None:
        """Charge les workflows existants."""
        try:
            if self.data_manager:
                workflows_data = await self.data_manager.retrieve(
                    "orchestration:workflows",
                    DataType.WORKFLOW
                )
                
                if workflows_data:
                    for wf_dict in workflows_data:
                        workflow = self._deserialize_workflow(wf_dict)
                        if workflow:
                            with self._workflows_lock:
                                self._workflows[workflow.workflow_id] = workflow
            
            logger.info(f"Loaded {len(self._workflows)} workflows")
            
        except Exception as e:
            logger.error(f"Load workflows error: {e}")
    
    async def _load_triggers(self) -> None:
        """Charge les triggers existants."""
        try:
            if self.data_manager:
                triggers_data = await self.data_manager.retrieve(
                    "orchestration:triggers",
                    DataType.TRIGGER
                )
                
                if triggers_data:
                    for trigger_dict in triggers_data:
                        trigger = self._deserialize_trigger(trigger_dict)
                        if trigger:
                            with self._trigger_lock:
                                self._triggers[trigger.trigger_id] = trigger
            
            logger.info(f"Loaded {len(self._triggers)} triggers")
            
        except Exception as e:
            logger.error(f"Load triggers error: {e}")
    
    def _deserialize_workflow(self, data: Dict) -> Optional[Workflow]:
        """Désérialise un workflow."""
        try:
            return Workflow(
                workflow_id=data.get("workflow_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                description=data.get("description", ""),
                workflow_type=WorkflowType(data.get("workflow_type", "data_pipeline")),
                tasks=data.get("tasks", []),
                dependencies=data.get("dependencies", []),
                schedule=data.get("schedule"),
                status=WorkflowStatus(data.get("status", "created")),
                start_time=datetime.fromisoformat(data.get("start_time")) if data.get("start_time") else None,
                end_time=datetime.fromisoformat(data.get("end_time")) if data.get("end_time") else None,
                retry_count=data.get("retry_count", 0),
                max_retries=data.get("max_retries", 3),
                timeout=data.get("timeout", 3600),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing workflow: {e}")
            return None
    
    def _deserialize_trigger(self, data: Dict) -> Optional[WorkflowTrigger]:
        """Désérialise un trigger."""
        try:
            return WorkflowTrigger(
                trigger_id=data.get("trigger_id", str(uuid.uuid4())),
                workflow_id=data.get("workflow_id", ""),
                trigger_type=data.get("trigger_type", ""),
                schedule=data.get("schedule"),
                event=data.get("event"),
                condition=data.get("condition"),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing trigger: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Récupère un workflow."""
        with self._workflows_lock:
            return self._workflows.get(workflow_id)
    
    async def get_workflows(self) -> List[Workflow]:
        """Récupère les workflows."""
        with self._workflows_lock:
            return list(self._workflows.values())
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Récupère une tâche."""
        with self._tasks_lock:
            return self._tasks.get(task_id)
    
    async def create_trigger(self, trigger: WorkflowTrigger) -> str:
        """Crée un trigger."""
        with self._trigger_lock:
            self._triggers[trigger.trigger_id] = trigger
        
        if self.data_manager:
            await self.data_manager.store(
                f"orchestration:trigger:{trigger.trigger_id}",
                trigger.to_dict(),
                DataType.TRIGGER
            )
        
        logger.info(f"Trigger created for workflow {trigger.workflow_id}")
        return trigger.trigger_id
    
    async def get_trigger(self, trigger_id: str) -> Optional[WorkflowTrigger]:
        """Récupère un trigger."""
        with self._trigger_lock:
            return self._triggers.get(trigger_id)
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Annule une exécution."""
        with self._exec_lock:
            execution = self._executions.get(execution_id)
            if not execution or execution.status not in [WorkflowStatus.PENDING, WorkflowStatus.RUNNING]:
                return False
            
            execution.status = WorkflowStatus.CANCELLED
            execution.end_time = datetime.now(timezone.utc)
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._workflows_lock:
            self._stats["total_workflows"] = len(self._workflows)
        with self._exec_lock:
            self._stats["total_executions"] = len(self._executions)
        
        return self._stats.copy()


# ============== WORKFLOW BUILDER ==============

class WorkflowBuilder:
    """
    Constructeur de workflows.
    Facilite la création de workflows complexes.
    """
    
    def __init__(self):
        self._workflow = Workflow()
        self._tasks = []
    
    def name(self, name: str) -> 'WorkflowBuilder':
        """Définit le nom du workflow."""
        self._workflow.name = name
        return self
    
    def description(self, description: str) -> 'WorkflowBuilder':
        """Définit la description."""
        self._workflow.description = description
        return self
    
    def type(self, workflow_type: WorkflowType) -> 'WorkflowBuilder':
        """Définit le type."""
        self._workflow.workflow_type = workflow_type
        return self
    
    def task(self, name: str, action: Callable, **kwargs) -> 'WorkflowBuilder':
        """Ajoute une tâche."""
        task_config = {
            "name": name,
            "action": action,
            "parameters": kwargs.get("parameters", {}),
            "dependencies": kwargs.get("dependencies", []),
            "max_retries": kwargs.get("max_retries", 3),
            "timeout": kwargs.get("timeout", 300),
            "metadata": kwargs.get("metadata", {}),
            "tags": kwargs.get("tags", [])
        }
        self._tasks.append(task_config)
        return self
    
    def schedule(self, schedule: str) -> 'WorkflowBuilder':
        """Définit le planning."""
        self._workflow.schedule = schedule
        return self
    
    def timeout(self, timeout: int) -> 'WorkflowBuilder':
        """Définit le timeout."""
        self._workflow.timeout = timeout
        return self
    
    def max_retries(self, retries: int) -> 'WorkflowBuilder':
        """Définit le nombre de retries."""
        self._workflow.max_retries = retries
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'WorkflowBuilder':
        """Définit les métadonnées."""
        self._workflow.metadata = metadata
        return self
    
    def tags(self, tags: List[str]) -> 'WorkflowBuilder':
        """Définit les tags."""
        self._workflow.tags = tags
        return self
    
    def build(self) -> Workflow:
        """Construit le workflow."""
        self._workflow.tasks = self._tasks
        return self._workflow


# ============== FACTORY ==============

class OrchestrationFactory:
    """Factory pour créer des composants d'orchestration."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> OrchestrationEngine:
        """Crée un moteur d'orchestration."""
        engine = OrchestrationEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_builder() -> WorkflowBuilder:
        """Crée un constructeur de workflows."""
        return WorkflowBuilder()


# ============== EXPORT ==============

__all__ = [
    "WorkflowType",
    "WorkflowStatus",
    "TaskStatus",
    "TaskDependency",
    "Workflow",
    "Task",
    "WorkflowExecution",
    "WorkflowTrigger",
    "OrchestrationEngineInterface",
    "OrchestrationEngine",
    "WorkflowBuilder",
    "OrchestrationFactory"
]

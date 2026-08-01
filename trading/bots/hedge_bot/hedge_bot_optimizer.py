# trading/bots/hedge_bot/hedge_bot_optimizer.py
# Advanced System Optimization & Performance Tuning Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Optimizer Module - Module avancé d'optimisation du système et de réglage des performances
pour le Hedge Bot. Optimise les paramètres système, la configuration, les performances,
les ressources, et l'efficacité globale du système de hedging.
"""

import asyncio
import json
import time
import psutil
import platform
import gc
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import pickle
import zlib
import os
import sys
import resource

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_optimizer")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class OptimizationTarget(Enum):
    """Cibles d'optimisation."""
    PERFORMANCE = "performance"      # Performance générale
    MEMORY = "memory"                # Utilisation mémoire
    CPU = "cpu"                      # Utilisation CPU
    LATENCY = "latency"              # Latence
    THROUGHPUT = "throughput"        # Débit
    NETWORK = "network"              # Réseau
    STORAGE = "storage"              # Stockage
    CONFIGURATION = "configuration"  # Configuration
    PARAMETERS = "parameters"        # Paramètres


class OptimizationMethod(Enum):
    """Méthodes d'optimisation."""
    GRID_SEARCH = "grid_search"          # Recherche par grille
    RANDOM_SEARCH = "random_search"      # Recherche aléatoire
    BAYESIAN = "bayesian"                # Optimisation bayésienne
    GENETIC = "genetic"                  # Algorithme génétique
    SIMULATED_ANNEALING = "simulated_annealing"  # Recuit simulé
    GRADIENT = "gradient"                # Descente de gradient
    AUTO = "auto"                        # Automatique


class OptimizationStatus(Enum):
    """Statuts d'optimisation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


# ============== DATA MODELS ==============

@dataclass
class OptimizationJob:
    """Job d'optimisation."""
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    target: OptimizationTarget = OptimizationTarget.PERFORMANCE
    method: OptimizationMethod = OptimizationMethod.BAYESIAN
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    status: OptimizationStatus = OptimizationStatus.PENDING
    progress: float = 0.0
    best_params: Dict[str, Any] = field(default_factory=dict)
    best_score: float = 0.0
    iterations: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class SystemMetrics:
    """Métriques système."""
    metrics_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_percent: float = 0.0
    cpu_count: int = 0
    memory_percent: float = 0.0
    memory_available: float = 0.0
    memory_used: float = 0.0
    disk_percent: float = 0.0
    disk_used: float = 0.0
    disk_free: float = 0.0
    network_sent: float = 0.0
    network_recv: float = 0.0
    process_cpu: float = 0.0
    process_memory: float = 0.0
    thread_count: int = 0
    open_files: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    """Résultat d'optimisation."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    target: OptimizationTarget = OptimizationTarget.PERFORMANCE
    original_value: float = 0.0
    optimized_value: float = 0.0
    improvement: float = 0.0
    improvement_percent: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    applied: bool = False
    applied_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class OptimizerInterface(ABC):
    """Interface abstraite pour l'optimiseur."""
    
    @abstractmethod
    async def create_job(self, config: Dict[str, Any]) -> OptimizationJob:
        """Crée un job d'optimisation."""
        pass
    
    @abstractmethod
    async def run_job(self, job_id: str) -> OptimizationJob:
        """Exécute un job d'optimisation."""
        pass
    
    @abstractmethod
    async def apply_optimization(self, job_id: str) -> bool:
        """Applique les résultats d'optimisation."""
        pass


# ============== IMPLÉMENTATION ==============

class SystemOptimizer(OptimizerInterface):
    """
    Optimiseur système avancé pour le Hedge Bot.
    Optimise les performances et l'efficacité du système.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des jobs
        self._jobs: Dict[str, OptimizationJob] = {}
        self._jobs_lock = threading.RLock()
        
        # Gestion des métriques
        self._metrics: List[SystemMetrics] = []
        self._metrics_lock = threading.RLock()
        
        # Gestion des résultats
        self._results: Dict[str, OptimizationResult] = {}
        self._results_lock = threading.RLock()
        
        # Cache des paramètres optimisés
        self._optimized_params: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "jobs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "optimizations_applied": 0,
            "total_improvement": 0.0,
            "avg_improvement": 0.0,
            "system_cpu_avg": 0.0,
            "system_memory_avg": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Queue d'optimisation
        self._optimization_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # État
        self._is_running = False
        
        logger.info("SystemOptimizer initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_method": OptimizationMethod.BAYESIAN,
            "default_target": OptimizationTarget.PERFORMANCE,
            "max_iterations": 100,
            "convergence_threshold": 0.001,
            "memory_limit_mb": 4096,
            "cpu_limit_percent": 80,
            "optimization_interval": 3600,
            "metrics_interval": 60,
            "enable_auto_optimization": True,
            "auto_optimization_interval": 86400,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_caching": True
        }
    
    async def start(self) -> None:
        """Démarre l'optimiseur système."""
        logger.info("SystemOptimizer starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._optimization_processor())
        asyncio.create_task(self._auto_optimization_loop())
        asyncio.create_task(self._cache_cleaner())
        
        logger.info("SystemOptimizer started")
    
    async def stop(self) -> None:
        """Arrête l'optimiseur système."""
        logger.info("SystemOptimizer stopping...")
        self._is_running = False
        
        # Drain de la queue
        await self._drain_queue()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("SystemOptimizer stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_job(self, config: Dict[str, Any]) -> OptimizationJob:
        """Crée un job d'optimisation."""
        job = OptimizationJob(
            name=config.get("name", f"Optimization_{uuid.uuid4().hex[:8]}"),
            target=OptimizationTarget(config.get("target", "performance")),
            method=OptimizationMethod(config.get("method", "bayesian")),
            parameters=config.get("parameters", {}),
            constraints=config.get("constraints", {}),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        with self._jobs_lock:
            self._jobs[job.job_id] = job
            self._stats["jobs_created"] += 1
        
        # Mise en queue
        await self._optimization_queue.put(job)
        
        logger.info(f"Optimization job created: {job.name} (id={job.job_id})")
        return job
    
    async def run_job(self, job_id: str) -> OptimizationJob:
        """Exécute un job d'optimisation."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
        
        job.status = OptimizationStatus.RUNNING
        job.start_time = datetime.now(timezone.utc)
        
        try:
            # Exécution selon la méthode
            if job.method == OptimizationMethod.GRID_SEARCH:
                result = await self._grid_search_optimization(job)
            elif job.method == OptimizationMethod.RANDOM_SEARCH:
                result = await self._random_search_optimization(job)
            elif job.method == OptimizationMethod.BAYESIAN:
                result = await self._bayesian_optimization(job)
            elif job.method == OptimizationMethod.GENETIC:
                result = await self._genetic_optimization(job)
            elif job.method == OptimizationMethod.SIMULATED_ANNEALING:
                result = await self._simulated_annealing_optimization(job)
            else:
                result = await self._auto_optimization(job)
            
            # Mise à jour du job
            job.status = OptimizationStatus.COMPLETED
            job.progress = 1.0
            job.best_params = result["params"]
            job.best_score = result["score"]
            job.iterations = result.get("iterations", 0)
            job.metrics = result.get("metrics", {})
            job.end_time = datetime.now(timezone.utc)
            
            self._stats["jobs_completed"] += 1
            self._stats["avg_improvement"] = (
                self._stats["avg_improvement"] * 0.9 + result.get("improvement", 0) * 0.1
            )
            
            # Création du résultat
            optimization_result = OptimizationResult(
                job_id=job_id,
                target=job.target,
                original_value=result.get("original_value", 0),
                optimized_value=result.get("optimized_value", 0),
                improvement=result.get("improvement", 0),
                improvement_percent=result.get("improvement_percent", 0),
                parameters=result["params"]
            )
            
            with self._results_lock:
                self._results[optimization_result.result_id] = optimization_result
            
            logger.info(f"Optimization completed: {job.name} score={job.best_score:.4f}")
            return job
            
        except Exception as e:
            job.status = OptimizationStatus.FAILED
            job.end_time = datetime.now(timezone.utc)
            job.logs.append(f"Error: {str(e)}")
            self._stats["jobs_failed"] += 1
            
            logger.error(f"Optimization error: {e}")
            raise
    
    async def apply_optimization(self, job_id: str) -> bool:
        """Applique les résultats d'optimisation."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job or job.status != OptimizationStatus.COMPLETED:
                return False
        
        try:
            # Application des paramètres optimisés
            for key, value in job.best_params.items():
                with self._cache_lock:
                    self._optimized_params[key] = value
            
            # Mise à jour de la configuration
            # Dans un système réel, on mettrait à jour la configuration système
            
            # Création du résultat d'application
            with self._results_lock:
                for result in self._results.values():
                    if result.job_id == job_id:
                        result.applied = True
                        result.applied_at = datetime.now(timezone.utc)
                        break
            
            self._stats["optimizations_applied"] += 1
            self._stats["total_improvement"] += job.best_score
            
            logger.info(f"Optimization applied: {job.name}")
            return True
            
        except Exception as e:
            logger.error(f"Apply optimization error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - OPTIMISATION ==========
    
    async def _grid_search_optimization(self, job: OptimizationJob) -> Dict[str, Any]:
        """Optimisation par recherche en grille."""
        # Simulation de recherche en grille
        best_score = -float('inf')
        best_params = job.parameters.copy()
        
        # Définition de la grille
        grid = {}
        for key, value in job.parameters.items():
            if isinstance(value, dict) and "values" in value:
                grid[key] = value["values"]
            else:
                grid[key] = [value]
        
        # Parcours de la grille
        total = np.prod([len(v) for v in grid.values()])
        iteration = 0
        
        for params in self._generate_grid(grid):
            iteration += 1
            progress = iteration / total
            
            # Évaluation des paramètres
            score = await self._evaluate_params(job, params)
            
            if score > best_score:
                best_score = score
                best_params = params.copy()
            
            job.progress = progress
        
        return {
            "params": best_params,
            "score": best_score,
            "iterations": iteration,
            "original_value": 0,
            "optimized_value": best_score,
            "improvement": best_score - 0,
            "improvement_percent": (best_score - 0) / (0 + 0.01) * 100
        }
    
    async def _random_search_optimization(self, job: OptimizationJob) -> Dict[str, Any]:
        """Optimisation par recherche aléatoire."""
        best_score = -float('inf')
        best_params = job.parameters.copy()
        iterations = self.config["max_iterations"]
        
        for i in range(iterations):
            # Génération de paramètres aléatoires
            params = {}
            for key, value in job.parameters.items():
                if isinstance(value, dict):
                    if "min" in value and "max" in value:
                        params[key] = np.random.uniform(value["min"], value["max"])
                    elif "values" in value:
                        params[key] = np.random.choice(value["values"])
                else:
                    params[key] = value
            
            # Évaluation
            score = await self._evaluate_params(job, params)
            
            if score > best_score:
                best_score = score
                best_params = params.copy()
            
            job.progress = (i + 1) / iterations
        
        return {
            "params": best_params,
            "score": best_score,
            "iterations": iterations,
            "original_value": 0,
            "optimized_value": best_score,
            "improvement": best_score - 0,
            "improvement_percent": (best_score - 0) / (0 + 0.01) * 100
        }
    
    async def _bayesian_optimization(self, job: OptimizationJob) -> Dict[str, Any]:
        """Optimisation bayésienne."""
        # Simulation d'optimisation bayésienne
        best_score = -float('inf')
        best_params = job.parameters.copy()
        iterations = self.config["max_iterations"]
        
        for i in range(iterations):
            # Simulation de l'acquisition
            params = {}
            for key, value in job.parameters.items():
                if isinstance(value, dict):
                    if "min" in value and "max" in value:
                        params[key] = np.random.uniform(value["min"], value["max"])
                    elif "values" in value:
                        params[key] = np.random.choice(value["values"])
                else:
                    params[key] = value
            
            # Évaluation
            score = await self._evaluate_params(job, params)
            
            if score > best_score:
                best_score = score
                best_params = params.copy()
            
            job.progress = (i + 1) / iterations
            
            # Vérification de la convergence
            if i > 10 and abs(score - best_score) < self.config["convergence_threshold"]:
                break
        
        return {
            "params": best_params,
            "score": best_score,
            "iterations": i + 1,
            "original_value": 0,
            "optimized_value": best_score,
            "improvement": best_score - 0,
            "improvement_percent": (best_score - 0) / (0 + 0.01) * 100
        }
    
    async def _genetic_optimization(self, job: OptimizationJob) -> Dict[str, Any]:
        """Optimisation par algorithme génétique."""
        # Simulation d'algorithme génétique
        best_score = -float('inf')
        best_params = job.parameters.copy()
        generations = self.config["max_iterations"] // 10
        
        for gen in range(generations):
            # Simulation de population
            population = []
            for _ in range(10):
                params = {}
                for key, value in job.parameters.items():
                    if isinstance(value, dict):
                        if "min" in value and "max" in value:
                            params[key] = np.random.uniform(value["min"], value["max"])
                        elif "values" in value:
                            params[key] = np.random.choice(value["values"])
                    else:
                        params[key] = value
                
                score = await self._evaluate_params(job, params)
                population.append((params, score))
            
            # Sélection du meilleur
            best = max(population, key=lambda x: x[1])
            
            if best[1] > best_score:
                best_score = best[1]
                best_params = best[0].copy()
            
            job.progress = (gen + 1) / generations
        
        return {
            "params": best_params,
            "score": best_score,
            "iterations": generations * 10,
            "original_value": 0,
            "optimized_value": best_score,
            "improvement": best_score - 0,
            "improvement_percent": (best_score - 0) / (0 + 0.01) * 100
        }
    
    async def _simulated_annealing_optimization(self, job: OptimizationJob) -> Dict[str, Any]:
        """Optimisation par recuit simulé."""
        best_score = -float('inf')
        best_params = job.parameters.copy()
        iterations = self.config["max_iterations"]
        
        temperature = 100.0
        cooling_rate = 0.99
        
        current_params = job.parameters.copy()
        current_score = await self._evaluate_params(job, current_params)
        
        for i in range(iterations):
            # Génération d'un voisin
            neighbor = current_params.copy()
            for key in neighbor.keys():
                if isinstance(neighbor[key], dict):
                    if "min" in neighbor[key] and "max" in neighbor[key]:
                        step = (neighbor[key]["max"] - neighbor[key]["min"]) * 0.1
                        neighbor[key] = np.random.normal(neighbor[key], step)
                        neighbor[key] = max(neighbor[key]["min"], min(neighbor[key]["max"], neighbor[key]))
                    elif "values" in neighbor[key]:
                        neighbor[key] = np.random.choice(neighbor[key]["values"])
            
            neighbor_score = await self._evaluate_params(job, neighbor)
            
            # Acceptation
            if neighbor_score > current_score:
                current_params = neighbor
                current_score = neighbor_score
            else:
                if np.random.random() < np.exp((neighbor_score - current_score) / temperature):
                    current_params = neighbor
                    current_score = neighbor_score
            
            if current_score > best_score:
                best_score = current_score
                best_params = current_params.copy()
            
            temperature *= cooling_rate
            job.progress = (i + 1) / iterations
        
        return {
            "params": best_params,
            "score": best_score,
            "iterations": iterations,
            "original_value": 0,
            "optimized_value": best_score,
            "improvement": best_score - 0,
            "improvement_percent": (best_score - 0) / (0 + 0.01) * 100
        }
    
    async def _auto_optimization(self, job: OptimizationJob) -> Dict[str, Any]:
        """Optimisation automatique."""
        # Sélection automatique de la méthode
        return await self._bayesian_optimization(job)
    
    async def _evaluate_params(self, job: OptimizationJob, params: Dict[str, Any]) -> float:
        """Évalue des paramètres."""
        # Simulation d'évaluation
        # Dans un système réel, on exécuterait des tests de performance
        
        # Score de base
        score = 0.5
        
        # Impact des paramètres
        for key, value in params.items():
            if isinstance(value, (int, float)):
                score += value * 0.1
        
        # Bruit
        noise = np.random.normal(0, 0.05)
        score += noise
        
        return max(0, min(1, score))
    
    def _generate_grid(self, grid: Dict[str, List[Any]]) -> Generator:
        """Génère les combinaisons de la grille."""
        import itertools
        
        keys = list(grid.keys())
        values = list(grid.values())
        
        for combination in itertools.product(*values):
            yield {keys[i]: combination[i] for i in range(len(keys))}
    
    # ========== MÉTHODES PRIVÉES - MÉTRIQUES ==========
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques système."""
        while self._is_running:
            await asyncio.sleep(self.config["metrics_interval"])
            
            try:
                # Collecte des métriques
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                net = psutil.net_io_counters()
                process = psutil.Process()
                
                metrics = SystemMetrics(
                    cpu_percent=cpu_percent,
                    cpu_count=psutil.cpu_count(),
                    memory_percent=memory.percent,
                    memory_available=memory.available / (1024 ** 2),
                    memory_used=memory.used / (1024 ** 2),
                    disk_percent=disk.percent,
                    disk_used=disk.used / (1024 ** 3),
                    disk_free=disk.free / (1024 ** 3),
                    network_sent=net.bytes_sent / (1024 ** 2),
                    network_recv=net.bytes_recv / (1024 ** 2),
                    process_cpu=process.cpu_percent(),
                    process_memory=process.memory_info().rss / (1024 ** 2),
                    thread_count=process.num_threads(),
                    open_files=process.num_fds() if hasattr(process, 'num_fds') else 0
                )
                
                with self._metrics_lock:
                    self._metrics.append(metrics)
                    
                    # Limitation
                    if len(self._metrics) > 1000:
                        self._metrics = self._metrics[-1000:]
                
                # Mise à jour des statistiques
                self._stats["system_cpu_avg"] = (
                    self._stats["system_cpu_avg"] * 0.9 + cpu_percent * 0.1
                )
                self._stats["system_memory_avg"] = (
                    self._stats["system_memory_avg"] * 0.9 + memory.percent * 0.1
                )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _optimization_processor(self) -> None:
        """Traite les jobs d'optimisation."""
        while self._is_running:
            try:
                job = await self._optimization_queue.get()
                asyncio.create_task(self.run_job(job.job_id))
                
            except Exception as e:
                logger.error(f"Optimization processor error: {e}")
                await asyncio.sleep(1)
    
    async def _auto_optimization_loop(self) -> None:
        """Boucle d'optimisation automatique."""
        if not self.config["enable_auto_optimization"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["auto_optimization_interval"])
            
            try:
                # Analyse des métriques
                with self._metrics_lock:
                    if self._metrics:
                        recent = self._metrics[-10:]
                        avg_cpu = np.mean([m.cpu_percent for m in recent])
                        avg_memory = np.mean([m.memory_percent for m in recent])
                
                # Création d'un job d'optimisation
                if avg_cpu > self.config["cpu_limit_percent"]:
                    job = await self.create_job({
                        "name": "CPU Optimization",
                        "target": OptimizationTarget.CPU,
                        "parameters": {"cpu_limit": {"min": 20, "max": 90}},
                        "metadata": {"trigger": "auto"}
                    })
                    await self._optimization_queue.put(job)
                
                if avg_memory > self.config["memory_limit_mb"] / 4096 * 100:
                    job = await self.create_job({
                        "name": "Memory Optimization",
                        "target": OptimizationTarget.MEMORY,
                        "parameters": {"memory_limit": {"min": 1024, "max": 8192}},
                        "metadata": {"trigger": "auto"}
                    })
                    await self._optimization_queue.put(job)
                
            except Exception as e:
                logger.error(f"Auto-optimization loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._optimized_params) > self.config["cache_size"]:
                        keys = list(self._optimized_params.keys())
                        for key in keys[:len(self._optimized_params) - self.config["cache_size"]]:
                            del self._optimized_params[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la queue d'optimisation."""
        while not self._optimization_queue.empty():
            try:
                job = await self._optimization_queue.get()
                job.status = OptimizationStatus.CANCELLED
                job.end_time = datetime.now(timezone.utc)
            except Exception:
                break
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_job(self, job_id: str) -> Optional[OptimizationJob]:
        """Récupère un job."""
        with self._jobs_lock:
            return self._jobs.get(job_id)
    
    async def get_jobs(self, status: Optional[OptimizationStatus] = None) -> List[OptimizationJob]:
        """Récupère les jobs."""
        with self._jobs_lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [j for j in jobs if j.status == status]
            return sorted(jobs, key=lambda j: j.start_time or j.created_at, reverse=True)
    
    async def get_result(self, result_id: str) -> Optional[OptimizationResult]:
        """Récupère un résultat."""
        with self._results_lock:
            return self._results.get(result_id)
    
    async def get_results(self, job_id: str) -> List[OptimizationResult]:
        """Récupère les résultats d'un job."""
        with self._results_lock:
            return [r for r in self._results.values() if r.job_id == job_id]
    
    async def get_system_metrics(self, limit: int = 100) -> List[SystemMetrics]:
        """Récupère les métriques système."""
        with self._metrics_lock:
            return self._metrics[-limit:]
    
    async def get_optimized_param(self, key: str) -> Optional[Any]:
        """Récupère un paramètre optimisé."""
        with self._cache_lock:
            return self._optimized_params.get(key)
    
    async def get_optimized_params(self) -> Dict[str, Any]:
        """Récupère les paramètres optimisés."""
        with self._cache_lock:
            return self._optimized_params.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._jobs_lock:
            self._stats["total_jobs"] = len(self._jobs)
        with self._results_lock:
            self._stats["total_results"] = len(self._results)
        
        return self._stats.copy()


# ============== SYSTEM OPTIMIZATION UTILITIES ==============

class SystemOptimizationUtils:
    """Utilitaires d'optimisation système."""
    
    @staticmethod
    def optimize_memory_usage() -> Dict[str, Any]:
        """Optimise l'utilisation mémoire."""
        result = {
            "gc_collected": 0,
            "memory_freed_mb": 0
        }
        
        # Garbage collection
        collected = gc.collect()
        result["gc_collected"] = collected
        
        # Libération de mémoire
        if hasattr(gc, "get_stats"):
            stats = gc.get_stats()
            result["gc_stats"] = stats
        
        # Mise à jour des limites
        try:
            resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        except:
            pass
        
        return result
    
    @staticmethod
    def optimize_cpu_usage() -> Dict[str, Any]:
        """Optimise l'utilisation CPU."""
        result = {
            "priority_adjusted": False,
            "affinity_set": False
        }
        
        # Ajustement de la priorité
        try:
            os.nice(0)
            result["priority_adjusted"] = True
        except:
            pass
        
        # Définition de l'affinité CPU
        try:
            cpu_count = psutil.cpu_count()
            if cpu_count > 1:
                psutil.Process().cpu_affinity(list(range(cpu_count)))
                result["affinity_set"] = True
        except:
            pass
        
        return result
    
    @staticmethod
    def optimize_threading() -> Dict[str, Any]:
        """Optimise le threading."""
        result = {
            "thread_pool_size": os.cpu_count() * 2,
            "recommendation": ""
        }
        
        # Recommandation de taille de pool
        cpu_count = os.cpu_count() or 4
        if cpu_count < 4:
            result["recommendation"] = "Consider reducing thread pool size"
        elif cpu_count > 8:
            result["recommendation"] = "Consider increasing thread pool size"
        
        return result


# ============== FACTORY ==============

class OptimizerFactory:
    """Factory pour créer des composants d'optimisation."""
    
    @staticmethod
    async def create_optimizer(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SystemOptimizer:
        """Crée un optimiseur système."""
        optimizer = SystemOptimizer(
            data_manager=data_manager,
            config=config
        )
        await optimizer.start()
        return optimizer


# ============== EXPORT ==============

__all__ = [
    "OptimizationTarget",
    "OptimizationMethod",
    "OptimizationStatus",
    "OptimizationJob",
    "SystemMetrics",
    "OptimizationResult",
    "OptimizerInterface",
    "SystemOptimizer",
    "SystemOptimizationUtils",
    "OptimizerFactory"
]

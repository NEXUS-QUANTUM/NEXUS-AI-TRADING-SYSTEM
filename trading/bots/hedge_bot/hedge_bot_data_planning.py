# trading/bots/hedge_bot/hedge_bot_data_planning.py
# Advanced Data Planning & Strategy Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Planning Module - Module avancé de planification des données et de gestion des stratégies
pour le Hedge Bot. Gère la planification stratégique, l'analyse des besoins en données,
l'optimisation des ressources, et la roadmap des données pour le système de hedging.
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
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import pickle
import zlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_planning")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class PlanningHorizon(Enum):
    """Horizons de planification."""
    SHORT_TERM = "short_term"          # 0-3 mois
    MEDIUM_TERM = "medium_term"        # 3-12 mois
    LONG_TERM = "long_term"            # 1-3 ans
    STRATEGIC = "strategic"            # 3-5 ans


class PlanningPriority(Enum):
    """Priorités de planification."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    NICE_TO_HAVE = 4


class DataRequirementType(Enum):
    """Types de besoins en données."""
    REAL_TIME = "real_time"
    HISTORICAL = "historical"
    BATCH = "batch"
    STREAMING = "streaming"
    AGGREGATED = "aggregated"
    RAW = "raw"
    DERIVED = "derived"


# ============== DATA MODELS ==============

@dataclass
class DataPlan:
    """Plan de données."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    horizon: PlanningHorizon = PlanningHorizon.MEDIUM_TERM
    priority: PlanningPriority = PlanningPriority.MEDIUM
    objectives: List[str] = field(default_factory=list)
    requirements: List[Dict[str, Any]] = field(default_factory=list)
    resources: Dict[str, Any] = field(default_factory=dict)
    timeline: Dict[str, Any] = field(default_factory=dict)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    status: str = "draft"  # draft, active, in_progress, completed, cancelled
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    owner: str = ""
    stakeholders: List[str] = field(default_factory=list)


@dataclass
class DataRequirement:
    """Besoins en données."""
    requirement_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    name: str = ""
    description: str = ""
    requirement_type: DataRequirementType = DataRequirementType.REAL_TIME
    data_types: List[DataType] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    frequency: str = ""
    volume_estimate: float = 0.0
    latency_requirement: float = 0.0
    retention_days: int = 0
    priority: PlanningPriority = PlanningPriority.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending, approved, rejected, implemented


@dataclass
class DataRoadmap:
    """Roadmap des données."""
    roadmap_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    horizon: PlanningHorizon = PlanningHorizon.STRATEGIC
    phases: List[Dict[str, Any]] = field(default_factory=list)
    initiatives: List[Dict[str, Any]] = field(default_factory=list)
    timeline: Dict[str, Any] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)
    risks: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


# ============== INTERFACES ==============

class PlanningEngineInterface(ABC):
    """Interface abstraite pour le moteur de planification."""
    
    @abstractmethod
    async def create_plan(self, plan: DataPlan) -> str:
        """Crée un plan de données."""
        pass
    
    @abstractmethod
    async def create_requirement(self, requirement: DataRequirement) -> str:
        """Crée un besoin en données."""
        pass
    
    @abstractmethod
    async def create_roadmap(self, roadmap: DataRoadmap) -> str:
        """Crée une roadmap des données."""
        pass
    
    @abstractmethod
    async def get_plan(self, plan_id: str) -> Optional[DataPlan]:
        """Récupère un plan de données."""
        pass


# ============== IMPLÉMENTATION ==============

class PlanningEngine(PlanningEngineInterface):
    """
    Moteur de planification avancé pour le Hedge Bot.
    Gère la planification stratégique, les besoins en données et les roadmaps.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des plans
        self._plans: Dict[str, DataPlan] = {}
        self._plans_lock = threading.RLock()
        
        # Gestion des besoins
        self._requirements: Dict[str, DataRequirement] = {}
        self._req_lock = threading.RLock()
        
        # Gestion des roadmaps
        self._roadmaps: Dict[str, DataRoadmap] = {}
        self._roadmap_lock = threading.RLock()
        
        # Cache des analyses
        self._analysis_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "plans_created": 0,
            "requirements_created": 0,
            "roadmaps_created": 0,
            "plans_completed": 0,
            "requirements_implemented": 0,
            "avg_plan_duration_days": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PlanningEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_horizon": PlanningHorizon.MEDIUM_TERM,
            "default_priority": PlanningPriority.MEDIUM,
            "plan_review_interval": 86400,
            "max_plans": 100,
            "max_requirements": 1000,
            "auto_archive_days": 365,
            "enable_analytics": True,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_caching": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur de planification."""
        logger.info("PlanningEngine starting...")
        self._is_running = True
        
        # Chargement des plans
        await self._load_plans()
        
        # Chargement des besoins
        await self._load_requirements()
        
        # Chargement des roadmaps
        await self._load_roadmaps()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._plan_review_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PlanningEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de planification."""
        logger.info("PlanningEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("PlanningEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_plan(self, plan: DataPlan) -> str:
        """Crée un plan de données."""
        with self._plans_lock:
            self._plans[plan.plan_id] = plan
            self._stats["plans_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"planning:plan:{plan.plan_id}",
                plan.to_dict(),
                DataType.PLAN
            )
        
        logger.info(f"Data plan created: {plan.name} (id={plan.plan_id})")
        return plan.plan_id
    
    async def create_requirement(self, requirement: DataRequirement) -> str:
        """Crée un besoin en données."""
        with self._req_lock:
            self._requirements[requirement.requirement_id] = requirement
            self._stats["requirements_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"planning:requirement:{requirement.requirement_id}",
                requirement.to_dict(),
                DataType.REQUIREMENT
            )
        
        logger.info(f"Data requirement created: {requirement.name}")
        return requirement.requirement_id
    
    async def create_roadmap(self, roadmap: DataRoadmap) -> str:
        """Crée une roadmap des données."""
        with self._roadmap_lock:
            self._roadmaps[roadmap.roadmap_id] = roadmap
            self._stats["roadmaps_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"planning:roadmap:{roadmap.roadmap_id}",
                roadmap.to_dict(),
                DataType.ROADMAP
            )
        
        logger.info(f"Data roadmap created: {roadmap.name}")
        return roadmap.roadmap_id
    
    async def get_plan(self, plan_id: str) -> Optional[DataPlan]:
        """Récupère un plan de données."""
        with self._plans_lock:
            return self._plans.get(plan_id)
    
    # ========== MÉTHODES PRIVÉES - ANALYSE ==========
    
    async def _analyze_requirements(self, plan_id: str) -> Dict[str, Any]:
        """Analyse les besoins d'un plan."""
        requirements = await self.get_requirements(plan_id)
        
        analysis = {
            "total_requirements": len(requirements),
            "by_type": defaultdict(int),
            "by_priority": defaultdict(int),
            "by_status": defaultdict(int),
            "volume_total": 0.0,
            "latency_avg": 0.0,
            "retention_avg": 0.0,
            "implemented": 0,
            "pending": 0,
            "approved": 0,
            "rejected": 0
        }
        
        for req in requirements:
            analysis["by_type"][req.requirement_type.value] += 1
            analysis["by_priority"][req.priority.value] += 1
            analysis["by_status"][req.status] += 1
            
            analysis["volume_total"] += req.volume_estimate
            analysis["latency_avg"] += req.latency_requirement
            analysis["retention_avg"] += req.retention_days
            
            if req.status == "implemented":
                analysis["implemented"] += 1
            elif req.status == "pending":
                analysis["pending"] += 1
            elif req.status == "approved":
                analysis["approved"] += 1
            elif req.status == "rejected":
                analysis["rejected"] += 1
        
        if requirements:
            analysis["latency_avg"] /= len(requirements)
            analysis["retention_avg"] /= len(requirements)
        
        return analysis
    
    async def _generate_recommendations(self, plan: DataPlan) -> List[str]:
        """Génère des recommandations pour un plan."""
        recommendations = []
        
        # Analyse des besoins
        requirements = await self.get_requirements(plan.plan_id)
        
        if not requirements:
            recommendations.append("No requirements defined. Consider adding data requirements.")
        
        # Vérification des priorités
        high_priority = [r for r in requirements if r.priority == PlanningPriority.CRITICAL]
        if high_priority and not any(r.status == "implemented" for r in high_priority):
            recommendations.append("Critical requirements not implemented. Prioritize implementation.")
        
        # Vérification des volumes
        total_volume = sum(r.volume_estimate for r in requirements)
        if total_volume > 1000000:
            recommendations.append("High data volume detected. Consider scalability planning.")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _plan_review_loop(self) -> None:
        """Boucle de révision des plans."""
        while self._is_running:
            await asyncio.sleep(self.config["plan_review_interval"])
            
            try:
                with self._plans_lock:
                    for plan in self._plans.values():
                        if plan.status == "active":
                            # Révision du plan
                            recommendations = await self._generate_recommendations(plan)
                            if recommendations:
                                logger.info(f"Plan {plan.name} recommendations: {recommendations}")
                        
                        # Vérification de l'archivage
                        if plan.status in ["completed", "cancelled"]:
                            age = (datetime.now(timezone.utc) - plan.updated_at).days
                            if age > self.config["auto_archive_days"]:
                                plan.status = "archived"
                
            except Exception as e:
                logger.error(f"Plan review loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._analysis_cache) > self.config["cache_size"]:
                        keys = list(self._analysis_cache.keys())
                        for key in keys[:len(self._analysis_cache) - self.config["cache_size"]]:
                            del self._analysis_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._plans_lock:
                    self._stats["total_plans"] = len(self._plans)
                    active_plans = len([p for p in self._plans.values() if p.status == "active"])
                    self._stats["active_plans"] = active_plans
                
                with self._req_lock:
                    self._stats["total_requirements"] = len(self._requirements)
                    implemented = len([r for r in self._requirements.values() if r.status == "implemented"])
                    self._stats["requirements_implemented"] = implemented
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "planning:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_plans(self) -> None:
        """Charge les plans existants."""
        try:
            if self.data_manager:
                plans_data = await self.data_manager.retrieve(
                    "planning:plans",
                    DataType.PLAN
                )
                
                if plans_data:
                    for p_dict in plans_data:
                        plan = self._deserialize_plan(p_dict)
                        if plan:
                            with self._plans_lock:
                                self._plans[plan.plan_id] = plan
            
            logger.info(f"Loaded {len(self._plans)} data plans")
            
        except Exception as e:
            logger.error(f"Load plans error: {e}")
    
    async def _load_requirements(self) -> None:
        """Charge les besoins existants."""
        try:
            if self.data_manager:
                req_data = await self.data_manager.retrieve(
                    "planning:requirements",
                    DataType.REQUIREMENT
                )
                
                if req_data:
                    for r_dict in req_data:
                        requirement = self._deserialize_requirement(r_dict)
                        if requirement:
                            with self._req_lock:
                                self._requirements[requirement.requirement_id] = requirement
            
            logger.info(f"Loaded {len(self._requirements)} requirements")
            
        except Exception as e:
            logger.error(f"Load requirements error: {e}")
    
    async def _load_roadmaps(self) -> None:
        """Charge les roadmaps existantes."""
        try:
            if self.data_manager:
                roadmap_data = await self.data_manager.retrieve(
                    "planning:roadmaps",
                    DataType.ROADMAP
                )
                
                if roadmap_data:
                    for r_dict in roadmap_data:
                        roadmap = self._deserialize_roadmap(r_dict)
                        if roadmap:
                            with self._roadmap_lock:
                                self._roadmaps[roadmap.roadmap_id] = roadmap
            
            logger.info(f"Loaded {len(self._roadmaps)} roadmaps")
            
        except Exception as e:
            logger.error(f"Load roadmaps error: {e}")
    
    def _deserialize_plan(self, data: Dict) -> Optional[DataPlan]:
        """Désérialise un plan."""
        try:
            return DataPlan(
                plan_id=data.get("plan_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                description=data.get("description", ""),
                horizon=PlanningHorizon(data.get("horizon", "medium_term")),
                priority=PlanningPriority(data.get("priority", "medium")),
                objectives=data.get("objectives", []),
                requirements=data.get("requirements", []),
                resources=data.get("resources", {}),
                timeline=data.get("timeline", {}),
                milestones=data.get("milestones", []),
                risks=data.get("risks", []),
                dependencies=data.get("dependencies", []),
                status=data.get("status", "draft"),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                owner=data.get("owner", ""),
                stakeholders=data.get("stakeholders", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing plan: {e}")
            return None
    
    def _deserialize_requirement(self, data: Dict) -> Optional[DataRequirement]:
        """Désérialise un besoin."""
        try:
            return DataRequirement(
                requirement_id=data.get("requirement_id", str(uuid.uuid4())),
                plan_id=data.get("plan_id", ""),
                name=data.get("name", ""),
                description=data.get("description", ""),
                requirement_type=DataRequirementType(data.get("requirement_type", "real_time")),
                data_types=[DataType(dt) for dt in data.get("data_types", [])],
                sources=data.get("sources", []),
                frequency=data.get("frequency", ""),
                volume_estimate=data.get("volume_estimate", 0.0),
                latency_requirement=data.get("latency_requirement", 0.0),
                retention_days=data.get("retention_days", 0),
                priority=PlanningPriority(data.get("priority", "medium")),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                status=data.get("status", "pending")
            )
        except Exception as e:
            logger.error(f"Error deserializing requirement: {e}")
            return None
    
    def _deserialize_roadmap(self, data: Dict) -> Optional[DataRoadmap]:
        """Désérialise une roadmap."""
        try:
            return DataRoadmap(
                roadmap_id=data.get("roadmap_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                description=data.get("description", ""),
                horizon=PlanningHorizon(data.get("horizon", "strategic")),
                phases=data.get("phases", []),
                initiatives=data.get("initiatives", []),
                timeline=data.get("timeline", {}),
                dependencies=data.get("dependencies", {}),
                resources=data.get("resources", {}),
                risks=data.get("risks", []),
                metrics=data.get("metrics", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing roadmap: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_plans(self, status: Optional[str] = None) -> List[DataPlan]:
        """Récupère les plans."""
        with self._plans_lock:
            plans = list(self._plans.values())
            if status:
                plans = [p for p in plans if p.status == status]
            return sorted(plans, key=lambda p: p.created_at, reverse=True)
    
    async def get_requirements(self, plan_id: str) -> List[DataRequirement]:
        """Récupère les besoins d'un plan."""
        with self._req_lock:
            return [r for r in self._requirements.values() if r.plan_id == plan_id]
    
    async def get_roadmap(self, roadmap_id: str) -> Optional[DataRoadmap]:
        """Récupère une roadmap."""
        with self._roadmap_lock:
            return self._roadmaps.get(roadmap_id)
    
    async def get_roadmaps(self) -> List[DataRoadmap]:
        """Récupère les roadmaps."""
        with self._roadmap_lock:
            return list(self._roadmaps.values())
    
    async def approve_requirement(self, requirement_id: str) -> bool:
        """Approuve un besoin."""
        with self._req_lock:
            requirement = self._requirements.get(requirement_id)
            if not requirement:
                return False
            
            requirement.status = "approved"
            requirement.updated_at = datetime.now(timezone.utc)
            return True
    
    async def implement_requirement(self, requirement_id: str) -> bool:
        """Marque un besoin comme implémenté."""
        with self._req_lock:
            requirement = self._requirements.get(requirement_id)
            if not requirement:
                return False
            
            requirement.status = "implemented"
            requirement.updated_at = datetime.now(timezone.utc)
            return True
    
    async def analyze_plan(self, plan_id: str) -> Dict[str, Any]:
        """Analyse un plan."""
        # Vérification du cache
        cache_key = f"plan_analysis_{plan_id}"
        with self._cache_lock:
            if cache_key in self._analysis_cache:
                return self._analysis_cache[cache_key]
        
        analysis = await self._analyze_requirements(plan_id)
        plan = await self.get_plan(plan_id)
        if plan:
            analysis["plan"] = plan.to_dict()
            analysis["recommendations"] = await self._generate_recommendations(plan)
        
        # Mise en cache
        with self._cache_lock:
            if len(self._analysis_cache) < self.config["cache_size"]:
                self._analysis_cache[cache_key] = analysis
        
        return analysis
    
    async def generate_plan_report(self, plan_id: str) -> Dict[str, Any]:
        """Génère un rapport pour un plan."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        
        requirements = await self.get_requirements(plan_id)
        analysis = await self.analyze_plan(plan_id)
        
        report = {
            "plan": plan.to_dict(),
            "summary": {
                "total_requirements": len(requirements),
                "implemented": len([r for r in requirements if r.status == "implemented"]),
                "pending": len([r for r in requirements if r.status == "pending"]),
                "approved": len([r for r in requirements if r.status == "approved"]),
                "rejected": len([r for r in requirements if r.status == "rejected"])
            },
            "analysis": analysis,
            "recommendations": await self._generate_recommendations(plan),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        return report
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._plans_lock:
            self._stats["total_plans"] = len(self._plans)
        with self._req_lock:
            self._stats["total_requirements"] = len(self._requirements)
        with self._roadmap_lock:
            self._stats["total_roadmaps"] = len(self._roadmaps)
        
        return self._stats.copy()


# ============== PLANNING STRATEGY BUILDER ==============

class PlanningStrategyBuilder:
    """
    Constructeur de stratégies de planification.
    Facilite la création de plans stratégiques.
    """
    
    def __init__(self):
        self._plan = DataPlan()
    
    def name(self, name: str) -> 'PlanningStrategyBuilder':
        """Définit le nom."""
        self._plan.name = name
        return self
    
    def description(self, description: str) -> 'PlanningStrategyBuilder':
        """Définit la description."""
        self._plan.description = description
        return self
    
    def horizon(self, horizon: PlanningHorizon) -> 'PlanningStrategyBuilder':
        """Définit l'horizon."""
        self._plan.horizon = horizon
        return self
    
    def priority(self, priority: PlanningPriority) -> 'PlanningStrategyBuilder':
        """Définit la priorité."""
        self._plan.priority = priority
        return self
    
    def objective(self, objective: str) -> 'PlanningStrategyBuilder':
        """Ajoute un objectif."""
        self._plan.objectives.append(objective)
        return self
    
    def requirement(self, requirement: Dict[str, Any]) -> 'PlanningStrategyBuilder':
        """Ajoute un besoin."""
        self._plan.requirements.append(requirement)
        return self
    
    def milestone(self, milestone: Dict[str, Any]) -> 'PlanningStrategyBuilder':
        """Ajoute un jalon."""
        self._plan.milestones.append(milestone)
        return self
    
    def risk(self, risk: Dict[str, Any]) -> 'PlanningStrategyBuilder':
        """Ajoute un risque."""
        self._plan.risks.append(risk)
        return self
    
    def build(self) -> DataPlan:
        """Construit le plan."""
        return self._plan


# ============== FACTORY ==============

class PlanningFactory:
    """Factory pour créer des composants de planification."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PlanningEngine:
        """Crée un moteur de planification."""
        engine = PlanningEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_strategy_builder() -> PlanningStrategyBuilder:
        """Crée un constructeur de stratégies."""
        return PlanningStrategyBuilder()


# ============== EXPORT ==============

__all__ = [
    "PlanningHorizon",
    "PlanningPriority",
    "DataRequirementType",
    "DataPlan",
    "DataRequirement",
    "DataRoadmap",
    "PlanningEngineInterface",
    "PlanningEngine",
    "PlanningStrategyBuilder",
    "PlanningFactory"
]

# trading/bots/hedge_bot/hedge_bot_scenario_manager.py
# Advanced Scenario Management & What-If Analysis Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Scenario Manager Module - Module avancé de gestion de scénarios et d'analyse what-if
pour le Hedge Bot. Permet la simulation de scénarios, l'analyse d'impact, la planification
stratégique, l'optimisation des décisions et la gestion des risques pour le hedging.
"""

import asyncio
import json
import math
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

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_scenario_manager")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType, HedgeStrategy
)


# ============== ENUMS & TYPES ==============

class ScenarioType(Enum):
    """Types de scénarios."""
    WHAT_IF = "what_if"                # Analyse what-if
    STRESS = "stress"                  # Test de stress
    MARKET = "market"                  # Scénario de marché
    STRATEGY = "strategy"              # Scénario de stratégie
    EXECUTION = "execution"            # Scénario d'exécution
    RISK = "risk"                      # Scénario de risque
    COMPLIANCE = "compliance"          # Scénario de conformité
    OPTIMIZATION = "optimization"      # Scénario d'optimisation
    DISASTER = "disaster"              # Scénario de catastrophe
    RECOVERY = "recovery"              # Scénario de récupération


class ScenarioStatus(Enum):
    """Statuts des scénarios."""
    DRAFT = "draft"
    ACTIVE = "active"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ScenarioPriority(Enum):
    """Priorités des scénarios."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class ScenarioOutcome(Enum):
    """Résultats de scénario."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"
    EXCEPTIONAL = "exceptional"


# ============== DATA MODELS ==============

@dataclass
class Scenario:
    """Modèle de scénario."""
    scenario_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    scenario_type: ScenarioType = ScenarioType.WHAT_IF
    priority: ScenarioPriority = ScenarioPriority.MEDIUM
    status: ScenarioStatus = ScenarioStatus.DRAFT
    parameters: Dict[str, Any] = field(default_factory=dict)
    assumptions: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: ScenarioOutcome = ScenarioOutcome.INCONCLUSIVE
    actual_outcome: Optional[ScenarioOutcome] = None
    risk_level: float = 0.5
    probability: float = 0.5
    impact_score: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    owner: str = ""
    stakeholders: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    lessons_learned: List[str] = field(default_factory=list)


@dataclass
class ScenarioExecution:
    """Exécution de scénario."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    status: ScenarioStatus = ScenarioStatus.RUNNING
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    parameters_used: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    outcome: ScenarioOutcome = ScenarioOutcome.INCONCLUSIVE
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioComparison:
    """Comparaison de scénarios."""
    comparison_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scenario_ids: List[str] = field(default_factory=list)
    metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    rankings: Dict[str, int] = field(default_factory=dict)
    best_scenario: Optional[str] = None
    worst_scenario: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioTemplate:
    """Template de scénario."""
    template_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    scenario_type: ScenarioType = ScenarioType.WHAT_IF
    default_parameters: Dict[str, Any] = field(default_factory=dict)
    assumptions: Dict[str, Any] = field(default_factory=dict)
    expected_metrics: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


# ============== INTERFACES ==============

class ScenarioManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de scénarios."""
    
    @abstractmethod
    async def create_scenario(self, config: Dict[str, Any]) -> Scenario:
        """Crée un scénario."""
        pass
    
    @abstractmethod
    async def execute_scenario(self, scenario_id: str) -> ScenarioExecution:
        """Exécute un scénario."""
        pass
    
    @abstractmethod
    async def compare_scenarios(self, scenario_ids: List[str]) -> ScenarioComparison:
        """Compare des scénarios."""
        pass


# ============== IMPLÉMENTATION ==============

class ScenarioManager(ScenarioManagerInterface):
    """
    Gestionnaire de scénarios avancé pour le Hedge Bot.
    Gère l'analyse what-if, la planification stratégique et l'optimisation des décisions.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des scénarios
        self._scenarios: Dict[str, Scenario] = {}
        self._scenarios_lock = threading.RLock()
        
        # Gestion des exécutions
        self._executions: Dict[str, ScenarioExecution] = {}
        self._executions_lock = threading.RLock()
        
        # Gestion des templates
        self._templates: Dict[str, ScenarioTemplate] = {}
        self._templates_lock = threading.RLock()
        
        # Gestion des comparaisons
        self._comparisons: Dict[str, ScenarioComparison] = {}
        self._comparisons_lock = threading.RLock()
        
        # Queue d'exécution
        self._execution_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "scenarios_created": 0,
            "scenarios_executed": 0,
            "comparisons_made": 0,
            "templates_created": 0,
            "avg_execution_time_ms": 0.0,
            "success_rate": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("ScenarioManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_priority": ScenarioPriority.MEDIUM,
            "default_scenario_type": ScenarioType.WHAT_IF,
            "execution_timeout": 3600,
            "max_concurrent_executions": 5,
            "auto_archive_days": 30,
            "default_risk_level": 0.5,
            "default_probability": 0.5,
            "impact_threshold": 0.3,
            "comparison_metrics": ["sharpe", "max_drawdown", "win_rate"],
            "enable_notifications": True,
            "enable_audit": True,
            "history_retention_days": 365
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire de scénarios."""
        logger.info("ScenarioManager starting...")
        self._is_running = True
        
        # Chargement des templates
        await self._load_templates()
        
        # Chargement des scénarios existants
        await self._load_scenarios()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._execution_processor())
        asyncio.create_task(self._archive_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("ScenarioManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de scénarios."""
        logger.info("ScenarioManager stopping...")
        self._is_running = False
        
        # Attente des exécutions en cours
        await self._drain_queue()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("ScenarioManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_scenario(self, config: Dict[str, Any]) -> Scenario:
        """Crée un scénario."""
        scenario = Scenario(
            name=config.get("name", f"Scenario_{uuid.uuid4().hex[:8]}"),
            description=config.get("description", ""),
            scenario_type=ScenarioType(config.get("scenario_type", "what_if")),
            priority=ScenarioPriority(config.get("priority", "medium")),
            parameters=config.get("parameters", {}),
            assumptions=config.get("assumptions", {}),
            risk_level=config.get("risk_level", 0.5),
            probability=config.get("probability", 0.5),
            owner=config.get("owner", "system"),
            stakeholders=config.get("stakeholders", []),
            tags=config.get("tags", []),
            metadata=config.get("metadata", {})
        )
        
        with self._scenarios_lock:
            self._scenarios[scenario.scenario_id] = scenario
            self._stats["scenarios_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"scenario:{scenario.scenario_id}",
                scenario.to_dict(),
                DataType.SCENARIO
            )
        
        logger.info(f"Scenario created: {scenario.name} (id={scenario.scenario_id})")
        return scenario
    
    async def execute_scenario(self, scenario_id: str) -> ScenarioExecution:
        """Exécute un scénario."""
        with self._scenarios_lock:
            scenario = self._scenarios.get(scenario_id)
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
            
            scenario.status = ScenarioStatus.RUNNING
            scenario.updated_at = datetime.now(timezone.utc)
        
        # Création de l'exécution
        execution = ScenarioExecution(
            scenario_id=scenario_id,
            parameters_used=scenario.parameters.copy()
        )
        
        with self._executions_lock:
            self._executions[execution.execution_id] = execution
        
        # Mise en queue
        await self._execution_queue.put((scenario_id, execution.execution_id))
        
        # Attente du résultat
        while execution.status == ScenarioStatus.RUNNING:
            await asyncio.sleep(0.1)
        
        return execution
    
    async def compare_scenarios(self, scenario_ids: List[str]) -> ScenarioComparison:
        """Compare des scénarios."""
        self._stats["comparisons_made"] += 1
        
        scenarios = []
        with self._scenarios_lock:
            for sid in scenario_ids:
                if sid in self._scenarios:
                    scenarios.append(self._scenarios[sid])
        
        if len(scenarios) < 2:
            raise ValueError("At least 2 scenarios required for comparison")
        
        # Extraction des métriques
        metrics = {}
        for scenario in scenarios:
            metrics[scenario.scenario_id] = scenario.metadata.get("metrics", {})
        
        # Calcul des rankings
        rankings = {}
        best_scenario = None
        worst_scenario = None
        
        for metric, values in metrics.items():
            # Classement par métrique
            sorted_ids = sorted(values.items(), key=lambda x: x[1], reverse=True)
            for i, (sid, _) in enumerate(sorted_ids):
                if sid not in rankings:
                    rankings[sid] = 0
                rankings[sid] += i
        
        # Meilleur et pire scénario
        if rankings:
            best_scenario = min(rankings, key=rankings.get)
            worst_scenario = max(rankings, key=rankings.get)
        
        # Génération des recommandations
        recommendations = await self._generate_comparison_recommendations(
            scenarios, metrics, rankings
        )
        
        # Création de la comparaison
        comparison = ScenarioComparison(
            scenario_ids=scenario_ids,
            metrics=metrics,
            rankings=rankings,
            best_scenario=best_scenario,
            worst_scenario=worst_scenario,
            recommendations=recommendations
        )
        
        with self._comparisons_lock:
            self._comparisons[comparison.comparison_id] = comparison
        
        logger.info(f"Scenario comparison completed: {len(scenarios)} scenarios")
        return comparison
    
    # ========== MÉTHODES PRIVÉES - EXÉCUTION ==========
    
    async def _execution_processor(self) -> None:
        """Traite les exécutions de scénarios."""
        while self._is_running:
            try:
                scenario_id, execution_id = await self._execution_queue.get()
                
                # Exécution du scénario
                asyncio.create_task(self._run_scenario(scenario_id, execution_id))
                
            except Exception as e:
                logger.error(f"Execution processor error: {e}")
                await asyncio.sleep(1)
    
    async def _run_scenario(self, scenario_id: str, execution_id: str) -> None:
        """Exécute un scénario spécifique."""
        with self._executions_lock:
            execution = self._executions.get(execution_id)
            if not execution:
                return
        
        try:
            start_time = time.time()
            
            # Récupération du scénario
            with self._scenarios_lock:
                scenario = self._scenarios.get(scenario_id)
                if not scenario:
                    raise ValueError(f"Scenario {scenario_id} not found")
            
            # Simulation du scénario
            result = await self._simulate_scenario(scenario)
            
            # Mise à jour de l'exécution
            execution.end_time = datetime.now(timezone.utc)
            execution.duration_ms = (time.time() - start_time) * 1000
            execution.metrics = result["metrics"]
            execution.outcome = result["outcome"]
            execution.status = ScenarioStatus.COMPLETED
            
            # Mise à jour du scénario
            scenario.status = ScenarioStatus.COMPLETED
            scenario.executed_at = execution.start_time
            scenario.completed_at = execution.end_time
            scenario.actual_outcome = result["outcome"]
            scenario.results = result
            scenario.impact_score = self._calculate_impact_score(result)
            
            self._stats["scenarios_executed"] += 1
            self._stats["avg_execution_time_ms"] = (
                self._stats["avg_execution_time_ms"] * 0.9 + execution.duration_ms * 0.1
            )
            
            logger.info(f"Scenario executed: {scenario.name} outcome={execution.outcome.value}")
            
        except Exception as e:
            execution.status = ScenarioStatus.FAILED
            execution.error = str(e)
            execution.end_time = datetime.now(timezone.utc)
            execution.duration_ms = (time.time() - start_time) * 1000
            
            logger.error(f"Scenario execution failed: {e}")
    
    async def _simulate_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        """Simule un scénario."""
        # Simulation basée sur le type de scénario
        if scenario.scenario_type == ScenarioType.STRESS:
            return await self._simulate_stress_scenario(scenario)
        elif scenario.scenario_type == ScenarioType.MARKET:
            return await self._simulate_market_scenario(scenario)
        elif scenario.scenario_type == ScenarioType.STRATEGY:
            return await self._simulate_strategy_scenario(scenario)
        elif scenario.scenario_type == ScenarioType.RISK:
            return await self._simulate_risk_scenario(scenario)
        else:
            return await self._simulate_generic_scenario(scenario)
    
    async def _simulate_stress_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        """Simule un scénario de stress."""
        # Paramètres de stress
        stress_level = scenario.parameters.get("stress_level", 0.5)
        duration = scenario.parameters.get("duration", 30)
        
        # Simulation
        metrics = {
            "sharpe": 0.5 - stress_level * 0.5,
            "max_drawdown": 0.1 + stress_level * 0.3,
            "volatility": 0.2 + stress_level * 0.4,
            "var": 0.05 + stress_level * 0.1,
            "expected_shortfall": 0.08 + stress_level * 0.15
        }
        
        outcome = ScenarioOutcome.SUCCESS if stress_level < 0.7 else ScenarioOutcome.FAILURE
        
        return {
            "metrics": metrics,
            "outcome": outcome,
            "stress_level": stress_level,
            "duration": duration,
            "passed_stress_test": stress_level < 0.7
        }
    
    async def _simulate_market_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        """Simule un scénario de marché."""
        # Paramètres de marché
        volatility = scenario.parameters.get("volatility", 0.2)
        trend = scenario.parameters.get("trend", 0.0)
        liquidity = scenario.parameters.get("liquidity", 0.8)
        
        # Simulation
        metrics = {
            "sharpe": 0.5 + trend * 0.3 - volatility * 0.2,
            "max_drawdown": 0.1 + volatility * 0.2 - liquidity * 0.05,
            "win_rate": 0.5 + trend * 0.2,
            "profit_factor": 1.0 + trend * 0.5
        }
        
        outcome = ScenarioOutcome.SUCCESS if metrics["sharpe"] > 0 else ScenarioOutcome.FAILURE
        
        return {
            "metrics": metrics,
            "outcome": outcome,
            "volatility": volatility,
            "trend": trend,
            "liquidity": liquidity
        }
    
    async def _simulate_strategy_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        """Simule un scénario de stratégie."""
        # Paramètres de stratégie
        aggressiveness = scenario.parameters.get("aggressiveness", 0.5)
        risk_tolerance = scenario.parameters.get("risk_tolerance", 0.5)
        hedge_ratio = scenario.parameters.get("hedge_ratio", 0.5)
        
        # Simulation
        metrics = {
            "sharpe": 0.3 + aggressiveness * 0.4 - risk_tolerance * 0.1,
            "max_drawdown": 0.05 + risk_tolerance * 0.2,
            "win_rate": 0.4 + aggressiveness * 0.3,
            "hedge_effectiveness": hedge_ratio * (1 - risk_tolerance * 0.2)
        }
        
        outcome = ScenarioOutcome.SUCCESS if metrics["sharpe"] > 0.2 else ScenarioOutcome.FAILURE
        
        return {
            "metrics": metrics,
            "outcome": outcome,
            "aggressiveness": aggressiveness,
            "risk_tolerance": risk_tolerance,
            "hedge_ratio": hedge_ratio
        }
    
    async def _simulate_risk_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        """Simule un scénario de risque."""
        # Paramètres de risque
        var = scenario.parameters.get("var", 0.05)
        drawdown = scenario.parameters.get("drawdown", 0.1)
        correlation_break = scenario.parameters.get("correlation_break", False)
        
        # Simulation
        metrics = {
            "var_breach": 1.0 if var > 0.08 else 0.0,
            "drawdown_breach": 1.0 if drawdown > 0.15 else 0.0,
            "risk_score": var * 2 + drawdown * 1.5,
            "correlation_stability": 0.5 if correlation_break else 0.9
        }
        
        outcome = ScenarioOutcome.SUCCESS if metrics["risk_score"] < 0.3 else ScenarioOutcome.FAILURE
        
        return {
            "metrics": metrics,
            "outcome": outcome,
            "var": var,
            "drawdown": drawdown,
            "correlation_break": correlation_break
        }
    
    async def _simulate_generic_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        """Simule un scénario générique."""
        # Simulation de base
        base_value = scenario.parameters.get("base_value", 100)
        volatility = scenario.parameters.get("volatility", 0.1)
        
        # Simulation Monte Carlo simplifiée
        np.random.seed(hash(scenario.scenario_id) % 2**32)
        returns = np.random.normal(0, volatility, 252)
        path = base_value * np.exp(np.cumsum(returns))
        
        metrics = {
            "final_value": path[-1],
            "max_value": np.max(path),
            "min_value": np.min(path),
            "volatility": np.std(returns),
            "sharpe": np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
        }
        
        outcome = ScenarioOutcome.SUCCESS if metrics["final_value"] > base_value else ScenarioOutcome.FAILURE
        
        return {
            "metrics": metrics,
            "outcome": outcome,
            "path": path.tolist(),
            "base_value": base_value
        }
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _calculate_impact_score(self, result: Dict[str, Any]) -> float:
        """Calcule un score d'impact."""
        metrics = result.get("metrics", {})
        
        # Score basé sur plusieurs métriques
        scores = []
        
        if "sharpe" in metrics:
            scores.append(max(0, min(1, (metrics["sharpe"] + 1) / 2)))
        
        if "max_drawdown" in metrics:
            scores.append(1 - min(1, metrics["max_drawdown"] * 2))
        
        if "win_rate" in metrics:
            scores.append(metrics["win_rate"])
        
        if scores:
            return np.mean(scores)
        return 0.5
    
    async def _generate_comparison_recommendations(
        self,
        scenarios: List[Scenario],
        metrics: Dict[str, Dict[str, float]],
        rankings: Dict[str, int]
    ) -> List[str]:
        """Génère des recommandations à partir de la comparaison."""
        recommendations = []
        
        if not rankings:
            return ["No recommendations available"]
        
        # Meilleur scénario
        best_id = min(rankings, key=rankings.get)
        best_scenario = next((s for s in scenarios if s.scenario_id == best_id), None)
        
        if best_scenario:
            recommendations.append(f"Consider adopting scenario '{best_scenario.name}' as it outperforms others")
        
        # Améliorations possibles
        for scenario in scenarios:
            if scenario.scenario_id != best_id:
                metrics_data = metrics.get(scenario.scenario_id, {})
                best_metrics = metrics.get(best_id, {})
                
                for metric, value in metrics_data.items():
                    if metric in best_metrics and value < best_metrics[metric]:
                        recommendations.append(
                            f"Improve {metric} in scenario '{scenario.name}' "
                            f"(current: {value:.2f}, best: {best_metrics[metric]:.2f})"
                        )
        
        # Recommandations générales
        avg_risk = np.mean([s.risk_level for s in scenarios])
        if avg_risk > 0.6:
            recommendations.append("Consider reducing risk exposure across all scenarios")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _archive_loop(self) -> None:
        """Archive les scénarios anciens."""
        while self._is_running:
            await asyncio.sleep(86400)  # 1 jour
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["auto_archive_days"])
                
                with self._scenarios_lock:
                    to_archive = [
                        sid for sid, scenario in self._scenarios.items()
                        if scenario.status in [ScenarioStatus.COMPLETED, ScenarioStatus.FAILED]
                        and scenario.completed_at and scenario.completed_at < cutoff
                    ]
                    
                    for sid in to_archive:
                        self._scenarios[sid].status = ScenarioStatus.ARCHIVED
                        
                if to_archive:
                    logger.info(f"Archived {len(to_archive)} scenarios")
                
            except Exception as e:
                logger.error(f"Archive loop error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la queue d'exécution."""
        while not self._execution_queue.empty():
            try:
                scenario_id, execution_id = await self._execution_queue.get()
                with self._executions_lock:
                    if execution_id in self._executions:
                        self._executions[execution_id].status = ScenarioStatus.CANCELLED
            except Exception:
                break
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._scenarios_lock:
                    self._stats["total_scenarios"] = len(self._scenarios)
                    active = len([s for s in self._scenarios.values() if s.status == ScenarioStatus.ACTIVE])
                    self._stats["active_scenarios"] = active
                
                with self._executions_lock:
                    self._stats["total_executions"] = len(self._executions)
                
                # Calcul du taux de succès
                if self._stats["scenarios_executed"] > 0:
                    self._stats["success_rate"] = (
                        self._stats["scenarios_executed"] / self._stats["scenarios_created"]
                    )
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "scenario:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_templates(self) -> None:
        """Charge les templates de scénarios."""
        # Templates par défaut
        default_templates = [
            ScenarioTemplate(
                name="Market Crash",
                description="Scenario simulating a major market crash",
                scenario_type=ScenarioType.STRESS,
                default_parameters={
                    "stress_level": 0.8,
                    "duration": 30,
                    "volatility": 0.5
                },
                expected_metrics=["sharpe", "max_drawdown", "var"],
                recommended_actions=[
                    "Increase hedge ratio",
                    "Reduce position sizes",
                    "Increase cash allocation"
                ]
            ),
            ScenarioTemplate(
                name="Bull Market",
                description="Scenario simulating a strong bull market",
                scenario_type=ScenarioType.MARKET,
                default_parameters={
                    "volatility": 0.15,
                    "trend": 0.3,
                    "liquidity": 0.9
                },
                expected_metrics=["sharpe", "win_rate", "profit_factor"],
                recommended_actions=[
                    "Increase exposure to high-beta assets",
                    "Consider momentum strategies",
                    "Reduce hedging"
                ]
            ),
            ScenarioTemplate(
                name="Volatility Spike",
                description="Scenario simulating a volatility spike",
                scenario_type=ScenarioType.RISK,
                default_parameters={
                    "var": 0.1,
                    "drawdown": 0.15,
                    "correlation_break": True
                },
                expected_metrics=["var_breach", "drawdown_breach", "risk_score"],
                recommended_actions=[
                    "Implement volatility targeting",
                    "Use options for tail risk hedging",
                    "Diversify across uncorrelated assets"
                ]
            )
        ]
        
        for template in default_templates:
            with self._templates_lock:
                self._templates[template.template_id] = template
                self._stats["templates_created"] += 1
        
        logger.info(f"Loaded {len(default_templates)} scenario templates")
    
    async def _load_scenarios(self) -> None:
        """Charge les scénarios existants."""
        try:
            if self.data_manager:
                scenarios_data = await self.data_manager.retrieve(
                    "scenarios:all",
                    DataType.SCENARIO
                )
                
                if scenarios_data:
                    for scenario_dict in scenarios_data:
                        scenario = self._deserialize_scenario(scenario_dict)
                        if scenario:
                            with self._scenarios_lock:
                                self._scenarios[scenario.scenario_id] = scenario
            
            logger.info(f"Loaded {len(self._scenarios)} scenarios")
            
        except Exception as e:
            logger.error(f"Load scenarios error: {e}")
    
    def _deserialize_scenario(self, data: Dict) -> Optional[Scenario]:
        """Désérialise un scénario."""
        try:
            return Scenario(
                scenario_id=data.get("scenario_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                description=data.get("description", ""),
                scenario_type=ScenarioType(data.get("scenario_type", "what_if")),
                priority=ScenarioPriority(data.get("priority", "medium")),
                status=ScenarioStatus(data.get("status", "draft")),
                parameters=data.get("parameters", {}),
                assumptions=data.get("assumptions", {}),
                expected_outcome=ScenarioOutcome(data.get("expected_outcome", "inconclusive")),
                actual_outcome=ScenarioOutcome(data.get("actual_outcome")) if data.get("actual_outcome") else None,
                risk_level=data.get("risk_level", 0.5),
                probability=data.get("probability", 0.5),
                impact_score=data.get("impact_score", 0.0),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                executed_at=datetime.fromisoformat(data.get("executed_at")) if data.get("executed_at") else None,
                completed_at=datetime.fromisoformat(data.get("completed_at")) if data.get("completed_at") else None,
                owner=data.get("owner", ""),
                stakeholders=data.get("stakeholders", []),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
                results=data.get("results", {}),
                lessons_learned=data.get("lessons_learned", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing scenario: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """Récupère un scénario."""
        with self._scenarios_lock:
            return self._scenarios.get(scenario_id)
    
    async def get_scenarios(self, status: Optional[ScenarioStatus] = None) -> List[Scenario]:
        """Récupère les scénarios."""
        with self._scenarios_lock:
            scenarios = list(self._scenarios.values())
            if status:
                scenarios = [s for s in scenarios if s.status == status]
            return sorted(scenarios, key=lambda s: s.created_at, reverse=True)
    
    async def get_execution(self, execution_id: str) -> Optional[ScenarioExecution]:
        """Récupère une exécution."""
        with self._executions_lock:
            return self._executions.get(execution_id)
    
    async def get_executions(self, scenario_id: str) -> List[ScenarioExecution]:
        """Récupère les exécutions d'un scénario."""
        with self._executions_lock:
            return [e for e in self._executions.values() if e.scenario_id == scenario_id]
    
    async def get_template(self, template_id: str) -> Optional[ScenarioTemplate]:
        """Récupère un template."""
        with self._templates_lock:
            return self._templates.get(template_id)
    
    async def get_templates(self) -> List[ScenarioTemplate]:
        """Récupère les templates."""
        with self._templates_lock:
            return list(self._templates.values())
    
    async def create_from_template(self, template_id: str, customizations: Dict[str, Any]) -> Scenario:
        """Crée un scénario à partir d'un template."""
        template = await self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Fusion des paramètres
        parameters = template.default_parameters.copy()
        parameters.update(customizations.get("parameters", {}))
        
        # Création du scénario
        config = {
            "name": customizations.get("name", f"From {template.name}"),
            "description": customizations.get("description", template.description),
            "scenario_type": template.scenario_type.value,
            "parameters": parameters,
            "assumptions": template.assumptions.copy(),
            "tags": template.tags.copy()
        }
        
        return await self.create_scenario(config)
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Annule une exécution."""
        with self._executions_lock:
            execution = self._executions.get(execution_id)
            if not execution or execution.status != ScenarioStatus.RUNNING:
                return False
            
            execution.status = ScenarioStatus.CANCELLED
            execution.end_time = datetime.now(timezone.utc)
            return True
    
    async def update_scenario_status(self, scenario_id: str, status: ScenarioStatus) -> bool:
        """Met à jour le statut d'un scénario."""
        with self._scenarios_lock:
            scenario = self._scenarios.get(scenario_id)
            if not scenario:
                return False
            
            scenario.status = status
            scenario.updated_at = datetime.now(timezone.utc)
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._scenarios_lock:
            self._stats["total_scenarios"] = len(self._scenarios)
        with self._executions_lock:
            self._stats["total_executions"] = len(self._executions)
        
        return self._stats.copy()


# ============== FACTORY ==============

class ScenarioFactory:
    """Factory pour créer des composants de scénarios."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ScenarioManager:
        """Crée un gestionnaire de scénarios."""
        manager = ScenarioManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager


# ============== EXPORT ==============

__all__ = [
    "ScenarioType",
    "ScenarioStatus",
    "ScenarioPriority",
    "ScenarioOutcome",
    "Scenario",
    "ScenarioExecution",
    "ScenarioComparison",
    "ScenarioTemplate",
    "ScenarioManagerInterface",
    "ScenarioManager",
    "ScenarioFactory"
]

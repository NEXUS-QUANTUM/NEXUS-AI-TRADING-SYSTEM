# trading/bots/hedge_bot/hedge_bot_sensitivity.py
# Advanced Sensitivity Analysis & Stress Testing Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Sensitivity Module - Module avancé d'analyse de sensibilité et de tests de résistance
pour le Hedge Bot. Analyse l'impact des paramètres, la robustesse des stratégies,
la sensibilité aux conditions de marché et la stabilité du système de hedging.
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
from scipy import stats
from scipy.optimize import minimize
import itertools

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_sensitivity")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType, HedgeStrategy
)


# ============== ENUMS & TYPES ==============

class SensitivityType(Enum):
    """Types d'analyse de sensibilité."""
    PARAMETER = "parameter"           # Sensibilité aux paramètres
    MARKET = "market"                 # Sensibilité aux conditions de marché
    VOLATILITY = "volatility"         # Sensibilité à la volatilité
    CORRELATION = "correlation"       # Sensibilité aux corrélations
    LIQUIDITY = "liquidity"           # Sensibilité à la liquidité
    TIMING = "timing"                 # Sensibilité au timing
    REGIME = "regime"                 # Sensibilité aux régimes de marché
    STRATEGY = "strategy"             # Sensibilité à la stratégie
    EXECUTION = "execution"           # Sensibilité à l'exécution


class SensitivityMetric(Enum):
    """Métriques de sensibilité."""
    SHARPE = "sharpe"
    SORTINO = "sortino"
    CALMAR = "calmar"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_VALUE = "expected_value"
    VOLATILITY = "volatility"
    BETA = "beta"
    ALPHA = "alpha"
    R_SQUARED = "r_squared"
    INFORMATION_RATIO = "information_ratio"


class SensitivityLevel(Enum):
    """Niveaux de sensibilité."""
    LOW = "low"                       # Sensibilité faible
    MEDIUM = "medium"                 # Sensibilité moyenne
    HIGH = "high"                     # Sensibilité élevée
    CRITICAL = "critical"             # Sensibilité critique


# ============== DATA MODELS ==============

@dataclass
class SensitivityAnalysis:
    """Analyse de sensibilité."""
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    sensitivity_type: SensitivityType = SensitivityType.PARAMETER
    metrics: List[SensitivityMetric] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    base_values: Dict[str, float] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    sensitivity_scores: Dict[str, float] = field(default_factory=dict)
    critical_parameters: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ScenarioAnalysis:
    """Analyse de scénario."""
    scenario_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    base_result: Dict[str, float] = field(default_factory=dict)
    scenario_results: Dict[str, Dict[str, float]] = field(default_factory=dict)
    deviations: Dict[str, float] = field(default_factory=dict)
    impact_score: float = 0.0
    probability: float = 0.0
    severity: str = "medium"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParameterSensitivity:
    """Sensibilité d'un paramètre."""
    parameter_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parameter_name: str = ""
    base_value: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    sensitivity: float = 0.0
    elasticity: float = 0.0
    contribution: float = 0.0
    level: SensitivityLevel = SensitivityLevel.MEDIUM
    metric: SensitivityMetric = SensitivityMetric.SHARPE
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class SensitivityEngineInterface(ABC):
    """Interface abstraite pour le moteur de sensibilité."""
    
    @abstractmethod
    async def analyze_sensitivity(self, config: Dict[str, Any]) -> SensitivityAnalysis:
        """Analyse la sensibilité du système."""
        pass
    
    @abstractmethod
    async def run_scenario(self, scenario: ScenarioAnalysis) -> ScenarioAnalysis:
        """Exécute une analyse de scénario."""
        pass
    
    @abstractmethod
    async def identify_critical_parameters(self, analysis: SensitivityAnalysis) -> List[str]:
        """Identifie les paramètres critiques."""
        pass


# ============== IMPLÉMENTATION ==============

class SensitivityEngine(SensitivityEngineInterface):
    """
    Moteur d'analyse de sensibilité avancé pour le Hedge Bot.
    Analyse la robustesse et la stabilité du système de hedging.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des analyses
        self._analyses: Dict[str, SensitivityAnalysis] = {}
        self._analyses_lock = threading.RLock()
        
        # Gestion des scénarios
        self._scenarios: Dict[str, ScenarioAnalysis] = {}
        self._scenarios_lock = threading.RLock()
        
        # Gestion des paramètres sensibles
        self._sensitive_params: Dict[str, ParameterSensitivity] = {}
        self._params_lock = threading.RLock()
        
        # Cache des calculs
        self._calculation_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "analyses_performed": 0,
            "scenarios_run": 0,
            "critical_params_found": 0,
            "avg_sensitivity": 0.0,
            "high_sensitivity_count": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("SensitivityEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "sensitivity_threshold": 0.1,
            "critical_threshold": 0.3,
            "num_samples": 100,
            "confidence_level": 0.95,
            "parameter_ranges": {},
            "default_metrics": ["sharpe", "max_drawdown", "win_rate"],
            "scenario_probability": 0.5,
            "use_monte_carlo": True,
            "parallel_analysis": True,
            "cache_size": 100
        }
    
    async def start(self) -> None:
        """Démarre le moteur de sensibilité."""
        logger.info("SensitivityEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("SensitivityEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de sensibilité."""
        logger.info("SensitivityEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("SensitivityEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def analyze_sensitivity(self, config: Dict[str, Any]) -> SensitivityAnalysis:
        """Analyse la sensibilité du système."""
        self._stats["analyses_performed"] += 1
        
        try:
            # Configuration
            sensitivity_type = SensitivityType(config.get("type", "parameter"))
            metrics = config.get("metrics", [SensitivityMetric.SHARPE])
            parameters = config.get("parameters", {})
            
            # Définition des plages de paramètres
            param_ranges = self._get_parameter_ranges(parameters)
            
            # Analyse de sensibilité
            results = {}
            sensitivity_scores = {}
            critical_params = []
            
            for param_name, (min_val, max_val) in param_ranges.items():
                # Évaluation de la sensibilité
                sensitivity = await self._evaluate_parameter_sensitivity(
                    param_name, min_val, max_val, metrics
                )
                results[param_name] = sensitivity
                
                # Score de sensibilité
                score = np.mean([s["sensitivity"] for s in sensitivity.values()])
                sensitivity_scores[param_name] = score
                
                # Identification des paramètres critiques
                if score > self.config["critical_threshold"]:
                    critical_params.append(param_name)
            
            # Génération des recommandations
            recommendations = await self._generate_recommendations(
                sensitivity_scores, critical_params
            )
            
            # Création de l'analyse
            analysis = SensitivityAnalysis(
                name=config.get("name", f"Sensitivity_{uuid.uuid4().hex[:8]}"),
                sensitivity_type=sensitivity_type,
                metrics=metrics,
                parameters=parameters,
                base_values={p: (min_val + max_val) / 2 for p, (min_val, max_val) in param_ranges.items()},
                results=results,
                sensitivity_scores=sensitivity_scores,
                critical_parameters=critical_params,
                recommendations=recommendations,
                metadata=config.get("metadata", {})
            )
            
            # Stockage de l'analyse
            with self._analyses_lock:
                self._analyses[analysis.analysis_id] = analysis
            
            # Mise à jour des statistiques
            self._stats["critical_params_found"] += len(critical_params)
            self._stats["avg_sensitivity"] = (
                self._stats["avg_sensitivity"] * 0.9 +
                np.mean(list(sensitivity_scores.values())) * 0.1
            )
            
            logger.info(f"Sensitivity analysis completed: {len(critical_params)} critical parameters")
            return analysis
            
        except Exception as e:
            logger.error(f"Sensitivity analysis error: {e}")
            raise
    
    async def run_scenario(self, scenario: ScenarioAnalysis) -> ScenarioAnalysis:
        """Exécute une analyse de scénario."""
        self._stats["scenarios_run"] += 1
        
        try:
            # Simulation du scénario
            base_result = await self._simulate_base_case(scenario.parameters)
            scenario_results = {}
            deviations = {}
            
            for param_name, param_value in scenario.parameters.items():
                # Variation du paramètre
                variant_params = scenario.parameters.copy()
                variant_params[param_name] = param_value * 1.5
                
                result = await self._simulate_scenario(variant_params)
                scenario_results[param_name] = result
                
                # Calcul de la déviation
                deviation = abs(result.get("sharpe", 0) - base_result.get("sharpe", 0))
                deviations[param_name] = deviation
            
            # Score d'impact
            impact_score = np.mean(list(deviations.values()))
            
            # Mise à jour du scénario
            scenario.base_result = base_result
            scenario.scenario_results = scenario_results
            scenario.deviations = deviations
            scenario.impact_score = impact_score
            scenario.severity = self._determine_severity(impact_score)
            
            # Stockage du scénario
            with self._scenarios_lock:
                self._scenarios[scenario.scenario_id] = scenario
            
            logger.info(f"Scenario analysis completed: {scenario.name} impact={impact_score:.3f}")
            return scenario
            
        except Exception as e:
            logger.error(f"Scenario analysis error: {e}")
            raise
    
    async def identify_critical_parameters(self, analysis: SensitivityAnalysis) -> List[str]:
        """Identifie les paramètres critiques."""
        return analysis.critical_parameters
    
    # ========== MÉTHODES PRIVÉES - SENSIBILITÉ ==========
    
    async def _evaluate_parameter_sensitivity(
        self,
        param_name: str,
        min_val: float,
        max_val: float,
        metrics: List[SensitivityMetric]
    ) -> Dict[str, Dict[str, float]]:
        """Évalue la sensibilité d'un paramètre."""
        results = {}
        
        # Échantillonnage
        values = np.linspace(min_val, max_val, self.config["num_samples"])
        
        for metric in metrics:
            sensitivities = []
            
            for value in values:
                # Simulation avec la valeur du paramètre
                # Dans un système réel, on exécuterait le modèle
                result = await self._simulate_parameter_value(param_name, value, metric)
                sensitivities.append(result)
            
            # Calcul de la sensibilité
            sensitivity = np.std(sensitivities) / (np.mean(sensitivities) + 1e-6)
            elasticity = np.gradient(sensitivities, values).mean()
            
            results[metric.value] = {
                "sensitivity": sensitivity,
                "elasticity": elasticity,
                "mean": np.mean(sensitivities),
                "std": np.std(sensitivities),
                "min": np.min(sensitivities),
                "max": np.max(sensitivities)
            }
        
        return results
    
    async def _simulate_parameter_value(
        self,
        param_name: str,
        value: float,
        metric: SensitivityMetric
    ) -> float:
        """Simule une valeur de paramètre."""
        # Simulation simplifiée
        # Dans un système réel, on exécuterait la stratégie
        
        # Effet de base
        base = 0.5
        
        # Effet du paramètre
        param_effect = value * 0.5
        
        # Bruit
        noise = np.random.normal(0, 0.05)
        
        result = base + param_effect + noise
        
        # Ajustement selon la métrique
        if metric == SensitivityMetric.SHARPE:
            result = min(3.0, max(-1.0, result * 2))
        elif metric == SensitivityMetric.MAX_DRAWDOWN:
            result = min(0.5, max(0.0, 1 - result))
        elif metric == SensitivityMetric.WIN_RATE:
            result = min(1.0, max(0.0, 0.5 + result * 0.4))
        
        return result
    
    async def _simulate_base_case(self, parameters: Dict[str, Any]) -> Dict[str, float]:
        """Simule le cas de base."""
        return {
            "sharpe": 1.5 + np.random.normal(0, 0.1),
            "max_drawdown": 0.1 + np.random.normal(0, 0.02),
            "win_rate": 0.6 + np.random.normal(0, 0.05),
            "profit_factor": 2.0 + np.random.normal(0, 0.2)
        }
    
    async def _simulate_scenario(self, parameters: Dict[str, Any]) -> Dict[str, float]:
        """Simule un scénario."""
        # Variation des résultats
        base = await self._simulate_base_case(parameters)
        
        # Impact des paramètres
        for param, value in parameters.items():
            if isinstance(value, (int, float)):
                impact = value * 0.1
                base["sharpe"] += impact
                base["max_drawdown"] += impact * 0.5
                base["win_rate"] += impact * 0.2
        
        return base
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _get_parameter_ranges(self, parameters: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
        """Définit les plages des paramètres."""
        ranges = {}
        
        for param, value in parameters.items():
            if isinstance(value, (int, float)):
                # Plage par défaut: ±50%
                min_val = value * 0.5
                max_val = value * 1.5
                
                # Utilisation des plages personnalisées
                if param in self.config["parameter_ranges"]:
                    min_val, max_val = self.config["parameter_ranges"][param]
                
                ranges[param] = (min_val, max_val)
        
        return ranges
    
    def _determine_severity(self, impact: float) -> str:
        """Détermine la sévérité d'un impact."""
        if impact > 0.3:
            return "critical"
        elif impact > 0.2:
            return "high"
        elif impact > 0.1:
            return "medium"
        else:
            return "low"
    
    async def _generate_recommendations(
        self,
        sensitivity_scores: Dict[str, float],
        critical_params: List[str]
    ) -> List[str]:
        """Génère des recommandations."""
        recommendations = []
        
        if not critical_params:
            recommendations.append("No critical parameters detected. System appears robust.")
            return recommendations
        
        for param in critical_params:
            score = sensitivity_scores[param]
            recommendations.append(
                f"Parameter '{param}' is critical (score={score:.2f}). "
                "Consider reducing sensitivity or implementing dynamic adjustment."
            )
        
        # Recommandations générales
        if len(critical_params) > 3:
            recommendations.append(
                "Multiple critical parameters detected. "
                "Consider simplifying the model or adding robustness measures."
            )
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._calculation_cache) > self.config["cache_size"]:
                        keys = list(self._calculation_cache.keys())
                        for key in keys[:len(self._calculation_cache) - self.config["cache_size"]]:
                            del self._calculation_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._analyses_lock:
                    self._stats["total_analyses"] = len(self._analyses)
                with self._scenarios_lock:
                    self._stats["total_scenarios"] = len(self._scenarios)
                with self._params_lock:
                    self._stats["total_parameters"] = len(self._sensitive_params)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "sensitivity:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_analysis(self, analysis_id: str) -> Optional[SensitivityAnalysis]:
        """Récupère une analyse."""
        with self._analyses_lock:
            return self._analyses.get(analysis_id)
    
    async def get_analyses(self) -> List[SensitivityAnalysis]:
        """Récupère les analyses."""
        with self._analyses_lock:
            return list(self._analyses.values())
    
    async def get_scenario(self, scenario_id: str) -> Optional[ScenarioAnalysis]:
        """Récupère un scénario."""
        with self._scenarios_lock:
            return self._scenarios.get(scenario_id)
    
    async def get_scenarios(self) -> List[ScenarioAnalysis]:
        """Récupère les scénarios."""
        with self._scenarios_lock:
            return list(self._scenarios.values())
    
    async def get_parameter_sensitivity(self, param_name: str) -> Optional[ParameterSensitivity]:
        """Récupère la sensibilité d'un paramètre."""
        with self._params_lock:
            return self._sensitive_params.get(param_name)
    
    async def run_monte_carlo_sensitivity(
        self,
        config: Dict[str, Any],
        num_samples: int = 1000
    ) -> SensitivityAnalysis:
        """Exécute une analyse de sensibilité Monte Carlo."""
        # Création de la configuration
        mc_config = config.copy()
        mc_config["use_monte_carlo"] = True
        mc_config["num_samples"] = num_samples
        
        return await self.analyze_sensitivity(mc_config)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._analyses_lock:
            self._stats["total_analyses"] = len(self._analyses)
        with self._scenarios_lock:
            self._stats["total_scenarios"] = len(self._scenarios)
        
        return self._stats.copy()


# ============== SENSITIVITY REPORT ==============

class SensitivityReport:
    """
    Générateur de rapports de sensibilité.
    Crée des rapports détaillés d'analyse de sensibilité.
    """
    
    def __init__(self, engine: SensitivityEngine):
        self.engine = engine
    
    async def generate(self, analysis_id: str) -> Dict[str, Any]:
        """Génère un rapport de sensibilité."""
        analysis = await self.engine.get_analysis(analysis_id)
        if not analysis:
            return {"error": "Analysis not found"}
        
        report = {
            "analysis_id": analysis.analysis_id,
            "name": analysis.name,
            "type": analysis.sensitivity_type.value,
            "timestamp": analysis.timestamp.isoformat(),
            "summary": {
                "total_parameters": len(analysis.sensitivity_scores),
                "critical_parameters": len(analysis.critical_parameters),
                "avg_sensitivity": np.mean(list(analysis.sensitivity_scores.values()))
            },
            "critical_parameters": analysis.critical_parameters,
            "sensitivity_scores": analysis.sensitivity_scores,
            "recommendations": analysis.recommendations,
            "detailed_results": analysis.results
        }
        
        # Statistiques par métrique
        metrics = {}
        for param, results in analysis.results.items():
            for metric, values in results.items():
                if metric not in metrics:
                    metrics[metric] = []
                metrics[metric].append(values["sensitivity"])
        
        report["metric_statistics"] = {
            metric: {
                "mean": np.mean(values),
                "std": np.std(values),
                "max": np.max(values),
                "min": np.min(values)
            }
            for metric, values in metrics.items()
        }
        
        return report


# ============== FACTORY ==============

class SensitivityFactory:
    """Factory pour créer des composants de sensibilité."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SensitivityEngine:
        """Crée un moteur de sensibilité."""
        engine = SensitivityEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_report(engine: SensitivityEngine) -> SensitivityReport:
        """Crée un générateur de rapports."""
        return SensitivityReport(engine)


# ============== EXPORT ==============

__all__ = [
    "SensitivityType",
    "SensitivityMetric",
    "SensitivityLevel",
    "SensitivityAnalysis",
    "ScenarioAnalysis",
    "ParameterSensitivity",
    "SensitivityEngineInterface",
    "SensitivityEngine",
    "SensitivityReport",
    "SensitivityFactory"
]

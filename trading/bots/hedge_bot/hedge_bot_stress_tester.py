# trading/bots/hedge_bot/hedge_bot_stress_tester.py
# Advanced Stress Testing & Scenario Analysis Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Stress Tester Module - Module avancé de tests de stress et d'analyse de scénarios pour le Hedge Bot.
Simule des conditions de marché extrêmes, teste la résilience du système, analyse la performance
en situation de crise et valide les stratégies de hedging sous stress.
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
import random
from scipy import stats
from scipy.optimize import minimize

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_stress_tester")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType, HedgeStrategy
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult, OrderStatus
)


# ============== ENUMS & TYPES ==============

class StressType(Enum):
    """Types de tests de stress."""
    MARKET_SHOCK = "market_shock"              # Choc de marché
    VOLATILITY_SPIKE = "volatility_spike"      # Pic de volatilité
    LIQUIDITY_CRISIS = "liquidity_crisis"      # Crise de liquidité
    CORRELATION_BREAK = "correlation_break"    # Rupture de corrélation
    FLASH_CRASH = "flash_crash"                # Flash crash
    GAP_OPEN = "gap_open"                      # Gap à l'ouverture
    CIRCUIT_BREAKER = "circuit_breaker"        # Circuit breaker
    SYSTEM_FAILURE = "system_failure"          # Panne système
    NETWORK_LATENCY = "network_latency"        # Latence réseau
    ORDER_FLOW_IMBALANCE = "order_flow_imbalance"  # Déséquilibre des ordres


class ScenarioType(Enum):
    """Types de scénarios."""
    HISTORICAL = "historical"                  # Scénario historique
    SYNTHETIC = "synthetic"                    # Scénario synthétique
    MONTE_CARLO = "monte_carlo"                # Simulation Monte Carlo
    STRESS = "stress"                          # Stress test
    WHAT_IF = "what_if"                        # Analyse what-if
    BLACK_SWAN = "black_swan"                  # Cygne noir


class StressSeverity(Enum):
    """Niveaux de sévérité des stress."""
    MILD = "mild"                              # Léger (5-15% de variation)
    MODERATE = "moderate"                      # Modéré (15-30% de variation)
    SEVERE = "severe"                          # Sévère (30-50% de variation)
    EXTREME = "extreme"                        # Extrême (50-80% de variation)
    CATASTROPHIC = "catastrophic"              # Catastrophique (>80% de variation)


# ============== DATA MODELS ==============

@dataclass
class StressScenario:
    """Scénario de stress."""
    scenario_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    scenario_type: ScenarioType = ScenarioType.SYNTHETIC
    stress_type: StressType = StressType.MARKET_SHOCK
    severity: StressSeverity = StressSeverity.MODERATE
    parameters: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration: int = 60  # secondes
    impact_assets: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "scenario_type": self.scenario_type.value,
            "stress_type": self.stress_type.value,
            "severity": self.severity.value,
            "parameters": self.parameters,
            "start_time": self.start_time.isoformat(),
            "duration": self.duration,
            "impact_assets": self.impact_assets,
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class StressTestResult:
    """Résultat de test de stress."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    success: bool = False
    max_drawdown: float = 0.0
    max_loss: float = 0.0
    recovery_time: float = 0.0
    var_break: float = 0.0
    expected_shortfall: float = 0.0
    sharpe_ratio: float = 0.0
    resilience_score: float = 0.0
    recovery_score: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    breakdowns: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class StressMetric:
    """Métrique de stress."""
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    value: float = 0.0
    threshold: float = 0.0
    status: str = "pass"  # pass, warning, fail, critical
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class StressTesterInterface(ABC):
    """Interface abstraite pour le testeur de stress."""
    
    @abstractmethod
    async def create_scenario(self, config: Dict[str, Any]) -> StressScenario:
        """Crée un scénario de stress."""
        pass
    
    @abstractmethod
    async def run_scenario(self, scenario_id: str) -> StressTestResult:
        """Exécute un scénario de stress."""
        pass
    
    @abstractmethod
    async def run_monte_carlo(self, params: Dict[str, Any]) -> List[StressTestResult]:
        """Exécute une simulation Monte Carlo."""
        pass


# ============== IMPLÉMENTATION ==============

class StressTester(StressTesterInterface):
    """
    Testeur de stress avancé pour le Hedge Bot.
    Simule des conditions extrêmes et valide la robustesse du système.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des scénarios
        self._scenarios: Dict[str, StressScenario] = {}
        self._scenarios_lock = threading.RLock()
        
        # Gestion des résultats
        self._results: Dict[str, StressTestResult] = {}
        self._results_lock = threading.RLock()
        
        # Gestion des métriques
        self._metrics: Dict[str, List[StressMetric]] = defaultdict(list)
        self._metrics_lock = threading.RLock()
        
        # Historique des simulations
        self._simulation_history: deque = deque(maxlen=10000)
        self._history_lock = threading.RLock()
        
        # Cache des données historiques
        self._historical_cache: Dict[str, pd.DataFrame] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "scenarios_created": 0,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "avg_resilience": 0.0,
            "critical_breaks": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("StressTester initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_simulation_count": 1000,
            "confidence_level": 0.95,
            "timeout": 3600,
            "max_history": 10000,
            "enable_parallel": True,
            "scenario_library": [
                "2008_financial_crisis",
                "2020_covid_crash",
                "2022_volatility_crisis",
                "flash_crash_2010",
                "swiss_franc_shock_2015"
            ],
            "var_periods": [1, 5, 10, 20, 50],
            "drawdown_threshold": 0.1,
            "recovery_threshold": 0.5,
            "critical_threshold": 0.2
        }
    
    async def start(self) -> None:
        """Démarre le testeur de stress."""
        logger.info("StressTester starting...")
        self._is_running = True
        
        # Chargement des scénarios historiques
        await self._load_historical_scenarios()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._cleanup_loop())
        
        logger.info("StressTester started")
    
    async def stop(self) -> None:
        """Arrête le testeur de stress."""
        logger.info("StressTester stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("StressTester stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_scenario(self, config: Dict[str, Any]) -> StressScenario:
        """Crée un scénario de stress."""
        scenario = StressScenario(
            name=config.get("name", f"Scenario_{uuid.uuid4().hex[:8]}"),
            description=config.get("description", ""),
            scenario_type=ScenarioType(config.get("scenario_type", "synthetic")),
            stress_type=StressType(config.get("stress_type", "market_shock")),
            severity=StressSeverity(config.get("severity", "moderate")),
            parameters=config.get("parameters", {}),
            duration=config.get("duration", 60),
            impact_assets=config.get("impact_assets", []),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        with self._scenarios_lock:
            self._scenarios[scenario.scenario_id] = scenario
            self._stats["scenarios_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"stress:scenario:{scenario.scenario_id}",
                scenario.to_dict(),
                DataType.SCENARIO
            )
        
        logger.info(f"Stress scenario created: {scenario.name} (id={scenario.scenario_id})")
        return scenario
    
    async def run_scenario(self, scenario_id: str) -> StressTestResult:
        """Exécute un scénario de stress."""
        self._stats["tests_run"] += 1
        
        with self._scenarios_lock:
            scenario = self._scenarios.get(scenario_id)
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
        
        try:
            # Génération des données de stress
            stress_data = await self._generate_stress_data(scenario)
            
            # Exécution de la simulation
            result = await self._simulate_stress(scenario, stress_data)
            
            # Calcul des métriques
            metrics = await self._calculate_stress_metrics(scenario, result)
            
            # Détermination du succès
            result.success = result.resilience_score >= 0.5
            
            # Mise à jour des statistiques
            if result.success:
                self._stats["tests_passed"] += 1
            else:
                self._stats["tests_failed"] += 1
            
            self._stats["avg_resilience"] = (
                self._stats["avg_resilience"] * 0.9 + result.resilience_score * 0.1
            )
            
            # Stockage du résultat
            with self._results_lock:
                self._results[result.result_id] = result
            
            if self.data_manager:
                await self.data_manager.store(
                    f"stress:result:{result.result_id}",
                    result.to_dict(),
                    DataType.RESULT
                )
            
            logger.info(f"Stress test completed: {scenario.name} "
                       f"resilience={result.resilience_score:.2f}")
            
            return result
            
        except Exception as e:
            self._stats["tests_failed"] += 1
            logger.error(f"Stress test error: {e}")
            raise
    
    async def run_monte_carlo(self, params: Dict[str, Any]) -> List[StressTestResult]:
        """Exécute une simulation Monte Carlo."""
        num_simulations = params.get("num_simulations", self.config["default_simulation_count"])
        
        logger.info(f"Running Monte Carlo simulation with {num_simulations} iterations")
        
        # Création du scénario de base
        base_config = {
            "name": "Monte Carlo Simulation",
            "scenario_type": ScenarioType.MONTE_CARLO.value,
            "stress_type": StressType.MARKET_SHOCK.value,
            "severity": StressSeverity.MODERATE.value,
            "duration": params.get("duration", 60),
            "parameters": {
                "volatility_range": params.get("volatility_range", (0.1, 0.5)),
                "shock_magnitude": params.get("shock_magnitude", 0.3),
                "correlation_range": params.get("correlation_range", (-0.5, 0.5))
            },
            "impact_assets": params.get("impact_assets", ["BTC-USD", "ETH-USD", "SPX"])
        }
        
        base_scenario = await self.create_scenario(base_config)
        
        # Exécution des simulations
        results = []
        
        if self.config["enable_parallel"]:
            # Parallélisation
            tasks = []
            for i in range(num_simulations):
                # Variation des paramètres
                scenario = copy.deepcopy(base_scenario)
                scenario.parameters["volatility"] = random.uniform(
                    params.get("volatility_range", (0.1, 0.5))[0],
                    params.get("volatility_range", (0.1, 0.5))[1]
                )
                scenario.parameters["shock_magnitude"] = random.uniform(
                    params.get("shock_magnitude", 0.1),
                    params.get("shock_magnitude", 0.5)
                )
                scenario.parameters["correlation"] = random.uniform(
                    params.get("correlation_range", (-0.5, 0.5))[0],
                    params.get("correlation_range", (-0.5, 0.5))[1]
                )
                
                task = asyncio.create_task(self.run_scenario(scenario.scenario_id))
                tasks.append(task)
            
            # Attente des résultats
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    results.append(result)
                except Exception as e:
                    logger.error(f"Monte Carlo iteration failed: {e}")
        else:
            # Exécution séquentielle
            for i in range(num_simulations):
                scenario = copy.deepcopy(base_scenario)
                scenario.parameters["volatility"] = random.uniform(
                    params.get("volatility_range", (0.1, 0.5))[0],
                    params.get("volatility_range", (0.1, 0.5))[1]
                )
                scenario.parameters["shock_magnitude"] = random.uniform(
                    params.get("shock_magnitude", 0.1),
                    params.get("shock_magnitude", 0.5)
                )
                scenario.parameters["correlation"] = random.uniform(
                    params.get("correlation_range", (-0.5, 0.5))[0],
                    params.get("correlation_range", (-0.5, 0.5))[1]
                )
                
                try:
                    result = await self.run_scenario(scenario.scenario_id)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Monte Carlo iteration {i} failed: {e}")
        
        # Analyse des résultats
        analysis = self._analyze_monte_carlo_results(results)
        
        logger.info(f"Monte Carlo simulation completed: {len(results)} successful iterations")
        
        # Stockage de l'analyse
        if self.data_manager:
            await self.data_manager.store(
                f"stress:monte_carlo:{uuid.uuid4()}",
                analysis,
                DataType.ANALYSIS
            )
        
        return results
    
    # ========== MÉTHODES PRIVÉES - SIMULATION ==========
    
    async def _generate_stress_data(self, scenario: StressScenario) -> pd.DataFrame:
        """Génère des données de stress."""
        # Détermination des paramètres
        magnitude = self._get_magnitude(scenario.severity)
        
        # Données de base
        assets = scenario.impact_assets or ["BTC-USD", "ETH-USD", "SPX"]
        periods = scenario.duration * 2  # Points de données
        
        # Génération des données
        data = {}
        
        for asset in assets:
            # Prix de base
            base_price = 100.0
            
            # Stress selon le type
            if scenario.stress_type == StressType.MARKET_SHOCK:
                prices = self._generate_market_shock(base_price, magnitude, periods, scenario)
            elif scenario.stress_type == StressType.VOLATILITY_SPIKE:
                prices = self._generate_volatility_spike(base_price, magnitude, periods, scenario)
            elif scenario.stress_type == StressType.LIQUIDITY_CRISIS:
                prices = self._generate_liquidity_crisis(base_price, magnitude, periods, scenario)
            elif scenario.stress_type == StressType.CORRELATION_BREAK:
                prices = self._generate_correlation_break(base_price, magnitude, periods, scenario)
            elif scenario.stress_type == StressType.FLASH_CRASH:
                prices = self._generate_flash_crash(base_price, magnitude, periods, scenario)
            elif scenario.stress_type == StressType.CIRCUIT_BREAKER:
                prices = self._generate_circuit_breaker(base_price, magnitude, periods, scenario)
            else:
                prices = self._generate_default_stress(base_price, magnitude, periods)
            
            data[asset] = prices
        
        # Création du DataFrame
        df = pd.DataFrame(data)
        df.index = pd.date_range(
            start=scenario.start_time,
            periods=periods,
            freq='1s'
        )
        
        return df
    
    def _get_magnitude(self, severity: StressSeverity) -> float:
        """Obtient la magnitude du stress."""
        magnitudes = {
            StressSeverity.MILD: (0.05, 0.15),
            StressSeverity.MODERATE: (0.15, 0.30),
            StressSeverity.SEVERE: (0.30, 0.50),
            StressSeverity.EXTREME: (0.50, 0.80),
            StressSeverity.CATASTROPHIC: (0.80, 0.95)
        }
        
        min_mag, max_mag = magnitudes.get(severity, (0.15, 0.30))
        return random.uniform(min_mag, max_mag)
    
    def _generate_market_shock(self, base_price: float, magnitude: float, periods: int, scenario: StressScenario) -> List[float]:
        """Génère un choc de marché."""
        prices = [base_price]
        shock_time = int(periods * 0.3)
        
        for i in range(1, periods):
            if i == shock_time:
                # Choc soudain
                change = -magnitude * random.uniform(0.8, 1.2)
            elif i > shock_time:
                # Récupération partielle
                recovery = 0.5 * magnitude * (i - shock_time) / (periods - shock_time)
                change = recovery * random.uniform(0.5, 1.5)
            else:
                # Volatilité normale avant choc
                change = random.gauss(0, 0.005)
            
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, 1.0))
        
        return prices
    
    def _generate_volatility_spike(self, base_price: float, magnitude: float, periods: int, scenario: StressScenario) -> List[float]:
        """Génère un pic de volatilité."""
        prices = [base_price]
        
        for i in range(1, periods):
            # Volatilité variable
            if i < periods * 0.2:
                vol = 0.01
            elif i < periods * 0.6:
                # Spike de volatilité
                vol = magnitude * random.uniform(0.5, 1.5)
            else:
                # Retour à la normale
                vol = 0.01 * (1 + (i - periods * 0.6) / (periods * 0.4))
            
            change = random.gauss(0, vol)
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, 1.0))
        
        return prices
    
    def _generate_liquidity_crisis(self, base_price: float, magnitude: float, periods: int, scenario: StressScenario) -> List[float]:
        """Génère une crise de liquidité."""
        prices = [base_price]
        spread_multiplier = 1.0
        
        for i in range(1, periods):
            if i < periods * 0.2:
                # Phase normale
                spread_multiplier = 1.0
            elif i < periods * 0.5:
                # Crise de liquidité
                spread_multiplier = 1 + magnitude * 5 * (i - periods * 0.2) / (periods * 0.3)
            else:
                # Récupération
                spread_multiplier = 1 + magnitude * 5 * (periods * 0.5 - i) / (periods * 0.5)
            
            # Impact sur les prix
            price_impact = random.gauss(0, 0.01 * spread_multiplier)
            new_price = prices[-1] * (1 + price_impact)
            prices.append(max(new_price, 1.0))
        
        return prices
    
    def _generate_correlation_break(self, base_price: float, magnitude: float, periods: int, scenario: StressScenario) -> List[float]:
        """Génère une rupture de corrélation."""
        prices = [base_price]
        
        for i in range(1, periods):
            if i < periods * 0.4:
                # Corrélation normale
                change = random.gauss(0, 0.01)
            elif i < periods * 0.6:
                # Rupture de corrélation
                change = random.gauss(0, magnitude * 0.5) * random.choice([-1, 1])
            else:
                # Nouvelle normalité
                change = random.gauss(0, 0.02)
            
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, 1.0))
        
        return prices
    
    def _generate_flash_crash(self, base_price: float, magnitude: float, periods: int, scenario: StressScenario) -> List[float]:
        """Génère un flash crash."""
        prices = [base_price]
        crash_time = int(periods * 0.4)
        recovery_time = int(periods * 0.6)
        
        for i in range(1, periods):
            if i == crash_time:
                # Flash crash
                change = -magnitude * random.uniform(1.5, 2.5)
            elif crash_time < i < recovery_time:
                # Baisse rapide
                change = -magnitude * 0.1 * random.uniform(0.5, 1.5)
            elif i >= recovery_time:
                # Récupération rapide
                recovery_factor = (i - recovery_time) / (periods - recovery_time)
                change = magnitude * 0.3 * recovery_factor * random.uniform(0.5, 1.5)
            else:
                change = random.gauss(0, 0.005)
            
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, 1.0))
        
        return prices
    
    def _generate_circuit_breaker(self, base_price: float, magnitude: float, periods: int, scenario: StressScenario) -> List[float]:
        """Génère un circuit breaker."""
        prices = [base_price]
        breaker_count = 0
        
        for i in range(1, periods):
            if i < periods * 0.3:
                # Baisse rapide
                change = -magnitude * 0.02 * random.uniform(0.5, 1.5)
            elif i < periods * 0.4:
                # Circuit breaker
                change = 0
                breaker_count += 1
            else:
                # Reprise
                change = magnitude * 0.01 * random.uniform(0.5, 1.5)
            
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, 1.0))
        
        return prices
    
    def _generate_default_stress(self, base_price: float, magnitude: float, periods: int) -> List[float]:
        """Génère un stress par défaut."""
        prices = [base_price]
        
        for i in range(1, periods):
            if i < periods * 0.2:
                change = random.gauss(0, 0.01)
            elif i < periods * 0.5:
                change = random.gauss(0, magnitude * 0.1)
            else:
                change = random.gauss(0, 0.015)
            
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, 1.0))
        
        return prices
    
    # ========== MÉTHODES PRIVÉES - SIMULATION ==========
    
    async def _simulate_stress(self, scenario: StressScenario, data: pd.DataFrame) -> StressTestResult:
        """Simule un scénario de stress."""
        # Simulation des réactions du hedge bot
        positions = []
        pnl_history = []
        drawdown_history = []
        var_history = []
        
        for idx, row in data.iterrows():
            # Simulation de la réaction du système
            # Dans un système réel, on exécuterait le hedge bot
            
            # Calcul du PnL
            pnl = 0.0
            for asset in data.columns:
                if asset in row:
                    # PnL simplifié
                    pnl += row[asset] * 0.1
            
            pnl_history.append(pnl)
            
            # Calcul du drawdown
            if pnl_history:
                current_max = max(pnl_history)
                drawdown = (current_max - pnl) / current_max if current_max > 0 else 0
                drawdown_history.append(drawdown)
            
            # Calcul du VaR
            if len(pnl_history) > 10:
                var = np.percentile(pnl_history[-10:], 5)
                var_history.append(var)
        
        # Calcul des métriques
        max_drawdown = max(drawdown_history) if drawdown_history else 0.0
        max_loss = min(pnl_history) if pnl_history else 0.0
        final_pnl = pnl_history[-1] if pnl_history else 0.0
        
        # Temps de récupération
        recovery_time = 0
        if drawdown_history:
            for i, dd in enumerate(drawdown_history):
                if dd < 0.1:
                    recovery_time = i
                    break
        
        # VaR et Expected Shortfall
        if var_history:
            var_break = max(var_history)
            expected_shortfall = np.mean([v for v in var_history if v < var_break])
        else:
            var_break = 0.0
            expected_shortfall = 0.0
        
        # Sharpe ratio simulé
        if pnl_history:
            mean_pnl = np.mean(pnl_history)
            std_pnl = np.std(pnl_history) if np.std(pnl_history) > 0 else 0.001
            sharpe_ratio = mean_pnl / std_pnl * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
        
        # Score de résilience
        resilience_score = self._calculate_resilience(
            max_drawdown, max_loss, recovery_time, var_break, expected_shortfall
        )
        
        # Score de récupération
        recovery_score = 1 - (recovery_time / len(data)) if len(data) > 0 else 0
        
        # Création du résultat
        result = StressTestResult(
            scenario_id=scenario.scenario_id,
            max_drawdown=max_drawdown,
            max_loss=abs(max_loss),
            recovery_time=recovery_time,
            var_break=var_break,
            expected_shortfall=abs(expected_shortfall),
            sharpe_ratio=sharpe_ratio,
            resilience_score=resilience_score,
            recovery_score=recovery_score,
            metrics={
                "final_pnl": final_pnl,
                "peak_pnl": max(pnl_history) if pnl_history else 0,
                "volatility": np.std(pnl_history) if pnl_history else 0,
                "var_95": var_break if var_break else 0
            },
            breakdowns=[
                {"type": "drawdown", "max": max_drawdown},
                {"type": "loss", "max": abs(max_loss)},
                {"type": "recovery", "time": recovery_time}
            ]
        )
        
        return result
    
    def _calculate_resilience(
        self,
        drawdown: float,
        loss: float,
        recovery: float,
        var_break: float,
        expected_shortfall: float
    ) -> float:
        """Calcule le score de résilience."""
        # Scores individuels
        drawdown_score = max(0, 1 - drawdown / 0.5)
        loss_score = max(0, 1 - loss / 1000)
        recovery_score = max(0, 1 - recovery / 100)
        var_score = max(0, 1 - abs(var_break) / 0.1)
        es_score = max(0, 1 - abs(expected_shortfall) / 0.15)
        
        # Score pondéré
        weights = {
            "drawdown": 0.25,
            "loss": 0.20,
            "recovery": 0.20,
            "var": 0.20,
            "es": 0.15
        }
        
        resilience = (
            drawdown_score * weights["drawdown"] +
            loss_score * weights["loss"] +
            recovery_score * weights["recovery"] +
            var_score * weights["var"] +
            es_score * weights["es"]
        )
        
        return min(1.0, max(0.0, resilience))
    
    # ========== MÉTHODES PRIVÉES - MÉTRIQUES ==========
    
    async def _calculate_stress_metrics(self, scenario: StressScenario, result: StressTestResult) -> List[StressMetric]:
        """Calcule les métriques de stress."""
        metrics = []
        
        # Métriques de base
        metric_configs = [
            ("max_drawdown", result.max_drawdown, 0.1),
            ("max_loss", result.max_loss, 100),
            ("recovery_time", result.recovery_time, 30),
            ("var_break", result.var_break, 0.05),
            ("sharpe_ratio", result.sharpe_ratio, 1.0),
            ("resilience_score", result.resilience_score, 0.7)
        ]
        
        for name, value, threshold in metric_configs:
            status = "pass"
            if value > threshold * 1.5:
                status = "critical"
            elif value > threshold * 1.2:
                status = "fail"
            elif value > threshold * 1.1:
                status = "warning"
            
            metric = StressMetric(
                name=name,
                value=value,
                threshold=threshold,
                status=status,
                metadata={"scenario_id": scenario.scenario_id}
            )
            metrics.append(metric)
        
        # Stockage des métriques
        with self._metrics_lock:
            for metric in metrics:
                self._metrics[metric.name].append(metric)
        
        return metrics
    
    # ========== MÉTHODES PRIVÉES - ANALYSE ==========
    
    def _analyze_monte_carlo_results(self, results: List[StressTestResult]) -> Dict[str, Any]:
        """Analyse les résultats Monte Carlo."""
        if not results:
            return {"status": "no_results"}
        
        # Statistiques
        resilience_scores = [r.resilience_score for r in results]
        drawdowns = [r.max_drawdown for r in results]
        losses = [r.max_loss for r in results]
        
        analysis = {
            "num_simulations": len(results),
            "avg_resilience": np.mean(resilience_scores),
            "std_resilience": np.std(resilience_scores),
            "min_resilience": np.min(resilience_scores),
            "max_resilience": np.max(resilience_scores),
            "avg_drawdown": np.mean(drawdowns),
            "avg_loss": np.mean(losses),
            "percentile_5": np.percentile(resilience_scores, 5),
            "percentile_95": np.percentile(resilience_scores, 95),
            "success_rate": sum(1 for r in results if r.success) / len(results)
        }
        
        # Distribution
        analysis["resilience_distribution"] = {
            "0-0.2": sum(1 for s in resilience_scores if s < 0.2),
            "0.2-0.4": sum(1 for s in resilience_scores if 0.2 <= s < 0.4),
            "0.4-0.6": sum(1 for s in resilience_scores if 0.4 <= s < 0.6),
            "0.6-0.8": sum(1 for s in resilience_scores if 0.6 <= s < 0.8),
            "0.8-1.0": sum(1 for s in resilience_scores if s >= 0.8)
        }
        
        return analysis
    
    # ========== MÉTHODES PRIVÉES - SCÉNARIOS HISTORIQUES ==========
    
    async def _load_historical_scenarios(self) -> None:
        """Charge les scénarios historiques."""
        historical_scenarios = [
            {
                "name": "2008 Financial Crisis",
                "description": "Simulation of the 2008 financial crisis",
                "scenario_type": ScenarioType.HISTORICAL.value,
                "stress_type": StressType.MARKET_SHOCK.value,
                "severity": StressSeverity.EXTREME.value,
                "duration": 3600,
                "parameters": {
                    "volatility": 0.5,
                    "drawdown": 0.4,
                    "correlation_break": True
                }
            },
            {
                "name": "2020 COVID Crash",
                "description": "Simulation of the March 2020 COVID crash",
                "scenario_type": ScenarioType.HISTORICAL.value,
                "stress_type": StressType.FLASH_CRASH.value,
                "severity": StressSeverity.SEVERE.value,
                "duration": 1800,
                "parameters": {
                    "volatility": 0.3,
                    "drawdown": 0.3,
                    "recovery_time": 300
                }
            },
            {
                "name": "2022 Volatility Crisis",
                "description": "Simulation of the 2022 volatility crisis",
                "scenario_type": ScenarioType.HISTORICAL.value,
                "stress_type": StressType.VOLATILITY_SPIKE.value,
                "severity": StressSeverity.MODERATE.value,
                "duration": 1200,
                "parameters": {
                    "volatility": 0.2,
                    "duration": 1200
                }
            }
        ]
        
        for config in historical_scenarios:
            try:
                await self.create_scenario(config)
            except Exception as e:
                logger.error(f"Error loading historical scenario {config['name']}: {e}")
        
        logger.info(f"Loaded {len(historical_scenarios)} historical scenarios")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _monitoring_loop(self) -> None:
        """Boucle de monitoring des stress tests."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Vérification des métriques critiques
                with self._metrics_lock:
                    for metric_name, metrics in self._metrics.items():
                        if metrics:
                            latest = metrics[-1]
                            if latest.status == "critical":
                                logger.warning(f"Critical stress metric: {metric_name} = {latest.value}")
                                
                                # Envoi d'une alerte
                                if self.data_manager:
                                    await self.data_manager.store(
                                        f"alert:stress:{metric_name}",
                                        {
                                            "metric": metric_name,
                                            "value": latest.value,
                                            "threshold": latest.threshold,
                                            "status": latest.status
                                        },
                                        DataType.ALERT
                                    )
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Nettoyage des anciens résultats
                with self._results_lock:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                    old_results = [
                        rid for rid, result in self._results.items()
                        if result.timestamp < cutoff
                    ]
                    for rid in old_results:
                        del self._results[rid]
                
                logger.debug(f"Cleaned up {len(old_results)} old results")
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_scenario(self, scenario_id: str) -> Optional[StressScenario]:
        """Récupère un scénario de stress."""
        with self._scenarios_lock:
            return self._scenarios.get(scenario_id)
    
    async def get_scenarios(self) -> List[StressScenario]:
        """Récupère les scénarios de stress."""
        with self._scenarios_lock:
            return list(self._scenarios.values())
    
    async def get_result(self, result_id: str) -> Optional[StressTestResult]:
        """Récupère un résultat de stress test."""
        with self._results_lock:
            return self._results.get(result_id)
    
    async def get_results(self, limit: int = 100) -> List[StressTestResult]:
        """Récupère les résultats de stress test."""
        with self._results_lock:
            results = list(self._results.values())
            return sorted(results, key=lambda r: r.timestamp, reverse=True)[:limit]
    
    async def get_metrics(self, metric_name: Optional[str] = None) -> List[StressMetric]:
        """Récupère les métriques de stress."""
        with self._metrics_lock:
            if metric_name:
                return self._metrics.get(metric_name, [])
            return [m for metrics in self._metrics.values() for m in metrics]
    
    async def generate_report(self, scenario_id: str) -> Dict[str, Any]:
        """Génère un rapport de stress test."""
        # Récupération du scénario
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            return {"error": "Scenario not found"}
        
        # Récupération des résultats
        with self._results_lock:
            results = [r for r in self._results.values() if r.scenario_id == scenario_id]
        
        if not results:
            return {"error": "No results found for this scenario"}
        
        # Génération du rapport
        report = {
            "scenario": scenario.to_dict(),
            "results": [r.to_dict() for r in results],
            "summary": {
                "total_tests": len(results),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
                "avg_resilience": np.mean([r.resilience_score for r in results]),
                "avg_drawdown": np.mean([r.max_drawdown for r in results]),
                "avg_recovery": np.mean([r.recovery_time for r in results])
            },
            "worst_case": max(results, key=lambda r: r.max_loss).to_dict() if results else None,
            "best_case": max(results, key=lambda r: r.resilience_score).to_dict() if results else None
        }
        
        # Stockage du rapport
        if self.data_manager:
            await self.data_manager.store(
                f"stress:report:{scenario_id}",
                report,
                DataType.REPORT
            )
        
        return report
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._scenarios_lock:
            self._stats["total_scenarios"] = len(self._scenarios)
        with self._results_lock:
            self._stats["total_results"] = len(self._results)
        
        return self._stats.copy()


# ============== FACTORY ==============

class StressTesterFactory:
    """Factory pour créer des testeurs de stress."""
    
    @staticmethod
    async def create_tester(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> StressTester:
        """Crée un testeur de stress."""
        tester = StressTester(
            data_manager=data_manager,
            config=config
        )
        await tester.start()
        return tester


# ============== EXPORT ==============

__all__ = [
    "StressType",
    "ScenarioType",
    "StressSeverity",
    "StressScenario",
    "StressTestResult",
    "StressMetric",
    "StressTesterInterface",
    "StressTester",
    "StressTesterFactory"
]

# blockchain/defi/defi_risk.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module DeFi Risk - Gestion des Risques DeFi

Ce module implémente un système complet de gestion des risques pour les
opérations DeFi, incluant l'analyse des risques, le monitoring, les alertes,
et les mécanismes de mitigation.

Fonctionnalités principales:
- Analyse des risques de protocole
- Analyse des risques de position
- Analyse des risques de marché
- Monitoring en temps réel
- Alertes de risque
- Mitigation des risques
- Stress testing
- Analyse de corrélation
- Calcul des métriques de risque (VaR, CVaR, Sharpe, etc.)
- Gestion des limites de risque
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from functools import lru_cache, wraps
import statistics
import math

import numpy as np
from scipy import stats as scipy_stats

# Import des modules internes
try:
    from ..core.exceptions import DeFiError, RiskError, ValidationError
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
    from .defi_config import DeFiConfigManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import DeFiError, RiskError, ValidationError
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
    from .defi_config import DeFiConfigManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class RiskCategory(Enum):
    """Catégories de risque"""
    PROTOCOL = "protocol"
    MARKET = "market"
    LIQUIDITY = "liquidity"
    COUNTERPARTY = "counterparty"
    OPERATIONAL = "operational"
    REGULATORY = "regulatory"
    SYSTEMIC = "systemic"


class RiskEventType(Enum):
    """Types d'événements de risque"""
    HEALTH_FACTOR_DROP = "health_factor_drop"
    LIQUIDATION_WARNING = "liquidation_warning"
    LIQUIDATION = "liquidation"
    PRICE_CRASH = "price_crash"
    PROTOCOL_VULNERABILITY = "protocol_vulnerability"
    GAS_SPIKE = "gas_spike"
    TVL_DROP = "tvl_drop"
    APY_DROP = "apy_drop"
    POSITION_IMBALANCE = "position_imbalance"
    CORRELATION_BREAK = "correlation_break"


class RiskSeverity(Enum):
    """Sévérité du risque"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    CATASTROPHIC = "catastrophic"


@dataclass
class RiskMetric:
    """Métrique de risque"""
    metric_id: str
    category: RiskCategory
    name: str
    value: float
    threshold: float
    severity: RiskSeverity
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "metric_id": self.metric_id,
            "category": self.category.value,
            "name": self.name,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def is_exceeded(self) -> bool:
        """Vérifie si la métrique dépasse le seuil"""
        return self.value > self.threshold


@dataclass
class RiskEvent:
    """Événement de risque"""
    event_id: str
    event_type: RiskEventType
    severity: RiskSeverity
    position_id: Optional[str] = None
    protocol: Optional[str] = None
    chain: Optional[str] = None
    value: Optional[Decimal] = None
    threshold: Optional[Decimal] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "position_id": self.position_id,
            "protocol": self.protocol,
            "chain": self.chain,
            "value": str(self.value) if self.value else None,
            "threshold": str(self.threshold) if self.threshold else None,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class RiskProfile:
    """Profil de risque"""
    profile_id: str
    positions: List[Position]
    total_value_usd: Decimal
    risk_score: float
    var_95: Decimal  # Value at Risk 95%
    cvar_95: Decimal  # Conditional VaR 95%
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: Decimal
    concentration_score: float
    correlation_matrix: Dict[str, float]
    metrics: List[RiskMetric]
    events: List[RiskEvent]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "profile_id": self.profile_id,
            "total_value_usd": str(self.total_value_usd),
            "risk_score": self.risk_score,
            "var_95": str(self.var_95),
            "cvar_95": str(self.cvar_95),
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": str(self.max_drawdown),
            "concentration_score": self.concentration_score,
            "correlation_matrix": self.correlation_matrix,
            "metrics": [m.to_dict() for m in self.metrics],
            "events": [e.to_dict() for e in self.events],
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class DeFiRiskManager:
    """
    Gestionnaire de risques DeFi
    """

    # Paramètres de risque par défaut
    DEFAULT_RISK_PARAMETERS = {
        "max_health_factor": Decimal("3.0"),
        "min_health_factor": Decimal("1.2"),
        "liquidation_warning": Decimal("1.3"),
        "max_leverage": Decimal("3.0"),
        "max_concentration": 0.3,  # 30% max par position
        "var_confidence": 0.95,
        "max_drawdown": Decimal("0.2"),  # 20% max drawdown
        "sharpe_minimum": 0.5,
        "sortino_minimum": 0.3,
        "correlation_threshold": 0.7,
        "price_volatility_warning": 0.3,
        "price_volatility_critical": 0.5,
        "tvl_drop_warning": 0.1,
        "tvl_drop_critical": 0.2,
        "apy_drop_warning": 0.2,
        "apy_drop_critical": 0.4,
    }

    def __init__(
        self,
        config: Dict[str, Any],
        defi_manager: Any,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de risques

        Args:
            config: Configuration
            defi_manager: Gestionnaire DeFi
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.defi_manager = defi_manager
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # Paramètres de risque
        self.risk_params = self.DEFAULT_RISK_PARAMETERS.copy()
        self.risk_params.update(config.get("risk_parameters", {}))

        # États internes
        self._profiles: Dict[str, RiskProfile] = {}
        self._metrics: Dict[str, RiskMetric] = {}
        self._events: List[RiskEvent] = []
        self._historical_events: List[RiskEvent] = []
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            backoff=2.0,
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Alertes
        self._alert_callbacks: List[Callable] = []

        # Historique des prix (simulé)
        self._price_history: Dict[str, List[Decimal]] = defaultdict(list)
        self._max_history_length = 1000

        logger.info("DeFiRiskManager initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def analyze_risk(
        self,
        positions: List[Position],
        user: Optional[str] = None,
    ) -> RiskProfile:
        """
        Analyse le risque d'un portefeuille de positions

        Args:
            positions: Liste des positions
            user: Adresse de l'utilisateur (optionnel)

        Returns:
            Profil de risque
        """
        profile_id = f"rp_{uuid.uuid4().hex[:8]}"
        logger.info(f"Analyse de risque {profile_id} pour {len(positions)} positions")

        try:
            # Calcul de la valeur totale
            total_value = sum(p.value_usd for p in positions)

            # Métriques de risque
            metrics = await self._calculate_risk_metrics(positions, total_value)

            # Calcul des métriques avancées
            var_95 = await self._calculate_var(positions, 0.95)
            cvar_95 = await self._calculate_cvar(positions, 0.95)
            sharpe = await self._calculate_sharpe_ratio(positions)
            sortino = await self._calculate_sortino_ratio(positions)
            max_drawdown = await self._calculate_max_drawdown(positions)
            concentration = await self._calculate_concentration(positions)
            correlation = await self._calculate_correlation(positions)

            # Score de risque global
            risk_score = self._calculate_risk_score(
                metrics=metrics,
                var=var_95,
                max_drawdown=max_drawdown,
                concentration=concentration,
            )

            # Détection des événements de risque
            events = await self._detect_risk_events(positions, metrics)

            # Enregistrement des événements
            for event in events:
                self._events.append(event)

            profile = RiskProfile(
                profile_id=profile_id,
                positions=positions,
                total_value_usd=total_value,
                risk_score=risk_score,
                var_95=var_95,
                cvar_95=cvar_95,
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                max_drawdown=max_drawdown,
                concentration_score=concentration,
                correlation_matrix=correlation,
                metrics=metrics,
                events=events,
                timestamp=datetime.now(),
            )

            # Stockage
            self._profiles[profile_id] = profile

            # Métriques
            self.metrics.record_gauge("defi_risk_score", risk_score)
            self.metrics.record_gauge("defi_var_95", float(var_95))
            self.metrics.record_gauge("defi_sharpe_ratio", sharpe)
            self.metrics.record_gauge("defi_concentration", concentration)

            # Alertes
            if risk_score > 0.7:
                await self._send_alert({
                    "type": "high_risk_score",
                    "score": risk_score,
                    "threshold": 0.7,
                    "severity": "critical",
                })

            return profile

        except Exception as e:
            logger.error(f"Erreur d'analyse de risque: {e}")
            raise RiskError(f"Erreur d'analyse de risque: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def monitor_risk(
        self,
        profile_id: str,
        interval: int = 60,
    ) -> None:
        """
        Surveille le risque d'un profil en continu

        Args:
            profile_id: ID du profil
            interval: Intervalle en secondes
        """
        logger.info(f"Surveillance du risque {profile_id}")

        while True:
            try:
                profile = self._profiles.get(profile_id)
                if not profile:
                    logger.warning(f"Profil {profile_id} non trouvé")
                    break

                # Mise à jour des métriques
                updated_metrics = await self._update_risk_metrics(profile)

                # Vérification des seuils
                for metric in updated_metrics:
                    if metric.is_exceeded():
                        await self._send_alert({
                            "type": "risk_threshold_exceeded",
                            "metric": metric.name,
                            "value": metric.value,
                            "threshold": metric.threshold,
                            "severity": metric.severity.value,
                        })

                # Mise à jour du profil
                profile.metrics = updated_metrics
                profile.timestamp = datetime.now()

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de surveillance du risque: {e}")
                await asyncio.sleep(interval * 2)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def stress_test(
        self,
        positions: List[Position],
        scenarios: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Effectue un stress test sur les positions

        Args:
            positions: Liste des positions
            scenarios: Liste des scénarios de stress

        Returns:
            Résultats du stress test
        """
        logger.info(f"Stress test de {len(positions)} positions")

        try:
            results = {
                "scenarios": [],
                "worst_case": None,
                "best_case": None,
            }

            for scenario in scenarios:
                # Application du scénario
                scenario_result = await self._apply_stress_scenario(
                    positions, scenario
                )
                results["scenarios"].append(scenario_result)

            # Identification du pire cas
            worst = min(results["scenarios"], key=lambda x: x["value_after"])
            results["worst_case"] = worst

            best = max(results["scenarios"], key=lambda x: x["value_after"])
            results["best_case"] = best

            return results

        except Exception as e:
            logger.error(f"Erreur de stress test: {e}")
            raise RiskError(f"Erreur de stress test: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_risk_profile(self, profile_id: str) -> Optional[RiskProfile]:
        """
        Obtient un profil de risque

        Args:
            profile_id: ID du profil

        Returns:
            Profil de risque ou None
        """
        return self._profiles.get(profile_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_risk_metrics(
        self,
        protocol: Optional[str] = None,
        chain: Optional[str] = None,
    ) -> List[RiskMetric]:
        """
        Obtient les métriques de risque

        Args:
            protocol: Filtrer par protocole
            chain: Filtrer par chaîne

        Returns:
            Liste des métriques
        """
        metrics = list(self._metrics.values())

        if protocol:
            metrics = [m for m in metrics if m.metadata.get("protocol") == protocol]

        if chain:
            metrics = [m for m in metrics if m.metadata.get("chain") == chain]

        return metrics

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_risk_events(
        self,
        severity: Optional[RiskSeverity] = None,
        protocol: Optional[str] = None,
        chain: Optional[str] = None,
        limit: int = 100,
    ) -> List[RiskEvent]:
        """
        Obtient les événements de risque

        Args:
            severity: Sévérité minimum
            protocol: Filtrer par protocole
            chain: Filtrer par chaîne
            limit: Nombre maximum

        Returns:
            Liste des événements
        """
        events = self._events.copy()

        if severity:
            severity_order = [e.value for e in RiskSeverity]
            min_index = severity_order.index(severity.value)
            events = [
                e for e in events
                if severity_order.index(e.severity.value) >= min_index
            ]

        if protocol:
            events = [e for e in events if e.protocol == protocol]

        if chain:
            events = [e for e in events if e.chain == chain]

        # Trier par date (plus récent en premier)
        events.sort(key=lambda x: x.timestamp, reverse=True)

        return events[:limit]

    # ============================================================
    # MÉTHODES DE CALCUL DES MÉTRIQUES
    # ============================================================

    async def _calculate_risk_metrics(
        self,
        positions: List[Position],
        total_value: Decimal,
    ) -> List[RiskMetric]:
        """Calcule les métriques de risque"""
        metrics = []

        # Health factor (pour les positions avec dette)
        for pos in positions:
            if pos.position_type == PositionType.DEBT:
                health_factor = Decimal(str(pos.metadata.get("health_factor", "999")))
                metrics.append(RiskMetric(
                    metric_id=f"hf_{uuid.uuid4().hex[:8]}",
                    category=RiskCategory.PROTOCOL,
                    name="health_factor",
                    value=float(health_factor),
                    threshold=float(self.risk_params["min_health_factor"]),
                    severity=RiskSeverity.HIGH if health_factor < Decimal("1.1") else RiskSeverity.MEDIUM,
                    timestamp=datetime.now(),
                    metadata={
                        "position_id": pos.position_id,
                        "protocol": pos.protocol,
                        "chain": pos.chain,
                        "token": pos.token,
                    },
                ))

        # Concentration
        if total_value > 0:
            for pos in positions:
                concentration = float(pos.value_usd / total_value)
                metrics.append(RiskMetric(
                    metric_id=f"conc_{uuid.uuid4().hex[:8]}",
                    category=RiskCategory.MARKET,
                    name="concentration",
                    value=concentration,
                    threshold=self.risk_params["max_concentration"],
                    severity=RiskSeverity.MEDIUM if concentration > 0.3 else RiskSeverity.LOW,
                    timestamp=datetime.now(),
                    metadata={
                        "position_id": pos.position_id,
                        "token": pos.token,
                    },
                ))

        # Volatilité
        for pos in positions:
            volatility = await self._calculate_volatility(pos.token, pos.chain)
            metrics.append(RiskMetric(
                metric_id=f"vol_{uuid.uuid4().hex[:8]}",
                category=RiskCategory.MARKET,
                name="volatility",
                value=float(volatility),
                threshold=self.risk_params["price_volatility_warning"],
                severity=RiskSeverity.HIGH if volatility > Decimal("0.5") else RiskSeverity.MEDIUM,
                timestamp=datetime.now(),
                metadata={
                    "position_id": pos.position_id,
                    "token": pos.token,
                    "chain": pos.chain,
                },
            ))

        return metrics

    async def _calculate_var(
        self,
        positions: List[Position],
        confidence: float = 0.95,
    ) -> Decimal:
        """Calcule la Value at Risk"""
        if not positions:
            return Decimal("0")

        # Simulé - dans la réalité, on utiliserait des données historiques
        # et une simulation Monte Carlo
        returns = []
        for pos in positions:
            # Simuler des rendements
            volatility = await self._calculate_volatility(pos.token, pos.chain)
            mean_return = 0.0001  # 0.01% par jour
            daily_return = np.random.normal(mean_return, float(volatility))
            returns.append(daily_return * float(pos.value_usd))

        # Calcul du VaR
        if returns:
            var = np.percentile(returns, (1 - confidence) * 100)
            return Decimal(str(abs(var)))

        return Decimal("0")

    async def _calculate_cvar(
        self,
        positions: List[Position],
        confidence: float = 0.95,
    ) -> Decimal:
        """Calcule la Conditional Value at Risk"""
        if not positions:
            return Decimal("0")

        # Simulé
        var = await self._calculate_var(positions, confidence)
        # CVaR est généralement plus élevé que VaR
        return var * Decimal("1.5")

    async def _calculate_sharpe_ratio(
        self,
        positions: List[Position],
    ) -> float:
        """Calcule le ratio de Sharpe"""
        if not positions:
            return 0.0

        # Simulé
        returns = []
        for pos in positions:
            apy = float(pos.apy) if pos.apy else 0.0
            volatility = float(await self._calculate_volatility(pos.token, pos.chain))
            if volatility > 0:
                returns.append(apy / volatility)

        return statistics.mean(returns) if returns else 0.0

    async def _calculate_sortino_ratio(
        self,
        positions: List[Position],
    ) -> float:
        """Calcule le ratio de Sortino"""
        if not positions:
            return 0.0

        # Simulé
        sharpe = await self._calculate_sharpe_ratio(positions)
        return sharpe * 1.2  # Sortino est généralement plus élevé

    async def _calculate_max_drawdown(
        self,
        positions: List[Position],
    ) -> Decimal:
        """Calcule le drawdown maximum"""
        if not positions:
            return Decimal("0")

        # Simulé - dans la réalité, on utiliserait des données historiques
        values = []
        for pos in positions:
            # Simuler des valeurs historiques
            current_value = float(pos.value_usd)
            # Variation aléatoire
            for _ in range(30):
                change = np.random.normal(0, 0.02)  # 2% de volatilité
                value = current_value * (1 + change)
                values.append(value)

        if not values:
            return Decimal("0")

        # Calcul du drawdown
        peak = values[0]
        max_drawdown = 0.0
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return Decimal(str(max_drawdown))

    async def _calculate_concentration(
        self,
        positions: List[Position],
    ) -> float:
        """Calcule le score de concentration"""
        if not positions:
            return 0.0

        total_value = sum(p.value_usd for p in positions)
        if total_value == 0:
            return 0.0

        # HHI (Herfindahl-Hirschman Index)
        hhi = 0.0
        for pos in positions:
            share = float(pos.value_usd / total_value)
            hhi += share ** 2

        return hhi

    async def _calculate_correlation(
        self,
        positions: List[Position],
    ) -> Dict[str, float]:
        """Calcule la matrice de corrélation"""
        if len(positions) < 2:
            return {}

        # Simulé - dans la réalité, on utiliserait des données historiques
        correlations = {}
        tokens = [p.token for p in positions]

        for i, token1 in enumerate(tokens):
            for j, token2 in enumerate(tokens):
                if i < j:
                    key = f"{token1}:{token2}"
                    # Corrélation simulée
                    if token1 == token2:
                        correlation = 1.0
                    elif token1 in ["USDC", "USDT", "DAI"] and token2 in ["USDC", "USDT", "DAI"]:
                        correlation = 0.9
                    elif "ETH" in token1 or "ETH" in token2:
                        correlation = 0.6
                    else:
                        correlation = 0.3
                    correlations[key] = correlation

        return correlations

    async def _calculate_volatility(self, token: str, chain: str) -> Decimal:
        """Calcule la volatilité d'un token"""
        # Simulé - dans la réalité, on utiliserait des données historiques
        volatilities = {
            "USDC": Decimal("0.01"),
            "USDT": Decimal("0.01"),
            "DAI": Decimal("0.015"),
            "ETH": Decimal("0.35"),
            "WETH": Decimal("0.35"),
            "WBTC": Decimal("0.30"),
            "MATIC": Decimal("0.45"),
            "AVAX": Decimal("0.50"),
        }
        return volatilities.get(token, Decimal("0.20"))

    def _calculate_risk_score(
        self,
        metrics: List[RiskMetric],
        var: Decimal,
        max_drawdown: Decimal,
        concentration: float,
    ) -> float:
        """Calcule le score de risque global"""
        # Score basé sur les métriques
        scores = []

        # Health factor
        hf_metrics = [m for m in metrics if m.name == "health_factor"]
        if hf_metrics:
            hf = hf_metrics[0]
            if hf.value < 1.1:
                scores.append(0.9)
            elif hf.value < 1.2:
                scores.append(0.7)
            elif hf.value < 1.5:
                scores.append(0.4)
            else:
                scores.append(0.1)

        # Concentration
        scores.append(min(1.0, concentration * 2))

        # VaR
        var_score = min(1.0, float(var) / 1000)
        scores.append(var_score)

        # Max drawdown
        drawdown_score = min(1.0, float(max_drawdown) * 2)
        scores.append(drawdown_score)

        # Score final
        if scores:
            return sum(scores) / len(scores)

        return 0.0

    # ============================================================
    # MÉTHODES DE DÉTECTION DES ÉVÉNEMENTS
    # ============================================================

    async def _detect_risk_events(
        self,
        positions: List[Position],
        metrics: List[RiskMetric],
    ) -> List[RiskEvent]:
        """Détecte les événements de risque"""
        events = []

        # Vérification du health factor
        for metric in metrics:
            if metric.name == "health_factor" and metric.is_exceeded():
                events.append(RiskEvent(
                    event_id=f"re_{uuid.uuid4().hex[:8]}",
                    event_type=RiskEventType.HEALTH_FACTOR_DROP,
                    severity=metric.severity,
                    position_id=metric.metadata.get("position_id"),
                    protocol=metric.metadata.get("protocol"),
                    chain=metric.metadata.get("chain"),
                    value=Decimal(str(metric.value)),
                    threshold=Decimal(str(metric.threshold)),
                    message=f"Health factor trop bas: {metric.value:.2f}",
                    metadata=metric.metadata,
                ))

        # Vérification du drawdown
        for pos in positions:
            if pos.value_usd > 0:
                drawdown = await self._calculate_max_drawdown([pos])
                if drawdown > self.risk_params["max_drawdown"]:
                    events.append(RiskEvent(
                        event_id=f"re_{uuid.uuid4().hex[:8]}",
                        event_type=RiskEventType.POSITION_IMBALANCE,
                        severity=RiskSeverity.HIGH,
                        position_id=pos.position_id,
                        protocol=pos.protocol,
                        chain=pos.chain,
                        value=drawdown,
                        threshold=self.risk_params["max_drawdown"],
                        message=f"Drawdown élevé: {drawdown:.2%}",
                        metadata={"position": pos.to_dict()},
                    ))

        # Vérification de la concentration
        for metric in metrics:
            if metric.name == "concentration" and metric.is_exceeded():
                events.append(RiskEvent(
                    event_id=f"re_{uuid.uuid4().hex[:8]}",
                    event_type=RiskEventType.POSITION_IMBALANCE,
                    severity=metric.severity,
                    position_id=metric.metadata.get("position_id"),
                    protocol=metric.metadata.get("protocol"),
                    chain=metric.metadata.get("chain"),
                    value=Decimal(str(metric.value)),
                    threshold=Decimal(str(metric.threshold)),
                    message=f"Concentration trop élevée: {metric.value:.2%}",
                    metadata=metric.metadata,
                ))

        return events

    # ============================================================
    # MÉTHODES DE STRESS TEST
    # ============================================================

    async def _apply_stress_scenario(
        self,
        positions: List[Position],
        scenario: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Applique un scénario de stress"""
        scenario_type = scenario.get("type", "price_shock")
        impact = scenario.get("impact", Decimal("0.2"))

        result = {
            "scenario": scenario,
            "value_before": sum(p.value_usd for p in positions),
            "value_after": Decimal("0"),
            "impact": Decimal("0"),
        }

        # Application du stress
        stressed_positions = []
        for pos in positions:
            if scenario_type == "price_shock":
                # Choc de prix
                shock_factor = Decimal("1") - impact
                new_value = pos.value_usd * shock_factor
                stressed_positions.append({
                    "position": pos,
                    "value_after": new_value,
                })

            elif scenario_type == "liquidation":
                # Scénario de liquidation
                if pos.position_type == PositionType.DEBT:
                    new_value = Decimal("0")
                else:
                    new_value = pos.value_usd * Decimal("0.8")
                stressed_positions.append({
                    "position": pos,
                    "value_after": new_value,
                })

            else:
                # Scénario générique
                new_value = pos.value_usd * (Decimal("1") - impact)
                stressed_positions.append({
                    "position": pos,
                    "value_after": new_value,
                })

        # Calcul des valeurs après stress
        total_after = sum(p["value_after"] for p in stressed_positions)
        result["value_after"] = total_after
        result["impact"] = (result["value_before"] - total_after) / result["value_before"]

        # Détails des positions
        result["positions"] = [
            {
                "position_id": p["position"].position_id,
                "token": p["position"].token,
                "value_before": str(p["position"].value_usd),
                "value_after": str(p["value_after"]),
            }
            for p in stressed_positions
        ]

        return result

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def _update_risk_metrics(self, profile: RiskProfile) -> List[RiskMetric]:
        """Met à jour les métriques de risque"""
        updated_metrics = []

        for metric in profile.metrics:
            if metric.name == "health_factor":
                # Mise à jour du health factor
                position = next(
                    (p for p in profile.positions if p.position_id == metric.metadata.get("position_id")),
                    None
                )
                if position and position.metadata.get("health_factor"):
                    new_value = float(position.metadata["health_factor"])
                    metric.value = new_value
                    metric.timestamp = datetime.now()
                    updated_metrics.append(metric)

            elif metric.name == "concentration":
                # Mise à jour de la concentration
                new_value = float(await self._calculate_concentration(profile.positions))
                metric.value = new_value
                metric.timestamp = datetime.now()
                updated_metrics.append(metric)

        return updated_metrics

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    def add_alert_callback(self, callback: Callable) -> None:
        """Ajoute un callback pour les alertes"""
        self._alert_callbacks.append(callback)

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire de risques"""
        return {
            "total_profiles": len(self._profiles),
            "total_metrics": len(self._metrics),
            "total_events": len(self._events),
            "critical_events": len([e for e in self._events if e.severity == RiskSeverity.CRITICAL]),
            "high_events": len([e for e in self._events if e.severity == RiskSeverity.HIGH]),
            "average_risk_score": self._calculate_average_risk_score(),
        }

    def _calculate_average_risk_score(self) -> float:
        """Calcule le score de risque moyen"""
        if not self._profiles:
            return 0.0

        scores = [p.risk_score for p in self._profiles.values()]
        return sum(scores) / len(scores)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources DeFiRiskManager...")

        self._profiles.clear()
        self._metrics.clear()
        self._events.clear()
        self._historical_events.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_defi_risk_manager(
    config: Dict[str, Any],
    defi_manager: Any,
    **kwargs,
) -> DeFiRiskManager:
    """
    Crée une instance de DeFiRiskManager

    Args:
        config: Configuration
        defi_manager: Gestionnaire DeFi
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiRiskManager
    """
    return DeFiRiskManager(
        config=config,
        defi_manager=defi_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de DeFiRiskManager"""
    # Configuration
    config = {
        "risk_parameters": {
            "min_health_factor": "1.2",
            "max_concentration": 0.3,
            "max_drawdown": "0.2",
        },
    }

    # DeFi manager (simplifié)
    class SimpleDeFiManager:
        pass

    defi_manager = SimpleDeFiManager()

    # Création du gestionnaire de risques
    risk_manager = create_defi_risk_manager(
        config=config,
        defi_manager=defi_manager,
    )

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE DE RISQUE: {alert}")

    risk_manager.add_alert_callback(alert_callback)

    # Création de positions de test
    positions = [
        Position(
            position_id=f"pos_{i}",
            position_type=PositionType.SUPPLY,
            protocol="aave_v3",
            chain="ethereum",
            token=token,
            amount=Decimal(str(1000)),
            value_usd=Decimal(str(1000)),
            apy=Decimal("0.05"),
            timestamp=datetime.now(),
            metadata={"health_factor": "1.5"},
        )
        for i, token in enumerate(["USDC", "ETH", "WBTC"])
    ]

    # Analyse du risque
    profile = await risk_manager.analyze_risk(positions)
    print(f"Profil de risque: {profile.to_dict()}")

    # Stress test
    scenarios = [
        {"type": "price_shock", "impact": Decimal("0.2")},
        {"type": "price_shock", "impact": Decimal("0.4")},
        {"type": "liquidation"},
    ]

    stress_results = await risk_manager.stress_test(positions, scenarios)
    print(f"Stress test: {stress_results}")

    # Obtention des événements de risque
    events = await risk_manager.get_risk_events(limit=5)
    print(f"Événements de risque récents: {len(events)}")

    # Statistiques
    stats = risk_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await risk_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

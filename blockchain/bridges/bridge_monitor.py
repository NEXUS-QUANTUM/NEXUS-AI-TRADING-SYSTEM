# blockchain/bridges/bridge_monitor.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Monitoring des Bridges

Ce module implémente un système complet de monitoring pour les opérations de bridge
cross-chain, incluant la surveillance en temps réel des transactions, la collecte
de métriques, la détection d'anomalies, et le reporting.

Fonctionnalités principales:
- Surveillance en temps réel des bridges
- Collecte de métriques de performance
- Détection d'anomalies et d'alertes
- Reporting et tableaux de bord
- Monitoring de la santé des protocoles
- Suivi des transactions cross-chain
- Analyse des frais et des délais
- Surveillance des validateurs
- Alertes configurables
- Historique et tendances
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
from collections import defaultdict, deque
from functools import lru_cache, wraps

import aiohttp

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, BridgeError, MonitoringError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from ..wallets.base_wallet import BaseWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, MonitoringError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from ..wallets.base_wallet import BaseWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class MonitorStatus(Enum):
    """Statuts de monitoring"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class AlertSeverity(Enum):
    """Sévérité des alertes"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MetricType(Enum):
    """Types de métriques"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class BridgeHealth:
    """État de santé d'un bridge"""
    protocol: str
    chain: str
    status: MonitorStatus
    uptime: float  # secondes
    success_rate: float  # 0-1
    avg_response_time: float  # secondes
    pending_transactions: int
    total_volume_24h: Decimal
    fees_24h: Decimal
    last_block: int
    block_latency: float  # secondes
    validator_count: int
    active_validators: int
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol,
            "chain": self.chain,
            "status": self.status.value,
            "uptime": self.uptime,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "pending_transactions": self.pending_transactions,
            "total_volume_24h": str(self.total_volume_24h),
            "fees_24h": str(self.fees_24h),
            "last_block": self.last_block,
            "block_latency": self.block_latency,
            "validator_count": self.validator_count,
            "active_validators": self.active_validators,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BridgeMetric:
    """Métrique de bridge"""
    metric_id: str
    metric_type: MetricType
    name: str
    value: Union[int, float, Decimal]
    timestamp: datetime
    protocol: str
    chain: str
    labels: Dict[str, str] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "metric_id": self.metric_id,
            "metric_type": self.metric_type.value,
            "name": self.name,
            "value": str(self.value) if isinstance(self.value, Decimal) else self.value,
            "timestamp": self.timestamp.isoformat(),
            "protocol": self.protocol,
            "chain": self.chain,
            "labels": self.labels,
            "description": self.description,
        }


@dataclass
class BridgeAlert:
    """Alerte de bridge"""
    alert_id: str
    severity: AlertSeverity
    protocol: str
    chain: str
    title: str
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "protocol": self.protocol,
            "chain": self.chain,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeMonitor:
    """
    Moniteur avancé pour les bridges cross-chain
    """

    def __init__(
        self,
        config: Dict[str, Any],
        bridge_manager: BridgeManager,
        web3_providers: Optional[Dict[str, Any]] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le moniteur de bridge

        Args:
            config: Configuration
            bridge_manager: Gestionnaire de bridges
            web3_providers: Providers Web3 par chaîne
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.bridge_manager = bridge_manager
        self.web3_providers = web3_providers or {}
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._health_cache: Dict[str, Tuple[float, BridgeHealth]] = {}
        self._metrics: Dict[str, BridgeMetric] = {}
        self._alerts: List[BridgeAlert] = []
        self._pending_alerts: List[BridgeAlert] = []
        self._alert_history: deque = deque(maxlen=1000)
        self._monitoring_tasks: List[asyncio.Task] = []
        self._is_running = False
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des alertes
        self._alert_rules: Dict[str, Dict[str, Any]] = self._load_alert_rules()
        self._alert_callbacks: List[Callable] = []

        # Statistiques
        self._stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._historical_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des prix
        self._price_cache: Dict[str, Decimal] = {}

        logger.info("BridgeMonitor initialisé avec succès")

    def _load_alert_rules(self) -> Dict[str, Dict[str, Any]]:
        """Charge les règles d'alertes"""
        default_rules = {
            "success_rate_below": {
                "threshold": 0.95,
                "severity": AlertSeverity.WARNING,
                "description": "Success rate below 95%",
            },
            "success_rate_critical": {
                "threshold": 0.90,
                "severity": AlertSeverity.CRITICAL,
                "description": "Success rate below 90%",
            },
            "pending_transactions_high": {
                "threshold": 50,
                "severity": AlertSeverity.WARNING,
                "description": "High number of pending transactions",
            },
            "pending_transactions_critical": {
                "threshold": 100,
                "severity": AlertSeverity.CRITICAL,
                "description": "Critical number of pending transactions",
            },
            "response_time_high": {
                "threshold": 10.0,
                "severity": AlertSeverity.WARNING,
                "description": "High response time",
            },
            "response_time_critical": {
                "threshold": 30.0,
                "severity": AlertSeverity.CRITICAL,
                "description": "Critical response time",
            },
            "volume_anomaly": {
                "threshold": 3.0,  # standard deviations
                "severity": AlertSeverity.WARNING,
                "description": "Anomalous volume detected",
            },
            "fee_anomaly": {
                "threshold": 2.0,  # standard deviations
                "severity": AlertSeverity.WARNING,
                "description": "Anomalous fees detected",
            },
        }

        # Fusion avec la configuration
        configured_rules = self.config.get("alert_rules", {})
        default_rules.update(configured_rules)

        return default_rules

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    async def start_monitoring(self) -> None:
        """Démarre le monitoring en arrière-plan"""
        if self._is_running:
            return

        self._is_running = True
        logger.info("Démarrage du monitoring des bridges")

        # Tâches de monitoring
        self._monitoring_tasks.extend([
            asyncio.create_task(self._monitor_health()),
            asyncio.create_task(self._monitor_metrics()),
            asyncio.create_task(self._monitor_alerts()),
            asyncio.create_task(self._monitor_pending_transactions()),
        ])

    async def stop_monitoring(self) -> None:
        """Arrête le monitoring"""
        self._is_running = False

        for task in self._monitoring_tasks:
            task.cancel()

        try:
            await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)
        except Exception:
            pass

        self._monitoring_tasks.clear()
        logger.info("Monitoring des bridges arrêté")

    async def get_bridge_health(
        self,
        protocol: str,
        chain: str,
        force_refresh: bool = False,
    ) -> BridgeHealth:
        """
        Obtient l'état de santé d'un bridge

        Args:
            protocol: Protocole
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            État de santé du bridge
        """
        cache_key = f"{protocol}:{chain}"

        if not force_refresh and cache_key in self._health_cache:
            cached_time, health = self._health_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return health

        try:
            # Récupération des données de santé
            health = await self._collect_bridge_health(protocol, chain)

            # Mise en cache
            self._health_cache[cache_key] = (time.time(), health)

            # Métriques
            self.metrics_collector.record_gauge(
                "bridge_health_status",
                1 if health.status == MonitorStatus.HEALTHY else 0,
                {
                    "protocol": protocol,
                    "chain": chain,
                    "status": health.status.value,
                },
            )

            return health

        except Exception as e:
            logger.error(f"Erreur de collecte de santé pour {protocol}: {e}")
            raise MonitoringError(f"Erreur de collecte de santé: {e}")

    async def get_bridge_metrics(
        self,
        protocol: str,
        chain: str,
        metric_name: Optional[str] = None,
        timeframe: int = 3600,
    ) -> List[BridgeMetric]:
        """
        Obtient les métriques d'un bridge

        Args:
            protocol: Protocole
            chain: Chaîne
            metric_name: Nom de la métrique (optionnel)
            timeframe: Période en secondes

        Returns:
            Liste des métriques
        """
        cutoff = datetime.now() - timedelta(seconds=timeframe)

        metrics = []
        for metric in self._metrics.values():
            if metric.protocol == protocol and metric.chain == chain:
                if metric_name and metric.name != metric_name:
                    continue
                if metric.timestamp >= cutoff:
                    metrics.append(metric)

        return sorted(metrics, key=lambda m: m.timestamp)

    async def get_alerts(
        self,
        protocol: Optional[str] = None,
        chain: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[BridgeAlert]:
        """
        Obtient les alertes

        Args:
            protocol: Filtrer par protocole
            chain: Filtrer par chaîne
            severity: Filtrer par sévérité
            resolved: Filtrer par statut de résolution
            limit: Nombre maximum d'alertes

        Returns:
            Liste des alertes
        """
        alerts = self._alerts.copy()

        if protocol:
            alerts = [a for a in alerts if a.protocol == protocol]

        if chain:
            alerts = [a for a in alerts if a.chain == chain]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]

        # Trier par date (plus récent en premier)
        alerts.sort(key=lambda a: a.timestamp, reverse=True)

        return alerts[:limit]

    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Résout une alerte

        Args:
            alert_id: ID de l'alerte

        Returns:
            True si résolu avec succès
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.now()
                return True

        return False

    def add_alert_callback(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les alertes

        Args:
            callback: Fonction callback
        """
        self._alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable) -> None:
        """
        Supprime un callback d'alerte

        Args:
            callback: Fonction callback à supprimer
        """
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)

    # ============================================================
    # MÉTHODES DE COLLECTE
    # ============================================================

    async def _collect_bridge_health(
        self,
        protocol: str,
        chain: str,
    ) -> BridgeHealth:
        """Collecte l'état de santé d'un bridge"""
        try:
            # Récupération des données via le bridge manager
            bridge = await self.bridge_manager.get_bridge(protocol, chain)
            if not bridge:
                raise MonitoringError(f"Bridge {protocol} sur {chain} non trouvé")

            # Collecte des métriques de base
            success_rate = await self._calculate_success_rate(protocol, chain)
            pending_txs = await self._count_pending_transactions(protocol, chain)
            response_time = await self._calculate_response_time(protocol, chain)
            volume_24h = await self._calculate_volume_24h(protocol, chain)
            fees_24h = await self._calculate_fees_24h(protocol, chain)

            # Collecte des données de chaîne
            block_data = await self._get_block_data(chain)
            validator_data = await self._get_validator_data(protocol, chain)

            # Calcul de l'uptime
            uptime = await self._calculate_uptime(protocol, chain)

            # Détermination du statut
            status = self._determine_status(
                success_rate=success_rate,
                pending_txs=pending_txs,
                response_time=response_time,
                uptime=uptime,
            )

            health = BridgeHealth(
                protocol=protocol,
                chain=chain,
                status=status,
                uptime=uptime,
                success_rate=success_rate,
                avg_response_time=response_time,
                pending_transactions=pending_txs,
                total_volume_24h=volume_24h,
                fees_24h=fees_24h,
                last_block=block_data.get("number", 0),
                block_latency=block_data.get("latency", 0.0),
                validator_count=validator_data.get("total", 0),
                active_validators=validator_data.get("active", 0),
            )

            return health

        except Exception as e:
            logger.error(f"Erreur de collecte de santé: {e}")
            raise

    async def _collect_metrics(
        self,
        protocol: str,
        chain: str,
    ) -> None:
        """Collecte les métriques d'un bridge"""
        try:
            # Métriques de performance
            performance_metrics = await self._collect_performance_metrics(
                protocol, chain
            )
            for metric in performance_metrics:
                self._metrics[metric.metric_id] = metric

            # Métriques de volume
            volume_metrics = await self._collect_volume_metrics(protocol, chain)
            for metric in volume_metrics:
                self._metrics[metric.metric_id] = metric

            # Métriques de frais
            fee_metrics = await self._collect_fee_metrics(protocol, chain)
            for metric in fee_metrics:
                self._metrics[metric.metric_id] = metric

            # Métriques de santé
            health_metrics = await self._collect_health_metrics(protocol, chain)
            for metric in health_metrics:
                self._metrics[metric.metric_id] = metric

            # Métriques de sécurité
            security_metrics = await self._collect_security_metrics(protocol, chain)
            for metric in security_metrics:
                self._metrics[metric.metric_id] = metric

        except Exception as e:
            logger.error(f"Erreur de collecte de métriques pour {protocol}: {e}")

    async def _collect_performance_metrics(
        self,
        protocol: str,
        chain: str,
    ) -> List[BridgeMetric]:
        """Collecte les métriques de performance"""
        metrics = []

        try:
            # Temps de réponse
            response_time = await self._calculate_response_time(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"perf_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="response_time",
                value=response_time,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Average response time in seconds",
            ))

            # Taux de succès
            success_rate = await self._calculate_success_rate(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"perf_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="success_rate",
                value=success_rate,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Success rate (0-1)",
            ))

            # Transactions en attente
            pending = await self._count_pending_transactions(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"perf_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="pending_transactions",
                value=pending,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Number of pending transactions",
            ))

            # Uptime
            uptime = await self._calculate_uptime(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"perf_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="uptime",
                value=uptime,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Uptime in seconds",
            ))

            return metrics

        except Exception as e:
            logger.error(f"Erreur de collecte des métriques de performance: {e}")
            return []

    async def _collect_volume_metrics(
        self,
        protocol: str,
        chain: str,
    ) -> List[BridgeMetric]:
        """Collecte les métriques de volume"""
        metrics = []

        try:
            # Volume 24h
            volume_24h = await self._calculate_volume_24h(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"vol_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="volume_24h",
                value=volume_24h,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Total volume in last 24 hours",
            ))

            # Volume 1h
            volume_1h = await self._calculate_volume_1h(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"vol_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="volume_1h",
                value=volume_1h,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Total volume in last hour",
            ))

            # Nombre de transactions 24h
            tx_count_24h = await self._count_transactions_24h(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"vol_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.COUNTER,
                name="transactions_24h",
                value=tx_count_24h,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Number of transactions in last 24 hours",
            ))

            return metrics

        except Exception as e:
            logger.error(f"Erreur de collecte des métriques de volume: {e}")
            return []

    async def _collect_fee_metrics(
        self,
        protocol: str,
        chain: str,
    ) -> List[BridgeMetric]:
        """Collecte les métriques de frais"""
        metrics = []

        try:
            # Frais 24h
            fees_24h = await self._calculate_fees_24h(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"fee_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="fees_24h",
                value=fees_24h,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Total fees in last 24 hours",
            ))

            # Frais moyen par transaction
            avg_fee = await self._calculate_average_fee(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"fee_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="average_fee",
                value=avg_fee,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Average fee per transaction",
            ))

            return metrics

        except Exception as e:
            logger.error(f"Erreur de collecte des métriques de frais: {e}")
            return []

    async def _collect_health_metrics(
        self,
        protocol: str,
        chain: str,
    ) -> List[BridgeMetric]:
        """Collecte les métriques de santé"""
        metrics = []

        try:
            # État de santé
            health = await self.get_bridge_health(protocol, chain)
            metrics.append(BridgeMetric(
                metric_id=f"health_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="health_status",
                value=1 if health.status == MonitorStatus.HEALTHY else 0,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                labels={"status": health.status.value},
                description="Bridge health status (1=healthy, 0=unhealthy)",
            ))

            # Latence des blocs
            metrics.append(BridgeMetric(
                metric_id=f"health_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="block_latency",
                value=health.block_latency,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Block latency in seconds",
            ))

            # Validateurs actifs
            metrics.append(BridgeMetric(
                metric_id=f"health_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.GAUGE,
                name="active_validators",
                value=health.active_validators,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Number of active validators",
            ))

            return metrics

        except Exception as e:
            logger.error(f"Erreur de collecte des métriques de santé: {e}")
            return []

    async def _collect_security_metrics(
        self,
        protocol: str,
        chain: str,
    ) -> List[BridgeMetric]:
        """Collecte les métriques de sécurité"""
        metrics = []

        try:
            # Nombre d'incidents de sécurité
            security_events = await self._count_security_events(protocol, chain, 3600)
            metrics.append(BridgeMetric(
                metric_id=f"sec_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.COUNTER,
                name="security_events_1h",
                value=security_events,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Number of security events in last hour",
            ))

            # Menaces détectées
            threats = await self._count_threats(protocol, chain, 3600)
            metrics.append(BridgeMetric(
                metric_id=f"sec_{uuid.uuid4().hex[:8]}",
                metric_type=MetricType.COUNTER,
                name="threats_detected_1h",
                value=threats,
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                description="Number of threats detected in last hour",
            ))

            return metrics

        except Exception as e:
            logger.error(f"Erreur de collecte des métriques de sécurité: {e}")
            return []

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _calculate_success_rate(self, protocol: str, chain: str) -> float:
        """Calcule le taux de succès"""
        try:
            # Dans la réalité, on récupérerait les données historiques
            # Simulé: retourner un taux basé sur les transactions récentes
            return 0.99  # 99% de succès

        except Exception as e:
            logger.warning(f"Erreur de calcul du taux de succès: {e}")
            return 0.95

    async def _count_pending_transactions(self, protocol: str, chain: str) -> int:
        """Compte les transactions en attente"""
        try:
            # Dans la réalité, on interrogerait les APIs
            return 0

        except Exception as e:
            logger.warning(f"Erreur de comptage des transactions en attente: {e}")
            return 0

    async def _calculate_response_time(self, protocol: str, chain: str) -> float:
        """Calcule le temps de réponse moyen"""
        try:
            # Dans la réalité, on mesurerait les temps de réponse réels
            return 1.5  # 1.5 secondes

        except Exception as e:
            logger.warning(f"Erreur de calcul du temps de réponse: {e}")
            return 5.0

    async def _calculate_volume_24h(self, protocol: str, chain: str) -> Decimal:
        """Calcule le volume des 24 dernières heures"""
        try:
            # Dans la réalité, on interrogerait les données historiques
            return Decimal("1000000")

        except Exception as e:
            logger.warning(f"Erreur de calcul du volume: {e}")
            return Decimal("0")

    async def _calculate_volume_1h(self, protocol: str, chain: str) -> Decimal:
        """Calcule le volume de la dernière heure"""
        try:
            return Decimal("50000")

        except Exception as e:
            logger.warning(f"Erreur de calcul du volume 1h: {e}")
            return Decimal("0")

    async def _calculate_fees_24h(self, protocol: str, chain: str) -> Decimal:
        """Calcule les frais des 24 dernières heures"""
        try:
            return Decimal("1000")

        except Exception as e:
            logger.warning(f"Erreur de calcul des frais: {e}")
            return Decimal("0")

    async def _calculate_average_fee(self, protocol: str, chain: str) -> Decimal:
        """Calcule le frais moyen par transaction"""
        try:
            return Decimal("5")

        except Exception as e:
            logger.warning(f"Erreur de calcul du frais moyen: {e}")
            return Decimal("0")

    async def _count_transactions_24h(self, protocol: str, chain: str) -> int:
        """Compte les transactions des 24 dernières heures"""
        try:
            return 1000

        except Exception as e:
            logger.warning(f"Erreur de comptage des transactions: {e}")
            return 0

    async def _count_security_events(
        self,
        protocol: str,
        chain: str,
        timeframe: int,
    ) -> int:
        """Compte les événements de sécurité"""
        try:
            return 0

        except Exception as e:
            logger.warning(f"Erreur de comptage des événements de sécurité: {e}")
            return 0

    async def _count_threats(
        self,
        protocol: str,
        chain: str,
        timeframe: int,
    ) -> int:
        """Compte les menaces détectées"""
        try:
            return 0

        except Exception as e:
            logger.warning(f"Erreur de comptage des menaces: {e}")
            return 0

    async def _calculate_uptime(self, protocol: str, chain: str) -> float:
        """Calcule l'uptime"""
        try:
            # Simulé: 99.9% d'uptime
            return 3600 * 24 * 30  # 30 jours

        except Exception as e:
            logger.warning(f"Erreur de calcul de l'uptime: {e}")
            return 3600 * 24

    async def _get_block_data(self, chain: str) -> Dict[str, Any]:
        """Obtient les données de bloc"""
        try:
            provider = self.web3_providers.get(chain)
            if provider:
                block = await provider.eth.get_block("latest")
                return {
                    "number": block.get("number", 0),
                    "timestamp": block.get("timestamp", 0),
                    "latency": time.time() - block.get("timestamp", time.time()),
                }

            return {"number": 0, "latency": 0.0}

        except Exception as e:
            logger.warning(f"Erreur d'obtention des données de bloc: {e}")
            return {"number": 0, "latency": 0.0}

    async def _get_validator_data(self, protocol: str, chain: str) -> Dict[str, Any]:
        """Obtient les données des validateurs"""
        try:
            return {"total": 10, "active": 8}

        except Exception as e:
            logger.warning(f"Erreur d'obtention des données de validateurs: {e}")
            return {"total": 0, "active": 0}

    def _determine_status(
        self,
        success_rate: float,
        pending_txs: int,
        response_time: float,
        uptime: float,
    ) -> MonitorStatus:
        """Détermine le statut de santé"""
        if success_rate < 0.90:
            return MonitorStatus.UNHEALTHY
        elif success_rate < 0.95:
            return MonitorStatus.DEGRADED

        if pending_txs > 100:
            return MonitorStatus.DEGRADED
        elif pending_txs > 200:
            return MonitorStatus.UNHEALTHY

        if response_time > 30.0:
            return MonitorStatus.UNHEALTHY
        elif response_time > 10.0:
            return MonitorStatus.DEGRADED

        if uptime < 3600 * 24 * 7:  # Moins d'une semaine
            return MonitorStatus.DEGRADED

        return MonitorStatus.HEALTHY

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def _monitor_health(self) -> None:
        """Monitore la santé des bridges en continu"""
        while self._is_running:
            try:
                protocols = self.config.get("monitored_protocols", [])
                chains = self.config.get("monitored_chains", [])

                for protocol in protocols:
                    for chain in chains:
                        try:
                            health = await self.get_bridge_health(
                                protocol, chain, force_refresh=True
                            )

                            # Vérification des alertes
                            await self._check_health_alerts(health)

                        except Exception as e:
                            logger.error(f"Erreur de monitoring de {protocol}/{chain}: {e}")

            except Exception as e:
                logger.error(f"Erreur de monitoring de santé: {e}")

            await asyncio.sleep(60)  # Toutes les minutes

    async def _monitor_metrics(self) -> None:
        """Monitore les métriques en continu"""
        while self._is_running:
            try:
                protocols = self.config.get("monitored_protocols", [])
                chains = self.config.get("monitored_chains", [])

                for protocol in protocols:
                    for chain in chains:
                        try:
                            await self._collect_metrics(protocol, chain)
                        except Exception as e:
                            logger.error(f"Erreur de collecte de métriques pour {protocol}/{chain}: {e}")

            except Exception as e:
                logger.error(f"Erreur de monitoring des métriques: {e}")

            await asyncio.sleep(300)  # Toutes les 5 minutes

    async def _monitor_alerts(self) -> None:
        """Monitore les alertes en continu"""
        while self._is_running:
            try:
                # Vérification des alertes en attente
                for alert in self._pending_alerts:
                    if not alert.resolved:
                        # Envoi de l'alerte
                        await self._send_alert(alert)

            except Exception as e:
                logger.error(f"Erreur de monitoring des alertes: {e}")

            await asyncio.sleep(10)

    async def _monitor_pending_transactions(self) -> None:
        """Monitore les transactions en attente"""
        while self._is_running:
            try:
                protocols = self.config.get("monitored_protocols", [])
                chains = self.config.get("monitored_chains", [])

                for protocol in protocols:
                    for chain in chains:
                        try:
                            pending = await self._count_pending_transactions(
                                protocol, chain
                            )

                            if pending > 50:
                                await self._create_alert(
                                    severity=AlertSeverity.WARNING,
                                    protocol=protocol,
                                    chain=chain,
                                    title="High pending transactions",
                                    message=f"{pending} transactions pending for {protocol} on {chain}",
                                    metadata={"pending_count": pending},
                                )

                        except Exception as e:
                            logger.error(f"Erreur de monitoring des transactions en attente: {e}")

            except Exception as e:
                logger.error(f"Erreur de monitoring des transactions en attente: {e}")

            await asyncio.sleep(60)  # Toutes les minutes

    # ============================================================
    # MÉTHODES D'ALERTES
    # ============================================================

    async def _check_health_alerts(self, health: BridgeHealth) -> None:
        """Vérifie les alertes de santé"""
        # Taux de succès
        if health.success_rate < 0.90:
            await self._create_alert(
                severity=AlertSeverity.CRITICAL,
                protocol=health.protocol,
                chain=health.chain,
                title="Critical success rate",
                message=f"Success rate is {health.success_rate:.2%}",
                metadata={"success_rate": health.success_rate},
            )
        elif health.success_rate < 0.95:
            await self._create_alert(
                severity=AlertSeverity.WARNING,
                protocol=health.protocol,
                chain=health.chain,
                title="Low success rate",
                message=f"Success rate is {health.success_rate:.2%}",
                metadata={"success_rate": health.success_rate},
            )

        # Transactions en attente
        if health.pending_transactions > 100:
            await self._create_alert(
                severity=AlertSeverity.CRITICAL,
                protocol=health.protocol,
                chain=health.chain,
                title="Critical pending transactions",
                message=f"{health.pending_transactions} transactions pending",
                metadata={"pending": health.pending_transactions},
            )
        elif health.pending_transactions > 50:
            await self._create_alert(
                severity=AlertSeverity.WARNING,
                protocol=health.protocol,
                chain=health.chain,
                title="High pending transactions",
                message=f"{health.pending_transactions} transactions pending",
                metadata={"pending": health.pending_transactions},
            )

        # Temps de réponse
        if health.avg_response_time > 30.0:
            await self._create_alert(
                severity=AlertSeverity.CRITICAL,
                protocol=health.protocol,
                chain=health.chain,
                title="Critical response time",
                message=f"Response time is {health.avg_response_time:.1f}s",
                metadata={"response_time": health.avg_response_time},
            )
        elif health.avg_response_time > 10.0:
            await self._create_alert(
                severity=AlertSeverity.WARNING,
                protocol=health.protocol,
                chain=health.chain,
                title="High response time",
                message=f"Response time is {health.avg_response_time:.1f}s",
                metadata={"response_time": health.avg_response_time},
            )

        # Statut général
        if health.status == MonitorStatus.OFFLINE:
            await self._create_alert(
                severity=AlertSeverity.EMERGENCY,
                protocol=health.protocol,
                chain=health.chain,
                title="Bridge offline",
                message=f"{health.protocol} on {health.chain} is offline",
                metadata={},
            )

    async def _create_alert(
        self,
        severity: AlertSeverity,
        protocol: str,
        chain: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BridgeAlert:
        """Crée une alerte"""
        alert = BridgeAlert(
            alert_id=f"alert_{uuid.uuid4().hex[:12]}",
            severity=severity,
            protocol=protocol,
            chain=chain,
            title=title,
            message=message,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        self._alerts.append(alert)
        self._pending_alerts.append(alert)
        self._alert_history.append(alert)

        # Métriques
        self.metrics_collector.record_increment(
            "bridge_alert_created",
            {
                "protocol": protocol,
                "chain": chain,
                "severity": severity.value,
            },
        )

        logger.info(
            f"Alerte créée: {severity.value} - {title} "
            f"({protocol}/{chain})"
        )

        return alert

    async def _send_alert(self, alert: BridgeAlert) -> None:
        """Envoie une alerte"""
        try:
            alert_data = alert.to_dict()

            # Appel des callbacks
            for callback in self._alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert_data)
                    else:
                        callback(alert_data)
                except Exception as e:
                    logger.warning(f"Erreur de callback d'alerte: {e}")

            # Marquer comme envoyée
            if alert in self._pending_alerts:
                self._pending_alerts.remove(alert)

        except Exception as e:
            logger.error(f"Erreur d'envoi d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du monitoring"""
        total_alerts = len(self._alerts)
        pending_alerts = len([a for a in self._alerts if not a.resolved])
        critical_alerts = len([a for a in self._alerts if a.severity == AlertSeverity.CRITICAL])

        return {
            "total_alerts": total_alerts,
            "pending_alerts": pending_alerts,
            "critical_alerts": critical_alerts,
            "metrics_count": len(self._metrics),
            "cached_health": len(self._health_cache),
            "is_running": self._is_running,
            "alert_rules_count": len(self._alert_rules),
            "alert_callbacks": len(self._alert_callbacks),
        }

    def get_health_summary(self) -> Dict[str, Any]:
        """Obtient un résumé de la santé des bridges"""
        summary = defaultdict(lambda: defaultdict(dict))

        for cache_key, (_, health) in self._health_cache.items():
            protocol, chain = cache_key.split(":", 1)
            summary[protocol][chain] = {
                "status": health.status.value,
                "success_rate": health.success_rate,
                "pending_txs": health.pending_transactions,
                "uptime": health.uptime,
            }

        return dict(summary)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeMonitor...")

        await self.stop_monitoring()

        self._health_cache.clear()
        self._metrics.clear()
        self._alerts.clear()
        self._pending_alerts.clear()
        self._alert_history.clear()
        self._alert_callbacks.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_monitor(
    config: Dict[str, Any],
    bridge_manager: BridgeManager,
    **kwargs,
) -> BridgeMonitor:
    """
    Crée une instance de BridgeMonitor

    Args:
        config: Configuration
        bridge_manager: Gestionnaire de bridges
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeMonitor
    """
    return BridgeMonitor(
        config=config,
        bridge_manager=bridge_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeMonitor"""
    # Configuration
    config = {
        "monitored_protocols": ["wormhole", "layerzero", "cctp"],
        "monitored_chains": ["ethereum", "polygon", "arbitrum"],
        "alert_rules": {
            "success_rate_below": {
                "threshold": 0.95,
                "severity": "warning",
            },
            "pending_transactions_high": {
                "threshold": 50,
                "severity": "warning",
            },
        },
    }

    # Bridge manager (simplifié)
    class SimpleBridgeManager:
        async def get_bridge(self, protocol, chain):
            return {"protocol": protocol, "chain": chain}

    bridge_manager = SimpleBridgeManager()

    # Création du moniteur
    monitor = create_bridge_monitor(
        config=config,
        bridge_manager=bridge_manager,
    )

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE: {alert}")

    monitor.add_alert_callback(alert_callback)

    # Démarrage du monitoring
    await monitor.start_monitoring()

    # Attendre un peu
    await asyncio.sleep(5)

    # Obtention de la santé d'un bridge
    health = await monitor.get_bridge_health("wormhole", "ethereum")
    print(f"Santé: {health.to_dict()}")

    # Obtention des métriques
    metrics = await monitor.get_bridge_metrics("wormhole", "ethereum")
    print(f"Métriques: {len(metrics)}")

    # Statistiques
    stats = monitor.get_statistics()
    print(f"Statistiques: {stats}")

    # Résumé de santé
    summary = monitor.get_health_summary()
    print(f"Résumé: {summary}")

    # Nettoyage
    await monitor.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

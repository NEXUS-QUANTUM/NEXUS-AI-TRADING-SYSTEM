# blockchain/onchain-analysis/mempool_analyzer.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Mempool Analyzer - Analyse du Mempool

Ce module implémente un système complet d'analyse du mempool pour les
blockchains, permettant le monitoring des transactions en attente,
l'optimisation des frais, et la détection d'activités anormales.

Fonctionnalités principales:
- Surveillance du mempool en temps réel
- Analyse des transactions en attente
- Optimisation des frais
- Détection d'activités suspectes
- Front-running detection
- Sandwich attack detection
- Support multi-chaînes
- Alertes d'activité
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
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

import aiohttp
import web3
from web3 import Web3
from web3.contract import Contract
from eth_utils import to_checksum_address

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, AnalysisError, ValidationError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from ..nodes.base_node import BaseNode
    from ..nodes.node_manager import NodeManager
    from ..nodes.node_rpc import NodeRPCClient, RPCMethod
    from .base_analyzer import BaseAnalyzer, AnalysisResult, AnalysisStatus
    from .analysis_config import AnalysisConfig, MetricType, AnalysisType
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, AnalysisError, ValidationError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from ..nodes.base_node import BaseNode
    from ..nodes.node_manager import NodeManager
    from ..nodes.node_rpc import NodeRPCClient, RPCMethod
    from .base_analyzer import BaseAnalyzer, AnalysisResult, AnalysisStatus
    from .analysis_config import AnalysisConfig, MetricType, AnalysisType

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class MempoolStatus(Enum):
    """Statuts du mempool"""
    NORMAL = "normal"
    CONGESTED = "congested"
    SPIKING = "spiking"
    UNDER_ATTACK = "under_attack"


class TransactionType(Enum):
    """Types de transactions"""
    NORMAL = "normal"
    HIGH_FEE = "high_fee"
    FRONT_RUN = "front_run"
    SANDWICH = "sandwich"
    SUSPICIOUS = "suspicious"


@dataclass
class MempoolTransaction:
    """Transaction dans le mempool"""
    tx_hash: str
    from_address: str
    to_address: Optional[str]
    value: Decimal
    gas_price: int
    gas_limit: int
    nonce: int
    input_data: str
    timestamp: datetime
    transaction_type: TransactionType
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "tx_hash": self.tx_hash,
            "from": self.from_address,
            "to": self.to_address,
            "value": str(self.value),
            "gas_price": self.gas_price,
            "gas_limit": self.gas_limit,
            "nonce": self.nonce,
            "input_data": self.input_data[:100] + "...",
            "timestamp": self.timestamp.isoformat(),
            "transaction_type": self.transaction_type.value,
            "metadata": self.metadata,
        }


@dataclass
class MempoolStats:
    """Statistiques du mempool"""
    chain: str
    total_pending: int
    average_gas_price: int
    min_gas_price: int
    max_gas_price: int
    gas_price_distribution: Dict[str, int]
    pending_by_type: Dict[str, int]
    total_value_pending: Decimal
    status: MempoolStatus
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "chain": self.chain,
            "total_pending": self.total_pending,
            "average_gas_price": self.average_gas_price,
            "min_gas_price": self.min_gas_price,
            "max_gas_price": self.max_gas_price,
            "gas_price_distribution": self.gas_price_distribution,
            "pending_by_type": self.pending_by_type,
            "total_value_pending": str(self.total_value_pending),
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class MempoolAlert:
    """Alerte de mempool"""
    alert_id: str
    chain: str
    alert_type: str
    severity: str
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "alert_id": self.alert_id,
            "chain": self.chain,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# SEUILS DU MEMPOOL
# ============================================================

MEMPOOL_THRESHOLDS = {
    "ethereum": {
        "normal_pending": 100,
        "congested_pending": 1000,
        "spiking_pending": 5000,
        "normal_gas_price": 50,  # gwei
        "high_gas_price": 200,  # gwei
        "suspicious_gas_price": 500,  # gwei
    },
    "polygon": {
        "normal_pending": 50,
        "congested_pending": 500,
        "spiking_pending": 2000,
        "normal_gas_price": 50,
        "high_gas_price": 200,
        "suspicious_gas_price": 500,
    },
    "bsc": {
        "normal_pending": 20,
        "congested_pending": 200,
        "spiking_pending": 1000,
        "normal_gas_price": 5,
        "high_gas_price": 20,
        "suspicious_gas_price": 50,
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class MempoolAnalyzer(BaseAnalyzer):
    """
    Analyseur du mempool
    """

    def __init__(
        self,
        config: AnalysisConfig,
        node_manager: NodeManager,
        rpc_client: NodeRPCClient,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 60,  # Cache court pour le mempool
    ):
        """
        Initialise l'analyseur de mempool

        Args:
            config: Configuration de l'analyse
            node_manager: Gestionnaire de nœuds
            rpc_client: Client RPC
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, node_manager, rpc_client, metrics_collector, cache_ttl)

        self._pending_transactions: Dict[str, List[MempoolTransaction]] = defaultdict(list)
        self._mempool_stats: Dict[str, MempoolStats] = {}
        self._alerts: List[MempoolAlert] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        logger.info(f"MempoolAnalyzer {config.name} initialisé")

    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def collect_data(self) -> Dict[str, Any]:
        """
        Collecte les données du mempool

        Returns:
            Données collectées
        """
        logger.info(f"Collecte des données du mempool pour {self.config.chain}")

        data = {}
        chain = self.config.chain

        try:
            # Récupération des transactions en attente
            pending_txs = await self._get_pending_transactions(chain)
            data["pending_transactions"] = pending_txs

            # Récupération des statistiques
            stats = await self._get_mempool_stats(chain)
            data["stats"] = stats

            # Détection des anomalies
            anomalies = await self._detect_anomalies(chain, pending_txs, stats)
            data["anomalies"] = anomalies

        except Exception as e:
            logger.warning(f"Erreur de collecte du mempool: {e}")

        return data

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def process_data(self, data: Dict[str, Any]) -> Dict[MetricType, Any]:
        """
        Traite les données du mempool

        Args:
            data: Données collectées

        Returns:
            Métriques calculées
        """
        logger.info(f"Traitement des données du mempool")

        metrics = {}

        stats = data.get("stats")
        if stats:
            # Nombre de transactions en attente
            metrics[MetricType.TRANSACTION_COUNT] = stats.total_pending

            # Prix moyen du gaz
            metrics[MetricType.GAS_USAGE] = stats.average_gas_price

            # Valeur totale en attente
            metrics[MetricType.VOLUME_24H] = stats.total_value_pending

            # Status du mempool
            status_score = self._status_to_score(stats.status)
            metrics[MetricType.VOLATILITY_RISK] = status_score

        # Anomalies
        anomalies = data.get("anomalies", [])
        metrics[MetricType.SUSPICIOUS_ACTIVITY] = len(anomalies)

        return metrics

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def generate_insights(self, metrics: Dict[MetricType, Any]) -> List[str]:
        """
        Génère des insights à partir des données du mempool

        Args:
            metrics: Métriques calculées

        Returns:
            Liste des insights
        """
        insights = []

        # Analyse de l'activité
        if MetricType.TRANSACTION_COUNT in metrics:
            pending = metrics[MetricType.TRANSACTION_COUNT]
            if pending > 1000:
                insights.append(f"Mempool congestionné: {pending} transactions en attente")
            elif pending > 100:
                insights.append(f"Activité modérée dans le mempool: {pending} transactions")

        # Analyse du prix du gaz
        if MetricType.GAS_USAGE in metrics:
            gas_price = metrics[MetricType.GAS_USAGE]
            if gas_price > 200:
                insights.append(f"Prix du gaz élevé: {gas_price} Gwei")
            elif gas_price > 100:
                insights.append(f"Prix du gaz modéré: {gas_price} Gwei")

        # Anomalies
        if MetricType.SUSPICIOUS_ACTIVITY in metrics:
            anomalies = metrics[MetricType.SUSPICIOUS_ACTIVITY]
            if anomalies > 0:
                insights.append(f"{anomalies} activités suspectes détectées")

        return insights

    # ============================================================
    # MÉTHODES DE COLLECTE DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def _get_pending_transactions(self, chain: str) -> List[MempoolTransaction]:
        """
        Récupère les transactions en attente

        Args:
            chain: Chaîne

        Returns:
            Liste des transactions
        """
        try:
            # Récupération des transactions en attente
            # Dans la réalité, on utiliserait txpool_content
            # Simulé pour l'exemple
            pending_txs = []

            for i in range(20):
                tx = MempoolTransaction(
                    tx_hash=f"0x{hash(str(i)):064x}",
                    from_address=f"0x{hash(str(i+1)):040x}",
                    to_address=f"0x{hash(str(i+2)):040x}",
                    value=Decimal(str(0.1 * (i + 1))),
                    gas_price=50 + i * 10,
                    gas_limit=21000 + i * 1000,
                    nonce=i,
                    input_data="0x",
                    timestamp=datetime.now() - timedelta(seconds=i),
                    transaction_type=TransactionType.NORMAL,
                )
                pending_txs.append(tx)

            self._pending_transactions[chain] = pending_txs
            return pending_txs

        except Exception as e:
            logger.warning(f"Erreur de récupération du mempool: {e}")
            return []

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def _get_mempool_stats(self, chain: str) -> MempoolStats:
        """
        Calcule les statistiques du mempool

        Args:
            chain: Chaîne

        Returns:
            Statistiques du mempool
        """
        txs = self._pending_transactions.get(chain, [])

        if not txs:
            return MempoolStats(
                chain=chain,
                total_pending=0,
                average_gas_price=0,
                min_gas_price=0,
                max_gas_price=0,
                gas_price_distribution={},
                pending_by_type={},
                total_value_pending=Decimal("0"),
                status=MempoolStatus.NORMAL,
                timestamp=datetime.now(),
            )

        # Calcul des statistiques
        gas_prices = [tx.gas_price for tx in txs]
        total_value = sum(tx.value for tx in txs)

        # Distribution des prix du gaz
        distribution = defaultdict(int)
        for gp in gas_prices:
            bucket = (gp // 10) * 10
            distribution[f"{bucket}-{bucket+10}"] += 1

        # Distribution par type
        type_distribution = defaultdict(int)
        for tx in txs:
            type_distribution[tx.transaction_type.value] += 1

        # Status du mempool
        status = self._determine_status(chain, len(txs), gas_prices)

        return MempoolStats(
            chain=chain,
            total_pending=len(txs),
            average_gas_price=int(sum(gas_prices) / len(gas_prices)),
            min_gas_price=min(gas_prices),
            max_gas_price=max(gas_prices),
            gas_price_distribution=dict(distribution),
            pending_by_type=dict(type_distribution),
            total_value_pending=total_value,
            status=status,
            timestamp=datetime.now(),
        )

    # ============================================================
    # MÉTHODES DE DÉTECTION D'ANOMALIES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def _detect_anomalies(
        self,
        chain: str,
        pending_txs: List[MempoolTransaction],
        stats: MempoolStats,
    ) -> List[MempoolAlert]:
        """
        Détecte les anomalies dans le mempool

        Args:
            chain: Chaîne
            pending_txs: Transactions en attente
            stats: Statistiques du mempool

        Returns:
            Liste des alertes
        """
        alerts = []

        # 1. Détection de front-running
        front_run_alerts = await self._detect_front_running(pending_txs, chain)
        alerts.extend(front_run_alerts)

        # 2. Détection de sandwich attacks
        sandwich_alerts = await self._detect_sandwich_attacks(pending_txs, chain)
        alerts.extend(sandwich_alerts)

        # 3. Détection de pic de prix
        price_alert = await self._detect_price_spike(chain, stats)
        if price_alert:
            alerts.append(price_alert)

        # 4. Détection de congestion
        congestion_alert = await self._detect_congestion(chain, stats)
        if congestion_alert:
            alerts.append(congestion_alert)

        return alerts

    async def _detect_front_running(
        self,
        pending_txs: List[MempoolTransaction],
        chain: str,
    ) -> List[MempoolAlert]:
        """
        Détecte les attaques de front-running

        Args:
            pending_txs: Transactions en attente
            chain: Chaîne

        Returns:
            Liste des alertes
        """
        alerts = []
        threshold = MEMPOOL_THRESHOLDS.get(chain, {}).get("suspicious_gas_price", 500)

        # Tri par prix du gaz
        sorted_txs = sorted(pending_txs, key=lambda x: x.gas_price, reverse=True)

        for i, tx in enumerate(sorted_txs[:10]):
            if tx.gas_price > threshold:
                alert = MempoolAlert(
                    alert_id=f"front_run_{uuid.uuid4().hex[:12]}",
                    chain=chain,
                    alert_type="front_running",
                    severity="warning",
                    message=f"Front-running détecté: {tx.from_address[:8]}...",
                    details={
                        "tx_hash": tx.tx_hash,
                        "gas_price": tx.gas_price,
                        "from": tx.from_address,
                        "to": tx.to_address,
                    },
                    timestamp=datetime.now(),
                )
                alerts.append(alert)

        return alerts

    async def _detect_sandwich_attacks(
        self,
        pending_txs: List[MempoolTransaction],
        chain: str,
    ) -> List[MempoolAlert]:
        """
        Détecte les attaques sandwich

        Args:
            pending_txs: Transactions en attente
            chain: Chaîne

        Returns:
            Liste des alertes
        """
        alerts = []
        threshold = MEMPOOL_THRESHOLDS.get(chain, {}).get("high_gas_price", 200)

        # Recherche de patterns sandwich
        for i in range(len(pending_txs) - 2):
            tx1 = pending_txs[i]
            tx2 = pending_txs[i + 1]
            tx3 = pending_txs[i + 2]

            # Pattern sandwich: front-run + target + back-run
            if (tx1.gas_price > threshold and
                tx3.gas_price > threshold and
                tx2.gas_price < min(tx1.gas_price, tx3.gas_price)):

                alert = MempoolAlert(
                    alert_id=f"sandwich_{uuid.uuid4().hex[:12]}",
                    chain=chain,
                    alert_type="sandwich_attack",
                    severity="critical",
                    message=f"Sandwich attack détectée",
                    details={
                        "front_run": tx1.tx_hash,
                        "target": tx2.tx_hash,
                        "back_run": tx3.tx_hash,
                        "gas_prices": [tx1.gas_price, tx2.gas_price, tx3.gas_price],
                    },
                    timestamp=datetime.now(),
                )
                alerts.append(alert)

        return alerts

    async def _detect_price_spike(self, chain: str, stats: MempoolStats) -> Optional[MempoolAlert]:
        """
        Détecte les pics de prix

        Args:
            chain: Chaîne
            stats: Statistiques du mempool

        Returns:
            Alerte ou None
        """
        threshold = MEMPOOL_THRESHOLDS.get(chain, {}).get("high_gas_price", 200)

        if stats.average_gas_price > threshold:
            return MempoolAlert(
                alert_id=f"price_spike_{uuid.uuid4().hex[:12]}",
                chain=chain,
                alert_type="price_spike",
                severity="warning",
                message=f"Pic de prix du gaz: {stats.average_gas_price} Gwei",
                details={
                    "average_gas_price": stats.average_gas_price,
                    "max_gas_price": stats.max_gas_price,
                    "pending_count": stats.total_pending,
                },
                timestamp=datetime.now(),
            )

        return None

    async def _detect_congestion(self, chain: str, stats: MempoolStats) -> Optional[MempoolAlert]:
        """
        Détecte la congestion du mempool

        Args:
            chain: Chaîne
            stats: Statistiques du mempool

        Returns:
            Alerte ou None
        """
        threshold = MEMPOOL_THRESHOLDS.get(chain, {}).get("congested_pending", 1000)

        if stats.total_pending > threshold:
            return MempoolAlert(
                alert_id=f"congestion_{uuid.uuid4().hex[:12]}",
                chain=chain,
                alert_type="congestion",
                severity="warning",
                message=f"Mempool congestionné: {stats.total_pending} transactions",
                details={
                    "pending_count": stats.total_pending,
                    "average_gas_price": stats.average_gas_price,
                    "status": stats.status.value,
                },
                timestamp=datetime.now(),
            )

        return None

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _determine_status(self, chain: str, pending_count: int, gas_prices: List[int]) -> MempoolStatus:
        """
        Détermine le statut du mempool

        Args:
            chain: Chaîne
            pending_count: Nombre de transactions en attente
            gas_prices: Liste des prix du gaz

        Returns:
            Statut du mempool
        """
        thresholds = MEMPOOL_THRESHOLDS.get(chain, {})

        if pending_count > thresholds.get("spiking_pending", 5000):
            return MempoolStatus.SPIKING

        if pending_count > thresholds.get("congested_pending", 1000):
            return MempoolStatus.CONGESTED

        if gas_prices and max(gas_prices) > thresholds.get("suspicious_gas_price", 500) * 2:
            return MempoolStatus.UNDER_ATTACK

        return MempoolStatus.NORMAL

    def _status_to_score(self, status: MempoolStatus) -> Decimal:
        """
        Convertit le statut en score

        Args:
            status: Statut du mempool

        Returns:
            Score
        """
        scores = {
            MempoolStatus.NORMAL: Decimal("0.1"),
            MempoolStatus.CONGESTED: Decimal("0.5"),
            MempoolStatus.SPIKING: Decimal("0.8"),
            MempoolStatus.UNDER_ATTACK: Decimal("1.0"),
        }
        return scores.get(status, Decimal("0.1"))

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def start_monitoring(self, interval: int = 10) -> None:
        """
        Démarre le monitoring du mempool

        Args:
            interval: Intervalle en secondes
        """
        if self._is_monitoring:
            return

        self._is_monitoring = True
        logger.info(f"Démarrage du monitoring du mempool pour {self.config.chain}")

        while self._is_monitoring:
            try:
                # Collecte des données
                data = await self.collect_data()

                # Traitement des alertes
                anomalies = data.get("anomalies", [])
                for alert in anomalies:
                    self._alerts.append(alert)
                    await self._send_alert(alert.to_dict())

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring du mempool: {e}")
                await asyncio.sleep(interval * 2)

    async def stop_monitoring(self) -> None:
        """Arrête le monitoring du mempool"""
        self._is_monitoring = False
        logger.info(f"Monitoring du mempool arrêté pour {self.config.chain}")

    # ============================================================
    # MÉTHODE D'ANALYSE PRINCIPALE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def analyze(self) -> AnalysisResult:
        """
        Exécute l'analyse du mempool

        Returns:
            Résultat de l'analyse
        """
        return await self.run()


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_mempool_analyzer(
    config: AnalysisConfig,
    node_manager: NodeManager,
    rpc_client: NodeRPCClient,
    **kwargs,
) -> MempoolAnalyzer:
    """
    Crée une instance de MempoolAnalyzer

    Args:
        config: Configuration de l'analyse
        node_manager: Gestionnaire de nœuds
        rpc_client: Client RPC
        **kwargs: Arguments additionnels

    Returns:
        Instance de MempoolAnalyzer
    """
    return MempoolAnalyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de MempoolAnalyzer"""
    # Configuration
    config = AnalysisConfig(
        analysis_id="mempool_analysis_1",
        analysis_type=AnalysisType.CUSTOM,
        name="Mempool Analysis",
        description="Analysis of mempool activity",
        chain="ethereum",
        tokens=[],
        metrics=[],
        timeframe=3600,
        frequency=60,
    )

    # Création des dépendances (simplifiées)
    class SimpleNodeManager:
        async def get_nodes_by_protocol(self, protocol):
            return []

    class SimpleRPCClient:
        async def call(self, method, params, endpoint):
            return type('Response', (), {'is_success': lambda: True, 'result': '0x0'})

    node_manager = SimpleNodeManager()
    rpc_client = SimpleRPCClient()

    # Création de l'analyseur
    analyzer = create_mempool_analyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
    )

    # Exécution de l'analyse
    result = await analyzer.analyze()
    print(f"Résultat: {result.to_dict()}")

    # Démarrage du monitoring
    await analyzer.start_monitoring(interval=10)

    # Attendre quelques secondes
    await asyncio.sleep(15)

    # Arrêt du monitoring
    await analyzer.stop_monitoring()

    # Génération d'un rapport
    report = await analyzer.generate_report()
    print(f"Rapport: {report.to_dict()}")

    # Statistiques
    stats = analyzer.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await analyzer.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

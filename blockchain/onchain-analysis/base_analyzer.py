# blockchain/onchain-analysis/base_analyzer.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Base Analyzer - Classe de Base pour les Analyseurs On-Chain

Ce module définit la classe de base abstraite pour tous les analyseurs on-chain,
fournissant l'interface commune, les fonctionnalités partagées, et les
mécanismes de base pour l'analyse des données blockchain.

Fonctionnalités principales:
- Interface unifiée pour tous les analyseurs
- Gestion des métriques
- Collecte de données on-chain
- Analyse des données
- Génération de rapports
- Gestion des erreurs
- Monitoring des analyses
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
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
from functools import wraps

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
    from .analysis_config import (
        AnalysisConfig,
        MetricConfig,
        MetricType,
        AnalysisType,
    )
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
    from .analysis_config import (
        AnalysisConfig,
        MetricConfig,
        MetricType,
        AnalysisType,
    )

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class AnalysisStatus(Enum):
    """Statuts d'analyse"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AnalysisResult:
    """Résultat d'analyse"""
    analysis_id: str
    timestamp: datetime
    metrics: Dict[MetricType, Any]
    status: AnalysisStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "analysis_id": self.analysis_id,
            "timestamp": self.timestamp.isoformat(),
            "metrics": {k.value: v for k, v in self.metrics.items()},
            "status": self.status.value,
            "metadata": self.metadata,
        }


@dataclass
class AnalysisReport:
    """Rapport d'analyse"""
    report_id: str
    analysis_id: str
    start_time: datetime
    end_time: datetime
    results: List[AnalysisResult]
    summary: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "report_id": self.report_id,
            "analysis_id": self.analysis_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE DE BASE ABSTRAITE
# ============================================================

class BaseAnalyzer(ABC):
    """
    Classe de base abstraite pour tous les analyseurs on-chain
    """

    def __init__(
        self,
        config: AnalysisConfig,
        node_manager: NodeManager,
        rpc_client: NodeRPCClient,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise l'analyseur de base

        Args:
            config: Configuration de l'analyse
            node_manager: Gestionnaire de nœuds
            rpc_client: Client RPC
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.node_manager = node_manager
        self.rpc_client = rpc_client
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # État interne
        self._analysis_id = config.analysis_id
        self._status = AnalysisStatus.PENDING
        self._results: List[AnalysisResult] = []
        self._last_run: Optional[datetime] = None
        self._active_operations: Dict[str, Dict[str, Any]] = {}
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

        # Cache
        self._cache: Dict[str, Tuple[float, Any]] = {}

        # Métriques
        self._operation_count = 0
        self._success_count = 0
        self._failure_count = 0

        # Alertes
        self._alert_callbacks: List[Callable] = []

        logger.info(f"BaseAnalyzer {config.name} initialisé")

    # ============================================================
    # MÉTHODES ABSTRAITES (À IMPLÉMENTER)
    # ============================================================

    @abstractmethod
    async def analyze(self) -> AnalysisResult:
        """
        Exécute l'analyse

        Returns:
            Résultat de l'analyse
        """
        pass

    @abstractmethod
    async def collect_data(self) -> Dict[str, Any]:
        """
        Collecte les données on-chain

        Returns:
            Données collectées
        """
        pass

    @abstractmethod
    async def process_data(self, data: Dict[str, Any]) -> Dict[MetricType, Any]:
        """
        Traite les données collectées

        Args:
            data: Données collectées

        Returns:
            Métriques calculées
        """
        pass

    @abstractmethod
    async def generate_insights(self, metrics: Dict[MetricType, Any]) -> List[str]:
        """
        Génère des insights à partir des métriques

        Args:
            metrics: Métriques calculées

        Returns:
            Liste des insights
        """
        pass

    # ============================================================
    # MÉTHODES DE BASE COMMUNES
    # ============================================================

    async def run(self) -> AnalysisResult:
        """
        Exécute l'analyse complète

        Returns:
            Résultat de l'analyse
        """
        operation_id = self._generate_operation_id()
        logger.info(f"Exécution de l'analyse {self._analysis_id} ({operation_id})")

        self._status = AnalysisStatus.RUNNING

        try:
            # Collecte des données
            data = await self.collect_data()

            # Traitement des données
            metrics = await self.process_data(data)

            # Génération des insights
            insights = await self.generate_insights(metrics)

            # Création du résultat
            result = AnalysisResult(
                analysis_id=self._analysis_id,
                timestamp=datetime.now(),
                metrics=metrics,
                status=AnalysisStatus.COMPLETED,
                metadata={
                    "insights": insights,
                    "data_count": len(data) if isinstance(data, dict) else 0,
                },
            )

            self._results.append(result)
            self._status = AnalysisStatus.COMPLETED
            self._last_run = datetime.now()

            # Métriques
            self._success_count += 1
            self.metrics.record_increment(
                "analysis_run_success",
                1,
                {"analysis_id": self._analysis_id},
            )

            logger.info(f"Analyse {self._analysis_id} terminée avec succès")
            return result

        except Exception as e:
            logger.error(f"Erreur d'analyse {self._analysis_id}: {e}")
            self._status = AnalysisStatus.FAILED
            self._failure_count += 1

            self.metrics.record_increment(
                "analysis_run_failed",
                1,
                {"analysis_id": self._analysis_id, "error": type(e).__name__},
            )

            raise AnalysisError(f"Erreur d'analyse: {e}")

        finally:
            self._operation_count += 1

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_status(self) -> AnalysisStatus:
        """
        Obtient le statut de l'analyse

        Returns:
            Statut de l'analyse
        """
        return self._status

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_results(self, limit: int = 100) -> List[AnalysisResult]:
        """
        Obtient les résultats de l'analyse

        Args:
            limit: Nombre maximum de résultats

        Returns:
            Liste des résultats
        """
        return self._results[-limit:]

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def generate_report(self) -> AnalysisReport:
        """
        Génère un rapport d'analyse

        Returns:
            Rapport d'analyse
        """
        if not self._results:
            raise AnalysisError("Aucun résultat disponible")

        latest_result = self._results[-1]
        insights = latest_result.metadata.get("insights", [])

        # Résumé
        summary = {
            "total_runs": len(self._results),
            "success_rate": self._success_count / max(1, self._operation_count),
            "latest_status": self._status.value,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "metrics_count": len(latest_result.metrics),
        }

        return AnalysisReport(
            report_id=f"rpt_{uuid.uuid4().hex[:12]}",
            analysis_id=self._analysis_id,
            start_time=self._results[0].timestamp if self._results else datetime.now(),
            end_time=datetime.now(),
            results=self._results[-10:],
            summary=summary,
            insights=insights,
            recommendations=await self._generate_recommendations(latest_result),
        )

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtient les statistiques de l'analyseur

        Returns:
            Statistiques
        """
        total_operations = self._operation_count
        success_rate = self._success_count / max(1, total_operations)

        return {
            "analysis_id": self._analysis_id,
            "name": self.config.name,
            "type": self.config.analysis_type.value,
            "status": self._status.value,
            "total_operations": total_operations,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
            "total_results": len(self._results),
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "cache_size": len(self._cache),
        }

    def get_config(self) -> AnalysisConfig:
        """
        Obtient la configuration de l'analyse

        Returns:
            Configuration
        """
        return self.config

    # ============================================================
    # MÉTHODES UTILITAIRES PROTÉGÉES
    # ============================================================

    def _generate_operation_id(self) -> str:
        """Génère un ID d'opération unique"""
        return f"op_{uuid.uuid4().hex[:12]}"

    def _get_cache_key(self, *args, **kwargs) -> str:
        """Génère une clé de cache"""
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
        return hashlib.sha256(":".join(key_parts).encode()).hexdigest()

    async def _cache_get(self, key: str) -> Optional[Any]:
        """Obtient une valeur du cache"""
        if key in self._cache:
            cached_time, value = self._cache[key]
            if time.time() - cached_time < self.cache_ttl:
                return value
        return None

    async def _cache_set(self, key: str, value: Any) -> None:
        """Définit une valeur dans le cache"""
        self._cache[key] = (time.time(), value)

    async def _get_node(self) -> Optional[BaseNode]:
        """Obtient un nœud pour la chaîne configurée"""
        try:
            protocol = self._get_protocol_from_chain(self.config.chain)
            nodes = await self.node_manager.get_nodes_by_protocol(protocol)
            if nodes:
                return nodes[0]
            return None
        except Exception as e:
            logger.warning(f"Erreur de récupération du nœud: {e}")
            return None

    def _get_protocol_from_chain(self, chain: str) -> str:
        """Convertit le nom de la chaîne en protocole"""
        chain_map = {
            "ethereum": "ethereum",
            "bsc": "bsc",
            "polygon": "polygon",
            "arbitrum": "arbitrum",
            "optimism": "optimism",
            "avalanche": "avalanche",
            "solana": "solana",
            "base": "base",
        }
        return chain_map.get(chain, "ethereum")

    async def _make_rpc_call(
        self,
        method: Union[str, RPCMethod],
        params: List[Any],
    ) -> Any:
        """Effectue un appel RPC"""
        node = await self._get_node()
        if not node:
            raise AnalysisError("Aucun nœud disponible")

        try:
            response = await self.rpc_client.call(
                method=method,
                params=params,
                endpoint=node.config.endpoint,
            )

            if response.is_success():
                return response.result

            raise AnalysisError(f"RPC call failed: {response.error}")

        except Exception as e:
            logger.error(f"Erreur RPC: {e}")
            raise

    async def _generate_recommendations(
        self,
        result: AnalysisResult,
    ) -> List[str]:
        """
        Génère des recommandations à partir des résultats

        Args:
            result: Résultat de l'analyse

        Returns:
            Liste des recommandations
        """
        recommendations = []

        # Recommandations basées sur les métriques
        for metric_type, value in result.metrics.items():
            metric_config = self._get_metric_config(metric_type)
            if metric_config:
                if metric_config.threshold_warning and value > metric_config.threshold_warning:
                    recommendations.append(
                        f"{metric_config.name} dépasse le seuil d'avertissement: {value}"
                    )
                if metric_config.threshold_critical and value > metric_config.threshold_critical:
                    recommendations.append(
                        f"{metric_config.name} dépasse le seuil critique: {value}"
                    )

        return recommendations

    def _get_metric_config(self, metric_type: MetricType) -> Optional[MetricConfig]:
        """Obtient la configuration d'une métrique"""
        for metric in self.config.metrics:
            if metric.metric_type == metric_type:
                return metric
        return None

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

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

    def add_alert_callback(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les alertes

        Args:
            callback: Fonction callback
        """
        self._alert_callbacks.append(callback)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """
        Nettoie les ressources

        Cette méthode doit être appelée lors de l'arrêt
        """
        logger.info(f"Nettoyage de l'analyseur {self._analysis_id}")

        # Nettoyage des opérations actives
        for operation_id in list(self._active_operations.keys()):
            try:
                self._active_operations[operation_id]["status"] = "cancelled"
            except Exception as e:
                logger.warning(f"Erreur d'annulation de {operation_id}: {e}")

        # Nettoyage du cache
        self._cache.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info(f"Analyseur {self._analysis_id} nettoyé")

    # ============================================================
    # MÉTHODES DE CONTEXTE
    # ============================================================

    async def __aenter__(self):
        """Support du contexte async"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support du contexte async"""
        await self.cleanup()


# ============================================================
# DÉCORATEURS UTILITAIRES
# ============================================================

def log_operation(operation_type: str):
    """
    Décorateur pour logger les opérations

    Args:
        operation_type: Type d'opération
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            operation_id = self._generate_operation_id()
            self._operation_count += 1

            try:
                # Log de début
                await self.log_operation(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    details={"action": "start"},
                )

                # Exécution
                result = await func(self, *args, **kwargs)

                # Log de succès
                self._success_count += 1
                await self.log_operation(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    details={"action": "success"},
                )

                return result

            except Exception as e:
                # Log d'erreur
                await self.handle_error(e, operation_id)
                raise

        return wrapper
    return decorator


def measure_time():
    """
    Décorateur pour mesurer le temps d'exécution
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()

            try:
                result = await func(self, *args, **kwargs)
                elapsed = time.time() - start_time

                self.metrics.record_timing(
                    f"analysis_{func.__name__}_time",
                    elapsed,
                    {"analysis_id": self._analysis_id},
                )

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.debug(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
                raise

        return wrapper
    return decorator


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de la classe de base"""
    # Configuration
    config = AnalysisConfig(
        analysis_id="test_analysis",
        analysis_type=AnalysisType.CUSTOM,
        name="Test Analysis",
        description="Test analysis description",
        chain="ethereum",
        tokens=["ETH"],
        metrics=[],
        timeframe=3600,
        frequency=300,
    )

    # Création des dépendances (simplifiées)
    class SimpleNodeManager:
        async def get_nodes_by_protocol(self, protocol):
            return []

    class SimpleRPCClient:
        async def call(self, method, params, endpoint):
            return type('Response', (), {'is_success': lambda: True, 'result': {}})

    node_manager = SimpleNodeManager()
    rpc_client = SimpleRPCClient()

    # Création d'une implémentation de test
    class TestAnalyzer(BaseAnalyzer):
        async def analyze(self):
            return AnalysisResult(
                analysis_id=self._analysis_id,
                timestamp=datetime.now(),
                metrics={},
                status=AnalysisStatus.COMPLETED,
            )

        async def collect_data(self):
            return {"data": "test"}

        async def process_data(self, data):
            return {}

        async def generate_insights(self, metrics):
            return ["Test insight"]

    # Utilisation
    analyzer = TestAnalyzer(config, node_manager, rpc_client)

    # Exécution de l'analyse
    result = await analyzer.run()
    print(f"Résultat: {result.to_dict()}")

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

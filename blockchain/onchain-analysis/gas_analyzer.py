# blockchain/onchain-analysis/gas_analyzer.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Gas Analyzer - Analyse des Frais de Gaz

Ce module implémente un système complet d'analyse des frais de gaz sur
les blockchains, permettant le monitoring des prix, l'optimisation des
transactions, et la détection d'anomalies.

Fonctionnalités principales:
- Analyse des prix du gaz en temps réel
- Analyse des tendances de gaz
- Optimisation des transactions
- Détection d'anomalies
- Alertes de prix
- Support multi-chaînes
- Prédiction des prix
- Analyse de l'activité réseau
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

class GasPriceLevel(Enum):
    """Niveaux de prix du gaz"""
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"
    RAPID = "rapid"
    CRITICAL = "critical"


@dataclass
class GasData:
    """Données de gaz"""
    chain: str
    gas_price: int  # wei
    gas_price_gwei: Decimal  # gwei
    base_fee: Optional[int] = None
    priority_fee: Optional[int] = None
    max_fee_per_gas: Optional[int] = None
    max_priority_fee_per_gas: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "chain": self.chain,
            "gas_price": self.gas_price,
            "gas_price_gwei": str(self.gas_price_gwei),
            "base_fee": self.base_fee,
            "priority_fee": self.priority_fee,
            "max_fee_per_gas": self.max_fee_per_gas,
            "max_priority_fee_per_gas": self.max_priority_fee_per_gas,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class GasPrediction:
    """Prédiction de gaz"""
    chain: str
    predicted_gas_price: int
    confidence: float
    timeframe: int  # secondes
    current_gas_price: int
    trend: str  # up, down, stable
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "chain": self.chain,
            "predicted_gas_price": self.predicted_gas_price,
            "confidence": self.confidence,
            "timeframe": self.timeframe,
            "current_gas_price": self.current_gas_price,
            "trend": self.trend,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class GasAlert:
    """Alerte de gaz"""
    alert_id: str
    chain: str
    gas_price: int
    threshold: int
    condition: str  # gt, lt, gte, lte
    severity: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "alert_id": self.alert_id,
            "chain": self.chain,
            "gas_price": self.gas_price,
            "threshold": self.threshold,
            "condition": self.condition,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# SEUILS DE GAZ PAR CHAÎNE
# ============================================================

GAS_THRESHOLDS = {
    "ethereum": {
        "low": 20,  # gwei
        "standard": 40,
        "high": 80,
        "rapid": 150,
        "critical": 200,
    },
    "polygon": {
        "low": 30,  # gwei
        "standard": 50,
        "high": 100,
        "rapid": 200,
        "critical": 300,
    },
    "bsc": {
        "low": 3,  # gwei
        "standard": 5,
        "high": 10,
        "rapid": 20,
        "critical": 30,
    },
    "arbitrum": {
        "low": 0.1,  # gwei
        "standard": 0.2,
        "high": 0.5,
        "rapid": 1.0,
        "critical": 2.0,
    },
    "optimism": {
        "low": 0.01,  # gwei
        "standard": 0.02,
        "high": 0.05,
        "rapid": 0.1,
        "critical": 0.2,
    },
    "avalanche": {
        "low": 25,  # gwei
        "standard": 50,
        "high": 100,
        "rapid": 200,
        "critical": 300,
    },
    "base": {
        "low": 0.1,  # gwei
        "standard": 0.2,
        "high": 0.5,
        "rapid": 1.0,
        "critical": 2.0,
    },
    "solana": {
        "low": 0.0001,  # SOL
        "standard": 0.0002,
        "high": 0.0005,
        "rapid": 0.001,
        "critical": 0.002,
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class GasAnalyzer(BaseAnalyzer):
    """
    Analyseur des frais de gaz
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
        Initialise l'analyseur de gaz

        Args:
            config: Configuration de l'analyse
            node_manager: Gestionnaire de nœuds
            rpc_client: Client RPC
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, node_manager, rpc_client, metrics_collector, cache_ttl)

        self._gas_history: Dict[str, List[GasData]] = defaultdict(list)
        self._predictions: Dict[str, GasPrediction] = {}
        self._alerts: List[GasAlert] = []
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        logger.info(f"GasAnalyzer {config.name} initialisé")

    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def collect_data(self) -> Dict[str, Any]:
        """
        Collecte les données de gaz

        Returns:
            Données collectées
        """
        logger.info(f"Collecte des données de gaz pour {self.config.chain}")

        data = {}
        chain = self.config.chain

        try:
            # Récupération du prix du gaz
            gas_data = await self._get_gas_data(chain)
            data["gas_data"] = gas_data

            # Récupération de l'historique
            history = self._gas_history.get(chain, [])
            data["history"] = history[-100:]

            # Récupération des prédictions
            prediction = self._predictions.get(chain)
            if prediction:
                data["prediction"] = prediction

            # Niveau actuel
            level = self._get_gas_level(chain, gas_data.gas_price_gwei)
            data["level"] = level.value

        except Exception as e:
            logger.warning(f"Erreur de collecte de gaz: {e}")

        return data

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def process_data(self, data: Dict[str, Any]) -> Dict[MetricType, Any]:
        """
        Traite les données de gaz

        Args:
            data: Données collectées

        Returns:
            Métriques calculées
        """
        logger.info(f"Traitement des données de gaz")

        metrics = {}

        gas_data = data.get("gas_data")
        if gas_data:
            # Prix du gaz
            metrics[MetricType.PRICE_VOLATILITY] = gas_data.gas_price_gwei

            # Base fee
            if gas_data.base_fee:
                metrics[MetricType.GAS_USAGE] = gas_data.base_fee

            # Niveau
            level = data.get("level", "standard")
            metrics[MetricType.VOLUME_CHANGE] = self._level_to_score(level)

        # Analyse de l'historique
        history = data.get("history", [])
        if len(history) > 1:
            # Changement
            current = history[-1].gas_price_gwei
            previous = history[-2].gas_price_gwei
            change = ((current - previous) / previous) if previous > 0 else 0
            metrics[MetricType.VOLUME_24H] = change

            # Volatilité
            prices = [h.gas_price_gwei for h in history[-20:]]
            if prices:
                avg = sum(prices) / len(prices)
                volatility = sum(abs(p - avg) for p in prices) / len(prices)
                metrics[MetricType.PRICE_VOLATILITY] = volatility

        return metrics

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def generate_insights(self, metrics: Dict[MetricType, Any]) -> List[str]:
        """
        Génère des insights à partir des données de gaz

        Args:
            metrics: Métriques calculées

        Returns:
            Liste des insights
        """
        insights = []

        # Analyse du prix du gaz
        if MetricType.PRICE_VOLATILITY in metrics:
            gas_price = metrics[MetricType.PRICE_VOLATILITY]
            chain = self.config.chain

            level = self._get_gas_level(chain, gas_price)

            if level == GasPriceLevel.LOW:
                insights.append(f"Prix du gaz bas sur {chain}: {gas_price:.1f} Gwei")
            elif level == GasPriceLevel.HIGH:
                insights.append(f"Prix du gaz élevé sur {chain}: {gas_price:.1f} Gwei")
            elif level == GasPriceLevel.CRITICAL:
                insights.append(f"CRITIQUE: Prix du gaz très élevé sur {chain}: {gas_price:.1f} Gwei")

        # Tendance
        if MetricType.VOLUME_24H in metrics:
            change = metrics[MetricType.VOLUME_24H]
            if change > Decimal("0.2"):
                insights.append(f"Augmentation significative du prix du gaz: {change:.1%}")
            elif change < -Decimal("0.2"):
                insights.append(f"Diminution significative du prix du gaz: {change:.1%}")

        return insights

    # ============================================================
    # MÉTHODES DE COLLECTE DE GAZ
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def _get_gas_data(self, chain: str) -> GasData:
        """
        Récupère les données de gaz

        Args:
            chain: Chaîne

        Returns:
            Données de gaz
        """
        try:
            # Récupération du prix du gaz
            gas_price = await self._get_gas_price(chain)
            gas_price_gwei = Decimal(str(gas_price)) / Decimal(1e9)

            # Récupération du base fee (EIP-1559)
            base_fee = await self._get_base_fee(chain)

            # Récupération du priority fee
            priority_fee = await self._get_priority_fee(chain)

            gas_data = GasData(
                chain=chain,
                gas_price=gas_price,
                gas_price_gwei=gas_price_gwei,
                base_fee=base_fee,
                priority_fee=priority_fee,
                max_fee_per_gas=gas_price * 2,
                max_priority_fee_per_gas=priority_fee,
                timestamp=datetime.now(),
            )

            # Stockage de l'historique
            self._gas_history[chain].append(gas_data)

            # Limitation de l'historique
            if len(self._gas_history[chain]) > 1000:
                self._gas_history[chain] = self._gas_history[chain][-500:]

            return gas_data

        except Exception as e:
            logger.error(f"Erreur de récupération des données de gaz: {e}")
            raise AnalysisError(f"Erreur de récupération des données de gaz: {e}")

    async def _get_gas_price(self, chain: str) -> int:
        """
        Récupère le prix du gaz

        Args:
            chain: Chaîne

        Returns:
            Prix du gaz en wei
        """
        try:
            result = await self._make_rpc_call(
                RPCMethod.ETH_GET_GAS_PRICE,
                [],
            )

            return int(result, 16) if result else 0

        except Exception as e:
            logger.warning(f"Erreur de récupération du prix du gaz: {e}")
            return 0

    async def _get_base_fee(self, chain: str) -> Optional[int]:
        """
        Récupère le base fee

        Args:
            chain: Chaîne

        Returns:
            Base fee en wei
        """
        try:
            # Récupération du dernier bloc
            block = await self._make_rpc_call(
                RPCMethod.ETH_GET_BLOCK_BY_NUMBER,
                ["latest", False],
            )

            if block and "baseFeePerGas" in block:
                return int(block["baseFeePerGas"], 16)

            return None

        except Exception as e:
            logger.warning(f"Erreur de récupération du base fee: {e}")
            return None

    async def _get_priority_fee(self, chain: str) -> Optional[int]:
        """
        Récupère le priority fee

        Args:
            chain: Chaîne

        Returns:
            Priority fee en wei
        """
        try:
            # Simulé - dans la réalité, on utiliserait fee_history
            return 1000000000  # 1 Gwei

        except Exception as e:
            logger.warning(f"Erreur de récupération du priority fee: {e}")
            return None

    # ============================================================
    # MÉTHODES DE PRÉDICTION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def predict_gas_price(
        self,
        chain: str,
        timeframe: int = 3600,
    ) -> GasPrediction:
        """
        Prédit le prix du gaz

        Args:
            chain: Chaîne
            timeframe: Période de prédiction en secondes

        Returns:
            Prédiction de gaz
        """
        logger.info(f"Prédiction du prix du gaz pour {chain}")

        try:
            history = self._gas_history.get(chain, [])

            if len(history) < 10:
                raise AnalysisError("Pas assez de données pour la prédiction")

            # Récupération des prix récents
            prices = [h.gas_price_gwei for h in history[-30:]]

            # Calcul de la tendance
            if len(prices) > 1:
                change = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0

                if change > 0.05:
                    trend = "up"
                elif change < -0.05:
                    trend = "down"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            # Prédiction simple
            if trend == "up":
                predicted_price = prices[-1] * (1 + 0.1)
            elif trend == "down":
                predicted_price = prices[-1] * (1 - 0.1)
            else:
                predicted_price = prices[-1] * (1 + 0.02)

            confidence = 0.7

            prediction = GasPrediction(
                chain=chain,
                predicted_gas_price=int(predicted_price * 1e9),
                confidence=confidence,
                timeframe=timeframe,
                current_gas_price=int(prices[-1] * 1e9),
                trend=trend,
                timestamp=datetime.now(),
            )

            self._predictions[chain] = prediction

            return prediction

        except Exception as e:
            logger.error(f"Erreur de prédiction du gaz: {e}")
            raise AnalysisError(f"Erreur de prédiction du gaz: {e}")

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def check_alerts(self, chain: str) -> List[GasAlert]:
        """
        Vérifie les alertes de gaz

        Args:
            chain: Chaîne

        Returns:
            Liste des alertes
        """
        gas_data = await self._get_gas_data(chain)
        gas_price_gwei = gas_data.gas_price_gwei

        alerts = []
        thresholds = GAS_THRESHOLDS.get(chain, {})

        for level, threshold in thresholds.items():
            if gas_price_gwei > threshold:
                severity = "critical" if level == "critical" else "warning"

                alert = GasAlert(
                    alert_id=f"gas_alert_{uuid.uuid4().hex[:12]}",
                    chain=chain,
                    gas_price=int(gas_price_gwei * 1e9),
                    threshold=int(threshold * 1e9),
                    condition="gt",
                    severity=severity,
                    message=f"Prix du gaz {level} sur {chain}: {gas_price_gwei:.1f} Gwei",
                    timestamp=datetime.now(),
                )

                alerts.append(alert)
                self._alerts.append(alert)

                # Envoi de l'alerte
                await self._send_alert(alert.to_dict())

        return alerts

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_gas_level(self, chain: str, gas_price_gwei: Decimal) -> GasPriceLevel:
        """
        Obtient le niveau de prix du gaz

        Args:
            chain: Chaîne
            gas_price_gwei: Prix en Gwei

        Returns:
            Niveau de prix
        """
        thresholds = GAS_THRESHOLDS.get(chain, {})

        if gas_price_gwei >= thresholds.get("critical", float('inf')):
            return GasPriceLevel.CRITICAL
        elif gas_price_gwei >= thresholds.get("rapid", float('inf')):
            return GasPriceLevel.RAPID
        elif gas_price_gwei >= thresholds.get("high", float('inf')):
            return GasPriceLevel.HIGH
        elif gas_price_gwei >= thresholds.get("standard", float('inf')):
            return GasPriceLevel.STANDARD
        else:
            return GasPriceLevel.LOW

    def _level_to_score(self, level: str) -> Decimal:
        """
        Convertit un niveau en score

        Args:
            level: Niveau

        Returns:
            Score
        """
        scores = {
            "low": Decimal("0.2"),
            "standard": Decimal("0.5"),
            "high": Decimal("0.7"),
            "rapid": Decimal("0.9"),
            "critical": Decimal("1.0"),
        }
        return scores.get(level, Decimal("0.5"))

    # ============================================================
    # MÉTHODE D'ANALYSE PRINCIPALE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def analyze(self) -> AnalysisResult:
        """
        Exécute l'analyse du gaz

        Returns:
            Résultat de l'analyse
        """
        return await self.run()


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_gas_analyzer(
    config: AnalysisConfig,
    node_manager: NodeManager,
    rpc_client: NodeRPCClient,
    **kwargs,
) -> GasAnalyzer:
    """
    Crée une instance de GasAnalyzer

    Args:
        config: Configuration de l'analyse
        node_manager: Gestionnaire de nœuds
        rpc_client: Client RPC
        **kwargs: Arguments additionnels

    Returns:
        Instance de GasAnalyzer
    """
    return GasAnalyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de GasAnalyzer"""
    # Configuration
    config = AnalysisConfig(
        analysis_id="gas_analysis_1",
        analysis_type=AnalysisType.CUSTOM,
        name="Gas Price Analysis",
        description="Analysis of gas prices",
        chain="ethereum",
        tokens=[],
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
            return type('Response', (), {'is_success': lambda: True, 'result': '0x' + hex(1000000000)[2:]})

    node_manager = SimpleNodeManager()
    rpc_client = SimpleRPCClient()

    # Création de l'analyseur
    analyzer = create_gas_analyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
    )

    # Exécution de l'analyse
    result = await analyzer.analyze()
    print(f"Résultat: {result.to_dict()}")

    # Prédiction du gaz
    prediction = await analyzer.predict_gas_price("ethereum", 3600)
    print(f"Prédiction: {prediction.to_dict()}")

    # Vérification des alertes
    alerts = await analyzer.check_alerts("ethereum")
    print(f"Alertes: {len(alerts)}")

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

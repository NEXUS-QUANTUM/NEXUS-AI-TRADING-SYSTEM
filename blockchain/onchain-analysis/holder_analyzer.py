# blockchain/onchain-analysis/holder_analyzer.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Holder Analyzer - Analyse des Holders de Tokens

Ce module implémente un système complet d'analyse des holders de tokens,
permettant l'analyse de la distribution, des concentrations, des mouvements,
et des tendances des détenteurs.

Fonctionnalités principales:
- Analyse de la distribution des holders
- Analyse de la concentration
- Tracking des mouvements de holders
- Analyse des whales
- Analyse des tendances
- Détection d'accumulation/distribution
- Support multi-tokens
- Alertes de mouvements
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

class HolderCategory(Enum):
    """Catégories de holders"""
    WHALE = "whale"  # > 1% du supply
    LARGE = "large"  # 0.1% - 1%
    MEDIUM = "medium"  # 0.01% - 0.1%
    SMALL = "small"  # 0.001% - 0.01%
    MICRO = "micro"  # < 0.001%
    UNKNOWN = "unknown"


class HolderAction(Enum):
    """Actions des holders"""
    ACCUMULATING = "accumulating"
    DISTRIBUTING = "distributing"
    HOLDING = "holding"
    INACTIVE = "inactive"


@dataclass
class Holder:
    """Détenteur de token"""
    address: str
    balance: Decimal
    percentage: Decimal
    category: HolderCategory
    action: HolderAction
    first_seen: datetime
    last_active: datetime
    transaction_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "balance": str(self.balance),
            "percentage": str(self.percentage),
            "category": self.category.value,
            "action": self.action.value,
            "first_seen": self.first_seen.isoformat(),
            "last_active": self.last_active.isoformat(),
            "transaction_count": self.transaction_count,
            "metadata": self.metadata,
        }


@dataclass
class HolderStats:
    """Statistiques des holders"""
    token: str
    chain: str
    total_supply: Decimal
    total_holders: int
    active_holders: int
    new_holders_24h: int
    whale_count: int
    whale_percentage: Decimal
    concentration_index: float  # 0-1
    top_10_percentage: Decimal
    top_50_percentage: Decimal
    top_100_percentage: Decimal
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "token": self.token,
            "chain": self.chain,
            "total_supply": str(self.total_supply),
            "total_holders": self.total_holders,
            "active_holders": self.active_holders,
            "new_holders_24h": self.new_holders_24h,
            "whale_count": self.whale_count,
            "whale_percentage": str(self.whale_percentage),
            "concentration_index": self.concentration_index,
            "top_10_percentage": str(self.top_10_percentage),
            "top_50_percentage": str(self.top_50_percentage),
            "top_100_percentage": str(self.top_100_percentage),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class HolderAlert:
    """Alerte de holder"""
    alert_id: str
    token: str
    chain: str
    address: str
    event_type: str  # whale_movement, accumulation, distribution
    amount: Decimal
    percentage: Decimal
    severity: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "alert_id": self.alert_id,
            "token": self.token,
            "chain": self.chain,
            "address": self.address,
            "event_type": self.event_type,
            "amount": str(self.amount),
            "percentage": str(self.percentage),
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class HolderAnalyzer(BaseAnalyzer):
    """
    Analyseur des holders de tokens
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
        Initialise l'analyseur de holders

        Args:
            config: Configuration de l'analyse
            node_manager: Gestionnaire de nœuds
            rpc_client: Client RPC
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, node_manager, rpc_client, metrics_collector, cache_ttl)

        self._holders: Dict[str, Dict[str, Holder]] = defaultdict(dict)
        self._holder_stats: Dict[str, HolderStats] = {}
        self._alerts: List[HolderAlert] = []
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        logger.info(f"HolderAnalyzer {config.name} initialisé")

    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def collect_data(self) -> Dict[str, Any]:
        """
        Collecte les données des holders

        Returns:
            Données collectées
        """
        logger.info(f"Collecte des données des holders pour {self.config.chain}")

        data = {}
        chain = self.config.chain
        tokens = self.config.tokens

        for token in tokens:
            try:
                # Récupération des holders
                holders_data = await self._get_holders_data(token, chain)
                if holders_data:
                    data[token] = holders_data

                # Récupération des statistiques
                stats = await self._get_holder_stats(token, chain)
                if stats:
                    data[f"{token}_stats"] = stats

            except Exception as e:
                logger.warning(f"Erreur pour {token}: {e}")

        return data

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def process_data(self, data: Dict[str, Any]) -> Dict[MetricType, Any]:
        """
        Traite les données des holders

        Args:
            data: Données collectées

        Returns:
            Métriques calculées
        """
        logger.info(f"Traitement des données des holders")

        metrics = {}

        for token, token_data in data.items():
            if isinstance(token_data, HolderStats):
                stats = token_data

                # Concentration
                metrics[MetricType.WHALE_CONCENTRATION] = stats.concentration_index

                # Nombre de whales
                metrics[MetricType.WHALE_TRANSACTIONS] = stats.whale_count

                # Nouveaux holders
                metrics[MetricType.NETWORK_GROWTH] = stats.new_holders_24h

                # Active holders
                metrics[MetricType.ACTIVE_ADDRESSES] = stats.active_holders

        return metrics

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def generate_insights(self, metrics: Dict[MetricType, Any]) -> List[str]:
        """
        Génère des insights à partir des données des holders

        Args:
            metrics: Métriques calculées

        Returns:
            Liste des insights
        """
        insights = []

        # Analyse de la concentration
        if MetricType.WHALE_CONCENTRATION in metrics:
            concentration = metrics[MetricType.WHALE_CONCENTRATION]
            if concentration > 0.5:
                insights.append(f"Concentration élevée: {concentration:.1%}")

        # Analyse des whales
        if MetricType.WHALE_TRANSACTIONS in metrics:
            whale_count = metrics[MetricType.WHALE_TRANSACTIONS]
            if whale_count > 10:
                insights.append(f"Nombre élevé de whales: {whale_count}")

        # Analyse de la croissance
        if MetricType.NETWORK_GROWTH in metrics:
            growth = metrics[MetricType.NETWORK_GROWTH]
            if growth > 100:
                insights.append(f"Forte croissance des holders: {growth} nouveaux")

        return insights

    # ============================================================
    # MÉTHODES DE COLLECTE DE DONNÉES
    # ============================================================

    async def _get_holders_data(
        self,
        token: str,
        chain: str,
        limit: int = 1000,
    ) -> List[Holder]:
        """
        Récupère les données des holders

        Args:
            token: Symbole du token
            chain: Chaîne
            limit: Nombre maximum de holders

        Returns:
            Liste des holders
        """
        try:
            # Récupération de l'adresse du token
            token_address = await self._get_token_address(token, chain)

            # Récupération du total supply
            total_supply = await self._get_token_supply(token_address, chain)

            # Simulation de holders
            holders = []

            # Pour l'exemple, on crée des holders simulés
            for i in range(min(limit, 50)):
                address = f"0x{hash(str(i)):040x}"

                # Balance simulée
                if i < 10:
                    # Whales
                    balance = total_supply * Decimal(str(0.05 - (i * 0.004)))
                    category = HolderCategory.WHALE
                elif i < 30:
                    # Large holders
                    balance = total_supply * Decimal(str(0.008 - (i * 0.0002)))
                    category = HolderCategory.LARGE
                else:
                    # Medium holders
                    balance = total_supply * Decimal(str(0.0005 - (i * 0.00001)))
                    category = HolderCategory.MEDIUM

                if balance < 0:
                    balance = Decimal("0")

                percentage = (balance / total_supply) if total_supply > 0 else Decimal("0")

                holder = Holder(
                    address=address,
                    balance=balance,
                    percentage=percentage,
                    category=category,
                    action=HolderAction.HOLDING,
                    first_seen=datetime.now() - timedelta(days=30),
                    last_active=datetime.now(),
                    transaction_count=10 + i,
                )

                holders.append(holder)
                self._holders[token][address] = holder

            return holders

        except Exception as e:
            logger.warning(f"Erreur de récupération des holders: {e}")
            return []

    async def _get_holder_stats(self, token: str, chain: str) -> Optional[HolderStats]:
        """
        Récupère les statistiques des holders

        Args:
            token: Symbole du token
            chain: Chaîne

        Returns:
            Statistiques des holders
        """
        try:
            holders = list(self._holders.get(token, {}).values())
            if not holders:
                return None

            # Calcul du total supply
            total_supply = await self._get_token_supply_from_holders(holders)

            # Catégorisation
            whales = [h for h in holders if h.category == HolderCategory.WHALE]
            active = [h for h in holders if h.last_active > datetime.now() - timedelta(days=7)]

            # Concentration
            sorted_holders = sorted(holders, key=lambda x: x.balance, reverse=True)
            top_10 = sum(h.balance for h in sorted_holders[:10])
            top_50 = sum(h.balance for h in sorted_holders[:50])
            top_100 = sum(h.balance for h in sorted_holders[:100])

            # Index de concentration (HHI simplifié)
            concentration_index = sum(
                (float(h.balance / total_supply) ** 2)
                for h in holders[:100]
                if total_supply > 0
            )

            return HolderStats(
                token=token,
                chain=chain,
                total_supply=total_supply,
                total_holders=len(holders),
                active_holders=len(active),
                new_holders_24h=len([h for h in holders if h.first_seen > datetime.now() - timedelta(days=1)]),
                whale_count=len(whales),
                whale_percentage=(sum(h.balance for h in whales) / total_supply) if total_supply > 0 else Decimal("0"),
                concentration_index=concentration_index,
                top_10_percentage=(top_10 / total_supply) if total_supply > 0 else Decimal("0"),
                top_50_percentage=(top_50 / total_supply) if total_supply > 0 else Decimal("0"),
                top_100_percentage=(top_100 / total_supply) if total_supply > 0 else Decimal("0"),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.warning(f"Erreur de calcul des statistiques: {e}")
            return None

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_token_address(self, token: str, chain: str) -> str:
        """
        Obtient l'adresse du token

        Args:
            token: Symbole du token
            chain: Chaîne

        Returns:
            Adresse du token
        """
        # Mapping des tokens connus
        token_addresses = {
            "ethereum": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            },
            "bsc": {
                "BNB": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
                "USDT": "0x55d398326f99059fF775485246999027B3197955",
            },
            "polygon": {
                "MATIC": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            },
        }

        return token_addresses.get(chain, {}).get(token, token)

    async def _get_token_supply(self, token_address: str, chain: str) -> Decimal:
        """
        Récupère le total supply d'un token

        Args:
            token_address: Adresse du token
            chain: Chaîne

        Returns:
            Total supply
        """
        try:
            if token_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                # Token natif - total supply approximatif
                return Decimal("100000000")  # 100 millions

            # ERC-20 totalSupply
            result = await self._make_rpc_call(
                RPCMethod.ETH_CALL,
                [{
                    "to": token_address,
                    "data": "0x18160ddd",
                }, "latest"],
            )

            if result:
                return Decimal(str(int(result, 16))) / Decimal(1e18)

            return Decimal("0")

        except Exception as e:
            logger.warning(f"Erreur de récupération du total supply: {e}")
            return Decimal("0")

    async def _get_token_supply_from_holders(self, holders: List[Holder]) -> Decimal:
        """
        Calcule le total supply à partir des holders

        Args:
            holders: Liste des holders

        Returns:
            Total supply estimé
        """
        if not holders:
            return Decimal("0")

        # Somme des balances des holders
        total = sum(h.balance for h in holders)

        # Estimation du total supply
        # Dans la réalité, on utiliserait le totalSupply du contrat
        return total

    # ============================================================
    # MÉTHODES D'ANALYSE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def analyze_whale_movements(
        self,
        token: str,
        chain: str,
        threshold: Decimal = Decimal("100000"),
    ) -> List[HolderAlert]:
        """
        Analyse les mouvements des whales

        Args:
            token: Symbole du token
            chain: Chaîne
            threshold: Seuil en USD

        Returns:
            Liste des alertes
        """
        logger.info(f"Analyse des mouvements de whales pour {token}")

        alerts = []
        holders = self._holders.get(token, {})

        for address, holder in holders.items():
            if holder.category == HolderCategory.WHALE:
                if holder.action in [HolderAction.ACCUMULATING, HolderAction.DISTRIBUTING]:
                    alert = HolderAlert(
                        alert_id=f"whale_alert_{uuid.uuid4().hex[:12]}",
                        token=token,
                        chain=chain,
                        address=address,
                        event_type=holder.action.value,
                        amount=holder.balance * Decimal("0.01"),  # 1% du solde
                        percentage=holder.percentage * Decimal("0.01"),
                        severity="warning",
                        message=f"Whale {holder.action.value}: {address[:8]}...",
                        timestamp=datetime.now(),
                    )

                    alerts.append(alert)
                    self._alerts.append(alert)

                    # Envoi de l'alerte
                    await self._send_alert(alert.to_dict())

        return alerts

    # ============================================================
    # MÉTHODE D'ANALYSE PRINCIPALE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def analyze(self) -> AnalysisResult:
        """
        Exécute l'analyse des holders

        Returns:
            Résultat de l'analyse
        """
        return await self.run()


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_holder_analyzer(
    config: AnalysisConfig,
    node_manager: NodeManager,
    rpc_client: NodeRPCClient,
    **kwargs,
) -> HolderAnalyzer:
    """
    Crée une instance de HolderAnalyzer

    Args:
        config: Configuration de l'analyse
        node_manager: Gestionnaire de nœuds
        rpc_client: Client RPC
        **kwargs: Arguments additionnels

    Returns:
        Instance de HolderAnalyzer
    """
    return HolderAnalyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de HolderAnalyzer"""
    # Configuration
    config = AnalysisConfig(
        analysis_id="holder_analysis_1",
        analysis_type=AnalysisType.CUSTOM,
        name="Holder Analysis",
        description="Analysis of token holders",
        chain="ethereum",
        tokens=["USDC", "USDT"],
        metrics=[],
        timeframe=86400,
        frequency=3600,
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
    analyzer = create_holder_analyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
    )

    # Exécution de l'analyse
    result = await analyzer.analyze()
    print(f"Résultat: {result.to_dict()}")

    # Analyse des mouvements de whales
    alerts = await analyzer.analyze_whale_movements("USDC", "ethereum")
    print(f"Alertes whales: {len(alerts)}")

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

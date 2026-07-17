# blockchain/onchain-analysis/defi_analyzer.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module DeFi Analyzer - Analyse des Protocoles DeFi

Ce module implémente des analyseurs spécialisés pour les protocoles DeFi,
permettant l'analyse des TVL, des volumes, des taux d'intérêt,
des positions, et des métriques de performance.

Fonctionnalités principales:
- Analyse des TVL (Total Value Locked)
- Analyse des volumes de trading
- Analyse des taux d'intérêt
- Analyse des positions
- Analyse des risques
- Analyse des rendements
- Monitoring des protocoles
- Alertes de performance
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
    from ..defi.base_protocol import BaseProtocol
    from ..defi.aave import AaveIntegration
    from ..defi.compound import CompoundIntegration
    from ..defi.curve import CurveIntegration
    from ..defi.uniswap import UniswapIntegration
    from ..defi.defi_manager import DeFiManager
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
    from ..defi.base_protocol import BaseProtocol
    from ..defi.aave import AaveIntegration
    from ..defi.compound import CompoundIntegration
    from ..defi.curve import CurveIntegration
    from ..defi.uniswap import UniswapIntegration
    from ..defi.defi_manager import DeFiManager
    from .base_analyzer import BaseAnalyzer, AnalysisResult, AnalysisStatus
    from .analysis_config import AnalysisConfig, MetricType, AnalysisType

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class DeFiProtocol(Enum):
    """Protocoles DeFi supportés"""
    AAVE = "aave"
    COMPOUND = "compound"
    CURVE = "curve"
    UNISWAP = "uniswap"
    MAKER = "maker"
    LIDO = "lido"
    YEARN = "yearn"
    CONVEX = "convex"
    BALANCER = "balancer"


@dataclass
class DeFiMetrics:
    """Métriques DeFi"""
    protocol: str
    chain: str
    tvl: Decimal
    volume_24h: Decimal
    volume_7d: Decimal
    volume_30d: Decimal
    apy: Decimal
    total_users: int
    active_users: int
    total_transactions: int
    tvl_change_24h: Decimal
    tvl_change_7d: Decimal
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol,
            "chain": self.chain,
            "tvl": str(self.tvl),
            "volume_24h": str(self.volume_24h),
            "volume_7d": str(self.volume_7d),
            "volume_30d": str(self.volume_30d),
            "apy": str(self.apy),
            "total_users": self.total_users,
            "active_users": self.active_users,
            "total_transactions": self.total_transactions,
            "tvl_change_24h": str(self.tvl_change_24h),
            "tvl_change_7d": str(self.tvl_change_7d),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CONFIGURATION DES PROTOCOLES
# ============================================================

PROTOCOL_CONFIGS = {
    DeFiProtocol.AAVE: {
        "chains": ["ethereum", "polygon", "arbitrum", "optimism", "avalanche", "base"],
        "tokens": ["USDC", "USDT", "DAI", "WETH", "WBTC", "MATIC", "AVAX"],
        "contracts": {
            "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        },
    },
    DeFiProtocol.COMPOUND: {
        "chains": ["ethereum", "polygon", "arbitrum", "optimism", "base"],
        "tokens": ["USDC", "USDT", "WETH", "WBTC"],
        "contracts": {
            "comet": "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
        },
    },
    DeFiProtocol.CURVE: {
        "chains": ["ethereum", "polygon", "arbitrum", "optimism"],
        "tokens": ["3CRV", "stETH", "CRV"],
        "contracts": {
            "pool": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",
        },
    },
    DeFiProtocol.UNISWAP: {
        "chains": ["ethereum", "polygon", "arbitrum", "optimism", "base"],
        "tokens": ["UNI", "ETH-USDC", "ETH-USDT"],
        "contracts": {
            "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        },
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class DeFiAnalyzer(BaseAnalyzer):
    """
    Analyseur spécialisé pour les protocoles DeFi
    """

    def __init__(
        self,
        config: AnalysisConfig,
        node_manager: NodeManager,
        rpc_client: NodeRPCClient,
        defi_manager: Optional[DeFiManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise l'analyseur DeFi

        Args:
            config: Configuration de l'analyse
            node_manager: Gestionnaire de nœuds
            rpc_client: Client RPC
            defi_manager: Gestionnaire DeFi
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, node_manager, rpc_client, metrics_collector, cache_ttl)

        self.defi_manager = defi_manager or DeFiManager(
            config={},
            wallet_manager=wallet_manager,
            web3_providers={},
        )
        self._protocol_instances: Dict[str, Dict[str, Any]] = {}
        self._metrics_cache: Dict[str, Tuple[float, DeFiMetrics]] = {}

        # Initialisation des instances de protocoles
        self._initialize_protocols()

        logger.info(f"DeFiAnalyzer {config.name} initialisé")

    def _initialize_protocols(self) -> None:
        """Initialise les instances des protocoles"""
        try:
            # Aave
            if DeFiProtocol.AAVE.value in self.config.tokens or not self.config.tokens:
                self._protocol_instances[DeFiProtocol.AAVE.value] = {
                    "ethereum": AaveIntegration(
                        config={},
                        wallet_manager=None,
                        web3_providers={},
                    ),
                }

            # Compound
            if DeFiProtocol.COMPOUND.value in self.config.tokens or not self.config.tokens:
                self._protocol_instances[DeFiProtocol.COMPOUND.value] = {
                    "ethereum": CompoundIntegration(
                        config={},
                        wallet_manager=None,
                        web3_providers={},
                    ),
                }

            # Curve
            if DeFiProtocol.CURVE.value in self.config.tokens or not self.config.tokens:
                self._protocol_instances[DeFiProtocol.CURVE.value] = {
                    "ethereum": CurveIntegration(
                        config={},
                        wallet_manager=None,
                        web3_providers={},
                    ),
                }

            # Uniswap
            if DeFiProtocol.UNISWAP.value in self.config.tokens or not self.config.tokens:
                self._protocol_instances[DeFiProtocol.UNISWAP.value] = {
                    "ethereum": UniswapIntegration(
                        config={},
                        wallet_manager=None,
                        web3_providers={},
                    ),
                }

            logger.info(f"Instances de protocoles initialisées: {list(self._protocol_instances.keys())}")

        except Exception as e:
            logger.error(f"Erreur d'initialisation des protocoles: {e}")
            raise AnalysisError(f"Erreur d'initialisation des protocoles: {e}")

    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def collect_data(self) -> Dict[str, Any]:
        """
        Collecte les données DeFi

        Returns:
            Données collectées
        """
        logger.info(f"Collecte des données DeFi pour {self.config.chain}")

        data = {}
        protocols = self.config.tokens or list(self._protocol_instances.keys())

        for protocol_name in protocols:
            try:
                protocol_data = await self._collect_protocol_data(
                    protocol_name,
                    self.config.chain,
                )
                if protocol_data:
                    data[protocol_name] = protocol_data

            except Exception as e:
                logger.warning(f"Erreur de collecte pour {protocol_name}: {e}")

        return data

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def process_data(self, data: Dict[str, Any]) -> Dict[MetricType, Any]:
        """
        Traite les données DeFi collectées

        Args:
            data: Données collectées

        Returns:
            Métriques calculées
        """
        logger.info(f"Traitement des données DeFi")

        metrics = {}

        for protocol_name, protocol_data in data.items():
            # TVL
            if "tvl" in protocol_data:
                metrics[MetricType.VOLUME_24H] = protocol_data["tvl"]

            # Volume
            if "volume_24h" in protocol_data:
                metrics[MetricType.VOLUME_24H] = protocol_data["volume_24h"]

            # APY
            if "apy" in protocol_data:
                metrics[MetricType.PRICE_VOLATILITY] = protocol_data["apy"]

            # Utilisateurs
            if "active_users" in protocol_data:
                metrics[MetricType.ACTIVE_ADDRESSES] = protocol_data["active_users"]

            # Risque
            risk_score = await self._calculate_risk_score(protocol_data)
            metrics[MetricType.RISK_SCORE] = risk_score

            # Liquidité
            liquidity = await self._calculate_liquidity(protocol_data)
            metrics[MetricType.LIQUIDITY_24H] = liquidity

        return metrics

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def generate_insights(self, metrics: Dict[MetricType, Any]) -> List[str]:
        """
        Génère des insights à partir des métriques DeFi

        Args:
            metrics: Métriques calculées

        Returns:
            Liste des insights
        """
        insights = []

        # Analyse de la TVL
        if MetricType.VOLUME_24H in metrics:
            tvl = metrics[MetricType.VOLUME_24H]
            if tvl > Decimal("1000000000"):
                insights.append(f"TVL élevée: ${tvl:,.0f} (plus d'1 milliard)")
            elif tvl > Decimal("100000000"):
                insights.append(f"TVL significative: ${tvl:,.0f}")

        # Analyse du volume
        if MetricType.VOLUME_24H in metrics:
            volume = metrics[MetricType.VOLUME_24H]
            if volume > Decimal("100000000"):
                insights.append(f"Volume 24h élevé: ${volume:,.0f}")

        # Analyse du risque
        if MetricType.RISK_SCORE in metrics:
            risk = metrics[MetricType.RISK_SCORE]
            if risk > 70:
                insights.append(f"Score de risque élevé: {risk}/100")
            elif risk > 50:
                insights.append(f"Score de risque modéré: {risk}/100")

        # Analyse de l'APY
        if MetricType.PRICE_VOLATILITY in metrics:
            apy = metrics[MetricType.PRICE_VOLATILITY]
            if apy > Decimal("0.1"):
                insights.append(f"APY élevé: {apy:.2%}")

        return insights

    # ============================================================
    # MÉTHODES DE COLLECTE DE DONNÉES
    # ============================================================

    async def _collect_protocol_data(
        self,
        protocol_name: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Collecte les données d'un protocole spécifique

        Args:
            protocol_name: Nom du protocole
            chain: Chaîne

        Returns:
            Données du protocole
        """
        try:
            # Récupération des instances du protocole
            protocol_instances = self._protocol_instances.get(protocol_name, {})
            protocol_instance = protocol_instances.get(chain)

            if not protocol_instance:
                return {}

            # Collecte selon le protocole
            if protocol_name == DeFiProtocol.AAVE.value:
                return await self._collect_aave_data(protocol_instance, chain)
            elif protocol_name == DeFiProtocol.COMPOUND.value:
                return await self._collect_compound_data(protocol_instance, chain)
            elif protocol_name == DeFiProtocol.CURVE.value:
                return await self._collect_curve_data(protocol_instance, chain)
            elif protocol_name == DeFiProtocol.UNISWAP.value:
                return await self._collect_uniswap_data(protocol_instance, chain)
            else:
                return await self._collect_generic_data(protocol_instance, chain)

        except Exception as e:
            logger.warning(f"Erreur de collecte pour {protocol_name}: {e}")
            return {}

    async def _collect_aave_data(self, instance: AaveIntegration, chain: str) -> Dict[str, Any]:
        """Collecte les données Aave"""
        data = {}

        try:
            # Récupération des réserves
            reserves = {}
            for token in self.config.tokens:
                try:
                    reserve = await instance.get_reserve_data(token, chain)
                    reserves[token] = reserve
                except Exception as e:
                    logger.warning(f"Erreur pour {token}: {e}")

            if reserves:
                # Calcul de la TVL
                total_tvl = sum(r.total_liquidity for r in reserves.values())
                data["tvl"] = total_tvl

                # Volume 24h (simulé)
                data["volume_24h"] = total_tvl * Decimal("0.01")

                # APY moyen
                avg_apy = sum(r.supply_rate for r in reserves.values()) / len(reserves)
                data["apy"] = avg_apy

                # Utilisateurs (simulé)
                data["total_users"] = 10000
                data["active_users"] = 1000

                # TVL change
                data["tvl_change_24h"] = Decimal("0.02")
                data["tvl_change_7d"] = Decimal("0.05")

        except Exception as e:
            logger.warning(f"Erreur Aave: {e}")

        return data

    async def _collect_compound_data(self, instance: CompoundIntegration, chain: str) -> Dict[str, Any]:
        """Collecte les données Compound"""
        data = {}

        try:
            # Récupération des réserves
            reserves = {}
            for token in self.config.tokens:
                try:
                    reserve = await instance.get_reserve_data(token, chain)
                    reserves[token] = reserve
                except Exception as e:
                    logger.warning(f"Erreur pour {token}: {e}")

            if reserves:
                total_supply = sum(r.total_supply for r in reserves.values())
                data["tvl"] = total_supply
                data["volume_24h"] = total_supply * Decimal("0.008")
                data["apy"] = Decimal("0.04")
                data["total_users"] = 5000
                data["active_users"] = 500
                data["tvl_change_24h"] = Decimal("0.015")
                data["tvl_change_7d"] = Decimal("0.04")

        except Exception as e:
            logger.warning(f"Erreur Compound: {e}")

        return data

    async def _collect_curve_data(self, instance: CurveIntegration, chain: str) -> Dict[str, Any]:
        """Collecte les données Curve"""
        data = {}

        try:
            # Récupération des pools
            pool = await instance.get_pool_data("3pool", chain)

            if pool:
                data["tvl"] = pool.tvl
                data["volume_24h"] = pool.volume_24h
                data["apy"] = pool.apy
                data["total_users"] = 3000
                data["active_users"] = 300
                data["tvl_change_24h"] = Decimal("0.03")
                data["tvl_change_7d"] = Decimal("0.07")

        except Exception as e:
            logger.warning(f"Erreur Curve: {e}")

        return data

    async def _collect_uniswap_data(self, instance: UniswapIntegration, chain: str) -> Dict[str, Any]:
        """Collecte les données Uniswap"""
        data = {}

        try:
            # Récupération des pools (simulé)
            data["tvl"] = Decimal("1000000000")
            data["volume_24h"] = Decimal("500000000")
            data["apy"] = Decimal("0.05")
            data["total_users"] = 20000
            data["active_users"] = 2000
            data["tvl_change_24h"] = Decimal("0.025")
            data["tvl_change_7d"] = Decimal("0.06")

        except Exception as e:
            logger.warning(f"Erreur Uniswap: {e}")

        return data

    async def _collect_generic_data(self, instance: Any, chain: str) -> Dict[str, Any]:
        """Collecte les données génériques"""
        return {
            "tvl": Decimal("100000000"),
            "volume_24h": Decimal("10000000"),
            "apy": Decimal("0.06"),
            "total_users": 1000,
            "active_users": 100,
            "tvl_change_24h": Decimal("0.01"),
            "tvl_change_7d": Decimal("0.03"),
        }

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _calculate_risk_score(self, data: Dict[str, Any]) -> float:
        """Calcule le score de risque"""
        risk_score = 0.0

        # TVL (plus la TVL est élevée, plus le risque est faible)
        tvl = data.get("tvl", Decimal("0"))
        if tvl > Decimal("1000000000"):
            risk_score += 10
        elif tvl > Decimal("100000000"):
            risk_score += 20
        else:
            risk_score += 30

        # Volatilité (simulée)
        risk_score += 25

        # Liquidité
        liquidity = await self._calculate_liquidity(data)
        if liquidity > Decimal("100000000"):
            risk_score += 10
        else:
            risk_score += 25

        # TVL change
        tvl_change = data.get("tvl_change_24h", Decimal("0"))
        if tvl_change > Decimal("0.1"):
            risk_score += 10

        return min(100, risk_score)

    async def _calculate_liquidity(self, data: Dict[str, Any]) -> Decimal:
        """Calcule la liquidité"""
        tvl = data.get("tvl", Decimal("0"))
        volume = data.get("volume_24h", Decimal("0"))

        if volume > 0:
            liquidity = tvl / volume
        else:
            liquidity = Decimal("0")

        return liquidity

    # ============================================================
    # MÉTHODE D'ANALYSE PRINCIPALE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def analyze(self) -> AnalysisResult:
        """
        Exécute l'analyse DeFi

        Returns:
            Résultat de l'analyse
        """
        return await self.run()


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_defi_analyzer(
    config: AnalysisConfig,
    node_manager: NodeManager,
    rpc_client: NodeRPCClient,
    **kwargs,
) -> DeFiAnalyzer:
    """
    Crée une instance de DeFiAnalyzer

    Args:
        config: Configuration de l'analyse
        node_manager: Gestionnaire de nœuds
        rpc_client: Client RPC
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiAnalyzer
    """
    return DeFiAnalyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de DeFiAnalyzer"""
    # Configuration
    config = AnalysisConfig(
        analysis_id="defi_analysis_1",
        analysis_type=AnalysisType.CUSTOM,
        name="DeFi Protocol Analysis",
        description="Analysis of major DeFi protocols",
        chain="ethereum",
        tokens=["aave", "compound", "curve", "uniswap"],
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
            return type('Response', (), {'is_success': lambda: True, 'result': {}})

    node_manager = SimpleNodeManager()
    rpc_client = SimpleRPCClient()

    # Création de l'analyseur
    analyzer = create_defi_analyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
    )

    # Exécution de l'analyse
    result = await analyzer.analyze()
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

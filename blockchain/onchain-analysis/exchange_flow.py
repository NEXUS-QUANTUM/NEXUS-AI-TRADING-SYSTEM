# blockchain/onchain-analysis/exchange_flow.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Exchange Flow - Analyse des Flux d'Échanges

Ce module implémente un système complet d'analyse des flux d'échanges
on-chain, permettant le tracking des mouvements de fonds entre les exchanges,
les wallets, et les protocoles DeFi.

Fonctionnalités principales:
- Tracking des flux vers/depuis les exchanges
- Analyse des balances des exchanges
- Détection des mouvements importants
- Analyse des tendances d'accumulation/distribution
- Alertes de mouvements suspects
- Support multi-exchanges
- Analyse des adresses chaudes/froides
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
    from ..wallets.multi_chain_wallet import MultiChainWallet
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
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from .base_analyzer import BaseAnalyzer, AnalysisResult, AnalysisStatus
    from .analysis_config import AnalysisConfig, MetricType, AnalysisType

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class ExchangeType(Enum):
    """Types d'exchanges"""
    CEX = "cex"  # Centralized Exchange
    DEX = "dex"  # Decentralized Exchange
    HYBRID = "hybrid"


class FlowDirection(Enum):
    """Directions des flux"""
    INFLOW = "inflow"  # Vers l'exchange
    OUTFLOW = "outflow"  # Depuis l'exchange
    INTERNAL = "internal"  # Interne à l'exchange


@dataclass
class ExchangeAddress:
    """Adresse d'exchange"""
    address: str
    exchange: str
    exchange_type: ExchangeType
    label: str
    is_hot: bool = True
    is_cold: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "exchange": self.exchange,
            "exchange_type": self.exchange_type.value,
            "label": self.label,
            "is_hot": self.is_hot,
            "is_cold": self.is_cold,
            "metadata": self.metadata,
        }


@dataclass
class ExchangeFlow:
    """Flux d'exchange"""
    flow_id: str
    exchange: str
    token: str
    chain: str
    direction: FlowDirection
    amount: Decimal
    value_usd: Decimal
    tx_hash: str
    from_address: str
    to_address: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "flow_id": self.flow_id,
            "exchange": self.exchange,
            "token": self.token,
            "chain": self.chain,
            "direction": self.direction.value,
            "amount": str(self.amount),
            "value_usd": str(self.value_usd),
            "tx_hash": self.tx_hash,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ExchangeBalance:
    """Balance d'exchange"""
    exchange: str
    token: str
    chain: str
    balance: Decimal
    balance_usd: Decimal
    change_24h: Decimal
    change_7d: Decimal
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "exchange": self.exchange,
            "token": self.token,
            "chain": self.chain,
            "balance": str(self.balance),
            "balance_usd": str(self.balance_usd),
            "change_24h": str(self.change_24h),
            "change_7d": str(self.change_7d),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ExchangeFlowAlert:
    """Alerte de flux d'exchange"""
    alert_id: str
    exchange: str
    token: str
    direction: FlowDirection
    amount: Decimal
    value_usd: Decimal
    threshold: Decimal
    severity: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "alert_id": self.alert_id,
            "exchange": self.exchange,
            "token": self.token,
            "direction": self.direction.value,
            "amount": str(self.amount),
            "value_usd": str(self.value_usd),
            "threshold": str(self.threshold),
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# ADRESSES DES EXCHANGES CONNUES
# ============================================================

KNOWN_EXCHANGE_ADDRESSES = {
    "binance": {
        "ethereum": [
            "0x28C6c06298d514Db089934071355E5743bf21d60",
            "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
            "0xdfd5293d8e347dFe59E90eFd55b2956a1343963d",
        ],
        "bsc": [
            "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",
            "0x0000000000000000000000000000000000000000",
        ],
    },
    "coinbase": {
        "ethereum": [
            "0x71660C4005BA85c37cceD55c0Ba449B46B76B3C8",
            "0x0D0707963952f2fBA59dD06f2b425ace40b492Fe",
        ],
    },
    "kraken": {
        "ethereum": [
            "0x267bE1C1D684F78cb4F6a176C4911b741E50Ff6c",
            "0x2910543Af39aBA0Cd09dBB2D50200b3E800A63D2",
        ],
    },
    "okx": {
        "ethereum": [
            "0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b",
            "0x2c8fbb630bC4297B1DC5eCb9CbBB6C4fcb8d8b8d",
        ],
    },
    "bybit": {
        "ethereum": [
            "0x1Db3439a222C519ab44bb1144fC28167b4Fa6EE6",
            "0xF89d7B9c864f589bBf53a82105107622B35Ea40c",
        ],
    },
    "gateio": {
        "ethereum": [
            "0x0D0707963952f2fBA59dD06f2b425ace40b492Fe",
        ],
    },
    "huobi": {
        "ethereum": [
            "0x5e5831a204cb3aEeC49d1b1f3E1a6Bf3C9aF6b9d",
        ],
    },
    "ftx": {
        "ethereum": [
            "0x2fAF487A4414Fe77e2327F0bf4AE2a264a776AD2",
        ],
    },
    "gemini": {
        "ethereum": [
            "0x61EDCdF5bb737ADffE5043706D7Db5e0F1A3b3D7",
        ],
    },
    "bitfinex": {
        "ethereum": [
            "0x77134cBC06cF00d64b2cD444cFdc1Ec56560d0e5",
        ],
    },
}

# Tokens populaires
POPULAR_TOKENS = {
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
        "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    },
    "polygon": {
        "MATIC": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
        "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class ExchangeFlowAnalyzer(BaseAnalyzer):
    """
    Analyseur des flux d'échanges on-chain
    """

    def __init__(
        self,
        config: AnalysisConfig,
        node_manager: NodeManager,
        rpc_client: NodeRPCClient,
        wallet_manager: Optional[MultiChainWallet] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise l'analyseur de flux d'échanges

        Args:
            config: Configuration de l'analyse
            node_manager: Gestionnaire de nœuds
            rpc_client: Client RPC
            wallet_manager: Gestionnaire de wallets
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, node_manager, rpc_client, metrics_collector, cache_ttl)

        self.wallet_manager = wallet_manager
        self._exchange_addresses: Dict[str, Dict[str, List[ExchangeAddress]]] = {}
        self._balances: Dict[str, Dict[str, ExchangeBalance]] = {}
        self._flows: List[ExchangeFlow] = []
        self._alerts: List[ExchangeFlowAlert] = []
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Initialisation des adresses d'échanges
        self._initialize_exchange_addresses()

        logger.info(f"ExchangeFlowAnalyzer {config.name} initialisé")

    def _initialize_exchange_addresses(self) -> None:
        """Initialise les adresses des exchanges"""
        for exchange, chains in KNOWN_EXCHANGE_ADDRESSES.items():
            self._exchange_addresses[exchange] = {}

            for chain, addresses in chains.items():
                self._exchange_addresses[exchange][chain] = []

                for address in addresses:
                    # Détermination du type (hot/cold)
                    is_hot = True
                    is_cold = False

                    # Certaines adresses sont connues comme cold
                    cold_indicators = ["cold", "treasury", "reserve"]
                    for indicator in cold_indicators:
                        if indicator in address.lower():
                            is_hot = False
                            is_cold = True
                            break

                    exchange_addr = ExchangeAddress(
                        address=address,
                        exchange=exchange,
                        exchange_type=ExchangeType.CEX,
                        label=f"{exchange} {chain}",
                        is_hot=is_hot,
                        is_cold=is_cold,
                    )

                    self._exchange_addresses[exchange][chain].append(exchange_addr)

        logger.info(f"Adresses d'échanges initialisées: {len(self._exchange_addresses)} exchanges")

    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def collect_data(self) -> Dict[str, Any]:
        """
        Collecte les données de flux d'échanges

        Returns:
            Données collectées
        """
        logger.info(f"Collecte des flux d'échanges pour {self.config.chain}")

        data = {}
        chain = self.config.chain
        tokens = self.config.tokens or list(POPULAR_TOKENS.get(chain, {}).keys())

        # Récupération des balances des exchanges
        balances = await self._collect_exchange_balances(chain, tokens)
        data["balances"] = balances

        # Récupération des flux récents
        flows = await self._collect_recent_flows(chain, tokens)
        data["flows"] = flows

        # Détection des mouvements importants
        movements = await self._detect_important_movements(chain, flows)
        data["movements"] = movements

        return data

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def process_data(self, data: Dict[str, Any]) -> Dict[MetricType, Any]:
        """
        Traite les données de flux d'échanges

        Args:
            data: Données collectées

        Returns:
            Métriques calculées
        """
        logger.info(f"Traitement des données de flux d'échanges")

        metrics = {}

        # Métriques de flux
        flows = data.get("flows", [])
        total_inflow = Decimal("0")
        total_outflow = Decimal("0")

        for flow in flows:
            if flow.direction == FlowDirection.INFLOW:
                total_inflow += flow.value_usd
            elif flow.direction == FlowDirection.OUTFLOW:
                total_outflow += flow.value_usd

        metrics[MetricType.VOLUME_24H] = total_inflow + total_outflow

        # Net flow
        net_flow = total_inflow - total_outflow
        metrics[MetricType.VOLUME_CHANGE] = net_flow

        # Alertes
        alerts = data.get("movements", [])
        metrics[MetricType.WHALE_TRANSACTIONS] = len(alerts)

        # Balances des exchanges
        balances = data.get("balances", [])
        total_balance = sum(b.balance_usd for b in balances)
        metrics[MetricType.LIQUIDITY_24H] = total_balance

        # Concentration
        if balances:
            max_balance = max(b.balance_usd for b in balances)
            concentration = max_balance / total_balance if total_balance > 0 else 0
            metrics[MetricType.WHALE_CONCENTRATION] = concentration

        return metrics

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def generate_insights(self, metrics: Dict[MetricType, Any]) -> List[str]:
        """
        Génère des insights à partir des flux d'échanges

        Args:
            metrics: Métriques calculées

        Returns:
            Liste des insights
        """
        insights = []

        # Flux net
        if MetricType.VOLUME_CHANGE in metrics:
            net_flow = metrics[MetricType.VOLUME_CHANGE]
            if net_flow > Decimal("1000000"):
                insights.append(f"Afflux net important: ${net_flow:,.0f} vers les exchanges")
            elif net_flow < -Decimal("1000000"):
                insights.append(f"Sortie nette importante: ${-net_flow:,.0f} des exchanges")

        # Concentration
        if MetricType.WHALE_CONCENTRATION in metrics:
            concentration = metrics[MetricType.WHALE_CONCENTRATION]
            if concentration > 0.5:
                insights.append(f"Concentration élevée sur un exchange: {concentration:.1%}")

        # Alertes
        if MetricType.WHALE_TRANSACTIONS in metrics:
            alerts_count = metrics[MetricType.WHALE_TRANSACTIONS]
            if alerts_count > 5:
                insights.append(f"{alerts_count} mouvements importants détectés")

        return insights

    # ============================================================
    # MÉTHODES DE COLLECTE DE DONNÉES
    # ============================================================

    async def _collect_exchange_balances(
        self,
        chain: str,
        tokens: List[str],
    ) -> List[ExchangeBalance]:
        """
        Collecte les balances des exchanges

        Args:
            chain: Chaîne
            tokens: Liste des tokens

        Returns:
            Liste des balances
        """
        balances = []

        for exchange, chains in self._exchange_addresses.items():
            if chain not in chains:
                continue

            exchange_addrs = chains[chain]

            for token in tokens:
                try:
                    total_balance = Decimal("0")

                    for addr in exchange_addrs:
                        try:
                            balance = await self._get_address_balance(
                                addr.address,
                                token,
                                chain,
                            )
                            total_balance += balance
                        except Exception as e:
                            logger.debug(f"Erreur pour {addr.address}: {e}")

                    if total_balance > 0:
                        # Récupération du prix
                        price = await self._get_token_price(token, chain)

                        balance_usd = total_balance * price

                        # Calcul des changements (simulés)
                        change_24h = Decimal("0.02")  # 2% de changement
                        change_7d = Decimal("0.05")  # 5% de changement

                        balance_data = ExchangeBalance(
                            exchange=exchange,
                            token=token,
                            chain=chain,
                            balance=total_balance,
                            balance_usd=balance_usd,
                            change_24h=change_24h,
                            change_7d=change_7d,
                            timestamp=datetime.now(),
                        )

                        balances.append(balance_data)

                except Exception as e:
                    logger.warning(f"Erreur pour {exchange}/{token}: {e}")

        return balances

    async def _collect_recent_flows(
        self,
        chain: str,
        tokens: List[str],
        limit: int = 1000,
    ) -> List[ExchangeFlow]:
        """
        Collecte les flux récents

        Args:
            chain: Chaîne
            tokens: Liste des tokens
            limit: Nombre maximum de transactions

        Returns:
            Liste des flux
        """
        flows = []

        try:
            # Récupération des transactions récentes
            # Dans la réalité, on interrogerait un indexeur
            # Simulé pour l'exemple

            # Création de flux simulés
            for i in range(min(limit, 20)):
                direction = FlowDirection.INFLOW if i % 2 == 0 else FlowDirection.OUTFLOW
                token = tokens[i % len(tokens)] if tokens else "ETH"

                flow = ExchangeFlow(
                    flow_id=f"flow_{uuid.uuid4().hex[:12]}",
                    exchange="binance",
                    token=token,
                    chain=chain,
                    direction=direction,
                    amount=Decimal(str(100 * (i + 1))),
                    value_usd=Decimal(str(1000 * (i + 1))),
                    tx_hash=f"0x{hash(str(i)):064x}",
                    from_address="0x..." if direction == FlowDirection.OUTFLOW else exchange_address,
                    to_address=exchange_address if direction == FlowDirection.OUTFLOW else "0x...",
                    timestamp=datetime.now() - timedelta(hours=i),
                )

                flows.append(flow)

        except Exception as e:
            logger.warning(f"Erreur de collecte des flux: {e}")

        self._flows.extend(flows)
        return flows

    async def _detect_important_movements(
        self,
        chain: str,
        flows: List[ExchangeFlow],
        threshold_usd: Decimal = Decimal("100000"),
    ) -> List[ExchangeFlowAlert]:
        """
        Détecte les mouvements importants

        Args:
            chain: Chaîne
            flows: Liste des flux
            threshold_usd: Seuil en USD

        Returns:
            Liste des alertes
        """
        alerts = []

        for flow in flows:
            if flow.value_usd >= threshold_usd:
                severity = "critical" if flow.value_usd >= threshold_usd * 10 else "warning"

                alert = ExchangeFlowAlert(
                    alert_id=f"alert_{uuid.uuid4().hex[:12]}",
                    exchange=flow.exchange,
                    token=flow.token,
                    direction=flow.direction,
                    amount=flow.amount,
                    value_usd=flow.value_usd,
                    threshold=threshold_usd,
                    severity=severity,
                    message=f"Mouvement important détecté: {flow.value_usd:,.0f} USD",
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

    async def _get_address_balance(
        self,
        address: str,
        token: str,
        chain: str,
    ) -> Decimal:
        """
        Obtient le solde d'une adresse

        Args:
            address: Adresse
            token: Token
            chain: Chaîne

        Returns:
            Solde
        """
        try:
            # Vérification du cache
            cache_key = f"{chain}:{address}:{token}"
            cached = await self._cache_get(cache_key)
            if cached is not None:
                return cached

            # Récupération du solde via RPC
            token_address = POPULAR_TOKENS.get(chain, {}).get(token)

            if not token_address:
                return Decimal("0")

            if token_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                # Token natif
                result = await self._make_rpc_call(
                    RPCMethod.ETH_GET_BALANCE,
                    [address, "latest"],
                )
                balance = Decimal(str(int(result, 16) if result else 0)) / Decimal(1e18)
            else:
                # ERC-20
                result = await self._make_rpc_call(
                    RPCMethod.ETH_CALL,
                    [{
                        "to": token_address,
                        "data": f"0x70a082310000000000000000000000000000000000000000000000000000000000000000{address[2:]}",
                    }, "latest"],
                )
                balance = Decimal(str(int(result, 16) if result else 0)) / Decimal(1e18)

            # Mise en cache
            await self._cache_set(cache_key, balance)

            return balance

        except Exception as e:
            logger.warning(f"Erreur de solde pour {address}: {e}")
            return Decimal("0")

    async def _get_token_price(self, token: str, chain: str) -> Decimal:
        """
        Obtient le prix d'un token

        Args:
            token: Symbole du token
            chain: Chaîne

        Returns:
            Prix en USD
        """
        # Simulé - dans la réalité, on utiliserait un oracle
        prices = {
            "ETH": Decimal("3000"),
            "USDC": Decimal("1"),
            "USDT": Decimal("1"),
            "DAI": Decimal("1"),
            "WBTC": Decimal("60000"),
            "BNB": Decimal("600"),
            "MATIC": Decimal("0.7"),
            "BUSD": Decimal("1"),
        }
        return prices.get(token, Decimal("1"))

    # ============================================================
    # MÉTHODE D'ANALYSE PRINCIPALE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def analyze(self) -> AnalysisResult:
        """
        Exécute l'analyse des flux d'échanges

        Returns:
            Résultat de l'analyse
        """
        return await self.run()


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_exchange_flow_analyzer(
    config: AnalysisConfig,
    node_manager: NodeManager,
    rpc_client: NodeRPCClient,
    **kwargs,
) -> ExchangeFlowAnalyzer:
    """
    Crée une instance de ExchangeFlowAnalyzer

    Args:
        config: Configuration de l'analyse
        node_manager: Gestionnaire de nœuds
        rpc_client: Client RPC
        **kwargs: Arguments additionnels

    Returns:
        Instance de ExchangeFlowAnalyzer
    """
    return ExchangeFlowAnalyzer(
        config=config,
        node_manager=node_manager,
        rpc_client=rpc_client,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de ExchangeFlowAnalyzer"""
    # Configuration
    config = AnalysisConfig(
        analysis_id="exchange_flow_1",
        analysis_type=AnalysisType.CUSTOM,
        name="Exchange Flow Analysis",
        description="Analysis of exchange flows",
        chain="ethereum",
        tokens=["ETH", "USDC", "USDT"],
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
    analyzer = create_exchange_flow_analyzer(
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

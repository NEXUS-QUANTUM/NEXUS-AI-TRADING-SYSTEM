# blockchain/bridges/cross_chain_swap.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Swap Cross-Chain Avancé

Ce module implémente un système complet de swap entre différentes blockchains
avec support de multiples protocoles, routage intelligent, gestion des frais,
et mécanismes de sécurité avancés.

Fonctionnalités principales:
- Routage multi-DEX pour les swaps cross-chain
- Optimisation des coûts avec plusieurs fournisseurs de liquidité
- Support des bridges majeurs (LayerZero, Axelar, Wormhole)
- Gestion des frais de gaz sur différentes chaînes
- Mécanismes de fallback et reprise sur échec
- Surveillance en temps réel des transactions
- Intégration avec les systèmes de trading
"""

import asyncio
import hashlib
import hmac
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
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_typing import Address, ChecksumAddress, HexStr
from hexbytes import HexBytes

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import BlockchainError, BridgeError, ValidationError
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_analytics import BridgeAnalytics
    from .bridge_validator import BridgeValidator
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import BlockchainError, BridgeError, ValidationError
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_analytics import BridgeAnalytics
    from .bridge_validator import BridgeValidator
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class BridgeProtocol(Enum):
    """Protocoles de bridge supportés"""
    LAYERZERO = "layerzero"
    AXELAR = "axelar"
    WORMHOLE = "wormhole"
    CCTP = "cctp"
    ACROSS = "across"
    HOP = "hop"
    CONNEXT = "connext"
    SYNAPSE = "synapse"
    STARGATE = "stargate"
    MESON = "meson"
    DEBRIDGE = "debridge"
    LIQUIDITY = "liquidity"


class SwapStatus(Enum):
    """Statuts d'un swap"""
    PENDING = "pending"
    APPROVING = "approving"
    APPROVED = "approved"
    SWAPPING = "swapping"
    BRIDGING = "bridging"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    RETRYING = "retrying"


class SwapType(Enum):
    """Types de swap"""
    EXACT_INPUT = "exact_input"
    EXACT_OUTPUT = "exact_output"
    CROSS_CHAIN = "cross_chain"
    SAME_CHAIN = "same_chain"


class RoutingStrategy(Enum):
    """Stratégies de routage"""
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    BALANCED = "balanced"
    SAFEST = "safest"
    CUSTOM = "custom"


@dataclass
class SwapRoute:
    """Route de swap"""
    route_id: str
    chain_from: str
    chain_to: str
    token_from: str
    token_to: str
    amount: Decimal
    estimated_gas: Decimal
    estimated_fees: Decimal
    estimated_time: int  # secondes
    bridge_protocols: List[BridgeProtocol]
    dex_path: List[str]
    slippage: Decimal
    confidence: float
    route_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "route_id": self.route_id,
            "chain_from": self.chain_from,
            "chain_to": self.chain_to,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "estimated_gas": str(self.estimated_gas),
            "estimated_fees": str(self.estimated_fees),
            "estimated_time": self.estimated_time,
            "bridge_protocols": [p.value for p in self.bridge_protocols],
            "dex_path": self.dex_path,
            "slippage": str(self.slippage),
            "confidence": self.confidence,
        }


@dataclass
class CrossChainSwapRequest:
    """Requête de swap cross-chain"""
    request_id: str
    chain_from: str
    chain_to: str
    token_from: str
    token_to: str
    amount: Decimal
    wallet_address: str
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600  # secondes
    bridge_protocols: Optional[List[BridgeProtocol]] = None
    routing_strategy: RoutingStrategy = RoutingStrategy.BALANCED
    use_fallback: bool = True
    max_gas_price: Optional[Decimal] = None
    priority_fee: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "chain_from": self.chain_from,
            "chain_to": self.chain_to,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "wallet_address": self.wallet_address,
            "slippage_tolerance": str(self.slippage_tolerance),
            "deadline": self.deadline,
            "bridge_protocols": [p.value for p in self.bridge_protocols] if self.bridge_protocols else None,
            "routing_strategy": self.routing_strategy.value,
            "use_fallback": self.use_fallback,
            "max_gas_price": str(self.max_gas_price) if self.max_gas_price else None,
            "priority_fee": str(self.priority_fee) if self.priority_fee else None,
        }


@dataclass
class CrossChainSwapResult:
    """Résultat d'un swap cross-chain"""
    swap_id: str
    request_id: str
    status: SwapStatus
    route_used: Optional[SwapRoute] = None
    tx_hash_from: Optional[str] = None
    tx_hash_to: Optional[str] = None
    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    amount_received: Optional[Decimal] = None
    fees_total: Optional[Decimal] = None
    gas_used: Optional[Decimal] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    bridge_tx_ids: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "swap_id": self.swap_id,
            "request_id": self.request_id,
            "status": self.status.value,
            "route_used": self.route_used.to_dict() if self.route_used else None,
            "tx_hash_from": self.tx_hash_from,
            "tx_hash_to": self.tx_hash_to,
            "amount_in": str(self.amount_in) if self.amount_in else None,
            "amount_out": str(self.amount_out) if self.amount_out else None,
            "amount_received": str(self.amount_received) if self.amount_received else None,
            "fees_total": str(self.fees_total) if self.fees_total else None,
            "gas_used": str(self.gas_used) if self.gas_used else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "bridge_tx_ids": self.bridge_tx_ids,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }


# ============================================================
# CLASSES DE BASES
# ============================================================

class CrossChainSwapError(BlockchainError):
    """Erreur spécifique aux swaps cross-chain"""
    pass


class CrossChainSwap:
    """Classe principale pour les swaps cross-chain"""

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        bridge_manager: BridgeManager,
        web3_providers: Dict[str, Web3],
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le moteur de swaps cross-chain

        Args:
            config: Configuration du système
            wallet_manager: Gestionnaire de wallets
            bridge_manager: Gestionnaire de bridges
            web3_providers: Dictionnaire des providers Web3 par chaîne
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.bridge_manager = bridge_manager
        self.web3_providers = web3_providers
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._active_swaps: Dict[str, CrossChainSwapResult] = {}
        self._swap_history: List[CrossChainSwapResult] = []
        self._route_cache: Dict[str, Tuple[float, List[SwapRoute]]] = {}
        self._rate_limits: Dict[str, int] = defaultdict(int)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breaker par protocole
        self.circuit_breakers: Dict[BridgeProtocol, CircuitBreaker] = {
            protocol: CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60.0,
                half_open_attempts=3,
            )
            for protocol in BridgeProtocol
        }

        # Initialisation des contrats
        self._contracts: Dict[str, Dict[str, Contract]] = {}
        self._load_contracts()

        # Thread pool pour les opérations bloquantes
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des prix
        self._price_cache: Dict[str, Dict[str, Decimal]] = {}
        self._cache_lock = asyncio.Lock()

        logger.info("CrossChainSwap initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats smart nécessaires"""
        try:
            # ABIs des contrats
            router_abi = self._load_abi("router_abi.json")
            bridge_abi = self._load_abi("bridge_abi.json")
            erc20_abi = self._load_abi("erc20_abi.json")

            for chain, provider in self.web3_providers.items():
                self._contracts[chain] = {}
                # Routers DEX
                if chain in self.config.get("dex_contracts", {}):
                    router_addr = self.config["dex_contracts"][chain]["router"]
                    self._contracts[chain]["router"] = provider.eth.contract(
                        address=Web3.to_checksum_address(router_addr),
                        abi=router_abi,
                    )
                # Bridges
                if chain in self.config.get("bridge_contracts", {}):
                    bridge_addr = self.config["bridge_contracts"][chain]
                    self._contracts[chain]["bridge"] = provider.eth.contract(
                        address=Web3.to_checksum_address(bridge_addr),
                        abi=bridge_abi,
                    )
                logger.debug(f"Contrats chargés pour {chain}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise CrossChainSwapError(f"Erreur de chargement des contrats: {e}")

    def _load_abi(self, filename: str) -> List[Dict[str, Any]]:
        """Charge un fichier ABI"""
        try:
            import json
            from pathlib import Path

            abi_path = Path(__file__).parent / "abis" / filename
            with open(abi_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"ABI {filename} non trouvé, utilisation de l'ABI minimale")
            # ABI minimale pour les fonctionnalités de base
            if "router" in filename:
                return [
                    {
                        "constant": False,
                        "inputs": [
                            {"name": "path", "type": "address[]"},
                            {"name": "to", "type": "address"},
                            {"name": "deadline", "type": "uint256"},
                        ],
                        "name": "swapExactTokensForTokens",
                        "outputs": [{"name": "amounts", "type": "uint256[]"}],
                        "payable": False,
                        "stateMutability": "nonpayable",
                        "type": "function",
                    }
                ]
            elif "bridge" in filename:
                return [
                    {
                        "constant": False,
                        "inputs": [
                            {"name": "token", "type": "address"},
                            {"name": "amount", "type": "uint256"},
                            {"name": "to", "type": "address"},
                            {"name": "chainId", "type": "uint256"},
                        ],
                        "name": "bridge",
                        "outputs": [],
                        "payable": False,
                        "stateMutability": "nonpayable",
                        "type": "function",
                    }
                ]
            else:
                return [
                    {
                        "constant": True,
                        "inputs": [{"name": "owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "", "type": "uint256"}],
                        "payable": False,
                        "stateMutability": "view",
                        "type": "function",
                    },
                    {
                        "constant": False,
                        "inputs": [
                            {"name": "spender", "type": "address"},
                            {"name": "amount", "type": "uint256"},
                        ],
                        "name": "approve",
                        "outputs": [{"name": "", "type": "bool"}],
                        "payable": False,
                        "stateMutability": "nonpayable",
                        "type": "function",
                    },
                ]

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_swap_quote(
        self,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        **kwargs,
    ) -> List[SwapRoute]:
        """
        Obtient des devis pour un swap cross-chain

        Args:
            chain_from: Chaîne source
            chain_to: Chaîne destination
            token_from: Token source
            token_to: Token destination
            amount: Montant à swapper
            **kwargs: Arguments additionnels

        Returns:
            Liste des routes de swap possibles
        """
        logger.info(
            f"Demande de devis: {amount} {token_from} ({chain_from}) -> "
            f"{token_to} ({chain_to})"
        )

        # Vérification du cache
        cache_key = f"{chain_from}:{chain_to}:{token_from}:{token_to}:{amount}"
        if cache_key in self._route_cache:
            cached_time, routes = self._route_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Devis retourné du cache")
                return routes

        try:
            routes = await self._calculate_routes(
                chain_from=chain_from,
                chain_to=chain_to,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                **kwargs,
            )

            # Mise en cache
            self._route_cache[cache_key] = (time.time(), routes)

            # Métriques
            self.metrics.record_gauge(
                "cross_chain_swap_routes",
                len(routes),
                {
                    "chain_from": chain_from,
                    "chain_to": chain_to,
                    "token_from": token_from,
                    "token_to": token_to,
                },
            )

            return routes

        except Exception as e:
            logger.error(f"Erreur lors du calcul des routes: {e}")
            raise CrossChainSwapError(f"Erreur de calcul des routes: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_swap(self, request: CrossChainSwapRequest) -> CrossChainSwapResult:
        """
        Exécute un swap cross-chain

        Args:
            request: Requête de swap

        Returns:
            Résultat du swap
        """
        logger.info(f"Exécution du swap: {request.request_id}")

        # Création du résultat initial
        result = CrossChainSwapResult(
            swap_id=f"swap_{uuid.uuid4().hex[:12]}",
            request_id=request.request_id,
            status=SwapStatus.PENDING,
            start_time=datetime.now(),
        )

        self._active_swaps[result.swap_id] = result

        try:
            # 1. Obtention des routes
            routes = await self.get_swap_quote(
                chain_from=request.chain_from,
                chain_to=request.chain_to,
                token_from=request.token_from,
                token_to=request.token_to,
                amount=request.amount,
                bridge_protocols=request.bridge_protocols,
                routing_strategy=request.routing_strategy,
            )

            if not routes:
                result.status = SwapStatus.FAILED
                result.error_message = "Aucune route disponible"
                raise CrossChainSwapError("Aucune route disponible")

            # Sélection de la route
            selected_route = self._select_best_route(routes, request.routing_strategy)
            result.route_used = selected_route

            # 2. Exécution du swap
            result.status = SwapStatus.APPROVING
            result = await self._execute_swap_route(request, selected_route, result)

            # 3. Mise à jour finale
            result.status = SwapStatus.COMPLETED
            result.end_time = datetime.now()

            logger.info(
                f"Swap {result.swap_id} terminé avec succès: "
                f"{result.amount_in} -> {result.amount_out}"
            )

            # Métriques
            self.metrics.record_increment(
                "cross_chain_swap_completed",
                {
                    "chain_from": request.chain_from,
                    "chain_to": request.chain_to,
                    "token_from": request.token_from,
                    "token_to": request.token_to,
                    "bridge": selected_route.bridge_protocols[0].value if selected_route.bridge_protocols else "unknown",
                },
            )

            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution du swap: {e}")
            result.status = SwapStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()

            # Tentative de fallback
            if request.use_fallback and self._can_fallback(result):
                logger.info(f"Tentative de fallback pour {result.swap_id}")
                result = await self._execute_fallback(request, result)

            self.metrics.record_increment(
                "cross_chain_swap_failed",
                {
                    "chain_from": request.chain_from,
                    "chain_to": request.chain_to,
                    "error": str(e)[:50],
                },
            )

            return result

        finally:
            self._active_swaps.pop(result.swap_id, None)
            self._swap_history.append(result)
            if len(self._swap_history) > 1000:
                self._swap_history = self._swap_history[-500:]

    async def get_swap_status(self, swap_id: str) -> Optional[CrossChainSwapResult]:
        """
        Obtient le statut d'un swap

        Args:
            swap_id: ID du swap

        Returns:
            Statut du swap ou None
        """
        # Vérifier dans les swaps actifs
        if swap_id in self._active_swaps:
            return self._active_swaps[swap_id]

        # Vérifier dans l'historique
        for swap in reversed(self._swap_history):
            if swap.swap_id == swap_id:
                return swap

        return None

    async def cancel_swap(self, swap_id: str) -> bool:
        """
        Annule un swap en cours

        Args:
            swap_id: ID du swap

        Returns:
            True si annulé avec succès
        """
        if swap_id not in self._active_swaps:
            return False

        result = self._active_swaps[swap_id]
        if result.status in [SwapStatus.COMPLETED, SwapStatus.FAILED]:
            return False

        result.status = SwapStatus.CANCELLED
        result.end_time = datetime.now()
        logger.info(f"Swap {swap_id} annulé")

        return True

    # ============================================================
    # MÉTHODES INTERNES PRINCIPALES
    # ============================================================

    async def _calculate_routes(
        self,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        **kwargs,
    ) -> List[SwapRoute]:
        """Calcule les routes de swap possibles"""
        routes = []

        # Si même chaîne, swap direct
        if chain_from == chain_to:
            route = await self._calculate_same_chain_route(
                chain_from, token_from, token_to, amount, **kwargs
            )
            if route:
                routes.append(route)

        # Routes cross-chain
        bridge_protocols = kwargs.get("bridge_protocols", None)
        if bridge_protocols is None:
            bridge_protocols = list(BridgeProtocol)

        for protocol in bridge_protocols:
            # Vérification du circuit breaker
            if not self.circuit_breakers[protocol].is_available():
                logger.warning(f"Circuit breaker ouvert pour {protocol}")
                continue

            try:
                route = await self._calculate_cross_chain_route(
                    chain_from=chain_from,
                    chain_to=chain_to,
                    token_from=token_from,
                    token_to=token_to,
                    amount=amount,
                    protocol=protocol,
                    **kwargs,
                )
                if route:
                    routes.append(route)
            except Exception as e:
                logger.warning(f"Erreur pour {protocol}: {e}")
                self.circuit_breakers[protocol].record_failure()
                continue

        # Tri des routes par stratégie
        strategy = kwargs.get("routing_strategy", RoutingStrategy.BALANCED)
        routes = self._sort_routes(routes, strategy)

        return routes

    async def _calculate_cross_chain_route(
        self,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        protocol: BridgeProtocol,
        **kwargs,
    ) -> Optional[SwapRoute]:
        """Calcule une route cross-chain spécifique"""
        try:
            # Estimation des frais
            gas_estimate = await self._estimate_gas(
                chain_from, protocol, amount
            )
            bridge_fees = await self._estimate_bridge_fees(
                protocol, chain_from, chain_to, token_from, token_to, amount
            )
            dex_fees = await self._estimate_dex_fees(
                chain_from, chain_to, token_from, token_to, amount
            )

            # Estimation du temps
            estimated_time = await self._estimate_transfer_time(
                protocol, chain_from, chain_to
            )

            # Vérification de la liquidité
            liquidity_available = await self._check_liquidity(
                protocol, chain_from, chain_to, token_from, token_to, amount
            )
            if not liquidity_available:
                return None

            # Création de la route
            route_id = f"route_{uuid.uuid4().hex[:8]}"
            route = SwapRoute(
                route_id=route_id,
                chain_from=chain_from,
                chain_to=chain_to,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                estimated_gas=gas_estimate,
                estimated_fees=bridge_fees + dex_fees,
                estimated_time=estimated_time,
                bridge_protocols=[protocol],
                dex_path=self._get_dex_path(chain_from, chain_to, token_from, token_to),
                slippage=Decimal("0.005"),  # 0.5% par défaut
                confidence=self._calculate_route_confidence(protocol, amount),
                route_data={
                    "gas_estimate": str(gas_estimate),
                    "bridge_fees": str(bridge_fees),
                    "dex_fees": str(dex_fees),
                    "liquidity_check": True,
                },
            )

            return route

        except Exception as e:
            logger.error(f"Erreur de calcul de route pour {protocol}: {e}")
            return None

    async def _calculate_same_chain_route(
        self,
        chain: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        **kwargs,
    ) -> Optional[SwapRoute]:
        """Calcule une route sur la même chaîne"""
        try:
            # Estimation des frais DEX
            dex_fees = await self._estimate_dex_fees(
                chain, chain, token_from, token_to, amount
            )
            gas_estimate = await self._estimate_gas(chain, None, amount)

            route = SwapRoute(
                route_id=f"route_{uuid.uuid4().hex[:8]}",
                chain_from=chain,
                chain_to=chain,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                estimated_gas=gas_estimate,
                estimated_fees=dex_fees,
                estimated_time=30,  # 30 secondes pour un swap sur la même chaîne
                bridge_protocols=[],
                dex_path=self._get_dex_path(chain, chain, token_from, token_to),
                slippage=Decimal("0.003"),  # 0.3%
                confidence=0.95,
                route_data={
                    "gas_estimate": str(gas_estimate),
                    "dex_fees": str(dex_fees),
                },
            )

            return route

        except Exception as e:
            logger.error(f"Erreur de calcul de route same-chain: {e}")
            return None

    async def _execute_swap_route(
        self,
        request: CrossChainSwapRequest,
        route: SwapRoute,
        result: CrossChainSwapResult,
    ) -> CrossChainSwapResult:
        """Exécute une route de swap spécifique"""
        chain_from = request.chain_from
        chain_to = request.chain_to
        token_from = request.token_from
        token_to = request.token_to

        # Vérification du wallet
        wallet = await self.wallet_manager.get_wallet(request.wallet_address)
        if not wallet:
            raise CrossChainSwapError("Wallet non trouvé")

        # Vérification du solde
        balance = await self._get_token_balance(
            chain_from, token_from, wallet.address
        )
        if balance < request.amount:
            raise CrossChainSwapError(
                f"Solde insuffisant: {balance} < {request.amount}"
            )

        try:
            # 1. Approval du token si nécessaire
            result.status = SwapStatus.APPROVING
            await self._approve_token(
                chain_from,
                token_from,
                request.amount,
                wallet,
                route,
            )
            result.status = SwapStatus.APPROVED

            # 2. Swap sur la chaîne source
            result.status = SwapStatus.SWAPPING
            swap_result = await self._perform_swap(
                chain_from,
                token_from,
                token_to,
                request.amount,
                route,
                wallet,
                request.slippage_tolerance,
            )
            result.tx_hash_from = swap_result.get("tx_hash")
            result.amount_in = swap_result.get("amount_in")

            # Si même chaîne, terminé
            if chain_from == chain_to:
                result.amount_out = swap_result.get("amount_out")
                result.amount_received = result.amount_out
                result.fees_total = route.estimated_fees
                return result

            # 3. Bridge vers la chaîne destination
            result.status = SwapStatus.BRIDGING
            bridge_result = await self._bridge_tokens(
                chain_from=chain_from,
                chain_to=chain_to,
                token=token_to,
                amount=result.amount_out or Decimal(0),
                to_address=wallet.address,
                route=route,
                wallet=wallet,
            )
            result.tx_hash_to = bridge_result.get("tx_hash")
            result.bridge_tx_ids.append(bridge_result.get("bridge_tx_id"))
            result.amount_received = bridge_result.get("amount_received")

            # Métriques de performance
            elapsed = (datetime.now() - result.start_time).total_seconds()
            self.metrics.record_timing(
                "cross_chain_swap_execution_time",
                elapsed,
                {
                    "chain_from": chain_from,
                    "chain_to": chain_to,
                    "bridge": route.bridge_protocols[0].value if route.bridge_protocols else "none",
                },
            )

            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la route: {e}")
            # Marquer l'échec pour le circuit breaker
            if route.bridge_protocols:
                self.circuit_breakers[route.bridge_protocols[0]].record_failure()
            raise

    async def _execute_fallback(
        self,
        request: CrossChainSwapRequest,
        failed_result: CrossChainSwapResult,
    ) -> CrossChainSwapResult:
        """Exécute une stratégie de fallback"""
        logger.info(f"Exécution du fallback pour {request.request_id}")

        # Essayer avec un autre protocole
        available_protocols = [
            p for p in BridgeProtocol
            if p not in (request.bridge_protocols or [])
            and self.circuit_breakers[p].is_available()
        ]

        for protocol in available_protocols:
            try:
                # Recréation de la requête avec le nouveau protocole
                fallback_request = CrossChainSwapRequest(
                    request_id=request.request_id,
                    chain_from=request.chain_from,
                    chain_to=request.chain_to,
                    token_from=request.token_from,
                    token_to=request.token_to,
                    amount=request.amount,
                    wallet_address=request.wallet_address,
                    slippage_tolerance=request.slippage_tolerance * Decimal("1.5"),  # Tolérance plus élevée
                    deadline=request.deadline,
                    bridge_protocols=[protocol],
                    routing_strategy=RoutingStrategy.SAFEST,
                    use_fallback=False,  # Éviter les boucles
                    max_gas_price=request.max_gas_price,
                )

                # Réexécution avec le nouveau protocole
                result = await self.execute_swap(fallback_request)
                if result.status == SwapStatus.COMPLETED:
                    result.retry_count = failed_result.retry_count + 1
                    logger.info(f"Fallback réussi avec {protocol}")
                    return result

            except Exception as e:
                logger.warning(f"Échec du fallback avec {protocol}: {e}")
                continue

        # Si tout échoue, retourner l'échec original
        failed_result.retry_count += 1
        return failed_result

    # ============================================================
    # MÉTHODES DE ROUTAGE
    # ============================================================

    def _select_best_route(
        self,
        routes: List[SwapRoute],
        strategy: RoutingStrategy,
    ) -> SwapRoute:
        """Sélectionne la meilleure route selon la stratégie"""
        if not routes:
            raise CrossChainSwapError("Aucune route disponible")

        if strategy == RoutingStrategy.CHEAPEST:
            return min(routes, key=lambda r: r.estimated_fees)
        elif strategy == RoutingStrategy.FASTEST:
            return min(routes, key=lambda r: r.estimated_time)
        elif strategy == RoutingStrategy.SAFEST:
            return max(routes, key=lambda r: r.confidence)
        elif strategy == RoutingStrategy.BALANCED:
            # Score combiné: coût + temps + confiance
            def score(r: SwapRoute) -> float:
                cost_score = 1.0 - float(r.estimated_fees / Decimal("0.01"))
                time_score = 1.0 - (r.estimated_time / 1800.0)  # 30 min max
                confidence_score = r.confidence
                return (
                    cost_score * 0.4 +
                    time_score * 0.3 +
                    confidence_score * 0.3
                )
            return max(routes, key=score)
        else:
            return routes[0]

    def _sort_routes(
        self,
        routes: List[SwapRoute],
        strategy: RoutingStrategy,
    ) -> List[SwapRoute]:
        """Trie les routes selon la stratégie"""
        if strategy == RoutingStrategy.CHEAPEST:
            return sorted(routes, key=lambda r: r.estimated_fees)
        elif strategy == RoutingStrategy.FASTEST:
            return sorted(routes, key=lambda r: r.estimated_time)
        elif strategy == RoutingStrategy.SAFEST:
            return sorted(routes, key=lambda r: r.confidence, reverse=True)
        else:
            # Balanced
            def score(r: SwapRoute) -> float:
                cost_score = 1.0 - float(r.estimated_fees / Decimal("0.01"))
                time_score = 1.0 - (r.estimated_time / 1800.0)
                confidence_score = r.confidence
                return (
                    cost_score * 0.4 +
                    time_score * 0.3 +
                    confidence_score * 0.3
                )
            return sorted(routes, key=score, reverse=True)

    def _can_fallback(self, result: CrossChainSwapResult) -> bool:
        """Vérifie si un fallback est possible"""
        return (
            result.retry_count < 3 and
            result.status in [SwapStatus.FAILED, SwapStatus.RETRYING] and
            result.route_used is not None and
            len(result.route_used.bridge_protocols) > 0
        )

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _estimate_gas(
        self,
        chain: str,
        protocol: Optional[BridgeProtocol],
        amount: Decimal,
    ) -> Decimal:
        """Estime les frais de gaz"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0.001")  # Valeur par défaut

            # Estimation basée sur le protocole
            base_gas = {
                BridgeProtocol.LAYERZERO: 300000,
                BridgeProtocol.AXELAR: 400000,
                BridgeProtocol.WORMHOLE: 350000,
                BridgeProtocol.CCTP: 250000,
                BridgeProtocol.ACROSS: 200000,
                BridgeProtocol.HOP: 180000,
            }.get(protocol, 300000)

            # Ajustement selon le montant (les gros montants peuvent nécessiter plus de gaz)
            gas_factor = 1.0 + (float(amount) / 1000.0)
            estimated_gas = int(base_gas * min(gas_factor, 2.0))

            # Obtention du prix du gaz actuel
            gas_price = await provider.eth.gas_price
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            total_cost = Decimal(str(estimated_gas)) * gas_price_decimal
            return total_cost

        except Exception as e:
            logger.warning(f"Erreur d'estimation du gaz: {e}")
            return Decimal("0.001")

    async def _estimate_bridge_fees(
        self,
        protocol: BridgeProtocol,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
    ) -> Decimal:
        """Estime les frais de bridge"""
        # Frais fixes par protocole
        fixed_fees = {
            BridgeProtocol.LAYERZERO: Decimal("0.0005"),
            BridgeProtocol.AXELAR: Decimal("0.0008"),
            BridgeProtocol.WORMHOLE: Decimal("0.0003"),
            BridgeProtocol.CCTP: Decimal("0.0001"),
            BridgeProtocol.ACROSS: Decimal("0.0004"),
            BridgeProtocol.HOP: Decimal("0.0006"),
            BridgeProtocol.CONNEXT: Decimal("0.0007"),
            BridgeProtocol.SYNAPSE: Decimal("0.0005"),
            BridgeProtocol.STARGATE: Decimal("0.0004"),
        }.get(protocol, Decimal("0.0005"))

        # Frais variables basés sur le montant
        variable_fees = amount * Decimal("0.0005")  # 0.05%

        # Frais de chaîne
        chain_fees = {
            "ethereum": Decimal("0.001"),
            "bsc": Decimal("0.0001"),
            "polygon": Decimal("0.00005"),
            "arbitrum": Decimal("0.00008"),
            "optimism": Decimal("0.00008"),
            "avalanche": Decimal("0.00006"),
            "solana": Decimal("0.00001"),
        }.get(chain_to, Decimal("0.0001"))

        return fixed_fees + variable_fees + chain_fees

    async def _estimate_dex_fees(
        self,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
    ) -> Decimal:
        """Estime les frais de DEX"""
        # Frais DEX typiques (0.3% sur la plupart des DEX)
        dex_fee_percentage = Decimal("0.003")

        # Ajustement selon la chaîne
        chain_adjustments = {
            "ethereum": Decimal("1.2"),
            "bsc": Decimal("0.8"),
            "polygon": Decimal("0.8"),
            "arbitrum": Decimal("0.9"),
            "optimism": Decimal("0.9"),
            "avalanche": Decimal("0.8"),
            "solana": Decimal("0.6"),
        }

        adjustment = chain_adjustments.get(chain_from, Decimal("1.0"))

        # Si tokens identiques, pas de frais DEX
        if token_from == token_to:
            return Decimal("0")

        return amount * dex_fee_percentage * adjustment

    async def _estimate_transfer_time(
        self,
        protocol: BridgeProtocol,
        chain_from: str,
        chain_to: str,
    ) -> int:
        """Estime le temps de transfert en secondes"""
        base_times = {
            BridgeProtocol.LAYERZERO: 120,
            BridgeProtocol.AXELAR: 180,
            BridgeProtocol.WORMHOLE: 90,
            BridgeProtocol.CCTP: 60,
            BridgeProtocol.ACROSS: 150,
            BridgeProtocol.HOP: 100,
            BridgeProtocol.CONNEXT: 120,
            BridgeProtocol.SYNAPSE: 110,
            BridgeProtocol.STARGATE: 80,
        }.get(protocol, 120)

        # Ajustement selon les chaînes
        slow_chains = {"ethereum", "solana"}
        fast_chains = {"arbitrum", "optimism", "bsc", "polygon"}

        adjustment = 1.0
        if chain_from in slow_chains or chain_to in slow_chains:
            adjustment *= 1.5
        if chain_from in fast_chains and chain_to in fast_chains:
            adjustment *= 0.7

        return int(base_times * adjustment)

    async def _check_liquidity(
        self,
        protocol: BridgeProtocol,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
    ) -> bool:
        """Vérifie la disponibilité de la liquidité"""
        # Simulation simple - dans la réalité, on interrogerait les APIs
        # des différents fournisseurs de liquidité

        # Limites de liquidité simulées
        max_liquidity = {
            BridgeProtocol.LAYERZERO: Decimal("1000000"),
            BridgeProtocol.AXELAR: Decimal("500000"),
            BridgeProtocol.WORMHOLE: Decimal("2000000"),
            BridgeProtocol.CCTP: Decimal("500000"),
            BridgeProtocol.ACROSS: Decimal("300000"),
            BridgeProtocol.HOP: Decimal("200000"),
        }.get(protocol, Decimal("100000"))

        return amount <= max_liquidity

    def _calculate_route_confidence(
        self,
        protocol: BridgeProtocol,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance d'une route"""
        base_confidence = {
            BridgeProtocol.LAYERZERO: 0.95,
            BridgeProtocol.AXELAR: 0.92,
            BridgeProtocol.WORMHOLE: 0.97,
            BridgeProtocol.CCTP: 0.98,
            BridgeProtocol.ACROSS: 0.90,
            BridgeProtocol.HOP: 0.88,
            BridgeProtocol.CONNEXT: 0.85,
            BridgeProtocol.SYNAPSE: 0.87,
            BridgeProtocol.STARGATE: 0.93,
        }.get(protocol, 0.90)

        # Réduction pour les gros montants
        if amount > Decimal("100000"):
            base_confidence -= 0.10
        elif amount > Decimal("50000"):
            base_confidence -= 0.05
        elif amount > Decimal("10000"):
            base_confidence -= 0.02

        # Réduction basée sur la performance du circuit breaker
        if protocol in self.circuit_breakers:
            cb = self.circuit_breakers[protocol]
            if cb.failure_count > 0:
                base_confidence -= min(0.2, cb.failure_count * 0.02)

        return max(0.5, min(0.99, base_confidence))

    def _get_dex_path(
        self,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
    ) -> List[str]:
        """Obtient le chemin DEX optimal"""
        # Dans la réalité, on interrogerait des APIs DEX
        # Simulation de chemins DEX courants
        if token_from == token_to:
            return [token_from]

        # Chemins courants
        common_paths = {
            ("ethereum", "bsc"): ["ETH", "WBNB"],
            ("bsc", "ethereum"): ["WBNB", "ETH"],
            ("ethereum", "polygon"): ["ETH", "WMATIC"],
            ("polygon", "ethereum"): ["WMATIC", "ETH"],
            ("arbitrum", "ethereum"): ["ETH", "ETH"],
            ("optimism", "ethereum"): ["ETH", "ETH"],
        }

        path = common_paths.get((chain_from, chain_to), [token_from, token_to])
        return path

    # ============================================================
    # MÉTHODES D'EXÉCUTION
    # ============================================================

    async def _approve_token(
        self,
        chain: str,
        token_address: str,
        amount: Decimal,
        wallet: BaseWallet,
        route: SwapRoute,
    ) -> bool:
        """Approuve un token pour le swap"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise CrossChainSwapError(f"Provider Web3 non trouvé pour {chain}")

            # Vérifier si l'approbation est nécessaire
            spender = self._get_spender_address(chain, route)
            allowance = await self._get_allowance(
                chain, token_address, wallet.address, spender
            )

            if allowance >= amount:
                logger.debug(f"Approbation déjà suffisante: {allowance}")
                return True

            # Construction de la transaction d'approbation
            token_contract = self._contracts[chain]["token"]

            # Vérification de la version du contrat
            try:
                approve_tx = token_contract.functions.approve(
                    Web3.to_checksum_address(spender),
                    int(amount * Decimal(1e18)),
                ).build_transaction({
                    "from": Web3.to_checksum_address(wallet.address),
                    "nonce": await provider.eth.get_transaction_count(wallet.address),
                    "gas": 100000,
                    "gasPrice": await provider.eth.gas_price,
                })
            except AttributeError:
                # Fallback pour les anciennes versions
                approve_tx = {
                    "from": Web3.to_checksum_address(wallet.address),
                    "to": Web3.to_checksum_address(token_address),
                    "data": f"0x095ea7b3{spender[2:].zfill(64)}{hex(int(amount * Decimal(1e18)))[2:].zfill(64)}",
                    "gas": 100000,
                    "gasPrice": await provider.eth.gas_price,
                    "nonce": await provider.eth.get_transaction_count(wallet.address),
                }

            # Signature et envoi
            signed_tx = wallet.sign_transaction(approve_tx)
            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            # Attente de la confirmation
            receipt = await self._wait_for_transaction(provider, tx_hash)

            logger.info(f"Approbation réussie: {tx_hash.hex()}")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approbation: {e}")
            raise CrossChainSwapError(f"Erreur d'approbation: {e}")

    async def _perform_swap(
        self,
        chain: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        route: SwapRoute,
        wallet: BaseWallet,
        slippage_tolerance: Decimal,
    ) -> Dict[str, Any]:
        """Effectue le swap sur la chaîne source"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise CrossChainSwapError(f"Provider Web3 non trouvé pour {chain}")

            router_contract = self._contracts[chain]["router"]

            # Préparation du swap
            path = [Web3.to_checksum_address(t) for t in route.dex_path]
            amount_in = int(amount * Decimal(1e18))

            # Calcul du montant minimum avec slippage
            amount_out_min = await self._get_amount_out_min(
                chain, token_from, token_to, amount, slippage_tolerance
            )

            # Construction de la transaction
            swap_tx = await self._build_swap_transaction(
                chain,
                router_contract,
                path,
                amount_in,
                amount_out_min,
                wallet.address,
                route,
            )

            # Signature et envoi
            signed_tx = wallet.sign_transaction(swap_tx)
            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            # Attente de la confirmation
            receipt = await self._wait_for_transaction(provider, tx_hash)

            # Récupération du résultat
            amount_out = await self._get_swap_result(
                chain, token_to, wallet.address, receipt
            )

            return {
                "tx_hash": tx_hash.hex(),
                "amount_in": amount,
                "amount_out": amount_out,
                "receipt": receipt,
            }

        except Exception as e:
            logger.error(f"Erreur de swap: {e}")
            raise CrossChainSwapError(f"Erreur de swap: {e}")

    async def _bridge_tokens(
        self,
        chain_from: str,
        chain_to: str,
        token: str,
        amount: Decimal,
        to_address: str,
        route: SwapRoute,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Bridge les tokens vers la chaîne destination"""
        try:
            provider = self.web3_providers.get(chain_from)
            if not provider:
                raise CrossChainSwapError(f"Provider Web3 non trouvé pour {chain_from}")

            bridge_contract = self._contracts[chain_from]["bridge"]
            protocol = route.bridge_protocols[0]

            # Construction du bridge selon le protocole
            bridge_data = await self._build_bridge_transaction(
                chain_from=chain_from,
                chain_to=chain_to,
                token=token,
                amount=amount,
                to_address=to_address,
                protocol=protocol,
                wallet=wallet,
            )

            # Envoi de la transaction
            signed_tx = wallet.sign_transaction(bridge_data["tx"])
            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            # Attente de la confirmation initiale
            receipt = await self._wait_for_transaction(provider, tx_hash)

            # Attente de la finalisation cross-chain
            bridge_tx_id = bridge_data.get("bridge_tx_id", tx_hash.hex())
            amount_received = await self._wait_for_cross_chain_completion(
                protocol,
                chain_from,
                chain_to,
                bridge_tx_id,
                amount,
            )

            return {
                "tx_hash": tx_hash.hex(),
                "bridge_tx_id": bridge_tx_id,
                "amount_received": amount_received,
                "receipt": receipt,
            }

        except Exception as e:
            logger.error(f"Erreur de bridge: {e}")
            raise CrossChainSwapError(f"Erreur de bridge: {e}")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_token_balance(
        self,
        chain: str,
        token_address: str,
        wallet_address: str,
    ) -> Decimal:
        """Obtient le solde d'un token"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            # Si le token est la chaîne native
            if token_address == "0x0000000000000000000000000000000000000000":
                balance = await provider.eth.get_balance(wallet_address)
                return Decimal(str(balance)) / Decimal(1e18)

            # Token ERC20
            token_abi = self._load_abi("erc20_abi.json")
            token_contract = provider.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=token_abi,
            )
            balance = await token_contract.functions.balanceOf(wallet_address).call()
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            logger.error(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _get_allowance(
        self,
        chain: str,
        token_address: str,
        owner: str,
        spender: str,
    ) -> Decimal:
        """Obtient l'allowance d'un token"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            token_contract = self._contracts[chain].get("token")
            if not token_contract:
                return Decimal("0")

            allowance = await token_contract.functions.allowance(
                Web3.to_checksum_address(owner),
                Web3.to_checksum_address(spender),
            ).call()

            return Decimal(str(allowance)) / Decimal(1e18)

        except Exception as e:
            logger.warning(f"Erreur d'allowance: {e}")
            return Decimal("0")

    async def _get_amount_out_min(
        self,
        chain: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        slippage_tolerance: Decimal,
    ) -> int:
        """Calcule le montant minimum avec slippage"""
        try:
            # Estimation du montant reçu
            amount_out = await self._get_amount_out(chain, token_from, token_to, amount)

            # Application du slippage
            amount_out_min = int(amount_out * (1 - float(slippage_tolerance)) * Decimal(1e18))
            return amount_out_min

        except Exception as e:
            logger.warning(f"Erreur de calcul amount out: {e}")
            return int(amount * (1 - float(slippage_tolerance)) * Decimal(1e18))

    async def _get_amount_out(
        self,
        chain: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
    ) -> Decimal:
        """Estime le montant reçu pour un swap"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return amount * Decimal("0.997")

            router_contract = self._contracts[chain].get("router")
            if not router_contract:
                return amount * Decimal("0.997")

            path = [Web3.to_checksum_address(token_from), Web3.to_checksum_address(token_to)]
            amount_in = int(amount * Decimal(1e18))

            # Appel getAmountsOut
            amounts = await router_contract.functions.getAmountsOut(
                amount_in,
                path,
            ).call()

            return Decimal(str(amounts[-1])) / Decimal(1e18)

        except Exception as e:
            logger.warning(f"Erreur getAmountsOut: {e}")
            return amount * Decimal("0.997")

    async def _wait_for_transaction(
        self,
        provider: Web3,
        tx_hash: HexBytes,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                receipt = await provider.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt.status == 1:
                        return dict(receipt)
                    else:
                        raise CrossChainSwapError(f"Transaction échouée: {tx_hash.hex()}")
            except Exception:
                pass
            await asyncio.sleep(2)

        raise CrossChainSwapError(f"Timeout de la transaction: {tx_hash.hex()}")

    async def _wait_for_cross_chain_completion(
        self,
        protocol: BridgeProtocol,
        chain_from: str,
        chain_to: str,
        bridge_tx_id: str,
        amount: Decimal,
        timeout: int = 1800,
    ) -> Decimal:
        """
        Attend la finalisation d'une transaction cross-chain

        Args:
            protocol: Protocole de bridge
            chain_from: Chaîne source
            chain_to: Chaîne destination
            bridge_tx_id: ID de la transaction bridge
            amount: Montant attendu
            timeout: Timeout en secondes

        Returns:
            Montant reçu
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Vérification du statut via le bridge manager
                status = await self.bridge_manager.get_bridge_status(
                    protocol,
                    bridge_tx_id,
                )

                if status.get("status") == "completed":
                    received = Decimal(str(status.get("amount_received", str(amount))))
                    logger.info(f"Bridge cross-chain terminé: {received}")
                    return received

                elif status.get("status") == "failed":
                    raise CrossChainSwapError(
                        f"Bridge cross-chain échoué: {status.get('error')}"
                    )

                # Progression
                progress = status.get("progress", 0)
                logger.debug(f"Progression du bridge: {progress}%")

            except Exception as e:
                logger.warning(f"Erreur de vérification du bridge: {e}")

            await asyncio.sleep(10)

        raise CrossChainSwapError(
            f"Timeout du bridge cross-chain: {bridge_tx_id}"
        )

    def _get_spender_address(self, chain: str, route: SwapRoute) -> str:
        """Obtient l'adresse du spender pour le swap"""
        # Adresse du router DEX
        dex_config = self.config.get("dex_contracts", {}).get(chain, {})
        return dex_config.get("router", "0x0000000000000000000000000000000000000000")

    async def _build_swap_transaction(
        self,
        chain: str,
        router_contract: Contract,
        path: List[str],
        amount_in: int,
        amount_out_min: int,
        to_address: str,
        route: SwapRoute,
    ) -> Dict[str, Any]:
        """Construit la transaction de swap"""
        provider = self.web3_providers.get(chain)
        if not provider:
            raise CrossChainSwapError(f"Provider Web3 non trouvé pour {chain}")

        deadline = int(time.time()) + 3600

        try:
            # Utilisation de la méthode standard
            swap_tx = router_contract.functions.swapExactTokensForTokens(
                amount_in,
                amount_out_min,
                path,
                Web3.to_checksum_address(to_address),
                deadline,
            ).build_transaction({
                "from": Web3.to_checksum_address(to_address),
                "nonce": await provider.eth.get_transaction_count(to_address),
                "gas": 200000,
                "gasPrice": await provider.eth.gas_price,
            })

            return dict(swap_tx)

        except Exception as e:
            logger.warning(f"Erreur de build swap tx: {e}")
            # Fallback simple
            return {
                "from": Web3.to_checksum_address(to_address),
                "to": Web3.to_checksum_address(path[0]),
                "value": amount_in,
                "gas": 200000,
                "gasPrice": await provider.eth.gas_price,
                "nonce": await provider.eth.get_transaction_count(to_address),
                "data": "0x",
            }

    async def _build_bridge_transaction(
        self,
        chain_from: str,
        chain_to: str,
        token: str,
        amount: Decimal,
        to_address: str,
        protocol: BridgeProtocol,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Construit la transaction de bridge"""
        provider = self.web3_providers.get(chain_from)
        if not provider:
            raise CrossChainSwapError(f"Provider Web3 non trouvé pour {chain_from}")

        bridge_contract = self._contracts[chain_from].get("bridge")
        if not bridge_contract:
            # Simuler un bridge si le contrat n'est pas disponible
            return {
                "tx": {
                    "from": Web3.to_checksum_address(to_address),
                    "to": Web3.to_checksum_address(token),
                    "value": int(amount * Decimal(1e18)),
                    "gas": 300000,
                    "gasPrice": await provider.eth.gas_price,
                    "nonce": await provider.eth.get_transaction_count(to_address),
                    "data": "0x",
                },
                "bridge_tx_id": f"sim_{uuid.uuid4().hex[:16]}",
            }

        try:
            # Construction selon le protocole
            chain_id_to = self._get_chain_id(chain_to)

            if protocol == BridgeProtocol.LAYERZERO:
                # LayerZero bridge
                bridge_data = await self._build_layerzero_tx(
                    bridge_contract,
                    token,
                    amount,
                    to_address,
                    chain_id_to,
                    provider,
                )
            elif protocol == BridgeProtocol.WORMHOLE:
                bridge_data = await self._build_wormhole_tx(
                    bridge_contract,
                    token,
                    amount,
                    to_address,
                    chain_id_to,
                    provider,
                )
            else:
                # Transaction générique
                bridge_data = {
                    "to": Web3.to_checksum_address(bridge_contract.address),
                    "value": 0,
                    "gas": 300000,
                    "gasPrice": await provider.eth.gas_price,
                    "nonce": await provider.eth.get_transaction_count(to_address),
                    "data": "0x",
                }

            return {
                "tx": bridge_data,
                "bridge_tx_id": f"{protocol.value}_{uuid.uuid4().hex[:16]}",
            }

        except Exception as e:
            logger.error(f"Erreur de construction bridge: {e}")
            raise CrossChainSwapError(f"Erreur de construction bridge: {e}")

    async def _build_layerzero_tx(
        self,
        contract: Contract,
        token: str,
        amount: Decimal,
        to_address: str,
        chain_id_to: int,
        provider: Web3,
    ) -> Dict[str, Any]:
        """Construit une transaction LayerZero"""
        try:
            # Récupération des paramètres LayerZero
            adapter_params = self._get_layerzero_adapter_params()
            bridge_contract = self._contracts.get("layerzero", {}).get("bridge")

            tx = contract.functions.bridge(
                Web3.to_checksum_address(token),
                int(amount * Decimal(1e18)),
                Web3.to_checksum_address(to_address),
                chain_id_to,
                adapter_params,
            ).build_transaction({
                "from": Web3.to_checksum_address(to_address),
                "nonce": await provider.eth.get_transaction_count(to_address),
                "gas": 500000,
                "gasPrice": await provider.eth.gas_price,
            })

            return dict(tx)

        except Exception as e:
            logger.error(f"Erreur LayerZero: {e}")
            raise

    async def _build_wormhole_tx(
        self,
        contract: Contract,
        token: str,
        amount: Decimal,
        to_address: str,
        chain_id_to: int,
        provider: Web3,
    ) -> Dict[str, Any]:
        """Construit une transaction Wormhole"""
        try:
            # Récupération de l'émulateur
            emitter = self._get_wormhole_emitter(chain_id_to)

            tx = contract.functions.bridge(
                Web3.to_checksum_address(token),
                int(amount * Decimal(1e18)),
                Web3.to_checksum_address(to_address),
                chain_id_to,
                emitter,
            ).build_transaction({
                "from": Web3.to_checksum_address(to_address),
                "nonce": await provider.eth.get_transaction_count(to_address),
                "gas": 400000,
                "gasPrice": await provider.eth.gas_price,
            })

            return dict(tx)

        except Exception as e:
            logger.error(f"Erreur Wormhole: {e}")
            raise

    async def _get_swap_result(
        self,
        chain: str,
        token: str,
        wallet_address: str,
        receipt: Dict[str, Any],
    ) -> Decimal:
        """Récupère le résultat d'un swap"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            # Obtention du solde après la transaction
            balance_after = await self._get_token_balance(
                chain,
                token,
                wallet_address,
            )

            # Essayer d'extraire le montant des logs
            try:
                token_contract = self._contracts[chain].get("token")
                if token_contract:
                    # Recherche de l'événement Transfer
                    transfer_event = token_contract.events.Transfer()
                    for log in receipt.get("logs", []):
                        try:
                            event = transfer_event.process_log(log)
                            if event.get("args", {}).get("to", "").lower() == wallet_address.lower():
                                return Decimal(str(event["args"]["amount"])) / Decimal(1e18)
                        except Exception:
                            continue
            except Exception:
                pass

            return balance_after

        except Exception as e:
            logger.warning(f"Erreur de récupération du résultat: {e}")
            return Decimal("0")

    # ============================================================
    # MÉTHODES DE CONFIGURATION ET UTILITAIRES
    # ============================================================

    def _get_chain_id(self, chain_name: str) -> int:
        """Obtient l'ID de chaîne"""
        chain_ids = {
            "ethereum": 1,
            "bsc": 56,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "avalanche": 43114,
            "solana": 101,  # ID simulé
            "base": 8453,
            "linea": 59144,
            "scroll": 534352,
        }
        return chain_ids.get(chain_name, 1)

    def _get_layerzero_adapter_params(self) -> bytes:
        """Obtient les paramètres d'adaptateur LayerZero"""
        # Version 1, gas 200000
        return b"".join([b"\x00", (200000).to_bytes(4, "big")])

    def _get_wormhole_emitter(self, chain_id: int) -> str:
        """Obtient l'émulateur Wormhole pour une chaîne"""
        emitters = {
            1: "0x0000000000000000000000000000000000000000",
            56: "0x0000000000000000000000000000000000000000",
            137: "0x0000000000000000000000000000000000000000",
            42161: "0x0000000000000000000000000000000000000000",
            10: "0x0000000000000000000000000000000000000000",
            43114: "0x0000000000000000000000000000000000000000",
        }
        return emitters.get(chain_id, "0x0000000000000000000000000000000000000000")

    @lru_cache(maxsize=128)
    def get_token_address(
        self,
        chain: str,
        symbol: str,
    ) -> Optional[str]:
        """Obtient l'adresse d'un token par symbole"""
        token_addresses = self.config.get("tokens", {}).get(chain, {})
        return token_addresses.get(symbol.upper())

    @lru_cache(maxsize=128)
    def get_chain_name_from_id(self, chain_id: int) -> str:
        """Obtient le nom de la chaîne à partir de son ID"""
        chain_names = {
            1: "ethereum",
            56: "bsc",
            137: "polygon",
            42161: "arbitrum",
            10: "optimism",
            43114: "avalanche",
            101: "solana",
            8453: "base",
            59144: "linea",
            534352: "scroll",
        }
        return chain_names.get(chain_id, "ethereum")

    # ============================================================
    # MÉTHODES D'ANALYSE ET DE RAPPORT
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        completed_swaps = [
            s for s in self._swap_history
            if s.status == SwapStatus.COMPLETED
        ]

        failed_swaps = [
            s for s in self._swap_history
            if s.status == SwapStatus.FAILED
        ]

        total_volume = sum(
            s.amount_in or Decimal("0")
            for s in self._swap_history
            if s.amount_in
        )

        total_fees = sum(
            s.fees_total or Decimal("0")
            for s in self._swap_history
            if s.fees_total
        )

        return {
            "total_swaps": len(self._swap_history),
            "completed_swaps": len(completed_swaps),
            "failed_swaps": len(failed_swaps),
            "active_swaps": len(self._active_swaps),
            "success_rate": len(completed_swaps) / max(1, len(self._swap_history)),
            "total_volume": str(total_volume),
            "total_fees": str(total_fees),
            "avg_swap_time": self._calculate_avg_swap_time(),
            "bridge_usage": self._get_bridge_usage_stats(),
            "circuit_breakers": {
                p.value: {
                    "available": cb.is_available(),
                    "failure_count": cb.failure_count,
                    "success_count": cb.success_count,
                }
                for p, cb in self.circuit_breakers.items()
            },
        }

    def _calculate_avg_swap_time(self) -> float:
        """Calcule le temps moyen des swaps"""
        completed_swaps = [
            s for s in self._swap_history
            if s.status == SwapStatus.COMPLETED and s.start_time and s.end_time
        ]

        if not completed_swaps:
            return 0.0

        total_time = sum(
            (s.end_time - s.start_time).total_seconds()
            for s in completed_swaps
        )

        return total_time / len(completed_swaps)

    def _get_bridge_usage_stats(self) -> Dict[str, int]:
        """Obtient les statistiques d'utilisation des bridges"""
        usage = defaultdict(int)
        for swap in self._swap_history:
            if swap.route_used:
                for protocol in swap.route_used.bridge_protocols:
                    usage[protocol.value] += 1
        return dict(usage)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources CrossChainSwap...")

        # Fermeture des connexions
        for provider in self.web3_providers.values():
            try:
                # Web3 n'a pas de méthode de fermeture explicite
                pass
            except Exception:
                pass

        # Nettoyage du cache
        self._route_cache.clear()
        self._price_cache.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_cross_chain_swap(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    bridge_manager: BridgeManager,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> CrossChainSwap:
    """
    Crée une instance de CrossChainSwap

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        bridge_manager: Gestionnaire de bridges
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de CrossChainSwap
    """
    return CrossChainSwap(
        config=config,
        wallet_manager=wallet_manager,
        bridge_manager=bridge_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du système de swap cross-chain"""
    # Configuration
    config = {
        "dex_contracts": {
            "ethereum": {
                "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            },
            "bsc": {
                "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
            },
        },
        "bridge_contracts": {
            "ethereum": "0x...",
            "bsc": "0x...",
        },
        "tokens": {
            "ethereum": {
                "ETH": "0x0000000000000000000000000000000000000000",
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            },
            "bsc": {
                "BNB": "0x0000000000000000000000000000000000000000",
                "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            },
        },
    }

    # Création des Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "bsc": Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org")),
    }

    # Ajout du middleware PoA pour BSC
    web3_providers["bsc"].middleware_onion.inject(geth_poa_middleware, layer=0)

    # Création du wallet
    wallet_manager = MultiChainWallet(config={}, web3_providers=web3_providers)

    # Création du bridge manager
    bridge_manager = BridgeManager({})

    # Création du swap cross-chain
    cross_chain_swap = create_cross_chain_swap(
        config=config,
        wallet_manager=wallet_manager,
        bridge_manager=bridge_manager,
        web3_providers=web3_providers,
    )

    # Demande de devis
    routes = await cross_chain_swap.get_swap_quote(
        chain_from="ethereum",
        chain_to="bsc",
        token_from="ETH",
        token_to="BNB",
        amount=Decimal("1.0"),
    )

    print(f"Routes trouvées: {len(routes)}")
    for route in routes:
        print(f"  Protocole: {[p.value for p in route.bridge_protocols]}")
        print(f"  Frais estimés: {route.estimated_fees}")
        print(f"  Temps estimé: {route.estimated_time}s")

    # Exécution d'un swap
    if routes:
        request = CrossChainSwapRequest(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            chain_from="ethereum",
            chain_to="bsc",
            token_from="ETH",
            token_to="BNB",
            amount=Decimal("0.1"),
            wallet_address="0xYourWalletAddress",
            routing_strategy=RoutingStrategy.BALANCED,
        )

        result = await cross_chain_swap.execute_swap(request)
        print(f"Résultat: {result.status.value}")
        if result.status == SwapStatus.COMPLETED:
            print(f"  Montant reçu: {result.amount_received}")

    # Statistiques
    stats = cross_chain_swap.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await cross_chain_swap.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

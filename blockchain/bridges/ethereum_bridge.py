# blockchain/bridges/ethereum_bridge.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Bridge Ethereum Avancé

Ce module implémente un système complet de bridge pour la blockchain Ethereum
avec support de multiples protocoles de bridge (LayerZero, Wormhole, Axelar, etc.),
gestion des frais de gaz, optimisation des transactions, et mécanismes de sécurité
avancés.

Fonctionnalités principales:
- Support de multiples protocoles de bridge
- Gestion intelligente des frais de gaz
- Optimisation des transactions avec EIP-1559
- Surveillance en temps réel des bridges
- Mécanismes de fallback et reprise sur échec
- Intégration avec les systèmes de trading
- Support des tokens ERC-20 et ETH natif
- Gestion des approvals et allowances
- Monitoring des transactions cross-chain
"""

import asyncio
import hashlib
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
from eth_utils import to_checksum_address, is_address, to_hex

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
    from ..wallets.ethereum_wallet import EthereumWallet
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
    from ..wallets.ethereum_wallet import EthereumWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class EthereumBridgeProtocol(Enum):
    """Protocoles de bridge supportés sur Ethereum"""
    LAYERZERO = "layerzero"
    WORMHOLE = "wormhole"
    AXELAR = "axelar"
    CCTP = "cctp"  # Circle Cross-Chain Transfer Protocol
    ACROSS = "across"
    HOP = "hop"
    CONNEXT = "connext"
    SYNAPSE = "synapse"
    STARGATE = "stargate"
    DEBRIDGE = "debridge"
    LIQUIDITY = "liquidity"
    NATIVE = "native"  # Bridge natif Ethereum


class BridgeStatus(Enum):
    """Statuts d'un bridge"""
    PENDING = "pending"
    APPROVING = "approving"
    APPROVED = "approved"
    BRIDGING = "bridging"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    RETRYING = "retrying"
    REVERTED = "reverted"


class BridgeType(Enum):
    """Types de bridge"""
    LOCK_AND_MINT = "lock_and_mint"
    BURN_AND_MINT = "burn_and_mint"
    LOCK_AND_UNLOCK = "lock_and_unlock"
    SWAP = "swap"
    CCTP = "cctp"
    ZK = "zk"


@dataclass
class BridgeQuote:
    """Devis de bridge"""
    quote_id: str
    protocol: EthereumBridgeProtocol
    bridge_type: BridgeType
    token_from: str
    token_to: str
    amount: Decimal
    estimated_gas: Decimal
    estimated_fees: Decimal
    estimated_time: int  # secondes
    destination_chain: str
    destination_address: str
    min_amount_received: Decimal
    max_slippage: Decimal
    confidence: float
    quote_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol.value,
            "bridge_type": self.bridge_type.value,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "estimated_gas": str(self.estimated_gas),
            "estimated_fees": str(self.estimated_fees),
            "estimated_time": self.estimated_time,
            "destination_chain": self.destination_chain,
            "destination_address": self.destination_address,
            "min_amount_received": str(self.min_amount_received),
            "max_slippage": str(self.max_slippage),
            "confidence": self.confidence,
        }


@dataclass
class BridgeRequest:
    """Requête de bridge"""
    request_id: str
    protocol: EthereumBridgeProtocol
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    destination_chain: str
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600  # secondes
    use_fallback: bool = True
    max_gas_price: Optional[Decimal] = None
    priority_fee: Optional[Decimal] = None
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "protocol": self.protocol.value,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "source_address": self.source_address,
            "destination_address": self.destination_address,
            "destination_chain": self.destination_chain,
            "slippage_tolerance": str(self.slippage_tolerance),
            "deadline": self.deadline,
            "use_fallback": self.use_fallback,
            "max_gas_price": str(self.max_gas_price) if self.max_gas_price else None,
            "priority_fee": str(self.priority_fee) if self.priority_fee else None,
        }


@dataclass
class BridgeResult:
    """Résultat d'un bridge"""
    bridge_id: str
    request_id: str
    status: BridgeStatus
    protocol: EthereumBridgeProtocol
    tx_hash: Optional[str] = None
    bridge_tx_id: Optional[str] = None
    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    amount_received: Optional[Decimal] = None
    fees_total: Optional[Decimal] = None
    gas_used: Optional[Decimal] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    confirmations: int = 0
    target_confirmations: int = 12
    error_message: Optional[str] = None
    retry_count: int = 0
    transaction_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "bridge_id": self.bridge_id,
            "request_id": self.request_id,
            "status": self.status.value,
            "protocol": self.protocol.value,
            "tx_hash": self.tx_hash,
            "bridge_tx_id": self.bridge_tx_id,
            "amount_in": str(self.amount_in) if self.amount_in else None,
            "amount_out": str(self.amount_out) if self.amount_out else None,
            "amount_received": str(self.amount_received) if self.amount_received else None,
            "fees_total": str(self.fees_total) if self.fees_total else None,
            "gas_used": str(self.gas_used) if self.gas_used else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "confirmations": self.confirmations,
            "target_confirmations": self.target_confirmations,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }


# ============================================================
# CLASSES DE BASES
# ============================================================

class EthereumBridgeError(BlockchainError):
    """Erreur spécifique au bridge Ethereum"""
    pass


class EthereumBridge(BaseBridge):
    """
    Bridge Ethereum avancé avec support multi-protocoles
    """

    # ABIs des contrats
    ERC20_ABI = [
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
        {
            "constant": True,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "recipient", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "from", "type": "address"},
                {"indexed": True, "name": "to", "type": "address"},
                {"indexed": False, "name": "value", "type": "uint256"},
            ],
            "name": "Transfer",
            "type": "event",
        },
    ]

    BRIDGE_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
                {"name": "chainId", "type": "uint256"},
                {"name": "data", "type": "bytes"},
            ],
            "name": "bridge",
            "outputs": [{"name": "", "type": "bytes32"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "bridgeId", "type": "bytes32"}],
            "name": "getBridgeStatus",
            "outputs": [
                {"name": "status", "type": "uint8"},
                {"name": "amount", "type": "uint256"},
                {"name": "timestamp", "type": "uint256"},
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
    ]

    LAYERZERO_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
                {"name": "chainId", "type": "uint16"},
                {"name": "adapterParams", "type": "bytes"},
            ],
            "name": "bridge",
            "outputs": [],
            "payable": True,
            "stateMutability": "payable",
            "type": "function",
        },
    ]

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        web3_provider: Web3,
        bridge_manager: BridgeManager,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le bridge Ethereum

        Args:
            config: Configuration du bridge
            wallet_manager: Gestionnaire de wallets
            web3_provider: Provider Web3 pour Ethereum
            bridge_manager: Gestionnaire de bridges
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager)

        self.web3 = web3_provider
        self.bridge_manager = bridge_manager
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._active_bridges: Dict[str, BridgeResult] = {}
        self._bridge_history: List[BridgeResult] = []
        self._quote_cache: Dict[str, Tuple[float, BridgeQuote]] = {}
        self._contracts: Dict[str, Contract] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breaker par protocole
        self.circuit_breakers: Dict[EthereumBridgeProtocol, CircuitBreaker] = {
            protocol: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
            for protocol in EthereumBridgeProtocol
        }

        # Thread pool pour les opérations bloquantes
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des prix
        self._gas_price_cache: Dict[str, Dict[str, Any]] = {}
        self._token_decimals_cache: Dict[str, int] = {}

        # Charge les contrats
        self._load_contracts()

        # Initialise les routes de bridge
        self._bridge_routes: Dict[EthereumBridgeProtocol, Dict[str, Any]] = {}
        self._load_bridge_routes()

        logger.info("EthereumBridge initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats smart nécessaires"""
        try:
            # Contrat ERC20
            self._contracts["erc20"] = self.web3.eth.contract(
                abi=self.ERC20_ABI
            )

            # Contrat bridge générique
            bridge_address = self.config.get("bridge_contracts", {}).get("generic")
            if bridge_address:
                self._contracts["bridge"] = self.web3.eth.contract(
                    address=to_checksum_address(bridge_address),
                    abi=self.BRIDGE_ABI,
                )

            # Contrats spécifiques par protocole
            for protocol in EthereumBridgeProtocol:
                contract_config = self.config.get("protocols", {}).get(protocol.value, {})
                if contract_config.get("address"):
                    abi = self._get_protocol_abi(protocol)
                    self._contracts[protocol.value] = self.web3.eth.contract(
                        address=to_checksum_address(contract_config["address"]),
                        abi=abi,
                    )

            logger.info(f"Contrats chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise EthereumBridgeError(f"Erreur de chargement des contrats: {e}")

    def _get_protocol_abi(self, protocol: EthereumBridgeProtocol) -> List[Dict[str, Any]]:
        """Obtient l'ABI pour un protocole spécifique"""
        if protocol == EthereumBridgeProtocol.LAYERZERO:
            return self.LAYERZERO_ABI
        elif protocol == EthereumBridgeProtocol.WORMHOLE:
            # ABI Wormhole simplifiée
            return [
                {
                    "constant": False,
                    "inputs": [
                        {"name": "token", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                        {"name": "to", "type": "address"},
                        {"name": "chainId", "type": "uint16"},
                        {"name": "emitter", "type": "address"},
                    ],
                    "name": "bridge",
                    "outputs": [{"name": "", "type": "bytes32"}],
                    "payable": True,
                    "stateMutability": "payable",
                    "type": "function",
                },
            ]
        else:
            return self.BRIDGE_ABI

    def _load_bridge_routes(self) -> None:
        """Charge les routes de bridge disponibles"""
        # Routes par défaut pour Ethereum
        default_routes = {
            EthereumBridgeProtocol.LAYERZERO: {
                "supports": ["ethereum", "bsc", "polygon", "arbitrum", "optimism"],
                "tokens": ["ETH", "USDC", "USDT", "DAI", "WBTC"],
                "min_amount": Decimal("0.001"),
                "max_amount": Decimal("100000"),
            },
            EthereumBridgeProtocol.WORMHOLE: {
                "supports": ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "solana"],
                "tokens": ["ETH", "USDC", "USDT", "DAI", "WBTC"],
                "min_amount": Decimal("0.001"),
                "max_amount": Decimal("200000"),
            },
            EthereumBridgeProtocol.CCTP: {
                "supports": ["ethereum", "arbitrum", "optimism", "avalanche"],
                "tokens": ["USDC"],
                "min_amount": Decimal("1"),
                "max_amount": Decimal("100000"),
            },
            EthereumBridgeProtocol.ACROSS: {
                "supports": ["ethereum", "arbitrum", "optimism", "polygon"],
                "tokens": ["ETH", "USDC", "USDT", "DAI"],
                "min_amount": Decimal("0.01"),
                "max_amount": Decimal("50000"),
            },
            EthereumBridgeProtocol.HOP: {
                "supports": ["ethereum", "arbitrum", "optimism", "polygon"],
                "tokens": ["ETH", "USDC", "USDT", "DAI"],
                "min_amount": Decimal("0.01"),
                "max_amount": Decimal("30000"),
            },
        }

        # Fusion avec la configuration
        configured_routes = self.config.get("routes", {})
        for protocol, route in default_routes.items():
            if protocol.value in configured_routes:
                route.update(configured_routes[protocol.value])
            self._bridge_routes[protocol] = route

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_quote(
        self,
        token_from: str,
        token_to: str,
        amount: Decimal,
        destination_chain: str,
        destination_address: str,
        protocol: Optional[EthereumBridgeProtocol] = None,
        **kwargs,
    ) -> BridgeQuote:
        """
        Obtient un devis pour un bridge

        Args:
            token_from: Token source
            token_to: Token destination
            amount: Montant à bridge
            destination_chain: Chaîne destination
            destination_address: Adresse destination
            protocol: Protocole spécifique (optionnel)
            **kwargs: Arguments additionnels

        Returns:
            Devis de bridge
        """
        logger.info(
            f"Demande de devis: {amount} {token_from} -> {token_to} "
            f"vers {destination_chain}"
        )

        # Vérification du cache
        cache_key = f"{token_from}:{token_to}:{amount}:{destination_chain}:{protocol}"
        if cache_key in self._quote_cache:
            cached_time, quote = self._quote_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Devis retourné du cache")
                return quote

        try:
            # Sélection du protocole
            if protocol is None:
                protocol = await self._select_best_protocol(
                    token_from, token_to, destination_chain
                )

            # Vérification du circuit breaker
            if not self.circuit_breakers[protocol].is_available():
                logger.warning(f"Circuit breaker ouvert pour {protocol.value}")
                # Essayer un autre protocole
                fallback_protocol = await self._select_fallback_protocol(
                    protocol, token_from, token_to, destination_chain
                )
                if fallback_protocol:
                    protocol = fallback_protocol
                else:
                    raise EthereumBridgeError(
                        f"Protocole {protocol.value} indisponible"
                    )

            # Génération du devis
            quote = await self._generate_quote(
                protocol=protocol,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                destination_chain=destination_chain,
                destination_address=destination_address,
                **kwargs,
            )

            # Mise en cache
            self._quote_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "ethereum_bridge_quote",
                1,
                {
                    "protocol": protocol.value,
                    "token_from": token_from,
                    "token_to": token_to,
                    "destination_chain": destination_chain,
                },
            )

            return quote

        except Exception as e:
            logger.error(f"Erreur lors de la génération du devis: {e}")
            raise EthereumBridgeError(f"Erreur de génération de devis: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_bridge(self, request: BridgeRequest) -> BridgeResult:
        """
        Exécute un bridge

        Args:
            request: Requête de bridge

        Returns:
            Résultat du bridge
        """
        logger.info(f"Exécution du bridge: {request.request_id}")

        # Création du résultat initial
        result = BridgeResult(
            bridge_id=f"bridge_{uuid.uuid4().hex[:12]}",
            request_id=request.request_id,
            status=BridgeStatus.PENDING,
            protocol=request.protocol,
            start_time=datetime.now(),
        )

        self._active_bridges[result.bridge_id] = result

        try:
            # 1. Obtention du devis
            quote = await self.get_quote(
                token_from=request.token_from,
                token_to=request.token_to,
                amount=request.amount,
                destination_chain=request.destination_chain,
                destination_address=request.destination_address,
                protocol=request.protocol,
                slippage_tolerance=request.slippage_tolerance,
            )

            # 2. Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(request.source_address)
            if not wallet:
                raise EthereumBridgeError("Wallet non trouvé")

            # 3. Vérification du solde
            balance = await self._get_token_balance(
                request.token_from,
                wallet.address,
            )
            if balance < request.amount:
                raise EthereumBridgeError(
                    f"Solde insuffisant: {balance} < {request.amount}"
                )

            # 4. Approval du token si nécessaire
            result.status = BridgeStatus.APPROVING
            await self._approve_token(
                token=request.token_from,
                amount=request.amount,
                wallet=wallet,
                protocol=request.protocol,
            )
            result.status = BridgeStatus.APPROVED

            # 5. Exécution du bridge
            result.status = BridgeStatus.BRIDGING
            bridge_result = await self._perform_bridge(
                request=request,
                quote=quote,
                wallet=wallet,
            )

            # Mise à jour du résultat
            result.tx_hash = bridge_result.get("tx_hash")
            result.bridge_tx_id = bridge_result.get("bridge_tx_id")
            result.amount_in = request.amount
            result.amount_out = quote.min_amount_received

            # 6. Attente de la confirmation
            result.status = BridgeStatus.CONFIRMING
            final_result = await self._wait_for_confirmation(
                bridge_id=result.bridge_id,
                tx_hash=result.tx_hash,
                target_confirmations=12,
            )

            # Mise à jour finale
            result.status = BridgeStatus.COMPLETED
            result.amount_received = final_result.get("amount_received", result.amount_out)
            result.fees_total = quote.estimated_fees
            result.gas_used = quote.estimated_gas
            result.end_time = datetime.now()
            result.confirmations = final_result.get("confirmations", 12)

            logger.info(
                f"Bridge {result.bridge_id} terminé avec succès: "
                f"{result.amount_in} -> {result.amount_received}"
            )

            # Métriques
            self.metrics.record_increment(
                "ethereum_bridge_completed",
                {
                    "protocol": request.protocol.value,
                    "token_from": request.token_from,
                    "token_to": request.token_to,
                    "destination_chain": request.destination_chain,
                },
            )

            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution du bridge: {e}")
            result.status = BridgeStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()

            # Tentative de fallback
            if request.use_fallback and self._can_fallback(result):
                logger.info(f"Tentative de fallback pour {result.bridge_id}")
                fallback_result = await self._execute_fallback(request, result)
                if fallback_result.status == BridgeStatus.COMPLETED:
                    return fallback_result

            self.metrics.record_increment(
                "ethereum_bridge_failed",
                {
                    "protocol": request.protocol.value,
                    "error": str(e)[:50],
                },
            )

            return result

        finally:
            self._active_bridges.pop(result.bridge_id, None)
            self._bridge_history.append(result)
            if len(self._bridge_history) > 1000:
                self._bridge_history = self._bridge_history[-500:]

    async def get_bridge_status(self, bridge_id: str) -> Optional[BridgeResult]:
        """
        Obtient le statut d'un bridge

        Args:
            bridge_id: ID du bridge

        Returns:
            Statut du bridge ou None
        """
        # Vérifier dans les bridges actifs
        if bridge_id in self._active_bridges:
            return self._active_bridges[bridge_id]

        # Vérifier dans l'historique
        for bridge in reversed(self._bridge_history):
            if bridge.bridge_id == bridge_id:
                return bridge

        return None

    async def cancel_bridge(self, bridge_id: str) -> bool:
        """
        Annule un bridge en cours

        Args:
            bridge_id: ID du bridge

        Returns:
            True si annulé avec succès
        """
        if bridge_id not in self._active_bridges:
            return False

        result = self._active_bridges[bridge_id]
        if result.status in [BridgeStatus.COMPLETED, BridgeStatus.FAILED]:
            return False

        result.status = BridgeStatus.CANCELLED
        result.end_time = datetime.now()
        logger.info(f"Bridge {bridge_id} annulé")

        return True

    # ============================================================
    # MÉTHODES INTERNES PRINCIPALES
    # ============================================================

    async def _select_best_protocol(
        self,
        token_from: str,
        token_to: str,
        destination_chain: str,
    ) -> EthereumBridgeProtocol:
        """Sélectionne le meilleur protocole pour le bridge"""
        available_protocols = []

        for protocol, route in self._bridge_routes.items():
            # Vérification du circuit breaker
            if not self.circuit_breakers[protocol].is_available():
                continue

            # Vérification du support de la chaîne
            if destination_chain not in route.get("supports", []):
                continue

            # Vérification du support du token
            if token_from not in route.get("tokens", []):
                continue

            available_protocols.append(protocol)

        if not available_protocols:
            raise EthereumBridgeError("Aucun protocole disponible")

        # Sélection du protocole avec le meilleur score
        scores = []
        for protocol in available_protocols:
            score = await self._score_protocol(
                protocol, token_from, token_to, destination_chain
            )
            scores.append((score, protocol))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]

    async def _select_fallback_protocol(
        self,
        failed_protocol: EthereumBridgeProtocol,
        token_from: str,
        token_to: str,
        destination_chain: str,
    ) -> Optional[EthereumBridgeProtocol]:
        """Sélectionne un protocole de fallback"""
        for protocol in self._bridge_routes.keys():
            if protocol == failed_protocol:
                continue
            if not self.circuit_breakers[protocol].is_available():
                continue
            if destination_chain not in self._bridge_routes[protocol].get("supports", []):
                continue
            if token_from not in self._bridge_routes[protocol].get("tokens", []):
                continue
            return protocol
        return None

    async def _score_protocol(
        self,
        protocol: EthereumBridgeProtocol,
        token_from: str,
        token_to: str,
        destination_chain: str,
    ) -> float:
        """Calcule un score pour un protocole"""
        try:
            # Simulation d'un devis pour évaluer les coûts
            quote = await self._generate_quote(
                protocol=protocol,
                token_from=token_from,
                token_to=token_to,
                amount=Decimal("1"),
                destination_chain=destination_chain,
                destination_address="0x0000000000000000000000000000000000000000",
                simulate=True,
            )

            # Score basé sur les frais et le temps
            cost_score = 1.0 - float(quote.estimated_fees / Decimal("0.01"))
            time_score = 1.0 - (quote.estimated_time / 1800.0)
            confidence_score = quote.confidence

            return cost_score * 0.4 + time_score * 0.3 + confidence_score * 0.3

        except Exception:
            return 0.0

    async def _generate_quote(
        self,
        protocol: EthereumBridgeProtocol,
        token_from: str,
        token_to: str,
        amount: Decimal,
        destination_chain: str,
        destination_address: str,
        **kwargs,
    ) -> BridgeQuote:
        """Génère un devis pour un protocole spécifique"""
        try:
            # Estimation des frais
            gas_estimate = await self._estimate_gas(protocol, amount)
            bridge_fees = await self._estimate_bridge_fees(
                protocol, token_from, token_to, amount, destination_chain
            )
            slippage = kwargs.get("slippage_tolerance", Decimal("0.005"))

            # Estimation du temps
            estimated_time = await self._estimate_transfer_time(
                protocol, destination_chain
            )

            # Calcul du montant minimum reçu
            min_amount_received = amount * (1 - float(slippage))

            # Niveau de confiance
            confidence = self._calculate_confidence(protocol, amount)

            return BridgeQuote(
                quote_id=f"quote_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                bridge_type=await self._get_bridge_type(protocol),
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                estimated_gas=gas_estimate,
                estimated_fees=bridge_fees,
                estimated_time=estimated_time,
                destination_chain=destination_chain,
                destination_address=destination_address,
                min_amount_received=min_amount_received,
                max_slippage=slippage,
                confidence=confidence,
                quote_data=kwargs,
            )

        except Exception as e:
            logger.error(f"Erreur de génération de devis pour {protocol.value}: {e}")
            raise

    async def _perform_bridge(
        self,
        request: BridgeRequest,
        quote: BridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute le bridge"""
        try:
            protocol = request.protocol

            # Construction de la transaction selon le protocole
            if protocol == EthereumBridgeProtocol.LAYERZERO:
                tx_data = await self._build_layerzero_transaction(request, quote, wallet)
            elif protocol == EthereumBridgeProtocol.WORMHOLE:
                tx_data = await self._build_wormhole_transaction(request, quote, wallet)
            elif protocol == EthereumBridgeProtocol.CCTP:
                tx_data = await self._build_cctp_transaction(request, quote, wallet)
            else:
                tx_data = await self._build_generic_transaction(request, quote, wallet)

            # Envoi de la transaction
            tx_hash = await self._send_transaction(tx_data, wallet)

            # Récupération du bridge_tx_id
            bridge_tx_id = await self._extract_bridge_tx_id(tx_hash, protocol)

            return {
                "tx_hash": tx_hash.hex(),
                "bridge_tx_id": bridge_tx_id,
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution du bridge: {e}")
            raise

    async def _wait_for_confirmation(
        self,
        bridge_id: str,
        tx_hash: Optional[str],
        target_confirmations: int = 12,
        timeout: int = 3600,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'un bridge"""
        if not tx_hash:
            raise EthereumBridgeError("Hash de transaction manquant")

        start_time = time.time()
        hex_hash = HexBytes(tx_hash)

        while time.time() - start_time < timeout:
            try:
                # Vérification de la transaction
                receipt = await self.web3.eth.get_transaction_receipt(hex_hash)
                if receipt:
                    confirmations = await self._get_confirmations(hex_hash)
                    if confirmations >= target_confirmations:
                        # Vérification du statut cross-chain
                        status = await self._check_bridge_status(bridge_id)
                        if status.get("status") == "completed":
                            return {
                                "amount_received": Decimal(str(status.get("amount", 0))),
                                "confirmations": confirmations,
                            }

                # Mise à jour du nombre de confirmations
                self._update_bridge_confirmations(bridge_id, await self._get_confirmations(hex_hash))

            except Exception as e:
                logger.warning(f"Erreur de vérification: {e}")

            await asyncio.sleep(10)

        raise EthereumBridgeError(f"Timeout de confirmation: {tx_hash}")

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_layerzero_transaction(
        self,
        request: BridgeRequest,
        quote: BridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Construit une transaction LayerZero"""
        contract = self._contracts.get("layerzero")
        if not contract:
            raise EthereumBridgeError("Contrat LayerZero non trouvé")

        # Récupération de l'ID de chaîne
        chain_id = self._get_chain_id(request.destination_chain)

        # Paramètres d'adaptateur
        adapter_params = self._get_layerzero_adapter_params()

        # Construction
        tx = contract.functions.bridge(
            to_checksum_address(request.token_from),
            int(request.amount * Decimal(1e18)),
            to_checksum_address(request.destination_address),
            chain_id,
            adapter_params,
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "nonce": await self.web3.eth.get_transaction_count(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(),
        })

        return dict(tx)

    async def _build_wormhole_transaction(
        self,
        request: BridgeRequest,
        quote: BridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Construit une transaction Wormhole"""
        contract = self._contracts.get("wormhole")
        if not contract:
            raise EthereumBridgeError("Contrat Wormhole non trouvé")

        chain_id = self._get_chain_id(request.destination_chain)
        emitter = self._get_wormhole_emitter(chain_id)

        tx = contract.functions.bridge(
            to_checksum_address(request.token_from),
            int(request.amount * Decimal(1e18)),
            to_checksum_address(request.destination_address),
            chain_id,
            to_checksum_address(emitter),
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "nonce": await self.web3.eth.get_transaction_count(request.source_address),
            "gas": 250000,
            "gasPrice": await self._get_gas_price(),
        })

        return dict(tx)

    async def _build_cctp_transaction(
        self,
        request: BridgeRequest,
        quote: BridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Construit une transaction CCTP (Circle)"""
        contract = self._contracts.get("cctp")
        if not contract:
            raise EthereumBridgeError("Contrat CCTP non trouvé")

        # Récupération du domaine Circle
        domain = self._get_circle_domain(request.destination_chain)

        tx = contract.functions.depositForBurn(
            int(request.amount * Decimal(1e6)),  # USDC a 6 décimales
            domain,
            to_checksum_address(request.destination_address),
            to_checksum_address(request.token_from),
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "nonce": await self.web3.eth.get_transaction_count(request.source_address),
            "gas": 200000,
            "gasPrice": await self._get_gas_price(),
        })

        return dict(tx)

    async def _build_generic_transaction(
        self,
        request: BridgeRequest,
        quote: BridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Construit une transaction générique de bridge"""
        contract = self._contracts.get("bridge")
        if not contract:
            # Fallback: construction manuelle
            chain_id = self._get_chain_id(request.destination_chain)
            return {
                "from": to_checksum_address(request.source_address),
                "to": to_checksum_address(self.config.get("bridge_address", "0x")),
                "value": 0,
                "gas": 300000,
                "gasPrice": await self._get_gas_price(),
                "nonce": await self.web3.eth.get_transaction_count(request.source_address),
                "data": f"0x{chain_id:064x}",
            }

        chain_id = self._get_chain_id(request.destination_chain)

        tx = contract.functions.bridge(
            to_checksum_address(request.token_from),
            int(request.amount * Decimal(1e18)),
            to_checksum_address(request.destination_address),
            chain_id,
            b"",
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "nonce": await self.web3.eth.get_transaction_count(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(),
        })

        return dict(tx)

    # ============================================================
    # MÉTHODES D'APPROBATION ET TRANSFERT
    # ============================================================

    async def _approve_token(
        self,
        token: str,
        amount: Decimal,
        wallet: BaseWallet,
        protocol: EthereumBridgeProtocol,
    ) -> bool:
        """Approuve un token pour le bridge"""
        try:
            # Si le token est natif, pas d'approbation nécessaire
            if token == "ETH" or token == "0x0000000000000000000000000000000000000000":
                return True

            # Récupération du spender
            spender = self._get_spender_address(protocol)

            # Vérification de l'allowance actuelle
            allowance = await self._get_allowance(token, wallet.address, spender)

            if allowance >= amount:
                logger.debug(f"Allowance suffisante: {allowance} >= {amount}")
                return True

            # Construction de la transaction d'approbation
            token_contract = self._contracts["erc20"].copy()
            token_contract.address = to_checksum_address(token)

            approve_tx = token_contract.functions.approve(
                to_checksum_address(spender),
                int(amount * Decimal(1e18)),
            ).build_transaction({
                "from": to_checksum_address(wallet.address),
                "nonce": await self.web3.eth.get_transaction_count(wallet.address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price(),
            })

            # Envoi de la transaction
            signed_tx = wallet.sign_transaction(approve_tx)
            tx_hash = await self.web3.eth.send_raw_transaction(signed_tx)

            # Attente de la confirmation
            receipt = await self._wait_for_transaction(tx_hash, timeout=120)
            if receipt.get("status") != 1:
                raise EthereumBridgeError("Échec de l'approbation")

            logger.info(f"Approbation réussie: {tx_hash.hex()}")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approbation: {e}")
            raise EthereumBridgeError(f"Erreur d'approbation: {e}")

    async def _send_transaction(
        self,
        tx_data: Dict[str, Any],
        wallet: BaseWallet,
    ) -> HexBytes:
        """Envoie une transaction signée"""
        try:
            # Signature
            signed_tx = wallet.sign_transaction(tx_data)

            # Envoi
            tx_hash = await self.web3.eth.send_raw_transaction(signed_tx)
            logger.info(f"Transaction envoyée: {tx_hash.hex()}")

            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'envoi de transaction: {e}")
            raise EthereumBridgeError(f"Erreur d'envoi de transaction: {e}")

    async def _wait_for_transaction(
        self,
        tx_hash: HexBytes,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                receipt = await self.web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return dict(receipt)
            except Exception:
                pass
            await asyncio.sleep(2)

        raise EthereumBridgeError(f"Timeout de transaction: {tx_hash.hex()}")

    # ============================================================
    # MÉTHODES DE VÉRIFICATION ET MONITORING
    # ============================================================

    async def _check_bridge_status(self, bridge_id: str) -> Dict[str, Any]:
        """Vérifie le statut d'un bridge"""
        try:
            # Récupération du bridge
            bridge = await self.get_bridge_status(bridge_id)
            if not bridge:
                return {"status": "unknown"}

            # Vérification via le bridge manager
            if bridge.bridge_tx_id:
                status = await self.bridge_manager.get_bridge_status(
                    bridge.protocol.value,
                    bridge.bridge_tx_id,
                )
                return status

            # Vérification via la blockchain
            if bridge.tx_hash:
                receipt = await self.web3.eth.get_transaction_receipt(
                    HexBytes(bridge.tx_hash)
                )
                if receipt:
                    confirmations = await self._get_confirmations(HexBytes(bridge.tx_hash))
                    return {
                        "status": "completed" if confirmations >= 12 else "confirming",
                        "confirmations": confirmations,
                        "amount": str(bridge.amount_out) if bridge.amount_out else "0",
                    }

            return {"status": "pending"}

        except Exception as e:
            logger.warning(f"Erreur de vérification du statut: {e}")
            return {"status": "unknown", "error": str(e)}

    async def _get_confirmations(self, tx_hash: HexBytes) -> int:
        """Obtient le nombre de confirmations d'une transaction"""
        try:
            receipt = await self.web3.eth.get_transaction_receipt(tx_hash)
            if not receipt:
                return 0

            block_number = receipt["blockNumber"]
            current_block = await self.web3.eth.block_number

            return current_block - block_number + 1

        except Exception:
            return 0

    def _update_bridge_confirmations(self, bridge_id: str, confirmations: int) -> None:
        """Met à jour le nombre de confirmations d'un bridge"""
        if bridge_id in self._active_bridges:
            self._active_bridges[bridge_id].confirmations = confirmations

    # ============================================================
    # MÉTHODES D'ESTIMATION
    # ============================================================

    async def _estimate_gas(
        self,
        protocol: EthereumBridgeProtocol,
        amount: Decimal,
    ) -> Decimal:
        """Estime les frais de gaz"""
        try:
            # Estimation de base par protocole
            base_gas = {
                EthereumBridgeProtocol.LAYERZERO: 300000,
                EthereumBridgeProtocol.WORMHOLE: 250000,
                EthereumBridgeProtocol.CCTP: 200000,
                EthereumBridgeProtocol.ACROSS: 150000,
                EthereumBridgeProtocol.HOP: 150000,
                EthereumBridgeProtocol.CONNEXT: 200000,
                EthereumBridgeProtocol.SYNAPSE: 180000,
                EthereumBridgeProtocol.STARGATE: 150000,
            }.get(protocol, 200000)

            # Ajustement selon le montant
            gas_factor = 1.0 + (float(amount) / 1000.0)
            estimated_gas = int(base_gas * min(gas_factor, 2.0))

            # Obtention du prix du gaz
            gas_price = await self._get_gas_price()
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            total_cost = Decimal(str(estimated_gas)) * gas_price_decimal
            return total_cost

        except Exception as e:
            logger.warning(f"Erreur d'estimation du gaz: {e}")
            return Decimal("0.001")

    async def _estimate_bridge_fees(
        self,
        protocol: EthereumBridgeProtocol,
        token_from: str,
        token_to: str,
        amount: Decimal,
        destination_chain: str,
    ) -> Decimal:
        """Estime les frais de bridge"""
        # Frais fixes par protocole
        fixed_fees = {
            EthereumBridgeProtocol.LAYERZERO: Decimal("0.0005"),
            EthereumBridgeProtocol.WORMHOLE: Decimal("0.0003"),
            EthereumBridgeProtocol.CCTP: Decimal("0.0001"),
            EthereumBridgeProtocol.ACROSS: Decimal("0.0004"),
            EthereumBridgeProtocol.HOP: Decimal("0.0006"),
            EthereumBridgeProtocol.CONNEXT: Decimal("0.0007"),
            EthereumBridgeProtocol.SYNAPSE: Decimal("0.0005"),
            EthereumBridgeProtocol.STARGATE: Decimal("0.0004"),
        }.get(protocol, Decimal("0.0005"))

        # Frais variables
        variable_fees = amount * Decimal("0.0005")

        # Frais de destination
        destination_fees = {
            "ethereum": Decimal("0.001"),
            "bsc": Decimal("0.0001"),
            "polygon": Decimal("0.00005"),
            "arbitrum": Decimal("0.00008"),
            "optimism": Decimal("0.00008"),
            "avalanche": Decimal("0.00006"),
        }.get(destination_chain, Decimal("0.0001"))

        return fixed_fees + variable_fees + destination_fees

    async def _estimate_transfer_time(
        self,
        protocol: EthereumBridgeProtocol,
        destination_chain: str,
    ) -> int:
        """Estime le temps de transfert en secondes"""
        base_time = {
            EthereumBridgeProtocol.LAYERZERO: 120,
            EthereumBridgeProtocol.WORMHOLE: 90,
            EthereumBridgeProtocol.CCTP: 60,
            EthereumBridgeProtocol.ACROSS: 150,
            EthereumBridgeProtocol.HOP: 100,
            EthereumBridgeProtocol.CONNEXT: 120,
            EthereumBridgeProtocol.SYNAPSE: 110,
            EthereumBridgeProtocol.STARGATE: 80,
        }.get(protocol, 120)

        # Ajustement selon la chaîne de destination
        slow_chains = {"ethereum", "solana"}
        fast_chains = {"arbitrum", "optimism", "bsc", "polygon"}

        adjustment = 1.0
        if destination_chain in slow_chains:
            adjustment *= 1.5
        elif destination_chain in fast_chains:
            adjustment *= 0.7

        return int(base_time * adjustment)

    async def _get_gas_price(self) -> int:
        """Obtient le prix du gaz actuel"""
        try:
            # Vérification du cache
            cache_key = "gas_price"
            if cache_key in self._gas_price_cache:
                cached_data = self._gas_price_cache[cache_key]
                if time.time() - cached_data.get("timestamp", 0) < 10:
                    return cached_data.get("price", 0)

            # Obtention du prix du gaz
            gas_price = await self.web3.eth.gas_price

            # Mise en cache
            self._gas_price_cache[cache_key] = {
                "price": gas_price,
                "timestamp": time.time(),
            }

            return gas_price

        except Exception as e:
            logger.warning(f"Erreur d'obtention du gaz: {e}")
            return 1000000000  # 1 Gwei par défaut

    async def _get_token_balance(
        self,
        token_address: str,
        wallet_address: str,
    ) -> Decimal:
        """Obtient le solde d'un token"""
        try:
            if token_address == "ETH" or token_address == "0x0000000000000000000000000000000000000000":
                balance = await self.web3.eth.get_balance(wallet_address)
                return Decimal(str(balance)) / Decimal(1e18)

            token_contract = self._contracts["erc20"].copy()
            token_contract.address = to_checksum_address(token_address)

            decimals = await self._get_token_decimals(token_address)
            balance = await token_contract.functions.balanceOf(
                to_checksum_address(wallet_address)
            ).call()

            return Decimal(str(balance)) / Decimal(10 ** decimals)

        except Exception as e:
            logger.error(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _get_allowance(
        self,
        token_address: str,
        owner: str,
        spender: str,
    ) -> Decimal:
        """Obtient l'allowance d'un token"""
        try:
            token_contract = self._contracts["erc20"].copy()
            token_contract.address = to_checksum_address(token_address)

            decimals = await self._get_token_decimals(token_address)
            allowance = await token_contract.functions.allowance(
                to_checksum_address(owner),
                to_checksum_address(spender),
            ).call()

            return Decimal(str(allowance)) / Decimal(10 ** decimals)

        except Exception as e:
            logger.warning(f"Erreur d'allowance: {e}")
            return Decimal("0")

    async def _get_token_decimals(self, token_address: str) -> int:
        """Obtient le nombre de décimales d'un token"""
        if token_address in self._token_decimals_cache:
            return self._token_decimals_cache[token_address]

        try:
            token_contract = self._contracts["erc20"].copy()
            token_contract.address = to_checksum_address(token_address)

            decimals = await token_contract.functions.decimals().call()
            self._token_decimals_cache[token_address] = decimals
            return decimals

        except Exception:
            return 18  # Par défaut pour l'ETH

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _calculate_confidence(
        self,
        protocol: EthereumBridgeProtocol,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            EthereumBridgeProtocol.LAYERZERO: 0.95,
            EthereumBridgeProtocol.WORMHOLE: 0.97,
            EthereumBridgeProtocol.CCTP: 0.98,
            EthereumBridgeProtocol.ACROSS: 0.90,
            EthereumBridgeProtocol.HOP: 0.88,
            EthereumBridgeProtocol.CONNEXT: 0.85,
            EthereumBridgeProtocol.SYNAPSE: 0.87,
            EthereumBridgeProtocol.STARGATE: 0.93,
        }.get(protocol, 0.90)

        # Réduction pour les gros montants
        if amount > Decimal("100000"):
            base_confidence -= 0.10
        elif amount > Decimal("50000"):
            base_confidence -= 0.05

        # Ajustement selon le circuit breaker
        if protocol in self.circuit_breakers:
            cb = self.circuit_breakers[protocol]
            if cb.failure_count > 0:
                base_confidence -= min(0.2, cb.failure_count * 0.02)

        return max(0.5, min(0.99, base_confidence))

    def _can_fallback(self, result: BridgeResult) -> bool:
        """Vérifie si un fallback est possible"""
        return (
            result.retry_count < 2 and
            result.status in [BridgeStatus.FAILED, BridgeStatus.RETRYING] and
            result.protocol is not None
        )

    async def _execute_fallback(
        self,
        request: BridgeRequest,
        failed_result: BridgeResult,
    ) -> BridgeResult:
        """Exécute une stratégie de fallback"""
        logger.info(f"Exécution du fallback pour {request.request_id}")

        # Essayer avec un autre protocole
        fallback_protocol = await self._select_fallback_protocol(
            request.protocol,
            request.token_from,
            request.token_to,
            request.destination_chain,
        )

        if fallback_protocol:
            try:
                fallback_request = BridgeRequest(
                    request_id=f"{request.request_id}_fallback",
                    protocol=fallback_protocol,
                    token_from=request.token_from,
                    token_to=request.token_to,
                    amount=request.amount,
                    source_address=request.source_address,
                    destination_address=request.destination_address,
                    destination_chain=request.destination_chain,
                    slippage_tolerance=request.slippage_tolerance * Decimal("1.5"),
                    deadline=request.deadline,
                    use_fallback=False,
                    max_gas_price=request.max_gas_price,
                )

                result = await self.execute_bridge(fallback_request)
                if result.status == BridgeStatus.COMPLETED:
                    result.retry_count = failed_result.retry_count + 1
                    logger.info(f"Fallback réussi avec {fallback_protocol.value}")
                    return result

            except Exception as e:
                logger.warning(f"Échec du fallback avec {fallback_protocol.value}: {e}")

        # Si tout échoue, retourner l'échec original
        failed_result.retry_count += 1
        return failed_result

    def _get_spender_address(self, protocol: EthereumBridgeProtocol) -> str:
        """Obtient l'adresse du spender pour un protocole"""
        protocol_config = self.config.get("protocols", {}).get(protocol.value, {})
        return protocol_config.get("spender", protocol_config.get("address", "0x"))

    def _get_chain_id(self, chain_name: str) -> int:
        """Obtient l'ID de chaîne"""
        chain_ids = {
            "ethereum": 1,
            "bsc": 56,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "avalanche": 43114,
            "base": 8453,
            "linea": 59144,
            "scroll": 534352,
        }
        return chain_ids.get(chain_name, 1)

    def _get_circle_domain(self, chain_name: str) -> int:
        """Obtient le domaine Circle pour CCTP"""
        domains = {
            "ethereum": 0,
            "arbitrum": 3,
            "optimism": 2,
            "avalanche": 1,
        }
        return domains.get(chain_name, 0)

    def _get_layerzero_adapter_params(self) -> bytes:
        """Obtient les paramètres d'adaptateur LayerZero"""
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

    async def _get_bridge_type(self, protocol: EthereumBridgeProtocol) -> BridgeType:
        """Obtient le type de bridge pour un protocole"""
        bridge_types = {
            EthereumBridgeProtocol.LAYERZERO: BridgeType.LOCK_AND_MINT,
            EthereumBridgeProtocol.WORMHOLE: BridgeType.LOCK_AND_MINT,
            EthereumBridgeProtocol.CCTP: BridgeType.CCTP,
            EthereumBridgeProtocol.ACROSS: BridgeType.SWAP,
            EthereumBridgeProtocol.HOP: BridgeType.SWAP,
            EthereumBridgeProtocol.CONNEXT: BridgeType.SWAP,
            EthereumBridgeProtocol.SYNAPSE: BridgeType.SWAP,
            EthereumBridgeProtocol.STARGATE: BridgeType.SWAP,
        }
        return bridge_types.get(protocol, BridgeType.LOCK_AND_MINT)

    async def _extract_bridge_tx_id(
        self,
        tx_hash: HexBytes,
        protocol: EthereumBridgeProtocol,
    ) -> str:
        """Extrait l'ID de transaction du bridge"""
        try:
            receipt = await self.web3.eth.get_transaction_receipt(tx_hash)

            # Recherche des logs spécifiques au protocole
            # Dans une implémentation réelle, on analyserait les logs
            # pour extraire l'ID du bridge

            return f"{protocol.value}_{tx_hash.hex()}"

        except Exception:
            return f"{protocol.value}_{tx_hash.hex()}"

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        completed_bridges = [
            b for b in self._bridge_history
            if b.status == BridgeStatus.COMPLETED
        ]

        failed_bridges = [
            b for b in self._bridge_history
            if b.status == BridgeStatus.FAILED
        ]

        total_volume = sum(
            b.amount_in or Decimal("0")
            for b in self._bridge_history
            if b.amount_in
        )

        total_fees = sum(
            b.fees_total or Decimal("0")
            for b in self._bridge_history
            if b.fees_total
        )

        # Statistiques par protocole
        protocol_stats = defaultdict(lambda: {"count": 0, "volume": Decimal("0")})
        for bridge in self._bridge_history:
            if bridge.protocol:
                protocol_stats[bridge.protocol.value]["count"] += 1
                if bridge.amount_in:
                    protocol_stats[bridge.protocol.value]["volume"] += bridge.amount_in

        return {
            "total_bridges": len(self._bridge_history),
            "completed_bridges": len(completed_bridges),
            "failed_bridges": len(failed_bridges),
            "active_bridges": len(self._active_bridges),
            "success_rate": len(completed_bridges) / max(1, len(self._bridge_history)),
            "total_volume": str(total_volume),
            "total_fees": str(total_fees),
            "avg_bridge_time": self._calculate_avg_bridge_time(),
            "protocol_stats": {
                p: {
                    "count": stats["count"],
                    "volume": str(stats["volume"]),
                }
                for p, stats in protocol_stats.items()
            },
            "circuit_breakers": {
                p.value: {
                    "available": cb.is_available(),
                    "failure_count": cb.failure_count,
                    "success_count": cb.success_count,
                }
                for p, cb in self.circuit_breakers.items()
            },
        }

    def _calculate_avg_bridge_time(self) -> float:
        """Calcule le temps moyen des bridges"""
        completed_bridges = [
            b for b in self._bridge_history
            if b.status == BridgeStatus.COMPLETED and b.start_time and b.end_time
        ]

        if not completed_bridges:
            return 0.0

        total_time = sum(
            (b.end_time - b.start_time).total_seconds()
            for b in completed_bridges
        )

        return total_time / len(completed_bridges)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources EthereumBridge...")

        # Nettoyage du cache
        self._quote_cache.clear()
        self._gas_price_cache.clear()
        self._token_decimals_cache.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_ethereum_bridge(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_provider: Web3,
    bridge_manager: BridgeManager,
    **kwargs,
) -> EthereumBridge:
    """
    Crée une instance de EthereumBridge

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_provider: Provider Web3
        bridge_manager: Gestionnaire de bridges
        **kwargs: Arguments additionnels

    Returns:
        Instance de EthereumBridge
    """
    return EthereumBridge(
        config=config,
        wallet_manager=wallet_manager,
        web3_provider=web3_provider,
        bridge_manager=bridge_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du bridge Ethereum"""
    # Configuration
    config = {
        "bridge_address": "0x...",
        "protocols": {
            "layerzero": {
                "address": "0x...",
                "spender": "0x...",
            },
            "wormhole": {
                "address": "0x...",
                "spender": "0x...",
            },
            "cctp": {
                "address": "0x...",
                "spender": "0x...",
            },
        },
        "routes": {
            "layerzero": {
                "supports": ["arbitrum", "optimism", "polygon"],
                "tokens": ["USDC", "USDT", "DAI"],
            },
        },
    }

    # Création du Web3 provider
    web3_provider = Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY"))

    # Création du wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création du bridge manager
    bridge_manager = BridgeManager({})

    # Création du bridge
    bridge = create_ethereum_bridge(
        config=config,
        wallet_manager=wallet_manager,
        web3_provider=web3_provider,
        bridge_manager=bridge_manager,
    )

    # Obtention d'un devis
    quote = await bridge.get_quote(
        token_from="USDC",
        token_to="USDC",
        amount=Decimal("1000"),
        destination_chain="arbitrum",
        destination_address="0x...",
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un bridge
    if quote:
        request = BridgeRequest(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            protocol=EthereumBridgeProtocol.LAYERZERO,
            token_from="USDC",
            token_to="USDC",
            amount=Decimal("100"),
            source_address="0x...",
            destination_address="0x...",
            destination_chain="arbitrum",
        )

        result = await bridge.execute_bridge(request)
        print(f"Résultat: {result.to_dict()}")

    # Statistiques
    stats = bridge.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await bridge.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

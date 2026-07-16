# blockchain/bridges/arbitrum_bridge.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Bridge Arbitrum

Ce module implémente un système complet de bridge pour Arbitrum
avec support des bridges officiels, des protocoles tiers, et des mécanismes
de sécurité avancés.

Fonctionnalités principales:
- Support du bridge natif Arbitrum (L1 <-> L2)
- Support du bridge native-to-native (L2 <-> L2)
- Support des protocoles tiers (LayerZero, Wormhole, etc.)
- Gestion des tokens ERC-20 sur Arbitrum
- Optimisation des frais en ETH
- Support des tokens natifs (ETH, USDC, etc.)
- Gestion des mappings de tokens Arbitrum
- Support des retraits rapides (Fast Withdrawals)
- Surveillance en temps réel des bridges
- Mécanismes de fallback
- Support des cross-chain vers Ethereum et autres
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
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from .bridge_transaction import BridgeTransactionManager
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.arbitrum_wallet import ArbitrumWallet
    from ..security.encryption import EncryptionManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from .bridge_transaction import BridgeTransactionManager
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.arbitrum_wallet import ArbitrumWallet
    from ..security.encryption import EncryptionManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class ArbitrumBridgeProtocol(Enum):
    """Protocoles de bridge supportés sur Arbitrum"""
    ARBITRUM_BRIDGE = "arbitrum_bridge"  # Bridge natif Arbitrum
    ARBITRUM_NATIVE = "arbitrum_native"  # Bridge native-to-native
    RETRYABLE = "retryable"  # Retryable tickets
    LAYERZERO = "layerzero"
    WORMHOLE = "wormhole"
    AXELAR = "axelar"
    CCTP = "cctp"
    ACROSS = "across"
    HOP = "hop"
    SYNAPSE = "synapse"
    STARGATE = "stargate"
    CONNEXT = "connext"
    DEBRIDGE = "debridge"
    MULTICHAIN = "multichain"


class ArbitrumBridgeDirection(Enum):
    """Direction du bridge"""
    DEPOSIT = "deposit"  # L1 -> L2 (Arbitrum)
    WITHDRAWAL = "withdrawal"  # L2 (Arbitrum) -> L1
    CROSS_CHAIN = "cross_chain"  # L2 -> Autre L2 / L1
    RETRYABLE = "retryable"  # Retryable ticket


class ArbitrumBridgeType(Enum):
    """Types de bridge Arbitrum"""
    L1_L2 = "l1_l2"  # Bridge entre L1 et L2
    L2_L2 = "l2_l2"  # Bridge entre L2 et L2
    RETRYABLE = "retryable"  # Retryable tickets
    NATIVE = "native"  # Bridge natif


@dataclass
class ArbitrumBridgeQuote:
    """Devis de bridge Arbitrum"""
    quote_id: str
    protocol: ArbitrumBridgeProtocol
    bridge_type: ArbitrumBridgeType
    direction: ArbitrumBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    l1_gas_estimate: Decimal  # Frais L1 (pour deposit)
    l2_gas_estimate: Decimal  # Frais L2
    bridge_fees: Decimal
    total_fees: Decimal
    estimated_time: int  # secondes
    min_amount_received: Decimal
    max_slippage: Decimal
    confidence: float
    retryable_gas: Optional[int] = None
    l1_tx_hash: Optional[str] = None
    quote_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol.value,
            "bridge_type": self.bridge_type.value,
            "direction": self.direction.value,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "l1_gas_estimate": str(self.l1_gas_estimate),
            "l2_gas_estimate": str(self.l2_gas_estimate),
            "bridge_fees": str(self.bridge_fees),
            "total_fees": str(self.total_fees),
            "estimated_time": self.estimated_time,
            "min_amount_received": str(self.min_amount_received),
            "max_slippage": str(self.max_slippage),
            "confidence": self.confidence,
            "retryable_gas": self.retryable_gas,
            "l1_tx_hash": self.l1_tx_hash,
        }


@dataclass
class ArbitrumBridgeRequest:
    """Requête de bridge Arbitrum"""
    request_id: str
    protocol: ArbitrumBridgeProtocol
    bridge_type: ArbitrumBridgeType
    direction: ArbitrumBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    destination_chain: str = "ethereum"
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    use_fallback: bool = True
    max_gas_price: Optional[Decimal] = None
    max_l1_gas_price: Optional[Decimal] = None
    retryable_gas_limit: Optional[int] = None
    priority_fee: Optional[int] = None
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "protocol": self.protocol.value,
            "bridge_type": self.bridge_type.value,
            "direction": self.direction.value,
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
            "max_l1_gas_price": str(self.max_l1_gas_price) if self.max_l1_gas_price else None,
            "retryable_gas_limit": self.retryable_gas_limit,
            "priority_fee": self.priority_fee,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class ArbitrumBridge(BaseBridge):
    """
    Bridge avancé pour Arbitrum avec support multi-protocoles
    """

    # Adresses des contrats Arbitrum (Mainnet)
    CONTRACTS = {
        "l1": {
            "bridge": "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",
            "inbox": "0x4Dbd4fc535Ac27206064B68FfCf827b0A60BAB3f",
            "outbox": "0x0B9857ae2D4b3d41Fe6Ff3D826B5b99D66Be6B60",
            "rollup": "0x5eF0D09d1E6204141B4d37530808eD19f60FBa35",
        },
        "l2": {
            "bridge": "0x096760F208390250649E3e8763348E783AEF5562",
            "inbox": "0x6c9A3Aa5fc0BfA03b726187d99fc16547Dc25a87",
            "outbox": "0x6c9A3Aa5fc0BfA03b726187d99fc16547Dc25a87",
        },
        "layerzero": {
            "endpoint": "0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675",
            "bridge": "0x4B29C7Ab7F95A3355bD6F1FcBf388cD6534fC819",
        },
        "wormhole": {
            "core_bridge": "0x98f3c9e6E3fAce36bAAd05FE09d375Ef1464288B",
            "token_bridge": "0xB6F6D86a8f9879A9c87f643768d9efc38c1Da6E7",
        },
        "cctp": {
            "token_messenger": "0x354222B555b952382a5762d4c342E7FBeA0B5b3C",
        },
        "multichain": {
            "router": "0xFEa7a6a0B346362BF88A9e4A88416B77a57D6c2A",
        },
        "stargate": {
            "router": "0x53Bf833A5d6c4ddA888F69c22C88C9f356a41614",
        },
    }

    # Token mappings Arbitrum
    TOKEN_MAPPINGS = {
        "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # ETH natif
        "USDC": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
        "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "WBTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
        "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "LINK": "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4",
        "UNI": "0xFa7F8980b0f1E64A2062791cc3b0871572f1F7f0",
        "AAVE": "0xba5DdD1f9d7F570dc94a51479a000E3BCE967196",
    }

    # Token mappings cross-chain
    CROSS_CHAIN_MAPPINGS = {
        "ethereum": {
            "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
            "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        },
        "polygon": {
            "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        },
        "optimism": {
            "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
            "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
            "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
        },
        "bsc": {
            "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "USDT": "0x55d398326f99059fF775485246999027B3197955",
        },
        "avalanche": {
            "USDC": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
            "USDT": "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7",
        },
    }

    # ABIs des contrats
    ARBITRUM_BRIDGE_L1_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "data", "type": "bytes"},
            ],
            "name": "depositETH",
            "outputs": [],
            "payable": True,
            "stateMutability": "payable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "l1Token", "type": "address"},
                {"name": "l2Token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "minGas", "type": "uint32"},
                {"name": "data", "type": "bytes"},
            ],
            "name": "depositERC20",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "l1Token", "type": "address"},
                {"name": "l2Token", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "withdraw",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "", "type": "bytes32"}],
            "name": "withdrawals",
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

    ARBITRUM_BRIDGE_L2_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "l1Token", "type": "address"},
                {"name": "l2Token", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "withdraw",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "withdrawETH",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    RETRYABLE_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "callValue", "type": "uint256"},
                {"name": "data", "type": "bytes"},
                {"name": "gasLimit", "type": "uint256"},
                {"name": "maxFee", "type": "uint256"},
            ],
            "name": "createRetryableTicket",
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
        web3_providers: Dict[str, Web3],
        bridge_manager: BridgeManager,
        transaction_manager: BridgeTransactionManager,
        validator: Optional[BridgeValidator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le bridge Arbitrum

        Args:
            config: Configuration du bridge
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 (L1 et L2)
            bridge_manager: Gestionnaire de bridges
            transaction_manager: Gestionnaire de transactions
            validator: Validateur de bridge
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager)

        self.web3_providers = web3_providers
        self.bridge_manager = bridge_manager
        self.transaction_manager = transaction_manager
        self.validator = validator
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # Providers L1/L2
        self.l1_web3 = web3_providers.get("ethereum")
        self.l2_web3 = web3_providers.get("arbitrum")

        if not self.l1_web3 or not self.l2_web3:
            raise ValueError("Providers L1 et L2 requis")

        # Ajout du middleware PoA pour Arbitrum
        try:
            self.l2_web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception:
            pass

        # États internes
        self._active_bridges: Dict[str, Dict[str, Any]] = {}
        self._bridge_history: List[Dict[str, Any]] = []
        self._quote_cache: Dict[str, Tuple[float, ArbitrumBridgeQuote]] = {}
        self._contracts: Dict[str, Dict[str, Contract]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[ArbitrumBridgeProtocol, CircuitBreaker] = {
            protocol: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
            for protocol in ArbitrumBridgeProtocol
        }

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache
        self._gas_cache: Dict[str, Dict[str, Any]] = {}
        self._token_mapping_cache: Dict[str, Dict[str, str]] = {}
        self._retryable_cache: Dict[str, Dict[str, Any]] = {}

        # Charge les contrats
        self._load_contracts()

        # Charge les mappings de tokens
        self._load_token_mappings()

        # Initialise les retryable tickets
        self._retryable_queue: Dict[str, Dict[str, Any]] = {}

        logger.info("ArbitrumBridge initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats smart"""
        try:
            # Contrats L1
            l1_contracts = {}
            for name, address in self.CONTRACTS["l1"].items():
                if name == "bridge" or name == "inbox" or name == "outbox":
                    abi = self.ARBITRUM_BRIDGE_L1_ABI
                    l1_contracts[name] = self.l1_web3.eth.contract(
                        address=to_checksum_address(address),
                        abi=abi,
                    )
            self._contracts["l1"] = l1_contracts

            # Contrats L2
            l2_contracts = {}
            for name, address in self.CONTRACTS["l2"].items():
                if name == "bridge" or name == "outbox":
                    abi = self.ARBITRUM_BRIDGE_L2_ABI
                    l2_contracts[name] = self.l2_web3.eth.contract(
                        address=to_checksum_address(address),
                        abi=abi,
                    )
            self._contracts["l2"] = l2_contracts

            # Contrats protocol
            protocol_contracts = {}
            for name, contract_info in self.CONTRACTS.items():
                if name not in ["l1", "l2"]:
                    if name == "retryable":
                        abi = self.RETRYABLE_ABI
                    else:
                        abi = self._get_generic_abi()

                    address = contract_info.get("bridge") or contract_info.get("router") or contract_info.get("endpoint")
                    if address:
                        protocol_contracts[name] = self.l2_web3.eth.contract(
                            address=to_checksum_address(address),
                            abi=abi,
                        )
            self._contracts["protocol"] = protocol_contracts

            logger.info(f"Contrats L1 chargés: {list(l1_contracts.keys())}")
            logger.info(f"Contrats L2 chargés: {list(l2_contracts.keys())}")
            logger.info(f"Contrats protocole chargés: {list(protocol_contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise BridgeError(f"Erreur de chargement des contrats: {e}")

    def _get_generic_abi(self) -> List[Dict[str, Any]]:
        """Obtient une ABI générique"""
        return [
            {
                "constant": False,
                "inputs": [
                    {"name": "token", "type": "address"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "to", "type": "address"},
                    {"name": "data", "type": "bytes"},
                ],
                "name": "bridge",
                "outputs": [],
                "payable": False,
                "stateMutability": "nonpayable",
                "type": "function",
            },
        ]

    def _load_token_mappings(self) -> None:
        """Charge les mappings des tokens Arbitrum"""
        # Mappings Arbitrum
        self._token_mapping_cache["arbitrum"] = self.TOKEN_MAPPINGS

        # Mappings cross-chain
        self._token_mapping_cache["cross_chain"] = self.CROSS_CHAIN_MAPPINGS

        # Ajout des mappings depuis la configuration
        if self.config.get("token_mappings"):
            user_mappings = self.config.get("token_mappings", {})
            for chain, tokens in user_mappings.items():
                if chain not in self._token_mapping_cache["cross_chain"]:
                    self._token_mapping_cache["cross_chain"][chain] = {}
                self._token_mapping_cache["cross_chain"][chain].update(tokens)

        logger.info(f"Token mappings chargés: {len(self._token_mapping_cache)}")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_quote(
        self,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: ArbitrumBridgeDirection,
        destination_chain: str = "ethereum",
        destination_address: str = "",
        protocol: Optional[ArbitrumBridgeProtocol] = None,
        bridge_type: Optional[ArbitrumBridgeType] = None,
        **kwargs,
    ) -> ArbitrumBridgeQuote:
        """
        Obtient un devis pour un bridge Arbitrum

        Args:
            token_from: Token source
            token_to: Token destination
            amount: Montant à bridge
            direction: Direction du bridge
            destination_chain: Chaîne destination
            destination_address: Adresse destination
            protocol: Protocole spécifique
            bridge_type: Type de bridge
            **kwargs: Arguments additionnels

        Returns:
            Devis de bridge
        """
        logger.info(
            f"Demande de devis Arbitrum: {amount} {token_from} -> {token_to} "
            f"({direction.value})"
        )

        # Vérification du cache
        cache_key = f"{token_from}:{token_to}:{amount}:{direction.value}:{destination_chain}:{protocol}:{bridge_type}"
        if cache_key in self._quote_cache:
            cached_time, quote = self._quote_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Devis retourné du cache")
                return quote

        try:
            # Sélection du protocole
            if protocol is None:
                protocol = await self._select_best_protocol(
                    token_from, token_to, direction, destination_chain
                )

            # Sélection du type de bridge
            if bridge_type is None:
                bridge_type = await self._select_bridge_type(protocol, direction)

            # Vérification du circuit breaker
            if not self.circuit_breakers[protocol].is_available():
                logger.warning(f"Circuit breaker ouvert pour {protocol.value}")
                fallback_protocol = await self._select_fallback_protocol(
                    protocol, token_from, token_to, direction, destination_chain
                )
                if fallback_protocol:
                    protocol = fallback_protocol
                else:
                    raise BridgeError(f"Protocole {protocol.value} indisponible")

            # Génération du devis
            quote = await self._generate_quote(
                protocol=protocol,
                bridge_type=bridge_type,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                direction=direction,
                destination_chain=destination_chain,
                destination_address=destination_address,
                **kwargs,
            )

            # Mise en cache
            self._quote_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "arbitrum_bridge_quote",
                1,
                {
                    "protocol": protocol.value,
                    "bridge_type": bridge_type.value,
                    "direction": direction.value,
                    "token_from": token_from,
                    "token_to": token_to,
                },
            )

            return quote

        except Exception as e:
            logger.error(f"Erreur lors de la génération du devis: {e}")
            raise BridgeError(f"Erreur de génération de devis: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_bridge(
        self,
        request: ArbitrumBridgeRequest,
    ) -> Dict[str, Any]:
        """
        Exécute un bridge Arbitrum

        Args:
            request: Requête de bridge

        Returns:
            Résultat du bridge
        """
        bridge_id = f"arb_bridge_{uuid.uuid4().hex[:12]}"
        logger.info(f"Exécution du bridge Arbitrum {bridge_id}")

        try:
            # 1. Obtention du devis
            quote = await self.get_quote(
                token_from=request.token_from,
                token_to=request.token_to,
                amount=request.amount,
                direction=request.direction,
                destination_chain=request.destination_chain,
                destination_address=request.destination_address,
                protocol=request.protocol,
                bridge_type=request.bridge_type,
                slippage_tolerance=request.slippage_tolerance,
            )

            # 2. Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(request.source_address)
            if not wallet:
                raise BridgeError("Wallet non trouvé")

            # 3. Vérification du solde
            balance = await self._get_balance(
                request.token_from,
                request.source_address,
                request.direction,
            )
            if balance < request.amount:
                raise BridgeError(
                    f"Solde insuffisant: {balance} < {request.amount}"
                )

            # 4. Approval du token si nécessaire
            if request.token_from != "ETH":
                await self._approve_token(
                    token=request.token_from,
                    amount=request.amount,
                    wallet=wallet,
                    protocol=request.protocol,
                    direction=request.direction,
                )

            # 5. Exécution selon la direction
            if request.direction == ArbitrumBridgeDirection.DEPOSIT:
                result = await self._execute_deposit(request, quote, wallet)
            elif request.direction == ArbitrumBridgeDirection.WITHDRAWAL:
                result = await self._execute_withdrawal(request, quote, wallet)
            elif request.direction == ArbitrumBridgeDirection.RETRYABLE:
                result = await self._execute_retryable(request, quote, wallet)
            else:
                result = await self._execute_cross_chain(request, quote, wallet)

            # 6. Attente de la confirmation
            final_result = await self._wait_for_confirmation(
                bridge_id=bridge_id,
                tx_hash=result.get("tx_hash"),
                direction=request.direction,
            )

            # Mise à jour du statut
            result["status"] = "completed"
            result["bridge_id"] = bridge_id
            result["amount_received"] = final_result.get("amount_received", quote.min_amount_received)
            result["fees_paid"] = quote.total_fees
            result["completed_at"] = datetime.now().isoformat()

            # Gestion des retryable tickets
            if request.direction == ArbitrumBridgeDirection.RETRYABLE:
                result["retryable_ticket_id"] = final_result.get("ticket_id")

            # Stockage
            self._active_bridges.pop(bridge_id, None)
            self._bridge_history.append(result)

            # Métriques
            self.metrics.record_increment(
                "arbitrum_bridge_completed",
                {
                    "protocol": request.protocol.value,
                    "bridge_type": request.bridge_type.value,
                    "direction": request.direction.value,
                    "token": request.token_from,
                },
            )

            logger.info(f"Bridge Arbitrum {bridge_id} terminé avec succès")
            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution du bridge: {e}")
            error_result = {
                "bridge_id": bridge_id,
                "status": "failed",
                "error": str(e),
                "request": request.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }

            self._bridge_history.append(error_result)

            self.metrics.record_increment(
                "arbitrum_bridge_failed",
                {
                    "protocol": request.protocol.value,
                    "bridge_type": request.bridge_type.value,
                    "direction": request.direction.value,
                    "error": str(e)[:50],
                },
            )

            raise BridgeError(f"Erreur d'exécution du bridge: {e}")

    # ============================================================
    # MÉTHODES D'EXÉCUTION
    # ============================================================

    async def _execute_deposit(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un dépôt L1 -> L2"""
        logger.info(f"Exécution du dépôt Arbitrum: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de dépôt
            tx_data = await self._build_deposit_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="ethereum",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="arbitrum_deposit",
            )

            return {
                "tx_hash": tx_result.get("tx_hash"),
                "direction": "deposit",
                "amount": str(request.amount),
                "token": request.token_from,
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution du dépôt: {e}")
            raise

    async def _execute_withdrawal(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un retrait L2 -> L1"""
        logger.info(f"Exécution du retrait Arbitrum: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de retrait
            tx_data = await self._build_withdrawal_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="arbitrum",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="arbitrum_withdrawal",
            )

            return {
                "tx_hash": tx_result.get("tx_hash"),
                "direction": "withdrawal",
                "amount": str(request.amount),
                "token": request.token_from,
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution du retrait: {e}")
            raise

    async def _execute_retryable(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un retryable ticket Arbitrum"""
        logger.info(f"Exécution du retryable ticket Arbitrum: {request.amount}")

        try:
            # Construction du retryable ticket
            tx_data = await self._build_retryable_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="arbitrum",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="arbitrum_retryable",
            )

            # Enregistrement du retryable
            retryable_id = tx_result.get("tx_hash")
            self._retryable_queue[retryable_id] = {
                "request": request,
                "quote": quote,
                "tx_hash": retryable_id,
                "status": "pending",
            }

            return {
                "tx_hash": tx_result.get("tx_hash"),
                "direction": "retryable",
                "amount": str(request.amount),
                "token": request.token_from,
                "retryable_ticket_id": retryable_id,
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution du retryable: {e}")
            raise

    async def _execute_cross_chain(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un bridge cross-chain depuis Arbitrum"""
        logger.info(f"Exécution du bridge cross-chain Arbitrum: {request.amount}")

        protocol = request.protocol

        if protocol == ArbitrumBridgeProtocol.ARBITRUM_BRIDGE:
            return await self._execute_arbitrum_bridge(request, quote, wallet)
        elif protocol == ArbitrumBridgeProtocol.ARBITRUM_NATIVE:
            return await self._execute_native_bridge(request, quote, wallet)
        elif protocol == ArbitrumBridgeProtocol.LAYERZERO:
            return await self._execute_layerzero(request, quote, wallet)
        elif protocol == ArbitrumBridgeProtocol.WORMHOLE:
            return await self._execute_wormhole(request, quote, wallet)
        elif protocol == ArbitrumBridgeProtocol.MULTICHAIN:
            return await self._execute_multichain(request, quote, wallet)
        elif protocol == ArbitrumBridgeProtocol.STARGATE:
            return await self._execute_stargate(request, quote, wallet)
        else:
            return await self._execute_generic_bridge(request, quote, wallet)

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_deposit_transaction(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de dépôt Arbitrum"""
        # Récupération du contrat L1
        l1_contract = self._contracts["l1"].get("bridge")
        if not l1_contract:
            raise BridgeError("Contrat L1 non trouvé")

        # Récupération des addresses des tokens
        token_mapping = self._token_mapping_cache["arbitrum"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        # Récupération du token L2 correspondant
        l2_token = await self._get_l2_token_address(token_address, request.token_to)

        # Valeur en wei
        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        # Paramètres du retryable
        gas_limit = request.retryable_gas_limit or 200000
        max_fee = amount_wei  # Simplifié

        if request.token_from == "ETH":
            # Dépôt d'ETH natif
            tx_data = l1_contract.functions.depositETH(
                to_checksum_address(request.destination_address),
                amount_wei,
                b"",  # Données additionnelles
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "value": amount_wei,
                "gas": 300000,
                "gasPrice": await self._get_l1_gas_price(),
            })
        else:
            # Dépôt d'ERC20
            tx_data = l1_contract.functions.depositERC20(
                to_checksum_address(token_address),
                to_checksum_address(l2_token),
                amount_wei,
                gas_limit,
                b"",
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 400000,
                "gasPrice": await self._get_l1_gas_price(),
            })

        return dict(tx_data)

    async def _build_withdrawal_transaction(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de retrait Arbitrum"""
        # Récupération du contrat L2
        l2_contract = self._contracts["l2"].get("bridge")
        if not l2_contract:
            raise BridgeError("Contrat L2 non trouvé")

        # Récupération des addresses des tokens
        token_mapping = self._token_mapping_cache["arbitrum"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        # Récupération du token L1 correspondant
        l1_token = await self._get_l1_token_address(token_address, request.token_to)

        # Valeur en wei
        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        if request.token_from == "ETH":
            # Retrait d'ETH natif
            tx_data = l2_contract.functions.withdrawETH(
                to_checksum_address(request.destination_address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 200000,
                "gasPrice": await self._get_l2_gas_price(),
            })
        else:
            # Retrait d'ERC20
            tx_data = l2_contract.functions.withdraw(
                to_checksum_address(l1_token),
                to_checksum_address(token_address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 300000,
                "gasPrice": await self._get_l2_gas_price(),
            })

        return dict(tx_data)

    async def _build_retryable_transaction(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit un retryable ticket Arbitrum"""
        # Récupération du contrat retryable
        retryable_contract = self._contracts["protocol"].get("retryable")
        if not retryable_contract:
            raise BridgeError("Contrat retryable non trouvé")

        # Valeur en wei
        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        # Data pour le retryable
        data = self._encode_retryable_data(
            request.token_from,
            request.token_to,
            amount_wei,
            request.destination_address,
        )

        # Construction du retryable
        tx_data = retryable_contract.functions.createRetryableTicket(
            to_checksum_address(request.destination_address),
            amount_wei,
            data,
            request.retryable_gas_limit or 200000,
            amount_wei,  # maxFee
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "value": amount_wei,
            "gas": 400000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        return dict(tx_data)

    # ============================================================
    # MÉTHODES DE PROTOCOLES SPÉCIFIQUES
    # ============================================================

    async def _execute_arbitrum_bridge(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute le bridge natif Arbitrum"""
        logger.info("Exécution du bridge natif Arbitrum")

        # Utiliser la direction appropriée
        if request.direction == ArbitrumBridgeDirection.DEPOSIT:
            return await self._execute_deposit(request, quote, wallet)
        elif request.direction == ArbitrumBridgeDirection.WITHDRAWAL:
            return await self._execute_withdrawal(request, quote, wallet)
        else:
            # Cross-chain via le bridge natif
            return await self._execute_deposit(request, quote, wallet)

    async def _execute_native_bridge(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute le bridge native-to-native"""
        logger.info("Exécution du bridge native-to-native")

        # Utilisation du bridge natif L2
        return await self._execute_withdrawal(request, quote, wallet)

    async def _execute_layerzero(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute LayerZero sur Arbitrum"""
        logger.info("Exécution de LayerZero bridge sur Arbitrum")

        contract = self._contracts["protocol"].get("layerzero")
        if not contract:
            raise BridgeError("Contrat LayerZero non trouvé")

        # Paramètres d'adaptateur
        adapter_params = self._get_layerzero_adapter_params()

        # Construction de la transaction
        chain_id = self._get_chain_id(request.destination_chain)

        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        tx_data = contract.functions.bridge(
            to_checksum_address(request.token_from),
            amount_wei,
            to_checksum_address(request.destination_address),
            chain_id,
            adapter_params,
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="arbitrum",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="layerzero",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "layerzero",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_wormhole(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Wormhole sur Arbitrum"""
        logger.info("Exécution de Wormhole bridge sur Arbitrum")

        contract = self._contracts["protocol"].get("wormhole")
        if not contract:
            raise BridgeError("Contrat Wormhole non trouvé")

        # Récupération de l'émulateur
        chain_id = self._get_chain_id(request.destination_chain)
        emitter = self._get_wormhole_emitter(chain_id)

        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        tx_data = contract.functions.bridge(
            to_checksum_address(request.token_from),
            amount_wei,
            to_checksum_address(request.destination_address),
            chain_id,
            to_checksum_address(emitter),
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 250000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="arbitrum",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="wormhole",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "wormhole",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_multichain(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Multichain sur Arbitrum"""
        logger.info("Exécution de Multichain bridge sur Arbitrum")

        contract = self._contracts["protocol"].get("multichain")
        if not contract:
            raise BridgeError("Contrat Multichain non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["arbitrum"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        chain_id = self._get_chain_id(request.destination_chain)

        tx_data = contract.functions.bridge(
            to_checksum_address(token_address),
            amount_wei,
            to_checksum_address(request.destination_address),
            chain_id,
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="arbitrum",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="multichain",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "multichain",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_stargate(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Stargate sur Arbitrum"""
        logger.info("Exécution de Stargate bridge sur Arbitrum")

        contract = self._contracts["protocol"].get("stargate")
        if not contract:
            raise BridgeError("Contrat Stargate non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["arbitrum"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        chain_id = self._get_chain_id(request.destination_chain)

        # Construction de la transaction Stargate
        tx_data = contract.functions.bridge(
            to_checksum_address(token_address),
            amount_wei,
            to_checksum_address(request.destination_address),
            chain_id,
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="arbitrum",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="stargate",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "stargate",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_generic_bridge(
        self,
        request: ArbitrumBridgeRequest,
        quote: ArbitrumBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un protocole générique"""
        logger.info("Exécution du bridge générique sur Arbitrum")

        contract_name = request.protocol.value
        contract = self._contracts["protocol"].get(contract_name)
        if not contract:
            raise BridgeError(f"Contrat {contract_name} non trouvé")

        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        tx_data = contract.functions.bridge(
            to_checksum_address(request.token_from),
            amount_wei,
            to_checksum_address(request.destination_address),
            b"",
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="arbitrum",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="generic_bridge",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": request.protocol.value,
            "amount": str(request.amount),
            "token": request.token_from,
        }

    # ============================================================
    # MÉTHODES D'APPROBATION
    # ============================================================

    async def _approve_token(
        self,
        token: str,
        amount: Decimal,
        wallet: BaseWallet,
        protocol: ArbitrumBridgeProtocol,
        direction: ArbitrumBridgeDirection,
    ) -> bool:
        """Approuve un token pour le bridge"""
        try:
            # Récupération du spender
            spender = self._get_spender_address(protocol, direction)

            # Vérification de l'allowance
            allowance = await self._get_allowance(token, wallet.address, spender, direction)

            if allowance >= amount:
                logger.debug(f"Allowance suffisante: {allowance} >= {amount}")
                return True

            # Construction de la transaction d'approbation
            provider = self.l1_web3 if direction == ArbitrumBridgeDirection.DEPOSIT else self.l2_web3

            token_mapping = self._token_mapping_cache["arbitrum"]
            token_address = token_mapping.get(token, token)

            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            decimals = self._get_token_decimals(token)
            amount_wei = int(amount * Decimal(10 ** decimals))

            approve_tx = token_contract.functions.approve(
                to_checksum_address(spender),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet.address),
                "nonce": await provider.eth.get_transaction_count(wallet.address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price(direction),
            })

            # Envoi de la transaction
            signed_tx = wallet.sign_transaction(approve_tx)
            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            # Attente de la confirmation
            receipt = await self._wait_for_transaction(provider, tx_hash)
            if receipt.get("status") != 1:
                raise BridgeError("Échec de l'approbation")

            logger.info(f"Approbation réussie: {tx_hash.hex()}")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approbation: {e}")
            raise BridgeError(f"Erreur d'approbation: {e}")

    async def _get_allowance(
        self,
        token: str,
        owner: str,
        spender: str,
        direction: ArbitrumBridgeDirection,
    ) -> Decimal:
        """Obtient l'allowance d'un token"""
        try:
            provider = self.l1_web3 if direction == ArbitrumBridgeDirection.DEPOSIT else self.l2_web3

            token_mapping = self._token_mapping_cache["arbitrum"]
            token_address = token_mapping.get(token, token)

            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            decimals = self._get_token_decimals(token)
            allowance = await token_contract.functions.allowance(
                to_checksum_address(owner),
                to_checksum_address(spender),
            ).call()

            return Decimal(str(allowance)) / Decimal(10 ** decimals)

        except Exception as e:
            logger.warning(f"Erreur d'allowance: {e}")
            return Decimal("0")

    # ============================================================
    # MÉTHODES DE VÉRIFICATION ET CONFIRMATION
    # ============================================================

    async def _wait_for_confirmation(
        self,
        bridge_id: str,
        tx_hash: Optional[str],
        direction: ArbitrumBridgeDirection,
        timeout: int = 3600,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction Arbitrum"""
        if not tx_hash:
            raise BridgeError("Hash de transaction manquant")

        logger.info(f"Attente de confirmation pour {bridge_id}: {tx_hash}")

        start_time = time.time()
        provider = self.l1_web3 if direction == ArbitrumBridgeDirection.DEPOSIT else self.l2_web3

        while time.time() - start_time < timeout:
            try:
                receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))
                if receipt:
                    status = receipt.get("status")
                    if status == 1:
                        # Vérification du statut L2 pour les dépôts
                        if direction == ArbitrumBridgeDirection.DEPOSIT:
                            l2_receipt = await self._wait_for_l2_transaction(
                                tx_hash, timeout - (time.time() - start_time)
                            )
                            if l2_receipt:
                                return {
                                    "amount_received": str(l2_receipt.get("amount", 0)),
                                    "confirmations": 12,
                                }
                        elif direction == ArbitrumBridgeDirection.RETRYABLE:
                            # Vérification du retryable ticket
                            ticket = await self._get_retryable_ticket_status(tx_hash)
                            if ticket and ticket.get("status") == "completed":
                                return {
                                    "amount_received": str(ticket.get("amount", 0)),
                                    "ticket_id": ticket.get("ticket_id"),
                                    "confirmations": 12,
                                }
                        else:
                            # Retrait L2 -> L1
                            l1_receipt = await self._wait_for_l1_withdrawal(
                                tx_hash, timeout - (time.time() - start_time)
                            )
                            if l1_receipt:
                                return {
                                    "amount_received": str(l1_receipt.get("amount", 0)),
                                    "confirmations": 12,
                                }

            except Exception as e:
                logger.warning(f"Erreur de vérification: {e}")

            await asyncio.sleep(10)

        raise BridgeError(f"Timeout de confirmation: {tx_hash}")

    async def _wait_for_l2_transaction(
        self,
        l1_tx_hash: str,
        timeout: int,
    ) -> Optional[Dict[str, Any]]:
        """Attend la transaction L2 pour un dépôt"""
        logger.info(f"Attente de la transaction L2 pour {l1_tx_hash}")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Récupération du dépôt
                deposit = await self._get_deposit_info(l1_tx_hash)
                if deposit and deposit.get("status") == "completed":
                    return {
                        "amount": deposit.get("amount", 0),
                        "l2_tx_hash": deposit.get("l2_tx_hash"),
                    }
            except Exception as e:
                logger.warning(f"Erreur de vérification L2: {e}")

            await asyncio.sleep(15)

        return None

    async def _wait_for_l1_withdrawal(
        self,
        l2_tx_hash: str,
        timeout: int,
    ) -> Optional[Dict[str, Any]]:
        """Attend la transaction L1 pour un retrait"""
        logger.info(f"Attente de la transaction L1 pour {l2_tx_hash}")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Récupération du retrait
                withdrawal = await self._get_withdrawal_info(l2_tx_hash)
                if withdrawal and withdrawal.get("status") == "completed":
                    return {
                        "amount": withdrawal.get("amount", 0),
                        "l1_tx_hash": withdrawal.get("l1_tx_hash"),
                    }
            except Exception as e:
                logger.warning(f"Erreur de vérification L1: {e}")

            await asyncio.sleep(30)  # Les retraits sont plus lents

        return None

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _generate_quote(
        self,
        protocol: ArbitrumBridgeProtocol,
        bridge_type: ArbitrumBridgeType,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: ArbitrumBridgeDirection,
        destination_chain: str,
        destination_address: str,
        **kwargs,
    ) -> ArbitrumBridgeQuote:
        """Génère un devis pour un protocole spécifique"""
        try:
            # Estimation des frais
            l1_gas = await self._estimate_l1_gas(protocol, amount, direction)
            l2_gas = await self._estimate_l2_gas(protocol, amount, direction)
            bridge_fees = await self._estimate_bridge_fees(
                protocol, token_from, amount, direction
            )
            total_fees = l1_gas + l2_gas + bridge_fees

            # Estimation du temps
            estimated_time = await self._estimate_time(protocol, bridge_type, direction)

            # Retryable gas
            retryable_gas = None
            if direction == ArbitrumBridgeDirection.RETRYABLE:
                retryable_gas = kwargs.get("retryable_gas_limit", 200000)

            # Niveau de confiance
            confidence = self._calculate_confidence(protocol, amount)

            # Slippage
            slippage = kwargs.get("slippage_tolerance", Decimal("0.005"))

            # Montant minimum reçu
            min_amount_received = amount * (1 - float(slippage))

            return ArbitrumBridgeQuote(
                quote_id=f"arb_q_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                bridge_type=bridge_type,
                direction=direction,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                l1_gas_estimate=l1_gas,
                l2_gas_estimate=l2_gas,
                bridge_fees=bridge_fees,
                total_fees=total_fees,
                estimated_time=estimated_time,
                min_amount_received=min_amount_received,
                max_slippage=slippage,
                confidence=confidence,
                retryable_gas=retryable_gas,
                quote_data=kwargs,
            )

        except Exception as e:
            logger.error(f"Erreur de génération de devis pour {protocol.value}: {e}")
            raise

    async def _estimate_l1_gas(
        self,
        protocol: ArbitrumBridgeProtocol,
        amount: Decimal,
        direction: ArbitrumBridgeDirection,
    ) -> Decimal:
        """Estime les frais L1"""
        try:
            # Base gas L1
            base_gas = 100000 if direction == ArbitrumBridgeDirection.DEPOSIT else 0

            if direction == ArbitrumBridgeDirection.DEPOSIT:
                # Obtention du prix du gaz L1
                gas_price = await self._get_l1_gas_price()
                gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

                l1_fees = Decimal(str(base_gas)) * gas_price_decimal
                return l1_fees

            return Decimal("0")

        except Exception as e:
            logger.warning(f"Erreur d'estimation L1: {e}")
            return Decimal("0.001")

    async def _estimate_l2_gas(
        self,
        protocol: ArbitrumBridgeProtocol,
        amount: Decimal,
        direction: ArbitrumBridgeDirection,
    ) -> Decimal:
        """Estime les frais L2"""
        try:
            # Base gas L2
            base_gas = {
                ArbitrumBridgeProtocol.ARBITRUM_BRIDGE: 150000,
                ArbitrumBridgeProtocol.ARBITRUM_NATIVE: 100000,
                ArbitrumBridgeProtocol.RETRYABLE: 200000,
                ArbitrumBridgeProtocol.LAYERZERO: 300000,
                ArbitrumBridgeProtocol.WORMHOLE: 250000,
                ArbitrumBridgeProtocol.MULTICHAIN: 300000,
                ArbitrumBridgeProtocol.STARGATE: 200000,
            }.get(protocol, 200000)

            # Ajustement selon le montant
            if amount > Decimal("100000"):
                base_gas = int(base_gas * 1.5)
            elif amount > Decimal("50000"):
                base_gas = int(base_gas * 1.2)

            # Obtention du prix du gaz L2
            gas_price = await self._get_l2_gas_price()
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            total_cost = Decimal(str(base_gas)) * gas_price_decimal
            return total_cost

        except Exception as e:
            logger.warning(f"Erreur d'estimation L2: {e}")
            return Decimal("0.001")

    async def _estimate_bridge_fees(
        self,
        protocol: ArbitrumBridgeProtocol,
        token: str,
        amount: Decimal,
        direction: ArbitrumBridgeDirection,
    ) -> Decimal:
        """Estime les frais de bridge"""
        # Frais par protocole
        base_fees = {
            ArbitrumBridgeProtocol.ARBITRUM_BRIDGE: Decimal("0.0001"),
            ArbitrumBridgeProtocol.ARBITRUM_NATIVE: Decimal("0.00005"),
            ArbitrumBridgeProtocol.RETRYABLE: Decimal("0.00015"),
            ArbitrumBridgeProtocol.LAYERZERO: Decimal("0.0005"),
            ArbitrumBridgeProtocol.WORMHOLE: Decimal("0.0003"),
            ArbitrumBridgeProtocol.MULTICHAIN: Decimal("0.0004"),
            ArbitrumBridgeProtocol.STARGATE: Decimal("0.0004"),
            ArbitrumBridgeProtocol.CCTP: Decimal("0.0001"),
        }.get(protocol, Decimal("0.0003"))

        # Frais variables
        variable_fees = amount * Decimal("0.0002")

        # Ajustement direction
        direction_multiplier = 1.0 if direction == ArbitrumBridgeDirection.DEPOSIT else 1.3

        return (base_fees + variable_fees) * Decimal(str(direction_multiplier))

    async def _estimate_time(
        self,
        protocol: ArbitrumBridgeProtocol,
        bridge_type: ArbitrumBridgeType,
        direction: ArbitrumBridgeDirection,
    ) -> int:
        """Estime le temps de bridge en secondes"""
        base_time = {
            ArbitrumBridgeProtocol.ARBITRUM_BRIDGE: 120,
            ArbitrumBridgeProtocol.ARBITRUM_NATIVE: 60,
            ArbitrumBridgeProtocol.RETRYABLE: 300,
            ArbitrumBridgeProtocol.LAYERZERO: 100,
            ArbitrumBridgeProtocol.WORMHOLE: 80,
            ArbitrumBridgeProtocol.MULTICHAIN: 150,
            ArbitrumBridgeProtocol.STARGATE: 70,
            ArbitrumBridgeProtocol.CCTP: 60,
        }.get(protocol, 120)

        # Les retraits sont plus lents
        if direction == ArbitrumBridgeDirection.WITHDRAWAL:
            base_time = int(base_time * 2)

        # Les retryables sont plus lents
        if bridge_type == ArbitrumBridgeType.RETRYABLE:
            base_time = int(base_time * 3)

        return base_time

    def _calculate_confidence(
        self,
        protocol: ArbitrumBridgeProtocol,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            ArbitrumBridgeProtocol.ARBITRUM_BRIDGE: 0.99,
            ArbitrumBridgeProtocol.ARBITRUM_NATIVE: 0.99,
            ArbitrumBridgeProtocol.RETRYABLE: 0.95,
            ArbitrumBridgeProtocol.LAYERZERO: 0.95,
            ArbitrumBridgeProtocol.WORMHOLE: 0.97,
            ArbitrumBridgeProtocol.MULTICHAIN: 0.92,
            ArbitrumBridgeProtocol.STARGATE: 0.93,
            ArbitrumBridgeProtocol.CCTP: 0.98,
        }.get(protocol, 0.95)

        if amount > Decimal("50000"):
            base_confidence -= 0.10
        elif amount > Decimal("10000"):
            base_confidence -= 0.05

        if protocol in self.circuit_breakers:
            cb = self.circuit_breakers[protocol]
            if cb.failure_count > 0:
                base_confidence -= min(0.2, cb.failure_count * 0.02)

        return max(0.5, min(0.99, base_confidence))

    # ============================================================
    # MÉTHODES DE SÉLECTION
    # ============================================================

    async def _select_best_protocol(
        self,
        token_from: str,
        token_to: str,
        direction: ArbitrumBridgeDirection,
        destination_chain: str,
    ) -> ArbitrumBridgeProtocol:
        """Sélectionne le meilleur protocole"""
        available_protocols = []

        for protocol in ArbitrumBridgeProtocol:
            if not self.circuit_breakers[protocol].is_available():
                continue

            if await self._is_protocol_supported(
                protocol, token_from, token_to, direction, destination_chain
            ):
                available_protocols.append(protocol)

        if not available_protocols:
            # Fallback sur le bridge natif
            return ArbitrumBridgeProtocol.ARBITRUM_BRIDGE

        # Score des protocoles
        scores = []
        for protocol in available_protocols:
            score = await self._score_protocol(
                protocol, token_from, token_to, direction, destination_chain
            )
            scores.append((score, protocol))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]

    async def _select_bridge_type(
        self,
        protocol: ArbitrumBridgeProtocol,
        direction: ArbitrumBridgeDirection,
    ) -> ArbitrumBridgeType:
        """Sélectionne le type de bridge"""
        if protocol == ArbitrumBridgeProtocol.ARBITRUM_BRIDGE:
            if direction == ArbitrumBridgeDirection.DEPOSIT:
                return ArbitrumBridgeType.L1_L2
            elif direction == ArbitrumBridgeDirection.WITHDRAWAL:
                return ArbitrumBridgeType.L1_L2
            else:
                return ArbitrumBridgeType.L2_L2
        elif protocol == ArbitrumBridgeProtocol.ARBITRUM_NATIVE:
            return ArbitrumBridgeType.NATIVE
        elif protocol == ArbitrumBridgeProtocol.RETRYABLE:
            return ArbitrumBridgeType.RETRYABLE
        else:
            return ArbitrumBridgeType.L2_L2

    async def _is_protocol_supported(
        self,
        protocol: ArbitrumBridgeProtocol,
        token_from: str,
        token_to: str,
        direction: ArbitrumBridgeDirection,
        destination_chain: str,
    ) -> bool:
        """Vérifie si un protocole supporte la requête"""
        # Tokens supportés
        supported_tokens = self.config.get("protocol_tokens", {}).get(protocol.value, [])
        if supported_tokens and token_from not in supported_tokens:
            return False

        # Directions supportées
        supported_directions = self.config.get("protocol_directions", {}).get(protocol.value, [])
        if supported_directions and direction.value not in supported_directions:
            return False

        # Chaînes destination supportées
        supported_chains = self.config.get("protocol_chains", {}).get(protocol.value, [])
        if supported_chains and destination_chain not in supported_chains:
            return False

        return True

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_balance(
        self,
        token: str,
        address: str,
        direction: ArbitrumBridgeDirection,
    ) -> Decimal:
        """Obtient le solde d'un token"""
        provider = self.l1_web3 if direction == ArbitrumBridgeDirection.DEPOSIT else self.l2_web3

        try:
            if token == "ETH":
                balance = await provider.eth.get_balance(address)
                return Decimal(str(balance)) / Decimal(1e18)

            token_mapping = self._token_mapping_cache["arbitrum"]
            token_address = token_mapping.get(token, token)

            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            decimals = self._get_token_decimals(token)
            balance = await token_contract.functions.balanceOf(
                to_checksum_address(address)
            ).call()

            return Decimal(str(balance)) / Decimal(10 ** decimals)

        except Exception as e:
            logger.error(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _get_l1_gas_price(self) -> int:
        """Obtient le prix du gaz L1"""
        try:
            return await self.l1_web3.eth.gas_price
        except Exception:
            return 30000000000  # 30 Gwei par défaut

    async def _get_l2_gas_price(self) -> int:
        """Obtient le prix du gaz L2"""
        try:
            return await self.l2_web3.eth.gas_price
        except Exception:
            return 100000000  # 0.1 Gwei par défaut

    async def _get_gas_price(self, direction: ArbitrumBridgeDirection) -> int:
        """Obtient le prix du gaz selon la direction"""
        if direction == ArbitrumBridgeDirection.DEPOSIT:
            return await self._get_l1_gas_price()
        else:
            return await self._get_l2_gas_price()

    async def _get_l2_token_address(self, l1_token: str, token_symbol: str) -> str:
        """Obtient l'adresse L2 d'un token L1"""
        # Vérifier le cache
        l2_mapping = self._token_mapping_cache.get("cross_chain", {}).get("arbitrum", {})
        for l2_addr, l1_addr in l2_mapping.items():
            if l1_addr.lower() == l1_token.lower():
                return l2_addr

        # Si non trouvé, retourner l'adresse L1
        return l1_token

    async def _get_l1_token_address(self, l2_token: str, token_symbol: str) -> str:
        """Obtient l'adresse L1 d'un token L2"""
        # Vérifier le cache
        l1_mapping = self._token_mapping_cache.get("cross_chain", {}).get("ethereum", {})
        for l1_addr, l2_addr in l1_mapping.items():
            if l2_addr.lower() == l2_token.lower():
                return l1_addr

        return l2_token

    def _encode_retryable_data(
        self,
        token_from: str,
        token_to: str,
        amount: int,
        destination: str,
    ) -> bytes:
        """Encode les données pour un retryable ticket"""
        # Encodage ABI des données
        encoded = web3.Web3.to_bytes(text=f"{token_from}:{token_to}:{amount}:{destination}")
        return encoded

    def _get_spender_address(
        self,
        protocol: ArbitrumBridgeProtocol,
        direction: ArbitrumBridgeDirection,
    ) -> str:
        """Obtient l'adresse du spender"""
        if protocol == ArbitrumBridgeProtocol.ARBITRUM_BRIDGE:
            if direction == ArbitrumBridgeDirection.DEPOSIT:
                return self.CONTRACTS["l1"]["bridge"]
            else:
                return self.CONTRACTS["l2"]["bridge"]
        else:
            protocol_config = self.config.get("protocols", {}).get(protocol.value, {})
            return protocol_config.get("spender", "0x")

    def _get_chain_id(self, chain_name: str) -> int:
        """Obtient l'ID de chaîne"""
        chain_ids = {
            "ethereum": 1,
            "arbitrum": 42161,
            "polygon": 137,
            "optimism": 10,
            "bsc": 56,
            "avalanche": 43114,
            "base": 8453,
        }
        return chain_ids.get(chain_name, 42161)

    def _get_layerzero_adapter_params(self) -> bytes:
        """Obtient les paramètres d'adaptateur LayerZero"""
        return b"".join([b"\x00", (200000).to_bytes(4, "big")])

    def _get_wormhole_emitter(self, chain_id: int) -> str:
        """Obtient l'émulateur Wormhole"""
        emitters = {
            1: "0x0000000000000000000000000000000000000000",
            42161: "0x0000000000000000000000000000000000000000",
            137: "0x0000000000000000000000000000000000000000",
            10: "0x0000000000000000000000000000000000000000",
            56: "0x0000000000000000000000000000000000000000",
            43114: "0x0000000000000000000000000000000000000000",
        }
        return emitters.get(chain_id, "0x0000000000000000000000000000000000000000")

    async def _get_deposit_info(self, l1_tx_hash: str) -> Dict[str, Any]:
        """Récupère les informations d'un dépôt"""
        # Simulé - dans la réalité, on interrogerait l'indexeur
        return {"status": "pending"}

    async def _get_withdrawal_info(self, l2_tx_hash: str) -> Dict[str, Any]:
        """Récupère les informations d'un retrait"""
        return {"status": "pending"}

    async def _get_retryable_ticket_status(self, ticket_id: str) -> Dict[str, Any]:
        """Récupère le statut d'un retryable ticket"""
        if ticket_id in self._retryable_queue:
            return {"status": "completed", "ticket_id": ticket_id}
        return {"status": "pending"}

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
                    return dict(receipt)
            except Exception:
                pass
            await asyncio.sleep(2)

        raise BridgeError(f"Timeout de transaction: {tx_hash.hex()}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        completed_bridges = [b for b in self._bridge_history if b.get("status") == "completed"]
        failed_bridges = [b for b in self._bridge_history if b.get("status") == "failed"]

        total_volume = sum(
            Decimal(b.get("amount", "0")) for b in self._bridge_history
            if b.get("amount")
        )

        return {
            "total_bridges": len(self._bridge_history),
            "completed_bridges": len(completed_bridges),
            "failed_bridges": len(failed_bridges),
            "active_bridges": len(self._active_bridges),
            "success_rate": len(completed_bridges) / max(1, len(self._bridge_history)),
            "total_volume": str(total_volume),
            "protocol_stats": self._get_protocol_stats(),
            "retryable_stats": self._get_retryable_stats(),
        }

    def _get_protocol_stats(self) -> Dict[str, Any]:
        """Obtient les statistiques par protocole"""
        stats = defaultdict(lambda: {"count": 0, "volume": Decimal("0")})

        for bridge in self._bridge_history:
            protocol = bridge.get("protocol", "unknown")
            stats[protocol]["count"] += 1
            if bridge.get("amount"):
                stats[protocol]["volume"] += Decimal(bridge["amount"])

        return {
            k: {"count": v["count"], "volume": str(v["volume"])}
            for k, v in stats.items()
        }

    def _get_retryable_stats(self) -> Dict[str, Any]:
        """Obtient les statistiques des retryable tickets"""
        total = len(self._retryable_queue)
        pending = sum(1 for t in self._retryable_queue.values() if t.get("status") == "pending")
        completed = sum(1 for t in self._retryable_queue.values() if t.get("status") == "completed")

        return {
            "total": total,
            "pending": pending,
            "completed": completed,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources ArbitrumBridge...")

        # Nettoyage des caches
        self._quote_cache.clear()
        self._gas_cache.clear()
        self._token_mapping_cache.clear()
        self._retryable_cache.clear()
        self._retryable_queue.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_arbitrum_bridge(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Web3],
    bridge_manager: BridgeManager,
    transaction_manager: BridgeTransactionManager,
    **kwargs,
) -> ArbitrumBridge:
    """
    Crée une instance de ArbitrumBridge

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        bridge_manager: Gestionnaire de bridges
        transaction_manager: Gestionnaire de transactions
        **kwargs: Arguments additionnels

    Returns:
        Instance de ArbitrumBridge
    """
    return ArbitrumBridge(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du ArbitrumBridge"""
    # Configuration
    config = {
        "protocol_tokens": {
            "arbitrum_bridge": ["ETH", "USDC", "USDT", "DAI", "WBTC"],
            "layerzero": ["ETH", "USDC", "USDT"],
            "wormhole": ["ETH", "USDC", "USDT", "WBTC"],
            "multichain": ["ETH", "USDC", "USDT", "DAI"],
            "stargate": ["ETH", "USDC", "USDT"],
        },
        "protocol_directions": {
            "arbitrum_bridge": ["deposit", "withdrawal", "cross_chain"],
            "arbitrum_native": ["cross_chain"],
            "retryable": ["retryable"],
            "layerzero": ["cross_chain"],
            "wormhole": ["cross_chain"],
            "multichain": ["cross_chain"],
            "stargate": ["cross_chain"],
        },
        "protocol_chains": {
            "arbitrum_bridge": ["ethereum", "polygon", "optimism"],
            "layerzero": ["ethereum", "polygon", "optimism", "bsc", "avalanche"],
            "wormhole": ["ethereum", "polygon", "solana", "bsc"],
            "multichain": ["ethereum", "polygon", "optimism", "bsc"],
            "stargate": ["ethereum", "polygon", "optimism", "bsc", "avalanche"],
        },
        "token_mappings": {
            "arbitrum": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "USDC": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
            },
        },
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "arbitrum": Web3(Web3.HTTPProvider("https://arb1.arbitrum.io/rpc")),
    }

    # Ajout du middleware PoA pour Arbitrum
    try:
        web3_providers["arbitrum"].middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Bridge manager (simplifié)
    class SimpleBridgeManager:
        pass

    bridge_manager = SimpleBridgeManager()

    # Transaction manager (simplifié)
    class SimpleTransactionManager:
        async def create_and_send_transaction(self, **kwargs):
            return {"tx_hash": "0x..."}

    transaction_manager = SimpleTransactionManager()

    # Création du bridge
    bridge = create_arbitrum_bridge(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
    )

    # Obtention d'un devis pour un dépôt
    quote = await bridge.get_quote(
        token_from="ETH",
        token_to="ETH",
        amount=Decimal("0.1"),
        direction=ArbitrumBridgeDirection.DEPOSIT,
        destination_chain="arbitrum",
        destination_address="0x...",
        protocol=ArbitrumBridgeProtocol.ARBITRUM_BRIDGE,
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un bridge
    request = ArbitrumBridgeRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol=ArbitrumBridgeProtocol.ARBITRUM_BRIDGE,
        bridge_type=ArbitrumBridgeType.L1_L2,
        direction=ArbitrumBridgeDirection.DEPOSIT,
        token_from="ETH",
        token_to="ETH",
        amount=Decimal("0.01"),
        source_address="0x...",
        destination_address="0x...",
        destination_chain="arbitrum",
    )

    result = await bridge.execute_bridge(request)
    print(f"Résultat: {result}")

    # Nettoyage
    await bridge.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

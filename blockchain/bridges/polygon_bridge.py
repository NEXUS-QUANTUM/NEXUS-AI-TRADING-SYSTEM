# blockchain/bridges/polygon_bridge.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Bridge Polygon (PoS)

Ce module implémente un système complet de bridge pour la blockchain Polygon
avec support des bridges PoS (Proof of Stake) et Plasma, gestion des frais
optimisés, et mécanismes de sécurité avancés.

Fonctionnalités principales:
- Support du bridge PoS Polygon
- Support du bridge Plasma (legacy)
- Gestion des tokens ERC-20 et ERC-721
- Optimisation des frais de gaz
- Support des mappings de tokens
- Surveillance en temps réel des bridges
- Mécanismes de fallback
- Gestion des approvals
- Monitoring des transactions cross-chain
- Support des withdrawals rapides
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
    from ..wallets.ethereum_wallet import EthereumWallet
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
    from ..wallets.ethereum_wallet import EthereumWallet
    from ..security.encryption import EncryptionManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class PolygonBridgeProtocol(Enum):
    """Protocoles de bridge supportés sur Polygon"""
    POS = "pos"  # Bridge PoS Polygon
    PLASMA = "plasma"  # Bridge Plasma (legacy)
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


class PolygonBridgeDirection(Enum):
    """Direction du bridge"""
    DEPOSIT = "deposit"  # L1 -> L2 (Polygon)
    WITHDRAWAL = "withdrawal"  # L2 (Polygon) -> L1
    CROSS_CHAIN = "cross_chain"


class PolygonBridgeType(Enum):
    """Type de bridge Polygon"""
    POS = "pos"  # Proof of Stake
    PLASMA = "plasma"  # Plasma
    ERC20 = "erc20"
    ERC721 = "erc721"
    ERC1155 = "erc1155"


@dataclass
class PolygonBridgeQuote:
    """Devis de bridge Polygon"""
    quote_id: str
    protocol: PolygonBridgeProtocol
    bridge_type: PolygonBridgeType
    direction: PolygonBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    gas_estimate: Decimal
    bridge_fees: Decimal
    total_fees: Decimal
    estimated_time: int  # secondes
    min_amount_received: Decimal
    max_slippage: Decimal
    confidence: float
    checkpoint_required: bool
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
            "gas_estimate": str(self.gas_estimate),
            "bridge_fees": str(self.bridge_fees),
            "total_fees": str(self.total_fees),
            "estimated_time": self.estimated_time,
            "min_amount_received": str(self.min_amount_received),
            "max_slippage": str(self.max_slippage),
            "confidence": self.confidence,
            "checkpoint_required": self.checkpoint_required,
        }


@dataclass
class PolygonBridgeRequest:
    """Requête de bridge Polygon"""
    request_id: str
    protocol: PolygonBridgeProtocol
    bridge_type: PolygonBridgeType
    direction: PolygonBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    use_fallback: bool = True
    max_gas_price: Optional[Decimal] = None
    wait_for_checkpoint: bool = True
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
            "slippage_tolerance": str(self.slippage_tolerance),
            "deadline": self.deadline,
            "use_fallback": self.use_fallback,
            "max_gas_price": str(self.max_gas_price) if self.max_gas_price else None,
            "wait_for_checkpoint": self.wait_for_checkpoint,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class PolygonBridge(BaseBridge):
    """
    Bridge avancé pour Polygon avec support PoS et autres protocoles
    """

    # Adresses des contrats Polygon (Mainnet)
    CONTRACTS = {
        "pos": {
            "l1": {
                "root_chain_manager": "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77",
                "root_chain": "0x86E4Dc95c7FBdBf52e33D563BbDB00823894C287",
                "deposit_manager": "0x401F6c983eA34274ec46f84D70b31C151321188b",
                "state_sender": "0x28e4F3a7f651294B3a2207942E3aEe4E66CbE6b0",
                "predicate_manager": "0xE52F3DAD0dEcFd6064F7bBEf41EAfA60E54E539f",
            },
            "l2": {
                "root_chain_manager": "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77",
                "child_chain": "0x7C574BD8AAb1B3307B84bC93Bd7Db0C8226075A4",
                "child_token": "0x0000000000000000000000000000000000001010",
            },
        },
        "plasma": {
            "l1": {
                "root_chain_manager": "0x5E46E194E84D74cC0F4aF2A6918F2C49B5fB9E57",
                "root_chain": "0x22bB2d3F6842D3F702224d47D70D3c7051e43877",
            },
            "l2": {
                "child_chain": "0x7C574BD8AAb1B3307B84bC93Bd7Db0C8226075A4",
            },
        },
        "layerzero": {
            "l2": {
                "address": "0x4B29C7Ab7F95A3355bD6F1FcBf388cD6534fC819",
            },
        },
        "wormhole": {
            "l2": {
                "address": "0xE91D153E0b41518A2Ce8Dd3D7944Fa863463a97d",
            },
        },
        "cctp": {
            "l2": {
                "address": "0x354222B555b952382a5762d4c342E7FBeA0B5b3C",
            },
        },
    }

    # ABIs des contrats
    ROOT_CHAIN_MANAGER_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
                {"name": "data", "type": "bytes"},
            ],
            "name": "deposit",
            "outputs": [],
            "payable": True,
            "stateMutability": "payable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
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
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
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
            "name": "deposits",
            "outputs": [
                {"name": "depositId", "type": "bytes32"},
                {"name": "status", "type": "uint8"},
                {"name": "amount", "type": "uint256"},
                {"name": "timestamp", "type": "uint256"},
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
    ]

    CHILD_CHAIN_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
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

    TOKEN_MAPPING_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "", "type": "address"}],
            "name": "tokenToToken",
            "outputs": [
                {"name": "l1Token", "type": "address"},
                {"name": "l2Token", "type": "address"},
            ],
            "payable": False,
            "stateMutability": "view",
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
        Initialise le bridge Polygon

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
        self.l2_web3 = web3_providers.get("polygon")

        if not self.l1_web3 or not self.l2_web3:
            raise ValueError("Providers L1 et L2 requis")

        # États internes
        self._active_bridges: Dict[str, Dict[str, Any]] = {}
        self._bridge_history: List[Dict[str, Any]] = []
        self._quote_cache: Dict[str, Tuple[float, PolygonBridgeQuote]] = {}
        self._contracts: Dict[str, Dict[str, Contract]] = {}
        self._token_mappings: Dict[str, Dict[str, str]] = {}
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[PolygonBridgeProtocol, CircuitBreaker] = {
            protocol: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
            for protocol in PolygonBridgeProtocol
        }

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache
        self._gas_cache: Dict[str, Dict[str, Any]] = {}
        self._deposit_cache: Dict[str, Dict[str, Any]] = {}
        self._withdrawal_cache: Dict[str, Dict[str, Any]] = {}

        # Charge les contrats
        self._load_contracts()

        # Charge les mappings de tokens
        self._load_token_mappings()

        logger.info("PolygonBridge initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats smart"""
        try:
            # Contrats L1
            l1_contracts = {}
            for name, contract_info in self.CONTRACTS.items():
                l1_info = contract_info.get("l1")
                if l1_info:
                    abi = self._get_contract_abi(name, "l1")
                    for contract_name, address in l1_info.items():
                        if address:
                            l1_contracts[contract_name] = self.l1_web3.eth.contract(
                                address=to_checksum_address(address),
                                abi=abi,
                            )
            self._contracts["l1"] = l1_contracts

            # Contrats L2
            l2_contracts = {}
            for name, contract_info in self.CONTRACTS.items():
                l2_info = contract_info.get("l2")
                if l2_info:
                    abi = self._get_contract_abi(name, "l2")
                    for contract_name, address in l2_info.items():
                        if address:
                            l2_contracts[contract_name] = self.l2_web3.eth.contract(
                                address=to_checksum_address(address),
                                abi=abi,
                            )
            self._contracts["l2"] = l2_contracts

            logger.info(f"Contrats L1 chargés: {list(l1_contracts.keys())}")
            logger.info(f"Contrats L2 chargés: {list(l2_contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise BridgeError(f"Erreur de chargement des contrats: {e}")

    def _get_contract_abi(self, name: str, layer: str) -> List[Dict[str, Any]]:
        """Obtient l'ABI pour un contrat spécifique"""
        if name == "pos":
            if layer == "l1":
                return self.ROOT_CHAIN_MANAGER_ABI
            else:
                return self.CHILD_CHAIN_ABI
        elif name == "plasma":
            if layer == "l1":
                return self.ROOT_CHAIN_MANAGER_ABI
            else:
                return self.CHILD_CHAIN_ABI
        else:
            # ABI générique
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
        """Charge les mappings des tokens L1/L2 Polygon"""
        # Mappings standard Polygon PoS
        self._token_mappings = {
            "l1_to_l2": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # ETH natif
                "MATIC": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",  # MATIC L1
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC L1
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT L1
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI L1
                "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC L1
            },
            "l2_to_l1": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # ETH natif L2
                "MATIC": "0x0000000000000000000000000000000000001010",  # MATIC L2
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC L2
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",  # USDT L2
                "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",  # DAI L2
                "WBTC": "0x1bfd67037b42cf73acF2047067bd4F2C47D9BfD6",  # WBTC L2
            }
        }

        # Ajout des mappings depuis la configuration
        if self.config.get("token_mappings"):
            user_mappings = self.config.get("token_mappings", {})
            for direction, tokens in user_mappings.items():
                if direction in self._token_mappings:
                    self._token_mappings[direction].update(tokens)

        logger.info(f"Token mappings chargés: {len(self._token_mappings)} directions")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_quote(
        self,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: PolygonBridgeDirection,
        destination_address: str,
        protocol: Optional[PolygonBridgeProtocol] = None,
        bridge_type: Optional[PolygonBridgeType] = None,
        **kwargs,
    ) -> PolygonBridgeQuote:
        """
        Obtient un devis pour un bridge Polygon

        Args:
            token_from: Token source
            token_to: Token destination
            amount: Montant à bridge
            direction: Direction du bridge
            destination_address: Adresse destination
            protocol: Protocole spécifique
            bridge_type: Type de bridge
            **kwargs: Arguments additionnels

        Returns:
            Devis de bridge
        """
        logger.info(
            f"Demande de devis Polygon: {amount} {token_from} -> {token_to} "
            f"({direction.value})"
        )

        # Vérification du cache
        cache_key = f"{token_from}:{token_to}:{amount}:{direction.value}:{protocol}:{bridge_type}"
        if cache_key in self._quote_cache:
            cached_time, quote = self._quote_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Devis retourné du cache")
                return quote

        try:
            # Sélection du protocole
            if protocol is None:
                protocol = await self._select_best_protocol(
                    token_from, token_to, direction
                )

            # Sélection du type de bridge
            if bridge_type is None:
                bridge_type = await self._select_bridge_type(protocol, token_from, direction)

            # Vérification du circuit breaker
            if not self.circuit_breakers[protocol].is_available():
                logger.warning(f"Circuit breaker ouvert pour {protocol.value}")
                fallback_protocol = await self._select_fallback_protocol(
                    protocol, token_from, token_to, direction
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
                destination_address=destination_address,
                **kwargs,
            )

            # Mise en cache
            self._quote_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "polygon_bridge_quote",
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
        request: PolygonBridgeRequest,
    ) -> Dict[str, Any]:
        """
        Exécute un bridge Polygon

        Args:
            request: Requête de bridge

        Returns:
            Résultat du bridge
        """
        bridge_id = f"poly_bridge_{uuid.uuid4().hex[:12]}"
        logger.info(f"Exécution du bridge Polygon {bridge_id}")

        try:
            # 1. Obtention du devis
            quote = await self.get_quote(
                token_from=request.token_from,
                token_to=request.token_to,
                amount=request.amount,
                direction=request.direction,
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

            # 4. Vérification des mappings de tokens
            if request.token_from != request.token_to:
                token_mapping = await self._get_token_mapping(
                    request.token_from,
                    request.direction,
                )
                if not token_mapping:
                    raise BridgeError(f"Mapping non trouvé pour {request.token_from}")

            # 5. Approval du token si nécessaire
            if request.token_from != "ETH" and request.token_from != "MATIC":
                await self._approve_token(
                    token=request.token_from,
                    amount=request.amount,
                    wallet=wallet,
                    protocol=request.protocol,
                    direction=request.direction,
                )

            # 6. Exécution selon la direction
            if request.direction == PolygonBridgeDirection.DEPOSIT:
                result = await self._execute_deposit(request, quote, wallet)
            elif request.direction == PolygonBridgeDirection.WITHDRAWAL:
                result = await self._execute_withdrawal(request, quote, wallet)
            else:
                result = await self._execute_cross_chain(request, quote, wallet)

            # 7. Attente de la confirmation
            final_result = await self._wait_for_confirmation(
                bridge_id=bridge_id,
                tx_hash=result.get("tx_hash"),
                direction=request.direction,
                wait_for_checkpoint=request.wait_for_checkpoint,
            )

            # Mise à jour du statut
            result["status"] = "completed"
            result["bridge_id"] = bridge_id
            result["amount_received"] = final_result.get("amount_received", quote.min_amount_received)
            result["fees_paid"] = quote.total_fees
            result["completed_at"] = datetime.now().isoformat()
            result["checkpoint"] = final_result.get("checkpoint")

            # Stockage
            self._active_bridges.pop(bridge_id, None)
            self._bridge_history.append(result)

            # Métriques
            self.metrics.record_increment(
                "polygon_bridge_completed",
                {
                    "protocol": request.protocol.value,
                    "bridge_type": request.bridge_type.value,
                    "direction": request.direction.value,
                    "token": request.token_from,
                },
            )

            logger.info(f"Bridge Polygon {bridge_id} terminé avec succès")
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
                "polygon_bridge_failed",
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
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un dépôt L1 -> Polygon"""
        logger.info(f"Exécution du dépôt Polygon: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de dépôt
            tx_data = await self._build_deposit_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="ethereum",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="polygon_deposit",
            )

            return {
                "tx_hash": tx_result.get("tx_hash"),
                "direction": "deposit",
                "amount": str(request.amount),
                "token": request.token_from,
                "bridge_type": request.bridge_type.value,
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution du dépôt: {e}")
            raise

    async def _execute_withdrawal(
        self,
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un retrait Polygon -> L1"""
        logger.info(f"Exécution du retrait Polygon: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de retrait
            tx_data = await self._build_withdrawal_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="polygon",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="polygon_withdrawal",
            )

            return {
                "tx_hash": tx_result.get("tx_hash"),
                "direction": "withdrawal",
                "amount": str(request.amount),
                "token": request.token_from,
                "bridge_type": request.bridge_type.value,
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution du retrait: {e}")
            raise

    async def _execute_cross_chain(
        self,
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un bridge cross-chain depuis Polygon"""
        logger.info(f"Exécution du bridge cross-chain Polygon: {request.amount}")

        # Utilisation d'un protocole spécifique
        protocol = request.protocol

        if protocol == PolygonBridgeProtocol.LAYERZERO:
            return await self._execute_layerzero(request, quote, wallet)
        elif protocol == PolygonBridgeProtocol.WORMHOLE:
            return await self._execute_wormhole(request, quote, wallet)
        elif protocol == PolygonBridgeProtocol.CCTP:
            return await self._execute_cctp(request, quote, wallet)
        else:
            return await self._execute_generic_bridge(request, quote, wallet)

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_deposit_transaction(
        self,
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de dépôt Polygon"""
        # Récupération du contrat approprié
        if request.bridge_type == PolygonBridgeType.POS:
            root_chain_manager = self._contracts["l1"].get("root_chain_manager")
            if not root_chain_manager:
                raise BridgeError("RootChainManager non trouvé")
            contract = root_chain_manager
        elif request.bridge_type == PolygonBridgeType.PLASMA:
            root_chain = self._contracts["l1"].get("root_chain")
            if not root_chain:
                raise BridgeError("RootChain non trouvé")
            contract = root_chain
        else:
            # Bridge générique
            contract = self._contracts["l1"].get("deposit_manager")

        if not contract:
            raise BridgeError("Contrat de dépôt non trouvé")

        # Récupération des addresses
        token_mapping = await self._get_token_mapping(request.token_from, PolygonBridgeDirection.DEPOSIT)
        l1_token = token_mapping.get("l1_token", request.token_from) if token_mapping else request.token_from

        # Valeur en wei
        amount_wei = int(request.amount * Decimal(1e18))

        # Construction selon le token
        if request.token_from in ["ETH", "MATIC"]:
            # Dépôt de token natif
            tx_data = contract.functions.deposit(
                to_checksum_address(l1_token),
                amount_wei,
                to_checksum_address(request.destination_address),
                b"",  # Données additionnelles
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "value": amount_wei if request.token_from == "ETH" else 0,
                "gas": 300000,
                "gasPrice": await self._get_l1_gas_price(),
            })
        else:
            # Dépôt d'ERC20
            tx_data = contract.functions.depositERC20(
                to_checksum_address(l1_token),
                amount_wei,
                to_checksum_address(request.destination_address),
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 400000,
                "gasPrice": await self._get_l1_gas_price(),
            })

        return dict(tx_data)

    async def _build_withdrawal_transaction(
        self,
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de retrait Polygon"""
        # Récupération du contrat approprié
        if request.bridge_type == PolygonBridgeType.POS:
            child_chain = self._contracts["l2"].get("child_chain")
            if not child_chain:
                raise BridgeError("ChildChain non trouvé")
            contract = child_chain
        else:
            contract = self._contracts["l2"].get("child_chain")

        if not contract:
            raise BridgeError("Contrat de retrait non trouvé")

        # Récupération des addresses
        token_mapping = await self._get_token_mapping(request.token_from, PolygonBridgeDirection.WITHDRAWAL)
        l2_token = token_mapping.get("l2_token", request.token_from) if token_mapping else request.token_from

        # Valeur en wei
        amount_wei = int(request.amount * Decimal(1e18))

        # Construction de la transaction
        tx_data = contract.functions.withdraw(
            to_checksum_address(l2_token),
            amount_wei,
            to_checksum_address(request.destination_address),
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        return dict(tx_data)

    # ============================================================
    # MÉTHODES D'APPROBATION
    # ============================================================

    async def _approve_token(
        self,
        token: str,
        amount: Decimal,
        wallet: BaseWallet,
        protocol: PolygonBridgeProtocol,
        direction: PolygonBridgeDirection,
    ) -> bool:
        """Approuve un token pour le bridge"""
        try:
            # Récupération du spender
            spender = await self._get_spender_address(protocol, direction)

            # Vérification de l'allowance
            allowance = await self._get_allowance(
                token,
                wallet.address,
                spender,
                direction,
            )

            if allowance >= amount:
                logger.debug(f"Allowance suffisante: {allowance} >= {amount}")
                return True

            # Construction de la transaction d'approbation
            provider = self.l1_web3 if direction == PolygonBridgeDirection.DEPOSIT else self.l2_web3

            token_contract = provider.eth.contract(
                address=to_checksum_address(token),
                abi=self.ERC20_ABI,
            )

            amount_wei = int(amount * Decimal(1e18))

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

    # ============================================================
    # MÉTHODES DE CONFIRMATION ET CHECKPOINTS
    # ============================================================

    async def _wait_for_confirmation(
        self,
        bridge_id: str,
        tx_hash: Optional[str],
        direction: PolygonBridgeDirection,
        wait_for_checkpoint: bool = True,
        timeout: int = 3600,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'un bridge Polygon"""
        if not tx_hash:
            raise BridgeError("Hash de transaction manquant")

        logger.info(f"Attente de confirmation pour {bridge_id}: {tx_hash}")

        start_time = time.time()
        provider = self.l1_web3 if direction == PolygonBridgeDirection.DEPOSIT else self.l2_web3

        while time.time() - start_time < timeout:
            try:
                receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))
                if receipt:
                    status = receipt.get("status")
                    if status == 1:
                        # Vérification du checkpoint pour les dépôts
                        if direction == PolygonBridgeDirection.DEPOSIT and wait_for_checkpoint:
                            checkpoint = await self._wait_for_checkpoint(
                                tx_hash, timeout - (time.time() - start_time)
                            )
                            if checkpoint:
                                return {
                                    "amount_received": str(checkpoint.get("amount", 0)),
                                    "confirmations": 12,
                                    "checkpoint": checkpoint,
                                }
                        else:
                            # Retrait ou confirmation simple
                            confirmations = await self._get_confirmations(
                                "ethereum" if direction == PolygonBridgeDirection.DEPOSIT else "polygon",
                                tx_hash,
                            )
                            if confirmations >= 12:
                                return {
                                    "amount_received": str(confirmations),
                                    "confirmations": confirmations,
                                }

            except Exception as e:
                logger.warning(f"Erreur de vérification: {e}")

            await asyncio.sleep(10)

        raise BridgeError(f"Timeout de confirmation: {tx_hash}")

    async def _wait_for_checkpoint(
        self,
        tx_hash: str,
        timeout: int,
    ) -> Optional[Dict[str, Any]]:
        """Attend le checkpoint Polygon"""
        logger.info(f"Attente du checkpoint pour {tx_hash}")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Récupération du checkpoint
                checkpoint = await self._get_checkpoint_info(tx_hash)
                if checkpoint and checkpoint.get("status") == "completed":
                    return checkpoint
            except Exception as e:
                logger.warning(f"Erreur de vérification du checkpoint: {e}")

            await asyncio.sleep(30)  # Les checkpoints Polygon prennent du temps

        return None

    async def _get_checkpoint_info(self, tx_hash: str) -> Dict[str, Any]:
        """Récupère les informations du checkpoint"""
        # Simulé - dans la réalité, on interroge l'indexeur Polygon
        return {
            "status": "pending",
            "block_number": 0,
            "timestamp": int(time.time()),
        }

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _generate_quote(
        self,
        protocol: PolygonBridgeProtocol,
        bridge_type: PolygonBridgeType,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: PolygonBridgeDirection,
        destination_address: str,
        **kwargs,
    ) -> PolygonBridgeQuote:
        """Génère un devis pour un protocole spécifique"""
        try:
            # Estimation des frais
            gas_estimate = await self._estimate_gas(
                protocol, bridge_type, amount, direction
            )
            bridge_fees = await self._estimate_bridge_fees(
                protocol, token_from, amount, direction
            )
            total_fees = gas_estimate + bridge_fees

            # Estimation du temps
            estimated_time = await self._estimate_time(
                protocol, bridge_type, direction
            )

            # Checkpoint requis
            checkpoint_required = direction == PolygonBridgeDirection.DEPOSIT

            # Niveau de confiance
            confidence = self._calculate_confidence(protocol, amount)

            # Slippage
            slippage = kwargs.get("slippage_tolerance", Decimal("0.005"))

            # Montant minimum reçu
            min_amount_received = amount * (1 - float(slippage))

            return PolygonBridgeQuote(
                quote_id=f"poly_q_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                bridge_type=bridge_type,
                direction=direction,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                gas_estimate=gas_estimate,
                bridge_fees=bridge_fees,
                total_fees=total_fees,
                estimated_time=estimated_time,
                min_amount_received=min_amount_received,
                max_slippage=slippage,
                confidence=confidence,
                checkpoint_required=checkpoint_required,
                quote_data=kwargs,
            )

        except Exception as e:
            logger.error(f"Erreur de génération de devis pour {protocol.value}: {e}")
            raise

    async def _estimate_gas(
        self,
        protocol: PolygonBridgeProtocol,
        bridge_type: PolygonBridgeType,
        amount: Decimal,
        direction: PolygonBridgeDirection,
    ) -> Decimal:
        """Estime les frais de gaz"""
        # Base gas selon le type
        base_gas = {
            PolygonBridgeType.POS: 200000,
            PolygonBridgeType.PLASMA: 300000,
            PolygonBridgeType.ERC20: 150000,
            PolygonBridgeType.ERC721: 250000,
            PolygonBridgeType.ERC1155: 300000,
        }.get(bridge_type, 200000)

        # Ajustement selon la direction
        if direction == PolygonBridgeDirection.WITHDRAWAL:
            base_gas = int(base_gas * 1.5)  # Les retraits consomment plus

        # Obtention du prix du gaz
        gas_price = await self._get_gas_price(direction)
        gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

        total_cost = Decimal(str(base_gas)) * gas_price_decimal
        return total_cost

    async def _estimate_bridge_fees(
        self,
        protocol: PolygonBridgeProtocol,
        token: str,
        amount: Decimal,
        direction: PolygonBridgeDirection,
    ) -> Decimal:
        """Estime les frais de bridge"""
        # Frais par protocole
        base_fees = {
            PolygonBridgeProtocol.POS: Decimal("0.0001"),
            PolygonBridgeProtocol.PLASMA: Decimal("0.0002"),
            PolygonBridgeProtocol.LAYERZERO: Decimal("0.0005"),
            PolygonBridgeProtocol.WORMHOLE: Decimal("0.0003"),
            PolygonBridgeProtocol.CCTP: Decimal("0.0001"),
            PolygonBridgeProtocol.ACROSS: Decimal("0.0004"),
            PolygonBridgeProtocol.HOP: Decimal("0.0006"),
            PolygonBridgeProtocol.SYNAPSE: Decimal("0.0005"),
            PolygonBridgeProtocol.STARGATE: Decimal("0.0004"),
        }.get(protocol, Decimal("0.0003"))

        # Frais variables
        variable_fees = amount * Decimal("0.0002")

        # Ajustement direction
        direction_multiplier = 1.0 if direction == PolygonBridgeDirection.DEPOSIT else 1.3

        return (base_fees + variable_fees) * Decimal(str(direction_multiplier))

    async def _estimate_time(
        self,
        protocol: PolygonBridgeProtocol,
        bridge_type: PolygonBridgeType,
        direction: PolygonBridgeDirection,
    ) -> int:
        """Estime le temps de bridge en secondes"""
        base_time = {
            PolygonBridgeProtocol.POS: 120,
            PolygonBridgeProtocol.PLASMA: 180,
            PolygonBridgeProtocol.LAYERZERO: 100,
            PolygonBridgeProtocol.WORMHOLE: 80,
            PolygonBridgeProtocol.CCTP: 60,
            PolygonBridgeProtocol.ACROSS: 130,
            PolygonBridgeProtocol.HOP: 90,
            PolygonBridgeProtocol.SYNAPSE: 95,
            PolygonBridgeProtocol.STARGATE: 70,
        }.get(protocol, 120)

        # Les retraits sont plus lents à cause des checkpoints
        if direction == PolygonBridgeDirection.WITHDRAWAL:
            base_time += 3600  # 1 heure supplémentaire

        return base_time

    def _calculate_confidence(
        self,
        protocol: PolygonBridgeProtocol,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            PolygonBridgeProtocol.POS: 0.99,
            PolygonBridgeProtocol.PLASMA: 0.95,
            PolygonBridgeProtocol.LAYERZERO: 0.95,
            PolygonBridgeProtocol.WORMHOLE: 0.97,
            PolygonBridgeProtocol.CCTP: 0.98,
            PolygonBridgeProtocol.ACROSS: 0.90,
            PolygonBridgeProtocol.HOP: 0.88,
            PolygonBridgeProtocol.SYNAPSE: 0.87,
            PolygonBridgeProtocol.STARGATE: 0.93,
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
        direction: PolygonBridgeDirection,
    ) -> PolygonBridgeProtocol:
        """Sélectionne le meilleur protocole"""
        available_protocols = []

        for protocol in PolygonBridgeProtocol:
            if not self.circuit_breakers[protocol].is_available():
                continue

            if await self._is_protocol_supported(protocol, token_from, token_to, direction):
                available_protocols.append(protocol)

        if not available_protocols:
            return PolygonBridgeProtocol.POS

        # Score des protocoles
        scores = []
        for protocol in available_protocols:
            score = await self._score_protocol(protocol, token_from, token_to, direction)
            scores.append((score, protocol))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]

    async def _select_bridge_type(
        self,
        protocol: PolygonBridgeProtocol,
        token: str,
        direction: PolygonBridgeDirection,
    ) -> PolygonBridgeType:
        """Sélectionne le type de bridge"""
        # Par défaut pour le bridge POS
        if protocol == PolygonBridgeProtocol.POS:
            if token in ["ETH", "MATIC"]:
                return PolygonBridgeType.POS
            else:
                return PolygonBridgeType.ERC20
        elif protocol == PolygonBridgeProtocol.PLASMA:
            return PolygonBridgeType.PLASMA
        else:
            return PolygonBridgeType.ERC20

    async def _is_protocol_supported(
        self,
        protocol: PolygonBridgeProtocol,
        token_from: str,
        token_to: str,
        direction: PolygonBridgeDirection,
    ) -> bool:
        """Vérifie si un protocole supporte la requête"""
        supported_tokens = self.config.get("protocol_tokens", {}).get(protocol.value, [])
        if supported_tokens and token_from not in supported_tokens:
            return False

        supported_directions = self.config.get("protocol_directions", {}).get(protocol.value, [])
        if supported_directions and direction.value not in supported_directions:
            return False

        return True

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_balance(
        self,
        token: str,
        address: str,
        direction: PolygonBridgeDirection,
    ) -> Decimal:
        """Obtient le solde d'un token"""
        provider = self.l1_web3 if direction == PolygonBridgeDirection.DEPOSIT else self.l2_web3

        try:
            if token in ["ETH", "MATIC"]:
                balance = await provider.eth.get_balance(address)
                return Decimal(str(balance)) / Decimal(1e18)

            token_contract = provider.eth.contract(
                address=to_checksum_address(token),
                abi=self.ERC20_ABI,
            )
            balance = await token_contract.functions.balanceOf(
                to_checksum_address(address)
            ).call()
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            logger.error(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _get_allowance(
        self,
        token: str,
        owner: str,
        spender: str,
        direction: PolygonBridgeDirection,
    ) -> Decimal:
        """Obtient l'allowance d'un token"""
        provider = self.l1_web3 if direction == PolygonBridgeDirection.DEPOSIT else self.l2_web3

        try:
            token_contract = provider.eth.contract(
                address=to_checksum_address(token),
                abi=self.ERC20_ABI,
            )
            allowance = await token_contract.functions.allowance(
                to_checksum_address(owner),
                to_checksum_address(spender),
            ).call()
            return Decimal(str(allowance)) / Decimal(1e18)

        except Exception as e:
            logger.warning(f"Erreur d'allowance: {e}")
            return Decimal("0")

    async def _get_token_mapping(
        self,
        token: str,
        direction: PolygonBridgeDirection,
    ) -> Optional[Dict[str, str]]:
        """Obtient le mapping d'un token"""
        mapping_key = "l1_to_l2" if direction == PolygonBridgeDirection.DEPOSIT else "l2_to_l1"
        mappings = self._token_mappings.get(mapping_key, {})

        # Chercher le mapping pour ce token
        for l1_token, l2_token in mappings.items():
            if l1_token.lower() == token.lower() or l2_token.lower() == token.lower():
                return {
                    "l1_token": l1_token,
                    "l2_token": l2_token,
                }

        return None

    async def _get_spender_address(
        self,
        protocol: PolygonBridgeProtocol,
        direction: PolygonBridgeDirection,
    ) -> str:
        """Obtient l'adresse du spender"""
        if protocol == PolygonBridgeProtocol.POS:
            if direction == PolygonBridgeDirection.DEPOSIT:
                return self.CONTRACTS["pos"]["l1"]["deposit_manager"]
            else:
                return self.CONTRACTS["pos"]["l2"]["child_chain"]
        elif protocol == PolygonBridgeProtocol.PLASMA:
            return self.CONTRACTS["plasma"]["l1"]["root_chain"]
        else:
            # Autres protocoles
            contract_info = self.CONTRACTS.get(protocol.value, {})
            l2_info = contract_info.get("l2", {})
            return l2_info.get("address", "0x")

    async def _get_gas_price(self, direction: PolygonBridgeDirection) -> int:
        """Obtient le prix du gaz"""
        provider = self.l1_web3 if direction == PolygonBridgeDirection.DEPOSIT else self.l2_web3
        try:
            return await provider.eth.gas_price
        except Exception:
            return 30000000000  # 30 Gwei par défaut

    async def _get_l1_gas_price(self) -> int:
        """Obtient le prix du gaz L1"""
        try:
            return await self.l1_web3.eth.gas_price
        except Exception:
            return 50000000000  # 50 Gwei par défaut

    async def _get_l2_gas_price(self) -> int:
        """Obtient le prix du gaz L2 (Polygon)"""
        try:
            return await self.l2_web3.eth.gas_price
        except Exception:
            return 100000000000  # 100 Gwei sur Polygon par défaut

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

    async def _get_confirmations(self, chain: str, tx_hash: str) -> int:
        """Obtient le nombre de confirmations"""
        provider = self.web3_providers.get(chain)
        if not provider:
            return 0

        try:
            receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))
            if not receipt:
                return 0

            block_number = receipt.get("blockNumber", 0)
            current_block = await provider.eth.block_number
            return current_block - block_number + 1

        except Exception:
            return 0

    # ============================================================
    # MÉTHODES DE PROTOCOLES SPÉCIFIQUES
    # ============================================================

    async def _execute_layerzero(
        self,
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute LayerZero sur Polygon"""
        logger.info("Exécution de LayerZero bridge sur Polygon")

        layerzero_contract = self._contracts["l2"].get("address")
        if not layerzero_contract:
            raise BridgeError("Contrat LayerZero non trouvé")

        chain_id = self._get_chain_id(request.destination_chain)
        adapter_params = self._get_layerzero_adapter_params()

        tx_data = layerzero_contract.functions.bridge(
            to_checksum_address(request.token_from),
            int(request.amount * Decimal(1e18)),
            to_checksum_address(request.destination_address),
            chain_id,
            adapter_params,
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="polygon",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="polygon_layerzero",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "layerzero",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_wormhole(
        self,
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Wormhole sur Polygon"""
        logger.info("Exécution de Wormhole bridge sur Polygon")

        wormhole_contract = self._contracts["l2"].get("address")
        if not wormhole_contract:
            raise BridgeError("Contrat Wormhole non trouvé")

        chain_id = self._get_chain_id(request.destination_chain)
        emitter = self._get_wormhole_emitter(chain_id)

        tx_data = wormhole_contract.functions.bridge(
            to_checksum_address(request.token_from),
            int(request.amount * Decimal(1e18)),
            to_checksum_address(request.destination_address),
            chain_id,
            to_checksum_address(emitter),
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 250000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="polygon",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="polygon_wormhole",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "wormhole",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_cctp(
        self,
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute CCTP (Circle) sur Polygon"""
        logger.info("Exécution de CCTP bridge sur Polygon")

        cctp_contract = self._contracts["l2"].get("address")
        if not cctp_contract:
            raise BridgeError("Contrat CCTP non trouvé")

        domain = self._get_circle_domain(request.destination_chain)

        tx_data = cctp_contract.functions.depositForBurn(
            int(request.amount * Decimal(1e6)),
            domain,
            to_checksum_address(request.destination_address),
            to_checksum_address(request.token_from),
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 200000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="polygon",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="polygon_cctp",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "cctp",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_generic_bridge(
        self,
        request: PolygonBridgeRequest,
        quote: PolygonBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un protocole générique"""
        logger.info("Exécution du bridge générique sur Polygon")

        contract_name = request.protocol.value
        generic_contract = self._contracts["l2"].get(contract_name)
        if not generic_contract:
            raise BridgeError(f"Contrat {contract_name} non trouvé")

        tx_data = generic_contract.functions.bridge(
            to_checksum_address(request.token_from),
            int(request.amount * Decimal(1e18)),
            to_checksum_address(request.destination_address),
            b"",
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_l2_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="polygon",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="polygon_generic",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": request.protocol.value,
            "amount": str(request.amount),
            "token": request.token_from,
        }

    # ============================================================
    # MÉTHODES DE CONFIGURATION
    # ============================================================

    def _get_chain_id(self, chain_name: str) -> int:
        """Obtient l'ID de chaîne"""
        chain_ids = {
            "ethereum": 1,
            "polygon": 137,
            "bsc": 56,
            "arbitrum": 42161,
            "optimism": 10,
            "avalanche": 43114,
            "base": 8453,
        }
        return chain_ids.get(chain_name, 137)

    def _get_layerzero_adapter_params(self) -> bytes:
        """Obtient les paramètres d'adaptateur LayerZero"""
        return b"".join([b"\x00", (200000).to_bytes(4, "big")])

    def _get_wormhole_emitter(self, chain_id: int) -> str:
        """Obtient l'émulateur Wormhole"""
        emitters = {
            1: "0x0000000000000000000000000000000000000000",
            56: "0x0000000000000000000000000000000000000000",
            137: "0x0000000000000000000000000000000000000000",
            42161: "0x0000000000000000000000000000000000000000",
            10: "0x0000000000000000000000000000000000000000",
            43114: "0x0000000000000000000000000000000000000000",
        }
        return emitters.get(chain_id, "0x0000000000000000000000000000000000000000")

    def _get_circle_domain(self, chain_name: str) -> int:
        """Obtient le domaine Circle"""
        domains = {
            "ethereum": 0,
            "arbitrum": 3,
            "optimism": 2,
            "avalanche": 1,
            "polygon": 7,
        }
        return domains.get(chain_name, 0)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources PolygonBridge...")

        # Nettoyage des caches
        self._quote_cache.clear()
        self._gas_cache.clear()
        self._token_mappings.clear()
        self._checkpoints.clear()
        self._deposit_cache.clear()
        self._withdrawal_cache.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_polygon_bridge(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Web3],
    bridge_manager: BridgeManager,
    transaction_manager: BridgeTransactionManager,
    **kwargs,
) -> PolygonBridge:
    """
    Crée une instance de PolygonBridge

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        bridge_manager: Gestionnaire de bridges
        transaction_manager: Gestionnaire de transactions
        **kwargs: Arguments additionnels

    Returns:
        Instance de PolygonBridge
    """
    return PolygonBridge(
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
    """Exemple d'utilisation du bridge Polygon"""
    # Configuration
    config = {
        "protocol_tokens": {
            "pos": ["ETH", "MATIC", "USDC", "USDT", "DAI"],
            "layerzero": ["ETH", "USDC", "USDT"],
            "wormhole": ["ETH", "USDC", "WBTC"],
        },
        "protocol_directions": {
            "pos": ["deposit", "withdrawal"],
            "layerzero": ["cross_chain"],
            "wormhole": ["cross_chain"],
        },
        "token_mappings": {
            "l1_to_l2": {
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "MATIC": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
            },
            "l2_to_l1": {
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "MATIC": "0x0000000000000000000000000000000000001010",
            },
        },
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "polygon": Web3(Web3.HTTPProvider("https://polygon-rpc.com")),
    }

    # Ajout du middleware PoA pour Polygon
    web3_providers["polygon"].middleware_onion.inject(geth_poa_middleware, layer=0)

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
    bridge = create_polygon_bridge(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
    )

    # Obtention d'un devis pour un dépôt
    quote = await bridge.get_quote(
        token_from="MATIC",
        token_to="MATIC",
        amount=Decimal("10"),
        direction=PolygonBridgeDirection.DEPOSIT,
        destination_address="0x...",
        protocol=PolygonBridgeProtocol.POS,
        bridge_type=PolygonBridgeType.POS,
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un bridge
    request = PolygonBridgeRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol=PolygonBridgeProtocol.POS,
        bridge_type=PolygonBridgeType.POS,
        direction=PolygonBridgeDirection.DEPOSIT,
        token_from="MATIC",
        token_to="MATIC",
        amount=Decimal("1"),
        source_address="0x...",
        destination_address="0x...",
    )

    result = await bridge.execute_bridge(request)
    print(f"Résultat: {result}")

    # Nettoyage
    await bridge.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

# blockchain/bridges/optimism_bridge.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Bridge Optimism (OP Mainnet)

Ce module implémente un système complet de bridge pour la blockchain Optimism
avec support de tous les protocoles de bridge majeurs, gestion optimisée des
frais de gaz L1/L2, et mécanismes de sécurité avancés.

Fonctionnalités principales:
- Support de tous les protocoles de bridge sur Optimism
- Gestion des frais L1 (Layer 1) et L2 (Layer 2)
- Optimisation des transactions avec EIP-1559
- Support des withdrawals (retraits) L2 -> L1
- Surveillance en temps réel des bridges
- Mécanismes de fallback et reprise
- Support des tokens standard (ERC-20, ETH)
- Gestion des approvals L1/L2
- Monitoring des transactions cross-chain
- Support du bridge natif Optimism
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

class OptimismBridgeProtocol(Enum):
    """Protocoles de bridge supportés sur Optimism"""
    NATIVE = "native"  # Bridge natif Optimism
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
    LIQUIDITY = "liquidity"


class OptimismBridgeDirection(Enum):
    """Direction du bridge"""
    DEPOSIT = "deposit"  # L1 -> L2
    WITHDRAWAL = "withdrawal"  # L2 -> L1
    CROSS_CHAIN = "cross_chain"


class L2GasStrategy(Enum):
    """Stratégies de gaz pour Optimism"""
    STANDARD = "standard"
    FAST = "fast"
    RAPID = "rapid"
    L1_PRIORITY = "l1_priority"
    ECONOMICAL = "economical"


@dataclass
class OptimismBridgeQuote:
    """Devis de bridge Optimism"""
    quote_id: str
    protocol: OptimismBridgeProtocol
    direction: OptimismBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    l1_gas_estimate: Decimal  # Frais L1
    l2_gas_estimate: Decimal  # Frais L2
    bridge_fees: Decimal
    total_fees: Decimal
    estimated_time: int  # secondes
    min_amount_received: Decimal
    max_slippage: Decimal
    confidence: float
    l1_security_check: bool
    l2_security_check: bool
    quote_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol.value,
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
            "l1_security_check": self.l1_security_check,
            "l2_security_check": self.l2_security_check,
        }


@dataclass
class OptimismBridgeRequest:
    """Requête de bridge Optimism"""
    request_id: str
    protocol: OptimismBridgeProtocol
    direction: OptimismBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    gas_strategy: L2GasStrategy = L2GasStrategy.STANDARD
    use_fallback: bool = True
    max_l1_gas_price: Optional[Decimal] = None
    max_l2_gas_price: Optional[Decimal] = None
    custom_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "protocol": self.protocol.value,
            "direction": self.direction.value,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "source_address": self.source_address,
            "destination_address": self.destination_address,
            "slippage_tolerance": str(self.slippage_tolerance),
            "deadline": self.deadline,
            "gas_strategy": self.gas_strategy.value,
            "use_fallback": self.use_fallback,
            "max_l1_gas_price": str(self.max_l1_gas_price) if self.max_l1_gas_price else None,
            "max_l2_gas_price": str(self.max_l2_gas_price) if self.max_l2_gas_price else None,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class OptimismBridge(BaseBridge):
    """
    Bridge avancé pour Optimism avec support multi-protocoles
    """

    # Adresses des contrats Optimism (Mainnet)
    CONTRACTS = {
        "native_bridge": {
            "address": "0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1",
            "l1_cross_domain_messenger": "0x25ace71c97B33Cc4729CF772ae268934F7ab5fA1",
            "l1_standard_bridge": "0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1",
            "l2_cross_domain_messenger": "0x4200000000000000000000000000000000000007",
            "l2_standard_bridge": "0x4200000000000000000000000000000000000010",
        },
        "layerzero": {
            "address": "0x4B29C7Ab7F95A3355bD6F1FcBf388cD6534fC819",
            "endpoint": "0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675",
        },
        "wormhole": {
            "address": "0xE91D153E0b41518A2Ce8Dd3D7944Fa863463a97d",
            "core_bridge": "0x0b2402144Bb366a632D14B83F244D2e0e21bD39c",
        },
        "cctp": {
            "address": "0x354222B555b952382a5762d4c342E7FBeA0B5b3C",
        },
    }

    # ABIs des contrats
    NATIVE_BRIDGE_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_amount", "type": "uint256"},
                {"name": "_data", "type": "bytes"},
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
                {"name": "_l1Token", "type": "address"},
                {"name": "_l2Token", "type": "address"},
                {"name": "_amount", "type": "uint256"},
                {"name": "_minGasLimit", "type": "uint32"},
                {"name": "_extraData", "type": "bytes"},
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
                {"name": "_l1Token", "type": "address"},
                {"name": "_l2Token", "type": "address"},
                {"name": "_amount", "type": "uint256"},
            ],
            "name": "withdrawERC20",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [
                {"name": "_l1Token", "type": "address"},
                {"name": "_l2Token", "type": "address"},
            ],
            "name": "getTokenAddresses",
            "outputs": [
                {"name": "", "type": "address"},
                {"name": "", "type": "address"},
            ],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
    ]

    L2_MESSENGER_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "_target", "type": "address"},
                {"name": "_message", "type": "bytes"},
                {"name": "_gasLimit", "type": "uint32"},
            ],
            "name": "sendMessage",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "", "type": "bytes32"}],
            "name": "sentMessages",
            "outputs": [{"name": "", "type": "bool"}],
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
        Initialise le bridge Optimism

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

        # Séparation des providers L1/L2
        self.l1_web3 = web3_providers.get("ethereum")
        self.l2_web3 = web3_providers.get("optimism")

        if not self.l1_web3 or not self.l2_web3:
            raise ValueError("Providers L1 et L2 requis")

        # États internes
        self._active_bridges: Dict[str, Dict[str, Any]] = {}
        self._bridge_history: List[Dict[str, Any]] = []
        self._quote_cache: Dict[str, Tuple[float, OptimismBridgeQuote]] = {}
        self._contracts: Dict[str, Dict[str, Contract]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[OptimismBridgeProtocol, CircuitBreaker] = {
            protocol: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
            for protocol in OptimismBridgeProtocol
        }

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache
        self._gas_cache: Dict[str, Dict[str, Any]] = {}
        self._token_mapping_cache: Dict[str, Dict[str, str]] = {}

        # Charge les contrats
        self._load_contracts()

        # Charge les mappings de tokens
        self._load_token_mappings()

        logger.info("OptimismBridge initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats smart"""
        try:
            # Contrats L1
            l1_contracts = {}
            for name, contract_info in self.CONTRACTS.items():
                if "l1" in contract_info or name in ["native_bridge", "layerzero", "wormhole", "cctp"]:
                    address = contract_info.get("address") or contract_info.get("l1_cross_domain_messenger")
                    if address:
                        abi = self._get_contract_abi(name)
                        l1_contracts[name] = self.l1_web3.eth.contract(
                            address=to_checksum_address(address),
                            abi=abi,
                        )
            self._contracts["l1"] = l1_contracts

            # Contrats L2
            l2_contracts = {}
            for name, contract_info in self.CONTRACTS.items():
                if "l2" in contract_info:
                    address = contract_info.get("l2_cross_domain_messenger") or contract_info.get("l2_standard_bridge")
                    if address:
                        abi = self._get_contract_abi(name)
                        l2_contracts[name] = self.l2_web3.eth.contract(
                            address=to_checksum_address(address),
                            abi=abi,
                        )
            self._contracts["l2"] = l2_contracts

            logger.info(f"Contrats L1 chargés: {list(l1_contracts.keys())}")
            logger.info(f"Contrats L2 chargés: {list(l2_contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise BridgeError(f"Erreur de chargement des contrats: {e}")

    def _get_contract_abi(self, name: str) -> List[Dict[str, Any]]:
        """Obtient l'ABI pour un contrat spécifique"""
        if name == "native_bridge":
            return self.NATIVE_BRIDGE_ABI
        elif name in ["l1_cross_domain_messenger", "l2_cross_domain_messenger"]:
            return self.L2_MESSENGER_ABI
        else:
            # ABI générique pour les autres protocoles
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
        """Charge les mappings des tokens L1/L2"""
        # Mappings standard Optimism
        self._token_mapping_cache = {
            "l1_to_l2": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # ETH natif
                "USDC": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",  # USDC L1
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT L1
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI L1
                "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC L1
            },
            "l2_to_l1": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # ETH natif L2
                "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",  # USDC L2
                "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",  # USDT L2
                "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",  # DAI L2
                "WBTC": "0x68f180fcCe6836688e9084f035309E29Bf0A2095",  # WBTC L2
            }
        }

        # Ajout des mappings depuis la configuration
        if self.config.get("token_mappings"):
            user_mappings = self.config.get("token_mappings", {})
            for direction, tokens in user_mappings.items():
                if direction in self._token_mapping_cache:
                    self._token_mapping_cache[direction].update(tokens)

        logger.info(f"Token mappings chargés: {len(self._token_mapping_cache)} directions")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_quote(
        self,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: OptimismBridgeDirection,
        destination_address: str,
        protocol: Optional[OptimismBridgeProtocol] = None,
        **kwargs,
    ) -> OptimismBridgeQuote:
        """
        Obtient un devis pour un bridge Optimism

        Args:
            token_from: Token source
            token_to: Token destination
            amount: Montant à bridge
            direction: Direction du bridge
            destination_address: Adresse destination
            protocol: Protocole spécifique
            **kwargs: Arguments additionnels

        Returns:
            Devis de bridge
        """
        logger.info(
            f"Demande de devis Optimism: {amount} {token_from} -> {token_to} "
            f"({direction.value})"
        )

        # Vérification du cache
        cache_key = f"{token_from}:{token_to}:{amount}:{direction.value}:{protocol}"
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
                "optimism_bridge_quote",
                1,
                {
                    "protocol": protocol.value,
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
        request: OptimismBridgeRequest,
    ) -> Dict[str, Any]:
        """
        Exécute un bridge Optimism

        Args:
            request: Requête de bridge

        Returns:
            Résultat du bridge
        """
        bridge_id = f"op_bridge_{uuid.uuid4().hex[:12]}"
        logger.info(f"Exécution du bridge Optimism {bridge_id}")

        try:
            # 1. Obtention du devis
            quote = await self.get_quote(
                token_from=request.token_from,
                token_to=request.token_to,
                amount=request.amount,
                direction=request.direction,
                destination_address=request.destination_address,
                protocol=request.protocol,
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

            # 4. Exécution selon la direction
            if request.direction == OptimismBridgeDirection.DEPOSIT:
                result = await self._execute_deposit(request, quote, wallet)
            elif request.direction == OptimismBridgeDirection.WITHDRAWAL:
                result = await self._execute_withdrawal(request, quote, wallet)
            else:
                result = await self._execute_cross_chain(request, quote, wallet)

            # 5. Attente de la confirmation
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

            # Stockage
            self._active_bridges.pop(bridge_id, None)
            self._bridge_history.append(result)

            # Métriques
            self.metrics.record_increment(
                "optimism_bridge_completed",
                {
                    "protocol": request.protocol.value,
                    "direction": request.direction.value,
                    "token": request.token_from,
                },
            )

            logger.info(f"Bridge Optimism {bridge_id} terminé avec succès")
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
                "optimism_bridge_failed",
                {
                    "protocol": request.protocol.value,
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
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un dépôt L1 -> L2"""
        logger.info(f"Exécution du dépôt Optimism: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de dépôt
            tx_data = await self._build_deposit_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="ethereum",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="bridge_deposit",
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
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un retrait L2 -> L1"""
        logger.info(f"Exécution du retrait Optimism: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de retrait
            tx_data = await self._build_withdrawal_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="optimism",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="bridge_withdrawal",
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

    async def _execute_cross_chain(
        self,
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un bridge cross-chain"""
        logger.info(f"Exécution du bridge cross-chain Optimism: {request.amount}")

        # Utilisation d'un protocole spécifique
        protocol = request.protocol

        if protocol == OptimismBridgeProtocol.NATIVE:
            # Bridge natif
            return await self._execute_native_bridge(request, quote, wallet)
        elif protocol == OptimismBridgeProtocol.LAYERZERO:
            # LayerZero
            return await self._execute_layerzero(request, quote, wallet)
        elif protocol == OptimismBridgeProtocol.WORMHOLE:
            # Wormhole
            return await self._execute_wormhole(request, quote, wallet)
        else:
            # Protocole générique
            return await self._execute_generic_bridge(request, quote, wallet)

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_deposit_transaction(
        self,
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de dépôt"""
        # Récupération du contrat natif
        bridge_contract = self._contracts["l1"].get("native_bridge")
        if not bridge_contract:
            raise BridgeError("Contrat de bridge natif non trouvé")

        # Récupération des adresses des tokens
        token_mapping = self._token_mapping_cache.get("l1_to_l2", {})
        l1_token = token_mapping.get(request.token_from, request.token_from)

        # Valeur en wei
        amount_wei = int(request.amount * Decimal(1e18))

        # Construction selon le token
        if request.token_from == "ETH":
            # Dépôt d'ETH natif
            tx_data = bridge_contract.functions.depositETH(
                to_checksum_address(request.destination_address),
                amount_wei,
                b"",  # Données additionnelles
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "value": amount_wei,
                "gas": 200000,
                "gasPrice": await self._get_l1_gas_price(),
            })
        else:
            # Dépôt d'ERC20
            l2_token = await self._get_l2_token_address(l1_token, request.token_to)
            tx_data = bridge_contract.functions.depositERC20(
                to_checksum_address(l1_token),
                to_checksum_address(l2_token),
                amount_wei,
                200000,  # Gas limit L2
                b"",  # Données additionnelles
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 300000,
                "gasPrice": await self._get_l1_gas_price(),
            })

        return dict(tx_data)

    async def _build_withdrawal_transaction(
        self,
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de retrait"""
        # Récupération du contrat L2
        bridge_contract = self._contracts["l2"].get("native_bridge")
        if not bridge_contract:
            raise BridgeError("Contrat L2 non trouvé")

        # Récupération des tokens
        token_mapping = self._token_mapping_cache.get("l2_to_l1", {})
        l2_token = token_mapping.get(request.token_from, request.token_from)

        # Valeur en wei
        amount_wei = int(request.amount * Decimal(1e18))

        if request.token_from == "ETH":
            # Retrait d'ETH natif (via messenger)
            messenger_contract = self._contracts["l2"].get("l2_cross_domain_messenger")
            if not messenger_contract:
                raise BridgeError("Messenger L2 non trouvé")

            # Message pour le retrait
            message = await self._encode_withdrawal_message(
                request.destination_address,
                amount_wei,
            )

            tx_data = messenger_contract.functions.sendMessage(
                to_checksum_address(request.destination_address),
                message,
                200000,  # Gas limit L1
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 300000,
                "gasPrice": await self._get_l2_gas_price(),
            })
        else:
            # Retrait d'ERC20
            l1_token = await self._get_l1_token_address(l2_token, request.token_to)
            tx_data = bridge_contract.functions.withdrawERC20(
                to_checksum_address(l1_token),
                to_checksum_address(l2_token),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 300000,
                "gasPrice": await self._get_l2_gas_price(),
            })

        return dict(tx_data)

    # ============================================================
    # MÉTHODES DE VÉRIFICATION ET CONFIRMATION
    # ============================================================

    async def _wait_for_confirmation(
        self,
        bridge_id: str,
        tx_hash: Optional[str],
        direction: OptimismBridgeDirection,
        timeout: int = 3600,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'un bridge"""
        if not tx_hash:
            raise BridgeError("Hash de transaction manquant")

        logger.info(f"Attente de confirmation pour {bridge_id}: {tx_hash}")

        start_time = time.time()
        provider = self.l1_web3 if direction == OptimismBridgeDirection.DEPOSIT else self.l2_web3

        while time.time() - start_time < timeout:
            try:
                receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))
                if receipt:
                    status = receipt.get("status")
                    if status == 1:
                        # Vérification du statut L2 pour les dépôts
                        if direction == OptimismBridgeDirection.DEPOSIT:
                            l2_receipt = await self._wait_for_l2_transaction(
                                tx_hash, timeout - (time.time() - start_time)
                            )
                            if l2_receipt:
                                return {
                                    "amount_received": str(l2_receipt.get("amount", 0)),
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
    # MÉTHODES DE CALCUL DE COÛTS
    # ============================================================

    async def _estimate_l1_gas(self, amount: Decimal, direction: OptimismBridgeDirection) -> Decimal:
        """Estime les frais L1 pour un bridge"""
        try:
            # Estimation de base
            base_gas = 100000 if direction == OptimismBridgeDirection.DEPOSIT else 200000

            # Obtention du prix du gaz L1
            gas_price = await self._get_l1_gas_price()
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            # Frais L1
            l1_fees = Decimal(str(base_gas)) * gas_price_decimal

            return l1_fees

        except Exception as e:
            logger.warning(f"Erreur d'estimation L1: {e}")
            return Decimal("0.0005")

    async def _estimate_l2_gas(self, amount: Decimal, direction: OptimismBridgeDirection) -> Decimal:
        """Estime les frais L2 pour un bridge"""
        try:
            # Estimation de base
            base_gas = 50000 if direction == OptimismBridgeDirection.DEPOSIT else 80000

            # Obtention du prix du gaz L2
            gas_price = await self._get_l2_gas_price()
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            # Frais L2
            l2_fees = Decimal(str(base_gas)) * gas_price_decimal

            return l2_fees

        except Exception as e:
            logger.warning(f"Erreur d'estimation L2: {e}")
            return Decimal("0.0001")

    async def _get_l1_gas_price(self) -> int:
        """Obtient le prix du gaz L1"""
        try:
            return await self.l1_web3.eth.gas_price
        except Exception:
            return 50000000000  # 50 Gwei par défaut

    async def _get_l2_gas_price(self) -> int:
        """Obtient le prix du gaz L2"""
        try:
            return await self.l2_web3.eth.gas_price
        except Exception:
            return 100000000  # 0.1 Gwei par défaut

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_balance(
        self,
        token: str,
        address: str,
        direction: OptimismBridgeDirection,
    ) -> Decimal:
        """Obtient le solde d'un token"""
        provider = self.l1_web3 if direction == OptimismBridgeDirection.DEPOSIT else self.l2_web3

        try:
            if token == "ETH":
                balance = await provider.eth.get_balance(address)
                return Decimal(str(balance)) / Decimal(1e18)

            # Token ERC20
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

    async def _get_l2_token_address(self, l1_token: str, token_symbol: str) -> str:
        """Obtient l'adresse L2 d'un token L1"""
        # Vérifier le cache
        cache_key = f"{l1_token}:{token_symbol}"
        if cache_key in self._token_mapping_cache.get("l2_tokens", {}):
            return self._token_mapping_cache["l2_tokens"][cache_key]

        # Mapping standard
        l2_mapping = self._token_mapping_cache.get("l2_to_l1", {})
        for l2_addr, l1_addr in l2_mapping.items():
            if l1_addr.lower() == l1_token.lower():
                return l2_addr

        # Si non trouvé, retourner l'adresse L1
        return l1_token

    async def _get_l1_token_address(self, l2_token: str, token_symbol: str) -> str:
        """Obtient l'adresse L1 d'un token L2"""
        # Mapping standard
        l1_mapping = self._token_mapping_cache.get("l1_to_l2", {})
        for l1_addr, l2_addr in l1_mapping.items():
            if l2_addr.lower() == l2_token.lower():
                return l1_addr

        return l2_token

    async def _encode_withdrawal_message(self, to_address: str, amount: int) -> bytes:
        """Encode le message de retrait"""
        # Standard ABI encode
        encoded = encode_single(
            "(address,uint256)",
            (to_checksum_address(to_address), amount),
        )
        return encoded

    async def _get_deposit_info(self, l1_tx_hash: str) -> Dict[str, Any]:
        """Récupère les informations d'un dépôt"""
        # Simulé - dans la réalité, on interrogeait l'indexeur Optimism
        return {"status": "pending"}

    async def _get_withdrawal_info(self, l2_tx_hash: str) -> Dict[str, Any]:
        """Récupère les informations d'un retrait"""
        return {"status": "pending"}

    # ============================================================
    # MÉTHODES DE PROTOCOLES SPÉCIFIQUES
    # ============================================================

    async def _execute_native_bridge(
        self,
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute le bridge natif Optimism"""
        # Le bridge natif est géré via les transactions de dépôt/retrait
        if request.direction == OptimismBridgeDirection.CROSS_CHAIN:
            # Pour cross-chain, on utilise le bridge natif
            return await self._execute_deposit(request, quote, wallet)
        else:
            return await self._execute_deposit(request, quote, wallet)

    async def _execute_layerzero(
        self,
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute LayerZero sur Optimism"""
        logger.info("Exécution de LayerZero bridge")

        # Récupération du contrat LayerZero
        layerzero_contract = self._contracts["l2"].get("layerzero")
        if not layerzero_contract:
            raise BridgeError("Contrat LayerZero non trouvé")

        # Construction de la transaction
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

        # Envoi de la transaction
        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="optimism",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="bridge_layerzero",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "layerzero",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_wormhole(
        self,
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Wormhole sur Optimism"""
        logger.info("Exécution de Wormhole bridge")

        # Récupération du contrat Wormhole
        wormhole_contract = self._contracts["l2"].get("wormhole")
        if not wormhole_contract:
            raise BridgeError("Contrat Wormhole non trouvé")

        # Récupération de l'émulateur
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
            chain="optimism",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="bridge_wormhole",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "wormhole",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_generic_bridge(
        self,
        request: OptimismBridgeRequest,
        quote: OptimismBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un protocole générique"""
        logger.info("Exécution du bridge générique")

        # Utilisation du contrat générique
        generic_contract = self._contracts["l2"].get(request.protocol.value)
        if not generic_contract:
            raise BridgeError(f"Contrat {request.protocol.value} non trouvé")

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
            chain="optimism",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="bridge_generic",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": request.protocol.value,
            "amount": str(request.amount),
            "token": request.token_from,
        }

    # ============================================================
    # MÉTHODES DE SÉLECTION ET DEVIATION
    # ============================================================

    async def _select_best_protocol(
        self,
        token_from: str,
        token_to: str,
        direction: OptimismBridgeDirection,
    ) -> OptimismBridgeProtocol:
        """Sélectionne le meilleur protocole"""
        available_protocols = []

        for protocol in OptimismBridgeProtocol:
            if not self.circuit_breakers[protocol].is_available():
                continue

            # Vérification du support
            if await self._is_protocol_supported(protocol, token_from, token_to, direction):
                available_protocols.append(protocol)

        if not available_protocols:
            # Fallback sur le bridge natif
            return OptimismBridgeProtocol.NATIVE

        # Score des protocoles
        scores = []
        for protocol in available_protocols:
            score = await self._score_protocol(protocol, token_from, token_to, direction)
            scores.append((score, protocol))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]

    async def _select_fallback_protocol(
        self,
        failed_protocol: OptimismBridgeProtocol,
        token_from: str,
        token_to: str,
        direction: OptimismBridgeDirection,
    ) -> Optional[OptimismBridgeProtocol]:
        """Sélectionne un protocole de fallback"""
        for protocol in OptimismBridgeProtocol:
            if protocol == failed_protocol:
                continue
            if not self.circuit_breakers[protocol].is_available():
                continue
            if await self._is_protocol_supported(protocol, token_from, token_to, direction):
                return protocol
        return None

    async def _score_protocol(
        self,
        protocol: OptimismBridgeProtocol,
        token_from: str,
        token_to: str,
        direction: OptimismBridgeDirection,
    ) -> float:
        """Calcule un score pour un protocole"""
        try:
            # Génération d'un devis pour évaluation
            quote = await self._generate_quote(
                protocol=protocol,
                token_from=token_from,
                token_to=token_to,
                amount=Decimal("1"),
                direction=direction,
                destination_address="0x0000000000000000000000000000000000000000",
                simulate=True,
            )

            # Score basé sur les coûts, le temps et la confiance
            cost_score = 1.0 - float(quote.total_fees / Decimal("0.01"))
            time_score = 1.0 - (quote.estimated_time / 1800.0)
            confidence_score = quote.confidence

            return cost_score * 0.4 + time_score * 0.3 + confidence_score * 0.3

        except Exception:
            return 0.0

    async def _is_protocol_supported(
        self,
        protocol: OptimismBridgeProtocol,
        token_from: str,
        token_to: str,
        direction: OptimismBridgeDirection,
    ) -> bool:
        """Vérifie si un protocole supporte la requête"""
        # Vérification basique
        supported_tokens = self.config.get("protocol_tokens", {}).get(protocol.value, [])
        if supported_tokens and token_from not in supported_tokens:
            return False

        # Vérification de la direction
        supported_directions = self.config.get("protocol_directions", {}).get(protocol.value, [])
        if supported_directions and direction.value not in supported_directions:
            return False

        return True

    # ============================================================
    # MÉTHODES DE GÉNÉRATION DE DEVIS
    # ============================================================

    async def _generate_quote(
        self,
        protocol: OptimismBridgeProtocol,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: OptimismBridgeDirection,
        destination_address: str,
        **kwargs,
    ) -> OptimismBridgeQuote:
        """Génère un devis pour un protocole spécifique"""
        try:
            # Estimation des frais
            l1_gas = await self._estimate_l1_gas(amount, direction)
            l2_gas = await self._estimate_l2_gas(amount, direction)
            bridge_fees = await self._estimate_bridge_fees(
                protocol, token_from, amount, direction
            )

            total_fees = l1_gas + l2_gas + bridge_fees

            # Estimation du temps
            estimated_time = await self._estimate_time(protocol, direction)

            # Niveau de confiance
            confidence = self._calculate_confidence(protocol, amount)

            # Slippage
            slippage = kwargs.get("slippage_tolerance", Decimal("0.005"))

            # Montant minimum reçu
            min_amount_received = amount * (1 - float(slippage))

            return OptimismBridgeQuote(
                quote_id=f"op_q_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
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
                l1_security_check=True,
                l2_security_check=True,
                quote_data=kwargs,
            )

        except Exception as e:
            logger.error(f"Erreur de génération de devis pour {protocol.value}: {e}")
            raise

    async def _estimate_bridge_fees(
        self,
        protocol: OptimismBridgeProtocol,
        token: str,
        amount: Decimal,
        direction: OptimismBridgeDirection,
    ) -> Decimal:
        """Estime les frais de bridge spécifiques"""
        # Frais par protocole
        base_fees = {
            OptimismBridgeProtocol.NATIVE: Decimal("0.0001"),
            OptimismBridgeProtocol.LAYERZERO: Decimal("0.0005"),
            OptimismBridgeProtocol.WORMHOLE: Decimal("0.0003"),
            OptimismBridgeProtocol.CCTP: Decimal("0.0001"),
            OptimismBridgeProtocol.ACROSS: Decimal("0.0004"),
            OptimismBridgeProtocol.HOP: Decimal("0.0006"),
            OptimismBridgeProtocol.SYNAPSE: Decimal("0.0005"),
            OptimismBridgeProtocol.STARGATE: Decimal("0.0004"),
            OptimismBridgeProtocol.CONNEXT: Decimal("0.0007"),
        }.get(protocol, Decimal("0.0005"))

        # Frais variables
        variable_fees = amount * Decimal("0.0003")

        # Ajustement direction
        direction_multiplier = 1.0 if direction == OptimismBridgeDirection.DEPOSIT else 1.5

        return (base_fees + variable_fees) * Decimal(str(direction_multiplier))

    async def _estimate_time(
        self,
        protocol: OptimismBridgeProtocol,
        direction: OptimismBridgeDirection,
    ) -> int:
        """Estime le temps de bridge en secondes"""
        base_time = {
            OptimismBridgeProtocol.NATIVE: 120,
            OptimismBridgeProtocol.LAYERZERO: 100,
            OptimismBridgeProtocol.WORMHOLE: 80,
            OptimismBridgeProtocol.CCTP: 60,
            OptimismBridgeProtocol.ACROSS: 130,
            OptimismBridgeProtocol.HOP: 90,
            OptimismBridgeProtocol.SYNAPSE: 95,
            OptimismBridgeProtocol.STARGATE: 70,
            OptimismBridgeProtocol.CONNEXT: 110,
        }.get(protocol, 120)

        # Les retraits sont plus lents
        if direction == OptimismBridgeDirection.WITHDRAWAL:
            base_time *= 3  # ~7 jours pour un retrait Optimism

        return base_time

    def _calculate_confidence(
        self,
        protocol: OptimismBridgeProtocol,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            OptimismBridgeProtocol.NATIVE: 0.99,
            OptimismBridgeProtocol.LAYERZERO: 0.95,
            OptimismBridgeProtocol.WORMHOLE: 0.97,
            OptimismBridgeProtocol.CCTP: 0.98,
            OptimismBridgeProtocol.ACROSS: 0.90,
            OptimismBridgeProtocol.HOP: 0.88,
            OptimismBridgeProtocol.SYNAPSE: 0.87,
            OptimismBridgeProtocol.STARGATE: 0.93,
            OptimismBridgeProtocol.CONNEXT: 0.85,
        }.get(protocol, 0.90)

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
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources OptimismBridge...")

        # Nettoyage des caches
        self._quote_cache.clear()
        self._gas_cache.clear()
        self._token_mapping_cache.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_optimism_bridge(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Web3],
    bridge_manager: BridgeManager,
    transaction_manager: BridgeTransactionManager,
    **kwargs,
) -> OptimismBridge:
    """
    Crée une instance de OptimismBridge

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        bridge_manager: Gestionnaire de bridges
        transaction_manager: Gestionnaire de transactions
        **kwargs: Arguments additionnels

    Returns:
        Instance de OptimismBridge
    """
    return OptimismBridge(
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
    """Exemple d'utilisation du bridge Optimism"""
    # Configuration
    config = {
        "protocol_tokens": {
            "native": ["ETH", "USDC", "USDT", "DAI"],
            "layerzero": ["ETH", "USDC", "USDT"],
            "wormhole": ["ETH", "USDC", "WBTC"],
        },
        "protocol_directions": {
            "native": ["deposit", "withdrawal"],
            "layerzero": ["cross_chain"],
            "wormhole": ["cross_chain"],
        },
        "token_mappings": {
            "l1_to_l2": {
                "USDC": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
            },
            "l2_to_l1": {
                "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
            },
        },
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "optimism": Web3(Web3.HTTPProvider("https://mainnet.optimism.io")),
    }

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
    bridge = create_optimism_bridge(
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
        direction=OptimismBridgeDirection.DEPOSIT,
        destination_address="0x...",
        protocol=OptimismBridgeProtocol.NATIVE,
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un bridge
    request = OptimismBridgeRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol=OptimismBridgeProtocol.NATIVE,
        direction=OptimismBridgeDirection.DEPOSIT,
        token_from="ETH",
        token_to="ETH",
        amount=Decimal("0.01"),
        source_address="0x...",
        destination_address="0x...",
    )

    result = await bridge.execute_bridge(request)
    print(f"Résultat: {result}")

    # Nettoyage
    await bridge.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

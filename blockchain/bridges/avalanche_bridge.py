# blockchain/bridges/avalanche_bridge.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Bridge Avalanche (AVAX)

Ce module implémente un système complet de bridge pour la blockchain Avalanche
avec support des bridges officiels (Avalanche Bridge), des protocoles tiers,
et des mécanismes de sécurité avancés.

Fonctionnalités principales:
- Support du Avalanche Bridge officiel (AB)
- Support du bridge Avalanche-Ethereum (AEB)
- Support des protocoles tiers (LayerZero, Wormhole, etc.)
- Gestion des tokens ARC-20
- Optimisation des frais en AVAX
- Support des tokens natifs (AVAX, USDC, etc.)
- Gestion des mappings de tokens Avalanche
- Surveillance en temps réel des bridges
- Mécanismes de fallback
- Support des cross-chain vers Ethereum et autres
- Monitoring des transactions cross-chain
- Support des sous-réseaux (Subnets)
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
    from ..wallets.avalanche_wallet import AvalancheWallet
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
    from ..wallets.avalanche_wallet import AvalancheWallet
    from ..security.encryption import EncryptionManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class AvalancheBridgeProtocol(Enum):
    """Protocoles de bridge supportés sur Avalanche"""
    AVALANCHE_BRIDGE = "avalanche_bridge"  # Bridge officiel
    AVALANCHE_ETHEREUM = "avalanche_ethereum"  # Bridge Avalanche-Ethereum
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


class AvalancheBridgeDirection(Enum):
    """Direction du bridge"""
    DEPOSIT = "deposit"  # Vers Avalanche
    WITHDRAWAL = "withdrawal"  # Depuis Avalanche
    CROSS_CHAIN = "cross_chain"


class AvalancheTokenType(Enum):
    """Types de tokens Avalanche"""
    ARC20 = "arc20"  # Token standard ARC-20
    NATIVE = "native"  # AVAX natif
    WETH = "weth"  # Wrapped ETH sur Avalanche
    ERC20 = "erc20"  # Token ERC-20 bridge


@dataclass
class AvalancheBridgeQuote:
    """Devis de bridge Avalanche"""
    quote_id: str
    protocol: AvalancheBridgeProtocol
    direction: AvalancheBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    gas_estimate: Decimal  # Frais en AVAX
    bridge_fees: Decimal
    total_fees: Decimal
    estimated_time: int  # secondes
    min_amount_received: Decimal
    max_slippage: Decimal
    confidence: float
    avalanche_confirmations_required: int
    subnet_id: Optional[str] = None
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
            "gas_estimate": str(self.gas_estimate),
            "bridge_fees": str(self.bridge_fees),
            "total_fees": str(self.total_fees),
            "estimated_time": self.estimated_time,
            "min_amount_received": str(self.min_amount_received),
            "max_slippage": str(self.max_slippage),
            "confidence": self.confidence,
            "avalanche_confirmations_required": self.avalanche_confirmations_required,
            "subnet_id": self.subnet_id,
        }


@dataclass
class AvalancheBridgeRequest:
    """Requête de bridge Avalanche"""
    request_id: str
    protocol: AvalancheBridgeProtocol
    direction: AvalancheBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    destination_chain: str = "ethereum"
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    use_fallback: bool = True
    max_avax_fee: Optional[Decimal] = None
    priority_fee: Optional[int] = None
    subnet_id: Optional[str] = None
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
            "destination_chain": self.destination_chain,
            "slippage_tolerance": str(self.slippage_tolerance),
            "deadline": self.deadline,
            "use_fallback": self.use_fallback,
            "max_avax_fee": str(self.max_avax_fee) if self.max_avax_fee else None,
            "priority_fee": self.priority_fee,
            "subnet_id": self.subnet_id,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class AvalancheBridge(BaseBridge):
    """
    Bridge avancé pour Avalanche avec support multi-protocoles
    """

    # Adresses des contrats Avalanche C-Chain (Mainnet)
    CONTRACTS = {
        "avalanche_bridge": {
            "bridge": "0xE3Cd3eF29E1Bc35BC095b059CE491aC30d16A17c",
            "token": "0xE3Cd3eF29E1Bc35BC095b059CE491aC30d16A17c",
            "wrapped_avax": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",
        },
        "avalanche_ethereum": {
            "bridge": "0xE3Cd3eF29E1Bc35BC095b059CE491aC30d16A17c",
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
    }

    # Token mappings Avalanche C-Chain
    TOKEN_MAPPINGS = {
        "AVAX": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # AVAX natif
        "USDC": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        "USDT": "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7",
        "DAI": "0xd586E7F844cEa2F87f50152665BCbc2C279D8d70",
        "WETH": "0x49D5c2BdFfAC6AE2BFdb6640F4F80f226db10eAB",
        "WBTC": "0x50b7545627a5162F82A992c33b87aDc75187B218",
        "LINK": "0x5947BB275c521040051D82396192181b413227A3",
        "MIM": "0x130966628846BFd36ff31a822705796e8cb8C18D",
        "JOE": "0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd",
        "QI": "0x8729438EB15e2C8B576fCc6AeCdA6A148776C0F5",
    }

    # Token mappings cross-chain
    CROSS_CHAIN_MAPPINGS = {
        "ethereum": {
            "AVAX": "0x85f1387BEE1DEb063BD631D09E5C7beC5a164FeD",
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        },
        "polygon": {
            "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        },
        "arbitrum": {
            "USDC": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
            "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        },
        "optimism": {
            "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
            "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
        },
        "bsc": {
            "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "USDT": "0x55d398326f99059fF775485246999027B3197955",
        },
    }

    # ABIs des contrats
    AVALANCHE_BRIDGE_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
                {"name": "chainId", "type": "uint256"},
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
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "depositAVAX",
            "outputs": [],
            "payable": True,
            "stateMutability": "payable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "withdrawAVAX",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    WORMHOLE_ABI = [
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

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        avalanche_provider: Web3,
        bridge_manager: BridgeManager,
        transaction_manager: BridgeTransactionManager,
        validator: Optional[BridgeValidator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le bridge Avalanche

        Args:
            config: Configuration du bridge
            wallet_manager: Gestionnaire de wallets
            avalanche_provider: Provider Web3 pour Avalanche C-Chain
            bridge_manager: Gestionnaire de bridges
            transaction_manager: Gestionnaire de transactions
            validator: Validateur de bridge
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager)

        self.avalanche_provider = avalanche_provider
        self.bridge_manager = bridge_manager
        self.transaction_manager = transaction_manager
        self.validator = validator
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # Ajout du middleware PoA pour Avalanche
        try:
            self.avalanche_provider.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception:
            pass

        # États internes
        self._active_bridges: Dict[str, Dict[str, Any]] = {}
        self._bridge_history: List[Dict[str, Any]] = []
        self._quote_cache: Dict[str, Tuple[float, AvalancheBridgeQuote]] = {}
        self._contracts: Dict[str, Contract] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[AvalancheBridgeProtocol, CircuitBreaker] = {
            protocol: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
            for protocol in AvalancheBridgeProtocol
        }

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache
        self._gas_cache: Dict[str, Dict[str, Any]] = {}
        self._token_mapping_cache: Dict[str, Dict[str, str]] = {}

        # Sous-réseaux supportés
        self._supported_subnets = set(config.get("supported_subnets", []))

        # Charge les contrats
        self._load_contracts()

        # Charge les mappings de tokens
        self._load_token_mappings()

        logger.info("AvalancheBridge initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats smart"""
        try:
            for name, contract_info in self.CONTRACTS.items():
                if name == "avalanche_bridge" or name == "avalanche_ethereum":
                    abi = self.AVALANCHE_BRIDGE_ABI
                elif name == "wormhole":
                    abi = self.WORMHOLE_ABI
                else:
                    abi = self._get_generic_abi()

                address = contract_info.get("bridge") or contract_info.get("endpoint") or contract_info.get("router")
                if address:
                    self._contracts[name] = self.avalanche_provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=abi,
                    )

            logger.info(f"Contrats chargés: {list(self._contracts.keys())}")

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
        """Charge les mappings des tokens Avalanche"""
        # Mappings Avalanche C-Chain
        self._token_mapping_cache["avalanche"] = self.TOKEN_MAPPINGS

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
        direction: AvalancheBridgeDirection,
        destination_chain: str = "ethereum",
        destination_address: str = "",
        protocol: Optional[AvalancheBridgeProtocol] = None,
        subnet_id: Optional[str] = None,
        **kwargs,
    ) -> AvalancheBridgeQuote:
        """
        Obtient un devis pour un bridge Avalanche

        Args:
            token_from: Token source
            token_to: Token destination
            amount: Montant à bridge
            direction: Direction du bridge
            destination_chain: Chaîne destination (pour cross-chain)
            destination_address: Adresse destination
            protocol: Protocole spécifique
            subnet_id: ID du sous-réseau (optionnel)
            **kwargs: Arguments additionnels

        Returns:
            Devis de bridge
        """
        logger.info(
            f"Demande de devis Avalanche: {amount} {token_from} -> {token_to} "
            f"({direction.value})"
        )

        # Vérification du cache
        cache_key = f"{token_from}:{token_to}:{amount}:{direction.value}:{destination_chain}:{protocol}:{subnet_id}"
        if cache_key in self._quote_cache:
            cached_time, quote = self._quote_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Devis retourné du cache")
                return quote

        try:
            # Sélection du protocole
            if protocol is None:
                protocol = await self._select_best_protocol(
                    token_from, token_to, direction, destination_chain, subnet_id
                )

            # Vérification du circuit breaker
            if not self.circuit_breakers[protocol].is_available():
                logger.warning(f"Circuit breaker ouvert pour {protocol.value}")
                fallback_protocol = await self._select_fallback_protocol(
                    protocol, token_from, token_to, direction, destination_chain, subnet_id
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
                destination_chain=destination_chain,
                destination_address=destination_address,
                subnet_id=subnet_id,
                **kwargs,
            )

            # Mise en cache
            self._quote_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "avalanche_bridge_quote",
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
        request: AvalancheBridgeRequest,
    ) -> Dict[str, Any]:
        """
        Exécute un bridge Avalanche

        Args:
            request: Requête de bridge

        Returns:
            Résultat du bridge
        """
        bridge_id = f"avax_bridge_{uuid.uuid4().hex[:12]}"
        logger.info(f"Exécution du bridge Avalanche {bridge_id}")

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
                subnet_id=request.subnet_id,
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
            )
            if balance < request.amount:
                raise BridgeError(
                    f"Solde insuffisant: {balance} < {request.amount}"
                )

            # 4. Approval du token si nécessaire
            if request.token_from != "AVAX":
                await self._approve_token(
                    token=request.token_from,
                    amount=request.amount,
                    wallet=wallet,
                    protocol=request.protocol,
                )

            # 5. Exécution selon la direction
            if request.direction == AvalancheBridgeDirection.DEPOSIT:
                result = await self._execute_deposit(request, quote, wallet)
            elif request.direction == AvalancheBridgeDirection.WITHDRAWAL:
                result = await self._execute_withdrawal(request, quote, wallet)
            else:
                result = await self._execute_cross_chain(request, quote, wallet)

            # 6. Attente de la confirmation
            final_result = await self._wait_for_confirmation(
                bridge_id=bridge_id,
                tx_hash=result.get("tx_hash"),
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
                "avalanche_bridge_completed",
                {
                    "protocol": request.protocol.value,
                    "direction": request.direction.value,
                    "token": request.token_from,
                },
            )

            logger.info(f"Bridge Avalanche {bridge_id} terminé avec succès")
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
                "avalanche_bridge_failed",
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
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un dépôt vers Avalanche"""
        logger.info(f"Exécution du dépôt Avalanche: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de dépôt
            tx_data = await self._build_deposit_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="avalanche",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="avalanche_deposit",
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
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un retrait depuis Avalanche"""
        logger.info(f"Exécution du retrait Avalanche: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de retrait
            tx_data = await self._build_withdrawal_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="avalanche",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="avalanche_withdrawal",
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
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un bridge cross-chain depuis Avalanche"""
        logger.info(f"Exécution du bridge cross-chain Avalanche: {request.amount}")

        protocol = request.protocol

        if protocol == AvalancheBridgeProtocol.AVALANCHE_BRIDGE:
            return await self._execute_avalanche_bridge(request, quote, wallet)
        elif protocol == AvalancheBridgeProtocol.AVALANCHE_ETHEREUM:
            return await self._execute_avalanche_ethereum_bridge(request, quote, wallet)
        elif protocol == AvalancheBridgeProtocol.LAYERZERO:
            return await self._execute_layerzero(request, quote, wallet)
        elif protocol == AvalancheBridgeProtocol.WORMHOLE:
            return await self._execute_wormhole(request, quote, wallet)
        elif protocol == AvalancheBridgeProtocol.MULTICHAIN:
            return await self._execute_multichain(request, quote, wallet)
        else:
            return await self._execute_generic_bridge(request, quote, wallet)

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_deposit_transaction(
        self,
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de dépôt Avalanche"""
        # Récupération du contrat approprié
        if request.protocol == AvalancheBridgeProtocol.AVALANCHE_BRIDGE:
            contract = self._contracts.get("avalanche_bridge")
        else:
            contract = self._contracts.get(request.protocol.value)

        if not contract:
            raise BridgeError("Contrat de bridge non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["avalanche"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        # Valeur en wei (18 décimales pour AVAX, 6 pour USDC, etc.)
        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        if request.token_from == "AVAX":
            # Dépôt d'AVAX natif
            tx_data = contract.functions.depositAVAX(
                to_checksum_address(request.destination_address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "value": amount_wei,
                "gas": 200000,
                "gasPrice": await self._get_avalanche_gas_price(),
            })
        else:
            # Dépôt de token ARC-20
            tx_data = contract.functions.bridge(
                to_checksum_address(token_address),
                amount_wei,
                to_checksum_address(request.destination_address),
                self._get_chain_id(request.destination_chain),
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 300000,
                "gasPrice": await self._get_avalanche_gas_price(),
            })

        return dict(tx_data)

    async def _build_withdrawal_transaction(
        self,
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de retrait Avalanche"""
        contract = self._contracts.get("avalanche_bridge")
        if not contract:
            raise BridgeError("Contrat de bridge non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["avalanche"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        if request.token_from == "AVAX":
            # Retrait d'AVAX
            tx_data = contract.functions.withdrawAVAX(
                to_checksum_address(request.destination_address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 200000,
                "gasPrice": await self._get_avalanche_gas_price(),
            })
        else:
            # Retrait de token
            tx_data = contract.functions.bridge(
                to_checksum_address(token_address),
                amount_wei,
                to_checksum_address(request.destination_address),
                self._get_chain_id(request.destination_chain),
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 300000,
                "gasPrice": await self._get_avalanche_gas_price(),
            })

        return dict(tx_data)

    # ============================================================
    # MÉTHODES DE PROTOCOLES SPÉCIFIQUES
    # ============================================================

    async def _execute_avalanche_bridge(
        self,
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute le bridge officiel Avalanche"""
        logger.info("Exécution du Avalanche Bridge")

        tx_data = await self._build_deposit_transaction(request, quote)

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="avalanche",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="avalanche_bridge",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "avalanche_bridge",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_avalanche_ethereum_bridge(
        self,
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute le bridge Avalanche-Ethereum"""
        logger.info("Exécution du Avalanche-Ethereum Bridge")

        contract = self._contracts.get("avalanche_ethereum")
        if not contract:
            raise BridgeError("Contrat Avalanche-Ethereum non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["avalanche"]
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
            "gasPrice": await self._get_avalanche_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="avalanche",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="avalanche_ethereum_bridge",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "avalanche_ethereum",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_layerzero(
        self,
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute LayerZero sur Avalanche"""
        logger.info("Exécution de LayerZero bridge sur Avalanche")

        contract = self._contracts.get("layerzero")
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
            "gasPrice": await self._get_avalanche_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="avalanche",
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
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Wormhole sur Avalanche"""
        logger.info("Exécution de Wormhole bridge sur Avalanche")

        contract = self._contracts.get("wormhole")
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
            "gasPrice": await self._get_avalanche_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="avalanche",
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
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Multichain sur Avalanche"""
        logger.info("Exécution de Multichain bridge sur Avalanche")

        contract = self._contracts.get("multichain")
        if not contract:
            raise BridgeError("Contrat Multichain non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["avalanche"]
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
            "gasPrice": await self._get_avalanche_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="avalanche",
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

    async def _execute_generic_bridge(
        self,
        request: AvalancheBridgeRequest,
        quote: AvalancheBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un protocole générique"""
        logger.info("Exécution du bridge générique sur Avalanche")

        contract_name = request.protocol.value
        contract = self._contracts.get(contract_name)
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
            "gasPrice": await self._get_avalanche_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="avalanche",
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
        protocol: AvalancheBridgeProtocol,
    ) -> bool:
        """Approuve un token pour le bridge"""
        try:
            # Récupération du spender
            spender = self._get_spender_address(protocol)

            # Vérification de l'allowance
            allowance = await self._get_allowance(token, wallet.address, spender)

            if allowance >= amount:
                logger.debug(f"Allowance suffisante: {allowance} >= {amount}")
                return True

            # Construction de la transaction d'approbation
            token_mapping = self._token_mapping_cache["avalanche"]
            token_address = token_mapping.get(token, token)

            token_contract = self.avalanche_provider.eth.contract(
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
                "nonce": await self.avalanche_provider.eth.get_transaction_count(wallet.address),
                "gas": 100000,
                "gasPrice": await self._get_avalanche_gas_price(),
            })

            # Envoi de la transaction
            signed_tx = wallet.sign_transaction(approve_tx)
            tx_hash = await self.avalanche_provider.eth.send_raw_transaction(signed_tx)

            # Attente de la confirmation
            receipt = await self._wait_for_transaction(tx_hash)
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
    ) -> Decimal:
        """Obtient l'allowance d'un token"""
        try:
            token_mapping = self._token_mapping_cache["avalanche"]
            token_address = token_mapping.get(token, token)

            token_contract = self.avalanche_provider.eth.contract(
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
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction Avalanche"""
        if not tx_hash:
            raise BridgeError("Hash de transaction manquant")

        logger.info(f"Attente de confirmation pour {bridge_id}: {tx_hash}")

        start_time = time.time()
        provider = self.avalanche_provider

        while time.time() - start_time < timeout:
            try:
                receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))
                if receipt:
                    status = receipt.get("status")
                    if status == 1:
                        confirmations = await self._get_confirmations(tx_hash)
                        if confirmations >= 12:
                            return {
                                "amount_received": "0",  # À extraire des logs
                                "confirmations": confirmations,
                            }
                    else:
                        raise BridgeError("Transaction reverted")

            except Exception as e:
                logger.warning(f"Erreur de vérification: {e}")

            await asyncio.sleep(5)

        raise BridgeError(f"Timeout de confirmation: {tx_hash}")

    async def _get_confirmations(self, tx_hash: str) -> int:
        """Obtient le nombre de confirmations"""
        try:
            receipt = await self.avalanche_provider.eth.get_transaction_receipt(HexBytes(tx_hash))
            if not receipt:
                return 0

            block_number = receipt.get("blockNumber", 0)
            current_block = await self.avalanche_provider.eth.block_number

            return current_block - block_number + 1

        except Exception:
            return 0

    async def _wait_for_transaction(
        self,
        tx_hash: HexBytes,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                receipt = await self.avalanche_provider.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return dict(receipt)
            except Exception:
                pass
            await asyncio.sleep(2)

        raise BridgeError(f"Timeout de transaction: {tx_hash.hex()}")

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _generate_quote(
        self,
        protocol: AvalancheBridgeProtocol,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: AvalancheBridgeDirection,
        destination_chain: str,
        destination_address: str,
        subnet_id: Optional[str] = None,
        **kwargs,
    ) -> AvalancheBridgeQuote:
        """Génère un devis pour un protocole spécifique"""
        try:
            # Estimation des frais
            gas_estimate = await self._estimate_gas(protocol, amount, direction)
            bridge_fees = await self._estimate_bridge_fees(
                protocol, token_from, amount, direction
            )
            total_fees = gas_estimate + bridge_fees

            # Estimation du temps
            estimated_time = await self._estimate_time(protocol, direction)

            # Confirmations Avalanche
            confirmations = 12 if direction == AvalancheBridgeDirection.DEPOSIT else 15

            # Niveau de confiance
            confidence = self._calculate_confidence(protocol, amount)

            # Slippage
            slippage = kwargs.get("slippage_tolerance", Decimal("0.005"))

            # Montant minimum reçu
            min_amount_received = amount * (1 - float(slippage))

            # Vérification du sous-réseau
            if subnet_id and self._supported_subnets and subnet_id not in self._supported_subnets:
                logger.warning(f"Sous-réseau {subnet_id} non supporté, utilisation du réseau principal")

            return AvalancheBridgeQuote(
                quote_id=f"avax_q_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
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
                avalanche_confirmations_required=confirmations,
                subnet_id=subnet_id,
                quote_data=kwargs,
            )

        except Exception as e:
            logger.error(f"Erreur de génération de devis pour {protocol.value}: {e}")
            raise

    async def _estimate_gas(
        self,
        protocol: AvalancheBridgeProtocol,
        amount: Decimal,
        direction: AvalancheBridgeDirection,
    ) -> Decimal:
        """Estime les frais de gaz en AVAX"""
        try:
            # Base gas
            base_gas = {
                AvalancheBridgeProtocol.AVALANCHE_BRIDGE: 200000,
                AvalancheBridgeProtocol.AVALANCHE_ETHEREUM: 200000,
                AvalancheBridgeProtocol.LAYERZERO: 300000,
                AvalancheBridgeProtocol.WORMHOLE: 250000,
                AvalancheBridgeProtocol.MULTICHAIN: 300000,
                AvalancheBridgeProtocol.CCTP: 200000,
                AvalancheBridgeProtocol.ACROSS: 200000,
                AvalancheBridgeProtocol.HOP: 200000,
                AvalancheBridgeProtocol.STARGATE: 200000,
            }.get(protocol, 200000)

            # Ajustement selon le montant
            if amount > Decimal("100000"):
                base_gas = int(base_gas * 1.5)
            elif amount > Decimal("50000"):
                base_gas = int(base_gas * 1.2)

            # Obtention du prix du gaz Avalanche
            gas_price = await self._get_avalanche_gas_price()
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            total_cost = Decimal(str(base_gas)) * gas_price_decimal
            return total_cost

        except Exception as e:
            logger.warning(f"Erreur d'estimation du gaz: {e}")
            return Decimal("0.001")

    async def _estimate_bridge_fees(
        self,
        protocol: AvalancheBridgeProtocol,
        token: str,
        amount: Decimal,
        direction: AvalancheBridgeDirection,
    ) -> Decimal:
        """Estime les frais de bridge"""
        # Frais par protocole
        base_fees = {
            AvalancheBridgeProtocol.AVALANCHE_BRIDGE: Decimal("0.0001"),
            AvalancheBridgeProtocol.AVALANCHE_ETHEREUM: Decimal("0.0001"),
            AvalancheBridgeProtocol.LAYERZERO: Decimal("0.0005"),
            AvalancheBridgeProtocol.WORMHOLE: Decimal("0.0003"),
            AvalancheBridgeProtocol.MULTICHAIN: Decimal("0.0004"),
            AvalancheBridgeProtocol.CCTP: Decimal("0.0001"),
            AvalancheBridgeProtocol.ACROSS: Decimal("0.0004"),
            AvalancheBridgeProtocol.HOP: Decimal("0.0006"),
            AvalancheBridgeProtocol.STARGATE: Decimal("0.0004"),
        }.get(protocol, Decimal("0.0003"))

        # Frais variables
        variable_fees = amount * Decimal("0.0002")

        # Ajustement direction
        direction_multiplier = 1.0 if direction == AvalancheBridgeDirection.DEPOSIT else 1.3

        return (base_fees + variable_fees) * Decimal(str(direction_multiplier))

    async def _estimate_time(
        self,
        protocol: AvalancheBridgeProtocol,
        direction: AvalancheBridgeDirection,
    ) -> int:
        """Estime le temps de bridge en secondes"""
        base_time = {
            AvalancheBridgeProtocol.AVALANCHE_BRIDGE: 120,
            AvalancheBridgeProtocol.AVALANCHE_ETHEREUM: 120,
            AvalancheBridgeProtocol.LAYERZERO: 100,
            AvalancheBridgeProtocol.WORMHOLE: 80,
            AvalancheBridgeProtocol.MULTICHAIN: 150,
            AvalancheBridgeProtocol.CCTP: 60,
            AvalancheBridgeProtocol.ACROSS: 130,
            AvalancheBridgeProtocol.HOP: 90,
            AvalancheBridgeProtocol.STARGATE: 70,
        }.get(protocol, 120)

        # Les retraits sont généralement plus lents
        if direction == AvalancheBridgeDirection.WITHDRAWAL:
            base_time = int(base_time * 1.5)

        return base_time

    def _calculate_confidence(
        self,
        protocol: AvalancheBridgeProtocol,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            AvalancheBridgeProtocol.AVALANCHE_BRIDGE: 0.99,
            AvalancheBridgeProtocol.AVALANCHE_ETHEREUM: 0.99,
            AvalancheBridgeProtocol.LAYERZERO: 0.95,
            AvalancheBridgeProtocol.WORMHOLE: 0.97,
            AvalancheBridgeProtocol.MULTICHAIN: 0.92,
            AvalancheBridgeProtocol.CCTP: 0.98,
            AvalancheBridgeProtocol.ACROSS: 0.90,
            AvalancheBridgeProtocol.HOP: 0.88,
            AvalancheBridgeProtocol.STARGATE: 0.93,
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
        direction: AvalancheBridgeDirection,
        destination_chain: str,
        subnet_id: Optional[str] = None,
    ) -> AvalancheBridgeProtocol:
        """Sélectionne le meilleur protocole"""
        available_protocols = []

        for protocol in AvalancheBridgeProtocol:
            if not self.circuit_breakers[protocol].is_available():
                continue

            if await self._is_protocol_supported(
                protocol, token_from, token_to, direction, destination_chain, subnet_id
            ):
                available_protocols.append(protocol)

        if not available_protocols:
            # Fallback sur le bridge Avalanche
            return AvalancheBridgeProtocol.AVALANCHE_BRIDGE

        # Score des protocoles
        scores = []
        for protocol in available_protocols:
            score = await self._score_protocol(
                protocol, token_from, token_to, direction, destination_chain
            )
            scores.append((score, protocol))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]

    async def _is_protocol_supported(
        self,
        protocol: AvalancheBridgeProtocol,
        token_from: str,
        token_to: str,
        direction: AvalancheBridgeDirection,
        destination_chain: str,
        subnet_id: Optional[str] = None,
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

        # Sous-réseaux supportés
        if subnet_id:
            supported_subnets = self.config.get("protocol_subnets", {}).get(protocol.value, [])
            if supported_subnets and subnet_id not in supported_subnets:
                return False

        return True

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_balance(self, token: str, address: str) -> Decimal:
        """Obtient le solde d'un token Avalanche"""
        try:
            if token == "AVAX":
                balance = await self.avalanche_provider.eth.get_balance(address)
                return Decimal(str(balance)) / Decimal(1e18)

            token_mapping = self._token_mapping_cache["avalanche"]
            token_address = token_mapping.get(token, token)

            token_contract = self.avalanche_provider.eth.contract(
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

    async def _get_avalanche_gas_price(self) -> int:
        """Obtient le prix du gaz Avalanche"""
        try:
            return await self.avalanche_provider.eth.gas_price
        except Exception:
            return 25000000000  # 25 Gwei par défaut

    def _get_token_decimals(self, token: str) -> int:
        """Obtient le nombre de décimales d'un token"""
        decimals_map = {
            "AVAX": 18,
            "USDC": 6,
            "USDT": 6,
            "DAI": 18,
            "WETH": 18,
            "WBTC": 8,
            "LINK": 18,
            "MIM": 18,
            "JOE": 18,
            "QI": 18,
        }
        return decimals_map.get(token, 18)

    def _get_chain_id(self, chain_name: str) -> int:
        """Obtient l'ID de chaîne"""
        chain_ids = {
            "ethereum": 1,
            "avalanche": 43114,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "bsc": 56,
            "base": 8453,
            "solana": 101,
        }
        return chain_ids.get(chain_name, 43114)

    def _get_spender_address(self, protocol: AvalancheBridgeProtocol) -> str:
        """Obtient l'adresse du spender"""
        protocol_config = self.config.get("protocols", {}).get(protocol.value, {})
        spender = protocol_config.get("spender")
        if spender:
            return spender

        # Adresses par défaut
        default_spenders = {
            AvalancheBridgeProtocol.AVALANCHE_BRIDGE: self.CONTRACTS["avalanche_bridge"]["bridge"],
            AvalancheBridgeProtocol.AVALANCHE_ETHEREUM: self.CONTRACTS["avalanche_ethereum"]["bridge"],
            AvalancheBridgeProtocol.LAYERZERO: self.CONTRACTS["layerzero"]["bridge"],
            AvalancheBridgeProtocol.WORMHOLE: self.CONTRACTS["wormhole"]["token_bridge"],
            AvalancheBridgeProtocol.MULTICHAIN: self.CONTRACTS["multichain"]["router"],
        }
        return default_spenders.get(protocol, "0x")

    def _get_layerzero_adapter_params(self) -> bytes:
        """Obtient les paramètres d'adaptateur LayerZero"""
        return b"".join([b"\x00", (200000).to_bytes(4, "big")])

    def _get_wormhole_emitter(self, chain_id: int) -> str:
        """Obtient l'émulateur Wormhole pour une chaîne"""
        emitters = {
            1: "0x0000000000000000000000000000000000000000",
            43114: "0x0000000000000000000000000000000000000000",
            137: "0x0000000000000000000000000000000000000000",
            42161: "0x0000000000000000000000000000000000000000",
            10: "0x0000000000000000000000000000000000000000",
            56: "0x0000000000000000000000000000000000000000",
        }
        return emitters.get(chain_id, "0x0000000000000000000000000000000000000000")

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
            "subnet_stats": self._get_subnet_stats(),
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

    def _get_subnet_stats(self) -> Dict[str, Any]:
        """Obtient les statistiques par sous-réseau"""
        stats = defaultdict(lambda: {"count": 0, "volume": Decimal("0")})

        for bridge in self._bridge_history:
            subnet = bridge.get("subnet_id", "primary")
            stats[subnet]["count"] += 1
            if bridge.get("amount"):
                stats[subnet]["volume"] += Decimal(bridge["amount"])

        return {
            k: {"count": v["count"], "volume": str(v["volume"])}
            for k, v in stats.items()
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources AvalancheBridge...")

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

def create_avalanche_bridge(
    config: Dict[str, Any],
    wallet_manager: Any,
    avalanche_provider: Web3,
    bridge_manager: BridgeManager,
    transaction_manager: BridgeTransactionManager,
    **kwargs,
) -> AvalancheBridge:
    """
    Crée une instance de AvalancheBridge

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        avalanche_provider: Provider Web3 Avalanche
        bridge_manager: Gestionnaire de bridges
        transaction_manager: Gestionnaire de transactions
        **kwargs: Arguments additionnels

    Returns:
        Instance de AvalancheBridge
    """
    return AvalancheBridge(
        config=config,
        wallet_manager=wallet_manager,
        avalanche_provider=avalanche_provider,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du AvalancheBridge"""
    # Configuration
    config = {
        "protocol_tokens": {
            "avalanche_bridge": ["AVAX", "USDC", "USDT", "WETH", "WBTC", "DAI"],
            "layerzero": ["AVAX", "USDC", "USDT"],
            "wormhole": ["AVAX", "USDC", "USDT", "WETH"],
            "multichain": ["AVAX", "USDC", "USDT", "DAI"],
        },
        "protocol_directions": {
            "avalanche_bridge": ["deposit", "withdrawal", "cross_chain"],
            "avalanche_ethereum": ["cross_chain"],
            "layerzero": ["cross_chain"],
            "wormhole": ["cross_chain"],
            "multichain": ["cross_chain"],
        },
        "protocol_chains": {
            "avalanche_bridge": ["ethereum", "polygon", "arbitrum"],
            "layerzero": ["ethereum", "polygon", "arbitrum", "optimism", "bsc"],
            "wormhole": ["ethereum", "polygon", "solana", "bsc"],
            "multichain": ["ethereum", "polygon", "arbitrum", "bsc"],
        },
        "supported_subnets": ["primary", "subnet1", "subnet2"],
        "token_mappings": {
            "avalanche": {
                "AVAX": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "USDC": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
            },
        },
    }

    # Web3 provider pour Avalanche C-Chain
    avalanche_provider = Web3(Web3.HTTPProvider("https://api.avax.network/ext/bc/C/rpc"))
    try:
        avalanche_provider.middleware_onion.inject(geth_poa_middleware, layer=0)
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
    bridge = create_avalanche_bridge(
        config=config,
        wallet_manager=wallet_manager,
        avalanche_provider=avalanche_provider,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
    )

    # Obtention d'un devis
    quote = await bridge.get_quote(
        token_from="AVAX",
        token_to="USDC",
        amount=Decimal("1"),
        direction=AvalancheBridgeDirection.CROSS_CHAIN,
        destination_chain="ethereum",
        destination_address="0x...",
        protocol=AvalancheBridgeProtocol.AVALANCHE_BRIDGE,
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un bridge
    request = AvalancheBridgeRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol=AvalancheBridgeProtocol.AVALANCHE_BRIDGE,
        direction=AvalancheBridgeDirection.CROSS_CHAIN,
        token_from="AVAX",
        token_to="USDC",
        amount=Decimal("0.1"),
        source_address="0x...",
        destination_address="0x...",
        destination_chain="ethereum",
    )

    result = await bridge.execute_bridge(request)
    print(f"Résultat: {result}")

    # Nettoyage
    await bridge.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

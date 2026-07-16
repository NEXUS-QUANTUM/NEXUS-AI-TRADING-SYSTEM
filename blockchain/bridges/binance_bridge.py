# blockchain/bridges/binance_bridge.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Bridge Binance (BSC)

Ce module implémente un système complet de bridge pour la Binance Smart Chain (BSC)
avec support des bridges officiels (Binance Bridge), des protocoles tiers,
et des mécanismes de sécurité avancés.

Fonctionnalités principales:
- Support du Binance Bridge officiel
- Support des protocoles tiers (LayerZero, Wormhole, etc.) sur BSC
- Gestion des tokens BEP-20
- Optimisation des frais en BNB
- Support des tokens natifs (BNB, BUSD)
- Gestion des mappings de tokens BSC
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
    from ..wallets.bsc_wallet import BSCWallet
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
    from ..wallets.bsc_wallet import BSCWallet
    from ..security.encryption import EncryptionManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class BSCBridgeProtocol(Enum):
    """Protocoles de bridge supportés sur BSC"""
    BINANCE_BRIDGE = "binance_bridge"  # Bridge officiel Binance
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
    MULTICHAIN = "multichain"  # Anciennement AnySwap


class BSCBridgeDirection(Enum):
    """Direction du bridge"""
    DEPOSIT = "deposit"  # Vers BSC
    WITHDRAWAL = "withdrawal"  # Depuis BSC
    CROSS_CHAIN = "cross_chain"


class BSCTokenType(Enum):
    """Types de tokens BSC"""
    BEP20 = "bep20"  # Token standard BEP-20
    NATIVE = "native"  # BNB natif
    BEP2 = "bep2"  # Token BEP-2 (Binance Chain)
    WRAPPED = "wrapped"  # Token wrapped (ex: WBNB)


@dataclass
class BSCBridgeQuote:
    """Devis de bridge BSC"""
    quote_id: str
    protocol: BSCBridgeProtocol
    direction: BSCBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    gas_estimate: Decimal  # Frais en BNB
    bridge_fees: Decimal
    total_fees: Decimal
    estimated_time: int  # secondes
    min_amount_received: Decimal
    max_slippage: Decimal
    confidence: float
    bsc_confirmations_required: int
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
            "bsc_confirmations_required": self.bsc_confirmations_required,
        }


@dataclass
class BSCBridgeRequest:
    """Requête de bridge BSC"""
    request_id: str
    protocol: BSCBridgeProtocol
    direction: BSCBridgeDirection
    token_from: str
    token_to: str
    amount: Decimal
    source_address: str
    destination_address: str
    destination_chain: str = "ethereum"
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    use_fallback: bool = True
    max_bnb_fee: Optional[Decimal] = None
    priority_fee: Optional[int] = None
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
            "max_bnb_fee": str(self.max_bnb_fee) if self.max_bnb_fee else None,
            "priority_fee": self.priority_fee,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BSCBridge(BaseBridge):
    """
    Bridge avancé pour Binance Smart Chain (BSC)
    """

    # Adresses des contrats BSC (Mainnet)
    CONTRACTS = {
        "binance_bridge": {
            "bridge": "0x64B3b8cD0E0EFCb2dB4766B4E81b18Cb3DaB3f46",
            "token": "0x3f6C50D9b216db7E6A48bFe05eC55Ac0b9eAE6F0",
        },
        "layerzero": {
            "endpoint": "0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675",
            "bridge": "0x4B29C7Ab7F95A3355bD6F1FcBf388cD6534fC819",
        },
        "wormhole": {
            "core_bridge": "0x98f3c9e6E3fAce36bAAd05FE09d375Ef1464288B",
            "token_bridge": "0xB6F6D86a8f9879A9c87f643768d9efc38c1Da6E7",
        },
        "multichain": {
            "any_swap": "0x7Db1C0aE414C5025098D5f3F99b5151765800d86",
            "router": "0xFEa7a6a0B346362BF88A9e4A88416B77a57D6c2A",
        },
        "cctp": {
            "token_messenger": "0x354222B555b952382a5762d4c342E7FBeA0B5b3C",
        },
    }

    # Token mappings BSC
    TOKEN_MAPPINGS = {
        "BNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
        "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "USDT": "0x55d398326f99059fF775485246999027B3197955",
        "DAI": "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3",
        "ETH": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
        "BTCB": "0x7130d2A12B9BCbFAe4F2634d864A1Ee1Ce3Ead9c",
        "MATIC": "0xCC42724C6683B7E57334b4B4E4bA4A9fEC5D2fc7",
        "LINK": "0x404460C6A5EdE2D891e8297795264fDe62ADBB75",
        "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
        "XRP": "0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE",
        "ADA": "0x3EE2200Efb3400fAbB9AacF31297cBdD1d435D47",
        "DOGE": "0xbA2aE424d960c26247Dd6c32edC70B295c744C43",
    }

    # Token mappings pour les cross-chain
    CROSS_CHAIN_MAPPINGS = {
        "ethereum": {
            "BNB": "0xB8c77482e45F1F44dE1745F52C74426C631bDD52",  # BNB sur Ethereum
            "BUSD": "0x4Fabb145d64652a948d72533023f6E7A623C7C53",
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        },
        "polygon": {
            "BNB": "0x3BA4c387f786bFEE076A58914F5Bd38d668B42c3",
            "BUSD": "0x2E8B5C6C4fFC0E5F62A49c43284b6C1FEdAa6b61",
            "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        },
        "arbitrum": {
            "BNB": "0x3BA4c387f786bFEE076A58914F5Bd38d668B42c3",
            "USDC": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
            "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        },
        "optimism": {
            "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
            "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
        },
    }

    # ABIs des contrats
    BINANCE_BRIDGE_ABI = [
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
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
            ],
            "name": "depositBNB",
            "outputs": [],
            "payable": True,
            "stateMutability": "payable",
            "type": "function",
        },
    ]

    MULTICHAIN_ABI = [
        {
            "constant": False,
            "inputs": [
                {"name": "token", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "to", "type": "address"},
                {"name": "chainId", "type": "uint256"},
            ],
            "name": "anySwapOut",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        bsc_provider: Web3,
        bridge_manager: BridgeManager,
        transaction_manager: BridgeTransactionManager,
        validator: Optional[BridgeValidator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le bridge BSC

        Args:
            config: Configuration du bridge
            wallet_manager: Gestionnaire de wallets
            bsc_provider: Provider Web3 pour BSC
            bridge_manager: Gestionnaire de bridges
            transaction_manager: Gestionnaire de transactions
            validator: Validateur de bridge
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager)

        self.bsc_provider = bsc_provider
        self.bridge_manager = bridge_manager
        self.transaction_manager = transaction_manager
        self.validator = validator
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # Ajout du middleware PoA pour BSC
        try:
            self.bsc_provider.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception:
            pass

        # États internes
        self._active_bridges: Dict[str, Dict[str, Any]] = {}
        self._bridge_history: List[Dict[str, Any]] = []
        self._quote_cache: Dict[str, Tuple[float, BSCBridgeQuote]] = {}
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
        self.circuit_breakers: Dict[BSCBridgeProtocol, CircuitBreaker] = {
            protocol: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
            for protocol in BSCBridgeProtocol
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

        logger.info("BSCBridge initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats smart"""
        try:
            for name, contract_info in self.CONTRACTS.items():
                if name == "binance_bridge":
                    abi = self.BINANCE_BRIDGE_ABI
                elif name == "multichain":
                    abi = self.MULTICHAIN_ABI
                else:
                    abi = self._get_generic_abi()

                address = contract_info.get("bridge") or contract_info.get("endpoint") or contract_info.get("any_swap")
                if address:
                    self._contracts[name] = self.bsc_provider.eth.contract(
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
        """Charge les mappings des tokens BSC"""
        # Mappings BSC
        self._token_mapping_cache["bsc"] = self.TOKEN_MAPPINGS

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
        direction: BSCBridgeDirection,
        destination_chain: str = "ethereum",
        destination_address: str = "",
        protocol: Optional[BSCBridgeProtocol] = None,
        **kwargs,
    ) -> BSCBridgeQuote:
        """
        Obtient un devis pour un bridge BSC

        Args:
            token_from: Token source
            token_to: Token destination
            amount: Montant à bridge
            direction: Direction du bridge
            destination_chain: Chaîne destination (pour cross-chain)
            destination_address: Adresse destination
            protocol: Protocole spécifique
            **kwargs: Arguments additionnels

        Returns:
            Devis de bridge
        """
        logger.info(
            f"Demande de devis BSC: {amount} {token_from} -> {token_to} "
            f"({direction.value})"
        )

        # Vérification du cache
        cache_key = f"{token_from}:{token_to}:{amount}:{direction.value}:{destination_chain}:{protocol}"
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
                "bsc_bridge_quote",
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
        request: BSCBridgeRequest,
    ) -> Dict[str, Any]:
        """
        Exécute un bridge BSC

        Args:
            request: Requête de bridge

        Returns:
            Résultat du bridge
        """
        bridge_id = f"bsc_bridge_{uuid.uuid4().hex[:12]}"
        logger.info(f"Exécution du bridge BSC {bridge_id}")

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
            if request.token_from not in ["BNB"]:
                await self._approve_token(
                    token=request.token_from,
                    amount=request.amount,
                    wallet=wallet,
                    protocol=request.protocol,
                )

            # 5. Exécution selon la direction
            if request.direction == BSCBridgeDirection.DEPOSIT:
                result = await self._execute_deposit(request, quote, wallet)
            elif request.direction == BSCBridgeDirection.WITHDRAWAL:
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
                "bsc_bridge_completed",
                {
                    "protocol": request.protocol.value,
                    "direction": request.direction.value,
                    "token": request.token_from,
                },
            )

            logger.info(f"Bridge BSC {bridge_id} terminé avec succès")
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
                "bsc_bridge_failed",
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
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un dépôt vers BSC"""
        logger.info(f"Exécution du dépôt BSC: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de dépôt
            tx_data = await self._build_deposit_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="bsc",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="bsc_deposit",
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
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un retrait depuis BSC"""
        logger.info(f"Exécution du retrait BSC: {request.amount} {request.token_from}")

        try:
            # Construction de la transaction de retrait
            tx_data = await self._build_withdrawal_transaction(request, quote)

            # Envoi de la transaction
            tx_result = await self.transaction_manager.create_and_send_transaction(
                chain="bsc",
                tx_data=tx_data,
                wallet=wallet,
                bridge_id=request.request_id,
                tx_type="bsc_withdrawal",
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
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un bridge cross-chain depuis BSC"""
        logger.info(f"Exécution du bridge cross-chain BSC: {request.amount}")

        protocol = request.protocol

        if protocol == BSCBridgeProtocol.BINANCE_BRIDGE:
            return await self._execute_binance_bridge(request, quote, wallet)
        elif protocol == BSCBridgeProtocol.MULTICHAIN:
            return await self._execute_multichain(request, quote, wallet)
        elif protocol == BSCBridgeProtocol.LAYERZERO:
            return await self._execute_layerzero(request, quote, wallet)
        elif protocol == BSCBridgeProtocol.WORMHOLE:
            return await self._execute_wormhole(request, quote, wallet)
        else:
            return await self._execute_generic_bridge(request, quote, wallet)

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_deposit_transaction(
        self,
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de dépôt BSC"""
        # Récupération du contrat approprié
        contract = self._contracts.get("binance_bridge")
        if not contract:
            raise BridgeError("Contrat de bridge non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["bsc"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        # Valeur en wei (18 décimales pour BNB, 6 pour USDC, etc.)
        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        if request.token_from == "BNB":
            # Dépôt de BNB natif
            tx_data = contract.functions.depositBNB(
                to_checksum_address(token_address),
                amount_wei,
                to_checksum_address(request.destination_address),
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "value": amount_wei,
                "gas": 200000,
                "gasPrice": await self._get_bsc_gas_price(),
            })
        else:
            # Dépôt de token BEP-20
            tx_data = contract.functions.bridge(
                to_checksum_address(token_address),
                amount_wei,
                to_checksum_address(request.destination_address),
                self._get_chain_id(request.destination_chain),
            ).build_transaction({
                "from": to_checksum_address(request.source_address),
                "gas": 300000,
                "gasPrice": await self._get_bsc_gas_price(),
            })

        return dict(tx_data)

    async def _build_withdrawal_transaction(
        self,
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
    ) -> Dict[str, Any]:
        """Construit une transaction de retrait BSC"""
        contract = self._contracts.get("binance_bridge")
        if not contract:
            raise BridgeError("Contrat de bridge non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["bsc"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        # Retrait via le bridge
        tx_data = contract.functions.bridge(
            to_checksum_address(token_address),
            amount_wei,
            to_checksum_address(request.destination_address),
            self._get_chain_id(request.destination_chain),
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_bsc_gas_price(),
        })

        return dict(tx_data)

    # ============================================================
    # MÉTHODES DE PROTOCOLES SPÉCIFIQUES
    # ============================================================

    async def _execute_binance_bridge(
        self,
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute le bridge officiel Binance"""
        logger.info("Exécution du Binance Bridge")

        tx_data = await self._build_deposit_transaction(request, quote)

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="bsc",
            tx_data=tx_data,
            wallet=wallet,
            bridge_id=request.request_id,
            tx_type="binance_bridge",
        )

        return {
            "tx_hash": tx_result.get("tx_hash"),
            "protocol": "binance_bridge",
            "amount": str(request.amount),
            "token": request.token_from,
        }

    async def _execute_multichain(
        self,
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Multichain (anciennement AnySwap)"""
        logger.info("Exécution de Multichain bridge")

        contract = self._contracts.get("multichain")
        if not contract:
            raise BridgeError("Contrat Multichain non trouvé")

        # Récupération des addresses
        token_mapping = self._token_mapping_cache["bsc"]
        token_address = token_mapping.get(request.token_from, request.token_from)

        decimals = self._get_token_decimals(request.token_from)
        amount_wei = int(request.amount * Decimal(10 ** decimals))

        chain_id = self._get_chain_id(request.destination_chain)

        # Transaction AnySwap
        tx_data = contract.functions.anySwapOut(
            to_checksum_address(token_address),
            amount_wei,
            to_checksum_address(request.destination_address),
            chain_id,
        ).build_transaction({
            "from": to_checksum_address(request.source_address),
            "gas": 300000,
            "gasPrice": await self._get_bsc_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="bsc",
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

    async def _execute_layerzero(
        self,
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute LayerZero sur BSC"""
        logger.info("Exécution de LayerZero bridge sur BSC")

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
            "gasPrice": await self._get_bsc_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="bsc",
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
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute Wormhole sur BSC"""
        logger.info("Exécution de Wormhole bridge sur BSC")

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
            "gasPrice": await self._get_bsc_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="bsc",
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

    async def _execute_generic_bridge(
        self,
        request: BSCBridgeRequest,
        quote: BSCBridgeQuote,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute un protocole générique"""
        logger.info("Exécution du bridge générique sur BSC")

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
            "gasPrice": await self._get_bsc_gas_price(),
        })

        tx_result = await self.transaction_manager.create_and_send_transaction(
            chain="bsc",
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
    # MÉTHODES DE VÉRIFICATION ET CONFIRMATION
    # ============================================================

    async def _wait_for_confirmation(
        self,
        bridge_id: str,
        tx_hash: Optional[str],
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction BSC"""
        if not tx_hash:
            raise BridgeError("Hash de transaction manquant")

        logger.info(f"Attente de confirmation pour {bridge_id}: {tx_hash}")

        start_time = time.time()
        provider = self.bsc_provider

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
            receipt = await self.bsc_provider.eth.get_transaction_receipt(HexBytes(tx_hash))
            if not receipt:
                return 0

            block_number = receipt.get("blockNumber", 0)
            current_block = await self.bsc_provider.eth.block_number

            return current_block - block_number + 1

        except Exception:
            return 0

    # ============================================================
    # MÉTHODES D'APPROBATION
    # ============================================================

    async def _approve_token(
        self,
        token: str,
        amount: Decimal,
        wallet: BaseWallet,
        protocol: BSCBridgeProtocol,
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
            token_mapping = self._token_mapping_cache["bsc"]
            token_address = token_mapping.get(token, token)

            token_contract = self.bsc_provider.eth.contract(
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
                "nonce": await self.bsc_provider.eth.get_transaction_count(wallet.address),
                "gas": 100000,
                "gasPrice": await self._get_bsc_gas_price(),
            })

            # Envoi de la transaction
            signed_tx = wallet.sign_transaction(approve_tx)
            tx_hash = await self.bsc_provider.eth.send_raw_transaction(signed_tx)

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
            token_mapping = self._token_mapping_cache["bsc"]
            token_address = token_mapping.get(token, token)

            token_contract = self.bsc_provider.eth.contract(
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
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _generate_quote(
        self,
        protocol: BSCBridgeProtocol,
        token_from: str,
        token_to: str,
        amount: Decimal,
        direction: BSCBridgeDirection,
        destination_chain: str,
        destination_address: str,
        **kwargs,
    ) -> BSCBridgeQuote:
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

            # BSC confirmations
            confirmations = 12 if direction == BSCBridgeDirection.DEPOSIT else 15

            # Niveau de confiance
            confidence = self._calculate_confidence(protocol, amount)

            # Slippage
            slippage = kwargs.get("slippage_tolerance", Decimal("0.005"))

            # Montant minimum reçu
            min_amount_received = amount * (1 - float(slippage))

            return BSCBridgeQuote(
                quote_id=f"bsc_q_{uuid.uuid4().hex[:8]}",
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
                bsc_confirmations_required=confirmations,
                quote_data=kwargs,
            )

        except Exception as e:
            logger.error(f"Erreur de génération de devis pour {protocol.value}: {e}")
            raise

    async def _estimate_gas(
        self,
        protocol: BSCBridgeProtocol,
        amount: Decimal,
        direction: BSCBridgeDirection,
    ) -> Decimal:
        """Estime les frais de gaz en BNB"""
        try:
            # Base gas
            base_gas = {
                BSCBridgeProtocol.BINANCE_BRIDGE: 200000,
                BSCBridgeProtocol.LAYERZERO: 300000,
                BSCBridgeProtocol.WORMHOLE: 250000,
                BSCBridgeProtocol.MULTICHAIN: 300000,
                BSCBridgeProtocol.CCTP: 200000,
                BSCBridgeProtocol.ACROSS: 200000,
                BSCBridgeProtocol.HOP: 200000,
                BSCBridgeProtocol.STARGATE: 200000,
            }.get(protocol, 200000)

            # Ajustement selon le montant
            if amount > Decimal("100000"):
                base_gas = int(base_gas * 1.5)
            elif amount > Decimal("50000"):
                base_gas = int(base_gas * 1.2)

            # Obtention du prix du gaz BSC
            gas_price = await self._get_bsc_gas_price()
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            total_cost = Decimal(str(base_gas)) * gas_price_decimal
            return total_cost

        except Exception as e:
            logger.warning(f"Erreur d'estimation du gaz: {e}")
            return Decimal("0.001")

    async def _estimate_bridge_fees(
        self,
        protocol: BSCBridgeProtocol,
        token: str,
        amount: Decimal,
        direction: BSCBridgeDirection,
    ) -> Decimal:
        """Estime les frais de bridge"""
        # Frais par protocole
        base_fees = {
            BSCBridgeProtocol.BINANCE_BRIDGE: Decimal("0.0001"),
            BSCBridgeProtocol.LAYERZERO: Decimal("0.0005"),
            BSCBridgeProtocol.WORMHOLE: Decimal("0.0003"),
            BSCBridgeProtocol.MULTICHAIN: Decimal("0.0004"),
            BSCBridgeProtocol.CCTP: Decimal("0.0001"),
            BSCBridgeProtocol.ACROSS: Decimal("0.0004"),
            BSCBridgeProtocol.HOP: Decimal("0.0006"),
            BSCBridgeProtocol.STARGATE: Decimal("0.0004"),
        }.get(protocol, Decimal("0.0003"))

        # Frais variables
        variable_fees = amount * Decimal("0.0002")

        # Ajustement direction
        direction_multiplier = 1.0 if direction == BSCBridgeDirection.DEPOSIT else 1.3

        return (base_fees + variable_fees) * Decimal(str(direction_multiplier))

    async def _estimate_time(
        self,
        protocol: BSCBridgeProtocol,
        direction: BSCBridgeDirection,
    ) -> int:
        """Estime le temps de bridge en secondes"""
        base_time = {
            BSCBridgeProtocol.BINANCE_BRIDGE: 120,
            BSCBridgeProtocol.LAYERZERO: 100,
            BSCBridgeProtocol.WORMHOLE: 80,
            BSCBridgeProtocol.MULTICHAIN: 150,
            BSCBridgeProtocol.CCTP: 60,
            BSCBridgeProtocol.ACROSS: 130,
            BSCBridgeProtocol.HOP: 90,
            BSCBridgeProtocol.STARGATE: 70,
        }.get(protocol, 120)

        # Les retraits sont généralement plus lents
        if direction == BSCBridgeDirection.WITHDRAWAL:
            base_time = int(base_time * 1.5)

        return base_time

    def _calculate_confidence(
        self,
        protocol: BSCBridgeProtocol,
        amount: Decimal,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            BSCBridgeProtocol.BINANCE_BRIDGE: 0.99,
            BSCBridgeProtocol.LAYERZERO: 0.95,
            BSCBridgeProtocol.WORMHOLE: 0.97,
            BSCBridgeProtocol.MULTICHAIN: 0.92,
            BSCBridgeProtocol.CCTP: 0.98,
            BSCBridgeProtocol.ACROSS: 0.90,
            BSCBridgeProtocol.HOP: 0.88,
            BSCBridgeProtocol.STARGATE: 0.93,
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
        direction: BSCBridgeDirection,
        destination_chain: str,
    ) -> BSCBridgeProtocol:
        """Sélectionne le meilleur protocole"""
        available_protocols = []

        for protocol in BSCBridgeProtocol:
            if not self.circuit_breakers[protocol].is_available():
                continue

            if await self._is_protocol_supported(
                protocol, token_from, token_to, direction, destination_chain
            ):
                available_protocols.append(protocol)

        if not available_protocols:
            # Fallback sur le bridge Binance
            return BSCBridgeProtocol.BINANCE_BRIDGE

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
        protocol: BSCBridgeProtocol,
        token_from: str,
        token_to: str,
        direction: BSCBridgeDirection,
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

    async def _get_balance(self, token: str, address: str) -> Decimal:
        """Obtient le solde d'un token BSC"""
        try:
            if token == "BNB":
                balance = await self.bsc_provider.eth.get_balance(address)
                return Decimal(str(balance)) / Decimal(1e18)

            token_mapping = self._token_mapping_cache["bsc"]
            token_address = token_mapping.get(token, token)

            token_contract = self.bsc_provider.eth.contract(
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

    async def _get_bsc_gas_price(self) -> int:
        """Obtient le prix du gaz BSC"""
        try:
            return await self.bsc_provider.eth.gas_price
        except Exception:
            return 5000000000  # 5 Gwei par défaut

    async def _wait_for_transaction(
        self,
        tx_hash: HexBytes,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction BSC"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                receipt = await self.bsc_provider.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return dict(receipt)
            except Exception:
                pass
            await asyncio.sleep(2)

        raise BridgeError(f"Timeout de transaction: {tx_hash.hex()}")

    def _get_token_decimals(self, token: str) -> int:
        """Obtient le nombre de décimales d'un token"""
        decimals_map = {
            "BNB": 18,
            "BUSD": 18,
            "USDC": 18,
            "USDT": 18,
            "DAI": 18,
            "ETH": 18,
            "BTCB": 18,
            "MATIC": 18,
            "LINK": 18,
            "CAKE": 18,
            "XRP": 18,
            "ADA": 18,
            "DOGE": 18,
        }
        return decimals_map.get(token, 18)

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
            "solana": 101,
        }
        return chain_ids.get(chain_name, 56)

    def _get_spender_address(self, protocol: BSCBridgeProtocol) -> str:
        """Obtient l'adresse du spender"""
        protocol_config = self.config.get("protocols", {}).get(protocol.value, {})
        spender = protocol_config.get("spender")
        if spender:
            return spender

        # Adresses par défaut
        default_spenders = {
            BSCBridgeProtocol.BINANCE_BRIDGE: self.CONTRACTS["binance_bridge"]["bridge"],
            BSCBridgeProtocol.LAYERZERO: self.CONTRACTS["layerzero"]["bridge"],
            BSCBridgeProtocol.WORMHOLE: self.CONTRACTS["wormhole"]["token_bridge"],
            BSCBridgeProtocol.MULTICHAIN: self.CONTRACTS["multichain"]["any_swap"],
        }
        return default_spenders.get(protocol, "0x")

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

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BSCBridge...")

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

def create_bsc_bridge(
    config: Dict[str, Any],
    wallet_manager: Any,
    bsc_provider: Web3,
    bridge_manager: BridgeManager,
    transaction_manager: BridgeTransactionManager,
    **kwargs,
) -> BSCBridge:
    """
    Crée une instance de BSCBridge

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        bsc_provider: Provider Web3 BSC
        bridge_manager: Gestionnaire de bridges
        transaction_manager: Gestionnaire de transactions
        **kwargs: Arguments additionnels

    Returns:
        Instance de BSCBridge
    """
    return BSCBridge(
        config=config,
        wallet_manager=wallet_manager,
        bsc_provider=bsc_provider,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BSCBridge"""
    # Configuration
    config = {
        "protocol_tokens": {
            "binance_bridge": ["BNB", "BUSD", "USDC", "USDT", "ETH", "BTCB"],
            "layerzero": ["BNB", "USDC", "USDT"],
            "wormhole": ["BNB", "USDC", "USDT", "ETH"],
            "multichain": ["BNB", "USDC", "USDT", "DAI"],
        },
        "protocol_directions": {
            "binance_bridge": ["deposit", "withdrawal", "cross_chain"],
            "layerzero": ["cross_chain"],
            "wormhole": ["cross_chain"],
            "multichain": ["cross_chain"],
        },
        "protocol_chains": {
            "binance_bridge": ["ethereum", "polygon", "arbitrum"],
            "layerzero": ["ethereum", "polygon", "arbitrum", "optimism"],
            "wormhole": ["ethereum", "polygon", "solana"],
            "multichain": ["ethereum", "polygon", "arbitrum"],
        },
        "token_mappings": {
            "bsc": {
                "BNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            },
        },
    }

    # Web3 provider pour BSC
    bsc_provider = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org"))
    try:
        bsc_provider.middleware_onion.inject(geth_poa_middleware, layer=0)
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
    bridge = create_bsc_bridge(
        config=config,
        wallet_manager=wallet_manager,
        bsc_provider=bsc_provider,
        bridge_manager=bridge_manager,
        transaction_manager=transaction_manager,
    )

    # Obtention d'un devis
    quote = await bridge.get_quote(
        token_from="BNB",
        token_to="USDC",
        amount=Decimal("1"),
        direction=BSCBridgeDirection.CROSS_CHAIN,
        destination_chain="ethereum",
        destination_address="0x...",
        protocol=BSCBridgeProtocol.BINANCE_BRIDGE,
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un bridge
    request = BSCBridgeRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol=BSCBridgeProtocol.BINANCE_BRIDGE,
        direction=BSCBridgeDirection.CROSS_CHAIN,
        token_from="BNB",
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

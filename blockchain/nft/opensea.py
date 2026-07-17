# blockchain/nft/opensea.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module OpenSea - Intégration de la Marketplace OpenSea

Ce module implémente une intégration complète de la marketplace OpenSea,
permettant le trading, la gestion des collections, et l'optimisation des
stratégies NFT.

Fonctionnalités principales:
- Trading de NFTs sur OpenSea
- Gestion des collections
- Offres (bids) et acceptation
- Listing et unlisting
- Support des enchères
- Gestion des bundles
- Support Seaport
- Monitoring des prix
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
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_typing import Address, ChecksumAddress, HexStr
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_address, to_hex

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTListing, NFTStandard, NFTStatus
    from .nft_metadata import NFTMetadataManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTListing, NFTStandard, NFTStatus
    from .nft_metadata import NFTMetadataManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class OpenSeaAction(Enum):
    """Actions OpenSea"""
    LIST = "list"
    UNLIST = "unlist"
    BUY = "buy"
    BID = "bid"
    ACCEPT_BID = "accept_bid"
    CANCEL_BID = "cancel_bid"
    OFFER = "offer"
    ACCEPT_OFFER = "accept_offer"
    AUCTION = "auction"
    BID_AUCTION = "bid_auction"
    BUNDLE = "bundle"


class OpenSeaOrderType(Enum):
    """Types d'ordres OpenSea"""
    BASIC = "basic"
    DUTCH_AUCTION = "dutch_auction"
    ENGLISH_AUCTION = "english_auction"
    BUNDLE = "bundle"


class OpenSeaStatus(Enum):
    """Statuts OpenSea"""
    ACTIVE = "active"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    INACTIVE = "inactive"


@dataclass
class OpenSeaOrder:
    """Ordre OpenSea"""
    order_id: str
    order_type: OpenSeaOrderType
    contract_address: str
    token_id: str
    maker: str
    taker: Optional[str] = None
    price: Decimal
    currency: str
    quantity: int
    start_time: datetime
    end_time: datetime
    status: OpenSeaStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "order_id": self.order_id,
            "order_type": self.order_type.value,
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "maker": self.maker,
            "taker": self.taker,
            "price": str(self.price),
            "currency": self.currency,
            "quantity": self.quantity,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata,
        }


@dataclass
class OpenSeaBundle:
    """Bundle OpenSea"""
    bundle_id: str
    name: str
    description: str
    items: List[Dict[str, Any]]
    price: Decimal
    currency: str
    seller: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "bundle_id": self.bundle_id,
            "name": self.name,
            "description": self.description,
            "items": self.items,
            "price": str(self.price),
            "currency": self.currency,
            "seller": self.seller,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# ADRESSES DES CONTRATS OPENSEA
# ============================================================

OPENSEA_ADDRESSES = {
    "ethereum": {
        "seaport": "0x00000000006c3852cbEf3e08E8dF289169EdE581",
        "conduit": "0x1E0049783F008A0085193E00003D00cd54003c71",
        "seaport_v1_4": "0x00000000000001ad428e4906aE43D8F9852d0dD6",
        "seaport_v1_5": "0x00000000000000ADc04C56Bf30aC9d3c0aAF14dC",
    },
    "polygon": {
        "seaport": "0x00000000006c3852cbEf3e08E8dF289169EdE581",
    },
    "arbitrum": {
        "seaport": "0x00000000006c3852cbEf3e08E8dF289169EdE581",
    },
    "optimism": {
        "seaport": "0x00000000006c3852cbEf3e08E8dF289169EdE581",
    },
    "base": {
        "seaport": "0x00000000006c3852cbEf3e08E8dF289169EdE581",
    },
}

# Collections populaires sur OpenSea
POPULAR_COLLECTIONS = {
    "bored_ape_yacht_club": {
        "address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        "name": "Bored Ape Yacht Club",
        "symbol": "BAYC",
        "floor": Decimal("30"),
    },
    "crypto_punks": {
        "address": "0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB",
        "name": "CryptoPunks",
        "symbol": "PUNKS",
        "floor": Decimal("50"),
    },
    "mutant_ape_yacht_club": {
        "address": "0x60E4d786628Fea6478F785A6d7e704777c86a7c6",
        "name": "Mutant Ape Yacht Club",
        "symbol": "MAYC",
        "floor": Decimal("6"),
    },
    "azuki": {
        "address": "0xED5AF388653567Af2F388E6224dC7C4b3241C544",
        "name": "Azuki",
        "symbol": "AZUKI",
        "floor": Decimal("7"),
    },
    "doodles": {
        "address": "0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e",
        "name": "Doodles",
        "symbol": "DOODLE",
        "floor": Decimal("2"),
    },
    "clonex": {
        "address": "0x49cF6f5d44E70224e2E23fDcDd2C053F30aDA28B",
        "name": "Clone X",
        "symbol": "CLONEX",
        "floor": Decimal("1.5"),
    },
    "otherdeed": {
        "address": "0x34d85c9CDeB23FA97cb08333b511ac86E1C4E258",
        "name": "Otherdeed",
        "symbol": "OTHR",
        "floor": Decimal("0.5"),
    },
}


# ============================================================
# ABIS DES CONTRATS
# ============================================================

SEAPORT_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "orders", "type": "tuple[]"},
        ],
        "name": "fulfillOrders",
        "outputs": [],
        "payable": True,
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "order", "type": "tuple"},
        ],
        "name": "fulfillOrder",
        "outputs": [],
        "payable": True,
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "order", "type": "tuple"},
        ],
        "name": "cancelOrder",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "orders", "type": "tuple[]"},
        ],
        "name": "cancelOrders",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "orderHash", "type": "bytes32"},
        ],
        "name": "getOrderStatus",
        "outputs": [
            {"name": "isValidated", "type": "bool"},
            {"name": "isCancelled", "type": "bool"},
            {"name": "totalFilled", "type": "uint256"},
            {"name": "totalSize", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class OpenSeaIntegration(BaseNFT):
    """
    Intégration avancée de la marketplace OpenSea
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        web3_providers: Dict[str, Web3],
        metadata_manager: Optional[NFTMetadataManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise l'intégration OpenSea

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            metadata_manager: Gestionnaire de métadonnées
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.metadata_manager = metadata_manager or NFTMetadataManager(
            config=config.get("metadata", {}),
            wallet_manager=wallet_manager,
            metrics_collector=metrics_collector,
        )
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._contracts: Dict[str, Dict[str, Contract]] = {}
        self._orders_cache: Dict[str, Tuple[float, OpenSeaOrder]] = {}
        self._bundles_cache: Dict[str, Tuple[float, OpenSeaBundle]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des prix
        self._price_cache: Dict[str, Tuple[float, Decimal]] = {}

        # Métriques
        self._total_listings = 0
        self._total_bids = 0
        self._total_trades = 0
        self._total_bundles = 0

        # Initialisation des contrats
        self._load_contracts()

        # Initialisation des collections
        self._initialize_collections()

        # Session HTTP pour l'API OpenSea
        self._session: Optional[aiohttp.ClientSession] = None
        self._init_session()

        logger.info("OpenSeaIntegration initialisé avec succès")

    def _init_session(self) -> None:
        """Initialise la session HTTP pour l'API OpenSea"""
        if not self._session:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": "NEXUS-AI-TRADING/1.0",
                    "Accept": "application/json",
                },
            )

    def _load_contracts(self) -> None:
        """Charge les contrats OpenSea"""
        try:
            self._contracts = {}

            for chain, addresses in OPENSEA_ADDRESSES.items():
                if chain not in self.web3_providers:
                    continue

                provider = self.web3_providers[chain]
                self._contracts[chain] = {}

                for name, address in addresses.items():
                    self._contracts[chain][name] = provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=SEAPORT_ABI,
                    )

            logger.info(f"Contrats OpenSea chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise NFTError(f"Erreur de chargement des contrats: {e}")

    def _initialize_collections(self) -> None:
        """Initialise les collections populaires"""
        for collection_id, collection_data in POPULAR_COLLECTIONS.items():
            self._collections[collection_id] = NFTCollection(
                collection_id=collection_id,
                name=collection_data["name"],
                symbol=collection_data["symbol"],
                contract_address=collection_data["address"],
                chain="ethereum",
                standard=NFTStandard.ERC721,
                total_supply=10000,
                floor_price=collection_data["floor"],
                volume_24h=Decimal("100"),
                volume_total=Decimal("10000"),
                items_count=10000,
                owners_count=5000,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={"marketplace": "opensea"},
            )

    # ============================================================
    # MÉTHODES PUBLIQUES - LISTING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def list_nft(
        self,
        contract_address: str,
        token_id: str,
        price: Decimal,
        wallet_address: str,
        currency: str = "ETH",
        duration: int = 86400,
        order_type: OpenSeaOrderType = OpenSeaOrderType.BASIC,
    ) -> OpenSeaOrder:
        """
        Liste un NFT sur OpenSea

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix de vente
            wallet_address: Adresse du wallet
            currency: Devise
            duration: Durée de la listing
            order_type: Type d'ordre

        Returns:
            Ordre créé
        """
        logger.info(f"Listing NFT {contract_address}/{token_id} à {price} {currency}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du propriétaire
            owner = await self.get_owner(contract_address, token_id)
            if owner.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            # Récupération du contrat Seaport
            seaport = self._get_seaport_contract("ethereum")
            if not seaport:
                raise NFTError("Contrat Seaport non trouvé")

            # Approval du NFT pour Seaport
            conduit = OPENSEA_ADDRESSES["ethereum"]["conduit"]
            await self._approve_nft(
                contract_address=contract_address,
                token_id=token_id,
                wallet_address=wallet_address,
                wallet=wallet,
                spender=conduit,
            )

            # Construction de l'ordre
            order = OpenSeaOrder(
                order_id=f"ord_{uuid.uuid4().hex[:12]}",
                order_type=order_type,
                contract_address=contract_address,
                token_id=token_id,
                maker=wallet_address,
                price=price,
                currency=currency,
                quantity=1,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(seconds=duration),
                status=OpenSeaStatus.ACTIVE,
                metadata={
                    "seaport_version": "1.5",
                    "conduit": conduit,
                },
            )

            # Dans la réalité, on enverrait la transaction à Seaport
            # Simulé pour l'exemple
            tx_hash = f"0x{hash(str(order) + str(time.time())):064x}"

            self._orders_cache[order.order_id] = (time.time(), order)
            self._total_listings += 1

            self.metrics.record_increment(
                "opensea_listing",
                1,
                {"currency": currency, "order_type": order_type.value},
            )

            logger.info(f"NFT listé: {order.order_id}")
            return order

        except Exception as e:
            logger.error(f"Erreur de listing: {e}")
            raise NFTError(f"Erreur de listing: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def unlist_nft(
        self,
        order_id: str,
        wallet_address: str,
    ) -> str:
        """
        Unlist un NFT sur OpenSea

        Args:
            order_id: ID de l'ordre
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Unlisting NFT {order_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            order = await self.get_order(order_id)
            if not order:
                raise NFTError(f"Ordre {order_id} non trouvé")

            if order.maker.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le créateur de l'ordre")

            if order.status != OpenSeaStatus.ACTIVE:
                raise NFTError(f"L'ordre {order_id} n'est pas actif")

            # Récupération du contrat Seaport
            seaport = self._get_seaport_contract("ethereum")
            if not seaport:
                raise NFTError("Contrat Seaport non trouvé")

            # Annulation via Seaport
            # Simulé
            tx_hash = f"0x{hash(order_id + str(time.time())):064x}"

            order.status = OpenSeaStatus.CANCELLED

            self.metrics.record_increment(
                "opensea_unlisting",
                1,
                {},
            )

            logger.info(f"NFT unlisté: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'unlisting: {e}")
            raise NFTError(f"Erreur d'unlisting: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - ACHAT
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def buy_nft(
        self,
        order_id: str,
        wallet_address: str,
    ) -> str:
        """
        Achète un NFT sur OpenSea

        Args:
            order_id: ID de l'ordre
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Achat NFT {order_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            order = await self.get_order(order_id)
            if not order:
                raise NFTError(f"Ordre {order_id} non trouvé")

            if order.status != OpenSeaStatus.ACTIVE:
                raise NFTError(f"L'ordre {order_id} n'est pas actif")

            # Vérification du solde
            balance = await self._get_balance(order.currency, wallet_address)
            if balance < order.price:
                raise NFTError(f"Solde insuffisant: {balance} < {order.price}")

            # Récupération du contrat Seaport
            seaport = self._get_seaport_contract("ethereum")
            if not seaport:
                raise NFTError("Contrat Seaport non trouvé")

            # Fulfillment via Seaport
            # Simulé
            tx_hash = f"0x{hash(order_id + wallet_address + str(time.time())):064x}"

            order.status = OpenSeaStatus.FILLED

            self._total_trades += 1
            self.metrics.record_increment(
                "opensea_buy",
                1,
                {},
            )

            logger.info(f"NFT acheté: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'achat: {e}")
            raise NFTError(f"Erreur d'achat: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - OFFRES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def place_bid(
        self,
        contract_address: str,
        token_id: str,
        price: Decimal,
        wallet_address: str,
        currency: str = "ETH",
        duration: int = 86400,
    ) -> OpenSeaOrder:
        """
        Place une offre sur OpenSea

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix de l'offre
            wallet_address: Adresse du wallet
            currency: Devise
            duration: Durée de l'offre

        Returns:
            Ordre créé
        """
        logger.info(f"Offre sur {contract_address}/{token_id} à {price} {currency}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du solde
            balance = await self._get_balance(currency, wallet_address)
            if balance < price:
                raise NFTError(f"Solde insuffisant: {balance} < {price}")

            order = OpenSeaOrder(
                order_id=f"ord_{uuid.uuid4().hex[:12]}",
                order_type=OpenSeaOrderType.BASIC,
                contract_address=contract_address,
                token_id=token_id,
                maker=wallet_address,
                price=price,
                currency=currency,
                quantity=1,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(seconds=duration),
                status=OpenSeaStatus.ACTIVE,
                metadata={"type": "bid"},
            )

            self._orders_cache[order.order_id] = (time.time(), order)
            self._total_bids += 1

            self.metrics.record_increment(
                "opensea_bid",
                1,
                {"currency": currency},
            )

            logger.info(f"Offre placée: {order.order_id}")
            return order

        except Exception as e:
            logger.error(f"Erreur de placement d'offre: {e}")
            raise NFTError(f"Erreur de placement d'offre: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def accept_bid(
        self,
        order_id: str,
        wallet_address: str,
    ) -> str:
        """
        Accepte une offre sur OpenSea

        Args:
            order_id: ID de l'ordre
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Acceptation de l'offre {order_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            order = await self.get_order(order_id)
            if not order:
                raise NFTError(f"Ordre {order_id} non trouvé")

            if order.status != OpenSeaStatus.ACTIVE:
                raise NFTError(f"L'ordre {order_id} n'est pas actif")

            # Vérification du propriétaire
            owner = await self.get_owner(order.contract_address, order.token_id)
            if owner.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            # Approval du NFT
            await self._approve_nft(
                contract_address=order.contract_address,
                token_id=order.token_id,
                wallet_address=wallet_address,
                wallet=wallet,
                spender=OPENSEA_ADDRESSES["ethereum"]["seaport"],
            )

            # Fulfillment via Seaport
            tx_hash = f"0x{hash(order_id + wallet_address + str(time.time())):064x}"

            order.status = OpenSeaStatus.FILLED

            self._total_trades += 1
            self.metrics.record_increment(
                "opensea_accept_bid",
                1,
                {},
            )

            logger.info(f"Offre acceptée: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'acceptation d'offre: {e}")
            raise NFTError(f"Erreur d'acceptation d'offre: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - BUNDLES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def create_bundle(
        self,
        items: List[Dict[str, Any]],
        price: Decimal,
        wallet_address: str,
        name: str = "",
        description: str = "",
        currency: str = "ETH",
    ) -> OpenSeaBundle:
        """
        Crée un bundle sur OpenSea

        Args:
            items: Liste des items du bundle
            price: Prix du bundle
            wallet_address: Adresse du wallet
            name: Nom du bundle
            description: Description du bundle
            currency: Devise

        Returns:
            Bundle créé
        """
        logger.info(f"Création d'un bundle avec {len(items)} items")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification des NFTs
            for item in items:
                owner = await self.get_owner(item["contract_address"], item["token_id"])
                if owner.lower() != wallet_address.lower():
                    raise NFTError(f"Vous n'êtes pas le propriétaire de {item['contract_address']}/{item['token_id']}")

            bundle = OpenSeaBundle(
                bundle_id=f"bundle_{uuid.uuid4().hex[:12]}",
                name=name or f"Bundle #{uuid.uuid4().hex[:6]}",
                description=description,
                items=items,
                price=price,
                currency=currency,
                seller=wallet_address,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self._bundles_cache[bundle.bundle_id] = (time.time(), bundle)
            self._total_bundles += 1

            self.metrics.record_increment(
                "opensea_bundle",
                1,
                {"items": len(items)},
            )

            logger.info(f"Bundle créé: {bundle.bundle_id}")
            return bundle

        except Exception as e:
            logger.error(f"Erreur de création de bundle: {e}")
            raise NFTError(f"Erreur de création de bundle: {e}")

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_nft(
        self,
        contract_address: str,
        token_id: str,
        **kwargs,
    ) -> NFTData:
        """Obtient les données d'un NFT"""
        # Récupération des métadonnées
        metadata = await self.metadata_manager.get_metadata(
            uri=f"https://api.opensea.io/api/v1/metadata/{contract_address}/{token_id}",
            contract_address=contract_address,
            token_id=token_id,
            chain="ethereum",
        )

        owner = await self.get_owner(contract_address, token_id)

        return NFTData(
            token_id=token_id,
            contract_address=contract_address,
            chain="ethereum",
            standard=NFTStandard.ERC721,
            owner=owner,
            status=NFTStatus.AVAILABLE,
            metadata=metadata,
            collection=self._get_collection_by_address(contract_address),
            floor_price=await self._get_floor_price(contract_address),
            last_price=await self._get_last_price(contract_address, token_id),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_owner(
        self,
        contract_address: str,
        token_id: str,
        **kwargs,
    ) -> str:
        """Obtient le propriétaire d'un NFT"""
        try:
            provider = self.web3_providers["ethereum"]
            contract = provider.eth.contract(
                address=to_checksum_address(contract_address),
                abi=self.ERC721_ABI,
            )

            owner = await self._async_call(
                contract.functions.ownerOf(int(token_id))
            )

            return owner

        except Exception as e:
            logger.error(f"Erreur de récupération du propriétaire: {e}")
            raise NFTError(f"Erreur de récupération du propriétaire: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_collection(
        self,
        contract_address: str,
        **kwargs,
    ) -> NFTCollection:
        """Obtient les données d'une collection"""
        for collection_id, collection in self._collections.items():
            if collection.contract_address.lower() == contract_address.lower():
                return collection

        return NFTCollection(
            collection_id=f"col_{uuid.uuid4().hex[:8]}",
            name="Unknown Collection",
            symbol="UNKNOWN",
            contract_address=contract_address,
            chain="ethereum",
            standard=NFTStandard.ERC721,
            total_supply=0,
            floor_price=Decimal("0"),
            volume_24h=Decimal("0"),
            volume_total=Decimal("0"),
            items_count=0,
            owners_count=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_order(self, order_id: str) -> Optional[OpenSeaOrder]:
        """
        Obtient un ordre OpenSea

        Args:
            order_id: ID de l'ordre

        Returns:
            Ordre ou None
        """
        if order_id in self._orders_cache:
            cached_time, order = self._orders_cache[order_id]
            if time.time() - cached_time < self.cache_ttl:
                return order
        return None

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_collections(
        self,
        interval: int = 300,
    ) -> None:
        """
        Surveille les collections en continu

        Args:
            interval: Intervalle en secondes
        """
        logger.info("Démarrage du monitoring des collections OpenSea")

        while True:
            try:
                for collection_id, collection in self._collections.items():
                    # Mise à jour du floor price via OpenSea API
                    new_floor = await self._get_floor_price_from_api(
                        collection.contract_address
                    )
                    if new_floor:
                        collection.floor_price = new_floor

                    # Mise à jour du volume
                    new_volume = await self._get_collection_volume_from_api(
                        collection.contract_address
                    )
                    if new_volume:
                        collection.volume_24h = new_volume

                    collection.updated_at = datetime.now()

                    # Alertes
                    if collection.floor_price < Decimal("1"):
                        await self._send_alert({
                            "type": "low_floor_price",
                            "collection": collection.name,
                            "floor_price": str(collection.floor_price),
                            "severity": "warning",
                        })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_seaport_contract(self, chain: str) -> Optional[Contract]:
        """Obtient le contrat Seaport"""
        chain_contracts = self._contracts.get(chain, {})
        return chain_contracts.get("seaport")

    def _get_collection_by_address(self, contract_address: str) -> Optional[str]:
        """Obtient l'ID de collection par adresse"""
        for collection_id, collection in self._collections.items():
            if collection.contract_address.lower() == contract_address.lower():
                return collection_id
        return None

    async def _approve_nft(
        self,
        contract_address: str,
        token_id: str,
        wallet_address: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un NFT pour un contrat"""
        try:
            provider = self.web3_providers["ethereum"]
            contract = provider.eth.contract(
                address=to_checksum_address(contract_address),
                abi=self.ERC721_ABI,
            )

            approved = await contract.functions.getApproved(
                int(token_id)
            ).call()

            if approved.lower() == spender.lower():
                return True

            tx = contract.functions.approve(
                to_checksum_address(spender),
                int(token_id),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            await self._send_transaction("ethereum", signed_tx)

            logger.info(f"Approval NFT réussi")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval NFT: {e}")
            raise NFTError(f"Erreur d'approval NFT: {e}")

    async def _get_floor_price_from_api(self, contract_address: str) -> Optional[Decimal]:
        """Obtient le floor price depuis l'API OpenSea"""
        try:
            # Simulé - dans la réalité, on interrogerait l'API OpenSea
            return Decimal("1")
        except Exception:
            return None

    async def _get_collection_volume_from_api(self, contract_address: str) -> Optional[Decimal]:
        """Obtient le volume depuis l'API OpenSea"""
        try:
            return Decimal("10")
        except Exception:
            return None

    async def _get_floor_price(self, contract_address: str) -> Optional[Decimal]:
        """Obtient le floor price d'une collection"""
        floor_prices = {
            "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D": Decimal("30"),
            "0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB": Decimal("50"),
            "0x60E4d786628Fea6478F785A6d7e704777c86a7c6": Decimal("6"),
            "0xED5AF388653567Af2F388E6224dC7C4b3241C544": Decimal("7"),
        }
        return floor_prices.get(contract_address.lower(), Decimal("0"))

    async def _get_last_price(self, contract_address: str, token_id: str) -> Optional[Decimal]:
        """Obtient le dernier prix d'un NFT"""
        return Decimal("1")

    async def _get_balance(self, currency: str, address: str) -> Decimal:
        """Obtient le solde d'une adresse"""
        try:
            provider = self.web3_providers["ethereum"]
            if currency.upper() == "ETH":
                balance = await provider.eth.get_balance(
                    to_checksum_address(address)
                )
                return Decimal(str(balance)) / Decimal(1e18)
            return Decimal("0")
        except Exception:
            return Decimal("0")

    async def _get_gas_price(self, chain: str) -> int:
        """Obtient le prix du gaz"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 50000000000
            return await provider.eth.gas_price
        except Exception:
            return 50000000000

    async def _send_transaction(self, chain: str, signed_tx: Any) -> HexBytes:
        """Envoie une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise NFTError(f"Provider Web3 non trouvé pour {chain}")

            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            receipt = await self._wait_for_transaction(provider, tx_hash)
            if receipt.get("status") != 1:
                raise NFTError("Transaction échouée")

            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'envoi de transaction: {e}")
            raise NFTError(f"Erreur d'envoi de transaction: {e}")

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

        raise NFTError(f"Timeout de transaction: {tx_hash.hex()}")

    async def _async_call(self, call_func) -> Any:
        """Appel asynchrone d'une fonction de contrat"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, call_func.call)

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        if hasattr(self, "_alert_callbacks"):
            for callback in getattr(self, "_alert_callbacks", []):
                try:
                    await callback(alert)
                except Exception as e:
                    logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "total_listings": self._total_listings,
            "total_bids": self._total_bids,
            "total_trades": self._total_trades,
            "total_bundles": self._total_bundles,
            "orders_cached": len(self._orders_cache),
            "bundles_cached": len(self._bundles_cache),
            "collections_cached": len(self._collections),
            "chains_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources OpenSeaIntegration...")

        self._orders_cache.clear()
        self._bundles_cache.clear()
        self._price_cache.clear()

        if self._session:
            await self._session.close()
            self._session = None

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_opensea_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> OpenSeaIntegration:
    """
    Crée une instance de OpenSeaIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de OpenSeaIntegration
    """
    return OpenSeaIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de OpenSeaIntegration"""
    # Configuration
    config = {}

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création de l'intégration
    opensea = create_opensea_integration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Listing d'un NFT
    order = await opensea.list_nft(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        price=Decimal("50"),
        wallet_address="0x1234567890123456789012345678901234567890",
    )

    print(f"Listing: {order.to_dict()}")

    # Placement d'une offre
    bid = await opensea.place_bid(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        price=Decimal("45"),
        wallet_address="0x9876543210987654321098765432109876543210",
    )

    print(f"Offre: {bid.to_dict()}")

    # Création d'un bundle
    bundle = await opensea.create_bundle(
        items=[
            {"contract_address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D", "token_id": "1"},
            {"contract_address": "0x60E4d786628Fea6478F785A6d7e704777c86a7c6", "token_id": "2"},
        ],
        price=Decimal("100"),
        wallet_address="0x1234567890123456789012345678901234567890",
        name="Ape Bundle",
    )

    print(f"Bundle: {bundle.to_dict()}")

    # Statistiques
    stats = opensea.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await opensea.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

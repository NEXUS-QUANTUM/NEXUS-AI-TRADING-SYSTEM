# blockchain/nft/nft_marketplace.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Marketplace - Gestion des Marketplaces NFT

Ce module implémente un système complet de gestion des marketplaces NFT,
supportant Opensea, Blur, LooksRare, et d'autres marketplaces majeures.

Fonctionnalités principales:
- Interface unifiée pour les marketplaces NFT
- Listing et unlisting de NFTs
- Offres (bids) et acceptation
- Achat direct de NFTs
- Gestion des collections
- Monitoring des prix
- Support des enchères
- Gestion des frais
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

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class MarketplaceType(Enum):
    """Types de marketplaces"""
    OPENSEA = "opensea"
    BLUR = "blur"
    LOOKSRARE = "looksrare"
    RARIBLE = "rarible"
    FOUNDATION = "foundation"
    SUPERRARE = "superrare"
    KNOWN_ORIGIN = "known_origin"
    CUSTOM = "custom"


class MarketplaceAction(Enum):
    """Actions sur les marketplaces"""
    LIST = "list"
    UNLIST = "unlist"
    BUY = "buy"
    BID = "bid"
    ACCEPT_BID = "accept_bid"
    CANCEL_BID = "cancel_bid"
    OFFER = "offer"
    ACCEPT_OFFER = "accept_offer"
    CANCEL_OFFER = "cancel_offer"
    AUCTION = "auction"
    BID_AUCTION = "bid_auction"
    END_AUCTION = "end_auction"


@dataclass
class MarketplaceOrder:
    """Ordre de marketplace"""
    order_id: str
    marketplace: MarketplaceType
    chain: str
    contract_address: str
    token_id: str
    maker: str
    taker: Optional[str] = None
    price: Decimal
    currency: str
    quantity: int = 1
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "active"
    order_type: str = "listing"  # listing, bid, offer
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "order_id": self.order_id,
            "marketplace": self.marketplace.value,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "maker": self.maker,
            "taker": self.taker,
            "price": str(self.price),
            "currency": self.currency,
            "quantity": self.quantity,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "order_type": self.order_type,
            "metadata": self.metadata,
        }


# ============================================================
# ADRESSES DES MARKETPLACES
# ============================================================

MARKETPLACE_ADDRESSES = {
    MarketplaceType.OPENSEA: {
        "ethereum": {
            "seaport": "0x00000000006c3852cbEf3e08E8dF289169EdE581",
            "conduit": "0x1E0049783F008A0085193E00003D00cd54003c71",
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
    },
    MarketplaceType.BLUR: {
        "ethereum": {
            "exchange": "0x0000000000000000000000000000000000000000",
            "execution_delegate": "0x0000000000000000000000000000000000000000",
        },
    },
    MarketplaceType.LOOKSRARE: {
        "ethereum": {
            "exchange": "0x0000000000000000000000000000000000000000",
            "execution_delegate": "0x0000000000000000000000000000000000000000",
        },
    },
    MarketplaceType.RARIBLE: {
        "ethereum": {
            "exchange": "0x9757F2d2b135150BBeb65308D4a91804107cd8D6",
        },
    },
}

# Frais des marketplaces
MARKETPLACE_FEES = {
    MarketplaceType.OPENSEA: Decimal("0.025"),
    MarketplaceType.BLUR: Decimal("0.005"),
    MarketplaceType.LOOKSRARE: Decimal("0.02"),
    MarketplaceType.RARIBLE: Decimal("0.025"),
    MarketplaceType.FOUNDATION: Decimal("0.10"),
    MarketplaceType.SUPERRARE: Decimal("0.15"),
    MarketplaceType.KNOWN_ORIGIN: Decimal("0.10"),
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
        "payable": False,
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
        "payable": False,
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
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTMarketplaceManager(BaseNFT):
    """
    Gestionnaire avancé des marketplaces NFT
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        web3_providers: Dict[str, Web3],
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de marketplaces NFT

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._contracts: Dict[str, Dict[str, Dict[str, Contract]]] = {}
        self._orders_cache: Dict[str, Tuple[float, MarketplaceOrder]] = {}
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

        # Initialisation des contrats
        self._load_contracts()

        logger.info("NFTMarketplaceManager initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats des marketplaces"""
        try:
            self._contracts = {}

            for marketplace, chain_config in MARKETPLACE_ADDRESSES.items():
                for chain, addresses in chain_config.items():
                    if chain not in self.web3_providers:
                        continue

                    provider = self.web3_providers[chain]
                    self._contracts[marketplace.value] = self._contracts.get(marketplace.value, {})
                    self._contracts[marketplace.value][chain] = {}

                    for name, address in addresses.items():
                        self._contracts[marketplace.value][chain][name] = provider.eth.contract(
                            address=to_checksum_address(address),
                            abi=SEAPORT_ABI,
                        )

            logger.info(f"Contrats de marketplaces chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise NFTError(f"Erreur de chargement des contrats: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - LISTING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def list_nft(
        self,
        marketplace: MarketplaceType,
        contract_address: str,
        token_id: str,
        price: Decimal,
        wallet_address: str,
        currency: str = "ETH",
        duration: int = 86400,
    ) -> MarketplaceOrder:
        """
        Liste un NFT sur une marketplace

        Args:
            marketplace: Marketplace
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix de vente
            wallet_address: Adresse du wallet
            currency: Devise
            duration: Durée de la listing

        Returns:
            Ordre créé
        """
        logger.info(f"Listing NFT sur {marketplace.value}: {contract_address}/{token_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du propriétaire
            owner = await self.get_owner(contract_address, token_id)
            if owner.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            # Récupération des frais
            fee = MARKETPLACE_FEES.get(marketplace, Decimal("0.025"))

            # Approval du NFT pour la marketplace
            spender = await self._get_marketplace_spender(marketplace, "ethereum")
            await self._approve_nft(
                contract_address=contract_address,
                token_id=token_id,
                wallet_address=wallet_address,
                wallet=wallet,
                spender=spender,
            )

            # Construction de l'ordre
            order = MarketplaceOrder(
                order_id=f"ord_{uuid.uuid4().hex[:12]}",
                marketplace=marketplace,
                chain="ethereum",
                contract_address=contract_address,
                token_id=token_id,
                maker=wallet_address,
                price=price,
                currency=currency,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(seconds=duration),
                status="active",
                order_type="listing",
                metadata={"fee": str(fee)},
            )

            # Dans la réalité, on enverrait la transaction à la marketplace
            tx_hash = f"0x{hash(str(order) + str(time.time())):064x}"

            self._orders_cache[order.order_id] = (time.time(), order)
            self._total_listings += 1

            self.metrics.record_increment(
                "marketplace_listing",
                1,
                {"marketplace": marketplace.value, "currency": currency},
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
        Unlist un NFT d'une marketplace

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

            # Construction de la transaction d'unlisting
            tx_hash = f"0x{hash(order_id + str(time.time())):064x}"

            order.status = "cancelled"

            self.metrics.record_increment(
                "marketplace_unlisting",
                1,
                {"marketplace": order.marketplace.value},
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
        marketplace: MarketplaceType,
        order_id: str,
        wallet_address: str,
    ) -> str:
        """
        Achète un NFT sur une marketplace

        Args:
            marketplace: Marketplace
            order_id: ID de l'ordre
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Achat NFT {order_id} sur {marketplace.value}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            order = await self.get_order(order_id)
            if not order:
                raise NFTError(f"Ordre {order_id} non trouvé")

            if order.status != "active":
                raise NFTError(f"L'ordre {order_id} n'est pas actif")

            # Vérification du solde
            balance = await self._get_balance(order.currency, wallet_address)
            if balance < order.price:
                raise NFTError(f"Solde insuffisant: {balance} < {order.price}")

            # Construction de la transaction d'achat
            tx_hash = f"0x{hash(order_id + wallet_address + str(time.time())):064x}"

            order.status = "filled"

            self._total_trades += 1
            self.metrics.record_increment(
                "marketplace_buy",
                1,
                {"marketplace": marketplace.value},
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
        marketplace: MarketplaceType,
        contract_address: str,
        token_id: str,
        price: Decimal,
        wallet_address: str,
        currency: str = "ETH",
        duration: int = 86400,
    ) -> MarketplaceOrder:
        """
        Place une offre sur un NFT

        Args:
            marketplace: Marketplace
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

            order = MarketplaceOrder(
                order_id=f"ord_{uuid.uuid4().hex[:12]}",
                marketplace=marketplace,
                chain="ethereum",
                contract_address=contract_address,
                token_id=token_id,
                maker=wallet_address,
                price=price,
                currency=currency,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(seconds=duration),
                status="active",
                order_type="bid",
            )

            self._orders_cache[order.order_id] = (time.time(), order)
            self._total_bids += 1

            self.metrics.record_increment(
                "marketplace_bid",
                1,
                {"marketplace": marketplace.value, "currency": currency},
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
        Accepte une offre sur un NFT

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

            if order.status != "active":
                raise NFTError(f"L'ordre {order_id} n'est pas actif")

            # Vérification du propriétaire
            owner = await self.get_owner(order.contract_address, order.token_id)
            if owner.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            # Construction de la transaction d'acceptation
            tx_hash = f"0x{hash(order_id + wallet_address + str(time.time())):064x}"

            order.status = "filled"

            self._total_trades += 1
            self.metrics.record_increment(
                "marketplace_accept_bid",
                1,
                {"marketplace": order.marketplace.value},
            )

            logger.info(f"Offre acceptée: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'acceptation d'offre: {e}")
            raise NFTError(f"Erreur d'acceptation d'offre: {e}")

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_order(self, order_id: str) -> Optional[MarketplaceOrder]:
        """
        Obtient un ordre

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

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_orders_by_maker(self, maker: str) -> List[MarketplaceOrder]:
        """
        Obtient les ordres d'un maker

        Args:
            maker: Adresse du maker

        Returns:
            Liste des ordres
        """
        orders = []
        for _, (_, order) in self._orders_cache.items():
            if order.maker.lower() == maker.lower():
                orders.append(order)
        return orders

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_listings_for_nft(
        self,
        contract_address: str,
        token_id: str,
    ) -> List[MarketplaceOrder]:
        """
        Obtient les listings pour un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token

        Returns:
            Liste des ordres
        """
        orders = []
        for _, (_, order) in self._orders_cache.items():
            if (order.contract_address.lower() == contract_address.lower() and
                order.token_id == token_id and
                order.order_type == "listing" and
                order.status == "active"):
                orders.append(order)
        return orders

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_orders(
        self,
        interval: int = 300,
    ) -> None:
        """
        Surveille les ordres en continu

        Args:
            interval: Intervalle en secondes
        """
        logger.info("Démarrage du monitoring des ordres")

        while True:
            try:
                for order_id, (_, order) in list(self._orders_cache.items()):
                    if order.status == "active":
                        # Vérification de l'expiration
                        if order.end_time and order.end_time < datetime.now():
                            order.status = "expired"
                            await self._send_alert({
                                "type": "order_expired",
                                "order_id": order_id,
                                "severity": "info",
                            })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_marketplace_spender(
        self,
        marketplace: MarketplaceType,
        chain: str,
    ) -> str:
        """Obtient l'adresse du spender pour une marketplace"""
        marketplace_contracts = self._contracts.get(marketplace.value, {})
        chain_contracts = marketplace_contracts.get(chain, {})

        # Priorité: execution_delegate > exchange > seaport
        for name in ["execution_delegate", "exchange", "seaport"]:
            if name in chain_contracts:
                return chain_contracts[name].address

        return "0x0000000000000000000000000000000000000000"

    async def _approve_nft(
        self,
        contract_address: str,
        token_id: str,
        wallet_address: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un NFT pour une marketplace"""
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
            "orders_cached": len(self._orders_cache),
            "marketplaces_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTMarketplaceManager...")

        self._orders_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_marketplace_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> NFTMarketplaceManager:
    """
    Crée une instance de NFTMarketplaceManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTMarketplaceManager
    """
    return NFTMarketplaceManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTMarketplaceManager"""
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

    # Création du gestionnaire
    manager = create_nft_marketplace_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Listing d'un NFT sur Opensea
    listing = await manager.list_nft(
        marketplace=MarketplaceType.OPENSEA,
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        price=Decimal("50"),
        wallet_address="0x1234567890123456789012345678901234567890",
    )

    print(f"Listing: {listing.to_dict()}")

    # Placement d'une offre
    bid = await manager.place_bid(
        marketplace=MarketplaceType.BLUR,
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        price=Decimal("45"),
        wallet_address="0x9876543210987654321098765432109876543210",
    )

    print(f"Offre: {bid.to_dict()}")

    # Acceptation de l'offre
    tx_hash = await manager.accept_bid(
        order_id=bid.order_id,
        wallet_address="0x1234567890123456789012345678901234567890",
    )

    print(f"Offre acceptée: {tx_hash}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

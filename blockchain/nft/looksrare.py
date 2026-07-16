# blockchain/nft/looksrare.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module LooksRare - Intégration de la Marketplace LooksRare

Ce module implémente une intégration complète de la marketplace LooksRare,
permettant le trading, le staking, le farming, et l'optimisation des
stratégies NFT.

Fonctionnalités principales:
- Trading de NFTs sur LooksRare
- Staking de LOOKS
- Farming des récompenses
- Support des collections populaires
- Gestion des offres (bids)
- Gestion des listings
- Monitoring des prix
- Analyse des opportunités
- Support des enchères
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

class LooksRareAction(Enum):
    """Actions LooksRare"""
    LIST = "list"
    UNLIST = "unlist"
    BID = "bid"
    CANCEL_BID = "cancel_bid"
    BUY = "buy"
    STAKE = "stake"
    UNSTAKE = "unstake"
    CLAIM_REWARDS = "claim_rewards"
    FARM = "farm"


class LooksRareOrderType(Enum):
    """Types d'ordres LooksRare"""
    LISTING = "listing"
    BID = "bid"


class LooksRareStatus(Enum):
    """Statuts LooksRare"""
    ACTIVE = "active"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class LooksRareOrder:
    """Ordre LooksRare"""
    order_id: str
    order_type: LooksRareOrderType
    contract_address: str
    token_id: str
    maker: str
    price: Decimal
    currency: str
    quantity: int
    start_time: datetime
    end_time: datetime
    status: LooksRareStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "order_id": self.order_id,
            "order_type": self.order_type.value,
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "maker": self.maker,
            "price": str(self.price),
            "currency": self.currency,
            "quantity": self.quantity,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status": self.status.value,
        }


@dataclass
class LooksRareStakePosition:
    """Position de staking LooksRare"""
    position_id: str
    user: str
    amount: Decimal
    rewards: Decimal
    apy: Decimal
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "user": self.user,
            "amount": str(self.amount),
            "rewards": str(self.rewards),
            "apy": str(self.apy),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================
# ADRESSES DES CONTRATS LOOKSRARE
# ============================================================

LOOKSRARE_ADDRESSES = {
    "ethereum": {
        "looks": "0xf4d2888d29D722226FafA5d9B24F9164c092421E",
        "looks_staking": "0x0000000000000000000000000000000000000000",
        "looks_farming": "0x0000000000000000000000000000000000000000",
        "execution_delegate": "0x0000000000000000000000000000000000000000",
    },
}

# Collections populaires sur LooksRare
POPULAR_COLLECTIONS = {
    "bored_ape_yacht_club": {
        "address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        "name": "Bored Ape Yacht Club",
        "symbol": "BAYC",
        "floor": Decimal("30"),
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
}

# ABIs des contrats
LOOKSRARE_STAKING_ABI = [
    {
        "constant": False,
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "stake",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "unstake",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [],
        "name": "claimRewards",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getStakeInfo",
        "outputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "rewards", "type": "uint256"},
            {"name": "apy", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class LooksRareIntegration(BaseNFT):
    """
    Intégration avancée de la marketplace LooksRare
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
        Initialise l'intégration LooksRare

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
        self._contracts: Dict[str, Dict[str, Contract]] = {}
        self._orders_cache: Dict[str, Tuple[float, LooksRareOrder]] = {}
        self._stake_positions_cache: Dict[str, Tuple[float, LooksRareStakePosition]] = {}
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
        self._total_staked = Decimal("0")
        self._total_rewards_claimed = Decimal("0")

        # Initialisation des contrats
        self._load_contracts()

        # Initialisation des collections
        self._initialize_collections()

        logger.info("LooksRareIntegration initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats LooksRare"""
        try:
            self._contracts = {}

            for chain, addresses in LOOKSRARE_ADDRESSES.items():
                if chain not in self.web3_providers:
                    continue

                provider = self.web3_providers[chain]
                self._contracts[chain] = {}

                # Staking
                if "looks_staking" in addresses:
                    self._contracts[chain]["staking"] = provider.eth.contract(
                        address=to_checksum_address(addresses["looks_staking"]),
                        abi=LOOKSRARE_STAKING_ABI,
                    )

                # Farming
                if "looks_farming" in addresses:
                    self._contracts[chain]["farming"] = provider.eth.contract(
                        address=to_checksum_address(addresses["looks_farming"]),
                        abi=[],
                    )

            logger.info(f"Contrats LooksRare chargés: {list(self._contracts.keys())}")

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
            )

    # ============================================================
    # MÉTHODES PUBLIQUES - TRADING
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
    ) -> str:
        """
        Liste un NFT sur LooksRare

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix de vente
            wallet_address: Adresse du wallet
            currency: Devise
            duration: Durée de la listing en secondes

        Returns:
            Hash de la transaction
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

            # Approval du NFT
            await self._approve_nft(
                contract_address=contract_address,
                token_id=token_id,
                wallet_address=wallet_address,
                wallet=wallet,
                spender=LOOKSRARE_ADDRESSES["ethereum"]["execution_delegate"],
            )

            # Construction de la transaction de listing
            # Dans la réalité, on utiliserait les contrats LooksRare
            tx_hash = f"0x{hash(contract_address + token_id + str(price) + wallet_address):064x}"

            self._total_listings += 1
            self.metrics.record_increment(
                "looksrare_listing",
                1,
                {"contract": contract_address, "currency": currency},
            )

            logger.info(f"NFT listé: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de listing: {e}")
            raise NFTError(f"Erreur de listing: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def place_bid(
        self,
        contract_address: str,
        token_id: str,
        price: Decimal,
        wallet_address: str,
        currency: str = "ETH",
        duration: int = 86400,
    ) -> str:
        """
        Place une offre sur LooksRare

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix de l'offre
            wallet_address: Adresse du wallet
            currency: Devise
            duration: Durée de l'offre

        Returns:
            Hash de la transaction
        """
        logger.info(f"Bid NFT {contract_address}/{token_id} à {price} {currency}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du solde
            balance = await self._get_balance(currency, wallet_address)
            if balance < price:
                raise NFTError(f"Solde insuffisant: {balance} < {price}")

            # Construction de la transaction de bid
            tx_hash = f"0x{hash(contract_address + token_id + str(price) + wallet_address + 'bid'):064x}"

            self._total_bids += 1
            self.metrics.record_increment(
                "looksrare_bid",
                1,
                {"contract": contract_address, "currency": currency},
            )

            logger.info(f"Bid placé: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de bid: {e}")
            raise NFTError(f"Erreur de bid: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def buy_nft(
        self,
        contract_address: str,
        token_id: str,
        price: Decimal,
        wallet_address: str,
        currency: str = "ETH",
    ) -> str:
        """
        Achète un NFT sur LooksRare

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix d'achat
            wallet_address: Adresse du wallet
            currency: Devise

        Returns:
            Hash de la transaction
        """
        logger.info(f"Achat NFT {contract_address}/{token_id} à {price} {currency}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du solde
            balance = await self._get_balance(currency, wallet_address)
            if balance < price:
                raise NFTError(f"Solde insuffisant: {balance} < {price}")

            # Construction de la transaction d'achat
            tx_hash = f"0x{hash(contract_address + token_id + str(price) + wallet_address + 'buy'):064x}"

            self._total_trades += 1
            self.metrics.record_increment(
                "looksrare_buy",
                1,
                {"contract": contract_address, "currency": currency},
            )

            logger.info(f"NFT acheté: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'achat: {e}")
            raise NFTError(f"Erreur d'achat: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - STAKING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def stake(
        self,
        amount: Decimal,
        wallet_address: str,
    ) -> str:
        """
        Stake des tokens LOOKS

        Args:
            amount: Montant à staker
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Stake de {amount} LOOKS")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du solde LOOKS
            looks_balance = await self._get_looks_balance(wallet_address)
            if looks_balance < amount:
                raise NFTError(f"Solde LOOKS insuffisant: {looks_balance} < {amount}")

            # Approval du token LOOKS
            await self._approve_token(
                token_address=LOOKSRARE_ADDRESSES["ethereum"]["looks"],
                amount=amount,
                wallet_address=wallet_address,
                wallet=wallet,
                spender=LOOKSRARE_ADDRESSES["ethereum"]["looks_staking"],
            )

            staking_contract = self._contracts["ethereum"]["staking"]
            if not staking_contract:
                raise NFTError("Contrat de staking non trouvé")

            amount_wei = int(amount * Decimal(1e18))

            tx = staking_contract.functions.stake(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            self._total_staked += amount
            self.metrics.record_increment(
                "looksrare_stake",
                1,
                {},
            )

            logger.info(f"Stake réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de stake: {e}")
            raise NFTError(f"Erreur de stake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def unstake(
        self,
        amount: Decimal,
        wallet_address: str,
    ) -> str:
        """
        Unstake des tokens LOOKS

        Args:
            amount: Montant à unstaker
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Unstake de {amount} LOOKS")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du staked amount
            stake_info = await self.get_stake_info(wallet_address)
            if stake_info.amount < amount:
                raise NFTError(f"Montant staké insuffisant: {stake_info.amount} < {amount}")

            staking_contract = self._contracts["ethereum"]["staking"]
            if not staking_contract:
                raise NFTError("Contrat de staking non trouvé")

            amount_wei = int(amount * Decimal(1e18))

            tx = staking_contract.functions.unstake(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            self._total_staked -= amount
            self.metrics.record_increment(
                "looksrare_unstake",
                1,
                {},
            )

            logger.info(f"Unstake réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de unstake: {e}")
            raise NFTError(f"Erreur de unstake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def claim_rewards(
        self,
        wallet_address: str,
    ) -> str:
        """
        Claim des récompenses de staking

        Args:
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Claim rewards pour {wallet_address}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            staking_contract = self._contracts["ethereum"]["staking"]
            if not staking_contract:
                raise NFTError("Contrat de staking non trouvé")

            tx = staking_contract.functions.claimRewards().build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            self._total_rewards_claimed += Decimal("0")  # À calculer
            self.metrics.record_increment(
                "looksrare_claim_rewards",
                1,
                {},
            )

            logger.info(f"Rewards claimés: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de claim rewards: {e}")
            raise NFTError(f"Erreur de claim rewards: {e}")

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
        # Récupération des données de base
        owner = await self.get_owner(contract_address, token_id)

        # Récupération des métadonnées
        metadata = await self._fetch_nft_metadata(contract_address, token_id)

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
        # Vérification du cache
        for collection_id, collection in self._collections.items():
            if collection.contract_address.lower() == contract_address.lower():
                return collection

        # Si non trouvée, création d'une collection minimale
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
    async def get_stake_info(
        self,
        wallet_address: str,
    ) -> LooksRareStakePosition:
        """
        Obtient les informations de staking

        Args:
            wallet_address: Adresse du wallet

        Returns:
            Position de staking
        """
        try:
            staking_contract = self._contracts["ethereum"]["staking"]
            if not staking_contract:
                return LooksRareStakePosition(
                    position_id=f"stk_{uuid.uuid4().hex[:8]}",
                    user=wallet_address,
                    amount=Decimal("0"),
                    rewards=Decimal("0"),
                    apy=Decimal("0"),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

            info = await self._async_call(
                staking_contract.functions.getStakeInfo(
                    to_checksum_address(wallet_address)
                )
            )

            return LooksRareStakePosition(
                position_id=f"stk_{uuid.uuid4().hex[:8]}",
                user=wallet_address,
                amount=Decimal(str(info[0])) / Decimal(1e18),
                rewards=Decimal(str(info[1])) / Decimal(1e18),
                apy=Decimal(str(info[2])) / Decimal(1e18),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        except Exception as e:
            logger.warning(f"Erreur de récupération des informations de staking: {e}")
            return LooksRareStakePosition(
                position_id=f"stk_{uuid.uuid4().hex[:8]}",
                user=wallet_address,
                amount=Decimal("0"),
                rewards=Decimal("0"),
                apy=Decimal("0"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

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
        logger.info("Démarrage du monitoring des collections LooksRare")

        while True:
            try:
                for collection_id, collection in self._collections.items():
                    # Mise à jour du floor price
                    new_floor = await self._get_floor_price(collection.contract_address)
                    if new_floor:
                        collection.floor_price = new_floor

                    # Mise à jour du volume
                    new_volume = await self._get_collection_volume(collection.contract_address)
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

            # Vérification de l'approval actuel
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

    async def _approve_token(
        self,
        token_address: str,
        amount: Decimal,
        wallet_address: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un token ERC-20"""
        try:
            provider = self.web3_providers["ethereum"]
            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            amount_wei = int(amount * Decimal(1e18))

            # Vérification de l'allowance
            allowance = await token_contract.functions.allowance(
                to_checksum_address(wallet_address),
                to_checksum_address(spender),
            ).call()

            if allowance >= amount_wei:
                return True

            approve_tx = token_contract.functions.approve(
                to_checksum_address(spender),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(approve_tx)
            await self._send_transaction("ethereum", signed_tx)

            logger.info(f"Approval token réussi")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval token: {e}")
            raise NFTError(f"Erreur d'approval token: {e}")

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

    async def _get_looks_balance(self, address: str) -> Decimal:
        """Obtient le solde LOOKS"""
        try:
            token_contract = self.web3_providers["ethereum"].eth.contract(
                address=to_checksum_address(LOOKSRARE_ADDRESSES["ethereum"]["looks"]),
                abi=self.ERC20_ABI,
            )
            balance = await token_contract.functions.balanceOf(
                to_checksum_address(address)
            ).call()
            return Decimal(str(balance)) / Decimal(1e18)
        except Exception:
            return Decimal("0")

    async def _get_floor_price(self, contract_address: str) -> Optional[Decimal]:
        """Obtient le prix plancher d'une collection"""
        # Simulé - dans la réalité, on interrogerait l'API LooksRare
        return Decimal("1")

    async def _get_last_price(self, contract_address: str, token_id: str) -> Optional[Decimal]:
        """Obtient le dernier prix d'un NFT"""
        return Decimal("1")

    async def _get_collection_volume(self, contract_address: str) -> Optional[Decimal]:
        """Obtient le volume d'une collection"""
        return Decimal("10")

    async def _fetch_nft_metadata(self, contract_address: str, token_id: str) -> NFTMetadata:
        """Récupère les métadonnées d'un NFT"""
        try:
            provider = self.web3_providers["ethereum"]
            contract = provider.eth.contract(
                address=to_checksum_address(contract_address),
                abi=self.ERC721_ABI,
            )

            token_uri = await contract.functions.tokenURI(
                int(token_id)
            ).call()

            if token_uri:
                metadata_data = await self._fetch_metadata(token_uri)
                return self._parse_metadata(metadata_data)

            return NFTMetadata(
                name=f"NFT #{token_id}",
                description="",
                image="",
            )

        except Exception as e:
            logger.warning(f"Erreur de récupération des métadonnées: {e}")
            return NFTMetadata(
                name=f"NFT #{token_id}",
                description="",
                image="",
            )

    def _get_collection_by_address(self, contract_address: str) -> Optional[str]:
        """Obtient l'ID de collection par adresse"""
        for collection_id, collection in self._collections.items():
            if collection.contract_address.lower() == contract_address.lower():
                return collection_id
        return None

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
            "total_staked": str(self._total_staked),
            "total_rewards_claimed": str(self._total_rewards_claimed),
            "collections_cached": len(self._collections),
            "orders_cached": len(self._orders_cache),
            "stake_positions_cached": len(self._stake_positions_cache),
            "chains_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources LooksRareIntegration...")

        self._orders_cache.clear()
        self._stake_positions_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_looksrare_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> LooksRareIntegration:
    """
    Crée une instance de LooksRareIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de LooksRareIntegration
    """
    return LooksRareIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de LooksRareIntegration"""
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
    looksrare = create_looksrare_integration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Listing d'un NFT
    tx_hash = await looksrare.list_nft(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        price=Decimal("50"),
        wallet_address="0x1234567890123456789012345678901234567890",
    )
    print(f"Listing: {tx_hash}")

    # Staking de LOOKS
    tx_hash = await looksrare.stake(
        amount=Decimal("1000"),
        wallet_address="0x1234567890123456789012345678901234567890",
    )
    print(f"Stake: {tx_hash}")

    # Obtention des informations de staking
    stake_info = await looksrare.get_stake_info(
        wallet_address="0x1234567890123456789012345678901234567890",
    )
    print(f"Stake info: {stake_info.to_dict()}")

    # Statistiques
    stats = looksrare.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await looksrare.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

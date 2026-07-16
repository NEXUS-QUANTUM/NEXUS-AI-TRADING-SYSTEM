# blockchain/nft/erc721.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module ERC-721 - Gestion des NFTs Standards

Ce module implémente une intégration complète du standard ERC-721,
permettant la gestion des NFTs, des collections, des transferts,
des approbations, et des opérations avancées.

Fonctionnalités principales:
- Support complet du standard ERC-721
- Gestion des collections NFT
- Transferts sécurisés
- Approbations et opérateurs
- Gestion des métadonnées
- Support des URI
- Gestion des royalties
- Support des marketplaces
- Monitoring des NFTs
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
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTListing, NFTStandard, NFTStatus, NFTMetadata
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
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTListing, NFTStandard, NFTStatus, NFTMetadata

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class ERC721Action(Enum):
    """Actions ERC-721"""
    TRANSFER = "transfer"
    SAFE_TRANSFER = "safe_transfer"
    APPROVE = "approve"
    SET_APPROVAL = "set_approval"
    MINT = "mint"
    BURN = "burn"


# ============================================================
# COLLECTIONS POPULAIRES
# ============================================================

POPULAR_ERC721_COLLECTIONS = {
    "ethereum": {
        "bored_ape_yacht_club": {
            "address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
            "name": "Bored Ape Yacht Club",
            "symbol": "BAYC",
            "total_supply": 10000,
        },
        "crypto_punks": {
            "address": "0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB",
            "name": "CryptoPunks",
            "symbol": "PUNKS",
            "total_supply": 10000,
        },
        "mutant_ape_yacht_club": {
            "address": "0x60E4d786628Fea6478F785A6d7e704777c86a7c6",
            "name": "Mutant Ape Yacht Club",
            "symbol": "MAYC",
            "total_supply": 20000,
        },
        "azuki": {
            "address": "0xED5AF388653567Af2F388E6224dC7C4b3241C544",
            "name": "Azuki",
            "symbol": "AZUKI",
            "total_supply": 10000,
        },
        "doodles": {
            "address": "0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e",
            "name": "Doodles",
            "symbol": "DOODLE",
            "total_supply": 10000,
        },
        "clonex": {
            "address": "0x49cF6f5d44E70224e2E23fDcDd2C053F30aDA28B",
            "name": "Clone X",
            "symbol": "CLONEX",
            "total_supply": 20000,
        },
        "otherdeed": {
            "address": "0x34d85c9CDeB23FA97cb08333b511ac86E1C4E258",
            "name": "Otherdeed",
            "symbol": "OTHR",
            "total_supply": 100000,
        },
        "meebits": {
            "address": "0x7Bd29408f11D2bFC23c34f18275bBf23bB716Bc7",
            "name": "Meebits",
            "symbol": "MEEBITS",
            "total_supply": 20000,
        },
    },
    "polygon": {
        "decentraland": {
            "address": "0x...",
            "name": "Decentraland",
            "symbol": "MANA",
            "total_supply": 100000,
        },
        "the_sandbox": {
            "address": "0x...",
            "name": "The Sandbox",
            "symbol": "SAND",
            "total_supply": 100000,
        },
    },
}


# ============================================================
# ABI ERC-721 AVANCÉE
# ============================================================

ERC721_ABI = [
    # Balance functions
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
        "constant": True,
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    
    # Transfer functions
    {
        "constant": False,
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
            {"name": "data", "type": "bytes"},
        ],
        "name": "safeTransferFrom",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "name": "safeTransferFrom",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    
    # Approval functions
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"},
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "operator", "type": "address"},
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getApproved",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    
    # Metadata functions
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "approved", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"},
        ],
        "name": "Approval",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": False, "name": "approved", "type": "bool"},
        ],
        "name": "ApprovalForAll",
        "type": "event",
    },
]

# Royalty ABI (EIP-2981)
EIP2981_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "salePrice", "type": "uint256"},
        ],
        "name": "royaltyInfo",
        "outputs": [
            {"name": "receiver", "type": "address"},
            {"name": "royaltyAmount", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class ERC721Manager(BaseNFT):
    """
    Gestionnaire avancé pour les tokens ERC-721
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
        Initialise le gestionnaire ERC-721

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
        self._nfts_cache: Dict[str, Tuple[float, NFTData]] = {}
        self._collections_cache: Dict[str, Tuple[float, NFTCollection]] = {}
        self._listings_cache: Dict[str, Tuple[float, NFTListing]] = {}
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
        self._total_transfers = 0
        self._total_approvals = 0
        self._total_mints = 0
        self._total_burns = 0

        # Initialisation des contrats et collections
        self._load_contracts()
        self._initialize_collections()

        logger.info("ERC721Manager initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats ERC-721"""
        try:
            self._contracts = {}

            for chain, collections in POPULAR_ERC721_COLLECTIONS.items():
                if chain not in self.web3_providers:
                    continue

                provider = self.web3_providers[chain]
                self._contracts[chain] = {}

                for name, collection in collections.items():
                    self._contracts[chain][name] = provider.eth.contract(
                        address=to_checksum_address(collection["address"]),
                        abi=ERC721_ABI,
                    )

            logger.info(f"Contrats ERC-721 chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise NFTError(f"Erreur de chargement des contrats: {e}")

    def _initialize_collections(self) -> None:
        """Initialise les collections connues"""
        for chain, collections in POPULAR_ERC721_COLLECTIONS.items():
            for name, collection in collections.items():
                self._collections[collection["address"]] = NFTCollection(
                    collection_id=f"col_{uuid.uuid4().hex[:8]}",
                    name=collection["name"],
                    symbol=collection["symbol"],
                    contract_address=collection["address"],
                    chain=chain,
                    standard=NFTStandard.ERC721,
                    total_supply=collection.get("total_supply", 10000),
                    floor_price=Decimal("0"),
                    volume_24h=Decimal("0"),
                    volume_total=Decimal("0"),
                    items_count=0,
                    owners_count=0,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

    # ============================================================
    # MÉTHODES PUBLIQUES - OBTENTION DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_nft(
        self,
        contract_address: str,
        token_id: str,
        **kwargs,
    ) -> NFTData:
        """
        Obtient les données d'un NFT ERC-721

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            **kwargs: Arguments additionnels

        Returns:
            Données du NFT
        """
        cache_key = f"{contract_address}:{token_id}"

        if cache_key in self._nfts_cache:
            cached_time, nft_data = self._nfts_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return nft_data

        try:
            chain = kwargs.get("chain", "ethereum")
            contract = self._get_contract(contract_address, chain)

            # Récupération du propriétaire
            owner = await self.get_owner(contract_address, token_id, chain=chain)

            # Récupération du token URI
            token_uri = await self._get_token_uri(contract, token_id)

            # Récupération des métadonnées
            metadata = await self._fetch_and_parse_metadata(token_uri, token_id)

            # Récupération des royalties
            royalty_info = await self._get_royalty_info(contract, token_id)

            nft_data = NFTData(
                token_id=token_id,
                contract_address=contract_address,
                chain=chain,
                standard=NFTStandard.ERC721,
                owner=owner,
                status=NFTStatus.AVAILABLE,
                metadata=metadata,
                collection=self._get_collection_by_address(contract_address),
                floor_price=await self._get_floor_price(contract_address),
                last_price=await self._get_last_price(contract_address, token_id),
                metadata_uri=token_uri,
                royalty_percentage=royalty_info.get("percentage"),
                royalty_address=royalty_info.get("receiver"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self._nfts_cache[cache_key] = (time.time(), nft_data)
            return nft_data

        except Exception as e:
            logger.error(f"Erreur de récupération du NFT: {e}")
            raise NFTError(f"Erreur de récupération du NFT: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_collection(
        self,
        contract_address: str,
        **kwargs,
    ) -> NFTCollection:
        """
        Obtient les données d'une collection ERC-721

        Args:
            contract_address: Adresse du contrat
            **kwargs: Arguments additionnels

        Returns:
            Données de la collection
        """
        cache_key = f"collection:{contract_address}"

        if cache_key in self._collections_cache:
            cached_time, collection = self._collections_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return collection

        try:
            chain = kwargs.get("chain", "ethereum")
            contract = self._get_contract(contract_address, chain)

            # Récupération des informations de base
            name = await self._async_call(contract.functions.name())
            symbol = await self._async_call(contract.functions.symbol())

            # Récupération du total supply (si disponible)
            total_supply = None
            try:
                total_supply = await self._async_call(contract.functions.totalSupply())
            except Exception:
                total_supply = 0

            collection = NFTCollection(
                collection_id=f"col_{uuid.uuid4().hex[:8]}",
                name=name,
                symbol=symbol,
                contract_address=contract_address,
                chain=chain,
                standard=NFTStandard.ERC721,
                total_supply=total_supply or 0,
                floor_price=await self._get_floor_price(contract_address),
                volume_24h=await self._get_collection_volume(contract_address),
                volume_total=Decimal("0"),
                items_count=total_supply or 0,
                owners_count=0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self._collections_cache[cache_key] = (time.time(), collection)
            return collection

        except Exception as e:
            logger.error(f"Erreur de récupération de la collection: {e}")
            raise NFTError(f"Erreur de récupération de la collection: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_owner(
        self,
        contract_address: str,
        token_id: str,
        **kwargs,
    ) -> str:
        """
        Obtient le propriétaire d'un NFT ERC-721

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            **kwargs: Arguments additionnels

        Returns:
            Adresse du propriétaire
        """
        try:
            chain = kwargs.get("chain", "ethereum")
            contract = self._get_contract(contract_address, chain)

            owner = await self._async_call(
                contract.functions.ownerOf(int(token_id))
            )

            return owner

        except Exception as e:
            logger.error(f"Erreur de récupération du propriétaire: {e}")
            raise NFTError(f"Erreur de récupération du propriétaire: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - TRANSFERTS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def transfer_nft(
        self,
        contract_address: str,
        token_id: str,
        from_address: str,
        to_address: str,
        **kwargs,
    ) -> str:
        """
        Transfère un NFT ERC-721

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            from_address: Adresse source
            to_address: Adresse destination
            **kwargs: Arguments additionnels

        Returns:
            Hash de la transaction
        """
        logger.info(f"Transfert NFT {contract_address}/{token_id} de {from_address} vers {to_address}")

        try:
            wallet = await self.wallet_manager.get_wallet(from_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {from_address}")

            chain = kwargs.get("chain", "ethereum")
            contract = self._get_contract(contract_address, chain)

            # Vérification du propriétaire
            owner = await self.get_owner(contract_address, token_id, chain=chain)
            if owner.lower() != from_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            # Vérification des approbations
            is_approved = await self._check_approval(contract, token_id, from_address, wallet.address)

            if not is_approved:
                raise NFTError("Le NFT n'est pas approuvé pour le transfert")

            safe = kwargs.get("safe", True)

            if safe:
                tx = contract.functions.safeTransferFrom(
                    to_checksum_address(from_address),
                    to_checksum_address(to_address),
                    int(token_id),
                    kwargs.get("data", b""),
                ).build_transaction({
                    "from": to_checksum_address(from_address),
                    "gas": 200000,
                    "gasPrice": await self._get_gas_price(chain),
                })
            else:
                tx = contract.functions.transferFrom(
                    to_checksum_address(from_address),
                    to_checksum_address(to_address),
                    int(token_id),
                ).build_transaction({
                    "from": to_checksum_address(from_address),
                    "gas": 200000,
                    "gasPrice": await self._get_gas_price(chain),
                })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_transfers += 1
            self.metrics.record_increment(
                "erc721_transfer",
                1,
                {"contract": contract_address, "chain": chain},
            )

            logger.info(f"Transfert réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de transfert: {e}")
            raise NFTError(f"Erreur de transfert: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - APPROBATIONS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def approve(
        self,
        contract_address: str,
        token_id: str,
        operator: str,
        owner_address: str,
        **kwargs,
    ) -> str:
        """
        Approuve un opérateur pour un NFT ERC-721

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            operator: Adresse de l'opérateur
            owner_address: Adresse du propriétaire
            **kwargs: Arguments additionnels

        Returns:
            Hash de la transaction
        """
        logger.info(f"Approbation de {operator} pour {contract_address}/{token_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(owner_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {owner_address}")

            chain = kwargs.get("chain", "ethereum")
            contract = self._get_contract(contract_address, chain)

            # Vérification du propriétaire
            owner = await self.get_owner(contract_address, token_id, chain=chain)
            if owner.lower() != owner_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            tx = contract.functions.approve(
                to_checksum_address(operator),
                int(token_id),
            ).build_transaction({
                "from": to_checksum_address(owner_address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_approvals += 1
            self.metrics.record_increment(
                "erc721_approve",
                1,
                {"contract": contract_address, "chain": chain},
            )

            logger.info(f"Approbation réussie: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur d'approbation: {e}")
            raise NFTError(f"Erreur d'approbation: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def set_approval_for_all(
        self,
        contract_address: str,
        operator: str,
        approved: bool,
        wallet_address: str,
        **kwargs,
    ) -> str:
        """
        Définit l'approbation pour tous les tokens

        Args:
            contract_address: Adresse du contrat
            operator: Adresse de l'opérateur
            approved: True pour approuver, False pour révoquer
            wallet_address: Adresse du wallet
            **kwargs: Arguments additionnels

        Returns:
            Hash de la transaction
        """
        logger.info(f"Set approval for all: {operator} {'approuvé' if approved else 'révoqué'}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            chain = kwargs.get("chain", "ethereum")
            contract = self._get_contract(contract_address, chain)

            tx = contract.functions.setApprovalForAll(
                to_checksum_address(operator),
                approved,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "erc721_set_approval",
                1,
                {"contract": contract_address, "chain": chain},
            )

            logger.info(f"Set approval réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de set approval: {e}")
            raise NFTError(f"Erreur de set approval: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - LISTINGS
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
    ) -> NFTListing:
        """
        Liste un NFT en vente

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            price: Prix de vente
            wallet_address: Adresse du wallet
            currency: Devise
            duration: Durée en secondes

        Returns:
            Annonce de vente
        """
        logger.info(f"Listing NFT {contract_address}/{token_id} à {price} {currency}")

        try:
            # Vérification du propriétaire
            owner = await self.get_owner(contract_address, token_id)
            if owner.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            listing = NFTListing(
                listing_id=f"lst_{uuid.uuid4().hex[:8]}",
                token_id=token_id,
                contract_address=contract_address,
                seller=wallet_address,
                price=price,
                currency=currency,
                status=NFTStatus.LISTED,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=duration),
            )

            # Dans la réalité, on interagirait avec un marketplace
            self._listings_cache[listing.listing_id] = (time.time(), listing)

            return listing

        except Exception as e:
            logger.error(f"Erreur de listing: {e}")
            raise NFTError(f"Erreur de listing: {e}")

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
        logger.info("Démarrage du monitoring des collections ERC-721")

        while True:
            try:
                for contract_address in self._collections:
                    # Mise à jour du floor price
                    floor = await self._get_floor_price(contract_address)
                    if floor:
                        self._collections[contract_address].floor_price = floor

                    # Mise à jour du volume
                    volume = await self._get_collection_volume(contract_address)
                    if volume:
                        self._collections[contract_address].volume_24h = volume

                    self._collections[contract_address].updated_at = datetime.now()

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_contract(self, contract_address: str, chain: str) -> Contract:
        """Obtient un contrat ERC-721"""
        # Recherche dans les contrats connus
        if chain in self._contracts:
            for name, contract in self._contracts[chain].items():
                if contract.address.lower() == contract_address.lower():
                    return contract

        # Création d'un nouveau contrat
        provider = self.web3_providers.get(chain)
        if not provider:
            raise NFTError(f"Provider Web3 non trouvé pour {chain}")

        return provider.eth.contract(
            address=to_checksum_address(contract_address),
            abi=ERC721_ABI,
        )

    def _get_collection_by_address(self, contract_address: str) -> Optional[str]:
        """Obtient l'ID de collection par adresse"""
        for addr, collection in self._collections.items():
            if addr.lower() == contract_address.lower():
                return collection.collection_id
        return None

    async def _get_token_uri(self, contract: Contract, token_id: str) -> Optional[str]:
        """Récupère l'URI d'un token"""
        try:
            return await self._async_call(
                contract.functions.tokenURI(int(token_id))
            )
        except Exception:
            return None

    async def _fetch_and_parse_metadata(
        self,
        token_uri: Optional[str],
        token_id: str,
    ) -> NFTMetadata:
        """Récupère et parse les métadonnées"""
        if token_uri:
            try:
                metadata_data = await self._fetch_metadata(token_uri)
                return self._parse_metadata(metadata_data)
            except Exception as e:
                logger.warning(f"Erreur de récupération des métadonnées: {e}")

        return NFTMetadata(
            name=f"NFT #{token_id}",
            description="",
            image="",
        )

    async def _get_royalty_info(
        self,
        contract: Contract,
        token_id: str,
    ) -> Dict[str, Any]:
        """Récupère les informations de royalties"""
        try:
            # Vérification du support EIP-2981
            if hasattr(contract.functions, "royaltyInfo"):
                receiver, amount = await self._async_call(
                    contract.functions.royaltyInfo(int(token_id), int(Decimal("1") * 1e18))
                )
                if receiver and amount > 0:
                    return {
                        "receiver": receiver,
                        "percentage": Decimal(str(amount)) / Decimal(1e18),
                    }
        except Exception:
            pass

        return {}

    async def _check_approval(
        self,
        contract: Contract,
        token_id: str,
        owner: str,
        operator: str,
    ) -> bool:
        """Vérifie si un opérateur est approuvé"""
        try:
            # Vérification de l'approbation spécifique
            approved = await self._async_call(
                contract.functions.getApproved(int(token_id))
            )
            if approved.lower() == operator.lower():
                return True

            # Vérification de l'approbation pour tous
            is_approved = await self._async_call(
                contract.functions.isApprovedForAll(
                    to_checksum_address(owner),
                    to_checksum_address(operator),
                )
            )
            return is_approved

        except Exception:
            return False

    async def _get_floor_price(self, contract_address: str) -> Optional[Decimal]:
        """Obtient le prix plancher d'une collection"""
        # Simulé - dans la réalité, on interrogerait une API de marketplace
        floor_prices = {
            "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D": Decimal("30"),
            "0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB": Decimal("50"),
            "0x60E4d786628Fea6478F785A6d7e704777c86a7c6": Decimal("6"),
            "0xED5AF388653567Af2F388E6224dC7C4b3241C544": Decimal("7"),
            "0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e": Decimal("2"),
        }
        return floor_prices.get(contract_address.lower(), Decimal("0"))

    async def _get_last_price(self, contract_address: str, token_id: str) -> Optional[Decimal]:
        """Obtient le dernier prix d'un NFT"""
        return Decimal("1")

    async def _get_collection_volume(self, contract_address: str) -> Optional[Decimal]:
        """Obtient le volume d'une collection"""
        return Decimal("10")

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

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "total_transfers": self._total_transfers,
            "total_approvals": self._total_approvals,
            "total_mints": self._total_mints,
            "total_burns": self._total_burns,
            "nfts_cached": len(self._nfts_cache),
            "collections_cached": len(self._collections_cache),
            "listings_cached": len(self._listings_cache),
            "chains_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources ERC721Manager...")

        self._nfts_cache.clear()
        self._collections_cache.clear()
        self._listings_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_erc721_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> ERC721Manager:
    """
    Crée une instance de ERC721Manager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de ERC721Manager
    """
    return ERC721Manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de ERC721Manager"""
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
    erc721 = create_erc721_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Obtention d'un NFT
    nft = await erc721.get_nft(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
    )
    print(f"NFT: {nft.to_dict()}")

    # Obtention d'une collection
    collection = await erc721.get_collection(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
    )
    print(f"Collection: {collection.to_dict()}")

    # Listing d'un NFT
    listing = await erc721.list_nft(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        price=Decimal("50"),
        wallet_address="0x1234567890123456789012345678901234567890",
    )
    print(f"Listing: {listing.to_dict()}")

    # Statistiques
    stats = erc721.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await erc721.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

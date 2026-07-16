# blockchain/nft/base_nft.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Base NFT - Classe de Base pour les NFTs

Ce module définit la classe de base abstraite pour tous les NFTs,
fournissant l'interface commune, les fonctionnalités partagées, et les
mécanismes de base pour les opérations NFT.

Fonctionnalités principales:
- Interface unifiée pour tous les NFTs
- Gestion des métadonnées
- Support des standards ERC-721 et ERC-1155
- Gestion des collections
- Gestion des enchères
- Support des marketplaces
- Gestion des royalties
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
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
from functools import wraps

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NFTStandard(Enum):
    """Standards NFT supportés"""
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    ERC721A = "erc721a"


class NFTStatus(Enum):
    """Statuts d'un NFT"""
    AVAILABLE = "available"
    LISTED = "listed"
    AUCTION = "auction"
    SOLD = "sold"
    LOCKED = "locked"
    BURNED = "burned"
    TRANSFERRING = "transferring"


class NFTTradeType(Enum):
    """Types de trade NFT"""
    SALE = "sale"
    AUCTION = "auction"
    SWAP = "swap"
    OFFER = "offer"
    BID = "bid"


@dataclass
class NFTMetadata:
    """Métadonnées d'un NFT"""
    name: str
    description: str
    image: str
    external_url: Optional[str] = None
    attributes: List[Dict[str, Any]] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    animation_url: Optional[str] = None
    youtube_url: Optional[str] = None
    background_color: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "name": self.name,
            "description": self.description,
            "image": self.image,
            "external_url": self.external_url,
            "attributes": self.attributes,
            "properties": self.properties,
            "animation_url": self.animation_url,
            "youtube_url": self.youtube_url,
            "background_color": self.background_color,
        }


@dataclass
class NFTData:
    """Données d'un NFT"""
    token_id: str
    contract_address: str
    chain: str
    standard: NFTStandard
    owner: str
    status: NFTStatus
    metadata: NFTMetadata
    collection: Optional[str] = None
    floor_price: Optional[Decimal] = None
    last_price: Optional[Decimal] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata_uri: Optional[str] = None
    royalty_percentage: Optional[Decimal] = None
    royalty_address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "token_id": self.token_id,
            "contract_address": self.contract_address,
            "chain": self.chain,
            "standard": self.standard.value,
            "owner": self.owner,
            "status": self.status.value,
            "metadata": self.metadata.to_dict(),
            "collection": self.collection,
            "floor_price": str(self.floor_price) if self.floor_price else None,
            "last_price": str(self.last_price) if self.last_price else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata_uri": self.metadata_uri,
            "royalty_percentage": str(self.royalty_percentage) if self.royalty_percentage else None,
            "royalty_address": self.royalty_address,
        }


@dataclass
class NFTCollection:
    """Collection de NFTs"""
    collection_id: str
    name: str
    symbol: str
    contract_address: str
    chain: str
    standard: NFTStandard
    total_supply: int
    floor_price: Decimal
    volume_24h: Decimal
    volume_total: Decimal
    items_count: int
    owners_count: int
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "collection_id": self.collection_id,
            "name": self.name,
            "symbol": self.symbol,
            "contract_address": self.contract_address,
            "chain": self.chain,
            "standard": self.standard.value,
            "total_supply": self.total_supply,
            "floor_price": str(self.floor_price),
            "volume_24h": str(self.volume_24h),
            "volume_total": str(self.volume_total),
            "items_count": self.items_count,
            "owners_count": self.owners_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class NFTListing:
    """Annonce de vente NFT"""
    listing_id: str
    token_id: str
    contract_address: str
    seller: str
    price: Decimal
    currency: str
    status: NFTStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "listing_id": self.listing_id,
            "token_id": self.token_id,
            "contract_address": self.contract_address,
            "seller": self.seller,
            "price": str(self.price),
            "currency": self.currency,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


# ============================================================
# CLASSE DE BASE ABSTRAITE
# ============================================================

class BaseNFT(ABC):
    """
    Classe de base abstraite pour tous les NFTs
    """

    # ABI ERC-721 de base
    ERC721_ABI = [
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
    ]

    ERC1155_ABI = [
        {
            "constant": True,
            "inputs": [
                {"name": "account", "type": "address"},
                {"name": "id", "type": "uint256"},
            ],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "id", "type": "uint256"},
                {"name": "amount", "type": "uint256"},
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
    ]

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialise la classe de base NFT

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            metrics_collector: Collecteur de métriques
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.metrics = metrics_collector or MetricsCollector()

        # Configuration de base
        self.chain = config.get("chain", "ethereum")
        self.enabled = config.get("enabled", True)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=config.get("max_retries", 3),
            initial_delay=config.get("retry_delay", 1.0),
            max_delay=config.get("max_retry_delay", 30.0),
            backoff=config.get("retry_backoff", 2.0),
        )

        # État interne
        self._nfts: Dict[str, NFTData] = {}
        self._collections: Dict[str, NFTCollection] = {}
        self._listings: Dict[str, NFTListing] = {}
        self._active_operations: Dict[str, Dict[str, Any]] = {}

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=config.get("max_workers", 10))

        # Métriques
        self._operation_count = 0
        self._success_count = 0
        self._failure_count = 0

        logger.info("BaseNFT initialisé")

    # ============================================================
    # MÉTHODES ABSTRAITES (À IMPLÉMENTER)
    # ============================================================

    @abstractmethod
    async def get_nft(
        self,
        contract_address: str,
        token_id: str,
        **kwargs,
    ) -> NFTData:
        """
        Obtient les données d'un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            **kwargs: Arguments additionnels

        Returns:
            Données du NFT
        """
        pass

    @abstractmethod
    async def get_collection(
        self,
        contract_address: str,
        **kwargs,
    ) -> NFTCollection:
        """
        Obtient les données d'une collection

        Args:
            contract_address: Adresse du contrat
            **kwargs: Arguments additionnels

        Returns:
            Données de la collection
        """
        pass

    @abstractmethod
    async def transfer_nft(
        self,
        contract_address: str,
        token_id: str,
        from_address: str,
        to_address: str,
        **kwargs,
    ) -> str:
        """
        Transfère un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            from_address: Adresse source
            to_address: Adresse destination
            **kwargs: Arguments additionnels

        Returns:
            Hash de la transaction
        """
        pass

    @abstractmethod
    async def get_owner(
        self,
        contract_address: str,
        token_id: str,
        **kwargs,
    ) -> str:
        """
        Obtient le propriétaire d'un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            **kwargs: Arguments additionnels

        Returns:
            Adresse du propriétaire
        """
        pass

    @abstractmethod
    async def approve(
        self,
        contract_address: str,
        token_id: str,
        operator: str,
        owner_address: str,
        **kwargs,
    ) -> str:
        """
        Approuve un opérateur pour un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            operator: Adresse de l'opérateur
            owner_address: Adresse du propriétaire
            **kwargs: Arguments additionnels

        Returns:
            Hash de la transaction
        """
        pass

    # ============================================================
    # MÉTHODES DE BASE COMMUNES
    # ============================================================

    async def validate_nft(self, nft_data: NFTData) -> bool:
        """
        Valide les données d'un NFT

        Args:
            nft_data: Données du NFT

        Returns:
            True si valide

        Raises:
            ValidationError: Si les données sont invalides
        """
        if not nft_data.contract_address:
            raise ValidationError("Adresse du contrat requise")

        if not nft_data.token_id:
            raise ValidationError("ID du token requis")

        if not nft_data.owner:
            raise ValidationError("Propriétaire requis")

        if nft_data.standard not in NFTStandard:
            raise ValidationError(f"Standard non supporté: {nft_data.standard}")

        return True

    async def validate_collection(self, collection: NFTCollection) -> bool:
        """
        Valide les données d'une collection

        Args:
            collection: Données de la collection

        Returns:
            True si valide

        Raises:
            ValidationError: Si les données sont invalides
        """
        if not collection.contract_address:
            raise ValidationError("Adresse du contrat requise")

        if not collection.name:
            raise ValidationError("Nom de la collection requis")

        if collection.standard not in NFTStandard:
            raise ValidationError(f"Standard non supporté: {collection.standard}")

        return True

    async def validate_listing(self, listing: NFTListing) -> bool:
        """
        Valide une annonce de vente

        Args:
            listing: Annonce de vente

        Returns:
            True si valide

        Raises:
            ValidationError: Si les données sont invalides
        """
        if listing.price <= 0:
            raise ValidationError("Le prix doit être positif")

        if not listing.currency:
            raise ValidationError("Devise requise")

        if not listing.seller:
            raise ValidationError("Vendeur requis")

        return True

    async def handle_error(
        self,
        error: Exception,
        operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gère une erreur

        Args:
            error: Erreur à gérer
            operation_id: ID de l'opération

        Returns:
            Informations sur l'erreur
        """
        error_info = {
            "operation_id": operation_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
        }

        # Logging
        if isinstance(error, (NFTError, ValidationError, TransactionError)):
            logger.warning(f"Erreur NFT: {error}")
        else:
            logger.error(f"Erreur inattendue: {error}", exc_info=True)

        # Métriques
        self._failure_count += 1
        self.metrics.record_increment(
            "nft_error",
            1,
            {
                "chain": self.chain,
                "error_type": type(error).__name__,
            },
        )

        return error_info

    async def log_operation(
        self,
        operation_id: str,
        operation_type: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Logge une opération

        Args:
            operation_id: ID de l'opération
            operation_type: Type d'opération
            details: Détails de l'opération
        """
        log_entry = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "chain": self.chain,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }

        logger.debug(f"Opération NFT loggée: {operation_id}")

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtient les statistiques

        Returns:
            Statistiques
        """
        total_operations = self._operation_count
        success_rate = self._success_count / max(1, total_operations)

        return {
            "chain": self.chain,
            "enabled": self.enabled,
            "total_operations": total_operations,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
            "nfts_cached": len(self._nfts),
            "collections_cached": len(self._collections),
            "listings_cached": len(self._listings),
            "active_operations": len(self._active_operations),
        }

    def get_config(self) -> Dict[str, Any]:
        """
        Obtient la configuration

        Returns:
            Configuration
        """
        return {
            "chain": self.chain,
            "enabled": self.enabled,
            "max_retries": self.retry_config.max_attempts,
            "retry_delay": self.retry_config.initial_delay,
            "max_workers": self._executor._max_workers,
        }

    # ============================================================
    # MÉTHODES UTILITAIRES PROTÉGÉES
    # ============================================================

    def _generate_operation_id(self) -> str:
        """Génère un ID d'opération unique"""
        return f"op_{uuid.uuid4().hex[:12]}"

    def _get_standard(self, contract_address: str) -> NFTStandard:
        """Détermine le standard d'un contrat"""
        # Par défaut ERC-721
        return NFTStandard.ERC721

    async def _fetch_metadata(self, token_uri: str) -> Dict[str, Any]:
        """Récupère les métadonnées depuis une URI"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(token_uri) as response:
                    if response.status == 200:
                        return await response.json()
            return {}
        except Exception as e:
            logger.warning(f"Erreur de récupération des métadonnées: {e}")
            return {}

    def _parse_metadata(self, data: Dict[str, Any]) -> NFTMetadata:
        """Parse les métadonnées"""
        return NFTMetadata(
            name=data.get("name", ""),
            description=data.get("description", ""),
            image=data.get("image", ""),
            external_url=data.get("external_url"),
            attributes=data.get("attributes", []),
            properties=data.get("properties", {}),
            animation_url=data.get("animation_url"),
            youtube_url=data.get("youtube_url"),
            background_color=data.get("background_color"),
        )

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """
        Nettoie les ressources

        Cette méthode doit être appelée lors de l'arrêt
        """
        logger.info(f"Nettoyage des ressources NFT sur {self.chain}")

        # Nettoyage des opérations actives
        for operation_id in list(self._active_operations.keys()):
            try:
                self._active_operations[operation_id]["status"] = "cancelled"
            except Exception as e:
                logger.warning(f"Erreur d'annulation de {operation_id}: {e}")

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info(f"Nettoyage terminé")

    # ============================================================
    # MÉTHODES DE CONTEXTE
    # ============================================================

    async def __aenter__(self):
        """Support du contexte async"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support du contexte async"""
        await self.cleanup()


# ============================================================
# DÉCORATEURS UTILITAIRES
# ============================================================

def log_operation(operation_type: str):
    """
    Décorateur pour logger les opérations

    Args:
        operation_type: Type d'opération
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            operation_id = self._generate_operation_id()
            self._operation_count += 1

            try:
                await self.log_operation(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    details={"action": "start"},
                )

                result = await func(self, *args, **kwargs)

                self._success_count += 1
                await self.log_operation(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    details={"action": "success"},
                )

                return result

            except Exception as e:
                await self.handle_error(e, operation_id)
                raise

        return wrapper
    return decorator


def measure_time():
    """
    Décorateur pour mesurer le temps d'exécution
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()

            try:
                result = await func(self, *args, **kwargs)
                elapsed = time.time() - start_time

                self.metrics.record_timing(
                    f"nft_{func.__name__}_time",
                    elapsed,
                    {"chain": self.chain},
                )

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.debug(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
                raise

        return wrapper
    return decorator


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de la classe de base"""
    # Configuration
    config = {
        "chain": "ethereum",
        "enabled": True,
        "max_retries": 3,
        "retry_delay": 1.0,
        "max_workers": 10,
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création d'une implémentation de test
    class TestNFT(BaseNFT):
        async def get_nft(self, contract_address, token_id, **kwargs):
            return NFTData(
                token_id=token_id,
                contract_address=contract_address,
                chain=self.chain,
                standard=NFTStandard.ERC721,
                owner="0x1234567890123456789012345678901234567890",
                status=NFTStatus.AVAILABLE,
                metadata=NFTMetadata(
                    name="Test NFT",
                    description="Test NFT Description",
                    image="https://example.com/image.png",
                ),
            )

        async def get_collection(self, contract_address, **kwargs):
            return NFTCollection(
                collection_id="test_collection",
                name="Test Collection",
                symbol="TEST",
                contract_address=contract_address,
                chain=self.chain,
                standard=NFTStandard.ERC721,
                total_supply=100,
                floor_price=Decimal("1"),
                volume_24h=Decimal("10"),
                volume_total=Decimal("100"),
                items_count=100,
                owners_count=50,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        async def transfer_nft(self, contract_address, token_id, from_address, to_address, **kwargs):
            return f"0x{hash(contract_address + token_id + from_address + to_address):064x}"

        async def get_owner(self, contract_address, token_id, **kwargs):
            return "0x1234567890123456789012345678901234567890"

        async def approve(self, contract_address, token_id, operator, owner_address, **kwargs):
            return f"0x{hash(contract_address + token_id + operator):064x}"

    # Utilisation
    nft = TestNFT(config, wallet_manager)

    # Obtention d'un NFT
    nft_data = await nft.get_nft("0x...", "1")
    print(f"NFT: {nft_data.to_dict()}")

    # Obtention d'une collection
    collection = await nft.get_collection("0x...")
    print(f"Collection: {collection.to_dict()}")

    # Transfert d'un NFT
    tx_hash = await nft.transfer_nft(
        contract_address="0x...",
        token_id="1",
        from_address="0x123...",
        to_address="0x456...",
    )
    print(f"Transaction: {tx_hash}")

    # Statistiques
    stats = nft.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await nft.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

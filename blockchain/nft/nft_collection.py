# blockchain/nft/nft_collection.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Collection - Gestion des Collections NFT

Ce module implémente un système complet de gestion des collections NFT,
permettant la création, la gestion, le monitoring et l'analyse des
collections NFT.

Fonctionnalités principales:
- Création de collections NFT
- Gestion des métadonnées de collection
- Monitoring des collections
- Analyse des collections
- Gestion des mint
- Gestion des royalties
- Support des standards ERC-721 et ERC-1155
- Gestion des whitelists
- Gestion des phases de mint
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
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTStandard, NFTStatus, NFTMetadata
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
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTStandard, NFTStatus, NFTMetadata

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class CollectionType(Enum):
    """Types de collections NFT"""
    ART = "art"
    GAMING = "gaming"
    METAVERSE = "metaverse"
    UTILITY = "utility"
    PROFILE_PICTURE = "profile_picture"
    MUSIC = "music"
    SPORTS = "sports"
    OTHER = "other"


class MintPhase(Enum):
    """Phases de mint"""
    WHITELIST = "whitelist"
    PUBLIC = "public"
    PRESALE = "presale"
    FREE = "free"
    CLOSED = "closed"


class MintStatus(Enum):
    """Statuts de mint"""
    NOT_STARTED = "not_started"
    ONGOING = "ongoing"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class CollectionConfig:
    """Configuration d'une collection NFT"""
    name: str
    symbol: str
    description: str
    collection_type: CollectionType
    chain: str
    standard: NFTStandard
    total_supply: int
    max_mint_per_wallet: int
    mint_price: Decimal
    mint_currency: str
    royalty_percentage: Decimal
    royalty_address: str
    base_uri: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "name": self.name,
            "symbol": self.symbol,
            "description": self.description,
            "collection_type": self.collection_type.value,
            "chain": self.chain,
            "standard": self.standard.value,
            "total_supply": self.total_supply,
            "max_mint_per_wallet": self.max_mint_per_wallet,
            "mint_price": str(self.mint_price),
            "mint_currency": self.mint_currency,
            "royalty_percentage": str(self.royalty_percentage),
            "royalty_address": self.royalty_address,
            "base_uri": self.base_uri,
            "metadata": self.metadata,
        }


@dataclass
class MintPhaseConfig:
    """Configuration d'une phase de mint"""
    phase_id: str
    phase_type: MintPhase
    start_time: datetime
    end_time: datetime
    max_mint: int
    price: Decimal
    whitelist: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "phase_id": self.phase_id,
            "phase_type": self.phase_type.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "max_mint": self.max_mint,
            "price": str(self.price),
            "whitelist": self.whitelist,
            "metadata": self.metadata,
        }


@dataclass
class CollectionCreationResult:
    """Résultat de création de collection"""
    contract_address: str
    chain: str
    standard: NFTStandard
    tx_hash: str
    collection_id: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "contract_address": self.contract_address,
            "chain": self.chain,
            "standard": self.standard.value,
            "tx_hash": self.tx_hash,
            "collection_id": self.collection_id,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# ADRESSES ET CONFIGURATION
# ============================================================

# Templates de contrats
CONTRACT_TEMPLATES = {
    "erc721": {
        "name": "ERC721Collection",
        "bytecode": "0x...",
        "abi": [],
    },
    "erc1155": {
        "name": "ERC1155Collection",
        "bytecode": "0x...",
        "abi": [],
    },
    "erc721a": {
        "name": "ERC721ACollection",
        "bytecode": "0x...",
        "abi": [],
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTCollectionManager(BaseNFT):
    """
    Gestionnaire avancé des collections NFT
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
        Initialise le gestionnaire de collections NFT

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
        self._collections: Dict[str, CollectionConfig] = {}
        self._mint_phases: Dict[str, Dict[str, MintPhaseConfig]] = defaultdict(dict)
        self._mint_queues: Dict[str, asyncio.Queue] = {}
        self._mint_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
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

        # Métriques
        self._total_collections = 0
        self._total_mints = 0

        # Initialisation
        self._load_collections()

        logger.info("NFTCollectionManager initialisé avec succès")

    def _load_collections(self) -> None:
        """Charge les collections existantes"""
        # Dans une implémentation réelle, on chargerait depuis une base de données
        pass

    # ============================================================
    # MÉTHODES PUBLIQUES - CRÉATION DE COLLECTION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def create_collection(
        self,
        config: CollectionConfig,
        wallet_address: str,
        deployer_address: Optional[str] = None,
    ) -> CollectionCreationResult:
        """
        Crée une nouvelle collection NFT

        Args:
            config: Configuration de la collection
            wallet_address: Adresse du wallet
            deployer_address: Adresse du déployeur (optionnel)

        Returns:
            Résultat de la création
        """
        logger.info(f"Création de la collection {config.name} sur {config.chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Validation de la configuration
            await self._validate_collection_config(config)

            # Récupération du template de contrat
            template = CONTRACT_TEMPLATES.get(config.standard.value.lower())
            if not template:
                raise NFTError(f"Template non trouvé pour {config.standard.value}")

            # Construction du contrat
            contract_data = await self._build_contract(
                template=template,
                config=config,
                deployer=deployer_address or wallet_address,
            )

            # Déploiement du contrat
            tx_hash = await self._deploy_contract(
                contract_data=contract_data,
                wallet=wallet,
                chain=config.chain,
            )

            # Récupération de l'adresse du contrat
            contract_address = await self._get_contract_address(
                chain=config.chain,
                tx_hash=tx_hash,
            )

            # Enregistrement de la collection
            collection_id = f"col_{uuid.uuid4().hex[:12]}"
            self._collections[collection_id] = config

            self._total_collections += 1
            self.metrics.record_increment(
                "nft_collection_created",
                1,
                {
                    "chain": config.chain,
                    "standard": config.standard.value,
                    "type": config.collection_type.value,
                },
            )

            result = CollectionCreationResult(
                contract_address=contract_address,
                chain=config.chain,
                standard=config.standard,
                tx_hash=tx_hash.hex(),
                collection_id=collection_id,
                created_at=datetime.now(),
            )

            logger.info(f"Collection créée: {contract_address}")
            return result

        except Exception as e:
            logger.error(f"Erreur de création de collection: {e}")
            raise NFTError(f"Erreur de création de collection: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - MINT
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def mint_nft(
        self,
        collection_id: str,
        wallet_address: str,
        to_address: Optional[str] = None,
        quantity: int = 1,
        phase_id: Optional[str] = None,
    ) -> str:
        """
        Mint un NFT d'une collection

        Args:
            collection_id: ID de la collection
            wallet_address: Adresse du wallet
            to_address: Adresse de destination (optionnel)
            quantity: Quantité à minter
            phase_id: ID de la phase de mint

        Returns:
            Hash de la transaction
        """
        logger.info(f"Mint de {quantity} NFT(s) pour {collection_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Récupération de la collection
            collection = self._collections.get(collection_id)
            if not collection:
                raise NFTError(f"Collection {collection_id} non trouvée")

            # Vérification des phases
            phase = await self._get_active_phase(collection_id, phase_id)
            if not phase:
                raise NFTError("Aucune phase de mint active")

            # Vérification du statut
            status = await self.get_mint_status(collection_id)
            if status != MintStatus.ONGOING:
                raise NFTError(f"Mint non actif: {status.value}")

            # Vérification des limites
            await self._validate_mint_limits(
                collection=collection,
                phase=phase,
                wallet_address=wallet_address,
                quantity=quantity,
            )

            # Vérification de la whitelist
            if phase.phase_type == MintPhase.WHITELIST:
                if wallet_address not in phase.whitelist:
                    raise NFTError("Wallet non whitelisté")

            # Construction de la transaction de mint
            tx_data = await self._build_mint_transaction(
                collection=collection,
                phase=phase,
                to_address=to_address or wallet_address,
                quantity=quantity,
                wallet_address=wallet_address,
            )

            signed_tx = wallet.sign_transaction(tx_data)
            tx_hash = await self._send_transaction(collection.chain, signed_tx)

            self._total_mints += quantity
            self.metrics.record_increment(
                "nft_minted",
                quantity,
                {
                    "collection": collection_id,
                    "chain": collection.chain,
                    "phase": phase.phase_type.value,
                },
            )

            logger.info(f"Mint réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de mint: {e}")
            raise NFTError(f"Erreur de mint: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def batch_mint(
        self,
        collection_id: str,
        wallets: List[str],
        quantities: List[int],
        wallet_address: str,
        phase_id: Optional[str] = None,
    ) -> str:
        """
        Mint multiple NFTs en batch

        Args:
            collection_id: ID de la collection
            wallets: Liste des adresses
            quantities: Liste des quantités
            wallet_address: Adresse du wallet
            phase_id: ID de la phase de mint

        Returns:
            Hash de la transaction
        """
        if len(wallets) != len(quantities):
            raise ValidationError("Les listes wallets et quantities doivent avoir la même longueur")

        logger.info(f"Batch mint de {len(wallets)} wallets pour {collection_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            collection = self._collections.get(collection_id)
            if not collection:
                raise NFTError(f"Collection {collection_id} non trouvée")

            phase = await self._get_active_phase(collection_id, phase_id)
            if not phase:
                raise NFTError("Aucune phase de mint active")

            # Vérification du statut
            status = await self.get_mint_status(collection_id)
            if status != MintStatus.ONGOING:
                raise NFTError(f"Mint non actif: {status.value}")

            total_quantity = sum(quantities)

            # Vérification des limites globales
            if phase.max_mint > 0 and total_quantity > phase.max_mint:
                raise NFTError(f"Quantité totale {total_quantity} dépasse la limite {phase.max_mint}")

            # Construction de la transaction batch
            tx_data = await self._build_batch_mint_transaction(
                collection=collection,
                phase=phase,
                wallets=wallets,
                quantities=quantities,
                wallet_address=wallet_address,
            )

            signed_tx = wallet.sign_transaction(tx_data)
            tx_hash = await self._send_transaction(collection.chain, signed_tx)

            self._total_mints += total_quantity
            self.metrics.record_increment(
                "nft_batch_minted",
                total_quantity,
                {
                    "collection": collection_id,
                    "chain": collection.chain,
                },
            )

            logger.info(f"Batch mint réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de batch mint: {e}")
            raise NFTError(f"Erreur de batch mint: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - GESTION DES PHASES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def create_mint_phase(
        self,
        collection_id: str,
        phase_config: MintPhaseConfig,
        wallet_address: str,
    ) -> str:
        """
        Crée une phase de mint

        Args:
            collection_id: ID de la collection
            phase_config: Configuration de la phase
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Création de la phase {phase_config.phase_type.value} pour {collection_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            collection = self._collections.get(collection_id)
            if not collection:
                raise NFTError(f"Collection {collection_id} non trouvée")

            # Validation de la phase
            await self._validate_phase_config(collection, phase_config)

            # Enregistrement de la phase
            phase_id = phase_config.phase_id or f"phase_{uuid.uuid4().hex[:8]}"
            self._mint_phases[collection_id][phase_id] = phase_config

            # Mise à jour on-chain (dans la réalité)
            tx_hash = f"0x{hash(collection_id + phase_id + str(time.time())):064x}"

            logger.info(f"Phase créée: {phase_id}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de création de phase: {e}")
            raise NFTError(f"Erreur de création de phase: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_mint_status(self, collection_id: str) -> MintStatus:
        """
        Obtient le statut du mint

        Args:
            collection_id: ID de la collection

        Returns:
            Statut du mint
        """
        collection = self._collections.get(collection_id)
        if not collection:
            raise NFTError(f"Collection {collection_id} non trouvée")

        phases = self._mint_phases.get(collection_id, {})
        if not phases:
            return MintStatus.NOT_STARTED

        now = datetime.now()
        for phase in phases.values():
            if phase.start_time <= now <= phase.end_time:
                return MintStatus.ONGOING
            elif phase.start_time > now:
                return MintStatus.NOT_STARTED

        return MintStatus.COMPLETED

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_collection(self, collection_id: str) -> Optional[CollectionConfig]:
        """Obtient une collection par son ID"""
        return self._collections.get(collection_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_collection_by_address(
        self,
        contract_address: str,
        chain: str,
    ) -> Optional[CollectionConfig]:
        """Obtient une collection par son adresse"""
        for collection in self._collections.values():
            if collection.contract_address == contract_address and collection.chain == chain:
                return collection
        return None

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_phase(self, collection_id: str, phase_id: str) -> Optional[MintPhaseConfig]:
        """Obtient une phase de mint"""
        return self._mint_phases.get(collection_id, {}).get(phase_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_active_phase(self, collection_id: str) -> Optional[MintPhaseConfig]:
        """Obtient la phase active"""
        return await self._get_active_phase(collection_id)

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_collection(
        self,
        collection_id: str,
        interval: int = 60,
    ) -> None:
        """
        Surveille une collection en continu

        Args:
            collection_id: ID de la collection
            interval: Intervalle en secondes
        """
        logger.info(f"Démarrage du monitoring de la collection {collection_id}")

        while True:
            try:
                collection = self._collections.get(collection_id)
                if not collection:
                    logger.warning(f"Collection {collection_id} non trouvée")
                    break

                # Mise à jour du statut
                status = await self.get_mint_status(collection_id)
                if status == MintStatus.ONGOING:
                    # Vérification des limites
                    for phase in self._mint_phases.get(collection_id, {}).values():
                        if phase.end_time < datetime.now():
                            # Phase expirée
                            await self._send_alert({
                                "type": "phase_expired",
                                "collection": collection_id,
                                "phase": phase.phase_id,
                                "severity": "warning",
                            })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES DE GESTION DE LA WHITELIST
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def add_to_whitelist(
        self,
        collection_id: str,
        phase_id: str,
        addresses: List[str],
        wallet_address: str,
    ) -> str:
        """
        Ajoute des adresses à la whitelist

        Args:
            collection_id: ID de la collection
            phase_id: ID de la phase
            addresses: Liste des adresses
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Ajout de {len(addresses)} adresses à la whitelist")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            phase = self._mint_phases.get(collection_id, {}).get(phase_id)
            if not phase:
                raise NFTError(f"Phase {phase_id} non trouvée")

            # Ajout des adresses
            phase.whitelist.extend(addresses)

            # Mise à jour on-chain (dans la réalité)
            tx_hash = f"0x{hash(collection_id + phase_id + str(time.time()) + 'whitelist'):064x}"

            logger.info(f"Adresses ajoutées à la whitelist")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'ajout à la whitelist: {e}")
            raise NFTError(f"Erreur d'ajout à la whitelist: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def is_whitelisted(self, collection_id: str, phase_id: str, address: str) -> bool:
        """
        Vérifie si une adresse est whitelistée

        Args:
            collection_id: ID de la collection
            phase_id: ID de la phase
            address: Adresse à vérifier

        Returns:
            True si whitelistée
        """
        phase = self._mint_phases.get(collection_id, {}).get(phase_id)
        if not phase:
            return False

        return address in phase.whitelist

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _validate_collection_config(self, config: CollectionConfig) -> None:
        """Valide une configuration de collection"""
        if not config.name:
            raise ValidationError("Le nom de la collection est requis")

        if not config.symbol:
            raise ValidationError("Le symbole de la collection est requis")

        if config.total_supply <= 0:
            raise ValidationError("Le total supply doit être positif")

        if config.mint_price < 0:
            raise ValidationError("Le prix de mint ne peut pas être négatif")

        if config.royalty_percentage < 0 or config.royalty_percentage > 100:
            raise ValidationError("Le pourcentage de royalties doit être entre 0 et 100")

        if not config.royalty_address:
            raise ValidationError("L'adresse de royalties est requise")

        if config.standard not in [NFTStandard.ERC721, NFTStandard.ERC1155]:
            raise ValidationError(f"Standard {config.standard.value} non supporté")

    async def _validate_phase_config(
        self,
        collection: CollectionConfig,
        phase: MintPhaseConfig,
    ) -> None:
        """Valide une configuration de phase"""
        if phase.start_time >= phase.end_time:
            raise ValidationError("La date de début doit être avant la date de fin")

        if phase.max_mint < 0:
            raise ValidationError("Le max mint doit être positif")

        if phase.phase_type == MintPhase.WHITELIST and not phase.whitelist:
            raise ValidationError("La whitelist ne peut pas être vide")

    async def _validate_mint_limits(
        self,
        collection: CollectionConfig,
        phase: MintPhaseConfig,
        wallet_address: str,
        quantity: int,
    ) -> None:
        """Valide les limites de mint"""
        # Limite par phase
        if phase.max_mint > 0 and quantity > phase.max_mint:
            raise ValidationError(
                f"Quantité {quantity} dépasse la limite de la phase {phase.max_mint}"
            )

        # Limite par wallet
        if collection.max_mint_per_wallet > 0:
            # Dans la réalité, on vérifierait les mints précédents
            pass

    async def _get_active_phase(
        self,
        collection_id: str,
        phase_id: Optional[str] = None,
    ) -> Optional[MintPhaseConfig]:
        """Obtient la phase active"""
        phases = self._mint_phases.get(collection_id, {})

        if phase_id:
            return phases.get(phase_id)

        now = datetime.now()
        for phase in phases.values():
            if phase.start_time <= now <= phase.end_time:
                return phase

        return None

    async def _build_contract(
        self,
        template: Dict[str, Any],
        config: CollectionConfig,
        deployer: str,
    ) -> Dict[str, Any]:
        """Construit un contrat"""
        # Dans la réalité, on générerait le bytecode avec les paramètres
        return {
            "bytecode": template["bytecode"],
            "abi": template["abi"],
            "parameters": {
                "name": config.name,
                "symbol": config.symbol,
                "totalSupply": config.total_supply,
                "maxMintPerWallet": config.max_mint_per_wallet,
                "mintPrice": int(config.mint_price * Decimal(1e18)),
                "royaltyPercentage": int(config.royalty_percentage * 100),
                "royaltyAddress": to_checksum_address(config.royalty_address),
                "baseURI": config.base_uri,
                "deployer": to_checksum_address(deployer),
            },
        }

    async def _deploy_contract(
        self,
        contract_data: Dict[str, Any],
        wallet: BaseWallet,
        chain: str,
    ) -> HexBytes:
        """Déploie un contrat"""
        # Simulé - dans la réalité, on utiliserait web3 pour déployer
        return HexBytes(f"0x{hash(str(contract_data) + str(time.time())):064x}")

    async def _get_contract_address(
        self,
        chain: str,
        tx_hash: HexBytes,
    ) -> str:
        """Récupère l'adresse du contrat déployé"""
        # Simulé
        return f"0x{uuid.uuid4().hex[:40]}"

    async def _build_mint_transaction(
        self,
        collection: CollectionConfig,
        phase: MintPhaseConfig,
        to_address: str,
        quantity: int,
        wallet_address: str,
    ) -> Dict[str, Any]:
        """Construit une transaction de mint"""
        # Simulé
        return {
            "from": to_checksum_address(wallet_address),
            "to": "0x...",
            "value": int(phase.price * Decimal(1e18) * quantity),
            "gas": 200000,
            "gasPrice": await self._get_gas_price(collection.chain),
            "data": "0x",
        }

    async def _build_batch_mint_transaction(
        self,
        collection: CollectionConfig,
        phase: MintPhaseConfig,
        wallets: List[str],
        quantities: List[int],
        wallet_address: str,
    ) -> Dict[str, Any]:
        """Construit une transaction de batch mint"""
        return {
            "from": to_checksum_address(wallet_address),
            "to": "0x...",
            "value": int(phase.price * Decimal(1e18) * sum(quantities)),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(collection.chain),
            "data": "0x",
        }

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
            "total_collections": self._total_collections,
            "total_mints": self._total_mints,
            "active_collections": len(self._collections),
            "active_phases": sum(len(phases) for phases in self._mint_phases.values()),
            "chains_supported": list(self.web3_providers.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTCollectionManager...")

        self._collections.clear()
        self._mint_phases.clear()
        self._mint_queues.clear()
        self._mint_locks.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_collection_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> NFTCollectionManager:
    """
    Crée une instance de NFTCollectionManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTCollectionManager
    """
    return NFTCollectionManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTCollectionManager"""
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
    manager = create_nft_collection_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Création d'une collection
    collection_config = CollectionConfig(
        name="My NFT Collection",
        symbol="MNFT",
        description="My awesome NFT collection",
        collection_type=CollectionType.ART,
        chain="ethereum",
        standard=NFTStandard.ERC721,
        total_supply=10000,
        max_mint_per_wallet=10,
        mint_price=Decimal("0.1"),
        mint_currency="ETH",
        royalty_percentage=Decimal("5"),
        royalty_address="0x1234567890123456789012345678901234567890",
        base_uri="https://api.example.com/metadata/",
    )

    result = await manager.create_collection(
        config=collection_config,
        wallet_address="0x1234567890123456789012345678901234567890",
    )

    print(f"Collection créée: {result.to_dict()}")

    # Création d'une phase de mint
    phase_config = MintPhaseConfig(
        phase_id="phase_1",
        phase_type=MintPhase.PUBLIC,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(days=7),
        max_mint=1000,
        price=Decimal("0.1"),
    )

    tx_hash = await manager.create_mint_phase(
        collection_id=result.collection_id,
        phase_config=phase_config,
        wallet_address="0x1234567890123456789012345678901234567890",
    )

    print(f"Phase créée: {tx_hash}")

    # Mint d'un NFT
    tx_hash = await manager.mint_nft(
        collection_id=result.collection_id,
        wallet_address="0x1234567890123456789012345678901234567890",
        quantity=1,
    )

    print(f"NFT minté: {tx_hash}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())


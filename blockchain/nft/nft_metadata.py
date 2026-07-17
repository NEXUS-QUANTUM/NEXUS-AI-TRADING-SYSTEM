# blockchain/nft/nft_metadata.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés 

"""
Module NFT Metadata - Gestion des Métadonnées NFT

Ce module implémente un système complet de gestion des métadonnées NFT,
supportant les standards ERC-721, ERC-1155, les protocoles de stockage
(IPFS, Arweave, HTTP), et les formats de métadonnées.

Fonctionnalités principales:
- Gestion des métadonnées NFT (ERC-721, ERC-1155)
- Support des protocoles de stockage (IPFS, Arweave, HTTP)
- Validation des métadonnées
- Génération de métadonnées
- Mise à jour des métadonnées
- Cache des métadonnées
- Support des attributes et propriétés
- Support des animations et médias
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
from urllib.parse import urlparse
import hashlib
import base64

import aiohttp
import web3
from web3 import Web3
from web3.contract import Contract
from eth_utils import to_checksum_address, is_address, to_hex

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, MetadataError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTMetadata
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, MetadataError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTMetadata

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class MetadataStandard(Enum):
    """Standards de métadonnées"""
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    OPENSEA = "opensea"
    LOOKSRARE = "looksrare"
    CUSTOM = "custom"


class StorageProtocol(Enum):
    """Protocoles de stockage"""
    IPFS = "ipfs"
    ARWEAVE = "arweave"
    HTTP = "http"
    HTTPS = "https"
    CUSTOM = "custom"


class MetadataStatus(Enum):
    """Statuts des métadonnées"""
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    UPDATING = "updating"
    ERROR = "error"


@dataclass
class MetadataSource:
    """Source de métadonnées"""
    uri: str
    protocol: StorageProtocol
    chain: str
    contract_address: str
    token_id: str
    content_hash: Optional[str] = None
    fetched_at: Optional[datetime] = None
    status: MetadataStatus = MetadataStatus.PENDING
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "uri": self.uri,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "content_hash": self.content_hash,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "status": self.status.value,
            "error_message": self.error_message,
        }


@dataclass
class MetadataTemplate:
    """Template de métadonnées"""
    template_id: str
    name: str
    description: str
    standard: MetadataStandard
    required_fields: List[str]
    optional_fields: List[str]
    schema: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "standard": self.standard.value,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "schema": self.schema,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================
# TEMPLATES PAR DÉFAUT
# ============================================================

DEFAULT_TEMPLATES = {
    "erc721_default": {
        "name": "ERC721 Default",
        "description": "Default ERC-721 metadata template",
        "standard": "erc721",
        "required_fields": ["name", "image"],
        "optional_fields": ["description", "attributes", "properties", "animation_url", "external_url"],
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "maxLength": 100},
                "description": {"type": "string", "maxLength": 500},
                "image": {"type": "string", "format": "uri"},
                "external_url": {"type": "string", "format": "uri"},
                "animation_url": {"type": "string", "format": "uri"},
                "attributes": {"type": "array"},
                "properties": {"type": "object"},
            },
            "required": ["name", "image"],
        },
    },
    "erc1155_default": {
        "name": "ERC1155 Default",
        "description": "Default ERC-1155 metadata template",
        "standard": "erc1155",
        "required_fields": ["name", "image"],
        "optional_fields": ["description", "attributes", "properties", "animation_url"],
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "maxLength": 100},
                "description": {"type": "string", "maxLength": 500},
                "image": {"type": "string", "format": "uri"},
                "animation_url": {"type": "string", "format": "uri"},
                "attributes": {"type": "array"},
                "properties": {"type": "object"},
            },
            "required": ["name", "image"],
        },
    },
    "opensea_metadata": {
        "name": "OpenSea Metadata",
        "description": "OpenSea compatible metadata template",
        "standard": "opensea",
        "required_fields": ["name", "image", "description"],
        "optional_fields": ["external_url", "animation_url", "attributes", "properties", "background_color"],
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "maxLength": 100},
                "description": {"type": "string", "maxLength": 1000},
                "image": {"type": "string", "format": "uri"},
                "external_url": {"type": "string", "format": "uri"},
                "animation_url": {"type": "string", "format": "uri"},
                "background_color": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
                "attributes": {"type": "array"},
                "properties": {"type": "object"},
            },
            "required": ["name", "image", "description"],
        },
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTMetadataManager(BaseNFT):
    """
    Gestionnaire avancé des métadonnées NFT
    """

    # Protocoles de stockage par défaut
    DEFAULT_GATEWAYS = {
        StorageProtocol.IPFS: "https://ipfs.io/ipfs/",
        StorageProtocol.ARWEAVE: "https://arweave.net/",
        StorageProtocol.HTTP: "",
        StorageProtocol.HTTPS: "",
    }

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de métadonnées

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._metadata_cache: Dict[str, Tuple[float, NFTMetadata]] = {}
        self._sources_cache: Dict[str, Tuple[float, MetadataSource]] = {}
        self._templates: Dict[str, MetadataTemplate] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
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

        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None

        # Chargement des templates
        self._load_templates()

        # Initialisation de la session HTTP
        self._init_session()

        logger.info("NFTMetadataManager initialisé avec succès")

    def _init_session(self) -> None:
        """Initialise la session HTTP"""
        if not self._session:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": "NEXUS-AI-TRADING/1.0",
                    "Accept": "application/json",
                },
            )

    def _load_templates(self) -> None:
        """Charge les templates de métadonnées"""
        for template_id, template_data in DEFAULT_TEMPLATES.items():
            self._templates[template_id] = MetadataTemplate(
                template_id=template_id,
                name=template_data["name"],
                description=template_data["description"],
                standard=MetadataStandard(template_data["standard"]),
                required_fields=template_data["required_fields"],
                optional_fields=template_data["optional_fields"],
                schema=template_data["schema"],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        logger.info(f"Templates de métadonnées chargés: {len(self._templates)}")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_metadata(
        self,
        uri: str,
        contract_address: str,
        token_id: str,
        chain: str = "ethereum",
        force_refresh: bool = False,
    ) -> NFTMetadata:
        """
        Récupère les métadonnées depuis une URI

        Args:
            uri: URI des métadonnées
            contract_address: Adresse du contrat
            token_id: ID du token
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Métadonnées du NFT
        """
        cache_key = f"{chain}:{contract_address}:{token_id}"

        if not force_refresh and cache_key in self._metadata_cache:
            cached_time, metadata = self._metadata_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return metadata

        try:
            # Récupération de la source
            source = await self._get_or_create_source(uri, contract_address, token_id, chain)

            # Récupération des métadonnées
            metadata_data = await self._fetch_from_uri(uri)

            # Validation des métadonnées
            validated_metadata = await self._validate_metadata(metadata_data)

            # Création de l'objet NFTMetadata
            metadata = NFTMetadata(
                name=validated_metadata.get("name", f"NFT #{token_id}"),
                description=validated_metadata.get("description", ""),
                image=validated_metadata.get("image", ""),
                external_url=validated_metadata.get("external_url"),
                attributes=validated_metadata.get("attributes", []),
                properties=validated_metadata.get("properties", {}),
                animation_url=validated_metadata.get("animation_url"),
                youtube_url=validated_metadata.get("youtube_url"),
                background_color=validated_metadata.get("background_color"),
            )

            # Mise en cache
            self._metadata_cache[cache_key] = (time.time(), metadata)

            # Mise à jour de la source
            source.status = MetadataStatus.VALID
            source.content_hash = self._compute_content_hash(metadata_data)
            source.fetched_at = datetime.now()
            source.metadata = metadata_data

            self._sources_cache[uri] = (time.time(), source)

            # Métriques
            self.metrics.record_increment(
                "nft_metadata_fetched",
                1,
                {"chain": chain, "protocol": source.protocol.value},
            )

            return metadata

        except Exception as e:
            logger.error(f"Erreur de récupération des métadonnées: {e}")
            raise MetadataError(f"Erreur de récupération des métadonnées: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def generate_metadata(
        self,
        template_id: str,
        data: Dict[str, Any],
        output_format: str = "json",
    ) -> Dict[str, Any]:
        """
        Génère des métadonnées à partir d'un template

        Args:
            template_id: ID du template
            data: Données pour le template
            output_format: Format de sortie

        Returns:
            Métadonnées générées
        """
        template = self._templates.get(template_id)
        if not template:
            raise MetadataError(f"Template {template_id} non trouvé")

        try:
            # Validation des données par rapport au template
            validated_data = await self._validate_template_data(template, data)

            # Génération des métadonnées
            metadata = {
                "name": validated_data.get("name", ""),
                "description": validated_data.get("description", ""),
                "image": validated_data.get("image", ""),
                "external_url": validated_data.get("external_url"),
                "animation_url": validated_data.get("animation_url"),
                "background_color": validated_data.get("background_color"),
                "attributes": validated_data.get("attributes", []),
                "properties": validated_data.get("properties", {}),
            }

            # Formatage de sortie
            if output_format.lower() == "json":
                return metadata
            else:
                raise MetadataError(f"Format {output_format} non supporté")

        except Exception as e:
            logger.error(f"Erreur de génération des métadonnées: {e}")
            raise MetadataError(f"Erreur de génération des métadonnées: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def upload_metadata(
        self,
        metadata: Dict[str, Any],
        storage_protocol: StorageProtocol = StorageProtocol.IPFS,
        filename: Optional[str] = None,
    ) -> str:
        """
        Upload des métadonnées vers un protocole de stockage

        Args:
            metadata: Métadonnées à uploader
            storage_protocol: Protocole de stockage
            filename: Nom du fichier

        Returns:
            URI des métadonnées
        """
        logger.info(f"Upload des métadonnées vers {storage_protocol.value}")

        try:
            # Validation des métadonnées
            validated_metadata = await self._validate_metadata(metadata)

            # Upload selon le protocole
            if storage_protocol == StorageProtocol.IPFS:
                uri = await self._upload_to_ipfs(validated_metadata, filename)
            elif storage_protocol == StorageProtocol.ARWEAVE:
                uri = await self._upload_to_arweave(validated_metadata, filename)
            elif storage_protocol in [StorageProtocol.HTTP, StorageProtocol.HTTPS]:
                uri = await self._upload_to_http(validated_metadata, filename, storage_protocol)
            else:
                raise MetadataError(f"Protocole {storage_protocol.value} non supporté")

            self.metrics.record_increment(
                "nft_metadata_uploaded",
                1,
                {"protocol": storage_protocol.value},
            )

            logger.info(f"Métadonnées uploadées: {uri}")
            return uri

        except Exception as e:
            logger.error(f"Erreur d'upload des métadonnées: {e}")
            raise MetadataError(f"Erreur d'upload des métadonnées: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def validate_metadata(
        self,
        metadata: Dict[str, Any],
        standard: MetadataStandard = MetadataStandard.ERC721,
    ) -> Tuple[bool, List[str]]:
        """
        Valide des métadonnées

        Args:
            metadata: Métadonnées à valider
            standard: Standard de validation

        Returns:
            (est_valide, liste_des_erreurs)
        """
        return await self._validate_metadata_with_errors(metadata, standard)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_metadata_source(
        self,
        uri: str,
        contract_address: str,
        token_id: str,
        chain: str = "ethereum",
    ) -> Optional[MetadataSource]:
        """
        Obtient la source des métadonnées

        Args:
            uri: URI des métadonnées
            contract_address: Adresse du contrat
            token_id: ID du token
            chain: Chaîne

        Returns:
            Source des métadonnées ou None
        """
        cache_key = f"{chain}:{contract_address}:{token_id}"

        if cache_key in self._sources_cache:
            cached_time, source = self._sources_cache[cache_key]
            return source

        return await self._get_or_create_source(uri, contract_address, token_id, chain)

    # ============================================================
    # MÉTHODES DE TEMPLATE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def create_template(
        self,
        name: str,
        standard: MetadataStandard,
        required_fields: List[str],
        schema: Dict[str, Any],
        description: str = "",
        optional_fields: Optional[List[str]] = None,
    ) -> MetadataTemplate:
        """
        Crée un nouveau template de métadonnées

        Args:
            name: Nom du template
            standard: Standard de métadonnées
            required_fields: Champs requis
            schema: Schéma JSON
            description: Description
            optional_fields: Champs optionnels

        Returns:
            Template créé
        """
        template_id = f"template_{uuid.uuid4().hex[:8]}"

        template = MetadataTemplate(
            template_id=template_id,
            name=name,
            description=description,
            standard=standard,
            required_fields=required_fields,
            optional_fields=optional_fields or [],
            schema=schema,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self._templates[template_id] = template

        logger.info(f"Template créé: {template_id}")
        return template

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_template(self, template_id: str) -> Optional[MetadataTemplate]:
        """
        Obtient un template

        Args:
            template_id: ID du template

        Returns:
            Template ou None
        """
        return self._templates.get(template_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def list_templates(self) -> List[MetadataTemplate]:
        """
        Liste tous les templates

        Returns:
            Liste des templates
        """
        return list(self._templates.values())

    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================

    async def _fetch_from_uri(self, uri: str) -> Dict[str, Any]:
        """Récupère les données depuis une URI"""
        try:
            # Support de l'URI IPFS
            if uri.startswith("ipfs://"):
                ipfs_hash = uri.replace("ipfs://", "")
                gateway = self.config.get("ipfs_gateway", "https://ipfs.io/ipfs/")
                http_uri = f"{gateway}{ipfs_hash}"
            else:
                http_uri = uri

            # Récupération asynchrone
            if not self._session:
                self._init_session()

            async with self._session.get(http_uri) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    raise MetadataError(f"Métadonnées non trouvées: {uri}")
                else:
                    raise MetadataError(
                        f"Erreur {response.status} lors de la récupération: {uri}"
                    )

        except aiohttp.ClientError as e:
            raise MetadataError(f"Erreur de connexion: {e}")
        except json.JSONDecodeError as e:
            raise MetadataError(f"Erreur de parsing JSON: {e}")
        except Exception as e:
            raise MetadataError(f"Erreur de récupération: {e}")

    async def _validate_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Valide des métadonnées"""
        try:
            # Vérification des champs requis
            required = ["name"]
            for field in required:
                if field not in metadata:
                    raise ValidationError(f"Champ requis manquant: {field}")

            # Vérification des URLs
            if "image" in metadata and metadata["image"]:
                if not self._is_valid_url(metadata["image"]):
                    raise ValidationError("URL de l'image invalide")

            if "external_url" in metadata and metadata["external_url"]:
                if not self._is_valid_url(metadata["external_url"]):
                    raise ValidationError("URL externe invalide")

            if "animation_url" in metadata and metadata["animation_url"]:
                if not self._is_valid_url(metadata["animation_url"]):
                    raise ValidationError("URL d'animation invalide")

            # Validation des attributs
            if "attributes" in metadata and metadata["attributes"]:
                if not isinstance(metadata["attributes"], list):
                    raise ValidationError("Les attributs doivent être une liste")

                for attr in metadata["attributes"]:
                    if not isinstance(attr, dict):
                        raise ValidationError("Chaque attribut doit être un objet")
                    if "trait_type" not in attr or "value" not in attr:
                        raise ValidationError("Les attributs doivent avoir trait_type et value")

            return metadata

        except ValidationError as e:
            raise MetadataError(f"Validation échouée: {e}")

    async def _validate_metadata_with_errors(
        self,
        metadata: Dict[str, Any],
        standard: MetadataStandard,
    ) -> Tuple[bool, List[str]]:
        """Valide des métadonnées avec retour des erreurs"""
        errors = []

        try:
            # Vérification des champs requis selon le standard
            if standard == MetadataStandard.ERC721:
                required = ["name", "image"]
            elif standard == MetadataStandard.ERC1155:
                required = ["name", "image"]
            elif standard == MetadataStandard.OPENSEA:
                required = ["name", "image", "description"]
            else:
                required = ["name"]

            for field in required:
                if field not in metadata:
                    errors.append(f"Champ requis manquant: {field}")

            # Vérification des URLs
            url_fields = ["image", "external_url", "animation_url"]
            for field in url_fields:
                if field in metadata and metadata[field]:
                    if not self._is_valid_url(metadata[field]):
                        errors.append(f"URL invalide pour {field}: {metadata[field]}")

            # Validation des attributs
            if "attributes" in metadata and metadata["attributes"]:
                if not isinstance(metadata["attributes"], list):
                    errors.append("Les attributs doivent être une liste")
                else:
                    for i, attr in enumerate(metadata["attributes"]):
                        if not isinstance(attr, dict):
                            errors.append(f"L'attribut {i} doit être un objet")
                        elif "trait_type" not in attr or "value" not in attr:
                            errors.append(f"L'attribut {i} doit avoir trait_type et value")

            return len(errors) == 0, errors

        except Exception as e:
            return False, [str(e)]

    async def _validate_template_data(
        self,
        template: MetadataTemplate,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Valide des données par rapport à un template"""
        errors = []

        # Vérification des champs requis
        for field in template.required_fields:
            if field not in data:
                errors.append(f"Champ requis manquant: {field}")

        # Vérification du schéma (simplifiée)
        if errors:
            raise ValidationError(f"Validation du template échouée: {errors}")

        return data

    async def _upload_to_ipfs(self, metadata: Dict[str, Any], filename: Optional[str]) -> str:
        """Upload vers IPFS"""
        # Simulé - dans la réalité, on utiliserait une API IPFS
        content = json.dumps(metadata)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"ipfs://{content_hash}"

    async def _upload_to_arweave(self, metadata: Dict[str, Any], filename: Optional[str]) -> str:
        """Upload vers Arweave"""
        # Simulé
        content = json.dumps(metadata)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"arweave://{content_hash}"

    async def _upload_to_http(
        self,
        metadata: Dict[str, Any],
        filename: Optional[str],
        protocol: StorageProtocol,
    ) -> str:
        """Upload vers HTTP/HTTPS"""
        # Simulé
        content = json.dumps(metadata)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"{protocol.value}://metadata.nexus.io/{content_hash}"

    async def _get_or_create_source(
        self,
        uri: str,
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> MetadataSource:
        """Obtient ou crée une source de métadonnées"""
        cache_key = f"{chain}:{contract_address}:{token_id}"

        if cache_key in self._sources_cache:
            cached_time, source = self._sources_cache[cache_key]
            return source

        # Détection du protocole
        protocol = self._detect_protocol(uri)

        source = MetadataSource(
            uri=uri,
            protocol=protocol,
            chain=chain,
            contract_address=contract_address,
            token_id=token_id,
            status=MetadataStatus.PENDING,
        )

        self._sources_cache[uri] = (time.time(), source)

        return source

    def _detect_protocol(self, uri: str) -> StorageProtocol:
        """Détecte le protocole d'une URI"""
        if uri.startswith("ipfs://"):
            return StorageProtocol.IPFS
        elif uri.startswith("ar://") or uri.startswith("arweave://"):
            return StorageProtocol.ARWEAVE
        elif uri.startswith("http://"):
            return StorageProtocol.HTTP
        elif uri.startswith("https://"):
            return StorageProtocol.HTTPS
        else:
            return StorageProtocol.CUSTOM

    def _is_valid_url(self, url: str) -> bool:
        """Vérifie si une URL est valide"""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ["http", "https", "ipfs", "ar", "arweave"]
        except Exception:
            return False

    def _compute_content_hash(self, data: Dict[str, Any]) -> str:
        """Calcule le hash du contenu"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "metadata_cached": len(self._metadata_cache),
            "sources_cached": len(self._sources_cache),
            "templates_available": len(self._templates),
            "cache_ttl": self.cache_ttl,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTMetadataManager...")

        self._metadata_cache.clear()
        self._sources_cache.clear()

        if self._session:
            await self._session.close()
            self._session = None

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_metadata_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    **kwargs,
) -> NFTMetadataManager:
    """
    Crée une instance de NFTMetadataManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTMetadataManager
    """
    return NFTMetadataManager(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTMetadataManager"""
    # Configuration
    config = {
        "ipfs_gateway": "https://ipfs.io/ipfs/",
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création du gestionnaire
    metadata_manager = create_nft_metadata_manager(
        config=config,
        wallet_manager=wallet_manager,
    )

    # Récupération des métadonnées
    metadata = await metadata_manager.get_metadata(
        uri="ipfs://QmXkfzFkLwXn1dWVmDpJZQy8qv8Vw3VpXcVpXcVpXcVpX",
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
    )

    print(f"Métadonnées: {metadata.to_dict()}")

    # Génération de métadonnées
    generated = await metadata_manager.generate_metadata(
        template_id="erc721_default",
        data={
            "name": "My NFT",
            "description": "My awesome NFT",
            "image": "https://example.com/image.png",
            "attributes": [
                {"trait_type": "Rarity", "value": "Legendary"},
                {"trait_type": "Color", "value": "Gold"},
            ],
        },
    )

    print(f"Métadonnées générées: {generated}")

    # Upload des métadonnées
    uri = await metadata_manager.upload_metadata(
        metadata=generated,
        storage_protocol=StorageProtocol.IPFS,
    )

    print(f"URI: {uri}")

    # Statistiques
    stats = metadata_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await metadata_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

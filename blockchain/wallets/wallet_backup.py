"""
NEXUS AI TRADING SYSTEM - WALLET BACKUP MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de sauvegarde et restauration de wallets multi-blockchain.
Support du chiffrement AES-256, stockage sécurisé, et récupération d'urgence.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiofiles
import aiohttp
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletStatus,
    BlockchainNetwork,
    WalletType
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class BackupType(Enum):
    """Types de sauvegarde."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    ENCRYPTED = "encrypted"
    PLAIN = "plain"
    MULTISIG = "multisig"


class BackupStatus(Enum):
    """Statuts de sauvegarde."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"


class RecoveryMethod(Enum):
    """Méthodes de récupération."""
    MNEMONIC = "mnemonic"
    PRIVATE_KEY = "private_key"
    KEYSTORE = "keystore"
    MULTISIG = "multisig"
    SOCIAL = "social"
    EMERGENCY = "emergency"


@dataclass
class BackupMetadata:
    """Métadonnées de sauvegarde."""
    backup_id: UUID
    wallet_id: UUID
    user_id: UUID
    backup_type: BackupType
    created_at: datetime
    updated_at: datetime
    size_bytes: int
    checksum: str
    encryption_algorithm: str
    version: str
    status: BackupStatus
    storage_location: str
    recovery_methods: List[RecoveryMethod]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "backup_id": str(self.backup_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "backup_type": self.backup_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "encryption_algorithm": self.encryption_algorithm,
            "version": self.version,
            "status": self.status.value,
            "storage_location": self.storage_location,
            "recovery_methods": [r.value for r in self.recovery_methods],
            "metadata": self.metadata
        }


@dataclass
class BackupData:
    """Données de sauvegarde."""
    wallet_id: UUID
    user_id: UUID
    chain_type: str
    network: str
    address: str
    private_key_encrypted: Optional[str] = None
    mnemonic_encrypted: Optional[str] = None
    keystore_json: Optional[str] = None
    public_key: Optional[str] = None
    derivation_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "chain_type": self.chain_type,
            "network": self.network,
            "address": self.address,
            "private_key_encrypted": self.private_key_encrypted,
            "mnemonic_encrypted": self.mnemonic_encrypted,
            "keystore_json": self.keystore_json,
            "public_key": self.public_key,
            "derivation_path": self.derivation_path,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class BackupRecovery:
    """Récupération de sauvegarde."""
    recovery_id: UUID
    backup_id: UUID
    user_id: UUID
    method: RecoveryMethod
    status: str
    recovery_data: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "recovery_id": str(self.recovery_id),
            "backup_id": str(self.backup_id),
            "user_id": str(self.user_id),
            "method": self.method.value,
            "status": self.status,
            "recovery_data": self.recovery_data,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE WALLET BACKUP
# ============================================================================

class WalletBackupService:
    """
    Service de sauvegarde et restauration de wallets multi-blockchain.
    """

    # Version du format de sauvegarde
    BACKUP_VERSION = "3.0.0"
    
    # Algorithmes de chiffrement supportés
    ENCRYPTION_ALGORITHMS = {
        "AES-256-GCM": {"key_size": 32, "iv_size": 12, "tag_size": 16},
        "AES-256-CBC": {"key_size": 32, "iv_size": 16},
        "ChaCha20-Poly1305": {"key_size": 32, "iv_size": 12, "tag_size": 16}
    }
    
    # Algorithmes de dérivation de clé
    KDF_ALGORITHMS = {
        "PBKDF2": {"iterations": 100000, "salt_size": 32},
        "Scrypt": {"n": 16384, "r": 8, "p": 1, "salt_size": 32},
        "Argon2": {"iterations": 3, "memory": 65536, "parallelism": 1, "salt_size": 32}
    }

    def __init__(
        self,
        storage_path: str = "./backups",
        encryption_key: Optional[str] = None,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service de sauvegarde.

        Args:
            storage_path: Chemin de stockage des sauvegardes
            encryption_key: Clé de chiffrement maître
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.storage_path = Path(storage_path)
        self.encryption_key = encryption_key
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Création du répertoire de stockage
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Cache
        self._backup_cache: Dict[UUID, BackupMetadata] = {}
        self._recovery_cache: Dict[UUID, BackupRecovery] = {}
        
        # Métriques
        self._metrics = {
            "total_backups": 0,
            "total_restores": 0,
            "total_encrypted": 0,
            "storage_used_bytes": 0,
            "last_backup": None,
            "last_restore": None
        }

        logger.info(f"WalletBackupService initialisé avec stockage dans {storage_path}")

    # ========================================================================
    # CRÉATION DE SAUVEGARDE
    # ========================================================================

    async def create_backup(
        self,
        wallet: BaseWallet,
        backup_type: BackupType = BackupType.ENCRYPTED,
        password: Optional[str] = None,
        recovery_methods: Optional[List[RecoveryMethod]] = None,
        metadata: Optional[Dict] = None
    ) -> BackupMetadata:
        """
        Crée une sauvegarde d'un wallet.

        Args:
            wallet: Wallet à sauvegarder
            backup_type: Type de sauvegarde
            password: Mot de passe pour le chiffrement
            recovery_methods: Méthodes de récupération
            metadata: Métadonnées supplémentaires

        Returns:
            Métadonnées de la sauvegarde
        """
        try:
            backup_id = uuid4()
            timestamp = datetime.now()
            
            # Récupération des données du wallet
            backup_data = await self._extract_wallet_data(wallet)
            
            # Création du fichier de sauvegarde
            backup_file = self.storage_path / f"{backup_id}.backup"
            encrypted_file = self.storage_path / f"{backup_id}.encrypted"
            
            # Sérialisation des données
            data_json = json.dumps(backup_data.to_dict(), indent=2)
            data_bytes = data_json.encode('utf-8')
            
            # Calcul du checksum
            checksum = hashlib.sha256(data_bytes).hexdigest()
            
            # Chiffrement si nécessaire
            if backup_type in [BackupType.ENCRYPTED, BackupType.FULL]:
                if not password and not self.encryption_key:
                    raise ValueError("Mot de passe ou clé de chiffrement requis")
                
                encryption_key = self._derive_key(password or self.encryption_key)
                encrypted_data = await self._encrypt_data(data_bytes, encryption_key)
                
                # Écriture du fichier chiffré
                async with aiofiles.open(encrypted_file, 'wb') as f:
                    await f.write(encrypted_data)
                
                file_path = str(encrypted_file)
                size_bytes = len(encrypted_data)
                encryption_algorithm = "AES-256-GCM"
            else:
                # Écriture du fichier non chiffré
                async with aiofiles.open(backup_file, 'wb') as f:
                    await f.write(data_bytes)
                
                file_path = str(backup_file)
                size_bytes = len(data_bytes)
                encryption_algorithm = "none"

            # Métadonnées de la sauvegarde
            metadata_obj = BackupMetadata(
                backup_id=backup_id,
                wallet_id=wallet.config.wallet_id,
                user_id=wallet.config.user_id,
                backup_type=backup_type,
                created_at=timestamp,
                updated_at=timestamp,
                size_bytes=size_bytes,
                checksum=checksum,
                encryption_algorithm=encryption_algorithm,
                version=self.BACKUP_VERSION,
                status=BackupStatus.COMPLETED,
                storage_location=file_path,
                recovery_methods=recovery_methods or [
                    RecoveryMethod.PRIVATE_KEY,
                    RecoveryMethod.MNEMONIC
                ],
                metadata=metadata or {}
            )

            # Stockage des métadonnées
            self._backup_cache[backup_id] = metadata_obj
            
            # Mise à jour des métriques
            self._metrics["total_backups"] += 1
            self._metrics["storage_used_bytes"] += size_bytes
            self._metrics["last_backup"] = timestamp.isoformat()
            if backup_type == BackupType.ENCRYPTED:
                self._metrics["total_encrypted"] += 1

            # Sauvegarde des métadonnées dans Redis
            if self.redis:
                await self._store_metadata(metadata_obj)

            logger.info(f"Sauvegarde créée: {backup_id} pour {wallet.config.wallet_id}")
            return metadata_obj

        except Exception as e:
            logger.error(f"Erreur lors de la création de la sauvegarde: {e}")
            raise

    async def _extract_wallet_data(
        self,
        wallet: BaseWallet
    ) -> BackupData:
        """
        Extrait les données d'un wallet.

        Args:
            wallet: Wallet

        Returns:
            Données de sauvegarde
        """
        config = wallet.config
        
        return BackupData(
            wallet_id=config.wallet_id,
            user_id=config.user_id,
            chain_type=config.blockchain,
            network=config.network.value if hasattr(config.network, 'value') else str(config.network),
            address=config.address,
            private_key_encrypted=config.private_key_encrypted,
            public_key=config.public_key,
            derivation_path=config.derivation_path,
            metadata={
                "name": config.name,
                "type": config.type.value if hasattr(config.type, 'value') else str(config.type),
                "is_hardware": config.is_hardware,
                "is_imported": config.is_imported,
                "is_created": config.is_created
            }
        )

    # ========================================================================
    # CHIFFREMENT ET DÉCHIFFREMENT
    # ========================================================================

    def _derive_key(
        self,
        password: str,
        salt: Optional[bytes] = None,
        algorithm: str = "PBKDF2"
    ) -> bytes:
        """
        Dérive une clé de chiffrement à partir d'un mot de passe.

        Args:
            password: Mot de passe
            salt: Sel (optionnel)
            algorithm: Algorithme de dérivation

        Returns:
            Clé dérivée
        """
        if salt is None:
            salt = os.urandom(32)
        
        password_bytes = password.encode('utf-8')
        
        if algorithm == "PBKDF2":
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
        elif algorithm == "Scrypt":
            kdf = Scrypt(
                salt=salt,
                length=32,
                n=16384,
                r=8,
                p=1,
                backend=default_backend()
            )
        else:
            raise ValueError(f"Algorithme non supporté: {algorithm}")
        
        return kdf.derive(password_bytes)

    async def _encrypt_data(
        self,
        data: bytes,
        key: bytes
    ) -> bytes:
        """
        Chiffre des données avec AES-256-GCM.

        Args:
            data: Données à chiffrer
            key: Clé de chiffrement

        Returns:
            Données chiffrées
        """
        try:
            # Génération de l'IV
            iv = os.urandom(12)
            
            # Création du chiffreur
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # Chiffrement
            encrypted = encryptor.update(data) + encryptor.finalize()
            
            # Récupération du tag
            tag = encryptor.tag
            
            # Assemblage: IV + Tag + Données chiffrées
            result = iv + tag + encrypted
            
            return result

        except Exception as e:
            logger.error(f"Erreur lors du chiffrement: {e}")
            raise

    async def _decrypt_data(
        self,
        encrypted_data: bytes,
        key: bytes
    ) -> bytes:
        """
        Déchiffre des données avec AES-256-GCM.

        Args:
            encrypted_data: Données chiffrées
            key: Clé de chiffrement

        Returns:
            Données déchiffrées
        """
        try:
            # Extraction de l'IV, du tag et des données
            iv = encrypted_data[:12]
            tag = encrypted_data[12:28]
            ciphertext = encrypted_data[28:]
            
            # Création du déchiffreur
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Déchiffrement
            decrypted = decryptor.update(ciphertext) + decryptor.finalize()
            
            return decrypted

        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement: {e}")
            raise

    # ========================================================================
    # RESTAURATION DE SAUVEGARDE
    # ========================================================================

    async def restore_backup(
        self,
        backup_id: UUID,
        password: Optional[str] = None,
        restore_metadata: Optional[Dict] = None
    ) -> BackupRecovery:
        """
        Restaure une sauvegarde.

        Args:
            backup_id: ID de la sauvegarde
            password: Mot de passe (si chiffré)
            restore_metadata: Métadonnées de restauration

        Returns:
            Récupération de sauvegarde
        """
        try:
            recovery_id = uuid4()
            timestamp = datetime.now()
            
            # Récupération des métadonnées
            metadata = await self.get_backup_metadata(backup_id)
            if not metadata:
                raise ValueError(f"Sauvegarde {backup_id} non trouvée")
            
            # Lecture du fichier
            backup_path = Path(metadata.storage_location)
            if not backup_path.exists():
                raise ValueError(f"Fichier de sauvegarde non trouvé: {backup_path}")
            
            async with aiofiles.open(backup_path, 'rb') as f:
                file_data = await f.read()
            
            # Déchiffrement si nécessaire
            if metadata.encryption_algorithm != "none":
                if not password and not self.encryption_key:
                    raise ValueError("Mot de passe ou clé de chiffrement requis")
                
                encryption_key = self._derive_key(password or self.encryption_key)
                decrypted_data = await self._decrypt_data(file_data, encryption_key)
            else:
                decrypted_data = file_data
            
            # Vérification du checksum
            checksum = hashlib.sha256(decrypted_data).hexdigest()
            if checksum != metadata.checksum:
                raise ValueError("Checksum invalide - Fichier corrompu")
            
            # Parsing des données
            data_json = decrypted_data.decode('utf-8')
            backup_data = json.loads(data_json)
            
            # Création de la récupération
            recovery = BackupRecovery(
                recovery_id=recovery_id,
                backup_id=backup_id,
                user_id=metadata.user_id,
                method=RecoveryMethod.PRIVATE_KEY,  # Par défaut
                status="completed",
                recovery_data=backup_data,
                created_at=timestamp,
                completed_at=datetime.now(),
                metadata=restore_metadata or {}
            )
            
            # Mise en cache
            self._recovery_cache[recovery_id] = recovery
            
            # Mise à jour des métriques
            self._metrics["total_restores"] += 1
            self._metrics["last_restore"] = timestamp.isoformat()
            
            logger.info(f"Sauvegarde restaurée: {backup_id} -> {recovery_id}")
            return recovery

        except Exception as e:
            logger.error(f"Erreur lors de la restauration: {e}")
            raise

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def recover_wallet_from_backup(
        self,
        backup_id: UUID,
        password: Optional[str] = None
    ) -> BaseWallet:
        """
        Récupère un wallet complet à partir d'une sauvegarde.

        Args:
            backup_id: ID de la sauvegarde
            password: Mot de passe (si chiffré)

        Returns:
            Wallet restauré
        """
        try:
            # Récupération de la sauvegarde
            recovery = await self.restore_backup(backup_id, password)
            
            # Extraction des données
            data = recovery.recovery_data
            
            # Création de la configuration
            config = WalletConfig(
                wallet_id=UUID(data["wallet_id"]),
                user_id=UUID(data["user_id"]),
                name=data["metadata"]["name"],
                type=WalletType(data["metadata"]["type"]),
                blockchain=data["chain_type"],
                network=BlockchainNetwork(data["network"]),
                address=data["address"],
                private_key_encrypted=data.get("private_key_encrypted"),
                public_key=data.get("public_key"),
                mnemonic_encrypted=data.get("mnemonic_encrypted"),
                derivation_path=data.get("derivation_path"),
                is_hardware=data["metadata"]["is_hardware"],
                is_imported=data["metadata"]["is_imported"],
                is_created=data["metadata"]["is_created"],
                status=WalletStatus.ACTIVE,
                metadata=data["metadata"]
            )
            
            # Création du wallet approprié
            from .ethereum_wallet import EthereumWallet
            from .bsc_wallet import BSCWallet
            from .polygon_wallet import PolygonWallet
            from .solana_wallet import SolanaWallet
            from .tron_wallet import TronWallet
            
            chain_type = data["chain_type"].lower()
            
            if chain_type == "ethereum":
                wallet = EthereumWallet(config, self.api_keys)
            elif chain_type == "bsc":
                wallet = BSCWallet(config, self.api_keys)
            elif chain_type == "polygon":
                wallet = PolygonWallet(config, self.api_keys)
            elif chain_type == "solana":
                wallet = SolanaWallet(config, self.api_keys)
            elif chain_type == "tron":
                wallet = TronWallet(config, self.api_keys)
            else:
                raise ValueError(f"Blockchain non supportée: {chain_type}")
            
            # Initialisation
            await wallet.initialize()
            
            logger.info(f"Wallet restauré: {wallet.config.address}")
            return wallet

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du wallet: {e}")
            raise

    async def recover_from_mnemonic(
        self,
        mnemonic: str,
        chain_type: str,
        network: str,
        derivation_path: Optional[str] = None
    ) -> BaseWallet:
        """
        Récupère un wallet à partir d'une phrase mnémonique.

        Args:
            mnemonic: Phrase mnémonique
            chain_type: Type de blockchain
            network: Réseau
            derivation_path: Chemin de dérivation (optionnel)

        Returns:
            Wallet restauré
        """
        try:
            # Création de l'instance de wallet appropriée
            from .ethereum_wallet import EthereumWallet
            from .bsc_wallet import BSCWallet
            from .polygon_wallet import PolygonWallet
            from .solana_wallet import SolanaWallet
            from .tron_wallet import TronWallet
            
            # Génération du wallet
            if chain_type == "ethereum":
                from eth_account import Account
                Account.enable_unaudited_hdwallet_features()
                account = Account.from_mnemonic(mnemonic)
                address = account.address
                private_key = account.key.hex()
                
                config = WalletConfig(
                    wallet_id=uuid4(),
                    user_id=UUID("00000000-0000-0000-0000-000000000000"),
                    name=f"Recovered {chain_type} Wallet",
                    type=WalletType.HD,
                    blockchain=chain_type,
                    network=BlockchainNetwork(network),
                    address=address,
                    private_key_encrypted=private_key,
                    public_key=account.key.hex(),
                    mnemonic_encrypted=mnemonic,
                    derivation_path=derivation_path or "m/44'/60'/0'/0/0",
                    is_created=False,
                    is_imported=True,
                    status=WalletStatus.ACTIVE
                )
                wallet = EthereumWallet(config, self.api_keys)
            
            elif chain_type == "bsc":
                # Même logique que Ethereum
                from eth_account import Account
                Account.enable_unaudited_hdwallet_features()
                account = Account.from_mnemonic(mnemonic)
                address = account.address
                private_key = account.key.hex()
                
                config = WalletConfig(
                    wallet_id=uuid4(),
                    user_id=UUID("00000000-0000-0000-0000-000000000000"),
                    name=f"Recovered {chain_type} Wallet",
                    type=WalletType.HD,
                    blockchain=chain_type,
                    network=BlockchainNetwork(network),
                    address=address,
                    private_key_encrypted=private_key,
                    public_key=account.key.hex(),
                    mnemonic_encrypted=mnemonic,
                    derivation_path=derivation_path or "m/44'/60'/0'/0/0",
                    is_created=False,
                    is_imported=True,
                    status=WalletStatus.ACTIVE
                )
                wallet = BSCWallet(config, self.api_keys)
            
            elif chain_type == "polygon":
                # Même logique que Ethereum
                from eth_account import Account
                Account.enable_unaudited_hdwallet_features()
                account = Account.from_mnemonic(mnemonic)
                address = account.address
                private_key = account.key.hex()
                
                config = WalletConfig(
                    wallet_id=uuid4(),
                    user_id=UUID("00000000-0000-0000-0000-000000000000"),
                    name=f"Recovered {chain_type} Wallet",
                    type=WalletType.HD,
                    blockchain=chain_type,
                    network=BlockchainNetwork(network),
                    address=address,
                    private_key_encrypted=private_key,
                    public_key=account.key.hex(),
                    mnemonic_encrypted=mnemonic,
                    derivation_path=derivation_path or "m/44'/60'/0'/0/0",
                    is_created=False,
                    is_imported=True,
                    status=WalletStatus.ACTIVE
                )
                wallet = PolygonWallet(config, self.api_keys)
            
            elif chain_type == "solana":
                from solders.keypair import Keypair
                from solders.pubkey import Pubkey
                from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
                
                # Génération du keypair Solana à partir de la mnémonique
                seed = Bip39SeedGenerator(mnemonic).Generate()
                bip44_ctx = Bip44.FromSeed(seed, Bip44Coins.SOLANA)
                keypair = bip44_ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
                
                private_key = bytes(keypair.PrivateKey().Raw().ToBytes()).hex()
                public_key = str(keypair.PublicKey().Raw().ToBytes().ToBytes())
                address = str(keypair.PublicKey().Raw().ToBytes())
                
                config = WalletConfig(
                    wallet_id=uuid4(),
                    user_id=UUID("00000000-0000-0000-0000-000000000000"),
                    name=f"Recovered {chain_type} Wallet",
                    type=WalletType.HD,
                    blockchain=chain_type,
                    network=BlockchainNetwork(network),
                    address=address,
                    private_key_encrypted=private_key,
                    public_key=public_key,
                    mnemonic_encrypted=mnemonic,
                    derivation_path=derivation_path or "m/44'/501'/0'/0'",
                    is_created=False,
                    is_imported=True,
                    status=WalletStatus.ACTIVE
                )
                wallet = SolanaWallet(config, self.api_keys)
            
            else:
                raise ValueError(f"Blockchain non supportée: {chain_type}")
            
            await wallet.initialize()
            
            logger.info(f"Wallet récupéré depuis mnémonique: {wallet.config.address}")
            return wallet

        except Exception as e:
            logger.error(f"Erreur lors de la récupération depuis mnémonique: {e}")
            raise

    # ========================================================================
    # GESTION DES SAUVEGARDES
    # ========================================================================

    async def get_backup_metadata(
        self,
        backup_id: UUID
    ) -> Optional[BackupMetadata]:
        """
        Récupère les métadonnées d'une sauvegarde.

        Args:
            backup_id: ID de la sauvegarde

        Returns:
            Métadonnées de la sauvegarde
        """
        try:
            # Vérification du cache
            if backup_id in self._backup_cache:
                return self._backup_cache[backup_id]

            # Vérification dans Redis
            if self.redis:
                metadata = await self._retrieve_metadata(backup_id)
                if metadata:
                    self._backup_cache[backup_id] = metadata
                    return metadata

            # Vérification dans le système de fichiers
            metadata_file = self.storage_path / f"{backup_id}.meta"
            if metadata_file.exists():
                async with aiofiles.open(metadata_file, 'r') as f:
                    data = await f.read()
                    metadata_dict = json.loads(data)
                    metadata = BackupMetadata(**metadata_dict)
                    self._backup_cache[backup_id] = metadata
                    return metadata

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des métadonnées: {e}")
            return None

    async def list_backups(
        self,
        user_id: Optional[UUID] = None,
        wallet_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[BackupMetadata]:
        """
        Liste les sauvegardes.

        Args:
            user_id: ID de l'utilisateur (optionnel)
            wallet_id: ID du wallet (optionnel)
            limit: Nombre de sauvegardes
            offset: Décalage

        Returns:
            Liste des sauvegardes
        """
        backups = []

        try:
            # Récupération depuis Redis si disponible
            if self.redis:
                backup_ids = await self._list_backup_ids(user_id, wallet_id)
                for backup_id in backup_ids[offset:offset + limit]:
                    metadata = await self.get_backup_metadata(backup_id)
                    if metadata:
                        backups.append(metadata)
            else:
                # Récupération depuis le système de fichiers
                for file_path in self.storage_path.glob("*.meta"):
                    try:
                        async with aiofiles.open(file_path, 'r') as f:
                            data = await f.read()
                            metadata_dict = json.loads(data)
                            metadata = BackupMetadata(**metadata_dict)
                            
                            if user_id and metadata.user_id != user_id:
                                continue
                            if wallet_id and metadata.wallet_id != wallet_id:
                                continue
                            
                            backups.append(metadata)
                    except Exception as e:
                        logger.error(f"Erreur lors de la lecture de {file_path}: {e}")

            return backups[:limit]

        except Exception as e:
            logger.error(f"Erreur lors du listing des sauvegardes: {e}")
            return []

    async def delete_backup(
        self,
        backup_id: UUID,
        permanent: bool = False
    ) -> bool:
        """
        Supprime une sauvegarde.

        Args:
            backup_id: ID de la sauvegarde
            permanent: Suppression définitive

        Returns:
            True si supprimé
        """
        try:
            metadata = await self.get_backup_metadata(backup_id)
            if not metadata:
                return False

            # Suppression du fichier
            backup_path = Path(metadata.storage_location)
            if backup_path.exists():
                if permanent:
                    backup_path.unlink()
                else:
                    # Déplacement vers la corbeille
                    trash_path = self.storage_path / "trash" / backup_path.name
                    trash_path.parent.mkdir(parents=True, exist_ok=True)
                    backup_path.rename(trash_path)

            # Suppression des métadonnées
            metadata_file = self.storage_path / f"{backup_id}.meta"
            if metadata_file.exists():
                metadata_file.unlink()

            # Suppression du cache
            if backup_id in self._backup_cache:
                del self._backup_cache[backup_id]

            # Suppression de Redis
            if self.redis:
                await self._delete_metadata(backup_id)

            # Mise à jour des métriques
            self._metrics["storage_used_bytes"] -= metadata.size_bytes

            logger.info(f"Sauvegarde supprimée: {backup_id}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la sauvegarde: {e}")
            return False

    # ========================================================================
    # SAUVEGARDE D'URGENCE
    # ========================================================================

    async def create_emergency_backup(
        self,
        wallet: BaseWallet,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crée une sauvegarde d'urgence (format lisible).

        Args:
            wallet: Wallet à sauvegarder
            output_path: Chemin de sortie (optionnel)

        Returns:
            Données de sauvegarde d'urgence
        """
        try:
            # Extraction des données
            data = await self._extract_wallet_data(wallet)
            
            # Création du dictionnaire de sauvegarde d'urgence
            emergency_data = {
                "wallet_id": str(data.wallet_id),
                "user_id": str(data.user_id),
                "chain_type": data.chain_type,
                "network": data.network,
                "address": data.address,
                "private_key": data.private_key_encrypted,
                "public_key": data.public_key,
                "mnemonic": data.mnemonic_encrypted,
                "derivation_path": data.derivation_path,
                "created_at": data.created_at.isoformat(),
                "metadata": data.metadata,
                "emergency": {
                    "created": datetime.now().isoformat(),
                    "version": self.BACKUP_VERSION,
                    "type": "emergency_backup",
                    "instructions": """
                        ⚠️ SAUVEGARDE D'URGENCE - CONSERVER EN LIEU SÉCURISÉ
                        1. Cette sauvegarde contient vos clés privées
                        2. Ne jamais partager ces informations
                        3. Stocker dans un endroit physiquement sécurisé
                        4. Utiliser uniquement en cas d'urgence absolue
                    """
                }
            }
            
            # Écriture du fichier si demandé
            if output_path:
                async with aiofiles.open(output_path, 'w') as f:
                    await f.write(json.dumps(emergency_data, indent=2))
                logger.info(f"Sauvegarde d'urgence créée: {output_path}")
            
            return emergency_data

        except Exception as e:
            logger.error(f"Erreur lors de la création de la sauvegarde d'urgence: {e}")
            raise

    # ========================================================================
    # MÉTHODES DE STOCKAGE
    # ========================================================================

    async def _store_metadata(self, metadata: BackupMetadata) -> None:
        """
        Stocke les métadonnées dans Redis.

        Args:
            metadata: Métadonnées à stocker
        """
        try:
            key = f"backup:metadata:{metadata.backup_id}"
            await self.redis.setex(
                key,
                86400 * 30,  # 30 jours
                json.dumps(metadata.to_dict())
            )
            
            # Index par utilisateur
            user_key = f"backup:user:{metadata.user_id}"
            await self.redis.sadd(user_key, str(metadata.backup_id))
            
            # Index par wallet
            wallet_key = f"backup:wallet:{metadata.wallet_id}"
            await self.redis.sadd(wallet_key, str(metadata.backup_id))

        except Exception as e:
            logger.error(f"Erreur lors du stockage des métadonnées: {e}")

    async def _retrieve_metadata(
        self,
        backup_id: UUID
    ) -> Optional[BackupMetadata]:
        """
        Récupère les métadonnées depuis Redis.

        Args:
            backup_id: ID de la sauvegarde

        Returns:
            Métadonnées ou None
        """
        try:
            key = f"backup:metadata:{backup_id}"
            data = await self.redis.get(key)
            if data:
                metadata_dict = json.loads(data)
                return BackupMetadata(**metadata_dict)
            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des métadonnées: {e}")
            return None

    async def _delete_metadata(self, backup_id: UUID) -> None:
        """
        Supprime les métadonnées de Redis.

        Args:
            backup_id: ID de la sauvegarde
        """
        try:
            # Récupération des métadonnées d'abord
            metadata = await self._retrieve_metadata(backup_id)
            if metadata:
                # Suppression des index
                user_key = f"backup:user:{metadata.user_id}"
                await self.redis.srem(user_key, str(backup_id))
                
                wallet_key = f"backup:wallet:{metadata.wallet_id}"
                await self.redis.srem(wallet_key, str(backup_id))
            
            # Suppression des métadonnées
            key = f"backup:metadata:{backup_id}"
            await self.redis.delete(key)

        except Exception as e:
            logger.error(f"Erreur lors de la suppression des métadonnées: {e}")

    async def _list_backup_ids(
        self,
        user_id: Optional[UUID] = None,
        wallet_id: Optional[UUID] = None
    ) -> List[UUID]:
        """
        Liste les IDs de sauvegarde depuis Redis.

        Args:
            user_id: ID de l'utilisateur
            wallet_id: ID du wallet

        Returns:
            Liste des IDs
        """
        try:
            if user_id:
                key = f"backup:user:{user_id}"
            elif wallet_id:
                key = f"backup:wallet:{wallet_id}"
            else:
                return []

            ids = await self.redis.smembers(key)
            return [UUID(id.decode()) for id in ids]

        except Exception as e:
            logger.error(f"Erreur lors du listing des IDs: {e}")
            return []

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_storage_usage(self) -> Dict[str, Any]:
        """
        Récupère l'utilisation du stockage.

        Returns:
            Utilisation du stockage
        """
        try:
            total_size = 0
            file_count = 0
            
            for file_path in self.storage_path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1

            return {
                "total_bytes": total_size,
                "total_mb": total_size / (1024 * 1024),
                "total_gb": total_size / (1024 * 1024 * 1024),
                "file_count": file_count,
                "backup_count": self._metrics["total_backups"],
                "storage_path": str(self.storage_path),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'utilisation du stockage: {e}")
            return {}

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            storage_usage = await self.get_storage_usage()
            
            return {
                "status": "healthy",
                "total_backups": self._metrics["total_backups"],
                "total_restores": self._metrics["total_restores"],
                "total_encrypted": self._metrics["total_encrypted"],
                "storage_used_bytes": self._metrics["storage_used_bytes"],
                "storage_usage": storage_usage,
                "last_backup": self._metrics["last_backup"],
                "last_restore": self._metrics["last_restore"],
                "cached_backups": len(self._backup_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def cleanup(self, days: int = 30) -> Dict[str, Any]:
        """
        Nettoie les sauvegardes anciennes.

        Args:
            days: Âge maximum en jours

        Returns:
            Résultat du nettoyage
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            deleted = 0
            size_freed = 0
            
            backups = await self.list_backups()
            
            for backup in backups:
                if backup.created_at < cutoff:
                    # Suppression de la sauvegarde
                    if await self.delete_backup(backup.backup_id, permanent=True):
                        deleted += 1
                        size_freed += backup.size_bytes
            
            return {
                "deleted_count": deleted,
                "size_freed_bytes": size_freed,
                "size_freed_mb": size_freed / (1024 * 1024),
                "cutoff_date": cutoff.isoformat(),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")
            return {"error": str(e)}

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de WalletBackupService...")
        self._backup_cache.clear()
        self._recovery_cache.clear()
        logger.info("WalletBackupService fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_backup_service(
    storage_path: str = "./backups",
    encryption_key: Optional[str] = None,
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None
) -> WalletBackupService:
    """
    Crée une instance du service de sauvegarde.

    Args:
        storage_path: Chemin de stockage
        encryption_key: Clé de chiffrement maître
        redis_url: URL de connexion Redis
        api_keys: Clés API

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletBackupService(
        storage_path=storage_path,
        encryption_key=encryption_key,
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BackupType",
    "BackupStatus",
    "RecoveryMethod",
    "BackupMetadata",
    "BackupData",
    "BackupRecovery",
    "WalletBackupService",
    "create_wallet_backup_service"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service de sauvegarde."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET BACKUP MODULE")
    print("=" * 60)

    # Création du service
    backup_service = create_wallet_backup_service(
        storage_path="./backups",
        encryption_key="my-secure-encryption-key-32-bytes!!",
        api_keys={}
    )

    # Création d'un wallet exemple
    from .ethereum_wallet import create_ethereum_wallet
    from uuid import UUID
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="Backup Wallet"
    )
    
    await wallet.initialize()

    print(f"\n✅ Wallet créé:")
    print(f"   Adresse: {wallet.config.address}")

    # Création d'une sauvegarde
    backup = await backup_service.create_backup(
        wallet=wallet,
        backup_type=BackupType.ENCRYPTED,
        password="my-secure-password",
        metadata={"purpose": "testing"}
    )

    print(f"\n📦 Sauvegarde créée:")
    print(f"   ID: {backup.backup_id}")
    print(f"   Type: {backup.backup_type.value}")
    print(f"   Taille: {backup.size_bytes} bytes")
    print(f"   Checksum: {backup.checksum[:16]}...")

    # Listing des sauvegardes
    backups = await backup_service.list_backups(user_id=user_id)
    print(f"\n📋 Sauvegardes: {len(backups)}")

    # Restauration de la sauvegarde
    recovery = await backup_service.restore_backup(
        backup_id=backup.backup_id,
        password="my-secure-password"
    )

    print(f"\n🔄 Restauration:")
    print(f"   ID: {recovery.recovery_id}")
    print(f"   Statut: {recovery.status}")

    # Sauvegarde d'urgence
    emergency = await backup_service.create_emergency_backup(
        wallet=wallet,
        output_path="./emergency_backup.json"
    )

    print(f"\n🚨 Sauvegarde d'urgence:")
    print(f"   Fichier: emergency_backup.json")
    print(f"   Adresse: {emergency['address']}")

    # Santé du service
    health = await backup_service.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Sauvegardes: {health['total_backups']}")
    print(f"   Restaurations: {health['total_restores']}")
    print(f"   Stockage utilisé: {health['storage_used_bytes']} bytes")

    # Nettoyage
    cleanup = await backup_service.cleanup(days=30)
    print(f"\n🧹 Nettoyage:")
    print(f"   Supprimées: {cleanup['deleted_count']}")
    print(f"   Espace libéré: {cleanup['size_freed_mb']:.2f} MB")

    # Fermeture
    await backup_service.close()
    await wallet.close()

    print("\n" + "=" * 60)
    print("WalletBackupService NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

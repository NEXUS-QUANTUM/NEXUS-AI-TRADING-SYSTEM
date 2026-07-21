"""
NEXUS AI TRADING SYSTEM - WALLET HD MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des wallets HD (Hierarchical Deterministic) multi-blockchain.
Support des standards BIP32, BIP39, BIP44, BIP49, BIP84, et SLIP44.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import base58
import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import bip39
import coincurve
import ed25519
from bip32 import BIP32
from bip32.utils import (
    derive_child_key,
    get_public_key_from_private_key,
    is_private_key,
    is_public_key
)
from eth_account import Account
from solders.keypair import Keypair
from web3 import Web3

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    BlockchainNetwork,
    WalletStatus,
    WalletType
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class HDStandard(Enum):
    """Standards HD supportés."""
    BIP32 = "bip32"
    BIP39 = "bip39"
    BIP44 = "bip44"
    BIP49 = "bip49"  # P2WPKH-nested-in-P2SH
    BIP84 = "bip84"  # Native SegWit
    BIP86 = "bip86"  # Taproot
    SLIP44 = "slip44"


class HDCoinType(Enum):
    """Types de coins pour BIP44."""
    BITCOIN = 0
    ETHEREUM = 60
    BINANCE = 714
    SOLANA = 501
    POLYGON = 966
    AVALANCHE = 9000
    TRON = 195
    POLKADOT = 354
    COSMOS = 118
    CARDANO = 1815
    ARBITRUM = 9001
    OPTIMISM = 9002


# Mapping des blockchains vers les coin types
COIN_TYPE_MAP = {
    "bitcoin": HDCoinType.BITCOIN,
    "ethereum": HDCoinType.ETHEREUM,
    "bsc": HDCoinType.BINANCE,
    "solana": HDCoinType.SOLANA,
    "polygon": HDCoinType.POLYGON,
    "avalanche": HDCoinType.AVALANCHE,
    "tron": HDCoinType.TRON,
    "polkadot": HDCoinType.POLKADOT,
    "cosmos": HDCoinType.COSMOS,
    "cardano": HDCoinType.CARDANO,
    "arbitrum": HDCoinType.ARBITRUM,
    "optimism": HDCoinType.OPTIMISM
}


@dataclass
class HDWalletPath:
    """Chemin de dérivation HD."""
    purpose: int
    coin_type: int
    account: int
    change: int
    index: int
    full_path: str = ""

    def __post_init__(self):
        """Génère le chemin complet après initialisation."""
        if not self.full_path:
            self.full_path = f"m/{self.purpose}'/{self.coin_type}'/{self.account}'/{self.change}/{self.index}"

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "purpose": self.purpose,
            "coin_type": self.coin_type,
            "account": self.account,
            "change": self.change,
            "index": self.index,
            "full_path": self.full_path
        }


@dataclass
class HDWalletInfo:
    """Informations d'un wallet HD."""
    wallet_id: UUID
    user_id: UUID
    name: str
    mnemonic_encrypted: str
    seed_encrypted: str
    root_private_key: str
    root_public_key: str
    master_fingerprint: str
    chain_code: str
    standard: HDStandard
    coin_type: HDCoinType
    account_index: int
    addresses: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "mnemonic_encrypted": self.mnemonic_encrypted,
            "seed_encrypted": self.seed_encrypted,
            "root_private_key": self.root_private_key,
            "root_public_key": self.root_public_key,
            "master_fingerprint": self.master_fingerprint,
            "chain_code": self.chain_code,
            "standard": self.standard.value,
            "coin_type": self.coin_type.value,
            "account_index": self.account_index,
            "addresses": self.addresses,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class HDAddress:
    """Adresse HD dérivée."""
    path: HDWalletPath
    address: str
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    index: int = 0
    is_used: bool = False
    balance: Decimal = Decimal("0")
    transaction_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "path": self.path.to_dict(),
            "address": self.address,
            "private_key": self.private_key,
            "public_key": self.public_key,
            "index": self.index,
            "is_used": self.is_used,
            "balance": str(self.balance),
            "transaction_count": self.transaction_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None
        }


# ============================================================================
# CLASSE HD WALLET
# ============================================================================

class HDWallet:
    """
    Wallet HD (Hierarchical Deterministic) multi-blockchain.
    """

    # Mnemonic word lists
    MNEMONIC_WORD_COUNTS = [12, 15, 18, 21, 24]
    MNEMONIC_LANGUAGES = ["english", "french", "spanish", "chinese", "japanese", "korean"]

    # Derivation paths par blockchain
    DERIVATION_PATHS = {
        "bitcoin": {
            "bip44": "m/44'/0'/0'/0/0",
            "bip49": "m/49'/0'/0'/0/0",
            "bip84": "m/84'/0'/0'/0/0",
            "bip86": "m/86'/0'/0'/0/0"
        },
        "ethereum": {
            "bip44": "m/44'/60'/0'/0/0",
            "bip49": "m/49'/60'/0'/0/0",
            "bip84": "m/84'/60'/0'/0/0"
        },
        "bsc": {
            "bip44": "m/44'/714'/0'/0/0",
            "bip49": "m/49'/714'/0'/0/0",
            "bip84": "m/84'/714'/0'/0/0"
        },
        "solana": {
            "bip44": "m/44'/501'/0'/0'",
            "bip49": "m/49'/501'/0'/0'",
            "bip84": "m/84'/501'/0'/0'"
        },
        "polygon": {
            "bip44": "m/44'/966'/0'/0/0"
        },
        "avalanche": {
            "bip44": "m/44'/9000'/0'/0/0"
        },
        "tron": {
            "bip44": "m/44'/195'/0'/0/0"
        },
        "polkadot": {
            "bip44": "m/44'/354'/0'/0/0"
        },
        "cosmos": {
            "bip44": "m/44'/118'/0'/0/0"
        },
        "cardano": {
            "bip44": "m/44'/1815'/0'/0/0"
        },
        "arbitrum": {
            "bip44": "m/44'/9001'/0'/0/0"
        },
        "optimism": {
            "bip44": "m/44'/9002'/0'/0/0"
        }
    }

    def __init__(
        self,
        config: WalletConfig,
        mnemonic: Optional[str] = None,
        passphrase: str = "",
        standard: HDStandard = HDStandard.BIP44,
        account_index: int = 0
    ):
        """
        Initialise un wallet HD.

        Args:
            config: Configuration du wallet
            mnemonic: Phrase mnémonique (optionnel)
            passphrase: Passphrase supplémentaire
            standard: Standard HD à utiliser
            account_index: Index du compte
        """
        self.config = config
        self.mnemonic = mnemonic
        self.passphrase = passphrase
        self.standard = standard
        self.account_index = account_index
        
        # Éléments HD
        self.seed = None
        self.root_private_key = None
        self.root_public_key = None
        self.chain_code = None
        self.master_fingerprint = None
        self._bip32 = None
        
        # Cache des adresses dérivées
        self._address_cache: Dict[str, HDAddress] = {}
        self._address_index: Dict[str, int] = {}
        
        # Blockchain spécifique
        self._blockchain_type = config.blockchain.lower()
        
        # Initialisation
        self._initialize_hd_wallet()

        logger.info(f"HDWallet initialisé pour {config.address[:8]}...")

    def _initialize_hd_wallet(self) -> None:
        """Initialise le wallet HD."""
        try:
            if self.mnemonic:
                # Vérification de la mnémonique
                if not bip39.check_mnemonic(self.mnemonic):
                    raise ValueError("Phrase mnémonique invalide")
                
                # Génération du seed
                self.seed = bip39.mnemonic_to_seed(self.mnemonic, self.passphrase)
                
                # Création du BIP32
                self._bip32 = BIP32.from_seed(self.seed)
                
                # Récupération de la clé racine
                self.root_private_key = self._bip32.private_key
                self.root_public_key = self._bip32.public_key
                self.chain_code = self._bip32.chain_code
                self.master_fingerprint = self._bip32.fingerprint.hex()
                
            else:
                # Génération d'une nouvelle mnémonique
                self.mnemonic = self.generate_mnemonic()
                self._initialize_hd_wallet()

        except Exception as e:
            logger.error(f"Erreur d'initialisation du wallet HD: {e}")
            raise

    # ========================================================================
    # GÉNÉRATION DE MNÉMONIQUE
    # ========================================================================

    @staticmethod
    def generate_mnemonic(
        strength: int = 256,
        language: str = "english"
    ) -> str:
        """
        Génère une phrase mnémonique.

        Args:
            strength: Force (128, 160, 192, 224, 256)
            language: Langue de la mnémonique

        Returns:
            Phrase mnémonique
        """
        if language not in HDWallet.MNEMONIC_LANGUAGES:
            raise ValueError(f"Langue non supportée: {language}")
        
        # Mise à jour de la langue
        bip39.set_language(language)
        
        # Génération de la mnémonique
        mnemonic = bip39.generate_mnemonic(strength)
        
        # Réinitialisation de la langue par défaut
        bip39.set_language("english")
        
        return mnemonic

    @staticmethod
    def validate_mnemonic(
        mnemonic: str,
        language: str = "english"
    ) -> bool:
        """
        Valide une phrase mnémonique.

        Args:
            mnemonic: Phrase à valider
            language: Langue de la mnémonique

        Returns:
            True si la phrase est valide
        """
        try:
            if language not in HDWallet.MNEMONIC_LANGUAGES:
                return False
            
            bip39.set_language(language)
            valid = bip39.check_mnemonic(mnemonic)
            bip39.set_language("english")
            
            return valid
            
        except Exception:
            return False

    # ========================================================================
    # DÉRIVATION D'ADRESSES
    # ========================================================================

    def derive_address(
        self,
        path: Optional[str] = None,
        index: Optional[int] = None,
        chain: str = "0",
        account: int = 0
    ) -> HDAddress:
        """
        Dérive une adresse HD.

        Args:
            path: Chemin de dérivation complet (optionnel)
            index: Index de l'adresse (optionnel)
            chain: Chaîne de dérivation (0=external, 1=internal)
            account: Numéro de compte

        Returns:
            Adresse HD dérivée
        """
        try:
            # Construction du chemin
            if path:
                full_path = path
            else:
                coin_type = COIN_TYPE_MAP.get(self._blockchain_type, HDCoinType.ETHEREUM).value
                purpose = self._get_purpose()
                change = int(chain)
                idx = index or self._get_next_index(chain)
                
                full_path = f"m/{purpose}'/{coin_type}'/{account}'/{change}/{idx}"
            
            # Dérivation de la clé
            child_key = self._bip32.get_child(full_path)
            
            # Récupération des clés
            private_key = child_key.private_key
            public_key = child_key.public_key
            
            # Génération de l'adresse
            address = self._derive_address_from_keys(
                public_key,
                private_key
            )
            
            # Création de l'objet HDAddress
            hd_address = HDAddress(
                path=self._parse_path(full_path),
                address=address,
                private_key=private_key.hex() if private_key else None,
                public_key=public_key.hex() if public_key else None,
                index=idx,
                created_at=datetime.now()
            )
            
            # Mise en cache
            cache_key = f"{chain}:{idx}"
            self._address_cache[cache_key] = hd_address
            
            return hd_address

        except Exception as e:
            logger.error(f"Erreur lors de la dérivation de l'adresse: {e}")
            raise

    def derive_addresses(
        self,
        count: int = 10,
        chain: str = "0",
        account: int = 0
    ) -> List[HDAddress]:
        """
        Dérive plusieurs adresses HD.

        Args:
            count: Nombre d'adresses à dériver
            chain: Chaîne de dérivation (0=external, 1=internal)
            account: Numéro de compte

        Returns:
            Liste des adresses HD dérivées
        """
        addresses = []
        start_index = self._get_next_index(chain)
        
        for i in range(start_index, start_index + count):
            address = self.derive_address(
                index=i,
                chain=chain,
                account=account
            )
            addresses.append(address)
        
        return addresses

    def get_address_by_index(
        self,
        index: int,
        chain: str = "0",
        account: int = 0
    ) -> Optional[HDAddress]:
        """
        Récupère une adresse par son index.

        Args:
            index: Index de l'adresse
            chain: Chaîne de dérivation
            account: Numéro de compte

        Returns:
            Adresse HD ou None
        """
        cache_key = f"{chain}:{index}"
        if cache_key in self._address_cache:
            return self._address_cache[cache_key]
        
        return self.derive_address(
            index=index,
            chain=chain,
            account=account
        )

    def get_next_address(
        self,
        chain: str = "0",
        account: int = 0
    ) -> HDAddress:
        """
        Récupère la prochaine adresse non utilisée.

        Args:
            chain: Chaîne de dérivation
            account: Numéro de compte

        Returns:
            Prochaine adresse HD
        """
        index = self._get_next_index(chain)
        return self.derive_address(
            index=index,
            chain=chain,
            account=account
        )

    def mark_address_used(
        self,
        address: str,
        chain: str = "0"
    ) -> None:
        """
        Marque une adresse comme utilisée.

        Args:
            address: Adresse à marquer
            chain: Chaîne de dérivation
        """
        cache_key = f"{chain}:{address}"
        if cache_key in self._address_cache:
            self._address_cache[cache_key].is_used = True
            self._address_cache[cache_key].last_used = datetime.now()
            
            # Mise à jour de l'index
            if chain not in self._address_index:
                self._address_index[chain] = 0
            self._address_index[chain] += 1

    # ========================================================================
    # MÉTHODES SPÉCIFIQUES PAR BLOCKCHAIN
    # ========================================================================

    def _derive_address_from_keys(
        self,
        public_key: bytes,
        private_key: Optional[bytes] = None
    ) -> str:
        """
        Dérive une adresse à partir des clés.

        Args:
            public_key: Clé publique
            private_key: Clé privée (optionnel)

        Returns:
            Adresse dérivée
        """
        blockchain = self._blockchain_type
        
        if blockchain in ["ethereum", "bsc", "polygon", "avalanche", "arbitrum", "optimism"]:
            # Ethereum-style address
            return self._derive_eth_address(public_key)
        
        elif blockchain == "solana":
            # Solana address
            return self._derive_solana_address(public_key)
        
        elif blockchain == "tron":
            # Tron address
            return self._derive_tron_address(public_key)
        
        elif blockchain == "bitcoin":
            # Bitcoin address
            return self._derive_btc_address(public_key)
        
        else:
            # Fallback: Ethereum-style
            return self._derive_eth_address(public_key)

    def _derive_eth_address(self, public_key: bytes) -> str:
        """
        Dérive une adresse Ethereum.

        Args:
            public_key: Clé publique

        Returns:
            Adresse Ethereum
        """
        # Keccak-256 hash de la clé publique
        keccak = Web3.keccak(public_key)
        address = keccak[-20:].hex()
        return f"0x{address}"

    def _derive_solana_address(self, public_key: bytes) -> str:
        """
        Dérive une adresse Solana.

        Args:
            public_key: Clé publique

        Returns:
            Adresse Solana
        """
        # Solana utilise ed25519
        return base58.b58encode(public_key).decode('utf-8')

    def _derive_tron_address(self, public_key: bytes) -> str:
        """
        Dérive une adresse Tron.

        Args:
            public_key: Clé publique

        Returns:
            Adresse Tron
        """
        # Tron utilise le même format que Ethereum mais avec un préfixe différent
        keccak = Web3.keccak(public_key)
        address = keccak[-20:].hex()
        return f"41{address}"

    def _derive_btc_address(self, public_key: bytes) -> str:
        """
        Dérive une adresse Bitcoin.

        Args:
            public_key: Clé publique

        Returns:
            Adresse Bitcoin
        """
        # Pour l'exemple, nous utilisons un format simplifié
        # En production, utiliser bitcoinlib ou similaire
        import hashlib
        sha256 = hashlib.sha256(public_key).digest()
        ripemd160 = hashlib.new('ripemd160', sha256).digest()
        
        # Version 0x00 pour mainnet
        version = b'\x00'
        checksum = hashlib.sha256(hashlib.sha256(version + ripemd160).digest()).digest()[:4]
        address = base58.b58encode(version + ripemd160 + checksum).decode('utf-8')
        
        return address

    # ========================================================================
    # MÉTHODES PRIVÉES
    # ========================================================================

    def _get_purpose(self) -> int:
        """
        Récupère le purpose pour le standard HD.

        Returns:
            Purpose
        """
        purpose_map = {
            HDStandard.BIP44: 44,
            HDStandard.BIP49: 49,
            HDStandard.BIP84: 84,
            HDStandard.BIP86: 86,
            HDStandard.BIP32: 32
        }
        return purpose_map.get(self.standard, 44)

    def _get_next_index(self, chain: str = "0") -> int:
        """
        Récupère le prochain index disponible.

        Args:
            chain: Chaîne de dérivation

        Returns:
            Prochain index
        """
        if chain not in self._address_index:
            self._address_index[chain] = 0
        
        return self._address_index[chain]

    def _parse_path(self, path: str) -> HDWalletPath:
        """
        Parse un chemin de dérivation.

        Args:
            path: Chemin de dérivation

        Returns:
            Objet HDWalletPath
        """
        parts = path.split('/')
        
        # Suppression du 'm' initial
        if parts[0] == 'm':
            parts = parts[1:]
        
        purpose = int(parts[0].replace("'", ""))
        coin_type = int(parts[1].replace("'", ""))
        account = int(parts[2].replace("'", ""))
        change = int(parts[3].replace("'", ""))
        index = int(parts[4].replace("'", ""))
        
        return HDWalletPath(
            purpose=purpose,
            coin_type=coin_type,
            account=account,
            change=change,
            index=index,
            full_path=path
        )

    def _get_blockchain_coin_type(self) -> HDCoinType:
        """
        Récupère le coin type pour la blockchain.

        Returns:
            Coin type
        """
        return COIN_TYPE_MAP.get(self._blockchain_type, HDCoinType.ETHEREUM)

    # ========================================================================
    # MÉTHODES DE SAUVEGARDE ET RESTAURATION
    # ========================================================================

    def export_keystore(
        self,
        password: str,
        address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exporte le wallet au format keystore.

        Args:
            password: Mot de passe pour le chiffrement
            address: Adresse à exporter (optionnel)

        Returns:
            Keystore JSON
        """
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
            
            # Création du keystore
            private_key = self.root_private_key.hex() if self.root_private_key else None
            
            if private_key:
                account = Account.from_key(private_key)
                keystore = account.encrypt(password)
                return keystore
            
            return {}

        except Exception as e:
            logger.error(f"Erreur lors de l'export du keystore: {e}")
            return {}

    @staticmethod
    def import_keystore(
        keystore: Dict[str, Any],
        password: str
    ) -> Tuple[str, str]:
        """
        Importe un keystore.

        Args:
            keystore: Keystore JSON
            password: Mot de passe

        Returns:
            (adresse, clé privée)
        """
        try:
            from eth_account import Account
            
            # Décryptage du keystore
            account = Account.decrypt(keystore, password)
            private_key = account.key.hex()
            address = account.address
            
            return address, private_key

        except Exception as e:
            logger.error(f"Erreur lors de l'import du keystore: {e}")
            raise

    def export_json(self) -> Dict[str, Any]:
        """
        Exporte le wallet au format JSON.

        Returns:
            JSON du wallet
        """
        return {
            "wallet_id": str(self.config.wallet_id),
            "mnemonic": self.mnemonic,
            "seed": self.seed.hex() if self.seed else None,
            "root_private_key": self.root_private_key.hex() if self.root_private_key else None,
            "root_public_key": self.root_public_key.hex() if self.root_public_key else None,
            "chain_code": self.chain_code.hex() if self.chain_code else None,
            "master_fingerprint": self.master_fingerprint,
            "standard": self.standard.value,
            "account_index": self.account_index,
            "addresses": {
                k: v.to_dict() for k, v in self._address_cache.items()
            }
        }

    @staticmethod
    def import_json(data: Dict[str, Any]) -> Tuple[str, str]:
        """
        Importe un wallet depuis JSON.

        Args:
            data: JSON du wallet

        Returns:
            (mnemonic, seed)
        """
        mnemonic = data.get("mnemonic")
        seed = data.get("seed")
        
        if not mnemonic and not seed:
            raise ValueError("Mnémonique ou seed requis")
        
        return mnemonic, seed

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    def get_info(self) -> Dict[str, Any]:
        """
        Récupère les informations du wallet HD.

        Returns:
            Informations du wallet
        """
        return {
            "wallet_id": str(self.config.wallet_id),
            "blockchain": self._blockchain_type,
            "standard": self.standard.value,
            "account_index": self.account_index,
            "master_fingerprint": self.master_fingerprint,
            "derivation_paths": self.DERIVATION_PATHS.get(self._blockchain_type, {}),
            "address_count": len(self._address_cache),
            "next_index": self._get_next_index(),
            "created_at": self.config.created_at.isoformat()
        }

    def get_balance(self) -> Decimal:
        """
        Récupère le solde total du wallet HD.

        Returns:
            Solde total
        """
        total_balance = Decimal("0")
        for address in self._address_cache.values():
            total_balance += address.balance
        return total_balance


# ============================================================================
# FACTORY HD WALLET
# ============================================================================

class HDWalletFactory:
    """
    Factory pour créer des wallets HD multi-blockchain.
    """

    @staticmethod
    def create_wallet(
        user_id: UUID,
        name: str,
        blockchain: str,
        network: BlockchainNetwork,
        mnemonic: Optional[str] = None,
        passphrase: str = "",
        standard: HDStandard = HDStandard.BIP44,
        account_index: int = 0,
        strength: int = 256,
        language: str = "english"
    ) -> HDWallet:
        """
        Crée un wallet HD.

        Args:
            user_id: ID de l'utilisateur
            name: Nom du wallet
            blockchain: Blockchain
            network: Réseau
            mnemonic: Phrase mnémonique (optionnel)
            passphrase: Passphrase (optionnel)
            standard: Standard HD
            account_index: Index du compte
            strength: Force de la mnémonique
            language: Langue de la mnémonique

        Returns:
            Wallet HD créé
        """
        # Génération de la mnémonique si non fournie
        if not mnemonic:
            mnemonic = HDWallet.generate_mnemonic(strength, language)
        
        # Dérivation de l'adresse racine
        temp_wallet = HDWallet(
            config=WalletConfig(
                wallet_id=uuid4(),
                user_id=user_id,
                name=name,
                type=WalletType.HD,
                blockchain=blockchain,
                network=network,
                address="",
                status=WalletStatus.ACTIVE
            ),
            mnemonic=mnemonic,
            passphrase=passphrase,
            standard=standard,
            account_index=account_index
        )
        
        # Dérivation de la première adresse
        first_address = temp_wallet.derive_address()
        temp_wallet.config.address = first_address.address
        
        return temp_wallet

    @staticmethod
    def create_from_mnemonic(
        mnemonic: str,
        user_id: UUID,
        name: str,
        blockchain: str,
        network: BlockchainNetwork,
        passphrase: str = "",
        standard: HDStandard = HDStandard.BIP44,
        account_index: int = 0
    ) -> HDWallet:
        """
        Crée un wallet HD à partir d'une mnémonique.

        Args:
            mnemonic: Phrase mnémonique
            user_id: ID de l'utilisateur
            name: Nom du wallet
            blockchain: Blockchain
            network: Réseau
            passphrase: Passphrase
            standard: Standard HD
            account_index: Index du compte

        Returns:
            Wallet HD créé
        """
        # Validation de la mnémonique
        if not HDWallet.validate_mnemonic(mnemonic):
            raise ValueError("Phrase mnémonique invalide")
        
        return HDWalletFactory.create_wallet(
            user_id=user_id,
            name=name,
            blockchain=blockchain,
            network=network,
            mnemonic=mnemonic,
            passphrase=passphrase,
            standard=standard,
            account_index=account_index
        )

    @staticmethod
    def create_from_seed(
        seed: bytes,
        user_id: UUID,
        name: str,
        blockchain: str,
        network: BlockchainNetwork,
        standard: HDStandard = HDStandard.BIP44,
        account_index: int = 0
    ) -> HDWallet:
        """
        Crée un wallet HD à partir d'un seed.

        Args:
            seed: Seed bytes
            user_id: ID de l'utilisateur
            name: Nom du wallet
            blockchain: Blockchain
            network: Réseau
            standard: Standard HD
            account_index: Index du compte

        Returns:
            Wallet HD créé
        """
        # Conversion du seed en mnémonique
        mnemonic = bip39.mnemonic_from_bytes(seed)
        
        return HDWalletFactory.create_wallet(
            user_id=user_id,
            name=name,
            blockchain=blockchain,
            network=network,
            mnemonic=mnemonic,
            standard=standard,
            account_index=account_index
        )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "HDStandard",
    "HDCoinType",
    "HDWalletPath",
    "HDWalletInfo",
    "HDAddress",
    "HDWallet",
    "HDWalletFactory",
    "COIN_TYPE_MAP"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du wallet HD."""
    print("=" * 60)
    print("NEXUS AI TRADING - HD WALLET MODULE")
    print("=" * 60)

    # Création d'un wallet HD
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    wallet = HDWalletFactory.create_wallet(
        user_id=user_id,
        name="Main HD Wallet",
        blockchain="ethereum",
        network=BlockchainNetwork.ETHEREUM_MAINNET,
        standard=HDStandard.BIP44,
        account_index=0
    )

    print(f"\n✅ Wallet HD créé:")
    print(f"   ID: {wallet.config.wallet_id}")
    print(f"   Blockchain: {wallet._blockchain_type}")
    print(f"   Standard: {wallet.standard.value}")
    print(f"   Master Fingerprint: {wallet.master_fingerprint}")

    # Récupération de la mnémonique
    print(f"\n🔑 Mnémonique (CONSERVER EN LIEU SÉCURISÉ):")
    print(f"   {wallet.mnemonic}")

    # Dérivation des adresses
    print(f"\n📍 Adresses dérivées:")
    for i in range(5):
        address = wallet.derive_address(index=i)
        print(f"   [{i}] {address.address[:8]}...{address.address[-8:]}")

    # Dérivation de plusieurs adresses
    addresses = wallet.derive_addresses(count=10)
    print(f"\n📋 {len(addresses)} adresses dérivées")

    # Récupération de la prochaine adresse
    next_address = wallet.get_next_address()
    print(f"\n🚀 Prochaine adresse: {next_address.address[:8]}...{next_address.address[-8:]}")

    # Export du keystore
    keystore = wallet.export_keystore("my-secure-password")
    print(f"\n🔐 Keystore exporté (simplifié):")
    print(f"   Version: {keystore.get('version', 'N/A')}")

    # Informations du wallet
    info = wallet.get_info()
    print(f"\n📊 Informations du wallet:")
    print(f"   Blockchain: {info['blockchain']}")
    print(f"   Standard: {info['standard']}")
    print(f"   Adresses dérivées: {info['address_count']}")
    print(f"   Prochain index: {info['next_index']}")

    print("\n" + "=" * 60)
    print("HDWallet module NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

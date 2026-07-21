"""
NEXUS AI TRADING SYSTEM - BASE WALLET MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Classe de base pour tous les wallets multi-blockchain.
Support des wallets Ethereum, Solana, Binance, Polygon, Avalanche, etc.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import base58
import bip39
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.eth import AsyncEth
from web3.middleware import geth_poa_middleware

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class WalletType(Enum):
    """Types de wallets."""
    EOA = "eoa"  # Externally Owned Account
    CONTRACT = "contract"
    MULTISIG = "multisig"
    HD = "hd"  # Hierarchical Deterministic
    SMART = "smart"
    MPC = "mpc"  # Multi-Party Computation


class WalletStatus(Enum):
    """Statuts d'un wallet."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    FROZEN = "frozen"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class BlockchainNetwork(Enum):
    """Réseaux blockchain supportés."""
    # Ethereum
    ETHEREUM_MAINNET = "ethereum_mainnet"
    ETHEREUM_GOERLI = "ethereum_goerli"
    ETHEREUM_SEPOLIA = "ethereum_sepolia"
    
    # Binance
    BSC_MAINNET = "bsc_mainnet"
    BSC_TESTNET = "bsc_testnet"
    
    # Polygon
    POLYGON_MAINNET = "polygon_mainnet"
    POLYGON_MUMBAI = "polygon_mumbai"
    
    # Solana
    SOLANA_MAINNET = "solana_mainnet"
    SOLANA_DEVNET = "solana_devnet"
    SOLANA_TESTNET = "solana_testnet"
    
    # Avalanche
    AVALANCHE_MAINNET = "avalanche_mainnet"
    AVALANCHE_FUJI = "avalanche_fuji"
    
    # Arbitrum
    ARBITRUM_MAINNET = "arbitrum_mainnet"
    ARBITRUM_GOERLI = "arbitrum_goerli"
    
    # Optimism
    OPTIMISM_MAINNET = "optimism_mainnet"
    OPTIMISM_GOERLI = "optimism_goerli"
    
    # Cardano
    CARDANO_MAINNET = "cardano_mainnet"
    CARDANO_TESTNET = "cardano_testnet"


class TransactionType(Enum):
    """Types de transactions."""
    SEND = "send"
    RECEIVE = "receive"
    STAKING = "staking"
    UNSTAKING = "unstaking"
    CLAIM_REWARDS = "claim_rewards"
    SWAP = "swap"
    BRIDGE = "bridge"
    APPROVAL = "approval"
    DEPLOY = "deploy"
    MULTISIG = "multisig"
    CUSTOM = "custom"


class TransactionStatus(Enum):
    """Statuts d'une transaction."""
    PENDING = "pending"
    PROCESSING = "processing"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REPLACED = "replaced"
    TIMEOUT = "timeout"


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class WalletConfig:
    """Configuration d'un wallet."""
    wallet_id: UUID
    user_id: UUID
    name: str
    type: WalletType
    blockchain: str
    network: BlockchainNetwork
    address: str
    private_key_encrypted: Optional[str] = None
    public_key: Optional[str] = None
    mnemonic_encrypted: Optional[str] = None
    derivation_path: Optional[str] = None
    is_hardware: bool = False
    is_imported: bool = False
    is_created: bool = False
    status: WalletStatus = WalletStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit la configuration en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "type": self.type.value,
            "blockchain": self.blockchain,
            "network": self.network.value,
            "address": self.address,
            "private_key_encrypted": self.private_key_encrypted,
            "public_key": self.public_key,
            "mnemonic_encrypted": self.mnemonic_encrypted,
            "derivation_path": self.derivation_path,
            "is_hardware": self.is_hardware,
            "is_imported": self.is_imported,
            "is_created": self.is_created,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class WalletBalance:
    """Solde d'un wallet."""
    wallet_id: UUID
    address: str
    blockchain: str
    network: BlockchainNetwork
    native_balance: Decimal
    native_balance_usd: Decimal
    token_balances: Dict[str, Decimal] = field(default_factory=dict)
    token_balances_usd: Dict[str, Decimal] = field(default_factory=dict)
    total_balance_usd: Decimal = Decimal("0")
    last_updated: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le solde en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "address": self.address,
            "blockchain": self.blockchain,
            "network": self.network.value,
            "native_balance": str(self.native_balance),
            "native_balance_usd": str(self.native_balance_usd),
            "token_balances": {k: str(v) for k, v in self.token_balances.items()},
            "token_balances_usd": {k: str(v) for k, v in self.token_balances_usd.items()},
            "total_balance_usd": str(self.total_balance_usd),
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class Transaction:
    """Transaction blockchain."""
    tx_id: UUID
    wallet_id: UUID
    user_id: UUID
    blockchain: str
    network: BlockchainNetwork
    tx_type: TransactionType
    from_address: str
    to_address: str
    amount: Decimal
    amount_usd: Decimal
    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    block_hash: Optional[str] = None
    gas_used: Optional[int] = None
    gas_price: Optional[Decimal] = None
    gas_currency: Optional[str] = None
    status: TransactionStatus = TransactionStatus.PENDING
    confirmations: int = 0
    required_confirmations: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit la transaction en dictionnaire."""
        return {
            "tx_id": str(self.tx_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "blockchain": self.blockchain,
            "network": self.network.value,
            "tx_type": self.tx_type.value,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "amount": str(self.amount),
            "amount_usd": str(self.amount_usd),
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "gas_used": self.gas_used,
            "gas_price": str(self.gas_price) if self.gas_price else None,
            "gas_currency": self.gas_currency,
            "status": self.status.value,
            "confirmations": self.confirmations,
            "required_confirmations": self.required_confirmations,
            "timestamp": self.timestamp.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


@dataclass
class TokenInfo:
    """Informations sur un token."""
    address: str
    symbol: str
    name: str
    decimals: int
    blockchain: str
    network: BlockchainNetwork
    price_usd: Optional[float] = None
    total_supply: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit les informations du token en dictionnaire."""
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "decimals": self.decimals,
            "blockchain": self.blockchain,
            "network": self.network.value,
            "price_usd": self.price_usd,
            "total_supply": str(self.total_supply) if self.total_supply else None,
            "market_cap": str(self.market_cap) if self.market_cap else None,
            "volume_24h": str(self.volume_24h) if self.volume_24h else None,
            "metadata": self.metadata
        }


# ============================================================================
# EXCEPTIONS
# ============================================================================

class WalletError(Exception):
    """Exception de base pour les erreurs de wallet."""
    pass


class WalletNotFoundError(WalletError):
    """Exception levée quand un wallet n'est pas trouvé."""
    pass


class WalletLockedError(WalletError):
    """Exception levée quand un wallet est verrouillé."""
    pass


class InsufficientBalanceError(WalletError):
    """Exception levée quand le solde est insuffisant."""
    pass


class InvalidAddressError(WalletError):
    """Exception levée quand une adresse est invalide."""
    pass


class TransactionError(WalletError):
    """Exception levée quand une transaction échoue."""
    pass


class NetworkError(WalletError):
    """Exception levée quand il y a une erreur réseau."""
    pass


# ============================================================================
# CLASSE DE BASE
# ============================================================================

class BaseWallet(ABC):
    """
    Classe de base pour tous les wallets multi-blockchain.
    Fournit les fonctionnalités communes et les interfaces standardisées.
    """

    # URLs des APIs blockchain
    API_URLS = {
        "ethereum": {
            "mainnet": "https://api.etherscan.io/api",
            "goerli": "https://api-goerli.etherscan.io/api",
            "sepolia": "https://api-sepolia.etherscan.io/api"
        },
        "bsc": {
            "mainnet": "https://api.bscscan.com/api",
            "testnet": "https://api-testnet.bscscan.com/api"
        },
        "polygon": {
            "mainnet": "https://api.polygonscan.com/api",
            "mumbai": "https://api-mumbai.polygonscan.com/api"
        },
        "solana": {
            "mainnet": "https://api.mainnet-beta.solana.com",
            "devnet": "https://api.devnet.solana.com",
            "testnet": "https://api.testnet.solana.com"
        },
        "avalanche": {
            "mainnet": "https://api.avax.network/ext/bc/C/rpc",
            "fuji": "https://api.avax-test.network/ext/bc/C/rpc"
        }
    }

    # RPC URLs par défaut
    RPC_URLS = {
        "ethereum": {
            "mainnet": "https://eth.llamarpc.com",
            "goerli": "https://goerli.gateway.tenderly.co",
            "sepolia": "https://sepolia.gateway.tenderly.co"
        },
        "bsc": {
            "mainnet": "https://bsc-dataseed.binance.org",
            "testnet": "https://data-seed-prebsc-1-s1.binance.org:8545"
        },
        "polygon": {
            "mainnet": "https://polygon-rpc.com",
            "mumbai": "https://rpc-mumbai.maticvigil.com"
        },
        "avalanche": {
            "mainnet": "https://api.avax.network/ext/bc/C/rpc",
            "fuji": "https://api.avax-test.network/ext/bc/C/rpc"
        },
        "arbitrum": {
            "mainnet": "https://arb1.arbitrum.io/rpc",
            "goerli": "https://goerli-rollup.arbitrum.io/rpc"
        },
        "optimism": {
            "mainnet": "https://mainnet.optimism.io",
            "goerli": "https://goerli.optimism.io"
        }
    }

    def __init__(
        self,
        config: WalletConfig,
        api_keys: Optional[Dict[str, str]] = None,
        web3_provider: Optional[Web3] = None
    ):
        """
        Initialise le wallet de base.

        Args:
            config: Configuration du wallet
            api_keys: Clés API pour les services externes
            web3_provider: Provider Web3 (optionnel)
        """
        self.config = config
        self.api_keys = api_keys or {}
        self.web3 = web3_provider
        self._is_initialized = False
        self._balance_cache: Dict[str, WalletBalance] = {}
        self._transaction_cache: Dict[str, Transaction] = {}
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(f"BaseWallet initialisé pour {config.blockchain} - {config.address[:8]}...")

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialise le wallet et la connexion à la blockchain.

        Returns:
            True si l'initialisation a réussi
        """
        pass

    @abstractmethod
    async def get_balance(
        self,
        token_address: Optional[str] = None,
        force_refresh: bool = False
    ) -> WalletBalance:
        """
        Récupère le solde du wallet.

        Args:
            token_address: Adresse du token (None pour le native)
            force_refresh: Forcer le rafraîchissement

        Returns:
            Solde du wallet
        """
        pass

    @abstractmethod
    async def get_balances(
        self,
        token_addresses: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Dict[str, WalletBalance]:
        """
        Récupère les soldes de plusieurs tokens.

        Args:
            token_addresses: Liste des adresses de tokens
            force_refresh: Forcer le rafraîchissement

        Returns:
            Dictionnaire des soldes par adresse
        """
        pass

    @abstractmethod
    async def send_transaction(
        self,
        to_address: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        data: Optional[str] = None,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Envoie une transaction.

        Args:
            to_address: Adresse du destinataire
            amount: Montant à envoyer
            token_address: Adresse du token (None pour le native)
            data: Données de la transaction
            gas_price: Prix du gaz (optionnel)
            gas_limit: Limite de gaz (optionnel)
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction créée
        """
        pass

    @abstractmethod
    async def send_batch_transactions(
        self,
        transactions: List[Dict[str, Any]]
    ) -> List[Transaction]:
        """
        Envoie un lot de transactions.

        Args:
            transactions: Liste des transactions à envoyer

        Returns:
            Liste des transactions créées
        """
        pass

    @abstractmethod
    async def get_transaction(
        self,
        tx_hash: str
    ) -> Optional[Transaction]:
        """
        Récupère une transaction par son hash.

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Transaction ou None
        """
        pass

    @abstractmethod
    async def get_transactions(
        self,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transaction]:
        """
        Récupère l'historique des transactions.

        Args:
            from_block: Bloc de début
            to_block: Bloc de fin
            limit: Nombre de transactions
            offset: Décalage

        Returns:
            Liste des transactions
        """
        pass

    @abstractmethod
    async def estimate_gas(
        self,
        to_address: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estime les frais de gaz pour une transaction.

        Args:
            to_address: Adresse du destinataire
            amount: Montant
            token_address: Adresse du token
            data: Données de la transaction

        Returns:
            Estimation des frais
        """
        pass

    @abstractmethod
    async def get_gas_price(self) -> Decimal:
        """
        Récupère le prix actuel du gaz.

        Returns:
            Prix du gaz
        """
        pass

    @abstractmethod
    async def get_network_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du réseau.

        Returns:
            Statut du réseau
        """
        pass

    @abstractmethod
    async def is_valid_address(self, address: str) -> bool:
        """
        Vérifie si une adresse est valide.

        Args:
            address: Adresse à vérifier

        Returns:
            True si l'adresse est valide
        """
        pass

    @abstractmethod
    async def get_token_info(
        self,
        token_address: str
    ) -> Optional[TokenInfo]:
        """
        Récupère les informations d'un token.

        Args:
            token_address: Adresse du token

        Returns:
            Informations du token
        """
        pass

    @abstractmethod
    async def get_token_balance(
        self,
        token_address: str,
        address: Optional[str] = None
    ) -> Decimal:
        """
        Récupère le solde d'un token.

        Args:
            token_address: Adresse du token
            address: Adresse du wallet (optionnel)

        Returns:
            Solde du token
        """
        pass

    @abstractmethod
    async def approve_token(
        self,
        token_address: str,
        spender_address: str,
        amount: Decimal,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Approuve un spender pour un token.

        Args:
            token_address: Adresse du token
            spender_address: Adresse du spender
            amount: Montant à approuver
            metadata: Métadonnées supplémentaires

        Returns:
            Transaction d'approbation
        """
        pass

    @abstractmethod
    async def get_allowance(
        self,
        token_address: str,
        owner_address: str,
        spender_address: str
    ) -> Decimal:
        """
        Récupère l'allowance d'un spender.

        Args:
            token_address: Adresse du token
            owner_address: Adresse du propriétaire
            spender_address: Adresse du spender

        Returns:
            Allowance du spender
        """
        pass

    @abstractmethod
    async def sign_message(
        self,
        message: str,
        address: Optional[str] = None
    ) -> str:
        """
        Signe un message.

        Args:
            message: Message à signer
            address: Adresse à utiliser (optionnel)

        Returns:
            Signature du message
        """
        pass

    @abstractmethod
    async def verify_signature(
        self,
        message: str,
        signature: str,
        address: str
    ) -> bool:
        """
        Vérifie une signature.

        Args:
            message: Message signé
            signature: Signature à vérifier
            address: Adresse qui a signé

        Returns:
            True si la signature est valide
        """
        pass

    @abstractmethod
    async def get_transaction_count(
        self,
        address: Optional[str] = None
    ) -> int:
        """
        Récupère le nombre de transactions d'une adresse.

        Args:
            address: Adresse à vérifier (optionnel)

        Returns:
            Nombre de transactions
        """
        pass

    @abstractmethod
    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du wallet et de la connexion.

        Returns:
            État de santé du wallet
        """
        pass

    # ========================================================================
    # MÉTHODES COMMUNES
    # ========================================================================

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Récupère ou crée une session HTTP.

        Returns:
            Session HTTP
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _close_session(self) -> None:
        """Ferme la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_network_name(self, network: BlockchainNetwork) -> str:
        """
        Récupère le nom du réseau.

        Args:
            network: Réseau blockchain

        Returns:
            Nom du réseau
        """
        return network.value.split("_")[-1] if "_" in network.value else network.value

    def _get_network_type(self, network: BlockchainNetwork) -> str:
        """
        Récupère le type du réseau (mainnet, testnet, etc.).

        Args:
            network: Réseau blockchain

        Returns:
            Type du réseau
        """
        parts = network.value.split("_")
        return parts[-1] if len(parts) > 1 else "mainnet"

    def _format_address(self, address: str) -> str:
        """
        Formate une adresse blockchain.

        Args:
            address: Adresse à formater

        Returns:
            Adresse formatée
        """
        if not address:
            return ""
        
        # Ethereum-like address
        if address.startswith("0x"):
            return Web3.to_checksum_address(address)
        
        # Solana-like address
        if len(address) >= 32 and len(address) <= 44:
            return address
        
        return address

    def _is_ethereum_based(self) -> bool:
        """
        Vérifie si le wallet est basé sur Ethereum.

        Returns:
            True si le wallet est basé sur Ethereum
        """
        ethereum_based = [
            "ethereum",
            "bsc",
            "polygon",
            "avalanche",
            "arbitrum",
            "optimism"
        ]
        return self.config.blockchain.lower() in ethereum_based

    def _is_solana_based(self) -> bool:
        """
        Vérifie si le wallet est basé sur Solana.

        Returns:
            True si le wallet est basé sur Solana
        """
        return self.config.blockchain.lower() == "solana"

    def _is_cardano_based(self) -> bool:
        """
        Vérifie si le wallet est basé sur Cardano.

        Returns:
            True si le wallet est basé sur Cardano
        """
        return self.config.blockchain.lower() == "cardano"

    async def _get_rpc_url(self) -> str:
        """
        Récupère l'URL RPC pour la blockchain et le réseau.

        Returns:
            URL RPC
        """
        blockchain = self.config.blockchain.lower()
        network = self._get_network_name(self.config.network)
        
        # Recherche dans les RPC_URLS
        if blockchain in self.RPC_URLS:
            if network in self.RPC_URLS[blockchain]:
                return self.RPC_URLS[blockchain][network]
            # Fallback sur mainnet
            if "mainnet" in self.RPC_URLS[blockchain]:
                return self.RPC_URLS[blockchain]["mainnet"]
        
        # Recherche dans les API_URLS
        if blockchain in self.API_URLS:
            if network in self.API_URLS[blockchain]:
                return self.API_URLS[blockchain][network]
            # Fallback sur mainnet
            if "mainnet" in self.API_URLS[blockchain]:
                return self.API_URLS[blockchain]["mainnet"]
        
        raise ValueError(f"URL RPC non trouvée pour {blockchain}/{network}")

    async def _get_api_url(self) -> str:
        """
        Récupère l'URL API pour la blockchain et le réseau.

        Returns:
            URL API
        """
        blockchain = self.config.blockchain.lower()
        network = self._get_network_name(self.config.network)
        
        if blockchain in self.API_URLS:
            if network in self.API_URLS[blockchain]:
                return self.API_URLS[blockchain][network]
            # Fallback sur mainnet
            if "mainnet" in self.API_URLS[blockchain]:
                return self.API_URLS[blockchain]["mainnet"]
        
        raise ValueError(f"URL API non trouvée pour {blockchain}/{network}")

    async def _get_api_key(self, service: str) -> Optional[str]:
        """
        Récupère une clé API.

        Args:
            service: Nom du service

        Returns:
            Clé API ou None
        """
        return self.api_keys.get(service)

    def _create_transaction_id(self) -> str:
        """
        Crée un ID de transaction.

        Returns:
            ID de transaction
        """
        return str(uuid4())

    def _create_tx_hash(self) -> str:
        """
        Crée un hash de transaction (pour simulation).

        Returns:
            Hash de transaction
        """
        return f"0x{uuid4().hex[:64]}"

    async def _retry_request(
        self,
        func,
        max_retries: int = 3,
        delay: int = 1,
        *args,
        **kwargs
    ):
        """
        Effectue une requête avec retry.

        Args:
            func: Fonction à exécuter
            max_retries: Nombre maximum de tentatives
            delay: Délai entre les tentatives
            *args: Arguments de la fonction
            **kwargs: Arguments nommés de la fonction

        Returns:
            Résultat de la fonction
        """
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Tentative {attempt + 1} échouée: {e}")
                await asyncio.sleep(delay * (attempt + 1))

    async def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Effectue une requête HTTP.

        Args:
            method: Méthode HTTP
            url: URL de la requête
            params: Paramètres de la requête
            data: Données de la requête
            headers: En-têtes HTTP

        Returns:
            Réponse de la requête
        """
        session = await self._get_session()
        
        default_headers = {
            "User-Agent": "NEXUS-AI-TRADING/3.0.0",
            "Accept": "application/json"
        }
        
        if headers:
            default_headers.update(headers)
        
        async with session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            headers=default_headers
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def _get_price(
        self,
        symbol: str,
        currency: str = "usd"
    ) -> float:
        """
        Récupère le prix d'un actif.

        Args:
            symbol: Symbole de l'actif
            currency: Devise de référence

        Returns:
            Prix de l'actif
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={
                        "ids": symbol.lower(),
                        "vs_currencies": currency
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get(symbol.lower(), {}).get(currency, 0))
            return 0.0
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix pour {symbol}: {e}")
            return 0.0

    # ========================================================================
    # MÉTHODES DE NETTOYAGE
    # ========================================================================

    async def close(self) -> None:
        """Ferme proprement le wallet."""
        await self._close_session()
        logger.info(f"Wallet {self.config.wallet_id} fermé")

    async def __aenter__(self):
        """Context manager enter."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    def __del__(self):
        """Destructeur."""
        if hasattr(self, '_session') and self._session:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._close_session())
            except Exception:
                pass


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def generate_mnemonic(strength: int = 256) -> str:
    """
    Génère une phrase mnémonique.

    Args:
        strength: Force de la phrase (128, 160, 192, 224, 256)

    Returns:
        Phrase mnémonique
    """
    return bip39.generate_mnemonic(strength)


def validate_mnemonic(mnemonic: str) -> bool:
    """
    Valide une phrase mnémonique.

    Args:
        mnemonic: Phrase mnémonique à valider

    Returns:
        True si la phrase est valide
    """
    return bip39.check_mnemonic(mnemonic)


def derive_eth_address(private_key: str) -> str:
    """
    Dérive une adresse Ethereum à partir d'une clé privée.

    Args:
        private_key: Clé privée

    Returns:
        Adresse Ethereum
    """
    account = Account.from_key(private_key)
    return account.address


def derive_solana_address(public_key: str) -> str:
    """
    Dérive une adresse Solana à partir d'une clé publique.

    Args:
        public_key: Clé publique

    Returns:
        Adresse Solana
    """
    return base58.b58encode(bytes.fromhex(public_key)).decode()


def is_valid_eth_address(address: str) -> bool:
    """
    Vérifie si une adresse Ethereum est valide.

    Args:
        address: Adresse à vérifier

    Returns:
        True si l'adresse est valide
    """
    return Web3.is_address(address) and Web3.is_checksum_address(address)


def is_valid_solana_address(address: str) -> bool:
    """
    Vérifie si une adresse Solana est valide.

    Args:
        address: Adresse à vérifier

    Returns:
        True si l'adresse est valide
    """
    if len(address) != 44:
        return False
    try:
        base58.b58decode(address)
        return True
    except Exception:
        return False


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "WalletType",
    "WalletStatus",
    "BlockchainNetwork",
    "TransactionType",
    "TransactionStatus",
    
    # Dataclasses
    "WalletConfig",
    "WalletBalance",
    "Transaction",
    "TokenInfo",
    
    # Exceptions
    "WalletError",
    "WalletNotFoundError",
    "WalletLockedError",
    "InsufficientBalanceError",
    "InvalidAddressError",
    "TransactionError",
    "NetworkError",
    
    # Classe de base
    "BaseWallet",
    
    # Fonctions utilitaires
    "generate_mnemonic",
    "validate_mnemonic",
    "derive_eth_address",
    "derive_solana_address",
    "is_valid_eth_address",
    "is_valid_solana_address"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de la classe BaseWallet."""
    print("=" * 60)
    print("NEXUS AI TRADING - BASE WALLET MODULE")
    print("=" * 60)
    
    # Création d'une configuration de wallet
    config = WalletConfig(
        wallet_id=uuid4(),
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        name="Main Wallet",
        type=WalletType.HD,
        blockchain="ethereum",
        network=BlockchainNetwork.ETHEREUM_MAINNET,
        address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        is_created=True,
        is_imported=False,
        is_hardware=False,
        metadata={"source": "nexus_platform"}
    )
    
    print(f"\n✅ Configuration du wallet:")
    print(f"   ID: {config.wallet_id}")
    print(f"   Nom: {config.name}")
    print(f"   Blockchain: {config.blockchain}")
    print(f"   Réseau: {config.network.value}")
    print(f"   Adresse: {config.address[:8]}...{config.address[-8:]}")
    
    # Test des fonctions utilitaires
    print("\n📋 Test des fonctions utilitaires:")
    
    # Génération d'une phrase mnémonique
    mnemonic = generate_mnemonic()
    print(f"   ✅ Phrase mnémonique générée: {mnemonic[:30]}...")
    print(f"   ✅ Validation de la phrase: {validate_mnemonic(mnemonic)}")
    
    # Test d'adresse Ethereum
    eth_address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    print(f"   ✅ Adresse Ethereum valide: {is_valid_eth_address(eth_address)}")
    
    print("\n" + "=" * 60)
    print("BaseWallet module NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

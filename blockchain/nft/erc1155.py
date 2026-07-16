# blockchain/nft/erc1155.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module ERC-1155 - Gestion des Tokens Multi-standards

Ce module implémente une intégration complète du standard ERC-1155,
permettant la gestion des tokens semi-fongibles, des collections,
des transferts en batch, et des opérations avancées.

Fonctionnalités principales:
- Support complet du standard ERC-1155
- Transferts simples et en batch
- Gestion des balances
- Approbations et opérateurs
- Gestion des métadonnées
- Support des URI
- Gestion des collections
- Support des mint et burn
- Monitoring des tokens
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

class ERC1155Action(Enum):
    """Actions ERC-1155"""
    TRANSFER = "transfer"
    TRANSFER_BATCH = "transfer_batch"
    APPROVE = "approve"
    SET_APPROVAL = "set_approval"
    MINT = "mint"
    MINT_BATCH = "mint_batch"
    BURN = "burn"
    BURN_BATCH = "burn_batch"


@dataclass
class ERC1155Token:
    """Token ERC-1155"""
    contract_address: str
    token_id: str
    balance: int
    metadata: NFTMetadata
    chain: str
    created_at: datetime
    updated_at: datetime
    metadata_uri: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "balance": self.balance,
            "metadata": self.metadata.to_dict(),
            "chain": self.chain,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata_uri": self.metadata_uri,
        }


@dataclass
class ERC1155BatchTransfer:
    """Transfert batch ERC-1155"""
    from_address: str
    to_address: str
    token_ids: List[str]
    amounts: List[int]
    timestamp: datetime
    tx_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "from": self.from_address,
            "to": self.to_address,
            "token_ids": self.token_ids,
            "amounts": self.amounts,
            "timestamp": self.timestamp.isoformat(),
            "tx_hash": self.tx_hash,
        }


# ============================================================
# ADRESSES ET CONFIGURATION
# ============================================================

# Exemples de contrats ERC-1155 populaires
KNOWN_ERC1155_CONTRACTS = {
    "ethereum": {
        "enjin": "0xFaafDC07907ff5120a76b34b731b278c9d6046cA",
        "sandbox": "0xF5b0A3E7fC225F740CF2B8bBEB8B4bE8bB1B3B2B",
        "decentraland": "0x3166E6bC21B0A2CbA3E8Dc9aBd3D0e3E9B3E3B3E",
    },
    "polygon": {
        "enjin": "0x...",
    },
}


# ============================================================
# ABI ERC-1155
# ============================================================

ERC1155_ABI = [
    # Balance functions
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
        "constant": True,
        "inputs": [
            {"name": "accounts", "type": "address[]"},
            {"name": "ids", "type": "uint256[]"},
        ],
        "name": "balanceOfBatch",
        "outputs": [{"name": "", "type": "uint256[]"}],
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
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "ids", "type": "uint256[]"},
            {"name": "amounts", "type": "uint256[]"},
            {"name": "data", "type": "bytes"},
        ],
        "name": "safeBatchTransferFrom",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    
    # Approval functions
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
    
    # URI functions
    {
        "constant": True,
        "inputs": [{"name": "id", "type": "uint256"}],
        "name": "uri",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    
    # Mint/Burn functions (optional, may not be present on all contracts)
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "id", "type": "uint256"},
            {"name": "amount", "type": "uint256"},
            {"name": "data", "type": "bytes"},
        ],
        "name": "mint",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "ids", "type": "uint256[]"},
            {"name": "amounts", "type": "uint256[]"},
            {"name": "data", "type": "bytes"},
        ],
        "name": "mintBatch",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "id", "type": "uint256"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "burn",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "ids", "type": "uint256[]"},
            {"name": "amounts", "type": "uint256[]"},
        ],
        "name": "burnBatch",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "ids", "type": "uint256[]"},
            {"indexed": False, "name": "values", "type": "uint256[]"},
        ],
        "name": "TransferBatch",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "id", "type": "uint256"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "TransferSingle",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "account", "type": "address"},
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": False, "name": "approved", "type": "bool"},
        ],
        "name": "ApprovalForAll",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "value", "type": "uint256"},
            {"indexed": True, "name": "id", "type": "uint256"},
            {"indexed": False, "name": "data", "type": "string"},
        ],
        "name": "URI",
        "type": "event",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class ERC1155Manager(BaseNFT):
    """
    Gestionnaire avancé pour les tokens ERC-1155
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
        Initialise le gestionnaire ERC-1155

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
        self._tokens_cache: Dict[str, Tuple[float, ERC1155Token]] = {}
        self._balances_cache: Dict[str, Tuple[float, Dict[str, int]]] = {}
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
        self._total_transfers = 0
        self._total_batch_transfers = 0
        self._total_mints = 0
        self._total_burns = 0

        # Initialisation des contrats
        self._load_contracts()

        logger.info("ERC1155Manager initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats ERC-1155"""
        try:
            self._contracts = {}

            for chain, chain_config in KNOWN_ERC1155_CONTRACTS.items():
                if chain not in self.web3_providers:
                    continue

                provider = self.web3_providers[chain]
                self._contracts[chain] = {}

                for name, address in chain_config.items():
                    self._contracts[chain][name] = provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=ERC1155_ABI,
                    )

            logger.info(f"Contrats ERC-1155 chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise NFTError(f"Erreur de chargement des contrats: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - BALANCES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_balance(
        self,
        contract_address: str,
        token_id: str,
        wallet_address: str,
        chain: str = "ethereum",
    ) -> int:
        """
        Obtient la balance d'un token pour une adresse

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            wallet_address: Adresse du wallet
            chain: Chaîne

        Returns:
            Balance du token
        """
        try:
            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            balance = await self._async_call(
                contract.functions.balanceOf(
                    to_checksum_address(wallet_address),
                    int(token_id),
                )
            )

            return balance

        except Exception as e:
            logger.error(f"Erreur de récupération de la balance: {e}")
            raise NFTError(f"Erreur de récupération de la balance: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_balances_batch(
        self,
        contract_address: str,
        accounts: List[str],
        token_ids: List[str],
        chain: str = "ethereum",
    ) -> List[int]:
        """
        Obtient les balances en batch

        Args:
            contract_address: Adresse du contrat
            accounts: Liste des adresses
            token_ids: Liste des IDs de tokens
            chain: Chaîne

        Returns:
            Liste des balances
        """
        if len(accounts) != len(token_ids):
            raise ValidationError("Les listes accounts et token_ids doivent avoir la même longueur")

        try:
            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            accounts_checksum = [to_checksum_address(a) for a in accounts]
            token_ids_int = [int(t) for t in token_ids]

            balances = await self._async_call(
                contract.functions.balanceOfBatch(
                    accounts_checksum,
                    token_ids_int,
                )
            )

            return balances

        except Exception as e:
            logger.error(f"Erreur de récupération des balances batch: {e}")
            raise NFTError(f"Erreur de récupération des balances batch: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - TRANSFERTS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def transfer_token(
        self,
        contract_address: str,
        token_id: str,
        amount: int,
        from_address: str,
        to_address: str,
        chain: str = "ethereum",
        data: bytes = b"",
    ) -> str:
        """
        Transfère un token ERC-1155

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            amount: Quantité à transférer
            from_address: Adresse source
            to_address: Adresse destination
            chain: Chaîne
            data: Données additionnelles

        Returns:
            Hash de la transaction
        """
        logger.info(f"Transfert de {amount} de {token_id} de {from_address} vers {to_address}")

        try:
            wallet = await self.wallet_manager.get_wallet(from_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {from_address}")

            # Vérification du solde
            balance = await self.get_balance(contract_address, token_id, from_address, chain)
            if balance < amount:
                raise NFTError(f"Solde insuffisant: {balance} < {amount}")

            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            tx = contract.functions.safeTransferFrom(
                to_checksum_address(from_address),
                to_checksum_address(to_address),
                int(token_id),
                amount,
                data,
            ).build_transaction({
                "from": to_checksum_address(from_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_transfers += 1
            self.metrics.record_increment(
                "erc1155_transfer",
                1,
                {"contract": contract_address, "chain": chain},
            )

            logger.info(f"Transfert réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de transfert: {e}")
            raise NFTError(f"Erreur de transfert: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def transfer_batch(
        self,
        contract_address: str,
        token_ids: List[str],
        amounts: List[int],
        from_address: str,
        to_address: str,
        chain: str = "ethereum",
        data: bytes = b"",
    ) -> str:
        """
        Transfère plusieurs tokens en batch

        Args:
            contract_address: Adresse du contrat
            token_ids: Liste des IDs de tokens
            amounts: Liste des quantités
            from_address: Adresse source
            to_address: Adresse destination
            chain: Chaîne
            data: Données additionnelles

        Returns:
            Hash de la transaction
        """
        if len(token_ids) != len(amounts):
            raise ValidationError("Les listes token_ids et amounts doivent avoir la même longueur")

        logger.info(f"Transfert batch de {len(token_ids)} tokens de {from_address} vers {to_address}")

        try:
            wallet = await self.wallet_manager.get_wallet(from_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {from_address}")

            # Vérification des soldes
            for token_id, amount in zip(token_ids, amounts):
                balance = await self.get_balance(contract_address, token_id, from_address, chain)
                if balance < amount:
                    raise NFTError(f"Solde insuffisant pour {token_id}: {balance} < {amount}")

            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            token_ids_int = [int(t) for t in token_ids]

            tx = contract.functions.safeBatchTransferFrom(
                to_checksum_address(from_address),
                to_checksum_address(to_address),
                token_ids_int,
                amounts,
                data,
            ).build_transaction({
                "from": to_checksum_address(from_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_batch_transfers += 1
            self.metrics.record_increment(
                "erc1155_batch_transfer",
                1,
                {"contract": contract_address, "chain": chain},
            )

            logger.info(f"Transfert batch réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de transfert batch: {e}")
            raise NFTError(f"Erreur de transfert batch: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - APPROVATIONS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def set_approval_for_all(
        self,
        contract_address: str,
        operator: str,
        approved: bool,
        wallet_address: str,
        chain: str = "ethereum",
    ) -> str:
        """
        Définit l'approbation pour tous les tokens

        Args:
            contract_address: Adresse du contrat
            operator: Adresse de l'opérateur
            approved: True pour approuver, False pour révoquer
            wallet_address: Adresse du wallet
            chain: Chaîne

        Returns:
            Hash de la transaction
        """
        logger.info(f"Set approval for all: {operator} {'apprové' if approved else 'révoqué'}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

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

            logger.info(f"Set approval réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de set approval: {e}")
            raise NFTError(f"Erreur de set approval: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def is_approved_for_all(
        self,
        contract_address: str,
        owner: str,
        operator: str,
        chain: str = "ethereum",
    ) -> bool:
        """
        Vérifie si un opérateur est approuvé

        Args:
            contract_address: Adresse du contrat
            owner: Propriétaire
            operator: Opérateur
            chain: Chaîne

        Returns:
            True si approuvé
        """
        try:
            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            approved = await self._async_call(
                contract.functions.isApprovedForAll(
                    to_checksum_address(owner),
                    to_checksum_address(operator),
                )
            )

            return approved

        except Exception as e:
            logger.error(f"Erreur de vérification d'approval: {e}")
            raise NFTError(f"Erreur de vérification d'approval: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - MINT & BURN
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def mint(
        self,
        contract_address: str,
        token_id: str,
        amount: int,
        to_address: str,
        wallet_address: str,
        chain: str = "ethereum",
        data: bytes = b"",
    ) -> str:
        """
        Mint un token ERC-1155

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            amount: Quantité à minter
            to_address: Adresse de destination
            wallet_address: Adresse du wallet
            chain: Chaîne
            data: Données additionnelles

        Returns:
            Hash de la transaction
        """
        logger.info(f"Mint de {amount} de {token_id} vers {to_address}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            # Vérification que le contrat supporte le mint
            if not hasattr(contract.functions, "mint"):
                raise NFTError("Le contrat ne supporte pas le mint")

            tx = contract.functions.mint(
                to_checksum_address(to_address),
                int(token_id),
                amount,
                data,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_mints += 1
            self.metrics.record_increment(
                "erc1155_mint",
                1,
                {"contract": contract_address, "chain": chain},
            )

            logger.info(f"Mint réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de mint: {e}")
            raise NFTError(f"Erreur de mint: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def burn(
        self,
        contract_address: str,
        token_id: str,
        amount: int,
        from_address: str,
        wallet_address: str,
        chain: str = "ethereum",
    ) -> str:
        """
        Burn un token ERC-1155

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            amount: Quantité à brûler
            from_address: Adresse source
            wallet_address: Adresse du wallet
            chain: Chaîne

        Returns:
            Hash de la transaction
        """
        logger.info(f"Burn de {amount} de {token_id} de {from_address}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du solde
            balance = await self.get_balance(contract_address, token_id, from_address, chain)
            if balance < amount:
                raise NFTError(f"Solde insuffisant: {balance} < {amount}")

            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            # Vérification que le contrat supporte le burn
            if not hasattr(contract.functions, "burn"):
                raise NFTError("Le contrat ne supporte pas le burn")

            tx = contract.functions.burn(
                to_checksum_address(from_address),
                int(token_id),
                amount,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_burns += 1
            self.metrics.record_increment(
                "erc1155_burn",
                1,
                {"contract": contract_address, "chain": chain},
            )

            logger.info(f"Burn réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de burn: {e}")
            raise NFTError(f"Erreur de burn: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - MÉTADONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_token_metadata(
        self,
        contract_address: str,
        token_id: str,
        chain: str = "ethereum",
    ) -> NFTMetadata:
        """
        Récupère les métadonnées d'un token

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            chain: Chaîne

        Returns:
            Métadonnées du token
        """
        try:
            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            # Récupération de l'URI
            token_uri = await self._async_call(
                contract.functions.uri(int(token_id))
            )

            if token_uri:
                metadata_data = await self._fetch_metadata(token_uri)
                return self._parse_metadata(metadata_data)

            return NFTMetadata(
                name=f"ERC-1155 Token #{token_id}",
                description="",
                image="",
            )

        except Exception as e:
            logger.warning(f"Erreur de récupération des métadonnées: {e}")
            return NFTMetadata(
                name=f"ERC-1155 Token #{token_id}",
                description="",
                image="",
            )

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_balances(
        self,
        contract_address: str,
        addresses: List[str],
        token_ids: List[str],
        chain: str = "ethereum",
        interval: int = 300,
    ) -> None:
        """
        Surveille les balances en continu

        Args:
            contract_address: Adresse du contrat
            addresses: Liste des adresses à surveiller
            token_ids: Liste des IDs de tokens
            chain: Chaîne
            interval: Intervalle en secondes
        """
        logger.info(f"Démarrage du monitoring des balances ERC-1155")

        while True:
            try:
                # Récupération des balances en batch
                all_balances = {}
                for address in addresses:
                    for token_id in token_ids:
                        balance = await self.get_balance(
                            contract_address, token_id, address, chain
                        )
                        key = f"{address}:{token_id}"
                        all_balances[key] = balance

                        # Alertes
                        if balance == 0:
                            await self._send_alert({
                                "type": "zero_balance",
                                "contract": contract_address,
                                "address": address,
                                "token_id": token_id,
                                "severity": "info",
                            })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_contract(self, contract_address: str, chain: str) -> Optional[Contract]:
        """Obtient un contrat ERC-1155"""
        # Recherche dans les contrats connus
        if chain in self._contracts:
            for name, contract in self._contracts[chain].items():
                if contract.address.lower() == contract_address.lower():
                    return contract

        # Création d'un nouveau contrat
        provider = self.web3_providers.get(chain)
        if not provider:
            return None

        return provider.eth.contract(
            address=to_checksum_address(contract_address),
            abi=ERC1155_ABI,
        )

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
    # MÉTHODES DE BASE
    # ============================================================

    async def get_nft(
        self,
        contract_address: str,
        token_id: str,
        **kwargs,
    ) -> NFTData:
        """Obtient les données d'un NFT ERC-1155"""
        chain = kwargs.get("chain", "ethereum")
        owner = kwargs.get("owner")

        if not owner:
            owner = await self.get_owner(contract_address, token_id, chain=chain)

        metadata = await self.get_token_metadata(contract_address, token_id, chain)

        return NFTData(
            token_id=token_id,
            contract_address=contract_address,
            chain=chain,
            standard=NFTStandard.ERC1155,
            owner=owner,
            status=NFTStatus.AVAILABLE,
            metadata=metadata,
            metadata_uri=await self._get_token_uri(contract_address, token_id, chain),
        )

    async def get_collection(
        self,
        contract_address: str,
        **kwargs,
    ) -> NFTCollection:
        """Obtient les données d'une collection ERC-1155"""
        chain = kwargs.get("chain", "ethereum")

        # Récupération des informations de base
        try:
            contract = self._get_contract(contract_address, chain)
            if not contract:
                raise NFTError(f"Contrat {contract_address} non trouvé sur {chain}")

            name = await self._async_call(contract.functions.name())
            symbol = await self._async_call(contract.functions.symbol())

            return NFTCollection(
                collection_id=f"col_{uuid.uuid4().hex[:8]}",
                name=name,
                symbol=symbol,
                contract_address=contract_address,
                chain=chain,
                standard=NFTStandard.ERC1155,
                total_supply=0,  # Non disponible directement
                floor_price=Decimal("0"),
                volume_24h=Decimal("0"),
                volume_total=Decimal("0"),
                items_count=0,
                owners_count=0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        except Exception as e:
            logger.warning(f"Erreur de récupération de la collection: {e}")
            return NFTCollection(
                collection_id=f"col_{uuid.uuid4().hex[:8]}",
                name=f"Collection {contract_address[:8]}",
                symbol="UNKNOWN",
                contract_address=contract_address,
                chain=chain,
                standard=NFTStandard.ERC1155,
                total_supply=0,
                floor_price=Decimal("0"),
                volume_24h=Decimal("0"),
                volume_total=Decimal("0"),
                items_count=0,
                owners_count=0,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    async def get_owner(
        self,
        contract_address: str,
        token_id: str,
        **kwargs,
    ) -> str:
        """Obtient le propriétaire d'un token ERC-1155"""
        # Pour ERC-1155, il n'y a pas de propriétaire unique
        # On retourne l'adresse du contrat
        return contract_address

    async def transfer_nft(
        self,
        contract_address: str,
        token_id: str,
        from_address: str,
        to_address: str,
        **kwargs,
    ) -> str:
        """Transfère un NFT ERC-1155"""
        amount = kwargs.get("amount", 1)
        chain = kwargs.get("chain", "ethereum")
        data = kwargs.get("data", b"")

        return await self.transfer_token(
            contract_address=contract_address,
            token_id=token_id,
            amount=amount,
            from_address=from_address,
            to_address=to_address,
            chain=chain,
            data=data,
        )

    async def approve(
        self,
        contract_address: str,
        token_id: str,
        operator: str,
        owner_address: str,
        **kwargs,
    ) -> str:
        """Approuve un opérateur pour un token ERC-1155"""
        chain = kwargs.get("chain", "ethereum")
        approved = kwargs.get("approved", True)

        # Pour ERC-1155, l'approbation est pour tous les tokens
        return await self.set_approval_for_all(
            contract_address=contract_address,
            operator=operator,
            approved=approved,
            wallet_address=owner_address,
            chain=chain,
        )

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "total_transfers": self._total_transfers,
            "total_batch_transfers": self._total_batch_transfers,
            "total_mints": self._total_mints,
            "total_burns": self._total_burns,
            "tokens_cached": len(self._tokens_cache),
            "balances_cached": len(self._balances_cache),
            "chains_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources ERC1155Manager...")

        self._tokens_cache.clear()
        self._balances_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")

    # ============================================================
    # MÉTHODES PRIVÉES
    # ============================================================

    async def _get_token_uri(
        self,
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> Optional[str]:
        """Récupère l'URI d'un token"""
        try:
            contract = self._get_contract(contract_address, chain)
            if not contract:
                return None

            return await self._async_call(
                contract.functions.uri(int(token_id))
            )

        except Exception:
            return None


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_erc1155_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> ERC1155Manager:
    """
    Crée une instance de ERC1155Manager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de ERC1155Manager
    """
    return ERC1155Manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de ERC1155Manager"""
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
    erc1155 = create_erc1155_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Récupération d'une balance
    balance = await erc1155.get_balance(
        contract_address="0xFaafDC07907ff5120a76b34b731b278c9d6046cA",
        token_id="1",
        wallet_address="0x1234567890123456789012345678901234567890",
    )
    print(f"Balance: {balance}")

    # Obtention d'un token
    nft = await erc1155.get_nft(
        contract_address="0xFaafDC07907ff5120a76b34b731b278c9d6046cA",
        token_id="1",
        owner="0x1234567890123456789012345678901234567890",
    )
    print(f"NFT: {nft.to_dict()}")

    # Statistiques
    stats = erc1155.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await erc1155.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

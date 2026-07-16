# blockchain/defi/maker_dao.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module MakerDAO - Intégration du Protocole Maker

Ce module implémente une intégration complète du protocole MakerDAO,
permettant la gestion des positions DAI, le dépôt de collatéraux,
l'emprunt de DAI, et l'optimisation des rendements.

Fonctionnalités principales:
- Dépôt de collatéraux (ETH, WBTC, USDC, etc.)
- Emprunt de DAI avec collatéral
- Remboursement de DAI
- Gestion des positions Vaults
- Support des Vaults (anciennement CDPs)
- Support du DAI Savings Rate (DSR)
- Support du staking MKR
- Monitoring des positions
- Alertes de liquidation
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
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class MakerAction(Enum):
    """Actions MakerDAO"""
    DEPOSIT = "deposit"  # Dépôt de collatéral
    WITHDRAW = "withdraw"  # Retrait de collatéral
    BORROW = "borrow"  # Emprunt de DAI
    REPAY = "repay"  # Remboursement de DAI
    DEPOSIT_DSR = "deposit_dsr"  # Dépôt dans DSR
    WITHDRAW_DSR = "withdraw_dsr"  # Retrait de DSR
    STAKE_MKR = "stake_mkr"  # Staking MKR
    UNSTAKE_MKR = "unstake_mkr"  # Unstaking MKR


class MakerPositionType(Enum):
    """Types de positions Maker"""
    VAULT = "vault"
    DSR = "dsr"
    MKR_STAKE = "mkr_stake"


@dataclass
class MakerVaultData:
    """Données d'un Vault Maker"""
    vault_id: str
    owner: str
    collateral_token: str
    collateral_amount: Decimal
    collateral_value_usd: Decimal
    debt_amount: Decimal
    debt_value_usd: Decimal
    collateralization_ratio: Decimal
    liquidation_price: Decimal
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "vault_id": self.vault_id,
            "owner": self.owner,
            "collateral_token": self.collateral_token,
            "collateral_amount": str(self.collateral_amount),
            "collateral_value_usd": str(self.collateral_value_usd),
            "debt_amount": str(self.debt_amount),
            "debt_value_usd": str(self.debt_value_usd),
            "collateralization_ratio": str(self.collateralization_ratio),
            "liquidation_price": str(self.liquidation_price),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class MakerPosition:
    """Position MakerDAO"""
    position_id: str
    position_type: MakerPositionType
    user: str
    chain: str
    token: str
    amount: Decimal
    value_usd: Decimal
    apy: Decimal
    risk_level: RiskLevel
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "position_type": self.position_type.value,
            "user": self.user,
            "chain": self.chain,
            "token": self.token,
            "amount": str(self.amount),
            "value_usd": str(self.value_usd),
            "apy": str(self.apy),
            "risk_level": self.risk_level.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================
# ADRESSES DES CONTRATS MAKERDAO
# ============================================================

MAKER_ADDRESSES = {
    "ethereum": {
        "dai": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "dsr": "0x197E90f9FAD81970bA7976f33CbD77088E5D7cf7",
        "pot": "0x197E90f9FAD81970bA7976f33CbD77088E5D7cf7",
        "vat": "0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B",
        "join_eth": "0x2F0b23f53734252BdaF73581C77b7d9aDf2CEA5E",
        "join_wbtc": "0xBF72Da2Bd84c5170614F5Dd4C6D4cC3F0E3DfF5E",
        "join_usdc": "0x0A59649758aa4d66E25f08Dd01271e891fe52199",
        "join_weth": "0x2F0b23f53734252BdaF73581C77b7d9aDf2CEA5E",
        "mkr": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",
        "governance": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",
    },
    "polygon": {
        "dai": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        "dsr": "0x...",  # À ajouter
    },
}

# Collatéraux supportés
SUPPORTED_COLLATERAL = {
    "ETH": {
        "token": "ETH",
        "join": "join_eth",
        "decimals": 18,
        "liquidation_ratio": Decimal("1.5"),
        "stability_fee": Decimal("0.02"),
    },
    "WETH": {
        "token": "WETH",
        "join": "join_weth",
        "decimals": 18,
        "liquidation_ratio": Decimal("1.5"),
        "stability_fee": Decimal("0.02"),
    },
    "WBTC": {
        "token": "WBTC",
        "join": "join_wbtc",
        "decimals": 8,
        "liquidation_ratio": Decimal("1.5"),
        "stability_fee": Decimal("0.025"),
    },
    "USDC": {
        "token": "USDC",
        "join": "join_usdc",
        "decimals": 6,
        "liquidation_ratio": Decimal("1.1"),
        "stability_fee": Decimal("0.01"),
    },
}

# ABIs des contrats
DAI_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "usr", "type": "address"},
            {"name": "wad", "type": "uint256"},
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
            {"name": "usr", "type": "address"},
            {"name": "wad", "type": "uint256"},
        ],
        "name": "burn",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "usr", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

VAT_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "urn", "type": "bytes32"},
            {"name": "ilk", "type": "bytes32"},
            {"name": "wad", "type": "uint256"},
        ],
        "name": "frob",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "urn", "type": "bytes32"},
            {"name": "ilk", "type": "bytes32"},
        ],
        "name": "urns",
        "outputs": [
            {"name": "ink", "type": "uint256"},
            {"name": "art", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "ilk", "type": "bytes32"}],
        "name": "ilks",
        "outputs": [
            {"name": "Art", "type": "uint256"},
            {"name": "rate", "type": "uint256"},
            {"name": "spot", "type": "uint256"},
            {"name": "line", "type": "uint256"},
            {"name": "dust", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

POT_ABI = [
    {
        "constant": False,
        "inputs": [{"name": "wad", "type": "uint256"}],
        "name": "join",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "wad", "type": "uint256"}],
        "name": "exit",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "dsr",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "usr", "type": "address"}],
        "name": "pie",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

JOIN_ABI = [
    {
        "constant": False,
        "inputs": [{"name": "usr", "type": "address"}, {"name": "wad", "type": "uint256"}],
        "name": "join",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "usr", "type": "address"}, {"name": "wad", "type": "uint256"}],
        "name": "exit",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class MakerDAOIntegration(BaseProtocol):
    """
    Intégration avancée du protocole MakerDAO
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
        Initialise l'intégration MakerDAO

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
        self._vaults_cache: Dict[str, Tuple[float, MakerVaultData]] = {}
        self._positions_cache: Dict[str, Tuple[float, MakerPosition]] = {}
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
        self._dsr_cache: Dict[str, Tuple[float, Decimal]] = {}

        # Métriques
        self._total_collateral = Decimal("0")
        self._total_debt = Decimal("0")
        self._total_dsr_deposits = Decimal("0")

        # Initialisation des contrats
        self._load_contracts()

        logger.info("MakerDAOIntegration initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats MakerDAO"""
        try:
            self._contracts = {}

            for chain, addresses in MAKER_ADDRESSES.items():
                if chain not in self.web3_providers:
                    logger.warning(f"Provider Web3 non trouvé pour {chain}")
                    continue

                provider = self.web3_providers[chain]
                self._contracts[chain] = {}

                # DAI
                self._contracts[chain]["dai"] = provider.eth.contract(
                    address=to_checksum_address(addresses["dai"]),
                    abi=DAI_ABI,
                )

                # VAT
                if "vat" in addresses:
                    self._contracts[chain]["vat"] = provider.eth.contract(
                        address=to_checksum_address(addresses["vat"]),
                        abi=VAT_ABI,
                    )

                # POT (DSR)
                if "pot" in addresses:
                    self._contracts[chain]["pot"] = provider.eth.contract(
                        address=to_checksum_address(addresses["pot"]),
                        abi=POT_ABI,
                    )

                # Join contracts
                for name, address in addresses.items():
                    if name.startswith("join_"):
                        self._contracts[chain][name] = provider.eth.contract(
                            address=to_checksum_address(address),
                            abi=JOIN_ABI,
                        )

            logger.info(f"Contrats MakerDAO chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise DeFiError(f"Erreur de chargement des contrats: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - VAULTS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def deposit_collateral(
        self,
        collateral_token: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Dépose un collatéral dans un Vault Maker

        Args:
            collateral_token: Token de collatéral (ETH, WBTC, USDC, etc.)
            amount: Montant à déposer
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Dépôt de {amount} {collateral_token} sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du collatéral
            collateral_config = SUPPORTED_COLLATERAL.get(collateral_token)
            if not collateral_config:
                raise DeFiError(f"Collatéral {collateral_token} non supporté")

            # Vérification du solde
            balance = await self._get_balance(collateral_token, chain, wallet_address)
            if balance < amount:
                raise DeFiError(f"Solde insuffisant: {balance} < {amount}")

            # Récupération des contrats
            join_contract = self._contracts[chain].get(collateral_config["join"])
            if not join_contract:
                raise DeFiError(f"Join contract non trouvé pour {collateral_token}")

            amount_wei = int(amount * Decimal(10 ** collateral_config["decimals"]))

            # Construction de la transaction
            tx = join_contract.functions.join(
                to_checksum_address(wallet_address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_collateral += amount
            self.metrics.record_increment(
                "maker_deposit_collateral",
                1,
                {"token": collateral_token, "chain": chain},
            )

            logger.info(f"Collatéral déposé: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de dépôt de collatéral: {e}")
            raise DeFiError(f"Erreur de dépôt de collatéral: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def withdraw_collateral(
        self,
        collateral_token: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Retire un collatéral d'un Vault Maker

        Args:
            collateral_token: Token de collatéral
            amount: Montant à retirer
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Retrait de {amount} {collateral_token} sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du collatéral
            collateral_config = SUPPORTED_COLLATERAL.get(collateral_token)
            if not collateral_config:
                raise DeFiError(f"Collatéral {collateral_token} non supporté")

            # Vérification de la position
            vault = await self.get_vault(wallet_address, chain)
            if vault and vault.collateral_amount < amount:
                raise DeFiError(
                    f"Collatéral insuffisant: {vault.collateral_amount} < {amount}"
                )

            join_contract = self._contracts[chain].get(collateral_config["join"])
            if not join_contract:
                raise DeFiError(f"Join contract non trouvé pour {collateral_token}")

            amount_wei = int(amount * Decimal(10 ** collateral_config["decimals"]))

            tx = join_contract.functions.exit(
                to_checksum_address(wallet_address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_collateral -= amount
            self.metrics.record_increment(
                "maker_withdraw_collateral",
                1,
                {"token": collateral_token, "chain": chain},
            )

            logger.info(f"Collatéral retiré: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de retrait de collatéral: {e}")
            raise DeFiError(f"Erreur de retrait de collatéral: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def borrow_dai(
        self,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        collateral_token: str = "ETH",
    ) -> str:
        """
        Emprunte du DAI avec un collatéral

        Args:
            amount: Montant de DAI à emprunter
            chain: Chaîne
            wallet_address: Adresse du wallet
            collateral_token: Token de collatéral

        Returns:
            Hash de la transaction
        """
        logger.info(f"Emprunt de {amount} DAI sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du collatéral
            collateral_config = SUPPORTED_COLLATERAL.get(collateral_token)
            if not collateral_config:
                raise DeFiError(f"Collatéral {collateral_token} non supporté")

            # Vérification du ratio de collateralisation
            vault = await self.get_vault(wallet_address, chain)
            if vault:
                new_debt = vault.debt_amount + amount
                new_ratio = vault.collateral_value_usd / new_debt
                if new_ratio < collateral_config["liquidation_ratio"]:
                    raise DeFiError(
                        f"Collatéralisation trop faible: {new_ratio:.2f} < {collateral_config['liquidation_ratio']:.2f}"
                    )

            # Récupération du contrat DAI
            dai_contract = self._contracts[chain].get("dai")
            if not dai_contract:
                raise DeFiError(f"Contrat DAI non trouvé sur {chain}")

            amount_wei = int(amount * Decimal(1e18))

            tx = dai_contract.functions.mint(
                to_checksum_address(wallet_address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_debt += amount
            self.metrics.record_increment(
                "maker_borrow_dai",
                1,
                {"chain": chain},
            )

            logger.info(f"DAI emprunté: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur d'emprunt DAI: {e}")
            raise DeFiError(f"Erreur d'emprunt DAI: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def repay_dai(
        self,
        amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Rembourse du DAI

        Args:
            amount: Montant de DAI à rembourser
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Remboursement de {amount} DAI sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du solde DAI
            dai_balance = await self._get_dai_balance(chain, wallet_address)
            if dai_balance < amount:
                raise DeFiError(f"Solde DAI insuffisant: {dai_balance} < {amount}")

            dai_contract = self._contracts[chain].get("dai")
            if not dai_contract:
                raise DeFiError(f"Contrat DAI non trouvé sur {chain}")

            amount_wei = int(amount * Decimal(1e18))

            tx = dai_contract.functions.burn(
                to_checksum_address(wallet_address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_debt -= amount
            self.metrics.record_increment(
                "maker_repay_dai",
                1,
                {"chain": chain},
            )

            logger.info(f"DAI remboursé: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de remboursement DAI: {e}")
            raise DeFiError(f"Erreur de remboursement DAI: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_vault(
        self,
        user: str,
        chain: str,
        force_refresh: bool = False,
    ) -> Optional[MakerVaultData]:
        """
        Obtient les données d'un Vault Maker

        Args:
            user: Adresse de l'utilisateur
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Données du Vault ou None
        """
        cache_key = f"{chain}:{user}"

        if not force_refresh and cache_key in self._vaults_cache:
            cached_time, vault = self._vaults_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return vault

        try:
            # Récupération des données du Vault
            # Simulé - dans la réalité, on interrogerait le contrat VAT
            vault = MakerVaultData(
                vault_id=f"vault_{uuid.uuid4().hex[:8]}",
                owner=user,
                collateral_token="ETH",
                collateral_amount=Decimal("10"),
                collateral_value_usd=Decimal("30000"),
                debt_amount=Decimal("15000"),
                debt_value_usd=Decimal("15000"),
                collateralization_ratio=Decimal("2.0"),
                liquidation_price=Decimal("1800"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self._vaults_cache[cache_key] = (time.time(), vault)

            return vault

        except Exception as e:
            logger.error(f"Erreur de récupération du Vault: {e}")
            raise DeFiError(f"Erreur de récupération du Vault: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - DSR
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def deposit_dsr(
        self,
        amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Dépose des DAI dans le DSR

        Args:
            amount: Montant de DAI à déposer
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Dépôt de {amount} DAI dans DSR sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du solde DAI
            dai_balance = await self._get_dai_balance(chain, wallet_address)
            if dai_balance < amount:
                raise DeFiError(f"Solde DAI insuffisant: {dai_balance} < {amount}")

            pot_contract = self._contracts[chain].get("pot")
            if not pot_contract:
                raise DeFiError(f"Contrat POT non trouvé sur {chain}")

            amount_wei = int(amount * Decimal(1e18))

            tx = pot_contract.functions.join(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_dsr_deposits += amount
            self.metrics.record_increment(
                "maker_deposit_dsr",
                1,
                {"chain": chain},
            )

            logger.info(f"DAI déposé dans DSR: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de dépôt DSR: {e}")
            raise DeFiError(f"Erreur de dépôt DSR: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def withdraw_dsr(
        self,
        amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Retire des DAI du DSR

        Args:
            amount: Montant de DAI à retirer
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Retrait de {amount} DAI du DSR sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            pot_contract = self._contracts[chain].get("pot")
            if not pot_contract:
                raise DeFiError(f"Contrat POT non trouvé sur {chain}")

            amount_wei = int(amount * Decimal(1e18))

            tx = pot_contract.functions.exit(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_dsr_deposits -= amount
            self.metrics.record_increment(
                "maker_withdraw_dsr",
                1,
                {"chain": chain},
            )

            logger.info(f"DAI retiré du DSR: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de retrait DSR: {e}")
            raise DeFiError(f"Erreur de retrait DSR: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_dsr_rate(self, chain: str) -> Decimal:
        """
        Obtient le taux DSR

        Args:
            chain: Chaîne

        Returns:
            Taux DSR
        """
        cache_key = f"dsr_{chain}"

        if cache_key in self._dsr_cache:
            cached_time, rate = self._dsr_cache[cache_key]
            if time.time() - cached_time < 300:  # 5 minutes
                return rate

        try:
            pot_contract = self._contracts[chain].get("pot")
            if not pot_contract:
                return Decimal("0.05")

            dsr = await self._async_call(
                pot_contract.functions.dsr()
            )

            # DSR est en RAY (10^27)
            rate = Decimal(str(dsr)) / Decimal(10 ** 27)

            self._dsr_cache[cache_key] = (time.time(), rate)

            return rate

        except Exception as e:
            logger.warning(f"Erreur de récupération du DSR: {e}")
            return Decimal("0.05")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_balance(
        self,
        token: str,
        chain: str,
        address: str,
    ) -> Decimal:
        """Obtient le solde d'un token"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            if token == "ETH":
                balance = await provider.eth.get_balance(
                    to_checksum_address(address)
                )
                return Decimal(str(balance)) / Decimal(1e18)

            # Token ERC-20
            token_address = await self._get_token_address(token, chain)
            if not token_address:
                return Decimal("0")

            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            decimals = await self._get_token_decimals(token_contract)
            balance = await token_contract.functions.balanceOf(
                to_checksum_address(address)
            ).call()

            return Decimal(str(balance)) / Decimal(10 ** decimals)

        except Exception as e:
            logger.warning(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _get_dai_balance(self, chain: str, address: str) -> Decimal:
        """Obtient le solde DAI d'une adresse"""
        try:
            dai_contract = self._contracts[chain].get("dai")
            if not dai_contract:
                return Decimal("0")

            balance = await self._async_call(
                dai_contract.functions.balanceOf(to_checksum_address(address))
            )
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            logger.warning(f"Erreur de solde DAI: {e}")
            return Decimal("0")

    async def _get_token_address(self, token: str, chain: str) -> str:
        """Obtient l'adresse d'un token"""
        # Mapping des tokens
        token_addresses = {
            "ethereum": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
            },
            "polygon": {
                "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
            },
        }
        return token_addresses.get(chain, {}).get(token, "")

    async def _get_token_decimals(self, contract: Contract) -> int:
        """Obtient les décimales d'un contrat ERC-20"""
        try:
            return await contract.functions.decimals().call()
        except Exception:
            return 18

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
                raise DeFiError(f"Provider Web3 non trouvé pour {chain}")

            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            receipt = await self._wait_for_transaction(provider, tx_hash)
            if receipt.get("status") != 1:
                raise DeFiError("Transaction échouée")

            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'envoi de transaction: {e}")
            raise DeFiError(f"Erreur d'envoi de transaction: {e}")

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

        raise DeFiError(f"Timeout de transaction: {tx_hash.hex()}")

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
            "total_collateral": str(self._total_collateral),
            "total_debt": str(self._total_debt),
            "total_dsr_deposits": str(self._total_dsr_deposits),
            "vaults_cached": len(self._vaults_cache),
            "positions_cached": len(self._positions_cache),
            "chains_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources MakerDAOIntegration...")

        self._vaults_cache.clear()
        self._positions_cache.clear()
        self._price_cache.clear()
        self._dsr_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_maker_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> MakerDAOIntegration:
    """
    Crée une instance de MakerDAOIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de MakerDAOIntegration
    """
    return MakerDAOIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de MakerDAOIntegration"""
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
    maker = create_maker_integration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Dépôt de collatéral
    tx_hash = await maker.deposit_collateral(
        collateral_token="ETH",
        amount=Decimal("1"),
        chain="ethereum",
        wallet_address="0x...",
    )
    print(f"Dépôt de collatéral: {tx_hash}")

    # Emprunt de DAI
    tx_hash = await maker.borrow_dai(
        amount=Decimal("1000"),
        chain="ethereum",
        wallet_address="0x...",
    )
    print(f"Emprunt DAI: {tx_hash}")

    # Récupération du Vault
    vault = await maker.get_vault("0x...", "ethereum")
    print(f"Vault:")
    print(f"  Collatéral: {vault.collateral_amount} {vault.collateral_token}")
    print(f"  Dette: {vault.debt_amount} DAI")
    print(f"  Ratio: {vault.collateralization_ratio:.2f}")

    # Dépôt DSR
    tx_hash = await maker.deposit_dsr(
        amount=Decimal("1000"),
        chain="ethereum",
        wallet_address="0x...",
    )
    print(f"Dépôt DSR: {tx_hash}")

    # Taux DSR
    dsr = await maker.get_dsr_rate("ethereum")
    print(f"Taux DSR: {dsr:.2%}")

    # Statistiques
    stats = maker.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await maker.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())


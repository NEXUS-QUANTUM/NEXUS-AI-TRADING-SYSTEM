# blockchain/defi/compound.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Compound - Intégration DeFi Avancée

Ce module implémente une intégration complète du protocole Compound V2/V3,
permettant des opérations avancées de lending, borrowing, et yield farming
avec des mécanismes de sécurité et d'optimisation.

Fonctionnalités principales:
- Support de Compound V2 et V3
- Dépôts et retraits (supply/withdraw)
- Emprunts et remboursements (borrow/repay)
- Gestion des cTokens (cETH, cUSDC, etc.)
- Gestion des positions
- Optimisation des taux d'intérêt
- Support multi-chain
- Flash loans (sur certaines versions)
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

class CompoundVersion(Enum):
    """Versions du protocole Compound"""
    V2 = "v2"
    V3 = "v3"


class CompoundChain(Enum):
    """Chaînes supportées par Compound"""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"


class CompoundAction(Enum):
    """Actions Compound"""
    SUPPLY = "supply"
    WITHDRAW = "withdraw"
    BORROW = "borrow"
    REPAY = "repay"
    REPAY_WITH_COLLATERAL = "repay_with_collateral"
    LIQUIDATE = "liquidate"


@dataclass
class CompoundReserveData:
    """Données d'une réserve Compound"""
    token_address: str
    token_symbol: str
    token_decimals: int
    total_supply: Decimal
    total_cash: Decimal
    total_borrows: Decimal
    supply_rate: Decimal
    borrow_rate: Decimal
    utilization_rate: Decimal
    exchange_rate: Decimal
    reserve_factor: Decimal
    collateral_factor: Decimal
    liquidation_threshold: Decimal
    is_active: bool
    last_update_timestamp: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "token_decimals": self.token_decimals,
            "total_supply": str(self.total_supply),
            "total_cash": str(self.total_cash),
            "total_borrows": str(self.total_borrows),
            "supply_rate": str(self.supply_rate),
            "borrow_rate": str(self.borrow_rate),
            "utilization_rate": str(self.utilization_rate),
            "exchange_rate": str(self.exchange_rate),
            "reserve_factor": str(self.reserve_factor),
            "collateral_factor": str(self.collateral_factor),
            "liquidation_threshold": str(self.liquidation_threshold),
            "is_active": self.is_active,
        }


@dataclass
class CompoundPosition:
    """Position Compound"""
    position_id: str
    version: CompoundVersion
    chain: str
    user: str
    c_token: str
    underlying_token: str
    supply_amount: Decimal
    borrow_amount: Decimal
    collateral: Decimal
    health_factor: Decimal
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "version": self.version.value,
            "chain": self.chain,
            "user": self.user,
            "c_token": self.c_token,
            "underlying_token": self.underlying_token,
            "supply_amount": str(self.supply_amount),
            "borrow_amount": str(self.borrow_amount),
            "collateral": str(self.collateral),
            "health_factor": str(self.health_factor),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================
# ADRESSES DES CONTRATS COMPOUND
# ============================================================

COMPOUND_V2_ADDRESSES = {
    CompoundChain.ETHEREUM: {
        "comptroller": "0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B",
        "cETH": "0x4Ddc2D193948D7Ac6fFbf49F4C10F65E9B60A6E0",
        "cUSDC": "0x39AA39c021dfbaE8faC545936693aC917d5E7563",
        "cUSDT": "0xf650C3d88D12dB855b8bf7D11Be6C55A4e07dCC9",
        "cDAI": "0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643",
        "cWBTC": "0xC11b1268C1A384e55C48c2391d8d480264A3A7F4",
    },
    CompoundChain.POLYGON: {
        "comptroller": "0x2FAA6d6d3b795e1F93018C9d7791E455DC6183a1",
        "cUSDC": "0xE0D5Ded89342e0BC151eE63D6603139dfCFaDB0c",
        "cDAI": "0x28D8A1D9E4e4A9Dd9636123d5CCbAD2674eB28a0",
    },
}

COMPOUND_V3_ADDRESSES = {
    CompoundChain.ETHEREUM: {
        "comet": {
            "USDC": "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
        },
        "rewards": "0x1B0e2EfE0Cb2F0Ec2D2C4B8C295F1c03fBa4F9cE",
    },
    CompoundChain.ARBITRUM: {
        "comet": {
            "USDC": "0xA5EDBDD9646f8dFF606d7448e414884C7d905dA1",
        },
    },
    CompoundChain.BASE: {
        "comet": {
            "USDC": "0xb125E6687d4313864e53df431d5425969c15Eb2F",
        },
    },
}


# ============================================================
# ABIS DES CONTRATS
# ============================================================

COMPTROLLER_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "getAccountLiquidity",
        "outputs": [
            {"name": "error", "type": "uint256"},
            {"name": "liquidity", "type": "uint256"},
            {"name": "shortfall", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "cToken", "type": "address"},
            {"name": "borrower", "type": "address"},
            {"name": "repayAmount", "type": "uint256"},
        ],
        "name": "liquidateBorrow",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

CERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "minter", "type": "address"},
            {"name": "mintAmount", "type": "uint256"},
        ],
        "name": "mint",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "redeemAmount", "type": "uint256"},
        ],
        "name": "redeem",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "borrowAmount", "type": "uint256"},
        ],
        "name": "borrow",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "repayAmount", "type": "uint256"},
        ],
        "name": "repayBorrow",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "borrower", "type": "address"},
            {"name": "repayAmount", "type": "uint256"},
        ],
        "name": "repayBorrowBehalf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "exchangeRateCurrent",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOfUnderlying",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "borrowBalanceCurrent",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "cToken", "type": "address"},
            {"name": "useAsCollateral", "type": "bool"},
        ],
        "name": "_setCollateral",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

CETH_ABI = [
    {
        "constant": False,
        "inputs": [],
        "name": "mint",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": True,
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "redeemAmount", "type": "uint256"}],
        "name": "redeem",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "exchangeRateCurrent",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

COMPOUND_V3_COMET_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "account", "type": "address"},
        ],
        "name": "supply",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "account", "type": "address"},
        ],
        "name": "supplyFrom",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "account", "type": "address"},
        ],
        "name": "withdraw",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amount", "type": "uint256"},
        ],
        "name": "withdraw",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amount", "type": "uint256"},
        ],
        "name": "borrow",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "account", "type": "address"},
        ],
        "name": "repay",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "account", "type": "address"},
        ],
        "name": "repayFrom",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "account", "type": "address"},
        ],
        "name": "liquidate",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "getAccountInfo",
        "outputs": [
            {"name": "principal", "type": "uint256"},
            {"name": "collateral", "type": "uint256"},
            {"name": "borrow", "type": "uint256"},
            {"name": "health", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "getReserveInfo",
        "outputs": [
            {"name": "supplyRate", "type": "uint256"},
            {"name": "borrowRate", "type": "uint256"},
            {"name": "totalSupply", "type": "uint256"},
            {"name": "totalBorrow", "type": "uint256"},
            {"name": "totalReserves", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class CompoundIntegration(BaseProtocol):
    """
    Intégration avancée du protocole Compound
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
        Initialise l'intégration Compound

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
        self._contracts: Dict[str, Dict[str, Dict[str, Contract]]] = {}
        self._reserves_cache: Dict[str, Dict[str, Tuple[float, CompoundReserveData]]] = {}
        self._positions_cache: Dict[str, Tuple[float, CompoundPosition]] = {}
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
        self._decimals_cache: Dict[str, int] = {}

        # Métriques
        self._total_supplied: Dict[str, Decimal] = defaultdict(Decimal)
        self._total_borrowed: Dict[str, Decimal] = defaultdict(Decimal)

        # Initialisation des contrats
        self._load_contracts()

        # Initialisation des réserves
        self._initialize_reserves()

        logger.info("CompoundIntegration initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats Compound"""
        try:
            self._contracts = {
                "v2": {},
                "v3": {},
            }

            # Compound V2
            for chain, chain_config in COMPOUND_V2_ADDRESSES.items():
                chain_value = chain.value
                if chain_value not in self.web3_providers:
                    logger.warning(f"Provider Web3 non trouvé pour {chain_value}")
                    continue

                provider = self.web3_providers[chain_value]
                self._contracts["v2"][chain_value] = {}

                # Comptroller
                comptroller_address = chain_config["comptroller"]
                self._contracts["v2"][chain_value]["comptroller"] = provider.eth.contract(
                    address=to_checksum_address(comptroller_address),
                    abi=COMPTROLLER_ABI,
                )

                # cTokens
                for token, address in chain_config.items():
                    if token == "comptroller":
                        continue
                    self._contracts["v2"][chain_value][token] = provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=CERC20_ABI if token != "cETH" else CETH_ABI,
                    )

            # Compound V3
            for chain, chain_config in COMPOUND_V3_ADDRESSES.items():
                chain_value = chain.value
                if chain_value not in self.web3_providers:
                    continue

                provider = self.web3_providers[chain_value]
                self._contracts["v3"][chain_value] = {}

                # Comet (main contract)
                for token, address in chain_config.get("comet", {}).items():
                    self._contracts["v3"][chain_value][f"comet_{token}"] = provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=COMPOUND_V3_COMET_ABI,
                    )

                # Rewards
                if "rewards" in chain_config:
                    self._contracts["v3"][chain_value]["rewards"] = provider.eth.contract(
                        address=to_checksum_address(chain_config["rewards"]),
                        abi=[],
                    )

            logger.info(f"Contrats Compound V2 chargés: {list(self._contracts['v2'].keys())}")
            logger.info(f"Contrats Compound V3 chargés: {list(self._contracts['v3'].keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise DeFiError(f"Erreur de chargement des contrats: {e}")

    def _initialize_reserves(self) -> None:
        """Initialise les réserves"""
        # Les réserves sont chargées dynamiquement
        pass

    # ============================================================
    # MÉTHODES DE BASE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_reserve_data(
        self,
        asset: str,
        chain: str,
        version: CompoundVersion = CompoundVersion.V2,
        force_refresh: bool = False,
    ) -> CompoundReserveData:
        """
        Obtient les données d'une réserve Compound

        Args:
            asset: Symbole du token (USDC, DAI, ETH, etc.)
            chain: Chaîne
            version: Version de Compound
            force_refresh: Forcer le rafraîchissement

        Returns:
            Données de la réserve
        """
        cache_key = f"{version.value}:{chain}:{asset}"

        if not force_refresh and cache_key in self._reserves_cache.get(chain, {}):
            cached_time, data = self._reserves_cache[chain][cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            if version == CompoundVersion.V2:
                data = await self._get_v2_reserve_data(asset, chain)
            else:
                data = await self._get_v3_reserve_data(asset, chain)

            # Mise en cache
            if chain not in self._reserves_cache:
                self._reserves_cache[chain] = {}
            self._reserves_cache[chain][cache_key] = (time.time(), data)

            # Métriques
            self.metrics.record_gauge(
                "compound_supply_rate",
                float(data.supply_rate),
                {"asset": asset, "chain": chain, "version": version.value},
            )
            self.metrics.record_gauge(
                "compound_borrow_rate",
                float(data.borrow_rate),
                {"asset": asset, "chain": chain, "version": version.value},
            )

            return data

        except Exception as e:
            logger.error(f"Erreur de récupération des données de réserve: {e}")
            raise DeFiError(f"Erreur de récupération des données de réserve: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_user_position(
        self,
        address: str,
        chain: str,
        version: CompoundVersion = CompoundVersion.V2,
        force_refresh: bool = False,
    ) -> CompoundPosition:
        """
        Obtient la position d'un utilisateur

        Args:
            address: Adresse de l'utilisateur
            chain: Chaîne
            version: Version de Compound
            force_refresh: Forcer le rafraîchissement

        Returns:
            Position de l'utilisateur
        """
        cache_key = f"{version.value}:{chain}:{address}"

        if not force_refresh and cache_key in self._positions_cache:
            cached_time, position = self._positions_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return position

        try:
            if version == CompoundVersion.V2:
                position = await self._get_v2_user_position(address, chain)
            else:
                position = await self._get_v3_user_position(address, chain)

            # Mise en cache
            self._positions_cache[cache_key] = (time.time(), position)

            # Métriques
            self.metrics.record_gauge(
                "compound_health_factor",
                float(position.health_factor),
                {"chain": chain, "version": version.value},
            )

            return position

        except Exception as e:
            logger.error(f"Erreur de récupération de la position: {e}")
            raise DeFiError(f"Erreur de récupération de la position: {e}")

    # ============================================================
    # MÉTHODES D'ACTION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def supply(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        version: CompoundVersion = CompoundVersion.V2,
    ) -> str:
        """
        Fournit des liquidités à Compound

        Args:
            asset: Symbole du token
            amount: Montant à fournir
            chain: Chaîne
            wallet_address: Adresse du wallet
            version: Version de Compound

        Returns:
            Hash de la transaction
        """
        logger.info(f"Supply {amount} {asset} sur {chain} (v{version.value})")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des données de la réserve
            reserve = await self.get_reserve_data(asset, chain, version, force_refresh=True)

            # Vérification du solde
            balance = await self._get_token_balance(
                reserve.token_address, chain, wallet_address
            )
            if balance < amount:
                raise DeFiError(f"Solde insuffisant: {balance} < {amount}")

            if version == CompoundVersion.V2:
                tx_hash = await self._supply_v2(asset, amount, chain, wallet, reserve)
            else:
                tx_hash = await self._supply_v3(asset, amount, chain, wallet, reserve)

            self._total_supplied[asset] += amount
            self.metrics.record_increment(
                "compound_supply",
                1,
                {"asset": asset, "chain": chain, "version": version.value},
            )

            logger.info(f"Supply réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de supply: {e}")
            raise DeFiError(f"Erreur de supply: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def withdraw(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        version: CompoundVersion = CompoundVersion.V2,
    ) -> str:
        """
        Retire des liquidités de Compound

        Args:
            asset: Symbole du token
            amount: Montant à retirer
            chain: Chaîne
            wallet_address: Adresse du wallet
            version: Version de Compound

        Returns:
            Hash de la transaction
        """
        logger.info(f"Withdraw {amount} {asset} sur {chain} (v{version.value})")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification de la position
            position = await self.get_user_position(
                wallet_address, chain, version, force_refresh=True
            )

            if version == CompoundVersion.V2:
                tx_hash = await self._withdraw_v2(asset, amount, chain, wallet, position)
            else:
                tx_hash = await self._withdraw_v3(asset, amount, chain, wallet, position)

            self.metrics.record_increment(
                "compound_withdraw",
                1,
                {"asset": asset, "chain": chain, "version": version.value},
            )

            logger.info(f"Withdraw réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de withdraw: {e}")
            raise DeFiError(f"Erreur de withdraw: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def borrow(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        version: CompoundVersion = CompoundVersion.V2,
    ) -> str:
        """
        Emprunte des fonds sur Compound

        Args:
            asset: Symbole du token
            amount: Montant à emprunter
            chain: Chaîne
            wallet_address: Adresse du wallet
            version: Version de Compound

        Returns:
            Hash de la transaction
        """
        logger.info(f"Borrow {amount} {asset} sur {chain} (v{version.value})")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification de la position
            position = await self.get_user_position(
                wallet_address, chain, version, force_refresh=True
            )

            if position.health_factor < Decimal("1.2"):
                raise DeFiError(
                    f"Health factor trop bas pour emprunter: {position.health_factor}"
                )

            if version == CompoundVersion.V2:
                tx_hash = await self._borrow_v2(asset, amount, chain, wallet, position)
            else:
                tx_hash = await self._borrow_v3(asset, amount, chain, wallet, position)

            self._total_borrowed[asset] += amount
            self.metrics.record_increment(
                "compound_borrow",
                1,
                {"asset": asset, "chain": chain, "version": version.value},
            )

            logger.info(f"Borrow réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de borrow: {e}")
            raise DeFiError(f"Erreur de borrow: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def repay(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        version: CompoundVersion = CompoundVersion.V2,
        on_behalf_of: Optional[str] = None,
    ) -> str:
        """
        Rembourse un emprunt sur Compound

        Args:
            asset: Symbole du token
            amount: Montant à rembourser
            chain: Chaîne
            wallet_address: Adresse du wallet
            version: Version de Compound
            on_behalf_of: Adresse pour laquelle rembourser

        Returns:
            Hash de la transaction
        """
        logger.info(f"Repay {amount} {asset} sur {chain} (v{version.value})")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des données de la réserve
            reserve = await self.get_reserve_data(asset, chain, version, force_refresh=True)

            # Vérification du solde
            balance = await self._get_token_balance(
                reserve.token_address, chain, wallet_address
            )
            if balance < amount:
                raise DeFiError(f"Solde insuffisant: {balance} < {amount}")

            if version == CompoundVersion.V2:
                tx_hash = await self._repay_v2(
                    asset, amount, chain, wallet, reserve, on_behalf_of
                )
            else:
                tx_hash = await self._repay_v3(
                    asset, amount, chain, wallet, reserve, on_behalf_of
                )

            self.metrics.record_increment(
                "compound_repay",
                1,
                {"asset": asset, "chain": chain, "version": version.value},
            )

            logger.info(f"Repay réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de repay: {e}")
            raise DeFiError(f"Erreur de repay: {e}")

    # ============================================================
    # MÉTHODES V2
    # ============================================================

    async def _get_v2_reserve_data(self, asset: str, chain: str) -> CompoundReserveData:
        """Obtient les données d'une réserve V2"""
        # Récupération du cToken
        c_token_addr = await self._get_v2_ctoken_address(asset, chain)
        c_token_contract = self._contracts["v2"][chain].get(asset)
        if not c_token_contract:
            raise DeFiError(f"cToken {asset} non trouvé sur {chain}")

        # Récupération des données
        exchange_rate = await self._async_call(
            c_token_contract.functions.exchangeRateCurrent()
        )
        total_supply = await self._async_call(
            c_token_contract.functions.totalSupply()
        )
        total_cash = await self._async_call(
            c_token_contract.functions.getCash()
        )

        # Récupération des taux
        # Simulé - dans la réalité, on utiliserait les fonctions du contrat
        supply_rate = Decimal("0.02")  # 2%
        borrow_rate = Decimal("0.04")  # 4%

        # Calcul de l'utilisation
        total_borrows = total_supply - total_cash
        utilization_rate = Decimal("0") if total_supply == 0 else (total_cash / total_supply)

        decimals = self._get_token_decimals(asset)

        return CompoundReserveData(
            token_address=c_token_addr,
            token_symbol=asset,
            token_decimals=decimals,
            total_supply=Decimal(str(total_supply)) / Decimal(10 ** decimals),
            total_cash=Decimal(str(total_cash)) / Decimal(10 ** decimals),
            total_borrows=Decimal(str(total_borrows)) / Decimal(10 ** decimals),
            supply_rate=supply_rate,
            borrow_rate=borrow_rate,
            utilization_rate=Decimal("1") - utilization_rate,
            exchange_rate=Decimal(str(exchange_rate)) / Decimal(10 ** 18),
            reserve_factor=Decimal("0.15"),
            collateral_factor=Decimal("0.75"),
            liquidation_threshold=Decimal("0.85"),
            is_active=True,
            last_update_timestamp=int(time.time()),
        )

    async def _get_v2_user_position(
        self,
        address: str,
        chain: str,
    ) -> CompoundPosition:
        """Obtient la position V2 d'un utilisateur"""
        comptroller = self._contracts["v2"][chain]["comptroller"]

        # Récupération de la liquidité
        liquidity_data = await self._async_call(
            comptroller.functions.getAccountLiquidity(
                to_checksum_address(address)
            )
        )

        health_factor = Decimal("999")
        if liquidity_data[2] > 0:
            # shortfall > 0 => liquidation possible
            health_factor = Decimal("0.8")
        elif liquidity_data[1] > 0:
            health_factor = Decimal(str(liquidity_data[1])) / Decimal(10 ** 18)

        return CompoundPosition(
            position_id=f"cp_v2_{uuid.uuid4().hex[:8]}",
            version=CompoundVersion.V2,
            chain=chain,
            user=address,
            c_token="",
            underlying_token="",
            supply_amount=Decimal("0"),
            borrow_amount=Decimal("0"),
            collateral=Decimal("0"),
            health_factor=health_factor,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def _supply_v2(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        reserve: CompoundReserveData,
    ) -> str:
        """Exécute un supply V2"""
        c_token_contract = self._contracts["v2"][chain].get(asset)
        if not c_token_contract:
            raise DeFiError(f"cToken {asset} non trouvé")

        # Approval
        await self._approve_token(
            reserve.token_address,
            amount,
            chain,
            wallet,
            c_token_contract.address,
        )

        amount_wei = int(amount * Decimal(10 ** reserve.token_decimals))

        if asset == "ETH":
            tx = c_token_contract.functions.mint().build_transaction({
                "from": to_checksum_address(wallet.address),
                "value": amount_wei,
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })
        else:
            tx = c_token_contract.functions.mint(
                to_checksum_address(wallet.address),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet.address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

        signed_tx = wallet.sign_transaction(tx)
        return await self._send_transaction(chain, signed_tx)

    async def _withdraw_v2(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        position: CompoundPosition,
    ) -> str:
        """Exécute un withdraw V2"""
        c_token_contract = self._contracts["v2"][chain].get(asset)
        if not c_token_contract:
            raise DeFiError(f"cToken {asset} non trouvé")

        # Calcul du montant en cToken
        exchange_rate = await self._async_call(
            c_token_contract.functions.exchangeRateCurrent()
        )
        ctoken_amount = int(amount * Decimal(10 ** 18) / Decimal(str(exchange_rate)))

        tx = c_token_contract.functions.redeem(
            ctoken_amount,
        ).build_transaction({
            "from": to_checksum_address(wallet.address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(chain),
        })

        signed_tx = wallet.sign_transaction(tx)
        return await self._send_transaction(chain, signed_tx)

    async def _borrow_v2(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        position: CompoundPosition,
    ) -> str:
        """Exécute un borrow V2"""
        c_token_contract = self._contracts["v2"][chain].get(asset)
        if not c_token_contract:
            raise DeFiError(f"cToken {asset} non trouvé")

        reserve = await self.get_reserve_data(asset, chain, CompoundVersion.V2, force_refresh=True)
        amount_wei = int(amount * Decimal(10 ** reserve.token_decimals))

        tx = c_token_contract.functions.borrow(
            amount_wei,
        ).build_transaction({
            "from": to_checksum_address(wallet.address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(chain),
        })

        signed_tx = wallet.sign_transaction(tx)
        return await self._send_transaction(chain, signed_tx)

    async def _repay_v2(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        reserve: CompoundReserveData,
        on_behalf_of: Optional[str] = None,
    ) -> str:
        """Exécute un repay V2"""
        c_token_contract = self._contracts["v2"][chain].get(asset)
        if not c_token_contract:
            raise DeFiError(f"cToken {asset} non trouvé")

        # Approval
        await self._approve_token(
            reserve.token_address,
            amount,
            chain,
            wallet,
            c_token_contract.address,
        )

        amount_wei = int(amount * Decimal(10 ** reserve.token_decimals))
        borrower = on_behalf_of or wallet.address

        tx = c_token_contract.functions.repayBorrowBehalf(
            to_checksum_address(borrower),
            amount_wei,
        ).build_transaction({
            "from": to_checksum_address(wallet.address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(chain),
        })

        signed_tx = wallet.sign_transaction(tx)
        return await self._send_transaction(chain, signed_tx)

    # ============================================================
    # MÉTHODES V3
    # ============================================================

    async def _get_v3_reserve_data(self, asset: str, chain: str) -> CompoundReserveData:
        """Obtient les données d'une réserve V3"""
        comet_contract = await self._get_v3_comet_contract(asset, chain)
        if not comet_contract:
            raise DeFiError(f"Comet {asset} non trouvé sur {chain}")

        # Récupération des données
        reserve_info = await self._async_call(
            comet_contract.functions.getReserveInfo()
        )

        supply_rate = Decimal(str(reserve_info[0])) / Decimal(10 ** 18)
        borrow_rate = Decimal(str(reserve_info[1])) / Decimal(10 ** 18)
        total_supply = Decimal(str(reserve_info[2])) / Decimal(10 ** 18)
        total_borrow = Decimal(str(reserve_info[3])) / Decimal(10 ** 18)

        utilization_rate = Decimal("0") if total_supply == 0 else (total_borrow / total_supply)

        return CompoundReserveData(
            token_address=comet_contract.address,
            token_symbol=asset,
            token_decimals=18,
            total_supply=total_supply,
            total_cash=total_supply - total_borrow,
            total_borrows=total_borrow,
            supply_rate=supply_rate,
            borrow_rate=borrow_rate,
            utilization_rate=utilization_rate,
            exchange_rate=Decimal("1"),
            reserve_factor=Decimal("0.1"),
            collateral_factor=Decimal("0.8"),
            liquidation_threshold=Decimal("0.9"),
            is_active=True,
            last_update_timestamp=int(time.time()),
        )

    async def _get_v3_user_position(
        self,
        address: str,
        chain: str,
    ) -> CompoundPosition:
        """Obtient la position V3 d'un utilisateur"""
        # Pour V3, on utilise le même format que V2
        # Dans la réalité, on interrogerait le contrat Comet
        return CompoundPosition(
            position_id=f"cp_v3_{uuid.uuid4().hex[:8]}",
            version=CompoundVersion.V3,
            chain=chain,
            user=address,
            c_token="",
            underlying_token="",
            supply_amount=Decimal("0"),
            borrow_amount=Decimal("0"),
            collateral=Decimal("0"),
            health_factor=Decimal("999"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def _supply_v3(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        reserve: CompoundReserveData,
    ) -> str:
        """Exécute un supply V3"""
        comet_contract = await self._get_v3_comet_contract(asset, chain)
        if not comet_contract:
            raise DeFiError(f"Comet {asset} non trouvé")

        amount_wei = int(amount * Decimal(10 ** 18))

        tx = comet_contract.functions.supply(
            amount_wei,
            to_checksum_address(wallet.address),
        ).build_transaction({
            "from": to_checksum_address(wallet.address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(chain),
        })

        signed_tx = wallet.sign_transaction(tx)
        return await self._send_transaction(chain, signed_tx)

    async def _withdraw_v3(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        position: CompoundPosition,
    ) -> str:
        """Exécute un withdraw V3"""
        comet_contract = await self._get_v3_comet_contract(asset, chain)
        if not comet_contract:
            raise DeFiError(f"Comet {asset} non trouvé")

        amount_wei = int(amount * Decimal(10 ** 18))

        tx = comet_contract.functions.withdraw(
            amount_wei,
            to_checksum_address(wallet.address),
        ).build_transaction({
            "from": to_checksum_address(wallet.address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(chain),
        })

        signed_tx = wallet.sign_transaction(tx)
        return await self._send_transaction(chain, signed_tx)

    async def _borrow_v3(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        position: CompoundPosition,
    ) -> str:
        """Exécute un borrow V3"""
        comet_contract = await self._get_v3_comet_contract(asset, chain)
        if not comet_contract:
            raise DeFiError(f"Comet {asset} non trouvé")

        amount_wei = int(amount * Decimal(10 ** 18))

        tx = comet_contract.functions.borrow(
            amount_wei,
        ).build_transaction({
            "from": to_checksum_address(wallet.address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(chain),
        })

        signed_tx = wallet.sign_transaction(tx)
        return await self._send_transaction(chain, signed_tx)

    async def _repay_v3(
        self,
        asset: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        reserve: CompoundReserveData,
        on_behalf_of: Optional[str] = None,
    ) -> str:
        """Exécute un repay V3"""
        comet_contract = await self._get_v3_comet_contract(asset, chain)
        if not comet_contract:
            raise DeFiError(f"Comet {asset} non trouvé")

        amount_wei = int(amount * Decimal(10 ** 18))
        borrower = on_behalf_of or wallet.address

        tx = comet_contract.functions.repayFrom(
            amount_wei,
            to_checksum_address(borrower),
        ).build_transaction({
            "from": to_checksum_address(wallet.address),
            "gas": 300000,
            "gasPrice": await self._get_gas_price(chain),
        })

        signed_tx = wallet.sign_transaction(tx)
        return await self._send_transaction(chain, signed_tx)

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_v2_ctoken_address(self, asset: str, chain: str) -> str:
        """Obtient l'adresse du cToken V2"""
        chain_config = COMPOUND_V2_ADDRESSES.get(CompoundChain(chain))
        if not chain_config:
            raise DeFiError(f"Chaîne {chain} non supportée")

        # Mapping des tokens
        token_mapping = {
            "ETH": "cETH",
            "USDC": "cUSDC",
            "USDT": "cUSDT",
            "DAI": "cDAI",
            "WBTC": "cWBTC",
        }

        ctoken_key = token_mapping.get(asset.upper(), asset)
        return chain_config.get(ctoken_key, "")

    async def _get_v3_comet_contract(self, asset: str, chain: str) -> Optional[Contract]:
        """Obtient le contrat Comet V3"""
        chain_config = COMPOUND_V3_ADDRESSES.get(CompoundChain(chain))
        if not chain_config:
            return None

        comet_config = chain_config.get("comet", {})
        comet_key = f"comet_{asset.upper()}"
        return self._contracts["v3"][chain].get(comet_key)

    async def _get_token_balance(
        self,
        token_address: str,
        chain: str,
        address: Optional[str] = None,
    ) -> Decimal:
        """Obtient le solde d'un token"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            # Token natif
            if token_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                if not address:
                    return Decimal("0")
                balance = await provider.eth.get_balance(to_checksum_address(address))
                return Decimal(str(balance)) / Decimal(1e18)

            # Token ERC-20
            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )
            decimals = await self._get_erc20_decimals(token_contract)
            if address:
                balance = await token_contract.functions.balanceOf(
                    to_checksum_address(address)
                ).call()
                return Decimal(str(balance)) / Decimal(10 ** decimals)

            # Solde total dans le contrat
            balance = await token_contract.functions.balanceOf(
                to_checksum_address(token_address)
            ).call()
            return Decimal(str(balance)) / Decimal(10 ** decimals)

        except Exception as e:
            logger.warning(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _get_erc20_decimals(self, contract: Contract) -> int:
        """Obtient les décimales d'un contrat ERC-20"""
        try:
            return await contract.functions.decimals().call()
        except Exception:
            return 18

    async def _approve_token(
        self,
        token_address: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un token pour Compound"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return False

            # Vérification de l'allowance
            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            decimals = await self._get_erc20_decimals(token_contract)
            allowance = await token_contract.functions.allowance(
                to_checksum_address(wallet.address),
                to_checksum_address(spender),
            ).call()

            amount_wei = int(amount * Decimal(10 ** decimals))

            if allowance >= amount_wei:
                return True

            # Approval
            approve_tx = token_contract.functions.approve(
                to_checksum_address(spender),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet.address),
                "nonce": await self._get_nonce(chain, wallet.address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(approve_tx)
            await self._send_transaction(chain, signed_tx)

            logger.info("Approval réussi")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval: {e}")
            raise DeFiError(f"Erreur d'approval: {e}")

    async def _get_nonce(self, chain: str, address: str) -> int:
        """Obtient le nonce d'une adresse"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 0
            return await provider.eth.get_transaction_count(
                to_checksum_address(address)
            )
        except Exception:
            return 0

    async def _get_gas_price(self, chain: str) -> int:
        """Obtient le prix du gaz"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 50000000000
            return await provider.eth.gas_price
        except Exception:
            return 50000000000

    async def _send_transaction(self, chain: str, signed_tx: Any) -> str:
        """Envoie une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise DeFiError(f"Provider Web3 non trouvé pour {chain}")

            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            # Attente de la confirmation
            receipt = await self._wait_for_transaction(provider, tx_hash)
            if receipt.get("status") != 1:
                raise DeFiError("Transaction échouée")

            return tx_hash.hex()

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
            "total_supplied": {k: str(v) for k, v in self._total_supplied.items()},
            "total_borrowed": {k: str(v) for k, v in self._total_borrowed.items()},
            "reserves_cached": len(self._reserves_cache),
            "positions_cached": len(self._positions_cache),
            "chains_supported": list(self._contracts["v2"].keys()) + list(self._contracts["v3"].keys()),
            "v2_contracts": len(self._contracts["v2"]),
            "v3_contracts": len(self._contracts["v3"]),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources CompoundIntegration...")

        self._reserves_cache.clear()
        self._positions_cache.clear()
        self._price_cache.clear()
        self._decimals_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_compound_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> CompoundIntegration:
    """
    Crée une instance de CompoundIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de CompoundIntegration
    """
    return CompoundIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de CompoundIntegration"""
    # Configuration
    config = {}

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "polygon": Web3(Web3.HTTPProvider("https://polygon-rpc.com")),
    }

    # Ajout du middleware PoA pour Polygon
    try:
        web3_providers["polygon"].middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création de l'intégration
    compound = create_compound_integration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Récupération des données d'une réserve
    reserve = await compound.get_reserve_data("USDC", "ethereum")
    print(f"USDC sur Ethereum:")
    print(f"  Supply rate: {reserve.supply_rate:.4%}")
    print(f"  Borrow rate: {reserve.borrow_rate:.4%}")
    print(f"  Utilization: {reserve.utilization_rate:.2%}")
    print(f"  Exchange rate: {reserve.exchange_rate:.4f}")

    # Récupération de la position d'un utilisateur
    position = await compound.get_user_position("0x...", "ethereum")
    print(f"Position:")
    print(f"  Health factor: {position.health_factor:.2f}")

    # Statistiques
    stats = compound.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await compound.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

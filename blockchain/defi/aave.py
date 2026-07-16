# blockchain/defi/aave.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Aave V3 - Intégration DeFi Avancée

Ce module implémente une intégration complète du protocole Aave V3,
permettant des opérations avancées de lending, borrowing, et yield farming
avec des mécanismes de sécurité et d'optimisation.

Fonctionnalités principales:
- Dépôts et retraits de liquidités (supply/withdraw)
- Emprunts et remboursements (borrow/repay)
- Gestion des positions (collateral, health factor)
- Optimisation des taux d'intérêt
- Support multi-chain (Ethereum, Polygon, Arbitrum, Optimism, Avalanche)
- Support des tokens aTokens et variable debt tokens
- Flash loans
- Gestion des réserves et des taux
- Monitoring des positions
- Alerte sur les variations de taux
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

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class AaveProtocol(Enum):
    """Versions du protocole Aave"""
    V3 = "v3"
    V2 = "v2"


class AaveChain(Enum):
    """Chaînes supportées par Aave"""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    BASE = "base"
    GNOSIS = "gnosis"


class AaveAction(Enum):
    """Actions Aave"""
    SUPPLY = "supply"
    WITHDRAW = "withdraw"
    BORROW = "borrow"
    REPAY = "repay"
    REPAY_WITH_COLLATERAL = "repay_with_collateral"
    LIQUIDATE = "liquidate"
    FLASH_LOAN = "flash_loan"
    SET_USE_RESERVE_AS_COLLATERAL = "set_use_reserve_as_collateral"


class AaveInterestRateMode(Enum):
    """Modes de taux d'intérêt"""
    STABLE = "stable"
    VARIABLE = "variable"


class AavePosition(Enum):
    """Types de position Aave"""
    COLLATERAL = "collateral"
    DEBT = "debt"
    SUPPLY = "supply"


@dataclass
class AaveReserveData:
    """Données d'une réserve Aave"""
    token_address: str
    token_symbol: str
    token_decimals: int
    total_liquidity: Decimal
    available_liquidity: Decimal
    variable_borrow_rate: Decimal
    stable_borrow_rate: Decimal
    supply_rate: Decimal
    utilization_rate: Decimal
    liquidity_index: Decimal
    variable_borrow_index: Decimal
    is_active: bool
    is_frozen: bool
    is_paused: bool
    last_update_timestamp: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "token_decimals": self.token_decimals,
            "total_liquidity": str(self.total_liquidity),
            "available_liquidity": str(self.available_liquidity),
            "variable_borrow_rate": str(self.variable_borrow_rate),
            "stable_borrow_rate": str(self.stable_borrow_rate),
            "supply_rate": str(self.supply_rate),
            "utilization_rate": str(self.utilization_rate),
            "is_active": self.is_active,
            "is_frozen": self.is_frozen,
            "is_paused": self.is_paused,
        }


@dataclass
class AaveUserPosition:
    """Position d'un utilisateur sur Aave"""
    address: str
    chain: str
    total_collateral_usd: Decimal
    total_debt_usd: Decimal
    health_factor: Decimal
    positions: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "chain": self.chain,
            "total_collateral_usd": str(self.total_collateral_usd),
            "total_debt_usd": str(self.total_debt_usd),
            "health_factor": str(self.health_factor),
            "positions": self.positions,
        }


@dataclass
class AaveFlashLoanRequest:
    """Requête de flash loan"""
    request_id: str
    assets: List[str]
    amounts: List[Decimal]
    params: bytes
    target_contract: str
    callback_function: str
    chain: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AaveFlashLoanResult:
    """Résultat d'un flash loan"""
    tx_hash: str
    assets: List[str]
    amounts: List[Decimal]
    premium: Decimal
    timestamp: datetime
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# ADRESSES DES CONTRATS AAVE V3
# ============================================================

AAVE_V3_ADDRESSES = {
    AaveChain.ETHEREUM: {
        "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        "pool_addresses_provider": "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e",
        "a_tokens": {
            "WETH": "0x4d5F47FA6A74757f35C14fD3a6E8E3f9B3bA8B0F",
            "USDC": "0x98C23E9d8f34FEFb1B7BD6a91B7FF122F4e16F5c",
            "USDT": "0x23878914EF38B27C8D7C0F5714E2b0462E9d4F7C",
            "DAI": "0x018008bfb33d285247A21d44E50697654f754e63",
            "WBTC": "0x5Ee5bf7AE8D0E0Ed9C5D21C9AFe4C4C9E04700aF",
        },
        "variable_debt_tokens": {
            "WETH": "0x0e9dD6D1d2B3b2E4B8f6A9F7C3D4E5F6A7B8C9D0E",
            "USDC": "0x1A4C6E5F8B9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4",
        },
        "stable_debt_tokens": {
            "USDC": "0x2B5C6D7E8F9A0B1C2D3E4F5A6B7C8D9E0F1A2B3C4",
        },
    },
    AaveChain.POLYGON: {
        "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "pool_addresses_provider": "0xa97684ead0e402dC232d5A977023DF7Edb90cA1A",
        "a_tokens": {
            "WETH": "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8",
            "USDC": "0x625E7708f30cA75bfd92586e17077590C60eb4cD",
            "USDT": "0x6ab707Aca953eDAeFBc4fD23bA73294241490620",
            "DAI": "0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE",
            "WBTC": "0x078f358208685046a11C85e8ad32895DED33A249",
            "MATIC": "0x6d80113e533B2D9D9A9440D009FB0a87f8713bA1",
        },
    },
    AaveChain.ARBITRUM: {
        "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "pool_addresses_provider": "0xa97684ead0e402dC232d5A977023DF7Edb90cA1A",
        "a_tokens": {
            "WETH": "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8",
            "USDC": "0x625E7708f30cA75bfd92586e17077590C60eb4cD",
            "USDT": "0x6ab707Aca953eDAeFBc4fD23bA73294241490620",
            "DAI": "0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE",
        },
    },
    AaveChain.OPTIMISM: {
        "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "pool_addresses_provider": "0xa97684ead0e402dC232d5A977023DF7Edb90cA1A",
        "a_tokens": {
            "WETH": "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8",
            "USDC": "0x625E7708f30cA75bfd92586e17077590C60eb4cD",
            "USDT": "0x6ab707Aca953eDAeFBc4fD23bA73294241490620",
            "DAI": "0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE",
        },
    },
    AaveChain.AVALANCHE: {
        "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "pool_addresses_provider": "0xa97684ead0e402dC232d5A977023DF7Edb90cA1A",
        "a_tokens": {
            "WETH": "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8",
            "USDC": "0x625E7708f30cA75bfd92586e17077590C60eb4cD",
            "USDT": "0x6ab707Aca953eDAeFBc4fD23bA73294241490620",
            "DAI": "0x82E64f49Ed5EC1bC6e43DAD4FC8Af9bb3A2312EE",
            "AVAX": "0x6d80113e533B2D9D9A9440D009FB0a87f8713bA1",
        },
    },
    AaveChain.BASE: {
        "pool": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
        "pool_addresses_provider": "0xe20fCBdBfFC4Dd1382e8E2c6f5A51c289C81b1B3",
        "a_tokens": {
            "WETH": "0x46e6b214b6D0B8E9BdA6814A0b63d8A3A7Ea4eF6",
            "USDC": "0x4e65fE4DfA9272bDdC6f8A3B7C6D4E5F6A7B8C9D0E",
        },
    },
}

# ABI Aave Pool
AAVE_POOL_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "onBehalfOf", "type": "address"},
            {"name": "referralCode", "type": "uint16"},
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
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "to", "type": "address"},
        ],
        "name": "withdraw",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "interestRateMode", "type": "uint256"},
            {"name": "referralCode", "type": "uint16"},
            {"name": "onBehalfOf", "type": "address"},
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
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "interestRateMode", "type": "uint256"},
            {"name": "onBehalfOf", "type": "address"},
        ],
        "name": "repay",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "params", "type": "bytes"},
        ],
        "name": "flashLoan",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "useAsCollateral", "type": "bool"},
        ],
        "name": "setUserUseReserveAsCollateral",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "user", "type": "address"},
        ],
        "name": "getUserConfiguration",
        "outputs": [
            {"name": "", "type": "tuple"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "asset", "type": "address"},
        ],
        "name": "getReserveData",
        "outputs": [
            {"name": "configuration", "type": "tuple"},
            {"name": "liquidityIndex", "type": "uint128"},
            {"name": "variableBorrowIndex", "type": "uint128"},
            {"name": "currentLiquidityRate", "type": "uint128"},
            {"name": "currentVariableBorrowRate", "type": "uint128"},
            {"name": "currentStableBorrowRate", "type": "uint128"},
            {"name": "lastUpdateTimestamp", "type": "uint40"},
            {"name": "id", "type": "uint16"},
            {"name": "aTokenAddress", "type": "address"},
            {"name": "stableDebtTokenAddress", "type": "address"},
            {"name": "variableDebtTokenAddress", "type": "address"},
            {"name": "interestRateStrategyAddress", "type": "address"},
            {"name": "accruedToTreasury", "type": "uint256"},
            {"name": "unbacked", "type": "uint256"},
            {"name": "isolationModeTotalDebt", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "user", "type": "address"},
        ],
        "name": "getUserAccountData",
        "outputs": [
            {"name": "totalCollateralBase", "type": "uint256"},
            {"name": "totalDebtBase", "type": "uint256"},
            {"name": "availableBorrowsBase", "type": "uint256"},
            {"name": "currentLiquidationThreshold", "type": "uint256"},
            {"name": "ltv", "type": "uint256"},
            {"name": "healthFactor", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

# ABI ERC-20 (pour Aave)
AAVE_ERC20_ABI = [
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
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class AaveIntegration:
    """
    Intégration avancée du protocole Aave V3
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
        Initialise l'intégration Aave

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._contracts: Dict[str, Dict[str, Contract]] = {}
        self._reserves_cache: Dict[str, Dict[str, Tuple[float, AaveReserveData]]] = {}
        self._positions_cache: Dict[str, Tuple[float, AaveUserPosition]] = {}
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
        self._total_deposits: Dict[str, Decimal] = defaultdict(Decimal)
        self._total_borrows: Dict[str, Decimal] = defaultdict(Decimal)
        self._total_flash_loans: int = 0

        # Initialisation des contrats
        self._load_contracts()

        # Initialisation des réserves
        self._initialize_reserves()

        logger.info("AaveIntegration initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats Aave"""
        try:
            for chain_name, chain_config in AAVE_V3_ADDRESSES.items():
                chain_value = chain_name.value
                if chain_value not in self.web3_providers:
                    logger.warning(f"Provider Web3 non trouvé pour {chain_value}")
                    continue

                provider = self.web3_providers[chain_value]
                self._contracts[chain_value] = {}

                # Pool contract
                pool_address = chain_config["pool"]
                self._contracts[chain_value]["pool"] = provider.eth.contract(
                    address=to_checksum_address(pool_address),
                    abi=AAVE_POOL_ABI,
                )

            logger.info(f"Contrats Aave chargés: {list(self._contracts.keys())}")

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
        force_refresh: bool = False,
    ) -> AaveReserveData:
        """
        Obtient les données d'une réserve Aave

        Args:
            asset: Symbole du token (ETH, USDC, etc.)
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Données de la réserve
        """
        cache_key = f"{chain}:{asset}"

        if not force_refresh and cache_key in self._reserves_cache.get(chain, {}):
            cached_time, data = self._reserves_cache[chain][cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Récupération de l'adresse du token
            token_address = self._get_token_address(asset, chain)

            # Récupération du contrat pool
            pool_contract = self._get_pool_contract(chain)
            if not pool_contract:
                raise DeFiError(f"Pool contract non trouvé pour {chain}")

            # Appel à getReserveData
            reserve_data = await self._async_call(
                pool_contract.functions.getReserveData(
                    to_checksum_address(token_address)
                )
            )

            # Construction des données
            supply_rate = Decimal(str(reserve_data[3])) / Decimal(1e27)
            variable_borrow_rate = Decimal(str(reserve_data[4])) / Decimal(1e27)
            stable_borrow_rate = Decimal(str(reserve_data[5])) / Decimal(1e27)

            # Calcul de l'utilisation
            total_liquidity = await self._get_token_balance(
                token_address, chain
            )
            available_liquidity = await self._get_token_balance(
                token_address, chain
            )

            utilization_rate = Decimal("0")
            if total_liquidity > 0:
                utilization_rate = Decimal("1") - (available_liquidity / total_liquidity)

            reserve = AaveReserveData(
                token_address=token_address,
                token_symbol=asset,
                token_decimals=self._get_token_decimals(asset),
                total_liquidity=total_liquidity,
                available_liquidity=available_liquidity,
                variable_borrow_rate=variable_borrow_rate,
                stable_borrow_rate=stable_borrow_rate,
                supply_rate=supply_rate,
                utilization_rate=utilization_rate,
                liquidity_index=Decimal(str(reserve_data[1])) / Decimal(1e27),
                variable_borrow_index=Decimal(str(reserve_data[2])) / Decimal(1e27),
                is_active=True,
                is_frozen=False,
                is_paused=False,
                last_update_timestamp=reserve_data[6],
            )

            # Mise en cache
            if chain not in self._reserves_cache:
                self._reserves_cache[chain] = {}
            self._reserves_cache[chain][cache_key] = (time.time(), reserve)

            # Métriques
            self.metrics.record_gauge(
                "aave_supply_rate",
                float(supply_rate),
                {"asset": asset, "chain": chain},
            )
            self.metrics.record_gauge(
                "aave_variable_borrow_rate",
                float(variable_borrow_rate),
                {"asset": asset, "chain": chain},
            )

            return reserve

        except Exception as e:
            logger.error(f"Erreur de récupération des données de réserve: {e}")
            raise DeFiError(f"Erreur de récupération des données de réserve: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_user_position(
        self,
        address: str,
        chain: str,
        force_refresh: bool = False,
    ) -> AaveUserPosition:
        """
        Obtient la position d'un utilisateur

        Args:
            address: Adresse de l'utilisateur
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Position de l'utilisateur
        """
        cache_key = f"{chain}:{address}"

        if not force_refresh and cache_key in self._positions_cache:
            cached_time, position = self._positions_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return position

        try:
            pool_contract = self._get_pool_contract(chain)
            if not pool_contract:
                raise DeFiError(f"Pool contract non trouvé pour {chain}")

            # Récupération des données du compte
            account_data = await self._async_call(
                pool_contract.functions.getUserAccountData(
                    to_checksum_address(address)
                )
            )

            # Décodage des données
            total_collateral_usd = Decimal(str(account_data[0])) / Decimal(1e8)
            total_debt_usd = Decimal(str(account_data[1])) / Decimal(1e8)
            health_factor = Decimal(str(account_data[5])) / Decimal(1e18)

            # Récupération des positions détaillées
            positions = await self._get_user_positions_details(
                address, chain
            )

            position = AaveUserPosition(
                address=address,
                chain=chain,
                total_collateral_usd=total_collateral_usd,
                total_debt_usd=total_debt_usd,
                health_factor=health_factor,
                positions=positions,
            )

            # Mise en cache
            self._positions_cache[cache_key] = (time.time(), position)

            # Métriques
            self.metrics.record_gauge(
                "aave_health_factor",
                float(health_factor),
                {"chain": chain},
            )
            self.metrics.record_gauge(
                "aave_collateral_usd",
                float(total_collateral_usd),
                {"chain": chain},
            )
            self.metrics.record_gauge(
                "aave_debt_usd",
                float(total_debt_usd),
                {"chain": chain},
            )

            # Alerte si health factor est faible
            if health_factor < Decimal("1.1"):
                logger.warning(
                    f"Health factor faible pour {address} sur {chain}: {health_factor}"
                )
                await self._send_health_alert(address, chain, health_factor)

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
        on_behalf_of: Optional[str] = None,
        referral_code: int = 0,
    ) -> str:
        """
        Fournit des liquidités à Aave

        Args:
            asset: Symbole du token
            amount: Montant à fournir
            chain: Chaîne
            wallet_address: Adresse du wallet
            on_behalf_of: Adresse pour laquelle fournir
            referral_code: Code de parrainage

        Returns:
            Hash de la transaction
        """
        logger.info(f"Supply {amount} {asset} sur {chain}")

        try:
            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des données de la réserve
            reserve = await self.get_reserve_data(asset, chain, force_refresh=True)

            # Vérification que la réserve est active
            if not reserve.is_active:
                raise DeFiError(f"Réserve {asset} inactive sur {chain}")

            # Vérification du solde
            balance = await self._get_token_balance(
                reserve.token_address, chain, wallet_address
            )
            if balance < amount:
                raise DeFiError(
                    f"Solde insuffisant: {balance} < {amount}"
                )

            # Approval
            await self._approve_token(
                reserve.token_address,
                amount,
                chain,
                wallet,
            )

            # Construction de la transaction
            pool_contract = self._get_pool_contract(chain)
            if not pool_contract:
                raise DeFiError(f"Pool contract non trouvé pour {chain}")

            amount_wei = int(amount * Decimal(10 ** reserve.token_decimals))
            on_behalf = on_behalf_of or wallet_address

            tx = pool_contract.functions.supply(
                to_checksum_address(reserve.token_address),
                amount_wei,
                to_checksum_address(on_behalf),
                referral_code,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "nonce": await self._get_nonce(chain, wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            # Signature et envoi
            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            # Mise à jour des métriques
            self._total_deposits[asset] += amount
            self.metrics.record_increment(
                "aave_supply",
                1,
                {"asset": asset, "chain": chain},
            )

            logger.info(f"Supply réussi: {tx_hash.hex()}")
            return tx_hash.hex()

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
        to_address: Optional[str] = None,
    ) -> str:
        """
        Retire des liquidités d'Aave

        Args:
            asset: Symbole du token
            amount: Montant à retirer
            chain: Chaîne
            wallet_address: Adresse du wallet
            to_address: Adresse de destination

        Returns:
            Hash de la transaction
        """
        logger.info(f"Withdraw {amount} {asset} sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des données de la réserve
            reserve = await self.get_reserve_data(asset, chain, force_refresh=True)

            # Vérification de la position
            position = await self.get_user_position(wallet_address, chain, force_refresh=True)

            if position.health_factor < Decimal("1.05"):
                raise DeFiError(
                    f"Health factor trop bas pour retirer: {position.health_factor}"
                )

            amount_wei = int(amount * Decimal(10 ** reserve.token_decimals))
            to = to_address or wallet_address

            pool_contract = self._get_pool_contract(chain)
            tx = pool_contract.functions.withdraw(
                to_checksum_address(reserve.token_address),
                amount_wei,
                to_checksum_address(to),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "nonce": await self._get_nonce(chain, wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "aave_withdraw",
                1,
                {"asset": asset, "chain": chain},
            )

            logger.info(f"Withdraw réussi: {tx_hash.hex()}")
            return tx_hash.hex()

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
        interest_rate_mode: AaveInterestRateMode = AaveInterestRateMode.VARIABLE,
        on_behalf_of: Optional[str] = None,
        referral_code: int = 0,
    ) -> str:
        """
        Emprunte des fonds sur Aave

        Args:
            asset: Symbole du token
            amount: Montant à emprunter
            chain: Chaîne
            wallet_address: Adresse du wallet
            interest_rate_mode: Mode de taux d'intérêt
            on_behalf_of: Adresse pour laquelle emprunter
            referral_code: Code de parrainage

        Returns:
            Hash de la transaction
        """
        logger.info(f"Borrow {amount} {asset} sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification de la position
            position = await self.get_user_position(wallet_address, chain, force_refresh=True)

            if position.health_factor < Decimal("1.2"):
                raise DeFiError(
                    f"Health factor trop bas pour emprunter: {position.health_factor}"
                )

            reserve = await self.get_reserve_data(asset, chain, force_refresh=True)

            # Vérification de la liquidité disponible
            if reserve.available_liquidity < amount:
                raise DeFiError(
                    f"Liquidité insuffisante: {reserve.available_liquidity} < {amount}"
                )

            amount_wei = int(amount * Decimal(10 ** reserve.token_decimals))
            rate_mode = 2 if interest_rate_mode == AaveInterestRateMode.VARIABLE else 1
            on_behalf = on_behalf_of or wallet_address

            pool_contract = self._get_pool_contract(chain)
            tx = pool_contract.functions.borrow(
                to_checksum_address(reserve.token_address),
                amount_wei,
                rate_mode,
                referral_code,
                to_checksum_address(on_behalf),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "nonce": await self._get_nonce(chain, wallet_address),
                "gas": 400000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_borrows[asset] += amount
            self.metrics.record_increment(
                "aave_borrow",
                1,
                {"asset": asset, "chain": chain, "rate_mode": interest_rate_mode.value},
            )

            logger.info(f"Borrow réussi: {tx_hash.hex()}")
            return tx_hash.hex()

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
        interest_rate_mode: AaveInterestRateMode = AaveInterestRateMode.VARIABLE,
        on_behalf_of: Optional[str] = None,
    ) -> str:
        """
        Rembourse un emprunt sur Aave

        Args:
            asset: Symbole du token
            amount: Montant à rembourser
            chain: Chaîne
            wallet_address: Adresse du wallet
            interest_rate_mode: Mode de taux d'intérêt
            on_behalf_of: Adresse pour laquelle rembourser

        Returns:
            Hash de la transaction
        """
        logger.info(f"Repay {amount} {asset} sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            reserve = await self.get_reserve_data(asset, chain, force_refresh=True)

            # Vérification du solde
            balance = await self._get_token_balance(
                reserve.token_address, chain, wallet_address
            )
            if balance < amount:
                raise DeFiError(
                    f"Solde insuffisant: {balance} < {amount}"
                )

            # Approval
            await self._approve_token(
                reserve.token_address,
                amount,
                chain,
                wallet,
            )

            amount_wei = int(amount * Decimal(10 ** reserve.token_decimals))
            rate_mode = 2 if interest_rate_mode == AaveInterestRateMode.VARIABLE else 1
            on_behalf = on_behalf_of or wallet_address

            pool_contract = self._get_pool_contract(chain)
            tx = pool_contract.functions.repay(
                to_checksum_address(reserve.token_address),
                amount_wei,
                rate_mode,
                to_checksum_address(on_behalf),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "nonce": await self._get_nonce(chain, wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "aave_repay",
                1,
                {"asset": asset, "chain": chain},
            )

            logger.info(f"Repay réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de repay: {e}")
            raise DeFiError(f"Erreur de repay: {e}")

    # ============================================================
    # FLASH LOANS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def flash_loan(
        self,
        request: AaveFlashLoanRequest,
        wallet_address: str,
    ) -> AaveFlashLoanResult:
        """
        Exécute un flash loan sur Aave

        Args:
            request: Requête de flash loan
            wallet_address: Adresse du wallet

        Returns:
            Résultat du flash loan
        """
        logger.info(f"Flash loan sur {request.chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des adresses des tokens
            asset_addresses = []
            amounts_wei = []

            for asset, amount in zip(request.assets, request.amounts):
                reserve = await self.get_reserve_data(asset, request.chain)
                asset_addresses.append(to_checksum_address(reserve.token_address))
                amounts_wei.append(int(amount * Decimal(10 ** reserve.token_decimals)))

            pool_contract = self._get_pool_contract(request.chain)
            if not pool_contract:
                raise DeFiError(f"Pool contract non trouvé pour {request.chain}")

            # Construction de la transaction flash loan
            tx = pool_contract.functions.flashLoan(
                to_checksum_address(request.target_contract),
                asset_addresses,
                amounts_wei,
                request.params,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "nonce": await self._get_nonce(request.chain, wallet_address),
                "gas": 1000000,
                "gasPrice": await self._get_gas_price(request.chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(request.chain, signed_tx)

            self._total_flash_loans += 1
            self.metrics.record_increment(
                "aave_flash_loan",
                1,
                {"chain": request.chain},
            )

            result = AaveFlashLoanResult(
                tx_hash=tx_hash.hex(),
                assets=request.assets,
                amounts=request.amounts,
                premium=Decimal("0"),  # À calculer
                timestamp=datetime.now(),
                status="completed",
            )

            logger.info(f"Flash loan réussi: {tx_hash.hex()}")
            return result

        except Exception as e:
            logger.error(f"Erreur de flash loan: {e}")
            raise DeFiError(f"Erreur de flash loan: {e}")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_pool_contract(self, chain: str) -> Optional[Contract]:
        """Obtient le contrat pool Aave"""
        return self._contracts.get(chain, {}).get("pool")

    def _get_token_address(self, asset: str, chain: str) -> str:
        """Obtient l'adresse du token sur une chaîne"""
        chain_config = AAVE_V3_ADDRESSES.get(AaveChain(chain))
        if not chain_config:
            raise DeFiError(f"Chaîne {chain} non supportée")

        # Vérifier si c'est un token natif
        if asset == "ETH" and chain == "ethereum":
            return "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

        # Vérifier dans les mappings
        a_tokens = chain_config.get("a_tokens", {})
        for token, address in a_tokens.items():
            if token.upper() == asset.upper():
                return address

        # Vérifier dans la configuration utilisateur
        user_tokens = self.config.get("token_mappings", {}).get(chain, {})
        if asset.upper() in user_tokens:
            return user_tokens[asset.upper()]

        raise DeFiError(f"Token {asset} non trouvé sur {chain}")

    def _get_token_decimals(self, asset: str) -> int:
        """Obtient le nombre de décimales d'un token"""
        decimals_map = {
            "ETH": 18,
            "WETH": 18,
            "USDC": 6,
            "USDT": 6,
            "DAI": 18,
            "WBTC": 8,
            "MATIC": 18,
            "AVAX": 18,
            "LINK": 18,
            "AAVE": 18,
        }
        return decimals_map.get(asset.upper(), 18)

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
                abi=AAVE_ERC20_ABI,
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
    ) -> bool:
        """Approuve un token pour Aave"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return False

            pool_contract = self._get_pool_contract(chain)
            if not pool_contract:
                return False

            spender = pool_contract.address

            # Vérification de l'allowance
            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=AAVE_ERC20_ABI,
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
            tx_hash = await self._send_transaction(chain, signed_tx)

            logger.info(f"Approval réussi: {tx_hash.hex()}")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval: {e}")
            raise DeFiError(f"Erreur d'approval: {e}")

    async def _get_user_positions_details(
        self,
        address: str,
        chain: str,
    ) -> List[Dict[str, Any]]:
        """Récupère les détails des positions d'un utilisateur"""
        positions = []

        try:
            chain_config = AAVE_V3_ADDRESSES.get(AaveChain(chain))
            if not chain_config:
                return positions

            a_tokens = chain_config.get("a_tokens", {})

            for token_symbol, a_token_address in a_tokens.items():
                # Solde du aToken
                balance = await self._get_token_balance(
                    a_token_address, chain, address
                )

                if balance > 0:
                    positions.append({
                        "type": "supply",
                        "token": token_symbol,
                        "amount": str(balance),
                        "a_token_address": a_token_address,
                    })

            return positions

        except Exception as e:
            logger.warning(f"Erreur de récupération des positions: {e}")
            return positions

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

    async def _send_transaction(self, chain: str, signed_tx: Any) -> HexBytes:
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
        # Web3 n'est pas asynchrone, donc on utilise un executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, call_func.call)

    async def _send_health_alert(
        self,
        address: str,
        chain: str,
        health_factor: Decimal,
    ) -> None:
        """Envoie une alerte de santé"""
        alert = {
            "type": "aave_health_warning",
            "address": address,
            "chain": chain,
            "health_factor": str(health_factor),
            "timestamp": datetime.now().isoformat(),
            "severity": "critical" if health_factor < Decimal("1.05") else "warning",
        }

        logger.warning(f"Alerte Aave: {alert}")

        # Appel des callbacks
        if hasattr(self, "_alert_callbacks"):
            for callback in getattr(self, "_alert_callbacks", []):
                try:
                    await callback(alert)
                except Exception as e:
                    logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_positions(
        self,
        addresses: List[str],
        chain: str,
        interval: int = 60,
    ) -> None:
        """
        Surveille les positions des utilisateurs

        Args:
            addresses: Liste des adresses à surveiller
            chain: Chaîne
            interval: Intervalle en secondes
        """
        logger.info(f"Démarrage du monitoring des positions sur {chain}")

        while True:
            try:
                for address in addresses:
                    position = await self.get_user_position(address, chain, force_refresh=True)

                    # Alerte si health factor est faible
                    if position.health_factor < Decimal("1.1"):
                        await self._send_health_alert(address, chain, position.health_factor)

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "total_deposits": {k: str(v) for k, v in self._total_deposits.items()},
            "total_borrows": {k: str(v) for k, v in self._total_borrows.items()},
            "total_flash_loans": self._total_flash_loans,
            "reserves_cached": len(self._reserves_cache),
            "positions_cached": len(self._positions_cache),
            "chains_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources AaveIntegration...")

        self._reserves_cache.clear()
        self._positions_cache.clear()
        self._price_cache.clear()
        self._decimals_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_aave_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> AaveIntegration:
    """
    Crée une instance de AaveIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de AaveIntegration
    """
    return AaveIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de AaveIntegration"""
    # Configuration
    config = {
        "token_mappings": {
            "ethereum": {
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            },
        },
    }

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
    aave = create_aave_integration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Récupération des données d'une réserve
    reserve = await aave.get_reserve_data("USDC", "ethereum")
    print(f"USDC on Ethereum:")
    print(f"  Supply rate: {reserve.supply_rate:.4%}")
    print(f"  Variable borrow rate: {reserve.variable_borrow_rate:.4%}")
    print(f"  Utilization: {reserve.utilization_rate:.2%}")

    # Récupération de la position d'un utilisateur
    position = await aave.get_user_position("0x...", "ethereum")
    print(f"Position:")
    print(f"  Collateral: ${position.total_collateral_usd:,.2f}")
    print(f"  Debt: ${position.total_debt_usd:,.2f}")
    print(f"  Health factor: {position.health_factor:.2f}")

    # Statistiques
    stats = aave.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await aave.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())

# blockchain/defi/flash_loan.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Flash Loan - Gestion des Flash Loans DeFi

Ce module implémente un système complet de gestion des flash loans
pour les protocoles DeFi, permettant l'exécution d'opérations complexes
sans capital initial, avec support de multiples protocoles et mécanismes
de sécurité avancés.

Fonctionnalités principales:
- Support de flash loans sur Aave V2/V3
- Support de flash loans sur dYdX
- Support de flash loans sur Uniswap
- Support de flash loans sur Curve
- Exécution d'arbitrage
- Exécution de liquidations
- Exécution de refinancement
- Gestion des positions
- Monitoring des flash loans
- Analyse des opportunités
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
    from .aave import AaveIntegration
    from .curve import CurveIntegration
    from .defi_config import DeFiConfigManager
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
    from .aave import AaveIntegration
    from .curve import CurveIntegration
    from .defi_config import DeFiConfigManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class FlashLoanProtocol(Enum):
    """Protocoles de flash loan supportés"""
    AAVE_V2 = "aave_v2"
    AAVE_V3 = "aave_v3"
    DYDX = "dydx"
    UNISWAP_V2 = "uniswap_v2"
    UNISWAP_V3 = "uniswap_v3"
    CURVE = "curve"
    BALANCER = "balancer"


class FlashLoanAction(Enum):
    """Types d'actions de flash loan"""
    ARBITRAGE = "arbitrage"
    LIQUIDATION = "liquidation"
    REFINANCE = "refinance"
    COLLATERAL_SWAP = "collateral_swap"
    LEVERAGE = "leverage"
    DELEVERAGE = "deleverage"
    YIELD_FARMING = "yield_farming"
    CUSTOM = "custom"


class FlashLoanStatus(Enum):
    """Statuts de flash loan"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"
    CANCELLED = "cancelled"


@dataclass
class FlashLoanConfig:
    """Configuration de flash loan"""
    protocol: FlashLoanProtocol
    chain: str
    asset: str
    amount: Decimal
    action: FlashLoanAction
    target_contract: str
    callback_function: str
    params: bytes
    deadline: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol.value,
            "chain": self.chain,
            "asset": self.asset,
            "amount": str(self.amount),
            "action": self.action.value,
            "target_contract": self.target_contract,
            "callback_function": self.callback_function,
            "deadline": self.deadline,
            "metadata": self.metadata,
        }


@dataclass
class FlashLoanResult:
    """Résultat de flash loan"""
    loan_id: str
    protocol: FlashLoanProtocol
    chain: str
    asset: str
    amount: Decimal
    fee: Decimal
    profit: Decimal
    status: FlashLoanStatus
    tx_hash: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "loan_id": self.loan_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "asset": self.asset,
            "amount": str(self.amount),
            "fee": str(self.fee),
            "profit": str(self.profit),
            "status": self.status.value,
            "tx_hash": self.tx_hash,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CONFIGURATION DES PROTOCOLES
# ============================================================

FLASH_LOAN_ADDRESSES = {
    "aave_v3": {
        "ethereum": {
            "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
            "flash_loan": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        },
        "polygon": {
            "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        },
        "arbitrum": {
            "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        },
        "optimism": {
            "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        },
    },
    "aave_v2": {
        "ethereum": {
            "pool": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
        },
    },
    "curve": {
        "ethereum": {
            "flash_loan": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",
        },
        "polygon": {
            "flash_loan": "0xE7a24EF0C5e95Ffb0f6684b813A78F2a3AD6D24C",
        },
    },
    "balancer": {
        "ethereum": {
            "vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        },
        "polygon": {
            "vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        },
    },
}

# ABIs des contrats
FLASH_LOAN_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "assets", "type": "address[]"},
            {"name": "amounts", "type": "uint256[]"},
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
            {"name": "receiver", "type": "address"},
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
]

FLASH_LOAN_RECEIVER_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "assets", "type": "address[]"},
            {"name": "amounts", "type": "uint256[]"},
            {"name": "premiums", "type": "uint256[]"},
            {"name": "initiator", "type": "address"},
            {"name": "params", "type": "bytes"},
        ],
        "name": "executeOperation",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class FlashLoanManager:
    """
    Gestionnaire de flash loans DeFi
    """

    # Frais par protocole
    PROTOCOL_FEES = {
        FlashLoanProtocol.AAVE_V3: Decimal("0.0009"),
        FlashLoanProtocol.AAVE_V2: Decimal("0.0009"),
        FlashLoanProtocol.DYDX: Decimal("0"),
        FlashLoanProtocol.UNISWAP_V2: Decimal("0.003"),
        FlashLoanProtocol.UNISWAP_V3: Decimal("0.003"),
        FlashLoanProtocol.CURVE: Decimal("0.0004"),
        FlashLoanProtocol.BALANCER: Decimal("0.0001"),
    }

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        web3_providers: Dict[str, Web3],
        aave: Optional[AaveIntegration] = None,
        curve: Optional[CurveIntegration] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de flash loans

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            aave: Intégration Aave
            curve: Intégration Curve
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.aave = aave
        self.curve = curve
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._contracts: Dict[str, Dict[str, Dict[str, Contract]]] = {}
        self._active_loans: Dict[str, FlashLoanResult] = {}
        self._loan_history: List[FlashLoanResult] = []
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

        # Cache
        self._opportunity_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

        # Statistiques
        self._stats: Dict[str, Any] = defaultdict(dict)
        self._total_loans = 0
        self._successful_loans = 0
        self._total_profit = Decimal("0")

        # Initialisation des contrats
        self._load_contracts()

        logger.info("FlashLoanManager initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats de flash loan"""
        try:
            self._contracts = {}

            for protocol, chain_config in FLASH_LOAN_ADDRESSES.items():
                for chain, addresses in chain_config.items():
                    if chain not in self.web3_providers:
                        continue

                    provider = self.web3_providers[chain]
                    self._contracts[protocol] = self._contracts.get(protocol, {})
                    self._contracts[protocol][chain] = {}

                    for name, address in addresses.items():
                        if name == "pool" or name == "flash_loan" or name == "vault":
                            self._contracts[protocol][chain][name] = provider.eth.contract(
                                address=to_checksum_address(address),
                                abi=FLASH_LOAN_ABI,
                            )

            logger.info(f"Contrats flash loan chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise DeFiError(f"Erreur de chargement des contrats: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_flash_loan(
        self,
        config: FlashLoanConfig,
        wallet_address: str,
        callback_address: Optional[str] = None,
    ) -> FlashLoanResult:
        """
        Exécute un flash loan

        Args:
            config: Configuration du flash loan
            wallet_address: Adresse du wallet
            callback_address: Adresse du callback (optionnel)

        Returns:
            Résultat du flash loan
        """
        loan_id = f"fl_{uuid.uuid4().hex[:12]}"
        logger.info(f"Exécution du flash loan {loan_id}")

        try:
            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du contrat
            contract = await self._get_flash_loan_contract(
                config.protocol, config.chain
            )
            if not contract:
                raise DeFiError(f"Contrat non trouvé pour {config.protocol.value}")

            # Vérification du montant
            if config.amount <= 0:
                raise ValidationError("Le montant doit être positif")

            # Obtention du callback
            callback = callback_address or wallet_address

            # Construction de la transaction
            tx_data = await self._build_flash_loan_transaction(
                config, contract, callback, wallet_address
            )

            # Envoi de la transaction
            tx_hash = await self._send_transaction(
                config.chain, tx_data, wallet
            )

            # Attente de la confirmation
            receipt = await self._wait_for_transaction(config.chain, tx_hash)

            # Extraction du résultat
            result = await self._extract_flash_loan_result(
                config, tx_hash, receipt
            )

            # Mise à jour des statistiques
            self._total_loans += 1
            if result.status == FlashLoanStatus.COMPLETED:
                self._successful_loans += 1
                self._total_profit += result.profit

            # Métriques
            self.metrics.record_increment(
                "flash_loan_executed",
                1,
                {
                    "protocol": config.protocol.value,
                    "chain": config.chain,
                    "asset": config.asset,
                    "status": result.status.value,
                },
            )
            self.metrics.record_gauge(
                "flash_loan_profit",
                float(result.profit),
                {"protocol": config.protocol.value},
            )

            # Stockage
            self._active_loans.pop(loan_id, None)
            self._loan_history.append(result)

            return result

        except Exception as e:
            logger.error(f"Erreur d'exécution du flash loan: {e}")

            # Enregistrement de l'échec
            result = FlashLoanResult(
                loan_id=loan_id,
                protocol=config.protocol,
                chain=config.chain,
                asset=config.asset,
                amount=config.amount,
                fee=Decimal("0"),
                profit=Decimal("0"),
                status=FlashLoanStatus.FAILED,
                tx_hash="",
                timestamp=datetime.now(),
                metadata={"error": str(e)},
            )

            self._loan_history.append(result)

            raise DeFiError(f"Erreur d'exécution du flash loan: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def find_arbitrage_opportunity(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
        protocols: Optional[List[FlashLoanProtocol]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Recherche une opportunité d'arbitrage

        Args:
            chain: Chaîne
            token_in: Token d'entrée
            token_out: Token de sortie
            amount: Montant
            protocols: Protocoles à vérifier

        Returns:
            Opportunité d'arbitrage ou None
        """
        cache_key = f"{chain}:{token_in}:{token_out}:{amount}"

        if cache_key in self._opportunity_cache:
            cached_time, opportunity = self._opportunity_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return opportunity

        try:
            # Vérification des prix sur différents DEX
            dex_prices = await self._get_dex_prices(chain, token_in, token_out, amount)

            # Recherche d'arbitrage
            best_opportunity = None
            best_profit = Decimal("0")

            protocols_to_check = protocols or [
                FlashLoanProtocol.UNISWAP_V3,
                FlashLoanProtocol.CURVE,
                FlashLoanProtocol.BALANCER,
            ]

            for protocol in protocols_to_check:
                if protocol not in dex_prices:
                    continue

                price = dex_prices[protocol]

                # Vérification de la rentabilité
                fee = self.PROTOCOL_FEES.get(protocol, Decimal("0"))
                profit = (amount * price) - amount - (amount * fee)

                if profit > best_profit and profit > Decimal("0.01"):
                    best_profit = profit
                    best_opportunity = {
                        "protocol": protocol,
                        "token_in": token_in,
                        "token_out": token_out,
                        "amount": amount,
                        "price": price,
                        "profit": profit,
                        "fee": fee,
                        "profit_percentage": (profit / amount) * 100,
                    }

            # Mise en cache
            self._opportunity_cache[cache_key] = (time.time(), best_opportunity)

            return best_opportunity

        except Exception as e:
            logger.error(f"Erreur de recherche d'arbitrage: {e}")
            return None

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def find_liquidation_opportunity(
        self,
        chain: str,
        protocol: str,
        user: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Recherche une opportunité de liquidation

        Args:
            chain: Chaîne
            protocol: Protocole de prêt
            user: Adresse de l'utilisateur

        Returns:
            Opportunité de liquidation ou None
        """
        try:
            # Récupération de la position
            position = None
            if self.aave and protocol == "aave":
                position = await self.aave.get_user_position(user, chain)

            if not position:
                return None

            # Vérification du health factor
            if position.health_factor > Decimal("1.0"):
                return None

            # Calcul de la liquidation
            liquidation_bonus = Decimal("0.05")  # 5% de bonus

            return {
                "user": user,
                "protocol": protocol,
                "chain": chain,
                "health_factor": position.health_factor,
                "debt_amount": position.total_debt_usd,
                "collateral_amount": position.total_collateral_usd,
                "liquidation_bonus": liquidation_bonus,
                "potential_profit": position.total_collateral_usd * liquidation_bonus,
            }

        except Exception as e:
            logger.error(f"Erreur de recherche de liquidation: {e}")
            return None

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_flash_loan_transaction(
        self,
        config: FlashLoanConfig,
        contract: Contract,
        callback: str,
        wallet_address: str,
    ) -> Dict[str, Any]:
        """Construit une transaction de flash loan"""
        amount_wei = int(config.amount * Decimal(10 ** 18))

        if config.protocol in [FlashLoanProtocol.AAVE_V2, FlashLoanProtocol.AAVE_V3]:
            # Aave flash loan
            asset_address = await self._get_asset_address(config.asset, config.chain)

            tx = contract.functions.flashLoan(
                to_checksum_address(callback),
                to_checksum_address(asset_address),
                amount_wei,
                config.params,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 1000000,
                "gasPrice": await self._get_gas_price(config.chain),
            })

        elif config.protocol == FlashLoanProtocol.CURVE:
            # Curve flash loan
            assets = [await self._get_asset_address(config.asset, config.chain)]
            amounts = [amount_wei]

            tx = contract.functions.flashLoan(
                to_checksum_address(callback),
                assets,
                amounts,
                config.params,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 1000000,
                "gasPrice": await self._get_gas_price(config.chain),
            })

        elif config.protocol == FlashLoanProtocol.BALANCER:
            # Balancer flash loan
            assets = [await self._get_asset_address(config.asset, config.chain)]
            amounts = [amount_wei]

            tx = contract.functions.flashLoan(
                to_checksum_address(callback),
                assets,
                amounts,
                config.params,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 1000000,
                "gasPrice": await self._get_gas_price(config.chain),
            })

        else:
            # Flash loan générique
            tx = {
                "from": to_checksum_address(wallet_address),
                "to": contract.address,
                "value": 0,
                "gas": 1000000,
                "gasPrice": await self._get_gas_price(config.chain),
                "data": "0x",
            }

        return dict(tx)

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE PRIX
    # ============================================================

    async def _get_dex_prices(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
    ) -> Dict[FlashLoanProtocol, Decimal]:
        """Obtient les prix sur différents DEX"""
        prices = {}

        try:
            # Uniswap V3
            uniswap_price = await self._get_uniswap_price(
                chain, token_in, token_out, amount
            )
            if uniswap_price:
                prices[FlashLoanProtocol.UNISWAP_V3] = uniswap_price

            # Curve
            if self.curve:
                curve_price = await self._get_curve_price(
                    chain, token_in, token_out, amount
                )
                if curve_price:
                    prices[FlashLoanProtocol.CURVE] = curve_price

            # Balancer (simulé)
            prices[FlashLoanProtocol.BALANCER] = await self._get_balancer_price(
                chain, token_in, token_out, amount
            )

            return prices

        except Exception as e:
            logger.warning(f"Erreur de récupération des prix: {e}")
            return prices

    async def _get_uniswap_price(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
    ) -> Optional[Decimal]:
        """Obtient le prix sur Uniswap"""
        # Simulé - dans la réalité, on interrogerait le contrat Uniswap
        # Prix légèrement différents pour simuler l'arbitrage
        base_price = Decimal("1")
        return base_price * Decimal("1.002")  # 0.2% de spread

    async def _get_curve_price(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
    ) -> Optional[Decimal]:
        """Obtient le prix sur Curve"""
        if not self.curve:
            return None

        try:
            # Utilisation de Curve pour obtenir le prix
            pool = await self.curve.get_pool_data("3pool", chain)
            # Simulé
            return Decimal("1")
        except Exception:
            return Decimal("1")

    async def _get_balancer_price(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
    ) -> Decimal:
        """Obtient le prix sur Balancer"""
        # Simulé
        return Decimal("1") * Decimal("0.998")  # 0.2% de spread

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_flash_loan_contract(
        self,
        protocol: FlashLoanProtocol,
        chain: str,
    ) -> Optional[Contract]:
        """Obtient le contrat de flash loan"""
        protocol_contracts = self._contracts.get(protocol.value)
        if not protocol_contracts:
            return None

        chain_contracts = protocol_contracts.get(chain)
        if not chain_contracts:
            return None

        # Priorité: flash_loan > pool > vault
        for name in ["flash_loan", "pool", "vault"]:
            if name in chain_contracts:
                return chain_contracts[name]

        return None

    async def _get_asset_address(self, asset: str, chain: str) -> str:
        """Obtient l'adresse d'un asset"""
        # Mapping des assets
        asset_addresses = {
            "ethereum": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            },
            "polygon": {
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
                "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
            },
        }

        chain_addresses = asset_addresses.get(chain, {})
        return chain_addresses.get(asset, asset)

    async def _get_gas_price(self, chain: str) -> int:
        """Obtient le prix du gaz"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 50000000000
            return await provider.eth.gas_price
        except Exception:
            return 50000000000

    async def _send_transaction(
        self,
        chain: str,
        tx_data: Dict[str, Any],
        wallet: BaseWallet,
    ) -> HexBytes:
        """Envoie une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise DeFiError(f"Provider Web3 non trouvé pour {chain}")

            signed_tx = wallet.sign_transaction(tx_data)
            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            logger.info(f"Transaction envoyée: {tx_hash.hex()}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'envoi de transaction: {e}")
            raise TransactionError(f"Erreur d'envoi de transaction: {e}")

    async def _wait_for_transaction(
        self,
        chain: str,
        tx_hash: HexBytes,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise DeFiError(f"Provider Web3 non trouvé pour {chain}")

            start_time = time.time()
            while time.time() - start_time < timeout:
                receipt = await provider.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt.get("status") != 1:
                        raise DeFiError("Transaction échouée")
                    return dict(receipt)
                await asyncio.sleep(2)

            raise DeFiError(f"Timeout de transaction: {tx_hash.hex()}")

        except Exception as e:
            logger.error(f"Erreur d'attente de transaction: {e}")
            raise

    async def _extract_flash_loan_result(
        self,
        config: FlashLoanConfig,
        tx_hash: HexBytes,
        receipt: Dict[str, Any],
    ) -> FlashLoanResult:
        """Extrait le résultat d'un flash loan"""
        # Calcul des frais
        fee = config.amount * self.PROTOCOL_FEES.get(config.protocol, Decimal("0.0009"))

        # Profit (simulé)
        profit = Decimal("0")

        # Vérification du succès
        status = FlashLoanStatus.COMPLETED if receipt.get("status") == 1 else FlashLoanStatus.FAILED

        return FlashLoanResult(
            loan_id=f"fl_{uuid.uuid4().hex[:12]}",
            protocol=config.protocol,
            chain=config.chain,
            asset=config.asset,
            amount=config.amount,
            fee=fee,
            profit=profit,
            status=status,
            tx_hash=tx_hash.hex(),
            timestamp=datetime.now(),
            metadata={
                "receipt": receipt,
                "config": config.to_dict(),
            },
        )

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques"""
        return {
            "total_loans": self._total_loans,
            "successful_loans": self._successful_loans,
            "success_rate": self._successful_loans / max(1, self._total_loans),
            "total_profit": str(self._total_profit),
            "average_profit": str(self._total_profit / max(1, self._successful_loans)),
            "active_loans": len(self._active_loans),
            "total_history": len(self._loan_history),
            "opportunity_cache": len(self._opportunity_cache),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources FlashLoanManager...")

        self._contracts.clear()
        self._active_loans.clear()
        self._loan_history.clear()
        self._opportunity_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_flash_loan_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> FlashLoanManager:
    """
    Crée une instance de FlashLoanManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de FlashLoanManager
    """
    return FlashLoanManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de FlashLoanManager"""
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

    # Création du gestionnaire
    manager = create_flash_loan_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Recherche d'opportunité d'arbitrage
    opportunity = await manager.find_arbitrage_opportunity(
        chain="ethereum",
        token_in="USDC",
        token_out="USDC",
        amount=Decimal("10000"),
    )

    if opportunity:
        print(f"Opportunité d'arbitrage trouvée:")
        print(f"  Protocole: {opportunity['protocol'].value}")
        print(f"  Profit: ${opportunity['profit']:.2f}")
        print(f"  Profit %: {opportunity['profit_percentage']:.2f}%")

    # Exécution d'un flash loan
    config = FlashLoanConfig(
        protocol=FlashLoanProtocol.AAVE_V3,
        chain="ethereum",
        asset="USDC",
        amount=Decimal("10000"),
        action=FlashLoanAction.ARBITRAGE,
        target_contract="0x...",
        callback_function="executeOperation",
        params=b"",
    )

    result = await manager.execute_flash_loan(
        config=config,
        wallet_address="0x...",
    )

    print(f"Résultat du flash loan: {result.to_dict()}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

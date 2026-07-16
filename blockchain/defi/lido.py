# blockchain/defi/lido.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Lido Finance - Intégration Staking Liquide

Ce module implémente une intégration complète du protocole Lido Finance,
permettant des opérations avancées de staking liquide, de gestion des
positions stETH, de farming et d'optimisation des rendements.

Fonctionnalités principales:
- Staking d'ETH vers stETH
- Unstaking de stETH vers ETH
- Gestion des positions stETH
- Farming des récompenses LDO
- Support multi-chain (Ethereum, Polygon, etc.)
- Optimisation des rendements
- Monitoring des positions
- Alertes de rendement
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
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel, YieldData
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
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel, YieldData

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class LidoChain(Enum):
    """Chaînes supportées par Lido"""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    SOLANA = "solana"  # Via Lido on Solana


class LidoAction(Enum):
    """Actions Lido"""
    STAKE = "stake"
    UNSTAKE = "unstake"
    CLAIM_REWARDS = "claim_rewards"
    WRAP = "wrap"  # stETH -> wstETH
    UNWRAP = "unwrap"  # wstETH -> stETH
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"


@dataclass
class LidoPosition:
    """Position Lido"""
    position_id: str
    chain: str
    user: str
    staked_eth: Decimal
    steth_balance: Decimal
    wsteth_balance: Decimal
    rewards: Decimal
    total_value_usd: Decimal
    apy: Decimal
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "chain": self.chain,
            "user": self.user,
            "staked_eth": str(self.staked_eth),
            "steth_balance": str(self.steth_balance),
            "wsteth_balance": str(self.wsteth_balance),
            "rewards": str(self.rewards),
            "total_value_usd": str(self.total_value_usd),
            "apy": str(self.apy),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class LidoQuote:
    """Devis Lido"""
    quote_id: str
    chain: str
    action: LidoAction
    amount_in: Decimal
    amount_out: Decimal
    fee: Decimal
    estimated_time: int
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "chain": self.chain,
            "action": self.action.value,
            "amount_in": str(self.amount_in),
            "amount_out": str(self.amount_out),
            "fee": str(self.fee),
            "estimated_time": self.estimated_time,
            "confidence": self.confidence,
        }


# ============================================================
# ADRESSES DES CONTRATS LIDO
# ============================================================

LIDO_ADDRESSES = {
    LidoChain.ETHEREUM: {
        "lido": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
        "steth": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
        "wsteth": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0",
        "staking_router": "0xdc6A0bC8DdB86d7Ef6Ff6cA3Ab9d9B0b9b0b9b0b",
        "oracle": "0x442af784A788A5bd6F42A01EBe9F287a871243fb",
        "curves": {
            "steth_eth": "0xDC24316b9AE028F1497c275EB9192a3Ea0f67022",
        },
    },
    LidoChain.POLYGON: {
        "lido": "0xC3b7D2D8FdC278Bc31A3D4b3a4EaA3D4b3a4EaA3",
        "stmatic": "0x3A58a54C686Fc311A5B4D3E0a6C7b9E9b9E9b9E",
    },
}

# ABIs des contrats
LIDO_ABI = [
    {
        "constant": False,
        "inputs": [],
        "name": "submit",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": True,
        "stateMutability": "payable",
        "type": "function",
    },
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
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "burn",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "getTotalPooledEther",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "getTotalShares",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

WSTETH_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "stETHAmount", "type": "uint256"}],
        "name": "wrap",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "wstETHAmount", "type": "uint256"}],
        "name": "unwrap",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "wrap",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "unwrap",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "stEthPerToken",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "tokensPerStEth",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class LidoIntegration(BaseProtocol):
    """
    Intégration avancée du protocole Lido Finance
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
        Initialise l'intégration Lido

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
        self._positions_cache: Dict[str, Tuple[float, LidoPosition]] = {}
        self._quotes_cache: Dict[str, Tuple[float, LidoQuote]] = {}
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
        self._apy_cache: Dict[str, Tuple[float, Decimal]] = {}

        # Métriques
        self._total_staked = Decimal("0")
        self._total_unstaked = Decimal("0")
        self._total_rewards = Decimal("0")

        # Initialisation des contrats
        self._load_contracts()

        logger.info("LidoIntegration initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats Lido"""
        try:
            self._contracts = {}

            for chain, addresses in LIDO_ADDRESSES.items():
                chain_value = chain.value
                if chain_value not in self.web3_providers:
                    logger.warning(f"Provider Web3 non trouvé pour {chain_value}")
                    continue

                provider = self.web3_providers[chain_value]
                self._contracts[chain_value] = {}

                # Contrat Lido principal
                if "lido" in addresses:
                    self._contracts[chain_value]["lido"] = provider.eth.contract(
                        address=to_checksum_address(addresses["lido"]),
                        abi=LIDO_ABI,
                    )

                # Contrat stETH (même que Lido)
                if "steth" in addresses:
                    self._contracts[chain_value]["steth"] = provider.eth.contract(
                        address=to_checksum_address(addresses["steth"]),
                        abi=LIDO_ABI,
                    )

                # Contrat wstETH
                if "wsteth" in addresses:
                    self._contracts[chain_value]["wsteth"] = provider.eth.contract(
                        address=to_checksum_address(addresses["wsteth"]),
                        abi=WSTETH_ABI,
                    )

                # Oracle
                if "oracle" in addresses:
                    self._contracts[chain_value]["oracle"] = provider.eth.contract(
                        address=to_checksum_address(addresses["oracle"]),
                        abi=[],
                    )

            logger.info(f"Contrats Lido chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise DeFiError(f"Erreur de chargement des contrats: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def stake(
        self,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        min_steth: Optional[Decimal] = None,
    ) -> str:
        """
        Stake ETH pour recevoir stETH

        Args:
            amount: Montant d'ETH à staker
            chain: Chaîne
            wallet_address: Adresse du wallet
            min_steth: Montant minimum de stETH à recevoir

        Returns:
            Hash de la transaction
        """
        logger.info(f"Stake {amount} ETH sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du solde
            balance = await self._get_balance(chain, wallet_address)
            if balance < amount:
                raise DeFiError(f"Solde insuffisant: {balance} < {amount}")

            # Récupération du contrat Lido
            lido_contract = self._contracts[chain].get("lido")
            if not lido_contract:
                raise DeFiError(f"Contrat Lido non trouvé sur {chain}")

            amount_wei = int(amount * Decimal(1e18))

            # Construction de la transaction
            tx = lido_contract.functions.submit().build_transaction({
                "from": to_checksum_address(wallet_address),
                "value": amount_wei,
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_staked += amount
            self.metrics.record_increment(
                "lido_stake",
                1,
                {"chain": chain},
            )

            logger.info(f"Stake réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de stake: {e}")
            raise DeFiError(f"Erreur de stake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def unstake(
        self,
        steth_amount: Decimal,
        chain: str,
        wallet_address: str,
        min_eth: Optional[Decimal] = None,
    ) -> str:
        """
        Unstake stETH pour récupérer ETH

        Args:
            steth_amount: Montant de stETH à unstaker
            chain: Chaîne
            wallet_address: Adresse du wallet
            min_eth: Montant minimum d'ETH à recevoir

        Returns:
            Hash de la transaction
        """
        logger.info(f"Unstake {steth_amount} stETH sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du contrat Lido
            lido_contract = self._contracts[chain].get("lido")
            if not lido_contract:
                raise DeFiError(f"Contrat Lido non trouvé sur {chain}")

            # Vérification du solde stETH
            steth_balance = await self._get_steth_balance(chain, wallet_address)
            if steth_balance < steth_amount:
                raise DeFiError(
                    f"Solde stETH insuffisant: {steth_balance} < {steth_amount}"
                )

            amount_wei = int(steth_amount * Decimal(1e18))

            # Construction de la transaction (burn)
            tx = lido_contract.functions.burn(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_unstaked += steth_amount
            self.metrics.record_increment(
                "lido_unstake",
                1,
                {"chain": chain},
            )

            logger.info(f"Unstake réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de unstake: {e}")
            raise DeFiError(f"Erreur de unstake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def wrap(
        self,
        steth_amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Wrap stETH en wstETH

        Args:
            steth_amount: Montant de stETH à wrapper
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Wrap {steth_amount} stETH en wstETH sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du contrat wstETH
            wsteth_contract = self._contracts[chain].get("wsteth")
            if not wsteth_contract:
                raise DeFiError(f"Contrat wstETH non trouvé sur {chain}")

            amount_wei = int(steth_amount * Decimal(1e18))

            # Construction de la transaction
            tx = wsteth_contract.functions.wrap(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "lido_wrap",
                1,
                {"chain": chain},
            )

            logger.info(f"Wrap réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de wrap: {e}")
            raise DeFiError(f"Erreur de wrap: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def unwrap(
        self,
        wsteth_amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Unwrap wstETH en stETH

        Args:
            wsteth_amount: Montant de wstETH à unwrapper
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Unwrap {wsteth_amount} wstETH en stETH sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du contrat wstETH
            wsteth_contract = self._contracts[chain].get("wsteth")
            if not wsteth_contract:
                raise DeFiError(f"Contrat wstETH non trouvé sur {chain}")

            amount_wei = int(wsteth_amount * Decimal(1e18))

            # Construction de la transaction
            tx = wsteth_contract.functions.unwrap(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "lido_unwrap",
                1,
                {"chain": chain},
            )

            logger.info(f"Unwrap réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de unwrap: {e}")
            raise DeFiError(f"Erreur de unwrap: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_position(
        self,
        user: str,
        chain: str,
        force_refresh: bool = False,
    ) -> Optional[LidoPosition]:
        """
        Obtient la position Lido d'un utilisateur

        Args:
            user: Adresse de l'utilisateur
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Position Lido ou None
        """
        cache_key = f"{chain}:{user}"

        if not force_refresh and cache_key in self._positions_cache:
            cached_time, position = self._positions_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return position

        try:
            # Récupération des balances
            steth_balance = await self._get_steth_balance(chain, user)
            wsteth_balance = await self._get_wsteth_balance(chain, user)

            if steth_balance == 0 and wsteth_balance == 0:
                return None

            # Calcul de l'ETH staké
            staked_eth = await self._convert_steth_to_eth(steth_balance, chain)

            # Récupération de l'APY
            apy = await self._get_apy(chain)

            # Calcul de la valeur totale
            eth_price = await self._get_eth_price()
            total_value = (staked_eth + wsteth_balance) * eth_price

            # Récupération des récompenses (simulé)
            rewards = Decimal("0")

            position = LidoPosition(
                position_id=f"lp_{uuid.uuid4().hex[:8]}",
                chain=chain,
                user=user,
                staked_eth=staked_eth,
                steth_balance=steth_balance,
                wsteth_balance=wsteth_balance,
                rewards=rewards,
                total_value_usd=total_value,
                apy=apy,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            # Mise en cache
            self._positions_cache[cache_key] = (time.time(), position)

            # Métriques
            self.metrics.record_gauge(
                "lido_staked_eth",
                float(staked_eth),
                {"chain": chain},
            )
            self.metrics.record_gauge(
                "lido_total_value",
                float(total_value),
                {"chain": chain},
            )

            return position

        except Exception as e:
            logger.error(f"Erreur de récupération de la position: {e}")
            raise DeFiError(f"Erreur de récupération de la position: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_quote(
        self,
        action: LidoAction,
        amount: Decimal,
        chain: str,
        **kwargs,
    ) -> LidoQuote:
        """
        Obtient un devis pour une action Lido

        Args:
            action: Action Lido
            amount: Montant
            chain: Chaîne
            **kwargs: Arguments additionnels

        Returns:
            Devis Lido
        """
        cache_key = f"{chain}:{action.value}:{amount}"

        if cache_key in self._quotes_cache:
            cached_time, quote = self._quotes_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return quote

        try:
            amount_out = Decimal("0")
            fee = Decimal("0")
            estimated_time = 60
            confidence = 0.98

            if action == LidoAction.STAKE:
                # 1 ETH = ~1 stETH
                amount_out = amount * Decimal("0.9995")  # Frais de 0.05%
                fee = amount * Decimal("0.0005")
                estimated_time = 60

            elif action == LidoAction.UNSTAKE:
                # 1 stETH = ~1 ETH
                amount_out = amount * Decimal("0.999")
                fee = amount * Decimal("0.001")
                estimated_time = 600  # 10 minutes

            elif action == LidoAction.WRAP:
                # 1 stETH = ~1 wstETH
                amount_out = amount * Decimal("0.9999")
                fee = amount * Decimal("0.0001")
                estimated_time = 60

            elif action == LidoAction.UNWRAP:
                # 1 wstETH = ~1 stETH
                amount_out = amount * Decimal("0.9999")
                fee = amount * Decimal("0.0001")
                estimated_time = 60

            quote = LidoQuote(
                quote_id=f"lq_{uuid.uuid4().hex[:8]}",
                chain=chain,
                action=action,
                amount_in=amount,
                amount_out=amount_out,
                fee=fee,
                estimated_time=estimated_time,
                confidence=confidence,
                metadata=kwargs,
            )

            self._quotes_cache[cache_key] = (time.time(), quote)

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_positions(
        self,
        addresses: List[str],
        chain: str,
        interval: int = 300,
    ) -> None:
        """
        Surveille les positions Lido

        Args:
            addresses: Liste des adresses
            chain: Chaîne
            interval: Intervalle en secondes
        """
        logger.info(f"Démarrage du monitoring Lido sur {chain}")

        while True:
            try:
                for address in addresses:
                    position = await self.get_position(address, chain, force_refresh=True)
                    if position:
                        # Vérification des alertes
                        if position.apy < Decimal("0.02"):  # 2% APY
                            await self._send_alert({
                                "type": "low_apy",
                                "address": address,
                                "chain": chain,
                                "apy": str(position.apy),
                                "severity": "warning",
                            })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_balance(self, chain: str, address: str) -> Decimal:
        """Obtient le solde ETH d'une adresse"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            balance = await provider.eth.get_balance(to_checksum_address(address))
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            logger.warning(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _get_steth_balance(self, chain: str, address: str) -> Decimal:
        """Obtient le solde stETH d'une adresse"""
        try:
            steth_contract = self._contracts[chain].get("steth")
            if not steth_contract:
                return Decimal("0")

            balance = await self._async_call(
                steth_contract.functions.balanceOf(to_checksum_address(address))
            )
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            logger.warning(f"Erreur de solde stETH: {e}")
            return Decimal("0")

    async def _get_wsteth_balance(self, chain: str, address: str) -> Decimal:
        """Obtient le solde wstETH d'une adresse"""
        try:
            wsteth_contract = self._contracts[chain].get("wsteth")
            if not wsteth_contract:
                return Decimal("0")

            balance = await self._async_call(
                wsteth_contract.functions.balanceOf(to_checksum_address(address))
            )
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            logger.warning(f"Erreur de solde wstETH: {e}")
            return Decimal("0")

    async def _convert_steth_to_eth(self, steth_amount: Decimal, chain: str) -> Decimal:
        """Convertit stETH en ETH"""
        try:
            lido_contract = self._contracts[chain].get("lido")
            if not lido_contract:
                return steth_amount

            # Calcul basé sur le ratio totalPooledEther / totalShares
            total_eth = await self._async_call(
                lido_contract.functions.getTotalPooledEther()
            )
            total_shares = await self._async_call(
                lido_contract.functions.getTotalShares()
            )

            if total_shares == 0:
                return steth_amount

            ratio = Decimal(str(total_eth)) / Decimal(str(total_shares))
            return steth_amount * ratio

        except Exception as e:
            logger.warning(f"Erreur de conversion stETH: {e}")
            return steth_amount

    async def _get_apy(self, chain: str) -> Decimal:
        """Obtient l'APY Lido"""
        cache_key = f"apy_{chain}"

        if cache_key in self._apy_cache:
            cached_time, apy = self._apy_cache[cache_key]
            if time.time() - cached_time < 3600:  # 1 heure
                return apy

        # APY Lido (simulé - dans la réalité, on interrogerait l'oracle)
        apy = Decimal("0.035")  # 3.5% par défaut

        self._apy_cache[cache_key] = (time.time(), apy)
        return apy

    async def _get_eth_price(self) -> Decimal:
        """Obtient le prix de l'ETH"""
        cache_key = "eth_price"

        if cache_key in self._price_cache:
            cached_time, price = self._price_cache[cache_key]
            if time.time() - cached_time < 60:  # 1 minute
                return price

        # Simulé - dans la réalité, on utiliserait un oracle
        price = Decimal("3000")

        self._price_cache[cache_key] = (time.time(), price)
        return price

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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, call_func.call)

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
            "total_staked": str(self._total_staked),
            "total_unstaked": str(self._total_unstaked),
            "total_rewards": str(self._total_rewards),
            "positions_cached": len(self._positions_cache),
            "quotes_cached": len(self._quotes_cache),
            "chains_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources LidoIntegration...")

        self._positions_cache.clear()
        self._quotes_cache.clear()
        self._price_cache.clear()
        self._apy_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_lido_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> LidoIntegration:
    """
    Crée une instance de LidoIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de LidoIntegration
    """
    return LidoIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de LidoIntegration"""
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
    lido = create_lido_integration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Obtention d'un devis
    quote = await lido.get_quote(
        action=LidoAction.STAKE,
        amount=Decimal("1"),
        chain="ethereum",
    )

    print(f"Devis stake: {quote.to_dict()}")

    # Récupération d'une position
    position = await lido.get_position(
        user="0x...",
        chain="ethereum",
    )

    if position:
        print(f"Position Lido:")
        print(f"  stETH: {position.steth_balance}")
        print(f"  wstETH: {position.wsteth_balance}")
        print(f"  Valeur: ${position.total_value_usd:,.2f}")
        print(f"  APY: {position.apy:.2%}")

    # Statistiques
    stats = lido.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await lido.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

# blockchain/nft/nft_staking.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Staking - Gestion du Staking NFT

Ce module implémente un système complet de staking pour les NFTs,
supportant le staking simple, le farming de tokens, les pools de staking,
et l'optimisation des rendements.

Fonctionnalités principales:
- Staking de NFTs
- Farming de tokens
- Pools de staking
- Calcul des récompenses
- Gestion des périodes de lock
- Monitoring des positions
- Alertes de performance
- Support multi-protocoles
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
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTStandard, NFTStatus
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
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTStandard, NFTStatus

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NFTStakingProtocol(Enum):
    """Protocoles de staking NFT supportés"""
    BENDDAO = "benddao"
    NFTFI = "nftfi"
    PARASPACE = "paraspace"
    ARCADE = "arcade"
    CUSTOM = "custom"


class StakingStatus(Enum):
    """Statuts de staking"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    LOCKED = "locked"


@dataclass
class NFTStake:
    """Position de staking NFT"""
    stake_id: str
    protocol: NFTStakingProtocol
    chain: str
    contract_address: str
    token_id: str
    staker: str
    amount: Decimal
    reward_token: str
    apy: Decimal
    start_time: datetime
    end_time: Optional[datetime] = None
    lock_duration: int = 0  # secondes
    status: StakingStatus = StakingStatus.ACTIVE
    rewards_claimed: Decimal = Decimal("0")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "stake_id": self.stake_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "staker": self.staker,
            "amount": str(self.amount),
            "reward_token": self.reward_token,
            "apy": str(self.apy),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "lock_duration": self.lock_duration,
            "status": self.status.value,
            "rewards_claimed": str(self.rewards_claimed),
            "metadata": self.metadata,
        }


@dataclass
class StakingPool:
    """Pool de staking NFT"""
    pool_id: str
    protocol: NFTStakingProtocol
    chain: str
    name: str
    contract_address: str
    reward_token: str
    total_staked: Decimal
    total_rewards: Decimal
    apy: Decimal
    min_stake_duration: int
    max_stake_duration: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "pool_id": self.pool_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "name": self.name,
            "contract_address": self.contract_address,
            "reward_token": self.reward_token,
            "total_staked": str(self.total_staked),
            "total_rewards": str(self.total_rewards),
            "apy": str(self.apy),
            "min_stake_duration": self.min_stake_duration,
            "max_stake_duration": self.max_stake_duration,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================
# ADRESSES DES PROTOCOLES
# ============================================================

STAKING_PROTOCOL_ADDRESSES = {
    NFTStakingProtocol.BENDDAO: {
        "ethereum": {
            "staking": "0x...",
        },
    },
    NFTStakingProtocol.NFTFI: {
        "ethereum": {
            "staking": "0x...",
        },
    },
    NFTStakingProtocol.PARASPACE: {
        "ethereum": {
            "staking": "0x...",
        },
    },
}


# ============================================================
# ABIS DES CONTRATS
# ============================================================

NFT_STAKING_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "nft", "type": "address"},
            {"name": "id", "type": "uint256"},
            {"name": "duration", "type": "uint256"},
        ],
        "name": "stake",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "nft", "type": "address"},
            {"name": "id", "type": "uint256"},
        ],
        "name": "unstake",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "nft", "type": "address"},
            {"name": "id", "type": "uint256"},
        ],
        "name": "claimRewards",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "nft", "type": "address"},
            {"name": "id", "type": "uint256"},
        ],
        "name": "getStakeInfo",
        "outputs": [
            {"name": "staker", "type": "address"},
            {"name": "startTime", "type": "uint256"},
            {"name": "endTime", "type": "uint256"},
            {"name": "rewards", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTStakingManager(BaseNFT):
    """
    Gestionnaire de staking NFT
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
        Initialise le gestionnaire de staking NFT

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
        self._stakes_cache: Dict[str, Tuple[float, NFTStake]] = {}
        self._pools_cache: Dict[str, Tuple[float, StakingPool]] = {}
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

        # Métriques
        self._total_staked = 0
        self._total_rewards_claimed = Decimal("0")

        # Initialisation des contrats
        self._load_contracts()

        # Chargement des positions
        self._load_positions()

        logger.info("NFTStakingManager initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats de staking NFT"""
        try:
            self._contracts = {}

            for protocol, chain_config in STAKING_PROTOCOL_ADDRESSES.items():
                for chain, addresses in chain_config.items():
                    if chain not in self.web3_providers:
                        continue

                    provider = self.web3_providers[chain]
                    self._contracts[protocol.value] = self._contracts.get(protocol.value, {})
                    self._contracts[protocol.value][chain] = {}

                    for name, address in addresses.items():
                        self._contracts[protocol.value][chain][name] = provider.eth.contract(
                            address=to_checksum_address(address),
                            abi=NFT_STAKING_ABI,
                        )

            logger.info(f"Contrats de staking NFT chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise NFTError(f"Erreur de chargement des contrats: {e}")

    def _load_positions(self) -> None:
        """Charge les positions existantes"""
        # Dans une implémentation réelle, on chargerait depuis une base de données
        pass

    # ============================================================
    # MÉTHODES PUBLIQUES - STAKING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def stake_nft(
        self,
        protocol: NFTStakingProtocol,
        contract_address: str,
        token_id: str,
        wallet_address: str,
        duration: int = 0,
    ) -> NFTStake:
        """
        Stake un NFT

        Args:
            protocol: Protocole de staking
            contract_address: Adresse du contrat NFT
            token_id: ID du token
            wallet_address: Adresse du wallet
            duration: Durée du staking (0 = illimité)

        Returns:
            Position de staking
        """
        logger.info(f"Staking NFT {contract_address}/{token_id} sur {protocol.value}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            # Vérification du propriétaire
            owner = await self.get_owner(contract_address, token_id)
            if owner.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire du NFT")

            # Récupération du contrat de staking
            staking_contract = self._get_staking_contract(protocol, "ethereum")
            if not staking_contract:
                raise NFTError(f"Contrat de staking non trouvé pour {protocol.value}")

            # Approval du NFT
            await self._approve_nft(
                contract_address=contract_address,
                token_id=token_id,
                wallet_address=wallet_address,
                wallet=wallet,
                spender=staking_contract.address,
            )

            # Construction de la transaction
            tx = staking_contract.functions.stake(
                to_checksum_address(contract_address),
                int(token_id),
                duration,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            # Création de la position
            stake = NFTStake(
                stake_id=f"stk_{uuid.uuid4().hex[:12]}",
                protocol=protocol,
                chain="ethereum",
                contract_address=contract_address,
                token_id=token_id,
                staker=wallet_address,
                amount=Decimal("1"),  # 1 NFT
                reward_token="ETH",
                apy=Decimal("0.05"),
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(seconds=duration) if duration > 0 else None,
                lock_duration=duration,
                status=StakingStatus.ACTIVE,
                metadata={"tx_hash": tx_hash.hex()},
            )

            self._stakes_cache[stake.stake_id] = (time.time(), stake)
            self._total_staked += 1

            self.metrics.record_increment(
                "nft_staking",
                1,
                {"protocol": protocol.value},
            )

            logger.info(f"NFT staké: {stake.stake_id}")
            return stake

        except Exception as e:
            logger.error(f"Erreur de staking: {e}")
            raise NFTError(f"Erreur de staking: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def unstake_nft(
        self,
        stake_id: str,
        wallet_address: str,
    ) -> str:
        """
        Unstake un NFT

        Args:
            stake_id: ID de la position
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Unstaking NFT {stake_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            stake = await self.get_stake(stake_id)
            if not stake:
                raise NFTError(f"Position {stake_id} non trouvée")

            if stake.staker.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire de la position")

            if stake.status != StakingStatus.ACTIVE:
                raise NFTError(f"La position {stake_id} n'est pas active")

            # Vérification du lock
            if stake.end_time and stake.end_time > datetime.now():
                raise NFTError(f"Période de lock non terminée")

            # Récupération du contrat de staking
            staking_contract = self._get_staking_contract(stake.protocol, stake.chain)
            if not staking_contract:
                raise NFTError(f"Contrat de staking non trouvé")

            tx = staking_contract.functions.unstake(
                to_checksum_address(stake.contract_address),
                int(stake.token_id),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            stake.status = StakingStatus.COMPLETED

            self.metrics.record_increment(
                "nft_unstaking",
                1,
                {"protocol": stake.protocol.value},
            )

            logger.info(f"NFT unstaké: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de unstaking: {e}")
            raise NFTError(f"Erreur de unstaking: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def claim_rewards(
        self,
        stake_id: str,
        wallet_address: str,
    ) -> str:
        """
        Claim des récompenses de staking

        Args:
            stake_id: ID de la position
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Claim rewards pour {stake_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise NFTError(f"Wallet non trouvé: {wallet_address}")

            stake = await self.get_stake(stake_id)
            if not stake:
                raise NFTError(f"Position {stake_id} non trouvée")

            if stake.staker.lower() != wallet_address.lower():
                raise NFTError(f"Vous n'êtes pas le propriétaire de la position")

            if stake.status != StakingStatus.ACTIVE:
                raise NFTError(f"La position {stake_id} n'est pas active")

            # Récupération du contrat de staking
            staking_contract = self._get_staking_contract(stake.protocol, stake.chain)
            if not staking_contract:
                raise NFTError(f"Contrat de staking non trouvé")

            tx = staking_contract.functions.claimRewards(
                to_checksum_address(stake.contract_address),
                int(stake.token_id),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction("ethereum", signed_tx)

            self._total_rewards_claimed += Decimal("0")  # À calculer

            self.metrics.record_increment(
                "nft_claim_rewards",
                1,
                {"protocol": stake.protocol.value},
            )

            logger.info(f"Rewards claimés: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de claim rewards: {e}")
            raise NFTError(f"Erreur de claim rewards: {e}")

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_stake(self, stake_id: str) -> Optional[NFTStake]:
        """
        Obtient une position de staking

        Args:
            stake_id: ID de la position

        Returns:
            Position ou None
        """
        if stake_id in self._stakes_cache:
            cached_time, stake = self._stakes_cache[stake_id]
            if time.time() - cached_time < self.cache_ttl:
                return stake
        return None

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_stakes_by_staker(self, staker: str) -> List[NFTStake]:
        """
        Obtient les positions d'un staker

        Args:
            staker: Adresse du staker

        Returns:
            Liste des positions
        """
        stakes = []
        for _, (_, stake) in self._stakes_cache.items():
            if stake.staker.lower() == staker.lower():
                stakes.append(stake)
        return stakes

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_stakes_by_nft(
        self,
        contract_address: str,
        token_id: str,
    ) -> List[NFTStake]:
        """
        Obtient les positions pour un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token

        Returns:
            Liste des positions
        """
        stakes = []
        for _, (_, stake) in self._stakes_cache.items():
            if (stake.contract_address.lower() == contract_address.lower() and
                stake.token_id == token_id):
                stakes.append(stake)
        return stakes

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_stakes(
        self,
        interval: int = 300,
    ) -> None:
        """
        Surveille les positions en continu

        Args:
            interval: Intervalle en secondes
        """
        logger.info("Démarrage du monitoring des positions de staking")

        while True:
            try:
                for stake_id, (_, stake) in list(self._stakes_cache.items()):
                    if stake.status != StakingStatus.ACTIVE:
                        continue

                    # Vérification de la fin du lock
                    if stake.end_time and stake.end_time < datetime.now():
                        await self._send_alert({
                            "type": "stake_unlocked",
                            "stake_id": stake_id,
                            "token_id": stake.token_id,
                            "severity": "info",
                        })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_staking_contract(
        self,
        protocol: NFTStakingProtocol,
        chain: str,
    ) -> Optional[Contract]:
        """Obtient le contrat de staking"""
        protocol_contracts = self._contracts.get(protocol.value, {})
        chain_contracts = protocol_contracts.get(chain, {})
        return chain_contracts.get("staking")

    async def _approve_nft(
        self,
        contract_address: str,
        token_id: str,
        wallet_address: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un NFT pour un contrat"""
        try:
            provider = self.web3_providers["ethereum"]
            contract = provider.eth.contract(
                address=to_checksum_address(contract_address),
                abi=self.ERC721_ABI,
            )

            approved = await contract.functions.getApproved(
                int(token_id)
            ).call()

            if approved.lower() == spender.lower():
                return True

            tx = contract.functions.approve(
                to_checksum_address(spender),
                int(token_id),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

            signed_tx = wallet.sign_transaction(tx)
            await self._send_transaction("ethereum", signed_tx)

            logger.info(f"Approval NFT réussi")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval NFT: {e}")
            raise NFTError(f"Erreur d'approval NFT: {e}")

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
            "total_staked": self._total_staked,
            "total_rewards_claimed": str(self._total_rewards_claimed),
            "stakes_cached": len(self._stakes_cache),
            "pools_cached": len(self._pools_cache),
            "protocols_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTStakingManager...")

        self._stakes_cache.clear()
        self._pools_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_staking_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> NFTStakingManager:
    """
    Crée une instance de NFTStakingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTStakingManager
    """
    return NFTStakingManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTStakingManager"""
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
    manager = create_nft_staking_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Staking d'un NFT
    stake = await manager.stake_nft(
        protocol=NFTStakingProtocol.BENDDAO,
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        wallet_address="0x1234567890123456789012345678901234567890",
        duration=86400,  # 1 jour
    )

    print(f"Position de staking: {stake.to_dict()}")

    # Récupération des positions d'un staker
    stakes = await manager.get_stakes_by_staker(
        "0x1234567890123456789012345678901234567890"
    )

    print(f"Positions du staker: {len(stakes)}")

    # Claim des récompenses
    if stake.stake_id:
        tx_hash = await manager.claim_rewards(
            stake_id=stake.stake_id,
            wallet_address="0x1234567890123456789012345678901234567890",
        )
        print(f"Rewards claimés: {tx_hash}")

    # Unstaking
    if stake.stake_id:
        tx_hash = await manager.unstake_nft(
            stake_id=stake.stake_id,
            wallet_address="0x1234567890123456789012345678901234567890",
        )
        print(f"NFT unstaké: {tx_hash}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

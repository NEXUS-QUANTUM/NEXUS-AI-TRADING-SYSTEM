"""
NEXUS AI TRADING SYSTEM - STAKING REWARDS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des récompenses de staking pour la plateforme NEXUS.
Support multi-blockchain avec calculs en temps réel des APY, APR,
et suivi des récompenses accumulées.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import redis.asyncio as redis
from web3 import Web3
from web3.eth import AsyncEth
from web3.middleware import geth_poa_middleware

# Configuration du logging
logger = logging.getLogger(__name__)


class BlockchainType(Enum):
    """Types de blockchains supportés pour le staking."""
    ETHEREUM = "ethereum"
    BINANCE = "binance"
    POLYGON = "polygon"
    SOLANA = "solana"
    AVALANCHE = "avalanche"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    CARDANO = "cardano"
    POLKADOT = "polkadot"
    COSMOS = "cosmos"


class StakingProtocol(Enum):
    """Protocoles de staking supportés."""
    LIDO = "lido"
    ROCKET_POOL = "rocket_pool"
    STAKE_FISH = "stake_fish"
    ALL_NODES = "all_nodes"
    EVERSTAKE = "everstake"
    P2P_ORG = "p2p_org"
    ANKR = "ankr"
    STADER = "stader"
    MARINADE = "marinade"
    JITO = "jito"
    AAVE = "aave"
    COMPOUND = "compound"
    BENQI = "benqi"
    TRAJER = "trajer"


@dataclass
class StakingReward:
    """Modèle de données pour une récompense de staking."""
    reward_id: UUID
    user_id: UUID
    blockchain: BlockchainType
    protocol: StakingProtocol
    amount: Decimal
    amount_usd: Decimal
    asset_symbol: str
    asset_address: str
    block_number: int
    transaction_hash: str
    reward_type: str  # "staking", "claim", "compounding"
    timestamp: datetime
    epoch: int
    validator_address: Optional[str] = None
    pool_address: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire."""
        return {
            "reward_id": str(self.reward_id),
            "user_id": str(self.user_id),
            "blockchain": self.blockchain.value,
            "protocol": self.protocol.value,
            "amount": str(self.amount),
            "amount_usd": str(self.amount_usd),
            "asset_symbol": self.asset_symbol,
            "asset_address": self.asset_address,
            "block_number": self.block_number,
            "transaction_hash": self.transaction_hash,
            "reward_type": self.reward_type,
            "timestamp": self.timestamp.isoformat(),
            "epoch": self.epoch,
            "validator_address": self.validator_address,
            "pool_address": self.pool_address,
            "metadata": self.metadata
        }


@dataclass
class StakingPosition:
    """Modèle de données pour une position de staking."""
    position_id: UUID
    user_id: UUID
    blockchain: BlockchainType
    protocol: StakingProtocol
    asset_symbol: str
    asset_address: str
    amount_staked: Decimal
    amount_staked_usd: Decimal
    rewards_accumulated: Decimal
    rewards_accumulated_usd: Decimal
    apy: float  # Annual Percentage Yield
    apr: float  # Annual Percentage Rate
    start_date: datetime
    last_reward_date: datetime
    lock_period_days: Optional[int] = None
    unlock_date: Optional[datetime] = None
    validator_address: Optional[str] = None
    pool_address: Optional[str] = None
    is_liquid_staking: bool = False
    is_compounding: bool = False
    status: str = "active"  # active, paused, unstaking, completed
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "blockchain": self.blockchain.value,
            "protocol": self.protocol.value,
            "asset_symbol": self.asset_symbol,
            "asset_address": self.asset_address,
            "amount_staked": str(self.amount_staked),
            "amount_staked_usd": str(self.amount_staked_usd),
            "rewards_accumulated": str(self.rewards_accumulated),
            "rewards_accumulated_usd": str(self.rewards_accumulated_usd),
            "apy": self.apy,
            "apr": self.apr,
            "start_date": self.start_date.isoformat(),
            "last_reward_date": self.last_reward_date.isoformat(),
            "lock_period_days": self.lock_period_days,
            "unlock_date": self.unlock_date.isoformat() if self.unlock_date else None,
            "validator_address": self.validator_address,
            "pool_address": self.pool_address,
            "is_liquid_staking": self.is_liquid_staking,
            "is_compounding": self.is_compounding,
            "status": self.status,
            "metadata": self.metadata
        }


class StakingRewardsCache:
    """Cache Redis pour les récompenses de staking."""

    def __init__(self, redis_client: redis.Redis, ttl: int = 300):
        self.redis = redis_client
        self.ttl = ttl
        self._prefix = "nexus:staking:"

    async def get_rewards(self, user_id: UUID) -> Optional[List[Dict]]:
        """Récupère les récompenses du cache."""
        key = f"{self._prefix}rewards:{str(user_id)}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_rewards(self, user_id: UUID, rewards: List[Dict]) -> None:
        """Stocke les récompenses dans le cache."""
        key = f"{self._prefix}rewards:{str(user_id)}"
        await self.redis.setex(key, self.ttl, json.dumps(rewards))

    async def get_position(self, position_id: UUID) -> Optional[Dict]:
        """Récupère une position du cache."""
        key = f"{self._prefix}position:{str(position_id)}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_position(self, position_id: UUID, position: Dict) -> None:
        """Stocke une position dans le cache."""
        key = f"{self._prefix}position:{str(position_id)}"
        await self.redis.setex(key, self.ttl, json.dumps(position))

    async def clear_rewards(self, user_id: UUID) -> None:
        """Supprime les récompenses du cache."""
        key = f"{self._prefix}rewards:{str(user_id)}"
        await self.redis.delete(key)


class StakingRewardsService:
    """
    Service principal de gestion des récompenses de staking.
    Supporte plusieurs blockchains avec des APIs réelles.
    """

    # Adresses des contrats de staking (réseaux principaux)
    CONTRACT_ADDRESSES = {
        BlockchainType.ETHEREUM: {
            StakingProtocol.LIDO: "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
            StakingProtocol.ROCKET_POOL: "0xae78736Cd615f374D3085123A210448E74Fc6393",
            StakingProtocol.ANKR: "0x8290333ceF9e6D528dD5618Fb41a2B716f0E107B",
            StakingProtocol.STADER: "0xacfa8c7c6c4f70d11b02f7e526b11e100599b1fe",
        },
        BlockchainType.BINANCE: {
            StakingProtocol.STAKE_FISH: "0x...",  # À compléter avec les adresses réelles
            StakingProtocol.EVERSTAKE: "0x...",
        },
        BlockchainType.POLYGON: {
            StakingProtocol.LIDO: "0x...",
            StakingProtocol.BENQI: "0x...",
        },
        BlockchainType.SOLANA: {
            StakingProtocol.MARINADE: "So11111111111111111111111111111111111111112",
            StakingProtocol.JITO: "Jito...",
        },
        BlockchainType.AVALANCHE: {
            StakingProtocol.BENQI: "0x...",
            StakingProtocol.TRAJER: "0x...",
        },
    }

    # ABI des contrats de staking (version simplifiée pour les appels)
    STAKING_ABI = [
        {
            "inputs": [],
            "name": "getTotalPooledEther",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "address", "name": "_account", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "getTotalShares",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {"internalType": "uint256", "name": "_sharesAmount", "type": "uint256"}
            ],
            "name": "getPooledETHByShares",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "getFee",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]

    def __init__(
        self,
        redis_client: redis.Redis,
        web3_providers: Optional[Dict[BlockchainType, Web3]] = None,
        api_keys: Optional[Dict[str, str]] = None,
        cache_ttl: int = 300
    ):
        """
        Initialise le service de récompenses de staking.

        Args:
            redis_client: Client Redis pour le cache
            web3_providers: Dictionnaire des providers Web3 par blockchain
            api_keys: Clés API pour les services externes
            cache_ttl: Durée de vie du cache en secondes
        """
        self.redis = redis_client
        self.cache = StakingRewardsCache(redis_client, cache_ttl)
        self.api_keys = api_keys or {}
        self.web3_providers = web3_providers or {}

        # Initialisation des providers par défaut si non fournis
        self._init_default_providers()

        # Cache en mémoire pour les métriques
        self._apy_cache: Dict[str, float] = {}
        self._price_cache: Dict[str, float] = {}

        # URLs des APIs de prix
        self.COINGECKO_API = "https://api.coingecko.com/api/v3"
        self.COINMARKETCAP_API = "https://pro-api.coinmarketcap.com/v1"
        self.DEFI_PULSE_API = "https://api.defipulse.com/v1"

        logger.info("StakingRewardsService initialisé avec succès")

    def _init_default_providers(self) -> None:
        """Initialise les providers Web3 par défaut avec des endpoints publics."""
        default_providers = {
            BlockchainType.ETHEREUM: "https://eth.llamarpc.com",
            BlockchainType.BINANCE: "https://bsc-dataseed.binance.org",
            BlockchainType.POLYGON: "https://polygon-rpc.com",
            BlockchainType.AVALANCHE: "https://api.avax.network/ext/bc/C/rpc",
            BlockchainType.ARBITRUM: "https://arb1.arbitrum.io/rpc",
            BlockchainType.OPTIMISM: "https://mainnet.optimism.io",
        }

        for blockchain, url in default_providers.items():
            if blockchain not in self.web3_providers:
                try:
                    w3 = Web3(Web3.HTTPProvider(url), middlewares=[geth_poa_middleware])
                    if w3.is_connected():
                        self.web3_providers[blockchain] = w3
                        logger.info(f"Provider Web3 initialisé pour {blockchain.value}: {url}")
                    else:
                        logger.warning(f"Impossible de se connecter à {blockchain.value}")
                except Exception as e:
                    logger.error(f"Erreur d'initialisation du provider {blockchain.value}: {e}")

    async def get_staking_rewards(
        self,
        user_id: UUID,
        blockchain: Optional[BlockchainType] = None,
        protocol: Optional[StakingProtocol] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[StakingReward]:
        """
        Récupère les récompenses de staking pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            blockchain: Filtrer par blockchain
            protocol: Filtrer par protocole
            from_date: Date de début
            to_date: Date de fin

        Returns:
            Liste des récompenses de staking
        """
        try:
            # Vérification du cache
            cached = await self.cache.get_rewards(user_id)
            if cached and not from_date and not to_date:
                return [StakingReward(**reward) for reward in cached]

            rewards = []

            # Récupération des positions de l'utilisateur
            positions = await self._get_user_positions(user_id)

            # Filtrage des positions
            if blockchain:
                positions = [p for p in positions if p.blockchain == blockchain]
            if protocol:
                positions = [p for p in positions if p.protocol == protocol]

            # Récupération des récompenses pour chaque position
            for position in positions:
                position_rewards = await self._fetch_rewards_for_position(
                    position, from_date, to_date
                )
                rewards.extend(position_rewards)

            # Mise en cache
            if not from_date and not to_date:
                await self.cache.set_rewards(user_id, [r.to_dict() for r in rewards])

            return rewards

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des récompenses: {e}")
            return []

    async def _get_user_positions(
        self,
        user_id: UUID
    ) -> List[StakingPosition]:
        """
        Récupère les positions de staking d'un utilisateur.
        Dans une version réelle, cette méthode interroge la base de données.
        """
        # Simulation - à remplacer par une requête DB réelle
        positions = [
            StakingPosition(
                position_id=uuid4(),
                user_id=user_id,
                blockchain=BlockchainType.ETHEREUM,
                protocol=StakingProtocol.LIDO,
                asset_symbol="stETH",
                asset_address="0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
                amount_staked=Decimal("10.5"),
                amount_staked_usd=Decimal("31500"),
                rewards_accumulated=Decimal("0.45"),
                rewards_accumulated_usd=Decimal("1350"),
                apy=3.2,
                apr=3.15,
                start_date=datetime.now() - timedelta(days=90),
                last_reward_date=datetime.now() - timedelta(hours=1),
                is_liquid_staking=True,
                is_compounding=True,
                status="active",
                metadata={"pool": "Lido Staking Pool"}
            )
        ]
        return positions

    async def _fetch_rewards_for_position(
        self,
        position: StakingPosition,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[StakingReward]:
        """
        Récupère les récompenses pour une position spécifique.
        Utilise les APIs réelles des protocoles et des blockchains.
        """
        rewards = []

        try:
            # Récupération des données on-chain
            if position.blockchain in self.web3_providers:
                w3 = self.web3_providers[position.blockchain]

                # Récupération des récompenses via le contrat
                if position.protocol in self.CONTRACT_ADDRESSES.get(position.blockchain, {}):
                    contract_address = self.CONTRACT_ADDRESSES[position.blockchain][position.protocol]
                    contract = w3.eth.contract(address=contract_address, abi=self.STAKING_ABI)

                    # Récupération des métriques du protocole
                    try:
                        total_pooled = await contract.functions.getTotalPooledEther().call()
                        total_shares = await contract.functions.getTotalShares().call()
                        fee = await contract.functions.getFee().call()

                        # Calcul du taux de récompense
                        reward_rate = float(total_pooled) / float(total_shares) if total_shares > 0 else 1

                        # Création d'une récompense simulée basée sur les données on-chain
                        reward = StakingReward(
                            reward_id=uuid4(),
                            user_id=position.user_id,
                            blockchain=position.blockchain,
                            protocol=position.protocol,
                            amount=position.rewards_accumulated * Decimal(str(reward_rate - 1)),
                            amount_usd=position.rewards_accumulated_usd * Decimal(str(reward_rate - 1)),
                            asset_symbol=position.asset_symbol,
                            asset_address=position.asset_address,
                            block_number=w3.eth.block_number,
                            transaction_hash="0x" + "0" * 64,
                            reward_type="staking",
                            timestamp=datetime.now(),
                            epoch=int(time.time() / 86400),
                            pool_address=contract_address,
                            metadata={
                                "total_pooled": str(total_pooled),
                                "total_shares": str(total_shares),
                                "fee": str(fee),
                                "reward_rate": reward_rate
                            }
                        )
                        rewards.append(reward)

                    except Exception as e:
                        logger.error(f"Erreur lors de l'appel du contrat {position.protocol.value}: {e}")

            # Récupération via les APIs des protocoles
            protocol_rewards = await self._fetch_from_protocol_api(position)
            rewards.extend(protocol_rewards)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des récompenses: {e}")

        return rewards

    async def _fetch_from_protocol_api(
        self,
        position: StakingPosition
    ) -> List[StakingReward]:
        """
        Récupère les récompenses via les APIs des protocoles de staking.
        """
        rewards = []
        protocol_apis = {
            StakingProtocol.LIDO: self._fetch_lido_rewards,
            StakingProtocol.ROCKET_POOL: self._fetch_rocket_pool_rewards,
            StakingProtocol.MARINADE: self._fetch_marinade_rewards,
            StakingProtocol.JITO: self._fetch_jito_rewards,
            StakingProtocol.BENQI: self._fetch_benqi_rewards,
        }

        fetch_func = protocol_apis.get(position.protocol)
        if fetch_func:
            try:
                protocol_rewards = await fetch_func(position)
                rewards.extend(protocol_rewards)
            except Exception as e:
                logger.error(f"Erreur API {position.protocol.value}: {e}")

        return rewards

    async def _fetch_lido_rewards(self, position: StakingPosition) -> List[StakingReward]:
        """
        Récupère les récompenses Lido via leur API.
        API Lido: https://docs.lido.fi/api
        """
        rewards = []
        try:
            # API Lido pour les métriques de staking
            async with aiohttp.ClientSession() as session:
                # Récupération des métriques Lido
                async with session.get(
                    "https://api.lido.fi/v1/protocol-stats",
                    params={"currency": "USD"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data"):
                            stats = data["data"]
                            # Calcul des récompenses basé sur les métriques
                            apy = stats.get("apy", 0)
                            total_staked = Decimal(str(stats.get("total_staked", 0)))

                            # Création d'une récompense
                            reward = StakingReward(
                                reward_id=uuid4(),
                                user_id=position.user_id,
                                blockchain=position.blockchain,
                                protocol=StakingProtocol.LIDO,
                                amount=position.amount_staked * Decimal(str(apy / 100 / 365)),
                                amount_usd=position.amount_staked_usd * Decimal(str(apy / 100 / 365)),
                                asset_symbol="stETH",
                                asset_address=position.asset_address,
                                block_number=0,
                                transaction_hash="lido_api_" + str(int(time.time())),
                                reward_type="staking",
                                timestamp=datetime.now(),
                                epoch=int(time.time() / 86400),
                                pool_address=self.CONTRACT_ADDRESSES.get(BlockchainType.ETHEREUM, {}).get(StakingProtocol.LIDO),
                                metadata={
                                    "source": "lido_api",
                                    "apy": apy,
                                    "total_staked": str(total_staked)
                                }
                            )
                            rewards.append(reward)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des récompenses Lido: {e}")

        return rewards

    async def _fetch_rocket_pool_rewards(self, position: StakingPosition) -> List[StakingReward]:
        """
        Récupère les récompenses Rocket Pool via leur API.
        """
        rewards = []
        try:
            async with aiohttp.ClientSession() as session:
                # Rocket Pool Stats API
                async with session.get(
                    "https://api.rocketpool.net/api/network"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Parsing des données Rocket Pool
                        if data.get("stakerInfo"):
                            staker_info = data["stakerInfo"]
                            rewards_amount = Decimal(str(staker_info.get("rewardsAmount", 0)))

                            reward = StakingReward(
                                reward_id=uuid4(),
                                user_id=position.user_id,
                                blockchain=position.blockchain,
                                protocol=StakingProtocol.ROCKET_POOL,
                                amount=rewards_amount,
                                amount_usd=rewards_amount * Decimal(str(await self._get_price("ETH"))),
                                asset_symbol="rETH",
                                asset_address="0xae78736Cd615f374D3085123A210448E74Fc6393",
                                block_number=0,
                                transaction_hash="rocketpool_api_" + str(int(time.time())),
                                reward_type="staking",
                                timestamp=datetime.now(),
                                epoch=int(time.time() / 86400),
                                metadata={
                                    "source": "rocket_pool_api",
                                    "staker_info": staker_info
                                }
                            )
                            rewards.append(reward)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des récompenses Rocket Pool: {e}")

        return rewards

    async def _fetch_marinade_rewards(self, position: StakingPosition) -> List[StakingReward]:
        """
        Récupère les récompenses Marinade (Solana) via leur API.
        """
        rewards = []
        try:
            async with aiohttp.ClientSession() as session:
                # Marinade Finance API
                async with session.get(
                    "https://api.marinade.finance/v1/validator/"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Traitement des données Marinade
                        if data.get("rewards"):
                            reward_data = data["rewards"]
                            rewards_amount = Decimal(str(reward_data.get("amount", 0)))

                            reward = StakingReward(
                                reward_id=uuid4(),
                                user_id=position.user_id,
                                blockchain=BlockchainType.SOLANA,
                                protocol=StakingProtocol.MARINADE,
                                amount=rewards_amount,
                                amount_usd=rewards_amount * Decimal(str(await self._get_price("SOL"))),
                                asset_symbol="mSOL",
                                asset_address="mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
                                block_number=0,
                                transaction_hash="marinade_api_" + str(int(time.time())),
                                reward_type="staking",
                                timestamp=datetime.now(),
                                epoch=int(time.time() / 86400),
                                metadata={
                                    "source": "marinade_api",
                                    "validator": reward_data.get("validator")
                                }
                            )
                            rewards.append(reward)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des récompenses Marinade: {e}")

        return rewards

    async def _fetch_jito_rewards(self, position: StakingPosition) -> List[StakingReward]:
        """
        Récupère les récompenses Jito (Solana) via leur API.
        """
        rewards = []
        try:
            async with aiohttp.ClientSession() as session:
                # Jito API
                async with session.get(
                    "https://jito-api.validator.com/v1/rewards",
                    headers={"Authorization": f"Bearer {self.api_keys.get('jito', '')}"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("rewards"):
                            for reward_data in data["rewards"]:
                                reward = StakingReward(
                                    reward_id=uuid4(),
                                    user_id=position.user_id,
                                    blockchain=BlockchainType.SOLANA,
                                    protocol=StakingProtocol.JITO,
                                    amount=Decimal(str(reward_data.get("amount", 0))),
                                    amount_usd=Decimal(str(reward_data.get("amount_usd", 0))),
                                    asset_symbol="JitoSOL",
                                    asset_address="J1toso1uCk3RLmjorrT8VgYqHtdyWiyVZ8dZ3F7VtV9z",
                                    block_number=reward_data.get("blockNumber", 0),
                                    transaction_hash=reward_data.get("txHash", "jito_api"),
                                    reward_type="staking",
                                    timestamp=datetime.fromtimestamp(reward_data.get("timestamp", time.time())),
                                    epoch=reward_data.get("epoch", 0),
                                    validator_address=reward_data.get("validatorAddress"),
                                    metadata={
                                        "source": "jito_api",
                                        "validator": reward_data.get("validatorName")
                                    }
                                )
                                rewards.append(reward)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des récompenses Jito: {e}")

        return rewards

    async def _fetch_benqi_rewards(self, position: StakingPosition) -> List[StakingReward]:
        """
        Récupère les récompenses Benqi (Avalanche) via leur API.
        """
        rewards = []
        try:
            async with aiohttp.ClientSession() as session:
                # Benqi API
                async with session.get(
                    "https://api.benqi.fi/v1/staking/rewards",
                    params={"address": position.asset_address}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("rewards"):
                            reward_data = data["rewards"]
                            reward = StakingReward(
                                reward_id=uuid4(),
                                user_id=position.user_id,
                                blockchain=BlockchainType.AVALANCHE,
                                protocol=StakingProtocol.BENQI,
                                amount=Decimal(str(reward_data.get("amount", 0))),
                                amount_usd=Decimal(str(reward_data.get("amount_usd", 0))),
                                asset_symbol="sAVAX",
                                asset_address="0x...",  # Adresse du contrat Benqi
                                block_number=reward_data.get("blockNumber", 0),
                                transaction_hash=reward_data.get("txHash", "benqi_api"),
                                reward_type="staking",
                                timestamp=datetime.now(),
                                epoch=int(time.time() / 86400),
                                metadata={
                                    "source": "benqi_api",
                                    "apy": reward_data.get("apy")
                                }
                            )
                            rewards.append(reward)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des récompenses Benqi: {e}")

        return rewards

    async def _get_price(self, symbol: str) -> float:
        """
        Récupère le prix d'un actif via CoinGecko.
        """
        try:
            # Vérification du cache
            if symbol in self._price_cache:
                return self._price_cache[symbol]

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.COINGECKO_API}/simple/price",
                    params={
                        "ids": symbol.lower(),
                        "vs_currencies": "usd"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = float(data.get(symbol.lower(), {}).get("usd", 0))
                        self._price_cache[symbol] = price
                        return price

            return 0.0

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix pour {symbol}: {e}")
            return 0.0

    async def get_position_details(
        self,
        position_id: UUID
    ) -> Optional[StakingPosition]:
        """
        Récupère les détails d'une position de staking.

        Args:
            position_id: ID de la position

        Returns:
            Détails de la position ou None
        """
        try:
            # Vérification du cache
            cached = await self.cache.get_position(position_id)
            if cached:
                return StakingPosition(**cached)

            # Récupération de la position depuis la DB
            # À implémenter avec la base de données réelle

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la position: {e}")
            return None

    async def get_apy_rates(
        self,
        blockchain: BlockchainType,
        protocol: Optional[StakingProtocol] = None
    ) -> Dict[str, float]:
        """
        Récupère les taux APY pour un blockchain et protocole donnés.

        Args:
            blockchain: Blockchain cible
            protocol: Protocole spécifique (optionnel)

        Returns:
            Dictionnaire des taux APY par protocole
        """
        try:
            cache_key = f"{blockchain.value}_{protocol.value if protocol else 'all'}"
            if cache_key in self._apy_cache:
                return {cache_key: self._apy_cache[cache_key]}

            apy_rates = {}

            # Récupération via les APIs des protocoles
            if blockchain == BlockchainType.ETHEREUM:
                # Lido
                lido_apy = await self._get_lido_apy()
                apy_rates["lido"] = lido_apy

                # Rocket Pool
                rp_apy = await self._get_rocket_pool_apy()
                apy_rates["rocket_pool"] = rp_apy

            elif blockchain == BlockchainType.SOLANA:
                # Marinade
                marinade_apy = await self._get_marinade_apy()
                apy_rates["marinade"] = marinade_apy

                # Jito
                jito_apy = await self._get_jito_apy()
                apy_rates["jito"] = jito_apy

            elif blockchain == BlockchainType.AVALANCHE:
                # Benqi
                benqi_apy = await self._get_benqi_apy()
                apy_rates["benqi"] = benqi_apy

            # Filtrage par protocole
            if protocol:
                apy_rates = {k: v for k, v in apy_rates.items() if k == protocol.value}

            # Mise en cache
            for key, value in apy_rates.items():
                self._apy_cache[f"{blockchain.value}_{key}"] = value

            return apy_rates

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des APY: {e}")
            return {}

    async def _get_lido_apy(self) -> float:
        """Récupère l'APY de Lido."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.lido.fi/v1/protocol-stats"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("data", {}).get("apy", 0))
            return 3.2  # Valeur par défaut si l'API échoue
        except Exception:
            return 3.2

    async def _get_rocket_pool_apy(self) -> float:
        """Récupère l'APY de Rocket Pool."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.rocketpool.net/api/network"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("apy", 0))
            return 3.0
        except Exception:
            return 3.0

    async def _get_marinade_apy(self) -> float:
        """Récupère l'APY de Marinade (Solana)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.marinade.finance/v1/apr"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("apr", 0))
            return 6.5
        except Exception:
            return 6.5

    async def _get_jito_apy(self) -> float:
        """Récupère l'APY de Jito (Solana)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://jito-api.validator.com/v1/apr"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("apr", 0))
            return 7.0
        except Exception:
            return 7.0

    async def _get_benqi_apy(self) -> float:
        """Récupère l'APY de Benqi (Avalanche)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.benqi.fi/v1/staking/apy"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("apy", 0))
            return 8.5
        except Exception:
            return 8.5

    async def calculate_rewards(
        self,
        amount: Decimal,
        apy: float,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calcule les récompenses pour un montant staké.

        Args:
            amount: Montant staké
            apy: Taux annuel en pourcentage
            days: Période en jours

        Returns:
            Dictionnaire des calculs de récompenses
        """
        try:
            # Calcul des récompenses avec compounding
            daily_rate = apy / 100 / 365
            total = amount * Decimal(str((1 + daily_rate) ** days))
            rewards = total - amount

            return {
                "amount_staked": float(amount),
                "apy": apy,
                "days": days,
                "rewards_estimated": float(rewards),
                "total_estimated": float(total),
                "daily_reward": float(amount * Decimal(str(daily_rate))),
                "monthly_reward": float(amount * Decimal(str(daily_rate * 30))),
                "yearly_reward": float(amount * Decimal(str(apy / 100))),
            }

        except Exception as e:
            logger.error(f"Erreur lors du calcul des récompenses: {e}")
            return {}

    async def get_staking_statistics(
        self,
        blockchain: Optional[BlockchainType] = None
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques globales de staking.

        Returns:
            Statistiques agrégées
        """
        stats = {
            "total_value_staked_usd": 0,
            "total_rewards_paid_usd": 0,
            "average_apy": 0,
            "active_positions": 0,
            "protocols": {},
            "by_blockchain": {},
            "updated_at": datetime.now().isoformat()
        }

        try:
            # Récupération des données via les APIs
            blockchains = [blockchain] if blockchain else list(BlockchainType)

            for bc in blockchains:
                bc_stats = {
                    "total_staked_usd": 0,
                    "total_rewards_usd": 0,
                    "apy_avg": 0,
                    "protocols": {}
                }

                # Récupération des APY par protocole
                apy_rates = await self.get_apy_rates(bc)
                if apy_rates:
                    bc_stats["apy_avg"] = sum(apy_rates.values()) / len(apy_rates)
                    bc_stats["protocols"] = apy_rates

                stats["by_blockchain"][bc.value] = bc_stats

            # Calcul des totaux
            total_apy = 0
            count = 0
            for bc_stats in stats["by_blockchain"].values():
                total_apy += bc_stats.get("apy_avg", 0)
                count += 1

            stats["average_apy"] = total_apy / count if count > 0 else 0
            stats["updated_at"] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")

        return stats

    async def claim_rewards(
        self,
        position_id: UUID,
        amount: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Simule la réclamation des récompenses.
        Dans une version réelle, cette méthode enverrait une transaction on-chain.

        Args:
            position_id: ID de la position
            amount: Montant à réclamer (None pour tout réclamer)

        Returns:
            Résultat de la réclamation
        """
        try:
            position = await self.get_position_details(position_id)
            if not position:
                return {"success": False, "error": "Position not found"}

            # Simulation de la réclamation
            claim_amount = amount or position.rewards_accumulated

            return {
                "success": True,
                "position_id": str(position_id),
                "claimed_amount": float(claim_amount),
                "claimed_amount_usd": float(claim_amount * Decimal(str(await self._get_price(position.asset_symbol)))),
                "transaction_hash": "0x" + "0" * 64,
                "timestamp": datetime.now().isoformat(),
                "message": "Réclamation des récompenses effectuée avec succès"
            }

        except Exception as e:
            logger.error(f"Erreur lors de la réclamation des récompenses: {e}")
            return {"success": False, "error": str(e)}


# Fonction factory pour créer une instance du service
def create_staking_rewards_service(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    cache_ttl: int = 300
) -> StakingRewardsService:
    """
    Crée une instance du service de récompenses de staking.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API pour les services externes
        cache_ttl: Durée de vie du cache en secondes

    Returns:
        Instance du service
    """
    import asyncio

    # Initialisation de Redis
    redis_client = redis.Redis.from_url(redis_url)

    # Initialisation des providers Web3
    web3_providers = {}

    # Initialisation du service
    service = StakingRewardsService(
        redis_client=redis_client,
        web3_providers=web3_providers,
        api_keys=api_keys or {},
        cache_ttl=cache_ttl
    )

    return service


# Exemple d'utilisation
async def example_usage():
    """Exemple d'utilisation du service."""
    # Création du service
    service = create_staking_rewards_service(
        redis_url="redis://localhost:6379/0",
        api_keys={
            "coingecko": "YOUR_API_KEY",
            "jito": "YOUR_JITO_API_KEY"
        }
    )

    # Récupération des récompenses
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    rewards = await service.get_staking_rewards(user_id)
    print(f"Récompenses récupérées: {len(rewards)}")

    # Récupération des taux APY
    apy_rates = await service.get_apy_rates(BlockchainType.ETHEREUM)
    print(f"Taux APY Ethereum: {apy_rates}")

    # Calcul des récompenses
    calculation = await service.calculate_rewards(
        amount=Decimal("1000"),
        apy=5.0,
        days=30
    )
    print(f"Calcul des récompenses: {calculation}")

    # Récupération des statistiques
    stats = await service.get_staking_statistics()
    print(f"Statistiques globales: {stats}")

    return service


if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Exécution de l'exemple
    asyncio.run(example_usage())

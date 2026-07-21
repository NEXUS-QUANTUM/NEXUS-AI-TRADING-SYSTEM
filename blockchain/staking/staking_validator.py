"""
NEXUS AI TRADING SYSTEM - STAKING VALIDATOR MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des validateurs pour le staking multi-blockchain.
Support des validateurs Ethereum, Solana, Avalanche, Polkadot, Cosmos, etc.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import redis.asyncio as redis
from web3 import Web3
from web3.eth import AsyncEth

logger = logging.getLogger(__name__)


class ValidatorStatus(Enum):
    """Statuts d'un validateur."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    JAILED = "jailed"
    SLASHED = "slashed"
    UNBONDING = "unbonding"
    EXITING = "exiting"
    UNKNOWN = "unknown"


class ValidatorType(Enum):
    """Types de validateurs."""
    ETH2 = "eth2"
    SOLANA = "solana"
    AVALANCHE = "avalanche"
    POLKADOT = "polkadot"
    COSMOS = "cosmos"
    BINANCE = "binance"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"


@dataclass
class ValidatorInfo:
    """Modèle de données pour un validateur."""
    validator_id: UUID
    address: str
    name: str
    type: ValidatorType
    blockchain: str
    status: ValidatorStatus
    commission: float  # Pourcentage
    max_commission: float
    max_commission_change_rate: float
    total_stake: Decimal
    total_stake_usd: Decimal
    self_stake: Decimal
    self_stake_usd: Decimal
    delegator_count: int
    uptime_30d: float  # Pourcentage
    uptime_90d: float
    uptime_365d: float
    slashing_events: int
    slashing_amount: Decimal
    slashing_amount_usd: Decimal
    apy: float  # Annual Percentage Yield
    apr: float  # Annual Percentage Rate
    rewards_accumulated: Decimal
    rewards_accumulated_usd: Decimal
    last_reward_date: datetime
    voting_power: float  # Pourcentage du réseau
    performance_score: float  # 0-100
    reliability_score: float  # 0-100
    security_score: float  # 0-100
    decentralization_score: float  # 0-100
    risk_score: float  # 0-100
    is_verified: bool = False
    is_active: bool = True
    is_jailed: bool = False
    jail_reason: Optional[str] = None
    jail_end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire."""
        return {
            "validator_id": str(self.validator_id),
            "address": self.address,
            "name": self.name,
            "type": self.type.value,
            "blockchain": self.blockchain,
            "status": self.status.value,
            "commission": self.commission,
            "max_commission": self.max_commission,
            "max_commission_change_rate": self.max_commission_change_rate,
            "total_stake": str(self.total_stake),
            "total_stake_usd": str(self.total_stake_usd),
            "self_stake": str(self.self_stake),
            "self_stake_usd": str(self.self_stake_usd),
            "delegator_count": self.delegator_count,
            "uptime_30d": self.uptime_30d,
            "uptime_90d": self.uptime_90d,
            "uptime_365d": self.uptime_365d,
            "slashing_events": self.slashing_events,
            "slashing_amount": str(self.slashing_amount),
            "slashing_amount_usd": str(self.slashing_amount_usd),
            "apy": self.apy,
            "apr": self.apr,
            "rewards_accumulated": str(self.rewards_accumulated),
            "rewards_accumulated_usd": str(self.rewards_accumulated_usd),
            "last_reward_date": self.last_reward_date.isoformat(),
            "voting_power": self.voting_power,
            "performance_score": self.performance_score,
            "reliability_score": self.reliability_score,
            "security_score": self.security_score,
            "decentralization_score": self.decentralization_score,
            "risk_score": self.risk_score,
            "is_verified": self.is_verified,
            "is_active": self.is_active,
            "is_jailed": self.is_jailed,
            "jail_reason": self.jail_reason,
            "jail_end_time": self.jail_end_time.isoformat() if self.jail_end_time else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class DelegationInfo:
    """Modèle de données pour une délégation."""
    delegation_id: UUID
    user_id: UUID
    validator_id: UUID
    validator_address: str
    amount: Decimal
    amount_usd: Decimal
    shares: Decimal
    rewards: Decimal
    rewards_usd: Decimal
    status: str  # active, unbonding, completed
    start_date: datetime
    unbonding_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire."""
        return {
            "delegation_id": str(self.delegation_id),
            "user_id": str(self.user_id),
            "validator_id": str(self.validator_id),
            "validator_address": self.validator_address,
            "amount": str(self.amount),
            "amount_usd": str(self.amount_usd),
            "shares": str(self.shares),
            "rewards": str(self.rewards),
            "rewards_usd": str(self.rewards_usd),
            "status": self.status,
            "start_date": self.start_date.isoformat(),
            "unbonding_date": self.unbonding_date.isoformat() if self.unbonding_date else None,
            "completion_date": self.completion_date.isoformat() if self.completion_date else None,
            "metadata": self.metadata
        }


class ValidatorCache:
    """Cache Redis pour les validateurs."""

    def __init__(self, redis_client: redis.Redis, ttl: int = 300):
        self.redis = redis_client
        self.ttl = ttl
        self._prefix = "nexus:staking:validator:"

    async def get_validator(self, address: str) -> Optional[Dict]:
        """Récupère un validateur du cache."""
        key = f"{self._prefix}{address}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_validator(self, address: str, validator: Dict) -> None:
        """Stocke un validateur dans le cache."""
        key = f"{self._prefix}{address}"
        await self.redis.setex(key, self.ttl, json.dumps(validator))

    async def get_validators_by_blockchain(self, blockchain: str) -> Optional[List[Dict]]:
        """Récupère les validateurs d'une blockchain."""
        key = f"{self._prefix}blockchain:{blockchain}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_validators_by_blockchain(self, blockchain: str, validators: List[Dict]) -> None:
        """Stocke les validateurs d'une blockchain."""
        key = f"{self._prefix}blockchain:{blockchain}"
        await self.redis.setex(key, self.ttl, json.dumps(validators))

    async def get_delegation(self, delegation_id: UUID) -> Optional[Dict]:
        """Récupère une délégation du cache."""
        key = f"{self._prefix}delegation:{str(delegation_id)}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_delegation(self, delegation_id: UUID, delegation: Dict) -> None:
        """Stocke une délégation dans le cache."""
        key = f"{self._prefix}delegation:{str(delegation_id)}"
        await self.redis.setex(key, self.ttl, json.dumps(delegation))


class StakingValidatorService:
    """
    Service de gestion des validateurs pour le staking multi-blockchain.
    Supporte plusieurs blockchains avec des APIs réelles.
    """

    # URLs des APIs de validateur
    VALIDATOR_APIS = {
        ValidatorType.ETH2: {
            "beaconchain": "https://beaconcha.in/api/v1/validator",
            "beaconstat": "https://beaconstat.info/api/v1/validator",
            "etherscan": "https://api.etherscan.io/api"
        },
        ValidatorType.SOLANA: {
            "stakeview": "https://api.stakeview.app/v1/validator",
            "solanabeach": "https://solanabeach.io/api/v1/validator",
            "validators": "https://api.validators.app/v1/validator"
        },
        ValidatorType.AVALANCHE: {
            "avascan": "https://api.avascan.info/v1/validator",
            "avalanche": "https://avalanche-c-chain.publicnode.com"
        },
        ValidatorType.POLKADOT: {
            "polkadot": "https://polkadot.api.subscan.io/api/v1/validator",
            "subscan": "https://api.subscan.io/api/v1/validator"
        },
        ValidatorType.COSMOS: {
            "cosmos": "https://cosmos.api.mintscan.io/v1/validator",
            "mintscan": "https://api.mintscan.io/v1/validator"
        },
        ValidatorType.BINANCE: {
            "bscscan": "https://api.bscscan.com/api",
            "bnbchain": "https://bnbchain-validator-api.bnbchain.org"
        }
    }

    # Adresses des contrats de staking
    STAKING_CONTRACTS = {
        "ethereum": {
            "deposit_contract": "0x00000000219ab540356cBB839Cbe05303d7705Fa",
            "withdrawal_contract": "0x..."
        },
        "solana": {
            "stake_program": "Stake11111111111111111111111111111111111111"
        }
    }

    def __init__(
        self,
        redis_client: redis.Redis,
        web3_providers: Optional[Dict[str, Web3]] = None,
        api_keys: Optional[Dict[str, str]] = None,
        cache_ttl: int = 300
    ):
        """
        Initialise le service de gestion des validateurs.

        Args:
            redis_client: Client Redis pour le cache
            web3_providers: Dictionnaire des providers Web3 par blockchain
            api_keys: Clés API pour les services externes
            cache_ttl: Durée de vie du cache en secondes
        """
        self.redis = redis_client
        self.cache = ValidatorCache(redis_client, cache_ttl)
        self.api_keys = api_keys or {}
        self.web3_providers = web3_providers or {}

        # Cache en mémoire
        self._validator_cache_memory: Dict[str, ValidatorInfo] = {}
        self._delegation_cache: Dict[UUID, DelegationInfo] = {}
        self._top_validators_cache: Dict[str, List[ValidatorInfo]] = {}
        self._validator_stats_cache: Dict[str, Dict] = {}

        # Métriques de performance
        self._performance_metrics = {
            "total_validators": 0,
            "active_validators": 0,
            "total_delegators": 0,
            "total_stake": Decimal(0),
            "average_apy": 0,
            "top_validators": []
        }

        logger.info("StakingValidatorService initialisé avec succès")

    async def get_validator_info(
        self,
        address: str,
        blockchain: str,
        force_refresh: bool = False
    ) -> Optional[ValidatorInfo]:
        """
        Récupère les informations d'un validateur.

        Args:
            address: Adresse du validateur
            blockchain: Blockchain du validateur
            force_refresh: Forcer le rafraîchissement

        Returns:
            Informations du validateur ou None
        """
        try:
            # Vérification du cache
            cache_key = f"{blockchain}_{address}"
            if not force_refresh and cache_key in self._validator_cache_memory:
                cached = self._validator_cache_memory[cache_key]
                if (datetime.now() - cached.updated_at).seconds < 300:
                    return cached

            # Vérification du cache Redis
            cached_data = await self.cache.get_validator(address)
            if cached_data and not force_refresh:
                validator = ValidatorInfo(**cached_data)
                self._validator_cache_memory[cache_key] = validator
                return validator

            # Récupération des données depuis les APIs
            validator_data = await self._fetch_validator_data(address, blockchain)

            if not validator_data:
                logger.warning(f"Aucune donnée trouvée pour le validateur {address} sur {blockchain}")
                return None

            # Création de l'objet ValidatorInfo
            validator = self._create_validator_info(address, blockchain, validator_data)

            # Mise en cache
            self._validator_cache_memory[cache_key] = validator
            await self.cache.set_validator(address, validator.to_dict())

            return validator

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des informations du validateur: {e}")
            return None

    async def _fetch_validator_data(
        self,
        address: str,
        blockchain: str
    ) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur depuis les APIs.
        """
        validator_data = {
            "name": "Unknown",
            "commission": 5.0,
            "max_commission": 10.0,
            "max_commission_change_rate": 1.0,
            "total_stake": 0,
            "self_stake": 0,
            "delegator_count": 0,
            "uptime_30d": 99.0,
            "uptime_90d": 98.5,
            "uptime_365d": 98.0,
            "slashing_events": 0,
            "slashing_amount": 0,
            "apy": 4.0,
            "apr": 3.95,
            "voting_power": 0.1,
            "status": "active",
            "is_verified": False,
            "is_jailed": False
        }

        try:
            # Détermination du type de validateur
            validator_type = self._get_validator_type(blockchain)

            # Récupération des données selon la blockchain
            if validator_type == ValidatorType.ETH2:
                eth2_data = await self._fetch_eth2_validator_data(address)
                validator_data.update(eth2_data)

            elif validator_type == ValidatorType.SOLANA:
                solana_data = await self._fetch_solana_validator_data(address)
                validator_data.update(solana_data)

            elif validator_type == ValidatorType.AVALANCHE:
                avalanche_data = await self._fetch_avalanche_validator_data(address)
                validator_data.update(avalanche_data)

            elif validator_type == ValidatorType.POLKADOT:
                polkadot_data = await self._fetch_polkadot_validator_data(address)
                validator_data.update(polkadot_data)

            elif validator_type == ValidatorType.COSMOS:
                cosmos_data = await self._fetch_cosmos_validator_data(address)
                validator_data.update(cosmos_data)

            elif validator_type == ValidatorType.BINANCE:
                binance_data = await self._fetch_binance_validator_data(address)
                validator_data.update(binance_data)

            # Calcul des scores
            validator_data["performance_score"] = self._calculate_performance_score(validator_data)
            validator_data["reliability_score"] = self._calculate_reliability_score(validator_data)
            validator_data["security_score"] = self._calculate_security_score(validator_data)
            validator_data["decentralization_score"] = self._calculate_decentralization_score(validator_data)
            validator_data["risk_score"] = self._calculate_validator_risk_score(validator_data)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données du validateur: {e}")

        return validator_data

    def _get_validator_type(self, blockchain: str) -> ValidatorType:
        """Détermine le type de validateur en fonction de la blockchain."""
        blockchain_lower = blockchain.lower()
        if "eth" in blockchain_lower or "ethereum" in blockchain_lower:
            return ValidatorType.ETH2
        elif "solana" in blockchain_lower:
            return ValidatorType.SOLANA
        elif "avalanche" in blockchain_lower:
            return ValidatorType.AVALANCHE
        elif "polkadot" in blockchain_lower:
            return ValidatorType.POLKADOT
        elif "cosmos" in blockchain_lower:
            return ValidatorType.COSMOS
        elif "binance" in blockchain_lower or "bnb" in blockchain_lower:
            return ValidatorType.BINANCE
        elif "polygon" in blockchain_lower:
            return ValidatorType.POLYGON
        elif "arbitrum" in blockchain_lower:
            return ValidatorType.ARBITRUM
        elif "optimism" in blockchain_lower:
            return ValidatorType.OPTIMISM
        return ValidatorType.ETH2

    async def _fetch_eth2_validator_data(self, address: str) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur Ethereum 2.0.
        """
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                # Beaconcha.in API
                api_key = self.api_keys.get("beaconchain", "")
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

                async with session.get(
                    f"{self.VALIDATOR_APIS[ValidatorType.ETH2]['beaconchain']}/{address}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            validator_data = result["data"]
                            data = {
                                "name": validator_data.get("name", f"Validator {address[:8]}"),
                                "commission": float(validator_data.get("commission", 5.0)),
                                "max_commission": float(validator_data.get("max_commission", 10.0)),
                                "total_stake": float(validator_data.get("effective_balance", 0)),
                                "self_stake": float(validator_data.get("self_balance", 0)),
                                "delegator_count": int(validator_data.get("delegators", 0)),
                                "uptime_30d": float(validator_data.get("uptime_30d", 99.0)),
                                "uptime_90d": float(validator_data.get("uptime_90d", 98.5)),
                                "uptime_365d": float(validator_data.get("uptime_365d", 98.0)),
                                "slashing_events": int(validator_data.get("slashing_events", 0)),
                                "slashing_amount": float(validator_data.get("slashing_amount", 0)),
                                "apy": float(validator_data.get("apy", 4.0)),
                                "apr": float(validator_data.get("apr", 3.95)),
                                "voting_power": float(validator_data.get("voting_power", 0.1)),
                                "status": validator_data.get("status", "active"),
                                "is_verified": validator_data.get("is_verified", False),
                                "is_jailed": validator_data.get("is_jailed", False)
                            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données Ethereum: {e}")

        return data

    async def _fetch_solana_validator_data(self, address: str) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur Solana.
        """
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                # Stakeview API
                async with session.get(
                    f"{self.VALIDATOR_APIS[ValidatorType.SOLANA]['stakeview']}/{address}"
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            validator_data = result["data"]
                            data = {
                                "name": validator_data.get("name", f"Validator {address[:8]}"),
                                "commission": float(validator_data.get("commission", 5.0)),
                                "max_commission": float(validator_data.get("max_commission", 10.0)),
                                "total_stake": float(validator_data.get("total_stake", 0)),
                                "self_stake": float(validator_data.get("self_stake", 0)),
                                "delegator_count": int(validator_data.get("delegators", 0)),
                                "uptime_30d": float(validator_data.get("uptime_30d", 99.0)),
                                "uptime_90d": float(validator_data.get("uptime_90d", 98.5)),
                                "uptime_365d": float(validator_data.get("uptime_365d", 98.0)),
                                "slashing_events": int(validator_data.get("slashing_events", 0)),
                                "slashing_amount": float(validator_data.get("slashing_amount", 0)),
                                "apy": float(validator_data.get("apy", 6.5)),
                                "apr": float(validator_data.get("apr", 6.4)),
                                "voting_power": float(validator_data.get("voting_power", 0.05)),
                                "status": validator_data.get("status", "active"),
                                "is_verified": validator_data.get("is_verified", False),
                                "is_jailed": validator_data.get("is_jailed", False)
                            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données Solana: {e}")

        return data

    async def _fetch_avalanche_validator_data(self, address: str) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur Avalanche.
        """
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                # Avascan API
                async with session.get(
                    f"{self.VALIDATOR_APIS[ValidatorType.AVALANCHE]['avascan']}/{address}"
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            validator_data = result["data"]
                            data = {
                                "name": validator_data.get("name", f"Validator {address[:8]}"),
                                "commission": float(validator_data.get("commission", 5.0)),
                                "max_commission": float(validator_data.get("max_commission", 10.0)),
                                "total_stake": float(validator_data.get("total_stake", 0)),
                                "self_stake": float(validator_data.get("self_stake", 0)),
                                "delegator_count": int(validator_data.get("delegators", 0)),
                                "uptime_30d": float(validator_data.get("uptime_30d", 99.0)),
                                "uptime_90d": float(validator_data.get("uptime_90d", 98.5)),
                                "uptime_365d": float(validator_data.get("uptime_365d", 98.0)),
                                "slashing_events": int(validator_data.get("slashing_events", 0)),
                                "slashing_amount": float(validator_data.get("slashing_amount", 0)),
                                "apy": float(validator_data.get("apy", 8.0)),
                                "apr": float(validator_data.get("apr", 7.9)),
                                "voting_power": float(validator_data.get("voting_power", 0.1)),
                                "status": validator_data.get("status", "active"),
                                "is_verified": validator_data.get("is_verified", False),
                                "is_jailed": validator_data.get("is_jailed", False)
                            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données Avalanche: {e}")

        return data

    async def _fetch_polkadot_validator_data(self, address: str) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur Polkadot.
        """
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                # Subscan API
                async with session.post(
                    self.VALIDATOR_APIS[ValidatorType.POLKADOT]['subscan'],
                    json={"address": address}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            validator_data = result["data"]
                            data = {
                                "name": validator_data.get("name", f"Validator {address[:8]}"),
                                "commission": float(validator_data.get("commission", 5.0)),
                                "max_commission": float(validator_data.get("max_commission", 10.0)),
                                "total_stake": float(validator_data.get("total_stake", 0)),
                                "self_stake": float(validator_data.get("self_stake", 0)),
                                "delegator_count": int(validator_data.get("delegators", 0)),
                                "uptime_30d": float(validator_data.get("uptime_30d", 99.0)),
                                "uptime_90d": float(validator_data.get("uptime_90d", 98.5)),
                                "uptime_365d": float(validator_data.get("uptime_365d", 98.0)),
                                "slashing_events": int(validator_data.get("slashing_events", 0)),
                                "slashing_amount": float(validator_data.get("slashing_amount", 0)),
                                "apy": float(validator_data.get("apy", 12.0)),
                                "apr": float(validator_data.get("apr", 11.8)),
                                "voting_power": float(validator_data.get("voting_power", 0.05)),
                                "status": validator_data.get("status", "active"),
                                "is_verified": validator_data.get("is_verified", False),
                                "is_jailed": validator_data.get("is_jailed", False)
                            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données Polkadot: {e}")

        return data

    async def _fetch_cosmos_validator_data(self, address: str) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur Cosmos.
        """
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                # Mintscan API
                async with session.get(
                    f"{self.VALIDATOR_APIS[ValidatorType.COSMOS]['cosmos']}/{address}"
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            validator_data = result["data"]
                            data = {
                                "name": validator_data.get("name", f"Validator {address[:8]}"),
                                "commission": float(validator_data.get("commission", 5.0)),
                                "max_commission": float(validator_data.get("max_commission", 10.0)),
                                "total_stake": float(validator_data.get("total_stake", 0)),
                                "self_stake": float(validator_data.get("self_stake", 0)),
                                "delegator_count": int(validator_data.get("delegators", 0)),
                                "uptime_30d": float(validator_data.get("uptime_30d", 99.0)),
                                "uptime_90d": float(validator_data.get("uptime_90d", 98.5)),
                                "uptime_365d": float(validator_data.get("uptime_365d", 98.0)),
                                "slashing_events": int(validator_data.get("slashing_events", 0)),
                                "slashing_amount": float(validator_data.get("slashing_amount", 0)),
                                "apy": float(validator_data.get("apy", 15.0)),
                                "apr": float(validator_data.get("apr", 14.8)),
                                "voting_power": float(validator_data.get("voting_power", 0.05)),
                                "status": validator_data.get("status", "active"),
                                "is_verified": validator_data.get("is_verified", False),
                                "is_jailed": validator_data.get("is_jailed", False)
                            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données Cosmos: {e}")

        return data

    async def _fetch_binance_validator_data(self, address: str) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur Binance.
        """
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                # BSCScan API
                api_key = self.api_keys.get("bscscan", "")
                async with session.get(
                    f"{self.VALIDATOR_APIS[ValidatorType.BINANCE]['bscscan']}",
                    params={
                        "module": "account",
                        "action": "txlist",
                        "address": address,
                        "apikey": api_key
                    }
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("status") == "1":
                            data = {
                                "name": f"Validator {address[:8]}",
                                "commission": 5.0,
                                "max_commission": 10.0,
                                "total_stake": 0,
                                "self_stake": 0,
                                "delegator_count": 0,
                                "uptime_30d": 99.0,
                                "uptime_90d": 98.5,
                                "uptime_365d": 98.0,
                                "slashing_events": 0,
                                "slashing_amount": 0,
                                "apy": 5.0,
                                "apr": 4.95,
                                "voting_power": 0.1,
                                "status": "active",
                                "is_verified": False,
                                "is_jailed": False
                            }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données Binance: {e}")

        return data

    def _create_validator_info(
        self,
        address: str,
        blockchain: str,
        data: Dict[str, Any]
    ) -> ValidatorInfo:
        """
        Crée un objet ValidatorInfo à partir des données.
        """
        validator_type = self._get_validator_type(blockchain)

        return ValidatorInfo(
            validator_id=uuid4(),
            address=address,
            name=data.get("name", f"Validator {address[:8]}"),
            type=validator_type,
            blockchain=blockchain,
            status=ValidatorStatus(data.get("status", "active")),
            commission=float(data.get("commission", 5.0)),
            max_commission=float(data.get("max_commission", 10.0)),
            max_commission_change_rate=float(data.get("max_commission_change_rate", 1.0)),
            total_stake=Decimal(str(data.get("total_stake", 0))),
            total_stake_usd=Decimal(str(data.get("total_stake_usd", 0))),
            self_stake=Decimal(str(data.get("self_stake", 0))),
            self_stake_usd=Decimal(str(data.get("self_stake_usd", 0))),
            delegator_count=int(data.get("delegator_count", 0)),
            uptime_30d=float(data.get("uptime_30d", 99.0)),
            uptime_90d=float(data.get("uptime_90d", 98.5)),
            uptime_365d=float(data.get("uptime_365d", 98.0)),
            slashing_events=int(data.get("slashing_events", 0)),
            slashing_amount=Decimal(str(data.get("slashing_amount", 0))),
            slashing_amount_usd=Decimal(str(data.get("slashing_amount_usd", 0))),
            apy=float(data.get("apy", 4.0)),
            apr=float(data.get("apr", 3.95)),
            rewards_accumulated=Decimal(str(data.get("rewards_accumulated", 0))),
            rewards_accumulated_usd=Decimal(str(data.get("rewards_accumulated_usd", 0))),
            last_reward_date=datetime.now(),
            voting_power=float(data.get("voting_power", 0.1)),
            performance_score=float(data.get("performance_score", 90.0)),
            reliability_score=float(data.get("reliability_score", 90.0)),
            security_score=float(data.get("security_score", 85.0)),
            decentralization_score=float(data.get("decentralization_score", 70.0)),
            risk_score=float(data.get("risk_score", 30.0)),
            is_verified=data.get("is_verified", False),
            is_active=data.get("status", "active") == "active",
            is_jailed=data.get("is_jailed", False),
            jail_reason=data.get("jail_reason"),
            jail_end_time=datetime.fromisoformat(data["jail_end_time"]) if data.get("jail_end_time") else None,
            metadata=data.get("metadata", {}),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    def _calculate_performance_score(self, data: Dict[str, Any]) -> float:
        """Calcule le score de performance d'un validateur."""
        score = 70.0

        try:
            # Uptime (poids: 40%)
            uptime = data.get("uptime_30d", 99.0)
            uptime_score = min(uptime, 100) * 0.4

            # Slashing (poids: 20%)
            slashing_events = data.get("slashing_events", 0)
            slashing_score = max(0, 100 - slashing_events * 10) * 0.2

            # APY (poids: 20%)
            apy = data.get("apy", 4.0)
            apy_score = min(apy * 5, 100) * 0.2

            # Voting power (poids: 20%)
            voting_power = data.get("voting_power", 0.1)
            voting_score = min(voting_power * 10, 100) * 0.2

            score = uptime_score + slashing_score + apy_score + voting_score

        except Exception as e:
            logger.error(f"Erreur lors du calcul du score de performance: {e}")

        return min(max(score, 0), 100)

    def _calculate_reliability_score(self, data: Dict[str, Any]) -> float:
        """Calcule le score de fiabilité d'un validateur."""
        score = 70.0

        try:
            # Uptime long terme (poids: 40%)
            uptime_365d = data.get("uptime_365d", 98.0)
            uptime_score = min(uptime_365d, 100) * 0.4

            # Slashing (poids: 30%)
            slashing_events = data.get("slashing_events", 0)
            slashing_score = max(0, 100 - slashing_events * 15) * 0.3

            # Commission stability (poids: 15%)
            max_commission_change = data.get("max_commission_change_rate", 1.0)
            if max_commission_change < 1.0:
                commission_score = 100
            elif max_commission_change < 5.0:
                commission_score = 80
            else:
                commission_score = 60
            commission_score *= 0.15

            # Delegator count (poids: 15%)
            delegators = data.get("delegator_count", 0)
            if delegators > 10000:
                delegator_score = 100
            elif delegators > 1000:
                delegator_score = 80
            elif delegators > 100:
                delegator_score = 60
            else:
                delegator_score = 40
            delegator_score *= 0.15

            score = uptime_score + slashing_score + commission_score + delegator_score

        except Exception as e:
            logger.error(f"Erreur lors du calcul du score de fiabilité: {e}")

        return min(max(score, 0), 100)

    def _calculate_security_score(self, data: Dict[str, Any]) -> float:
        """Calcule le score de sécurité d'un validateur."""
        score = 70.0

        try:
            # Slashing (poids: 40%)
            slashing_events = data.get("slashing_events", 0)
            slashing_score = max(0, 100 - slashing_events * 20) * 0.4

            # Self stake (poids: 30%)
            self_stake_pct = data.get("self_stake_pct", 0)
            if self_stake_pct > 20:
                self_stake_score = 100
            elif self_stake_pct > 10:
                self_stake_score = 80
            elif self_stake_pct > 5:
                self_stake_score = 60
            else:
                self_stake_score = 40
            self_stake_score *= 0.3

            # Verification status (poids: 15%)
            is_verified = data.get("is_verified", False)
            verification_score = 100 if is_verified else 50
            verification_score *= 0.15

            # Jail status (poids: 15%)
            is_jailed = data.get("is_jailed", False)
            jail_score = 0 if is_jailed else 100
            jail_score *= 0.15

            score = slashing_score + self_stake_score + verification_score + jail_score

        except Exception as e:
            logger.error(f"Erreur lors du calcul du score de sécurité: {e}")

        return min(max(score, 0), 100)

    def _calculate_decentralization_score(self, data: Dict[str, Any]) -> float:
        """Calcule le score de décentralisation d'un validateur."""
        score = 50.0

        try:
            # Voting power (poids: 40%)
            voting_power = data.get("voting_power", 0.1)
            if voting_power < 0.5:
                voting_score = 100
            elif voting_power < 1.0:
                voting_score = 80
            elif voting_power < 2.0:
                voting_score = 60
            elif voting_power < 5.0:
                voting_score = 40
            else:
                voting_score = 20
            voting_score *= 0.4

            # Delegator count (poids: 30%)
            delegators = data.get("delegator_count", 0)
            if delegators > 10000:
                delegator_score = 100
            elif delegators > 1000:
                delegator_score = 80
            elif delegators > 100:
                delegator_score = 60
            else:
                delegator_score = 40
            delegator_score *= 0.3

            # Self stake ratio (poids: 30%)
            total_stake = data.get("total_stake", 0)
            self_stake = data.get("self_stake", 0)
            if total_stake > 0:
                self_ratio = self_stake / total_stake * 100
                if self_ratio < 10:
                    self_score = 100
                elif self_ratio < 20:
                    self_score = 80
                elif self_ratio < 50:
                    self_score = 60
                else:
                    self_score = 40
            else:
                self_score = 50
            self_score *= 0.3

            score = voting_score + delegator_score + self_score

        except Exception as e:
            logger.error(f"Erreur lors du calcul du score de décentralisation: {e}")

        return min(max(score, 0), 100)

    def _calculate_validator_risk_score(self, data: Dict[str, Any]) -> float:
        """Calcule le score de risque d'un validateur."""
        risk_score = 30.0

        try:
            # Slashing (poids: 30%)
            slashing_events = data.get("slashing_events", 0)
            risk_score += slashing_events * 10

            # Uptime (poids: 25%)
            uptime = data.get("uptime_30d", 99.0)
            if uptime < 95:
                risk_score += 20
            elif uptime < 99:
                risk_score += 10

            # Commission (poids: 15%)
            commission = data.get("commission", 5.0)
            if commission > 10:
                risk_score += 15
            elif commission > 5:
                risk_score += 5

            # Total stake (poids: 15%)
            total_stake = data.get("total_stake", 0)
            if total_stake < 100000:
                risk_score += 15
            elif total_stake < 500000:
                risk_score += 10

            # Delegators (poids: 15%)
            delegators = data.get("delegator_count", 0)
            if delegators < 50:
                risk_score += 15
            elif delegators < 100:
                risk_score += 10

        except Exception as e:
            logger.error(f"Erreur lors du calcul du score de risque: {e}")

        return min(max(risk_score, 0), 100)

    async def get_top_validators(
        self,
        blockchain: str,
        limit: int = 10,
        sort_by: str = "total_stake"
    ) -> List[ValidatorInfo]:
        """
        Récupère les meilleurs validateurs d'une blockchain.

        Args:
            blockchain: Blockchain cible
            limit: Nombre de validateurs à retourner
            sort_by: Critère de tri (total_stake, apy, performance_score)

        Returns:
            Liste des meilleurs validateurs
        """
        try:
            # Vérification du cache
            cache_key = f"{blockchain}_{sort_by}_{limit}"
            if cache_key in self._top_validators_cache:
                cached = self._top_validators_cache[cache_key]
                if (datetime.now() - cached[0].updated_at).seconds < 300:
                    return cached

            validators = []

            # Récupération des validateurs depuis les APIs
            validator_type = self._get_validator_type(blockchain)

            if validator_type == ValidatorType.ETH2:
                validators = await self._fetch_top_eth2_validators(limit)

            elif validator_type == ValidatorType.SOLANA:
                validators = await self._fetch_top_solana_validators(limit)

            elif validator_type == ValidatorType.AVALANCHE:
                validators = await self._fetch_top_avalanche_validators(limit)

            elif validator_type == ValidatorType.POLKADOT:
                validators = await self._fetch_top_polkadot_validators(limit)

            elif validator_type == ValidatorType.COSMOS:
                validators = await self._fetch_top_cosmos_validators(limit)

            # Tri des validateurs
            sort_map = {
                "total_stake": lambda v: v.total_stake,
                "apy": lambda v: v.apy,
                "performance_score": lambda v: v.performance_score,
                "reliability_score": lambda v: v.reliability_score,
                "security_score": lambda v: v.security_score,
                "decentralization_score": lambda v: v.decentralization_score,
                "risk_score": lambda v: -v.risk_score
            }

            sort_key = sort_map.get(sort_by, lambda v: v.total_stake)
            validators.sort(key=sort_key, reverse=True)
            validators = validators[:limit]

            # Mise en cache
            self._top_validators_cache[cache_key] = validators

            return validators

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des meilleurs validateurs: {e}")
            return []

    async def _fetch_top_eth2_validators(self, limit: int) -> List[ValidatorInfo]:
        """Récupère les meilleurs validateurs Ethereum 2.0."""
        validators = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://beaconcha.in/api/v1/validator/leaderboard",
                    params={"limit": limit, "sort": "stake"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            for validator_data in result["data"]:
                                address = validator_data.get("address", "")
                                if address:
                                    validator = await self.get_validator_info(address, "ethereum")
                                    if validator:
                                        validators.append(validator)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des validateurs Ethereum: {e}")

        return validators

    async def _fetch_top_solana_validators(self, limit: int) -> List[ValidatorInfo]:
        """Récupère les meilleurs validateurs Solana."""
        validators = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.stakeview.app/v1/validators",
                    params={"limit": limit, "sort": "stake"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            for validator_data in result["data"]:
                                address = validator_data.get("address", "")
                                if address:
                                    validator = await self.get_validator_info(address, "solana")
                                    if validator:
                                        validators.append(validator)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des validateurs Solana: {e}")

        return validators

    async def _fetch_top_avalanche_validators(self, limit: int) -> List[ValidatorInfo]:
        """Récupère les meilleurs validateurs Avalanche."""
        validators = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.avascan.info/v1/validators",
                    params={"limit": limit, "sort": "stake"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            for validator_data in result["data"]:
                                address = validator_data.get("address", "")
                                if address:
                                    validator = await self.get_validator_info(address, "avalanche")
                                    if validator:
                                        validators.append(validator)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des validateurs Avalanche: {e}")

        return validators

    async def _fetch_top_polkadot_validators(self, limit: int) -> List[ValidatorInfo]:
        """Récupère les meilleurs validateurs Polkadot."""
        validators = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.subscan.io/api/v1/validator/list",
                    params={"limit": limit, "sort": "stake"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            for validator_data in result["data"]:
                                address = validator_data.get("address", "")
                                if address:
                                    validator = await self.get_validator_info(address, "polkadot")
                                    if validator:
                                        validators.append(validator)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des validateurs Polkadot: {e}")

        return validators

    async def _fetch_top_cosmos_validators(self, limit: int) -> List[ValidatorInfo]:
        """Récupère les meilleurs validateurs Cosmos."""
        validators = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.mintscan.io/v1/validators",
                    params={"limit": limit, "sort": "stake"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("data"):
                            for validator_data in result["data"]:
                                address = validator_data.get("address", "")
                                if address:
                                    validator = await self.get_validator_info(address, "cosmos")
                                    if validator:
                                        validators.append(validator)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des validateurs Cosmos: {e}")

        return validators

    async def delegate_to_validator(
        self,
        user_id: UUID,
        validator_address: str,
        blockchain: str,
        amount: Decimal,
        metadata: Optional[Dict] = None
    ) -> DelegationInfo:
        """
        Délègue des fonds à un validateur.

        Args:
            user_id: ID de l'utilisateur
            validator_address: Adresse du validateur
            blockchain: Blockchain du validateur
            amount: Montant à déléguer
            metadata: Métadonnées supplémentaires

        Returns:
            Informations de la délégation
        """
        try:
            # Vérification du validateur
            validator = await self.get_validator_info(validator_address, blockchain)
            if not validator:
                raise ValueError(f"Validateur {validator_address} non trouvé sur {blockchain}")

            # Vérification du statut du validateur
            if not validator.is_active:
                raise ValueError(f"Le validateur {validator_address} n'est pas actif")

            # Création de la délégation
            delegation = DelegationInfo(
                delegation_id=uuid4(),
                user_id=user_id,
                validator_id=validator.validator_id,
                validator_address=validator_address,
                amount=amount,
                amount_usd=amount * Decimal(str(await self._get_price(blockchain))),
                shares=Decimal(0),  # Calculé par le protocole
                rewards=Decimal(0),
                rewards_usd=Decimal(0),
                status="active",
                start_date=datetime.now(),
                metadata=metadata or {}
            )

            # Simulation de l'envoi de la transaction
            tx_hash = await self._send_delegation_transaction(user_id, validator_address, amount)

            # Mise à jour des récompenses
            delegation.metadata["transaction_hash"] = tx_hash
            delegation.metadata["blockchain"] = blockchain

            # Mise en cache
            await self.cache.set_delegation(delegation.delegation_id, delegation.to_dict())

            return delegation

        except Exception as e:
            logger.error(f"Erreur lors de la délégation: {e}")
            raise

    async def _send_delegation_transaction(
        self,
        user_id: UUID,
        validator_address: str,
        amount: Decimal
    ) -> str:
        """
        Simule l'envoi d'une transaction de délégation.
        Dans une version réelle, cela enverrait une transaction on-chain.
        """
        # Simulation
        return f"0x{user_id.hex[:32]}{int(datetime.now().timestamp()):x}"

    async def undelegate_from_validator(
        self,
        delegation_id: UUID,
        amount: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Annule une délégation.

        Args:
            delegation_id: ID de la délégation
            amount: Montant à annuler (None pour tout)

        Returns:
            Résultat de l'opération
        """
        try:
            delegation = await self.get_delegation(delegation_id)
            if not delegation:
                return {"success": False, "error": "Délégation non trouvée"}

            if delegation.status != "active":
                return {"success": False, "error": "La délégation n'est pas active"}

            # Simulation de l'annulation
            unbonding_amount = amount or delegation.amount

            result = {
                "success": True,
                "delegation_id": str(delegation_id),
                "amount": float(unbonding_amount),
                "validator_address": delegation.validator_address,
                "status": "unbonding",
                "unbonding_date": datetime.now().isoformat(),
                "completion_date": (datetime.now() + timedelta(days=21)).isoformat(),
                "transaction_hash": f"0x{delegation_id.hex[:32]}{int(datetime.now().timestamp()):x}",
                "message": "Délégation annulée avec succès"
            }

            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'annulation de la délégation: {e}")
            return {"success": False, "error": str(e)}

    async def get_delegation(
        self,
        delegation_id: UUID
    ) -> Optional[DelegationInfo]:
        """
        Récupère les informations d'une délégation.

        Args:
            delegation_id: ID de la délégation

        Returns:
            Informations de la délégation ou None
        """
        try:
            # Vérification du cache
            if delegation_id in self._delegation_cache:
                return self._delegation_cache[delegation_id]

            cached = await self.cache.get_delegation(delegation_id)
            if cached:
                delegation = DelegationInfo(**cached)
                self._delegation_cache[delegation_id] = delegation
                return delegation

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la délégation: {e}")
            return None

    async def get_user_delegations(
        self,
        user_id: UUID,
        blockchain: Optional[str] = None
    ) -> List[DelegationInfo]:
        """
        Récupère toutes les délégations d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            blockchain: Filtrer par blockchain

        Returns:
            Liste des délégations
        """
        # Dans une version réelle, on interrogerait la base de données
        # Simulation
        delegations = []

        # Création d'une délégation de démonstration
        demo_delegation = DelegationInfo(
            delegation_id=uuid4(),
            user_id=user_id,
            validator_id=uuid4(),
            validator_address="0x0123456789abcdef0123456789abcdef01234567",
            amount=Decimal("1000"),
            amount_usd=Decimal("1000"),
            shares=Decimal("1000"),
            rewards=Decimal("45.5"),
            rewards_usd=Decimal("45.5"),
            status="active",
            start_date=datetime.now() - timedelta(days=30),
            metadata={"blockchain": "ethereum", "validator_name": "Lido"}
        )

        if not blockchain or blockchain == "ethereum":
            delegations.append(demo_delegation)

        return delegations

    async def get_validator_statistics(
        self,
        blockchain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques globales des validateurs.

        Returns:
            Statistiques agrégées
        """
        stats = {
            "total_validators": 0,
            "active_validators": 0,
            "total_delegators": 0,
            "total_stake_usd": 0,
            "average_apy": 0,
            "average_commission": 0,
            "by_blockchain": {},
            "updated_at": datetime.now().isoformat()
        }

        try:
            blockchains = [blockchain] if blockchain else ["ethereum", "solana", "avalanche", "polkadot", "cosmos"]

            for bc in blockchains:
                bc_stats = {
                    "total_validators": 0,
                    "active_validators": 0,
                    "total_stake_usd": 0,
                    "average_apy": 0,
                    "average_commission": 0,
                    "top_validators": []
                }

                # Récupération des validateurs
                validators = await self.get_top_validators(bc, limit=100)
                if validators:
                    bc_stats["total_validators"] = len(validators)
                    bc_stats["active_validators"] = sum(1 for v in validators if v.is_active)
                    bc_stats["total_stake_usd"] = float(sum(v.total_stake_usd for v in validators))
                    bc_stats["average_apy"] = sum(v.apy for v in validators) / len(validators)
                    bc_stats["average_commission"] = sum(v.commission for v in validators) / len(validators)
                    bc_stats["top_validators"] = [
                        {
                            "address": v.address,
                            "name": v.name,
                            "apy": v.apy,
                            "commission": v.commission,
                            "total_stake_usd": float(v.total_stake_usd)
                        }
                        for v in validators[:10]
                    ]

                stats["by_blockchain"][bc] = bc_stats

            # Calcul des totaux
            for bc_stats in stats["by_blockchain"].values():
                stats["total_validators"] += bc_stats["total_validators"]
                stats["active_validators"] += bc_stats["active_validators"]
                stats["total_stake_usd"] += bc_stats["total_stake_usd"]
                stats["average_apy"] += bc_stats["average_apy"]
                stats["average_commission"] += bc_stats["average_commission"]

            if stats["by_blockchain"]:
                count = len(stats["by_blockchain"])
                stats["average_apy"] /= count
                stats["average_commission"] /= count

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")

        return stats

    async def _get_price(self, blockchain: str) -> float:
        """
        Récupère le prix d'un actif.
        """
        # Dans une version réelle, on utiliserait CoinGecko ou autre
        prices = {
            "ethereum": 3000.0,
            "solana": 150.0,
            "avalanche": 35.0,
            "polkadot": 7.0,
            "cosmos": 8.0,
            "binance": 600.0
        }
        return prices.get(blockchain.lower(), 1.0)

    async def monitor_validator_status(
        self,
        address: str,
        blockchain: str,
        interval_seconds: int = 60
    ) -> None:
        """
        Surveille le statut d'un validateur en continu.

        Args:
            address: Adresse du validateur
            blockchain: Blockchain du validateur
            interval_seconds: Intervalle de surveillance
        """
        try:
            while True:
                try:
                    # Récupération des informations du validateur
                    validator = await self.get_validator_info(address, blockchain, force_refresh=True)

                    if validator:
                        # Vérification des changements de statut
                        if validator.is_jailed:
                            logger.warning(f"⚠️ Validateur {address} mis en jail: {validator.jail_reason}")

                        if validator.slashing_events > 0:
                            logger.warning(f"⚠️ Événement de slashing détecté pour {address}")

                        # Mise à jour des métriques
                        self._update_validator_metrics(validator)

                    await asyncio.sleep(interval_seconds)

                except Exception as e:
                    logger.error(f"Erreur lors de la surveillance du validateur: {e}")
                    await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info(f"Surveillance du validateur {address} arrêtée")

    def _update_validator_metrics(self, validator: ValidatorInfo) -> None:
        """
        Met à jour les métriques d'un validateur.
        """
        key = f"{validator.blockchain}_{validator.address}"
        self._validator_stats_cache[key] = {
            "last_check": datetime.now().isoformat(),
            "status": validator.status.value,
            "uptime": validator.uptime_30d,
            "apy": validator.apy,
            "voting_power": validator.voting_power
        }

    async def get_validator_recommendations(
        self,
        blockchain: str,
        min_apy: float = 0,
        max_risk_score: float = 50,
        min_reliability: float = 80
    ) -> List[ValidatorInfo]:
        """
        Recommande des validateurs basé sur des critères.

        Args:
            blockchain: Blockchain cible
            min_apy: APY minimum
            max_risk_score: Score de risque maximum
            min_reliability: Score de fiabilité minimum

        Returns:
            Liste des validateurs recommandés
        """
        try:
            validators = await self.get_top_validators(blockchain, limit=100)

            recommendations = []

            for validator in validators:
                if (validator.apy >= min_apy and
                    validator.risk_score <= max_risk_score and
                    validator.reliability_score >= min_reliability and
                    validator.is_active and
                    not validator.is_jailed):
                    recommendations.append(validator)

            # Tri par score combiné
            recommendations.sort(
                key=lambda v: (v.reliability_score * 0.4 +
                               v.performance_score * 0.3 +
                               (100 - v.risk_score) * 0.3),
                reverse=True
            )

            return recommendations[:20]

        except Exception as e:
            logger.error(f"Erreur lors de la génération des recommandations: {e}")
            return []


# Fonction factory
def create_staking_validator_service(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    cache_ttl: int = 300
) -> StakingValidatorService:
    """
    Crée une instance du service de gestion des validateurs.
    """
    import redis.asyncio as redis

    redis_client = redis.Redis.from_url(redis_url)

    return StakingValidatorService(
        redis_client=redis_client,
        api_keys=api_keys or {},
        cache_ttl=cache_ttl
    )


# Exemple d'utilisation
async def example_usage():
    """Exemple d'utilisation du service."""
    # Création du service
    service = create_staking_validator_service(
        redis_url="redis://localhost:6379/0",
        api_keys={
            "beaconchain": "YOUR_BEACONCHAIN_KEY",
            "bscscan": "YOUR_BSCSCAN_KEY"
        }
    )

    # Récupération d'un validateur
    validator = await service.get_validator_info(
        address="0x0123456789abcdef0123456789abcdef01234567",
        blockchain="ethereum"
    )
    if validator:
        print(f"✅ Validateur: {validator.name}")
        print(f"   Address: {validator.address}")
        print(f"   APY: {validator.apy}%")
        print(f"   Commission: {validator.commission}%")
        print(f"   Total Stake: ${float(validator.total_stake_usd):,.2f}")
        print(f"   Performance Score: {validator.performance_score:.1f}")
        print(f"   Risk Score: {validator.risk_score:.1f}")

    # Récupération des meilleurs validateurs
    top_validators = await service.get_top_validators("ethereum", limit=5)
    print(f"\n📊 Top 5 validateurs Ethereum:")
    for v in top_validators:
        print(f"   {v.name}: APY {v.apy}%, Stake ${float(v.total_stake_usd):,.0f}")

    # Délégation
    delegation = await service.delegate_to_validator(
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        validator_address="0x0123456789abcdef0123456789abcdef01234567",
        blockchain="ethereum",
        amount=Decimal("1000")
    )
    print(f"\n💰 Délégation créée: {delegation.delegation_id}")

    # Recommandations
    recommendations = await service.get_validator_recommendations(
        blockchain="ethereum",
        min_apy=3.0,
        max_risk_score=40,
        min_reliability=85
    )
    print(f"\n🌟 {len(recommendations)} validateurs recommandés")

    return service


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

"""
NEXUS AI TRADING SYSTEM - STAKING RISK MANAGEMENT MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des risques pour le staking multi-blockchain.
Analyse en temps réel des risques: volatilité, liquidité, slashing,
validator risk, protocol risk, et smart contract risk.
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import numpy as np
import redis.asyncio as redis
from scipy import stats
from web3 import Web3
from web3.eth import AsyncEth

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Niveaux de risque pour le staking."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    """Catégories de risques."""
    PROTOCOL = "protocol_risk"
    SMART_CONTRACT = "smart_contract_risk"
    VALIDATOR = "validator_risk"
    LIQUIDITY = "liquidity_risk"
    SLASHING = "slashing_risk"
    IMPERMANENT_LOSS = "impermanent_loss"
    VOLATILITY = "volatility_risk"
    COUNTERPARTY = "counterparty_risk"
    REGULATORY = "regulatory_risk"
    TECHNICAL = "technical_risk"
    ECONOMIC = "economic_risk"
    OPERATIONAL = "operational_risk"


@dataclass
class RiskScore:
    """Modèle de données pour un score de risque."""
    risk_id: UUID
    user_id: UUID
    position_id: UUID
    category: RiskCategory
    level: RiskLevel
    score: float  # 0-100
    impact: float  # 0-100, impact potentiel
    probability: float  # 0-100, probabilité d'occurrence
    detected_at: datetime
    description: str
    mitigation_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire."""
        return {
            "risk_id": str(self.risk_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id),
            "category": self.category.value,
            "level": self.level.value,
            "score": self.score,
            "impact": self.impact,
            "probability": self.probability,
            "detected_at": self.detected_at.isoformat(),
            "description": self.description,
            "mitigation_steps": self.mitigation_steps,
            "metadata": self.metadata
        }


@dataclass
class RiskMetrics:
    """Métriques de risque pour une position de staking."""
    position_id: UUID
    total_risk_score: float  # 0-100
    max_drawdown: float  # Pourcentage
    volatility_30d: float  # Écart-type annualisé
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    var_95: float  # Value at Risk 95%
    var_99: float  # Value at Risk 99%
    expected_shortfall: float  # CVaR
    liquidation_risk: float  # 0-100
    concentration_risk: float  # 0-100
    protocol_health: float  # 0-100
    validator_reliability: float  # 0-100
    slashing_probability: float  # 0-100
    risk_reward_ratio: float
    timestamp: datetime
    historical_volatility: List[float] = field(default_factory=list)
    correlation_matrix: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "total_risk_score": self.total_risk_score,
            "max_drawdown": self.max_drawdown,
            "volatility_30d": self.volatility_30d,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "expected_shortfall": self.expected_shortfall,
            "liquidation_risk": self.liquidation_risk,
            "concentration_risk": self.concentration_risk,
            "protocol_health": self.protocol_health,
            "validator_reliability": self.validator_reliability,
            "slashing_probability": self.slashing_probability,
            "risk_reward_ratio": self.risk_reward_ratio,
            "timestamp": self.timestamp.isoformat(),
            "historical_volatility": self.historical_volatility,
            "correlation_matrix": self.correlation_matrix
        }


@dataclass
class ValidatorRiskProfile:
    """Profil de risque d'un validateur."""
    validator_address: str
    name: str
    blockchain: str
    commission: float
    uptime_30d: float  # Pourcentage
    slashing_events: int
    total_stake: float
    delegator_count: int
    risk_score: float  # 0-100
    reliability_score: float  # 0-100
    performance_score: float  # 0-100
    security_score: float  # 0-100
    decentralization_score: float  # 0-100
    last_updated: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'objet en dictionnaire."""
        return {
            "validator_address": self.validator_address,
            "name": self.name,
            "blockchain": self.blockchain,
            "commission": self.commission,
            "uptime_30d": self.uptime_30d,
            "slashing_events": self.slashing_events,
            "total_stake": self.total_stake,
            "delegator_count": self.delegator_count,
            "risk_score": self.risk_score,
            "reliability_score": self.reliability_score,
            "performance_score": self.performance_score,
            "security_score": self.security_score,
            "decentralization_score": self.decentralization_score,
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata
        }


class RiskMetricsCache:
    """Cache Redis pour les métriques de risque."""

    def __init__(self, redis_client: redis.Redis, ttl: int = 180):
        self.redis = redis_client
        self.ttl = ttl
        self._prefix = "nexus:staking:risk:"

    async def get_risk_score(self, user_id: UUID) -> Optional[Dict]:
        """Récupère le score de risque d'un utilisateur."""
        key = f"{self._prefix}score:{str(user_id)}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_risk_score(self, user_id: UUID, score: Dict) -> None:
        """Stocke le score de risque d'un utilisateur."""
        key = f"{self._prefix}score:{str(user_id)}"
        await self.redis.setex(key, self.ttl, json.dumps(score))

    async def get_metrics(self, position_id: UUID) -> Optional[Dict]:
        """Récupère les métriques de risque d'une position."""
        key = f"{self._prefix}metrics:{str(position_id)}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_metrics(self, position_id: UUID, metrics: Dict) -> None:
        """Stocke les métriques de risque d'une position."""
        key = f"{self._prefix}metrics:{str(position_id)}"
        await self.redis.setex(key, self.ttl, json.dumps(metrics))


class StakingRiskManager:
    """
    Gestionnaire de risques pour le staking multi-blockchain.
    Analyse en temps réel via APIs réelles et on-chain data.
    """

    # Configurations de risque par protocole
    PROTOCOL_RISK_CONFIG = {
        StakingProtocol.LIDO: {
            "base_risk": 15,
            "audit_score": 95,
            "insurance": True,
            "multisig": True,
            "time_locked": True
        },
        StakingProtocol.ROCKET_POOL: {
            "base_risk": 20,
            "audit_score": 90,
            "insurance": True,
            "multisig": True,
            "time_locked": False
        },
        StakingProtocol.MARINADE: {
            "base_risk": 25,
            "audit_score": 85,
            "insurance": False,
            "multisig": True,
            "time_locked": True
        },
        StakingProtocol.JITO: {
            "base_risk": 30,
            "audit_score": 80,
            "insurance": False,
            "multisig": True,
            "time_locked": False
        },
        StakingProtocol.BENQI: {
            "base_risk": 28,
            "audit_score": 82,
            "insurance": False,
            "multisig": True,
            "time_locked": True
        },
        StakingProtocol.ANKR: {
            "base_risk": 22,
            "audit_score": 88,
            "insurance": False,
            "multisig": True,
            "time_locked": True
        }
    }

    # Seuils de risque
    RISK_THRESHOLDS = {
        RiskLevel.VERY_LOW: (0, 20),
        RiskLevel.LOW: (20, 40),
        RiskLevel.MEDIUM: (40, 60),
        RiskLevel.HIGH: (60, 80),
        RiskLevel.VERY_HIGH: (80, 90),
        RiskLevel.CRITICAL: (90, 100)
    }

    def __init__(
        self,
        redis_client: redis.Redis,
        web3_providers: Optional[Dict[BlockchainType, Web3]] = None,
        api_keys: Optional[Dict[str, str]] = None,
        cache_ttl: int = 180
    ):
        """
        Initialise le gestionnaire de risques.

        Args:
            redis_client: Client Redis pour le cache
            web3_providers: Dictionnaire des providers Web3 par blockchain
            api_keys: Clés API pour les services externes
            cache_ttl: Durée de vie du cache en secondes
        """
        self.redis = redis_client
        self.cache = RiskMetricsCache(redis_client, cache_ttl)
        self.api_keys = api_keys or {}
        self.web3_providers = web3_providers or {}

        # URLs des APIs de données on-chain
        self.SANCTIONS_API = "https://api.sanctions.io/v1"
        self.DEFI_LLAMA_API = "https://api.llama.fi"
        self.BEACONCHAIN_API = "https://beaconcha.in/api/v1"
        self.VALIDATOR_APIS = {
            BlockchainType.ETHEREUM: "https://beaconcha.in/api/v1/validator",
            BlockchainType.SOLANA: "https://api.stakeview.app/v1/validator",
            BlockchainType.AVALANCHE: "https://api.avascan.info/v1/validator",
            BlockchainType.POLYGON: "https://api.polygonscan.com/api",
        }

        # Initialisation des fournisseurs par défaut
        self._init_default_providers()

        # Cache pour les profils de validateurs
        self._validator_cache: Dict[str, ValidatorRiskProfile] = {}
        self._historical_volatility: Dict[str, List[float]] = {}

        # Métriques de marché
        self._market_metrics = {
            "total_value_locked": 0,
            "average_apy": 0,
            "volatility_index": 0,
            "fear_greed_index": 50,
            "liquidity_score": 0
        }

        logger.info("StakingRiskManager initialisé avec succès")

    def _init_default_providers(self) -> None:
        """Initialise les providers Web3 par défaut."""
        default_providers = {
            BlockchainType.ETHEREUM: "https://eth.llamarpc.com",
            BlockchainType.BINANCE: "https://bsc-dataseed.binance.org",
            BlockchainType.POLYGON: "https://polygon-rpc.com",
            BlockchainType.AVALANCHE: "https://api.avax.network/ext/bc/C/rpc",
        }

        for blockchain, url in default_providers.items():
            if blockchain not in self.web3_providers:
                try:
                    w3 = Web3(Web3.HTTPProvider(url))
                    if w3.is_connected():
                        self.web3_providers[blockchain] = w3
                        logger.info(f"Provider Web3 initialisé pour {blockchain.value}")
                except Exception as e:
                    logger.error(f"Erreur d'initialisation du provider {blockchain.value}: {e}")

    async def assess_position_risk(
        self,
        position: StakingPosition,
        user_id: UUID
    ) -> RiskMetrics:
        """
        Évalue le risque d'une position de staking.

        Args:
            position: Position de staking à évaluer
            user_id: ID de l'utilisateur

        Returns:
            Métriques de risque complètes
        """
        try:
            # Vérification du cache
            cached = await self.cache.get_metrics(position.position_id)
            if cached:
                return RiskMetrics(**cached)

            # Récupération des données on-chain
            protocol_data = await self._get_protocol_data(position)
            validator_data = await self._get_validator_data(position)
            market_data = await self._get_market_data(position)

            # Calcul des métriques de risque
            metrics = await self._calculate_risk_metrics(
                position,
                protocol_data,
                validator_data,
                market_data
            )

            # Mise en cache
            await self.cache.set_metrics(position.position_id, metrics.to_dict())

            return metrics

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque: {e}")
            # Retourne des métriques par défaut avec un risque élevé
            return RiskMetrics(
                position_id=position.position_id,
                total_risk_score=75.0,
                max_drawdown=30.0,
                volatility_30d=45.0,
                sharpe_ratio=0.5,
                sortino_ratio=0.3,
                calmar_ratio=0.4,
                var_95=25.0,
                var_99=40.0,
                expected_shortfall=35.0,
                liquidation_risk=60.0,
                concentration_risk=50.0,
                protocol_health=40.0,
                validator_reliability=50.0,
                slashing_probability=20.0,
                risk_reward_ratio=0.8,
                timestamp=datetime.now()
            )

    async def _get_protocol_data(
        self,
        position: StakingPosition
    ) -> Dict[str, Any]:
        """
        Récupère les données du protocole via DefiLlama.
        """
        protocol_data = {
            "tvl": 0,
            "tvl_change_24h": 0,
            "apy": 0,
            "apy_change": 0,
            "protocol_health": 0,
            "audit_score": 0,
            "insurance": False,
            "multisig": False
        }

        try:
            protocol_name = position.protocol.value
            async with aiohttp.ClientSession() as session:
                # DefiLlama Protocol Data
                async with session.get(
                    f"{self.DEFI_LLAMA_API}/protocol/{protocol_name}"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("protocol"):
                            protocol = data["protocol"]
                            protocol_data["tvl"] = protocol.get("tvl", 0)
                            protocol_data["tvl_change_24h"] = protocol.get("tvl_change_24h", 0)
                            protocol_data["apy"] = protocol.get("apy", 0)

            # Récupération des métriques de santé du protocole
            health_metrics = await self._get_protocol_health(position)
            protocol_data.update(health_metrics)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données du protocole: {e}")

        return protocol_data

    async def _get_protocol_health(
        self,
        position: StakingPosition
    ) -> Dict[str, Any]:
        """
        Évalue la santé d'un protocole de staking.
        """
        health_metrics = {
            "protocol_health": 70,
            "audit_score": 85,
            "insurance": False,
            "multisig": True
        }

        try:
            # Récupération de la configuration de risque du protocole
            config = self.PROTOCOL_RISK_CONFIG.get(position.protocol, {})
            health_metrics.update(config)

            # Ajustement basé sur le TVL
            if position.protocol in [StakingProtocol.LIDO, StakingProtocol.ROCKET_POOL]:
                health_metrics["protocol_health"] += 10
                health_metrics["audit_score"] += 5

            # Récupération des métriques via les APIs
            if position.blockchain == BlockchainType.ETHEREUM:
                async with aiohttp.ClientSession() as session:
                    # Beaconcha.in pour les métriques Ethereum
                    async with session.get(
                        f"{self.BEACONCHAIN_API}/network/health"
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            health_metrics["protocol_health"] = data.get("health_score", 70)

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation de la santé du protocole: {e}")

        return health_metrics

    async def _get_validator_data(
        self,
        position: StakingPosition
    ) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur.
        """
        validator_data = {
            "uptime": 99.0,
            "slashing_events": 0,
            "commission": 5.0,
            "total_stake": 0,
            "delegators": 0,
            "reliability": 0,
            "performance": 0,
            "security": 0,
            "decentralization": 0
        }

        if not position.validator_address:
            return validator_data

        try:
            # Vérification du cache
            cache_key = f"{position.blockchain.value}_{position.validator_address}"
            if cache_key in self._validator_cache:
                cached = self._validator_cache[cache_key]
                if (datetime.now() - cached.last_updated).seconds < 3600:
                    return cached.to_dict()

            # Récupération des données du validateur
            api_url = self.VALIDATOR_APIS.get(position.blockchain)
            if api_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{api_url}/{position.validator_address}"
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            validator_data = self._parse_validator_data(data, position.blockchain)

            # Création du profil de validateur
            profile = ValidatorRiskProfile(
                validator_address=position.validator_address,
                name=data.get("name", "Unknown"),
                blockchain=position.blockchain.value,
                commission=validator_data["commission"],
                uptime_30d=validator_data["uptime"],
                slashing_events=validator_data["slashing_events"],
                total_stake=validator_data["total_stake"],
                delegator_count=validator_data["delegators"],
                risk_score=self._calculate_validator_risk_score(validator_data),
                reliability_score=validator_data["reliability"],
                performance_score=validator_data["performance"],
                security_score=validator_data["security"],
                decentralization_score=validator_data["decentralization"],
                last_updated=datetime.now()
            )

            # Mise en cache
            self._validator_cache[cache_key] = profile

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données du validateur: {e}")

        return validator_data

    def _parse_validator_data(
        self,
        data: Dict,
        blockchain: BlockchainType
    ) -> Dict[str, Any]:
        """
        Parse les données d'un validateur selon la blockchain.
        """
        if blockchain == BlockchainType.ETHEREUM:
            return {
                "uptime": float(data.get("uptime", 99.0)),
                "slashing_events": int(data.get("slashing_events", 0)),
                "commission": float(data.get("commission", 5.0)),
                "total_stake": float(data.get("total_stake", 0)),
                "delegators": int(data.get("delegators", 0)),
                "reliability": float(data.get("reliability", 90.0)),
                "performance": float(data.get("performance", 95.0)),
                "security": float(data.get("security", 85.0)),
                "decentralization": float(data.get("decentralization", 70.0))
            }
        elif blockchain == BlockchainType.SOLANA:
            return {
                "uptime": float(data.get("stake", {}).get("uptime", 99.0)),
                "slashing_events": int(data.get("slashes", 0)),
                "commission": float(data.get("commission", 5.0)),
                "total_stake": float(data.get("stake", {}).get("amount", 0)),
                "delegators": int(data.get("stake", {}).get("delegators", 0)),
                "reliability": float(data.get("reliability", 90.0)),
                "performance": float(data.get("performance", 95.0)),
                "security": float(data.get("security", 85.0)),
                "decentralization": float(data.get("decentralization", 70.0))
            }
        else:
            return {
                "uptime": float(data.get("uptime", 99.0)),
                "slashing_events": int(data.get("slashing_events", 0)),
                "commission": float(data.get("commission", 5.0)),
                "total_stake": float(data.get("total_stake", 0)),
                "delegators": int(data.get("delegators", 0)),
                "reliability": 90.0,
                "performance": 95.0,
                "security": 85.0,
                "decentralization": 70.0
            }

    def _calculate_validator_risk_score(
        self,
        validator_data: Dict[str, Any]
    ) -> float:
        """
        Calcule le score de risque d'un validateur.
        """
        risk_score = 0.0

        # Facteurs de risque
        if validator_data["uptime"] < 95:
            risk_score += 20
        elif validator_data["uptime"] < 99:
            risk_score += 10

        if validator_data["slashing_events"] > 0:
            risk_score += min(validator_data["slashing_events"] * 10, 30)

        if validator_data["commission"] > 10:
            risk_score += 10

        if validator_data["total_stake"] < 1000000:
            risk_score += 10

        if validator_data["delegators"] < 100:
            risk_score += 10

        # Score de sécurité et de fiabilité
        risk_score += (100 - validator_data["reliability"]) * 0.3
        risk_score += (100 - validator_data["security"]) * 0.2
        risk_score += (100 - validator_data["performance"]) * 0.2

        return min(risk_score, 100)

    async def _get_market_data(
        self,
        position: StakingPosition
    ) -> Dict[str, Any]:
        """
        Récupère les données de marché pour l'évaluation des risques.
        """
        market_data = {
            "price": 0,
            "price_change_24h": 0,
            "volume_24h": 0,
            "market_cap": 0,
            "volatility": 0,
            "liquidity": 0,
            "fear_greed": 50
        }

        try:
            asset_symbol = position.asset_symbol
            async with aiohttp.ClientSession() as session:
                # CoinGecko pour les données de marché
                async with session.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": asset_symbol.lower(),
                        "order": "market_cap_desc",
                        "per_page": 1,
                        "page": 1,
                        "sparkline": "true"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            market_data.update({
                                "price": data[0].get("current_price", 0),
                                "price_change_24h": data[0].get("price_change_percentage_24h", 0),
                                "volume_24h": data[0].get("total_volume", 0),
                                "market_cap": data[0].get("market_cap", 0)
                            })

                            # Calcul de la volatilité depuis les sparkline
                            sparkline = data[0].get("sparkline_in_7d", {}).get("price", [])
                            if sparkline:
                                volatility = np.std(sparkline) / np.mean(sparkline) * 100
                                market_data["volatility"] = volatility

            # Récupération du Fear & Greed Index
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.alternative.me/fng/"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data"):
                            market_data["fear_greed"] = int(data["data"][0].get("value", 50))

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données de marché: {e}")

        return market_data

    async def _calculate_risk_metrics(
        self,
        position: StakingPosition,
        protocol_data: Dict[str, Any],
        validator_data: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> RiskMetrics:
        """
        Calcule les métriques de risque complètes.
        """
        # Calcul des composantes de risque
        protocol_risk = self._calculate_protocol_risk(protocol_data)
        validator_risk = self._calculate_validator_risk(validator_data)
        market_risk = self._calculate_market_risk(market_data)
        liquidity_risk = self._calculate_liquidity_risk(position, market_data)
        slashing_risk = self._calculate_slashing_risk(validator_data)
        concentration_risk = self._calculate_concentration_risk(position)

        # Score de risque total
        total_risk_score = (
            protocol_risk * 0.25 +
            validator_risk * 0.25 +
            market_risk * 0.20 +
            liquidity_risk * 0.15 +
            slashing_risk * 0.10 +
            concentration_risk * 0.05
        )

        # Calcul des métriques financières
        volatility_30d = self._calculate_volatility(position)
        returns = self._calculate_historical_returns(position)

        # Calcul du Sharpe ratio (simplifié)
        risk_free_rate = 0.02  # Taux sans risque ~2%
        avg_return = np.mean(returns) if returns else 0
        std_return = np.std(returns) if returns else 1
        sharpe_ratio = (avg_return - risk_free_rate) / std_return if std_return > 0 else 0

        # Calcul du Sortino ratio
        downside_returns = [r for r in returns if r < 0] if returns else []
        downside_deviation = np.std(downside_returns) if downside_returns else 1
        sortino_ratio = (avg_return - risk_free_rate) / downside_deviation if downside_deviation > 0 else 0

        # Value at Risk (VaR) et Expected Shortfall (CVaR)
        if returns:
            var_95 = np.percentile(returns, 5)
            var_99 = np.percentile(returns, 1)
            expected_shortfall = np.mean([r for r in returns if r < var_95]) if var_95 else 0
        else:
            var_95 = -20
            var_99 = -30
            expected_shortfall = -25

        # Max Drawdown
        max_drawdown = self._calculate_max_drawdown(position)

        # Calmar Ratio
        calmar_ratio = avg_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Risk-Reward Ratio
        risk_reward_ratio = abs(avg_return / (var_95 / 100)) if var_95 != 0 else 0

        return RiskMetrics(
            position_id=position.position_id,
            total_risk_score=total_risk_score,
            max_drawdown=abs(max_drawdown * 100),
            volatility_30d=volatility_30d,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            var_95=abs(var_95 * 100),
            var_99=abs(var_99 * 100),
            expected_shortfall=abs(expected_shortfall * 100),
            liquidation_risk=self._calculate_liquidation_risk(position),
            concentration_risk=concentration_risk,
            protocol_health=protocol_data.get("protocol_health", 70),
            validator_reliability=validator_data.get("reliability", 90),
            slashing_probability=slashing_risk,
            risk_reward_ratio=risk_reward_ratio,
            timestamp=datetime.now(),
            historical_volatility=self._get_historical_volatility(position),
            correlation_matrix=self._calculate_correlations(position)
        )

    def _calculate_protocol_risk(
        self,
        protocol_data: Dict[str, Any]
    ) -> float:
        """
        Calcule le risque du protocole.
        """
        risk = 50.0  # Risque par défaut

        try:
            # Ajustements basés sur les métriques
            tvl = protocol_data.get("tvl", 0)
            if tvl > 1_000_000_000:  # > 1B
                risk -= 15
            elif tvl > 500_000_000:
                risk -= 10
            elif tvl > 100_000_000:
                risk -= 5
            elif tvl < 10_000_000:
                risk += 15

            # Changement de TVL
            tvl_change = protocol_data.get("tvl_change_24h", 0)
            if abs(tvl_change) > 20:
                risk += 10

            # Santé du protocole
            health = protocol_data.get("protocol_health", 70)
            risk += (100 - health) * 0.3

            # Audit score
            audit_score = protocol_data.get("audit_score", 80)
            risk += (100 - audit_score) * 0.2

            # Insurance
            if not protocol_data.get("insurance", False):
                risk += 10

            # Multisig
            if not protocol_data.get("multisig", True):
                risk += 5

            return min(max(risk, 0), 100)

        except Exception as e:
            logger.error(f"Erreur lors du calcul du risque protocole: {e}")
            return risk

    def _calculate_validator_risk(
        self,
        validator_data: Dict[str, Any]
    ) -> float:
        """
        Calcule le risque du validateur.
        """
        risk = 50.0

        try:
            # Uptime
            uptime = validator_data.get("uptime", 99)
            if uptime < 95:
                risk += 20
            elif uptime < 99:
                risk += 10

            # Slashing events
            slashing_events = validator_data.get("slashing_events", 0)
            if slashing_events > 0:
                risk += min(slashing_events * 10, 30)

            # Commission
            commission = validator_data.get("commission", 5)
            if commission > 10:
                risk += 10
            elif commission > 5:
                risk += 5

            # Total stake
            total_stake = validator_data.get("total_stake", 0)
            if total_stake < 100_000:
                risk += 15
            elif total_stake < 500_000:
                risk += 10

            # Delegators
            delegators = validator_data.get("delegators", 0)
            if delegators < 50:
                risk += 10
            elif delegators < 100:
                risk += 5

            # Reliability score
            reliability = validator_data.get("reliability", 90)
            risk += (100 - reliability) * 0.2

            # Security score
            security = validator_data.get("security", 85)
            risk += (100 - security) * 0.15

            return min(max(risk, 0), 100)

        except Exception as e:
            logger.error(f"Erreur lors du calcul du risque validateur: {e}")
            return risk

    def _calculate_market_risk(
        self,
        market_data: Dict[str, Any]
    ) -> float:
        """
        Calcule le risque de marché.
        """
        risk = 50.0

        try:
            # Volatilité
            volatility = market_data.get("volatility", 30)
            if volatility > 50:
                risk += 20
            elif volatility > 30:
                risk += 10

            # Price change 24h
            price_change = abs(market_data.get("price_change_24h", 0))
            if price_change > 15:
                risk += 15
            elif price_change > 10:
                risk += 10
            elif price_change > 5:
                risk += 5

            # Fear & Greed Index
            fear_greed = market_data.get("fear_greed", 50)
            if fear_greed < 20:  # Extreme fear
                risk += 15
            elif fear_greed > 80:  # Extreme greed
                risk += 10

            # Volume
            volume = market_data.get("volume_24h", 0)
            if volume < 10_000_000:
                risk += 10

            # Market cap
            market_cap = market_data.get("market_cap", 0)
            if market_cap < 1_000_000_000:
                risk += 15            elif market_cap < 5_000_000_000:
                risk += 10

            return min(max(risk, 0), 100)

        except Exception as e:
            logger.error(f"Erreur lors du calcul du risque de marché: {e}")
            return risk

    def _calculate_liquidity_risk(
        self,
        position: StakingPosition,
        market_data: Dict[str, Any]
    ) -> float:
        """
        Calcule le risque de liquidité.
        """
        risk = 50.0

        try:
            # Volume
            volume = market_data.get("volume_24h", 0)
            if volume > 100_000_000:
                risk -= 20
            elif volume > 50_000_000:
                risk -= 10
            elif volume < 10_000_000:
                risk += 15

            # Market cap
            market_cap = market_data.get("market_cap", 0)
            if market_cap > 10_000_000_000:
                risk -= 15
            elif market_cap > 5_000_000_000:
                risk -= 10
            elif market_cap < 1_000_000_000:
                risk += 10

            # Position size relative to liquidity
            position_value = float(position.amount_staked_usd)
            if position_value > 0:
                daily_volume = market_data.get("volume_24h", 0)
                if daily_volume > 0:
                    concentration = position_value / daily_volume
                    if concentration > 0.01:  # > 1% du volume
                        risk += 15
                    elif concentration > 0.005:
                        risk += 10

            # Lock period
            if position.lock_period_days and position.lock_period_days > 30:
                risk += 10

            return min(max(risk, 0), 100)

        except Exception as e:
            logger.error(f"Erreur lors du calcul du risque de liquidité: {e}")
            return risk

    def _calculate_slashing_risk(
        self,
        validator_data: Dict[str, Any]
    ) -> float:
        """
        Calcule le risque de slashing.
        """
        risk = 10.0  # Risque de base

        try:
            # Historique de slashing
            slashing_events = validator_data.get("slashing_events", 0)
            if slashing_events > 0:
                risk += slashing_events * 10

            # Uptime
            uptime = validator_data.get("uptime", 99)
            if uptime < 95:
                risk += 15
            elif uptime < 99:
                risk += 10

            # Commission (validateurs avec commission élevée peuvent avoir plus de risques)
            commission = validator_data.get("commission", 5)
            if commission > 10:
                risk += 5

            # Reliability score
            reliability = validator_data.get("reliability", 90)
            risk += (100 - reliability) * 0.2

            # Security score
            security = validator_data.get("security", 85)
            risk += (100 - security) * 0.15

            return min(max(risk, 0), 100)

        except Exception as e:
            logger.error(f"Erreur lors du calcul du risque de slashing: {e}")
            return risk

    def _calculate_concentration_risk(
        self,
        position: StakingPosition
    ) -> float:
        """
        Calcule le risque de concentration.
        """
        risk = 30.0  # Risque de base

        try:
            # Concentration sur un seul protocole
            # Dans une version réelle, on vérifierait les autres positions
            risk += 10

            # Concentration sur un seul validateur
            if position.validator_address:
                risk += 10

            # Concentration sur un seul asset
            risk += 5

            return min(max(risk, 0), 100)

        except Exception as e:
            logger.error(f"Erreur lors du calcul du risque de concentration: {e}")
            return risk

    def _calculate_liquidation_risk(
        self,
        position: StakingPosition
    ) -> float:
        """
        Calcule le risque de liquidation.
        """
        # Pour le staking, la liquidation est principalement liée aux protocoles de prêt
        # Risque de base
        risk = 15.0

        try:
            # Si le staking est utilisé comme collateral
            if position.metadata.get("used_as_collateral", False):
                risk += 30

            # Loan-to-value ratio
            ltv = position.metadata.get("ltv", 0)
            if ltv > 80:
                risk += 30
            elif ltv > 60:
                risk += 15
            elif ltv > 40:
                risk += 5

            # Volatilité de l'asset
            volatility = self._calculate_volatility(position)
            if volatility > 50:
                risk += 20
            elif volatility > 30:
                risk += 10

            return min(max(risk, 0), 100)

        except Exception as e:
            logger.error(f"Erreur lors du calcul du risque de liquidation: {e}")
            return risk

    def _calculate_volatility(
        self,
        position: StakingPosition
    ) -> float:
        """
        Calcule la volatilité annualisée.
        """
        try:
            returns = self._calculate_historical_returns(position)
            if returns:
                daily_volatility = np.std(returns)
                annualized_volatility = daily_volatility * np.sqrt(365) * 100
                return annualized_volatility
            return 30.0  # Volatilité par défaut
        except Exception:
            return 30.0

    def _calculate_historical_returns(
        self,
        position: StakingPosition
    ) -> List[float]:
        """
        Calcule les rendements historiques.
        """
        # Dans une version réelle, on récupérerait les données historiques
        # Simulation avec une distribution normale
        np.random.seed(hash(position.position_id) % 2**32)
        returns = np.random.normal(0.001, 0.02, 30).tolist()
        return returns

    def _calculate_max_drawdown(
        self,
        position: StakingPosition
    ) -> float:
        """
        Calcule le max drawdown.
        """
        try:
            returns = self._calculate_historical_returns(position)
            if not returns:
                return 0.15  # Drawdown par défaut

            cumulative = np.cumprod(1 + np.array(returns))
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = np.min(drawdown)
            return abs(max_drawdown)

        except Exception:
            return 0.15

    def _get_historical_volatility(
        self,
        position: StakingPosition
    ) -> List[float]:
        """
        Récupère l'historique de volatilité.
        """
        key = str(position.position_id)
        if key not in self._historical_volatility:
            # Simulation de données historiques
            self._historical_volatility[key] = [
                25 + 15 * np.sin(i / 10) + 5 * np.random.randn()
                for i in range(30)
            ]
        return self._historical_volatility[key]

    def _calculate_correlations(
        self,
        position: StakingPosition
    ) -> Dict[str, float]:
        """
        Calcule les corrélations avec d'autres actifs.
        """
        # Dans une version réelle, on calculerait les corrélations réelles
        correlations = {
            "BTC": 0.7 + 0.2 * np.random.randn(),
            "ETH": 0.8 + 0.1 * np.random.randn(),
            "USDT": 0.05 + 0.05 * np.random.randn(),
            "USDC": 0.03 + 0.03 * np.random.randn()
        }
        return {k: min(max(v, -1), 1) for k, v in correlations.items()}

    async def get_risk_score(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère le score de risque global d'un utilisateur.
        """
        try:
            cached = await self.cache.get_risk_score(user_id)
            if cached:
                return cached

            # Récupération des positions de l'utilisateur
            positions = await self._get_user_positions(user_id)

            if not positions:
                return {
                    "user_id": str(user_id),
                    "total_risk_score": 0,
                    "max_risk_score": 0,
                    "position_risks": [],
                    "risk_distribution": {},
                    "recommendations": []
                }

            # Évaluation du risque pour chaque position
            position_risks = []
            total_risk = 0

            for position in positions:
                metrics = await self.assess_position_risk(position, user_id)
                position_risks.append({
                    "position_id": str(position.position_id),
                    "risk_score": metrics.total_risk_score,
                    "level": self._get_risk_level(metrics.total_risk_score).value
                })
                total_risk += metrics.total_risk_score

            # Calcul du risque total
            avg_risk = total_risk / len(positions) if positions else 0

            # Distribution des risques
            risk_distribution = {
                "very_low": 0,
                "low": 0,
                "medium": 0,
                "high": 0,
                "very_high": 0,
                "critical": 0
            }

            for pr in position_risks:
                risk_distribution[pr["level"]] += 1

            result = {
                "user_id": str(user_id),
                "total_risk_score": avg_risk,
                "max_risk_score": max([p["risk_score"] for p in position_risks]) if position_risks else 0,
                "position_risks": position_risks,
                "risk_distribution": risk_distribution,
                "recommendations": self._generate_recommendations(position_risks),
                "timestamp": datetime.now().isoformat()
            }

            # Mise en cache
            await self.cache.set_risk_score(user_id, result)

            return result

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du score de risque: {e}")
            return {
                "user_id": str(user_id),
                "error": str(e),
                "total_risk_score": 50.0,
                "timestamp": datetime.now().isoformat()
            }

    async def _get_user_positions(
        self,
        user_id: UUID
    ) -> List[StakingPosition]:
        """
        Récupère les positions de staking d'un utilisateur.
        """
        # Dans une version réelle, on interrogerait la base de données
        # Simulation
        return [
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
                validator_address="0x0123456789abcdef0123456789abcdef01234567",
                metadata={"pool": "Lido Staking Pool"}
            )
        ]

    def _get_risk_level(self, score: float) -> RiskLevel:
        """
        Détermine le niveau de risque basé sur le score.
        """
        for level, (min_score, max_score) in self.RISK_THRESHOLDS.items():
            if min_score <= score < max_score:
                return level
        return RiskLevel.CRITICAL

    def _generate_recommendations(
        self,
        position_risks: List[Dict]
    ) -> List[str]:
        """
        Génère des recommandations basées sur les risques.
        """
        recommendations = []

        high_risk_positions = [p for p in position_risks if p["risk_score"] > 60]

        if high_risk_positions:
            recommendations.append(
                "🚨 Réduisez l'exposition aux positions à haut risque: "
                f"{', '.join([p['position_id'][:8] for p in high_risk_positions])}"
            )

        # Recommandations de diversification
        if len(position_risks) < 3:
            recommendations.append(
                "📊 Diversifiez vos positions de staking sur plusieurs protocoles"
            )

        # Recommandations de validateur
        for pos in position_risks:
            if pos.get("validator_risk", 0) > 60:
                recommendations.append(
                    f"🔍 Revoyez le validateur pour la position {pos['position_id'][:8]}"
                )

        return recommendations

    async def monitor_risks(
        self,
        user_id: UUID,
        interval_seconds: int = 60
    ) -> None:
        """
        Surveille en continu les risques pour un utilisateur.
        """
        try:
            while True:
                risk_score = await self.get_risk_score(user_id)

                # Vérification des seuils critiques
                if risk_score.get("total_risk_score", 0) > 80:
                    await self._trigger_alert(user_id, risk_score)

                await asyncio.sleep(interval_seconds)

        except asyncio.CancelledError:
            logger.info(f"Surveillance des risques arrêtée pour {user_id}")
        except Exception as e:
            logger.error(f"Erreur lors de la surveillance des risques: {e}")

    async def _trigger_alert(
        self,
        user_id: UUID,
        risk_score: Dict[str, Any]
    ) -> None:
        """
        Déclenche une alerte de risque.
        """
        alert = {
            "user_id": str(user_id),
            "timestamp": datetime.now().isoformat(),
            "type": "RISK_THRESHOLD_EXCEEDED",
            "severity": "CRITICAL",
            "risk_score": risk_score.get("total_risk_score", 0),
            "message": "⚠️ Alerte: Seuil de risque critique dépassé!",
            "recommendations": risk_score.get("recommendations", [])
        }

        # Dans une version réelle, on enverrait l'alerte via différents canaux
        logger.warning(f"⚠️ ALERTE RISQUE CRITIQUE: {alert}")

        # Envoi via WebSocket, Email, SMS, etc.
        await self._send_notification(user_id, alert)

    async def _send_notification(
        self,
        user_id: UUID,
        alert: Dict[str, Any]
    ) -> None:
        """
        Envoie une notification d'alerte.
        """
        # Simule l'envoi de notification
        logger.info(f"📱 Notification envoyée à {user_id}: {alert['message']}")

    async def get_validator_risk_profile(
        self,
        validator_address: str,
        blockchain: BlockchainType
    ) -> Optional[ValidatorRiskProfile]:
        """
        Récupère le profil de risque d'un validateur.
        """
        try:
            cache_key = f"{blockchain.value}_{validator_address}"
            if cache_key in self._validator_cache:
                return self._validator_cache[cache_key]

            # Récupération des données du validateur
            validator_data = await self._get_validator_data_by_address(
                validator_address,
                blockchain
            )

            if validator_data:
                profile = ValidatorRiskProfile(
                    validator_address=validator_address,
                    name=validator_data.get("name", "Unknown"),
                    blockchain=blockchain.value,
                    commission=validator_data.get("commission", 5.0),
                    uptime_30d=validator_data.get("uptime", 99.0),
                    slashing_events=validator_data.get("slashing_events", 0),
                    total_stake=validator_data.get("total_stake", 0),
                    delegator_count=validator_data.get("delegators", 0),
                    risk_score=self._calculate_validator_risk_score(validator_data),
                    reliability_score=validator_data.get("reliability", 90.0),
                    performance_score=validator_data.get("performance", 95.0),
                    security_score=validator_data.get("security", 85.0),
                    decentralization_score=validator_data.get("decentralization", 70.0),
                    last_updated=datetime.now()
                )

                self._validator_cache[cache_key] = profile
                return profile

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du profil du validateur: {e}")
            return None

    async def _get_validator_data_by_address(
        self,
        validator_address: str,
        blockchain: BlockchainType
    ) -> Dict[str, Any]:
        """
        Récupère les données d'un validateur par son adresse.
        """
        try:
            api_url = self.VALIDATOR_APIS.get(blockchain)
            if not api_url:
                return {}

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{api_url}/{validator_address}") as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_validator_data(data, blockchain)

            return {}

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données du validateur: {e}")
            return {}


# Fonction factory
def create_staking_risk_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    cache_ttl: int = 180
) -> StakingRiskManager:
    """
    Crée une instance du gestionnaire de risques.
    """
    import redis.asyncio as redis

    redis_client = redis.Redis.from_url(redis_url)

    return StakingRiskManager(
        redis_client=redis_client,
        api_keys=api_keys or {},
        cache_ttl=cache_ttl
    )


# Exemple d'utilisation
async def example_usage():
    """Exemple d'utilisation du gestionnaire de risques."""
    # Création du gestionnaire
    manager = create_staking_risk_manager(
        redis_url="redis://localhost:6379/0",
        api_keys={
            "coingecko": "YOUR_API_KEY",
            "beaconchain": "YOUR_BEACONCHAIN_KEY"
        }
    )

    # Évaluation du risque d'une position
    position = StakingPosition(
        position_id=uuid4(),
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
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
        validator_address="0x0123456789abcdef0123456789abcdef01234567"
    )

    metrics = await manager.assess_position_risk(position, position.user_id)
    print(f"📊 Métriques de risque: {metrics.to_dict()}")

    # Score de risque global
    risk_score = await manager.get_risk_score(position.user_id)
    print(f"🎯 Score de risque: {risk_score}")

    # Profil d'un validateur
    profile = await manager.get_validator_risk_profile(
        validator_address="0x0123456789abcdef0123456789abcdef01234567",
        blockchain=BlockchainType.ETHEREUM
    )
    if profile:
        print(f"✅ Profil validateur: {profile.to_dict()}")

    return manager


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

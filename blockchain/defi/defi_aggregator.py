# blockchain/defi/defi_aggregator.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module DeFi Aggregator - Agrégateur DeFi Avancé

Ce module implémente un agrégateur DeFi complet qui permet d'interagir avec
multiples protocoles DeFi (Aave, Compound, Curve, etc.) via une interface unifiée,
avec optimisation des rendements et gestion des risques.

Fonctionnalités principales:
- Interface unifiée pour tous les protocoles DeFi
- Optimisation automatique des rendements
- Répartition intelligente des fonds
- Gestion des risques multi-protocoles
- Rebalancing automatique
- Monitoring en temps réel
- Alertes de performance
- Statistiques et rapports
- Support multi-chain
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

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel, YieldData
    from .aave import AaveIntegration
    from .compound import CompoundIntegration
    from .curve import CurveIntegration
    from .borrowing import BorrowingManager
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
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel, YieldData
    from .aave import AaveIntegration
    from .compound import CompoundIntegration
    from .curve import CurveIntegration
    from .borrowing import BorrowingManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class DeFiStrategy(Enum):
    """Stratégies DeFi"""
    YIELD_FARMING = "yield_farming"
    LENDING = "lending"
    STAKING = "staking"
    LIQUIDITY_PROVISION = "liquidity_provision"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class AllocationStrategy(Enum):
    """Stratégies d'allocation"""
    EQUAL = "equal"  # Répartition égale
    WEIGHTED = "weighted"  # Pondérée par rendement
    RISK_ADJUSTED = "risk_adjusted"  # Ajustée au risque
    MAX_APY = "max_apy"  # Maximiser l'APY
    MIN_RISK = "min_risk"  # Minimiser le risque
    CUSTOM = "custom"


class DeFiStatus(Enum):
    """Statuts DeFi"""
    ACTIVE = "active"
    PAUSED = "paused"
    REBALANCING = "rebalancing"
    EMERGENCY = "emergency"
    INACTIVE = "inactive"


@dataclass
class DeFiStrategyConfig:
    """Configuration d'une stratégie DeFi"""
    strategy_id: str
    name: str
    strategy_type: DeFiStrategy
    allocation_strategy: AllocationStrategy
    protocols: List[str]
    tokens: List[str]
    chains: List[str]
    risk_level: RiskLevel
    min_amount: Decimal
    max_amount: Decimal
    target_allocation: Dict[str, Decimal]  # Protocol -> target %
    rebalance_threshold: Decimal  # % de deviation pour rebalancer
    max_slippage: Decimal
    gas_optimization: bool = True
    auto_compound: bool = True
    emergency_withdrawal: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "strategy_type": self.strategy_type.value,
            "allocation_strategy": self.allocation_strategy.value,
            "protocols": self.protocols,
            "tokens": self.tokens,
            "chains": self.chains,
            "risk_level": self.risk_level.value,
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount),
            "target_allocation": {k: str(v) for k, v in self.target_allocation.items()},
            "rebalance_threshold": str(self.rebalance_threshold),
            "max_slippage": str(self.max_slippage),
            "gas_optimization": self.gas_optimization,
            "auto_compound": self.auto_compound,
            "emergency_withdrawal": self.emergency_withdrawal,
        }


@dataclass
class DeFiPosition:
    """Position DeFi agrégée"""
    position_id: str
    strategy_id: str
    protocol: str
    chain: str
    token: str
    amount: Decimal
    value_usd: Decimal
    apy: Decimal
    risk_level: RiskLevel
    status: DeFiStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "strategy_id": self.strategy_id,
            "protocol": self.protocol,
            "chain": self.chain,
            "token": self.token,
            "amount": str(self.amount),
            "value_usd": str(self.value_usd),
            "apy": str(self.apy),
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class DeFiPortfolio:
    """Portefeuille DeFi"""
    portfolio_id: str
    strategy_id: str
    total_value_usd: Decimal
    total_apy: Decimal
    positions: List[DeFiPosition]
    risk_score: float
    status: DeFiStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "portfolio_id": self.portfolio_id,
            "strategy_id": self.strategy_id,
            "total_value_usd": str(self.total_value_usd),
            "total_apy": str(self.total_apy),
            "positions": [p.to_dict() for p in self.positions],
            "risk_score": self.risk_score,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class DeFiAggregator:
    """
    Agrégateur DeFi avancé
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        aave: Optional[AaveIntegration] = None,
        compound: Optional[CompoundIntegration] = None,
        curve: Optional[CurveIntegration] = None,
        borrowing_manager: Optional[BorrowingManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise l'agrégateur DeFi

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            aave: Intégration Aave
            compound: Intégration Compound
            curve: Intégration Curve
            borrowing_manager: Gestionnaire d'emprunts
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.aave = aave
        self.compound = compound
        self.curve = curve
        self.borrowing_manager = borrowing_manager
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._strategies: Dict[str, DeFiStrategyConfig] = {}
        self._portfolios: Dict[str, DeFiPortfolio] = {}
        self._positions: Dict[str, DeFiPosition] = {}
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
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
        self._yield_cache: Dict[str, Tuple[float, Dict[str, Decimal]]] = {}
        self._price_cache: Dict[str, Tuple[float, Decimal]] = {}

        # Alertes
        self._alert_callbacks: List[Callable] = []

        # Statistiques
        self._stats: Dict[str, Any] = defaultdict(dict)

        # Chargement des stratégies
        self._load_strategies()

        logger.info("DeFiAggregator initialisé avec succès")

    def _load_strategies(self) -> None:
        """Charge les stratégies DeFi"""
        default_strategies = {
            "conservative_lending": DeFiStrategyConfig(
                strategy_id="conservative_lending",
                name="Conservative Lending",
                strategy_type=DeFiStrategy.LENDING,
                allocation_strategy=AllocationStrategy.RISK_ADJUSTED,
                protocols=["aave_v3", "compound_v3"],
                tokens=["USDC", "USDT", "DAI"],
                chains=["ethereum", "polygon"],
                risk_level=RiskLevel.LOW,
                min_amount=Decimal("100"),
                max_amount=Decimal("1000000"),
                target_allocation={
                    "aave_v3": Decimal("0.6"),
                    "compound_v3": Decimal("0.4"),
                },
                rebalance_threshold=Decimal("0.1"),
                max_slippage=Decimal("0.005"),
                auto_compound=True,
            ),
            "yield_farming": DeFiStrategyConfig(
                strategy_id="yield_farming",
                name="Yield Farming",
                strategy_type=DeFiStrategy.YIELD_FARMING,
                allocation_strategy=AllocationStrategy.MAX_APY,
                protocols=["curve", "aave_v3"],
                tokens=["USDC", "DAI", "ETH"],
                chains=["ethereum", "polygon"],
                risk_level=RiskLevel.MEDIUM,
                min_amount=Decimal("500"),
                max_amount=Decimal("500000"),
                target_allocation={
                    "curve": Decimal("0.5"),
                    "aave_v3": Decimal("0.5"),
                },
                rebalance_threshold=Decimal("0.15"),
                max_slippage=Decimal("0.01"),
                auto_compound=True,
            ),
            "balanced_portfolio": DeFiStrategyConfig(
                strategy_id="balanced_portfolio",
                name="Balanced Portfolio",
                strategy_type=DeFiStrategy.BALANCED,
                allocation_strategy=AllocationStrategy.WEIGHTED,
                protocols=["aave_v3", "compound_v3", "curve"],
                tokens=["USDC", "USDT", "DAI", "ETH"],
                chains=["ethereum", "polygon", "arbitrum"],
                risk_level=RiskLevel.MEDIUM,
                min_amount=Decimal("1000"),
                max_amount=Decimal("2000000"),
                target_allocation={
                    "aave_v3": Decimal("0.4"),
                    "compound_v3": Decimal("0.3"),
                    "curve": Decimal("0.3"),
                },
                rebalance_threshold=Decimal("0.12"),
                max_slippage=Decimal("0.0075"),
                auto_compound=True,
            ),
        }

        # Fusion avec la configuration utilisateur
        user_strategies = self.config.get("strategies", {})
        for strategy_id, strategy in default_strategies.items():
            if strategy_id in user_strategies:
                # Mise à jour avec les valeurs utilisateur
                for key, value in user_strategies[strategy_id].items():
                    if hasattr(strategy, key):
                        setattr(strategy, key, value)

            self._strategies[strategy_id] = strategy

        logger.info(f"Stratégies chargées: {list(self._strategies.keys())}")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_portfolio(
        self,
        strategy_id: str,
        user: str,
        force_refresh: bool = False,
    ) -> Optional[DeFiPortfolio]:
        """
        Obtient le portefeuille DeFi d'un utilisateur

        Args:
            strategy_id: ID de la stratégie
            user: Adresse de l'utilisateur
            force_refresh: Forcer le rafraîchissement

        Returns:
            Portefeuille DeFi
        """
        portfolio_key = f"{strategy_id}:{user}"

        if not force_refresh and portfolio_key in self._portfolios:
            return self._portfolios[portfolio_key]

        try:
            strategy = self._strategies.get(strategy_id)
            if not strategy:
                raise DeFiError(f"Stratégie {strategy_id} non trouvée")

            positions = []
            total_value = Decimal("0")
            total_apy = Decimal("0")

            # Récupération des positions via les protocoles
            for protocol_name in strategy.protocols:
                protocol_positions = await self._get_protocol_positions(
                    protocol_name, user, strategy
                )

                for pos in protocol_positions:
                    positions.append(pos)
                    total_value += pos.value_usd
                    total_apy += pos.apy * (pos.value_usd / max(total_value, Decimal("1")))

            # Calcul du score de risque
            risk_score = self._calculate_risk_score(positions)

            portfolio = DeFiPortfolio(
                portfolio_id=f"dp_{uuid.uuid4().hex[:8]}",
                strategy_id=strategy_id,
                total_value_usd=total_value,
                total_apy=total_apy,
                positions=positions,
                risk_score=risk_score,
                status=DeFiStatus.ACTIVE,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self._portfolios[portfolio_key] = portfolio

            # Métriques
            self.metrics.record_gauge(
                "defi_portfolio_value",
                float(total_value),
                {"strategy": strategy_id, "user": user[:10]},
            )
            self.metrics.record_gauge(
                "defi_portfolio_apy",
                float(total_apy),
                {"strategy": strategy_id},
            )

            return portfolio

        except Exception as e:
            logger.error(f"Erreur de récupération du portefeuille: {e}")
            raise DeFiError(f"Erreur de récupération du portefeuille: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_strategy(
        self,
        strategy_id: str,
        user: str,
        amount: Decimal,
        token: str,
        chain: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Exécute une stratégie DeFi

        Args:
            strategy_id: ID de la stratégie
            user: Adresse de l'utilisateur
            amount: Montant à investir
            token: Token à investir
            chain: Chaîne
            dry_run: Simuler sans exécuter

        Returns:
            Résultat de l'exécution
        """
        operation_id = f"op_{uuid.uuid4().hex[:12]}"
        logger.info(f"Exécution de la stratégie {strategy_id} pour {user}")

        try:
            strategy = self._strategies.get(strategy_id)
            if not strategy:
                raise DeFiError(f"Stratégie {strategy_id} non trouvée")

            # Validation
            await self._validate_execution(strategy, amount, token, chain, user)

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(user)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {user}")

            # Calcul de l'allocation
            allocation = await self._calculate_allocation(
                strategy, amount, token, chain
            )

            if dry_run:
                return {
                    "operation_id": operation_id,
                    "status": "dry_run",
                    "allocation": {k: str(v) for k, v in allocation.items()},
                    "strategy": strategy.to_dict(),
                }

            # Exécution des allocations
            results = await self._execute_allocation(
                strategy, allocation, user, wallet
            )

            # Mise à jour du portefeuille
            await self.get_portfolio(strategy_id, user, force_refresh=True)

            # Métriques
            self.metrics.record_increment(
                "defi_strategy_executed",
                1,
                {"strategy": strategy_id, "chain": chain, "token": token},
            )

            return {
                "operation_id": operation_id,
                "status": "completed",
                "allocation": {k: str(v) for k, v in allocation.items()},
                "results": results,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Erreur d'exécution de la stratégie: {e}")
            raise DeFiError(f"Erreur d'exécution de la stratégie: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def rebalance(
        self,
        strategy_id: str,
        user: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Rebalance un portefeuille DeFi

        Args:
            strategy_id: ID de la stratégie
            user: Adresse de l'utilisateur
            force: Forcer le rebalancing

        Returns:
            Résultat du rebalancing
        """
        logger.info(f"Rebalancing de la stratégie {strategy_id} pour {user}")

        try:
            strategy = self._strategies.get(strategy_id)
            if not strategy:
                raise DeFiError(f"Stratégie {strategy_id} non trouvée")

            # Récupération du portefeuille actuel
            portfolio = await self.get_portfolio(strategy_id, user, force_refresh=True)

            if not portfolio:
                raise DeFiError(f"Portefeuille non trouvé pour {strategy_id}")

            # Vérification du besoin de rebalancing
            if not force and not await self._needs_rebalancing(strategy, portfolio):
                return {
                    "status": "no_rebalance_needed",
                    "portfolio": portfolio.to_dict(),
                }

            # Calcul des ajustements
            adjustments = await self._calculate_rebalance_adjustments(
                strategy, portfolio
            )

            if not adjustments:
                return {
                    "status": "no_adjustments_needed",
                    "portfolio": portfolio.to_dict(),
                }

            # Exécution des ajustements
            wallet = await self.wallet_manager.get_wallet(user)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {user}")

            results = await self._execute_rebalance(
                strategy, adjustments, user, wallet
            )

            # Mise à jour du portefeuille
            await self.get_portfolio(strategy_id, user, force_refresh=True)

            # Métriques
            self.metrics.record_increment(
                "defi_rebalance",
                1,
                {"strategy": strategy_id},
            )

            return {
                "status": "completed",
                "adjustments": adjustments,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Erreur de rebalancing: {e}")
            raise DeFiError(f"Erreur de rebalancing: {e}")

    async def get_best_yield(
        self,
        token: str,
        chain: str,
        amount: Decimal,
        risk_tolerance: RiskLevel = RiskLevel.MEDIUM,
    ) -> List[Dict[str, Any]]:
        """
        Obtient les meilleurs rendements pour un token

        Args:
            token: Token
            chain: Chaîne
            amount: Montant
            risk_tolerance: Tolérance au risque

        Returns:
            Liste des meilleurs rendements
        """
        logger.info(f"Recherche des meilleurs rendements pour {token} sur {chain}")

        try:
            yields = []

            # Récupération des rendements de tous les protocoles
            protocols = ["aave_v3", "compound_v3", "curve"]

            for protocol_name in protocols:
                try:
                    protocol_yield = await self._get_protocol_yield(
                        protocol_name, token, chain, amount
                    )

                    if protocol_yield and protocol_yield.apy > 0:
                        yields.append({
                            "protocol": protocol_name,
                            "apy": str(protocol_yield.apy),
                            "apr": str(protocol_yield.apr),
                            "risk_level": protocol_yield.risk_level.value,
                            "rewards": protocol_yield.rewards,
                        })

                except Exception as e:
                    logger.warning(f"Erreur pour {protocol_name}: {e}")

            # Tri par APY
            yields.sort(key=lambda x: Decimal(x["apy"]), reverse=True)

            # Filtrage par tolérance au risque
            if risk_tolerance != RiskLevel.VERY_HIGH:
                risk_order = [r.value for r in RiskLevel]
                max_risk_index = risk_order.index(risk_tolerance.value)
                yields = [
                    y for y in yields
                    if risk_order.index(y["risk_level"]) <= max_risk_index
                ]

            return yields

        except Exception as e:
            logger.error(f"Erreur de recherche de rendement: {e}")
            raise DeFiError(f"Erreur de recherche de rendement: {e}")

    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================

    async def _get_protocol_positions(
        self,
        protocol_name: str,
        user: str,
        strategy: DeFiStrategyConfig,
    ) -> List[DeFiPosition]:
        """Obtient les positions d'un protocole"""
        positions = []

        try:
            if protocol_name.startswith("aave"):
                if not self.aave:
                    return []

                # Récupération des positions Aave
                for token in strategy.tokens:
                    try:
                        position = await self.aave.get_user_position(
                            user, token, strategy.chains[0]
                        )
                        if position:
                            positions.append(DeFiPosition(
                                position_id=f"pos_{uuid.uuid4().hex[:8]}",
                                strategy_id=strategy.strategy_id,
                                protocol=protocol_name,
                                chain=strategy.chains[0],
                                token=token,
                                amount=position.total_collateral,
                                value_usd=position.total_collateral_usd,
                                apy=Decimal("0.03"),  # Simulé
                                risk_level=RiskLevel.LOW,
                                status=DeFiStatus.ACTIVE,
                                created_at=datetime.now(),
                                updated_at=datetime.now(),
                            ))
                    except Exception as e:
                        logger.debug(f"Erreur pour {token} sur Aave: {e}")

            elif protocol_name.startswith("compound"):
                if not self.compound:
                    return []

                # Récupération des positions Compound
                for token in strategy.tokens:
                    try:
                        position = await self.compound.get_user_position(
                            user, strategy.chains[0]
                        )
                        if position:
                            positions.append(DeFiPosition(
                                position_id=f"pos_{uuid.uuid4().hex[:8]}",
                                strategy_id=strategy.strategy_id,
                                protocol=protocol_name,
                                chain=strategy.chains[0],
                                token=token,
                                amount=position.supply_amount,
                                value_usd=position.supply_amount * Decimal("1"),
                                apy=Decimal("0.025"),
                                risk_level=RiskLevel.LOW,
                                status=DeFiStatus.ACTIVE,
                                created_at=datetime.now(),
                                updated_at=datetime.now(),
                            ))
                    except Exception as e:
                        logger.debug(f"Erreur pour {token} sur Compound: {e}")

            elif protocol_name == "curve":
                if not self.curve:
                    return []

                # Récupération des positions Curve
                for token in strategy.tokens:
                    try:
                        position = await self.curve.get_position(
                            "3pool", user, strategy.chains[0]
                        )
                        if position:
                            positions.append(DeFiPosition(
                                position_id=f"pos_{uuid.uuid4().hex[:8]}",
                                strategy_id=strategy.strategy_id,
                                protocol=protocol_name,
                                chain=strategy.chains[0],
                                token=token,
                                amount=position.lp_amount,
                                value_usd=position.lp_value_usd,
                                apy=position.apy,
                                risk_level=RiskLevel.MEDIUM,
                                status=DeFiStatus.ACTIVE,
                                created_at=datetime.now(),
                                updated_at=datetime.now(),
                            ))
                    except Exception as e:
                        logger.debug(f"Erreur pour {token} sur Curve: {e}")

            return positions

        except Exception as e:
            logger.warning(f"Erreur de récupération des positions {protocol_name}: {e}")
            return []

    async def _get_protocol_yield(
        self,
        protocol_name: str,
        token: str,
        chain: str,
        amount: Decimal,
    ) -> Optional[YieldData]:
        """Obtient les données de rendement d'un protocole"""
        try:
            if protocol_name.startswith("aave"):
                if not self.aave:
                    return None

                reserve = await self.aave.get_reserve_data(token, chain)
                return YieldData(
                    protocol=protocol_name,
                    chain=chain,
                    token=token,
                    apy=reserve.supply_rate,
                    apr=reserve.supply_rate,
                    rewards=[],
                    risk_level=RiskLevel.LOW,
                    timestamp=datetime.now(),
                )

            elif protocol_name.startswith("compound"):
                if not self.compound:
                    return None

                reserve = await self.compound.get_reserve_data(token, chain)
                return YieldData(
                    protocol=protocol_name,
                    chain=chain,
                    token=token,
                    apy=reserve.supply_rate,
                    apr=reserve.supply_rate,
                    rewards=[],
                    risk_level=RiskLevel.LOW,
                    timestamp=datetime.now(),
                )

            elif protocol_name == "curve":
                if not self.curve:
                    return None

                pool = await self.curve.get_pool_data("3pool", chain)
                return YieldData(
                    protocol=protocol_name,
                    chain=chain,
                    token=token,
                    apy=pool.apy,
                    apr=pool.apy * Decimal("0.95"),
                    rewards=[{"token": "CRV", "apy": Decimal("0.02")}],
                    risk_level=RiskLevel.MEDIUM,
                    timestamp=datetime.now(),
                )

            return None

        except Exception as e:
            logger.warning(f"Erreur de récupération du rendement {protocol_name}: {e}")
            return None

    async def _validate_execution(
        self,
        strategy: DeFiStrategyConfig,
        amount: Decimal,
        token: str,
        chain: str,
        user: str,
    ) -> None:
        """Valide l'exécution d'une stratégie"""
        if amount < strategy.min_amount:
            raise ValidationError(
                f"Montant inférieur au minimum: {strategy.min_amount}"
            )

        if amount > strategy.max_amount:
            raise ValidationError(
                f"Montant supérieur au maximum: {strategy.max_amount}"
            )

        if token not in strategy.tokens:
            raise ValidationError(f"Token {token} non supporté par la stratégie")

        if chain not in strategy.chains:
            raise ValidationError(f"Chaîne {chain} non supportée par la stratégie")

        if not user or len(user) != 42:
            raise ValidationError("Adresse utilisateur invalide")

    async def _calculate_allocation(
        self,
        strategy: DeFiStrategyConfig,
        amount: Decimal,
        token: str,
        chain: str,
    ) -> Dict[str, Decimal]:
        """Calcule l'allocation des fonds"""
        allocation = {}

        if strategy.allocation_strategy == AllocationStrategy.EQUAL:
            # Répartition égale
            per_protocol = amount / len(strategy.protocols)
            for protocol in strategy.protocols:
                allocation[protocol] = per_protocol

        elif strategy.allocation_strategy == AllocationStrategy.WEIGHTED:
            # Répartition pondérée
            total_weight = sum(strategy.target_allocation.values())
            for protocol in strategy.protocols:
                weight = strategy.target_allocation.get(protocol, Decimal("0"))
                allocation[protocol] = amount * (weight / total_weight)

        elif strategy.allocation_strategy == AllocationStrategy.MAX_APY:
            # Maximisation de l'APY
            yields = {}
            for protocol in strategy.protocols:
                yield_data = await self._get_protocol_yield(protocol, token, chain, amount)
                if yield_data:
                    yields[protocol] = yield_data.apy

            if yields:
                total_apy = sum(yields.values())
                for protocol, apy in yields.items():
                    allocation[protocol] = amount * (apy / total_apy)
            else:
                # Fallback sur égal
                per_protocol = amount / len(strategy.protocols)
                for protocol in strategy.protocols:
                    allocation[protocol] = per_protocol

        elif strategy.allocation_strategy == AllocationStrategy.RISK_ADJUSTED:
            # Ajustée au risque
            risk_scores = {}
            for protocol in strategy.protocols:
                yield_data = await self._get_protocol_yield(protocol, token, chain, amount)
                if yield_data:
                    risk_score = self._calculate_protocol_risk_score(yield_data)
                    risk_scores[protocol] = risk_score

            if risk_scores:
                total_score = sum(risk_scores.values())
                for protocol, score in risk_scores.items():
                    allocation[protocol] = amount * (score / total_score)
            else:
                per_protocol = amount / len(strategy.protocols)
                for protocol in strategy.protocols:
                    allocation[protocol] = per_protocol

        else:
            # Custom ou fallback
            per_protocol = amount / len(strategy.protocols)
            for protocol in strategy.protocols:
                allocation[protocol] = per_protocol

        return allocation

    async def _execute_allocation(
        self,
        strategy: DeFiStrategyConfig,
        allocation: Dict[str, Decimal],
        user: str,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute l'allocation des fonds"""
        results = {}

        for protocol_name, amount in allocation.items():
            if amount <= 0:
                continue

            try:
                if protocol_name.startswith("aave") and self.aave:
                    # Exécution sur Aave
                    tx_hash = await self.aave.supply(
                        asset=strategy.tokens[0],
                        amount=amount,
                        chain=strategy.chains[0],
                        wallet_address=user,
                    )
                    results[protocol_name] = {
                        "status": "completed",
                        "tx_hash": tx_hash,
                        "amount": str(amount),
                    }

                elif protocol_name.startswith("compound") and self.compound:
                    # Exécution sur Compound
                    tx_hash = await self.compound.supply(
                        asset=strategy.tokens[0],
                        amount=amount,
                        chain=strategy.chains[0],
                        wallet_address=user,
                    )
                    results[protocol_name] = {
                        "status": "completed",
                        "tx_hash": tx_hash,
                        "amount": str(amount),
                    }

                elif protocol_name == "curve" and self.curve:
                    # Exécution sur Curve
                    tx_hash = await self.curve.add_liquidity(
                        pool_id="3pool",
                        amounts={strategy.tokens[0]: amount},
                        chain=strategy.chains[0],
                        wallet_address=user,
                    )
                    results[protocol_name] = {
                        "status": "completed",
                        "tx_hash": tx_hash,
                        "amount": str(amount),
                    }

                else:
                    results[protocol_name] = {
                        "status": "skipped",
                        "reason": "Protocole non disponible",
                    }

            except Exception as e:
                logger.error(f"Erreur d'exécution sur {protocol_name}: {e}")
                results[protocol_name] = {
                    "status": "failed",
                    "error": str(e),
                }

        return results

    async def _needs_rebalancing(
        self,
        strategy: DeFiStrategyConfig,
        portfolio: DeFiPortfolio,
    ) -> bool:
        """Vérifie si un rebalancing est nécessaire"""
        if not portfolio.positions:
            return False

        # Calcul des allocations actuelles
        total_value = portfolio.total_value_usd
        if total_value == 0:
            return False

        current_allocation = {}
        for position in portfolio.positions:
            current_allocation[position.protocol] = position.value_usd / total_value

        # Vérification des écarts
        for protocol, target in strategy.target_allocation.items():
            current = current_allocation.get(protocol, Decimal("0"))
            deviation = abs(current - target)

            if deviation > strategy.rebalance_threshold:
                logger.info(
                    f"Rebalancing nécessaire pour {protocol}: "
                    f"current={current:.2%}, target={target:.2%}, deviation={deviation:.2%}"
                )
                return True

        return False

    async def _calculate_rebalance_adjustments(
        self,
        strategy: DeFiStrategyConfig,
        portfolio: DeFiPortfolio,
    ) -> Dict[str, Dict[str, Decimal]]:
        """Calcule les ajustements de rebalancing"""
        if not portfolio.positions:
            return {}

        total_value = portfolio.total_value_usd
        if total_value == 0:
            return {}

        # Calcul des allocations actuelles
        current_allocation = {}
        protocol_values = {}

        for position in portfolio.positions:
            current_allocation[position.protocol] = position.value_usd / total_value
            protocol_values[position.protocol] = position.value_usd

        adjustments = {}

        for protocol, target in strategy.target_allocation.items():
            current = current_allocation.get(protocol, Decimal("0"))
            target_value = total_value * target
            current_value = protocol_values.get(protocol, Decimal("0"))

            if current_value < target_value:
                # Ajouter
                amount = target_value - current_value
                adjustments[protocol] = {
                    "action": "add",
                    "amount": amount,
                }
            elif current_value > target_value:
                # Retirer
                amount = current_value - target_value
                adjustments[protocol] = {
                    "action": "remove",
                    "amount": amount,
                }
            else:
                adjustments[protocol] = {
                    "action": "none",
                    "amount": Decimal("0"),
                }

        return adjustments

    async def _execute_rebalance(
        self,
        strategy: DeFiStrategyConfig,
        adjustments: Dict[str, Dict[str, Decimal]],
        user: str,
        wallet: BaseWallet,
    ) -> Dict[str, Any]:
        """Exécute les ajustements de rebalancing"""
        results = {}

        for protocol_name, adjustment in adjustments.items():
            if adjustment["action"] == "none" or adjustment["amount"] <= 0:
                continue

            try:
                if adjustment["action"] == "remove":
                    # Retrait
                    if protocol_name.startswith("aave") and self.aave:
                        tx_hash = await self.aave.withdraw(
                            asset=strategy.tokens[0],
                            amount=adjustment["amount"],
                            chain=strategy.chains[0],
                            wallet_address=user,
                        )
                    elif protocol_name.startswith("compound") and self.compound:
                        tx_hash = await self.compound.withdraw(
                            asset=strategy.tokens[0],
                            amount=adjustment["amount"],
                            chain=strategy.chains[0],
                            wallet_address=user,
                        )
                    elif protocol_name == "curve" and self.curve:
                        tx_hash = await self.curve.remove_liquidity(
                            pool_id="3pool",
                            lp_amount=adjustment["amount"],
                            chain=strategy.chains[0],
                            wallet_address=user,
                        )
                    else:
                        results[protocol_name] = {
                            "status": "skipped",
                            "reason": "Protocole non disponible",
                        }
                        continue

                    results[protocol_name] = {
                        "status": "completed",
                        "action": "remove",
                        "tx_hash": tx_hash,
                        "amount": str(adjustment["amount"]),
                    }

                elif adjustment["action"] == "add":
                    # Ajout
                    if protocol_name.startswith("aave") and self.aave:
                        tx_hash = await self.aave.supply(
                            asset=strategy.tokens[0],
                            amount=adjustment["amount"],
                            chain=strategy.chains[0],
                            wallet_address=user,
                        )
                    elif protocol_name.startswith("compound") and self.compound:
                        tx_hash = await self.compound.supply(
                            asset=strategy.tokens[0],
                            amount=adjustment["amount"],
                            chain=strategy.chains[0],
                            wallet_address=user,
                        )
                    elif protocol_name == "curve" and self.curve:
                        tx_hash = await self.curve.add_liquidity(
                            pool_id="3pool",
                            amounts={strategy.tokens[0]: adjustment["amount"]},
                            chain=strategy.chains[0],
                            wallet_address=user,
                        )
                    else:
                        results[protocol_name] = {
                            "status": "skipped",
                            "reason": "Protocole non disponible",
                        }
                        continue

                    results[protocol_name] = {
                        "status": "completed",
                        "action": "add",
                        "tx_hash": tx_hash,
                        "amount": str(adjustment["amount"]),
                    }

            except Exception as e:
                logger.error(f"Erreur de rebalancing sur {protocol_name}: {e}")
                results[protocol_name] = {
                    "status": "failed",
                    "error": str(e),
                }

        return results

    def _calculate_risk_score(self, positions: List[DeFiPosition]) -> float:
        """Calcule le score de risque d'un portefeuille"""
        if not positions:
            return 0.0

        # Pondération par valeur
        total_value = sum(p.value_usd for p in positions)
        if total_value == 0:
            return 0.0

        risk_scores = {
            RiskLevel.VERY_LOW: 0.1,
            RiskLevel.LOW: 0.3,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.HIGH: 0.7,
            RiskLevel.VERY_HIGH: 0.9,
        }

        weighted_risk = 0.0
        for position in positions:
            weight = position.value_usd / total_value
            weighted_risk += risk_scores[position.risk_level] * float(weight)

        return weighted_risk

    def _calculate_protocol_risk_score(self, yield_data: YieldData) -> float:
        """Calcule le score de risque d'un protocole"""
        risk_scores = {
            RiskLevel.VERY_LOW: 0.9,
            RiskLevel.LOW: 0.7,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.HIGH: 0.3,
            RiskLevel.VERY_HIGH: 0.1,
        }
        return risk_scores.get(yield_data.risk_level, 0.5)

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    def add_alert_callback(self, callback: Callable) -> None:
        """Ajoute un callback pour les alertes"""
        self._alert_callbacks.append(callback)

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques de l'agrégateur"""
        return {
            "strategies": len(self._strategies),
            "portfolios": len(self._portfolios),
            "positions": len(self._positions),
            "active_operations": len(self._active_operations),
            "cache_size": len(self._yield_cache),
            "total_value_locked": self._calculate_total_value_locked(),
            "average_apy": self._calculate_average_apy(),
        }

    def _calculate_total_value_locked(self) -> Decimal:
        """Calcule la valeur totale verrouillée"""
        total = Decimal("0")
        for portfolio in self._portfolios.values():
            total += portfolio.total_value_usd
        return total

    def _calculate_average_apy(self) -> Decimal:
        """Calcule l'APY moyen"""
        if not self._portfolios:
            return Decimal("0")

        total_apy = Decimal("0")
        for portfolio in self._portfolios.values():
            total_apy += portfolio.total_apy

        return total_apy / len(self._portfolios)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources DeFiAggregator...")

        self._strategies.clear()
        self._portfolios.clear()
        self._positions.clear()
        self._active_operations.clear()
        self._yield_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_defi_aggregator(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    **kwargs,
) -> DeFiAggregator:
    """
    Crée une instance de DeFiAggregator

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiAggregator
    """
    return DeFiAggregator(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de DeFiAggregator"""
    # Configuration
    config = {
        "strategies": {
            "conservative_lending": {
                "protocols": ["aave_v3", "compound_v3"],
                "tokens": ["USDC", "USDT"],
                "chains": ["ethereum", "polygon"],
            },
        },
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création de l'agrégateur
    aggregator = create_defi_aggregator(
        config=config,
        wallet_manager=wallet_manager,
    )

    # Obtention des meilleurs rendements
    yields = await aggregator.get_best_yield(
        token="USDC",
        chain="ethereum",
        amount=Decimal("10000"),
        risk_tolerance=RiskLevel.MEDIUM,
    )

    print("Meilleurs rendements:")
    for y in yields[:5]:
        print(f"  {y['protocol']}: {y['apy']} APY (risque: {y['risk_level']})")

    # Exécution d'une stratégie
    result = await aggregator.execute_strategy(
        strategy_id="conservative_lending",
        user="0x1234567890123456789012345678901234567890",
        amount=Decimal("10000"),
        token="USDC",
        chain="ethereum",
        dry_run=True,  # Simuler
    )

    print(f"Résultat de la simulation: {result}")

    # Statistiques
    stats = aggregator.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await aggregator.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

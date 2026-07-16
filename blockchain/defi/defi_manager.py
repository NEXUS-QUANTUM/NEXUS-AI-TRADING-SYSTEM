# blockchain/defi/defi_manager.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module DeFi Manager - Gestionnaire Centralisé DeFi

Ce module implémente un gestionnaire centralisé pour toutes les opérations DeFi,
intégrant tous les protocoles, l'agrégation, l'analytique, et la gestion
des risques dans une interface unifiée.

Fonctionnalités principales:
- Interface unifiée pour tous les protocoles DeFi
- Gestion centralisée des positions
- Optimisation automatique des rendements
- Gestion des risques multi-protocoles
- Monitoring et alertes en temps réel
- Rapports et analytique
- Rebalancing automatique
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
    from ..security.encryption import EncryptionManager
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
    from .defi_config import DeFiConfigManager, DeFiProtocol, DeFiChain, Environment
    from .defi_aggregator import DeFiAggregator
    from .defi_analytics import DeFiAnalytics
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
    from ..security.encryption import EncryptionManager
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
    from .defi_config import DeFiConfigManager, DeFiProtocol, DeFiChain, Environment
    from .defi_aggregator import DeFiAggregator
    from .defi_analytics import DeFiAnalytics
    from .aave import AaveIntegration
    from .compound import CompoundIntegration
    from .curve import CurveIntegration
    from .borrowing import BorrowingManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class DeFiManagerStatus(Enum):
    """Statuts du gestionnaire DeFi"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class DeFiManagerConfig:
    """Configuration du gestionnaire DeFi"""
    auto_rebalance: bool = True
    auto_compound: bool = True
    max_positions: int = 10
    min_health_factor: Decimal = Decimal("1.2")
    max_risk_score: float = 0.7
    rebalance_interval: int = 3600  # 1 heure
    monitoring_interval: int = 60  # 1 minute
    emergency_withdrawal: bool = True
    max_slippage: Decimal = Decimal("0.01")
    gas_multiplier: float = 1.1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeFiManagerState:
    """État du gestionnaire DeFi"""
    status: DeFiManagerStatus
    total_value_usd: Decimal
    total_apy: Decimal
    positions: List[Position]
    risk_score: float
    health_factor: Decimal
    last_rebalance: Optional[datetime]
    last_monitoring: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "status": self.status.value,
            "total_value_usd": str(self.total_value_usd),
            "total_apy": str(self.total_apy),
            "positions": [p.to_dict() for p in self.positions],
            "risk_score": self.risk_score,
            "health_factor": str(self.health_factor),
            "last_rebalance": self.last_rebalance.isoformat() if self.last_rebalance else None,
            "last_monitoring": self.last_monitoring.isoformat() if self.last_monitoring else None,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class DeFiManager:
    """
    Gestionnaire centralisé DeFi
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        web3_providers: Dict[str, Any],
        encryption_manager: Optional[EncryptionManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire DeFi

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            encryption_manager: Gestionnaire de chiffrement
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # Configuration
        self.manager_config = DeFiManagerConfig(**config.get("manager", {}))

        # États internes
        self._status = DeFiManagerStatus.INITIALIZING
        self._state: Optional[DeFiManagerState] = None
        self._positions: Dict[str, Position] = {}
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._is_running = False
        self._monitor_tasks: List[asyncio.Task] = []

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

        # Alertes
        self._alert_callbacks: List[Callable] = []

        # Initialisation des sous-systèmes
        self._initialize_subsystems()

        # Chargement de l'état
        self._load_state()

        self._status = DeFiManagerStatus.ACTIVE

        logger.info("DeFiManager initialisé avec succès")

    # ============================================================
    # INITIALISATION
    # ============================================================

    def _initialize_subsystems(self) -> None:
        """Initialise les sous-systèmes DeFi"""
        try:
            # Configuration
            self.config_manager = DeFiConfigManager(
                config_dir=self.config.get("config_dir"),
                environment=self.config.get("environment", "production"),
                metrics_collector=self.metrics,
            )

            # Intégrations des protocoles
            self.aave = AaveIntegration(
                config=self.config.get("aave", {}),
                wallet_manager=self.wallet_manager,
                web3_providers=self.web3_providers,
                metrics_collector=self.metrics,
                encryption_manager=self.encryption_manager,
            )

            self.compound = CompoundIntegration(
                config=self.config.get("compound", {}),
                wallet_manager=self.wallet_manager,
                web3_providers=self.web3_providers,
                metrics_collector=self.metrics,
                encryption_manager=self.encryption_manager,
            )

            self.curve = CurveIntegration(
                config=self.config.get("curve", {}),
                wallet_manager=self.wallet_manager,
                web3_providers=self.web3_providers,
                metrics_collector=self.metrics,
                encryption_manager=self.encryption_manager,
            )

            # Gestionnaire d'emprunts
            protocol_instances = {
                "aave_v3_ethereum": self.aave,
                "compound_v3_ethereum": self.compound,
            }
            self.borrowing_manager = BorrowingManager(
                config=self.config.get("borrowing", {}),
                wallet_manager=self.wallet_manager,
                protocol_instances=protocol_instances,
                metrics_collector=self.metrics,
            )

            # Agrégateur
            self.aggregator = DeFiAggregator(
                config=self.config.get("aggregator", {}),
                wallet_manager=self.wallet_manager,
                aave=self.aave,
                compound=self.compound,
                curve=self.curve,
                borrowing_manager=self.borrowing_manager,
                metrics_collector=self.metrics,
            )

            # Analytique
            self.analytics = DeFiAnalytics(
                config=self.config.get("analytics", {}),
                defi_aggregator=self.aggregator,
                aave=self.aave,
                compound=self.compound,
                curve=self.curve,
                metrics_collector=self.metrics,
            )

            # Ajout des callbacks d'alerte
            self.aggregator.add_alert_callback(self._handle_alert)
            self.borrowing_manager.add_alert_callback(self._handle_alert)

            logger.info("Sous-systèmes DeFi initialisés")

        except Exception as e:
            logger.error(f"Erreur d'initialisation des sous-systèmes: {e}")
            raise DeFiError(f"Erreur d'initialisation: {e}")

    def _load_state(self) -> None:
        """Charge l'état du gestionnaire"""
        self._state = DeFiManagerState(
            status=DeFiManagerStatus.ACTIVE,
            total_value_usd=Decimal("0"),
            total_apy=Decimal("0"),
            positions=[],
            risk_score=0.0,
            health_factor=Decimal("999"),
            last_rebalance=None,
            last_monitoring=None,
        )

        # Dans la réalité, on chargerait depuis une base de données
        logger.info("État DeFiManager chargé")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

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
            token: Token
            chain: Chaîne
            dry_run: Simuler sans exécuter

        Returns:
            Résultat de l'exécution
        """
        logger.info(f"Exécution de la stratégie {strategy_id} pour {user}")

        try:
            # Vérification du statut
            if self._status != DeFiManagerStatus.ACTIVE:
                raise DeFiError(f"Gestionnaire non actif: {self._status.value}")

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(user)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {user}")

            # Vérification du solde
            balance = await self._get_balance(token, chain, user)
            if balance < amount:
                raise DeFiError(f"Solde insuffisant: {balance} < {amount}")

            # Vérification des limites
            if amount < self.manager_config.min_amount:
                raise DeFiError(f"Montant inférieur au minimum: {self.manager_config.min_amount}")

            max_amount = self.config.get("max_investment", Decimal("1000000"))
            if amount > max_amount:
                raise DeFiError(f"Montant supérieur au maximum: {max_amount}")

            # Exécution via l'agrégateur
            result = await self.aggregator.execute_strategy(
                strategy_id=strategy_id,
                user=user,
                amount=amount,
                token=token,
                chain=chain,
                dry_run=dry_run,
            )

            if not dry_run:
                # Mise à jour de l'état
                await self._update_state()

                # Métriques
                self.metrics.record_increment(
                    "defi_manager_strategy_executed",
                    1,
                    {"strategy": strategy_id, "chain": chain, "token": token},
                )

            return result

        except Exception as e:
            logger.error(f"Erreur d'exécution de la stratégie: {e}")
            raise DeFiError(f"Erreur d'exécution de la stratégie: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_positions(self, user: str) -> List[Position]:
        """
        Obtient les positions d'un utilisateur

        Args:
            user: Adresse de l'utilisateur

        Returns:
            Liste des positions
        """
        try:
            positions = []

            # Positions depuis l'agrégateur
            portfolio = await self.aggregator.get_portfolio("", user)
            if portfolio:
                positions.extend(portfolio.positions)

            # Positions d'emprunt
            borrow_positions = await self.borrowing_manager.get_positions(user)
            for pos in borrow_positions:
                positions.append(Position(
                    position_id=pos.position_id,
                    position_type=PositionType.DEBT,
                    protocol=pos.protocol.value,
                    chain=pos.chain,
                    token=pos.debt_token,
                    amount=pos.debt_amount,
                    value_usd=pos.debt_value_usd,
                    apy=pos.current_interest_rate,
                    timestamp=datetime.now(),
                    metadata={
                        "collateral_token": pos.collateral_token,
                        "collateral_amount": str(pos.collateral_amount),
                        "health_factor": str(pos.health_factor),
                    },
                ))

            return positions

        except Exception as e:
            logger.error(f"Erreur de récupération des positions: {e}")
            raise DeFiError(f"Erreur de récupération des positions: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_state(self) -> DeFiManagerState:
        """
        Obtient l'état du gestionnaire

        Returns:
            État du gestionnaire
        """
        await self._update_state()
        return self._state

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def rebalance(self, user: str, force: bool = False) -> Dict[str, Any]:
        """
        Rebalance les positions d'un utilisateur

        Args:
            user: Adresse de l'utilisateur
            force: Forcer le rebalancing

        Returns:
            Résultat du rebalancing
        """
        logger.info(f"Rebalancing pour {user}")

        try:
            # Vérification du statut
            if self._status != DeFiManagerStatus.ACTIVE:
                raise DeFiError(f"Gestionnaire non actif: {self._status.value}")

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(user)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {user}")

            # Exécution du rebalancing
            result = await self.aggregator.rebalance("", user, force)

            # Mise à jour de l'état
            await self._update_state()

            # Métriques
            self.metrics.record_increment(
                "defi_manager_rebalance",
                1,
                {"user": user[:10]},
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de rebalancing: {e}")
            raise DeFiError(f"Erreur de rebalancing: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_best_yields(
        self,
        token: str,
        chain: str,
        amount: Decimal,
        risk_tolerance: RiskLevel = RiskLevel.MEDIUM,
    ) -> List[Dict[str, Any]]:
        """
        Obtient les meilleurs rendements

        Args:
            token: Token
            chain: Chaîne
            amount: Montant
            risk_tolerance: Tolérance au risque

        Returns:
            Liste des meilleurs rendements
        """
        return await self.aggregator.get_best_yield(
            token=token,
            chain=chain,
            amount=amount,
            risk_tolerance=risk_tolerance,
        )

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def generate_report(
        self,
        title: str,
        timeframe: str = "week",
        protocols: Optional[List[str]] = None,
        tokens: Optional[List[str]] = None,
        chains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Génère un rapport DeFi

        Args:
            title: Titre du rapport
            timeframe: Période (hour, day, week, month, quarter, year)
            protocols: Protocoles à analyser
            tokens: Tokens à analyser
            chains: Chaînes à analyser

        Returns:
            Rapport
        """
        # Conversion du timeframe
        timeframe_map = {
            "hour": AnalyticsTimeframe.HOUR,
            "day": AnalyticsTimeframe.DAY,
            "week": AnalyticsTimeframe.WEEK,
            "month": AnalyticsTimeframe.MONTH,
            "quarter": AnalyticsTimeframe.QUARTER,
            "year": AnalyticsTimeframe.YEAR,
        }
        tf = timeframe_map.get(timeframe, AnalyticsTimeframe.WEEK)

        # Génération du rapport
        report = await self.analytics.generate_report(
            title=title,
            timeframe=tf,
            protocols=protocols,
            tokens=tokens,
            chains=chains,
        )

        return report.to_dict()

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def start_monitoring(self) -> None:
        """Démarre le monitoring en arrière-plan"""
        if self._is_running:
            return

        self._is_running = True
        logger.info("Démarrage du monitoring DeFi")

        # Tâches de monitoring
        self._monitor_tasks.extend([
            asyncio.create_task(self._monitor_positions()),
            asyncio.create_task(self._monitor_health()),
            asyncio.create_task(self._monitor_yields()),
            asyncio.create_task(self._monitor_risks()),
        ])

        # Démarrer le monitoring des sous-systèmes
        await self.aggregator.start_monitoring()
        await self.borrowing_manager.monitor_positions()

        # Monitoring de l'analytique
        asyncio.create_task(self._monitor_analytics())

    async def stop_monitoring(self) -> None:
        """Arrête le monitoring"""
        self._is_running = False

        for task in self._monitor_tasks:
            task.cancel()

        try:
            await asyncio.gather(*self._monitor_tasks, return_exceptions=True)
        except Exception:
            pass

        self._monitor_tasks.clear()
        logger.info("Monitoring DeFi arrêté")

    async def _monitor_positions(self) -> None:
        """Monitore les positions en continu"""
        while self._is_running:
            try:
                # Mise à jour des positions
                await self._update_state()

                # Vérification des health factors
                for position in self._state.positions:
                    if position.position_type == PositionType.DEBT:
                        health_factor = Decimal(str(position.metadata.get("health_factor", "999")))
                        if health_factor < self.manager_config.min_health_factor:
                            await self._send_alert({
                                "type": "low_health_factor",
                                "position_id": position.position_id,
                                "health_factor": str(health_factor),
                                "severity": "critical",
                            })

            except Exception as e:
                logger.error(f"Erreur de monitoring des positions: {e}")

            await asyncio.sleep(self.manager_config.monitoring_interval)

    async def _monitor_health(self) -> None:
        """Monitore la santé du système"""
        while self._is_running:
            try:
                # Vérification de la santé globale
                health_check = {
                    "status": self._status.value,
                    "active_protocols": len(self.config_manager.get_supported_protocols()),
                    "total_value": str(self._state.total_value_usd) if self._state else "0",
                    "risk_score": self._state.risk_score if self._state else 0.0,
                }

                # Alertes
                if self._state and self._state.risk_score > self.manager_config.max_risk_score:
                    await self._send_alert({
                        "type": "high_risk_score",
                        "risk_score": self._state.risk_score,
                        "threshold": self.manager_config.max_risk_score,
                        "severity": "warning",
                    })

            except Exception as e:
                logger.error(f"Erreur de monitoring de santé: {e}")

            await asyncio.sleep(self.manager_config.monitoring_interval * 5)

    async def _monitor_yields(self) -> None:
        """Monitore les rendements"""
        while self._is_running:
            try:
                # Récupération des meilleurs rendements
                tokens = self.config_manager.get_supported_tokens()
                chains = self.config_manager.get_supported_chains()

                for token in tokens[:5]:  # Limiter pour la performance
                    for chain in chains[:3]:
                        try:
                            yields = await self.get_best_yields(
                                token=token,
                                chain=chain,
                                amount=Decimal("1000"),
                            )
                            if yields:
                                best = yields[0]
                                self.metrics.record_gauge(
                                    "defi_best_yield",
                                    float(Decimal(best["apy"])),
                                    {"token": token, "chain": chain, "protocol": best["protocol"]},
                                )
                        except Exception as e:
                            logger.debug(f"Erreur pour {token} sur {chain}: {e}")

            except Exception as e:
                logger.error(f"Erreur de monitoring des rendements: {e}")

            await asyncio.sleep(self.manager_config.monitoring_interval * 10)

    async def _monitor_risks(self) -> None:
        """Monitore les risques"""
        while self._is_running:
            try:
                # Vérification des risques système
                risk_analysis = await self._analyze_system_risks()

                if risk_analysis.get("critical_risks"):
                    await self._send_alert({
                        "type": "system_risks",
                        "risks": risk_analysis["critical_risks"],
                        "severity": "critical",
                    })

            except Exception as e:
                logger.error(f"Erreur de monitoring des risques: {e}")

            await asyncio.sleep(self.manager_config.monitoring_interval * 15)

    async def _monitor_analytics(self) -> None:
        """Monitore l'analytique"""
        while self._is_running:
            try:
                # Mise à jour des métriques d'analytique
                overview = await self.analytics.get_market_overview()
                for key, value in overview.items():
                    if isinstance(value, Decimal):
                        self.metrics.record_gauge(
                            f"defi_market_{key}",
                            float(value),
                        )

            except Exception as e:
                logger.error(f"Erreur de monitoring de l'analytique: {e}")

            await asyncio.sleep(self.manager_config.monitoring_interval * 30)

    # ============================================================
    # MÉTHODES D'ANALYSE
    # ============================================================

    async def _analyze_system_risks(self) -> Dict[str, Any]:
        """Analyse les risques système"""
        risks = {
            "critical_risks": [],
            "warning_risks": [],
            "info_risks": [],
        }

        try:
            # Vérification du risque de liquidité
            if self._state and self._state.total_value_usd > 0:
                # Simulé - dans la réalité, on analyserait les données
                pass

            # Vérification des positions surexposées
            positions = self._state.positions if self._state else []
            if len(positions) > 0:
                # Analyse de la concentration
                total_value = sum(p.value_usd for p in positions)
                for pos in positions:
                    concentration = pos.value_usd / total_value
                    if concentration > Decimal("0.3"):
                        risks["warning_risks"].append({
                            "type": "concentration",
                            "position": pos.position_id,
                            "concentration": str(concentration),
                        })

            # Vérification des protocoles
            protocols = self.config_manager.get_supported_protocols()
            if len(protocols) < 2:
                risks["info_risks"].append({
                    "type": "low_diversification",
                    "message": "Peu de protocoles utilisés",
                })

            return risks

        except Exception as e:
            logger.error(f"Erreur d'analyse des risques: {e}")
            return risks

    # ============================================================
    # MÉTHODES DE MISE À JOUR
    # ============================================================

    async def _update_state(self) -> None:
        """Met à jour l'état du gestionnaire"""
        try:
            # Récupération des positions
            positions = []
            total_value = Decimal("0")
            total_apy = Decimal("0")
            count = 0

            # Positions de l'agrégateur
            for user in self._get_active_users():
                try:
                    user_positions = await self.get_positions(user)
                    positions.extend(user_positions)
                except Exception as e:
                    logger.debug(f"Erreur pour {user}: {e}")

            # Calcul des métriques
            for pos in positions:
                total_value += pos.value_usd
                total_apy += pos.apy
                count += 1

            if count > 0:
                total_apy = total_apy / count

            # Calcul du score de risque
            risk_score = self._calculate_risk_score(positions)

            # Mise à jour de l'état
            if self._state:
                self._state.positions = positions
                self._state.total_value_usd = total_value
                self._state.total_apy = total_apy
                self._state.risk_score = risk_score
                self._state.last_monitoring = datetime.now()
                self._state.status = self._status

            # Métriques
            self.metrics.record_gauge("defi_manager_total_value", float(total_value))
            self.metrics.record_gauge("defi_manager_total_apy", float(total_apy))
            self.metrics.record_gauge("defi_manager_risk_score", risk_score)

        except Exception as e:
            logger.error(f"Erreur de mise à jour de l'état: {e}")

    def _calculate_risk_score(self, positions: List[Position]) -> float:
        """Calcule le score de risque"""
        if not positions:
            return 0.0

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
        for pos in positions:
            risk_level = RiskLevel.MEDIUM  # Par défaut
            if pos.metadata.get("risk_level"):
                try:
                    risk_level = RiskLevel(pos.metadata["risk_level"])
                except ValueError:
                    pass

            weight = pos.value_usd / total_value
            weighted_risk += risk_scores.get(risk_level, 0.5) * float(weight)

        return weighted_risk

    def _get_active_users(self) -> List[str]:
        """Obtient la liste des utilisateurs actifs"""
        # Dans la réalité, on récupérerait depuis une base de données
        return ["0x..."]  # Placeholder

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_balance(self, token: str, chain: str, user: str) -> Decimal:
        """Obtient le solde d'un token"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            # Récupération de l'adresse du token
            token_config = self.config_manager.get_token_config(token)
            if not token_config:
                return Decimal("0")

            if token_config.is_native:
                balance = await provider.eth.get_balance(user)
                return Decimal(str(balance)) / Decimal(10 ** token_config.decimals)

            # Token ERC-20
            token_contract = provider.eth.contract(
                address=token_config.address,
                abi=self.ERC20_ABI,
            )
            balance = await token_contract.functions.balanceOf(user).call()
            return Decimal(str(balance)) / Decimal(10 ** token_config.decimals)

        except Exception as e:
            logger.warning(f"Erreur de solde pour {token} sur {chain}: {e}")
            return Decimal("0")

    async def _handle_alert(self, alert: Dict[str, Any]) -> None:
        """Gère une alerte"""
        logger.info(f"Alerte DeFi: {alert}")

        # Métrique
        self.metrics.record_increment(
            "defi_alert",
            1,
            {"type": alert.get("type", "unknown"), "severity": alert.get("severity", "info")},
        )

        # Envoi aux callbacks
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        await self._handle_alert(alert)

    # ============================================================
    # MÉTHODES DE CONTROLE
    # ============================================================

    def pause(self) -> None:
        """Met en pause le gestionnaire"""
        self._status = DeFiManagerStatus.PAUSED
        logger.info("DeFiManager mis en pause")

    def resume(self) -> None:
        """Reprend le gestionnaire"""
        self._status = DeFiManagerStatus.ACTIVE
        logger.info("DeFiManager repris")

    def emergency_stop(self) -> None:
        """Arrêt d'urgence"""
        self._status = DeFiManagerStatus.SHUTDOWN
        logger.warning("DeFiManager arrêté d'urgence")

        # Arrêt des sous-systèmes
        asyncio.create_task(self._emergency_cleanup())

    async def _emergency_cleanup(self) -> None:
        """Nettoyage d'urgence"""
        try:
            await self.stop_monitoring()

            # Fermeture des sous-systèmes
            await self.aggregator.cleanup()
            await self.borrowing_manager.cleanup()
            await self.analytics.cleanup()
            await self.aave.cleanup()
            await self.compound.cleanup()
            await self.curve.cleanup()

            logger.info("Nettoyage d'urgence terminé")

        except Exception as e:
            logger.error(f"Erreur lors du nettoyage d'urgence: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        return {
            "status": self._status.value,
            "total_value_usd": str(self._state.total_value_usd) if self._state else "0",
            "total_apy": str(self._state.total_apy) if self._state else "0",
            "positions_count": len(self._state.positions) if self._state else 0,
            "risk_score": self._state.risk_score if self._state else 0.0,
            "active_operations": len(self._active_operations),
            "is_running": self._is_running,
            "monitor_tasks": len(self._monitor_tasks),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources DeFiManager...")

        self._status = DeFiManagerStatus.SHUTDOWN

        await self.stop_monitoring()

        # Nettoyage des sous-systèmes
        await self.aggregator.cleanup()
        await self.borrowing_manager.cleanup()
        await self.analytics.cleanup()
        await self.aave.cleanup()
        await self.compound.cleanup()
        await self.curve.cleanup()
        await self.config_manager.cleanup()

        self._positions.clear()
        self._active_operations.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_defi_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> DeFiManager:
    """
    Crée une instance de DeFiManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiManager
    """
    return DeFiManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de DeFiManager"""
    # Configuration
    config = {
        "environment": "production",
        "max_investment": "1000000",
        "manager": {
            "auto_rebalance": True,
            "auto_compound": True,
            "min_health_factor": "1.2",
            "max_risk_score": 0.7,
            "rebalance_interval": 3600,
            "monitoring_interval": 60,
        },
        "aave": {},
        "compound": {},
        "curve": {},
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "polygon": Web3(Web3.HTTPProvider("https://polygon-rpc.com")),
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création du gestionnaire
    manager = create_defi_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE: {alert}")

    manager.add_alert_callback(alert_callback)

    # Démarrage du monitoring
    await manager.start_monitoring()

    # Exécution d'une stratégie
    result = await manager.execute_strategy(
        strategy_id="conservative_lending",
        user="0x1234567890123456789012345678901234567890",
        amount=Decimal("10000"),
        token="USDC",
        chain="ethereum",
        dry_run=True,
    )

    print(f"Résultat: {result}")

    # Obtention de l'état
    state = await manager.get_state()
    print(f"État: {state.to_dict()}")

    # Obtention des meilleurs rendements
    yields = await manager.get_best_yields(
        token="USDC",
        chain="ethereum",
        amount=Decimal("1000"),
    )

    print("Meilleurs rendements:")
    for y in yields[:5]:
        print(f"  {y['protocol']}: {y['apy']} APY")

    # Génération d'un rapport
    report = await manager.generate_report(
        title="Rapport DeFi",
        timeframe="week",
    )

    print(f"Rapport: {report}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

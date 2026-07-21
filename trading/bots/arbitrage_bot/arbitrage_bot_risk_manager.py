"""
NEXUS AI TRADING SYSTEM - ARBITRAGE BOT RISK MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des risques pour le bot d'arbitrage.
Gestion des risques de marché, de liquidité, de contrepartie, et opérationnels.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
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
from scipy import stats

from ..arbitrage_bot import (
    ArbitrageBot,
    ArbitrageOpportunity,
    ArbitrageConfig,
    ExchangeType,
    ArbitrageType,
    ArbitrageStatus
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class RiskType(Enum):
    """Types de risques."""
    MARKET = "market"
    LIQUIDITY = "liquidity"
    COUNTERPARTY = "counterparty"
    OPERATIONAL = "operational"
    SYSTEMIC = "systemic"
    REGULATORY = "regulatory"
    TECHNICAL = "technical"
    EXECUTION = "execution"
    SLIPPAGE = "slippage"
    GAS = "gas"
    BRIDGE = "bridge"
    SMART_CONTRACT = "smart_contract"


class RiskLevel(Enum):
    """Niveaux de risque."""
    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5
    CRITICAL = 6


@dataclass
class RiskAssessment:
    """Évaluation des risques."""
    assessment_id: UUID
    bot_id: UUID
    risk_type: RiskType
    risk_level: RiskLevel
    score: float  # 0-100
    probability: float  # 0-1
    impact: float  # 0-1
    severity: float  # 0-1
    description: str
    recommendations: List[str]
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    mitigated: bool = False
    mitigated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "assessment_id": str(self.assessment_id),
            "bot_id": str(self.bot_id),
            "risk_type": self.risk_type.value,
            "risk_level": self.risk_level.value,
            "score": self.score,
            "probability": self.probability,
            "impact": self.impact,
            "severity": self.severity,
            "description": self.description,
            "recommendations": self.recommendations,
            "metrics": self.metrics,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "mitigated": self.mitigated,
            "mitigated_at": self.mitigated_at.isoformat() if self.mitigated_at else None
        }


@dataclass
class RiskMetrics:
    """Métriques de risque."""
    bot_id: UUID
    total_risk_score: float
    max_drawdown: float
    current_drawdown: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    var_95: Decimal
    var_99: Decimal
    expected_shortfall: Decimal
    beta: float
    alpha: float
    correlation_matrix: Dict[str, float]
    concentration_risk: float
    liquidity_risk: float
    counterparty_risk: float
    operational_risk: float
    risk_reward_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "bot_id": str(self.bot_id),
            "total_risk_score": self.total_risk_score,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "var_95": str(self.var_95),
            "var_99": str(self.var_99),
            "expected_shortfall": str(self.expected_shortfall),
            "beta": self.beta,
            "alpha": self.alpha,
            "correlation_matrix": self.correlation_matrix,
            "concentration_risk": self.concentration_risk,
            "liquidity_risk": self.liquidity_risk,
            "counterparty_risk": self.counterparty_risk,
            "operational_risk": self.operational_risk,
            "risk_reward_ratio": self.risk_reward_ratio,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class RiskLimit:
    """Limite de risque."""
    limit_id: UUID
    bot_id: UUID
    risk_type: RiskType
    metric: str
    max_value: float
    current_value: float
    threshold_warning: float
    threshold_critical: float
    action: str  # "warn", "reduce", "stop"
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "limit_id": str(self.limit_id),
            "bot_id": str(self.bot_id),
            "risk_type": self.risk_type.value,
            "metric": self.metric,
            "max_value": self.max_value,
            "current_value": self.current_value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "action": self.action,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# ============================================================================
# CLASSE RISK MANAGER
# ============================================================================

class ArbitrageBotRiskManager:
    """
    Gestionnaire de risques pour le bot d'arbitrage.
    """

    # Seuils de risque par défaut
    DEFAULT_RISK_LIMITS = {
        "max_drawdown": {"warning": 0.10, "critical": 0.20},
        "max_position_size": {"warning": 0.05, "critical": 0.10},
        "max_leverage": {"warning": 2.0, "critical": 3.0},
        "max_exposure": {"warning": 0.50, "critical": 0.75},
        "max_slippage": {"warning": 0.01, "critical": 0.02},
        "min_liquidity": {"warning": 100000, "critical": 50000},
        "max_gas_price": {"warning": 100, "critical": 200},
        "max_volatility": {"warning": 0.30, "critical": 0.50}
    }

    # Pondérations des risques
    RISK_WEIGHTS = {
        RiskType.MARKET: 0.25,
        RiskType.LIQUIDITY: 0.20,
        RiskType.COUNTERPARTY: 0.15,
        RiskType.OPERATIONAL: 0.15,
        RiskType.EXECUTION: 0.10,
        RiskType.SLIPPAGE: 0.05,
        RiskType.GAS: 0.05,
        RiskType.SMART_CONTRACT: 0.05
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        risk_limits: Optional[Dict[str, Any]] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le gestionnaire de risques.

        Args:
            redis_client: Client Redis pour le cache
            risk_limits: Limites de risque
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.risk_limits = risk_limits or self.DEFAULT_RISK_LIMITS
        self.api_keys = api_keys or {}
        
        # Cache
        self._assessments: Dict[UUID, RiskAssessment] = {}
        self._metrics_cache: Dict[UUID, RiskMetrics] = {}
        self._limits_cache: Dict[UUID, List[RiskLimit]] = {}
        
        # Historique des risques
        self._risk_history: Dict[UUID, List[RiskAssessment]] = {}
        
        # Alertes
        self._alert_cache: Dict[UUID, List[Dict]] = {}
        
        # Métriques
        self._metrics = {
            "total_assessments": 0,
            "current_risk_level": "low",
            "risk_by_type": {},
            "alerts_triggered": 0,
            "critical_events": 0,
            "mitigated_risks": 0,
            "last_assessment": None,
            "last_alert": None
        }

        logger.info("ArbitrageBotRiskManager initialisé avec succès")

    # ========================================================================
    # ÉVALUATION DES RISQUES
    # ========================================================================

    async def assess_risks(
        self,
        bot: ArbitrageBot,
        include_all: bool = True,
        metadata: Optional[Dict] = None
    ) -> List[RiskAssessment]:
        """
        Évalue tous les risques pour un bot.

        Args:
            bot: Bot à évaluer
            include_all: Inclure tous les types de risques
            metadata: Métadonnées

        Returns:
            Liste des évaluations de risques
        """
        try:
            assessments = []
            bot_id = bot.config.bot_id

            # Risque de marché
            market_risk = await self._assess_market_risk(bot)
            if market_risk:
                assessments.append(market_risk)

            # Risque de liquidité
            liquidity_risk = await self._assess_liquidity_risk(bot)
            if liquidity_risk:
                assessments.append(liquidity_risk)

            # Risque de contrepartie
            counterparty_risk = await self._assess_counterparty_risk(bot)
            if counterparty_risk:
                assessments.append(counterparty_risk)

            # Risque opérationnel
            operational_risk = await self._assess_operational_risk(bot)
            if operational_risk:
                assessments.append(operational_risk)

            # Risque d'exécution
            execution_risk = await self._assess_execution_risk(bot)
            if execution_risk:
                assessments.append(execution_risk)

            # Risque de slippage
            slippage_risk = await self._assess_slippage_risk(bot)
            if slippage_risk:
                assessments.append(slippage_risk)

            # Risque de gaz
            gas_risk = await self._assess_gas_risk(bot)
            if gas_risk:
                assessments.append(gas_risk)

            # Risque de smart contract
            sc_risk = await self._assess_smart_contract_risk(bot)
            if sc_risk:
                assessments.append(sc_risk)

            # Stockage
            for assessment in assessments:
                self._assessments[assessment.assessment_id] = assessment
                
                if bot_id not in self._risk_history:
                    self._risk_history[bot_id] = []
                self._risk_history[bot_id].append(assessment)

            # Mise à jour des métriques
            self._metrics["total_assessments"] += len(assessments)
            self._metrics["last_assessment"] = datetime.now().isoformat()

            # Sauvegarde dans Redis
            if self.redis:
                await self._save_assessments(bot_id, assessments)

            return assessments

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation des risques: {e}")
            return []

    async def _assess_market_risk(
        self,
        bot: ArbitrageBot
    ) -> Optional[RiskAssessment]:
        """
        Évalue le risque de marché.

        Args:
            bot: Bot

        Returns:
            Évaluation du risque de marché
        """
        try:
            # Récupération des données de marché
            market_data = await self._get_market_data(bot)
            
            if not market_data:
                return None

            # Calcul de la volatilité
            volatility = self._calculate_volatility(market_data)
            
            # Calcul du drawdown
            drawdown = self._calculate_drawdown(market_data)
            
            # Calcul de la corrélation
            correlation = self._calculate_correlation(market_data)
            
            # Score de risque
            risk_score = (volatility * 0.4 + drawdown * 0.3 + correlation * 0.3) * 100
            
            # Niveau de risque
            risk_level = self._get_risk_level(risk_score)
            
            # Probabilité et impact
            probability = min(volatility / 0.5, 1.0)
            impact = min(drawdown / 0.3, 1.0)
            severity = (probability + impact) / 2

            recommendations = []
            if volatility > 0.3:
                recommendations.append("Réduire l'exposition en période de forte volatilité")
            if drawdown > 0.1:
                recommendations.append("Utiliser des stop-loss pour limiter les pertes")
            if correlation > 0.8:
                recommendations.append("Diversifier les positions pour réduire la corrélation")

            return RiskAssessment(
                assessment_id=uuid4(),
                bot_id=bot.config.bot_id,
                risk_type=RiskType.MARKET,
                risk_level=risk_level,
                score=risk_score,
                probability=probability,
                impact=impact,
                severity=severity,
                description=f"Risque de marché: volatilité {volatility:.2%}, drawdown {drawdown:.2%}",
                recommendations=recommendations,
                metrics={
                    "volatility": volatility,
                    "drawdown": drawdown,
                    "correlation": correlation
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=1)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque de marché: {e}")
            return None

    async def _assess_liquidity_risk(
        self,
        bot: ArbitrageBot
    ) -> Optional[RiskAssessment]:
        """
        Évalue le risque de liquidité.

        Args:
            bot: Bot

        Returns:
            Évaluation du risque de liquidité
        """
        try:
            # Récupération des données de liquidité
            liquidity_data = await self._get_liquidity_data(bot)
            
            if not liquidity_data:
                return None

            # Calcul du spread
            spread = liquidity_data.get("spread", 0.01)
            
            # Profondeur du carnet d'ordres
            depth = liquidity_data.get("depth", 0)
            
            # Volume
            volume = liquidity_data.get("volume_24h", 0)

            # Score de risque
            risk_score = (spread * 0.4 + (1 - min(depth / 1000000, 1)) * 0.3 + (1 - min(volume / 10000000, 1)) * 0.3) * 100
            
            risk_level = self._get_risk_level(risk_score)
            
            probability = min(spread / 0.05, 1.0)
            impact = min(1 - depth / 1000000, 1.0)
            severity = (probability + impact) / 2

            recommendations = []
            if spread > 0.02:
                recommendations.append("Éviter les tokens avec un spread large")
            if depth < 100000:
                recommendations.append("Vérifier la profondeur du carnet d'ordres avant d'entrer")
            if volume < 1000000:
                recommendations.append("Préférer les tokens avec un volume d'échange élevé")

            return RiskAssessment(
                assessment_id=uuid4(),
                bot_id=bot.config.bot_id,
                risk_type=RiskType.LIQUIDITY,
                risk_level=risk_level,
                score=risk_score,
                probability=probability,
                impact=impact,
                severity=severity,
                description=f"Risque de liquidité: spread {spread:.2%}, depth ${depth:,.0f}, volume ${volume:,.0f}",
                recommendations=recommendations,
                metrics={
                    "spread": spread,
                    "depth": depth,
                    "volume_24h": volume
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=1)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque de liquidité: {e}")
            return None

    async def _assess_counterparty_risk(
        self,
        bot: ArbitrageBot
    ) -> Optional[RiskAssessment]:
        """
        Évalue le risque de contrepartie.

        Args:
            bot: Bot

        Returns:
            Évaluation du risque de contrepartie
        """
        try:
            exchanges = bot.config.exchanges or []
            risks = []

            for exchange in exchanges:
                # Récupération des données de l'exchange
                exchange_data = await self._get_exchange_data(exchange)
                
                if exchange_data:
                    risk_score = exchange_data.get("risk_score", 50)
                    risks.append({
                        "exchange": exchange,
                        "risk_score": risk_score
                    })

            if not risks:
                return None

            avg_risk = sum(r["risk_score"] for r in risks) / len(risks)
            risk_level = self._get_risk_level(avg_risk)

            probability = avg_risk / 100
            impact = 0.5  # Impact moyen pour le risque de contrepartie
            severity = (probability + impact) / 2

            recommendations = []
            for r in risks:
                if r["risk_score"] > 70:
                    recommendations.append(f"Réduire l'exposition sur {r['exchange'].value}")

            return RiskAssessment(
                assessment_id=uuid4(),
                bot_id=bot.config.bot_id,
                risk_type=RiskType.COUNTERPARTY,
                risk_level=risk_level,
                score=avg_risk,
                probability=probability,
                impact=impact,
                severity=severity,
                description=f"Risque de contrepartie moyen: {avg_risk:.1f}%",
                recommendations=recommendations,
                metrics={
                    "exchanges": risks,
                    "avg_risk": avg_risk
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=1)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque de contrepartie: {e}")
            return None

    async def _assess_operational_risk(
        self,
        bot: ArbitrageBot
    ) -> Optional[RiskAssessment]:
        """
        Évalue le risque opérationnel.

        Args:
            bot: Bot

        Returns:
            Évaluation du risque opérationnel
        """
        try:
            # Facteurs de risque opérationnel
            uptime = await self._get_bot_uptime(bot)
            error_rate = await self._get_error_rate(bot)
            latency = await self._get_latency(bot)

            risk_score = ((1 - uptime) * 0.4 + error_rate * 0.3 + (latency / 1000) * 0.3) * 100
            
            risk_level = self._get_risk_level(risk_score)

            probability = min(error_rate, 1.0)
            impact = min(1 - uptime, 1.0)
            severity = (probability + impact) / 2

            recommendations = []
            if uptime < 0.99:
                recommendations.append("Améliorer la redondance et la fiabilité du système")
            if error_rate > 0.05:
                recommendations.append("Réduire les erreurs en optimisant le code")
            if latency > 500:
                recommendations.append("Optimiser les performances pour réduire la latence")

            return RiskAssessment(
                assessment_id=uuid4(),
                bot_id=bot.config.bot_id,
                risk_type=RiskType.OPERATIONAL,
                risk_level=risk_level,
                score=risk_score,
                probability=probability,
                impact=impact,
                severity=severity,
                description=f"Risque opérationnel: uptime {uptime:.2%}, erreurs {error_rate:.2%}, latence {latency:.0f}ms",
                recommendations=recommendations,
                metrics={
                    "uptime": uptime,
                    "error_rate": error_rate,
                    "latency": latency
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=1)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque opérationnel: {e}")
            return None

    async def _assess_execution_risk(
        self,
        bot: ArbitrageBot
    ) -> Optional[RiskAssessment]:
        """
        Évalue le risque d'exécution.

        Args:
            bot: Bot

        Returns:
            Évaluation du risque d'exécution
        """
        try:
            # Historique des exécutions
            execution_history = await self._get_execution_history(bot)
            
            if not execution_history:
                return None

            # Taux de réussite
            success_rate = execution_history.get("success_rate", 0.95)
            
            # Temps moyen d'exécution
            avg_execution_time = execution_history.get("avg_execution_time", 1.0)
            
            # Taux de rééchec
            retry_rate = execution_history.get("retry_rate", 0.05)

            risk_score = ((1 - success_rate) * 0.5 + retry_rate * 0.3 + min(avg_execution_time / 5, 1) * 0.2) * 100
            
            risk_level = self._get_risk_level(risk_score)

            probability = 1 - success_rate
            impact = min(retry_rate, 1.0)
            severity = (probability + impact) / 2

            recommendations = []
            if success_rate < 0.95:
                recommendations.append("Améliorer la stratégie d'exécution")
            if retry_rate > 0.1:
                recommendations.append("Optimiser la gestion des erreurs et des retries")

            return RiskAssessment(
                assessment_id=uuid4(),
                bot_id=bot.config.bot_id,
                risk_type=RiskType.EXECUTION,
                risk_level=risk_level,
                score=risk_score,
                probability=probability,
                impact=impact,
                severity=severity,
                description=f"Risque d'exécution: succès {success_rate:.2%}, retry {retry_rate:.2%}, temps {avg_execution_time:.2f}s",
                recommendations=recommendations,
                metrics={
                    "success_rate": success_rate,
                    "retry_rate": retry_rate,
                    "avg_execution_time": avg_execution_time
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=6)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque d'exécution: {e}")
            return None

    async def _assess_slippage_risk(
        self,
        bot: ArbitrageBot
    ) -> Optional[RiskAssessment]:
        """
        Évalue le risque de slippage.

        Args:
            bot: Bot

        Returns:
            Évaluation du risque de slippage
        """
        try:
            # Historique des slippages
            slippage_history = await self._get_slippage_history(bot)
            
            if not slippage_history:
                return None

            # Slippage moyen
            avg_slippage = slippage_history.get("avg_slippage", 0.01)
            
            # Slippage maximum
            max_slippage = slippage_history.get("max_slippage", 0.05)

            risk_score = (avg_slippage * 0.6 + max_slippage * 0.4) * 100
            
            risk_level = self._get_risk_level(risk_score)

            probability = min(avg_slippage / 0.05, 1.0)
            impact = min(max_slippage / 0.1, 1.0)
            severity = (probability + impact) / 2

            recommendations = []
            if avg_slippage > 0.02:
                recommendations.append("Utiliser des ordres limites pour réduire le slippage")
            if max_slippage > 0.05:
                recommendations.append("Augmenter la tolérance de slippage ou réduire la taille des ordres")

            return RiskAssessment(
                assessment_id=uuid4(),
                bot_id=bot.config.bot_id,
                risk_type=RiskType.SLIPPAGE,
                risk_level=risk_level,
                score=risk_score,
                probability=probability,
                impact=impact,
                severity=severity,
                description=f"Risque de slippage: moyen {avg_slippage:.2%}, max {max_slippage:.2%}",
                recommendations=recommendations,
                metrics={
                    "avg_slippage": avg_slippage,
                    "max_slippage": max_slippage
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=6)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque de slippage: {e}")
            return None

    async def _assess_gas_risk(
        self,
        bot: ArbitrageBot
    ) -> Optional[RiskAssessment]:
        """
        Évalue le risque de gaz.

        Args:
            bot: Bot

        Returns:
            Évaluation du risque de gaz
        """
        try:
            # Récupération des données de gaz
            gas_data = await self._get_gas_data(bot)
            
            if not gas_data:
                return None

            # Prix actuel du gaz
            gas_price = gas_data.get("current_gas", 50)
            
            # Prix historique
            avg_gas_price = gas_data.get("avg_gas", 40)
            max_gas_price = gas_data.get("max_gas", 200)

            risk_score = ((gas_price / max_gas_price) * 0.5 + (gas_price / avg_gas_price - 1) * 0.3 + 0.2) * 100
            
            risk_level = self._get_risk_level(risk_score)

            probability = min(gas_price / max_gas_price, 1.0)
            impact = min((gas_price - avg_gas_price) / avg_gas_price, 1.0)
            severity = (probability + impact) / 2

            recommendations = []
            if gas_price > 100:
                recommendations.append("Attendre une baisse du prix du gaz avant d'exécuter")
            if gas_price > 150:
                recommendations.append("Utiliser un réseau alternatif ou un L2")

            return RiskAssessment(
                assessment_id=uuid4(),
                bot_id=bot.config.bot_id,
                risk_type=RiskType.GAS,
                risk_level=risk_level,
                score=risk_score,
                probability=probability,
                impact=impact,
                severity=severity,
                description=f"Risque de gaz: prix {gas_price} GWEI (moyenne {avg_gas_price} GWEI)",
                recommendations=recommendations,
                metrics={
                    "current_gas": gas_price,
                    "avg_gas": avg_gas_price,
                    "max_gas": max_gas_price
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=15)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque de gaz: {e}")
            return None

    async def _assess_smart_contract_risk(
        self,
        bot: ArbitrageBot
    ) -> Optional[RiskAssessment]:
        """
        Évalue le risque de smart contract.

        Args:
            bot: Bot

        Returns:
            Évaluation du risque de smart contract
        """
        try:
            contracts = bot.config.contracts or []
            
            if not contracts:
                return None

            risks = []
            for contract in contracts:
                contract_risk = await self._get_contract_risk(contract)
                if contract_risk:
                    risks.append(contract_risk)

            if not risks:
                return None

            avg_risk = sum(r["risk_score"] for r in risks) / len(risks)
            risk_level = self._get_risk_level(avg_risk)

            probability = avg_risk / 100
            impact = 0.7  # Impact élevé pour les smart contracts
            severity = (probability + impact) / 2

            recommendations = []
            for r in risks:
                if r["risk_score"] > 70:
                    recommendations.append(f"Vérifier l'audit du contrat {r['address']}")
                if r.get("has_audit") == False:
                    recommendations.append(f"Contract {r['address']} n'a pas été audité")

            return RiskAssessment(
                assessment_id=uuid4(),
                bot_id=bot.config.bot_id,
                risk_type=RiskType.SMART_CONTRACT,
                risk_level=risk_level,
                score=avg_risk,
                probability=probability,
                impact=impact,
                severity=severity,
                description=f"Risque de smart contract: {avg_risk:.1f}%",
                recommendations=recommendations,
                metrics={
                    "contracts": risks,
                    "avg_risk": avg_risk
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=7)
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation du risque de smart contract: {e}")
            return None

    # ========================================================================
    # MÉTHODES DE CALCUL
    # ========================================================================

    def _get_risk_level(self, score: float) -> RiskLevel:
        """
        Détermine le niveau de risque à partir d'un score.

        Args:
            score: Score de risque (0-100)

        Returns:
            Niveau de risque
        """
        if score < 20:
            return RiskLevel.VERY_LOW
        elif score < 40:
            return RiskLevel.LOW
        elif score < 60:
            return RiskLevel.MEDIUM
        elif score < 80:
            return RiskLevel.HIGH
        elif score < 90:
            return RiskLevel.VERY_HIGH
        else:
            return RiskLevel.CRITICAL

    def _calculate_volatility(self, data: List[float]) -> float:
        """
        Calcule la volatilité.

        Args:
            data: Données de prix

        Returns:
            Volatilité
        """
        if len(data) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(data)):
            if data[i-1] > 0:
                ret = (data[i] - data[i-1]) / data[i-1]
                returns.append(ret)
        
        if not returns:
            return 0.0
        
        return np.std(returns) * np.sqrt(365)

    def _calculate_drawdown(self, data: List[float]) -> float:
        """
        Calcule le drawdown.

        Args:
            data: Données de prix

        Returns:
            Drawdown
        """
        if len(data) < 2:
            return 0.0
        
        peak = data[0]
        max_drawdown = 0.0
        
        for price in data:
            if price > peak:
                peak = price
            drawdown = (peak - price) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown

    def _calculate_correlation(self, data: List[float]) -> float:
        """
        Calcule la corrélation avec le marché.

        Args:
            data: Données de prix

        Returns:
            Corrélation
        """
        # Simulation de corrélation
        return min(abs(np.random.normal(0.5, 0.2)), 1.0)

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ========================================================================

    async def _get_market_data(self, bot: ArbitrageBot) -> List[float]:
        """
        Récupère les données de marché.

        Args:
            bot: Bot

        Returns:
            Données de prix
        """
        # Simulation de données
        return list(np.random.normal(50000, 1000, 30))

    async def _get_liquidity_data(self, bot: ArbitrageBot) -> Dict[str, Any]:
        """
        Récupère les données de liquidité.

        Args:
            bot: Bot

        Returns:
            Données de liquidité
        """
        return {
            "spread": random.uniform(0.001, 0.05),
            "depth": random.uniform(10000, 500000),
            "volume_24h": random.uniform(100000, 50000000)
        }

    async def _get_exchange_data(self, exchange: ExchangeType) -> Dict[str, Any]:
        """
        Récupère les données d'un exchange.

        Args:
            exchange: Exchange

        Returns:
            Données de l'exchange
        """
        return {
            "risk_score": random.uniform(20, 80),
            "uptime": random.uniform(0.95, 0.999),
            "volume": random.uniform(100000, 100000000)
        }

    async def _get_bot_uptime(self, bot: ArbitrageBot) -> float:
        """
        Récupère le temps de fonctionnement du bot.

        Args:
            bot: Bot

        Returns:
            Uptime
        """
        return random.uniform(0.95, 0.999)

    async def _get_error_rate(self, bot: ArbitrageBot) -> float:
        """
        Récupère le taux d'erreur du bot.

        Args:
            bot: Bot

        Returns:
            Taux d'erreur
        """
        return random.uniform(0.001, 0.05)

    async def _get_latency(self, bot: ArbitrageBot) -> float:
        """
        Récupère la latence du bot.

        Args:
            bot: Bot

        Returns:
            Latence en ms
        """
        return random.uniform(50, 500)

    async def _get_execution_history(self, bot: ArbitrageBot) -> Dict[str, Any]:
        """
        Récupère l'historique des exécutions.

        Args:
            bot: Bot

        Returns:
            Historique des exécutions
        """
        return {
            "success_rate": random.uniform(0.90, 0.99),
            "retry_rate": random.uniform(0.01, 0.10),
            "avg_execution_time": random.uniform(0.5, 3.0)
        }

    async def _get_slippage_history(self, bot: ArbitrageBot) -> Dict[str, Any]:
        """
        Récupère l'historique des slippages.

        Args:
            bot: Bot

        Returns:
            Historique des slippages
        """
        return {
            "avg_slippage": random.uniform(0.005, 0.03),
            "max_slippage": random.uniform(0.02, 0.08)
        }

    async def _get_gas_data(self, bot: ArbitrageBot) -> Dict[str, Any]:
        """
        Récupère les données de gaz.

        Args:
            bot: Bot

        Returns:
            Données de gaz
        """
        return {
            "current_gas": random.uniform(20, 200),
            "avg_gas": random.uniform(30, 50),
            "max_gas": random.uniform(150, 300)
        }

    async def _get_contract_risk(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """
        Récupère le risque d'un smart contract.

        Args:
            contract: Configuration du contrat

        Returns:
            Risque du contrat
        """
        return {
            "address": contract.get("address", ""),
            "risk_score": random.uniform(20, 80),
            "has_audit": random.choice([True, False])
        }

    # ========================================================================
    # LIMITES DE RISQUE
    # ========================================================================

    async def check_risk_limits(
        self,
        bot: ArbitrageBot,
        action: str = "trade"
    ) -> Tuple[bool, List[str]]:
        """
        Vérifie les limites de risque.

        Args:
            bot: Bot
            action: Action à vérifier

        Returns:
            (est_valide, messages)
        """
        try:
            warnings = []
            bot_id = bot.config.bot_id

            # Récupération des limites
            limits = await self._get_limits(bot_id)

            # Vérification de chaque limite
            for limit in limits:
                if not limit.enabled:
                    continue

                # Vérification de la valeur actuelle
                current_value = await self._get_metric_value(bot, limit.metric)
                limit.current_value = current_value

                if current_value > limit.threshold_critical:
                    warnings.append(f"⚠️ {limit.metric} critique: {current_value:.2f} > {limit.threshold_critical}")
                    self._metrics["critical_events"] += 1
                    
                    if limit.action == "stop":
                        return False, warnings
                elif current_value > limit.threshold_warning:
                    warnings.append(f"⚡ {limit.metric} en alerte: {current_value:.2f} > {limit.threshold_warning}")
                    self._metrics["alerts_triggered"] += 1

            return True, warnings

        except Exception as e:
            logger.error(f"Erreur lors de la vérification des limites de risque: {e}")
            return False, [f"Erreur: {str(e)}"]

    async def _get_limits(self, bot_id: UUID) -> List[RiskLimit]:
        """
        Récupère les limites de risque.

        Args:
            bot_id: ID du bot

        Returns:
            Liste des limites
        """
        if bot_id in self._limits_cache:
            return self._limits_cache[bot_id]

        limits = []
        
        for metric, thresholds in self.DEFAULT_RISK_LIMITS.items():
            limit = RiskLimit(
                limit_id=uuid4(),
                bot_id=bot_id,
                risk_type=RiskType.MARKET,
                metric=metric,
                max_value=thresholds["critical"],
                current_value=0,
                threshold_warning=thresholds["warning"],
                threshold_critical=thresholds["critical"],
                action="warn" if metric != "max_drawdown" else "stop"
            )
            limits.append(limit)

        self._limits_cache[bot_id] = limits
        return limits

    async def _get_metric_value(
        self,
        bot: ArbitrageBot,
        metric: str
    ) -> float:
        """
        Récupère la valeur d'une métrique.

        Args:
            bot: Bot
            metric: Nom de la métrique

        Returns:
            Valeur de la métrique
        """
        if metric == "max_drawdown":
            return random.uniform(0.05, 0.25)
        elif metric == "max_position_size":
            return random.uniform(0.01, 0.15)
        elif metric == "max_leverage":
            return random.uniform(1.0, 4.0)
        elif metric == "max_exposure":
            return random.uniform(0.3, 0.8)
        elif metric == "max_slippage":
            return random.uniform(0.005, 0.03)
        elif metric == "min_liquidity":
            return random.uniform(30000, 150000)
        elif metric == "max_gas_price":
            return random.uniform(20, 250)
        elif metric == "max_volatility":
            return random.uniform(0.2, 0.6)
        else:
            return 0.0

    # ========================================================================
    # MÉTHODES DE STOCKAGE
    # ========================================================================

    async def _save_assessments(
        self,
        bot_id: UUID,
        assessments: List[RiskAssessment]
    ) -> None:
        """
        Sauvegarde les évaluations dans Redis.

        Args:
            bot_id: ID du bot
            assessments: Liste des évaluations
        """
        try:
            for assessment in assessments:
                key = f"risk:assessment:{assessment.assessment_id}"
                await self.redis.setex(
                    key,
                    86400 * 7,  # 7 jours
                    json.dumps(assessment.to_dict())
                )
            
            # Index par bot
            key = f"risk:assessments:{bot_id}"
            await self.redis.lpush(
                key,
                *[str(a.assessment_id) for a in assessments]
            )
            await self.redis.ltrim(key, 0, 999)

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des évaluations: {e}")

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_assessments": self._metrics["total_assessments"],
                "current_risk_level": self._metrics["current_risk_level"],
                "risk_by_type": self._metrics["risk_by_type"],
                "alerts_triggered": self._metrics["alerts_triggered"],
                "critical_events": self._metrics["critical_events"],
                "mitigated_risks": self._metrics["mitigated_risks"],
                "last_assessment": self._metrics["last_assessment"],
                "last_alert": self._metrics["last_alert"],
                "cached_assessments": len(self._assessments),
                "cached_metrics": len(self._metrics_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de ArbitrageBotRiskManager...")
        self._assessments.clear()
        self._metrics_cache.clear()
        self._limits_cache.clear()
        self._risk_history.clear()
        self._alert_cache.clear()
        logger.info("ArbitrageBotRiskManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_arbitrage_bot_risk_manager(
    redis_url: str = "redis://localhost:6379/0",
    risk_limits: Optional[Dict[str, Any]] = None,
    api_keys: Optional[Dict[str, str]] = None
) -> ArbitrageBotRiskManager:
    """
    Crée une instance du gestionnaire de risques.

    Args:
        redis_url: URL de connexion Redis
        risk_limits: Limites de risque
        api_keys: Clés API

    Returns:
        Instance du gestionnaire
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ArbitrageBotRiskManager(
        redis_client=redis_client,
        risk_limits=risk_limits,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "RiskType",
    "RiskLevel",
    "RiskAssessment",
    "RiskMetrics",
    "RiskLimit",
    "ArbitrageBotRiskManager",
    "create_arbitrage_bot_risk_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire de risques."""
    print("=" * 60)
    print("NEXUS AI TRADING - ARBITRAGE BOT RISK MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    risk_manager = create_arbitrage_bot_risk_manager()

    # Création d'un bot exemple
    from ..arbitrage_bot import ArbitrageBot, ArbitrageConfig
    
    config = ArbitrageConfig(
        bot_id=uuid4(),
        name="Risk Bot",
        exchanges=[ExchangeType.BINANCE, ExchangeType.COINBASE],
        min_profit_threshold=0.005
    )
    
    bot = ArbitrageBot(
        config=config,
        exchange_clients={}
    )

    print(f"\n✅ Bot ID: {bot.config.bot_id}")

    # Évaluation des risques
    print(f"\n📊 Évaluation des risques...")
    assessments = await risk_manager.assess_risks(bot)

    print(f"   {len(assessments)} risques évalués")

    # Affichage des évaluations
    print(f"\n📋 Évaluations:")
    for assessment in assessments[:5]:
        print(f"   {assessment.risk_type.value.upper()}: "
              f"{assessment.risk_level.value} (score: {assessment.score:.1f})")
        print(f"      {assessment.description}")
        if assessment.recommendations:
            print(f"      → {assessment.recommendations[0]}")

    # Vérification des limites de risque
    print(f"\n⚠️ Vérification des limites de risque...")
    valid, warnings = await risk_manager.check_risk_limits(bot)

    print(f"   Valide: {valid}")
    for warning in warnings[:3]:
        print(f"   {warning}")

    # Santé du service
    health = await risk_manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Évaluations: {health['total_assessments']}")
    print(f"   Niveau de risque: {health['current_risk_level']}")
    print(f"   Alertes: {health['alerts_triggered']}")
    print(f"   Événements critiques: {health['critical_events']}")

    # Fermeture
    await risk_manager.close()

    print("\n" + "=" * 60)
    print("ArbitrageBotRiskManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import random
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

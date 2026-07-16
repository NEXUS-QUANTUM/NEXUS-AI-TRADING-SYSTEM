# blockchain/defi/defi_analytics.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module DeFi Analytics - Analytique Avancée des Protocoles DeFi

Ce module implémente un système complet d'analytique pour les protocoles DeFi,
permettant l'analyse des rendements, des risques, des volumes, et des tendances
du marché DeFi.

Fonctionnalités principales:
- Analyse des rendements (APY/APR)
- Analyse des risques (volatilité, liquidité)
- Analyse des volumes de trading
- Analyse des TVL (Total Value Locked)
- Analyse des tendances du marché
- Analyse des corrélations
- Analyse des portefeuilles
- Métriques de performance
- Rapports automatisés
- Alertes de marché
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
import statistics

import aiohttp
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats

# Import des modules internes
try:
    from ..core.exceptions import AnalyticsError, DeFiError
    from ..core.logging import get_logger
    from ..core.metrics import MetricsCollector
    from ..core.retry import async_retry, RetryConfig
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel, YieldData
    from .aave import AaveIntegration
    from .compound import CompoundIntegration
    from .curve import CurveIntegration
    from .defi_aggregator import DeFiAggregator
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import AnalyticsError, DeFiError
    from ..core.metrics import MetricsCollector
    from ..core.retry import async_retry, RetryConfig
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel, YieldData
    from .aave import AaveIntegration
    from .compound import CompoundIntegration
    from .curve import CurveIntegration
    from .defi_aggregator import DeFiAggregator

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class AnalyticsTimeframe(Enum):
    """Périodes d'analyse"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class AnalyticsMetric(Enum):
    """Métriques d'analyse"""
    # Rendements
    APY = "apy"
    APR = "apr"
    TOTAL_YIELD = "total_yield"
    YIELD_DAILY = "yield_daily"
    YIELD_WEEKLY = "yield_weekly"
    YIELD_MONTHLY = "yield_monthly"
    
    # Risques
    VOLATILITY = "volatility"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    VAR_95 = "var_95"
    CVAR_95 = "cvar_95"
    
    # Volumes
    VOLUME_24H = "volume_24h"
    VOLUME_7D = "volume_7d"
    VOLUME_30D = "volume_30d"
    TVL = "tvl"
    TVL_CHANGE = "tvl_change"
    
    # Utilisateurs
    ACTIVE_USERS = "active_users"
    NEW_USERS = "new_users"
    USER_RETENTION = "user_retention"
    
    # Performance
    TOTAL_VALUE = "total_value"
    PNL = "pnl"
    ROI = "roi"
    ALPHA = "alpha"
    BETA = "beta"


@dataclass
class DeFiAnalyticsData:
    """Données d'analytique DeFi"""
    timestamp: datetime
    protocol: str
    chain: str
    token: str
    metrics: Dict[AnalyticsMetric, Decimal]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "protocol": self.protocol,
            "chain": self.chain,
            "token": self.token,
            "metrics": {k.value: str(v) for k, v in self.metrics.items()},
            "metadata": self.metadata,
        }


@dataclass
class DeFiReport:
    """Rapport DeFi"""
    report_id: str
    title: str
    timeframe: AnalyticsTimeframe
    start_date: datetime
    end_date: datetime
    summary: Dict[str, Any]
    metrics: Dict[AnalyticsMetric, List[DeFiAnalyticsData]]
    insights: List[str]
    recommendations: List[str]
    generated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "report_id": self.report_id,
            "title": self.title,
            "timeframe": self.timeframe.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "summary": self.summary,
            "metrics": {
                k.value: [m.to_dict() for m in v]
                for k, v in self.metrics.items()
            },
            "insights": self.insights,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class DeFiPositionAnalytics:
    """Analytique de position DeFi"""
    position_id: str
    protocol: str
    chain: str
    token: str
    initial_amount: Decimal
    current_amount: Decimal
    initial_value_usd: Decimal
    current_value_usd: Decimal
    total_yield: Decimal
    yield_percentage: Decimal
    apy: Decimal
    risk_score: float
    sharpe_ratio: float
    max_drawdown: Decimal
    volatility: Decimal
    duration_days: int
    transactions: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "protocol": self.protocol,
            "chain": self.chain,
            "token": self.token,
            "initial_amount": str(self.initial_amount),
            "current_amount": str(self.current_amount),
            "initial_value_usd": str(self.initial_value_usd),
            "current_value_usd": str(self.current_value_usd),
            "total_yield": str(self.total_yield),
            "yield_percentage": str(self.yield_percentage),
            "apy": str(self.apy),
            "risk_score": self.risk_score,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": str(self.max_drawdown),
            "volatility": str(self.volatility),
            "duration_days": self.duration_days,
            "transactions": self.transactions,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class DeFiAnalytics:
    """
    Moteur d'analytique DeFi
    """

    def __init__(
        self,
        config: Dict[str, Any],
        defi_aggregator: Optional[DeFiAggregator] = None,
        aave: Optional[AaveIntegration] = None,
        compound: Optional[CompoundIntegration] = None,
        curve: Optional[CurveIntegration] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le moteur d'analytique DeFi

        Args:
            config: Configuration
            defi_aggregator: Agrégateur DeFi
            aave: Intégration Aave
            compound: Intégration Compound
            curve: Intégration Curve
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.defi_aggregator = defi_aggregator
        self.aave = aave
        self.compound = compound
        self.curve = curve
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._analytics_cache: Dict[str, Tuple[float, Any]] = {}
        self._report_cache: Dict[str, Tuple[float, DeFiReport]] = {}
        self._price_cache: Dict[str, Tuple[float, Decimal]] = {}
        self._historical_data: Dict[str, List[DeFiAnalyticsData]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Statistiques
        self._stats: Dict[str, Any] = defaultdict(dict)

        logger.info("DeFiAnalytics initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_protocol_analytics(
        self,
        protocol: str,
        token: str,
        chain: str,
        timeframe: AnalyticsTimeframe = AnalyticsTimeframe.DAY,
        force_refresh: bool = False,
    ) -> DeFiAnalyticsData:
        """
        Obtient l'analytique d'un protocole

        Args:
            protocol: Nom du protocole
            token: Token
            chain: Chaîne
            timeframe: Période
            force_refresh: Forcer le rafraîchissement

        Returns:
            Données d'analytique
        """
        cache_key = f"{protocol}:{token}:{chain}:{timeframe.value}"

        if not force_refresh and cache_key in self._analytics_cache:
            cached_time, data = self._analytics_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Collecte des données
            metrics = await self._collect_protocol_metrics(protocol, token, chain)

            # Calcul des métriques avancées
            metrics = await self._calculate_advanced_metrics(metrics, timeframe)

            data = DeFiAnalyticsData(
                timestamp=datetime.now(),
                protocol=protocol,
                chain=chain,
                token=token,
                metrics=metrics,
            )

            # Stockage historique
            self._historical_data[cache_key].append(data)

            # Mise en cache
            self._analytics_cache[cache_key] = (time.time(), data)

            # Métriques
            for metric, value in metrics.items():
                self.metrics.record_gauge(
                    f"defi_{metric.value}",
                    float(value),
                    {"protocol": protocol, "chain": chain, "token": token},
                )

            return data

        except Exception as e:
            logger.error(f"Erreur d'analytique pour {protocol}: {e}")
            raise AnalyticsError(f"Erreur d'analytique: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_position_analytics(
        self,
        position_id: str,
        user: str,
        protocol: str,
        chain: str,
        token: str,
        force_refresh: bool = False,
    ) -> DeFiPositionAnalytics:
        """
        Obtient l'analytique d'une position

        Args:
            position_id: ID de la position
            user: Adresse de l'utilisateur
            protocol: Protocole
            chain: Chaîne
            token: Token
            force_refresh: Forcer le rafraîchissement

        Returns:
            Analytique de la position
        """
        cache_key = f"pos:{position_id}:{user}"

        if not force_refresh and cache_key in self._analytics_cache:
            cached_time, data = self._analytics_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Récupération de la position
            position = None
            if self.defi_aggregator:
                portfolio = await self.defi_aggregator.get_portfolio(
                    protocol, user, force_refresh
                )
                if portfolio:
                    for pos in portfolio.positions:
                        if pos.position_id == position_id:
                            position = pos
                            break

            if not position:
                raise DeFiError(f"Position {position_id} non trouvée")

            # Calcul des métriques
            analytics = await self._calculate_position_metrics(position, user, protocol, chain, token)

            # Stockage
            self._analytics_cache[cache_key] = (time.time(), analytics)

            return analytics

        except Exception as e:
            logger.error(f"Erreur d'analytique de position: {e}")
            raise AnalyticsError(f"Erreur d'analytique de position: {e}")

    @async_retry(max_attempts=2, initial_delay=1.0)
    async def generate_report(
        self,
        title: str,
        timeframe: AnalyticsTimeframe,
        protocols: Optional[List[str]] = None,
        tokens: Optional[List[str]] = None,
        chains: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> DeFiReport:
        """
        Génère un rapport DeFi

        Args:
            title: Titre du rapport
            timeframe: Période
            protocols: Protocoles à analyser
            tokens: Tokens à analyser
            chains: Chaînes à analyser
            start_date: Date de début
            end_date: Date de fin

        Returns:
            Rapport DeFi
        """
        report_id = f"dfr_{uuid.uuid4().hex[:12]}"
        logger.info(f"Génération du rapport {report_id}: {title}")

        try:
            # Détermination des dates
            if start_date is None or end_date is None:
                start_date, end_date = self._get_timeframe_dates(timeframe)

            # Collecte des données
            metrics_data = {}
            insights = []
            recommendations = []

            # Analyse par protocole
            protocol_list = protocols or ["aave_v3", "compound_v3", "curve"]
            token_list = tokens or ["USDC", "USDT", "DAI", "ETH"]
            chain_list = chains or ["ethereum", "polygon", "arbitrum"]

            for protocol in protocol_list:
                for token in token_list:
                    for chain in chain_list:
                        try:
                            data = await self.get_protocol_analytics(
                                protocol, token, chain, timeframe, force_refresh=True
                            )
                            if data.metrics:
                                metrics_data[f"{protocol}:{token}:{chain}"] = data
                        except Exception as e:
                            logger.warning(f"Erreur pour {protocol}:{token}:{chain}: {e}")

            # Génération des insights
            insights = await self._generate_insights(metrics_data)

            # Génération des recommandations
            recommendations = await self._generate_recommendations(metrics_data, insights)

            # Résumé
            summary = await self._generate_summary(metrics_data)

            # Création du rapport
            report = DeFiReport(
                report_id=report_id,
                title=title,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                summary=summary,
                metrics={k: [v] for k, v in metrics_data.items()},
                insights=insights,
                recommendations=recommendations,
                generated_at=datetime.now(),
            )

            # Mise en cache
            self._report_cache[report_id] = (time.time(), report)

            # Métriques
            self.metrics.record_increment(
                "defi_report_generated",
                1,
                {"timeframe": timeframe.value},
            )

            return report

        except Exception as e:
            logger.error(f"Erreur de génération de rapport: {e}")
            raise AnalyticsError(f"Erreur de génération de rapport: {e}")

    async def get_market_overview(
        self,
        chain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Obtient une vue d'ensemble du marché DeFi

        Args:
            chain: Chaîne (optionnel)

        Returns:
            Vue d'ensemble du marché
        """
        overview = {
            "timestamp": datetime.now().isoformat(),
            "total_tvl": Decimal("0"),
            "top_protocols": [],
            "top_tokens": [],
            "average_apy": Decimal("0"),
            "market_sentiment": "neutral",
            "trends": {},
        }

        try:
            # Récupération des données de tous les protocoles
            protocols = ["aave_v3", "compound_v3", "curve"]
            tokens = ["USDC", "USDT", "DAI", "ETH"]

            total_tvl = Decimal("0")
            total_apy = Decimal("0")
            protocol_count = 0

            for protocol in protocols:
                for token in tokens:
                    try:
                        data = await self.get_protocol_analytics(
                            protocol, token, chain or "ethereum"
                        )
                        if data.metrics.get(AnalyticsMetric.TVL):
                            tvl = data.metrics[AnalyticsMetric.TVL]
                            total_tvl += tvl

                        if data.metrics.get(AnalyticsMetric.APY):
                            apy = data.metrics[AnalyticsMetric.APY]
                            total_apy += apy
                            protocol_count += 1

                    except Exception:
                        continue

            # Calcul des moyennes
            if protocol_count > 0:
                overview["average_apy"] = total_apy / protocol_count

            overview["total_tvl"] = total_tvl

            # Top protocoles (simulé)
            overview["top_protocols"] = [
                {"name": "Aave V3", "tvl": "2.5B", "apy": "3.2%"},
                {"name": "Compound V3", "tvl": "1.8B", "apy": "2.8%"},
                {"name": "Curve", "tvl": "1.2B", "apy": "4.1%"},
            ]

            # Top tokens
            overview["top_tokens"] = [
                {"symbol": "USDC", "tvl": "3.2B", "average_apy": "3.5%"},
                {"symbol": "USDT", "tvl": "2.1B", "average_apy": "3.2%"},
                {"symbol": "DAI", "tvl": "1.5B", "average_apy": "2.8%"},
                {"symbol": "ETH", "tvl": "1.0B", "average_apy": "2.5%"},
            ]

            # Sentiment du marché (simulé)
            overview["market_sentiment"] = "positive"

            return overview

        except Exception as e:
            logger.error(f"Erreur de vue d'ensemble: {e}")
            return overview

    # ============================================================
    # MÉTHODES DE COLLECTE
    # ============================================================

    async def _collect_protocol_metrics(
        self,
        protocol: str,
        token: str,
        chain: str,
    ) -> Dict[AnalyticsMetric, Decimal]:
        """Collecte les métriques d'un protocole"""
        metrics = {}

        try:
            if protocol.startswith("aave") and self.aave:
                # Aave metrics
                reserve = await self.aave.get_reserve_data(token, chain)
                metrics[AnalyticsMetric.APY] = reserve.supply_rate
                metrics[AnalyticsMetric.TVL] = reserve.total_liquidity
                metrics[AnalyticsMetric.VOLUME_24H] = reserve.total_liquidity * Decimal("0.01")
                metrics[AnalyticsMetric.ACTIVE_USERS] = Decimal("1000")

            elif protocol.startswith("compound") and self.compound:
                # Compound metrics
                reserve = await self.compound.get_reserve_data(token, chain)
                metrics[AnalyticsMetric.APY] = reserve.supply_rate
                metrics[AnalyticsMetric.TVL] = reserve.total_supply
                metrics[AnalyticsMetric.VOLUME_24H] = reserve.total_supply * Decimal("0.008")
                metrics[AnalyticsMetric.ACTIVE_USERS] = Decimal("800")

            elif protocol == "curve" and self.curve:
                # Curve metrics
                pool = await self.curve.get_pool_data("3pool", chain)
                metrics[AnalyticsMetric.APY] = pool.apy
                metrics[AnalyticsMetric.TVL] = pool.tvl
                metrics[AnalyticsMetric.VOLUME_24H] = pool.volume_24h
                metrics[AnalyticsMetric.ACTIVE_USERS] = Decimal("500")

            # Métriques communes
            metrics[AnalyticsMetric.APR] = metrics.get(AnalyticsMetric.APY, Decimal("0")) * Decimal("0.95")
            metrics[AnalyticsMetric.TVL_CHANGE] = Decimal("0.02")  # 2% de changement
            metrics[AnalyticsMetric.NEW_USERS] = Decimal("50")
            metrics[AnalyticsMetric.USER_RETENTION] = Decimal("0.85")

            # Métriques de risque (simulées)
            metrics[AnalyticsMetric.VOLATILITY] = Decimal("0.15")
            metrics[AnalyticsMetric.SHARPE_RATIO] = Decimal("1.2")
            metrics[AnalyticsMetric.MAX_DRAWDOWN] = Decimal("0.05")
            metrics[AnalyticsMetric.VAR_95] = Decimal("0.03")

            return metrics

        except Exception as e:
            logger.warning(f"Erreur de collecte pour {protocol}: {e}")
            return {}

    async def _calculate_advanced_metrics(
        self,
        metrics: Dict[AnalyticsMetric, Decimal],
        timeframe: AnalyticsTimeframe,
    ) -> Dict[AnalyticsMetric, Decimal]:
        """Calcule les métriques avancées"""
        advanced = metrics.copy()

        # Calcul du ROI
        if AnalyticsMetric.TOTAL_YIELD in metrics:
            advanced[AnalyticsMetric.ROI] = metrics[AnalyticsMetric.TOTAL_YIELD]

        # Calcul de l'Alpha (simulé)
        if AnalyticsMetric.APY in metrics:
            advanced[AnalyticsMetric.ALPHA] = metrics[AnalyticsMetric.APY] - Decimal("0.02")

        # Calcul du Beta (simulé)
        advanced[AnalyticsMetric.BETA] = Decimal("0.8")

        # Calcul du Sortino Ratio (simulé)
        if AnalyticsMetric.APY in metrics and AnalyticsMetric.VOLATILITY in metrics:
            advanced[AnalyticsMetric.SORTINO_RATIO] = (
                metrics[AnalyticsMetric.APY] / (metrics[AnalyticsMetric.VOLATILITY] * Decimal("0.7"))
            )

        # Calcul du CVaR (simulé)
        if AnalyticsMetric.VAR_95 in metrics:
            advanced[AnalyticsMetric.CVAR_95] = metrics[AnalyticsMetric.VAR_95] * Decimal("1.5")

        return advanced

    async def _calculate_position_metrics(
        self,
        position: Any,
        user: str,
        protocol: str,
        chain: str,
        token: str,
    ) -> DeFiPositionAnalytics:
        """Calcule les métriques d'une position"""
        # Simulé - dans la réalité, on calculerait à partir des données historiques
        initial_value = Decimal("1000")
        current_value = Decimal("1100")
        total_yield = current_value - initial_value
        yield_percentage = (total_yield / initial_value) * Decimal("100")

        return DeFiPositionAnalytics(
            position_id=position.position_id,
            protocol=protocol,
            chain=chain,
            token=token,
            initial_amount=Decimal("1000"),
            current_amount=Decimal("1100"),
            initial_value_usd=initial_value,
            current_value_usd=current_value,
            total_yield=total_yield,
            yield_percentage=yield_percentage,
            apy=Decimal("0.05"),
            risk_score=0.3,
            sharpe_ratio=1.5,
            max_drawdown=Decimal("0.02"),
            volatility=Decimal("0.12"),
            duration_days=30,
            transactions=5,
        )

    # ============================================================
    # MÉTHODES DE GÉNÉRATION D'INSIGHTS
    # ============================================================

    async def _generate_insights(
        self,
        metrics_data: Dict[str, DeFiAnalyticsData],
    ) -> List[str]:
        """Génère des insights à partir des données"""
        insights = []

        # Trouver le meilleur APY
        best_apy = None
        best_protocol = None

        for key, data in metrics_data.items():
            apy = data.metrics.get(AnalyticsMetric.APY)
            if apy and (best_apy is None or apy > best_apy):
                best_apy = apy
                best_protocol = key

        if best_protocol:
            insights.append(
                f"Meilleur rendement: {best_protocol} avec {best_apy:.2%} APY"
            )

        # Analyse de la TVL
        total_tvl = Decimal("0")
        for data in metrics_data.values():
            tvl = data.metrics.get(AnalyticsMetric.TVL, Decimal("0"))
            total_tvl += tvl

        if total_tvl > 0:
            insights.append(f"TVL totale: ${total_tvl:,.0f}")

        # Analyse des volumes
        total_volume = Decimal("0")
        for data in metrics_data.values():
            volume = data.metrics.get(AnalyticsMetric.VOLUME_24H, Decimal("0"))
            total_volume += volume

        if total_volume > 0:
            insights.append(f"Volume 24h total: ${total_volume:,.0f}")

        # Analyse des utilisateurs
        total_users = Decimal("0")
        for data in metrics_data.values():
            users = data.metrics.get(AnalyticsMetric.ACTIVE_USERS, Decimal("0"))
            total_users += users

        if total_users > 0:
            insights.append(f"Utilisateurs actifs: {int(total_users)}")

        return insights

    async def _generate_recommendations(
        self,
        metrics_data: Dict[str, DeFiAnalyticsData],
        insights: List[str],
    ) -> List[str]:
        """Génère des recommandations"""
        recommendations = []

        # Recommandation 1: Diversification
        if len(metrics_data) > 0:
            recommendations.append(
                "Diversifier les positions sur plusieurs protocoles pour réduire le risque"
            )

        # Recommandation 2: Optimisation des rendements
        best_apy = None
        best_protocol = None

        for key, data in metrics_data.items():
            apy = data.metrics.get(AnalyticsMetric.APY)
            if apy and (best_apy is None or apy > best_apy):
                best_apy = apy
                best_protocol = key

        if best_protocol:
            recommendations.append(
                f"Considérer {best_protocol} pour des rendements plus élevés ({best_apy:.2%} APY)"
            )

        # Recommandation 3: Gestion des risques
        recommendations.append(
            "Surveiller régulièrement le health factor des positions empruntées"
        )

        # Recommandation 4: Rééquilibrage
        recommendations.append(
            "Rééquilibrer le portefeuille mensuellement pour maintenir l'allocation cible"
        )

        return recommendations

    async def _generate_summary(
        self,
        metrics_data: Dict[str, DeFiAnalyticsData],
    ) -> Dict[str, Any]:
        """Génère un résumé des données"""
        if not metrics_data:
            return {"status": "no_data"}

        total_tvl = Decimal("0")
        avg_apy = Decimal("0")
        total_volume = Decimal("0")
        total_users = Decimal("0")
        count = 0

        for data in metrics_data.values():
            total_tvl += data.metrics.get(AnalyticsMetric.TVL, Decimal("0"))
            avg_apy += data.metrics.get(AnalyticsMetric.APY, Decimal("0"))
            total_volume += data.metrics.get(AnalyticsMetric.VOLUME_24H, Decimal("0"))
            total_users += data.metrics.get(AnalyticsMetric.ACTIVE_USERS, Decimal("0"))
            count += 1

        if count > 0:
            avg_apy /= count

        return {
            "total_tvl": str(total_tvl),
            "average_apy": str(avg_apy),
            "total_volume_24h": str(total_volume),
            "active_users": int(total_users),
            "protocols_analyzed": count,
            "timestamp": datetime.now().isoformat(),
        }

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_timeframe_dates(self, timeframe: AnalyticsTimeframe) -> Tuple[datetime, datetime]:
        """Obtient les dates pour une période"""
        end_date = datetime.now()

        if timeframe == AnalyticsTimeframe.HOUR:
            start_date = end_date - timedelta(hours=1)
        elif timeframe == AnalyticsTimeframe.DAY:
            start_date = end_date - timedelta(days=1)
        elif timeframe == AnalyticsTimeframe.WEEK:
            start_date = end_date - timedelta(weeks=1)
        elif timeframe == AnalyticsTimeframe.MONTH:
            start_date = end_date - timedelta(days=30)
        elif timeframe == AnalyticsTimeframe.QUARTER:
            start_date = end_date - timedelta(days=90)
        elif timeframe == AnalyticsTimeframe.YEAR:
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=7)

        return start_date, end_date

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques de l'analytique"""
        return {
            "cache_size": len(self._analytics_cache),
            "report_cache_size": len(self._report_cache),
            "historical_data_size": len(self._historical_data),
            "total_metrics_collected": sum(len(v) for v in self._historical_data.values()),
            "cache_ttl": self.cache_ttl,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources DeFiAnalytics...")

        self._analytics_cache.clear()
        self._report_cache.clear()
        self._price_cache.clear()
        self._historical_data.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_defi_analytics(
    config: Dict[str, Any],
    **kwargs,
) -> DeFiAnalytics:
    """
    Crée une instance de DeFiAnalytics

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiAnalytics
    """
    return DeFiAnalytics(
        config=config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de DeFiAnalytics"""
    # Configuration
    config = {}

    # Création de l'analytique
    analytics = create_defi_analytics(config=config)

    # Obtention de l'analytique d'un protocole
    data = await analytics.get_protocol_analytics(
        protocol="aave_v3",
        token="USDC",
        chain="ethereum",
    )

    print(f"Analytique Aave V3/USDC:")
    for metric, value in data.metrics.items():
        print(f"  {metric.value}: {value:.4f}")

    # Génération d'un rapport
    report = await analytics.generate_report(
        title="Rapport DeFi Hebdomadaire",
        timeframe=AnalyticsTimeframe.WEEK,
        protocols=["aave_v3", "compound_v3"],
        tokens=["USDC", "USDT"],
    )

    print(f"\nRapport généré: {report.report_id}")
    print(f"Insights: {report.insights}")
    print(f"Recommandations: {report.recommendations}")

    # Vue d'ensemble du marché
    overview = await analytics.get_market_overview("ethereum")
    print(f"\nVue d'ensemble du marché:")
    print(f"  TVL totale: ${overview['total_tvl']:,.0f}")
    print(f"  APY moyenne: {overview['average_apy']:.2%}")
    print(f"  Sentiment: {overview['market_sentiment']}")

    # Statistiques
    stats = analytics.get_statistics()
    print(f"\nStatistiques: {stats}")

    # Nettoyage
    await analytics.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

# blockchain/bridges/bridge_analytics.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module d'Analytique des Bridges

Ce module implémente un système complet d'analytique pour les opérations de bridge
cross-chain, incluant l'analyse des volumes, des frais, des performances, des
tendances, et des métriques avancées.

Fonctionnalités principales:
- Analyse des volumes de bridge
- Analyse des frais et des coûts
- Analyse des performances (temps, succès)
- Analyse des tendances et des patterns
- Analyse des utilisateurs et des adresses
- Analyse des tokens et des paires
- Analyse des protocoles
- Tableaux de bord et visualisations
- Rapports automatisés
- Prédictions et forecasting
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
from collections import defaultdict, deque
from functools import lru_cache, wraps
import statistics
import math

import aiohttp
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats

# Import des modules internes
try:
    from ..core.exceptions import AnalyticsError, BridgeError
    from ..core.logging import get_logger
    from ..core.metrics import MetricsCollector
    from ..core.retry import async_retry, RetryConfig
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_events import BridgeEventManager, BridgeEvent, EventType
    from .bridge_fees import BridgeFeeManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import AnalyticsError, BridgeError
    from ..core.metrics import MetricsCollector
    from ..core.retry import async_retry, RetryConfig
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_events import BridgeEventManager, BridgeEvent, EventType
    from .bridge_fees import BridgeFeeManager

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
    VOLUME = "volume"
    VOLUME_USD = "volume_usd"
    TRANSACTIONS = "transactions"
    FEES = "fees"
    FEES_USD = "fees_usd"
    SUCCESS_RATE = "success_rate"
    AVG_TIME = "avg_time"
    AVG_AMOUNT = "avg_amount"
    MEDIAN_AMOUNT = "median_amount"
    UNIQUE_USERS = "unique_users"
    ACTIVE_PROTOCOLS = "active_protocols"
    TOTAL_BRIDGED = "total_bridged"


@dataclass
class AnalyticsPoint:
    """Point de données analytique"""
    timestamp: datetime
    value: Union[int, float, Decimal, str]
    metric: AnalyticsMetric
    protocol: Optional[str] = None
    chain: Optional[str] = None
    token: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": str(self.value) if isinstance(self.value, Decimal) else self.value,
            "metric": self.metric.value,
            "protocol": self.protocol,
            "chain": self.chain,
            "token": self.token,
            "metadata": self.metadata,
        }


@dataclass
class AnalyticsReport:
    """Rapport d'analytique"""
    report_id: str
    title: str
    timeframe: AnalyticsTimeframe
    start_date: datetime
    end_date: datetime
    metrics: Dict[AnalyticsMetric, List[AnalyticsPoint]]
    summary: Dict[str, Any]
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
            "metrics": {
                k.value: [p.to_dict() for p in v]
                for k, v in self.metrics.items()
            },
            "summary": self.summary,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class ProtocolAnalytics:
    """Analytique par protocole"""
    protocol: str
    total_volume: Decimal
    total_volume_usd: Decimal
    total_fees: Decimal
    total_fees_usd: Decimal
    transaction_count: int
    success_rate: float
    avg_time: float
    unique_users: int
    avg_amount: Decimal
    median_amount: Decimal
    top_tokens: List[Tuple[str, Decimal]]
    daily_stats: List[Dict[str, Any]]
    trends: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol,
            "total_volume": str(self.total_volume),
            "total_volume_usd": str(self.total_volume_usd),
            "total_fees": str(self.total_fees),
            "total_fees_usd": str(self.total_fees_usd),
            "transaction_count": self.transaction_count,
            "success_rate": self.success_rate,
            "avg_time": self.avg_time,
            "unique_users": self.unique_users,
            "avg_amount": str(self.avg_amount),
            "median_amount": str(self.median_amount),
            "top_tokens": [(t, str(v)) for t, v in self.top_tokens],
            "trends": self.trends,
        }


@dataclass
class TokenAnalytics:
    """Analytique par token"""
    token: str
    chain: str
    total_volume: Decimal
    total_volume_usd: Decimal
    transaction_count: int
    unique_users: int
    avg_amount: Decimal
    median_amount: Decimal
    price_usd: Optional[Decimal]
    price_change_24h: Optional[float]
    protocols_used: List[str]
    daily_stats: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "token": self.token,
            "chain": self.chain,
            "total_volume": str(self.total_volume),
            "total_volume_usd": str(self.total_volume_usd),
            "transaction_count": self.transaction_count,
            "unique_users": self.unique_users,
            "avg_amount": str(self.avg_amount),
            "median_amount": str(self.median_amount),
            "price_usd": str(self.price_usd) if self.price_usd else None,
            "price_change_24h": self.price_change_24h,
            "protocols_used": self.protocols_used,
        }


@dataclass
class UserAnalytics:
    """Analytique par utilisateur"""
    address: str
    total_volume: Decimal
    total_volume_usd: Decimal
    total_fees: Decimal
    total_fees_usd: Decimal
    transaction_count: int
    success_rate: float
    avg_amount: Decimal
    protocols_used: List[str]
    tokens_used: List[str]
    chains_used: List[str]
    first_seen: datetime
    last_seen: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "total_volume": str(self.total_volume),
            "total_volume_usd": str(self.total_volume_usd),
            "total_fees": str(self.total_fees),
            "total_fees_usd": str(self.total_fees_usd),
            "transaction_count": self.transaction_count,
            "success_rate": self.success_rate,
            "avg_amount": str(self.avg_amount),
            "protocols_used": self.protocols_used,
            "tokens_used": self.tokens_used,
            "chains_used": self.chains_used,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeAnalytics:
    """
    Moteur d'analytique pour les bridges cross-chain
    """

    def __init__(
        self,
        config: Dict[str, Any],
        bridge_manager: BridgeManager,
        event_manager: Optional[BridgeEventManager] = None,
        fee_manager: Optional[BridgeFeeManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le moteur d'analytique

        Args:
            config: Configuration
            bridge_manager: Gestionnaire de bridges
            event_manager: Gestionnaire d'événements
            fee_manager: Gestionnaire de frais
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.bridge_manager = bridge_manager
        self.event_manager = event_manager
        self.fee_manager = fee_manager
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._analytics_cache: Dict[str, Tuple[float, Any]] = {}
        self._report_cache: Dict[str, Tuple[float, AnalyticsReport]] = {}
        self._price_cache: Dict[str, Tuple[float, Decimal]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Base de données locale (simulée)
        self._data_store: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Configuration des prix
        self._price_update_interval = 60  # secondes

        logger.info("BridgeAnalytics initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_protocol_analytics(
        self,
        protocol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ProtocolAnalytics:
        """
        Obtient l'analytique pour un protocole

        Args:
            protocol: Nom du protocole
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)

        Returns:
            Analytique du protocole
        """
        cache_key = f"protocol:{protocol}:{start_date}:{end_date}"

        if cache_key in self._analytics_cache:
            cached_time, data = self._analytics_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Collecte des données
            events = await self._get_events_for_analytics(protocol, start_date, end_date)

            if not events:
                return self._empty_protocol_analytics(protocol)

            # Calcul des métriques
            analytics = await self._calculate_protocol_analytics(protocol, events)

            # Mise en cache
            self._analytics_cache[cache_key] = (time.time(), analytics)

            # Métriques
            self.metrics.record_increment(
                "analytics_protocol_generated",
                1,
                {"protocol": protocol},
            )

            return analytics

        except Exception as e:
            logger.error(f"Erreur d'analytique pour {protocol}: {e}")
            raise AnalyticsError(f"Erreur d'analytique: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_token_analytics(
        self,
        token: str,
        chain: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> TokenAnalytics:
        """
        Obtient l'analytique pour un token

        Args:
            token: Symbole du token
            chain: Chaîne (optionnel)
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)

        Returns:
            Analytique du token
        """
        cache_key = f"token:{token}:{chain}:{start_date}:{end_date}"

        if cache_key in self._analytics_cache:
            cached_time, data = self._analytics_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Collecte des données
            events = await self._get_events_for_analytics(
                token=token,
                chain=chain,
                start_date=start_date,
                end_date=end_date,
            )

            if not events:
                return self._empty_token_analytics(token, chain)

            # Calcul des métriques
            analytics = await self._calculate_token_analytics(token, chain, events)

            # Mise en cache
            self._analytics_cache[cache_key] = (time.time(), analytics)

            return analytics

        except Exception as e:
            logger.error(f"Erreur d'analytique pour {token}: {e}")
            raise AnalyticsError(f"Erreur d'analytique: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_user_analytics(
        self,
        address: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> UserAnalytics:
        """
        Obtient l'analytique pour un utilisateur

        Args:
            address: Adresse de l'utilisateur
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)

        Returns:
            Analytique de l'utilisateur
        """
        cache_key = f"user:{address}:{start_date}:{end_date}"

        if cache_key in self._analytics_cache:
            cached_time, data = self._analytics_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Collecte des données
            events = await self._get_events_for_analytics(
                address=address,
                start_date=start_date,
                end_date=end_date,
            )

            if not events:
                return self._empty_user_analytics(address)

            # Calcul des métriques
            analytics = await self._calculate_user_analytics(address, events)

            # Mise en cache
            self._analytics_cache[cache_key] = (time.time(), analytics)

            return analytics

        except Exception as e:
            logger.error(f"Erreur d'analytique pour {address}: {e}")
            raise AnalyticsError(f"Erreur d'analytique: {e}")

    @async_retry(max_attempts=2, initial_delay=1.0)
    async def generate_report(
        self,
        title: str,
        timeframe: AnalyticsTimeframe,
        metrics: List[AnalyticsMetric],
        protocols: Optional[List[str]] = None,
        chains: Optional[List[str]] = None,
        tokens: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> AnalyticsReport:
        """
        Génère un rapport d'analytique

        Args:
            title: Titre du rapport
            timeframe: Période d'analyse
            metrics: Métriques à inclure
            protocols: Protocoles à analyser
            chains: Chaînes à analyser
            tokens: Tokens à analyser
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)

        Returns:
            Rapport d'analytique
        """
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"
        logger.info(f"Génération du rapport {report_id}: {title}")

        try:
            # Détermination des dates
            if start_date is None or end_date is None:
                start_date, end_date = self._get_timeframe_dates(timeframe)

            # Collecte des données
            events = await self._get_events_for_analytics(
                protocols=protocols,
                chains=chains,
                tokens=tokens,
                start_date=start_date,
                end_date=end_date,
            )

            # Calcul des métriques
            metric_data = {}
            summary = {}

            for metric in metrics:
                data = await self._calculate_metric(events, metric)
                metric_data[metric] = data

                # Résumé
                if data:
                    summary[metric.value] = self._summarize_metric(data)

            # Insights
            insights = await self._generate_insights(events, metric_data)

            # Recommandations
            recommendations = await self._generate_recommendations(
                events, metric_data, insights
            )

            # Création du rapport
            report = AnalyticsReport(
                report_id=report_id,
                title=title,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                metrics=metric_data,
                summary=summary,
                insights=insights,
                recommendations=recommendations,
                generated_at=datetime.now(),
            )

            # Mise en cache
            cache_key = f"report:{report_id}"
            self._report_cache[cache_key] = (time.time(), report)

            # Métriques
            self.metrics.record_increment(
                "analytics_report_generated",
                1,
                {"timeframe": timeframe.value},
            )

            return report

        except Exception as e:
            logger.error(f"Erreur de génération de rapport: {e}")
            raise AnalyticsError(f"Erreur de génération de rapport: {e}")

    async def get_trends(
        self,
        metric: AnalyticsMetric,
        protocols: Optional[List[str]] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Obtient les tendances pour une métrique

        Args:
            metric: Métrique à analyser
            protocols: Protocoles à analyser (optionnel)
            days: Nombre de jours

        Returns:
            Tendances
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        events = await self._get_events_for_analytics(
            protocols=protocols,
            start_date=start_date,
            end_date=end_date,
        )

        # Groupement par jour
        daily_data = defaultdict(list)

        for event in events:
            day = event.timestamp.date()
            value = await self._extract_metric_value(event, metric)
            if value is not None:
                daily_data[day].append(value)

        # Calcul des moyennes par jour
        daily_avg = {}
        for day, values in daily_data.items():
            if values:
                daily_avg[day] = sum(values) / len(values)

        # Calcul de la tendance
        dates = sorted(daily_avg.keys())
        values = [float(daily_avg[d]) for d in dates]

        if len(values) >= 2:
            # Régression linéaire
            x = list(range(len(values)))
            slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, values)

            trend = {
                "slope": slope,
                "intercept": intercept,
                "correlation": r_value,
                "direction": "up" if slope > 0 else "down",
                "strength": abs(r_value),
                "values": values,
                "dates": [d.isoformat() for d in dates],
            }
        else:
            trend = {
                "slope": 0,
                "direction": "stable",
                "strength": 0,
                "values": values,
                "dates": [d.isoformat() for d in dates],
            }

        return trend

    async def get_volume_distribution(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Obtient la distribution des volumes

        Args:
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)

        Returns:
            Distribution des volumes
        """
        events = await self._get_events_for_analytics(
            start_date=start_date,
            end_date=end_date,
        )

        # Distribution par protocole
        protocol_volumes = defaultdict(Decimal)
        chain_volumes = defaultdict(Decimal)
        token_volumes = defaultdict(Decimal)

        for event in events:
            if event.amount and event.event_type in [
                EventType.BRIDGE_COMPLETED,
                EventType.DEPOSIT_CONFIRMED,
                EventType.TOKEN_TRANSFERRED,
            ]:
                if event.protocol:
                    protocol_volumes[event.protocol] += event.amount
                if event.chain:
                    chain_volumes[event.chain] += event.amount
                if event.token:
                    token_volumes[event.token] += event.amount

        total_volume = sum(protocol_volumes.values())

        return {
            "by_protocol": {
                k: str(v) for k, v in protocol_volumes.items()
            },
            "by_chain": {
                k: str(v) for k, v in chain_volumes.items()
            },
            "by_token": {
                k: str(v) for k, v in token_volumes.items()
            },
            "total_volume": str(total_volume),
        }

    async def get_health_dashboard(self) -> Dict[str, Any]:
        """
        Obtient le tableau de bord de santé

        Returns:
            Tableau de bord de santé
        """
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": "healthy",
            "protocols": {},
            "alerts": [],
            "metrics": {},
        }

        try:
            # Récupération de tous les protocoles
            protocols = await self.bridge_manager.get_all_bridges()

            for protocol in protocols:
                if not protocol.enabled:
                    continue

                try:
                    # Analytique du protocole
                    analytics = await self.get_protocol_analytics(protocol.protocol)

                    # Évaluation de la santé
                    health_score = self._calculate_protocol_health_score(analytics)

                    dashboard["protocols"][protocol.protocol] = {
                        "status": "healthy" if health_score > 0.8 else "degraded",
                        "health_score": health_score,
                        "success_rate": analytics.success_rate,
                        "volume_24h": str(analytics.daily_stats[-1]["volume"]) if analytics.daily_stats else "0",
                        "pending_transactions": analytics.daily_stats[-1]["pending"] if analytics.daily_stats else 0,
                    }

                    # Alertes
                    if health_score < 0.7:
                        dashboard["alerts"].append({
                            "severity": "critical",
                            "protocol": protocol.protocol,
                            "message": f"Health score below threshold: {health_score:.2f}",
                        })
                    elif health_score < 0.85:
                        dashboard["alerts"].append({
                            "severity": "warning",
                            "protocol": protocol.protocol,
                            "message": f"Health score below optimal: {health_score:.2f}",
                        })

                except Exception as e:
                    logger.warning(f"Erreur de santé pour {protocol.protocol}: {e}")

            # Métriques globales
            dashboard["metrics"] = {
                "total_protocols": len(dashboard["protocols"]),
                "healthy_protocols": sum(1 for p in dashboard["protocols"].values() if p["status"] == "healthy"),
                "degraded_protocols": sum(1 for p in dashboard["protocols"].values() if p["status"] == "degraded"),
            }

            # Santé globale
            if dashboard["metrics"]["degraded_protocols"] > len(dashboard["protocols"]) * 0.3:
                dashboard["overall_health"] = "degraded"
            elif dashboard["metrics"]["degraded_protocols"] > len(dashboard["protocols"]) * 0.5:
                dashboard["overall_health"] = "unhealthy"

            return dashboard

        except Exception as e:
            logger.error(f"Erreur du tableau de bord de santé: {e}")
            return dashboard

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _calculate_protocol_analytics(
        self,
        protocol: str,
        events: List[BridgeEvent],
    ) -> ProtocolAnalytics:
        """Calcule l'analytique d'un protocole"""
        # Filtrage des événements pertinents
        relevant_events = [
            e for e in events
            if e.protocol == protocol
            and e.event_type in [
                EventType.BRIDGE_COMPLETED,
                EventType.DEPOSIT_CONFIRMED,
                EventType.TOKEN_TRANSFERRED,
            ]
        ]

        if not relevant_events:
            return self._empty_protocol_analytics(protocol)

        # Calculs de base
        total_volume = sum(e.amount for e in relevant_events if e.amount)
        transaction_count = len(relevant_events)

        # Succès et échecs
        success_events = [
            e for e in events
            if e.protocol == protocol and e.status == EventStatus.PROCESSED
        ]
        failed_events = [
            e for e in events
            if e.protocol == protocol and e.status == EventStatus.FAILED
        ]

        success_rate = len(success_events) / max(1, len(success_events) + len(failed_events))

        # Temps moyen
        avg_time = self._calculate_avg_time(events)

        # Utilisateurs uniques
        unique_users = len(set(
            e.from_address for e in relevant_events
            if e.from_address
        ))

        # Montants
        amounts = [e.amount for e in relevant_events if e.amount]
        avg_amount = sum(amounts) / len(amounts) if amounts else Decimal(0)
        median_amount = sorted(amounts)[len(amounts) // 2] if amounts else Decimal(0)

        # Tokens utilisés
        token_counts = defaultdict(Decimal)
        for event in relevant_events:
            if event.token:
                token_counts[event.token] += event.amount or Decimal(0)

        top_tokens = sorted(
            token_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Statistiques quotidiennes
        daily_stats = await self._calculate_daily_stats(relevant_events)

        # Tendances
        trends = await self._calculate_trends(relevant_events)

        # Conversion USD (simulée)
        total_volume_usd = total_volume * Decimal("1")  # À remplacer par un vrai prix
        total_fees = await self._calculate_total_fees(protocol, events)
        total_fees_usd = total_fees * Decimal("1")

        return ProtocolAnalytics(
            protocol=protocol,
            total_volume=total_volume,
            total_volume_usd=total_volume_usd,
            total_fees=total_fees,
            total_fees_usd=total_fees_usd,
            transaction_count=transaction_count,
            success_rate=success_rate,
            avg_time=avg_time,
            unique_users=unique_users,
            avg_amount=avg_amount,
            median_amount=median_amount,
            top_tokens=top_tokens,
            daily_stats=daily_stats,
            trends=trends,
        )

    async def _calculate_token_analytics(
        self,
        token: str,
        chain: Optional[str],
        events: List[BridgeEvent],
    ) -> TokenAnalytics:
        """Calcule l'analytique d'un token"""
        relevant_events = [
            e for e in events
            if e.token == token
            and (chain is None or e.chain == chain)
            and e.event_type in [
                EventType.BRIDGE_COMPLETED,
                EventType.DEPOSIT_CONFIRMED,
                EventType.TOKEN_TRANSFERRED,
            ]
        ]

        if not relevant_events:
            return self._empty_token_analytics(token, chain)

        total_volume = sum(e.amount for e in relevant_events if e.amount)
        transaction_count = len(relevant_events)

        # Utilisateurs uniques
        unique_users = len(set(
            e.from_address for e in relevant_events
            if e.from_address
        ))

        # Montants
        amounts = [e.amount for e in relevant_events if e.amount]
        avg_amount = sum(amounts) / len(amounts) if amounts else Decimal(0)
        median_amount = sorted(amounts)[len(amounts) // 2] if amounts else Decimal(0)

        # Protocoles utilisés
        protocols_used = list(set(e.protocol for e in relevant_events if e.protocol))

        # Prix (simulé)
        price_usd = await self._get_token_price(token)
        price_change_24h = await self._get_token_price_change(token)

        total_volume_usd = total_volume * (price_usd or Decimal("1"))

        # Statistiques quotidiennes
        daily_stats = await self._calculate_daily_stats(relevant_events)

        return TokenAnalytics(
            token=token,
            chain=chain or "unknown",
            total_volume=total_volume,
            total_volume_usd=total_volume_usd,
            transaction_count=transaction_count,
            unique_users=unique_users,
            avg_amount=avg_amount,
            median_amount=median_amount,
            price_usd=price_usd,
            price_change_24h=price_change_24h,
            protocols_used=protocols_used,
            daily_stats=daily_stats,
        )

    async def _calculate_user_analytics(
        self,
        address: str,
        events: List[BridgeEvent],
    ) -> UserAnalytics:
        """Calcule l'analytique d'un utilisateur"""
        relevant_events = [
            e for e in events
            if e.from_address == address or e.to_address == address
        ]

        if not relevant_events:
            return self._empty_user_analytics(address)

        total_volume = sum(e.amount for e in relevant_events if e.amount)
        transaction_count = len(relevant_events)

        # Succès
        success_events = [
            e for e in relevant_events
            if e.status == EventStatus.PROCESSED
        ]
        failed_events = [
            e for e in relevant_events
            if e.status == EventStatus.FAILED
        ]

        success_rate = len(success_events) / max(1, len(success_events) + len(failed_events))

        # Montants
        amounts = [e.amount for e in relevant_events if e.amount]
        avg_amount = sum(amounts) / len(amounts) if amounts else Decimal(0)

        # Protocoles, tokens, chaînes utilisés
        protocols_used = list(set(e.protocol for e in relevant_events if e.protocol))
        tokens_used = list(set(e.token for e in relevant_events if e.token))
        chains_used = list(set(e.chain for e in relevant_events if e.chain))

        # Dates
        timestamps = [e.timestamp for e in relevant_events]
        first_seen = min(timestamps) if timestamps else datetime.now()
        last_seen = max(timestamps) if timestamps else datetime.now()

        # Frais
        total_fees = await self._calculate_user_fees(address, relevant_events)
        total_fees_usd = total_fees * Decimal("1")

        total_volume_usd = total_volume * Decimal("1")

        return UserAnalytics(
            address=address,
            total_volume=total_volume,
            total_volume_usd=total_volume_usd,
            total_fees=total_fees,
            total_fees_usd=total_fees_usd,
            transaction_count=transaction_count,
            success_rate=success_rate,
            avg_amount=avg_amount,
            protocols_used=protocols_used,
            tokens_used=tokens_used,
            chains_used=chains_used,
            first_seen=first_seen,
            last_seen=last_seen,
        )

    # ============================================================
    # MÉTHODES D'AGRÉGATION
    # ============================================================

    async def _get_events_for_analytics(
        self,
        protocol: Optional[str] = None,
        protocols: Optional[List[str]] = None,
        chain: Optional[str] = None,
        chains: Optional[List[str]] = None,
        token: Optional[str] = None,
        tokens: Optional[List[str]] = None,
        address: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[BridgeEvent]:
        """Récupère les événements pour l'analytique"""
        if not self.event_manager:
            return []

        try:
            # Construction du filtre
            filter_params = EventFilter()

            if protocol:
                filter_params.protocols = [protocol]
            elif protocols:
                filter_params.protocols = protocols

            if chain:
                filter_params.chains = [chain]
            elif chains:
                filter_params.chains = chains

            if token:
                filter_params.tokens = [token]
            elif tokens:
                filter_params.tokens = tokens

            if address:
                filter_params.addresses = [address]

            if start_date:
                filter_params.from_date = start_date

            if end_date:
                filter_params.to_date = end_date

            filter_params.statuses = [
                EventStatus.PROCESSED,
                EventStatus.FAILED,
            ]

            events = await self.event_manager.get_events(filter_params, limit=10000)

            return events

        except Exception as e:
            logger.error(f"Erreur de récupération des événements: {e}")
            return []

    async def _calculate_metric(
        self,
        events: List[BridgeEvent],
        metric: AnalyticsMetric,
    ) -> List[AnalyticsPoint]:
        """Calcule une métrique spécifique"""
        points = []

        if metric == AnalyticsMetric.VOLUME:
            for event in events:
                if event.amount:
                    points.append(AnalyticsPoint(
                        timestamp=event.timestamp,
                        value=event.amount,
                        metric=metric,
                        protocol=event.protocol,
                        chain=event.chain,
                        token=event.token,
                    ))

        elif metric == AnalyticsMetric.TRANSACTIONS:
            # Compter par période
            daily_counts = defaultdict(int)
            for event in events:
                day = event.timestamp.date()
                daily_counts[day] += 1

            for day, count in daily_counts.items():
                points.append(AnalyticsPoint(
                    timestamp=datetime.combine(day, datetime.min.time()),
                    value=count,
                    metric=metric,
                ))

        elif metric == AnalyticsMetric.SUCCESS_RATE:
            # Calcul par période
            daily_stats = defaultdict(lambda: {"success": 0, "total": 0})
            for event in events:
                day = event.timestamp.date()
                daily_stats[day]["total"] += 1
                if event.status == EventStatus.PROCESSED:
                    daily_stats[day]["success"] += 1

            for day, stats in daily_stats.items():
                rate = stats["success"] / max(1, stats["total"])
                points.append(AnalyticsPoint(
                    timestamp=datetime.combine(day, datetime.min.time()),
                    value=rate,
                    metric=metric,
                ))

        elif metric == AnalyticsMetric.AVG_TIME:
            # Temps moyen par jour
            daily_times = defaultdict(list)
            for event in events:
                if event.processed_at and event.timestamp:
                    duration = (event.processed_at - event.timestamp).total_seconds()
                    if duration > 0:
                        day = event.timestamp.date()
                        daily_times[day].append(duration)

            for day, times in daily_times.items():
                avg_time = sum(times) / len(times) if times else 0
                points.append(AnalyticsPoint(
                    timestamp=datetime.combine(day, datetime.min.time()),
                    value=avg_time,
                    metric=metric,
                ))

        # Autres métriques...

        return points

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _empty_protocol_analytics(self, protocol: str) -> ProtocolAnalytics:
        """Retourne une analytique vide pour un protocole"""
        return ProtocolAnalytics(
            protocol=protocol,
            total_volume=Decimal(0),
            total_volume_usd=Decimal(0),
            total_fees=Decimal(0),
            total_fees_usd=Decimal(0),
            transaction_count=0,
            success_rate=0.0,
            avg_time=0.0,
            unique_users=0,
            avg_amount=Decimal(0),
            median_amount=Decimal(0),
            top_tokens=[],
            daily_stats=[],
            trends={},
        )

    def _empty_token_analytics(self, token: str, chain: Optional[str]) -> TokenAnalytics:
        """Retourne une analytique vide pour un token"""
        return TokenAnalytics(
            token=token,
            chain=chain or "unknown",
            total_volume=Decimal(0),
            total_volume_usd=Decimal(0),
            transaction_count=0,
            unique_users=0,
            avg_amount=Decimal(0),
            median_amount=Decimal(0),
            price_usd=None,
            price_change_24h=None,
            protocols_used=[],
            daily_stats=[],
        )

    def _empty_user_analytics(self, address: str) -> UserAnalytics:
        """Retourne une analytique vide pour un utilisateur"""
        return UserAnalytics(
            address=address,
            total_volume=Decimal(0),
            total_volume_usd=Decimal(0),
            total_fees=Decimal(0),
            total_fees_usd=Decimal(0),
            transaction_count=0,
            success_rate=0.0,
            avg_amount=Decimal(0),
            protocols_used=[],
            tokens_used=[],
            chains_used=[],
            first_seen=datetime.now(),
            last_seen=datetime.now(),
        )

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

    def _calculate_avg_time(self, events: List[BridgeEvent]) -> float:
        """Calcule le temps moyen de traitement"""
        times = []
        for event in events:
            if event.processed_at and event.timestamp:
                duration = (event.processed_at - event.timestamp).total_seconds()
                if duration > 0:
                    times.append(duration)

        return sum(times) / len(times) if times else 0.0

    async def _calculate_daily_stats(
        self,
        events: List[BridgeEvent],
    ) -> List[Dict[str, Any]]:
        """Calcule les statistiques quotidiennes"""
        daily_data = defaultdict(lambda: {
            "volume": Decimal(0),
            "transactions": 0,
            "success": 0,
            "failed": 0,
            "pending": 0,
        })

        for event in events:
            day = event.timestamp.date()
            daily_data[day]["transactions"] += 1

            if event.amount:
                daily_data[day]["volume"] += event.amount

            if event.status == EventStatus.PROCESSED:
                daily_data[day]["success"] += 1
            elif event.status == EventStatus.FAILED:
                daily_data[day]["failed"] += 1
            else:
                daily_data[day]["pending"] += 1

        return [
            {
                "date": day.isoformat(),
                "volume": str(data["volume"]),
                "transactions": data["transactions"],
                "success_rate": data["success"] / max(1, data["transactions"]),
                "pending": data["pending"],
            }
            for day, data in sorted(daily_data.items())
        ]

    async def _calculate_trends(
        self,
        events: List[BridgeEvent],
    ) -> Dict[str, float]:
        """Calcule les tendances"""
        if not events:
            return {}

        # Tendance des volumes
        daily_volumes = defaultdict(Decimal)
        for event in events:
            if event.amount:
                day = event.timestamp.date()
                daily_volumes[day] += event.amount

        volumes = [float(v) for v in daily_volumes.values()]
        if len(volumes) >= 2:
            x = list(range(len(volumes)))
            slope, _, _, _, _ = scipy_stats.linregress(x, volumes)
            volume_trend = slope
        else:
            volume_trend = 0

        # Tendance des transactions
        daily_counts = defaultdict(int)
        for event in events:
            day = event.timestamp.date()
            daily_counts[day] += 1

        counts = list(daily_counts.values())
        if len(counts) >= 2:
            x = list(range(len(counts)))
            slope, _, _, _, _ = scipy_stats.linregress(x, counts)
            transaction_trend = slope
        else:
            transaction_trend = 0

        return {
            "volume_trend": volume_trend,
            "transaction_trend": transaction_trend,
            "volume_growth": volume_trend / max(1, volumes[0]) if volumes else 0,
            "transaction_growth": transaction_trend / max(1, counts[0]) if counts else 0,
        }

    async def _calculate_total_fees(
        self,
        protocol: str,
        events: List[BridgeEvent],
    ) -> Decimal:
        """Calcule les frais totaux pour un protocole"""
        if not self.fee_manager:
            return Decimal(0)

        total_fees = Decimal(0)
        for event in events:
            if event.amount:
                # Estimation des frais
                quote = await self.fee_manager.get_fee_quote(
                    protocol=event.protocol,
                    chain_from=event.chain,
                    chain_to=event.chain,  # Simplifié
                    token_from=event.token or "ETH",
                    token_to=event.token or "ETH",
                    amount=event.amount,
                )
                total_fees += quote.total_fee

        return total_fees

    async def _calculate_user_fees(
        self,
        address: str,
        events: List[BridgeEvent],
    ) -> Decimal:
        """Calcule les frais pour un utilisateur"""
        # Simulé - dans la réalité, on calculerait à partir des transactions
        return Decimal(len(events)) * Decimal("0.001")

    async def _get_token_price(self, token: str) -> Optional[Decimal]:
        """Obtient le prix d'un token"""
        # Simulé - dans la réalité, on utiliserait un oracle de prix
        prices = {
            "ETH": Decimal("3000"),
            "USDC": Decimal("1"),
            "USDT": Decimal("1"),
            "DAI": Decimal("1"),
            "WBTC": Decimal("60000"),
            "MATIC": Decimal("0.7"),
            "SOL": Decimal("100"),
            "BNB": Decimal("600"),
            "AVAX": Decimal("40"),
        }
        return prices.get(token)

    async def _get_token_price_change(self, token: str) -> Optional[float]:
        """Obtient la variation de prix d'un token"""
        # Simulé
        return 0.05  # 5% de changement

    def _calculate_protocol_health_score(self, analytics: ProtocolAnalytics) -> float:
        """Calcule le score de santé d'un protocole"""
        score = 0.0

        # Taux de succès (poids: 30%)
        score += analytics.success_rate * 0.3

        # Volume (poids: 25%)
        if analytics.total_volume > Decimal("1000000"):
            score += 0.25
        elif analytics.total_volume > Decimal("100000"):
            score += 0.15
        elif analytics.total_volume > Decimal("10000"):
            score += 0.05

        # Transactions (poids: 20%)
        if analytics.transaction_count > 1000:
            score += 0.2
        elif analytics.transaction_count > 100:
            score += 0.1
        elif analytics.transaction_count > 10:
            score += 0.05

        # Temps moyen (poids: 15%)
        if analytics.avg_time < 60:
            score += 0.15
        elif analytics.avg_time < 120:
            score += 0.1
        elif analytics.avg_time < 300:
            score += 0.05

        # Utilisateurs uniques (poids: 10%)
        if analytics.unique_users > 1000:
            score += 0.1
        elif analytics.unique_users > 100:
            score += 0.05
        elif analytics.unique_users > 10:
            score += 0.02

        return min(1.0, score)

    def _summarize_metric(self, data: List[AnalyticsPoint]) -> Dict[str, Any]:
        """Résume une métrique"""
        if not data:
            return {"count": 0}

        values = [v for v in data if v.value is not None]

        if not values:
            return {"count": 0}

        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v.value))
            except (TypeError, ValueError):
                pass

        if not numeric_values:
            return {"count": len(values)}

        return {
            "count": len(numeric_values),
            "min": min(numeric_values),
            "max": max(numeric_values),
            "avg": sum(numeric_values) / len(numeric_values),
            "median": statistics.median(numeric_values),
            "std_dev": statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0,
            "total": sum(numeric_values),
        }

    async def _extract_metric_value(
        self,
        event: BridgeEvent,
        metric: AnalyticsMetric,
    ) -> Optional[Union[int, float, Decimal]]:
        """Extrait la valeur d'une métrique d'un événement"""
        if metric == AnalyticsMetric.VOLUME:
            return event.amount
        elif metric == AnalyticsMetric.TRANSACTIONS:
            return 1
        elif metric == AnalyticsMetric.SUCCESS_RATE:
            return 1 if event.status == EventStatus.PROCESSED else 0
        elif metric == AnalyticsMetric.AVG_TIME:
            if event.processed_at and event.timestamp:
                return (event.processed_at - event.timestamp).total_seconds()
        elif metric == AnalyticsMetric.FEES:
            if event.amount:
                return event.amount * Decimal("0.001")  # Simulé

        return None

    async def _generate_insights(
        self,
        events: List[BridgeEvent],
        metric_data: Dict[AnalyticsMetric, List[AnalyticsPoint]],
    ) -> List[str]:
        """Génère des insights à partir des données"""
        insights = []

        # Insight 1: Volume le plus élevé
        if metric_data.get(AnalyticsMetric.VOLUME):
            volumes = [p for p in metric_data[AnalyticsMetric.VOLUME] if p.value]
            if volumes:
                max_volume = max(volumes, key=lambda x: float(x.value))
                insights.append(
                    f"Plus haut volume journalier: {max_volume.value} "
                    f"le {max_volume.timestamp.strftime('%Y-%m-%d')}"
                )

        # Insight 2: Taux de succès
        if metric_data.get(AnalyticsMetric.SUCCESS_RATE):
            rates = [p for p in metric_data[AnalyticsMetric.SUCCESS_RATE] if p.value]
            if rates:
                avg_rate = sum(float(r.value) for r in rates) / len(rates)
                insights.append(f"Taux de succès moyen: {avg_rate:.2%}")

        # Insight 3: Temps moyen
        if metric_data.get(AnalyticsMetric.AVG_TIME):
            times = [p for p in metric_data[AnalyticsMetric.AVG_TIME] if p.value]
            if times:
                avg_time = sum(float(t.value) for t in times) / len(times)
                insights.append(f"Temps de traitement moyen: {avg_time:.1f}s")

        # Insight 4: Tendances
        if len(events) > 100:
            insights.append("Volume de transactions élevé (>100)")

        return insights

    async def _generate_recommendations(
        self,
        events: List[BridgeEvent],
        metric_data: Dict[AnalyticsMetric, List[AnalyticsPoint]],
        insights: List[str],
    ) -> List[str]:
        """Génère des recommandations"""
        recommendations = []

        # Recommandation 1: Optimisation des frais
        if len(events) > 50:
            recommendations.append("Envisager d'optimiser les frais pour les gros volumes")

        # Recommandation 2: Amélioration du taux de succès
        if metric_data.get(AnalyticsMetric.SUCCESS_RATE):
            rates = [p for p in metric_data[AnalyticsMetric.SUCCESS_RATE] if p.value]
            if rates:
                avg_rate = sum(float(r.value) for r in rates) / len(rates)
                if avg_rate < 0.95:
                    recommendations.append(
                        f"Améliorer le taux de succès ({avg_rate:.2%}) en optimisant "
                        "les paramètres de transaction"
                    )

        # Recommandation 3: Réduction du temps de traitement
        if metric_data.get(AnalyticsMetric.AVG_TIME):
            times = [p for p in metric_data[AnalyticsMetric.AVG_TIME] if p.value]
            if times:
                avg_time = sum(float(t.value) for t in times) / len(times)
                if avg_time > 180:
                    recommendations.append(
                        f"Réduire le temps de traitement ({avg_time:.1f}s) "
                        "en utilisant des frais de priorité plus élevés"
                    )

        # Recommandation 4: Diversification
        if len(set(e.protocol for e in events)) < 2:
            recommendations.append(
                "Diversifier les protocoles utilisés pour réduire les risques"
            )

        return recommendations

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques de l'analytique"""
        return {
            "cache_size": len(self._analytics_cache),
            "report_cache_size": len(self._report_cache),
            "price_cache_size": len(self._price_cache),
            "data_store_size": sum(len(v) for v in self._data_store.values()),
            "cache_ttl": self.cache_ttl,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeAnalytics...")

        self._analytics_cache.clear()
        self._report_cache.clear()
        self._price_cache.clear()
        self._data_store.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_analytics(
    config: Dict[str, Any],
    bridge_manager: BridgeManager,
    **kwargs,
) -> BridgeAnalytics:
    """
    Crée une instance de BridgeAnalytics

    Args:
        config: Configuration
        bridge_manager: Gestionnaire de bridges
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeAnalytics
    """
    return BridgeAnalytics(
        config=config,
        bridge_manager=bridge_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeAnalytics"""
    # Configuration
    config = {
        "price_update_interval": 60,
        "cache_ttl": 300,
    }

    # Bridge manager (simplifié)
    class SimpleBridgeManager:
        async def get_all_bridges(self):
            return []

    bridge_manager = SimpleBridgeManager()

    # Event manager (simplifié)
    class SimpleEventManager:
        async def get_events(self, filter_params, limit):
            return []

    event_manager = SimpleEventManager()

    # Création de l'analytique
    analytics = create_bridge_analytics(
        config=config,
        bridge_manager=bridge_manager,
        event_manager=event_manager,
    )

    # Génération d'un rapport
    report = await analytics.generate_report(
        title="Rapport Hebdomadaire des Bridges",
        timeframe=AnalyticsTimeframe.WEEK,
        metrics=[
            AnalyticsMetric.VOLUME,
            AnalyticsMetric.TRANSACTIONS,
            AnalyticsMetric.SUCCESS_RATE,
            AnalyticsMetric.AVG_TIME,
        ],
    )

    print(f"Rapport généré: {report.report_id}")
    print(f"Insights: {report.insights}")
    print(f"Recommandations: {report.recommendations}")

    # Tableau de bord de santé
    dashboard = await analytics.get_health_dashboard()
    print(f"Santé globale: {dashboard['overall_health']}")

    # Statistiques
    stats = analytics.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await analytics.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

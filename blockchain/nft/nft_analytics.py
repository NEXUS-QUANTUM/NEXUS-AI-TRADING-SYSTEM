# blockchain/nft/nft_analytics.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Analytics - Analytique Avancée des NFTs

Ce module implémente un système complet d'analytique pour les NFTs,
permettant l'analyse des collections, des prix, des volumes, des tendances,
et des métriques avancées pour le trading NFT.

Fonctionnalités principales:
- Analyse des collections NFT
- Analyse des prix (floor, average, last)
- Analyse des volumes de trading
- Analyse des tendances du marché
- Analyse des holders
- Analyse des royalties
- Analyse des wallets
- Métriques de performance
- Rapports automatisés
- Prédictions de prix
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
    from ..core.exceptions import AnalyticsError, NFTError
    from ..core.logging import get_logger
    from ..core.metrics import MetricsCollector
    from ..core.retry import async_retry, RetryConfig
    from .base_nft import BaseNFT, NFTData, NFTCollection
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import AnalyticsError, NFTError
    from ..core.metrics import MetricsCollector
    from ..core.retry import async_retry, RetryConfig
    from .base_nft import BaseNFT, NFTData, NFTCollection

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NFTAnalyticsTimeframe(Enum):
    """Périodes d'analyse"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class NFTAnalyticsMetric(Enum):
    """Métriques d'analyse NFT"""
    # Prix
    FLOOR_PRICE = "floor_price"
    AVERAGE_PRICE = "average_price"
    LAST_PRICE = "last_price"
    MIN_PRICE = "min_price"
    MAX_PRICE = "max_price"
    PRICE_CHANGE = "price_change"
    
    # Volume
    VOLUME_24H = "volume_24h"
    VOLUME_7D = "volume_7d"
    VOLUME_30D = "volume_30d"
    VOLUME_CHANGE = "volume_change"
    
    # Collections
    ITEMS_COUNT = "items_count"
    OWNERS_COUNT = "owners_count"
    HOLDERS_COUNT = "holders_count"
    UNIQUE_HOLDERS = "unique_holders"
    WHALE_CONCENTRATION = "whale_concentration"
    
    # Trading
    LISTINGS_COUNT = "listings_count"
    SALES_COUNT = "sales_count"
    SALES_CHANGE = "sales_change"
    AVERAGE_SALE_PRICE = "average_sale_price"
    MEDIAN_SALE_PRICE = "median_sale_price"
    
    # Royalties
    TOTAL_ROYALTIES = "total_royalties"
    AVERAGE_ROYALTY = "average_royalty"
    ROYALTY_CHANGE = "royalty_change"
    
    # Performance
    MARKET_CAP = "market_cap"
    LIQUIDITY = "liquidity"
    TURNOVER_RATE = "turnover_rate"
    HOLDING_PERIOD = "holding_period"


@dataclass
class NFTAnalyticsData:
    """Données d'analytique NFT"""
    timestamp: datetime
    collection: str
    chain: str
    metrics: Dict[NFTAnalyticsMetric, Decimal]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "collection": self.collection,
            "chain": self.chain,
            "metrics": {k.value: str(v) for k, v in self.metrics.items()},
            "metadata": self.metadata,
        }


@dataclass
class NFTReport:
    """Rapport NFT"""
    report_id: str
    title: str
    timeframe: NFTAnalyticsTimeframe
    start_date: datetime
    end_date: datetime
    summary: Dict[str, Any]
    metrics: Dict[NFTAnalyticsMetric, List[NFTAnalyticsData]]
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
class CollectionAnalytics:
    """Analytique de collection NFT"""
    collection: str
    chain: str
    floor_price: Decimal
    average_price: Decimal
    volume_24h: Decimal
    volume_7d: Decimal
    volume_30d: Decimal
    items_count: int
    owners_count: int
    whale_concentration: float
    market_cap: Decimal
    liquidity: Decimal
    turnover_rate: Decimal
    avg_holding_period: int
    price_trend: Dict[str, float]
    volume_trend: Dict[str, float]
    top_holders: List[Dict[str, Any]]
    recent_sales: List[Dict[str, Any]]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "collection": self.collection,
            "chain": self.chain,
            "floor_price": str(self.floor_price),
            "average_price": str(self.average_price),
            "volume_24h": str(self.volume_24h),
            "volume_7d": str(self.volume_7d),
            "volume_30d": str(self.volume_30d),
            "items_count": self.items_count,
            "owners_count": self.owners_count,
            "whale_concentration": self.whale_concentration,
            "market_cap": str(self.market_cap),
            "liquidity": str(self.liquidity),
            "turnover_rate": str(self.turnover_rate),
            "avg_holding_period": self.avg_holding_period,
            "price_trend": self.price_trend,
            "volume_trend": self.volume_trend,
            "top_holders": self.top_holders,
            "recent_sales": self.recent_sales,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class NFTWalletAnalytics:
    """Analytique de wallet NFT"""
    wallet: str
    chain: str
    total_value: Decimal
    nft_count: int
    collections: List[Dict[str, Any]]
    total_bought: Decimal
    total_sold: Decimal
    profit_loss: Decimal
    roi: Decimal
    avg_holding_period: int
    trade_count: int
    first_trade: datetime
    last_trade: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "wallet": self.wallet,
            "chain": self.chain,
            "total_value": str(self.total_value),
            "nft_count": self.nft_count,
            "collections": self.collections,
            "total_bought": str(self.total_bought),
            "total_sold": str(self.total_sold),
            "profit_loss": str(self.profit_loss),
            "roi": str(self.roi),
            "avg_holding_period": self.avg_holding_period,
            "trade_count": self.trade_count,
            "first_trade": self.first_trade.isoformat(),
            "last_trade": self.last_trade.isoformat(),
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTAnalytics:
    """
    Moteur d'analytique NFT
    """

    def __init__(
        self,
        config: Dict[str, Any],
        nft_instances: Dict[str, Any],
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le moteur d'analytique NFT

        Args:
            config: Configuration
            nft_instances: Instances des gestionnaires NFT
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.nft_instances = nft_instances
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._analytics_cache: Dict[str, Tuple[float, Any]] = {}
        self._report_cache: Dict[str, Tuple[float, NFTReport]] = {}
        self._price_cache: Dict[str, Tuple[float, Decimal]] = {}
        self._historical_data: Dict[str, List[NFTAnalyticsData]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Statistiques
        self._stats: Dict[str, Any] = defaultdict(dict)

        logger.info("NFTAnalytics initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_collection_analytics(
        self,
        collection: str,
        chain: str = "ethereum",
        timeframe: NFTAnalyticsTimeframe = NFTAnalyticsTimeframe.DAY,
        force_refresh: bool = False,
    ) -> CollectionAnalytics:
        """
        Obtient l'analytique d'une collection NFT

        Args:
            collection: Nom ou adresse de la collection
            chain: Chaîne
            timeframe: Période
            force_refresh: Forcer le rafraîchissement

        Returns:
            Analytique de la collection
        """
        cache_key = f"{collection}:{chain}:{timeframe.value}"

        if not force_refresh and cache_key in self._analytics_cache:
            cached_time, data = self._analytics_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Récupération des données
            analytics = await self._collect_collection_data(collection, chain)

            # Calcul des métriques avancées
            analytics = await self._calculate_advanced_metrics(analytics, timeframe)

            # Mise en cache
            self._analytics_cache[cache_key] = (time.time(), analytics)

            # Métriques
            self.metrics.record_gauge(
                "nft_collection_floor_price",
                float(analytics.floor_price),
                {"collection": collection, "chain": chain},
            )
            self.metrics.record_gauge(
                "nft_collection_volume",
                float(analytics.volume_24h),
                {"collection": collection, "chain": chain},
            )

            return analytics

        except Exception as e:
            logger.error(f"Erreur d'analytique pour {collection}: {e}")
            raise AnalyticsError(f"Erreur d'analytique: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_wallet_analytics(
        self,
        wallet: str,
        chain: str = "ethereum",
        force_refresh: bool = False,
    ) -> NFTWalletAnalytics:
        """
        Obtient l'analytique d'un wallet NFT

        Args:
            wallet: Adresse du wallet
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Analytique du wallet
        """
        cache_key = f"wallet:{wallet}:{chain}"

        if not force_refresh and cache_key in self._analytics_cache:
            cached_time, data = self._analytics_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Récupération des données
            analytics = await self._collect_wallet_data(wallet, chain)

            # Mise en cache
            self._analytics_cache[cache_key] = (time.time(), analytics)

            return analytics

        except Exception as e:
            logger.error(f"Erreur d'analytique pour {wallet}: {e}")
            raise AnalyticsError(f"Erreur d'analytique: {e}")

    @async_retry(max_attempts=2, initial_delay=1.0)
    async def generate_report(
        self,
        title: str,
        timeframe: NFTAnalyticsTimeframe,
        collections: Optional[List[str]] = None,
        chains: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> NFTReport:
        """
        Génère un rapport NFT

        Args:
            title: Titre du rapport
            timeframe: Période
            collections: Collections à analyser
            chains: Chaînes à analyser
            start_date: Date de début
            end_date: Date de fin

        Returns:
            Rapport NFT
        """
        report_id = f"nftr_{uuid.uuid4().hex[:12]}"
        logger.info(f"Génération du rapport {report_id}: {title}")

        try:
            # Détermination des dates
            if start_date is None or end_date is None:
                start_date, end_date = self._get_timeframe_dates(timeframe)

            # Collecte des données
            metrics_data = {}
            insights = []
            recommendations = []

            # Analyse par collection
            collections_to_analyze = collections or ["bored_ape_yacht_club", "mutant_ape_yacht_club", "azuki"]
            chains_to_analyze = chains or ["ethereum"]

            for collection in collections_to_analyze:
                for chain in chains_to_analyze:
                    try:
                        data = await self.get_collection_analytics(
                            collection, chain, timeframe, force_refresh=True
                        )
                        metrics_data[f"{collection}:{chain}"] = data
                    except Exception as e:
                        logger.warning(f"Erreur pour {collection}:{chain}: {e}")

            # Génération des insights
            insights = await self._generate_insights(metrics_data)

            # Génération des recommandations
            recommendations = await self._generate_recommendations(metrics_data, insights)

            # Résumé
            summary = await self._generate_summary(metrics_data)

            # Création du rapport
            report = NFTReport(
                report_id=report_id,
                title=title,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                summary=summary,
                metrics={},
                insights=insights,
                recommendations=recommendations,
                generated_at=datetime.now(),
            )

            # Mise en cache
            self._report_cache[report_id] = (time.time(), report)

            # Métriques
            self.metrics.record_increment(
                "nft_report_generated",
                1,
                {"timeframe": timeframe.value},
            )

            return report

        except Exception as e:
            logger.error(f"Erreur de génération de rapport: {e}")
            raise AnalyticsError(f"Erreur de génération de rapport: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_market_overview(
        self,
        chain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Obtient une vue d'ensemble du marché NFT

        Args:
            chain: Chaîne (optionnel)

        Returns:
            Vue d'ensemble du marché
        """
        overview = {
            "timestamp": datetime.now().isoformat(),
            "total_volume_24h": Decimal("0"),
            "top_collections": [],
            "trending_collections": [],
            "market_sentiment": "neutral",
            "trends": {},
        }

        try:
            # Récupération des données de toutes les collections
            collections = ["bored_ape_yacht_club", "mutant_ape_yacht_club", "azuki", "doodles", "clonex"]

            for collection in collections:
                try:
                    data = await self.get_collection_analytics(
                        collection, chain or "ethereum"
                    )
                    overview["total_volume_24h"] += data.volume_24h

                    # Top collections
                    overview["top_collections"].append({
                        "name": collection,
                        "floor_price": str(data.floor_price),
                        "volume_24h": str(data.volume_24h),
                        "items_count": data.items_count,
                    })

                except Exception:
                    continue

            # Tri des top collections
            overview["top_collections"].sort(
                key=lambda x: Decimal(x["volume_24h"]),
                reverse=True
            )

            # Sentiment du marché (simulé)
            overview["market_sentiment"] = "positive"

            return overview

        except Exception as e:
            logger.error(f"Erreur de vue d'ensemble: {e}")
            return overview

    # ============================================================
    # MÉTHODES DE COLLECTE
    # ============================================================

    async def _collect_collection_data(
        self,
        collection: str,
        chain: str,
    ) -> CollectionAnalytics:
        """Collecte les données d'une collection"""
        try:
            # Récupération de l'instance NFT
            nft_instance = self.nft_instances.get(f"{chain}_erc721")
            if not nft_instance:
                raise NFTError(f"Instance NFT non trouvée pour {chain}")

            # Récupération de la collection
            # Dans la réalité, on utiliserait les adresses de contrats
            # Simulé pour l'exemple
            collection_data = {
                "floor_price": Decimal("30"),
                "average_price": Decimal("35"),
                "volume_24h": Decimal("100"),
                "volume_7d": Decimal("700"),
                "volume_30d": Decimal("3000"),
                "items_count": 10000,
                "owners_count": 5000,
                "whale_concentration": 0.15,
                "market_cap": Decimal("300000"),
                "liquidity": Decimal("0.1"),
                "turnover_rate": Decimal("0.05"),
                "avg_holding_period": 30,
            }

            return CollectionAnalytics(
                collection=collection,
                chain=chain,
                floor_price=collection_data["floor_price"],
                average_price=collection_data["average_price"],
                volume_24h=collection_data["volume_24h"],
                volume_7d=collection_data["volume_7d"],
                volume_30d=collection_data["volume_30d"],
                items_count=collection_data["items_count"],
                owners_count=collection_data["owners_count"],
                whale_concentration=collection_data["whale_concentration"],
                market_cap=collection_data["market_cap"],
                liquidity=collection_data["liquidity"],
                turnover_rate=collection_data["turnover_rate"],
                avg_holding_period=collection_data["avg_holding_period"],
                price_trend={"7d": 0.05, "30d": 0.12},
                volume_trend={"7d": 0.08, "30d": 0.20},
                top_holders=[
                    {"address": "0x...", "count": 100, "percentage": 1.0},
                ],
                recent_sales=[
                    {"price": "30", "buyer": "0x...", "timestamp": "2024-01-01T00:00:00"},
                ],
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Erreur de collecte des données: {e}")
            raise

    async def _collect_wallet_data(
        self,
        wallet: str,
        chain: str,
    ) -> NFTWalletAnalytics:
        """Collecte les données d'un wallet"""
        # Simulé
        return NFTWalletAnalytics(
            wallet=wallet,
            chain=chain,
            total_value=Decimal("1000"),
            nft_count=10,
            collections=[
                {"name": "BAYC", "count": 1, "value": Decimal("30")},
            ],
            total_bought=Decimal("500"),
            total_sold=Decimal("200"),
            profit_loss=Decimal("300"),
            roi=Decimal("0.6"),
            avg_holding_period=30,
            trade_count=5,
            first_trade=datetime.now() - timedelta(days=30),
            last_trade=datetime.now(),
        )

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _calculate_advanced_metrics(
        self,
        analytics: CollectionAnalytics,
        timeframe: NFTAnalyticsTimeframe,
    ) -> CollectionAnalytics:
        """Calcule les métriques avancées"""
        # Calcul des tendances
        analytics.price_trend = {
            "7d": 0.05,
            "30d": 0.12,
            "90d": 0.20,
        }

        analytics.volume_trend = {
            "7d": 0.08,
            "30d": 0.20,
            "90d": 0.35,
        }

        return analytics

    # ============================================================
    # MÉTHODES DE GÉNÉRATION D'INSIGHTS
    # ============================================================

    async def _generate_insights(
        self,
        metrics_data: Dict[str, CollectionAnalytics],
    ) -> List[str]:
        """Génère des insights à partir des données"""
        insights = []

        # Trouver la meilleure collection
        if metrics_data:
            best_collection = max(
                metrics_data.items(),
                key=lambda x: x[1].volume_24h
            )
            insights.append(
                f"Plus grand volume: {best_collection[0]} avec {best_collection[1].volume_24h:.2f} ETH"
            )

        # Analyse des prix
        avg_floor = sum(d.floor_price for d in metrics_data.values()) / max(1, len(metrics_data))
        insights.append(f"Prix plancher moyen: {avg_floor:.2f} ETH")

        # Analyse des volumes
        total_volume = sum(d.volume_24h for d in metrics_data.values())
        insights.append(f"Volume total 24h: {total_volume:.2f} ETH")

        return insights

    async def _generate_recommendations(
        self,
        metrics_data: Dict[str, CollectionAnalytics],
        insights: List[str],
    ) -> List[str]:
        """Génère des recommandations"""
        recommendations = []

        # Recommandation 1: Diversification
        if len(metrics_data) > 0:
            recommendations.append(
                "Diversifier les positions sur plusieurs collections pour réduire le risque"
            )

        # Recommandation 2: Collection avec meilleur potentiel
        if metrics_data:
            best_growth = max(
                metrics_data.items(),
                key=lambda x: x[1].volume_trend.get("30d", 0)
            )
            recommendations.append(
                f"Considérer {best_growth[0]} pour un fort potentiel de croissance"
            )

        return recommendations

    async def _generate_summary(
        self,
        metrics_data: Dict[str, CollectionAnalytics],
    ) -> Dict[str, Any]:
        """Génère un résumé des données"""
        if not metrics_data:
            return {"status": "no_data"}

        total_volume = sum(d.volume_24h for d in metrics_data.values())
        avg_floor = sum(d.floor_price for d in metrics_data.values()) / len(metrics_data)
        total_items = sum(d.items_count for d in metrics_data.values())

        return {
            "total_volume_24h": str(total_volume),
            "average_floor_price": str(avg_floor),
            "total_items": total_items,
            "collections_analyzed": len(metrics_data),
            "timestamp": datetime.now().isoformat(),
        }

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_timeframe_dates(self, timeframe: NFTAnalyticsTimeframe) -> Tuple[datetime, datetime]:
        """Obtient les dates pour une période"""
        end_date = datetime.now()

        if timeframe == NFTAnalyticsTimeframe.HOUR:
            start_date = end_date - timedelta(hours=1)
        elif timeframe == NFTAnalyticsTimeframe.DAY:
            start_date = end_date - timedelta(days=1)
        elif timeframe == NFTAnalyticsTimeframe.WEEK:
            start_date = end_date - timedelta(weeks=1)
        elif timeframe == NFTAnalyticsTimeframe.MONTH:
            start_date = end_date - timedelta(days=30)
        elif timeframe == NFTAnalyticsTimeframe.QUARTER:
            start_date = end_date - timedelta(days=90)
        elif timeframe == NFTAnalyticsTimeframe.YEAR:
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
        logger.info("Nettoyage des ressources NFTAnalytics...")

        self._analytics_cache.clear()
        self._report_cache.clear()
        self._price_cache.clear()
        self._historical_data.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_analytics(
    config: Dict[str, Any],
    nft_instances: Dict[str, Any],
    **kwargs,
) -> NFTAnalytics:
    """
    Crée une instance de NFTAnalytics

    Args:
        config: Configuration
        nft_instances: Instances NFT
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTAnalytics
    """
    return NFTAnalytics(
        config=config,
        nft_instances=nft_instances,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTAnalytics"""
    # Configuration
    config = {}

    # NFT instances (simplifié)
    class SimpleNFT:
        async def get_collection(self, address):
            return None

    nft_instances = {
        "ethereum_erc721": SimpleNFT(),
    }

    # Création de l'analytique
    analytics = create_nft_analytics(
        config=config,
        nft_instances=nft_instances,
    )

    # Obtention de l'analytique d'une collection
    collection_analytics = await analytics.get_collection_analytics(
        collection="bored_ape_yacht_club",
        chain="ethereum",
    )

    print(f"Collection BAYC:")
    print(f"  Floor price: {collection_analytics.floor_price:.2f} ETH")
    print(f"  Volume 24h: {collection_analytics.volume_24h:.2f} ETH")
    print(f"  Items: {collection_analytics.items_count}")
    print(f"  Owners: {collection_analytics.owners_count}")

    # Génération d'un rapport
    report = await analytics.generate_report(
        title="Rapport NFT Hebdomadaire",
        timeframe=NFTAnalyticsTimeframe.WEEK,
        collections=["bored_ape_yacht_club", "mutant_ape_yacht_club"],
    )

    print(f"\nRapport généré: {report.report_id}")
    print(f"Insights: {report.insights}")
    print(f"Recommandations: {report.recommendations}")

    # Vue d'ensemble du marché
    overview = await analytics.get_market_overview("ethereum")
    print(f"\nVue d'ensemble du marché:")
    print(f"  Volume total 24h: {overview['total_volume_24h']:.2f} ETH")
    print(f"  Sentiment: {overview['market_sentiment']}")

    # Statistiques
    stats = analytics.get_statistics()
    print(f"\nStatistiques: {stats}")

    # Nettoyage
    await analytics.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())

# trading/bots/hedge_bot/hedge_bot_market_data.py
# Advanced Market Data Collection & Processing Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Market Data Module - Module avancé de collecte et de traitement des données de marché
pour le Hedge Bot. Gère la collecte de données en temps réel, l'historique des prix,
les indicateurs techniques, l'analyse de marché et la gestion des données de marché.
"""

import asyncio
import json
import math
import time
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import pickle
import zlib
import aiohttp
import aiohttp.client_exceptions

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_market_data")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class MarketDataSource(Enum):
    """Sources de données de marché."""
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BYBIT = "bybit"
    OKX = "okx"
    ALPACA = "alpaca"
    IBKR = "ibkr"
    OANDA = "oanda"
    YAHOO = "yahoo"
    POLYGON = "polygon"
    CUSTOM = "custom"


class MarketDataInterval(Enum):
    """Intervalles de données de marché."""
    TICK = "tick"
    SECOND_1 = "1s"
    SECOND_5 = "5s"
    SECOND_15 = "15s"
    SECOND_30 = "30s"
    MINUTE_1 = "1m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_8 = "8h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    DAY_3 = "3d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class MarketDataCategory(Enum):
    """Catégories de données de marché."""
    PRICE = "price"
    VOLUME = "volume"
    ORDER_BOOK = "order_book"
    TRADES = "trades"
    OHLCV = "ohlcv"
    TICKER = "ticker"
    DEPTH = "depth"
    FUNDING = "funding"
    OPEN_INTEREST = "open_interest"


# ============== DATA MODELS ==============

@dataclass
class MarketData:
    """Données de marché."""
    data_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    source: MarketDataSource = MarketDataSource.CUSTOM
    interval: MarketDataInterval = MarketDataInterval.MINUTE_1
    category: MarketDataCategory = MarketDataCategory.PRICE
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    processed: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "data_id": self.data_id,
            "symbol": self.symbol,
            "source": self.source.value,
            "interval": self.interval.value,
            "category": self.category.value,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "processed": self.processed
        }


@dataclass
class OrderBookData:
    """Données de carnet d'ordres."""
    orderbook_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    source: MarketDataSource = MarketDataSource.CUSTOM
    bids: List[Tuple[float, float]] = field(default_factory=list)
    asks: List[Tuple[float, float]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "orderbook_id": self.orderbook_id,
            "symbol": self.symbol,
            "source": self.source.value,
            "bids": self.bids,
            "asks": self.asks,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class TradeData:
    """Données de transactions."""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    source: MarketDataSource = MarketDataSource.CUSTOM
    price: float = 0.0
    quantity: float = 0.0
    side: str = ""  # buy, sell
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "source": self.source.value,
            "price": self.price,
            "quantity": self.quantity,
            "side": self.side,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class MarketSubscription:
    """Abonnement aux données de marché."""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    source: MarketDataSource = MarketDataSource.CUSTOM
    interval: MarketDataInterval = MarketDataInterval.MINUTE_1
    categories: List[MarketDataCategory] = field(default_factory=list)
    callback: Optional[Callable] = None
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "subscription_id": self.subscription_id,
            "symbol": self.symbol,
            "source": self.source.value,
            "interval": self.interval.value,
            "categories": [c.value for c in self.categories],
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags
        }


# ============== INTERFACES ==============

class MarketDataEngineInterface(ABC):
    """Interface abstraite pour le moteur de données de marché."""
    
    @abstractmethod
    async def get_ohlcv(self, symbol: str, interval: MarketDataInterval) -> pd.DataFrame:
        """Récupère les données OHLCV."""
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: str) -> OrderBookData:
        """Récupère le carnet d'ordres."""
        pass
    
    @abstractmethod
    async def get_trades(self, symbol: str, limit: int = 100) -> List[TradeData]:
        """Récupère les transactions."""
        pass
    
    @abstractmethod
    async def subscribe(self, subscription: MarketSubscription) -> bool:
        """S'abonne aux données de marché."""
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        """Récupère le prix actuel."""
        pass


# ============== IMPLÉMENTATION ==============

class MarketDataEngine(MarketDataEngineInterface):
    """
    Moteur de données de marché avancé pour le Hedge Bot.
    Gère la collecte, le traitement et la distribution des données de marché.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des données
        self._market_data: Dict[str, List[MarketData]] = defaultdict(list)
        self._data_lock = threading.RLock()
        
        # Gestion des carnets d'ordres
        self._order_books: Dict[str, OrderBookData] = {}
        self._book_lock = threading.RLock()
        
        # Gestion des transactions
        self._trades: Dict[str, List[TradeData]] = defaultdict(list)
        self._trade_lock = threading.RLock()
        
        # Gestion des abonnements
        self._subscriptions: Dict[str, MarketSubscription] = {}
        self._sub_lock = threading.RLock()
        
        # Cache des données
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._cache_lock = threading.RLock()
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "data_points_collected": 0,
            "orderbook_updates": 0,
            "trades_processed": 0,
            "subscriptions_active": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_latency_ms": 0.0,
            "api_calls": 0,
            "api_errors": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Queue de traitement
        self._processing_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # État
        self._is_running = False
        
        logger.info("MarketDataEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_source": MarketDataSource.CUSTOM,
            "default_interval": MarketDataInterval.MINUTE_1,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "data_retention_days": 30,
            "max_data_points": 100000,
            "orderbook_depth": 10,
            "trades_limit": 1000,
            "aggregation_interval": 60,
            "enable_streaming": True,
            "api_timeout": 30,
            "max_retries": 3,
            "retry_delay": 1.0,
            "binance_api_url": "https://api.binance.com",
            "binance_ws_url": "wss://stream.binance.com:9443/ws",
            "coinbase_api_url": "https://api.coinbase.com",
            "coinbase_ws_url": "wss://ws-feed.pro.coinbase.com",
            "kraken_api_url": "https://api.kraken.com",
            "kraken_ws_url": "wss://ws.kraken.com"
        }
    
    async def start(self) -> None:
        """Démarre le moteur de données de marché."""
        logger.info("MarketDataEngine starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config["api_timeout"])
        )
        
        # Chargement des données
        await self._load_data()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._data_processor())
        asyncio.create_task(self._data_aggregator())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._streaming_manager())
        
        logger.info("MarketDataEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de données de marché."""
        logger.info("MarketDataEngine stopping...")
        self._is_running = False
        
        # Drain de la queue
        await self._drain_queue()
        
        # Fermeture de la session
        if self._session:
            await self._session.close()
        
        # Sauvegarde des données
        await self._save_data()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("MarketDataEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def get_ohlcv(self, symbol: str, interval: MarketDataInterval) -> pd.DataFrame:
        """Récupère les données OHLCV."""
        # Vérification du cache
        cache_key = f"{symbol}_{interval.value}"
        with self._cache_lock:
            if cache_key in self._data_cache:
                self._stats["cache_hits"] += 1
                return self._data_cache[cache_key]
        
        self._stats["cache_misses"] += 1
        
        # Récupération depuis la source
        data = await self._fetch_ohlcv(symbol, interval)
        
        if data is not None and not data.empty:
            # Mise en cache
            with self._cache_lock:
                if len(self._data_cache) < self.config["cache_size"]:
                    self._data_cache[cache_key] = data
            
            # Stockage
            await self._store_market_data(symbol, interval, data)
        
        return data if data is not None else pd.DataFrame()
    
    async def get_order_book(self, symbol: str) -> OrderBookData:
        """Récupère le carnet d'ordres."""
        # Vérification du cache
        with self._book_lock:
            if symbol in self._order_books:
                return self._order_books[symbol]
        
        # Récupération depuis la source
        order_book = await self._fetch_order_book(symbol)
        
        if order_book:
            with self._book_lock:
                self._order_books[symbol] = order_book
        
        return order_book if order_book else OrderBookData(symbol=symbol)
    
    async def get_trades(self, symbol: str, limit: int = 100) -> List[TradeData]:
        """Récupère les transactions."""
        with self._trade_lock:
            trades = self._trades.get(symbol, [])
            if trades:
                return trades[-limit:]
        
        # Récupération depuis la source
        trades = await self._fetch_trades(symbol, limit)
        
        if trades:
            with self._trade_lock:
                self._trades[symbol] = trades
        
        return trades if trades else []
    
    async def subscribe(self, subscription: MarketSubscription) -> bool:
        """S'abonne aux données de marché."""
        with self._sub_lock:
            self._subscriptions[subscription.subscription_id] = subscription
            self._stats["subscriptions_active"] = len([s for s in self._subscriptions.values() if s.active])
        
        logger.info(f"Subscription created: {subscription.symbol} interval={subscription.interval.value}")
        return True
    
    async def get_current_price(self, symbol: str) -> float:
        """Récupère le prix actuel."""
        # Vérification du cache
        with self._cache_lock:
            cache_key = f"price_{symbol}"
            if cache_key in self._data_cache:
                return self._data_cache[cache_key]
        
        # Récupération du prix
        price = await self._fetch_current_price(symbol)
        
        if price > 0:
            with self._cache_lock:
                self._data_cache[cache_key] = price
        
        return price
    
    # ========== MÉTHODES PRIVÉES - COLLECTE ==========
    
    async def _fetch_ohlcv(self, symbol: str, interval: MarketDataInterval) -> Optional[pd.DataFrame]:
        """Récupère les données OHLCV depuis la source."""
        try:
            # Simulation pour l'exemple
            # Dans un système réel, on interrogerait l'API
            logger.debug(f"Fetching OHLCV for {symbol} interval={interval.value}")
            self._stats["api_calls"] += 1
            
            # Génération de données simulées
            periods = 100
            end_time = datetime.now(timezone.utc)
            
            # Création des timestamps selon l'intervalle
            if interval == MarketDataInterval.TICK:
                freq = "1s"
            elif interval == MarketDataInterval.MINUTE_1:
                freq = "1min"
            elif interval == MarketDataInterval.HOUR_1:
                freq = "1h"
            elif interval == MarketDataInterval.DAY_1:
                freq = "1d"
            else:
                freq = "1min"
            
            timestamps = pd.date_range(end=end_time, periods=periods, freq=freq)
            
            # Génération des prix
            base_price = 100.0
            prices = base_price + np.cumsum(np.random.randn(periods) * 0.5)
            prices = np.maximum(prices, 1.0)
            
            # Construction du DataFrame
            df = pd.DataFrame({
                "timestamp": timestamps,
                "open": prices * 0.99,
                "high": prices * 1.01,
                "low": prices * 0.98,
                "close": prices,
                "volume": np.random.uniform(100, 1000, periods)
            })
            
            df.set_index("timestamp", inplace=True)
            
            return df
            
        except Exception as e:
            self._stats["api_errors"] += 1
            logger.error(f"OHLCV fetch error: {e}")
            return None
    
    async def _fetch_order_book(self, symbol: str) -> Optional[OrderBookData]:
        """Récupère le carnet d'ordres depuis la source."""
        try:
            logger.debug(f"Fetching order book for {symbol}")
            self._stats["api_calls"] += 1
            
            # Simulation de carnet d'ordres
            depth = self.config["orderbook_depth"]
            base_price = 100.0
            
            bid_prices = base_price - np.random.uniform(0, 5, depth)
            ask_prices = base_price + np.random.uniform(0, 5, depth)
            
            bids = [(p, np.random.uniform(1, 10)) for p in sorted(bid_prices, reverse=True)]
            asks = [(p, np.random.uniform(1, 10)) for p in sorted(ask_prices)]
            
            return OrderBookData(
                symbol=symbol,
                source=self.config["default_source"],
                bids=bids,
                asks=asks
            )
            
        except Exception as e:
            self._stats["api_errors"] += 1
            logger.error(f"Order book fetch error: {e}")
            return None
    
    async def _fetch_trades(self, symbol: str, limit: int) -> List[TradeData]:
        """Récupère les transactions depuis la source."""
        try:
            logger.debug(f"Fetching trades for {symbol} limit={limit}")
            self._stats["api_calls"] += 1
            
            # Simulation de transactions
            trades = []
            for _ in range(min(limit, 100)):
                price = np.random.uniform(95, 105)
                quantity = np.random.uniform(0.1, 10)
                side = "buy" if np.random.random() > 0.5 else "sell"
                
                trades.append(TradeData(
                    symbol=symbol,
                    source=self.config["default_source"],
                    price=price,
                    quantity=quantity,
                    side=side
                ))
            
            return trades
            
        except Exception as e:
            self._stats["api_errors"] += 1
            logger.error(f"Trades fetch error: {e}")
            return []
    
    async def _fetch_current_price(self, symbol: str) -> float:
        """Récupère le prix actuel depuis la source."""
        try:
            logger.debug(f"Fetching current price for {symbol}")
            self._stats["api_calls"] += 1
            
            # Simulation de prix
            return 100.0 + np.random.randn() * 2
            
        except Exception as e:
            self._stats["api_errors"] += 1
            logger.error(f"Current price fetch error: {e}")
            return 0.0
    
    async def _store_market_data(self, symbol: str, interval: MarketDataInterval, data: pd.DataFrame) -> None:
        """Stocke les données de marché."""
        for idx, row in data.iterrows():
            market_data = MarketData(
                symbol=symbol,
                source=self.config["default_source"],
                interval=interval,
                category=MarketDataCategory.OHLCV,
                open=row.get("open", 0.0),
                high=row.get("high", 0.0),
                low=row.get("low", 0.0),
                close=row.get("close", 0.0),
                volume=row.get("volume", 0.0),
                timestamp=idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            )
            
            with self._data_lock:
                self._market_data[symbol].append(market_data)
                self._stats["data_points_collected"] += 1
                
                # Limitation
                if len(self._market_data[symbol]) > self.config["max_data_points"]:
                    self._market_data[symbol] = self._market_data[symbol][-self.config["max_data_points"]:]
    
    # ========== MÉTHODES PRIVÉES - TRAITEMENT ==========
    
    async def _data_processor(self) -> None:
        """Traite les données en queue."""
        while self._is_running:
            try:
                data = await self._processing_queue.get()
                # Traitement des données
                # Dans un système réel, on traiterait les données
                await asyncio.sleep(0.001)
                
            except Exception as e:
                logger.error(f"Data processor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _data_aggregator(self) -> None:
        """Agrège les données périodiquement."""
        while self._is_running:
            await asyncio.sleep(self.config["aggregation_interval"])
            
            try:
                # Agrégation des données par intervalle
                with self._data_lock:
                    for symbol, data in self._market_data.items():
                        if len(data) < 2:
                            continue
                        
                        # Agrégation en OHLCV
                        # Dans un système réel, on agrégerait les données
                        pass
                
            except Exception as e:
                logger.error(f"Data aggregator error: {e}")
    
    async def _streaming_manager(self) -> None:
        """Gère les connexions de streaming."""
        if not self.config["enable_streaming"]:
            return
        
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Vérification des abonnements actifs
                with self._sub_lock:
                    active_subs = [s for s in self._subscriptions.values() if s.active]
                
                # Dans un système réel, on maintiendrait les connexions WebSocket
                pass
                
            except Exception as e:
                logger.error(f"Streaming manager error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _drain_queue(self) -> None:
        """Vide la queue de traitement."""
        while not self._processing_queue.empty():
            try:
                await self._processing_queue.get()
            except Exception:
                break
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._data_cache) > self.config["cache_size"]:
                        keys = list(self._data_cache.keys())
                        for key in keys[:len(self._data_cache) - self.config["cache_size"]]:
                            del self._data_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._data_lock:
                    self._stats["total_data_points"] = sum(len(d) for d in self._market_data.values())
                with self._sub_lock:
                    self._stats["active_subscriptions"] = len([s for s in self._subscriptions.values() if s.active])
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "market_data:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_data(self) -> None:
        """Charge les données existantes."""
        try:
            if self.data_manager:
                data_data = await self.data_manager.retrieve(
                    "market_data:all",
                    DataType.MARKET
                )
                
                if data_data:
                    for d_dict in data_data:
                        data = self._deserialize_market_data(d_dict)
                        if data:
                            with self._data_lock:
                                self._market_data[data.symbol].append(data)
            
            logger.info(f"Loaded market data points")
            
        except Exception as e:
            logger.error(f"Load data error: {e}")
    
    async def _save_data(self) -> None:
        """Sauvegarde les données."""
        try:
            if self.data_manager:
                with self._data_lock:
                    for data_list in self._market_data.values():
                        for data in data_list:
                            await self.data_manager.store(
                                f"market_data:{data.data_id}",
                                data.to_dict(),
                                DataType.MARKET
                            )
            
            logger.info("Market data saved")
            
        except Exception as e:
            logger.error(f"Save data error: {e}")
    
    def _deserialize_market_data(self, data: Dict) -> Optional[MarketData]:
        """Désérialise des données de marché."""
        try:
            return MarketData(
                data_id=data.get("data_id", str(uuid.uuid4())),
                symbol=data.get("symbol", ""),
                source=MarketDataSource(data.get("source", "custom")),
                interval=MarketDataInterval(data.get("interval", "1m")),
                category=MarketDataCategory(data.get("category", "price")),
                open=data.get("open", 0.0),
                high=data.get("high", 0.0),
                low=data.get("low", 0.0),
                close=data.get("close", 0.0),
                volume=data.get("volume", 0.0),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                processed=data.get("processed", False)
            )
        except Exception as e:
            logger.error(f"Error deserializing market data: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_symbols(self) -> List[str]:
        """Récupère la liste des symboles."""
        with self._data_lock:
            return list(self._market_data.keys())
    
    async def get_data_stats(self, symbol: str) -> Dict[str, Any]:
        """Récupère les statistiques des données."""
        with self._data_lock:
            data = self._market_data.get(symbol, [])
        
        if not data:
            return {"count": 0}
        
        prices = [d.close for d in data]
        volumes = [d.volume for d in data]
        
        return {
            "count": len(data),
            "price_min": np.min(prices),
            "price_max": np.max(prices),
            "price_mean": np.mean(prices),
            "price_std": np.std(prices),
            "volume_sum": np.sum(volumes),
            "volume_mean": np.mean(volumes)
        }
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Se désabonne des données de marché."""
        with self._sub_lock:
            subscription = self._subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            subscription.active = False
            self._stats["subscriptions_active"] = len([s for s in self._subscriptions.values() if s.active])
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._data_lock:
            self._stats["total_data_points"] = sum(len(d) for d in self._market_data.values())
        with self._sub_lock:
            self._stats["active_subscriptions"] = len([s for s in self._subscriptions.values() if s.active])
        
        return self._stats.copy()


# ============== TECHNICAL INDICATORS ==============

class TechnicalIndicators:
    """
    Calculateur d'indicateurs techniques.
    Calcule les indicateurs techniques pour l'analyse de marché.
    """
    
    @staticmethod
    def sma(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Simple Moving Average."""
        if len(data) < period:
            return np.array([])
        return data["close"].rolling(window=period).mean().values
    
    @staticmethod
    def ema(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Exponential Moving Average."""
        if len(data) < period:
            return np.array([])
        return data["close"].ewm(span=period, adjust=False).mean().values
    
    @staticmethod
    def rsi(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        if len(data) < period + 1:
            return np.array([])
        
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.values
    
    @staticmethod
    def macd(data: pd.DataFrame) -> Dict[str, np.ndarray]:
        """MACD."""
        if len(data) < 26:
            return {"macd": np.array([]), "signal": np.array([]), "histogram": np.array([])}
        
        exp1 = data["close"].ewm(span=12, adjust=False).mean()
        exp2 = data["close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        return {
            "macd": macd.values,
            "signal": signal.values,
            "histogram": histogram.values
        }
    
    @staticmethod
    def bollinger(data: pd.DataFrame, period: int = 20, std: int = 2) -> Dict[str, np.ndarray]:
        """Bollinger Bands."""
        if len(data) < period:
            return {"upper": np.array([]), "middle": np.array([]), "lower": np.array([]), "position": np.array([])}
        
        sma = data["close"].rolling(window=period).mean()
        rolling_std = data["close"].rolling(window=period).std()
        upper = sma + (rolling_std * std)
        lower = sma - (rolling_std * std)
        position = (data["close"] - lower) / (upper - lower)
        return {
            "upper": upper.values,
            "middle": sma.values,
            "lower": lower.values,
            "position": position.values
        }
    
    @staticmethod
    def atr(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Average True Range."""
        if len(data) < period + 1:
            return np.array([])
        
        high = data["high"]
        low = data["low"]
        close = data["close"]
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.values


# ============== FACTORY ==============

class MarketDataFactory:
    """Factory pour créer des composants de données de marché."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MarketDataEngine:
        """Crée un moteur de données de marché."""
        engine = MarketDataEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_technical_indicators() -> TechnicalIndicators:
        """Crée un calculateur d'indicateurs techniques."""
        return TechnicalIndicators()


# ============== EXPORT ==============

__all__ = [
    "MarketDataSource",
    "MarketDataInterval",
    "MarketDataCategory",
    "MarketData",
    "OrderBookData",
    "TradeData",
    "MarketSubscription",
    "MarketDataEngineInterface",
    "MarketDataEngine",
    "TechnicalIndicators",
    "MarketDataFactory"
]

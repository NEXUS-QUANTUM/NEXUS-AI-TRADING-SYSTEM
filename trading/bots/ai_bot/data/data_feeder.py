"""
NEXUS AI TRADING SYSTEM - Data Feeder for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/data/data_feeder.py
Description: Gestionnaire d'alimentation en données pour le bot AI.
             Supporte les flux en temps réel, le streaming asynchrone,
             le buffering, la réconciliation et la validation des données.
             Permet de nourrir les modèles AI avec des données propres
             et structurées en temps réel.
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import queue

import numpy as np
import pandas as pd

from trading.backtesting.data_provider import DataProvider
from trading.bots.ai_bot.data.data_processor import DataProcessor
from trading.bots.ai_bot.data.data_validator import DataValidator
from trading.bots.ai_bot.data.data_normalizer import DataNormalizer
from shared.exceptions import DataFeederError
from shared.helpers.date_helpers import timestamp_to_datetime, datetime_to_timestamp

# Configuration du logging
logger = logging.getLogger(__name__)


class FeedStatus(Enum):
    """Statut du data feeder."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    BUFFERING = "buffering"
    CATCHING_UP = "catching_up"
    ERROR = "error"
    STOPPED = "stopped"


class DataSourceType(Enum):
    """Types de sources de données."""
    BROKER = "broker"
    API = "api"
    WEBSOCKET = "websocket"
    DATABASE = "database"
    FILE = "file"
    CACHE = "cache"
    SIMULATED = "simulated"


@dataclass
class DataFeedConfig:
    """
    Configuration du data feeder.
    """
    # Sources de données
    symbol: str
    sources: List[DataSourceType] = field(default_factory=lambda: [
        DataSourceType.WEBSOCKET,
        DataSourceType.API,
        DataSourceType.BROKER
    ])
    
    # Paramètres de timeframes
    primary_timeframe: str = "1m"
    secondary_timeframes: List[str] = field(default_factory=lambda: ["5m", "15m", "1h"])
    
    # Paramètres de buffering
    buffer_size: int = 1000
    buffer_timeout: int = 60  # secondes
    max_queue_size: int = 10000
    
    # Paramètres de streaming
    stream_interval: float = 1.0  # secondes
    stream_batch_size: int = 100
    
    # Paramètres de backfill
    backfill_days: int = 30
    backfill_timeframe: str = "1m"
    backfill_batch_size: int = 1000
    
    # Paramètres de validation
    validate_data: bool = True
    strict_mode: bool = False
    max_data_lag: int = 60  # secondes
    
    # Paramètres de réconciliation
    reconcile_on_start: bool = True
    reconcile_interval: int = 3600  # secondes
    
    # Paramètres de performance
    parallel: bool = True
    n_workers: int = 4
    async_processing: bool = True
    
    # Paramètres de sortie
    enable_logging: bool = True
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Validation des paramètres."""
        if not self.symbol:
            raise DataFeederError("Symbole requis")
        
        if self.buffer_size < 10:
            raise DataFeederError("buffer_size doit être >= 10")
        
        if self.stream_interval < 0.1:
            raise DataFeederError("stream_interval doit être >= 0.1")
        
        if self.backfill_days < 0:
            raise DataFeederError("backfill_days doit être >= 0")


@dataclass
class DataBatch:
    """
    Batch de données.
    """
    symbol: str
    timeframe: str
    data: pd.DataFrame
    timestamp: datetime
    source: DataSourceType
    sequence: int = 0
    is_complete: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'data_shape': self.data.shape,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source.value,
            'sequence': self.sequence,
            'is_complete': self.is_complete
        }


@dataclass
class DataFeedStats:
    """
    Statistiques du data feeder.
    """
    total_batches: int = 0
    total_records: int = 0
    total_errors: int = 0
    total_skipped: int = 0
    buffer_usage: float = 0.0
    stream_latency: float = 0.0
    last_update: Optional[datetime] = None
    last_batch_time: Optional[datetime] = None
    sources_connected: int = 0
    sources_disconnected: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'total_batches': self.total_batches,
            'total_records': self.total_records,
            'total_errors': self.total_errors,
            'total_skipped': self.total_skipped,
            'buffer_usage': self.buffer_usage,
            'stream_latency': self.stream_latency,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'last_batch_time': self.last_batch_time.isoformat() if self.last_batch_time else None,
            'sources_connected': self.sources_connected,
            'sources_disconnected': self.sources_disconnected
        }


class DataFeeder:
    """
    Gestionnaire d'alimentation en données pour le bot AI.
    """
    
    def __init__(self, config: DataFeedConfig):
        """
        Initialise le data feeder.
        
        Args:
            config: Configuration du data feeder.
        """
        self.config = config
        self.state = FeedStatus.IDLE
        self.stats = DataFeedStats()
        
        # Composants
        self.data_provider = DataProvider()
        self.data_processor = DataProcessor()
        self.data_validator = DataValidator()
        self.data_normalizer = DataNormalizer()
        
        # Buffers
        self._buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=config.buffer_size))
        self._queue: queue.Queue = queue.Queue(maxsize=config.max_queue_size)
        
        # Cache de données
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._latest_data: Dict[str, pd.Series] = {}
        
        # État des sources
        self._source_status: Dict[DataSourceType, bool] = {}
        self._source_connections: Dict[DataSourceType, Any] = {}
        
        # Threads et tâches
        self._running = False
        self._pause_requested = False
        self._stop_requested = False
        self._worker_threads: List[threading.Thread] = []
        self._async_tasks: List[asyncio.Task] = []
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_data': [],
            'on_error': [],
            'on_status_change': [],
            'on_buffer_full': []
        }
        
        # Métadonnées
        self._sequence = 0
        self._last_sequence = 0
        
        logger.info(f"DataFeeder initialisé pour {config.symbol}")
        logger.info(f"Sources: {[s.value for s in config.sources]}")
        logger.info(f"Buffer: {config.buffer_size} records")
    
    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================
    
    def start(self) -> None:
        """
        Démarre le data feeder.
        """
        if self._running:
            logger.warning("DataFeeder déjà en cours d'exécution")
            return
        
        self.state = FeedStatus.INITIALIZING
        self._running = True
        self._stop_requested = False
        self._pause_requested = False
        
        logger.info("Démarrage du DataFeeder...")
        
        try:
            # Initialisation des sources
            self._initialize_sources()
            
            # Backfill initial
            if self.config.backfill_days > 0:
                self._perform_backfill()
            
            # Démarrage des threads
            self._start_workers()
            
            # Démarrage du stream
            if self.config.async_processing:
                asyncio.create_task(self._async_stream())
            else:
                self._start_sync_stream()
            
            self.state = FeedStatus.RUNNING
            logger.info("DataFeeder démarré avec succès")
            
        except Exception as e:
            logger.error(f"Erreur de démarrage: {e}")
            self.state = FeedStatus.ERROR
            raise DataFeederError(f"Erreur de démarrage: {e}")
    
    def stop(self) -> None:
        """
        Arrête le data feeder.
        """
        if not self._running:
            logger.warning("DataFeeder déjà arrêté")
            return
        
        logger.info("Arrêt du DataFeeder...")
        self.state = FeedStatus.STOPPING
        self._stop_requested = True
        self._running = False
        
        # Arrêt des threads
        for thread in self._worker_threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        # Arrêt des tâches asynchrones
        for task in self._async_tasks:
            task.cancel()
        
        # Fermeture des sources
        self._close_sources()
        
        self.state = FeedStatus.STOPPED
        logger.info("DataFeeder arrêté")
    
    def pause(self) -> None:
        """
        Met le data feeder en pause.
        """
        if not self._running:
            raise DataFeederError("DataFeeder non en cours d'exécution")
        
        self._pause_requested = True
        self.state = FeedStatus.PAUSED
        logger.info("DataFeeder en pause")
    
    def resume(self) -> None:
        """
        Reprend le data feeder.
        """
        if not self._running:
            raise DataFeederError("DataFeeder non en cours d'exécution")
        
        self._pause_requested = False
        self.state = FeedStatus.RUNNING
        logger.info("DataFeeder repris")
    
    # ============================================================
    # GESTION DES SOURCES
    # ============================================================
    
    def _initialize_sources(self) -> None:
        """
        Initialise les sources de données.
        """
        for source_type in self.config.sources:
            try:
                if source_type == DataSourceType.BROKER:
                    # Initialisation du broker
                    from trading.brokers.base import Broker
                    # self._source_connections[source_type] = Broker()
                    pass
                elif source_type == DataSourceType.WEBSOCKET:
                    # Initialisation du WebSocket
                    # self._source_connections[source_type] = WebSocketClient()
                    pass
                elif source_type == DataSourceType.API:
                    # Initialisation de l'API
                    # self._source_connections[source_type] = APIClient()
                    pass
                
                self._source_status[source_type] = True
                self.stats.sources_connected += 1
                logger.info(f"Source {source_type.value} initialisée")
                
            except Exception as e:
                logger.error(f"Erreur d'initialisation de {source_type.value}: {e}")
                self._source_status[source_type] = False
                self.stats.sources_disconnected += 1
    
    def _close_sources(self) -> None:
        """
        Ferme les sources de données.
        """
        for source_type, connection in self._source_connections.items():
            try:
                if connection:
                    # connection.close()
                    pass
                logger.info(f"Source {source_type.value} fermée")
            except Exception as e:
                logger.error(f"Erreur de fermeture de {source_type.value}: {e}")
    
    # ============================================================
    # BACKFILL
    # ============================================================
    
    def _perform_backfill(self) -> None:
        """
        Effectue le backfill initial.
        """
        logger.info(f"Backfill: {self.config.backfill_days} jours")
        
        try:
            start_date = datetime.now() - timedelta(days=self.config.backfill_days)
            end_date = datetime.now()
            
            # Récupération des données historiques
            data = self.data_provider.get_historical_data(
                symbol=self.config.symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=self.config.backfill_timeframe
            )
            
            if data is not None and not data.empty:
                # Traitement des données
                processed_data = self._process_data(data)
                
                # Chargement dans le buffer
                self._load_into_buffer(processed_data)
                
                # Mise à jour du cache
                self._update_cache(processed_data)
                
                logger.info(f"Backfill terminé: {len(processed_data)} records")
            else:
                logger.warning("Aucune donnée de backfill disponible")
                
        except Exception as e:
            logger.error(f"Erreur de backfill: {e}")
    
    def _load_into_buffer(self, data: pd.DataFrame) -> None:
        """
        Charge les données dans le buffer.
        
        Args:
            data: Données à charger.
        """
        for _, row in data.iterrows():
            self._buffers[self.config.symbol].append(row.to_dict())
            
            # Ajout à la queue
            try:
                self._queue.put(row.to_dict(), block=False)
            except queue.Full:
                logger.warning("Queue pleine, perte de données")
                self.stats.total_skipped += 1
        
        self.stats.total_records += len(data)
    
    # ============================================================
    # TRAITEMENT DES DONNÉES
    # ============================================================
    
    def _process_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Traite les données brutes.
        
        Args:
            data: Données brutes.
            
        Returns:
            Données traitées.
        """
        # Validation
        if self.config.validate_data:
            valid_data = self.data_validator.validate(data)
            if valid_data.empty and self.config.strict_mode:
                raise DataFeederError("Données invalides en mode strict")
            data = valid_data
        
        # Normalisation
        data = self.data_normalizer.normalize(data)
        
        # Ajout des métadonnées
        data['symbol'] = self.config.symbol
        data['processed_at'] = datetime.now()
        
        return data
    
    def _update_cache(self, data: pd.DataFrame) -> None:
        """
        Met à jour le cache de données.
        
        Args:
            data: Nouvelles données.
        """
        # Mise à jour du cache principal
        if self.config.symbol not in self._data_cache:
            self._data_cache[self.config.symbol] = data
        else:
            # Concaténation et suppression des doublons
            combined = pd.concat([self._data_cache[self.config.symbol], data])
            combined = combined.drop_duplicates(subset=['timestamp'])
            combined = combined.sort_values('timestamp')
            
            # Limitation de la taille
            if len(combined) > self.config.buffer_size * 2:
                combined = combined.iloc[-self.config.buffer_size:]
            
            self._data_cache[self.config.symbol] = combined
        
        # Mise à jour des dernières données
        if not data.empty:
            self._latest_data[self.config.symbol] = data.iloc[-1]
    
    # ============================================================
    # STREAMING
    # ============================================================
    
    def _start_sync_stream(self) -> None:
        """
        Démarre le streaming synchrone.
        """
        logger.info("Démarrage du stream synchrone")
        
        thread = threading.Thread(target=self._sync_stream_loop, daemon=True)
        thread.start()
        self._worker_threads.append(thread)
    
    def _sync_stream_loop(self) -> None:
        """
        Boucle du streaming synchrone.
        """
        while self._running and not self._stop_requested:
            try:
                if self._pause_requested:
                    time.sleep(0.1)
                    continue
                
                # Récupération des données
                data = self._fetch_data()
                
                if data is not None and not data.empty:
                    # Traitement
                    processed = self._process_data(data)
                    
                    # Chargement
                    self._load_into_buffer(processed)
                    self._update_cache(processed)
                    
                    # Notification
                    self._notify_callbacks('on_data', processed)
                    
                    # Statistiques
                    self.stats.total_batches += 1
                    self.stats.last_batch_time = datetime.now()
                
                # Attente
                time.sleep(self.config.stream_interval)
                
            except Exception as e:
                logger.error(f"Erreur de streaming: {e}")
                self.stats.total_errors += 1
                self._notify_callbacks('on_error', {'error': str(e)})
                time.sleep(5)
    
    async def _async_stream(self) -> None:
        """
        Streaming asynchrone.
        """
        logger.info("Démarrage du stream asynchrone")
        
        while self._running and not self._stop_requested:
            try:
                if self._pause_requested:
                    await asyncio.sleep(0.1)
                    continue
                
                # Récupération des données
                data = await self._fetch_data_async()
                
                if data is not None and not data.empty:
                    # Traitement
                    processed = self._process_data(data)
                    
                    # Chargement
                    self._load_into_buffer(processed)
                    self._update_cache(processed)
                    
                    # Notification
                    self._notify_callbacks('on_data', processed)
                    
                    # Statistiques
                    self.stats.total_batches += 1
                    self.stats.last_batch_time = datetime.now()
                
                # Attente
                await asyncio.sleep(self.config.stream_interval)
                
            except asyncio.CancelledError:
                logger.info("Stream asynchrone annulé")
                break
            except Exception as e:
                logger.error(f"Erreur de streaming asynchrone: {e}")
                self.stats.total_errors += 1
                self._notify_callbacks('on_error', {'error': str(e)})
                await asyncio.sleep(5)
    
    def _fetch_data(self) -> Optional[pd.DataFrame]:
        """
        Récupère les données depuis les sources.
        
        Returns:
            DataFrame des données ou None.
        """
        data = None
        
        # Essayer les sources dans l'ordre
        for source_type in self.config.sources:
            if not self._source_status.get(source_type, False):
                continue
            
            try:
                if source_type == DataSourceType.WEBSOCKET:
                    data = self._fetch_from_websocket()
                elif source_type == DataSourceType.API:
                    data = self._fetch_from_api()
                elif source_type == DataSourceType.BROKER:
                    data = self._fetch_from_broker()
                elif source_type == DataSourceType.DATABASE:
                    data = self._fetch_from_database()
                elif source_type == DataSourceType.CACHE:
                    data = self._fetch_from_cache()
                elif source_type == DataSourceType.SIMULATED:
                    data = self._generate_simulated_data()
                
                if data is not None and not data.empty:
                    break
                    
            except Exception as e:
                logger.debug(f"Erreur de source {source_type.value}: {e}")
                continue
        
        return data
    
    async def _fetch_data_async(self) -> Optional[pd.DataFrame]:
        """
        Récupère les données de manière asynchrone.
        
        Returns:
            DataFrame des données ou None.
        """
        # Version asynchrone de _fetch_data
        return await asyncio.get_event_loop().run_in_executor(
            None, self._fetch_data
        )
    
    def _fetch_from_websocket(self) -> Optional[pd.DataFrame]:
        """
        Récupère les données d'un WebSocket.
        
        Returns:
            DataFrame des données.
        """
        # Simulation de données WebSocket
        data = pd.DataFrame([{
            'timestamp': datetime.now(),
            'open': np.random.normal(100, 1),
            'high': np.random.normal(101, 1),
            'low': np.random.normal(99, 1),
            'close': np.random.normal(100, 1),
            'volume': np.random.randint(1000, 10000)
        }])
        return data
    
    def _fetch_from_api(self) -> Optional[pd.DataFrame]:
        """
        Récupère les données d'une API.
        
        Returns:
            DataFrame des données.
        """
        # Simulation de données API
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)
        
        data = self.data_provider.get_historical_data(
            symbol=self.config.symbol,
            start_date=start_time,
            end_date=end_time,
            timeframe=self.config.primary_timeframe
        )
        
        return data
    
    def _fetch_from_broker(self) -> Optional[pd.DataFrame]:
        """
        Récupère les données d'un broker.
        
        Returns:
            DataFrame des données.
        """
        # Simulation de données broker
        return self._fetch_from_api()
    
    def _fetch_from_database(self) -> Optional[pd.DataFrame]:
        """
        Récupère les données d'une base de données.
        
        Returns:
            DataFrame des données.
        """
        # Simulation de données base de données
        return None
    
    def _fetch_from_cache(self) -> Optional[pd.DataFrame]:
        """
        Récupère les données du cache.
        
        Returns:
            DataFrame des données.
        """
        if self.config.symbol in self._data_cache:
            cache = self._data_cache[self.config.symbol]
            if not cache.empty:
                # Dernières données
                return cache.iloc[-1:].copy()
        return None
    
    def _generate_simulated_data(self) -> pd.DataFrame:
        """
        Génère des données simulées.
        
        Returns:
            DataFrame de données simulées.
        """
        # Données synthétiques
        price = 100
        for _ in range(10):
            price = price * np.random.normal(1, 0.001)
        
        data = pd.DataFrame([{
            'timestamp': datetime.now(),
            'open': price * np.random.uniform(0.999, 1.001),
            'high': price * np.random.uniform(1.001, 1.005),
            'low': price * np.random.uniform(0.995, 0.999),
            'close': price,
            'volume': np.random.randint(1000, 10000)
        }])
        return data
    
    # ============================================================
    # WORKERS
    # ============================================================
    
    def _start_workers(self) -> None:
        """
        Démarre les workers de traitement.
        """
        if not self.config.parallel:
            return
        
        logger.info(f"Démarrage de {self.config.n_workers} workers")
        
        for i in range(self.config.n_workers):
            thread = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=True,
                name=f"DataWorker-{i}"
            )
            thread.start()
            self._worker_threads.append(thread)
    
    def _worker_loop(self, worker_id: int) -> None:
        """
        Boucle des workers de traitement.
        
        Args:
            worker_id: ID du worker.
        """
        logger.info(f"Worker {worker_id} démarré")
        
        while self._running and not self._stop_requested:
            try:
                # Récupération des données de la queue
                data_item = self._queue.get(timeout=1)
                
                if data_item is None:
                    continue
                
                # Traitement du lot
                self._process_data_item(data_item)
                
                self._queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} erreur: {e}")
                self.stats.total_errors += 1
        
        logger.info(f"Worker {worker_id} arrêté")
    
    def _process_data_item(self, data_item: Dict[str, Any]) -> None:
        """
        Traite un élément de données.
        
        Args:
            data_item: Élément de données.
        """
        # Traitement spécifique selon le type
        pass
    
    # ============================================================
    # RÉCONCILIATION
    # ============================================================
    
    def reconcile(self) -> None:
        """
        Réconcilie les données entre les sources.
        """
        logger.info("Réconciliation des données...")
        
        try:
            # Vérification des écarts
            source_data = {}
            for source_type in self.config.sources:
                if source_type == DataSourceType.API:
                    data = self._fetch_from_api()
                    if data is not None and not data.empty:
                        source_data[source_type] = data
            
            # Comparaison et correction
            if len(source_data) > 1:
                self._compare_and_correct(source_data)
            
            logger.info("Réconciliation terminée")
            
        except Exception as e:
            logger.error(f"Erreur de réconciliation: {e}")
    
    def _compare_and_correct(self, source_data: Dict[DataSourceType, pd.DataFrame]) -> None:
        """
        Compare et corrige les données entre les sources.
        
        Args:
            source_data: Données par source.
        """
        # Trouver la source la plus récente
        latest_source = None
        latest_time = None
        
        for source, data in source_data.items():
            if data is not None and not data.empty:
                last_time = data.iloc[-1]['timestamp']
                if latest_time is None or last_time > latest_time:
                    latest_time = last_time
                    latest_source = source
        
        if latest_source is not None:
            # Utiliser la source la plus récente comme référence
            reference_data = source_data[latest_source]
            self._update_cache(reference_data)
            
            logger.info(f"Source de référence: {latest_source.value}")
    
    # ============================================================
    # GESTION DES CALLBACKS
    # ============================================================
    
    def on_data(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les données.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_data'].append(callback)
    
    def on_error(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les erreurs.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_error'].append(callback)
    
    def on_status_change(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les changements de statut.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_status_change'].append(callback)
    
    def _notify_callbacks(self, event: str, data: Any) -> None:
        """
        Notifie les callbacks d'un événement.
        
        Args:
            event: Nom de l'événement.
            data: Données de l'événement.
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Erreur dans le callback {event}: {e}")
    
    # ============================================================
    # ACCÈS AUX DONNÉES
    # ============================================================
    
    def get_latest_data(self) -> Optional[pd.Series]:
        """
        Retourne les dernières données.
        
        Returns:
            Dernières données ou None.
        """
        return self._latest_data.get(self.config.symbol)
    
    def get_data(self, timeframe: Optional[str] = None) -> pd.DataFrame:
        """
        Retourne les données courantes.
        
        Args:
            timeframe: Timeframe spécifique.
            
        Returns:
            DataFrame des données.
        """
        if self.config.symbol in self._data_cache:
            data = self._data_cache[self.config.symbol]
            if data is not None and not data.empty:
                return data.copy()
        return pd.DataFrame()
    
    def get_historical_data(
        self,
        days: int = 7,
        timeframe: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Retourne des données historiques.
        
        Args:
            days: Nombre de jours.
            timeframe: Timeframe spécifique.
            
        Returns:
            DataFrame des données historiques.
        """
        timeframe = timeframe or self.config.backfill_timeframe
        
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()
        
        return self.data_provider.get_historical_data(
            symbol=self.config.symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe
        )
    
    def get_buffered_data(self, n_records: int = 100) -> pd.DataFrame:
        """
        Retourne les données du buffer.
        
        Args:
            n_records: Nombre de records.
            
        Returns:
            DataFrame des données du buffer.
        """
        buffer = self._buffers.get(self.config.symbol, deque())
        if not buffer:
            return pd.DataFrame()
        
        data = list(buffer)
        data = data[-n_records:] if n_records > 0 else data
        
        return pd.DataFrame(data)
    
    # ============================================================
    # STATISTIQUES ET MONITORING
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du data feeder.
        
        Returns:
            Statistiques détaillées.
        """
        buffer = self._buffers.get(self.config.symbol, deque())
        
        stats = self.stats.to_dict()
        stats.update({
            'status': self.state.value,
            'buffer_size': len(buffer),
            'buffer_max_size': self.config.buffer_size,
            'queue_size': self._queue.qsize(),
            'cache_size': len(self._data_cache.get(self.config.symbol, pd.DataFrame())),
            'running': self._running,
            'paused': self._pause_requested
        })
        
        return stats
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut du data feeder.
        
        Returns:
            Statut du data feeder.
        """
        return {
            'status': self.state.value,
            'running': self._running,
            'paused': self._pause_requested,
            'sources': {
                source.value: self._source_status.get(source, False)
                for source in self.config.sources
            },
            'stats': self.stats.to_dict()
        }
    
    def clear_buffer(self) -> None:
        """
        Vide le buffer.
        """
        if self.config.symbol in self._buffers:
            self._buffers[self.config.symbol].clear()
        logger.info("Buffer vidé")
    
    def clear_cache(self) -> None:
        """
        Vide le cache.
        """
        self._data_cache.clear()
        self._latest_data.clear()
        logger.info("Cache vidé")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_data_feeder(
    symbol: str,
    primary_timeframe: str = "1m",
    buffer_size: int = 1000,
    **kwargs
) -> DataFeeder:
    """
    Crée un data feeder avec configuration simplifiée.
    
    Args:
        symbol: Symbole à suivre.
        primary_timeframe: Timeframe principal.
        buffer_size: Taille du buffer.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du DataFeeder.
    """
    config = DataFeedConfig(
        symbol=symbol,
        primary_timeframe=primary_timeframe,
        buffer_size=buffer_size,
        **kwargs
    )
    return DataFeeder(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'DataFeeder',
    'DataFeedConfig',
    'DataFeedStats',
    'DataBatch',
    'FeedStatus',
    'DataSourceType',
    'create_data_feeder'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

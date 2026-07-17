"""
NEXUS AI TRADING SYSTEM - Data Pipeline for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/data/data_pipeline.py
Description: Pipeline de traitement de données complet pour le bot AI.
             Intègre l'extraction, la validation, la normalisation,
             l'augmentation, la transformation et le stockage des données.
             Supporte les flux batch et streaming avec orchestration avancée.
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

import numpy as np
import pandas as pd

from trading.bots.ai_bot.data.data_feeder import DataFeeder, DataFeedConfig
from trading.bots.ai_bot.data.data_validator import DataValidator, ValidationConfig
from trading.bots.ai_bot.data.data_normalizer import DataNormalizer, NormalizationConfig
from trading.bots.ai_bot.data.data_augmentation import DataAugmentor, AugmentationConfig
from trading.bots.ai_bot.data.data_processor import DataProcessor, ProcessingConfig
from trading.bots.ai_bot.data.data_storage import DataStorage, StorageConfig
from shared.exceptions import PipelineError
from shared.helpers.date_helpers import timestamp_to_datetime

# Configuration du logging
logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Étapes du pipeline."""
    EXTRACTION = "extraction"
    VALIDATION = "validation"
    NORMALIZATION = "normalization"
    AUGMENTATION = "augmentation"
    FEATURE_ENGINEERING = "feature_engineering"
    TRANSFORMATION = "transformation"
    STORAGE = "storage"
    COMPLETE = "complete"


class PipelineStatus(Enum):
    """Statut du pipeline."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PROCESSING = "processing"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class PipelineConfig:
    """
    Configuration du pipeline de données.
    """
    # Nom et description
    name: str = "default_pipeline"
    description: str = ""
    
    # Étapes activées
    enable_extraction: bool = True
    enable_validation: bool = True
    enable_normalization: bool = True
    enable_augmentation: bool = True
    enable_feature_engineering: bool = True
    enable_transformation: bool = True
    enable_storage: bool = True
    
    # Configurations des composants
    feeder_config: Optional[DataFeedConfig] = None
    validator_config: Optional[ValidationConfig] = None
    normalizer_config: Optional[NormalizationConfig] = None
    augmentor_config: Optional[AugmentationConfig] = None
    processor_config: Optional[ProcessingConfig] = None
    storage_config: Optional[StorageConfig] = None
    
    # Paramètres de pipeline
    batch_size: int = 100
    max_queue_size: int = 1000
    parallel: bool = True
    n_workers: int = 4
    async_processing: bool = True
    
    # Paramètres de performance
    cache_size: int = 10000
    cache_ttl: int = 3600  # secondes
    
    # Paramètres de monitoring
    enable_monitoring: bool = True
    log_level: str = "INFO"
    save_intermediate: bool = False
    
    # Paramètres de fallback
    fallback_on_error: bool = True
    max_retries: int = 3
    retry_delay: int = 5
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.batch_size < 1:
            raise PipelineError("batch_size doit être >= 1")
        
        if self.max_queue_size < self.batch_size:
            raise PipelineError("max_queue_size doit être >= batch_size")
        
        # Configurations par défaut
        if self.feeder_config is None:
            self.feeder_config = DataFeedConfig(symbol="BTC-USD")
        
        if self.validator_config is None:
            self.validator_config = ValidationConfig()
        
        if self.normalizer_config is None:
            self.normalizer_config = NormalizationConfig()
        
        if self.augmentor_config is None:
            self.augmentor_config = AugmentationConfig()
        
        if self.processor_config is None:
            self.processor_config = ProcessingConfig()
        
        if self.storage_config is None:
            self.storage_config = StorageConfig()


@dataclass
class PipelineMetrics:
    """
    Métriques du pipeline.
    """
    # Compteurs
    total_inputs: int = 0
    total_outputs: int = 0
    total_errors: int = 0
    total_skipped: int = 0
    total_processed: int = 0
    
    # Temps
    average_processing_time: float = 0.0
    total_processing_time: float = 0.0
    last_processing_time: float = 0.0
    max_processing_time: float = 0.0
    
    # Étapes
    stage_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Performance
    throughput: float = 0.0  # items/seconde
    queue_size: int = 0
    cache_hit_rate: float = 0.0
    cache_miss_rate: float = 0.0
    
    # Statut
    status: str = "idle"
    last_update: Optional[datetime] = None
    current_stage: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'total_inputs': self.total_inputs,
            'total_outputs': self.total_outputs,
            'total_errors': self.total_errors,
            'total_skipped': self.total_skipped,
            'total_processed': self.total_processed,
            'average_processing_time': round(self.average_processing_time, 4),
            'total_processing_time': round(self.total_processing_time, 2),
            'last_processing_time': round(self.last_processing_time, 4),
            'max_processing_time': round(self.max_processing_time, 4),
            'throughput': round(self.throughput, 2),
            'queue_size': self.queue_size,
            'cache_hit_rate': round(self.cache_hit_rate, 4),
            'cache_miss_rate': round(self.cache_miss_rate, 4),
            'status': self.status,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'current_stage': self.current_stage,
            'stage_metrics': self.stage_metrics
        }


class DataPipeline:
    """
    Pipeline complet de traitement de données pour le bot AI.
    """
    
    def __init__(self, config: PipelineConfig):
        """
        Initialise le pipeline de données.
        
        Args:
            config: Configuration du pipeline.
        """
        self.config = config
        self.status = PipelineStatus.IDLE
        self.metrics = PipelineMetrics()
        
        # Composants du pipeline
        self.feeder = DataFeeder(config.feeder_config) if config.enable_extraction else None
        self.validator = DataValidator(config.validator_config) if config.enable_validation else None
        self.normalizer = DataNormalizer(config.normalizer_config) if config.enable_normalization else None
        self.augmentor = DataAugmentor(config.augmentor_config) if config.enable_augmentation else None
        self.processor = DataProcessor(config.processor_config) if config.enable_feature_engineering else None
        self.storage = DataStorage(config.storage_config) if config.enable_storage else None
        
        # Queues de traitement
        self.input_queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_queue_size)
        self.output_queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_queue_size)
        
        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_batch_complete': [],
            'on_error': [],
            'on_stage_complete': [],
            'on_status_change': []
        }
        
        # État d'exécution
        self._running = False
        self._stop_requested = False
        self._pause_requested = False
        self._processing_tasks: List[asyncio.Task] = []
        
        # Statistiques de stage
        self._stage_times: Dict[str, List[float]] = {}
        
        logger.info(f"DataPipeline initialisé: {config.name}")
        logger.info(f"Étapes activées: {self._get_active_stages()}")
    
    def _get_active_stages(self) -> List[str]:
        """
        Retourne la liste des étapes actives.
        
        Returns:
            Liste des étapes actives.
        """
        stages = []
        if self.config.enable_extraction:
            stages.append('extraction')
        if self.config.enable_validation:
            stages.append('validation')
        if self.config.enable_normalization:
            stages.append('normalization')
        if self.config.enable_augmentation:
            stages.append('augmentation')
        if self.config.enable_feature_engineering:
            stages.append('feature_engineering')
        if self.config.enable_transformation:
            stages.append('transformation')
        if self.config.enable_storage:
            stages.append('storage')
        return stages
    
    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================
    
    async def start(self) -> None:
        """
        Démarre le pipeline.
        """
        if self.status in [PipelineStatus.RUNNING, PipelineStatus.PROCESSING]:
            logger.warning("Pipeline déjà en cours d'exécution")
            return
        
        self.status = PipelineStatus.INITIALIZING
        self._running = True
        self._stop_requested = False
        self._pause_requested = False
        
        logger.info(f"Démarrage du pipeline: {self.config.name}")
        
        try:
            # Initialisation des composants
            await self._initialize_components()
            
            # Démarrage des workers
            await self._start_workers()
            
            # Démarrage du feeder
            if self.feeder:
                await self.feeder.start()
            
            self.status = PipelineStatus.RUNNING
            self.metrics.status = "running"
            self._notify_callbacks('on_status_change', {'status': 'running'})
            
            logger.info("Pipeline démarré avec succès")
            
        except Exception as e:
            logger.error(f"Erreur de démarrage: {e}")
            self.status = PipelineStatus.ERROR
            self.metrics.status = "error"
            raise PipelineError(f"Erreur de démarrage: {e}")
    
    async def stop(self) -> None:
        """
        Arrête le pipeline.
        """
        if not self._running:
            logger.warning("Pipeline déjà arrêté")
            return
        
        logger.info("Arrêt du pipeline...")
        self.status = PipelineStatus.STOPPED
        self.metrics.status = "stopped"
        self._stop_requested = True
        self._running = False
        
        # Arrêt des composants
        if self.feeder:
            await self.feeder.stop()
        
        # Annulation des tâches
        for task in self._processing_tasks:
            task.cancel()
        
        await asyncio.gather(*self._processing_tasks, return_exceptions=True)
        
        # Nettoyage
        self._processing_tasks.clear()
        self._notify_callbacks('on_status_change', {'status': 'stopped'})
        
        logger.info("Pipeline arrêté")
    
    async def pause(self) -> None:
        """
        Met le pipeline en pause.
        """
        if not self._running:
            raise PipelineError("Pipeline non en cours d'exécution")
        
        self._pause_requested = True
        self.status = PipelineStatus.PAUSED
        self.metrics.status = "paused"
        
        if self.feeder:
            await self.feeder.pause()
        
        self._notify_callbacks('on_status_change', {'status': 'paused'})
        logger.info("Pipeline en pause")
    
    async def resume(self) -> None:
        """
        Reprend le pipeline.
        """
        if not self._running:
            raise PipelineError("Pipeline non en cours d'exécution")
        
        self._pause_requested = False
        self.status = PipelineStatus.RUNNING
        self.metrics.status = "running"
        
        if self.feeder:
            await self.feeder.resume()
        
        self._notify_callbacks('on_status_change', {'status': 'running'})
        logger.info("Pipeline repris")
    
    # ============================================================
    # TRAITEMENT DES DONNÉES
    # ============================================================
    
    async def process_batch(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Traite un batch de données à travers le pipeline.
        
        Args:
            data: Données à traiter.
            
        Returns:
            Données traitées.
        """
        start_time = time.time()
        self.metrics.total_inputs += len(data)
        
        try:
            # Étape 1: Validation
            if self.config.enable_validation and self.validator:
                data = await self._process_stage(
                    'validation',
                    self.validator.validate,
                    data
                )
            
            # Étape 2: Normalisation
            if self.config.enable_normalization and self.normalizer:
                data = await self._process_stage(
                    'normalization',
                    self.normalizer.fit_transform,
                    data
                )
            
            # Étape 3: Augmentation
            if self.config.enable_augmentation and self.augmentor:
                result = await self._process_stage(
                    'augmentation',
                    self.augmentor.augment,
                    data
                )
                if hasattr(result, 'data'):
                    data = result.data
            
            # Étape 4: Feature Engineering
            if self.config.enable_feature_engineering and self.processor:
                data = await self._process_stage(
                    'feature_engineering',
                    self.processor.process_features,
                    data
                )
            
            # Étape 5: Stockage
            if self.config.enable_storage and self.storage:
                await self._process_stage(
                    'storage',
                    self.storage.store,
                    data
                )
            
            # Mise à jour des métriques
            processing_time = time.time() - start_time
            self._update_metrics(data, processing_time)
            
            self.metrics.current_stage = None
            self.metrics.last_update = datetime.now()
            self.metrics.total_processed += len(data)
            self.metrics.total_outputs += len(data)
            
            self._notify_callbacks('on_batch_complete', {
                'batch_size': len(data),
                'processing_time': processing_time
            })
            
            return data
            
        except Exception as e:
            logger.error(f"Erreur de traitement: {e}")
            self.metrics.total_errors += 1
            self._notify_callbacks('on_error', {'error': str(e)})
            
            if not self.config.fallback_on_error:
                raise
            
            return pd.DataFrame()
    
    async def _process_stage(
        self,
        stage_name: str,
        stage_func: Callable,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Traite une étape du pipeline.
        
        Args:
            stage_name: Nom de l'étape.
            stage_func: Fonction de traitement.
            data: Données à traiter.
            
        Returns:
            Données traitées.
        """
        start_time = time.time()
        self.metrics.current_stage = stage_name
        
        try:
            # Vérification du cache
            cache_key = f"{stage_name}_{hash(str(data))}"
            if cache_key in self._cache:
                cache_entry = self._cache[cache_key]
                cache_time = self._cache_timestamps.get(cache_key)
                
                if cache_time and (datetime.now() - cache_time).seconds < self.config.cache_ttl:
                    self.metrics.cache_hit_rate = (self.metrics.cache_hit_rate * 0.9 + 0.1)
                    logger.debug(f"Cache hit pour {stage_name}")
                    return cache_entry
            
            # Exécution de l'étape
            result = stage_func(data)
            
            # Sauvegarde dans le cache
            if self.config.cache_size > 0:
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = datetime.now()
                
                # Nettoyage du cache si nécessaire
                if len(self._cache) > self.config.cache_size:
                    oldest_key = min(self._cache_timestamps.keys(), 
                                   key=lambda k: self._cache_timestamps[k])
                    del self._cache[oldest_key]
                    del self._cache_timestamps[oldest_key]
            
            # Métriques de l'étape
            stage_time = time.time() - start_time
            if stage_name not in self._stage_times:
                self._stage_times[stage_name] = []
            self._stage_times[stage_name].append(stage_time)
            
            # Limitation de l'historique
            if len(self._stage_times[stage_name]) > 1000:
                self._stage_times[stage_name] = self._stage_times[stage_name][-1000:]
            
            # Mise à jour des métriques globales
            self.metrics.stage_metrics[stage_name] = {
                'avg_time': round(np.mean(self._stage_times[stage_name]), 4),
                'last_time': round(stage_time, 4),
                'total_calls': len(self._stage_times[stage_name])
            }
            
            self._notify_callbacks('on_stage_complete', {
                'stage': stage_name,
                'time': stage_time,
                'data_shape': result.shape if hasattr(result, 'shape') else None
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur dans l'étape {stage_name}: {e}")
            self.metrics.total_errors += 1
            self.metrics.cache_miss_rate = (self.metrics.cache_miss_rate * 0.9 + 0.1)
            
            if self.config.fallback_on_error:
                logger.warning(f"Fallback pour l'étape {stage_name}")
                return data
            
            raise
    
    def _update_metrics(self, data: pd.DataFrame, processing_time: float) -> None:
        """
        Met à jour les métriques.
        
        Args:
            data: Données traitées.
            processing_time: Temps de traitement.
        """
        self.metrics.last_processing_time = processing_time
        self.metrics.total_processing_time += processing_time
        self.metrics.max_processing_time = max(
            self.metrics.max_processing_time,
            processing_time
        )
        
        # Moyenne glissante
        if self.metrics.average_processing_time == 0:
            self.metrics.average_processing_time = processing_time
        else:
            self.metrics.average_processing_time = (
                self.metrics.average_processing_time * 0.9 + processing_time * 0.1
            )
        
        # Throughput
        if processing_time > 0:
            self.metrics.throughput = len(data) / processing_time
    
    # ============================================================
    # WORKERS ET TÂCHES
    # ============================================================
    
    async def _initialize_components(self) -> None:
        """
        Initialise les composants du pipeline.
        """
        # Initialisation du normaliseur
        if self.normalizer and self.config.enable_normalization:
            # Essayer de charger un normaliseur existant
            try:
                self.normalizer.load("models/normalizer.pkl")
                logger.info("Normaliseur chargé")
            except:
                logger.info("Normaliseur à ajuster")
    
    async def _start_workers(self) -> None:
        """
        Démarre les workers de traitement.
        """
        if not self.config.parallel:
            # Un seul worker
            worker = asyncio.create_task(self._worker_loop(0))
            self._processing_tasks.append(worker)
            return
        
        # Plusieurs workers
        for i in range(self.config.n_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._processing_tasks.append(worker)
        
        logger.info(f"{len(self._processing_tasks)} workers démarrés")
    
    async def _worker_loop(self, worker_id: int) -> None:
        """
        Boucle des workers.
        
        Args:
            worker_id: ID du worker.
        """
        logger.info(f"Worker {worker_id} démarré")
        
        while self._running and not self._stop_requested:
            try:
                # Vérification de la pause
                if self._pause_requested:
                    await asyncio.sleep(0.1)
                    continue
                
                # Récupération d'un batch
                try:
                    data = await asyncio.wait_for(
                        self.input_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Traitement
                self.status = PipelineStatus.PROCESSING
                self.metrics.status = "processing"
                
                try:
                    processed_data = await self.process_batch(data)
                    
                    # Envoi vers la sortie
                    if not processed_data.empty:
                        try:
                            self.output_queue.put_nowait(processed_data)
                        except asyncio.QueueFull:
                            logger.warning(f"Queue de sortie pleine (worker {worker_id})")
                            self.metrics.total_skipped += len(processed_data)
                    
                except Exception as e:
                    logger.error(f"Worker {worker_id} erreur: {e}")
                    self.metrics.total_errors += 1
                
                finally:
                    self.input_queue.task_done()
                    self.status = PipelineStatus.RUNNING
                    self.metrics.status = "running"
                
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} annulé")
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} erreur fatale: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_id} arrêté")
    
    # ============================================================
    # INTERFACE DE DONNÉES
    # ============================================================
    
    async def feed_data(self, data: pd.DataFrame) -> None:
        """
        Alimente le pipeline avec des données.
        
        Args:
            data: Données à traiter.
        """
        if data.empty:
            return
        
        try:
            await self.input_queue.put(data)
            logger.debug(f"Données ajoutées à la queue: {len(data)} lignes")
            
        except asyncio.QueueFull:
            logger.warning("Queue pleine, données ignorées")
            self.metrics.total_skipped += len(data)
    
    async def get_processed_data(self, timeout: float = 5.0) -> pd.DataFrame:
        """
        Récupère les données traitées.
        
        Args:
            timeout: Timeout en secondes.
            
        Returns:
            Données traitées.
        """
        try:
            data = await asyncio.wait_for(
                self.output_queue.get(),
                timeout=timeout
            )
            self.output_queue.task_done()
            return data
            
        except asyncio.TimeoutError:
            return pd.DataFrame()
    
    def get_latest_batch(self) -> pd.DataFrame:
        """
        Récupère le dernier batch traité (non-bloquant).
        
        Returns:
            Dernier batch ou DataFrame vide.
        """
        try:
            if not self.output_queue.empty():
                data = self.output_queue.get_nowait()
                self.output_queue.task_done()
                return data
        except (asyncio.QueueEmpty, asyncio.QueueFull):
            pass
        
        return pd.DataFrame()
    
    # ============================================================
    # MONITORING
    # ============================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Retourne les métriques du pipeline.
        
        Returns:
            Métriques du pipeline.
        """
        metrics = self.metrics.to_dict()
        
        # Ajout des métriques du feeder
        if self.feeder:
            metrics['feeder'] = self.feeder.get_stats()
        
        # Ajout des métriques de la queue
        metrics['queue'] = {
            'input_size': self.input_queue.qsize(),
            'output_size': self.output_queue.qsize(),
            'max_size': self.config.max_queue_size
        }
        
        # Ajout des métriques du cache
        metrics['cache'] = {
            'size': len(self._cache),
            'max_size': self.config.cache_size,
            'hit_rate': self.metrics.cache_hit_rate,
            'miss_rate': self.metrics.cache_miss_rate
        }
        
        return metrics
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut du pipeline.
        
        Returns:
            Statut du pipeline.
        """
        return {
            'status': self.status.value,
            'running': self._running,
            'paused': self._pause_requested,
            'active_stages': self._get_active_stages(),
            'current_stage': self.metrics.current_stage,
            'workers': len(self._processing_tasks),
            'metrics': self.metrics.to_dict()
        }
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on_batch_complete(self, callback: Callable) -> None:
        """
        Ajoute un callback pour la fin d'un batch.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_batch_complete'].append(callback)
    
    def on_error(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les erreurs.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_error'].append(callback)
    
    def on_stage_complete(self, callback: Callable) -> None:
        """
        Ajoute un callback pour la fin d'une étape.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_stage_complete'].append(callback)
    
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
    # SAUVEGARDE ET CHARGEMENT
    # ============================================================
    
    async def save_pipeline_state(self, filepath: str) -> None:
        """
        Sauvegarde l'état du pipeline.
        
        Args:
            filepath: Chemin de sauvegarde.
        """
        import os
        import pickle
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        state = {
            'config': self.config,
            'metrics': self.metrics,
            'timestamp': datetime.now(),
            'pipeline_name': self.config.name
        }
        
        # Sauvegarde des composants
        if self.normalizer:
            normalizer_path = filepath.replace('.pkl', '_normalizer.pkl')
            self.normalizer.save(normalizer_path)
        
        if self.validator:
            validator_path = filepath.replace('.pkl', '_validator.pkl')
            # self.validator.save(validator_path)
        
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        
        logger.info(f"État du pipeline sauvegardé: {filepath}")
    
    async def load_pipeline_state(self, filepath: str) -> None:
        """
        Charge l'état du pipeline.
        
        Args:
            filepath: Chemin de chargement.
        """
        import pickle
        
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        # Chargement des composants
        if self.normalizer:
            normalizer_path = filepath.replace('.pkl', '_normalizer.pkl')
            try:
                self.normalizer.load(normalizer_path)
            except:
                logger.warning("Normaliseur non trouvé")
        
        self.metrics = state['metrics']
        
        logger.info(f"État du pipeline chargé: {filepath}")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_pipeline(
    symbol: str,
    name: str = "trading_pipeline",
    batch_size: int = 100,
    **kwargs
) -> DataPipeline:
    """
    Crée un pipeline avec configuration simplifiée.
    
    Args:
        symbol: Symbole à trader.
        name: Nom du pipeline.
        batch_size: Taille des batches.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du DataPipeline.
    """
    feeder_config = DataFeedConfig(symbol=symbol)
    config = PipelineConfig(
        name=name,
        batch_size=batch_size,
        feeder_config=feeder_config,
        **kwargs
    )
    return DataPipeline(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'DataPipeline',
    'PipelineConfig',
    'PipelineMetrics',
    'PipelineStage',
    'PipelineStatus',
    'create_pipeline'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

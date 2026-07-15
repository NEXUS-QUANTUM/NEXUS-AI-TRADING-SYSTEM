
# ai/prediction/prediction_pipeline.py
"""
NEXUS AI TRADING SYSTEM - Prediction Pipeline
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import pickle
import os
import time
import threading
from queue import Queue, PriorityQueue
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PredictionPipelineConfig:
    """Configuration pour Prediction Pipeline"""
    name: str = "default_pipeline"
    batch_size: int = 64
    max_queue_size: int = 1000
    num_workers: int = 4
    use_cache: bool = True
    cache_ttl: int = 300
    save_intermediate: bool = True
    intermediate_dir: str = "./intermediate"
    log_predictions: bool = True
    log_file: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'batch_size': self.batch_size,
            'max_queue_size': self.max_queue_size,
            'num_workers': self.num_workers,
            'use_cache': self.use_cache,
            'cache_ttl': self.cache_ttl,
            'save_intermediate': self.save_intermediate,
            'intermediate_dir': self.intermediate_dir,
            'log_predictions': self.log_predictions,
            'log_file': self.log_file,
            'timeout': self.timeout,
            'retry_count': self.retry_count,
        }


@dataclass
class PredictionTask:
    """Tâche de prédiction"""
    id: str
    data: Any
    timestamp: datetime
    priority: int = 0
    retry_count: int = 0
    status: str = 'pending'  # pending, processing, completed, failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority,
            'retry_count': self.retry_count,
            'status': self.status,
        }


@dataclass
class PredictionResult:
    """Résultat de prédiction"""
    task_id: str
    predictions: np.ndarray
    confidence: Optional[np.ndarray] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    processing_time: float = 0.0
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'confidence': self.confidence.tolist() if isinstance(self.confidence, np.ndarray) else self.confidence,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
            'processing_time': self.processing_time,
            'success': self.success,
            'error': self.error,
        }


class PredictionPipeline:
    """
    Pipeline de prédiction pour l'IA de trading.

    Features:
    - Batch processing
    - Async predictions
    - Queue management
    - Multi-worker
    - Caching
    - Logging
    - Retry mechanism
    - Intermediate saving

    Example:
        ```python
        config = PredictionPipelineConfig(
            name='market_pipeline',
            batch_size=64,
            num_workers=4,
            use_cache=True
        )
        pipeline = PredictionPipeline(config)

        # Add predictor
        pipeline.add_predictor('lstm', lstm_model)
        pipeline.add_predictor('xgboost', xgb_model)

        # Process
        pipeline.start()
        result = pipeline.predict(data)
        pipeline.stop()
        ```
    """

    def __init__(self, config: Optional[PredictionPipelineConfig] = None):
        self.config = config or PredictionPipelineConfig()
        self.predictors: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.preprocessors: List[Callable] = []
        self.postprocessors: List[Callable] = []
        self._queue: PriorityQueue = PriorityQueue(maxsize=self.config.max_queue_size)
        self._results: Dict[str, PredictionResult] = {}
        self._cache: Dict[str, Any] = {}
        self._workers: List[threading.Thread] = []
        self._running = False
        self._lock = threading.RLock()

        # Stats
        self._stats = {
            'total_tasks': 0,
            'completed': 0,
            'failed': 0,
            'avg_time': 0,
        }

        # Intermediate directory
        if self.config.save_intermediate:
            os.makedirs(self.config.intermediate_dir, exist_ok=True)

        # Logging
        if self.config.log_file:
            self._setup_logging()

        logger.info(f"PredictionPipeline '{self.config.name}' initialisé")

    def _setup_logging(self):
        """Configure le logging"""
        if self.config.log_file:
            os.makedirs(os.path.dirname(self.config.log_file), exist_ok=True)
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(file_handler)

    def add_predictor(self, name: str, predictor: Any, scaler: Optional[Any] = None):
        """
        Ajoute un prédicteur au pipeline.

        Args:
            name: Nom du prédicteur
            predictor: Modèle de prédiction
            scaler: Scaler pour normalisation
        """
        self.predictors[name] = predictor
        if scaler:
            self.scalers[name] = scaler
        logger.info(f"Prédicteur '{name}' ajouté")

    def add_preprocessor(self, func: Callable):
        """Ajoute un préprocesseur"""
        self.preprocessors.append(func)
        logger.info("Préprocesseur ajouté")

    def add_postprocessor(self, func: Callable):
        """Ajoute un postprocesseur"""
        self.postprocessors.append(func)
        logger.info("Postprocesseur ajouté")

    def _preprocess(self, data: Any) -> Any:
        """Applique les préprocesseurs"""
        for func in self.preprocessors:
            data = func(data)
        return data

    def _postprocess(self, data: Any) -> Any:
        """Applique les postprocesseurs"""
        for func in self.postprocessors:
            data = func(data)
        return data

    def _get_cache_key(self, task: PredictionTask) -> str:
        """Génère une clé de cache"""
        import hashlib
        key_data = f"{task.id}_{task.data}_{task.priority}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _save_intermediate(self, task_id: str, data: Any):
        """Sauvegarde les données intermédiaires"""
        if not self.config.save_intermediate:
            return

        try:
            filepath = os.path.join(self.config.intermediate_dir, f"{task_id}.pkl")
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Erreur de sauvegarde intermédiaire: {e}")

    def _process_task(self, task: PredictionTask) -> PredictionResult:
        """
        Traite une tâche de prédiction.

        Args:
            task: Tâche à traiter

        Returns:
            PredictionResult: Résultat de la prédiction
        """
        start_time = time.time()
        result = PredictionResult(
            task_id=task.id,
            predictions=np.array([]),
            processing_time=0.0
        )

        try:
            # Préprocessing
            data = self._preprocess(task.data)

            # Cache
            cache_key = self._get_cache_key(task)
            if self.config.use_cache and cache_key in self._cache:
                cached = self._cache[cache_key]
                result.predictions = cached['predictions']
                result.confidence = cached.get('confidence')
                result.metadata = cached.get('metadata')
                result.processing_time = time.time() - start_time
                logger.debug(f"Task {task.id} récupérée du cache")
                return result

            # Prédiction avec chaque prédicteur
            predictions = []
            confidences = []

            for name, predictor in self.predictors.items():
                try:
                    # Normalisation
                    if name in self.scalers:
                        data_scaled = self.scalers[name].transform(data)
                    else:
                        data_scaled = data

                    # Prédiction
                    pred = predictor.predict(data_scaled)
                    predictions.append(pred)

                    # Confiance si disponible
                    if hasattr(predictor, 'predict_proba'):
                        conf = predictor.predict_proba(data_scaled)
                        confidences.append(conf)

                except Exception as e:
                    logger.error(f"Erreur avec prédicteur {name}: {e}")
                    continue

            if not predictions:
                raise RuntimeError("Aucune prédiction disponible")

            # Agrégation
            final_pred = np.mean(predictions, axis=0)
            final_conf = np.mean(confidences, axis=0) if confidences else None

            # Postprocessing
            final_pred = self._postprocess(final_pred)

            # Résultat
            result.predictions = final_pred
            result.confidence = final_conf
            result.metadata = {
                'n_predictors': len(predictions),
                'predictors': list(self.predictors.keys())
            }
            result.processing_time = time.time() - start_time
            result.success = True

            # Cache
            if self.config.use_cache:
                self._cache[cache_key] = {
                    'predictions': final_pred,
                    'confidence': final_conf,
                    'metadata': result.metadata,
                    'timestamp': datetime.now(),
                }

            # Sauvegarde intermédiaire
            self._save_intermediate(task.id, result)

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(f"Erreur de traitement task {task.id}: {e}")

        return result

    def _worker_loop(self):
        """Boucle de travailleur"""
        while self._running:
            try:
                # Récupération de la tâche
                priority, task = self._queue.get(timeout=1)

                # Traitement
                result = self._process_task(task)

                # Enregistrement
                with self._lock:
                    self._results[task.id] = result
                    self._stats['completed'] += 1
                    if result.success:
                        self._stats['total_tasks'] += 1
                    else:
                        self._stats['failed'] += 1

                logger.debug(f"Task {task.id} terminée")

            except Exception as e:
                if self._running:
                    logger.error(f"Erreur worker: {e}")

    def start(self):
        """Démarre le pipeline"""
        if self._running:
            logger.warning("Pipeline déjà en cours")
            return

        self._running = True

        # Création des workers
        for i in range(self.config.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"worker_{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"Pipeline démarré avec {self.config.num_workers} workers")

    def stop(self):
        """Arrête le pipeline"""
        self._running = False

        # Attente des workers
        for worker in self._workers:
            worker.join(timeout=5)

        self._workers.clear()
        logger.info("Pipeline arrêté")

    def predict(
        self,
        data: Any,
        task_id: Optional[str] = None,
        priority: int = 0,
        wait: bool = True,
        timeout: Optional[int] = None
    ) -> Optional[PredictionResult]:
        """
        Soumet une tâche de prédiction.

        Args:
            data: Données à prédire
            task_id: ID de la tâche (généré si None)
            priority: Priorité (plus élevé = plus important)
            wait: Attendre le résultat
            timeout: Timeout en secondes

        Returns:
            Optional[PredictionResult]: Résultat de la prédiction
        """
        if task_id is None:
            task_id = f"task_{datetime.now().timestamp()}_{id(data)}"

        task = PredictionTask(
            id=task_id,
            data=data,
            timestamp=datetime.now(),
            priority=priority
        )

        # Mise en file
        self._queue.put((-priority, task))

        with self._lock:
            self._stats['total_tasks'] += 1

        if wait:
            # Attente du résultat
            start = time.time()
            timeout = timeout or self.config.timeout

            while time.time() - start < timeout:
                if task_id in self._results:
                    result = self._results.pop(task_id)
                    return result
                time.sleep(0.1)

            logger.warning(f"Timeout pour task {task_id}")
            return None

        return None

    def predict_batch(
        self,
        data_list: List[Any],
        priority: int = 0,
        wait: bool = True
    ) -> List[Optional[PredictionResult]]:
        """
        Soumet un batch de tâches de prédiction.

        Args:
            data_list: Liste des données à prédire
            priority: Priorité par défaut
            wait: Attendre les résultats

        Returns:
            List[Optional[PredictionResult]]: Résultats des prédictions
        """
        results = []

        for i, data in enumerate(data_list):
            task_id = f"batch_{datetime.now().timestamp()}_{i}"
            result = self.predict(data, task_id, priority, wait)
            results.append(result)

        return results

    def get_result(self, task_id: str) -> Optional[PredictionResult]:
        """Récupère un résultat par ID"""
        with self._lock:
            return self._results.get(task_id)

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du pipeline"""
        stats = self._stats.copy()
        stats.update({
            'queue_size': self._queue.qsize(),
            'num_predictors': len(self.predictors),
            'num_workers': len(self._workers),
            'cache_size': len(self._cache),
            'is_running': self._running,
        })
        return stats

    def clear_cache(self):
        """Vide le cache"""
        with self._lock:
            self._cache.clear()
        logger.info("Cache vidé")

    def clear_results(self):
        """Vide les résultats"""
        with self._lock:
            self._results.clear()
        logger.info("Résultats vidés")

    def get_predictors(self) -> List[str]:
        """Retourne la liste des prédicteurs"""
        return list(self.predictors.keys())

    def remove_predictor(self, name: str) -> bool:
        """Supprime un prédicteur"""
        if name in self.predictors:
            del self.predictors[name]
            if name in self.scalers:
                del self.scalers[name]
            logger.info(f"Prédicteur '{name}' supprimé")
            return True
        return False

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le pipeline.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'predictors': self.predictors,
                'scalers': self.scalers,
                'stats': self._stats,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Pipeline sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'PredictionPipeline':
        """
        Charge un pipeline.

        Args:
            filepath: Chemin du fichier

        Returns:
            PredictionPipeline: Pipeline chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = PredictionPipelineConfig(**data['config'])
            pipeline = cls(config)

            pipeline.predictors = data.get('predictors', {})
            pipeline.scalers = data.get('scalers', {})
            pipeline._stats = data.get('stats', {})

            logger.info(f"Pipeline chargé: {filepath}")
            return pipeline

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_prediction_pipeline(
    name: str = "default_pipeline",
    batch_size: int = 64,
    num_workers: int = 4,
    **kwargs
) -> PredictionPipeline:
    """
    Factory pour créer un pipeline de prédiction.

    Args:
        name: Nom du pipeline
        batch_size: Taille du batch
        num_workers: Nombre de workers
        **kwargs: Arguments supplémentaires

    Returns:
        PredictionPipeline: Pipeline de prédiction
    """
    config = PredictionPipelineConfig(
        name=name,
        batch_size=batch_size,
        num_workers=num_workers,
        **kwargs
    )
    return PredictionPipeline(config)


__all__ = [
    'PredictionPipeline',
    'PredictionPipelineConfig',
    'PredictionTask',
    'PredictionResult',
    'create_prediction_pipeline',
]

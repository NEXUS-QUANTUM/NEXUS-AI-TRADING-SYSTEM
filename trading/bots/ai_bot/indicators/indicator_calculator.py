"""
NEXUS AI TRADING SYSTEM - Indicator Calculator for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/indicators/indicator_calculator.py
Description: Calculateur unifié d'indicateurs techniques pour le bot AI.
             Intègre tous les indicateurs standards et personnalisés,
             avec gestion du caching, de la parallélisation, et des
             dépendances entre indicateurs. Supporte le calcul batch
             et en temps réel avec optimisation des performances.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
import numpy as np
import pandas as pd

from trading.bots.ai_bot.indicators.base_indicator import (
    BaseIndicator,
    IndicatorConfig,
    IndicatorResult,
    IndicatorCategory,
    IndicatorType
)
from trading.bots.ai_bot.indicators.custom_indicators import (
    MarketSentimentIndicator,
    OrderFlowIndicator,
    MarketRegimeIndicator,
    CrossCorrelationIndicator,
    AdaptiveVolatilityIndicator,
    MarketCycleIndicator,
    AdvancedRSIIndicator,
    CustomIndicatorFactory
)
from trading.bots.ai_bot.indicators.indicator_cache import IndicatorCache, CacheConfig
from trading.bots.ai_bot.indicators.indicator_factory import IndicatorFactory
from shared.exceptions import IndicatorError
from shared.helpers.number_helpers import round_decimal

# Configuration du logging
logger = logging.getLogger(__name__)


class CalculationMode(Enum):
    """Modes de calcul."""
    SINGLE = "single"          # Calcul unique
    BATCH = "batch"            # Calcul par lot
    REALTIME = "realtime"      # Temps réel
    STREAMING = "streaming"    # Streaming continu
    ASYNC = "async"            # Asynchrone


class IndicatorPriority(Enum):
    """Priorités des indicateurs."""
    HIGH = "high"              # Haute priorité
    NORMAL = "normal"          # Priorité normale
    LOW = "low"                # Basse priorité
    BACKGROUND = "background"  # Arrière-plan


@dataclass
class CalculatorConfig:
    """
    Configuration du calculateur d'indicateurs.
    """
    # Mode de calcul
    mode: CalculationMode = CalculationMode.SINGLE
    
    # Parallélisation
    parallel: bool = True
    max_workers: int = 4
    use_process_pool: bool = False
    
    # Caching
    cache_enabled: bool = True
    cache_ttl: int = 3600
    cache_backend: str = "memory"
    
    # Performance
    batch_size: int = 100
    max_queue_size: int = 1000
    timeout: float = 30.0
    
    # Dépendances
    resolve_dependencies: bool = True
    max_dependency_depth: int = 5
    
    # Monitoring
    enable_monitoring: bool = True
    log_performance: bool = False
    save_metrics: bool = True
    
    # Réglages avancés
    fallback_on_error: bool = True
    retry_on_error: bool = True
    max_retries: int = 3
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.max_workers < 1:
            raise IndicatorError("max_workers doit être >= 1")
        
        if self.batch_size < 1:
            raise IndicatorError("batch_size doit être >= 1")
        
        if self.max_queue_size < 1:
            raise IndicatorError("max_queue_size doit être >= 1")


@dataclass
class IndicatorDependency:
    """
    Dépendance entre indicateurs.
    """
    indicator_name: str
    depends_on: List[str] = field(default_factory=list)
    priority: IndicatorPriority = IndicatorPriority.NORMAL
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'indicator_name': self.indicator_name,
            'depends_on': self.depends_on,
            'priority': self.priority.value
        }


@dataclass
class CalculationResult:
    """
    Résultat du calcul d'indicateurs.
    """
    # Résultats
    results: Dict[str, IndicatorResult] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    
    # Métadonnées
    total_time: float = 0.0
    indicator_count: int = 0
    successful_count: int = 0
    failed_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'results': {k: v.to_dict() for k, v in self.results.items()},
            'errors': self.errors,
            'total_time': round(self.total_time, 4),
            'indicator_count': self.indicator_count,
            'successful_count': self.successful_count,
            'failed_count': self.failed_count,
            'timestamp': self.timestamp.isoformat()
        }
    
    def is_successful(self) -> bool:
        """Vérifie si tous les indicateurs ont réussi."""
        return self.failed_count == 0
    
    def get_result(self, name: str) -> Optional[IndicatorResult]:
        """Récupère un résultat par nom."""
        return self.results.get(name)


class IndicatorCalculator:
    """
    Calculateur unifié d'indicateurs techniques.
    """
    
    def __init__(self, config: Optional[CalculatorConfig] = None):
        """
        Initialise le calculateur d'indicateurs.
        
        Args:
            config: Configuration du calculateur.
        """
        self.config = config or CalculatorConfig()
        
        # Cache
        cache_config = CacheConfig(
            backend=self.config.cache_backend,
            ttl=self.config.cache_ttl
        )
        self.cache = IndicatorCache(cache_config) if self.config.cache_enabled else None
        
        # Fabriques
        self.factory = IndicatorFactory()
        self.custom_factory = CustomIndicatorFactory()
        
        # Dépendances
        self._dependencies: Dict[str, IndicatorDependency] = {}
        self._dependency_graph: Dict[str, List[str]] = {}
        
        # Thread pools
        self._thread_pool = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._process_pool = ProcessPoolExecutor(max_workers=self.config.max_workers) if self.config.use_process_pool else None
        
        # Statistiques
        self._stats = {
            'total_calculations': 0,
            'total_indicator_calculations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'avg_calculation_time': 0.0
        }
        
        # État
        self._running = False
        self._lock = threading.Lock()
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_calculation_start': [],
            'on_calculation_complete': [],
            'on_indicator_complete': [],
            'on_error': []
        }
        
        logger.info("IndicatorCalculator initialisé")
        logger.info(f"Mode: {self.config.mode.value}")
        logger.info(f"Cache: {'Activé' if self.config.cache_enabled else 'Désactivé'}")
        logger.info(f"Workers: {self.config.max_workers}")
    
    # ============================================================
    # GESTION DES INDICATEURS
    # ============================================================
    
    def register_indicator(
        self,
        indicator_class: type,
        name: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        priority: IndicatorPriority = IndicatorPriority.NORMAL
    ) -> None:
        """
        Enregistre un indicateur.
        
        Args:
            indicator_class: Classe de l'indicateur.
            name: Nom de l'indicateur.
            dependencies: Dépendances.
            priority: Priorité.
        """
        indicator_name = name or indicator_class.__name__
        
        # Enregistrement dans la fabrique
        self.factory.register(indicator_name, indicator_class)
        
        # Dépendances
        if dependencies:
            self._dependencies[indicator_name] = IndicatorDependency(
                indicator_name=indicator_name,
                depends_on=dependencies,
                priority=priority
            )
            self._dependency_graph[indicator_name] = dependencies
        
        logger.info(f"Indicateur enregistré: {indicator_name}")
    
    def register_custom_indicator(
        self,
        name: str,
        indicator_class: type,
        dependencies: Optional[List[str]] = None,
        priority: IndicatorPriority = IndicatorPriority.NORMAL
    ) -> None:
        """
        Enregistre un indicateur personnalisé.
        
        Args:
            name: Nom de l'indicateur.
            indicator_class: Classe de l'indicateur.
            dependencies: Dépendances.
            priority: Priorité.
        """
        self.custom_factory.register(name, indicator_class)
        
        if dependencies:
            self._dependencies[name] = IndicatorDependency(
                indicator_name=name,
                depends_on=dependencies,
                priority=priority
            )
            self._dependency_graph[name] = dependencies
        
        logger.info(f"Indicateur personnalisé enregistré: {name}")
    
    def get_available_indicators(self) -> List[str]:
        """
        Retourne la liste des indicateurs disponibles.
        
        Returns:
            Liste des noms d'indicateurs.
        """
        std = self.factory.get_available()
        custom = self.custom_factory.get_available()
        return list(set(std + custom))
    
    # ============================================================
    # CALCUL DES INDICATEURS
    # ============================================================
    
    def calculate(
        self,
        data: pd.DataFrame,
        indicator_names: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> CalculationResult:
        """
        Calcule les indicateurs.
        
        Args:
            data: Données OHLCV.
            indicator_names: Liste des indicateurs (None = tous).
            params: Paramètres supplémentaires.
            use_cache: Utiliser le cache.
            force_refresh: Forcer le rafraîchissement.
            
        Returns:
            Résultat du calcul.
        """
        start_time = time.time()
        
        # Notification
        self._notify_callbacks('on_calculation_start', {
            'indicator_count': len(indicator_names) if indicator_names else len(self.get_available_indicators())
        })
        
        # Validation des données
        if data is None or data.empty:
            raise IndicatorError("Données vides")
        
        # Sélection des indicateurs
        if indicator_names is None:
            indicator_names = self.get_available_indicators()
        
        # Résolution des dépendances
        if self.config.resolve_dependencies:
            indicator_names = self._resolve_dependencies(indicator_names)
        
        logger.info(f"Calcul de {len(indicator_names)} indicateurs")
        
        result = CalculationResult()
        result.indicator_count = len(indicator_names)
        
        # Calcul
        if self.config.mode == CalculationMode.SINGLE:
            results, errors = self._calculate_single(data, indicator_names, params, use_cache, force_refresh)
        elif self.config.mode == CalculationMode.BATCH:
            results, errors = self._calculate_batch(data, indicator_names, params, use_cache, force_refresh)
        elif self.config.mode == CalculationMode.ASYNC:
            loop = asyncio.get_event_loop()
            results, errors = loop.run_until_complete(
                self._calculate_async(data, indicator_names, params, use_cache, force_refresh)
            )
        else:
            results, errors = self._calculate_single(data, indicator_names, params, use_cache, force_refresh)
        
        # Mise à jour du résultat
        result.results = results
        result.errors = errors
        result.successful_count = len(results)
        result.failed_count = len(errors)
        result.total_time = time.time() - start_time
        
        # Statistiques
        self._stats['total_calculations'] += 1
        self._stats['total_indicator_calculations'] += len(indicator_names)
        self._stats['avg_calculation_time'] = (
            self._stats['avg_calculation_time'] * (self._stats['total_calculations'] - 1) +
            result.total_time
        ) / self._stats['total_calculations']
        
        # Notification
        self._notify_callbacks('on_calculation_complete', result.to_dict())
        
        logger.info(f"Calcul terminé: {result.successful_count} succès, {result.failed_count} échecs")
        
        return result
    
    def _calculate_single(
        self,
        data: pd.DataFrame,
        indicator_names: List[str],
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Tuple[Dict[str, IndicatorResult], Dict[str, str]]:
        """
        Calcule les indicateurs en mode unique.
        
        Returns:
            Tuple (résultats, erreurs).
        """
        results = {}
        errors = {}
        params = params or {}
        
        for name in indicator_names:
            try:
                start_time = time.time()
                
                # Vérification du cache
                if use_cache and self.cache and not force_refresh:
                    cached = self._get_from_cache(name, data, params)
                    if cached:
                        results[name] = cached
                        self._stats['cache_hits'] += 1
                        continue
                
                # Création de l'indicateur
                indicator = self._create_indicator(name, params.get(name, {}))
                
                # Vérification des dépendances
                if name in self._dependencies:
                    deps = self._dependencies[name].depends_on
                    for dep in deps:
                        if dep not in results:
                            raise IndicatorError(f"Dépendance non satisfaite: {dep}")
                
                # Calcul
                indicator_result = indicator.calculate(data, params.get(name, {}))
                
                # Stockage
                results[name] = indicator_result
                
                # Mise en cache
                if use_cache and self.cache:
                    self._save_to_cache(name, data, indicator_result, params)
                
                # Notification
                self._notify_callbacks('on_indicator_complete', {
                    'name': name,
                    'time': time.time() - start_time,
                    'success': True
                })
                
                self._stats['total_indicator_calculations'] += 1
                
            except Exception as e:
                error_msg = f"Erreur pour {name}: {e}"
                logger.error(error_msg)
                errors[name] = str(e)
                self._stats['errors'] += 1
                
                if not self.config.fallback_on_error:
                    raise
                
                self._notify_callbacks('on_error', {
                    'name': name,
                    'error': str(e)
                })
        
        return results, errors
    
    def _calculate_batch(
        self,
        data: pd.DataFrame,
        indicator_names: List[str],
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Tuple[Dict[str, IndicatorResult], Dict[str, str]]:
        """
        Calcule les indicateurs en mode batch.
        
        Returns:
            Tuple (résultats, erreurs).
        """
        results = {}
        errors = {}
        
        # Tri par priorité
        sorted_names = self._sort_by_priority(indicator_names)
        
        # Calcul par lots
        for i in range(0, len(sorted_names), self.config.batch_size):
            batch = sorted_names[i:i + self.config.batch_size]
            batch_results, batch_errors = self._calculate_batch_parallel(
                data, batch, params, use_cache, force_refresh
            )
            results.update(batch_results)
            errors.update(batch_errors)
        
        return results, errors
    
    def _calculate_batch_parallel(
        self,
        data: pd.DataFrame,
        indicator_names: List[str],
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Tuple[Dict[str, IndicatorResult], Dict[str, str]]:
        """
        Calcule un lot d'indicateurs en parallèle.
        
        Returns:
            Tuple (résultats, erreurs).
        """
        if not self.config.parallel:
            return self._calculate_single(data, indicator_names, params, use_cache, force_refresh)
        
        results = {}
        errors = {}
        futures = []
        
        # Soumission des tâches
        for name in indicator_names:
            if self.config.use_process_pool and self._process_pool:
                future = self._process_pool.submit(
                    self._calculate_single_indicator,
                    data, name, params, use_cache, force_refresh
                )
            else:
                future = self._thread_pool.submit(
                    self._calculate_single_indicator,
                    data, name, params, use_cache, force_refresh
                )
            futures.append((name, future))
        
        # Récupération des résultats
        for name, future in futures:
            try:
                result = future.result(timeout=self.config.timeout)
                if result is not None:
                    results[name] = result
                else:
                    errors[name] = "Aucun résultat"
            except Exception as e:
                errors[name] = str(e)
                self._stats['errors'] += 1
        
        return results, errors
    
    def _calculate_single_indicator(
        self,
        data: pd.DataFrame,
        name: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Optional[IndicatorResult]:
        """
        Calcule un seul indicateur (pour parallélisation).
        
        Returns:
            Résultat de l'indicateur ou None.
        """
        try:
            start_time = time.time()
            
            # Vérification du cache
            if use_cache and self.cache and not force_refresh:
                cached = self._get_from_cache(name, data, params)
                if cached:
                    self._stats['cache_hits'] += 1
                    return cached
            
            # Création de l'indicateur
            indicator = self._create_indicator(name, params.get(name, {}) if params else {})
            
            # Calcul
            result = indicator.calculate(data, params.get(name, {}) if params else {})
            
            # Mise en cache
            if use_cache and self.cache:
                self._save_to_cache(name, data, result, params)
            
            self._stats['cache_misses'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur pour {name}: {e}")
            return None
    
    async def _calculate_async(
        self,
        data: pd.DataFrame,
        indicator_names: List[str],
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Tuple[Dict[str, IndicatorResult], Dict[str, str]]:
        """
        Calcule les indicateurs de manière asynchrone.
        
        Returns:
            Tuple (résultats, erreurs).
        """
        results = {}
        errors = {}
        
        # Création des tâches
        tasks = []
        for name in indicator_names:
            task = asyncio.create_task(
                self._calculate_async_single(
                    data, name, params, use_cache, force_refresh
                )
            )
            tasks.append((name, task))
        
        # Attente des résultats
        for name, task in tasks:
            try:
                result = await task
                if result is not None:
                    results[name] = result
                else:
                    errors[name] = "Aucun résultat"
            except Exception as e:
                errors[name] = str(e)
        
        return results, errors
    
    async def _calculate_async_single(
        self,
        data: pd.DataFrame,
        name: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Optional[IndicatorResult]:
        """
        Calcule un indicateur de manière asynchrone.
        
        Returns:
            Résultat de l'indicateur ou None.
        """
        loop = asyncio.get_event_loop()
        
        try:
            # Exécution dans un thread pool
            result = await loop.run_in_executor(
                self._thread_pool,
                self._calculate_single_indicator,
                data, name, params, use_cache, force_refresh
            )
            return result
            
        except Exception as e:
            logger.error(f"Erreur asynchrone pour {name}: {e}")
            return None
    
    # ============================================================
    # GESTION DU CACHE
    # ============================================================
    
    def _get_from_cache(
        self,
        name: str,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[IndicatorResult]:
        """
        Récupère un résultat du cache.
        
        Returns:
            Résultat ou None.
        """
        if not self.cache:
            return None
        
        data_hash = self._hash_data(data)
        return self.cache.get(name, self.config.symbol, self.config.timeframe, data_hash, params)
    
    def _save_to_cache(
        self,
        name: str,
        data: pd.DataFrame,
        result: IndicatorResult,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Sauvegarde un résultat dans le cache.
        
        Args:
            name: Nom de l'indicateur.
            data: Données.
            result: Résultat.
            params: Paramètres.
        """
        if not self.cache:
            return
        
        data_hash = self._hash_data(data)
        self.cache.set(name, self.config.symbol, self.config.timeframe, data_hash, result, params)
    
    def _hash_data(self, data: pd.DataFrame) -> str:
        """
        Génère un hash des données.
        
        Args:
            data: Données.
            
        Returns:
            Hash des données.
        """
        return hashlib.md5(data.to_json().encode()).hexdigest()
    
    # ============================================================
    # GESTION DES DÉPENDANCES
    # ============================================================
    
    def _resolve_dependencies(self, indicator_names: List[str]) -> List[str]:
        """
        Résout les dépendances entre indicateurs.
        
        Args:
            indicator_names: Liste des indicateurs.
            
        Returns:
            Liste ordonnée des indicateurs.
        """
        resolved = []
        graph = self._dependency_graph.copy()
        
        # Tri topologique
        def resolve(name: str, visited: set):
            if name in visited:
                return
            visited.add(name)
            
            if name in graph:
                for dep in graph[name]:
                    if dep in indicator_names:
                        resolve(dep, visited)
            
            if name not in resolved:
                resolved.append(name)
        
        # Résolution
        visited = set()
        for name in indicator_names:
            resolve(name, visited)
        
        return resolved
    
    def _sort_by_priority(self, indicator_names: List[str]) -> List[str]:
        """
        Trie les indicateurs par priorité.
        
        Args:
            indicator_names: Liste des indicateurs.
            
        Returns:
            Liste triée.
        """
        priority_order = {
            IndicatorPriority.HIGH: 0,
            IndicatorPriority.NORMAL: 1,
            IndicatorPriority.LOW: 2,
            IndicatorPriority.BACKGROUND: 3
        }
        
        def get_priority(name: str) -> int:
            if name in self._dependencies:
                return priority_order.get(self._dependencies[name].priority, 1)
            return 1
        
        return sorted(indicator_names, key=get_priority)
    
    # ============================================================
    # CRÉATION D'INDICATEURS
    # ============================================================
    
    def _create_indicator(self, name: str, params: Dict[str, Any]) -> BaseIndicator:
        """
        Crée un indicateur.
        
        Args:
            name: Nom de l'indicateur.
            params: Paramètres.
            
        Returns:
            Instance de l'indicateur.
        """
        # Essayer d'abord la fabrique personnalisée
        try:
            return self.custom_factory.create(name, self.config.symbol, self.config.timeframe, **params)
        except:
            pass
        
        # Essayer la fabrique standard
        try:
            return self.factory.create(name, self.config.symbol, self.config.timeframe, **params)
        except:
            pass
        
        raise IndicatorError(f"Indicateur inconnu: {name}")
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du calculateur.
        
        Returns:
            Statistiques.
        """
        cache_stats = self.cache.get_stats() if self.cache else {}
        
        return {
            **self._stats,
            'cache': cache_stats,
            'indicator_count': len(self.get_available_indicators()),
            'dependency_count': len(self._dependencies),
            'mode': self.config.mode.value,
            'parallel': self.config.parallel
        }
    
    def clear_cache(self) -> None:
        """
        Vide le cache.
        """
        if self.cache:
            self.cache.clear()
            logger.info("Cache vidé")
    
    def reset(self) -> None:
        """
        Réinitialise le calculateur.
        """
        self._stats = {
            'total_calculations': 0,
            'total_indicator_calculations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'avg_calculation_time': 0.0
        }
        self.clear_cache()
        logger.info("Calculateur réinitialisé")
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on_calculation_start(self, callback: Callable) -> None:
        """Ajoute un callback pour le début du calcul."""
        self._callbacks['on_calculation_start'].append(callback)
    
    def on_calculation_complete(self, callback: Callable) -> None:
        """Ajoute un callback pour la fin du calcul."""
        self._callbacks['on_calculation_complete'].append(callback)
    
    def on_indicator_complete(self, callback: Callable) -> None:
        """Ajoute un callback pour la fin d'un indicateur."""
        self._callbacks['on_indicator_complete'].append(callback)
    
    def on_error(self, callback: Callable) -> None:
        """Ajoute un callback pour les erreurs."""
        self._callbacks['on_error'].append(callback)
    
    def _notify_callbacks(self, event: str, data: Any) -> None:
        """
        Notifie les callbacks.
        
        Args:
            event: Nom de l'événement.
            data: Données.
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Erreur dans le callback {event}: {e}")
    
    # ============================================================
    # GESTION DU CYCLE DE VIE
    # ============================================================
    
    def start(self) -> None:
        """Démarre le calculateur."""
        if self._running:
            return
        
        self._running = True
        logger.info("Calculateur démarré")
    
    def stop(self) -> None:
        """Arrête le calculateur."""
        self._running = False
        
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
        
        if self._process_pool:
            self._process_pool.shutdown(wait=True)
        
        if self.cache:
            self.cache.close()
        
        logger.info("Calculateur arrêté")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_indicator_calculator(
    mode: str = "single",
    parallel: bool = True,
    max_workers: int = 4,
    **kwargs
) -> IndicatorCalculator:
    """
    Crée un calculateur d'indicateurs.
    
    Args:
        mode: Mode de calcul.
        parallel: Paralléliser.
        max_workers: Nombre de workers.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du calculateur.
    """
    mode_map = {
        'single': CalculationMode.SINGLE,
        'batch': CalculationMode.BATCH,
        'realtime': CalculationMode.REALTIME,
        'streaming': CalculationMode.STREAMING,
        'async': CalculationMode.ASYNC
    }
    
    config = CalculatorConfig(
        mode=mode_map.get(mode, CalculationMode.SINGLE),
        parallel=parallel,
        max_workers=max_workers,
        **kwargs
    )
    
    return IndicatorCalculator(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'IndicatorCalculator',
    'CalculatorConfig',
    'CalculationResult',
    'CalculationMode',
    'IndicatorPriority',
    'IndicatorDependency',
    'create_indicator_calculator'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

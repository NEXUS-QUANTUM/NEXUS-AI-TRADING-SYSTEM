"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Retry Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de retry pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import time
import random
import functools
import logging
import inspect
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    Tuple,
    Coroutine,
    Awaitable,
    Iterator,
    AsyncIterator,
    ContextManager,
    AsyncContextManager
)
from enum import Enum
from dataclasses import dataclass, field
from contextlib import contextmanager, asynccontextmanager

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')

# ============================================================
# ENUMS
# ============================================================

class RetryStrategy(Enum):
    """Stratégies de retry"""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"
    FULL_JITTER = "full_jitter"
    EQUAL_JITTER = "equal_jitter"
    DECORRELATED_JITTER = "decorrelated_jitter"
    RANDOM = "random"

class RetryResult(Enum):
    """Résultats de retry"""
    SUCCESS = "success"
    RETRY = "retry"
    FAILURE = "failure"
    SKIP = "skip"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class RetryConfig:
    """Configuration de retry"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.5
    timeout: Optional[float] = None
    retry_on: Tuple[Type[Exception], ...] = (Exception,)
    retry_on_result: Optional[Callable[[Any], bool]] = None
    max_retries_per_minute: Optional[int] = None
    max_retries_per_hour: Optional[int] = None
    log_retries: bool = True
    log_level: int = logging.WARNING
    raise_on_timeout: bool = True
    
class RetryContext:
    """Contexte de retry"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.attempt = 0
        self.start_time = time.time()
        self.last_error: Optional[Exception] = None
        self.last_result: Optional[Any] = None
        self.delays: List[float] = []
        self.success = False
        self.final_attempt = False
        self.should_retry = True
    
    @property
    def elapsed(self) -> float:
        """Temps écoulé depuis le début"""
        return time.time() - self.start_time
    
    @property
    def remaining_timeout(self) -> Optional[float]:
        """Temps restant avant timeout"""
        if self.config.timeout is None:
            return None
        remaining = self.config.timeout - self.elapsed
        return max(0, remaining)
    
    def next_delay(self) -> float:
        """
        Calcule le prochain délai
        
        Returns:
            float: Délai en secondes
        """
        self.attempt += 1
        
        if self.attempt == 1:
            return 0.0
        
        # Calculer le délai de base
        if self.config.strategy == RetryStrategy.FIXED:
            delay = self.config.initial_delay
        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.initial_delay * self.attempt
        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.initial_delay * (self.config.backoff_multiplier ** (self.attempt - 1))
        elif self.config.strategy in [RetryStrategy.EXPONENTIAL_JITTER, RetryStrategy.FULL_JITTER]:
            base = self.config.initial_delay * (self.config.backoff_multiplier ** (self.attempt - 1))
            delay = random.uniform(0, base)
        elif self.config.strategy == RetryStrategy.EQUAL_JITTER:
            base = self.config.initial_delay * (self.config.backoff_multiplier ** (self.attempt - 1))
            delay = (base / 2) + random.uniform(0, base / 2)
        elif self.config.strategy == RetryStrategy.DECORRELATED_JITTER:
            if self.attempt == 1:
                delay = self.config.initial_delay
            else:
                previous_delay = self.delays[-1] if self.delays else self.config.initial_delay
                base = previous_delay * self.config.backoff_multiplier
                delay = random.uniform(self.config.initial_delay, base)
        elif self.config.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(0, self.config.max_delay)
        else:
            delay = self.config.initial_delay * (self.config.backoff_multiplier ** (self.attempt - 1))
        
        # Appliquer le jitter si nécessaire
        if self.config.jitter and self.config.strategy not in [
            RetryStrategy.FULL_JITTER,
            RetryStrategy.EQUAL_JITTER,
            RetryStrategy.DECORRELATED_JITTER,
            RetryStrategy.EXPONENTIAL_JITTER
        ]:
            jitter_range = delay * self.config.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
        
        # Limiter le délai maximum
        delay = min(delay, self.config.max_delay)
        
        # S'assurer que le délai est positif
        delay = max(delay, 0.001)
        
        self.delays.append(delay)
        return delay

# ============================================================
# RETRY DECORATOR
# ============================================================

def retry(config: Optional[RetryConfig] = None) -> Callable:
    """
    Décorateur de retry pour les fonctions synchrones
    
    Args:
        config: Configuration de retry
        
    Returns:
        Callable: Décorateur
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> R:
            context = RetryContext(config)
            
            while context.should_retry:
                try:
                    # Vérifier le timeout
                    if context.config.timeout is not None:
                        if context.elapsed >= context.config.timeout:
                            if context.config.raise_on_timeout:
                                raise TimeoutError(
                                    f"Function {func.__name__} timed out after {context.config.timeout}s"
                                )
                            else:
                                break
                    
                    # Exécuter la fonction
                    result = func(*args, **kwargs)
                    context.last_result = result
                    
                    # Vérifier le résultat
                    if context.config.retry_on_result is not None:
                        if context.config.retry_on_result(result):
                            context.last_error = ValueError("Result validation failed")
                            raise context.last_error
                    
                    context.success = True
                    context.should_retry = False
                    return result
                    
                except context.config.retry_on as e:
                    context.last_error = e
                    context.attempt += 1
                    
                    # Vérifier les limites
                    if context.attempt >= context.config.max_attempts:
                        context.final_attempt = True
                        context.should_retry = False
                        raise
                    
                    # Vérifier les limites par minute/heure
                    if context.config.max_retries_per_minute is not None:
                        # Implémenter le rate limiting
                        pass
                    
                    # Log
                    if context.config.log_retries:
                        logger.log(
                            context.config.log_level,
                            f"Retry {context.attempt}/{context.config.max_attempts} "
                            f"for {func.__name__}: {e}"
                        )
                    
                    # Attendre
                    delay = context.next_delay()
                    time.sleep(delay)
            
            # Si on arrive ici, c'est un échec
            if context.last_error:
                raise context.last_error
            return context.last_result
        
        return wrapper
    
    return decorator

def retry_async(config: Optional[RetryConfig] = None) -> Callable:
    """
    Décorateur de retry pour les fonctions asynchrones
    
    Args:
        config: Configuration de retry
        
    Returns:
        Callable: Décorateur
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., Coroutine[Any, Any, R]]) -> Callable[..., Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> R:
            context = RetryContext(config)
            
            while context.should_retry:
                try:
                    # Vérifier le timeout
                    if context.config.timeout is not None:
                        if context.elapsed >= context.config.timeout:
                            if context.config.raise_on_timeout:
                                raise TimeoutError(
                                    f"Function {func.__name__} timed out after {context.config.timeout}s"
                                )
                            else:
                                break
                    
                    # Exécuter la fonction
                    result = await func(*args, **kwargs)
                    context.last_result = result
                    
                    # Vérifier le résultat
                    if context.config.retry_on_result is not None:
                        if context.config.retry_on_result(result):
                            context.last_error = ValueError("Result validation failed")
                            raise context.last_error
                    
                    context.success = True
                    context.should_retry = False
                    return result
                    
                except context.config.retry_on as e:
                    context.last_error = e
                    context.attempt += 1
                    
                    # Vérifier les limites
                    if context.attempt >= context.config.max_attempts:
                        context.final_attempt = True
                        context.should_retry = False
                        raise
                    
                    # Log
                    if context.config.log_retries:
                        logger.log(
                            context.config.log_level,
                            f"Retry {context.attempt}/{context.config.max_attempts} "
                            f"for {func.__name__}: {e}"
                        )
                    
                    # Attendre
                    delay = context.next_delay()
                    await asyncio.sleep(delay)
            
            # Si on arrive ici, c'est un échec
            if context.last_error:
                raise context.last_error
            return context.last_result
        
        return wrapper
    
    return decorator

# ============================================================
# RETRY ITERATOR
# ============================================================

class RetryIterator:
    """
    Itérateur de retry
    
    Permet de réessayer une opération jusqu'à ce qu'elle réussisse
    """
    
    def __init__(
        self,
        func: Callable[[], Any],
        config: Optional[RetryConfig] = None,
        max_attempts: Optional[int] = None
    ):
        """
        Initialise l'itérateur
        
        Args:
            func: Fonction à exécuter
            config: Configuration de retry
            max_attempts: Nombre maximum de tentatives
        """
        self.func = func
        self.config = config or RetryConfig()
        if max_attempts is not None:
            self.config.max_attempts = max_attempts
        
        self.context = RetryContext(self.config)
        self.context.attempt = 0
        self._done = False
        self._result = None
        self._error = None
    
    def __iter__(self):
        return self
    
    def __next__(self) -> Any:
        """
        Tente la prochaine exécution
        
        Returns:
            Any: Résultat de la fonction
            
        Raises:
            StopIteration: Si terminé
        """
        if self._done:
            raise StopIteration
        
        try:
            result = self.func()
            self._result = result
            self._done = True
            return result
            
        except Exception as e:
            self._error = e
            self.context.attempt += 1
            
            if self.context.attempt >= self.config.max_attempts:
                self._done = True
                raise
            
            delay = self.context.next_delay()
            time.sleep(delay)
            return self.__next__()

class AsyncRetryIterator:
    """
    Itérateur de retry asynchrone
    
    Permet de réessayer une opération asynchrone jusqu'à ce qu'elle réussisse
    """
    
    def __init__(
        self,
        func: Callable[[], Coroutine[Any, Any, Any]],
        config: Optional[RetryConfig] = None,
        max_attempts: Optional[int] = None
    ):
        """
        Initialise l'itérateur
        
        Args:
            func: Fonction asynchrone à exécuter
            config: Configuration de retry
            max_attempts: Nombre maximum de tentatives
        """
        self.func = func
        self.config = config or RetryConfig()
        if max_attempts is not None:
            self.config.max_attempts = max_attempts
        
        self.context = RetryContext(self.config)
        self.context.attempt = 0
        self._done = False
        self._result = None
        self._error = None
    
    def __aiter__(self):
        return self
    
    async def __anext__(self) -> Any:
        """
        Tente la prochaine exécution asynchrone
        
        Returns:
            Any: Résultat de la fonction
            
        Raises:
            StopAsyncIteration: Si terminé
        """
        if self._done:
            raise StopAsyncIteration
        
        try:
            result = await self.func()
            self._result = result
            self._done = True
            return result
            
        except Exception as e:
            self._error = e
            self.context.attempt += 1
            
            if self.context.attempt >= self.config.max_attempts:
                self._done = True
                raise
            
            delay = self.context.next_delay()
            await asyncio.sleep(delay)
            return await self.__anext__()

# ============================================================
# RETRY CONTEXT MANAGER
# ============================================================

@contextmanager
def retry_context(config: Optional[RetryConfig] = None) -> Iterator[RetryContext]:
    """
    Context manager pour les retries
    
    Args:
        config: Configuration de retry
        
    Yields:
        RetryContext: Contexte de retry
    """
    config = config or RetryConfig()
    context = RetryContext(config)
    
    try:
        yield context
    except Exception as e:
        context.last_error = e
        context.attempt += 1
        raise

@asynccontextmanager
async def async_retry_context(config: Optional[RetryConfig] = None) -> AsyncIterator[RetryContext]:
    """
    Context manager asynchrone pour les retries
    
    Args:
        config: Configuration de retry
        
    Yields:
        RetryContext: Contexte de retry
    """
    config = config or RetryConfig()
    context = RetryContext(config)
    
    try:
        yield context
    except Exception as e:
        context.last_error = e
        context.attempt += 1
        raise

# ============================================================
# RETRY MANAGER
# ============================================================

class RetryManager:
    """
    Gestionnaire de retry
    
    Gère les opérations de retry avec état
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialise le gestionnaire
        
        Args:
            config: Configuration de retry
        """
        self.config = config or RetryConfig()
        self._context = RetryContext(self.config)
        self._stats = {
            'total_attempts': 0,
            'successful_attempts': 0,
            'failed_attempts': 0,
            'retried_attempts': 0,
            'timeouts': 0,
        }
        self._last_result: Optional[Any] = None
        self._last_error: Optional[Exception] = None
    
    def reset(self):
        """Réinitialise le gestionnaire"""
        self._context = RetryContext(self.config)
        self._last_result = None
        self._last_error = None
    
    def execute(self, func: Callable[[], Any]) -> Any:
        """
        Exécute une fonction avec retry
        
        Args:
            func: Fonction à exécuter
            
        Returns:
            Any: Résultat de la fonction
        """
        self.reset()
        
        while self._context.should_retry:
            try:
                self._stats['total_attempts'] += 1
                result = func()
                self._last_result = result
                self._stats['successful_attempts'] += 1
                self._context.success = True
                return result
                
            except Exception as e:
                self._stats['failed_attempts'] += 1
                self._last_error = e
                self._context.last_error = e
                self._context.attempt += 1
                
                if self._context.attempt >= self.config.max_attempts:
                    raise
                
                if self.config.timeout and self._context.elapsed >= self.config.timeout:
                    self._stats['timeouts'] += 1
                    if self.config.raise_on_timeout:
                        raise TimeoutError(f"Retry timed out after {self.config.timeout}s")
                    else:
                        break
                
                self._stats['retried_attempts'] += 1
                delay = self._context.next_delay()
                time.sleep(delay)
        
        return self._last_result
    
    async def execute_async(self, func: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        """
        Exécute une fonction asynchrone avec retry
        
        Args:
            func: Fonction asynchrone à exécuter
            
        Returns:
            Any: Résultat de la fonction
        """
        self.reset()
        
        while self._context.should_retry:
            try:
                self._stats['total_attempts'] += 1
                result = await func()
                self._last_result = result
                self._stats['successful_attempts'] += 1
                self._context.success = True
                return result
                
            except Exception as e:
                self._stats['failed_attempts'] += 1
                self._last_error = e
                self._context.last_error = e
                self._context.attempt += 1
                
                if self._context.attempt >= self.config.max_attempts:
                    raise
                
                if self.config.timeout and self._context.elapsed >= self.config.timeout:
                    self._stats['timeouts'] += 1
                    if self.config.raise_on_timeout:
                        raise TimeoutError(f"Retry timed out after {self.config.timeout}s")
                    else:
                        break
                
                self._stats['retried_attempts'] += 1
                delay = self._context.next_delay()
                await asyncio.sleep(delay)
        
        return self._last_result
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        return {
            **self._stats,
            'success_rate': self._stats['successful_attempts'] / self._stats['total_attempts']
            if self._stats['total_attempts'] > 0 else 0,
            'last_error': str(self._last_error) if self._last_error else None,
            'last_result': self._last_result,
            'attempts': self._context.attempt,
            'max_attempts': self.config.max_attempts,
        }

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'RetryStrategy',
    'RetryResult',
    
    # Data Classes
    'RetryConfig',
    'RetryContext',
    
    # Classes
    'RetryIterator',
    'AsyncRetryIterator',
    'RetryManager',
    
    # Décorateurs
    'retry',
    'retry_async',
    
    # Context Managers
    'retry_context',
    'async_retry_context',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Retry utilities module initialized")

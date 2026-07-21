"""
NEXUS AI TRADING SYSTEM - Hedge Bot Backoff Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de backoff et retry pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import time
import random
import functools
import logging
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
    Generator,
    Iterator,
    Coroutine,
    AsyncGenerator,
    AsyncIterator
)
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading

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
# BACKOFF STRATEGIES
# ============================================================

class BackoffStrategy(Enum):
    """Stratégies de backoff"""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    POLYNOMIAL = "polynomial"
    RANDOM = "random"
    FULL_JITTER = "full_jitter"
    EQUAL_JITTER = "equal_jitter"
    DECORRELATED_JITTER = "decorrelated_jitter"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class BackoffConfig:
    """Configuration de backoff"""
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.5
    max_attempts: int = 3
    retry_on: Tuple[Type[Exception], ...] = (Exception,)
    retry_on_result: Optional[Callable[[Any], bool]] = None
    timeout: Optional[float] = None
    raise_on_timeout: bool = True
    log_retries: bool = True
    log_level: int = logging.WARNING
    max_retries_per_minute: Optional[int] = None
    max_retries_per_hour: Optional[int] = None


@dataclass
class RetryContext:
    """Contexte de retry"""
    attempt: int = 0
    max_attempts: int = 3
    start_time: float = field(default_factory=time.time)
    last_error: Optional[Exception] = None
    last_result: Optional[Any] = None
    delays: List[float] = field(default_factory=list)
    success: bool = False
    final_attempt: bool = False
    should_retry: bool = True


# ============================================================
# BACKOFF CALCULATORS
# ============================================================

class BackoffCalculator:
    """
    Calculateur de délais de backoff
    
    Implémente différentes stratégies de backoff
    """
    
    @staticmethod
    def fixed_delay(base_delay: float, **kwargs) -> float:
        """
        Délai fixe
        
        Args:
            base_delay: Délai de base
            
        Returns:
            float: Délai
        """
        return base_delay
    
    @staticmethod
    def linear_delay(attempt: int, base_delay: float, **kwargs) -> float:
        """
        Délai linéaire
        
        Args:
            attempt: Numéro de tentative (0-indexé)
            base_delay: Délai de base
            
        Returns:
            float: Délai
        """
        return base_delay * (attempt + 1)
    
    @staticmethod
    def exponential_delay(attempt: int, base_delay: float, multiplier: float = 2.0, **kwargs) -> float:
        """
        Délai exponentiel
        
        Args:
            attempt: Numéro de tentative (0-indexé)
            base_delay: Délai de base
            multiplier: Multiplicateur exponentiel
            
        Returns:
            float: Délai
        """
        return base_delay * (multiplier ** attempt)
    
    @staticmethod
    def polynomial_delay(attempt: int, base_delay: float, degree: float = 2.0, **kwargs) -> float:
        """
        Délai polynomial
        
        Args:
            attempt: Numéro de tentative (0-indexé)
            base_delay: Délai de base
            degree: Degré du polynôme
            
        Returns:
            float: Délai
        """
        return base_delay * ((attempt + 1) ** degree)
    
    @staticmethod
    def random_delay(min_delay: float, max_delay: float, **kwargs) -> float:
        """
        Délai aléatoire
        
        Args:
            min_delay: Délai minimum
            max_delay: Délai maximum
            
        Returns:
            float: Délai
        """
        return random.uniform(min_delay, max_delay)
    
    @staticmethod
    def full_jitter(attempt: int, base_delay: float, multiplier: float = 2.0, **kwargs) -> float:
        """
        Jitter complet
        
        Args:
            attempt: Numéro de tentative (0-indexé)
            base_delay: Délai de base
            multiplier: Multiplicateur exponentiel
            
        Returns:
            float: Délai
        """
        base = base_delay * (multiplier ** attempt)
        return random.uniform(0, base)
    
    @staticmethod
    def equal_jitter(attempt: int, base_delay: float, multiplier: float = 2.0, **kwargs) -> float:
        """
        Jitter égal
        
        Args:
            attempt: Numéro de tentative (0-indexé)
            base_delay: Délai de base
            multiplier: Multiplicateur exponentiel
            
        Returns:
            float: Délai
        """
        base = base_delay * (multiplier ** attempt)
        return (base / 2) + random.uniform(0, base / 2)
    
    @staticmethod
    def decorrelated_jitter(
        attempt: int,
        base_delay: float,
        multiplier: float = 2.0,
        previous_delay: float = 0.0,
        **kwargs
    ) -> float:
        """
        Jitter décorrélé
        
        Args:
            attempt: Numéro de tentative (0-indexé)
            base_delay: Délai de base
            multiplier: Multiplicateur exponentiel
            previous_delay: Délai précédent
            
        Returns:
            float: Délai
        """
        if attempt == 0:
            return base_delay
        
        base = previous_delay * multiplier
        return random.uniform(base_delay, base)
    
    @staticmethod
    def exponential_jitter(
        attempt: int,
        base_delay: float,
        multiplier: float = 2.0,
        **kwargs
    ) -> float:
        """
        Jitter exponentiel
        
        Args:
            attempt: Numéro de tentative (0-indexé)
            base_delay: Délai de base
            multiplier: Multiplicateur exponentiel
            
        Returns:
            float: Délai
        """
        base = base_delay * (multiplier ** attempt)
        jitter = random.uniform(0, base * 0.5)
        return base + jitter
    
    @staticmethod
    def calculate(
        strategy: BackoffStrategy,
        attempt: int,
        config: BackoffConfig,
        previous_delay: Optional[float] = None
    ) -> float:
        """
        Calcule le délai selon la stratégie
        
        Args:
            strategy: Stratégie de backoff
            attempt: Numéro de tentative (0-indexé)
            config: Configuration de backoff
            previous_delay: Délai précédent (pour decorrelated_jitter)
            
        Returns:
            float: Délai calculé
        """
        kwargs = {
            'attempt': attempt,
            'base_delay': config.base_delay,
            'max_delay': config.max_delay,
            'multiplier': config.multiplier,
            'previous_delay': previous_delay,
        }
        
        if strategy == BackoffStrategy.FIXED:
            delay = BackoffCalculator.fixed_delay(**kwargs)
        elif strategy == BackoffStrategy.LINEAR:
            delay = BackoffCalculator.linear_delay(**kwargs)
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = BackoffCalculator.exponential_delay(**kwargs)
        elif strategy == BackoffStrategy.POLYNOMIAL:
            delay = BackoffCalculator.polynomial_delay(**kwargs)
        elif strategy == BackoffStrategy.RANDOM:
            delay = BackoffCalculator.random_delay(**kwargs)
        elif strategy == BackoffStrategy.FULL_JITTER:
            delay = BackoffCalculator.full_jitter(**kwargs)
        elif strategy == BackoffStrategy.EQUAL_JITTER:
            delay = BackoffCalculator.equal_jitter(**kwargs)
        elif strategy == BackoffStrategy.DECORRELATED_JITTER:
            delay = BackoffCalculator.decorrelated_jitter(**kwargs)
        elif strategy == BackoffStrategy.EXPONENTIAL_JITTER:
            delay = BackoffCalculator.exponential_jitter(**kwargs)
        else:
            delay = BackoffCalculator.exponential_delay(**kwargs)
        
        # Appliquer le jitter si configuré
        if config.jitter and strategy not in [
            BackoffStrategy.FULL_JITTER,
            BackoffStrategy.EQUAL_JITTER,
            BackoffStrategy.DECORRELATED_JITTER,
            BackoffStrategy.EXPONENTIAL_JITTER
        ]:
            jitter_range = delay * config.jitter_factor
            delay = delay + random.uniform(-jitter_range, jitter_range)
        
        # Limiter le délai maximum
        if config.max_delay > 0:
            delay = min(delay, config.max_delay)
        
        # S'assurer que le délai est positif
        delay = max(delay, 0.001)
        
        return delay

# ============================================================
# RETRY DECORATORS
# ============================================================

def retry(config: Optional[BackoffConfig] = None) -> Callable:
    """
    Décorateur de retry pour les fonctions synchrones
    
    Args:
        config: Configuration de backoff
        
    Returns:
        Callable: Décorateur
    """
    if config is None:
        config = BackoffConfig()
    
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> R:
            context = RetryContext(max_attempts=config.max_attempts)
            context.start_time = time.time()
            
            while context.should_retry:
                try:
                    # Vérifier le timeout
                    if config.timeout is not None:
                        if time.time() - context.start_time >= config.timeout:
                            if config.raise_on_timeout:
                                raise TimeoutError(
                                    f"Function {func.__name__} timed out after {config.timeout}s"
                                )
                            else:
                                context.final_attempt = True
                                context.should_retry = False
                                break
                    
                    result = func(*args, **kwargs)
                    context.last_result = result
                    
                    # Vérifier le résultat
                    if config.retry_on_result is not None:
                        if config.retry_on_result(result):
                            context.last_error = ValueError("Result validation failed")
                            raise context.last_error
                    
                    context.success = True
                    context.should_retry = False
                    return result
                    
                except config.retry_on as e:
                    context.last_error = e
                    context.attempt += 1
                    
                    if context.attempt >= config.max_attempts:
                        context.final_attempt = True
                        context.should_retry = False
                        raise
                    
                    if config.log_retries:
                        logger.log(
                            config.log_level,
                            f"Retry {context.attempt}/{config.max_attempts} "
                            f"for {func.__name__}: {e}"
                        )
                    
                    # Attendre
                    delay = BackoffCalculator.calculate(
                        config.strategy,
                        context.attempt,
                        config,
                        context.delays[-1] if context.delays else None
                    )
                    context.delays.append(delay)
                    time.sleep(delay)
            
            # Si on arrive ici, c'est un échec
            if context.last_error:
                raise context.last_error
            return context.last_result
        
        return wrapper
    
    return decorator

def retry_async(config: Optional[BackoffConfig] = None) -> Callable:
    """
    Décorateur de retry pour les fonctions asynchrones
    
    Args:
        config: Configuration de backoff
        
    Returns:
        Callable: Décorateur
    """
    if config is None:
        config = BackoffConfig()
    
    def decorator(func: Callable[..., Coroutine[Any, Any, R]]) -> Callable[..., Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> R:
            context = RetryContext(max_attempts=config.max_attempts)
            context.start_time = time.time()
            
            while context.should_retry:
                try:
                    # Vérifier le timeout
                    if config.timeout is not None:
                        if time.time() - context.start_time >= config.timeout:
                            if config.raise_on_timeout:
                                raise TimeoutError(
                                    f"Function {func.__name__} timed out after {config.timeout}s"
                                )
                            else:
                                context.final_attempt = True
                                context.should_retry = False
                                break
                    
                    result = await func(*args, **kwargs)
                    context.last_result = result
                    
                    # Vérifier le résultat
                    if config.retry_on_result is not None:
                        if config.retry_on_result(result):
                            context.last_error = ValueError("Result validation failed")
                            raise context.last_error
                    
                    context.success = True
                    context.should_retry = False
                    return result
                    
                except config.retry_on as e:
                    context.last_error = e
                    context.attempt += 1
                    
                    if context.attempt >= config.max_attempts:
                        context.final_attempt = True
                        context.should_retry = False
                        raise
                    
                    if config.log_retries:
                        logger.log(
                            config.log_level,
                            f"Retry {context.attempt}/{config.max_attempts} "
                            f"for {func.__name__}: {e}"
                        )
                    
                    # Attendre
                    delay = BackoffCalculator.calculate(
                        config.strategy,
                        context.attempt,
                        config,
                        context.delays[-1] if context.delays else None
                    )
                    context.delays.append(delay)
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
        config: Optional[BackoffConfig] = None,
        max_attempts: Optional[int] = None
    ):
        """
        Initialise l'itérateur
        
        Args:
            func: Fonction à exécuter
            config: Configuration de backoff
            max_attempts: Nombre maximum de tentatives
        """
        self.func = func
        self.config = config or BackoffConfig()
        if max_attempts is not None:
            self.config.max_attempts = max_attempts
        
        self.context = RetryContext(max_attempts=self.config.max_attempts)
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
            self.context.success = True
            self._done = True
            return result
            
        except Exception as e:
            self._error = e
            self.context.last_error = e
            self.context.attempt += 1
            
            if self.context.attempt >= self.config.max_attempts:
                self._done = True
                raise
            
            delay = BackoffCalculator.calculate(
                self.config.strategy,
                self.context.attempt,
                self.config,
                self.context.delays[-1] if self.context.delays else None
            )
            self.context.delays.append(delay)
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
        config: Optional[BackoffConfig] = None,
        max_attempts: Optional[int] = None
    ):
        """
        Initialise l'itérateur
        
        Args:
            func: Fonction asynchrone à exécuter
            config: Configuration de backoff
            max_attempts: Nombre maximum de tentatives
        """
        self.func = func
        self.config = config or BackoffConfig()
        if max_attempts is not None:
            self.config.max_attempts = max_attempts
        
        self.context = RetryContext(max_attempts=self.config.max_attempts)
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
            self.context.success = True
            self._done = True
            return result
            
        except Exception as e:
            self._error = e
            self.context.last_error = e
            self.context.attempt += 1
            
            if self.context.attempt >= self.config.max_attempts:
                self._done = True
                raise
            
            delay = BackoffCalculator.calculate(
                self.config.strategy,
                self.context.attempt,
                self.config,
                self.context.delays[-1] if self.context.delays else None
            )
            self.context.delays.append(delay)
            await asyncio.sleep(delay)
            return await self.__anext__()


# ============================================================
# RETRY CONTEXT MANAGERS
# ============================================================

@dataclass
class RetryState:
    """État du retry"""
    attempt: int = 0
    max_attempts: int = 3
    delay: float = 1.0
    last_error: Optional[Exception] = None
    success: bool = False
    result: Any = None
    elapsed: float = 0.0
    remaining_attempts: int = 3


class RetryManager:
    """
    Gestionnaire de retry
    
    Permet de gérer les retries avec état
    """
    
    def __init__(self, config: Optional[BackoffConfig] = None):
        """
        Initialise le gestionnaire
        
        Args:
            config: Configuration de backoff
        """
        self.config = config or BackoffConfig()
        self.context = RetryContext(max_attempts=self.config.max_attempts)
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
        self.context = RetryContext(max_attempts=self.config.max_attempts)
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
        
        while self.context.should_retry:
            try:
                self._stats['total_attempts'] += 1
                result = func()
                self._last_result = result
                self._stats['successful_attempts'] += 1
                self.context.success = True
                return result
                
            except Exception as e:
                self._stats['failed_attempts'] += 1
                self._last_error = e
                self.context.last_error = e
                self.context.attempt += 1
                
                if self.context.attempt >= self.config.max_attempts:
                    raise
                
                if self.config.timeout and self.context.elapsed >= self.config.timeout:
                    self._stats['timeouts'] += 1
                    if self.config.raise_on_timeout:
                        raise TimeoutError(f"Retry timed out after {self.config.timeout}s")
                    else:
                        break
                
                self._stats['retried_attempts'] += 1
                delay = BackoffCalculator.calculate(
                    self.config.strategy,
                    self.context.attempt,
                    self.config,
                    self.context.delays[-1] if self.context.delays else None
                )
                self.context.delays.append(delay)
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
        
        while self.context.should_retry:
            try:
                self._stats['total_attempts'] += 1
                result = await func()
                self._last_result = result
                self._stats['successful_attempts'] += 1
                self.context.success = True
                return result
                
            except Exception as e:
                self._stats['failed_attempts'] += 1
                self._last_error = e
                self.context.last_error = e
                self.context.attempt += 1
                
                if self.context.attempt >= self.config.max_attempts:
                    raise
                
                if self.config.timeout and self.context.elapsed >= self.config.timeout:
                    self._stats['timeouts'] += 1
                    if self.config.raise_on_timeout:
                        raise TimeoutError(f"Retry timed out after {self.config.timeout}s")
                    else:
                        break
                
                self._stats['retried_attempts'] += 1
                delay = BackoffCalculator.calculate(
                    self.config.strategy,
                    self.context.attempt,
                    self.config,
                    self.context.delays[-1] if self.context.delays else None
                )
                self.context.delays.append(delay)
                await asyncio.sleep(delay)
        
        return self._last_result
    
    def get_state(self) -> RetryState:
        """
        Récupère l'état actuel
        
        Returns:
            RetryState: État du retry
        """
        return RetryState(
            attempt=self.context.attempt,
            max_attempts=self.config.max_attempts,
            delay=self.context.delays[-1] if self.context.delays else self.config.base_delay,
            last_error=self._last_error,
            success=self.context.success,
            result=self._last_result,
            elapsed=self.context.elapsed,
            remaining_attempts=self.config.max_attempts - self.context.attempt
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            **self._stats,
            'success_rate': self._stats['successful_attempts'] / self._stats['total_attempts']
            if self._stats['total_attempts'] > 0 else 0,
            'last_error': str(self._last_error) if self._last_error else None,
            'last_result': self._last_result,
            'attempts': self.context.attempt,
            'max_attempts': self.config.max_attempts,
        }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'BackoffStrategy',
    
    # Data Classes
    'BackoffConfig',
    'RetryContext',
    'RetryState',
    
    # Classes
    'BackoffCalculator',
    'RetryIterator',
    'AsyncRetryIterator',
    'RetryManager',
    
    # Décorateurs
    'retry',
    'retry_async',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Backoff utilities module initialized")

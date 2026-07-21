"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Backoff Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de backoff et retry pour le bot d'arbitrage
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
            previous_delay: Délai précédent (pour décorrelated_jitter)
            
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
        else:
            delay = BackoffCalculator.exponential_delay(**kwargs)
        
        # Appliquer le jitter si configuré
        if config.jitter and strategy not in [
            BackoffStrategy.FULL_JITTER,
            BackoffStrategy.EQUAL_JITTER,
            BackoffStrategy.DECORRELATED_JITTER
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
            attempt = 0
            previous_delay = 0.0
            start_time = time.time()
            
            while True:
                try:
                    return func(*args, **kwargs)
                except config.retry_on as e:
                    attempt += 1
                    
                    if attempt >= config.max_attempts:
                        raise
                    
                    if config.timeout is not None:
                        elapsed = time.time() - start_time
                        if elapsed >= config.timeout:
                            if config.raise_on_timeout:
                                raise TimeoutError(
                                    f"Function {func.__name__} timed out after {config.timeout}s"
                                )
                            else:
                                raise
                    
                    delay = BackoffCalculator.calculate(
                        config.strategy,
                        attempt,
                        config,
                        previous_delay
                    )
                    previous_delay = delay
                    
                    if config.log_retries:
                        logger.log(
                            config.log_level,
                            f"Retry {attempt}/{config.max_attempts} for {func.__name__} "
                            f"after {delay:.2f}s due to: {e}"
                        )
                    
                    time.sleep(delay)
        
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
            attempt = 0
            previous_delay = 0.0
            start_time = time.time()
            
            while True:
                try:
                    return await func(*args, **kwargs)
                except config.retry_on as e:
                    attempt += 1
                    
                    if attempt >= config.max_attempts:
                        raise
                    
                    if config.timeout is not None:
                        elapsed = time.time() - start_time
                        if elapsed >= config.timeout:
                            if config.raise_on_timeout:
                                raise TimeoutError(
                                    f"Function {func.__name__} timed out after {config.timeout}s"
                                )
                            else:
                                raise
                    
                    delay = BackoffCalculator.calculate(
                        config.strategy,
                        attempt,
                        config,
                        previous_delay
                    )
                    previous_delay = delay
                    
                    if config.log_retries:
                        logger.log(
                            config.log_level,
                            f"Retry {attempt}/{config.max_attempts} for {func.__name__} "
                            f"after {delay:.2f}s due to: {e}"
                        )
                    
                    await asyncio.sleep(delay)
        
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
            max_attempts: Nombre maximum de tentatives (override config)
        """
        self.func = func
        self.config = config or BackoffConfig()
        if max_attempts is not None:
            self.config.max_attempts = max_attempts
        
        self.attempt = 0
        self.previous_delay = 0.0
        self.start_time = time.time()
        self.last_error: Optional[Exception] = None
    
    def __iter__(self) -> 'RetryIterator':
        return self
    
    def __next__(self) -> Any:
        """
        Tente la prochaine exécution
        
        Returns:
            Any: Résultat de la fonction
            
        Raises:
            StopIteration: Si le nombre maximum de tentatives est atteint
        """
        self.attempt += 1
        
        if self.attempt > self.config.max_attempts:
            raise StopIteration
        
        try:
            return self.func()
        except self.config.retry_on as e:
            self.last_error = e
            
            if self.attempt >= self.config.max_attempts:
                raise e
            
            if self.config.timeout is not None:
                elapsed = time.time() - self.start_time
                if elapsed >= self.config.timeout:
                    if self.config.raise_on_timeout:
                        raise TimeoutError(
                            f"Retry timed out after {self.config.timeout}s"
                        )
                    else:
                        raise e
            
            delay = BackoffCalculator.calculate(
                self.config.strategy,
                self.attempt,
                self.config,
                self.previous_delay
            )
            self.previous_delay = delay
            
            if self.config.log_retries:
                logger.log(
                    self.config.log_level,
                    f"Retry {self.attempt}/{self.config.max_attempts} "
                    f"after {delay:.2f}s due to: {e}"
                )
            
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
            max_attempts: Nombre maximum de tentatives (override config)
        """
        self.func = func
        self.config = config or BackoffConfig()
        if max_attempts is not None:
            self.config.max_attempts = max_attempts
        
        self.attempt = 0
        self.previous_delay = 0.0
        self.start_time = time.time()
        self.last_error: Optional[Exception] = None
    
    def __aiter__(self) -> 'AsyncRetryIterator':
        return self
    
    async def __anext__(self) -> Any:
        """
        Tente la prochaine exécution asynchrone
        
        Returns:
            Any: Résultat de la fonction
            
        Raises:
            StopAsyncIteration: Si le nombre maximum de tentatives est atteint
        """
        self.attempt += 1
        
        if self.attempt > self.config.max_attempts:
            raise StopAsyncIteration
        
        try:
            return await self.func()
        except self.config.retry_on as e:
            self.last_error = e
            
            if self.attempt >= self.config.max_attempts:
                raise e
            
            if self.config.timeout is not None:
                elapsed = time.time() - self.start_time
                if elapsed >= self.config.timeout:
                    if self.config.raise_on_timeout:
                        raise TimeoutError(
                            f"Retry timed out after {self.config.timeout}s"
                        )
                    else:
                        raise e
            
            delay = BackoffCalculator.calculate(
                self.config.strategy,
                self.attempt,
                self.config,
                self.previous_delay
            )
            self.previous_delay = delay
            
            if self.config.log_retries:
                logger.log(
                    self.config.log_level,
                    f"Retry {self.attempt}/{self.config.max_attempts} "
                    f"after {delay:.2f}s due to: {e}"
                )
            
            await asyncio.sleep(delay)
            
            return await self.__anext__()


# ============================================================
# RETRY CONTEXT MANAGERS
# ============================================================

@dataclass
class RetryContext:
    """Contexte de retry"""
    attempt: int = 0
    max_attempts: int = 3
    delay: float = 1.0
    last_error: Optional[Exception] = None
    success: bool = False
    result: Any = None


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
        self.attempt = 0
        self.previous_delay = 0.0
        self.start_time = time.time()
        self.last_error: Optional[Exception] = None
        self.results: List[Any] = []
        self.errors: List[Exception] = []
    
    def reset(self):
        """Réinitialise le gestionnaire"""
        self.attempt = 0
        self.previous_delay = 0.0
        self.start_time = time.time()
        self.last_error = None
        self.results.clear()
        self.errors.clear()
    
    def should_retry(self) -> bool:
        """
        Vérifie si une nouvelle tentative doit être faite
        
        Returns:
            bool: True si une nouvelle tentative doit être faite
        """
        if self.attempt >= self.config.max_attempts:
            return False
        
        if self.config.timeout is not None:
            elapsed = time.time() - self.start_time
            if elapsed >= self.config.timeout:
                return False
        
        return True
    
    def get_delay(self) -> float:
        """
        Calcule le délai pour la prochaine tentative
        
        Returns:
            float: Délai calculé
        """
        delay = BackoffCalculator.calculate(
            self.config.strategy,
            self.attempt,
            self.config,
            self.previous_delay
        )
        self.previous_delay = delay
        return delay
    
    def record_attempt(self, result: Any = None, error: Optional[Exception] = None):
        """
        Enregistre une tentative
        
        Args:
            result: Résultat de la tentative
            error: Erreur de la tentative
        """
        self.attempt += 1
        
        if error is not None:
            self.errors.append(error)
            self.last_error = error
        else:
            self.results.append(result)
    
    def get_context(self) -> RetryContext:
        """
        Récupère le contexte actuel
        
        Returns:
            RetryContext: Contexte de retry
        """
        return RetryContext(
            attempt=self.attempt,
            max_attempts=self.config.max_attempts,
            delay=self.previous_delay,
            last_error=self.last_error,
            success=len(self.results) > 0,
            result=self.results[-1] if self.results else None
        )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'BackoffStrategy',
    
    # Data Classes
    'BackoffConfig',
    'RetryContext',
    
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

"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Decorators
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Décorateurs pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import time
import functools
import inspect
import logging
import traceback
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    Tuple,
    Coroutine,
    AsyncIterator
)
from enum import Enum
from dataclasses import dataclass, field
from contextlib import contextmanager
import threading
from functools import wraps

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')
F = TypeVar('F', bound=Callable)

# ============================================================
# FUNCTION DECORATORS
# ============================================================

def timer(func: F) -> F:
    """
    Décorateur pour mesurer le temps d'exécution
    
    Args:
        func: Fonction à décorer
        
    Returns:
        F: Fonction décorée
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            logger.debug(f"{func.__name__} executed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(f"{func.__name__} failed after {elapsed:.3f}s: {e}")
            raise
    
    return wrapper


def async_timer(func: F) -> F:
    """
    Décorateur asynchrone pour mesurer le temps d'exécution
    
    Args:
        func: Fonction asynchrone à décorer
        
    Returns:
        F: Fonction décorée
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            logger.debug(f"{func.__name__} executed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(f"{func.__name__} failed after {elapsed:.3f}s: {e}")
            raise
    
    return wrapper


def log_call(func: F) -> F:
    """
    Décorateur pour logger les appels de fonction
    
    Args:
        func: Fonction à décorer
        
    Returns:
        F: Fonction décorée
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        args_str = ", ".join([str(a) for a in args])
        kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        all_args = ", ".join([a for a in [args_str, kwargs_str] if a])
        
        logger.debug(f"Calling {func.__name__}({all_args})")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
            raise
    
    return wrapper


def async_log_call(func: F) -> F:
    """
    Décorateur asynchrone pour logger les appels de fonction
    
    Args:
        func: Fonction asynchrone à décorer
        
    Returns:
        F: Fonction décorée
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        args_str = ", ".join([str(a) for a in args])
        kwargs_str = ", ".join([f"{k}={v}" for v in kwargs.items()])
        all_args = ", ".join([a for a in [args_str, kwargs_str] if a])
        
        logger.debug(f"Calling {func.__name__}({all_args})")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
            raise
    
    return wrapper


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[F], F]:
    """
    Décorateur pour réessayer une fonction en cas d'échec
    
    Args:
        max_attempts: Nombre maximum de tentatives
        delay: Délai initial entre les tentatives
        backoff: Multiplicateur de délai exponentiel
        exceptions: Exceptions à capturer
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}"
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    
    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[F], F]:
    """
    Décorateur asynchrone pour réessayer une fonction en cas d'échec
    
    Args:
        max_attempts: Nombre maximum de tentatives
        delay: Délai initial entre les tentatives
        backoff: Multiplicateur de délai exponentiel
        exceptions: Exceptions à capturer
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}"
                    )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    
    return decorator


def timeout(seconds: float) -> Callable[[F], F]:
    """
    Décorateur pour ajouter un timeout à une fonction
    
    Args:
        seconds: Nombre de secondes avant timeout
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
            
            # Sauvegarder le handler existant
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            
            try:
                signal.alarm(int(seconds))
                result = func(*args, **kwargs)
                signal.alarm(0)
                return result
            finally:
                signal.signal(signal.SIGALRM, old_handler)
                signal.alarm(0)
        
        return wrapper
    
    return decorator


def async_timeout(seconds: float) -> Callable[[F], F]:
    """
    Décorateur asynchrone pour ajouter un timeout
    
    Args:
        seconds: Nombre de secondes avant timeout
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
        
        return wrapper
    
    return decorator


def singleton(cls: Type[T]) -> Type[T]:
    """
    Décorateur pour créer un singleton
    
    Args:
        cls: Classe à décorer
        
    Returns:
        Type[T]: Classe singleton
    """
    instances = {}
    
    @functools.wraps(cls)
    def wrapper(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return wrapper


def synchronized(func: F) -> F:
    """
    Décorateur pour synchroniser l'accès à une méthode
    
    Args:
        func: Méthode à décorer
        
    Returns:
        F: Méthode décorée
    """
    lock = threading.RLock()
    
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        with lock:
            return func(self, *args, **kwargs)
    
    return wrapper


def async_synchronized(func: F) -> F:
    """
    Décorateur asynchrone pour synchroniser l'accès à une méthode
    
    Args:
        func: Méthode asynchrone à décorer
        
    Returns:
        F: Méthode décorée
    """
    lock = asyncio.Lock()
    
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        async with lock:
            return await func(self, *args, **kwargs)
    
    return wrapper


# ============================================================
# CLASS DECORATORS
# ============================================================

def dataclass_with_validation(cls: Type[T]) -> Type[T]:
    """
    Décorateur pour ajouter la validation à une dataclass
    
    Args:
        cls: Dataclass à décorer
        
    Returns:
        Type[T]: Dataclass avec validation
    """
    original_init = cls.__init__
    
    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if hasattr(self, '__post_init__'):
            self.__post_init__()
        if hasattr(self, 'validate'):
            self.validate()
    
    cls.__init__ = __init__
    
    return cls


def singleton_class(cls: Type[T]) -> Type[T]:
    """
    Décorateur pour créer une classe singleton
    
    Args:
        cls: Classe à décorer
        
    Returns:
        Type[T]: Classe singleton
    """
    instances = {}
    
    class SingletonMeta(type):
        def __call__(cls, *args, **kwargs):
            if cls not in instances:
                instances[cls] = super().__call__(*args, **kwargs)
            return instances[cls]
    
    return SingletonMeta(cls.__name__, (cls,), {})


# ============================================================
# CONTEXT MANAGER DECORATORS
# ============================================================

@contextmanager
def timeit(operation: str = "Operation"):
    """
    Context manager pour mesurer le temps d'exécution
    
    Args:
        operation: Nom de l'opération
        
    Yields:
        None
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start_time
        logger.debug(f"{operation} completed in {elapsed:.3f}s")


@contextmanager
def suppress(*exceptions: Type[Exception]):
    """
    Context manager pour supprimer des exceptions
    
    Args:
        exceptions: Exceptions à supprimer
        
    Yields:
        None
    """
    try:
        yield
    except exceptions:
        pass


@contextmanager
def catch_all(handler: Optional[Callable[[Exception], None]] = None):
    """
    Context manager pour capturer toutes les exceptions
    
    Args:
        handler: Gestionnaire d'exceptions optionnel
        
    Yields:
        None
    """
    try:
        yield
    except Exception as e:
        if handler:
            handler(e)
        else:
            logger.error(f"Exception caught: {e}")
            logger.debug(traceback.format_exc())


# ============================================================
# PROPERTY DECORATORS
# ============================================================

def cached_property(func: Callable[[Any], T]) -> property:
    """
    Décorateur pour créer une propriété avec cache
    
    Args:
        func: Fonction à décorer
        
    Returns:
        property: Propriété avec cache
    """
    attr_name = f"_cached_{func.__name__}"
    
    @property
    @functools.wraps(func)
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, func(self))
        return getattr(self, attr_name)
    
    return wrapper


def lazy_property(func: Callable[[Any], T]) -> property:
    """
    Décorateur pour créer une propriété lazy
    
    Args:
        func: Fonction à décorer
        
    Returns:
        property: Propriété lazy
    """
    attr_name = f"_lazy_{func.__name__}"
    
    @property
    @functools.wraps(func)
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, func(self))
        return getattr(self, attr_name)
    
    return wrapper


# ============================================================
# METHOD DECORATORS
# ============================================================

def classmethod_with_logging(cls_method: Callable) -> Callable:
    """
    Décorateur pour logger les méthodes de classe
    
    Args:
        cls_method: Méthode de classe à décorer
        
    Returns:
        Callable: Méthode décorée
    """
    @functools.wraps(cls_method)
    def wrapper(cls, *args, **kwargs):
        logger.debug(f"Calling {cls.__name__}.{cls_method.__name__}")
        try:
            result = cls_method(cls, *args, **kwargs)
            logger.debug(f"{cls.__name__}.{cls_method.__name__} completed")
            return result
        except Exception as e:
            logger.error(f"{cls.__name__}.{cls_method.__name__} failed: {e}")
            raise
    
    return wrapper


def staticmethod_with_logging(static_method: Callable) -> Callable:
    """
    Décorateur pour logger les méthodes statiques
    
    Args:
        static_method: Méthode statique à décorer
        
    Returns:
        Callable: Méthode décorée
    """
    @functools.wraps(static_method)
    def wrapper(*args, **kwargs):
        logger.debug(f"Calling static method {static_method.__name__}")
        try:
            result = static_method(*args, **kwargs)
            logger.debug(f"{static_method.__name__} completed")
            return result
        except Exception as e:
            logger.error(f"{static_method.__name__} failed: {e}")
            raise
    
    return wrapper


# ============================================================
# VALIDATION DECORATORS
# ============================================================

def validate_args(
    *validators: Callable[[Any], bool],
    error_message: str = "Argument validation failed"
) -> Callable[[F], F]:
    """
    Décorateur pour valider les arguments d'une fonction
    
    Args:
        validators: Liste de validateurs
        error_message: Message d'erreur
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i, arg in enumerate(args):
                for validator in validators:
                    if not validator(arg):
                        raise ValueError(f"{error_message} for argument {i}")
            
            for key, value in kwargs.items():
                for validator in validators:
                    if not validator(value):
                        raise ValueError(f"{error_message} for argument {key}")
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def validate_return(
    *validators: Callable[[Any], bool],
    error_message: str = "Return value validation failed"
) -> Callable[[F], F]:
    """
    Décorateur pour valider la valeur de retour d'une fonction
    
    Args:
        validators: Liste de validateurs
        error_message: Message d'erreur
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            for validator in validators:
                if not validator(result):
                    raise ValueError(error_message)
            
            return result
        
        return wrapper
    
    return decorator


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Fonction decorators
    'timer',
    'async_timer',
    'log_call',
    'async_log_call',
    'retry',
    'async_retry',
    'timeout',
    'async_timeout',
    'singleton',
    'synchronized',
    'async_synchronized',
    
    # Class decorators
    'dataclass_with_validation',
    'singleton_class',
    
    # Context managers
    'timeit',
    'suppress',
    'catch_all',
    
    # Property decorators
    'cached_property',
    'lazy_property',
    
    # Method decorators
    'classmethod_with_logging',
    'staticmethod_with_logging',
    
    # Validation decorators
    'validate_args',
    'validate_return',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Decorators module initialized")

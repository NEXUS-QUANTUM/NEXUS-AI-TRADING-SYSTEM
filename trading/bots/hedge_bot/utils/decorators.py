"""
NEXUS AI TRADING SYSTEM - Hedge Bot Decorators
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Décorateurs pour le bot de couverture
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
    AsyncIterator,
    cast
)
from enum import Enum
from dataclasses import dataclass, field
from contextlib import contextmanager
import threading
from functools import wraps
import warnings

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
# ENUMS
# ============================================================

class LogLevel(Enum):
    """Niveaux de log"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


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
    exceptions: tuple = (Exception,),
    log_retries: bool = True
) -> Callable[[F], F]:
    """
    Décorateur pour réessayer une fonction en cas d'échec
    
    Args:
        max_attempts: Nombre maximum de tentatives
        delay: Délai initial entre les tentatives
        backoff: Multiplicateur de délai exponentiel
        exceptions: Exceptions à capturer
        log_retries: Logger les tentatives
        
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
                    
                    if log_retries:
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
    exceptions: tuple = (Exception,),
    log_retries: bool = True
) -> Callable[[F], F]:
    """
    Décorateur asynchrone pour réessayer une fonction en cas d'échec
    
    Args:
        max_attempts: Nombre maximum de tentatives
        delay: Délai initial entre les tentatives
        backoff: Multiplicateur de délai exponentiel
        exceptions: Exceptions à capturer
        log_retries: Logger les tentatives
        
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
                    
                    if log_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}"
                        )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    
    return decorator


def timeout(seconds: float, error_message: Optional[str] = None) -> Callable[[F], F]:
    """
    Décorateur pour ajouter un timeout à une fonction
    
    Args:
        seconds: Nombre de secondes avant timeout
        error_message: Message d'erreur personnalisé
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_handler(signum, frame):
                msg = error_message or f"Function {func.__name__} timed out after {seconds}s"
                raise TimeoutError(msg)
            
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


def async_timeout(seconds: float, error_message: Optional[str] = None) -> Callable[[F], F]:
    """
    Décorateur asynchrone pour ajouter un timeout
    
    Args:
        seconds: Nombre de secondes avant timeout
        error_message: Message d'erreur personnalisé
        
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
                msg = error_message or f"Function {func.__name__} timed out after {seconds}s"
                raise TimeoutError(msg)
        
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


def method_synchronized(lock_name: str = "_lock") -> Callable:
    """
    Décorateur pour synchroniser l'accès avec un verrou nommé
    
    Args:
        lock_name: Nom de l'attribut verrou
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            lock = getattr(self, lock_name)
            with lock:
                return func(self, *args, **kwargs)
        return wrapper
    return decorator


def async_method_synchronized(lock_name: str = "_lock") -> Callable:
    """
    Décorateur asynchrone pour synchroniser l'accès avec un verrou nommé
    
    Args:
        lock_name: Nom de l'attribut verrou
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            lock = getattr(self, lock_name)
            async with lock:
                return await func(self, *args, **kwargs)
        return wrapper
    return decorator

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


def auto_str(cls: Type[T]) -> Type[T]:
    """
    Décorateur pour ajouter une représentation automatique
    
    Args:
        cls: Classe à décorer
        
    Returns:
        Type[T]: Classe avec __str__
    """
    def __str__(self):
        attrs = ', '.join(
            f"{k}={v!r}" for k, v in self.__dict__.items()
        )
        return f"{self.__class__.__name__}({attrs})"
    
    cls.__str__ = __str__
    return cls


def auto_repr(cls: Type[T]) -> Type[T]:
    """
    Décorateur pour ajouter une représentation automatique
    
    Args:
        cls: Classe à décorer
        
    Returns:
        Type[T]: Classe avec __repr__
    """
    def __repr__(self):
        attrs = ', '.join(
            f"{k}={v!r}" for k, v in self.__dict__.items()
        )
        return f"{self.__class__.__name__}({attrs})"
    
    cls.__repr__ = __repr__
    return cls


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


@contextmanager
def log_exceptions(logger_instance=None, message: str = "Exception occurred"):
    """
    Context manager pour logger les exceptions
    
    Args:
        logger_instance: Instance de logger
        message: Message de log
        
    Yields:
        None
    """
    try:
        yield
    except Exception as e:
        logger_instance = logger_instance or logger
        logger_instance.error(f"{message}: {e}", exc_info=True)
        raise


@contextmanager
def time_context(operation: str = "Operation"):
    """
    Context manager pour mesurer le temps (alias)
    
    Args:
        operation: Nom de l'opération
        
    Yields:
        None
    """
    with timeit(operation):
        yield


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


def computed_property(func: Callable[[Any], T]) -> property:
    """
    Décorateur pour créer une propriété calculée (alias)
    
    Args:
        func: Fonction à décorer
        
    Returns:
        property: Propriété calculée
    """
    return cached_property(func)


def thread_local_property(func: Callable[[Any], T]) -> property:
    """
    Décorateur pour créer une propriété thread-local
    
    Args:
        func: Fonction à décorer
        
    Returns:
        property: Propriété thread-local
    """
    attr_name = f"_thread_local_{func.__name__}"
    
    @property
    @functools.wraps(func)
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, threading.local())
        thread_local = getattr(self, attr_name)
        if not hasattr(thread_local, 'value'):
            thread_local.value = func(self)
        return thread_local.value
    
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


def method_logging(log_level: LogLevel = LogLevel.DEBUG) -> Callable:
    """
    Décorateur pour logger les méthodes avec niveau personnalisé
    
    Args:
        log_level: Niveau de log
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            level = getattr(logger, log_level.value)
            level(f"Calling {func.__name__}")
            try:
                result = func(*args, **kwargs)
                level(f"{func.__name__} completed")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} failed: {e}")
                raise
        return wrapper
    return decorator


def async_method_logging(log_level: LogLevel = LogLevel.DEBUG) -> Callable:
    """
    Décorateur asynchrone pour logger les méthodes
    
    Args:
        log_level: Niveau de log
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            level = getattr(logger, log_level.value)
            level(f"Calling {func.__name__}")
            try:
                result = await func(*args, **kwargs)
                level(f"{func.__name__} completed")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} failed: {e}")
                raise
        return wrapper
    return decorator

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


def validate_types(
    arg_types: Dict[str, type],
    return_type: Optional[type] = None
) -> Callable[[F], F]:
    """
    Décorateur pour valider les types des arguments
    
    Args:
        arg_types: Mapping des noms d'arguments vers les types
        return_type: Type de retour attendu
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Valider les arguments positionnels
            arg_names = list(inspect.signature(func).parameters.keys())
            for i, arg in enumerate(args):
                if i < len(arg_names):
                    arg_name = arg_names[i]
                    if arg_name in arg_types:
                        expected_type = arg_types[arg_name]
                        if not isinstance(arg, expected_type):
                            raise TypeError(
                                f"Argument '{arg_name}' must be of type {expected_type.__name__}, "
                                f"got {type(arg).__name__}"
                            )
            
            # Valider les arguments nommés
            for key, value in kwargs.items():
                if key in arg_types:
                    expected_type = arg_types[key]
                    if not isinstance(value, expected_type):
                        raise TypeError(
                            f"Argument '{key}' must be of type {expected_type.__name__}, "
                            f"got {type(value).__name__}"
                        )
            
            result = func(*args, **kwargs)
            
            # Valider le retour
            if return_type and not isinstance(result, return_type):
                raise TypeError(
                    f"Return value must be of type {return_type.__name__}, "
                    f"got {type(result).__name__}"
                )
            
            return result
        
        return wrapper
    
    return decorator


def validate_range(
    arg_name: str,
    min_value: Optional[Any] = None,
    max_value: Optional[Any] = None
) -> Callable[[F], F]:
    """
    Décorateur pour valider la plage d'un argument
    
    Args:
        arg_name: Nom de l'argument
        min_value: Valeur minimale
        max_value: Valeur maximale
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Trouver la valeur de l'argument
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            value = bound_args.arguments.get(arg_name)
            if value is not None:
                if min_value is not None and value < min_value:
                    raise ValueError(
                        f"Argument '{arg_name}' must be >= {min_value}, got {value}"
                    )
                if max_value is not None and value > max_value:
                    raise ValueError(
                        f"Argument '{arg_name}' must be <= {max_value}, got {value}"
                    )
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'LogLevel',
    
    # Function decorators
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
    'method_synchronized',
    'async_method_synchronized',
    
    # Class decorators
    'dataclass_with_validation',
    'singleton_class',
    'auto_str',
    'auto_repr',
    
    # Context managers
    'timeit',
    'suppress',
    'catch_all',
    'log_exceptions',
    'time_context',
    
    # Property decorators
    'cached_property',
    'lazy_property',
    'computed_property',
    'thread_local_property',
    
    # Method decorators
    'classmethod_with_logging',
    'staticmethod_with_logging',
    'method_logging',
    'async_method_logging',
    
    # Validation decorators
    'validate_args',
    'validate_return',
    'validate_types',
    'validate_range',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Decorators module initialized")

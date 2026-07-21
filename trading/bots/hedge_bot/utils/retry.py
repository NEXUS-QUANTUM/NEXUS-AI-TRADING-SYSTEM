"""
NEXUS AI TRADING SYSTEM - HEDGE BOT RETRY MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des retries pour le Hedge Bot.
Support des stratégies de retry, backoff, circuit breaker, et plus.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import logging
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class RetryStrategy(Enum):
    """Stratégies de retry."""
    NONE = "none"
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"
    RANDOM = "random"
    ADAPTIVE = "adaptive"
    CUSTOM = "custom"


class BackoffType(Enum):
    """Types de backoff."""
    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    POLYNOMIAL = "polynomial"
    RANDOM = "random"
    CUSTOM = "custom"


class CircuitBreakerState(Enum):
    """États du circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RetryConfig:
    """Configuration de retry."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: float = 0.1
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_on: Optional[List[Type[Exception]]] = None
    retry_on_status: Optional[List[int]] = None
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "max_attempts": self.max_attempts,
            "initial_delay": self.initial_delay,
            "max_delay": self.max_delay,
            "multiplier": self.multiplier,
            "jitter": self.jitter,
            "strategy": self.strategy.value,
            "retry_on": [e.__name__ for e in (self.retry_on or [])],
            "retry_on_status": self.retry_on_status,
            "timeout": self.timeout,
            "metadata": self.metadata
        }


@dataclass
class RetryStats:
    """Statistiques de retry."""
    attempt_id: UUID
    operation: str
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    last_attempt: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    total_duration: float = 0.0
    average_duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "attempt_id": str(self.attempt_id),
            "operation": self.operation,
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "total_duration": self.total_duration,
            "average_duration": self.average_duration,
            "metadata": self.metadata
        }


@dataclass
class CircuitBreakerConfig:
    """Configuration du circuit breaker."""
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 30.0
    half_open_timeout: float = 10.0
    monitored_exceptions: Optional[List[Type[Exception]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "timeout": self.timeout,
            "half_open_timeout": self.half_open_timeout,
            "monitored_exceptions": [e.__name__ for e in (self.monitored_exceptions or [])],
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE RETRY
# ============================================================================

class Retry:
    """
    Gestionnaire de retries avec stratégies avancées.
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        logger_obj: Optional[logging.Logger] = None
    ):
        """
        Initialise le gestionnaire de retries.

        Args:
            config: Configuration de retry
            logger_obj: Logger à utiliser
        """
        self.config = config or RetryConfig()
        self._logger = logger_obj or logger
        self._stats: Dict[str, RetryStats] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._metrics = {
            "total_attempts": 0,
            "total_successes": 0,
            "total_failures": 0,
            "total_timeouts": 0,
            "by_operation": {}
        }

    # ========================================================================
    # EXÉCUTION AVEC RETRY
    # ========================================================================

    async def execute(
        self,
        func: Callable,
        *args,
        operation_name: Optional[str] = None,
        config: Optional[RetryConfig] = None,
        **kwargs
    ) -> Any:
        """
        Exécute une fonction avec retry.

        Args:
            func: Fonction à exécuter
            *args: Arguments
            operation_name: Nom de l'opération
            config: Configuration spécifique
            **kwargs: Arguments nommés

        Returns:
            Résultat de la fonction

        Raises:
            Exception: Dernière exception levée
        """
        config = config or self.config
        operation_name = operation_name or func.__name__
        attempt_id = uuid4()

        start_time = time.time()
        last_exception = None
        attempt = 0

        # Initialisation des statistiques
        if operation_name not in self._stats:
            self._stats[operation_name] = RetryStats(
                attempt_id=attempt_id,
                operation=operation_name,
                total_attempts=0,
                successful_attempts=0,
                failed_attempts=0
            )

        stats = self._stats[operation_name]
        stats.total_attempts += 1
        self._metrics["total_attempts"] += 1

        while attempt < config.max_attempts:
            try:
                attempt += 1
                self._logger.debug(
                    f"Tentative {attempt}/{config.max_attempts} pour {operation_name}"
                )

                # Exécution avec timeout
                if config.timeout:
                    result = await asyncio.wait_for(
                        self._execute_func(func, *args, **kwargs),
                        timeout=config.timeout
                    )
                else:
                    result = await self._execute_func(func, *args, **kwargs)

                # Succès
                stats.successful_attempts += 1
                self._metrics["total_successes"] += 1
                stats.last_success = datetime.now()

                duration = time.time() - start_time
                stats.total_duration += duration
                stats.average_duration = stats.total_duration / stats.successful_attempts

                self._update_metrics(operation_name, success=True)

                return result

            except asyncio.TimeoutError as e:
                self._metrics["total_timeouts"] += 1
                last_exception = e
                stats.failed_attempts += 1
                stats.last_failure = datetime.now()
                self._logger.warning(
                    f"Timeout pour {operation_name} (tentative {attempt}/{config.max_attempts})"
                )

            except Exception as e:
                # Vérification si l'exception doit être retryée
                if not self._should_retry(e, config):
                    self._logger.error(
                        f"Exception non retryable pour {operation_name}: {e}"
                    )
                    raise

                last_exception = e
                stats.failed_attempts += 1
                stats.last_failure = datetime.now()
                self._metrics["total_failures"] += 1
                self._logger.warning(
                    f"Erreur pour {operation_name} (tentative {attempt}/{config.max_attempts}): {e}"
                )

            # Calcul du délai avant la prochaine tentative
            if attempt < config.max_attempts:
                delay = self._calculate_delay(attempt, config)
                self._logger.debug(f"Attente de {delay:.2f}s avant la prochaine tentative")
                await asyncio.sleep(delay)

        # Toutes les tentatives ont échoué
        self._update_metrics(operation_name, success=False)
        self._logger.error(
            f"Toutes les tentatives ({config.max_attempts}) ont échoué pour {operation_name}"
        )

        if last_exception:
            raise last_exception
        raise RetryError(f"Échec de {operation_name} après {config.max_attempts} tentatives")

    async def _execute_func(self, func: Callable, *args, **kwargs) -> Any:
        """
        Exécute une fonction de manière asynchrone.

        Args:
            func: Fonction à exécuter
            *args: Arguments
            **kwargs: Arguments nommés

        Returns:
            Résultat de la fonction
        """
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)

    # ========================================================================
    # STRATÉGIES DE RETRY
    # ========================================================================

    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """
        Calcule le délai avant la prochaine tentative.

        Args:
            attempt: Numéro de tentative
            config: Configuration de retry

        Returns:
            Délai en secondes
        """
        strategy = config.strategy
        initial_delay = config.initial_delay
        max_delay = config.max_delay
        multiplier = config.multiplier
        jitter = config.jitter

        delay = 0.0

        if strategy == RetryStrategy.FIXED:
            delay = initial_delay

        elif strategy == RetryStrategy.LINEAR:
            delay = initial_delay * attempt

        elif strategy == RetryStrategy.EXPONENTIAL:
            delay = initial_delay * (multiplier ** (attempt - 1))

        elif strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base_delay = initial_delay * (multiplier ** (attempt - 1))
            jitter_amount = base_delay * jitter * random.random()
            delay = base_delay + jitter_amount

        elif strategy == RetryStrategy.RANDOM:
            delay = random.uniform(initial_delay, max_delay)

        elif strategy == RetryStrategy.ADAPTIVE:
            # Adaptation basée sur les statistiques
            stats = self._stats.get(config.metadata.get("operation", ""))
            if stats and stats.successful_attempts > 0:
                avg_duration = stats.average_duration
                delay = min(avg_duration * 1.5, max_delay)
            else:
                delay = initial_delay

        delay = min(delay, max_delay)
        return delay

    def _should_retry(self, exception: Exception, config: RetryConfig) -> bool:
        """
        Vérifie si l'exception doit être retryée.

        Args:
            exception: Exception
            config: Configuration de retry

        Returns:
            True si retryable
        """
        if config.retry_on:
            for exc_type in config.retry_on:
                if isinstance(exception, exc_type):
                    return True
            return False

        # Si aucun type spécifié, retry toutes les exceptions sauf les critiques
        critical_exceptions = (
            KeyboardInterrupt,
            SystemExit,
            MemoryError,
            RecursionError,
            asyncio.CancelledError
        )

        if isinstance(exception, critical_exceptions):
            return False

        return True

    # ========================================================================
    # CIRCUIT BREAKER
    # ========================================================================

    def get_circuit_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> 'CircuitBreaker':
        """
        Récupère ou crée un circuit breaker.

        Args:
            name: Nom du circuit breaker
            config: Configuration

        Returns:
            Circuit breaker
        """
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(
                name=name,
                config=config or CircuitBreakerConfig(),
                logger_obj=self._logger
            )
        return self._circuit_breakers[name]

    async def execute_with_circuit_breaker(
        self,
        name: str,
        func: Callable,
        *args,
        config: Optional[CircuitBreakerConfig] = None,
        **kwargs
    ) -> Any:
        """
        Exécute une fonction avec circuit breaker.

        Args:
            name: Nom du circuit breaker
            func: Fonction à exécuter
            *args: Arguments
            config: Configuration
            **kwargs: Arguments nommés

        Returns:
            Résultat de la fonction

        Raises:
            CircuitBreakerOpenError: Circuit breaker ouvert
        """
        cb = self.get_circuit_breaker(name, config)
        
        if cb.is_open():
            raise CircuitBreakerOpenError(
                f"Circuit breaker {name} est ouvert"
            )

        try:
            result = await self.execute(func, *args, **kwargs)
            cb.record_success()
            return result

        except Exception as e:
            cb.record_failure()
            raise

    # ========================================================================
    # STATISTIQUES
    # ========================================================================

    def get_stats(self, operation: Optional[str] = None) -> Union[RetryStats, Dict[str, RetryStats]]:
        """
        Récupère les statistiques.

        Args:
            operation: Nom de l'opération

        Returns:
            Statistiques
        """
        if operation:
            return self._stats.get(operation, RetryStats(
                attempt_id=uuid4(),
                operation=operation,
                total_attempts=0,
                successful_attempts=0,
                failed_attempts=0
            ))
        return self._stats

    def _update_metrics(self, operation: str, success: bool) -> None:
        """
        Met à jour les métriques.

        Args:
            operation: Nom de l'opération
            success: Succès
        """
        if operation not in self._metrics["by_operation"]:
            self._metrics["by_operation"][operation] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0
            }
        
        op_metrics = self._metrics["by_operation"][operation]
        op_metrics["attempts"] += 1
        
        if success:
            op_metrics["successes"] += 1
        else:
            op_metrics["failures"] += 1

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            total = self._metrics["total_attempts"]
            success_rate = (
                self._metrics["total_successes"] / total * 100
                if total > 0 else 100
            )

            return {
                "status": "healthy",
                "total_attempts": self._metrics["total_attempts"],
                "total_successes": self._metrics["total_successes"],
                "total_failures": self._metrics["total_failures"],
                "total_timeouts": self._metrics["total_timeouts"],
                "success_rate": success_rate,
                "by_operation": self._metrics["by_operation"],
                "circuit_breakers": {
                    name: cb.get_state().value
                    for name, cb in self._circuit_breakers.items()
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de Retry...")
        self._stats.clear()
        self._circuit_breakers.clear()
        logger.info("Retry fermé")


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """
    Circuit breaker pour prévenir les appels répétés à un service défaillant.
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig,
        logger_obj: Optional[logging.Logger] = None
    ):
        """
        Initialise le circuit breaker.

        Args:
            name: Nom
            config: Configuration
            logger_obj: Logger
        """
        self.name = name
        self.config = config
        self._logger = logger_obj or logger
        
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._open_time: Optional[datetime] = None
        self._half_open_time: Optional[datetime] = None

    def is_open(self) -> bool:
        """
        Vérifie si le circuit est ouvert.

        Returns:
            True si ouvert
        """
        if self._state == CircuitBreakerState.OPEN:
            # Vérification du timeout
            if self._open_time:
                elapsed = (datetime.now() - self._open_time).total_seconds()
                if elapsed >= self.config.timeout:
                    self._transition_to_half_open()
                    return False
            return True

        return False

    def record_success(self) -> None:
        """
        Enregistre un succès.
        """
        self._last_success_time = datetime.now()

        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitBreakerState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        """
        Enregistre un échec.
        """
        self._last_failure_time = datetime.now()
        self._failure_count += 1

        if self._state == CircuitBreakerState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to_open()
        elif self._state == CircuitBreakerState.HALF_OPEN:
            self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Passe à l'état ouvert."""
        self._state = CircuitBreakerState.OPEN
        self._open_time = datetime.now()
        self._failure_count = 0
        self._success_count = 0
        self._logger.warning(f"Circuit breaker {self.name} ouvert")

    def _transition_to_half_open(self) -> None:
        """Passe à l'état semi-ouvert."""
        self._state = CircuitBreakerState.HALF_OPEN
        self._half_open_time = datetime.now()
        self._success_count = 0
        self._logger.info(f"Circuit breaker {self.name} semi-ouvert")

    def _transition_to_closed(self) -> None:
        """Passe à l'état fermé."""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._logger.info(f"Circuit breaker {self.name} fermé")

    def get_state(self) -> CircuitBreakerState:
        """
        Récupère l'état du circuit.

        Returns:
            État du circuit
        """
        return self._state

    def reset(self) -> None:
        """
        Réinitialise le circuit breaker.
        """
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._last_success_time = None
        self._open_time = None
        self._half_open_time = None
        self._logger.info(f"Circuit breaker {self.name} réinitialisé")


# ============================================================================
# DÉCORATEURS
# ============================================================================

def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    retry_on: Optional[List[Type[Exception]]] = None,
    timeout: Optional[float] = None,
    logger_obj: Optional[logging.Logger] = None
) -> Callable:
    """
    Décorateur pour retry automatique.

    Args:
        max_attempts: Nombre maximum de tentatives
        initial_delay: Délai initial
        max_delay: Délai maximum
        multiplier: Multiplicateur
        jitter: Jitter
        strategy: Stratégie de retry
        retry_on: Exceptions à retry
        timeout: Timeout
        logger_obj: Logger

    Returns:
        Fonction décorée
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        multiplier=multiplier,
        jitter=jitter,
        strategy=strategy,
        retry_on=retry_on,
        timeout=timeout
    )
    retry_manager = Retry(config, logger_obj)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_manager.execute(
                func,
                *args,
                operation_name=func.__name__,
                **kwargs
            )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    retry_manager.execute(
                        func,
                        *args,
                        operation_name=func.__name__,
                        **kwargs
                    )
                )
            finally:
                loop.close()

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    success_threshold: int = 3,
    timeout: float = 30.0,
    half_open_timeout: float = 10.0,
    monitored_exceptions: Optional[List[Type[Exception]]] = None,
    logger_obj: Optional[logging.Logger] = None
) -> Callable:
    """
    Décorateur pour circuit breaker.

    Args:
        name: Nom du circuit breaker
        failure_threshold: Seuil d'échec
        success_threshold: Seuil de succès
        timeout: Timeout
        half_open_timeout: Timeout semi-ouvert
        monitored_exceptions: Exceptions à surveiller
        logger_obj: Logger

    Returns:
        Fonction décorée
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout=timeout,
        half_open_timeout=half_open_timeout,
        monitored_exceptions=monitored_exceptions
    )
    retry_manager = Retry(logger_obj=logger_obj)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_manager.execute_with_circuit_breaker(
                name,
                func,
                *args,
                config=config,
                **kwargs
            )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    retry_manager.execute_with_circuit_breaker(
                        name,
                        func,
                        *args,
                        config=config,
                        **kwargs
                    )
                )
            finally:
                loop.close()

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ============================================================================
# EXCEPTIONS
# ============================================================================

class RetryError(Exception):
    """Exception de retry."""
    pass


class CircuitBreakerOpenError(Exception):
    """Exception lorsque le circuit breaker est ouvert."""
    pass


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
) -> Retry:
    """
    Crée une instance de Retry.

    Args:
        max_attempts: Nombre maximum de tentatives
        initial_delay: Délai initial
        strategy: Stratégie de retry

    Returns:
        Instance de Retry
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        strategy=strategy
    )
    return Retry(config)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "RetryStrategy",
    "BackoffType",
    "CircuitBreakerState",
    "RetryConfig",
    "RetryStats",
    "CircuitBreakerConfig",
    "Retry",
    "CircuitBreaker",
    "retry",
    "circuit_breaker",
    "RetryError",
    "CircuitBreakerOpenError",
    "create_retry"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du module retry."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT RETRY")
    print("=" * 60)

    # Création du gestionnaire
    retry_manager = create_retry(
        max_attempts=3,
        initial_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL_JITTER
    )

    print(f"\n✅ Retry manager créé")

    # Fonction avec retry
    print(f"\n🔄 Test de retry...")
    
    attempt_counter = 0
    
    async def flaky_function():
        nonlocal attempt_counter
        attempt_counter += 1
        if attempt_counter < 3:
            raise ValueError("Erreur temporaire")
        return "Succès!"

    try:
        result = await retry_manager.execute(
            flaky_function,
            operation_name="test_operation"
        )
        print(f"   Résultat: {result}")
        print(f"   Tentatives: {attempt_counter}")
    except Exception as e:
        print(f"   Erreur finale: {e}")

    # Circuit breaker
    print(f"\n🔌 Test de circuit breaker...")
    
    cb = retry_manager.get_circuit_breaker(
        "test_cb",
        CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            timeout=5.0
        )
    )

    for i in range(4):
        try:
            result = await retry_manager.execute_with_circuit_breaker(
                "test_cb",
                flaky_function
            )
            print(f"   Tentative {i+1}: Succès - {result}")
        except Exception as e:
            print(f"   Tentative {i+1}: Échec - {e}")

    print(f"   État du circuit: {cb.get_state().value}")

    # Décorateur
    print(f"\n🎯 Test du décorateur...")

    @retry(max_attempts=3, initial_delay=0.5)
    async def decorated_function():
        if random.random() < 0.7:
            raise ValueError("Erreur aléatoire")
        return "Succès!"

    for i in range(3):
        try:
            result = await decorated_function()
            print(f"   Essai {i+1}: {result}")
            break
        except Exception as e:
            print(f"   Essai {i+1}: Échec - {e}")

    # Statistiques
    stats = retry_manager.get_stats()
    print(f"\n📊 Statistiques:")
    for op, stat in stats.items():
        print(f"   {op}: {stat.successful_attempts}/{stat.total_attempts} succès")

    # Santé du service
    health = retry_manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Taux de succès: {health['success_rate']:.1f}%")
    print(f"   Tentatives totales: {health['total_attempts']}")

    # Fermeture
    await retry_manager.close()

    print("\n" + "=" * 60)
    print("Retry NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import random
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

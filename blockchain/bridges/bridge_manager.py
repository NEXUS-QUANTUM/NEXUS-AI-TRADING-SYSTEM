
# blockchain/bridges/bridge_manager.py
"""
NEXUS AI TRADING SYSTEM - Bridge Manager Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import threading
import time
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class BridgeManagerConfig:
    """Configuration pour Bridge Manager"""
    name: str = "bridge_manager"
    update_interval: int = 60  # secondes
    max_retries: int = 3
    retry_delay: int = 5
    timeout: int = 300
    enable_monitoring: bool = True
    enable_auto_recovery: bool = True
    alert_threshold: float = 0.1  # 10% de variation
    max_bridges: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'update_interval': self.update_interval,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout': self.timeout,
            'enable_monitoring': self.enable_monitoring,
            'enable_auto_recovery': self.enable_auto_recovery,
            'alert_threshold': self.alert_threshold,
            'max_bridges': self.max_bridges,
        }


@dataclass
class BridgeStatus:
    """Statut d'un bridge"""
    bridge_name: str
    is_active: bool
    last_check: datetime
    response_time: float
    error_count: int
    success_rate: float
    transaction_count: int
    volume_24h: float
    status_message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bridge_name': self.bridge_name,
            'is_active': self.is_active,
            'last_check': self.last_check.isoformat(),
            'response_time': self.response_time,
            'error_count': self.error_count,
            'success_rate': self.success_rate,
            'transaction_count': self.transaction_count,
            'volume_24h': self.volume_24h,
            'status_message': self.status_message,
        }


class BridgeManager:
    """
    Gestionnaire de bridges.

    Features:
    - Gestion multi-bridges
    - Monitoring des bridges
    - Auto-recovery
    - Load balancing
    - Statistiques

    Example:
        ```python
        config = BridgeManagerConfig(
            name='main_manager',
            enable_monitoring=True,
            enable_auto_recovery=True
        )
        manager = BridgeManager(config)

        # Ajouter un bridge
        manager.add_bridge('arbitrum', bridge_instance)

        # Démarrer
        manager.start()
        ```
    """

    def __init__(self, config: Optional[BridgeManagerConfig] = None):
        self.config = config or BridgeManagerConfig()
        self.bridges: Dict[str, Any] = {}
        self.statuses: Dict[str, BridgeStatus] = {}
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        logger.info(f"BridgeManager initialisé")

    def add_bridge(self, name: str, bridge: Any) -> bool:
        """
        Ajoute un bridge.

        Args:
            name: Nom du bridge
            bridge: Instance du bridge

        Returns:
            bool: True si ajouté
        """
        with self._lock:
            if len(self.bridges) >= self.config.max_bridges:
                logger.warning(f"Nombre maximum de bridges atteint ({self.config.max_bridges})")
                return False

            self.bridges[name] = bridge
            self.statuses[name] = BridgeStatus(
                bridge_name=name,
                is_active=True,
                last_check=datetime.now(),
                response_time=0.0,
                error_count=0,
                success_rate=1.0,
                transaction_count=0,
                volume_24h=0.0,
                status_message="Initialized",
            )

            logger.info(f"Bridge ajouté: {name}")
            return True

    def remove_bridge(self, name: str) -> bool:
        """
        Supprime un bridge.

        Args:
            name: Nom du bridge

        Returns:
            bool: True si supprimé
        """
        with self._lock:
            if name in self.bridges:
                del self.bridges[name]
                del self.statuses[name]
                logger.info(f"Bridge supprimé: {name}")
                return True

        logger.warning(f"Bridge non trouvé: {name}")
        return False

    def get_bridge(self, name: str) -> Optional[Any]:
        """
        Récupère un bridge.

        Args:
            name: Nom du bridge

        Returns:
            Optional[Any]: Instance du bridge
        """
        return self.bridges.get(name)

    def get_active_bridge(self) -> Optional[Any]:
        """
        Récupère un bridge actif (load balancing).

        Returns:
            Optional[Any]: Instance du bridge
        """
        with self._lock:
            active_bridges = [
                (name, status)
                for name, status in self.statuses.items()
                if status.is_active and name in self.bridges
            ]

            if not active_bridges:
                return None

            # Sélection du bridge avec le meilleur taux de succès
            best_bridge = max(active_bridges, key=lambda x: x[1].success_rate)
            return self.bridges[best_bridge[0]]

    def get_bridge_status(self, name: str) -> Optional[BridgeStatus]:
        """
        Récupère le statut d'un bridge.

        Args:
            name: Nom du bridge

        Returns:
            Optional[BridgeStatus]: Statut
        """
        return self.statuses.get(name)

    def get_all_statuses(self) -> Dict[str, BridgeStatus]:
        """
        Récupère tous les statuts.

        Returns:
            Dict[str, BridgeStatus]: Statuts
        """
        return self.statuses

    def start(self):
        """Démarre le gestionnaire"""
        if self.is_running:
            logger.warning("Déjà en cours d'exécution")
            return

        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

        logger.info("BridgeManager démarré")

    def stop(self):
        """Arrête le gestionnaire"""
        self.is_running = False

        if self._thread:
            self._thread.join(timeout=5)

        logger.info("BridgeManager arrêté")

    def _monitor_loop(self):
        """Boucle de monitoring"""
        while self.is_running:
            try:
                self._check_bridges()
            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")

            time.sleep(self.config.update_interval)

    def _check_bridges(self):
        """Vérifie tous les bridges"""
        for name, bridge in list(self.bridges.items()):
            try:
                status = self._check_bridge(name, bridge)
                with self._lock:
                    self.statuses[name] = status

                # Auto-recovery
                if not status.is_active and self.config.enable_auto_recovery:
                    self._recover_bridge(name, bridge)

            except Exception as e:
                logger.error(f"Erreur de vérification pour {name}: {e}")

    def _check_bridge(self, name: str, bridge: Any) -> BridgeStatus:
        """
        Vérifie un bridge individuel.

        Args:
            name: Nom du bridge
            bridge: Instance du bridge

        Returns:
            BridgeStatus: Statut
        """
        status = self.statuses.get(name)

        if status is None:
            return BridgeStatus(
                bridge_name=name,
                is_active=False,
                last_check=datetime.now(),
                response_time=0.0,
                error_count=0,
                success_rate=0.0,
                transaction_count=0,
                volume_24h=0.0,
                status_message="Not initialized",
            )

        try:
            start_time = time.time()

            # Vérification de la connexion
            if hasattr(bridge, 'get_stats'):
                stats = bridge.get_stats()
                is_active = True
                status_message = "OK"
            else:
                is_active = False
                status_message = "No stats method"

            response_time = time.time() - start_time

            # Mise à jour du statut
            return BridgeStatus(
                bridge_name=name,
                is_active=is_active,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=status.error_count,
                success_rate=stats.get('success_rate', 1.0) if is_active else 0.0,
                transaction_count=stats.get('total_transactions', 0) if is_active else 0,
                volume_24h=stats.get('total_volume', 0) if is_active else 0,
                status_message=status_message,
            )

        except Exception as e:
            logger.error(f"Erreur de vérification pour {name}: {e}")

            return BridgeStatus(
                bridge_name=name,
                is_active=False,
                last_check=datetime.now(),
                response_time=0.0,
                error_count=status.error_count + 1,
                success_rate=0.0,
                transaction_count=status.transaction_count,
                volume_24h=status.volume_24h,
                status_message=f"Error: {str(e)}",
            )

    def _recover_bridge(self, name: str, bridge: Any):
        """
        Tente de récupérer un bridge défaillant.

        Args:
            name: Nom du bridge
            bridge: Instance du bridge
        """
        logger.info(f"Tentative de récupération pour {name}")

        for attempt in range(self.config.max_retries):
            try:
                if hasattr(bridge, 'recover'):
                    bridge.recover()
                elif hasattr(bridge, 'reset'):
                    bridge.reset()

                # Vérification après récupération
                time.sleep(self.config.retry_delay)
                new_status = self._check_bridge(name, bridge)

                if new_status.is_active:
                    with self._lock:
                        self.statuses[name] = new_status
                    logger.info(f"Bridge récupéré: {name}")
                    return

            except Exception as e:
                logger.error(f"Erreur de récupération pour {name} (tentative {attempt+1}): {e}")

            time.sleep(self.config.retry_delay)

        logger.error(f"Échec de récupération pour {name}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retourne les statistiques globales.

        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            stats = {
                'total_bridges': len(self.bridges),
                'active_bridges': sum(1 for s in self.statuses.values() if s.is_active),
                'inactive_bridges': sum(1 for s in self.statuses.values() if not s.is_active),
                'total_transactions': sum(s.transaction_count for s in self.statuses.values()),
                'total_volume': sum(s.volume_24h for s in self.statuses.values()),
                'average_success_rate': np.mean([s.success_rate for s in self.statuses.values()]) if self.statuses else 0,
            }

            return stats

    def get_bridge_names(self) -> List[str]:
        """
        Retourne la liste des noms de bridges.

        Returns:
            List[str]: Liste des noms
        """
        return list(self.bridges.keys())


def create_bridge_manager(
    name: str = "bridge_manager",
    enable_monitoring: bool = True,
    enable_auto_recovery: bool = True,
    **kwargs
) -> BridgeManager:
    """
    Factory pour créer un gestionnaire de bridges.

    Args:
        name: Nom du gestionnaire
        enable_monitoring: Activer le monitoring
        enable_auto_recovery: Activer l'auto-recovery
        **kwargs: Arguments supplémentaires

    Returns:
        BridgeManager: Gestionnaire
    """
    config = BridgeManagerConfig(
        name=name,
        enable_monitoring=enable_monitoring,
        enable_auto_recovery=enable_auto_recovery,
        **kwargs
    )
    return BridgeManager(config)


__all__ = [
    'BridgeManager',
    'BridgeManagerConfig',
    'BridgeStatus',
    'create_bridge_manager',
]

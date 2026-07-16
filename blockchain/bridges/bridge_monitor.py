
# blockchain/bridges/bridge_monitor.py
"""
NEXUS AI TRADING SYSTEM - Bridge Monitor Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import time
import threading
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class BridgeMonitorConfig:
    """Configuration pour Bridge Monitor"""
    name: str = "bridge_monitor"
    check_interval: int = 60  # secondes
    history_size: int = 1000
    alert_threshold: float = 0.1  # 10% de variation
    latency_threshold: float = 5.0  # secondes
    error_threshold: int = 5
    enable_alerting: bool = True
    enable_logging: bool = True
    alert_cooldown: int = 300  # secondes

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'check_interval': self.check_interval,
            'history_size': self.history_size,
            'alert_threshold': self.alert_threshold,
            'latency_threshold': self.latency_threshold,
            'error_threshold': self.error_threshold,
            'enable_alerting': self.enable_alerting,
            'enable_logging': self.enable_logging,
            'alert_cooldown': self.alert_cooldown,
        }


@dataclass
class BridgeHealthCheck:
    """Résultat d'un health check"""
    bridge_name: str
    timestamp: datetime
    is_healthy: bool
    latency: float
    error_count: int
    success_rate: float
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bridge_name': self.bridge_name,
            'timestamp': self.timestamp.isoformat(),
            'is_healthy': self.is_healthy,
            'latency': self.latency,
            'error_count': self.error_count,
            'success_rate': self.success_rate,
            'details': self.details,
        }


@dataclass
class BridgeAlert:
    """Alerte de bridge"""
    bridge_name: str
    timestamp: datetime
    severity: str  # 'info', 'warning', 'critical'
    type: str
    message: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bridge_name': self.bridge_name,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity,
            'type': self.type,
            'message': self.message,
            'details': self.details,
        }


class BridgeMonitor:
    """
    Moniteur de bridges.

    Features:
    - Health checks automatiques
    - Alertes
    - Historique des checks
    - Métriques de performance
    - Détection d'anomalies

    Example:
        ```python
        config = BridgeMonitorConfig(
            name='arbitrum_monitor',
            check_interval=60,
            alert_threshold=0.1
        )
        monitor = BridgeMonitor(config)

        # Ajouter un bridge à surveiller
        monitor.add_bridge('arbitrum', bridge)

        # Démarrer le monitoring
        monitor.start()
        ```
    """

    def __init__(self, config: Optional[BridgeMonitorConfig] = None):
        self.config = config or BridgeMonitorConfig()
        self.bridges: Dict[str, Any] = {}
        self.health_history: Dict[str, deque] = {}
        self.alerts: List[BridgeAlert] = []
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._alert_timestamps: Dict[str, datetime] = {}

        logger.info(f"BridgeMonitor initialisé")

    def add_bridge(self, name: str, bridge: Any) -> bool:
        """
        Ajoute un bridge à surveiller.

        Args:
            name: Nom du bridge
            bridge: Instance du bridge

        Returns:
            bool: True si ajouté
        """
        with self._lock:
            self.bridges[name] = bridge
            self.health_history[name] = deque(maxlen=self.config.history_size)
            logger.info(f"Bridge ajouté au monitor: {name}")
            return True

    def remove_bridge(self, name: str) -> bool:
        """
        Supprime un bridge du monitor.

        Args:
            name: Nom du bridge

        Returns:
            bool: True si supprimé
        """
        with self._lock:
            if name in self.bridges:
                del self.bridges[name]
                del self.health_history[name]
                logger.info(f"Bridge supprimé du monitor: {name}")
                return True

        logger.warning(f"Bridge non trouvé: {name}")
        return False

    def start(self):
        """Démarre le monitoring"""
        if self.is_running:
            logger.warning("Déjà en cours d'exécution")
            return

        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

        logger.info("BridgeMonitor démarré")

    def stop(self):
        """Arrête le monitoring"""
        self.is_running = False

        if self._thread:
            self._thread.join(timeout=5)

        logger.info("BridgeMonitor arrêté")

    def _monitor_loop(self):
        """Boucle de monitoring"""
        while self.is_running:
            try:
                self._check_all_bridges()
            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")

            time.sleep(self.config.check_interval)

    def _check_all_bridges(self):
        """Vérifie tous les bridges"""
        for name, bridge in list(self.bridges.items()):
            try:
                check = self._check_bridge(name, bridge)
                with self._lock:
                    self.health_history[name].append(check)

                if not check.is_healthy and self.config.enable_alerting:
                    self._create_alert(name, check)

            except Exception as e:
                logger.error(f"Erreur de vérification pour {name}: {e}")

    def _check_bridge(self, name: str, bridge: Any) -> BridgeHealthCheck:
        """
        Vérifie un bridge individuel.

        Args:
            name: Nom du bridge
            bridge: Instance du bridge

        Returns:
            BridgeHealthCheck: Résultat du check
        """
        start_time = time.time()

        try:
            # Vérification du bridge
            if hasattr(bridge, 'get_stats'):
                stats = bridge.get_stats()
                is_healthy = stats.get('success_rate', 0) > 0.5
            elif hasattr(bridge, 'is_healthy'):
                is_healthy = bridge.is_healthy()
            else:
                is_healthy = True

            latency = time.time() - start_time

            # Calcul du taux de succès
            history = self.health_history.get(name, deque())
            success_rate = self._calculate_success_rate(history)

            return BridgeHealthCheck(
                bridge_name=name,
                timestamp=datetime.now(),
                is_healthy=is_healthy,
                latency=latency,
                error_count=0,
                success_rate=success_rate,
                details=stats if hasattr(bridge, 'get_stats') else {},
            )

        except Exception as e:
            return BridgeHealthCheck(
                bridge_name=name,
                timestamp=datetime.now(),
                is_healthy=False,
                latency=time.time() - start_time,
                error_count=1,
                success_rate=0.0,
                details={'error': str(e)},
            )

    def _calculate_success_rate(self, history: deque) -> float:
        """
        Calcule le taux de succès à partir de l'historique.

        Args:
            history: Historique des checks

        Returns:
            float: Taux de succès
        """
        if not history:
            return 1.0

        successful = sum(1 for h in history if h.is_healthy)
        return successful / len(history)

    def _create_alert(self, name: str, check: BridgeHealthCheck):
        """
        Crée une alerte pour un bridge.

        Args:
            name: Nom du bridge
            check: Résultat du health check
        """
        # Vérification du cooldown
        if name in self._alert_timestamps:
            last_alert = self._alert_timestamps[name]
            if (datetime.now() - last_alert).seconds < self.config.alert_cooldown:
                return

        # Détermination de la sévérité
        if check.success_rate < 0.5:
            severity = 'critical'
        elif check.success_rate < 0.8:
            severity = 'warning'
        else:
            severity = 'info'

        # Création de l'alerte
        alert = BridgeAlert(
            bridge_name=name,
            timestamp=datetime.now(),
            severity=severity,
            type='health_check',
            message=f"Bridge {name} - Taux de succès: {check.success_rate:.2%}",
            details={
                'latency': check.latency,
                'success_rate': check.success_rate,
                'is_healthy': check.is_healthy,
            },
        )

        self.alerts.append(alert)
        self._alert_timestamps[name] = datetime.now()

        if self.config.enable_logging:
            logger.warning(f"ALERTE [{severity}] {name}: {alert.message}")

    def get_health(self, name: str) -> Optional[BridgeHealthCheck]:
        """
        Récupère le dernier health check d'un bridge.

        Args:
            name: Nom du bridge

        Returns:
            Optional[BridgeHealthCheck]: Dernier check
        """
        history = self.health_history.get(name)
        if history:
            return history[-1]
        return None

    def get_history(self, name: str, limit: int = 100) -> List[BridgeHealthCheck]:
        """
        Récupère l'historique d'un bridge.

        Args:
            name: Nom du bridge
            limit: Nombre maximum de résultats

        Returns:
            List[BridgeHealthCheck]: Historique
        """
        history = self.health_history.get(name)
        if history:
            return list(history)[-limit:]
        return []

    def get_alerts(self, name: Optional[str] = None) -> List[BridgeAlert]:
        """
        Récupère les alertes.

        Args:
            name: Nom du bridge (optionnel)

        Returns:
            List[BridgeAlert]: Alertes
        """
        if name:
            return [a for a in self.alerts if a.bridge_name == name]
        return self.alerts

    def get_statistics(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Retourne les statistiques.

        Args:
            name: Nom du bridge (optionnel)

        Returns:
            Dict[str, Any]: Statistiques
        """
        if name:
            history = self.health_history.get(name, [])
            if history:
                return {
                    'bridge_name': name,
                    'total_checks': len(history),
                    'healthy_checks': sum(1 for h in history if h.is_healthy),
                    'success_rate': sum(1 for h in history if h.is_healthy) / len(history),
                    'average_latency': sum(h.latency for h in history) / len(history),
                    'last_check': history[-1].timestamp,
                }
            return {}

        # Statistiques globales
        stats = {
            'total_bridges': len(self.bridges),
            'monitored_bridges': list(self.bridges.keys()),
            'total_alerts': len(self.alerts),
            'alerts_by_severity': {
                'critical': sum(1 for a in self.alerts if a.severity == 'critical'),
                'warning': sum(1 for a in self.alerts if a.severity == 'warning'),
                'info': sum(1 for a in self.alerts if a.severity == 'info'),
            },
        }

        return stats

    def clear_alerts(self, name: Optional[str] = None) -> int:
        """
        Supprime les alertes.

        Args:
            name: Nom du bridge (optionnel)

        Returns:
            int: Nombre d'alertes supprimées
        """
        if name:
            before = len(self.alerts)
            self.alerts = [a for a in self.alerts if a.bridge_name != name]
            return before - len(self.alerts)

        count = len(self.alerts)
        self.alerts = []
        return count


def create_bridge_monitor(
    name: str = "bridge_monitor",
    check_interval: int = 60,
    **kwargs
) -> BridgeMonitor:
    """
    Factory pour créer un moniteur de bridge.

    Args:
        name: Nom du moniteur
        check_interval: Intervalle de vérification
        **kwargs: Arguments supplémentaires

    Returns:
        BridgeMonitor: Moniteur
    """
    config = BridgeMonitorConfig(
        name=name,
        check_interval=check_interval,
        **kwargs
    )
    return BridgeMonitor(config)


__all__ = [
    'BridgeMonitor',
    'BridgeMonitorConfig',
    'BridgeHealthCheck',
    'BridgeAlert',
    'create_bridge_monitor',
]

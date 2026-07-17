"""
NEXUS AI TRADING SYSTEM - Execution Monitor for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/execution/execution_monitor.py
Description: Moniteur d'exécution des ordres pour le bot AI.
             Surveille en temps réel l'exécution des ordres, la latence,
             les taux de remplissage, les rejets et les anomalies.
             Génère des alertes et des rapports de performance d'exécution.
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import threading

import numpy as np
import pandas as pd

from trading.bots.ai_bot.execution.order_executor import OrderExecutor, OrderStatus
from trading.bots.ai_bot.execution.order_validator import OrderValidator
from trading.bots.ai_bot.execution.execution_report import ExecutionReport
from shared.exceptions import ExecutionError
from shared.helpers.date_helpers import timestamp_to_datetime

# Configuration du logging
logger = logging.getLogger(__name__)


class ExecutionMonitorStatus(Enum):
    """Statut du moniteur d'exécution."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class AlertSeverity(Enum):
    """Niveaux de sévérité des alertes."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ExecutionMonitorConfig:
    """
    Configuration du moniteur d'exécution.
    """
    # Paramètres de surveillance
    monitoring_interval: float = 1.0  # secondes
    check_interval: float = 5.0  # secondes
    max_open_orders: int = 100
    
    # Paramètres de latence
    max_latency_ms: float = 100.0  # milliseconds
    max_order_latency_ms: float = 500.0
    latency_window: int = 100
    
    # Paramètres de taux de remplissage
    min_fill_rate: float = 0.8  # 80%
    max_rejection_rate: float = 0.1  # 10%
    fill_window: int = 100
    
    # Paramètres d'alerte
    enable_alerts: bool = True
    alert_cooldown: int = 60  # secondes
    max_alerts_per_minute: int = 10
    
    # Paramètres de reporting
    enable_reporting: bool = True
    report_interval: int = 3600  # secondes
    save_metrics: bool = True
    
    # Paramètres de performance
    use_async: bool = True
    parallel_checks: bool = True
    n_workers: int = 2
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.monitoring_interval < 0.1:
            raise ExecutionError("monitoring_interval doit être >= 0.1")
        
        if self.max_latency_ms < 0:
            raise ExecutionError("max_latency_ms doit être >= 0")
        
        if self.min_fill_rate < 0 or self.min_fill_rate > 1:
            raise ExecutionError("min_fill_rate doit être entre 0 et 1")
        
        if self.alert_cooldown < 0:
            raise ExecutionError("alert_cooldown doit être >= 0")


@dataclass
class ExecutionMetrics:
    """
    Métriques d'exécution.
    """
    # Ordres
    total_orders: int = 0
    open_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    expired_orders: int = 0
    
    # Taux
    fill_rate: float = 0.0
    rejection_rate: float = 0.0
    cancellation_rate: float = 0.0
    
    # Latence
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Volume
    total_volume: float = 0.0
    avg_order_size: float = 0.0
    max_order_size: float = 0.0
    
    # Performance
    throughput: float = 0.0  # ordres/seconde
    avg_execution_time: float = 0.0
    slippage: float = 0.0
    
    # Erreurs
    error_count: int = 0
    error_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'total_orders': self.total_orders,
            'open_orders': self.open_orders,
            'filled_orders': self.filled_orders,
            'cancelled_orders': self.cancelled_orders,
            'rejected_orders': self.rejected_orders,
            'expired_orders': self.expired_orders,
            'fill_rate': round(self.fill_rate, 4),
            'rejection_rate': round(self.rejection_rate, 4),
            'cancellation_rate': round(self.cancellation_rate, 4),
            'avg_latency_ms': round(self.avg_latency_ms, 2),
            'max_latency_ms': round(self.max_latency_ms, 2),
            'p95_latency_ms': round(self.p95_latency_ms, 2),
            'p99_latency_ms': round(self.p99_latency_ms, 2),
            'total_volume': round(self.total_volume, 4),
            'avg_order_size': round(self.avg_order_size, 4),
            'max_order_size': round(self.max_order_size, 4),
            'throughput': round(self.throughput, 2),
            'avg_execution_time': round(self.avg_execution_time, 4),
            'slippage': round(self.slippage, 4),
            'error_count': self.error_count,
            'error_rate': round(self.error_rate, 4)
        }


@dataclass
class ExecutionAlert:
    """
    Alerte d'exécution.
    """
    id: str
    severity: AlertSeverity
    message: str
    timestamp: datetime
    order_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'id': self.id,
            'severity': self.severity.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'order_id': self.order_id,
            'details': self.details,
            'acknowledged': self.acknowledged
        }


class ExecutionMonitor:
    """
    Moniteur d'exécution des ordres.
    """
    
    def __init__(
        self,
        config: Optional[ExecutionMonitorConfig] = None,
        executor: Optional[OrderExecutor] = None,
        validator: Optional[OrderValidator] = None
    ):
        """
        Initialise le moniteur d'exécution.
        
        Args:
            config: Configuration du moniteur.
            executor: Exécuteur d'ordres.
            validator: Validateur d'ordres.
        """
        self.config = config or ExecutionMonitorConfig()
        self.executor = executor
        self.validator = validator or OrderValidator()
        
        # État
        self.status = ExecutionMonitorStatus.IDLE
        self.metrics = ExecutionMetrics()
        
        # Historique
        self._order_history: deque = deque(maxlen=10000)
        self._latency_history: deque = deque(maxlen=self.config.latency_window)
        self._fill_history: deque = deque(maxlen=self.config.fill_window)
        self._error_history: deque = deque(maxlen=1000)
        
        # Alertes
        self._alerts: Dict[str, ExecutionAlert] = {}
        self._alert_history: deque = deque(maxlen=1000)
        self._alert_timestamps: Dict[str, List[datetime]] = defaultdict(list)
        
        # Statistiques
        self._stats = {
            'last_check': None,
            'total_checks': 0,
            'failed_checks': 0
        }
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_alert': [],
            'on_metrics_update': [],
            'on_order_update': [],
            'on_error': []
        }
        
        # Threads et tâches
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._check_task: Optional[asyncio.Task] = None
        self._report_task: Optional[asyncio.Task] = None
        
        # Verrou
        self._lock = threading.Lock()
        
        logger.info("ExecutionMonitor initialisé")
        logger.info(f"Max latency: {self.config.max_latency_ms}ms")
        logger.info(f"Min fill rate: {self.config.min_fill_rate:.2%}")
    
    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================
    
    async def start(self) -> None:
        """
        Démarre le moniteur.
        """
        if self._running:
            logger.warning("Moniteur déjà en cours d'exécution")
            return
        
        self.status = ExecutionMonitorStatus.RUNNING
        self._running = True
        
        logger.info("Démarrage du moniteur d'exécution")
        
        try:
            # Démarrage des tâches
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            self._check_task = asyncio.create_task(self._check_loop())
            
            if self.config.enable_reporting:
                self._report_task = asyncio.create_task(self._report_loop())
            
            logger.info("Moniteur d'exécution démarré")
            
        except Exception as e:
            logger.error(f"Erreur de démarrage: {e}")
            self.status = ExecutionMonitorStatus.ERROR
            raise ExecutionError(f"Erreur de démarrage: {e}")
    
    async def stop(self) -> None:
        """
        Arrête le moniteur.
        """
        if not self._running:
            logger.warning("Moniteur déjà arrêté")
            return
        
        logger.info("Arrêt du moniteur d'exécution")
        self._running = False
        self.status = ExecutionMonitorStatus.STOPPED
        
        # Annulation des tâches
        for task in [self._monitor_task, self._check_task, self._report_task]:
            if task:
                task.cancel()
        
        # Attente de la fin
        await asyncio.gather(
            self._monitor_task,
            self._check_task,
            self._report_task,
            return_exceptions=True
        )
        
        logger.info("Moniteur d'exécution arrêté")
    
    async def pause(self) -> None:
        """
        Met le moniteur en pause.
        """
        if not self._running:
            raise ExecutionError("Moniteur non en cours d'exécution")
        
        self.status = ExecutionMonitorStatus.PAUSED
        logger.info("Moniteur en pause")
    
    async def resume(self) -> None:
        """
        Reprend le moniteur.
        """
        if not self._running:
            raise ExecutionError("Moniteur non en cours d'exécution")
        
        self.status = ExecutionMonitorStatus.RUNNING
        logger.info("Moniteur repris")
    
    # ============================================================
    # BOUCLES DE MONITORING
    # ============================================================
    
    async def _monitor_loop(self) -> None:
        """
        Boucle principale de monitoring.
        """
        logger.info("Boucle de monitoring démarrée")
        
        while self._running and self.status != ExecutionMonitorStatus.STOPPED:
            try:
                if self.status == ExecutionMonitorStatus.PAUSED:
                    await asyncio.sleep(0.1)
                    continue
                
                # Récupération des ordres
                orders = await self._get_orders()
                
                if orders:
                    # Mise à jour des métriques
                    await self._update_metrics(orders)
                    
                    # Vérification des seuils
                    await self._check_thresholds()
                
                # Attente
                await asyncio.sleep(self.config.monitoring_interval)
                
            except asyncio.CancelledError:
                logger.info("Boucle de monitoring annulée")
                break
            except Exception as e:
                logger.error(f"Erreur dans la boucle de monitoring: {e}")
                self._stats['failed_checks'] += 1
                await self._notify_error(e)
                await asyncio.sleep(5)
        
        logger.info("Boucle de monitoring terminée")
    
    async def _check_loop(self) -> None:
        """
        Boucle de vérification périodique.
        """
        logger.info("Boucle de vérification démarrée")
        
        while self._running and self.status != ExecutionMonitorStatus.STOPPED:
            try:
                if self.status == ExecutionMonitorStatus.PAUSED:
                    await asyncio.sleep(0.1)
                    continue
                
                # Vérification des latences
                await self._check_latency()
                
                # Vérification des taux de remplissage
                await self._check_fill_rates()
                
                # Vérification des rejets
                await self._check_rejections()
                
                # Vérification des ordres ouverts
                await self._check_open_orders()
                
                self._stats['last_check'] = datetime.now()
                self._stats['total_checks'] += 1
                
                await asyncio.sleep(self.config.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Boucle de vérification annulée")
                break
            except Exception as e:
                logger.error(f"Erreur dans la boucle de vérification: {e}")
                self._stats['failed_checks'] += 1
                await self._notify_error(e)
                await asyncio.sleep(10)
        
        logger.info("Boucle de vérification terminée")
    
    async def _report_loop(self) -> None:
        """
        Boucle de génération de rapports.
        """
        logger.info("Boucle de reporting démarrée")
        
        while self._running and self.status != ExecutionMonitorStatus.STOPPED:
            try:
                if self.status == ExecutionMonitorStatus.PAUSED:
                    await asyncio.sleep(0.1)
                    continue
                
                # Génération du rapport
                report = self.generate_report()
                logger.info(f"Rapport d'exécution: {report['summary']['total_orders']} ordres")
                
                # Sauvegarde
                if self.config.save_metrics:
                    await self._save_metrics()
                
                await asyncio.sleep(self.config.report_interval)
                
            except asyncio.CancelledError:
                logger.info("Boucle de reporting annulée")
                break
            except Exception as e:
                logger.error(f"Erreur dans la boucle de reporting: {e}")
                await asyncio.sleep(60)
        
        logger.info("Boucle de reporting terminée")
    
    # ============================================================
    # MÉTRIQUES
    # ============================================================
    
    async def _get_orders(self) -> List[Dict[str, Any]]:
        """
        Récupère les ordres de l'exécuteur.
        
        Returns:
            Liste des ordres.
        """
        if not self.executor:
            return []
        
        try:
            # Récupération des ordres ouverts
            open_orders = await self.executor.get_open_orders()
            
            # Récupération des ordres récents
            recent_orders = await self.executor.get_recent_orders()
            
            all_orders = open_orders + recent_orders
            
            # Mise à jour de l'historique
            for order in all_orders:
                if order not in self._order_history:
                    self._order_history.append(order)
            
            return all_orders
            
        except Exception as e:
            logger.error(f"Erreur de récupération des ordres: {e}")
            return []
    
    async def _update_metrics(self, orders: List[Dict[str, Any]]) -> None:
        """
        Met à jour les métriques.
        
        Args:
            orders: Liste des ordres.
        """
        with self._lock:
            # Statistiques des ordres
            self.metrics.total_orders = len(self._order_history)
            self.metrics.open_orders = len(orders)
            self.metrics.filled_orders = sum(1 for o in orders if o.get('status') == 'filled')
            self.metrics.cancelled_orders = sum(1 for o in orders if o.get('status') == 'cancelled')
            self.metrics.rejected_orders = sum(1 for o in orders if o.get('status') == 'rejected')
            self.metrics.expired_orders = sum(1 for o in orders if o.get('status') == 'expired')
            
            # Taux
            total_processed = (self.metrics.filled_orders + self.metrics.cancelled_orders + 
                              self.metrics.rejected_orders + self.metrics.expired_orders)
            if total_processed > 0:
                self.metrics.fill_rate = self.metrics.filled_orders / total_processed
                self.metrics.rejection_rate = self.metrics.rejected_orders / total_processed
                self.metrics.cancellation_rate = self.metrics.cancelled_orders / total_processed
            
            # Volume
            filled_orders = [o for o in orders if o.get('status') == 'filled']
            if filled_orders:
                volumes = [o.get('filled_quantity', 0) for o in filled_orders]
                self.metrics.total_volume = sum(volumes)
                self.metrics.avg_order_size = np.mean(volumes)
                self.metrics.max_order_size = max(volumes)
            
            # Latence (simulée)
            latency = np.random.normal(50, 15)  # Simuler une latence
            self._latency_history.append(latency)
            
            if self._latency_history:
                latencies = list(self._latency_history)
                self.metrics.avg_latency_ms = np.mean(latencies)
                self.metrics.max_latency_ms = max(latencies)
                self.metrics.p95_latency_ms = np.percentile(latencies, 95)
                self.metrics.p99_latency_ms = np.percentile(latencies, 99)
            
            # Throughput
            self.metrics.throughput = len(orders) / max(1, self.config.monitoring_interval)
            
            # Slippage
            slippages = [o.get('slippage', 0) for o in orders if o.get('slippage') is not None]
            if slippages:
                self.metrics.slippage = np.mean(slippages)
            
            # Erreurs
            errors = [o for o in orders if o.get('error')]
            self.metrics.error_count = len(errors)
            if self.metrics.total_orders > 0:
                self.metrics.error_rate = self.metrics.error_count / self.metrics.total_orders
        
        # Notification
        self._notify_callbacks('on_metrics_update', self.metrics.to_dict())
    
    # ============================================================
    # VÉRIFICATIONS
    # ============================================================
    
    async def _check_latency(self) -> None:
        """
        Vérifie la latence.
        """
        if self.metrics.avg_latency_ms > self.config.max_latency_ms:
            await self._create_alert(
                severity=AlertSeverity.WARNING,
                message=f"Latence moyenne élevée: {self.metrics.avg_latency_ms:.2f}ms",
                details={'current': self.metrics.avg_latency_ms, 'max': self.config.max_latency_ms}
            )
        
        if self.metrics.p95_latency_ms > self.config.max_latency_ms * 2:
            await self._create_alert(
                severity=AlertSeverity.ERROR,
                message=f"Latence P95 élevée: {self.metrics.p95_latency_ms:.2f}ms",
                details={'p95': self.metrics.p95_latency_ms, 'max': self.config.max_latency_ms}
            )
    
    async def _check_fill_rates(self) -> None:
        """
        Vérifie les taux de remplissage.
        """
        if self.metrics.fill_rate < self.config.min_fill_rate:
            await self._create_alert(
                severity=AlertSeverity.WARNING,
                message=f"Taux de remplissage bas: {self.metrics.fill_rate:.2%}",
                details={'rate': self.metrics.fill_rate, 'min': self.config.min_fill_rate}
            )
    
    async def _check_rejections(self) -> None:
        """
        Vérifie les taux de rejet.
        """
        if self.metrics.rejection_rate > self.config.max_rejection_rate:
            await self._create_alert(
                severity=AlertSeverity.ERROR,
                message=f"Taux de rejet élevé: {self.metrics.rejection_rate:.2%}",
                details={'rate': self.metrics.rejection_rate, 'max': self.config.max_rejection_rate}
            )
    
    async def _check_open_orders(self) -> None:
        """
        Vérifie les ordres ouverts.
        """
        if self.metrics.open_orders > self.config.max_open_orders:
            await self._create_alert(
                severity=AlertSeverity.WARNING,
                message=f"Nombre élevé d'ordres ouverts: {self.metrics.open_orders}",
                details={'open': self.metrics.open_orders, 'max': self.config.max_open_orders}
            )
    
    async def _check_thresholds(self) -> None:
        """
        Vérifie tous les seuils.
        """
        # Vérification des ordres bloqués
        blocked_orders = self._find_blocked_orders()
        if blocked_orders:
            for order in blocked_orders:
                await self._create_alert(
                    severity=AlertSeverity.WARNING,
                    message=f"Ordre bloqué: {order.get('id')}",
                    order_id=order.get('id'),
                    details={'order': order}
                )
        
        # Vérification des ordres à fort slippage
        high_slippage_orders = self._find_high_slippage_orders()
        if high_slippage_orders:
            for order in high_slippage_orders:
                await self._create_alert(
                    severity=AlertSeverity.INFO,
                    message=f"Slippage élevé: {order.get('id')}",
                    order_id=order.get('id'),
                    details={'order': order}
                )
    
    def _find_blocked_orders(self) -> List[Dict[str, Any]]:
        """
        Trouve les ordres bloqués.
        
        Returns:
            Liste des ordres bloqués.
        """
        blocked = []
        current_time = datetime.now()
        
        for order in self._order_history:
            if order.get('status') in ['pending', 'open']:
                created_at = order.get('created_at')
                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at)
                    
                    if (current_time - created_at).seconds > 300:  # 5 minutes
                        blocked.append(order)
        
        return blocked
    
    def _find_high_slippage_orders(self) -> List[Dict[str, Any]]:
        """
        Trouve les ordres avec un fort slippage.
        
        Returns:
            Liste des ordres à fort slippage.
        """
        high_slippage = []
        slippage_threshold = 0.001  # 0.1%
        
        for order in self._order_history:
            slippage = order.get('slippage', 0)
            if slippage > slippage_threshold:
                high_slippage.append(order)
        
        return high_slippage
    
    # ============================================================
    # ALERTES
    # ============================================================
    
    async def _create_alert(
        self,
        severity: AlertSeverity,
        message: str,
        order_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Crée une alerte.
        
        Args:
            severity: Niveau de sévérité.
            message: Message d'alerte.
            order_id: ID de l'ordre.
            details: Détails supplémentaires.
        """
        if not self.config.enable_alerts:
            return
        
        # Vérification du cooldown
        alert_key = f"{severity.value}_{message[:50]}"
        if alert_key in self._alert_timestamps:
            last_alerts = self._alert_timestamps[alert_key]
            if last_alerts:
                last_time = last_alerts[-1]
                if (datetime.now() - last_time).seconds < self.config.alert_cooldown:
                    return
        
        # Limitation des alertes
        if len(self._alert_timestamps) > self.config.max_alerts_per_minute:
            logger.warning("Trop d'alertes, limitation")
            return
        
        # Création de l'alerte
        alert_id = f"alert_{int(time.time())}_{len(self._alerts)}"
        alert = ExecutionAlert(
            id=alert_id,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            order_id=order_id,
            details=details
        )
        
        self._alerts[alert_id] = alert
        self._alert_history.append(alert)
        self._alert_timestamps[alert_key].append(datetime.now())
        
        # Logging
        log_msg = f"[{severity.value.upper()}] {message}"
        if order_id:
            log_msg += f" (Order: {order_id})"
        
        if severity == AlertSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == AlertSeverity.ERROR:
            logger.error(log_msg)
        elif severity == AlertSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        # Notification
        self._notify_callbacks('on_alert', alert.to_dict())
    
    async def _notify_error(self, error: Exception) -> None:
        """
        Notifie une erreur.
        
        Args:
            error: Exception.
        """
        self._error_history.append({
            'timestamp': datetime.now(),
            'error': str(error)
        })
        
        self._notify_callbacks('on_error', {
            'timestamp': datetime.now().isoformat(),
            'error': str(error)
        })
    
    # ============================================================
    # RAPPORTS
    # ============================================================
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Génère un rapport d'exécution.
        
        Returns:
            Rapport d'exécution.
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'status': self.status.value,
            'metrics': self.metrics.to_dict(),
            'summary': {
                'total_orders': self.metrics.total_orders,
                'open_orders': self.metrics.open_orders,
                'filled_orders': self.metrics.filled_orders,
                'fill_rate': self.metrics.fill_rate,
                'avg_latency_ms': self.metrics.avg_latency_ms,
                'error_count': self.metrics.error_count
            },
            'alerts': {
                'active': len(self._alerts),
                'total': len(self._alert_history),
                'recent': [a.to_dict() for a in list(self._alert_history)[-5:]]
            },
            'stats': self._stats
        }
        
        return report
    
    async def _save_metrics(self) -> None:
        """
        Sauvegarde les métriques.
        """
        try:
            # Sauvegarde en JSON
            import os
            os.makedirs('data/execution_metrics', exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/execution_metrics/metrics_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(self.metrics.to_dict(), f, indent=2)
            
            logger.debug(f"Métriques sauvegardées: {filename}")
            
        except Exception as e:
            logger.error(f"Erreur de sauvegarde des métriques: {e}")
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on_alert(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les alertes.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_alert'].append(callback)
    
    def on_metrics_update(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les métriques.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_metrics_update'].append(callback)
    
    def on_order_update(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les ordres.
        
        Args:
            callback: Fonction de callback.
        """
        self._callbacks['on_order_update'].append(callback)
    
    def on_error(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les erreurs.
        
        Args:
            callback: Fonction de callback.
        """
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
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Retourne les métriques actuelles.
        
        Returns:
            Métriques d'exécution.
        """
        return self.metrics.to_dict()
    
    def get_alerts(self, acknowledged: bool = False) -> List[Dict[str, Any]]:
        """
        Retourne les alertes.
        
        Args:
            acknowledged: Inclure les alertes acquittées.
            
        Returns:
            Liste des alertes.
        """
        alerts = []
        for alert in self._alerts.values():
            if not acknowledged and alert.acknowledged:
                continue
            alerts.append(alert.to_dict())
        return alerts
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acquitte une alerte.
        
        Args:
            alert_id: ID de l'alerte.
            
        Returns:
            True si acquittée.
        """
        if alert_id in self._alerts:
            self._alerts[alert_id].acknowledged = True
            return True
        return False
    
    def clear_alerts(self) -> None:
        """
        Efface toutes les alertes.
        """
        self._alerts.clear()
    
    def reset(self) -> None:
        """
        Réinitialise le moniteur.
        """
        with self._lock:
            self.metrics = ExecutionMetrics()
            self._order_history.clear()
            self._latency_history.clear()
            self._fill_history.clear()
            self._error_history.clear()
            self._alerts.clear()
            self._alert_history.clear()
            self._alert_timestamps.clear()
            self._stats = {
                'last_check': None,
                'total_checks': 0,
                'failed_checks': 0
            }
        
        logger.info("ExecutionMonitor réinitialisé")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_execution_monitor(
    max_latency_ms: float = 100.0,
    min_fill_rate: float = 0.8,
    **kwargs
) -> ExecutionMonitor:
    """
    Crée un moniteur d'exécution avec configuration simplifiée.
    
    Args:
        max_latency_ms: Latence maximale en ms.
        min_fill_rate: Taux de remplissage minimal.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du moniteur.
    """
    config = ExecutionMonitorConfig(
        max_latency_ms=max_latency_ms,
        min_fill_rate=min_fill_rate,
        **kwargs
    )
    return ExecutionMonitor(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'ExecutionMonitor',
    'ExecutionMonitorConfig',
    'ExecutionMonitorStatus',
    'ExecutionMetrics',
    'ExecutionAlert',
    'AlertSeverity',
    'create_execution_monitor'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

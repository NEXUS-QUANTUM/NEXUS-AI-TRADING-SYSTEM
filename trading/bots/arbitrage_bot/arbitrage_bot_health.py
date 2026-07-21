"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Health Check
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Health check et monitoring pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import psutil
import platform
import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
import socket
import subprocess
import threading
from dataclasses import dataclass, field

# Imports internes
from .core.exchange_manager import ExchangeManager
from .core.data_manager import DataManager
from .core.cache_manager import CacheManager

from .utils import (
    get_cache_manager,
    get_lock_manager,
    get_queue_manager,
    get_pool_manager,
    get_thread_manager,
)

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class HealthCheckResult:
    """Résultat d'un health check"""
    name: str
    status: str  # healthy, warning, critical, unknown
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0

@dataclass
class SystemInfo:
    """Informations système"""
    os: str
    os_version: str
    hostname: str
    architecture: str
    python_version: str
    processor: str
    cpu_count: int
    memory_total: float  # MB
    memory_available: float  # MB
    memory_usage: float  # %
    disk_usage: float  # %
    uptime: float  # seconds
    load_avg: Tuple[float, float, float]

# ============================================================
# HEALTH CHECKER
# ============================================================

class ArbitrageBotHealth:
    """
    Health check pour le bot d'arbitrage
    
    Surveille l'état du bot, des composants, du système
    et génère des alertes en cas de problème
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        check_interval: int = 30,
        memory_threshold: float = 80.0,
        cpu_threshold: float = 80.0,
        disk_threshold: float = 80.0,
        exchange_timeout: int = 10,
        enable_metrics: bool = True
    ):
        """
        Initialise le health checker
        
        Args:
            config_path: Chemin de la configuration
            check_interval: Intervalle de vérification
            memory_threshold: Seuil de mémoire (%)
            cpu_threshold: Seuil de CPU (%)
            disk_threshold: Seuil de disque (%)
            exchange_timeout: Timeout des exchanges
            enable_metrics: Activer les métriques
        """
        self.config_path = config_path or "config/arbitrage_config.yaml"
        self.check_interval = check_interval
        self.memory_threshold = memory_threshold
        self.cpu_threshold = cpu_threshold
        self.disk_threshold = disk_threshold
        self.exchange_timeout = exchange_timeout
        self.enable_metrics = enable_metrics
        
        # Configuration
        self.config = None
        self._load_config()
        
        # Composants
        self._init_components()
        
        # Cache
        self.cache = get_cache_manager()
        
        # État
        self._running = False
        self._check_task = None
        self._results: List[HealthCheckResult] = []
        self._alerts: List[Dict[str, Any]] = []
        
        # Statistiques
        self.stats = {
            'total_checks': 0,
            'healthy': 0,
            'warning': 0,
            'critical': 0,
            'unknown': 0,
            'last_check': None,
            'check_duration': 0,
        }
        
        # Système info
        self.system_info = self._get_system_info()
        
        logger.info("Health checker initialized")
    
    def _load_config(self):
        """Charge la configuration"""
        try:
            loader = ConfigLoader(self.config_path)
            self.config = loader.load()
            logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _init_components(self):
        """Initialise les composants"""
        self.components = {
            'exchange_manager': ExchangeManager(self.config),
            'data_manager': DataManager(),
        }
        
        # Connecter les exchanges
        self.components['exchange_manager'].connect_all()
        
        logger.info("Components initialized")
    
    def _get_system_info(self) -> SystemInfo:
        """Récupère les informations système"""
        return SystemInfo(
            os=platform.system(),
            os_version=platform.version(),
            hostname=socket.gethostname(),
            architecture=platform.machine(),
            python_version=sys.version,
            processor=platform.processor(),
            cpu_count=psutil.cpu_count(),
            memory_total=psutil.virtual_memory().total / (1024 * 1024),
            memory_available=psutil.virtual_memory().available / (1024 * 1024),
            memory_usage=psutil.virtual_memory().percent,
            disk_usage=psutil.disk_usage('/').percent,
            uptime=time.time() - psutil.boot_time(),
            load_avg=psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0.0, 0.0, 0.0),
        )
    
    # ============================================================
    # CHECK METHODS
    # ============================================================
    
    async def check_system(self) -> HealthCheckResult:
        """
        Vérifie le système
        
        Returns:
            HealthCheckResult: Résultat du check
        """
        start_time = time.time()
        details = {}
        status = 'healthy'
        messages = []
        
        try:
            # CPU
            cpu_usage = psutil.cpu_percent(interval=1)
            details['cpu_usage'] = cpu_usage
            if cpu_usage > self.cpu_threshold:
                status = 'warning'
                messages.append(f"CPU usage high: {cpu_usage:.1f}%")
            
            # Mémoire
            memory = psutil.virtual_memory()
            details['memory_usage'] = memory.percent
            details['memory_available'] = memory.available / (1024 * 1024)
            if memory.percent > self.memory_threshold:
                status = 'warning'
                messages.append(f"Memory usage high: {memory.percent:.1f}%")
            
            # Disque
            disk = psutil.disk_usage('/')
            details['disk_usage'] = disk.percent
            if disk.percent > self.disk_threshold:
                status = 'warning'
                messages.append(f"Disk usage high: {disk.percent:.1f}%")
            
            # Processus
            process = psutil.Process()
            details['process_memory'] = process.memory_info().rss / (1024 * 1024)
            details['process_cpu'] = process.cpu_percent(interval=0.5)
            details['threads'] = process.num_threads()
            details['open_files'] = len(process.open_files())
            details['connections'] = len(process.connections())
            
        except Exception as e:
            status = 'unknown'
            messages.append(f"System check error: {e}")
        
        return HealthCheckResult(
            name='system',
            status=status,
            message='; '.join(messages) if messages else 'System is healthy',
            details=details,
            duration=time.time() - start_time
        )
    
    async def check_exchanges(self) -> HealthCheckResult:
        """
        Vérifie les exchanges
        
        Returns:
            HealthCheckResult: Résultat du check
        """
        start_time = time.time()
        details = {}
        status = 'healthy'
        messages = []
        
        try:
            exchanges = self.components['exchange_manager'].get_exchanges()
            
            for exchange in exchanges:
                exchange_name = exchange.name
                try:
                    # Vérifier la connexion
                    is_connected = await asyncio.wait_for(
                        exchange.is_connected(),
                        timeout=self.exchange_timeout
                    )
                    
                    details[exchange_name] = {
                        'connected': is_connected,
                        'symbols': len(exchange.get_symbols()),
                    }
                    
                    if not is_connected:
                        status = 'warning' if status != 'critical' else status
                        messages.append(f"Exchange {exchange_name} is disconnected")
                
                except asyncio.TimeoutError:
                    status = 'warning' if status != 'critical' else status
                    messages.append(f"Exchange {exchange_name} timeout")
                    details[exchange_name] = {'error': 'timeout'}
                
                except Exception as e:
                    status = 'critical'
                    messages.append(f"Exchange {exchange_name} error: {e}")
                    details[exchange_name] = {'error': str(e)}
            
        except Exception as e:
            status = 'unknown'
            messages.append(f"Exchanges check error: {e}")
        
        return HealthCheckResult(
            name='exchanges',
            status=status,
            message='; '.join(messages) if messages else 'All exchanges are healthy',
            details=details,
            duration=time.time() - start_time
        )
    
    async def check_database(self) -> HealthCheckResult:
        """
        Vérifie la base de données
        
        Returns:
            HealthCheckResult: Résultat du check
        """
        start_time = time.time()
        details = {}
        status = 'healthy'
        messages = []
        
        try:
            # Vérifier la connexion à la base de données
            if self.config.database.enabled:
                # Simuler une vérification de base de données
                # En production, faire une requête réelle
                details['enabled'] = True
                details['type'] = self.config.database.type
                details['host'] = self.config.database.host
                details['port'] = self.config.database.port
                details['name'] = self.config.database.name
                
                # Vérifier la connexion
                # await self._check_db_connection()
                
            else:
                details['enabled'] = False
                messages.append("Database is disabled")
            
        except Exception as e:
            status = 'critical'
            messages.append(f"Database error: {e}")
        
        return HealthCheckResult(
            name='database',
            status=status,
            message='; '.join(messages) if messages else 'Database is healthy',
            details=details,
            duration=time.time() - start_time
        )
    
    async def check_cache(self) -> HealthCheckResult:
        """
        Vérifie le cache
        
        Returns:
            HealthCheckResult: Résultat du check
        """
        start_time = time.time()
        details = {}
        status = 'healthy'
        messages = []
        
        try:
            # Vérifier le cache
            if self.cache:
                stats = self.cache.get_stats()
                details['size'] = stats.get('size', 0)
                details['hits'] = stats.get('hits', 0)
                details['misses'] = stats.get('misses', 0)
                details['hit_rate'] = stats.get('hit_rate', 0)
                
                if details['hit_rate'] < 0.5:
                    status = 'warning'
                    messages.append(f"Cache hit rate low: {details['hit_rate']:.1%}")
            else:
                status = 'unknown'
                messages.append("Cache is not available")
            
        except Exception as e:
            status = 'unknown'
            messages.append(f"Cache check error: {e}")
        
        return HealthCheckResult(
            name='cache',
            status=status,
            message='; '.join(messages) if messages else 'Cache is healthy',
            details=details,
            duration=time.time() - start_time
        )
    
    async def check_queues(self) -> HealthCheckResult:
        """
        Vérifie les files d'attente
        
        Returns:
            HealthCheckResult: Résultat du check
        """
        start_time = time.time()
        details = {}
        status = 'healthy'
        messages = []
        
        try:
            queue_manager = get_queue_manager()
            if queue_manager:
                stats = queue_manager.get_stats()
                details['total_queues'] = stats.get('total_queues', 0)
                details['total_items'] = stats.get('total_items', 0)
                
                for name, queue_stats in stats.get('queues', {}).items():
                    details[name] = {
                        'size': queue_stats.get('size', 0),
                        'max_size': queue_stats.get('max_size', 0),
                    }
                    
                    if queue_stats.get('size', 0) > 0.8 * queue_stats.get('max_size', 1):
                        status = 'warning'
                        messages.append(f"Queue {name} is nearly full")
            else:
                status = 'unknown'
                messages.append("Queue manager is not available")
            
        except Exception as e:
            status = 'unknown'
            messages.append(f"Queues check error: {e}")
        
        return HealthCheckResult(
            name='queues',
            status=status,
            message='; '.join(messages) if messages else 'Queues are healthy',
            details=details,
            duration=time.time() - start_time
        )
    
    async def check_pools(self) -> HealthCheckResult:
        """
        Vérifie les pools
        
        Returns:
            HealthCheckResult: Résultat du check
        """
        start_time = time.time()
        details = {}
        status = 'healthy'
        messages = []
        
        try:
            pool_manager = get_pool_manager()
            if pool_manager:
                stats = pool_manager.get_stats()
                details['total_pools'] = stats.get('total_pools', 0)
                details['total_objects'] = stats.get('total_objects', 0)
                
                for name, pool_stats in stats.get('pools', {}).items():
                    details[name] = {
                        'size': pool_stats.get('size', 0),
                        'active': pool_stats.get('active', 0),
                        'idle': pool_stats.get('idle', 0),
                    }
                    
                    if pool_stats.get('size', 0) == 0:
                        status = 'warning'
                        messages.append(f"Pool {name} is empty")
            else:
                status = 'unknown'
                messages.append("Pool manager is not available")
            
        except Exception as e:
            status = 'unknown'
            messages.append(f"Pools check error: {e}")
        
        return HealthCheckResult(
            name='pools',
            status=status,
            message='; '.join(messages) if messages else 'Pools are healthy',
            details=details,
            duration=time.time() - start_time
        )
    
    async def check_threads(self) -> HealthCheckResult:
        """
        Vérifie les threads
        
        Returns:
            HealthCheckResult: Résultat du check
        """
        start_time = time.time()
        details = {}
        status = 'healthy'
        messages = []
        
        try:
            thread_manager = get_thread_manager()
            if thread_manager:
                stats = thread_manager.get_stats()
                details['total_threads'] = stats.get('total_threads', 0)
                details['total_pools'] = stats.get('total_pools', 0)
                details['active_threads'] = stats.get('active_threads', 0)
                details['idle_threads'] = stats.get('idle_threads', 0)
                
                if stats.get('active_threads', 0) == 0:
                    status = 'warning'
                    messages.append("No active threads")
            else:
                status = 'unknown'
                messages.append("Thread manager is not available")
            
        except Exception as e:
            status = 'unknown'
            messages.append(f"Threads check error: {e}")
        
        return HealthCheckResult(
            name='threads',
            status=status,
            message='; '.join(messages) if messages else 'Threads are healthy',
            details=details,
            duration=time.time() - start_time
        )
    
    # ============================================================
    # MAIN CHECKS
    # ============================================================
    
    async def run_all_checks(self) -> List[HealthCheckResult]:
        """
        Exécute tous les checks
        
        Returns:
            List[HealthCheckResult]: Résultats des checks
        """
        start_time = time.time()
        results = []
        
        # Checks système
        results.append(await self.check_system())
        
        # Checks composants
        results.append(await self.check_exchanges())
        results.append(await self.check_database())
        results.append(await self.check_cache())
        results.append(await self.check_queues())
        results.append(await self.check_pools())
        results.append(await self.check_threads())
        
        # Mettre à jour les statistiques
        self.stats['total_checks'] += 1
        self.stats['last_check'] = datetime.now().isoformat()
        self.stats['check_duration'] = time.time() - start_time
        
        # Compteurs
        for result in results:
            if result.status == 'healthy':
                self.stats['healthy'] += 1
            elif result.status == 'warning':
                self.stats['warning'] += 1
            elif result.status == 'critical':
                self.stats['critical'] += 1
            else:
                self.stats['unknown'] += 1
        
        # Stocker les résultats
        self._results = results
        
        # Générer des alertes
        for result in results:
            if result.status in ['warning', 'critical']:
                self._alerts.append({
                    'timestamp': datetime.now().isoformat(),
                    'check': result.name,
                    'status': result.status,
                    'message': result.message,
                    'details': result.details,
                })
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """
        Récupère le statut global
        
        Returns:
            Dict[str, Any]: Statut global
        """
        if not self._results:
            return {
                'status': 'unknown',
                'message': 'No checks performed',
            }
        
        # Déterminer le statut global
        statuses = [r.status for r in self._results]
        if 'critical' in statuses:
            status = 'critical'
        elif 'warning' in statuses:
            status = 'warning'
        elif all(s == 'healthy' for s in statuses):
            status = 'healthy'
        else:
            status = 'unknown'
        
        return {
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'results': [r.__dict__ for r in self._results],
            'system_info': self.system_info.__dict__,
            'stats': self.stats,
            'alerts': self._alerts[-10:],  # Dernières 10 alertes
        }
    
    # ============================================================
    # CONTINUOUS MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring continu"""
        if self._running:
            logger.warning("Health checker already running")
            return
        
        self._running = True
        self._check_task = asyncio.create_task(self._monitor_loop())
        
        logger.info("Health checker started")
    
    def stop(self):
        """Arrête le monitoring continu"""
        if not self._running:
            logger.warning("Health checker not running")
            return
        
        self._running = False
        
        if self._check_task:
            self._check_task.cancel()
            self._check_task = None
        
        logger.info("Health checker stopped")
    
    async def _monitor_loop(self):
        """Boucle de monitoring"""
        while self._running:
            try:
                await self.run_all_checks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(self.check_interval)
    
    # ============================================================
    # ALERT GENERATION
    # ============================================================
    
    def get_alerts(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Récupère les alertes
        
        Args:
            severity: Sévérité ('warning', 'critical')
            
        Returns:
            List[Dict[str, Any]]: Alertes
        """
        alerts = self._alerts.copy()
        
        if severity:
            alerts = [a for a in alerts if a.get('status') == severity]
        
        return alerts

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot Health Check")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default="config/arbitrage_config.yaml"
    )
    parser.add_argument(
        "-i", "--interval",
        help="Check interval in seconds",
        type=int,
        default=30
    )
    parser.add_argument(
        "--once",
        help="Run once and exit",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Créer le health checker
    health = ArbitrageBotHealth(
        config_path=args.config,
        check_interval=args.interval
    )
    
    async def run():
        if args.once:
            results = await health.run_all_checks()
            print("\n" + "=" * 60)
            print("HEALTH CHECK RESULTS")
            print("=" * 60)
            for result in results:
                status_emoji = {
                    'healthy': '✅',
                    'warning': '⚠️',
                    'critical': '❌',
                    'unknown': '❓'
                }.get(result.status, '❓')
                print(f"{status_emoji} {result.name:12s} {result.status:10s} {result.message}")
            print("=" * 60)
        else:
            health.start()
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
            health.stop()
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopping health checker...")

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ArbitrageBotHealth',
    'HealthCheckResult',
    'SystemInfo',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()

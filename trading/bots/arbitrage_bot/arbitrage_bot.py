"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Main Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Module principal du bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import signal
import sys
import os
import time
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
import threading
import uuid

# Import des modules internes
from .config import ConfigLoader, FullConfig
from .core.arbitrage_engine import ArbitrageEngine
from .core.exchange_manager import ExchangeManager
from .core.strategy_manager import StrategyManager
from .core.risk_manager import RiskManager
from .core.execution_engine import ExecutionEngine
from .core.market_data import MarketData
from .core.notification_manager import NotificationManager
from .core.data_manager import DataManager
from .core.event_manager import EventManager
from .core.cache_manager import CacheManager
from .core.metrics_collector import MetricsCollector
from .core.health_check import HealthCheck
from .core.scheduler import Scheduler
from .core.lock_manager import LockManager

from .utils import (
    async_retry,
    async_timeout,
    get_event_loop_manager,
    get_cache_manager,
    get_lock_manager,
    get_thread_manager,
    get_pool_manager,
    get_queue_manager,
    get_timer_manager,
    Logger,
    setup_logging,
)

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================
DEFAULT_CONFIG_PATH = "config/arbitrage_config.yaml"
DEFAULT_ENV = "production"
VERSION = "2.0.0"

# ============================================================
# ARBITRAGE BOT
# ============================================================

class ArbitrageBot:
    """
    Bot d'arbitrage principal
    
    Coordonne tous les composants du système d'arbitrage
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        env: Optional[str] = None,
        debug: bool = False,
        **kwargs
    ):
        """
        Initialise le bot d'arbitrage
        
        Args:
            config_path: Chemin du fichier de configuration
            env: Environnement (development, staging, production)
            debug: Mode debug
            **kwargs: Arguments supplémentaires
        """
        self.instance_id = str(uuid.uuid4())[:8]
        self.start_time = None
        self._running = False
        self._initialized = False
        self._components: Dict[str, Any] = {}
        self._tasks: List[asyncio.Task] = []
        self._lock = threading.RLock()
        
        # Configuration
        self.config_path = config_path or os.environ.get(
            "NEXUS_CONFIG_PATH", DEFAULT_CONFIG_PATH
        )
        self.env = env or os.environ.get("NEXUS_ENV", DEFAULT_ENV)
        self.debug = debug or os.environ.get("NEXUS_DEBUG", "false").lower() == "true"
        
        # Configuration
        self.config = None
        self._load_config()
        
        # Composants
        self._init_components()
        
        # Gestion des signaux
        self._setup_signal_handlers()
        
        logger.info(f"ArbitrageBot initialized (instance: {self.instance_id}, env: {self.env})")
    
    def _load_config(self):
        """Charge la configuration"""
        try:
            loader = ConfigLoader(self.config_path)
            self.config = loader.load()
            
            # Override env
            if self.env:
                self.config.bot.environment = self.env
            
            # Override debug
            if self.debug:
                self.config.general.debug = True
                self.config.general.log_level = "debug"
            
            logger.info(f"Configuration loaded from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _init_components(self):
        """Initialise les composants"""
        self._components = {}
        
        # 1. Cache Manager
        self._components['cache_manager'] = get_cache_manager()
        
        # 2. Lock Manager
        self._components['lock_manager'] = get_lock_manager()
        
        # 3. Thread Manager
        self._components['thread_manager'] = get_thread_manager()
        
        # 4. Pool Manager
        self._components['pool_manager'] = get_pool_manager()
        
        # 5. Queue Manager
        self._components['queue_manager'] = get_queue_manager()
        
        # 6. Timer Manager
        self._components['timer_manager'] = get_timer_manager()
        
        # 7. Event Loop Manager
        self._components['event_loop_manager'] = get_event_loop_manager()
        
        # 8. Event Manager
        self._components['event_manager'] = EventManager()
        
        # 9. Data Manager
        self._components['data_manager'] = DataManager()
        
        # 10. Market Data
        self._components['market_data'] = MarketData(self.config)
        
        # 11. Exchange Manager
        self._components['exchange_manager'] = ExchangeManager(self.config)
        
        # 12. Strategy Manager
        self._components['strategy_manager'] = StrategyManager(self.config)
        
        # 13. Risk Manager
        self._components['risk_manager'] = RiskManager(self.config)
        
        # 14. Execution Engine
        self._components['execution_engine'] = ExecutionEngine(self.config)
        
        # 15. Arbitrage Engine
        self._components['arbitrage_engine'] = ArbitrageEngine(self.config)
        
        # 16. Notification Manager
        self._components['notification_manager'] = NotificationManager(self.config)
        
        # 17. Metrics Collector
        self._components['metrics_collector'] = MetricsCollector(self.config)
        
        # 18. Health Check
        self._components['health_check'] = HealthCheck(self.config)
        
        # 19. Scheduler
        self._components['scheduler'] = Scheduler(self.config)
        
        # 20. Logger
        self._components['logger'] = logger
        
        self._initialized = True
        logger.info("All components initialized")
    
    def _setup_signal_handlers(self):
        """Configure les gestionnaires de signaux"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if sys.platform != 'win32':
            signal.signal(signal.SIGHUP, signal_handler)
    
    # ============================================================
    # LIFECYCLE METHODS
    # ============================================================
    
    def start(self):
        """Démarre le bot"""
        if self._running:
            logger.warning("Bot is already running")
            return
        
        try:
            self.start_time = datetime.now()
            self._running = True
            
            # Démarrer les composants
            logger.info("Starting ArbitrageBot...")
            
            # Démarrer le scheduler
            self._components['scheduler'].start()
            
            # Démarrer le market data
            self._components['market_data'].start()
            
            # Démarrer les exchanges
            self._components['exchange_manager'].connect_all()
            
            # Démarrer les stratégies
            self._components['strategy_manager'].start_all()
            
            # Démarrer l'arbitrage engine
            self._components['arbitrage_engine'].start()
            
            # Démarrer le metrics collector
            self._components['metrics_collector'].start()
            
            # Démarrer le health check
            self._components['health_check'].start()
            
            # Démarrer les notifications
            self._components['notification_manager'].start()
            
            # Lancer les tâches asynchrones
            self._start_async_tasks()
            
            logger.info(f"ArbitrageBot started successfully (instance: {self.instance_id})")
            
            # Notifier le démarrage
            self._components['notification_manager'].send_notification({
                'type': 'SYSTEM',
                'severity': 'info',
                'title': 'Bot Started',
                'message': f'ArbitrageBot v{VERSION} started (instance: {self.instance_id})',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            self._running = False
            logger.error(f"Failed to start ArbitrageBot: {e}")
            raise
    
    def _start_async_tasks(self):
        """Démarre les tâches asynchrones"""
        loop = self._components['event_loop_manager'].loop
        
        # Tâche de monitoring
        self._tasks.append(
            loop.create_task(self._monitoring_task())
        )
        
        # Tâche de reporting
        self._tasks.append(
            loop.create_task(self._reporting_task())
        )
        
        # Tâche de nettoyage
        self._tasks.append(
            loop.create_task(self._cleanup_task())
        )
        
        # Tâche de health check
        self._tasks.append(
            loop.create_task(self._health_check_task())
        )
    
    def stop(self):
        """Arrête le bot"""
        if not self._running:
            logger.warning("Bot is not running")
            return
        
        logger.info("Stopping ArbitrageBot...")
        self._running = False
        
        try:
            # Arrêter les tâches asynchrones
            for task in self._tasks:
                task.cancel()
            
            # Arrêter les composants
            self._components['arbitrage_engine'].stop()
            self._components['strategy_manager'].stop_all()
            self._components['exchange_manager'].disconnect_all()
            self._components['market_data'].stop()
            self._components['metrics_collector'].stop()
            self._components['health_check'].stop()
            self._components['scheduler'].stop()
            self._components['notification_manager'].stop()
            
            # Notifier l'arrêt
            self._components['notification_manager'].send_notification({
                'type': 'SYSTEM',
                'severity': 'info',
                'title': 'Bot Stopped',
                'message': f'ArbitrageBot stopped (instance: {self.instance_id})',
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"ArbitrageBot stopped successfully (instance: {self.instance_id})")
            
        except Exception as e:
            logger.error(f"Error stopping ArbitrageBot: {e}")
    
    def restart(self):
        """Redémarre le bot"""
        logger.info("Restarting ArbitrageBot...")
        self.stop()
        time.sleep(2)
        self.start()
    
    # ============================================================
    # ASYNC TASKS
    # ============================================================
    
    async def _monitoring_task(self):
        """Tâche de monitoring"""
        while self._running:
            try:
                # Collecter les métriques
                metrics = self._components['metrics_collector'].collect_all()
                
                # Vérifier les alertes
                alerts = self._components['health_check'].check_alerts(metrics)
                for alert in alerts:
                    self._components['notification_manager'].send_alert(alert)
                
                # Mettre à jour les statistiques
                self._update_stats()
                
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring task error: {e}")
                await asyncio.sleep(5)
    
    async def _reporting_task(self):
        """Tâche de reporting"""
        while self._running:
            try:
                # Générer les rapports
                if datetime.now().minute == 0:
                    # Rapport horaire
                    self._generate_hourly_report()
                
                if datetime.now().hour == 0 and datetime.now().minute == 0:
                    # Rapport quotidien
                    self._generate_daily_report()
                
                if datetime.now().weekday() == 0 and datetime.now().hour == 0:
                    # Rapport hebdomadaire
                    self._generate_weekly_report()
                
                if datetime.now().day == 1 and datetime.now().hour == 0:
                    # Rapport mensuel
                    self._generate_monthly_report()
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reporting task error: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_task(self):
        """Tâche de nettoyage"""
        while self._running:
            try:
                # Nettoyer les données anciennes
                self._components['data_manager'].cleanup_old_data()
                
                # Nettoyer le cache
                self._components['cache_manager'].cleanup()
                
                # Nettoyer les queues
                self._components['queue_manager'].cleanup()
                
                await asyncio.sleep(3600)  # 1 heure
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
                await asyncio.sleep(300)
    
    async def _health_check_task(self):
        """Tâche de health check"""
        while self._running:
            try:
                # Exécuter le health check
                health = self._components['health_check'].run_all_checks()
                
                if health['status'] != 'healthy':
                    # Envoyer une alerte
                    self._components['notification_manager'].send_alert({
                        'type': 'HEALTH',
                        'severity': 'warning',
                        'title': 'Health Check Failed',
                        'message': f"Health check failed: {health['status']}",
                        'details': health,
                        'timestamp': datetime.now().isoformat()
                    })
                
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check task error: {e}")
                await asyncio.sleep(30)
    
    # ============================================================
    # REPORTING METHODS
    # ============================================================
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        # Récupérer les stats des composants
        stats = {
            'instance': self.instance_id,
            'uptime': (datetime.now() - self.start_time).total_seconds(),
            'components': {},
            'trades': self._components['execution_engine'].get_stats(),
            'opportunities': self._components['arbitrage_engine'].get_stats(),
            'exchanges': self._components['exchange_manager'].get_stats(),
            'strategies': self._components['strategy_manager'].get_stats(),
            'risk': self._components['risk_manager'].get_stats(),
            'cache': self._components['cache_manager'].get_stats(),
            'queues': self._components['queue_manager'].get_stats(),
            'pools': self._components['pool_manager'].get_stats(),
            'threads': self._components['thread_manager'].get_stats(),
        }
        
        # Stocker les stats
        self._components['data_manager'].set('stats', stats)
    
    def _generate_hourly_report(self):
        """Génère un rapport horaire"""
        stats = self._components['data_manager'].get('stats')
        report = {
            'type': 'HOURLY',
            'timestamp': datetime.now().isoformat(),
            'stats': stats,
            'summary': {
                'total_trades': stats.get('trades', {}).get('total', 0),
                'total_pnl': stats.get('trades', {}).get('pnl', 0),
                'win_rate': stats.get('trades', {}).get('win_rate', 0),
                'opportunities': stats.get('opportunities', {}).get('total', 0),
            }
        }
        
        # Envoyer le rapport
        self._components['notification_manager'].send_report(report)
    
    def _generate_daily_report(self):
        """Génère un rapport quotidien"""
        stats = self._components['data_manager'].get('stats')
        report = {
            'type': 'DAILY',
            'date': datetime.now().date().isoformat(),
            'stats': stats,
            'summary': {
                'total_trades': stats.get('trades', {}).get('total', 0),
                'total_pnl': stats.get('trades', {}).get('pnl', 0),
                'win_rate': stats.get('trades', {}).get('win_rate', 0),
                'opportunities': stats.get('opportunities', {}).get('total', 0),
                'sharpe_ratio': stats.get('trades', {}).get('sharpe_ratio', 0),
                'max_drawdown': stats.get('risk', {}).get('max_drawdown', 0),
            }
        }
        
        # Envoyer le rapport
        self._components['notification_manager'].send_report(report)
    
    def _generate_weekly_report(self):
        """Génère un rapport hebdomadaire"""
        stats = self._components['data_manager'].get('stats')
        report = {
            'type': 'WEEKLY',
            'week': datetime.now().isocalendar()[1],
            'stats': stats,
            'summary': {
                'total_trades': stats.get('trades', {}).get('total', 0),
                'total_pnl': stats.get('trades', {}).get('pnl', 0),
                'win_rate': stats.get('trades', {}).get('win_rate', 0),
                'opportunities': stats.get('opportunities', {}).get('total', 0),
                'sharpe_ratio': stats.get('trades', {}).get('sharpe_ratio', 0),
                'max_drawdown': stats.get('risk', {}).get('max_drawdown', 0),
                'best_day': stats.get('trades', {}).get('best_day', 0),
                'worst_day': stats.get('trades', {}).get('worst_day', 0),
            }
        }
        
        # Envoyer le rapport
        self._components['notification_manager'].send_report(report)
    
    def _generate_monthly_report(self):
        """Génère un rapport mensuel"""
        stats = self._components['data_manager'].get('stats')
        report = {
            'type': 'MONTHLY',
            'month': datetime.now().month,
            'year': datetime.now().year,
            'stats': stats,
            'summary': {
                'total_trades': stats.get('trades', {}).get('total', 0),
                'total_pnl': stats.get('trades', {}).get('pnl', 0),
                'win_rate': stats.get('trades', {}).get('win_rate', 0),
                'opportunities': stats.get('opportunities', {}).get('total', 0),
                'sharpe_ratio': stats.get('trades', {}).get('sharpe_ratio', 0),
                'max_drawdown': stats.get('risk', {}).get('max_drawdown', 0),
                'best_week': stats.get('trades', {}).get('best_week', 0),
                'worst_week': stats.get('trades', {}).get('worst_week', 0),
            }
        }
        
        # Envoyer le rapport
        self._components['notification_manager'].send_report(report)
    
    # ============================================================
    # COMPONENT ACCESS METHODS
    # ============================================================
    
    def get_component(self, name: str) -> Any:
        """
        Récupère un composant
        
        Args:
            name: Nom du composant
            
        Returns:
            Any: Composant
        """
        return self._components.get(name)
    
    def get_all_components(self) -> Dict[str, Any]:
        """
        Récupère tous les composants
        
        Returns:
            Dict[str, Any]: Composants
        """
        return self._components.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du bot
        
        Returns:
            Dict[str, Any]: Statut
        """
        return {
            'instance': self.instance_id,
            'running': self._running,
            'initialized': self._initialized,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'uptime': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            'env': self.env,
            'version': VERSION,
            'debug': self.debug,
            'components': {
                name: {
                    'status': 'active' if hasattr(comp, 'is_active') and comp.is_active() else 'unknown'
                }
                for name, comp in self._components.items()
            },
            'stats': self._components['data_manager'].get('stats', {}),
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Récupère les métriques
        
        Returns:
            Dict[str, Any]: Métriques
        """
        return self._components['metrics_collector'].get_all_metrics()
    
    def get_health(self) -> Dict[str, Any]:
        """
        Récupère le health check
        
        Returns:
            Dict[str, Any]: Health check
        """
        return self._components['health_check'].get_health_report()
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def is_running(self) -> bool:
        """Vérifie si le bot est en cours d'exécution"""
        return self._running
    
    def is_initialized(self) -> bool:
        """Vérifie si le bot est initialisé"""
        return self._initialized
    
    def get_config(self) -> FullConfig:
        """
        Récupère la configuration
        
        Returns:
            FullConfig: Configuration
        """
        return self.config
    
    def get_instance_id(self) -> str:
        """
        Récupère l'ID de l'instance
        
        Returns:
            str: ID de l'instance
        """
        return self.instance_id
    
    def get_version(self) -> str:
        """
        Récupère la version
        
        Returns:
            str: Version
        """
        return VERSION
    
    # ============================================================
    # CONTEXT MANAGER
    # ============================================================
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        self.stop()

# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default=os.environ.get("NEXUS_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    )
    parser.add_argument(
        "-e", "--env",
        help="Environment (development, staging, production)",
        default=os.environ.get("NEXUS_ENV", DEFAULT_ENV)
    )
    parser.add_argument(
        "-d", "--debug",
        help="Enable debug mode",
        action="store_true",
        default=os.environ.get("NEXUS_DEBUG", "false").lower() == "true"
    )
    parser.add_argument(
        "-v", "--version",
        help="Show version",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    if args.version:
        print(f"NEXUS Arbitrage Bot v{VERSION}")
        return
    
    # Configurer le logging
    setup_logging(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Créer et démarrer le bot
    try:
        bot = ArbitrageBot(
            config_path=args.config,
            env=args.env,
            debug=args.debug
        )
        
        bot.start()
        
        # Garder le bot en vie
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
        bot.stop()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ArbitrageBot',
    'VERSION',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()

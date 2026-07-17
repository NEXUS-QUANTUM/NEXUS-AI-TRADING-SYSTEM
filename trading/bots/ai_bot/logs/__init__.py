"""
NEXUS AI TRADING SYSTEM - Logs Module for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/logs/__init__.py
Description: Module de gestion des logs pour le bot AI.
             Intègre l'ensemble des fonctionnalités de logging,
             rotation des logs, analyse des logs, export et reporting.
             Supporte les logs en temps réel et les archives historiques.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta

# ============================================================
# EXPORTATION DES CLASSES PRINCIPALES
# ============================================================

# Gestionnaire de logs
from trading.bots.ai_bot.logs.log_manager import (
    LogManager,
    LogManagerConfig,
    LogLevel,
    LogCategory,
    LogEntry,
    LogStats,
    create_log_manager
)

# Rotation des logs
from trading.bots.ai_bot.logs.log_rotator import (
    LogRotator,
    LogRotatorConfig,
    RotationStrategy,
    RotationResult,
    create_log_rotator
)

# Analyseur de logs
from trading.bots.ai_bot.logs.log_analyzer import (
    LogAnalyzer,
    LogAnalyzerConfig,
    LogPattern,
    LogInsight,
    LogReport,
    create_log_analyzer
)

# Exportateur de logs
from trading.bots.ai_bot.logs.log_exporter import (
    LogExporter,
    LogExporterConfig,
    ExportFormat,
    ExportResult,
    create_log_exporter
)

# ============================================================
# VERSION ET MÉTADONNÉES
# ============================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__license__ = "Proprietary"

# ============================================================
# CONFIGURATION DU LOGGING
# ============================================================

logger = logging.getLogger(__name__)

def setup_logging(level: str = "INFO") -> None:
    """
    Configure le logging pour le module logs.
    
    Args:
        level: Niveau de logging ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Logs module logging configured at {level} level")

# ============================================================
# FONCTIONS RAPIDES
# ============================================================

def quick_log(
    message: str,
    level: str = "INFO",
    category: str = "GENERAL",
    data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log rapide d'un message.
    
    Args:
        message: Message à logger.
        level: Niveau de log.
        category: Catégorie de log.
        data: Données supplémentaires.
    """
    log_manager = create_log_manager()
    log_manager.log(level, category, message, data)


def quick_read_logs(
    log_file: str = "trading/bots/ai_bot/logs/ai_bot.log",
    level: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Lecture rapide des logs.
    
    Args:
        log_file: Chemin du fichier de logs.
        level: Niveau de log.
        category: Catégorie de log.
        limit: Nombre maximum de logs.
        
    Returns:
        Liste des logs.
    """
    log_manager = create_log_manager()
    return log_manager.read_logs(log_file, level, category, limit)


def quick_analyze_logs(
    log_file: str = "trading/bots/ai_bot/logs/ai_bot.log",
    days: int = 7
) -> Dict[str, Any]:
    """
    Analyse rapide des logs.
    
    Args:
        log_file: Chemin du fichier de logs.
        days: Nombre de jours à analyser.
        
    Returns:
        Résultats de l'analyse.
    """
    analyzer = create_log_analyzer()
    return analyzer.analyze_file(log_file, days)


def quick_export_logs(
    log_file: str = "trading/bots/ai_bot/logs/ai_bot.log",
    output_format: str = "json",
    output_file: Optional[str] = None
) -> str:
    """
    Export rapide des logs.
    
    Args:
        log_file: Chemin du fichier de logs.
        output_format: Format de sortie.
        output_file: Fichier de sortie.
        
    Returns:
        Chemin du fichier exporté.
    """
    exporter = create_log_exporter()
    return exporter.export(log_file, output_format, output_file)


# ============================================================
# CONSTANTES ET CONFIGURATIONS
# ============================================================

# Niveaux de log
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

# Catégories de log
LOG_CATEGORIES = [
    'SYSTEM',      # Logs système
    'TRADING',     # Logs de trading
    'STRATEGY',    # Logs de stratégie
    'MODEL',       # Logs de modèle
    'DATA',        # Logs de données
    'SECURITY',    # Logs de sécurité
    'PERFORMANCE', # Logs de performance
    'GENERAL'      # Logs généraux
]

# Stratégies de rotation
ROTATION_STRATEGIES = ['SIZE', 'TIME', 'HYBRID']

# Formats d'export
EXPORT_FORMATS = ['json', 'csv', 'html', 'pdf', 'excel']

# Fichiers de logs par défaut
DEFAULT_LOG_FILES = {
    'main': 'trading/bots/ai_bot/logs/ai_bot.log',
    'rotated': 'trading/bots/ai_bot/logs/ai_bot.log.1',
    'errors': 'trading/bots/ai_bot/logs/errors.log',
    'performance': 'trading/bots/ai_bot/logs/performance.log',
    'trades': 'trading/bots/ai_bot/logs/trades.log'
}

# Configuration par défaut
DEFAULT_CONFIG = {
    'log_dir': 'trading/bots/ai_bot/logs/',
    'archive_dir': 'trading/bots/ai_bot/logs/archive/',
    'max_file_size_mb': 10,
    'max_files': 10,
    'rotation_interval_days': 1,
    'compression': True,
    'keep_days': 30
}

# ============================================================
# CLASSES DE GESTION
# ============================================================

class LogManager:
    """
    Gestionnaire unifié des logs.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise le gestionnaire de logs.
        
        Args:
            config: Configuration du gestionnaire.
        """
        self.config = config or DEFAULT_CONFIG
        self._loggers: Dict[str, logging.Logger] = {}
        
        # Initialisation du logging
        self._setup_loggers()
        
        logger.info("LogManager initialisé")
    
    def _setup_loggers(self) -> None:
        """Configure les loggers."""
        # Logger principal
        self._loggers['main'] = self._create_logger('ai_bot')
        self._loggers['errors'] = self._create_logger('errors')
        self._loggers['performance'] = self._create_logger('performance')
        self._loggers['trades'] = self._create_logger('trades')
    
    def _create_logger(self, name: str) -> logging.Logger:
        """
        Crée un logger.
        
        Args:
            name: Nom du logger.
            
        Returns:
            Instance du logger.
        """
        logger_obj = logging.getLogger(f"nexus.ai_bot.{name}")
        
        # Handler pour fichier
        file_handler = logging.FileHandler(
            f"{self.config['log_dir']}{name}.log"
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger_obj.addHandler(file_handler)
        
        # Handler pour console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger_obj.addHandler(console_handler)
        
        logger_obj.setLevel(logging.INFO)
        
        return logger_obj
    
    def log(
        self,
        level: str,
        category: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Enregistre un log.
        
        Args:
            level: Niveau de log.
            category: Catégorie de log.
            message: Message.
            data: Données supplémentaires.
        """
        logger_obj = self._loggers.get('main')
        if not logger_obj:
            return
        
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'category': category,
            'message': message,
            'data': data or {}
        }
        
        logger_obj.log(log_level, json.dumps(log_entry))
    
    def read_logs(
        self,
        log_file: str,
        level: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Lit les logs depuis un fichier.
        
        Args:
            log_file: Chemin du fichier.
            level: Niveau de log.
            category: Catégorie.
            limit: Nombre maximum.
            
        Returns:
            Liste des logs.
        """
        logs = []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        log = json.loads(line.strip())
                        logs.append(log)
                    except:
                        continue
            
            # Filtrage
            if level:
                logs = [l for l in logs if l.get('level') == level]
            if category:
                logs = [l for l in logs if l.get('category') == category]
            
            # Tri par timestamp (plus récent en premier)
            logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return logs[:limit]
            
        except FileNotFoundError:
            logger.warning(f"Fichier de logs non trouvé: {log_file}")
            return []
        except Exception as e:
            logger.error(f"Erreur de lecture des logs: {e}")
            return []
    
    def get_stats(self, log_file: str) -> LogStats:
        """
        Retourne les statistiques d'un fichier de logs.
        
        Args:
            log_file: Chemin du fichier.
            
        Returns:
            Statistiques des logs.
        """
        logs = self.read_logs(log_file, limit=10000)
        
        stats = LogStats()
        
        if not logs:
            return stats
        
        stats.total = len(logs)
        
        for log in logs:
            level = log.get('level', 'UNKNOWN')
            category = log.get('category', 'UNKNOWN')
            stats.by_level[level] = stats.by_level.get(level, 0) + 1
            stats.by_category[category] = stats.by_category.get(category, 0) + 1
        
        return stats


class LogStats:
    """Statistiques des logs."""
    
    def __init__(self):
        self.total = 0
        self.by_level: Dict[str, int] = {}
        self.by_category: Dict[str, int] = {}
        self.first_log: Optional[str] = None
        self.last_log: Optional[str] = None


# ============================================================
# INITIALISATION DU MODULE
# ============================================================

logger.info("=" * 60)
logger.info("NEXUS AI TRADING SYSTEM - Logs Module")
logger.info(f"Version: {__version__}")
logger.info(f"Copyright: {__copyright__}")
logger.info("=" * 60)
logger.info(f"Log levels: {len(LOG_LEVELS)}")
logger.info(f"Log categories: {len(LOG_CATEGORIES)}")
logger.info(f"Rotation strategies: {len(ROTATION_STRATEGIES)}")
logger.info(f"Export formats: {len(EXPORT_FORMATS)}")
logger.info("=" * 60)

# ============================================================
# EXPORTATION COMPLÈTE
# ============================================================

__all__ = [
    # Classes principales
    'LogManager',
    'LogManagerConfig',
    'LogLevel',
    'LogCategory',
    'LogEntry',
    'LogStats',
    'LogRotator',
    'LogRotatorConfig',
    'RotationStrategy',
    'RotationResult',
    'LogAnalyzer',
    'LogAnalyzerConfig',
    'LogPattern',
    'LogInsight',
    'LogReport',
    'LogExporter',
    'LogExporterConfig',
    'ExportFormat',
    'ExportResult',
    
    # Fonctions rapides
    'create_log_manager',
    'create_log_rotator',
    'create_log_analyzer',
    'create_log_exporter',
    'quick_log',
    'quick_read_logs',
    'quick_analyze_logs',
    'quick_export_logs',
    'setup_logging',
    
    # Constantes
    'LOG_LEVELS',
    'LOG_CATEGORIES',
    'ROTATION_STRATEGIES',
    'EXPORT_FORMATS',
    'DEFAULT_LOG_FILES',
    'DEFAULT_CONFIG',
    
    # Métadonnées
    '__version__',
    '__author__',
    '__copyright__',
    '__license__'
]

# ============================================================
# FIN DU MODULE
# ============================================================

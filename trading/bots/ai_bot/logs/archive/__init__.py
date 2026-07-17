"""
NEXUS AI TRADING SYSTEM - Archive Logs Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/logs/archive/__init__.py
Description: Module de gestion des logs archivés pour le bot AI.
             Supporte la lecture, l'écriture, la compression,
             la rotation et l'analyse des fichiers de logs historiques.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta

# ============================================================
# EXPORTATION DES CLASSES PRINCIPALES
# ============================================================

from trading.bots.ai_bot.logs.archive.archive_reader import (
    ArchiveReader,
    ArchiveReaderConfig,
    ArchiveStats,
    ArchiveEntry,
    read_archive
)

from trading.bots.ai_bot.logs.archive.archive_writer import (
    ArchiveWriter,
    ArchiveWriterConfig,
    ArchiveRotation,
    ArchiveCompression,
    write_archive
)

from trading.bots.ai_bot.logs.archive.archive_analyzer import (
    ArchiveAnalyzer,
    AnalysisResult,
    LogPattern,
    LogTrend,
    ErrorSummary,
    analyze_archive
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
    Configure le logging pour le module archive.
    
    Args:
        level: Niveau de logging ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Archive module logging configured at {level} level")

# ============================================================
# FONCTIONS RAPIDES
# ============================================================

def quick_read_archive(
    filepath: str,
    level: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 100
) -> List[ArchiveEntry]:
    """
    Lecture rapide d'une archive.
    
    Args:
        filepath: Chemin du fichier d'archive.
        level: Niveau de log.
        module: Module.
        limit: Nombre maximum d'entrées.
        
    Returns:
        Liste des entrées.
    """
    return read_archive(filepath, level=level, module=module, limit=limit)


def quick_analyze_archive(
    filepath: str,
    date: Optional[datetime] = None
) -> AnalysisResult:
    """
    Analyse rapide d'une archive.
    
    Args:
        filepath: Chemin du fichier d'archive.
        date: Date de référence.
        
    Returns:
        Résultats de l'analyse.
    """
    return analyze_archive(filepath, date=date)


def quick_archive_stats(filepath: str) -> ArchiveStats:
    """
    Statistiques rapides d'une archive.
    
    Args:
        filepath: Chemin du fichier d'archive.
        
    Returns:
        Statistiques de l'archive.
    """
    reader = ArchiveReader(filepath)
    return reader.get_stats()


# ============================================================
# CONSTANTES ET CONFIGURATIONS
# ============================================================

# Formats de compression supportés
COMPRESSION_FORMATS = ['gz', 'bz2', 'xz', 'zip', 'none']

# Formats de date pour les archives
DATE_FORMATS = [
    '%Y-%m-%d',
    '%Y%m%d',
    '%d-%m-%Y',
    '%d%m%Y',
    '%Y-%m-%d_%H-%M-%S',
    '%Y%m%d_%H%M%S'
]

# Niveaux de log
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

# Modules par défaut
DEFAULT_MODULES = [
    'ai_bot',
    'data_feeder',
    'model_manager',
    'signal_processor',
    'order_executor',
    'position_manager',
    'risk_manager',
    'performance_tracker',
    'indicator_calculator',
    'market_analysis',
    'strategy_selector',
    'feature_engine',
    'model_predictor',
    'data_validator',
    'execution_monitor'
]

# Configuration par défaut
DEFAULT_CONFIG = {
    'archive_path': 'trading/bots/ai_bot/logs/archive/',
    'compression': 'gz',
    'rotation_days': 30,
    'max_size_mb': 100,
    'keep_days': 90,
    'auto_cleanup': True
}

# ============================================================
# CLASSES DE GESTION
# ============================================================

class ArchiveManager:
    """
    Gestionnaire unifié des logs archivés.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise le gestionnaire d'archives.
        
        Args:
            config: Configuration du gestionnaire.
        """
        self.config = config or DEFAULT_CONFIG
        self._readers: Dict[str, ArchiveReader] = {}
        self._writers: Dict[str, ArchiveWriter] = {}
        
        logger.info("ArchiveManager initialisé")
    
    def get_reader(self, filepath: str) -> ArchiveReader:
        """
        Récupère un lecteur d'archive.
        
        Args:
            filepath: Chemin du fichier.
            
        Returns:
            Lecteur d'archive.
        """
        if filepath not in self._readers:
            self._readers[filepath] = ArchiveReader(filepath)
        return self._readers[filepath]
    
    def get_writer(
        self,
        filepath: str,
        compression: str = "gz"
    ) -> ArchiveWriter:
        """
        Récupère un écrivain d'archive.
        
        Args:
            filepath: Chemin du fichier.
            compression: Type de compression.
            
        Returns:
            Écrivain d'archive.
        """
        key = f"{filepath}_{compression}"
        if key not in self._writers:
            self._writers[key] = ArchiveWriter(
                ArchiveWriterConfig(
                    filepath=filepath,
                    compression=compression
                )
            )
        return self._writers[key]
    
    def list_archives(
        self,
        pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Liste les archives disponibles.
        
        Args:
            pattern: Filtre de nom.
            
        Returns:
            Liste des archives.
        """
        import os
        import glob
        
        archive_path = self.config.get('archive_path', '')
        search_pattern = os.path.join(archive_path, f"*{pattern or ''}*")
        
        archives = []
        for filepath in glob.glob(search_pattern):
            if os.path.isfile(filepath):
                stats = os.stat(filepath)
                archives.append({
                    'path': filepath,
                    'name': os.path.basename(filepath),
                    'size': stats.st_size,
                    'size_mb': round(stats.st_size / (1024 * 1024), 2),
                    'modified': datetime.fromtimestamp(stats.st_mtime)
                })
        
        return sorted(archives, key=lambda x: x['modified'], reverse=True)
    
    def cleanup_old_archives(self, keep_days: int = 90) -> int:
        """
        Nettoie les archives anciennes.
        
        Args:
            keep_days: Nombre de jours à conserver.
            
        Returns:
            Nombre d'archives supprimées.
        """
        import os
        
        cutoff = datetime.now() - timedelta(days=keep_days)
        deleted = 0
        
        archives = self.list_archives()
        for archive in archives:
            if archive['modified'] < cutoff:
                try:
                    os.remove(archive['path'])
                    deleted += 1
                    logger.info(f"Archive supprimée: {archive['name']}")
                except Exception as e:
                    logger.error(f"Erreur de suppression: {e}")
        
        return deleted
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du gestionnaire.
        
        Returns:
            Statistiques.
        """
        archives = self.list_archives()
        
        total_size = sum(a['size'] for a in archives)
        
        return {
            'total_archives': len(archives),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'readers': len(self._readers),
            'writers': len(self._writers),
            'archives': archives[:10]  # Limiter pour l'affichage
        }


# ============================================================
# INITIALISATION DU MODULE
# ============================================================

logger.info("=" * 60)
logger.info("NEXUS AI TRADING SYSTEM - Archive Logs Module")
logger.info(f"Version: {__version__}")
logger.info(f"Copyright: {__copyright__}")
logger.info("=" * 60)
logger.info(f"Compression formats: {len(COMPRESSION_FORMATS)}")
logger.info(f"Default modules: {len(DEFAULT_MODULES)}")
logger.info("=" * 60)

# ============================================================
# EXPORTATION COMPLÈTE
# ============================================================

__all__ = [
    # Classes principales
    'ArchiveReader',
    'ArchiveReaderConfig',
    'ArchiveStats',
    'ArchiveEntry',
    'ArchiveWriter',
    'ArchiveWriterConfig',
    'ArchiveRotation',
    'ArchiveCompression',
    'ArchiveAnalyzer',
    'AnalysisResult',
    'LogPattern',
    'LogTrend',
    'ErrorSummary',
    'ArchiveManager',
    
    # Fonctions rapides
    'read_archive',
    'write_archive',
    'analyze_archive',
    'quick_read_archive',
    'quick_analyze_archive',
    'quick_archive_stats',
    'setup_logging',
    
    # Constantes
    'COMPRESSION_FORMATS',
    'DATE_FORMATS',
    'LOG_LEVELS',
    'DEFAULT_MODULES',
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

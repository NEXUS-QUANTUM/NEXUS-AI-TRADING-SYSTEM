"""
NEXUS AI TRADING SYSTEM - Data Module for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/data/__init__.py
Description: Module de gestion des données pour le bot AI.
             Intègre l'ensemble des fonctionnalités de traitement,
             validation, normalisation, augmentation, stockage
             et pipeline de données.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

# ============================================================
# EXPORTATION DES CLASSES PRINCIPALES
# ============================================================

# Data Pipeline
from trading.bots.ai_bot.data.data_pipeline import (
    DataPipeline,
    PipelineConfig,
    PipelineMetrics,
    PipelineStage,
    PipelineStatus,
    create_pipeline
)

# Data Feeder
from trading.bots.ai_bot.data.data_feeder import (
    DataFeeder,
    DataFeedConfig,
    DataFeedStats,
    DataBatch,
    FeedStatus,
    DataSourceType,
    create_data_feeder
)

# Data Processor
from trading.bots.ai_bot.data.data_processor import (
    DataProcessor,
    ProcessingConfig,
    ProcessingMode,
    FeatureCategory,
    FeatureSet,
    create_processor
)

# Data Validator
from trading.bots.ai_bot.data.data_validator import (
    DataValidator,
    ValidationConfig,
    ValidationReport,
    ValidationRule,
    ValidationRuleType,
    ValidationSeverity,
    create_validator,
    validate_data
)

# Data Normalizer
from trading.bots.ai_bot.data.data_normalizer import (
    DataNormalizer,
    NormalizationConfig,
    NormalizationStats,
    NormalizationMethod,
    create_normalizer,
    normalize_data
)

# Data Augmentation
from trading.bots.ai_bot.data.data_augmentation import (
    DataAugmentor,
    AugmentationConfig,
    AugmentationResult,
    AugmentationMethod,
    augment_time_series,
    create_augmented_dataset
)

# Data Storage
from trading.bots.ai_bot.data.data_storage import (
    DataStorage,
    StorageConfig,
    StorageMetadata,
    StorageType,
    CompressionType,
    create_storage
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
    Configure le logging pour le module data.
    
    Args:
        level: Niveau de logging ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Data module logging configured at {level} level")

# ============================================================
# FONCTIONS RAPIDES
# ============================================================

def quick_validate(
    data: Union[pd.DataFrame, np.ndarray, Dict, List],
    strict: bool = True,
    auto_fix: bool = False
) -> Tuple[pd.DataFrame, ValidationReport]:
    """
    Validation rapide des données.
    
    Args:
        data: Données à valider.
        strict: Mode strict.
        auto_fix: Correction automatique.
        
    Returns:
        Tuple (données traitées, rapport).
    """
    return validate_data(data, strict_mode=strict, auto_fix=auto_fix)


def quick_normalize(
    data: Union[pd.DataFrame, np.ndarray, List],
    method: str = "standard"
) -> np.ndarray:
    """
    Normalisation rapide des données.
    
    Args:
        data: Données à normaliser.
        method: Méthode de normalisation.
        
    Returns:
        Données normalisées.
    """
    return normalize_data(data, method=method)


def quick_augment(
    data: np.ndarray,
    labels: Optional[np.ndarray] = None,
    method: str = "jitter",
    n_augmented: Optional[int] = None
) -> AugmentationResult:
    """
    Augmentation rapide des données.
    
    Args:
        data: Données à augmenter.
        labels: Labels associés.
        method: Méthode d'augmentation.
        n_augmented: Nombre d'échantillons augmentés.
        
    Returns:
        Résultats de l'augmentation.
    """
    return augment_time_series(data, labels, method=method, n_augmented=n_augmented)


def quick_pipeline(
    symbol: str,
    name: str = "quick_pipeline",
    batch_size: int = 100
) -> DataPipeline:
    """
    Création rapide d'un pipeline.
    
    Args:
        symbol: Symbole à trader.
        name: Nom du pipeline.
        batch_size: Taille des batches.
        
    Returns:
        Instance du pipeline.
    """
    return create_pipeline(symbol, name, batch_size)


# ============================================================
# CONSTANTES ET CONFIGURATIONS
# ============================================================

# Méthodes de normalisation disponibles
NORMALIZATION_METHODS = [m.value for m in NormalizationMethod]

# Méthodes d'augmentation disponibles
AUGMENTATION_METHODS = [m.value for m in AugmentationMethod]

# Types de stockage disponibles
STORAGE_TYPES = [s.value for s in StorageType]

# Types de compression disponibles
COMPRESSION_TYPES = [c.value for c in CompressionType]

# Types de sources de données
DATA_SOURCE_TYPES = [s.value for s in DataSourceType]

# Types de règles de validation
VALIDATION_RULE_TYPES = [r.value for r in ValidationRuleType]

# Niveaux de sévérité
VALIDATION_SEVERITIES = [s.value for s in ValidationSeverity]

# Configuration par défaut
DEFAULT_CONFIG = {
    'batch_size': 100,
    'max_queue_size': 1000,
    'cache_size': 10000,
    'cache_ttl': 3600,
    'parallel': True,
    'n_workers': 4,
    'strict_mode': True,
    'auto_fix': False,
    'max_null_ratio': 0.1,
    'max_duplicate_ratio': 0.05,
    'max_outlier_ratio': 0.01,
    'min_completeness': 0.9
}

# Colonnes OHLCV standard
OHLCV_COLUMNS = ['open', 'high', 'low', 'close', 'volume']

# Timeframes supportés
SUPPORTED_TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '6h', '12h', '1d', '1w', '1M']

# ============================================================
# VALIDATION ET UTILITAIRES
# ============================================================

def validate_ohlcv(data: pd.DataFrame) -> ValidationReport:
    """
    Valide un DataFrame OHLCV.
    
    Args:
        data: DataFrame OHLCV.
        
    Returns:
        Rapport de validation.
    """
    validator = DataValidator()
    return validator.validate(data)[1]


def ensure_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    """
    S'assure que les colonnes OHLCV sont présentes.
    
    Args:
        data: DataFrame à vérifier.
        
    Returns:
        DataFrame avec OHLCV.
    """
    df = data.copy()
    
    # Vérification des colonnes
    for col in OHLCV_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    
    # Remplissage des valeurs manquantes
    df = df.fillna(method='ffill').fillna(method='bfill')
    
    return df


def get_data_stats(data: pd.DataFrame) -> Dict[str, Any]:
    """
    Retourne les statistiques descriptives des données.
    
    Args:
        data: DataFrame.
        
    Returns:
        Statistiques descriptives.
    """
    stats = {
        'shape': data.shape,
        'columns': list(data.columns),
        'dtypes': data.dtypes.to_dict(),
        'null_count': data.isna().sum().to_dict(),
        'null_ratio': (data.isna().sum() / len(data)).to_dict(),
        'memory_usage': data.memory_usage(deep=True).to_dict(),
        'total_memory': data.memory_usage(deep=True).sum()
    }
    
    # Statistiques numériques
    numeric_cols = data.select_dtypes(include=[np.number]).columns
    if not numeric_cols.empty:
        stats['numeric_stats'] = data[numeric_cols].describe().to_dict()
    
    return stats


# ============================================================
# CLASSES DE GESTION
# ============================================================

class DataManager:
    """
    Gestionnaire unifié des opérations de données.
    Intègre validation, normalisation, augmentation et stockage.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise le gestionnaire de données.
        
        Args:
            config: Configuration du gestionnaire.
        """
        self.config = config or DEFAULT_CONFIG
        
        # Initialisation des composants
        self.validator = DataValidator(ValidationConfig(
            strict_mode=self.config.get('strict_mode', True),
            auto_fix=self.config.get('auto_fix', False),
            max_null_ratio=self.config.get('max_null_ratio', 0.1),
            max_duplicate_ratio=self.config.get('max_duplicate_ratio', 0.05),
            max_outlier_ratio=self.config.get('max_outlier_ratio', 0.01)
        ))
        
        self.normalizer = DataNormalizer()
        self.augmentor = DataAugmentor()
        self.storage = DataStorage()
        
        # Statistiques
        self._stats = {
            'validated': 0,
            'normalized': 0,
            'augmented': 0,
            'stored': 0,
            'loaded': 0
        }
        
        logger.info("DataManager initialisé")
    
    def process(
        self,
        data: Union[pd.DataFrame, np.ndarray, List],
        validate: bool = True,
        normalize: bool = True,
        augment: bool = False,
        store: bool = False,
        name: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Traite les données à travers le pipeline complet.
        
        Args:
            data: Données à traiter.
            validate: Valider les données.
            normalize: Normaliser les données.
            augment: Augmenter les données.
            store: Stocker les données.
            name: Nom du dataset (pour le stockage).
            
        Returns:
            Tuple (données traitées, métadonnées).
        """
        start_time = datetime.now()
        metadata = {'processed_at': start_time.isoformat()}
        
        df = self._to_dataframe(data)
        
        # Validation
        if validate:
            df, report = self.validator.validate(df)
            metadata['validation'] = report.to_dict()
            self._stats['validated'] += 1
        
        # Normalisation
        if normalize:
            df_normalized = self.normalizer.fit_transform(df)
            metadata['normalization'] = {
                'method': self.normalizer.config.method.value,
                'stats': self.normalizer.stats.to_dict()
            }
            self._stats['normalized'] += 1
            df = df_normalized
        
        # Augmentation
        if augment:
            result = self.augmentor.augment(df)
            metadata['augmentation'] = {
                'methods': result.methods_applied,
                'factor': result.augmentation_factor
            }
            self._stats['augmented'] += 1
            df = pd.DataFrame(result.data)
        
        # Stockage
        if store and name:
            self.storage.store(df, name)
            metadata['storage'] = {
                'name': name,
                'type': self.storage.config.primary_storage.value
            }
            self._stats['stored'] += 1
        
        metadata['shape'] = df.shape
        metadata['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        return df, metadata
    
    def _to_dataframe(self, data: Union[pd.DataFrame, np.ndarray, List]) -> pd.DataFrame:
        """Convertit en DataFrame."""
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, np.ndarray):
            return pd.DataFrame(data)
        elif isinstance(data, list):
            return pd.DataFrame(data)
        else:
            raise ValidationError(f"Type non supporté: {type(data)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du gestionnaire.
        
        Returns:
            Statistiques.
        """
        return {
            **self._stats,
            'validator': self.validator.get_statistics(),
            'normalizer': self.normalizer.get_stats(),
            'storage': self.storage.get_stats()
        }
    
    def reset(self) -> None:
        """
        Réinitialise le gestionnaire.
        """
        self.validator.reset()
        self.normalizer.reset()
        self.augmentor = DataAugmentor()
        self._stats = {
            'validated': 0,
            'normalized': 0,
            'augmented': 0,
            'stored': 0,
            'loaded': 0
        }
        logger.info("DataManager réinitialisé")


# ============================================================
# INITIALISATION DU MODULE
# ============================================================

logger.info("=" * 60)
logger.info("NEXUS AI TRADING SYSTEM - Data Module")
logger.info(f"Version: {__version__}")
logger.info(f"Copyright: {__copyright__}")
logger.info("=" * 60)
logger.info(f"Normalization methods: {len(NORMALIZATION_METHODS)}")
logger.info(f"Augmentation methods: {len(AUGMENTATION_METHODS)}")
logger.info(f"Storage types: {len(STORAGE_TYPES)}")
logger.info(f"Validation rule types: {len(VALIDATION_RULE_TYPES)}")
logger.info("=" * 60)

# ============================================================
# EXPORTATION COMPLÈTE
# ============================================================

__all__ = [
    # Classes principales
    'DataPipeline',
    'PipelineConfig',
    'PipelineMetrics',
    'PipelineStage',
    'PipelineStatus',
    'DataFeeder',
    'DataFeedConfig',
    'DataFeedStats',
    'DataBatch',
    'FeedStatus',
    'DataSourceType',
    'DataProcessor',
    'ProcessingConfig',
    'ProcessingMode',
    'FeatureCategory',
    'FeatureSet',
    'DataValidator',
    'ValidationConfig',
    'ValidationReport',
    'ValidationRule',
    'ValidationRuleType',
    'ValidationSeverity',
    'DataNormalizer',
    'NormalizationConfig',
    'NormalizationStats',
    'NormalizationMethod',
    'DataAugmentor',
    'AugmentationConfig',
    'AugmentationResult',
    'AugmentationMethod',
    'DataStorage',
    'StorageConfig',
    'StorageMetadata',
    'StorageType',
    'CompressionType',
    'DataManager',
    
    # Fonctions rapides
    'create_pipeline',
    'create_data_feeder',
    'create_processor',
    'create_validator',
    'validate_data',
    'create_normalizer',
    'normalize_data',
    'augment_time_series',
    'create_augmented_dataset',
    'create_storage',
    'quick_validate',
    'quick_normalize',
    'quick_augment',
    'quick_pipeline',
    
    # Utilitaires
    'validate_ohlcv',
    'ensure_ohlcv',
    'get_data_stats',
    'setup_logging',
    
    # Constantes
    'NORMALIZATION_METHODS',
    'AUGMENTATION_METHODS',
    'STORAGE_TYPES',
    'COMPRESSION_TYPES',
    'DATA_SOURCE_TYPES',
    'VALIDATION_RULE_TYPES',
    'VALIDATION_SEVERITIES',
    'OHLCV_COLUMNS',
    'SUPPORTED_TIMEFRAMES',
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

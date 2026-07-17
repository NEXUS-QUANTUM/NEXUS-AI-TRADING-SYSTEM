"""
NEXUS AI TRADING SYSTEM - Indicators Module for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/indicators/__init__.py
Description: Module d'indicateurs techniques pour le bot AI.
             Intègre l'ensemble des indicateurs standards et personnalisés,
             avec gestion du cache, de la factory, et du calculateur
             unifié pour l'analyse technique avancée.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

# ============================================================
# EXPORTATION DES CLASSES PRINCIPALES
# ============================================================

# Base Indicator
from trading.bots.ai_bot.indicators.base_indicator import (
    BaseIndicator,
    IndicatorConfig,
    IndicatorResult,
    IndicatorState,
    IndicatorCategory,
    IndicatorType,
    validate_indicator_result,
    compare_indicators
)

# Custom Indicators
from trading.bots.ai_bot.indicators.custom_indicators import (
    MarketSentimentIndicator,
    OrderFlowIndicator,
    MarketRegimeIndicator,
    CrossCorrelationIndicator,
    AdaptiveVolatilityIndicator,
    MarketCycleIndicator,
    AdvancedRSIIndicator,
    CustomIndicatorFactory
)

# Indicator Factory
from trading.bots.ai_bot.indicators.indicator_factory import (
    IndicatorFactory,
    IndicatorFactorySingleton,
    IndicatorRegistry,
    IndicatorInfo,
    get_indicator_factory,
    create_indicator
)

# Indicator Cache
from trading.bots.ai_bot.indicators.indicator_cache import (
    IndicatorCache,
    CacheConfig,
    CacheEntry,
    CacheBackend,
    create_indicator_cache
)

# Indicator Calculator
from trading.bots.ai_bot.indicators.indicator_calculator import (
    IndicatorCalculator,
    CalculatorConfig,
    CalculationResult,
    CalculationMode,
    IndicatorPriority,
    IndicatorDependency,
    create_indicator_calculator
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
    Configure le logging pour le module indicators.
    
    Args:
        level: Niveau de logging ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Indicators module logging configured at {level} level")

# ============================================================
# FONCTIONS RAPIDES
# ============================================================

def quick_calculate_indicator(
    name: str,
    data: pd.DataFrame,
    symbol: str = "",
    timeframe: str = "1h",
    **kwargs
) -> IndicatorResult:
    """
    Calcule rapidement un indicateur.
    
    Args:
        name: Nom de l'indicateur.
        data: Données OHLCV.
        symbol: Symbole.
        timeframe: Timeframe.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultat de l'indicateur.
    """
    indicator = create_indicator(name, symbol, timeframe, **kwargs)
    return indicator.calculate(data, kwargs)


def quick_calculate_multi(
    data: pd.DataFrame,
    indicator_names: List[str],
    symbol: str = "",
    timeframe: str = "1h",
    parallel: bool = True,
    **kwargs
) -> Dict[str, IndicatorResult]:
    """
    Calcule rapidement plusieurs indicateurs.
    
    Args:
        data: Données OHLCV.
        indicator_names: Liste des indicateurs.
        symbol: Symbole.
        timeframe: Timeframe.
        parallel: Paralléliser.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Dictionnaire des résultats.
    """
    calculator = create_indicator_calculator(
        symbol=symbol,
        timeframe=timeframe,
        parallel=parallel,
        **kwargs
    )
    result = calculator.calculate(data, indicator_names)
    return result.results


def quick_list_indicators() -> Dict[str, IndicatorInfo]:
    """
    Liste tous les indicateurs disponibles.
    
    Returns:
        Dictionnaire des informations des indicateurs.
    """
    factory = get_indicator_factory()
    return factory.get_all_info()


def quick_get_indicator_info(name: str) -> Optional[IndicatorInfo]:
    """
    Récupère les informations d'un indicateur.
    
    Args:
        name: Nom de l'indicateur.
        
    Returns:
        Informations de l'indicateur.
    """
    factory = get_indicator_factory()
    return factory.get_info(name)


# ============================================================
# CONSTANTES ET CONFIGURATIONS
# ============================================================

# Catégories d'indicateurs
INDICATOR_CATEGORIES = [c.value for c in IndicatorCategory]

# Types d'indicateurs
INDICATOR_TYPES = [t.value for t in IndicatorType]

# Backends de cache
CACHE_BACKENDS = [b.value for b in CacheBackend]

# Modes de calcul
CALCULATION_MODES = [m.value for m in CalculationMode]

# Priorités des indicateurs
INDICATOR_PRIORITIES = [p.value for p in IndicatorPriority]

# Indicateurs disponibles par défaut
DEFAULT_INDICATORS = [
    'market_sentiment',
    'order_flow',
    'market_regime',
    'cross_correlation',
    'adaptive_volatility',
    'market_cycle',
    'advanced_rsi'
]

# Configuration par défaut
DEFAULT_CONFIG = {
    'calculator': {
        'mode': 'single',
        'parallel': True,
        'max_workers': 4,
        'cache_enabled': True,
        'cache_ttl': 3600,
        'cache_backend': 'memory'
    },
    'cache': {
        'max_size': 1000,
        'ttl': 3600,
        'backend': 'memory'
    }
}

# ============================================================
# CLASSES DE GESTION
# ============================================================

class IndicatorManager:
    """
    Gestionnaire unifié des indicateurs.
    Intègre factory, cache et calculator.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise le gestionnaire d'indicateurs.
        
        Args:
            config: Configuration du gestionnaire.
        """
        self.config = config or DEFAULT_CONFIG
        
        # Composants
        self.factory = get_indicator_factory()
        self.cache = None
        self.calculator = None
        
        # Initialisation
        self._initialize()
        
        logger.info("IndicatorManager initialisé")
    
    def _initialize(self) -> None:
        """Initialise les composants."""
        # Cache
        cache_config = self.config.get('cache', {})
        if cache_config.get('enabled', True):
            self.cache = create_indicator_cache(
                backend=cache_config.get('backend', 'memory'),
                max_size=cache_config.get('max_size', 1000),
                ttl=cache_config.get('ttl', 3600)
            )
        
        # Calculateur
        calc_config = self.config.get('calculator', {})
        self.calculator = create_indicator_calculator(
            mode=calc_config.get('mode', 'single'),
            parallel=calc_config.get('parallel', True),
            max_workers=calc_config.get('max_workers', 4),
            cache_enabled=calc_config.get('cache_enabled', True),
            cache_ttl=calc_config.get('cache_ttl', 3600),
            cache_backend=calc_config.get('cache_backend', 'memory')
        )
    
    def calculate(
        self,
        data: pd.DataFrame,
        indicators: Optional[List[str]] = None,
        use_cache: bool = True,
        force_refresh: bool = False,
        **kwargs
    ) -> CalculationResult:
        """
        Calcule les indicateurs.
        
        Args:
            data: Données OHLCV.
            indicators: Liste des indicateurs.
            use_cache: Utiliser le cache.
            force_refresh: Forcer le rafraîchissement.
            **kwargs: Paramètres supplémentaires.
            
        Returns:
            Résultat du calcul.
        """
        if self.calculator is None:
            raise IndicatorError("Calculateur non initialisé")
        
        return self.calculator.calculate(
            data,
            indicator_names=indicators,
            use_cache=use_cache,
            force_refresh=force_refresh,
            params=kwargs
        )
    
    def get_indicator(
        self,
        name: str,
        symbol: str,
        timeframe: str = "1h",
        **kwargs
    ) -> BaseIndicator:
        """
        Crée un indicateur.
        
        Args:
            name: Nom de l'indicateur.
            symbol: Symbole.
            timeframe: Timeframe.
            **kwargs: Paramètres supplémentaires.
            
        Returns:
            Instance de l'indicateur.
        """
        return self.factory.create(name, symbol, timeframe, **kwargs)
    
    def get_info(self, name: str) -> Optional[IndicatorInfo]:
        """Récupère les informations d'un indicateur."""
        return self.factory.get_info(name)
    
    def list_indicators(self) -> Dict[str, IndicatorInfo]:
        """Liste tous les indicateurs disponibles."""
        return self.factory.get_all_info()
    
    def clear_cache(self) -> None:
        """Vide le cache."""
        if self.cache:
            self.cache.clear()
        if self.calculator:
            self.calculator.clear_cache()
        logger.info("Cache vidé")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du gestionnaire.
        
        Returns:
            Statistiques.
        """
        stats = {
            'indicator_count': len(self.factory.get_available()),
            'categories': self.factory.get_categories(),
            'types': self.factory.get_types()
        }
        
        if self.calculator:
            stats['calculator'] = self.calculator.get_stats()
        
        if self.cache:
            stats['cache'] = self.cache.get_stats()
        
        return stats
    
    def reset(self) -> None:
        """Réinitialise le gestionnaire."""
        if self.calculator:
            self.calculator.reset()
        if self.cache:
            self.cache.clear()
        logger.info("IndicatorManager réinitialisé")

# ============================================================
# INITIALISATION DU MODULE
# ============================================================

logger.info("=" * 60)
logger.info("NEXUS AI TRADING SYSTEM - Indicators Module")
logger.info(f"Version: {__version__}")
logger.info(f"Copyright: {__copyright__}")
logger.info("=" * 60)
logger.info(f"Indicator categories: {len(INDICATOR_CATEGORIES)}")
logger.info(f"Indicator types: {len(INDICATOR_TYPES)}")
logger.info(f"Default indicators: {len(DEFAULT_INDICATORS)}")
logger.info("=" * 60)

# ============================================================
# EXPORTATION COMPLÈTE
# ============================================================

__all__ = [
    # Classes principales
    'BaseIndicator',
    'IndicatorConfig',
    'IndicatorResult',
    'IndicatorState',
    'IndicatorCategory',
    'IndicatorType',
    'MarketSentimentIndicator',
    'OrderFlowIndicator',
    'MarketRegimeIndicator',
    'CrossCorrelationIndicator',
    'AdaptiveVolatilityIndicator',
    'MarketCycleIndicator',
    'AdvancedRSIIndicator',
    'CustomIndicatorFactory',
    'IndicatorFactory',
    'IndicatorFactorySingleton',
    'IndicatorRegistry',
    'IndicatorInfo',
    'IndicatorCache',
    'CacheConfig',
    'CacheEntry',
    'CacheBackend',
    'IndicatorCalculator',
    'CalculatorConfig',
    'CalculationResult',
    'CalculationMode',
    'IndicatorPriority',
    'IndicatorDependency',
    'IndicatorManager',
    
    # Fonctions rapides
    'get_indicator_factory',
    'create_indicator',
    'create_indicator_cache',
    'create_indicator_calculator',
    'quick_calculate_indicator',
    'quick_calculate_multi',
    'quick_list_indicators',
    'quick_get_indicator_info',
    'validate_indicator_result',
    'compare_indicators',
    
    # Constantes
    'INDICATOR_CATEGORIES',
    'INDICATOR_TYPES',
    'CACHE_BACKENDS',
    'CALCULATION_MODES',
    'INDICATOR_PRIORITIES',
    'DEFAULT_INDICATORS',
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

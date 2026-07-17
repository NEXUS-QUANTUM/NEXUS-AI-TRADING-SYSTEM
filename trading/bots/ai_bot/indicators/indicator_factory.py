"""
NEXUS AI TRADING SYSTEM - Indicator Factory for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/indicators/indicator_factory.py
Description: Fabrique d'indicateurs techniques pour le bot AI.
             Gère la création, l'enregistrement, la découverte
             et l'instanciation des indicateurs standards et
             personnalisés. Supporte le chargement dynamique
             et la validation des indicateurs.
"""

import logging
import inspect
import importlib
import sys
from typing import Dict, List, Any, Optional, Type, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

from trading.bots.ai_bot.indicators.base_indicator import (
    BaseIndicator,
    IndicatorConfig,
    IndicatorCategory,
    IndicatorType
)
from shared.exceptions import IndicatorError

# Configuration du logging
logger = logging.getLogger(__name__)


class IndicatorRegistry:
    """
    Registre central des indicateurs.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialise le registre."""
        self._indicators: Dict[str, Type[BaseIndicator]] = {}
        self._aliases: Dict[str, str] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._loaded_modules: List[str] = []
        logger.info("IndicatorRegistry initialisé")
    
    def register(
        self,
        indicator_class: Type[BaseIndicator],
        name: Optional[str] = None,
        alias: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Enregistre un indicateur.
        
        Args:
            indicator_class: Classe de l'indicateur.
            name: Nom de l'indicateur.
            alias: Alias supplémentaires.
            metadata: Métadonnées.
        """
        if not issubclass(indicator_class, BaseIndicator):
            raise IndicatorError("La classe doit hériter de BaseIndicator")
        
        indicator_name = name or indicator_class.__name__
        
        # Enregistrement
        self._indicators[indicator_name] = indicator_class
        
        # Alias
        if alias:
            for a in alias:
                self._aliases[a] = indicator_name
        
        # Métadonnées
        self._metadata[indicator_name] = metadata or self._extract_metadata(indicator_class)
        
        logger.debug(f"Indicateur enregistré: {indicator_name}")
    
    def unregister(self, name: str) -> bool:
        """
        Désenregistre un indicateur.
        
        Args:
            name: Nom de l'indicateur.
            
        Returns:
            True si désenregistré.
        """
        if name in self._indicators:
            del self._indicators[name]
            # Supprimer les alias associés
            to_remove = [k for k, v in self._aliases.items() if v == name]
            for k in to_remove:
                del self._aliases[k]
            if name in self._metadata:
                del self._metadata[name]
            logger.debug(f"Indicateur désenregistré: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[Type[BaseIndicator]]:
        """
        Récupère un indicateur par son nom.
        
        Args:
            name: Nom de l'indicateur.
            
        Returns:
            Classe de l'indicateur ou None.
        """
        # Résolution de l'alias
        actual_name = self._aliases.get(name, name)
        return self._indicators.get(actual_name)
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les métadonnées d'un indicateur.
        
        Args:
            name: Nom de l'indicateur.
            
        Returns:
            Métadonnées ou None.
        """
        actual_name = self._aliases.get(name, name)
        return self._metadata.get(actual_name)
    
    def get_all(self) -> Dict[str, Type[BaseIndicator]]:
        """
        Retourne tous les indicateurs.
        
        Returns:
            Dictionnaire des indicateurs.
        """
        return self._indicators.copy()
    
    def get_available(self) -> List[str]:
        """
        Retourne la liste des indicateurs disponibles.
        
        Returns:
            Liste des noms.
        """
        return list(self._indicators.keys())
    
    def _extract_metadata(self, indicator_class: Type[BaseIndicator]) -> Dict[str, Any]:
        """
        Extrait les métadonnées d'un indicateur.
        
        Args:
            indicator_class: Classe de l'indicateur.
            
        Returns:
            Métadonnées.
        """
        metadata = {
            'name': indicator_class.__name__,
            'module': indicator_class.__module__,
            'docstring': inspect.getdoc(indicator_class) or "",
            'parameters': {}
        }
        
        # Extraire les paramètres par défaut
        if hasattr(indicator_class, 'get_default_params'):
            try:
                params = indicator_class.get_default_params()
                metadata['parameters'] = params
            except:
                pass
        
        # Extraire les catégories
        if hasattr(indicator_class, 'config'):
            config = getattr(indicator_class, 'config')
            if hasattr(config, 'category'):
                metadata['category'] = config.category.value
            if hasattr(config, 'indicator_type'):
                metadata['type'] = config.indicator_type.value
        
        return metadata
    
    def load_module(self, module_name: str) -> None:
        """
        Charge un module d'indicateurs.
        
        Args:
            module_name: Nom du module.
        """
        if module_name in self._loaded_modules:
            return
        
        try:
            module = importlib.import_module(module_name)
            
            # Découverte automatique des indicateurs
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (inspect.isclass(attr) and 
                    issubclass(attr, BaseIndicator) and 
                    attr != BaseIndicator):
                    self.register(attr)
            
            self._loaded_modules.append(module_name)
            logger.info(f"Module chargé: {module_name}")
            
        except Exception as e:
            logger.error(f"Erreur de chargement du module {module_name}: {e}")
    
    def discover(self, package: str = "trading.bots.ai_bot.indicators") -> None:
        """
        Découvre automatiquement les indicateurs.
        
        Args:
            package: Package à explorer.
        """
        try:
            import pkgutil
            import importlib
            
            package_obj = importlib.import_module(package)
            package_path = package_obj.__path__
            
            for _, module_name, _ in pkgutil.iter_modules(package_path):
                full_name = f"{package}.{module_name}"
                if full_name not in self._loaded_modules:
                    self.load_module(full_name)
            
            logger.info(f"Découverte terminée: {len(self._indicators)} indicateurs trouvés")
            
        except Exception as e:
            logger.error(f"Erreur de découverte: {e}")


@dataclass
class IndicatorInfo:
    """
    Informations sur un indicateur.
    """
    name: str
    class_name: str
    module: str
    description: str
    category: Optional[str] = None
    indicator_type: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = "NEXUS QUANTUM LTD"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'name': self.name,
            'class_name': self.class_name,
            'module': self.module,
            'description': self.description,
            'category': self.category,
            'indicator_type': self.indicator_type,
            'parameters': self.parameters,
            'aliases': self.aliases,
            'version': self.version,
            'author': self.author
        }


class IndicatorFactory:
    """
    Fabrique d'indicateurs techniques.
    """
    
    def __init__(self):
        """
        Initialise la fabrique.
        """
        self._registry = IndicatorRegistry()
        self._config_cache: Dict[str, IndicatorConfig] = {}
        
        # Enregistrement des indicateurs standards
        self._register_standard_indicators()
        
        logger.info("IndicatorFactory initialisé")
    
    def _register_standard_indicators(self) -> None:
        """
        Enregistre les indicateurs standards.
        """
        # Les indicateurs standards seront importés dynamiquement
        # pour éviter les dépendances circulaires
        
        # Importer et enregistrer les indicateurs standards
        try:
            from trading.bots.ai_bot.indicators.custom_indicators import (
                MarketSentimentIndicator,
                OrderFlowIndicator,
                MarketRegimeIndicator,
                CrossCorrelationIndicator,
                AdaptiveVolatilityIndicator,
                MarketCycleIndicator,
                AdvancedRSIIndicator
            )
            
            self.register(
                MarketSentimentIndicator,
                name="market_sentiment",
                alias=["sentiment", "msi"],
                metadata={
                    'category': 'custom',
                    'type': 'oscillator',
                    'description': 'Market sentiment indicator'
                }
            )
            
            self.register(
                OrderFlowIndicator,
                name="order_flow",
                alias=["flow", "ofi"],
                metadata={
                    'category': 'custom',
                    'type': 'volume_based',
                    'description': 'Order flow imbalance indicator'
                }
            )
            
            self.register(
                MarketRegimeIndicator,
                name="market_regime",
                alias=["regime", "mri"],
                metadata={
                    'category': 'custom',
                    'type': 'composite',
                    'description': 'Market regime detection'
                }
            )
            
            self.register(
                CrossCorrelationIndicator,
                name="cross_correlation",
                alias=["correlation", "cci"],
                metadata={
                    'category': 'custom',
                    'type': 'statistical',
                    'description': 'Cross-correlation between assets'
                }
            )
            
            self.register(
                AdaptiveVolatilityIndicator,
                name="adaptive_volatility",
                alias=["volatility", "avi"],
                metadata={
                    'category': 'custom',
                    'type': 'volatility',
                    'description': 'Adaptive volatility indicator'
                }
            )
            
            self.register(
                MarketCycleIndicator,
                name="market_cycle",
                alias=["cycle", "mci"],
                metadata={
                    'category': 'custom',
                    'type': 'cycle',
                    'description': 'Market cycle detection'
                }
            )
            
            self.register(
                AdvancedRSIIndicator,
                name="advanced_rsi",
                alias=["arsi", "rsi_advanced"],
                metadata={
                    'category': 'custom',
                    'type': 'momentum',
                    'description': 'Advanced RSI with divergence detection'
                }
            )
            
        except ImportError as e:
            logger.warning(f"Erreur d'import des indicateurs standards: {e}")
    
    def create(
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
        # Résolution du nom
        actual_name = self._registry._aliases.get(name, name)
        
        # Récupération de la classe
        indicator_class = self._registry.get(actual_name)
        
        if not indicator_class:
            raise IndicatorError(f"Indicateur inconnu: {name}")
        
        # Création de la configuration
        config = IndicatorConfig(
            name=actual_name,
            symbol=symbol,
            timeframe=timeframe,
            params=kwargs
        )
        
        # Création de l'instance
        try:
            instance = indicator_class(config)
            return instance
        except Exception as e:
            raise IndicatorError(f"Erreur de création de l'indicateur {name}: {e}")
    
    def register(
        self,
        indicator_class: Type[BaseIndicator],
        name: Optional[str] = None,
        alias: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Enregistre un indicateur.
        
        Args:
            indicator_class: Classe de l'indicateur.
            name: Nom de l'indicateur.
            alias: Alias supplémentaires.
            metadata: Métadonnées.
        """
        self._registry.register(indicator_class, name, alias, metadata)
    
    def get_info(self, name: str) -> Optional[IndicatorInfo]:
        """
        Retourne les informations d'un indicateur.
        
        Args:
            name: Nom de l'indicateur.
            
        Returns:
            Informations de l'indicateur.
        """
        actual_name = self._registry._aliases.get(name, name)
        indicator_class = self._registry.get(actual_name)
        
        if not indicator_class:
            return None
        
        metadata = self._registry.get_metadata(actual_name) or {}
        
        # Trouver les alias
        aliases = [k for k, v in self._registry._aliases.items() if v == actual_name]
        
        return IndicatorInfo(
            name=actual_name,
            class_name=indicator_class.__name__,
            module=indicator_class.__module__,
            description=metadata.get('description', ''),
            category=metadata.get('category'),
            indicator_type=metadata.get('type'),
            parameters=metadata.get('parameters', {}),
            aliases=aliases,
            version=metadata.get('version', '1.0.0'),
            author=metadata.get('author', 'NEXUS QUANTUM LTD')
        )
    
    def get_available(self) -> List[str]:
        """
        Retourne la liste des indicateurs disponibles.
        
        Returns:
            Liste des noms.
        """
        return self._registry.get_available()
    
    def get_all_info(self) -> Dict[str, IndicatorInfo]:
        """
        Retourne les informations de tous les indicateurs.
        
        Returns:
            Dictionnaire des informations.
        """
        result = {}
        for name in self.get_available():
            info = self.get_info(name)
            if info:
                result[name] = info
        return result
    
    def get_by_category(self, category: str) -> List[str]:
        """
        Retourne les indicateurs d'une catégorie.
        
        Args:
            category: Catégorie.
            
        Returns:
            Liste des noms.
        """
        result = []
        for name in self.get_available():
            metadata = self._registry.get_metadata(name)
            if metadata and metadata.get('category') == category:
                result.append(name)
        return result
    
    def get_by_type(self, indicator_type: str) -> List[str]:
        """
        Retourne les indicateurs d'un type.
        
        Args:
            indicator_type: Type d'indicateur.
            
        Returns:
            Liste des noms.
        """
        result = []
        for name in self.get_available():
            metadata = self._registry.get_metadata(name)
            if metadata and metadata.get('type') == indicator_type:
                result.append(name)
        return result
    
    def discover(self) -> None:
        """
        Découvre automatiquement les indicateurs.
        """
        self._registry.discover()
    
    def validate(self, name: str) -> bool:
        """
        Valide un indicateur.
        
        Args:
            name: Nom de l'indicateur.
            
        Returns:
            True si valide.
        """
        actual_name = self._registry._aliases.get(name, name)
        indicator_class = self._registry.get(actual_name)
        
        if not indicator_class:
            return False
        
        # Vérification de l'héritage
        if not issubclass(indicator_class, BaseIndicator):
            return False
        
        # Vérification des méthodes
        required_methods = ['calculate', 'update', 'get_default_params']
        for method in required_methods:
            if not hasattr(indicator_class, method):
                return False
        
        return True
    
    def get_categories(self) -> List[str]:
        """
        Retourne la liste des catégories disponibles.
        
        Returns:
            Liste des catégories.
        """
        categories = set()
        for name in self.get_available():
            metadata = self._registry.get_metadata(name)
            if metadata and 'category' in metadata:
                categories.add(metadata['category'])
        return sorted(list(categories))
    
    def get_types(self) -> List[str]:
        """
        Retourne la liste des types disponibles.
        
        Returns:
            Liste des types.
        """
        types = set()
        for name in self.get_available():
            metadata = self._registry.get_metadata(name)
            if metadata and 'type' in metadata:
                types.add(metadata['type'])
        return sorted(list(types))
    
    def clear(self) -> None:
        """
        Vide la fabrique.
        """
        self._registry = IndicatorRegistry()
        self._config_cache.clear()
        logger.info("IndicatorFactory vidée")


# ============================================================
# SINGLETON
# ============================================================

class IndicatorFactorySingleton:
    """
    Singleton de la fabrique d'indicateurs.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = IndicatorFactory()
        return cls._instance


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def get_indicator_factory() -> IndicatorFactory:
    """
    Retourne l'instance singleton de la fabrique.
    
    Returns:
        Instance de la fabrique.
    """
    return IndicatorFactorySingleton()


def create_indicator(
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
    factory = get_indicator_factory()
    return factory.create(name, symbol, timeframe, **kwargs)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'IndicatorFactory',
    'IndicatorFactorySingleton',
    'IndicatorRegistry',
    'IndicatorInfo',
    'get_indicator_factory',
    'create_indicator'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

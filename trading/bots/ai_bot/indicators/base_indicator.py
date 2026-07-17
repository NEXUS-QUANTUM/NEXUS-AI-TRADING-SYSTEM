"""
NEXUS AI TRADING SYSTEM - Base Indicator for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/indicators/base_indicator.py
Description: Classe de base pour tous les indicateurs techniques du bot AI.
             Définit l'interface standard pour le calcul, la mise à jour,
             le caching et la sérialisation des indicateurs.
             Supporte les indicateurs temps réel et historiques.
"""

import logging
import time
import hashlib
import json
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

from shared.exceptions import IndicatorError
from shared.helpers.number_helpers import round_decimal
from shared.helpers.date_helpers import timestamp_to_datetime

# Configuration du logging
logger = logging.getLogger(__name__)


class IndicatorCategory(Enum):
    """Catégories d'indicateurs."""
    TREND = "trend"                  # Indicateurs de tendance
    MOMENTUM = "momentum"            # Indicateurs de momentum
    VOLATILITY = "volatility"        # Indicateurs de volatilité
    VOLUME = "volume"                # Indicateurs de volume
    OVERLAY = "overlay"              # Indicateurs de superposition
    CYCLE = "cycle"                  # Indicateurs cycliques
    STATISTICAL = "statistical"      # Indicateurs statistiques
    CUSTOM = "custom"                # Indicateurs personnalisés


class IndicatorType(Enum):
    """Types d'indicateurs."""
    OSCILLATOR = "oscillator"        # Oscillateur
    MOVING_AVERAGE = "moving_average" # Moyenne mobile
    BAND = "band"                    # Bande
    ENVELOPE = "envelope"            # Enveloppe
    CHANNEL = "channel"              # Canal
    VOLUME_BASED = "volume_based"    # Basé sur le volume
    PRICE_BASED = "price_based"      # Basé sur le prix
    COMPOSITE = "composite"          # Composite


@dataclass
class IndicatorConfig:
    """
    Configuration de base d'un indicateur.
    """
    # Identifiants
    name: str = ""
    symbol: str = ""
    timeframe: str = "1h"
    
    # Paramètres
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Périodes
    lookback: int = 100
    warmup: int = 20
    
    # Comportement
    realtime: bool = False
    cache_enabled: bool = True
    cache_ttl: int = 60  # secondes
    
    # Métadonnées
    category: IndicatorCategory = IndicatorCategory.CUSTOM
    indicator_type: IndicatorType = IndicatorType.PRICE_BASED
    description: str = ""
    version: str = "1.0.0"
    
    def __post_init__(self):
        """Validation des paramètres."""
        if not self.name:
            self.name = self.__class__.__name__
        
        if self.lookback < 1:
            raise IndicatorError("lookback doit être >= 1")
        
        if self.warmup < 1:
            raise IndicatorError("warmup doit être >= 1")


@dataclass
class IndicatorResult:
    """
    Résultat d'un indicateur.
    """
    # Valeurs
    values: Union[pd.Series, np.ndarray, float]
    timestamp: Union[datetime, pd.DatetimeIndex]
    
    # Métadonnées
    name: str = ""
    symbol: str = ""
    timeframe: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Métriques
    min_value: float = 0.0
    max_value: float = 0.0
    mean_value: float = 0.0
    std_value: float = 0.0
    last_value: float = 0.0
    
    # Statut
    is_ready: bool = True
    is_valid: bool = True
    computed_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Post-initialisation."""
        if len(self.values) > 0:
            self.min_value = float(np.min(self.values))
            self.max_value = float(np.max(self.values))
            self.mean_value = float(np.mean(self.values))
            self.std_value = float(np.std(self.values))
            self.last_value = float(self.values[-1])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'name': self.name,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'params': self.params,
            'min_value': round(self.min_value, 6),
            'max_value': round(self.max_value, 6),
            'mean_value': round(self.mean_value, 6),
            'std_value': round(self.std_value, 6),
            'last_value': round(self.last_value, 6),
            'is_ready': self.is_ready,
            'is_valid': self.is_valid,
            'computed_at': self.computed_at.isoformat()
        }


@dataclass
class IndicatorState:
    """
    État interne d'un indicateur.
    """
    # Données
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    last_update: Optional[datetime] = None
    last_hash: str = ""
    
    # Résultats
    result: Optional[IndicatorResult] = None
    history: List[IndicatorResult] = field(default_factory=list)
    
    # Statut
    is_initialized: bool = False
    is_calculating: bool = False
    error_count: int = 0
    calculation_count: int = 0
    
    # Cache
    cache: Dict[str, IndicatorResult] = field(default_factory=dict)
    cache_timestamps: Dict[str, datetime] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'is_initialized': self.is_initialized,
            'is_calculating': self.is_calculating,
            'error_count': self.error_count,
            'calculation_count': self.calculation_count,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'last_hash': self.last_hash,
            'cache_size': len(self.cache)
        }


class BaseIndicator(ABC):
    """
    Classe de base pour tous les indicateurs techniques.
    """
    
    def __init__(self, config: IndicatorConfig):
        """
        Initialise l'indicateur.
        
        Args:
            config: Configuration de l'indicateur.
        """
        self.config = config
        self.state = IndicatorState()
        
        # Validation
        self._validate_config()
        
        logger.info(f"BaseIndicator initialisé: {self.config.name}")
        logger.info(f"Symbole: {self.config.symbol}, Timeframe: {self.config.timeframe}")
        logger.info(f"Category: {self.config.category.value}, Type: {self.config.indicator_type.value}")
    
    def _validate_config(self) -> None:
        """Valide la configuration."""
        if not self.config.name:
            raise IndicatorError("Nom de l'indicateur requis")
        
        if not self.config.symbol:
            raise IndicatorError("Symbole requis")
        
        if not self.config.timeframe:
            raise IndicatorError("Timeframe requis")
    
    # ============================================================
    # MÉTHODES ABSTRAITES
    # ============================================================
    
    @abstractmethod
    def calculate(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None
    ) -> IndicatorResult:
        """
        Calcule l'indicateur sur les données.
        
        Args:
            data: DataFrame OHLCV.
            params: Paramètres supplémentaires.
            
        Returns:
            Résultat de l'indicateur.
        """
        pass
    
    @abstractmethod
    def update(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """
        Met à jour l'indicateur avec de nouvelles données.
        
        Args:
            new_data: Nouvelles données OHLCV.
            
        Returns:
            Résultat mis à jour ou None.
        """
        pass
    
    @abstractmethod
    def get_default_params(self) -> Dict[str, Any]:
        """
        Retourne les paramètres par défaut.
        
        Returns:
            Paramètres par défaut.
        """
        pass
    
    # ============================================================
    # MÉTHODES CONCRÈTES
    # ============================================================
    
    def initialize(self, data: pd.DataFrame) -> None:
        """
        Initialise l'indicateur avec des données historiques.
        
        Args:
            data: Données historiques.
        """
        logger.info(f"Initialisation de {self.config.name} avec {len(data)} bars")
        
        try:
            # Vérification des données
            if data.empty:
                raise IndicatorError("Données vides pour l'initialisation")
            
            # Validation des colonnes
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing = [c for c in required_cols if c not in data.columns]
            if missing:
                raise IndicatorError(f"Colonnes manquantes: {missing}")
            
            # Sauvegarde des données
            self.state.data = data.copy()
            
            # Warmup
            warmup_data = data.iloc[:self.config.warmup]
            if len(warmup_data) < self.config.warmup:
                logger.warning(f"Warmup insuffisant: {len(warmup_data)} < {self.config.warmup}")
            else:
                self._warmup(warmup_data)
            
            # Calcul initial
            result = self.calculate(data)
            self.state.result = result
            
            # État
            self.state.is_initialized = True
            self.state.last_update = datetime.now()
            
            logger.info(f"Initialisation terminée pour {self.config.name}")
            
        except Exception as e:
            logger.error(f"Erreur d'initialisation: {e}")
            self.state.error_count += 1
            raise IndicatorError(f"Erreur d'initialisation: {e}")
    
    def _warmup(self, data: pd.DataFrame) -> None:
        """
        Warmup de l'indicateur.
        
        Args:
            data: Données de warmup.
        """
        # Par défaut, calcul normal
        pass
    
    def update_async(self, new_data: pd.DataFrame) -> Optional[IndicatorResult]:
        """
        Met à jour l'indicateur de manière asynchrone.
        
        Args:
            new_data: Nouvelles données.
            
        Returns:
            Résultat mis à jour ou None.
        """
        if self.state.is_calculating:
            logger.debug("Calcul en cours, mise à jour ignorée")
            return None
        
        try:
            self.state.is_calculating = True
            
            # Mise à jour
            result = self.update(new_data)
            
            # Mise en cache
            if result and self.config.cache_enabled:
                cache_key = self._generate_cache_key(new_data)
                self.state.cache[cache_key] = result
                self.state.cache_timestamps[cache_key] = datetime.now()
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur de mise à jour: {e}")
            self.state.error_count += 1
            return None
            
        finally:
            self.state.is_calculating = False
    
    def get_latest(self, force_refresh: bool = False) -> Optional[IndicatorResult]:
        """
        Retourne le dernier résultat.
        
        Args:
            force_refresh: Forcer le rafraîchissement.
            
        Returns:
            Dernier résultat ou None.
        """
        if not self.state.is_initialized:
            logger.warning("Indicateur non initialisé")
            return None
        
        if force_refresh and self.state.data is not None and not self.state.data.empty:
            self.state.result = self.calculate(self.state.data)
        
        return self.state.result
    
    def get_history(self, n: Optional[int] = None) -> List[IndicatorResult]:
        """
        Retourne l'historique des résultats.
        
        Args:
            n: Nombre d'éléments.
            
        Returns:
            Liste des résultats historiques.
        """
        history = self.state.history.copy()
        if n is not None:
            return history[-n:]
        return history
    
    def clear_history(self) -> None:
        """
        Vide l'historique.
        """
        self.state.history.clear()
        logger.info(f"Historique vidé pour {self.config.name}")
    
    def reset(self) -> None:
        """
        Réinitialise l'indicateur.
        """
        self.state = IndicatorState()
        logger.info(f"Indicateur {self.config.name} réinitialisé")
    
    # ============================================================
    # MÉTHODES DE CACHE
    # ============================================================
    
    def _generate_cache_key(self, data: pd.DataFrame) -> str:
        """
        Génère une clé de cache.
        
        Args:
            data: Données.
            
        Returns:
            Clé de cache.
        """
        data_hash = hashlib.md5(data.to_json().encode()).hexdigest()
        return f"{self.config.name}_{self.config.symbol}_{data_hash}"
    
    def clear_cache(self) -> None:
        """
        Vide le cache.
        """
        self.state.cache.clear()
        self.state.cache_timestamps.clear()
        logger.info(f"Cache vidé pour {self.config.name}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du cache.
        
        Returns:
            Statistiques du cache.
        """
        return {
            'size': len(self.state.cache),
            'entries': list(self.state.cache.keys()),
            'ttl': self.config.cache_ttl
        }
    
    # ============================================================
    # MÉTHODES DE SÉRIALISATION
    # ============================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit l'indicateur en dictionnaire.
        
        Returns:
            Dictionnaire de l'indicateur.
        """
        return {
            'name': self.config.name,
            'symbol': self.config.symbol,
            'timeframe': self.config.timeframe,
            'category': self.config.category.value,
            'type': self.config.indicator_type.value,
            'params': self.config.params,
            'description': self.config.description,
            'version': self.config.version,
            'state': self.state.to_dict(),
            'result': self.state.result.to_dict() if self.state.result else None
        }
    
    def to_json(self) -> str:
        """
        Convertit l'indicateur en JSON.
        
        Returns:
            JSON de l'indicateur.
        """
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseIndicator':
        """
        Crée un indicateur à partir d'un dictionnaire.
        
        Args:
            data: Dictionnaire de l'indicateur.
            
        Returns:
            Instance de l'indicateur.
        """
        config = IndicatorConfig(
            name=data.get('name', ''),
            symbol=data.get('symbol', ''),
            timeframe=data.get('timeframe', '1h'),
            params=data.get('params', {}),
            category=IndicatorCategory(data.get('category', 'custom')),
            indicator_type=IndicatorType(data.get('type', 'price_based')),
            description=data.get('description', ''),
            version=data.get('version', '1.0.0')
        )
        return cls(config)
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def get_name(self) -> str:
        """Retourne le nom de l'indicateur."""
        return self.config.name
    
    def get_symbol(self) -> str:
        """Retourne le symbole."""
        return self.config.symbol
    
    def get_timeframe(self) -> str:
        """Retourne le timeframe."""
        return self.config.timeframe
    
    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres."""
        return self.config.params.copy()
    
    def get_state(self) -> Dict[str, Any]:
        """Retourne l'état de l'indicateur."""
        return self.state.to_dict()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut de l'indicateur.
        
        Returns:
            Statut de l'indicateur.
        """
        return {
            'name': self.config.name,
            'initialized': self.state.is_initialized,
            'ready': self.state.is_initialized and self.state.result is not None,
            'last_update': self.state.last_update.isoformat() if self.state.last_update else None,
            'calculation_count': self.state.calculation_count,
            'error_count': self.state.error_count
        }
    
    def is_ready(self) -> bool:
        """
        Vérifie si l'indicateur est prêt.
        
        Returns:
            True si prêt.
        """
        return self.state.is_initialized and self.state.result is not None
    
    def set_param(self, key: str, value: Any) -> None:
        """
        Définit un paramètre.
        
        Args:
            key: Nom du paramètre.
            value: Valeur.
        """
        self.config.params[key] = value
        logger.info(f"Paramètre {key} = {value} défini pour {self.config.name}")
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """
        Récupère un paramètre.
        
        Args:
            key: Nom du paramètre.
            default: Valeur par défaut.
            
        Returns:
            Valeur du paramètre.
        """
        return self.config.params.get(key, default)
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Valide les données.
        
        Args:
            data: Données à valider.
            
        Returns:
            True si valides.
        """
        if data is None or data.empty:
            logger.warning("Données vides")
            return False
        
        # Colonnes requises
        required = ['open', 'high', 'low', 'close', 'volume']
        if not all(c in data.columns for c in required):
            logger.warning(f"Colonnes manquantes: {required}")
            return False
        
        return True
    
    def _merge_data(self, existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        """
        Fusionne les données existantes avec les nouvelles.
        
        Args:
            existing: Données existantes.
            new: Nouvelles données.
            
        Returns:
            DataFrame fusionné.
        """
        if new.empty:
            return existing
        
        # Concaténation
        merged = pd.concat([existing, new])
        
        # Suppression des doublons
        merged = merged.drop_duplicates(subset=['timestamp'])
        
        # Tri par timestamp
        merged = merged.sort_values('timestamp')
        
        return merged
    
    def _ensure_timeframe(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Assure que les données sont au bon timeframe.
        
        Args:
            data: Données à vérifier.
            
        Returns:
            DataFrame vérifié.
        """
        # Vérification de la colonne timestamp
        if 'timestamp' not in data.columns:
            raise IndicatorError("Colonne 'timestamp' manquante")
        
        # Conversion en datetime
        if not pd.api.types.is_datetime64_any_dtype(data['timestamp']):
            data['timestamp'] = pd.to_datetime(data['timestamp'])
        
        # Tri
        data = data.sort_values('timestamp')
        
        return data


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def validate_indicator_result(result: IndicatorResult) -> bool:
    """
    Valide un résultat d'indicateur.
    
    Args:
        result: Résultat à valider.
        
    Returns:
        True si valide.
    """
    if result is None:
        return False
    
    if not result.is_valid:
        return False
    
    if not result.is_ready:
        return False
    
    if len(result.values) == 0:
        return False
    
    return True


def compare_indicators(
    ind1: BaseIndicator,
    ind2: BaseIndicator,
    data: pd.DataFrame
) -> Dict[str, Any]:
    """
    Compare deux indicateurs.
    
    Args:
        ind1: Premier indicateur.
        ind2: Deuxième indicateur.
        data: Données de test.
        
    Returns:
        Résultats de la comparaison.
    """
    result1 = ind1.calculate(data)
    result2 = ind2.calculate(data)
    
    return {
        'indicator1': {
            'name': ind1.get_name(),
            'last_value': result1.last_value,
            'min': result1.min_value,
            'max': result1.max_value,
            'mean': result1.mean_value
        },
        'indicator2': {
            'name': ind2.get_name(),
            'last_value': result2.last_value,
            'min': result2.min_value,
            'max': result2.max_value,
            'mean': result2.mean_value
        },
        'correlation': np.corrcoef(
            result1.values if len(result1.values) > 0 else [0],
            result2.values if len(result2.values) > 0 else [0]
        )[0, 1] if len(result1.values) > 0 and len(result2.values) > 0 else 0
    }


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'BaseIndicator',
    'IndicatorConfig',
    'IndicatorResult',
    'IndicatorState',
    'IndicatorCategory',
    'IndicatorType',
    'validate_indicator_result',
    'compare_indicators'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

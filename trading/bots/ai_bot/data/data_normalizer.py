"""
NEXUS AI TRADING SYSTEM - Data Normalizer for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/data/data_normalizer.py
Description: Normaliseur de données pour les modèles AI.
             Supporte les techniques de normalisation avancées:
             Standardization (Z-score), Min-Max, Robust Scaling,
             Quantile Transformation, Power Transformation, 
             Log Transformation, et Normalization par batch.
             Permet d'adapter les données aux exigences des modèles AI.
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import boxcox
from sklearn.preprocessing import (
    StandardScaler,
    MinMaxScaler,
    RobustScaler,
    QuantileTransformer,
    PowerTransformer,
    Normalizer
)
from sklearn.decomposition import PCA

from shared.exceptions import NormalizationError
from shared.helpers.number_helpers import round_decimal

# Configuration du logging
logger = logging.getLogger(__name__)


class NormalizationMethod(Enum):
    """Méthodes de normalisation."""
    STANDARD = "standard"          # Z-score normalization
    MINMAX = "minmax"              # Min-Max scaling [0,1]
    ROBUST = "robust"              # Robust scaling (using median/IQR)
    QUANTILE = "quantile"          # Quantile transformation
    POWER = "power"                # Power transformation (Box-Cox, Yeo-Johnson)
    LOG = "log"                    # Log transformation
    UNIT = "unit"                  # Unit vector normalization
    BATCH = "batch"                # Batch normalization
    ADAPTIVE = "adaptive"          # Adaptive normalization
    SEQUENTIAL = "sequential"      # Sequential normalization (time series)
    COMPLEX = "complex"            # Complex number normalization


@dataclass
class NormalizationConfig:
    """
    Configuration de la normalisation.
    """
    # Méthode principale
    method: NormalizationMethod = NormalizationMethod.STANDARD
    
    # Paramètres Standard
    standard_mean: Optional[float] = None
    standard_std: Optional[float] = None
    
    # Paramètres Min-Max
    minmax_min: Optional[float] = None
    minmax_max: Optional[float] = None
    minmax_range: Tuple[float, float] = (0, 1)
    
    # Paramètres Robust
    robust_center: Optional[float] = None
    robust_scale: Optional[float] = None
    robust_quantile_range: Tuple[float, float] = (25, 75)
    
    # Paramètres Quantile
    quantile_n_quantiles: int = 1000
    quantile_output_distribution: str = "uniform"  # "uniform" ou "normal"
    quantile_subsample: int = 10000
    
    # Paramètres Power
    power_method: str = "yeo-johnson"  # "box-cox" ou "yeo-johnson"
    power_lambda: Optional[float] = None
    
    # Paramètres Batch
    batch_momentum: float = 0.9
    batch_epsilon: float = 1e-5
    batch_center: bool = True
    batch_scale: bool = True
    
    # Paramètres Adaptatifs
    adaptive_window: int = 100
    adaptive_learning_rate: float = 0.01
    
    # Paramètres Séquentiels
    sequential_window: int = 100
    sequential_lookback: int = 50
    
    # Paramètres généraux
    fit_per_feature: bool = True
    preserve_shape: bool = True
    handle_nan: str = "mean"  # "mean", "median", "zero", "remove"
    handle_inf: str = "clip"  # "clip", "remove", "zero"
    random_state: Optional[int] = 42
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.quantile_n_quantiles < 10:
            raise NormalizationError("quantile_n_quantiles doit être >= 10")
        
        if self.power_method not in ["box-cox", "yeo-johnson"]:
            raise NormalizationError("power_method doit être 'box-cox' ou 'yeo-johnson'")
        
        if self.batch_momentum < 0 or self.batch_momentum > 1:
            raise NormalizationError("batch_momentum doit être entre 0 et 1")
        
        if self.batch_epsilon <= 0:
            raise NormalizationError("batch_epsilon doit être > 0")
        
        if self.adaptive_window < 2:
            raise NormalizationError("adaptive_window doit être >= 2")


@dataclass
class NormalizationStats:
    """
    Statistiques de normalisation.
    """
    # Statistiques des données
    original_mean: float = 0.0
    original_std: float = 0.0
    original_min: float = 0.0
    original_max: float = 0.0
    original_median: float = 0.0
    
    # Statistiques normalisées
    normalized_mean: float = 0.0
    normalized_std: float = 0.0
    normalized_min: float = 0.0
    normalized_max: float = 0.0
    
    # Paramètres de normalisation
    method: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Performance
    fit_time: float = 0.0
    transform_time: float = 0.0
    n_features: int = 0
    n_samples: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'original_mean': round(self.original_mean, 6),
            'original_std': round(self.original_std, 6),
            'original_min': round(self.original_min, 6),
            'original_max': round(self.original_max, 6),
            'original_median': round(self.original_median, 6),
            'normalized_mean': round(self.normalized_mean, 6),
            'normalized_std': round(self.normalized_std, 6),
            'normalized_min': round(self.normalized_min, 6),
            'normalized_max': round(self.normalized_max, 6),
            'method': self.method,
            'params': self.params,
            'fit_time': round(self.fit_time, 4),
            'transform_time': round(self.transform_time, 4),
            'n_features': self.n_features,
            'n_samples': self.n_samples
        }


class DataNormalizer:
    """
    Normaliseur de données pour les modèles AI.
    """
    
    def __init__(self, config: Optional[NormalizationConfig] = None):
        """
        Initialise le normaliseur.
        
        Args:
            config: Configuration de la normalisation.
        """
        self.config = config or NormalizationConfig()
        self.stats = NormalizationStats()
        
        # Scalers sklearn
        self._scalers: Dict[str, Any] = {}
        self._fitted = False
        
        # Pour les méthodes adaptatives
        self._adaptive_means: Dict[str, float] = {}
        self._adaptive_stds: Dict[str, float] = {}
        self._adaptive_counts: Dict[str, int] = {}
        
        # Pour les méthodes séquentielles
        self._sequential_buffer: Dict[str, List[float]] = {}
        self._sequential_means: Dict[str, float] = {}
        self._sequential_stds: Dict[str, float] = {}
        
        # Cache
        self._transform_cache: Dict[str, np.ndarray] = {}
        self._inverse_cache: Dict[str, np.ndarray] = {}
        
        logger.info(f"DataNormalizer initialisé - Méthode: {self.config.method.value}")
    
    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================
    
    def fit(self, data: Union[np.ndarray, pd.DataFrame, List]) -> None:
        """
        Ajuste le normaliseur sur les données.
        
        Args:
            data: Données d'entraînement.
        """
        start_time = time.time()
        
        data_array = self._to_array(data)
        
        if len(data_array) == 0:
            raise NormalizationError("Données vides")
        
        logger.info(f"Ajustement du normaliseur sur {len(data_array)} échantillons")
        
        # Nettoyage
        data_array = self._clean_data(data_array)
        
        # Calcul des statistiques originales
        self.stats.original_mean = float(np.mean(data_array))
        self.stats.original_std = float(np.std(data_array))
        self.stats.original_min = float(np.min(data_array))
        self.stats.original_max = float(np.max(data_array))
        self.stats.original_median = float(np.median(data_array))
        self.stats.n_samples = len(data_array)
        self.stats.n_features = data_array.shape[1] if len(data_array.shape) > 1 else 1
        
        # Ajustement selon la méthode
        if self.config.method == NormalizationMethod.STANDARD:
            self._fit_standard(data_array)
        elif self.config.method == NormalizationMethod.MINMAX:
            self._fit_minmax(data_array)
        elif self.config.method == NormalizationMethod.ROBUST:
            self._fit_robust(data_array)
        elif self.config.method == NormalizationMethod.QUANTILE:
            self._fit_quantile(data_array)
        elif self.config.method == NormalizationMethod.POWER:
            self._fit_power(data_array)
        elif self.config.method == NormalizationMethod.UNIT:
            self._fit_unit(data_array)
        elif self.config.method == NormalizationMethod.BATCH:
            self._fit_batch(data_array)
        elif self.config.method == NormalizationMethod.ADAPTIVE:
            self._fit_adaptive(data_array)
        elif self.config.method == NormalizationMethod.SEQUENTIAL:
            self._fit_sequential(data_array)
        else:
            raise NormalizationError(f"Méthode non supportée: {self.config.method}")
        
        self._fitted = True
        
        # Vérification
        normalized = self.transform(data_array)
        self.stats.normalized_mean = float(np.mean(normalized))
        self.stats.normalized_std = float(np.std(normalized))
        self.stats.normalized_min = float(np.min(normalized))
        self.stats.normalized_max = float(np.max(normalized))
        
        self.stats.method = self.config.method.value
        self.stats.fit_time = time.time() - start_time
        
        logger.info(f"Ajustement terminé en {self.stats.fit_time:.3f}s")
        logger.info(f"Normalisé: mean={self.stats.normalized_mean:.4f}, "
                   f"std={self.stats.normalized_std:.4f}")
    
    def transform(self, data: Union[np.ndarray, pd.DataFrame, List]) -> np.ndarray:
        """
        Transforme les données en les normalisant.
        
        Args:
            data: Données à normaliser.
            
        Returns:
            Données normalisées.
        """
        if not self._fitted:
            raise NormalizationError("Le normaliseur doit être ajusté d'abord")
        
        start_time = time.time()
        
        data_array = self._to_array(data)
        
        if len(data_array) == 0:
            return np.array([])
        
        # Nettoyage
        data_array = self._clean_data(data_array)
        
        # Transformation selon la méthode
        if self.config.method == NormalizationMethod.STANDARD:
            transformed = self._transform_standard(data_array)
        elif self.config.method == NormalizationMethod.MINMAX:
            transformed = self._transform_minmax(data_array)
        elif self.config.method == NormalizationMethod.ROBUST:
            transformed = self._transform_robust(data_array)
        elif self.config.method == NormalizationMethod.QUANTILE:
            transformed = self._transform_quantile(data_array)
        elif self.config.method == NormalizationMethod.POWER:
            transformed = self._transform_power(data_array)
        elif self.config.method == NormalizationMethod.UNIT:
            transformed = self._transform_unit(data_array)
        elif self.config.method == NormalizationMethod.BATCH:
            transformed = self._transform_batch(data_array)
        elif self.config.method == NormalizationMethod.ADAPTIVE:
            transformed = self._transform_adaptive(data_array)
        elif self.config.method == NormalizationMethod.SEQUENTIAL:
            transformed = self._transform_sequential(data_array)
        else:
            raise NormalizationError(f"Méthode non supportée: {self.config.method}")
        
        self.stats.transform_time = time.time() - start_time
        
        return transformed
    
    def fit_transform(self, data: Union[np.ndarray, pd.DataFrame, List]) -> np.ndarray:
        """
        Ajuste et transforme les données.
        
        Args:
            data: Données à normaliser.
            
        Returns:
            Données normalisées.
        """
        self.fit(data)
        return self.transform(data)
    
    def inverse_transform(self, data: Union[np.ndarray, pd.DataFrame, List]) -> np.ndarray:
        """
        Inverse la transformation (retour aux échelles originales).
        
        Args:
            data: Données normalisées.
            
        Returns:
            Données dans l'échelle originale.
        """
        if not self._fitted:
            raise NormalizationError("Le normaliseur doit être ajusté d'abord")
        
        data_array = self._to_array(data)
        
        if len(data_array) == 0:
            return np.array([])
        
        # Transformation inverse selon la méthode
        if self.config.method == NormalizationMethod.STANDARD:
            return self._inverse_standard(data_array)
        elif self.config.method == NormalizationMethod.MINMAX:
            return self._inverse_minmax(data_array)
        elif self.config.method == NormalizationMethod.ROBUST:
            return self._inverse_robust(data_array)
        elif self.config.method == NormalizationMethod.QUANTILE:
            return self._inverse_quantile(data_array)
        elif self.config.method == NormalizationMethod.POWER:
            return self._inverse_power(data_array)
        elif self.config.method == NormalizationMethod.UNIT:
            return self._inverse_unit(data_array)
        elif self.config.method == NormalizationMethod.BATCH:
            return self._inverse_batch(data_array)
        elif self.config.method == NormalizationMethod.ADAPTIVE:
            return self._inverse_adaptive(data_array)
        elif self.config.method == NormalizationMethod.SEQUENTIAL:
            return self._inverse_sequential(data_array)
        else:
            raise NormalizationError(f"Méthode non supportée: {self.config.method}")
    
    # ============================================================
    # MÉTHODES DE NORMALISATION
    # ============================================================
    
    # --- Standard ---
    
    def _fit_standard(self, data: np.ndarray) -> None:
        """Ajuste la normalisation standard."""
        mean = self.config.standard_mean if self.config.standard_mean is not None else np.mean(data, axis=0)
        std = self.config.standard_std if self.config.standard_std is not None else np.std(data, axis=0)
        
        self._scalers['mean'] = mean
        self._scalers['std'] = std
        self.stats.params = {'mean': float(mean) if np.isscalar(mean) else mean.tolist(),
                             'std': float(std) if np.isscalar(std) else std.tolist()}
    
    def _transform_standard(self, data: np.ndarray) -> np.ndarray:
        """Applique la normalisation standard."""
        mean = self._scalers['mean']
        std = self._scalers['std']
        
        # Éviter la division par zéro
        std = np.where(std < 1e-8, 1, std)
        
        return (data - mean) / std
    
    def _inverse_standard(self, data: np.ndarray) -> np.ndarray:
        """Inverse la normalisation standard."""
        mean = self._scalers['mean']
        std = self._scalers['std']
        
        return data * std + mean
    
    # --- Min-Max ---
    
    def _fit_minmax(self, data: np.ndarray) -> None:
        """Ajuste la normalisation Min-Max."""
        min_val = self.config.minmax_min if self.config.minmax_min is not None else np.min(data, axis=0)
        max_val = self.config.minmax_max if self.config.minmax_max is not None else np.max(data, axis=0)
        
        # Éviter la division par zéro
        range_val = max_val - min_val
        range_val = np.where(range_val < 1e-8, 1, range_val)
        
        self._scalers['min'] = min_val
        self._scalers['range'] = range_val
        self._scalers['range_min'] = self.config.minmax_range[0]
        self._scalers['range_max'] = self.config.minmax_range[1]
        
        self.stats.params = {
            'min': float(min_val) if np.isscalar(min_val) else min_val.tolist(),
            'range': float(range_val) if np.isscalar(range_val) else range_val.tolist()
        }
    
    def _transform_minmax(self, data: np.ndarray) -> np.ndarray:
        """Applique la normalisation Min-Max."""
        min_val = self._scalers['min']
        range_val = self._scalers['range']
        range_min = self._scalers['range_min']
        range_max = self._scalers['range_max']
        
        normalized = (data - min_val) / range_val
        return normalized * (range_max - range_min) + range_min
    
    def _inverse_minmax(self, data: np.ndarray) -> np.ndarray:
        """Inverse la normalisation Min-Max."""
        min_val = self._scalers['min']
        range_val = self._scalers['range']
        range_min = self._scalers['range_min']
        range_max = self._scalers['range_max']
        
        normalized = (data - range_min) / (range_max - range_min)
        return normalized * range_val + min_val
    
    # --- Robust ---
    
    def _fit_robust(self, data: np.ndarray) -> None:
        """Ajuste la normalisation robuste."""
        center = self.config.robust_center if self.config.robust_center is not None else np.median(data, axis=0)
        q1, q3 = self.config.robust_quantile_range
        q1_val = np.percentile(data, q1, axis=0)
        q3_val = np.percentile(data, q3, axis=0)
        iqr = q3_val - q1_val
        iqr = np.where(iqr < 1e-8, 1, iqr)
        
        self._scalers['center'] = center
        self._scalers['iqr'] = iqr
        
        self.stats.params = {
            'center': float(center) if np.isscalar(center) else center.tolist(),
            'iqr': float(iqr) if np.isscalar(iqr) else iqr.tolist()
        }
    
    def _transform_robust(self, data: np.ndarray) -> np.ndarray:
        """Applique la normalisation robuste."""
        center = self._scalers['center']
        iqr = self._scalers['iqr']
        
        return (data - center) / iqr
    
    def _inverse_robust(self, data: np.ndarray) -> np.ndarray:
        """Inverse la normalisation robuste."""
        center = self._scalers['center']
        iqr = self._scalers['iqr']
        
        return data * iqr + center
    
    # --- Quantile ---
    
    def _fit_quantile(self, data: np.ndarray) -> None:
        """Ajuste la transformation quantile."""
        self._scalers['quantile'] = QuantileTransformer(
            n_quantiles=self.config.quantile_n_quantiles,
            output_distribution=self.config.quantile_output_distribution,
            subsample=self.config.quantile_subsample,
            random_state=self.config.random_state
        )
        self._scalers['quantile'].fit(data)
    
    def _transform_quantile(self, data: np.ndarray) -> np.ndarray:
        """Applique la transformation quantile."""
        return self._scalers['quantile'].transform(data)
    
    def _inverse_quantile(self, data: np.ndarray) -> np.ndarray:
        """Inverse la transformation quantile."""
        return self._scalers['quantile'].inverse_transform(data)
    
    # --- Power ---
    
    def _fit_power(self, data: np.ndarray) -> None:
        """Ajuste la transformation puissance."""
        self._scalers['power'] = PowerTransformer(
            method=self.config.power_method,
            standardize=False
        )
        self._scalers['power'].fit(data)
        self.stats.params['lambda'] = self._scalers['power'].lambdas_.tolist()
    
    def _transform_power(self, data: np.ndarray) -> np.ndarray:
        """Applique la transformation puissance."""
        return self._scalers['power'].transform(data)
    
    def _inverse_power(self, data: np.ndarray) -> np.ndarray:
        """Inverse la transformation puissance."""
        return self._scalers['power'].inverse_transform(data)
    
    # --- Unit ---
    
    def _fit_unit(self, data: np.ndarray) -> None:
        """Ajuste la normalisation unitaire."""
        self._scalers['unit'] = Normalizer(norm='l2')
        self._scalers['unit'].fit(data)
    
    def _transform_unit(self, data: np.ndarray) -> np.ndarray:
        """Applique la normalisation unitaire."""
        return self._scalers['unit'].transform(data)
    
    def _inverse_unit(self, data: np.ndarray) -> np.ndarray:
        """Inverse la normalisation unitaire."""
        # La normalisation unitaire n'est pas inversible directement
        # On utilise une approximation
        return data / np.linalg.norm(data, axis=1, keepdims=True)
    
    # --- Batch ---
    
    def _fit_batch(self, data: np.ndarray) -> None:
        """Ajuste la normalisation par batch."""
        mean = np.mean(data, axis=0)
        var = np.var(data, axis=0)
        
        self._scalers['batch_mean'] = mean
        self._scalers['batch_var'] = var
        self._scalers['batch_epsilon'] = self.config.batch_epsilon
        self._scalers['batch_center'] = self.config.batch_center
        self._scalers['batch_scale'] = self.config.batch_scale
    
    def _transform_batch(self, data: np.ndarray) -> np.ndarray:
        """Applique la normalisation par batch."""
        mean = self._scalers['batch_mean']
        var = self._scalers['batch_var']
        eps = self._scalers['batch_epsilon']
        center = self._scalers['batch_center']
        scale = self._scalers['batch_scale']
        
        if center and scale:
            return (data - mean) / np.sqrt(var + eps)
        elif center:
            return data - mean
        elif scale:
            return data / np.sqrt(var + eps)
        else:
            return data
    
    def _inverse_batch(self, data: np.ndarray) -> np.ndarray:
        """Inverse la normalisation par batch."""
        mean = self._scalers['batch_mean']
        var = self._scalers['batch_var']
        eps = self._scalers['batch_epsilon']
        center = self._scalers['batch_center']
        scale = self._scalers['batch_scale']
        
        if center and scale:
            return data * np.sqrt(var + eps) + mean
        elif center:
            return data + mean
        elif scale:
            return data * np.sqrt(var + eps)
        else:
            return data
    
    # --- Adaptive ---
    
    def _fit_adaptive(self, data: np.ndarray) -> None:
        """Ajuste la normalisation adaptative."""
        # Initialisation avec les premières données
        self._adaptive_means['global'] = np.mean(data, axis=0)
        self._adaptive_stds['global'] = np.std(data, axis=0)
        self._adaptive_counts['global'] = len(data)
    
    def _transform_adaptive(self, data: np.ndarray) -> np.ndarray:
        """Applique la normalisation adaptative."""
        # Mise à jour des statistiques
        batch_mean = np.mean(data, axis=0)
        batch_std = np.std(data, axis=0)
        batch_count = len(data)
        
        # Mise à jour exponentielle
        lr = self.config.adaptive_learning_rate
        current_mean = self._adaptive_means['global']
        current_std = self._adaptive_stds['global']
        
        self._adaptive_means['global'] = current_mean * (1 - lr) + batch_mean * lr
        self._adaptive_stds['global'] = current_std * (1 - lr) + batch_std * lr
        
        # Normalisation
        mean = self._adaptive_means['global']
        std = self._adaptive_stds['global']
        std = np.where(std < 1e-8, 1, std)
        
        return (data - mean) / std
    
    def _inverse_adaptive(self, data: np.ndarray) -> np.ndarray:
        """Inverse la normalisation adaptative."""
        mean = self._adaptive_means['global']
        std = self._adaptive_stds['global']
        std = np.where(std < 1e-8, 1, std)
        
        return data * std + mean
    
    # --- Sequential ---
    
    def _fit_sequential(self, data: np.ndarray) -> None:
        """Ajuste la normalisation séquentielle."""
        window = self.config.sequential_window
        
        for i in range(len(data)):
            start = max(0, i - window)
            window_data = data[start:i+1]
            
            self._sequential_buffer[f'seq_{i}'] = window_data.tolist()
            self._sequential_means[f'seq_{i}'] = np.mean(window_data)
            self._sequential_stds[f'seq_{i}'] = np.std(window_data)
    
    def _transform_sequential(self, data: np.ndarray) -> np.ndarray:
        """Applique la normalisation séquentielle."""
        window = self.config.sequential_window
        lookback = self.config.sequential_lookback
        
        normalized = np.zeros_like(data)
        
        for i in range(len(data)):
            # Fenêtre glissante
            start = max(0, i - window)
            end = i + 1
            window_data = data[start:end]
            
            # Statistiques de la fenêtre
            mean = np.mean(window_data)
            std = np.std(window_data)
            std = max(std, 1e-8)
            
            normalized[i] = (data[i] - mean) / std
        
        return normalized
    
    def _inverse_sequential(self, data: np.ndarray) -> np.ndarray:
        """Inverse la normalisation séquentielle."""
        # Approximation: utiliser les statistiques globales
        if self._sequential_means:
            mean = np.mean(list(self._sequential_means.values()))
            std = np.mean(list(self._sequential_stds.values()))
            std = max(std, 1e-8)
        else:
            mean = 0
            std = 1
        
        return data * std + mean
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def _to_array(self, data: Union[np.ndarray, pd.DataFrame, List]) -> np.ndarray:
        """
        Convertit les données en array numpy.
        
        Args:
            data: Données à convertir.
            
        Returns:
            Array numpy.
        """
        if isinstance(data, pd.DataFrame):
            return data.values
        elif isinstance(data, list):
            return np.array(data)
        elif isinstance(data, np.ndarray):
            return data
        else:
            raise NormalizationError(f"Type de données non supporté: {type(data)}")
    
    def _clean_data(self, data: np.ndarray) -> np.ndarray:
        """
        Nettoie les données.
        
        Args:
            data: Données à nettoyer.
            
        Returns:
            Données nettoyées.
        """
        if self.config.handle_nan == "remove":
            data = data[~np.isnan(data).any(axis=1)]
        elif self.config.handle_nan == "mean":
            data = np.nan_to_num(data, nan=np.nanmean(data))
        elif self.config.handle_nan == "median":
            data = np.nan_to_num(data, nan=np.nanmedian(data))
        else:  # zero
            data = np.nan_to_num(data, nan=0)
        
        if self.config.handle_inf == "remove":
            data = data[~np.isinf(data).any(axis=1)]
        elif self.config.handle_inf == "clip":
            data = np.clip(data, -1e10, 1e10)
        else:  # zero
            data = np.where(np.isinf(data), 0, data)
        
        return data
    
    def get_params(self) -> Dict[str, Any]:
        """
        Retourne les paramètres de normalisation.
        
        Returns:
            Paramètres de normalisation.
        """
        return {
            'method': self.config.method.value,
            'fitted': self._fitted,
            'stats': self.stats.to_dict(),
            'scalers': {k: v for k, v in self._scalers.items() 
                       if not isinstance(v, (QuantileTransformer, PowerTransformer, Normalizer))}
        }
    
    def reset(self) -> None:
        """
        Réinitialise le normaliseur.
        """
        self._fitted = False
        self._scalers.clear()
        self._adaptive_means.clear()
        self._adaptive_stds.clear()
        self._adaptive_counts.clear()
        self._sequential_buffer.clear()
        self._sequential_means.clear()
        self._sequential_stds.clear()
        self._transform_cache.clear()
        self._inverse_cache.clear()
        self.stats = NormalizationStats()
        
        logger.info("Normaliseur réinitialisé")
    
    def save(self, filepath: str) -> None:
        """
        Sauvegarde le normaliseur.
        
        Args:
            filepath: Chemin de sauvegarde.
        """
        import pickle
        import os
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump({
                'config': self.config,
                'stats': self.stats,
                'scalers': self._scalers,
                'fitted': self._fitted
            }, f)
        
        logger.info(f"Normaliseur sauvegardé: {filepath}")
    
    def load(self, filepath: str) -> None:
        """
        Charge un normaliseur sauvegardé.
        
        Args:
            filepath: Chemin de chargement.
        """
        import pickle
        
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        self.config = data['config']
        self.stats = data['stats']
        self._scalers = data['scalers']
        self._fitted = data['fitted']
        
        logger.info(f"Normaliseur chargé: {filepath}")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_normalizer(
    method: str = "standard",
    **kwargs
) -> DataNormalizer:
    """
    Crée un normaliseur avec configuration simplifiée.
    
    Args:
        method: Méthode de normalisation.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du DataNormalizer.
    """
    method_map = {
        'standard': NormalizationMethod.STANDARD,
        'minmax': NormalizationMethod.MINMAX,
        'robust': NormalizationMethod.ROBUST,
        'quantile': NormalizationMethod.QUANTILE,
        'power': NormalizationMethod.POWER,
        'log': NormalizationMethod.LOG,
        'unit': NormalizationMethod.UNIT,
        'batch': NormalizationMethod.BATCH,
        'adaptive': NormalizationMethod.ADAPTIVE,
        'sequential': NormalizationMethod.SEQUENTIAL
    }
    
    if method not in method_map:
        raise NormalizationError(f"Méthode inconnue: {method}")
    
    config = NormalizationConfig(method=method_map[method], **kwargs)
    return DataNormalizer(config)


def normalize_data(
    data: Union[np.ndarray, pd.DataFrame, List],
    method: str = "standard",
    **kwargs
) -> np.ndarray:
    """
    Normalise rapidement des données.
    
    Args:
        data: Données à normaliser.
        method: Méthode de normalisation.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Données normalisées.
    """
    normalizer = create_normalizer(method, **kwargs)
    return normalizer.fit_transform(data)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'DataNormalizer',
    'NormalizationConfig',
    'NormalizationStats',
    'NormalizationMethod',
    'create_normalizer',
    'normalize_data'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

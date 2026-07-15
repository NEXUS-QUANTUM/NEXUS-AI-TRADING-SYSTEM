# ai/models/forecasting/arima_model.py
"""
NEXUS AI TRADING SYSTEM - ARIMA Model for Time Series Forecasting
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import warnings
warnings.filterwarnings('ignore')

try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
    from statsmodels.tsa.seasonal import seasonal_decompose
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

try:
    from pmdarima import auto_arima
    PMDARIMA_AVAILABLE = True
except ImportError:
    PMDARIMA_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ARIMAConfig:
    order: Tuple[int, int, int] = (1, 1, 1)
    seasonal_order: Tuple[int, int, int, int] = (0, 0, 0, 0)
    trend: Optional[str] = None
    enforce_stationarity: bool = True
    enforce_invertibility: bool = True
    concentrate_scale: bool = False
    trend_offset: int = 1
    dates: Optional[pd.DatetimeIndex] = None
    freq: Optional[str] = None
    missing: str = 'none'
    validate_specification: bool = True

    def __post_init__(self):
        if not STATSMODELS_AVAILABLE:
            raise ImportError("Statsmodels n'est pas installé")


@dataclass
class ARIMAResult:
    predictions: np.ndarray
    confidence_intervals: Optional[np.ndarray] = None
    residuals: Optional[np.ndarray] = None
    aic: Optional[float] = None
    bic: Optional[float] = None
    log_likelihood: Optional[float] = None
    fitted_values: Optional[np.ndarray] = None
    forecast_steps: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    model_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'confidence_intervals': self.confidence_intervals.tolist() if isinstance(self.confidence_intervals, np.ndarray) else self.confidence_intervals,
            'residuals': self.residuals.tolist() if isinstance(self.residuals, np.ndarray) else self.residuals,
            'aic': self.aic,
            'bic': self.bic,
            'log_likelihood': self.log_likelihood,
            'fitted_values': self.fitted_values.tolist() if isinstance(self.fitted_values, np.ndarray) else self.fitted_values,
            'forecast_steps': self.forecast_steps,
            'timestamp': self.timestamp.isoformat(),
            'model_summary': self.model_summary,
        }


class ARIMAModel:
    """
    ARIMA (AutoRegressive Integrated Moving Average) model for time series forecasting.
    
    This implementation supports:
    - Standard ARIMA with configurable order (p, d, q)
    - Seasonal ARIMA (SARIMA) with seasonal order (P, D, Q, s)
    - Automatic order selection via auto_arima
    - Stationarity testing (ADF test)
    - Confidence intervals for predictions
    - Model diagnostics (residuals, AIC, BIC)
    
    Example:
        ```python
        # Create ARIMA model
        config = ARIMAConfig(order=(1, 1, 1))
        model = ARIMAModel(config)
        
        # Fit model
        model.fit(data)
        
        # Predict
        predictions = model.predict(steps=10)
        
        # Get forecast with confidence intervals
        forecast, conf_int = model.predict(steps=10, return_conf_int=True)
        ```
    """
    
    def __init__(self, config: Optional[ARIMAConfig] = None):
        if not STATSMODELS_AVAILABLE:
            raise ImportError("Statsmodels est requis. Installez avec: pip install statsmodels")
        
        self.config = config or ARIMAConfig()
        self.model: Optional[Any] = None
        self.fitted_model: Optional[Any] = None
        self.is_fitted = False
        self.data: Optional[np.ndarray] = None
        self.dates: Optional[pd.DatetimeIndex] = None
        self._prediction_cache: Dict[str, Any] = {}
        
        logger.info(f"ARIMAModel initialisé avec l'ordre {self.config.order}")
    
    def _check_stationarity(self, data: np.ndarray, significance_level: float = 0.05) -> bool:
        """Test de stationnarité ADF"""
        if not STATSMODELS_AVAILABLE:
            return True
        
        result = adfuller(data, autolag='AIC')
        p_value = result[1]
        
        logger.debug(f"Test ADF - p-value: {p_value:.4f}")
        
        if p_value < significance_level:
            logger.debug("La série est stationnaire")
            return True
        else:
            logger.warning("La série n'est pas stationnaire")
            return False
    
    def _make_stationary(self, data: np.ndarray, d: int = 1) -> np.ndarray:
        """Applique la différenciation pour rendre la série stationnaire"""
        if d <= 0:
            return data
        
        diff_data = data.copy()
        for _ in range(d):
            diff_data = np.diff(diff_data)
        
        return diff_data
    
    def _get_seasonal_order(self) -> Tuple[int, int, int, int]:
        """Retourne l'ordre saisonnier"""
        if hasattr(self.config, 'seasonal_order'):
            return self.config.seasonal_order
        return (0, 0, 0, 0)
    
    def _get_trend(self) -> Optional[str]:
        """Retourne la tendance"""
        if hasattr(self.config, 'trend'):
            return self.config.trend
        return None
    
    def _validate_data(self, data: Union[np.ndarray, pd.Series, List[float]]) -> np.ndarray:
        """Valide et convertit les données"""
        if isinstance(data, pd.Series):
            self.dates = data.index
            data = data.values
        elif isinstance(data, list):
            data = np.array(data)
        
        if not isinstance(data, np.ndarray):
            raise TypeError("Les données doivent être un tableau numpy, pandas Series ou liste")
        
        if len(data) < 10:
            raise ValueError("Les données doivent contenir au moins 10 points")
        
        if np.any(np.isnan(data)) or np.any(np.isinf(data)):
            raise ValueError("Les données contiennent des valeurs NaN ou Inf")
        
        return data.astype(np.float64)
    
    def _create_model(self, data: np.ndarray) -> Any:
        """Crée le modèle ARIMA"""
        if not STATSMODELS_AVAILABLE:
            raise ImportError("Statsmodels n'est pas installé")
        
        order = self.config.order
        seasonal_order = self._get_seasonal_order()
        trend = self._get_trend()
        
        if seasonal_order != (0, 0, 0, 0):
            # SARIMA
            model = ARIMA(
                data,
                order=order,
                seasonal_order=seasonal_order,
                trend=trend,
                enforce_stationarity=self.config.enforce_stationarity,
                enforce_invertibility=self.config.enforce_invertibility,
                concentrate_scale=self.config.concentrate_scale,
                trend_offset=self.config.trend_offset,
                dates=self.dates,
                freq=self.config.freq,
                missing=self.config.missing,
                validate_specification=self.config.validate_specification,
            )
        else:
            # ARIMA standard
            model = ARIMA(
                data,
                order=order,
                trend=trend,
                enforce_stationarity=self.config.enforce_stationarity,
                enforce_invertibility=self.config.enforce_invertibility,
                concentrate_scale=self.config.concentrate_scale,
                trend_offset=self.config.trend_offset,
                dates=self.dates,
                freq=self.config.freq,
                missing=self.config.missing,
                validate_specification=self.config.validate_specification,
            )
        
        return model
    
    def _auto_select_order(
        self,
        data: np.ndarray,
        max_p: int = 5,
        max_d: int = 2,
        max_q: int = 5,
        seasonal: bool = False,
        m: int = 1,
        **kwargs
    ) -> Tuple[int, int, int]:
        """Sélection automatique des paramètres ARIMA"""
        if not PMDARIMA_AVAILABLE:
            logger.warning("pmdarima non disponible, utilisation de l'ordre par défaut")
            return self.config.order
        
        if seasonal:
            model = auto_arima(
                data,
                start_p=0, max_p=max_p,
                start_d=0, max_d=max_d,
                start_q=0, max_q=max_q,
                seasonal=seasonal,
                m=m,
                trace=False,
                error_action='ignore',
                suppress_warnings=True,
                stepwise=True,
                **kwargs
            )
        else:
            model = auto_arima(
                data,
                start_p=0, max_p=max_p,
                start_d=0, max_d=max_d,
                start_q=0, max_q=max_q,
                seasonal=seasonal,
                trace=False,
                error_action='ignore',
                suppress_warnings=True,
                stepwise=True,
                **kwargs
            )
        
        order = model.order
        logger.info(f"Ordre sélectionné automatiquement: {order}")
        return order
    
    def fit(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        auto_optimize: bool = False,
        max_p: int = 5,
        max_d: int = 2,
        max_q: int = 5,
        seasonal: bool = False,
        m: int = 1,
        **kwargs
    ) -> 'ARIMAModel':
        """
        Entraîne le modèle ARIMA sur les données.
        
        Args:
            data: Données d'entraînement
            auto_optimize: Optimiser automatiquement les paramètres
            max_p: Ordre AR maximum pour auto_optimize
            max_d: Ordre de différenciation maximum pour auto_optimize
            max_q: Ordre MA maximum pour auto_optimize
            seasonal: Utiliser la saisonnalité
            m: Période saisonnière
            **kwargs: Arguments supplémentaires pour auto_arima
        
        Returns:
            ARIMAModel: Instance entraînée
        """
        self.data = self._validate_data(data)
        
        # Vérification de la stationnarité
        is_stationary = self._check_stationarity(self.data)
        d = self.config.order[1]
        
        if not is_stationary and d == 0:
            logger.warning("La série n'est pas stationnaire et d=0. Augmentation de d.")
            d = 1
            self.config.order = (self.config.order[0], d, self.config.order[2])
        
        # Optimisation automatique
        if auto_optimize:
            if PMDARIMA_AVAILABLE:
                order = self._auto_select_order(
                    self.data,
                    max_p=max_p,
                    max_d=max_d,
                    max_q=max_q,
                    seasonal=seasonal,
                    m=m,
                    **kwargs
                )
                self.config.order = order
            else:
                logger.warning("pmdarima non disponible pour l'optimisation automatique")
        
        # Création du modèle
        self.model = self._create_model(self.data)
        
        # Entraînement
        try:
            self.fitted_model = self.model.fit()
            self.is_fitted = True
            logger.info(f"Modèle entraîné - AIC: {self.fitted_model.aic:.2f}")
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement du modèle: {e}")
            raise
        
        return self
    
    def predict(
        self,
        steps: int = 1,
        return_conf_int: bool = False,
        conf_int_level: float = 0.95,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray], ARIMAResult]:
        """
        Effectue une prédiction pour les prochaines étapes.
        
        Args:
            steps: Nombre d'étapes à prédire
            return_conf_int: Retourner les intervalles de confiance
            conf_int_level: Niveau de confiance (0.95 = 95%)
            return_details: Retourner tous les détails du résultat
        
        Returns:
            np.ndarray: Prédictions
            Tuple[np.ndarray, np.ndarray]: (Prédictions, Intervalles de confiance)
            ARIMAResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")
        
        if self.fitted_model is None:
            raise ValueError("Aucun modèle entraîné disponible")
        
        if steps < 1:
            raise ValueError("steps doit être >= 1")
        
        cache_key = f"{steps}_{conf_int_level}_{return_conf_int}"
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            cached = self._prediction_cache[cache_key]
            if return_details:
                return cached
            elif return_conf_int:
                return cached.predictions, cached.confidence_intervals
            else:
                return cached.predictions
        
        try:
            # Prévision
            if return_conf_int:
                forecast_result = self.fitted_model.get_forecast(steps=steps)
                predictions = forecast_result.predicted_mean
                confidence_intervals = forecast_result.conf_int(alpha=1 - conf_int_level)
            else:
                predictions = self.fitted_model.forecast(steps=steps)
                confidence_intervals = None
            
            # Conversion en numpy
            if isinstance(predictions, pd.Series):
                predictions = predictions.values
            if isinstance(confidence_intervals, pd.DataFrame):
                confidence_intervals = confidence_intervals.values
            
            # Résidus
            residuals = None
            if hasattr(self.fitted_model, 'resid'):
                residuals = self.fitted_model.resid.values
            
            # Statistiques
            aic = getattr(self.fitted_model, 'aic', None)
            bic = getattr(self.fitted_model, 'bic', None)
            log_likelihood = getattr(self.fitted_model, 'llf', None)
            
            # Valeurs ajustées
            fitted_values = None
            if hasattr(self.fitted_model, 'fittedvalues'):
                fitted_values = self.fitted_model.fittedvalues.values
            
            # Résumé du modèle
            model_summary = None
            if hasattr(self.fitted_model, 'summary'):
                try:
                    model_summary = str(self.fitted_model.summary())
                except:
                    pass
            
            result = ARIMAResult(
                predictions=predictions,
                confidence_intervals=confidence_intervals,
                residuals=residuals,
                aic=aic,
                bic=bic,
                log_likelihood=log_likelihood,
                fitted_values=fitted_values,
                forecast_steps=steps,
                model_summary=model_summary,
            )
            
            self._prediction_cache[cache_key] = result
            
            if return_details:
                return result
            elif return_conf_int:
                return predictions, confidence_intervals
            else:
                return predictions
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {e}")
            raise
    
    def forecast(
        self,
        steps: int = 1,
        conf_int_level: float = 0.95
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Shortcut pour la prévision avec intervalles de confiance.
        
        Args:
            steps: Nombre d'étapes à prédire
            conf_int_level: Niveau de confiance
        
        Returns:
            Tuple[np.ndarray, np.ndarray]: (Prédictions, Intervalles de confiance)
        """
        return self.predict(
            steps=steps,
            return_conf_int=True,
            conf_int_level=conf_int_level
        )
    
    def get_residuals(self) -> Optional[np.ndarray]:
        """Retourne les résidus du modèle"""
        if not self.is_fitted or self.fitted_model is None:
            return None
        
        if hasattr(self.fitted_model, 'resid'):
            return self.fitted_model.resid.values
        return None
    
    def get_summary(self) -> Optional[str]:
        """Retourne le résumé du modèle"""
        if not self.is_fitted or self.fitted_model is None:
            return None
        
        if hasattr(self.fitted_model, 'summary'):
            try:
                return str(self.fitted_model.summary())
            except:
                return None
        return None
    
    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du modèle"""
        params = {
            'order': self.config.order,
            'seasonal_order': self._get_seasonal_order(),
            'trend': self._get_trend(),
            'enforce_stationarity': self.config.enforce_stationarity,
            'enforce_invertibility': self.config.enforce_invertibility,
            'is_fitted': self.is_fitted,
        }
        
        if self.is_fitted and self.fitted_model is not None:
            params.update({
                'aic': self.fitted_model.aic,
                'bic': self.fitted_model.bic,
                'log_likelihood': self.fitted_model.llf,
                'nobs': self.fitted_model.nobs,
            })
        
        return params
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de performance du modèle"""
        metrics = {
            'aic': None,
            'bic': None,
            'log_likelihood': None,
            'nobs': None,
            'residuals_std': None,
            'residuals_mean': None,
        }
        
        if self.is_fitted and self.fitted_model is not None:
            metrics['aic'] = getattr(self.fitted_model, 'aic', None)
            metrics['bic'] = getattr(self.fitted_model, 'bic', None)
            metrics['log_likelihood'] = getattr(self.fitted_model, 'llf', None)
            metrics['nobs'] = getattr(self.fitted_model, 'nobs', None)
            
            residuals = self.get_residuals()
            if residuals is not None:
                metrics['residuals_std'] = np.std(residuals)
                metrics['residuals_mean'] = np.mean(residuals)
        
        return metrics
    
    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le modèle sur le disque.
        
        Args:
            filepath: Chemin du fichier
        
        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            data = {
                'config': self.config,
                'fitted_model': self.fitted_model,
                'data': self.data,
                'dates': self.dates,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            logger.info(f"Modèle sauvegardé: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False
    
    @classmethod
    def load(cls, filepath: str) -> 'ARIMAModel':
        """
        Charge un modèle depuis le disque.
        
        Args:
            filepath: Chemin du fichier
        
        Returns:
            ARIMAModel: Modèle chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            model = cls(data['config'])
            model.fitted_model = data['fitted_model']
            model.data = data.get('data')
            model.dates = data.get('dates')
            model.is_fitted = data.get('is_fitted', False)
            
            logger.info(f"Modèle chargé: {filepath}")
            return model
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise
    
    def plot_diagnostics(self, figsize: Tuple[int, int] = (12, 8)) -> None:
        """
        Affiche les diagnostics du modèle.
        
        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return
        
        if not self.is_fitted or self.fitted_model is None:
            logger.warning("Le modèle n'est pas entraîné")
            return
        
        try:
            import matplotlib.pyplot as plt
            
            fig, axes = plt.subplots(2, 2, figsize=figsize)
            
            # Résidus standardisés
            residuals = self.get_residuals()
            if residuals is not None:
                axes[0, 0].plot(residuals)
                axes[0, 0].set_title('Résidus')
                axes[0, 0].axhline(y=0, color='r', linestyle='--')
                
                # Histogramme des résidus
                axes[0, 1].hist(residuals, bins=30, edgecolor='black')
                axes[0, 1].set_title('Distribution des résidus')
                
                # ACF des résidus
                from statsmodels.graphics.tsaplots import plot_acf
                plot_acf(residuals, ax=axes[1, 0], lags=20)
                axes[1, 0].set_title('ACF des résidus')
                
                # Q-Q plot
                from scipy import stats
                stats.probplot(residuals, dist="norm", plot=axes[1, 1])
                axes[1, 1].set_title('Q-Q Plot')
            
            plt.tight_layout()
            plt.show()
            
        except Exception as e:
            logger.error(f"Erreur lors du tracé des diagnostics: {e}")
    
    def plot_forecast(
        self,
        steps: int = 10,
        conf_int_level: float = 0.95,
        figsize: Tuple[int, int] = (12, 6)
    ) -> None:
        """
        Affiche la prévision du modèle.
        
        Args:
            steps: Nombre d'étapes à prévoir
            conf_int_level: Niveau de confiance
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return
        
        if not self.is_fitted or self.fitted_model is None:
            logger.warning("Le modèle n'est pas entraîné")
            return
        
        try:
            import matplotlib.pyplot as plt
            
            predictions, conf_int = self.forecast(steps, conf_int_level)
            
            fig, ax = plt.subplots(figsize=figsize)
            
            # Données historiques
            if self.data is not None:
                ax.plot(self.data, label='Historique', color='blue')
            
            # Prévision
            forecast_idx = range(len(self.data), len(self.data) + steps) if self.data is not None else range(steps)
            ax.plot(forecast_idx, predictions, label='Prévision', color='red')
            
            # Intervalles de confiance
            if conf_int is not None:
                ax.fill_between(
                    forecast_idx,
                    conf_int[:, 0],
                    conf_int[:, 1],
                    color='red',
                    alpha=0.2,
                    label=f'Intervalle de confiance {conf_int_level*100:.0f}%'
                )
            
            ax.set_title(f'Prévision ARIMA ({steps} étapes)')
            ax.set_xlabel('Temps')
            ax.set_ylabel('Valeur')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.show()
            
        except Exception as e:
            logger.error(f"Erreur lors du tracé de la prévision: {e}")


def create_arima_model(
    order: Tuple[int, int, int] = (1, 1, 1),
    seasonal_order: Tuple[int, int, int, int] = (0, 0, 0, 0),
    trend: Optional[str] = None,
    **kwargs
) -> ARIMAModel:
    """
    Factory pour créer un modèle ARIMA.
    
    Args:
        order: Ordre (p, d, q)
        seasonal_order: Ordre saisonnier (P, D, Q, s)
        trend: Tendance ('c', 't', 'ct', etc.)
        **kwargs: Arguments supplémentaires
    
    Returns:
        ARIMAModel: Instance du modèle
    """
    config = ARIMAConfig(
        order=order,
        seasonal_order=seasonal_order,
        trend=trend,
        **kwargs
    )
    return ARIMAModel(config)


__all__ = [
    'ARIMAModel',
    'ARIMAConfig',
    'ARIMAResult',
    'create_arima_model',
]

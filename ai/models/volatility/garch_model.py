
# ai/models/volatility/garch_model.py
"""
NEXUS AI TRADING SYSTEM - GARCH Model for Volatility Forecasting
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
    from arch import arch_model
    ARCH_AVAILABLE = True
except ImportError:
    ARCH_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class GARCHConfig:
    p: int = 1
    q: int = 1
    o: int = 0
    power: float = 2.0
    vol: str = 'GARCH'
    dist: str = 'normal'
    mean: str = 'constant'
    lags: Optional[int] = None
    hold_back: Optional[int] = None
    scale: Optional[float] = None
    rescale: bool = True
    use_gpu: bool = False

    def __post_init__(self):
        if not ARCH_AVAILABLE:
            raise ImportError("Arch n'est pas installé")
        if self.vol not in ['GARCH', 'EGARCH', 'GJR-GARCH', 'TARCH', 'ARCH', 'FIGARCH']:
            raise ValueError(f"Type de volatilité non supporté: {self.vol}")
        if self.dist not in ['normal', 't', 'skewt', 'ged']:
            raise ValueError(f"Distribution non supportée: {self.dist}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'p': self.p,
            'q': self.q,
            'o': self.o,
            'power': self.power,
            'vol': self.vol,
            'dist': self.dist,
            'mean': self.mean,
            'lags': self.lags,
            'hold_back': self.hold_back,
            'scale': self.scale,
            'rescale': self.rescale,
            'use_gpu': self.use_gpu,
        }


@dataclass
class GARCHResult:
    predictions: np.ndarray
    conditional_volatility: np.ndarray
    residuals: Optional[np.ndarray] = None
    params: Optional[Dict[str, float]] = None
    aic: Optional[float] = None
    bic: Optional[float] = None
    log_likelihood: Optional[float] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    forecast_steps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'conditional_volatility': self.conditional_volatility.tolist() if isinstance(self.conditional_volatility, np.ndarray) else self.conditional_volatility,
            'residuals': self.residuals.tolist() if isinstance(self.residuals, np.ndarray) else self.residuals,
            'params': self.params,
            'aic': self.aic,
            'bic': self.bic,
            'log_likelihood': self.log_likelihood,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'forecast_steps': self.forecast_steps,
        }


class GARCHModel:
    """
    GARCH (Generalized Autoregressive Conditional Heteroskedasticity) model
    for volatility forecasting.

    This implementation supports:
    - GARCH, EGARCH, GJR-GARCH, TARCH, ARCH, FIGARCH
    - Normal, Student-t, Skewed-t, GED distributions
    - Volatility forecasting
    - Confidence intervals
    - Model diagnostics

    Example:
        ```python
        config = GARCHConfig(
            p=1,
            q=1,
            vol='GARCH',
            dist='normal',
            mean='constant'
        )
        model = GARCHModel(config)

        # Fit model
        model.fit(returns)

        # Forecast volatility
        predictions, vol = model.predict(steps=10)
        ```
    """

    def __init__(self, config: Optional[GARCHConfig] = None):
        if not ARCH_AVAILABLE:
            raise ImportError("Arch est requis. Installez avec: pip install arch")

        self.config = config or GARCHConfig()
        self.model: Optional[arch_model] = None
        self.fitted_model: Optional[Any] = None
        self.is_fitted = False
        self.data: Optional[np.ndarray] = None
        self._prediction_cache: Dict[str, Any] = {}

        logger.info(f"GARCHModel initialisé avec {self.config.vol}")

    def _validate_data(self, data: Union[np.ndarray, pd.Series, List[float]]) -> np.ndarray:
        """Valide et convertit les données"""
        if isinstance(data, pd.Series):
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

    def _create_model(self, data: np.ndarray) -> arch_model:
        """Crée le modèle GARCH"""
        return arch_model(
            data,
            p=self.config.p,
            q=self.config.q,
            o=self.config.o,
            power=self.config.power,
            vol=self.config.vol,
            dist=self.config.dist,
            mean=self.config.mean,
            lags=self.config.lags,
            hold_back=self.config.hold_back,
            scale=self.config.scale,
            rescale=self.config.rescale,
        )

    def fit(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        update_freq: int = 1,
        **kwargs
    ) -> 'GARCHModel':
        """
        Entraîne le modèle GARCH sur les données.

        Args:
            data: Données de rendements
            update_freq: Fréquence de mise à jour
            **kwargs: Arguments supplémentaires pour fit

        Returns:
            GARCHModel: Instance entraînée
        """
        self.data = self._validate_data(data)

        self.model = self._create_model(self.data)

        # Entraînement
        logger.info(f"Début de l'entraînement GARCH ({self.config.vol})")

        try:
            self.fitted_model = self.model.fit(
                update_freq=update_freq,
                disp='off',
                **kwargs
            )
            self.is_fitted = True

            logger.info(f"Entraînement terminé - AIC: {self.fitted_model.aic:.2f}")
            logger.info(f"Paramètres: {self.fitted_model.params}")

        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement: {e}")
            raise

        return self

    def predict(
        self,
        steps: int = 1,
        horizon: Optional[int] = None,
        return_volatility: bool = True,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray], GARCHResult]:
        """
        Effectue une prédiction de volatilité.

        Args:
            steps: Nombre d'étapes à prédire
            horizon: Horizon de prévision (identique à steps)
            return_volatility: Retourner la volatilité conditionnelle
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Prédictions
            Tuple: (Prédictions, Volatilité conditionnelle)
            GARCHResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")

        if self.fitted_model is None:
            raise ValueError("Aucun modèle entraîné disponible")

        if steps < 1:
            raise ValueError("steps doit être >= 1")

        if horizon is None:
            horizon = steps

        cache_key = f"{steps}_{horizon}_{return_volatility}"
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            cached = self._prediction_cache[cache_key]
            if return_details:
                return cached
            elif return_volatility:
                return cached.predictions, cached.conditional_volatility
            else:
                return cached.predictions

        try:
            # Prévision
            forecast = self.fitted_model.forecast(horizon=horizon)

            # Extraire les prédictions
            predictions = forecast.mean.iloc[-1].values
            conditional_volatility = forecast.variance.iloc[-1].values ** 0.5

            # Résidus
            residuals = None
            if hasattr(self.fitted_model, 'resid'):
                residuals = self.fitted_model.resid.values

            # Paramètres
            params = None
            if hasattr(self.fitted_model, 'params'):
                params = self.fitted_model.params.to_dict()

            # Métriques
            aic = getattr(self.fitted_model, 'aic', None)
            bic = getattr(self.fitted_model, 'bic', None)
            log_likelihood = getattr(self.fitted_model, 'loglikelihood', None)

            result = GARCHResult(
                predictions=predictions,
                conditional_volatility=conditional_volatility,
                residuals=residuals,
                params=params,
                aic=aic,
                bic=bic,
                log_likelihood=log_likelihood,
                forecast_steps=steps,
            )

            self._prediction_cache[cache_key] = result

            if return_details:
                return result
            elif return_volatility:
                return predictions, conditional_volatility
            else:
                return predictions

        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {e}")
            raise

    def get_conditional_volatility(self) -> Optional[np.ndarray]:
        """
        Retourne la volatilité conditionnelle estimée.

        Returns:
            Optional[np.ndarray]: Volatilité conditionnelle
        """
        if not self.is_fitted or self.fitted_model is None:
            return None

        if hasattr(self.fitted_model, 'conditional_volatility'):
            return self.fitted_model.conditional_volatility.values
        return None

    def get_residuals(self) -> Optional[np.ndarray]:
        """
        Retourne les résidus standardisés.

        Returns:
            Optional[np.ndarray]: Résidus standardisés
        """
        if not self.is_fitted or self.fitted_model is None:
            return None

        if hasattr(self.fitted_model, 'std_resid'):
            return self.fitted_model.std_resid.values
        return None

    def get_summary(self) -> Optional[str]:
        """
        Retourne le résumé du modèle.

        Returns:
            Optional[str]: Résumé du modèle
        """
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
            'p': self.config.p,
            'q': self.config.q,
            'o': self.config.o,
            'vol': self.config.vol,
            'dist': self.config.dist,
            'mean': self.config.mean,
            'is_fitted': self.is_fitted,
        }

        if self.is_fitted and self.fitted_model is not None:
            params.update({
                'aic': self.fitted_model.aic,
                'bic': self.fitted_model.bic,
                'log_likelihood': self.fitted_model.loglikelihood,
                'params': self.fitted_model.params.to_dict(),
            })

        return params

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de performance"""
        metrics = {
            'aic': None,
            'bic': None,
            'log_likelihood': None,
            'params': None,
        }

        if self.is_fitted and self.fitted_model is not None:
            metrics['aic'] = self.fitted_model.aic
            metrics['bic'] = self.fitted_model.bic
            metrics['log_likelihood'] = self.fitted_model.loglikelihood
            metrics['params'] = self.fitted_model.params.to_dict()

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
                'config': self.config.to_dict(),
                'fitted_model': self.fitted_model,
                'data': self.data,
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
    def load(cls, filepath: str) -> 'GARCHModel':
        """
        Charge un modèle depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            GARCHModel: Modèle chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = GARCHConfig(**data['config'])
            model = cls(config)

            model.fitted_model = data['fitted_model']
            model.data = data.get('data')
            model.is_fitted = data.get('is_fitted', False)

            logger.info(f"Modèle chargé: {filepath}")
            return model

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise

    def plot_volatility(self, figsize: Tuple[int, int] = (12, 6)) -> None:
        """
        Affiche la volatilité conditionnelle.

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
            vol = self.get_conditional_volatility()
            if vol is None:
                return

            fig, ax = plt.subplots(figsize=figsize)

            ax.plot(vol, color='blue', label='Volatilité conditionnelle')
            ax.set_title(f'Volatilité conditionnelle - {self.config.vol}')
            ax.set_xlabel('Temps')
            ax.set_ylabel('Volatilité')
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")

    def plot_residuals(self, figsize: Tuple[int, int] = (12, 6)) -> None:
        """
        Affiche les résidus standardisés.

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
            residuals = self.get_residuals()
            if residuals is None:
                return

            fig, axes = plt.subplots(2, 1, figsize=figsize)

            axes[0].plot(residuals, color='blue')
            axes[0].set_title('Résidus standardisés')
            axes[0].set_xlabel('Temps')
            axes[0].set_ylabel('Résidus')
            axes[0].axhline(y=0, color='r', linestyle='--')
            axes[0].grid(True, alpha=0.3)

            axes[1].hist(residuals, bins=30, edgecolor='black', alpha=0.7)
            axes[1].set_title('Distribution des résidus standardisés')
            axes[1].set_xlabel('Résidus')
            axes[1].set_ylabel('Fréquence')
            axes[1].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")


def create_garch_model(
    p: int = 1,
    q: int = 1,
    vol: str = 'GARCH',
    dist: str = 'normal',
    **kwargs
) -> GARCHModel:
    config = GARCHConfig(
        p=p,
        q=q,
        vol=vol,
        dist=dist,
        **kwargs
    )
    return GARCHModel(config)


__all__ = [
    'GARCHModel',
    'GARCHConfig',
    'GARCHResult',
    'create_garch_model',
]

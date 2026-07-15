
# ai/models/forecasting/prophet_model.py
"""
NEXUS AI TRADING SYSTEM - Prophet Model for Time Series Forecasting
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import pickle
import os
import json
import warnings
warnings.filterwarnings('ignore')

try:
    from prophet import Prophet
    from prophet.serialize import model_to_json, model_from_json
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ProphetConfig:
    growth: str = 'linear'
    seasonality_mode: str = 'additive'
    daily_seasonality: Union[bool, int] = False
    weekly_seasonality: Union[bool, int] = False
    yearly_seasonality: Union[bool, int] = False
    seasonality_prior_scale: float = 10.0
    holidays_prior_scale: float = 10.0
    changepoint_prior_scale: float = 0.05
    changepoint_range: float = 0.8
    changepoints: Optional[List[datetime]] = None
    n_changepoints: int = 25
    interval_width: float = 0.95
    uncertainty_samples: int = 1000
    stan_backend: Optional[str] = None
    holidays: Optional[pd.DataFrame] = None
    seasonalities: Optional[List[Dict[str, Any]]] = None
    country_holidays: Optional[str] = None

    def __post_init__(self):
        if not PROPHET_AVAILABLE:
            raise ImportError("Prophet n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'growth': self.growth,
            'seasonality_mode': self.seasonality_mode,
            'daily_seasonality': self.daily_seasonality,
            'weekly_seasonality': self.weekly_seasonality,
            'yearly_seasonality': self.yearly_seasonality,
            'seasonality_prior_scale': self.seasonality_prior_scale,
            'holidays_prior_scale': self.holidays_prior_scale,
            'changepoint_prior_scale': self.changepoint_prior_scale,
            'changepoint_range': self.changepoint_range,
            'n_changepoints': self.n_changepoints,
            'interval_width': self.interval_width,
            'uncertainty_samples': self.uncertainty_samples,
            'stan_backend': self.stan_backend,
            'country_holidays': self.country_holidays,
        }


@dataclass
class ProphetResult:
    predictions: np.ndarray
    ds: Optional[pd.DatetimeIndex] = None
    yhat_lower: Optional[np.ndarray] = None
    yhat_upper: Optional[np.ndarray] = None
    trend: Optional[np.ndarray] = None
    trend_lower: Optional[np.ndarray] = None
    trend_upper: Optional[np.ndarray] = None
    seasonality: Optional[np.ndarray] = None
    seasonality_lower: Optional[np.ndarray] = None
    seasonality_upper: Optional[np.ndarray] = None
    forecast_steps: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    components: Optional[Dict[str, np.ndarray]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'ds': self.ds.tolist() if isinstance(self.ds, pd.DatetimeIndex) else None,
            'yhat_lower': self.yhat_lower.tolist() if isinstance(self.yhat_lower, np.ndarray) else self.yhat_lower,
            'yhat_upper': self.yhat_upper.tolist() if isinstance(self.yhat_upper, np.ndarray) else self.yhat_upper,
            'trend': self.trend.tolist() if isinstance(self.trend, np.ndarray) else self.trend,
            'seasonality': self.seasonality.tolist() if isinstance(self.seasonality, np.ndarray) else self.seasonality,
            'forecast_steps': self.forecast_steps,
            'timestamp': self.timestamp.isoformat(),
        }


class ProphetModel:
    """
    Prophet Model for time series forecasting using Facebook Prophet.

    This implementation provides a wrapper around Facebook Prophet with
    additional features for financial time series forecasting:
    - Automatic changepoint detection
    - Holiday effects
    - Daily, weekly, yearly seasonality
    - Custom seasonalities
    - Multiplicative/Additive seasonality modes
    - Uncertainty intervals

    Example:
        ```python
        # Create model
        config = ProphetConfig(
            growth='linear',
            seasonality_mode='additive',
            weekly_seasonality=True,
            yearly_seasonality=True
        )
        model = ProphetModel(config)

        # Prepare data
        df = pd.DataFrame({
            'ds': dates,
            'y': prices
        })

        # Fit model
        model.fit(df)

        # Predict
        future = model.make_future_dataframe(30)
        forecast = model.predict(future)
        ```
    """

    def __init__(self, config: Optional[ProphetConfig] = None):
        if not PROPHET_AVAILABLE:
            raise ImportError("Prophet est requis. Installez avec: pip install prophet")

        self.config = config or ProphetConfig()
        self.model: Optional[Prophet] = None
        self.is_fitted = False
        self.fitted_data: Optional[pd.DataFrame] = None
        self.future_data: Optional[pd.DataFrame] = None
        self._prediction_cache: Dict[str, Any] = {}

        logger.info("ProphetModel initialisé")

    def _create_prophet_model(self) -> Prophet:
        """Crée une instance de Prophet avec la configuration"""
        model = Prophet(
            growth=self.config.growth,
            seasonality_mode=self.config.seasonality_mode,
            daily_seasonality=self.config.daily_seasonality,
            weekly_seasonality=self.config.weekly_seasonality,
            yearly_seasonality=self.config.yearly_seasonality,
            seasonality_prior_scale=self.config.seasonality_prior_scale,
            holidays_prior_scale=self.config.holidays_prior_scale,
            changepoint_prior_scale=self.config.changepoint_prior_scale,
            changepoint_range=self.config.changepoint_range,
            changepoints=self.config.changepoints,
            n_changepoints=self.config.n_changepoints,
            interval_width=self.config.interval_width,
            uncertainty_samples=self.config.uncertainty_samples,
            stan_backend=self.config.stan_backend,
            holidays=self.config.holidays,
            country_holidays=self.config.country_holidays,
        )

        # Ajouter les saisonnalités personnalisées
        if self.config.seasonalities:
            for seasonality in self.config.seasonalities:
                model.add_seasonality(
                    name=seasonality['name'],
                    period=seasonality['period'],
                    fourier_order=seasonality.get('fourier_order', 1),
                    prior_scale=seasonality.get('prior_scale', 10.0),
                    mode=seasonality.get('mode', 'additive'),
                    condition_name=seasonality.get('condition_name'),
                )

        return model

    def fit(
        self,
        data: pd.DataFrame,
        **kwargs
    ) -> 'ProphetModel':
        """
        Entraîne le modèle Prophet.

        Args:
            data: DataFrame avec colonnes 'ds' (dates) et 'y' (valeurs)
            **kwargs: Arguments supplémentaires pour Prophet.fit

        Returns:
            ProphetModel: Instance entraînée
        """
        # Validation des données
        if 'ds' not in data.columns or 'y' not in data.columns:
            raise ValueError("Les données doivent contenir les colonnes 'ds' et 'y'")

        if data['ds'].dtype != 'datetime64[ns]':
            data['ds'] = pd.to_datetime(data['ds'])

        if data['y'].dtype not in ['float64', 'float32', 'int64', 'int32']:
            data['y'] = data['y'].astype(np.float64)

        # Supprimer les valeurs NaN
        data = data.dropna(subset=['ds', 'y'])

        if len(data) < 10:
            raise ValueError("Les données doivent contenir au moins 10 points")

        # Tri par date
        data = data.sort_values('ds').reset_index(drop=True)

        # Création du modèle
        self.model = self._create_prophet_model()

        # Entraînement
        logger.info("Début de l'entraînement Prophet")
        try:
            self.model.fit(data, **kwargs)
            self.is_fitted = True
            self.fitted_data = data
            logger.info("Entraînement terminé")
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement: {e}")
            raise

        return self

    def make_future_dataframe(
        self,
        periods: int,
        freq: str = 'D',
        include_history: bool = True
    ) -> pd.DataFrame:
        """
        Crée un DataFrame pour les prévisions futures.

        Args:
            periods: Nombre de périodes à prévoir
            freq: Fréquence ('D', 'H', 'W', 'M', etc.)
            include_history: Inclure les données historiques

        Returns:
            pd.DataFrame: DataFrame futur
        """
        if not self.is_fitted or self.fitted_data is None:
            raise ValueError("Le modèle doit être entraîné avant de créer un DataFrame futur")

        last_date = self.fitted_data['ds'].max()

        if include_history:
            dates = pd.date_range(
                start=self.fitted_data['ds'].min(),
                end=last_date + timedelta(days=periods) if freq == 'D' else None,
                periods=None if freq == 'D' else None,
                freq=freq
            )
            if freq != 'D':
                dates = pd.date_range(
                    start=self.fitted_data['ds'].min(),
                    periods=len(self.fitted_data) + periods,
                    freq=freq
                )
        else:
            dates = pd.date_range(
                start=last_date + pd.Timedelta(1, unit=freq),
                periods=periods,
                freq=freq
            )

        future_df = pd.DataFrame({'ds': dates})

        self.future_data = future_df
        return future_df

    def predict(
        self,
        periods: Optional[int] = None,
        future_df: Optional[pd.DataFrame] = None,
        include_history: bool = True,
        freq: str = 'D',
        return_details: bool = False
    ) -> Union[pd.DataFrame, ProphetResult]:
        """
        Effectue une prédiction.

        Args:
            periods: Nombre de périodes à prévoir
            future_df: DataFrame futur (optionnel)
            include_history: Inclure les données historiques
            freq: Fréquence
            return_details: Retourner les détails

        Returns:
            pd.DataFrame: Prévisions
            ProphetResult: Résultat complet
        """
        if not self.is_fitted or self.model is None:
            raise ValueError("Le modèle doit être entraîné avant de prédire")

        if future_df is None:
            if periods is None:
                periods = self.config.n_changepoints or 30
            future_df = self.make_future_dataframe(periods, freq, include_history)

        # Vérifier que le DataFrame a la colonne ds
        if 'ds' not in future_df.columns:
            raise ValueError("Le DataFrame futur doit contenir la colonne 'ds'")

        if future_df['ds'].dtype != 'datetime64[ns]':
            future_df['ds'] = pd.to_datetime(future_df['ds'])

        # Prédiction
        try:
            forecast = self.model.predict(future_df)

            # Extraire les résultats
            predictions = forecast['yhat'].values
            yhat_lower = forecast['yhat_lower'].values if 'yhat_lower' in forecast.columns else None
            yhat_upper = forecast['yhat_upper'].values if 'yhat_upper' in forecast.columns else None

            # Composants
            trend = forecast['trend'].values if 'trend' in forecast.columns else None
            trend_lower = forecast['trend_lower'].values if 'trend_lower' in forecast.columns else None
            trend_upper = forecast['trend_upper'].values if 'trend_upper' in forecast.columns else None

            seasonality = None
            seasonality_lower = None
            seasonality_upper = None

            # Extraire les saisonnalités
            components = {}
            for col in forecast.columns:
                if col.startswith('seasonal') or col in ['daily', 'weekly', 'yearly']:
                    if col.endswith('_lower') or col.endswith('_upper'):
                        continue
                    components[col] = forecast[col].values

            # Sélectionner la saisonnalité principale
            if 'seasonal' in forecast.columns:
                seasonality = forecast['seasonal'].values
                if 'seasonal_lower' in forecast.columns:
                    seasonality_lower = forecast['seasonal_lower'].values
                if 'seasonal_upper' in forecast.columns:
                    seasonality_upper = forecast['seasonal_upper'].values

            # Ajuster la longueur
            history_len = len(self.fitted_data) if self.fitted_data is not None else 0
            if len(predictions) > history_len:
                pred_len = len(predictions) - history_len
            else:
                pred_len = len(predictions)

            result = ProphetResult(
                predictions=predictions,
                ds=future_df['ds'],
                yhat_lower=yhat_lower,
                yhat_upper=yhat_upper,
                trend=trend,
                trend_lower=trend_lower,
                trend_upper=trend_upper,
                seasonality=seasonality,
                seasonality_lower=seasonality_lower,
                seasonality_upper=seasonality_upper,
                forecast_steps=len(predictions) - (len(self.fitted_data) if self.fitted_data is not None else 0),
                components=components if components else None,
            )

            if return_details:
                return result
            else:
                return forecast

        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {e}")
            raise

    def predict_only_forecast(
        self,
        periods: int,
        freq: str = 'D',
        return_details: bool = False
    ) -> Union[np.ndarray, ProphetResult]:
        """
        Prédit uniquement les valeurs futures (sans historique).

        Args:
            periods: Nombre de périodes à prévoir
            freq: Fréquence
            return_details: Retourner les détails

        Returns:
            np.ndarray: Prédictions
            ProphetResult: Résultat complet
        """
        result = self.predict(
            periods=periods,
            include_history=False,
            freq=freq,
            return_details=True
        )

        if return_details:
            return result
        else:
            return result.predictions

    def get_components(self) -> Dict[str, np.ndarray]:
        """
        Retourne les composants du modèle.

        Returns:
            Dict[str, np.ndarray]: Composants du modèle
        """
        if not self.is_fitted or self.model is None:
            raise ValueError("Le modèle doit être entraîné")

        if self.fitted_data is None:
            return {}

        # Créer un DataFrame futur pour l'historique
        future_df = pd.DataFrame({
            'ds': self.fitted_data['ds']
        })

        forecast = self.model.predict(future_df)

        components = {}
        for col in forecast.columns:
            if col not in ['ds', 'yhat', 'yhat_lower', 'yhat_upper']:
                components[col] = forecast[col].values

        return components

    def get_changepoints(self) -> List[datetime]:
        """
        Retourne les points de changement détectés.

        Returns:
            List[datetime]: Points de changement
        """
        if not self.is_fitted or self.model is None:
            raise ValueError("Le modèle doit être entraîné")

        if hasattr(self.model, 'changepoints'):
            return self.model.changepoints.tolist()
        return []

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du modèle"""
        params = self.config.to_dict()
        params.update({
            'is_fitted': self.is_fitted,
            'n_observations': len(self.fitted_data) if self.fitted_data is not None else 0,
        })
        return params

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de performance"""
        metrics = {
            'is_fitted': self.is_fitted,
            'n_observations': len(self.fitted_data) if self.fitted_data is not None else 0,
            'model_type': 'Prophet',
            'growth': self.config.growth,
            'seasonality_mode': self.config.seasonality_mode,
        }

        if self.is_fitted and self.model is not None:
            try:
                # Récupérer les métriques du modèle
                if hasattr(self.model, 'fit_kwargs'):
                    metrics.update(self.model.fit_kwargs)
            except:
                pass

        return metrics

    def cross_validation(
        self,
        initial: Union[int, str] = 30,
        period: Union[int, str] = 5,
        horizon: Union[int, str] = 7,
        parallel: str = 'processes'
    ) -> pd.DataFrame:
        """
        Effectue une validation croisée sur le modèle.

        Args:
            initial: Période initiale d'entraînement
            period: Période entre les découpes
            horizon: Horizon de prédiction
            parallel: Mode de parallélisation

        Returns:
            pd.DataFrame: Résultats de la validation croisée
        """
        if not PROPHET_AVAILABLE:
            raise ImportError("Prophet n'est pas installé")

        if not self.is_fitted or self.model is None:
            raise ValueError("Le modèle doit être entraîné")

        if self.fitted_data is None:
            raise ValueError("Aucune donnée disponible")

        try:
            from prophet.diagnostics import cross_validation

            df_cv = cross_validation(
                self.model,
                initial=initial,
                period=period,
                horizon=horizon,
                parallel=parallel,
            )
            return df_cv

        except Exception as e:
            logger.error(f"Erreur lors de la validation croisée: {e}")
            raise

    def performance_metrics(
        self,
        df_cv: Optional[pd.DataFrame] = None,
        metrics: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Calcule les métriques de performance.

        Args:
            df_cv: DataFrame de validation croisée
            metrics: Liste des métriques à calculer

        Returns:
            pd.DataFrame: Métriques de performance
        """
        if not PROPHET_AVAILABLE:
            raise ImportError("Prophet n'est pas installé")

        if df_cv is None:
            df_cv = self.cross_validation()

        try:
            from prophet.diagnostics import performance_metrics

            if metrics is None:
                metrics = ['mse', 'rmse', 'mae', 'mape', 'mdape', 'smape']

            df_metrics = performance_metrics(df_cv, metrics=metrics)
            return df_metrics

        except Exception as e:
            logger.error(f"Erreur lors du calcul des métriques: {e}")
            raise

    def plot_forecast(
        self,
        periods: Optional[int] = 30,
        figsize: Tuple[int, int] = (12, 6)
    ) -> None:
        """
        Affiche la prévision.

        Args:
            periods: Nombre de périodes à prévoir
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if not self.is_fitted or self.model is None:
            logger.warning("Le modèle n'est pas entraîné")
            return

        try:
            future = self.make_future_dataframe(periods)
            forecast = self.model.predict(future)

            fig = self.model.plot(forecast, figsize=figsize)
            plt.title(f'Prévision Prophet ({periods} périodes)')
            plt.xlabel('Date')
            plt.ylabel('Valeur')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"Erreur lors du tracé de la prévision: {e}")

    def plot_components(
        self,
        periods: Optional[int] = 30,
        figsize: Tuple[int, int] = (12, 8)
    ) -> None:
        """
        Affiche les composants du modèle.

        Args:
            periods: Nombre de périodes à prévoir
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if not self.is_fitted or self.model is None:
            logger.warning("Le modèle n'est pas entraîné")
            return

        try:
            future = self.make_future_dataframe(periods)
            forecast = self.model.predict(future)

            fig = self.model.plot_components(forecast, figsize=figsize)
            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"Erreur lors du tracé des composants: {e}")

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

            if self.model is not None:
                model_json = model_to_json(self.model)
            else:
                model_json = None

            data = {
                'config': self.config.to_dict(),
                'model_json': model_json,
                'fitted_data': self.fitted_data.to_dict() if self.fitted_data is not None else None,
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
    def load(cls, filepath: str) -> 'ProphetModel':
        """
        Charge un modèle depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            ProphetModel: Modèle chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = ProphetConfig(**data['config'])
            model = cls(config)

            if data.get('model_json'):
                model.model = model_from_json(data['model_json'])

            if data.get('fitted_data'):
                model.fitted_data = pd.DataFrame.from_dict(data['fitted_data'])

            model.is_fitted = data.get('is_fitted', False)

            logger.info(f"Modèle chargé: {filepath}")
            return model

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_prophet_model(
    growth: str = 'linear',
    seasonality_mode: str = 'additive',
    weekly_seasonality: bool = True,
    yearly_seasonality: bool = True,
    changepoint_prior_scale: float = 0.05,
    interval_width: float = 0.95,
    **kwargs
) -> ProphetModel:
    """
    Factory pour créer un modèle Prophet.

    Args:
        growth: Type de croissance ('linear', 'logistic')
        seasonality_mode: Mode de saisonnalité ('additive', 'multiplicative')
        weekly_seasonality: Activer la saisonnalité hebdomadaire
        yearly_seasonality: Activer la saisonnalité annuelle
        changepoint_prior_scale: Échelle de priorité des points de changement
        interval_width: Largeur des intervalles de confiance
        **kwargs: Arguments supplémentaires

    Returns:
        ProphetModel: Instance du modèle
    """
    config = ProphetConfig(
        growth=growth,
        seasonality_mode=seasonality_mode,
        weekly_seasonality=weekly_seasonality,
        yearly_seasonality=yearly_seasonality,
        changepoint_prior_scale=changepoint_prior_scale,
        interval_width=interval_width,
        **kwargs
    )
    return ProphetModel(config)


__all__ = [
    'ProphetModel',
    'ProphetConfig',
    'ProphetResult',
    'create_prophet_model',
]

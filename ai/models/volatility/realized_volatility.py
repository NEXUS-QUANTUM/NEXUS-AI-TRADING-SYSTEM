# ai/models/volatility/realized_volatility.py
"""
NEXUS AI TRADING SYSTEM - Realized Volatility Models
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
    from scipy import stats
    from scipy.optimize import minimize
    from scipy.stats import norm, t
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class RealizedVolatilityConfig:
    method: str = 'rv'  # 'rv', 'rkv', 'rvs', 'parkinson', 'garman_klass', 'rogers_satchell', 'yang_zhang'
    window: int = 20
    min_observations: int = 5
    use_returns: bool = True
    annualize: bool = True
    trading_days: int = 252
    scaling_factor: float = 1.0
    include_volume: bool = False

    def __post_init__(self):
        valid_methods = ['rv', 'rkv', 'rvs', 'parkinson', 'garman_klass', 'rogers_satchell', 'yang_zhang']
        if self.method not in valid_methods:
            raise ValueError(f"Méthode non supportée: {self.method}")


@dataclass
class RealizedVolatilityResult:
    volatility: np.ndarray
    method: str
    window: int
    dates: Optional[np.ndarray] = None
    annualized: bool = False
    trading_days: int = 252
    timestamp: datetime = field(default_factory=datetime.now)
    additional_metrics: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'volatility': self.volatility.tolist() if isinstance(self.volatility, np.ndarray) else self.volatility,
            'method': self.method,
            'window': self.window,
            'dates': self.dates.tolist() if isinstance(self.dates, np.ndarray) else self.dates,
            'annualized': self.annualized,
            'trading_days': self.trading_days,
            'timestamp': self.timestamp.isoformat(),
            'additional_metrics': self.additional_metrics,
        }


class RealizedVolatility:
    """
    Realized Volatility estimators for financial time series.

    Supports multiple estimation methods:
    - Realized Volatility (RV)
    - Realized Kernel Volatility (RKV)
    - Realized Semivariance (RVS)
    - Parkinson (1980) - High-Low
    - Garman-Klass (1980) - OHLC
    - Rogers-Satchell (1991) - OHLC with drift
    - Yang-Zhang (2000) - OHLC with overnight effects

    Example:
        ```python
        config = RealizedVolatilityConfig(
            method='rv',
            window=20,
            annualize=True,
            trading_days=252
        )
        estimator = RealizedVolatility(config)

        # Calculate realized volatility
        vol = estimator.calculate(returns)
        vol_ohlc = estimator.calculate_ohlc(high, low, open, close)
        ```
    """

    def __init__(self, config: Optional[RealizedVolatilityConfig] = None):
        self.config = config or RealizedVolatilityConfig()
        self._cache: Dict[str, Any] = {}

        logger.info(f"RealizedVolatility initialisé avec méthode: {self.config.method}")

    def _validate_data(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        name: str = 'data'
    ) -> np.ndarray:
        """Valide et convertit les données"""
        if isinstance(data, pd.Series):
            data = data.values
        elif isinstance(data, list):
            data = np.array(data)

        if not isinstance(data, np.ndarray):
            raise TypeError(f"{name} doit être un tableau numpy, pandas Series ou liste")

        if len(data) < self.config.min_observations:
            raise ValueError(f"{name} doit contenir au moins {self.config.min_observations} observations")

        if np.any(np.isnan(data)) or np.any(np.isinf(data)):
            raise ValueError(f"{name} contient des valeurs NaN ou Inf")

        return data.astype(np.float64)

    def _validate_ohlc(
        self,
        high: np.ndarray,
        low: np.ndarray,
        open_price: Optional[np.ndarray] = None,
        close: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        """Valide les données OHLC"""
        high = self._validate_data(high, 'high')
        low = self._validate_data(low, 'low')

        if len(high) != len(low):
            raise ValueError("high et low doivent avoir la même longueur")

        if open_price is not None:
            open_price = self._validate_data(open_price, 'open_price')
            if len(open_price) != len(high):
                raise ValueError("open_price doit avoir la même longueur que high/low")

        if close is not None:
            close = self._validate_data(close, 'close')
            if len(close) != len(high):
                raise ValueError("close doit avoir la même longueur que high/low")

        return high, low, open_price, close

    def _annualize(self, vol: np.ndarray) -> np.ndarray:
        """Annualise la volatilité"""
        if self.config.annualize:
            return vol * np.sqrt(self.config.trading_days)
        return vol

    def _calculate_rv(self, returns: np.ndarray) -> np.ndarray:
        """
        Realized Volatility (RV)
        Somme des carrés des rendements sur la fenêtre
        """
        n = len(returns)
        if n < self.config.window:
            raise ValueError(f"Pas assez de données. Besoin de {self.config.window} observations")

        vol = np.zeros(n)
        for i in range(self.config.window, n + 1):
            vol[i - 1] = np.sqrt(np.sum(returns[i - self.config.window:i] ** 2))

        return vol

    def _calculate_rkv(self, returns: np.ndarray) -> np.ndarray:
        """
        Realized Kernel Volatility (RKV)
        Utilise un noyau pour corriger le bruit de microstructure
        """
        n = len(returns)
        if n < self.config.window:
            raise ValueError(f"Pas assez de données. Besoin de {self.config.window} observations")

        vol = np.zeros(n)
        h = max(1, int(np.sqrt(self.config.window)))

        for i in range(self.config.window, n + 1):
            window_returns = returns[i - self.config.window:i]
            rv = np.sum(window_returns ** 2)

            # Kernel de Barndorff-Nielsen
            kernel_sum = 0
            for j in range(1, h):
                gamma = np.sum(window_returns[:-j] * window_returns[j:]) / (self.config.window - j)
                kernel = (1 - j / h)
                kernel_sum += kernel * gamma

            rkv = rv + 2 * kernel_sum
            vol[i - 1] = np.sqrt(max(rkv, 0))

        return vol

    def _calculate_rvs(self, returns: np.ndarray) -> np.ndarray:
        """
        Realized Semivariance (RVS)
        Volatilité des rendements négatifs seulement
        """
        n = len(returns)
        if n < self.config.window:
            raise ValueError(f"Pas assez de données. Besoin de {self.config.window} observations")

        vol = np.zeros(n)
        for i in range(self.config.window, n + 1):
            negative_returns = returns[i - self.config.window:i]
            negative_returns = negative_returns[negative_returns < 0]
            if len(negative_returns) > 0:
                vol[i - 1] = np.sqrt(np.sum(negative_returns ** 2) / self.config.window)
            else:
                vol[i - 1] = 0

        return vol

    def _calculate_parkinson(self, high: np.ndarray, low: np.ndarray) -> np.ndarray:
        """
        Parkinson (1980) estimator
        Utilise les prix haut et bas
        """
        n = len(high)
        if n < self.config.window:
            raise ValueError(f"Pas assez de données. Besoin de {self.config.window} observations")

        vol = np.zeros(n)
        for i in range(self.config.window, n + 1):
            log_range = np.log(high[i - self.config.window:i] / low[i - self.config.window:i])
            vol[i - 1] = np.sqrt(np.sum(log_range ** 2) / (self.config.window * 4 * np.log(2)))

        return vol

    def _calculate_garman_klass(
        self,
        high: np.ndarray,
        low: np.ndarray,
        open_price: np.ndarray,
        close: np.ndarray
    ) -> np.ndarray:
        """
        Garman-Klass (1980) estimator
        Utilise OHLC complet
        """
        n = len(high)
        if n < self.config.window:
            raise ValueError(f"Pas assez de données. Besoin de {self.config.window} observations")

        vol = np.zeros(n)

        # Constante de Garman-Klass
        c = 2 * np.log(2) - 1

        for i in range(self.config.window, n + 1):
            log_high_low = np.log(high[i - self.config.window:i] / low[i - self.config.window:i])
            log_close_open = np.log(close[i - self.config.window:i] / open_price[i - self.config.window:i])

            gk = (0.5 * np.sum(log_high_low ** 2) - c * np.sum(log_close_open ** 2)) / self.config.window
            vol[i - 1] = np.sqrt(max(gk, 0))

        return vol

    def _calculate_rogers_satchell(
        self,
        high: np.ndarray,
        low: np.ndarray,
        open_price: np.ndarray,
        close: np.ndarray
    ) -> np.ndarray:
        """
        Rogers-Satchell (1991) estimator
        OHLC avec correction du drift
        """
        n = len(high)
        if n < self.config.window:
            raise ValueError(f"Pas assez de données. Besoin de {self.config.window} observations")

        vol = np.zeros(n)

        for i in range(self.config.window, n + 1):
            log_high_open = np.log(high[i - self.config.window:i] / open_price[i - self.config.window:i])
            log_low_open = np.log(low[i - self.config.window:i] / open_price[i - self.config.window:i])
            log_close_high = np.log(close[i - self.config.window:i] / high[i - self.config.window:i])
            log_close_low = np.log(close[i - self.config.window:i] / low[i - self.config.window:i])

            rs = (log_high_open * log_high_open +
                  log_low_open * log_low_open +
                  log_close_high * log_close_high +
                  log_close_low * log_close_low) / self.config.window

            vol[i - 1] = np.sqrt(max(rs, 0))

        return vol

    def _calculate_yang_zhang(
        self,
        high: np.ndarray,
        low: np.ndarray,
        open_price: np.ndarray,
        close: np.ndarray
    ) -> np.ndarray:
        """
        Yang-Zhang (2000) estimator
        OHLC avec effets overnight
        """
        n = len(high)
        if n < self.config.window:
            raise ValueError(f"Pas assez de données. Besoin de {self.config.window} observations")

        vol = np.zeros(n)

        # Facteurs de pondération Yang-Zhang
        k = 0.34 / (1.34 + (self.config.window + 1) / (self.config.window - 1))
        alpha = 0.17
        beta = 0.83

        for i in range(self.config.window, n + 1):
            log_high_low = np.log(high[i - self.config.window:i] / low[i - self.config.window:i])
            log_close_open = np.log(close[i - self.config.window:i] / open_price[i - self.config.window:i])

            # Composantes
            open_close_var = np.sum(log_close_open ** 2) / self.config.window
            high_low_var = np.sum(log_high_low ** 2) / (self.config.window * 4 * np.log(2))

            # Volatilité overnight
            overnight_var = 0
            if i > self.config.window + 1:
                log_open_prev_close = np.log(open_price[i - self.config.window:i] /
                                             close[i - self.config.window - 1:i - 1])
                overnight_var = np.sum(log_open_prev_close ** 2) / (self.config.window - 1)

            yz = open_close_var + k * high_low_var + (1 - k) * overnight_var
            vol[i - 1] = np.sqrt(max(yz, 0))

        return vol

    def calculate(self, data: Union[np.ndarray, pd.Series, List[float]]) -> np.ndarray:
        """
        Calcule la volatilité réalisée.

        Args:
            data: Données de rendements

        Returns:
            np.ndarray: Volatilité réalisée
        """
        returns = self._validate_data(data, 'returns')
        returns = returns * self.config.scaling_factor

        if self.config.method == 'rv':
            vol = self._calculate_rv(returns)
        elif self.config.method == 'rkv':
            vol = self._calculate_rkv(returns)
        elif self.config.method == 'rvs':
            vol = self._calculate_rvs(returns)
        else:
            raise ValueError(f"Méthode non supportée pour les rendements: {self.config.method}")

        vol = self._annualize(vol)
        return vol

    def calculate_ohlc(
        self,
        high: Union[np.ndarray, pd.Series, List[float]],
        low: Union[np.ndarray, pd.Series, List[float]],
        open_price: Optional[Union[np.ndarray, pd.Series, List[float]]] = None,
        close: Optional[Union[np.ndarray, pd.Series, List[float]]] = None
    ) -> np.ndarray:
        """
        Calcule la volatilité réalisée à partir des prix OHLC.

        Args:
            high: Prix haut
            low: Prix bas
            open_price: Prix d'ouverture (optionnel)
            close: Prix de fermeture (optionnel)

        Returns:
            np.ndarray: Volatilité réalisée
        """
        high, low, open_price, close = self._validate_ohlc(high, low, open_price, close)

        if self.config.method == 'parkinson':
            vol = self._calculate_parkinson(high, low)
        elif self.config.method == 'garman_klass':
            if open_price is None or close is None:
                raise ValueError("open_price et close sont requis pour Garman-Klass")
            vol = self._calculate_garman_klass(high, low, open_price, close)
        elif self.config.method == 'rogers_satchell':
            if open_price is None or close is None:
                raise ValueError("open_price et close sont requis pour Rogers-Satchell")
            vol = self._calculate_rogers_satchell(high, low, open_price, close)
        elif self.config.method == 'yang_zhang':
            if open_price is None or close is None:
                raise ValueError("open_price et close sont requis pour Yang-Zhang")
            vol = self._calculate_yang_zhang(high, low, open_price, close)
        else:
            raise ValueError(f"Méthode non supportée pour OHLC: {self.config.method}")

        vol = self._annualize(vol)
        return vol

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres"""
        return {
            'method': self.config.method,
            'window': self.config.window,
            'min_observations': self.config.min_observations,
            'annualize': self.config.annualize,
            'trading_days': self.config.trading_days,
            'scaling_factor': self.config.scaling_factor,
        }

    def clear_cache(self):
        """Vide le cache"""
        self._cache.clear()

    def plot_volatility(
        self,
        vol: np.ndarray,
        dates: Optional[np.ndarray] = None,
        figsize: Tuple[int, int] = (12, 6)
    ) -> None:
        """
        Affiche la volatilité réalisée.

        Args:
            vol: Volatilité calculée
            dates: Dates pour l'axe x (optionnel)
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        try:
            fig, ax = plt.subplots(figsize=figsize)

            if dates is not None:
                ax.plot(dates, vol, color='blue', label=f'Volatilité {self.config.method}')
            else:
                ax.plot(vol, color='blue', label=f'Volatilité {self.config.method}')

            ax.set_title(f'Volatilité réalisée - {self.config.method.upper()}')
            ax.set_xlabel('Temps')
            ax.set_ylabel('Volatilité')
            if self.config.annualize:
                ax.set_ylabel('Volatilité annualisée')
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except Exception as e:
            logger.error(f"Erreur lors du tracé: {e}")


def create_realized_volatility(
    method: str = 'rv',
    window: int = 20,
    annualize: bool = True,
    trading_days: int = 252,
    **kwargs
) -> RealizedVolatility:
    config = RealizedVolatilityConfig(
        method=method,
        window=window,
        annualize=annualize,
        trading_days=trading_days,
        **kwargs
    )
    return RealizedVolatility(config)


__all__ = [
    'RealizedVolatility',
    'RealizedVolatilityConfig',
    'RealizedVolatilityResult',
    'create_realized_volatility',
]

# ai/simulation/market_simulator.py
"""
NEXUS AI TRADING SYSTEM - Market Simulator
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MarketSimulatorConfig:
    """Configuration pour Market Simulator"""
    symbols: List[str] = field(default_factory=lambda: ["BTC-USD", "ETH-USD", "SOL-USD"])
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    frequency: str = "1min"  # '1min', '5min', '15min', '1h', '1d'
    volatility: float = 0.02
    drift: float = 0.0001
    correlation: float = 0.5
    seed: Optional[int] = 42
    volume_mean: float = 1000.0
    volume_std: float = 200.0
    price_base: Dict[str, float] = field(default_factory=dict)
    use_geometric_brownian: bool = True
    add_spikes: bool = True
    spike_probability: float = 0.01
    spike_magnitude: float = 0.05

    def __post_init__(self):
        if not self.price_base:
            self.price_base = {
                "BTC-USD": 50000.0,
                "ETH-USD": 3000.0,
                "SOL-USD": 100.0,
            }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbols': self.symbols,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'frequency': self.frequency,
            'volatility': self.volatility,
            'drift': self.drift,
            'correlation': self.correlation,
            'seed': self.seed,
            'volume_mean': self.volume_mean,
            'volume_std': self.volume_std,
            'price_base': self.price_base,
            'use_geometric_brownian': self.use_geometric_brownian,
            'add_spikes': self.add_spikes,
            'spike_probability': self.spike_probability,
            'spike_magnitude': self.spike_magnitude,
        }


@dataclass
class MarketData:
    """Données de marché"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
        }


class MarketSimulator:
    """
    Simulateur de marché pour l'IA de trading.

    Features:
    - Multi-symbol simulation
    - Correlated price movements
    - Volume simulation
    - Price spikes
    - Technical indicator generation
    - Historical data export

    Example:
        ```python
        config = MarketSimulatorConfig(
            symbols=['BTC-USD', 'ETH-USD'],
            start_date='2024-01-01',
            end_date='2024-12-31',
            frequency='1h'
        )
        simulator = MarketSimulator(config)

        # Generate data
        data = simulator.generate()

        # Get data for specific symbol
        btc_data = simulator.get_data('BTC-USD')
        ```
    """

    def __init__(self, config: Optional[MarketSimulatorConfig] = None):
        self.config = config or MarketSimulatorConfig()

        if self.config.seed is not None:
            np.random.seed(self.config.seed)

        self.data: Dict[str, pd.DataFrame] = {}
        self.metadata: Dict[str, Any] = {}

        logger.info(f"MarketSimulator initialisé")

    def generate(self) -> Dict[str, pd.DataFrame]:
        """
        Génère les données de marché.

        Returns:
            Dict[str, pd.DataFrame]: Données générées
        """
        # Création de l'index temporel
        start = pd.Timestamp(self.config.start_date)
        end = pd.Timestamp(self.config.end_date)
        freq_map = {
            '1min': 'T', '5min': '5T', '15min': '15T',
            '1h': 'H', '1d': 'D'
        }
        freq = freq_map.get(self.config.frequency, 'T')

        date_range = pd.date_range(start=start, end=end, freq=freq)

        # Matrice de corrélation
        n_symbols = len(self.config.symbols)
        corr_matrix = np.ones((n_symbols, n_symbols)) * self.config.correlation
        np.fill_diagonal(corr_matrix, 1.0)

        # Cholesky decomposition
        L = np.linalg.cholesky(corr_matrix)

        # Génération pour chaque symbole
        for i, symbol in enumerate(self.config.symbols):
            base_price = self.config.price_base.get(symbol, 1000.0)

            # Génération des rendements
            n_steps = len(date_range)
            returns = np.zeros(n_steps)

            # Bruit corrélé
            noise = np.random.normal(0, 1, (n_steps, n_symbols))

            for t in range(n_steps):
                correlated_noise = L @ noise[t]
                returns[t] = correlated_noise[i]

            # GBM ou simple random walk
            if self.config.use_geometric_brownian:
                prices = base_price * np.exp(
                    np.cumsum(
                        self.config.drift - 0.5 * self.config.volatility**2 +
                        self.config.volatility * returns * np.sqrt(1/252)
                    )
                )
            else:
                prices = base_price * (1 + returns * self.config.volatility)

            # Ajout de spikes
            if self.config.add_spikes:
                for t in range(1, n_steps):
                    if np.random.random() < self.config.spike_probability:
                        spike = np.random.choice([-1, 1]) * self.config.spike_magnitude
                        prices[t] = prices[t] * (1 + spike)
                        prices[t] = max(prices[t], 0.01)

            # OHL
            high = prices * (1 + np.abs(np.random.normal(0, 0.005, n_steps)))
            low = prices * (1 - np.abs(np.random.normal(0, 0.005, n_steps)))
            open_price = np.roll(prices, 1)
            open_price[0] = prices[0]

            # Volume
            volume = np.abs(
                np.random.normal(self.config.volume_mean, self.config.volume_std, n_steps)
            )
            volume = np.maximum(volume, 1)

            # Création du DataFrame
            df = pd.DataFrame({
                'timestamp': date_range,
                'open': open_price,
                'high': high,
                'low': low,
                'close': prices,
                'volume': volume,
            })

            # Calcul des indicateurs techniques
            df = self._add_technical_indicators(df)

            self.data[symbol] = df

            self.metadata[symbol] = {
                'base_price': base_price,
                'mean_price': df['close'].mean(),
                'std_price': df['close'].std(),
                'max_price': df['close'].max(),
                'min_price': df['close'].min(),
                'n_steps': len(df),
            }

        logger.info(f"Données générées: {len(date_range)} pas, {len(self.config.symbols)} symboles")

        return self.data

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ajoute des indicateurs techniques.

        Args:
            df: DataFrame avec les prix

        Returns:
            pd.DataFrame: DataFrame avec indicateurs
        """
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values

        # Moving averages
        for window in [5, 10, 20, 50]:
            df[f'ma_{window}'] = pd.Series(close).rolling(window).mean().values

        # RSI
        df['rsi'] = self._calculate_rsi(close, 14)

        # MACD
        df['macd'], df['macd_signal'] = self._calculate_macd(close)

        # Bollinger Bands
        df['bb_middle'], df['bb_upper'], df['bb_lower'] = self._calculate_bollinger_bands(close)

        # ATR
        df['atr'] = self._calculate_atr(high, low, close, 14)

        # Volume indicators
        df['volume_ma'] = pd.Series(volume).rolling(20).mean().values
        df['volume_ratio'] = volume / (df['volume_ma'] + 1e-6)

        return df

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calcule le RSI"""
        rsi = np.zeros(len(prices))
        rsi[:period] = 50

        for i in range(period, len(prices)):
            gains = 0
            losses = 0
            for j in range(i - period + 1, i + 1):
                diff = prices[j] - prices[j-1]
                if diff > 0:
                    gains += diff
                else:
                    losses += abs(diff)

            avg_gain = gains / period
            avg_loss = losses / period

            if avg_loss == 0:
                rsi[i] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(self, prices: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Calcule le MACD"""
        def ema(data, span):
            return pd.Series(data).ewm(span=span).mean().values

        ema12 = ema(prices, 12)
        ema26 = ema(prices, 26)
        macd = ema12 - ema26
        signal = ema(macd, 9)

        return macd, signal

    def _calculate_bollinger_bands(self, prices: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calcule les Bollinger Bands"""
        ma20 = pd.Series(prices).rolling(20).mean().values
        std20 = pd.Series(prices).rolling(20).std().values

        upper = ma20 + 2 * std20
        lower = ma20 - 2 * std20

        return ma20, upper, lower

    def _calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Calcule l'ATR"""
        tr = np.zeros(len(high))
        for i in range(1, len(high)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )

        return pd.Series(tr).rolling(period).mean().values

    def get_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Récupère les données d'un symbole.

        Args:
            symbol: Symbole

        Returns:
            Optional[pd.DataFrame]: Données du symbole
        """
        return self.data.get(symbol)

    def get_all_data(self) -> Dict[str, pd.DataFrame]:
        """
        Récupère toutes les données.

        Returns:
            Dict[str, pd.DataFrame]: Toutes les données
        """
        return self.data

    def get_market_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère un snapshot du marché.

        Returns:
            Dict[str, Dict[str, Any]]: Snapshot du marché
        """
        snapshot = {}

        for symbol, df in self.data.items():
            last = df.iloc[-1]
            snapshot[symbol] = {
                'price': last['close'],
                'change': (last['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close'] if len(df) > 1 else 0,
                'volume': last['volume'],
                'high': last['high'],
                'low': last['low'],
                'timestamp': last['timestamp'],
            }

        return snapshot

    def plot(self, symbols: Optional[List[str]] = None, figsize: Tuple[int, int] = (12, 8)):
        """
        Affiche les données de marché.

        Args:
            symbols: Liste des symboles (optionnel)
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if symbols is None:
            symbols = self.config.symbols

        fig, axes = plt.subplots(len(symbols), 1, figsize=figsize)

        if len(symbols) == 1:
            axes = [axes]

        for i, symbol in enumerate(symbols):
            df = self.data.get(symbol)
            if df is None:
                continue

            ax = axes[i]
            ax.plot(df['timestamp'], df['close'], label='Close')
            ax.fill_between(
                df['timestamp'],
                df['bb_lower'],
                df['bb_upper'],
                alpha=0.2,
                label='Bollinger Bands'
            )
            ax.set_title(symbol)
            ax.set_ylabel('Price')
            ax.legend()
            ax.grid(True, alpha=0.3)

        plt.xlabel('Time')
        plt.tight_layout()
        plt.show()

    def to_csv(self, directory: str = "./market_data"):
        """
        Exporte les données en CSV.

        Args:
            directory: Répertoire de destination
        """
        import os
        os.makedirs(directory, exist_ok=True)

        for symbol, df in self.data.items():
            filepath = os.path.join(directory, f"{symbol}.csv")
            df.to_csv(filepath, index=False)
            logger.info(f"Données exportées: {filepath}")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde les données.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardé
        """
        try:
            import pickle
            import os

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'data': {k: v.to_dict(orient='list') for k, v in self.data.items()},
                'metadata': self.metadata,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"MarketSimulator sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'MarketSimulator':
        """
        Charge un simulateur de marché.

        Args:
            filepath: Chemin du fichier

        Returns:
            MarketSimulator: Simulateur chargé
        """
        try:
            import pickle

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = MarketSimulatorConfig(**data['config'])
            simulator = cls(config)

            # Restaurer les données
            for symbol, df_data in data.get('data', {}).items():
                simulator.data[symbol] = pd.DataFrame(df_data)

            simulator.metadata = data.get('metadata', {})

            logger.info(f"MarketSimulator chargé: {filepath}")
            return simulator

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_market_simulator(
    symbols: List[str] = None,
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    frequency: str = "1h",
    **kwargs
) -> MarketSimulator:
    """
    Factory pour créer un simulateur de marché.

    Args:
        symbols: Liste des symboles
        start_date: Date de début
        end_date: Date de fin
        frequency: Fréquence
        **kwargs: Arguments supplémentaires

    Returns:
        MarketSimulator: Simulateur de marché
    """
    if symbols is None:
        symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]

    config = MarketSimulatorConfig(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        **kwargs
    )
    return MarketSimulator(config)


__all__ = [
    'MarketSimulator',
    'MarketSimulatorConfig',
    'MarketData',
    'create_market_simulator',
]

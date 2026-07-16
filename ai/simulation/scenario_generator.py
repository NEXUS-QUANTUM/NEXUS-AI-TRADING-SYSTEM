# ai/simulation/scenario_generator.py
"""
NEXUS AI TRADING SYSTEM - Scenario Generator
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random
import json
import warnings
warnings.filterwarnings('ignore')

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ScenarioConfig:
    """Configuration pour Scenario Generator"""
    name: str = "default_scenario"
    description: str = ""
    market_condition: str = "normal"  # 'normal', 'bull', 'bear', 'volatile', 'crash'
    volatility: float = 0.02
    trend: float = 0.0001  # drift
    shock_probability: float = 0.01
    shock_magnitude: float = 0.1
    correlation: float = 0.5
    duration_days: int = 30
    frequency: str = "1h"
    symbols: List[str] = field(default_factory=lambda: ["BTC-USD", "ETH-USD", "SOL-USD"])
    price_base: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if not self.price_base:
            self.price_base = {
                "BTC-USD": 50000.0,
                "ETH-USD": 3000.0,
                "SOL-USD": 100.0,
            }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'market_condition': self.market_condition,
            'volatility': self.volatility,
            'trend': self.trend,
            'shock_probability': self.shock_probability,
            'shock_magnitude': self.shock_magnitude,
            'correlation': self.correlation,
            'duration_days': self.duration_days,
            'frequency': self.frequency,
            'symbols': self.symbols,
            'price_base': self.price_base,
        }


@dataclass
class ScenarioResult:
    """Résultat d'un scénario"""
    name: str
    description: str
    data: Dict[str, pd.DataFrame]
    metrics: Dict[str, Dict[str, float]]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'metrics': self.metrics,
            'timestamp': self.timestamp.isoformat(),
        }


class ScenarioGenerator:
    """
    Générateur de scénarios pour l'IA de trading.

    Features:
    - Multiples conditions de marché
    - Chocs de marché
    - Corrélation entre actifs
    - Scénarios personnalisables
    - Export/Import JSON

    Example:
        ```python
        config = ScenarioConfig(
            name='bear_market',
            market_condition='bear',
            volatility=0.03,
            trend=-0.0002,
            duration_days=30
        )
        generator = ScenarioGenerator(config)

        # Generate scenario
        result = generator.generate()
        data = result.data
        ```
    """

    def __init__(self, config: Optional[ScenarioConfig] = None):
        self.config = config or ScenarioConfig()
        self.scenarios: Dict[str, ScenarioResult] = {}

        logger.info(f"ScenarioGenerator initialisé")

    def generate(self) -> ScenarioResult:
        """
        Génère un scénario.

        Returns:
            ScenarioResult: Résultat du scénario
        """
        # Création de l'index temporel
        start_date = datetime.now()
        end_date = start_date + timedelta(days=self.config.duration_days)
        freq_map = {
            '1min': 'T', '5min': '5T', '15min': '15T',
            '1h': 'H', '4h': '4H', '1d': 'D'
        }
        freq = freq_map.get(self.config.frequency, 'H')

        date_range = pd.date_range(start=start_date, end=end_date, freq=freq)

        # Ajustement des paramètres selon la condition de marché
        vol, trend, shock_prob, shock_mag = self._get_market_parameters()

        # Génération des données
        data = {}
        metrics = {}

        for symbol in self.config.symbols:
            base_price = self.config.price_base.get(symbol, 1000.0)
            symbol_data = self._generate_symbol_data(
                symbol, date_range, base_price, vol, trend, shock_prob, shock_mag
            )
            data[symbol] = symbol_data
            metrics[symbol] = self._calculate_metrics(symbol_data)

        result = ScenarioResult(
            name=self.config.name,
            description=self.config.description,
            data=data,
            metrics=metrics,
        )

        self.scenarios[self.config.name] = result

        logger.info(f"Scénario généré: {self.config.name}")

        return result

    def _get_market_parameters(self) -> Tuple[float, float, float, float]:
        """
        Retourne les paramètres de marché.

        Returns:
            Tuple[float, float, float, float]: (volatility, trend, shock_prob, shock_mag)
        """
        condition = self.config.market_condition

        params = {
            'normal': (0.02, 0.0001, 0.01, 0.1),
            'bull': (0.015, 0.0005, 0.005, 0.05),
            'bear': (0.025, -0.0005, 0.015, 0.15),
            'volatile': (0.04, 0.0001, 0.02, 0.2),
            'crash': (0.05, -0.001, 0.05, 0.3),
        }

        return params.get(condition, params['normal'])

    def _generate_symbol_data(
        self,
        symbol: str,
        date_range: pd.DatetimeIndex,
        base_price: float,
        volatility: float,
        trend: float,
        shock_prob: float,
        shock_mag: float
    ) -> pd.DataFrame:
        """
        Génère les données pour un symbole.

        Args:
            symbol: Symbole
            date_range: Index temporel
            base_price: Prix de base
            volatility: Volatilité
            trend: Tendance
            shock_prob: Probabilité de choc
            shock_mag: Magnitude du choc

        Returns:
            pd.DataFrame: Données générées
        """
        n = len(date_range)

        # Rendements
        returns = np.random.normal(trend, volatility, n)

        # Chocs
        shocks = np.random.random(n) < shock_prob
        shock_directions = np.random.choice([-1, 1], n)
        shock_magnitudes = np.random.exponential(shock_mag, n)
        returns[shocks] += shock_directions[shocks] * shock_magnitudes[shocks]

        # Prix
        prices = base_price * np.cumprod(1 + returns)

        # OHL
        high = prices * (1 + np.abs(np.random.normal(0, volatility * 0.5, n)))
        low = prices * (1 - np.abs(np.random.normal(0, volatility * 0.5, n)))
        open_price = np.roll(prices, 1)
        open_price[0] = prices[0]

        # Volume
        volume = np.abs(np.random.normal(1000, 200, n))
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

        # Ajout des indicateurs
        df = self._add_indicators(df)

        return df

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ajoute des indicateurs techniques.

        Args:
            df: DataFrame

        Returns:
            pd.DataFrame: DataFrame avec indicateurs
        """
        close = df['close'].values

        # Moving averages
        for window in [5, 10, 20, 50]:
            df[f'ma_{window}'] = pd.Series(close).rolling(window).mean().values

        # RSI
        df['rsi'] = self._calculate_rsi(close)

        # MACD
        df['macd'], df['macd_signal'] = self._calculate_macd(close)

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

    def _calculate_metrics(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calcule les métriques d'un DataFrame.

        Args:
            df: DataFrame

        Returns:
            Dict[str, float]: Métriques
        """
        close = df['close'].values
        returns = np.diff(close) / close[:-1]

        metrics = {
            'start_price': close[0],
            'end_price': close[-1],
            'total_return': (close[-1] - close[0]) / close[0],
            'volatility': np.std(returns) * np.sqrt(252),
            'max_price': np.max(close),
            'min_price': np.min(close),
            'sharpe_ratio': np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0,
            'max_drawdown': self._calculate_max_drawdown(close),
        }

        return metrics

    def _calculate_max_drawdown(self, prices: np.ndarray) -> float:
        """Calcule le drawdown maximum"""
        peak = np.maximum.accumulate(prices)
        drawdown = (peak - prices) / peak
        return np.max(drawdown)

    def create_scenario_from_json(self, filepath: str) -> ScenarioResult:
        """
        Crée un scénario à partir d'un fichier JSON.

        Args:
            filepath: Chemin du fichier JSON

        Returns:
            ScenarioResult: Résultat du scénario
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            config = ScenarioConfig(**data['config'])
            generator = ScenarioGenerator(config)
            result = generator.generate()

            logger.info(f"Scénario chargé depuis JSON: {filepath}")
            return result

        except Exception as e:
            logger.error(f"Erreur de chargement JSON: {e}")
            raise

    def export_to_json(self, result: ScenarioResult, filepath: str) -> bool:
        """
        Exporte un scénario en JSON.

        Args:
            result: Résultat du scénario
            filepath: Chemin du fichier

        Returns:
            bool: True si exporté
        """
        try:
            data = {
                'config': self.config.to_dict(),
                'result': result.to_dict(),
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Scénario exporté: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur d'export: {e}")
            return False

    def plot(self, result: ScenarioResult, symbols: Optional[List[str]] = None):
        """
        Affiche un scénario.

        Args:
            result: Résultat du scénario
            symbols: Liste des symboles (optionnel)
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if symbols is None:
            symbols = list(result.data.keys())

        fig, axes = plt.subplots(len(symbols), 2, figsize=(15, 5 * len(symbols)))

        if len(symbols) == 1:
            axes = [axes]

        for i, symbol in enumerate(symbols):
            df = result.data.get(symbol)
            if df is None:
                continue

            # Prix
            ax1 = axes[i, 0]
            ax1.plot(df['timestamp'], df['close'], label='Close', color='blue')
            ax1.fill_between(
                df['timestamp'],
                df['close'].min(),
                df['close'].max(),
                alpha=0.1,
                color='blue'
            )
            ax1.set_title(f'{symbol} - Price')
            ax1.set_ylabel('Price')
            ax1.grid(True, alpha=0.3)

            # Indicateurs
            ax2 = axes[i, 1]
            ax2.plot(df['timestamp'], df['rsi'], label='RSI', color='purple')
            ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5)
            ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5)
            ax2.set_title(f'{symbol} - Indicators')
            ax2.set_ylabel('RSI')
            ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()


def create_scenario_generator(
    name: str = "default_scenario",
    market_condition: str = "normal",
    duration_days: int = 30,
    **kwargs
) -> ScenarioGenerator:
    """
    Factory pour créer un générateur de scénarios.

    Args:
        name: Nom du scénario
        market_condition: Condition de marché
        duration_days: Durée en jours
        **kwargs: Arguments supplémentaires

    Returns:
        ScenarioGenerator: Générateur de scénarios
    """
    config = ScenarioConfig(
        name=name,
        market_condition=market_condition,
        duration_days=duration_days,
        **kwargs
    )
    return ScenarioGenerator(config)


__all__ = [
    'ScenarioGenerator',
    'ScenarioConfig',
    'ScenarioResult',
    'create_scenario_generator',
]

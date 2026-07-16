# ai/strategies/arbitrage/statistical_arbitrage.py
"""
NEXUS AI TRADING SYSTEM - Statistical Arbitrage Strategy
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
    from scipy import stats
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class CointegrationResult:
    """Résultat de cointégration"""
    pair: Tuple[str, str]
    hedge_ratio: float
    spread: np.ndarray
    z_score: np.ndarray
    p_value: float
    is_cointegrated: bool
    half_life: float
    stationarity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pair': self.pair,
            'hedge_ratio': self.hedge_ratio,
            'p_value': self.p_value,
            'is_cointegrated': self.is_cointegrated,
            'half_life': self.half_life,
            'stationarity': self.stationarity,
        }


@dataclass
class StatisticalArbitrageConfig:
    """Configuration pour Statistical Arbitrage"""
    symbols: List[str] = field(default_factory=lambda: ['BTC-USD', 'ETH-USD', 'SOL-USD'])
    lookback_window: int = 100
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    stop_loss_zscore: float = 3.5
    min_hedge_ratio: float = 0.1
    max_hedge_ratio: float = 10.0
    p_value_threshold: float = 0.05
    half_life_threshold: float = 100
    max_position_size: float = 10000.0
    min_position_size: float = 100.0
    fee_rate: float = 0.001
    use_pca: bool = False
    n_components: int = 3
    update_frequency: int = 10
    max_pairs: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbols': self.symbols,
            'lookback_window': self.lookback_window,
            'entry_zscore': self.entry_zscore,
            'exit_zscore': self.exit_zscore,
            'stop_loss_zscore': self.stop_loss_zscore,
            'min_hedge_ratio': self.min_hedge_ratio,
            'max_hedge_ratio': self.max_hedge_ratio,
            'p_value_threshold': self.p_value_threshold,
            'half_life_threshold': self.half_life_threshold,
            'max_position_size': self.max_position_size,
            'min_position_size': self.min_position_size,
            'fee_rate': self.fee_rate,
            'use_pca': self.use_pca,
            'n_components': self.n_components,
            'update_frequency': self.update_frequency,
            'max_pairs': self.max_pairs,
        }


class StatisticalArbitrage:
    """
    Stratégie d'arbitrage statistique (Pairs Trading).

    Features:
    - Cointegration testing
    - Pair selection
    - Spread calculation
    - Entry/Exit signals
    - Risk management

    Example:
        ```python
        config = StatisticalArbitrageConfig(
            symbols=['BTC-USD', 'ETH-USD'],
            lookback_window=100,
            entry_zscore=2.0
        )
        strategy = StatisticalArbitrage(config)

        # Update with data
        strategy.update(price_data)

        # Get signals
        signals = strategy.get_signals()
        ```
    """

    def __init__(self, config: Optional[StatisticalArbitrageConfig] = None):
        self.config = config or StatisticalArbitrageConfig()
        self.data: Dict[str, pd.Series] = {}
        self.cointegrated_pairs: List[CointegrationResult] = []
        self.open_positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self._scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self._pca = PCA(n_components=self.config.n_components) if SKLEARN_AVAILABLE else None

        logger.info(f"StatisticalArbitrage initialisé")

    def update(self, data: Dict[str, pd.Series]) -> None:
        """
        Met à jour les données de prix.

        Args:
            data: Dictionnaire des séries de prix
        """
        self.data = data

        # Mise à jour des paires cointégrées
        if len(data) >= 2:
            self._update_cointegrated_pairs()

        # Mise à jour des positions
        self._update_positions()

        logger.info(f"Données mises à jour: {len(data)} symboles")

    def _update_cointegrated_pairs(self) -> None:
        """Met à jour les paires cointégrées"""
        if not SCIPY_AVAILABLE:
            logger.warning("SciPy non disponible")
            return

        symbols = list(self.data.keys())
        pairs = []

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                pair = self._test_cointegration(symbols[i], symbols[j])
                if pair and pair.is_cointegrated:
                    pairs.append(pair)

        # Trier par p-value et half-life
        pairs.sort(key=lambda x: (x.p_value, x.half_life))
        self.cointegrated_pairs = pairs[:self.config.max_pairs]

        if self.cointegrated_pairs:
            logger.info(f"{len(self.cointegrated_pairs)} paires cointégrées trouvées")

    def _test_cointegration(self, symbol1: str, symbol2: str) -> Optional[CointegrationResult]:
        """
        Teste la cointégration entre deux symboles.

        Args:
            symbol1: Premier symbole
            symbol2: Deuxième symbole

        Returns:
            Optional[CointegrationResult]: Résultat du test
        """
        if not SCIPY_AVAILABLE:
            return None

        if symbol1 not in self.data or symbol2 not in self.data:
            return None

        prices1 = self.data[symbol1].values[-self.config.lookback_window:]
        prices2 = self.data[symbol2].values[-self.config.lookback_window:]

        if len(prices1) < self.config.lookback_window or len(prices2) < self.config.lookback_window:
            return None

        # Régression linéaire
        from scipy import stats

        slope, intercept, r_value, p_value, std_err = stats.linregress(prices1, prices2)
        hedge_ratio = slope

        if not (self.config.min_hedge_ratio <= abs(hedge_ratio) <= self.config.max_hedge_ratio):
            return None

        # Spread
        spread = prices2 - hedge_ratio * prices1
        z_score = (spread - np.mean(spread)) / np.std(spread)

        # Test de stationnarité (ADF simplifié)
        from statsmodels.tsa.stattools import adfuller

        try:
            adf_result = adfuller(spread, autolag='AIC')
            p_value_adf = adf_result[1]
        except:
            p_value_adf = 1.0

        # Half-life
        spread_lag = np.roll(spread, 1)
        spread_lag[0] = spread[0]
        spread_diff = spread - spread_lag

        try:
            slope_hl, _, _, _, _ = stats.linregress(spread_lag, spread_diff)
            half_life = -np.log(2) / slope_hl if slope_hl < 0 else float('inf')
        except:
            half_life = float('inf')

        is_cointegrated = (
            p_value_adf < self.config.p_value_threshold and
            half_life < self.config.half_life_threshold
        )

        return CointegrationResult(
            pair=(symbol1, symbol2),
            hedge_ratio=hedge_ratio,
            spread=spread,
            z_score=z_score,
            p_value=p_value_adf,
            is_cointegrated=is_cointegrated,
            half_life=half_life,
            stationarity=1 - p_value_adf,
        )

    def _update_positions(self) -> None:
        """Met à jour les positions"""
        for pair in self.cointegrated_pairs:
            self._check_pair_signals(pair)

    def _check_pair_signals(self, pair: CointegrationResult) -> None:
        """
        Vérifie les signaux pour une paire.

        Args:
            pair: Paire cointégrée
        """
        symbol1, symbol2 = pair.pair
        z_score = pair.z_score[-1] if len(pair.z_score) > 0 else 0

        # Vérification des positions existantes
        position = self._find_position(symbol1, symbol2)

        if position is None:
            # Pas de position ouverte
            if z_score > self.config.entry_zscore:
                # Short spread -> short symbol1, long symbol2
                self._open_position(symbol1, symbol2, pair.hedge_ratio, 'short')
            elif z_score < -self.config.entry_zscore:
                # Long spread -> long symbol1, short symbol2
                self._open_position(symbol1, symbol2, pair.hedge_ratio, 'long')
        else:
            # Position ouverte
            if abs(z_score) < self.config.exit_zscore:
                # Fermeture
                self._close_position(position)
            elif abs(z_score) > self.config.stop_loss_zscore:
                # Stop loss
                position['status'] = 'stopped'
                self._close_position(position)

    def _find_position(self, symbol1: str, symbol2: str) -> Optional[Dict[str, Any]]:
        """Trouve une position ouverte"""
        for pos in self.open_positions:
            if pos['symbol1'] == symbol1 and pos['symbol2'] == symbol2:
                return pos
        return None

    def _open_position(self, symbol1: str, symbol2: str, hedge_ratio: float, direction: str) -> None:
        """
        Ouvre une position.

        Args:
            symbol1: Premier symbole
            symbol2: Deuxième symbole
            hedge_ratio: Ratio de couverture
            direction: 'long' ou 'short'
        """
        # Calcul de la taille
        price1 = self.data[symbol1].iloc[-1] if symbol1 in self.data else 1
        price2 = self.data[symbol2].iloc[-1] if symbol2 in self.data else 1

        position_size = min(
            self.config.max_position_size,
            self.config.min_position_size * 10
        )

        if direction == 'long':
            # Long symbol1, short symbol2
            size1 = position_size / price1
            size2 = position_size * hedge_ratio / price2
        else:
            # Short symbol1, long symbol2
            size1 = -position_size / price1
            size2 = -position_size * hedge_ratio / price2

        position = {
            'symbol1': symbol1,
            'symbol2': symbol2,
            'size1': size1,
            'size2': size2,
            'entry_price1': price1,
            'entry_price2': price2,
            'hedge_ratio': hedge_ratio,
            'direction': direction,
            'entry_zscore': self._get_current_zscore(symbol1, symbol2),
            'entry_time': datetime.now(),
            'status': 'open',
        }

        self.open_positions.append(position)

        logger.info(f"Position ouverte: {direction} {symbol1}/{symbol2}")

    def _close_position(self, position: Dict[str, Any]) -> None:
        """
        Ferme une position.

        Args:
            position: Position à fermer
        """
        # Calcul du P&L
        symbol1, symbol2 = position['symbol1'], position['symbol2']
        price1 = self.data[symbol1].iloc[-1] if symbol1 in self.data else position['entry_price1']
        price2 = self.data[symbol2].iloc[-1] if symbol2 in self.data else position['entry_price2']

        pnl1 = (price1 - position['entry_price1']) * position['size1']
        pnl2 = (price2 - position['entry_price2']) * position['size2']
        total_pnl = pnl1 + pnl2

        # Frais
        fees = abs(position['size1'] * price1 + position['size2'] * price2) * self.config.fee_rate
        net_pnl = total_pnl - fees

        trade = {
            'symbol1': symbol1,
            'symbol2': symbol2,
            'size1': position['size1'],
            'size2': position['size2'],
            'entry_time': position['entry_time'],
            'exit_time': datetime.now(),
            'entry_price1': position['entry_price1'],
            'entry_price2': position['entry_price2'],
            'exit_price1': price1,
            'exit_price2': price2,
            'pnl1': pnl1,
            'pnl2': pnl2,
            'total_pnl': total_pnl,
            'fees': fees,
            'net_pnl': net_pnl,
            'direction': position['direction'],
            'status': position.get('status', 'closed'),
        }

        self.trade_history.append(trade)
        self.open_positions.remove(position)

        logger.info(f"Position fermée: P&L={net_pnl:.2f}")

    def _get_current_zscore(self, symbol1: str, symbol2: str) -> float:
        """Calcule le z-score actuel pour une paire"""
        for pair in self.cointegrated_pairs:
            if pair.pair == (symbol1, symbol2) or pair.pair == (symbol2, symbol1):
                return pair.z_score[-1] if len(pair.z_score) > 0 else 0
        return 0

    def get_signals(self) -> List[Dict[str, Any]]:
        """
        Retourne les signaux de trading.

        Returns:
            List[Dict[str, Any]]: Signaux
        """
        signals = []

        for pair in self.cointegrated_pairs:
            symbol1, symbol2 = pair.pair
            z_score = pair.z_score[-1] if len(pair.z_score) > 0 else 0

            if z_score > self.config.entry_zscore:
                signals.append({
                    'type': 'short_spread',
                    'symbol1': symbol1,
                    'symbol2': symbol2,
                    'hedge_ratio': pair.hedge_ratio,
                    'z_score': z_score,
                    'confidence': self._calculate_confidence(pair),
                    'timestamp': datetime.now(),
                })
            elif z_score < -self.config.entry_zscore:
                signals.append({
                    'type': 'long_spread',
                    'symbol1': symbol1,
                    'symbol2': symbol2,
                    'hedge_ratio': pair.hedge_ratio,
                    'z_score': z_score,
                    'confidence': self._calculate_confidence(pair),
                    'timestamp': datetime.now(),
                })

        return signals

    def _calculate_confidence(self, pair: CointegrationResult) -> float:
        """Calcule la confiance pour une paire"""
        factors = []

        # 1. P-value
        factors.append(1 - pair.p_value)

        # 2. Half-life
        half_life_norm = min(1, pair.half_life / 50)
        factors.append(1 - half_life_norm)

        # 3. Stationnarité
        factors.append(pair.stationarity)

        return np.mean(factors)

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances de la stratégie.

        Returns:
            Dict[str, Any]: Performances
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
            }

        pnls = [t['net_pnl'] for t in self.trade_history]
        wins = [p for p in pnls if p > 0]

        return {
            'total_trades': len(self.trade_history),
            'total_pnl': sum(pnls),
            'win_rate': len(wins) / len(pnls) if pnls else 0.0,
            'avg_pnl': np.mean(pnls) if pnls else 0.0,
            'max_pnl': max(pnls) if pnls else 0.0,
            'min_pnl': min(pnls) if pnls else 0.0,
            'open_positions': len(self.open_positions),
            'active_pairs': len(self.cointegrated_pairs),
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la stratégie.

        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'symbols': self.config.symbols,
            'cointegrated_pairs': [p.to_dict() for p in self.cointegrated_pairs],
            'open_positions': self.open_positions,
            'total_trades': len(self.trade_history),
            'active_pairs': len(self.cointegrated_pairs),
        }


def create_statistical_arbitrage(
    symbols: List[str] = None,
    lookback_window: int = 100,
    entry_zscore: float = 2.0,
    **kwargs
) -> StatisticalArbitrage:
    """
    Factory pour créer une stratégie d'arbitrage statistique.

    Args:
        symbols: Liste des symboles
        lookback_window: Fenêtre de contexte
        entry_zscore: Z-score d'entrée
        **kwargs: Arguments supplémentaires

    Returns:
        StatisticalArbitrage: Stratégie d'arbitrage statistique
    """
    if symbols is None:
        symbols = ['BTC-USD', 'ETH-USD', 'SOL-USD']

    config = StatisticalArbitrageConfig(
        symbols=symbols,
        lookback_window=lookback_window,
        entry_zscore=entry_zscore,
        **kwargs
    )
    return StatisticalArbitrage(config)


__all__ = [
    'StatisticalArbitrage',
    'StatisticalArbitrageConfig',
    'CointegrationResult',
    'create_statistical_arbitrage',
]

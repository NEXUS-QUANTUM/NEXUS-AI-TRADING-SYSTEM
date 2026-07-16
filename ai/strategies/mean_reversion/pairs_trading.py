# ai/strategies/mean_reversion/pairs_trading.py
"""
NEXUS AI TRADING SYSTEM - Pairs Trading Mean Reversion Strategy
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
    from sklearn.linear_model import LinearRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class Pair:
    """Paire de trading"""
    symbol1: str
    symbol2: str
    hedge_ratio: float
    spread: np.ndarray
    z_score: np.ndarray
    half_life: float
    cointegration_pvalue: float
    correlation: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol1': self.symbol1,
            'symbol2': self.symbol2,
            'hedge_ratio': self.hedge_ratio,
            'half_life': self.half_life,
            'cointegration_pvalue': self.cointegration_pvalue,
            'correlation': self.correlation,
        }


@dataclass
class PairsTradingConfig:
    """Configuration pour Pairs Trading"""
    symbols: List[str] = field(default_factory=lambda: ['BTC-USD', 'ETH-USD', 'SOL-USD'])
    lookback_window: int = 100
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    stop_loss_zscore: float = 3.5
    min_correlation: float = 0.5
    max_hedge_ratio: float = 2.0
    min_hedge_ratio: float = 0.1
    max_position_size: float = 10000.0
    min_position_size: float = 100.0
    fee_rate: float = 0.001
    max_pairs: int = 5
    use_cointegration: bool = True
    cointegration_pvalue_threshold: float = 0.05

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbols': self.symbols,
            'lookback_window': self.lookback_window,
            'entry_zscore': self.entry_zscore,
            'exit_zscore': self.exit_zscore,
            'stop_loss_zscore': self.stop_loss_zscore,
            'min_correlation': self.min_correlation,
            'max_hedge_ratio': self.max_hedge_ratio,
            'min_hedge_ratio': self.min_hedge_ratio,
            'max_position_size': self.max_position_size,
            'min_position_size': self.min_position_size,
            'fee_rate': self.fee_rate,
            'max_pairs': self.max_pairs,
            'use_cointegration': self.use_cointegration,
            'cointegration_pvalue_threshold': self.cointegration_pvalue_threshold,
        }


@dataclass
class PairsSignal:
    """Signal de trading de paires"""
    timestamp: datetime
    pair: Tuple[str, str]
    signal_type: str
    symbol1: str
    symbol2: str
    symbol1_quantity: float
    symbol2_quantity: float
    z_score: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'pair': self.pair,
            'signal_type': self.signal_type,
            'symbol1': self.symbol1,
            'symbol2': self.symbol2,
            'symbol1_quantity': self.symbol1_quantity,
            'symbol2_quantity': self.symbol2_quantity,
            'z_score': self.z_score,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class PairsTradingStrategy:
    """
    Stratégie de trading de paires (Pairs Trading).

    Features:
    - Cointegration testing
    - Spread calculation
    - Entry/Exit signals
    - Position management
    - Risk management

    Example:
        ```python
        config = PairsTradingConfig(
            symbols=['BTC-USD', 'ETH-USD'],
            lookback_window=100,
            entry_zscore=2.0
        )
        strategy = PairsTradingStrategy(config)

        # Update with data
        signals = strategy.update(price_data)
        ```
    """

    def __init__(self, config: Optional[PairsTradingConfig] = None):
        self.config = config or PairsTradingConfig()
        self.data: Dict[str, pd.Series] = {}
        self.pairs: List[Pair] = []
        self.signals: List[PairsSignal] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.open_positions: List[Dict[str, Any]] = []

        logger.info(f"PairsTradingStrategy initialisé")

    def update(self, data: Dict[str, pd.Series]) -> List[PairsSignal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: Dictionnaire des séries de prix

        Returns:
            List[PairsSignal]: Signaux générés
        """
        self.data = data

        # Mise à jour des paires
        self._update_pairs()

        # Génération des signaux
        signals = self._generate_signals()

        # Gestion des positions
        self._update_positions()

        return signals

    def _update_pairs(self) -> None:
        """Met à jour les paires de trading"""
        if len(self.data) < 2:
            return

        symbols = list(self.data.keys())
        new_pairs = []

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                pair = self._analyze_pair(symbols[i], symbols[j])
                if pair:
                    new_pairs.append(pair)

        # Trier par p-value et corrélation
        new_pairs.sort(key=lambda x: (x.cointegration_pvalue, -x.correlation))
        self.pairs = new_pairs[:self.config.max_pairs]

    def _analyze_pair(self, symbol1: str, symbol2: str) -> Optional[Pair]:
        """
        Analyse une paire.

        Args:
            symbol1: Premier symbole
            symbol2: Deuxième symbole

        Returns:
            Optional[Pair]: Résultat de l'analyse
        """
        if symbol1 not in self.data or symbol2 not in self.data:
            return None

        prices1 = self.data[symbol1].values[-self.config.lookback_window:]
        prices2 = self.data[symbol2].values[-self.config.lookback_window:]

        if len(prices1) < self.config.lookback_window or len(prices2) < self.config.lookback_window:
            return None

        # Corrélation
        correlation = np.corrcoef(prices1, prices2)[0, 1]

        if abs(correlation) < self.config.min_correlation:
            return None

        if self.config.use_cointegration:
            # Test de cointégration
            coint_pvalue = self._test_cointegration(prices1, prices2)

            if coint_pvalue > self.config.cointegration_pvalue_threshold:
                return None
        else:
            coint_pvalue = 0.0

        # Régression linéaire
        hedge_ratio = self._calculate_hedge_ratio(prices1, prices2)

        if not (self.config.min_hedge_ratio <= abs(hedge_ratio) <= self.config.max_hedge_ratio):
            return None

        # Spread
        spread = prices2 - hedge_ratio * prices1
        z_score = (spread - np.mean(spread)) / np.std(spread)

        # Half-life
        half_life = self._calculate_half_life(spread)

        return Pair(
            symbol1=symbol1,
            symbol2=symbol2,
            hedge_ratio=hedge_ratio,
            spread=spread,
            z_score=z_score,
            half_life=half_life,
            cointegration_pvalue=coint_pvalue,
            correlation=correlation,
        )

    def _test_cointegration(self, prices1: np.ndarray, prices2: np.ndarray) -> float:
        """
        Teste la cointégration entre deux séries.

        Args:
            prices1: Première série
            prices2: Deuxième série

        Returns:
            float: P-value du test
        """
        if not SCIPY_AVAILABLE:
            return 1.0

        try:
            from statsmodels.tsa.stattools import coint
            coint_result = coint(prices1, prices2)
            return coint_result[1]
        except:
            return 1.0

    def _calculate_hedge_ratio(self, prices1: np.ndarray, prices2: np.ndarray) -> float:
        """
        Calcule le ratio de couverture.

        Args:
            prices1: Première série
            prices2: Deuxième série

        Returns:
            float: Ratio de couverture
        """
        if SKLEARN_AVAILABLE:
            X = prices1.reshape(-1, 1)
            y = prices2
            model = LinearRegression()
            model.fit(X, y)
            return model.coef_[0]
        else:
            # Méthode simplifiée
            return np.std(prices2) / np.std(prices1)

    def _calculate_half_life(self, spread: np.ndarray) -> float:
        """
        Calcule la half-life du spread.

        Args:
            spread: Spread

        Returns:
            float: Half-life
        """
        if not SCIPY_AVAILABLE or len(spread) < 2:
            return 100.0

        try:
            spread_lag = np.roll(spread, 1)
            spread_lag[0] = spread[0]
            spread_diff = spread - spread_lag

            slope, _, _, _, _ = stats.linregress(spread_lag[1:], spread_diff[1:])

            if slope < 0:
                half_life = -np.log(2) / slope
                return min(half_life, 1000)
            else:
                return 100.0
        except:
            return 100.0

    def _generate_signals(self) -> List[PairsSignal]:
        """
        Génère les signaux de trading.

        Returns:
            List[PairsSignal]: Signaux générés
        """
        signals = []

        for pair in self.pairs:
            current_z = pair.z_score[-1]

            # Vérification de la position
            position = self._find_position(pair.symbol1, pair.symbol2)

            if position is None:
                # Pas de position ouverte
                if current_z > self.config.entry_zscore:
                    # Short spread -> short symbol1, long symbol2
                    signal = self._create_signal(
                        pair, 'short_spread',
                        symbol1_quantity=-1,
                        symbol2_quantity=pair.hedge_ratio,
                        z_score=current_z,
                        reason=f"short_spread_zscore_{current_z:.2f}"
                    )
                    signals.append(signal)

                elif current_z < -self.config.entry_zscore:
                    # Long spread -> long symbol1, short symbol2
                    signal = self._create_signal(
                        pair, 'long_spread',
                        symbol1_quantity=1,
                        symbol2_quantity=-pair.hedge_ratio,
                        z_score=current_z,
                        reason=f"long_spread_zscore_{abs(current_z):.2f}"
                    )
                    signals.append(signal)

            else:
                # Position ouverte
                duration = (datetime.now() - position['entry_time']).days

                if duration >= 10:  # Max duration
                    signal = self._create_signal(
                        pair, 'exit',
                        symbol1_quantity=0,
                        symbol2_quantity=0,
                        z_score=current_z,
                        reason="max_duration_exceeded"
                    )
                    signals.append(signal)

                elif abs(current_z) < self.config.exit_zscore:
                    signal = self._create_signal(
                        pair, 'exit',
                        symbol1_quantity=0,
                        symbol2_quantity=0,
                        z_score=current_z,
                        reason="mean_reversion"
                    )
                    signals.append(signal)

                elif abs(current_z) > self.config.stop_loss_zscore:
                    signal = self._create_signal(
                        pair, 'exit',
                        symbol1_quantity=0,
                        symbol2_quantity=0,
                        z_score=current_z,
                        reason="stop_loss"
                    )
                    signals.append(signal)

        return signals

    def _create_signal(
        self,
        pair: Pair,
        signal_type: str,
        symbol1_quantity: float,
        symbol2_quantity: float,
        z_score: float,
        reason: str
    ) -> PairsSignal:
        """
        Crée un signal de trading.

        Args:
            pair: Paire
            signal_type: Type de signal
            symbol1_quantity: Quantité du symbole 1
            symbol2_quantity: Quantité du symbole 2
            z_score: Z-score
            reason: Raison

        Returns:
            PairsSignal: Signal créé
        """
        return PairsSignal(
            timestamp=datetime.now(),
            pair=(pair.symbol1, pair.symbol2),
            signal_type=signal_type,
            symbol1=pair.symbol1,
            symbol2=pair.symbol2,
            symbol1_quantity=symbol1_quantity,
            symbol2_quantity=symbol2_quantity,
            z_score=z_score,
            confidence=self._calculate_confidence(z_score),
            reason=reason,
        )

    def _calculate_confidence(self, z_score: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            z_score: Z-score

        Returns:
            float: Niveau de confiance (0-1)
        """
        confidence = min(1.0, abs(z_score) / self.config.entry_zscore)
        return confidence

    def _find_position(self, symbol1: str, symbol2: str) -> Optional[Dict[str, Any]]:
        """
        Trouve une position ouverte.

        Args:
            symbol1: Premier symbole
            symbol2: Deuxième symbole

        Returns:
            Optional[Dict[str, Any]]: Position trouvée
        """
        for pos in self.open_positions:
            if pos['symbol1'] == symbol1 and pos['symbol2'] == symbol2:
                return pos
        return None

    def _update_positions(self) -> None:
        """Met à jour les positions"""
        for signal in self.signals:
            if signal.signal_type in ['long_spread', 'short_spread']:
                # Ouverture de position
                position = {
                    'symbol1': signal.symbol1,
                    'symbol2': signal.symbol2,
                    'symbol1_quantity': signal.symbol1_quantity,
                    'symbol2_quantity': signal.symbol2_quantity,
                    'entry_time': signal.timestamp,
                    'entry_price1': self.data[signal.symbol1].iloc[-1],
                    'entry_price2': self.data[signal.symbol2].iloc[-1],
                    'signal': signal.to_dict(),
                }
                self.open_positions.append(position)

            elif signal.signal_type == 'exit':
                # Fermeture de position
                position = self._find_position(signal.symbol1, signal.symbol2)
                if position:
                    self._close_position(position, signal)

    def _close_position(self, position: Dict[str, Any], signal: PairsSignal) -> None:
        """
        Ferme une position.

        Args:
            position: Position à fermer
            signal: Signal de fermeture
        """
        price1 = self.data[signal.symbol1].iloc[-1]
        price2 = self.data[signal.symbol2].iloc[-1]

        # Calcul du P&L
        pnl1 = (price1 - position['entry_price1']) * position['symbol1_quantity']
        pnl2 = (price2 - position['entry_price2']) * position['symbol2_quantity']
        total_pnl = pnl1 + pnl2

        # Frais
        fees = abs(position['symbol1_quantity'] * price1 + position['symbol2_quantity'] * price2) * self.config.fee_rate
        net_pnl = total_pnl - fees

        trade = {
            'symbol1': signal.symbol1,
            'symbol2': signal.symbol2,
            'entry_time': position['entry_time'].isoformat(),
            'exit_time': signal.timestamp.isoformat(),
            'entry_price1': position['entry_price1'],
            'entry_price2': position['entry_price2'],
            'exit_price1': price1,
            'exit_price2': price2,
            'symbol1_quantity': position['symbol1_quantity'],
            'symbol2_quantity': position['symbol2_quantity'],
            'pnl1': pnl1,
            'pnl2': pnl2,
            'total_pnl': total_pnl,
            'fees': fees,
            'net_pnl': net_pnl,
            'signal': signal.to_dict(),
        }

        self.trade_history.append(trade)
        self.open_positions.remove(position)

        logger.info(f"Position fermée: {trade['symbol1']}/{trade['symbol2']} - P&L={net_pnl:.2f}")

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
            'active_pairs': len(self.pairs),
        }


def create_pairs_trading_strategy(
    symbols: List[str] = None,
    lookback_window: int = 100,
    entry_zscore: float = 2.0,
    **kwargs
) -> PairsTradingStrategy:
    """
    Factory pour créer une stratégie de trading de paires.

    Args:
        symbols: Liste des symboles
        lookback_window: Fenêtre de contexte
        entry_zscore: Z-score d'entrée
        **kwargs: Arguments supplémentaires

    Returns:
        PairsTradingStrategy: Stratégie de trading de paires
    """
    if symbols is None:
        symbols = ['BTC-USD', 'ETH-USD', 'SOL-USD']

    config = PairsTradingConfig(
        symbols=symbols,
        lookback_window=lookback_window,
        entry_zscore=entry_zscore,
        **kwargs
    )
    return PairsTradingStrategy(config)


__all__ = [
    'PairsTradingStrategy',
    'PairsTradingConfig',
    'Pair',
    'PairsSignal',
    'create_pairs_trading_strategy',
]

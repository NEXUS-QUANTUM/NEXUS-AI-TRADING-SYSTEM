
# ai/strategies/mean_reversion/kalman_filter.py
"""
NEXUS AI TRADING SYSTEM - Kalman Filter Mean Reversion Strategy
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class KalmanFilterConfig:
    """Configuration pour Kalman Filter"""
    symbol: str = "BTC-USD"
    observation_noise: float = 0.1
    process_noise: float = 0.01
    initial_state: float = 0.0
    initial_covariance: float = 1.0
    entry_threshold: float = 2.0
    exit_threshold: float = 1.0
    stop_loss_threshold: float = 3.0
    position_size: float = 1.0
    max_position_duration: int = 10
    fee_rate: float = 0.001
    use_adaptive_noise: bool = True
    noise_adaptation_rate: float = 0.01

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'observation_noise': self.observation_noise,
            'process_noise': self.process_noise,
            'initial_state': self.initial_state,
            'initial_covariance': self.initial_covariance,
            'entry_threshold': self.entry_threshold,
            'exit_threshold': self.exit_threshold,
            'stop_loss_threshold': self.stop_loss_threshold,
            'position_size': self.position_size,
            'max_position_duration': self.max_position_duration,
            'fee_rate': self.fee_rate,
            'use_adaptive_noise': self.use_adaptive_noise,
            'noise_adaptation_rate': self.noise_adaptation_rate,
        }


@dataclass
class KalmanFilterState:
    """État du filtre de Kalman"""
    timestamp: datetime
    price: float
    estimated_state: float
    covariance: float
    residual: float
    kalman_gain: float
    z_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'estimated_state': self.estimated_state,
            'covariance': self.covariance,
            'residual': self.residual,
            'kalman_gain': self.kalman_gain,
            'z_score': self.z_score,
        }


@dataclass
class KalmanSignal:
    """Signal de trading Kalman"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    estimated_state: float
    z_score: float
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'estimated_state': self.estimated_state,
            'z_score': self.z_score,
            'confidence': self.confidence,
            'reason': self.reason,
        }


class KalmanFilterStrategy:
    """
    Stratégie de mean reversion avec filtre de Kalman.

    Features:
    - Kalman filter for state estimation
    - Adaptive noise estimation
    - Entry/Exit signals
    - Position management

    Example:
        ```python
        config = KalmanFilterConfig(
            symbol='BTC-USD',
            observation_noise=0.1,
            process_noise=0.01,
            entry_threshold=2.0
        )
        strategy = KalmanFilterStrategy(config)

        # Update with price
        signal = strategy.update(price)
        ```
    """

    def __init__(self, config: Optional[KalmanFilterConfig] = None):
        self.config = config or KalmanFilterConfig()

        # Filtre de Kalman
        self.x = self.config.initial_state  # État estimé
        self.P = self.config.initial_covariance  # Covariance
        self.Q = self.config.process_noise  # Bruit de processus
        self.R = self.config.observation_noise  # Bruit d'observation

        self.price_history: List[float] = []
        self.state_history: List[KalmanFilterState] = []
        self.signals: List[KalmanSignal] = []
        self.trade_history: List[Dict[str, Any]] = []

        self.position = 0
        self.position_entry_price = 0.0
        self.position_entry_time: Optional[datetime] = None
        self.current_price = 0.0

        # Statistiques
        self.residuals: List[float] = []
        self.z_scores: List[float] = []

        logger.info(f"KalmanFilterStrategy initialisé pour {self.config.symbol}")

    def update(self, price: float) -> Optional[KalmanSignal]:
        """
        Met à jour le filtre avec un nouveau prix.

        Args:
            price: Prix actuel

        Returns:
            Optional[KalmanSignal]: Signal généré
        """
        self.current_price = price
        self.price_history.append(price)

        # Prédiction
        x_pred = self.x
        P_pred = self.P + self.Q

        # Mise à jour
        y = price - x_pred  # Résidu
        S = P_pred + self.R  # Covariance du résidu
        K = P_pred / S  # Gain de Kalman

        x_updated = x_pred + K * y
        P_updated = (1 - K) * P_pred

        # Mise à jour de l'état
        self.x = x_updated
        self.P = P_updated

        # Calcul du z-score
        z_score = y / np.sqrt(S)

        # Enregistrement
        state = KalmanFilterState(
            timestamp=datetime.now(),
            price=price,
            estimated_state=self.x,
            covariance=self.P,
            residual=y,
            kalman_gain=K,
            z_score=z_score,
        )

        self.state_history.append(state)
        self.residuals.append(y)
        self.z_scores.append(z_score)

        # Adaptation des bruits
        if self.config.use_adaptive_noise:
            self._adapt_noise(y)

        # Génération du signal
        signal = self._generate_signal(z_score)

        if signal:
            self.signals.append(signal)

            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        return signal

    def _adapt_noise(self, residual: float) -> None:
        """
        Adapte les bruits du filtre.

        Args:
            residual: Résidu de la mise à jour
        """
        # Adaptation du bruit d'observation
        if len(self.residuals) > 10:
            recent_residuals = self.residuals[-10:]
            var_residuals = np.var(recent_residuals)

            if var_residuals > 0:
                target_R = max(0.01, var_residuals)
                self.R += self.config.noise_adaptation_rate * (target_R - self.R)

        # Adaptation du bruit de processus
        if len(self.state_history) > 10:
            recent_states = [s.estimated_state for s in self.state_history[-10:]]
            var_states = np.var(recent_states)

            if var_states > 0:
                target_Q = max(0.001, var_states * 0.01)
                self.Q += self.config.noise_adaptation_rate * (target_Q - self.Q)

    def _generate_signal(self, z_score: float) -> Optional[KalmanSignal]:
        """
        Génère un signal de trading.

        Args:
            z_score: Z-score actuel

        Returns:
            Optional[KalmanSignal]: Signal généré
        """
        if self.position == 0:
            # Pas de position ouverte
            if z_score < -self.config.entry_threshold:
                # Oversold -> Buy
                return KalmanSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='buy',
                    price=self.current_price,
                    estimated_state=self.x,
                    z_score=z_score,
                    confidence=self._calculate_confidence(z_score),
                    reason=f"oversold_zscore_{abs(z_score):.2f}",
                )
            elif z_score > self.config.entry_threshold:
                # Overbought -> Sell
                return KalmanSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='sell',
                    price=self.current_price,
                    estimated_state=self.x,
                    z_score=z_score,
                    confidence=self._calculate_confidence(z_score),
                    reason=f"overbought_zscore_{abs(z_score):.2f}",
                )

        else:
            # Position ouverte
            duration = (datetime.now() - self.position_entry_time).days if self.position_entry_time else 0

            if duration >= self.config.max_position_duration:
                return KalmanSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='exit',
                    price=self.current_price,
                    estimated_state=self.x,
                    z_score=z_score,
                    confidence=0.8,
                    reason="max_duration_exceeded",
                )

            # Exit lorsque le z-score revient vers la moyenne
            if self.position > 0:  # Long position
                if z_score > -self.config.exit_threshold:
                    return KalmanSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='exit',
                        price=self.current_price,
                        estimated_state=self.x,
                        z_score=z_score,
                        confidence=self._calculate_confidence(abs(z_score)),
                        reason="mean_reversion",
                    )

            elif self.position < 0:  # Short position
                if z_score < self.config.exit_threshold:
                    return KalmanSignal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='exit',
                        price=self.current_price,
                        estimated_state=self.x,
                        z_score=z_score,
                        confidence=self._calculate_confidence(abs(z_score)),
                        reason="mean_reversion",
                    )

            # Stop loss
            if abs(z_score) > self.config.stop_loss_threshold:
                return KalmanSignal(
                    timestamp=datetime.now(),
                    symbol=self.config.symbol,
                    signal_type='exit',
                    price=self.current_price,
                    estimated_state=self.x,
                    z_score=z_score,
                    confidence=0.9,
                    reason="stop_loss",
                )

        return None

    def _calculate_confidence(self, z_score: float) -> float:
        """
        Calcule le niveau de confiance.

        Args:
            z_score: Z-score

        Returns:
            float: Niveau de confiance (0-1)
        """
        confidence = min(1.0, abs(z_score) / self.config.entry_threshold)
        return confidence

    def _open_position(self, signal: KalmanSignal) -> None:
        """Ouvre une position"""
        if signal.signal_type == 'buy':
            self.position = self.config.position_size
        elif signal.signal_type == 'sell':
            self.position = -self.config.position_size

        self.position_entry_price = signal.price
        self.position_entry_time = signal.timestamp

        logger.info(f"Position ouverte: {signal.signal_type} @ {signal.price:.2f}")

    def _close_position(self, signal: KalmanSignal) -> None:
        """Ferme une position"""
        if self.position == 0:
            return

        # Calcul du P&L
        if self.position > 0:
            pnl = (signal.price - self.position_entry_price) * abs(self.position)
        else:
            pnl = (self.position_entry_price - signal.price) * abs(self.position)

        # Frais
        fees = abs(self.position) * signal.price * self.config.fee_rate
        net_pnl = pnl - fees

        trade = {
            'entry_time': self.position_entry_time.isoformat() if self.position_entry_time else None,
            'exit_time': signal.timestamp.isoformat(),
            'entry_price': self.position_entry_price,
            'exit_price': signal.price,
            'position_size': self.position,
            'pnl': pnl,
            'fees': fees,
            'net_pnl': net_pnl,
            'signal': signal.to_dict(),
        }

        self.trade_history.append(trade)

        logger.info(f"Position fermée: P&L={net_pnl:.2f}")

        # Reset position
        self.position = 0
        self.position_entry_price = 0.0
        self.position_entry_time = None

    def get_state(self) -> Dict[str, Any]:
        """
        Retourne l'état actuel du filtre.

        Returns:
            Dict[str, Any]: État du filtre
        """
        return {
            'estimated_state': self.x,
            'covariance': self.P,
            'process_noise': self.Q,
            'observation_noise': self.R,
            'current_price': self.current_price,
            'z_score': self.z_scores[-1] if self.z_scores else 0.0,
        }

    def get_position(self) -> Dict[str, Any]:
        """
        Retourne la position actuelle.

        Returns:
            Dict[str, Any]: Position
        """
        return {
            'position': self.position,
            'entry_price': self.position_entry_price,
            'entry_time': self.position_entry_time.isoformat() if self.position_entry_time else None,
            'current_price': self.current_price,
            'unrealized_pnl': self._calculate_unrealized_pnl(),
        }

    def _calculate_unrealized_pnl(self) -> float:
        """Calcule le P&L non réalisé"""
        if self.position == 0:
            return 0.0

        if self.position > 0:
            pnl = (self.current_price - self.position_entry_price) * abs(self.position)
        else:
            pnl = (self.position_entry_price - self.current_price) * abs(self.position)

        return pnl

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
        }

    def get_history(self) -> pd.DataFrame:
        """
        Retourne l'historique des états.

        Returns:
            pd.DataFrame: Historique
        """
        if not self.state_history:
            return pd.DataFrame()

        data = []
        for state in self.state_history:
            data.append(state.to_dict())

        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df


def create_kalman_filter_strategy(
    symbol: str = "BTC-USD",
    observation_noise: float = 0.1,
    process_noise: float = 0.01,
    entry_threshold: float = 2.0,
    **kwargs
) -> KalmanFilterStrategy:
    """
    Factory pour créer une stratégie Kalman Filter.

    Args:
        symbol: Symbole
        observation_noise: Bruit d'observation
        process_noise: Bruit de processus
        entry_threshold: Seuil d'entrée
        **kwargs: Arguments supplémentaires

    Returns:
        KalmanFilterStrategy: Stratégie Kalman Filter
    """
    config = KalmanFilterConfig(
        symbol=symbol,
        observation_noise=observation_noise,
        process_noise=process_noise,
        entry_threshold=entry_threshold,
        **kwargs
    )
    return KalmanFilterStrategy(config)


__all__ = [
    'KalmanFilterStrategy',
    'KalmanFilterConfig',
    'KalmanFilterState',
    'KalmanSignal',
    'create_kalman_filter_strategy',
]

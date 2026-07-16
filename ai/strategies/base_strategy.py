
# ai/strategies/base_strategy.py
"""
NEXUS AI TRADING SYSTEM - Base Strategy Classes
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import pickle
import os
import json
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Configuration de base pour une stratégie"""
    name: str = "base_strategy"
    symbol: str = "BTC-USD"
    position_size: float = 1.0
    max_positions: int = 1
    fee_rate: float = 0.001
    slippage: float = 0.0005
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'symbol': self.symbol,
            'position_size': self.position_size,
            'max_positions': self.max_positions,
            'fee_rate': self.fee_rate,
            'slippage': self.slippage,
            'enabled': self.enabled,
            'description': self.description,
        }


@dataclass
class Signal:
    """Signal de trading"""
    timestamp: datetime
    symbol: str
    signal_type: str  # 'buy', 'sell', 'exit'
    price: float
    quantity: float
    confidence: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'price': self.price,
            'quantity': self.quantity,
            'confidence': self.confidence,
            'reason': self.reason,
            'metadata': self.metadata,
        }


@dataclass
class Position:
    """Position de trading"""
    symbol: str
    entry_price: float
    quantity: float
    entry_time: datetime
    current_price: float
    pnl: float
    pnl_percent: float
    status: str  # 'open', 'closed'
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'entry_time': self.entry_time.isoformat(),
            'current_price': self.current_price,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'status': self.status,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'metadata': self.metadata,
        }


@dataclass
class Trade:
    """Trade exécuté"""
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percent: float
    fees: float
    reason: str
    signal: Signal

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'fees': self.fees,
            'reason': self.reason,
            'signal': self.signal.to_dict(),
        }


@dataclass
class BacktestResult:
    """Résultat de backtest"""
    total_trades: int
    win_rate: float
    total_pnl: float
    max_pnl: float
    min_pnl: float
    avg_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    trades: List[Trade]
    positions: List[Position]
    equity_curve: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'total_pnl': self.total_pnl,
            'max_pnl': self.max_pnl,
            'min_pnl': self.min_pnl,
            'avg_pnl': self.avg_pnl,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'trades': [t.to_dict() for t in self.trades],
            'positions': [p.to_dict() for p in self.positions],
            'equity_curve': self.equity_curve,
        }


class BaseStrategy(ABC):
    """
    Classe de base pour toutes les stratégies de trading.

    Features:
    - Signal generation
    - Position management
    - Risk management
    - Performance tracking
    - Backtesting

    Example:
        ```python
        class MyStrategy(BaseStrategy):
            def __init__(self, config):
                super().__init__(config)

            def generate_signal(self, data):
                if data['close'].iloc[-1] > data['close'].iloc[-2]:
                    return Signal(
                        timestamp=datetime.now(),
                        symbol=self.config.symbol,
                        signal_type='buy',
                        price=data['close'].iloc[-1],
                        quantity=self.config.position_size,
                        confidence=0.8,
                        reason='price_up'
                    )
                return None
        ```
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        self.positions: List[Position] = []
        self.trades: List[Trade] = []
        self.signals: List[Signal] = []
        self.equity_curve: List[float] = []
        self.initial_balance: float = 0.0
        self.current_balance: float = 0.0
        self.is_backtesting: bool = False

        logger.info(f"BaseStrategy initialisé: {self.config.name}")

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        Génère un signal de trading.

        Args:
            data: Données de marché

        Returns:
            Optional[Signal]: Signal généré
        """
        pass

    def update(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        Met à jour la stratégie avec de nouvelles données.

        Args:
            data: Données de marché

        Returns:
            Optional[Signal]: Signal généré
        """
        signal = self.generate_signal(data)

        if signal:
            self.signals.append(signal)

            # Gestion de la position
            if signal.signal_type in ['buy', 'sell']:
                self._open_position(signal)
            elif signal.signal_type == 'exit':
                self._close_position(signal)

        # Mise à jour des positions
        self._update_positions(data)

        return signal

    def _open_position(self, signal: Signal) -> None:
        """Ouvre une position"""
        if len(self.positions) >= self.config.max_positions:
            return

        position = Position(
            symbol=signal.symbol,
            entry_price=signal.price,
            quantity=signal.quantity,
            entry_time=signal.timestamp,
            current_price=signal.price,
            pnl=0.0,
            pnl_percent=0.0,
            status='open',
            metadata=signal.metadata,
        )

        self.positions.append(position)

        logger.info(f"Position ouverte: {signal.symbol} @ {signal.price:.2f}")

    def _close_position(self, signal: Signal) -> None:
        """Ferme une position"""
        position = self._find_position(signal.symbol)

        if position is None:
            return

        # Calcul du P&L
        if position.quantity > 0:
            pnl = (signal.price - position.entry_price) * abs(position.quantity)
        else:
            pnl = (position.entry_price - signal.price) * abs(position.quantity)

        # Frais
        fees = abs(position.quantity) * signal.price * self.config.fee_rate
        net_pnl = pnl - fees

        trade = Trade(
            symbol=position.symbol,
            entry_price=position.entry_price,
            exit_price=signal.price,
            quantity=position.quantity,
            entry_time=position.entry_time,
            exit_time=signal.timestamp,
            pnl=net_pnl,
            pnl_percent=net_pnl / (position.entry_price * abs(position.quantity)),
            fees=fees,
            reason=signal.reason,
            signal=signal,
        )

        self.trades.append(trade)

        logger.info(f"Position fermée: {trade.symbol} P&L={net_pnl:.2f}")

        # Mise à jour de l'équité
        self.current_balance += net_pnl

        # Retrait de la position
        position.status = 'closed'
        position.exit_price = signal.price
        position.exit_time = signal.timestamp
        self.positions.remove(position)

    def _update_positions(self, data: pd.DataFrame) -> None:
        """Met à jour les positions"""
        current_price = data['close'].iloc[-1]

        for position in self.positions:
            position.current_price = current_price

            if position.quantity > 0:
                pnl = (current_price - position.entry_price) * abs(position.quantity)
            else:
                pnl = (position.entry_price - current_price) * abs(position.quantity)

            position.pnl = pnl
            position.pnl_percent = pnl / (position.entry_price * abs(position.quantity))

        # Mise à jour de l'équité
        total_equity = self.current_balance
        for position in self.positions:
            total_equity += position.pnl

        self.equity_curve.append(total_equity)

    def _find_position(self, symbol: str) -> Optional[Position]:
        """Trouve une position ouverte"""
        for position in self.positions:
            if position.symbol == symbol and position.status == 'open':
                return position
        return None

    def get_positions(self) -> List[Position]:
        """
        Retourne les positions.

        Returns:
            List[Position]: Positions
        """
        return self.positions

    def get_trades(self) -> List[Trade]:
        """
        Retourne les trades.

        Returns:
            List[Trade]: Trades
        """
        return self.trades

    def get_signals(self) -> List[Signal]:
        """
        Retourne les signaux.

        Returns:
            List[Signal]: Signaux
        """
        return self.signals

    def get_equity_curve(self) -> List[float]:
        """
        Retourne la courbe d'équité.

        Returns:
            List[float]: Courbe d'équité
        """
        return self.equity_curve

    def backtest(self, data: pd.DataFrame, initial_balance: float = 10000.0) -> BacktestResult:
        """
        Effectue un backtest de la stratégie.

        Args:
            data: Données historiques
            initial_balance: Solde initial

        Returns:
            BacktestResult: Résultat du backtest
        """
        self.is_backtesting = True
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.equity_curve = [initial_balance]

        for i in range(len(data)):
            window = data.iloc[:i+1]
            self.update(window)

        return self._calculate_performance()

    def _calculate_performance(self) -> BacktestResult:
        """Calcule les performances"""
        if not self.trades:
            return BacktestResult(
                total_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                max_pnl=0.0,
                min_pnl=0.0,
                avg_pnl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                trades=[],
                positions=self.positions,
                equity_curve=self.equity_curve,
            )

        pnls = [t.pnl for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        total_pnl = sum(pnls)
        win_rate = len(wins) / len(pnls) if pnls else 0.0

        profit_factor = sum(wins) / abs(sum(losses)) if losses else float('inf')

        # Sharpe Ratio
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        sharpe_ratio = np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252) if len(returns) > 0 else 0.0

        # Max Drawdown
        peak = np.maximum.accumulate(self.equity_curve)
        drawdown = (peak - self.equity_curve) / peak
        max_drawdown = np.max(drawdown)

        return BacktestResult(
            total_trades=len(self.trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            max_pnl=max(pnls) if pnls else 0.0,
            min_pnl=min(pnls) if pnls else 0.0,
            avg_pnl=np.mean(pnls) if pnls else 0.0,
            avg_win=np.mean(wins) if wins else 0.0,
            avg_loss=np.mean(losses) if losses else 0.0,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            trades=self.trades,
            positions=self.positions,
            equity_curve=self.equity_curve,
        )

    def get_config(self) -> Dict[str, Any]:
        """
        Retourne la configuration de la stratégie.

        Returns:
            Dict[str, Any]: Configuration
        """
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """
        Retourne les métriques de la stratégie.

        Returns:
            Dict[str, Any]: Métriques
        """
        return {
            'total_trades': len(self.trades),
            'open_positions': len(self.positions),
            'total_signals': len(self.signals),
            'current_balance': self.current_balance,
            'equity': self.current_balance + sum(p.pnl for p in self.positions),
        }

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde la stratégie.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardée
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'trades': [t.to_dict() for t in self.trades],
                'positions': [p.to_dict() for p in self.positions],
                'signals': [s.to_dict() for s in self.signals],
                'equity_curve': self.equity_curve,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Stratégie sauvegardée: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'BaseStrategy':
        """
        Charge une stratégie.

        Args:
            filepath: Chemin du fichier

        Returns:
            BaseStrategy: Stratégie chargée
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = StrategyConfig(**data['config'])
            strategy = cls(config)

            # Restaurer les données
            strategy.trades = data.get('trades', [])
            strategy.positions = data.get('positions', [])
            strategy.signals = data.get('signals', [])
            strategy.equity_curve = data.get('equity_curve', [])

            logger.info(f"Stratégie chargée: {filepath}")
            return strategy

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_strategy(
    strategy_type: str,
    **kwargs
) -> BaseStrategy:
    """
    Factory pour créer des stratégies.

    Args:
        strategy_type: Type de stratégie
        **kwargs: Paramètres de configuration

    Returns:
        BaseStrategy: Stratégie créée
    """
    # Import des stratégies disponibles
    from ai.strategies.arbitrage import create_arbitrage_strategy
    from ai.strategies.hedging import create_hedging_strategy
    from ai.strategies.mean_reversion import create_mean_reversion_strategy
    from ai.strategies.momentum import create_momentum_strategy
    from ai.strategies.scalping import create_scalping_strategy
    from ai.strategies.sniper import create_sniper_strategy
    from ai.strategies.swing import create_swing_strategy

    strategy_map = {
        'arbitrage': create_arbitrage_strategy,
        'hedging': create_hedging_strategy,
        'mean_reversion': create_mean_reversion_strategy,
        'momentum': create_momentum_strategy,
        'scalping': create_scalping_strategy,
        'sniper': create_sniper_strategy,
        'swing': create_swing_strategy,
    }

    if strategy_type not in strategy_map:
        raise ValueError(f"Type de stratégie non supporté: {strategy_type}")

    return strategy_map[strategy_type](**kwargs)


__all__ = [
    'BaseStrategy',
    'StrategyConfig',
    'Signal',
    'Position',
    'Trade',
    'BacktestResult',
    'create_strategy',
]

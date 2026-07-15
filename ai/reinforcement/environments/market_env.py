
# ai/reinforcement/environments/market_env.py
"""
NEXUS AI TRADING SYSTEM - Market Environment for Reinforcement Learning
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import gymnasium as gym
from gymnasium import spaces
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MarketEnvConfig:
    """Configuration pour Market Environment"""
    symbol: str = "BTC-USD"
    window_size: int = 50
    max_steps: int = 1000
    initial_balance: float = 10000.0
    transaction_cost: float = 0.001
    reward_scaling: float = 1.0
    max_position: float = 1.0
    use_technical_indicators: bool = True
    use_sentiment: bool = False
    random_start: bool = True
    seed: Optional[int] = 42

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'window_size': self.window_size,
            'max_steps': self.max_steps,
            'initial_balance': self.initial_balance,
            'transaction_cost': self.transaction_cost,
            'reward_scaling': self.reward_scaling,
            'max_position': self.max_position,
            'use_technical_indicators': self.use_technical_indicators,
            'use_sentiment': self.use_sentiment,
            'random_start': self.random_start,
            'seed': self.seed,
        }


class MarketEnv(gym.Env):
    """
    Market Environment for Reinforcement Learning trading.

    Features:
    - Continuous and discrete action spaces
    - Technical indicators as state features
    - Realistic transaction costs
    - Portfolio management
    - Reward shaping
    - Random starting positions

    Example:
        ```python
        config = MarketEnvConfig(
            symbol='BTC-USD',
            window_size=50,
            initial_balance=10000.0,
            transaction_cost=0.001
        )
        env = MarketEnv(config, data=historical_data)

        # Training loop
        state = env.reset()
        done = False
        while not done:
            action = agent.select_action(state)
            next_state, reward, done, info = env.step(action)
            state = next_state
        ```
    """

    metadata = {'render_modes': ['human', 'rgb_array'], 'render_fps': 30}

    def __init__(
        self,
        config: Optional[MarketEnvConfig] = None,
        data: Optional[pd.DataFrame] = None
    ):
        super().__init__()

        self.config = config or MarketEnvConfig()
        self.data = data
        self.window_size = self.config.window_size
        self.max_steps = self.config.max_steps
        self.initial_balance = self.config.initial_balance
        self.transaction_cost = self.config.transaction_cost
        self.reward_scaling = self.config.reward_scaling
        self.max_position = self.config.max_position
        self.use_technical_indicators = self.config.use_technical_indicators
        self.use_sentiment = self.config.use_sentiment
        self.random_start = self.config.random_start
        self.seed = self.config.seed

        if self.seed is not None:
            np.random.seed(self.seed)

        # Chargement des données
        if self.data is None:
            self._generate_data()

        # Espaces d'action et d'état
        self.action_space = spaces.Box(
            low=np.array([-1.0, 0.0]),
            high=np.array([1.0, 1.0]),
            dtype=np.float32
        )

        # État: prix, indicateurs, position, balance
        state_dim = self._get_state_dim()
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(state_dim,),
            dtype=np.float32
        )

        # Initialisation
        self.reset()

    def _generate_data(self):
        """Génère des données synthétiques pour test"""
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=365),
            end=datetime.now(),
            freq='D'
        )

        n = len(dates)
        price = 10000 * np.cumprod(1 + np.random.normal(0, 0.02, n))
        volume = np.random.uniform(1000, 10000, n)

        self.data = pd.DataFrame({
            'date': dates,
            'open': price * (1 + np.random.uniform(-0.01, 0.01, n)),
            'high': price * (1 + np.random.uniform(0, 0.02, n)),
            'low': price * (1 + np.random.uniform(-0.02, 0, n)),
            'close': price,
            'volume': volume,
        })
        self.data.set_index('date', inplace=True)

    def _get_state_dim(self) -> int:
        """Calcule la dimension de l'état"""
        dim = 5  # price, position, balance, returns, volatility

        if self.use_technical_indicators:
            dim += 6  # MA5, MA10, MA20, RSI, MACD, BB

        if self.use_sentiment:
            dim += 1  # sentiment score

        return dim

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcule les indicateurs techniques"""
        indicators = {}

        if len(df) < 20:
            return {f'metric_{i}': 0.0 for i in range(6)}

        close = df['close'].values
        high = df['high'].values
        low = df['low'].values

        # Moving averages
        indicators['ma5'] = np.mean(close[-5:]) / close[-1] - 1
        indicators['ma10'] = np.mean(close[-10:]) / close[-1] - 1
        indicators['ma20'] = np.mean(close[-20:]) / close[-1] - 1

        # RSI
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.mean(gain[-14:]) if len(gain) >= 14 else 0
        avg_loss = np.mean(loss[-14:]) if len(loss) >= 14 else 0
        if avg_loss == 0:
            indicators['rsi'] = 50.0
        else:
            rs = avg_gain / avg_loss
            indicators['rsi'] = 100 - 100 / (1 + rs)

        # MACD
        if len(close) >= 26:
            ema12 = pd.Series(close).ewm(span=12).mean().values[-1]
            ema26 = pd.Series(close).ewm(span=26).mean().values[-1]
            indicators['macd'] = (ema12 - ema26) / close[-1]

        # Bollinger Bands
        if len(close) >= 20:
            std = np.std(close[-20:])
            indicators['bb'] = (close[-1] - np.mean(close[-20:])) / (std + 1e-6)

        return indicators

    def _get_state(self) -> np.ndarray:
        """Construit l'état actuel"""
        if len(self.data) < self.window_size + self.current_step:
            # Données insuffisantes
            return np.zeros(self.observation_space.shape)

        window = self.data.iloc[:self.current_step].tail(self.window_size)

        # Prix
        current_price = window['close'].iloc[-1]
        returns = window['close'].pct_change().values[-1] if len(window) > 1 else 0
        volatility = window['close'].pct_change().std() if len(window) > 1 else 0

        # État de base
        state = [
            current_price / 100000,  # normalisé
            self.position,
            self.balance / self.initial_balance,
            returns,
            volatility,
        ]

        # Indicateurs techniques
        if self.use_technical_indicators:
            indicators = self._calculate_technical_indicators(window)
            for key in ['ma5', 'ma10', 'ma20', 'rsi', 'macd', 'bb']:
                state.append(indicators.get(key, 0.0))

        # Sentiment
        if self.use_sentiment:
            # Simulé pour l'instant
            state.append(np.random.normal(0, 0.1))

        return np.array(state, dtype=np.float32)

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Réinitialise l'environnement.

        Args:
            seed: Seed pour la reproductibilité
            options: Options supplémentaires

        Returns:
            Tuple[np.ndarray, Dict[str, Any]]: (État, Informations)
        """
        super().reset(seed=seed)

        if seed is not None:
            np.random.seed(seed)

        # Position de départ aléatoire
        if self.random_start:
            self.current_step = np.random.randint(
                self.window_size,
                max(len(self.data) - self.max_steps, self.window_size + 1)
            )
        else:
            self.current_step = self.window_size

        self.position = 0.0
        self.balance = self.initial_balance
        self.step_count = 0
        self.portfolio_values = [self.initial_balance]
        self.actions = []

        state = self._get_state()
        info = {
            'step': self.step_count,
            'balance': self.balance,
            'position': self.position,
            'portfolio_value': self.balance,
        }

        return state, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Effectue une action dans l'environnement.

        Args:
            action: Action [position_change, stop_loss]

        Returns:
            Tuple: (state, reward, terminated, truncated, info)
        """
        self.step_count += 1

        # Interprétation de l'action
        position_change = np.clip(action[0], -1, 1)
        stop_loss = np.clip(action[1], 0, 1)

        # Mise à jour de la position
        old_position = self.position
        self.position += position_change * 0.1  # Taille du pas
        self.position = np.clip(self.position, -self.max_position, self.max_position)

        # Prix actuel
        current_price = self.data['close'].iloc[self.current_step]
        next_price = self.data['close'].iloc[self.current_step + 1] if self.current_step + 1 < len(self.data) else current_price

        # Calcul du P&L
        price_change = (next_price - current_price) / current_price
        pnl = self.position * price_change * self.balance

        # Coûts de transaction
        if self.position != old_position:
            trade_size = abs(self.position - old_position) * self.balance
            transaction_cost = trade_size * self.transaction_cost
            pnl -= transaction_cost

        # Stop loss
        if self.position != 0 and stop_loss > 0.5:
            price_change_stop = (next_price - current_price) / current_price
            if price_change_stop < -0.05:  # 5% stop loss
                pnl = -abs(self.position) * self.balance * 0.05

        # Mise à jour du solde
        self.balance += pnl
        self.balance = max(self.balance, 0)

        # Portfolio value
        portfolio_value = self.balance + self.position * self.balance
        self.portfolio_values.append(portfolio_value)

        # Récompense
        reward = pnl * self.reward_scaling
        if self.balance <= 0:
            reward = -1000  # Pénalité pour faillite

        # Mise à jour du step
        self.current_step += 1

        # Vérifications de fin
        terminated = self.balance <= 0 or self.step_count >= self.max_steps
        truncated = self.current_step >= len(self.data) - 1

        # État suivant
        state = self._get_state()

        # Informations
        info = {
            'step': self.step_count,
            'balance': self.balance,
            'position': self.position,
            'portfolio_value': portfolio_value,
            'pnl': pnl,
            'price': current_price,
            'action': action,
        }

        return state, reward, terminated, truncated, info

    def render(self, mode: str = 'human'):
        """
        Affiche l'état de l'environnement.
        """
        if mode == 'human':
            print(f"Step: {self.step_count}")
            print(f"Balance: {self.balance:.2f}")
            print(f"Position: {self.position:.2f}")
            print(f"Portfolio: {self.balance:.2f}")
            print("-" * 40)

    def close(self):
        """Ferme l'environnement"""
        pass

    def get_portfolio_history(self) -> List[float]:
        """
        Retourne l'historique du portefeuille.

        Returns:
            List[float]: Historique des valeurs du portefeuille
        """
        return self.portfolio_values

    def get_action_history(self) -> List[np.ndarray]:
        """
        Retourne l'historique des actions.

        Returns:
            List[np.ndarray]: Historique des actions
        """
        return self.actions


class DiscreteMarketEnv(MarketEnv):
    """Market Environment avec actions discrètes"""

    def __init__(
        self,
        config: Optional[MarketEnvConfig] = None,
        data: Optional[pd.DataFrame] = None
    ):
        super().__init__(config, data)

        # Action discrète: hold, buy, sell
        self.action_space = spaces.Discrete(3)

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Effectue une action discrète.

        Args:
            action: 0=hold, 1=buy, 2=sell

        Returns:
            Tuple: (state, reward, terminated, truncated, info)
        """
        # Conversion en action continue
        if action == 0:  # hold
            pos_change = 0
        elif action == 1:  # buy
            pos_change = 0.1
        else:  # sell
            pos_change = -0.1

        # Appel à l'étape parente
        return super().step(np.array([pos_change, 0.0]))


def create_market_env(
    symbol: str = "BTC-USD",
    window_size: int = 50,
    initial_balance: float = 10000.0,
    discrete: bool = False,
    **kwargs
) -> Union[MarketEnv, DiscreteMarketEnv]:
    """
    Factory pour créer un environnement de marché.

    Args:
        symbol: Symbole de l'actif
        window_size: Taille de la fenêtre
        initial_balance: Solde initial
        discrete: Actions discrètes ou continues
        **kwargs: Arguments supplémentaires

    Returns:
        Union[MarketEnv, DiscreteMarketEnv]: Environnement de marché
    """
    config = MarketEnvConfig(
        symbol=symbol,
        window_size=window_size,
        initial_balance=initial_balance,
        **kwargs
    )

    if discrete:
        return DiscreteMarketEnv(config)
    return MarketEnv(config)


__all__ = [
    'MarketEnv',
    'MarketEnvConfig',
    'DiscreteMarketEnv',
    'create_market_env',
]


# ai/reinforcement/environments/portfolio_env.py
"""
NEXUS AI TRADING SYSTEM - Portfolio Management Environment
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
    import gymnasium as gym
    from gymnasium import spaces
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PortfolioEnvConfig:
    """Configuration pour Portfolio Environment"""
    symbols: List[str] = field(default_factory=lambda: ["BTC-USD", "ETH-USD", "SOL-USD"])
    window_size: int = 50
    max_steps: int = 1000
    initial_balance: float = 10000.0
    transaction_cost: float = 0.001
    reward_scaling: float = 1.0
    max_asset_position: float = 0.5
    min_asset_position: float = 0.0
    use_technical_indicators: bool = True
    random_start: bool = True
    seed: Optional[int] = 42
    risk_free_rate: float = 0.02

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbols': self.symbols,
            'window_size': self.window_size,
            'max_steps': self.max_steps,
            'initial_balance': self.initial_balance,
            'transaction_cost': self.transaction_cost,
            'reward_scaling': self.reward_scaling,
            'max_asset_position': self.max_asset_position,
            'min_asset_position': self.min_asset_position,
            'use_technical_indicators': self.use_technical_indicators,
            'random_start': self.random_start,
            'seed': self.seed,
            'risk_free_rate': self.risk_free_rate,
        }


class PortfolioEnv(gym.Env):
    """
    Portfolio Management Environment for Reinforcement Learning.

    Features:
    - Multi-asset portfolio management
    - Allocation optimization
    - Realistic transaction costs
    - Risk management
    - Performance metrics (Sharpe, Sortino)

    Example:
        ```python
        config = PortfolioEnvConfig(
            symbols=['BTC-USD', 'ETH-USD', 'SOL-USD'],
            initial_balance=10000.0,
            transaction_cost=0.001
        )
        env = PortfolioEnv(config, data=data_dict)

        # Training loop
        state = env.reset()
        done = False
        while not done:
            action = agent.select_action(state)
            next_state, reward, done, info = env.step(action)
            state = next_state
        ```
    """

    metadata = {'render_modes': ['human'], 'render_fps': 30}

    def __init__(
        self,
        config: Optional[PortfolioEnvConfig] = None,
        data: Optional[Dict[str, pd.DataFrame]] = None
    ):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or PortfolioEnvConfig()
        self.data = data
        self.symbols = self.config.symbols
        self.n_assets = len(self.symbols)
        self.window_size = self.config.window_size
        self.max_steps = self.config.max_steps
        self.initial_balance = self.config.initial_balance
        self.transaction_cost = self.config.transaction_cost
        self.reward_scaling = self.config.reward_scaling
        self.max_asset_position = self.config.max_asset_position
        self.min_asset_position = self.config.min_asset_position
        self.use_technical_indicators = self.config.use_technical_indicators
        self.random_start = self.config.random_start
        self.seed = self.config.seed
        self.risk_free_rate = self.config.risk_free_rate

        if self.seed is not None:
            np.random.seed(self.seed)

        # Chargement des données
        if self.data is None:
            self._generate_data()

        # Vérification des données
        self._validate_data()

        # Espaces d'action et d'état
        # Action: allocation pour chaque actif (somme = 1)
        self.action_space = spaces.Box(
            low=np.array([self.min_asset_position] * self.n_assets),
            high=np.array([self.max_asset_position] * self.n_assets),
            dtype=np.float32
        )

        # État: prix, indicateurs, allocations, balance
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
        self.data = {}

        dates = pd.date_range(
            start=datetime.now() - timedelta(days=365),
            end=datetime.now(),
            freq='D'
        )

        for symbol in self.symbols:
            n = len(dates)
            base_price = np.random.uniform(100, 10000)
            drift = np.random.normal(0.0001, 0.02, n)
            price = base_price * np.cumprod(1 + drift)

            self.data[symbol] = pd.DataFrame({
                'date': dates,
                'open': price * (1 + np.random.uniform(-0.01, 0.01, n)),
                'high': price * (1 + np.random.uniform(0, 0.02, n)),
                'low': price * (1 + np.random.uniform(-0.02, 0, n)),
                'close': price,
                'volume': np.random.uniform(1000, 10000, n),
            })
            self.data[symbol].set_index('date', inplace=True)

    def _validate_data(self):
        """Valide les données d'entrée"""
        if self.data is None:
            raise ValueError("Les données ne peuvent pas être None")

        for symbol in self.symbols:
            if symbol not in self.data:
                raise ValueError(f"Données manquantes pour {symbol}")

            if len(self.data[symbol]) < self.window_size + 10:
                raise ValueError(f"Données insuffisantes pour {symbol}")

    def _get_state_dim(self) -> int:
        """Calcule la dimension de l'état"""
        # Prix normalisés pour chaque actif
        dim = self.n_assets * 3  # price, returns, volatility

        if self.use_technical_indicators:
            dim += self.n_assets * 4  # MA5, MA10, RSI, BB

        # Allocations et balance
        dim += self.n_assets + 1

        return dim

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcule les indicateurs techniques"""
        indicators = {}

        if len(df) < 20:
            return {f'metric_{i}': 0.0 for i in range(4)}

        close = df['close'].values

        indicators['ma5'] = np.mean(close[-5:]) / close[-1] - 1
        indicators['ma10'] = np.mean(close[-10:]) / close[-1] - 1

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

        if len(close) >= 20:
            std = np.std(close[-20:])
            indicators['bb'] = (close[-1] - np.mean(close[-20:])) / (std + 1e-6)

        return indicators

    def _get_state(self) -> np.ndarray:
        """Construit l'état actuel"""
        if self.current_step < self.window_size:
            return np.zeros(self.observation_space.shape)

        state = []

        for symbol in self.symbols:
            df = self.data[symbol]
            window = df.iloc[:self.current_step].tail(self.window_size)

            current_price = window['close'].iloc[-1]
            returns = window['close'].pct_change().values[-1] if len(window) > 1 else 0
            volatility = window['close'].pct_change().std() if len(window) > 1 else 0

            state.extend([current_price / 100000, returns, volatility])

            if self.use_technical_indicators:
                indicators = self._calculate_technical_indicators(window)
                for key in ['ma5', 'ma10', 'rsi', 'bb']:
                    state.append(indicators.get(key, 0.0))

        # Allocations actuelles
        state.extend(self.allocations)

        # Balance normalisée
        state.append(self.balance / self.initial_balance)

        return np.array(state, dtype=np.float32)

    def _calculate_portfolio_metrics(self) -> Dict[str, float]:
        """Calcule les métriques du portefeuille"""
        returns = np.diff(self.portfolio_values) / self.portfolio_values[:-1]

        if len(returns) < 2:
            return {'sharpe': 0, 'sortino': 0, 'max_drawdown': 0}

        # Sharpe ratio (annualisé)
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return > 0:
            sharpe = (avg_return - self.risk_free_rate / 252) / std_return * np.sqrt(252)
        else:
            sharpe = 0

        # Sortino ratio
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_std = np.std(negative_returns)
            if downside_std > 0:
                sortino = (avg_return - self.risk_free_rate / 252) / downside_std * np.sqrt(252)
            else:
                sortino = 0
        else:
            sortino = 0

        # Max drawdown
        cumulative = np.maximum.accumulate(self.portfolio_values)
        drawdown = (cumulative - self.portfolio_values) / cumulative
        max_drawdown = np.max(drawdown)

        return {'sharpe': sharpe, 'sortino': sortino, 'max_drawdown': max_drawdown}

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

        if self.random_start:
            self.current_step = np.random.randint(
                self.window_size,
                max(len(self.data[self.symbols[0]]) - self.max_steps, self.window_size + 1)
            )
        else:
            self.current_step = self.window_size

        self.balance = self.initial_balance
        self.allocations = np.array([1.0 / self.n_assets] * self.n_assets)
        self.asset_holdings = self.allocations * self.balance
        self.step_count = 0
        self.portfolio_values = [self.balance]
        self.actions = []

        # Prix initiaux
        self.current_prices = self._get_current_prices()

        state = self._get_state()
        info = {
            'step': self.step_count,
            'balance': self.balance,
            'allocations': self.allocations,
            'portfolio_value': self.balance,
        }

        return state, info

    def _get_current_prices(self) -> Dict[str, float]:
        """Retourne les prix actuels des actifs"""
        prices = {}
        for symbol in self.symbols:
            df = self.data[symbol]
            prices[symbol] = df['close'].iloc[self.current_step]
        return prices

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Effectue une action dans l'environnement.

        Args:
            action: Allocation pour chaque actif (somme = 1)

        Returns:
            Tuple: (state, reward, terminated, truncated, info)
        """
        self.step_count += 1

        # Normalisation de l'action
        action = np.clip(action, self.min_asset_position, self.max_asset_position)
        action = action / np.sum(action)  # Somme = 1

        old_allocations = self.allocations.copy()

        # Mise à jour des allocations avec coûts de transaction
        transaction_costs = np.sum(np.abs(action - old_allocations)) * self.transaction_cost * self.balance
        self.balance -= transaction_costs

        self.allocations = action
        self.asset_holdings = self.allocations * self.balance

        # Mise à jour du step et des prix
        self.current_step += 1
        new_prices = self._get_current_prices()

        # Calcul du P&L
        old_prices = self.current_prices
        price_returns = np.array([
            (new_prices[symbol] / old_prices[symbol] - 1)
            for symbol in self.symbols
        ])

        # Valeur du portefeuille
        asset_values = self.allocations * self.balance * (1 + price_returns)
        total_value = np.sum(asset_values)
        self.balance = total_value
        self.portfolio_values.append(total_value)

        # Récompense
        portfolio_return = (total_value - self.portfolio_values[-2]) / self.portfolio_values[-2] if len(self.portfolio_values) > 1 else 0
        reward = portfolio_return * self.reward_scaling

        # Pénalité pour concentration excessive
        concentration_penalty = np.std(self.allocations) * 0.1
        reward -= concentration_penalty

        self.current_prices = new_prices

        # Vérifications de fin
        terminated = self.balance <= 0 or self.step_count >= self.max_steps
        truncated = self.current_step >= len(self.data[self.symbols[0]]) - 1

        # Métriques
        metrics = self._calculate_portfolio_metrics()
        info = {
            'step': self.step_count,
            'balance': self.balance,
            'allocations': self.allocations,
            'portfolio_value': total_value,
            'portfolio_return': portfolio_return,
            'sharpe_ratio': metrics['sharpe'],
            'sortino_ratio': metrics['sortino'],
            'max_drawdown': metrics['max_drawdown'],
            'transaction_cost': transaction_costs,
        }

        state = self._get_state()

        return state, reward, terminated, truncated, info

    def render(self, mode: str = 'human'):
        """Affiche l'état de l'environnement"""
        if mode == 'human':
            print(f"Step: {self.step_count}")
            print(f"Balance: {self.balance:.2f}")
            print(f"Allocations: {dict(zip(self.symbols, self.allocations))}")
            print(f"Portfolio Value: {self.balance:.2f}")
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

    def get_allocation_history(self) -> List[np.ndarray]:
        """
        Retourne l'historique des allocations.

        Returns:
            List[np.ndarray]: Historique des allocations
        """
        return self.actions


def create_portfolio_env(
    symbols: List[str] = ["BTC-USD", "ETH-USD", "SOL-USD"],
    initial_balance: float = 10000.0,
    **kwargs
) -> PortfolioEnv:
    """
    Factory pour créer un environnement de portefeuille.

    Args:
        symbols: Liste des symboles
        initial_balance: Solde initial
        **kwargs: Arguments supplémentaires

    Returns:
        PortfolioEnv: Environnement de portefeuille
    """
    config = PortfolioEnvConfig(
        symbols=symbols,
        initial_balance=initial_balance,
        **kwargs
    )
    return PortfolioEnv(config)


__all__ = [
    'PortfolioEnv',
    'PortfolioEnvConfig',
    'create_portfolio_env',
]

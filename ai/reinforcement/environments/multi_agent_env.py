
# ai/reinforcement/environments/multi_agent_env.py
"""
NEXUS AI TRADING SYSTEM - Multi-Agent Market Environment
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
class AgentConfig:
    """Configuration pour un agent dans l'environnement multi-agents"""
    name: str
    initial_balance: float = 10000.0
    max_position: float = 1.0
    transaction_cost: float = 0.001
    strategy: str = 'random'  # 'random', 'momentum', 'mean_reversion', 'custom'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'initial_balance': self.initial_balance,
            'max_position': self.max_position,
            'transaction_cost': self.transaction_cost,
            'strategy': self.strategy,
        }


@dataclass
class MultiAgentEnvConfig:
    """Configuration pour Multi-Agent Market Environment"""
    symbol: str = "BTC-USD"
    window_size: int = 50
    max_steps: int = 1000
    agents: List[AgentConfig] = field(default_factory=list)
    use_technical_indicators: bool = True
    random_start: bool = True
    seed: Optional[int] = 42
    reward_scaling: float = 1.0
    competition_mode: bool = True
    cooperative_reward: float = 0.1

    def __post_init__(self):
        if not self.agents:
            self.agents = [
                AgentConfig(name="Agent_1"),
                AgentConfig(name="Agent_2"),
                AgentConfig(name="Agent_3"),
            ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'window_size': self.window_size,
            'max_steps': self.max_steps,
            'agents': [a.to_dict() for a in self.agents],
            'use_technical_indicators': self.use_technical_indicators,
            'random_start': self.random_start,
            'seed': self.seed,
            'reward_scaling': self.reward_scaling,
            'competition_mode': self.competition_mode,
            'cooperative_reward': self.cooperative_reward,
        }


class MultiAgentMarketEnv:
    """
    Multi-Agent Market Environment for Reinforcement Learning.

    Features:
    - Multiple trading agents
    - Competition and cooperation modes
    - Individual portfolio management
    - Shared market data
    - Agent-specific strategies

    Example:
        ```python
        agent_configs = [
            AgentConfig(name="Trader_1", strategy='momentum'),
            AgentConfig(name="Trader_2", strategy='mean_reversion'),
        ]
        config = MultiAgentEnvConfig(agents=agent_configs)
        env = MultiAgentMarketEnv(config, data=historical_data)

        # Training loop
        states = env.reset()
        done = False
        while not done:
            actions = {}
            for agent_id in env.agents:
                actions[agent_id] = agents[agent_id].select_action(states[agent_id])
            next_states, rewards, done, info = env.step(actions)
            states = next_states
        ```
    """

    metadata = {'render_modes': ['human'], 'render_fps': 30}

    def __init__(
        self,
        config: Optional[MultiAgentEnvConfig] = None,
        data: Optional[pd.DataFrame] = None
    ):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or MultiAgentEnvConfig()
        self.data = data
        self.window_size = self.config.window_size
        self.max_steps = self.config.max_steps
        self.use_technical_indicators = self.config.use_technical_indicators
        self.random_start = self.config.random_start
        self.seed = self.config.seed
        self.reward_scaling = self.config.reward_scaling
        self.competition_mode = self.config.competition_mode
        self.cooperative_reward = self.config.cooperative_reward

        if self.seed is not None:
            np.random.seed(self.seed)

        # Chargement des données
        if self.data is None:
            self._generate_data()

        # Initialisation des agents
        self.agents = {}
        self.agent_ids = []
        for agent_config in self.config.agents:
            self.agents[agent_config.name] = self._create_agent(agent_config)
            self.agent_ids.append(agent_config.name)

        # Espaces d'action et d'état
        self.action_spaces = {}
        self.observation_spaces = {}

        for agent_id in self.agent_ids:
            state_dim = self._get_state_dim()
            self.observation_spaces[agent_id] = spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=(state_dim,),
                dtype=np.float32
            )
            self.action_spaces[agent_id] = spaces.Box(
                low=np.array([-1.0, 0.0]),
                high=np.array([1.0, 1.0]),
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

    def _create_agent(self, agent_config: AgentConfig) -> Dict[str, Any]:
        """Crée un agent dans l'environnement"""
        return {
            'config': agent_config,
            'balance': agent_config.initial_balance,
            'position': 0.0,
            'portfolio_values': [agent_config.initial_balance],
            'rewards': [],
            'actions': [],
        }

    def _get_state_dim(self) -> int:
        """Calcule la dimension de l'état"""
        dim = 5  # price, position, balance, returns, volatility

        if self.use_technical_indicators:
            dim += 6  # MA5, MA10, MA20, RSI, MACD, BB

        return dim

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcule les indicateurs techniques"""
        indicators = {}

        if len(df) < 20:
            return {f'metric_{i}': 0.0 for i in range(6)}

        close = df['close'].values

        # Moving averages
        indicators['ma5'] = np.mean(close[-5:]) / close[-1] - 1
        indicators['ma10'] = np.mean(close[-10:]) / close[-1] - 1
        indicators['ma20'] = np.mean(close[-20:]) / close[-1] - 1

        # RSI (simplifié)
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

        # MACD simplifié
        if len(close) >= 26:
            ema12 = pd.Series(close).ewm(span=12).mean().values[-1]
            ema26 = pd.Series(close).ewm(span=26).mean().values[-1]
            indicators['macd'] = (ema12 - ema26) / close[-1]

        # Bollinger Bands
        if len(close) >= 20:
            std = np.std(close[-20:])
            indicators['bb'] = (close[-1] - np.mean(close[-20:])) / (std + 1e-6)

        return indicators

    def _get_agent_state(self, agent_id: str) -> np.ndarray:
        """Construit l'état pour un agent spécifique"""
        if len(self.data) < self.window_size + self.current_step:
            return np.zeros(self.observation_spaces[agent_id].shape)

        window = self.data.iloc[:self.current_step].tail(self.window_size)
        agent = self.agents[agent_id]

        current_price = window['close'].iloc[-1]
        returns = window['close'].pct_change().values[-1] if len(window) > 1 else 0
        volatility = window['close'].pct_change().std() if len(window) > 1 else 0

        state = [
            current_price / 100000,
            agent['position'],
            agent['balance'] / self.agents[agent_id]['config'].initial_balance,
            returns,
            volatility,
        ]

        if self.use_technical_indicators:
            indicators = self._calculate_technical_indicators(window)
            for key in ['ma5', 'ma10', 'ma20', 'rsi', 'macd', 'bb']:
                state.append(indicators.get(key, 0.0))

        return np.array(state, dtype=np.float32)

    def reset(
        self,
        seed: Optional[int] = None
    ) -> Dict[str, np.ndarray]:
        """
        Réinitialise l'environnement multi-agents.

        Args:
            seed: Seed pour la reproductibilité

        Returns:
            Dict[str, np.ndarray]: États des agents
        """
        if seed is not None:
            np.random.seed(seed)

        if self.random_start:
            self.current_step = np.random.randint(
                self.window_size,
                max(len(self.data) - self.max_steps, self.window_size + 1)
            )
        else:
            self.current_step = self.window_size

        self.step_count = 0

        # Réinitialisation des agents
        for agent_id, agent in self.agents.items():
            agent['balance'] = agent['config'].initial_balance
            agent['position'] = 0.0
            agent['portfolio_values'] = [agent['config'].initial_balance]
            agent['rewards'] = []
            agent['actions'] = []

        states = {}
        for agent_id in self.agent_ids:
            states[agent_id] = self._get_agent_state(agent_id)

        return states

    def step(
        self,
        actions: Dict[str, np.ndarray]
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, float], bool, Dict[str, Any]]:
        """
        Effectue des actions pour tous les agents.

        Args:
            actions: Dictionnaire des actions par agent

        Returns:
            Tuple: (states, rewards, done, info)
        """
        self.step_count += 1

        current_price = self.data['close'].iloc[self.current_step]
        next_price = self.data['close'].iloc[self.current_step + 1] if self.current_step + 1 < len(self.data) else current_price
        price_change = (next_price - current_price) / current_price

        rewards = {}
        total_pnl = 0.0
        total_positions = 0.0

        # Exécution des actions
        for agent_id in self.agent_ids:
            agent = self.agents[agent_id]
            action = actions.get(agent_id, np.array([0.0, 0.0]))

            position_change = np.clip(action[0], -1, 1)
            stop_loss = np.clip(action[1], 0, 1)

            old_position = agent['position']
            agent['position'] += position_change * 0.1
            agent['position'] = np.clip(
                agent['position'],
                -agent['config'].max_position,
                agent['config'].max_position
            )

            pnl = agent['position'] * price_change * agent['balance']

            if agent['position'] != old_position:
                trade_size = abs(agent['position'] - old_position) * agent['balance']
                pnl -= trade_size * agent['config'].transaction_cost

            if agent['position'] != 0 and stop_loss > 0.5:
                if price_change < -0.05:
                    pnl = -abs(agent['position']) * agent['balance'] * 0.05

            agent['balance'] += pnl
            agent['balance'] = max(agent['balance'], 0)

            portfolio_value = agent['balance'] + agent['position'] * agent['balance']
            agent['portfolio_values'].append(portfolio_value)

            reward = pnl * self.reward_scaling
            if agent['balance'] <= 0:
                reward = -1000

            agent['rewards'].append(reward)
            agent['actions'].append(action)

            rewards[agent_id] = reward
            total_pnl += pnl
            total_positions += abs(agent['position'])

        # Coopération / Compétition
        if self.competition_mode:
            # Récompense relative à la performance des autres
            avg_reward = np.mean(list(rewards.values()))
            for agent_id in self.agent_ids:
                rewards[agent_id] += (rewards[agent_id] - avg_reward) * 0.1
        else:
            # Récompense coopérative
            for agent_id in self.agent_ids:
                rewards[agent_id] += total_pnl * self.cooperative_reward / len(self.agent_ids)

        self.current_step += 1

        # États suivants
        states = {}
        for agent_id in self.agent_ids:
            states[agent_id] = self._get_agent_state(agent_id)

        done = (
            self.step_count >= self.max_steps or
            self.current_step >= len(self.data) - 1 or
            any(agent['balance'] <= 0 for agent in self.agents.values())
        )

        info = {
            'step': self.step_count,
            'prices': {'current': current_price, 'next': next_price},
            'total_pnl': total_pnl,
            'total_positions': total_positions,
            'agent_info': {
                agent_id: {
                    'balance': agent['balance'],
                    'position': agent['position'],
                    'portfolio_value': agent['balance'] + agent['position'] * agent['balance']
                }
                for agent_id, agent in self.agents.items()
            }
        }

        return states, rewards, done, info

    def render(self, mode: str = 'human'):
        """Affiche l'état de l'environnement"""
        if mode == 'human':
            print(f"Step: {self.step_count}")
            print("=" * 50)
            for agent_id, agent in self.agents.items():
                print(f"Agent: {agent_id}")
                print(f"  Balance: {agent['balance']:.2f}")
                print(f"  Position: {agent['position']:.2f}")
                print(f"  Portfolio: {agent['balance'] + agent['position'] * agent['balance']:.2f}")
            print("=" * 50)

    def close(self):
        """Ferme l'environnement"""
        pass

    def get_agent_portfolio_history(self, agent_id: str) -> List[float]:
        """
        Retourne l'historique du portefeuille d'un agent.

        Args:
            agent_id: ID de l'agent

        Returns:
            List[float]: Historique des valeurs du portefeuille
        """
        if agent_id in self.agents:
            return self.agents[agent_id]['portfolio_values']
        return []


def create_multi_agent_env(
    symbols: Optional[List[str]] = None,
    agent_configs: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> MultiAgentMarketEnv:
    """
    Factory pour créer un environnement multi-agents.

    Args:
        symbols: Liste des symboles (pour données multi-actifs)
        agent_configs: Configurations des agents
        **kwargs: Arguments supplémentaires

    Returns:
        MultiAgentMarketEnv: Environnement multi-agents
    """
    config = MultiAgentEnvConfig(**kwargs)

    if agent_configs:
        config.agents = [AgentConfig(**ac) for ac in agent_configs]

    return MultiAgentMarketEnv(config)


__all__ = [
    'MultiAgentMarketEnv',
    'MultiAgentEnvConfig',
    'AgentConfig',
    'create_multi_agent_env',
]

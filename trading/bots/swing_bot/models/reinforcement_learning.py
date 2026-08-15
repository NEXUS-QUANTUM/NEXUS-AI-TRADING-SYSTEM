"""
Swing Bot Reinforcement Learning Model
========================================

This module provides reinforcement learning models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import random
import warnings
warnings.filterwarnings('ignore')


@dataclass
class RLState:
    """Reinforcement learning state."""
    features: np.ndarray
    timestamp: datetime
    price: float
    position: int


@dataclass
class RLAction:
    """Reinforcement learning action."""
    action_type: str  # 'buy', 'sell', 'hold'
    quantity: float
    confidence: float


@dataclass
class RLExperience:
    """Reinforcement learning experience."""
    state: RLState
    action: RLAction
    reward: float
    next_state: RLState
    done: bool


@dataclass
class RLSignal:
    """Reinforcement learning trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class ReinforcementLearningModel:
    """
    Reinforcement learning model for trading.
    
    Implements Q-learning and policy gradient methods.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the reinforcement learning model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.learning_rate = self.config.get('learning_rate', 0.01)
        self.discount_factor = self.config.get('discount_factor', 0.95)
        self.exploration_rate = self.config.get('exploration_rate', 0.1)
        self.batch_size = self.config.get('batch_size', 32)
        self.memory_size = self.config.get('memory_size', 1000)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Experience replay
        self.memory: deque = deque(maxlen=self.memory_size)
        self.episode_count = 0
        self.total_reward = 0
        
        # State and action spaces
        self.state_dim = self.config.get('state_dim', 10)
        self.action_space = ['buy', 'sell', 'hold']
        
        # Q-table (simplified)
        self.q_table = {}
        self.learning_enabled = True
        
    def get_state(self, df: pd.DataFrame) -> RLState:
        """
        Extract state from market data.
        
        Args:
            df: OHLCV data
            
        Returns:
            RLState object
        """
        if len(df) < 20:
            return self._get_default_state()
        
        close = df['close'].values
        
        # Extract features
        features = np.array([
            close[-1] / close[-10] if len(close) >= 10 else 1,
            np.mean(close[-5:]) / close[-1] if len(close) >= 5 else 1,
            np.std(close[-5:]) / close[-1] if len(close) >= 5 else 0,
            (close[-1] - close[-2]) / close[-2] if len(close) >= 2 else 0,
            (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0,
            (close[-1] - close[-10]) / close[-10] if len(close) >= 10 else 0,
            np.mean(close[-3:]) / np.mean(close[-10:]) if len(close) >= 10 else 1,
            np.std(close[-3:]) / np.std(close[-10:]) if len(close) >= 10 else 1,
            (close[-1] - np.min(close[-10:])) / (np.max(close[-10:]) - np.min(close[-10:])) if len(close) >= 10 else 0.5,
            df['volume'].iloc[-1] / np.mean(df['volume'].values[-10:]) if len(df) >= 10 else 1
        ])
        
        return RLState(
            features=features,
            timestamp=datetime.now(),
            price=close[-1],
            position=0
        )
    
    def _get_default_state(self) -> RLState:
        """
        Get default state.
        
        Returns:
            Default RLState object
        """
        return RLState(
            features=np.zeros(self.state_dim),
            timestamp=datetime.now(),
            price=100.0,
            position=0
        )
    
    def get_action(self, state: RLState) -> RLAction:
        """
        Get action from policy.
        
        Args:
            state: Current state
            
        Returns:
            RLAction object
        """
        if self.learning_enabled and random.random() < self.exploration_rate:
            # Exploration
            action_type = random.choice(self.action_space)
            confidence = random.random()
        else:
            # Exploitation
            state_key = self._get_state_key(state)
            if state_key in self.q_table:
                q_values = self.q_table[state_key]
                best_action = max(q_values, key=q_values.get)
                action_type = best_action
                confidence = q_values[best_action]
            else:
                action_type = 'hold'
                confidence = 0.5
        
        # Calculate quantity
        quantity = self._calculate_quantity(state, action_type)
        
        return RLAction(
            action_type=action_type,
            quantity=quantity,
            confidence=confidence
        )
    
    def _get_state_key(self, state: RLState) -> str:
        """
        Get key for state.
        
        Args:
            state: State object
            
        Returns:
            State key string
        """
        # Discretize features for Q-table
        features = state.features
        discretized = [int(f * 10) for f in features[:5]]
        return '_'.join(str(d) for d in discretized)
    
    def _calculate_quantity(self, state: RLState, action_type: str) -> float:
        """
        Calculate position quantity.
        
        Args:
            state: Current state
            action_type: Action type
            
        Returns:
            Quantity
        """
        if action_type == 'buy':
            return 1.0
        elif action_type == 'sell':
            return -1.0
        else:
            return 0.0
    
    def update_q_table(self, experience: RLExperience) -> None:
        """
        Update Q-table with experience.
        
        Args:
            experience: RLExperience object
        """
        state_key = self._get_state_key(experience.state)
        next_state_key = self._get_state_key(experience.next_state)
        
        if state_key not in self.q_table:
            self.q_table[state_key] = {action: 0.0 for action in self.action_space}
        
        # Current Q-value
        current_q = self.q_table[state_key][experience.action.action_type]
        
        # Max Q-value for next state
        if next_state_key in self.q_table:
            max_next_q = max(self.q_table[next_state_key].values())
        else:
            max_next_q = 0.0
        
        # Q-learning update
        new_q = current_q + self.learning_rate * (
            experience.reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state_key][experience.action.action_type] = new_q
    
    def remember(self, experience: RLExperience) -> None:
        """
        Store experience in memory.
        
        Args:
            experience: RLExperience object
        """
        self.memory.append(experience)
    
    def replay(self) -> None:
        """Replay experiences for batch learning."""
        if len(self.memory) < self.batch_size:
            return
        
        batch = random.sample(self.memory, self.batch_size)
        
        for experience in batch:
            self.update_q_table(experience)
    
    def calculate_reward(self, state: RLState, action: RLAction,
                        next_state: RLState) -> float:
        """
        Calculate reward for action.
        
        Args:
            state: Current state
            action: Action taken
            next_state: Next state
            
        Returns:
            Reward value
        """
        # Price change
        price_change = (next_state.price - state.price) / state.price
        
        # Position based reward
        if action.action_type == 'buy':
            reward = price_change
        elif action.action_type == 'sell':
            reward = -price_change
        else:
            reward = 0.0
        
        # Add penalty for holding
        if action.action_type == 'hold' and abs(price_change) > 0.01:
            reward -= 0.01
        
        return reward
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[RLSignal]:
        """
        Generate trading signal using reinforcement learning.
        
        Args:
            df: OHLCV data
            
        Returns:
            RLSignal or None
        """
        if len(df) < 20:
            return None
        
        state = self.get_state(df)
        action = self.get_action(state)
        
        if action.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Generate signal
        if action.action_type == 'buy':
            signal_type = 'buy'
            reason = "RL model predicts buying opportunity"
            target = current_price * 1.02
            stop_loss = current_price * 0.98
        elif action.action_type == 'sell':
            signal_type = 'sell'
            reason = "RL model predicts selling opportunity"
            target = current_price * 0.98
            stop_loss = current_price * 1.02
        else:
            return None
        
        return RLSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=action.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators={
                'q_values': self.q_table.get(self._get_state_key(state), {}),
                'exploration_rate': self.exploration_rate,
                'episode': self.episode_count
            }
        )
    
    def train(self, df: pd.DataFrame) -> None:
        """
        Train RL model on data.
        
        Args:
            df: OHLCV data
            
        Returns:
            None
        """
        if len(df) < 50:
            return
        
        self.episode_count += 1
        
        # Iterate through data
        for i in range(20, len(df) - 1):
            # Get current and next state
            current_data = df.iloc[:i + 1]
            next_data = df.iloc[:i + 2]
            
            state = self.get_state(current_data)
            next_state = self.get_state(next_data)
            
            # Get action
            action = self.get_action(state)
            
            # Calculate reward
            reward = self.calculate_reward(state, action, next_state)
            
            # Store experience
            experience = RLExperience(
                state=state,
                action=action,
                reward=reward,
                next_state=next_state,
                done=(i == len(df) - 2)
            )
            self.remember(experience)
        
        # Replay experiences
        self.replay()
    
    def get_model_stats(self) -> Dict[str, Any]:
        """
        Get RL model statistics.
        
        Returns:
            Model statistics
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'episodes': self.episode_count,
            'memory_size': len(self.memory),
            'q_table_size': len(self.q_table),
            'exploration_rate': self.exploration_rate,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor,
            'total_reward': self.total_reward,
            'action_counts': {
                action: sum(1 for q in self.q_table.values() if q.get(action, 0) > 0)
                for action in self.action_space
            }
        }


def create_reinforcement_learning_model(config: Optional[Dict[str, Any]] = None) -> ReinforcementLearningModel:
    """
    Create a reinforcement learning model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ReinforcementLearningModel instance
    """
    return ReinforcementLearningModel(config)


__all__ = [
    'RLState',
    'RLAction',
    'RLExperience',
    'RLSignal',
    'ReinforcementLearningModel',
    'create_reinforcement_learning_model'
]

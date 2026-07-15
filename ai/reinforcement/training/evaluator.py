# ai/reinforcement/training/evaluator.py
"""
NEXUS AI TRADING SYSTEM - Training Evaluator Module
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

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EvaluatorConfig:
    """Configuration pour Evaluator"""
    evaluation_episodes: int = 10
    evaluation_frequency: int = 10
    render_eval: bool = False
    save_results: bool = True
    results_dir: str = "./evaluation_results"
    metrics: List[str] = field(default_factory=lambda: ['reward', 'sharpe', 'drawdown', 'win_rate'])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'evaluation_episodes': self.evaluation_episodes,
            'evaluation_frequency': self.evaluation_frequency,
            'render_eval': self.render_eval,
            'save_results': self.save_results,
            'results_dir': self.results_dir,
            'metrics': self.metrics,
        }


@dataclass
class EvaluationResult:
    """Résultat d'évaluation"""
    episode: int
    metrics: Dict[str, float]
    portfolio_values: List[float]
    returns: List[float]
    actions: List[Any]
    rewards: List[float]
    trades: List[Dict[str, Any]]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode': self.episode,
            'metrics': self.metrics,
            'portfolio_values': self.portfolio_values,
            'returns': self.returns,
            'actions': self.actions,
            'rewards': self.rewards,
            'trades': self.trades,
            'timestamp': self.timestamp.isoformat(),
        }


class Evaluator:
    """
    Évaluateur pour l'entraînement RL.

    Features:
    - Évaluation périodique
    - Métriques de performance
    - Visualisation
    - Sauvegarde des résultats
    - Comparaison des agents

    Example:
        ```python
        config = EvaluatorConfig(
            evaluation_episodes=10,
            evaluation_frequency=50,
            save_results=True
        )
        evaluator = Evaluator(config)

        # Évaluation
        results = evaluator.evaluate(agent, env)
        evaluator.save_results(results)
        ```
    """

    def __init__(self, config: Optional[EvaluatorConfig] = None):
        self.config = config or EvaluatorConfig()
        self.history: List[EvaluationResult] = []
        self.best_result: Optional[EvaluationResult] = None
        self.best_score = float('-inf')

        if self.config.save_results:
            os.makedirs(self.config.results_dir, exist_ok=True)

        logger.info(f"Evaluator initialisé")

    def evaluate(
        self,
        agent: Any,
        env: Any,
        n_episodes: Optional[int] = None
    ) -> EvaluationResult:
        """
        Évalue un agent sur plusieurs épisodes.

        Args:
            agent: Agent à évaluer
            env: Environnement
            n_episodes: Nombre d'épisodes (optionnel)

        Returns:
            EvaluationResult: Résultats de l'évaluation
        """
        n_episodes = n_episodes or self.config.evaluation_episodes

        all_rewards = []
        all_portfolio_values = []
        all_returns = []
        all_actions = []
        all_trades = []

        for episode in range(n_episodes):
            state = env.reset()
            done = False
            episode_rewards = []
            episode_portfolio_values = []
            episode_actions = []
            episode_trades = []

            while not done:
                action = agent.select_action(state)
                next_state, reward, done, info = env.step(action)

                episode_rewards.append(reward)
                episode_actions.append(action)

                if 'portfolio_value' in info:
                    episode_portfolio_values.append(info['portfolio_value'])
                elif hasattr(env, 'portfolio_values'):
                    episode_portfolio_values.append(env.portfolio_values[-1] if env.portfolio_values else 0)

                if done:
                    episode_trades = env.get_trade_history() if hasattr(env, 'get_trade_history') else []

                state = next_state

            all_rewards.append(np.sum(episode_rewards))
            all_portfolio_values.append(episode_portfolio_values)
            all_actions.append(episode_actions)
            all_trades.append(episode_trades)

        # Calcul des métriques
        metrics = self._compute_metrics(all_rewards, all_portfolio_values)

        # Résultat
        result = EvaluationResult(
            episode=len(self.history),
            metrics=metrics,
            portfolio_values=all_portfolio_values[-1] if all_portfolio_values else [],
            returns=np.diff(all_portfolio_values[-1]) / all_portfolio_values[-1][:-1] if len(all_portfolio_values) > 0 else [],
            actions=all_actions[-1] if all_actions else [],
            rewards=all_rewards,
            trades=all_trades[-1] if all_trades else [],
        )

        self.history.append(result)

        # Meilleur résultat
        score = metrics.get('reward', 0)
        if score > self.best_score:
            self.best_score = score
            self.best_result = result

        logger.info(f"Évaluation {len(self.history)}: Reward={metrics.get('reward', 0):.2f}, Sharpe={metrics.get('sharpe', 0):.2f}")

        return result

    def _compute_metrics(
        self,
        rewards: List[float],
        portfolio_values: List[List[float]]
    ) -> Dict[str, float]:
        """Calcule les métriques d'évaluation"""
        metrics = {}

        # Récompense moyenne
        metrics['reward'] = np.mean(rewards)
        metrics['reward_std'] = np.std(rewards)
        metrics['reward_max'] = np.max(rewards)
        metrics['reward_min'] = np.min(rewards)

        # Rendements
        if portfolio_values and portfolio_values[0]:
            returns = np.diff(portfolio_values[0]) / portfolio_values[0][:-1]

            if len(returns) > 1:
                # Sharpe Ratio
                mean_return = np.mean(returns)
                std_return = np.std(returns) + 1e-6
                metrics['sharpe'] = mean_return / std_return * np.sqrt(252)

                # Drawdown
                cumulative = np.cumprod(1 + returns)
                peak = np.maximum.accumulate(cumulative)
                drawdown = (peak - cumulative) / peak
                metrics['max_drawdown'] = np.max(drawdown)
                metrics['avg_drawdown'] = np.mean(drawdown)

                # Win rate
                win_rate = np.mean(returns > 0)
                metrics['win_rate'] = win_rate

                # Profit factor
                gains = np.sum(returns[returns > 0])
                losses = np.abs(np.sum(returns[returns < 0])) + 1e-6
                metrics['profit_factor'] = gains / losses

        return metrics

    def get_best_result(self) -> Optional[EvaluationResult]:
        """Retourne le meilleur résultat"""
        return self.best_result

    def get_history(self) -> pd.DataFrame:
        """
        Retourne l'historique des évaluations.

        Returns:
            pd.DataFrame: Historique
        """
        data = []
        for result in self.history:
            row = {'episode': result.episode}
            row.update(result.metrics)
            data.append(row)
        return pd.DataFrame(data)

    def plot_results(self, figsize: Tuple[int, int] = (12, 8)):
        """
        Affiche les résultats des évaluations.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        df = self.get_history()

        fig, axes = plt.subplots(2, 2, figsize=figsize)

        # Reward
        axes[0, 0].plot(df['episode'], df['reward'], 'b-', label='Reward')
        axes[0, 0].fill_between(
            df['episode'],
            df['reward'] - df['reward_std'],
            df['reward'] + df['reward_std'],
            alpha=0.2,
            color='blue'
        )
        axes[0, 0].set_xlabel('Évaluation')
        axes[0, 0].set_ylabel('Récompense')
        axes[0, 0].set_title('Récompense moyenne')
        axes[0, 0].grid(True, alpha=0.3)

        # Sharpe
        if 'sharpe' in df.columns:
            axes[0, 1].plot(df['episode'], df['sharpe'], 'g-', label='Sharpe')
            axes[0, 1].set_xlabel('Évaluation')
            axes[0, 1].set_ylabel('Sharpe Ratio')
            axes[0, 1].set_title('Sharpe Ratio')
            axes[0, 1].grid(True, alpha=0.3)
            axes[0, 1].axhline(y=0, color='r', linestyle='--')

        # Drawdown
        if 'max_drawdown' in df.columns:
            axes[1, 0].plot(df['episode'], df['max_drawdown'], 'r-', label='Max Drawdown')
            axes[1, 0].set_xlabel('Évaluation')
            axes[1, 0].set_ylabel('Drawdown')
            axes[1, 0].set_title('Drawdown maximum')
            axes[1, 0].grid(True, alpha=0.3)

        # Win Rate
        if 'win_rate' in df.columns:
            axes[1, 1].plot(df['episode'], df['win_rate'], 'm-', label='Win Rate')
            axes[1, 1].set_xlabel('Évaluation')
            axes[1, 1].set_ylabel('Win Rate')
            axes[1, 1].set_title('Taux de réussite')
            axes[1, 1].grid(True, alpha=0.3)
            axes[1, 1].axhline(y=0.5, color='r', linestyle='--')

        plt.tight_layout()
        plt.show()

    def save_results(self, filepath: Optional[str] = None):
        """
        Sauvegarde les résultats.

        Args:
            filepath: Chemin du fichier (optionnel)
        """
        if not self.config.save_results:
            return

        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = os.path.join(self.config.results_dir, f"evaluation_{timestamp}.pkl")

        try:
            data = {
                'config': self.config.to_dict(),
                'history': [r.to_dict() for r in self.history],
                'best_result': self.best_result.to_dict() if self.best_result else None,
                'timestamp': datetime.now().isoformat(),
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Résultats sauvegardés: {filepath}")

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")


def create_evaluator(
    evaluation_episodes: int = 10,
    evaluation_frequency: int = 10,
    **kwargs
) -> Evaluator:
    """
    Factory pour créer un évaluateur.

    Args:
        evaluation_episodes: Nombre d'épisodes d'évaluation
        evaluation_frequency: Fréquence d'évaluation
        **kwargs: Arguments supplémentaires

    Returns:
        Evaluator: Évaluateur
    """
    config = EvaluatorConfig(
        evaluation_episodes=evaluation_episodes,
        evaluation_frequency=evaluation_frequency,
        **kwargs
    )
    return Evaluator(config)


__all__ = [
    'Evaluator',
    'EvaluatorConfig',
    'EvaluationResult',
    'create_evaluator',
]

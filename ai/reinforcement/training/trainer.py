# ai/reinforcement/training/trainer.py
"""
NEXUS AI TRADING SYSTEM - Reinforcement Learning Trainer
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time
import warnings
warnings.filterwarnings('ignore')

from ai.reinforcement.training.checkpoint import CheckpointManager, CheckpointConfig
from ai.reinforcement.training.evaluator import Evaluator, EvaluatorConfig
from ai.reinforcement.training.logger import TrainingLogger, LoggerConfig

logger = logging.getLogger(__name__)


@dataclass
class TrainerConfig:
    """Configuration pour Trainer"""
    n_episodes: int = 1000
    max_steps_per_episode: int = 1000
    eval_frequency: int = 50
    save_frequency: int = 100
    log_frequency: int = 10
    render_training: bool = False
    render_eval: bool = False
    seed: Optional[int] = 42
    use_gpu: bool = False
    verbose: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_episodes': self.n_episodes,
            'max_steps_per_episode': self.max_steps_per_episode,
            'eval_frequency': self.eval_frequency,
            'save_frequency': self.save_frequency,
            'log_frequency': self.log_frequency,
            'render_training': self.render_training,
            'render_eval': self.render_eval,
            'seed': self.seed,
            'use_gpu': self.use_gpu,
            'verbose': self.verbose,
        }


class Trainer:
    """
    Entraîneur pour l'apprentissage par renforcement.

    Features:
    - Boucle d'entraînement complète
    - Évaluation périodique
    - Checkpoints
    - Logging
    - Visualisation
    - Gestion des seeds

    Example:
        ```python
        config = TrainerConfig(
            n_episodes=1000,
            eval_frequency=50,
            save_frequency=100
        )
        trainer = Trainer(config)

        trainer.train(agent, env, eval_env)
        ```
    """

    def __init__(self, config: Optional[TrainerConfig] = None):
        self.config = config or TrainerConfig()

        # Initialisation des composants
        self.checkpoint_manager = CheckpointManager(
            CheckpointConfig(
                save_frequency=self.config.save_frequency,
                save_best_only=True
            )
        )

        self.evaluator = Evaluator(
            EvaluatorConfig(
                evaluation_episodes=10,
                evaluation_frequency=self.config.eval_frequency,
                render_eval=self.config.render_eval
            )
        )

        self.logger = TrainingLogger(
            LoggerConfig(
                log_frequency=self.config.log_frequency
            )
        )

        self.history = {
            'episodes': [],
            'rewards': [],
            'losses': [],
            'eval_rewards': [],
        }

        self.start_time = None
        self.total_steps = 0

        if self.config.seed is not None:
            np.random.seed(self.config.seed)
            try:
                import torch
                torch.manual_seed(self.config.seed)
            except ImportError:
                pass

        logger.info(f"Trainer initialisé")

    def train(
        self,
        agent: Any,
        train_env: Any,
        eval_env: Optional[Any] = None,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Entraîne un agent.

        Args:
            agent: Agent à entraîner
            train_env: Environnement d'entraînement
            eval_env: Environnement d'évaluation (optionnel)
            callback: Fonction de callback

        Returns:
            Dict[str, Any]: Historique de l'entraînement
        """
        self.start_time = time.time()

        logger.info(f"Début de l'entraînement pour {self.config.n_episodes} épisodes")

        for episode in range(1, self.config.n_episodes + 1):
            # Réinitialisation
            state = train_env.reset()
            done = False
            episode_reward = 0
            episode_loss = 0
            steps = 0

            # Boucle d'épisode
            while not done and steps < self.config.max_steps_per_episode:
                # Sélection de l'action
                action = agent.select_action(state)

                # Exécution
                next_state, reward, done, info = train_env.step(action)

                # Stockage de la transition
                agent.store_transition(state, action, reward, next_state, done)

                # Mise à jour de l'agent
                loss = agent.update()
                if loss is not None:
                    if isinstance(loss, dict):
                        episode_loss += loss.get('total_loss', 0)
                    else:
                        episode_loss += loss

                # Mise à jour
                state = next_state
                episode_reward += reward
                steps += 1
                self.total_steps += 1

                if self.config.render_training:
                    train_env.render()

            # Fin d'épisode
            self.history['episodes'].append(episode)
            self.history['rewards'].append(episode_reward)
            self.history['losses'].append(episode_loss / max(steps, 1))

            # Logging
            if episode % self.config.log_frequency == 0:
                self._log_episode(episode, episode_reward, episode_loss / max(steps, 1))

            # Évaluation
            if episode % self.config.eval_frequency == 0:
                eval_result = self._evaluate(agent, eval_env or train_env)
                self.history['eval_rewards'].append(eval_result.metrics.get('reward', 0))
                self.logger.log_metrics(episode, eval_result.metrics, prefix='eval')

            # Sauvegarde
            if episode % self.config.save_frequency == 0:
                self._save_checkpoint(agent, episode)

            # Callback
            if callback is not None:
                callback(episode, episode_reward, self.history)

        # Fin de l'entraînement
        training_time = time.time() - self.start_time

        self.logger.log_metrics(self.config.n_episodes, {
            'total_time': training_time,
            'total_steps': self.total_steps,
        })

        # Sauvegarde finale
        self._save_checkpoint(agent, self.config.n_episodes)
        self.logger.save()

        logger.info(f"Entraînement terminé en {training_time:.2f}s")
        logger.info(f"Meilleur épisode: {self._get_best_episode()}")

        return self.history

    def _evaluate(self, agent: Any, env: Any) -> Any:
        """Évalue l'agent"""
        return self.evaluator.evaluate(agent, env)

    def _save_checkpoint(self, agent: Any, episode: int):
        """Sauvegarde un checkpoint"""
        metrics = {
            'reward': self.history['rewards'][-1] if self.history['rewards'] else 0,
            'loss': self.history['losses'][-1] if self.history['losses'] else 0,
        }

        if self.history['eval_rewards']:
            metrics['eval_reward'] = self.history['eval_rewards'][-1]

        self.checkpoint_manager.save(agent, episode, self.total_steps, metrics)

    def _log_episode(self, episode: int, reward: float, loss: float):
        """Log un épisode"""
        metrics = {
            'reward': reward,
            'loss': loss,
            'steps': self.total_steps,
            'time': time.time() - self.start_time,
        }

        self.logger.log_metrics(episode, metrics)

        if self.config.verbose:
            logger.info(f"Episode {episode}: Reward={reward:.2f}, Loss={loss:.4f}")

    def _get_best_episode(self) -> Dict[str, Any]:
        """Retourne le meilleur épisode"""
        if not self.history['rewards']:
            return {}

        best_idx = np.argmax(self.history['rewards'])
        return {
            'episode': self.history['episodes'][best_idx],
            'reward': self.history['rewards'][best_idx],
            'loss': self.history['losses'][best_idx],
        }

    def get_history(self) -> Dict[str, List[float]]:
        """Retourne l'historique"""
        return self.history

    def plot_results(self):
        """Affiche les résultats"""
        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(2, 2, figsize=(12, 8))

            # Reward
            axes[0, 0].plot(self.history['episodes'], self.history['rewards'])
            axes[0, 0].set_xlabel('Episode')
            axes[0, 0].set_ylabel('Reward')
            axes[0, 0].set_title('Training Reward')
            axes[0, 0].grid(True, alpha=0.3)

            # Loss
            axes[0, 1].plot(self.history['episodes'], self.history['losses'])
            axes[0, 1].set_xlabel('Episode')
            axes[0, 1].set_ylabel('Loss')
            axes[0, 1].set_title('Training Loss')
            axes[0, 1].grid(True, alpha=0.3)

            # Eval Reward
            if self.history['eval_rewards']:
                axes[1, 0].plot(
                    self.history['episodes'][::self.config.eval_frequency],
                    self.history['eval_rewards']
                )
                axes[1, 0].set_xlabel('Episode')
                axes[1, 0].set_ylabel('Eval Reward')
                axes[1, 0].set_title('Evaluation Reward')
                axes[1, 0].grid(True, alpha=0.3)

            # Cumulative Reward
            cumulative = np.cumsum(self.history['rewards'])
            axes[1, 1].plot(self.history['episodes'], cumulative)
            axes[1, 1].set_xlabel('Episode')
            axes[1, 1].set_ylabel('Cumulative Reward')
            axes[1, 1].set_title('Cumulative Reward')
            axes[1, 1].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except ImportError:
            logger.warning("Matplotlib non disponible")


def create_trainer(
    n_episodes: int = 1000,
    eval_frequency: int = 50,
    save_frequency: int = 100,
    **kwargs
) -> Trainer:
    """
    Factory pour créer un entraîneur.

    Args:
        n_episodes: Nombre d'épisodes
        eval_frequency: Fréquence d'évaluation
        save_frequency: Fréquence de sauvegarde
        **kwargs: Arguments supplémentaires

    Returns:
        Trainer: Entraîneur
    """
    config = TrainerConfig(
        n_episodes=n_episodes,
        eval_frequency=eval_frequency,
        save_frequency=save_frequency,
        **kwargs
    )
    return Trainer(config)


__all__ = [
    'Trainer',
    'TrainerConfig',
    'create_trainer',
]

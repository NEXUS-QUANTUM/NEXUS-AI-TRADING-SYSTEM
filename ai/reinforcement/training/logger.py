# ai/reinforcement/training/logger.py
"""
NEXUS AI TRADING SYSTEM - Training Logger Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import os
import json
import csv
from typing import Optional, List, Dict, Any, Union
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
class LoggerConfig:
    """Configuration pour Logger"""
    log_dir: str = "./logs"
    log_level: str = "INFO"
    save_metrics: bool = True
    save_plots: bool = True
    log_frequency: int = 1
    max_log_files: int = 10
    use_tensorboard: bool = False
    use_wandb: bool = False
    wandb_project: Optional[str] = None
    wandb_entity: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'log_dir': self.log_dir,
            'log_level': self.log_level,
            'save_metrics': self.save_metrics,
            'save_plots': self.save_plots,
            'log_frequency': self.log_frequency,
            'max_log_files': self.max_log_files,
            'use_tensorboard': self.use_tensorboard,
            'use_wandb': self.use_wandb,
            'wandb_project': self.wandb_project,
            'wandb_entity': self.wandb_entity,
        }


class TrainingLogger:
    """
    Logger pour l'entraînement RL.

    Features:
    - Logging des métriques
    - Sauvegarde des graphiques
    - Support TensorBoard
    - Support Weights & Biases
    - Export CSV

    Example:
        ```python
        config = LoggerConfig(
            log_dir="./runs/exp1/logs",
            save_metrics=True,
            save_plots=True
        )
        logger = TrainingLogger(config)

        # Logging
        logger.log_metrics(episode, metrics)
        logger.log_plot(episode, data)
        logger.save()
        ```
    """

    def __init__(self, config: Optional[LoggerConfig] = None):
        self.config = config or LoggerConfig()
        self.metrics_history: List[Dict[str, Any]] = []
        self.plot_history: List[Dict[str, Any]] = []

        # Création du répertoire
        os.makedirs(self.config.log_dir, exist_ok=True)

        # Configuration du logging
        self._setup_logging()

        # Initialisation de TensorBoard
        if self.config.use_tensorboard:
            self._init_tensorboard()

        # Initialisation de Weights & Biases
        if self.config.use_wandb:
            self._init_wandb()

        logger.info(f"TrainingLogger initialisé: {self.config.log_dir}")

    def _setup_logging(self):
        """Configure le logging"""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)

        log_file = os.path.join(self.config.log_dir, "training.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Ajout des handlers au logger root
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    def _init_tensorboard(self):
        """Initialise TensorBoard"""
        try:
            from torch.utils.tensorboard import SummaryWriter
            self.writer = SummaryWriter(self.config.log_dir)
            logger.info("TensorBoard initialisé")
        except ImportError:
            logger.warning("TensorBoard non disponible")

    def _init_wandb(self):
        """Initialise Weights & Biases"""
        try:
            import wandb
            wandb.init(
                project=self.config.wandb_project,
                entity=self.config.wandb_entity,
                dir=self.config.log_dir,
                config=self.config.to_dict(),
            )
            self.wandb = wandb
            logger.info("Weights & Biases initialisé")
        except ImportError:
            logger.warning("Weights & Biases non disponible")

    def log_metrics(self, episode: int, metrics: Dict[str, float], **kwargs):
        """
        Log des métriques.

        Args:
            episode: Épisode
            metrics: Métriques
            **kwargs: Données supplémentaires
        """
        data = {
            'episode': episode,
            'timestamp': datetime.now().isoformat(),
            **metrics,
            **kwargs
        }

        self.metrics_history.append(data)

        # TensorBoard
        if hasattr(self, 'writer'):
            for key, value in metrics.items():
                self.writer.add_scalar(key, value, episode)

        # Weights & Biases
        if hasattr(self, 'wandb'):
            self.wandb.log({**metrics, 'episode': episode}, step=episode)

    def log_plot(self, name: str, data: Dict[str, Any], episode: Optional[int] = None):
        """
        Log d'un graphique.

        Args:
            name: Nom du graphique
            data: Données
            episode: Épisode (optionnel)
        """
        self.plot_history.append({
            'name': name,
            'data': data,
            'episode': episode,
            'timestamp': datetime.now().isoformat(),
        })

    def log_agent(self, agent: Any, episode: int):
        """
        Log des informations de l'agent.

        Args:
            agent: Agent
            episode: Épisode
        """
        if hasattr(agent, 'get_metrics'):
            metrics = agent.get_metrics()
            self.log_metrics(episode, {f'agent_{k}': v for k, v in metrics.items()})

    def log_env(self, env: Any, episode: int):
        """
        Log des informations de l'environnement.

        Args:
            env: Environnement
            episode: Épisode
        """
        if hasattr(env, 'get_stats'):
            stats = env.get_stats()
            self.log_metrics(episode, {f'env_{k}': v for k, v in stats.items()})

    def get_metrics(self) -> pd.DataFrame:
        """
        Retourne les métriques sous forme de DataFrame.

        Returns:
            pd.DataFrame: Métriques
        """
        import pandas as pd
        return pd.DataFrame(self.metrics_history)

    def save(self):
        """Sauvegarde les logs"""
        # Sauvegarde des métriques
        if self.config.save_metrics:
            self._save_metrics()

        # Sauvegarde des graphiques
        if self.config.save_plots:
            self._save_plots()

        # Sauvegarde de la configuration
        self._save_config()

        # Rotation des logs
        self._rotate_logs()

        logger.info("Logs sauvegardés")

    def _save_metrics(self):
        """Sauvegarde les métriques en CSV"""
        if not self.metrics_history:
            return

        import pandas as pd
        df = pd.DataFrame(self.metrics_history)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(self.config.log_dir, f"metrics_{timestamp}.csv")
        df.to_csv(filepath, index=False)

        # Garder uniquement les fichiers récents
        self._cleanup_old_files('*.csv')

    def _save_plots(self):
        """Sauvegarde les graphiques"""
        if not MATPLOTLIB_AVAILABLE:
            return

        for plot in self.plot_history:
            name = plot['name']
            data = plot['data']

            # Création du graphique
            fig, ax = plt.subplots(figsize=(10, 6))

            if 'values' in data:
                ax.plot(data['values'], label=name)
            elif 'x' in data and 'y' in data:
                ax.plot(data['x'], data['y'], label=name)

            ax.set_xlabel('Time')
            ax.set_ylabel('Value')
            ax.set_title(name)
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Sauvegarde
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = os.path.join(self.config.log_dir, f"plot_{name}_{timestamp}.png")
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()

    def _save_config(self):
        """Sauvegarde la configuration"""
        config_file = os.path.join(self.config.log_dir, "config.json")
        with open(config_file, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=2)

    def _rotate_logs(self):
        """Rotation des fichiers de log"""
        # Nettoyage des fichiers CSV
        self._cleanup_old_files('*.csv')

        # Nettoyage des images
        self._cleanup_old_files('*.png')

    def _cleanup_old_files(self, pattern: str):
        """Supprime les fichiers les plus anciens"""
        import glob
        files = glob.glob(os.path.join(self.config.log_dir, pattern))

        if len(files) > self.config.max_log_files:
            files.sort(key=os.path.getmtime)
            for f in files[:-self.config.max_log_files]:
                os.remove(f)

    def close(self):
        """Ferme le logger"""
        # Fermeture de TensorBoard
        if hasattr(self, 'writer'):
            self.writer.close()

        # Fermeture de Weights & Biases
        if hasattr(self, 'wandb'):
            self.wandb.finish()


def create_training_logger(
    log_dir: str = "./logs",
    save_metrics: bool = True,
    save_plots: bool = True,
    **kwargs
) -> TrainingLogger:
    """
    Factory pour créer un logger d'entraînement.

    Args:
        log_dir: Répertoire des logs
        save_metrics: Sauvegarder les métriques
        save_plots: Sauvegarder les graphiques
        **kwargs: Arguments supplémentaires

    Returns:
        TrainingLogger: Logger d'entraînement
    """
    config = LoggerConfig(
        log_dir=log_dir,
        save_metrics=save_metrics,
        save_plots=save_plots,
        **kwargs
    )
    return TrainingLogger(config)


__all__ = [
    'TrainingLogger',
    'LoggerConfig',
    'create_training_logger',
]

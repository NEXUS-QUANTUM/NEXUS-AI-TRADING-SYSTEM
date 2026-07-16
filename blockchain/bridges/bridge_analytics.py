
# blockchain/bridges/bridge_analytics.py
"""
NEXUS AI TRADING SYSTEM - Bridge Analytics Module
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
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BridgeAnalyticsConfig:
    """Configuration pour Bridge Analytics"""
    name: str = "bridge_analytics"
    window_size: int = 24  # heures
    confidence_level: float = 0.95
    metrics: List[str] = field(default_factory=lambda: ['volume', 'fee', 'latency', 'success_rate'])
    timezone: str = "UTC"
    save_plots: bool = False
    plot_dir: str = "./bridge_analytics"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'window_size': self.window_size,
            'confidence_level': self.confidence_level,
            'metrics': self.metrics,
            'timezone': self.timezone,
            'save_plots': self.save_plots,
            'plot_dir': self.plot_dir,
        }


@dataclass
class BridgeStatistics:
    """Statistiques du bridge"""
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    success_rate: float
    total_volume: float
    average_volume: float
    max_volume: float
    min_volume: float
    total_fees: float
    average_fee: float
    max_fee: float
    min_fee: float
    average_latency: float
    max_latency: float
    min_latency: float
    throughput: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_transactions': self.total_transactions,
            'successful_transactions': self.successful_transactions,
            'failed_transactions': self.failed_transactions,
            'success_rate': self.success_rate,
            'total_volume': self.total_volume,
            'average_volume': self.average_volume,
            'max_volume': self.max_volume,
            'min_volume': self.min_volume,
            'total_fees': self.total_fees,
            'average_fee': self.average_fee,
            'max_fee': self.max_fee,
            'min_fee': self.min_fee,
            'average_latency': self.average_latency,
            'max_latency': self.max_latency,
            'min_latency': self.min_latency,
            'throughput': self.throughput,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class BridgeAlert:
    """Alerte du bridge"""
    timestamp: datetime
    severity: str  # 'info', 'warning', 'critical'
    metric: str
    value: float
    threshold: float
    message: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity,
            'metric': self.metric,
            'value': self.value,
            'threshold': self.threshold,
            'message': self.message,
            'details': self.details,
        }


class BridgeAnalytics:
    """
    Analytics pour les bridges blockchain.

    Features:
    - Métriques de performance
    - Analyse de volume
    - Analyse des frais
    - Analyse de latence
    - Alertes
    - Visualisation

    Example:
        ```python
        config = BridgeAnalyticsConfig(
            name='analytics',
            window_size=24,
            metrics=['volume', 'fee', 'latency']
        )
        analytics = BridgeAnalytics(config)

        # Mise à jour des données
        analytics.update(transaction_data)

        # Statistiques
        stats = analytics.get_statistics()

        # Alertes
        alerts = analytics.check_alerts()
        ```
    """

    def __init__(self, config: Optional[BridgeAnalyticsConfig] = None):
        self.config = config or BridgeAnalyticsConfig()
        self.data: List[Dict[str, Any]] = []
        self.statistics: Dict[str, BridgeStatistics] = {}
        self.alerts: List[BridgeAlert] = []

        if self.config.save_plots:
            import os
            os.makedirs(self.config.plot_dir, exist_ok=True)

        logger.info(f"BridgeAnalytics initialisé")

    def update(self, transactions: List[Dict[str, Any]]) -> None:
        """
        Met à jour les données d'analyse.

        Args:
            transactions: Liste des transactions
        """
        self.data.extend(transactions)

        # Garder seulement les données récentes
        cutoff = datetime.now() - timedelta(hours=self.config.window_size)
        self.data = [tx for tx in self.data if tx.get('timestamp', datetime.now()) >= cutoff]

        # Mise à jour des statistiques
        self._update_statistics()

        # Vérification des alertes
        self._check_alerts()

        logger.info(f"Données mises à jour: {len(self.data)} transactions")

    def _update_statistics(self) -> None:
        """Met à jour les statistiques"""
        if not self.data:
            return

        # Statistiques globales
        total_tx = len(self.data)
        successful = sum(1 for tx in self.data if tx.get('status') == 'confirmed')
        failed = total_tx - successful

        volumes = [tx.get('value', 0) for tx in self.data]
        fees = [tx.get('gas_price', 0) * tx.get('gas_used', 0) / 1e18 for tx in self.data]
        latencies = [tx.get('latency', 0) for tx in self.data]

        stats = BridgeStatistics(
            total_transactions=total_tx,
            successful_transactions=successful,
            failed_transactions=failed,
            success_rate=successful / total_tx if total_tx > 0 else 0,
            total_volume=sum(volumes),
            average_volume=np.mean(volumes) if volumes else 0,
            max_volume=max(volumes) if volumes else 0,
            min_volume=min(volumes) if volumes else 0,
            total_fees=sum(fees),
            average_fee=np.mean(fees) if fees else 0,
            max_fee=max(fees) if fees else 0,
            min_fee=min(fees) if fees else 0,
            average_latency=np.mean(latencies) if latencies else 0,
            max_latency=max(latencies) if latencies else 0,
            min_latency=min(latencies) if latencies else 0,
            throughput=total_tx / self.config.window_size if self.config.window_size > 0 else 0,
            timestamp=datetime.now(),
        )

        self.statistics['global'] = stats

        # Statistiques par direction
        for direction in ['L1_TO_L2', 'L2_TO_L1']:
            dir_tx = [tx for tx in self.data if tx.get('direction') == direction]
            if dir_tx:
                dir_stats = BridgeStatistics(
                    total_transactions=len(dir_tx),
                    successful_transactions=sum(1 for tx in dir_tx if tx.get('status') == 'confirmed'),
                    failed_transactions=sum(1 for tx in dir_tx if tx.get('status') == 'failed'),
                    success_rate=sum(1 for tx in dir_tx if tx.get('status') == 'confirmed') / len(dir_tx) if dir_tx else 0,
                    total_volume=sum(tx.get('value', 0) for tx in dir_tx),
                    average_volume=np.mean([tx.get('value', 0) for tx in dir_tx]) if dir_tx else 0,
                    max_volume=max([tx.get('value', 0) for tx in dir_tx]) if dir_tx else 0,
                    min_volume=min([tx.get('value', 0) for tx in dir_tx]) if dir_tx else 0,
                    total_fees=sum(tx.get('gas_price', 0) * tx.get('gas_used', 0) / 1e18 for tx in dir_tx),
                    average_fee=np.mean([tx.get('gas_price', 0) * tx.get('gas_used', 0) / 1e18 for tx in dir_tx]) if dir_tx else 0,
                    max_fee=max([tx.get('gas_price', 0) * tx.get('gas_used', 0) / 1e18 for tx in dir_tx]) if dir_tx else 0,
                    min_fee=min([tx.get('gas_price', 0) * tx.get('gas_used', 0) / 1e18 for tx in dir_tx]) if dir_tx else 0,
                    average_latency=np.mean([tx.get('latency', 0) for tx in dir_tx]) if dir_tx else 0,
                    max_latency=max([tx.get('latency', 0) for tx in dir_tx]) if dir_tx else 0,
                    min_latency=min([tx.get('latency', 0) for tx in dir_tx]) if dir_tx else 0,
                    throughput=len(dir_tx) / self.config.window_size if self.config.window_size > 0 else 0,
                    timestamp=datetime.now(),
                )
                self.statistics[direction] = dir_stats

    def _check_alerts(self) -> None:
        """Vérifie les alertes"""
        if not self.statistics:
            return

        stats = self.statistics.get('global')
        if not stats:
            return

        # Alerte: taux de succès bas
        if stats.success_rate < 0.9:
            self.alerts.append(BridgeAlert(
                timestamp=datetime.now(),
                severity='warning',
                metric='success_rate',
                value=stats.success_rate,
                threshold=0.9,
                message=f"Taux de succès bas: {stats.success_rate:.2%}",
                details={'total': stats.total_transactions, 'successful': stats.successful_transactions},
            ))

        # Alerte: volume anormal
        if stats.total_volume > 0:
            volume_threshold = stats.total_volume * 2
            if stats.total_volume > volume_threshold:
                self.alerts.append(BridgeAlert(
                    timestamp=datetime.now(),
                    severity='info',
                    metric='volume',
                    value=stats.total_volume,
                    threshold=volume_threshold,
                    message=f"Volume élevé: {stats.total_volume:.2f}",
                    details={'normal': volume_threshold / 2, 'current': stats.total_volume},
                ))

        # Alerte: latence élevée
        if stats.average_latency > 60:
            self.alerts.append(BridgeAlert(
                timestamp=datetime.now(),
                severity='warning',
                metric='latency',
                value=stats.average_latency,
                threshold=60,
                message=f"Latence élevée: {stats.average_latency:.2f}s",
                details={'avg': stats.average_latency, 'max': stats.max_latency},
            ))

    def get_statistics(self) -> Dict[str, BridgeStatistics]:
        """
        Retourne les statistiques.

        Returns:
            Dict[str, BridgeStatistics]: Statistiques
        """
        return self.statistics

    def get_alerts(self) -> List[BridgeAlert]:
        """
        Retourne les alertes.

        Returns:
            List[BridgeAlert]: Alertes
        """
        return self.alerts

    def get_volume_analysis(self) -> Dict[str, Any]:
        """
        Analyse des volumes.

        Returns:
            Dict[str, Any]: Analyse des volumes
        """
        if not self.data:
            return {}

        volumes = [tx.get('value', 0) for tx in self.data]
        timestamps = [tx.get('timestamp', datetime.now()) for tx in self.data]

        return {
            'total_volume': sum(volumes),
            'average_volume': np.mean(volumes),
            'max_volume': max(volumes),
            'min_volume': min(volumes),
            'volume_per_hour': sum(volumes) / self.config.window_size if self.config.window_size > 0 else 0,
            'peak_volume': max(volumes),
            'peak_time': timestamps[np.argmax(volumes)] if volumes else None,
        }

    def get_fee_analysis(self) -> Dict[str, Any]:
        """
        Analyse des frais.

        Returns:
            Dict[str, Any]: Analyse des frais
        """
        if not self.data:
            return {}

        fees = [tx.get('gas_price', 0) * tx.get('gas_used', 0) / 1e18 for tx in self.data]

        return {
            'total_fees': sum(fees),
            'average_fee': np.mean(fees),
            'max_fee': max(fees),
            'min_fee': min(fees),
            'fee_per_hour': sum(fees) / self.config.window_size if self.config.window_size > 0 else 0,
        }

    def get_latency_analysis(self) -> Dict[str, Any]:
        """
        Analyse de latence.

        Returns:
            Dict[str, Any]: Analyse de latence
        """
        if not self.data:
            return {}

        latencies = [tx.get('latency', 0) for tx in self.data]

        return {
            'average_latency': np.mean(latencies),
            'max_latency': max(latencies),
            'min_latency': min(latencies),
            'p95_latency': np.percentile(latencies, 95) if latencies else 0,
            'p99_latency': np.percentile(latencies, 99) if latencies else 0,
        }

    def plot_statistics(self, figsize: Tuple[int, int] = (15, 10)) -> None:
        """
        Affiche les statistiques du bridge.

        Args:
            figsize: Taille de la figure
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib n'est pas disponible")
            return

        if not self.data:
            logger.warning("Aucune donnée disponible")
            return

        fig, axes = plt.subplots(2, 2, figsize=figsize)

        # Volume
        ax = axes[0, 0]
        volumes = [tx.get('value', 0) for tx in self.data]
        timestamps = [tx.get('timestamp', datetime.now()) for tx in self.data]
        ax.plot(timestamps, volumes, 'b-', alpha=0.7)
        ax.set_title('Volume des transactions')
        ax.set_xlabel('Temps')
        ax.set_ylabel('Volume')
        ax.grid(True, alpha=0.3)

        # Frais
        ax = axes[0, 1]
        fees = [tx.get('gas_price', 0) * tx.get('gas_used', 0) / 1e18 for tx in self.data]
        ax.hist(fees, bins=30, edgecolor='black', alpha=0.7)
        ax.set_title('Distribution des frais')
        ax.set_xlabel('Frais (ETH)')
        ax.set_ylabel('Fréquence')
        ax.grid(True, alpha=0.3)

        # Latence
        ax = axes[1, 0]
        latencies = [tx.get('latency', 0) for tx in self.data]
        ax.hist(latencies, bins=30, edgecolor='black', alpha=0.7)
        ax.axvline(x=60, color='r', linestyle='--', label='Seuil (60s)')
        ax.set_title('Distribution de latence')
        ax.set_xlabel('Latence (s)')
        ax.set_ylabel('Fréquence')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Taux de succès
        ax = axes[1, 1]
        successful = sum(1 for tx in self.data if tx.get('status') == 'confirmed')
        total = len(self.data)
        ax.pie([successful, total - successful], labels=['Succès', 'Échec'], autopct='%1.1f%%')
        ax.set_title(f'Taux de succès: {successful/total*100:.1f}%')

        plt.tight_layout()

        if self.config.save_plots:
            import os
            filename = f"{self.config.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.config.plot_dir, filename)
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Graphique sauvegardé: {filepath}")

        plt.show()

    def reset(self) -> None:
        """Réinitialise les données"""
        self.data = []
        self.statistics = {}
        self.alerts = []

        logger.info("Données réinitialisées")


def create_bridge_analytics(
    name: str = "bridge_analytics",
    window_size: int = 24,
    **kwargs
) -> BridgeAnalytics:
    """
    Factory pour créer un outil d'analyse de bridge.

    Args:
        name: Nom de l'analyse
        window_size: Taille de la fenêtre en heures
        **kwargs: Arguments supplémentaires

    Returns:
        BridgeAnalytics: Outil d'analyse
    """
    config = BridgeAnalyticsConfig(
        name=name,
        window_size=window_size,
        **kwargs
    )
    return BridgeAnalytics(config)


__all__ = [
    'BridgeAnalytics',
    'BridgeAnalyticsConfig',
    'BridgeStatistics',
    'BridgeAlert',
    'create_bridge_analytics',
]

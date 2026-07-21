"""
NEXUS AI TRADING SYSTEM - HEDGE BOT DRAWDOWN CONTROLLER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de contrôle du drawdown pour le Hedge Bot.
Gestion, monitoring, et limitation du drawdown.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
import pandas as pd

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class DrawdownStatus(Enum):
    """Statuts de drawdown."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    MAXIMUM = "maximum"
    RECOVERING = "recovering"


class DrawdownAction(Enum):
    """Actions de drawdown."""
    NONE = "none"
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    PAUSE_TRADING = "pause_trading"
    STOP_TRADING = "stop_trading"
    HEDGE = "hedge"
    RECOVER = "recover"


@dataclass
class DrawdownMetrics:
    """Métriques de drawdown."""
    user_id: UUID
    current_drawdown: float
    max_drawdown: float
    peak_value: Decimal
    trough_value: Decimal
    current_value: Decimal
    drawdown_duration_days: int
    recovery_time_days: int
    status: DrawdownStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown,
            "peak_value": str(self.peak_value),
            "trough_value": str(self.trough_value),
            "current_value": str(self.current_value),
            "drawdown_duration_days": self.drawdown_duration_days,
            "recovery_time_days": self.recovery_time_days,
            "status": self.status.value,
            "metadata": self.metadata
        }


@dataclass
class DrawdownAlert:
    """Alerte de drawdown."""
    alert_id: UUID
    user_id: UUID
    drawdown_level: float
    threshold: float
    status: DrawdownStatus
    action: DrawdownAction
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "alert_id": str(self.alert_id),
            "user_id": str(self.user_id),
            "drawdown_level": self.drawdown_level,
            "threshold": self.threshold,
            "status": self.status.value,
            "action": self.action.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE DRAWDOWN CONTROLLER
# ============================================================================

class DrawdownController:
    """
    Contrôleur de drawdown avancé.
    """

    # Seuils de drawdown par défaut
    DEFAULT_THRESHOLDS = {
        "warning": 0.10,
        "critical": 0.20,
        "maximum": 0.30
    }

    # Actions par seuil
    DEFAULT_ACTIONS = {
        "warning": DrawdownAction.REDUCE_POSITION,
        "critical": DrawdownAction.PAUSE_TRADING,
        "maximum": DrawdownAction.STOP_TRADING
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le contrôleur de drawdown.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Seuils
        self.thresholds = self.config.get("thresholds", self.DEFAULT_THRESHOLDS)
        self.actions = self.config.get("actions", self.DEFAULT_ACTIONS)
        
        # Cache
        self._metrics_cache: Dict[UUID, DrawdownMetrics] = {}
        self._alert_cache: Dict[UUID, List[DrawdownAlert]] = {}
        self._history_cache: Dict[UUID, List[float]] = {}
        self._peak_cache: Dict[UUID, Decimal] = {}
        
        # Métriques
        self._metrics = {
            "total_alerts": 0,
            "total_actions": 0,
            "by_status": {},
            "last_alert": None
        }

        logger.info("DrawdownController initialisé avec succès")

    # ========================================================================
    # CALCUL DU DRAWDOWN
    # ========================================================================

    async def calculate(
        self,
        user_id: UUID,
        value_history: List[Decimal],
        current_value: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> DrawdownMetrics:
        """
        Calcule les métriques de drawdown.

        Args:
            user_id: ID de l'utilisateur
            value_history: Historique des valeurs
            current_value: Valeur actuelle
            metadata: Métadonnées

        Returns:
            Métriques de drawdown
        """
        try:
            # Conversion en float
            values = [float(v) for v in value_history]
            
            if not values:
                values = [100.0]  # Valeur par défaut

            # Calcul du drawdown
            peak = max(values)
            trough = min(values)
            current = float(current_value) if current_value else values[-1]

            # Drawdown actuel
            current_drawdown = (peak - current) / peak if peak > 0 else 0

            # Drawdown maximum
            max_drawdown = (peak - trough) / peak if peak > 0 else 0

            # Durée du drawdown
            drawdown_duration = self._calculate_drawdown_duration(values)

            # Temps de récupération
            recovery_time = self._calculate_recovery_time(values, peak)

            # Statut
            status = self._get_status(current_drawdown)

            metrics = DrawdownMetrics(
                user_id=user_id,
                current_drawdown=current_drawdown,
                max_drawdown=max_drawdown,
                peak_value=Decimal(str(peak)),
                trough_value=Decimal(str(trough)),
                current_value=Decimal(str(current)),
                drawdown_duration_days=drawdown_duration,
                recovery_time_days=recovery_time,
                status=status,
                metadata=metadata or {}
            )

            self._metrics_cache[user_id] = metrics
            self._history_cache[user_id] = values
            self._peak_cache[user_id] = Decimal(str(peak))

            # Vérification des alertes
            await self._check_alerts(user_id, current_drawdown)

            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul du drawdown: {e}")
            raise

    def _calculate_drawdown_duration(self, values: List[float]) -> int:
        """
        Calcule la durée du drawdown.

        Args:
            values: Historique des valeurs

        Returns:
            Durée en jours
        """
        if len(values) < 2:
            return 0

        # Trouver le dernier peak
        peak_idx = 0
        for i in range(1, len(values)):
            if values[i] > values[peak_idx]:
                peak_idx = i

        # Calculer la durée depuis le peak
        if peak_idx < len(values) - 1:
            return len(values) - peak_idx - 1

        return 0

    def _calculate_recovery_time(self, values: List[float], peak: float) -> int:
        """
        Calcule le temps de récupération.

        Args:
            values: Historique des valeurs
            peak: Valeur de pic

        Returns:
            Temps de récupération en jours
        """
        if len(values) < 2:
            return 0

        # Trouver le premier point de récupération
        for i in range(len(values)):
            if values[i] >= peak:
                return i

        return len(values)

    def _get_status(self, drawdown: float) -> DrawdownStatus:
        """
        Détermine le statut du drawdown.

        Args:
            drawdown: Niveau de drawdown

        Returns:
            Statut
        """
        if drawdown >= self.thresholds.get("maximum", 0.30):
            return DrawdownStatus.MAXIMUM
        elif drawdown >= self.thresholds.get("critical", 0.20):
            return DrawdownStatus.CRITICAL
        elif drawdown >= self.thresholds.get("warning", 0.10):
            return DrawdownStatus.WARNING
        elif drawdown > 0.01:
            return DrawdownStatus.RECOVERING
        else:
            return DrawdownStatus.NORMAL

    # ========================================================================
    # ALERTES DE DRAWDOWN
    # ========================================================================

    async def _check_alerts(
        self,
        user_id: UUID,
        drawdown: float
    ) -> None:
        """
        Vérifie les alertes de drawdown.

        Args:
            user_id: ID de l'utilisateur
            drawdown: Niveau de drawdown
        """
        try:
            status = self._get_status(drawdown)

            # Vérification des seuils
            for level, threshold in self.thresholds.items():
                if drawdown >= threshold:
                    action = self.actions.get(level, DrawdownAction.NONE)
                    
                    alert = DrawdownAlert(
                        alert_id=uuid4(),
                        user_id=user_id,
                        drawdown_level=drawdown,
                        threshold=threshold,
                        status=status,
                        action=action,
                        message=f"Drawdown de {drawdown*100:.1f}% atteint le seuil {level} ({threshold*100:.1f}%)",
                        timestamp=datetime.now()
                    )

                    if user_id not in self._alert_cache:
                        self._alert_cache[user_id] = []
                    
                    self._alert_cache[user_id].append(alert)
                    self._metrics["total_alerts"] += 1

                    status_key = status.value
                    if status_key not in self._metrics["by_status"]:
                        self._metrics["by_status"][status_key] = 0
                    self._metrics["by_status"][status_key] += 1

                    self._metrics["last_alert"] = datetime.now().isoformat()

                    # Exécution de l'action
                    await self._execute_action(user_id, action, alert)

                    break

        except Exception as e:
            logger.error(f"Erreur de vérification des alertes: {e}")

    async def _execute_action(
        self,
        user_id: UUID,
        action: DrawdownAction,
        alert: DrawdownAlert
    ) -> None:
        """
        Exécute une action de drawdown.

        Args:
            user_id: ID de l'utilisateur
            action: Action à exécuter
            alert: Alerte déclenchée
        """
        try:
            self._metrics["total_actions"] += 1

            if action == DrawdownAction.REDUCE_POSITION:
                logger.info(f"Réduction de position pour {user_id} - Drawdown: {alert.drawdown_level*100:.1f}%")
                # Ici, logique de réduction de position
            
            elif action == DrawdownAction.CLOSE_POSITION:
                logger.info(f"Fermeture de position pour {user_id} - Drawdown: {alert.drawdown_level*100:.1f}%")
                # Ici, logique de fermeture de position
            
            elif action == DrawdownAction.PAUSE_TRADING:
                logger.info(f"Pause du trading pour {user_id} - Drawdown: {alert.drawdown_level*100:.1f}%")
                # Ici, logique de pause du trading
            
            elif action == DrawdownAction.STOP_TRADING:
                logger.info(f"Arrêt du trading pour {user_id} - Drawdown: {alert.drawdown_level*100:.1f}%")
                # Ici, logique d'arrêt du trading
            
            elif action == DrawdownAction.HEDGE:
                logger.info(f"Hedge activé pour {user_id} - Drawdown: {alert.drawdown_level*100:.1f}%")
                # Ici, logique de hedge

        except Exception as e:
            logger.error(f"Erreur d'exécution de l'action: {e}")

    # ========================================================================
    # ANALYSE DU DRAWDOWN
    # ========================================================================

    async def analyze_drawdown(
        self,
        user_id: UUID,
        value_history: List[Decimal]
    ) -> Dict[str, Any]:
        """
        Analyse approfondie du drawdown.

        Args:
            user_id: ID de l'utilisateur
            value_history: Historique des valeurs

        Returns:
            Analyse du drawdown
        """
        try:
            values = [float(v) for v in value_history]
            
            if len(values) < 2:
                return {"error": "Historique insuffisant"}

            # Calcul des drawdowns
            drawdowns = []
            peak = values[0]
            
            for value in values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak if peak > 0 else 0
                drawdowns.append(drawdown)

            # Statistiques
            avg_drawdown = np.mean(drawdowns)
            max_drawdown = np.max(drawdowns)
            std_drawdown = np.std(drawdowns)

            # Distribution
            distribution = {
                "0-5%": len([d for d in drawdowns if d < 0.05]),
                "5-10%": len([d for d in drawdowns if 0.05 <= d < 0.10]),
                "10-20%": len([d for d in drawdowns if 0.10 <= d < 0.20]),
                "20-30%": len([d for d in drawdowns if 0.20 <= d < 0.30]),
                ">30%": len([d for d in drawdowns if d >= 0.30])
            }

            # Périodes de drawdown
            drawdown_periods = []
            in_drawdown = False
            start_idx = 0
            
            for i, dd in enumerate(drawdowns):
                if dd > 0.05 and not in_drawdown:
                    in_drawdown = True
                    start_idx = i
                elif dd <= 0.05 and in_drawdown:
                    in_drawdown = False
                    drawdown_periods.append({
                        "start": start_idx,
                        "end": i,
                        "duration": i - start_idx,
                        "max_drawdown": max(drawdowns[start_idx:i+1])
                    })

            return {
                "avg_drawdown": avg_drawdown,
                "max_drawdown": max_drawdown,
                "std_drawdown": std_drawdown,
                "distribution": distribution,
                "drawdown_periods": drawdown_periods,
                "total_drawdown_periods": len(drawdown_periods),
                "drawdown_frequency": len(drawdown_periods) / len(values) * 100 if len(values) > 0 else 0,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur d'analyse du drawdown: {e}")
            return {"error": str(e)}

    # ========================================================================
    # RÉCUPÉRATION APRÈS DRAWDOWN
    # ========================================================================

    async def recovery_plan(
        self,
        user_id: UUID,
        current_drawdown: float,
        target_drawdown: float = 0.05
    ) -> Dict[str, Any]:
        """
        Génère un plan de récupération.

        Args:
            user_id: ID de l'utilisateur
            current_drawdown: Drawdown actuel
            target_drawdown: Drawdown cible

        Returns:
            Plan de récupération
        """
        try:
            recovery_amount = current_drawdown - target_drawdown
            
            return {
                "recovery_amount": recovery_amount,
                "target_drawdown": target_drawdown,
                "estimated_days": max(0, int(recovery_amount / 0.01)),  # Estimation simplifiée
                "strategy": [
                    "Réduire l'exposition aux actifs risqués",
                    "Augmenter la part des actifs stables",
                    "Utiliser des stratégies de hedge",
                    "Diversifier le portefeuille"
                ],
                "recommendations": [
                    f"Objectif de récupération: {recovery_amount*100:.1f}%",
                    f"Durée estimée: {max(0, int(recovery_amount / 0.01))} jours",
                    "Surveiller quotidiennement le drawdown",
                    "Ajuster les positions progressivement"
                ],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur de génération du plan de récupération: {e}")
            return {"error": str(e)}

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_metrics(
        self,
        user_id: UUID
    ) -> Optional[DrawdownMetrics]:
        """
        Récupère les métriques de drawdown.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Métriques ou None
        """
        return self._metrics_cache.get(user_id)

    async def get_alerts(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[DrawdownAlert]:
        """
        Récupère les alertes de drawdown.

        Args:
            user_id: ID de l'utilisateur
            limit: Nombre d'alertes
            offset: Décalage

        Returns:
            Liste des alertes
        """
        alerts = self._alert_cache.get(user_id, [])
        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        return alerts[offset:offset + limit]

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_alerts": self._metrics["total_alerts"],
                "total_actions": self._metrics["total_actions"],
                "by_status": self._metrics["by_status"],
                "last_alert": self._metrics["last_alert"],
                "cached_metrics": len(self._metrics_cache),
                "cached_alerts": len(self._alert_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de DrawdownController...")
        self._metrics_cache.clear()
        self._alert_cache.clear()
        self._history_cache.clear()
        self._peak_cache.clear()
        logger.info("DrawdownController fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_drawdown_controller(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> DrawdownController:
    """
    Crée une instance de DrawdownController.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de DrawdownController
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return DrawdownController(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "DrawdownStatus",
    "DrawdownAction",
    "DrawdownMetrics",
    "DrawdownAlert",
    "DrawdownController",
    "create_drawdown_controller"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du DrawdownController."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT DRAWDOWN CONTROLLER")
    print("=" * 60)

    # Création du contrôleur
    controller = create_drawdown_controller()

    print(f"\n✅ DrawdownController initialisé")

    # Génération d'un historique de valeurs
    np.random.seed(42)
    n = 100
    values = [100.0]
    
    for i in range(n-1):
        change = np.random.normal(0, 0.02)
        new_value = values[-1] * (1 + change)
        values.append(max(0, new_value))

    # Calcul du drawdown
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Calcul du drawdown...")
    
    metrics = await controller.calculate(
        user_id=user_id,
        value_history=[Decimal(str(v)) for v in values],
        current_value=Decimal(str(values[-1]))
    )

    print(f"   Drawdown actuel: {metrics.current_drawdown*100:.1f}%")
    print(f"   Drawdown maximum: {metrics.max_drawdown*100:.1f}%")
    print(f"   Statut: {metrics.status.value}")
    print(f"   Durée: {metrics.drawdown_duration_days} jours")
    print(f"   Temps de récupération: {metrics.recovery_time_days} jours")

    # Analyse approfondie
    print(f"\n🔍 Analyse du drawdown...")
    analysis = await controller.analyze_drawdown(
        user_id=user_id,
        value_history=[Decimal(str(v)) for v in values]
    )

    print(f"   Drawdown moyen: {analysis.get('avg_drawdown', 0)*100:.1f}%")
    print(f"   Périodes de drawdown: {analysis.get('total_drawdown_periods', 0)}")
    print(f"   Fréquence: {analysis.get('drawdown_frequency', 0):.1f}%")

    # Plan de récupération
    print(f"\n📋 Plan de récupération...")
    plan = await controller.recovery_plan(
        user_id=user_id,
        current_drawdown=metrics.current_drawdown,
        target_drawdown=0.05
    )

    print(f"   Montant à récupérer: {plan.get('recovery_amount', 0)*100:.1f}%")
    print(f"   Jours estimés: {plan.get('estimated_days', 0)}")
    print(f"   Stratégies: {len(plan.get('strategy', []))}")

    # Alertes
    print(f"\n🔔 Alertes de drawdown:")
    alerts = await controller.get_alerts(user_id)
    for alert in alerts[:3]:
        print(f"   {alert.timestamp.strftime('%H:%M:%S')}: {alert.message}")

    # Santé du service
    health = await controller.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Alertes: {health['total_alerts']}")
    print(f"   Actions: {health['total_actions']}")
    print(f"   Dernière alerte: {health['last_alert']}")

    # Fermeture
    await controller.close()

    print("\n" + "=" * 60)
    print("DrawdownController NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

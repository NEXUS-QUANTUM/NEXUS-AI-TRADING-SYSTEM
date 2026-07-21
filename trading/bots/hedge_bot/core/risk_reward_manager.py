"""
NEXUS AI TRADING SYSTEM - Hedge Bot Risk Reward Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de risque/récompense pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import math
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import numpy as np

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class RiskRewardType(Enum):
    """Types de risque/récompense"""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    ADAPTIVE = "adaptive"
    VOLATILITY = "volatility"
    KELLY = "kelly"
    OPTIMAL = "optimal"
    CUSTOM = "custom"

class RiskRewardStatus(Enum):
    """Statuts de risque/récompense"""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAUSED = "paused"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class RiskRewardLevel:
    """Niveau de risque/récompense"""
    id: str
    risk: float
    reward: float
    ratio: float
    probability: float
    expected_value: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskRewardPosition:
    """Position de risque/récompense"""
    id: str
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    position_size: float
    status: RiskRewardStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskRewardMetrics:
    """Métriques de risque/récompense"""
    total_risk: float
    total_reward: float
    avg_risk_reward_ratio: float
    win_rate: float
    expected_value: float
    profit_factor: float
    risk_adjusted_return: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskRewardConfig:
    """Configuration de risque/récompense"""
    enabled: bool = True
    default_ratio: float = 2.0
    min_ratio: float = 1.0
    max_ratio: float = 5.0
    risk_per_trade: float = 0.01  # 1% of capital
    max_risk_per_day: float = 0.05  # 5% of capital
    max_risk_per_week: float = 0.10  # 10% of capital
    kelly_fraction: float = 0.25
    volatility_adjustment: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# RISK REWARD MANAGER
# ============================================================

class RiskRewardManager:
    """
    Gestionnaire de risque/récompense pour le bot de couverture
    
    Gère les ratios risque/récompense, dimensionnement des positions
    et optimisation du risque
    """
    
    def __init__(
        self,
        config: Optional[RiskRewardConfig] = None,
        update_interval: int = 60,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de risque/récompense
        
        Args:
            config: Configuration
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or RiskRewardConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Positions
        self.positions: Dict[str, RiskRewardPosition] = {}
        self.active_positions: Dict[str, RiskRewardPosition] = {}
        self.closed_positions: Dict[str, RiskRewardPosition] = {}
        
        # Niveaux
        self.levels: Dict[str, RiskRewardLevel] = {}
        
        # Métriques
        self.metrics: Optional[RiskRewardMetrics] = None
        
        # Statistiques
        self.stats = {
            'total_positions': 0,
            'active_positions': 0,
            'closed_positions': 0,
            'winning_positions': 0,
            'losing_positions': 0,
            'total_risk': 0.0,
            'total_reward': 0.0,
            'avg_ratio': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'expected_value': 0.0,
            'risk_adjusted_return': 0.0,
        }
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'position_created': [],
            'position_updated': [],
            'position_closed': [],
            'risk_breached': [],
            'target_hit': [],
        }
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Capital
        self.capital: float = 10000.0
        
        # Démarrer le monitoring
        if enable_monitoring and update_interval > 0:
            self.start()
        
        logger.info("RiskRewardManager initialized")
    
    # ============================================================
    # POSITION MANAGEMENT
    # ============================================================
    
    def create_position(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        capital: Optional[float] = None,
        ratio: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskRewardPosition:
        """
        Crée une position de risque/récompense
        
        Args:
            symbol: Symbole
            entry_price: Prix d'entrée
            stop_loss: Prix de stop loss
            take_profit: Prix de take profit
            capital: Capital à utiliser
            ratio: Ratio risque/récompense
            metadata: Métadonnées
            
        Returns:
            RiskRewardPosition: Position créée
        """
        with self._lock:
            # Calculer le ratio
            if ratio is None:
                ratio = self.config.default_ratio
            
            # Calculer les montants
            risk_amount = abs(entry_price - stop_loss)
            reward_amount = abs(take_profit - entry_price)
            risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
            
            # Calculer la taille de position
            capital = capital or self.capital
            position_size = self._calculate_position_size(capital, risk_amount, ratio)
            
            position = RiskRewardPosition(
                id=f"rr_{int(time.time())}_{symbol}",
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_amount=risk_amount * position_size,
                reward_amount=reward_amount * position_size,
                risk_reward_ratio=risk_reward_ratio,
                position_size=position_size,
                status=RiskRewardStatus.ACTIVE,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata=metadata or {}
            )
            
            self.positions[position.id] = position
            self.active_positions[position.id] = position
            self.stats['total_positions'] += 1
            self.stats['active_positions'] += 1
            
            self._update_stats()
            self._trigger_event('position_created', position)
            
            logger.info(f"Risk/Reward position created: {symbol} - Ratio: {risk_reward_ratio:.2f}")
            return position
    
    def _calculate_position_size(
        self,
        capital: float,
        risk_per_unit: float,
        ratio: float
    ) -> float:
        """
        Calcule la taille de position
        
        Args:
            capital: Capital disponible
            risk_per_unit: Risque par unité
            ratio: Ratio risque/récompense
            
        Returns:
            float: Taille de position
        """
        # Risque par trade
        risk_amount = capital * self.config.risk_per_trade
        
        # Ajustement de volatilité
        if self.config.volatility_adjustment:
            # Simuler l'ajustement de volatilité
            volatility_factor = 1.0
            risk_amount *= volatility_factor
        
        # Kelly Criterion
        if self.config.kelly_fraction > 0:
            # Simuler le calcul Kelly
            win_rate = 0.6
            avg_win = 2.0
            avg_loss = 1.0
            kelly = (win_rate / avg_loss) - ((1 - win_rate) / avg_win)
            kelly = max(0, min(kelly, 1)) * self.config.kelly_fraction
            risk_amount *= kelly
        
        # Calculer la taille
        position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0
        
        return position_size
    
    def update_position(self, position_id: str, current_price: float) -> bool:
        """
        Met à jour une position
        
        Args:
            position_id: ID de la position
            current_price: Prix actuel
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            if position.status != RiskRewardStatus.ACTIVE:
                return False
            
            position.updated_at = datetime.now()
            
            # Vérifier le stop loss
            if position.side == 'long':
                if current_price <= position.stop_loss:
                    self._close_position(position_id, current_price, 'stop_loss')
                    return True
                if current_price >= position.take_profit:
                    self._close_position(position_id, current_price, 'take_profit')
                    return True
            else:
                if current_price >= position.stop_loss:
                    self._close_position(position_id, current_price, 'stop_loss')
                    return True
                if current_price <= position.take_profit:
                    self._close_position(position_id, current_price, 'take_profit')
                    return True
            
            self._trigger_event('position_updated', position)
            return True
    
    def _close_position(
        self,
        position_id: str,
        price: float,
        reason: str
    ) -> bool:
        """
        Ferme une position
        
        Args:
            position_id: ID de la position
            price: Prix de fermeture
            reason: Raison de la fermeture
            
        Returns:
            bool: True si fermée
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            # Calculer le P&L
            if position.side == 'long':
                pnl = (price - position.entry_price) * position.position_size
            else:
                pnl = (position.entry_price - price) * position.position_size
            
            position.status = RiskRewardStatus.TRIGGERED
            position.metadata['close_price'] = price
            position.metadata['close_reason'] = reason
            position.metadata['pnl'] = pnl
            
            self.active_positions.pop(position_id, None)
            self.closed_positions[position_id] = position
            self.stats['active_positions'] -= 1
            self.stats['closed_positions'] += 1
            
            if pnl > 0:
                self.stats['winning_positions'] += 1
                self._trigger_event('target_hit', position)
            else:
                self.stats['losing_positions'] += 1
                self._trigger_event('risk_breached', position)
            
            self._update_stats()
            self._trigger_event('position_closed', position)
            
            logger.info(f"Position closed: {position_id} - {reason} - PNL: {pnl:.2f}")
            return True
    
    def get_position(self, position_id: str) -> Optional[RiskRewardPosition]:
        """
        Récupère une position
        
        Args:
            position_id: ID de la position
            
        Returns:
            Optional[RiskRewardPosition]: Position
        """
        return self.positions.get(position_id)
    
    def get_active_positions(self) -> List[RiskRewardPosition]:
        """
        Récupère les positions actives
        
        Returns:
            List[RiskRewardPosition]: Positions actives
        """
        return list(self.active_positions.values())
    
    # ============================================================
    # OPTIMIZATION
    # ============================================================
    
    def calculate_optimal_ratio(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calcule le ratio optimal
        
        Args:
            win_rate: Taux de victoire
            avg_win: Gain moyen
            avg_loss: Perte moyenne
            
        Returns:
            float: Ratio optimal
        """
        if avg_loss == 0:
            return self.config.max_ratio
        
        # Kelly Criterion
        kelly = (win_rate / avg_loss) - ((1 - win_rate) / avg_win)
        kelly = max(0, min(kelly, 1))
        
        # Ratio optimal
        optimal_ratio = (1 + kelly) / (1 - kelly) * self.config.kelly_fraction
        optimal_ratio = max(self.config.min_ratio, min(optimal_ratio, self.config.max_ratio))
        
        return optimal_ratio
    
    def calculate_kelly_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calcule la fraction Kelly
        
        Args:
            win_rate: Taux de victoire
            avg_win: Gain moyen
            avg_loss: Perte moyenne
            
        Returns:
            float: Fraction Kelly
        """
        if avg_loss == 0:
            return 0
        
        kelly = (win_rate / avg_loss) - ((1 - win_rate) / avg_win)
        kelly = max(0, min(kelly, 1))
        
        return kelly
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
    
    def calculate_metrics(self) -> RiskRewardMetrics:
        """
        Calcule les métriques de risque/récompense
        
        Returns:
            RiskRewardMetrics: Métriques calculées
        """
        with self._lock:
            closed = list(self.closed_positions.values())
            if not closed:
                return RiskRewardMetrics(0,0,0,0,0,0,0)
            
            total_risk = sum(p.risk_amount for p in closed)
            total_reward = sum(p.reward_amount for p in closed)
            avg_ratio = sum(p.risk_reward_ratio for p in closed) / len(closed) if closed else 0
            
            winning = [p for p in closed if p.metadata.get('pnl', 0) > 0]
            win_rate = len(winning) / len(closed) if closed else 0
            
            # Expected Value
            avg_win = sum(p.metadata.get('pnl', 0) for p in winning) / len(winning) if winning else 0
            avg_loss = sum(abs(p.metadata.get('pnl', 0)) for p in closed if p.metadata.get('pnl', 0) < 0)
            avg_loss = avg_loss / (len(closed) - len(winning)) if (len(closed) - len(winning)) > 0 else 0
            
            expected_value = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
            
            # Profit Factor
            total_win = sum(p.metadata.get('pnl', 0) for p in winning)
            total_loss = sum(abs(p.metadata.get('pnl', 0)) for p in closed if p.metadata.get('pnl', 0) < 0)
            profit_factor = total_win / total_loss if total_loss > 0 else float('inf')
            
            # Risk Adjusted Return
            total_pnl = sum(p.metadata.get('pnl', 0) for p in closed)
            risk_adjusted_return = total_pnl / total_risk if total_risk > 0 else 0
            
            metrics = RiskRewardMetrics(
                total_risk=total_risk,
                total_reward=total_reward,
                avg_risk_reward_ratio=avg_ratio,
                win_rate=win_rate,
                expected_value=expected_value,
                profit_factor=profit_factor,
                risk_adjusted_return=risk_adjusted_return
            )
            
            self.metrics = metrics
            return metrics
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        metrics = self.calculate_metrics()
        self.stats.update({
            'total_risk': metrics.total_risk,
            'total_reward': metrics.total_reward,
            'avg_ratio': metrics.avg_risk_reward_ratio,
            'win_rate': metrics.win_rate,
            'profit_factor': metrics.profit_factor,
            'expected_value': metrics.expected_value,
            'risk_adjusted_return': metrics.risk_adjusted_return,
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            return self.stats.copy()
    
    def get_report(self) -> Dict[str, Any]:
        """
        Récupère un rapport
        
        Returns:
            Dict[str, Any]: Rapport
        """
        metrics = self.calculate_metrics()
        
        return {
            'timestamp': time.time(),
            'stats': self.get_stats(),
            'metrics': {
                'total_risk': metrics.total_risk,
                'total_reward': metrics.total_reward,
                'avg_risk_reward_ratio': metrics.avg_risk_reward_ratio,
                'win_rate': metrics.win_rate,
                'expected_value': metrics.expected_value,
                'profit_factor': metrics.profit_factor,
                'risk_adjusted_return': metrics.risk_adjusted_return,
            },
            'active_positions': [
                {
                    'id': p.id,
                    'symbol': p.symbol,
                    'entry_price': p.entry_price,
                    'stop_loss': p.stop_loss,
                    'take_profit': p.take_profit,
                    'risk_amount': p.risk_amount,
                    'reward_amount': p.reward_amount,
                    'ratio': p.risk_reward_ratio,
                }
                for p in self.active_positions.values()
            ],
            'alerts': self.alerts[-10:],
        }
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on(self, event: str, callback: Callable):
        """
        Enregistre un callback
        
        Args:
            event: Événement
            callback: Fonction de callback
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _trigger_event(self, event: str, data: Any):
        """
        Déclenche un événement
        
        Args:
            event: Événement
            data: Données
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # ============================================================
    # ALERTS
    # ============================================================
    
    def _add_alert(self, message: str, severity: str = "info"):
        """
        Ajoute une alerte
        
        Args:
            message: Message
            severity: Sévérité
        """
        alert = {
            'timestamp': time.time(),
            'severity': severity,
            'message': message,
        }
        self.alerts.append(alert)
        
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    # ============================================================
    # MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            return
        
        self._running = True
        self._update_task = threading.Thread(target=self._update_loop, daemon=True)
        self._update_task.start()
        
        logger.info("RiskRewardManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("RiskRewardManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_positions()
                self._check_risk_limits()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_positions(self):
        """Met à jour les positions"""
        # À implémenter avec les prix réels
        pass
    
    def _check_risk_limits(self):
        """Vérifie les limites de risque"""
        # Vérifier le risque total
        total_risk = sum(p.risk_amount for p in self.active_positions.values())
        daily_risk = self.capital * self.config.max_risk_per_day
        
        if total_risk > daily_risk:
            self._add_alert(
                f"Daily risk limit exceeded: {total_risk:.2f} > {daily_risk:.2f}",
                "warning"
            )

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_risk_reward_manager: Optional[RiskRewardManager] = None

def get_risk_reward_manager(
    config: Optional[RiskRewardConfig] = None
) -> RiskRewardManager:
    """
    Récupère le gestionnaire de risque/récompense (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        RiskRewardManager: Gestionnaire de risque/récompense
    """
    global _risk_reward_manager
    if _risk_reward_manager is None:
        _risk_reward_manager = RiskRewardManager(config)
    return _risk_reward_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'RiskRewardType',
    'RiskRewardStatus',
    'RiskRewardLevel',
    'RiskRewardPosition',
    'RiskRewardMetrics',
    'RiskRewardConfig',
    'RiskRewardManager',
    'get_risk_reward_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Risk reward manager module initialized")

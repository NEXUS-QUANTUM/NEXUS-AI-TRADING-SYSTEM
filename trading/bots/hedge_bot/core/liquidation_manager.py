"""
NEXUS AI TRADING SYSTEM - Hedge Bot Liquidation Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de liquidation pour le bot de couverture
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

class LiquidationType(Enum):
    """Types de liquidation"""
    MARGIN = "margin"
    STOP = "stop"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    EMERGENCY = "emergency"
    PARTIAL = "partial"
    FULL = "full"

class LiquidationStatus(Enum):
    """Statuts de liquidation"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"

class LiquidationPriority(Enum):
    """Priorités de liquidation"""
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    CRITICAL = 0

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class LiquidationOrder:
    """Ordre de liquidation"""
    id: str
    symbol: str
    side: str
    size: float
    price: float
    type: LiquidationType
    priority: LiquidationPriority
    status: LiquidationStatus
    created_at: datetime
    executed_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LiquidationPosition:
    """Position à liquider"""
    id: str
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    liquidation_price: float
    margin_used: float
    pnl: float
    reason: str
    type: LiquidationType
    status: LiquidationStatus
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LiquidationMetrics:
    """Métriques de liquidation"""
    total_liquidations: int
    total_volume: float
    total_pnl: float
    avg_execution_time: float
    success_rate: float
    partial_liquidations: int
    failed_liquidations: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LiquidationConfig:
    """Configuration de liquidation"""
    enabled: bool = True
    max_partial_size: float = 0.5  # 50% of position
    min_partial_size: float = 0.01  # 1% of position
    execution_timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 5.0
    slippage_tolerance: float = 0.01
    emergency_threshold: float = 0.90
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# LIQUIDATION MANAGER
# ============================================================

class LiquidationManager:
    """
    Gestionnaire de liquidation pour le bot de couverture
    
    Gère les liquidations de positions avec différentes stratégies
    """
    
    def __init__(
        self,
        config: Optional[LiquidationConfig] = None,
        update_interval: int = 5,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de liquidation
        
        Args:
            config: Configuration de liquidation
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or LiquidationConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Positions à liquider
        self.liquidation_positions: Dict[str, LiquidationPosition] = {}
        self.active_liquidations: Dict[str, LiquidationPosition] = {}
        self.completed_liquidations: Dict[str, LiquidationPosition] = {}
        
        # Ordres de liquidation
        self.orders: Dict[str, LiquidationOrder] = {}
        self.pending_orders: Dict[str, LiquidationOrder] = {}
        self.executed_orders: Dict[str, LiquidationOrder] = {}
        
        # Métriques
        self.metrics: Optional[LiquidationMetrics] = None
        
        # Statistiques
        self.stats = {
            'total_liquidations': 0,
            'active_liquidations': 0,
            'completed_liquidations': 0,
            'failed_liquidations': 0,
            'partial_liquidations': 0,
            'total_volume': 0.0,
            'total_pnl': 0.0,
            'avg_execution_time': 0.0,
            'success_rate': 0.0,
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
            'liquidation_started': [],
            'liquidation_completed': [],
            'liquidation_failed': [],
            'liquidation_partial': [],
            'emergency_liquidation': [],
        }
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Démarrer le monitoring
        if enable_monitoring and update_interval > 0:
            self.start()
        
        logger.info("LiquidationManager initialized")
    
    # ============================================================
    # LIQUIDATION MANAGEMENT
    # ============================================================
    
    def add_liquidation(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        current_price: float,
        liquidation_price: float,
        margin_used: float,
        reason: str,
        liquidation_type: LiquidationType = LiquidationType.STOP,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Ajoute une position à liquider
        
        Args:
            symbol: Symbole
            side: Côté
            size: Taille
            entry_price: Prix d'entrée
            current_price: Prix actuel
            liquidation_price: Prix de liquidation
            margin_used: Marge utilisée
            reason: Raison
            liquidation_type: Type de liquidation
            metadata: Métadonnées
            
        Returns:
            str: ID de la liquidation
        """
        with self._lock:
            position = LiquidationPosition(
                id=f"liq_{int(time.time())}_{symbol}",
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                current_price=current_price,
                liquidation_price=liquidation_price,
                margin_used=margin_used,
                pnl=(current_price - entry_price) * size,
                reason=reason,
                type=liquidation_type,
                status=LiquidationStatus.PENDING,
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            
            self.liquidation_positions[position.id] = position
            self.active_liquidations[position.id] = position
            self.stats['total_liquidations'] += 1
            self.stats['active_liquidations'] += 1
            
            # Déterminer la priorité
            priority = self._calculate_priority(position)
            
            # Créer l'ordre de liquidation
            order = LiquidationOrder(
                id=f"ord_{int(time.time())}_{symbol}",
                symbol=symbol,
                side=side,
                size=size,
                price=current_price,
                type=liquidation_type,
                priority=priority,
                status=LiquidationStatus.PENDING,
                created_at=datetime.now(),
                executed_at=None,
                metadata=metadata or {}
            )
            
            self.orders[order.id] = order
            self.pending_orders[order.id] = order
            
            self._trigger_event('liquidation_started', position)
            
            if liquidation_type == LiquidationType.EMERGENCY:
                self._trigger_event('emergency_liquidation', position)
            
            logger.info(f"Liquidation added: {position.id} - {symbol} - {size} @ {current_price:.2f}")
            return position.id
    
    def _calculate_priority(self, position: LiquidationPosition) -> LiquidationPriority:
        """
        Calcule la priorité de liquidation
        
        Args:
            position: Position à liquider
            
        Returns:
            LiquidationPriority: Priorité
        """
        # Calculer le ratio de marge
        margin_ratio = position.margin_used / (position.size * position.current_price)
        
        if margin_ratio > 0.9:
            return LiquidationPriority.CRITICAL
        elif margin_ratio > 0.7:
            return LiquidationPriority.HIGH
        elif margin_ratio > 0.5:
            return LiquidationPriority.MEDIUM
        else:
            return LiquidationPriority.LOW
    
    def execute_liquidation(self, position_id: str) -> bool:
        """
        Exécute une liquidation
        
        Args:
            position_id: ID de la position
            
        Returns:
            bool: True si exécutée
        """
        with self._lock:
            position = self.liquidation_positions.get(position_id)
            if not position:
                return False
            
            if position.status != LiquidationStatus.PENDING:
                return False
            
            position.status = LiquidationStatus.IN_PROGRESS
            
            # Exécuter la liquidation
            try:
                success = self._execute_liquidation_order(position)
                
                if success:
                    position.status = LiquidationStatus.COMPLETED
                    self.active_liquidations.pop(position_id, None)
                    self.completed_liquidations[position_id] = position
                    self.stats['active_liquidations'] -= 1
                    self.stats['completed_liquidations'] += 1
                    self.stats['total_volume'] += position.size
                    self.stats['total_pnl'] += position.pnl
                    
                    self._trigger_event('liquidation_completed', position)
                    
                    logger.info(f"Liquidation completed: {position_id}")
                else:
                    position.status = LiquidationStatus.FAILED
                    self.stats['failed_liquidations'] += 1
                    self._trigger_event('liquidation_failed', position)
                    
                    logger.warning(f"Liquidation failed: {position_id}")
                
                self._update_stats()
                return success
                
            except Exception as e:
                position.status = LiquidationStatus.FAILED
                self.stats['failed_liquidations'] += 1
                logger.error(f"Liquidation execution error: {e}")
                return False
    
    def _execute_liquidation_order(self, position: LiquidationPosition) -> bool:
        """
        Exécute un ordre de liquidation
        
        Args:
            position: Position à liquider
            
        Returns:
            bool: True si exécuté
        """
        # Simuler l'exécution d'un ordre de liquidation
        # À implémenter avec des exchanges réels
        
        # Simuler le slippage
        slippage = np.random.uniform(-self.config.slippage_tolerance, self.config.slippage_tolerance)
        execution_price = position.current_price * (1 + slippage)
        
        # Mettre à jour les métadonnées
        position.metadata['execution_price'] = execution_price
        position.metadata['execution_time'] = datetime.now()
        
        return True
    
    def partial_liquidation(self, position_id: str, size: float) -> bool:
        """
        Exécute une liquidation partielle
        
        Args:
            position_id: ID de la position
            size: Taille à liquider
            
        Returns:
            bool: True si exécutée
        """
        with self._lock:
            position = self.liquidation_positions.get(position_id)
            if not position:
                return False
            
            if position.status != LiquidationStatus.PENDING:
                return False
            
            # Vérifier les limites
            max_size = position.size * self.config.max_partial_size
            min_size = position.size * self.config.min_partial_size
            
            if size > max_size:
                size = max_size
            if size < min_size:
                return False
            
            # Exécuter la liquidation partielle
            try:
                success = self._execute_partial_liquidation(position, size)
                
                if success:
                    position.size -= size
                    position.status = LiquidationStatus.PARTIAL
                    self.stats['partial_liquidations'] += 1
                    self._trigger_event('liquidation_partial', position)
                    
                    logger.info(f"Partial liquidation: {position_id} - {size} units")
                else:
                    return False
                
                return True
                
            except Exception as e:
                logger.error(f"Partial liquidation error: {e}")
                return False
    
    def _execute_partial_liquidation(self, position: LiquidationPosition, size: float) -> bool:
        """
        Exécute une liquidation partielle
        
        Args:
            position: Position à liquider
            size: Taille à liquider
            
        Returns:
            bool: True si exécutée
        """
        # Simuler l'exécution d'une liquidation partielle
        # À implémenter avec des exchanges réels
        
        return True
    
    def cancel_liquidation(self, position_id: str) -> bool:
        """
        Annule une liquidation
        
        Args:
            position_id: ID de la position
            
        Returns:
            bool: True si annulée
        """
        with self._lock:
            position = self.liquidation_positions.get(position_id)
            if not position:
                return False
            
            if position.status not in [LiquidationStatus.PENDING, LiquidationStatus.IN_PROGRESS]:
                return False
            
            position.status = LiquidationStatus.CANCELLED
            self.active_liquidations.pop(position_id, None)
            self.stats['active_liquidations'] -= 1
            
            logger.info(f"Liquidation cancelled: {position_id}")
            return True
    
    def get_liquidation(self, position_id: str) -> Optional[LiquidationPosition]:
        """
        Récupère une liquidation
        
        Args:
            position_id: ID de la liquidation
            
        Returns:
            Optional[LiquidationPosition]: Position de liquidation
        """
        return self.liquidation_positions.get(position_id)
    
    def get_active_liquidations(self) -> List[LiquidationPosition]:
        """
        Récupère les liquidations actives
        
        Returns:
            List[LiquidationPosition]: Liquidations actives
        """
        return list(self.active_liquidations.values())
    
    def get_liquidations_by_type(self, liquidation_type: LiquidationType) -> List[LiquidationPosition]:
        """
        Récupère les liquidations par type
        
        Args:
            liquidation_type: Type de liquidation
            
        Returns:
            List[LiquidationPosition]: Liquidations
        """
        return [p for p in self.liquidation_positions.values() if p.type == liquidation_type]
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
    
    def calculate_metrics(self) -> LiquidationMetrics:
        """
        Calcule les métriques de liquidation
        
        Returns:
            LiquidationMetrics: Métriques calculées
        """
        with self._lock:
            completed = list(self.completed_liquidations.values())
            total = self.stats['total_liquidations']
            
            if not completed:
                return LiquidationMetrics(0,0,0,0,0,0,0)
            
            total_volume = sum(p.size for p in completed)
            total_pnl = sum(p.pnl for p in completed)
            
            # Temps d'exécution moyen
            execution_times = []
            for p in completed:
                if p.metadata.get('execution_time'):
                    execution_time = (p.metadata['execution_time'] - p.created_at).total_seconds()
                    execution_times.append(execution_time)
            
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
            
            # Taux de succès
            success_rate = self.stats['completed_liquidations'] / total if total > 0 else 0
            
            metrics = LiquidationMetrics(
                total_liquidations=total,
                total_volume=total_volume,
                total_pnl=total_pnl,
                avg_execution_time=avg_execution_time,
                success_rate=success_rate,
                partial_liquidations=self.stats['partial_liquidations'],
                failed_liquidations=self.stats['failed_liquidations']
            )
            
            self.metrics = metrics
            return metrics
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        metrics = self.calculate_metrics()
        self.stats.update({
            'total_volume': metrics.total_volume,
            'total_pnl': metrics.total_pnl,
            'avg_execution_time': metrics.avg_execution_time,
            'success_rate': metrics.success_rate,
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
                'total_liquidations': metrics.total_liquidations,
                'total_volume': metrics.total_volume,
                'total_pnl': metrics.total_pnl,
                'avg_execution_time': metrics.avg_execution_time,
                'success_rate': metrics.success_rate,
                'partial_liquidations': metrics.partial_liquidations,
                'failed_liquidations': metrics.failed_liquidations,
            },
            'active_liquidations': [
                {
                    'id': p.id,
                    'symbol': p.symbol,
                    'side': p.side,
                    'size': p.size,
                    'current_price': p.current_price,
                    'liquidation_price': p.liquidation_price,
                    'margin_used': p.margin_used,
                    'pnl': p.pnl,
                    'reason': p.reason,
                    'type': p.type.value,
                }
                for p in self.active_liquidations.values()
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
        
        logger.info("LiquidationManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("LiquidationManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_liquidations()
                self._check_emergency_liquidations()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_liquidations(self):
        """Met à jour les liquidations"""
        # À implémenter avec les prix réels
        pass
    
    def _check_emergency_liquidations(self):
        """Vérifie les liquidations d'urgence"""
        for position in self.active_liquidations.values():
            margin_ratio = position.margin_used / (position.size * position.current_price)
            if margin_ratio > self.config.emergency_threshold:
                # Déclencher une liquidation d'urgence
                position.type = LiquidationType.EMERGENCY
                self.execute_liquidation(position.id)
                self._add_alert(
                    f"Emergency liquidation: {position.symbol} - {margin_ratio:.1%} margin used",
                    "critical"
                )

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_liquidation_manager: Optional[LiquidationManager] = None

def get_liquidation_manager(
    config: Optional[LiquidationConfig] = None
) -> LiquidationManager:
    """
    Récupère le gestionnaire de liquidation (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        LiquidationManager: Gestionnaire de liquidation
    """
    global _liquidation_manager
    if _liquidation_manager is None:
        _liquidation_manager = LiquidationManager(config)
    return _liquidation_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'LiquidationType',
    'LiquidationStatus',
    'LiquidationPriority',
    'LiquidationOrder',
    'LiquidationPosition',
    'LiquidationMetrics',
    'LiquidationConfig',
    'LiquidationManager',
    'get_liquidation_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Liquidation manager module initialized")

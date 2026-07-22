"""
NEXUS AI TRADING SYSTEM - Hedge Bot Margin Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de marge pour le bot de couverture
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

class MarginMode(Enum):
    """Modes de marge"""
    ISOLATED = "isolated"
    CROSS = "cross"
    PORTFOLIO = "portfolio"
    HEDGED = "hedged"

class MarginType(Enum):
    """Types de marge"""
    INITIAL = "initial"
    MAINTENANCE = "maintenance"
    VARIATION = "variation"
    AVAILABLE = "available"
    USED = "used"

class MarginStatus(Enum):
    """Statuts de marge"""
    HEALTHY = "healthy"
    WARNING = "warning"
    MARGIN_CALL = "margin_call"
    LIQUIDATION = "liquidation"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class MarginAccount:
    """Compte de marge"""
    id: str
    total_balance: float
    available_balance: float
    used_margin: float
    maintenance_margin: float
    initial_margin: float
    equity: float
    margin_ratio: float
    mode: MarginMode
    status: MarginStatus
    last_update: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MarginPosition:
    """Position de marge"""
    id: str
    symbol: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    initial_margin: float
    maintenance_margin: float
    liquidation_price: float
    margin_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MarginMetrics:
    """Métriques de marge"""
    total_margin: float
    used_margin: float
    available_margin: float
    margin_ratio: float
    liquidation_risk: float
    total_pnl: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MarginConfig:
    """Configuration de marge"""
    enabled: bool = True
    initial_margin_rate: float = 0.10  # 10%
    maintenance_margin_rate: float = 0.05  # 5%
    margin_call_threshold: float = 0.80
    liquidation_threshold: float = 0.95
    auto_add_margin: bool = True
    max_margin_multiplier: float = 3.0
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# MARGIN MANAGER
# ============================================================

class MarginManager:
    """
    Gestionnaire de marge pour le bot de couverture
    
    Gère les comptes de marge, les positions et les appels de marge
    """
    
    def __init__(
        self,
        config: Optional[MarginConfig] = None,
        update_interval: int = 10,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de marge
        
        Args:
            config: Configuration de marge
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or MarginConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Comptes
        self.accounts: Dict[str, MarginAccount] = {}
        self.active_accounts: Dict[str, MarginAccount] = {}
        
        # Positions
        self.positions: Dict[str, MarginPosition] = {}
        self.open_positions: Dict[str, MarginPosition] = {}
        
        # Métriques
        self.metrics: Optional[MarginMetrics] = None
        
        # Statistiques
        self.stats = {
            'total_accounts': 0,
            'active_accounts': 0,
            'total_positions': 0,
            'open_positions': 0,
            'total_margin': 0.0,
            'used_margin': 0.0,
            'available_margin': 0.0,
            'margin_ratio': 0.0,
            'total_pnl': 0.0,
            'margin_calls': 0,
            'liquidations': 0,
        }
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'margin_call': [],
            'margin_added': [],
            'margin_released': [],
            'liquidation': [],
        }
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Capital total
        self.total_capital: float = 10000.0
        
        # Démarrer le monitoring
        if enable_monitoring and update_interval > 0:
            self.start()
        
        logger.info("MarginManager initialized")
    
    # ============================================================
    # ACCOUNT MANAGEMENT
    # ============================================================
    
    def create_account(
        self,
        account_id: str,
        initial_balance: float,
        mode: MarginMode = MarginMode.CROSS,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MarginAccount:
        """
        Crée un compte de marge
        
        Args:
            account_id: ID du compte
            initial_balance: Solde initial
            mode: Mode de marge
            metadata: Métadonnées
            
        Returns:
            MarginAccount: Compte créé
        """
        with self._lock:
            account = MarginAccount(
                id=account_id,
                total_balance=initial_balance,
                available_balance=initial_balance,
                used_margin=0.0,
                maintenance_margin=0.0,
                initial_margin=0.0,
                equity=initial_balance,
                margin_ratio=0.0,
                mode=mode,
                status=MarginStatus.HEALTHY,
                last_update=datetime.now(),
                metadata=metadata or {}
            )
            
            self.accounts[account_id] = account
            self.active_accounts[account_id] = account
            self.stats['total_accounts'] += 1
            self.stats['active_accounts'] += 1
            self.stats['total_margin'] += initial_balance
            
            logger.info(f"Margin account created: {account_id} - {initial_balance:.2f}")
            return account
    
    def update_account(self, account_id: str, balance_change: float) -> bool:
        """
        Met à jour un compte de marge
        
        Args:
            account_id: ID du compte
            balance_change: Changement de solde
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            account = self.accounts.get(account_id)
            if not account:
                return False
            
            account.total_balance += balance_change
            account.equity += balance_change
            account.available_balance += balance_change
            account.last_update = datetime.now()
            
            self._update_account_status(account)
            
            logger.debug(f"Account updated: {account_id} - {balance_change:.2f}")
            return True
    
    def _update_account_status(self, account: MarginAccount):
        """
        Met à jour le statut d'un compte
        
        Args:
            account: Compte à mettre à jour
        """
        # Calculer le ratio de marge
        if account.total_balance > 0:
            margin_ratio = account.used_margin / account.total_balance
        else:
            margin_ratio = 0.0
        
        account.margin_ratio = margin_ratio
        
        # Déterminer le statut
        if margin_ratio >= self.config.liquidation_threshold:
            account.status = MarginStatus.LIQUIDATION
            self._trigger_event('liquidation', account)
            self._add_alert(f"Liquidation: {account.id} - {margin_ratio:.1%}", "critical")
        elif margin_ratio >= self.config.margin_call_threshold:
            account.status = MarginStatus.MARGIN_CALL
            self._trigger_event('margin_call', account)
            self._add_alert(f"Margin call: {account.id} - {margin_ratio:.1%}", "warning")
        elif margin_ratio >= 0.6:
            account.status = MarginStatus.WARNING
        else:
            account.status = MarginStatus.HEALTHY
    
    # ============================================================
    # POSITION MANAGEMENT
    # ============================================================
    
    def add_position(
        self,
        symbol: str,
        size: float,
        entry_price: float,
        account_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MarginPosition:
        """
        Ajoute une position de marge
        
        Args:
            symbol: Symbole
            size: Taille
            entry_price: Prix d'entrée
            account_id: ID du compte
            metadata: Métadonnées
            
        Returns:
            MarginPosition: Position créée
        """
        with self._lock:
            account = self.accounts.get(account_id)
            if not account:
                raise ValueError(f"Account not found: {account_id}")
            
            # Calculer les marges
            initial_margin = size * entry_price * self.config.initial_margin_rate
            maintenance_margin = size * entry_price * self.config.maintenance_margin_rate
            
            # Vérifier la marge disponible
            if initial_margin > account.available_balance:
                raise ValueError(f"Insufficient margin: {initial_margin:.2f} > {account.available_balance:.2f}")
            
            # Calculer le prix de liquidation
            liquidation_price = self._calculate_liquidation_price(
                entry_price=entry_price,
                size=size,
                initial_margin=initial_margin,
                maintenance_margin=maintenance_margin
            )
            
            position = MarginPosition(
                id=f"margin_pos_{int(time.time())}_{symbol}",
                symbol=symbol,
                size=size,
                entry_price=entry_price,
                current_price=entry_price,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                initial_margin=initial_margin,
                maintenance_margin=maintenance_margin,
                liquidation_price=liquidation_price,
                margin_ratio=0.0,
                metadata=metadata or {}
            )
            
            self.positions[position.id] = position
            self.open_positions[position.id] = position
            self.stats['total_positions'] += 1
            self.stats['open_positions'] += 1
            
            # Mettre à jour le compte
            account.used_margin += initial_margin
            account.available_balance -= initial_margin
            account.maintenance_margin += maintenance_margin
            
            self._update_account_status(account)
            self._update_stats()
            
            logger.info(f"Margin position added: {position.id} - {symbol} - {size} @ {entry_price:.2f}")
            return position
    
    def _calculate_liquidation_price(
        self,
        entry_price: float,
        size: float,
        initial_margin: float,
        maintenance_margin: float
    ) -> float:
        """
        Calcule le prix de liquidation
        
        Args:
            entry_price: Prix d'entrée
            size: Taille
            initial_margin: Marge initiale
            maintenance_margin: Marge de maintenance
            
        Returns:
            float: Prix de liquidation
        """
        # Prix de liquidation simplifié
        # À implémenter avec des calculs plus précis selon l'exchange
        margin_ratio = initial_margin / (size * entry_price)
        
        if margin_ratio > 0:
            liquidation_price = entry_price * (1 - maintenance_margin / margin_ratio)
        else:
            liquidation_price = entry_price * 0.5
        
        return liquidation_price
    
    def update_position(
        self,
        position_id: str,
        current_price: float,
        account_id: str
    ) -> bool:
        """
        Met à jour une position de marge
        
        Args:
            position_id: ID de la position
            current_price: Prix actuel
            account_id: ID du compte
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            account = self.accounts.get(account_id)
            if not account:
                return False
            
            position.current_price = current_price
            
            # Calculer le P&L
            if position.size > 0:
                position.unrealized_pnl = (current_price - position.entry_price) * position.size
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * abs(position.size)
            
            # Mettre à jour le compte
            account.equity = account.total_balance + position.unrealized_pnl
            account.margin_ratio = account.used_margin / account.equity if account.equity > 0 else 0
            
            # Vérifier la liquidation
            if current_price <= position.liquidation_price:
                self._liquidate_position(position_id, account_id)
                return True
            
            self._update_account_status(account)
            self._update_stats()
            
            return True
    
    def _liquidate_position(self, position_id: str, account_id: str) -> bool:
        """
        Liquide une position de marge
        
        Args:
            position_id: ID de la position
            account_id: ID du compte
            
        Returns:
            bool: True si liquidée
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            account = self.accounts.get(account_id)
            if not account:
                return False
            
            # Libérer la marge
            account.used_margin -= position.initial_margin
            account.available_balance += position.initial_margin
            
            # Enregistrer le P&L réalisé
            position.realized_pnl = position.unrealized_pnl
            
            # Retirer la position
            self.open_positions.pop(position_id, None)
            self.stats['open_positions'] -= 1
            
            self._update_account_status(account)
            self._trigger_event('liquidation', position)
            self._add_alert(f"Position liquidated: {position_id}", "critical")
            
            logger.warning(f"Position liquidated: {position_id}")
            return True
    
    def close_position(self, position_id: str, account_id: str) -> bool:
        """
        Ferme une position de marge
        
        Args:
            position_id: ID de la position
            account_id: ID du compte
            
        Returns:
            bool: True si fermée
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            account = self.accounts.get(account_id)
            if not account:
                return False
            
            # Libérer la marge
            account.used_margin -= position.initial_margin
            account.available_balance += position.initial_margin
            
            # Enregistrer le P&L réalisé
            position.realized_pnl = position.unrealized_pnl
            
            # Retirer la position
            self.open_positions.pop(position_id, None)
            self.stats['open_positions'] -= 1
            
            self._update_account_status(account)
            self._update_stats()
            
            logger.info(f"Position closed: {position_id}")
            return True
    
    # ============================================================
    # MARGIN OPERATIONS
    # ============================================================
    
    def add_margin(self, account_id: str, amount: float) -> bool:
        """
        Ajoute de la marge à un compte
        
        Args:
            account_id: ID du compte
            amount: Montant à ajouter
            
        Returns:
            bool: True si ajouté
        """
        with self._lock:
            account = self.accounts.get(account_id)
            if not account:
                return False
            
            account.total_balance += amount
            account.available_balance += amount
            account.equity += amount
            account.last_update = datetime.now()
            
            self._update_account_status(account)
            self._trigger_event('margin_added', account)
            
            logger.info(f"Margin added: {account_id} - {amount:.2f}")
            return True
    
    def release_margin(self, account_id: str, amount: float) -> bool:
        """
        Libère de la marge d'un compte
        
        Args:
            account_id: ID du compte
            amount: Montant à libérer
            
        Returns:
            bool: True si libéré
        """
        with self._lock:
            account = self.accounts.get(account_id)
            if not account:
                return False
            
            if amount > account.available_balance:
                return False
            
            account.total_balance -= amount
            account.available_balance -= amount
            account.equity -= amount
            account.last_update = datetime.now()
            
            self._update_account_status(account)
            self._trigger_event('margin_released', account)
            
            logger.info(f"Margin released: {account_id} - {amount:.2f}")
            return True
    
    def get_account(self, account_id: str) -> Optional[MarginAccount]:
        """
        Récupère un compte de marge
        
        Args:
            account_id: ID du compte
            
        Returns:
            Optional[MarginAccount]: Compte
        """
        return self.accounts.get(account_id)
    
    def get_position(self, position_id: str) -> Optional[MarginPosition]:
        """
        Récupère une position de marge
        
        Args:
            position_id: ID de la position
            
        Returns:
            Optional[MarginPosition]: Position
        """
        return self.positions.get(position_id)
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
    
    def calculate_metrics(self) -> MarginMetrics:
        """
        Calcule les métriques de marge
        
        Returns:
            MarginMetrics: Métriques calculées
        """
        with self._lock:
            total_margin = sum(a.total_balance for a in self.accounts.values())
            used_margin = sum(a.used_margin for a in self.accounts.values())
            available_margin = sum(a.available_balance for a in self.accounts.values())
            
            # Ratio de marge total
            margin_ratio = used_margin / total_margin if total_margin > 0 else 0
            
            # Risque de liquidation
            liquidation_risk = 0.0
            for account in self.accounts.values():
                if account.margin_ratio > liquidation_risk:
                    liquidation_risk = account.margin_ratio
            
            # P&L total
            total_pnl = sum(p.unrealized_pnl + p.realized_pnl for p in self.positions.values())
            
            metrics = MarginMetrics(
                total_margin=total_margin,
                used_margin=used_margin,
                available_margin=available_margin,
                margin_ratio=margin_ratio,
                liquidation_risk=liquidation_risk,
                total_pnl=total_pnl
            )
            
            self.metrics = metrics
            return metrics
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        metrics = self.calculate_metrics()
        self.stats.update({
            'total_margin': metrics.total_margin,
            'used_margin': metrics.used_margin,
            'available_margin': metrics.available_margin,
            'margin_ratio': metrics.margin_ratio,
            'total_pnl': metrics.total_pnl,
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
                'total_margin': metrics.total_margin,
                'used_margin': metrics.used_margin,
                'available_margin': metrics.available_margin,
                'margin_ratio': metrics.margin_ratio,
                'liquidation_risk': metrics.liquidation_risk,
                'total_pnl': metrics.total_pnl,
            },
            'accounts': [
                {
                    'id': a.id,
                    'total_balance': a.total_balance,
                    'available_balance': a.available_balance,
                    'used_margin': a.used_margin,
                    'margin_ratio': a.margin_ratio,
                    'status': a.status.value,
                }
                for a in self.accounts.values()
            ],
            'open_positions': [
                {
                    'id': p.id,
                    'symbol': p.symbol,
                    'size': p.size,
                    'entry_price': p.entry_price,
                    'current_price': p.current_price,
                    'unrealized_pnl': p.unrealized_pnl,
                    'liquidation_price': p.liquidation_price,
                }
                for p in self.open_positions.values()
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
        
        logger.info("MarginManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("MarginManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_positions()
                self._check_margin_calls()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_positions(self):
        """Met à jour les positions"""
        # À implémenter avec les prix réels
        pass
    
    def _check_margin_calls(self):
        """Vérifie les appels de marge"""
        for account in self.accounts.values():
            if account.status == MarginStatus.MARGIN_CALL:
                self._add_alert(
                    f"Margin call: {account.id} - {account.margin_ratio:.1%}",
                    "warning"
                )
            elif account.status == MarginStatus.LIQUIDATION:
                self._add_alert(
                    f"Liquidation: {account.id} - {account.margin_ratio:.1%}",
                    "critical"
                )

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_margin_manager: Optional[MarginManager] = None

def get_margin_manager(
    config: Optional[MarginConfig] = None
) -> MarginManager:
    """
    Récupère le gestionnaire de marge (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        MarginManager: Gestionnaire de marge
    """
    global _margin_manager
    if _margin_manager is None:
        _margin_manager = MarginManager(config)
    return _margin_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'MarginMode',
    'MarginType',
    'MarginStatus',
    'MarginAccount',
    'MarginPosition',
    'MarginMetrics',
    'MarginConfig',
    'MarginManager',
    'get_margin_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Margin manager module initialized")

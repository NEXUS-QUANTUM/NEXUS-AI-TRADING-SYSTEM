"""
NEXUS AI TRADING SYSTEM - Hedge Bot Spot Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de spot pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import json
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

class SpotType(Enum):
    """Types de spot"""
    CRYPTO = "crypto"
    FOREX = "forex"
    STOCK = "stock"
    COMMODITY = "commodity"
    INDEX = "index"
    ETF = "etf"
    BOND = "bond"

class SpotOrderType(Enum):
    """Types d'ordres spot"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"

class SpotOrderSide(Enum):
    """Côtés des ordres spot"""
    BUY = "buy"
    SELL = "sell"

class SpotOrderStatus(Enum):
    """Statuts des ordres spot"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class SpotPosition:
    """Position spot"""
    id: str
    symbol: str
    exchange: str
    side: SpotOrderSide
    size: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_percent: float
    entry_time: datetime
    last_update: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SpotBalance:
    """Balance spot"""
    asset: str
    free: float
    locked: float
    total: float
    usd_value: float
    last_update: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SpotOrder:
    """Ordre spot"""
    id: str
    symbol: str
    exchange: str
    side: SpotOrderSide
    type: SpotOrderType
    size: float
    price: Optional[float]
    stop_price: Optional[float]
    limit_price: Optional[float]
    status: SpotOrderStatus
    filled_size: float
    avg_price: Optional[float]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SpotConfig:
    """Configuration spot"""
    enabled: bool = True
    max_positions: int = 10
    max_position_size: float = 10000.0
    min_position_size: float = 1.0
    default_leverage: float = 1.0
    stop_loss_percent: float = 0.02
    take_profit_percent: float = 0.03
    slippage_tolerance: float = 0.005
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# SPOT MANAGER
# ============================================================

class SpotManager:
    """
    Gestionnaire de spot pour le bot de couverture
    
    Gère les positions, ordres et balances spot
    """
    
    def __init__(
        self,
        config: Optional[SpotConfig] = None,
        update_interval: int = 5,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de spot
        
        Args:
            config: Configuration spot
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or SpotConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Positions
        self.positions: Dict[str, SpotPosition] = {}
        self.open_positions: Dict[str, SpotPosition] = {}
        self.closed_positions: Dict[str, SpotPosition] = {}
        
        # Ordres
        self.orders: Dict[str, SpotOrder] = {}
        self.open_orders: Dict[str, SpotOrder] = {}
        self.filled_orders: Dict[str, SpotOrder] = {}
        
        # Balances
        self.balances: Dict[str, SpotBalance] = {}
        
        # Statistiques
        self.stats = {
            'total_positions': 0,
            'open_positions': 0,
            'closed_positions': 0,
            'total_orders': 0,
            'open_orders': 0,
            'filled_orders': 0,
            'total_pnl': 0.0,
            'total_volume': 0.0,
            'total_value': 0.0,
            'by_symbol': {},
            'by_exchange': {},
        }
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'position_opened': [],
            'position_closed': [],
            'order_placed': [],
            'order_filled': [],
            'balance_updated': [],
        }
        
        # Démarrer le monitoring
        if enable_monitoring and update_interval > 0:
            self.start()
        
        logger.info("SpotManager initialized")
    
    # ============================================================
    # POSITION MANAGEMENT
    # ============================================================
    
    def open_position(
        self,
        symbol: str,
        exchange: str,
        side: SpotOrderSide,
        size: float,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SpotPosition:
        """
        Ouvre une position spot
        
        Args:
            symbol: Symbole
            exchange: Exchange
            side: Côté
            size: Taille
            price: Prix
            metadata: Métadonnées
            
        Returns:
            SpotPosition: Position ouverte
        """
        with self._lock:
            # Vérifier les limites
            if len(self.open_positions) >= self.config.max_positions:
                raise ValueError(f"Maximum positions reached: {self.config.max_positions}")
            
            if size > self.config.max_position_size:
                raise ValueError(f"Position size exceeds maximum: {self.config.max_position_size}")
            
            if size < self.config.min_position_size:
                raise ValueError(f"Position size below minimum: {self.config.min_position_size}")
            
            position = SpotPosition(
                id=f"spot_{int(time.time())}_{symbol}",
                symbol=symbol,
                exchange=exchange,
                side=side,
                size=size,
                entry_price=price,
                current_price=price,
                pnl=0.0,
                pnl_percent=0.0,
                entry_time=datetime.now(),
                last_update=datetime.now(),
                metadata=metadata or {}
            )
            
            self.positions[position.id] = position
            self.open_positions[position.id] = position
            self.stats['total_positions'] += 1
            self.stats['open_positions'] += 1
            
            self._update_stats()
            self._trigger_event('position_opened', position)
            
            logger.info(f"Spot position opened: {symbol} {side.value} {size} @ {price:.2f}")
            return position
    
    def close_position(self, position_id: str, price: float) -> bool:
        """
        Ferme une position spot
        
        Args:
            position_id: ID de la position
            price: Prix de fermeture
            
        Returns:
            bool: True si fermée
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            # Calculer le P&L
            if position.side == SpotOrderSide.BUY:
                pnl = (price - position.entry_price) * position.size
            else:
                pnl = (position.entry_price - price) * position.size
            
            position.pnl = pnl
            position.pnl_percent = (pnl / (position.entry_price * position.size)) * 100
            position.current_price = price
            position.last_update = datetime.now()
            
            self.open_positions.pop(position_id, None)
            self.closed_positions[position_id] = position
            self.stats['open_positions'] -= 1
            self.stats['closed_positions'] += 1
            self.stats['total_pnl'] += pnl
            
            self._update_stats()
            self._trigger_event('position_closed', position)
            
            logger.info(f"Spot position closed: {position.symbol} PNL: ${pnl:.2f}")
            return True
    
    def update_position_price(self, position_id: str, price: float) -> bool:
        """
        Met à jour le prix d'une position
        
        Args:
            position_id: ID de la position
            price: Prix actuel
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            position = self.positions.get(position_id)
            if not position:
                return False
            
            position.current_price = price
            position.last_update = datetime.now()
            
            # Mettre à jour le P&L
            if position.side == SpotOrderSide.BUY:
                pnl = (price - position.entry_price) * position.size
            else:
                pnl = (position.entry_price - price) * position.size
            
            position.pnl = pnl
            position.pnl_percent = (pnl / (position.entry_price * position.size)) * 100
            
            return True
    
    def get_position(self, position_id: str) -> Optional[SpotPosition]:
        """
        Récupère une position spot
        
        Args:
            position_id: ID de la position
            
        Returns:
            Optional[SpotPosition]: Position
        """
        return self.positions.get(position_id)
    
    def get_open_positions(self) -> List[SpotPosition]:
        """
        Récupère les positions ouvertes
        
        Returns:
            List[SpotPosition]: Positions ouvertes
        """
        return list(self.open_positions.values())
    
    def get_positions_by_symbol(self, symbol: str) -> List[SpotPosition]:
        """
        Récupère les positions par symbole
        
        Args:
            symbol: Symbole
            
        Returns:
            List[SpotPosition]: Positions
        """
        return [p for p in self.positions.values() if p.symbol == symbol]
    
    # ============================================================
    # ORDER MANAGEMENT
    # ============================================================
    
    def place_order(
        self,
        symbol: str,
        exchange: str,
        side: SpotOrderSide,
        size: float,
        order_type: SpotOrderType = SpotOrderType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SpotOrder:
        """
        Place un ordre spot
        
        Args:
            symbol: Symbole
            exchange: Exchange
            side: Côté
            size: Taille
            order_type: Type d'ordre
            price: Prix
            stop_price: Prix stop
            limit_price: Prix limit
            metadata: Métadonnées
            
        Returns:
            SpotOrder: Ordre placé
        """
        with self._lock:
            order = SpotOrder(
                id=f"order_{int(time.time())}_{symbol}",
                symbol=symbol,
                exchange=exchange,
                side=side,
                type=order_type,
                size=size,
                price=price,
                stop_price=stop_price,
                limit_price=limit_price,
                status=SpotOrderStatus.PENDING,
                filled_size=0.0,
                avg_price=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata=metadata or {}
            )
            
            self.orders[order.id] = order
            self.open_orders[order.id] = order
            self.stats['total_orders'] += 1
            self.stats['open_orders'] += 1
            
            self._trigger_event('order_placed', order)
            
            logger.info(f"Spot order placed: {symbol} {side.value} {size} {order_type.value}")
            return order
    
    def fill_order(self, order_id: str, price: float, size: float) -> bool:
        """
        Remplit un ordre spot
        
        Args:
            order_id: ID de l'ordre
            price: Prix d'exécution
            size: Taille exécutée
            
        Returns:
            bool: True si rempli
        """
        with self._lock:
            order = self.orders.get(order_id)
            if not order:
                return False
            
            order.filled_size += size
            order.avg_price = price
            order.updated_at = datetime.now()
            order.status = SpotOrderStatus.PARTIALLY_FILLED
            
            if order.filled_size >= order.size:
                order.status = SpotOrderStatus.FILLED
                self.open_orders.pop(order_id, None)
                self.filled_orders[order_id] = order
                self.stats['open_orders'] -= 1
                self.stats['filled_orders'] += 1
                self._trigger_event('order_filled', order)
            
            # Ouvrir une position si nécessaire
            if order.metadata.get('open_position', False) and order.status == SpotOrderStatus.FILLED:
                self.open_position(
                    symbol=order.symbol,
                    exchange=order.exchange,
                    side=order.side,
                    size=order.filled_size,
                    price=order.avg_price or price,
                    metadata={'order_id': order_id}
                )
            
            return True
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Annule un ordre spot
        
        Args:
            order_id: ID de l'ordre
            
        Returns:
            bool: True si annulé
        """
        with self._lock:
            order = self.orders.get(order_id)
            if not order:
                return False
            
            if order.status in [SpotOrderStatus.FILLED, SpotOrderStatus.CANCELLED]:
                return False
            
            order.status = SpotOrderStatus.CANCELLED
            order.updated_at = datetime.now()
            self.open_orders.pop(order_id, None)
            self.stats['open_orders'] -= 1
            
            logger.info(f"Spot order cancelled: {order_id}")
            return True
    
    def get_order(self, order_id: str) -> Optional[SpotOrder]:
        """
        Récupère un ordre spot
        
        Args:
            order_id: ID de l'ordre
            
        Returns:
            Optional[SpotOrder]: Ordre
        """
        return self.orders.get(order_id)
    
    def get_open_orders(self) -> List[SpotOrder]:
        """
        Récupère les ordres ouverts
        
        Returns:
            List[SpotOrder]: Ordres ouverts
        """
        return list(self.open_orders.values())
    
    # ============================================================
    # BALANCE MANAGEMENT
    # ============================================================
    
    def update_balance(
        self,
        asset: str,
        free: float,
        locked: float = 0.0,
        usd_value: Optional[float] = None
    ) -> SpotBalance:
        """
        Met à jour une balance
        
        Args:
            asset: Actif
            free: Montant libre
            locked: Montant verrouillé
            usd_value: Valeur en USD
            
        Returns:
            SpotBalance: Balance mise à jour
        """
        with self._lock:
            balance = self.balances.get(asset, SpotBalance(
                asset=asset,
                free=0.0,
                locked=0.0,
                total=0.0,
                usd_value=0.0
            ))
            
            balance.free = free
            balance.locked = locked
            balance.total = free + locked
            if usd_value is not None:
                balance.usd_value = usd_value
            balance.last_update = datetime.now()
            
            self.balances[asset] = balance
            self._trigger_event('balance_updated', balance)
            
            return balance
    
    def get_balance(self, asset: str) -> Optional[SpotBalance]:
        """
        Récupère une balance
        
        Args:
            asset: Actif
            
        Returns:
            Optional[SpotBalance]: Balance
        """
        return self.balances.get(asset)
    
    def get_all_balances(self) -> Dict[str, SpotBalance]:
        """
        Récupère toutes les balances
        
        Returns:
            Dict[str, SpotBalance]: Balances
        """
        return self.balances.copy()
    
    def get_total_value(self) -> float:
        """
        Récupère la valeur totale en USD
        
        Returns:
            float: Valeur totale
        """
        return sum(b.usd_value for b in self.balances.values())
    
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
    # STATISTICS
    # ============================================================
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        with self._lock:
            # Par symbole
            by_symbol = {}
            for position in self.positions.values():
                by_symbol[position.symbol] = by_symbol.get(position.symbol, 0) + 1
            self.stats['by_symbol'] = by_symbol
            
            # Par exchange
            by_exchange = {}
            for position in self.positions.values():
                by_exchange[position.exchange] = by_exchange.get(position.exchange, 0) + 1
            self.stats['by_exchange'] = by_exchange
            
            # Volume total
            self.stats['total_volume'] = sum(p.size for p in self.positions.values())
            
            # Valeur totale
            self.stats['total_value'] = sum(p.current_price * p.size for p in self.open_positions.values())
    
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
        return {
            'timestamp': time.time(),
            'stats': self.get_stats(),
            'open_positions': [
                {
                    'id': p.id,
                    'symbol': p.symbol,
                    'side': p.side.value,
                    'size': p.size,
                    'entry_price': p.entry_price,
                    'current_price': p.current_price,
                    'pnl': p.pnl,
                    'pnl_percent': p.pnl_percent,
                }
                for p in self.open_positions.values()
            ],
            'open_orders': [
                {
                    'id': o.id,
                    'symbol': o.symbol,
                    'side': o.side.value,
                    'type': o.type.value,
                    'size': o.size,
                    'price': o.price,
                    'status': o.status.value,
                }
                for o in self.open_orders.values()
            ],
            'balances': [
                {
                    'asset': b.asset,
                    'free': b.free,
                    'locked': b.locked,
                    'total': b.total,
                    'usd_value': b.usd_value,
                }
                for b in self.balances.values()
            ],
            'alerts': self.alerts[-10:],
        }
    
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
        
        logger.info("SpotManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("SpotManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_prices()
                self._check_stop_loss()
                self._check_take_profit()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_prices(self):
        """Met à jour les prix"""
        # À implémenter avec les prix réels
        pass
    
    def _check_stop_loss(self):
        """Vérifie les stop loss"""
        for position in self.open_positions.values():
            if position.metadata.get('stop_loss'):
                stop_price = position.metadata['stop_loss']
                if position.side == SpotOrderSide.BUY and position.current_price <= stop_price:
                    self.close_position(position.id, position.current_price)
                    self._add_alert(f"Stop loss triggered: {position.symbol} @ {position.current_price:.2f}", "warning")
                elif position.side == SpotOrderSide.SELL and position.current_price >= stop_price:
                    self.close_position(position.id, position.current_price)
                    self._add_alert(f"Stop loss triggered: {position.symbol} @ {position.current_price:.2f}", "warning")
    
    def _check_take_profit(self):
        """Vérifie les take profit"""
        for position in self.open_positions.values():
            if position.metadata.get('take_profit'):
                take_price = position.metadata['take_profit']
                if position.side == SpotOrderSide.BUY and position.current_price >= take_price:
                    self.close_position(position.id, position.current_price)
                    self._add_alert(f"Take profit triggered: {position.symbol} @ {position.current_price:.2f}", "success")
                elif position.side == SpotOrderSide.SELL and position.current_price <= take_price:
                    self.close_position(position.id, position.current_price)
                    self._add_alert(f"Take profit triggered: {position.symbol} @ {position.current_price:.2f}", "success")
    
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
# SINGLETON INSTANCE
# ============================================================

_spot_manager: Optional[SpotManager] = None

def get_spot_manager(
    config: Optional[SpotConfig] = None
) -> SpotManager:
    """
    Récupère le gestionnaire de spot (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        SpotManager: Gestionnaire de spot
    """
    global _spot_manager
    if _spot_manager is None:
        _spot_manager = SpotManager(config)
    return _spot_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'SpotType',
    'SpotOrderType',
    'SpotOrderSide',
    'SpotOrderStatus',
    'SpotPosition',
    'SpotBalance',
    'SpotOrder',
    'SpotConfig',
    'SpotManager',
    'get_spot_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Spot manager module initialized")

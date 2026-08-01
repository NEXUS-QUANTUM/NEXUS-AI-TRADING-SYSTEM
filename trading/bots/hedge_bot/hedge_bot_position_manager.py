# trading/bots/hedge_bot/hedge_bot_position_manager.py
# Advanced Position Management & Monitoring Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Position Manager Module - Module avancé de gestion et de monitoring des positions
pour le Hedge Bot. Gère l'ouverture, la fermeture, le suivi des positions, l'ajustement
des stops, la gestion des risques et le reporting des positions de hedging.
"""

import asyncio
import json
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_position_manager")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult, OrderStatus
)


# ============== ENUMS & TYPES ==============

class PositionStatus(Enum):
    """Statuts des positions."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PositionType(Enum):
    """Types de positions."""
    LONG = "long"
    SHORT = "short"
    HEDGE = "hedge"
    SPREAD = "spread"
    OPTION = "option"


class PositionRisk(Enum):
    """Niveaux de risque des positions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============== DATA MODELS ==============

@dataclass
class Position:
    """Modèle de position."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    position_type: PositionType = PositionType.LONG
    entry_price: float = 0.0
    current_price: float = 0.0
    quantity: float = 0.0
    filled_quantity: float = 0.0
    average_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    status: PositionStatus = PositionStatus.PENDING
    pnl: float = 0.0
    pnl_percent: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    risk_level: PositionRisk = PositionRisk.MEDIUM
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    decision_id: Optional[str] = None
    strategy: Optional[str] = None
    hedge_ratio: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "position_type": self.position_type.value,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "trailing_stop": self.trailing_stop,
            "status": self.status.value,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "risk_level": self.risk_level.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "metadata": self.metadata,
            "tags": self.tags,
            "decision_id": self.decision_id,
            "strategy": self.strategy,
            "hedge_ratio": self.hedge_ratio
        }


@dataclass
class PositionUpdate:
    """Mise à jour de position."""
    update_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = ""
    field: str = ""
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionSummary:
    """Résumé des positions."""
    summary_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_positions: int = 0
    open_positions: int = 0
    closed_positions: int = 0
    total_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    total_exposure: float = 0.0
    average_risk: float = 0.0
    positions_by_type: Dict[str, int] = field(default_factory=dict)
    positions_by_risk: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class PositionManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de positions."""
    
    @abstractmethod
    async def open_position(self, config: Dict[str, Any]) -> Position:
        """Ouvre une position."""
        pass
    
    @abstractmethod
    async def close_position(self, position_id: str) -> bool:
        """Ferme une position."""
        pass
    
    @abstractmethod
    async def update_position(self, position_id: str, price: float) -> Optional[Position]:
        """Met à jour une position."""
        pass
    
    @abstractmethod
    async def get_position(self, position_id: str) -> Optional[Position]:
        """Récupère une position."""
        pass


# ============== IMPLÉMENTATION ==============

class PositionManager(PositionManagerInterface):
    """
    Gestionnaire de positions avancé pour le Hedge Bot.
    Gère l'ouverture, le suivi et la fermeture des positions.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des positions
        self._positions: Dict[str, Position] = {}
        self._positions_lock = threading.RLock()
        
        # Gestion des mises à jour
        self._updates: Dict[str, List[PositionUpdate]] = defaultdict(list)
        self._updates_lock = threading.RLock()
        
        # Gestion des summaries
        self._summaries: List[PositionSummary] = []
        self._summary_lock = threading.RLock()
        
        # Cache des prix
        self._price_cache: Dict[str, float] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "positions_opened": 0,
            "positions_closed": 0,
            "positions_updated": 0,
            "total_pnl": 0.0,
            "winning_positions": 0,
            "losing_positions": 0,
            "win_rate": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "max_profit": 0.0,
            "max_loss": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PositionManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_position_type": PositionType.LONG,
            "default_risk_level": PositionRisk.MEDIUM,
            "max_positions": 100,
            "min_position_size": 0.01,
            "max_position_size": 1000000,
            "default_stop_loss_pct": 0.02,
            "default_take_profit_pct": 0.04,
            "monitoring_interval": 1.0,
            "update_interval": 5.0,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "auto_monitor": True,
            "auto_close_at_target": True,
            "history_retention_days": 30
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire de positions."""
        logger.info("PositionManager starting...")
        self._is_running = True
        
        # Chargement des positions existantes
        await self._load_positions()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._position_monitor())
        asyncio.create_task(self._price_updater())
        asyncio.create_task(self._summary_generator())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PositionManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de positions."""
        logger.info("PositionManager stopping...")
        self._is_running = False
        
        # Sauvegarde des positions
        await self._save_positions()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("PositionManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def open_position(self, config: Dict[str, Any]) -> Position:
        """Ouvre une position."""
        self._stats["positions_opened"] += 1
        
        symbol = config.get("symbol", "")
        position_type = PositionType(config.get("position_type", "long"))
        entry_price = config.get("entry_price", 0.0)
        quantity = config.get("quantity", 0.0)
        
        # Validation
        if entry_price <= 0:
            raise ValueError("Invalid entry price")
        
        if quantity <= 0:
            raise ValueError("Invalid quantity")
        
        # Création de la position
        position = Position(
            symbol=symbol,
            position_type=position_type,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            filled_quantity=quantity,
            average_price=entry_price,
            stop_loss=config.get("stop_loss"),
            take_profit=config.get("take_profit"),
            trailing_stop=config.get("trailing_stop"),
            status=PositionStatus.OPEN,
            risk_level=PositionRisk(config.get("risk_level", "medium")),
            decision_id=config.get("decision_id"),
            strategy=config.get("strategy"),
            hedge_ratio=config.get("hedge_ratio", 0.0),
            metadata=config.get("metadata", {})
        )
        
        with self._positions_lock:
            self._positions[position.position_id] = position
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"position:{position.position_id}",
                position.to_dict(),
                DataType.POSITION
            )
        
        logger.info(f"Position opened: {symbol} {position_type.value} quantity={quantity} price={entry_price}")
        return position
    
    async def close_position(self, position_id: str) -> bool:
        """Ferme une position."""
        with self._positions_lock:
            position = self._positions.get(position_id)
            if not position or position.status == PositionStatus.CLOSED:
                return False
            
            # Mise à jour du PnL
            position.realized_pnl = position.pnl
            position.status = PositionStatus.CLOSED
            position.closed_at = datetime.now(timezone.utc)
            
            self._stats["positions_closed"] += 1
            self._stats["total_pnl"] += position.pnl
            
            if position.pnl > 0:
                self._stats["winning_positions"] += 1
                self._stats["avg_profit"] = (
                    self._stats["avg_profit"] * 0.9 + position.pnl * 0.1
                )
                self._stats["max_profit"] = max(self._stats["max_profit"], position.pnl)
            else:
                self._stats["losing_positions"] += 1
                self._stats["avg_loss"] = (
                    self._stats["avg_loss"] * 0.9 + abs(position.pnl) * 0.1
                )
                self._stats["max_loss"] = min(self._stats["max_loss"], position.pnl)
            
            # Mise à jour du win rate
            total = self._stats["winning_positions"] + self._stats["losing_positions"]
            if total > 0:
                self._stats["win_rate"] = self._stats["winning_positions"] / total
        
        logger.info(f"Position closed: {position.symbol} pnl={position.pnl:.2f}")
        return True
    
    async def update_position(self, position_id: str, price: float) -> Optional[Position]:
        """Met à jour une position."""
        self._stats["positions_updated"] += 1
        
        with self._positions_lock:
            position = self._positions.get(position_id)
            if not position or position.status == PositionStatus.CLOSED:
                return None
            
            # Mise à jour du prix
            old_price = position.current_price
            position.current_price = price
            
            # Calcul du PnL
            if position.position_type == PositionType.LONG:
                position.unrealized_pnl = (price - position.average_price) * position.filled_quantity
            else:
                position.unrealized_pnl = (position.average_price - price) * position.filled_quantity
            
            position.pnl = position.realized_pnl + position.unrealized_pnl
            position.pnl_percent = (position.pnl / (position.average_price * position.filled_quantity)) * 100
            
            # Mise à jour du max profit/loss
            if position.pnl > position.max_profit:
                position.max_profit = position.pnl
            if position.pnl < position.max_loss:
                position.max_loss = position.pnl
            
            position.updated_at = datetime.now(timezone.utc)
            
            # Vérification des targets
            if self.config["auto_close_at_target"]:
                if position.take_profit and price >= position.take_profit:
                    await self.close_position(position_id)
                    logger.info(f"Take profit hit for {position.symbol}: {price}")
                elif position.stop_loss and price <= position.stop_loss:
                    await self.close_position(position_id)
                    logger.info(f"Stop loss hit for {position.symbol}: {price}")
            
            return position
    
    async def get_position(self, position_id: str) -> Optional[Position]:
        """Récupère une position."""
        with self._positions_lock:
            return self._positions.get(position_id)
    
    # ========== MÉTHODES PRIVÉES - MONITORING ==========
    
    async def _position_monitor(self) -> None:
        """Monitor les positions en continu."""
        while self._is_running:
            await asyncio.sleep(self.config["monitoring_interval"])
            
            try:
                with self._positions_lock:
                    for position in self._positions.values():
                        if position.status == PositionStatus.OPEN:
                            # Récupération du prix actuel
                            if self.data_manager:
                                price_data = await self.data_manager.retrieve(
                                    f"market:{position.symbol}:price",
                                    DataType.MARKET
                                )
                                if price_data:
                                    current_price = price_data.get("price", 0.0)
                                    await self.update_position(position.position_id, current_price)
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
    
    async def _price_updater(self) -> None:
        """Met à jour les prix en cache."""
        while self._is_running:
            await asyncio.sleep(self.config["update_interval"])
            
            try:
                if self.data_manager:
                    # Récupération des prix pour tous les symboles
                    for position in self._positions.values():
                        if position.status == PositionStatus.OPEN:
                            price_data = await self.data_manager.retrieve(
                                f"market:{position.symbol}:price",
                                DataType.MARKET
                            )
                            if price_data:
                                with self._cache_lock:
                                    self._price_cache[position.symbol] = price_data.get("price", 0.0)
                
            except Exception as e:
                logger.error(f"Price updater error: {e}")
    
    async def _summary_generator(self) -> None:
        """Génère des résumés de positions périodiques."""
        while self._is_running:
            await asyncio.sleep(60)  # 1 minute
            
            try:
                summary = await self._generate_summary()
                
                with self._summary_lock:
                    self._summaries.append(summary)
                    if len(self._summaries) > 1000:
                        self._summaries = self._summaries[-1000:]
                
            except Exception as e:
                logger.error(f"Summary generator error: {e}")
    
    async def _generate_summary(self) -> PositionSummary:
        """Génère un résumé des positions."""
        with self._positions_lock:
            positions = list(self._positions.values())
        
        summary = PositionSummary(
            total_positions=len(positions),
            open_positions=sum(1 for p in positions if p.status == PositionStatus.OPEN),
            closed_positions=sum(1 for p in positions if p.status == PositionStatus.CLOSED),
            total_pnl=sum(p.pnl for p in positions),
            total_unrealized_pnl=sum(p.unrealized_pnl for p in positions if p.status == PositionStatus.OPEN),
            total_realized_pnl=sum(p.realized_pnl for p in positions if p.status == PositionStatus.CLOSED),
            total_exposure=sum(p.quantity * p.current_price for p in positions if p.status == PositionStatus.OPEN),
            average_risk=np.mean([p.risk_level.value for p in positions]) if positions else 0,
            positions_by_type={},
            positions_by_risk={}
        )
        
        # Positions par type
        for p in positions:
            summary.positions_by_type[p.position_type.value] = (
                summary.positions_by_type.get(p.position_type.value, 0) + 1
            )
            summary.positions_by_risk[p.risk_level.value] = (
                summary.positions_by_risk.get(p.risk_level.value, 0) + 1
            )
        
        return summary
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._positions_lock:
                    self._stats["total_positions"] = len(self._positions)
                    open_positions = len([p for p in self._positions.values() if p.status == PositionStatus.OPEN])
                    self._stats["open_positions"] = open_positions
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "position:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_positions(self) -> None:
        """Charge les positions existantes."""
        try:
            if self.data_manager:
                positions_data = await self.data_manager.retrieve(
                    "positions:all",
                    DataType.POSITION
                )
                
                if positions_data:
                    for pos_dict in positions_data:
                        position = self._deserialize_position(pos_dict)
                        if position:
                            with self._positions_lock:
                                self._positions[position.position_id] = position
            
            logger.info(f"Loaded {len(self._positions)} positions")
            
        except Exception as e:
            logger.error(f"Load positions error: {e}")
    
    async def _save_positions(self) -> None:
        """Sauvegarde les positions."""
        try:
            if self.data_manager:
                with self._positions_lock:
                    for position in self._positions.values():
                        await self.data_manager.store(
                            f"position:{position.position_id}",
                            position.to_dict(),
                            DataType.POSITION
                        )
            
            logger.info("Positions saved")
            
        except Exception as e:
            logger.error(f"Save positions error: {e}")
    
    def _deserialize_position(self, data: Dict) -> Optional[Position]:
        """Désérialise une position."""
        try:
            return Position(
                position_id=data.get("position_id", str(uuid.uuid4())),
                symbol=data.get("symbol", ""),
                position_type=PositionType(data.get("position_type", "long")),
                entry_price=data.get("entry_price", 0.0),
                current_price=data.get("current_price", 0.0),
                quantity=data.get("quantity", 0.0),
                filled_quantity=data.get("filled_quantity", 0.0),
                average_price=data.get("average_price", 0.0),
                stop_loss=data.get("stop_loss"),
                take_profit=data.get("take_profit"),
                trailing_stop=data.get("trailing_stop"),
                status=PositionStatus(data.get("status", "pending")),
                pnl=data.get("pnl", 0.0),
                pnl_percent=data.get("pnl_percent", 0.0),
                unrealized_pnl=data.get("unrealized_pnl", 0.0),
                realized_pnl=data.get("realized_pnl", 0.0),
                max_profit=data.get("max_profit", 0.0),
                max_loss=data.get("max_loss", 0.0),
                risk_level=PositionRisk(data.get("risk_level", "medium")),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                closed_at=datetime.fromisoformat(data.get("closed_at")) if data.get("closed_at") else None,
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                decision_id=data.get("decision_id"),
                strategy=data.get("strategy"),
                hedge_ratio=data.get("hedge_ratio", 0.0)
            )
        except Exception as e:
            logger.error(f"Error deserializing position: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_positions(self, status: Optional[PositionStatus] = None) -> List[Position]:
        """Récupère les positions."""
        with self._positions_lock:
            positions = list(self._positions.values())
            if status:
                positions = [p for p in positions if p.status == status]
            return sorted(positions, key=lambda p: p.created_at, reverse=True)
    
    async def get_open_positions(self) -> List[Position]:
        """Récupère les positions ouvertes."""
        return await self.get_positions(PositionStatus.OPEN)
    
    async def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Récupère les positions par symbole."""
        with self._positions_lock:
            return [p for p in self._positions.values() if p.symbol == symbol]
    
    async def get_position_updates(self, position_id: str) -> List[PositionUpdate]:
        """Récupère les mises à jour d'une position."""
        with self._updates_lock:
            return self._updates.get(position_id, [])
    
    async def get_summary(self) -> PositionSummary:
        """Récupère le résumé actuel des positions."""
        return await self._generate_summary()
    
    async def get_summaries(self, limit: int = 100) -> List[PositionSummary]:
        """Récupère l'historique des résumés."""
        with self._summary_lock:
            return self._summaries[-limit:]
    
    async def update_stop_loss(self, position_id: str, stop_loss: float) -> bool:
        """Met à jour le stop loss d'une position."""
        with self._positions_lock:
            position = self._positions.get(position_id)
            if not position:
                return False
            
            position.stop_loss = stop_loss
            position.updated_at = datetime.now(timezone.utc)
            return True
    
    async def update_take_profit(self, position_id: str, take_profit: float) -> bool:
        """Met à jour le take profit d'une position."""
        with self._positions_lock:
            position = self._positions.get(position_id)
            if not position:
                return False
            
            position.take_profit = take_profit
            position.updated_at = datetime.now(timezone.utc)
            return True
    
    async def update_trailing_stop(self, position_id: str, trailing_stop: float) -> bool:
        """Met à jour le trailing stop d'une position."""
        with self._positions_lock:
            position = self._positions.get(position_id)
            if not position:
                return False
            
            position.trailing_stop = trailing_stop
            position.updated_at = datetime.now(timezone.utc)
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._positions_lock:
            self._stats["total_positions"] = len(self._positions)
        
        return self._stats.copy()


# ============== POSITION ANALYZER ==============

class PositionAnalyzer:
    """
    Analyseur de positions.
    Analyse les performances et les risques des positions.
    """
    
    def __init__(self, manager: PositionManager):
        self.manager = manager
    
    async def analyze_positions(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Analyse les positions."""
        if symbol:
            positions = await self.manager.get_positions_by_symbol(symbol)
        else:
            positions = await self.manager.get_positions()
        
        if not positions:
            return {"message": "No positions found"}
        
        # Analyse
        analysis = {
            "total_positions": len(positions),
            "open_positions": len([p for p in positions if p.status == PositionStatus.OPEN]),
            "closed_positions": len([p for p in positions if p.status == PositionStatus.CLOSED]),
            "total_pnl": sum(p.pnl for p in positions),
            "avg_pnl": sum(p.pnl for p in positions) / len(positions) if positions else 0,
            "win_rate": 0,
            "avg_profit": 0,
            "avg_loss": 0,
            "max_profit": max(p.pnl for p in positions) if positions else 0,
            "max_loss": min(p.pnl for p in positions) if positions else 0,
            "risk_distribution": {}
        }
        
        # Win rate
        winning = [p for p in positions if p.pnl > 0]
        losing = [p for p in positions if p.pnl < 0]
        
        if positions:
            analysis["win_rate"] = len(winning) / len(positions)
            analysis["avg_profit"] = sum(p.pnl for p in winning) / len(winning) if winning else 0
            analysis["avg_loss"] = sum(p.pnl for p in losing) / len(losing) if losing else 0
        
        # Distribution des risques
        for p in positions:
            level = p.risk_level.value
            analysis["risk_distribution"][level] = analysis["risk_distribution"].get(level, 0) + 1
        
        return analysis


# ============== FACTORY ==============

class PositionManagerFactory:
    """Factory pour créer des composants de gestion de positions."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PositionManager:
        """Crée un gestionnaire de positions."""
        manager = PositionManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager
    
    @staticmethod
    def create_analyzer(manager: PositionManager) -> PositionAnalyzer:
        """Crée un analyseur de positions."""
        return PositionAnalyzer(manager)


# ============== EXPORT ==============

__all__ = [
    "PositionStatus",
    "PositionType",
    "PositionRisk",
    "Position",
    "PositionUpdate",
    "PositionSummary",
    "PositionManagerInterface",
    "PositionManager",
    "PositionAnalyzer",
    "PositionManagerFactory"
]

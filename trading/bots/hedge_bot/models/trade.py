"""
NEXUS AI TRADING SYSTEM - HEDGE BOT TRADE MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données de trading pour le Hedge Bot.
Définition des entités de trade, ordres, positions, et exécutions.

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

from sqlalchemy import (
    Column, String, DateTime, Numeric, Integer, Boolean, 
    ForeignKey, Text, JSON, Enum as SQLEnum, Index, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..utils.helpers import safe_decimal, safe_float

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class TradeSide(Enum):
    """Côtés de trade."""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


class TradeStatus(Enum):
    """Statuts de trade."""
    PENDING = "pending"
    OPEN = "open"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class OrderType(Enum):
    """Types d'ordres."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"


class TimeInForce(Enum):
    """Durées de validité."""
    GTC = "gtc"      # Good Till Cancelled
    IOC = "ioc"      # Immediate Or Cancel
    FOK = "fok"      # Fill Or Kill
    DAY = "day"      # Day order
    GTD = "gtd"      # Good Till Date


class OrderStatus(Enum):
    """Statuts d'ordre."""
    PENDING = "pending"
    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionStatus(Enum):
    """Statuts de position."""
    OPEN = "open"
    PARTIAL = "partial"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"
    HEDGED = "hedged"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class TradeModel(Base):
    """Modèle de trade."""
    __tablename__ = "trades"

    trade_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=True)
    order_id = Column(String(36), nullable=True)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(50), nullable=False)
    side = Column(SQLEnum(TradeSide), nullable=False)
    status = Column(SQLEnum(TradeStatus), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    total = Column(Numeric(20, 8), nullable=False)
    fee = Column(Numeric(20, 8), nullable=False)
    fee_currency = Column(String(10), nullable=True)
    realized_pnl = Column(Numeric(20, 8), nullable=True)
    unrealized_pnl = Column(Numeric(20, 8), nullable=True)
    entry_price = Column(Numeric(20, 8), nullable=True)
    exit_price = Column(Numeric(20, 8), nullable=True)
    metadata = Column(JSON, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_trades_user_id", "user_id"),
        Index("idx_trades_position_id", "position_id"),
        Index("idx_trades_symbol", "symbol"),
        Index("idx_trades_exchange", "exchange"),
        Index("idx_trades_status", "status"),
        Index("idx_trades_created_at", "created_at"),
    )


class OrderModel(Base):
    """Modèle d'ordre."""
    __tablename__ = "orders"

    order_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    position_id = Column(String(36), nullable=True)
    trade_id = Column(String(36), nullable=True)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(50), nullable=False)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    side = Column(SQLEnum(TradeSide), nullable=False)
    status = Column(SQLEnum(OrderStatus), nullable=False)
    time_in_force = Column(SQLEnum(TimeInForce), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    filled_quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=True)
    stop_price = Column(Numeric(20, 8), nullable=True)
    limit_price = Column(Numeric(20, 8), nullable=True)
    average_price = Column(Numeric(20, 8), nullable=True)
    fee = Column(Numeric(20, 8), nullable=False)
    fee_currency = Column(String(10), nullable=True)
    metadata = Column(JSON, nullable=True)
    exchange_order_id = Column(String(255), nullable=True)
    executed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_orders_user_id", "user_id"),
        Index("idx_orders_position_id", "position_id"),
        Index("idx_orders_symbol", "symbol"),
        Index("idx_orders_exchange", "exchange"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_type", "order_type"),
        Index("idx_orders_created_at", "created_at"),
    )


class PositionModel(Base):
    """Modèle de position."""
    __tablename__ = "positions"

    position_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(50), nullable=False)
    side = Column(SQLEnum(TradeSide), nullable=False)
    status = Column(SQLEnum(PositionStatus), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=True)
    take_profit = Column(Numeric(20, 8), nullable=True)
    unrealized_pnl = Column(Numeric(20, 8), nullable=True)
    realized_pnl = Column(Numeric(20, 8), nullable=True)
    total_fees = Column(Numeric(20, 8), nullable=False)
    metadata = Column(JSON, nullable=True)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_positions_user_id", "user_id"),
        Index("idx_positions_symbol", "symbol"),
        Index("idx_positions_exchange", "exchange"),
        Index("idx_positions_status", "status"),
        Index("idx_positions_opened_at", "opened_at"),
    )


class ExecutionModel(Base):
    """Modèle d'exécution."""
    __tablename__ = "executions"

    execution_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    order_id = Column(String(36), ForeignKey("orders.order_id"), nullable=False)
    trade_id = Column(String(36), nullable=True)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(50), nullable=False)
    side = Column(SQLEnum(TradeSide), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    total = Column(Numeric(20, 8), nullable=False)
    fee = Column(Numeric(20, 8), nullable=False)
    fee_currency = Column(String(10), nullable=True)
    metadata = Column(JSON, nullable=True)
    exchange_execution_id = Column(String(255), nullable=True)
    executed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    order = relationship("OrderModel")

    __table_args__ = (
        Index("idx_executions_user_id", "user_id"),
        Index("idx_executions_order_id", "order_id"),
        Index("idx_executions_symbol", "symbol"),
        Index("idx_executions_exchange", "exchange"),
        Index("idx_executions_executed_at", "executed_at"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class Trade:
    """Trade."""
    trade_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    order_id: Optional[UUID]
    symbol: str
    exchange: str
    side: TradeSide
    status: TradeStatus
    quantity: Decimal
    price: Decimal
    total: Decimal
    fee: Decimal
    fee_currency: Optional[str]
    realized_pnl: Optional[Decimal]
    unrealized_pnl: Optional[Decimal]
    entry_price: Optional[Decimal]
    exit_price: Optional[Decimal]
    metadata: Dict[str, Any] = field(default_factory=dict)
    executed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "trade_id": str(self.trade_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "order_id": str(self.order_id) if self.order_id else None,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value,
            "status": self.status.value,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "total": str(self.total),
            "fee": str(self.fee),
            "fee_currency": self.fee_currency,
            "realized_pnl": str(self.realized_pnl) if self.realized_pnl else None,
            "unrealized_pnl": str(self.unrealized_pnl) if self.unrealized_pnl else None,
            "entry_price": str(self.entry_price) if self.entry_price else None,
            "exit_price": str(self.exit_price) if self.exit_price else None,
            "metadata": self.metadata,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Order:
    """Ordre."""
    order_id: UUID
    user_id: UUID
    position_id: Optional[UUID]
    trade_id: Optional[UUID]
    symbol: str
    exchange: str
    order_type: OrderType
    side: TradeSide
    status: OrderStatus
    time_in_force: TimeInForce
    quantity: Decimal
    filled_quantity: Decimal
    price: Optional[Decimal]
    stop_price: Optional[Decimal]
    limit_price: Optional[Decimal]
    average_price: Optional[Decimal]
    fee: Decimal
    fee_currency: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    exchange_order_id: Optional[str] = None
    executed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "order_id": str(self.order_id),
            "user_id": str(self.user_id),
            "position_id": str(self.position_id) if self.position_id else None,
            "trade_id": str(self.trade_id) if self.trade_id else None,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "order_type": self.order_type.value,
            "side": self.side.value,
            "status": self.status.value,
            "time_in_force": self.time_in_force.value,
            "quantity": str(self.quantity),
            "filled_quantity": str(self.filled_quantity),
            "price": str(self.price) if self.price else None,
            "stop_price": str(self.stop_price) if self.stop_price else None,
            "limit_price": str(self.limit_price) if self.limit_price else None,
            "average_price": str(self.average_price) if self.average_price else None,
            "fee": str(self.fee),
            "fee_currency": self.fee_currency,
            "metadata": self.metadata,
            "exchange_order_id": self.exchange_order_id,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Position:
    """Position."""
    position_id: UUID
    user_id: UUID
    symbol: str
    exchange: str
    side: TradeSide
    status: PositionStatus
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    stop_loss: Optional[Decimal]
    take_profit: Optional[Decimal]
    unrealized_pnl: Optional[Decimal]
    realized_pnl: Optional[Decimal]
    total_fees: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value,
            "status": self.status.value,
            "quantity": str(self.quantity),
            "entry_price": str(self.entry_price),
            "current_price": str(self.current_price),
            "stop_loss": str(self.stop_loss) if self.stop_loss else None,
            "take_profit": str(self.take_profit) if self.take_profit else None,
            "unrealized_pnl": str(self.unrealized_pnl) if self.unrealized_pnl else None,
            "realized_pnl": str(self.realized_pnl) if self.realized_pnl else None,
            "total_fees": str(self.total_fees),
            "metadata": self.metadata,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Execution:
    """Exécution."""
    execution_id: UUID
    user_id: UUID
    order_id: UUID
    trade_id: Optional[UUID]
    symbol: str
    exchange: str
    side: TradeSide
    quantity: Decimal
    price: Decimal
    total: Decimal
    fee: Decimal
    fee_currency: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    exchange_execution_id: Optional[str] = None
    executed_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "execution_id": str(self.execution_id),
            "user_id": str(self.user_id),
            "order_id": str(self.order_id),
            "trade_id": str(self.trade_id) if self.trade_id else None,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "total": str(self.total),
            "fee": str(self.fee),
            "fee_currency": self.fee_currency,
            "metadata": self.metadata,
            "exchange_execution_id": self.exchange_execution_id,
            "executed_at": self.executed_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_trade(
    user_id: UUID,
    symbol: str,
    exchange: str,
    side: TradeSide,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal = Decimal("0"),
    fee_currency: Optional[str] = None,
    position_id: Optional[UUID] = None,
    order_id: Optional[UUID] = None,
    metadata: Optional[Dict] = None
) -> Trade:
    """
    Crée un trade.

    Args:
        user_id: ID de l'utilisateur
        symbol: Symbole
        exchange: Exchange
        side: Côté
        quantity: Quantité
        price: Prix
        fee: Frais
        fee_currency: Devise des frais
        position_id: ID de la position
        order_id: ID de l'ordre
        metadata: Métadonnées

    Returns:
        Trade créé
    """
    total = quantity * price
    return Trade(
        trade_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        order_id=order_id,
        symbol=symbol,
        exchange=exchange,
        side=side,
        status=TradeStatus.PENDING,
        quantity=quantity,
        price=price,
        total=total,
        fee=fee,
        fee_currency=fee_currency or "USD",
        realized_pnl=None,
        unrealized_pnl=None,
        entry_price=price if side in [TradeSide.BUY, TradeSide.LONG] else None,
        exit_price=price if side in [TradeSide.SELL, TradeSide.SHORT] else None,
        metadata=metadata or {}
    )


def create_order(
    user_id: UUID,
    symbol: str,
    exchange: str,
    order_type: OrderType,
    side: TradeSide,
    quantity: Decimal,
    time_in_force: TimeInForce = TimeInForce.GTC,
    price: Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
    limit_price: Optional[Decimal] = None,
    position_id: Optional[UUID] = None,
    trade_id: Optional[UUID] = None,
    metadata: Optional[Dict] = None
) -> Order:
    """
    Crée un ordre.

    Args:
        user_id: ID de l'utilisateur
        symbol: Symbole
        exchange: Exchange
        order_type: Type d'ordre
        side: Côté
        quantity: Quantité
        time_in_force: Durée de validité
        price: Prix
        stop_price: Prix de stop
        limit_price: Prix limite
        position_id: ID de la position
        trade_id: ID du trade
        metadata: Métadonnées

    Returns:
        Ordre créé
    """
    return Order(
        order_id=uuid4(),
        user_id=user_id,
        position_id=position_id,
        trade_id=trade_id,
        symbol=symbol,
        exchange=exchange,
        order_type=order_type,
        side=side,
        status=OrderStatus.PENDING,
        time_in_force=time_in_force,
        quantity=quantity,
        filled_quantity=Decimal("0"),
        price=price,
        stop_price=stop_price,
        limit_price=limit_price,
        average_price=None,
        fee=Decimal("0"),
        fee_currency=None,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TradeSide",
    "TradeStatus",
    "OrderType",
    "TimeInForce",
    "OrderStatus",
    "PositionStatus",
    "TradeModel",
    "OrderModel",
    "PositionModel",
    "ExecutionModel",
    "Trade",
    "Order",
    "Position",
    "Execution",
    "create_trade",
    "create_order"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles de trading."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT TRADE MODELS")
    print("=" * 60)

    # Création d'un trade
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Création d'un trade...")
    
    trade = create_trade(
        user_id=user_id,
        symbol="BTC/USDT",
        exchange="BINANCE",
        side=TradeSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000"),
        fee=Decimal("2.5"),
        metadata={"strategy": "momentum"}
    )

    print(f"   ID: {trade.trade_id}")
    print(f"   Symbole: {trade.symbol}")
    print(f"   Côté: {trade.side.value}")
    print(f"   Quantité: {trade.quantity}")
    print(f"   Prix: ${trade.price}")
    print(f"   Total: ${trade.total}")

    # Création d'un ordre
    print(f"\n📝 Création d'un ordre...")
    
    order = create_order(
        user_id=user_id,
        symbol="BTC/USDT",
        exchange="BINANCE",
        order_type=OrderType.LIMIT,
        side=TradeSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50500"),
        time_in_force=TimeInForce.GTC
    )

    print(f"   ID: {order.order_id}")
    print(f"   Type: {order.order_type.value}")
    print(f"   Prix: ${order.price}")
    print(f"   Statut: {order.status.value}")

    # Création d'une position
    print(f"\n📈 Création d'une position...")
    
    position = Position(
        position_id=uuid4(),
        user_id=user_id,
        symbol="BTC/USDT",
        exchange="BINANCE",
        side=TradeSide.LONG,
        status=PositionStatus.OPEN,
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000"),
        current_price=Decimal("52000"),
        stop_loss=Decimal("48000"),
        take_profit=Decimal("55000"),
        unrealized_pnl=Decimal("200"),
        realized_pnl=Decimal("0"),
        total_fees=Decimal("2.5"),
        opened_at=datetime.now()
    )

    print(f"   ID: {position.position_id}")
    print(f"   Entrée: ${position.entry_price}")
    print(f"   Actuel: ${position.current_price}")
    print(f"   PnL: ${position.unrealized_pnl}")
    print(f"   Stop Loss: ${position.stop_loss}")
    print(f"   Take Profit: ${position.take_profit}")

    # Exécution
    print(f"\n⚡ Création d'une exécution...")
    
    execution = Execution(
        execution_id=uuid4(),
        user_id=user_id,
        order_id=order.order_id,
        symbol="BTC/USDT",
        exchange="BINANCE",
        side=TradeSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50100"),
        total=Decimal("5010"),
        fee=Decimal("2.5"),
        executed_at=datetime.now()
    )

    print(f"   ID: {execution.execution_id}")
    print(f"   Quantité: {execution.quantity}")
    print(f"   Prix: ${execution.price}")
    print(f"   Total: ${execution.total}")

    print("\n" + "=" * 60)
    print("Trade Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

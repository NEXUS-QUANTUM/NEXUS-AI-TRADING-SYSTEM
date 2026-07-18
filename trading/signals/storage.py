# trading/signals/storage.py
"""
NEXUS AI TRADING SYSTEM - Signal Storage
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides persistent storage for trading signals with support for:
- Signal archiving and retrieval
- Performance tracking and analysis
- Signal lifecycle management
- Query and filtering capabilities
- Export and reporting
"""

import json
import sqlite3
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import deque
from pathlib import Path
import aiosqlite

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from .base import Signal, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class SignalStatus(str, Enum):
    """Status of a signal in the system"""
    GENERATED = "generated"
    VALIDATED = "validated"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SignalOutcome(str, Enum):
    """Outcome of a signal after trading"""
    PENDING = "pending"
    PROFIT = "profit"
    LOSS = "loss"
    BREAK_EVEN = "break_even"
    PARTIAL = "partial"


@dataclass
class SignalRecord:
    """Complete record of a signal with performance data"""
    # Signal data
    signal: Signal
    signal_id: str
    status: SignalStatus = SignalStatus.GENERATED
    outcome: SignalOutcome = SignalOutcome.PENDING
    
    # Execution data
    execution_price: Optional[float] = None
    executed_quantity: Optional[float] = None
    execution_time: Optional[datetime] = None
    
    # Result data
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    
    # Metadata
    strategy_id: str = ""
    strategy_name: str = ""
    broker_id: str = ""
    account_id: str = ""
    order_id: Optional[str] = None
    position_id: Optional[str] = None
    
    # Timestamps
    generated_at: datetime = field(default_factory=datetime.utcnow)
    validated_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Tags and metadata
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "symbol": self.signal.symbol,
            "signal_type": self.signal.signal_type.value,
            "strength": self.signal.strength.value,
            "confidence": self.signal.confidence,
            "price": self.signal.price,
            "position_size": self.signal.position_size,
            "stop_loss": self.signal.stop_loss,
            "take_profit": self.signal.take_profit,
            "status": self.status.value,
            "outcome": self.outcome.value,
            "execution_price": self.execution_price,
            "executed_quantity": self.executed_quantity,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "broker_id": self.broker_id,
            "account_id": self.account_id,
            "order_id": self.order_id,
            "position_id": self.position_id,
            "generated_at": self.generated_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "tags": json.dumps(self.tags),
            "notes": self.notes,
            "metadata": json.dumps(self.metadata),
            "signal_data": json.dumps(self.signal.to_dict()),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalRecord":
        """Create from dictionary."""
        signal_data = json.loads(data.get("signal_data", "{}"))
        signal = Signal.from_dict(signal_data)
        
        return cls(
            signal=signal,
            signal_id=data.get("signal_id", ""),
            status=SignalStatus(data.get("status", "generated")),
            outcome=SignalOutcome(data.get("outcome", "pending")),
            execution_price=data.get("execution_price"),
            executed_quantity=data.get("executed_quantity"),
            execution_time=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None,
            exit_price=data.get("exit_price"),
            exit_time=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            pnl=data.get("pnl"),
            pnl_percent=data.get("pnl_percent"),
            strategy_id=data.get("strategy_id", ""),
            strategy_name=data.get("strategy_name", ""),
            broker_id=data.get("broker_id", ""),
            account_id=data.get("account_id", ""),
            order_id=data.get("order_id"),
            position_id=data.get("position_id"),
            generated_at=datetime.fromisoformat(data["generated_at"]) if data.get("generated_at") else datetime.utcnow(),
            validated_at=None,
            executed_at=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None,
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            tags=json.loads(data.get("tags", "[]")),
            notes=data.get("notes", ""),
            metadata=json.loads(data.get("metadata", "{}")),
        )


# ============================================================================
# SIGNAL STORAGE
# ============================================================================

class SignalStorage:
    """
    Persistent storage for trading signals using SQLite.
    
    Features:
    - Signal persistence
    - Query and filtering
    - Performance tracking
    - Signal lifecycle management
    - Export and reporting
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the signal storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or "data/signals.db"
        self._initialized = False
        
        # In-memory cache for recent signals
        self._cache: Dict[str, SignalRecord] = {}
        self._cache_size = 1000
        self._recent_signals: deque = deque(maxlen=100)
        
        self.logger = logger
        
        # Initialize database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create signals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    strategy_id TEXT,
                    strategy_name TEXT,
                    symbol TEXT,
                    signal_type TEXT,
                    strength TEXT,
                    confidence REAL,
                    price REAL,
                    position_size REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    status TEXT,
                    outcome TEXT,
                    execution_price REAL,
                    executed_quantity REAL,
                    exit_price REAL,
                    pnl REAL,
                    pnl_percent REAL,
                    broker_id TEXT,
                    account_id TEXT,
                    order_id TEXT,
                    position_id TEXT,
                    generated_at TEXT,
                    executed_at TEXT,
                    closed_at TEXT,
                    tags TEXT,
                    notes TEXT,
                    metadata TEXT,
                    signal_data TEXT
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol ON signals(symbol)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON signals(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_generated_at ON signals(generated_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategy_id ON signals(strategy_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_type ON signals(signal_type)
            """)
            
            # Create performance statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signal_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT,
                    symbol TEXT,
                    period TEXT,
                    total_signals INTEGER,
                    executed_signals INTEGER,
                    profitable_signals INTEGER,
                    losing_signals INTEGER,
                    win_rate REAL,
                    total_pnl REAL,
                    avg_pnl REAL,
                    max_profit REAL,
                    max_loss REAL,
                    avg_confidence REAL,
                    created_at TEXT,
                    UNIQUE(strategy_id, symbol, period)
                )
            """)
            
            conn.commit()
            conn.close()
            self._initialized = True
            self.logger.info(f"Signal storage initialized at {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            self._initialized = False
    
    async def save_signal(self, record: SignalRecord) -> bool:
        """
        Save a signal record to storage.
        
        Args:
            record: Signal record to save
            
        Returns:
            bool: True if saved successfully
        """
        if not self._initialized:
            self.logger.error("Database not initialized")
            return False
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                data = record.to_dict()
                
                # Check if signal already exists
                cursor = await db.execute(
                    "SELECT signal_id FROM signals WHERE signal_id = ?",
                    (record.signal_id,)
                )
                existing = await cursor.fetchone()
                
                if existing:
                    # Update existing record
                    updates = []
                    values = []
                    for key, value in data.items():
                        if key != "signal_id":
                            updates.append(f"{key} = ?")
                            values.append(value)
                    values.append(record.signal_id)
                    
                    query = f"UPDATE signals SET {', '.join(updates)} WHERE signal_id = ?"
                    await db.execute(query, values)
                else:
                    # Insert new record
                    placeholders = ", ".join(["?"] * len(data))
                    columns = ", ".join(data.keys())
                    query = f"INSERT INTO signals ({columns}) VALUES ({placeholders})"
                    await db.execute(query, list(data.values()))
                
                await db.commit()
                
                # Update cache
                self._cache[record.signal_id] = record
                self._recent_signals.append(record)
                
                if len(self._cache) > self._cache_size:
                    # Remove oldest from cache
                    oldest = self._recent_signals[0]
                    if oldest.signal_id in self._cache:
                        del self._cache[oldest.signal_id]
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to save signal: {e}")
            return False
    
    async def get_signal(self, signal_id: str) -> Optional[SignalRecord]:
        """
        Get a signal record by ID.
        
        Args:
            signal_id: Signal ID
            
        Returns:
            Optional[SignalRecord]: Signal record or None
        """
        # Check cache first
        if signal_id in self._cache:
            return self._cache[signal_id]
        
        if not self._initialized:
            return None
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT * FROM signals WHERE signal_id = ?", (signal_id,))
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                columns = [description[0] for description in cursor.description]
                data = dict(zip(columns, row))
                
                record = SignalRecord.from_dict(data)
                
                # Cache for future
                if len(self._cache) < self._cache_size:
                    self._cache[signal_id] = record
                
                return record
                
        except Exception as e:
            self.logger.error(f"Failed to get signal {signal_id}: {e}")
            return None
    
    async def update_signal_status(
        self,
        signal_id: str,
        status: SignalStatus,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update the status of a signal.
        
        Args:
            signal_id: Signal ID
            status: New status
            metadata: Additional metadata to update
            
        Returns:
            bool: True if updated successfully
        """
        record = await self.get_signal(signal_id)
        if not record:
            return False
        
        record.status = status
        
        if status == SignalStatus.VALIDATED:
            record.validated_at = datetime.utcnow()
        elif status == SignalStatus.EXECUTED:
            record.executed_at = datetime.utcnow()
        elif status == SignalStatus.CLOSED:
            record.closed_at = datetime.utcnow()
        
        if metadata:
            record.metadata.update(metadata)
        
        return await self.save_signal(record)
    
    async def update_signal_result(
        self,
        signal_id: str,
        exit_price: float,
        pnl: float,
        pnl_percent: float,
        exit_time: Optional[datetime] = None,
    ) -> bool:
        """
        Update the result of a closed signal.
        
        Args:
            signal_id: Signal ID
            exit_price: Exit price
            pnl: Profit/Loss amount
            pnl_percent: Profit/Loss percentage
            exit_time: Exit time
            
        Returns:
            bool: True if updated successfully
        """
        record = await self.get_signal(signal_id)
        if not record:
            return False
        
        record.exit_price = exit_price
        record.pnl = pnl
        record.pnl_percent = pnl_percent
        record.exit_time = exit_time or datetime.utcnow()
        record.status = SignalStatus.CLOSED
        record.outcome = SignalOutcome.PROFIT if pnl > 0 else SignalOutcome.LOSS if pnl < 0 else SignalOutcome.BREAK_EVEN
        record.closed_at = record.exit_time
        
        return await self.save_signal(record)
    
    async def query_signals(
        self,
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        status: Optional[SignalStatus] = None,
        outcome: Optional[SignalOutcome] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        min_pnl: Optional[float] = None,
        max_pnl: Optional[float] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "generated_at DESC",
    ) -> List[SignalRecord]:
        """
        Query signals with filters.
        
        Args:
            symbol: Symbol filter
            strategy_id: Strategy ID filter
            signal_type: Signal type filter
            status: Status filter
            outcome: Outcome filter
            start_time: Start time filter
            end_time: End time filter
            min_confidence: Minimum confidence
            max_confidence: Maximum confidence
            min_pnl: Minimum P&L
            max_pnl: Maximum P&L
            tags: Tags to filter
            limit: Maximum results
            offset: Results offset
            order_by: Order by clause
            
        Returns:
            List[SignalRecord]: Matching signals
        """
        if not self._initialized:
            return []
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Build query
                conditions = []
                params = []
                
                if symbol:
                    conditions.append("symbol = ?")
                    params.append(symbol)
                
                if strategy_id:
                    conditions.append("strategy_id = ?")
                    params.append(strategy_id)
                
                if signal_type:
                    conditions.append("signal_type = ?")
                    params.append(signal_type.value)
                
                if status:
                    conditions.append("status = ?")
                    params.append(status.value)
                
                if outcome:
                    conditions.append("outcome = ?")
                    params.append(outcome.value)
                
                if start_time:
                    conditions.append("generated_at >= ?")
                    params.append(start_time.isoformat())
                
                if end_time:
                    conditions.append("generated_at <= ?")
                    params.append(end_time.isoformat())
                
                if min_confidence is not None:
                    conditions.append("confidence >= ?")
                    params.append(min_confidence)
                
                if max_confidence is not None:
                    conditions.append("confidence <= ?")
                    params.append(max_confidence)
                
                if min_pnl is not None:
                    conditions.append("pnl >= ?")
                    params.append(min_pnl)
                
                if max_pnl is not None:
                    conditions.append("pnl <= ?")
                    params.append(max_pnl)
                
                if tags:
                    # Simple tag filtering - check if any tag exists
                    tag_conditions = []
                    for tag in tags:
                        tag_conditions.append("tags LIKE ?")
                        params.append(f'%"{tag}"%')
                    conditions.append(f"({' OR '.join(tag_conditions)})")
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                query = f"""
                    SELECT * FROM signals
                    WHERE {where_clause}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])
                
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
                
                columns = [description[0] for description in cursor.description]
                
                results = []
                for row in rows:
                    data = dict(zip(columns, row))
                    record = SignalRecord.from_dict(data)
                    results.append(record)
                
                return results
                
        except Exception as e:
            self.logger.error(f"Failed to query signals: {e}")
            return []
    
    async def get_statistics(
        self,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        period: str = "all_time",
    ) -> Dict[str, Any]:
        """
        Get signal statistics.
        
        Args:
            strategy_id: Strategy ID filter
            symbol: Symbol filter
            period: Time period
            
        Returns:
            Dict[str, Any]: Statistics
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                conditions = ["status = 'closed'"]
                params = []
                
                if strategy_id:
                    conditions.append("strategy_id = ?")
                    params.append(strategy_id)
                
                if symbol:
                    conditions.append("symbol = ?")
                    params.append(symbol)
                
                if period != "all_time":
                    time_ago = None
                    if period == "today":
                        time_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    elif period == "week":
                        time_ago = datetime.utcnow() - timedelta(days=7)
                    elif period == "month":
                        time_ago = datetime.utcnow() - timedelta(days=30)
                    elif period == "quarter":
                        time_ago = datetime.utcnow() - timedelta(days=90)
                    elif period == "year":
                        time_ago = datetime.utcnow() - timedelta(days=365)
                    
                    if time_ago:
                        conditions.append("closed_at >= ?")
                        params.append(time_ago.isoformat())
                
                where_clause = " AND ".join(conditions)
                
                # Get statistics
                query = f"""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome = 'profit' THEN 1 ELSE 0 END) as profitable,
                        SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losing,
                        SUM(CASE WHEN outcome = 'break_even' THEN 1 ELSE 0 END) as break_even,
                        AVG(pnl) as avg_pnl,
                        AVG(pnl_percent) as avg_pnl_percent,
                        MAX(pnl) as max_profit,
                        MIN(pnl) as max_loss,
                        AVG(confidence) as avg_confidence,
                        SUM(pnl) as total_pnl
                    FROM signals
                    WHERE {where_clause}
                """
                cursor = await db.execute(query, params)
                row = await cursor.fetchone()
                
                if not row:
                    return {}
                
                columns = [description[0] for description in cursor.description]
                stats = dict(zip(columns, row))
                
                # Add derived statistics
                total = stats.get("total", 0)
                profitable = stats.get("profitable", 0)
                losing = stats.get("losing", 0)
                
                stats["win_rate"] = (profitable / total * 100) if total > 0 else 0
                stats["loss_rate"] = (losing / total * 100) if total > 0 else 0
                stats["profit_factor"] = (
                    (profitable * stats.get("avg_pnl", 0)) / (losing * abs(stats.get("avg_pnl", 0)))
                    if losing > 0 else float('inf')
                )
                stats["total_signals"] = total
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}
    
    async def get_performance_by_symbol(self, strategy_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get performance breakdown by symbol.
        
        Args:
            strategy_id: Strategy ID filter
            
        Returns:
            List[Dict[str, Any]]: Performance by symbol
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                conditions = ["status = 'closed'"]
                params = []
                
                if strategy_id:
                    conditions.append("strategy_id = ?")
                    params.append(strategy_id)
                
                where_clause = " AND ".join(conditions)
                
                query = f"""
                    SELECT 
                        symbol,
                        COUNT(*) as total_signals,
                        SUM(CASE WHEN outcome = 'profit' THEN 1 ELSE 0 END) as profitable,
                        SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losing,
                        AVG(pnl) as avg_pnl,
                        SUM(pnl) as total_pnl,
                        AVG(confidence) as avg_confidence
                    FROM signals
                    WHERE {where_clause}
                    GROUP BY symbol
                    ORDER BY total_pnl DESC
                """
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
                
                columns = [description[0] for description in cursor.description]
                results = []
                for row in rows:
                    data = dict(zip(columns, row))
                    total = data.get("total_signals", 0)
                    profitable = data.get("profitable", 0)
                    data["win_rate"] = (profitable / total * 100) if total > 0 else 0
                    results.append(data)
                
                return results
                
        except Exception as e:
            self.logger.error(f"Failed to get performance by symbol: {e}")
            return []
    
    async def get_recent_signals(self, limit: int = 50) -> List[SignalRecord]:
        """
        Get recent signals.
        
        Args:
            limit: Maximum number of signals
            
        Returns:
            List[SignalRecord]: Recent signals
        """
        return await self.query_signals(limit=limit, order_by="generated_at DESC")
    
    async def get_active_signals(self) -> List[SignalRecord]:
        """
        Get active (not closed) signals.
        
        Returns:
            List[SignalRecord]: Active signals
        """
        return await self.query_signals(
            status=SignalStatus.EXECUTED,
            limit=1000,
        )
    
    async def delete_signal(self, signal_id: str) -> bool:
        """
        Delete a signal record.
        
        Args:
            signal_id: Signal ID
            
        Returns:
            bool: True if deleted successfully
        """
        if not self._initialized:
            return False
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM signals WHERE signal_id = ?", (signal_id,))
                await db.commit()
                
                # Remove from cache
                if signal_id in self._cache:
                    del self._cache[signal_id]
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to delete signal {signal_id}: {e}")
            return False
    
    async def archive_old_signals(self, days: int = 90) -> int:
        """
        Archive signals older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            int: Number of signals archived
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        signals = await self.query_signals(
            end_time=cutoff,
            limit=10000,
        )
        
        archived = 0
        for record in signals:
            record.status = SignalStatus.ARCHIVED
            if await self.save_signal(record):
                archived += 1
        
        return archived
    
    async def export_signals(
        self,
        format: str = "json",
        **filters,
    ) -> Union[str, bytes]:
        """
        Export signals in various formats.
        
        Args:
            format: Export format (json, csv, csv)
            **filters: Query filters
            
        Returns:
            Union[str, bytes]: Exported data
        """
        signals = await self.query_signals(**filters, limit=10000)
        
        if format == "json":
            data = [record.to_dict() for record in signals]
            return json.dumps(data, indent=2, default=str)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if signals:
                fieldnames = [
                    "signal_id", "symbol", "signal_type", "strength",
                    "confidence", "price", "position_size", "status",
                    "outcome", "pnl", "pnl_percent", "generated_at"
                ]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for record in signals:
                    data = record.to_dict()
                    row = {k: data.get(k) for k in fieldnames}
                    writer.writerow(row)
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()
        self._recent_signals.clear()
        self.logger.info("Cache cleared")


# ============================================================================
# SIGNAL STORAGE MANAGER
# ============================================================================

class SignalStorageManager:
    """
    Manager for signal storage with multiple database support.
    """
    
    def __init__(self):
        """Initialize the storage manager."""
        self._storages: Dict[str, SignalStorage] = {}
        self._default_storage: Optional[SignalStorage] = None
        self.logger = logger
    
    def get_storage(self, name: str = "default") -> SignalStorage:
        """
        Get a storage instance.
        
        Args:
            name: Storage name
            
        Returns:
            SignalStorage: Storage instance
        """
        if name not in self._storages:
            db_path = f"data/signals_{name}.db" if name != "default" else "data/signals.db"
            self._storages[name] = SignalStorage(db_path)
            
            if name == "default":
                self._default_storage = self._storages[name]
        
        return self._storages[name]
    
    def set_default_storage(self, name: str) -> bool:
        """
        Set the default storage.
        
        Args:
            name: Storage name
            
        Returns:
            bool: True if storage exists
        """
        if name in self._storages:
            self._default_storage = self._storages[name]
            return True
        return False


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "SignalStatus",
    "SignalOutcome",
    
    # Models
    "SignalRecord",
    
    # Storage
    "SignalStorage",
    "SignalStorageManager",
]

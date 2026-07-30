# trading/bots/hedge_bot/hedge_bot_audit_trail.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Audit Trail Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Audit Trail Module

This module provides comprehensive audit trail and logging capabilities
for the NEXUS Hedge Bot system. It tracks all actions, events, and changes
for compliance, debugging, and analysis purposes.

The module covers:
- Trade Audit Logging
- Position Audit Logging
- Order Audit Logging
- Configuration Audit Logging
- User Activity Logging
- System Event Logging
- Error Logging
- Compliance Logging
- Performance Logging
- Security Logging
- Data Access Logging
- API Logging
"""

import os
import sys
import json
import time
import logging
import hashlib
import hmac
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import sqlite3
import csv
from collections import deque

logger = logging.getLogger(__name__)


# ============================================================
# AUDIT ENUMS
# ============================================================

class AuditEventType(Enum):
    """Audit event types"""
    # Trading Events
    TRADE_EXECUTED = "trade_executed"
    TRADE_CANCELLED = "trade_cancelled"
    ORDER_PLACED = "order_placed"
    ORDER_UPDATED = "order_updated"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"
    
    # Configuration Events
    CONFIG_LOADED = "config_loaded"
    CONFIG_UPDATED = "config_updated"
    CONFIG_RELOADED = "config_reloaded"
    
    # Strategy Events
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"
    STRATEGY_UPDATED = "strategy_updated"
    STRATEGY_SIGNAL = "strategy_signal"
    
    # System Events
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    
    # Security Events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    ACCESS_DENIED = "access_denied"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    
    # Data Events
    DATA_LOADED = "data_loaded"
    DATA_UPDATED = "data_updated"
    DATA_EXPORTED = "data_exported"
    
    # User Events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ROLE_CHANGED = "user_role_changed"


class AuditSeverity(Enum):
    """Audit severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class AuditStatus(Enum):
    """Audit status"""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    PARTIAL = "partial"


# ============================================================
# AUDIT DATACLASSES
# ============================================================

@dataclass
class AuditEntry:
    """Audit entry"""
    id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    status: AuditStatus
    user: Optional[str]
    source: str
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    version: str = "2.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "user": self.user,
            "source": self.source,
            "description": self.description,
            "data": self.data,
            "request_id": self.request_id,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "version": self.version,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)
    
    def to_csv_row(self) -> List[str]:
        """Convert to CSV row"""
        return [
            self.id,
            self.timestamp.isoformat(),
            self.event_type.value,
            self.severity.value,
            self.status.value,
            self.user or "",
            self.source,
            self.description,
            json.dumps(self.data, default=str),
            self.request_id or "",
            self.ip_address or "",
            self.session_id or "",
        ]


# ============================================================
# AUDIT STORAGE
# ============================================================

class AuditStorage:
    """
    Audit storage backend
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize audit storage
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.storage_type = self.config.get("type", "sqlite")
        self.storage_path = self.config.get("path", "audit.db")
        self.max_entries = self.config.get("max_entries", 100000)
        self.retention_days = self.config.get("retention_days", 365)
        
        if self.storage_type == "sqlite":
            self._init_sqlite()
        elif self.storage_type == "file":
            self._init_file()
        else:
            self._init_memory()
        
        logger.info(f"Audit storage initialized: {self.storage_type}")
    
    def _init_sqlite(self) -> None:
        """Initialize SQLite storage"""
        self.conn = sqlite3.connect(self.storage_path)
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_entries (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                event_type TEXT,
                severity TEXT,
                status TEXT,
                user TEXT,
                source TEXT,
                description TEXT,
                data TEXT,
                request_id TEXT,
                ip_address TEXT,
                session_id TEXT,
                version TEXT,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_entries(timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_event_type ON audit_entries(event_type)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_user ON audit_entries(user)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_severity ON audit_entries(severity)
        ''')
        
        self.conn.commit()
    
    def _init_file(self) -> None:
        """Initialize file storage"""
        self.file_path = Path(self.storage_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create CSV header if file doesn't exist
        if not self.file_path.exists():
            with open(self.file_path, "w") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "id", "timestamp", "event_type", "severity", "status",
                    "user", "source", "description", "data", "request_id",
                    "ip_address", "session_id"
                ])
    
    def _init_memory(self) -> None:
        """Initialize memory storage"""
        self.memory_storage = deque(maxlen=self.max_entries)
    
    def store(self, entry: AuditEntry) -> bool:
        """
        Store an audit entry
        
        Args:
            entry: Audit entry
            
        Returns:
            True if successful
        """
        try:
            if self.storage_type == "sqlite":
                return self._store_sqlite(entry)
            elif self.storage_type == "file":
                return self._store_file(entry)
            else:
                return self._store_memory(entry)
        except Exception as e:
            logger.error(f"Failed to store audit entry: {e}")
            return False
    
    def _store_sqlite(self, entry: AuditEntry) -> bool:
        """Store in SQLite"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO audit_entries (
                id, timestamp, event_type, severity, status, user,
                source, description, data, request_id, ip_address,
                session_id, version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry.id,
            entry.timestamp.isoformat(),
            entry.event_type.value,
            entry.severity.value,
            entry.status.value,
            entry.user,
            entry.source,
            entry.description,
            json.dumps(entry.data, default=str),
            entry.request_id,
            entry.ip_address,
            entry.session_id,
            entry.version,
            datetime.now().isoformat(),
        ))
        self.conn.commit()
        return True
    
    def _store_file(self, entry: AuditEntry) -> bool:
        """Store in file"""
        with open(self.file_path, "a") as f:
            writer = csv.writer(f)
            writer.writerow(entry.to_csv_row())
        return True
    
    def _store_memory(self, entry: AuditEntry) -> bool:
        """Store in memory"""
        self.memory_storage.append(entry.to_dict())
        return True
    
    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditSeverity] = None,
        user: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Query audit entries
        
        Args:
            start_time: Start time
            end_time: End time
            event_type: Event type filter
            severity: Severity filter
            user: User filter
            limit: Maximum number of entries
            
        Returns:
            List of audit entries
        """
        if self.storage_type == "sqlite":
            return self._query_sqlite(start_time, end_time, event_type, severity, user, limit)
        elif self.storage_type == "file":
            return self._query_file(start_time, end_time, event_type, severity, user, limit)
        else:
            return self._query_memory(start_time, end_time, event_type, severity, user, limit)
    
    def _query_sqlite(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        event_type: Optional[AuditEventType],
        severity: Optional[AuditSeverity],
        user: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Query SQLite"""
        query = "SELECT * FROM audit_entries WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity.value)
        
        if user:
            query += " AND user = ?"
            params.append(user)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "timestamp": datetime.fromisoformat(row[1]),
                "event_type": row[2],
                "severity": row[3],
                "status": row[4],
                "user": row[5],
                "source": row[6],
                "description": row[7],
                "data": json.loads(row[8]) if row[8] else {},
                "request_id": row[9],
                "ip_address": row[10],
                "session_id": row[11],
                "version": row[12],
            })
        
        return results
    
    def _query_file(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        event_type: Optional[AuditEventType],
        severity: Optional[AuditSeverity],
        user: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Query file"""
        results = []
        
        with open(self.file_path, "r") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            
            for row in reader:
                if len(row) < 12:
                    continue
                
                timestamp = datetime.fromisoformat(row[1])
                
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue
                if event_type and row[2] != event_type.value:
                    continue
                if severity and row[3] != severity.value:
                    continue
                if user and row[5] != user:
                    continue
                
                results.append({
                    "id": row[0],
                    "timestamp": timestamp,
                    "event_type": row[2],
                    "severity": row[3],
                    "status": row[4],
                    "user": row[5],
                    "source": row[6],
                    "description": row[7],
                    "data": json.loads(row[8]) if row[8] else {},
                    "request_id": row[9],
                    "ip_address": row[10],
                    "session_id": row[11],
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    def _query_memory(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        event_type: Optional[AuditEventType],
        severity: Optional[AuditSeverity],
        user: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Query memory"""
        results = []
        
        for entry in self.memory_storage:
            timestamp = datetime.fromisoformat(entry["timestamp"])
            
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue
            if event_type and entry["event_type"] != event_type.value:
                continue
            if severity and entry["severity"] != severity.value:
                continue
            if user and entry["user"] != user:
                continue
            
            results.append(entry)
            
            if len(results) >= limit:
                break
        
        return results
    
    def cleanup(self) -> int:
        """
        Clean up old entries
        
        Returns:
            Number of entries removed
        """
        if self.storage_type == "sqlite":
            cutoff = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM audit_entries WHERE timestamp < ?", (cutoff,))
            count = cursor.rowcount
            self.conn.commit()
            return count
        return 0


# ============================================================
# AUDIT TRAIL MANAGER
# ============================================================

class AuditTrailManager:
    """
    Audit trail manager for the hedge bot
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize audit trail manager
        
        Args:
            config: Configuration dictionary
        """
        if hasattr(self, '_initialized'):
            return
        
        self.config = config or {}
        self.storage = AuditStorage(self.config.get("storage", {}))
        self.enabled = self.config.get("enabled", True)
        self.source = self.config.get("source", "hedge_bot")
        self.version = self.config.get("version", "2.0.0")
        self._initialized = True
        
        logger.info("Audit trail manager initialized")
    
    def log(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        status: AuditStatus,
        description: str,
        data: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[AuditEntry]:
        """
        Log an audit entry
        
        Args:
            event_type: Event type
            severity: Severity
            status: Status
            description: Description
            data: Additional data
            user: User name
            request_id: Request ID
            ip_address: IP address
            session_id: Session ID
            
        Returns:
            Audit entry
        """
        if not self.enabled:
            return None
        
        entry = AuditEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            event_type=event_type,
            severity=severity,
            status=status,
            user=user,
            source=self.source,
            description=description,
            data=data or {},
            request_id=request_id,
            ip_address=ip_address,
            session_id=session_id,
            version=self.version,
        )
        
        self.storage.store(entry)
        
        # Log to standard logger
        log_message = f"[AUDIT] {severity.value}: {event_type.value} - {description}"
        if severity == AuditSeverity.ERROR:
            logger.error(log_message)
        elif severity == AuditSeverity.WARNING:
            logger.warning(log_message)
        elif severity == AuditSeverity.CRITICAL:
            logger.critical(log_message)
        elif severity == AuditSeverity.SECURITY:
            logger.warning(f"[SECURITY] {log_message}")
        else:
            logger.info(log_message)
        
        return entry
    
    # ============================================================
    # CONVENIENCE METHODS
    # ============================================================
    
    def log_trade(self, trade: Dict[str, Any]) -> Optional[AuditEntry]:
        """Log a trade"""
        return self.log(
            event_type=AuditEventType.TRADE_EXECUTED,
            severity=AuditSeverity.INFO,
            status=AuditStatus.SUCCESS,
            description=f"Trade executed: {trade.get('symbol')} {trade.get('side')} {trade.get('quantity')}",
            data=trade,
        )
    
    def log_order(self, order: Dict[str, Any]) -> Optional[AuditEntry]:
        """Log an order"""
        return self.log(
            event_type=AuditEventType.ORDER_PLACED,
            severity=AuditSeverity.INFO,
            status=AuditStatus.SUCCESS,
            description=f"Order placed: {order.get('symbol')} {order.get('side')} {order.get('quantity')} @ {order.get('price')}",
            data=order,
        )
    
    def log_position(self, position: Dict[str, Any], action: str) -> Optional[AuditEntry]:
        """Log a position"""
        event_type = {
            "open": AuditEventType.POSITION_OPENED,
            "update": AuditEventType.POSITION_UPDATED,
            "close": AuditEventType.POSITION_CLOSED,
        }.get(action, AuditEventType.POSITION_UPDATED)
        
        return self.log(
            event_type=event_type,
            severity=AuditSeverity.INFO,
            status=AuditStatus.SUCCESS,
            description=f"Position {action}: {position.get('symbol')} {position.get('side')} {position.get('quantity')}",
            data=position,
        )
    
    def log_config_change(self, changes: Dict[str, Any]) -> Optional[AuditEntry]:
        """Log a configuration change"""
        return self.log(
            event_type=AuditEventType.CONFIG_UPDATED,
            severity=AuditSeverity.WARNING,
            status=AuditStatus.SUCCESS,
            description="Configuration updated",
            data=changes,
        )
    
    def log_strategy(self, strategy: str, action: str) -> Optional[AuditEntry]:
        """Log a strategy action"""
        event_type = {
            "start": AuditEventType.STRATEGY_STARTED,
            "stop": AuditEventType.STRATEGY_STOPPED,
            "update": AuditEventType.STRATEGY_UPDATED,
        }.get(action, AuditEventType.STRATEGY_UPDATED)
        
        return self.log(
            event_type=event_type,
            severity=AuditSeverity.INFO,
            status=AuditStatus.SUCCESS,
            description=f"Strategy {action}: {strategy}",
            data={"strategy": strategy, "action": action},
        )
    
    def log_system_event(self, event: str, severity: AuditSeverity = AuditSeverity.INFO) -> Optional[AuditEntry]:
        """Log a system event"""
        event_type = {
            "start": AuditEventType.SYSTEM_STARTED,
            "stop": AuditEventType.SYSTEM_STOPPED,
            "error": AuditEventType.SYSTEM_ERROR,
            "warning": AuditEventType.SYSTEM_WARNING,
        }.get(event, AuditEventType.SYSTEM_WARNING)
        
        return self.log(
            event_type=event_type,
            severity=severity,
            status=AuditStatus.SUCCESS if event not in ["error", "warning"] else AuditStatus.FAILURE,
            description=f"System {event}",
            data={"event": event},
        )
    
    def log_security_event(
        self,
        event: str,
        user: Optional[str] = None,
        success: bool = True
    ) -> Optional[AuditEntry]:
        """Log a security event"""
        event_type = {
            "login": AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILED,
            "logout": AuditEventType.LOGOUT,
            "access_denied": AuditEventType.ACCESS_DENIED,
        }.get(event, AuditEventType.ACCESS_DENIED)
        
        return self.log(
            event_type=event_type,
            severity=AuditSeverity.SECURITY,
            status=AuditStatus.SUCCESS if success else AuditStatus.FAILURE,
            description=f"Security event: {event}",
            user=user,
            data={"event": event, "success": success},
        )
    
    # ============================================================
    # QUERY METHODS
    # ============================================================
    
    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditSeverity] = None,
        user: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Query audit entries
        
        Args:
            start_time: Start time
            end_time: End time
            event_type: Event type filter
            severity: Severity filter
            user: User filter
            limit: Maximum number of entries
            
        Returns:
            List of audit entries
        """
        return self.storage.query(start_time, end_time, event_type, severity, user, limit)
    
    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit entries"""
        return self.query(limit=limit)
    
    def get_by_user(self, user: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit entries by user"""
        return self.query(user=user, limit=limit)
    
    def get_by_event_type(self, event_type: AuditEventType, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit entries by event type"""
        return self.query(event_type=event_type, limit=limit)
    
    def get_by_severity(self, severity: AuditSeverity, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit entries by severity"""
        return self.query(severity=severity, limit=limit)
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def generate_report(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate audit report
        
        Args:
            start_time: Start time
            end_time: End time
            
        Returns:
            Audit report
        """
        entries = self.query(start_time=start_time, end_time=end_time, limit=10000)
        
        # Statistics
        total = len(entries)
        by_event_type = {}
        by_severity = {}
        by_user = {}
        by_status = {}
        
        for entry in entries:
            event_type = entry.get("event_type", "unknown")
            severity = entry.get("severity", "unknown")
            user = entry.get("user", "system")
            status = entry.get("status", "unknown")
            
            by_event_type[event_type] = by_event_type.get(event_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_user[user] = by_user.get(user, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "period": {
                "start": start_time.isoformat() if start_time else "beginning",
                "end": end_time.isoformat() if end_time else "now",
            },
            "total_entries": total,
            "by_event_type": by_event_type,
            "by_severity": by_severity,
            "by_user": by_user,
            "by_status": by_status,
            "recent_entries": entries[:100],
        }
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _generate_id(self) -> str:
        """Generate unique audit ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = str(hash(str(time.time())))[-6:]
        return f"audit_{timestamp}_{random_part}"
    
    def cleanup(self) -> int:
        """Clean up old audit entries"""
        return self.storage.cleanup()
    
    def get_status(self) -> Dict[str, Any]:
        """Get audit trail status"""
        return {
            "enabled": self.enabled,
            "storage_type": self.storage.storage_type,
            "storage_path": self.storage.storage_path,
            "total_entries": len(self.storage.query(limit=10000)) if self.storage.storage_type == "memory" else "unknown",
            "retention_days": self.storage.retention_days,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AuditEventType",
    "AuditSeverity",
    "AuditStatus",
    
    # Dataclasses
    "AuditEntry",
    
    # Classes
    "AuditStorage",
    "AuditTrailManager",
]

# ============================================================
# END OF MODULE
# ============================================================

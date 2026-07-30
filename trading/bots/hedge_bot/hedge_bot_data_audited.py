# trading/bots/hedge_bot/hedge_bot_data_audited.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Audited Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Audited Module

This module provides comprehensive data auditing and compliance capabilities
for the NEXUS Hedge Bot system. It tracks data access, modifications, and
ensures data integrity and compliance.

The module covers:
- Data Access Auditing
- Data Modification Auditing
- Data Integrity Auditing
- Compliance Auditing
- Data Lineage Tracking
- Data Provenance
- Audit Trail Management
- Audit Report Generation
- Data Governance
"""

import os
import sys
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# DATA AUDITED ENUMS
# ============================================================

class AuditAction(Enum):
    """Audit actions"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    IMPORT = "import"
    ARCHIVE = "archive"
    RESTORE = "restore"
    ACCESS = "access"


class AuditStatus(Enum):
    """Audit status"""
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    ERROR = "error"


class AuditLevel(Enum):
    """Audit levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


@dataclass
class AuditRecord:
    """Audit record"""
    id: str
    timestamp: datetime
    user_id: str
    action: AuditAction
    resource: str
    status: AuditStatus
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    level: AuditLevel = AuditLevel.INFO
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action.value,
            "resource": self.resource,
            "status": self.status.value,
            "details": self.details,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "level": self.level.value,
        }


@dataclass
class DataLineage:
    """Data lineage"""
    data_id: str
    source: str
    transformations: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    version: int
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "data_id": self.data_id,
            "source": self.source,
            "transformations": self.transformations,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }


@dataclass
class AuditReport:
    """Audit report"""
    id: str
    title: str
    period: Dict[str, str]
    summary: Dict[str, Any]
    records: List[AuditRecord]
    violations: List[Dict[str, Any]]
    recommendations: List[str]
    compliance_status: bool
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "period": self.period,
            "summary": self.summary,
            "records": [r.to_dict() for r in self.records],
            "violations": self.violations,
            "recommendations": self.recommendations,
            "compliance_status": self.compliance_status,
            "generated_at": self.generated_at.isoformat(),
        }


# ============================================================
# DATA AUDITED ENGINE
# ============================================================

class DataAuditedEngine:
    """
    Comprehensive data auditing engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data auditing engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.max_records = self.config.get("max_records", 10000)
        self.retention_days = self.config.get("retention_days", 365)
        self.audit_enabled = self.config.get("audit_enabled", True)
        
        # State
        self.audit_records: List[AuditRecord] = []
        self.lineage_records: Dict[str, DataLineage] = {}
        self.audit_reports: List[AuditReport] = []
        
        # Create audit log directory
        self.audit_log_dir = Path(self.config.get("audit_log_dir", "audit_logs"))
        self.audit_log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Data auditing engine initialized")
    
    # ============================================================
    # AUDIT RECORDING
    # ============================================================
    
    def record_audit(
        self,
        user_id: str,
        action: AuditAction,
        resource: str,
        status: AuditStatus = AuditStatus.SUCCESS,
        details: Optional[Dict[str, Any]] = None,
        level: AuditLevel = AuditLevel.INFO,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AuditRecord:
        """
        Record an audit entry
        
        Args:
            user_id: User ID
            action: Action performed
            resource: Resource affected
            status: Audit status
            details: Additional details
            level: Audit level
            before_state: State before action
            after_state: State after action
            ip_address: IP address
            session_id: Session ID
            
        Returns:
            AuditRecord
        """
        if not self.audit_enabled:
            return None
        
        record = AuditRecord(
            id=f"audit_{int(time.time())}_{len(self.audit_records)}",
            timestamp=datetime.now(),
            user_id=user_id,
            action=action,
            resource=resource,
            status=status,
            details=details or {},
            ip_address=ip_address,
            session_id=session_id,
            before_state=before_state,
            after_state=after_state,
            level=level,
        )
        
        self.audit_records.append(record)
        
        # Trim records if needed
        if len(self.audit_records) > self.max_records:
            self.audit_records = self.audit_records[-self.max_records:]
        
        # Log to file
        self._write_audit_log(record)
        
        # Log critical events
        if level in [AuditLevel.ERROR, AuditLevel.CRITICAL, AuditLevel.SECURITY]:
            logger.warning(f"Audit: {level.value} - {user_id} {action.value} {resource} - {status.value}")
        
        return record
    
    def _write_audit_log(self, record: AuditRecord) -> None:
        """
        Write audit record to log file
        
        Args:
            record: Audit record
        """
        log_file = self.audit_log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
    
    # ============================================================
    # DATA LINEAGE
    # ============================================================
    
    def track_lineage(
        self,
        data_id: str,
        source: str,
        transformations: List[Dict[str, Any]],
        data: Optional[pd.DataFrame] = None
    ) -> DataLineage:
        """
        Track data lineage
        
        Args:
            data_id: Data ID
            source: Source of data
            transformations: Transformations applied
            data: Data for checksum
            
        Returns:
            DataLineage
        """
        # Calculate checksum
        checksum = ""
        if data is not None:
            checksum = self._calculate_checksum(data)
        
        lineage = DataLineage(
            data_id=data_id,
            source=source,
            transformations=transformations,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            version=1,
            checksum=checksum,
        )
        
        self.lineage_records[data_id] = lineage
        return lineage
    
    def update_lineage(
        self,
        data_id: str,
        transformations: List[Dict[str, Any]],
        data: Optional[pd.DataFrame] = None
    ) -> Optional[DataLineage]:
        """
        Update data lineage
        
        Args:
            data_id: Data ID
            transformations: Transformations applied
            data: Data for checksum
            
        Returns:
            Updated lineage or None
        """
        lineage = self.lineage_records.get(data_id)
        if not lineage:
            return None
        
        # Calculate checksum
        checksum = ""
        if data is not None:
            checksum = self._calculate_checksum(data)
        
        lineage.transformations.extend(transformations)
        lineage.updated_at = datetime.now()
        lineage.version += 1
        lineage.checksum = checksum
        
        return lineage
    
    def _calculate_checksum(self, data: pd.DataFrame) -> str:
        """Calculate data checksum"""
        try:
            df_bytes = data.to_csv(index=False).encode()
            return hashlib.sha256(df_bytes).hexdigest()
        except:
            return ""
    
    # ============================================================
    # AUDIT QUERIES
    # ============================================================
    
    def get_audit_records(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource: Optional[str] = None,
        status: Optional[AuditStatus] = None,
        level: Optional[AuditLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditRecord]:
        """
        Query audit records
        
        Args:
            user_id: Filter by user
            action: Filter by action
            resource: Filter by resource
            status: Filter by status
            level: Filter by level
            start_time: Start time
            end_time: End time
            limit: Maximum records
            
        Returns:
            List of audit records
        """
        records = self.audit_records.copy()
        
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        if action:
            records = [r for r in records if r.action == action]
        if resource:
            records = [r for r in records if r.resource == resource]
        if status:
            records = [r for r in records if r.status == status]
        if level:
            records = [r for r in records if r.level == level]
        if start_time:
            records = [r for r in records if r.timestamp >= start_time]
        if end_time:
            records = [r for r in records if r.timestamp <= end_time]
        
        return records[-limit:]
    
    def get_lineage(self, data_id: str) -> Optional[DataLineage]:
        """
        Get data lineage
        
        Args:
            data_id: Data ID
            
        Returns:
            DataLineage or None
        """
        return self.lineage_records.get(data_id)
    
    # ============================================================
    # AUDIT REPORTS
    # ============================================================
    
    def generate_audit_report(
        self,
        period_days: int = 30,
        title: Optional[str] = None
    ) -> AuditReport:
        """
        Generate audit report
        
        Args:
            period_days: Report period in days
            title: Report title
            
        Returns:
            AuditReport
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=period_days)
        
        records = self.get_audit_records(
            start_time=start_time,
            end_time=end_time,
            limit=self.max_records
        )
        
        # Generate summary
        summary = {
            "total_records": len(records),
            "by_action": {},
            "by_status": {},
            "by_level": {},
            "by_user": {},
        }
        
        for record in records:
            action = record.action.value
            status = record.status.value
            level = record.level.value
            user = record.user_id
            
            summary["by_action"][action] = summary["by_action"].get(action, 0) + 1
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            summary["by_level"][level] = summary["by_level"].get(level, 0) + 1
            summary["by_user"][user] = summary["by_user"].get(user, 0) + 1
        
        # Find violations
        violations = []
        for record in records:
            if record.status in [AuditStatus.FAILURE, AuditStatus.ERROR]:
                violations.append({
                    "record_id": record.id,
                    "user": record.user_id,
                    "action": record.action.value,
                    "resource": record.resource,
                    "reason": record.details.get("error", "Unknown error"),
                })
        
        # Generate recommendations
        recommendations = []
        if violations:
            recommendations.append(f"Investigate {len(violations)} failed audit records")
        
        # Check for security violations
        security_events = [r for r in records if r.level == AuditLevel.SECURITY]
        if security_events:
            recommendations.append(f"Review {len(security_events)} security events")
        
        # Check for access violations
        access_events = [r for r in records if r.action == AuditAction.ACCESS and r.status == AuditStatus.FAILURE]
        if access_events:
            recommendations.append("Review failed access attempts")
        
        report = AuditReport(
            id=f"audit_report_{int(time.time())}",
            title=title or f"Audit Report - {period_days} days",
            period={
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            summary=summary,
            records=records[-100:],
            violations=violations,
            recommendations=recommendations,
            compliance_status=len(violations) == 0,
            generated_at=datetime.now(),
        )
        
        self.audit_reports.append(report)
        return report
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get audit statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_audit_records": len(self.audit_records),
            "audit_enabled": self.audit_enabled,
            "total_lineage_records": len(self.lineage_records),
            "total_audit_reports": len(self.audit_reports),
            "last_audit": self.audit_records[-1].to_dict() if self.audit_records else None,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "AuditAction",
    "AuditStatus",
    "AuditLevel",
    
    # Dataclasses
    "AuditRecord",
    "DataLineage",
    "AuditReport",
    
    # Classes
    "DataAuditedEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

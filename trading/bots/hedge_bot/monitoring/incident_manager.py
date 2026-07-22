# trading/bots/hedge_bot/monitoring/incident_manager.py

"""
NEXUS HEDGE BOT - INCIDENT MANAGER
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced incident management system with lifecycle tracking, escalation,
root cause analysis, and post-mortem generation.

Version: 3.0.0
"""

import asyncio
import json
import sqlite3
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import aiohttp
import structlog
import yaml
from pydantic import BaseModel, Field, validator

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    SEV0 = "sev0"  # Critical - System down
    SEV1 = "sev1"  # Major - Significant impact
    SEV2 = "sev2"  # Moderate - Limited impact
    SEV3 = "sev3"  # Minor - Minimal impact
    SEV4 = "sev4"  # Informational


class IncidentStatus(str, Enum):
    """Incident lifecycle status."""
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"
    MITIGATED = "mitigated"
    ESCALATED = "escalated"


class IncidentCategory(str, Enum):
    """Incident categories."""
    SYSTEM = "system"
    NETWORK = "network"
    BROKER = "broker"
    TRADING = "trading"
    RISK = "risk"
    MARKET = "market"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    DATA = "data"
    PERFORMANCE = "performance"


class IncidentType(str, Enum):
    """Types of incidents."""
    OUTAGE = "outage"
    DEGRADATION = "degradation"
    SECURITY_BREACH = "security_breach"
    DATA_CORRUPTION = "data_corruption"
    BROKER_FAILURE = "broker_failure"
    TRADING_ERROR = "trading_error"
    RISK_VIOLATION = "risk_violation"
    MARKET_EVENT = "market_event"
    COMPLIANCE_VIOLATION = "compliance_violation"
    PERFORMANCE_ISSUE = "performance_issue"


# === DATA MODELS ===

@dataclass
class Incident:
    """Incident data model."""
    incident_id: str = field(default_factory=lambda: f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}")
    title: str = ""
    description: str = ""
    severity: IncidentSeverity = IncidentSeverity.SEV3
    status: IncidentStatus = IncidentStatus.INVESTIGATING
    category: IncidentCategory = IncidentCategory.SYSTEM
    type: IncidentType = IncidentType.OUTAGE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    detected_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    mitigated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    escalation_level: int = 0
    escalation_required: bool = False
    escalation_at: Optional[datetime] = None
    affected_components: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    impact_metrics: Dict[str, Any] = field(default_factory=dict)
    root_cause: Optional[str] = None
    resolution_steps: List[str] = field(default_factory=list)
    prevention_steps: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    related_incidents: List[str] = field(default_factory=list)
    related_alerts: List[str] = field(default_factory=list)
    timeline_entries: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_post_mortem_required: bool = False
    post_mortem_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "mitigated_at": self.mitigated_at.isoformat() if self.mitigated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "escalation_at": self.escalation_at.isoformat() if self.escalation_at else None,
            "severity": self.severity.value,
            "status": self.status.value,
            "category": self.category.value,
            "type": self.type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Incident":
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("detected_at"):
            data["detected_at"] = datetime.fromisoformat(data["detected_at"])
        if data.get("acknowledged_at"):
            data["acknowledged_at"] = datetime.fromisoformat(data["acknowledged_at"])
        if data.get("mitigated_at"):
            data["mitigated_at"] = datetime.fromisoformat(data["mitigated_at"])
        if data.get("resolved_at"):
            data["resolved_at"] = datetime.fromisoformat(data["resolved_at"])
        if data.get("closed_at"):
            data["closed_at"] = datetime.fromisoformat(data["closed_at"])
        if data.get("escalation_at"):
            data["escalation_at"] = datetime.fromisoformat(data["escalation_at"])
        data["severity"] = IncidentSeverity(data["severity"])
        data["status"] = IncidentStatus(data["status"])
        data["category"] = IncidentCategory(data["category"])
        data["type"] = IncidentType(data["type"])
        return cls(**data)


# === INCIDENT MANAGER ===

class IncidentManager:
    """
    Advanced incident management system with lifecycle tracking,
    escalation, root cause analysis, and post-mortem generation.
    """

    def __init__(
        self,
        config: Union[Dict[str, Any], str],
    ):
        """
        Initialize the IncidentManager.

        Args:
            config: Configuration dictionary or path to config file
        """
        if isinstance(config, str):
            with open(config, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = config

        self._lock = threading.RLock()
        self._closed = False

        # Database for persistent storage
        self._db_path = Path(self.config.get("db_path", "incidents.db"))
        self._initialize_db()

        # In-memory cache
        self._incident_cache: Dict[str, Incident] = {}
        self._active_incidents: Dict[str, Incident] = {}

        # Escalation configuration
        self._escalation_policies = self.config.get("escalation_policies", {})
        self._severity_slos = self.config.get("severity_slos", {})

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._escalation_task: Optional[asyncio.Task] = None

        # Start background tasks
        self._start_background_tasks()

        logger.info(
            "incident_manager_initialized",
            db_path=str(self._db_path),
            escalation_policies=len(self._escalation_policies),
        )

    def _initialize_db(self) -> None:
        """Initialize the SQLite database."""
        self._db = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                category TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                detected_at TEXT,
                acknowledged_at TEXT,
                mitigated_at TEXT,
                resolved_at TEXT,
                closed_at TEXT,
                assigned_to TEXT,
                escalation_level INTEGER DEFAULT 0,
                escalation_required INTEGER DEFAULT 0,
                escalation_at TEXT,
                affected_components TEXT,
                affected_symbols TEXT,
                impact_metrics TEXT,
                root_cause TEXT,
                resolution_steps TEXT,
                prevention_steps TEXT,
                lessons_learned TEXT,
                related_incidents TEXT,
                related_alerts TEXT,
                timeline_entries TEXT,
                tags TEXT,
                metadata TEXT,
                is_post_mortem_required INTEGER DEFAULT 0,
                post_mortem_url TEXT
            )
        """)

        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_category ON incidents(category)
        """)

        logger.info("incident_db_initialized", db_path=str(self._db_path))

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        try:
            loop = asyncio.get_event_loop()

            # Escalation task
            self._escalation_task = loop.create_task(self._escalation_loop())

            logger.info("background_tasks_started")
        except RuntimeError:
            logger.warning("no_event_loop_available_background_tasks_disabled")

    async def _escalation_loop(self) -> None:
        """Background task for handling incident escalations."""
        while not self._closed:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                await self._process_escalations()
            except Exception as e:
                logger.error("escalation_loop_error", error=str(e))

    async def _process_escalations(self) -> None:
        """Process incident escalations."""
        with self._lock:
            now = datetime.utcnow()
            escalated_ids = []

            for incident_id, incident in self._active_incidents.items():
                if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
                    continue

                # Check escalation policy
                policy = self._escalation_policies.get(incident.severity.value)
                if not policy:
                    continue

                # Check if escalation is needed
                age = (now - incident.created_at).total_seconds()
                escalation_threshold = policy.get("escalation_timeout", 300)  # 5 minutes default

                if age > escalation_threshold:
                    if incident.escalation_level < policy.get("max_escalations", 3):
                        incident.escalation_level += 1
                        incident.escalation_required = True
                        incident.escalation_at = now
                        incident.status = IncidentStatus.ESCALATED
                        escalated_ids.append(incident_id)

                        # Log escalation
                        self._add_timeline_entry(
                            incident,
                            f"Escalated to level {incident.escalation_level}",
                            "escalation",
                            {"level": incident.escalation_level, "policy": policy},
                        )

                        logger.warning(
                            "incident_escalated",
                            incident_id=incident_id,
                            severity=incident.severity.value,
                            escalation_level=incident.escalation_level,
                        )

            # Update escalated incidents
            for incident_id in escalated_ids:
                self._save_incident(self._active_incidents[incident_id])

    def create_incident(
        self,
        title: str,
        description: str,
        severity: Union[str, IncidentSeverity] = IncidentSeverity.SEV3,
        category: Union[str, IncidentCategory] = IncidentCategory.SYSTEM,
        type: Union[str, IncidentType] = IncidentType.OUTAGE,
        affected_components: Optional[List[str]] = None,
        affected_symbols: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        assigned_to: Optional[str] = None,
    ) -> Incident:
        """
        Create a new incident.

        Args:
            title: Incident title
            description: Incident description
            severity: Incident severity
            category: Incident category
            type: Incident type
            affected_components: Affected components
            affected_symbols: Affected trading symbols
            tags: Incident tags
            assigned_to: Assigned team member

        Returns:
            Created Incident object
        """
        if isinstance(severity, str):
            severity = IncidentSeverity(severity)
        if isinstance(category, str):
            category = IncidentCategory(category)
        if isinstance(type, str):
            type = IncidentType(type)

        incident = Incident(
            title=title,
            description=description,
            severity=severity,
            category=category,
            type=type,
            affected_components=affected_components or [],
            affected_symbols=affected_symbols or [],
            tags=tags or [],
            assigned_to=assigned_to,
            detected_at=datetime.utcnow(),
        )

        # Add initial timeline entry
        self._add_timeline_entry(
            incident,
            f"Incident created: {title}",
            "creation",
            {"severity": severity.value, "category": category.value},
        )

        with self._lock:
            self._incident_cache[incident.incident_id] = incident
            self._active_incidents[incident.incident_id] = incident
            self._save_incident(incident)

        # Check if post-mortem is required
        if severity in (IncidentSeverity.SEV0, IncidentSeverity.SEV1):
            incident.is_post_mortem_required = True
            self._save_incident(incident)

        logger.info(
            "incident_created",
            incident_id=incident.incident_id,
            severity=severity.value,
            category=category.value,
            title=title,
        )

        return incident

    def update_incident(
        self,
        incident_id: str,
        status: Optional[Union[str, IncidentStatus]] = None,
        description: Optional[str] = None,
        assigned_to: Optional[str] = None,
        root_cause: Optional[str] = None,
        resolution_steps: Optional[List[str]] = None,
        prevention_steps: Optional[List[str]] = None,
    ) -> Optional[Incident]:
        """
        Update an incident.

        Args:
            incident_id: ID of the incident
            status: New status
            description: New description
            assigned_to: New assignee
            root_cause: Root cause
            resolution_steps: Resolution steps
            prevention_steps: Prevention steps

        Returns:
            Updated Incident or None if not found
        """
        with self._lock:
            incident = self._incident_cache.get(incident_id)
            if not incident:
                return None

            old_status = incident.status

            if status:
                if isinstance(status, str):
                    status = IncidentStatus(status)
                incident.status = status
                incident.updated_at = datetime.utcnow()

                # Status-specific actions
                if status == IncidentStatus.ACKNOWLEDGED:
                    incident.acknowledged_at = datetime.utcnow()
                    self._add_timeline_entry(
                        incident,
                        f"Acknowledged by {assigned_to or 'unknown'}",
                        "acknowledgment",
                        {"assigned_to": assigned_to},
                    )

                elif status == IncidentStatus.MITIGATED:
                    incident.mitigated_at = datetime.utcnow()
                    self._add_timeline_entry(
                        incident,
                        "Incident mitigated",
                        "mitigation",
                        {},
                    )

                elif status == IncidentStatus.RESOLVED:
                    incident.resolved_at = datetime.utcnow()
                    self._add_timeline_entry(
                        incident,
                        "Incident resolved",
                        "resolution",
                        {"root_cause": root_cause},
                    )
                    # Remove from active incidents
                    if incident_id in self._active_incidents:
                        del self._active_incidents[incident_id]

                elif status == IncidentStatus.CLOSED:
                    incident.closed_at = datetime.utcnow()
                    self._add_timeline_entry(
                        incident,
                        "Incident closed",
                        "closure",
                        {},
                    )

            if description:
                incident.description = description

            if assigned_to:
                incident.assigned_to = assigned_to

            if root_cause:
                incident.root_cause = root_cause

            if resolution_steps:
                incident.resolution_steps = resolution_steps

            if prevention_steps:
                incident.prevention_steps = prevention_steps

            self._save_incident(incident)

            logger.info(
                "incident_updated",
                incident_id=incident_id,
                old_status=old_status.value if old_status else None,
                new_status=incident.status.value,
            )

            return incident

    def add_timeline_entry(
        self,
        incident_id: str,
        message: str,
        entry_type: str = "note",
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a timeline entry to an incident.

        Args:
            incident_id: ID of the incident
            message: Entry message
            entry_type: Type of entry
            data: Additional data

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            incident = self._incident_cache.get(incident_id)
            if not incident:
                return False

            self._add_timeline_entry(incident, message, entry_type, data)
            self._save_incident(incident)
            return True

    def _add_timeline_entry(
        self,
        incident: Incident,
        message: str,
        entry_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a timeline entry to an incident."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "type": entry_type,
            "data": data or {},
        }
        incident.timeline_entries.append(entry)
        incident.updated_at = datetime.utcnow()

    def resolve_incident(
        self,
        incident_id: str,
        root_cause: Optional[str] = None,
        resolution_steps: Optional[List[str]] = None,
        prevention_steps: Optional[List[str]] = None,
    ) -> Optional[Incident]:
        """
        Resolve an incident.

        Args:
            incident_id: ID of the incident
            root_cause: Root cause of the incident
            resolution_steps: Steps taken to resolve
            prevention_steps: Steps to prevent recurrence

        Returns:
            Updated Incident or None if not found
        """
        return self.update_incident(
            incident_id=incident_id,
            status=IncidentStatus.RESOLVED,
            root_cause=root_cause,
            resolution_steps=resolution_steps,
            prevention_steps=prevention_steps,
        )

    def close_incident(self, incident_id: str) -> Optional[Incident]:
        """
        Close a resolved incident.

        Args:
            incident_id: ID of the incident

        Returns:
            Updated Incident or None if not found
        """
        return self.update_incident(
            incident_id=incident_id,
            status=IncidentStatus.CLOSED,
        )

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """
        Get an incident by ID.

        Args:
            incident_id: ID of the incident

        Returns:
            Incident object or None if not found
        """
        # Check cache first
        if incident_id in self._incident_cache:
            return self._incident_cache[incident_id]

        # Query database
        cursor = self._db.execute(
            "SELECT * FROM incidents WHERE incident_id = ?",
            (incident_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        data = self._deserialize_incident_data(data)

        incident = Incident.from_dict(data)
        self._incident_cache[incident_id] = incident
        return incident

    def get_active_incidents(
        self,
        severity: Optional[IncidentSeverity] = None,
        category: Optional[IncidentCategory] = None,
    ) -> List[Incident]:
        """
        Get all active incidents.

        Args:
            severity: Filter by severity
            category: Filter by category

        Returns:
            List of active incidents
        """
        incidents = list(self._active_incidents.values())

        if severity:
            incidents = [i for i in incidents if i.severity == severity]

        if category:
            incidents = [i for i in incidents if i.category == category]

        return sorted(incidents, key=lambda i: (i.severity.value, i.created_at))

    def get_incidents(
        self,
        status: Optional[Union[str, IncidentStatus]] = None,
        severity: Optional[Union[str, IncidentSeverity]] = None,
        category: Optional[Union[str, IncidentCategory]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Incident]:
        """
        Get incidents with filtering.

        Args:
            status: Filter by status
            severity: Filter by severity
            category: Filter by category
            start_date: Start date
            end_date: End date
            limit: Maximum number of incidents
            offset: Pagination offset

        Returns:
            List of incidents
        """
        sql = "SELECT * FROM incidents WHERE 1=1"
        params = []

        if status:
            if isinstance(status, str):
                status = IncidentStatus(status)
            sql += " AND status = ?"
            params.append(status.value)

        if severity:
            if isinstance(severity, str):
                severity = IncidentSeverity(severity)
            sql += " AND severity = ?"
            params.append(severity.value)

        if category:
            if isinstance(category, str):
                category = IncidentCategory(category)
            sql += " AND category = ?"
            params.append(category.value)

        if start_date:
            sql += " AND created_at >= ?"
            params.append(start_date.isoformat())

        if end_date:
            sql += " AND created_at <= ?"
            params.append(end_date.isoformat())

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        incidents = []

        for row in rows:
            data = dict(zip(columns, row))
            data = self._deserialize_incident_data(data)
            incidents.append(Incident.from_dict(data))

        return incidents

    def _deserialize_incident_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize JSON fields in incident data."""
        json_fields = [
            "affected_components", "affected_symbols", "impact_metrics",
            "resolution_steps", "prevention_steps", "lessons_learned",
            "related_incidents", "related_alerts", "timeline_entries",
            "tags", "metadata"
        ]

        for field in json_fields:
            if field in data and data[field]:
                try:
                    data[field] = json.loads(data[field])
                except json.JSONDecodeError:
                    data[field] = []

        return data

    def _save_incident(self, incident: Incident) -> None:
        """Save incident to database."""
        try:
            self._db.execute("""
                INSERT OR REPLACE INTO incidents (
                    incident_id, title, description, severity, status, category, type,
                    created_at, updated_at, detected_at, acknowledged_at, mitigated_at,
                    resolved_at, closed_at, assigned_to, escalation_level,
                    escalation_required, escalation_at, affected_components,
                    affected_symbols, impact_metrics, root_cause, resolution_steps,
                    prevention_steps, lessons_learned, related_incidents,
                    related_alerts, timeline_entries, tags, metadata,
                    is_post_mortem_required, post_mortem_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident.incident_id,
                incident.title,
                incident.description,
                incident.severity.value,
                incident.status.value,
                incident.category.value,
                incident.type.value,
                incident.created_at.isoformat(),
                incident.updated_at.isoformat(),
                incident.detected_at.isoformat() if incident.detected_at else None,
                incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
                incident.mitigated_at.isoformat() if incident.mitigated_at else None,
                incident.resolved_at.isoformat() if incident.resolved_at else None,
                incident.closed_at.isoformat() if incident.closed_at else None,
                incident.assigned_to,
                incident.escalation_level,
                1 if incident.escalation_required else 0,
                incident.escalation_at.isoformat() if incident.escalation_at else None,
                json.dumps(incident.affected_components),
                json.dumps(incident.affected_symbols),
                json.dumps(incident.impact_metrics),
                incident.root_cause,
                json.dumps(incident.resolution_steps),
                json.dumps(incident.prevention_steps),
                json.dumps(incident.lessons_learned),
                json.dumps(incident.related_incidents),
                json.dumps(incident.related_alerts),
                json.dumps(incident.timeline_entries),
                json.dumps(incident.tags),
                json.dumps(incident.metadata),
                1 if incident.is_post_mortem_required else 0,
                incident.post_mortem_url,
            ))
        except Exception as e:
            logger.error(
                "failed_to_save_incident",
                incident_id=incident.incident_id,
                error=str(e),
            )

    def generate_post_mortem(self, incident_id: str) -> Optional[str]:
        """
        Generate a post-mortem report for an incident.

        Args:
            incident_id: ID of the incident

        Returns:
            Post-mortem content as string, or None if not found
        """
        incident = self.get_incident(incident_id)
        if not incident:
            return None

        # Generate post-mortem
        post_mortem = f"""
# Post-Mortem Report

## Incident Information

- **Incident ID:** {incident.incident_id}
- **Title:** {incident.title}
- **Severity:** {incident.severity.value}
- **Status:** {incident.status.value}
- **Category:** {incident.category.value}
- **Type:** {incident.type.value}
- **Created:** {incident.created_at.isoformat()}
- **Resolved:** {incident.resolved_at.isoformat() if incident.resolved_at else 'Not resolved'}

## Description

{incident.description}

## Impact

- **Affected Components:** {', '.join(incident.affected_components) if incident.affected_components else 'None'}
- **Affected Symbols:** {', '.join(incident.affected_symbols) if incident.affected_symbols else 'None'}

## Root Cause

{incident.root_cause or 'Not determined'}

## Timeline

"""
        for entry in incident.timeline_entries:
            post_mortem += f"- **{entry['timestamp']}** - {entry['message']}\n"

        post_mortem += f"""
## Resolution Steps

{chr(10).join([f"- {step}" for step in incident.resolution_steps]) if incident.resolution_steps else '- Not specified'}

## Prevention Steps

{chr(10).join([f"- {step}" for step in incident.prevention_steps]) if incident.prevention_steps else '- Not specified'}

## Lessons Learned

{chr(10).join([f"- {lesson}" for lesson in incident.lessons_learned]) if incident.lessons_learned else '- Not specified'}

## Related Incidents

{chr(10).join([f"- {related}" for related in incident.related_incidents]) if incident.related_incidents else '- None'}

---
*Generated by NEXUS Incident Manager v3.0.0*
"""

        # Save post-mortem
        incident.post_mortem_url = f"post_mortem_{incident_id}.md"
        self._save_incident(incident)

        # Save to file
        pm_path = Path(self.config.get("post_mortem_dir", "post_mortems"))
        pm_path.mkdir(parents=True, exist_ok=True)
        file_path = pm_path / f"{incident.incident_id}_post_mortem.md"

        with open(file_path, "w") as f:
            f.write(post_mortem)

        logger.info(
            "post_mortem_generated",
            incident_id=incident_id,
            path=str(file_path),
        )

        return post_mortem

    def add_lessons_learned(
        self,
        incident_id: str,
        lesson: str,
    ) -> bool:
        """
        Add a lesson learned to an incident.

        Args:
            incident_id: ID of the incident
            lesson: Lesson learned

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            incident = self._incident_cache.get(incident_id)
            if not incident:
                return False

            incident.lessons_learned.append(lesson)
            self._save_incident(incident)
            return True

    def link_incidents(
        self,
        incident_id_1: str,
        incident_id_2: str,
    ) -> bool:
        """
        Link two incidents together.

        Args:
            incident_id_1: First incident ID
            incident_id_2: Second incident ID

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            incident1 = self._incident_cache.get(incident_id_1)
            incident2 = self._incident_cache.get(incident_id_2)

            if not incident1 or not incident2:
                return False

            if incident_id_2 not in incident1.related_incidents:
                incident1.related_incidents.append(incident_id_2)
                self._save_incident(incident1)

            if incident_id_1 not in incident2.related_incidents:
                incident2.related_incidents.append(incident_id_1)
                self._save_incident(incident2)

            return True

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get incident manager metrics.

        Returns:
            Dictionary of metrics
        """
        total = self._get_total_incidents()
        active = len(self._active_incidents)
        by_severity = self._get_incident_counts_by_severity()
        by_status = self._get_incident_counts_by_status()

        return {
            "total_incidents": total,
            "active_incidents": active,
            "by_severity": by_severity,
            "by_status": by_status,
            "escalation_rate": self._calculate_escalation_rate(),
            "mean_time_to_resolve": self._calculate_mttr(),
            "mean_time_to_acknowledge": self._calculate_mtta(),
        }

    def _get_total_incidents(self) -> int:
        """Get total number of incidents in database."""
        cursor = self._db.execute("SELECT COUNT(*) FROM incidents")
        return cursor.fetchone()[0]

    def _get_incident_counts_by_severity(self) -> Dict[str, int]:
        """Get incident counts grouped by severity."""
        cursor = self._db.execute(
            "SELECT severity, COUNT(*) FROM incidents GROUP BY severity"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _get_incident_counts_by_status(self) -> Dict[str, int]:
        """Get incident counts grouped by status."""
        cursor = self._db.execute(
            "SELECT status, COUNT(*) FROM incidents GROUP BY status"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _calculate_escalation_rate(self) -> float:
        """Calculate the escalation rate."""
        total = self._get_total_incidents()
        if total == 0:
            return 0.0

        cursor = self._db.execute(
            "SELECT COUNT(*) FROM incidents WHERE escalation_required = 1"
        )
        escalated = cursor.fetchone()[0]
        return round((escalated / total) * 100, 2)

    def _calculate_mttr(self) -> float:
        """Calculate Mean Time To Resolve (MTTR) in minutes."""
        cursor = self._db.execute("""
            SELECT AVG(
                (julianday(resolved_at) - julianday(created_at)) * 24 * 60
            ) FROM incidents WHERE resolved_at IS NOT NULL
        """)
        result = cursor.fetchone()[0]
        return round(result if result else 0, 2)

    def _calculate_mtta(self) -> float:
        """Calculate Mean Time To Acknowledge (MTTA) in minutes."""
        cursor = self._db.execute("""
            SELECT AVG(
                (julianday(acknowledged_at) - julianday(created_at)) * 24 * 60
            ) FROM incidents WHERE acknowledged_at IS NOT NULL
        """)
        result = cursor.fetchone()[0]
        return round(result if result else 0, 2)

    def close(self) -> None:
        """Close the incident manager."""
        if self._closed:
            return

        self._closed = True

        if hasattr(self, "_db") and self._db:
            self._db.close()

        logger.info("incident_manager_closed")

    def __enter__(self) -> "IncidentManager":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# === MODULE EXPORTS ===

__all__ = [
    "IncidentManager",
    "Incident",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentCategory",
    "IncidentType",
]

logger.info("incident_manager_module_loaded", version="3.0.0")

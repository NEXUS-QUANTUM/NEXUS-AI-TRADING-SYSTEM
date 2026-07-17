"""
NEXUS AI TRADING SYSTEM - Incident Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced incident management system for tracking, analyzing, and resolving
incidents in the trading system with root cause analysis, SLA tracking,
and post-mortem reporting.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import yaml
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
INCIDENT_COUNTER = Counter(
    "nexus_incidents_total",
    "Total number of incidents",
    ["severity", "status", "type"],
)
INCIDENT_RESOLUTION_TIME = Histogram(
    "nexus_incident_resolution_time_seconds",
    "Time taken to resolve incidents",
    ["severity"],
)
INCIDENT_ACTIVE = Gauge(
    "nexus_incidents_active",
    "Number of currently active incidents",
    ["severity"],
)
SLA_BREACH_COUNTER = Counter(
    "nexus_sla_breaches_total",
    "Total number of SLA breaches",
    ["severity"],
)


class IncidentSeverity(Enum):
    """Incident severity levels."""

    SEV1 = "sev1"  # Critical - Immediate action required
    SEV2 = "sev2"  # High - Urgent action required
    SEV3 = "sev3"  # Medium - Normal priority
    SEV4 = "sev4"  # Low - Low priority
    SEV5 = "sev5"  # Info - Informational


class IncidentStatus(Enum):
    """Incident status states."""

    DETECTED = "detected"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentType(Enum):
    """Types of incidents."""

    SYSTEM = "system"
    TRADING = "trading"
    DATA = "data"
    NETWORK = "network"
    SECURITY = "security"
    BROKER = "broker"
    MODEL = "model"
    PERFORMANCE = "performance"
    USER = "user"
    THIRD_PARTY = "third_party"


@dataclass
class SLAConfig:
    """SLA configuration for incident response."""

    severity: IncidentSeverity
    detection_time_minutes: int
    response_time_minutes: int
    resolution_time_minutes: int
    notification_escalation_minutes: int = 15

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "severity": self.severity.value,
            "detection_time_minutes": self.detection_time_minutes,
            "response_time_minutes": self.response_time_minutes,
            "resolution_time_minutes": self.resolution_time_minutes,
            "notification_escalation_minutes": self.notification_escalation_minutes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SLAConfig":
        """Create from dictionary."""
        return cls(
            severity=IncidentSeverity(data["severity"]),
            detection_time_minutes=data["detection_time_minutes"],
            response_time_minutes=data["response_time_minutes"],
            resolution_time_minutes=data["resolution_time_minutes"],
            notification_escalation_minutes=data.get("notification_escalation_minutes", 15),
        )


@dataclass
class Incident:
    """Incident record."""

    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    type: IncidentType
    affected_components: List[str]
    detected_at: datetime
    investigating_at: Optional[datetime] = None
    identified_at: Optional[datetime] = None
    mitigating_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    assigned_team: Optional[str] = None
    root_cause: Optional[str] = None
    resolution_notes: Optional[str] = None
    related_alerts: List[str] = field(default_factory=list)
    related_incidents: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    sla_breached: bool = False
    escalation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "status": self.status.value,
            "type": self.type.value,
            "affected_components": self.affected_components,
            "detected_at": self.detected_at.isoformat(),
            "investigating_at": self.investigating_at.isoformat() if self.investigating_at else None,
            "identified_at": self.identified_at.isoformat() if self.identified_at else None,
            "mitigating_at": self.mitigating_at.isoformat() if self.mitigating_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "assigned_to": self.assigned_to,
            "assigned_team": self.assigned_team,
            "root_cause": self.root_cause,
            "resolution_notes": self.resolution_notes,
            "related_alerts": self.related_alerts,
            "related_incidents": self.related_incidents,
            "tags": self.tags,
            "timeline": self.timeline,
            "metadata": self.metadata,
            "sla_breached": self.sla_breached,
            "escalation_count": self.escalation_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Incident":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            severity=IncidentSeverity(data["severity"]),
            status=IncidentStatus(data["status"]),
            type=IncidentType(data["type"]),
            affected_components=data.get("affected_components", []),
            detected_at=datetime.fromisoformat(data["detected_at"]),
            investigating_at=datetime.fromisoformat(data["investigating_at"]) if data.get("investigating_at") else None,
            identified_at=datetime.fromisoformat(data["identified_at"]) if data.get("identified_at") else None,
            mitigating_at=datetime.fromisoformat(data["mitigating_at"]) if data.get("mitigating_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            assigned_to=data.get("assigned_to"),
            assigned_team=data.get("assigned_team"),
            root_cause=data.get("root_cause"),
            resolution_notes=data.get("resolution_notes"),
            related_alerts=data.get("related_alerts", []),
            related_incidents=data.get("related_incidents", []),
            tags=data.get("tags", []),
            timeline=data.get("timeline", []),
            metadata=data.get("metadata", {}),
            sla_breached=data.get("sla_breached", False),
            escalation_count=data.get("escalation_count", 0),
        )


@dataclass
class IncidentReport:
    """Post-mortem incident report."""

    incident_id: str
    title: str
    severity: IncidentSeverity
    type: IncidentType
    duration_minutes: float
    root_cause: str
    timeline: List[Dict[str, Any]]
    impact: Dict[str, Any]
    action_items: List[Dict[str, Any]]
    lessons_learned: List[str]
    recommendations: List[str]
    created_at: datetime
    created_by: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "severity": self.severity.value,
            "type": self.type.value,
            "duration_minutes": self.duration_minutes,
            "root_cause": self.root_cause,
            "timeline": self.timeline,
            "impact": self.impact,
            "action_items": self.action_items,
            "lessons_learned": self.lessons_learned,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
        }


class IncidentManager:
    """
    Advanced incident management system with SLA tracking and post-mortems.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        alert_manager: Optional[Any] = None,
    ):
        """
        Initialize the incident manager.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
            alert_manager: Alert manager instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.alert_manager = alert_manager
        self._lock = asyncio.Lock()
        self._incidents: Dict[str, Incident] = {}
        self._reports: Dict[str, IncidentReport] = {}
        self._sla_configs: Dict[IncidentSeverity, SLAConfig] = {}
        self._notification_handlers: List[Callable] = []
        self._monitor_task: Optional[asyncio.Task] = None

        # Load configuration
        self.incident_config = self.config.get("incident_manager", {})
        self.storage_path = Path(self.incident_config.get("storage_path", "./data/incidents"))
        self.auto_report_generation = self.incident_config.get("auto_report_generation", True)
        self.escalation_enabled = self.incident_config.get("escalation_enabled", True)
        self.max_incident_age_days = self.incident_config.get("max_incident_age_days", 30)

        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load SLA configs
        self._load_sla_configs()

        # Load stored incidents
        self._load_incidents()

        # Start monitor task
        self._start_monitor_task()

        logger.info("IncidentManager initialized")

    def _load_sla_configs(self):
        """Load SLA configurations."""
        default_sla = {
            IncidentSeverity.SEV1: SLAConfig(
                severity=IncidentSeverity.SEV1,
                detection_time_minutes=1,
                response_time_minutes=5,
                resolution_time_minutes=15,
                notification_escalation_minutes=2,
            ),
            IncidentSeverity.SEV2: SLAConfig(
                severity=IncidentSeverity.SEV2,
                detection_time_minutes=5,
                response_time_minutes=15,
                resolution_time_minutes=60,
                notification_escalation_minutes=5,
            ),
            IncidentSeverity.SEV3: SLAConfig(
                severity=IncidentSeverity.SEV3,
                detection_time_minutes=15,
                response_time_minutes=30,
                resolution_time_minutes=240,
                notification_escalation_minutes=10,
            ),
            IncidentSeverity.SEV4: SLAConfig(
                severity=IncidentSeverity.SEV4,
                detection_time_minutes=30,
                response_time_minutes=60,
                resolution_time_minutes=480,
                notification_escalation_minutes=15,
            ),
            IncidentSeverity.SEV5: SLAConfig(
                severity=IncidentSeverity.SEV5,
                detection_time_minutes=60,
                response_time_minutes=120,
                resolution_time_minutes=1440,
                notification_escalation_minutes=30,
            ),
        }

        self._sla_configs = default_sla

        # Override with config if provided
        for severity, config in self.incident_config.get("sla_configs", {}).items():
            try:
                severity_enum = IncidentSeverity(severity)
                self._sla_configs[severity_enum] = SLAConfig.from_dict(config)
            except Exception as e:
                logger.error(f"Error loading SLA config for {severity}: {e}")

    def _load_incidents(self):
        """Load incidents from storage."""
        try:
            for file_path in self.storage_path.glob("*.json"):
                with open(file_path, "r") as f:
                    data = json.load(f)
                    incident = Incident.from_dict(data)
                    self._incidents[incident.id] = incident

            logger.info(f"Loaded {len(self._incidents)} incidents from storage")

            # Load reports
            report_path = self.storage_path / "reports"
            if report_path.exists():
                for file_path in report_path.glob("*.json"):
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        report = IncidentReport(
                            incident_id=data["incident_id"],
                            title=data["title"],
                            severity=IncidentSeverity(data["severity"]),
                            type=IncidentType(data["type"]),
                            duration_minutes=data["duration_minutes"],
                            root_cause=data["root_cause"],
                            timeline=data["timeline"],
                            impact=data["impact"],
                            action_items=data["action_items"],
                            lessons_learned=data["lessons_learned"],
                            recommendations=data["recommendations"],
                            created_at=datetime.fromisoformat(data["created_at"]),
                            created_by=data["created_by"],
                        )
                        self._reports[data["incident_id"]] = report

        except Exception as e:
            logger.error(f"Error loading incidents: {e}")

    def _start_monitor_task(self):
        """Start the incident monitor task."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """Background loop for monitoring incidents."""
        while True:
            try:
                await self._check_sla_breaches()
                await self._escalate_incidents()
                await self._auto_close_old_incidents()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(10)

    async def create_incident(
        self,
        title: str,
        description: str,
        severity: Union[IncidentSeverity, str],
        type: Union[IncidentType, str],
        affected_components: List[str],
        source: Optional[str] = None,
        related_alerts: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Incident:
        """
        Create a new incident.

        Args:
            title: Incident title
            description: Incident description
            severity: Incident severity
            type: Incident type
            affected_components: Affected components
            source: Source of incident
            related_alerts: Related alert IDs
            tags: Incident tags
            metadata: Additional metadata

        Returns:
            Created incident
        """
        # Parse severity and type
        if isinstance(severity, str):
            severity = IncidentSeverity(severity)
        if isinstance(type, str):
            type = IncidentType(type)

        # Generate incident ID
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}-{int(time.time())}"

        # Create incident
        incident = Incident(
            id=incident_id,
            title=title,
            description=description,
            severity=severity,
            status=IncidentStatus.DETECTED,
            type=type,
            affected_components=affected_components,
            detected_at=datetime.utcnow(),
            related_alerts=related_alerts or [],
            tags=tags or [],
            metadata=metadata or {},
        )

        # Add timeline entry
        incident.timeline.append({
            "timestamp": incident.detected_at.isoformat(),
            "event": "incident_detected",
            "message": f"Incident detected with severity {severity.value}",
        })

        # Store incident
        async with self._lock:
            self._incidents[incident_id] = incident
            await self._save_incident(incident)

        # Update metrics
        INCIDENT_COUNTER.labels(
            severity=severity.value,
            status=incident.status.value,
            type=type.value,
        ).inc()
        INCIDENT_ACTIVE.labels(severity=severity.value).inc()

        # Send notification
        await self._notify_incident_created(incident)

        logger.info(f"Incident {incident_id} created: {title} ({severity.value})")

        return incident

    async def update_incident_status(
        self,
        incident_id: str,
        status: Union[IncidentStatus, str],
        notes: Optional[str] = None,
        user: Optional[str] = None,
    ) -> Optional[Incident]:
        """
        Update incident status.

        Args:
            incident_id: Incident ID
            status: New status
            notes: Status update notes
            user: User performing the update

        Returns:
            Updated incident or None
        """
        if isinstance(status, str):
            status = IncidentStatus(status)

        async with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                return None

            old_status = incident.status
            incident.status = status

            # Update timestamps
            now = datetime.utcnow()
            if status == IncidentStatus.INVESTIGATING and not incident.investigating_at:
                incident.investigating_at = now
            elif status == IncidentStatus.IDENTIFIED and not incident.identified_at:
                incident.identified_at = now
            elif status == IncidentStatus.MITIGATING and not incident.mitigating_at:
                incident.mitigating_at = now
            elif status == IncidentStatus.RESOLVED and not incident.resolved_at:
                incident.resolved_at = now
                # Record resolution time
                resolution_time = (incident.resolved_at - incident.detected_at).total_seconds()
                INCIDENT_RESOLUTION_TIME.labels(
                    severity=incident.severity.value
                ).observe(resolution_time)
                INCIDENT_ACTIVE.labels(severity=incident.severity.value).dec()
            elif status == IncidentStatus.CLOSED and not incident.closed_at:
                incident.closed_at = now

            # Add timeline entry
            incident.timeline.append({
                "timestamp": now.isoformat(),
                "event": f"status_changed",
                "from_status": old_status.value,
                "to_status": status.value,
                "notes": notes or "",
                "user": user or "system",
            })

            # Save incident
            await self._save_incident(incident)

            # Update metrics
            INCIDENT_COUNTER.labels(
                severity=incident.severity.value,
                status=status.value,
                type=incident.type.value,
            ).inc()

            # Generate report if resolved
            if status == IncidentStatus.RESOLVED and self.auto_report_generation:
                await self._generate_incident_report(incident_id, user or "system")

            # Send notification
            await self._notify_incident_updated(incident, old_status)

            logger.info(f"Incident {incident_id} status updated to {status.value}")

            return incident

    async def add_incident_timeline(
        self,
        incident_id: str,
        event: str,
        message: str,
        user: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add timeline entry to an incident.

        Args:
            incident_id: Incident ID
            event: Event name
            message: Event message
            user: User performing the action
            data: Additional event data

        Returns:
            True if successful
        """
        async with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                return False

            incident.timeline.append({
                "timestamp": datetime.utcnow().isoformat(),
                "event": event,
                "message": message,
                "user": user or "system",
                "data": data or {},
            })

            await self._save_incident(incident)
            return True

    async def resolve_incident(
        self,
        incident_id: str,
        root_cause: str,
        resolution_notes: str,
        user: str = "system",
    ) -> Optional[Incident]:
        """
        Resolve an incident with root cause analysis.

        Args:
            incident_id: Incident ID
            root_cause: Root cause of the incident
            resolution_notes: Resolution notes
            user: User resolving the incident

        Returns:
            Resolved incident or None
        """
        incident = await self.update_incident_status(
            incident_id,
            IncidentStatus.RESOLVED,
            resolution_notes,
            user,
        )

        if incident:
            incident.root_cause = root_cause
            incident.resolution_notes = resolution_notes

            # Add root cause to timeline
            await self.add_incident_timeline(
                incident_id,
                "root_cause_identified",
                f"Root cause identified: {root_cause}",
                user,
            )

            await self._save_incident(incident)

        return incident

    async def close_incident(
        self,
        incident_id: str,
        user: str = "system",
    ) -> Optional[Incident]:
        """
        Close a resolved incident.

        Args:
            incident_id: Incident ID
            user: User closing the incident

        Returns:
            Closed incident or None
        """
        return await self.update_incident_status(
            incident_id,
            IncidentStatus.CLOSED,
            user=user,
        )

    async def assign_incident(
        self,
        incident_id: str,
        assigned_to: Optional[str] = None,
        assigned_team: Optional[str] = None,
        user: str = "system",
    ) -> bool:
        """
        Assign an incident to a person or team.

        Args:
            incident_id: Incident ID
            assigned_to: Person assigned
            assigned_team: Team assigned
            user: User performing the assignment

        Returns:
            True if successful
        """
        async with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                return False

            incident.assigned_to = assigned_to
            incident.assigned_team = assigned_team

            incident.timeline.append({
                "timestamp": datetime.utcnow().isoformat(),
                "event": "assigned",
                "message": f"Assigned to {assigned_to or assigned_team}",
                "user": user,
            })

            await self._save_incident(incident)
            logger.info(f"Incident {incident_id} assigned to {assigned_to or assigned_team}")
            return True

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        """
        Get an incident by ID.

        Args:
            incident_id: Incident ID

        Returns:
            Incident or None
        """
        async with self._lock:
            return self._incidents.get(incident_id)

    async def list_incidents(
        self,
        status: Optional[Union[IncidentStatus, str]] = None,
        severity: Optional[Union[IncidentSeverity, str]] = None,
        type: Optional[Union[IncidentType, str]] = None,
        assigned_to: Optional[str] = None,
        assigned_team: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Incident]:
        """
        List incidents with filters.

        Args:
            status: Filter by status
            severity: Filter by severity
            type: Filter by type
            assigned_to: Filter by assignee
            assigned_team: Filter by team
            from_date: Filter from date
            to_date: Filter to date
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of incidents
        """
        async with self._lock:
            incidents = list(self._incidents.values())

            if status:
                if isinstance(status, str):
                    status = IncidentStatus(status)
                incidents = [i for i in incidents if i.status == status]

            if severity:
                if isinstance(severity, str):
                    severity = IncidentSeverity(severity)
                incidents = [i for i in incidents if i.severity == severity]

            if type:
                if isinstance(type, str):
                    type = IncidentType(type)
                incidents = [i for i in incidents if i.type == type]

            if assigned_to:
                incidents = [i for i in incidents if i.assigned_to == assigned_to]

            if assigned_team:
                incidents = [i for i in incidents if i.assigned_team == assigned_team]

            if from_date:
                incidents = [i for i in incidents if i.detected_at >= from_date]

            if to_date:
                incidents = [i for i in incidents if i.detected_at <= to_date]

            # Sort by detection time
            incidents.sort(key=lambda x: x.detected_at, reverse=True)

            return incidents[offset:offset + limit]

    async def get_incident_stats(self) -> Dict[str, Any]:
        """
        Get incident statistics.

        Returns:
            Incident statistics
        """
        async with self._lock:
            total = len(self._incidents)

            by_status = {}
            by_severity = {}
            by_type = {}

            for incident in self._incidents.values():
                by_status[incident.status.value] = by_status.get(incident.status.value, 0) + 1
                by_severity[incident.severity.value] = by_severity.get(incident.severity.value, 0) + 1
                by_type[incident.type.value] = by_type.get(incident.type.value, 0) + 1

            # Calculate average resolution time
            resolved_incidents = [
                i for i in self._incidents.values()
                if i.resolved_at and i.detected_at
            ]

            if resolved_incidents:
                avg_resolution_time = np.mean([
                    (i.resolved_at - i.detected_at).total_seconds() / 60
                    for i in resolved_incidents
                ])
            else:
                avg_resolution_time = 0

            # SLA breach rate
            total_resolved = len(resolved_incidents)
            sla_breaches = sum(1 for i in resolved_incidents if i.sla_breached)

            return {
                "total_incidents": total,
                "active_incidents": by_status.get(IncidentStatus.DETECTED.value, 0) +
                                   by_status.get(IncidentStatus.INVESTIGATING.value, 0) +
                                   by_status.get(IncidentStatus.IDENTIFIED.value, 0) +
                                   by_status.get(IncidentStatus.MITIGATING.value, 0),
                "by_status": by_status,
                "by_severity": by_severity,
                "by_type": by_type,
                "avg_resolution_time_minutes": avg_resolution_time,
                "sla_breach_rate": sla_breaches / total_resolved if total_resolved > 0 else 0,
                "sla_breaches": sla_breaches,
            }

    async def _check_sla_breaches(self):
        """Check for SLA breaches."""
        async with self._lock:
            for incident in self._incidents.values():
                if incident.status in [IncidentStatus.DETECTED, IncidentStatus.INVESTIGATING]:
                    sla_config = self._sla_configs.get(incident.severity)
                    if not sla_config:
                        continue

                    elapsed = (datetime.utcnow() - incident.detected_at).total_seconds() / 60

                    # Check response SLA
                    if elapsed > sla_config.response_time_minutes:
                        if not incident.sla_breached:
                            incident.sla_breached = True
                            SLA_BREACH_COUNTER.labels(
                                severity=incident.severity.value
                            ).inc()
                            await self._notify_sla_breach(incident, "response")
                            logger.warning(f"SLA breach: Response time exceeded for {incident.id}")

                    # Check resolution SLA
                    if elapsed > sla_config.resolution_time_minutes:
                        incident.sla_breached = True
                        SLA_BREACH_COUNTER.labels(
                            severity=incident.severity.value
                        ).inc()
                        await self._notify_sla_breach(incident, "resolution")
                        logger.warning(f"SLA breach: Resolution time exceeded for {incident.id}")

    async def _escalate_incidents(self):
        """Escalate incidents as needed."""
        if not self.escalation_enabled:
            return

        async with self._lock:
            for incident in self._incidents.values():
                if incident.status in [IncidentStatus.DETECTED, IncidentStatus.INVESTIGATING]:
                    sla_config = self._sla_configs.get(incident.severity)
                    if not sla_config:
                        continue

                    elapsed = (datetime.utcnow() - incident.detected_at).total_seconds() / 60

                    # Escalate if response time exceeded
                    if elapsed > sla_config.response_time_minutes:
                        incident.escalation_count += 1
                        await self._notify_escalation(incident)
                        logger.info(f"Incident {incident.id} escalated (count: {incident.escalation_count})")

    async def _auto_close_old_incidents(self):
        """Auto-close old resolved incidents."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.max_incident_age_days)

        async with self._lock:
            for incident in list(self._incidents.values()):
                if incident.status in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]:
                    if incident.resolved_at and incident.resolved_at < cutoff_date:
                        if incident.status == IncidentStatus.RESOLVED:
                            await self.close_incident(incident.id, "system")
                        else:
                            # Archive old closed incidents
                            del self._incidents[incident.id]
                            logger.info(f"Archived old incident {incident.id}")

    async def _generate_incident_report(self, incident_id: str, created_by: str):
        """
        Generate post-mortem report for an incident.

        Args:
            incident_id: Incident ID
            created_by: User creating the report
        """
        incident = await self.get_incident(incident_id)

        if not incident:
            return

        # Calculate duration
        duration_minutes = 0
        if incident.resolved_at and incident.detected_at:
            duration_minutes = (incident.resolved_at - incident.detected_at).total_seconds() / 60

        # Generate report
        report = IncidentReport(
            incident_id=incident.id,
            title=incident.title,
            severity=incident.severity,
            type=incident.type,
            duration_minutes=duration_minutes,
            root_cause=incident.root_cause or "Under investigation",
            timeline=incident.timeline,
            impact={
                "affected_components": incident.affected_components,
                "downtime_minutes": duration_minutes,
                "user_impact": "Limited" if duration_minutes < 10 else "Moderate",
            },
            action_items=[],
            lessons_learned=[],
            recommendations=[],
            created_at=datetime.utcnow(),
            created_by=created_by,
        )

        # Store report
        self._reports[incident_id] = report
        await self._save_report(report)

        logger.info(f"Incident report generated for {incident_id}")

    async def _save_incident(self, incident: Incident):
        """Save incident to storage."""
        try:
            file_path = self.storage_path / f"{incident.id}.json"
            with open(file_path, "w") as f:
                json.dump(incident.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving incident {incident.id}: {e}")

    async def _save_report(self, report: IncidentReport):
        """Save incident report to storage."""
        try:
            report_path = self.storage_path / "reports"
            report_path.mkdir(parents=True, exist_ok=True)
            file_path = report_path / f"{report.incident_id}.json"
            with open(file_path, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving report {report.incident_id}: {e}")

    async def _notify_incident_created(self, incident: Incident):
        """Send notification for new incident."""
        for handler in self._notification_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(incident, "created")
                else:
                    handler(incident, "created")
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")

    async def _notify_incident_updated(self, incident: Incident, old_status: IncidentStatus):
        """Send notification for incident update."""
        for handler in self._notification_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(incident, "updated", {"old_status": old_status.value})
                else:
                    handler(incident, "updated", {"old_status": old_status.value})
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")

    async def _notify_sla_breach(self, incident: Incident, breach_type: str):
        """Send notification for SLA breach."""
        for handler in self._notification_handlers:
            try:
                message = {
                    "incident": incident.to_dict(),
                    "breach_type": breach_type,
                    "severity": incident.severity.value,
                }
                if asyncio.iscoroutinefunction(handler):
                    await handler(incident, "sla_breach", message)
                else:
                    handler(incident, "sla_breach", message)
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")

    async def _notify_escalation(self, incident: Incident):
        """Send notification for incident escalation."""
        for handler in self._notification_handlers:
            try:
                message = {
                    "incident": incident.to_dict(),
                    "escalation_count": incident.escalation_count,
                }
                if asyncio.iscoroutinefunction(handler):
                    await handler(incident, "escalated", message)
                else:
                    handler(incident, "escalated", message)
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")

    def register_notification_handler(self, handler: Callable):
        """
        Register a notification handler.

        Args:
            handler: Callback function for notifications
        """
        self._notification_handlers.append(handler)
        logger.info("Registered notification handler")

    async def get_report(self, incident_id: str) -> Optional[IncidentReport]:
        """
        Get incident report.

        Args:
            incident_id: Incident ID

        Returns:
            Incident report or None
        """
        return self._reports.get(incident_id)

    async def get_reports(self) -> List[IncidentReport]:
        """
        Get all incident reports.

        Returns:
            List of incident reports
        """
        return list(self._reports.values())

    async def shutdown(self):
        """Shutdown the incident manager."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("IncidentManager shut down")


# Export singleton
incident_manager = IncidentManager()

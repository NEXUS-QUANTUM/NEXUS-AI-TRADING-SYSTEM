# trading/bots/arbitrage_bot/monitoring/incident_manager.py
# NEXUS AI TRADING SYSTEM - INCIDENT MANAGER
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides comprehensive incident management for the arbitrage bot,
# including incident detection, tracking, resolution, and post-mortem analysis.
# ====================================================================================

"""
NEXUS Arbitrage Bot Incident Manager

This module provides comprehensive incident management for:
- Incident detection and classification
- Incident tracking and status management
- Root cause analysis and investigation
- Resolution and recovery procedures
- Post-mortem analysis and reporting
- Incident history and analytics
- Integration with alerting systems
- SLA tracking and compliance
"""

import asyncio
import logging
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque

# NEXUS internal imports
from trading.bots.arbitrage_bot.models.alert import Alert, AlertSeverity, AlertCategory, AlertStatus
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.core.retry_handler import RetryHandler

logger = logging.getLogger("nexus.arbitrage.incident_manager")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    SEV1 = "sev1"  # Critical - Service down
    SEV2 = "sev2"  # High - Major impact
    SEV3 = "sev3"  # Medium - Moderate impact
    SEV4 = "sev4"  # Low - Minor impact
    SEV5 = "sev5"  # Informational - No impact


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
    EXCHANGE = "exchange"
    TRADING = "trading"
    SYSTEM = "system"
    NETWORK = "network"
    SECURITY = "security"
    DATA = "data"
    PERFORMANCE = "performance"
    DEPLOYMENT = "deployment"
    THIRD_PARTY = "third_party"
    MARKET = "market"


class IncidentPriority(str, Enum):
    """Incident priority levels."""
    P0 = "p0"  # Immediate action
    P1 = "p1"  # High priority
    P2 = "p2"  # Medium priority
    P3 = "p3"  # Low priority
    P4 = "p4"  # Informational


class ResolutionStatus(str, Enum):
    """Resolution status."""
    FIXED = "fixed"
    WORKAROUND = "workaround"
    PARTIAL = "partial"
    NO_FIX = "no_fix"
    PENDING = "pending"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class Incident:
    """
    Incident data model.
    """
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    category: IncidentCategory
    priority: IncidentPriority
    status: IncidentStatus
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    detected_at: Optional[datetime]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    escalated_at: Optional[datetime]
    
    # Related items
    alert_ids: List[str]
    trade_ids: List[str]
    opportunity_ids: List[str]
    exchange_names: List[str]
    
    # Assignment
    assigned_to: str
    assigned_team: str
    
    # Updates
    updates: List[Dict[str, Any]]
    
    # Resolution
    resolution_status: Optional[ResolutionStatus]
    resolution_description: str
    root_cause: str
    corrective_actions: List[str]
    preventive_actions: List[str]
    
    # Impact
    impact_description: str
    impacted_services: List[str]
    impacted_users: int
    financial_impact: float
    
    # SLA
    sla_breach: bool
    sla_target_minutes: int
    response_time: float  # seconds
    resolution_time: float  # seconds
    
    # Metadata
    environment: str
    version: str
    tags: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Incident":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class IncidentTimeline:
    """
    Incident timeline entry.
    """
    incident_id: str
    timestamp: datetime
    event_type: str  # created, updated, escalated, resolved, closed, comment
    user: str
    message: str
    details: Dict[str, Any]


@dataclass
class IncidentMetrics:
    """
    Incident metrics.
    """
    total_incidents: int
    open_incidents: int
    resolved_incidents: int
    closed_incidents: int
    by_severity: Dict[str, int]
    by_category: Dict[str, int]
    by_status: Dict[str, int]
    avg_resolution_time: float
    avg_response_time: float
    sla_breach_rate: float
    period_start: datetime
    period_end: datetime


@dataclass
class IncidentReport:
    """
    Incident report.
    """
    report_id: str
    incident_id: str
    title: str
    executive_summary: str
    timeline: List[Dict[str, Any]]
    root_cause_analysis: str
    impact_analysis: str
    resolution_summary: str
    corrective_actions: List[str]
    preventive_actions: List[str]
    lessons_learned: List[str]
    recommendations: List[str]
    created_at: datetime
    updated_at: datetime
    author: str


# ====================================================================================
# INCIDENT MANAGER
# ====================================================================================

class IncidentManager:
    """
    Comprehensive incident management system.
    
    Features:
    - Incident creation and tracking
    - Severity and priority classification
    - SLA tracking and breach detection
    - Root cause analysis
    - Resolution management
    - Post-mortem reporting
    - Incident analytics
    - Integration with alerts
    - Escalation management
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the incident manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Incident storage
        self._incidents: Dict[str, Incident] = {}
        self._timeline: Dict[str, List[IncidentTimeline]] = defaultdict(list)
        self._incident_history: deque = deque(maxlen=10000)
        
        # SLA defaults
        self._sla_targets = {
            IncidentSeverity.SEV1: 15,   # 15 minutes
            IncidentSeverity.SEV2: 30,   # 30 minutes
            IncidentSeverity.SEV3: 60,   # 60 minutes
            IncidentSeverity.SEV4: 120,  # 120 minutes
            IncidentSeverity.SEV5: 240,  # 240 minutes
        }
        
        # Escalation rules
        self._escalation_rules: Dict[str, Dict[str, Any]] = {}
        
        # Metrics
        self._metrics = MetricsCollector(
            name="nexus_incident_manager",
            labels={"service": "arbitrage_bot"}
        )
        self._setup_metrics()
        
        # State
        self._running = False
        self._initialized = False
        self._background_tasks: Set[asyncio.Task] = set()
        self._start_time = datetime.utcnow()
        
        logger.info("IncidentManager initialized (version=3.0.0)")
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics.register_counter("incidents_total", "Total incidents")
        self._metrics.register_gauge("incidents_open", "Open incidents")
        self._metrics.register_gauge("incidents_by_severity", "Incidents by severity")
        self._metrics.register_histogram("incident_resolution_time", "Incident resolution time in seconds")
        self._metrics.register_histogram("incident_response_time", "Incident response time in seconds")
        self._metrics.register_counter("sla_breaches", "SLA breaches")
        
    def set_sla_target(self, severity: IncidentSeverity, minutes: int) -> None:
        """
        Set SLA target for a severity level.
        
        Args:
            severity: Incident severity
            minutes: SLA target in minutes
        """
        self._sla_targets[severity] = minutes
        logger.info(f"SLA target for {severity.value}: {minutes} minutes")
        
    def add_escalation_rule(
        self,
        name: str,
        severity: IncidentSeverity,
        after_minutes: int,
        escalate_to: str,
        notify: List[str]
    ) -> None:
        """
        Add an escalation rule.
        
        Args:
            name: Rule name
            severity: Incident severity
            after_minutes: Minutes after incident creation
            escalate_to: User/team to escalate to
            notify: List of users/teams to notify
        """
        self._escalation_rules[name] = {
            "severity": severity,
            "after_minutes": after_minutes,
            "escalate_to": escalate_to,
            "notify": notify
        }
        logger.info(f"Added escalation rule: {name}")
        
    async def initialize(self) -> None:
        """Initialize the incident manager."""
        if self._initialized:
            return
            
        self._initialized = True
        self._running = True
        
        # Start background tasks
        await self._start_background_tasks()
        
        logger.info("IncidentManager initialized")
        
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        # SLA monitoring
        task = asyncio.create_task(self._sla_monitor_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Metrics update
        task = asyncio.create_task(self._metrics_update_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
    async def _sla_monitor_loop(self) -> None:
        """Monitor SLA compliance."""
        while self._running:
            try:
                await asyncio.sleep(30)
                await self._check_sla_breaches()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SLA monitor error: {e}")
                
    async def _metrics_update_loop(self) -> None:
        """Update metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(60)
                
                # Update metrics
                open_incidents = sum(1 for i in self._incidents.values() 
                                    if i.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED])
                self._metrics.set_gauge("incidents_open", open_incidents)
                
                # By severity
                for sev in IncidentSeverity:
                    count = sum(1 for i in self._incidents.values() if i.severity == sev)
                    self._metrics.set_gauge(
                        f"incidents_by_severity_{sev.value}",
                        count
                    )
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics update error: {e}")
                
    async def _check_sla_breaches(self) -> None:
        """Check for SLA breaches."""
        now = datetime.utcnow()
        
        for incident in self._incidents.values():
            if incident.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]:
                elapsed = (now - incident.created_at).total_seconds() / 60
                sla_target = self._sla_targets.get(incident.severity, 60)
                
                if elapsed > sla_target and not incident.sla_breach:
                    incident.sla_breach = True
                    incident.updated_at = now
                    self._metrics.increment_counter("sla_breaches")
                    logger.warning(
                        f"SLA breach for incident {incident.incident_id}: "
                        f"{elapsed:.1f} minutes > {sla_target} minutes"
                    )
                    
                    # Trigger escalation
                    await self._check_escalation(incident)
                    
    async def _check_escalation(self, incident: Incident) -> None:
        """
        Check if incident needs escalation.
        
        Args:
            incident: Incident to check
        """
        for rule_name, rule in self._escalation_rules.items():
            if incident.severity == rule["severity"]:
                elapsed = (datetime.utcnow() - incident.created_at).total_seconds() / 60
                if elapsed > rule["after_minutes"]:
                    if incident.status != IncidentStatus.ESCALATED:
                        incident.status = IncidentStatus.ESCALATED
                        incident.escalated_at = datetime.utcnow()
                        incident.assigned_to = rule["escalate_to"]
                        
                        # Add timeline entry
                        await self._add_timeline_entry(
                            incident.incident_id,
                            "escalated",
                            "system",
                            f"Escalated to {rule['escalate_to']}",
                            {"rule": rule_name, "after_minutes": rule["after_minutes"]}
                        )
                        
                        logger.info(
                            f"Incident {incident.incident_id} escalated to {rule['escalate_to']}"
                        )
                        break
                        
    # ====================================================================
    # INCIDENT MANAGEMENT
    # ====================================================================
    
    async def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity = IncidentSeverity.SEV3,
        category: IncidentCategory = IncidentCategory.SYSTEM,
        alert_ids: Optional[List[str]] = None,
        **kwargs
    ) -> Incident:
        """
        Create a new incident.
        
        Args:
            title: Incident title
            description: Incident description
            severity: Incident severity
            category: Incident category
            alert_ids: Related alert IDs
            **kwargs: Additional fields
            
        Returns:
            Created incident
        """
        incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        # Determine priority
        priority = self._get_priority(severity)
        
        incident = Incident(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            priority=priority,
            status=IncidentStatus.INVESTIGATING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            detected_at=datetime.utcnow(),
            resolved_at=None,
            closed_at=None,
            escalated_at=None,
            alert_ids=alert_ids or [],
            trade_ids=[],
            opportunity_ids=[],
            exchange_names=[],
            assigned_to="",
            assigned_team="",
            updates=[],
            resolution_status=None,
            resolution_description="",
            root_cause="",
            corrective_actions=[],
            preventive_actions=[],
            impact_description="",
            impacted_services=[],
            impacted_users=0,
            financial_impact=0.0,
            sla_breach=False,
            sla_target_minutes=self._sla_targets.get(severity, 60),
            response_time=0.0,
            resolution_time=0.0,
            environment=kwargs.get("environment", "production"),
            version=kwargs.get("version", "3.0.0"),
            tags=kwargs.get("tags", []),
            metadata=kwargs.get("metadata", {})
        )
        
        # Store incident
        self._incidents[incident_id] = incident
        self._incident_history.append(incident)
        
        # Add timeline entry
        await self._add_timeline_entry(
            incident_id,
            "created",
            "system",
            f"Incident created: {title}",
            {"severity": severity.value, "category": category.value}
        )
        
        # Update metrics
        self._metrics.increment_counter("incidents_total")
        
        logger.info(f"Incident created: {incident_id} - {title}")
        return incident
        
    async def update_incident(
        self,
        incident_id: str,
        status: Optional[IncidentStatus] = None,
        assigned_to: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> Optional[Incident]:
        """
        Update an incident.
        
        Args:
            incident_id: Incident ID
            status: New status
            assigned_to: User assigned
            description: New description
            **kwargs: Additional fields to update
            
        Returns:
            Updated incident or None if not found
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            logger.warning(f"Incident not found: {incident_id}")
            return None
            
        old_status = incident.status
        
        if status:
            incident.status = status
            
            if status == IncidentStatus.RESOLVED:
                incident.resolved_at = datetime.utcnow()
                incident.resolution_time = (
                    (incident.resolved_at - incident.created_at).total_seconds()
                )
                self._metrics.record_histogram(
                    "incident_resolution_time",
                    incident.resolution_time
                )
            elif status == IncidentStatus.CLOSED:
                incident.closed_at = datetime.utcnow()
                
        if assigned_to:
            incident.assigned_to = assigned_to
            
        if description:
            incident.description = description
            
        # Update other fields
        for key, value in kwargs.items():
            if hasattr(incident, key):
                setattr(incident, key, value)
                
        incident.updated_at = datetime.utcnow()
        
        # Add timeline entry
        await self._add_timeline_entry(
            incident_id,
            "updated",
            "system",
            f"Status changed from {old_status.value} to {incident.status.value}",
            {"old_status": old_status.value, "new_status": incident.status.value}
        )
        
        return incident
        
    async def resolve_incident(
        self,
        incident_id: str,
        resolution_description: str,
        root_cause: str = "",
        corrective_actions: Optional[List[str]] = None,
        preventive_actions: Optional[List[str]] = None
    ) -> Optional[Incident]:
        """
        Resolve an incident.
        
        Args:
            incident_id: Incident ID
            resolution_description: Description of resolution
            root_cause: Root cause analysis
            corrective_actions: Actions taken to correct
            preventive_actions: Actions to prevent recurrence
            
        Returns:
            Resolved incident or None
        """
        incident = await self.update_incident(
            incident_id=incident_id,
            status=IncidentStatus.RESOLVED,
            resolution_description=resolution_description,
            root_cause=root_cause,
            corrective_actions=corrective_actions or [],
            preventive_actions=preventive_actions or []
        )
        
        if incident:
            # Add resolution timeline entry
            await self._add_timeline_entry(
                incident_id,
                "resolved",
                "system",
                f"Incident resolved: {resolution_description}",
                {"root_cause": root_cause}
            )
            
            logger.info(f"Incident resolved: {incident_id}")
            
        return incident
        
    async def close_incident(
        self,
        incident_id: str,
        final_notes: str = ""
    ) -> Optional[Incident]:
        """
        Close an incident.
        
        Args:
            incident_id: Incident ID
            final_notes: Final notes
            
        Returns:
            Closed incident or None
        """
        incident = await self.update_incident(
            incident_id=incident_id,
            status=IncidentStatus.CLOSED
        )
        
        if incident:
            await self._add_timeline_entry(
                incident_id,
                "closed",
                "system",
                f"Incident closed: {final_notes or 'No additional notes'}",
                {"final_notes": final_notes}
            )
            
            logger.info(f"Incident closed: {incident_id}")
            
        return incident
        
    async def add_timeline_entry(
        self,
        incident_id: str,
        event_type: str,
        user: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add timeline entry to incident.
        
        Args:
            incident_id: Incident ID
            event_type: Type of event
            user: User performing action
            message: Event message
            details: Additional details
        """
        await self._add_timeline_entry(incident_id, event_type, user, message, details)
        
    async def _add_timeline_entry(
        self,
        incident_id: str,
        event_type: str,
        user: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Internal timeline entry addition."""
        entry = IncidentTimeline(
            incident_id=incident_id,
            timestamp=datetime.utcnow(),
            event_type=event_type,
            user=user,
            message=message,
            details=details or {}
        )
        
        self._timeline[incident_id].append(entry)
        
        # Update incident updates
        incident = self._incidents.get(incident_id)
        if incident:
            incident.updates.append({
                "timestamp": entry.timestamp.isoformat(),
                "type": event_type,
                "user": user,
                "message": message,
                "details": details
            })
            
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident by ID."""
        return self._incidents.get(incident_id)
        
    def get_timeline(self, incident_id: str) -> List[IncidentTimeline]:
        """Get incident timeline."""
        return self._timeline.get(incident_id, [])
        
    def get_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        category: Optional[IncidentCategory] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Incident]:
        """
        Get incidents with filters.
        
        Args:
            status: Filter by status
            severity: Filter by severity
            category: Filter by category
            limit: Maximum number of incidents
            offset: Offset for pagination
            
        Returns:
            List of incidents
        """
        incidents = list(self._incidents.values())
        
        if status:
            incidents = [i for i in incidents if i.status == status]
        if severity:
            incidents = [i for i in incidents if i.severity == severity]
        if category:
            incidents = [i for i in incidents if i.category == category]
            
        # Sort by created_at descending
        incidents.sort(key=lambda i: i.created_at, reverse=True)
        
        return incidents[offset:offset + limit]
        
    def get_metrics(self, period_days: int = 7) -> IncidentMetrics:
        """
        Get incident metrics.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Incident metrics
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        incidents = [i for i in self._incident_history if i.created_at > cutoff]
        
        by_severity = defaultdict(int)
        by_category = defaultdict(int)
        by_status = defaultdict(int)
        
        resolution_times = []
        response_times = []
        sla_breaches = 0
        
        for incident in incidents:
            by_severity[incident.severity.value] += 1
            by_category[incident.category.value] += 1
            by_status[incident.status.value] += 1
            
            if incident.resolution_time > 0:
                resolution_times.append(incident.resolution_time)
            if incident.response_time > 0:
                response_times.append(incident.response_time)
            if incident.sla_breach:
                sla_breaches += 1
                
        return IncidentMetrics(
            total_incidents=len(incidents),
            open_incidents=sum(1 for i in incidents 
                              if i.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]),
            resolved_incidents=sum(1 for i in incidents if i.status == IncidentStatus.RESOLVED),
            closed_incidents=sum(1 for i in incidents if i.status == IncidentStatus.CLOSED),
            by_severity=dict(by_severity),
            by_category=dict(by_category),
            by_status=dict(by_status),
            avg_resolution_time=sum(resolution_times) / len(resolution_times) if resolution_times else 0,
            avg_response_time=sum(response_times) / len(response_times) if response_times else 0,
            sla_breach_rate=sla_breaches / len(incidents) if incidents else 0,
            period_start=cutoff,
            period_end=datetime.utcnow()
        )
        
    def _get_priority(self, severity: IncidentSeverity) -> IncidentPriority:
        """Get priority from severity."""
        mapping = {
            IncidentSeverity.SEV1: IncidentPriority.P0,
            IncidentSeverity.SEV2: IncidentPriority.P1,
            IncidentSeverity.SEV3: IncidentPriority.P2,
            IncidentSeverity.SEV4: IncidentPriority.P3,
            IncidentSeverity.SEV5: IncidentPriority.P4,
        }
        return mapping.get(severity, IncidentPriority.P2)
        
    async def generate_report(self, incident_id: str) -> Optional[IncidentReport]:
        """
        Generate incident report.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            Incident report or None
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
            
        timeline = self._timeline.get(incident_id, [])
        
        report = IncidentReport(
            report_id=f"RPT-{incident_id}",
            incident_id=incident_id,
            title=incident.title,
            executive_summary=self._generate_executive_summary(incident),
            timeline=[{
                "timestamp": entry.timestamp.isoformat(),
                "type": entry.event_type,
                "user": entry.user,
                "message": entry.message
            } for entry in timeline],
            root_cause_analysis=incident.root_cause,
            impact_analysis=incident.impact_description,
            resolution_summary=incident.resolution_description,
            corrective_actions=incident.corrective_actions,
            preventive_actions=incident.preventive_actions,
            lessons_learned=self._generate_lessons_learned(incident),
            recommendations=self._generate_recommendations(incident),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            author="system"
        )
        
        return report
        
    def _generate_executive_summary(self, incident: Incident) -> str:
        """Generate executive summary."""
        lines = [
            f"Incident: {incident.title}",
            f"Severity: {incident.severity.value.upper()}",
            f"Category: {incident.category.value}",
            f"Status: {incident.status.value}",
            f"Duration: {self._format_duration(incident.resolution_time)}",
            f"Impact: {incident.impact_description or 'No impact description provided'}"
        ]
        return "\n".join(lines)
        
    def _generate_lessons_learned(self, incident: Incident) -> List[str]:
        """Generate lessons learned."""
        lessons = []
        if incident.root_cause:
            lessons.append(f"Root cause identified: {incident.root_cause}")
        if incident.corrective_actions:
            lessons.append(f"Corrective actions taken: {', '.join(incident.corrective_actions)}")
        if incident.preventive_actions:
            lessons.append(f"Preventive actions planned: {', '.join(incident.preventive_actions)}")
        return lessons
        
    def _generate_recommendations(self, incident: Incident) -> List[str]:
        """Generate recommendations."""
        recommendations = []
        
        if incident.sla_breach:
            recommendations.append("Review SLA targets and escalation procedures")
            
        if incident.resolution_time > self._sla_targets.get(incident.severity, 60) * 60:
            recommendations.append("Investigate causes of delayed resolution")
            
        if not incident.root_cause:
            recommendations.append("Perform thorough root cause analysis")
            
        if not incident.preventive_actions:
            recommendations.append("Define preventive actions to avoid recurrence")
            
        return recommendations
        
    def _format_duration(self, seconds: float) -> str:
        """Format duration."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
            
    async def close(self) -> None:
        """Close the incident manager."""
        self._running = False
        self._initialized = False
        
        # Cancel background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        logger.info("IncidentManager closed")


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_incident_manager: Optional[IncidentManager] = None


def get_incident_manager() -> IncidentManager:
    """
    Get the global incident manager instance.
    
    Returns:
        IncidentManager instance
    """
    global _global_incident_manager
    if _global_incident_manager is None:
        _global_incident_manager = IncidentManager()
    return _global_incident_manager


def reset_incident_manager() -> None:
    """Reset the global incident manager instance."""
    global _global_incident_manager
    if _global_incident_manager:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_incident_manager.close())
            else:
                asyncio.run(_global_incident_manager.close())
        except Exception:
            pass
    _global_incident_manager = None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'IncidentSeverity',
    'IncidentStatus',
    'IncidentCategory',
    'IncidentPriority',
    'ResolutionStatus',
    
    # Data Models
    'Incident',
    'IncidentTimeline',
    'IncidentMetrics',
    'IncidentReport',
    
    # Main Class
    'IncidentManager',
    'get_incident_manager',
    'reset_incident_manager',
]

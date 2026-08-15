"""
Swing Bot Incident Manager
============================

This module provides incident management capabilities for the Swing Bot trading system.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from .notification_service import NotificationService
from .metric_collector import MetricCollector
from .log_analyzer import LogAnalyzer


class IncidentSeverity(Enum):
    """Incident severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IncidentStatus(Enum):
    """Incident status states."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class IncidentType(Enum):
    """Incident types."""
    SYSTEM = "system"
    TRADING = "trading"
    RISK = "risk"
    MARKET = "market"
    EXECUTION = "execution"
    DATA = "data"
    NETWORK = "network"
    SECURITY = "security"
    OPERATIONAL = "operational"


@dataclass
class Incident:
    """Incident data structure."""
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    type: IncidentType
    created_at: datetime
    updated_at: datetime
    assigned_to: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    related_incidents: List[str] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None


class IncidentManager:
    """
    Manage incidents and alerts.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the incident manager.
        
        Args:
            config: Configuration settings
        """
        self.config = config or {}
        self.incidents: Dict[str, Incident] = {}
        self.active_incidents: Set[str] = set()
        self.handlers: Dict[IncidentType, List[Callable]] = {
            incident_type: [] for incident_type in IncidentType
        }
        self.notification_service = NotificationService(self.config.get('notification', {}))
        self.metric_collector = MetricCollector(self.config.get('metrics', {}))
        self.log_analyzer = LogAnalyzer(self.config.get('logs', {}))
        self._lock = None
        
        # Initialize with default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default incident handlers."""
        self.register_handler(IncidentType.SYSTEM, self._handle_system_incident)
        self.register_handler(IncidentType.TRADING, self._handle_trading_incident)
        self.register_handler(IncidentType.RISK, self._handle_risk_incident)
        self.register_handler(IncidentType.EXECUTION, self._handle_execution_incident)
    
    def register_handler(self, incident_type: IncidentType, handler: Callable) -> None:
        """
        Register an incident handler.
        
        Args:
            incident_type: Type of incident
            handler: Handler function
        """
        if incident_type in self.handlers:
            self.handlers[incident_type].append(handler)
    
    def create_incident(
        self,
        title: str,
        description: str,
        severity: Union[IncidentSeverity, str],
        incident_type: Union[IncidentType, str],
        tags: Optional[List[str]] = None,
        assigned_to: Optional[str] = None
    ) -> Incident:
        """
        Create a new incident.
        
        Args:
            title: Incident title
            description: Incident description
            severity: Severity level
            incident_type: Type of incident
            tags: Additional tags
            assigned_to: Person assigned to the incident
        
        Returns:
            Created incident
        """
        # Convert string to enum if needed
        if isinstance(severity, str):
            severity = IncidentSeverity(severity.lower())
        if isinstance(incident_type, str):
            incident_type = IncidentType(incident_type.lower())
        
        incident = Incident(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            severity=severity,
            status=IncidentStatus.NEW,
            type=incident_type,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            assigned_to=assigned_to,
            tags=tags or []
        )
        
        self.incidents[incident.id] = incident
        self.active_incidents.add(incident.id)
        
        # Call handlers
        for handler in self.handlers.get(incident_type, []):
            try:
                handler(incident)
            except Exception as e:
                logging.error(f"Incident handler error: {e}")
        
        # Send notification
        self._send_incident_notification(incident)
        
        # Record metric
        self.metric_collector.record('incidents', 1, {
            'severity': severity.value,
            'type': incident_type.value
        }, 'count')
        
        return incident
    
    def update_incident(
        self,
        incident_id: str,
        status: Optional[Union[IncidentStatus, str]] = None,
        assigned_to: Optional[str] = None,
        resolution: Optional[str] = None,
        comments: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Incident]:
        """
        Update an incident.
        
        Args:
            incident_id: Incident ID
            status: New status
            assigned_to: New assignee
            resolution: Resolution details
            comments: Additional comments
        
        Returns:
            Updated incident or None
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return None
        
        if status:
            if isinstance(status, str):
                status = IncidentStatus(status.lower())
            incident.status = status
            
            if status == IncidentStatus.RESOLVED:
                incident.resolved_at = datetime.now()
                self.active_incidents.discard(incident_id)
        
        if assigned_to:
            incident.assigned_to = assigned_to
        
        if resolution:
            incident.resolution = resolution
        
        if comments:
            incident.comments.extend(comments)
        
        incident.updated_at = datetime.now()
        
        # Send update notification
        self._send_incident_update_notification(incident)
        
        return incident
    
    def close_incident(self, incident_id: str) -> bool:
        """
        Close an incident.
        
        Args:
            incident_id: Incident ID
        
        Returns:
            True if closed, False otherwise
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        
        incident.status = IncidentStatus.CLOSED
        incident.updated_at = datetime.now()
        self.active_incidents.discard(incident_id)
        
        # Record metric
        self.metric_collector.record('incidents_closed', 1, {
            'severity': incident.severity.value,
            'type': incident.type.value
        }, 'count')
        
        return True
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """
        Get an incident by ID.
        
        Args:
            incident_id: Incident ID
        
        Returns:
            Incident or None
        """
        return self.incidents.get(incident_id)
    
    def get_active_incidents(self) -> List[Incident]:
        """
        Get all active incidents.
        
        Returns:
            List of active incidents
        """
        return [self.incidents[i] for i in self.active_incidents if i in self.incidents]
    
    def get_incidents_by_status(self, status: IncidentStatus) -> List[Incident]:
        """
        Get incidents by status.
        
        Args:
            status: Incident status
        
        Returns:
            List of incidents
        """
        return [i for i in self.incidents.values() if i.status == status]
    
    def get_incidents_by_severity(self, severity: IncidentSeverity) -> List[Incident]:
        """
        Get incidents by severity.
        
        Args:
            severity: Incident severity
        
        Returns:
            List of incidents
        """
        return [i for i in self.incidents.values() if i.severity == severity]
    
    def get_incidents_by_type(self, incident_type: IncidentType) -> List[Incident]:
        """
        Get incidents by type.
        
        Args:
            incident_type: Incident type
        
        Returns:
            List of incidents
        """
        return [i for i in self.incidents.values() if i.type == incident_type]
    
    def get_incidents_by_time_range(
        self,
        start: datetime,
        end: datetime
    ) -> List[Incident]:
        """
        Get incidents within a time range.
        
        Args:
            start: Start time
            end: End time
        
        Returns:
            List of incidents
        """
        return [
            i for i in self.incidents.values()
            if start <= i.created_at <= end
        ]
    
    def search_incidents(self, query: str) -> List[Incident]:
        """
        Search incidents by title or description.
        
        Args:
            query: Search query
        
        Returns:
            List of matching incidents
        """
        query = query.lower()
        return [
            i for i in self.incidents.values()
            if query in i.title.lower() or query in i.description.lower()
        ]
    
    def add_comment(self, incident_id: str, comment: str, author: str) -> Optional[Incident]:
        """
        Add a comment to an incident.
        
        Args:
            incident_id: Incident ID
            comment: Comment text
            author: Comment author
        
        Returns:
            Updated incident or None
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return None
        
        incident.comments.append({
            'author': author,
            'comment': comment,
            'timestamp': datetime.now().isoformat()
        })
        incident.updated_at = datetime.now()
        
        return incident
    
    def link_incidents(self, incident_id: str, related_id: str) -> bool:
        """
        Link two incidents.
        
        Args:
            incident_id: Primary incident ID
            related_id: Related incident ID
        
        Returns:
            True if linked, False otherwise
        """
        incident = self.incidents.get(incident_id)
        related = self.incidents.get(related_id)
        
        if not incident or not related:
            return False
        
        if related_id not in incident.related_incidents:
            incident.related_incidents.append(related_id)
        
        if incident_id not in related.related_incidents:
            related.related_incidents.append(incident_id)
        
        return True
    
    def _send_incident_notification(self, incident: Incident) -> None:
        """Send notification for a new incident."""
        severity_icons = {
            IncidentSeverity.CRITICAL: '🚨',
            IncidentSeverity.HIGH: '⚠️',
            IncidentSeverity.MEDIUM: '📢',
            IncidentSeverity.LOW: 'ℹ️',
            IncidentSeverity.INFO: '📋'
        }
        
        title = f"{severity_icons.get(incident.severity, '📢')} New Incident: {incident.title}"
        message = f"""
**ID:** {incident.id}
**Type:** {incident.type.value.upper()}
**Severity:** {incident.severity.value.upper()}
**Status:** {incident.status.value.upper()}
**Created:** {incident.created_at.strftime('%Y-%m-%d %H:%M:%S')}

**Description:**
{incident.description}

**Tags:** {', '.join(incident.tags) if incident.tags else 'None'}
**Assigned To:** {incident.assigned_to or 'Unassigned'}
        """
        
        priority = 'critical' if incident.severity == IncidentSeverity.CRITICAL else 'high'
        self.notification_service.send_alert(
            alert_type='incident',
            message=message,
            severity=priority,
            data={'incident_id': incident.id}
        )
    
    def _send_incident_update_notification(self, incident: Incident) -> None:
        """Send notification for an incident update."""
        title = f"Incident Update: {incident.title}"
        message = f"""
**ID:** {incident.id}
**Status:** {incident.status.value.upper()}
**Updated:** {incident.updated_at.strftime('%Y-%m-%d %H:%M:%S')}

**Resolution:** {incident.resolution or 'Not yet resolved'}
        """
        
        self.notification_service.send_notification(
            message=message,
            title=title,
            priority='normal'
        )
    
    def _handle_system_incident(self, incident: Incident) -> None:
        """Handle system incidents."""
        # Log system incident
        logging.info(f"System incident: {incident.title}")
        
        # Check if incident is critical
        if incident.severity == IncidentSeverity.CRITICAL:
            # Collect system metrics
            system_metrics = self.metric_collector.get_latest_metrics()
            incident.metrics['system'] = system_metrics
    
    def _handle_trading_incident(self, incident: Incident) -> None:
        """Handle trading incidents."""
        logging.info(f"Trading incident: {incident.title}")
        
        # Collect trading metrics
        trading_metrics = self.metric_collector.get_latest_metrics()
        incident.metrics['trading'] = trading_metrics
    
    def _handle_risk_incident(self, incident: Incident) -> None:
        """Handle risk incidents."""
        logging.info(f"Risk incident: {incident.title}")
        
        # Log risk metrics
        risk_metrics = self.metric_collector.get_latest_metrics()
        incident.metrics['risk'] = risk_metrics
    
    def _handle_execution_incident(self, incident: Incident) -> None:
        """Handle execution incidents."""
        logging.info(f"Execution incident: {incident.title}")
        
        # Collect execution metrics
        execution_metrics = self.metric_collector.get_latest_metrics()
        incident.metrics['execution'] = execution_metrics
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate an incident report.
        
        Returns:
            Incident report
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'total_incidents': len(self.incidents),
            'active_incidents': len(self.active_incidents),
            'incidents_by_severity': {
                severity.value: len(self.get_incidents_by_severity(severity))
                for severity in IncidentSeverity
            },
            'incidents_by_status': {
                status.value: len(self.get_incidents_by_status(status))
                for status in IncidentStatus
            },
            'incidents_by_type': {
                incident_type.value: len(self.get_incidents_by_type(incident_type))
                for incident_type in IncidentType
            },
            'recent_incidents': [
                {
                    'id': i.id,
                    'title': i.title,
                    'severity': i.severity.value,
                    'status': i.status.value,
                    'type': i.type.value,
                    'created_at': i.created_at.isoformat()
                }
                for i in sorted(
                    self.incidents.values(),
                    key=lambda x: x.created_at,
                    reverse=True
                )[:10]
            ]
        }


# Global incident manager instance
_incident_manager: Optional[IncidentManager] = None


def get_incident_manager() -> IncidentManager:
    """Get the global incident manager instance."""
    global _incident_manager
    if _incident_manager is None:
        _incident_manager = IncidentManager()
    return _incident_manager


def create_incident(
    title: str,
    description: str,
    severity: Union[IncidentSeverity, str],
    incident_type: Union[IncidentType, str],
    tags: Optional[List[str]] = None,
    assigned_to: Optional[str] = None
) -> Incident:
    """
    Create a new incident using the global manager.
    
    Args:
        title: Incident title
        description: Incident description
        severity: Severity level
        incident_type: Type of incident
        tags: Additional tags
        assigned_to: Person assigned to the incident
    
    Returns:
        Created incident
    """
    return get_incident_manager().create_incident(
        title, description, severity, incident_type, tags, assigned_to
    )


__all__ = [
    'IncidentSeverity',
    'IncidentStatus',
    'IncidentType',
    'Incident',
    'IncidentManager',
    'get_incident_manager',
    'create_incident'
]

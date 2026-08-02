# trading/bots/hedge_bot/hedge_bot_data_reported.py

import asyncio
import logging
import time
import json
import hashlib
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class ReportSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class ReportCategory(str, Enum):
    SYSTEM = "system"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TRADING = "trading"
    RISK = "risk"
    DATA = "data"
    NETWORK = "network"
    DATABASE = "database"
    API = "api"
    USER = "user"
    COMPLIANCE = "compliance"
    OPERATIONS = "operations"
    MAINTENANCE = "maintenance"
    AUDIT = "audit"
    BUSINESS = "business"


class ReportStatus(str, Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"
    DUPLICATE = "duplicate"
    WONTFIX = "wontfix"


@dataclass
class DataReport:
    id: str
    title: str
    description: str
    category: ReportCategory
    severity: ReportSeverity
    status: ReportStatus
    created_at: float
    updated_at: float
    source: str
    source_id: Optional[str] = None
    assigned_to: Optional[str] = None
    resolved_at: Optional[float] = None
    closed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    related_reports: List[str] = field(default_factory=list)
    solution: Optional[str] = None
    severity_score: float = 0.0


@dataclass
class ReportMetric:
    id: str
    report_id: str
    name: str
    value: float
    unit: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportTemplate:
    id: str
    name: str
    category: ReportCategory
    severity: ReportSeverity
    title_template: str
    description_template: str
    default_tags: List[str] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportStats:
    total: int
    new: int
    assigned: int
    in_progress: int
    resolved: int
    closed: int
    by_severity: Dict[str, int]
    by_category: Dict[str, int]
    avg_resolution_time: float
    total_comments: int


class DataReportManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._reports: Dict[str, DataReport] = {}
        self._metrics: Dict[str, List[ReportMetric]] = defaultdict(list)
        self._templates: Dict[str, ReportTemplate] = {}
        self._stats: Dict[str, ReportStats] = {}
        self._handlers: Dict[ReportCategory, List[Callable]] = defaultdict(list)
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        self._initialize_default_templates()

    def _initialize_default_templates(self) -> None:
        templates = [
            ReportTemplate(
                id="system_error",
                name="System Error Report",
                category=ReportCategory.SYSTEM,
                severity=ReportSeverity.ERROR,
                title_template="System Error: {error_type}",
                description_template="A system error occurred:\n{error_message}\n\nStack trace:\n{stack_trace}",
                default_tags=["system", "error"],
                required_fields=["error_type", "error_message", "stack_trace"]
            ),
            ReportTemplate(
                id="performance_issue",
                name="Performance Issue Report",
                category=ReportCategory.PERFORMANCE,
                severity=ReportSeverity.WARNING,
                title_template="Performance Issue: {metric}",
                description_template="Performance issue detected:\nMetric: {metric}\nValue: {value}\nThreshold: {threshold}",
                default_tags=["performance", "alert"],
                required_fields=["metric", "value", "threshold"]
            ),
            ReportTemplate(
                id="security_breach",
                name="Security Breach Report",
                category=ReportCategory.SECURITY,
                severity=ReportSeverity.CRITICAL,
                title_template="Security Breach: {type}",
                description_template="Security breach detected:\nType: {type}\nSource: {source}\nDetails: {details}",
                default_tags=["security", "critical"],
                required_fields=["type", "source", "details"]
            ),
            ReportTemplate(
                id="trading_anomaly",
                name="Trading Anomaly Report",
                category=ReportCategory.TRADING,
                severity=ReportSeverity.ERROR,
                title_template="Trading Anomaly: {asset}",
                description_template="Trading anomaly detected:\nAsset: {asset}\nAnomaly Type: {anomaly_type}\nDetails: {details}",
                default_tags=["trading", "anomaly"],
                required_fields=["asset", "anomaly_type", "details"]
            ),
            ReportTemplate(
                id="risk_alert",
                name="Risk Alert Report",
                category=ReportCategory.RISK,
                severity=ReportSeverity.WARNING,
                title_template="Risk Alert: {risk_type}",
                description_template="Risk alert triggered:\nRisk Type: {risk_type}\nLevel: {level}\nDetails: {details}",
                default_tags=["risk", "alert"],
                required_fields=["risk_type", "level", "details"]
            )
        ]
        
        for template in templates:
            self._templates[template.id] = template

    def register_handler(self, category: ReportCategory, handler: Callable) -> None:
        self._handlers[category].append(handler)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_report(
        self,
        title: str,
        description: str,
        category: ReportCategory,
        severity: ReportSeverity,
        source: str,
        source_id: Optional[str] = None,
        template_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataReport:
        async with self._lock:
            report_id = hashlib.md5(f"{title}_{time.time()}".encode()).hexdigest()
            
            if template_id and template_id in self._templates:
                template = self._templates[template_id]
                tags = (tags or []) + template.default_tags
            
            report = DataReport(
                id=report_id,
                title=title,
                description=description,
                category=category,
                severity=severity,
                status=ReportStatus.NEW,
                created_at=time.time(),
                updated_at=time.time(),
                source=source,
                source_id=source_id,
                tags=tags or [],
                metadata=metadata or {}
            )
            
            self._reports[report_id] = report
            await self._process_handlers(report)
            await self._notify_observers("report_created", report)
            
            return report

    async def create_from_template(
        self,
        template_id: str,
        parameters: Dict[str, Any],
        source: str,
        source_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DataReport]:
        if template_id not in self._templates:
            return None
        
        template = self._templates[template_id]
        
        for field in template.required_fields:
            if field not in parameters:
                raise ValueError(f"Required field missing: {field}")
        
        title = template.title_template.format(**parameters)
        description = template.description_template.format(**parameters)
        
        return await self.create_report(
            title=title,
            description=description,
            category=template.category,
            severity=template.severity,
            source=source,
            source_id=source_id,
            template_id=template_id,
            tags=tags,
            metadata=metadata
        )

    async def update_report(
        self,
        report_id: str,
        status: Optional[ReportStatus] = None,
        assigned_to: Optional[str] = None,
        solution: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DataReport]:
        async with self._lock:
            if report_id not in self._reports:
                return None
            
            report = self._reports[report_id]
            
            if status:
                old_status = report.status
                report.status = status
                
                if status == ReportStatus.RESOLVED:
                    report.resolved_at = time.time()
                elif status == ReportStatus.CLOSED:
                    report.closed_at = time.time()
                elif status == ReportStatus.REOPENED:
                    report.resolved_at = None
                
                await self._notify_observers("status_changed", report, old_status)
            
            if assigned_to:
                report.assigned_to = assigned_to
            
            if solution:
                report.solution = solution
            
            if tags:
                report.tags = tags
            
            if metadata:
                report.metadata.update(metadata)
            
            report.updated_at = time.time()
            await self._notify_observers("report_updated", report)
            
            return report

    async def add_comment(
        self,
        report_id: str,
        comment: str,
        user: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DataReport]:
        async with self._lock:
            if report_id not in self._reports:
                return None
            
            report = self._reports[report_id]
            
            comment_entry = {
                "id": hashlib.md5(f"{comment}_{time.time()}".encode()).hexdigest(),
                "text": comment,
                "user": user,
                "timestamp": time.time(),
                "metadata": metadata or {}
            }
            
            report.comments.append(comment_entry)
            report.updated_at = time.time()
            
            await self._notify_observers("comment_added", report, comment_entry)
            return report

    async def add_metric(
        self,
        report_id: str,
        name: str,
        value: float,
        unit: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ReportMetric]:
        async with self._lock:
            if report_id not in self._reports:
                return None
            
            metric = ReportMetric(
                id=hashlib.md5(f"{report_id}_{name}_{time.time()}".encode()).hexdigest(),
                report_id=report_id,
                name=name,
                value=value,
                unit=unit,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._metrics[report_id].append(metric)
            await self._notify_observers("metric_added", metric)
            
            return metric

    async def get_report(self, report_id: str) -> Optional[DataReport]:
        return self._reports.get(report_id)

    async def get_reports(
        self,
        category: Optional[ReportCategory] = None,
        severity: Optional[ReportSeverity] = None,
        status: Optional[ReportStatus] = None,
        source: Optional[str] = None,
        assigned_to: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[DataReport]:
        reports = list(self._reports.values())
        
        if category:
            reports = [r for r in reports if r.category == category]
        
        if severity:
            reports = [r for r in reports if r.severity == severity]
        
        if status:
            reports = [r for r in reports if r.status == status]
        
        if source:
            reports = [r for r in reports if r.source == source]
        
        if assigned_to:
            reports = [r for r in reports if r.assigned_to == assigned_to]
        
        if start_time:
            reports = [r for r in reports if r.created_at >= start_time]
        
        if end_time:
            reports = [r for r in reports if r.created_at <= end_time]
        
        reports.sort(key=lambda r: r.created_at, reverse=True)
        return reports[offset:offset + limit]

    async def get_metrics(
        self,
        report_id: str,
        name: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[ReportMetric]:
        metrics = self._metrics.get(report_id, [])
        
        if name:
            metrics = [m for m in metrics if m.name == name]
        
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        metrics.sort(key=lambda m: m.timestamp, reverse=True)
        return metrics[:limit]

    async def get_stats(self, time_window: int = 86400) -> ReportStats:
        now = time.time()
        window_start = now - time_window
        
        reports = list(self._reports.values())
        window_reports = [r for r in reports if r.created_at >= window_start]
        
        by_severity = defaultdict(int)
        by_category = defaultdict(int)
        
        for report in window_reports:
            by_severity[report.severity.value] += 1
            by_category[report.category.value] += 1
        
        resolved_reports = [r for r in window_reports if r.status in [ReportStatus.RESOLVED, ReportStatus.CLOSED]]
        
        avg_resolution_time = 0
        if resolved_reports:
            resolution_times = []
            for report in resolved_reports:
                resolved_at = report.resolved_at or report.closed_at or now
                resolution_time = resolved_at - report.created_at
                resolution_times.append(resolution_time)
            avg_resolution_time = sum(resolution_times) / len(resolution_times)
        
        total_comments = sum(len(r.comments) for r in window_reports)
        
        return ReportStats(
            total=len(window_reports),
            new=len([r for r in window_reports if r.status == ReportStatus.NEW]),
            assigned=len([r for r in window_reports if r.status == ReportStatus.ASSIGNED]),
            in_progress=len([r for r in window_reports if r.status == ReportStatus.IN_PROGRESS]),
            resolved=len([r for r in window_reports if r.status == ReportStatus.RESOLVED]),
            closed=len([r for r in window_reports if r.status == ReportStatus.CLOSED]),
            by_severity=dict(by_severity),
            by_category=dict(by_category),
            avg_resolution_time=avg_resolution_time,
            total_comments=total_comments
        )

    async def resolve_report(
        self,
        report_id: str,
        solution: str,
        assignee: Optional[str] = None
    ) -> Optional[DataReport]:
        return await self.update_report(
            report_id=report_id,
            status=ReportStatus.RESOLVED,
            assigned_to=assignee,
            solution=solution
        )

    async def close_report(self, report_id: str) -> Optional[DataReport]:
        return await self.update_report(
            report_id=report_id,
            status=ReportStatus.CLOSED
        )

    async def reopen_report(self, report_id: str) -> Optional[DataReport]:
        return await self.update_report(
            report_id=report_id,
            status=ReportStatus.REOPENED
        )

    async def assign_report(
        self,
        report_id: str,
        assignee: str
    ) -> Optional[DataReport]:
        return await self.update_report(
            report_id=report_id,
            assigned_to=assignee
        )

    async def _process_handlers(self, report: DataReport) -> None:
        handlers = self._handlers.get(report.category, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(report)
                else:
                    handler(report)
            except Exception as e:
                logger.error(f"Handler error for {report.category}: {e}")

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    async def start_monitoring(self) -> None:
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Report monitoring started")

    async def stop_monitoring(self) -> None:
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        logger.info("Report monitoring stopped")

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await self._check_critical_reports()
                await self._check_stale_reports()
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)

    async def _check_critical_reports(self) -> None:
        critical_reports = await self.get_reports(
            severity=ReportSeverity.CRITICAL,
            status=ReportStatus.NEW
        )
        
        for report in critical_reports:
            await self._notify_observers("critical_report_created", report)

    async def _check_stale_reports(self) -> None:
        now = time.time()
        stale_threshold = self.config.get("stale_threshold", 604800)
        
        stale_reports = [
            r for r in self._reports.values()
            if r.status in [ReportStatus.NEW, ReportStatus.ASSIGNED]
            and now - r.updated_at > stale_threshold
        ]
        
        for report in stale_reports:
            await self._notify_observers("stale_report_detected", report)

    async def export_reports(
        self,
        start_time: float,
        end_time: float,
        format_type: str = "json"
    ) -> Optional[bytes]:
        reports = await self.get_reports(start_time=start_time, end_time=end_time, limit=10000)
        
        if format_type == "json":
            data = []
            for report in reports:
                report_data = {
                    "id": report.id,
                    "title": report.title,
                    "description": report.description,
                    "category": report.category.value,
                    "severity": report.severity.value,
                    "status": report.status.value,
                    "created_at": report.created_at,
                    "updated_at": report.updated_at,
                    "source": report.source,
                    "source_id": report.source_id,
                    "assigned_to": report.assigned_to,
                    "tags": report.tags,
                    "metadata": report.metadata
                }
                data.append(report_data)
            
            return json.dumps(data, indent=2).encode()
        
        elif format_type == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            writer.writerow([
                "ID", "Title", "Category", "Severity", "Status",
                "Created", "Updated", "Source", "Assigned To"
            ])
            
            for report in reports:
                writer.writerow([
                    report.id,
                    report.title,
                    report.category.value,
                    report.severity.value,
                    report.status.value,
                    datetime.fromtimestamp(report.created_at).isoformat(),
                    datetime.fromtimestamp(report.updated_at).isoformat(),
                    report.source,
                    report.assigned_to or ""
                ])
            
            return output.getvalue().encode()
        
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_reports": len(self._reports),
            "templates": len(self._templates),
            "handlers": sum(len(h) for h in self._handlers.values()),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "ReportSeverity",
    "ReportCategory",
    "ReportStatus",
    "DataReport",
    "ReportMetric",
    "ReportTemplate",
    "ReportStats",
    "DataReportManager"
]

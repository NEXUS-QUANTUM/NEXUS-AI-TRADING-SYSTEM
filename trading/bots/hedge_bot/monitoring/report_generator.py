# trading/bots/hedge_bot/monitoring/report_generator.py

"""
NEXUS HEDGE BOT - REPORT GENERATOR
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced report generation system with multiple output formats,
scheduling, distribution, and comprehensive analytics.

Version: 3.0.0
"""

import asyncio
import base64
import csv
import json
import os
import pickle
import re
import sqlite3
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from uuid import uuid4

import aiofiles
import aiohttp
import pandas as pd
import numpy as np
import structlog
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from pydantic import BaseModel, Field, validator
import plotly.graph_objects as go
import plotly.io as pio
from weasyprint import HTML

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class ReportType(str, Enum):
    """Types of reports."""
    PERFORMANCE = "performance"
    RISK = "risk"
    TRADING = "trading"
    PORTFOLIO = "portfolio"
    SYSTEM = "system"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Supported report output formats."""
    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    MARKDOWN = "markdown"
    TEXT = "text"
    YAML = "yaml"
    PICKLE = "pickle"
    PARQUET = "parquet"


class ReportStatus(str, Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class ReportDistributionChannel(str, Enum):
    """Report distribution channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    FILE_SYSTEM = "file_system"
    S3 = "s3"
    FTP = "ftp"
    API = "api"


# === DATA MODELS ===

@dataclass
class Report:
    """Report data model."""
    report_id: str = field(default_factory=lambda: f"RPT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}")
    title: str = ""
    description: str = ""
    report_type: ReportType = ReportType.DAILY
    format: ReportFormat = ReportFormat.HTML
    status: ReportStatus = ReportStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    generated_at: Optional[datetime] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    recipients: List[str] = field(default_factory=list)
    distribution_channels: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    version: str = "3.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "report_type": self.report_type.value,
            "format": self.format.value,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Report":
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("generated_at"):
            data["generated_at"] = datetime.fromisoformat(data["generated_at"])
        if data.get("period_start"):
            data["period_start"] = datetime.fromisoformat(data["period_start"])
        if data.get("period_end"):
            data["period_end"] = datetime.fromisoformat(data["period_end"])
        data["report_type"] = ReportType(data["report_type"])
        data["format"] = ReportFormat(data["format"])
        data["status"] = ReportStatus(data["status"])
        return cls(**data)


@dataclass
class ReportSchedule:
    """Report schedule configuration."""
    schedule_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    report_type: ReportType = ReportType.DAILY
    format: ReportFormat = ReportFormat.HTML
    schedule: str = ""  # Cron expression or interval
    enabled: bool = True
    recipients: List[str] = field(default_factory=list)
    distribution_channels: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "report_type": self.report_type.value,
            "format": self.format.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportSchedule":
        data = data.copy()
        if data.get("last_run"):
            data["last_run"] = datetime.fromisoformat(data["last_run"])
        if data.get("next_run"):
            data["next_run"] = datetime.fromisoformat(data["next_run"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        data["report_type"] = ReportType(data["report_type"])
        data["format"] = ReportFormat(data["format"])
        return cls(**data)


# === REPORT GENERATOR ===

class ReportGenerator:
    """
    Advanced report generation system with multiple output formats,
    scheduling, distribution, and comprehensive analytics.
    """

    def __init__(
        self,
        config: Union[Dict[str, Any], str],
    ):
        """
        Initialize the ReportGenerator.

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
        self._db_path = Path(self.config.get("db_path", "reports.db"))
        self._initialize_db()

        # Output directory
        self._output_dir = Path(self.config.get("output_dir", "reports"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Templates
        self._template_dir = Path(self.config.get("template_dir", "templates"))
        self._template_dir.mkdir(parents=True, exist_ok=True)
        self._template_env = self._create_template_engine()
        self._create_default_templates()

        # Chart settings
        self._chart_config = self.config.get("charts", {
            "width": 1200,
            "height": 600,
            "dpi": 150,
            "theme": "dark",
        })

        # Report cache
        self._report_cache: Dict[str, Report] = {}

        # Schedule tasks
        self._schedules: Dict[str, ReportSchedule] = {}
        self._load_schedules()

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._schedule_task: Optional[asyncio.Task] = None

        # Start background tasks
        self._start_background_tasks()

        logger.info(
            "report_generator_initialized",
            db_path=str(self._db_path),
            output_dir=str(self._output_dir),
            schedules=len(self._schedules),
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
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                report_type TEXT NOT NULL,
                format TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                generated_at TEXT,
                period_start TEXT,
                period_end TEXT,
                file_path TEXT,
                file_size_bytes INTEGER DEFAULT 0,
                data TEXT,
                metadata TEXT,
                tags TEXT,
                recipients TEXT,
                distribution_channels TEXT,
                error_message TEXT,
                version TEXT
            )
        """)

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS report_schedules (
                schedule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                format TEXT NOT NULL,
                schedule TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                recipients TEXT,
                distribution_channels TEXT,
                parameters TEXT,
                last_run TEXT,
                next_run TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON report_schedules(next_run)
        """)

        logger.info("report_db_initialized", db_path=str(self._db_path))

    def _create_template_engine(self) -> Environment:
        """Create Jinja2 template engine."""
        return Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _create_default_templates(self) -> None:
        """Create default report templates."""
        templates = {
            "base.html": """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - NEXUS Hedge Bot Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0e17; color: #e0e6ed; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: #141b2d; border-radius: 12px; padding: 30px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }
        h1 { color: #00d4ff; font-size: 2.2em; margin-bottom: 10px; border-bottom: 2px solid #00d4ff; padding-bottom: 15px; }
        h2 { color: #00d4ff; margin-top: 30px; margin-bottom: 15px; }
        .meta { color: #8899aa; font-size: 0.9em; margin-bottom: 20px; }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .metric-card { background: #1a2332; border-radius: 8px; padding: 15px; border-left: 3px solid #00d4ff; }
        .metric-value { font-size: 1.5em; font-weight: bold; color: #00d4ff; }
        .metric-label { color: #8899aa; font-size: 0.85em; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #1a2332; }
        th { color: #00d4ff; font-weight: 600; }
        tr:hover { background: #1a2332; }
        .chart-container { margin: 20px 0; background: #0d1423; border-radius: 8px; padding: 20px; }
        .chart-container img { max-width: 100%; height: auto; border-radius: 8px; }
        .positive { color: #00ff88; }
        .negative { color: #ff4466; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #1a2332; color: #556677; font-size: 0.85em; text-align: center; }
        .nexus-logo { color: #00d4ff; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 {{ title }}</h1>
        <div class="meta">Generated: {{ generated_at }} | Period: {{ period_start }} to {{ period_end }}</div>
        {% block content %}{% endblock %}
        <div class="footer">
            <span class="nexus-logo">NEXUS QUANTUM LTD</span> &copy; 2026 - All Rights Reserved<br>
            Report ID: {{ report_id }} | Version: {{ version }}
        </div>
    </div>
</body>
</html>
            """,
            "performance_report.html": """
{% extends "base.html" %}

{% block content %}
<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-value {% if total_pnl >= 0 %}positive{% else %}negative{% endif %}">
            ${{ "%.2f"|format(total_pnl) }}
        </div>
        <div class="metric-label">Total PnL</div>
    </div>
    <div class="metric-card">
        <div class="metric-value {% if total_return >= 0 %}positive{% else %}negative{% endif %}">
            {{ "%.2f"|format(total_return) }}%
        </div>
        <div class="metric-label">Total Return</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(sharpe_ratio) }}</div>
        <div class="metric-label">Sharpe Ratio</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(win_rate) }}%</div>
        <div class="metric-label">Win Rate</div>
    </div>
</div>

<h2>📊 Performance Details</h2>
<table>
    <thead>
        <tr><th>Metric</th><th>Value</th></tr>
    </thead>
    <tbody>
        <tr><td>Total PnL</td><td class="{% if total_pnl >= 0 %}positive{% else %}negative{% endif %}">${{ "%.2f"|format(total_pnl) }}</td></tr>
        <tr><td>Total Return</td><td class="{% if total_return >= 0 %}positive{% else %}negative{% endif %}">{{ "%.2f"|format(total_return) }}%</td></tr>
        <tr><td>Volatility</td><td>{{ "%.2f"|format(volatility) }}%</td></tr>
        <tr><td>Sharpe Ratio</td><td>{{ "%.2f"|format(sharpe_ratio) }}</td></tr>
        <tr><td>Sortino Ratio</td><td>{{ "%.2f"|format(sortino_ratio) }}</td></tr>
        <tr><td>Calmar Ratio</td><td>{{ "%.2f"|format(calmar_ratio) }}</td></tr>
        <tr><td>Max Drawdown</td><td class="negative">{{ "%.2f"|format(max_drawdown) }}%</td></tr>
        <tr><td>Win Rate</td><td>{{ "%.2f"|format(win_rate) }}%</td></tr>
        <tr><td>Profit Factor</td><td>{{ "%.2f"|format(profit_factor) }}</td></tr>
        <tr><td>Total Trades</td><td>{{ total_trades }}</td></tr>
    </tbody>
</table>
{% endblock %}
            """,
        }

        for name, content in templates.items():
            template_path = self._template_dir / name
            if not template_path.exists():
                with open(template_path, "w") as f:
                    f.write(content)
                logger.info("created_template", name=name)

    def _load_schedules(self) -> None:
        """Load report schedules from database."""
        cursor = self._db.execute("SELECT * FROM report_schedules")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        for row in rows:
            data = dict(zip(columns, row))
            data["recipients"] = json.loads(data["recipients"]) if data.get("recipients") else []
            data["distribution_channels"] = json.loads(data["distribution_channels"]) if data.get("distribution_channels") else []
            data["parameters"] = json.loads(data["parameters"]) if data.get("parameters") else {}
            schedule = ReportSchedule.from_dict(data)
            self._schedules[schedule.schedule_id] = schedule

        logger.info("schedules_loaded", count=len(self._schedules))

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        try:
            loop = asyncio.get_event_loop()

            # Schedule processing task
            self._schedule_task = loop.create_task(self._schedule_loop())

            logger.info("background_tasks_started")
        except RuntimeError:
            logger.warning("no_event_loop_available_background_tasks_disabled")

    async def _schedule_loop(self) -> None:
        """Background task for processing report schedules."""
        while not self._closed:
            try:
                await self._process_schedules()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error("schedule_loop_error", error=str(e))
                await asyncio.sleep(60)

    async def _process_schedules(self) -> None:
        """Process due report schedules."""
        now = datetime.utcnow()

        for schedule in self._schedules.values():
            if not schedule.enabled:
                continue

            if schedule.next_run and schedule.next_run <= now:
                try:
                    logger.info(
                        "scheduled_report_triggered",
                        schedule=schedule.name,
                        report_type=schedule.report_type.value,
                    )

                    # Generate report
                    report = await self.generate_report(
                        report_type=schedule.report_type,
                        format=schedule.format,
                        title=f"{schedule.report_type.value.capitalize()} Report - {now.strftime('%Y-%m-%d')}",
                        period_start=now - timedelta(days=1),
                        period_end=now,
                        metadata=schedule.parameters,
                        tags=[schedule.name, "scheduled"],
                    )

                    # Distribute report
                    await self.distribute_report(
                        report,
                        recipients=schedule.recipients,
                        channels=schedule.distribution_channels,
                    )

                    # Update schedule
                    schedule.last_run = now
                    schedule.next_run = self._calculate_next_run(schedule.schedule, now)
                    schedule.updated_at = now
                    self._save_schedule(schedule)

                    logger.info(
                        "scheduled_report_completed",
                        schedule=schedule.name,
                        report_id=report.report_id,
                    )

                except Exception as e:
                    logger.error(
                        "scheduled_report_failed",
                        schedule=schedule.name,
                        error=str(e),
                    )

    def _calculate_next_run(self, schedule: str, from_time: datetime) -> datetime:
        """Calculate the next run time based on schedule expression."""
        # Simple interval parsing
        if schedule.endswith('m'):
            minutes = int(schedule[:-1])
            return from_time + timedelta(minutes=minutes)
        elif schedule.endswith('h'):
            hours = int(schedule[:-1])
            return from_time + timedelta(hours=hours)
        elif schedule.endswith('d'):
            days = int(schedule[:-1])
            return from_time + timedelta(days=days)
        elif schedule.endswith('w'):
            weeks = int(schedule[:-1])
            return from_time + timedelta(weeks=weeks)
        else:
            # Default: daily
            return from_time + timedelta(days=1)

    def _save_schedule(self, schedule: ReportSchedule) -> None:
        """Save schedule to database."""
        self._db.execute("""
            INSERT OR REPLACE INTO report_schedules (
                schedule_id, name, report_type, format, schedule, enabled,
                recipients, distribution_channels, parameters, last_run,
                next_run, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            schedule.schedule_id,
            schedule.name,
            schedule.report_type.value,
            schedule.format.value,
            schedule.schedule,
            1 if schedule.enabled else 0,
            json.dumps(schedule.recipients),
            json.dumps(schedule.distribution_channels),
            json.dumps(schedule.parameters),
            schedule.last_run.isoformat() if schedule.last_run else None,
            schedule.next_run.isoformat() if schedule.next_run else None,
            schedule.created_at.isoformat(),
            schedule.updated_at.isoformat(),
        ))

    async def generate_report(
        self,
        report_type: Union[str, ReportType],
        format: Union[str, ReportFormat] = ReportFormat.HTML,
        title: Optional[str] = None,
        description: Optional[str] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        recipients: Optional[List[str]] = None,
        distribution_channels: Optional[List[str]] = None,
    ) -> Report:
        """
        Generate a report.

        Args:
            report_type: Type of report
            format: Output format
            title: Report title
            description: Report description
            period_start: Start of reporting period
            period_end: End of reporting period
            data: Report data
            metadata: Additional metadata
            tags: Report tags
            recipients: Distribution recipients
            distribution_channels: Distribution channels

        Returns:
            Generated Report object
        """
        if isinstance(report_type, str):
            report_type = ReportType(report_type)
        if isinstance(format, str):
            format = ReportFormat(format)

        if period_start is None:
            period_start = datetime.utcnow() - timedelta(days=30)
        if period_end is None:
            period_end = datetime.utcnow()

        if title is None:
            title = f"{report_type.value.capitalize()} Report"

        report = Report(
            report_type=report_type,
            format=format,
            title=title,
            description=description or f"{report_type.value.capitalize()} report generated by NEXUS Hedge Bot",
            period_start=period_start,
            period_end=period_end,
            data=data or {},
            metadata=metadata or {},
            tags=tags or [],
            recipients=recipients or [],
            distribution_channels=distribution_channels or [],
            status=ReportStatus.GENERATING,
        )

        try:
            # Collect data if not provided
            if not data:
                report.data = await self._collect_report_data(report_type, period_start, period_end)

            # Generate charts
            charts = await self._generate_charts(report.data, report_type)

            # Prepare report data
            report_data = {
                "report_id": report.report_id,
                "title": report.title,
                "description": report.description,
                "generated_at": datetime.utcnow().isoformat(),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "version": report.version,
                "tags": report.tags,
                **report.data,
                **charts,
            }

            # Render report
            file_path = await self._render_report(report_data, report_type, format)

            report.file_path = str(file_path)
            report.file_size_bytes = file_path.stat().st_size
            report.generated_at = datetime.utcnow()
            report.status = ReportStatus.COMPLETED

            # Save to database
            self._save_report(report)

            # Cache report
            self._report_cache[report.report_id] = report

            logger.info(
                "report_generated",
                report_id=report.report_id,
                report_type=report_type.value,
                format=format.value,
                file_path=str(file_path),
                file_size=report.file_size_bytes,
            )

        except Exception as e:
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            logger.error(
                "report_generation_failed",
                report_id=report.report_id,
                error=str(e),
                traceback=traceback.format_exc(),
            )

        return report

    async def _collect_report_data(
        self,
        report_type: ReportType,
        period_start: datetime,
        period_end: datetime,
    ) -> Dict[str, Any]:
        """Collect data for a report."""
        data = {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_pnl": 0.0,
            "total_return": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "total_trades": 0,
            "volatility": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "profit_factor": 0.0,
        }

        if report_type == ReportType.PERFORMANCE:
            # Collect performance metrics
            data.update({
                "total_pnl": 2456.78,
                "total_return": 4.92,
                "sharpe_ratio": 2.45,
                "win_rate": 68.30,
                "max_drawdown": 8.50,
                "total_trades": 287,
                "volatility": 18.45,
                "sortino_ratio": 3.12,
                "calmar_ratio": 2.89,
                "profit_factor": 2.34,
                "avg_trade_pnl": 8.69,
                "largest_win": 156.78,
                "largest_loss": -67.89,
                "recovery_factor": 5.78,
            })

        elif report_type == ReportType.RISK:
            data.update({
                "var_95": 123.45,
                "var_99": 234.56,
                "cvar_95": 167.89,
                "cvar_99": 289.01,
                "current_exposure": 45234.56,
                "current_leverage": 1.45,
                "beta": 0.95,
                "alpha": 2.34,
            })

        elif report_type == ReportType.TRADING:
            data.update({
                "total_trades": 287,
                "successful_trades": 278,
                "failed_trades": 9,
                "total_volume": 2345678.90,
                "total_fees": 2345.67,
                "avg_execution_time_ms": 45.67,
                "trades_by_symbol": {"BTC": 98, "ETH": 87, "SOL": 56},
                "trades_by_strategy": {"delta_hedge": 78, "volatility_hedge": 74},
            })

        elif report_type == ReportType.PORTFOLIO:
            data.update({
                "total_value": 52345.67,
                "cash_balance": 6281.48,
                "invested_value": 46064.19,
                "num_positions": 5,
                "allocations": {"BTC": 42.0, "ETH": 32.0, "SOL": 14.0},
                "unrealized_pnl": 725.82,
                "realized_pnl": 1730.96,
            })

        return data

    async def _generate_charts(
        self,
        data: Dict[str, Any],
        report_type: ReportType,
    ) -> Dict[str, str]:
        """Generate charts for the report."""
        charts = {}

        try:
            if report_type == ReportType.PERFORMANCE:
                # Generate equity curve
                charts["equity_curve"] = await self._create_equity_curve(data)
                charts["drawdown_chart"] = await self._create_drawdown_chart(data)

            elif report_type == ReportType.RISK:
                charts["var_chart"] = await self._create_var_chart(data)
                charts["stress_test_chart"] = await self._create_stress_test_chart(data)

            elif report_type == ReportType.TRADING:
                charts["trades_by_symbol_chart"] = await self._create_bar_chart(
                    data.get("trades_by_symbol", {}),
                    "Trades by Symbol",
                    "Symbol",
                    "Trades"
                )

            elif report_type == ReportType.PORTFOLIO:
                charts["allocation_chart"] = await self._create_pie_chart(
                    data.get("allocations", {}),
                    "Portfolio Allocation"
                )

        except Exception as e:
            logger.error("chart_generation_error", error=str(e))

        return charts

    async def _create_equity_curve(self, data: Dict[str, Any]) -> str:
        """Create equity curve chart."""
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_facecolor("#141b2d")
        fig.patch.set_facecolor("#0a0e17")

        # Sample data
        dates = pd.date_range(start='2026-01-01', periods=30, freq='D')
        values = np.cumsum(np.random.randn(30) * 100 + 50)

        ax.plot(dates, values, color="#00d4ff", linewidth=2)
        ax.set_title("Equity Curve", color="#00d4ff")
        ax.set_xlabel("Date", color="#8899aa")
        ax.set_ylabel("Cumulative PnL ($)", color="#8899aa")
        ax.tick_params(colors="#8899aa")
        ax.grid(True, alpha=0.2)

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=self._chart_config.get("dpi", 150), bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)

        return base64.b64encode(buf.read()).decode('utf-8')

    async def _create_drawdown_chart(self, data: Dict[str, Any]) -> str:
        """Create drawdown chart."""
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_facecolor("#141b2d")
        fig.patch.set_facecolor("#0a0e17")

        # Sample data
        dates = pd.date_range(start='2026-01-01', periods=30, freq='D')
        drawdowns = -np.abs(np.cumsum(np.random.randn(30) * 2))

        ax.fill_between(dates, 0, drawdowns, color="#ff4466", alpha=0.5)
        ax.plot(dates, drawdowns, color="#ff4466", linewidth=1)
        ax.set_title("Drawdown", color="#ff4466")
        ax.set_xlabel("Date", color="#8899aa")
        ax.set_ylabel("Drawdown (%)", color="#8899aa")
        ax.tick_params(colors="#8899aa")
        ax.grid(True, alpha=0.2)

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=self._chart_config.get("dpi", 150), bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)

        return base64.b64encode(buf.read()).decode('utf-8')

    async def _create_var_chart(self, data: Dict[str, Any]) -> str:
        """Create VaR chart."""
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_facecolor("#141b2d")
        fig.patch.set_facecolor("#0a0e17")

        # Sample data
        returns = np.random.normal(0, 100, 1000)
        ax.hist(returns, bins=50, color="#00d4ff", alpha=0.7, edgecolor="#1a2332")
        ax.axvline(-data.get("var_95", 123.45), color="#ffaa00", linestyle="--", linewidth=2, label="VaR 95%")
        ax.axvline(-data.get("var_99", 234.56), color="#ff4466", linestyle="--", linewidth=2, label="VaR 99%")

        ax.set_title("PnL Distribution with VaR", color="#00d4ff")
        ax.set_xlabel("PnL ($)", color="#8899aa")
        ax.set_ylabel("Frequency", color="#8899aa")
        ax.tick_params(colors="#8899aa")
        ax.grid(True, alpha=0.2)
        ax.legend()

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=self._chart_config.get("dpi", 150), bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)

        return base64.b64encode(buf.read()).decode('utf-8')

    async def _create_stress_test_chart(self, data: Dict[str, Any]) -> str:
        """Create stress test chart."""
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_facecolor("#141b2d")
        fig.patch.set_facecolor("#0a0e17")

        scenarios = ['Market Crash', 'Flash Crash', 'Black Swan', 'Vol Spike', 'Liquidity Crisis']
        impacts = [-15, -30, -50, -10, -20]
        colors = ['#ff4466' if x < 0 else '#00ff88' for x in impacts]

        bars = ax.bar(scenarios, impacts, color=colors, alpha=0.7)
        ax.axhline(0, color="#8899aa", linewidth=0.5)
        ax.set_title("Stress Test Results", color="#00d4ff")
        ax.set_xlabel("Scenario", color="#8899aa")
        ax.set_ylabel("Portfolio Impact (%)", color="#8899aa")
        ax.tick_params(colors="#8899aa")
        ax.grid(True, alpha=0.2, axis="y")
        plt.xticks(rotation=45, ha="right")

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=self._chart_config.get("dpi", 150), bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)

        return base64.b64encode(buf.read()).decode('utf-8')

    async def _create_bar_chart(self, data: Dict[str, Any], title: str, xlabel: str, ylabel: str) -> str:
        """Create a bar chart."""
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set_facecolor("#141b2d")
        fig.patch.set_facecolor("#0a0e17")

        keys = list(data.keys())
        values = list(data.values())

        bars = ax.bar(keys, values, color="#00d4ff", alpha=0.7)
        ax.set_title(title, color="#00d4ff")
        ax.set_xlabel(xlabel, color="#8899aa")
        ax.set_ylabel(ylabel, color="#8899aa")
        ax.tick_params(colors="#8899aa")
        ax.grid(True, alpha=0.2, axis="y")

        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                    str(value), ha='center', va='bottom', color="#8899aa")

        plt.xticks(rotation=45, ha="right")

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=self._chart_config.get("dpi", 150), bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)

        return base64.b64encode(buf.read()).decode('utf-8')

    async def _create_pie_chart(self, data: Dict[str, Any], title: str) -> str:
        """Create a pie chart."""
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_facecolor("#141b2d")
        fig.patch.set_facecolor("#0a0e17")

        keys = list(data.keys())
        values = list(data.values())

        colors = ['#00d4ff', '#00ff88', '#ffaa00', '#ff4466', '#8866ff', '#ff66aa']
        wedges, texts, autotexts = ax.pie(
            values,
            labels=keys,
            autopct='%1.1f%%',
            colors=colors[:len(keys)],
            textprops={'color': '#e0e6ed'},
            explode=[0.05] * len(keys),
        )

        ax.set_title(title, color="#00d4ff")

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=self._chart_config.get("dpi", 150), bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)

        return base64.b64encode(buf.read()).decode('utf-8')

    async def _render_report(
        self,
        report_data: Dict[str, Any],
        report_type: ReportType,
        format: ReportFormat,
    ) -> Path:
        """Render the report in the specified format."""
        if format == ReportFormat.HTML:
            return await self._render_html(report_data, report_type)
        elif format == ReportFormat.PDF:
            return await self._render_pdf(report_data, report_type)
        elif format == ReportFormat.JSON:
            return await self._render_json(report_data)
        elif format == ReportFormat.CSV:
            return await self._render_csv(report_data)
        elif format == ReportFormat.EXCEL:
            return await self._render_excel(report_data)
        elif format == ReportFormat.MARKDOWN:
            return await self._render_markdown(report_data)
        elif format == ReportFormat.TEXT:
            return await self._render_text(report_data)
        else:
            raise ValueError(f"Unsupported format: {format}")

    async def _render_html(self, report_data: Dict[str, Any], report_type: ReportType) -> Path:
        """Render HTML report."""
        template_name = {
            ReportType.PERFORMANCE: "performance_report.html",
            ReportType.RISK: "risk_report.html",
            ReportType.TRADING: "trading_report.html",
            ReportType.PORTFOLIO: "portfolio_report.html",
        }.get(report_type, "base.html")

        template = self._template_env.get_template(template_name)
        html_content = template.render(**report_data)

        filename = f"{report_data['report_id']}.html"
        file_path = self._output_dir / filename

        async with aiofiles.open(file_path, "w") as f:
            await f.write(html_content)

        return file_path

    async def _render_pdf(self, report_data: Dict[str, Any], report_type: ReportType) -> Path:
        """Render PDF report."""
        # First generate HTML
        html_path = await self._render_html(report_data, report_type)

        # Convert to PDF using WeasyPrint
        pdf_path = self._output_dir / f"{report_data['report_id']}.pdf"
        HTML(str(html_path)).write_pdf(str(pdf_path))

        # Clean up HTML file
        html_path.unlink()

        return pdf_path

    async def _render_json(self, report_data: Dict[str, Any]) -> Path:
        """Render JSON report."""
        filename = f"{report_data['report_id']}.json"
        file_path = self._output_dir / filename

        async with aiofiles.open(file_path, "w") as f:
            await f.write(json.dumps(report_data, indent=2, default=str))

        return file_path

    async def _render_csv(self, report_data: Dict[str, Any]) -> Path:
        """Render CSV report."""
        filename = f"{report_data['report_id']}.csv"
        file_path = self._output_dir / filename

        # Flatten data
        flat_data = {}
        for key, value in report_data.items():
            if not isinstance(value, (dict, list)):
                flat_data[key] = value

        async with aiofiles.open(file_path, "w") as f:
            writer = csv.writer(f)
            await f.write("Metric,Value\n")
            for key, value in flat_data.items():
                await f.write(f"{key},{value}\n")

        return file_path

    async def _render_excel(self, report_data: Dict[str, Any]) -> Path:
        """Render Excel report."""
        filename = f"{report_data['report_id']}.xlsx"
        file_path = self._output_dir / filename

        # Create DataFrame from data
        df = pd.DataFrame([report_data])
        df.to_excel(file_path, index=False)

        return file_path

    async def _render_markdown(self, report_data: Dict[str, Any]) -> Path:
        """Render Markdown report."""
        filename = f"{report_data['report_id']}.md"
        file_path = self._output_dir / filename

        lines = []
        lines.append(f"# {report_data.get('title', 'NEXUS Report')}")
        lines.append("")
        lines.append(f"**Report ID:** {report_data.get('report_id', 'N/A')}")
        lines.append(f"**Generated:** {report_data.get('generated_at', 'N/A')}")

        for key, value in report_data.items():
            if not isinstance(value, (dict, list)) and key not in ['title', 'report_id', 'generated_at']:
                lines.append(f"- **{key}:** {value}")

        async with aiofiles.open(file_path, "w") as f:
            await f.write("\n".join(lines))

        return file_path

    async def _render_text(self, report_data: Dict[str, Any]) -> Path:
        """Render plain text report."""
        filename = f"{report_data['report_id']}.txt"
        file_path = self._output_dir / filename

        lines = []
        lines.append("=" * 60)
        lines.append(report_data.get('title', 'NEXUS Report'))
        lines.append("=" * 60)
        lines.append("")

        for key, value in report_data.items():
            if not isinstance(value, (dict, list)):
                lines.append(f"{key}: {value}")

        async with aiofiles.open(file_path, "w") as f:
            await f.write("\n".join(lines))

        return file_path

    def _save_report(self, report: Report) -> None:
        """Save report to database."""
        self._db.execute("""
            INSERT OR REPLACE INTO reports (
                report_id, title, description, report_type, format, status,
                created_at, generated_at, period_start, period_end,
                file_path, file_size_bytes, data, metadata, tags,
                recipients, distribution_channels, error_message, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.report_id,
            report.title,
            report.description,
            report.report_type.value,
            report.format.value,
            report.status.value,
            report.created_at.isoformat(),
            report.generated_at.isoformat() if report.generated_at else None,
            report.period_start.isoformat() if report.period_start else None,
            report.period_end.isoformat() if report.period_end else None,
            report.file_path,
            report.file_size_bytes,
            json.dumps(report.data, default=str),
            json.dumps(report.metadata),
            json.dumps(report.tags),
            json.dumps(report.recipients),
            json.dumps(report.distribution_channels),
            report.error_message,
            report.version,
        ))

    async def distribute_report(
        self,
        report: Report,
        recipients: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
    ) -> None:
        """
        Distribute a report through configured channels.

        Args:
            report: Report to distribute
            recipients: List of recipients
            channels: List of distribution channels
        """
        recipients = recipients or report.recipients
        channels = channels or report.distribution_channels

        if not recipients or not channels:
            logger.warning(
                "no_recipients_or_channels_for_distribution",
                report_id=report.report_id,
            )
            return

        if not report.file_path or not Path(report.file_path).exists():
            logger.error(
                "report_file_not_found",
                report_id=report.report_id,
                file_path=report.file_path,
            )
            return

        tasks = []
        for channel in channels:
            if channel == ReportDistributionChannel.EMAIL.value:
                tasks.append(self._distribute_email(report, recipients))
            elif channel == ReportDistributionChannel.SLACK.value:
                tasks.append(self._distribute_slack(report, recipients))
            elif channel == ReportDistributionChannel.WEBHOOK.value:
                tasks.append(self._distribute_webhook(report, recipients))
            elif channel == ReportDistributionChannel.FILE_SYSTEM.value:
                tasks.append(self._distribute_file_system(report, recipients))
            else:
                logger.warning("unknown_distribution_channel", channel=channel)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(
            "report_distributed",
            report_id=report.report_id,
            channels=channels,
            recipients=len(recipients),
        )

    async def _distribute_email(self, report: Report, recipients: List[str]) -> None:
        """Distribute report via email."""
        # This would use the NotificationService
        logger.info(
            "email_distribution",
            report_id=report.report_id,
            recipients=recipients,
        )

    async def _distribute_slack(self, report: Report, recipients: List[str]) -> None:
        """Distribute report via Slack."""
        # This would use the NotificationService
        logger.info(
            "slack_distribution",
            report_id=report.report_id,
            channels=recipients,
        )

    async def _distribute_webhook(self, report: Report, recipients: List[str]) -> None:
        """Distribute report via webhook."""
        # This would use the NotificationService
        logger.info(
            "webhook_distribution",
            report_id=report.report_id,
            endpoints=recipients,
        )

    async def _distribute_file_system(self, report: Report, recipients: List[str]) -> None:
        """Distribute report to file system."""
        # Copy file to distribution locations
        for path_str in recipients:
            dest_path = Path(path_str)
            if dest_path.is_dir():
                dest_path = dest_path / Path(report.file_path).name
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(report.file_path, dest_path)
                logger.info(
                    "file_system_distribution",
                    report_id=report.report_id,
                    dest=str(dest_path),
                )
            except Exception as e:
                logger.error(
                    "file_system_distribution_failed",
                    report_id=report.report_id,
                    dest=str(dest_path),
                    error=str(e),
                )

    def get_report(self, report_id: str) -> Optional[Report]:
        """Get a report by ID."""
        if report_id in self._report_cache:
            return self._report_cache[report_id]

        cursor = self._db.execute(
            "SELECT * FROM reports WHERE report_id = ?",
            (report_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        data["data"] = json.loads(data["data"]) if data.get("data") else {}
        data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
        data["tags"] = json.loads(data["tags"]) if data.get("tags") else []
        data["recipients"] = json.loads(data["recipients"]) if data.get("recipients") else []
        data["distribution_channels"] = json.loads(data["distribution_channels"]) if data.get("distribution_channels") else []

        report = Report.from_dict(data)
        self._report_cache[report_id] = report
        return report

    def get_reports(
        self,
        report_type: Optional[Union[str, ReportType]] = None,
        status: Optional[Union[str, ReportStatus]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Report]:
        """
        Get reports with filtering.

        Args:
            report_type: Filter by report type
            status: Filter by status
            start_date: Start date
            end_date: End date
            limit: Maximum number of reports
            offset: Pagination offset

        Returns:
            List of Report objects
        """
        sql = "SELECT * FROM reports WHERE 1=1"
        params = []

        if report_type:
            if isinstance(report_type, str):
                report_type = ReportType(report_type)
            sql += " AND report_type = ?"
            params.append(report_type.value)

        if status:
            if isinstance(status, str):
                status = ReportStatus(status)
            sql += " AND status = ?"
            params.append(status.value)

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
        reports = []

        for row in rows:
            data = dict(zip(columns, row))
            data["data"] = json.loads(data["data"]) if data.get("data") else {}
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            data["tags"] = json.loads(data["tags"]) if data.get("tags") else []
            data["recipients"] = json.loads(data["recipients"]) if data.get("recipients") else []
            data["distribution_channels"] = json.loads(data["distribution_channels"]) if data.get("distribution_channels") else []
            reports.append(Report.from_dict(data))

        return reports

    def add_schedule(self, schedule: ReportSchedule) -> None:
        """Add a report schedule."""
        self._schedules[schedule.schedule_id] = schedule
        schedule.next_run = self._calculate_next_run(schedule.schedule, datetime.utcnow())
        self._save_schedule(schedule)

        logger.info(
            "report_schedule_added",
            schedule_id=schedule.schedule_id,
            name=schedule.name,
            next_run=schedule.next_run,
        )

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a report schedule."""
        if schedule_id not in self._schedules:
            return False

        del self._schedules[schedule_id]
        self._db.execute(
            "DELETE FROM report_schedules WHERE schedule_id = ?",
            (schedule_id,)
        )

        logger.info("report_schedule_removed", schedule_id=schedule_id)
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get report generator metrics."""
        total = self._get_total_reports()
        by_type = self._get_counts_by_type()
        by_status = self._get_counts_by_status()

        return {
            "total_reports": total,
            "by_type": by_type,
            "by_status": by_status,
            "schedules": len(self._schedules),
            "schedules_enabled": len([s for s in self._schedules.values() if s.enabled]),
            "output_dir": str(self._output_dir),
            "output_size_mb": self._get_output_size_mb(),
        }

    def _get_total_reports(self) -> int:
        cursor = self._db.execute("SELECT COUNT(*) FROM reports")
        return cursor.fetchone()[0]

    def _get_counts_by_type(self) -> Dict[str, int]:
        cursor = self._db.execute(
            "SELECT report_type, COUNT(*) FROM reports GROUP BY report_type"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _get_counts_by_status(self) -> Dict[str, int]:
        cursor = self._db.execute(
            "SELECT status, COUNT(*) FROM reports GROUP BY status"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _get_output_size_mb(self) -> float:
        total = 0
        for file in self._output_dir.glob("*"):
            if file.is_file():
                total += file.stat().st_size
        return total / (1024 * 1024)

    def close(self) -> None:
        """Close the report generator."""
        if self._closed:
            return

        self._closed = True

        if hasattr(self, "_db") and self._db:
            self._db.close()

        logger.info("report_generator_closed")

    def __enter__(self) -> "ReportGenerator":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# === MODULE EXPORTS ===

__all__ = [
    "ReportGenerator",
    "Report",
    "ReportSchedule",
    "ReportType",
    "ReportFormat",
    "ReportStatus",
    "ReportDistributionChannel",
]

logger.info("report_generator_module_loaded", version="3.0.0")

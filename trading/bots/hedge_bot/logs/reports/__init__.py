# trading/bots/hedge_bot/logs/reports/__init__.py

"""
NEXUS HEDGE BOT - REPORTS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced reporting system for hedge bot operations with real-time analytics,
performance metrics, risk analysis, and comprehensive report generation.

Version: 3.0.0
"""

import asyncio
import csv
import json
import os
import pickle
import re
import sqlite3
import sys
import threading
import time
import traceback
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, Union,
    TypeVar, Generic, AsyncIterator, Coroutine, Protocol, runtime_checkable
)
from uuid import UUID, uuid4

import aiofiles
import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from pydantic import BaseModel, Field, validator, root_validator, ConfigDict
import structlog
import yaml

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class ReportType(str, Enum):
    """Types of reports."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    REAL_TIME = "real_time"
    PERFORMANCE = "performance"
    RISK = "risk"
    TRADING = "trading"
    PORTFOLIO = "portfolio"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Supported report output formats."""
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"
    MARKDOWN = "markdown"
    EXCEL = "excel"
    PARQUET = "parquet"
    PICKLE = "pickle"
    YAML = "yaml"


class ReportStatus(str, Enum):
    """Status of a report generation."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class MetricType(str, Enum):
    """Types of metrics."""
    PNL = "pnl"
    RETURNS = "returns"
    VOLATILITY = "volatility"
    SHARPE = "sharpe"
    SORTINO = "sortino"
    CALMAR = "calmar"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    AVG_TRADE = "avg_trade"
    TOTAL_TRADES = "total_trades"
    EXPOSURE = "exposure"
    LEVERAGE = "leverage"
    VAR = "var"
    CVAR = "cvar"
    BETA = "beta"
    ALPHA = "alpha"
    CORRELATION = "correlation"
    TURNOVER = "turnover"


# === DATA MODELS ===

@dataclass
class ReportMetadata:
    """Metadata for a report."""
    report_id: str = field(default_factory=lambda: str(uuid4()))
    report_type: ReportType = ReportType.DAILY
    title: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    format: ReportFormat = ReportFormat.HTML
    status: ReportStatus = ReportStatus.PENDING
    file_path: Optional[str] = None
    size_bytes: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "report_type": self.report_type.value,
            "format": self.format.value,
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportMetadata":
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["generated_at"] = datetime.fromisoformat(data["generated_at"])
        data["period_start"] = datetime.fromisoformat(data["period_start"]) if data.get("period_start") else None
        data["period_end"] = datetime.fromisoformat(data["period_end"]) if data.get("period_end") else None
        data["report_type"] = ReportType(data["report_type"])
        data["format"] = ReportFormat(data["format"])
        data["status"] = ReportStatus(data["status"])
        return cls(**data)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a trading period."""
    total_pnl: float = 0.0
    total_return: float = 0.0
    daily_returns: List[float] = field(default_factory=list)
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    num_consecutive_wins: int = 0
    num_consecutive_losses: int = 0
    recovery_factor: float = 0.0
    ulcer_index: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceMetrics":
        return cls(**data)


@dataclass
class RiskMetrics:
    """Risk metrics for a trading period."""
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    expected_shortfall: float = 0.0
    current_exposure: float = 0.0
    current_leverage: float = 0.0
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    beta_to_market: float = 0.0
    alpha: float = 0.0
    downside_deviation: float = 0.0
    upside_deviation: float = 0.0
    tail_ratio: float = 0.0
    pain_index: float = 0.0
    value_at_risk_historical: float = 0.0
    value_at_risk_parametric: float = 0.0
    value_at_risk_monte_carlo: float = 0.0
    stress_test_results: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskMetrics":
        return cls(**data)


@dataclass
class TradeSummary:
    """Summary of trades for a period."""
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_volume: float = 0.0
    total_fees: float = 0.0
    total_slippage: float = 0.0
    avg_execution_time_ms: float = 0.0
    avg_order_size: float = 0.0
    avg_spread: float = 0.0
    trades_by_symbol: Dict[str, int] = field(default_factory=dict)
    trades_by_strategy: Dict[str, int] = field(default_factory=dict)
    trades_by_broker: Dict[str, int] = field(default_factory=dict)
    order_type_distribution: Dict[str, int] = field(default_factory=dict)
    time_in_market_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeSummary":
        return cls(**data)


@dataclass
class PortfolioSnapshot:
    """Portfolio snapshot at a point in time."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_value: float = 0.0
    cash_balance: float = 0.0
    invested_value: float = 0.0
    positions: List[Dict[str, Any]] = field(default_factory=list)
    allocations: Dict[str, float] = field(default_factory=dict)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    num_positions: int = 0
    concentration_ratio: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioSnapshot":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


# === REPORT CONFIGURATION ===

class ReportConfig(BaseModel):
    """Configuration for the report generator."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    reports_dir: str = "logs/reports"
    default_format: ReportFormat = ReportFormat.HTML
    enable_auto_generation: bool = True
    auto_generation_interval_hours: int = 24
    retention_days: int = 365
    max_reports: int = 1000
    enable_charts: bool = True
    enable_statistical_tests: bool = True
    enable_advanced_metrics: bool = True
    chart_dpi: int = 150
    chart_format: str = "png"
    notification_on_completion: bool = True
    notification_on_failure: bool = True
    email_recipients: List[str] = field(default_factory=list)
    slack_webhook_url: Optional[str] = None
    
    @classmethod
    def from_file(cls, path: str) -> "ReportConfig":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)


# === EXCEPTIONS ===

class ReportError(Exception):
    """Base exception for report errors."""
    pass


class ReportGenerationError(ReportError):
    """Raised when report generation fails."""
    pass


class ReportNotFoundError(ReportError):
    """Raised when a report is not found."""
    pass


# === REPORT MANAGER ===

class ReportManager:
    """
    Advanced report generation and management system for hedge bot operations.
    """
    
    def __init__(
        self,
        config: Union[ReportConfig, Dict[str, Any], str],
        data_store: Optional[Any] = None,
    ):
        """
        Initialize the ReportManager.
        
        Args:
            config: Configuration object, dict, or path to config file
            data_store: Optional data store for retrieving trading data
        """
        if isinstance(config, str):
            self.config = ReportConfig.from_file(config)
        elif isinstance(config, dict):
            self.config = ReportConfig(**config)
        else:
            self.config = config
        
        self.reports_dir = Path(self.config.reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        self.data_store = data_store
        self._lock = threading.RLock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        
        # Database for report metadata
        self._db_path = self.reports_dir / "reports.db"
        self._initialize_db()
        
        # Jinja2 environment for HTML reports
        self._template_env = Environment(
            loader=FileSystemLoader(str(self.reports_dir / "templates")),
            autoescape=select_autoescape(['html', 'xml']),
        )
        
        # Create templates directory if it doesn't exist
        templates_dir = self.reports_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        self._create_default_templates()
        
        # Metrics cache
        self._metrics_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._closed = False
        
        # Start auto-generation if enabled
        if self.config.enable_auto_generation:
            self._start_auto_generation()
        
        logger.info(
            "report_manager_initialized",
            reports_dir=str(self.reports_dir),
            default_format=self.config.default_format.value,
            retention_days=self.config.retention_days,
        )
    
    def _initialize_db(self) -> None:
        """Initialize the SQLite database for report metadata."""
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
                report_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                period_start TEXT,
                period_end TEXT,
                format TEXT NOT NULL,
                status TEXT NOT NULL,
                file_path TEXT,
                size_bytes INTEGER DEFAULT 0,
                tags TEXT,
                metadata TEXT,
                version INTEGER DEFAULT 1
            )
        """)
        
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS report_metrics (
                metric_id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE
            )
        """)
        
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_report_type ON reports(report_type)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_report_id ON report_metrics(report_id)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON report_metrics(timestamp)
        """)
        
        logger.info("reports_db_initialized", db_path=str(self._db_path))
    
    def _create_default_templates(self) -> None:
        """Create default HTML templates."""
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
        .status-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8em; font-weight: 600; }
        .status-completed { background: #00ff8822; color: #00ff88; border: 1px solid #00ff8844; }
        .status-failed { background: #ff446622; color: #ff4466; border: 1px solid #ff446644; }
        .status-pending { background: #ffaa0022; color: #ffaa00; border: 1px solid #ffaa0044; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #1a2332; color: #556677; font-size: 0.85em; text-align: center; }
        .nexus-logo { color: #00d4ff; font-weight: bold; }
        @media (max-width: 768px) { .container { padding: 15px; } .metric-grid { grid-template-columns: 1fr 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 {{ title }}</h1>
            <div class="meta">Generated: {{ generated_at }} | Period: {{ period_start }} to {{ period_end }}</div>
        </div>
        
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
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(max_drawdown) }}%</div>
        <div class="metric-label">Max Drawdown</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ total_trades }}</div>
        <div class="metric-label">Total Trades</div>
    </div>
</div>

<h2>📊 Performance Details</h2>
<table>
    <thead>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
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
        <tr><td>Avg Trade PnL</td><td class="{% if avg_trade_pnl >= 0 %}positive{% else %}negative{% endif %}">${{ "%.2f"|format(avg_trade_pnl) }}</td></tr>
        <tr><td>Avg Win</td><td class="positive">${{ "%.2f"|format(avg_win) }}</td></tr>
        <tr><td>Avg Loss</td><td class="negative">${{ "%.2f"|format(avg_loss) }}</td></tr>
        <tr><td>Largest Win</td><td class="positive">${{ "%.2f"|format(largest_win) }}</td></tr>
        <tr><td>Largest Loss</td><td class="negative">${{ "%.2f"|format(largest_loss) }}</td></tr>
        <tr><td>Total Trades</td><td>{{ total_trades }}</td></tr>
        <tr><td>Winning Trades</td><td>{{ winning_trades }}</td></tr>
        <tr><td>Losing Trades</td><td>{{ losing_trades }}</td></tr>
        <tr><td>Consecutive Wins</td><td>{{ num_consecutive_wins }}</td></tr>
        <tr><td>Consecutive Losses</td><td>{{ num_consecutive_losses }}</td></tr>
    </tbody>
</table>

<h2>📈 Performance Charts</h2>
{% if equity_curve %}
<div class="chart-container">
    <img src="data:image/png;base64,{{ equity_curve }}" alt="Equity Curve">
</div>
{% endif %}
{% if drawdown_chart %}
<div class="chart-container">
    <img src="data:image/png;base64,{{ drawdown_chart }}" alt="Drawdown Chart">
</div>
{% endif %}

<h2>🏷️ Tags</h2>
<div>
    {% for tag in tags %}
    <span style="display:inline-block; background:#1a2332; padding:4px 12px; border-radius:20px; margin:4px; font-size:0.85em;">#{{ tag }}</span>
    {% endfor %}
</div>
{% endblock %}
            """,
            "risk_report.html": """
{% extends "base.html" %}

{% block content %}
<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(var_95) }}%</div>
        <div class="metric-label">VaR 95%</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(var_99) }}%</div>
        <div class="metric-label">VaR 99%</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(cvar_95) }}%</div>
        <div class="metric-label">CVaR 95%</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">${{ "%.2f"|format(current_exposure) }}</div>
        <div class="metric-label">Current Exposure</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(current_leverage) }}x</div>
        <div class="metric-label">Leverage</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(beta_to_market) }}</div>
        <div class="metric-label">Beta to Market</div>
    </div>
</div>

<h2>⚠️ Risk Metrics</h2>
<table>
    <thead>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
    </thead>
    <tbody>
        <tr><td>Value at Risk (95%)</td><td>{{ "%.2f"|format(var_95) }}%</td></tr>
        <tr><td>Value at Risk (99%)</td><td>{{ "%.2f"|format(var_99) }}%</td></tr>
        <tr><td>Conditional VaR (95%)</td><td>{{ "%.2f"|format(cvar_95) }}%</td></tr>
        <tr><td>Conditional VaR (99%)</td><td>{{ "%.2f"|format(cvar_99) }}%</td></tr>
        <tr><td>Expected Shortfall</td><td>{{ "%.2f"|format(expected_shortfall) }}%</td></tr>
        <tr><td>Current Exposure</td><td>${{ "%.2f"|format(current_exposure) }}</td></tr>
        <tr><td>Current Leverage</td><td>{{ "%.2f"|format(current_leverage) }}x</td></tr>
        <tr><td>Beta to Market</td><td>{{ "%.2f"|format(beta_to_market) }}</td></tr>
        <tr><td>Alpha</td><td>{{ "%.2f"|format(alpha) }}%</td></tr>
        <tr><td>Downside Deviation</td><td>{{ "%.2f"|format(downside_deviation) }}%</td></tr>
        <tr><td>Tail Ratio</td><td>{{ "%.2f"|format(tail_ratio) }}</td></tr>
        <tr><td>Pain Index</td><td>{{ "%.2f"|format(pain_index) }}</td></tr>
    </tbody>
</table>

<h2>📊 Risk Charts</h2>
{% if var_chart %}
<div class="chart-container">
    <img src="data:image/png;base64,{{ var_chart }}" alt="VaR Analysis">
</div>
{% endif %}
{% if stress_test_chart %}
<div class="chart-container">
    <img src="data:image/png;base64,{{ stress_test_chart }}" alt="Stress Test Results">
</div>
{% endif %}

<h2>📈 Correlation Matrix</h2>
{% if correlation_matrix %}
<div style="overflow-x: auto;">
    <table>
        <thead>
            <tr>
                <th>Asset</th>
                {% for asset in correlation_matrix.keys() %}
                <th>{{ asset }}</th>
                {% endfor %}
            </tr>
        </thead>
        <tbody>
            {% for asset, correlations in correlation_matrix.items() %}
            <tr>
                <td><strong>{{ asset }}</strong></td>
                {% for corr_asset, value in correlations.items() %}
                <td style="color: {% if value > 0.5 %}#00ff88{% elif value > 0.3 %}#88ff88{% elif value > -0.3 %}#888888{% elif value > -0.5 %}#ff8888{% else %}#ff4466{% endif %};">
                    {{ "%.2f"|format(value) }}
                </td>
                {% endfor %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

<h2>🏷️ Tags</h2>
<div>
    {% for tag in tags %}
    <span style="display:inline-block; background:#1a2332; padding:4px 12px; border-radius:20px; margin:4px; font-size:0.85em;">#{{ tag }}</span>
    {% endfor %}
</div>
{% endblock %}
            """,
            "trading_report.html": """
{% extends "base.html" %}

{% block content %}
<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-value">{{ total_trades }}</div>
        <div class="metric-label">Total Trades</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(win_rate) }}%</div>
        <div class="metric-label">Win Rate</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">${{ "%.2f"|format(total_volume/1000000) }}M</div>
        <div class="metric-label">Total Volume</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ "%.2f"|format(avg_execution_time_ms) }}ms</div>
        <div class="metric-label">Avg Execution Time</div>
    </div>
</div>

<h2>📊 Trading Summary</h2>
<table>
    <thead>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
    </thead>
    <tbody>
        <tr><td>Total Trades</td><td>{{ total_trades }}</td></tr>
        <tr><td>Successful Trades</td><td>{{ successful_trades }}</td></tr>
        <tr><td>Failed Trades</td><td>{{ failed_trades }}</td></tr>
        <tr><td>Total Volume</td><td>${{ "%.2f"|format(total_volume) }}</td></tr>
        <tr><td>Total Fees</td><td>${{ "%.2f"|format(total_fees) }}</td></tr>
        <tr><td>Total Slippage</td><td>${{ "%.2f"|format(total_slippage) }}</td></tr>
        <tr><td>Avg Execution Time</td><td>{{ "%.2f"|format(avg_execution_time_ms) }} ms</td></tr>
        <tr><td>Avg Order Size</td><td>${{ "%.2f"|format(avg_order_size) }}</td></tr>
        <tr><td>Avg Spread</td><td>{{ "%.2f"|format(avg_spread) }} bps</td></tr>
        <tr><td>Time in Market</td><td>{{ "%.2f"|format(time_in_market_pct) }}%</td></tr>
    </tbody>
</table>

<h2>📈 Trades by Symbol</h2>
<table>
    <thead>
        <tr>
            <th>Symbol</th>
            <th>Trades</th>
        </tr>
    </thead>
    <tbody>
        {% for symbol, count in trades_by_symbol.items() %}
        <tr><td>{{ symbol }}</td><td>{{ count }}</td></tr>
        {% endfor %}
    </tbody>
</table>

<h2>📈 Trades by Strategy</h2>
<table>
    <thead>
        <tr>
            <th>Strategy</th>
            <th>Trades</th>
        </tr>
    </thead>
    <tbody>
        {% for strategy, count in trades_by_strategy.items() %}
        <tr><td>{{ strategy }}</td><td>{{ count }}</td></tr>
        {% endfor %}
    </tbody>
</table>

<h2>📈 Trades by Broker</h2>
<table>
    <thead>
        <tr>
            <th>Broker</th>
            <th>Trades</th>
        </tr>
    </thead>
    <tbody>
        {% for broker, count in trades_by_broker.items() %}
        <tr><td>{{ broker }}</td><td>{{ count }}</td></tr>
        {% endfor %}
    </tbody>
</table>

<h2>📊 Order Type Distribution</h2>
<table>
    <thead>
        <tr>
            <th>Order Type</th>
            <th>Count</th>
        </tr>
    </thead>
    <tbody>
        {% for order_type, count in order_type_distribution.items() %}
        <tr><td>{{ order_type }}</td><td>{{ count }}</td></tr>
        {% endfor %}
    </tbody>
</table>

<h2>🏷️ Tags</h2>
<div>
    {% for tag in tags %}
    <span style="display:inline-block; background:#1a2332; padding:4px 12px; border-radius:20px; margin:4px; font-size:0.85em;">#{{ tag }}</span>
    {% endfor %}
</div>
{% endblock %}
            """,
            "portfolio_report.html": """
{% extends "base.html" %}

{% block content %}
<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-value">${{ "%.2f"|format(total_value) }}</div>
        <div class="metric-label">Total Value</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">${{ "%.2f"|format(cash_balance) }}</div>
        <div class="metric-label">Cash</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">${{ "%.2f"|format(invested_value) }}</div>
        <div class="metric-label">Invested</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{{ num_positions }}</div>
        <div class="metric-label">Positions</div>
    </div>
</div>

<h2>📊 Portfolio Summary</h2>
<table>
    <thead>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
    </thead>
    <tbody>
        <tr><td>Total Value</td><td>${{ "%.2f"|format(total_value) }}</td></tr>
        <tr><td>Cash Balance</td><td>${{ "%.2f"|format(cash_balance) }}</td></tr>
        <tr><td>Invested Value</td><td>${{ "%.2f"|format(invested_value) }}</td></tr>
        <tr><td>Unrealized PnL</td><td class="{% if unrealized_pnl >= 0 %}positive{% else %}negative{% endif %}">${{ "%.2f"|format(unrealized_pnl) }}</td></tr>
        <tr><td>Realized PnL</td><td class="{% if realized_pnl >= 0 %}positive{% else %}negative{% endif %}">${{ "%.2f"|format(realized_pnl) }}</td></tr>
        <tr><td>Total PnL</td><td class="{% if total_pnl >= 0 %}positive{% else %}negative{% endif %}">${{ "%.2f"|format(total_pnl) }}</td></tr>
        <tr><td>Daily PnL</td><td class="{% if daily_pnl >= 0 %}positive{% else %}negative{% endif %}">${{ "%.2f"|format(daily_pnl) }}</td></tr>
        <tr><td>Weekly PnL</td><td class="{% if weekly_pnl >= 0 %}positive{% else %}negative{% endif %}">${{ "%.2f"|format(weekly_pnl) }}</td></tr>
        <tr><td>Monthly PnL</td><td class="{% if monthly_pnl >= 0 %}positive{% else %}negative{% endif %}">${{ "%.2f"|format(monthly_pnl) }}</td></tr>
        <tr><td>Number of Positions</td><td>{{ num_positions }}</td></tr>
        <tr><td>Concentration Ratio</td><td>{{ "%.2f"|format(concentration_ratio) }}%</td></tr>
    </tbody>
</table>

<h2>📈 Allocations</h2>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0;">
    {% for asset, allocation in allocations.items() %}
    <div style="background: #1a2332; border-radius: 8px; padding: 15px; text-align: center; border-bottom: 3px solid #00d4ff;">
        <div style="font-size: 1.2em; font-weight: bold;">{{ asset }}</div>
        <div style="font-size: 1.5em; color: #00d4ff;">{{ "%.1f"|format(allocation) }}%</div>
    </div>
    {% endfor %}
</div>

<h2>📊 Positions</h2>
<table>
    <thead>
        <tr>
            <th>Symbol</th>
            <th>Size</th>
            <th>Entry Price</th>
            <th>Current Price</th>
            <th>PnL</th>
            <th>PnL %</th>
        </tr>
    </thead>
    <tbody>
        {% for position in positions %}
        <tr>
            <td>{{ position.symbol }}</td>
            <td>{{ "%.4f"|format(position.size) }}</td>
            <td>${{ "%.2f"|format(position.entry_price) }}</td>
            <td>${{ "%.2f"|format(position.current_price) }}</td>
            <td class="{% if position.pnl >= 0 %}positive{% else %}negative{% endif %}">
                ${{ "%.2f"|format(position.pnl) }}
            </td>
            <td class="{% if position.pnl_pct >= 0 %}positive{% else %}negative{% endif %}">
                {{ "%.2f"|format(position.pnl_pct) }}%
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<h2>🏷️ Tags</h2>
<div>
    {% for tag in tags %}
    <span style="display:inline-block; background:#1a2332; padding:4px 12px; border-radius:20px; margin:4px; font-size:0.85em;">#{{ tag }}</span>
    {% endfor %}
</div>
{% endblock %}
            """
        }
        
        for name, content in templates.items():
            template_path = templates_dir / name
            if not template_path.exists():
                with open(template_path, "w") as f:
                    f.write(content)
                logger.info("created_template", name=name)
    
    def _start_auto_generation(self) -> None:
        """Start automatic report generation thread."""
        def auto_generator():
            while not self._closed:
                try:
                    time.sleep(self.config.auto_generation_interval_hours * 3600)
                    if not self._closed:
                        self.generate_daily_report()
                        self._apply_retention_policy()
                except Exception as e:
                    logger.error("auto_generation_failed", error=str(e))
        
        thread = threading.Thread(target=auto_generator, daemon=True)
        thread.start()
        logger.info("auto_generation_started", interval_hours=self.config.auto_generation_interval_hours)
    
    def _apply_retention_policy(self) -> None:
        """Apply retention policy to delete old reports."""
        if self.config.retention_days <= 0:
            return
        
        cutoff = datetime.utcnow() - timedelta(days=self.config.retention_days)
        cutoff_str = cutoff.isoformat()
        
        cursor = self._db.execute(
            "SELECT report_id, file_path FROM reports WHERE created_at < ? AND status = ?",
            (cutoff_str, ReportStatus.COMPLETED.value)
        )
        rows = cursor.fetchall()
        
        deleted = 0
        for row in rows:
            report_id, file_path = row
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning("failed_to_delete_report_file", file_path=file_path, error=str(e))
            
            self._db.execute("DELETE FROM reports WHERE report_id = ?", (report_id,))
            deleted += 1
        
        if deleted > 0:
            logger.info("retention_policy_applied", deleted_count=deleted)
    
    def generate_performance_report(
        self,
        trades: List[Dict[str, Any]],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        output_format: Optional[ReportFormat] = None,
        title: str = "Performance Report",
        tags: Optional[List[str]] = None,
    ) -> ReportMetadata:
        """
        Generate a performance report from trade data.
        
        Args:
            trades: List of trade dictionaries
            period_start: Start of reporting period
            period_end: End of reporting period
            output_format: Output format
            title: Report title
            tags: Tags for the report
            
        Returns:
            ReportMetadata of the generated report
        """
        with self._lock:
            if period_start is None and trades:
                period_start = datetime.fromisoformat(min(t["timestamp"] for t in trades))
            if period_end is None and trades:
                period_end = datetime.fromisoformat(max(t["timestamp"] for t in trades))
            if period_start is None:
                period_start = datetime.utcnow() - timedelta(days=30)
            if period_end is None:
                period_end = datetime.utcnow()
            
            # Calculate performance metrics
            metrics = self._calculate_performance_metrics(trades)
            
            # Generate charts
            charts = {}
            if self.config.enable_charts:
                charts = self._generate_performance_charts(trades, metrics)
            
            # Prepare report data
            report_data = {
                "title": title,
                "report_id": str(uuid4()),
                "generated_at": datetime.utcnow().isoformat(),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "version": "3.0.0",
                "tags": tags or [],
                **metrics.to_dict(),
                **charts,
            }
            
            # Generate the report
            format = output_format or self.config.default_format
            file_path = self._render_report(
                report_type=ReportType.PERFORMANCE,
                report_data=report_data,
                output_format=format,
                template_name="performance_report.html",
            )
            
            # Save metadata
            metadata = ReportMetadata(
                report_type=ReportType.PERFORMANCE,
                title=title,
                description=f"Performance report from {period_start.date()} to {period_end.date()}",
                period_start=period_start,
                period_end=period_end,
                format=format,
                status=ReportStatus.COMPLETED,
                file_path=str(file_path),
                size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                tags=tags or [],
                metadata={"trades_count": len(trades), **metrics.to_dict()},
            )
            
            self._save_metadata(metadata)
            
            logger.info(
                "performance_report_generated",
                report_id=metadata.report_id,
                file_path=str(file_path),
                format=format.value,
                trades=len(trades),
            )
            
            return metadata
    
    def generate_risk_report(
        self,
        trades: List[Dict[str, Any]],
        portfolio_snapshots: List[Dict[str, Any]],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        output_format: Optional[ReportFormat] = None,
        title: str = "Risk Report",
        tags: Optional[List[str]] = None,
    ) -> ReportMetadata:
        """
        Generate a risk report.
        
        Args:
            trades: List of trade dictionaries
            portfolio_snapshots: List of portfolio snapshots
            period_start: Start of reporting period
            period_end: End of reporting period
            output_format: Output format
            title: Report title
            tags: Tags for the report
            
        Returns:
            ReportMetadata of the generated report
        """
        with self._lock:
            if period_start is None and trades:
                period_start = datetime.fromisoformat(min(t["timestamp"] for t in trades))
            if period_end is None and trades:
                period_end = datetime.fromisoformat(max(t["timestamp"] for t in trades))
            if period_start is None:
                period_start = datetime.utcnow() - timedelta(days=30)
            if period_end is None:
                period_end = datetime.utcnow()
            
            # Calculate risk metrics
            risk_metrics = self._calculate_risk_metrics(trades, portfolio_snapshots)
            
            # Generate charts
            charts = {}
            if self.config.enable_charts:
                charts = self._generate_risk_charts(trades, portfolio_snapshots, risk_metrics)
            
            # Prepare report data
            report_data = {
                "title": title,
                "report_id": str(uuid4()),
                "generated_at": datetime.utcnow().isoformat(),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "version": "3.0.0",
                "tags": tags or [],
                **risk_metrics.to_dict(),
                **charts,
            }
            
            # Generate the report
            format = output_format or self.config.default_format
            file_path = self._render_report(
                report_type=ReportType.RISK,
                report_data=report_data,
                output_format=format,
                template_name="risk_report.html",
            )
            
            # Save metadata
            metadata = ReportMetadata(
                report_type=ReportType.RISK,
                title=title,
                description=f"Risk report from {period_start.date()} to {period_end.date()}",
                period_start=period_start,
                period_end=period_end,
                format=format,
                status=ReportStatus.COMPLETED,
                file_path=str(file_path),
                size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                tags=tags or [],
                metadata={"trades_count": len(trades), **risk_metrics.to_dict()},
            )
            
            self._save_metadata(metadata)
            
            logger.info(
                "risk_report_generated",
                report_id=metadata.report_id,
                file_path=str(file_path),
                format=format.value,
            )
            
            return metadata
    
    def generate_trading_report(
        self,
        trades: List[Dict[str, Any]],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        output_format: Optional[ReportFormat] = None,
        title: str = "Trading Report",
        tags: Optional[List[str]] = None,
    ) -> ReportMetadata:
        """
        Generate a trading summary report.
        
        Args:
            trades: List of trade dictionaries
            period_start: Start of reporting period
            period_end: End of reporting period
            output_format: Output format
            title: Report title
            tags: Tags for the report
            
        Returns:
            ReportMetadata of the generated report
        """
        with self._lock:
            if period_start is None and trades:
                period_start = datetime.fromisoformat(min(t["timestamp"] for t in trades))
            if period_end is None and trades:
                period_end = datetime.fromisoformat(max(t["timestamp"] for t in trades))
            if period_start is None:
                period_start = datetime.utcnow() - timedelta(days=30)
            if period_end is None:
                period_end = datetime.utcnow()
            
            # Calculate trading metrics
            trade_summary = self._calculate_trade_summary(trades)
            
            # Prepare report data
            report_data = {
                "title": title,
                "report_id": str(uuid4()),
                "generated_at": datetime.utcnow().isoformat(),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "version": "3.0.0",
                "tags": tags or [],
                **trade_summary.to_dict(),
            }
            
            # Generate the report
            format = output_format or self.config.default_format
            file_path = self._render_report(
                report_type=ReportType.TRADING,
                report_data=report_data,
                output_format=format,
                template_name="trading_report.html",
            )
            
            # Save metadata
            metadata = ReportMetadata(
                report_type=ReportType.TRADING,
                title=title,
                description=f"Trading report from {period_start.date()} to {period_end.date()}",
                period_start=period_start,
                period_end=period_end,
                format=format,
                status=ReportStatus.COMPLETED,
                file_path=str(file_path),
                size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                tags=tags or [],
                metadata={"trades_count": len(trades), **trade_summary.to_dict()},
            )
            
            self._save_metadata(metadata)
            
            logger.info(
                "trading_report_generated",
                report_id=metadata.report_id,
                file_path=str(file_path),
                format=format.value,
                trades=len(trades),
            )
            
            return metadata
    
    def generate_portfolio_report(
        self,
        portfolio_snapshots: List[Dict[str, Any]],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        output_format: Optional[ReportFormat] = None,
        title: str = "Portfolio Report",
        tags: Optional[List[str]] = None,
    ) -> ReportMetadata:
        """
        Generate a portfolio report.
        
        Args:
            portfolio_snapshots: List of portfolio snapshots
            period_start: Start of reporting period
            period_end: End of reporting period
            output_format: Output format
            title: Report title
            tags: Tags for the report
            
        Returns:
            ReportMetadata of the generated report
        """
        with self._lock:
            if period_start is None and portfolio_snapshots:
                period_start = datetime.fromisoformat(min(s["timestamp"] for s in portfolio_snapshots))
            if period_end is None and portfolio_snapshots:
                period_end = datetime.fromisoformat(max(s["timestamp"] for s in portfolio_snapshots))
            if period_start is None:
                period_start = datetime.utcnow() - timedelta(days=30)
            if period_end is None:
                period_end = datetime.utcnow()
            
            # Get latest snapshot
            latest = portfolio_snapshots[-1] if portfolio_snapshots else {}
            
            # Prepare report data
            report_data = {
                "title": title,
                "report_id": str(uuid4()),
                "generated_at": datetime.utcnow().isoformat(),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "version": "3.0.0",
                "tags": tags or [],
                "total_value": latest.get("total_value", 0),
                "cash_balance": latest.get("cash_balance", 0),
                "invested_value": latest.get("invested_value", 0),
                "positions": latest.get("positions", []),
                "allocations": latest.get("allocations", {}),
                "unrealized_pnl": latest.get("unrealized_pnl", 0),
                "realized_pnl": latest.get("realized_pnl", 0),
                "total_pnl": latest.get("total_pnl", 0),
                "daily_pnl": latest.get("daily_pnl", 0),
                "weekly_pnl": latest.get("weekly_pnl", 0),
                "monthly_pnl": latest.get("monthly_pnl", 0),
                "num_positions": latest.get("num_positions", 0),
                "concentration_ratio": latest.get("concentration_ratio", 0),
            }
            
            # Generate the report
            format = output_format or self.config.default_format
            file_path = self._render_report(
                report_type=ReportType.PORTFOLIO,
                report_data=report_data,
                output_format=format,
                template_name="portfolio_report.html",
            )
            
            # Save metadata
            metadata = ReportMetadata(
                report_type=ReportType.PORTFOLIO,
                title=title,
                description=f"Portfolio report from {period_start.date()} to {period_end.date()}",
                period_start=period_start,
                period_end=period_end,
                format=format,
                status=ReportStatus.COMPLETED,
                file_path=str(file_path),
                size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                tags=tags or [],
                metadata={"snapshots_count": len(portfolio_snapshots), **report_data},
            )
            
            self._save_metadata(metadata)
            
            logger.info(
                "portfolio_report_generated",
                report_id=metadata.report_id,
                file_path=str(file_path),
                format=format.value,
            )
            
            return metadata
    
    def generate_daily_report(self) -> Optional[ReportMetadata]:
        """
        Generate a daily report.
        
        Returns:
            ReportMetadata of the generated report
        """
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=1)
        
        # Get data from data store
        trades = []
        portfolio_snapshots = []
        
        if self.data_store:
            try:
                trades = self.data_store.get_trades(period_start, period_end)
                portfolio_snapshots = self.data_store.get_portfolio_snapshots(period_start, period_end)
            except Exception as e:
                logger.error("failed_to_get_data", error=str(e))
                return None
        
        if not trades and not portfolio_snapshots:
            logger.info("no_data_for_daily_report")
            return None
        
        # Generate component reports
        metadata = None
        
        if trades:
            # Generate performance report
            metadata = self.generate_performance_report(
                trades=trades,
                period_start=period_start,
                period_end=period_end,
                title=f"Daily Performance Report - {period_start.date()}",
                tags=["daily", "performance"],
            )
        
        if portfolio_snapshots:
            # Generate portfolio report
            metadata = self.generate_portfolio_report(
                portfolio_snapshots=portfolio_snapshots,
                period_start=period_start,
                period_end=period_end,
                title=f"Daily Portfolio Report - {period_start.date()}",
                tags=["daily", "portfolio"],
            )
        
        return metadata
    
    def _calculate_performance_metrics(self, trades: List[Dict[str, Any]]) -> PerformanceMetrics:
        """Calculate performance metrics from trades."""
        if not trades:
            return PerformanceMetrics()
        
        try:
            # Convert to DataFrame for easier calculation
            df = pd.DataFrame(trades)
            
            # Ensure timestamp is datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
            
            # Calculate returns
            df["pnl"] = df.get("pnl", 0)
            df["return_pct"] = df.get("return_pct", 0)
            
            total_pnl = df["pnl"].sum()
            total_return = df["return_pct"].sum() if len(df) > 0 else 0
            
            # Daily returns (resample)
            daily_pnl = df.set_index("timestamp").resample("D")["pnl"].sum()
            daily_returns = daily_pnl.values.tolist() if len(daily_pnl) > 0 else [0]
            
            # Volatility (annualized)
            volatility = daily_pnl.std() * np.sqrt(252) if len(daily_pnl) > 1 else 0
            
            # Sharpe ratio (assuming 0% risk-free rate)
            sharpe = (daily_pnl.mean() / (daily_pnl.std() + 1e-10)) * np.sqrt(252) if len(daily_pnl) > 1 else 0
            
            # Sortino ratio
            downside = daily_pnl[daily_pnl < 0] if len(daily_pnl) > 0 else pd.Series([0])
            downside_std = downside.std() if len(downside) > 0 else 0
            sortino = (daily_pnl.mean() / (downside_std + 1e-10)) * np.sqrt(252) if downside_std > 0 else 0
            
            # Max drawdown
            cumulative = daily_pnl.cumsum()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / (running_max.abs() + 1e-10)
            max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
            
            # Calmar ratio
            calmar = (daily_pnl.mean() * 252) / (max_drawdown + 1e-10) if max_drawdown > 0 else 0
            
            # Win rate
            winning_trades = df[df["pnl"] > 0] if len(df) > 0 else pd.DataFrame()
            losing_trades = df[df["pnl"] < 0] if len(df) > 0 else pd.DataFrame()
            win_rate = len(winning_trades) / len(df) * 100 if len(df) > 0 else 0
            
            # Profit factor
            gross_profit = winning_trades["pnl"].sum() if len(winning_trades) > 0 else 0
            gross_loss = abs(losing_trades["pnl"].sum()) if len(losing_trades) > 0 else 0
            profit_factor = gross_profit / (gross_loss + 1e-10) if gross_loss > 0 else 0
            
            # Average trade
            avg_trade = df["pnl"].mean() if len(df) > 0 else 0
            avg_win = winning_trades["pnl"].mean() if len(winning_trades) > 0 else 0
            avg_loss = losing_trades["pnl"].mean() if len(losing_trades) > 0 else 0
            
            # Largest win/loss
            largest_win = winning_trades["pnl"].max() if len(winning_trades) > 0 else 0
            largest_loss = losing_trades["pnl"].min() if len(losing_trades) > 0 else 0
            
            # Consecutive wins/losses
            win_loss = df["pnl"].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
            max_consecutive_wins = 0
            max_consecutive_losses = 0
            current_wins = 0
            current_losses = 0
            
            for val in win_loss:
                if val > 0:
                    current_wins += 1
                    current_losses = 0
                    max_consecutive_wins = max(max_consecutive_wins, current_wins)
                elif val < 0:
                    current_losses += 1
                    current_wins = 0
                    max_consecutive_losses = max(max_consecutive_losses, current_losses)
                else:
                    current_wins = 0
                    current_losses = 0
            
            # Recovery factor
            recovery_factor = total_pnl / (max_drawdown * 100 + 1e-10) if max_drawdown > 0 else 0
            
            # Ulcer index
            if len(cumulative) > 0:
                ulcer = np.sqrt(((drawdown ** 2).sum()) / len(drawdown)) if len(drawdown) > 0 else 0
            else:
                ulcer = 0
            
            return PerformanceMetrics(
                total_pnl=float(total_pnl),
                total_return=float(total_return),
                daily_returns=daily_returns,
                volatility=float(volatility),
                sharpe_ratio=float(sharpe),
                sortino_ratio=float(sortino),
                calmar_ratio=float(calmar),
                max_drawdown=float(max_drawdown * 100),
                max_drawdown_duration_days=0,  # Not implemented
                win_rate=float(win_rate),
                profit_factor=float(profit_factor),
                avg_trade_pnl=float(avg_trade),
                avg_win=float(avg_win),
                avg_loss=float(avg_loss),
                total_trades=int(len(df)),
                winning_trades=int(len(winning_trades)),
                losing_trades=int(len(losing_trades)),
                largest_win=float(largest_win),
                largest_loss=float(largest_loss),
                num_consecutive_wins=int(max_consecutive_wins),
                num_consecutive_losses=int(max_consecutive_losses),
                recovery_factor=float(recovery_factor),
                ulcer_index=float(ulcer),
            )
        except Exception as e:
            logger.error("failed_to_calculate_performance_metrics", error=str(e), traceback=traceback.format_exc())
            return PerformanceMetrics()
    
    def _calculate_risk_metrics(
        self,
        trades: List[Dict[str, Any]],
        portfolio_snapshots: List[Dict[str, Any]],
    ) -> RiskMetrics:
        """Calculate risk metrics from trades and portfolio snapshots."""
        risk_metrics = RiskMetrics()
        
        try:
            if trades:
                df = pd.DataFrame(trades)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df["pnl"] = df.get("pnl", 0)
                
                # VaR calculations
                pnl_values = df["pnl"].values
                var_95 = np.percentile(pnl_values, 5)
                var_99 = np.percentile(pnl_values, 1)
                
                # CVaR
                cvar_95 = pnl_values[pnl_values <= var_95].mean() if len(pnl_values[pnl_values <= var_95]) > 0 else var_95
                cvar_99 = pnl_values[pnl_values <= var_99].mean() if len(pnl_values[pnl_values <= var_99]) > 0 else var_99
                
                # Expected shortfall
                expected_shortfall = cvar_95
                
                # Downside and upside deviation
                negative_returns = pnl_values[pnl_values < 0]
                positive_returns = pnl_values[pnl_values > 0]
                downside_deviation = np.std(negative_returns) if len(negative_returns) > 1 else 0
                upside_deviation = np.std(positive_returns) if len(positive_returns) > 1 else 0
                
                # Tail ratio
                p95 = np.percentile(pnl_values, 95)
                p5 = np.percentile(pnl_values, 5)
                tail_ratio = abs(p95 / p5) if abs(p5) > 1e-10 else 0
                
                # Pain index
                cumulative = df["pnl"].cumsum()
                running_max = cumulative.expanding().max()
                drawdown = (cumulative - running_max) / (running_max.abs() + 1e-10)
                pain_index = abs(drawdown.mean()) if len(drawdown) > 0 else 0
                
                risk_metrics.var_95 = float(abs(var_95))
                risk_metrics.var_99 = float(abs(var_99))
                risk_metrics.cvar_95 = float(abs(cvar_95))
                risk_metrics.cvar_99 = float(abs(cvar_99))
                risk_metrics.expected_shortfall = float(abs(expected_shortfall))
                risk_metrics.downside_deviation = float(downside_deviation)
                risk_metrics.upside_deviation = float(upside_deviation)
                risk_metrics.tail_ratio = float(tail_ratio)
                risk_metrics.pain_index = float(pain_index)
            
            if portfolio_snapshots:
                latest = portfolio_snapshots[-1] if portfolio_snapshots else {}
                risk_metrics.current_exposure = latest.get("invested_value", 0)
                risk_metrics.current_leverage = latest.get("leverage", 1.0)
                risk_metrics.beta_to_market = latest.get("beta_to_market", 1.0)
                risk_metrics.alpha = latest.get("alpha", 0)
                risk_metrics.correlation_matrix = latest.get("correlation_matrix", {})
            
            # Stress test results (simplified)
            risk_metrics.stress_test_results = {
                "market_crash": -0.15,
                "flash_crash": -0.30,
                "black_swan": -0.50,
                "volatility_spike": -0.10,
                "liquidity_crisis": -0.20,
            }
            
        except Exception as e:
            logger.error("failed_to_calculate_risk_metrics", error=str(e))
        
        return risk_metrics
    
    def _calculate_trade_summary(self, trades: List[Dict[str, Any]]) -> TradeSummary:
        """Calculate trade summary metrics."""
        if not trades:
            return TradeSummary()
        
        try:
            df = pd.DataFrame(trades)
            
            total_trades = len(df)
            successful_trades = len(df[df.get("status", "") == "filled"]) if "status" in df else total_trades
            failed_trades = total_trades - successful_trades
            
            total_volume = df.get("volume", df.get("size", 0)).sum()
            total_fees = df.get("fee", 0).sum()
            total_slippage = df.get("slippage", 0).sum()
            
            avg_execution_time = df.get("execution_time_ms", 0).mean() if "execution_time_ms" in df else 0
            avg_order_size = df.get("size", 0).mean() if "size" in df else 0
            avg_spread = df.get("spread_bps", 0).mean() if "spread_bps" in df else 0
            
            # Categorize trades
            trades_by_symbol = {}
            trades_by_strategy = {}
            trades_by_broker = {}
            order_type_distribution = {}
            
            if "symbol" in df:
                trades_by_symbol = df["symbol"].value_counts().to_dict()
            if "strategy" in df:
                trades_by_strategy = df["strategy"].value_counts().to_dict()
            if "broker" in df:
                trades_by_broker = df["broker"].value_counts().to_dict()
            if "order_type" in df:
                order_type_distribution = df["order_type"].value_counts().to_dict()
            
            # Time in market (simplified)
            time_in_market = 0
            
            return TradeSummary(
                total_trades=total_trades,
                successful_trades=successful_trades,
                failed_trades=failed_trades,
                total_volume=float(total_volume),
                total_fees=float(total_fees),
                total_slippage=float(total_slippage),
                avg_execution_time_ms=float(avg_execution_time),
                avg_order_size=float(avg_order_size),
                avg_spread=float(avg_spread),
                trades_by_symbol={k: int(v) for k, v in trades_by_symbol.items()},
                trades_by_strategy={k: int(v) for k, v in trades_by_strategy.items()},
                trades_by_broker={k: int(v) for k, v in trades_by_broker.items()},
                order_type_distribution={k: int(v) for k, v in order_type_distribution.items()},
                time_in_market_pct=time_in_market,
            )
        except Exception as e:
            logger.error("failed_to_calculate_trade_summary", error=str(e))
            return TradeSummary()
    
    def _generate_performance_charts(
        self,
        trades: List[Dict[str, Any]],
        metrics: PerformanceMetrics,
    ) -> Dict[str, str]:
        """Generate performance charts as base64-encoded images."""
        charts = {}
        
        if not trades:
            return charts
        
        try:
            df = pd.DataFrame(trades)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
            
            # Equity curve
            fig, ax = plt.subplots(figsize=(12, 6))
            cumulative_pnl = df["pnl"].cumsum() if "pnl" in df else pd.Series([0] * len(df))
            ax.plot(df["timestamp"], cumulative_pnl, color="#00d4ff", linewidth=2)
            ax.set_title("Equity Curve", color="#00d4ff")
            ax.set_xlabel("Date")
            ax.set_ylabel("Cumulative PnL ($)")
            ax.grid(True, alpha=0.2)
            ax.tick_params(colors="#8899aa")
            fig.patch.set_facecolor("#0a0e17")
            ax.set_facecolor("#141b2d")
            for spine in ax.spines.values():
                spine.set_color("#1a2332")
            plt.tight_layout()
            
            # Convert to base64
            import base64
            from io import BytesIO
            buf = BytesIO()
            fig.savefig(buf, format=self.config.chart_format, dpi=self.config.chart_dpi, bbox_inches="tight")
            buf.seek(0)
            charts["equity_curve"] = base64.b64encode(buf.read()).decode("utf-8")
            plt.close(fig)
            
            # Drawdown chart
            fig, ax = plt.subplots(figsize=(12, 6))
            cumulative = df["pnl"].cumsum() if "pnl" in df else pd.Series([0] * len(df))
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / (running_max.abs() + 1e-10) * 100
            
            ax.fill_between(df["timestamp"], 0, drawdown, color="#ff4466", alpha=0.5)
            ax.plot(df["timestamp"], drawdown, color="#ff4466", linewidth=1)
            ax.set_title("Drawdown", color="#ff4466")
            ax.set_xlabel("Date")
            ax.set_ylabel("Drawdown (%)")
            ax.grid(True, alpha=0.2)
            ax.tick_params(colors="#8899aa")
            fig.patch.set_facecolor("#0a0e17")
            ax.set_facecolor("#141b2d")
            for spine in ax.spines.values():
                spine.set_color("#1a2332")
            plt.tight_layout()
            
            buf = BytesIO()
            fig.savefig(buf, format=self.config.chart_format, dpi=self.config.chart_dpi, bbox_inches="tight")
            buf.seek(0)
            charts["drawdown_chart"] = base64.b64encode(buf.read()).decode("utf-8")
            plt.close(fig)
            
        except Exception as e:
            logger.error("failed_to_generate_performance_charts", error=str(e))
        
        return charts
    
    def _generate_risk_charts(
        self,
        trades: List[Dict[str, Any]],
        portfolio_snapshots: List[Dict[str, Any]],
        risk_metrics: RiskMetrics,
    ) -> Dict[str, str]:
        """Generate risk charts as base64-encoded images."""
        charts = {}
        
        try:
            import base64
            from io import BytesIO
            
            # VaR analysis chart
            if trades:
                df = pd.DataFrame(trades)
                df["pnl"] = df.get("pnl", 0)
                
                fig, ax = plt.subplots(figsize=(12, 6))
                n, bins, patches = ax.hist(df["pnl"], bins=50, color="#00d4ff", alpha=0.7, edgecolor="#1a2332")
                
                # Add VaR lines
                var_95 = -risk_metrics.var_95
                var_99 = -risk_metrics.var_99
                ax.axvline(var_95, color="#ffaa00", linestyle="--", linewidth=2, label=f"VaR 95%: {risk_metrics.var_95:.2f}")
                ax.axvline(var_99, color="#ff4466", linestyle="--", linewidth=2, label=f"VaR 99%: {risk_metrics.var_99:.2f}")
                
                ax.set_title("PnL Distribution with VaR", color="#00d4ff")
                ax.set_xlabel("PnL ($)")
                ax.set_ylabel("Frequency")
                ax.legend()
                ax.grid(True, alpha=0.2)
                ax.tick_params(colors="#8899aa")
                fig.patch.set_facecolor("#0a0e17")
                ax.set_facecolor("#141b2d")
                for spine in ax.spines.values():
                    spine.set_color("#1a2332")
                plt.tight_layout()
                
                buf = BytesIO()
                fig.savefig(buf, format=self.config.chart_format, dpi=self.config.chart_dpi, bbox_inches="tight")
                buf.seek(0)
                charts["var_chart"] = base64.b64encode(buf.read()).decode("utf-8")
                plt.close(fig)
            
            # Stress test chart
            if risk_metrics.stress_test_results:
                fig, ax = plt.subplots(figsize=(12, 6))
                scenarios = list(risk_metrics.stress_test_results.keys())
                values = list(risk_metrics.stress_test_results.values())
                colors = ["#ff4466" if v < 0 else "#00ff88" for v in values]
                
                bars = ax.bar(scenarios, values, color=colors, alpha=0.7)
                ax.set_title("Stress Test Results", color="#00d4ff")
                ax.set_xlabel("Scenario")
                ax.set_ylabel("Portfolio Impact (%)")
                ax.axhline(0, color="#8899aa", linewidth=0.5)
                ax.grid(True, alpha=0.2, axis="y")
                ax.tick_params(colors="#8899aa")
                fig.patch.set_facecolor("#0a0e17")
                ax.set_facecolor("#141b2d")
                for spine in ax.spines.values():
                    spine.set_color("#1a2332")
                plt.xticks(rotation=45, ha="right")
                plt.tight_layout()
                
                buf = BytesIO()
                fig.savefig(buf, format=self.config.chart_format, dpi=self.config.chart_dpi, bbox_inches="tight")
                buf.seek(0)
                charts["stress_test_chart"] = base64.b64encode(buf.read()).decode("utf-8")
                plt.close(fig)
            
        except Exception as e:
            logger.error("failed_to_generate_risk_charts", error=str(e))
        
        return charts
    
    def _render_report(
        self,
        report_type: ReportType,
        report_data: Dict[str, Any],
        output_format: ReportFormat,
        template_name: str,
    ) -> Path:
        """Render the report in the specified format."""
        try:
            if output_format == ReportFormat.HTML:
                return self._render_html_report(report_data, template_name)
            elif output_format == ReportFormat.JSON:
                return self._render_json_report(report_data)
            elif output_format == ReportFormat.CSV:
                return self._render_csv_report(report_data)
            elif output_format == ReportFormat.MARKDOWN:
                return self._render_markdown_report(report_data)
            elif output_format == ReportFormat.YAML:
                return self._render_yaml_report(report_data)
            elif output_format == ReportFormat.PICKLE:
                return self._render_pickle_report(report_data)
            else:
                raise ValueError(f"Unsupported output format: {output_format}")
        except Exception as e:
            logger.error("failed_to_render_report", error=str(e), traceback=traceback.format_exc())
            raise ReportGenerationError(f"Failed to render report: {e}")
    
    def _render_html_report(self, report_data: Dict[str, Any], template_name: str) -> Path:
        """Render HTML report using Jinja2 template."""
        try:
            template = self._template_env.get_template(template_name)
            html_content = template.render(**report_data)
            
            # Create output path
            filename = f"report_{report_data['report_id']}.html"
            file_path = self.reports_dir / filename
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            return file_path
        except Exception as e:
            logger.error("failed_to_render_html", error=str(e))
            raise
    
    def _render_json_report(self, report_data: Dict[str, Any]) -> Path:
        """Render JSON report."""
        filename = f"report_{report_data['report_id']}.json"
        file_path = self.reports_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return file_path
    
    def _render_csv_report(self, report_data: Dict[str, Any]) -> Path:
        """Render CSV report."""
        filename = f"report_{report_data['report_id']}.csv"
        file_path = self.reports_dir / filename
        
        # Flatten the data
        flat_data = {}
        for key, value in report_data.items():
            if not isinstance(value, (dict, list)):
                flat_data[key] = value
        
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value"])
            for key, value in flat_data.items():
                writer.writerow([key, str(value)])
        
        return file_path
    
    def _render_markdown_report(self, report_data: Dict[str, Any]) -> Path:
        """Render Markdown report."""
        filename = f"report_{report_data['report_id']}.md"
        file_path = self.reports_dir / filename
        
        lines = []
        lines.append(f"# {report_data.get('title', 'NEXUS Hedge Bot Report')}")
        lines.append("")
        lines.append(f"**Report ID:** {report_data.get('report_id', 'N/A')}")
        lines.append(f"**Generated:** {report_data.get('generated_at', 'N/A')}")
        lines.append(f"**Period:** {report_data.get('period_start', 'N/A')} to {report_data.get('period_end', 'N/A')}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        
        # Add metrics
        for key, value in report_data.items():
            if not isinstance(value, (dict, list)):
                lines.append(f"- **{key}:** {value}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*Generated by NEXUS QUANTUM LTD - AI Trading System v3.0*")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return file_path
    
    def _render_yaml_report(self, report_data: Dict[str, Any]) -> Path:
        """Render YAML report."""
        filename = f"report_{report_data['report_id']}.yaml"
        file_path = self.reports_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(report_data, f, default_flow_style=False)
        
        return file_path
    
    def _render_pickle_report(self, report_data: Dict[str, Any]) -> Path:
        """Render Pickle report."""
        filename = f"report_{report_data['report_id']}.pkl"
        file_path = self.reports_dir / filename
        
        with open(file_path, "wb") as f:
            pickle.dump(report_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        return file_path
    
    def _save_metadata(self, metadata: ReportMetadata) -> None:
        """Save report metadata to the database."""
        with self._lock:
            self._db.execute("""
                INSERT OR REPLACE INTO reports (
                    report_id, report_type, title, description, created_at, generated_at,
                    period_start, period_end, format, status, file_path, size_bytes, tags, metadata, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.report_id,
                metadata.report_type.value,
                metadata.title,
                metadata.description,
                metadata.created_at.isoformat(),
                metadata.generated_at.isoformat(),
                metadata.period_start.isoformat() if metadata.period_start else None,
                metadata.period_end.isoformat() if metadata.period_end else None,
                metadata.format.value,
                metadata.status.value,
                metadata.file_path,
                metadata.size_bytes,
                json.dumps(metadata.tags),
                json.dumps(metadata.metadata),
                metadata.version,
            ))
    
    def get_report(self, report_id: str) -> Optional[ReportMetadata]:
        """Get report metadata by ID."""
        cursor = self._db.execute(
            "SELECT * FROM reports WHERE report_id = ?",
            (report_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        data["tags"] = json.loads(data["tags"]) if data.get("tags") else []
        data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
        
        return ReportMetadata.from_dict(data)
    
    def list_reports(
        self,
        report_type: Optional[ReportType] = None,
        status: Optional[ReportStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ReportMetadata]:
        """List reports with optional filtering."""
        sql = "SELECT * FROM reports WHERE 1=1"
        params = []
        
        if report_type:
            sql += " AND report_type = ?"
            params.append(report_type.value)
        
        if status:
            sql += " AND status = ?"
            params.append(status.value)
        
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        
        for row in rows:
            data = dict(zip(columns, row))
            data["tags"] = json.loads(data["tags"]) if data.get("tags") else []
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            results.append(ReportMetadata.from_dict(data))
        
        return results
    
    def delete_report(self, report_id: str) -> bool:
        """Delete a report."""
        with self._lock:
            # Get file path
            cursor = self._db.execute(
                "SELECT file_path FROM reports WHERE report_id = ?",
                (report_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return False
            
            file_path = row[0]
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning("failed_to_delete_report_file", file_path=file_path, error=str(e))
            
            self._db.execute("DELETE FROM reports WHERE report_id = ?", (report_id,))
            return True
    
    def close(self) -> None:
        """Close the report manager."""
        if self._closed:
            return
        
        self._closed = True
        
        if hasattr(self, "_db") and self._db:
            self._db.close()
        
        self._executor.shutdown(wait=True)
        
        logger.info("report_manager_closed")
    
    def __enter__(self) -> "ReportManager":
        return self
    
    def __exit__(self, *args) -> None:
        self.close()


# === MODULE EXPORTS ===

__all__ = [
    # Main classes
    "ReportManager",
    "ReportConfig",
    "ReportMetadata",
    "PerformanceMetrics",
    "RiskMetrics",
    "TradeSummary",
    "PortfolioSnapshot",
    
    # Enums
    "ReportType",
    "ReportFormat",
    "ReportStatus",
    "MetricType",
    
    # Exceptions
    "ReportError",
    "ReportGenerationError",
    "ReportNotFoundError",
]

logger.info("reports_module_loaded", version="3.0.0")

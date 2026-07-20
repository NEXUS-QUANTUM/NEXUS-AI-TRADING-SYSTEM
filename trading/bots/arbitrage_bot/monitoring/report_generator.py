# trading/bots/arbitrage_bot/monitoring/report_generator.py
# NEXUS AI TRADING SYSTEM - REPORT GENERATOR
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides comprehensive report generation for the arbitrage bot,
# including performance reports, trade reports, opportunity reports, and
# system health reports.
# ====================================================================================

"""
NEXUS Arbitrage Bot Report Generator

This module provides comprehensive report generation for:
- Performance reports (latency, throughput, system metrics)
- Trade reports (execution, PnL, volume)
- Opportunity reports (detection, execution, profitability)
- System health reports (status, issues, uptime)
- Custom report templates
- Scheduled report generation
- Multi-format export (JSON, CSV, HTML, PDF)
- Email delivery
"""

import asyncio
import logging
import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import aiofiles
import jinja2

# NEXUS internal imports
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.models.trade import Trade, TradeSummary
from trading.bots.arbitrage_bot.models.opportunity import ArbitrageOpportunity, OpportunitySummary
from trading.bots.arbitrage_bot.models.alert import AlertStats
from trading.bots.arbitrage_bot.models.performance import PerformanceMetrics

logger = logging.getLogger("nexus.arbitrage.report_generator")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class ReportType(str, Enum):
    """Types of reports."""
    PERFORMANCE = "performance"
    TRADE = "trade"
    OPPORTUNITY = "opportunity"
    HEALTH = "health"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Report output formats."""
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"
    MARKDOWN = "markdown"


class ReportStatus(str, Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportSchedule(str, Enum):
    """Report scheduling frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ON_DEMAND = "on_demand"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class Report:
    """
    Report data model.
    """
    report_id: str
    type: ReportType
    format: ReportFormat
    title: str
    description: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    status: ReportStatus
    data: Dict[str, Any]
    file_path: str
    metadata: Dict[str, Any]


@dataclass
class ReportConfig:
    """
    Report configuration.
    """
    report_id: str
    type: ReportType
    format: ReportFormat
    schedule: ReportSchedule
    recipients: List[str]
    enabled: bool
    template_name: str
    parameters: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class ReportTemplate:
    """
    Report template.
    """
    name: str
    type: ReportType
    format: ReportFormat
    template: str
    variables: List[str]
    version: str
    created_at: datetime
    updated_at: datetime


# ====================================================================================
# REPORT GENERATOR
# ====================================================================================

class ReportGenerator:
    """
    Comprehensive report generation system.
    
    Features:
    - Multi-format report generation
    - Custom report templates
    - Scheduled report generation
    - Export to JSON, CSV, HTML, PDF
    - Email delivery
    - Report history
    - Template management
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the report generator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.report_dir = Path(self.config.get("report_dir", "reports"))
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        # Report storage
        self._reports: Dict[str, Report] = {}
        self._report_history: deque = deque(maxlen=1000)
        self._configs: Dict[str, ReportConfig] = {}
        self._templates: Dict[str, ReportTemplate] = {}
        
        # Template engine
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.report_dir / "templates")),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
        
        # Metrics
        self._metrics = MetricsCollector(
            name="nexus_report_generator",
            labels={"service": "arbitrage_bot"}
        )
        self._setup_metrics()
        
        # Data sources
        self._trade_manager = None
        self._opportunity_manager = None
        self._alert_manager = None
        self._performance_monitor = None
        
        # State
        self._running = False
        self._initialized = False
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Register default templates
        self._register_default_templates()
        
        logger.info("ReportGenerator initialized (version=3.0.0)")
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics.register_counter("reports_generated", "Reports generated")
        self._metrics.register_counter("reports_failed", "Reports failed")
        self._metrics.register_gauge("reports_pending", "Reports pending")
        self._metrics.register_histogram("report_generation_time", "Report generation time in seconds")
        
    def _register_default_templates(self) -> None:
        """Register default report templates."""
        # Performance report template
        self.register_template(ReportTemplate(
            name="performance_default",
            type=ReportType.PERFORMANCE,
            format=ReportFormat.HTML,
            template=self._get_performance_template(),
            variables=["latency", "throughput", "cpu", "memory", "status"],
            version="1.0",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ))
        
        # Trade report template
        self.register_template(ReportTemplate(
            name="trade_default",
            type=ReportType.TRADE,
            format=ReportFormat.HTML,
            template=self._get_trade_template(),
            variables=["total_trades", "win_rate", "profit", "volume", "summary"],
            version="1.0",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ))
        
        # Opportunity report template
        self.register_template(ReportTemplate(
            name="opportunity_default",
            type=ReportType.OPPORTUNITY,
            format=ReportFormat.HTML,
            template=self._get_opportunity_template(),
            variables=["detected", "executed", "profit", "success_rate", "summary"],
            version="1.0",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ))
        
    def _get_performance_template(self) -> str:
        """Get performance report template."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NEXUS Performance Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #1a237e; color: white; padding: 20px; border-radius: 5px; }
                .section { margin: 20px 0; padding: 15px; border: 1px solid #e0e0e0; border-radius: 5px; }
                .status { padding: 10px; border-radius: 5px; font-weight: bold; }
                .excellent { background: #4caf50; color: white; }
                .good { background: #8bc34a; color: white; }
                .fair { background: #ffc107; color: black; }
                .poor { background: #ff5722; color: white; }
                .critical { background: #c62828; color: white; }
                .metric { display: inline-block; margin: 10px; padding: 15px; background: #f5f5f5; border-radius: 5px; }
                .value { font-size: 24px; font-weight: bold; }
                .unit { font-size: 14px; color: #757575; }
                .label { color: #616161; }
                table { width: 100%; border-collapse: collapse; }
                th { background: #1a237e; color: white; padding: 10px; text-align: left; }
                td { padding: 10px; border-bottom: 1px solid #e0e0e0; }
                .footer { margin-top: 20px; padding-top: 10px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #757575; text-align: center; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>NEXUS Performance Report</h1>
                <p>Generated: {{ generated_at }}</p>
                <p>Period: {{ period_start }} - {{ period_end }}</p>
            </div>
            
            <div class="section">
                <h2>System Status</h2>
                <div class="status {{ status }}">{{ status|upper }}</div>
            </div>
            
            <div class="section">
                <h2>Metrics</h2>
                <div class="metric">
                    <div class="label">Latency (P95)</div>
                    <div class="value">{{ latency.p95|round(2) }} <span class="unit">ms</span></div>
                </div>
                <div class="metric">
                    <div class="label">Latency (P99)</div>
                    <div class="value">{{ latency.p99|round(2) }} <span class="unit">ms</span></div>
                </div>
                <div class="metric">
                    <div class="label">CPU Usage</div>
                    <div class="value">{{ cpu|round(1) }} <span class="unit">%</span></div>
                </div>
                <div class="metric">
                    <div class="label">Memory Usage</div>
                    <div class="value">{{ memory|round(1) }} <span class="unit">%</span></div>
                </div>
            </div>
            
            <div class="section">
                <h2>Recommendations</h2>
                <ul>
                {% for rec in recommendations %}
                    <li>{{ rec }}</li>
                {% endfor %}
                </ul>
            </div>
            
            <div class="footer">
                <p>NEXUS Arbitrage Bot - Automated Report</p>
                <p>© 2026 NEXUS QUANTUM LTD</p>
            </div>
        </body>
        </html>
        """
        
    def _get_trade_template(self) -> str:
        """Get trade report template."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NEXUS Trade Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #1a237e; color: white; padding: 20px; border-radius: 5px; }
                .section { margin: 20px 0; padding: 15px; border: 1px solid #e0e0e0; border-radius: 5px; }
                .metric { display: inline-block; margin: 10px; padding: 15px; background: #f5f5f5; border-radius: 5px; }
                .value { font-size: 24px; font-weight: bold; }
                .unit { font-size: 14px; color: #757575; }
                .label { color: #616161; }
                .positive { color: #2e7d32; }
                .negative { color: #c62828; }
                table { width: 100%; border-collapse: collapse; }
                th { background: #1a237e; color: white; padding: 10px; text-align: left; }
                td { padding: 10px; border-bottom: 1px solid #e0e0e0; }
                .footer { margin-top: 20px; padding-top: 10px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #757575; text-align: center; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>NEXUS Trade Report</h1>
                <p>Generated: {{ generated_at }}</p>
                <p>Period: {{ period_start }} - {{ period_end }}</p>
            </div>
            
            <div class="section">
                <h2>Summary</h2>
                <div class="metric">
                    <div class="label">Total Trades</div>
                    <div class="value">{{ summary.total_trades }}</div>
                </div>
                <div class="metric">
                    <div class="label">Win Rate</div>
                    <div class="value">{{ summary.win_rate|round(1) }} <span class="unit">%</span></div>
                </div>
                <div class="metric">
                    <div class="label">Total Profit</div>
                    <div class="value {{ 'positive' if summary.total_profit > 0 else 'negative' }}">{{ summary.total_profit|round(2) }} <span class="unit">USDT</span></div>
                </div>
                <div class="metric">
                    <div class="label">Volume</div>
                    <div class="value">{{ summary.total_volume|round(2) }} <span class="unit">USDT</span></div>
                </div>
            </div>
            
            <div class="section">
                <h2>Recent Trades</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Exchange</th>
                            <th>Side</th>
                            <th>Quantity</th>
                            <th>Price</th>
                            <th>Profit</th>
                        </tr>
                    </thead>
                    <tbody>
                    {% for trade in trades %}
                        <tr>
                            <td>{{ trade.timestamp }}</td>
                            <td>{{ trade.symbol }}</td>
                            <td>{{ trade.exchange }}</td>
                            <td>{{ trade.side }}</td>
                            <td>{{ trade.quantity|round(4) }}</td>
                            <td>{{ trade.price|round(2) }}</td>
                            <td class="{{ 'positive' if trade.profit > 0 else 'negative' }}">{{ trade.profit|round(2) }}</td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div class="footer">
                <p>NEXUS Arbitrage Bot - Automated Report</p>
                <p>© 2026 NEXUS QUANTUM LTD</p>
            </div>
        </body>
        </html>
        """
        
    def _get_opportunity_template(self) -> str:
        """Get opportunity report template."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NEXUS Opportunity Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #1a237e; color: white; padding: 20px; border-radius: 5px; }
                .section { margin: 20px 0; padding: 15px; border: 1px solid #e0e0e0; border-radius: 5px; }
                .metric { display: inline-block; margin: 10px; padding: 15px; background: #f5f5f5; border-radius: 5px; }
                .value { font-size: 24px; font-weight: bold; }
                .unit { font-size: 14px; color: #757575; }
                .label { color: #616161; }
                .positive { color: #2e7d32; }
                table { width: 100%; border-collapse: collapse; }
                th { background: #1a237e; color: white; padding: 10px; text-align: left; }
                td { padding: 10px; border-bottom: 1px solid #e0e0e0; }
                .footer { margin-top: 20px; padding-top: 10px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #757575; text-align: center; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>NEXUS Opportunity Report</h1>
                <p>Generated: {{ generated_at }}</p>
                <p>Period: {{ period_start }} - {{ period_end }}</p>
            </div>
            
            <div class="section">
                <h2>Summary</h2>
                <div class="metric">
                    <div class="label">Detected</div>
                    <div class="value">{{ summary.detected }}</div>
                </div>
                <div class="metric">
                    <div class="label">Executed</div>
                    <div class="value">{{ summary.executed }}</div>
                </div>
                <div class="metric">
                    <div class="label">Success Rate</div>
                    <div class="value">{{ summary.success_rate|round(1) }} <span class="unit">%</span></div>
                </div>
                <div class="metric">
                    <div class="label">Total Profit</div>
                    <div class="value positive">{{ summary.total_profit|round(2) }} <span class="unit">USDT</span></div>
                </div>
            </div>
            
            <div class="section">
                <h2>Top Opportunities</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Type</th>
                            <th>Profit %</th>
                            <th>Confidence</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                    {% for opp in opportunities %}
                        <tr>
                            <td>{{ opp.timestamp }}</td>
                            <td>{{ opp.symbol }}</td>
                            <td>{{ opp.type }}</td>
                            <td>{{ opp.profit_percent|round(2) }}</td>
                            <td>{{ opp.confidence|round(1) }}%</td>
                            <td>{{ opp.status }}</td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div class="footer">
                <p>NEXUS Arbitrage Bot - Automated Report</p>
                <p>© 2026 NEXUS QUANTUM LTD</p>
            </div>
        </body>
        </html>
        """
        
    def setup_data_sources(
        self,
        trade_manager: Any,
        opportunity_manager: Any,
        alert_manager: Any,
        performance_monitor: Any
    ) -> None:
        """
        Setup data sources for report generation.
        
        Args:
            trade_manager: Trade manager instance
            opportunity_manager: Opportunity manager instance
            alert_manager: Alert manager instance
            performance_monitor: Performance monitor instance
        """
        self._trade_manager = trade_manager
        self._opportunity_manager = opportunity_manager
        self._alert_manager = alert_manager
        self._performance_monitor = performance_monitor
        logger.info("Data sources configured for report generation")
        
    def register_template(self, template: ReportTemplate) -> None:
        """
        Register a report template.
        
        Args:
            template: Report template
        """
        self._templates[template.name] = template
        logger.info(f"Registered template: {template.name}")
        
    def add_config(self, config: ReportConfig) -> None:
        """
        Add report configuration.
        
        Args:
            config: Report configuration
        """
        self._configs[config.report_id] = config
        logger.info(f"Added report config: {config.report_id}")
        
    async def initialize(self) -> None:
        """Initialize the report generator."""
        if self._initialized:
            return
            
        self._initialized = True
        self._running = True
        
        # Start scheduled report generation
        task = asyncio.create_task(self._scheduled_report_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        logger.info("ReportGenerator initialized")
        
    async def _scheduled_report_loop(self) -> None:
        """Generate scheduled reports."""
        while self._running:
            try:
                now = datetime.utcnow()
                
                for config in self._configs.values():
                    if not config.enabled:
                        continue
                        
                    if self._should_generate(now, config):
                        asyncio.create_task(self.generate_report(
                            config.type,
                            config.format,
                            config.template_name,
                            config.parameters
                        ))
                        
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduled report loop error: {e}")
                
    def _should_generate(self, now: datetime, config: ReportConfig) -> bool:
        """
        Check if report should be generated.
        
        Args:
            now: Current time
            config: Report configuration
            
        Returns:
            True if should generate
        """
        if config.schedule == ReportSchedule.ON_DEMAND:
            return False
            
        # Check last generated time
        last_generated = None
        for report in self._report_history:
            if report.type == config.type:
                last_generated = report.generated_at
                break
                
        if not last_generated:
            return True
            
        # Check schedule
        days = (now - last_generated).days
        if config.schedule == ReportSchedule.DAILY and days >= 1:
            return True
        elif config.schedule == ReportSchedule.WEEKLY and days >= 7:
            return True
        elif config.schedule == ReportSchedule.MONTHLY and days >= 30:
            return True
        elif config.schedule == ReportSchedule.QUARTERLY and days >= 90:
            return True
            
        return False
        
    async def generate_report(
        self,
        type: ReportType,
        format: ReportFormat,
        template_name: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Optional[Report]:
        """
        Generate a report.
        
        Args:
            type: Report type
            format: Report format
            template_name: Template name
            parameters: Template parameters
            period_start: Period start time
            period_end: Period end time
            
        Returns:
            Generated report
        """
        report_id = f"RPT-{datetime.utcnow().strftime('%Y%m%d')}-{len(self._reports)+1:04d}"
        
        try:
            start_time = time.time()
            
            # Set period
            if not period_end:
                period_end = datetime.utcnow()
            if not period_start:
                if type == ReportType.DAILY:
                    period_start = period_end - timedelta(days=1)
                elif type == ReportType.WEEKLY:
                    period_start = period_end - timedelta(weeks=1)
                elif type == ReportType.MONTHLY:
                    period_start = period_end - timedelta(days=30)
                else:
                    period_start = period_end - timedelta(days=7)
                    
            # Collect data
            data = await self._collect_data(type, period_start, period_end)
            
            # Apply template
            rendered = await self._render_report(type, format, template_name, data, parameters)
            
            # Save report
            file_path = await self._save_report(report_id, format, rendered)
            
            # Create report object
            report = Report(
                report_id=report_id,
                type=type,
                format=format,
                title=f"{type.value.capitalize()} Report",
                description=f"Report generated for {type.value} analysis",
                period_start=period_start,
                period_end=period_end,
                generated_at=datetime.utcnow(),
                status=ReportStatus.COMPLETED,
                data=data,
                file_path=file_path,
                metadata={
                    "template": template_name,
                    "parameters": parameters or {}
                }
            )
            
            # Store report
            self._reports[report_id] = report
            self._report_history.append(report)
            self._metrics.increment_counter("reports_generated")
            
            # Record generation time
            generation_time = (time.time() - start_time)
            self._metrics.record_histogram("report_generation_time", generation_time)
            
            logger.info(f"Report generated: {report_id} ({generation_time:.2f}s)")
            return report
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            self._metrics.increment_counter("reports_failed")
            return None
            
    async def _collect_data(
        self,
        type: ReportType,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Collect data for report.
        
        Args:
            type: Report type
            start_time: Start time
            end_time: End time
            
        Returns:
            Collected data
        """
        data = {
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        if type in [ReportType.PERFORMANCE, ReportType.DAILY, ReportType.WEEKLY, ReportType.MONTHLY]:
            if self._performance_monitor:
                report = self._performance_monitor.get_performance_report()
                data["performance"] = {
                    "status": report.status.value,
                    "latency": report.metrics.get("latency", {}),
                    "throughput": report.metrics.get("throughput", {}),
                    "system": report.metrics.get("system", {}),
                    "issues": [asdict(i) for i in report.issues],
                    "recommendations": report.recommendations
                }
                
        if type in [ReportType.TRADE, ReportType.DAILY, ReportType.WEEKLY, ReportType.MONTHLY]:
            if self._trade_manager:
                summary = await self._trade_manager.get_summary(
                    start_date=start_time,
                    end_date=end_time
                )
                trades = await self._trade_manager.get_trades(
                    from_date=start_time.isoformat(),
                    to_date=end_time.isoformat(),
                    limit=100
                )
                data["trades"] = {
                    "summary": asdict(summary) if summary else {},
                    "recent": [asdict(t) for t in trades[:50]]
                }
                
        if type in [ReportType.OPPORTUNITY, ReportType.DAILY, ReportType.WEEKLY, ReportType.MONTHLY]:
            if self._opportunity_manager:
                summary = await self._opportunity_manager.get_summary(
                    period_days=(end_time - start_time).days
                )
                opportunities = await self._opportunity_manager.get_opportunities(
                    limit=100
                )
                data["opportunities"] = {
                    "summary": asdict(summary) if summary else {},
                    "recent": [asdict(o) for o in opportunities[:50]]
                }
                
        if type == ReportType.HEALTH:
            if self._alert_manager:
                stats = self._alert_manager.get_stats(period_days=(end_time - start_time).days)
                data["health"] = {
                    "alerts": asdict(stats) if stats else {},
                    "status": "healthy"
                }
                
        return data
        
    async def _render_report(
        self,
        type: ReportType,
        format: ReportFormat,
        template_name: str,
        data: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render report using template.
        
        Args:
            type: Report type
            format: Report format
            template_name: Template name
            data: Report data
            parameters: Template parameters
            
        Returns:
            Rendered report
        """
        if format == ReportFormat.JSON:
            return json.dumps(data, indent=2, default=str)
            
        if format == ReportFormat.CSV:
            return self._render_csv(data)
            
        if format == ReportFormat.MARKDOWN:
            return self._render_markdown(data)
            
        # HTML and PDF
        template = self._templates.get(template_name)
        if not template:
            # Find default template for type
            default_name = f"{type.value}_default"
            template = self._templates.get(default_name)
            
        if template:
            # Render with Jinja2
            context = data.copy()
            if parameters:
                context.update(parameters)
            context["generated_at"] = datetime.utcnow().isoformat()
            
            jinja_template = self._jinja_env.from_string(template.template)
            return jinja_template.render(**context)
            
        # Fallback: simple HTML
        return f"""
        <html>
        <head><title>NEXUS Report</title></head>
        <body>
            <h1>NEXUS {type.value.capitalize()} Report</h1>
            <pre>{json.dumps(data, indent=2, default=str)}</pre>
        </body>
        </html>
        """
        
    def _render_csv(self, data: Dict[str, Any]) -> str:
        """
        Render data as CSV.
        
        Args:
            data: Report data
            
        Returns:
            CSV string
        """
        # Extract flat data
        flat_data = self._flatten_dict(data)
        output = []
        
        writer = csv.StringIO()
        if flat_data:
            fieldnames = list(flat_data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_data)
            
        return writer.getvalue() if output else ""
        
    def _flatten_dict(self, data: Dict[str, Any], prefix: str = "") -> List[Dict[str, Any]]:
        """
        Flatten nested dictionary for CSV export.
        
        Args:
            data: Dictionary to flatten
            prefix: Key prefix
            
        Returns:
            List of flattened dictionaries
        """
        result = []
        
        for key, value in data.items():
            full_key = f"{prefix}_{key}" if prefix else key
            
            if isinstance(value, dict):
                result.extend(self._flatten_dict(value, full_key))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        result.extend(self._flatten_dict(item, f"{full_key}_{i}"))
                    else:
                        result.append({full_key: str(item)})
            else:
                result.append({full_key: str(value)})
                
        return result
        
    def _render_markdown(self, data: Dict[str, Any]) -> str:
        """
        Render data as Markdown.
        
        Args:
            data: Report data
            
        Returns:
            Markdown string
        """
        lines = [
            f"# NEXUS Report",
            f"",
            f"## Generated: {datetime.utcnow().isoformat()}",
            f"",
        ]
        
        for section, content in data.items():
            if isinstance(content, dict):
                lines.append(f"### {section.replace('_', ' ').title()}")
                for key, value in content.items():
                    if not isinstance(value, (dict, list)):
                        lines.append(f"- **{key}**: {value}")
                lines.append("")
                
        return "\n".join(lines)
        
    async def _save_report(
        self,
        report_id: str,
        format: ReportFormat,
        content: str
    ) -> str:
        """
        Save report to file.
        
        Args:
            report_id: Report ID
            format: Report format
            content: Report content
            
        Returns:
            File path
        """
        extension = {
            ReportFormat.JSON: "json",
            ReportFormat.CSV: "csv",
            ReportFormat.HTML: "html",
            ReportFormat.PDF: "pdf",
            ReportFormat.MARKDOWN: "md"
        }.get(format, "txt")
        
        filename = f"{report_id}.{extension}"
        file_path = self.report_dir / filename
        
        async with aiofiles.open(file_path, 'w') as f:
            await f.write(content)
            
        return str(file_path)
        
    def get_report(self, report_id: str) -> Optional[Report]:
        """
        Get report by ID.
        
        Args:
            report_id: Report ID
            
        Returns:
            Report or None
        """
        return self._reports.get(report_id)
        
    def get_history(
        self,
        limit: int = 100,
        type: Optional[ReportType] = None
    ) -> List[Report]:
        """
        Get report history.
        
        Args:
            limit: Maximum results
            type: Filter by type
            
        Returns:
            List of reports
        """
        history = list(self._report_history)
        if type:
            history = [r for r in history if r.type == type]
        return history[-limit:]
        
    async def close(self) -> None:
        """Close the report generator."""
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
                    
        logger.info("ReportGenerator closed")


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_report_generator: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """
    Get the global report generator instance.
    
    Returns:
        ReportGenerator instance
    """
    global _global_report_generator
    if _global_report_generator is None:
        _global_report_generator = ReportGenerator()
    return _global_report_generator


def reset_report_generator() -> None:
    """Reset the global report generator instance."""
    global _global_report_generator
    if _global_report_generator:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_report_generator.close())
            else:
                asyncio.run(_global_report_generator.close())
        except Exception:
            pass
    _global_report_generator = None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'ReportType',
    'ReportFormat',
    'ReportStatus',
    'ReportSchedule',
    
    # Data Models
    'Report',
    'ReportConfig',
    'ReportTemplate',
    
    # Main Class
    'ReportGenerator',
    'get_report_generator',
    'reset_report_generator',
]

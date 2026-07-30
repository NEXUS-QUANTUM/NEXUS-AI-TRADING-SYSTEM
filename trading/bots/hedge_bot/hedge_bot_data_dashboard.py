# trading/bots/hedge_bot/hedge_bot_data_dashboard.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Dashboard Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Dashboard Module

This module provides comprehensive dashboard and visualization capabilities
for the NEXUS Hedge Bot system. It creates interactive dashboards for
monitoring trading data, performance metrics, and system status.

The module covers:
- Dashboard Creation
- Widget Management
- Data Visualization
- Real-time Updates
- Performance Monitoring
- Trading Analytics
- Risk Dashboards
- Customizable Layouts
"""

import os
import sys
import json
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

logger = logging.getLogger(__name__)


# ============================================================
# DATA DASHBOARD ENUMS
# ============================================================

class DashboardType(Enum):
    """Dashboard types"""
    TRADING = "trading"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    PERFORMANCE = "performance"
    SYSTEM = "system"
    CUSTOM = "custom"


class WidgetType(Enum):
    """Widget types"""
    CHART = "chart"
    METRIC = "metric"
    TABLE = "table"
    STATUS = "status"
    ALERT = "alert"
    GAUGE = "gauge"
    HEATMAP = "heatmap"


class UpdateFrequency(Enum):
    """Update frequencies"""
    REALTIME = "realtime"
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"


@dataclass
class DashboardConfig:
    """Dashboard configuration"""
    id: str
    name: str
    type: DashboardType
    widgets: List[Dict[str, Any]]
    layout: str = "grid"
    refresh_interval: int = 5
    theme: str = "dark"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "widgets": self.widgets,
            "layout": self.layout,
            "refresh_interval": self.refresh_interval,
            "theme": self.theme,
        }


@dataclass
class DashboardWidget:
    """Dashboard widget"""
    id: str
    type: WidgetType
    title: str
    data: Dict[str, Any]
    position: Dict[str, int]
    size: Dict[str, int]
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "data": self.data,
            "position": self.position,
            "size": self.size,
            "config": self.config,
        }


@dataclass
class DashboardData:
    """Dashboard data"""
    dashboard_id: str
    widgets: Dict[str, Any]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "dashboard_id": self.dashboard_id,
            "widgets": self.widgets,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# DATA DASHBOARD ENGINE
# ============================================================

class DataDashboardEngine:
    """
    Comprehensive data dashboard engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the dashboard engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        if not HAS_PLOTLY:
            logger.warning("Plotly not installed. Visualization limited.")
        
        # State
        self.dashboards: Dict[str, DashboardConfig] = {}
        self.widget_data: Dict[str, Dict[str, Any]] = {}
        self.active_widgets: Dict[str, Callable] = {}
        
        # Register default widget generators
        self._register_default_widgets()
        
        logger.info("Data dashboard engine initialized")
    
    # ============================================================
    # DEFAULT WIDGETS
    # ============================================================
    
    def _register_default_widgets(self) -> None:
        """Register default widget generators"""
        self.active_widgets["metric"] = self._generate_metric_widget
        self.active_widgets["chart"] = self._generate_chart_widget
        self.active_widgets["table"] = self._generate_table_widget
        self.active_widgets["status"] = self._generate_status_widget
        self.active_widgets["alert"] = self._generate_alert_widget
        self.active_widgets["gauge"] = self._generate_gauge_widget
    
    def _generate_metric_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate metric widget"""
        value = data.get("value", 0)
        label = data.get("label", "Metric")
        change = data.get("change", 0)
        
        return {
            "value": value,
            "label": label,
            "change": change,
            "formatted": f"{value:,.2f}",
            "status": "positive" if change >= 0 else "negative",
        }
    
    def _generate_chart_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate chart widget"""
        chart_type = data.get("chart_type", "line")
        series = data.get("series", [])
        labels = data.get("labels", [])
        
        if not HAS_PLOTLY:
            return {"html": "Plotly not installed"}
        
        fig = go.Figure()
        
        if chart_type == "line":
            for s in series:
                fig.add_trace(go.Scatter(
                    x=labels,
                    y=s.get("data", []),
                    name=s.get("name", "Series"),
                    mode="lines",
                ))
        elif chart_type == "bar":
            for s in series:
                fig.add_trace(go.Bar(
                    x=labels,
                    y=s.get("data", []),
                    name=s.get("name", "Series"),
                ))
        elif chart_type == "pie":
            fig.add_trace(go.Pie(
                labels=labels,
                values=series[0].get("data", []) if series else [],
            ))
        
        fig.update_layout(
            template="plotly_dark",
            showlegend=True,
            height=300,
        )
        
        return {"figure": fig.to_json()}
    
    def _generate_table_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate table widget"""
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        
        return {
            "columns": columns,
            "rows": rows,
            "count": len(rows),
        }
    
    def _generate_status_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate status widget"""
        status = data.get("status", "unknown")
        message = data.get("message", "")
        details = data.get("details", {})
        
        return {
            "status": status,
            "message": message,
            "details": details,
            "color": {
                "healthy": "green",
                "warning": "yellow",
                "error": "red",
                "unknown": "gray",
            }.get(status, "gray"),
        }
    
    def _generate_alert_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate alert widget"""
        alerts = data.get("alerts", [])
        
        return {
            "alerts": alerts,
            "count": len(alerts),
            "critical": len([a for a in alerts if a.get("severity") == "critical"]),
        }
    
    def _generate_gauge_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate gauge widget"""
        value = data.get("value", 0)
        min_val = data.get("min", 0)
        max_val = data.get("max", 100)
        label = data.get("label", "Gauge")
        
        return {
            "value": value,
            "min": min_val,
            "max": max_val,
            "label": label,
            "percentage": (value - min_val) / (max_val - min_val) * 100 if max_val > min_val else 0,
            "color": "green" if value < 70 else "yellow" if value < 90 else "red",
        }
    
    # ============================================================
    # DASHBOARD MANAGEMENT
    # ============================================================
    
    def create_dashboard(
        self,
        name: str,
        dashboard_type: DashboardType = DashboardType.TRADING,
        widgets: Optional[List[Dict[str, Any]]] = None,
        layout: str = "grid",
        refresh_interval: int = 5,
        theme: str = "dark"
    ) -> DashboardConfig:
        """
        Create a dashboard
        
        Args:
            name: Dashboard name
            dashboard_type: Dashboard type
            widgets: Widget configurations
            layout: Layout type
            refresh_interval: Refresh interval in seconds
            theme: Theme
            
        Returns:
            DashboardConfig
        """
        dashboard = DashboardConfig(
            id=f"dash_{int(time.time())}_{name}",
            name=name,
            type=dashboard_type,
            widgets=widgets or [],
            layout=layout,
            refresh_interval=refresh_interval,
            theme=theme,
        )
        
        self.dashboards[dashboard.id] = dashboard
        logger.info(f"Created dashboard: {name}")
        return dashboard
    
    def delete_dashboard(self, dashboard_id: str) -> bool:
        """
        Delete a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            True if deleted
        """
        if dashboard_id in self.dashboards:
            del self.dashboards[dashboard_id]
            return True
        return False
    
    def get_dashboard(self, dashboard_id: str) -> Optional[DashboardConfig]:
        """
        Get a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            DashboardConfig or None
        """
        return self.dashboards.get(dashboard_id)
    
    def get_dashboards(self) -> List[DashboardConfig]:
        """
        Get all dashboards
        
        Returns:
            List of dashboards
        """
        return list(self.dashboards.values())
    
    # ============================================================
    # WIDGET MANAGEMENT
    # ============================================================
    
    def add_widget(
        self,
        dashboard_id: str,
        widget_type: WidgetType,
        title: str,
        data: Dict[str, Any],
        position: Dict[str, int],
        size: Dict[str, int],
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a widget to a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            widget_type: Widget type
            title: Widget title
            data: Widget data
            position: Widget position
            size: Widget size
            config: Widget configuration
            
        Returns:
            True if added
        """
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return False
        
        widget = {
            "id": f"widget_{int(time.time())}_{len(dashboard.widgets)}",
            "type": widget_type.value,
            "title": title,
            "data": data,
            "position": position,
            "size": size,
            "config": config or {},
        }
        
        dashboard.widgets.append(widget)
        return True
    
    def remove_widget(self, dashboard_id: str, widget_id: str) -> bool:
        """
        Remove a widget from a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            widget_id: Widget ID
            
        Returns:
            True if removed
        """
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return False
        
        dashboard.widgets = [w for w in dashboard.widgets if w["id"] != widget_id]
        return True
    
    def update_widget_data(
        self,
        dashboard_id: str,
        widget_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Update widget data
        
        Args:
            dashboard_id: Dashboard ID
            widget_id: Widget ID
            data: New data
            
        Returns:
            True if updated
        """
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return False
        
        for widget in dashboard.widgets:
            if widget["id"] == widget_id:
                widget["data"] = data
                return True
        return False
    
    # ============================================================
    # DASHBOARD RENDERING
    # ============================================================
    
    def render_dashboard(
        self,
        dashboard_id: str,
        data_provider: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Render a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            data_provider: Data provider function
            
        Returns:
            Rendered dashboard data
        """
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return {"error": "Dashboard not found"}
        
        rendered_widgets = {}
        
        for widget in dashboard.widgets:
            widget_data = widget["data"]
            
            # Get real-time data if provider exists
            if data_provider:
                try:
                    widget_data = data_provider(widget["id"], widget["type"], widget["data"])
                except Exception as e:
                    logger.error(f"Failed to get data for widget {widget['id']}: {e}")
            
            # Generate widget
            generator = self.active_widgets.get(widget["type"])
            if generator:
                try:
                    rendered = generator(widget_data)
                    rendered_widgets[widget["id"]] = {
                        "title": widget["title"],
                        "type": widget["type"],
                        "position": widget["position"],
                        "size": widget["size"],
                        "content": rendered,
                        "config": widget.get("config", {}),
                    }
                except Exception as e:
                    logger.error(f"Failed to render widget {widget['id']}: {e}")
                    rendered_widgets[widget["id"]] = {"error": str(e)}
        
        return {
            "dashboard_id": dashboard_id,
            "name": dashboard.name,
            "type": dashboard.type.value,
            "theme": dashboard.theme,
            "widgets": rendered_widgets,
            "timestamp": datetime.now().isoformat(),
            "refresh_interval": dashboard.refresh_interval,
        }
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get dashboard statistics
        
        Returns:
            Statistics dictionary
        """
        total_widgets = sum(len(d.widgets) for d in self.dashboards.values())
        
        return {
            "total_dashboards": len(self.dashboards),
            "total_widgets": total_widgets,
            "dashboard_types": {
                dt.value: len([d for d in self.dashboards.values() if d.type == dt])
                for dt in DashboardType
            },
            "widget_types": {
                wt.value: sum(
                    1 for d in self.dashboards.values()
                    for w in d.widgets if w["type"] == wt.value
                )
                for wt in WidgetType
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "DashboardType",
    "WidgetType",
    "UpdateFrequency",
    
    # Dataclasses
    "DashboardConfig",
    "DashboardWidget",
    "DashboardData",
    
    # Classes
    "DataDashboardEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

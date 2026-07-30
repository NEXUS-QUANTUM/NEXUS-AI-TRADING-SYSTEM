# trading/bots/hedge_bot/hedge_bot_dashboard.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Dashboard Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Dashboard Module

This module provides comprehensive dashboard and monitoring capabilities
for the NEXUS Hedge Bot system. It includes real-time dashboards, widgets,
and visualization components for monitoring bot performance.

The module covers:
- Dashboard Management
- Widget Management
- Real-time Updates
- Performance Monitoring
- Portfolio Visualization
- Risk Monitoring
- Strategy Monitoring
- Alert Management
- Customizable Layouts
- Export Capabilities
"""

import os
import sys
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================
# DASHBOARD ENUMS
# ============================================================

class WidgetType(Enum):
    """Widget types"""
    METRIC = "metric"
    CHART = "chart"
    TABLE = "table"
    STATUS = "status"
    ALERT = "alert"
    PERFORMANCE = "performance"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    STRATEGY = "strategy"
    ORDER_BOOK = "order_book"
    TRADE_HISTORY = "trade_history"
    POSITION = "position"
    CUSTOM = "custom"


class DashboardLayout(Enum):
    """Dashboard layouts"""
    GRID = "grid"
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    CUSTOM = "custom"


class WidgetSize(Enum):
    """Widget sizes"""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"
    FULL = "full"


# ============================================================
# DASHBOARD DATACLASSES
# ============================================================

@dataclass
class Widget:
    """Dashboard widget"""
    id: str
    type: WidgetType
    title: str
    size: WidgetSize
    position: Dict[str, int]
    data: Dict[str, Any]
    config: Dict[str, Any]
    refresh_interval: int = 5
    last_update: Optional[datetime] = None
    is_visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "size": self.size.value,
            "position": self.position,
            "data": self.data,
            "config": self.config,
            "refresh_interval": self.refresh_interval,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "is_visible": self.is_visible,
            "metadata": self.metadata,
        }


@dataclass
class Dashboard:
    """Dashboard definition"""
    id: str
    name: str
    description: str
    layout: DashboardLayout
    widgets: List[Widget]
    refresh_interval: int = 5
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "layout": self.layout.value,
            "widgets": [w.to_dict() for w in self.widgets],
            "refresh_interval": self.refresh_interval,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class DashboardMetric:
    """Dashboard metric"""
    name: str
    value: Any
    change: Optional[float] = None
    change_percent: Optional[float] = None
    status: str = "normal"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "value": self.value,
            "change": self.change,
            "change_percent": self.change_percent,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# DASHBOARD ENGINE
# ============================================================

class DashboardEngine:
    """
    Comprehensive dashboard engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the dashboard engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_refresh = self.config.get("default_refresh", 5)
        
        # State
        self.dashboards: Dict[str, Dashboard] = {}
        self.widget_data: Dict[str, Any] = {}
        self.widget_handlers: Dict[str, Callable] = {}
        
        # Initialize default widgets
        self._init_default_widgets()
        
        logger.info("Dashboard engine initialized")
    
    # ============================================================
    # DEFAULT WIDGETS
    # ============================================================
    
    def _init_default_widgets(self) -> None:
        """Initialize default widget handlers"""
        self.widget_handlers["metric"] = self._handle_metric_widget
        self.widget_handlers["chart"] = self._handle_chart_widget
        self.widget_handlers["table"] = self._handle_table_widget
        self.widget_handlers["status"] = self._handle_status_widget
        self.widget_handlers["alert"] = self._handle_alert_widget
        self.widget_handlers["performance"] = self._handle_performance_widget
        self.widget_handlers["portfolio"] = self._handle_portfolio_widget
        self.widget_handlers["risk"] = self._handle_risk_widget
        self.widget_handlers["strategy"] = self._handle_strategy_widget
        
        logger.info(f"Initialized {len(self.widget_handlers)} widget handlers")
    
    # ============================================================
    # DASHBOARD MANAGEMENT
    # ============================================================
    
    def create_dashboard(
        self,
        name: str,
        description: str,
        layout: DashboardLayout = DashboardLayout.GRID,
        widgets: Optional[List[Dict[str, Any]]] = None
    ) -> Dashboard:
        """
        Create a new dashboard
        
        Args:
            name: Dashboard name
            description: Dashboard description
            layout: Dashboard layout
            widgets: List of widget configurations
            
        Returns:
            Dashboard
        """
        dashboard = Dashboard(
            id=f"dash_{int(time.time())}_{len(self.dashboards)}",
            name=name,
            description=description,
            layout=layout,
            widgets=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        # Add widgets
        if widgets:
            for widget_config in widgets:
                widget = self.create_widget(dashboard.id, widget_config)
                dashboard.widgets.append(widget)
        
        self.dashboards[dashboard.id] = dashboard
        logger.info(f"Created dashboard: {name}")
        return dashboard
    
    def update_dashboard(
        self,
        dashboard_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dashboard]:
        """
        Update a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            updates: Updates to apply
            
        Returns:
            Updated dashboard or None
        """
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return None
        
        for key, value in updates.items():
            if hasattr(dashboard, key):
                setattr(dashboard, key, value)
        
        dashboard.updated_at = datetime.now()
        logger.info(f"Updated dashboard: {dashboard.name}")
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
            logger.info(f"Deleted dashboard: {dashboard_id}")
            return True
        return False
    
    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """
        Get a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            Dashboard or None
        """
        return self.dashboards.get(dashboard_id)
    
    def get_dashboards(self) -> List[Dashboard]:
        """
        Get all dashboards
        
        Returns:
            List of dashboards
        """
        return list(self.dashboards.values())
    
    # ============================================================
    # WIDGET MANAGEMENT
    # ============================================================
    
    def create_widget(
        self,
        dashboard_id: str,
        config: Dict[str, Any]
    ) -> Widget:
        """
        Create a widget
        
        Args:
            dashboard_id: Dashboard ID
            config: Widget configuration
            
        Returns:
            Widget
        """
        widget = Widget(
            id=f"widget_{int(time.time())}_{len(self.widget_data)}",
            type=WidgetType(config.get("type", "metric")),
            title=config.get("title", "Widget"),
            size=WidgetSize(config.get("size", "medium")),
            position=config.get("position", {"x": 0, "y": 0}),
            data=config.get("data", {}),
            config=config.get("config", {}),
            refresh_interval=config.get("refresh_interval", self.default_refresh),
            metadata=config.get("metadata", {}),
        )
        
        self.widget_data[widget.id] = widget
        return widget
    
    def update_widget(
        self,
        widget_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Widget]:
        """
        Update a widget
        
        Args:
            widget_id: Widget ID
            updates: Updates to apply
            
        Returns:
            Updated widget or None
        """
        widget = self.widget_data.get(widget_id)
        if not widget:
            return None
        
        for key, value in updates.items():
            if hasattr(widget, key):
                setattr(widget, key, value)
        
        widget.last_update = datetime.now()
        return widget
    
    def delete_widget(self, widget_id: str) -> bool:
        """
        Delete a widget
        
        Args:
            widget_id: Widget ID
            
        Returns:
            True if deleted
        """
        if widget_id in self.widget_data:
            del self.widget_data[widget_id]
            logger.info(f"Deleted widget: {widget_id}")
            return True
        return False
    
    def get_widget(self, widget_id: str) -> Optional[Widget]:
        """
        Get a widget
        
        Args:
            widget_id: Widget ID
            
        Returns:
            Widget or None
        """
        return self.widget_data.get(widget_id)
    
    def get_widgets(self, dashboard_id: str) -> List[Widget]:
        """
        Get widgets for a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            List of widgets
        """
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return []
        return dashboard.widgets
    
    # ============================================================
    # WIDGET HANDLERS
    # ============================================================
    
    def register_widget_handler(
        self,
        widget_type: str,
        handler: Callable
    ) -> None:
        """
        Register a widget handler
        
        Args:
            widget_type: Widget type
            handler: Handler function
        """
        self.widget_handlers[widget_type] = handler
        logger.info(f"Registered widget handler: {widget_type}")
    
    def _handle_metric_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle metric widget"""
        return {
            "value": widget.data.get("value", 0),
            "change": widget.data.get("change", 0),
            "change_percent": widget.data.get("change_percent", 0),
            "status": widget.data.get("status", "normal"),
        }
    
    def _handle_chart_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle chart widget"""
        return {
            "series": widget.data.get("series", []),
            "labels": widget.data.get("labels", []),
            "type": widget.data.get("chart_type", "line"),
        }
    
    def _handle_table_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle table widget"""
        return {
            "columns": widget.data.get("columns", []),
            "rows": widget.data.get("rows", []),
        }
    
    def _handle_status_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle status widget"""
        return {
            "status": widget.data.get("status", "unknown"),
            "message": widget.data.get("message", ""),
            "details": widget.data.get("details", {}),
        }
    
    def _handle_alert_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle alert widget"""
        return {
            "alerts": widget.data.get("alerts", []),
            "count": len(widget.data.get("alerts", [])),
        }
    
    def _handle_performance_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle performance widget"""
        return {
            "metrics": widget.data.get("metrics", {}),
            "trend": widget.data.get("trend", {}),
        }
    
    def _handle_portfolio_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle portfolio widget"""
        return {
            "total_value": widget.data.get("total_value", 0),
            "allocation": widget.data.get("allocation", {}),
            "positions": widget.data.get("positions", []),
        }
    
    def _handle_risk_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle risk widget"""
        return {
            "var": widget.data.get("var", 0),
            "drawdown": widget.data.get("drawdown", 0),
            "risk_score": widget.data.get("risk_score", 0),
        }
    
    def _handle_strategy_widget(self, widget: Widget) -> Dict[str, Any]:
        """Handle strategy widget"""
        return {
            "name": widget.data.get("name", ""),
            "status": widget.data.get("status", ""),
            "metrics": widget.data.get("metrics", {}),
        }
    
    # ============================================================
    # DATA UPDATE
    # ============================================================
    
    def update_widget_data(
        self,
        widget_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Update widget data
        
        Args:
            widget_id: Widget ID
            data: New data
            
        Returns:
            True if updated
        """
        widget = self.get_widget(widget_id)
        if not widget:
            return False
        
        widget.data = data
        widget.last_update = datetime.now()
        return True
    
    def refresh_widget(self, widget_id: str) -> Optional[Dict[str, Any]]:
        """
        Refresh a widget
        
        Args:
            widget_id: Widget ID
            
        Returns:
            Widget data or None
        """
        widget = self.get_widget(widget_id)
        if not widget:
            return None
        
        handler = self.widget_handlers.get(widget.type.value)
        if handler:
            return handler(widget)
        
        return widget.data
    
    def refresh_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """
        Refresh a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            Dashboard data
        """
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return {}
        
        result = {
            "dashboard_id": dashboard.id,
            "name": dashboard.name,
            "timestamp": datetime.now().isoformat(),
            "widgets": {},
        }
        
        for widget in dashboard.widgets:
            if widget.is_visible:
                result["widgets"][widget.id] = self.refresh_widget(widget.id)
        
        return result
    
    # ============================================================
    # EXPORT
    # ============================================================
    
    def export_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """
        Export a dashboard
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            Dashboard data
        """
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return {}
        
        return {
            "dashboard": dashboard.to_dict(),
            "widgets": [w.to_dict() for w in dashboard.widgets],
            "exported_at": datetime.now().isoformat(),
        }
    
    def import_dashboard(self, data: Dict[str, Any]) -> Optional[Dashboard]:
        """
        Import a dashboard
        
        Args:
            data: Dashboard data
            
        Returns:
            Imported dashboard
        """
        try:
            dashboard_data = data.get("dashboard", {})
            widgets_data = data.get("widgets", [])
            
            # Create dashboard
            dashboard = self.create_dashboard(
                name=dashboard_data.get("name", "Imported Dashboard"),
                description=dashboard_data.get("description", ""),
                layout=DashboardLayout(dashboard_data.get("layout", "grid")),
            )
            
            # Add widgets
            for widget_data in widgets_data:
                widget = self.create_widget(dashboard.id, widget_data)
                dashboard.widgets.append(widget)
            
            return dashboard
        except Exception as e:
            logger.error(f"Failed to import dashboard: {e}")
            return None
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get dashboard statistics
        
        Returns:
            Statistics dictionary
        """
        total_widgets = sum(len(d.get("widgets", [])) for d in self.dashboards.values())
        
        return {
            "total_dashboards": len(self.dashboards),
            "total_widgets": total_widgets,
            "active_dashboards": len([d for d in self.dashboards.values() if d.is_active]),
            "widget_types": {
                wtype.value: len([w for d in self.dashboards.values() for w in d.widgets if w.type.value == wtype.value])
                for wtype in WidgetType
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "WidgetType",
    "DashboardLayout",
    "WidgetSize",
    
    # Dataclasses
    "Widget",
    "Dashboard",
    "DashboardMetric",
    
    # Classes
    "DashboardEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

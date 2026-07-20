# trading/bots/arbitrage_bot/templates/__init__.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Templates Package

"""
Templates Package - Complete Web Interface Templates

This package provides comprehensive HTML templates for the NEXUS AI Trading
System web interface, including dashboard, exchanges, opportunities,
performance monitoring, and configuration pages.

Architecture:
    - Base Templates: Layout and structure
    - Components: Reusable UI components
    - Partials: Modular template sections
    - Pages: Complete page templates
    - API Integration: Dynamic data rendering

Template Structure:
    ├── __init__.py                  # Package initialization
    ├── dashboard.html               # Main dashboard
    ├── exchanges.html               # Exchange management
    ├── logs.html                    # System logs
    ├── opportunities.html           # Arbitrage opportunities
    ├── performance.html             # Performance metrics
    ├── reports.html                 # Report viewer
    ├── settings.html                # System settings
    ├── strategies.html              # Strategy management
    ├── components/                  # Reusable components
    │   ├── chart_card.html
    │   ├── exchange_card.html
    │   ├── metric_card.html
    │   └── opportunity_card.html
    └── partials/                    # Partial templates
        ├── alerts.html
        ├── footer.html
        ├── header.html
        ├── metrics.html
        └── sidebar.html

Exports:
    - Template paths
    - Template rendering functions
    - API integration helpers
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
from decimal import Decimal
import jinja2

# Logger setup
logger = logging.getLogger(__name__)

# Version information
__version__ = "4.2.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package metadata
PACKAGE_METADATA = {
    "name": "templates",
    "version": __version__,
    "description": "Web Interface Templates Package",
    "author": __author__,
    "copyright": __copyright__,
    "template_count": 8,
    "component_count": 4,
    "partial_count": 5,
    "supported_pages": [
        "dashboard",
        "exchanges",
        "logs",
        "opportunities",
        "performance",
        "reports",
        "settings",
        "strategies",
    ],
}

# Template paths
TEMPLATE_DIR = Path(__file__).parent
COMPONENTS_DIR = TEMPLATE_DIR / "components"
PARTIALS_DIR = TEMPLATE_DIR / "partials"

# Ensure directories exist
COMPONENTS_DIR.mkdir(exist_ok=True)
PARTIALS_DIR.mkdir(exist_ok=True)

# Public API - All templates
__all__ = [
    # Template constants
    'TEMPLATE_DIR',
    'COMPONENTS_DIR',
    'PARTIALS_DIR',
    
    # Template functions
    'render_template',
    'render_component',
    'render_partial',
    'get_template_path',
    'list_templates',
    'load_template',
    'save_template',
    'delete_template',
    
    # API helpers
    'TemplateEngine',
    'TemplateContext',
    'APIConnector',
    'TemplateRenderer',
    
    # Data providers
    'get_dashboard_data',
    'get_exchanges_data',
    'get_opportunities_data',
    'get_performance_data',
    'get_logs_data',
    'get_reports_data',
    'get_settings_data',
    'get_strategies_data',
    
    # Metadata
    'PACKAGE_METADATA',
    'get_version',
    'get_metadata',
    'list_templates',
]


class TemplateContext:
    """
    Template context for rendering.
    
    This class manages the context data for template rendering,
    including system state, API data, and user preferences.
    """
    
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        """
        Initialize the template context.
        
        Args:
            data: Initial context data
        """
        self.data = data or {}
        self._defaults = self._get_defaults()
        self._callbacks: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = []
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Get default context values."""
        return {
            "system": {
                "name": "NEXUS AI Trading System",
                "version": __version__,
                "environment": "production",
                "uptime": "24h",
                "status": "running",
                "build": "4.2.0",
            },
            "user": {
                "name": "Administrator",
                "role": "admin",
                "authenticated": True,
                "avatar": "/static/images/avatar.png",
            },
            "theme": {
                "mode": "dark",
                "primary_color": "#6C63FF",
                "secondary_color": "#00D4FF",
                "accent_color": "#FF6B6B",
                "background_color": "#1A1A2E",
                "card_background": "#16213E",
            },
            "timestamp": datetime.utcnow().isoformat(),
            "navigation": {
                "items": [
                    {"name": "Dashboard", "icon": "dashboard", "url": "/"},
                    {"name": "Exchanges", "icon": "exchange", "url": "/exchanges"},
                    {"name": "Opportunities", "icon": "opportunity", "url": "/opportunities"},
                    {"name": "Strategies", "icon": "strategy", "url": "/strategies"},
                    {"name": "Performance", "icon": "performance", "url": "/performance"},
                    {"name": "Reports", "icon": "reports", "url": "/reports"},
                    {"name": "Logs", "icon": "logs", "url": "/logs"},
                    {"name": "Settings", "icon": "settings", "url": "/settings"},
                ],
                "active": "dashboard",
            },
            "notifications": {
                "count": 3,
                "items": [
                    {"type": "info", "message": "System started successfully", "time": "2m ago"},
                    {"type": "warning", "message": "High latency detected on Binance", "time": "15m ago"},
                    {"type": "success", "message": "Arbitrage opportunity executed", "time": "30m ago"},
                ],
            },
        }
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """
        Add a context callback.
        
        Args:
            callback: Function that modifies context
        """
        self._callbacks.append(callback)
    
    def update(self, data: Dict[str, Any]) -> None:
        """
        Update context data.
        
        Args:
            data: New context data
        """
        self.data.update(data)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a context value.
        
        Args:
            key: Context key
            default: Default value
            
        Returns:
            Context value
        """
        return self.data.get(key, self._defaults.get(key, default))
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all context data.
        
        Returns:
            Complete context dictionary
        """
        result = self._defaults.copy()
        result.update(self.data)
        
        # Apply callbacks
        for callback in self._callbacks:
            try:
                result = callback(result)
            except Exception as e:
                logger.error(f"Context callback failed: {e}")
        
        return result


class TemplateEngine:
    """
    Template engine for rendering HTML templates.
    
    This class provides Jinja2-based template rendering with
    support for components, partials, and API data integration.
    """
    
    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize the template engine.
        
        Args:
            template_dir: Template directory path
        """
        self.template_dir = template_dir or TEMPLATE_DIR
        self._setup_environment()
        self._template_cache: Dict[str, jinja2.Template] = {}
        self.logger = logging.getLogger(f"{__name__}.TemplateEngine")
    
    def _setup_environment(self) -> None:
        """Set up Jinja2 environment."""
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader([
                str(self.template_dir),
                str(COMPONENTS_DIR),
                str(PARTIALS_DIR),
            ]),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            cache_size=100,
        )
        
        # Add custom filters
        self.env.filters['format_decimal'] = self._format_decimal
        self.env.filters['format_currency'] = self._format_currency
        self.env.filters['format_percentage'] = self._format_percentage
        self.env.filters['format_datetime'] = self._format_datetime
        self.env.filters['format_duration'] = self._format_duration
        self.env.filters['format_volume'] = self._format_volume
        self.env.filters['format_number'] = self._format_number
        self.env.filters['truncate'] = self._truncate
        self.env.filters['safe_json'] = self._safe_json
        self.env.filters['safe_html'] = self._safe_html
        self.env.filters['capitalize'] = self._capitalize
        self.env.filters['lower'] = str.lower
        self.env.filters['upper'] = str.upper
        
        # Add global functions
        self.env.globals['now'] = datetime.utcnow
        self.env.globals['range'] = range
        self.env.globals['len'] = len
        self.env.globals['enumerate'] = enumerate
        self.env.globals['zip'] = zip
    
    def _format_decimal(self, value: Union[Decimal, float, int, str]) -> str:
        """Format decimal value."""
        try:
            d = Decimal(str(value))
            return f"{d:.2f}"
        except:
            return str(value)
    
    def _format_currency(self, value: Union[Decimal, float, int, str]) -> str:
        """Format currency value."""
        try:
            d = Decimal(str(value))
            if d >= 0:
                return f"${d:,.2f}"
            else:
                return f"-${abs(d):,.2f}"
        except:
            return str(value)
    
    def _format_percentage(self, value: Union[Decimal, float, int, str]) -> str:
        """Format percentage value."""
        try:
            d = Decimal(str(value))
            return f"{d:+.2f}%"
        except:
            return str(value)
    
    def _format_datetime(self, value: Union[datetime, str, int]) -> str:
        """Format datetime value."""
        try:
            if isinstance(value, str):
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, (int, float)):
                value = datetime.fromtimestamp(value)
            return value.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            return str(value)
    
    def _format_duration(self, seconds: Union[int, float, str]) -> str:
        """Format duration value."""
        try:
            s = int(seconds)
            days = s // 86400
            hours = (s % 86400) // 3600
            minutes = (s % 3600) // 60
            seconds = s % 60
            
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if seconds > 0 or not parts:
                parts.append(f"{seconds}s")
            
            return " ".join(parts)
        except:
            return str(seconds)
    
    def _format_volume(self, value: Union[Decimal, float, int, str]) -> str:
        """Format volume value with suffix."""
        try:
            d = Decimal(str(value))
            if d >= 1_000_000_000:
                return f"{d / 1_000_000_000:.2f}B"
            elif d >= 1_000_000:
                return f"{d / 1_000_000:.2f}M"
            elif d >= 1_000:
                return f"{d / 1_000:.2f}K"
            else:
                return f"{d:.2f}"
        except:
            return str(value)
    
    def _format_number(self, value: Union[int, float, str]) -> str:
        """Format number with commas."""
        try:
            return f"{int(float(value)):,}"
        except:
            return str(value)
    
    def _truncate(self, value: str, length: int = 50, suffix: str = "...") -> str:
        """Truncate string."""
        if not value:
            return ""
        if len(value) <= length:
            return value
        return value[:length] + suffix
    
    def _safe_json(self, value: Any) -> str:
        """Convert to safe JSON string."""
        try:
            return json.dumps(value, default=str)
        except:
            return "{}"
    
    def _safe_html(self, value: str) -> str:
        """Escape HTML content."""
        return jinja2.escape(value)
    
    def _capitalize(self, value: str) -> str:
        """Capitalize string."""
        if not value:
            return ""
        return value[0].upper() + value[1:].lower()
    
    def render_template(
        self,
        template_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a template.
        
        Args:
            template_name: Template name
            context: Template context
            
        Returns:
            Rendered HTML
        """
        try:
            # Check cache
            if template_name in self._template_cache:
                template = self._template_cache[template_name]
            else:
                template = self.env.get_template(template_name)
                self._template_cache[template_name] = template
            
            ctx = TemplateContext(context or {})
            return template.render(**ctx.get_all())
        except jinja2.TemplateNotFound:
            self.logger.error(f"Template not found: {template_name}")
            return f"<h1>Template Not Found</h1><p>{template_name}</p>"
        except Exception as e:
            self.logger.error(f"Template rendering failed: {e}")
            return f"<h1>Template Error</h1><p>{e}</p>"
    
    def render_component(
        self,
        component_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a component.
        
        Args:
            component_name: Component name
            context: Component context
            
        Returns:
            Rendered HTML
        """
        template_path = f"components/{component_name}.html"
        return self.render_template(template_path, context)
    
    def render_partial(
        self,
        partial_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a partial.
        
        Args:
            partial_name: Partial name
            context: Partial context
            
        Returns:
            Rendered HTML
        """
        template_path = f"partials/{partial_name}.html"
        return self.render_template(template_path, context)
    
    def render_string(
        self,
        template_string: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a template string.
        
        Args:
            template_string: Template string
            context: Template context
            
        Returns:
            Rendered HTML
        """
        try:
            template = self.env.from_string(template_string)
            ctx = TemplateContext(context or {})
            return template.render(**ctx.get_all())
        except Exception as e:
            self.logger.error(f"String rendering failed: {e}")
            return f"<h1>Template Error</h1><p>{e}</p>"
    
    def clear_cache(self) -> None:
        """Clear template cache."""
        self._template_cache.clear()
        self.logger.info("Template cache cleared")


class APIConnector:
    """
    API connector for template data.
    
    This class provides API integration for template rendering,
    fetching data from the backend and preparing it for templates.
    """
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the API connector.
        
        Args:
            base_url: Base API URL
        """
        self.base_url = base_url or "http://localhost:8000/api"
        self.logger = logging.getLogger(f"{__name__}.APIConnector")
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: int = 60  # seconds
    
    async def _fetch(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Fetch data from API.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            API response
        """
        # In production, this would make actual HTTP requests
        # For now, return sample data from data providers
        if endpoint == "dashboard":
            return await get_dashboard_data()
        elif endpoint == "exchanges":
            return await get_exchanges_data()
        elif endpoint == "opportunities":
            return await get_opportunities_data()
        elif endpoint == "performance":
            return await get_performance_data()
        elif endpoint == "logs":
            return await get_logs_data()
        elif endpoint == "reports":
            return await get_reports_data()
        elif endpoint == "settings":
            return await get_settings_data()
        elif endpoint == "strategies":
            return await get_strategies_data()
        else:
            return {"error": f"Unknown endpoint: {endpoint}"}
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data from API."""
        return await self._fetch("dashboard")
    
    async def get_exchanges_data(self) -> Dict[str, Any]:
        """Get exchanges data from API."""
        return await self._fetch("exchanges")
    
    async def get_opportunities_data(self) -> Dict[str, Any]:
        """Get opportunities data from API."""
        return await self._fetch("opportunities")
    
    async def get_performance_data(self) -> Dict[str, Any]:
        """Get performance data from API."""
        return await self._fetch("performance")
    
    async def get_logs_data(self) -> Dict[str, Any]:
        """Get logs data from API."""
        return await self._fetch("logs")
    
    async def get_reports_data(self) -> Dict[str, Any]:
        """Get reports data from API."""
        return await self._fetch("reports")
    
    async def get_settings_data(self) -> Dict[str, Any]:
        """Get settings data from API."""
        return await self._fetch("settings")
    
    async def get_strategies_data(self) -> Dict[str, Any]:
        """Get strategies data from API."""
        return await self._fetch("strategies")


class TemplateRenderer:
    """
    Template renderer with API integration.
    
    This class provides async template rendering with API data integration.
    """
    
    def __init__(
        self,
        engine: Optional[TemplateEngine] = None,
        api: Optional[APIConnector] = None
    ):
        """
        Initialize the template renderer.
        
        Args:
            engine: Template engine instance
            api: API connector instance
        """
        self.engine = engine or get_template_engine()
        self.api = api or get_api_connector()
        self.logger = logging.getLogger(f"{__name__}.TemplateRenderer")
    
    async def render_page(
        self,
        page: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a page with API data.
        
        Args:
            page: Page name
            context: Additional context
            
        Returns:
            Rendered HTML
        """
        try:
            # Fetch API data based on page
            api_data = {}
            if page == "dashboard":
                api_data = await self.api.get_dashboard_data()
            elif page == "exchanges":
                api_data = await self.api.get_exchanges_data()
            elif page == "opportunities":
                api_data = await self.api.get_opportunities_data()
            elif page == "performance":
                api_data = await self.api.get_performance_data()
            elif page == "logs":
                api_data = await self.api.get_logs_data()
            elif page == "reports":
                api_data = await self.api.get_reports_data()
            elif page == "settings":
                api_data = await self.api.get_settings_data()
            elif page == "strategies":
                api_data = await self.api.get_strategies_data()
            
            # Merge contexts
            full_context = {
                "page": page,
                "data": api_data,
                **(context or {}),
            }
            
            # Render template
            return self.engine.render_template(f"{page}.html", full_context)
        except Exception as e:
            self.logger.error(f"Page rendering failed: {e}")
            return self.engine.render_template("error.html", {"error": str(e)})


# Global instances
_template_engine = None
_api_connector = None
_renderer = None


def get_template_engine() -> TemplateEngine:
    """Get the global template engine instance."""
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine()
    return _template_engine


def get_api_connector() -> APIConnector:
    """Get the global API connector instance."""
    global _api_connector
    if _api_connector is None:
        _api_connector = APIConnector()
    return _api_connector


def get_renderer() -> TemplateRenderer:
    """Get the global template renderer instance."""
    global _renderer
    if _renderer is None:
        _renderer = TemplateRenderer()
    return _renderer


# Synchronous render functions
def render_template(
    template_name: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Render a template.
    
    Args:
        template_name: Template name
        context: Template context
        
    Returns:
        Rendered HTML
    """
    engine = get_template_engine()
    return engine.render_template(template_name, context)


def render_component(
    component_name: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Render a component.
    
    Args:
        component_name: Component name
        context: Component context
        
    Returns:
        Rendered HTML
    """
    engine = get_template_engine()
    return engine.render_component(component_name, context)


def render_partial(
    partial_name: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Render a partial.
    
    Args:
        partial_name: Partial name
        context: Partial context
        
    Returns:
        Rendered HTML
    """
    engine = get_template_engine()
    return engine.render_partial(partial_name, context)


def render_string(
    template_string: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Render a template string.
    
    Args:
        template_string: Template string
        context: Template context
        
    Returns:
        Rendered HTML
    """
    engine = get_template_engine()
    return engine.render_string(template_string, context)


# Async render functions
async def render_page_async(
    page: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Render a page asynchronously.
    
    Args:
        page: Page name
        context: Additional context
        
    Returns:
        Rendered HTML
    """
    renderer = get_renderer()
    return await renderer.render_page(page, context)


# Template file operations
def get_template_path(template_name: str) -> Path:
    """
    Get template file path.
    
    Args:
        template_name: Template name
        
    Returns:
        Template path
    """
    # Check if it's a component
    if template_name.startswith("components/"):
        return COMPONENTS_DIR / template_name.replace("components/", "")
    elif template_name.startswith("partials/"):
        return PARTIALS_DIR / template_name.replace("partials/", "")
    else:
        return TEMPLATE_DIR / template_name


def list_templates(recursive: bool = True) -> List[str]:
    """
    List all available templates.
    
    Args:
        recursive: Include subdirectories
        
    Returns:
        List of template names
    """
    templates = []
    
    for ext in ['html']:
        # Main directory
        for file_path in TEMPLATE_DIR.glob(f"*.{ext}"):
            templates.append(file_path.name)
        
        # Components
        for file_path in COMPONENTS_DIR.glob(f"*.{ext}"):
            templates.append(f"components/{file_path.name}")
        
        # Partials
        for file_path in PARTIALS_DIR.glob(f"*.{ext}"):
            templates.append(f"partials/{file_path.name}")
    
    return sorted(templates)


def load_template(template_name: str) -> Optional[str]:
    """
    Load template content.
    
    Args:
        template_name: Template name
        
    Returns:
        Template content or None
    """
    try:
        template_path = get_template_path(template_name)
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    except Exception as e:
        logger.error(f"Failed to load template {template_name}: {e}")
        return None


def save_template(template_name: str, content: str) -> bool:
    """
    Save template content.
    
    Args:
        template_name: Template name
        content: Template content
        
    Returns:
        True if saved successfully
    """
    try:
        template_path = get_template_path(template_name)
        template_path.parent.mkdir(exist_ok=True)
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Clear cache
        get_template_engine().clear_cache()
        
        logger.info(f"Saved template: {template_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to save template {template_name}: {e}")
        return False


def delete_template(template_name: str) -> bool:
    """
    Delete template.
    
    Args:
        template_name: Template name
        
    Returns:
        True if deleted successfully
    """
    try:
        template_path = get_template_path(template_name)
        if template_path.exists():
            template_path.unlink()
            
            # Clear cache
            get_template_engine().clear_cache()
            
            logger.info(f"Deleted template: {template_name}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete template {template_name}: {e}")
        return False


# Data providers - sample data for templates
async def get_dashboard_data() -> Dict[str, Any]:
    """Get dashboard data."""
    return {
        "metrics": {
            "total_profit": 1567.89,
            "total_trades": 167,
            "win_rate": 74.8,
            "total_volume": 483678.90,
            "active_positions": 15,
            "exposure": 235678.90,
            "best_trade": 67.89,
            "worst_trade": -34.56,
        },
        "performance": {
            "daily": [12.34, 8.90, 5.67, 7.89, 15.67, 23.45, 45.67],
            "weekly": [123.45, 89.01, 67.89, 56.78, 45.67, 34.56, 23.45],
            "monthly": [456.78, 345.67, 234.56, 123.45, 89.01, 67.89],
        },
        "recent_trades": [
            {
                "id": "trade_001",
                "symbol": "BTC/USD",
                "side": "BUY",
                "price": 94200.00,
                "quantity": 0.5,
                "profit": 12.34,
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "id": "trade_002",
                "symbol": "ETH/USD",
                "side": "SELL",
                "price": 3450.00,
                "quantity": 2.0,
                "profit": 8.90,
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "id": "trade_003",
                "symbol": "SOL/USD",
                "side": "BUY",
                "price": 185.50,
                "quantity": 50,
                "profit": 5.67,
                "timestamp": datetime.utcnow().isoformat(),
            },
        ],
        "opportunities": [
            {
                "id": "opp_001",
                "type": "cross_exchange",
                "symbol": "BTC/USD",
                "profit": 12.34,
                "confidence": 0.92,
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "id": "opp_002",
                "type": "dex",
                "symbol": "ETH/USD",
                "profit": 8.90,
                "confidence": 0.88,
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "id": "opp_003",
                "type": "statistical",
                "symbol": "BTC/ETH",
                "profit": 7.89,
                "confidence": 0.81,
                "timestamp": datetime.utcnow().isoformat(),
            },
        ],
        "system_status": {
            "status": "running",
            "cpu": 23.4,
            "memory": 45.6,
            "disk": 34.5,
            "uptime": "24h",
            "connections": 67,
            "queue_size": 45,
            "error_rate": 0.23,
        },
    }


async def get_exchanges_data() -> Dict[str, Any]:
    """Get exchanges data."""
    return {
        "exchanges": [
            {
                "name": "Binance",
                "type": "CEX",
                "status": "connected",
                "markets": ["spot", "futures"],
                "volume_24h": 1234567.89,
                "latency": 12,
                "connected_since": datetime.utcnow().isoformat(),
                "trading_pairs": 234,
                "websocket": True,
            },
            {
                "name": "Bybit",
                "type": "CEX",
                "status": "connected",
                "markets": ["spot", "futures"],
                "volume_24h": 987654.32,
                "latency": 15,
                "connected_since": datetime.utcnow().isoformat(),
                "trading_pairs": 187,
                "websocket": True,
            },
            {
                "name": "OKX",
                "type": "CEX",
                "status": "connected",
                "markets": ["spot", "futures", "perpetual"],
                "volume_24h": 876543.21,
                "latency": 18,
                "connected_since": datetime.utcnow().isoformat(),
                "trading_pairs": 156,
                "websocket": True,
            },
            {
                "name": "Uniswap",
                "type": "DEX",
                "status": "connected",
                "markets": ["spot"],
                "volume_24h": 456789.01,
                "latency": 45,
                "connected_since": datetime.utcnow().isoformat(),
                "trading_pairs": 89,
                "websocket": False,
            },
            {
                "name": "PancakeSwap",
                "type": "DEX",
                "status": "connected",
                "markets": ["spot"],
                "volume_24h": 345678.90,
                "latency": 52,
                "connected_since": datetime.utcnow().isoformat(),
                "trading_pairs": 67,
                "websocket": False,
            },
        ],
        "summary": {
            "total_exchanges": 5,
            "connected": 5,
            "total_volume": 3904233.33,
            "avg_latency": 28.4,
            "websocket_connections": 3,
        },
        "connection_status": {
            "healthy": 5,
            "degraded": 0,
            "unhealthy": 0,
        },
    }


async def get_opportunities_data() -> Dict[str, Any]:
    """Get opportunities data."""
    return {
        "opportunities": [
            {
                "id": "opp_001",
                "type": "cross_exchange",
                "symbol": "BTC/USD",
                "entry_price": 94200.00,
                "exit_price": 94245.50,
                "expected_profit": 12.34,
                "expected_profit_pct": 0.12,
                "confidence": 0.92,
                "risk": 0.15,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "executed",
            },
            {
                "id": "opp_002",
                "type": "dex",
                "symbol": "ETH/USD",
                "entry_price": 3450.00,
                "exit_price": 3465.50,
                "expected_profit": 8.90,
                "expected_profit_pct": 0.45,
                "confidence": 0.88,
                "risk": 0.20,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending",
            },
            {
                "id": "opp_003",
                "type": "statistical",
                "symbol": "BTC/ETH",
                "entry_price": 0.0354,
                "exit_price": 0.0358,
                "expected_profit": 7.89,
                "expected_profit_pct": 0.32,
                "confidence": 0.81,
                "risk": 0.25,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "executing",
            },
            {
                "id": "opp_004",
                "type": "triangular",
                "symbol": "BTC/ETH/SOL",
                "entry_price": 1.00,
                "exit_price": 1.0032,
                "expected_profit": 5.67,
                "expected_profit_pct": 0.28,
                "confidence": 0.78,
                "risk": 0.30,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending",
            },
            {
                "id": "opp_005",
                "type": "flash_loan",
                "symbol": "USDC",
                "entry_price": 1.00,
                "exit_price": 1.00045,
                "expected_profit": 4.56,
                "expected_profit_pct": 0.045,
                "confidence": 0.75,
                "risk": 0.35,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "failed",
            },
        ],
        "summary": {
            "total": 28,
            "executed": 12,
            "pending": 10,
            "failed": 6,
            "total_profit": 234.50,
            "avg_confidence": 0.82,
            "avg_risk": 0.25,
        },
        "by_type": {
            "cross_exchange": 8,
            "dex": 6,
            "statistical": 5,
            "triangular": 5,
            "flash_loan": 4,
        },
    }


async def get_performance_data() -> Dict[str, Any]:
    """Get performance data."""
    return {
        "metrics": {
            "sharpe_ratio": 1.85,
            "sortino_ratio": 2.34,
            "calmar_ratio": 1.56,
            "max_drawdown": 4.2,
            "win_rate": 74.8,
            "profit_factor": 2.34,
            "avg_win": 23.45,
            "avg_loss": 12.34,
            "expectancy": 8.72,
            "recovery_factor": 3.12,
        },
        "daily_returns": [12.34, 8.90, 5.67, 7.89, 15.67, 23.45, 45.67],
        "monthly_returns": [123.45, 89.01, 67.89, 56.78, 45.67, 34.56],
        "equity_curve": [
            {"date": "2026-01-01", "value": 100000},
            {"date": "2026-01-02", "value": 100234},
            {"date": "2026-01-03", "value": 100456},
            {"date": "2026-01-04", "value": 100789},
            {"date": "2026-01-05", "value": 101234},
            {"date": "2026-01-06", "value": 101567},
            {"date": "2026-01-07", "value": 101890},
        ],
        "drawdown": {
            "current": 2.3,
            "max": 4.2,
            "avg": 1.8,
            "duration": 3.5,
        },
        "strategy_performance": {
            "cross_exchange": {"profit": 567.89, "trades": 45, "win_rate": 82.2},
            "dex": {"profit": 345.67, "trades": 32, "win_rate": 78.1},
            "statistical": {"profit": 234.56, "trades": 28, "win_rate": 71.4},
            "triangular": {"profit": 178.90, "trades": 22, "win_rate": 68.2},
            "flash_loan": {"profit": 67.89, "trades": 12, "win_rate": 66.7},
        },
    }


async def get_logs_data() -> Dict[str, Any]:
    """Get logs data."""
    return {
        "logs": [
            {
                "timestamp": "2026-01-01 00:00:05.126",
                "level": "INFO",
                "module": "DEX_EXECUTOR",
                "exchange": "UNISWAP",
                "message": "Executing dex arbitrage: ETH -> USDC -> DAI -> ETH",
                "details": {"gas": 145678, "profit": 8.50},
            },
            {
                "timestamp": "2026-01-01 00:00:10.237",
                "level": "INFO",
                "module": "CROSS_EXCHANGE_EXECUTOR",
                "exchange": "BINANCE/BYBIT",
                "message": "Executing cross-exchange arbitrage: BTC/USD",
                "details": {"buy_price": 94200.00, "sell_price": 94245.50},
            },
            {
                "timestamp": "2026-01-01 00:00:15.348",
                "level": "INFO",
                "module": "TRIANGULAR_EXECUTOR",
                "exchange": "OKX",
                "message": "Executing triangular arbitrage: BTC -> ETH -> SOL -> BTC",
                "details": {"profit": 5.67, "execution_time": 45},
            },
            {
                "timestamp": "2026-01-01 00:00:20.460",
                "level": "INFO",
                "module": "STATISTICAL_EXECUTOR",
                "exchange": "BINANCE",
                "message": "Executing statistical arbitrage: BTC/ETH",
                "details": {"z_score": 2.34, "correlation": 0.89},
            },
            {
                "timestamp": "2026-01-01 00:00:30.681",
                "level": "INFO",
                "module": "FLASH_LOAN_EXECUTOR",
                "exchange": "AAVE",
                "message": "Executing flash loan arbitrage: USDC",
                "details": {"amount": 100000, "fee": 0.09},
            },
            {
                "timestamp": "2026-01-01 00:00:35.793",
                "level": "INFO",
                "module": "FUTURES_SPOT_EXECUTOR",
                "exchange": "BINANCE",
                "message": "Executing basis trade: BTC/USD",
                "details": {"spot": 94200.00, "futures": 94350.00},
            },
            {
                "timestamp": "2026-01-01 00:00:40.890",
                "level": "ERROR",
                "module": "ORDER_EXECUTOR",
                "exchange": "BINANCE",
                "message": "Order failed: Insufficient balance for BTC/USD",
                "details": {"error_code": -2010, "required": 47100.00},
            },
            {
                "timestamp": "2026-01-01 00:00:45.901",
                "level": "INFO",
                "module": "OPPORTUNITY_SCANNER",
                "exchange": "ALL",
                "message": "Scan completed: 5 exchanges, 28 opportunities",
                "details": {"scan_time": 1.2, "cache_hit": 78},
            },
        ],
        "stats": {
            "total": 1234,
            "info": 1188,
            "warning": 34,
            "error": 12,
            "by_module": {
                "DEX_EXECUTOR": 234,
                "CROSS_EXCHANGE_EXECUTOR": 189,
                "TRIANGULAR_EXECUTOR": 156,
                "STATISTICAL_EXECUTOR": 145,
                "FLASH_LOAN_EXECUTOR": 98,
                "FUTURES_SPOT_EXECUTOR": 87,
                "OTHER": 325,
            },
        },
    }


async def get_reports_data() -> Dict[str, Any]:
    """Get reports data."""
    return {
        "reports": [
            {
                "id": "report_001",
                "name": "Daily Report",
                "date": "2026-01-01",
                "type": "daily",
                "format": "json",
                "size": "2.3 MB",
                "status": "generated",
                "url": "/reports/daily_2026-01-01.json",
            },
            {
                "id": "report_002",
                "name": "Weekly Report",
                "date": "2025-12-28",
                "type": "weekly",
                "format": "html",
                "size": "5.6 MB",
                "status": "generated",
                "url": "/reports/weekly_2025-12-28.html",
            },
            {
                "id": "report_003",
                "name": "Monthly Report",
                "date": "2025-12-01",
                "type": "monthly",
                "format": "pdf",
                "size": "12.4 MB",
                "status": "generated",
                "url": "/reports/monthly_2025-12-01.pdf",
            },
            {
                "id": "report_004",
                "name": "Performance Report",
                "date": "2025-12-31",
                "type": "performance",
                "format": "csv",
                "size": "3.7 MB",
                "status": "pending",
                "url": "/reports/performance_2025-12-31.csv",
            },
        ],
        "summary": {
            "total_reports": 24,
            "generated": 22,
            "pending": 2,
            "failed": 0,
            "total_size": 156.8,
        },
        "formats": {
            "json": 12,
            "html": 6,
            "pdf": 4,
            "csv": 2,
        },
    }


async def get_settings_data() -> Dict[str, Any]:
    """Get settings data."""
    return {
        "general": {
            "system_name": "NEXUS AI Trading System",
            "environment": "production",
            "log_level": "info",
            "auto_start": True,
        },
        "trading": {
            "max_position_size": 100000,
            "max_leverage": 3,
            "max_drawdown": 5.0,
            "stop_loss_percentage": 2.0,
            "take_profit_percentage": 5.0,
            "min_profit_threshold": 0.1,
        },
        "exchanges": {
            "binance": {"enabled": True, "api_key": "****1234", "secret": "****5678"},
            "bybit": {"enabled": True, "api_key": "****2345", "secret": "****6789"},
            "okx": {"enabled": True, "api_key": "****3456", "secret": "****7890"},
            "uniswap": {"enabled": True, "private_key": "****4567"},
            "pancakeswap": {"enabled": False, "private_key": ""},
        },
        "strategies": {
            "cross_exchange": {"enabled": True, "min_profit": 0.1, "max_slippage": 0.01},
            "dex": {"enabled": True, "min_profit": 0.2, "max_slippage": 0.02},
            "statistical": {"enabled": True, "zscore_entry": 2.0, "zscore_exit": 0.5},
            "triangular": {"enabled": True, "min_profit": 0.15, "max_path_length": 5},
            "flash_loan": {"enabled": False, "max_amount": 100000},
        },
        "security": {
            "two_factor_auth": True,
            "session_timeout": 3600,
            "ip_whitelist": ["192.168.1.0/24"],
            "api_rate_limit": 100,
        },
    }


async def get_strategies_data() -> Dict[str, Any]:
    """Get strategies data."""
    return {
        "strategies": [
            {
                "id": "cross_exchange",
                "name": "Cross-Exchange Arbitrage",
                "type": "arbitrage",
                "status": "running",
                "description": "Arbitrage across different centralized exchanges",
                "profit_24h": 567.89,
                "trades_24h": 45,
                "win_rate": 82.2,
                "enabled": True,
            },
            {
                "id": "dex",
                "name": "DEX Arbitrage",
                "type": "arbitrage",
                "status": "running",
                "description": "Arbitrage on decentralized exchanges",
                "profit_24h": 345.67,
                "trades_24h": 32,
                "win_rate": 78.1,
                "enabled": True,
            },
            {
                "id": "statistical",
                "name": "Statistical Arbitrage",
                "type": "statistical",
                "status": "running",
                "description": "Uses statistical methods for arbitrage",
                "profit_24h": 234.56,
                "trades_24h": 28,
                "win_rate": 71.4,
                "enabled": True,
            },
            {
                "id": "triangular",
                "name": "Triangular Arbitrage",
                "type": "arbitrage",
                "status": "paused",
                "description": "Arbitrage across three trading pairs",
                "profit_24h": 178.90,
                "trades_24h": 22,
                "win_rate": 68.2,
                "enabled": False,
            },
            {
                "id": "flash_loan",
                "name": "Flash Loan Arbitrage",
                "type": "arbitrage",
                "status": "stopped",
                "description": "Capital-efficient arbitrage using flash loans",
                "profit_24h": 67.89,
                "trades_24h": 12,
                "win_rate": 66.7,
                "enabled": False,
            },
        ],
        "summary": {
            "total": 5,
            "running": 3,
            "paused": 1,
            "stopped": 1,
            "total_profit_24h": 1395.01,
            "total_trades_24h": 139,
        },
    }


# Package initialization
logger.info(f"Initializing Templates Package v{__version__}")
logger.info(f"Template directory: {TEMPLATE_DIR}")
logger.info(f"Components directory: {COMPONENTS_DIR}")
logger.info(f"Partials directory: {PARTIALS_DIR}")
logger.info(f"Found {len(list_templates())} templates")

# Create default templates if they don't exist
def _create_default_templates() -> None:
    """Create default template files if they don't exist."""
    default_templates = {
        "dashboard.html": """<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - NEXUS AI Trading</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    {% include 'partials/header.html' %}
    <div class="container">
        <div class="sidebar">
            {% include 'partials/sidebar.html' %}
        </div>
        <div class="main-content">
            <h1>Dashboard</h1>
            <div class="metrics-grid">
                {% for metric in data.metrics %}
                    {% include 'components/metric_card.html' with context %}
                {% endfor %}
            </div>
            {% include 'partials/alerts.html' %}
        </div>
    </div>
    {% include 'partials/footer.html' %}
</body>
</html>""",
        "exchanges.html": """<!DOCTYPE html>
<html>
<head>
    <title>Exchanges - NEXUS AI Trading</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    {% include 'partials/header.html' %}
    <div class="container">
        <div class="sidebar">
            {% include 'partials/sidebar.html' %}
        </div>
        <div class="main-content">
            <h1>Exchanges</h1>
            <div class="exchanges-grid">
                {% for exchange in data.exchanges %}
                    {% include 'components/exchange_card.html' with context %}
                {% endfor %}
            </div>
        </div>
    </div>
    {% include 'partials/footer.html' %}
</body>
</html>""",
        "opportunities.html": """<!DOCTYPE html>
<html>
<head>
    <title>Opportunities - NEXUS AI Trading</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    {% include 'partials/header.html' %}
    <div class="container">
        <div class="sidebar">
            {% include 'partials/sidebar.html' %}
        </div>
        <div class="main-content">
            <h1>Opportunities</h1>
            <div class="opportunities-list">
                {% for opportunity in data.opportunities %}
                    {% include 'components/opportunity_card.html' with context %}
                {% endfor %}
            </div>
        </div>
    </div>
    {% include 'partials/footer.html' %}
</body>
</html>""",
        "performance.html": """<!DOCTYPE html>
<html>
<head>
    <title>Performance - NEXUS AI Trading</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    {% include 'partials/header.html' %}
    <div class="container">
        <div class="sidebar">
            {% include 'partials/sidebar.html' %}
        </div>
        <div class="main-content">
            <h1>Performance</h1>
            <div class="performance-metrics">
                {% include 'partials/metrics.html' %}
            </div>
            <div class="charts">
                {% for chart in data.charts %}
                    {% include 'components/chart_card.html' with context %}
                {% endfor %}
            </div>
        </div>
    </div>
    {% include 'partials/footer.html' %}
</body>
</html>""",
    }
    
    for template_name, content in default_templates.items():
        template_path = TEMPLATE_DIR / template_name
        if not template_path.exists():
            save_template(template_name, content)
            logger.info(f"Created default template: {template_name}")

_create_default_templates()


# Lazy imports for circular dependency resolution
def __getattr__(name: str) -> Any:
    """
    Lazy import for submodules.
    
    This allows for clean imports while avoiding circular dependencies.
    """
    if name in ['components', 'partials']:
        raise AttributeError(f"Module {name} not loaded. Please import directly.")
    raise AttributeError(f"module {__name__} has no attribute {name}")

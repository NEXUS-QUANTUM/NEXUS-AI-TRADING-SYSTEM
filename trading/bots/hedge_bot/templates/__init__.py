# trading/bots/hedge_bot/templates/__init__.py

"""
NEXUS AI TRADING SYSTEM - Hedge Bot Templates Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Template package initialization for the Hedge Bot web interface.
Manages template loading, context processors, and template utilities.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Template package metadata
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package name
PACKAGE_NAME = "nexus_hedge_bot_templates"

# Template directories
TEMPLATE_DIRS = [
    Path(__file__).parent,
    Path(__file__).parent / "components",
    Path(__file__).parent / "partials",
]

# Template settings
TEMPLATE_SETTINGS = {
    "debug": True,
    "auto_reload": True,
    "directory": str(Path(__file__).parent),
    "loaders": [
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",
    ],
    "context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.template.context_processors.static",
        "nexus.trading.context_processors.global_context",
        "nexus.trading.context_processors.user_context",
        "nexus.trading.context_processors.exchange_context",
    ],
}

# Template tags
TEMPLATE_TAGS = {
    "nexus_tags": "nexus.trading.templatetags.nexus_tags",
    "static": "django.templatetags.static",
    "i18n": "django.templatetags.i18n",
    "l10n": "django.templatetags.l10n",
    "tz": "django.templatetags.tz",
}

# Template filters
TEMPLATE_FILTERS = {
    "currency": "nexus.trading.templatetags.nexus_tags.currency",
    "format_price": "nexus.trading.templatetags.nexus_tags.format_price",
    "format_volume": "nexus.trading.templatetags.nexus_tags.format_volume",
    "format_number": "nexus.trading.templatetags.nexus_tags.format_number",
    "format_date": "nexus.trading.templatetags.nexus_tags.format_date",
    "format_time": "nexus.trading.templatetags.nexus_tags.format_time",
    "truncate": "nexus.trading.templatetags.nexus_tags.truncate",
    "safe_json": "nexus.trading.templatetags.nexus_tags.safe_json",
    "add_class": "nexus.trading.templatetags.nexus_tags.add_class",
    "placeholder": "nexus.trading.templatetags.nexus_tags.placeholder",
}

# Exported variables
__all__ = [
    "__version__",
    "__author__",
    "__copyright__",
    "PACKAGE_NAME",
    "TEMPLATE_DIRS",
    "TEMPLATE_SETTINGS",
    "TEMPLATE_TAGS",
    "TEMPLATE_FILTERS",
]

# Template context processors
def global_context(request: Any) -> Dict[str, Any]:
    """
    Global template context processor.
    
    Provides global variables available to all templates.
    """
    from django.conf import settings
    
    return {
        "nexus_version": getattr(settings, "NEXUS_VERSION", "3.0.0"),
        "nexus_environment": getattr(settings, "NEXUS_ENVIRONMENT", "production"),
        "nexus_debug": getattr(settings, "DEBUG", False),
        "nexus_site_name": getattr(settings, "NEXUS_SITE_NAME", "NEXUS AI Trading"),
        "nexus_support_email": getattr(settings, "NEXUS_SUPPORT_EMAIL", "support@nexustradingia.com"),
        "nexus_company_name": getattr(settings, "NEXUS_COMPANY_NAME", "NEXUS QUANTUM LTD"),
        "nexus_copyright_year": getattr(settings, "NEXUS_COPYRIGHT_YEAR", "2026"),
        "nexus_logo_url": getattr(settings, "NEXUS_LOGO_URL", "/static/images/nexus-logo-light.svg"),
        "nexus_favicon_url": getattr(settings, "NEXUS_FAVICON_URL", "/static/images/nexus-favicon.svg"),
    }

def user_context(request: Any) -> Dict[str, Any]:
    """
    User context processor.
    
    Provides user-specific variables to templates.
    """
    user = getattr(request, "user", None)
    
    if user and user.is_authenticated:
        return {
            "user_id": getattr(user, "id", None),
            "user_name": getattr(user, "username", "Guest"),
            "user_email": getattr(user, "email", ""),
            "user_role": getattr(user, "role", "Trader"),
            "user_avatar": getattr(user, "avatar", "/static/images/default-avatar.png"),
            "user_is_authenticated": True,
            "user_permissions": getattr(user, "permissions", []),
        }
    
    return {
        "user_id": None,
        "user_name": "Guest",
        "user_email": "",
        "user_role": "Trader",
        "user_avatar": "/static/images/default-avatar.png",
        "user_is_authenticated": False,
        "user_permissions": [],
    }

def exchange_context(request: Any) -> Dict[str, Any]:
    """
    Exchange context processor.
    
    Provides exchange-specific variables to templates.
    """
    from django.conf import settings
    
    default_exchange = getattr(settings, "DEFAULT_EXCHANGE", "binance")
    exchange_name = request.GET.get("exchange", default_exchange)
    
    exchange_names = {
        "binance": "Binance",
        "bybit": "Bybit",
        "kraken": "Kraken",
        "coinbase": "Coinbase",
        "okx": "OKX",
        "ftx": "FTX",
        "gate": "Gate.io",
        "huobi": "Huobi",
        "kucoin": "KuCoin",
        "bitfinex": "Bitfinex",
        "deribit": "Deribit",
        "bitmex": "BitMEX",
    }
    
    exchange_icons = {
        "binance": "/static/logos/binance-logo.png",
        "bybit": "/static/logos/bybit-logo.png",
        "kraken": "/static/logos/kraken-logo.png",
        "coinbase": "/static/logos/coinbase-logo.png",
        "okx": "/static/logos/okx-logo.png",
        "ftx": "/static/logos/ftx-logo.png",
        "gate": "/static/logos/gate-logo.png",
        "huobi": "/static/logos/huobi-logo.png",
        "kucoin": "/static/logos/kucoin-logo.png",
        "bitfinex": "/static/logos/bitfinex-logo.png",
        "deribit": "/static/logos/deribit-logo.png",
        "bitmex": "/static/logos/bitmex-logo.png",
    }
    
    exchange_statuses = {
        "binance": "online",
        "bybit": "online",
        "kraken": "online",
        "coinbase": "online",
        "okx": "online",
        "ftx": "offline",
        "gate": "online",
        "huobi": "online",
        "kucoin": "online",
        "bitfinex": "online",
        "deribit": "online",
        "bitmex": "online",
    }
    
    return {
        "exchange": exchange_name,
        "exchange_name": exchange_names.get(exchange_name, exchange_name.capitalize()),
        "exchange_icon": exchange_icons.get(exchange_name, "/static/logos/default-logo.png"),
        "exchange_status": exchange_statuses.get(exchange_name, "unknown"),
        "exchange_list": [
            {"id": k, "name": v, "icon": exchange_icons.get(k, ""), "status": exchange_statuses.get(k, "unknown")}
            for k, v in exchange_names.items()
        ],
        "default_exchange": default_exchange,
    }

# Template tags
class NexusTemplateTags:
    """
    Custom template tags for NEXUS templates.
    """
    
    @staticmethod
    def currency(value: float, currency: str = "USD") -> str:
        """Format currency value."""
        from nexus.trading.utils.formatters import format_currency
        return format_currency(value, currency)
    
    @staticmethod
    def format_price(value: float, precision: int = 2) -> str:
        """Format price value."""
        from nexus.trading.utils.formatters import format_price
        return format_price(value, precision)
    
    @staticmethod
    def format_volume(value: float) -> str:
        """Format volume value."""
        from nexus.trading.utils.formatters import format_volume
        return format_volume(value)
    
    @staticmethod
    def format_number(value: float, precision: int = 2) -> str:
        """Format number value."""
        from nexus.trading.utils.formatters import format_number
        return format_number(value, precision)
    
    @staticmethod
    def format_date(timestamp: float, fmt: str = "%Y-%m-%d") -> str:
        """Format date from timestamp."""
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(fmt)
    
    @staticmethod
    def format_time(timestamp: float, fmt: str = "%H:%M:%S") -> str:
        """Format time from timestamp."""
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(fmt)
    
    @staticmethod
    def truncate(value: str, length: int = 50, suffix: str = "...") -> str:
        """Truncate string to specified length."""
        if len(value) <= length:
            return value
        return value[:length] + suffix
    
    @staticmethod
    def safe_json(value: Any) -> str:
        """Convert value to safe JSON string."""
        import json
        return json.dumps(value, default=str)
    
    @staticmethod
    def add_class(value: str, class_name: str) -> str:
        """Add CSS class to HTML element."""
        return f'{value} class="{class_name}"' if value and class_name else value
    
    @staticmethod
    def placeholder(value: str) -> str:
        """Add placeholder attribute to HTML element."""
        return f'{value} placeholder="..."' if value else ""

# Template utilities
def get_template_path(template_name: str) -> Path:
    """Get full path to a template file."""
    for template_dir in TEMPLATE_DIRS:
        template_path = template_dir / template_name
        if template_path.exists():
            return template_path
    raise FileNotFoundError(f"Template not found: {template_name}")

def list_templates(directory: Optional[Path] = None) -> List[str]:
    """List all available templates."""
    if directory is None:
        directory = TEMPLATE_DIRS[0]
    
    templates = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                rel_path = os.path.relpath(os.path.join(root, file), directory)
                templates.append(rel_path)
    
    return sorted(templates)

def get_component_templates() -> List[str]:
    """List all component templates."""
    components_dir = TEMPLATE_DIRS[1] if len(TEMPLATE_DIRS) > 1 else None
    if components_dir and components_dir.exists():
        return list_templates(components_dir)
    return []

def get_partial_templates() -> List[str]:
    """List all partial templates."""
    partials_dir = TEMPLATE_DIRS[2] if len(TEMPLATE_DIRS) > 2 else None
    if partials_dir and partials_dir.exists():
        return list_templates(partials_dir)
    return []

# Initialize package
def init_templates() -> None:
    """Initialize the templates package."""
    logger.info(f"Initializing templates package v{__version__}")
    logger.info(f"Template directories: {TEMPLATE_DIRS}")
    
    # Create necessary directories if they don't exist
    for template_dir in TEMPLATE_DIRS:
        template_dir.mkdir(exist_ok=True, parents=True)
    
    # Create __init__.py files in subdirectories
    for template_dir in TEMPLATE_DIRS:
        init_file = template_dir / "__init__.py"
        if not init_file.exists():
            init_file.touch()
    
    logger.info("Templates package initialized successfully")

# Cleanup
def cleanup_templates() -> None:
    """Cleanup the templates package."""
    logger.info("Cleaning up templates package")
    # Add cleanup logic here if needed

# Package version
VERSION = __version__

# Export all
__all__ = [
    "__version__",
    "__author__",
    "__copyright__",
    "PACKAGE_NAME",
    "TEMPLATE_DIRS",
    "TEMPLATE_SETTINGS",
    "TEMPLATE_TAGS",
    "TEMPLATE_FILTERS",
    "global_context",
    "user_context",
    "exchange_context",
    "NexusTemplateTags",
    "get_template_path",
    "list_templates",
    "get_component_templates",
    "get_partial_templates",
    "init_templates",
    "cleanup_templates",
    "VERSION",
]

# Auto-initialize if this is the main package
if __name__ == "__main__":
    init_templates()
    print(f"NEXUS Hedge Bot Templates v{__version__} initialized successfully")
    print(f"Template directories: {TEMPLATE_DIRS}")
    print(f"Available templates: {len(list_templates())}")

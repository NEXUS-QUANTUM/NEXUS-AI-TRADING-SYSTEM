# trading/bots/ai_bot/templates/__init__.py
# NEXUS AI TRADING SYSTEM - Templates Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Templates Module for NEXUS AI Trading Bot Dashboard.

This module provides all HTML templates for the AI Bot dashboard including:
- Main dashboard
- Performance analytics
- Alerts management
- Settings configuration
- Logs viewer
- Reports generation
- Trade history
- Position management
- System status
- User profile
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Version
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Module logger
import logging
logger = logging.getLogger("nexus.trading.bot.templates")

# ============================================================================
# Template Constants
# ============================================================================

TEMPLATE_DIR = Path(__file__).parent

TEMPLATES = {
    "dashboard": "dashboard.html",
    "performance": "performance.html",
    "alerts": "alerts.html",
    "settings": "settings.html",
    "logs": "logs.html",
    "reports": "reports.html",
    "trades": "trades.html",
    "positions": "positions.html",
    "status": "status.html",
    "profile": "profile.html",
}


# ============================================================================
# Template Manager
# ============================================================================

class TemplateManager:
    """
    Template Manager for NEXUS AI Trading Bot Dashboard.
    Provides template loading, rendering, and management.
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize template manager.

        Args:
            template_dir: Directory containing templates
        """
        self.template_dir = template_dir or TEMPLATE_DIR
        self._template_cache: Dict[str, str] = {}
        self._template_dependencies: Dict[str, List[str]] = {}
        self._partials: Dict[str, str] = {}

        # Load partials
        self._load_partials()

        logger.info(
            "TemplateManager initialized",
            extra={
                "template_dir": str(self.template_dir),
                "templates_available": len(TEMPLATES),
            }
        )

    # ========================================================================
    # Template Loading
    # ========================================================================

    def load_template(self, name: str, force_reload: bool = False) -> Optional[str]:
        """
        Load a template by name.

        Args:
            name: Template name
            force_reload: Force reload from disk

        Returns:
            Template content or None
        """
        if name not in TEMPLATES:
            logger.warning(f"Template {name} not found")
            return None

        if not force_reload and name in self._template_cache:
            return self._template_cache[name]

        file_path = self.template_dir / TEMPLATES[name]

        if not file_path.exists():
            logger.error(f"Template file not found: {file_path}")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self._template_cache[name] = content
            return content

        except Exception as e:
            logger.error(f"Error loading template {name}: {e}")
            return None

    def render_template(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        force_reload: bool = False,
    ) -> Optional[str]:
        """
        Render a template with context.

        Args:
            name: Template name
            context: Template context
            force_reload: Force reload from disk

        Returns:
            Rendered template or None
        """
        template = self.load_template(name, force_reload)

        if template is None:
            return None

        context = context or {}

        # Process template
        rendered = self._process_template(template, context)

        return rendered

    def render_partial(
        self,
        partial_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Render a partial template.

        Args:
            partial_name: Partial name
            context: Template context

        Returns:
            Rendered partial or None
        """
        if partial_name not in self._partials:
            partial_file = self.template_dir / "partials" / f"{partial_name}.html"
            if partial_file.exists():
                try:
                    with open(partial_file, 'r', encoding='utf-8') as f:
                        self._partials[partial_name] = f.read()
                except Exception as e:
                    logger.error(f"Error loading partial {partial_name}: {e}")
                    return None
            else:
                logger.warning(f"Partial {partial_name} not found")
                return None

        template = self._partials.get(partial_name)
        if template is None:
            return None

        context = context or {}
        return self._process_template(template, context)

    # ========================================================================
    # Template Processing
    # ========================================================================

    def _process_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        Process a template with context.

        Args:
            template: Template content
            context: Template context

        Returns:
            Processed template
        """
        # Simple variable substitution
        result = template

        # Replace {{ variable }} placeholders
        import re
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}'

        def replace_var(match):
            var_path = match.group(1)
            value = self._get_nested_value(context, var_path)
            return str(value) if value is not None else ''

        result = re.sub(pattern, replace_var, result)

        # Handle include statements
        include_pattern = r'\{\%\s*include\s+[\'"]([^\'"]+)[\'"]\s*\%\}'

        def include_partial(match):
            partial_name = match.group(1)
            return self.render_partial(partial_name, context) or ''

        result = re.sub(include_pattern, include_partial, result)

        # Handle for loops
        for_pattern = r'\{\%\s*for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*\%\}(.*?)\{\%\s*endfor\s*\%\}'

        def process_for(match):
            var_name = match.group(1)
            iterable_path = match.group(2)
            body = match.group(3)

            iterable = self._get_nested_value(context, iterable_path)

            if not isinstance(iterable, (list, tuple)):
                return ''

            result_parts = []
            for item in iterable:
                if isinstance(item, dict):
                    # Create a new context with the item
                    item_context = {var_name: item}
                    # Merge with parent context
                    merged_context = {**context, **item_context}
                    result_parts.append(self._process_template(body, merged_context))
                else:
                    item_context = {var_name: item}
                    merged_context = {**context, **item_context}
                    result_parts.append(self._process_template(body, merged_context))

            return ''.join(result_parts)

        result = re.sub(for_pattern, process_for, result, flags=re.DOTALL)

        # Handle if statements
        if_pattern = r'\{\%\s*if\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*\%\}(.*?)(?:\{\%\s*else\s*\%\}(.*?))?\{\%\s*endif\s*\%\}'

        def process_if(match):
            condition_path = match.group(1)
            true_body = match.group(2)
            false_body = match.group(3) if len(match.groups()) > 2 and match.group(3) is not None else ''

            value = self._get_nested_value(context, condition_path)

            if value:
                return self._process_template(true_body, context)
            else:
                return self._process_template(false_body, context)

        result = re.sub(if_pattern, process_if, result, flags=re.DOTALL)

        # Handle safe filter
        safe_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\|\s*safe\s*\}\}'

        def safe_filter(match):
            var_path = match.group(1)
            value = self._get_nested_value(context, var_path)
            return str(value) if value is not None else ''

        result = re.sub(safe_pattern, safe_filter, result)

        return result

    def _get_nested_value(self, context: Dict[str, Any], path: str) -> Any:
        """
        Get a nested value from context.

        Args:
            context: Context dictionary
            path: Dot-separated path

        Returns:
            Value or None
        """
        parts = path.split('.')
        value = context

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, (list, tuple)) and part.isdigit():
                idx = int(part)
                if 0 <= idx < len(value):
                    value = value[idx]
                else:
                    return None
            else:
                return None

        return value

    # ========================================================================
    # Partial Loading
    # ========================================================================

    def _load_partials(self) -> None:
        """Load partial templates."""
        partials_dir = self.template_dir / "partials"

        if not partials_dir.exists():
            return

        for file_path in partials_dir.glob("*.html"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._partials[file_path.stem] = content
            except Exception as e:
                logger.error(f"Error loading partial {file_path.name}: {e}")

    # ========================================================================
    # Template Management
    # ========================================================================

    def get_template_names(self) -> List[str]:
        """
        Get all template names.

        Returns:
            List of template names
        """
        return list(TEMPLATES.keys())

    def get_template_path(self, name: str) -> Optional[Path]:
        """
        Get template file path.

        Args:
            name: Template name

        Returns:
            Path or None
        """
        if name not in TEMPLATES:
            return None
        return self.template_dir / TEMPLATES[name]

    def template_exists(self, name: str) -> bool:
        """
        Check if a template exists.

        Args:
            name: Template name

        Returns:
            True if exists
        """
        path = self.get_template_path(name)
        return path is not None and path.exists()

    def reload_templates(self) -> None:
        """Reload all templates from disk."""
        self._template_cache.clear()
        self._partials.clear()
        self._load_partials()
        logger.info("Templates reloaded")

    def add_partial(self, name: str, content: str) -> None:
        """
        Add a partial template.

        Args:
            name: Partial name
            content: Partial content
        """
        self._partials[name] = content

    def remove_partial(self, name: str) -> None:
        """
        Remove a partial template.

        Args:
            name: Partial name
        """
        if name in self._partials:
            del self._partials[name]

    # ========================================================================
    # Performance Metrics
    # ========================================================================

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            "templates_loaded": len(self._template_cache),
            "partials_loaded": len(self._partials),
            "total_templates": len(TEMPLATES),
            "template_names": list(TEMPLATES.keys()),
        }


# ============================================================================
# Singleton Access
# ============================================================================

_template_manager = None


def get_template_manager() -> TemplateManager:
    """
    Get the global template manager instance.

    Returns:
        TemplateManager instance
    """
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager


def render_template(
    name: str,
    context: Optional[Dict[str, Any]] = None,
    force_reload: bool = False,
) -> Optional[str]:
    """
    Quick access function to render a template.

    Args:
        name: Template name
        context: Template context
        force_reload: Force reload from disk

    Returns:
        Rendered template or None
    """
    manager = get_template_manager()
    return manager.render_template(name, context, force_reload)


def render_partial(
    name: str,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Quick access function to render a partial.

    Args:
        name: Partial name
        context: Template context

    Returns:
        Rendered partial or None
    """
    manager = get_template_manager()
    return manager.render_partial(name, context)


def get_template(name: str) -> Optional[str]:
    """
    Quick access function to get a template.

    Args:
        name: Template name

    Returns:
        Template content or None
    """
    manager = get_template_manager()
    return manager.load_template(name)


def template_exists(name: str) -> bool:
    """
    Quick access function to check if a template exists.

    Args:
        name: Template name

    Returns:
        True if exists
    """
    manager = get_template_manager()
    return manager.template_exists(name)


# ============================================================================
# Module Information
# ============================================================================

MODULE_INFO = {
    "name": "Templates",
    "version": __version__,
    "author": __author__,
    "copyright": __copyright__,
    "description": "HTML templates for NEXUS AI Trading Bot Dashboard",
    "templates": list(TEMPLATES.keys()),
    "partials": ["navbar", "sidebar", "footer", "header", "alerts_list"],
}


def get_module_info() -> Dict[str, Any]:
    """Get module information."""
    return MODULE_INFO


def get_version() -> str:
    """Get module version."""
    return __version__


# ============================================================================
# Module Initialization
# ============================================================================

def initialize_module(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize the templates module.

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary containing initialized components
    """
    logger.info("Initializing Templates Module...")

    components = {}

    try:
        # Initialize template manager
        manager = TemplateManager()
        components["manager"] = manager

        logger.info("Templates Module initialized successfully")
        logger.info(f"  - Templates: {len(TEMPLATES)}")
        logger.info(f"  - Partials: {len(manager._partials)}")

    except Exception as e:
        logger.error(f"Failed to initialize Templates Module: {e}")
        raise

    return components


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Print module info
    print(f"Templates Module v{__version__}")
    print(f"Author: {__author__}")
    print("\nAvailable Templates:")
    for name in get_template_names():
        print(f"  - {name}")

"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Formatters Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de formatage pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import json
import re
import html
import xml
from datetime import datetime, date, time, timedelta
from decimal import Decimal, getcontext
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Callable,
    TypeVar,
    Generic
)
from enum import Enum
import numbers
import math
import locale
import string
import textwrap
import unicodedata
import difflib
import colorama
from colorama import Fore, Back, Style, init as colorama_init
from dataclasses import is_dataclass, asdict
from collections.abc import Iterable

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

# Unités pour les tailles
SIZE_UNITS = {
    'B': 1,
    'KB': 1024,
    'MB': 1024 ** 2,
    'GB': 1024 ** 3,
    'TB': 1024 ** 4,
    'PB': 1024 ** 5,
}

# Unités pour les durées
TIME_UNITS = {
    'ns': 1e-9,
    'μs': 1e-6,
    'ms': 1e-3,
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
    'w': 604800,
}

# Unités pour les grandes nombres
NUMBER_UNITS = {
    'K': 1e3,
    'M': 1e6,
    'B': 1e9,
    'T': 1e12,
    'Q': 1e15,
}

# ============================================================
# CURRENCY FORMATTER
# ============================================================

class CurrencyFormatter:
    """Formateur de devises"""
    
    # Symboles par devise
    SYMBOLS = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CNY': '¥',
        'CHF': 'Fr',
        'CAD': 'C$',
        'AUD': 'A$',
        'NZD': 'NZ$',
        'BTC': '₿',
        'ETH': 'Ξ',
        'SOL': '◎',
        'XRP': '✕',
        'ADA': '₳',
        'DOT': '●',
        'USDT': '₮',
        'BUSD': '₿',
        'USDC': '₮',
        'DAI': '◈',
    }
    
    # Formats par devise
    FORMATS = {
        'USD': {'decimals': 2, 'separator': ',', 'decimal': '.', 'symbol': '$', 'position': 'before'},
        'EUR': {'decimals': 2, 'separator': '.', 'decimal': ',', 'symbol': '€', 'position': 'after'},
        'GBP': {'decimals': 2, 'separator': ',', 'decimal': '.', 'symbol': '£', 'position': 'before'},
        'JPY': {'decimals': 0, 'separator': ',', 'decimal': '.', 'symbol': '¥', 'position': 'before'},
        'BTC': {'decimals': 8, 'separator': ',', 'decimal': '.', 'symbol': '₿', 'position': 'before'},
        'ETH': {'decimals': 8, 'separator': ',', 'decimal': '.', 'symbol': 'Ξ', 'position': 'before'},
        'default': {'decimals': 2, 'separator': ',', 'decimal': '.', 'symbol': '', 'position': 'before'},
    }
    
    @staticmethod
    def format(
        value: Any,
        currency: str = 'USD',
        decimals: Optional[int] = None,
        symbol: bool = True,
        separator: bool = True,
        position: str = 'before'
    ) -> str:
        """
        Formate un montant en devise
        
        Args:
            value: Montant à formater
            currency: Code devise
            decimals: Nombre de décimales
            symbol: Afficher le symbole
            separator: Utiliser le séparateur de milliers
            position: Position du symbole ('before', 'after')
            
        Returns:
            str: Montant formaté
        """
        try:
            num = float(value)
        except (ValueError, TypeError):
            return str(value)
        
        # Récupérer le format
        fmt = CurrencyFormatter.FORMATS.get(currency, CurrencyFormatter.FORMATS['default'])
        
        if decimals is None:
            decimals = fmt['decimals']
        
        # Arrondir
        num = round(num, decimals)
        
        # Formatage du nombre
        if decimals >= 0:
            if separator:
                formatted = f"{num:,.{decimals}f}"
                formatted = formatted.replace(',', fmt['separator']).replace('.', fmt['decimal'])
            else:
                formatted = f"{num:.{decimals}f}"
        else:
            formatted = str(num)
        
        # Ajouter le symbole
        if symbol:
            symbol_char = CurrencyFormatter.SYMBOLS.get(currency, currency)
            if position == 'before':
                formatted = f"{symbol_char}{formatted}"
            else:
                formatted = f"{formatted} {symbol_char}"
        
        return formatted
    
    @staticmethod
    def parse(value: str, currency: str = 'USD') -> float:
        """
        Parse un montant formaté
        
        Args:
            value: Chaîne à parser
            currency: Code devise
            
        Returns:
            float: Montant parsé
        """
        if not value:
            return 0.0
        
        # Supprimer le symbole
        symbol = CurrencyFormatter.SYMBOLS.get(currency, '')
        if symbol and symbol in value:
            value = value.replace(symbol, '').strip()
        
        # Supprimer les séparateurs
        fmt = CurrencyFormatter.FORMATS.get(currency, CurrencyFormatter.FORMATS['default'])
        value = value.replace(fmt['separator'], '').replace(fmt['decimal'], '.')
        
        try:
            return float(value)
        except ValueError:
            return 0.0

# ============================================================
# NUMBER FORMATTER
# ============================================================

class NumberFormatter:
    """Formateur de nombres"""
    
    @staticmethod
    def format(
        value: Any,
        decimals: int = 2,
        separator: bool = True,
        decimal_separator: str = '.',
        thousand_separator: str = ',',
        min_decimals: int = 0,
        max_decimals: Optional[int] = None,
        padding: bool = False
    ) -> str:
        """
        Formate un nombre
        
        Args:
            value: Nombre à formater
            decimals: Nombre de décimales
            separator: Utiliser le séparateur de milliers
            decimal_separator: Séparateur décimal
            thousand_separator: Séparateur de milliers
            min_decimals: Nombre minimum de décimales
            max_decimals: Nombre maximum de décimales
            padding: Ajouter des zéros
            
        Returns:
            str: Nombre formaté
        """
        try:
            num = float(value)
        except (ValueError, TypeError):
            return str(value)
        
        # Déterminer le nombre de décimales
        if max_decimals is not None:
            num = round(num, max_decimals)
        
        if decimals > 0:
            if separator:
                formatted = f"{num:,.{decimals}f}"
                formatted = formatted.replace(',', thousand_separator)
                if decimal_separator != '.':
                    formatted = formatted.replace('.', decimal_separator)
            else:
                formatted = f"{num:.{decimals}f}"
        else:
            formatted = f"{int(num):,}" if separator else str(int(num))
            if decimal_separator != '.' and separator:
                formatted = formatted.replace(',', thousand_separator)
        
        # Ajouter des zéros si nécessaire
        if padding and decimals > 0:
            if decimal_separator not in formatted:
                formatted += decimal_separator + '0' * decimals
        
        return formatted
    
    @staticmethod
    def format_percent(
        value: Any,
        decimals: int = 2,
        include_sign: bool = True
    ) -> str:
        """
        Formate un pourcentage
        
        Args:
            value: Valeur à formater
            decimals: Nombre de décimales
            include_sign: Inclure le signe
            
        Returns:
            str: Pourcentage formaté
        """
        try:
            num = float(value)
        except (ValueError, TypeError):
            return str(value)
        
        # Convertir en pourcentage
        num = num * 100
        
        formatted = f"{num:.{decimals}f}%"
        
        if include_sign and num > 0:
            formatted = f"+{formatted}"
        elif include_sign and num < 0:
            formatted = f"{formatted}"
        
        return formatted
    
    @staticmethod
    def format_scientific(
        value: Any,
        precision: int = 3
    ) -> str:
        """
        Formate un nombre en notation scientifique
        
        Args:
            value: Nombre à formater
            precision: Précision
            
        Returns:
            str: Nombre formaté
        """
        try:
            num = float(value)
        except (ValueError, TypeError):
            return str(value)
        
        if num == 0:
            return "0"
        
        exponent = int(math.floor(math.log10(abs(num))))
        mantissa = num / (10 ** exponent)
        
        return f"{mantissa:.{precision}f}e{exponent:+d}"
    
    @staticmethod
    def format_engineering(
        value: Any,
        precision: int = 3
    ) -> str:
        """
        Formate un nombre en notation ingénieur
        
        Args:
            value: Nombre à formater
            precision: Précision
            
        Returns:
            str: Nombre formaté
        """
        try:
            num = float(value)
        except (ValueError, TypeError):
            return str(value)
        
        if num == 0:
            return "0"
        
        exponent = int(math.floor(math.log10(abs(num))))
        exponent = exponent - (exponent % 3)
        mantissa = num / (10 ** exponent)
        
        return f"{mantissa:.{precision}f}e{exponent:+d}"
    
    @staticmethod
    def format_human(
        value: Any,
        precision: int = 2,
        base: int = 1024
    ) -> str:
        """
        Formate un nombre en format lisible
        
        Args:
            value: Nombre à formater
            precision: Précision
            base: Base (1000 ou 1024)
            
        Returns:
            str: Nombre formaté
        """
        try:
            num = float(value)
        except (ValueError, TypeError):
            return str(value)
        
        if num == 0:
            return "0"
        
        sign = "-" if num < 0 else ""
        num = abs(num)
        
        units = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
        
        for unit in units:
            if num < base:
                formatted = f"{num:.{precision}f}{unit}"
                break
            num /= base
        else:
            formatted = f"{num:.{precision}f}{units[-1]}"
        
        return f"{sign}{formatted}"

# ============================================================
# DATE TIME FORMATTER
# ============================================================

class DateTimeFormatter:
    """Formateur de dates et heures"""
    
    @staticmethod
    def format_datetime(
        dt: Optional[datetime],
        fmt: str = 'YYYY-MM-DD HH:mm:ss',
        tz: Optional[str] = None
    ) -> str:
        """
        Formate une date/heure
        
        Args:
            dt: Date/heure à formater
            fmt: Format (support token substitution)
            tz: Fuseau horaire
            
        Returns:
            str: Date/heure formatée
        """
        if dt is None:
            return ''
        
        # Convertir le fuseau horaire
        if tz:
            import pytz
            dt = dt.astimezone(pytz.timezone(tz))
        
        # Substituer les tokens
        tokens = {
            'YYYY': dt.strftime('%Y'),
            'YY': dt.strftime('%y'),
            'MM': dt.strftime('%m'),
            'M': dt.strftime('%-m') if hasattr(dt, 'strftime') else dt.strftime('%m').lstrip('0'),
            'DD': dt.strftime('%d'),
            'D': dt.strftime('%-d') if hasattr(dt, 'strftime') else dt.strftime('%d').lstrip('0'),
            'HH': dt.strftime('%H'),
            'H': dt.strftime('%-H') if hasattr(dt, 'strftime') else dt.strftime('%H').lstrip('0'),
            'hh': dt.strftime('%I'),
            'h': dt.strftime('%-I') if hasattr(dt, 'strftime') else dt.strftime('%I').lstrip('0'),
            'mm': dt.strftime('%M'),
            'm': dt.strftime('%-M') if hasattr(dt, 'strftime') else dt.strftime('%M').lstrip('0'),
            'ss': dt.strftime('%S'),
            's': dt.strftime('%-S') if hasattr(dt, 'strftime') else dt.strftime('%S').lstrip('0'),
            'SSS': dt.strftime('%f')[:3],
            'SS': dt.strftime('%f')[:2],
            'S': dt.strftime('%f')[:1],
            'AMPM': dt.strftime('%p'),
            'ampm': dt.strftime('%p').lower(),
            'TZD': dt.strftime('%z'),
            'TZN': dt.strftime('%Z'),
            'DAY': dt.strftime('%A'),
            'Day': dt.strftime('%a'),
            'MONTH': dt.strftime('%B'),
            'Month': dt.strftime('%b'),
            'DOY': dt.strftime('%j'),
            'WOY': dt.strftime('%W'),
        }
        
        for token, value in tokens.items():
            fmt = fmt.replace(token, value)
        
        return fmt
    
    @staticmethod
    def format_date(
        dt: Optional[datetime],
        fmt: str = 'YYYY-MM-DD'
    ) -> str:
        """
        Formate une date
        
        Args:
            dt: Date à formater
            fmt: Format
            
        Returns:
            str: Date formatée
        """
        return DateTimeFormatter.format_datetime(dt, fmt)
    
    @staticmethod
    def format_time(
        dt: Optional[datetime],
        fmt: str = 'HH:mm:ss'
    ) -> str:
        """
        Formate une heure
        
        Args:
            dt: Heure à formater
            fmt: Format
            
        Returns:
            str: Heure formatée
        """
        return DateTimeFormatter.format_datetime(dt, fmt)
    
    @staticmethod
    def format_duration(
        seconds: float,
        fmt: str = 'auto',
        short: bool = False
    ) -> str:
        """
        Formate une durée en secondes
        
        Args:
            seconds: Durée en secondes
            fmt: Format ('auto', 'detailed', 'short', 'compact')
            short: Format court
            
        Returns:
            str: Durée formatée
        """
        if seconds < 0:
            seconds = abs(seconds)
            sign = '-'
        else:
            sign = ''
        
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        millis = int((seconds - int(seconds)) * 1000)
        
        if fmt == 'auto':
            if days > 0:
                fmt = 'detailed'
            elif hours > 0:
                fmt = 'detailed'
            elif minutes > 0:
                fmt = 'detailed'
            else:
                fmt = 'compact'
        
        if fmt == 'detailed':
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if secs > 0:
                parts.append(f"{secs:.0f}s")
            if not parts:
                parts.append("0s")
            return sign + " ".join(parts)
        
        elif fmt == 'compact':
            if days > 0:
                return f"{sign}{days}d {hours}h"
            elif hours > 0:
                return f"{sign}{hours}h {minutes}m"
            elif minutes > 0:
                return f"{sign}{minutes}m {secs:.0f}s"
            elif secs > 0:
                return f"{sign}{secs:.1f}s"
            else:
                return f"{sign}0s"
        
        else:  # short
            if days > 0:
                return f"{sign}{days}d"
            elif hours > 0:
                return f"{sign}{hours}h"
            elif minutes > 0:
                return f"{sign}{minutes}m"
            elif secs > 0:
                return f"{sign}{secs:.0f}s"
            else:
                return f"{sign}0s"

# ============================================================
# JSON FORMATTER
# ============================================================

class JSONFormatter:
    """Formateur JSON"""
    
    @staticmethod
    def format(
        data: Any,
        indent: int = 2,
        sort_keys: bool = False,
        compact: bool = False,
        colorized: bool = False
    ) -> str:
        """
        Formate des données en JSON
        
        Args:
            data: Données à formater
            indent: Indentation
            sort_keys: Trier les clés
            compact: Format compact
            colorized: Coloriser
            
        Returns:
            str: JSON formaté
        """
        def default_serializer(obj):
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            if is_dataclass(obj):
                return asdict(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, date):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, Enum):
                return obj.value
            return str(obj)
        
        if compact:
            return json.dumps(data, default=default_serializer, separators=(',', ':'))
        
        json_str = json.dumps(
            data,
            indent=indent,
            sort_keys=sort_keys,
            default=default_serializer
        )
        
        if colorized:
            return JSONFormatter._colorize_json(json_str)
        
        return json_str
    
    @staticmethod
    def _colorize_json(json_str: str) -> str:
        """Colorise du JSON"""
        # À implémenter avec pygments ou une lib similaire
        return json_str

# ============================================================
# TABLE FORMATTER
# ============================================================

class TableFormatter:
    """Formateur de tableaux"""
    
    @staticmethod
    def format_table(
        data: List[Dict[str, Any]],
        headers: Optional[List[str]] = None,
        alignment: Dict[str, str] = None,
        max_width: int = 80,
        padding: int = 2,
        border: bool = True,
        style: str = 'simple'  # simple, markdown, html
    ) -> str:
        """
        Formate des données en tableau
        
        Args:
            data: Données à formater
            headers: En-têtes
            alignment: Alignement par colonne
            max_width: Largeur maximale
            padding: Padding
            border: Afficher les bordures
            style: Style ('simple', 'markdown', 'html')
            
        Returns:
            str: Tableau formaté
        """
        if not data:
            return ''
        
        # Déterminer les headers
        if headers is None:
            headers = list(data[0].keys())
        
        # Calculer les largeurs
        widths = {h: len(h) for h in headers}
        for row in data:
            for h in headers:
                val = str(row.get(h, ''))
                widths[h] = max(widths[h], len(val))
        
        # Limiter les largeurs
        total_width = sum(widths.values()) + padding * len(headers) * 2 + len(headers) + 1
        if total_width > max_width:
            for h in headers:
                if widths[h] > max_width / len(headers):
                    widths[h] = int(max_width / len(headers)) - 3
        
        # Construire le tableau
        if style == 'markdown':
            return TableFormatter._format_markdown_table(data, headers, widths, alignment, padding)
        elif style == 'html':
            return TableFormatter._format_html_table(data, headers, widths, alignment, padding)
        else:
            return TableFormatter._format_simple_table(data, headers, widths, alignment, padding, border)
    
    @staticmethod
    def _format_simple_table(
        data: List[Dict[str, Any]],
        headers: List[str],
        widths: Dict[str, int],
        alignment: Dict[str, str],
        padding: int,
        border: bool
    ) -> str:
        """Formatage de tableau simple"""
        lines = []
        
        # En-tête
        header_line = " " + " | ".join(
            f"{h:^{widths[h]}}" for h in headers
        )
        if border:
            separator = "+" + "+".join("-" * (widths[h] + padding * 2) for h in headers) + "+"
            lines.append(separator)
            lines.append("| " + " | ".join(
                f"{h:^{widths[h]}}" for h in headers
            ) + " |")
            lines.append(separator)
        else:
            lines.append(header_line)
            lines.append(" " + "-|-".join("-" * widths[h] for h in headers))
        
        # Données
        for row in data:
            if border:
                line = "| " + " | ".join(
                    f"{str(row.get(h, '')):^{widths[h]}}" for h in headers
                ) + " |"
            else:
                line = " " + " | ".join(
                    f"{str(row.get(h, '')):^{widths[h]}}" for h in headers
                )
            lines.append(line)
        
        if border:
            lines.append(separator)
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_markdown_table(
        data: List[Dict[str, Any]],
        headers: List[str],
        widths: Dict[str, int],
        alignment: Dict[str, str],
        padding: int
    ) -> str:
        """Formatage de tableau Markdown"""
        lines = []
        
        # En-tête
        header_line = "| " + " | ".join(h for h in headers) + " |"
        lines.append(header_line)
        
        # Séparateur
        sep_parts = []
        for h in headers:
            align = (alignment or {}).get(h, 'center')
            if align == 'left':
                sep_parts.append(":" + "-" * (widths[h]) + "")
            elif align == 'right':
                sep_parts.append("" + "-" * (widths[h]) + ":")
            else:
                sep_parts.append(":" + "-" * (widths[h]) + ":")
        lines.append("|" + "|".join(sep_parts) + "|")
        
        # Données
        for row in data:
            row_line = "| " + " | ".join(
                str(row.get(h, '')) for h in headers
            ) + " |"
            lines.append(row_line)
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_html_table(
        data: List[Dict[str, Any]],
        headers: List[str],
        widths: Dict[str, int],
        alignment: Dict[str, str],
        padding: int
    ) -> str:
        """Formatage de tableau HTML"""
        lines = []
        
        lines.append("<table>")
        
        # En-tête
        lines.append("  <thead>")
        lines.append("    <tr>")
        for h in headers:
            lines.append(f"      <th>{h}</th>")
        lines.append("    </tr>")
        lines.append("  </thead>")
        
        # Données
        lines.append("  <tbody>")
        for row in data:
            lines.append("    <tr>")
            for h in headers:
                val = str(row.get(h, ''))
                lines.append(f"      <td>{html.escape(val)}</td>")
            lines.append("    </tr>")
        lines.append("  </tbody>")
        
        lines.append("</table>")
        
        return "\n".join(lines)

# ============================================================
# LOG FORMATTER
# ============================================================

class LogFormatter:
    """Formateur de logs"""
    
    @staticmethod
    def format_log_entry(
        level: str,
        message: str,
        timestamp: Optional[datetime] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Formate une entrée de log
        
        Args:
            level: Niveau de log
            message: Message
            timestamp: Timestamp
            **kwargs: Champs supplémentaires
            
        Returns:
            Dict[str, Any]: Entrée formatée
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        entry = {
            'timestamp': timestamp.isoformat(),
            'level': level.upper(),
            'message': message,
            **kwargs
        }
        
        return entry
    
    @staticmethod
    def format_log_entry_text(
        level: str,
        message: str,
        timestamp: Optional[datetime] = None,
        **kwargs
    ) -> str:
        """
        Formate une entrée de log en texte
        
        Args:
            level: Niveau de log
            message: Message
            timestamp: Timestamp
            **kwargs: Champs supplémentaires
            
        Returns:
            str: Entrée formatée
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        parts = [timestamp.isoformat(), f"[{level.upper()}]", message]
        
        for key, value in kwargs.items():
            parts.append(f"{key}={value}")
        
        return " ".join(parts)

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Classes
    'CurrencyFormatter',
    'NumberFormatter',
    'DateTimeFormatter',
    'JSONFormatter',
    'TableFormatter',
    'LogFormatter',
]

# ============================================================
# INITIALIZATION
# ============================================================

# Initialiser colorama pour Windows
colorama_init()

logger.info("Formatters utilities module initialized")

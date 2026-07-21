"""
NEXUS AI TRADING SYSTEM - HEDGE BOT FORMATTERS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de formatage pour le Hedge Bot.
Support du formatage des nombres, dates, monnaies, et données de trading.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import pytz
import humanize
import babel.numbers
from babel.dates import format_date, format_datetime, format_time
from babel.numbers import format_currency, format_decimal, format_percent

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class NumberFormat(Enum):
    """Formats de nombres."""
    DECIMAL = "decimal"
    PERCENT = "percent"
    CURRENCY = "currency"
    SCIENTIFIC = "scientific"
    ENGINEERING = "engineering"
    COMPACT = "compact"
    ROMAN = "roman"


class DateFormat(Enum):
    """Formats de dates."""
    ISO = "iso"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    FULL = "full"
    RELATIVE = "relative"
    TIME_AGO = "time_ago"
    TIMESTAMP = "timestamp"


class Color(Enum):
    """Couleurs pour l'affichage."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"
    
    # Couleurs de texte
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Couleurs de fond
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    
    # Couleurs vives
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Fonds vifs
    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_MAGENTA = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"


class Emoji(Enum):
    """Émojis pour l'affichage."""
    # Trading
    TRADING = "📈"
    TRADING_DOWN = "📉"
    MONEY = "💰"
    MONEY_BAG = "🤑"
    COINS = "🪙"
    CRYPTO = "₿"
    STOCK = "📊"
    CHART = "📈"
    CHART_DOWN = "📉"
    
    # Status
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    CHECK = "✔️"
    CROSS = "❌"
    STAR = "⭐"
    FIRE = "🔥"
    ROCKET = "🚀"
    BULL = "🐂"
    BEAR = "🐻"
    
    # Time
    CLOCK = "🕐"
    ALARM = "⏰"
    CALENDAR = "📅"
    
    # Misc
    LOCK = "🔒"
    UNLOCK = "🔓"
    KEY = "🔑"
    GEAR = "⚙️"
    WARNING_TRIANGLE = "⚠️"
    BELL = "🔔"
    BELL_SLASH = "🔕"
    EMAIL = "📧"
    PHONE = "📱"
    COMPUTER = "💻"
    NETWORK = "🌐"
    DATABASE = "🗄️"


@dataclass
class FormatterConfig:
    """Configuration du formateur."""
    locale: str = "en_US"
    timezone: str = "UTC"
    currency: str = "USD"
    decimal_places: int = 2
    thousands_separator: str = ","
    decimal_separator: str = "."
    date_format: str = "medium"
    time_format: str = "medium"
    color_enabled: bool = True
    emoji_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# CLASSE FORMATTERS
# ============================================================================

class Formatters:
    """
    Utilitaires de formatage pour le Hedge Bot.
    """

    # Unités SI
    SI_UNITS = [
        (1e24, "Y"),
        (1e21, "Z"),
        (1e18, "E"),
        (1e15, "P"),
        (1e12, "T"),
        (1e9, "G"),
        (1e6, "M"),
        (1e3, "k"),
        (1, ""),
        (1e-3, "m"),
        (1e-6, "µ"),
        (1e-9, "n"),
        (1e-12, "p"),
        (1e-15, "f"),
        (1e-18, "a"),
        (1e-21, "z"),
        (1e-24, "y")
    ]

    # Couleurs pour les variations
    COLOR_POSITIVE = Color.GREEN
    COLOR_NEGATIVE = Color.RED
    COLOR_NEUTRAL = Color.WHITE
    COLOR_WARNING = Color.YELLOW
    COLOR_INFO = Color.CYAN
    COLOR_ERROR = Color.RED
    COLOR_SUCCESS = Color.GREEN

    def __init__(
        self,
        config: Optional[FormatterConfig] = None
    ):
        """
        Initialise le formateur.

        Args:
            config: Configuration du formateur
        """
        self.config = config or FormatterConfig()
        
        # Cache
        self._locale_cache: Dict[str, Any] = {}
        self._timezone_cache: Dict[str, Any] = {}
        
        # Métriques
        self._metrics = {
            "total_formats": 0,
            "by_type": {},
            "last_format": None
        }

        logger.info(f"Formatters initialisé avec locale: {self.config.locale}")

    # ========================================================================
    # FORMATAGE DES NOMBRES
    # ========================================================================

    def format_number(
        self,
        value: Union[int, float, Decimal, str],
        decimals: Optional[int] = None,
        format_type: NumberFormat = NumberFormat.DECIMAL,
        locale: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Formate un nombre.

        Args:
            value: Valeur à formater
            decimals: Nombre de décimales
            format_type: Type de format
            locale: Locale à utiliser
            **kwargs: Arguments supplémentaires

        Returns:
            Nombre formaté
        """
        try:
            self._metrics["total_formats"] += 1
            self._metrics["last_format"] = datetime.now().isoformat()
            
            if "by_type" not in self._metrics:
                self._metrics["by_type"] = {}
            self._metrics["by_type"]["number"] = self._metrics["by_type"].get("number", 0) + 1

            # Conversion en Decimal
            if isinstance(value, str):
                value = Decimal(value)
            elif isinstance(value, (int, float)):
                value = Decimal(str(value))

            decimals = decimals or self.config.decimal_places
            locale = locale or self.config.locale

            if format_type == NumberFormat.DECIMAL:
                return self._format_decimal(value, decimals, locale)
            elif format_type == NumberFormat.PERCENT:
                return self._format_percent(value, decimals, locale)
            elif format_type == NumberFormat.CURRENCY:
                return self._format_currency(value, self.config.currency, decimals, locale)
            elif format_type == NumberFormat.SCIENTIFIC:
                return self._format_scientific(value, decimals)
            elif format_type == NumberFormat.ENGINEERING:
                return self._format_engineering(value, decimals)
            elif format_type == NumberFormat.COMPACT:
                return self._format_compact(value, decimals)
            elif format_type == NumberFormat.ROMAN:
                return self._format_roman(value)
            else:
                return str(value)

        except Exception as e:
            logger.error(f"Erreur lors du formatage du nombre: {e}")
            return str(value)

    def _format_decimal(
        self,
        value: Decimal,
        decimals: int,
        locale: str
    ) -> str:
        """
        Formate un nombre décimal.

        Args:
            value: Valeur
            decimals: Nombre de décimales
            locale: Locale

        Returns:
            Nombre formaté
        """
        try:
            rounded = value.quantize(Decimal('0.' + '0' * decimals), rounding=ROUND_HALF_UP)
            return format_decimal(
                float(rounded),
                locale=locale,
                format=f"#,##0.{'0' * decimals if decimals > 0 else ''}"
            )
        except Exception:
            return str(value)

    def _format_percent(
        self,
        value: Decimal,
        decimals: int,
        locale: str
    ) -> str:
        """
        Formate un pourcentage.

        Args:
            value: Valeur
            decimals: Nombre de décimales
            locale: Locale

        Returns:
            Pourcentage formaté
        """
        try:
            return format_percent(
                float(value),
                locale=locale,
                format=f"#,##0.{'0' * decimals if decimals > 0 else ''}%"
            )
        except Exception:
            return f"{value}%"

    def _format_currency(
        self,
        value: Decimal,
        currency: str,
        decimals: int,
        locale: str
    ) -> str:
        """
        Formate une devise.

        Args:
            value: Valeur
            currency: Devise
            decimals: Nombre de décimales
            locale: Locale

        Returns:
            Devise formatée
        """
        try:
            return format_currency(
                float(value),
                currency,
                locale=locale,
                format=f"#,##0.{'0' * decimals if decimals > 0 else ''}"
            )
        except Exception:
            return f"{currency} {value}"

    def _format_scientific(self, value: Decimal, decimals: int) -> str:
        """
        Formate en notation scientifique.

        Args:
            value: Valeur
            decimals: Nombre de décimales

        Returns:
            Nombre en notation scientifique
        """
        try:
            return f"{value:.{decimals}e}"
        except Exception:
            return str(value)

    def _format_engineering(self, value: Decimal, decimals: int) -> str:
        """
        Formate en notation ingénieur.

        Args:
            value: Valeur
            decimals: Nombre de décimales

        Returns:
            Nombre en notation ingénieur
        """
        try:
            exponent = 0
            v = float(value)
            while abs(v) >= 1000:
                v /= 1000
                exponent += 1
            while abs(v) < 1:
                v *= 1000
                exponent -= 1
            return f"{v:.{decimals}f}e{exponent*3}"
        except Exception:
            return str(value)

    def _format_compact(self, value: Decimal, decimals: int) -> str:
        """
        Formate en notation compacte.

        Args:
            value: Valeur
            decimals: Nombre de décimales

        Returns:
            Nombre en notation compacte
        """
        try:
            v = float(value)
            for limit, suffix in self.SI_UNITS:
                if abs(v) >= limit:
                    return f"{v/limit:.{decimals}f}{suffix}"
            return str(value)
        except Exception:
            return str(value)

    def _format_roman(self, value: Decimal) -> str:
        """
        Formate en chiffres romains.

        Args:
            value: Valeur

        Returns:
            Chiffres romains
        """
        try:
            num = int(value)
            if num <= 0 or num > 3999:
                return str(value)
            
            roman_numerals = {
                1000: 'M', 900: 'CM', 500: 'D', 400: 'CD',
                100: 'C', 90: 'XC', 50: 'L', 40: 'XL',
                10: 'X', 9: 'IX', 5: 'V', 4: 'IV', 1: 'I'
            }
            
            result = ""
            for val, numeral in roman_numerals.items():
                while num >= val:
                    result += numeral
                    num -= val
            return result
        except Exception:
            return str(value)

    # ========================================================================
    # FORMATAGE DES DATES
    # ========================================================================

    def format_date(
        self,
        date_obj: Union[datetime, str, int, float],
        format_type: DateFormat = DateFormat.MEDIUM,
        locale: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> str:
        """
        Formate une date.

        Args:
            date_obj: Objet date
            format_type: Type de format
            locale: Locale à utiliser
            timezone: Fuseau horaire

        Returns:
            Date formatée
        """
        try:
            self._metrics["total_formats"] += 1
            self._metrics["by_type"]["date"] = self._metrics["by_type"].get("date", 0) + 1
            self._metrics["last_format"] = datetime.now().isoformat()

            # Conversion en datetime
            dt = self._to_datetime(date_obj)
            
            locale = locale or self.config.locale
            timezone = timezone or self.config.timezone
            
            # Application du fuseau horaire
            if timezone:
                tz = pytz.timezone(timezone)
                if dt.tzinfo is None:
                    dt = pytz.UTC.localize(dt)
                dt = dt.astimezone(tz)

            if format_type == DateFormat.ISO:
                return dt.isoformat()
            elif format_type == DateFormat.SHORT:
                return format_datetime(dt, "short", locale=locale)
            elif format_type == DateFormat.MEDIUM:
                return format_datetime(dt, "medium", locale=locale)
            elif format_type == DateFormat.LONG:
                return format_datetime(dt, "long", locale=locale)
            elif format_type == DateFormat.FULL:
                return format_datetime(dt, "full", locale=locale)
            elif format_type == DateFormat.RELATIVE:
                return humanize.naturaltime(dt)
            elif format_type == DateFormat.TIME_AGO:
                return self._format_time_ago(dt)
            elif format_type == DateFormat.TIMESTAMP:
                return str(int(dt.timestamp()))
            else:
                return dt.isoformat()

        except Exception as e:
            logger.error(f"Erreur lors du formatage de la date: {e}")
            return str(date_obj)

    def _format_time_ago(self, dt: datetime) -> str:
        """
        Formate une date en "il y a X temps".

        Args:
            dt: Datetime

        Returns:
            Date formatée
        """
        try:
            now = datetime.now(pytz.UTC)
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            
            diff = now - dt
            
            seconds = diff.total_seconds()
            minutes = seconds / 60
            hours = minutes / 60
            days = hours / 24
            weeks = days / 7
            months = days / 30.44
            years = days / 365.25

            if seconds < 60:
                return f"il y a {int(seconds)} seconde{'s' if int(seconds) > 1 else ''}"
            elif minutes < 60:
                return f"il y a {int(minutes)} minute{'s' if int(minutes) > 1 else ''}"
            elif hours < 24:
                return f"il y a {int(hours)} heure{'s' if int(hours) > 1 else ''}"
            elif days < 7:
                return f"il y a {int(days)} jour{'s' if int(days) > 1 else ''}"
            elif weeks < 4:
                return f"il y a {int(weeks)} semaine{'s' if int(weeks) > 1 else ''}"
            elif months < 12:
                return f"il y a {int(months)} moi{'s' if int(months) > 1 else ''}"
            else:
                return f"il y a {int(years)} an{'s' if int(years) > 1 else ''}"

        except Exception:
            return str(dt)

    def _to_datetime(self, date_obj: Union[datetime, str, int, float]) -> datetime:
        """
        Convertit en datetime.

        Args:
            date_obj: Objet date

        Returns:
            Datetime
        """
        if isinstance(date_obj, datetime):
            return date_obj
        elif isinstance(date_obj, str):
            try:
                return datetime.fromisoformat(date_obj)
            except ValueError:
                return datetime.strptime(date_obj, "%Y-%m-%d %H:%M:%S")
        elif isinstance(date_obj, (int, float)):
            return datetime.fromtimestamp(date_obj)
        else:
            raise ValueError(f"Type non supporté: {type(date_obj)}")

    # ========================================================================
    # FORMATAGE DES DEVISES
    # ========================================================================

    def format_currency_amount(
        self,
        amount: Union[int, float, Decimal],
        currency: Optional[str] = None,
        decimals: Optional[int] = None,
        color: bool = True
    ) -> str:
        """
        Formate un montant en devise.

        Args:
            amount: Montant
            currency: Devise
            decimals: Nombre de décimales
            color: Ajouter des couleurs

        Returns:
            Montant formaté
        """
        try:
            self._metrics["total_formats"] += 1
            self._metrics["by_type"]["currency"] = self._metrics["by_type"].get("currency", 0) + 1

            currency = currency or self.config.currency
            decimals = decimals or self.config.decimal_places
            
            formatted = self.format_number(
                amount,
                decimals=decimals,
                format_type=NumberFormat.CURRENCY,
                locale=self.config.locale
            )
            
            if color:
                if amount > 0:
                    formatted = f"{self.COLOR_POSITIVE.value}{formatted}{Color.RESET.value}"
                elif amount < 0:
                    formatted = f"{self.COLOR_NEGATIVE.value}{formatted}{Color.RESET.value}"
            
            return formatted

        except Exception as e:
            logger.error(f"Erreur lors du formatage de la devise: {e}")
            return f"{currency} {amount}"

    # ========================================================================
    # FORMATAGE DES VARIATIONS
    # ========================================================================

    def format_change(
        self,
        change: Union[int, float, Decimal],
        as_percent: bool = True,
        decimals: Optional[int] = None,
        with_arrow: bool = True,
        color: bool = True
    ) -> str:
        """
        Formate une variation.

        Args:
            change: Variation
            as_percent: Afficher en pourcentage
            decimals: Nombre de décimales
            with_arrow: Ajouter une flèche
            color: Ajouter des couleurs

        Returns:
            Variation formatée
        """
        try:
            self._metrics["total_formats"] += 1
            self._metrics["by_type"]["change"] = self._metrics["by_type"].get("change", 0) + 1

            decimals = decimals or self.config.decimal_places
            
            if as_percent:
                formatted = self.format_number(
                    change,
                    decimals=decimals,
                    format_type=NumberFormat.PERCENT
                )
            else:
                formatted = self.format_number(
                    change,
                    decimals=decimals
                )
            
            # Ajout de la flèche
            if with_arrow and change != 0:
                arrow = "▲" if change > 0 else "▼"
                formatted = f"{arrow} {formatted}"
            
            # Ajout de la couleur
            if color:
                if change > 0:
                    formatted = f"{self.COLOR_POSITIVE.value}{formatted}{Color.RESET.value}"
                elif change < 0:
                    formatted = f"{self.COLOR_NEGATIVE.value}{formatted}{Color.RESET.value}"
            
            return formatted

        except Exception as e:
            logger.error(f"Erreur lors du formatage de la variation: {e}")
            return str(change)

    # ========================================================================
    # FORMATAGE DES ADRESSES
    # ========================================================================

    def format_address(
        self,
        address: str,
        start_chars: int = 6,
        end_chars: int = 6,
        separator: str = "..."
    ) -> str:
        """
        Formate une adresse (tronquée).

        Args:
            address: Adresse
            start_chars: Nombre de caractères au début
            end_chars: Nombre de caractères à la fin
            separator: Séparateur

        Returns:
            Adresse formatée
        """
        try:
            if len(address) <= start_chars + end_chars:
                return address
            return f"{address[:start_chars]}{separator}{address[-end_chars:]}"
        except Exception:
            return address

    # ========================================================================
    # FORMATAGE DES TAILLES
    # ========================================================================

    def format_size(
        self,
        size_bytes: int,
        decimals: int = 2
    ) -> str:
        """
        Formate une taille en bytes.

        Args:
            size_bytes: Taille en bytes
            decimals: Nombre de décimales

        Returns:
            Taille formatée
        """
        try:
            self._metrics["total_formats"] += 1
            self._metrics["by_type"]["size"] = self._metrics["by_type"].get("size", 0) + 1

            units = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
            size = float(size_bytes)
            
            for unit in units:
                if abs(size) < 1024.0:
                    return f"{size:.{decimals}f} {unit}"
                size /= 1024.0
            
            return f"{size:.{decimals}f} {units[-1]}"

        except Exception as e:
            logger.error(f"Erreur lors du formatage de la taille: {e}")
            return f"{size_bytes} B"

    # ========================================================================
    # FORMATAGE DES TABLEAUX
    # ========================================================================

    def format_table(
        self,
        data: List[Dict[str, Any]],
        headers: Optional[List[str]] = None,
        colors: bool = True,
        align: str = "left"
    ) -> str:
        """
        Formate un tableau.

        Args:
            data: Données du tableau
            headers: En-têtes
            colors: Ajouter des couleurs
            align: Alignement

        Returns:
            Tableau formaté
        """
        try:
            if not data:
                return ""

            if not headers:
                headers = list(data[0].keys())

            # Calcul des largeurs
            widths = {h: len(h) for h in headers}
            for row in data:
                for h in headers:
                    value = str(row.get(h, ""))
                    widths[h] = max(widths[h], len(value))

            # Construction du tableau
            lines = []
            
            # Séparateur haut
            separator = "+" + "+".join("-" * (widths[h] + 2) for h in headers) + "+"
            lines.append(separator)
            
            # En-têtes
            header_line = "|"
            for h in headers:
                if colors:
                    header_line += f" {Color.BOLD.value}{h.center(widths[h])}{Color.RESET.value} |"
                else:
                    header_line += f" {h.center(widths[h])} |"
            lines.append(header_line)
            lines.append(separator)
            
            # Données
            for row in data:
                line = "|"
                for h in headers:
                    value = str(row.get(h, ""))
                    if align == "right":
                        line += f" {value.rjust(widths[h])} |"
                    elif align == "center":
                        line += f" {value.center(widths[h])} |"
                    else:
                        line += f" {value.ljust(widths[h])} |"
                lines.append(line)
            
            lines.append(separator)
            
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Erreur lors du formatage du tableau: {e}")
            return str(data)

    # ========================================================================
    # FORMATAGE AVEC COULEURS
    # ========================================================================

    def color_text(
        self,
        text: str,
        color: Color = Color.WHITE,
        background: Optional[Color] = None,
        style: Optional[Color] = None
    ) -> str:
        """
        Ajoute des couleurs à un texte.

        Args:
            text: Texte
            color: Couleur du texte
            background: Couleur de fond
            style: Style

        Returns:
            Texte coloré
        """
        if not self.config.color_enabled:
            return text

        result = ""
        if style:
            result += style.value
        if color:
            result += color.value
        if background:
            result += background.value
        result += text
        result += Color.RESET.value
        
        return result

    def color_by_value(
        self,
        value: Union[int, float, Decimal],
        text: Optional[str] = None,
        threshold: float = 0
    ) -> str:
        """
        Colore un texte en fonction de sa valeur.

        Args:
            value: Valeur
            text: Texte (si None, utilise la valeur)
            threshold: Seuil

        Returns:
            Texte coloré
        """
        text = text or str(value)
        
        if value > threshold:
            return self.color_text(text, self.COLOR_POSITIVE)
        elif value < threshold:
            return self.color_text(text, self.COLOR_NEGATIVE)
        else:
            return self.color_text(text, self.COLOR_NEUTRAL)

    # ========================================================================
    # FORMATAGE AVEC ÉMOJIS
    # ========================================================================

    def add_emoji(
        self,
        text: str,
        emoji: Emoji,
        position: str = "prefix"
    ) -> str:
        """
        Ajoute un émoji à un texte.

        Args:
            text: Texte
            emoji: Émoji
            position: Position (prefix, suffix)

        Returns:
            Texte avec émoji
        """
        if not self.config.emoji_enabled:
            return text

        if position == "prefix":
            return f"{emoji.value} {text}"
        else:
            return f"{text} {emoji.value}"

    def get_status_emoji(
        self,
        status: str
    ) -> str:
        """
        Récupère l'émoji correspondant à un statut.

        Args:
            status: Statut

        Returns:
            Émoji
        """
        status_map = {
            "success": Emoji.SUCCESS,
            "error": Emoji.ERROR,
            "warning": Emoji.WARNING,
            "info": Emoji.INFO,
            "pending": Emoji.CLOCK,
            "completed": Emoji.CHECK,
            "failed": Emoji.CROSS,
            "active": Emoji.FIRE,
            "inactive": Emoji.BELL_SLASH
        }
        return status_map.get(status.lower(), Emoji.INFO)

    # ========================================================================
    # FORMATAGE DES DONNÉES DE TRADING
    # ========================================================================

    def format_trade(
        self,
        trade_data: Dict[str, Any],
        verbose: bool = False
    ) -> str:
        """
        Formate une transaction.

        Args:
            trade_data: Données de la transaction
            verbose: Format verbeux

        Returns:
            Transaction formatée
        """
        try:
            if verbose:
                lines = []
                for key, value in trade_data.items():
                    if key == "timestamp":
                        value = self.format_date(value)
                    elif key in ["amount", "price", "fee"]:
                        value = self.format_currency_amount(value)
                    lines.append(f"{key}: {value}")
                return "\n".join(lines)
            else:
                symbol = trade_data.get("symbol", "UNKNOWN")
                side = trade_data.get("side", "N/A")
                amount = trade_data.get("amount", 0)
                price = trade_data.get("price", 0)
                timestamp = trade_data.get("timestamp", datetime.now())
                
                return f"{self.format_date(timestamp, DateFormat.SHORT)} | {symbol} | {side.upper()} | {self.format_number(amount)} @ {self.format_currency_amount(price)}"

        except Exception as e:
            logger.error(f"Erreur lors du formatage de la transaction: {e}")
            return str(trade_data)

    def format_position(
        self,
        position: Dict[str, Any],
        verbose: bool = False
    ) -> str:
        """
        Formate une position.

        Args:
            position: Données de la position
            verbose: Format verbeux

        Returns:
            Position formatée
        """
        try:
            symbol = position.get("symbol", "UNKNOWN")
            side = position.get("side", "N/A")
            size = position.get("size", 0)
            entry = position.get("entry_price", 0)
            current = position.get("current_price", 0)
            pnl = position.get("pnl", 0)
            pnl_pct = position.get("pnl_percent", 0)

            if verbose:
                return (f"{self.color_by_value(pnl)} | "
                        f"{symbol} | {side.upper()} | "
                        f"Size: {self.format_number(size)} | "
                        f"Entry: {self.format_currency_amount(entry)} | "
                        f"Current: {self.format_currency_amount(current)} | "
                        f"PnL: {self.format_change(pnl, as_percent=False)} ({self.format_change(pnl_pct)})")
            else:
                return (f"{symbol} | {side.upper()} | "
                        f"Size: {self.format_number(size)} | "
                        f"PnL: {self.format_change(pnl, as_percent=False)}")

        except Exception as e:
            logger.error(f"Erreur lors du formatage de la position: {e}")
            return str(position)

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "locale": self.config.locale,
                "timezone": self.config.timezone,
                "currency": self.config.currency,
                "total_formats": self._metrics["total_formats"],
                "by_type": self._metrics["by_type"],
                "last_format": self._metrics["last_format"],
                "color_enabled": self.config.color_enabled,
                "emoji_enabled": self.config.emoji_enabled,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de Formatters...")
        self._locale_cache.clear()
        self._timezone_cache.clear()
        logger.info("Formatters fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_formatters(
    locale: str = "en_US",
    timezone: str = "UTC",
    currency: str = "USD"
) -> Formatters:
    """
    Crée une instance de Formatters.

    Args:
        locale: Locale
        timezone: Fuseau horaire
        currency: Devise

    Returns:
        Instance de Formatters
    """
    config = FormatterConfig(
        locale=locale,
        timezone=timezone,
        currency=currency
    )
    return Formatters(config)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "NumberFormat",
    "DateFormat",
    "Color",
    "Emoji",
    "FormatterConfig",
    "Formatters",
    "create_formatters"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de Formatters."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT FORMATTERS")
    print("=" * 60)

    # Création de l'instance
    formatters = create_formatters(
        locale="fr_FR",
        timezone="Europe/Paris",
        currency="EUR"
    )

    print(f"\n✅ Formatters initialisé:")
    print(f"   Locale: {formatters.config.locale}")
    print(f"   Timezone: {formatters.config.timezone}")
    print(f"   Currency: {formatters.config.currency}")

    # Formatage des nombres
    print(f"\n🔢 Formatage des nombres:")
    print(f"   Decimal: {formatters.format_number(1234.5678)}")
    print(f"   Percent: {formatters.format_number(0.1234, format_type=NumberFormat.PERCENT)}")
    print(f"   Currency: {formatters.format_number(1234.56, format_type=NumberFormat.CURRENCY)}")
    print(f"   Compact: {formatters.format_number(1234567, format_type=NumberFormat.COMPACT)}")

    # Formatage des dates
    now = datetime.now()
    print(f"\n📅 Formatage des dates:")
    print(f"   ISO: {formatters.format_date(now, DateFormat.ISO)}")
    print(f"   Short: {formatters.format_date(now, DateFormat.SHORT)}")
    print(f"   Medium: {formatters.format_date(now, DateFormat.MEDIUM)}")
    print(f"   Relative: {formatters.format_date(now - timedelta(days=2), DateFormat.RELATIVE)}")

    # Formatage des variations
    print(f"\n📊 Formatage des variations:")
    print(f"   Positif: {formatters.format_change(0.05)}")
    print(f"   Négatif: {formatters.format_change(-0.03)}")

    # Formatage des adresses
    address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    print(f"\n🔑 Formatage des adresses:")
    print(f"   Original: {address}")
    print(f"   Formaté: {formatters.format_address(address)}")

    # Formatage des couleurs
    print(f"\n🎨 Formatage des couleurs:")
    print(f"   {formatters.color_text('Texte vert', Color.GREEN)}")
    print(f"   {formatters.color_text('Texte rouge', Color.RED)}")
    print(f"   {formatters.color_text('Texte jaune', Color.YELLOW)}")

    # Formatage des émojis
    print(f"\n😊 Formatage des émojis:")
    print(f"   {formatters.add_emoji('Succès', Emoji.SUCCESS)}")
    print(f"   {formatters.add_emoji('Erreur', Emoji.ERROR)}")
    print(f"   {formatters.add_emoji('Alerte', Emoji.WARNING)}")

    # Formatage des transactions
    trade = {
        "symbol": "BTC/EUR",
        "side": "buy",
        "amount": 0.1,
        "price": 30000,
        "timestamp": now - timedelta(hours=2)
    }
    print(f"\n💹 Formatage des transactions:")
    print(f"   {formatters.format_trade(trade)}")

    # Santé du service
    health = formatters.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Statut: {health['status']}")
    print(f"   Total formats: {health['total_formats']}")
    print(f"   Par type: {health['by_type']}")

    # Fermeture
    await formatters.close()

    print("\n" + "=" * 60)
    print("Formatters NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

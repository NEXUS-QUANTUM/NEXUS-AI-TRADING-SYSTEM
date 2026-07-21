"""
NEXUS AI TRADING SYSTEM - Hedge Bot Date Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de date et heure pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import calendar
import time
from datetime import (
    datetime,
    date,
    time as datetime_time,
    timedelta,
    tzinfo
)
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Callable,
    Iterator,
    Generator
)
import pytz
from pytz import timezone, UTC
import re
from dateutil import parser
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzutc, tzlocal, gettz
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
import arrow
from collections import defaultdict
from enum import Enum
import json

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

# Intervalles de temps en secondes
SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 3600
SECONDS_IN_DAY = 86400
SECONDS_IN_WEEK = 604800
SECONDS_IN_MONTH = 2592000  # 30 days
SECONDS_IN_YEAR = 31536000  # 365 days

# Intervalles de temps en millisecondes
MS_IN_SECOND = 1000
MS_IN_MINUTE = 60000
MS_IN_HOUR = 3600000
MS_IN_DAY = 86400000
MS_IN_WEEK = 604800000
MS_IN_MONTH = 2592000000  # 30 days in ms
MS_IN_YEAR = 31536000000  # 365 days in ms

# Formats de date communs
DATE_FORMATS = {
    'iso': '%Y-%m-%dT%H:%M:%S',
    'iso_ms': '%Y-%m-%dT%H:%M:%S.%f',
    'iso_z': '%Y-%m-%dT%H:%M:%SZ',
    'iso_ms_z': '%Y-%m-%dT%H:%M:%S.%fZ',
    'datetime': '%Y-%m-%d %H:%M:%S',
    'date': '%Y-%m-%d',
    'date_us': '%m/%d/%Y',
    'date_eu': '%d/%m/%Y',
    'time': '%H:%M:%S',
    'time_ms': '%H:%M:%S.%f',
    'timestamp': '%Y%m%d%H%M%S',
    'timestamp_ms': '%Y%m%d%H%M%S%f',
    'rfc2822': '%a, %d %b %Y %H:%M:%S %z',
    'rfc3339': '%Y-%m-%dT%H:%M:%S%z',
    'rfc3339_ms': '%Y-%m-%dT%H:%M:%S.%f%z',
    'http': '%a, %d %b %Y %H:%M:%S GMT',
    'cookie': '%A, %d-%b-%Y %H:%M:%S GMT',
    'email': '%a, %d %b %Y %H:%M:%S %z',
    'compact': '%Y%m%d%H%M%S',
    'rfc822': '%a, %d %b %Y %H:%M:%S %z',
    'rfc1123': '%a, %d %b %Y %H:%M:%S %Z',
    'rfc850': '%A, %d-%b-%Y %H:%M:%S %Z',
    'asctime': '%a %b %d %H:%M:%S %Y',
}

# Noms des mois et jours
MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April',
    5: 'May', 6: 'June', 7: 'July', 8: 'August',
    9: 'September', 10: 'October', 11: 'November', 12: 'December'
}
MONTH_NAMES_SHORT = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
}
DAY_NAMES = {
    0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
    4: 'Friday', 5: 'Saturday', 6: 'Sunday'
}
DAY_NAMES_SHORT = {
    0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu',
    4: 'Fri', 5: 'Sat', 6: 'Sun'
}

# ============================================================
# TIMEZONE UTILITIES
# ============================================================

class TimezoneUtils:
    """Utilitaires de fuseaux horaires"""
    
    # Fuseaux horaires communs
    COMMON_TIMEZONES = {
        'utc': 'UTC',
        'gmt': 'GMT',
        'est': 'US/Eastern',
        'edt': 'US/Eastern',
        'cst': 'US/Central',
        'cdt': 'US/Central',
        'mst': 'US/Mountain',
        'mdt': 'US/Mountain',
        'pst': 'US/Pacific',
        'pdt': 'US/Pacific',
        'hst': 'US/Hawaii',
        'akst': 'US/Alaska',
        'akdt': 'US/Alaska',
        'cet': 'CET',
        'cest': 'CEST',
        'eet': 'EET',
        'eest': 'EEST',
        'bst': 'GB',
        'ist': 'Asia/Kolkata',
        'jst': 'Asia/Tokyo',
        'cst_cn': 'Asia/Shanghai',
        'hkt': 'Asia/Hong_Kong',
        'sgt': 'Asia/Singapore',
        'aest': 'Australia/Sydney',
        'aedt': 'Australia/Sydney',
        'nzst': 'Pacific/Auckland',
        'nzdt': 'Pacific/Auckland',
        'msk': 'Europe/Moscow',
        'east': 'Indian/Reunion',
        'west': 'Atlantic/Azores',
    }
    
    @staticmethod
    def get_timezone(tz_name: str) -> tzinfo:
        """
        Récupère un fuseau horaire
        
        Args:
            tz_name: Nom du fuseau horaire
            
        Returns:
            tzinfo: Fuseau horaire
        """
        # Normaliser le nom
        tz_name = tz_name.lower().strip()
        
        # Vérifier les alias
        if tz_name in TimezoneUtils.COMMON_TIMEZONES:
            tz_name = TimezoneUtils.COMMON_TIMEZONES[tz_name]
        
        try:
            return timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            try:
                return gettz(tz_name)
            except Exception:
                logger.warning(f"Unknown timezone: {tz_name}, falling back to UTC")
                return UTC
    
    @staticmethod
    def get_utc() -> tzinfo:
        """Récupère le fuseau horaire UTC"""
        return UTC
    
    @staticmethod
    def get_local() -> tzinfo:
        """Récupère le fuseau horaire local"""
        return tzlocal()
    
    @staticmethod
    def now(tz: Optional[Union[str, tzinfo]] = None) -> datetime:
        """
        Récupère la date/heure actuelle dans un fuseau
        
        Args:
            tz: Fuseau horaire
            
        Returns:
            datetime: Date/heure actuelle
        """
        if tz is None:
            tz = UTC
        
        if isinstance(tz, str):
            tz = TimezoneUtils.get_timezone(tz)
        
        return datetime.now(tz)
    
    @staticmethod
    def utcnow() -> datetime:
        """Récupère la date/heure UTC actuelle"""
        return datetime.now(UTC)
    
    @staticmethod
    def convert_timezone(
        dt: datetime,
        from_tz: Optional[Union[str, tzinfo]] = None,
        to_tz: Optional[Union[str, tzinfo]] = None
    ) -> datetime:
        """
        Convertit une date/heure d'un fuseau à l'autre
        
        Args:
            dt: Date/heure à convertir
            from_tz: Fuseau source
            to_tz: Fuseau cible
            
        Returns:
            datetime: Date/heure convertie
        """
        if from_tz is None:
            from_tz = UTC
        
        if to_tz is None:
            to_tz = UTC
        
        if isinstance(from_tz, str):
            from_tz = TimezoneUtils.get_timezone(from_tz)
        
        if isinstance(to_tz, str):
            to_tz = TimezoneUtils.get_timezone(to_tz)
        
        # Si la date n'a pas de fuseau, l'attacher
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=from_tz)
        
        return dt.astimezone(to_tz)
    
    @staticmethod
    def list_timezones() -> List[str]:
        """Récupère la liste des fuseaux horaires disponibles"""
        return pytz.all_timezones
    
    @staticmethod
    def get_timezone_offset(tz: Union[str, tzinfo], dt: Optional[datetime] = None) -> timedelta:
        """
        Récupère le décalage d'un fuseau horaire
        
        Args:
            tz: Fuseau horaire
            dt: Date/heure (optionnelle)
            
        Returns:
            timedelta: Décalage
        """
        if isinstance(tz, str):
            tz = TimezoneUtils.get_timezone(tz)
        
        if dt is None:
            dt = datetime.now(UTC)
        
        return tz.utcoffset(dt)
    
    @staticmethod
    def get_timezone_name(tz: Union[str, tzinfo]) -> str:
        """
        Récupère le nom d'un fuseau horaire
        
        Args:
            tz: Fuseau horaire
            
        Returns:
            str: Nom du fuseau
        """
        if isinstance(tz, str):
            return tz
        
        if hasattr(tz, 'zone'):
            return tz.zone
        
        return str(tz)
    
    @staticmethod
    def get_utc_offset(tz: Union[str, tzinfo]) -> str:
        """
        Récupère le décalage UTC en format string
        
        Args:
            tz: Fuseau horaire
            
        Returns:
            str: Décalage UTC
        """
        if isinstance(tz, str):
            tz = TimezoneUtils.get_timezone(tz)
        
        offset = tz.utcoffset(datetime.now(UTC))
        if offset is None:
            return "+00:00"
        
        hours = offset.seconds // 3600
        minutes = (offset.seconds % 3600) // 60
        sign = "+" if offset.days >= 0 else "-"
        
        return f"{sign}{hours:02d}:{minutes:02d}"

# ============================================================
# DATE UTILITIES
# ============================================================

class DateUtils:
    """Utilitaires de date"""
    
    @staticmethod
    def parse_date(
        date_string: str,
        formats: Optional[List[str]] = None,
        fuzzy: bool = True
    ) -> Optional[datetime]:
        """
        Parse une date à partir d'une chaîne
        
        Args:
            date_string: Chaîne à parser
            formats: Formats à essayer
            fuzzy: Utiliser le parsing flou
            
        Returns:
            Optional[datetime]: Date parsée
        """
        if not date_string:
            return None
        
        # Essayer les formats spécifiques
        if formats:
            for fmt in formats:
                try:
                    return datetime.strptime(date_string, fmt)
                except ValueError:
                    continue
        
        # Essayer avec dateutil
        try:
            return parser.parse(date_string, fuzzy=fuzzy)
        except Exception:
            pass
        
        # Essayer avec arrow
        try:
            return arrow.get(date_string).datetime
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def format_date(
        dt: Union[datetime, date, str],
        fmt: str = 'iso',
        tz: Optional[Union[str, tzinfo]] = None
    ) -> str:
        """
        Formate une date
        
        Args:
            dt: Date à formater
            fmt: Format ou nom de format
            tz: Fuseau horaire
            
        Returns:
            str: Date formatée
        """
        if isinstance(dt, str):
            dt = DateUtils.parse_date(dt)
            if dt is None:
                return ""
        
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime_time.min)
        
        if tz is not None and isinstance(dt, datetime):
            if isinstance(tz, str):
                tz = TimezoneUtils.get_timezone(tz)
            dt = TimezoneUtils.convert_timezone(dt, to_tz=tz)
        
        if fmt in DATE_FORMATS:
            fmt = DATE_FORMATS[fmt]
        
        return dt.strftime(fmt)
    
    @staticmethod
    def to_timestamp(dt: Union[datetime, date, str]) -> float:
        """
        Convertit une date en timestamp
        
        Args:
            dt: Date à convertir
            
        Returns:
            float: Timestamp
        """
        if isinstance(dt, str):
            dt = DateUtils.parse_date(dt)
            if dt is None:
                return 0.0
        
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime_time.min)
        
        return dt.timestamp()
    
    @staticmethod
    def to_timestamp_ms(dt: Union[datetime, date, str]) -> int:
        """
        Convertit une date en timestamp millisecondes
        
        Args:
            dt: Date à convertir
            
        Returns:
            int: Timestamp en millisecondes
        """
        return int(DateUtils.to_timestamp(dt) * MS_IN_SECOND)
    
    @staticmethod
    def from_timestamp(timestamp: float, tz: Optional[Union[str, tzinfo]] = None) -> datetime:
        """
        Convertit un timestamp en datetime
        
        Args:
            timestamp: Timestamp
            tz: Fuseau horaire
            
        Returns:
            datetime: Datetime
        """
        dt = datetime.fromtimestamp(timestamp, UTC)
        
        if tz is not None:
            if isinstance(tz, str):
                tz = TimezoneUtils.get_timezone(tz)
            dt = TimezoneUtils.convert_timezone(dt, to_tz=tz)
        
        return dt
    
    @staticmethod
    def from_timestamp_ms(timestamp_ms: int, tz: Optional[Union[str, tzinfo]] = None) -> datetime:
        """
        Convertit un timestamp millisecondes en datetime
        
        Args:
            timestamp_ms: Timestamp en millisecondes
            tz: Fuseau horaire
            
        Returns:
            datetime: Datetime
        """
        return DateUtils.from_timestamp(timestamp_ms / MS_IN_SECOND, tz)
    
    @staticmethod
    def round_date(
        dt: datetime,
        interval: str = 'minute',
        direction: str = 'nearest'
    ) -> datetime:
        """
        Arrondit une date à un intervalle
        
        Args:
            dt: Date à arrondir
            interval: Intervalle ('second', 'minute', 'hour', 'day', 'week', 'month', 'year')
            direction: Direction ('nearest', 'up', 'down')
            
        Returns:
            datetime: Date arrondie
        """
        intervals = {
            'second': timedelta(seconds=1),
            'minute': timedelta(minutes=1),
            'hour': timedelta(hours=1),
            'day': timedelta(days=1),
            'week': timedelta(weeks=1),
            'month': timedelta(days=30),
            'year': timedelta(days=365),
        }
        
        delta = intervals.get(interval, timedelta(minutes=1))
        
        if direction == 'down':
            return dt - (dt - datetime.min) % delta
        elif direction == 'up':
            return dt + (delta - (dt - datetime.min) % delta)
        else:  # nearest
            return dt + (delta / 2 - (dt - datetime.min) % delta)
    
    @staticmethod
    def floor_date(dt: datetime, interval: str = 'minute') -> datetime:
        """Arrondit une date à l'inférieur"""
        return DateUtils.round_date(dt, interval, 'down')
    
    @staticmethod
    def ceil_date(dt: datetime, interval: str = 'minute') -> datetime:
        """Arrondit une date au supérieur"""
        return DateUtils.round_date(dt, interval, 'up')
    
    @staticmethod
    def add_days(dt: datetime, days: int) -> datetime:
        """Ajoute des jours à une date"""
        return dt + timedelta(days=days)
    
    @staticmethod
    def add_hours(dt: datetime, hours: int) -> datetime:
        """Ajoute des heures à une date"""
        return dt + timedelta(hours=hours)
    
    @staticmethod
    def add_minutes(dt: datetime, minutes: int) -> datetime:
        """Ajoute des minutes à une date"""
        return dt + timedelta(minutes=minutes)
    
    @staticmethod
    def add_seconds(dt: datetime, seconds: int) -> datetime:
        """Ajoute des secondes à une date"""
        return dt + timedelta(seconds=seconds)
    
    @staticmethod
    def add_months(dt: datetime, months: int) -> datetime:
        """Ajoute des mois à une date"""
        return dt + relativedelta(months=months)
    
    @staticmethod
    def add_years(dt: datetime, years: int) -> datetime:
        """Ajoute des années à une date"""
        return dt + relativedelta(years=years)
    
    @staticmethod
    def days_between(dt1: datetime, dt2: datetime) -> int:
        """Calcule le nombre de jours entre deux dates"""
        return abs((dt2 - dt1).days)
    
    @staticmethod
    def hours_between(dt1: datetime, dt2: datetime) -> float:
        """Calcule le nombre d'heures entre deux dates"""
        return abs((dt2 - dt1).total_seconds() / SECONDS_IN_HOUR)
    
    @staticmethod
    def minutes_between(dt1: datetime, dt2: datetime) -> float:
        """Calcule le nombre de minutes entre deux dates"""
        return abs((dt2 - dt1).total_seconds() / SECONDS_IN_MINUTE)
    
    @staticmethod
    def seconds_between(dt1: datetime, dt2: datetime) -> float:
        """Calcule le nombre de secondes entre deux dates"""
        return abs((dt2 - dt1).total_seconds())
    
    @staticmethod
    def is_weekday(dt: datetime) -> bool:
        """Vérifie si une date est un jour de semaine"""
        return dt.weekday() < 5
    
    @staticmethod
    def is_weekend(dt: datetime) -> bool:
        """Vérifie si une date est un week-end"""
        return dt.weekday() >= 5
    
    @staticmethod
    def get_quarter(dt: datetime) -> int:
        """Récupère le trimestre"""
        return (dt.month - 1) // 3 + 1
    
    @staticmethod
    def get_week_number(dt: datetime) -> int:
        """Récupère le numéro de semaine"""
        return dt.isocalendar()[1]
    
    @staticmethod
    def get_month_name(dt: datetime, short: bool = False) -> str:
        """Récupère le nom du mois"""
        month_map = MONTH_NAMES_SHORT if short else MONTH_NAMES
        return month_map.get(dt.month, '')
    
    @staticmethod
    def get_day_name(dt: datetime, short: bool = False) -> str:
        """Récupère le nom du jour"""
        day_map = DAY_NAMES_SHORT if short else DAY_NAMES
        return day_map.get(dt.weekday(), '')

# ============================================================
# DATE RANGE UTILITIES
# ============================================================

class DateRangeUtils:
    """Utilitaires de plages de dates"""
    
    @staticmethod
    def date_range(
        start: datetime,
        end: datetime,
        step: str = 'day',
        inclusive: bool = True
    ) -> Generator[datetime, None, None]:
        """
        Génère une plage de dates
        
        Args:
            start: Date de début
            end: Date de fin
            step: Pas ('second', 'minute', 'hour', 'day', 'week', 'month', 'year')
            inclusive: Inclure la date de fin
            
        Yields:
            datetime: Date suivante
        """
        steps = {
            'second': timedelta(seconds=1),
            'minute': timedelta(minutes=1),
            'hour': timedelta(hours=1),
            'day': timedelta(days=1),
            'week': timedelta(weeks=1),
            'month': timedelta(days=30),
            'year': timedelta(days=365),
        }
        
        delta = steps.get(step, timedelta(days=1))
        
        current = start
        if inclusive:
            end = end + delta
        
        while current < end:
            yield current
            current += delta
    
    @staticmethod
    def date_range_rrule(
        start: datetime,
        end: datetime,
        freq: str = 'daily',
        interval: int = 1,
        byweekday: Optional[List[int]] = None,
        bymonthday: Optional[List[int]] = None,
        bymonth: Optional[List[int]] = None
    ) -> Generator[datetime, None, None]:
        """
        Génère une plage de dates avec rrule
        
        Args:
            start: Date de début
            end: Date de fin
            freq: Fréquence ('daily', 'weekly', 'monthly', 'yearly')
            interval: Intervalle
            byweekday: Jours de la semaine
            bymonthday: Jours du mois
            bymonth: Mois
            
        Yields:
            datetime: Date suivante
        """
        freq_map = {
            'daily': DAILY,
            'weekly': WEEKLY,
            'monthly': MONTHLY,
            'yearly': YEARLY,
        }
        
        freq_enum = freq_map.get(freq.lower(), DAILY)
        
        rule = rrule(
            freq=freq_enum,
            interval=interval,
            dtstart=start,
            until=end,
            byweekday=byweekday,
            bymonthday=bymonthday,
            bymonth=bymonth
        )
        
        for dt in rule:
            yield dt
    
    @staticmethod
    def split_date_range(
        start: datetime,
        end: datetime,
        chunk_size: int,
        chunk_unit: str = 'day'
    ) -> List[Tuple[datetime, datetime]]:
        """
        Divise une plage de dates en morceaux
        
        Args:
            start: Date de début
            end: Date de fin
            chunk_size: Taille des morceaux
            chunk_unit: Unité ('second', 'minute', 'hour', 'day', 'week', 'month', 'year')
            
        Returns:
            List[Tuple[datetime, datetime]]: Liste des morceaux
        """
        units = {
            'second': timedelta(seconds=1),
            'minute': timedelta(minutes=1),
            'hour': timedelta(hours=1),
            'day': timedelta(days=1),
            'week': timedelta(weeks=1),
            'month': timedelta(days=30),
            'year': timedelta(days=365),
        }
        
        delta = units.get(chunk_unit, timedelta(days=1)) * chunk_size
        
        chunks = []
        current = start
        
        while current < end:
            chunk_end = min(current + delta, end)
            chunks.append((current, chunk_end))
            current = chunk_end
        
        return chunks
    
    @staticmethod
    def overlapping_ranges(
        ranges: List[Tuple[datetime, datetime]]
    ) -> List[Tuple[datetime, datetime]]:
        """
        Fusionne les plages de dates qui se chevauchent
        
        Args:
            ranges: Liste des plages
            
        Returns:
            List[Tuple[datetime, datetime]]: Plages fusionnées
        """
        if not ranges:
            return []
        
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        merged = []
        current_start, current_end = sorted_ranges[0]
        
        for start, end in sorted_ranges[1:]:
            if start <= current_end:
                current_end = max(current_end, end)
            else:
                merged.append((current_start, current_end))
                current_start, current_end = start, end
        
        merged.append((current_start, current_end))
        return merged

# ============================================================
# DURATION UTILITIES
# ============================================================

class DurationUtils:
    """Utilitaires de durée"""
    
    @staticmethod
    def format_duration(seconds: float, short: bool = False, compact: bool = False) -> str:
        """
        Formate une durée en secondes
        
        Args:
            seconds: Durée en secondes
            short: Format court
            compact: Format compact
            
        Returns:
            str: Durée formatée
        """
        if seconds < 0:
            seconds = abs(seconds)
            prefix = "-"
        else:
            prefix = ""
        
        days = int(seconds // SECONDS_IN_DAY)
        hours = int((seconds % SECONDS_IN_DAY) // SECONDS_IN_HOUR)
        minutes = int((seconds % SECONDS_IN_HOUR) // SECONDS_IN_MINUTE)
        secs = int(seconds % SECONDS_IN_MINUTE)
        millis = int((seconds - int(seconds)) * 1000)
        
        parts = []
        
        if compact:
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if secs > 0:
                parts.append(f"{secs}s")
            if not parts:
                parts.append("0s")
        elif short:
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if secs > 0:
                parts.append(f"{secs}s")
            if not parts:
                parts.append("0s")
        else:
            if days > 0:
                parts.append(f"{days} day{'s' if days > 1 else ''}")
            if hours > 0:
                parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
            if minutes > 0:
                parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
            if secs > 0:
                parts.append(f"{secs} second{'s' if secs > 1 else ''}")
            if not parts:
                parts.append("0 seconds")
            if millis > 0 and secs == 0:
                parts.append(f"{millis} millisecond{'s' if millis > 1 else ''}")
        
        return prefix + " ".join(parts)
    
    @staticmethod
    def format_duration_human(seconds: float) -> str:
        """
        Formate une durée en format lisible
        
        Args:
            seconds: Durée en secondes
            
        Returns:
            str: Durée lisible
        """
        if seconds < SECONDS_IN_MINUTE:
            return f"{seconds:.1f}s"
        elif seconds < SECONDS_IN_HOUR:
            minutes = seconds / SECONDS_IN_MINUTE
            return f"{minutes:.1f}m"
        elif seconds < SECONDS_IN_DAY:
            hours = seconds / SECONDS_IN_HOUR
            return f"{hours:.1f}h"
        elif seconds < SECONDS_IN_WEEK:
            days = seconds / SECONDS_IN_DAY
            return f"{days:.1f}d"
        elif seconds < SECONDS_IN_MONTH:
            weeks = seconds / SECONDS_IN_WEEK
            return f"{weeks:.1f}w"
        else:
            months = seconds / SECONDS_IN_MONTH
            return f"{months:.1f}mo"
    
    @staticmethod
    def parse_duration(duration_string: str) -> float:
        """
        Parse une durée à partir d'une chaîne
        
        Args:
            duration_string: Chaîne de durée (ex: "2d 3h 15m")
            
        Returns:
            float: Durée en secondes
        """
        if not duration_string:
            return 0.0
        
        total_seconds = 0.0
        pattern = r'(\d+\.?\d*)\s*([a-z]+)'
        
        for match in re.findall(pattern, duration_string.lower()):
            value = float(match[0])
            unit = match[1]
            
            if unit in ['s', 'sec', 'second', 'seconds']:
                total_seconds += value
            elif unit in ['m', 'min', 'minute', 'minutes']:
                total_seconds += value * SECONDS_IN_MINUTE
            elif unit in ['h', 'hr', 'hour', 'hours']:
                total_seconds += value * SECONDS_IN_HOUR
            elif unit in ['d', 'day', 'days']:
                total_seconds += value * SECONDS_IN_DAY
            elif unit in ['w', 'week', 'weeks']:
                total_seconds += value * SECONDS_IN_WEEK
            elif unit in ['mo', 'month', 'months']:
                total_seconds += value * SECONDS_IN_MONTH
            elif unit in ['y', 'yr', 'year', 'years']:
                total_seconds += value * SECONDS_IN_YEAR
            elif unit in ['ms', 'millisecond', 'milliseconds']:
                total_seconds += value / 1000
        
        return total_seconds
    
    @staticmethod
    def parse_duration_compact(duration_string: str) -> float:
        """
        Parse une durée compacte (ex: "2d3h15m")
        
        Args:
            duration_string: Chaîne de durée compacte
            
        Returns:
            float: Durée en secondes
        """
        if not duration_string:
            return 0.0
        
        total_seconds = 0.0
        pattern = r'(\d+\.?\d*)([dhms])'
        
        unit_map = {
            'd': SECONDS_IN_DAY,
            'h': SECONDS_IN_HOUR,
            'm': SECONDS_IN_MINUTE,
            's': 1,
        }
        
        for match in re.findall(pattern, duration_string.lower()):
            value = float(match[0])
            unit = match[1]
            total_seconds += value * unit_map.get(unit, 1)
        
        return total_seconds

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Constantes
    'SECONDS_IN_MINUTE',
    'SECONDS_IN_HOUR',
    'SECONDS_IN_DAY',
    'SECONDS_IN_WEEK',
    'SECONDS_IN_MONTH',
    'SECONDS_IN_YEAR',
    'MS_IN_SECOND',
    'MS_IN_MINUTE',
    'MS_IN_HOUR',
    'MS_IN_DAY',
    'MS_IN_WEEK',
    'MS_IN_MONTH',
    'MS_IN_YEAR',
    'DATE_FORMATS',
    'MONTH_NAMES',
    'MONTH_NAMES_SHORT',
    'DAY_NAMES',
    'DAY_NAMES_SHORT',
    
    # Classes
    'TimezoneUtils',
    'DateUtils',
    'DateRangeUtils',
    'DurationUtils',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Date utilities module initialized")

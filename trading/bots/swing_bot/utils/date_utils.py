"""
Swing Bot Date Utilities Module
================================

This module provides date and time utilities for the Swing Bot trading system.
Includes date formatting, timezone handling, and date calculations.
"""

import time
import calendar
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Union, List, Tuple, Dict, Any
import pytz
from dateutil import parser, relativedelta, tz
import holidays


class DateUtils:
    """
    Utility class for date and time operations.
    """
    
    # Common date formats
    DATE_FORMATS = {
        'iso': '%Y-%m-%d',
        'iso_with_time': '%Y-%m-%d %H:%M:%S',
        'iso_with_millis': '%Y-%m-%d %H:%M:%S.%f',
        'us': '%m/%d/%Y',
        'us_with_time': '%m/%d/%Y %H:%M:%S',
        'european': '%d/%m/%Y',
        'european_with_time': '%d/%m/%Y %H:%M:%S',
        'timestamp': '%Y%m%d_%H%M%S',
        'filename': '%Y-%m-%d_%H-%M-%S',
        'date_filename': '%Y-%m-%d',
    }
    
    @staticmethod
    def now() -> datetime:
        """
        Get current UTC time.
        
        Returns:
            Current UTC datetime
        """
        return datetime.utcnow()
    
    @staticmethod
    def now_local() -> datetime:
        """
        Get current local time.
        
        Returns:
            Current local datetime
        """
        return datetime.now()
    
    @staticmethod
    def today() -> date:
        """
        Get today's date.
        
        Returns:
            Today's date
        """
        return DateUtils.now().date()
    
    @staticmethod
    def utcnow() -> datetime:
        """
        Get current UTC time with timezone.
        
        Returns:
            Current UTC datetime with timezone
        """
        return datetime.now(timezone.utc)
    
    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """
        Convert datetime to UTC.
        
        Args:
            dt: Datetime to convert
        
        Returns:
            UTC datetime
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def to_local(dt: datetime) -> datetime:
        """
        Convert datetime to local timezone.
        
        Args:
            dt: Datetime to convert
        
        Returns:
            Local datetime
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz.tzlocal())
    
    @staticmethod
    def to_timezone(dt: datetime, timezone_str: str) -> datetime:
        """
        Convert datetime to a specific timezone.
        
        Args:
            dt: Datetime to convert
            timezone_str: Timezone name (e.g., 'America/New_York')
        
        Returns:
            Timezone-aware datetime
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(pytz.timezone(timezone_str))
    
    @staticmethod
    def parse_date(
        date_str: str,
        formats: Optional[List[str]] = None,
        fuzzy: bool = True
    ) -> Optional[datetime]:
        """
        Parse a date string.
        
        Args:
            date_str: Date string to parse
            formats: List of format strings to try
            fuzzy: Use fuzzy parsing
        
        Returns:
            Parsed datetime or None
        """
        if formats:
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        
        try:
            return parser.parse(date_str, fuzzy=fuzzy)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def format_date(
        dt: Union[datetime, date, str],
        format_str: str = 'iso'
    ) -> str:
        """
        Format a date.
        
        Args:
            dt: Date to format
            format_str: Format string or format key
        
        Returns:
            Formatted date string
        """
        if isinstance(dt, str):
            dt = DateUtils.parse_date(dt)
            if dt is None:
                return dt
        
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime.min.time())
        
        if format_str in DateUtils.DATE_FORMATS:
            format_str = DateUtils.DATE_FORMATS[format_str]
        
        return dt.strftime(format_str)
    
    @staticmethod
    def format_timestamp(timestamp: Union[int, float], format_str: str = 'iso') -> str:
        """
        Format a timestamp.
        
        Args:
            timestamp: Unix timestamp
            format_str: Format string or format key
        
        Returns:
            Formatted date string
        """
        dt = datetime.fromtimestamp(timestamp)
        return DateUtils.format_date(dt, format_str)
    
    @staticmethod
    def parse_timestamp(date_str: str) -> Optional[float]:
        """
        Parse a date string to timestamp.
        
        Args:
            date_str: Date string to parse
        
        Returns:
            Unix timestamp or None
        """
        dt = DateUtils.parse_date(date_str)
        if dt:
            return dt.timestamp()
        return None
    
    @staticmethod
    def add_days(dt: Union[datetime, date], days: int) -> Union[datetime, date]:
        """
        Add days to a date.
        
        Args:
            dt: Date to add to
            days: Number of days to add
        
        Returns:
            New date
        """
        return dt + timedelta(days=days)
    
    @staticmethod
    def add_weeks(dt: Union[datetime, date], weeks: int) -> Union[datetime, date]:
        """
        Add weeks to a date.
        
        Args:
            dt: Date to add to
            weeks: Number of weeks to add
        
        Returns:
            New date
        """
        return dt + timedelta(weeks=weeks)
    
    @staticmethod
    def add_months(dt: Union[datetime, date], months: int) -> Union[datetime, date]:
        """
        Add months to a date.
        
        Args:
            dt: Date to add to
            months: Number of months to add
        
        Returns:
            New date
        """
        if isinstance(dt, datetime):
            return dt + relativedelta.relativedelta(months=months)
        return dt + relativedelta.relativedelta(months=months)
    
    @staticmethod
    def add_years(dt: Union[datetime, date], years: int) -> Union[datetime, date]:
        """
        Add years to a date.
        
        Args:
            dt: Date to add to
            years: Number of years to add
        
        Returns:
            New date
        """
        if isinstance(dt, datetime):
            return dt + relativedelta.relativedelta(years=years)
        return dt + relativedelta.relativedelta(years=years)
    
    @staticmethod
    def diff_days(start: Union[datetime, date], end: Union[datetime, date]) -> int:
        """
        Calculate difference in days.
        
        Args:
            start: Start date
            end: End date
        
        Returns:
            Number of days
        """
        return (end - start).days
    
    @staticmethod
    def diff_seconds(start: datetime, end: datetime) -> float:
        """
        Calculate difference in seconds.
        
        Args:
            start: Start datetime
            end: End datetime
        
        Returns:
            Number of seconds
        """
        return (end - start).total_seconds()
    
    @staticmethod
    def diff_minutes(start: datetime, end: datetime) -> float:
        """
        Calculate difference in minutes.
        
        Args:
            start: Start datetime
            end: End datetime
        
        Returns:
            Number of minutes
        """
        return DateUtils.diff_seconds(start, end) / 60
    
    @staticmethod
    def diff_hours(start: datetime, end: datetime) -> float:
        """
        Calculate difference in hours.
        
        Args:
            start: Start datetime
            end: End datetime
        
        Returns:
            Number of hours
        """
        return DateUtils.diff_seconds(start, end) / 3600
    
    @staticmethod
    def get_weekday(dt: Union[datetime, date]) -> int:
        """
        Get weekday (0=Monday, 6=Sunday).
        
        Args:
            dt: Date
        
        Returns:
            Weekday number
        """
        return dt.weekday()
    
    @staticmethod
    def get_weekday_name(dt: Union[datetime, date], full: bool = False) -> str:
        """
        Get weekday name.
        
        Args:
            dt: Date
            full: Return full name (True) or abbreviated (False)
        
        Returns:
            Weekday name
        """
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        short_weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        idx = dt.weekday()
        return weekdays[idx] if full else short_weekdays[idx]
    
    @staticmethod
    def get_month_name(dt: Union[datetime, date], full: bool = False) -> str:
        """
        Get month name.
        
        Args:
            dt: Date
            full: Return full name (True) or abbreviated (False)
        
        Returns:
            Month name
        """
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        short_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        idx = dt.month - 1
        return months[idx] if full else short_months[idx]
    
    @staticmethod
    def get_days_in_month(year: int, month: int) -> int:
        """
        Get number of days in a month.
        
        Args:
            year: Year
            month: Month (1-12)
        
        Returns:
            Number of days
        """
        return calendar.monthrange(year, month)[1]
    
    @staticmethod
    def get_week_number(dt: Union[datetime, date]) -> int:
        """
        Get ISO week number.
        
        Args:
            dt: Date
        
        Returns:
            Week number
        """
        return dt.isocalendar()[1]
    
    @staticmethod
    def get_quarter(dt: Union[datetime, date]) -> int:
        """
        Get quarter (1-4).
        
        Args:
            dt: Date
        
        Returns:
            Quarter number
        """
        return (dt.month - 1) // 3 + 1
    
    @staticmethod
    def get_quarter_start(dt: Union[datetime, date]) -> datetime:
        """
        Get start of quarter.
        
        Args:
            dt: Date
        
        Returns:
            Start of quarter datetime
        """
        quarter = DateUtils.get_quarter(dt)
        if quarter == 1:
            return datetime(dt.year, 1, 1)
        elif quarter == 2:
            return datetime(dt.year, 4, 1)
        elif quarter == 3:
            return datetime(dt.year, 7, 1)
        else:
            return datetime(dt.year, 10, 1)
    
    @staticmethod
    def get_quarter_end(dt: Union[datetime, date]) -> datetime:
        """
        Get end of quarter.
        
        Args:
            dt: Date
        
        Returns:
            End of quarter datetime
        """
        quarter = DateUtils.get_quarter(dt)
        if quarter == 1:
            return datetime(dt.year, 3, 31, 23, 59, 59)
        elif quarter == 2:
            return datetime(dt.year, 6, 30, 23, 59, 59)
        elif quarter == 3:
            return datetime(dt.year, 9, 30, 23, 59, 59)
        else:
            return datetime(dt.year, 12, 31, 23, 59, 59)
    
    @staticmethod
    def get_year_start(dt: Union[datetime, date]) -> datetime:
        """
        Get start of year.
        
        Args:
            dt: Date
        
        Returns:
            Start of year datetime
        """
        return datetime(dt.year, 1, 1)
    
    @staticmethod
    def get_year_end(dt: Union[datetime, date]) -> datetime:
        """
        Get end of year.
        
        Args:
            dt: Date
        
        Returns:
            End of year datetime
        """
        return datetime(dt.year, 12, 31, 23, 59, 59)
    
    @staticmethod
    def get_month_start(dt: Union[datetime, date]) -> datetime:
        """
        Get start of month.
        
        Args:
            dt: Date
        
        Returns:
            Start of month datetime
        """
        return datetime(dt.year, dt.month, 1)
    
    @staticmethod
    def get_month_end(dt: Union[datetime, date]) -> datetime:
        """
        Get end of month.
        
        Args:
            dt: Date
        
        Returns:
            End of month datetime
        """
        days = DateUtils.get_days_in_month(dt.year, dt.month)
        return datetime(dt.year, dt.month, days, 23, 59, 59)
    
    @staticmethod
    def get_week_start(dt: Union[datetime, date]) -> datetime:
        """
        Get start of week (Monday).
        
        Args:
            dt: Date
        
        Returns:
            Start of week datetime
        """
        weekday = dt.weekday()
        start = dt - timedelta(days=weekday)
        return datetime(start.year, start.month, start.day)
    
    @staticmethod
    def get_week_end(dt: Union[datetime, date]) -> datetime:
        """
        Get end of week (Sunday).
        
        Args:
            dt: Date
        
        Returns:
            End of week datetime
        """
        start = DateUtils.get_week_start(dt)
        end = start + timedelta(days=6)
        return datetime(end.year, end.month, end.day, 23, 59, 59)
    
    @staticmethod
    def is_weekday(dt: Union[datetime, date]) -> bool:
        """
        Check if date is a weekday (Monday-Friday).
        
        Args:
            dt: Date
        
        Returns:
            True if weekday, False otherwise
        """
        return dt.weekday() < 5
    
    @staticmethod
    def is_weekend(dt: Union[datetime, date]) -> bool:
        """
        Check if date is a weekend (Saturday-Sunday).
        
        Args:
            dt: Date
        
        Returns:
            True if weekend, False otherwise
        """
        return dt.weekday() >= 5
    
    @staticmethod
    def is_market_open(dt: Union[datetime, date], market: str = 'US') -> bool:
        """
        Check if a market is open on a given date.
        
        Args:
            dt: Date to check
            market: Market code ('US', 'UK', 'JP', etc.)
        
        Returns:
            True if market is open, False otherwise
        """
        # Get market holidays
        if market == 'US':
            market_holidays = holidays.US()
        elif market == 'UK':
            market_holidays = holidays.UK()
        elif market == 'JP':
            market_holidays = holidays.Japan()
        elif market == 'CA':
            market_holidays = holidays.Canada()
        elif market == 'DE':
            market_holidays = holidays.Germany()
        elif market == 'FR':
            market_holidays = holidays.France()
        else:
            market_holidays = {}
        
        # Check if date is a holiday
        if dt in market_holidays:
            return False
        
        # Check if date is a weekend
        if DateUtils.is_weekend(dt):
            return False
        
        return True
    
    @staticmethod
    def get_timezone_offset(timezone_str: str) -> int:
        """
        Get timezone offset in seconds.
        
        Args:
            timezone_str: Timezone name
        
        Returns:
            Offset in seconds
        """
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        return now.utcoffset().total_seconds()
    
    @staticmethod
    def get_timezone_name(dt: datetime) -> str:
        """
        Get timezone name.
        
        Args:
            dt: Datetime
        
        Returns:
            Timezone name
        """
        if dt.tzinfo is None:
            return 'UTC'
        return dt.tzinfo.tzname(dt)
    
    @staticmethod
    def generate_date_range(
        start: Union[datetime, date],
        end: Union[datetime, date],
        step: Union[timedelta, str] = timedelta(days=1)
    ) -> List[datetime]:
        """
        Generate a range of dates.
        
        Args:
            start: Start date
            end: End date
            step: Step size (timedelta or 'days', 'weeks', 'months')
        
        Returns:
            List of dates
        """
        if isinstance(step, str):
            step_map = {
                'days': timedelta(days=1),
                'weeks': timedelta(weeks=1),
                'months': timedelta(days=30),
                'years': timedelta(days=365),
            }
            step = step_map.get(step, timedelta(days=1))
        
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += step
        
        return dates
    
    @staticmethod
    def generate_trading_days(
        start: Union[datetime, date],
        end: Union[datetime, date],
        market: str = 'US'
    ) -> List[datetime]:
        """
        Generate a range of trading days.
        
        Args:
            start: Start date
            end: End date
            market: Market code
        
        Returns:
            List of trading days
        """
        dates = []
        current = start
        while current <= end:
            if DateUtils.is_market_open(current, market):
                dates.append(current)
            current += timedelta(days=1)
        
        return dates
    
    @staticmethod
    def get_trading_days_count(
        start: Union[datetime, date],
        end: Union[datetime, date],
        market: str = 'US'
    ) -> int:
        """
        Get number of trading days between two dates.
        
        Args:
            start: Start date
            end: End date
            market: Market code
        
        Returns:
            Number of trading days
        """
        return len(DateUtils.generate_trading_days(start, end, market))


# Function aliases for easier import
now = DateUtils.now
now_local = DateUtils.now_local
today = DateUtils.today
utcnow = DateUtils.utcnow
to_utc = DateUtils.to_utc
to_local = DateUtils.to_local
to_timezone = DateUtils.to_timezone
parse_date = DateUtils.parse_date
format_date = DateUtils.format_date
format_timestamp = DateUtils.format_timestamp
parse_timestamp = DateUtils.parse_timestamp
add_days = DateUtils.add_days
add_weeks = DateUtils.add_weeks
add_months = DateUtils.add_months
add_years = DateUtils.add_years
diff_days = DateUtils.diff_days
diff_seconds = DateUtils.diff_seconds
diff_minutes = DateUtils.diff_minutes
diff_hours = DateUtils.diff_hours
get_weekday = DateUtils.get_weekday
get_weekday_name = DateUtils.get_weekday_name
get_month_name = DateUtils.get_month_name
get_days_in_month = DateUtils.get_days_in_month
get_week_number = DateUtils.get_week_number
get_quarter = DateUtils.get_quarter
get_quarter_start = DateUtils.get_quarter_start
get_quarter_end = DateUtils.get_quarter_end
get_year_start = DateUtils.get_year_start
get_year_end = DateUtils.get_year_end
get_month_start = DateUtils.get_month_start
get_month_end = DateUtils.get_month_end
get_week_start = DateUtils.get_week_start
get_week_end = DateUtils.get_week_end
is_weekday = DateUtils.is_weekday
is_weekend = DateUtils.is_weekend
is_market_open = DateUtils.is_market_open
get_timezone_offset = DateUtils.get_timezone_offset
get_timezone_name = DateUtils.get_timezone_name
generate_date_range = DateUtils.generate_date_range
generate_trading_days = DateUtils.generate_trading_days
get_trading_days_count = DateUtils.get_trading_days_count


__all__ = [
    # Class
    'DateUtils',
    
    # Constants
    'DATE_FORMATS',
    
    # Function aliases
    'now',
    'now_local',
    'today',
    'utcnow',
    'to_utc',
    'to_local',
    'to_timezone',
    'parse_date',
    'format_date',
    'format_timestamp',
    'parse_timestamp',
    'add_days',
    'add_weeks',
    'add_months',
    'add_years',
    'diff_days',
    'diff_seconds',
    'diff_minutes',
    'diff_hours',
    'get_weekday',
    'get_weekday_name',
    'get_month_name',
    'get_days_in_month',
    'get_week_number',
    'get_quarter',
    'get_quarter_start',
    'get_quarter_end',
    'get_year_start',
    'get_year_end',
    'get_month_start',
    'get_month_end',
    'get_week_start',
    'get_week_end',
    'is_weekday',
    'is_weekend',
    'is_market_open',
    'get_timezone_offset',
    'get_timezone_name',
    'generate_date_range',
    'generate_trading_days',
    'get_trading_days_count',
]

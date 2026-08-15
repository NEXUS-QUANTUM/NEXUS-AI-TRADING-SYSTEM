"""
Swing Bot Formatters Module
============================

This module provides formatting utilities for the Swing Bot trading system.
Includes data formatters, output formatters, and display utilities.
"""

import json
import yaml
import csv
import io
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np


class Formatters:
    """
    Utility class for formatting data.
    """
    
    @staticmethod
    def format_price(price: float, precision: int = 2, currency: Optional[str] = None) -> str:
        """
        Format a price value.
        
        Args:
            price: Price value
            precision: Number of decimal places
            currency: Currency symbol
        
        Returns:
            Formatted price string
        """
        formatted = f"{price:.{precision}f}"
        if currency:
            formatted = f"{currency}{formatted}"
        return formatted
    
    @staticmethod
    def format_quantity(quantity: float, precision: int = 0) -> str:
        """
        Format a quantity value.
        
        Args:
            quantity: Quantity value
            precision: Number of decimal places
        
        Returns:
            Formatted quantity string
        """
        return f"{quantity:.{precision}f}"
    
    @staticmethod
    def format_percentage(value: float, precision: int = 2, include_sign: bool = True) -> str:
        """
        Format a percentage value.
        
        Args:
            value: Percentage value (0.01 = 1%)
            precision: Number of decimal places
            include_sign: Include + or - sign
        
        Returns:
            Formatted percentage string
        """
        sign = ""
        if include_sign and value > 0:
            sign = "+"
        formatted = f"{sign}{value * 100:.{precision}f}%"
        return formatted
    
    @staticmethod
    def format_currency(amount: float, currency: str = '$', precision: int = 2) -> str:
        """
        Format a currency amount.
        
        Args:
            amount: Amount value
            currency: Currency symbol
            precision: Number of decimal places
        
        Returns:
            Formatted currency string
        """
        return f"{currency}{amount:,.{precision}f}"
    
    @staticmethod
    def format_volume(volume: float, precision: int = 0) -> str:
        """
        Format a volume value.
        
        Args:
            volume: Volume value
            precision: Number of decimal places
        
        Returns:
            Formatted volume string
        """
        if volume >= 1e12:
            return f"{volume / 1e12:.{precision}f}T"
        elif volume >= 1e9:
            return f"{volume / 1e9:.{precision}f}B"
        elif volume >= 1e6:
            return f"{volume / 1e6:.{precision}f}M"
        elif volume >= 1e3:
            return f"{volume / 1e3:.{precision}f}K"
        else:
            return f"{volume:.{precision}f}"
    
    @staticmethod
    def format_duration(seconds: float, precision: int = 1) -> str:
        """
        Format a duration in seconds.
        
        Args:
            seconds: Duration in seconds
            precision: Number of decimal places
        
        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds:.{precision}f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.{precision}f}m"
        elif seconds < 86400:
            return f"{seconds / 3600:.{precision}f}h"
        else:
            return f"{seconds / 86400:.{precision}f}d"
    
    @staticmethod
    def format_datetime(dt: datetime, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
        """
        Format a datetime object.
        
        Args:
            dt: Datetime object
            fmt: Format string
        
        Returns:
            Formatted datetime string
        """
        return dt.strftime(fmt)
    
    @staticmethod
    def format_date(dt: datetime, fmt: str = '%Y-%m-%d') -> str:
        """
        Format a date object.
        
        Args:
            dt: Datetime object
            fmt: Format string
        
        Returns:
            Formatted date string
        """
        return dt.strftime(fmt)
    
    @staticmethod
    def format_time(dt: datetime, fmt: str = '%H:%M:%S') -> str:
        """
        Format a time object.
        
        Args:
            dt: Datetime object
            fmt: Format string
        
        Returns:
            Formatted time string
        """
        return dt.strftime(fmt)
    
    @staticmethod
    def format_timestamp(timestamp: int, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
        """
        Format a Unix timestamp.
        
        Args:
            timestamp: Unix timestamp
            fmt: Format string
        
        Returns:
            Formatted timestamp string
        """
        dt = datetime.fromtimestamp(timestamp)
        return Formatters.format_datetime(dt, fmt)
    
    @staticmethod
    def format_interval(start: datetime, end: datetime) -> str:
        """
        Format a time interval.
        
        Args:
            start: Start datetime
            end: End datetime
        
        Returns:
            Formatted interval string
        """
        duration = end - start
        days = duration.days
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        
        return " ".join(parts) if parts else "0m"
    
    @staticmethod
    def format_size(size: int, precision: int = 2) -> str:
        """
        Format a size in bytes.
        
        Args:
            size: Size in bytes
            precision: Number of decimal places
        
        Returns:
            Formatted size string
        """
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        i = 0
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.{precision}f} {units[i]}"
    
    @staticmethod
    def format_number(value: float, precision: int = 2, thousands_sep: bool = True) -> str:
        """
        Format a number.
        
        Args:
            value: Number value
            precision: Number of decimal places
            thousands_sep: Use thousands separator
        
        Returns:
            Formatted number string
        """
        if thousands_sep:
            return f"{value:,.{precision}f}"
        return f"{value:.{precision}f}"
    
    @staticmethod
    def format_hex(data: bytes, separator: str = ' ') -> str:
        """
        Format bytes as hex string.
        
        Args:
            data: Bytes data
            separator: Separator between bytes
        
        Returns:
            Formatted hex string
        """
        return separator.join(f"{b:02x}" for b in data)
    
    @staticmethod
    def format_json(data: Any, indent: int = 2, sort_keys: bool = True) -> str:
        """
        Format data as JSON string.
        
        Args:
            data: Data to format
            indent: Indentation level
            sort_keys: Sort dictionary keys
        
        Returns:
            Formatted JSON string
        """
        return json.dumps(data, indent=indent, sort_keys=sort_keys, default=str)
    
    @staticmethod
    def format_yaml(data: Any, indent: int = 2) -> str:
        """
        Format data as YAML string.
        
        Args:
            data: Data to format
            indent: Indentation level
        
        Returns:
            Formatted YAML string
        """
        return yaml.dump(data, indent=indent, default_flow_style=False)
    
    @staticmethod
    def format_csv(data: List[Dict[str, Any]], delimiter: str = ',') -> str:
        """
        Format data as CSV string.
        
        Args:
            data: List of dictionaries
            delimiter: CSV delimiter
        
        Returns:
            Formatted CSV string
        """
        if not data:
            return ""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys(), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()
    
    @staticmethod
    def format_table(data: List[Dict[str, Any]], headers: Optional[List[str]] = None) -> str:
        """
        Format data as a table.
        
        Args:
            data: List of dictionaries
            headers: Column headers
        
        Returns:
            Formatted table string
        """
        if not data:
            return ""
        
        headers = headers or list(data[0].keys())
        
        # Calculate column widths
        widths = {h: len(str(h)) for h in headers}
        for row in data:
            for h in headers:
                value = str(row.get(h, ''))
                widths[h] = max(widths[h], len(value))
        
        # Build table
        lines = []
        
        # Header
        header_line = " | ".join(h.ljust(widths[h]) for h in headers)
        lines.append(header_line)
        lines.append("-" * len(header_line))
        
        # Rows
        for row in data:
            line = " | ".join(str(row.get(h, '')).ljust(widths[h]) for h in headers)
            lines.append(line)
        
        return "\n".join(lines)
    
    @staticmethod
    def format_pandas(df: pd.DataFrame, max_rows: int = 20, max_cols: int = 10) -> str:
        """
        Format a pandas DataFrame.
        
        Args:
            df: DataFrame
            max_rows: Maximum rows to display
            max_cols: Maximum columns to display
        
        Returns:
            Formatted DataFrame string
        """
        with pd.option_context('display.max_rows', max_rows, 'display.max_columns', max_cols):
            return str(df)
    
    @staticmethod
    def format_numpy(arr: np.ndarray, precision: int = 4) -> str:
        """
        Format a numpy array.
        
        Args:
            arr: Numpy array
            precision: Number of decimal places
        
        Returns:
            Formatted array string
        """
        with np.printoptions(precision=precision, suppress=True):
            return str(arr)
    
    @staticmethod
    def format_dict(data: Dict[str, Any], indent: int = 0, prefix: str = '') -> str:
        """
        Format a dictionary as a string.
        
        Args:
            data: Dictionary to format
            indent: Indentation level
            prefix: Prefix string
        
        Returns:
            Formatted dictionary string
        """
        lines = []
        indent_str = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{indent_str}{prefix}{key}:")
                lines.append(Formatters.format_dict(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{indent_str}{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(Formatters.format_dict(item, indent + 1, "- "))
                    else:
                        lines.append(f"{indent_str}  - {item}")
            else:
                lines.append(f"{indent_str}{prefix}{key}: {value}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_list(data: List[Any], indent: int = 0, prefix: str = '') -> str:
        """
        Format a list as a string.
        
        Args:
            data: List to format
            indent: Indentation level
            prefix: Prefix string
        
        Returns:
            Formatted list string
        """
        lines = []
        indent_str = "  " * indent
        
        for item in data:
            if isinstance(item, dict):
                lines.append(Formatters.format_dict(item, indent, prefix))
            elif isinstance(item, list):
                lines.append(Formatters.format_list(item, indent, prefix))
            else:
                lines.append(f"{indent_str}{prefix}{item}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_error(error: Exception, include_traceback: bool = False) -> str:
        """
        Format an exception.
        
        Args:
            error: Exception object
            include_traceback: Include traceback
        
        Returns:
            Formatted error string
        """
        if include_traceback:
            import traceback
            return traceback.format_exc()
        return f"{type(error).__name__}: {str(error)}"
    
    @staticmethod
    def format_status(status: str, status_type: str = 'info') -> str:
        """
        Format a status message.
        
        Args:
            status: Status message
            status_type: Status type (info, success, warning, error)
        
        Returns:
            Formatted status string
        """
        icons = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌',
            'debug': '🐛',
        }
        icon = icons.get(status_type, 'ℹ️')
        return f"{icon} {status}"
    
    @staticmethod
    def format_progress(current: int, total: int, bar_length: int = 30) -> str:
        """
        Format a progress bar.
        
        Args:
            current: Current progress
            total: Total progress
            bar_length: Length of the progress bar
        
        Returns:
            Formatted progress bar string
        """
        progress = current / total
        filled = int(bar_length * progress)
        bar = '█' * filled + '░' * (bar_length - filled)
        percentage = progress * 100
        return f"[{bar}] {percentage:.1f}% ({current}/{total})"
    
    @staticmethod
    def format_address(address: str, prefix: int = 6, suffix: int = 4) -> str:
        """
        Format an address with prefix and suffix.
        
        Args:
            address: Full address
            prefix: Number of characters to show at start
            suffix: Number of characters to show at end
        
        Returns:
            Formatted address string
        """
        if len(address) <= prefix + suffix:
            return address
        return f"{address[:prefix]}...{address[-suffix:]}"


# Function aliases for easier import
format_price = Formatters.format_price
format_quantity = Formatters.format_quantity
format_percentage = Formatters.format_percentage
format_currency = Formatters.format_currency
format_volume = Formatters.format_volume
format_duration = Formatters.format_duration
format_datetime = Formatters.format_datetime
format_date = Formatters.format_date
format_time = Formatters.format_time
format_timestamp = Formatters.format_timestamp
format_interval = Formatters.format_interval
format_size = Formatters.format_size
format_number = Formatters.format_number
format_hex = Formatters.format_hex
format_json = Formatters.format_json
format_yaml = Formatters.format_yaml
format_csv = Formatters.format_csv
format_table = Formatters.format_table
format_pandas = Formatters.format_pandas
format_numpy = Formatters.format_numpy
format_dict = Formatters.format_dict
format_list = Formatters.format_list
format_error = Formatters.format_error
format_status = Formatters.format_status
format_progress = Formatters.format_progress
format_address = Formatters.format_address


__all__ = [
    # Class
    'Formatters',
    
    # Function aliases
    'format_price',
    'format_quantity',
    'format_percentage',
    'format_currency',
    'format_volume',
    'format_duration',
    'format_datetime',
    'format_date',
    'format_time',
    'format_timestamp',
    'format_interval',
    'format_size',
    'format_number',
    'format_hex',
    'format_json',
    'format_yaml',
    'format_csv',
    'format_table',
    'format_pandas',
    'format_numpy',
    'format_dict',
    'format_list',
    'format_error',
    'format_status',
    'format_progress',
    'format_address',
]

"""
Swing Bot Converters Module
============================

This module provides conversion utilities for the Swing Bot trading system.
Includes data type conversions, unit conversions, and format conversions.
"""

import json
import base64
import binascii
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
from decimal import Decimal


class Converters:
    """
    Utility class for data conversion operations.
    """
    
    @staticmethod
    def to_int(value: Any, default: int = 0) -> int:
        """
        Convert a value to int.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Int value or default
        """
        try:
            if isinstance(value, str):
                # Remove commas and whitespace
                value = value.replace(',', '').strip()
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def to_float(value: Any, default: float = 0.0) -> float:
        """
        Convert a value to float.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Float value or default
        """
        try:
            if isinstance(value, str):
                # Remove commas and whitespace
                value = value.replace(',', '').strip()
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def to_decimal(value: Any, default: Optional[Decimal] = None) -> Decimal:
        """
        Convert a value to Decimal.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Decimal value or default
        """
        if default is None:
            default = Decimal('0')
        try:
            if isinstance(value, str):
                value = value.replace(',', '').strip()
            return Decimal(str(value))
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def to_bool(value: Any, default: bool = False) -> bool:
        """
        Convert a value to bool.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Bool value or default
        """
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ('true', '1', 'yes', 'on', 'enabled'):
                return True
            if value_lower in ('false', '0', 'no', 'off', 'disabled'):
                return False
        
        if isinstance(value, (int, float)):
            return bool(value)
        
        return default
    
    @staticmethod
    def to_str(value: Any, default: str = '') -> str:
        """
        Convert a value to str.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            String value or default
        """
        if value is None:
            return default
        try:
            if isinstance(value, (list, dict)):
                return json.dumps(value, default=str)
            return str(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def to_bytes(value: Any, encoding: str = 'utf-8') -> bytes:
        """
        Convert a value to bytes.
        
        Args:
            value: Value to convert
            encoding: Encoding to use
        
        Returns:
            Bytes value
        """
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode(encoding)
        if isinstance(value, (int, float)):
            return str(value).encode(encoding)
        if isinstance(value, (list, dict)):
            return json.dumps(value, default=str).encode(encoding)
        return bytes(value)
    
    @staticmethod
    def to_json(value: Any, default: Optional[Dict] = None) -> Dict:
        """
        Convert a value to JSON/dict.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Dict value or default
        """
        if default is None:
            default = {}
        
        if isinstance(value, dict):
            return value
        
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        if hasattr(value, '__dict__'):
            return value.__dict__
        
        return default
    
    @staticmethod
    def to_list(value: Any, default: Optional[List] = None) -> List:
        """
        Convert a value to list.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            List value or default
        """
        if default is None:
            default = []
        
        if isinstance(value, list):
            return value
        
        if isinstance(value, tuple):
            return list(value)
        
        if isinstance(value, str):
            # Try to parse as JSON array
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                # Try to split by commas
                if ',' in value:
                    return [item.strip() for item in value.split(',')]
                return [value]
        
        if isinstance(value, (int, float, bool)):
            return [value]
        
        if value is None:
            return default
        
        return list(value) if hasattr(value, '__iter__') else default
    
    @staticmethod
    def to_datetime(
        value: Any,
        formats: Optional[List[str]] = None,
        default: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Convert a value to datetime.
        
        Args:
            value: Value to convert
            formats: List of format strings to try
            default: Default value if conversion fails
        
        Returns:
            Datetime value or default
        """
        if default is None:
            default = datetime.now()
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except (ValueError, OSError):
                pass
        
        if isinstance(value, str):
            # Try to parse with formats
            if formats:
                for fmt in formats:
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
            
            # Try common formats
            common_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%d',
                '%m/%d/%Y %H:%M:%S',
                '%m/%d/%Y',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y',
            ]
            for fmt in common_formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            
            # Try dateutil parser
            try:
                from dateutil import parser
                return parser.parse(value)
            except (ImportError, ValueError):
                pass
        
        return default
    
    @staticmethod
    def to_date(value: Any, default: Optional[date] = None) -> Optional[date]:
        """
        Convert a value to date.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Date value or default
        """
        if default is None:
            default = date.today()
        
        dt = Converters.to_datetime(value, default=default)
        return dt.date() if dt else default
    
    @staticmethod
    def to_timestamp(value: Any, default: int = 0) -> int:
        """
        Convert a value to Unix timestamp.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Unix timestamp or default
        """
        dt = Converters.to_datetime(value)
        if dt:
            return int(dt.timestamp())
        return default
    
    @staticmethod
    def to_base64(value: Union[str, bytes]) -> str:
        """
        Convert a value to base64 string.
        
        Args:
            value: Value to convert
        
        Returns:
            Base64 string
        """
        if isinstance(value, str):
            value = value.encode()
        return base64.b64encode(value).decode()
    
    @staticmethod
    def from_base64(value: str, encoding: str = 'utf-8') -> str:
        """
        Convert a base64 string to original value.
        
        Args:
            value: Base64 string
            encoding: Encoding to use
        
        Returns:
            Decoded string
        """
        decoded = base64.b64decode(value)
        return decoded.decode(encoding)
    
    @staticmethod
    def to_hex(value: Union[str, bytes]) -> str:
        """
        Convert a value to hex string.
        
        Args:
            value: Value to convert
        
        Returns:
            Hex string
        """
        if isinstance(value, str):
            value = value.encode()
        return value.hex()
    
    @staticmethod
    def from_hex(value: str, encoding: str = 'utf-8') -> str:
        """
        Convert a hex string to original value.
        
        Args:
            value: Hex string
            encoding: Encoding to use
        
        Returns:
            Decoded string
        """
        decoded = bytes.fromhex(value)
        return decoded.decode(encoding)
    
    @staticmethod
    def to_binary(value: Any, encoding: str = 'utf-8') -> bytes:
        """
        Convert a value to binary string.
        
        Args:
            value: Value to convert
            encoding: Encoding to use
        
        Returns:
            Binary string
        """
        return Converters.to_bytes(value, encoding)
    
    @staticmethod
    def from_binary(value: bytes, encoding: str = 'utf-8') -> str:
        """
        Convert a binary string to original value.
        
        Args:
            value: Binary string
            encoding: Encoding to use
        
        Returns:
            Decoded string
        """
        return value.decode(encoding)
    
    @staticmethod
    def to_percent(value: float, decimals: int = 2) -> str:
        """
        Convert a value to percentage string.
        
        Args:
            value: Value to convert (0.01 = 1%)
            decimals: Number of decimal places
        
        Returns:
            Percentage string
        """
        return f"{value * 100:.{decimals}f}%"
    
    @staticmethod
    def from_percent(value: str) -> float:
        """
        Convert a percentage string to value.
        
        Args:
            value: Percentage string (e.g., '10.5%')
        
        Returns:
            Value (0.105)
        """
        value = value.strip().replace('%', '')
        return float(value) / 100
    
    @staticmethod
    def to_currency(value: float, currency: str = '$', decimals: int = 2) -> str:
        """
        Convert a value to currency string.
        
        Args:
            value: Value to convert
            currency: Currency symbol
            decimals: Number of decimal places
        
        Returns:
            Currency string
        """
        return f"{currency}{value:,.{decimals}f}"
    
    @staticmethod
    def from_currency(value: str) -> float:
        """
        Convert a currency string to value.
        
        Args:
            value: Currency string (e.g., '$1,234.56')
        
        Returns:
            Value
        """
        value = value.strip()
        # Remove currency symbols
        for symbol in ['$', '€', '£', '¥', '₽', '₹', 'R$']:
            value = value.replace(symbol, '')
        # Remove commas
        value = value.replace(',', '')
        return float(value)
    
    @staticmethod
    def to_time(value: Any, default: Optional[datetime] = None) -> Optional[datetime]:
        """
        Convert a value to time.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Time value or default
        """
        dt = Converters.to_datetime(value, default=default)
        if dt:
            return dt.time()
        return default
    
    @staticmethod
    def to_timedelta(value: Any, default: Optional[timedelta] = None) -> Optional[timedelta]:
        """
        Convert a value to timedelta.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Timedelta value or default
        """
        if default is None:
            default = timedelta(0)
        
        if isinstance(value, timedelta):
            return value
        
        if isinstance(value, (int, float)):
            return timedelta(seconds=value)
        
        if isinstance(value, str):
            # Try to parse as HH:MM:SS
            parts = value.split(':')
            if len(parts) == 3:
                try:
                    hours, minutes, seconds = map(int, parts)
                    return timedelta(hours=hours, minutes=minutes, seconds=seconds)
                except ValueError:
                    pass
            
            # Try to parse as days
            try:
                return timedelta(days=float(value))
            except ValueError:
                pass
        
        return default
    
    @staticmethod
    def to_iso_format(dt: Union[datetime, date]) -> str:
        """
        Convert a datetime to ISO format.
        
        Args:
            dt: Datetime or date
        
        Returns:
            ISO format string
        """
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime.min.time())
        return dt.isoformat()
    
    @staticmethod
    def from_iso_format(value: str) -> datetime:
        """
        Convert an ISO format string to datetime.
        
        Args:
            value: ISO format string
        
        Returns:
            Datetime
        """
        return datetime.fromisoformat(value)
    
    @staticmethod
    def to_dataframe(data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Convert data to pandas DataFrame.
        
        Args:
            data: List of dictionaries
        
        Returns:
            Pandas DataFrame
        """
        return pd.DataFrame(data)
    
    @staticmethod
    def to_dict(data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Convert pandas DataFrame to list of dictionaries.
        
        Args:
            data: Pandas DataFrame
        
        Returns:
            List of dictionaries
        """
        return data.to_dict('records')
    
    @staticmethod
    def to_numpy(data: Union[List, pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Convert data to numpy array.
        
        Args:
            data: Data to convert
        
        Returns:
            Numpy array
        """
        if isinstance(data, np.ndarray):
            return data
        if isinstance(data, pd.DataFrame):
            return data.values
        if isinstance(data, (list, tuple)):
            return np.array(data)
        return np.array([data])
    
    @staticmethod
    def to_series(data: List[Any]) -> pd.Series:
        """
        Convert data to pandas Series.
        
        Args:
            data: List of values
        
        Returns:
            Pandas Series
        """
        return pd.Series(data)


# Function aliases for easier import
to_int = Converters.to_int
to_float = Converters.to_float
to_decimal = Converters.to_decimal
to_bool = Converters.to_bool
to_str = Converters.to_str
to_bytes = Converters.to_bytes
to_json = Converters.to_json
to_list = Converters.to_list
to_datetime = Converters.to_datetime
to_date = Converters.to_date
to_timestamp = Converters.to_timestamp
to_base64 = Converters.to_base64
from_base64 = Converters.from_base64
to_hex = Converters.to_hex
from_hex = Converters.from_hex
to_binary = Converters.to_binary
from_binary = Converters.from_binary
to_percent = Converters.to_percent
from_percent = Converters.from_percent
to_currency = Converters.to_currency
from_currency = Converters.from_currency
to_time = Converters.to_time
to_timedelta = Converters.to_timedelta
to_iso_format = Converters.to_iso_format
from_iso_format = Converters.from_iso_format
to_dataframe = Converters.to_dataframe
to_dict = Converters.to_dict
to_numpy = Converters.to_numpy
to_series = Converters.to_series


__all__ = [
    # Class
    'Converters',
    
    # Function aliases
    'to_int',
    'to_float',
    'to_decimal',
    'to_bool',
    'to_str',
    'to_bytes',
    'to_json',
    'to_list',
    'to_datetime',
    'to_date',
    'to_timestamp',
    'to_base64',
    'from_base64',
    'to_hex',
    'from_hex',
    'to_binary',
    'from_binary',
    'to_percent',
    'from_percent',
    'to_currency',
    'from_currency',
    'to_time',
    'to_timedelta',
    'to_iso_format',
    'from_iso_format',
    'to_dataframe',
    'to_dict',
    'to_numpy',
    'to_series',
]

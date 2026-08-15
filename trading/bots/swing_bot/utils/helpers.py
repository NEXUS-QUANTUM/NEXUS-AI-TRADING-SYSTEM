"""
Swing Bot Helpers Module.
=========================

This module provides helper utilities for the Swing Bot trading system.
Includes general-purpose helper functions and utilities.
"""

import os
import sys
import json
import yaml
import pickle
import hashlib
import base64
import inspect
import functools
import contextlib
import tempfile
import shutil
from typing import Any, Dict, List, Optional, Union, Callable, Tuple, TypeVar
from datetime import datetime, timedelta
from pathlib import Path
import logging
import importlib
import subprocess
import platform


T = TypeVar('T')


class Helpers:
    """
    Utility class for general-purpose helper functions.
    """
    
    @staticmethod
    def ensure_dir(path: Union[str, Path]) -> Path:
        """
        Ensure a directory exists.
        
        Args:
            path: Directory path
        
        Returns:
            Path object
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def ensure_file(path: Union[str, Path], content: Optional[str] = None) -> Path:
        """
        Ensure a file exists.
        
        Args:
            path: File path
            content: Content to write if file doesn't exist
        
        Returns:
            Path object
        """
        path = Path(path)
        Helpers.ensure_dir(path.parent)
        if not path.exists() and content is not None:
            path.write_text(content)
        return path
    
    @staticmethod
    def load_json(path: Union[str, Path]) -> Any:
        """
        Load JSON from a file.
        
        Args:
            path: File path
        
        Returns:
            JSON data
        """
        with open(path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def save_json(path: Union[str, Path], data: Any, indent: int = 2) -> None:
        """
        Save JSON to a file.
        
        Args:
            path: File path
            data: Data to save
            indent: Indentation level
        """
        Helpers.ensure_dir(Path(path).parent)
        with open(path, 'w') as f:
            json.dump(data, f, indent=indent)
    
    @staticmethod
    def load_yaml(path: Union[str, Path]) -> Any:
        """
        Load YAML from a file.
        
        Args:
            path: File path
        
        Returns:
            YAML data
        """
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    @staticmethod
    def save_yaml(path: Union[str, Path], data: Any) -> None:
        """
        Save YAML to a file.
        
        Args:
            path: File path
            data: Data to save
        """
        Helpers.ensure_dir(Path(path).parent)
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
    
    @staticmethod
    def load_pickle(path: Union[str, Path]) -> Any:
        """
        Load pickle from a file.
        
        Args:
            path: File path
        
        Returns:
            Pickled data
        """
        with open(path, 'rb') as f:
            return pickle.load(f)
    
    @staticmethod
    def save_pickle(path: Union[str, Path], data: Any) -> None:
        """
        Save pickle to a file.
        
        Args:
            path: File path
            data: Data to save
        """
        Helpers.ensure_dir(Path(path).parent)
        with open(path, 'wb') as f:
            pickle.dump(data, f)
    
    @staticmethod
    def get_file_hash(path: Union[str, Path], algorithm: str = 'sha256') -> str:
        """
        Get hash of a file.
        
        Args:
            path: File path
            algorithm: Hash algorithm
        
        Returns:
            File hash
        """
        hash_func = hashlib.new(algorithm)
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    @staticmethod
    def get_text_hash(text: str, algorithm: str = 'sha256') -> str:
        """
        Get hash of a string.
        
        Args:
            text: Text to hash
            algorithm: Hash algorithm
        
        Returns:
            Text hash
        """
        hash_func = hashlib.new(algorithm)
        hash_func.update(text.encode())
        return hash_func.hexdigest()
    
    @staticmethod
    def get_data_hash(data: Any, algorithm: str = 'sha256') -> str:
        """
        Get hash of any data.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm
        
        Returns:
            Data hash
        """
        return Helpers.get_text_hash(json.dumps(data, sort_keys=True), algorithm)
    
    @staticmethod
    def get_file_size(path: Union[str, Path]) -> int:
        """
        Get file size in bytes.
        
        Args:
            path: File path
        
        Returns:
            File size in bytes
        """
        return Path(path).stat().st_size
    
    @staticmethod
    def get_file_age(path: Union[str, Path]) -> float:
        """
        Get file age in seconds.
        
        Args:
            path: File path
        
        Returns:
            File age in seconds
        """
        return time.time() - Path(path).stat().st_mtime
    
    @staticmethod
    def is_file_older_than(path: Union[str, Path], seconds: float) -> bool:
        """
        Check if a file is older than a given number of seconds.
        
        Args:
            path: File path
            seconds: Age threshold in seconds
        
        Returns:
            True if older, False otherwise
        """
        return Helpers.get_file_age(path) > seconds
    
    @staticmethod
    def find_files(pattern: str, directory: Union[str, Path] = '.', recursive: bool = True) -> List[Path]:
        """
        Find files matching a pattern.
        
        Args:
            pattern: File pattern (glob)
            directory: Directory to search
            recursive: Search recursively
        
        Returns:
            List of matching file paths
        """
        directory = Path(directory)
        if recursive:
            return list(directory.glob(f'**/{pattern}'))
        return list(directory.glob(pattern))
    
    @staticmethod
    def find_files_by_extension(extension: str, directory: Union[str, Path] = '.', recursive: bool = True) -> List[Path]:
        """
        Find files by extension.
        
        Args:
            extension: File extension (e.g., '.txt')
            directory: Directory to search
            recursive: Search recursively
        
        Returns:
            List of matching file paths
        """
        return Helpers.find_files(f'*{extension}', directory, recursive)
    
    @staticmethod
    def get_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
        """
        Find an available port.
        
        Args:
            start_port: Starting port
            max_attempts: Maximum attempts
        
        Returns:
            Available port
        
        Raises:
            RuntimeError: If no port is available
        """
        import socket
        for port in range(start_port, start_port + max_attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('', port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f"No available ports found starting from {start_port}")
    
    @staticmethod
    def get_current_time() -> datetime:
        """Get current UTC time."""
        return datetime.utcnow()
    
    @staticmethod
    def get_current_timestamp() -> int:
        """Get current Unix timestamp."""
        return int(time.time())
    
    @staticmethod
    def format_datetime(dt: datetime, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
        """
        Format datetime as string.
        
        Args:
            dt: Datetime object
            fmt: Format string
        
        Returns:
            Formatted datetime string
        """
        return dt.strftime(fmt)
    
    @staticmethod
    def parse_datetime(text: str, fmt: str = '%Y-%m-%d %H:%M:%S') -> datetime:
        """
        Parse datetime from string.
        
        Args:
            text: Datetime string
            fmt: Format string
        
        Returns:
            Datetime object
        
        Raises:
            ValueError: If parsing fails
        """
        return datetime.strptime(text, fmt)
    
    @staticmethod
    def get_environment() -> str:
        """Get the current environment."""
        return os.environ.get('ENV', 'development')
    
    @staticmethod
    def is_production() -> bool:
        """Check if running in production."""
        return Helpers.get_environment().lower() == 'production'
    
    @staticmethod
    def is_development() -> bool:
        """Check if running in development."""
        return Helpers.get_environment().lower() == 'development'
    
    @staticmethod
    def is_debug() -> bool:
        """Check if debug mode is enabled."""
        return os.environ.get('DEBUG', 'false').lower() == 'true'
    
    @staticmethod
    def get_hostname() -> str:
        """Get the system hostname."""
        return socket.gethostname()
    
    @staticmethod
    def get_pid() -> int:
        """Get the current process ID."""
        return os.getpid()
    
    @staticmethod
    def get_cpu_count() -> int:
        """Get the number of CPU cores."""
        return os.cpu_count() or 1
    
    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """
        Get memory usage in MB.
        
        Returns:
            Dictionary with memory usage statistics
        """
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss_mb': memory_info.rss / (1024 * 1024),
            'vms_mb': memory_info.vms / (1024 * 1024),
            'percent': process.memory_percent()
        }
    
    @staticmethod
    def get_cpu_usage() -> float:
        """
        Get CPU usage percentage.
        
        Returns:
            CPU usage percentage
        """
        import psutil
        return psutil.cpu_percent(interval=1)
    
    @staticmethod
    def get_disk_usage(path: Union[str, Path] = '/') -> Dict[str, float]:
        """
        Get disk usage statistics.
        
        Args:
            path: Path to check
        
        Returns:
            Dictionary with disk usage statistics
        """
        import psutil
        usage = psutil.disk_usage(str(path))
        return {
            'total_gb': usage.total / (1024 * 1024 * 1024),
            'used_gb': usage.used / (1024 * 1024 * 1024),
            'free_gb': usage.free / (1024 * 1024 * 1024),
            'percent': usage.percent
        }
    
    @staticmethod
    def get_network_usage() -> Dict[str, float]:
        """
        Get network usage statistics.
        
        Returns:
            Dictionary with network usage statistics
        """
        import psutil
        net_io = psutil.net_io_counters()
        return {
            'bytes_sent_mb': net_io.bytes_sent / (1024 * 1024),
            'bytes_recv_mb': net_io.bytes_recv / (1024 * 1024),
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv
        }
    
    @staticmethod
    def format_bytes(size: int, decimals: int = 2) -> str:
        """
        Format bytes to human-readable string.
        
        Args:
            size: Size in bytes
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        i = 0
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.{decimals}f} {units[i]}"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in seconds to human-readable string.
        
        Args:
            seconds: Duration in seconds
        
        Returns:
            Formatted string
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        elif seconds < 86400:
            return f"{seconds / 3600:.1f}h"
        else:
            return f"{seconds / 86400:.1f}d"
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 2) -> str:
        """
        Format a percentage.
        
        Args:
            value: Value to format
            decimals: Number of decimal places
        
        Returns:
            Formatted string
        """
        return f"{value * 100:.{decimals}f}%"
    
    @staticmethod
    def safe_divide(a: float, b: float, default: float = 0.0) -> float:
        """
        Safely divide two numbers.
        
        Args:
            a: Numerator
            b: Denominator
            default: Default value if division fails
        
        Returns:
            Division result or default
        """
        try:
            return a / b
        except (ZeroDivisionError, TypeError):
            return default
    
    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """
        Safely convert to int.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Int value or default
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> float:
        """
        Safely convert to float.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Float value or default
        """
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_string(value: Any, default: str = '') -> str:
        """
        Safely convert to string.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            String value or default
        """
        try:
            return str(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_dict(value: Any, default: Optional[Dict] = None) -> Dict:
        """
        Safely convert to dict.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            Dict value or default
        """
        if default is None:
            default = {}
        try:
            if isinstance(value, dict):
                return value
            return dict(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_list(value: Any, default: Optional[List] = None) -> List:
        """
        Safely convert to list.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
        
        Returns:
            List value or default
        """
        if default is None:
            default = []
        try:
            if isinstance(value, list):
                return value
            return list(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
        """
        Truncate a string to a maximum length.
        
        Args:
            text: Input string
            max_length: Maximum length
            suffix: Suffix to append if truncated
        
        Returns:
            Truncated string
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def get_class_name(obj: Any) -> str:
        """
        Get the class name of an object.
        
        Args:
            obj: Object
        
        Returns:
            Class name
        """
        return obj.__class__.__name__
    
    @staticmethod
    def get_function_name(func: Callable) -> str:
        """
        Get the name of a function.
        
        Args:
            func: Function
        
        Returns:
            Function name
        """
        return func.__name__
    
    @staticmethod
    def get_module_name(obj: Any) -> str:
        """
        Get the module name of an object.
        
        Args:
            obj: Object
        
        Returns:
            Module name
        """
        return obj.__module__
    
    @staticmethod
    def get_full_name(obj: Any) -> str:
        """
        Get the full name (module + class/function) of an object.
        
        Args:
            obj: Object
        
        Returns:
            Full name
        """
        module = Helpers.get_module_name(obj)
        name = Helpers.get_class_name(obj)
        return f"{module}.{name}"
    
    @staticmethod
    def import_module(module_path: str) -> Any:
        """
        Import a module dynamically.
        
        Args:
            module_path: Module path (e.g., 'trading.bots.swing_bot')
        
        Returns:
            Imported module
        """
        return importlib.import_module(module_path)
    
    @staticmethod
    def import_class(class_path: str) -> Any:
        """
        Import a class dynamically.
        
        Args:
            class_path: Class path (e.g., 'trading.bots.swing_bot.SwingBot')
        
        Returns:
            Imported class
        """
        module_path, class_name = class_path.rsplit('.', 1)
        module = Helpers.import_module(module_path)
        return getattr(module, class_name)
    
    @staticmethod
    def get_signature(func: Callable) -> inspect.Signature:
        """
        Get the signature of a function.
        
        Args:
            func: Function
        
        Returns:
            Function signature
        """
        return inspect.signature(func)
    
    @staticmethod
    def get_parameters(func: Callable) -> List[inspect.Parameter]:
        """
        Get the parameters of a function.
        
        Args:
            func: Function
        
        Returns:
            List of parameters
        """
        return list(Helpers.get_signature(func).parameters.values())
    
    @staticmethod
    def get_parameter_names(func: Callable) -> List[str]:
        """
        Get the parameter names of a function.
        
        Args:
            func: Function
        
        Returns:
            List of parameter names
        """
        return [p.name for p in Helpers.get_parameters(func)]
    
    @staticmethod
    def is_async_function(func: Callable) -> bool:
        """
        Check if a function is asynchronous.
        
        Args:
            func: Function
        
        Returns:
            True if async, False otherwise
        """
        return inspect.iscoroutinefunction(func)
    
    @staticmethod
    def is_class_method(func: Callable) -> bool:
        """
        Check if a function is a class method.
        
        Args:
            func: Function
        
        Returns:
            True if class method, False otherwise
        """
        return inspect.ismethod(func)
    
    @staticmethod
    def is_static_method(func: Callable) -> bool:
        """
        Check if a function is a static method.
        
        Args:
            func: Function
        
        Returns:
            True if static method, False otherwise
        """
        return isinstance(func, staticmethod)
    
    @staticmethod
    def is_property(obj: Any) -> bool:
        """
        Check if an object is a property.
        
        Args:
            obj: Object
        
        Returns:
            True if property, False otherwise
        """
        return isinstance(obj, property)
    
    @staticmethod
    def is_lambda(func: Callable) -> bool:
        """
        Check if a function is a lambda.
        
        Args:
            func: Function
        
        Returns:
            True if lambda, False otherwise
        """
        return func.__name__ == '<lambda>'
    
    @staticmethod
    def is_generator(func: Callable) -> bool:
        """
        Check if a function is a generator.
        
        Args:
            func: Function
        
        Returns:
            True if generator, False otherwise
        """
        return inspect.isgeneratorfunction(func)
    
    @staticmethod
    def get_default_args(func: Callable) -> Dict[str, Any]:
        """
        Get the default arguments of a function.
        
        Args:
            func: Function
        
        Returns:
            Dictionary of default arguments
        """
        signature = inspect.signature(func)
        return {
            k: v.default
            for k, v in signature.parameters.items()
            if v.default is not inspect.Parameter.empty
        }
    
    @staticmethod
    def get_annotations(func: Callable) -> Dict[str, Any]:
        """
        Get the annotations of a function.
        
        Args:
            func: Function
        
        Returns:
            Dictionary of annotations
        """
        return func.__annotations__
    
    @staticmethod
    def get_docstring(obj: Any) -> Optional[str]:
        """
        Get the docstring of an object.
        
        Args:
            obj: Object
        
        Returns:
            Docstring or None
        """
        return inspect.getdoc(obj)
    
    @staticmethod
    def get_source_code(obj: Any) -> Optional[str]:
        """
        Get the source code of an object.
        
        Args:
            obj: Object
        
        Returns:
            Source code or None
        """
        try:
            return inspect.getsource(obj)
        except (TypeError, OSError):
            return None
    
    @staticmethod
    def get_lineno(obj: Any) -> Optional[int]:
        """
        Get the line number of an object.
        
        Args:
            obj: Object
        
        Returns:
            Line number or None
        """
        try:
            return inspect.getsourcelines(obj)[1]
        except (TypeError, OSError):
            return None
    
    @staticmethod
    def get_file_path(obj: Any) -> Optional[str]:
        """
        Get the file path of an object.
        
        Args:
            obj: Object
        
        Returns:
            File path or None
        """
        try:
            return inspect.getfile(obj)
        except (TypeError, OSError):
            return None
    
    @staticmethod
    def get_stack() -> List[inspect.FrameInfo]:
        """
        Get the current stack.
        
        Returns:
            List of frame information
        """
        return inspect.stack()
    
    @staticmethod
    def get_caller_frame(depth: int = 1) -> Optional[inspect.FrameInfo]:
        """
        Get the caller's frame.
        
        Args:
            depth: Stack depth to go back
        
        Returns:
            Frame information or None
        """
        stack = Helpers.get_stack()
        if len(stack) > depth:
            return stack[depth]
        return None
    
    @staticmethod
    def get_caller_function(depth: int = 1) -> Optional[str]:
        """
        Get the caller's function name.
        
        Args:
            depth: Stack depth to go back
        
        Returns:
            Function name or None
        """
        frame = Helpers.get_caller_frame(depth + 1)
        if frame:
            return frame.function
        return None
    
    @staticmethod
    def get_caller_file(depth: int = 1) -> Optional[str]:
        """
        Get the caller's file name.
        
        Args:
            depth: Stack depth to go back
        
        Returns:
            File name or None
        """
        frame = Helpers.get_caller_frame(depth + 1)
        if frame:
            return frame.filename
        return None
    
    @staticmethod
    def get_caller_line(depth: int = 1) -> Optional[int]:
        """
        Get the caller's line number.
        
        Args:
            depth: Stack depth to go back
        
        Returns:
            Line number or None
        """
        frame = Helpers.get_caller_frame(depth + 1)
        if frame:
            return frame.lineno
        return None


# Function aliases for easier import
ensure_dir = Helpers.ensure_dir
ensure_file = Helpers.ensure_file
load_json = Helpers.load_json
save_json = Helpers.save_json
load_yaml = Helpers.load_yaml
save_yaml = Helpers.save_yaml
load_pickle = Helpers.load_pickle
save_pickle = Helpers.save_pickle
get_file_hash = Helpers.get_file_hash
get_text_hash = Helpers.get_text_hash
get_data_hash = Helpers.get_data_hash
get_file_size = Helpers.get_file_size
get_file_age = Helpers.get_file_age
is_file_older_than = Helpers.is_file_older_than
find_files = Helpers.find_files
find_files_by_extension = Helpers.find_files_by_extension
get_available_port = Helpers.get_available_port
get_current_time = Helpers.get_current_time
get_current_timestamp = Helpers.get_current_timestamp
format_datetime = Helpers.format_datetime
parse_datetime = Helpers.parse_datetime
get_environment = Helpers.get_environment
is_production = Helpers.is_production
is_development = Helpers.is_development
is_debug = Helpers.is_debug
get_hostname = Helpers.get_hostname
get_pid = Helpers.get_pid
get_cpu_count = Helpers.get_cpu_count
get_memory_usage = Helpers.get_memory_usage
get_cpu_usage = Helpers.get_cpu_usage
get_disk_usage = Helpers.get_disk_usage
get_network_usage = Helpers.get_network_usage
format_bytes = Helpers.format_bytes
format_duration = Helpers.format_duration
format_percentage = Helpers.format_percentage
safe_divide = Helpers.safe_divide
safe_int = Helpers.safe_int
safe_float = Helpers.safe_float
safe_string = Helpers.safe_string
safe_dict = Helpers.safe_dict
safe_list = Helpers.safe_list
truncate_string = Helpers.truncate_string
get_class_name = Helpers.get_class_name
get_function_name = Helpers.get_function_name
get_module_name = Helpers.get_module_name
get_full_name = Helpers.get_full_name
import_module = Helpers.import_module
import_class = Helpers.import_class
get_signature = Helpers.get_signature
get_parameters = Helpers.get_parameters
get_parameter_names = Helpers.get_parameter_names
is_async_function = Helpers.is_async_function
is_class_method = Helpers.is_class_method
is_static_method = Helpers.is_static_method
is_property = Helpers.is_property
is_lambda = Helpers.is_lambda
is_generator = Helpers.is_generator
get_default_args = Helpers.get_default_args
get_annotations = Helpers.get_annotations
get_docstring = Helpers.get_docstring
get_source_code = Helpers.get_source_code
get_lineno = Helpers.get_lineno
get_file_path = Helpers.get_file_path
get_stack = Helpers.get_stack
get_caller_frame = Helpers.get_caller_frame
get_caller_function = Helpers.get_caller_function
get_caller_file = Helpers.get_caller_file
get_caller_line = Helpers.get_caller_line


__all__ = [
    # Class
    'Helpers',
    
    # Function aliases
    'ensure_dir',
    'ensure_file',
    'load_json',
    'save_json',
    'load_yaml',
    'save_yaml',
    'load_pickle',
    'save_pickle',
    'get_file_hash',
    'get_text_hash',
    'get_data_hash',
    'get_file_size',
    'get_file_age',
    'is_file_older_than',
    'find_files',
    'find_files_by_extension',
    'get_available_port',
    'get_current_time',
    'get_current_timestamp',
    'format_datetime',
    'parse_datetime',
    'get_environment',
    'is_production',
    'is_development',
    'is_debug',
    'get_hostname',
    'get_pid',
    'get_cpu_count',
    'get_memory_usage',
    'get_cpu_usage',
    'get_disk_usage',
    'get_network_usage',
    'format_bytes',
    'format_duration',
    'format_percentage',
    'safe_divide',
    'safe_int',
    'safe_float',
    'safe_string',
    'safe_dict',
    'safe_list',
    'truncate_string',
    'get_class_name',
    'get_function_name',
    'get_module_name',
    'get_full_name',
    'import_module',
    'import_class',
    'get_signature',
    'get_parameters',
    'get_parameter_names',
    'is_async_function',
    'is_class_method',
    'is_static_method',
    'is_property',
    'is_lambda',
    'is_generator',
    'get_default_args',
    'get_annotations',
    'get_docstring',
    'get_source_code',
    'get_lineno',
    'get_file_path',
    'get_stack',
    'get_caller_frame',
    'get_caller_function',
    'get_caller_file',
    'get_caller_line',
]

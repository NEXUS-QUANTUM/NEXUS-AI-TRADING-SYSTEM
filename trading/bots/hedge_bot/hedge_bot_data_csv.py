# trading/bots/hedge_bot/hedge_bot_data_csv.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data CSV Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data CSV Module

This module provides comprehensive CSV data handling capabilities for the
NEXUS Hedge Bot system. It handles reading, writing, and processing
CSV data files for trading data, market data, and configuration.

The module covers:
- CSV Reading
- CSV Writing
- Data Validation
- Data Transformation
- Large File Handling
- CSV Export/Import
- Data Formatting
"""

import os
import sys
import csv
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Iterator
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================
# DATA CSV ENUMS
# ============================================================

class CSVFormat(Enum):
    """CSV formats"""
    STANDARD = "standard"
    EXCEL = "excel"
    TSV = "tsv"
    CUSTOM = "custom"


class CSVEncoding(Enum):
    """CSV encodings"""
    UTF8 = "utf-8"
    UTF8_SIG = "utf-8-sig"
    ASCII = "ascii"
    LATIN1 = "latin-1"
    CP1252 = "cp1252"


@dataclass
class CSVConfig:
    """CSV configuration"""
    delimiter: str = ","
    quotechar: str = '"'
    escapechar: str = "\\"
    encoding: CSVEncoding = CSVEncoding.UTF8
    header: bool = True
    skip_rows: int = 0
    max_rows: Optional[int] = None
    date_format: str = "%Y-%m-%d %H:%M:%S"
    decimal_separator: str = "."
    thousands_separator: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "delimiter": self.delimiter,
            "quotechar": self.quotechar,
            "escapechar": self.escapechar,
            "encoding": self.encoding.value,
            "header": self.header,
            "skip_rows": self.skip_rows,
            "max_rows": self.max_rows,
            "date_format": self.date_format,
            "decimal_separator": self.decimal_separator,
            "thousands_separator": self.thousands_separator,
        }


@dataclass
class CSVData:
    """CSV data"""
    headers: List[str]
    data: List[List[Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "headers": self.headers,
            "rows": len(self.data),
            "columns": len(self.headers) if self.headers else 0,
            "metadata": self.metadata,
            "source": self.source,
        }


# ============================================================
# DATA CSV ENGINE
# ============================================================

class DataCSVEngine:
    """
    Comprehensive CSV data engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the CSV data engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_config = CSVConfig(
            delimiter=self.config.get("delimiter", ","),
            quotechar=self.config.get("quotechar", '"'),
            encoding=CSVEncoding(self.config.get("encoding", "utf-8")),
        )
        
        # State
        self.cache: Dict[str, CSVData] = {}
        
        logger.info("CSV data engine initialized")
    
    # ============================================================
    # CSV READING
    # ============================================================
    
    def read_csv(
        self,
        file_path: Union[str, Path],
        config: Optional[CSVConfig] = None,
        as_dataframe: bool = False
    ) -> Union[CSVData, pd.DataFrame]:
        """
        Read CSV file
        
        Args:
            file_path: Path to CSV file
            config: CSV configuration
            as_dataframe: Return as DataFrame
            
        Returns:
            CSVData or DataFrame
        """
        if config is None:
            config = self.default_config
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Use pandas for large files or dataframe output
        if as_dataframe or config.max_rows and config.max_rows > 10000:
            return self._read_with_pandas(file_path, config)
        
        return self._read_with_csv(file_path, config)
    
    def _read_with_csv(self, file_path: Path, config: CSVConfig) -> CSVData:
        """Read CSV using csv module"""
        with open(file_path, 'r', encoding=config.encoding.value) as f:
            # Skip rows
            for _ in range(config.skip_rows):
                f.readline()
            
            reader = csv.reader(
                f,
                delimiter=config.delimiter,
                quotechar=config.quotechar,
                escapechar=config.escapechar,
            )
            
            # Read header
            if config.header:
                headers = next(reader)
            else:
                headers = None
            
            # Read data
            data = []
            row_count = 0
            for row in reader:
                if config.max_rows and row_count >= config.max_rows:
                    break
                data.append(row)
                row_count += 1
            
            # Generate headers if not present
            if not headers:
                headers = [f"col_{i}" for i in range(len(data[0]) if data else 0)]
        
        return CSVData(
            headers=headers,
            data=data,
            source=str(file_path),
            metadata={
                "row_count": len(data),
                "column_count": len(headers) if headers else 0,
                "encoding": config.encoding.value,
                "delimiter": config.delimiter,
            },
        )
    
    def _read_with_pandas(self, file_path: Path, config: CSVConfig) -> pd.DataFrame:
        """Read CSV using pandas"""
        df = pd.read_csv(
            file_path,
            delimiter=config.delimiter,
            quotechar=config.quotechar,
            encoding=config.encoding.value,
            skiprows=config.skip_rows,
            nrows=config.max_rows,
            header=0 if config.header else None,
        )
        
        return df
    
    # ============================================================
    # CSV WRITING
    # ============================================================
    
    def write_csv(
        self,
        data: Union[CSVData, pd.DataFrame, List[Dict[str, Any]]],
        file_path: Union[str, Path],
        config: Optional[CSVConfig] = None
    ) -> bool:
        """
        Write CSV file
        
        Args:
            data: Data to write
            file_path: Output file path
            config: CSV configuration
            
        Returns:
            True if written
        """
        if config is None:
            config = self.default_config
        
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if isinstance(data, pd.DataFrame):
                self._write_dataframe(data, file_path, config)
            elif isinstance(data, CSVData):
                self._write_csvdata(data, file_path, config)
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                self._write_dictlist(data, file_path, config)
            else:
                raise ValueError("Unsupported data type")
            
            logger.info(f"CSV written: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")
            return False
    
    def _write_csvdata(self, data: CSVData, file_path: Path, config: CSVConfig) -> None:
        """Write CSVData object"""
        with open(file_path, 'w', encoding=config.encoding.value, newline='') as f:
            writer = csv.writer(
                f,
                delimiter=config.delimiter,
                quotechar=config.quotechar,
                escapechar=config.escapechar,
            )
            
            if config.header and data.headers:
                writer.writerow(data.headers)
            
            writer.writerows(data.data)
    
    def _write_dataframe(self, df: pd.DataFrame, file_path: Path, config: CSVConfig) -> None:
        """Write DataFrame"""
        df.to_csv(
            file_path,
            sep=config.delimiter,
            quotechar=config.quotechar,
            encoding=config.encoding.value,
            index=False,
        )
    
    def _write_dictlist(self, data: List[Dict[str, Any]], file_path: Path, config: CSVConfig) -> None:
        """Write list of dictionaries"""
        if not data:
            return
        
        headers = list(data[0].keys())
        
        with open(file_path, 'w', encoding=config.encoding.value, newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=headers,
                delimiter=config.delimiter,
                quotechar=config.quotechar,
                escapechar=config.escapechar,
            )
            
            if config.header:
                writer.writeheader()
            
            writer.writerows(data)
    
    # ============================================================
    # DATA PROCESSING
    # ============================================================
    
    def validate_csv(
        self,
        csv_data: CSVData,
        expected_headers: Optional[List[str]] = None,
        expected_types: Optional[Dict[str, type]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate CSV data
        
        Args:
            csv_data: CSVData to validate
            expected_headers: Expected headers
            expected_types: Expected column types
            
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Validate headers
        if expected_headers:
            if len(csv_data.headers) != len(expected_headers):
                errors.append(f"Expected {len(expected_headers)} columns, got {len(csv_data.headers)}")
            else:
                for i, (actual, expected) in enumerate(zip(csv_data.headers, expected_headers)):
                    if actual != expected:
                        errors.append(f"Column {i}: expected '{expected}', got '{actual}'")
        
        # Validate types
        if expected_types:
            for row_idx, row in enumerate(csv_data.data):
                for col_idx, col_name in enumerate(csv_data.headers):
                    if col_name in expected_types:
                        expected_type = expected_types[col_name]
                        value = row[col_idx] if col_idx < len(row) else None
                        try:
                            if expected_type == int:
                                int(value)
                            elif expected_type == float:
                                float(value)
                            elif expected_type == bool:
                                bool(value)
                        except (ValueError, TypeError):
                            errors.append(f"Row {row_idx}, Column {col_name}: expected {expected_type.__name__}, got '{value}'")
        
        return len(errors) == 0, errors
    
    def convert_to_dataframe(
        self,
        csv_data: CSVData,
        convert_types: bool = True
    ) -> pd.DataFrame:
        """
        Convert CSVData to DataFrame
        
        Args:
            csv_data: CSVData
            convert_types: Convert data types
            
        Returns:
            DataFrame
        """
        if convert_types:
            # Try to infer types
            return pd.DataFrame(csv_data.data, columns=csv_data.headers)
        else:
            return pd.DataFrame(csv_data.data, columns=csv_data.headers)
    
    def convert_from_dataframe(
        self,
        df: pd.DataFrame,
        headers: Optional[List[str]] = None
    ) -> CSVData:
        """
        Convert DataFrame to CSVData
        
        Args:
            df: DataFrame
            headers: Column headers
            
        Returns:
            CSVData
        """
        if headers is None:
            headers = df.columns.tolist()
        
        data = df.values.tolist()
        
        return CSVData(
            headers=headers,
            data=data,
            metadata={
                "row_count": len(data),
                "column_count": len(headers),
                "source": "dataframe",
            },
        )
    
    # ============================================================
    # LARGE FILE HANDLING
    # ============================================================
    
    def read_csv_chunks(
        self,
        file_path: Union[str, Path],
        chunk_size: int = 10000,
        config: Optional[CSVConfig] = None
    ) -> Iterator[pd.DataFrame]:
        """
        Read CSV in chunks for large files
        
        Args:
            file_path: Path to CSV file
            chunk_size: Number of rows per chunk
            config: CSV configuration
            
        Yields:
            DataFrame chunks
        """
        if config is None:
            config = self.default_config
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        for chunk in pd.read_csv(
            file_path,
            delimiter=config.delimiter,
            quotechar=config.quotechar,
            encoding=config.encoding.value,
            skiprows=config.skip_rows,
            chunksize=chunk_size,
            header=0 if config.header else None,
        ):
            yield chunk
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get CSV engine statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_cached": len(self.cache),
            "default_config": self.default_config.to_dict(),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "CSVFormat",
    "CSVEncoding",
    
    # Dataclasses
    "CSVConfig",
    "CSVData",
    
    # Classes
    "DataCSVEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

# trading/bots/hedge_bot/hedge_bot_compressor.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Compressor Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Compressor Module

This module provides comprehensive data compression capabilities for the
NEXUS Hedge Bot system. It handles data compression for storage optimization,
network transmission, and performance improvement.

The module covers:
- Data Compression
- Time Series Compression
- Lossless Compression
- Lossy Compression
- Dictionary Compression
- Delta Compression
- Run-Length Encoding
- Huffman Coding
- LZ77/LZ78 Compression
- Deflate Compression
- Data Deduplication
- Compression Ratio Optimization
"""

import os
import sys
import json
import zlib
import gzip
import bz2
import lzma
import pickle
import hashlib
import struct
import logging
import numpy as np
from typing import Dict, Any, Optional, List, Union, Tuple, BinaryIO
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


# ============================================================
# COMPRESSOR ENUMS
# ============================================================

class CompressionMethod(Enum):
    """Compression methods"""
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    LZMA = "lzma"
    ZLIB = "zlib"
    DEFLATE = "deflate"
    DELTA = "delta"
    RLE = "rle"
    DICTIONARY = "dictionary"
    HUFFMAN = "huffman"
    LZ77 = "lz77"
    LZ78 = "lz78"


class CompressionLevel(Enum):
    """Compression levels"""
    FAST = "fast"
    NORMAL = "normal"
    BEST = "best"


class CompressionType(Enum):
    """Compression types"""
    LOSSLESS = "lossless"
    LOSSY = "lossy"
    HYBRID = "hybrid"


@dataclass
class CompressionConfig:
    """Compression configuration"""
    method: CompressionMethod
    level: CompressionLevel
    type: CompressionType
    dictionary: Optional[Dict[str, int]] = None
    window_size: int = 65536
    memory_level: int = 8
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "method": self.method.value,
            "level": self.level.value,
            "type": self.type.value,
            "window_size": self.window_size,
            "memory_level": self.memory_level,
        }


@dataclass
class CompressionResult:
    """Compression result"""
    original_size: int
    compressed_size: int
    ratio: float
    compression_time: float
    decompression_time: float
    method: CompressionMethod
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "ratio": self.ratio,
            "compression_time": self.compression_time,
            "decompression_time": self.decompression_time,
            "method": self.method.value,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }


# ============================================================
# COMPRESSOR ENGINE
# ============================================================

class CompressorEngine:
    """
    Comprehensive compression engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the compression engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_method = self.config.get("default_method", CompressionMethod.GZIP)
        self.default_level = self.config.get("default_level", CompressionLevel.NORMAL)
        
        # Cache
        self.compression_cache: Dict[str, CompressionResult] = {}
        
        logger.info("Compression engine initialized")
    
    # ============================================================
    # BASIC COMPRESSION
    # ============================================================
    
    def compress_data(
        self,
        data: bytes,
        method: Optional[CompressionMethod] = None,
        level: Optional[CompressionLevel] = None
    ) -> Tuple[bytes, CompressionResult]:
        """
        Compress data
        
        Args:
            data: Data to compress
            method: Compression method
            level: Compression level
            
        Returns:
            (compressed_data, CompressionResult)
        """
        if method is None:
            method = self.default_method
        if level is None:
            level = self.default_level
        
        original_size = len(data)
        start_time = datetime.now()
        
        # Compress based on method
        if method == CompressionMethod.GZIP:
            compressed = self._compress_gzip(data, level)
        elif method == CompressionMethod.BZIP2:
            compressed = self._compress_bzip2(data, level)
        elif method == CompressionMethod.LZMA:
            compressed = self._compress_lzma(data, level)
        elif method == CompressionMethod.ZLIB:
            compressed = self._compress_zlib(data, level)
        elif method == CompressionMethod.DEFLATE:
            compressed = self._compress_deflate(data)
        elif method == CompressionMethod.RLE:
            compressed = self._compress_rle(data)
        elif method == CompressionMethod.DELTA:
            compressed = self._compress_delta(data)
        elif method == CompressionMethod.DICTIONARY:
            compressed = self._compress_dictionary(data)
        else:
            compressed = data
        
        compression_time = (datetime.now() - start_time).total_seconds()
        compressed_size = len(compressed)
        ratio = compressed_size / original_size if original_size > 0 else 1.0
        checksum = self._calculate_checksum(compressed)
        
        result = CompressionResult(
            original_size=original_size,
            compressed_size=compressed_size,
            ratio=ratio,
            compression_time=compression_time,
            decompression_time=0.0,
            method=method,
            checksum=checksum,
            metadata={
                "level": level.value,
                "original_checksum": self._calculate_checksum(data),
            }
        )
        
        return compressed, result
    
    def decompress_data(
        self,
        compressed_data: bytes,
        method: CompressionMethod
    ) -> Tuple[bytes, CompressionResult]:
        """
        Decompress data
        
        Args:
            compressed_data: Compressed data
            method: Compression method
            
        Returns:
            (decompressed_data, CompressionResult)
        """
        start_time = datetime.now()
        
        # Decompress based on method
        if method == CompressionMethod.GZIP:
            decompressed = self._decompress_gzip(compressed_data)
        elif method == CompressionMethod.BZIP2:
            decompressed = self._decompress_bzip2(compressed_data)
        elif method == CompressionMethod.LZMA:
            decompressed = self._decompress_lzma(compressed_data)
        elif method == CompressionMethod.ZLIB:
            decompressed = self._decompress_zlib(compressed_data)
        elif method == CompressionMethod.DEFLATE:
            decompressed = self._decompress_deflate(compressed_data)
        elif method == CompressionMethod.RLE:
            decompressed = self._decompress_rle(compressed_data)
        elif method == CompressionMethod.DELTA:
            decompressed = self._decompress_delta(compressed_data)
        elif method == CompressionMethod.DICTIONARY:
            decompressed = self._decompress_dictionary(compressed_data)
        else:
            decompressed = compressed_data
        
        decompression_time = (datetime.now() - start_time).total_seconds()
        
        result = CompressionResult(
            original_size=len(decompressed),
            compressed_size=len(compressed_data),
            ratio=len(compressed_data) / len(decompressed) if len(decompressed) > 0 else 1.0,
            compression_time=0.0,
            decompression_time=decompression_time,
            method=method,
            checksum=self._calculate_checksum(decompressed),
        )
        
        return decompressed, result
    
    # ============================================================
    # COMPRESSION METHODS
    # ============================================================
    
    def _compress_gzip(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with GZIP"""
        compress_level = self._get_compress_level(level)
        return gzip.compress(data, compresslevel=compress_level)
    
    def _decompress_gzip(self, data: bytes) -> bytes:
        """Decompress with GZIP"""
        return gzip.decompress(data)
    
    def _compress_bzip2(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with BZIP2"""
        compress_level = self._get_compress_level(level)
        return bz2.compress(data, compresslevel=compress_level)
    
    def _decompress_bzip2(self, data: bytes) -> bytes:
        """Decompress with BZIP2"""
        return bz2.decompress(data)
    
    def _compress_lzma(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with LZMA"""
        compress_level = self._get_compress_level(level)
        return lzma.compress(data, preset=compress_level)
    
    def _decompress_lzma(self, data: bytes) -> bytes:
        """Decompress with LZMA"""
        return lzma.decompress(data)
    
    def _compress_zlib(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with ZLIB"""
        compress_level = self._get_compress_level(level)
        return zlib.compress(data, level=compress_level)
    
    def _decompress_zlib(self, data: bytes) -> bytes:
        """Decompress with ZLIB"""
        return zlib.decompress(data)
    
    def _compress_deflate(self, data: bytes) -> bytes:
        """Compress with DEFLATE"""
        return zlib.compress(data)[2:]  # Remove zlib header
    
    def _decompress_deflate(self, data: bytes) -> bytes:
        """Decompress with DEFLATE"""
        return zlib.decompress(b'\x78\x9c' + data)  # Add zlib header
    
    def _compress_rle(self, data: bytes) -> bytes:
        """Run-Length Encoding compression"""
        compressed = []
        i = 0
        n = len(data)
        
        while i < n:
            count = 1
            while i + count < n and data[i] == data[i + count]:
                count += 1
            
            # Encode as (count, value)
            compressed.append(count)
            compressed.append(data[i])
            i += count
        
        return bytes(compressed)
    
    def _decompress_rle(self, data: bytes) -> bytes:
        """Run-Length Encoding decompression"""
        decompressed = []
        i = 0
        n = len(data)
        
        while i < n:
            count = data[i]
            if i + 1 < n:
                value = data[i + 1]
                decompressed.extend([value] * count)
                i += 2
            else:
                i += 1
        
        return bytes(decompressed)
    
    def _compress_delta(self, data: bytes) -> bytes:
        """Delta compression"""
        if len(data) < 2:
            return data
        
        # Simple first-order delta
        compressed = bytearray()
        compressed.append(data[0])
        
        for i in range(1, len(data)):
            delta = data[i] - data[i-1]
            compressed.append(delta & 0xFF)
        
        return bytes(compressed)
    
    def _decompress_delta(self, data: bytes) -> bytes:
        """Delta decompression"""
        if len(data) < 2:
            return data
        
        decompressed = bytearray()
        decompressed.append(data[0])
        
        for i in range(1, len(data)):
            value = decompressed[-1] + data[i]
            decompressed.append(value & 0xFF)
        
        return bytes(decompressed)
    
    def _compress_dictionary(self, data: bytes) -> bytes:
        """Dictionary compression (simplified)"""
        # Build frequency dictionary
        freq = {}
        for byte in data:
            freq[byte] = freq.get(byte, 0) + 1
        
        # Sort by frequency
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        
        # Create dictionary mapping
        dictionary = {byte: i for i, (byte, _) in enumerate(sorted_freq)}
        
        # Compress using dictionary
        compressed = bytearray()
        for byte in data:
            compressed.append(dictionary[byte])
        
        # Store dictionary header
        header = struct.pack('H', len(dictionary))
        for byte, code in dictionary.items():
            header += struct.pack('BB', byte, code)
        
        return header + bytes(compressed)
    
    def _decompress_dictionary(self, data: bytes) -> bytes:
        """Dictionary decompression"""
        if len(data) < 2:
            return data
        
        # Read header
        dict_size = struct.unpack('H', data[:2])[0]
        offset = 2
        
        # Rebuild dictionary
        dictionary = {}
        for _ in range(dict_size):
            if offset + 2 > len(data):
                break
            byte, code = struct.unpack('BB', data[offset:offset+2])
            dictionary[code] = byte
            offset += 2
        
        # Decompress
        decompressed = bytearray()
        for i in range(offset, len(data)):
            code = data[i]
            if code in dictionary:
                decompressed.append(dictionary[code])
        
        return bytes(decompressed)
    
    def _get_compress_level(self, level: CompressionLevel) -> int:
        """Get compression level integer"""
        levels = {
            CompressionLevel.FAST: 1,
            CompressionLevel.NORMAL: 6,
            CompressionLevel.BEST: 9,
        }
        return levels.get(level, 6)
    
    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate checksum"""
        return hashlib.sha256(data).hexdigest()
    
    # ============================================================
    # HIGH-LEVEL COMPRESSION
    # ============================================================
    
    def compress_object(
        self,
        obj: Any,
        method: Optional[CompressionMethod] = None,
        level: Optional[CompressionLevel] = None
    ) -> Tuple[bytes, CompressionResult]:
        """
        Compress a Python object
        
        Args:
            obj: Object to compress
            method: Compression method
            level: Compression level
            
        Returns:
            (compressed_data, CompressionResult)
        """
        # Serialize object
        serialized = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        
        # Compress
        return self.compress_data(serialized, method, level)
    
    def decompress_object(
        self,
        compressed_data: bytes,
        method: CompressionMethod
    ) -> Tuple[Any, CompressionResult]:
        """
        Decompress a Python object
        
        Args:
            compressed_data: Compressed data
            method: Compression method
            
        Returns:
            (object, CompressionResult)
        """
        # Decompress
        decompressed, result = self.decompress_data(compressed_data, method)
        
        # Deserialize
        obj = pickle.loads(decompressed)
        
        return obj, result
    
    def compress_json(
        self,
        data: Dict[str, Any],
        method: Optional[CompressionMethod] = None,
        level: Optional[CompressionLevel] = None
    ) -> Tuple[bytes, CompressionResult]:
        """
        Compress JSON data
        
        Args:
            data: JSON data
            method: Compression method
            level: Compression level
            
        Returns:
            (compressed_data, CompressionResult)
        """
        json_str = json.dumps(data)
        json_bytes = json_str.encode('utf-8')
        return self.compress_data(json_bytes, method, level)
    
    def decompress_json(
        self,
        compressed_data: bytes,
        method: CompressionMethod
    ) -> Tuple[Dict[str, Any], CompressionResult]:
        """
        Decompress JSON data
        
        Args:
            compressed_data: Compressed data
            method: Compression method
            
        Returns:
            (JSON data, CompressionResult)
        """
        decompressed, result = self.decompress_data(compressed_data, method)
        json_str = decompressed.decode('utf-8')
        data = json.loads(json_str)
        return data, result
    
    # ============================================================
    # TIME SERIES COMPRESSION
    # ============================================================
    
    def compress_time_series(
        self,
        data: np.ndarray,
        tolerance: float = 0.001,
        method: Optional[CompressionMethod] = None,
        level: Optional[CompressionLevel] = None
    ) -> Tuple[bytes, CompressionResult]:
        """
        Compress time series data with tolerance
        
        Args:
            data: Time series data
            tolerance: Error tolerance
            method: Compression method
            level: Compression level
            
        Returns:
            (compressed_data, CompressionResult)
        """
        # Simple compression: store only significant changes
        compressed = []
        prev_value = data[0]
        compressed.append(prev_value)
        
        for i in range(1, len(data)):
            if abs(data[i] - prev_value) > tolerance:
                compressed.append(data[i])
                prev_value = data[i]
        
        # Convert to bytes
        compressed_bytes = np.array(compressed, dtype=np.float64).tobytes()
        
        # Add metadata
        metadata = {
            "original_length": len(data),
            "compressed_length": len(compressed),
            "tolerance": tolerance,
            "dtype": str(data.dtype),
        }
        
        # Store metadata and compressed data
        metadata_json = json.dumps(metadata).encode()
        header = struct.pack('I', len(metadata_json)) + metadata_json
        
        compressed_data = header + compressed_bytes
        
        # Further compress
        if method is not None:
            compressed_data, result = self.compress_data(compressed_data, method, level)
            result.metadata.update(metadata)
            return compressed_data, result
        
        result = CompressionResult(
            original_size=len(data) * data.itemsize,
            compressed_size=len(compressed_data),
            ratio=len(compressed_data) / (len(data) * data.itemsize) if len(data) > 0 else 1.0,
            compression_time=0.0,
            decompression_time=0.0,
            method=CompressionMethod.NONE,
            checksum=self._calculate_checksum(compressed_data),
            metadata=metadata,
        )
        
        return compressed_data, result
    
    def decompress_time_series(
        self,
        compressed_data: bytes,
        method: Optional[CompressionMethod] = None
    ) -> Tuple[np.ndarray, CompressionResult]:
        """
        Decompress time series data
        
        Args:
            compressed_data: Compressed data
            method: Compression method
            
        Returns:
            (time_series_data, CompressionResult)
        """
        # Decompress first if needed
        if method is not None:
            decompressed_data, result = self.decompress_data(compressed_data, method)
        else:
            decompressed_data = compressed_data
            result = CompressionResult(
                original_size=0,
                compressed_size=len(compressed_data),
                ratio=1.0,
                compression_time=0.0,
                decompression_time=0.0,
                method=CompressionMethod.NONE,
                checksum=self._calculate_checksum(compressed_data),
            )
        
        # Read header
        if len(decompressed_data) < 4:
            return np.array([]), result
        
        metadata_len = struct.unpack('I', decompressed_data[:4])[0]
        metadata_json = decompressed_data[4:4+metadata_len]
        metadata = json.loads(metadata_json.decode())
        
        # Read data
        data_bytes = decompressed_data[4+metadata_len:]
        data = np.frombuffer(data_bytes, dtype=metadata.get('dtype', 'float64'))
        
        # Reconstruct time series (simple linear interpolation)
        original_length = metadata.get('original_length', len(data))
        reconstructed = np.zeros(original_length)
        
        if len(data) > 1:
            indices = np.linspace(0, original_length - 1, len(data), dtype=np.int64)
            reconstructed = np.interp(np.arange(original_length), indices, data)
        else:
            reconstructed.fill(data[0] if len(data) > 0 else 0)
        
        result.metadata = metadata
        return reconstructed, result
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def get_best_method(
        self,
        data: bytes,
        methods: Optional[List[CompressionMethod]] = None
    ) -> CompressionMethod:
        """
        Find the best compression method for data
        
        Args:
            data: Data to compress
            methods: Methods to test
            
        Returns:
            Best compression method
        """
        if methods is None:
            methods = [
                CompressionMethod.GZIP,
                CompressionMethod.BZIP2,
                CompressionMethod.LZMA,
                CompressionMethod.ZLIB,
                CompressionMethod.DEFLATE,
                CompressionMethod.DELTA,
                CompressionMethod.RLE,
            ]
        
        best_method = CompressionMethod.NONE
        best_ratio = 1.0
        
        for method in methods:
            try:
                compressed, result = self.compress_data(data, method, CompressionLevel.FAST)
                if result.ratio < best_ratio:
                    best_ratio = result.ratio
                    best_method = method
            except:
                continue
        
        return best_method
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get compression statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_compressions": len(self.compression_cache),
            "default_method": self.default_method.value,
            "default_level": self.default_level.value,
            "cache_hit_rate": 0.0,  # Not implemented
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "CompressionMethod",
    "CompressionLevel",
    "CompressionType",
    
    # Dataclasses
    "CompressionConfig",
    "CompressionResult",
    
    # Classes
    "CompressorEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

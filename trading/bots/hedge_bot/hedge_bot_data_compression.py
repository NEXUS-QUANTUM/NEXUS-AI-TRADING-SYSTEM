# trading/bots/hedge_bot/hedge_bot_data_compression.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Compression Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Compression Module

This module provides comprehensive data compression and decompression
capabilities for the NEXUS Hedge Bot system. It optimizes data storage
and transmission by reducing data size.

The module covers:
- Data Compression Algorithms
- Lossless Compression
- Time-Series Compression
- Dictionary Compression
- Delta Compression
- Run-Length Encoding
- Bit Packing
- Decompression
- Compression Ratio Optimization
"""

import os
import sys
import json
import logging
import zlib
import gzip
import bz2
import lzma
import pickle
import struct
import numpy as np
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


# ============================================================
# DATA COMPRESSION ENUMS
# ============================================================

class CompressionAlgorithm(Enum):
    """Compression algorithms"""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    LZMA = "lzma"
    DELTA = "delta"
    RLE = "rle"
    DICTIONARY = "dictionary"
    ZSTD = "zstd"


class CompressionLevel(Enum):
    """Compression levels"""
    FAST = "fast"
    NORMAL = "normal"
    BEST = "best"


@dataclass
class CompressionConfig:
    """Compression configuration"""
    algorithm: CompressionAlgorithm
    level: CompressionLevel
    block_size: int = 65536
    dictionary: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "algorithm": self.algorithm.value,
            "level": self.level.value,
            "block_size": self.block_size,
            "dictionary": self.dictionary,
        }


@dataclass
class CompressionResult:
    """Compression result"""
    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_time: float
    decompression_time: float
    algorithm: CompressionAlgorithm
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "compression_ratio": self.compression_ratio,
            "compression_time": self.compression_time,
            "decompression_time": self.decompression_time,
            "algorithm": self.algorithm.value,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }


# ============================================================
# DATA COMPRESSION ENGINE
# ============================================================

class DataCompressionEngine:
    """
    Comprehensive data compression engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data compression engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_algorithm = self.config.get("default_algorithm", CompressionAlgorithm.ZLIB)
        self.default_level = self.config.get("default_level", CompressionLevel.NORMAL)
        
        # Try to import zstd
        try:
            import zstandard as zstd
            self.zstd = zstd
            HAS_ZSTD = True
        except ImportError:
            HAS_ZSTD = False
        
        logger.info("Data compression engine initialized")
    
    # ============================================================
    # COMPRESSION
    # ============================================================
    
    def compress_data(
        self,
        data: bytes,
        algorithm: Optional[CompressionAlgorithm] = None,
        level: Optional[CompressionLevel] = None
    ) -> Tuple[bytes, CompressionResult]:
        """
        Compress data
        
        Args:
            data: Data to compress
            algorithm: Compression algorithm
            level: Compression level
            
        Returns:
            (compressed_data, CompressionResult)
        """
        if algorithm is None:
            algorithm = self.default_algorithm
        if level is None:
            level = self.default_level
        
        original_size = len(data)
        start_time = datetime.now()
        
        if algorithm == CompressionAlgorithm.NONE:
            compressed = data
        
        elif algorithm == CompressionAlgorithm.ZLIB:
            compressed = self._compress_zlib(data, level)
        
        elif algorithm == CompressionAlgorithm.GZIP:
            compressed = self._compress_gzip(data, level)
        
        elif algorithm == CompressionAlgorithm.BZIP2:
            compressed = self._compress_bzip2(data, level)
        
        elif algorithm == CompressionAlgorithm.LZMA:
            compressed = self._compress_lzma(data, level)
        
        elif algorithm == CompressionAlgorithm.DELTA:
            compressed = self._compress_delta(data)
        
        elif algorithm == CompressionAlgorithm.RLE:
            compressed = self._compress_rle(data)
        
        elif algorithm == CompressionAlgorithm.DICTIONARY:
            compressed = self._compress_dictionary(data)
        
        elif algorithm == CompressionAlgorithm.ZSTD:
            if HAS_ZSTD:
                compressed = self._compress_zstd(data, level)
            else:
                compressed = data
        
        else:
            compressed = data
        
        compression_time = (datetime.now() - start_time).total_seconds()
        compressed_size = len(compressed)
        ratio = compressed_size / original_size if original_size > 0 else 1.0
        
        result = CompressionResult(
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=ratio,
            compression_time=compression_time,
            decompression_time=0.0,
            algorithm=algorithm,
            checksum=self._calculate_checksum(compressed),
            metadata={
                "level": level.value if level else "none",
                "original_checksum": self._calculate_checksum(data),
            },
        )
        
        return compressed, result
    
    def _compress_zlib(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with ZLIB"""
        compress_level = self._get_compress_level(level)
        return zlib.compress(data, level=compress_level)
    
    def _compress_gzip(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with GZIP"""
        compress_level = self._get_compress_level(level)
        return gzip.compress(data, compresslevel=compress_level)
    
    def _compress_bzip2(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with BZIP2"""
        compress_level = self._get_compress_level(level)
        return bz2.compress(data, compresslevel=compress_level)
    
    def _compress_lzma(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with LZMA"""
        compress_level = self._get_compress_level(level)
        return lzma.compress(data, preset=compress_level)
    
    def _compress_delta(self, data: bytes) -> bytes:
        """Delta compression"""
        if len(data) < 2:
            return data
        
        compressed = bytearray()
        compressed.append(data[0])
        
        for i in range(1, len(data)):
            delta = data[i] - data[i-1]
            compressed.append(delta & 0xFF)
        
        return bytes(compressed)
    
    def _compress_rle(self, data: bytes) -> bytes:
        """Run-Length Encoding"""
        compressed = []
        i = 0
        n = len(data)
        
        while i < n:
            count = 1
            while i + count < n and data[i] == data[i + count]:
                count += 1
            
            compressed.append(count)
            compressed.append(data[i])
            i += count
        
        return bytes(compressed)
    
    def _compress_dictionary(self, data: bytes) -> bytes:
        """Dictionary compression"""
        # Build frequency dictionary
        freq = {}
        for byte in data:
            freq[byte] = freq.get(byte, 0) + 1
        
        # Sort by frequency
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        
        # Create dictionary mapping
        dictionary = {byte: i for i, (byte, _) in enumerate(sorted_freq)}
        
        # Compress
        compressed = bytearray()
        for byte in data:
            compressed.append(dictionary[byte])
        
        # Store dictionary header
        header = struct.pack('H', len(dictionary))
        for byte, code in dictionary.items():
            header += struct.pack('BB', byte, code)
        
        return header + bytes(compressed)
    
    def _compress_zstd(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress with ZSTD"""
        if not HAS_ZSTD:
            return data
        
        compress_level = self._get_compress_level(level)
        compressor = self.zstd.ZstdCompressor(level=compress_level)
        return compressor.compress(data)
    
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
    # DECOMPRESSION
    # ============================================================
    
    def decompress_data(
        self,
        compressed_data: bytes,
        algorithm: CompressionAlgorithm
    ) -> Tuple[bytes, CompressionResult]:
        """
        Decompress data
        
        Args:
            compressed_data: Compressed data
            algorithm: Compression algorithm
            
        Returns:
            (decompressed_data, CompressionResult)
        """
        start_time = datetime.now()
        
        if algorithm == CompressionAlgorithm.NONE:
            decompressed = compressed_data
        
        elif algorithm == CompressionAlgorithm.ZLIB:
            decompressed = self._decompress_zlib(compressed_data)
        
        elif algorithm == CompressionAlgorithm.GZIP:
            decompressed = self._decompress_gzip(compressed_data)
        
        elif algorithm == CompressionAlgorithm.BZIP2:
            decompressed = self._decompress_bzip2(compressed_data)
        
        elif algorithm == CompressionAlgorithm.LZMA:
            decompressed = self._decompress_lzma(compressed_data)
        
        elif algorithm == CompressionAlgorithm.DELTA:
            decompressed = self._decompress_delta(compressed_data)
        
        elif algorithm == CompressionAlgorithm.RLE:
            decompressed = self._decompress_rle(compressed_data)
        
        elif algorithm == CompressionAlgorithm.DICTIONARY:
            decompressed = self._decompress_dictionary(compressed_data)
        
        elif algorithm == CompressionAlgorithm.ZSTD:
            if HAS_ZSTD:
                decompressed = self._decompress_zstd(compressed_data)
            else:
                decompressed = compressed_data
        
        else:
            decompressed = compressed_data
        
        decompression_time = (datetime.now() - start_time).total_seconds()
        
        result = CompressionResult(
            original_size=len(decompressed),
            compressed_size=len(compressed_data),
            compression_ratio=len(compressed_data) / len(decompressed) if len(decompressed) > 0 else 1.0,
            compression_time=0.0,
            decompression_time=decompression_time,
            algorithm=algorithm,
            checksum=self._calculate_checksum(decompressed),
        )
        
        return decompressed, result
    
    def _decompress_zlib(self, data: bytes) -> bytes:
        """Decompress with ZLIB"""
        return zlib.decompress(data)
    
    def _decompress_gzip(self, data: bytes) -> bytes:
        """Decompress with GZIP"""
        return gzip.decompress(data)
    
    def _decompress_bzip2(self, data: bytes) -> bytes:
        """Decompress with BZIP2"""
        return bz2.decompress(data)
    
    def _decompress_lzma(self, data: bytes) -> bytes:
        """Decompress with LZMA"""
        return lzma.decompress(data)
    
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
    
    def _decompress_rle(self, data: bytes) -> bytes:
        """RLE decompression"""
        decompressed = []
        i = 0
        n = len(data)
        
        while i < n:
            if i + 1 < n:
                count = data[i]
                value = data[i + 1]
                decompressed.extend([value] * count)
                i += 2
            else:
                i += 1
        
        return bytes(decompressed)
    
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
    
    def _decompress_zstd(self, data: bytes) -> bytes:
        """Decompress with ZSTD"""
        if not HAS_ZSTD:
            return data
        
        decompressor = self.zstd.ZstdDecompressor()
        return decompressor.decompress(data)
    
    # ============================================================
    # COMPRESSION OPTIMIZATION
    # ============================================================
    
    def find_best_algorithm(
        self,
        data: bytes,
        algorithms: Optional[List[CompressionAlgorithm]] = None
    ) -> Tuple[CompressionAlgorithm, CompressionResult]:
        """
        Find the best compression algorithm for data
        
        Args:
            data: Data to compress
            algorithms: Algorithms to test
            
        Returns:
            (best_algorithm, CompressionResult)
        """
        if algorithms is None:
            algorithms = [
                CompressionAlgorithm.ZLIB,
                CompressionAlgorithm.GZIP,
                CompressionAlgorithm.BZIP2,
                CompressionAlgorithm.LZMA,
            ]
        
        best_ratio = 1.0
        best_algorithm = CompressionAlgorithm.NONE
        best_result = None
        
        for algorithm in algorithms:
            try:
                compressed, result = self.compress_data(data, algorithm, CompressionLevel.FAST)
                if result.compression_ratio < best_ratio:
                    best_ratio = result.compression_ratio
                    best_algorithm = algorithm
                    best_result = result
            except:
                continue
        
        return best_algorithm, best_result
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get compression statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "default_algorithm": self.default_algorithm.value,
            "default_level": self.default_level.value,
            "algorithms_available": {
                "zstd": HAS_ZSTD,
                "zlib": True,
                "gzip": True,
                "bzip2": True,
                "lzma": True,
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "CompressionAlgorithm",
    "CompressionLevel",
    
    # Dataclasses
    "CompressionConfig",
    "CompressionResult",
    
    # Classes
    "DataCompressionEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

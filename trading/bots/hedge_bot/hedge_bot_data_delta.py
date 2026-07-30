# trading/bots/hedge_bot/hedge_bot_data_delta.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Delta Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Delta Module

This module provides comprehensive delta computation and change detection
capabilities for the NEXUS Hedge Bot system. It tracks changes in data,
computes deltas, and manages change detection.

The module covers:
- Delta Computation
- Change Detection
- Data Comparison
- Version Tracking
- Difference Analysis
- Change History
- Patch Generation
- Data Synchronization
"""

import os
import sys
import json
import logging
import hashlib
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import difflib

logger = logging.getLogger(__name__)


# ============================================================
# DATA DELTA ENUMS
# ============================================================

class DeltaType(Enum):
    """Delta types"""
    ADD = "add"
    REMOVE = "remove"
    MODIFY = "modify"
    NO_CHANGE = "no_change"


class ComparisonMode(Enum):
    """Comparison modes"""
    FULL = "full"
    KEYS = "keys"
    VALUES = "values"
    STRUCTURE = "structure"
    CUSTOM = "custom"


@dataclass
class DataDelta:
    """Data delta"""
    id: str
    delta_type: DeltaType
    key: str
    old_value: Any
    new_value: Any
    path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "delta_type": self.delta_type.value,
            "key": self.key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "path": self.path,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DataSnapshot:
    """Data snapshot"""
    id: str
    version: int
    data: Dict[str, Any]
    timestamp: datetime
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "checksum": self.checksum,
            "metadata": self.metadata,
            "data_size": len(str(self.data)),
        }


@dataclass
class DeltaResult:
    """Delta result"""
    delta_type: DeltaType
    deltas: List[DataDelta]
    summary: Dict[str, int]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "delta_type": self.delta_type.value,
            "deltas": [d.to_dict() for d in self.deltas],
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# DATA DELTA ENGINE
# ============================================================

class DataDeltaEngine:
    """
    Comprehensive data delta engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data delta engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.max_history = self.config.get("max_history", 100)
        self.comparison_mode = self.config.get("comparison_mode", ComparisonMode.FULL)
        
        # State
        self.snapshots: Dict[str, DataSnapshot] = {}
        self.deltas: Dict[str, List[DataDelta]] = {}
        self.delta_results: List[DeltaResult] = []
        self.version_counter: int = 0
        
        logger.info("Data delta engine initialized")
    
    # ============================================================
    # DELTA COMPUTATION
    # ============================================================
    
    def compute_delta(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        mode: ComparisonMode = ComparisonMode.FULL,
        path: str = ""
    ) -> List[DataDelta]:
        """
        Compute delta between old and new data
        
        Args:
            old_data: Old data
            new_data: New data
            mode: Comparison mode
            path: Current path
            
        Returns:
            List of DataDelta
        """
        deltas = []
        
        if mode == ComparisonMode.FULL:
            deltas = self._compute_full_delta(old_data, new_data, path)
        elif mode == ComparisonMode.KEYS:
            deltas = self._compute_keys_delta(old_data, new_data, path)
        elif mode == ComparisonMode.VALUES:
            deltas = self._compute_values_delta(old_data, new_data, path)
        elif mode == ComparisonMode.STRUCTURE:
            deltas = self._compute_structure_delta(old_data, new_data, path)
        else:
            deltas = self._compute_full_delta(old_data, new_data, path)
        
        return deltas
    
    def _compute_full_delta(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        path: str
    ) -> List[DataDelta]:
        """Compute full delta between dictionaries"""
        deltas = []
        
        # Get all keys
        all_keys = set(old_data.keys()) | set(new_data.keys())
        
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            
            if key not in old_data:
                # Added
                deltas.append(DataDelta(
                    id=f"delta_{int(time.time())}_{len(deltas)}",
                    delta_type=DeltaType.ADD,
                    key=key,
                    old_value=None,
                    new_value=new_data[key],
                    path=current_path,
                ))
            elif key not in new_data:
                # Removed
                deltas.append(DataDelta(
                    id=f"delta_{int(time.time())}_{len(deltas)}",
                    delta_type=DeltaType.REMOVE,
                    key=key,
                    old_value=old_data[key],
                    new_value=None,
                    path=current_path,
                ))
            elif old_data[key] != new_data[key]:
                # Modified
                if isinstance(old_data[key], dict) and isinstance(new_data[key], dict):
                    # Recursively compare nested dicts
                    nested_deltas = self._compute_full_delta(
                        old_data[key],
                        new_data[key],
                        current_path
                    )
                    deltas.extend(nested_deltas)
                else:
                    # Simple value modification
                    deltas.append(DataDelta(
                        id=f"delta_{int(time.time())}_{len(deltas)}",
                        delta_type=DeltaType.MODIFY,
                        key=key,
                        old_value=old_data[key],
                        new_value=new_data[key],
                        path=current_path,
                    ))
        
        return deltas
    
    def _compute_keys_delta(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        path: str
    ) -> List[DataDelta]:
        """Compute delta based on keys only"""
        deltas = []
        
        old_keys = set(old_data.keys())
        new_keys = set(new_data.keys())
        
        # Added keys
        for key in new_keys - old_keys:
            deltas.append(DataDelta(
                id=f"delta_{int(time.time())}_{len(deltas)}",
                delta_type=DeltaType.ADD,
                key=key,
                old_value=None,
                new_value=new_data[key],
                path=f"{path}.{key}" if path else key,
            ))
        
        # Removed keys
        for key in old_keys - new_keys:
            deltas.append(DataDelta(
                id=f"delta_{int(time.time())}_{len(deltas)}",
                delta_type=DeltaType.REMOVE,
                key=key,
                old_value=old_data[key],
                new_value=None,
                path=f"{path}.{key}" if path else key,
            ))
        
        return deltas
    
    def _compute_values_delta(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        path: str
    ) -> List[DataDelta]:
        """Compute delta based on values only"""
        deltas = []
        
        common_keys = set(old_data.keys()) & set(new_data.keys())
        
        for key in common_keys:
            if old_data[key] != new_data[key]:
                deltas.append(DataDelta(
                    id=f"delta_{int(time.time())}_{len(deltas)}",
                    delta_type=DeltaType.MODIFY,
                    key=key,
                    old_value=old_data[key],
                    new_value=new_data[key],
                    path=f"{path}.{key}" if path else key,
                ))
        
        return deltas
    
    def _compute_structure_delta(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        path: str
    ) -> List[DataDelta]:
        """Compute delta based on structure only"""
        deltas = []
        
        def get_structure(data):
            if isinstance(data, dict):
                return {k: type(v).__name__ for k, v in data.items()}
            return type(data).__name__
        
        old_structure = get_structure(old_data)
        new_structure = get_structure(new_data)
        
        return self._compute_keys_delta(old_structure, new_structure, path)
    
    # ============================================================
    # SNAPSHOT MANAGEMENT
    # ============================================================
    
    def create_snapshot(
        self,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataSnapshot:
        """
        Create a data snapshot
        
        Args:
            data: Data to snapshot
            metadata: Additional metadata
            
        Returns:
            DataSnapshot
        """
        self.version_counter += 1
        
        snapshot = DataSnapshot(
            id=f"snapshot_{int(time.time())}_{self.version_counter}",
            version=self.version_counter,
            data=data.copy(),
            timestamp=datetime.now(),
            checksum=self._calculate_checksum(data),
            metadata=metadata or {},
        )
        
        self.snapshots[snapshot.id] = snapshot
        
        # Clean old snapshots
        if len(self.snapshots) > self.max_history:
            oldest = min(self.snapshots.items(), key=lambda x: x[1].timestamp)[0]
            del self.snapshots[oldest]
        
        logger.info(f"Created snapshot v{self.version_counter}")
        return snapshot
    
    def get_snapshot(self, snapshot_id: str) -> Optional[DataSnapshot]:
        """
        Get a snapshot
        
        Args:
            snapshot_id: Snapshot ID
            
        Returns:
            DataSnapshot or None
        """
        return self.snapshots.get(snapshot_id)
    
    def get_latest_snapshot(self) -> Optional[DataSnapshot]:
        """
        Get latest snapshot
        
        Returns:
            DataSnapshot or None
        """
        if not self.snapshots:
            return None
        
        return max(self.snapshots.values(), key=lambda x: x.timestamp)
    
    def get_snapshots(
        self,
        limit: int = 10
    ) -> List[DataSnapshot]:
        """
        Get snapshots
        
        Args:
            limit: Maximum number of snapshots
            
        Returns:
            List of snapshots
        """
        snapshots = list(self.snapshots.values())
        snapshots.sort(key=lambda x: x.timestamp, reverse=True)
        return snapshots[:limit]
    
    # ============================================================
    # DELTA ANALYSIS
    # ============================================================
    
    def compare_snapshots(
        self,
        snapshot1_id: str,
        snapshot2_id: str,
        mode: ComparisonMode = ComparisonMode.FULL
    ) -> DeltaResult:
        """
        Compare two snapshots
        
        Args:
            snapshot1_id: First snapshot ID
            snapshot2_id: Second snapshot ID
            mode: Comparison mode
            
        Returns:
            DeltaResult
        """
        snapshot1 = self.get_snapshot(snapshot1_id)
        snapshot2 = self.get_snapshot(snapshot2_id)
        
        if not snapshot1 or not snapshot2:
            raise ValueError("Snapshot not found")
        
        deltas = self.compute_delta(
            snapshot1.data,
            snapshot2.data,
            mode,
        )
        
        # Generate summary
        summary = {
            "adds": len([d for d in deltas if d.delta_type == DeltaType.ADD]),
            "removes": len([d for d in deltas if d.delta_type == DeltaType.REMOVE]),
            "modifies": len([d for d in deltas if d.delta_type == DeltaType.MODIFY]),
            "total": len(deltas),
        }
        
        result = DeltaResult(
            delta_type=DeltaType.MODIFY,
            deltas=deltas,
            summary=summary,
            timestamp=datetime.now(),
            metadata={
                "snapshot1": snapshot1.id,
                "snapshot2": snapshot2.id,
                "version1": snapshot1.version,
                "version2": snapshot2.version,
            },
        )
        
        self.delta_results.append(result)
        return result
    
    def get_delta_history(
        self,
        limit: int = 10
    ) -> List[DeltaResult]:
        """
        Get delta history
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of DeltaResult
        """
        return self.delta_results[-limit:]
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate data checksum"""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def detect_changes(
        self,
        data: Dict[str, Any],
        previous_data: Optional[Dict[str, Any]] = None
    ) -> DeltaResult:
        """
        Detect changes in data
        
        Args:
            data: Current data
            previous_data: Previous data
            
        Returns:
            DeltaResult
        """
        if previous_data is None:
            # Get previous snapshot
            latest = self.get_latest_snapshot()
            if latest:
                previous_data = latest.data
            else:
                # Create first snapshot
                self.create_snapshot(data)
                return DeltaResult(
                    delta_type=DeltaType.NO_CHANGE,
                    deltas=[],
                    summary={"total": 0},
                    timestamp=datetime.now(),
                    metadata={"first_snapshot": True},
                )
        
        # Compute deltas
        deltas = self.compute_delta(previous_data, data)
        
        # Determine delta type
        if not deltas:
            delta_type = DeltaType.NO_CHANGE
        else:
            delta_type = DeltaType.MODIFY
        
        # Summary
        summary = {
            "adds": len([d for d in deltas if d.delta_type == DeltaType.ADD]),
            "removes": len([d for d in deltas if d.delta_type == DeltaType.REMOVE]),
            "modifies": len([d for d in deltas if d.delta_type == DeltaType.MODIFY]),
            "total": len(deltas),
        }
        
        result = DeltaResult(
            delta_type=delta_type,
            deltas=deltas,
            summary=summary,
            timestamp=datetime.now(),
            metadata={
                "version": self.version_counter + 1,
                "has_changes": len(deltas) > 0,
            },
        )
        
        # Create new snapshot
        self.create_snapshot(data)
        self.delta_results.append(result)
        
        return result
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get delta statistics
        
        Returns:
            Statistics dictionary
        """
        total_deltas = sum(len(r.deltas) for r in self.delta_results)
        
        return {
            "total_snapshots": len(self.snapshots),
            "total_delta_results": len(self.delta_results),
            "total_deltas": total_deltas,
            "latest_version": self.version_counter,
            "comparison_mode": self.comparison_mode.value,
            "delta_types": {
                dt.value: sum(
                    1 for r in self.delta_results
                    for d in r.deltas if d.delta_type == dt
                )
                for dt in DeltaType
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "DeltaType",
    "ComparisonMode",
    
    # Dataclasses
    "DataDelta",
    "DataSnapshot",
    "DeltaResult",
    
    # Classes
    "DataDeltaEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

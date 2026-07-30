# trading/bots/hedge_bot/hedge_bot_data_catalog.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Catalog Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Catalog Module

This module provides comprehensive data catalog and metadata management
capabilities for the NEXUS Hedge Bot system. It tracks data assets,
metadata, lineage, and data quality.

The module covers:
- Data Asset Management
- Metadata Management
- Data Lineage
- Data Quality Tracking
- Data Discovery
- Data Classification
- Data Versioning
- Data Governance
- Data Catalog Search
"""

import os
import sys
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import re

logger = logging.getLogger(__name__)


# ============================================================
# DATA CATALOG ENUMS
# ============================================================

class DataAssetType(Enum):
    """Data asset types"""
    DATABASE = "database"
    TABLE = "table"
    COLUMN = "column"
    FILE = "file"
    STREAM = "stream"
    API = "api"
    CACHE = "cache"
    MODEL = "model"


class DataQuality(Enum):
    """Data quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


class DataSensitivity(Enum):
    """Data sensitivity levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


@dataclass
class DataAsset:
    """Data asset"""
    id: str
    name: str
    type: DataAssetType
    description: str
    location: str
    created_at: datetime
    updated_at: datetime
    owner: str
    tags: List[str]
    metadata: Dict[str, Any]
    quality: DataQuality = DataQuality.UNKNOWN
    sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    version: int = 1
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    usage_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "location": self.location,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "owner": self.owner,
            "tags": self.tags,
            "metadata": self.metadata,
            "quality": self.quality.value,
            "sensitivity": self.sensitivity.value,
            "version": self.version,
            "parent_id": self.parent_id,
            "dependencies": self.dependencies,
            "usage_count": self.usage_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
        }


@dataclass
class DataLineage:
    """Data lineage"""
    asset_id: str
    source_assets: List[str]
    target_assets: List[str]
    transformations: List[Dict[str, Any]]
    created_at: datetime
    version: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "asset_id": self.asset_id,
            "source_assets": self.source_assets,
            "target_assets": self.target_assets,
            "transformations": self.transformations,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
        }


@dataclass
class DataQualityReport:
    """Data quality report"""
    asset_id: str
    quality: DataQuality
    score: float
    metrics: Dict[str, float]
    issues: List[str]
    recommendations: List[str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "asset_id": self.asset_id,
            "quality": self.quality.value,
            "score": self.score,
            "metrics": self.metrics,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# DATA CATALOG ENGINE
# ============================================================

class DataCatalogEngine:
    """
    Comprehensive data catalog engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data catalog engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.catalog_path = Path(self.config.get("catalog_path", "data_catalog.json"))
        
        # State
        self.assets: Dict[str, DataAsset] = {}
        self.lineage: Dict[str, DataLineage] = {}
        self.quality_reports: Dict[str, List[DataQualityReport]] = {}
        
        # Load catalog
        self._load_catalog()
        
        logger.info("Data catalog engine initialized")
    
    # ============================================================
    # CATALOG LOADING/SAVING
    # ============================================================
    
    def _load_catalog(self) -> None:
        """Load catalog from file"""
        if self.catalog_path.exists():
            try:
                with open(self.catalog_path, "r") as f:
                    data = json.load(f)
                    
                    # Load assets
                    for asset_data in data.get("assets", []):
                        asset = DataAsset(
                            id=asset_data["id"],
                            name=asset_data["name"],
                            type=DataAssetType(asset_data["type"]),
                            description=asset_data["description"],
                            location=asset_data["location"],
                            created_at=datetime.fromisoformat(asset_data["created_at"]),
                            updated_at=datetime.fromisoformat(asset_data["updated_at"]),
                            owner=asset_data["owner"],
                            tags=asset_data["tags"],
                            metadata=asset_data["metadata"],
                            quality=DataQuality(asset_data.get("quality", "unknown")),
                            sensitivity=DataSensitivity(asset_data.get("sensitivity", "internal")),
                            version=asset_data.get("version", 1),
                            parent_id=asset_data.get("parent_id"),
                            dependencies=asset_data.get("dependencies", []),
                            usage_count=asset_data.get("usage_count", 0),
                            last_accessed=datetime.fromisoformat(asset_data["last_accessed"]) if asset_data.get("last_accessed") else None,
                        )
                        self.assets[asset.id] = asset
                    
                    # Load lineage
                    for lineage_data in data.get("lineage", []):
                        lineage = DataLineage(
                            asset_id=lineage_data["asset_id"],
                            source_assets=lineage_data["source_assets"],
                            target_assets=lineage_data["target_assets"],
                            transformations=lineage_data["transformations"],
                            created_at=datetime.fromisoformat(lineage_data["created_at"]),
                            version=lineage_data.get("version", 1),
                        )
                        self.lineage[lineage.asset_id] = lineage
                    
                    logger.info(f"Loaded catalog with {len(self.assets)} assets")
            except Exception as e:
                logger.error(f"Failed to load catalog: {e}")
    
    def _save_catalog(self) -> None:
        """Save catalog to file"""
        try:
            data = {
                "assets": [a.to_dict() for a in self.assets.values()],
                "lineage": [l.to_dict() for l in self.lineage.values()],
                "updated_at": datetime.now().isoformat(),
            }
            
            with open(self.catalog_path, "w") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved catalog with {len(self.assets)} assets")
        except Exception as e:
            logger.error(f"Failed to save catalog: {e}")
    
    # ============================================================
    # ASSET MANAGEMENT
    # ============================================================
    
    def create_asset(
        self,
        name: str,
        asset_type: DataAssetType,
        description: str,
        location: str,
        owner: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    ) -> DataAsset:
        """
        Create a data asset
        
        Args:
            name: Asset name
            asset_type: Asset type
            description: Asset description
            location: Asset location
            owner: Asset owner
            tags: Tags
            metadata: Additional metadata
            parent_id: Parent asset ID
            sensitivity: Data sensitivity
            
        Returns:
            DataAsset
        """
        asset = DataAsset(
            id=f"asset_{int(time.time())}_{len(self.assets)}",
            name=name,
            type=asset_type,
            description=description,
            location=location,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            owner=owner,
            tags=tags or [],
            metadata=metadata or {},
            sensitivity=sensitivity,
            parent_id=parent_id,
        )
        
        self.assets[asset.id] = asset
        self._save_catalog()
        
        logger.info(f"Created asset: {name} ({asset_type.value})")
        return asset
    
    def update_asset(
        self,
        asset_id: str,
        updates: Dict[str, Any]
    ) -> Optional[DataAsset]:
        """
        Update an asset
        
        Args:
            asset_id: Asset ID
            updates: Updates to apply
            
        Returns:
            Updated asset or None
        """
        asset = self.assets.get(asset_id)
        if not asset:
            return None
        
        for key, value in updates.items():
            if hasattr(asset, key):
                setattr(asset, key, value)
        
        asset.updated_at = datetime.now()
        asset.version += 1
        self._save_catalog()
        
        return asset
    
    def delete_asset(self, asset_id: str) -> bool:
        """
        Delete an asset
        
        Args:
            asset_id: Asset ID
            
        Returns:
            True if deleted
        """
        if asset_id in self.assets:
            del self.assets[asset_id]
            if asset_id in self.lineage:
                del self.lineage[asset_id]
            if asset_id in self.quality_reports:
                del self.quality_reports[asset_id]
            self._save_catalog()
            logger.info(f"Deleted asset: {asset_id}")
            return True
        return False
    
    def get_asset(self, asset_id: str) -> Optional[DataAsset]:
        """
        Get an asset
        
        Args:
            asset_id: Asset ID
            
        Returns:
            DataAsset or None
        """
        return self.assets.get(asset_id)
    
    def get_assets(
        self,
        asset_type: Optional[DataAssetType] = None,
        tag: Optional[str] = None,
        owner: Optional[str] = None
    ) -> List[DataAsset]:
        """
        Get assets matching criteria
        
        Args:
            asset_type: Filter by type
            tag: Filter by tag
            owner: Filter by owner
            
        Returns:
            List of assets
        """
        assets = list(self.assets.values())
        
        if asset_type:
            assets = [a for a in assets if a.type == asset_type]
        if tag:
            assets = [a for a in assets if tag in a.tags]
        if owner:
            assets = [a for a in assets if a.owner == owner]
        
        return assets
    
    # ============================================================
    # LINEAGE MANAGEMENT
    # ============================================================
    
    def track_lineage(
        self,
        asset_id: str,
        source_assets: List[str],
        target_assets: List[str],
        transformations: List[Dict[str, Any]]
    ) -> DataLineage:
        """
        Track data lineage
        
        Args:
            asset_id: Asset ID
            source_assets: Source asset IDs
            target_assets: Target asset IDs
            transformations: Transformation details
            
        Returns:
            DataLineage
        """
        lineage = DataLineage(
            asset_id=asset_id,
            source_assets=source_assets,
            target_assets=target_assets,
            transformations=transformations,
            created_at=datetime.now(),
            version=1,
        )
        
        self.lineage[asset_id] = lineage
        self._save_catalog()
        
        return lineage
    
    def get_lineage(self, asset_id: str) -> Optional[DataLineage]:
        """
        Get data lineage
        
        Args:
            asset_id: Asset ID
            
        Returns:
            DataLineage or None
        """
        return self.lineage.get(asset_id)
    
    def get_upstream(self, asset_id: str) -> List[DataAsset]:
        """
        Get upstream assets
        
        Args:
            asset_id: Asset ID
            
        Returns:
            List of upstream assets
        """
        lineage = self.lineage.get(asset_id)
        if not lineage:
            return []
        
        return [self.assets.get(source_id) for source_id in lineage.source_assets if source_id in self.assets]
    
    def get_downstream(self, asset_id: str) -> List[DataAsset]:
        """
        Get downstream assets
        
        Args:
            asset_id: Asset ID
            
        Returns:
            List of downstream assets
        """
        downstream = []
        for lineage in self.lineage.values():
            if asset_id in lineage.source_assets:
                asset = self.assets.get(lineage.asset_id)
                if asset:
                    downstream.append(asset)
        return downstream
    
    # ============================================================
    # QUALITY MANAGEMENT
    # ============================================================
    
    def assess_quality(
        self,
        asset_id: str,
        quality: DataQuality,
        score: float,
        metrics: Dict[str, float],
        issues: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None
    ) -> DataQualityReport:
        """
        Assess data quality
        
        Args:
            asset_id: Asset ID
            quality: Quality level
            score: Quality score (0-1)
            metrics: Quality metrics
            issues: Issues found
            recommendations: Improvement recommendations
            
        Returns:
            DataQualityReport
        """
        report = DataQualityReport(
            asset_id=asset_id,
            quality=quality,
            score=score,
            metrics=metrics,
            issues=issues or [],
            recommendations=recommendations or [],
            timestamp=datetime.now(),
        )
        
        if asset_id not in self.quality_reports:
            self.quality_reports[asset_id] = []
        self.quality_reports[asset_id].append(report)
        
        # Update asset quality
        asset = self.assets.get(asset_id)
        if asset:
            asset.quality = quality
            self._save_catalog()
        
        return report
    
    def get_quality_reports(
        self,
        asset_id: str,
        limit: int = 10
    ) -> List[DataQualityReport]:
        """
        Get quality reports for an asset
        
        Args:
            asset_id: Asset ID
            limit: Maximum number of reports
            
        Returns:
            List of quality reports
        """
        reports = self.quality_reports.get(asset_id, [])
        return reports[-limit:]
    
    # ============================================================
    # SEARCH
    # ============================================================
    
    def search(self, query: str) -> List[DataAsset]:
        """
        Search for assets
        
        Args:
            query: Search query
            
        Returns:
            List of matching assets
        """
        query_lower = query.lower()
        results = []
        
        for asset in self.assets.values():
            if (query_lower in asset.name.lower() or
                query_lower in asset.description.lower() or
                any(query_lower in tag.lower() for tag in asset.tags)):
                results.append(asset)
        
        return results
    
    # ============================================================
    # USAGE TRACKING
    # ============================================================
    
    def record_usage(self, asset_id: str) -> None:
        """
        Record asset usage
        
        Args:
            asset_id: Asset ID
        """
        asset = self.assets.get(asset_id)
        if asset:
            asset.usage_count += 1
            asset.last_accessed = datetime.now()
            self._save_catalog()
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get catalog statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_assets": len(self.assets),
            "by_type": {
                t.value: len([a for a in self.assets.values() if a.type == t])
                for t in DataAssetType
            },
            "by_quality": {
                q.value: len([a for a in self.assets.values() if a.quality == q])
                for q in DataQuality
            },
            "by_sensitivity": {
                s.value: len([a for a in self.assets.values() if a.sensitivity == s])
                for s in DataSensitivity
            },
            "total_lineage": len(self.lineage),
            "total_quality_reports": sum(len(r) for r in self.quality_reports.values()),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "DataAssetType",
    "DataQuality",
    "DataSensitivity",
    
    # Dataclasses
    "DataAsset",
    "DataLineage",
    "DataQualityReport",
    
    # Classes
    "DataCatalogEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

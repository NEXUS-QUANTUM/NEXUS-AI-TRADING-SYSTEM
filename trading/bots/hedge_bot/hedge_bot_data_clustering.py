# trading/bots/hedge_bot/hedge_bot_data_clustering.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Clustering Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Clustering Module

This module provides comprehensive data clustering and segmentation
capabilities for the NEXUS Hedge Bot system. It identifies patterns,
groups similar data points, and discovers market segments.

The module covers:
- K-Means Clustering
- Hierarchical Clustering
- DBSCAN Clustering
- Gaussian Mixture Models
- Market Segmentation
- Pattern Discovery
- Anomaly Detection via Clustering
- Cluster Visualization
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

# Try to import sklearn
try:
    from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score, calinski_harabasz_score
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)


# ============================================================
# CLUSTERING ENUMS
# ============================================================

class ClusteringMethod(Enum):
    """Clustering methods"""
    KMEANS = "kmeans"
    DBSCAN = "dbscan"
    HIERARCHICAL = "hierarchical"
    GMM = "gmm"
    AGGREGATIVE = "aggregative"


class DistanceMetric(Enum):
    """Distance metrics"""
    EUCLIDEAN = "euclidean"
    MANHATTAN = "manhattan"
    COSINE = "cosine"
    CORRELATION = "correlation"


@dataclass
class ClusteringResult:
    """Clustering result"""
    method: ClusteringMethod
    n_clusters: int
    labels: List[int]
    metrics: Dict[str, float]
    cluster_centers: Optional[np.ndarray] = None
    cluster_sizes: Dict[int, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "method": self.method.value,
            "n_clusters": self.n_clusters,
            "metrics": self.metrics,
            "cluster_centers": self.cluster_centers.tolist() if self.cluster_centers is not None else None,
            "cluster_sizes": self.cluster_sizes,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ClusterProfile:
    """Cluster profile"""
    cluster_id: int
    size: int
    percentage: float
    centroid: np.ndarray
    features: Dict[str, Any]
    statistics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "percentage": self.percentage,
            "centroid": self.centroid.tolist(),
            "features": self.features,
            "statistics": self.statistics,
        }


# ============================================================
# DATA CLUSTERING ENGINE
# ============================================================

class DataClusteringEngine:
    """
    Comprehensive data clustering engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the clustering engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.random_seed = self.config.get("random_seed", 42)
        
        if not HAS_SKLEARN:
            logger.warning("scikit-learn not installed. Clustering capabilities limited.")
        
        # State
        self.clustering_results: List[ClusteringResult] = []
        self.cluster_profiles: List[ClusterProfile] = []
        self.models: Dict[str, Any] = {}
        
        logger.info("Data clustering engine initialized")
    
    # ============================================================
    # K-MEANS CLUSTERING
    # ============================================================
    
    def kmeans_cluster(
        self,
        data: np.ndarray,
        n_clusters: int = 5,
        max_iter: int = 300,
        random_state: int = 42
    ) -> ClusteringResult:
        """
        Perform K-Means clustering
        
        Args:
            data: Data to cluster
            n_clusters: Number of clusters
            max_iter: Maximum iterations
            random_state: Random seed
            
        Returns:
            ClusteringResult
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn required for K-Means")
        
        # Scale data
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data)
        
        # Perform K-Means
        kmeans = KMeans(
            n_clusters=n_clusters,
            max_iter=max_iter,
            random_state=random_state,
            n_init=10,
        )
        labels = kmeans.fit_predict(data_scaled)
        
        # Calculate metrics
        metrics = self._calculate_metrics(data_scaled, labels)
        
        # Get cluster sizes
        cluster_sizes = {}
        for i in range(n_clusters):
            cluster_sizes[i] = np.sum(labels == i)
        
        result = ClusteringResult(
            method=ClusteringMethod.KMEANS,
            n_clusters=n_clusters,
            labels=labels.tolist(),
            metrics=metrics,
            cluster_centers=kmeans.cluster_centers_,
            cluster_sizes=cluster_sizes,
        )
        
        self.clustering_results.append(result)
        self.models[f"kmeans_{n_clusters}"] = kmeans
        
        return result
    
    # ============================================================
    # DBSCAN CLUSTERING
    # ============================================================
    
    def dbscan_cluster(
        self,
        data: np.ndarray,
        eps: float = 0.5,
        min_samples: int = 5
    ) -> ClusteringResult:
        """
        Perform DBSCAN clustering
        
        Args:
            data: Data to cluster
            eps: Neighborhood radius
            min_samples: Minimum samples per cluster
            
        Returns:
            ClusteringResult
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn required for DBSCAN")
        
        # Scale data
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data)
        
        # Perform DBSCAN
        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        labels = dbscan.fit_predict(data_scaled)
        
        # Calculate metrics (excluding noise)
        unique_labels = set(labels)
        n_clusters = len([l for l in unique_labels if l != -1])
        
        # Calculate metrics for non-noise points
        valid_mask = labels != -1
        if np.sum(valid_mask) > 0:
            metrics = self._calculate_metrics(data_scaled[valid_mask], labels[valid_mask])
        else:
            metrics = {}
        
        # Cluster sizes
        cluster_sizes = {}
        for label in unique_labels:
            if label != -1:
                cluster_sizes[label] = np.sum(labels == label)
        
        result = ClusteringResult(
            method=ClusteringMethod.DBSCAN,
            n_clusters=n_clusters,
            labels=labels.tolist(),
            metrics=metrics,
            cluster_sizes=cluster_sizes,
        )
        
        self.clustering_results.append(result)
        return result
    
    # ============================================================
    # HIERARCHICAL CLUSTERING
    # ============================================================
    
    def hierarchical_cluster(
        self,
        data: np.ndarray,
        n_clusters: int = 5,
        linkage: str = 'ward',
        metric: str = 'euclidean'
    ) -> ClusteringResult:
        """
        Perform hierarchical clustering
        
        Args:
            data: Data to cluster
            n_clusters: Number of clusters
            linkage: Linkage method
            metric: Distance metric
            
        Returns:
            ClusteringResult
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn required for hierarchical clustering")
        
        # Scale data
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data)
        
        # Perform hierarchical clustering
        hierarchical = AgglomerativeClustering(
            n_clusters=n_clusters,
            linkage=linkage,
            metric=metric,
        )
        labels = hierarchical.fit_predict(data_scaled)
        
        # Calculate metrics
        metrics = self._calculate_metrics(data_scaled, labels)
        
        # Cluster sizes
        cluster_sizes = {}
        for i in range(n_clusters):
            cluster_sizes[i] = np.sum(labels == i)
        
        result = ClusteringResult(
            method=ClusteringMethod.HIERARCHICAL,
            n_clusters=n_clusters,
            labels=labels.tolist(),
            metrics=metrics,
            cluster_sizes=cluster_sizes,
        )
        
        self.clustering_results.append(result)
        return result
    
    # ============================================================
    # GAUSSIAN MIXTURE MODEL
    # ============================================================
    
    def gmm_cluster(
        self,
        data: np.ndarray,
        n_clusters: int = 5,
        covariance_type: str = 'full',
        max_iter: int = 100
    ) -> ClusteringResult:
        """
        Perform Gaussian Mixture Model clustering
        
        Args:
            data: Data to cluster
            n_clusters: Number of clusters
            covariance_type: Covariance type
            max_iter: Maximum iterations
            
        Returns:
            ClusteringResult
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn required for GMM")
        
        # Scale data
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data)
        
        # Perform GMM
        gmm = GaussianMixture(
            n_components=n_clusters,
            covariance_type=covariance_type,
            max_iter=max_iter,
            random_state=self.random_seed,
        )
        labels = gmm.fit_predict(data_scaled)
        
        # Calculate metrics
        metrics = self._calculate_metrics(data_scaled, labels)
        metrics["bic"] = gmm.bic(data_scaled)
        metrics["aic"] = gmm.aic(data_scaled)
        
        # Cluster sizes
        cluster_sizes = {}
        for i in range(n_clusters):
            cluster_sizes[i] = np.sum(labels == i)
        
        result = ClusteringResult(
            method=ClusteringMethod.GMM,
            n_clusters=n_clusters,
            labels=labels.tolist(),
            metrics=metrics,
            cluster_sizes=cluster_sizes,
        )
        
        self.clustering_results.append(result)
        self.models[f"gmm_{n_clusters}"] = gmm
        
        return result
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
    
    def _calculate_metrics(self, data: np.ndarray, labels: np.ndarray) -> Dict[str, float]:
        """
        Calculate clustering metrics
        
        Args:
            data: Data
            labels: Cluster labels
            
        Returns:
            Metrics dictionary
        """
        metrics = {}
        
        unique_labels = set(labels)
        n_clusters = len(unique_labels)
        
        if n_clusters < 2:
            metrics["silhouette_score"] = 0.0
            metrics["calinski_harabasz_score"] = 0.0
            return metrics
        
        try:
            # Silhouette score
            metrics["silhouette_score"] = silhouette_score(data, labels)
        except:
            metrics["silhouette_score"] = 0.0
        
        try:
            # Calinski-Harabasz score
            metrics["calinski_harabasz_score"] = calinski_harabasz_score(data, labels)
        except:
            metrics["calinski_harabasz_score"] = 0.0
        
        # Number of points per cluster
        cluster_counts = [np.sum(labels == i) for i in range(n_clusters)]
        metrics["min_cluster_size"] = min(cluster_counts) if cluster_counts else 0
        metrics["max_cluster_size"] = max(cluster_counts) if cluster_counts else 0
        metrics["avg_cluster_size"] = np.mean(cluster_counts) if cluster_counts else 0
        
        return metrics
    
    # ============================================================
    # CLUSTER PROFILING
    # ============================================================
    
    def profile_clusters(
        self,
        data: np.ndarray,
        result: ClusteringResult,
        feature_names: Optional[List[str]] = None
    ) -> List[ClusterProfile]:
        """
        Profile clusters
        
        Args:
            data: Original data
            result: Clustering result
            feature_names: Feature names
            
        Returns:
            List of ClusterProfile
        """
        profiles = []
        labels = np.array(result.labels)
        total = len(data)
        
        unique_labels = set(labels)
        if -1 in unique_labels:
            unique_labels.remove(-1)  # Remove noise for DBSCAN
        
        for cluster_id in sorted(unique_labels):
            mask = labels == cluster_id
            cluster_data = data[mask]
            size = np.sum(mask)
            
            # Calculate centroid
            centroid = np.mean(cluster_data, axis=0)
            
            # Calculate statistics
            stats = {
                "mean": np.mean(cluster_data, axis=0).tolist(),
                "std": np.std(cluster_data, axis=0).tolist(),
                "min": np.min(cluster_data, axis=0).tolist(),
                "max": np.max(cluster_data, axis=0).tolist(),
            }
            
            # Feature analysis
            features = {}
            if feature_names and len(feature_names) == cluster_data.shape[1]:
                for i, name in enumerate(feature_names):
                    features[name] = {
                        "mean": np.mean(cluster_data[:, i]),
                        "std": np.std(cluster_data[:, i]),
                        "min": np.min(cluster_data[:, i]),
                        "max": np.max(cluster_data[:, i]),
                    }
            
            profile = ClusterProfile(
                cluster_id=cluster_id,
                size=size,
                percentage=size / total,
                centroid=centroid,
                features=features,
                statistics=stats,
            )
            
            profiles.append(profile)
        
        self.cluster_profiles = profiles
        return profiles
    
    # ============================================================
    # OPTIMAL CLUSTER COUNT
    # ============================================================
    
    def find_optimal_clusters(
        self,
        data: np.ndarray,
        max_clusters: int = 10,
        method: str = "silhouette"
    ) -> Dict[str, Any]:
        """
        Find optimal number of clusters
        
        Args:
            data: Data to cluster
            max_clusters: Maximum number of clusters
            method: Evaluation method
            
        Returns:
            Optimal clusters information
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn required for optimal clusters")
        
        # Scale data
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data)
        
        scores = []
        
        for n_clusters in range(2, max_clusters + 1):
            kmeans = KMeans(n_clusters=n_clusters, random_state=self.random_seed, n_init=10)
            labels = kmeans.fit_predict(data_scaled)
            
            if method == "silhouette":
                score = silhouette_score(data_scaled, labels)
            elif method == "calinski_harabasz":
                score = calinski_harabasz_score(data_scaled, labels)
            else:
                score = silhouette_score(data_scaled, labels)
            
            scores.append({
                "n_clusters": n_clusters,
                "score": score,
            })
        
        # Find optimal
        optimal = max(scores, key=lambda x: x["score"])
        
        return {
            "optimal_clusters": optimal["n_clusters"],
            "score": optimal["score"],
            "all_scores": scores,
            "method": method,
        }
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get clustering statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_clustering_operations": len(self.clustering_results),
            "total_models": len(self.models),
            "methods_used": {
                m.value: len([r for r in self.clustering_results if r.method == m])
                for m in ClusteringMethod
            },
            "last_result": self.clustering_results[-1].to_dict() if self.clustering_results else None,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "ClusteringMethod",
    "DistanceMetric",
    
    # Dataclasses
    "ClusteringResult",
    "ClusterProfile",
    
    # Classes
    "DataClusteringEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

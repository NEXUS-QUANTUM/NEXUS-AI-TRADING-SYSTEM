# trading/bots/hedge_bot/hedge_bot_concentration.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Concentration Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Concentration Module

This module provides comprehensive concentration risk analysis and
management capabilities for the NEXUS Hedge Bot system. It monitors
portfolio concentration, calculates concentration metrics, and
enforces concentration limits.

The module covers:
- Asset Concentration Analysis
- Sector Concentration Analysis
- Geographic Concentration Analysis
- Counterparty Concentration Analysis
- Herfindahl-Hirschman Index (HHI)
- Gini Coefficient
- Concentration Ratios
- Diversification Scoring
- Concentration Limits Enforcement
- Concentration Alerts
- Concentration Reporting
"""

import os
import sys
import json
import logging
import numpy as np
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================
# CONCENTRATION ENUMS
# ============================================================

class ConcentrationType(Enum):
    """Concentration types"""
    ASSET = "asset"
    SECTOR = "sector"
    GEOGRAPHIC = "geographic"
    COUNTERPARTY = "counterparty"
    ASSET_CLASS = "asset_class"
    CURRENCY = "currency"


class ConcentrationLevel(Enum):
    """Concentration levels"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConcentrationMetrics:
    """Concentration metrics"""
    hhi: float  # Herfindahl-Hirschman Index
    gini_coefficient: float
    concentration_ratio_5: float  # Top 5 concentration
    concentration_ratio_10: float  # Top 10 concentration
    diversification_score: float
    effective_number_of_assets: float
    entropy_index: float
    level: ConcentrationLevel
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "hhi": self.hhi,
            "gini_coefficient": self.gini_coefficient,
            "concentration_ratio_5": self.concentration_ratio_5,
            "concentration_ratio_10": self.concentration_ratio_10,
            "diversification_score": self.diversification_score,
            "effective_number_of_assets": self.effective_number_of_assets,
            "entropy_index": self.entropy_index,
            "level": self.level.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class ConcentrationAlert:
    """Concentration alert"""
    id: str
    type: ConcentrationType
    level: ConcentrationLevel
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "level": self.level.value,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
        }


# ============================================================
# CONCENTRATION ENGINE
# ============================================================

class ConcentrationEngine:
    """
    Comprehensive concentration analysis engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the concentration engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.hhi_thresholds = self.config.get("hhi_thresholds", {
            "low": 0.10,
            "moderate": 0.15,
            "high": 0.25,
        })
        self.gini_thresholds = self.config.get("gini_thresholds", {
            "low": 0.35,
            "moderate": 0.50,
            "high": 0.65,
        })
        self.diversification_target = self.config.get("diversification_target", 0.70)
        self.concentration_ratio_limit = self.config.get("concentration_ratio_limit", 0.45)
        
        # State
        self.metrics_cache: Dict[str, ConcentrationMetrics] = {}
        self.alerts: List[ConcentrationAlert] = {}
        
        logger.info("Concentration engine initialized")
    
    # ============================================================
    # HHI CALCULATION
    # ============================================================
    
    def calculate_hhi(self, weights: Dict[str, float]) -> float:
        """
        Calculate Herfindahl-Hirschman Index
        
        Args:
            weights: Asset weights (sum to 1)
            
        Returns:
            HHI value
        """
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 1.0
        
        normalized_weights = {k: v / total_weight for k, v in weights.items()}
        hhi = sum(w ** 2 for w in normalized_weights.values())
        return hhi
    
    def calculate_effective_assets(self, weights: Dict[str, float]) -> float:
        """
        Calculate effective number of assets
        
        Args:
            weights: Asset weights
            
        Returns:
            Effective number of assets
        """
        hhi = self.calculate_hhi(weights)
        return 1 / hhi if hhi > 0 else 0
    
    # ============================================================
    # GINI COEFFICIENT
    # ============================================================
    
    def calculate_gini(self, values: List[float]) -> float:
        """
        Calculate Gini coefficient
        
        Args:
            values: List of values
            
        Returns:
            Gini coefficient
        """
        if not values:
            return 1.0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        if n == 1:
            return 0.0
        
        # Calculate Gini
        sum_abs_diff = 0
        for i in range(n):
            for j in range(i + 1, n):
                sum_abs_diff += abs(sorted_values[i] - sorted_values[j])
        
        gini = (2 * sum_abs_diff) / (n ** 2 * np.mean(sorted_values))
        return gini
    
    # ============================================================
    # CONCENTRATION RATIOS
    # ============================================================
    
    def calculate_concentration_ratios(
        self,
        weights: Dict[str, float],
        n: int = 5
    ) -> Dict[str, float]:
        """
        Calculate concentration ratios
        
        Args:
            weights: Asset weights
            n: Number of assets
            
        Returns:
            Concentration ratios
        """
        sorted_weights = sorted(weights.values(), reverse=True)
        
        ratios = {}
        for i in [5, 10, 20]:
            if len(sorted_weights) >= i:
                ratios[f"cr_{i}"] = sum(sorted_weights[:i])
            else:
                ratios[f"cr_{i}"] = sum(sorted_weights)
        
        return ratios
    
    # ============================================================
    # ENTROPY INDEX
    # ============================================================
    
    def calculate_entropy(self, weights: Dict[str, float]) -> float:
        """
        Calculate entropy index
        
        Args:
            weights: Asset weights
            
        Returns:
            Entropy index
        """
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0
        
        normalized_weights = [w / total_weight for w in weights.values()]
        normalized_weights = [w for w in normalized_weights if w > 0]
        
        entropy = -sum(w * np.log(w) for w in normalized_weights)
        return entropy
    
    # ============================================================
    # DIVERSIFICATION SCORE
    # ============================================================
    
    def calculate_diversification_score(
        self,
        weights: Dict[str, float],
        correlation_matrix: Optional[np.ndarray] = None
    ) -> float:
        """
        Calculate diversification score
        
        Args:
            weights: Asset weights
            correlation_matrix: Correlation matrix
            
        Returns:
            Diversification score (0-1)
        """
        if not weights:
            return 0.0
        
        # Basic diversification based on HHI
        hhi = self.calculate_hhi(weights)
        hhi_score = 1 - hhi
        
        # Adjust for number of assets
        n = len(weights)
        n_score = min(n / 20, 1.0)  # 20 assets considered well-diversified
        
        # Adjust for correlation if available
        corr_score = 0.5
        if correlation_matrix is not None:
            n_assets = len(weights)
            if n_assets > 1:
                # Calculate average correlation
                upper_tri = correlation_matrix[np.triu_indices(n_assets, k=1)]
                avg_corr = np.mean(upper_tri) if len(upper_tri) > 0 else 0.5
                corr_score = 1 - avg_corr
        
        # Combined score
        score = 0.4 * hhi_score + 0.3 * n_score + 0.3 * corr_score
        return min(max(score, 0.0), 1.0)
    
    # ============================================================
    # CONCENTRATION ANALYSIS
    # ============================================================
    
    def analyze_concentration(
        self,
        weights: Dict[str, float],
        name: str = "portfolio",
        type: ConcentrationType = ConcentrationType.ASSET,
        correlation_matrix: Optional[np.ndarray] = None
    ) -> ConcentrationMetrics:
        """
        Analyze concentration for a set of assets
        
        Args:
            weights: Asset weights
            name: Portfolio name
            type: Concentration type
            correlation_matrix: Correlation matrix
            
        Returns:
            ConcentrationMetrics
        """
        # Calculate metrics
        hhi = self.calculate_hhi(weights)
        effective_assets = self.calculate_effective_assets(weights)
        gini = self.calculate_gini(list(weights.values()))
        ratios = self.calculate_concentration_ratios(weights)
        entropy = self.calculate_entropy(weights)
        div_score = self.calculate_diversification_score(weights, correlation_matrix)
        
        # Determine level
        if hhi <= self.hhi_thresholds["low"]:
            level = ConcentrationLevel.LOW
        elif hhi <= self.hhi_thresholds["moderate"]:
            level = ConcentrationLevel.MODERATE
        elif hhi <= self.hhi_thresholds["high"]:
            level = ConcentrationLevel.HIGH
        else:
            level = ConcentrationLevel.CRITICAL
        
        # Create metrics
        metrics = ConcentrationMetrics(
            hhi=hhi,
            gini_coefficient=gini,
            concentration_ratio_5=ratios.get("cr_5", 0),
            concentration_ratio_10=ratios.get("cr_10", 0),
            diversification_score=div_score,
            effective_number_of_assets=effective_assets,
            entropy_index=entropy,
            level=level,
            details={
                "name": name,
                "type": type.value,
                "n_assets": len(weights),
                "ratios": ratios,
                "top_assets": sorted(weights.items(), key=lambda x: x[1], reverse=True)[:10],
            }
        )
        
        # Cache
        cache_key = f"{name}_{type.value}"
        self.metrics_cache[cache_key] = metrics
        
        return metrics
    
    # ============================================================
    # SECTOR CONCENTRATION
    # ============================================================
    
    def analyze_sector_concentration(
        self,
        asset_sector_map: Dict[str, str],
        weights: Dict[str, float]
    ) -> ConcentrationMetrics:
        """
        Analyze sector concentration
        
        Args:
            asset_sector_map: Asset to sector mapping
            weights: Asset weights
            
        Returns:
            ConcentrationMetrics
        """
        # Aggregate weights by sector
        sector_weights = defaultdict(float)
        for asset, weight in weights.items():
            sector = asset_sector_map.get(asset, "other")
            sector_weights[sector] += weight
        
        return self.analyze_concentration(
            dict(sector_weights),
            name="sector_concentration",
            type=ConcentrationType.SECTOR,
        )
    
    # ============================================================
    # COUNTERPARTY CONCENTRATION
    # ============================================================
    
    def analyze_counterparty_concentration(
        self,
        counterparty_weights: Dict[str, float]
    ) -> ConcentrationMetrics:
        """
        Analyze counterparty concentration
        
        Args:
            counterparty_weights: Counterparty weights
            
        Returns:
            ConcentrationMetrics
        """
        return self.analyze_concentration(
            counterparty_weights,
            name="counterparty_concentration",
            type=ConcentrationType.COUNTERPARTY,
        )
    
    # ============================================================
    # CONCENTRATION LIMITS
    # ============================================================
    
    def check_concentration_limits(
        self,
        metrics: ConcentrationMetrics,
        limits: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Check concentration against limits
        
        Args:
            metrics: Concentration metrics
            limits: Concentration limits
            
        Returns:
            Check results
        """
        if limits is None:
            limits = {
                "hhi_max": self.hhi_thresholds["high"],
                "gini_max": self.gini_thresholds["high"],
                "cr_5_max": self.concentration_ratio_limit,
            }
        
        results = {
            "passed": True,
            "violations": [],
            "warnings": [],
        }
        
        # Check HHI
        if metrics.hhi > limits.get("hhi_max", 0.25):
            results["violations"].append({
                "metric": "hhi",
                "value": metrics.hhi,
                "limit": limits["hhi_max"],
            })
            results["passed"] = False
        elif metrics.hhi > limits.get("hhi_max", 0.25) * 0.8:
            results["warnings"].append({
                "metric": "hhi",
                "value": metrics.hhi,
                "limit": limits["hhi_max"],
                "utilization": metrics.hhi / limits["hhi_max"],
            })
        
        # Check Gini
        if metrics.gini_coefficient > limits.get("gini_max", 0.65):
            results["violations"].append({
                "metric": "gini",
                "value": metrics.gini_coefficient,
                "limit": limits["gini_max"],
            })
            results["passed"] = False
        elif metrics.gini_coefficient > limits.get("gini_max", 0.65) * 0.8:
            results["warnings"].append({
                "metric": "gini",
                "value": metrics.gini_coefficient,
                "limit": limits["gini_max"],
            })
        
        # Check concentration ratio
        if metrics.concentration_ratio_5 > limits.get("cr_5_max", 0.45):
            results["violations"].append({
                "metric": "cr_5",
                "value": metrics.concentration_ratio_5,
                "limit": limits["cr_5_max"],
            })
            results["passed"] = False
        elif metrics.concentration_ratio_5 > limits.get("cr_5_max", 0.45) * 0.8:
            results["warnings"].append({
                "metric": "cr_5",
                "value": metrics.concentration_ratio_5,
                "limit": limits["cr_5_max"],
            })
        
        return results
    
    # ============================================================
    # ALERT MANAGEMENT
    # ============================================================
    
    def create_alert(
        self,
        type: ConcentrationType,
        level: ConcentrationLevel,
        metric: str,
        value: float,
        threshold: float,
        message: str
    ) -> ConcentrationAlert:
        """
        Create a concentration alert
        
        Args:
            type: Concentration type
            level: Concentration level
            metric: Metric name
            value: Metric value
            threshold: Threshold value
            message: Alert message
            
        Returns:
            ConcentrationAlert
        """
        alert = ConcentrationAlert(
            id=f"conc_{int(time.time())}_{len(self.alerts)}",
            type=type,
            level=level,
            metric=metric,
            value=value,
            threshold=threshold,
            message=message,
            timestamp=datetime.now(),
        )
        
        self.alerts.append(alert)
        logger.warning(f"Concentration alert: {message}")
        return alert
    
    def check_and_alert(
        self,
        metrics: ConcentrationMetrics,
        limits: Optional[Dict[str, float]] = None
    ) -> List[ConcentrationAlert]:
        """
        Check concentration and create alerts if needed
        
        Args:
            metrics: Concentration metrics
            limits: Concentration limits
            
        Returns:
            List of alerts
        """
        alerts = []
        
        # Get limits
        if limits is None:
            limits = {}
        hhi_max = limits.get("hhi_max", self.hhi_thresholds["high"])
        gini_max = limits.get("gini_max", self.gini_thresholds["high"])
        
        # Check HHI
        if metrics.hhi > hhi_max:
            alert = self.create_alert(
                type=ConcentrationType.ASSET,
                level=metrics.level,
                metric="hhi",
                value=metrics.hhi,
                threshold=hhi_max,
                message=f"HHI concentration critical: {metrics.hhi:.3f} > {hhi_max:.3f}",
            )
            alerts.append(alert)
        
        # Check Gini
        if metrics.gini_coefficient > gini_max:
            alert = self.create_alert(
                type=ConcentrationType.ASSET,
                level=metrics.level,
                metric="gini",
                value=metrics.gini_coefficient,
                threshold=gini_max,
                message=f"Gini concentration high: {metrics.gini_coefficient:.3f} > {gini_max:.3f}",
            )
            alerts.append(alert)
        
        return alerts
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def generate_report(self, metrics: ConcentrationMetrics) -> Dict[str, Any]:
        """
        Generate concentration report
        
        Args:
            metrics: Concentration metrics
            
        Returns:
            Report data
        """
        return {
            "summary": {
                "hhi": metrics.hhi,
                "gini_coefficient": metrics.gini_coefficient,
                "diversification_score": metrics.diversification_score,
                "level": metrics.level.value,
                "effective_assets": metrics.effective_number_of_assets,
            },
            "concentration_ratios": {
                "cr_5": metrics.concentration_ratio_5,
                "cr_10": metrics.concentration_ratio_10,
            },
            "top_assets": metrics.details.get("top_assets", []),
            "risk_level": metrics.level.value,
            "recommendations": self._generate_recommendations(metrics),
        }
    
    def _generate_recommendations(self, metrics: ConcentrationMetrics) -> List[str]:
        """
        Generate recommendations based on concentration metrics
        
        Args:
            metrics: Concentration metrics
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if metrics.hhi > 0.2:
            recommendations.append("Consider diversifying portfolio to reduce concentration")
        
        if metrics.gini_coefficient > 0.5:
            recommendations.append("Consider rebalancing to reduce inequality in weights")
        
        if metrics.concentration_ratio_5 > 0.4:
            recommendations.append("Reduce exposure to top 5 assets")
        
        if metrics.diversification_score < 0.5:
            recommendations.append("Increase diversification by adding more assets")
        
        return recommendations
    
    # ============================================================
    # GETTER METHODS
    # ============================================================
    
    def get_metrics(self, name: str, type: ConcentrationType) -> Optional[ConcentrationMetrics]:
        """
        Get cached concentration metrics
        
        Args:
            name: Portfolio name
            type: Concentration type
            
        Returns:
            ConcentrationMetrics or None
        """
        cache_key = f"{name}_{type.value}"
        return self.metrics_cache.get(cache_key)
    
    def get_alerts(
        self,
        type: Optional[ConcentrationType] = None,
        level: Optional[ConcentrationLevel] = None
    ) -> List[ConcentrationAlert]:
        """
        Get concentration alerts
        
        Args:
            type: Filter by type
            level: Filter by level
            
        Returns:
            List of alerts
        """
        alerts = list(self.alerts)
        
        if type:
            alerts = [a for a in alerts if a.type == type]
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        return alerts
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get engine statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_metrics": len(self.metrics_cache),
            "total_alerts": len(self.alerts),
            "active_alerts": len([a for a in self.alerts if not a.resolved]),
            "hhi_thresholds": self.hhi_thresholds,
            "gini_thresholds": self.gini_thresholds,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "ConcentrationType",
    "ConcentrationLevel",
    
    # Dataclasses
    "ConcentrationMetrics",
    "ConcentrationAlert",
    
    # Classes
    "ConcentrationEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

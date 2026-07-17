# trading/bots/ai_bot/ai_bot_feature_engine.py
# NEXUS AI TRADING SYSTEM - Feature Engineering Engine
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Feature Engineering Engine for NEXUS AI Trading Bot.
Provides comprehensive feature engineering capabilities including:
- Technical indicator calculation
- Feature extraction and transformation
- Feature selection and importance ranking
- Feature scaling and normalization
- Target encoding and feature engineering
- Automated feature engineering
- Feature store integration
- Real-time feature computation
- Feature versioning and lineage
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.feature_selection import (
    SelectKBest,
    mutual_info_regression,
    f_regression,
    RFE,
)
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.ensemble import RandomForestRegressor

# NEXUS Imports
from trading.bots.ai_bot.indicators.indicator_factory import IndicatorFactory
from trading.bots.ai_bot.data.data_processor import DataProcessor
from trading.bots.ai_bot.data.data_storage import DataStorage
from trading.bots.ai_bot.config.bot_configs import BotConfig
from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import CacheManager

logger = get_logger("nexus.trading.bot.feature_engine")


# ============================================================================
# Enums & Constants
# ============================================================================

class FeatureType(str, Enum):
    """Types of features."""
    PRICE = "price"
    VOLUME = "volume"
    TECHNICAL = "technical"
    STATISTICAL = "statistical"
    SENTIMENT = "sentiment"
    ONCHAIN = "onchain"
    MACRO = "macro"
    DERIVED = "derived"
    CATEGORICAL = "categorical"
    TEXT = "text"
    IMAGE = "image"
    TIME = "time"


class FeatureTransform(str, Enum):
    """Feature transformation types."""
    NONE = "none"
    STANDARDIZE = "standardize"
    NORMALIZE = "normalize"
    ROBUST = "robust"
    LOG = "log"
    SQRT = "sqrt"
    BOX_COX = "box_cox"
    YEO_JOHNSON = "yeo_johnson"
    PCA = "pca"
    DIFFERENCE = "difference"
    PERCENT_CHANGE = "percent_change"
    RATIO = "ratio"


class FeatureSelection(str, Enum):
    """Feature selection methods."""
    NONE = "none"
    VARIANCE_THRESHOLD = "variance_threshold"
    SELECT_K_BEST = "select_k_best"
    RFE = "rfe"
    RANDOM_FOREST = "random_forest"
    MUTUAL_INFO = "mutual_info"
    CORRELATION = "correlation"
    PCA = "pca"


@dataclass
class FeatureDefinition:
    """Feature definition."""
    name: str
    feature_type: FeatureType
    source: str
    transform: FeatureTransform
    window: Optional[int] = None
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    is_target: bool = False
    is_required: bool = True


@dataclass
class FeatureSet:
    """Feature set for training/prediction."""
    features: pd.DataFrame
    targets: Optional[pd.DataFrame] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"


@dataclass
class FeatureImportance:
    """Feature importance data."""
    feature_name: str
    importance: float
    rank: int
    method: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# Feature Engineering Engine
# ============================================================================

class FeatureEngineeringEngine:
    """
    Advanced Feature Engineering Engine for NEXUS AI Trading Bot.
    """

    def __init__(
        self,
        config: BotConfig,
        data_processor: DataProcessor,
        data_storage: DataStorage,
        cache_manager: CacheManager,
        indicator_factory: IndicatorFactory,
    ):
        """
        Initialize feature engineering engine.

        Args:
            config: Bot configuration
            data_processor: Data processor instance
            data_storage: Data storage instance
            cache_manager: Cache manager instance
            indicator_factory: Indicator factory instance
        """
        self.config = config
        self.data_processor = data_processor
        self.data_storage = data_storage
        self.cache_manager = cache_manager
        self.indicator_factory = indicator_factory

        # Feature registry
        self._feature_definitions: Dict[str, FeatureDefinition] = {}
        self._feature_cache: Dict[str, pd.DataFrame] = {}
        self._feature_importance: Dict[str, List[FeatureImportance]] = {}

        # Transformers
        self._scalers: Dict[str, Any] = {}
        self._pca: Optional[PCA] = None
        self._feature_selector: Optional[Any] = None

        # Performance metrics
        self._performance = {
            "features_computed": 0,
            "features_selected": 0,
            "feature_importance_calculated": 0,
            "average_compute_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Register default features
        self._register_default_features()

        logger.info(
            "FeatureEngineeringEngine initialized",
            extra={
                "features_registered": len(self._feature_definitions),
                "cache_enabled": cache_manager is not None,
            }
        )

    # -----------------------------------------------------------------------
    # Feature Registration
    # -----------------------------------------------------------------------

    def register_feature(self, definition: FeatureDefinition) -> bool:
        """
        Register a new feature.

        Args:
            definition: Feature definition

        Returns:
            True if registered successfully
        """
        if definition.name in self._feature_definitions:
            logger.warning(f"Feature {definition.name} already registered")
            return False

        self._feature_definitions[definition.name] = definition
        logger.info(f"Feature registered: {definition.name}")
        return True

    def register_features(self, definitions: List[FeatureDefinition]) -> int:
        """
        Register multiple features.

        Args:
            definitions: List of feature definitions

        Returns:
            Number of features registered
        """
        count = 0
        for definition in definitions:
            if self.register_feature(definition):
                count += 1
        return count

    def unregister_feature(self, name: str) -> bool:
        """
        Unregister a feature.

        Args:
            name: Feature name

        Returns:
            True if unregistered successfully
        """
        if name not in self._feature_definitions:
            logger.warning(f"Feature {name} not found")
            return False

        del self._feature_definitions[name]
        self._feature_cache.pop(name, None)
        self._feature_importance.pop(name, None)
        logger.info(f"Feature unregistered: {name}")
        return True

    # -----------------------------------------------------------------------
    # Feature Computation
    # -----------------------------------------------------------------------

    async def compute_features(
        self,
        data: pd.DataFrame,
        feature_names: Optional[List[str]] = None,
        use_cache: bool = True,
        cache_ttl: int = 300,
    ) -> pd.DataFrame:
        """
        Compute features from data.

        Args:
            data: Input data
            feature_names: List of features to compute (all if None)
            use_cache: Use cache
            cache_ttl: Cache TTL in seconds

        Returns:
            DataFrame with features
        """
        start_time = time.time()

        if feature_names is None:
            feature_names = list(self._feature_definitions.keys())

        # Check cache
        cache_key = self._build_cache_key(data, feature_names)
        if use_cache and cache_key in self._feature_cache:
            self._performance["cache_hits"] += 1
            return self._feature_cache[cache_key]

        self._performance["cache_misses"] += 1

        # Compute features
        result = pd.DataFrame(index=data.index)

        for name in feature_names:
            if name not in self._feature_definitions:
                logger.warning(f"Feature {name} not registered")
                continue

            definition = self._feature_definitions[name]
            feature_data = await self._compute_feature(data, definition)

            if feature_data is not None:
                result[name] = feature_data

        # Apply transformations
        result = await self._apply_transformations(result)

        # Cache result
        if use_cache and self.cache_manager:
            self._feature_cache[cache_key] = result
            self.cache_manager.set(cache_key, result, ttl=cache_ttl)

        # Update performance
        elapsed_ms = (time.time() - start_time) * 1000
        self._performance["features_computed"] += len(feature_names)
        self._performance["average_compute_time_ms"] = (
            (self._performance["average_compute_time_ms"] *
             (self._performance["features_computed"] - 1) +
             elapsed_ms) / self._performance["features_computed"]
        )

        return result

    async def _compute_feature(
        self,
        data: pd.DataFrame,
        definition: FeatureDefinition,
    ) -> Optional[pd.Series]:
        """
        Compute a single feature.

        Args:
            data: Input data
            definition: Feature definition

        Returns:
            Feature series or None
        """
        try:
            if definition.feature_type == FeatureType.TECHNICAL:
                return await self._compute_technical_feature(data, definition)
            elif definition.feature_type == FeatureType.STATISTICAL:
                return await self._compute_statistical_feature(data, definition)
            elif definition.feature_type == FeatureType.DERIVED:
                return await self._compute_derived_feature(data, definition)
            elif definition.feature_type == FeatureType.TIME:
                return await self._compute_time_feature(data, definition)
            else:
                return await self._compute_generic_feature(data, definition)

        except Exception as e:
            logger.error(f"Error computing feature {definition.name}: {e}")
            return None

    async def _compute_technical_feature(
        self,
        data: pd.DataFrame,
        definition: FeatureDefinition,
    ) -> Optional[pd.Series]:
        """
        Compute technical indicator feature.

        Args:
            data: Input data
            definition: Feature definition

        Returns:
            Feature series or None
        """
        try:
            indicator = self.indicator_factory.create_indicator(
                name=definition.source,
                params=definition.params,
            )

            if indicator is None:
                return None

            result = await indicator.calculate(data)
            return result

        except Exception as e:
            logger.error(f"Error computing technical feature: {e}")
            return None

    async def _compute_statistical_feature(
        self,
        data: pd.DataFrame,
        definition: FeatureDefinition,
    ) -> Optional[pd.Series]:
        """
        Compute statistical feature.

        Args:
            data: Input data
            definition: Feature definition

        Returns:
            Feature series or None
        """
        try:
            source = definition.source
            window = definition.window or 20
            params = definition.params

            if source not in data.columns:
                return None

            values = data[source]

            if params.get("method") == "mean":
                result = values.rolling(window).mean()
            elif params.get("method") == "std":
                result = values.rolling(window).std()
            elif params.get("method") == "skew":
                result = values.rolling(window).skew()
            elif params.get("method") == "kurt":
                result = values.rolling(window).kurt()
            elif params.get("method") == "quantile":
                q = params.get("quantile", 0.5)
                result = values.rolling(window).quantile(q)
            else:
                result = values.rolling(window).mean()

            return result

        except Exception as e:
            logger.error(f"Error computing statistical feature: {e}")
            return None

    async def _compute_derived_feature(
        self,
        data: pd.DataFrame,
        definition: FeatureDefinition,
    ) -> Optional[pd.Series]:
        """
        Compute derived feature.

        Args:
            data: Input data
            definition: Feature definition

        Returns:
            Feature series or None
        """
        try:
            source = definition.source
            params = definition.params

            if source not in data.columns:
                return None

            values = data[source]

            if params.get("method") == "difference":
                result = values.diff()
            elif params.get("method") == "percent_change":
                result = values.pct_change()
            elif params.get("method") == "ratio":
                ratio_source = params.get("ratio_source")
                if ratio_source and ratio_source in data.columns:
                    result = values / data[ratio_source]
                else:
                    return None
            elif params.get("method") == "lag":
                periods = params.get("periods", 1)
                result = values.shift(periods)
            else:
                return None

            return result

        except Exception as e:
            logger.error(f"Error computing derived feature: {e}")
            return None

    async def _compute_time_feature(
        self,
        data: pd.DataFrame,
        definition: FeatureDefinition,
    ) -> Optional[pd.Series]:
        """
        Compute time-based feature.

        Args:
            data: Input data
            definition: Feature definition

        Returns:
            Feature series or None
        """
        try:
            params = definition.params
            index = data.index

            if params.get("method") == "hour":
                return pd.Series(index.hour, index=index)
            elif params.get("method") == "day_of_week":
                return pd.Series(index.dayofweek, index=index)
            elif params.get("method") == "month":
                return pd.Series(index.month, index=index)
            elif params.get("method") == "quarter":
                return pd.Series(index.quarter, index=index)
            elif params.get("method") == "year":
                return pd.Series(index.year, index=index)
            elif params.get("method") == "day_of_year":
                return pd.Series(index.dayofyear, index=index)
            else:
                return None

        except Exception as e:
            logger.error(f"Error computing time feature: {e}")
            return None

    async def _compute_generic_feature(
        self,
        data: pd.DataFrame,
        definition: FeatureDefinition,
    ) -> Optional[pd.Series]:
        """
        Compute generic feature.

        Args:
            data: Input data
            definition: Feature definition

        Returns:
            Feature series or None
        """
        try:
            source = definition.source

            if source not in data.columns:
                return None

            return data[source]

        except Exception as e:
            logger.error(f"Error computing generic feature: {e}")
            return None

    # -----------------------------------------------------------------------
    # Feature Transformations
    # -----------------------------------------------------------------------

    async def _apply_transformations(
        self,
        features: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Apply transformations to features.

        Args:
            features: Feature DataFrame

        Returns:
            Transformed features
        """
        result = features.copy()

        for name in result.columns:
            if name not in self._feature_definitions:
                continue

            definition = self._feature_definitions[name]
            transform = definition.transform

            if transform == FeatureTransform.NONE:
                continue

            try:
                if transform == FeatureTransform.STANDARDIZE:
                    result[name] = await self._standardize(result[name])
                elif transform == FeatureTransform.NORMALIZE:
                    result[name] = await self._normalize(result[name])
                elif transform == FeatureTransform.ROBUST:
                    result[name] = await self._robust_scale(result[name])
                elif transform == FeatureTransform.LOG:
                    result[name] = np.log1p(result[name])
                elif transform == FeatureTransform.SQRT:
                    result[name] = np.sqrt(result[name])
                elif transform == FeatureTransform.DIFFERENCE:
                    result[name] = result[name].diff()
                elif transform == FeatureTransform.PERCENT_CHANGE:
                    result[name] = result[name].pct_change()
                else:
                    continue

            except Exception as e:
                logger.error(f"Error applying transform {transform} to {name}: {e}")

        return result

    async def _standardize(self, series: pd.Series) -> pd.Series:
        """Standardize series."""
        scaler = StandardScaler()
        values = series.values.reshape(-1, 1)
        scaled = scaler.fit_transform(values)
        return pd.Series(scaled.flatten(), index=series.index)

    async def _normalize(self, series: pd.Series) -> pd.Series:
        """Normalize series."""
        scaler = MinMaxScaler()
        values = series.values.reshape(-1, 1)
        scaled = scaler.fit_transform(values)
        return pd.Series(scaled.flatten(), index=series.index)

    async def _robust_scale(self, series: pd.Series) -> pd.Series:
        """Robust scale series."""
        scaler = RobustScaler()
        values = series.values.reshape(-1, 1)
        scaled = scaler.fit_transform(values)
        return pd.Series(scaled.flatten(), index=series.index)

    # -----------------------------------------------------------------------
    # Feature Selection
    # -----------------------------------------------------------------------

    async def select_features(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        method: FeatureSelection = FeatureSelection.RANDOM_FOREST,
        k: int = 50,
    ) -> pd.DataFrame:
        """
        Select important features.

        Args:
            features: Feature DataFrame
            targets: Target values
            method: Selection method
            k: Number of features to select

        Returns:
            Selected features DataFrame
        """
        start_time = time.time()

        if method == FeatureSelection.NONE:
            return features

        try:
            if method == FeatureSelection.VARIANCE_THRESHOLD:
                selected = await self._select_by_variance(features)
            elif method == FeatureSelection.SELECT_K_BEST:
                selected = await self._select_k_best(features, targets, k)
            elif method == FeatureSelection.RFE:
                selected = await self._select_rfe(features, targets, k)
            elif method == FeatureSelection.RANDOM_FOREST:
                selected = await self._select_random_forest(features, targets, k)
            elif method == FeatureSelection.MUTUAL_INFO:
                selected = await self._select_mutual_info(features, targets, k)
            elif method == FeatureSelection.CORRELATION:
                selected = await self._select_by_correlation(features, targets)
            elif method == FeatureSelection.PCA:
                selected = await self._select_pca(features, k)
            else:
                return features

            self._performance["features_selected"] += len(selected.columns)
            return selected

        except Exception as e:
            logger.error(f"Error selecting features: {e}")
            return features

    async def _select_by_variance(
        self,
        features: pd.DataFrame,
        threshold: float = 0.01,
    ) -> pd.DataFrame:
        """Select features by variance threshold."""
        variances = features.var()
        selected_cols = variances[variances > threshold].index.tolist()
        return features[selected_cols]

    async def _select_k_best(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        k: int,
    ) -> pd.DataFrame:
        """Select top K features using F-test."""
        selector = SelectKBest(score_func=f_regression, k=min(k, len(features.columns)))
        selector.fit(features, targets)

        # Get selected feature indices
        selected_indices = selector.get_support(indices=True)
        selected_cols = features.columns[selected_indices].tolist()

        # Store feature scores
        scores = selector.scores_
        for i, col in enumerate(features.columns):
            if col in selected_cols:
                importance = FeatureImportance(
                    feature_name=col,
                    importance=float(scores[i]),
                    rank=i + 1,
                    method="select_k_best",
                )
                self._add_feature_importance(importance)

        return features[selected_cols]

    async def _select_rfe(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        k: int,
    ) -> pd.DataFrame:
        """Select features using Recursive Feature Elimination."""
        estimator = RandomForestRegressor(n_estimators=100, random_state=42)
        selector = RFE(estimator, n_features_to_select=min(k, len(features.columns)))
        selector.fit(features, targets)

        selected_cols = features.columns[selector.support_].tolist()

        # Store feature importance
        for i, col in enumerate(features.columns):
            if col in selected_cols:
                importance = FeatureImportance(
                    feature_name=col,
                    importance=float(selector.ranking_[i]),
                    rank=i + 1,
                    method="rfe",
                )
                self._add_feature_importance(importance)

        return features[selected_cols]

    async def _select_random_forest(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        k: int,
    ) -> pd.DataFrame:
        """Select features using Random Forest importance."""
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(features, targets)

        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]

        selected_cols = [features.columns[i] for i in indices[:k]]

        # Store feature importance
        for i, col in enumerate(selected_cols):
            importance = FeatureImportance(
                feature_name=col,
                importance=float(importances[indices[i]]),
                rank=i + 1,
                method="random_forest",
            )
            self._add_feature_importance(importance)

        return features[selected_cols]

    async def _select_mutual_info(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        k: int,
    ) -> pd.DataFrame:
        """Select features using mutual information."""
        selector = SelectKBest(
            score_func=mutual_info_regression,
            k=min(k, len(features.columns)),
        )
        selector.fit(features, targets)

        selected_indices = selector.get_support(indices=True)
        selected_cols = features.columns[selected_indices].tolist()

        # Store feature importance
        scores = selector.scores_
        for i, col in enumerate(features.columns):
            if col in selected_cols:
                importance = FeatureImportance(
                    feature_name=col,
                    importance=float(scores[i]),
                    rank=i + 1,
                    method="mutual_info",
                )
                self._add_feature_importance(importance)

        return features[selected_cols]

    async def _select_by_correlation(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        threshold: float = 0.1,
    ) -> pd.DataFrame:
        """Select features by correlation with target."""
        correlations = features.corrwith(targets).abs()
        selected_cols = correlations[correlations > threshold].index.tolist()

        return features[selected_cols]

    async def _select_pca(
        self,
        features: pd.DataFrame,
        n_components: int,
    ) -> pd.DataFrame:
        """Select features using PCA."""
        pca = PCA(n_components=min(n_components, len(features.columns)))
        pca.fit(features)

        # Get component loadings
        loadings = pca.components_.T
        component_importance = np.abs(loadings).sum(axis=1)

        selected_indices = np.argsort(component_importance)[::-1][:n_components]
        selected_cols = features.columns[selected_indices].tolist()

        # Store feature importance
        for i, col in enumerate(selected_cols):
            importance = FeatureImportance(
                feature_name=col,
                importance=float(component_importance[selected_indices[i]]),
                rank=i + 1,
                method="pca",
            )
            self._add_feature_importance(importance)

        return features[selected_cols]

    # -----------------------------------------------------------------------
    # Feature Importance
    # -----------------------------------------------------------------------

    async def calculate_feature_importance(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        method: str = "random_forest",
    ) -> List[FeatureImportance]:
        """
        Calculate feature importance.

        Args:
            features: Feature DataFrame
            targets: Target values
            method: Importance method

        Returns:
            List of FeatureImportance
        """
        try:
            if method == "random_forest":
                importances = await self._calculate_rf_importance(features, targets)
            elif method == "mutual_info":
                importances = await self._calculate_mi_importance(features, targets)
            elif method == "correlation":
                importances = await self._calculate_correlation_importance(features, targets)
            else:
                return []

            self._performance["feature_importance_calculated"] += 1

            # Store importance
            for importance in importances:
                self._add_feature_importance(importance)

            return importances

        except Exception as e:
            logger.error(f"Error calculating feature importance: {e}")
            return []

    async def _calculate_rf_importance(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
    ) -> List[FeatureImportance]:
        """Calculate Random Forest importance."""
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(features, targets)

        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]

        results = []
        for i, idx in enumerate(indices):
            results.append(FeatureImportance(
                feature_name=features.columns[idx],
                importance=float(importances[idx]),
                rank=i + 1,
                method="random_forest",
            ))

        return results

    async def _calculate_mi_importance(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
    ) -> List[FeatureImportance]:
        """Calculate mutual information importance."""
        scores = mutual_info_regression(features, targets)
        indices = np.argsort(scores)[::-1]

        results = []
        for i, idx in enumerate(indices):
            results.append(FeatureImportance(
                feature_name=features.columns[idx],
                importance=float(scores[idx]),
                rank=i + 1,
                method="mutual_info",
            ))

        return results

    async def _calculate_correlation_importance(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
    ) -> List[FeatureImportance]:
        """Calculate correlation-based importance."""
        correlations = features.corrwith(targets).abs()
        sorted_corr = correlations.sort_values(ascending=False)

        results = []
        for i, (name, corr) in enumerate(sorted_corr.items()):
            results.append(FeatureImportance(
                feature_name=name,
                importance=float(corr),
                rank=i + 1,
                method="correlation",
            ))

        return results

    def _add_feature_importance(self, importance: FeatureImportance) -> None:
        """Add feature importance to history."""
        if importance.feature_name not in self._feature_importance:
            self._feature_importance[importance.feature_name] = []

        self._feature_importance[importance.feature_name].append(importance)

        # Keep last 100 entries
        if len(self._feature_importance[importance.feature_name]) > 100:
            self._feature_importance[importance.feature_name] = (
                self._feature_importance[importance.feature_name][-100:]
            )

    # -----------------------------------------------------------------------
    # Feature Store Integration
    # -----------------------------------------------------------------------

    async def save_feature_set(
        self,
        feature_set: FeatureSet,
        name: str,
        version: str = "1.0.0",
    ) -> bool:
        """
        Save feature set to store.

        Args:
            feature_set: FeatureSet to save
            name: Feature set name
            version: Version

        Returns:
            True if saved successfully
        """
        try:
            data = {
                "features": feature_set.features.to_dict(),
                "targets": feature_set.targets.to_dict() if feature_set.targets is not None else None,
                "metadata": feature_set.metadata,
                "timestamp": feature_set.timestamp.isoformat(),
                "version": version,
                "columns": feature_set.features.columns.tolist(),
            }

            key = f"feature_set:{name}:{version}"
            success = await self.data_storage.save_data(key, data)

            if success:
                logger.info(f"Feature set saved: {name} v{version}")
            return success

        except Exception as e:
            logger.error(f"Error saving feature set: {e}")
            return False

    async def load_feature_set(
        self,
        name: str,
        version: str = "latest",
    ) -> Optional[FeatureSet]:
        """
        Load feature set from store.

        Args:
            name: Feature set name
            version: Version

        Returns:
            FeatureSet or None
        """
        try:
            if version == "latest":
                # Get latest version
                versions = await self._get_feature_set_versions(name)
                if not versions:
                    return None
                version = versions[-1]

            key = f"feature_set:{name}:{version}"
            data = await self.data_storage.load_data(key)

            if not data:
                return None

            features = pd.DataFrame(data["features"])
            targets = pd.DataFrame(data["targets"]) if data["targets"] else None

            return FeatureSet(
                features=features,
                targets=targets,
                metadata=data.get("metadata", {}),
                timestamp=datetime.fromisoformat(data["timestamp"]),
                version=data.get("version", "1.0.0"),
            )

        except Exception as e:
            logger.error(f"Error loading feature set: {e}")
            return None

    async def _get_feature_set_versions(self, name: str) -> List[str]:
        """Get available versions for a feature set."""
        try:
            pattern = f"feature_set:{name}:*"
            keys = await self.data_storage.list_keys(pattern)
            versions = [key.split(":")[-1] for key in keys]
            return sorted(versions)
        except Exception:
            return []

    # -----------------------------------------------------------------------
    # Feature Pipeline
    # -----------------------------------------------------------------------

    async def create_feature_pipeline(
        self,
        data: pd.DataFrame,
        feature_names: Optional[List[str]] = None,
        target_column: Optional[str] = None,
        target_horizon: int = 1,
    ) -> FeatureSet:
        """
        Create a complete feature pipeline.

        Args:
            data: Input data
            feature_names: List of features to compute
            target_column: Target column name
            target_horizon: Target horizon in steps

        Returns:
            FeatureSet
        """
        try:
            # Compute features
            features = await self.compute_features(data, feature_names)

            # Create targets
            targets = None
            if target_column and target_column in data.columns:
                targets = data[target_column].shift(-target_horizon)
                targets = targets.dropna()

                # Align features with targets
                features = features.loc[targets.index]

            # Create feature set
            feature_set = FeatureSet(
                features=features,
                targets=targets if targets is not None else None,
                metadata={
                    "num_features": len(features.columns),
                    "num_samples": len(features),
                    "feature_names": features.columns.tolist(),
                    "target_column": target_column,
                    "target_horizon": target_horizon,
                },
            )

            return feature_set

        except Exception as e:
            logger.error(f"Error creating feature pipeline: {e}")
            return FeatureSet(features=pd.DataFrame())

    # -----------------------------------------------------------------------
    # Default Features
    # -----------------------------------------------------------------------

    def _register_default_features(self) -> None:
        """Register default features."""
        # Price features
        self.register_feature(FeatureDefinition(
            name="open",
            feature_type=FeatureType.PRICE,
            source="open",
            transform=FeatureTransform.NONE,
            description="Opening price",
        ))
        self.register_feature(FeatureDefinition(
            name="high",
            feature_type=FeatureType.PRICE,
            source="high",
            transform=FeatureTransform.NONE,
            description="High price",
        ))
        self.register_feature(FeatureDefinition(
            name="low",
            feature_type=FeatureType.PRICE,
            source="low",
            transform=FeatureTransform.NONE,
            description="Low price",
        ))
        self.register_feature(FeatureDefinition(
            name="close",
            feature_type=FeatureType.PRICE,
            source="close",
            transform=FeatureTransform.NONE,
            description="Closing price",
        ))
        self.register_feature(FeatureDefinition(
            name="volume",
            feature_type=FeatureType.VOLUME,
            source="volume",
            transform=FeatureTransform.NONE,
            description="Volume",
        ))

        # Technical features
        self.register_feature(FeatureDefinition(
            name="rsi",
            feature_type=FeatureType.TECHNICAL,
            source="rsi",
            transform=FeatureTransform.NORMALIZE,
            params={"period": 14},
            description="Relative Strength Index",
        ))
        self.register_feature(FeatureDefinition(
            name="macd",
            feature_type=FeatureType.TECHNICAL,
            source="macd",
            transform=FeatureTransform.STANDARDIZE,
            params={"fast": 12, "slow": 26, "signal": 9},
            description="MACD",
        ))
        self.register_feature(FeatureDefinition(
            name="macd_signal",
            feature_type=FeatureType.TECHNICAL,
            source="macd_signal",
            transform=FeatureTransform.STANDARDIZE,
            params={"fast": 12, "slow": 26, "signal": 9},
            description="MACD Signal",
        ))
        self.register_feature(FeatureDefinition(
            name="macd_histogram",
            feature_type=FeatureType.TECHNICAL,
            source="macd_histogram",
            transform=FeatureTransform.STANDARDIZE,
            params={"fast": 12, "slow": 26, "signal": 9},
            description="MACD Histogram",
        ))
        self.register_feature(FeatureDefinition(
            name="bb_upper",
            feature_type=FeatureType.TECHNICAL,
            source="bb_upper",
            transform=FeatureTransform.NORMALIZE,
            params={"period": 20, "std": 2},
            description="Bollinger Bands Upper",
        ))
        self.register_feature(FeatureDefinition(
            name="bb_middle",
            feature_type=FeatureType.TECHNICAL,
            source="bb_middle",
            transform=FeatureTransform.NORMALIZE,
            params={"period": 20, "std": 2},
            description="Bollinger Bands Middle",
        ))
        self.register_feature(FeatureDefinition(
            name="bb_lower",
            feature_type=FeatureType.TECHNICAL,
            source="bb_lower",
            transform=FeatureTransform.NORMALIZE,
            params={"period": 20, "std": 2},
            description="Bollinger Bands Lower",
        ))
        self.register_feature(FeatureDefinition(
            name="bb_width",
            feature_type=FeatureType.TECHNICAL,
            source="bb_width",
            transform=FeatureTransform.NORMALIZE,
            params={"period": 20, "std": 2},
            description="Bollinger Bands Width",
        ))
        self.register_feature(FeatureDefinition(
            name="adx",
            feature_type=FeatureType.TECHNICAL,
            source="adx",
            transform=FeatureTransform.NORMALIZE,
            params={"period": 14},
            description="ADX",
        ))
        self.register_feature(FeatureDefinition(
            name="obv",
            feature_type=FeatureType.TECHNICAL,
            source="obv",
            transform=FeatureTransform.STANDARDIZE,
            params={"period": 20},
            description="On-Balance Volume",
        ))

        # Statistical features
        self.register_feature(FeatureDefinition(
            name="return_1",
            feature_type=FeatureType.STATISTICAL,
            source="close",
            transform=FeatureTransform.NONE,
            window=1,
            params={"method": "percent_change"},
            description="1-period return",
        ))
        self.register_feature(FeatureDefinition(
            name="return_5",
            feature_type=FeatureType.STATISTICAL,
            source="close",
            transform=FeatureTransform.NONE,
            window=5,
            params={"method": "percent_change"},
            description="5-period return",
        ))
        self.register_feature(FeatureDefinition(
            name="return_10",
            feature_type=FeatureType.STATISTICAL,
            source="close",
            transform=FeatureTransform.NONE,
            window=10,
            params={"method": "percent_change"},
            description="10-period return",
        ))
        self.register_feature(FeatureDefinition(
            name="return_20",
            feature_type=FeatureType.STATISTICAL,
            source="close",
            transform=FeatureTransform.NONE,
            window=20,
            params={"method": "percent_change"},
            description="20-period return",
        ))

        # Derived features
        self.register_feature(FeatureDefinition(
            name="price_volume_ratio",
            feature_type=FeatureType.DERIVED,
            source="close",
            transform=FeatureTransform.NONE,
            params={"method": "ratio", "ratio_source": "volume"},
            description="Price to volume ratio",
        ))
        self.register_feature(FeatureDefinition(
            name="high_low_ratio",
            feature_type=FeatureType.DERIVED,
            source="high",
            transform=FeatureTransform.NONE,
            params={"method": "ratio", "ratio_source": "low"},
            description="High to low ratio",
        ))

        # Time features
        self.register_feature(FeatureDefinition(
            name="hour",
            feature_type=FeatureType.TIME,
            source="",
            transform=FeatureTransform.NONE,
            params={"method": "hour"},
            description="Hour of day",
        ))
        self.register_feature(FeatureDefinition(
            name="day_of_week",
            feature_type=FeatureType.TIME,
            source="",
            transform=FeatureTransform.NONE,
            params={"method": "day_of_week"},
            description="Day of week",
        ))
        self.register_feature(FeatureDefinition(
            name="month",
            feature_type=FeatureType.TIME,
            source="",
            transform=FeatureTransform.NONE,
            params={"method": "month"},
            description="Month",
        ))

        logger.info(f"Registered {len(self._feature_definitions)} default features")

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def _build_cache_key(self, data: pd.DataFrame, feature_names: List[str]) -> str:
        """Build cache key."""
        data_hash = hash(data.to_json())
        feature_hash = hash(tuple(sorted(feature_names)))
        return f"features:{data_hash}:{feature_hash}"

    def get_feature_definition(self, name: str) -> Optional[FeatureDefinition]:
        """Get feature definition by name."""
        return self._feature_definitions.get(name)

    def get_feature_importances(self, name: str) -> List[FeatureImportance]:
        """Get feature importance history."""
        return self._feature_importance.get(name, [])

    def get_feature_statistics(self) -> Dict[str, Any]:
        """Get feature statistics."""
        return {
            "total_features": len(self._feature_definitions),
            "feature_types": {
                ft.value: len([f for f in self._feature_definitions.values() if f.feature_type == ft])
                for ft in FeatureType
            },
            "features_with_importance": len(self._feature_importance),
            "cache_size": len(self._feature_cache),
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "feature_cache_size": len(self._feature_cache),
            "feature_definitions": len(self._feature_definitions),
            "feature_importance_history": sum(len(v) for v in self._feature_importance.values()),
        }

    def clear_cache(self) -> None:
        """Clear feature cache."""
        self._feature_cache.clear()
        self._scalers.clear()
        self._pca = None
        self._feature_selector = None
        logger.info("Feature cache cleared")

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the feature engineering engine."""
        logger.info("FeatureEngineeringEngine started")

    async def stop(self) -> None:
        """Stop the feature engineering engine."""
        self.clear_cache()
        logger.info("FeatureEngineeringEngine stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_feature_engineering_engine(
    config: BotConfig,
    data_processor: DataProcessor,
    data_storage: DataStorage,
    cache_manager: CacheManager,
    indicator_factory: IndicatorFactory,
) -> FeatureEngineeringEngine:
    """
    Factory function to create a FeatureEngineeringEngine instance.

    Args:
        config: Bot configuration
        data_processor: Data processor instance
        data_storage: Data storage instance
        cache_manager: Cache manager instance
        indicator_factory: Indicator factory instance

    Returns:
        FeatureEngineeringEngine instance
    """
    return FeatureEngineeringEngine(
        config=config,
        data_processor=data_processor,
        data_storage=data_storage,
        cache_manager=cache_manager,
        indicator_factory=indicator_factory,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the feature engineering engine
    pass

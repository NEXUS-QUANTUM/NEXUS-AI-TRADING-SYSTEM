"""
NEXUS AI TRADING SYSTEM - Feature Engineering
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Feature Engineering system with:
- Technical indicators (SMA, EMA, RSI, MACD, etc.)
- Statistical features
- Lag features
- Rolling features
- Interaction features
- Domain-specific features
- Feature selection
- Feature importance
- Dimensionality reduction
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import find_peaks
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, f_regression, mutual_info_regression
from sklearn.preprocessing import StandardScaler
from ta import add_all_ta_features
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolume, VolumeWeightedAveragePrice
from pydantic import BaseModel, Field, validator

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import FeatureEngineeringError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class FeatureType(str, Enum):
    """Feature types"""
    TECHNICAL = "technical"
    STATISTICAL = "statistical"
    LAG = "lag"
    ROLLING = "rolling"
    INTERACTION = "interaction"
    DOMAIN = "domain"
    REDUCED = "reduced"


class FeatureSelectionMethod(str, Enum):
    """Feature selection methods"""
    K_BEST = "k_best"
    MUTUAL_INFO = "mutual_info"
    PCA = "pca"
    RFE = "rfe"
    TREE_IMPORTANCE = "tree_importance"


@dataclass
class FeatureConfig:
    """Feature configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    type: FeatureType
    columns: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureResult:
    """Feature engineering result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    config_id: str
    data: pd.DataFrame
    original_features: List[str]
    new_features: List[str]
    dropped_features: List[str]
    feature_count: int
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class FeatureEngineerConfig(BaseModel):
    """Feature engineer configuration"""
    enabled: bool = True
    default_tech_indicators: bool = True
    default_lag_periods: List[int] = [1, 2, 3, 5, 10, 20]
    default_rolling_windows: List[int] = [5, 10, 20, 50, 100]
    max_features: int = Field(default=1000, gt=0)
    parallel_workers: int = Field(default=4, gt=0)
    cache_enabled: bool = True
    cache_ttl: int = Field(default=3600, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# FEATURE ENGINEER
# ========================================

class FeatureEngineer:
    """
    Complete feature engineer for trading data.
    
    Features:
    - Technical indicators (SMA, EMA, RSI, MACD, etc.)
    - Statistical features
    - Lag features
    - Rolling features
    - Interaction features
    - Domain-specific features
    - Feature selection
    - Feature importance
    - Dimensionality reduction
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = FeatureEngineerConfig(**(config or {}))
        self.redis = get_redis()
        
        # State
        self._configs: Dict[str, FeatureConfig] = {}
        self._cache: Dict[str, FeatureResult] = {}
        self._feature_importance: Dict[str, Dict[str, float]] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_engineerings": 0,
            "successful_engineerings": 0,
            "failed_engineerings": 0,
            "features_created": 0,
            "features_dropped": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_engineering_time": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.FeatureEngineer")
        self.logger.info("FeatureEngineer initialized")
    
    # ========================================
    # CONFIGURATION MANAGEMENT
    # ========================================
    
    async def register_config(
        self,
        name: str,
        type: FeatureType,
        columns: Optional[List[str]] = None,
        **kwargs
    ) -> FeatureConfig:
        """
        Register a feature configuration.
        
        Args:
            name: Configuration name
            type: Feature type
            columns: Columns to process
            **kwargs: Additional parameters
            
        Returns:
            FeatureConfig: Registered configuration
        """
        config = FeatureConfig(
            name=name,
            type=type,
            columns=columns or [],
            **kwargs
        )
        
        self._configs[config.id] = config
        
        self.logger.info(f"Registered feature config: {name}")
        return config
    
    # ========================================
    # FEATURE ENGINEERING
    # ========================================
    
    async def engineer_features(
        self,
        data: pd.DataFrame,
        config_id: Optional[str] = None,
        config: Optional[FeatureConfig] = None,
        cache_key: Optional[str] = None
    ) -> FeatureResult:
        """
        Engineer features.
        
        Args:
            data: Input data
            config_id: Config ID
            config: Config (alternative)
            cache_key: Cache key
            
        Returns:
            FeatureResult: Engineered features
        """
        start_time = time.time()
        
        # Get config
        if config_id:
            feature_config = self._configs.get(config_id)
            if not feature_config:
                raise FeatureEngineeringError(f"Config {config_id} not found")
        elif config:
            feature_config = config
        else:
            raise FeatureEngineeringError("No config provided")
        
        # Check cache
        if self.config.cache_enabled and cache_key:
            cached = self._get_cached_result(cache_key)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        try:
            # Copy data
            df = data.copy()
            original_features = df.columns.tolist()
            
            # Track new features
            new_features = []
            dropped_features = []
            
            # Apply feature engineering based on type
            if feature_config.type == FeatureType.TECHNICAL:
                df, new_feats = await self._add_technical_features(df, feature_config)
                new_features.extend(new_feats)
            
            elif feature_config.type == FeatureType.STATISTICAL:
                df, new_feats = await self._add_statistical_features(df, feature_config)
                new_features.extend(new_feats)
            
            elif feature_config.type == FeatureType.LAG:
                df, new_feats = await self._add_lag_features(df, feature_config)
                new_features.extend(new_feats)
            
            elif feature_config.type == FeatureType.ROLLING:
                df, new_feats = await self._add_rolling_features(df, feature_config)
                new_features.extend(new_feats)
            
            elif feature_config.type == FeatureType.INTERACTION:
                df, new_feats = await self._add_interaction_features(df, feature_config)
                new_features.extend(new_feats)
            
            elif feature_config.type == FeatureType.DOMAIN:
                df, new_feats = await self._add_domain_features(df, feature_config)
                new_features.extend(new_feats)
            
            elif feature_config.type == FeatureType.REDUCED:
                df, new_feats, dropped = await self._reduce_features(df, feature_config)
                new_features.extend(new_feats)
                dropped_features.extend(dropped)
            
            # Drop any features exceeding limit
            if len(df.columns) > self.config.max_features:
                excess = len(df.columns) - self.config.max_features
                # Drop features with highest variance
                variances = df.var()
                to_drop = variances.nlargest(excess).index.tolist()
                df = df.drop(columns=to_drop)
                dropped_features.extend(to_drop)
            
            # Update feature counts
            self._metrics["features_created"] += len(new_features)
            self._metrics["features_dropped"] += len(dropped_features)
            
            # Create result
            result = FeatureResult(
                config_id=feature_config.id,
                data=df,
                original_features=original_features,
                new_features=new_features,
                dropped_features=dropped_features,
                feature_count=len(df.columns),
                processing_time=time.time() - start_time
            )
            
            # Update metrics
            self._metrics["total_engineerings"] += 1
            self._metrics["successful_engineerings"] += 1
            self._metrics["avg_engineering_time"] = (
                self._metrics["avg_engineering_time"] * 0.9 + result.processing_time * 0.1
            )
            
            # Cache result
            if self.config.cache_enabled and cache_key:
                self._set_cached_result(cache_key, result)
                self._metrics["cache_misses"] += 1
            
            self.logger.info(
                f"Feature engineering completed: {feature_config.name} "
                f"features={len(df.columns)} time={result.processing_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Feature engineering failed: {e}")
            self._metrics["failed_engineerings"] += 1
            raise FeatureEngineeringError(f"Feature engineering failed: {e}")
    
    # ========================================
    # TECHNICAL INDICATORS
    # ========================================
    
    async def _add_technical_features(
        self,
        df: pd.DataFrame,
        config: FeatureConfig
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Add technical indicators"""
        new_features = []
        df_copy = df.copy()
        
        # Ensure required columns exist
        required = ['open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in df_copy.columns:
                self.logger.warning(f"Missing required column for technical indicators: {col}")
                return df, []
        
        # Add all TA features
        try:
            df_ta = add_all_ta_features(
                df_copy,
                open="open",
                high="high",
                low="low",
                close="close",
                volume="volume",
                fillna=True
            )
            
            # Get new feature names
            new_features = [col for col in df_ta.columns if col not in df_copy.columns]
            
            # Add to original dataframe
            for col in new_features:
                df[col] = df_ta[col]
            
            return df, new_features
            
        except Exception as e:
            self.logger.error(f"Technical indicator error: {e}")
            return df, []
    
    # ========================================
    # STATISTICAL FEATURES
    # ========================================
    
    async def _add_statistical_features(
        self,
        df: pd.DataFrame,
        config: FeatureConfig
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Add statistical features"""
        new_features = []
        df_copy = df.copy()
        
        columns = config.columns or df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df_copy.columns:
                continue
            
            # Skewness
            skew_col = f"{col}_skew"
            df_copy[skew_col] = df_copy[col].rolling(20).apply(lambda x: stats.skew(x) if len(x) > 2 else 0)
            new_features.append(skew_col)
            
            # Kurtosis
            kurt_col = f"{col}_kurt"
            df_copy[kurt_col] = df_copy[col].rolling(20).apply(lambda x: stats.kurtosis(x) if len(x) > 2 else 0)
            new_features.append(kurt_col)
            
            # Z-score
            zscore_col = f"{col}_zscore"
            df_copy[zscore_col] = (df_copy[col] - df_copy[col].rolling(20).mean()) / df_copy[col].rolling(20).std()
            new_features.append(zscore_col)
            
            # Range
            range_col = f"{col}_range"
            df_copy[range_col] = df_copy[col].rolling(20).max() - df_copy[col].rolling(20).min()
            new_features.append(range_col)
        
        for col in new_features:
            df[col] = df_copy[col]
        
        return df, new_features
    
    # ========================================
    # LAG FEATURES
    # ========================================
    
    async def _add_lag_features(
        self,
        df: pd.DataFrame,
        config: FeatureConfig
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Add lag features"""
        new_features = []
        df_copy = df.copy()
        
        columns = config.columns or df.select_dtypes(include=[np.number]).columns.tolist()
        periods = config.parameters.get('periods', self.config.default_lag_periods)
        
        for col in columns:
            if col not in df_copy.columns:
                continue
            
            for period in periods:
                lag_col = f"{col}_lag_{period}"
                df_copy[lag_col] = df_copy[col].shift(period)
                new_features.append(lag_col)
        
        for col in new_features:
            df[col] = df_copy[col]
        
        return df, new_features
    
    # ========================================
    # ROLLING FEATURES
    # ========================================
    
    async def _add_rolling_features(
        self,
        df: pd.DataFrame,
        config: FeatureConfig
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Add rolling features"""
        new_features = []
        df_copy = df.copy()
        
        columns = config.columns or df.select_dtypes(include=[np.number]).columns.tolist()
        windows = config.parameters.get('windows', self.config.default_rolling_windows)
        
        for col in columns:
            if col not in df_copy.columns:
                continue
            
            for window in windows:
                if len(df_copy) < window:
                    continue
                
                # Rolling mean
                mean_col = f"{col}_rolling_mean_{window}"
                df_copy[mean_col] = df_copy[col].rolling(window).mean()
                new_features.append(mean_col)
                
                # Rolling std
                std_col = f"{col}_rolling_std_{window}"
                df_copy[std_col] = df_copy[col].rolling(window).std()
                new_features.append(std_col)
                
                # Rolling min
                min_col = f"{col}_rolling_min_{window}"
                df_copy[min_col] = df_copy[col].rolling(window).min()
                new_features.append(min_col)
                
                # Rolling max
                max_col = f"{col}_rolling_max_{window}"
                df_copy[max_col] = df_copy[col].rolling(window).max()
                new_features.append(max_col)
                
                # Rolling quantile
                for q in [0.25, 0.75]:
                    quantile_col = f"{col}_rolling_q{int(q*100)}_{window}"
                    df_copy[quantile_col] = df_copy[col].rolling(window).quantile(q)
                    new_features.append(quantile_col)
        
        for col in new_features:
            df[col] = df_copy[col]
        
        return df, new_features
    
    # ========================================
    # INTERACTION FEATURES
    # ========================================
    
    async def _add_interaction_features(
        self,
        df: pd.DataFrame,
        config: FeatureConfig
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Add interaction features"""
        new_features = []
        df_copy = df.copy()
        
        columns = config.columns or df.select_dtypes(include=[np.number]).columns.tolist()
        
        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                col1 = columns[i]
                col2 = columns[j]
                
                if col1 not in df_copy.columns or col2 not in df_copy.columns:
                    continue
                
                # Product
                prod_col = f"{col1}_{col2}_prod"
                df_copy[prod_col] = df_copy[col1] * df_copy[col2]
                new_features.append(prod_col)
                
                # Ratio
                ratio_col = f"{col1}_{col2}_ratio"
                df_copy[ratio_col] = df_copy[col1] / (df_copy[col2] + 1e-8)
                new_features.append(ratio_col)
        
        for col in new_features:
            df[col] = df_copy[col]
        
        return df, new_features
    
    # ========================================
    # DOMAIN FEATURES
    # ========================================
    
    async def _add_domain_features(
        self,
        df: pd.DataFrame,
        config: FeatureConfig
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Add domain-specific features"""
        new_features = []
        df_copy = df.copy()
        
        # Price features
        if all(col in df_copy.columns for col in ['open', 'high', 'low', 'close']):
            # Body size
            df_copy['body_size'] = abs(df_copy['close'] - df_copy['open'])
            new_features.append('body_size')
            
            # Upper shadow
            df_copy['upper_shadow'] = df_copy['high'] - df_copy[['open', 'close']].max(axis=1)
            new_features.append('upper_shadow')
            
            # Lower shadow
            df_copy['lower_shadow'] = df_copy[['open', 'close']].min(axis=1) - df_copy['low']
            new_features.append('lower_shadow')
            
            # Price position
            df_copy['price_position'] = (df_copy['close'] - df_copy['low']) / (df_copy['high'] - df_copy['low'] + 1e-8)
            new_features.append('price_position')
        
        # Volume features
        if 'volume' in df_copy.columns:
            # Volume change
            df_copy['volume_change'] = df_copy['volume'].pct_change()
            new_features.append('volume_change')
            
            # Volume moving average ratio
            df_copy['volume_ma_ratio'] = df_copy['volume'] / df_copy['volume'].rolling(20).mean()
            new_features.append('volume_ma_ratio')
        
        # Time features
        if isinstance(df_copy.index, pd.DatetimeIndex):
            df_copy['day_of_week'] = df_copy.index.dayofweek
            new_features.append('day_of_week')
            
            df_copy['hour'] = df_copy.index.hour
            new_features.append('hour')
            
            df_copy['minute'] = df_copy.index.minute
            new_features.append('minute')
        
        for col in new_features:
            df[col] = df_copy[col]
        
        return df, new_features
    
    # ========================================
    # FEATURE REDUCTION
    # ========================================
    
    async def _reduce_features(
        self,
        df: pd.DataFrame,
        config: FeatureConfig
    ) -> Tuple[pd.DataFrame, List[str], List[str]]:
        """Reduce features using selection methods"""
        new_features = []
        dropped_features = []
        df_copy = df.copy()
        
        method = config.parameters.get('method', FeatureSelectionMethod.K_BEST)
        n_features = config.parameters.get('n_features', min(50, len(df.columns) // 2))
        target = config.parameters.get('target')
        
        if target is None or target not in df_copy.columns:
            self.logger.warning("No target column for feature selection")
            return df, [], []
        
        X = df_copy.drop(columns=[target])
        y = df_copy[target]
        
        # Handle missing values
        X = X.fillna(X.mean())
        
        if method == FeatureSelectionMethod.K_BEST:
            selector = SelectKBest(score_func=f_regression, k=n_features)
            selector.fit(X, y)
            selected_mask = selector.get_support()
            
        elif method == FeatureSelectionMethod.MUTUAL_INFO:
            selector = SelectKBest(score_func=mutual_info_regression, k=n_features)
            selector.fit(X, y)
            selected_mask = selector.get_support()
            
        elif method == FeatureSelectionMethod.PCA:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            pca = PCA(n_components=min(n_features, X.shape[1]))
            X_pca = pca.fit_transform(X_scaled)
            
            # Create PCA features
            for i in range(X_pca.shape[1]):
                col = f"pca_{i+1}"
                df_copy[col] = X_pca[:, i]
                new_features.append(col)
            
            # Drop original features
            dropped_features = X.columns.tolist()
            df_copy = df_copy.drop(columns=dropped_features)
            
            # Add target back
            df_copy[target] = y
            
            for col in new_features:
                df[col] = df_copy[col]
            
            return df, new_features, dropped_features
            
        else:
            self.logger.warning(f"Unsupported feature selection method: {method}")
            return df, [], []
        
        # Apply selection
        selected_features = X.columns[selected_mask].tolist()
        dropped_features = [col for col in X.columns if col not in selected_features]
        
        # Keep selected features and target
        keep_cols = selected_features + [target]
        df_copy = df_copy[keep_cols]
        
        new_features = selected_features
        
        for col in new_features:
            df[col] = df_copy[col]
        
        return df, new_features, dropped_features
    
    # ========================================
    # CACHE MANAGEMENT
    # ========================================
    
    def _get_cached_result(self, cache_key: str) -> Optional[FeatureResult]:
        """Get cached result"""
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check Redis cache
        try:
            cached = self.redis.get(f"feature:{cache_key}")
            if cached:
                data = json.loads(cached)
                return FeatureResult(**data)
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def _set_cached_result(self, cache_key: str, result: FeatureResult) -> None:
        """Cache result"""
        self._cache[cache_key] = result
        
        try:
            self.redis.setex(
                f"feature:{cache_key}",
                self.config.cache_ttl,
                json.dumps(result.__dict__, default=str)
            )
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
    
    # ========================================
    # HEALTH MONITORING
    # ========================================
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                health = await self.health_check()
                self.logger.debug(f"Health: {health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self.config.health_check_interval)
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get engineer metrics"""
        return {
            **self._metrics,
            "total_configs": len(self._configs),
            "cache_size": len(self._cache)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check engineer health"""
        health = {
            'status': 'healthy',
            'total_configs': len(self._configs),
            'cache_size': len(self._cache)
        }
        
        if len(self._cache) > 1000:
            health['status'] = 'degraded'
            health['warning'] = 'Cache size exceeds limit'
        
        return health
    
    # ========================================
    # FEATURE IMPORTANCE
    # ========================================
    
    async def calculate_feature_importance(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        method: str = 'correlation'
    ) -> Dict[str, float]:
        """
        Calculate feature importance.
        
        Args:
            X: Features
            y: Target
            method: Importance method
            
        Returns:
            Dict[str, float]: Feature importance scores
        """
        importance = {}
        
        if method == 'correlation':
            for col in X.columns:
                if pd.api.types.is_numeric_dtype(X[col]):
                    corr = X[col].corr(y)
                    importance[col] = abs(corr) if not np.isnan(corr) else 0
                    
        elif method == 'mutual_info':
            X_filled = X.fillna(X.mean())
            mi = mutual_info_regression(X_filled, y)
            for col, score in zip(X.columns, mi):
                importance[col] = score
                
        else:
            self.logger.warning(f"Unsupported importance method: {method}")
            return {}
        
        # Normalize
        total = sum(importance.values())
        if total > 0:
            for col in importance:
                importance[col] /= total
        
        return importance
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the feature engineer"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("FeatureEngineer started")
    
    async def stop(self) -> None:
        """Stop the feature engineer"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("FeatureEngineer stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_feature_engineer: Optional[FeatureEngineer] = None


def get_feature_engineer() -> FeatureEngineer:
    """Get singleton instance of FeatureEngineer"""
    global _feature_engineer
    if _feature_engineer is None:
        _feature_engineer = FeatureEngineer()
    return _feature_engineer


def reset_feature_engineer() -> None:
    """Reset the feature engineer (for testing)"""
    global _feature_engineer
    if _feature_engineer:
        asyncio.create_task(_feature_engineer.stop())
    _feature_engineer = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'FeatureEngineer',
    'FeatureEngineerConfig',
    'FeatureConfig',
    'FeatureResult',
    'FeatureType',
    'FeatureSelectionMethod',
    'get_feature_engineer',
    'reset_feature_engineer'
]

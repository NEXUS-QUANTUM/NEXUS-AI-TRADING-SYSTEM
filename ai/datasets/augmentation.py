"""
NEXUS AI TRADING SYSTEM - Data Augmentation
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Data Augmentation system with:
- Time series augmentation
- Price transformation
- Noise injection
- Time warping
- Magnitude warping
- Data synthesis
- Window slicing
- Feature engineering
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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import savgol_filter
from scipy.ndimage import gaussian_filter1d
from pydantic import BaseModel, Field, validator

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import AugmentationError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class AugmentationType(str, Enum):
    """Augmentation types"""
    NOISE = "noise"
    WARPING = "warping"
    SCALING = "scaling"
    SHIFTING = "shifting"
    CROPPING = "cropping"
    SYNTHESIS = "synthesis"
    MIXING = "mixing"
    TIMESTAMP = "timestamp"
    FEATURE = "feature"


class NoiseType(str, Enum):
    """Noise types"""
    GAUSSIAN = "gaussian"
    UNIFORM = "uniform"
    LAPLACIAN = "laplacian"
    POISSON = "poisson"
    IMPULSE = "impulse"
    PERIODIC = "periodic"
    BROWNIAN = "brownian"


class WarpingType(str, Enum):
    """Warping types"""
    TIME = "time"
    MAGNITUDE = "magnitude"
    PHASE = "phase"
    FREQUENCY = "frequency"
    DYNAMIC = "dynamic"


@dataclass
class AugmentationConfig:
    """Augmentation configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    type: AugmentationType
    parameters: Dict[str, Any] = field(default_factory=dict)
    probability: float = 0.5
    intensity: float = 0.5
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AugmentedData:
    """Augmented data"""
    original: pd.DataFrame
    augmented: pd.DataFrame
    config: AugmentationConfig
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AugmenterConfig(BaseModel):
    """Augmenter configuration"""
    enabled: bool = True
    default_probability: float = Field(default=0.5, ge=0, le=1)
    default_intensity: float = Field(default=0.5, ge=0, le=1)
    max_augmentations: int = Field(default=10, gt=0)
    parallel_workers: int = Field(default=4, gt=0)
    cache_enabled: bool = True
    cache_ttl: int = Field(default=3600, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# DATA AUGMENTER
# ========================================

class DataAugmenter:
    """
    Complete data augmenter for time series data.
    
    Features:
    - Time series augmentation
    - Price transformation
    - Noise injection
    - Time warping
    - Magnitude warping
    - Data synthesis
    - Window slicing
    - Feature engineering
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = AugmenterConfig(**(config or {}))
        self.redis = get_redis()
        
        # State
        self._augmentations: Dict[str, AugmentationConfig] = {}
        self._cache: Dict[str, AugmentedData] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_augmentations": 0,
            "augmented_samples": 0,
            "augmentations_by_type": {},
            "avg_augmentation_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        self.logger = get_logger(f"{__name__}.DataAugmenter")
        self.logger.info("DataAugmenter initialized")
    
    # ========================================
    # AUGMENTATION CONFIGURATION
    # ========================================
    
    async def register_augmentation(
        self,
        name: str,
        type: AugmentationType,
        parameters: Optional[Dict[str, Any]] = None,
        probability: float = 0.5,
        intensity: float = 0.5
    ) -> AugmentationConfig:
        """
        Register an augmentation configuration.
        
        Args:
            name: Augmentation name
            type: Augmentation type
            parameters: Augmentation parameters
            probability: Probability of application
            intensity: Intensity of augmentation
            
        Returns:
            AugmentationConfig: Registered configuration
        """
        config = AugmentationConfig(
            name=name,
            type=type,
            parameters=parameters or {},
            probability=min(1.0, max(0.0, probability)),
            intensity=min(1.0, max(0.0, intensity))
        )
        
        self._augmentations[config.id] = config
        
        self.logger.info(f"Registered augmentation: {name} ({type.value})")
        return config
    
    # ========================================
    # DATA AUGMENTATION
    # ========================================
    
    async def augment_data(
        self,
        data: pd.DataFrame,
        config_id: Optional[str] = None,
        config: Optional[AugmentationConfig] = None,
        cache_key: Optional[str] = None
    ) -> AugmentedData:
        """
        Augment time series data.
        
        Args:
            data: Original data
            config_id: Augmentation config ID
            config: Augmentation config (alternative)
            cache_key: Cache key
            
        Returns:
            AugmentedData: Augmented data
        """
        start_time = time.time()
        
        # Get config
        if config_id:
            aug_config = self._augmentations.get(config_id)
            if not aug_config:
                raise AugmentationError(f"Augmentation config {config_id} not found")
        elif config:
            aug_config = config
        else:
            raise AugmentationError("No augmentation config provided")
        
        # Check cache
        if self.config.cache_enabled and cache_key:
            cached = self._get_cached_augmentation(cache_key)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        try:
            # Apply augmentation
            augmented_df = await self._apply_augmentation(data, aug_config)
            
            # Create result
            result = AugmentedData(
                original=data.copy(),
                augmented=augmented_df,
                config=aug_config
            )
            
            # Cache result
            if self.config.cache_enabled and cache_key:
                self._set_cached_augmentation(cache_key, result)
                self._metrics["cache_misses"] += 1
            
            # Update metrics
            self._metrics["total_augmentations"] += 1
            self._metrics["augmented_samples"] += len(augmented_df)
            
            if aug_config.type.value not in self._metrics["augmentations_by_type"]:
                self._metrics["augmentations_by_type"][aug_config.type.value] = 0
            self._metrics["augmentations_by_type"][aug_config.type.value] += 1
            
            elapsed = time.time() - start_time
            self._metrics["avg_augmentation_time"] = (
                self._metrics["avg_augmentation_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(
                f"Augmentation applied: {aug_config.name} "
                f"samples={len(augmented_df)} time={elapsed:.3f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Augmentation failed: {e}")
            raise AugmentationError(f"Augmentation failed: {e}")
    
    async def _apply_augmentation(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply augmentation to data"""
        if config.type == AugmentationType.NOISE:
            return await self._apply_noise(data, config)
        elif config.type == AugmentationType.WARPING:
            return await self._apply_warping(data, config)
        elif config.type == AugmentationType.SCALING:
            return await self._apply_scaling(data, config)
        elif config.type == AugmentationType.SHIFTING:
            return await self._apply_shifting(data, config)
        elif config.type == AugmentationType.CROPPING:
            return await self._apply_cropping(data, config)
        elif config.type == AugmentationType.SYNTHESIS:
            return await self._apply_synthesis(data, config)
        elif config.type == AugmentationType.MIXING:
            return await self._apply_mixing(data, config)
        elif config.type == AugmentationType.TIMESTAMP:
            return await self._apply_timestamp_augmentation(data, config)
        elif config.type == AugmentationType.FEATURE:
            return await self._apply_feature_augmentation(data, config)
        else:
            raise AugmentationError(f"Unsupported augmentation type: {config.type}")
    
    # ========================================
    # AUGMENTATION METHODS
    # ========================================
    
    async def _apply_noise(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply noise augmentation"""
        df = data.copy()
        noise_type = config.parameters.get('noise_type', NoiseType.GAUSSIAN.value)
        intensity = config.intensity
        
        # Get numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            if noise_type == NoiseType.GAUSSIAN.value:
                noise = np.random.normal(0, intensity * df[col].std(), len(df))
            elif noise_type == NoiseType.UNIFORM.value:
                noise = np.random.uniform(-intensity, intensity, len(df)) * df[col].std()
            elif noise_type == NoiseType.LAPLACIAN.value:
                noise = np.random.laplace(0, intensity * df[col].std(), len(df))
            elif noise_type == NoiseType.POISSON.value:
                noise = np.random.poisson(intensity * df[col].std(), len(df))
            elif noise_type == NoiseType.IMPULSE.value:
                noise = np.zeros(len(df))
                mask = np.random.random(len(df)) < intensity * 0.1
                noise[mask] = np.random.choice([-1, 1], size=np.sum(mask)) * df[col].std()
            elif noise_type == NoiseType.PERIODIC.value:
                period = config.parameters.get('period', 20)
                amplitude = intensity * df[col].std()
                noise = amplitude * np.sin(2 * np.pi * np.arange(len(df)) / period)
            else:
                noise = np.random.normal(0, intensity * df[col].std(), len(df))
            
            df[col] = df[col] + noise
        
        return df
    
    async def _apply_warping(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply time/magnitude warping"""
        df = data.copy()
        warping_type = config.parameters.get('warping_type', WarpingType.TIME.value)
        intensity = config.intensity
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if warping_type == WarpingType.TIME.value:
            # Time warping (stretch/compress)
            factor = 1 + intensity * (np.random.random() * 2 - 1) * 0.5
            n_points = len(df)
            new_indices = np.linspace(0, n_points - 1, int(n_points * factor))
            new_indices = np.clip(new_indices, 0, n_points - 1).astype(int)
            
            for col in numeric_cols:
                df[col] = df[col].iloc[new_indices].values
            
            # Truncate to original length
            df = df.iloc[:n_points]
            
        elif warping_type == WarpingType.MAGNITUDE.value:
            # Magnitude warping
            smooth = config.parameters.get('smooth', 3)
            sigma = intensity * 10 + 1
            
            # Apply Gaussian smoothing to create warping curve
            warping_curve = gaussian_filter1d(
                np.random.normal(0, 1, len(df)),
                sigma
            )
            warping_curve = 1 + intensity * warping_curve / np.std(warping_curve) * 0.3
            
            for col in numeric_cols:
                df[col] = df[col] * warping_curve
        
        elif warping_type == WarpingType.PHASE.value:
            # Phase warping
            phase_shift = intensity * 2 * np.pi * (np.random.random() - 0.5)
            n_points = len(df)
            t = np.arange(n_points)
            
            for col in numeric_cols:
                # FFT-based phase shift
                fft_data = np.fft.fft(df[col])
                freqs = np.fft.fftfreq(n_points)
                phase_shift_curve = np.exp(1j * 2 * np.pi * freqs * phase_shift)
                df[col] = np.real(np.fft.ifft(fft_data * phase_shift_curve))
        
        return df
    
    async def _apply_scaling(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply scaling augmentation"""
        df = data.copy()
        scale_factor = 1 + config.intensity * (np.random.random() * 2 - 1) * 0.5
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            if config.parameters.get('center', True):
                mean = df[col].mean()
                df[col] = (df[col] - mean) * scale_factor + mean
            else:
                df[col] = df[col] * scale_factor
        
        return df
    
    async def _apply_shifting(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply shifting augmentation"""
        df = data.copy()
        shift = config.intensity * (np.random.random() * 2 - 1) * 0.1
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            mean = df[col].mean()
            std = df[col].std()
            df[col] = df[col] + shift * std
        
        return df
    
    async def _apply_cropping(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply cropping augmentation"""
        df = data.copy()
        crop_ratio = config.parameters.get('crop_ratio', 0.1) * config.intensity
        
        if crop_ratio >= 1:
            return df
        
        n_points = len(df)
        crop_size = int(n_points * crop_ratio)
        
        if crop_size <= 0:
            return df
        
        # Random crop
        start_idx = np.random.randint(0, max(1, n_points - crop_size))
        end_idx = start_idx + crop_size
        
        return df.iloc[start_idx:end_idx].copy()
    
    async def _apply_synthesis(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply data synthesis"""
        df = data.copy()
        synth_method = config.parameters.get('method', 'interpolation')
        intensity = config.intensity
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if synth_method == 'interpolation':
            # Generate synthetic points
            n_synth = int(len(df) * intensity * 0.2)
            indices = np.random.choice(len(df) - 1, n_synth)
            
            for idx in indices:
                if idx + 1 < len(df):
                    # Interpolate between points
                    weights = np.random.random()
                    for col in numeric_cols:
                        value = df[col].iloc[idx] * (1 - weights) + df[col].iloc[idx + 1] * weights
                        df.loc[len(df)] = df.loc[idx].copy()
                        df.loc[len(df) - 1, col] = value
            
            # Sort by index
            df = df.sort_index().reset_index(drop=True)
        
        elif synth_method == 'bootstrap':
            # Bootstrap sampling
            n_samples = int(len(df) * intensity * 0.5)
            indices = np.random.choice(len(df), n_samples, replace=True)
            synthetic = df.iloc[indices].copy()
            
            # Add small noise
            for col in numeric_cols:
                noise = np.random.normal(0, 0.01 * df[col].std(), len(synthetic))
                synthetic[col] = synthetic[col] + noise
            
            df = pd.concat([df, synthetic], ignore_index=True)
        
        return df
    
    async def _apply_mixing(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply data mixing augmentation"""
        df = data.copy()
        mix_ratio = config.intensity * 0.5
        
        if len(df) < 2:
            return df
        
        # Shuffle and mix
        n_samples = len(df)
        indices = np.random.permutation(n_samples)
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            df[col] = df[col] * (1 - mix_ratio) + df[col].iloc[indices].values * mix_ratio
        
        return df
    
    async def _apply_timestamp_augmentation(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply timestamp augmentation"""
        df = data.copy()
        
        if 'timestamp' not in df.columns and df.index.name != 'timestamp':
            return df
        
        # Get timestamp column
        timestamp_col = 'timestamp' if 'timestamp' in df.columns else df.index.name
        
        if timestamp_col is None:
            return df
        
        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        
        # Add time shifts
        shift_days = int(config.intensity * 7)  # Up to 7 days
        shift_hours = int(config.intensity * 24)  # Up to 24 hours
        
        # Random time shift
        if config.parameters.get('shift_type', 'random') == 'random':
            shift = np.random.randint(-shift_days, shift_days + 1)
            df[timestamp_col] = df[timestamp_col] + pd.Timedelta(days=shift)
        
        # Add time noise
        if config.parameters.get('add_noise', True):
            noise_seconds = int(config.intensity * 3600)  # Up to 1 hour
            noise = np.random.randint(-noise_seconds, noise_seconds + 1, len(df))
            df[timestamp_col] = df[timestamp_col] + pd.to_timedelta(noise, unit='s')
        
        return df
    
    async def _apply_feature_augmentation(
        self,
        data: pd.DataFrame,
        config: AugmentationConfig
    ) -> pd.DataFrame:
        """Apply feature augmentation"""
        df = data.copy()
        feature_type = config.parameters.get('feature_type', 'lag')
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if feature_type == 'lag':
            # Add lag features
            lags = range(1, int(config.intensity * 5) + 1)
            for col in numeric_cols:
                for lag in lags:
                    df[f'{col}_lag_{lag}'] = df[col].shift(lag)
        
        elif feature_type == 'rolling':
            # Add rolling features
            windows = range(3, int(config.intensity * 10) + 1, 2)
            for col in numeric_cols:
                for window in windows:
                    if window <= len(df):
                        df[f'{col}_rolling_mean_{window}'] = df[col].rolling(window).mean()
                        df[f'{col}_rolling_std_{window}'] = df[col].rolling(window).std()
        
        elif feature_type == 'diff':
            # Add difference features
            diffs = range(1, int(config.intensity * 3) + 1)
            for col in numeric_cols:
                for diff in diffs:
                    df[f'{col}_diff_{diff}'] = df[col].diff(diff)
        
        elif feature_type == 'interaction':
            # Add interaction features
            if len(numeric_cols) >= 2:
                for i in range(len(numeric_cols)):
                    for j in range(i + 1, len(numeric_cols)):
                        col1 = numeric_cols[i]
                        col2 = numeric_cols[j]
                        df[f'{col1}_{col2}_prod'] = df[col1] * df[col2]
                        df[f'{col1}_{col2}_ratio'] = df[col1] / (df[col2] + 1e-8)
        
        return df
    
    # ========================================
    # CACHE MANAGEMENT
    # ========================================
    
    def _get_cached_augmentation(self, cache_key: str) -> Optional[AugmentedData]:
        """Get cached augmentation"""
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check Redis cache
        try:
            cached = self.redis.get(f"augmentation:{cache_key}")
            if cached:
                data = json.loads(cached)
                return AugmentedData(**data)
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def _set_cached_augmentation(
        self,
        cache_key: str,
        data: AugmentedData
    ) -> None:
        """Cache augmentation"""
        self._cache[cache_key] = data
        
        try:
            self.redis.setex(
                f"augmentation:{cache_key}",
                self.config.cache_ttl,
                json.dumps(data.__dict__, default=str)
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
        """Get augmenter metrics"""
        return {
            **self._metrics,
            "total_configs": len(self._augmentations),
            "cache_size": len(self._cache)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check augmenter health"""
        health = {
            'status': 'healthy',
            'total_configs': len(self._augmentations),
            'cache_size': len(self._cache),
            'total_augmentations': self._metrics["total_augmentations"]
        }
        
        if len(self._cache) > 1000:
            health['status'] = 'degraded'
            health['warning'] = 'Cache size exceeds limit'
        
        return health
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the augmenter"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("DataAugmenter started")
    
    async def stop(self) -> None:
        """Stop the augmenter"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("DataAugmenter stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_data_augmenter: Optional[DataAugmenter] = None


def get_data_augmenter() -> DataAugmenter:
    """Get singleton instance of DataAugmenter"""
    global _data_augmenter
    if _data_augmenter is None:
        _data_augmenter = DataAugmenter()
    return _data_augmenter


def reset_data_augmenter() -> None:
    """Reset the data augmenter (for testing)"""
    global _data_augmenter
    if _data_augmenter:
        asyncio.create_task(_data_augmenter.stop())
    _data_augmenter = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'DataAugmenter',
    'AugmenterConfig',
    'AugmentationConfig',
    'AugmentedData',
    'AugmentationType',
    'NoiseType',
    'WarpingType',
    'get_data_augmenter',
    'reset_data_augmenter'
]

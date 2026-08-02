# trading/bots/hedge_bot/hedge_bot_data_sampling.py

import asyncio
import logging
import time
import math
import random
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class SamplingMethod(str, Enum):
    RANDOM = "random"
    SYSTEMATIC = "systematic"
    STRATIFIED = "stratified"
    CLUSTER = "cluster"
    BOOTSTRAP = "bootstrap"
    RESERVOIR = "reservoir"
    IMPORTANCE = "importance"
    REJECTION = "rejection"
    ADAPTIVE = "adaptive"
    QUANTILE = "quantile"
    LATEST = "latest"
    OLDEST = "oldest"
    PERCENTILE = "percentile"
    UNIFORM = "uniform"
    GAUSSIAN = "gaussian"


class SamplingDimension(str, Enum):
    TIME = "time"
    VALUE = "value"
    CATEGORY = "category"
    SPATIAL = "spatial"
    TEMPORAL = "temporal"
    FREQUENCY = "frequency"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    SPREAD = "spread"
    LIQUIDITY = "liquidity"


@dataclass
class SamplingConfig:
    method: SamplingMethod
    sample_size: int
    seed: Optional[int] = None
    replacement: bool = False
    stratify_by: Optional[List[str]] = None
    cluster_by: Optional[List[str]] = None
    weights: Optional[List[float]] = None
    importance_scores: Optional[List[float]] = None
    quantile: Optional[float] = None
    percentile: Optional[float] = None
    window_size: Optional[int] = None
    batch_size: Optional[int] = None
    probability_threshold: Optional[float] = None
    dimensions: Optional[List[SamplingDimension]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SamplingResult:
    id: str
    method: SamplingMethod
    sample: pd.DataFrame
    original_size: int
    sample_size: int
    sample_ratio: float
    execution_time: float
    confidence_interval: Optional[Tuple[float, float]] = None
    bias: Optional[float] = None
    variance: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SamplingStatistics:
    sample_size: int
    population_size: int
    mean: float
    std: float
    variance: float
    skewness: float
    kurtosis: float
    min: float
    max: float
    quantiles: Dict[float, float]
    confidence_interval: Tuple[float, float]
    bias: float
    efficiency: float


class DataSamplingManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._samplers: Dict[SamplingMethod, Callable] = {}
        self._results: Dict[str, SamplingResult] = {}
        self._statistics: Dict[str, SamplingStatistics] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_samplers()

    def _initialize_samplers(self) -> None:
        self.register_sampler(SamplingMethod.RANDOM, self._sample_random)
        self.register_sampler(SamplingMethod.SYSTEMATIC, self._sample_systematic)
        self.register_sampler(SamplingMethod.STRATIFIED, self._sample_stratified)
        self.register_sampler(SamplingMethod.CLUSTER, self._sample_cluster)
        self.register_sampler(SamplingMethod.BOOTSTRAP, self._sample_bootstrap)
        self.register_sampler(SamplingMethod.RESERVOIR, self._sample_reservoir)
        self.register_sampler(SamplingMethod.IMPORTANCE, self._sample_importance)
        self.register_sampler(SamplingMethod.REJECTION, self._sample_rejection)
        self.register_sampler(SamplingMethod.ADAPTIVE, self._sample_adaptive)
        self.register_sampler(SamplingMethod.QUANTILE, self._sample_quantile)
        self.register_sampler(SamplingMethod.LATEST, self._sample_latest)
        self.register_sampler(SamplingMethod.OLDEST, self._sample_oldest)
        self.register_sampler(SamplingMethod.PERCENTILE, self._sample_percentile)
        self.register_sampler(SamplingMethod.UNIFORM, self._sample_uniform)
        self.register_sampler(SamplingMethod.GAUSSIAN, self._sample_gaussian)

    def register_sampler(self, method: SamplingMethod, sampler: Callable) -> None:
        self._samplers[method] = sampler

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def sample(
        self,
        data: Union[pd.DataFrame, List, np.ndarray],
        config: SamplingConfig,
        compute_statistics: bool = True
    ) -> SamplingResult:
        async with self._lock:
            if isinstance(data, list):
                data = pd.DataFrame(data)
            elif isinstance(data, np.ndarray):
                data = pd.DataFrame(data)
            elif not isinstance(data, pd.DataFrame):
                raise ValueError("Data must be DataFrame, list, or numpy array")
            
            if config.sample_size > len(data):
                config.sample_size = len(data)
            
            if config.method not in self._samplers:
                raise ValueError(f"Unsupported sampling method: {config.method}")
            
            start_time = time.time()
            sampler = self._samplers[config.method]
            
            if config.seed is not None:
                random.seed(config.seed)
                np.random.seed(config.seed)
            
            sample = await sampler(data, config)
            
            execution_time = time.time() - start_time
            
            result = SamplingResult(
                id=hashlib.md5(f"{config.method.value}_{time.time()}".encode()).hexdigest(),
                method=config.method,
                sample=sample,
                original_size=len(data),
                sample_size=len(sample),
                sample_ratio=len(sample) / len(data) if len(data) > 0 else 0,
                execution_time=execution_time,
                metadata=config.metadata
            )
            
            if compute_statistics:
                stats = await self._compute_statistics(data, sample, config)
                self._statistics[result.id] = stats
                result.confidence_interval = stats.confidence_interval
                result.bias = stats.bias
                result.variance = stats.variance
            
            self._results[result.id] = result
            await self._notify_observers("sampling_completed", result)
            
            return result

    async def _sample_random(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if config.replacement:
            return data.sample(n=config.sample_size, replace=True, random_state=config.seed)
        else:
            return data.sample(n=config.sample_size, random_state=config.seed)

    async def _sample_systematic(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        n = len(data)
        k = math.ceil(n / config.sample_size)
        start = random.randint(0, k - 1) if config.seed is None else config.seed % k
        
        indices = list(range(start, n, k))[:config.sample_size]
        return data.iloc[indices]

    async def _sample_stratified(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if not config.stratify_by:
            raise ValueError("Stratify_by required for stratified sampling")
        
        stratify_cols = config.stratify_by
        sample_size = config.sample_size
        
        groups = data.groupby(stratify_cols)
        group_sizes = groups.size()
        total_size = len(data)
        
        samples = []
        for group_name, group in groups:
            group_ratio = group_sizes[group_name] / total_size
            group_sample_size = max(1, int(sample_size * group_ratio))
            group_sample = group.sample(n=min(group_sample_size, len(group)), random_state=config.seed)
            samples.append(group_sample)
        
        return pd.concat(samples)

    async def _sample_cluster(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if not config.cluster_by:
            raise ValueError("Cluster_by required for cluster sampling")
        
        cluster_cols = config.cluster_by
        clusters = data.groupby(cluster_cols)
        cluster_names = list(clusters.groups.keys())
        
        num_clusters = len(cluster_names)
        sample_clusters = random.sample(cluster_names, min(config.sample_size, num_clusters))
        
        samples = []
        for cluster in sample_clusters:
            cluster_data = clusters.get_group(cluster)
            samples.append(cluster_data)
        
        return pd.concat(samples).sample(n=config.sample_size, random_state=config.seed)

    async def _sample_bootstrap(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        return data.sample(n=config.sample_size, replace=True, random_state=config.seed)

    async def _sample_reservoir(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        reservoir = []
        for i, row in enumerate(data.iterrows()):
            if i < config.sample_size:
                reservoir.append(row)
            else:
                j = random.randint(0, i)
                if j < config.sample_size:
                    reservoir[j] = row
        
        return pd.DataFrame([r[1] for r in reservoir])

    async def _sample_importance(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if config.importance_scores is None or len(config.importance_scores) != len(data):
            raise ValueError("Importance scores required")
        
        scores = np.array(config.importance_scores)
        probabilities = scores / scores.sum()
        
        indices = np.random.choice(
            len(data),
            size=config.sample_size,
            replace=config.replacement,
            p=probabilities
        )
        
        return data.iloc[indices]

    async def _sample_rejection(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if config.probability_threshold is None:
            raise ValueError("Probability threshold required for rejection sampling")
        
        if config.importance_scores is None:
            raise ValueError("Importance scores required for rejection sampling")
        
        max_score = max(config.importance_scores)
        
        samples = []
        attempts = 0
        max_attempts = config.sample_size * 10
        
        while len(samples) < config.sample_size and attempts < max_attempts:
            idx = random.randint(0, len(data) - 1)
            score = config.importance_scores[idx]
            
            acceptance_prob = score / max_score
            if random.random() < acceptance_prob:
                samples.append(data.iloc[idx])
            
            attempts += 1
        
        return pd.DataFrame(samples)

    async def _sample_adaptive(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if config.batch_size is None:
            config.batch_size = config.sample_size // 10
        
        sample_size = config.sample_size
        batch_size = min(config.batch_size, sample_size)
        
        sample = []
        remaining = data.copy()
        
        while len(sample) < sample_size and len(remaining) > 0:
            batch = remaining.sample(n=min(batch_size, len(remaining)), random_state=config.seed)
            sample.append(batch)
            remaining = remaining.drop(batch.index)
        
        result = pd.concat(sample)
        if len(result) > sample_size:
            result = result.sample(n=sample_size, random_state=config.seed)
        
        return result

    async def _sample_quantile(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if config.quantile is None:
            raise ValueError("Quantile required for quantile sampling")
        
        if config.dimensions is None:
            raise ValueError("Dimensions required for quantile sampling")
        
        quantile = config.quantile
        
        for col in data.select_dtypes(include=[np.number]).columns:
            q_value = data[col].quantile(quantile)
            data = data[data[col] <= q_value]
        
        if len(data) < config.sample_size:
            return data
        
        return data.sample(n=config.sample_size, random_state=config.seed)

    async def _sample_latest(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        return data.tail(config.sample_size)

    async def _sample_oldest(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        return data.head(config.sample_size)

    async def _sample_percentile(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if config.percentile is None:
            raise ValueError("Percentile required for percentile sampling")
        
        if config.dimensions is None:
            raise ValueError("Dimensions required for percentile sampling")
        
        percentile = config.percentile
        
        for col in data.select_dtypes(include=[np.number]).columns:
            p_value = np.percentile(data[col].dropna(), percentile)
            data = data[data[col] <= p_value]
        
        if len(data) < config.sample_size:
            return data
        
        return data.sample(n=config.sample_size, random_state=config.seed)

    async def _sample_uniform(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if config.dimensions is None:
            return await self._sample_random(data, config)
        
        for col in data.select_dtypes(include=[np.number]).columns:
            if col in config.dimensions:
                data[col] = data[col].rank(pct=True)
        
        return data.sample(n=config.sample_size, random_state=config.seed)

    async def _sample_gaussian(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        if config.dimensions is None:
            return await self._sample_random(data, config)
        
        for col in data.select_dtypes(include=[np.number]).columns:
            if col in config.dimensions:
                data[col] = np.random.normal(data[col].mean(), data[col].std(), len(data))
        
        return data.sample(n=config.sample_size, random_state=config.seed)

    async def _compute_statistics(
        self,
        population: pd.DataFrame,
        sample: pd.DataFrame,
        config: SamplingConfig
    ) -> SamplingStatistics:
        numeric_cols = population.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return SamplingStatistics(
                sample_size=len(sample),
                population_size=len(population),
                mean=0,
                std=0,
                variance=0,
                skewness=0,
                kurtosis=0,
                min=0,
                max=0,
                quantiles={0.25: 0, 0.5: 0, 0.75: 0},
                confidence_interval=(0, 0),
                bias=0,
                efficiency=0
            )
        
        pop_values = population[numeric_cols[0]].dropna()
        sample_values = sample[numeric_cols[0]].dropna()
        
        if len(pop_values) == 0 or len(sample_values) == 0:
            return SamplingStatistics(
                sample_size=len(sample),
                population_size=len(population),
                mean=0,
                std=0,
                variance=0,
                skewness=0,
                kurtosis=0,
                min=0,
                max=0,
                quantiles={0.25: 0, 0.5: 0, 0.75: 0},
                confidence_interval=(0, 0),
                bias=0,
                efficiency=0
            )
        
        pop_mean = pop_values.mean()
        sample_mean = sample_values.mean()
        pop_std = pop_values.std()
        sample_std = sample_values.std()
        
        standard_error = sample_std / np.sqrt(len(sample_values))
        z_score = 1.96
        confidence_interval = (
            sample_mean - z_score * standard_error,
            sample_mean + z_score * standard_error
        )
        
        bias = sample_mean - pop_mean
        variance = sample_std ** 2
        efficiency = (pop_std ** 2) / (sample_std ** 2) if sample_std > 0 else 0
        
        return SamplingStatistics(
            sample_size=len(sample),
            population_size=len(population),
            mean=sample_mean,
            std=sample_std,
            variance=variance,
            skewness=float(skew(sample_values)) if len(sample_values) > 2 else 0,
            kurtosis=float(kurtosis(sample_values)) if len(sample_values) > 3 else 0,
            min=float(sample_values.min()),
            max=float(sample_values.max()),
            quantiles={
                0.25: float(sample_values.quantile(0.25)),
                0.5: float(sample_values.quantile(0.5)),
                0.75: float(sample_values.quantile(0.75))
            },
            confidence_interval=confidence_interval,
            bias=bias,
            efficiency=efficiency
        )

    async def get_result(self, result_id: str) -> Optional[SamplingResult]:
        return self._results.get(result_id)

    async def get_statistics(self, result_id: str) -> Optional[SamplingStatistics]:
        return self._statistics.get(result_id)

    async def get_results_by_method(self, method: SamplingMethod) -> List[SamplingResult]:
        return [r for r in self._results.values() if r.method == method]

    async def compare_samples(
        self,
        result_ids: List[str]
    ) -> Dict[str, Any]:
        results = []
        for result_id in result_ids:
            if result_id in self._results:
                results.append(self._results[result_id])
        
        if len(results) < 2:
            return {}
        
        comparison = {
            "methods": [r.method.value for r in results],
            "sample_sizes": [r.sample_size for r in results],
            "sample_ratios": [r.sample_ratio for r in results],
            "execution_times": [r.execution_time for r in results],
            "statistics": {}
        }
        
        for i, result in enumerate(results):
            stats = self._statistics.get(result.id)
            if stats:
                comparison["statistics"][f"result_{i}"] = {
                    "mean": stats.mean,
                    "std": stats.std,
                    "bias": stats.bias,
                    "efficiency": stats.efficiency,
                    "confidence_interval": stats.confidence_interval
                }
        
        return comparison

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "samplers": len(self._samplers),
            "results": len(self._results),
            "statistics": len(self._statistics),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "SamplingMethod",
    "SamplingDimension",
    "SamplingConfig",
    "SamplingResult",
    "SamplingStatistics",
    "DataSamplingManager"
]

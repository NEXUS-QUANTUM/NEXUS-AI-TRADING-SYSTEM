"""
NEXUS AI TRADING SYSTEM - Datasets Package
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Datasets system with:
- Data Augmentation
- Data Loader
- Data Preprocessor
- Dataset Builder
- Feature Engineering
- Time Series Split
- Data validation
- Data transformation
- Data versioning
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type

# ========================================
# VERSION
# ========================================

__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# ========================================
# DATA AUGMENTATION
# ========================================

from ai.datasets.augmentation import (
    DataAugmenter,
    AugmenterConfig,
    AugmentationConfig,
    AugmentedData,
    AugmentationType,
    NoiseType,
    WarpingType,
    get_data_augmenter,
    reset_data_augmenter
)

# ========================================
# DATA LOADER
# ========================================

from ai.datasets.data_loader import (
    DataLoader,
    LoaderConfig,
    DataLoaderConfig,
    DataChunk,
    DataLoadResult,
    DataSource,
    DataFormat,
    DataType,
    LoadingMode,
    get_data_loader,
    reset_data_loader
)

# ========================================
# DATA PREPROCESSOR
# ========================================

from ai.datasets.data_preprocessor import (
    DataPreprocessor,
    PreprocessorConfig,
    PreprocessingConfig,
    PreprocessingResult,
    MissingValueStrategy,
    OutlierMethod,
    ScalingMethod,
    get_data_preprocessor,
    reset_data_preprocessor
)

# ========================================
# DATASET BUILDER
# ========================================

from ai.datasets.dataset_builder import (
    DatasetBuilder,
    DatasetBuilderConfig,
    DatasetConfig,
    Dataset,
    DatasetSummary,
    SplitType,
    DatasetStatus,
    get_dataset_builder,
    reset_dataset_builder
)

# ========================================
# FEATURE ENGINEERING
# ========================================

from ai.datasets.feature_engineering import (
    FeatureEngineer,
    FeatureEngineerConfig,
    FeatureConfig,
    FeatureResult,
    FeatureType,
    FeatureSelectionMethod,
    get_feature_engineer,
    reset_feature_engineer
)

# ========================================
# TIME SERIES SPLIT
# ========================================

from ai.datasets.time_series_split import (
    TimeSeriesSplitter,
    SplitterConfig,
    SplitConfig,
    Split,
    SplitResult,
    SplitMethod,
    SplitStatus,
    get_time_series_splitter,
    reset_time_series_splitter
)

# ========================================
# REGISTRIES
# ========================================

DATASET_COMPONENTS = {
    'data_augmenter': DataAugmenter,
    'data_loader': DataLoader,
    'data_preprocessor': DataPreprocessor,
    'dataset_builder': DatasetBuilder,
    'feature_engineer': FeatureEngineer,
    'time_series_splitter': TimeSeriesSplitter
}

# ========================================
# CONFIGURATION SCHEMAS
# ========================================

DATASET_CONFIG_SCHEMAS = {
    'augmentation': AugmenterConfig,
    'loader': LoaderConfig,
    'preprocessor': PreprocessorConfig,
    'dataset_builder': DatasetBuilderConfig,
    'feature_engineer': FeatureEngineerConfig,
    'splitter': SplitterConfig
}

# ========================================
# EXPORTS
# ========================================

__all__ = [
    # Data Augmentation
    'DataAugmenter',
    'AugmenterConfig',
    'AugmentationConfig',
    'AugmentedData',
    'AugmentationType',
    'NoiseType',
    'WarpingType',
    'get_data_augmenter',
    'reset_data_augmenter',
    
    # Data Loader
    'DataLoader',
    'LoaderConfig',
    'DataLoaderConfig',
    'DataChunk',
    'DataLoadResult',
    'DataSource',
    'DataFormat',
    'DataType',
    'LoadingMode',
    'get_data_loader',
    'reset_data_loader',
    
    # Data Preprocessor
    'DataPreprocessor',
    'PreprocessorConfig',
    'PreprocessingConfig',
    'PreprocessingResult',
    'MissingValueStrategy',
    'OutlierMethod',
    'ScalingMethod',
    'get_data_preprocessor',
    'reset_data_preprocessor',
    
    # Dataset Builder
    'DatasetBuilder',
    'DatasetBuilderConfig',
    'DatasetConfig',
    'Dataset',
    'DatasetSummary',
    'SplitType',
    'DatasetStatus',
    'get_dataset_builder',
    'reset_dataset_builder',
    
    # Feature Engineering
    'FeatureEngineer',
    'FeatureEngineerConfig',
    'FeatureConfig',
    'FeatureResult',
    'FeatureType',
    'FeatureSelectionMethod',
    'get_feature_engineer',
    'reset_feature_engineer',
    
    # Time Series Split
    'TimeSeriesSplitter',
    'SplitterConfig',
    'SplitConfig',
    'Split',
    'SplitResult',
    'SplitMethod',
    'SplitStatus',
    'get_time_series_splitter',
    'reset_time_series_splitter',
    
    # Registries
    'DATASET_COMPONENTS',
    'DATASET_CONFIG_SCHEMAS',
    
    # Version
    '__version__',
    '__author__',
    '__copyright__'
]

# ========================================
# COMPONENT INITIALIZATION
# ========================================

def initialize_datasets() -> None:
    """Initialize all dataset components"""
    logger = logging.getLogger(__name__)
    
    components = {
        'data_augmenter': get_data_augmenter,
        'data_loader': get_data_loader,
        'data_preprocessor': get_data_preprocessor,
        'dataset_builder': get_dataset_builder,
        'feature_engineer': get_feature_engineer,
        'time_series_splitter': get_time_series_splitter
    }
    
    for name, getter in components.items():
        try:
            component = getter()
            logger.info(f"Initialized {name}")
        except Exception as e:
            logger.error(f"Failed to initialize {name}: {e}")
    
    logger.info("Dataset components initialized")


def shutdown_datasets() -> None:
    """Shutdown all dataset components"""
    logger = logging.getLogger(__name__)
    
    components = {
        'data_augmenter': (get_data_augmenter, reset_data_augmenter),
        'data_loader': (get_data_loader, reset_data_loader),
        'data_preprocessor': (get_data_preprocessor, reset_data_preprocessor),
        'dataset_builder': (get_dataset_builder, reset_dataset_builder),
        'feature_engineer': (get_feature_engineer, reset_feature_engineer),
        'time_series_splitter': (get_time_series_splitter, reset_time_series_splitter)
    }
    
    for name, (getter, resetter) in components.items():
        try:
            resetter()
            logger.info(f"Shutdown {name}")
        except Exception as e:
            logger.error(f"Failed to shutdown {name}: {e}")
    
    logger.info("Dataset components shutdown")

# ========================================
# CONTEXT MANAGER
# ========================================

class DatasetContext:
    """Context manager for datasets"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """Enter context"""
        self.logger.info("Starting dataset context")
        initialize_datasets()
        
        # Start components
        components = [
            get_data_augmenter(),
            get_data_loader(),
            get_data_preprocessor(),
            get_dataset_builder(),
            get_feature_engineer(),
            get_time_series_splitter()
        ]
        
        for component in components:
            if hasattr(component, 'start'):
                try:
                    await component.start()
                    self.logger.info(f"Started {component.__class__.__name__}")
                except Exception as e:
                    self.logger.error(f"Failed to start {component.__class__.__name__}: {e}")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context"""
        self.logger.info("Stopping dataset context")
        
        # Stop components
        components = [
            get_data_augmenter(),
            get_data_loader(),
            get_data_preprocessor(),
            get_dataset_builder(),
            get_feature_engineer(),
            get_time_series_splitter()
        ]
        
        for component in components:
            if hasattr(component, 'stop'):
                try:
                    await component.stop()
                    self.logger.info(f"Stopped {component.__class__.__name__}")
                except Exception as e:
                    self.logger.error(f"Failed to stop {component.__class__.__name__}: {e}")
        
        shutdown_datasets()

# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

async def load_and_preprocess_data(
    source: str,
    format: DataFormat,
    preprocess_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> PreprocessingResult:
    """
    Load and preprocess data in one step.
    
    Args:
        source: Data source
        format: Data format
        preprocess_config: Preprocessing configuration
        **kwargs: Additional parameters
        
    Returns:
        PreprocessingResult: Preprocessed data
    """
    # Load data
    loader = get_data_loader()
    load_result = await loader.load_data(
        config=DataLoaderConfig(
            name="temp_loader",
            source=source,
            format=format,
            **kwargs
        )
    )
    
    # Preprocess data
    preprocessor = get_data_preprocessor()
    config = await preprocessor.register_config(
        name="temp_preprocess",
        **preprocess_config or {}
    )
    
    return await preprocessor.preprocess(
        data=load_result.data,
        config_id=config.id
    )


async def build_ml_dataset(
    name: str,
    sources: List[str],
    target: str,
    features: Optional[List[str]] = None,
    split_ratio: float = 0.8,
    **kwargs
) -> Dataset:
    """
    Build a machine learning dataset.
    
    Args:
        name: Dataset name
        sources: Data sources
        target: Target column
        features: Feature columns
        split_ratio: Train ratio
        **kwargs: Additional parameters
        
    Returns:
        Dataset: Built dataset
    """
    builder = get_dataset_builder()
    config = await builder.register_config(
        name=name,
        sources=sources,
        target=target,
        features=features or [],
        train_ratio=split_ratio,
        **kwargs
    )
    
    return await builder.build_dataset(config.id)


async def engineer_trading_features(
    data: pd.DataFrame,
    add_lags: bool = True,
    add_rolling: bool = True,
    add_technical: bool = True
) -> FeatureResult:
    """
    Engineer trading features.
    
    Args:
        data: Input data
        add_lags: Add lag features
        add_rolling: Add rolling features
        add_technical: Add technical indicators
        
    Returns:
        FeatureResult: Engineered features
    """
    engineer = get_feature_engineer()
    config = await engineer.register_config(
        name="trading_features",
        type=FeatureType.TECHNICAL,
        parameters={
            'add_lags': add_lags,
            'add_rolling': add_rolling,
            'add_technical': add_technical
        }
    )
    
    return await engineer.engineer_features(
        data=data,
        config_id=config.id
    )


async def split_time_series(
    data: pd.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    method: SplitMethod = SplitMethod.WALK_FORWARD
) -> SplitResult:
    """
    Split time series data.
    
    Args:
        data: Data to split
        train_ratio: Training ratio
        val_ratio: Validation ratio
        test_ratio: Test ratio
        method: Split method
        
    Returns:
        SplitResult: Split results
    """
    splitter = get_time_series_splitter()
    config = await splitter.register_config(
        name="temp_split",
        method=method,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio
    )
    
    return await splitter.execute_split(
        data=data,
        config_id=config.id
    )

# ========================================
# INITIALIZATION
# ========================================

logger = logging.getLogger(__name__)
logger.info(f"NEXUS Datasets Package v{__version__} initialized")
logger.info(f"Available components: {list(DATASET_COMPONENTS.keys())}")

# Auto-initialize components
initialize_datasets()

# ========================================
# END OF PACKAGE
# ========================================

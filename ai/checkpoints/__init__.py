"""
NEXUS AI TRADING SYSTEM - Checkpoints Package
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Checkpoints system with:
- Checkpoint Manager
- Model Saver
- Version Tracker
- State persistence
- Model serialization
- Version management
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
# CHECKPOINT MANAGER
# ========================================

from ai.checkpoints.checkpoint_manager import (
    CheckpointManager,
    CheckpointConfig,
    Checkpoint,
    CheckpointInfo,
    CheckpointType,
    CheckpointStatus,
    StorageType,
    get_checkpoint_manager,
    reset_checkpoint_manager
)

# ========================================
# MODEL SAVER
# ========================================

from ai.checkpoints.model_saver import (
    ModelSaver,
    ModelSaverConfig,
    ModelMetadata,
    ModelInfo,
    FrameworkType,
    ModelStatus,
    get_model_saver,
    reset_model_saver
)

# ========================================
# VERSION TRACKER
# ========================================

from ai.checkpoints.version_tracker import (
    VersionTracker,
    VersionConfig,
    Version,
    VersionInfo,
    VersionDiff,
    VersionStatus,
    VersionType,
    get_version_tracker,
    reset_version_tracker
)

# ========================================
# REGISTRIES
# ========================================

CHECKPOINT_COMPONENTS = {
    'checkpoint_manager': CheckpointManager,
    'model_saver': ModelSaver,
    'version_tracker': VersionTracker
}

# ========================================
# CONFIGURATION SCHEMAS
# ========================================

CHECKPOINT_CONFIG_SCHEMAS = {
    'checkpoint': CheckpointConfig,
    'model_saver': ModelSaverConfig,
    'version_tracker': VersionConfig
}

# ========================================
# EXPORTS
# ========================================

__all__ = [
    # Checkpoint Manager
    'CheckpointManager',
    'CheckpointConfig',
    'Checkpoint',
    'CheckpointInfo',
    'CheckpointType',
    'CheckpointStatus',
    'StorageType',
    'get_checkpoint_manager',
    'reset_checkpoint_manager',
    
    # Model Saver
    'ModelSaver',
    'ModelSaverConfig',
    'ModelMetadata',
    'ModelInfo',
    'FrameworkType',
    'ModelStatus',
    'get_model_saver',
    'reset_model_saver',
    
    # Version Tracker
    'VersionTracker',
    'VersionConfig',
    'Version',
    'VersionInfo',
    'VersionDiff',
    'VersionStatus',
    'VersionType',
    'get_version_tracker',
    'reset_version_tracker',
    
    # Registries
    'CHECKPOINT_COMPONENTS',
    'CHECKPOINT_CONFIG_SCHEMAS',
    
    # Version
    '__version__',
    '__author__',
    '__copyright__'
]

# ========================================
# COMPONENT INITIALIZATION
# ========================================

def initialize_checkpoints() -> None:
    """Initialize all checkpoint components"""
    logger = logging.getLogger(__name__)
    
    components = {
        'checkpoint_manager': get_checkpoint_manager,
        'model_saver': get_model_saver,
        'version_tracker': get_version_tracker
    }
    
    for name, getter in components.items():
        try:
            component = getter()
            logger.info(f"Initialized {name}")
        except Exception as e:
            logger.error(f"Failed to initialize {name}: {e}")
    
    logger.info("Checkpoint components initialized")


def shutdown_checkpoints() -> None:
    """Shutdown all checkpoint components"""
    logger = logging.getLogger(__name__)
    
    components = {
        'checkpoint_manager': (get_checkpoint_manager, reset_checkpoint_manager),
        'model_saver': (get_model_saver, reset_model_saver),
        'version_tracker': (get_version_tracker, reset_version_tracker)
    }
    
    for name, (getter, resetter) in components.items():
        try:
            resetter()
            logger.info(f"Shutdown {name}")
        except Exception as e:
            logger.error(f"Failed to shutdown {name}: {e}")
    
    logger.info("Checkpoint components shutdown")

# ========================================
# CONTEXT MANAGER
# ========================================

class CheckpointContext:
    """Context manager for checkpoints"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """Enter context"""
        self.logger.info("Starting checkpoint context")
        initialize_checkpoints()
        
        # Start components
        components = [
            get_checkpoint_manager(),
            get_model_saver(),
            get_version_tracker()
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
        self.logger.info("Stopping checkpoint context")
        
        # Stop components
        components = [
            get_checkpoint_manager(),
            get_model_saver(),
            get_version_tracker()
        ]
        
        for component in components:
            if hasattr(component, 'stop'):
                try:
                    await component.stop()
                    self.logger.info(f"Stopped {component.__class__.__name__}")
                except Exception as e:
                    self.logger.error(f"Failed to stop {component.__class__.__name__}: {e}")
        
        shutdown_checkpoints()

# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

async def save_checkpoint(
    name: str,
    type: CheckpointType,
    data: Any,
    version: str = "1.0.0",
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Checkpoint:
    """
    Save a checkpoint.
    
    Args:
        name: Checkpoint name
        type: Checkpoint type
        data: Data to save
        version: Version
        tags: Tags
        metadata: Metadata
        
    Returns:
        Checkpoint: Created checkpoint
    """
    manager = get_checkpoint_manager()
    return await manager.create_checkpoint(
        name=name,
        type=type,
        data=data,
        version=version,
        tags=tags,
        metadata=metadata
    )


async def restore_checkpoint(
    checkpoint_id: str
) -> Any:
    """
    Restore a checkpoint.
    
    Args:
        checkpoint_id: Checkpoint ID
        
    Returns:
        Any: Restored data
    """
    manager = get_checkpoint_manager()
    return await manager.restore_checkpoint(checkpoint_id)


async def save_model(
    model: Any,
    name: str,
    framework: FrameworkType,
    architecture: str,
    version: str = "1.0.0",
    metrics: Optional[Dict[str, float]] = None,
    tags: Optional[List[str]] = None
) -> ModelMetadata:
    """
    Save a model.
    
    Args:
        model: Model to save
        name: Model name
        framework: Framework type
        architecture: Architecture
        version: Version
        metrics: Metrics
        tags: Tags
        
    Returns:
        ModelMetadata: Saved model metadata
    """
    saver = get_model_saver()
    return await saver.save_model(
        model=model,
        name=name,
        framework=framework,
        architecture=architecture,
        version=version,
        metrics=metrics,
        tags=tags
    )


async def load_model(
    model_id: str
) -> Any:
    """
    Load a model.
    
    Args:
        model_id: Model ID
        
    Returns:
        Any: Loaded model
    """
    saver = get_model_saver()
    return await saver.load_model(model_id)


async def create_version(
    name: str,
    number: str,
    type: VersionType,
    description: str = "",
    tags: Optional[List[str]] = None
) -> Version:
    """
    Create a version.
    
    Args:
        name: Version name
        number: Version number
        type: Version type
        description: Description
        tags: Tags
        
    Returns:
        Version: Created version
    """
    tracker = get_version_tracker()
    return await tracker.create_version(
        name=name,
        number=number,
        type=type,
        description=description,
        tags=tags
    )


async def publish_version(
    name: str,
    number: str
) -> Version:
    """
    Publish a version.
    
    Args:
        name: Version name
        number: Version number
        
    Returns:
        Version: Published version
    """
    tracker = get_version_tracker()
    
    # Get version by name and number
    version = await tracker.get_version_by_name_number(name, number)
    if not version:
        raise ValueError(f"Version {name} v{number} not found")
    
    return await tracker.publish_version(version.id)

# ========================================
# INITIALIZATION
# ========================================

logger = logging.getLogger(__name__)
logger.info(f"NEXUS Checkpoints Package v{__version__} initialized")
logger.info(f"Available components: {list(CHECKPOINT_COMPONENTS.keys())}")

# Auto-initialize components
initialize_checkpoints()

# ========================================
# END OF PACKAGE
# ========================================

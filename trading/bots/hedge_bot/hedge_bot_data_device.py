# trading/bots/hedge_bot/hedge_bot_data_device.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Device Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Device Module

This module provides comprehensive device data collection and management
capabilities for the NEXUS Hedge Bot system. It collects device metrics,
manages device state, and provides device-specific optimizations.

The module covers:
- Device Metrics Collection
- Resource Monitoring
- Device Optimization
- Hardware Acceleration
- Performance Tuning
- Device State Management
- Device Health Monitoring
"""

import os
import sys
import json
import logging
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

# Try to import psutil
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Try to import GPU libraries
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import tensorflow as tf
    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False

logger = logging.getLogger(__name__)


# ============================================================
# DATA DEVICE ENUMS
# ============================================================

class DeviceType(Enum):
    """Device types"""
    CPU = "cpu"
    GPU = "gpu"
    TPU = "tpu"
    FPGA = "fpga"
    ASIC = "asic"


class DeviceStatus(Enum):
    """Device status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    OVERLOADED = "overloaded"


class Architecture(Enum):
    """CPU architectures"""
    X86_64 = "x86_64"
    ARM64 = "arm64"
    ARM = "arm"
    X86 = "x86"
    RISCV = "riscv"


@dataclass
class DeviceInfo:
    """Device information"""
    name: str
    type: DeviceType
    architecture: Architecture
    cores: int
    memory_gb: float
    clock_speed_mhz: float
    temperature_celsius: float
    status: DeviceStatus
    load_percent: float
    memory_used_percent: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "type": self.type.value,
            "architecture": self.architecture.value,
            "cores": self.cores,
            "memory_gb": self.memory_gb,
            "clock_speed_mhz": self.clock_speed_mhz,
            "temperature_celsius": self.temperature_celsius,
            "status": self.status.value,
            "load_percent": self.load_percent,
            "memory_used_percent": self.memory_used_percent,
        }


@dataclass
class DeviceMetric:
    """Device metric"""
    device_name: str
    metric_type: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "device_name": self.device_name,
            "metric_type": self.metric_type,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class DeviceOptimization:
    """Device optimization settings"""
    device_type: DeviceType
    batch_size: int
    threads: int
    memory_limit_gb: float
    use_gpu: bool
    precision: str = "float32"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "device_type": self.device_type.value,
            "batch_size": self.batch_size,
            "threads": self.threads,
            "memory_limit_gb": self.memory_limit_gb,
            "use_gpu": self.use_gpu,
            "precision": self.precision,
        }


# ============================================================
# DATA DEVICE ENGINE
# ============================================================

class DataDeviceEngine:
    """
    Comprehensive device data engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the device engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        if not HAS_PSUTIL:
            logger.warning("psutil not installed. Device monitoring limited.")
        
        # State
        self.devices: Dict[str, DeviceInfo] = {}
        self.metrics_history: Dict[str, List[DeviceMetric]] = {}
        self.optimizations: Dict[str, DeviceOptimization] = {}
        
        # Initialize
        self._detect_devices()
        self._init_optimizations()
        
        logger.info("Device engine initialized")
    
    # ============================================================
    # DEVICE DETECTION
    # ============================================================
    
    def _detect_devices(self) -> None:
        """Detect available devices"""
        # CPU detection
        cpu_info = self._detect_cpu()
        if cpu_info:
            self.devices["cpu"] = cpu_info
        
        # GPU detection
        gpu_info = self._detect_gpu()
        if gpu_info:
            self.devices["gpu"] = gpu_info
        
        logger.info(f"Detected {len(self.devices)} devices")
    
    def _detect_cpu(self) -> Optional[DeviceInfo]:
        """Detect CPU information"""
        if not HAS_PSUTIL:
            return None
        
        try:
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            memory = psutil.virtual_memory()
            
            architecture = Architecture.X86_64
            if platform.machine() == "arm64":
                architecture = Architecture.ARM64
            elif platform.machine() == "arm":
                architecture = Architecture.ARM
            elif platform.machine() == "x86_64":
                architecture = Architecture.X86_64
            
            return DeviceInfo(
                name=platform.processor() or "CPU",
                type=DeviceType.CPU,
                architecture=architecture,
                cores=cpu_count or 0,
                memory_gb=memory.total / (1024 ** 3),
                clock_speed_mhz=cpu_freq.current if cpu_freq else 0,
                temperature_celsius=self._get_cpu_temperature(),
                status=DeviceStatus.HEALTHY,
                load_percent=psutil.cpu_percent(),
                memory_used_percent=memory.percent,
            )
        except Exception as e:
            logger.error(f"Failed to detect CPU: {e}")
            return None
    
    def _detect_gpu(self) -> Optional[DeviceInfo]:
        """Detect GPU information"""
        gpu_info = None
        
        # Try PyTorch
        if HAS_TORCH and torch.cuda.is_available():
            try:
                device_count = torch.cuda.device_count()
                if device_count > 0:
                    # Get first GPU info
                    gpu_name = torch.cuda.get_device_name(0)
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                    
                    gpu_info = DeviceInfo(
                        name=gpu_name,
                        type=DeviceType.GPU,
                        architecture=Architecture.X86_64,
                        cores=torch.cuda.device_count(),
                        memory_gb=gpu_memory,
                        clock_speed_mhz=0,
                        temperature_celsius=self._get_gpu_temperature(),
                        status=DeviceStatus.HEALTHY,
                        load_percent=0,
                        memory_used_percent=0,
                    )
            except Exception as e:
                logger.debug(f"PyTorch GPU detection failed: {e}")
        
        # Try TensorFlow
        if not gpu_info and HAS_TENSORFLOW:
            try:
                gpus = tf.config.experimental.list_physical_devices('GPU')
                if gpus:
                    gpu_info = DeviceInfo(
                        name=str(gpus[0]),
                        type=DeviceType.GPU,
                        architecture=Architecture.X86_64,
                        cores=len(gpus),
                        memory_gb=0,  # Cannot easily get
                        clock_speed_mhz=0,
                        temperature_celsius=0,
                        status=DeviceStatus.HEALTHY,
                        load_percent=0,
                        memory_used_percent=0,
                    )
            except Exception as e:
                logger.debug(f"TensorFlow GPU detection failed: {e}")
        
        return gpu_info
    
    def _get_cpu_temperature(self) -> float:
        """Get CPU temperature"""
        try:
            if sys.platform == "linux":
                # Linux: read from thermal zone
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = int(f.read()) / 1000.0
                    return temp
            elif sys.platform == "darwin":
                # macOS: use osx-cpu-temp
                result = subprocess.run(["osx-cpu-temp"], capture_output=True, text=True)
                if result.returncode == 0:
                    return float(result.stdout.strip().replace("°C", ""))
            elif sys.platform == "win32":
                # Windows: use WMI
                import wmi
                w = wmi.WMI()
                for sensor in w.Win32_TemperatureProbe():
                    if sensor.CurrentReading:
                        return sensor.CurrentReading / 10.0
        except:
            pass
        return 0.0
    
    def _get_gpu_temperature(self) -> float:
        """Get GPU temperature"""
        try:
            if HAS_TORCH and torch.cuda.is_available():
                # PyTorch GPU temperature (limited support)
                pass
        except:
            pass
        return 0.0
    
    # ============================================================
    # OPTIMIZATIONS
    # ============================================================
    
    def _init_optimizations(self) -> None:
        """Initialize device optimizations"""
        for device_name, device in self.devices.items():
            if device.type == DeviceType.CPU:
                self.optimizations[device_name] = DeviceOptimization(
                    device_type=DeviceType.CPU,
                    batch_size=32,
                    threads=device.cores,
                    memory_limit_gb=device.memory_gb * 0.5,
                    use_gpu=False,
                )
            elif device.type == DeviceType.GPU:
                self.optimizations[device_name] = DeviceOptimization(
                    device_type=DeviceType.GPU,
                    batch_size=64,
                    threads=4,
                    memory_limit_gb=device.memory_gb * 0.8,
                    use_gpu=True,
                )
    
    def get_optimization(self, device_name: str) -> Optional[DeviceOptimization]:
        """
        Get device optimization settings
        
        Args:
            device_name: Device name
            
        Returns:
            DeviceOptimization or None
        """
        return self.optimizations.get(device_name)
    
    def update_optimization(
        self,
        device_name: str,
        updates: Dict[str, Any]
    ) -> Optional[DeviceOptimization]:
        """
        Update device optimization settings
        
        Args:
            device_name: Device name
            updates: Updates to apply
            
        Returns:
            Updated DeviceOptimization or None
        """
        optimization = self.optimizations.get(device_name)
        if not optimization:
            return None
        
        for key, value in updates.items():
            if hasattr(optimization, key):
                setattr(optimization, key, value)
        
        return optimization
    
    # ============================================================
    # METRICS COLLECTION
    # ============================================================
    
    def collect_metrics(self) -> Dict[str, List[DeviceMetric]]:
        """
        Collect current device metrics
        
        Returns:
            Dictionary of device metrics
        """
        metrics = {}
        
        # Update CPU metrics
        if "cpu" in self.devices:
            cpu_metrics = self._collect_cpu_metrics()
            metrics["cpu"] = cpu_metrics
            self._update_device_status("cpu")
        
        # Update GPU metrics
        if "gpu" in self.devices:
            gpu_metrics = self._collect_gpu_metrics()
            metrics["gpu"] = gpu_metrics
            self._update_device_status("gpu")
        
        return metrics
    
    def _collect_cpu_metrics(self) -> List[DeviceMetric]:
        """Collect CPU metrics"""
        metrics = []
        if not HAS_PSUTIL:
            return metrics
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent()
            metrics.append(DeviceMetric(
                device_name="cpu",
                metric_type="usage",
                value=cpu_percent,
                unit="%",
            ))
            
            # CPU frequency
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                metrics.append(DeviceMetric(
                    device_name="cpu",
                    metric_type="frequency",
                    value=cpu_freq.current,
                    unit="MHz",
                ))
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics.append(DeviceMetric(
                device_name="cpu",
                metric_type="memory_usage",
                value=memory.percent,
                unit="%",
            ))
            
            # Temperature
            temp = self._get_cpu_temperature()
            if temp > 0:
                metrics.append(DeviceMetric(
                    device_name="cpu",
                    metric_type="temperature",
                    value=temp,
                    unit="°C",
                ))
            
            # Store in history
            self.metrics_history.setdefault("cpu", []).extend(metrics)
            self._trim_history("cpu")
            
        except Exception as e:
            logger.error(f"Failed to collect CPU metrics: {e}")
        
        return metrics
    
    def _collect_gpu_metrics(self) -> List[DeviceMetric]:
        """Collect GPU metrics"""
        metrics = []
        
        try:
            if HAS_TORCH and torch.cuda.is_available():
                # GPU memory usage
                for i in range(torch.cuda.device_count()):
                    try:
                        allocated = torch.cuda.memory_allocated(i) / (1024 ** 3)
                        reserved = torch.cuda.memory_reserved(i) / (1024 ** 3)
                        
                        metrics.append(DeviceMetric(
                            device_name=f"gpu_{i}",
                            metric_type="memory_allocated",
                            value=allocated,
                            unit="GB",
                        ))
                        metrics.append(DeviceMetric(
                            device_name=f"gpu_{i}",
                            metric_type="memory_reserved",
                            value=reserved,
                            unit="GB",
                        ))
                    except:
                        pass
            
            # Store in history
            self.metrics_history.setdefault("gpu", []).extend(metrics)
            self._trim_history("gpu")
            
        except Exception as e:
            logger.error(f"Failed to collect GPU metrics: {e}")
        
        return metrics
    
    def _update_device_status(self, device_name: str) -> None:
        """Update device status based on metrics"""
        device = self.devices.get(device_name)
        if not device:
            return
        
        metrics = self.metrics_history.get(device_name, [])
        if not metrics:
            return
        
        # Check for overloaded
        for metric in metrics[-10:]:
            if metric.metric_type == "usage" and metric.value > 90:
                device.status = DeviceStatus.OVERLOADED
                break
            elif metric.metric_type == "temperature" and metric.value > 80:
                device.status = DeviceStatus.DEGRADED
                break
            else:
                device.status = DeviceStatus.HEALTHY
        
        # Update current values
        for metric in metrics[-1:]:
            if metric.metric_type == "usage":
                device.load_percent = metric.value
            elif metric.metric_type == "memory_usage":
                device.memory_used_percent = metric.value
            elif metric.metric_type == "temperature":
                device.temperature_celsius = metric.value
    
    def _trim_history(self, device_name: str) -> None:
        """Trim metric history to prevent unlimited growth"""
        if device_name in self.metrics_history:
            history = self.metrics_history[device_name]
            if len(history) > 1000:
                self.metrics_history[device_name] = history[-1000:]
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get device statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "devices": {k: v.to_dict() for k, v in self.devices.items()},
            "optimizations": {k: v.to_dict() for k, v in self.optimizations.items()},
            "metrics_history": {
                k: len(v) for k, v in self.metrics_history.items()
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "DeviceType",
    "DeviceStatus",
    "Architecture",
    
    # Dataclasses
    "DeviceInfo",
    "DeviceMetric",
    "DeviceOptimization",
    
    # Classes
    "DataDeviceEngine",
]

# ============================================================
# END OF MODULE
# ============================================================

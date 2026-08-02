# trading/bots/hedge_bot/hedge_bot_installer.py

import asyncio
import logging
import os
import sys
import subprocess
import platform
import shutil
import json
import hashlib
import tempfile
import tarfile
import zipfile
import urllib.request
import urllib.parse
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class InstallType(str, Enum):
    FULL = "full"
    MINIMAL = "minimal"
    CUSTOM = "custom"
    UPGRADE = "upgrade"
    PATCH = "patch"
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    CLOUD = "cloud"


class InstallStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class PackageManager(str, Enum):
    PIP = "pip"
    CONDA = "conda"
    POETRY = "poetry"
    NPM = "npm"
    YARN = "yarn"
    APT = "apt"
    YUM = "yum"
    DNF = "dnf"
    BREW = "brew"
    CHOCOLATEY = "chocolatey"


@dataclass
class InstallPackage:
    name: str
    version: str
    manager: PackageManager
    optional: bool = False
    dev_only: bool = False
    url: Optional[str] = None
    checksum: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstallComponent:
    name: str
    description: str
    required: bool = True
    packages: List[InstallPackage] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    directories: List[str] = field(default_factory=list)
    scripts: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    ports: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstallProfile:
    id: str
    name: str
    description: str
    type: InstallType
    components: List[str]
    environment: Dict[str, str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstallResult:
    id: str
    type: InstallType
    status: InstallStatus
    start_time: float
    end_time: Optional[float] = None
    components_installed: List[str] = field(default_factory=list)
    components_failed: List[str] = field(default_factory=list)
    packages_installed: List[str] = field(default_factory=list)
    packages_failed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstallEnvironment:
    os: str
    os_version: str
    architecture: str
    python_version: str
    node_version: Optional[str] = None
    docker_version: Optional[str] = None
    kubernetes_version: Optional[str] = None
    memory_available: int = 0
    disk_available: int = 0
    cpu_cores: int = 0


class HedgeBotInstaller:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._profiles: Dict[str, InstallProfile] = {}
        self._results: Dict[str, InstallResult] = {}
        self._components: Dict[str, InstallComponent] = {}
        self._environment: Optional[InstallEnvironment] = None
        self._install_path: str = ""
        self._temp_dir: Optional[str] = None
        self._current_result: Optional[InstallResult] = None
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_profiles()
        self._initialize_components()

    def _initialize_default_profiles(self) -> None:
        profiles = [
            InstallProfile(
                id="minimal",
                name="Minimal Installation",
                description="Core components only",
                type=InstallType.MINIMAL,
                components=["core"]
            ),
            InstallProfile(
                id="full",
                name="Full Installation",
                description="All components",
                type=InstallType.FULL,
                components=["core", "ai", "trading", "risk", "data", "monitoring", "api", "frontend"]
            ),
            InstallProfile(
                id="development",
                name="Development Environment",
                description="Full installation with development tools",
                type=InstallType.DEVELOPMENT,
                components=["core", "ai", "trading", "risk", "data", "monitoring", "api", "frontend", "dev_tools"]
            ),
            InstallProfile(
                id="production",
                name="Production Environment",
                description="Optimized for production",
                type=InstallType.PRODUCTION,
                components=["core", "ai", "trading", "risk", "data", "monitoring", "api"]
            ),
            InstallProfile(
                id="docker",
                name="Docker Installation",
                description="Docker container deployment",
                type=InstallType.DOCKER,
                components=["docker"]
            )
        ]
        
        for profile in profiles:
            self._profiles[profile.id] = profile

    def _initialize_components(self) -> None:
        components = [
            InstallComponent(
                name="core",
                description="Core system components",
                required=True,
                packages=[
                    InstallPackage("python", "3.12+", PackageManager.PIP),
                    InstallPackage("fastapi", "0.104+", PackageManager.PIP),
                    InstallPackage("uvicorn", "0.24+", PackageManager.PIP),
                    InstallPackage("pydantic", "2.5+", PackageManager.PIP),
                    InstallPackage("sqlalchemy", "2.0+", PackageManager.PIP),
                ],
                directories=["config", "data", "logs", "temp"]
            ),
            InstallComponent(
                name="ai",
                description="AI and Machine Learning components",
                packages=[
                    InstallPackage("torch", "2.0+", PackageManager.PIP),
                    InstallPackage("scikit-learn", "1.3+", PackageManager.PIP),
                    InstallPackage("transformers", "4.35+", PackageManager.PIP),
                    InstallPackage("langchain", "0.1+", PackageManager.PIP),
                    InstallPackage("xgboost", "2.0+", PackageManager.PIP),
                ]
            ),
            InstallComponent(
                name="trading",
                description="Trading components",
                packages=[
                    InstallPackage("pandas", "2.0+", PackageManager.PIP),
                    InstallPackage("numpy", "1.24+", PackageManager.PIP),
                    InstallPackage("ta-lib", "0.4+", PackageManager.PIP),
                    InstallPackage("ccxt", "4.1+", PackageManager.PIP),
                    InstallPackage("websocket-client", "1.6+", PackageManager.PIP),
                ]
            ),
            InstallComponent(
                name="risk",
                description="Risk management components",
                packages=[
                    InstallPackage("scipy", "1.11+", PackageManager.PIP),
                    InstallPackage("statsmodels", "0.14+", PackageManager.PIP),
                    InstallPackage("arch", "6.0+", PackageManager.PIP),
                ]
            ),
            InstallComponent(
                name="data",
                description="Data processing components",
                packages=[
                    InstallPackage("psycopg2", "2.9+", PackageManager.PIP),
                    InstallPackage("redis", "5.0+", PackageManager.PIP),
                    InstallPackage("clickhouse-driver", "0.2+", PackageManager.PIP),
                    InstallPackage("dask", "2023.12+", PackageManager.PIP),
                ]
            ),
            InstallComponent(
                name="monitoring",
                description="Monitoring and observability",
                packages=[
                    InstallPackage("prometheus-client", "0.19+", PackageManager.PIP),
                    InstallPackage("grafana-api", "1.0+", PackageManager.PIP),
                    InstallPackage("sentry-sdk", "1.38+", PackageManager.PIP),
                    InstallPackage("opentelemetry-api", "1.22+", PackageManager.PIP),
                ]
            ),
            InstallComponent(
                name="api",
                description="API and web components",
                packages=[
                    InstallPackage("fastapi", "0.104+", PackageManager.PIP),
                    InstallPackage("pydantic", "2.5+", PackageManager.PIP),
                    InstallPackage("jwt", "1.3+", PackageManager.PIP),
                    InstallPackage("passlib", "1.7+", PackageManager.PIP),
                ]
            ),
            InstallComponent(
                name="frontend",
                description="Frontend components",
                packages=[
                    InstallPackage("nodejs", "20+", PackageManager.NPM),
                    InstallPackage("react", "18+", PackageManager.NPM),
                    InstallPackage("next", "14+", PackageManager.NPM),
                    InstallPackage("tailwindcss", "3.4+", PackageManager.NPM),
                ]
            ),
            InstallComponent(
                name="dev_tools",
                description="Development tools",
                packages=[
                    InstallPackage("pytest", "7.4+", PackageManager.PIP),
                    InstallPackage("black", "23.11+", PackageManager.PIP),
                    InstallPackage("ruff", "0.1+", PackageManager.PIP),
                    InstallPackage("mypy", "1.7+", PackageManager.PIP),
                    InstallPackage("pre-commit", "3.5+", PackageManager.PIP),
                ],
                metadata={"dev_only": True}
            ),
            InstallComponent(
                name="docker",
                description="Docker deployment",
                packages=[
                    InstallPackage("docker", "24.0+", PackageManager.PIP),
                    InstallPackage("docker-compose", "2.23+", PackageManager.PIP),
                ],
                directories=["docker", "docker-compose.yml"]
            )
        ]
        
        for component in components:
            self._components[component.name] = component

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def detect_environment(self) -> InstallEnvironment:
        os_name = platform.system()
        os_version = platform.version()
        arch = platform.machine()
        
        python_version = platform.python_version()
        
        try:
            node_version = subprocess.check_output(["node", "--version"], text=True).strip()
        except:
            node_version = None
        
        try:
            docker_version = subprocess.check_output(["docker", "--version"], text=True).strip()
        except:
            docker_version = None
        
        try:
            kubectl_version = subprocess.check_output(["kubectl", "version", "--client", "-o", "json"], text=True)
            kubernetes_version = json.loads(kubectl_version).get("clientVersion", {}).get("gitVersion")
        except:
            kubernetes_version = None
        
        import psutil
        memory_available = psutil.virtual_memory().available
        disk_available = psutil.disk_usage("/").free
        cpu_cores = psutil.cpu_count()
        
        self._environment = InstallEnvironment(
            os=os_name,
            os_version=os_version,
            architecture=arch,
            python_version=python_version,
            node_version=node_version,
            docker_version=docker_version,
            kubernetes_version=kubernetes_version,
            memory_available=memory_available,
            disk_available=disk_available,
            cpu_cores=cpu_cores
        )
        
        return self._environment

    async def install(
        self,
        profile_id: str,
        install_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> InstallResult:
        async with self._lock:
            if profile_id not in self._profiles:
                raise ValueError(f"Profile not found: {profile_id}")
            
            profile = self._profiles[profile_id]
            
            result = InstallResult(
                id=str(hashlib.md5(f"{profile_id}_{time.time()}".encode()).hexdigest()),
                type=profile.type,
                status=InstallStatus.PENDING,
                start_time=time.time()
            )
            
            self._results[result.id] = result
            self._current_result = result
            self._install_path = install_path
            
            result.status = InstallStatus.RUNNING
            await self._notify_observers("install_started", result)
            
            try:
                await self._ensure_environment()
                await self._prepare_installation(profile, install_path, options)
                await self._install_components(profile, result)
                await self._post_installation(profile, result)
                
                result.status = InstallStatus.COMPLETED
                result.end_time = time.time()
                
                await self._notify_observers("install_completed", result)
                
            except Exception as e:
                result.status = InstallStatus.FAILED
                result.end_time = time.time()
                result.errors.append(str(e))
                
                logger.error(f"Installation failed: {e}")
                await self._notify_observers("install_failed", result)
            
            self._current_result = None
            return result

    async def _ensure_environment(self) -> None:
        if not self._environment:
            await self.detect_environment()

    async def _prepare_installation(
        self,
        profile: InstallProfile,
        install_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> None:
        os.makedirs(install_path, exist_ok=True)
        
        for component_name in profile.components:
            if component_name in self._components:
                component = self._components[component_name]
                
                for directory in component.directories:
                    dir_path = os.path.join(install_path, directory)
                    os.makedirs(dir_path, exist_ok=True)
        
        self._temp_dir = tempfile.mkdtemp()

    async def _install_components(
        self,
        profile: InstallProfile,
        result: InstallResult
    ) -> None:
        for component_name in profile.components:
            if component_name not in self._components:
                continue
            
            component = self._components[component_name]
            
            try:
                await self._install_component(component, result)
                result.components_installed.append(component_name)
                
            except Exception as e:
                logger.error(f"Failed to install component {component_name}: {e}")
                result.components_failed.append(component_name)
                result.errors.append(f"{component_name}: {str(e)}")
                
                if component.required and not self.config.get("ignore_required_failures", False):
                    raise

    async def _install_component(
        self,
        component: InstallComponent,
        result: InstallResult
    ) -> None:
        logger.info(f"Installing component: {component.name}")
        await self._notify_observers("component_installing", component)
        
        for package in component.packages:
            try:
                await self._install_package(package, result)
                result.packages_installed.append(package.name)
                
            except Exception as e:
                logger.error(f"Failed to install package {package.name}: {e}")
                result.packages_failed.append(package.name)
                
                if not package.optional:
                    raise
        
        for script in component.scripts:
            await self._run_script(script, component)
        
        for file in component.files:
            await self._copy_file(file, self._install_path)
        
        if component.environment:
            await self._setup_environment(component.environment)

    async def _install_package(
        self,
        package: InstallPackage,
        result: InstallResult
    ) -> None:
        logger.info(f"Installing package: {package.name}=={package.version}")
        
        if package.manager == PackageManager.PIP:
            cmd = [sys.executable, "-m", "pip", "install", f"{package.name}=={package.version}"]
            
            if self.config.get("use_venv", False):
                venv_path = os.path.join(self._install_path, "venv")
                cmd = [os.path.join(venv_path, "bin", "python"), "-m", "pip", "install", f"{package.name}=={package.version}"]
        
        elif package.manager == PackageManager.NPM:
            cmd = ["npm", "install", f"{package.name}@{package.version}"]
        
        elif package.manager == PackageManager.POETRY:
            cmd = ["poetry", "add", f"{package.name}=={package.version}"]
        
        elif package.manager == PackageManager.APT:
            cmd = ["sudo", "apt-get", "install", "-y", f"{package.name}={package.version}"]
        
        elif package.manager == PackageManager.BREW:
            cmd = ["brew", "install", f"{package.name}@{package.version}"]
        
        else:
            raise ValueError(f"Unsupported package manager: {package.manager}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._install_path
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Package installation failed: {stderr.decode()}")
        
        result.logs.append(f"Installed {package.name} {package.version}")

    async def _run_script(self, script: str, component: InstallComponent) -> None:
        script_path = os.path.join(self._install_path, script)
        
        if not os.path.exists(script_path):
            return
        
        process = await asyncio.create_subprocess_exec(
            "bash", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._install_path
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"Script execution failed: {stderr.decode()}")

    async def _copy_file(self, source: str, dest_dir: str) -> None:
        if not os.path.exists(source):
            return
        
        dest_path = os.path.join(dest_dir, os.path.basename(source))
        shutil.copy2(source, dest_path)

    async def _setup_environment(self, env_vars: Dict[str, str]) -> None:
        env_path = os.path.join(self._install_path, ".env")
        
        with open(env_path, "a") as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

    async def _post_installation(
        self,
        profile: InstallProfile,
        result: InstallResult
    ) -> None:
        await self._create_config_files(profile)
        await self._setup_services(profile)
        await self._create_launcher_scripts(profile)
        await self._verify_installation(profile, result)

    async def _create_config_files(self, profile: InstallProfile) -> None:
        config_path = os.path.join(self._install_path, "config")
        os.makedirs(config_path, exist_ok=True)
        
        config = {
            "version": "1.0.0",
            "install_type": profile.type.value,
            "profile": profile.id,
            "components": profile.components,
            "environment": self._environment.__dict__ if self._environment else {},
            "install_path": self._install_path,
            "created_at": datetime.now().isoformat()
        }
        
        with open(os.path.join(config_path, "install.json"), "w") as f:
            json.dump(config, f, indent=2)

    async def _setup_services(self, profile: InstallProfile) -> None:
        services_path = os.path.join(self._install_path, "services")
        os.makedirs(services_path, exist_ok=True)
        
        service_file = os.path.join(services_path, "nexus.service")
        
        service_content = f"""[Unit]
Description=Nexus AI Trading System
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'root')}
WorkingDirectory={self._install_path}
ExecStart={sys.executable} -m nexus.main
Restart=always
RestartSec=10
EnvironmentFile={self._install_path}/.env

[Install]
WantedBy=multi-user.target
"""
        
        with open(service_file, "w") as f:
            f.write(service_content)

    async def _create_launcher_scripts(self, profile: InstallProfile) -> None:
        scripts = [
            ("start.sh", "#!/bin/bash\npython -m nexus.main"),
            ("stop.sh", "#!/bin/bash\npkill -f nexus.main"),
            ("restart.sh", "#!/bin/bash\n./stop.sh\n./start.sh"),
            ("status.sh", "#!/bin/bash\nps aux | grep nexus.main | grep -v grep")
        ]
        
        for name, content in scripts:
            script_path = os.path.join(self._install_path, name)
            with open(script_path, "w") as f:
                f.write(content)
            os.chmod(script_path, 0o755)

    async def _verify_installation(
        self,
        profile: InstallProfile,
        result: InstallResult
    ) -> None:
        for component_name in profile.components:
            if component_name not in self._components:
                continue
            
            component = self._components[component_name]
            
            for package in component.packages:
                try:
                    await self._verify_package(package)
                except Exception as e:
                    result.warnings.append(f"Package {package.name} verification failed: {e}")

    async def _verify_package(self, package: InstallPackage) -> None:
        if package.manager == PackageManager.PIP:
            cmd = [sys.executable, "-m", "pip", "show", package.name]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise RuntimeError(f"Package {package.name} not found")

    async def upgrade(
        self,
        install_path: str,
        version: Optional[str] = None
    ) -> InstallResult:
        result = InstallResult(
            id=str(hashlib.md5(f"upgrade_{time.time()}".encode()).hexdigest()),
            type=InstallType.UPGRADE,
            status=InstallStatus.PENDING,
            start_time=time.time()
        )
        
        self._results[result.id] = result
        self._install_path = install_path
        
        try:
            result.status = InstallStatus.RUNNING
            
            await self._backup_configuration(install_path)
            await self._upgrade_packages(version, result)
            await self._migrate_configuration(install_path, result)
            
            result.status = InstallStatus.COMPLETED
            result.end_time = time.time()
            
        except Exception as e:
            result.status = InstallStatus.FAILED
            result.end_time = time.time()
            result.errors.append(str(e))
        
        return result

    async def _backup_configuration(self, install_path: str) -> None:
        config_path = os.path.join(install_path, "config")
        backup_path = os.path.join(install_path, "backup")
        
        if os.path.exists(config_path):
            shutil.copytree(config_path, backup_path, dirs_exist_ok=True)

    async def _upgrade_packages(self, version: Optional[str], result: InstallResult) -> None:
        for component in self._components.values():
            for package in component.packages:
                try:
                    if package.manager == PackageManager.PIP:
                        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", package.name]
                        if version:
                            cmd = [sys.executable, "-m", "pip", "install", f"{package.name}=={version}"]
                        
                        process = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            cwd=self._install_path
                        )
                        
                        stdout, stderr = await process.communicate()
                        
                        if process.returncode == 0:
                            result.packages_installed.append(package.name)
                        else:
                            result.packages_failed.append(package.name)
                            
                except Exception as e:
                    logger.error(f"Failed to upgrade {package.name}: {e}")

    async def _migrate_configuration(
        self,
        install_path: str,
        result: InstallResult
    ) -> None:
        config_path = os.path.join(install_path, "config")
        backup_path = os.path.join(install_path, "backup")
        
        if os.path.exists(backup_path):
            # Merge backup with new config
            for file in os.listdir(backup_path):
                backup_file = os.path.join(backup_path, file)
                config_file = os.path.join(config_path, file)
                
                if os.path.exists(backup_file) and not os.path.exists(config_file):
                    shutil.copy2(backup_file, config_file)

    async def uninstall(self, install_path: str, keep_config: bool = True) -> bool:
        try:
            if keep_config:
                config_path = os.path.join(install_path, "config")
                backup_path = os.path.join(os.path.dirname(install_path), "backup_config")
                
                if os.path.exists(config_path):
                    shutil.copytree(config_path, backup_path, dirs_exist_ok=True)
            
            shutil.rmtree(install_path)
            
            logger.info(f"Uninstalled from {install_path}")
            return True
            
        except Exception as e:
            logger.error(f"Uninstall failed: {e}")
            return False

    async def get_install_status(self, result_id: str) -> Optional[InstallResult]:
        return self._results.get(result_id)

    async def get_profiles(self) -> List[InstallProfile]:
        return list(self._profiles.values())

    async def get_profile(self, profile_id: str) -> Optional[InstallProfile]:
        return self._profiles.get(profile_id)

    async def get_components(self) -> List[InstallComponent]:
        return list(self._components.values())

    async def get_component(self, component_name: str) -> Optional[InstallComponent]:
        return self._components.get(component_name)

    async def get_environment(self) -> Optional[InstallEnvironment]:
        if not self._environment:
            await self.detect_environment()
        return self._environment

    async def validate_installation(self, install_path: str) -> bool:
        required_files = [
            "config/install.json",
            "venv",
            "services/nexus.service"
        ]
        
        for file_path in required_files:
            full_path = os.path.join(install_path, file_path)
            if not os.path.exists(full_path):
                return False
        
        return True

    def _get_install_dir(self) -> str:
        return self._install_path

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
            "profiles": len(self._profiles),
            "components": len(self._components),
            "results": len(self._results),
            "running": self._running,
            "environment": self._environment.__dict__ if self._environment else None
        }


__all__ = [
    "InstallType",
    "InstallStatus",
    "PackageManager",
    "InstallPackage",
    "InstallComponent",
    "InstallProfile",
    "InstallResult",
    "InstallEnvironment",
    "HedgeBotInstaller"
]

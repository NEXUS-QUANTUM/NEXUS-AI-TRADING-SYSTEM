# blockchain/smart-contracts/contract_compiler.py
# NEXUS AI TRADING SYSTEM - Smart Contract Compiler Framework
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced Smart Contract Compiler Framework for NEXUS AI Trading System.
Provides compilation, optimization, and verification of smart contracts
across multiple Solidity versions and compiler configurations.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
import requests
from web3 import Web3

# NEXUS Imports
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.compiler")


# ============================================================================
# Enums & Constants
# ============================================================================

class CompilerType(str, Enum):
    """Supported compiler types."""
    SOLC = "solc"
    VYPER = "vyper"
    YUL = "yul"
    HARDFAT = "hardhat"
    TRUFFLE = "truffle"
    FOUNDRY = "foundry"
    REMIX = "remix"


class OptimizationLevel(str, Enum):
    """Optimization levels."""
    NONE = "none"
    BASIC = "basic"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    EXTREME = "extreme"


class OutputFormat(str, Enum):
    """Output formats."""
    JSON = "json"
    BIN = "bin"
    BIN_RUNTIME = "bin-runtime"
    ABI = "abi"
    METADATA = "metadata"
    AST = "ast"
    OPCodes = "opcodes"
    IR = "ir"


class CompilerStatus(str, Enum):
    """Compilation status."""
    PENDING = "pending"
    COMPILING = "compiling"
    SUCCESS = "success"
    FAILED = "failed"
    OPTIMIZING = "optimizing"
    VERIFYING = "verifying"


@dataclass
class CompilerConfig:
    """Compiler configuration."""
    compiler_type: CompilerType = CompilerType.SOLC
    version: str = "0.8.20"
    optimization_level: OptimizationLevel = OptimizationLevel.STANDARD
    optimization_runs: int = 200
    evm_version: str = "london"
    output_formats: List[OutputFormat] = field(default_factory=lambda: [OutputFormat.ABI, OutputFormat.BIN])
    remappings: List[str] = field(default_factory=list)
    libraries: Dict[str, str] = field(default_factory=dict)
    base_path: Optional[str] = None
    include_paths: List[str] = field(default_factory=list)
    allow_paths: List[str] = field(default_factory=list)
    stop_after: Optional[str] = None
    no_metadata: bool = False
    metadata_hash: str = "ipfs"
    via_ir: bool = False
    experimental: Dict[str, bool] = field(default_factory=dict)


@dataclass
class CompilationResult:
    """Compilation result."""
    contract_name: str
    compiler_type: CompilerType
    compiler_version: str
    status: CompilerStatus
    abi: Optional[List[Dict[str, Any]]] = None
    bytecode: Optional[str] = None
    bytecode_runtime: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    ast: Optional[Dict[str, Any]] = None
    opcodes: Optional[str] = None
    ir: Optional[str] = None
    source_maps: Optional[str] = None
    gas_estimates: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    optimization_report: Optional[Dict[str, Any]] = None
    compilation_time_ms: float = 0.0
    file_path: Optional[str] = None


@dataclass
class ContractSource:
    """Contract source code."""
    name: str
    source: str
    path: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    version_pragma: Optional[str] = None


# ============================================================================
# Compiler Framework
# ============================================================================

class ContractCompiler:
    """
    Advanced Smart Contract Compiler Framework.
    Provides compilation, optimization, and verification of smart contracts.
    """

    # Solidity versions available
    SOLC_VERSIONS = [
        "0.8.26", "0.8.25", "0.8.24", "0.8.23", "0.8.22", "0.8.21",
        "0.8.20", "0.8.19", "0.8.18", "0.8.17", "0.8.16", "0.8.15",
        "0.8.14", "0.8.13", "0.8.12", "0.8.11", "0.8.10", "0.8.9",
        "0.8.8", "0.8.7", "0.8.6", "0.8.5", "0.8.4", "0.8.3",
        "0.8.2", "0.8.1", "0.8.0",
        "0.7.6", "0.7.5", "0.7.4", "0.7.3", "0.7.2", "0.7.1", "0.7.0",
        "0.6.12", "0.6.11", "0.6.10", "0.6.9", "0.6.8",
    ]

    # Standard library paths
    STD_LIBS = {
        "openzeppelin": "https://github.com/OpenZeppelin/openzeppelin-contracts.git",
        "forge-std": "https://github.com/foundry-rs/forge-std.git",
        "solmate": "https://github.com/transmissions11/solmate.git",
        "prb-math": "https://github.com/paulrberg/prb-math.git",
        "ds-test": "https://github.com/dapphub/ds-test.git",
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or {}
        self._temp_dir = None
        self._compilers_available: Dict[CompilerType, bool] = {}
        self._cache: Dict[str, CompilationResult] = {}
        self._source_cache: Dict[str, ContractSource] = {}

        # Performance metrics
        self._performance = {
            "compilations": 0,
            "successful": 0,
            "failed": 0,
            "avg_compilation_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Detect available compilers
        self._detect_compilers()

        logger.info(
            "ContractCompiler initialized",
            extra={
                "compilers_available": self._compilers_available,
                "solc_versions": len(self.SOLC_VERSIONS),
            }
        )

    # -----------------------------------------------------------------------
    # Compiler Detection
    # -----------------------------------------------------------------------

    def _detect_compilers(self) -> None:
        """Detect available compilers on the system."""
        # Check for solc
        self._compilers_available[CompilerType.SOLC] = self._check_solc()

        # Check for vyper
        self._compilers_available[CompilerType.VYPER] = self._check_vyper()

        # Check for hardhat
        self._compilers_available[CompilerType.HARDFAT] = self._check_hardhat()

        # Check for truffle
        self._compilers_available[CompilerType.TRUFFLE] = self._check_truffle()

        # Check for foundry
        self._compilers_available[CompilerType.FOUNDRY] = self._check_foundry()

    def _check_solc(self) -> bool:
        """Check if solc is available."""
        try:
            result = subprocess.run(
                ["solc", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_vyper(self) -> bool:
        """Check if vyper is available."""
        try:
            result = subprocess.run(
                ["vyper", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_hardhat(self) -> bool:
        """Check if hardhat is available."""
        try:
            result = subprocess.run(
                ["npx", "hardhat", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=os.getcwd(),
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_truffle(self) -> bool:
        """Check if truffle is available."""
        try:
            result = subprocess.run(
                ["truffle", "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_foundry(self) -> bool:
        """Check if foundry is available."""
        try:
            result = subprocess.run(
                ["forge", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Solidity Compilation
    # -----------------------------------------------------------------------

    async def compile_solidity(
        self,
        source: Union[str, ContractSource],
        config: Optional[CompilerConfig] = None,
        force_refresh: bool = False,
    ) -> Optional[CompilationResult]:
        """
        Compile Solidity source code.

        Args:
            source: Source code or ContractSource
            config: Compiler configuration
            force_refresh: Force recompilation

        Returns:
            CompilationResult or None if error
        """
        start_time = time.time()

        # Get source string
        if isinstance(source, ContractSource):
            source_code = source.source
            source_name = source.name
        else:
            source_code = source
            source_name = f"contract_{hash(source) % 10000}"

        # Check cache
        cache_key = f"{source_name}_{hash(source_code)}_{hash(str(config))}"
        if not force_refresh and cache_key in self._cache:
            self._performance["cache_hits"] += 1
            return self._cache[cache_key]

        self._performance["cache_misses"] += 1

        # Use default config if none provided
        if config is None:
            config = CompilerConfig()

        # Check if solc is available
        if not self._compilers_available.get(CompilerType.SOLC, False):
            logger.warning("solc not available, using online compiler")
            return await self._compile_online(source_code, source_name, config)

        try:
            # Write source to temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.sol',
                delete=False
            ) as f:
                f.write(source_code)
                temp_file = f.name

            # Build compilation command
            cmd = self._build_solc_command(temp_file, config)

            # Run compiler
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Clean up temp file
            os.unlink(temp_file)

            if result.returncode != 0:
                logger.error(f"Compilation failed: {result.stderr}")
                return self._create_error_result(
                    source_name,
                    CompilerType.SOLC,
                    config.version,
                    result.stderr.split('\n')
                )

            # Parse output
            compilation_result = self._parse_solc_output(
                result.stdout,
                source_name,
                config
            )

            # Add performance metrics
            compilation_result.compilation_time_ms = (time.time() - start_time) * 1000

            # Cache result
            self._cache[cache_key] = compilation_result
            self._performance["compilations"] += 1
            self._performance["successful"] += 1
            self._performance["avg_compilation_time_ms"] = (
                (self._performance["avg_compilation_time_ms"] *
                 (self._performance["compilations"] - 1) +
                 compilation_result.compilation_time_ms) /
                self._performance["compilations"]
            )

            logger.info(
                f"Compilation successful: {source_name}",
                extra={
                    "time_ms": compilation_result.compilation_time_ms,
                    "warnings": len(compilation_result.warnings),
                }
            )

            return compilation_result

        except subprocess.TimeoutExpired:
            logger.error("Compilation timed out")
            return self._create_error_result(
                source_name,
                CompilerType.SOLC,
                config.version,
                ["Compilation timed out"]
            )
        except Exception as e:
            logger.error(f"Compilation error: {e}")
            return self._create_error_result(
                source_name,
                CompilerType.SOLC,
                config.version,
                [str(e)]
            )

    def _build_solc_command(
        self,
        file_path: str,
        config: CompilerConfig,
    ) -> List[str]:
        """Build solc command line."""
        cmd = ["solc"]

        # Version
        if config.version:
            cmd.extend(["--version", config.version])

        # EVM version
        if config.evm_version:
            cmd.extend(["--evm-version", config.evm_version])

        # Optimization
        if config.optimization_level != OptimizationLevel.NONE:
            cmd.append("--optimize")
            cmd.extend(["--optimize-runs", str(config.optimization_runs)])

        # Output formats
        outputs = []
        if OutputFormat.ABI in config.output_formats:
            outputs.append("abi")
        if OutputFormat.BIN in config.output_formats:
            outputs.append("bin")
        if OutputFormat.BIN_RUNTIME in config.output_formats:
            outputs.append("bin-runtime")
        if OutputFormat.METADATA in config.output_formats:
            outputs.append("metadata")
        if OutputFormat.AST in config.output_formats:
            outputs.append("ast")
        if OutputFormat.OPCodes in config.output_formats:
            outputs.append("opcodes")
        if OutputFormat.IR in config.output_formats:
            outputs.append("ir")

        if outputs:
            cmd.extend(["--combined-json", ",".join(outputs)])

        # Metadata
        if config.no_metadata:
            cmd.append("--no-metadata")

        # via IR
        if config.via_ir:
            cmd.append("--via-ir")

        # Include paths
        for path in config.include_paths:
            cmd.extend(["--include-path", path])

        # Allow paths
        for path in config.allow_paths:
            cmd.extend(["--allow-paths", path])

        # Base path
        if config.base_path:
            cmd.extend(["--base-path", config.base_path])

        # Stop after
        if config.stop_after:
            cmd.extend(["--stop-after", config.stop_after])

        # Remappings
        for remap in config.remappings:
            cmd.extend(["--remappings", remap])

        # Libraries
        for lib, addr in config.libraries.items():
            cmd.extend(["--libraries", f"{lib}:{addr}"])

        # Input file
        cmd.append(file_path)

        return cmd

    def _parse_solc_output(
        self,
        output: str,
        contract_name: str,
        config: CompilerConfig,
    ) -> CompilationResult:
        """Parse solc combined JSON output."""
        try:
            data = json.loads(output)
            contracts = data.get("contracts", {})

            result = CompilationResult(
                contract_name=contract_name,
                compiler_type=CompilerType.SOLC,
                compiler_version=config.version,
                status=CompilerStatus.SUCCESS,
            )

            # Extract contract data
            for file_path, file_contracts in contracts.items():
                for name, contract_data in file_contracts.items():
                    if name == contract_name or not contract_name:
                        # Extract ABI
                        if "abi" in contract_data:
                            try:
                                result.abi = json.loads(contract_data["abi"])
                            except:
                                result.abi = None

                        # Extract bytecode
                        if "bin" in contract_data:
                            result.bytecode = "0x" + contract_data["bin"]

                        if "bin-runtime" in contract_data:
                            result.bytecode_runtime = "0x" + contract_data["bin-runtime"]

                        # Extract metadata
                        if "metadata" in contract_data:
                            try:
                                result.metadata = json.loads(contract_data["metadata"])
                            except:
                                result.metadata = None

                        # Extract AST
                        if "ast" in contract_data:
                            result.ast = contract_data["ast"]

                        # Extract opcodes
                        if "opcodes" in contract_data:
                            result.opcodes = contract_data["opcodes"]

                        # Extract IR
                        if "ir" in contract_data:
                            result.ir = contract_data["ir"]

                        # Source maps
                        if "srcmap" in contract_data:
                            result.source_maps = contract_data["srcmap"]

                        break

            # Extract warnings and errors
            errors = data.get("errors", [])
            for error in errors:
                if error.get("severity") == "error":
                    result.errors.append(error.get("message", ""))
                elif error.get("severity") == "warning":
                    result.warnings.append(error.get("message", ""))

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse solc output: {e}")
            return self._create_error_result(
                contract_name,
                CompilerType.SOLC,
                config.version,
                ["Failed to parse compiler output"]
            )

    # -----------------------------------------------------------------------
    # Online Compilation
    # -----------------------------------------------------------------------

    async def _compile_online(
        self,
        source: str,
        source_name: str,
        config: CompilerConfig,
    ) -> Optional[CompilationResult]:
        """
        Compile Solidity using online compiler service.

        Args:
            source: Source code
            source_name: Contract name
            config: Compiler configuration

        Returns:
            CompilationResult or None if error
        """
        try:
            # Use solc-bin API
            url = "https://solc-bin.ethereum.org/"

            # Build request
            payload = {
                "language": "Solidity",
                "sources": {
                    source_name: {
                        "content": source
                    }
                },
                "settings": {
                    "optimizer": {
                        "enabled": config.optimization_level != OptimizationLevel.NONE,
                        "runs": config.optimization_runs,
                    },
                    "evmVersion": config.evm_version,
                    "outputSelection": {
                        "*": {
                            "*": [
                                "abi",
                                "evm.bytecode",
                                "evm.deployedBytecode",
                                "metadata",
                                "ast",
                                "opcodes",
                            ]
                        }
                    }
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{url}compile",
                    json=payload,
                    timeout=30,
                ) as response:
                    if response.status != 200:
                        logger.error(f"Online compilation failed: {response.status}")
                        return self._create_error_result(
                            source_name,
                            CompilerType.SOLC,
                            config.version,
                            [f"Online compilation failed: {response.status}"]
                        )

                    data = await response.json()

                    # Parse result
                    result = CompilationResult(
                        contract_name=source_name,
                        compiler_type=CompilerType.SOLC,
                        compiler_version=config.version,
                        status=CompilerStatus.SUCCESS,
                    )

                    # Extract contract data
                    contracts = data.get("contracts", {}).get(source_name, {})
                    for name, contract_data in contracts.items():
                        # ABI
                        if "abi" in contract_data:
                            result.abi = contract_data["abi"]

                        # Bytecode
                        if "evm" in contract_data:
                            evm = contract_data["evm"]
                            if "bytecode" in evm:
                                result.bytecode = evm["bytecode"].get("object")
                            if "deployedBytecode" in evm:
                                result.bytecode_runtime = evm["deployedBytecode"].get("object")

                        # Metadata
                        if "metadata" in contract_data:
                            result.metadata = contract_data["metadata"]

                        # AST
                        if "ast" in contract_data:
                            result.ast = contract_data["ast"]

                        # Opcodes
                        if "opcodes" in contract_data:
                            result.opcodes = contract_data["opcodes"]

                        # Source maps
                        if "srcmap" in contract_data:
                            result.source_maps = contract_data["srcmap"]

                        break

                    return result

        except Exception as e:
            logger.error(f"Online compilation error: {e}")
            return self._create_error_result(
                source_name,
                CompilerType.SOLC,
                config.version,
                [str(e)]
            )

    # -----------------------------------------------------------------------
    # Vyper Compilation
    # -----------------------------------------------------------------------

    async def compile_vyper(
        self,
        source: Union[str, ContractSource],
        config: Optional[CompilerConfig] = None,
    ) -> Optional[CompilationResult]:
        """
        Compile Vyper source code.

        Args:
            source: Source code or ContractSource
            config: Compiler configuration

        Returns:
            CompilationResult or None if error
        """
        start_time = time.time()

        if isinstance(source, ContractSource):
            source_code = source.source
            source_name = source.name
        else:
            source_code = source
            source_name = f"contract_{hash(source) % 10000}"

        if not self._compilers_available.get(CompilerType.VYPER, False):
            logger.error("Vyper compiler not available")
            return self._create_error_result(
                source_name,
                CompilerType.VYPER,
                "unknown",
                ["Vyper compiler not installed"]
            )

        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.vy',
                delete=False
            ) as f:
                f.write(source_code)
                temp_file = f.name

            # Build command
            cmd = ["vyper", temp_file]

            # Output formats
            if config and OutputFormat.ABI in config.output_formats:
                cmd.append("--abi")
            if config and OutputFormat.BIN in config.output_formats:
                cmd.append("--bytecode")

            # Run compiler
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            os.unlink(temp_file)

            if result.returncode != 0:
                logger.error(f"Vyper compilation failed: {result.stderr}")
                return self._create_error_result(
                    source_name,
                    CompilerType.VYPER,
                    "unknown",
                    result.stderr.split('\n')
                )

            # Parse output
            result_obj = CompilationResult(
                contract_name=source_name,
                compiler_type=CompilerType.VYPER,
                compiler_version="unknown",
                status=CompilerStatus.SUCCESS,
            )

            # Parse output based on format
            output_lines = result.stdout.split('\n')

            # Try to detect ABI
            abi_start = None
            abi_end = None
            for i, line in enumerate(output_lines):
                if line.strip().startswith('[') and 'abi' in line.lower():
                    abi_start = i
                elif abi_start is not None and line.strip().startswith(']'):
                    abi_end = i
                    break

            if abi_start is not None and abi_end is not None:
                abi_lines = output_lines[abi_start:abi_end + 1]
                try:
                    result_obj.abi = json.loads(''.join(abi_lines))
                except:
                    pass

            # Try to detect bytecode
            for line in output_lines:
                if 'bytecode' in line.lower() and '0x' in line:
                    match = re.search(r'0x[a-fA-F0-9]+', line)
                    if match:
                        result_obj.bytecode = match.group()
                elif line.strip().startswith('0x') and len(line.strip()) > 100:
                    result_obj.bytecode = line.strip()

            # Set compilation time
            result_obj.compilation_time_ms = (time.time() - start_time) * 1000

            self._performance["compilations"] += 1
            self._performance["successful"] += 1

            return result_obj

        except Exception as e:
            logger.error(f"Vyper compilation error: {e}")
            return self._create_error_result(
                source_name,
                CompilerType.VYPER,
                "unknown",
                [str(e)]
            )

    # -----------------------------------------------------------------------
    # Hardhat Compilation
    # -----------------------------------------------------------------------

    async def compile_hardhat(
        self,
        project_path: str,
        config: Optional[CompilerConfig] = None,
    ) -> List[CompilationResult]:
        """
        Compile Hardhat project.

        Args:
            project_path: Path to Hardhat project
            config: Compiler configuration

        Returns:
            List of CompilationResult
        """
        start_time = time.time()

        if not self._compilers_available.get(CompilerType.HARDFAT, False):
            logger.error("Hardhat not available")
            return []

        try:
            # Run hardhat compile
            cmd = ["npx", "hardhat", "compile"]

            if config and config.optimization_level != OptimizationLevel.NONE:
                cmd.append("--optimize")

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=project_path,
            )

            if result.returncode != 0:
                logger.error(f"Hardhat compilation failed: {result.stderr}")
                return []

            # Read build artifacts
            artifacts_dir = Path(project_path) / "artifacts"
            results = []

            if artifacts_dir.exists():
                for contract_file in artifacts_dir.rglob("*.json"):
                    try:
                        with open(contract_file, 'r') as f:
                            data = json.load(f)

                        result_obj = CompilationResult(
                            contract_name=contract_file.stem,
                            compiler_type=CompilerType.HARDFAT,
                            compiler_version=config.version if config else "unknown",
                            status=CompilerStatus.SUCCESS,
                            abi=data.get("abi"),
                            bytecode=data.get("bytecode"),
                            bytecode_runtime=data.get("deployedBytecode"),
                            metadata=data.get("metadata"),
                            compilation_time_ms=(time.time() - start_time) * 1000,
                        )

                        results.append(result_obj)

                    except Exception as e:
                        logger.error(f"Error reading artifact {contract_file}: {e}")

            return results

        except Exception as e:
            logger.error(f"Hardhat compilation error: {e}")
            return []

    # -----------------------------------------------------------------------
    # Foundry Compilation
    # -----------------------------------------------------------------------

    async def compile_foundry(
        self,
        project_path: str,
        config: Optional[CompilerConfig] = None,
    ) -> List[CompilationResult]:
        """
        Compile Foundry project.

        Args:
            project_path: Path to Foundry project
            config: Compiler configuration

        Returns:
            List of CompilationResult
        """
        start_time = time.time()

        if not self._compilers_available.get(CompilerType.FOUNDRY, False):
            logger.error("Foundry not available")
            return []

        try:
            # Run forge build
            cmd = ["forge", "build", "--extra-output-files", "abi"]

            if config and config.optimization_level != OptimizationLevel.NONE:
                cmd.append("--optimize")

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=project_path,
            )

            if result.returncode != 0:
                logger.error(f"Foundry compilation failed: {result.stderr}")
                return []

            # Read build artifacts
            artifacts_dir = Path(project_path) / "out"
            results = []

            if artifacts_dir.exists():
                for contract_file in artifacts_dir.rglob("*.sol"):
                    # Read ABI
                    abi_file = contract_file.with_suffix(".json")
                    if abi_file.exists():
                        try:
                            with open(abi_file, 'r') as f:
                                data = json.load(f)

                            result_obj = CompilationResult(
                                contract_name=contract_file.stem,
                                compiler_type=CompilerType.FOUNDRY,
                                compiler_version=config.version if config else "unknown",
                                status=CompilerStatus.SUCCESS,
                                abi=data.get("abi"),
                                bytecode=data.get("bytecode"),
                                bytecode_runtime=data.get("deployedBytecode"),
                                metadata=data.get("metadata"),
                                compilation_time_ms=(time.time() - start_time) * 1000,
                            )

                            results.append(result_obj)

                        except Exception as e:
                            logger.error(f"Error reading artifact {abi_file}: {e}")

            return results

        except Exception as e:
            logger.error(f"Foundry compilation error: {e}")
            return []

    # -----------------------------------------------------------------------
    # Compilation Verification
    # -----------------------------------------------------------------------

    async def verify_compilation(
        self,
        result: CompilationResult,
        address: str,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify that compiled bytecode matches deployed contract.

        Args:
            result: CompilationResult
            address: Contract address
            source: Source code (optional)

        Returns:
            Verification result
        """
        verification = {
            "verified": False,
            "matches": False,
            "deployed_bytecode": None,
            "compiled_bytecode": None,
            "differences": [],
            "confidence": 0.0,
        }

        try:
            # Get deployed bytecode
            web3 = Web3()
            deployed_code = web3.eth.get_code(Web3.to_checksum_address(address))

            if not deployed_code or deployed_code == b'':
                verification["error"] = "No bytecode found at address"
                return verification

            deployed_hex = deployed_code.hex()
            verification["deployed_bytecode"] = "0x" + deployed_hex

            # Get compiled bytecode
            compiled_hex = result.bytecode_runtime or result.bytecode
            if not compiled_hex:
                verification["error"] = "No compiled bytecode available"
                return verification

            verification["compiled_bytecode"] = compiled_hex

            # Compare bytecode
            compiled_bytes = bytes.fromhex(compiled_hex.replace("0x", ""))
            deployed_bytes = deployed_code

            if compiled_bytes == deployed_bytes:
                verification["verified"] = True
                verification["matches"] = True
                verification["confidence"] = 1.0
            else:
                # Check for metadata differences
                # (Solidity appends metadata at the end)
                min_len = min(len(compiled_bytes), len(deployed_bytes))
                if min_len > 0:
                    compiled_truncated = compiled_bytes[:min_len]
                    deployed_truncated = deployed_bytes[:min_len]

                    if compiled_truncated == deployed_truncated:
                        verification["verified"] = True
                        verification["matches"] = True
                        verification["confidence"] = 0.9
                        verification["differences"].append(
                            "Metadata difference detected (likely compiler metadata)"
                        )

            return verification

        except Exception as e:
            logger.error(f"Verification error: {e}")
            verification["error"] = str(e)
            return verification

    # -----------------------------------------------------------------------
    # Optimization
    # -----------------------------------------------------------------------

    async def optimize_contract(
        self,
        source: Union[str, ContractSource],
        config: Optional[CompilerConfig] = None,
    ) -> Dict[str, Any]:
        """
        Optimize contract for gas efficiency.

        Args:
            source: Source code or ContractSource
            config: Compiler configuration

        Returns:
            Optimization report
        """
        if config is None:
            config = CompilerConfig()

        # Try different optimization levels
        optimization_results = {}
        best_result = None
        best_gas = float('inf')

        levels = [OptimizationLevel.NONE, OptimizationLevel.BASIC,
                  OptimizationLevel.STANDARD, OptimizationLevel.AGGRESSIVE]

        for level in levels:
            test_config = CompilerConfig(
                optimization_level=level,
                optimization_runs=config.optimization_runs,
                evm_version=config.evm_version,
                via_ir=config.via_ir,
            )

            result = await self.compile_solidity(source, test_config)
            if result and result.status == CompilerStatus.SUCCESS:
                # Estimate gas
                gas_estimate = self._estimate_gas(result)
                optimization_results[level.value] = {
                    "gas_estimate": gas_estimate,
                    "bytecode_size": len(result.bytecode or "") // 2,
                    "success": True,
                }

                if gas_estimate < best_gas:
                    best_gas = gas_estimate
                    best_result = result
            else:
                optimization_results[level.value] = {
                    "gas_estimate": None,
                    "bytecode_size": None,
                    "success": False,
                }

        return {
            "optimized": best_result is not None,
            "best_level": best_result.compiler_version if best_result else None,
            "results": optimization_results,
            "improvement": {
                "gas_saved": best_gas if best_gas != float('inf') else None,
                "size_reduction": None,  # Would calculate from best_result
            },
            "recommendations": self._generate_optimization_recommendations(
                optimization_results
            ),
        }

    def _estimate_gas(self, result: CompilationResult) -> int:
        """Estimate gas usage from bytecode."""
        if not result.bytecode:
            return 0

        # Simple estimate based on bytecode size and complexity
        bytecode_size = len(result.bytecode) // 2
        base_gas = 21000  # Transaction base gas

        # Add gas for bytecode size (200 gas per byte for contract creation)
        deployment_gas = bytecode_size * 200

        # Add gas for operations (rough estimate)
        if result.opcodes:
            op_count = len(result.opcodes.split())
            operation_gas = op_count * 3  # Average gas per opcode
        else:
            operation_gas = bytecode_size * 50

        return base_gas + deployment_gas + operation_gas

    def _generate_optimization_recommendations(
        self,
        results: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []

        if not results:
            return recommendations

        best_level = None
        best_gas = float('inf')

        for level, data in results.items():
            if data.get("success") and data.get("gas_estimate"):
                if data["gas_estimate"] < best_gas:
                    best_gas = data["gas_estimate"]
                    best_level = level

        if best_level:
            recommendations.append(f"Best optimization level: {best_level}")
        else:
            recommendations.append("Optimization failed for all levels")

        return recommendations

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def _create_error_result(
        self,
        contract_name: str,
        compiler_type: CompilerType,
        version: str,
        errors: List[str],
    ) -> CompilationResult:
        """Create an error compilation result."""
        self._performance["compilations"] += 1
        self._performance["failed"] += 1

        return CompilationResult(
            contract_name=contract_name,
            compiler_type=compiler_type,
            compiler_version=version,
            status=CompilerStatus.FAILED,
            errors=errors,
        )

    async def get_compiler_version(
        self,
        compiler_type: CompilerType = CompilerType.SOLC,
    ) -> Optional[str]:
        """Get compiler version."""
        if compiler_type == CompilerType.SOLC:
            try:
                result = subprocess.run(
                    ["solc", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    match = re.search(r'Version:\s*([\d.]+)', result.stdout)
                    if match:
                        return match.group(1)
            except Exception:
                pass

        elif compiler_type == CompilerType.VYPER:
            try:
                result = subprocess.run(
                    ["vyper", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    match = re.search(r'([\d.]+)', result.stdout)
                    if match:
                        return match.group(1)
            except Exception:
                pass

        return None

    def get_compiler_version_available(self, version: str) -> bool:
        """Check if a specific compiler version is available."""
        return version in self.SOLC_VERSIONS

    def clear_cache(self) -> None:
        """Clear compilation cache."""
        self._cache.clear()
        self._source_cache.clear()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "cache_size": len(self._cache),
            "source_cache_size": len(self._source_cache),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the compiler."""
        self._running = True
        logger.info("ContractCompiler started")

    async def stop(self) -> None:
        """Stop the compiler."""
        self._running = False
        logger.info("ContractCompiler stopped")

    def __del__(self):
        """Cleanup."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)


# ============================================================================
# Factory Function
# ============================================================================

def create_contract_compiler(
    config: Optional[Dict[str, Any]] = None,
) -> ContractCompiler:
    """Factory function to create a ContractCompiler instance."""
    return ContractCompiler(config=config)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the compiler
    pass

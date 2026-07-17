# blockchain/smart-contracts/contract_verifier.py
# NEXUS AI TRADING SYSTEM - Smart Contract Verification Framework
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced Smart Contract Verification Framework for NEXUS AI Trading System.
Provides multi-source contract verification, bytecode matching, source code
validation, and comprehensive verification reporting across multiple chains
and verification providers.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
from web3 import Web3

# NEXUS Imports
from blockchain.smart_contracts.contract_compiler import (
    CompilationResult,
    CompilerConfig,
    ContractCompiler,
    create_contract_compiler,
)
from blockchain.smart_contracts.contract_bytecode import (
    BytecodeAnalyzer,
    ContractAnalysis,
    create_bytecode_analyzer,
)
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.verifier")


# ============================================================================
# Enums & Constants
# ============================================================================

class VerificationProvider(str, Enum):
    """Verification providers."""
    ETHERSCAN = "etherscan"
    BSCSCAN = "bscscan"
    POLYGONSCAN = "polygonscan"
    ARBISCAN = "arbiscan"
    OPTIMISTIC = "optimistic"
    SNOWTRACE = "snowtrace"
    FTMSACN = "ftmscan"
    BASESCAN = "basescan"
    SOURCIFY = "sourcify"
    BLOCKSCOUT = "blockscout"
    CUSTOM = "custom"


class VerificationStatus(str, Enum):
    """Verification status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_VERIFIED = "not_verified"
    ERROR = "error"


class VerificationType(str, Enum):
    """Verification types."""
    FULL = "full"           # Full source verification
    PARTIAL = "partial"     # Partial verification
    BYTECODE = "bytecode"   # Bytecode comparison
    METADATA = "metadata"   # Metadata verification
    SOURCE = "source"       # Source code verification
    COMPILER = "compiler"   # Compiler version verification


@dataclass
class VerificationResult:
    """Verification result."""
    contract_address: str
    contract_name: str
    chain: str
    status: VerificationStatus
    verification_type: VerificationType
    provider: VerificationProvider
    timestamp: datetime
    source_code: Optional[str] = None
    compiler_version: Optional[str] = None
    optimization_used: Optional[bool] = None
    optimization_runs: Optional[int] = None
    abi: Optional[List[Dict[str, Any]]] = None
    bytecode: Optional[str] = None
    runtime_bytecode: Optional[str] = None
    metadata_hash: Optional[str] = None
    match_score: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    provider_data: Dict[str, Any] = field(default_factory=dict)
    verification_checks: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class VerificationConfig:
    """Verification configuration."""
    provider: VerificationProvider = VerificationProvider.ETHERSCAN
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5
    verify_optimization: bool = True
    verify_metadata: bool = True
    verify_bytecode: bool = True
    verify_compiler_version: bool = True
    save_artifacts: bool = True
    artifacts_dir: str = "verification_artifacts"
    custom_compiler_paths: List[str] = field(default_factory=list)


# ============================================================================
# Contract Verifier
# ============================================================================

class ContractVerifier:
    """
    Advanced Smart Contract Verification Framework.
    Provides multi-source contract verification and validation.
    """

    # Known verification endpoints
    PROVIDER_ENDPOINTS = {
        VerificationProvider.ETHERSCAN: "https://api.etherscan.io/api",
        VerificationProvider.BSCSCAN: "https://api.bscscan.com/api",
        VerificationProvider.POLYGONSCAN: "https://api.polygonscan.com/api",
        VerificationProvider.ARBISCAN: "https://api.arbiscan.io/api",
        VerificationProvider.OPTIMISTIC: "https://api-optimistic.etherscan.io/api",
        VerificationProvider.SNOWTRACE: "https://api.snowtrace.io/api",
        VerificationProvider.FTMSACN: "https://api.ftmscan.com/api",
        VerificationProvider.BASESCAN: "https://api.basescan.org/api",
        VerificationProvider.SOURCIFY: "https://sourcify.dev/api",
        VerificationProvider.BLOCKSCOUT: "https://blockscout.com/api",
    }

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[VerificationConfig] = None,
    ):
        self.web3_client = web3_client
        self.config = config or VerificationConfig()

        # Initialize components
        self.compiler = create_contract_compiler()
        self.bytecode_analyzer = create_bytecode_analyzer(web3_client)

        # Verification cache
        self._verification_cache: Dict[str, VerificationResult] = {}
        self._verification_history: Dict[str, List[VerificationResult]] = {}

        # Source code cache
        self._source_cache: Dict[str, str] = {}

        # State management
        self._running = False
        self._lock = asyncio.Lock()

        # Performance metrics
        self._performance = {
            "verifications_total": 0,
            "verifications_successful": 0,
            "verifications_failed": 0,
            "partial_verifications": 0,
            "avg_verification_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        logger.info(
            "ContractVerifier initialized",
            extra={
                "chain": web3_client.chain_name,
                "provider": config.provider.value,
            }
        )

    # -----------------------------------------------------------------------
    # Verification Methods
    # -----------------------------------------------------------------------

    async def verify_contract(
        self,
        contract_address: str,
        source_code: Optional[str] = None,
        contract_name: Optional[str] = None,
        compiler_version: Optional[str] = None,
        optimization_used: Optional[bool] = None,
        optimization_runs: Optional[int] = 200,
        force_refresh: bool = False,
        provider: Optional[VerificationProvider] = None,
    ) -> Optional[VerificationResult]:
        """
        Verify a contract using multiple methods.

        Args:
            contract_address: Contract address
            source_code: Source code (optional)
            contract_name: Contract name
            compiler_version: Compiler version
            optimization_used: Optimization flag
            optimization_runs: Optimization runs
            force_refresh: Force refresh cache
            provider: Verification provider

        Returns:
            VerificationResult or None
        """
        contract_address = Web3.to_checksum_address(contract_address)
        provider = provider or self.config.provider

        # Check cache
        cache_key = f"{contract_address}_{provider.value}"
        if not force_refresh and cache_key in self._verification_cache:
            self._performance["cache_hits"] += 1
            return self._verification_cache[cache_key]

        self._performance["cache_misses"] += 1
        start_time = time.time()

        try:
            # Get bytecode if not provided
            bytecode = await self.web3_client.get_code(contract_address)
            if not bytecode or bytecode == b'':
                logger.warning(f"No bytecode found at {contract_address}")
                return self._create_error_result(
                    contract_address,
                    contract_name or "Unknown",
                    "No bytecode found at address",
                )

            # Try to get source code if not provided
            if not source_code:
                source_code = await self._fetch_source_code(
                    contract_address,
                    provider,
                )

            # Get contract name if not provided
            if not contract_name and source_code:
                contract_name = self._extract_contract_name(source_code)

            # Perform verification based on available data
            verification_type = await self._determine_verification_type(
                source_code,
                bytecode,
                provider,
            )

            result = None

            if verification_type == VerificationType.FULL:
                result = await self._verify_full(
                    contract_address,
                    source_code,
                    contract_name,
                    compiler_version,
                    optimization_used,
                    optimization_runs,
                    provider,
                )
            elif verification_type == VerificationType.BYTECODE:
                result = await self._verify_bytecode(
                    contract_address,
                    bytecode,
                    provider,
                )
            elif verification_type == VerificationType.METADATA:
                result = await self._verify_metadata(
                    contract_address,
                    bytecode,
                    provider,
                )
            elif verification_type == VerificationType.SOURCE:
                result = await self._verify_source(
                    contract_address,
                    source_code,
                    contract_name,
                    provider,
                )
            else:
                # Try all methods
                result = await self._verify_all_methods(
                    contract_address,
                    source_code,
                    contract_name,
                    provider,
                )

            if result:
                result.verification_type = verification_type
                result.timestamp = datetime.utcnow()
                result.match_score = self._calculate_match_score(result)

                # Cache result
                self._verification_cache[cache_key] = result
                if contract_address not in self._verification_history:
                    self._verification_history[contract_address] = []
                self._verification_history[contract_address].append(result)

                # Update performance
                self._performance["verifications_total"] += 1
                if result.status == VerificationStatus.VERIFIED:
                    self._performance["verifications_successful"] += 1
                elif result.status == VerificationStatus.FAILED:
                    self._performance["verifications_failed"] += 1
                elif result.status == VerificationStatus.PARTIAL:
                    self._performance["partial_verifications"] += 1

                elapsed_ms = (time.time() - start_time) * 1000
                self._performance["avg_verification_time_ms"] = (
                    (self._performance["avg_verification_time_ms"] *
                     (self._performance["verifications_total"] - 1) +
                     elapsed_ms) / self._performance["verifications_total"]
                )

                logger.info(
                    f"Verification completed for {contract_address}",
                    extra={
                        "status": result.status.value,
                        "score": result.match_score,
                        "type": result.verification_type.value,
                        "duration_ms": elapsed_ms,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Verification error for {contract_address}: {e}")
            return self._create_error_result(
                contract_address,
                contract_name or "Unknown",
                str(e),
            )

    # -----------------------------------------------------------------------
    # Full Verification
    # -----------------------------------------------------------------------

    async def _verify_full(
        self,
        address: str,
        source_code: str,
        contract_name: str,
        compiler_version: Optional[str],
        optimization_used: Optional[bool],
        optimization_runs: Optional[int],
        provider: VerificationProvider,
    ) -> Optional[VerificationResult]:
        """Perform full verification."""
        checks = []
        errors = []
        warnings = []

        try:
            # Compile source code
            compiler_config = CompilerConfig(
                version=compiler_version or "0.8.20",
                optimization_level="standard" if optimization_used else "none",
                optimization_runs=optimization_runs or 200,
                output_formats=["abi", "bin", "bin-runtime", "metadata"],
            )

            compilation_result = await self.compiler.compile_solidity(
                source_code,
                compiler_config,
            )

            if not compilation_result or compilation_result.status.value != "success":
                errors.append("Compilation failed")
                checks.append({"check": "compilation", "passed": False})
                return VerificationResult(
                    contract_address=address,
                    contract_name=contract_name,
                    chain=self.web3_client.chain_name,
                    status=VerificationStatus.FAILED,
                    verification_type=VerificationType.FULL,
                    provider=provider,
                    timestamp=datetime.utcnow(),
                    errors=errors,
                    warnings=warnings,
                    verification_checks=checks,
                )

            checks.append({"check": "compilation", "passed": True})

            # Get deployed bytecode
            deployed_code = await self.web3_client.get_code(address)

            # Compare bytecode
            compiled_bytecode = compilation_result.bytecode
            compiled_runtime = compilation_result.bytecode_runtime

            if not compiled_bytecode:
                errors.append("No compiled bytecode available")
                return self._create_error_result(address, contract_name, "No compiled bytecode")

            # Compare runtime bytecode
            runtime_match = False
            if compiled_runtime:
                runtime_bytes = bytes.fromhex(compiled_runtime.replace("0x", ""))
                deployed_bytes = deployed_code

                # Check for metadata differences (Solidity appends metadata)
                min_len = min(len(runtime_bytes), len(deployed_bytes))
                if min_len > 0:
                    if runtime_bytes[:min_len] == deployed_bytes[:min_len]:
                        runtime_match = True
                else:
                    runtime_match = runtime_bytes == deployed_bytes

            checks.append({
                "check": "runtime_bytecode_match",
                "passed": runtime_match,
                "details": {
                    "compiled": compiled_runtime[:50] if compiled_runtime else "",
                    "deployed": deployed_code.hex()[:50] if deployed_code else "",
                }
            })

            # Get metadata hash
            metadata_hash = None
            if compilation_result.metadata:
                metadata_hash = hashlib.sha256(
                    json.dumps(compilation_result.metadata).encode()
                ).hexdigest()
                checks.append({"check": "metadata_available", "passed": True})

            # Determine status
            if runtime_match:
                status = VerificationStatus.VERIFIED
                match_score = 1.0
            elif runtime_match is False:
                # Check if it's a proxy
                is_proxy = await self._is_proxy_contract(address)
                if is_proxy:
                    status = VerificationStatus.PARTIAL
                    match_score = 0.7
                    warnings.append("Proxy contract detected - verifying implementation")
                else:
                    status = VerificationStatus.PARTIAL
                    match_score = 0.5
                    warnings.append("Bytecode mismatch - may be due to metadata or optimizations")
            else:
                status = VerificationStatus.PARTIAL
                match_score = 0.3
                warnings.append("Partial match - source may be different")

            return VerificationResult(
                contract_address=address,
                contract_name=contract_name,
                chain=self.web3_client.chain_name,
                status=status,
                verification_type=VerificationType.FULL,
                provider=provider,
                timestamp=datetime.utcnow(),
                source_code=source_code,
                compiler_version=compiler_version,
                optimization_used=optimization_used,
                optimization_runs=optimization_runs,
                abi=compilation_result.abi,
                bytecode=compiled_bytecode,
                runtime_bytecode=compiled_runtime,
                metadata_hash=metadata_hash,
                match_score=match_score,
                errors=errors,
                warnings=warnings,
                verification_checks=checks,
            )

        except Exception as e:
            return self._create_error_result(
                address,
                contract_name,
                str(e),
            )

    # -----------------------------------------------------------------------
    # Bytecode Verification
    # -----------------------------------------------------------------------

    async def _verify_bytecode(
        self,
        address: str,
        bytecode: bytes,
        provider: VerificationProvider,
    ) -> Optional[VerificationResult]:
        """Verify by analyzing bytecode."""
        checks = []
        errors = []
        warnings = []

        try:
            # Analyze bytecode
            analysis = await self.bytecode_analyzer.analyze_contract(address)

            if not analysis:
                errors.append("Bytecode analysis failed")
                return self._create_error_result(address, "Unknown", "Analysis failed")

            # Check for patterns
            patterns = analysis.patterns
            risk_level = analysis.risk_level

            checks.append({
                "check": "bytecode_analysis",
                "passed": True,
                "details": {
                    "patterns": [p.value for p in patterns],
                    "risk_level": risk_level.value,
                    "instructions": len(analysis.instructions),
                    "blocks": len(analysis.basic_blocks),
                }
            })

            # Verify against common standards
            if patterns:
                for pattern in patterns:
                    checks.append({
                        "check": f"pattern_{pattern.value}",
                        "passed": True,
                        "details": {"pattern": pattern.value},
                    })

            # Check for suspicious functions
            if analysis.suspicious_functions:
                warnings.append(f"Suspicious functions: {analysis.suspicious_functions}")

            return VerificationResult(
                contract_address=address,
                contract_name="Unknown",
                chain=self.web3_client.chain_name,
                status=VerificationStatus.PARTIAL,
                verification_type=VerificationType.BYTECODE,
                provider=provider,
                timestamp=datetime.utcnow(),
                bytecode=bytecode.hex() if bytecode else None,
                match_score=0.6 if patterns else 0.3,
                errors=errors,
                warnings=warnings,
                verification_checks=checks,
                metadata={"analysis": analysis.metadata},
            )

        except Exception as e:
            return self._create_error_result(address, "Unknown", str(e))

    # -----------------------------------------------------------------------
    # Metadata Verification
    # -----------------------------------------------------------------------

    async def _verify_metadata(
        self,
        address: str,
        bytecode: bytes,
        provider: VerificationProvider,
    ) -> Optional[VerificationResult]:
        """Verify contract metadata."""
        checks = []
        errors = []

        try:
            # Try to extract metadata from bytecode
            metadata = self._extract_metadata_from_bytecode(bytecode)

            if not metadata:
                errors.append("No metadata found in bytecode")
                return self._create_error_result(
                    address,
                    "Unknown",
                    "No metadata found",
                )

            checks.append({
                "check": "metadata_extraction",
                "passed": True,
                "details": {"metadata": metadata},
            })

            # Verify metadata integrity
            if "solc_version" in metadata:
                checks.append({
                    "check": "compiler_version_present",
                    "passed": True,
                    "details": {"version": metadata["solc_version"]},
                })

            return VerificationResult(
                contract_address=address,
                contract_name="Unknown",
                chain=self.web3_client.chain_name,
                status=VerificationStatus.PARTIAL,
                verification_type=VerificationType.METADATA,
                provider=provider,
                timestamp=datetime.utcnow(),
                bytecode=bytecode.hex() if bytecode else None,
                metadata_hash=hashlib.sha256(json.dumps(metadata).encode()).hexdigest(),
                match_score=0.5,
                errors=errors,
                verification_checks=checks,
                provider_data={"extracted_metadata": metadata},
            )

        except Exception as e:
            return self._create_error_result(address, "Unknown", str(e))

    def _extract_metadata_from_bytecode(self, bytecode: bytes) -> Dict[str, Any]:
        """Extract metadata from bytecode."""
        metadata = {}

        # Look for solc metadata pattern
        if b"solc" in bytecode:
            try:
                # Extract version
                start = bytecode.find(b"solc")
                if start != -1:
                    version_bytes = bytecode[start:start + 20]
                    try:
                        version_str = version_bytes.decode('utf-8', errors='ignore')
                        # Extract version number
                        import re
                        match = re.search(r'[0-9]+\.[0-9]+\.[0-9]+', version_str)
                        if match:
                            metadata["solc_version"] = match.group()
                    except:
                        pass
            except:
                pass

        return metadata

    # -----------------------------------------------------------------------
    # Source Verification
    # -----------------------------------------------------------------------

    async def _verify_source(
        self,
        address: str,
        source_code: str,
        contract_name: str,
        provider: VerificationProvider,
    ) -> Optional[VerificationResult]:
        """Verify source code."""
        checks = []
        errors = []

        try:
            if not source_code:
                errors.append("No source code provided")
                return self._create_error_result(
                    address,
                    contract_name,
                    "No source code",
                )

            # Extract contract name if not provided
            if not contract_name:
                contract_name = self._extract_contract_name(source_code)

            # Basic source validation
            if "contract" not in source_code:
                warnings = ["No contract keyword found in source"]
            else:
                warnings = []

            checks.append({
                "check": "source_code_present",
                "passed": True,
                "details": {
                    "lines": len(source_code.split('\n')),
                    "contract_name": contract_name,
                }
            })

            return VerificationResult(
                contract_address=address,
                contract_name=contract_name,
                chain=self.web3_client.chain_name,
                status=VerificationStatus.PARTIAL,
                verification_type=VerificationType.SOURCE,
                provider=provider,
                timestamp=datetime.utcnow(),
                source_code=source_code,
                match_score=0.4,
                errors=errors,
                warnings=warnings,
                verification_checks=checks,
            )

        except Exception as e:
            return self._create_error_result(address, contract_name, str(e))

    # -----------------------------------------------------------------------
    # All Methods Verification
    # -----------------------------------------------------------------------

    async def _verify_all_methods(
        self,
        address: str,
        source_code: Optional[str],
        contract_name: str,
        provider: VerificationProvider,
    ) -> Optional[VerificationResult]:
        """Try all verification methods."""
        results = []

        # Try source verification first if source available
        if source_code:
            result = await self._verify_source(address, source_code, contract_name, provider)
            if result and result.status != VerificationStatus.FAILED:
                results.append(result)

        # Try bytecode verification
        bytecode = await self.web3_client.get_code(address)
        if bytecode:
            result = await self._verify_bytecode(address, bytecode, provider)
            if result and result.status != VerificationStatus.FAILED:
                results.append(result)

        # Try metadata verification
        if bytecode:
            result = await self._verify_metadata(address, bytecode, provider)
            if result and result.status != VerificationStatus.FAILED:
                results.append(result)

        # Try full verification if source available
        if source_code:
            result = await self._verify_full(
                address,
                source_code,
                contract_name,
                None,
                None,
                None,
                provider,
            )
            if result:
                results.append(result)

        if not results:
            return self._create_error_result(
                address,
                contract_name,
                "All verification methods failed",
            )

        # Combine results
        best_result = max(results, key=lambda r: r.match_score)
        best_result.status = self._combine_status([r.status for r in results])

        # Add verification checks from all methods
        for result in results:
            if result.verification_checks:
                best_result.verification_checks.extend(result.verification_checks)

        return best_result

    # -----------------------------------------------------------------------
    # Provider Integration
    # -----------------------------------------------------------------------

    async def _fetch_source_code(
        self,
        address: str,
        provider: VerificationProvider,
    ) -> Optional[str]:
        """Fetch source code from verification provider."""
        try:
            if provider == VerificationProvider.SOURCIFY:
                return await self._fetch_from_sourcify(address)
            else:
                return await self._fetch_from_explorer(address, provider)

        except Exception as e:
            logger.error(f"Error fetching source code: {e}")
            return None

    async def _fetch_from_sourcify(self, address: str) -> Optional[str]:
        """Fetch source code from Sourcify."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.PROVIDER_ENDPOINTS[VerificationProvider.SOURCIFY]}/files"
                params = {
                    "address": address,
                    "chain": str(self.web3_client.chain_id),
                }
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and "files" in data:
                            for file in data["files"]:
                                if file.get("name", "").endswith(".sol"):
                                    return file.get("content")
                    return None
        except Exception as e:
            logger.error(f"Error fetching from Sourcify: {e}")
            return None

    async def _fetch_from_explorer(
        self,
        address: str,
        provider: VerificationProvider,
    ) -> Optional[str]:
        """Fetch source code from block explorer."""
        try:
            api_url = self.PROVIDER_ENDPOINTS.get(provider)
            if not api_url:
                return None

            params = {
                "module": "contract",
                "action": "getsourcecode",
                "address": address,
                "apikey": self.config.api_key or "",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "1":
                            source = data.get("result", [{}])[0].get("SourceCode", "")
                            if source:
                                return source
                    return None

        except Exception as e:
            logger.error(f"Error fetching from explorer: {e}")
            return None

    # -----------------------------------------------------------------------
    # Verification via Explorer API
    # -----------------------------------------------------------------------

    async def verify_via_explorer(
        self,
        address: str,
        source_code: str,
        contract_name: str,
        compiler_version: str,
        optimization_used: bool = False,
        optimization_runs: int = 200,
        provider: Optional[VerificationProvider] = None,
    ) -> Dict[str, Any]:
        """
        Submit contract for verification via explorer API.

        Args:
            address: Contract address
            source_code: Source code
            contract_name: Contract name
            compiler_version: Compiler version
            optimization_used: Optimization flag
            optimization_runs: Optimization runs
            provider: Verification provider

        Returns:
            Verification response
        """
        provider = provider or self.config.provider

        try:
            api_url = self.PROVIDER_ENDPOINTS.get(provider)
            if not api_url:
                return {"status": "error", "message": "Unsupported provider"}

            # Build verification request
            params = {
                "module": "contract",
                "action": "verifysourcecode",
                "address": address,
                "sourceCode": source_code,
                "contractname": contract_name,
                "compilerversion": compiler_version,
                "optimizationUsed": "1" if optimization_used else "0",
                "runs": str(optimization_runs),
                "apikey": self.config.api_key or "",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "status": data.get("status"),
                            "message": data.get("result", "Unknown response"),
                            "guid": data.get("result") if data.get("status") == "1" else None,
                            "raw": data,
                        }
                    else:
                        return {
                            "status": "error",
                            "message": f"HTTP {response.status}",
                        }

        except Exception as e:
            logger.error(f"Error submitting verification: {e}")
            return {"status": "error", "message": str(e)}

    # -----------------------------------------------------------------------
    # Verification Status Check
    # -----------------------------------------------------------------------

    async def check_verification_status(
        self,
        guid: str,
        provider: Optional[VerificationProvider] = None,
    ) -> Dict[str, Any]:
        """
        Check verification status.

        Args:
            guid: Verification GUID
            provider: Verification provider

        Returns:
            Status response
        """
        provider = provider or self.config.provider

        try:
            api_url = self.PROVIDER_ENDPOINTS.get(provider)
            if not api_url:
                return {"status": "error", "message": "Unsupported provider"}

            params = {
                "module": "contract",
                "action": "checkverifystatus",
                "guid": guid,
                "apikey": self.config.api_key or "",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "status": data.get("status"),
                            "message": data.get("result"),
                            "raw": data,
                        }
                    else:
                        return {
                            "status": "error",
                            "message": f"HTTP {response.status}",
                        }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def _create_error_result(
        self,
        address: str,
        contract_name: str,
        error: str,
    ) -> VerificationResult:
        """Create an error verification result."""
        return VerificationResult(
            contract_address=address,
            contract_name=contract_name,
            chain=self.web3_client.chain_name,
            status=VerificationStatus.FAILED,
            verification_type=VerificationType.FULL,
            provider=self.config.provider,
            timestamp=datetime.utcnow(),
            errors=[error],
            match_score=0.0,
        )

    def _extract_contract_name(self, source_code: str) -> str:
        """Extract contract name from source code."""
        import re
        pattern = r'contract\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        matches = re.findall(pattern, source_code)
        return matches[0] if matches else "UnknownContract"

    async def _is_proxy_contract(self, address: str) -> bool:
        """Check if contract is a proxy."""
        # Check EIP-1967 implementation slot
        implementation_slot = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
        try:
            storage = await self.web3_client.eth.get_storage_at(address, implementation_slot)
            if int(storage.hex(), 16) != 0:
                return True
        except Exception:
            pass

        # Check for admin slot
        admin_slot = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
        try:
            storage = await self.web3_client.eth.get_storage_at(address, admin_slot)
            if int(storage.hex(), 16) != 0:
                return True
        except Exception:
            pass

        return False

    async def _determine_verification_type(
        self,
        source_code: Optional[str],
        bytecode: bytes,
        provider: VerificationProvider,
    ) -> VerificationType:
        """Determine the best verification type."""
        if source_code and len(source_code) > 100:
            # Check if we can do full verification
            try:
                # Test compile
                result = await self.compiler.compile_solidity(source_code[:1000])
                if result and result.status.value == "success":
                    return VerificationType.FULL
            except Exception:
                pass
            return VerificationType.SOURCE
        elif bytecode and len(bytecode) > 100:
            return VerificationType.BYTECODE
        else:
            return VerificationType.METADATA

    def _calculate_match_score(self, result: VerificationResult) -> float:
        """Calculate match score from verification result."""
        if result.status == VerificationStatus.VERIFIED:
            return 1.0
        elif result.status == VerificationStatus.PARTIAL:
            # Calculate from checks
            passed = sum(1 for c in result.verification_checks if c.get("passed", False))
            total = len(result.verification_checks) or 1
            return passed / total
        else:
            return 0.0

    def _combine_status(self, statuses: List[VerificationStatus]) -> VerificationStatus:
        """Combine multiple verification statuses."""
        if VerificationStatus.VERIFIED in statuses:
            return VerificationStatus.VERIFIED
        elif VerificationStatus.PARTIAL in statuses:
            return VerificationStatus.PARTIAL
        elif VerificationStatus.FAILED in statuses:
            return VerificationStatus.FAILED
        else:
            return VerificationStatus.PENDING

    # -----------------------------------------------------------------------
    # Artifact Management
    # -----------------------------------------------------------------------

    async def save_artifacts(
        self,
        result: VerificationResult,
    ) -> None:
        """Save verification artifacts."""
        if not self.config.save_artifacts:
            return

        try:
            artifacts_dir = Path(self.config.artifacts_dir)
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            # Save verification result
            result_file = artifacts_dir / f"{result.contract_address}_verification.json"
            with open(result_file, 'w') as f:
                json.dump(result.__dict__, f, default=str, indent=2)

            # Save source code if available
            if result.source_code:
                source_file = artifacts_dir / f"{result.contract_address}_source.sol"
                with open(source_file, 'w') as f:
                    f.write(result.source_code)

            # Save ABI if available
            if result.abi:
                abi_file = artifacts_dir / f"{result.contract_address}_abi.json"
                with open(abi_file, 'w') as f:
                    json.dump(result.abi, f, indent=2)

            # Save bytecode if available
            if result.bytecode:
                bytecode_file = artifacts_dir / f"{result.contract_address}_bytecode.bin"
                with open(bytecode_file, 'w') as f:
                    f.write(result.bytecode)

        except Exception as e:
            logger.error(f"Error saving artifacts: {e}")

    # -----------------------------------------------------------------------
    # Performance Metrics
    # -----------------------------------------------------------------------

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "cache_size": len(self._verification_cache),
            "history_size": sum(len(h) for h in self._verification_history.values()),
            "source_cache_size": len(self._source_cache),
            "provider": self.config.provider.value,
        }

    def get_verification_history(
        self,
        address: str,
        limit: int = 100,
    ) -> List[VerificationResult]:
        """Get verification history for an address."""
        history = self._verification_history.get(address, [])
        return history[-limit:]

    def get_verification_stats(self) -> Dict[str, Any]:
        """Get verification statistics."""
        addresses = len(self._verification_history)
        total_verifications = sum(len(h) for h in self._verification_history.values())

        return {
            "total_addresses": addresses,
            "total_verifications": total_verifications,
            "verified": self._performance["verifications_successful"],
            "partial": self._performance["partial_verifications"],
            "failed": self._performance["verifications_failed"],
            "average_time_ms": self._performance["avg_verification_time_ms"],
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the verifier."""
        if self._running:
            return

        self._running = True
        await self.compiler.start()
        await self.bytecode_analyzer.start()

        logger.info("ContractVerifier started")

    async def stop(self) -> None:
        """Stop the verifier."""
        self._running = False
        await self.compiler.stop()
        await self.bytecode_analyzer.stop()

        logger.info("ContractVerifier stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_contract_verifier(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> ContractVerifier:
    """
    Factory function to create a ContractVerifier instance.

    Args:
        web3_client: Web3 client instance
        config: Configuration dictionary

    Returns:
        ContractVerifier instance
    """
    if config:
        verification_config = VerificationConfig(**config)
    else:
        verification_config = VerificationConfig()

    return ContractVerifier(
        web3_client=web3_client,
        config=verification_config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the contract verifier
    pass

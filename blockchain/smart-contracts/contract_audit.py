# blockchain/smart-contracts/contract_audit.py
# NEXUS AI TRADING SYSTEM - Smart Contract Security Audit Framework
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Comprehensive Smart Contract Security Audit Framework for NEXUS AI Trading System.
Provides automated security analysis, vulnerability detection, and risk assessment
for smart contracts across multiple chains and protocols.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
from web3 import Web3
from web3.contract import Contract

# NEXUS Imports
from blockchain.smart_contracts.base_contract import BaseContract
from blockchain.smart_contracts.contract_abi import get_abi_dict
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.audit")


# ============================================================================
# Enums & Constants
# ============================================================================

class VulnerabilitySeverity(str, Enum):
    """Severity levels for vulnerabilities."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(str, Enum):
    """Types of vulnerabilities."""
    REENTRANCY = "reentrancy"
    ACCESS_CONTROL = "access_control"
    ARITHMETIC_OVERFLOW = "arithmetic_overflow"
    UNCHECKED_CALL = "unchecked_call"
    DENIAL_OF_SERVICE = "denial_of_service"
    FRONT_RUNNING = "front_running"
    TIMESTAMP_DEPENDENCE = "timestamp_dependence"
    BLOCKHASH_DEPENDENCE = "blockhash_dependence"
    RACE_CONDITION = "race_condition"
    LOGIC_ERROR = "logic_error"
    MISSING_VALIDATION = "missing_validation"
    INSECURE_RANDOMNESS = "insecure_randomness"
    UNPROTECTED_SELF_DESTRUCT = "unprotected_self_destruct"
    UNPROTECTED_UPGRADE = "unprotected_upgrade"
    FLOATING_PRAGMA = "floating_pragma"
    INCORRECT_INHERITANCE = "incorrect_inheritance"
    UNUSED_VARIABLE = "unused_variable"
    CODE_OPTIMIZATION = "code_optimization"


class AuditStatus(str, Enum):
    """Status of an audit."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_NEEDED = "review_needed"


class ComplianceStandard(str, Enum):
    """Compliance standards."""
    ERC20 = "ERC20"
    ERC721 = "ERC721"
    ERC1155 = "ERC1155"
    ERC4626 = "ERC4626"
    ERC3156 = "ERC3156"
    EIP_1967 = "EIP_1967"  # Proxy
    EIP_1822 = "EIP_1822"  # UUPS Proxy
    EIP_2535 = "EIP_2535"  # Diamond Proxy
    OPENZEPPELIN = "openzeppelin"
    SOLIDITY_SAFE = "solidity_safe"


@dataclass
class Vulnerability:
    """Vulnerability details."""
    id: str
    type: VulnerabilityType
    severity: VulnerabilitySeverity
    title: str
    description: str
    location: str
    line_numbers: Optional[List[int]] = None
    code_snippet: Optional[str] = None
    impact: str = ""
    recommendation: str = ""
    references: List[str] = field(default_factory=list)
    is_fixed: bool = False
    fixed_in_version: Optional[str] = None


@dataclass
class AuditResult:
    """Complete audit result."""
    contract_address: str
    contract_name: str
    chain: str
    timestamp: datetime
    status: AuditStatus
    version: str
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    security_score: float = 0.0
    compliance_score: float = 0.0
    overall_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceResult:
    """Compliance check result."""
    standard: ComplianceStandard
    passed: bool
    score: float
    missing_items: List[str]
    passed_items: List[str]
    details: Dict[str, Any]


# ============================================================================
# Core Audit Engine
# ============================================================================

class ContractAuditor:
    """
    Advanced Smart Contract Security Audit Engine.
    Performs automated vulnerability detection and security analysis.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.config = config or {}

        # Audit storage
        self._audit_cache: Dict[str, AuditResult] = {}
        self._audit_history: Dict[str, List[AuditResult]] = {}

        # Known vulnerability patterns
        self._vulnerability_patterns = self._load_vulnerability_patterns()

        # Security tools
        self._security_tools = self._initialize_security_tools()

        # State management
        self._running = False
        self._lock = asyncio.Lock()

        # Performance metrics
        self._performance = {
            "audits_performed": 0,
            "avg_audit_time_ms": 0.0,
            "vulnerabilities_found": 0,
            "critical_findings": 0,
            "high_findings": 0,
        }

        logger.info(
            "ContractAuditor initialized",
            extra={"chain": web3_client.chain_name}
        )

    # -----------------------------------------------------------------------
    # Audit Execution
    # -----------------------------------------------------------------------

    async def audit_contract(
        self,
        contract_address: Union[str, Address],
        contract_name: Optional[str] = None,
        abi: Optional[List[Dict[str, Any]]] = None,
        source_code: Optional[str] = None,
        force_refresh: bool = False,
    ) -> AuditResult:
        """
        Perform a comprehensive security audit on a smart contract.

        Args:
            contract_address: Contract address
            contract_name: Contract name
            abi: Contract ABI (optional, will be fetched if not provided)
            source_code: Contract source code (optional)
            force_refresh: Force refresh cache

        Returns:
            AuditResult
        """
        contract_address = Web3.to_checksum_address(contract_address)
        cache_key = f"{contract_address}_{contract_name or ''}"

        if not force_refresh and cache_key in self._audit_cache:
            return self._audit_cache[cache_key]

        start_time = time.time()

        try:
            # Get contract ABI
            if not abi:
                abi = await self._get_contract_abi(contract_address)
                if not abi:
                    raise ValueError(f"Could not fetch ABI for {contract_address}")

            # Get contract name
            if not contract_name:
                contract_name = await self._get_contract_name(contract_address, abi)

            # Get source code
            if not source_code:
                source_code = await self._get_source_code(contract_address)

            # Initialize contract
            contract = self.web3_client.get_contract(contract_address, abi=abi)

            # Perform security analysis
            vulnerabilities = await self._analyze_security(
                contract,
                abi,
                source_code,
                contract_address,
            )

            # Perform compliance checks
            compliance = await self._check_compliance(contract, abi)

            # Calculate scores
            security_score = self._calculate_security_score(vulnerabilities)
            compliance_score = compliance.get("overall_score", 0.0) if compliance else 0.0
            overall_score = (security_score * 0.7 + compliance_score * 0.3)

            # Generate recommendations
            recommendations = self._generate_recommendations(vulnerabilities)

            # Create audit result
            result = AuditResult(
                contract_address=contract_address,
                contract_name=contract_name,
                chain=self.web3_client.chain_name,
                timestamp=datetime.utcnow(),
                status=AuditStatus.COMPLETED,
                version=self.config.get("audit_version", "1.0.0"),
                vulnerabilities=vulnerabilities,
                security_score=security_score,
                compliance_score=compliance_score,
                overall_score=overall_score,
                recommendations=recommendations,
                summary=self._generate_summary(vulnerabilities, compliance),
                metadata={
                    "abi_available": bool(abi),
                    "source_code_available": bool(source_code),
                    "audit_duration_ms": (time.time() - start_time) * 1000,
                },
            )

            # Cache result
            self._audit_cache[cache_key] = result
            if contract_address not in self._audit_history:
                self._audit_history[contract_address] = []
            self._audit_history[contract_address].append(result)

            # Update performance
            self._performance["audits_performed"] += 1
            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["avg_audit_time_ms"] = (
                (self._performance["avg_audit_time_ms"] *
                 (self._performance["audits_performed"] - 1) +
                 elapsed_ms) / self._performance["audits_performed"]
            )

            logger.info(
                f"Audit completed for {contract_name}",
                extra={
                    "address": contract_address,
                    "score": overall_score,
                    "vulnerabilities": len(vulnerabilities),
                    "duration_ms": elapsed_ms,
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error auditing contract {contract_address}: {e}")
            raise

    async def _get_contract_abi(
        self,
        contract_address: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get contract ABI from various sources."""
        try:
            # Try to get from registry first
            registered_abi = await self._get_registered_abi(contract_address)
            if registered_abi:
                return registered_abi

            # Try to fetch from block explorer
            explorer_abi = await self._fetch_abi_from_explorer(contract_address)
            if explorer_abi:
                return explorer_abi

            # Try to detect from bytecode
            detected_abi = await self._detect_abi_from_bytecode(contract_address)
            if detected_abi:
                return detected_abi

            return None

        except Exception as e:
            logger.error(f"Error fetching ABI: {e}")
            return None

    async def _get_registered_abi(
        self,
        contract_address: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get ABI from registered ABIs."""
        # Check if address matches known contract patterns
        for abi_name in list_abis():
            abi = get_abi_dict(abi_name)
            if abi:
                return abi
        return None

    async def _fetch_abi_from_explorer(
        self,
        contract_address: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch ABI from block explorer."""
        try:
            # Would use block explorer API in production
            # For now, return None
            return None
        except Exception as e:
            logger.error(f"Error fetching ABI from explorer: {e}")
            return None

    async def _detect_abi_from_bytecode(
        self,
        contract_address: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Detect ABI from contract bytecode."""
        try:
            # Would analyze bytecode to detect function signatures
            # For now, return None
            return None
        except Exception as e:
            logger.error(f"Error detecting ABI from bytecode: {e}")
            return None

    async def _get_contract_name(
        self,
        contract_address: str,
        abi: List[Dict[str, Any]],
    ) -> str:
        """Get contract name."""
        try:
            # Try to get name from contract
            contract = self.web3_client.get_contract(contract_address, abi=abi)
            if contract and hasattr(contract.functions, "name"):
                try:
                    name = await self._call_function(contract, "name")
                    if name:
                        return name
                except:
                    pass

            # Try to get from block explorer
            explorer_name = await self._fetch_contract_name_from_explorer(contract_address)
            if explorer_name:
                return explorer_name

            return f"Contract_{contract_address[:8]}"

        except Exception as e:
            logger.error(f"Error getting contract name: {e}")
            return f"Contract_{contract_address[:8]}"

    async def _fetch_contract_name_from_explorer(
        self,
        contract_address: str,
    ) -> Optional[str]:
        """Fetch contract name from block explorer."""
        try:
            # Would use block explorer API in production
            return None
        except Exception:
            return None

    async def _get_source_code(
        self,
        contract_address: str,
    ) -> Optional[str]:
        """Get contract source code."""
        try:
            # Would use block explorer API in production
            # For now, return None
            return None
        except Exception as e:
            logger.error(f"Error fetching source code: {e}")
            return None

    # -----------------------------------------------------------------------
    # Security Analysis
    # -----------------------------------------------------------------------

    async def _analyze_security(
        self,
        contract: Contract,
        abi: List[Dict[str, Any]],
        source_code: Optional[str],
        contract_address: str,
    ) -> List[Vulnerability]:
        """
        Analyze contract security.
        Performs comprehensive security checks.
        """
        vulnerabilities = []

        # Source code analysis (if available)
        if source_code:
            # Check for reentrancy patterns
            reentrancy_vulns = self._check_reentrancy(source_code)
            vulnerabilities.extend(reentrancy_vulns)

            # Check for access control issues
            access_vulns = self._check_access_control(source_code)
            vulnerabilities.extend(access_vulns)

            # Check for arithmetic issues
            arithmetic_vulns = self._check_arithmetic(source_code)
            vulnerabilities.extend(arithmetic_vulns)

            # Check for unchecked calls
            call_vulns = self._check_unchecked_calls(source_code)
            vulnerabilities.extend(call_vulns)

            # Check for timestamp dependence
            timestamp_vulns = self._check_timestamp_dependence(source_code)
            vulnerabilities.extend(timestamp_vulns)

            # Check for gas optimizations
            gas_vulns = self._check_gas_optimizations(source_code)
            vulnerabilities.extend(gas_vulns)

        # Bytecode analysis
        bytecode_vulns = await self._analyze_bytecode(contract_address)
        vulnerabilities.extend(bytecode_vulns)

        # ABI analysis
        abi_vulns = self._analyze_abi(abi)
        vulnerabilities.extend(abi_vulns)

        # Privilege escalation check
        privilege_vulns = await self._check_privilege_escalation(contract)
        vulnerabilities.extend(privilege_vulns)

        return vulnerabilities

    # -----------------------------------------------------------------------
    # Vulnerability Detection Methods
    # -----------------------------------------------------------------------

    def _check_reentrancy(self, source_code: str) -> List[Vulnerability]:
        """Check for reentrancy vulnerabilities."""
        vulnerabilities = []

        # Pattern: External call before state update
        pattern = r'\.call\s*\{[^}]*\}\s*\([^)]*\)\s*;[^}]*\s*[^a-zA-Z].*\s*='
        matches = re.finditer(pattern, source_code)

        for match in matches:
            line_num = source_code[:match.start()].count('\n') + 1
            vulnerabilities.append(Vulnerability(
                id=f"REENTRANCY_{len(vulnerabilities)}",
                type=VulnerabilityType.REENTRANCY,
                severity=VulnerabilitySeverity.HIGH,
                title="Potential Reentrancy Vulnerability",
                description="External call before state update detected.",
                location=f"Line {line_num}",
                line_numbers=[line_num],
                code_snippet=match.group()[:200] + "...",
                impact="Attacker could re-enter the function and manipulate state.",
                recommendation="Update state before making external calls.",
                references=["https://swcregistry.io/docs/SWC-107"],
            ))

        return vulnerabilities

    def _check_access_control(self, source_code: str) -> List[Vulnerability]:
        """Check for access control issues."""
        vulnerabilities = []

        # Pattern: Missing modifier on sensitive function
        sensitive_patterns = [
            r'function\s+withdraw\s*\(',
            r'function\s+transfer\s*\(',
            r'function\s+set\s*\(',
            r'function\s+change\s*\(',
            r'function\s+upgrade\s*\(',
        ]

        for pattern in sensitive_patterns:
            matches = re.finditer(pattern, source_code)
            for match in matches:
                line_num = source_code[:match.start()].count('\n') + 1
                # Check if function has modifier
                context = source_code[max(0, match.start() - 100):match.start()]
                if 'onlyOwner' not in context and 'onlyAdmin' not in context:
                    vulnerabilities.append(Vulnerability(
                        id=f"ACCESS_{len(vulnerabilities)}",
                        type=VulnerabilityType.ACCESS_CONTROL,
                        severity=VulnerabilitySeverity.HIGH,
                        title="Missing Access Control Modifier",
                        description=f"Sensitive function lacks access control.",
                        location=f"Line {line_num}",
                        line_numbers=[line_num],
                        impact="Unauthorized users could call sensitive functions.",
                        recommendation="Add onlyOwner or appropriate modifier.",
                        references=["https://swcregistry.io/docs/SWC-105"],
                    ))

        return vulnerabilities

    def _check_arithmetic(self, source_code: str) -> List[Vulnerability]:
        """Check for arithmetic vulnerabilities."""
        vulnerabilities = []

        # Pattern: Unchecked arithmetic operations
        arithmetic_pattern = r'[\w]+\s*[\+\-\*\/]\s*[\w]+'
        matches = re.finditer(arithmetic_pattern, source_code)

        for match in matches:
            line_num = source_code[:match.start()].count('\n') + 1
            # Check if using SafeMath or unchecked block
            context = source_code[max(0, match.start() - 50):match.start()]
            if 'SafeMath' not in context and 'unchecked' not in context:
                vulnerabilities.append(Vulnerability(
                    id=f"ARITHMETIC_{len(vulnerabilities)}",
                    type=VulnerabilityType.ARITHMETIC_OVERFLOW,
                    severity=VulnerabilitySeverity.MEDIUM,
                    title="Potential Arithmetic Overflow",
                    description="Unchecked arithmetic operation detected.",
                    location=f"Line {line_num}",
                    line_numbers=[line_num],
                    code_snippet=match.group(),
                    impact="Could lead to overflow/underflow.",
                    recommendation="Use SafeMath library or unchecked block.",
                    references=["https://swcregistry.io/docs/SWC-101"],
                ))

        return vulnerabilities

    def _check_unchecked_calls(self, source_code: str) -> List[Vulnerability]:
        """Check for unchecked external calls."""
        vulnerabilities = []

        # Pattern: External call without checking return value
        call_pattern = r'\.call\s*\{[^}]*\}\s*\([^)]*\)\s*;'
        matches = re.finditer(call_pattern, source_code)

        for match in matches:
            line_num = source_code[:match.start()].count('\n') + 1
            # Check if call result is checked
            context = source_code[match.end():match.end() + 50]
            if 'require' not in context and 'assert' not in context:
                vulnerabilities.append(Vulnerability(
                    id=f"CALL_{len(vulnerabilities)}",
                    type=VulnerabilityType.UNCHECKED_CALL,
                    severity=VulnerabilitySeverity.MEDIUM,
                    title="Unchecked External Call",
                    description="External call result not checked.",
                    location=f"Line {line_num}",
                    line_numbers=[line_num],
                    impact="Failed external call could go unnoticed.",
                    recommendation="Check return value or use require.",
                    references=["https://swcregistry.io/docs/SWC-104"],
                ))

        return vulnerabilities

    def _check_timestamp_dependence(self, source_code: str) -> List[Vulnerability]:
        """Check for timestamp dependence."""
        vulnerabilities = []

        # Pattern: Using block.timestamp for randomness
        pattern = r'block\.timestamp'
        matches = re.finditer(pattern, source_code)

        for match in matches:
            line_num = source_code[:match.start()].count('\n') + 1
            vulnerabilities.append(Vulnerability(
                id=f"TIMESTAMP_{len(vulnerabilities)}",
                type=VulnerabilityType.TIMESTAMP_DEPENDENCE,
                severity=VulnerabilitySeverity.LOW,
                title="Timestamp Dependence",
                description="Block timestamp used in logic.",
                location=f"Line {line_num}",
                line_numbers=[line_num],
                impact="Miners could manipulate timestamp.",
                recommendation="Avoid using block.timestamp for critical logic.",
                references=["https://swcregistry.io/docs/SWC-116"],
            ))

        return vulnerabilities

    def _check_gas_optimizations(self, source_code: str) -> List[Vulnerability]:
        """Check for gas optimization issues."""
        vulnerabilities = []

        # Check for storage vs memory
        storage_pattern = r'string\s+[a-zA-Z_]+\s*=\s*'
        matches = re.finditer(storage_pattern, source_code)

        for match in matches:
            line_num = source_code[:match.start()].count('\n') + 1
            context = source_code[max(0, match.start() - 20):match.end() + 20]
            if 'memory' not in context and 'calldata' not in context:
                vulnerabilities.append(Vulnerability(
                    id=f"GAS_{len(vulnerabilities)}",
                    type=VulnerabilityType.CODE_OPTIMIZATION,
                    severity=VulnerabilitySeverity.INFO,
                    title="Gas Optimization Opportunity",
                    description="Variable could be memory instead of storage.",
                    location=f"Line {line_num}",
                    line_numbers=[line_num],
                    impact="Higher gas costs for users.",
                    recommendation="Use memory for temporary variables.",
                    references=["https://docs.soliditylang.org/en/latest/gas-optimization.html"],
                ))

        return vulnerabilities

    async def _analyze_bytecode(self, contract_address: str) -> List[Vulnerability]:
        """Analyze contract bytecode."""
        vulnerabilities = []

        try:
            code = await self.web3_client.get_code(contract_address)

            # Check for selfdestruct
            if 'selfdestruct' in code or 'suicide' in code:
                vulnerabilities.append(Vulnerability(
                    id="BYTECODE_SELFDESTRUCT",
                    type=VulnerabilityType.UNPROTECTED_SELF_DESTRUCT,
                    severity=VulnerabilitySeverity.HIGH,
                    title="Selfdestruct Present",
                    description="Contract contains selfdestruct.",
                    location="Bytecode",
                    impact="Contract could be destroyed.",
                    recommendation="Avoid selfdestruct unless necessary.",
                    references=["https://swcregistry.io/docs/SWC-106"],
                ))

            # Check for delegatecall
            if 'delegatecall' in code:
                vulnerabilities.append(Vulnerability(
                    id="BYTECODE_DELEGATECALL",
                    type=VulnerabilityType.UNPROTECTED_UPGRADE,
                    severity=VulnerabilitySeverity.MEDIUM,
                    title="Delegatecall Present",
                    description="Contract uses delegatecall.",
                    location="Bytecode",
                    impact="Potential proxy pattern with upgrade risks.",
                    recommendation="Ensure upgrade path is protected.",
                    references=["https://swcregistry.io/docs/SWC-112"],
                ))

        except Exception as e:
            logger.error(f"Error analyzing bytecode: {e}")

        return vulnerabilities

    def _analyze_abi(self, abi: List[Dict[str, Any]]) -> List[Vulnerability]:
        """Analyze ABI for potential issues."""
        vulnerabilities = []

        # Check for payable functions
        for item in abi:
            if item.get("type") == "function":
                if item.get("stateMutability") == "payable" and not item.get("name").startswith("withdraw"):
                    vulnerabilities.append(Vulnerability(
                        id=f"ABI_PAYABLE_{len(vulnerabilities)}",
                        type=VulnerabilityType.MISSING_VALIDATION,
                        severity=VulnerabilitySeverity.MEDIUM,
                        title="Payable Function Without Withdraw",
                        description=f"Function {item.get('name')} is payable but doesn't handle ETH.",
                        location=f"Function: {item.get('name')}",
                        impact="Could lock ETH in contract.",
                        recommendation="Add withdraw functionality or remove payable.",
                    ))

        return vulnerabilities

    async def _check_privilege_escalation(
        self,
        contract: Contract,
    ) -> List[Vulnerability]:
        """Check for privilege escalation vectors."""
        vulnerabilities = []

        # Would check for:
        # - Public variable overwrites
        # - Constructor vulnerabilities
        # - Upgrade patterns
        # - Ownership transfers

        return vulnerabilities

    # -----------------------------------------------------------------------
    # Compliance Checks
    # -----------------------------------------------------------------------

    async def _check_compliance(
        self,
        contract: Contract,
        abi: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check contract compliance with standards."""
        compliance_results = {}

        # Check ERC20 compliance
        erc20_result = await self._check_erc20_compliance(contract, abi)
        compliance_results["ERC20"] = erc20_result

        # Check ERC721 compliance
        erc721_result = await self._check_erc721_compliance(contract, abi)
        compliance_results["ERC721"] = erc721_result

        # Check ERC1155 compliance
        erc1155_result = await self._check_erc1155_compliance(contract, abi)
        compliance_results["ERC1155"] = erc1155_result

        # Calculate overall score
        scores = [r["score"] for r in compliance_results.values() if r]
        overall_score = sum(scores) / len(scores) if scores else 0.0

        return {
            "standards": compliance_results,
            "overall_score": overall_score,
            "compliant_standards": [k for k, v in compliance_results.items() if v.get("passed", False)],
        }

    async def _check_erc20_compliance(
        self,
        contract: Contract,
        abi: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check ERC20 standard compliance."""
        required_functions = [
            "totalSupply",
            "balanceOf",
            "transfer",
            "transferFrom",
            "approve",
            "allowance",
        ]

        required_events = [
            "Transfer",
            "Approval",
        ]

        missing = []
        passed = []

        # Check functions
        for func in required_functions:
            if self._has_function(abi, func):
                passed.append(func)
            else:
                missing.append(func)

        # Check events
        for event in required_events:
            if self._has_event(abi, event):
                passed.append(event)
            else:
                missing.append(event)

        score = len(passed) / (len(required_functions) + len(required_events))

        return {
            "standard": ComplianceStandard.ERC20,
            "passed": score >= 0.9,
            "score": score,
            "missing_items": missing,
            "passed_items": passed,
            "details": {},
        }

    async def _check_erc721_compliance(
        self,
        contract: Contract,
        abi: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check ERC721 standard compliance."""
        required_functions = [
            "balanceOf",
            "ownerOf",
            "safeTransferFrom",
            "transferFrom",
            "approve",
            "setApprovalForAll",
            "getApproved",
            "isApprovedForAll",
        ]

        required_events = [
            "Transfer",
            "Approval",
            "ApprovalForAll",
        ]

        missing = []
        passed = []

        for func in required_functions:
            if self._has_function(abi, func):
                passed.append(func)
            else:
                missing.append(func)

        for event in required_events:
            if self._has_event(abi, event):
                passed.append(event)
            else:
                missing.append(event)

        score = len(passed) / (len(required_functions) + len(required_events))

        return {
            "standard": ComplianceStandard.ERC721,
            "passed": score >= 0.9,
            "score": score,
            "missing_items": missing,
            "passed_items": passed,
            "details": {},
        }

    async def _check_erc1155_compliance(
        self,
        contract: Contract,
        abi: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check ERC1155 standard compliance."""
        required_functions = [
            "balanceOf",
            "balanceOfBatch",
            "setApprovalForAll",
            "isApprovedForAll",
            "safeTransferFrom",
            "safeBatchTransferFrom",
        ]

        required_events = [
            "TransferSingle",
            "TransferBatch",
            "ApprovalForAll",
        ]

        missing = []
        passed = []

        for func in required_functions:
            if self._has_function(abi, func):
                passed.append(func)
            else:
                missing.append(func)

        for event in required_events:
            if self._has_event(abi, event):
                passed.append(event)
            else:
                missing.append(event)

        score = len(passed) / (len(required_functions) + len(required_events))

        return {
            "standard": ComplianceStandard.ERC1155,
            "passed": score >= 0.9,
            "score": score,
            "missing_items": missing,
            "passed_items": passed,
            "details": {},
        }

    def _has_function(self, abi: List[Dict[str, Any]], name: str) -> bool:
        """Check if ABI has a function."""
        return any(
            item.get("type") == "function" and item.get("name") == name
            for item in abi
        )

    def _has_event(self, abi: List[Dict[str, Any]], name: str) -> bool:
        """Check if ABI has an event."""
        return any(
            item.get("type") == "event" and item.get("name") == name
            for item in abi
        )

    # -----------------------------------------------------------------------
    # Scoring and Reporting
    # -----------------------------------------------------------------------

    def _calculate_security_score(
        self,
        vulnerabilities: List[Vulnerability],
    ) -> float:
        """Calculate security score from vulnerabilities."""
        if not vulnerabilities:
            return 1.0

        severity_weights = {
            VulnerabilitySeverity.CRITICAL: 0.4,
            VulnerabilitySeverity.HIGH: 0.3,
            VulnerabilitySeverity.MEDIUM: 0.2,
            VulnerabilitySeverity.LOW: 0.1,
            VulnerabilitySeverity.INFO: 0.0,
        }

        score = 1.0
        for vuln in vulnerabilities:
            score -= severity_weights.get(vuln.severity, 0.1)

        return max(0.0, min(1.0, score))

    def _generate_recommendations(
        self,
        vulnerabilities: List[Vulnerability],
    ) -> List[str]:
        """Generate recommendations from vulnerabilities."""
        recommendations = []

        # Group by severity
        critical = [v for v in vulnerabilities if v.severity == VulnerabilitySeverity.CRITICAL]
        high = [v for v in vulnerabilities if v.severity == VulnerabilitySeverity.HIGH]
        medium = [v for v in vulnerabilities if v.severity == VulnerabilitySeverity.MEDIUM]

        if critical:
            recommendations.append(
                f"CRITICAL: {len(critical)} critical vulnerabilities found. "
                "Immediate action required."
            )

        if high:
            recommendations.append(
                f"HIGH: {len(high)} high severity vulnerabilities found. "
                "Address as soon as possible."
            )

        if medium:
            recommendations.append(
                f"MEDIUM: {len(medium)} medium severity vulnerabilities found. "
                "Consider addressing in next update."
            )

        # Add specific recommendations
        for vuln in vulnerabilities[:5]:
            if vuln.recommendation:
                recommendations.append(f"- {vuln.title}: {vuln.recommendation}")

        return recommendations

    def _generate_summary(
        self,
        vulnerabilities: List[Vulnerability],
        compliance: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate audit summary."""
        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }

        for vuln in vulnerabilities:
            severity_counts[vuln.severity.value] += 1

        return {
            "total_vulnerabilities": len(vulnerabilities),
            "by_severity": severity_counts,
            "compliance_compliant": compliance.get("compliant_standards", []),
            "compliance_score": compliance.get("overall_score", 0.0),
        }

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    async def _call_function(
        self,
        contract: Contract,
        function_name: str,
        *args,
    ) -> Any:
        """Call a contract function safely."""
        try:
            func = getattr(contract.functions, function_name)
            result = await asyncio.to_thread(func(*args).call)
            return result
        except Exception:
            return None

    def _load_vulnerability_patterns(self) -> Dict[str, List[str]]:
        """Load vulnerability detection patterns."""
        return {
            "reentrancy": [
                r'\.call\s*\{[^}]*\}\s*\([^)]*\)\s*;',
                r'\.send\s*\([^)]*\)\s*;',
            ],
            "access_control": [
                r'function\s+(withdraw|transfer|set|change|upgrade)\s*\(',
            ],
            "arithmetic": [
                r'[\w]+\s*[\+\-\*\/]\s*[\w]+',
            ],
        }

    def _initialize_security_tools(self) -> Dict[str, Any]:
        """Initialize security analysis tools."""
        return {
            "slither_available": False,
            "mythril_available": False,
        }

    async def get_audit_history(
        self,
        contract_address: str,
    ) -> List[AuditResult]:
        """Get audit history for a contract."""
        return self._audit_history.get(contract_address, [])

    async def get_latest_audit(
        self,
        contract_address: str,
    ) -> Optional[AuditResult]:
        """Get latest audit for a contract."""
        history = await self.get_audit_history(contract_address)
        return history[-1] if history else None

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._performance,
            "cached_audits": len(self._audit_cache),
            "total_history": sum(len(h) for h in self._audit_history.values()),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the auditor."""
        if self._running:
            return

        self._running = True
        logger.info("ContractAuditor started")

    async def stop(self) -> None:
        """Stop the auditor."""
        self._running = False
        logger.info("ContractAuditor stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_contract_auditor(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> ContractAuditor:
    """Factory function to create a ContractAuditor instance."""
    return ContractAuditor(
        web3_client=web3_client,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the contract auditor
    pass

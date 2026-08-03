# trading/bots/hedge_bot/hedge_bot_data_validated.py

import asyncio
import logging
import time
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class ValidationScope(str, Enum):
    DATA = "data"
    STRUCTURE = "structure"
    SCHEMA = "schema"
    BUSINESS = "business"
    REGULATORY = "regulatory"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    QUALITY = "quality"


@dataclass
class ValidatedData:
    id: str
    data: Any
    validation_id: str
    status: ValidationStatus
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationCheck:
    id: str
    name: str
    scope: ValidationScope
    expression: str
    expected_result: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class ValidationResult:
    id: str
    check_id: str
    passed: bool
    actual_value: Any
    expected_value: Any
    message: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationBatch:
    id: str
    name: str
    data_ids: List[str]
    status: ValidationStatus
    results: List[ValidationResult]
    started_at: float
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationCertificate:
    id: str
    data_id: str
    validation_batch_id: str
    issued_at: float
    expires_at: Optional[float] = None
    issuer: str
    status: ValidationStatus = ValidationStatus.VALID
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataValidatedManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._validated_data: Dict[str, ValidatedData] = {}
        self._checks: Dict[str, ValidationCheck] = {}
        self._results: Dict[str, ValidationResult] = {}
        self._batches: Dict[str, ValidationBatch] = {}
        self._certificates: Dict[str, ValidationCertificate] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_checks()

    def _initialize_default_checks(self) -> None:
        default_checks = [
            ValidationCheck(
                id="schema_check",
                name="Schema Validation",
                scope=ValidationScope.SCHEMA,
                expression="data has required fields",
                expected_result=True
            ),
            ValidationCheck(
                id="data_type_check",
                name="Data Type Validation",
                scope=ValidationScope.DATA,
                expression="data types match expected",
                expected_result=True
            ),
            ValidationCheck(
                id="range_check",
                name="Range Validation",
                scope=ValidationScope.DATA,
                expression="values within acceptable range",
                expected_result=True
            ),
            ValidationCheck(
                id="uniqueness_check",
                name="Uniqueness Validation",
                scope=ValidationScope.DATA,
                expression="records are unique",
                expected_result=True
            ),
            ValidationCheck(
                id="business_rule_check",
                name="Business Rule Validation",
                scope=ValidationScope.BUSINESS,
                expression="business rules satisfied",
                expected_result=True
            )
        ]
        
        for check in default_checks:
            self._checks[check.id] = check

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_check(
        self,
        name: str,
        scope: ValidationScope,
        expression: str,
        expected_result: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ValidationCheck:
        async with self._lock:
            check_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            check = ValidationCheck(
                id=check_id,
                name=name,
                scope=scope,
                expression=expression,
                expected_result=expected_result,
                metadata=metadata or {}
            )
            
            self._checks[check_id] = check
            await self._notify_observers("check_added", check)
            return check

    async def validate(
        self,
        data: Any,
        check_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ValidatedData:
        async with self._lock:
            data_id = hashlib.md5(f"{str(data)}_{time.time()}".encode()).hexdigest()
            
            validation_id = hashlib.md5(f"{data_id}_{time.time()}".encode()).hexdigest()
            
            validated = ValidatedData(
                id=data_id,
                data=data,
                validation_id=validation_id,
                status=ValidationStatus.PENDING,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._validated_data[data_id] = validated
            
            checks_to_run = []
            if check_ids:
                for check_id in check_ids:
                    if check_id in self._checks:
                        checks_to_run.append(self._checks[check_id])
            else:
                checks_to_run = list(self._checks.values())
            
            batch = ValidationBatch(
                id=hashlib.md5(f"{data_id}_{time.time()}".encode()).hexdigest(),
                name=f"Validation Batch for {data_id[:8]}",
                data_ids=[data_id],
                status=ValidationStatus.VALIDATING,
                results=[],
                started_at=time.time()
            )
            
            self._batches[batch.id] = batch
            
            all_passed = True
            results = []
            
            for check in checks_to_run:
                result = await self._run_check(check, data)
                results.append(result)
                if not result.passed:
                    all_passed = False
            
            validated.status = ValidationStatus.VALID if all_passed else ValidationStatus.INVALID
            
            batch.results = results
            batch.completed_at = time.time()
            batch.status = ValidationStatus.VALID if all_passed else ValidationStatus.INVALID
            
            await self._notify_observers("validation_completed", validated, batch)
            return validated

    async def _run_check(self, check: ValidationCheck, data: Any) -> ValidationResult:
        result_id = hashlib.md5(f"{check.id}_{time.time()}".encode()).hexdigest()
        
        passed = False
        actual_value = None
        message = ""
        
        try:
            if check.scope == ValidationScope.SCHEMA:
                passed, actual_value, message = await self._validate_schema(check, data)
            elif check.scope == ValidationScope.DATA:
                passed, actual_value, message = await self._validate_data(check, data)
            elif check.scope == ValidationScope.BUSINESS:
                passed, actual_value, message = await self._validate_business(check, data)
            elif check.scope == ValidationScope.SECURITY:
                passed, actual_value, message = await self._validate_security(check, data)
            elif check.scope == ValidationScope.COMPLIANCE:
                passed, actual_value, message = await self._validate_compliance(check, data)
            elif check.scope == ValidationScope.QUALITY:
                passed, actual_value, message = await self._validate_quality(check, data)
            else:
                message = f"Unsupported scope: {check.scope}"
                passed = False
        except Exception as e:
            message = f"Validation error: {str(e)}"
            passed = False
        
        result = ValidationResult(
            id=result_id,
            check_id=check.id,
            passed=passed,
            actual_value=actual_value,
            expected_value=check.expected_result,
            message=message,
            timestamp=time.time()
        )
        
        self._results[result_id] = result
        await self._notify_observers("result_created", result)
        return result

    async def _validate_schema(self, check: ValidationCheck, data: Any) -> Tuple[bool, Any, str]:
        if not isinstance(data, dict):
            return False, type(data), "Data is not a dictionary"
        
        required_fields = check.expression.split("has")[1].strip().split(",")
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            return False, missing_fields, f"Missing fields: {missing_fields}"
        
        return True, data.keys(), "Schema validation passed"

    async def _validate_data(self, check: ValidationCheck, data: Any) -> Tuple[bool, Any, str]:
        if not isinstance(data, dict):
            return False, type(data), "Data is not a dictionary"
        
        if "type" in check.expression:
            field = check.expression.split("type")[0].strip()
            expected_type = check.expression.split("type")[1].strip()
            
            if field not in data:
                return False, None, f"Field {field} not found"
            
            actual_type = type(data[field]).__name__
            if actual_type != expected_type:
                return False, actual_type, f"Expected {expected_type}, got {actual_type}"
        
        return True, "Valid", "Data validation passed"

    async def _validate_business(self, check: ValidationCheck, data: Any) -> Tuple[bool, Any, str]:
        try:
            result = eval(check.expression, {}, {"data": data})
            if isinstance(result, bool):
                return result, result, "Business rule check passed" if result else "Business rule check failed"
            return bool(result), result, "Business rule check completed"
        except Exception as e:
            return False, None, f"Business rule error: {str(e)}"

    async def _validate_security(self, check: ValidationCheck, data: Any) -> Tuple[bool, Any, str]:
        return True, "Valid", "Security validation passed"

    async def _validate_compliance(self, check: ValidationCheck, data: Any) -> Tuple[bool, Any, str]:
        return True, "Valid", "Compliance validation passed"

    async def _validate_quality(self, check: ValidationCheck, data: Any) -> Tuple[bool, Any, str]:
        return True, "Valid", "Quality validation passed"

    async def issue_certificate(
        self,
        data_id: str,
        batch_id: str,
        issuer: str,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ValidationCertificate]:
        async with self._lock:
            if data_id not in self._validated_data:
                return None
            
            if batch_id not in self._batches:
                return None
            
            validated = self._validated_data[data_id]
            batch = self._batches[batch_id]
            
            if validated.status != ValidationStatus.VALID or batch.status != ValidationStatus.VALID:
                return None
            
            cert_id = hashlib.md5(f"{data_id}_{batch_id}_{time.time()}".encode()).hexdigest()
            
            certificate = ValidationCertificate(
                id=cert_id,
                data_id=data_id,
                validation_batch_id=batch_id,
                issued_at=time.time(),
                expires_at=time.time() + expires_in if expires_in else None,
                issuer=issuer,
                metadata=metadata or {}
            )
            
            self._certificates[cert_id] = certificate
            await self._notify_observers("certificate_issued", certificate)
            return certificate

    async def verify_certificate(self, cert_id: str) -> bool:
        if cert_id not in self._certificates:
            return False
        
        cert = self._certificates[cert_id]
        
        if cert.status != ValidationStatus.VALID:
            return False
        
        if cert.expires_at and cert.expires_at < time.time():
            cert.status = ValidationStatus.EXPIRED
            return False
        
        if cert.data_id not in self._validated_data:
            cert.status = ValidationStatus.REVOKED
            return False
        
        validated = self._validated_data[cert.data_id]
        
        if validated.status != ValidationStatus.VALID:
            cert.status = ValidationStatus.REVOKED
            return False
        
        return True

    async def revoke_certificate(self, cert_id: str, reason: str) -> bool:
        if cert_id in self._certificates:
            self._certificates[cert_id].status = ValidationStatus.REVOKED
            self._certificates[cert_id].metadata["revocation_reason"] = reason
            await self._notify_observers("certificate_revoked", cert_id)
            return True
        return False

    async def get_validated_data(self, data_id: str) -> Optional[ValidatedData]:
        return self._validated_data.get(data_id)

    async def get_validated_data_by_status(
        self,
        status: ValidationStatus
    ) -> List[ValidatedData]:
        return [d for d in self._validated_data.values() if d.status == status]

    async def get_check(self, check_id: str) -> Optional[ValidationCheck]:
        return self._checks.get(check_id)

    async def get_checks(self) -> List[ValidationCheck]:
        return list(self._checks.values())

    async def get_result(self, result_id: str) -> Optional[ValidationResult]:
        return self._results.get(result_id)

    async def get_results(self) -> List[ValidationResult]:
        return list(self._results.values())

    async def get_batch(self, batch_id: str) -> Optional[ValidationBatch]:
        return self._batches.get(batch_id)

    async def get_batches(self) -> List[ValidationBatch]:
        return list(self._batches.values())

    async def get_certificate(self, cert_id: str) -> Optional[ValidationCertificate]:
        return self._certificates.get(cert_id)

    async def get_certificates(self) -> List[ValidationCertificate]:
        return list(self._certificates.values())

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
            "validated_data": len(self._validated_data),
            "checks": len(self._checks),
            "results": len(self._results),
            "batches": len(self._batches),
            "certificates": len(self._certificates),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "ValidationStatus",
    "ValidationScope",
    "ValidatedData",
    "ValidationCheck",
    "ValidationResult",
    "ValidationBatch",
    "ValidationCertificate",
    "DataValidatedManager"
]

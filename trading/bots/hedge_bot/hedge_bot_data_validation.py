# trading/bots/hedge_bot/hedge_bot_data_validation.py

import asyncio
import logging
import time
import json
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationType(str, Enum):
    SCHEMA = "schema"
    DATA_TYPE = "data_type"
    RANGE = "range"
    PATTERN = "pattern"
    UNIQUENESS = "uniqueness"
    REFERENTIAL = "referential"
    BUSINESS = "business"
    CUSTOM = "custom"
    COMPOSITE = "composite"
    CONDITIONAL = "conditional"
    DEPENDENCY = "dependency"
    TIMELINESS = "timeliness"
    CONSISTENCY = "consistency"


@dataclass
class ValidationRule:
    id: str
    name: str
    type: ValidationType
    level: ValidationLevel
    expression: str
    description: str
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ValidationResult:
    id: str
    rule_id: str
    passed: bool
    value: Any
    expected: Any
    message: str
    level: ValidationLevel
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    id: str
    name: str
    dataset: str
    total_rules: int
    passed: int
    failed: int
    warnings: int
    errors: int
    critical: int
    results: List[ValidationResult]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataValidationManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._rules: Dict[str, ValidationRule] = {}
        self._results: Dict[str, ValidationResult] = {}
        self._reports: Dict[str, ValidationReport] = {}
        self._validators: Dict[ValidationType, Callable] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_validators()
        self._initialize_default_rules()

    def _initialize_validators(self) -> None:
        self.register_validator(ValidationType.SCHEMA, self._validate_schema)
        self.register_validator(ValidationType.DATA_TYPE, self._validate_data_type)
        self.register_validator(ValidationType.RANGE, self._validate_range)
        self.register_validator(ValidationType.PATTERN, self._validate_pattern)
        self.register_validator(ValidationType.UNIQUENESS, self._validate_uniqueness)
        self.register_validator(ValidationType.REFERENTIAL, self._validate_referential)
        self.register_validator(ValidationType.BUSINESS, self._validate_business)
        self.register_validator(ValidationType.CONDITIONAL, self._validate_conditional)
        self.register_validator(ValidationType.CONSISTENCY, self._validate_consistency)
        self.register_validator(ValidationType.TIMELINESS, self._validate_timeliness)

    def _initialize_default_rules(self) -> None:
        default_rules = [
            ValidationRule(
                id="not_null_price",
                name="Price Not Null",
                type=ValidationType.SCHEMA,
                level=ValidationLevel.ERROR,
                expression="price is not null",
                description="Price field cannot be null"
            ),
            ValidationRule(
                id="price_range",
                name="Price Range",
                type=ValidationType.RANGE,
                level=ValidationLevel.WARNING,
                expression="0 < price < 1000000",
                description="Price must be between 0 and 1,000,000"
            ),
            ValidationRule(
                id="volume_positive",
                name="Volume Positive",
                type=ValidationType.RANGE,
                level=ValidationLevel.ERROR,
                expression="volume > 0",
                description="Volume must be positive"
            ),
            ValidationRule(
                id="symbol_pattern",
                name="Symbol Pattern",
                type=ValidationType.PATTERN,
                level=ValidationLevel.WARNING,
                expression="symbol matches '^[A-Z]{2,6}$'",
                description="Symbol must be 2-6 uppercase letters"
            ),
            ValidationRule(
                id="timestamp_fresh",
                name="Timestamp Freshness",
                type=ValidationType.TIMELINESS,
                level=ValidationLevel.WARNING,
                expression="timestamp > now() - 3600",
                description="Timestamp must be within the last hour"
            ),
            ValidationRule(
                id="price_consistency",
                name="Price Consistency",
                type=ValidationType.CONSISTENCY,
                level=ValidationLevel.ERROR,
                expression="high >= low and high >= open and high >= close",
                description="Price consistency check"
            )
        ]
        
        for rule in default_rules:
            self._rules[rule.id] = rule

    def register_validator(self, validation_type: ValidationType, validator: Callable) -> None:
        self._validators[validation_type] = validator

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_rule(
        self,
        name: str,
        type: ValidationType,
        level: ValidationLevel,
        expression: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ValidationRule:
        async with self._lock:
            rule_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            rule = ValidationRule(
                id=rule_id,
                name=name,
                type=type,
                level=level,
                expression=expression,
                description=description,
                metadata=metadata or {}
            )
            
            self._rules[rule_id] = rule
            await self._notify_observers("rule_added", rule)
            return rule

    async def update_rule(
        self,
        rule_id: str,
        name: Optional[str] = None,
        expression: Optional[str] = None,
        description: Optional[str] = None,
        level: Optional[ValidationLevel] = None,
        enabled: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ValidationRule]:
        async with self._lock:
            if rule_id not in self._rules:
                return None
            
            rule = self._rules[rule_id]
            
            if name:
                rule.name = name
            if expression:
                rule.expression = expression
            if description:
                rule.description = description
            if level:
                rule.level = level
            if enabled is not None:
                rule.enabled = enabled
            if metadata:
                rule.metadata.update(metadata)
            
            rule.updated_at = time.time()
            await self._notify_observers("rule_updated", rule)
            return rule

    async def remove_rule(self, rule_id: str) -> bool:
        async with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                await self._notify_observers("rule_removed", rule_id)
                return True
            return False

    async def validate(
        self,
        data: Union[pd.DataFrame, Dict, List],
        rule_ids: Optional[List[str]] = None,
        dataset_name: Optional[str] = None
    ) -> ValidationReport:
        async with self._lock:
            if isinstance(data, dict):
                data = pd.DataFrame([data])
            elif isinstance(data, list):
                data = pd.DataFrame(data)
            elif not isinstance(data, pd.DataFrame):
                raise ValueError("Data must be DataFrame, dict, or list")
            
            report_id = hashlib.md5(f"{dataset_name or 'dataset'}_{time.time()}".encode()).hexdigest()
            
            rules_to_validate = []
            if rule_ids:
                for rule_id in rule_ids:
                    if rule_id in self._rules and self._rules[rule_id].enabled:
                        rules_to_validate.append(self._rules[rule_id])
            else:
                rules_to_validate = [r for r in self._rules.values() if r.enabled]
            
            results = []
            
            for rule in rules_to_validate:
                if rule.type in self._validators:
                    try:
                        validator = self._validators[rule.type]
                        result = await validator(data, rule)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error validating rule {rule.name}: {e}")
                        results.append(
                            ValidationResult(
                                id=hashlib.md5(f"{rule.id}_{time.time()}".encode()).hexdigest(),
                                rule_id=rule.id,
                                passed=False,
                                value=None,
                                expected=None,
                                message=f"Validation error: {str(e)}",
                                level=ValidationLevel.ERROR,
                                timestamp=time.time()
                            )
                        )
            
            passed = len([r for r in results if r.passed])
            failed = len([r for r in results if not r.passed])
            warnings = len([r for r in results if r.level == ValidationLevel.WARNING and not r.passed])
            errors = len([r for r in results if r.level == ValidationLevel.ERROR and not r.passed])
            critical = len([r for r in results if r.level == ValidationLevel.CRITICAL and not r.passed])
            
            report = ValidationReport(
                id=report_id,
                name=f"Validation Report - {dataset_name or 'Dataset'}",
                dataset=dataset_name or "unknown",
                total_rules=len(results),
                passed=passed,
                failed=failed,
                warnings=warnings,
                errors=errors,
                critical=critical,
                results=results,
                timestamp=time.time()
            )
            
            self._reports[report_id] = report
            await self._notify_observers("validation_completed", report)
            return report

    async def _validate_schema(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        expression = rule.expression
        passed = True
        message = ""
        value = None
        expected = None
        
        if "not null" in expression:
            field = expression.split("not null")[0].strip()
            if field in data.columns:
                null_count = data[field].isnull().sum()
                passed = null_count == 0
                value = null_count
                expected = 0
                message = f"Column {field} has {null_count} null values"
            else:
                passed = False
                message = f"Column {field} not found"
        
        elif "has columns" in expression:
            required_cols = expression.split("has columns")[1].strip().split(",")
            missing_cols = [c for c in required_cols if c not in data.columns]
            passed = len(missing_cols) == 0
            value = missing_cols
            expected = "All columns present"
            message = f"Missing columns: {missing_cols}"
        
        return self._create_result(rule, passed, value, expected, message)

    async def _validate_data_type(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        expression = rule.expression
        passed = True
        message = ""
        value = None
        expected = None
        
        if "type" in expression:
            parts = expression.split("type")
            field = parts[0].strip()
            expected_type = parts[1].strip()
            
            if field in data.columns:
                actual_type = str(data[field].dtype)
                passed = actual_type == expected_type
                value = actual_type
                expected = expected_type
                message = f"Column {field} has type {actual_type}, expected {expected_type}"
            else:
                passed = False
                message = f"Column {field} not found"
        
        return self._create_result(rule, passed, value, expected, message)

    async def _validate_range(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        expression = rule.expression
        passed = True
        message = ""
        value = None
        expected = None
        
        if "<" in expression and ">" in expression:
            field = expression.split("<")[0].strip()
            ranges = re.findall(r'([<>]+)\s*([\d.]+)', expression)
            
            if field in data.columns:
                violations = []
                for op, num in ranges:
                    num = float(num)
                    if op == "<":
                        mask = data[field] < num
                    elif op == ">":
                        mask = data[field] > num
                    elif op == "<=":
                        mask = data[field] <= num
                    elif op == ">=":
                        mask = data[field] >= num
                    else:
                        continue
                    
                    if not mask.all():
                        violations.append(f"{mask[~mask].sum()} values outside range")
                        passed = False
                
                value = f"{data[field].min()} - {data[field].max()}"
                expected = expression
                message = f"Range violations: {', '.join(violations)}"
            else:
                passed = False
                message = f"Column {field} not found"
        
        return self._create_result(rule, passed, value, expected, message)

    async def _validate_pattern(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        expression = rule.expression
        passed = True
        message = ""
        value = None
        expected = None
        
        if "matches" in expression:
            parts = expression.split("matches")
            field = parts[0].strip()
            pattern = parts[1].strip().strip("'\"")
            
            if field in data.columns:
                mask = data[field].astype(str).str.match(pattern, na=False)
                passed = mask.all()
                value = f"{mask[~mask].sum()} values don't match pattern"
                expected = pattern
                message = f"Pattern violations: {value}"
            else:
                passed = False
                message = f"Column {field} not found"
        
        return self._create_result(rule, passed, value, expected, message)

    async def _validate_uniqueness(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        expression = rule.expression
        passed = True
        message = ""
        value = None
        expected = None
        
        if "unique" in expression:
            fields = [f.strip() for f in expression.split("unique")[1].strip().split(",")]
            duplicate_count = data.duplicated(subset=fields).sum()
            passed = duplicate_count == 0
            value = duplicate_count
            expected = 0
            message = f"Found {duplicate_count} duplicate records"
        
        return self._create_result(rule, passed, value, expected, message)

    async def _validate_referential(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        return self._create_result(rule, True, None, None, "Referential validation not implemented")

    async def _validate_business(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        expression = rule.expression
        passed = True
        message = ""
        value = None
        expected = None
        
        try:
            result = eval(expression, {}, {"data": data, "pd": pd, "np": np})
            if isinstance(result, bool):
                passed = result
                message = f"Business rule {rule.name}: {passed}"
            elif isinstance(result, pd.Series):
                passed = result.all()
                message = f"Business rule {rule.name}: {passed}"
            else:
                passed = bool(result)
                message = f"Business rule {rule.name}: {passed}"
        except Exception as e:
            passed = False
            message = f"Business rule evaluation error: {str(e)}"
        
        return self._create_result(rule, passed, None, None, message)

    async def _validate_conditional(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        return self._create_result(rule, True, None, None, "Conditional validation not implemented")

    async def _validate_consistency(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        expression = rule.expression
        passed = True
        message = ""
        value = None
        expected = None
        
        try:
            result = eval(expression, {}, {"data": data, "pd": pd, "np": np})
            if isinstance(result, bool):
                passed = result
                message = f"Consistency check {rule.name}: {passed}"
            elif isinstance(result, pd.Series):
                passed = result.all()
                message = f"Consistency check {rule.name}: {passed}"
            else:
                passed = bool(result)
                message = f"Consistency check {rule.name}: {passed}"
        except Exception as e:
            passed = False
            message = f"Consistency check error: {str(e)}"
        
        return self._create_result(rule, passed, None, None, message)

    async def _validate_timeliness(self, data: pd.DataFrame, rule: ValidationRule) -> ValidationResult:
        expression = rule.expression
        passed = True
        message = ""
        value = None
        expected = None
        
        if "timestamp" in expression:
            field = expression.split("timestamp")[0].strip()
            if field in data.columns:
                try:
                    timestamps = pd.to_datetime(data[field])
                    now = pd.Timestamp.now()
                    max_age = float(re.search(r'(\d+)', expression).group(1))
                    mask = (now - timestamps).dt.total_seconds() <= max_age
                    passed = mask.all()
                    value = f"{(mask[~mask]).sum()} stale records"
                    expected = f"Age <= {max_age} seconds"
                    message = f"Stale records: {value}"
                except Exception as e:
                    passed = False
                    message = f"Timeliness check error: {str(e)}"
            else:
                passed = False
                message = f"Column {field} not found"
        
        return self._create_result(rule, passed, value, expected, message)

    def _create_result(
        self,
        rule: ValidationRule,
        passed: bool,
        value: Any,
        expected: Any,
        message: str
    ) -> ValidationResult:
        return ValidationResult(
            id=hashlib.md5(f"{rule.id}_{time.time()}".encode()).hexdigest(),
            rule_id=rule.id,
            passed=passed,
            value=value,
            expected=expected,
            message=message,
            level=rule.level,
            timestamp=time.time(),
            metadata=rule.metadata
        )

    async def get_rule(self, rule_id: str) -> Optional[ValidationRule]:
        return self._rules.get(rule_id)

    async def get_rules(self) -> List[ValidationRule]:
        return list(self._rules.values())

    async def get_result(self, result_id: str) -> Optional[ValidationResult]:
        return self._results.get(result_id)

    async def get_report(self, report_id: str) -> Optional[ValidationReport]:
        return self._reports.get(report_id)

    async def get_reports(self) -> List[ValidationReport]:
        return list(self._reports.values())

    async def enable_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
            return True
        return False

    async def disable_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
            return True
        return False

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
            "rules": len(self._rules),
            "results": len(self._results),
            "reports": len(self._reports),
            "validators": len(self._validators),
            "running": self._running
        }


__all__ = [
    "ValidationLevel",
    "ValidationType",
    "ValidationRule",
    "ValidationResult",
    "ValidationReport",
    "DataValidationManager"
]

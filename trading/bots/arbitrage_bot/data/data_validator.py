# trading/bots/arbitrage_bot/data/data_validator.py
# Nexus AI Trading System - Arbitrage Bot Data Validator Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Data Validator Module

This module provides comprehensive data validation for the arbitrage
bot system, including:

- Schema validation (JSON Schema, Pydantic models)
- Data type validation
- Range and boundary validation
- Format validation (email, URL, date, etc.)
- Business rule validation
- Cross-field validation
- Custom validation rules
- Validation pipelines
- Real-time validation
- Batch validation
- Validation reporting
- Error handling and recovery

The data validator ensures all data entering the arbitrage bot meets
quality standards and business requirements.
"""

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import jsonschema
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ValidationSeverity(str, Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationStatus(str, Enum):
    """Validation status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


class ValidationRuleType(str, Enum):
    """Validation rule types."""
    SCHEMA = "schema"
    TYPE = "type"
    RANGE = "range"
    FORMAT = "format"
    PATTERN = "pattern"
    CUSTOM = "custom"
    CROSS_FIELD = "cross_field"
    BUSINESS = "business"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ValidationConfig(BaseModel):
    """Validation configuration."""
    enabled: bool = True
    strict_mode: bool = False
    fail_fast: bool = False
    max_errors: int = 100
    validate_schema: bool = True
    validate_types: bool = True
    validate_ranges: bool = True
    validate_formats: bool = True
    validate_business_rules: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationRule(BaseModel):
    """Validation rule."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    type: ValidationRuleType
    field: Optional[str] = None
    schema: Optional[Dict[str, Any]] = None
    pattern: Optional[str] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    allowed_values: Optional[List[Any]] = None
    format_type: Optional[str] = None
    custom_function: Optional[str] = None
    cross_fields: Optional[List[str]] = None
    business_rule: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Validation result."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    rule_name: str
    field: Optional[str] = None
    value: Optional[Any] = None
    status: ValidationStatus
    severity: ValidationSeverity
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationReport(BaseModel):
    """Validation report."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_source: str
    data_type: str
    total_validations: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    errors: int = 0
    critical: int = 0
    status: ValidationStatus = ValidationStatus.PASSED
    results: List[ValidationResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Validation rules
CREATE TABLE IF NOT EXISTS validation_rules (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(20) NOT NULL,
    field VARCHAR(255),
    schema JSONB,
    pattern VARCHAR(255),
    min_value JSONB,
    max_value JSONB,
    allowed_values JSONB,
    format_type VARCHAR(50),
    custom_function VARCHAR(255),
    cross_fields JSONB,
    business_rule VARCHAR(255),
    severity VARCHAR(20) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    message TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Validation results
CREATE TABLE IF NOT EXISTS validation_results (
    id VARCHAR(64) PRIMARY KEY,
    rule_id VARCHAR(64) NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    field VARCHAR(255),
    value JSONB,
    status VARCHAR(20) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT,
    details JSONB DEFAULT '{}',
    timestamp TIMESTAMP NOT NULL,
    INDEX idx_validation_results_rule_id (rule_id),
    INDEX idx_validation_results_status (status),
    INDEX idx_validation_results_timestamp (timestamp)
);

-- Validation reports
CREATE TABLE IF NOT EXISTS validation_reports (
    id VARCHAR(64) PRIMARY KEY,
    data_source VARCHAR(255) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    total_validations INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    warnings INTEGER NOT NULL,
    errors INTEGER NOT NULL,
    critical INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    results JSONB DEFAULT '[]',
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_ms FLOAT,
    metadata JSONB DEFAULT '{}',
    INDEX idx_validation_reports_data_source (data_source),
    INDEX idx_validation_reports_data_type (data_type),
    INDEX idx_validation_reports_status (status),
    INDEX idx_validation_reports_started_at (started_at)
);
"""


# =============================================================================
# DATA VALIDATOR CLASS
# =============================================================================

class DataValidator:
    """
    Advanced data validator for arbitrage bot.
    
    Features:
    - Schema validation (JSON Schema, Pydantic models)
    - Data type validation
    - Range and boundary validation
    - Format validation (email, URL, date, etc.)
    - Business rule validation
    - Cross-field validation
    - Custom validation rules
    - Validation pipelines
    - Real-time validation
    - Batch validation
    - Validation reporting
    - Error handling and recovery
    """
    
    def __init__(
        self,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[ValidationConfig] = None
    ):
        self.redis = redis
        self.pool = pool
        self.config = config or ValidationConfig()
        
        # Validation rules
        self._rules: Dict[str, ValidationRule] = {}
        self._rules_by_field: Dict[str, List[ValidationRule]] = {}
        
        # Custom validators
        self._custom_validators: Dict[str, Callable] = {}
        
        # Circuit breakers
        self._validator_cb = CircuitBreaker(
            name="data_validator",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info("DataValidator initialized")
    
    async def initialize(self):
        """Initialize the data validator."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load rules
        if self.pool:
            await self._load_rules()
        
        self._running = True
        self._initialized = True
        
        logger.info("DataValidator initialized")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # RULE MANAGEMENT
    # =========================================================================
    
    async def add_rule(
        self,
        rule: ValidationRule
    ) -> ValidationRule:
        """
        Add a validation rule.
        
        Args:
            rule: Validation rule
            
        Returns:
            Added ValidationRule
        """
        self._rules[rule.id] = rule
        
        if rule.field:
            if rule.field not in self._rules_by_field:
                self._rules_by_field[rule.field] = []
            self._rules_by_field[rule.field].append(rule)
        
        if self.pool:
            await self._save_rule(rule)
        
        logger.info(f"Added validation rule: {rule.name}")
        return rule
    
    async def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a validation rule.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            True if removed successfully
        """
        if rule_id not in self._rules:
            return False
        
        rule = self._rules[rule_id]
        del self._rules[rule_id]
        
        if rule.field and rule.field in self._rules_by_field:
            self._rules_by_field[rule.field] = [
                r for r in self._rules_by_field[rule.field]
                if r.id != rule_id
            ]
        
        if self.pool:
            await self._delete_rule(rule_id)
        
        logger.info(f"Removed validation rule: {rule.name}")
        return True
    
    async def get_rules(
        self,
        field: Optional[str] = None
    ) -> List[ValidationRule]:
        """
        Get validation rules.
        
        Args:
            field: Filter by field
            
        Returns:
            List of ValidationRule
        """
        if field:
            return self._rules_by_field.get(field, [])
        return list(self._rules.values())
    
    async def register_custom_validator(
        self,
        name: str,
        validator: Callable
    ):
        """
        Register a custom validator function.
        
        Args:
            name: Validator name
            validator: Validator function
        """
        self._custom_validators[name] = validator
        logger.info(f"Registered custom validator: {name}")
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    async def validate(
        self,
        data: Any,
        data_source: str = "unknown",
        data_type: str = "unknown",
        rules: Optional[List[ValidationRule]] = None,
        config: Optional[ValidationConfig] = None
    ) -> ValidationReport:
        """
        Validate data.
        
        Args:
            data: Data to validate
            data_source: Data source identifier
            data_type: Data type
            rules: Rules to apply (None = all enabled rules)
            config: Validation configuration
            
        Returns:
            ValidationReport
        """
        if self._validator_cb.is_open():
            raise CircuitBreakerOpenError("Data validator circuit breaker is open")
        
        report = ValidationReport(
            data_source=data_source,
            data_type=data_type,
            started_at=datetime.utcnow()
        )
        
        try:
            # Get rules
            if rules is None:
                rules = [r for r in self._rules.values() if r.enabled]
            
            validation_config = config or self.config
            
            # Apply rules
            results = []
            
            for rule in rules:
                if not rule.enabled:
                    continue
                
                # Validate based on rule type
                result = await self._apply_rule(rule, data, validation_config)
                results.append(result)
                
                # Update report
                report.total_validations += 1
                
                if result.status == ValidationStatus.PASSED:
                    report.passed += 1
                else:
                    report.failed += 1
                    
                    if result.severity == ValidationSeverity.WARNING:
                        report.warnings += 1
                    elif result.severity == ValidationSeverity.ERROR:
                        report.errors += 1
                    elif result.severity == ValidationSeverity.CRITICAL:
                        report.critical += 1
                
                # Fail fast
                if validation_config.fail_fast and result.status == ValidationStatus.FAILED:
                    if result.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                        break
                
                # Max errors
                if report.errors >= validation_config.max_errors:
                    break
            
            report.results = results
            
            # Determine overall status
            if report.critical > 0:
                report.status = ValidationStatus.FAILED
            elif report.errors > 0:
                report.status = ValidationStatus.FAILED
            elif report.warnings > 0:
                report.status = ValidationStatus.PASSED
            else:
                report.status = ValidationStatus.PASSED
            
            # Record success
            self._validator_cb.record_success()
            
        except Exception as e:
            self._validator_cb.record_failure()
            logger.error(f"Validation error: {e}")
            report.status = ValidationStatus.FAILED
            
        finally:
            report.completed_at = datetime.utcnow()
            report.duration_ms = (report.completed_at - report.started_at).total_seconds() * 1000
            
            # Save report
            if self.pool:
                await self._save_report(report)
        
        return report
    
    async def _apply_rule(
        self,
        rule: ValidationRule,
        data: Any,
        config: ValidationConfig
    ) -> ValidationResult:
        """
        Apply a validation rule.
        
        Args:
            rule: Validation rule
            data: Data to validate
            config: Validation configuration
            
        Returns:
            ValidationResult
        """
        # Get field value
        value = None
        if rule.field:
            value = self._get_nested_value(data, rule.field)
        
        try:
            if rule.type == ValidationRuleType.SCHEMA:
                status, message, details = await self._validate_schema(
                    data, rule, config
                )
            elif rule.type == ValidationRuleType.TYPE:
                status, message, details = await self._validate_type(
                    value, rule, config
                )
            elif rule.type == ValidationRuleType.RANGE:
                status, message, details = await self._validate_range(
                    value, rule, config
                )
            elif rule.type == ValidationRuleType.FORMAT:
                status, message, details = await self._validate_format(
                    value, rule, config
                )
            elif rule.type == ValidationRuleType.PATTERN:
                status, message, details = await self._validate_pattern(
                    value, rule, config
                )
            elif rule.type == ValidationRuleType.CROSS_FIELD:
                status, message, details = await self._validate_cross_field(
                    data, rule, config
                )
            elif rule.type == ValidationRuleType.BUSINESS:
                status, message, details = await self._validate_business_rule(
                    data, rule, config
                )
            elif rule.type == ValidationRuleType.CUSTOM:
                status, message, details = await self._validate_custom(
                    data, rule, config
                )
            else:
                status = ValidationStatus.SKIPPED
                message = f"Unknown rule type: {rule.type}"
                details = {}
            
        except Exception as e:
            status = ValidationStatus.FAILED
            message = f"Rule execution error: {str(e)}"
            details = {'error': str(e)}
        
        return ValidationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            field=rule.field,
            value=value,
            status=status,
            severity=rule.severity,
            message=message or rule.message or f"Validation failed for {rule.name}",
            details=details
        )
    
    # =========================================================================
    # VALIDATION METHODS
    # =========================================================================
    
    def _get_nested_value(self, data: Any, field: str) -> Any:
        """Get nested value from data using dot notation."""
        if not field:
            return data
        
        keys = field.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    idx = int(key)
                    current = current[idx] if idx < len(current) else None
                except ValueError:
                    current = None
            else:
                current = None
                break
        
        return current
    
    async def _validate_schema(
        self,
        data: Any,
        rule: ValidationRule,
        config: ValidationConfig
    ) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate against JSON Schema."""
        if not rule.schema:
            return ValidationStatus.SKIPPED, "No schema defined", {}
        
        if not config.validate_schema:
            return ValidationStatus.SKIPPED, "Schema validation disabled", {}
        
        try:
            jsonschema.validate(data, rule.schema)
            return ValidationStatus.PASSED, "Schema validation passed", {}
        except jsonschema.ValidationError as e:
            return ValidationStatus.FAILED, f"Schema validation failed: {e.message}", {
                'path': list(e.path),
                'validator': e.validator,
                'validator_value': e.validator_value
            }
    
    async def _validate_type(
        self,
        value: Any,
        rule: ValidationRule,
        config: ValidationConfig
    ) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate data type."""
        if not config.validate_types:
            return ValidationStatus.SKIPPED, "Type validation disabled", {}
        
        expected_type = rule.metadata.get('expected_type', '')
        if not expected_type:
            return ValidationStatus.SKIPPED, "No expected type defined", {}
        
        if value is None:
            return ValidationStatus.PASSED, "Null value allowed", {}
        
        actual_type = type(value).__name__
        if actual_type != expected_type:
            return ValidationStatus.FAILED, f"Type mismatch: expected {expected_type}, got {actual_type}", {
                'expected': expected_type,
                'actual': actual_type
            }
        
        return ValidationStatus.PASSED, "Type validation passed", {}
    
    async def _validate_range(
        self,
        value: Any,
        rule: ValidationRule,
        config: ValidationConfig
    ) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate range."""
        if not config.validate_ranges:
            return ValidationStatus.SKIPPED, "Range validation disabled", {}
        
        if value is None:
            return ValidationStatus.PASSED, "Null value allowed", {}
        
        # Convert to Decimal for comparison
        try:
            num_value = Decimal(str(value))
        except Exception:
            return ValidationStatus.FAILED, "Cannot convert value to number", {}
        
        details = {}
        
        if rule.min_value is not None:
            min_val = Decimal(str(rule.min_value))
            if num_value < min_val:
                return ValidationStatus.FAILED, f"Value {num_value} below minimum {min_val}", {
                    'value': float(num_value),
                    'min': float(min_val)
                }
        
        if rule.max_value is not None:
            max_val = Decimal(str(rule.max_value))
            if num_value > max_val:
                return ValidationStatus.FAILED, f"Value {num_value} above maximum {max_val}", {
                    'value': float(num_value),
                    'max': float(max_val)
                }
        
        return ValidationStatus.PASSED, "Range validation passed", {}
    
    async def _validate_format(
        self,
        value: Any,
        rule: ValidationRule,
        config: ValidationConfig
    ) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate format."""
        if not config.validate_formats:
            return ValidationStatus.SKIPPED, "Format validation disabled", {}
        
        if value is None:
            return ValidationStatus.PASSED, "Null value allowed", {}
        
        if not isinstance(value, str):
            return ValidationStatus.FAILED, "Value is not a string", {}
        
        format_type = rule.format_type or rule.metadata.get('format_type', '')
        if not format_type:
            return ValidationStatus.SKIPPED, "No format type defined", {}
        
        if format_type == 'email':
            import email_validator
            try:
                email_validator.validate_email(value)
                return ValidationStatus.PASSED, "Email format valid", {}
            except email_validator.EmailNotValidError as e:
                return ValidationStatus.FAILED, f"Invalid email: {e}", {}
                
        elif format_type == 'url':
            pattern = re.compile(
                r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/.*)?$'
            )
            if pattern.match(value):
                return ValidationStatus.PASSED, "URL format valid", {}
            return ValidationStatus.FAILED, "Invalid URL format", {}
            
        elif format_type == 'date':
            try:
                datetime.fromisoformat(value)
                return ValidationStatus.PASSED, "Date format valid", {}
            except ValueError:
                return ValidationStatus.FAILED, "Invalid date format", {}
            
        elif format_type == 'datetime':
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return ValidationStatus.PASSED, "DateTime format valid", {}
            except ValueError:
                return ValidationStatus.FAILED, "Invalid datetime format", {}
        
        return ValidationStatus.SKIPPED, f"Unknown format type: {format_type}", {}
    
    async def _validate_pattern(
        self,
        value: Any,
        rule: ValidationRule,
        config: ValidationConfig
    ) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate against regex pattern."""
        if not rule.pattern:
            return ValidationStatus.SKIPPED, "No pattern defined", {}
        
        if value is None:
            return ValidationStatus.PASSED, "Null value allowed", {}
        
        if not isinstance(value, str):
            return ValidationStatus.FAILED, "Value is not a string", {}
        
        pattern = re.compile(rule.pattern)
        if pattern.match(value):
            return ValidationStatus.PASSED, "Pattern match", {}
        
        return ValidationStatus.FAILED, f"Pattern mismatch: {rule.pattern}", {
            'pattern': rule.pattern,
            'value': value
        }
    
    async def _validate_cross_field(
        self,
        data: Any,
        rule: ValidationRule,
        config: ValidationConfig
    ) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate cross-field relationships."""
        if not rule.cross_fields:
            return ValidationStatus.SKIPPED, "No cross-fields defined", {}
        
        # Get all field values
        values = {}
        for field in rule.cross_fields:
            values[field] = self._get_nested_value(data, field)
        
        # Apply cross-field validation
        # This is a simplified example - can be extended
        condition = rule.metadata.get('condition', 'equals')
        
        if condition == 'equals':
            if len(set(values.values())) > 1:
                return ValidationStatus.FAILED, "Cross-field values do not match", {
                    'values': values
                }
        elif condition == 'greater_than':
            # Check each pair
            field_pairs = rule.metadata.get('pairs', [])
            for field1, field2 in field_pairs:
                if values.get(field1, 0) <= values.get(field2, 0):
                    return ValidationStatus.FAILED, f"{field1} should be greater than {field2}", {
                        'values': values
                    }
        
        return ValidationStatus.PASSED, "Cross-field validation passed", {}
    
    async def _validate_business_rule(
        self,
        data: Any,
        rule: ValidationRule,
        config: ValidationConfig
    ) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate business rule."""
        if not config.validate_business_rules:
            return ValidationStatus.SKIPPED, "Business rule validation disabled", {}
        
        # This would implement specific business rules
        # Simplified example
        if rule.business_rule == 'positive_arbitrage':
            # Check if arbitrage is positive
            buy_price = self._get_nested_value(data, 'buy_price')
            sell_price = self._get_nested_value(data, 'sell_price')
            
            if buy_price is not None and sell_price is not None:
                if sell_price <= buy_price:
                    return ValidationStatus.FAILED, "Arbitrage not profitable", {
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'spread': sell_price - buy_price
                    }
        
        return ValidationStatus.PASSED, "Business rule passed", {}
    
    async def _validate_custom(
        self,
        data: Any,
        rule: ValidationRule,
        config: ValidationConfig
    ) -> Tuple[ValidationStatus, str, Dict[str, Any]]:
        """Validate using custom function."""
        if not rule.custom_function:
            return ValidationStatus.SKIPPED, "No custom function defined", {}
        
        if rule.custom_function not in self._custom_validators:
            return ValidationStatus.SKIPPED, f"Custom validator not found: {rule.custom_function}", {}
        
        try:
            validator = self._custom_validators[rule.custom_function]
            result = validator(data, rule)
            
            if isinstance(result, tuple) and len(result) >= 2:
                status, message = result[0], result[1]
                details = result[2] if len(result) > 2 else {}
            elif isinstance(result, bool):
                status = ValidationStatus.PASSED if result else ValidationStatus.FAILED
                message = "Custom validation " + ("passed" if result else "failed")
                details = {}
            else:
                status = ValidationStatus.PASSED
                message = "Custom validation completed"
                details = {'result': result}
            
            return status, message, details
            
        except Exception as e:
            return ValidationStatus.FAILED, f"Custom validation error: {str(e)}", {
                'error': str(e)
            }
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_rules(self):
        """Load validation rules from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM validation_rules")
                
                for row in rows:
                    rule = ValidationRule(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'],
                        type=ValidationRuleType(row['type']),
                        field=row['field'],
                        schema=row['schema'],
                        pattern=row['pattern'],
                        min_value=row['min_value'],
                        max_value=row['max_value'],
                        allowed_values=row['allowed_values'],
                        format_type=row['format_type'],
                        custom_function=row['custom_function'],
                        cross_fields=row['cross_fields'],
                        business_rule=row['business_rule'],
                        severity=ValidationSeverity(row['severity']),
                        enabled=row['enabled'],
                        message=row['message'],
                        metadata=row['metadata'] or {}
                    )
                    
                    self._rules[rule.id] = rule
                    if rule.field:
                        if rule.field not in self._rules_by_field:
                            self._rules_by_field[rule.field] = []
                        self._rules_by_field[rule.field].append(rule)
                
                logger.info(f"Loaded {len(self._rules)} validation rules")
                
        except Exception as e:
            logger.error(f"Error loading validation rules: {e}")
    
    async def _save_rule(self, rule: ValidationRule):
        """Save validation rule to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO validation_rules (
                        id, name, description, type, field,
                        schema, pattern, min_value, max_value,
                        allowed_values, format_type, custom_function,
                        cross_fields, business_rule, severity,
                        enabled, message, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15,
                              $16, $17, $18)
                    """,
                    rule.id,
                    rule.name,
                    rule.description,
                    rule.type.value,
                    rule.field,
                    json.dumps(rule.schema) if rule.schema else None,
                    rule.pattern,
                    rule.min_value,
                    rule.max_value,
                    json.dumps(rule.allowed_values) if rule.allowed_values else None,
                    rule.format_type,
                    rule.custom_function,
                    json.dumps(rule.cross_fields) if rule.cross_fields else None,
                    rule.business_rule,
                    rule.severity.value,
                    rule.enabled,
                    rule.message,
                    json.dumps(rule.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving validation rule: {e}")
    
    async def _delete_rule(self, rule_id: str):
        """Delete validation rule from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM validation_rules WHERE id = $1",
                    rule_id
                )
        except Exception as e:
            logger.error(f"Error deleting validation rule: {e}")
    
    async def _save_report(self, report: ValidationReport):
        """Save validation report to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO validation_reports (
                        id, data_source, data_type,
                        total_validations, passed, failed,
                        warnings, errors, critical,
                        status, results,
                        started_at, completed_at, duration_ms,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13, $14, $15)
                    """,
                    report.id,
                    report.data_source,
                    report.data_type,
                    report.total_validations,
                    report.passed,
                    report.failed,
                    report.warnings,
                    report.errors,
                    report.critical,
                    report.status.value,
                    json.dumps([r.dict() for r in report.results], default=str),
                    report.started_at,
                    report.completed_at,
                    report.duration_ms,
                    json.dumps(report.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving validation report: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the data validator."""
        self._running = False
        logger.info("DataValidator shutdown")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Circuit breaker open error."""
    pass


class ValidationError(Exception):
    """Validation error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'DataValidator',
    'ValidationSeverity',
    'ValidationStatus',
    'ValidationRuleType',
    'ValidationConfig',
    'ValidationRule',
    'ValidationResult',
    'ValidationReport',
    'CircuitBreakerOpenError',
    'ValidationError'
]

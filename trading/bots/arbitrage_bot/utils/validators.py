"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Validators Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de validation pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import re
import json
import uuid
import ipaddress
import email_validator
import phonenumbers
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Callable,
    TypeVar,
    Generic,
    Iterator,
    Set,
    FrozenSet
)
from enum import Enum
from datetime import datetime, date, time
from decimal import Decimal
import hashlib
import base64
import urllib.parse
import xml.etree.ElementTree as ET

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')

# ============================================================
# ENUMS
# ============================================================

class ValidationSeverity(Enum):
    """Sévérités de validation"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ValidationRuleType(Enum):
    """Types de règles de validation"""
    REQUIRED = "required"
    TYPE = "type"
    LENGTH = "length"
    RANGE = "range"
    PATTERN = "pattern"
    CUSTOM = "custom"
    COMPARISON = "comparison"
    UNIQUE = "unique"
    EXISTENCE = "existence"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ValidationResult:
    """Résultat de validation"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, message: str):
        """Ajoute une erreur"""
        self.errors.append(message)
        self.valid = False
    
    def add_warning(self, message: str):
        """Ajoute un avertissement"""
        self.warnings.append(message)
    
    def add_info(self, message: str):
        """Ajoute une information"""
        self.info.append(message)

@dataclass
class ValidationRule:
    """Règle de validation"""
    type: ValidationRuleType
    field: str
    value: Any = None
    message: str = ""
    severity: ValidationSeverity = ValidationSeverity.ERROR
    condition: Optional[Callable[[Any], bool]] = None
    custom_validator: Optional[Callable[[Any], Tuple[bool, str]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# BASE VALIDATOR
# ============================================================

class BaseValidator:
    """
    Validateur de base
    
    Fournit des méthodes de validation communes
    """
    
    @staticmethod
    def validate_required(value: Any, field_name: str = "field") -> ValidationResult:
        """
        Valide qu'une valeur est présente
        
        Args:
            value: Valeur à valider
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(f"{field_name} is required")
        
        return result
    
    @staticmethod
    def validate_type(
        value: Any,
        expected_type: type,
        field_name: str = "field"
    ) -> ValidationResult:
        """
        Valide le type d'une valeur
        
        Args:
            value: Valeur à valider
            expected_type: Type attendu
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if not isinstance(value, expected_type):
            result.add_error(
                f"{field_name} must be of type {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
        
        return result
    
    @staticmethod
    def validate_length(
        value: Union[str, List, Dict, Any],
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        field_name: str = "field"
    ) -> ValidationResult:
        """
        Valide la longueur d'une valeur
        
        Args:
            value: Valeur à valider
            min_length: Longueur minimale
            max_length: Longueur maximale
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        length = len(value) if hasattr(value, '__len__') else 0
        
        if min_length is not None and length < min_length:
            result.add_error(
                f"{field_name} length must be at least {min_length}, got {length}"
            )
        
        if max_length is not None and length > max_length:
            result.add_error(
                f"{field_name} length must be at most {max_length}, got {length}"
            )
        
        return result
    
    @staticmethod
    def validate_range(
        value: Union[int, float, Decimal],
        min_value: Optional[Union[int, float, Decimal]] = None,
        max_value: Optional[Union[int, float, Decimal]] = None,
        field_name: str = "field"
    ) -> ValidationResult:
        """
        Valide la plage d'une valeur numérique
        
        Args:
            value: Valeur à valider
            min_value: Valeur minimale
            max_value: Valeur maximale
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            num_value = float(value)
        except (ValueError, TypeError):
            result.add_error(f"{field_name} must be a number")
            return result
        
        if min_value is not None and num_value < float(min_value):
            result.add_error(
                f"{field_name} must be at least {min_value}, got {num_value}"
            )
        
        if max_value is not None and num_value > float(max_value):
            result.add_error(
                f"{field_name} must be at most {max_value}, got {num_value}"
            )
        
        return result
    
    @staticmethod
    def validate_pattern(
        value: str,
        pattern: str,
        field_name: str = "field"
    ) -> ValidationResult:
        """
        Valide une valeur par rapport à un motif regex
        
        Args:
            value: Valeur à valider
            pattern: Motif regex
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if not re.match(pattern, value):
            result.add_error(
                f"{field_name} does not match required pattern: {pattern}"
            )
        
        return result
    
    @staticmethod
    def validate_email(email: str, field_name: str = "email") -> ValidationResult:
        """
        Valide une adresse email
        
        Args:
            email: Email à valider
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            email_validator.validate_email(email)
        except email_validator.EmailNotValidError as e:
            result.add_error(f"{field_name} is invalid: {e}")
        
        return result
    
    @staticmethod
    def validate_phone(
        phone: str,
        country: str = "US",
        field_name: str = "phone"
    ) -> ValidationResult:
        """
        Valide un numéro de téléphone
        
        Args:
            phone: Téléphone à valider
            country: Code pays
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            parsed = phonenumbers.parse(phone, country)
            if not phonenumbers.is_valid_number(parsed):
                result.add_error(f"{field_name} is invalid")
        except phonenumbers.NumberParseException as e:
            result.add_error(f"{field_name} is invalid: {e}")
        
        return result
    
    @staticmethod
    def validate_url(url: str, field_name: str = "url") -> ValidationResult:
        """
        Valide une URL
        
        Args:
            url: URL à valider
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            parsed = urllib.parse.urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                result.add_error(f"{field_name} is invalid")
        except Exception:
            result.add_error(f"{field_name} is invalid")
        
        return result
    
    @staticmethod
    def validate_uuid(uuid_str: str, field_name: str = "uuid") -> ValidationResult:
        """
        Valide un UUID
        
        Args:
            uuid_str: UUID à valider
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            uuid.UUID(uuid_str)
        except ValueError:
            result.add_error(f"{field_name} is not a valid UUID")
        
        return result
    
    @staticmethod
    def validate_ip(
        ip_str: str,
        version: Optional[int] = None,
        field_name: str = "ip"
    ) -> ValidationResult:
        """
        Valide une adresse IP
        
        Args:
            ip_str: IP à valider
            version: Version IP (4 ou 6)
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            ip = ipaddress.ip_address(ip_str)
            if version is not None:
                if version == 4 and ip.version != 4:
                    result.add_error(f"{field_name} must be IPv4")
                elif version == 6 and ip.version != 6:
                    result.add_error(f"{field_name} must be IPv6")
        except ValueError:
            result.add_error(f"{field_name} is not a valid IP address")
        
        return result
    
    @staticmethod
    def validate_date(
        date_str: str,
        format_str: str = "%Y-%m-%d",
        field_name: str = "date"
    ) -> ValidationResult:
        """
        Valide une date
        
        Args:
            date_str: Date à valider
            format_str: Format de date
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            datetime.strptime(date_str, format_str)
        except ValueError:
            result.add_error(
                f"{field_name} must be in format {format_str}"
            )
        
        return result
    
    @staticmethod
    def validate_datetime(
        datetime_str: str,
        field_name: str = "datetime"
    ) -> ValidationResult:
        """
        Valide une date/heure ISO
        
        Args:
            datetime_str: Date/heure à valider
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            datetime.fromisoformat(datetime_str)
        except ValueError:
            result.add_error(
                f"{field_name} must be a valid ISO datetime"
            )
        
        return result
    
    @staticmethod
    def validate_json(json_str: str, field_name: str = "json") -> ValidationResult:
        """
        Valide du JSON
        
        Args:
            json_str: JSON à valider
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            result.add_error(f"{field_name} is not valid JSON: {e}")
        
        return result
    
    @staticmethod
    def validate_base64(
        base64_str: str,
        field_name: str = "base64"
    ) -> ValidationResult:
        """
        Valide du base64
        
        Args:
            base64_str: Base64 à valider
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        try:
            base64.b64decode(base64_str, validate=True)
        except Exception:
            result.add_error(f"{field_name} is not valid base64")
        
        return result
    
    @staticmethod
    def validate_hex(hex_str: str, field_name: str = "hex") -> ValidationResult:
        """
        Valide une chaîne hexadécimale
        
        Args:
            hex_str: Hex à valider
            field_name: Nom du champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if not all(c in "0123456789abcdefABCDEF" for c in hex_str):
            result.add_error(f"{field_name} is not a valid hex string")
        
        return result

# ============================================================
# COMPARISON VALIDATORS
# ============================================================

class ComparisonValidator:
    """Validateur de comparaisons"""
    
    @staticmethod
    def validate_equal(
        value1: Any,
        value2: Any,
        field1: str = "field1",
        field2: str = "field2"
    ) -> ValidationResult:
        """
        Valide que deux valeurs sont égales
        
        Args:
            value1: Première valeur
            value2: Deuxième valeur
            field1: Nom du premier champ
            field2: Nom du deuxième champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if value1 != value2:
            result.add_error(f"{field1} must equal {field2}")
        
        return result
    
    @staticmethod
    def validate_not_equal(
        value1: Any,
        value2: Any,
        field1: str = "field1",
        field2: str = "field2"
    ) -> ValidationResult:
        """
        Valide que deux valeurs ne sont pas égales
        
        Args:
            value1: Première valeur
            value2: Deuxième valeur
            field1: Nom du premier champ
            field2: Nom du deuxième champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if value1 == value2:
            result.add_error(f"{field1} must not equal {field2}")
        
        return result
    
    @staticmethod
    def validate_greater(
        value1: Union[int, float],
        value2: Union[int, float],
        field1: str = "field1",
        field2: str = "field2"
    ) -> ValidationResult:
        """
        Valide que la première valeur est supérieure à la deuxième
        
        Args:
            value1: Première valeur
            value2: Deuxième valeur
            field1: Nom du premier champ
            field2: Nom du deuxième champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if value1 <= value2:
            result.add_error(f"{field1} must be greater than {field2}")
        
        return result
    
    @staticmethod
    def validate_greater_equal(
        value1: Union[int, float],
        value2: Union[int, float],
        field1: str = "field1",
        field2: str = "field2"
    ) -> ValidationResult:
        """
        Valide que la première valeur est supérieure ou égale à la deuxième
        
        Args:
            value1: Première valeur
            value2: Deuxième valeur
            field1: Nom du premier champ
            field2: Nom du deuxième champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if value1 < value2:
            result.add_error(f"{field1} must be greater than or equal to {field2}")
        
        return result
    
    @staticmethod
    def validate_less(
        value1: Union[int, float],
        value2: Union[int, float],
        field1: str = "field1",
        field2: str = "field2"
    ) -> ValidationResult:
        """
        Valide que la première valeur est inférieure à la deuxième
        
        Args:
            value1: Première valeur
            value2: Deuxième valeur
            field1: Nom du premier champ
            field2: Nom du deuxième champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if value1 >= value2:
            result.add_error(f"{field1} must be less than {field2}")
        
        return result
    
    @staticmethod
    def validate_less_equal(
        value1: Union[int, float],
        value2: Union[int, float],
        field1: str = "field1",
        field2: str = "field2"
    ) -> ValidationResult:
        """
        Valide que la première valeur est inférieure ou égale à la deuxième
        
        Args:
            value1: Première valeur
            value2: Deuxième valeur
            field1: Nom du premier champ
            field2: Nom du deuxième champ
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        if value1 > value2:
            result.add_error(f"{field1} must be less than or equal to {field2}")
        
        return result

# ============================================================
# CONDITIONAL VALIDATORS
# ============================================================

class ConditionalValidator:
    """Validateur conditionnel"""
    
    @staticmethod
    def validate_if(
        condition: Callable[[Dict[str, Any]], bool],
        validator: Callable[[Any], ValidationResult],
        field: str,
        data: Dict[str, Any]
    ) -> ValidationResult:
        """
        Valide une condition
        
        Args:
            condition: Fonction de condition
            validator: Validateur à exécuter si la condition est vraie
            field: Champ à valider
            data: Données complètes
            
        Returns:
            ValidationResult: Résultat de validation
        """
        if condition(data):
            return validator(data.get(field))
        
        return ValidationResult(valid=True)
    
    @staticmethod
    def validate_required_if(
        field: str,
        condition_field: str,
        condition_value: Any,
        data: Dict[str, Any]
    ) -> ValidationResult:
        """
        Valide qu'un champ est requis si une condition est remplie
        
        Args:
            field: Champ à valider
            condition_field: Champ de condition
            condition_value: Valeur de condition
            data: Données complètes
            
        Returns:
            ValidationResult: Résultat de validation
        """
        if data.get(condition_field) == condition_value:
            return BaseValidator.validate_required(data.get(field), field)
        
        return ValidationResult(valid=True)

# ============================================================
# SCHEMA VALIDATOR
# ============================================================

class SchemaValidator:
    """
    Validateur de schéma
    
    Valide des données selon un schéma défini
    """
    
    def __init__(self):
        self._rules: Dict[str, List[ValidationRule]] = {}
        self._validators: Dict[str, Callable] = {}
    
    def add_rule(self, rule: ValidationRule):
        """
        Ajoute une règle de validation
        
        Args:
            rule: Règle à ajouter
        """
        if rule.field not in self._rules:
            self._rules[rule.field] = []
        self._rules[rule.field].append(rule)
    
    def add_validator(self, field: str, validator: Callable[[Any], ValidationResult]):
        """
        Ajoute un validateur personnalisé
        
        Args:
            field: Champ à valider
            validator: Validateur personnalisé
        """
        self._validators[field] = validator
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Valide des données selon le schéma
        
        Args:
            data: Données à valider
            
        Returns:
            ValidationResult: Résultat de validation
        """
        result = ValidationResult(valid=True)
        
        # Valider les règles
        for field, rules in self._rules.items():
            value = data.get(field)
            
            for rule in rules:
                if rule.type == ValidationRuleType.REQUIRED:
                    field_result = BaseValidator.validate_required(value, field)
                    result.errors.extend(field_result.errors)
                    if not field_result.valid:
                        result.valid = False
                
                elif rule.type == ValidationRuleType.TYPE:
                    field_result = BaseValidator.validate_type(
                        value, rule.value, field
                    )
                    result.errors.extend(field_result.errors)
                    if not field_result.valid:
                        result.valid = False
                
                elif rule.type == ValidationRuleType.LENGTH:
                    field_result = BaseValidator.validate_length(
                        value,
                        rule.metadata.get('min_length'),
                        rule.metadata.get('max_length'),
                        field
                    )
                    result.errors.extend(field_result.errors)
                    if not field_result.valid:
                        result.valid = False
                
                elif rule.type == ValidationRuleType.RANGE:
                    field_result = BaseValidator.validate_range(
                        value,
                        rule.metadata.get('min_value'),
                        rule.metadata.get('max_value'),
                        field
                    )
                    result.errors.extend(field_result.errors)
                    if not field_result.valid:
                        result.valid = False
                
                elif rule.type == ValidationRuleType.PATTERN:
                    field_result = BaseValidator.validate_pattern(
                        value, rule.value, field
                    )
                    result.errors.extend(field_result.errors)
                    if not field_result.valid:
                        result.valid = False
                
                elif rule.type == ValidationRuleType.CUSTOM:
                    if rule.custom_validator:
                        field_result = rule.custom_validator(value)
                        result.errors.extend(field_result.errors)
                        if not field_result.valid:
                            result.valid = False
        
        # Valider les validateurs personnalisés
        for field, validator in self._validators.items():
            field_result = validator(data.get(field))
            result.errors.extend(field_result.errors)
            if not field_result.valid:
                result.valid = False
        
        return result

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'ValidationSeverity',
    'ValidationRuleType',
    
    # Data Classes
    'ValidationResult',
    'ValidationRule',
    
    # Classes
    'BaseValidator',
    'ComparisonValidator',
    'ConditionalValidator',
    'SchemaValidator',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Validators utilities module initialized")

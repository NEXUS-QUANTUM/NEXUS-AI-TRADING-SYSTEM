"""
NEXUS AI TRADING SYSTEM - HEDGE BOT VALIDATORS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de validation pour le Hedge Bot.
Support des validateurs de données, schémas, règles métier, et plus.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union
from uuid import UUID

import jsonschema
import pandas as pd
from pydantic import BaseModel, ValidationError, validator
from cerberus import Validator as CerberusValidator

from ..utils.helpers import safe_decimal, safe_float, safe_int

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class ValidationLevel(Enum):
    """Niveaux de validation."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class ValidationType(Enum):
    """Types de validation."""
    REQUIRED = "required"
    TYPE = "type"
    LENGTH = "length"
    RANGE = "range"
    PATTERN = "pattern"
    CUSTOM = "custom"
    CONDITIONAL = "conditional"
    DEPENDENCY = "dependency"
    UNIQUE = "unique"
    EXISTENCE = "existence"
    BUSINESS = "business"


@dataclass
class ValidationResult:
    """Résultat de validation."""
    valid: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    info: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "metadata": self.metadata
        }


@dataclass
class ValidationRule:
    """Règle de validation."""
    name: str
    field: str
    rule_type: ValidationType
    validator: Callable
    message: str
    level: ValidationLevel = ValidationLevel.ERROR
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# CLASSE VALIDATOR
# ============================================================================

class Validator:
    """
    Validateur de données avancé.
    """

    # Types supportés
    SUPPORTED_TYPES = {
        "string": str,
        "int": int,
        "float": float,
        "decimal": Decimal,
        "bool": bool,
        "list": list,
        "dict": dict,
        "datetime": datetime,
        "uuid": UUID,
        "any": Any
    }

    def __init__(
        self,
        strict_mode: bool = True,
        raise_on_error: bool = False,
        max_errors: int = 100
    ):
        """
        Initialise le validateur.

        Args:
            strict_mode: Mode strict
            raise_on_error: Lever une exception en cas d'erreur
            max_errors: Nombre maximum d'erreurs
        """
        self.strict_mode = strict_mode
        self.raise_on_error = raise_on_error
        self.max_errors = max_errors
        
        # Règles
        self._rules: Dict[str, List[ValidationRule]] = {}
        self._global_rules: List[ValidationRule] = []
        self._validators: Dict[str, Callable] = {}
        
        # Résultats
        self._results: Dict[str, ValidationResult] = {}
        
        # Métriques
        self._metrics = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "by_type": {},
            "last_validation": None
        }

        # Initialisation des validateurs par défaut
        self._init_default_validators()

        logger.info("Validator initialisé avec succès")

    def _init_default_validators(self) -> None:
        """Initialise les validateurs par défaut."""
        # Validateurs de base
        self.register_validator("required", self._validate_required)
        self.register_validator("type", self._validate_type)
        self.register_validator("length", self._validate_length)
        self.register_validator("range", self._validate_range)
        self.register_validator("pattern", self._validate_pattern)
        self.register_validator("email", self._validate_email)
        self.register_validator("url", self._validate_url)
        self.register_validator("uuid", self._validate_uuid)
        self.register_validator("ip", self._validate_ip)
        self.register_validator("phone", self._validate_phone)
        self.register_validator("credit_card", self._validate_credit_card)

    # ========================================================================
    # ENREGISTREMENT DES VALIDATEURS
    # ========================================================================

    def register_validator(
        self,
        name: str,
        validator: Callable
    ) -> None:
        """
        Enregistre un validateur.

        Args:
            name: Nom du validateur
            validator: Fonction de validation
        """
        self._validators[name] = validator
        logger.debug(f"Validateur {name} enregistré")

    def register_rule(
        self,
        field: str,
        rule: ValidationRule
    ) -> None:
        """
        Enregistre une règle de validation.

        Args:
            field: Champ
            rule: Règle de validation
        """
        if field not in self._rules:
            self._rules[field] = []
        self._rules[field].append(rule)
        logger.debug(f"Règle {rule.name} enregistrée pour {field}")

    def register_schema(
        self,
        schema: Dict[str, Any]
    ) -> None:
        """
        Enregistre un schéma de validation.

        Args:
            schema: Schéma au format Cerberus
        """
        for field, rules in schema.items():
            for rule_name, rule_config in rules.items():
                validator = self._validators.get(rule_name)
                if validator:
                    rule = ValidationRule(
                        name=rule_name,
                        field=field,
                        rule_type=ValidationType.CUSTOM,
                        validator=validator,
                        message=rule_config.get("message", f"Validation de {rule_name} échouée"),
                        params=rule_config.get("params", {})
                    )
                    self.register_rule(field, rule)

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def validate(
        self,
        data: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Valide des données.

        Args:
            data: Données à valider
            schema: Schéma de validation (optionnel)
            context: Contexte

        Returns:
            Résultat de validation
        """
        self._metrics["total_validations"] += 1
        self._metrics["last_validation"] = datetime.now().isoformat()

        errors = []
        warnings = []
        infos = []

        # Validation du schéma si fourni
        if schema:
            result = self._validate_schema(data, schema)
            errors.extend(result["errors"])
            warnings.extend(result["warnings"])
            infos.extend(result["info"])

        # Validation des règles enregistrées
        for field, rules in self._rules.items():
            value = data.get(field)
            
            for rule in rules:
                if not rule.enabled:
                    continue
                
                try:
                    valid = rule.validator(value, **rule.params)
                    if not valid:
                        error = {
                            "field": field,
                            "rule": rule.name,
                            "message": rule.message,
                            "value": value,
                            "params": rule.params
                        }
                        
                        if rule.level == ValidationLevel.ERROR:
                            errors.append(error)
                        elif rule.level == ValidationLevel.WARNING:
                            warnings.append(error)
                        else:
                            infos.append(error)
                except Exception as e:
                    error = {
                        "field": field,
                        "rule": rule.name,
                        "message": f"Erreur de validation: {str(e)}",
                        "value": value
                    }
                    errors.append(error)

        # Validation des règles globales
        for rule in self._global_rules:
            if not rule.enabled:
                continue
            
            try:
                valid = rule.validator(data, **rule.params)
                if not valid:
                    error = {
                        "field": rule.field,
                        "rule": rule.name,
                        "message": rule.message,
                        "value": data.get(rule.field)
                    }
                    
                    if rule.level == ValidationLevel.ERROR:
                        errors.append(error)
                    elif rule.level == ValidationLevel.WARNING:
                        warnings.append(error)
                    else:
                        infos.append(error)
            except Exception as e:
                error = {
                    "field": rule.field,
                    "rule": rule.name,
                    "message": f"Erreur de validation: {str(e)}",
                    "value": data.get(rule.field)
                }
                errors.append(error)

        # Limitation du nombre d'erreurs
        if len(errors) > self.max_errors:
            errors = errors[:self.max_errors]
            errors.append({
                "field": "_global",
                "rule": "max_errors",
                "message": f"Nombre maximum d'erreurs dépassé ({self.max_errors})"
            })

        valid = len(errors) == 0

        # Mise à jour des métriques
        if valid:
            self._metrics["successful_validations"] += 1
        else:
            self._metrics["failed_validations"] += 1

        result = ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            info=infos
        )

        if self.raise_on_error and not valid:
            raise ValidationError(f"Validation échouée: {len(errors)} erreur(s)")

        return result

    def validate_pydantic(
        self,
        data: Dict[str, Any],
        model: Type[BaseModel]
    ) -> ValidationResult:
        """
        Valide des données avec Pydantic.

        Args:
            data: Données à valider
            model: Modèle Pydantic

        Returns:
            Résultat de validation
        """
        errors = []
        warnings = []
        infos = []

        try:
            validated = model(**data)
            result = ValidationResult(
                valid=True,
                errors=[],
                warnings=[],
                info=[]
            )
            self._metrics["successful_validations"] += 1
            return result
        except ValidationError as e:
            for error in e.errors():
                errors.append({
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "rule": error["type"],
                    "message": error["msg"],
                    "value": error.get("ctx", {}).get("value")
                })
            
            result = ValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
                info=infos
            )
            self._metrics["failed_validations"] += 1
            
            if self.raise_on_error:
                raise
            return result

    def _validate_schema(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Dict[str, List[Dict]]:
        """
        Valide des données avec un schéma Cerberus.

        Args:
            data: Données à valider
            schema: Schéma Cerberus

        Returns:
            Résultat de validation
        """
        v = CerberusValidator(schema)
        
        if v.validate(data):
            return {"errors": [], "warnings": [], "info": []}
        
        errors = []
        for field, field_errors in v.errors.items():
            for error in field_errors:
                errors.append({
                    "field": field,
                    "rule": error,
                    "message": error,
                    "value": data.get(field)
                })
        
        return {"errors": errors, "warnings": [], "info": []}

    # ========================================================================
    # VALIDATEURS PAR DÉFAUT
    # ========================================================================

    def _validate_required(self, value: Any) -> bool:
        """Valide qu'une valeur est présente."""
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, (list, dict)) and not value:
            return False
        return True

    def _validate_type(self, value: Any, type_name: str) -> bool:
        """Valide le type d'une valeur."""
        if type_name not in self.SUPPORTED_TYPES:
            return False
        
        expected_type = self.SUPPORTED_TYPES[type_name]
        
        if expected_type == Decimal:
            try:
                Decimal(str(value))
                return True
            except:
                return False
        elif expected_type == datetime:
            if isinstance(value, datetime):
                return True
            try:
                datetime.fromisoformat(str(value))
                return True
            except:
                return False
        elif expected_type == UUID:
            try:
                UUID(str(value))
                return True
            except:
                return False
        else:
            return isinstance(value, expected_type)

    def _validate_length(
        self,
        value: Any,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ) -> bool:
        """Valide la longueur d'une valeur."""
        if value is None:
            return False
        
        length = len(str(value))
        
        if min_length is not None and length < min_length:
            return False
        if max_length is not None and length > max_length:
            return False
        
        return True

    def _validate_range(
        self,
        value: Any,
        min_value: Optional[Any] = None,
        max_value: Optional[Any] = None
    ) -> bool:
        """Valide la plage d'une valeur."""
        if value is None:
            return False
        
        try:
            numeric_value = float(value)
        except:
            return False
        
        if min_value is not None and numeric_value < float(min_value):
            return False
        if max_value is not None and numeric_value > float(max_value):
            return False
        
        return True

    def _validate_pattern(self, value: Any, pattern: str) -> bool:
        """Valide une valeur avec une expression régulière."""
        if value is None:
            return False
        
        return bool(re.match(pattern, str(value)))

    def _validate_email(self, value: Any) -> bool:
        """Valide une adresse email."""
        if value is None:
            return False
        
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, str(value)))

    def _validate_url(self, value: Any) -> bool:
        """Valide une URL."""
        if value is None:
            return False
        
        pattern = r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$"
        return bool(re.match(pattern, str(value)))

    def _validate_uuid(self, value: Any) -> bool:
        """Valide un UUID."""
        if value is None:
            return False
        
        try:
            UUID(str(value))
            return True
        except:
            return False

    def _validate_ip(self, value: Any) -> bool:
        """Valide une adresse IP."""
        if value is None:
            return False
        
        pattern_ipv4 = r"^(\d{1,3}\.){3}\d{1,3}$"
        pattern_ipv6 = r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"
        
        return bool(re.match(pattern_ipv4, str(value)) or re.match(pattern_ipv6, str(value)))

    def _validate_phone(self, value: Any) -> bool:
        """Valide un numéro de téléphone."""
        if value is None:
            return False
        
        # Format international simplifié
        pattern = r"^\+?[1-9]\d{1,14}$"
        return bool(re.match(pattern, str(value).replace(" ", "").replace("-", "")))

    def _validate_credit_card(self, value: Any) -> bool:
        """Valide un numéro de carte de crédit (algorithme de Luhn)."""
        if value is None:
            return False
        
        # Supprimer les espaces et tirets
        card_number = str(value).replace(" ", "").replace("-", "")
        
        if not card_number.isdigit():
            return False
        
        # Algorithme de Luhn
        total = 0
        alt = False
        
        for digit in reversed(card_number):
            n = int(digit)
            if alt:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
            alt = not alt
        
        return total % 10 == 0

    # ========================================================================
    # VALIDATEURS MÉTIER
    # ========================================================================

    def validate_order(self, order: Dict[str, Any]) -> ValidationResult:
        """
        Valide une commande.

        Args:
            order: Commande à valider

        Returns:
            Résultat de validation
        """
        schema = {
            "symbol": {"type": "string", "required": True},
            "side": {"type": "string", "allowed": ["buy", "sell"], "required": True},
            "quantity": {"type": "number", "min": 0, "required": True},
            "price": {"type": "number", "min": 0, "required": True},
            "order_type": {"type": "string", "allowed": ["market", "limit"], "required": True}
        }
        
        return self.validate(order, schema)

    def validate_transaction(self, transaction: Dict[str, Any]) -> ValidationResult:
        """
        Valide une transaction.

        Args:
            transaction: Transaction à valider

        Returns:
            Résultat de validation
        """
        schema = {
            "from": {"type": "string", "required": True},
            "to": {"type": "string", "required": True},
            "amount": {"type": "number", "min": 0, "required": True},
            "currency": {"type": "string", "required": True},
            "tx_hash": {"type": "string", "required": True}
        }
        
        return self.validate(transaction, schema)

    def validate_wallet(self, wallet: Dict[str, Any]) -> ValidationResult:
        """
        Valide un wallet.

        Args:
            wallet: Wallet à valider

        Returns:
            Résultat de validation
        """
        schema = {
            "address": {"type": "string", "required": True},
            "chain": {"type": "string", "required": True},
            "balance": {"type": "number", "min": 0, "required": True},
            "type": {"type": "string", "allowed": ["hot", "cold", "hardware"], "required": True}
        }
        
        return self.validate(wallet, schema)

    def validate_position(self, position: Dict[str, Any]) -> ValidationResult:
        """
        Valide une position.

        Args:
            position: Position à valider

        Returns:
            Résultat de validation
        """
        schema = {
            "symbol": {"type": "string", "required": True},
            "side": {"type": "string", "allowed": ["long", "short"], "required": True},
            "entry_price": {"type": "number", "min": 0, "required": True},
            "current_price": {"type": "number", "min": 0, "required": True},
            "quantity": {"type": "number", "min": 0, "required": True}
        }
        
        return self.validate(position, schema)

    # ========================================================================
    # VALIDATION DE DONNÉES STRUCTURÉES
    # ========================================================================

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        schema: Dict[str, Dict[str, Any]]
    ) -> ValidationResult:
        """
        Valide un DataFrame.

        Args:
            df: DataFrame à valider
            schema: Schéma de validation

        Returns:
            Résultat de validation
        """
        errors = []
        warnings = []
        infos = []

        # Validation des colonnes
        for column, rules in schema.items():
            if column not in df.columns:
                errors.append({
                    "field": column,
                    "rule": "required",
                    "message": f"Colonne {column} manquante"
                })
                continue

            # Validation des données
            for rule_name, rule_config in rules.items():
                validator = self._validators.get(rule_name)
                if not validator:
                    continue

                try:
                    valid = df[column].apply(
                        lambda x: validator(x, **rule_config.get("params", {}))
                    )
                    
                    if not valid.all():
                        invalid_count = (~valid).sum()
                        errors.append({
                            "field": column,
                            "rule": rule_name,
                            "message": f"{invalid_count} valeur(s) invalide(s)",
                            "invalid_values": df[column][~valid].tolist()
                        })
                except Exception as e:
                    errors.append({
                        "field": column,
                        "rule": rule_name,
                        "message": f"Erreur de validation: {str(e)}"
                    })

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=infos
        )

    def validate_json(
        self,
        json_data: Union[str, Dict],
        schema: Dict[str, Any]
    ) -> ValidationResult:
        """
        Valide des données JSON.

        Args:
            json_data: Données JSON
            schema: Schéma JSON Schema

        Returns:
            Résultat de validation
        """
        errors = []
        warnings = []
        infos = []

        # Conversion en dict si nécessaire
        if isinstance(json_data, str):
            try:
                json_data = json.loads(json_data)
            except json.JSONDecodeError as e:
                return ValidationResult(
                    valid=False,
                    errors=[{
                        "field": "_json",
                        "rule": "parse",
                        "message": f"Erreur de parsing JSON: {str(e)}"
                    }],
                    warnings=[],
                    info=[]
                )

        # Validation avec JSON Schema
        try:
            jsonschema.validate(json_data, schema)
        except jsonschema.ValidationError as e:
            errors.append({
                "field": ".".join(str(p) for p in e.path) if e.path else "_root",
                "rule": e.validator,
                "message": e.message,
                "value": e.instance
            })
        except jsonschema.SchemaError as e:
            errors.append({
                "field": "_schema",
                "rule": "schema",
                "message": f"Erreur de schéma: {str(e)}"
            })

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=infos
        )

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_validations": self._metrics["total_validations"],
                "successful_validations": self._metrics["successful_validations"],
                "failed_validations": self._metrics["failed_validations"],
                "success_rate": (
                    self._metrics["successful_validations"] / self._metrics["total_validations"] * 100
                    if self._metrics["total_validations"] > 0 else 100
                ),
                "by_type": self._metrics["by_type"],
                "last_validation": self._metrics["last_validation"],
                "registered_validators": len(self._validators),
                "registered_rules": sum(len(rules) for rules in self._rules.values()),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de Validator...")
        self._rules.clear()
        self._global_rules.clear()
        self._validators.clear()
        self._results.clear()
        logger.info("Validator fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_validator(
    strict_mode: bool = True,
    raise_on_error: bool = False
) -> Validator:
    """
    Crée une instance de Validator.

    Args:
        strict_mode: Mode strict
        raise_on_error: Lever une exception en cas d'erreur

    Returns:
        Instance de Validator
    """
    return Validator(
        strict_mode=strict_mode,
        raise_on_error=raise_on_error
    )


def validate_json_schema(
    data: Dict[str, Any],
    schema: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Valide des données avec un schéma JSON Schema.

    Args:
        data: Données à valider
        schema: Schéma JSON Schema

    Returns:
        (valide, liste des erreurs)
    """
    try:
        jsonschema.validate(data, schema)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [str(e)]
    except jsonschema.SchemaError as e:
        return False, [f"Erreur de schéma: {str(e)}"]


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ValidationLevel",
    "ValidationType",
    "ValidationResult",
    "ValidationRule",
    "Validator",
    "create_validator",
    "validate_json_schema"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du Validator."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT VALIDATOR")
    print("=" * 60)

    # Création du validateur
    validator = create_validator()

    print(f"\n✅ Validator initialisé")

    # Exemple de données
    data = {
        "name": "John Doe",
        "email": "john@example.com",
        "age": 30,
        "balance": 1000.50,
        "active": True,
        "tags": ["trading", "hedge"]
    }

    # Schéma de validation
    schema = {
        "name": {"type": "string", "minlength": 2, "maxlength": 50},
        "email": {"type": "string", "required": True},
        "age": {"type": "integer", "min": 18, "max": 120},
        "balance": {"type": "number", "min": 0},
        "active": {"type": "boolean"},
        "tags": {"type": "list", "schema": {"type": "string"}}
    }

    # Validation
    print(f"\n📋 Validation des données...")
    result = validator.validate(data, schema)

    print(f"   Valide: {result.valid}")
    if result.errors:
        print(f"   Erreurs: {len(result.errors)}")
        for error in result.errors[:3]:
            print(f"      - {error['field']}: {error['message']}")

    # Validation d'une commande
    print(f"\n💹 Validation d'une commande...")
    order = {
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 0.1,
        "price": 50000,
        "order_type": "limit"
    }

    result = validator.validate_order(order)
    print(f"   Commande valide: {result.valid}")

    # Validation Pydantic
    print(f"\n📦 Validation Pydantic...")
    
    class UserModel(BaseModel):
        name: str
        email: str
        age: int
        active: bool = True

    result = validator.validate_pydantic(data, UserModel)
    print(f"   Modèle valide: {result.valid}")

    # Validation personnalisée
    print(f"\n🔧 Validation personnalisée...")
    
    def validate_positive(value: Any, **kwargs) -> bool:
        return float(value) > 0

    validator.register_validator("positive", validate_positive)
    
    validator.register_rule(
        field="balance",
        rule=ValidationRule(
            name="positive",
            field="balance",
            rule_type=ValidationType.CUSTOM,
            validator=validate_positive,
            message="Le solde doit être positif"
        )
    )

    result = validator.validate({"balance": 100})
    print(f"   Solde positif: {result.valid}")

    result = validator.validate({"balance": -10})
    print(f"   Solde négatif: {result.valid}")

    # Santé du service
    health = validator.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Validations: {health['total_validations']}")
    print(f"   Taux de succès: {health['success_rate']:.1f}%")
    print(f"   Validateurs enregistrés: {health['registered_validators']}")

    # Fermeture
    await validator.close()

    print("\n" + "=" * 60)
    print("Validator NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    from pydantic import BaseModel
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())

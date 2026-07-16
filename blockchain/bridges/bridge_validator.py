
# blockchain/bridges/bridge_validator.py
"""
NEXUS AI TRADING SYSTEM - Bridge Validator Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import re
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Résultat de validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'details': self.details,
        }


@dataclass
class BridgeValidatorConfig:
    """Configuration pour Bridge Validator"""
    min_amount: float = 0.0001
    max_amount: float = 1000000.0
    min_confirmations: int = 12
    max_confirmations: int = 100
    allowed_tokens: List[str] = field(default_factory=lambda: ['ETH', 'USDC', 'USDT', 'DAI', 'WBTC'])
    allowed_chains: List[str] = field(default_factory=lambda: ['ethereum', 'arbitrum', 'avalanche', 'bsc'])
    validate_addresses: bool = True
    validate_amounts: bool = True
    validate_tokens: bool = True
    validate_chains: bool = True
    validate_confirmations: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'min_amount': self.min_amount,
            'max_amount': self.max_amount,
            'min_confirmations': self.min_confirmations,
            'max_confirmations': self.max_confirmations,
            'allowed_tokens': self.allowed_tokens,
            'allowed_chains': self.allowed_chains,
            'validate_addresses': self.validate_addresses,
            'validate_amounts': self.validate_amounts,
            'validate_tokens': self.validate_tokens,
            'validate_chains': self.validate_chains,
            'validate_confirmations': self.validate_confirmations,
        }


class BridgeValidator:
    """
    Validateur pour les bridges.

    Features:
    - Validation des adresses
    - Validation des montants
    - Validation des tokens
    - Validation des confirmations
    - Validation des chaînes

    Example:
        ```python
        config = BridgeValidatorConfig(
            min_amount=0.01,
            max_amount=100000,
            allowed_tokens=['ETH', 'USDC']
        )
        validator = BridgeValidator(config)

        # Valider une transaction
        result = validator.validate_transaction(transaction)
        if result.is_valid:
            # Transaction valide
            pass
        ```
    """

    def __init__(self, config: Optional[BridgeValidatorConfig] = None):
        if not WEB3_AVAILABLE:
            raise ImportError("Web3 n'est pas installé")

        self.config = config or BridgeValidatorConfig()
        self.w3 = Web3()

        logger.info(f"BridgeValidator initialisé")

    def validate_address(self, address: str) -> bool:
        """
        Valide une adresse Ethereum.

        Args:
            address: Adresse à valider

        Returns:
            bool: True si valide
        """
        if not self.config.validate_addresses:
            return True

        return Web3.is_address(address)

    def validate_amount(self, amount: float, token: str) -> ValidationResult:
        """
        Valide un montant.

        Args:
            amount: Montant à valider
            token: Symbole du token

        Returns:
            ValidationResult: Résultat de validation
        """
        errors = []
        warnings = []

        if not self.config.validate_amounts:
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details={'amount': amount, 'token': token},
            )

        if amount <= 0:
            errors.append(f"Montant invalide: {amount} (doit être > 0)")

        if amount < self.config.min_amount:
            warnings.append(f"Montant inférieur au minimum: {amount} < {self.config.min_amount}")

        if amount > self.config.max_amount:
            errors.append(f"Montant supérieur au maximum: {amount} > {self.config.max_amount}")

        # Vérification des décimales du token
        decimals = self._get_token_decimals(token)
        if amount * 10 ** decimals % 1 != 0:
            warnings.append(f"Montant avec des décimales excessives pour {token}")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details={'amount': amount, 'token': token, 'decimals': decimals},
        )

    def validate_token(self, token: str) -> ValidationResult:
        """
        Valide un token.

        Args:
            token: Symbole du token

        Returns:
            ValidationResult: Résultat de validation
        """
        errors = []
        warnings = []

        if not self.config.validate_tokens:
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details={'token': token},
            )

        if not token:
            errors.append("Token non spécifié")

        if token.upper() not in self.config.allowed_tokens:
            errors.append(f"Token non autorisé: {token}")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details={'token': token},
        )

    def validate_chain(self, chain: str) -> ValidationResult:
        """
        Valide une chaîne.

        Args:
            chain: Nom de la chaîne

        Returns:
            ValidationResult: Résultat de validation
        """
        errors = []
        warnings = []

        if not self.config.validate_chains:
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details={'chain': chain},
            )

        if not chain:
            errors.append("Chaîne non spécifiée")

        if chain.lower() not in self.config.allowed_chains:
            errors.append(f"Chaîne non autorisée: {chain}")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details={'chain': chain},
        )

    def validate_confirmations(self, confirmations: int) -> ValidationResult:
        """
        Valide le nombre de confirmations.

        Args:
            confirmations: Nombre de confirmations

        Returns:
            ValidationResult: Résultat de validation
        """
        errors = []
        warnings = []

        if not self.config.validate_confirmations:
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details={'confirmations': confirmations},
            )

        if confirmations < 0:
            errors.append(f"Confirmations invalides: {confirmations}")

        if confirmations < self.config.min_confirmations:
            warnings.append(f"Confirmations inférieures au minimum: {confirmations} < {self.config.min_confirmations}")

        if confirmations > self.config.max_confirmations:
            warnings.append(f"Confirmations supérieures au maximum: {confirmations} > {self.config.max_confirmations}")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details={'confirmations': confirmations},
        )

    def validate_transaction(self, transaction: Dict[str, Any]) -> ValidationResult:
        """
        Valide une transaction complète.

        Args:
            transaction: Transaction à valider

        Returns:
            ValidationResult: Résultat de validation
        """
        errors = []
        warnings = []
        details = {}

        # Validation des champs requis
        required_fields = ['from_address', 'to_address', 'amount', 'token', 'chain']
        for field in required_fields:
            if field not in transaction:
                errors.append(f"Champ requis manquant: {field}")
            else:
                details[field] = transaction[field]

        if errors:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details,
            )

        # Validation des adresses
        if self.config.validate_addresses:
            if not self.validate_address(transaction['from_address']):
                errors.append(f"Adresse source invalide: {transaction['from_address']}")

            if not self.validate_address(transaction['to_address']):
                errors.append(f"Adresse destination invalide: {transaction['to_address']}")

        # Validation du montant
        amount_result = self.validate_amount(transaction['amount'], transaction['token'])
        errors.extend(amount_result.errors)
        warnings.extend(amount_result.warnings)
        details['amount_validation'] = amount_result.details

        # Validation du token
        token_result = self.validate_token(transaction['token'])
        errors.extend(token_result.errors)
        warnings.extend(token_result.warnings)
        details['token_validation'] = token_result.details

        # Validation de la chaîne
        chain_result = self.validate_chain(transaction['chain'])
        errors.extend(chain_result.errors)
        warnings.extend(chain_result.warnings)
        details['chain_validation'] = chain_result.details

        # Validation des confirmations
        if 'confirmations' in transaction:
            conf_result = self.validate_confirmations(transaction['confirmations'])
            warnings.extend(conf_result.warnings)
            details['confirmations_validation'] = conf_result.details

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    def _get_token_decimals(self, token: str) -> int:
        """
        Retourne les décimales d'un token.

        Args:
            token: Symbole du token

        Returns:
            int: Décimales
        """
        decimals = {
            'ETH': 18,
            'USDC': 6,
            'USDT': 6,
            'DAI': 18,
            'WBTC': 8,
        }
        return decimals.get(token.upper(), 18)

    def validate_bridge_operation(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> ValidationResult:
        """
        Valide une opération de bridge.

        Args:
            operation: Type d'opération
            params: Paramètres de l'opération

        Returns:
            ValidationResult: Résultat de validation
        """
        errors = []
        warnings = []
        details = {'operation': operation}

        # Validation des paramètres de l'opération
        if operation == 'deposit':
            if 'amount' not in params:
                errors.append("Montant manquant pour le dépôt")
            if 'token' not in params:
                errors.append("Token manquant pour le dépôt")

        elif operation == 'withdraw':
            if 'amount' not in params:
                errors.append("Montant manquant pour le retrait")
            if 'token' not in params:
                errors.append("Token manquant pour le retrait")

        else:
            errors.append(f"Opération non supportée: {operation}")

        # Validation supplémentaire
        if 'amount' in params and 'token' in params:
            amount_result = self.validate_amount(params['amount'], params['token'])
            errors.extend(amount_result.errors)
            warnings.extend(amount_result.warnings)
            details['amount_validation'] = amount_result.details

        if 'token' in params:
            token_result = self.validate_token(params['token'])
            errors.extend(token_result.errors)
            warnings.extend(token_result.warnings)
            details['token_validation'] = token_result.details

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    def get_validation_rules(self) -> Dict[str, Any]:
        """
        Retourne les règles de validation.

        Returns:
            Dict[str, Any]: Règles
        """
        return {
            'min_amount': self.config.min_amount,
            'max_amount': self.config.max_amount,
            'min_confirmations': self.config.min_confirmations,
            'max_confirmations': self.config.max_confirmations,
            'allowed_tokens': self.config.allowed_tokens,
            'allowed_chains': self.config.allowed_chains,
            'validate_addresses': self.config.validate_addresses,
            'validate_amounts': self.config.validate_amounts,
            'validate_tokens': self.config.validate_tokens,
            'validate_chains': self.config.validate_chains,
            'validate_confirmations': self.config.validate_confirmations,
        }


def create_bridge_validator(
    min_amount: float = 0.0001,
    max_amount: float = 1000000.0,
    **kwargs
) -> BridgeValidator:
    """
    Factory pour créer un validateur de bridge.

    Args:
        min_amount: Montant minimum
        max_amount: Montant maximum
        **kwargs: Arguments supplémentaires

    Returns:
        BridgeValidator: Validateur
    """
    config = BridgeValidatorConfig(
        min_amount=min_amount,
        max_amount=max_amount,
        **kwargs
    )
    return BridgeValidator(config)


__all__ = [
    'BridgeValidator',
    'BridgeValidatorConfig',
    'ValidationResult',
    'create_bridge_validator',
]

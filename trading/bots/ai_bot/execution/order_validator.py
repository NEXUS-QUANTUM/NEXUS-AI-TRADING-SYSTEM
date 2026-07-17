"""
NEXUS AI TRADING SYSTEM - Order Validator for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/execution/order_validator.py
Description: Validateur d'ordres pour le bot AI.
             Supporte la validation complète des ordres, la vérification
             des fonds, des limites, des règles de trading, et de la
             conformité réglementaire.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from trading.bots.ai_bot.execution.order_executor import OrderConfig
from shared.exceptions import OrderValidationError
from shared.helpers.trading_helpers import validate_symbol
from shared.helpers.number_helpers import round_decimal

# Configuration du logging
logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Niveaux de validation."""
    BASIC = "basic"          # Validation de base
    STANDARD = "standard"    # Validation standard
    STRICT = "strict"        # Validation stricte
    COMPLIANCE = "compliance"  # Validation de conformité


class ValidationRule(Enum):
    """Règles de validation."""
    # Règles de base
    SYMBOL_VALID = "symbol_valid"
    SIDE_VALID = "side_valid"
    QUANTITY_POSITIVE = "quantity_positive"
    PRICE_POSITIVE = "price_positive"
    
    # Règles standard
    QUANTITY_LIMIT = "quantity_limit"
    PRICE_LIMIT = "price_limit"
    STOP_PRICE_VALID = "stop_price_valid"
    TAKE_PROFIT_VALID = "take_profit_valid"
    STOP_LOSS_VALID = "stop_loss_valid"
    
    # Règles strictes
    MIN_QUANTITY = "min_quantity"
    MAX_QUANTITY = "max_quantity"
    PRICE_PRECISION = "price_precision"
    QUANTITY_PRECISION = "quantity_precision"
    MIN_PRICE = "min_price"
    MAX_PRICE = "max_price"
    
    # Règles de conformité
    MAX_POSITION_SIZE = "max_position_size"
    MAX_DAILY_VOLUME = "max_daily_volume"
    MAX_OPEN_ORDERS = "max_open_orders"
    MIN_BALANCE = "min_balance"
    MAX_LEVERAGE = "max_leverage"
    
    # Règles de marché
    MARKET_HOURS = "market_hours"
    CIRCUIT_BREAKER = "circuit_breaker"
    PRICE_TOLERANCE = "price_tolerance"


@dataclass
class ValidationConfig:
    """
    Configuration de la validation.
    """
    # Niveau de validation
    level: ValidationLevel = ValidationLevel.STANDARD
    
    # Limites de quantité
    min_quantity: float = 0.0001
    max_quantity: float = 1000000.0
    
    # Limites de prix
    min_price: float = 0.000001
    max_price: float = 10000000.0
    
    # Précision
    price_precision: int = 8
    quantity_precision: int = 8
    
    # Position
    max_position_size: float = 100000.0
    max_daily_volume: float = 1000000.0
    max_open_orders: int = 50
    
    # Balance
    min_balance: float = 100.0
    max_leverage: float = 10.0
    
    # Règles de marché
    price_tolerance: float = 0.05  # 5%
    require_market_hours: bool = False
    
    # Règles de conformité
    require_compliance: bool = False
    max_order_value: float = 1000000.0
    max_daily_trades: int = 1000
    
    # Règles personnalisées
    custom_rules: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.min_quantity <= 0:
            raise OrderValidationError("min_quantity doit être > 0")
        
        if self.max_quantity < self.min_quantity:
            raise OrderValidationError("max_quantity doit être >= min_quantity")
        
        if self.min_price <= 0:
            raise OrderValidationError("min_price doit être > 0")
        
        if self.max_price < self.min_price:
            raise OrderValidationError("max_price doit être >= min_price")
        
        if self.price_precision < 0:
            raise OrderValidationError("price_precision doit être >= 0")
        
        if self.quantity_precision < 0:
            raise OrderValidationError("quantity_precision doit être >= 0")


@dataclass
class ValidationResult:
    """
    Résultat de la validation.
    """
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    passed_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    skipped_rules: List[str] = field(default_factory=list)
    
    def add_error(self, message: str, rule: Optional[str] = None) -> None:
        """Ajoute une erreur."""
        self.is_valid = False
        self.errors.append(message)
        if rule:
            self.failed_rules.append(rule)
    
    def add_warning(self, message: str, rule: Optional[str] = None) -> None:
        """Ajoute un avertissement."""
        self.warnings.append(message)
        if rule:
            self.skipped_rules.append(rule)
    
    def add_passed(self, rule: str) -> None:
        """Ajoute une règle passée."""
        self.passed_rules.append(rule)
    
    def merge(self, other: 'ValidationResult') -> None:
        """Fusionne avec un autre résultat."""
        self.is_valid = self.is_valid and other.is_valid
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.passed_rules.extend(other.passed_rules)
        self.failed_rules.extend(other.failed_rules)
        self.skipped_rules.extend(other.skipped_rules)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'passed_rules': self.passed_rules,
            'failed_rules': self.failed_rules,
            'skipped_rules': self.skipped_rules,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }
    
    def summary(self) -> str:
        """Retourne un résumé."""
        lines = []
        lines.append("=" * 50)
        lines.append(f"VALIDATION RESULT: {'PASSED' if self.is_valid else 'FAILED'}")
        lines.append("=" * 50)
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  ✗ {error}")
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")
        lines.append(f"Passed rules: {len(self.passed_rules)}")
        lines.append(f"Failed rules: {len(self.failed_rules)}")
        lines.append("=" * 50)
        return "\n".join(lines)


class OrderValidator:
    """
    Validateur d'ordres.
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialise le validateur.
        
        Args:
            config: Configuration de la validation.
        """
        self.config = config or ValidationConfig()
        
        # Cache
        self._validation_cache: Dict[str, ValidationResult] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._cache_ttl: int = 60  # secondes
        
        # Statistiques
        self._stats = {
            'total_validations': 0,
            'passed_validations': 0,
            'failed_validations': 0,
            'total_errors': 0,
            'total_warnings': 0
        }
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_validation': [],
            'on_validation_failed': [],
            'on_validation_passed': []
        }
        
        logger.info("OrderValidator initialisé")
        logger.info(f"Niveau de validation: {self.config.level.value}")
    
    # ============================================================
    # VALIDATION PRINCIPALE
    # ============================================================
    
    def validate_order(
        self,
        order: Union[OrderConfig, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Valide un ordre.
        
        Args:
            order: Ordre à valider.
            context: Contexte de validation (balance, positions, etc.).
            
        Returns:
            Résultat de la validation.
        """
        # Conversion en OrderConfig
        if isinstance(order, dict):
            try:
                order = OrderConfig(**order)
            except Exception as e:
                result = ValidationResult()
                result.add_error(f"Conversion d'ordre échouée: {e}")
                return result
        
        # Vérification du cache
        cache_key = self._generate_cache_key(order)
        if cache_key in self._validation_cache:
            timestamp = self._cache_timestamps.get(cache_key)
            if timestamp and (datetime.now() - timestamp).seconds < self._cache_ttl:
                logger.debug(f"Cache hit pour l'ordre {order.id}")
                return self._validation_cache[cache_key]
        
        logger.info(f"Validation de l'ordre {order.id}")
        self._stats['total_validations'] += 1
        
        result = ValidationResult()
        
        # Déterminer les règles à appliquer
        rules = self._get_rules_to_apply()
        
        # Application des règles
        for rule in rules:
            rule_result = self._apply_rule(rule, order, context)
            result.merge(rule_result)
            
            # Logging
            if not rule_result.is_valid:
                logger.warning(f"Règle {rule.value} échouée: {', '.join(rule_result.errors)}")
            else:
                logger.debug(f"Règle {rule.value} passée")
        
        # Mise à jour des statistiques
        if result.is_valid:
            self._stats['passed_validations'] += 1
            self._notify_callbacks('on_validation_passed', {
                'order_id': order.id,
                'result': result.to_dict()
            })
        else:
            self._stats['failed_validations'] += 1
            self._notify_callbacks('on_validation_failed', {
                'order_id': order.id,
                'result': result.to_dict()
            })
        
        self._stats['total_errors'] += len(result.errors)
        self._stats['total_warnings'] += len(result.warnings)
        
        # Mise en cache
        self._validation_cache[cache_key] = result
        self._cache_timestamps[cache_key] = datetime.now()
        
        # Notification
        self._notify_callbacks('on_validation', {
            'order_id': order.id,
            'result': result.to_dict()
        })
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(result.summary())
        
        return result
    
    def validate_order_batch(
        self,
        orders: List[Union[OrderConfig, Dict[str, Any]]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResult]:
        """
        Valide un lot d'ordres.
        
        Args:
            orders: Liste des ordres.
            context: Contexte de validation.
            
        Returns:
            Liste des résultats de validation.
        """
        results = []
        
        for order in orders:
            result = self.validate_order(order, context)
            results.append(result)
        
        return results
    
    # ============================================================
    # RÈGLES DE VALIDATION
    # ============================================================
    
    def _get_rules_to_apply(self) -> List[ValidationRule]:
        """
        Détermine les règles à appliquer.
        
        Returns:
            Liste des règles.
        """
        if self.config.level == ValidationLevel.BASIC:
            return [
                ValidationRule.SYMBOL_VALID,
                ValidationRule.SIDE_VALID,
                ValidationRule.QUANTITY_POSITIVE,
                ValidationRule.PRICE_POSITIVE
            ]
        
        elif self.config.level == ValidationLevel.STANDARD:
            return [
                ValidationRule.SYMBOL_VALID,
                ValidationRule.SIDE_VALID,
                ValidationRule.QUANTITY_POSITIVE,
                ValidationRule.PRICE_POSITIVE,
                ValidationRule.QUANTITY_LIMIT,
                ValidationRule.PRICE_LIMIT,
                ValidationRule.STOP_PRICE_VALID,
                ValidationRule.TAKE_PROFIT_VALID,
                ValidationRule.STOP_LOSS_VALID
            ]
        
        elif self.config.level == ValidationLevel.STRICT:
            return [
                ValidationRule.SYMBOL_VALID,
                ValidationRule.SIDE_VALID,
                ValidationRule.QUANTITY_POSITIVE,
                ValidationRule.PRICE_POSITIVE,
                ValidationRule.QUANTITY_LIMIT,
                ValidationRule.PRICE_LIMIT,
                ValidationRule.STOP_PRICE_VALID,
                ValidationRule.TAKE_PROFIT_VALID,
                ValidationRule.STOP_LOSS_VALID,
                ValidationRule.MIN_QUANTITY,
                ValidationRule.MAX_QUANTITY,
                ValidationRule.PRICE_PRECISION,
                ValidationRule.QUANTITY_PRECISION,
                ValidationRule.MIN_PRICE,
                ValidationRule.MAX_PRICE
            ]
        
        elif self.config.level == ValidationLevel.COMPLIANCE:
            return [
                ValidationRule.SYMBOL_VALID,
                ValidationRule.SIDE_VALID,
                ValidationRule.QUANTITY_POSITIVE,
                ValidationRule.PRICE_POSITIVE,
                ValidationRule.QUANTITY_LIMIT,
                ValidationRule.PRICE_LIMIT,
                ValidationRule.MIN_QUANTITY,
                ValidationRule.MAX_QUANTITY,
                ValidationRule.MAX_POSITION_SIZE,
                ValidationRule.MAX_DAILY_VOLUME,
                ValidationRule.MAX_OPEN_ORDERS,
                ValidationRule.MIN_BALANCE,
                ValidationRule.MAX_LEVERAGE,
                ValidationRule.PRICE_TOLERANCE,
                ValidationRule.MARKET_HOURS,
                ValidationRule.CIRCUIT_BREAKER
            ]
        
        else:
            return []
    
    def _apply_rule(
        self,
        rule: ValidationRule,
        order: OrderConfig,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Applique une règle de validation.
        
        Args:
            rule: Règle à appliquer.
            order: Ordre à valider.
            context: Contexte de validation.
            
        Returns:
            Résultat de la règle.
        """
        result = ValidationResult()
        
        try:
            if rule == ValidationRule.SYMBOL_VALID:
                self._validate_symbol(order, result)
            elif rule == ValidationRule.SIDE_VALID:
                self._validate_side(order, result)
            elif rule == ValidationRule.QUANTITY_POSITIVE:
                self._validate_quantity_positive(order, result)
            elif rule == ValidationRule.PRICE_POSITIVE:
                self._validate_price_positive(order, result)
            elif rule == ValidationRule.QUANTITY_LIMIT:
                self._validate_quantity_limit(order, result)
            elif rule == ValidationRule.PRICE_LIMIT:
                self._validate_price_limit(order, result)
            elif rule == ValidationRule.STOP_PRICE_VALID:
                self._validate_stop_price(order, result)
            elif rule == ValidationRule.TAKE_PROFIT_VALID:
                self._validate_take_profit(order, result)
            elif rule == ValidationRule.STOP_LOSS_VALID:
                self._validate_stop_loss(order, result)
            elif rule == ValidationRule.MIN_QUANTITY:
                self._validate_min_quantity(order, result)
            elif rule == ValidationRule.MAX_QUANTITY:
                self._validate_max_quantity(order, result)
            elif rule == ValidationRule.PRICE_PRECISION:
                self._validate_price_precision(order, result)
            elif rule == ValidationRule.QUANTITY_PRECISION:
                self._validate_quantity_precision(order, result)
            elif rule == ValidationRule.MIN_PRICE:
                self._validate_min_price(order, result)
            elif rule == ValidationRule.MAX_PRICE:
                self._validate_max_price(order, result)
            elif rule == ValidationRule.MAX_POSITION_SIZE:
                self._validate_max_position_size(order, context, result)
            elif rule == ValidationRule.MAX_DAILY_VOLUME:
                self._validate_max_daily_volume(order, context, result)
            elif rule == ValidationRule.MAX_OPEN_ORDERS:
                self._validate_max_open_orders(order, context, result)
            elif rule == ValidationRule.MIN_BALANCE:
                self._validate_min_balance(order, context, result)
            elif rule == ValidationRule.MAX_LEVERAGE:
                self._validate_max_leverage(order, context, result)
            elif rule == ValidationRule.PRICE_TOLERANCE:
                self._validate_price_tolerance(order, context, result)
            elif rule == ValidationRule.MARKET_HOURS:
                self._validate_market_hours(order, result)
            elif rule == ValidationRule.CIRCUIT_BREAKER:
                self._validate_circuit_breaker(order, context, result)
            else:
                result.add_warning(f"Règle non implémentée: {rule.value}", rule.value)
        except Exception as e:
            result.add_error(f"Erreur dans la règle {rule.value}: {e}", rule.value)
        
        if result.is_valid:
            result.add_passed(rule.value)
        
        return result
    
    # ============================================================
    # VALIDATEURS SPÉCIFIQUES
    # ============================================================
    
    def _validate_symbol(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide le symbole."""
        if not order.symbol:
            result.add_error("Symbole requis", "symbol_valid")
            return
        
        if not validate_symbol(order.symbol):
            result.add_error(f"Symbole invalide: {order.symbol}", "symbol_valid")
    
    def _validate_side(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide le côté de l'ordre."""
        if order.side not in ['BUY', 'SELL']:
            result.add_error(f"Côté invalide: {order.side}", "side_valid")
    
    def _validate_quantity_positive(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide que la quantité est positive."""
        if order.quantity <= 0:
            result.add_error(f"Quantité doit être positive: {order.quantity}", "quantity_positive")
    
    def _validate_price_positive(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide que le prix est positif."""
        if order.order_type in ['LIMIT', 'STOP_LIMIT']:
            if order.price is not None and order.price <= 0:
                result.add_error(f"Prix doit être positif: {order.price}", "price_positive")
    
    def _validate_quantity_limit(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide les limites de quantité."""
        if order.quantity > self.config.max_quantity:
            result.add_error(
                f"Quantité dépasse la limite maximum: {order.quantity} > {self.config.max_quantity}",
                "quantity_limit"
            )
    
    def _validate_price_limit(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide les limites de prix."""
        if order.order_type in ['LIMIT', 'STOP_LIMIT']:
            if order.price is not None:
                if order.price > self.config.max_price:
                    result.add_error(
                        f"Prix dépasse la limite maximum: {order.price} > {self.config.max_price}",
                        "price_limit"
                    )
                if order.price < self.config.min_price:
                    result.add_error(
                        f"Prix en dessous de la limite minimum: {order.price} < {self.config.min_price}",
                        "price_limit"
                    )
    
    def _validate_stop_price(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide le prix stop."""
        if order.order_type in ['STOP', 'STOP_LIMIT']:
            if order.stop_price is None:
                result.add_error("Prix stop requis", "stop_price_valid")
            elif order.stop_price <= 0:
                result.add_error(f"Prix stop doit être positif: {order.stop_price}", "stop_price_valid")
    
    def _validate_take_profit(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide le take profit."""
        if order.take_profit is not None:
            if order.take_profit <= 0:
                result.add_error(f"Take profit doit être positif: {order.take_profit}", "take_profit_valid")
            if order.price is not None:
                if order.side == 'BUY' and order.take_profit <= order.price:
                    result.add_error(f"Take profit doit être > prix pour un BUY: {order.take_profit} <= {order.price}", "take_profit_valid")
                if order.side == 'SELL' and order.take_profit >= order.price:
                    result.add_error(f"Take profit doit être < prix pour un SELL: {order.take_profit} >= {order.price}", "take_profit_valid")
    
    def _validate_stop_loss(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide le stop loss."""
        if order.stop_loss is not None:
            if order.stop_loss <= 0:
                result.add_error(f"Stop loss doit être positif: {order.stop_loss}", "stop_loss_valid")
            if order.price is not None:
                if order.side == 'BUY' and order.stop_loss >= order.price:
                    result.add_error(f"Stop loss doit être < prix pour un BUY: {order.stop_loss} >= {order.price}", "stop_loss_valid")
                if order.side == 'SELL' and order.stop_loss <= order.price:
                    result.add_error(f"Stop loss doit être > prix pour un SELL: {order.stop_loss} <= {order.price}", "stop_loss_valid")
    
    def _validate_min_quantity(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide la quantité minimale."""
        if order.quantity < self.config.min_quantity:
            result.add_error(
                f"Quantité en dessous du minimum: {order.quantity} < {self.config.min_quantity}",
                "min_quantity"
            )
    
    def _validate_max_quantity(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide la quantité maximale."""
        if order.quantity > self.config.max_quantity:
            result.add_error(
                f"Quantité dépasse le maximum: {order.quantity} > {self.config.max_quantity}",
                "max_quantity"
            )
    
    def _validate_price_precision(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide la précision du prix."""
        if order.price is not None:
            price_str = f"{order.price:.10f}"
            decimals = len(price_str.split('.')[1]) if '.' in price_str else 0
            if decimals > self.config.price_precision:
                result.add_error(
                    f"Précision du prix trop élevée: {decimals} > {self.config.price_precision}",
                    "price_precision"
                )
    
    def _validate_quantity_precision(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide la précision de la quantité."""
        quantity_str = f"{order.quantity:.10f}"
        decimals = len(quantity_str.split('.')[1]) if '.' in quantity_str else 0
        if decimals > self.config.quantity_precision:
            result.add_error(
                f"Précision de la quantité trop élevée: {decimals} > {self.config.quantity_precision}",
                "quantity_precision"
            )
    
    def _validate_min_price(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide le prix minimum."""
        if order.price is not None and order.price < self.config.min_price:
            result.add_error(
                f"Prix en dessous du minimum: {order.price} < {self.config.min_price}",
                "min_price"
            )
    
    def _validate_max_price(self, order: OrderConfig, result: ValidationResult) -> None:
        """Valide le prix maximum."""
        if order.price is not None and order.price > self.config.max_price:
            result.add_error(
                f"Prix dépasse le maximum: {order.price} > {self.config.max_price}",
                "max_price"
            )
    
    def _validate_max_position_size(
        self,
        order: OrderConfig,
        context: Optional[Dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """Valide la taille maximale de position."""
        if context and 'current_position' in context:
            current_position = context['current_position']
            new_position = current_position + order.quantity * (1 if order.side == 'BUY' else -1)
            if abs(new_position) > self.config.max_position_size:
                result.add_error(
                    f"Taille de position dépasse la limite: {abs(new_position)} > {self.config.max_position_size}",
                    "max_position_size"
                )
    
    def _validate_max_daily_volume(
        self,
        order: OrderConfig,
        context: Optional[Dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """Valide le volume quotidien maximum."""
        if context and 'daily_volume' in context:
            if context['daily_volume'] + order.quantity > self.config.max_daily_volume:
                result.add_error(
                    f"Volume quotidien dépasse la limite: {context['daily_volume'] + order.quantity} > {self.config.max_daily_volume}",
                    "max_daily_volume"
                )
    
    def _validate_max_open_orders(
        self,
        order: OrderConfig,
        context: Optional[Dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """Valide le nombre maximum d'ordres ouverts."""
        if context and 'open_orders' in context:
            if context['open_orders'] + 1 > self.config.max_open_orders:
                result.add_error(
                    f"Nombre d'ordres ouverts dépasse la limite: {context['open_orders'] + 1} > {self.config.max_open_orders}",
                    "max_open_orders"
                )
    
    def _validate_min_balance(
        self,
        order: OrderConfig,
        context: Optional[Dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """Valide le solde minimum."""
        if context and 'balance' in context:
            estimated_cost = order.quantity * (order.price or 0)
            if context['balance'] - estimated_cost < self.config.min_balance:
                result.add_error(
                    f"Solde insuffisant: {context['balance']} - {estimated_cost} < {self.config.min_balance}",
                    "min_balance"
                )
    
    def _validate_max_leverage(
        self,
        order: OrderConfig,
        context: Optional[Dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """Valide le levier maximum."""
        if context and 'leverage' in context:
            if context['leverage'] > self.config.max_leverage:
                result.add_error(
                    f"Levier dépasse la limite: {context['leverage']} > {self.config.max_leverage}",
                    "max_leverage"
                )
    
    def _validate_price_tolerance(
        self,
        order: OrderConfig,
        context: Optional[Dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """Valide la tolérance de prix."""
        if context and 'market_price' in context:
            if order.price is not None:
                diff = abs(order.price - context['market_price']) / context['market_price']
                if diff > self.config.price_tolerance:
                    result.add_error(
                        f"Prix hors tolérance: {diff:.2%} > {self.config.price_tolerance:.2%}",
                        "price_tolerance"
                    )
    
    def _validate_market_hours(
        self,
        order: OrderConfig,
        result: ValidationResult
    ) -> None:
        """Valide les heures de marché."""
        if self.config.require_market_hours:
            now = datetime.now()
            # Simuler les heures de marché (9:30 - 16:00)
            if now.weekday() in [5, 6]:  # Week-end
                result.add_error("Marché fermé (week-end)", "market_hours")
            elif not (9 <= now.hour < 16):
                result.add_error("Marché fermé (hors heures)", "market_hours")
            elif now.hour == 9 and now.minute < 30:
                result.add_error("Marché fermé (avant l'ouverture)", "market_hours")
    
    def _validate_circuit_breaker(
        self,
        order: OrderConfig,
        context: Optional[Dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """Valide le circuit breaker."""
        if context and 'circuit_breaker' in context:
            if context['circuit_breaker']:
                result.add_error("Circuit breaker actif", "circuit_breaker")
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def _generate_cache_key(self, order: OrderConfig) -> str:
        """
        Génère une clé de cache.
        
        Args:
            order: Ordre.
            
        Returns:
            Clé de cache.
        """
        return f"{order.id}_{order.symbol}_{order.side}_{order.quantity}_{order.price}_{order.order_type}"
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques.
        
        Returns:
            Statistiques du validateur.
        """
        return self._stats.copy()
    
    def reset(self) -> None:
        """
        Réinitialise le validateur.
        """
        self._validation_cache.clear()
        self._cache_timestamps.clear()
        self._stats = {
            'total_validations': 0,
            'passed_validations': 0,
            'failed_validations': 0,
            'total_errors': 0,
            'total_warnings': 0
        }
        
        logger.info("OrderValidator réinitialisé")
    
    def clear_cache(self) -> None:
        """
        Vide le cache.
        """
        self._validation_cache.clear()
        self._cache_timestamps.clear()
        logger.info("Cache vidé")
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on_validation(self, callback: Callable) -> None:
        """Ajoute un callback pour la validation."""
        self._callbacks['on_validation'].append(callback)
    
    def on_validation_failed(self, callback: Callable) -> None:
        """Ajoute un callback pour la validation échouée."""
        self._callbacks['on_validation_failed'].append(callback)
    
    def on_validation_passed(self, callback: Callable) -> None:
        """Ajoute un callback pour la validation réussie."""
        self._callbacks['on_validation_passed'].append(callback)
    
    def _notify_callbacks(self, event: str, data: Any) -> None:
        """
        Notifie les callbacks.
        
        Args:
            event: Nom de l'événement.
            data: Données.
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Erreur dans le callback {event}: {e}")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_order_validator(
    level: str = "standard",
    **kwargs
) -> OrderValidator:
    """
    Crée un validateur d'ordres.
    
    Args:
        level: Niveau de validation.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du validateur.
    """
    level_map = {
        'basic': ValidationLevel.BASIC,
        'standard': ValidationLevel.STANDARD,
        'strict': ValidationLevel.STRICT,
        'compliance': ValidationLevel.COMPLIANCE
    }
    
    config = ValidationConfig(
        level=level_map.get(level, ValidationLevel.STANDARD),
        **kwargs
    )
    return OrderValidator(config)


def validate_order_simple(
    order: Union[OrderConfig, Dict[str, Any]]
) -> ValidationResult:
    """
    Validation simple d'un ordre.
    
    Args:
        order: Ordre à valider.
        
    Returns:
        Résultat de la validation.
    """
    validator = OrderValidator()
    return validator.validate_order(order)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'OrderValidator',
    'ValidationConfig',
    'ValidationResult',
    'ValidationLevel',
    'ValidationRule',
    'create_order_validator',
    'validate_order_simple'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

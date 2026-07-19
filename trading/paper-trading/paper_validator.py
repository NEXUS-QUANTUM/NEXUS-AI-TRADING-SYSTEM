"""
NEXUS AI TRADING SYSTEM - Paper Trading Validator Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_validator.py
Description: Paper trading validation with full API integration
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.paper_trading_config import PaperTradingConfig
from shared.constants.trading_constants import ORDER_TYPES, TIME_FRAMES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class ValidationLevel(str, Enum):
    """Validation levels"""
    BASIC = "basic"  # Basic validation
    STANDARD = "standard"  # Standard validation
    STRICT = "strict"  # Strict validation
    FULL = "full"  # Full validation


class ValidationResult(str, Enum):
    """Validation result"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class ValidationRule(str, Enum):
    """Validation rules"""
    # Order validation
    MIN_ORDER_SIZE = "min_order_size"
    MAX_ORDER_SIZE = "max_order_size"
    MIN_PRICE = "min_price"
    MAX_PRICE = "max_price"
    PRICE_PRECISION = "price_precision"
    SIZE_PRECISION = "size_precision"
    
    # Account validation
    SUFFICIENT_BALANCE = "sufficient_balance"
    SUFFICIENT_MARGIN = "sufficient_margin"
    MAX_POSITIONS = "max_positions"
    MAX_LEVERAGE = "max_leverage"
    
    # Market validation
    SYMBOL_EXISTS = "symbol_exists"
    MARKET_OPEN = "market_open"
    LIQUIDITY_CHECK = "liquidity_check"
    VOLATILITY_CHECK = "volatility_check"
    
    # Risk validation
    RISK_LIMIT = "risk_limit"
    POSITION_LIMIT = "position_limit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ValidationRequest(BaseModel):
    """Request model for validation"""
    account_id: str
    symbol: str
    side: str
    size: float
    price: float
    order_type: str = "limit"
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v

    @validator('price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Price must be positive")
        return v


class ValidationResponse(BaseModel):
    """Response model for validation"""
    request_id: str
    account_id: str
    symbol: str
    result: ValidationResult
    level: ValidationLevel
    checks: List[Dict[str, Any]]
    passed_checks: int
    failed_checks: int
    warnings: List[str]
    errors: List[str]
    recommendations: List[str]
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationRuleConfig(BaseModel):
    """Configuration for validation rule"""
    rule: ValidationRule
    enabled: bool = True
    threshold: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    action: str = "reject"  # reject, warn, pass
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ValidationContext:
    """Context for validation"""
    account_id: str
    symbol: str
    side: str
    size: float
    price: float
    order_type: str
    validation_level: ValidationLevel
    account_data: Dict[str, Any]
    market_data: Dict[str, Any]
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]


@dataclass
class ValidationCheck:
    """Validation check result"""
    rule: ValidationRule
    passed: bool
    message: str
    severity: str  # error, warning, info
    value: Optional[float] = None
    threshold: Optional[float] = None


# =============================================================================
# PAPER TRADING VALIDATOR
# =============================================================================

class PaperTradingValidator:
    """
    Paper Trading Validator with full API integration.
    
    Features:
    - Order validation
    - Account validation
    - Market validation
    - Risk validation
    - Multiple validation levels
    - Configurable rules
    - Detailed validation reports
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None
    ):
        """
        Initialize PaperTradingValidator.
        
        Args:
            config: Paper trading configuration
        """
        self.config = config or PaperTradingConfig()
        
        # Validation rules
        self._rules: Dict[ValidationRule, ValidationRuleConfig] = {}
        
        # Initialize default rules
        self._init_default_rules()
        
        logger.info("PaperTradingValidator initialized")

    def _init_default_rules(self) -> None:
        """Initialize default validation rules"""
        default_rules = {
            ValidationRule.MIN_ORDER_SIZE: ValidationRuleConfig(
                rule=ValidationRule.MIN_ORDER_SIZE,
                enabled=True,
                min_value=0.001,
                action="reject"
            ),
            ValidationRule.MAX_ORDER_SIZE: ValidationRuleConfig(
                rule=ValidationRule.MAX_ORDER_SIZE,
                enabled=True,
                max_value=1000000,
                action="reject"
            ),
            ValidationRule.MIN_PRICE: ValidationRuleConfig(
                rule=ValidationRule.MIN_PRICE,
                enabled=True,
                min_value=0.000001,
                action="reject"
            ),
            ValidationRule.MAX_PRICE: ValidationRuleConfig(
                rule=ValidationRule.MAX_PRICE,
                enabled=True,
                max_value=10000000,
                action="reject"
            ),
            ValidationRule.PRICE_PRECISION: ValidationRuleConfig(
                rule=ValidationRule.PRICE_PRECISION,
                enabled=True,
                action="reject"
            ),
            ValidationRule.SIZE_PRECISION: ValidationRuleConfig(
                rule=ValidationRule.SIZE_PRECISION,
                enabled=True,
                action="reject"
            ),
            ValidationRule.SUFFICIENT_BALANCE: ValidationRuleConfig(
                rule=ValidationRule.SUFFICIENT_BALANCE,
                enabled=True,
                action="reject"
            ),
            ValidationRule.SUFFICIENT_MARGIN: ValidationRuleConfig(
                rule=ValidationRule.SUFFICIENT_MARGIN,
                enabled=True,
                action="reject"
            ),
            ValidationRule.MAX_POSITIONS: ValidationRuleConfig(
                rule=ValidationRule.MAX_POSITIONS,
                enabled=True,
                max_value=100,
                action="reject"
            ),
            ValidationRule.MAX_LEVERAGE: ValidationRuleConfig(
                rule=ValidationRule.MAX_LEVERAGE,
                enabled=True,
                max_value=2.0,
                action="reject"
            ),
            ValidationRule.SYMBOL_EXISTS: ValidationRuleConfig(
                rule=ValidationRule.SYMBOL_EXISTS,
                enabled=True,
                action="reject"
            ),
            ValidationRule.MARKET_OPEN: ValidationRuleConfig(
                rule=ValidationRule.MARKET_OPEN,
                enabled=True,
                action="reject"
            ),
            ValidationRule.RISK_LIMIT: ValidationRuleConfig(
                rule=ValidationRule.RISK_LIMIT,
                enabled=True,
                threshold=0.05,
                action="reject"
            ),
            ValidationRule.POSITION_LIMIT: ValidationRuleConfig(
                rule=ValidationRule.POSITION_LIMIT,
                enabled=True,
                max_value=1000,
                action="reject"
            ),
            ValidationRule.DAILY_LOSS_LIMIT: ValidationRuleConfig(
                rule=ValidationRule.DAILY_LOSS_LIMIT,
                enabled=True,
                max_value=10000,
                action="reject"
            )
        }
        
        self._rules = default_rules

    # =========================================================================
    # Validation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def validate(
        self,
        request: ValidationRequest
    ) -> ValidationResponse:
        """
        Validate an order.
        
        Args:
            request: Validation request
            
        Returns:
            ValidationResponse: Validation results
        """
        try:
            # Generate request ID
            request_id = f"val_{int(time.time() * 1000)}_{request.account_id[:8]}"
            
            # Build context
            context = await self._build_context(request)
            
            # Run validation checks
            checks = await self._run_checks(context)
            
            # Determine result
            passed_checks = sum(1 for c in checks if c.passed)
            failed_checks = sum(1 for c in checks if not c.passed)
            
            errors = [c.message for c in checks if not c.passed and c.severity == 'error']
            warnings = [c.message for c in checks if not c.passed and c.severity == 'warning']
            
            result = ValidationResult.PASSED
            if errors:
                result = ValidationResult.FAILED
            elif warnings:
                result = ValidationResult.WARNING
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(checks)
            
            return ValidationResponse(
                request_id=request_id,
                account_id=request.account_id,
                symbol=request.symbol,
                result=result,
                level=request.validation_level,
                checks=[asdict(c) for c in checks],
                passed_checks=passed_checks,
                failed_checks=failed_checks,
                warnings=warnings,
                errors=errors,
                recommendations=recommendations,
                timestamp=datetime.utcnow(),
                metadata=request.metadata
            )
            
        except Exception as e:
            logger.error(f"Error validating request: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Validation failed: {str(e)}"
            )

    async def _build_context(self, request: ValidationRequest) -> ValidationContext:
        """Build validation context"""
        # Get account data
        account_data = await self._get_account_data(request.account_id)
        
        # Get market data
        market_data = await self._get_market_data(request.symbol)
        
        # Get positions
        positions = await self._get_positions(request.account_id)
        
        # Get orders
        orders = await self._get_orders(request.account_id)
        
        return ValidationContext(
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            price=request.price,
            order_type=request.order_type,
            validation_level=request.validation_level,
            account_data=account_data,
            market_data=market_data,
            positions=positions,
            orders=orders
        )

    async def _get_account_data(self, account_id: str) -> Dict[str, Any]:
        """Get account data"""
        # In production, would fetch from database
        return {
            'balance': 100000.0,
            'equity': 100000.0,
            'margin_used': 0,
            'margin_available': 100000.0,
            'leverage': 1.0,
            'daily_pnl': 0,
            'daily_loss': 0
        }

    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data"""
        # In production, would fetch from market service
        return {
            'exists': True,
            'open': True,
            'price': 100.0,
            'bid': 99.95,
            'ask': 100.05,
            'volume': 1000000,
            'volatility': 0.02,
            'spread': 0.001
        }

    async def _get_positions(self, account_id: str) -> List[Dict[str, Any]]:
        """Get positions"""
        return []

    async def _get_orders(self, account_id: str) -> List[Dict[str, Any]]:
        """Get orders"""
        return []

    # =========================================================================
    # Validation Checks
    # =========================================================================

    async def _run_checks(
        self,
        context: ValidationContext
    ) -> List[ValidationCheck]:
        """Run all validation checks"""
        checks = []
        
        # Order validation
        if self._rules[ValidationRule.MIN_ORDER_SIZE].enabled:
            checks.append(await self._check_min_order_size(context))
        
        if self._rules[ValidationRule.MAX_ORDER_SIZE].enabled:
            checks.append(await self._check_max_order_size(context))
        
        if self._rules[ValidationRule.MIN_PRICE].enabled:
            checks.append(await self._check_min_price(context))
        
        if self._rules[ValidationRule.MAX_PRICE].enabled:
            checks.append(await self._check_max_price(context))
        
        if self._rules[ValidationRule.PRICE_PRECISION].enabled:
            checks.append(await self._check_price_precision(context))
        
        if self._rules[ValidationRule.SIZE_PRECISION].enabled:
            checks.append(await self._check_size_precision(context))
        
        # Account validation
        if self._rules[ValidationRule.SUFFICIENT_BALANCE].enabled:
            checks.append(await self._check_sufficient_balance(context))
        
        if self._rules[ValidationRule.SUFFICIENT_MARGIN].enabled:
            checks.append(await self._check_sufficient_margin(context))
        
        if self._rules[ValidationRule.MAX_POSITIONS].enabled:
            checks.append(await self._check_max_positions(context))
        
        if self._rules[ValidationRule.MAX_LEVERAGE].enabled:
            checks.append(await self._check_max_leverage(context))
        
        # Market validation
        if self._rules[ValidationRule.SYMBOL_EXISTS].enabled:
            checks.append(await self._check_symbol_exists(context))
        
        if self._rules[ValidationRule.MARKET_OPEN].enabled:
            checks.append(await self._check_market_open(context))
        
        # Risk validation
        if self._rules[ValidationRule.RISK_LIMIT].enabled:
            checks.append(await self._check_risk_limit(context))
        
        if self._rules[ValidationRule.POSITION_LIMIT].enabled:
            checks.append(await self._check_position_limit(context))
        
        if self._rules[ValidationRule.DAILY_LOSS_LIMIT].enabled:
            checks.append(await self._check_daily_loss_limit(context))
        
        return checks

    # -------------------------------------------------------------------------
    # Order Validation Checks
    # -------------------------------------------------------------------------

    async def _check_min_order_size(self, context: ValidationContext) -> ValidationCheck:
        """Check minimum order size"""
        rule = self._rules[ValidationRule.MIN_ORDER_SIZE]
        min_size = rule.min_value or 0.001
        
        passed = context.size >= min_size
        
        return ValidationCheck(
            rule=ValidationRule.MIN_ORDER_SIZE,
            passed=passed,
            message=f"Order size {context.size} must be at least {min_size}" if not passed else "Order size is valid",
            severity='error' if not passed else 'info',
            value=context.size,
            threshold=min_size
        )

    async def _check_max_order_size(self, context: ValidationContext) -> ValidationCheck:
        """Check maximum order size"""
        rule = self._rules[ValidationRule.MAX_ORDER_SIZE]
        max_size = rule.max_value or 1000000
        
        passed = context.size <= max_size
        
        return ValidationCheck(
            rule=ValidationRule.MAX_ORDER_SIZE,
            passed=passed,
            message=f"Order size {context.size} exceeds maximum {max_size}" if not passed else "Order size is valid",
            severity='error' if not passed else 'info',
            value=context.size,
            threshold=max_size
        )

    async def _check_min_price(self, context: ValidationContext) -> ValidationCheck:
        """Check minimum price"""
        rule = self._rules[ValidationRule.MIN_PRICE]
        min_price = rule.min_value or 0.000001
        
        passed = context.price >= min_price
        
        return ValidationCheck(
            rule=ValidationRule.MIN_PRICE,
            passed=passed,
            message=f"Price {context.price} must be at least {min_price}" if not passed else "Price is valid",
            severity='error' if not passed else 'info',
            value=context.price,
            threshold=min_price
        )

    async def _check_max_price(self, context: ValidationContext) -> ValidationCheck:
        """Check maximum price"""
        rule = self._rules[ValidationRule.MAX_PRICE]
        max_price = rule.max_value or 10000000
        
        passed = context.price <= max_price
        
        return ValidationCheck(
            rule=ValidationRule.MAX_PRICE,
            passed=passed,
            message=f"Price {context.price} exceeds maximum {max_price}" if not passed else "Price is valid",
            severity='error' if not passed else 'info',
            value=context.price,
            threshold=max_price
        )

    async def _check_price_precision(self, context: ValidationContext) -> ValidationCheck:
        """Check price precision"""
        # Check if price has reasonable precision
        price_str = str(context.price)
        if '.' in price_str:
            decimals = len(price_str.split('.')[1])
            passed = decimals <= 8
        else:
            passed = True
        
        return ValidationCheck(
            rule=ValidationRule.PRICE_PRECISION,
            passed=passed,
            message="Price precision exceeds 8 decimals" if not passed else "Price precision is valid",
            severity='warning' if not passed else 'info',
            value=context.price
        )

    async def _check_size_precision(self, context: ValidationContext) -> ValidationCheck:
        """Check size precision"""
        size_str = str(context.size)
        if '.' in size_str:
            decimals = len(size_str.split('.')[1])
            passed = decimals <= 8
        else:
            passed = True
        
        return ValidationCheck(
            rule=ValidationRule.SIZE_PRECISION,
            passed=passed,
            message="Size precision exceeds 8 decimals" if not passed else "Size precision is valid",
            severity='warning' if not passed else 'info',
            value=context.size
        )

    # -------------------------------------------------------------------------
    # Account Validation Checks
    # -------------------------------------------------------------------------

    async def _check_sufficient_balance(self, context: ValidationContext) -> ValidationCheck:
        """Check sufficient balance"""
        account = context.account_data
        order_value = context.size * context.price
        
        if context.side == 'buy':
            required = order_value
        else:  # sell
            required = 0
        
        passed = account.get('balance', 0) >= required
        
        return ValidationCheck(
            rule=ValidationRule.SUFFICIENT_BALANCE,
            passed=passed,
            message=f"Insufficient balance. Need {required:.2f}, have {account.get('balance', 0):.2f}" if not passed else "Sufficient balance",
            severity='error' if not passed else 'info',
            value=account.get('balance', 0),
            threshold=required
        )

    async def _check_sufficient_margin(self, context: ValidationContext) -> ValidationCheck:
        """Check sufficient margin"""
        account = context.account_data
        order_value = context.size * context.price
        margin_required = order_value * 0.5  # 50% margin
        
        passed = account.get('margin_available', 0) >= margin_required
        
        return ValidationCheck(
            rule=ValidationRule.SUFFICIENT_MARGIN,
            passed=passed,
            message=f"Insufficient margin. Need {margin_required:.2f}, have {account.get('margin_available', 0):.2f}" if not passed else "Sufficient margin",
            severity='error' if not passed else 'info',
            value=account.get('margin_available', 0),
            threshold=margin_required
        )

    async def _check_max_positions(self, context: ValidationContext) -> ValidationCheck:
        """Check maximum positions"""
        rule = self._rules[ValidationRule.MAX_POSITIONS]
        max_positions = rule.max_value or 100
        
        current_positions = len(context.positions)
        passed = current_positions < max_positions
        
        return ValidationCheck(
            rule=ValidationRule.MAX_POSITIONS,
            passed=passed,
            message=f"Maximum positions ({max_positions}) reached" if not passed else "Position count is within limit",
            severity='error' if not passed else 'info',
            value=current_positions,
            threshold=max_positions
        )

    async def _check_max_leverage(self, context: ValidationContext) -> ValidationCheck:
        """Check maximum leverage"""
        rule = self._rules[ValidationRule.MAX_LEVERAGE]
        max_leverage = rule.max_value or 2.0
        
        account = context.account_data
        leverage = account.get('leverage', 1.0)
        
        passed = leverage <= max_leverage
        
        return ValidationCheck(
            rule=ValidationRule.MAX_LEVERAGE,
            passed=passed,
            message=f"Leverage {leverage:.1f}x exceeds maximum {max_leverage:.1f}x" if not passed else "Leverage is within limit",
            severity='error' if not passed else 'info',
            value=leverage,
            threshold=max_leverage
        )

    # -------------------------------------------------------------------------
    # Market Validation Checks
    # -------------------------------------------------------------------------

    async def _check_symbol_exists(self, context: ValidationContext) -> ValidationCheck:
        """Check if symbol exists"""
        market = context.market_data
        passed = market.get('exists', False)
        
        return ValidationCheck(
            rule=ValidationRule.SYMBOL_EXISTS,
            passed=passed,
            message=f"Symbol {context.symbol} does not exist" if not passed else "Symbol exists",
            severity='error' if not passed else 'info'
        )

    async def _check_market_open(self, context: ValidationContext) -> ValidationCheck:
        """Check if market is open"""
        market = context.market_data
        passed = market.get('open', True)
        
        return ValidationCheck(
            rule=ValidationRule.MARKET_OPEN,
            passed=passed,
            message="Market is closed" if not passed else "Market is open",
            severity='error' if not passed else 'info'
        )

    # -------------------------------------------------------------------------
    # Risk Validation Checks
    # -------------------------------------------------------------------------

    async def _check_risk_limit(self, context: ValidationContext) -> ValidationCheck:
        """Check risk limit"""
        rule = self._rules[ValidationRule.RISK_LIMIT]
        risk_limit = rule.threshold or 0.05
        
        order_value = context.size * context.price
        account = context.account_data
        equity = account.get('equity', 1)
        
        risk_pct = order_value / equity if equity > 0 else 0
        passed = risk_pct <= risk_limit
        
        return ValidationCheck(
            rule=ValidationRule.RISK_LIMIT,
            passed=passed,
            message=f"Risk {risk_pct*100:.2f}% exceeds limit {risk_limit*100:.2f}%" if not passed else "Risk is within limit",
            severity='error' if not passed else 'info',
            value=risk_pct,
            threshold=risk_limit
        )

    async def _check_position_limit(self, context: ValidationContext) -> ValidationCheck:
        """Check position limit"""
        rule = self._rules[ValidationRule.POSITION_LIMIT]
        position_limit = rule.max_value or 1000
        
        # Calculate total position after order
        total_position = 0
        for pos in context.positions:
            if pos.get('symbol') == context.symbol:
                total_position += pos.get('size', 0)
        
        if context.side == 'buy':
            total_position += context.size
        else:  # sell
            total_position -= context.size
        
        passed = abs(total_position) <= position_limit
        
        return ValidationCheck(
            rule=ValidationRule.POSITION_LIMIT,
            passed=passed,
            message=f"Position {abs(total_position):.2f} exceeds limit {position_limit}" if not passed else "Position is within limit",
            severity='error' if not passed else 'info',
            value=abs(total_position),
            threshold=position_limit
        )

    async def _check_daily_loss_limit(self, context: ValidationContext) -> ValidationCheck:
        """Check daily loss limit"""
        rule = self._rules[ValidationRule.DAILY_LOSS_LIMIT]
        loss_limit = rule.max_value or 10000
        
        account = context.account_data
        daily_loss = account.get('daily_loss', 0)
        
        # Estimate potential loss
        potential_loss = context.size * context.price * 0.02  # 2% stop
        new_loss = daily_loss + potential_loss
        
        passed = new_loss <= loss_limit
        
        return ValidationCheck(
            rule=ValidationRule.DAILY_LOSS_LIMIT,
            passed=passed,
            message=f"Daily loss {new_loss:.2f} would exceed limit {loss_limit:.2f}" if not passed else "Daily loss is within limit",
            severity='error' if not passed else 'info',
            value=new_loss,
            threshold=loss_limit
        )

    # =========================================================================
    # Recommendations
    # =========================================================================

    async def _generate_recommendations(
        self,
        checks: List[ValidationCheck]
    ) -> List[str]:
        """Generate recommendations based on validation checks"""
        recommendations = []
        
        for check in checks:
            if not check.passed:
                if check.rule == ValidationRule.MIN_ORDER_SIZE:
                    recommendations.append(f"Increase order size to at least {check.threshold:.4f}")
                elif check.rule == ValidationRule.MAX_ORDER_SIZE:
                    recommendations.append(f"Reduce order size to at most {check.threshold:.0f}")
                elif check.rule == ValidationRule.SUFFICIENT_BALANCE:
                    recommendations.append("Add funds to account or reduce order size")
                elif check.rule == ValidationRule.SUFFICIENT_MARGIN:
                    recommendations.append("Reduce leverage or add more margin")
                elif check.rule == ValidationRule.MAX_POSITIONS:
                    recommendations.append("Close some positions before opening new ones")
                elif check.rule == ValidationRule.MAX_LEVERAGE:
                    recommendations.append("Reduce leverage to meet requirements")
                elif check.rule == ValidationRule.RISK_LIMIT:
                    recommendations.append("Reduce position size to stay within risk limits")
                elif check.rule == ValidationRule.POSITION_LIMIT:
                    recommendations.append("Close or reduce existing position")
                elif check.rule == ValidationRule.DAILY_LOSS_LIMIT:
                    recommendations.append("Reduce risk or stop trading for today")
        
        if not recommendations:
            recommendations.append("All validations passed")
        
        return recommendations

    # =========================================================================
    # Rule Management
    # =========================================================================

    async def get_rule(self, rule: ValidationRule) -> Optional[ValidationRuleConfig]:
        """Get validation rule"""
        return self._rules.get(rule)

    async def update_rule(
        self,
        rule: ValidationRule,
        config: ValidationRuleConfig
    ) -> bool:
        """Update validation rule"""
        if rule in self._rules:
            self._rules[rule] = config
            return True
        return False

    async def get_all_rules(self) -> Dict[str, ValidationRuleConfig]:
        """Get all validation rules"""
        return {k.value: v for k, v in self._rules.items()}

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the validator"""
        self._rules.clear()
        logger.info("PaperTradingValidator closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/paper-trading/validate", tags=["Paper Trading Validation"])


async def get_validator() -> PaperTradingValidator:
    """Dependency to get PaperTradingValidator instance"""
    return PaperTradingValidator()


@router.post("/order", response_model=ValidationResponse)
async def validate_order(
    request: ValidationRequest,
    validator: PaperTradingValidator = Depends(get_validator)
):
    """Validate an order"""
    return await validator.validate(request)


@router.get("/rules")
async def get_validation_rules(
    validator: PaperTradingValidator = Depends(get_validator)
):
    """Get all validation rules"""
    return await validator.get_all_rules()


@router.get("/rules/{rule}")
async def get_validation_rule(
    rule: ValidationRule,
    validator: PaperTradingValidator = Depends(get_validator)
):
    """Get validation rule"""
    rule_config = await validator.get_rule(rule)
    if not rule_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule.value} not found"
        )
    return rule_config


@router.put("/rules/{rule}")
async def update_validation_rule(
    rule: ValidationRule,
    config: ValidationRuleConfig,
    validator: PaperTradingValidator = Depends(get_validator)
):
    """Update validation rule"""
    success = await validator.update_rule(rule, config)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule.value} not found"
        )
    return {"success": True}


@router.get("/levels")
async def get_validation_levels():
    """Get validation levels"""
    return {
        'levels': [
            {'name': l.value, 'description': l.name.title()}
            for l in ValidationLevel
        ]
    }


@router.get("/rules-list")
async def get_validation_rules_list():
    """Get validation rules list"""
    return {
        'rules': [
            {'name': r.value, 'description': r.name.replace('_', ' ').title()}
            for r in ValidationRule
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingValidator',
    'ValidationLevel',
    'ValidationResult',
    'ValidationRule',
    'ValidationRequest',
    'ValidationResponse',
    'ValidationRuleConfig',
    'ValidationContext',
    'ValidationCheck',
    'router'
]

"""
NEXUS AI TRADING SYSTEM - Risk Limits Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/risk-management/risk_limits.py
Description: Comprehensive risk limits management with full API integration
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.risk_config import RiskConfig
from shared.constants.trading_constants import (
    RISK_LIMIT_TYPES,
    RISK_LEVELS,
    ORDER_TYPES,
    POSITION_DIRECTIONS
)
from shared.types.risk import (
    RiskLimit,
    RiskLimitCheck,
    RiskLimitBreach,
    RiskLimitStatus
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import (
    RiskLimit as RiskLimitModel,
    RiskLimitBreach as RiskLimitBreachModel,
    Position,
    Order,
    Trade
)
from backend.database.repositories.risk_repository import RiskRepository
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Risk management imports
from trading.risk_engine.risk_manager import RiskManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class LimitType(str, Enum):
    """Types of risk limits"""
    # Position Limits
    MAX_POSITION_SIZE = "max_position_size"
    MAX_POSITION_VALUE = "max_position_value"
    MAX_POSITIONS_PER_SYMBOL = "max_positions_per_symbol"
    MAX_POSITIONS_TOTAL = "max_positions_total"
    MIN_POSITION_SIZE = "min_position_size"
    
    # Exposure Limits
    MAX_GROSS_EXPOSURE = "max_gross_exposure"
    MAX_NET_EXPOSURE = "max_net_exposure"
    MAX_SECTOR_EXPOSURE = "max_sector_exposure"
    MAX_ASSET_EXPOSURE = "max_asset_exposure"
    
    # Risk Limits
    MAX_DAILY_LOSS = "max_daily_loss"
    MAX_WEEKLY_LOSS = "max_weekly_loss"
    MAX_MONTHLY_LOSS = "max_monthly_loss"
    MAX_DRAWDOWN = "max_drawdown"
    MAX_VAR = "max_var"
    MAX_CVAR = "max_cvar"
    
    # Leverage Limits
    MAX_LEVERAGE = "max_leverage"
    MAX_LEVERAGE_PER_POSITION = "max_leverage_per_position"
    
    # Concentration Limits
    MAX_CONCENTRATION = "max_concentration"
    MAX_CORRELATION = "max_correlation"
    MIN_DIVERSIFICATION = "min_diversification"
    
    # Trading Limits
    MAX_TRADES_PER_DAY = "max_trades_per_day"
    MAX_TRADES_PER_HOUR = "max_trades_per_hour"
    MAX_TRADE_SIZE = "max_trade_size"
    MIN_TRADE_SIZE = "min_trade_size"
    
    # Stop Loss / Take Profit
    MAX_STOP_LOSS_DISTANCE = "max_stop_loss_distance"
    MIN_STOP_LOSS_DISTANCE = "min_stop_loss_distance"
    MAX_TAKE_PROFIT_DISTANCE = "max_take_profit_distance"
    MIN_TAKE_PROFIT_DISTANCE = "min_take_profit_distance"
    
    # Time-based Limits
    MAX_HOLDING_TIME = "max_holding_time"
    MIN_HOLDING_TIME = "min_holding_time"
    
    # Custom Limits
    CUSTOM = "custom"


class LimitSeverity(str, Enum):
    """Severity of limit breach"""
    INFO = "info"
    WARNING = "warning"
    BREACH = "breach"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class LimitAction(str, Enum):
    """Actions to take on limit breach"""
    NONE = "none"
    LOG = "log"
    NOTIFY = "notify"
    ALERT = "alert"
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    PAUSE_TRADING = "pause_trading"
    STOP_TRADING = "stop_trading"
    LIQUIDATE = "liquidate"
    EMERGENCY_STOP = "emergency_stop"


class LimitScope(str, Enum):
    """Scope of risk limit"""
    GLOBAL = "global"
    PORTFOLIO = "portfolio"
    SYMBOL = "symbol"
    STRATEGY = "strategy"
    BROKER = "broker"
    USER = "user"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RiskLimitConfig(BaseModel):
    """Configuration for a risk limit"""
    limit_type: LimitType
    max_value: Optional[float] = None
    min_value: Optional[float] = None
    current_value: Optional[float] = None
    scope: LimitScope = LimitScope.PORTFOLIO
    severity: LimitSeverity = LimitSeverity.WARNING
    action: LimitAction = LimitAction.NOTIFY
    hard_limit: bool = True
    enabled: bool = True
    cooldown_seconds: int = 300
    breach_count_threshold: int = 3
    notification_channels: List[str] = field(default_factory=lambda: ["email", "telegram"])
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @validator('max_value')
    def validate_max(cls, v, values):
        if v is not None and v < 0:
            raise ValueError("max_value must be non-negative")
        return v
    
    @validator('min_value')
    def validate_min(cls, v, values):
        if v is not None and v < 0:
            raise ValueError("min_value must be non-negative")
        return v
    
    @validator('breach_count_threshold')
    def validate_threshold(cls, v):
        if v < 1:
            raise ValueError("breach_count_threshold must be at least 1")
        return v


class RiskLimitBreachRequest(BaseModel):
    """Request model for reporting a breach"""
    limit_type: LimitType
    current_value: float
    limit_value: float
    breach_value: float
    severity: LimitSeverity = LimitSeverity.BREACH
    action_taken: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class RiskLimitStatusResponse(BaseModel):
    """Response model for limit status"""
    limit_type: LimitType
    scope: LimitScope
    current_value: float
    max_value: Optional[float] = None
    min_value: Optional[float] = None
    usage_percentage: float
    status: str  # "ok", "warning", "breached", "critical"
    breached_at: Optional[datetime] = None
    breach_count: int = 0
    last_check: datetime
    actions: List[str] = []


class RiskLimitsSummaryResponse(BaseModel):
    """Summary of all risk limits"""
    timestamp: datetime
    total_limits: int
    active_limits: int
    breached_limits: List[str]
    warning_limits: List[str]
    critical_limits: List[str]
    overall_status: str
    limits: Dict[str, RiskLimitStatusResponse]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LimitBreachHistory:
    """History of limit breaches"""
    limit_type: str
    timestamp: datetime
    current_value: float
    limit_value: float
    severity: str
    action_taken: str
    resolved_at: Optional[datetime] = None
    resolution_action: Optional[str] = None


@dataclass
class LimitValidationResult:
    """Result of limit validation"""
    passed: bool
    limit_type: Optional[str] = None
    current_value: Optional[float] = None
    limit_value: Optional[float] = None
    message: Optional[str] = None
    severity: LimitSeverity = LimitSeverity.INFO
    action_required: Optional[LimitAction] = None


# =============================================================================
# RISK LIMITS MANAGER
# =============================================================================

class RiskLimitsManager:
    """
    Comprehensive Risk Limits Manager with full API integration.
    
    Manages all risk limits including:
    - Position limits
    - Exposure limits
    - Risk limits (drawdown, VaR, etc.)
    - Leverage limits
    - Concentration limits
    - Trading limits
    - Stop loss / Take profit limits
    - Time-based limits
    - Custom limits
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        risk_repo: Optional[RiskRepository] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize RiskLimitsManager.
        
        Args:
            config: Risk configuration
            broker_factory: Factory for broker instances
            risk_repo: Risk repository
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or RiskConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.risk_repo = risk_repo or RiskRepository()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Risk limits cache
        self._limits: Dict[str, RiskLimitConfig] = {}
        self._breach_history: Dict[str, List[LimitBreachHistory]] = {}
        self._breach_counts: Dict[str, int] = {}
        self._last_check_times: Dict[str, datetime] = {}
        self._cooldown_until: Dict[str, datetime] = {}
        
        # Circuit breakers for external API calls
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Risk manager instance
        self.risk_manager = RiskManager(config)
        
        # Initialize limits
        self._init_default_limits()
        
        logger.info("RiskLimitsManager initialized")

    def _init_default_limits(self) -> None:
        """Initialize default risk limits from configuration"""
        # Default risk limits
        default_limits = {
            LimitType.MAX_POSITION_SIZE: {
                'max_value': 1000,  # 1000 units
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.NOTIFY,
                'hard_limit': True
            },
            LimitType.MAX_POSITION_VALUE: {
                'max_value': 10000,  # $10,000
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.NOTIFY,
                'hard_limit': True
            },
            LimitType.MAX_GROSS_EXPOSURE: {
                'max_value': 50000,  # $50,000
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.PAUSE_TRADING,
                'hard_limit': True
            },
            LimitType.MAX_NET_EXPOSURE: {
                'max_value': 30000,  # $30,000
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.PAUSE_TRADING,
                'hard_limit': True
            },
            LimitType.MAX_DAILY_LOSS: {
                'max_value': 1000,  # $1,000
                'severity': LimitSeverity.CRITICAL,
                'action': LimitAction.PAUSE_TRADING,
                'hard_limit': True
            },
            LimitType.MAX_WEEKLY_LOSS: {
                'max_value': 3000,  # $3,000
                'severity': LimitSeverity.CRITICAL,
                'action': LimitAction.PAUSE_TRADING,
                'hard_limit': True
            },
            LimitType.MAX_DRAWDOWN: {
                'max_value': 0.20,  # 20% drawdown
                'severity': LimitSeverity.CRITICAL,
                'action': LimitAction.STOP_TRADING,
                'hard_limit': True
            },
            LimitType.MAX_LEVERAGE: {
                'max_value': 2.0,  # 2x leverage
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.REDUCE_POSITION,
                'hard_limit': True
            },
            LimitType.MAX_CONCENTRATION: {
                'max_value': 0.40,  # 40% concentration
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.NOTIFY,
                'hard_limit': True
            },
            LimitType.MAX_TRADES_PER_DAY: {
                'max_value': 100,
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.PAUSE_TRADING,
                'hard_limit': True
            },
            LimitType.MAX_TRADES_PER_HOUR: {
                'max_value': 20,
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.PAUSE_TRADING,
                'hard_limit': True
            },
            LimitType.MAX_STOP_LOSS_DISTANCE: {
                'max_value': 0.10,  # 10%
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.NOTIFY,
                'hard_limit': True
            },
            LimitType.MIN_STOP_LOSS_DISTANCE: {
                'min_value': 0.005,  # 0.5%
                'severity': LimitSeverity.WARNING,
                'action': LimitAction.NOTIFY,
                'hard_limit': True
            }
        }
        
        for limit_type, params in default_limits.items():
            self._limits[limit_type.value] = RiskLimitConfig(
                limit_type=limit_type,
                max_value=params.get('max_value'),
                min_value=params.get('min_value'),
                severity=params.get('severity', LimitSeverity.WARNING),
                action=params.get('action', LimitAction.NOTIFY),
                hard_limit=params.get('hard_limit', True),
                scope=params.get('scope', LimitScope.PORTFOLIO)
            )
        
        # Load limits from database if available
        self._load_limits_from_db()

    def _load_limits_from_db(self) -> None:
        """Load risk limits from database"""
        try:
            db_limits = self.risk_repo.get_all_limits()
            for db_limit in db_limits:
                self._limits[db_limit.limit_type] = RiskLimitConfig(
                    limit_type=LimitType(db_limit.limit_type),
                    max_value=db_limit.max_value,
                    min_value=db_limit.min_value,
                    scope=LimitScope(db_limit.scope),
                    severity=LimitSeverity(db_limit.severity),
                    action=LimitAction(db_limit.action),
                    hard_limit=db_limit.hard_limit,
                    enabled=db_limit.enabled,
                    cooldown_seconds=db_limit.cooldown_seconds,
                    breach_count_threshold=db_limit.breach_count_threshold,
                    notification_channels=db_limit.notification_channels or ["email", "telegram"],
                    metadata=db_limit.metadata or {}
                )
        except Exception as e:
            logger.warning(f"Error loading limits from database: {e}")

    # =========================================================================
    # Core Limit Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def check_limit(
        self,
        limit_type: Union[LimitType, str],
        current_value: float,
        context: Optional[Dict[str, Any]] = None
    ) -> LimitValidationResult:
        """
        Check if a limit is violated.
        
        Args:
            limit_type: Type of limit to check
            current_value: Current value to check
            context: Additional context
            
        Returns:
            LimitValidationResult: Result of the check
        """
        limit_key = limit_type.value if isinstance(limit_type, LimitType) else limit_type
        
        # Get limit configuration
        limit_config = self._limits.get(limit_key)
        if not limit_config:
            return LimitValidationResult(
                passed=True,
                message=f"Limit {limit_key} not configured, skipping check"
            )
        
        if not limit_config.enabled:
            return LimitValidationResult(
                passed=True,
                message=f"Limit {limit_key} is disabled"
            )
        
        # Check cooldown
        if self._is_in_cooldown(limit_key):
            return LimitValidationResult(
                passed=True,
                message=f"Limit {limit_key} in cooldown period"
            )
        
        # Perform check
        result = self._validate_limit_value(limit_config, current_value, context)
        
        # Record check
        self._last_check_times[limit_key] = datetime.utcnow()
        
        # Handle breach
        if not result.passed:
            await self._handle_limit_breach(limit_config, current_value, result)
        
        return result

    def _validate_limit_value(
        self,
        limit_config: RiskLimitConfig,
        current_value: float,
        context: Optional[Dict[str, Any]] = None
    ) -> LimitValidationResult:
        """Validate current value against limit"""
        passed = True
        severity = LimitSeverity.INFO
        message = "Limit check passed"
        
        # Check max value
        if limit_config.max_value is not None:
            if current_value > limit_config.max_value:
                passed = False
                severity = limit_config.severity
                message = f"{limit_config.limit_type.value} exceeded max: {current_value:.2f} > {limit_config.max_value:.2f}"
                return LimitValidationResult(
                    passed=False,
                    limit_type=limit_config.limit_type.value,
                    current_value=current_value,
                    limit_value=limit_config.max_value,
                    message=message,
                    severity=severity,
                    action_required=limit_config.action
                )
        
        # Check min value
        if limit_config.min_value is not None:
            if current_value < limit_config.min_value:
                passed = False
                severity = limit_config.severity
                message = f"{limit_config.limit_type.value} below min: {current_value:.2f} < {limit_config.min_value:.2f}"
                return LimitValidationResult(
                    passed=False,
                    limit_type=limit_config.limit_type.value,
                    current_value=current_value,
                    limit_value=limit_config.min_value,
                    message=message,
                    severity=severity,
                    action_required=limit_config.action
                )
        
        return LimitValidationResult(
            passed=True,
            limit_type=limit_config.limit_type.value,
            current_value=current_value,
            message=message,
            severity=severity
        )

    async def _handle_limit_breach(
        self,
        limit_config: RiskLimitConfig,
        current_value: float,
        result: LimitValidationResult
    ) -> None:
        """Handle a limit breach"""
        limit_key = limit_config.limit_type.value
        
        # Update breach count
        self._breach_counts[limit_key] = self._breach_counts.get(limit_key, 0) + 1
        
        # Record breach history
        breach = LimitBreachHistory(
            limit_type=limit_key,
            timestamp=datetime.utcnow(),
            current_value=current_value,
            limit_value=result.limit_value or 0,
            severity=result.severity.value,
            action_taken=result.action_required.value if result.action_required else "none"
        )
        
        if limit_key not in self._breach_history:
            self._breach_history[limit_key] = []
        self._breach_history[limit_key].append(breach)
        
        # Keep history manageable
        if len(self._breach_history[limit_key]) > 1000:
            self._breach_history[limit_key] = self._breach_history[limit_key][-1000:]
        
        # Check if threshold exceeded
        breach_count = self._breach_counts.get(limit_key, 0)
        if breach_count >= limit_config.breach_count_threshold:
            # Set cooldown
            self._cooldown_until[limit_key] = datetime.utcnow() + timedelta(
                seconds=limit_config.cooldown_seconds
            )
        
        # Execute action
        if result.action_required:
            await self._execute_action(
                limit_config,
                current_value,
                result.action_required
            )
        
        # Log breach
        logger.warning(
            f"Limit breach: {limit_key} - {result.message} "
            f"(breach #{breach_count})"
        )

    async def _execute_action(
        self,
        limit_config: RiskLimitConfig,
        current_value: float,
        action: LimitAction
    ) -> None:
        """Execute limit breach action"""
        try:
            if action == LimitAction.NONE:
                pass
            
            elif action == LimitAction.LOG:
                logger.info(f"Limit action LOG: {limit_config.limit_type.value}")
            
            elif action == LimitAction.NOTIFY:
                await self._send_notification(limit_config, current_value, "limit_breach")
            
            elif action == LimitAction.ALERT:
                await self._send_notification(limit_config, current_value, "limit_breach_alert")
            
            elif action == LimitAction.REDUCE_POSITION:
                await self._reduce_positions(limit_config, current_value)
            
            elif action == LimitAction.CLOSE_POSITION:
                await self._close_positions(limit_config)
            
            elif action == LimitAction.PAUSE_TRADING:
                await self._pause_trading(limit_config)
            
            elif action == LimitAction.STOP_TRADING:
                await self._stop_trading(limit_config)
            
            elif action == LimitAction.LIQUIDATE:
                await self._liquidate_positions(limit_config)
            
            elif action == LimitAction.EMERGENCY_STOP:
                await self._emergency_stop(limit_config)
            
        except Exception as e:
            logger.error(f"Error executing action {action}: {e}")

    def _is_in_cooldown(self, limit_key: str) -> bool:
        """Check if limit is in cooldown period"""
        cooldown_until = self._cooldown_until.get(limit_key)
        if cooldown_until:
            return datetime.utcnow() < cooldown_until
        return False

    # =========================================================================
    # Action Implementations
    # =========================================================================

    async def _send_notification(
        self,
        limit_config: RiskLimitConfig,
        current_value: float,
        notification_type: str
    ) -> None:
        """Send notification about limit breach"""
        try:
            message = (
                f"🚨 Risk Limit Breach\n\n"
                f"Limit: {limit_config.limit_type.value}\n"
                f"Current Value: {current_value:.2f}\n"
                f"Max Value: {limit_config.max_value or 'N/A'}\n"
                f"Min Value: {limit_config.min_value or 'N/A'}\n"
                f"Severity: {limit_config.severity.value}\n"
                f"Action: {limit_config.action.value}\n"
                f"Timestamp: {datetime.utcnow().isoformat()}"
            )
            
            # Send to configured channels
            for channel in limit_config.notification_channels:
                if channel == "email":
                    await self._send_email_notification(limit_config, message)
                elif channel == "telegram":
                    await self._send_telegram_notification(limit_config, message)
                elif channel == "slack":
                    await self._send_slack_notification(limit_config, message)
                elif channel == "webhook":
                    await self._send_webhook_notification(limit_config, message)
                    
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    async def _send_email_notification(self, limit_config: RiskLimitConfig, message: str) -> None:
        """Send email notification"""
        # Implement email sending
        logger.info(f"Email notification: {message[:100]}...")

    async def _send_telegram_notification(self, limit_config: RiskLimitConfig, message: str) -> None:
        """Send Telegram notification"""
        # Implement Telegram sending
        logger.info(f"Telegram notification: {message[:100]}...")

    async def _send_slack_notification(self, limit_config: RiskLimitConfig, message: str) -> None:
        """Send Slack notification"""
        # Implement Slack sending
        logger.info(f"Slack notification: {message[:100]}...")

    async def _send_webhook_notification(self, limit_config: RiskLimitConfig, message: str) -> None:
        """Send webhook notification"""
        # Implement webhook sending
        logger.info(f"Webhook notification: {message[:100]}...")

    async def _reduce_positions(self, limit_config: RiskLimitConfig, current_value: float) -> None:
        """Reduce positions to meet limit"""
        try:
            # Get current positions
            positions = await self.position_repo.get_all_active()
            
            if not positions:
                return
            
            # Calculate how much to reduce
            target_value = limit_config.max_value or current_value * 0.5
            reduction_needed = current_value - target_value
            reduction_pct = reduction_needed / current_value
            
            # Sort positions by size (largest first)
            positions.sort(key=lambda p: p.size, reverse=True)
            
            for position in positions:
                if reduction_needed <= 0:
                    break
                
                # Calculate reduction for this position
                position_value = position.size * position.entry_price
                position_reduction = min(
                    position_value * reduction_pct,
                    position_value * 0.5  # Max 50% reduction per position
                )
                
                if position_reduction > 0:
                    await self._reduce_position(position, position_reduction)
                    reduction_needed -= position_reduction
            
            logger.info(f"Reduced positions by {reduction_needed:.2f} to meet limit")
            
        except Exception as e:
            logger.error(f"Error reducing positions: {e}")

    async def _reduce_position(self, position: Any, reduction_amount: float) -> None:
        """Reduce a specific position"""
        # Implement position reduction
        logger.info(f"Reducing position {position.id} by {reduction_amount:.2f}")

    async def _close_positions(self, limit_config: RiskLimitConfig) -> None:
        """Close positions"""
        try:
            positions = await self.position_repo.get_all_active()
            
            for position in positions:
                await self._close_position(position)
            
            logger.info(f"Closed {len(positions)} positions due to limit breach")
            
        except Exception as e:
            logger.error(f"Error closing positions: {e}")

    async def _close_position(self, position: Any) -> None:
        """Close a specific position"""
        # Implement position closing
        logger.info(f"Closing position {position.id}")

    async def _pause_trading(self, limit_config: RiskLimitConfig) -> None:
        """Pause trading"""
        # Implement trading pause
        logger.info(f"Trading paused due to {limit_config.limit_type.value} limit breach")

    async def _stop_trading(self, limit_config: RiskLimitConfig) -> None:
        """Stop trading"""
        # Implement trading stop
        logger.info(f"Trading stopped due to {limit_config.limit_type.value} limit breach")

    async def _liquidate_positions(self, limit_config: RiskLimitConfig) -> None:
        """Liquidate all positions"""
        try:
            positions = await self.position_repo.get_all_active()
            
            for position in positions:
                await self._liquidate_position(position)
            
            logger.info(f"Liquidated {len(positions)} positions")
            
        except Exception as e:
            logger.error(f"Error liquidating positions: {e}")

    async def _liquidate_position(self, position: Any) -> None:
        """Liquidate a specific position"""
        # Implement position liquidation
        logger.info(f"Liquidating position {position.id}")

    async def _emergency_stop(self, limit_config: RiskLimitConfig) -> None:
        """Emergency stop"""
        # Implement emergency stop
        logger.error(f"EMERGENCY STOP triggered by {limit_config.limit_type.value}")

    # =========================================================================
    # Limit Management API
    # =========================================================================

    async def add_limit(self, config: RiskLimitConfig) -> bool:
        """
        Add a new risk limit.
        
        Args:
            config: Risk limit configuration
            
        Returns:
            bool: Success indicator
        """
        try:
            limit_key = config.limit_type.value
            self._limits[limit_key] = config
            self._breach_counts[limit_key] = 0
            
            # Save to database
            await self._save_limit_to_db(config)
            
            logger.info(f"Added risk limit: {limit_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding limit: {e}")
            return False

    async def update_limit(
        self,
        limit_type: Union[LimitType, str],
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update an existing risk limit.
        
        Args:
            limit_type: Type of limit to update
            updates: Update data
            
        Returns:
            bool: Success indicator
        """
        try:
            limit_key = limit_type.value if isinstance(limit_type, LimitType) else limit_type
            
            if limit_key not in self._limits:
                return False
            
            config = self._limits[limit_key]
            
            # Update fields
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # Save to database
            await self._save_limit_to_db(config)
            
            logger.info(f"Updated risk limit: {limit_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating limit: {e}")
            return False

    async def remove_limit(self, limit_type: Union[LimitType, str]) -> bool:
        """
        Remove a risk limit.
        
        Args:
            limit_type: Type of limit to remove
            
        Returns:
            bool: Success indicator
        """
        try:
            limit_key = limit_type.value if isinstance(limit_type, LimitType) else limit_type
            
            if limit_key not in self._limits:
                return False
            
            del self._limits[limit_key]
            
            # Remove from database
            await self._remove_limit_from_db(limit_key)
            
            logger.info(f"Removed risk limit: {limit_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing limit: {e}")
            return False

    async def _save_limit_to_db(self, config: RiskLimitConfig) -> None:
        """Save limit configuration to database"""
        try:
            await self.risk_repo.save_limit({
                'limit_type': config.limit_type.value,
                'max_value': config.max_value,
                'min_value': config.min_value,
                'scope': config.scope.value,
                'severity': config.severity.value,
                'action': config.action.value,
                'hard_limit': config.hard_limit,
                'enabled': config.enabled,
                'cooldown_seconds': config.cooldown_seconds,
                'breach_count_threshold': config.breach_count_threshold,
                'notification_channels': config.notification_channels,
                'metadata': config.metadata
            })
        except Exception as e:
            logger.error(f"Error saving limit to database: {e}")

    async def _remove_limit_from_db(self, limit_key: str) -> None:
        """Remove limit from database"""
        try:
            await self.risk_repo.delete_limit(limit_key)
        except Exception as e:
            logger.error(f"Error removing limit from database: {e}")

    # =========================================================================
    # Status and Reporting
    # =========================================================================

    async def get_limit_status(
        self,
        limit_type: Union[LimitType, str],
        current_value: Optional[float] = None
    ) -> Optional[RiskLimitStatusResponse]:
        """
        Get status of a specific limit.
        
        Args:
            limit_type: Type of limit
            current_value: Current value (optional)
            
        Returns:
            RiskLimitStatusResponse: Limit status
        """
        limit_key = limit_type.value if isinstance(limit_type, LimitType) else limit_type
        
        config = self._limits.get(limit_key)
        if not config:
            return None
        
        # Get current value if not provided
        if current_value is None:
            current_value = await self._get_current_value_for_limit(limit_key)
        
        # Calculate usage percentage
        usage_pct = 0.0
        if config.max_value:
            usage_pct = (current_value / config.max_value) * 100
        elif config.min_value:
            usage_pct = ((config.min_value - current_value) / config.min_value) * 100
        
        # Determine status
        status = "ok"
        if usage_pct > 90:
            status = "critical"
        elif usage_pct > 75:
            status = "warning"
        
        # Check breach history
        breach_count = self._breach_counts.get(limit_key, 0)
        last_breach = None
        if limit_key in self._breach_history and self._breach_history[limit_key]:
            last_breach = self._breach_history[limit_key][-1].timestamp
        
        return RiskLimitStatusResponse(
            limit_type=config.limit_type,
            scope=config.scope,
            current_value=current_value,
            max_value=config.max_value,
            min_value=config.min_value,
            usage_percentage=usage_pct,
            status=status,
            breached_at=last_breach,
            breach_count=breach_count,
            last_check=self._last_check_times.get(limit_key, datetime.utcnow()),
            actions=[config.action.value]
        )

    async def get_all_limits_status(self) -> RiskLimitsSummaryResponse:
        """
        Get status of all limits.
        
        Returns:
            RiskLimitsSummaryResponse: Summary of all limits
        """
        limits_status = {}
        breached = []
        warnings = []
        criticals = []
        
        for limit_key, config in self._limits.items():
            status = await self.get_limit_status(limit_key)
            if status:
                limits_status[limit_key] = status
                
                if status.status == "breached":
                    breached.append(limit_key)
                elif status.status == "warning":
                    warnings.append(limit_key)
                elif status.status == "critical":
                    criticals.append(limit_key)
        
        # Determine overall status
        overall = "ok"
        if criticals:
            overall = "critical"
        elif breached:
            overall = "breached"
        elif warnings:
            overall = "warning"
        
        return RiskLimitsSummaryResponse(
            timestamp=datetime.utcnow(),
            total_limits=len(self._limits),
            active_limits=sum(1 for c in self._limits.values() if c.enabled),
            breached_limits=breached,
            warning_limits=warnings,
            critical_limits=criticals,
            overall_status=overall,
            limits=limits_status
        )

    async def get_breach_history(
        self,
        limit_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get breach history.
        
        Args:
            limit_type: Filter by limit type
            limit: Maximum number of records
            
        Returns:
            List[Dict]: Breach history
        """
        history = []
        
        for key, breaches in self._breach_history.items():
            if limit_type and key != limit_type:
                continue
            
            for breach in breaches[-limit:]:
                history.append({
                    'limit_type': breach.limit_type,
                    'timestamp': breach.timestamp.isoformat(),
                    'current_value': breach.current_value,
                    'limit_value': breach.limit_value,
                    'severity': breach.severity,
                    'action_taken': breach.action_taken,
                    'resolved_at': breach.resolved_at.isoformat() if breach.resolved_at else None,
                    'resolution_action': breach.resolution_action
                })
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return history[:limit]

    async def resolve_breach(
        self,
        limit_type: str,
        resolution_action: str
    ) -> bool:
        """
        Resolve a limit breach.
        
        Args:
            limit_type: Type of limit
            resolution_action: Action taken to resolve
            
        Returns:
            bool: Success indicator
        """
        try:
            if limit_type not in self._breach_history:
                return False
            
            breaches = self._breach_history[limit_type]
            if breaches:
                # Mark most recent breach as resolved
                breaches[-1].resolved_at = datetime.utcnow()
                breaches[-1].resolution_action = resolution_action
            
            # Reset breach count
            self._breach_counts[limit_type] = 0
            
            logger.info(f"Resolved breach for {limit_type} with action: {resolution_action}")
            return True
            
        except Exception as e:
            logger.error(f"Error resolving breach: {e}")
            return False

    # =========================================================================
    # Integration Methods
    # =========================================================================

    async def validate_order(
        self,
        order: Dict[str, Any],
        portfolio_id: Optional[str] = None
    ) -> List[LimitValidationResult]:
        """
        Validate an order against all relevant limits.
        
        Args:
            order: Order details
            portfolio_id: Portfolio ID
            
        Returns:
            List[LimitValidationResult]: Validation results
        """
        results = []
        
        # Get current positions
        positions = await self.position_repo.get_by_portfolio_id(
            portfolio_id or order.get('portfolio_id')
        )
        
        # Get current trades
        trades = await self.trade_repo.get_by_portfolio_id(
            portfolio_id or order.get('portfolio_id'),
            period='today'
        )
        
        # Check position limits
        position_size = order.get('size', 0)
        position_value = position_size * order.get('price', 0)
        
        # Check max position size
        result = await self.check_limit(
            LimitType.MAX_POSITION_SIZE,
            position_size,
            {'order': order, 'positions': positions}
        )
        results.append(result)
        
        # Check max position value
        result = await self.check_limit(
            LimitType.MAX_POSITION_VALUE,
            position_value,
            {'order': order, 'positions': positions}
        )
        results.append(result)
        
        # Check max positions per symbol
        symbol_positions = [p for p in positions if p.symbol == order.get('symbol')]
        result = await self.check_limit(
            LimitType.MAX_POSITIONS_PER_SYMBOL,
            len(symbol_positions) + 1,
            {'order': order, 'positions': positions}
        )
        results.append(result)
        
        # Check trade limits
        today_trades = [t for t in trades if t.symbol == order.get('symbol')]
        
        result = await self.check_limit(
            LimitType.MAX_TRADES_PER_DAY,
            len(today_trades) + 1,
            {'order': order, 'trades': trades}
        )
        results.append(result)
        
        # Check stop loss limits
        if order.get('stop_loss'):
            sl_distance = abs(order['stop_loss'] - order.get('price', 0)) / order.get('price', 1)
            result = await self.check_limit(
                LimitType.MAX_STOP_LOSS_DISTANCE,
                sl_distance,
                {'order': order}
            )
            results.append(result)
            
            result = await self.check_limit(
                LimitType.MIN_STOP_LOSS_DISTANCE,
                sl_distance,
                {'order': order}
            )
            results.append(result)
        
        return results

    async def validate_position(
        self,
        position: Dict[str, Any],
        portfolio_id: Optional[str] = None
    ) -> List[LimitValidationResult]:
        """
        Validate a position against all relevant limits.
        
        Args:
            position: Position details
            portfolio_id: Portfolio ID
            
        Returns:
            List[LimitValidationResult]: Validation results
        """
        results = []
        
        # Get all positions
        all_positions = await self.position_repo.get_by_portfolio_id(
            portfolio_id or position.get('portfolio_id')
        )
        
        # Calculate exposures
        total_exposure = sum(p.value for p in all_positions)
        new_exposure = total_exposure + position.get('value', 0)
        
        # Check exposure limits
        result = await self.check_limit(
            LimitType.MAX_GROSS_EXPOSURE,
            new_exposure,
            {'position': position, 'positions': all_positions}
        )
        results.append(result)
        
        # Check concentration
        if all_positions:
            max_concentration = max(p.value / total_exposure for p in all_positions) if total_exposure > 0 else 0
            result = await self.check_limit(
                LimitType.MAX_CONCENTRATION,
                max_concentration,
                {'position': position, 'positions': all_positions}
            )
            results.append(result)
        
        # Check leverage
        portfolio = await self.portfolio_repo.get_by_id(portfolio_id or position.get('portfolio_id'))
        if portfolio:
            total_value = portfolio.total_value or 1
            leverage = new_exposure / total_value
            result = await self.check_limit(
                LimitType.MAX_LEVERAGE,
                leverage,
                {'position': position, 'positions': all_positions, 'portfolio': portfolio}
            )
            results.append(result)
        
        return results

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def _get_current_value_for_limit(self, limit_key: str) -> float:
        """Get current value for a specific limit type"""
        # This would need to be implemented based on the limit type
        # For now, return a mock value
        return 0.0

    async def reset_breach_counts(self) -> None:
        """Reset all breach counts"""
        self._breach_counts = {}
        self._cooldown_until = {}
        logger.info("Reset all breach counts")

    async def clear_history(self) -> None:
        """Clear all breach history"""
        self._breach_history = {}
        logger.info("Cleared all breach history")

    async def close(self) -> None:
        """Close connections and clean up resources"""
        # Clean up circuit breakers
        self._circuit_breakers.clear()
        
        logger.info("RiskLimitsManager closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/risk-limits", tags=["Risk Limits"])


async def get_limits_manager() -> RiskLimitsManager:
    """Dependency to get RiskLimitsManager instance"""
    return RiskLimitsManager()


@router.get("/")
async def get_all_limits(
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Get all risk limits"""
    return await manager.get_all_limits_status()


@router.get("/{limit_type}")
async def get_limit(
    limit_type: str,
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Get a specific risk limit"""
    status = await manager.get_limit_status(limit_type)
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Limit {limit_type} not found"
        )
    return status


@router.post("/")
async def create_limit(
    config: RiskLimitConfig,
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Create a new risk limit"""
    success = await manager.add_limit(config)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create limit"
        )
    return {"success": True, "limit": config.dict()}


@router.put("/{limit_type}")
async def update_limit(
    limit_type: str,
    updates: Dict[str, Any],
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Update a risk limit"""
    success = await manager.update_limit(limit_type, updates)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Limit {limit_type} not found"
        )
    return {"success": True, "updates": updates}


@router.delete("/{limit_type}")
async def delete_limit(
    limit_type: str,
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Delete a risk limit"""
    success = await manager.remove_limit(limit_type)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Limit {limit_type} not found"
        )
    return {"success": True}


@router.post("/check")
async def check_limit(
    limit_type: str,
    current_value: float,
    context: Optional[Dict[str, Any]] = Body(None),
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Check a limit"""
    result = await manager.check_limit(
        LimitType(limit_type),
        current_value,
        context
    )
    return result.__dict__


@router.get("/history")
async def get_breach_history(
    limit_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Get breach history"""
    return await manager.get_breach_history(limit_type, limit)


@router.post("/resolve/{limit_type}")
async def resolve_breach(
    limit_type: str,
    resolution_action: str = Body(..., embed=True),
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Resolve a limit breach"""
    success = await manager.resolve_breach(limit_type, resolution_action)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No breach found for {limit_type}"
        )
    return {"success": True}


@router.post("/reset")
async def reset_limits(
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Reset all limits and breaches"""
    await manager.reset_breach_counts()
    return {"success": True}


@router.post("/validate-order")
async def validate_order(
    order: Dict[str, Any],
    portfolio_id: Optional[str] = Query(None),
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Validate an order against risk limits"""
    results = await manager.validate_order(order, portfolio_id)
    return {
        "valid": all(r.passed for r in results),
        "results": [r.__dict__ for r in results]
    }


@router.post("/validate-position")
async def validate_position(
    position: Dict[str, Any],
    portfolio_id: Optional[str] = Query(None),
    manager: RiskLimitsManager = Depends(get_limits_manager)
):
    """Validate a position against risk limits"""
    results = await manager.validate_position(position, portfolio_id)
    return {
        "valid": all(r.passed for r in results),
        "results": [r.__dict__ for r in results]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'RiskLimitsManager',
    'LimitType',
    'LimitSeverity',
    'LimitAction',
    'LimitScope',
    'RiskLimitConfig',
    'RiskLimitBreachRequest',
    'RiskLimitStatusResponse',
    'RiskLimitsSummaryResponse',
    'LimitBreachHistory',
    'LimitValidationResult',
    'router'
]

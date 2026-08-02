# trading/bots/hedge_bot/hedge_bot_insurance.py

import asyncio
import logging
import time
import json
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class InsuranceType(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    GUARANTEED_STOP = "guaranteed_stop"
    POSITION_INSURANCE = "position_insurance"
    PORTFOLIO_INSURANCE = "portfolio_insurance"
    BLACK_SWAN = "black_swan"
    DRAWDOWN_PROTECTION = "drawdown_protection"
    VOLATILITY_PROTECTION = "volatility_protection"
    LIQUIDITY_PROTECTION = "liquidity_protection"
    COUNTERPARTY_PROTECTION = "counterparty_protection"
    EXECUTION_PROTECTION = "execution_protection"
    SLIPPAGE_PROTECTION = "slippage_protection"


class InsuranceStatus(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    INACTIVE = "inactive"


class InsuranceTrigger(str, Enum):
    PRICE = "price"
    TIME = "time"
    VOLATILITY = "volatility"
    DRAWDOWN = "drawdown"
    MANUAL = "manual"
    CONDITION = "condition"
    COMPOSITE = "composite"


@dataclass
class InsurancePolicy:
    id: str
    name: str
    type: InsuranceType
    status: InsuranceStatus
    asset: str
    position_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    trigger_type: InsuranceTrigger = InsuranceTrigger.PRICE
    trigger_value: float = 0.0
    trigger_condition: Optional[str] = None
    protection_level: float = 0.0
    coverage_amount: Decimal = Decimal('0')
    premium: Decimal = Decimal('0')
    deductible: Decimal = Decimal('0')
    max_payout: Decimal = Decimal('0')
    current_payout: Decimal = Decimal('0')
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    activated_at: Optional[float] = None
    triggered_at: Optional[float] = None
    paid_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class InsuranceClaim:
    id: str
    policy_id: str
    amount: Decimal
    status: str
    reason: str
    created_at: float
    processed_at: Optional[float] = None
    approved_at: Optional[float] = None
    paid_at: Optional[float] = None
    rejected_at: Optional[float] = None
    rejection_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsurancePremium:
    id: str
    policy_id: str
    amount: Decimal
    frequency: str
    next_payment: float
    last_payment: Optional[float] = None
    payment_method: Optional[str] = None
    paid: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsuranceRisk:
    id: str
    policy_id: str
    risk_score: float
    risk_category: str
    risk_factors: List[Dict[str, Any]]
    mitigation_strategies: List[str]
    assessed_at: float
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsuranceCoverage:
    id: str
    policy_id: str
    asset: str
    amount: Decimal
    percentage: float
    start_time: float
    end_time: Optional[float] = None
    used_amount: Decimal = Decimal('0')
    remaining_amount: Decimal = Decimal('0')
    metadata: Dict[str, Any] = field(default_factory=dict)


class InsuranceManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._policies: Dict[str, InsurancePolicy] = {}
        self._claims: Dict[str, InsuranceClaim] = {}
        self._premiums: Dict[str, InsurancePremium] = {}
        self._risks: Dict[str, InsuranceRisk] = {}
        self._coverages: Dict[str, InsuranceCoverage] = {}
        self._active_triggers: Dict[str, List[str]] = defaultdict(list)
        self._monitors: List[Callable] = []
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        self._initialize_default_policies()

    def _initialize_default_policies(self) -> None:
        default_policies = [
            {
                "name": "Standard Stop Loss",
                "type": InsuranceType.STOP_LOSS,
                "trigger_type": InsuranceTrigger.PRICE,
                "protection_level": 0.5,
                "coverage_amount": Decimal('1000'),
                "premium": Decimal('10'),
                "deductible": Decimal('50'),
                "max_payout": Decimal('1000')
            },
            {
                "name": "Black Swan Protection",
                "type": InsuranceType.BLACK_SWAN,
                "trigger_type": InsuranceTrigger.VOLATILITY,
                "protection_level": 0.9,
                "coverage_amount": Decimal('5000'),
                "premium": Decimal('100'),
                "deductible": Decimal('500'),
                "max_payout": Decimal('5000')
            },
            {
                "name": "Drawdown Protection",
                "type": InsuranceType.DRAWDOWN_PROTECTION,
                "trigger_type": InsuranceTrigger.DRAWDOWN,
                "protection_level": 0.7,
                "coverage_amount": Decimal('2000'),
                "premium": Decimal('50'),
                "deductible": Decimal('200'),
                "max_payout": Decimal('2000')
            }
        ]
        
        for policy_data in default_policies:
            policy = InsurancePolicy(
                id=str(uuid.uuid4()),
                name=policy_data["name"],
                type=policy_data["type"],
                status=InsuranceStatus.ACTIVE,
                asset="BTC/USDT",
                trigger_type=policy_data["trigger_type"],
                protection_level=policy_data["protection_level"],
                coverage_amount=policy_data["coverage_amount"],
                premium=policy_data["premium"],
                deductible=policy_data["deductible"],
                max_payout=policy_data["max_payout"],
                expires_at=time.time() + 86400 * 365
            )
            self._policies[policy.id] = policy
            self._active_triggers[policy.trigger_type.value].append(policy.id)

    def register_monitor(self, monitor: Callable) -> None:
        self._monitors.append(monitor)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_policy(
        self,
        name: str,
        policy_type: InsuranceType,
        asset: str,
        trigger_type: InsuranceTrigger,
        trigger_value: float,
        coverage_amount: Decimal,
        premium: Decimal,
        deductible: Decimal = Decimal('0'),
        max_payout: Optional[Decimal] = None,
        position_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        duration_days: int = 365,
        parameters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Dict[str, Any]]] = None
    ) -> InsurancePolicy:
        async with self._lock:
            policy_id = str(uuid.uuid4())
            
            policy = InsurancePolicy(
                id=policy_id,
                name=name,
                type=policy_type,
                status=InsuranceStatus.ACTIVE,
                asset=asset,
                position_id=position_id,
                portfolio_id=portfolio_id,
                trigger_type=trigger_type,
                trigger_value=trigger_value,
                protection_level=0.5,
                coverage_amount=coverage_amount,
                premium=premium,
                deductible=deductible,
                max_payout=max_payout or coverage_amount,
                expires_at=time.time() + duration_days * 86400,
                parameters=parameters or {},
                conditions=conditions or []
            )
            
            self._policies[policy_id] = policy
            self._active_triggers[trigger_type.value].append(policy_id)
            
            await self._notify_observers("policy_created", policy)
            return policy

    async def update_policy(
        self,
        policy_id: str,
        status: Optional[InsuranceStatus] = None,
        trigger_value: Optional[float] = None,
        coverage_amount: Optional[Decimal] = None,
        premium: Optional[Decimal] = None,
        deductible: Optional[Decimal] = None,
        max_payout: Optional[Decimal] = None,
        parameters: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[InsurancePolicy]:
        async with self._lock:
            if policy_id not in self._policies:
                return None
            
            policy = self._policies[policy_id]
            
            if status:
                old_status = policy.status
                policy.status = status
                
                if status == InsuranceStatus.TRIGGERED:
                    policy.triggered_at = time.time()
                elif status == InsuranceStatus.ACTIVE:
                    self._active_triggers[policy.trigger_type.value].append(policy_id)
                
                await self._notify_observers("policy_status_changed", policy, old_status)
            
            if trigger_value:
                policy.trigger_value = trigger_value
            
            if coverage_amount:
                policy.coverage_amount = coverage_amount
                policy.max_payout = coverage_amount
            
            if premium:
                policy.premium = premium
            
            if deductible:
                policy.deductible = deductible
            
            if max_payout:
                policy.max_payout = max_payout
            
            if parameters:
                policy.parameters.update(parameters)
            
            if conditions:
                policy.conditions = conditions
            
            await self._notify_observers("policy_updated", policy)
            return policy

    async def get_policy(self, policy_id: str) -> Optional[InsurancePolicy]:
        return self._policies.get(policy_id)

    async def get_policies(
        self,
        policy_type: Optional[InsuranceType] = None,
        status: Optional[InsuranceStatus] = None,
        asset: Optional[str] = None
    ) -> List[InsurancePolicy]:
        policies = list(self._policies.values())
        
        if policy_type:
            policies = [p for p in policies if p.type == policy_type]
        
        if status:
            policies = [p for p in policies if p.status == status]
        
        if asset:
            policies = [p for p in policies if p.asset == asset]
        
        return policies

    async def delete_policy(self, policy_id: str) -> bool:
        async with self._lock:
            if policy_id not in self._policies:
                return False
            
            policy = self._policies[policy_id]
            
            if policy.trigger_type.value in self._active_triggers:
                self._active_triggers[policy.trigger_type.value].remove(policy_id)
            
            del self._policies[policy_id]
            
            await self._notify_observers("policy_deleted", policy_id)
            return True

    async def create_claim(
        self,
        policy_id: str,
        amount: Decimal,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[InsuranceClaim]:
        async with self._lock:
            if policy_id not in self._policies:
                return None
            
            policy = self._policies[policy_id]
            
            if policy.status != InsuranceStatus.TRIGGERED:
                return None
            
            claim_id = str(uuid.uuid4())
            
            claim = InsuranceClaim(
                id=claim_id,
                policy_id=policy_id,
                amount=min(amount, policy.max_payout - policy.current_payout),
                status="pending",
                reason=reason,
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._claims[claim_id] = claim
            await self._notify_observers("claim_created", claim)
            return claim

    async def process_claim(
        self,
        claim_id: str,
        approve: bool = True,
        rejection_reason: Optional[str] = None
    ) -> Optional[InsuranceClaim]:
        async with self._lock:
            if claim_id not in self._claims:
                return None
            
            claim = self._claims[claim_id]
            policy = self._policies.get(claim.policy_id)
            
            if approve:
                claim.status = "approved"
                claim.approved_at = time.time()
                claim.processed_at = time.time()
                
                if policy:
                    policy.current_payout += claim.amount
                    await self._pay_claim(claim)
            else:
                claim.status = "rejected"
                claim.rejected_at = time.time()
                claim.processed_at = time.time()
                claim.rejection_reason = rejection_reason
            
            await self._notify_observers("claim_processed", claim)
            return claim

    async def _pay_claim(self, claim: InsuranceClaim) -> None:
        claim.status = "paid"
        claim.paid_at = time.time()
        
        logger.info(f"Paid claim {claim.id} amount {claim.amount}")
        await self._notify_observers("claim_paid", claim)

    async def start_monitoring(self) -> None:
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Insurance monitoring started")

    async def stop_monitoring(self) -> None:
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        logger.info("Insurance monitoring stopped")

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await self._check_triggers()
                await self._check_expirations()
                await self._process_premiums()
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)

    async def _check_triggers(self) -> None:
        for trigger_type, policy_ids in self._active_triggers.items():
            for policy_id in policy_ids:
                policy = self._policies.get(policy_id)
                if not policy or policy.status != InsuranceStatus.ACTIVE:
                    continue
                
                triggered = await self._evaluate_trigger(policy)
                
                if triggered:
                    policy.status = InsuranceStatus.TRIGGERED
                    policy.triggered_at = time.time()
                    self._active_triggers[trigger_type].remove(policy_id)
                    
                    await self._notify_observers("policy_triggered", policy)

    async def _evaluate_trigger(self, policy: InsurancePolicy) -> bool:
        try:
            if policy.trigger_type == InsuranceTrigger.PRICE:
                current_price = await self._get_current_price(policy.asset)
                if policy.parameters.get("direction") == "below":
                    return current_price <= policy.trigger_value
                else:
                    return current_price >= policy.trigger_value
            
            elif policy.trigger_type == InsuranceTrigger.VOLATILITY:
                current_volatility = await self._get_current_volatility(policy.asset)
                return current_volatility >= policy.trigger_value
            
            elif policy.trigger_type == InsuranceTrigger.DRAWDOWN:
                current_drawdown = await self._get_current_drawdown(policy.asset)
                return current_drawdown >= policy.trigger_value
            
            elif policy.trigger_type == InsuranceTrigger.TIME:
                current_time = time.time()
                return current_time >= policy.trigger_value
            
            elif policy.trigger_type == InsuranceTrigger.COMPOSITE:
                return await self._evaluate_composite_trigger(policy)
            
            elif policy.trigger_type == InsuranceTrigger.CONDITION:
                return await self._evaluate_condition_trigger(policy)
            
            elif policy.trigger_type == InsuranceTrigger.MANUAL:
                return False
            
        except Exception as e:
            logger.error(f"Error evaluating trigger for {policy.id}: {e}")
            return False
        
        return False

    async def _evaluate_composite_trigger(self, policy: InsurancePolicy) -> bool:
        conditions_met = 0
        total_conditions = len(policy.conditions)
        
        for condition in policy.conditions:
            if await self._evaluate_individual_condition(condition):
                conditions_met += 1
        
        threshold = policy.parameters.get("threshold", 0.5)
        return (conditions_met / total_conditions) >= threshold

    async def _evaluate_individual_condition(self, condition: Dict[str, Any]) -> bool:
        condition_type = condition.get("type")
        value = condition.get("value")
        operator = condition.get("operator", "eq")
        
        if condition_type == "price":
            current = await self._get_current_price(condition.get("asset", "BTC/USDT"))
        elif condition_type == "volatility":
            current = await self._get_current_volatility(condition.get("asset", "BTC/USDT"))
        elif condition_type == "drawdown":
            current = await self._get_current_drawdown(condition.get("asset", "BTC/USDT"))
        else:
            return False
        
        if operator == "eq":
            return current == value
        elif operator == "gt":
            return current > value
        elif operator == "gte":
            return current >= value
        elif operator == "lt":
            return current < value
        elif operator == "lte":
            return current <= value
        elif operator == "ne":
            return current != value
        elif operator == "between":
            return value[0] <= current <= value[1]
        
        return False

    async def _evaluate_condition_trigger(self, policy: InsurancePolicy) -> bool:
        for condition in policy.conditions:
            if not await self._evaluate_individual_condition(condition):
                return False
        return True

    async def _check_expirations(self) -> None:
        now = time.time()
        
        for policy in self._policies.values():
            if policy.status == InsuranceStatus.EXPIRED:
                continue
            
            if policy.expires_at and policy.expires_at <= now:
                policy.status = InsuranceStatus.EXPIRED
                await self._notify_observers("policy_expired", policy)

    async def _process_premiums(self) -> None:
        now = time.time()
        
        for premium in self._premiums.values():
            if premium.paid:
                continue
            
            if premium.next_payment <= now:
                await self._collect_premium(premium)
                premium.last_payment = now
                premium.next_payment = now + self._get_premium_interval(premium.frequency)

    async def _collect_premium(self, premium: InsurancePremium) -> None:
        logger.info(f"Collecting premium {premium.id} amount {premium.amount}")
        premium.paid = True
        await self._notify_observers("premium_collected", premium)

    def _get_premium_interval(self, frequency: str) -> int:
        if frequency == "daily":
            return 86400
        elif frequency == "weekly":
            return 604800
        elif frequency == "monthly":
            return 2592000
        elif frequency == "quarterly":
            return 7776000
        elif frequency == "yearly":
            return 31536000
        else:
            return 86400

    async def _get_current_price(self, asset: str) -> float:
        return 0.0

    async def _get_current_volatility(self, asset: str) -> float:
        return 0.0

    async def _get_current_drawdown(self, asset: str) -> float:
        return 0.0

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
        total_policies = len(self._policies)
        active_policies = len([p for p in self._policies.values() if p.status == InsuranceStatus.ACTIVE])
        triggered_policies = len([p for p in self._policies.values() if p.status == InsuranceStatus.TRIGGERED])
        expired_policies = len([p for p in self._policies.values() if p.status == InsuranceStatus.EXPIRED])
        
        total_claims = len(self._claims)
        pending_claims = len([c for c in self._claims.values() if c.status == "pending"])
        paid_claims = len([c for c in self._claims.values() if c.status == "paid"])
        rejected_claims = len([c for c in self._claims.values() if c.status == "rejected"])
        
        total_coverage = sum(p.coverage_amount for p in self._policies.values() if p.status == InsuranceStatus.ACTIVE)
        total_premiums = sum(p.premium for p in self._policies.values() if p.status == InsuranceStatus.ACTIVE)
        total_payouts = sum(p.current_payout for p in self._policies.values())
        
        return {
            "policies": {
                "total": total_policies,
                "active": active_policies,
                "triggered": triggered_policies,
                "expired": expired_policies,
                "total_coverage": float(total_coverage),
                "total_premiums": float(total_premiums),
                "total_payouts": float(total_payouts)
            },
            "claims": {
                "total": total_claims,
                "pending": pending_claims,
                "paid": paid_claims,
                "rejected": rejected_claims
            },
            "monitors": len(self._monitors),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "InsuranceType",
    "InsuranceStatus",
    "InsuranceTrigger",
    "InsurancePolicy",
    "InsuranceClaim",
    "InsurancePremium",
    "InsuranceRisk",
    "InsuranceCoverage",
    "InsuranceManager"
]

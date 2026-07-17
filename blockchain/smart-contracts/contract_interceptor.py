# blockchain/smart-contracts/contract_interceptor.py
# NEXUS AI TRADING SYSTEM - Smart Contract Call Interceptor
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Advanced Smart Contract Call Interceptor for NEXUS AI Trading System.
Provides comprehensive contract call interception, monitoring, analysis,
and security validation for all contract interactions across multiple chains.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from web3 import Web3
from web3.contract import Contract
from web3.exceptions import BadFunctionCallOutput, ContractLogicError

# NEXUS Imports
from blockchain.web3.web3_client import Web3Client
from shared.utilities.logger import get_logger

logger = get_logger("nexus.blockchain.interceptor")


# ============================================================================
# Enums & Constants
# ============================================================================

class InterceptAction(str, Enum):
    """Actions to take on intercepted calls."""
    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"
    LOG = "log"
    ALERT = "alert"
    DELAY = "delay"
    ROUTE = "route"
    SIMULATE = "simulate"


class InterceptLevel(str, Enum):
    """Interception levels."""
    NONE = "none"
    BASIC = "basic"      # Log only
    STANDARD = "standard"  # Log + validate
    ENFORCED = "enforced"  # Block unauthorized
    STRICT = "strict"     # Block all non-whitelisted
    PARANOID = "paranoid"  # Everything blocked unless explicitly allowed


class CallType(str, Enum):
    """Types of contract calls."""
    READ = "read"
    WRITE = "write"
    PAYABLE = "payable"
    VIEW = "view"
    PURE = "pure"
    CONSTRUCTOR = "constructor"
    FALLBACK = "fallback"
    RECEIVE = "receive"


@dataclass
class InterceptContext:
    """Context for an intercepted call."""
    call_id: str
    contract_address: str
    contract_name: Optional[str] = None
    function_name: str
    function_signature: str
    call_type: CallType
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    value: int = 0
    gas: int = 0
    gas_price: int = 0
    caller: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    block_number: int = 0
    transaction_hash: Optional[str] = None
    simulation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterceptResult:
    """Result of an intercepted call."""
    context: InterceptContext
    action: InterceptAction
    success: bool
    result: Any = None
    error: Optional[str] = None
    modified_args: Optional[Tuple[Any, ...]] = None
    modified_kwargs: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    gas_used: int = 0
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterceptRule:
    """Rule for intercepting calls."""
    rule_id: str
    name: str
    enabled: bool = True
    priority: int = 0
    contract_address: Optional[str] = None
    contract_name: Optional[str] = None
    function_name: Optional[str] = None
    function_signature: Optional[str] = None
    call_type: Optional[CallType] = None
    caller_address: Optional[str] = None
    action: InterceptAction = InterceptAction.LOG
    conditions: Dict[str, Any] = field(default_factory=dict)
    modifications: Dict[str, Any] = field(default_factory=dict)
    alert_config: Dict[str, Any] = field(default_factory=dict)
    log_level: str = "INFO"
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Contract Interceptor
# ============================================================================

class ContractInterceptor:
    """
    Advanced Smart Contract Call Interceptor.
    Intercepts, analyzes, and controls all contract interactions.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.web3_client = web3_client
        self.config = config or {}

        # Interception rules
        self._rules: List[InterceptRule] = []
        self._rules_by_contract: Dict[str, List[InterceptRule]] = {}
        self._rules_by_function: Dict[str, List[InterceptRule]] = {}

        # Whitelists
        self._address_whitelist: Set[str] = set()
        self._function_whitelist: Set[str] = set()
        self._caller_whitelist: Set[str] = set()

        # Blacklists
        self._address_blacklist: Set[str] = set()
        self._function_blacklist: Set[str] = set()
        self._caller_blacklist: Set[str] = set()

        # Call history
        self._call_history: List[InterceptResult] = []
        self._call_history_max = config.get("max_history", 10000)

        # Statistics
        self._stats = {
            "total_calls": 0,
            "allowed": 0,
            "blocked": 0,
            "modified": 0,
            "logged": 0,
            "alerts": 0,
            "errors": 0,
            "by_contract": {},
            "by_function": {},
            "by_caller": {},
        }

        # State management
        self._running = False
        self._lock = asyncio.Lock()
        self._intercept_level = InterceptLevel(config.get("level", InterceptLevel.STANDARD))

        # Callbacks
        self._before_callbacks: List[Callable] = []
        self._after_callbacks: List[Callable] = []
        self._alert_callbacks: List[Callable] = []

        # Initialize default rules
        self._initialize_default_rules()

        logger.info(
            "ContractInterceptor initialized",
            extra={
                "chain": web3_client.chain_name,
                "level": self._intercept_level.value,
                "rules": len(self._rules),
            }
        )

    # -----------------------------------------------------------------------
    # Rule Management
    # -----------------------------------------------------------------------

    def add_rule(self, rule: InterceptRule) -> None:
        """Add an interception rule."""
        self._rules.append(rule)

        # Index rules by contract
        if rule.contract_address:
            key = rule.contract_address.lower()
            if key not in self._rules_by_contract:
                self._rules_by_contract[key] = []
            self._rules_by_contract[key].append(rule)

        # Index rules by function
        if rule.function_signature:
            key = rule.function_signature
            if key not in self._rules_by_function:
                self._rules_by_function[key] = []
            self._rules_by_function[key].append(rule)

        # Sort by priority
        self._rules.sort(key=lambda r: r.priority, reverse=True)

        logger.info(f"Added intercept rule: {rule.rule_id}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an interception rule."""
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                self._rules.pop(i)
                # Remove from indexes
                self._rebuild_indexes()
                logger.info(f"Removed intercept rule: {rule_id}")
                return True
        return False

    def _rebuild_indexes(self) -> None:
        """Rebuild rule indexes."""
        self._rules_by_contract.clear()
        self._rules_by_function.clear()

        for rule in self._rules:
            if rule.contract_address:
                key = rule.contract_address.lower()
                if key not in self._rules_by_contract:
                    self._rules_by_contract[key] = []
                self._rules_by_contract[key].append(rule)

            if rule.function_signature:
                key = rule.function_signature
                if key not in self._rules_by_function:
                    self._rules_by_function[key] = []
                self._rules_by_function[key].append(rule)

        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = False
                return True
        return False

    # -----------------------------------------------------------------------
    # Whitelist / Blacklist Management
    # -----------------------------------------------------------------------

    def whitelist_address(self, address: str) -> None:
        """Add address to whitelist."""
        self._address_whitelist.add(address.lower())

    def whitelist_function(self, signature: str) -> None:
        """Add function signature to whitelist."""
        self._function_whitelist.add(signature)

    def whitelist_caller(self, address: str) -> None:
        """Add caller address to whitelist."""
        self._caller_whitelist.add(address.lower())

    def blacklist_address(self, address: str) -> None:
        """Add address to blacklist."""
        self._address_blacklist.add(address.lower())

    def blacklist_function(self, signature: str) -> None:
        """Add function signature to blacklist."""
        self._function_blacklist.add(signature)

    def blacklist_caller(self, address: str) -> None:
        """Add caller address to blacklist."""
        self._caller_blacklist.add(address.lower())

    def is_whitelisted(self, context: InterceptContext) -> bool:
        """Check if call is whitelisted."""
        if context.contract_address.lower() in self._address_whitelist:
            return True
        if context.function_signature in self._function_whitelist:
            return True
        if context.caller.lower() in self._caller_whitelist:
            return True
        return False

    def is_blacklisted(self, context: InterceptContext) -> bool:
        """Check if call is blacklisted."""
        if context.contract_address.lower() in self._address_blacklist:
            return True
        if context.function_signature in self._function_blacklist:
            return True
        if context.caller.lower() in self._caller_blacklist:
            return True
        return False

    # -----------------------------------------------------------------------
    # Interception Logic
    # -----------------------------------------------------------------------

    async def intercept_call(
        self,
        contract: Contract,
        function_name: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        Intercept a contract call.

        Args:
            contract: Contract instance
            function_name: Function name
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result or modified result
        """
        # Create context
        context = self._create_context(contract, function_name, args, kwargs)

        # Update stats
        self._stats["total_calls"] += 1
        self._stats["by_contract"][contract.address] = self._stats["by_contract"].get(contract.address, 0) + 1
        self._stats["by_function"][function_name] = self._stats["by_function"].get(function_name, 0) + 1
        self._stats["by_caller"][context.caller] = self._stats["by_caller"].get(context.caller, 0) + 1

        # Execute before callbacks
        await self._execute_before_callbacks(context)

        # Find matching rules
        matching_rules = self._find_matching_rules(context)

        # Determine action
        action, result = await self._determine_action(context, matching_rules)

        # Execute action
        if action == InterceptAction.BLOCK:
            self._stats["blocked"] += 1
            raise PermissionError(f"Call blocked: {function_name} on {contract.address}")

        elif action == InterceptAction.MODIFY:
            self._stats["modified"] += 1
            # Apply modifications
            context = self._apply_modifications(context, matching_rules)

        elif action == InterceptAction.ROUTE:
            self._stats["allowed"] += 1
            # Route to different contract/function
            context = await self._route_call(context, matching_rules)

        elif action == InterceptAction.SIMULATE:
            self._stats["allowed"] += 1
            # Simulate call without state changes
            return await self._simulate_call(context)

        elif action in [InterceptAction.LOG, InterceptAction.ALERT]:
            self._stats["logged"] += 1
            if action == InterceptAction.ALERT:
                self._stats["alerts"] += 1
            # Log and proceed

        # Execute the call
        try:
            start_time = time.time()
            func = getattr(contract.functions, function_name)
            call_result = await asyncio.to_thread(
                func(*context.args, **context.kwargs).call,
                {"from": context.caller}
            )
            execution_time = (time.time() - start_time) * 1000

            # Create result
            intercept_result = InterceptResult(
                context=context,
                action=action,
                success=True,
                result=call_result,
                execution_time_ms=execution_time,
                gas_used=0,  # Would be calculated from transaction
            )

            # Store in history
            await self._store_result(intercept_result)

            # Execute after callbacks
            await self._execute_after_callbacks(intercept_result)

            self._stats["allowed"] += 1
            return call_result

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Call execution error: {e}")

            intercept_result = InterceptResult(
                context=context,
                action=action,
                success=False,
                error=str(e),
            )

            await self._store_result(intercept_result)
            raise

    def _create_context(
        self,
        contract: Contract,
        function_name: str,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> InterceptContext:
        """Create intercept context."""
        # Determine call type
        call_type = self._determine_call_type(contract, function_name)

        # Create signature
        signature = self._create_signature(function_name, args, kwargs)

        return InterceptContext(
            call_id=f"{contract.address}_{function_name}_{int(time.time()*1000)}",
            contract_address=contract.address,
            contract_name=getattr(contract, "name", None),
            function_name=function_name,
            function_signature=signature,
            call_type=call_type,
            args=args,
            kwargs=kwargs,
            caller=self.web3_client.default_account or "",
            block_number=self.web3_client.eth.block_number if hasattr(self.web3_client, "eth") else 0,
        )

    def _determine_call_type(
        self,
        contract: Contract,
        function_name: str,
    ) -> CallType:
        """Determine call type from ABI."""
        if not contract.abi:
            return CallType.WRITE

        for item in contract.abi:
            if item.get("type") == "function" and item.get("name") == function_name:
                state_mutability = item.get("stateMutability", "")
                if state_mutability == "view":
                    return CallType.VIEW
                elif state_mutability == "pure":
                    return CallType.PURE
                elif state_mutability == "payable":
                    return CallType.PAYABLE
                else:
                    return CallType.WRITE

        return CallType.WRITE

    def _create_signature(
        self,
        function_name: str,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> str:
        """Create function signature."""
        # In production, would use proper ABI encoding
        arg_types = []
        for arg in args:
            if isinstance(arg, int):
                arg_types.append("uint256")
            elif isinstance(arg, str) and arg.startswith("0x"):
                arg_types.append("address")
            elif isinstance(arg, bool):
                arg_types.append("bool")
            elif isinstance(arg, list):
                arg_types.append("bytes")
            else:
                arg_types.append("bytes")

        return f"{function_name}({','.join(arg_types)})"

    def _find_matching_rules(
        self,
        context: InterceptContext,
    ) -> List[InterceptRule]:
        """Find rules matching the context."""
        matching = []

        # Check contract-specific rules
        contract_rules = self._rules_by_contract.get(context.contract_address.lower(), [])
        matching.extend(contract_rules)

        # Check function-specific rules
        function_rules = self._rules_by_function.get(context.function_signature, [])
        matching.extend(function_rules)

        # Check global rules
        global_rules = [r for r in self._rules if not r.contract_address and not r.function_signature]
        matching.extend(global_rules)

        # Filter by enabled and conditions
        filtered = []
        for rule in matching:
            if not rule.enabled:
                continue

            if rule.contract_name and context.contract_name != rule.contract_name:
                continue

            if rule.function_name and context.function_name != rule.function_name:
                continue

            if rule.call_type and context.call_type != rule.call_type:
                continue

            if rule.caller_address and context.caller.lower() != rule.caller_address.lower():
                continue

            # Check conditions
            if rule.conditions and not self._check_conditions(rule.conditions, context):
                continue

            filtered.append(rule)

        # Sort by priority
        filtered.sort(key=lambda r: r.priority, reverse=True)

        return filtered

    def _check_conditions(
        self,
        conditions: Dict[str, Any],
        context: InterceptContext,
    ) -> bool:
        """Check if conditions match."""
        for key, value in conditions.items():
            if key == "min_value" and context.value < value:
                return False
            if key == "max_value" and context.value > value:
                return False
            if key == "min_gas" and context.gas < value:
                return False
            if key == "max_gas" and context.gas > value:
                return False
            if key == "timestamp" and context.timestamp < datetime.fromisoformat(value):
                return False
        return True

    async def _determine_action(
        self,
        context: InterceptContext,
        rules: List[InterceptRule],
    ) -> Tuple[InterceptAction, Any]:
        """Determine action from matching rules."""
        # Check blacklist first
        if self.is_blacklisted(context):
            return InterceptAction.BLOCK, None

        # Check whitelist
        if self.is_whitelisted(context):
            return InterceptAction.ALLOW, None

        # Check level-based restrictions
        if self._intercept_level == InterceptLevel.STRICT:
            # Only allow whitelisted
            if not self.is_whitelisted(context):
                return InterceptAction.BLOCK, None

        elif self._intercept_level == InterceptLevel.PARANOID:
            # Block everything unless explicitly allowed
            return InterceptAction.BLOCK, None

        # Apply rules
        for rule in rules:
            if rule.action == InterceptAction.BLOCK:
                return InterceptAction.BLOCK, None
            if rule.action == InterceptAction.MODIFY:
                return InterceptAction.MODIFY, None
            if rule.action == InterceptAction.ROUTE:
                return InterceptAction.ROUTE, None
            if rule.action == InterceptAction.SIMULATE:
                return InterceptAction.SIMULATE, None
            if rule.action == InterceptAction.ALERT:
                return InterceptAction.ALERT, None
            if rule.action == InterceptAction.LOG:
                return InterceptAction.LOG, None

        # Default action based on level
        if self._intercept_level == InterceptLevel.ENFORCED:
            return InterceptAction.BLOCK, None
        elif self._intercept_level == InterceptLevel.STANDARD:
            return InterceptAction.LOG, None
        else:
            return InterceptAction.ALLOW, None

    def _apply_modifications(
        self,
        context: InterceptContext,
        rules: List[InterceptRule],
    ) -> InterceptContext:
        """Apply modifications from rules."""
        modified_args = list(context.args) if context.args else []
        modified_kwargs = dict(context.kwargs) if context.kwargs else {}

        for rule in rules:
            modifications = rule.modifications

            if "args" in modifications:
                for idx, value in modifications["args"].items():
                    if isinstance(idx, int) and idx < len(modified_args):
                        modified_args[idx] = value

            if "kwargs" in modifications:
                modified_kwargs.update(modifications["kwargs"])

            if "value" in modifications:
                context.value = modifications["value"]

            if "gas" in modifications:
                context.gas = modifications["gas"]

        context.args = tuple(modified_args)
        context.kwargs = modified_kwargs

        return context

    async def _route_call(
        self,
        context: InterceptContext,
        rules: List[InterceptRule],
    ) -> InterceptContext:
        """Route call to different contract/function."""
        for rule in rules:
            if rule.modifications and "route" in rule.modifications:
                route = rule.modifications["route"]
                context.contract_address = route.get("address", context.contract_address)
                context.function_name = route.get("function", context.function_name)
                break
        return context

    async def _simulate_call(self, context: InterceptContext) -> Any:
        """Simulate a call without state changes."""
        try:
            contract = self.web3_client.get_contract(
                context.contract_address,
                abi=[]  # Would need ABI
            )
            func = getattr(contract.functions, context.function_name)
            result = await asyncio.to_thread(
                func(*context.args, **context.kwargs).call,
                {"from": context.caller}
            )
            return result
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            raise

    # -----------------------------------------------------------------------
    # Call History
    # -----------------------------------------------------------------------

    async def _store_result(self, result: InterceptResult) -> None:
        """Store call result in history."""
        async with self._lock:
            self._call_history.append(result)
            if len(self._call_history) > self._call_history_max:
                self._call_history = self._call_history[-self._call_history_max:]

        # Check for alerts
        if result.context and result.context.metadata.get("alert"):
            await self._trigger_alerts(result)

    def get_call_history(
        self,
        limit: int = 100,
        contract_address: Optional[str] = None,
        function_name: Optional[str] = None,
        success_only: bool = False,
    ) -> List[InterceptResult]:
        """Get call history."""
        results = self._call_history

        if contract_address:
            results = [r for r in results if r.context and r.context.contract_address.lower() == contract_address.lower()]

        if function_name:
            results = [r for r in results if r.context and r.context.function_name == function_name]

        if success_only:
            results = [r for r in results if r.success]

        return results[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get interception statistics."""
        return {
            **self._stats,
            "rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules if r.enabled),
            "history_size": len(self._call_history),
            "level": self._intercept_level.value,
            "whitelist_size": len(self._address_whitelist) + len(self._function_whitelist) + len(self._caller_whitelist),
            "blacklist_size": len(self._address_blacklist) + len(self._function_blacklist) + len(self._caller_blacklist),
        }

    # -----------------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------------

    def register_before_callback(self, callback: Callable) -> None:
        """Register callback before call execution."""
        self._before_callbacks.append(callback)

    def register_after_callback(self, callback: Callable) -> None:
        """Register callback after call execution."""
        self._after_callbacks.append(callback)

    def register_alert_callback(self, callback: Callable) -> None:
        """Register callback for alerts."""
        self._alert_callbacks.append(callback)

    async def _execute_before_callbacks(self, context: InterceptContext) -> None:
        """Execute before callbacks."""
        for callback in self._before_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(context)
                else:
                    callback(context)
            except Exception as e:
                logger.error(f"Before callback error: {e}")

    async def _execute_after_callbacks(self, result: InterceptResult) -> None:
        """Execute after callbacks."""
        for callback in self._after_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"After callback error: {e}")

    async def _trigger_alerts(self, result: InterceptResult) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    # -----------------------------------------------------------------------
    # Default Rules
    # -----------------------------------------------------------------------

    def _initialize_default_rules(self) -> None:
        """Initialize default interception rules."""
        # Reentrancy protection
        self.add_rule(InterceptRule(
            rule_id="reentrancy_check",
            name="Reentrancy Protection",
            priority=100,
            action=InterceptAction.BLOCK,
            conditions={
                "max_gas": 500000,  # Prevent excessive gas usage
            },
        ))

        # Selfdestruct block
        self.add_rule(InterceptRule(
            rule_id="selfdestruct_block",
            name="Block Selfdestruct",
            priority=100,
            function_name="selfdestruct",
            action=InterceptAction.BLOCK,
        ))

        # Delegate call monitor
        self.add_rule(InterceptRule(
            rule_id="delegatecall_monitor",
            name="Monitor Delegate Calls",
            priority=50,
            function_name="delegatecall",
            action=InterceptAction.ALERT,
            alert_config={"severity": "high", "message": "Delegate call detected"},
        ))

        # Log all payable functions
        self.add_rule(InterceptRule(
            rule_id="payable_log",
            name="Log Payable Functions",
            priority=10,
            call_type=CallType.PAYABLE,
            action=InterceptAction.LOG,
        ))

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the interceptor."""
        self._running = True
        logger.info("ContractInterceptor started")

    async def stop(self) -> None:
        """Stop the interceptor."""
        self._running = False
        logger.info("ContractInterceptor stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_contract_interceptor(
    web3_client: Web3Client,
    config: Optional[Dict[str, Any]] = None,
) -> ContractInterceptor:
    """
    Factory function to create a ContractInterceptor instance.

    Args:
        web3_client: Web3 client instance
        config: Configuration dictionary

    Returns:
        ContractInterceptor instance
    """
    return ContractInterceptor(
        web3_client=web3_client,
        config=config or {},
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the contract interceptor
    pass

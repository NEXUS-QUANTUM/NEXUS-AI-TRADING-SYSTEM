"""
Swing Bot Planning Model
==========================

This module provides planning and strategy models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class TradingPlan:
    """Trading plan data structure."""
    plan_id: str
    name: str
    strategy: str
    time_horizon: str  # 'short', 'medium', 'long'
    entry_conditions: List[Dict[str, Any]]
    exit_conditions: List[Dict[str, Any]]
    risk_parameters: Dict[str, float]
    position_sizing: Dict[str, float]
    created_at: datetime
    updated_at: datetime
    status: str = 'active'  # 'active', 'paused', 'completed'


@dataclass
class PlanningSignal:
    """Planning trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    plan_id: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class PlanningModel:
    """
    Trading planning model for systematic strategy execution.
    
    Implements planning and strategy management.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the planning model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.plans: Dict[str, TradingPlan] = {}
        self.active_plans: List[str] = []
        self.history: List[Dict[str, Any]] = []
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def create_plan(self, name: str, strategy: str,
                   time_horizon: str,
                   entry_conditions: List[Dict[str, Any]],
                   exit_conditions: List[Dict[str, Any]],
                   risk_parameters: Dict[str, float],
                   position_sizing: Dict[str, float]) -> TradingPlan:
        """
        Create a new trading plan.
        
        Args:
            name: Plan name
            strategy: Strategy name
            time_horizon: Time horizon
            entry_conditions: Entry conditions
            exit_conditions: Exit conditions
            risk_parameters: Risk parameters
            position_sizing: Position sizing parameters
            
        Returns:
            TradingPlan object
        """
        plan_id = f"plan_{int(datetime.now().timestamp())}"
        
        plan = TradingPlan(
            plan_id=plan_id,
            name=name,
            strategy=strategy,
            time_horizon=time_horizon,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            risk_parameters=risk_parameters,
            position_sizing=position_sizing,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status='active'
        )
        
        self.plans[plan_id] = plan
        self.active_plans.append(plan_id)
        
        return plan
    
    def activate_plan(self, plan_id: str) -> bool:
        """
        Activate a trading plan.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            True if activated, False otherwise
        """
        if plan_id not in self.plans:
            return False
        
        plan = self.plans[plan_id]
        plan.status = 'active'
        if plan_id not in self.active_plans:
            self.active_plans.append(plan_id)
        
        return True
    
    def pause_plan(self, plan_id: str) -> bool:
        """
        Pause a trading plan.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            True if paused, False otherwise
        """
        if plan_id not in self.plans:
            return False
        
        plan = self.plans[plan_id]
        plan.status = 'paused'
        if plan_id in self.active_plans:
            self.active_plans.remove(plan_id)
        
        return True
    
    def complete_plan(self, plan_id: str) -> bool:
        """
        Complete a trading plan.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            True if completed, False otherwise
        """
        if plan_id not in self.plans:
            return False
        
        plan = self.plans[plan_id]
        plan.status = 'completed'
        if plan_id in self.active_plans:
            self.active_plans.remove(plan_id)
        
        return True
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze market conditions and evaluate plans.
        
        Args:
            df: OHLCV data
            
        Returns:
            Analysis results
        """
        if len(df) < self.lookback_period:
            return {'status': 'insufficient_data'}
        
        # Evaluate each active plan
        signals = []
        for plan_id in self.active_plans:
            plan = self.plans[plan_id]
            signal = self._evaluate_plan(df, plan)
            if signal:
                signals.append(signal)
        
        return {
            'signals': signals,
            'active_plans': len(self.active_plans),
            'plans': self.active_plans
        }
    
    def _evaluate_plan(self, df: pd.DataFrame, plan: TradingPlan) -> Optional[PlanningSignal]:
        """
        Evaluate a trading plan.
        
        Args:
            df: OHLCV data
            plan: TradingPlan object
            
        Returns:
            PlanningSignal or None
        """
        # Check entry conditions
        entry_signal = self._check_conditions(df, plan.entry_conditions)
        
        if not entry_signal:
            return None
        
        # Check exit conditions
        exit_signal = self._check_conditions(df, plan.exit_conditions)
        
        if exit_signal:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Calculate confidence
        confidence = self._calculate_plan_confidence(df, plan)
        
        if confidence < self.confidence_threshold:
            return None
        
        # Calculate targets
        target = self._calculate_target(df, plan, current_price)
        stop_loss = self._calculate_stop_loss(df, plan, current_price)
        
        return PlanningSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type='buy' if entry_signal['type'] == 'long' else 'sell',
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=f"Plan {plan.name} triggered",
            plan_id=plan.plan_id,
            indicators={
                'entry_condition': entry_signal,
                'plan_parameters': {
                    'time_horizon': plan.time_horizon,
                    'risk_parameters': plan.risk_parameters,
                    'position_sizing': plan.position_sizing
                }
            }
        )
    
    def _check_conditions(self, df: pd.DataFrame,
                         conditions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Check if conditions are met.
        
        Args:
            df: OHLCV data
            conditions: List of condition dictionaries
            
        Returns:
            Condition result or None
        """
        for condition in conditions:
            condition_type = condition.get('type')
            parameter = condition.get('parameter')
            threshold = condition.get('threshold')
            comparison = condition.get('comparison', 'gt')
            
            if condition_type == 'price':
                value = df['close'].iloc[-1]
            elif condition_type == 'volume':
                value = df['volume'].iloc[-1]
            elif condition_type == 'rsi':
                value = self._calculate_rsi(df, parameter)
            elif condition_type == 'ma':
                value = df['close'].rolling(parameter).mean().iloc[-1]
            elif condition_type == 'momentum':
                value = self._calculate_momentum(df, parameter)
            else:
                continue
            
            # Check condition
            if comparison == 'gt':
                if not (value > threshold):
                    return None
            elif comparison == 'lt':
                if not (value < threshold):
                    return None
            elif comparison == 'eq':
                if not (value == threshold):
                    return None
        
        return {'type': 'long' if conditions[0].get('type') != 'sell' else 'short'}
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int) -> float:
        """
        Calculate RSI.
        
        Args:
            df: OHLCV data
            period: RSI period
            
        Returns:
            RSI value
        """
        if len(df) < period + 1:
            return 50.0
        
        close = df['close'].values
        returns = np.diff(close)
        
        gains = np.where(returns > 0, returns, 0)
        losses = np.where(returns < 0, -returns, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_momentum(self, df: pd.DataFrame, period: int) -> float:
        """
        Calculate momentum.
        
        Args:
            df: OHLCV data
            period: Momentum period
            
        Returns:
            Momentum value
        """
        if len(df) < period + 1:
            return 0.0
        
        close = df['close'].values
        momentum = (close[-1] - close[-period]) / close[-period]
        
        return momentum
    
    def _calculate_plan_confidence(self, df: pd.DataFrame, plan: TradingPlan) -> float:
        """
        Calculate plan confidence.
        
        Args:
            df: OHLCV data
            plan: TradingPlan object
            
        Returns:
            Confidence score (0-1)
        """
        # Check historical performance
        history_performance = self._get_plan_performance(plan.plan_id)
        performance_score = min(history_performance, 1.0) if history_performance else 0.5
        
        # Check market conditions
        market_score = self._check_market_conditions(df)
        
        # Check plan parameters
        param_score = self._check_plan_parameters(plan)
        
        # Combine
        confidence = (performance_score * 0.4 + market_score * 0.3 + param_score * 0.3)
        
        return min(max(confidence, 0.0), 1.0)
    
    def _get_plan_performance(self, plan_id: str) -> float:
        """
        Get plan performance.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Performance score (0-1)
        """
        # This would be implemented with actual performance tracking
        return 0.5
    
    def _check_market_conditions(self, df: pd.DataFrame) -> float:
        """
        Check market conditions.
        
        Args:
            df: OHLCV data
            
        Returns:
            Market score (0-1)
        """
        close = df['close'].values
        
        if len(close) < self.lookback_period:
            return 0.5
        
        # Check trend
        slope, intercept = MathUtils.linear_regression(
            np.arange(len(close[-self.lookback_period:])),
            close[-self.lookback_period:]
        )
        r2 = MathUtils.r_squared(
            np.arange(len(close[-self.lookback_period:])),
            close[-self.lookback_period:]
        )
        
        trend_score = min(abs(slope) * 10, 1.0)
        reliability_score = min(r2 * 2, 1.0)
        
        return (trend_score + reliability_score) / 2
    
    def _check_plan_parameters(self, plan: TradingPlan) -> float:
        """
        Check plan parameters.
        
        Args:
            plan: TradingPlan object
            
        Returns:
            Parameter score (0-1)
        """
        # Check risk parameters
        risk_score = 1 - min(plan.risk_parameters.get('risk', 0.5), 0.5)
        
        # Check position sizing
        size_score = min(plan.position_sizing.get('size', 0.5), 0.5)
        
        return (risk_score + size_score) / 2
    
    def _calculate_target(self, df: pd.DataFrame, plan: TradingPlan,
                         current_price: float) -> float:
        """
        Calculate price target.
        
        Args:
            df: OHLCV data
            plan: TradingPlan object
            current_price: Current price
            
        Returns:
            Target price
        """
        risk_reward = plan.risk_parameters.get('risk_reward_ratio', 2.0)
        stop_loss = self._calculate_stop_loss(df, plan, current_price)
        
        if current_price > stop_loss:
            target = current_price + (current_price - stop_loss) * risk_reward
        else:
            target = current_price - (stop_loss - current_price) * risk_reward
        
        return target
    
    def _calculate_stop_loss(self, df: pd.DataFrame, plan: TradingPlan,
                           current_price: float) -> float:
        """
        Calculate stop loss.
        
        Args:
            df: OHLCV data
            plan: TradingPlan object
            current_price: Current price
            
        Returns:
            Stop loss price
        """
        stop_percent = plan.risk_parameters.get('stop_loss_percent', 0.02)
        
        return current_price * (1 - stop_percent)
    
    def get_plan_summary(self, plan_id: str) -> Dict[str, Any]:
        """
        Get plan summary.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Plan summary
        """
        if plan_id not in self.plans:
            return {'status': 'not_found'}
        
        plan = self.plans[plan_id]
        
        return {
            'plan_id': plan.plan_id,
            'name': plan.name,
            'strategy': plan.strategy,
            'time_horizon': plan.time_horizon,
            'status': plan.status,
            'created_at': plan.created_at.isoformat(),
            'updated_at': plan.updated_at.isoformat(),
            'entry_conditions': plan.entry_conditions,
            'exit_conditions': plan.exit_conditions,
            'risk_parameters': plan.risk_parameters,
            'position_sizing': plan.position_sizing
        }
    
    def get_all_plans(self) -> List[Dict[str, Any]]:
        """
        Get all plans.
        
        Returns:
            List of plan summaries
        """
        return [self.get_plan_summary(plan_id) for plan_id in self.plans]


def create_planning_model(config: Optional[Dict[str, Any]] = None) -> PlanningModel:
    """
    Create a planning model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        PlanningModel instance
    """
    return PlanningModel(config)


__all__ = [
    'TradingPlan',
    'PlanningSignal',
    'PlanningModel',
    'create_planning_model'
]

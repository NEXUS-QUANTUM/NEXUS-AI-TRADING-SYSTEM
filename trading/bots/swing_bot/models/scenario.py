"""
Swing Bot Scenario Model
==========================

This module provides scenario analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class Scenario:
    """Scenario data structure."""
    name: str
    description: str
    probability: float
    market_conditions: Dict[str, Any]
    expected_return: float
    expected_volatility: float
    confidence: float
    timestamp: datetime


@dataclass
class ScenarioResult:
    """Scenario result data structure."""
    scenario: Scenario
    portfolio_impact: float
    risk_impact: float
    recommendation: str
    confidence: float


@dataclass
class ScenarioSignal:
    """Scenario trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    scenario: Scenario
    indicators: Dict[str, Any] = field(default_factory=dict)


class ScenarioModel:
    """
    Scenario analysis model for market forecasting.
    
    Implements scenario planning and analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the scenario model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.scenarios: List[Scenario] = []
        self.results: List[ScenarioResult] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Register default scenarios
        self._register_default_scenarios()
        
    def _register_default_scenarios(self) -> None:
        """Register default scenarios."""
        default_scenarios = [
            Scenario(
                name='bull_case',
                description='Optimistic market scenario',
                probability=0.25,
                market_conditions={
                    'trend': 'up',
                    'volatility': 'low',
                    'liquidity': 'high',
                    'sentiment': 'bullish'
                },
                expected_return=0.15,
                expected_volatility=0.10,
                confidence=0.7,
                timestamp=datetime.now()
            ),
            Scenario(
                name='base_case',
                description='Moderate market scenario',
                probability=0.50,
                market_conditions={
                    'trend': 'neutral',
                    'volatility': 'moderate',
                    'liquidity': 'normal',
                    'sentiment': 'neutral'
                },
                expected_return=0.05,
                expected_volatility=0.15,
                confidence=0.6,
                timestamp=datetime.now()
            ),
            Scenario(
                name='bear_case',
                description='Pessimistic market scenario',
                probability=0.25,
                market_conditions={
                    'trend': 'down',
                    'volatility': 'high',
                    'liquidity': 'low',
                    'sentiment': 'bearish'
                },
                expected_return=-0.10,
                expected_volatility=0.25,
                confidence=0.6,
                timestamp=datetime.now()
            )
        ]
        
        self.scenarios.extend(default_scenarios)
    
    def add_scenario(self, scenario: Scenario) -> None:
        """
        Add a scenario.
        
        Args:
            scenario: Scenario object
        """
        self.scenarios.append(scenario)
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze scenarios.
        
        Args:
            df: OHLCV data
            
        Returns:
            Scenario analysis results
        """
        if len(df) < 50:
            return {'scenarios': [], 'signals': []}
        
        # Evaluate scenarios
        evaluated_scenarios = self._evaluate_scenarios(df)
        
        # Generate signals
        signals = self._generate_signals(df, evaluated_scenarios)
        
        return {
            'scenarios': evaluated_scenarios,
            'signals': signals,
            'best_scenario': self._get_best_scenario(evaluated_scenarios),
            'worst_scenario': self._get_worst_scenario(evaluated_scenarios),
            'market_character': self._get_market_character(df, evaluated_scenarios)
        }
    
    def _evaluate_scenarios(self, df: pd.DataFrame) -> List[ScenarioResult]:
        """
        Evaluate scenarios against current data.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of ScenarioResult objects
        """
        results = []
        close = df['close'].values
        returns = np.diff(np.log(close)) if len(close) > 1 else np.array([0])
        
        # Calculate current metrics
        current_return = np.mean(returns[-20:]) if len(returns) >= 20 else 0
        current_volatility = np.std(returns[-20:]) * np.sqrt(252) if len(returns) >= 20 else 0
        
        for scenario in self.scenarios:
            # Calculate impact
            impact = self._calculate_impact(scenario, current_return, current_volatility)
            
            # Calculate risk impact
            risk_impact = self._calculate_risk_impact(scenario, current_volatility)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(scenario, impact)
            
            results.append(ScenarioResult(
                scenario=scenario,
                portfolio_impact=impact,
                risk_impact=risk_impact,
                recommendation=recommendation,
                confidence=scenario.confidence
            ))
        
        self.results.extend(results)
        
        return results
    
    def _calculate_impact(self, scenario: Scenario, current_return: float,
                         current_volatility: float) -> float:
        """
        Calculate impact of scenario.
        
        Args:
            scenario: Scenario object
            current_return: Current return
            current_volatility: Current volatility
            
        Returns:
            Impact value
        """
        # Calculate expected return difference
        return_diff = scenario.expected_return - current_return
        
        # Calculate volatility adjustment
        vol_adjustment = 1 + (scenario.expected_volatility - current_volatility) / current_volatility if current_volatility > 0 else 1
        
        # Combine
        impact = return_diff * vol_adjustment
        
        return impact
    
    def _calculate_risk_impact(self, scenario: Scenario, current_volatility: float) -> float:
        """
        Calculate risk impact of scenario.
        
        Args:
            scenario: Scenario object
            current_volatility: Current volatility
            
        Returns:
            Risk impact value
        """
        if current_volatility == 0:
            return 0.0
        
        return (scenario.expected_volatility - current_volatility) / current_volatility
    
    def _generate_recommendation(self, scenario: Scenario, impact: float) -> str:
        """
        Generate recommendation based on scenario.
        
        Args:
            scenario: Scenario object
            impact: Impact value
            
        Returns:
            Recommendation string
        """
        if impact > 0.05:
            return f"Consider bullish positions for {scenario.name}"
        elif impact < -0.05:
            return f"Consider defensive positions for {scenario.name}"
        else:
            return f"Maintain current positions for {scenario.name}"
    
    def _generate_signals(self, df: pd.DataFrame,
                         evaluated_scenarios: List[ScenarioResult]) -> List[ScenarioSignal]:
        """
        Generate trading signals from scenarios.
        
        Args:
            df: OHLCV data
            evaluated_scenarios: List of scenario results
            
        Returns:
            List of ScenarioSignal objects
        """
        signals = []
        
        if not evaluated_scenarios:
            return signals
        
        # Get best and worst scenarios
        best = self._get_best_scenario(evaluated_scenarios)
        worst = self._get_worst_scenario(evaluated_scenarios)
        
        if not best or not worst:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Generate signal based on scenario confidence
        if best.confidence > self.confidence_threshold:
            signal_type = 'buy'
            reason = f"Best scenario {best.scenario.name} with confidence {best.confidence:.2f}"
            confidence = best.confidence
            target = current_price * (1 + 0.02)
            stop_loss = current_price * (1 - 0.01)
            
            signals.append(ScenarioSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                target=target,
                stop_loss=stop_loss,
                reason=reason,
                scenario=best.scenario,
                indicators={
                    'impact': best.portfolio_impact,
                    'risk_impact': best.risk_impact
                }
            ))
        
        return signals
    
    def _get_best_scenario(self, evaluated_scenarios: List[ScenarioResult]) -> Optional[ScenarioResult]:
        """
        Get best scenario.
        
        Args:
            evaluated_scenarios: List of scenario results
            
        Returns:
            Best scenario or None
        """
        if not evaluated_scenarios:
            return None
        
        # Sort by impact and confidence
        sorted_scenarios = sorted(evaluated_scenarios, 
                                key=lambda x: (x.portfolio_impact, x.confidence), 
                                reverse=True)
        
        return sorted_scenarios[0] if sorted_scenarios else None
    
    def _get_worst_scenario(self, evaluated_scenarios: List[ScenarioResult]) -> Optional[ScenarioResult]:
        """
        Get worst scenario.
        
        Args:
            evaluated_scenarios: List of scenario results
            
        Returns:
            Worst scenario or None
        """
        if not evaluated_scenarios:
            return None
        
        # Sort by impact and confidence
        sorted_scenarios = sorted(evaluated_scenarios, 
                                key=lambda x: (x.portfolio_impact, x.confidence))
        
        return sorted_scenarios[0] if sorted_scenarios else None
    
    def _get_market_character(self, df: pd.DataFrame,
                            evaluated_scenarios: List[ScenarioResult]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            evaluated_scenarios: List of scenario results
            
        Returns:
            Market character description
        """
        if not evaluated_scenarios:
            return "No scenarios evaluated"
        
        best = self._get_best_scenario(evaluated_scenarios)
        
        if best:
            return f"Best scenario: {best.scenario.name} (confidence: {best.confidence:.2f})"
        
        return "Scenario analysis inconclusive"
    
    def get_scenario_summary(self) -> Dict[str, Any]:
        """
        Get scenario summary.
        
        Returns:
            Scenario summary
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'total_scenarios': len(self.scenarios),
            'evaluated_scenarios': len(self.results),
            'scenarios': [
                {
                    'name': s.name,
                    'probability': s.probability,
                    'expected_return': s.expected_return,
                    'expected_volatility': s.expected_volatility,
                    'confidence': s.confidence
                }
                for s in self.scenarios
            ],
            'best_scenario': self._get_best_scenario(self.results) if self.results else None,
            'worst_scenario': self._get_worst_scenario(self.results) if self.results else None
        }


def create_scenario_model(config: Optional[Dict[str, Any]] = None) -> ScenarioModel:
    """
    Create a scenario model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ScenarioModel instance
    """
    return ScenarioModel(config)


__all__ = [
    'Scenario',
    'ScenarioResult',
    'ScenarioSignal',
    'ScenarioModel',
    'create_scenario_model'
]

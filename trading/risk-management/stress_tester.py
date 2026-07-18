"""
NEXUS AI TRADING SYSTEM - Stress Tester Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/risk-management/stress_tester.py
Description: Comprehensive portfolio stress testing with full API integration
"""

import asyncio
import json
import logging
import math
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm, t, skew, kurtosis
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.risk_config import RiskConfig
from shared.constants.trading_constants import (
    RISK_LEVELS,
    TIME_FRAMES,
    ASSET_CLASSES
)
from shared.types.risk import (
    StressTestConfig,
    StressTestResult,
    StressScenario,
    StressTestSummary
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import (
    Position,
    Order,
    Trade,
    PortfolioSnapshot,
    StressTest
)
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository
from backend.database.repositories.risk_repository import RiskRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Risk management imports
from trading.risk_management.portfolio_risk import PortfolioRiskManager
from trading.risk_management.risk_limits import RiskLimitsManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class StressScenarioType(str, Enum):
    """Types of stress test scenarios"""
    MARKET_CRASH = "market_crash"
    FLASH_CRASH = "flash_crash"
    BEAR_MARKET = "bear_market"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    INTEREST_RATE_HIKE = "interest_rate_hike"
    CURRENCY_CRISIS = "currency_crisis"
    COMMODITY_CRASH = "commodity_crash"
    GEOPOLITICAL_CRISIS = "geopolitical_crisis"
    SYSTEMIC_CRISIS = "systemic_crisis"
    CUSTOM = "custom"


class StressTestStatus(str, Enum):
    """Status of stress test"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StressSeverity(str, Enum):
    """Severity levels for stress tests"""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"
    CATASTROPHIC = "catastrophic"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StressTestRequest(BaseModel):
    """Request model for stress testing"""
    portfolio_id: str
    scenario_type: StressScenarioType = StressScenarioType.MARKET_CRASH
    severity: StressSeverity = StressSeverity.SEVERE
    time_horizon: str = "1d"  # 1h, 4h, 1d, 1w, 1m
    include_historical: bool = True
    include_monte_carlo: bool = True
    monte_carlo_simulations: int = 10000
    custom_scenario: Optional[Dict[str, Any]] = None
    use_correlation: bool = True
    detailed_output: bool = True
    confidence_level: float = 0.95
    max_loss_threshold: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('confidence_level')
    def validate_confidence(cls, v):
        if not 0 < v < 1:
            raise ValueError('Confidence level must be between 0 and 1')
        return v

    @validator('monte_carlo_simulations')
    def validate_simulations(cls, v):
        if v < 1000:
            raise ValueError('Monte Carlo simulations must be at least 1000')
        return v


class StressTestResponse(BaseModel):
    """Response model for stress test"""
    test_id: str
    portfolio_id: str
    scenario_type: StressScenarioType
    severity: StressSeverity
    status: StressTestStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    summary: Dict[str, Any]
    results: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    worst_case_loss: float
    worst_case_loss_pct: float
    expected_loss: float
    expected_loss_pct: float
    survival_probability: float
    capital_required: float
    time_to_recovery: Optional[float] = None


class HistoricalScenario(BaseModel):
    """Model for historical scenario"""
    name: str
    date: datetime
    market: str
    description: str
    shocks: Dict[str, float]
    duration_days: int
    recovery_days: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScenarioDefinition(BaseModel):
    """Model for scenario definition"""
    name: str
    type: StressScenarioType
    severity: StressSeverity
    shocks: Dict[str, float]  # Asset class -> shock percentage
    correlations: Optional[Dict[str, Dict[str, float]]] = None
    duration_days: int
    recovery_rate: float
    description: str


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class StressTestContext:
    """Context for stress testing"""
    portfolio_id: str
    scenario_type: StressScenarioType
    severity: StressSeverity
    time_horizon: int  # days
    positions: List[Any]
    trades: List[Any]
    snapshots: List[Any]
    market_data: Dict[str, Any]
    correlations: Dict[str, Dict[str, float]]
    volatilities: Dict[str, float]
    returns: Dict[str, List[float]]
    current_value: float
    historical_data: pd.DataFrame
    confidence_level: float


@dataclass
class ScenarioResult:
    """Result of a stress scenario"""
    scenario_name: str
    scenario_type: str
    severity: str
    loss: float
    loss_pct: float
    pnl: float
    pnl_pct: float
    var: float
    cvar: float
    max_drawdown: float
    recovery_time: Optional[float] = None
    capital_impact: float
    risk_score: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonteCarloResult:
    """Result of Monte Carlo simulation"""
    mean: float
    std: float
    var: float
    cvar: float
    max_loss: float
    max_loss_pct: float
    percentiles: Dict[str, float]
    distribution: List[float]
    survival_probability: float
    confidence_interval: Tuple[float, float]


# =============================================================================
# STRESS TESTER
# =============================================================================

class StressTester:
    """
    Comprehensive Stress Tester with full API integration.
    
    Features:
    - Multiple scenario types (market crash, flash crash, bear market, etc.)
    - Historical scenario replay
    - Monte Carlo simulation
    - Correlation-based stress propagation
    - Portfolio impact analysis
    - Capital adequacy assessment
    - Recovery time estimation
    - Risk metric computation
    - Custom scenario definition
    - Detailed reporting
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None,
        risk_repo: Optional[RiskRepository] = None,
        portfolio_risk: Optional[PortfolioRiskManager] = None,
        risk_limits: Optional[RiskLimitsManager] = None
    ):
        """
        Initialize StressTester.
        
        Args:
            config: Risk configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
            risk_repo: Risk repository
            portfolio_risk: Portfolio risk manager
            risk_limits: Risk limits manager
        """
        self.config = config or RiskConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        self.risk_repo = risk_repo or RiskRepository()
        self.portfolio_risk = portfolio_risk or PortfolioRiskManager()
        self.risk_limits = risk_limits or RiskLimitsManager()
        
        # Stress test storage
        self._tests: Dict[str, Dict[str, Any]] = {}
        self._scenarios: Dict[str, ScenarioDefinition] = {}
        self._historical_scenarios: List[HistoricalScenario] = []
        
        # Initialize scenarios
        self._init_default_scenarios()
        self._init_historical_scenarios()
        
        logger.info("StressTester initialized")

    def _init_default_scenarios(self) -> None:
        """Initialize default stress scenarios"""
        default_scenarios = {
            'market_crash_severe': ScenarioDefinition(
                name="Severe Market Crash",
                type=StressScenarioType.MARKET_CRASH,
                severity=StressSeverity.SEVERE,
                shocks={
                    'equity': -0.30,
                    'crypto': -0.50,
                    'fixed_income': -0.10,
                    'commodity': -0.20,
                    'forex': -0.15
                },
                duration_days=30,
                recovery_rate=0.50,
                description="Severe market crash similar to 2008 financial crisis"
            ),
            'market_crash_extreme': ScenarioDefinition(
                name="Extreme Market Crash",
                type=StressScenarioType.MARKET_CRASH,
                severity=StressSeverity.EXTREME,
                shocks={
                    'equity': -0.50,
                    'crypto': -0.70,
                    'fixed_income': -0.20,
                    'commodity': -0.35,
                    'forex': -0.25
                },
                duration_days=60,
                recovery_rate=0.30,
                description="Extreme market crash scenario"
            ),
            'flash_crash': ScenarioDefinition(
                name="Flash Crash",
                type=StressScenarioType.FLASH_CRASH,
                severity=StressSeverity.SEVERE,
                shocks={
                    'equity': -0.15,
                    'crypto': -0.40,
                    'fixed_income': -0.05,
                    'commodity': -0.10,
                    'forex': -0.08
                },
                duration_days=1,
                recovery_rate=0.80,
                description="Flash crash with rapid recovery"
            ),
            'bear_market': ScenarioDefinition(
                name="Bear Market",
                type=StressScenarioType.BEAR_MARKET,
                severity=StressSeverity.MODERATE,
                shocks={
                    'equity': -0.20,
                    'crypto': -0.30,
                    'fixed_income': 0.05,
                    'commodity': -0.15,
                    'forex': -0.10
                },
                duration_days=180,
                recovery_rate=0.60,
                description="Prolonged bear market"
            ),
            'volatility_spike': ScenarioDefinition(
                name="Volatility Spike",
                type=StressScenarioType.VOLATILITY_SPIKE,
                severity=StressSeverity.MODERATE,
                shocks={
                    'equity': -0.10,
                    'crypto': -0.25,
                    'fixed_income': -0.05,
                    'commodity': -0.10,
                    'forex': -0.05
                },
                duration_days=10,
                recovery_rate=0.70,
                description="Volatility spike with VIX surge"
            ),
            'liquidity_crisis': ScenarioDefinition(
                name="Liquidity Crisis",
                type=StressScenarioType.LIQUIDITY_CRISIS,
                severity=StressSeverity.SEVERE,
                shocks={
                    'equity': -0.25,
                    'crypto': -0.45,
                    'fixed_income': -0.15,
                    'commodity': -0.20,
                    'forex': -0.12
                },
                duration_days=45,
                recovery_rate=0.40,
                description="Liquidity crisis with widening spreads"
            ),
            'interest_rate_hike': ScenarioDefinition(
                name="Interest Rate Hike",
                type=StressScenarioType.INTEREST_RATE_HIKE,
                severity=StressSeverity.MODERATE,
                shocks={
                    'equity': -0.15,
                    'crypto': -0.20,
                    'fixed_income': -0.20,
                    'commodity': 0.10,
                    'forex': 0.10
                },
                duration_days=60,
                recovery_rate=0.50,
                description="Sharp interest rate increase"
            ),
            'currency_crisis': ScenarioDefinition(
                name="Currency Crisis",
                type=StressScenarioType.CURRENCY_CRISIS,
                severity=StressSeverity.SEVERE,
                shocks={
                    'equity': -0.20,
                    'crypto': -0.30,
                    'fixed_income': -0.10,
                    'commodity': -0.10,
                    'forex': -0.30
                },
                duration_days=30,
                recovery_rate=0.40,
                description="Major currency devaluation"
            ),
            'systemic_crisis': ScenarioDefinition(
                name="Systemic Crisis",
                type=StressScenarioType.SYSTEMIC_CRISIS,
                severity=StressSeverity.EXTREME,
                shocks={
                    'equity': -0.40,
                    'crypto': -0.60,
                    'fixed_income': -0.25,
                    'commodity': -0.30,
                    'forex': -0.20
                },
                duration_days=90,
                recovery_rate=0.25,
                description="Systemic financial crisis"
            )
        }
        
        for key, scenario in default_scenarios.items():
            self._scenarios[key] = scenario

    def _init_historical_scenarios(self) -> None:
        """Initialize historical scenarios"""
        historical = [
            HistoricalScenario(
                name="2008 Financial Crisis",
                date=datetime(2008, 9, 15),
                market="Global",
                description="Lehman Brothers collapse triggered global financial crisis",
                shocks={
                    'equity': -0.45,
                    'crypto': 0.0,
                    'fixed_income': -0.15,
                    'commodity': -0.35,
                    'forex': -0.10
                },
                duration_days=90,
                recovery_days=365
            ),
            HistoricalScenario(
                name="COVID-19 Crash 2020",
                date=datetime(2020, 3, 9),
                market="Global",
                description="Pandemic-induced market crash",
                shocks={
                    'equity': -0.35,
                    'crypto': -0.50,
                    'fixed_income': -0.10,
                    'commodity': -0.30,
                    'forex': -0.08
                },
                duration_days=30,
                recovery_days=120
            ),
            HistoricalScenario(
                name="Black Monday 1987",
                date=datetime(1987, 10, 19),
                market="US",
                description="Largest one-day percentage decline in US stock market history",
                shocks={
                    'equity': -0.22,
                    'crypto': 0.0,
                    'fixed_income': 0.05,
                    'commodity': -0.10,
                    'forex': -0.05
                },
                duration_days=1,
                recovery_days=90
            ),
            HistoricalScenario(
                name="Dot-com Bubble 2000",
                date=datetime(2000, 3, 10),
                market="US",
                description="Tech bubble burst",
                shocks={
                    'equity': -0.40,
                    'crypto': 0.0,
                    'fixed_income': 0.10,
                    'commodity': -0.10,
                    'forex': -0.05
                },
                duration_days=180,
                recovery_days=730
            ),
            HistoricalScenario(
                name="European Debt Crisis 2011",
                date=datetime(2011, 7, 21),
                market="Europe",
                description="European sovereign debt crisis",
                shocks={
                    'equity': -0.25,
                    'crypto': 0.0,
                    'fixed_income': -0.20,
                    'commodity': -0.15,
                    'forex': -0.15
                },
                duration_days=60,
                recovery_days=180
            )
        ]
        
        self._historical_scenarios = historical

    # =========================================================================
    # Stress Test Execution
    # =========================================================================

    @retry_async(max_attempts=3, delay=1.0)
    async def run_stress_test(
        self,
        request: StressTestRequest
    ) -> StressTestResponse:
        """
        Run a stress test on a portfolio.
        
        Args:
            request: Stress test request
            
        Returns:
            StressTestResponse: Stress test results
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Generate test ID
            test_id = f"stress_{int(time.time() * 1000)}_{request.portfolio_id}"
            
            # Update status
            self._tests[test_id] = {
                'status': StressTestStatus.RUNNING,
                'request': request,
                'started_at': datetime.utcnow()
            }
            
            # Build context
            context = await self._build_context(request)
            
            # Run stress test
            results = await self._execute_stress_test(context)
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                request,
                results,
                context
            )
            
            # Create response
            response = StressTestResponse(
                test_id=test_id,
                portfolio_id=request.portfolio_id,
                scenario_type=request.scenario_type,
                severity=request.severity,
                status=StressTestStatus.COMPLETED,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                summary=results.get('summary', {}),
                results=results.get('scenarios', {}),
                risk_metrics=results.get('risk_metrics', {}),
                recommendations=recommendations,
                worst_case_loss=results.get('worst_case_loss', 0),
                worst_case_loss_pct=results.get('worst_case_loss_pct', 0),
                expected_loss=results.get('expected_loss', 0),
                expected_loss_pct=results.get('expected_loss_pct', 0),
                survival_probability=results.get('survival_probability', 0),
                capital_required=results.get('capital_required', 0),
                time_to_recovery=results.get('time_to_recovery')
            )
            
            # Store result
            self._tests[test_id]['status'] = StressTestStatus.COMPLETED
            self._tests[test_id]['response'] = response
            
            logger.info(f"Stress test {test_id} completed")
            return response
            
        except Exception as e:
            logger.error(f"Error running stress test: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Stress test failed: {str(e)}"
            )

    async def _validate_request(self, request: StressTestRequest) -> None:
        """Validate stress test request"""
        # Validate portfolio exists
        portfolio = await self.portfolio_repo.get_by_id(request.portfolio_id)
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {request.portfolio_id} not found"
            )
        
        # Validate custom scenario if provided
        if request.custom_scenario:
            if 'shocks' not in request.custom_scenario:
                raise ValueError("Custom scenario must include 'shocks'")
            if not request.custom_scenario.get('shocks'):
                raise ValueError("Custom scenario shocks cannot be empty")

    async def _build_context(
        self,
        request: StressTestRequest
    ) -> StressTestContext:
        """Build context for stress testing"""
        # Get portfolio data
        portfolio = await self.portfolio_repo.get_by_id(request.portfolio_id)
        positions = await self.position_repo.get_by_portfolio_id(request.portfolio_id)
        trades = await self.trade_repo.get_by_portfolio_id(
            request.portfolio_id,
            limit=1000
        )
        snapshots = await self.portfolio_repo.get_snapshots(
            request.portfolio_id,
            limit=100
        )
        
        # Get market data
        market_data = await self._get_market_data(positions)
        
        # Calculate correlations
        correlations = await self._calculate_correlations(
            positions,
            market_data
        )
        
        # Calculate volatilities
        volatilities = await self._calculate_volatilities(
            positions,
            market_data
        )
        
        # Get historical returns
        historical_data = await self._get_historical_data(positions)
        
        # Calculate current value
        current_value = sum(float(p.size) * float(p.entry_price) for p in positions)
        
        return StressTestContext(
            portfolio_id=request.portfolio_id,
            scenario_type=request.scenario_type,
            severity=request.severity,
            time_horizon=self._parse_time_horizon(request.time_horizon),
            positions=positions,
            trades=trades,
            snapshots=snapshots,
            market_data=market_data,
            correlations=correlations,
            volatilities=volatilities,
            returns={},
            current_value=current_value,
            historical_data=historical_data,
            confidence_level=request.confidence_level
        )

    async def _get_market_data(
        self,
        positions: List[Any]
    ) -> Dict[str, Any]:
        """Get market data for positions"""
        market_data = {}
        
        for position in positions:
            try:
                symbol = position.symbol
                brokers = self.broker_factory.get_active_brokers()
                for broker in brokers:
                    try:
                        ticker = await broker.get_ticker(symbol)
                        market_data[symbol] = {
                            'price': float(ticker.get('price', 0)),
                            'high': float(ticker.get('high', 0)),
                            'low': float(ticker.get('low', 0)),
                            'volume': float(ticker.get('volume', 0)),
                            'volatility': float(ticker.get('volatility', 0.02)),
                            'asset_class': position.asset_class or 'equity'
                        }
                        break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Error getting market data for {position.symbol}: {e}")
        
        return market_data

    async def _calculate_correlations(
        self,
        positions: List[Any],
        market_data: Dict[str, Any]
    ) -> Dict[str, Dict[str, float]]:
        """Calculate correlation matrix for positions"""
        symbols = [p.symbol for p in positions]
        
        if len(symbols) < 2:
            return {}
        
        correlations = {}
        returns_by_symbol = {}
        
        for symbol in symbols:
            returns = await self._get_historical_returns(symbol, limit=252)
            if returns:
                returns_by_symbol[symbol] = returns
        
        if len(returns_by_symbol) < 2:
            return {}
        
        symbols_list = list(returns_by_symbol.keys())
        
        for i, sym1 in enumerate(symbols_list):
            correlations[sym1] = {}
            for j, sym2 in enumerate(symbols_list):
                if i == j:
                    correlations[sym1][sym2] = 1.0
                else:
                    returns1 = returns_by_symbol.get(sym1, [])
                    returns2 = returns_by_symbol.get(sym2, [])
                    
                    if returns1 and returns2:
                        min_len = min(len(returns1), len(returns2))
                        corr = np.corrcoef(returns1[:min_len], returns2[:min_len])[0, 1]
                        correlations[sym1][sym2] = float(corr) if not np.isnan(corr) else 0.0
                    else:
                        correlations[sym1][sym2] = 0.0
        
        return correlations

    async def _calculate_volatilities(
        self,
        positions: List[Any],
        market_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate volatilities for positions"""
        volatilities = {}
        
        for position in positions:
            symbol = position.symbol
            if symbol in market_data:
                vol = market_data[symbol].get('volatility', 0.02)
            else:
                # Calculate from historical data
                returns = await self._get_historical_returns(symbol, limit=30)
                vol = np.std(returns) * np.sqrt(252) if returns else 0.02
            
            volatilities[symbol] = float(vol)
        
        return volatilities

    async def _get_historical_returns(
        self,
        symbol: str,
        limit: int = 252
    ) -> List[float]:
        """Get historical returns for a symbol"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    prices = await broker.get_historical_prices(
                        symbol,
                        interval='1d',
                        limit=limit + 1
                    )
                    if prices and len(prices) > 1:
                        returns = [(prices[i] - prices[i-1]) / prices[i-1] 
                                  for i in range(1, len(prices))]
                        return returns
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting historical returns for {symbol}: {e}")
        
        # Generate mock returns
        return list(np.random.normal(0, 0.02, limit))

    async def _get_historical_data(
        self,
        positions: List[Any]
    ) -> pd.DataFrame:
        """Get historical data for positions"""
        data = {}
        
        for position in positions:
            symbol = position.symbol
            returns = await self._get_historical_returns(symbol, limit=252)
            if returns:
                data[symbol] = returns
        
        if not data:
            # Generate mock data
            for position in positions:
                data[position.symbol] = list(np.random.normal(0, 0.02, 252))
        
        return pd.DataFrame(data)

    def _parse_time_horizon(self, time_horizon: str) -> int:
        """Parse time horizon string to days"""
        mapping = {
            '1h': 1/24,
            '4h': 4/24,
            '1d': 1,
            '1w': 7,
            '1m': 30,
            '3m': 90,
            '6m': 180,
            '1y': 365
        }
        return int(mapping.get(time_horizon, 1))

    # =========================================================================
    # Stress Test Execution
    # =========================================================================

    async def _execute_stress_test(
        self,
        context: StressTestContext
    ) -> Dict[str, Any]:
        """
        Execute stress test based on context.
        
        Args:
            context: Stress test context
            
        Returns:
            Dict[str, Any]: Stress test results
        """
        results = {
            'scenarios': {},
            'summary': {},
            'risk_metrics': {},
            'worst_case_loss': 0,
            'worst_case_loss_pct': 0,
            'expected_loss': 0,
            'expected_loss_pct': 0,
            'survival_probability': 0,
            'capital_required': 0,
            'time_to_recovery': None
        }
        
        # Run scenario-based stress test
        scenario_result = await self._run_scenario_test(context)
        results['scenarios'][context.scenario_type.value] = scenario_result.__dict__
        
        # Run Monte Carlo simulation if requested
        if context.monte_carlo_simulations > 0:
            mc_result = await self._run_monte_carlo(context)
            results['monte_carlo'] = mc_result.__dict__
            results['survival_probability'] = mc_result.survival_probability
        
        # Calculate risk metrics
        risk_metrics = await self._calculate_risk_metrics(context, scenario_result)
        results['risk_metrics'] = risk_metrics
        
        # Calculate summary statistics
        results['summary'] = self._calculate_summary(context, scenario_result, risk_metrics)
        
        # Calculate worst-case and expected losses
        results['worst_case_loss'] = scenario_result.loss
        results['worst_case_loss_pct'] = scenario_result.loss_pct
        results['expected_loss'] = scenario_result.loss * 0.5
        results['expected_loss_pct'] = scenario_result.loss_pct * 0.5
        results['capital_required'] = scenario_result.loss * 1.2  # 20% buffer
        
        return results

    # -------------------------------------------------------------------------
    # Scenario Testing
    # -------------------------------------------------------------------------

    async def _run_scenario_test(
        self,
        context: StressTestContext
    ) -> ScenarioResult:
        """
        Run scenario-based stress test.
        
        Args:
            context: Stress test context
            
        Returns:
            ScenarioResult: Scenario test results
        """
        # Get scenario definition
        scenario = await self._get_scenario(context)
        
        # Apply shocks to positions
        shocks = scenario.shocks
        total_loss = 0
        position_impacts = {}
        
        for position in context.positions:
            symbol = position.symbol
            asset_class = self._get_asset_class(symbol)
            
            # Get shock for asset class
            shock = shocks.get(asset_class, -0.10)  # Default 10% shock
            
            # Adjust shock based on correlation
            if context.correlations:
                shock = self._apply_correlation_adjustment(
                    shock,
                    symbol,
                    context.correlations,
                    context.volatilities
                )
            
            # Calculate impact
            position_value = float(position.size) * float(position.entry_price)
            position_loss = position_value * shock
            total_loss += position_loss
            
            position_impacts[symbol] = {
                'value': position_value,
                'shock': shock,
                'loss': position_loss,
                'loss_pct': shock
            }
        
        # Calculate portfolio impact
        current_value = context.current_value
        loss_pct = total_loss / current_value if current_value > 0 else 0
        
        # Calculate recovery time
        recovery_time = self._estimate_recovery_time(
            loss_pct,
            scenario.recovery_rate
        )
        
        # Calculate VaR and CVaR
        var = loss_pct * context.confidence_level
        cvar = loss_pct * (1 + context.confidence_level) / 2
        
        return ScenarioResult(
            scenario_name=scenario.name,
            scenario_type=scenario.type.value,
            severity=scenario.severity.value,
            loss=total_loss,
            loss_pct=loss_pct,
            pnl=-total_loss,
            pnl_pct=-loss_pct,
            var=var,
            cvar=cvar,
            max_drawdown=loss_pct,
            recovery_time=recovery_time,
            capital_impact=total_loss,
            risk_score=loss_pct * 100,
            details={
                'position_impacts': position_impacts,
                'shocks': shocks,
                'duration_days': scenario.duration_days,
                'recovery_rate': scenario.recovery_rate
            }
        )

    async def _get_scenario(
        self,
        context: StressTestContext
    ) -> ScenarioDefinition:
        """Get scenario definition"""
        # Check if custom scenario provided
        if context.custom_scenario:
            return ScenarioDefinition(
                name=context.custom_scenario.get('name', 'Custom Scenario'),
                type=context.scenario_type,
                severity=context.severity,
                shocks=context.custom_scenario.get('shocks', {}),
                duration_days=context.custom_scenario.get('duration_days', 30),
                recovery_rate=context.custom_scenario.get('recovery_rate', 0.5),
                description=context.custom_scenario.get('description', 'Custom stress scenario')
            )
        
        # Get default scenario by type and severity
        scenario_key = f"{context.scenario_type.value}_{context.severity.value}"
        
        if scenario_key in self._scenarios:
            return self._scenarios[scenario_key]
        
        # Try by type only
        for key, scenario in self._scenarios.items():
            if scenario.type == context.scenario_type:
                return scenario
        
        # Return default
        return self._scenarios.get('market_crash_severe')

    def _get_asset_class(self, symbol: str) -> str:
        """Get asset class for symbol"""
        crypto_symbols = ['BTC', 'ETH', 'ADA', 'DOT', 'SOL', 'DOGE', 'XRP']
        equity_symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA']
        fixed_income_symbols = ['TLT', 'IEF', 'SHY', 'BND', 'AGG']
        commodity_symbols = ['GLD', 'SLV', 'USO', 'DBC', 'UNG']
        forex_symbols = ['FXE', 'FXB', 'FXY', 'UUP']
        
        symbol_upper = symbol.upper()
        
        if any(crypto in symbol_upper for crypto in crypto_symbols):
            return 'crypto'
        elif any(equity in symbol_upper for equity in equity_symbols):
            return 'equity'
        elif any(fixed in symbol_upper for fixed in fixed_income_symbols):
            return 'fixed_income'
        elif any(commodity in symbol_upper for commodity in commodity_symbols):
            return 'commodity'
        elif any(forex in symbol_upper for forex in forex_symbols):
            return 'forex'
        else:
            return 'equity'

    def _apply_correlation_adjustment(
        self,
        shock: float,
        symbol: str,
        correlations: Dict[str, Dict[str, float]],
        volatilities: Dict[str, float]
    ) -> float:
        """Apply correlation-based adjustment to shock"""
        if symbol not in volatilities:
            return shock
        
        # Adjust shock based on correlation with market
        total_correlation = 0
        count = 0
        
        for other_symbol, corr in correlations.get(symbol, {}).items():
            if other_symbol != symbol:
                total_correlation += abs(corr)
                count += 1
        
        if count > 0:
            avg_correlation = total_correlation / count
            # Higher correlation = stronger shock propagation
            shock = shock * (1 + avg_correlation * 0.5)
        
        return shock

    def _estimate_recovery_time(
        self,
        loss_pct: float,
        recovery_rate: float
    ) -> float:
        """Estimate time to recover from loss"""
        if loss_pct <= 0:
            return 0
        
        # Basic recovery time estimation
        # Time = -ln(1 - loss_pct) / recovery_rate
        recovery_time = -np.log(1 - loss_pct) / recovery_rate
        
        return float(max(recovery_time, 0))

    # -------------------------------------------------------------------------
    # Monte Carlo Simulation
    # -------------------------------------------------------------------------

    async def _run_monte_carlo(
        self,
        context: StressTestContext
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.
        
        Args:
            context: Stress test context
            
        Returns:
            MonteCarloResult: Monte Carlo results
        """
        n_simulations = context.monte_carlo_simulations or 10000
        
        # Get returns distribution
        returns = await self._get_returns_distribution(context)
        
        if not returns:
            returns = list(np.random.normal(0, 0.02, 1000))
        
        # Simulate
        simulated_returns = []
        
        for _ in range(n_simulations):
            # Sample from returns distribution
            if len(returns) > 0:
                sampled_return = np.random.choice(returns)
            else:
                sampled_return = np.random.normal(0, 0.02)
            
            simulated_returns.append(sampled_return)
        
        # Calculate statistics
        mean = np.mean(simulated_returns)
        std = np.std(simulated_returns)
        var = np.percentile(simulated_returns, (1 - context.confidence_level) * 100)
        cvar = np.mean([r for r in simulated_returns if r <= var])
        
        # Calculate percentiles
        percentiles = {
            '1%': np.percentile(simulated_returns, 1),
            '5%': np.percentile(simulated_returns, 5),
            '10%': np.percentile(simulated_returns, 10),
            '25%': np.percentile(simulated_returns, 25),
            '50%': np.percentile(simulated_returns, 50),
            '75%': np.percentile(simulated_returns, 75),
            '90%': np.percentile(simulated_returns, 90),
            '95%': np.percentile(simulated_returns, 95),
            '99%': np.percentile(simulated_returns, 99)
        }
        
        # Calculate max loss
        max_loss = min(simulated_returns) if simulated_returns else 0
        max_loss_pct = abs(max_loss)
        
        # Survival probability (probability of positive return)
        survival_probability = sum(1 for r in simulated_returns if r > 0) / len(simulated_returns) if simulated_returns else 0
        
        # Confidence interval
        ci_lower = np.percentile(simulated_returns, (1 - context.confidence_level) * 100 / 2)
        ci_upper = np.percentile(simulated_returns, (1 + context.confidence_level) * 100 / 2)
        
        return MonteCarloResult(
            mean=float(mean),
            std=float(std),
            var=float(abs(var)),
            cvar=float(abs(cvar)),
            max_loss=float(abs(max_loss)),
            max_loss_pct=float(max_loss_pct),
            percentiles=percentiles,
            distribution=simulated_returns,
            survival_probability=float(survival_probability),
            confidence_interval=(float(ci_lower), float(ci_upper))
        )

    async def _get_returns_distribution(
        self,
        context: StressTestContext
    ) -> List[float]:
        """Get returns distribution for Monte Carlo"""
        # Combine historical returns from positions
        all_returns = []
        
        for position in context.positions:
            symbol = position.symbol
            returns = await self._get_historical_returns(symbol, limit=252)
            if returns:
                all_returns.extend(returns)
        
        if not all_returns:
            # Generate synthetic returns
            all_returns = list(np.random.normal(0, 0.02, 1000))
        
        return all_returns

    # -------------------------------------------------------------------------
    # Risk Metrics
    # -------------------------------------------------------------------------

    async def _calculate_risk_metrics(
        self,
        context: StressTestContext,
        scenario_result: ScenarioResult
    ) -> Dict[str, Any]:
        """Calculate risk metrics for stress test"""
        metrics = {
            'var_95': scenario_result.var * context.current_value,
            'var_95_pct': scenario_result.var,
            'cvar_95': scenario_result.cvar * context.current_value,
            'cvar_95_pct': scenario_result.cvar,
            'expected_shortfall': scenario_result.loss * 0.7,
            'maximum_loss': scenario_result.loss,
            'maximum_loss_pct': scenario_result.loss_pct,
            'drawdown_at_risk': scenario_result.max_drawdown,
            'stress_loss': scenario_result.loss,
            'stress_loss_pct': scenario_result.loss_pct,
            'recovery_time': scenario_result.recovery_time,
            'capital_shortfall': max(0, scenario_result.loss - context.current_value * 0.1)
        }
        
        return metrics

    def _calculate_summary(
        self,
        context: StressTestContext,
        scenario_result: ScenarioResult,
        risk_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate summary statistics"""
        return {
            'total_value': context.current_value,
            'total_exposure': sum(float(p.size) * float(p.entry_price) for p in context.positions),
            'position_count': len(context.positions),
            'scenario_loss': scenario_result.loss,
            'scenario_loss_pct': scenario_result.loss_pct,
            'var_95_pct': risk_metrics.get('var_95_pct', 0),
            'cvar_95_pct': risk_metrics.get('cvar_95_pct', 0),
            'max_drawdown': scenario_result.max_drawdown,
            'recovery_time_days': scenario_result.recovery_time,
            'risk_score': scenario_result.risk_score,
            'survival_probability': scenario_result.risk_score / 100 if scenario_result.risk_score > 0 else 1
        }

    # =========================================================================
    # Recommendations
    # =========================================================================

    async def _generate_recommendations(
        self,
        request: StressTestRequest,
        results: Dict[str, Any],
        context: StressTestContext
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on stress test results"""
        recommendations = []
        
        loss_pct = results.get('worst_case_loss_pct', 0)
        survival = results.get('survival_probability', 0)
        
        # Check loss threshold
        max_loss_threshold = request.max_loss_threshold or 0.20
        
        if loss_pct > max_loss_threshold:
            recommendations.append({
                'action': 'reduce_risk_exposure',
                'severity': 'high',
                'description': f'Stress test shows potential loss of {loss_pct*100:.1f}%, exceeding {max_loss_threshold*100:.1f}% threshold. Consider reducing position sizes.',
                'expected_impact': 'Reduces potential losses by 30-50%'
            })
        
        # Check survival probability
        if survival < 0.5:
            recommendations.append({
                'action': 'increase_capital_buffer',
                'severity': 'high',
                'description': f'Survival probability is {survival*100:.1f}%. Consider increasing capital buffer or adding hedges.',
                'expected_impact': 'Improves survival probability to 70%+'
            })
        
        # Check diversification
        if context.positions and len(context.positions) > 1:
            correlations = context.correlations
            avg_correlation = 0
            count = 0
            
            for sym1, corr_dict in correlations.items():
                for sym2, corr in corr_dict.items():
                    if sym1 != sym2:
                        avg_correlation += abs(corr)
                        count += 1
            
            if count > 0:
                avg_correlation /= count
                
                if avg_correlation > 0.7:
                    recommendations.append({
                        'action': 'improve_diversification',
                        'severity': 'medium',
                        'description': f'Portfolio has high average correlation ({avg_correlation:.2f}). Consider adding uncorrelated assets.',
                        'expected_impact': 'Reduces portfolio volatility by 15-25%'
                    })
        
        # Check concentration
        total_value = context.current_value
        for position in context.positions:
            position_value = float(position.size) * float(position.entry_price)
            concentration = position_value / total_value if total_value > 0 else 0
            
            if concentration > 0.20:
                recommendations.append({
                    'action': 'reduce_concentration',
                    'severity': 'medium',
                    'description': f'Position {position.symbol} represents {concentration*100:.1f}% of portfolio. Consider reducing exposure.',
                    'expected_impact': 'Reduces single-asset risk'
                })
                break
        
        # Check leverage
        leverage = total_value / context.current_value if context.current_value > 0 else 1
        if leverage > 1.5:
            recommendations.append({
                'action': 'reduce_leverage',
                'severity': 'high',
                'description': f'Portfolio leverage is {leverage:.1f}x. Consider reducing leverage to 1.5x or lower.',
                'expected_impact': 'Reduces liquidation risk and stress losses'
            })
        
        # Add hedging recommendations
        if loss_pct > 0.15:
            recommendations.append({
                'action': 'add_hedges',
                'severity': 'medium',
                'description': f'Portfolio shows significant stress losses. Consider adding put options or inverse ETFs as hedges.',
                'expected_impact': 'Limits downside exposure by 40-60%'
            })
        
        return recommendations

    # =========================================================================
    # Historical Scenario Analysis
    # =========================================================================

    async def analyze_historical_scenario(
        self,
        scenario_name: str,
        portfolio_id: str
    ) -> Dict[str, Any]:
        """
        Analyze a historical scenario against a portfolio.
        
        Args:
            scenario_name: Name of historical scenario
            portfolio_id: Portfolio ID
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        # Find scenario
        scenario = None
        for s in self._historical_scenarios:
            if s.name.lower() == scenario_name.lower():
                scenario = s
                break
        
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Historical scenario '{scenario_name}' not found"
            )
        
        # Create stress test request
        request = StressTestRequest(
            portfolio_id=portfolio_id,
            scenario_type=StressScenarioType.CUSTOM,
            severity=StressSeverity.SEVERE,
            custom_scenario={
                'name': scenario.name,
                'shocks': scenario.shocks,
                'duration_days': scenario.duration_days,
                'recovery_rate': 1 / scenario.recovery_days if scenario.recovery_days > 0 else 0.01,
                'description': scenario.description
            }
        )
        
        # Run stress test
        response = await self.run_stress_test(request)
        
        # Add historical context
        result = response.dict()
        result['historical_context'] = {
            'date': scenario.date.isoformat(),
            'market': scenario.market,
            'duration_days': scenario.duration_days,
            'recovery_days': scenario.recovery_days
        }
        
        return result

    # =========================================================================
    # Scenario Management
    # =========================================================================

    async def create_scenario(self, definition: ScenarioDefinition) -> bool:
        """
        Create a custom scenario.
        
        Args:
            definition: Scenario definition
            
        Returns:
            bool: Success indicator
        """
        try:
            key = f"{definition.type.value}_{definition.severity.value}_{int(time.time())}"
            self._scenarios[key] = definition
            logger.info(f"Created scenario: {key}")
            return True
        except Exception as e:
            logger.error(f"Error creating scenario: {e}")
            return False

    async def get_scenario(self, scenario_id: str) -> Optional[ScenarioDefinition]:
        """Get a scenario by ID"""
        return self._scenarios.get(scenario_id)

    async def get_all_scenarios(self) -> List[ScenarioDefinition]:
        """Get all scenarios"""
        return list(self._scenarios.values())

    async def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario"""
        if scenario_id in self._scenarios:
            del self._scenarios[scenario_id]
            return True
        return False

    async def get_historical_scenarios(self) -> List[HistoricalScenario]:
        """Get all historical scenarios"""
        return self._historical_scenarios

    # =========================================================================
    # Test Management
    # =========================================================================

    async def get_test(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get a stress test by ID"""
        return self._tests.get(test_id)

    async def get_all_tests(
        self,
        portfolio_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all stress tests"""
        tests = []
        
        for test_id, test_data in self._tests.items():
            if portfolio_id and test_data.get('request', {}).portfolio_id != portfolio_id:
                continue
            
            tests.append({
                'test_id': test_id,
                'status': test_data.get('status'),
                'started_at': test_data.get('started_at'),
                'completed_at': test_data.get('completed_at'),
                'scenario_type': test_data.get('request', {}).scenario_type,
                'severity': test_data.get('request', {}).severity
            })
        
        tests.sort(key=lambda x: x.get('started_at', datetime.min), reverse=True)
        return tests[:limit]

    async def delete_test(self, test_id: str) -> bool:
        """Delete a stress test"""
        if test_id in self._tests:
            del self._tests[test_id]
            return True
        return False

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the stress tester"""
        self._tests.clear()
        self._scenarios.clear()
        logger.info("StressTester closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/stress-test", tags=["Stress Testing"])


async def get_tester() -> StressTester:
    """Dependency to get StressTester instance"""
    return StressTester()


@router.post("/run", response_model=StressTestResponse)
async def run_stress_test(
    request: StressTestRequest,
    tester: StressTester = Depends(get_tester)
):
    """Run a stress test on a portfolio"""
    return await tester.run_stress_test(request)


@router.get("/{test_id}")
async def get_stress_test(
    test_id: str,
    tester: StressTester = Depends(get_tester)
):
    """Get a stress test by ID"""
    test = await tester.get_test(test_id)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stress test {test_id} not found"
        )
    return test


@router.get("/")
async def get_all_tests(
    portfolio_id: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    tester: StressTester = Depends(get_tester)
):
    """Get all stress tests"""
    return await tester.get_all_tests(portfolio_id, limit)


@router.delete("/{test_id}")
async def delete_test(
    test_id: str,
    tester: StressTester = Depends(get_tester)
):
    """Delete a stress test"""
    success = await tester.delete_test(test_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stress test {test_id} not found"
        )
    return {"success": True}


@router.get("/scenarios")
async def get_scenarios(
    tester: StressTester = Depends(get_tester)
):
    """Get all stress scenarios"""
    return await tester.get_all_scenarios()


@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    tester: StressTester = Depends(get_tester)
):
    """Get a scenario by ID"""
    scenario = await tester.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {scenario_id} not found"
        )
    return scenario


@router.post("/scenarios")
async def create_scenario(
    definition: ScenarioDefinition,
    tester: StressTester = Depends(get_tester)
):
    """Create a custom scenario"""
    success = await tester.create_scenario(definition)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create scenario"
        )
    return {"success": True}


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    tester: StressTester = Depends(get_tester)
):
    """Delete a scenario"""
    success = await tester.delete_scenario(scenario_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {scenario_id} not found"
        )
    return {"success": True}


@router.get("/historical")
async def get_historical_scenarios(
    tester: StressTester = Depends(get_tester)
):
    """Get historical scenarios"""
    return await tester.get_historical_scenarios()


@router.post("/historical/{scenario_name}")
async def analyze_historical_scenario(
    scenario_name: str,
    portfolio_id: str = Query(..., description="Portfolio ID to analyze"),
    tester: StressTester = Depends(get_tester)
):
    """Analyze a historical scenario against a portfolio"""
    return await tester.analyze_historical_scenario(scenario_name, portfolio_id)


@router.get("/scenario-types")
async def get_scenario_types():
    """Get available scenario types"""
    return {
        'types': [
            {'name': t.value, 'description': t.name.replace('_', ' ').title()}
            for t in StressScenarioType
        ]
    }


@router.get("/severity-levels")
async def get_severity_levels():
    """Get available severity levels"""
    return {
        'levels': [
            {'name': s.value, 'description': s.name.title()}
            for s in StressSeverity
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'StressTester',
    'StressScenarioType',
    'StressTestStatus',
    'StressSeverity',
    'StressTestRequest',
    'StressTestResponse',
    'HistoricalScenario',
    'ScenarioDefinition',
    'StressTestContext',
    'ScenarioResult',
    'MonteCarloResult',
    'router'
]

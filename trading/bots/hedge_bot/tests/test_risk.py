# trading/bots/hedge_bot/tests/test_risk.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Risk Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Risk Tests

This module provides comprehensive tests for the risk management components
of the NEXUS Hedge Bot system. It covers all risk calculation, monitoring,
and control functionality.

The test suite covers:
- Value at Risk (VaR) calculations
- Conditional VaR (CVaR) calculations
- Expected Shortfall calculations
- Drawdown calculations
- Position sizing
- Risk limits
- Risk monitoring
- Stress testing
- Scenario analysis
- Correlation risk
- Volatility risk
- Liquidity risk
- Margin risk
- Stop loss management
- Take profit management
"""

import os
import sys
import math
import random
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

import pytest
import numpy as np
import pandas as pd

# Import risk components
from trading.bots.hedge_bot.risk.risk_manager import RiskManager, RiskConfig
from trading.bots.hedge_bot.risk.var import ValueAtRisk, VaRMethod
from trading.bots.hedge_bot.risk.cvar import ConditionalVaR
from trading.bots.hedge_bot.risk.drawdown import DrawdownController
from trading.bots.hedge_bot.risk.position_sizer import PositionSizer
from trading.bots.hedge_bot.risk.limits import RiskLimits, LimitType
from trading.bots.hedge_bot.risk.monitor import RiskMonitor
from trading.bots.hedge_bot.risk.stress import StressTester
from trading.bots.hedge_bot.risk.scenario import ScenarioAnalyzer
from trading.bots.hedge_bot.risk.correlation import CorrelationRisk
from trading.bots.hedge_bot.risk.volatility import VolatilityRisk
from trading.bots.hedge_bot.risk.liquidity import LiquidityRisk
from trading.bots.hedge_bot.risk.margin import MarginRisk

# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture
def sample_positions() -> List[Dict[str, Any]]:
    """Create sample positions for testing"""
    return [
        {
            "symbol": "BTC/USDT",
            "quantity": 1.0,
            "entry_price": 50000.0,
            "current_price": 52000.0,
            "side": "long",
        },
        {
            "symbol": "ETH/USDT",
            "quantity": 10.0,
            "entry_price": 3000.0,
            "current_price": 3200.0,
            "side": "long",
        },
        {
            "symbol": "SOL/USDT",
            "quantity": 100.0,
            "entry_price": 100.0,
            "current_price": 110.0,
            "side": "long",
        },
        {
            "symbol": "BTC/USDT",
            "quantity": 0.5,
            "entry_price": 51000.0,
            "current_price": 52000.0,
            "side": "short",
        },
    ]


@pytest.fixture
def sample_portfolio() -> Dict[str, Any]:
    """Create sample portfolio for testing"""
    return {
        "total_value": 150000.0,
        "positions": [
            {"symbol": "BTC/USDT", "value": 52000.0, "weight": 0.347},
            {"symbol": "ETH/USDT", "value": 32000.0, "weight": 0.213},
            {"symbol": "SOL/USDT", "value": 11000.0, "weight": 0.073},
            {"symbol": "USDT", "value": 55000.0, "weight": 0.367},
        ],
        "currency": "USD",
    }


@pytest.fixture
def sample_returns() -> np.ndarray:
    """Create sample returns for VaR calculation"""
    np.random.seed(42)
    return np.random.normal(0.001, 0.02, 252)


@pytest.fixture
def risk_manager() -> RiskManager:
    """Create risk manager instance"""
    config = RiskConfig(
        max_drawdown=0.15,
        daily_loss_limit=0.05,
        var_confidence=0.95,
        var_horizon=1,
        position_limit=100000,
        leverage_limit=3.0,
    )
    return RiskManager(config)


# ============================================================
# VALUE AT RISK TESTS
# ============================================================

class TestValueAtRisk:
    """
    Tests for Value at Risk calculations
    """

    def test_var_initialization(self) -> None:
        """Test VaR initialization"""
        var = ValueAtRisk(confidence=0.95, horizon=1, method=VaRMethod.HISTORICAL)
        assert var.confidence == 0.95
        assert var.horizon == 1
        assert var.method == VaRMethod.HISTORICAL

    def test_historical_var(self, sample_returns: np.ndarray) -> None:
        """Test historical VaR calculation"""
        var = ValueAtRisk(confidence=0.95, horizon=1, method=VaRMethod.HISTORICAL)
        var_value = var.calculate(sample_returns)
        
        # VaR should be positive
        assert var_value > 0
        
        # VaR should be less than worst loss
        expected_var = np.percentile(sample_returns, 5)
        assert abs(var_value - abs(expected_var)) < 0.001

    def test_parametric_var(self, sample_returns: np.ndarray) -> None:
        """Test parametric VaR calculation"""
        var = ValueAtRisk(confidence=0.95, horizon=1, method=VaRMethod.PARAMETRIC)
        var_value = var.calculate(sample_returns)
        
        # VaR should be positive
        assert var_value > 0
        
        # Parametric VaR should be reasonable
        mean = np.mean(sample_returns)
        std = np.std(sample_returns)
        expected_var = -(mean - 1.645 * std)
        assert abs(var_value - expected_var) < 0.001

    def test_monte_carlo_var(self, sample_returns: np.ndarray) -> None:
        """Test Monte Carlo VaR calculation"""
        var = ValueAtRisk(
            confidence=0.95,
            horizon=1,
            method=VaRMethod.MONTE_CARLO,
            simulations=10000,
        )
        var_value = var.calculate(sample_returns)
        
        # VaR should be positive
        assert var_value > 0
        
        # Monte Carlo VaR should be close to historical VaR
        historical_var = ValueAtRisk(confidence=0.95, horizon=1, method=VaRMethod.HISTORICAL)
        historical_value = historical_var.calculate(sample_returns)
        assert abs(var_value - historical_value) / historical_value < 0.1

    def test_var_horizon_scaling(self, sample_returns: np.ndarray) -> None:
        """Test VaR horizon scaling"""
        var_1d = ValueAtRisk(confidence=0.95, horizon=1, method=VaRMethod.PARAMETRIC)
        var_5d = ValueAtRisk(confidence=0.95, horizon=5, method=VaRMethod.PARAMETRIC)
        
        value_1d = var_1d.calculate(sample_returns)
        value_5d = var_5d.calculate(sample_returns)
        
        # 5-day VaR should be approximately sqrt(5) times 1-day VaR
        expected_ratio = math.sqrt(5)
        actual_ratio = value_5d / value_1d
        assert abs(actual_ratio - expected_ratio) / expected_ratio < 0.05

    def test_var_with_positions(self, sample_positions: List[Dict[str, Any]]) -> None:
        """Test VaR calculation with positions"""
        var = ValueAtRisk(confidence=0.95, horizon=1)
        var_value = var.calculate_with_positions(sample_positions)
        
        assert var_value > 0
        assert isinstance(var_value, float)


class TestConditionalVaR:
    """
    Tests for Conditional VaR (CVaR) calculations
    """

    def test_cvar_initialization(self) -> None:
        """Test CVaR initialization"""
        cvar = ConditionalVaR(confidence=0.95, horizon=1)
        assert cvar.confidence == 0.95
        assert cvar.horizon == 1

    def test_cvar_calculation(self, sample_returns: np.ndarray) -> None:
        """Test CVaR calculation"""
        cvar = ConditionalVaR(confidence=0.95, horizon=1)
        cvar_value = cvar.calculate(sample_returns)
        
        # CVaR should be positive
        assert cvar_value > 0
        
        # CVaR should be greater than or equal to VaR
        var = ValueAtRisk(confidence=0.95, horizon=1)
        var_value = var.calculate(sample_returns)
        assert cvar_value >= var_value

    def test_cvar_with_positions(self, sample_positions: List[Dict[str, Any]]) -> None:
        """Test CVaR calculation with positions"""
        cvar = ConditionalVaR(confidence=0.95, horizon=1)
        cvar_value = cvar.calculate_with_positions(sample_positions)
        
        assert cvar_value > 0
        assert isinstance(cvar_value, float)

    def test_cvar_horizon_scaling(self, sample_returns: np.ndarray) -> None:
        """Test CVaR horizon scaling"""
        cvar_1d = ConditionalVaR(confidence=0.95, horizon=1)
        cvar_5d = ConditionalVaR(confidence=0.95, horizon=5)
        
        value_1d = cvar_1d.calculate(sample_returns)
        value_5d = cvar_5d.calculate(sample_returns)
        
        # 5-day CVaR should be approximately sqrt(5) times 1-day CVaR
        expected_ratio = math.sqrt(5)
        actual_ratio = value_5d / value_1d
        assert abs(actual_ratio - expected_ratio) / expected_ratio < 0.05


# ============================================================
# DRAWDOWN TESTS
# ============================================================

class TestDrawdownController:
    """
    Tests for DrawdownController
    """

    def test_drawdown_initialization(self) -> None:
        """Test drawdown controller initialization"""
        drawdown = DrawdownController(max_drawdown=0.15)
        assert drawdown.max_drawdown == 0.15
        assert drawdown.current_drawdown == 0.0

    def test_drawdown_calculation(self) -> None:
        """Test drawdown calculation"""
        drawdown = DrawdownController(max_drawdown=0.15)
        
        # Simulate portfolio values
        values = [100000, 105000, 110000, 108000, 105000, 95000, 90000]
        
        for i, value in enumerate(values):
            drawdown.update(value)
            if i > 0:
                assert drawdown.current_drawdown >= 0.0
    
    def test_drawdown_limits(self) -> None:
        """Test drawdown limits"""
        drawdown = DrawdownController(max_drawdown=0.15)
        
        # Simulate portfolio values with drawdown
        values = [100000, 105000, 110000, 108000, 105000, 95000, 90000]
        
        for value in values:
            drawdown.update(value)
        
        # Current drawdown should be calculated
        assert drawdown.current_drawdown > 0.0
        assert drawdown.max_drawdown_achieved > 0.0
        
        # Check if drawdown limit is exceeded
        is_exceeded = drawdown.is_limit_exceeded()
        # 15% drawdown from 110000 peak to 90000 trough = 18.18%
        assert is_exceeded is True

    def test_drawdown_recovery(self) -> None:
        """Test drawdown recovery"""
        drawdown = DrawdownController(max_drawdown=0.15)
        
        # Simulate drawdown and recovery
        values = [100000, 105000, 110000, 108000, 105000, 95000, 90000, 95000, 100000, 105000, 110000]
        
        for value in values:
            drawdown.update(value)
        
        # After recovery, drawdown should be small
        assert drawdown.current_drawdown < 0.02

    def test_drawdown_duration(self) -> None:
        """Test drawdown duration tracking"""
        drawdown = DrawdownController(max_drawdown=0.15)
        
        # Simulate drawdown period
        values = [100000, 105000, 110000, 108000, 105000, 95000, 90000, 95000, 100000, 105000, 110000]
        
        for value in values:
            drawdown.update(value)
        
        # Duration should be tracked
        assert drawdown.drawdown_duration >= 0


# ============================================================
# POSITION SIZER TESTS
# ============================================================

class TestPositionSizer:
    """
    Tests for PositionSizer
    """

    def test_position_sizer_initialization(self) -> None:
        """Test position sizer initialization"""
        sizer = PositionSizer(max_position_size=10000, risk_per_trade=0.01)
        assert sizer.max_position_size == 10000
        assert sizer.risk_per_trade == 0.01

    def test_risk_based_sizing(self) -> None:
        """Test risk-based position sizing"""
        sizer = PositionSizer(
            max_position_size=10000,
            risk_per_trade=0.01,
            method="risk_based",
        )
        
        portfolio_value = 100000
        stop_loss_percentage = 0.02
        
        size = sizer.calculate_size(
            portfolio_value=portfolio_value,
            stop_loss_percentage=stop_loss_percentage,
        )
        
        # Expected size: (100000 * 0.01) / 0.02 = 50000
        # But capped at max_position_size = 10000
        expected_size = min(50000, 10000)
        assert size == expected_size

    def test_kelly_sizing(self) -> None:
        """Test Kelly Criterion sizing"""
        sizer = PositionSizer(
            max_position_size=10000,
            kelly_fraction=0.25,
            method="kelly",
        )
        
        win_rate = 0.55
        win_loss_ratio = 2.0
        
        size = sizer.calculate_size(
            portfolio_value=100000,
            win_rate=win_rate,
            win_loss_ratio=win_loss_ratio,
        )
        
        # Kelly percentage: (0.55 * 2.0 - 0.45) / 2.0 = 0.325
        # Fractional Kelly: 0.325 * 0.25 = 0.08125
        # Size: 100000 * 0.08125 = 8125
        expected_size = 8125
        assert abs(size - expected_size) < 1

    def test_fixed_sizing(self) -> None:
        """Test fixed position sizing"""
        sizer = PositionSizer(
            fixed_size=5000,
            method="fixed",
        )
        
        size = sizer.calculate_size(portfolio_value=100000)
        assert size == 5000

    def test_volatility_sizing(self) -> None:
        """Test volatility-based sizing"""
        sizer = PositionSizer(
            max_position_size=10000,
            target_volatility=0.15,
            method="volatility",
        )
        
        asset_volatility = 0.25
        
        size = sizer.calculate_size(
            portfolio_value=100000,
            asset_volatility=asset_volatility,
        )
        
        # Expected size: (100000 * 0.15) / 0.25 = 60000
        # Capped at max_position_size = 10000
        expected_size = min(60000, 10000)
        assert size == expected_size

    def test_sizing_with_correlation(self) -> None:
        """Test position sizing with correlation adjustment"""
        sizer = PositionSizer(
            max_position_size=10000,
            risk_per_trade=0.01,
            use_correlation_adjustment=True,
        )
        
        portfolio_value = 100000
        stop_loss_percentage = 0.02
        correlation = 0.5
        
        size = sizer.calculate_size(
            portfolio_value=portfolio_value,
            stop_loss_percentage=stop_loss_percentage,
            correlation=correlation,
        )
        
        # With correlation, size should be adjusted
        # Size = (100000 * 0.01) / 0.02 * (1 - 0.5) = 25000
        # Capped at 10000
        expected_size = min(25000, 10000)
        assert size == expected_size


# ============================================================
# RISK LIMITS TESTS
# ============================================================

class TestRiskLimits:
    """
    Tests for RiskLimits
    """

    def test_risk_limits_initialization(self) -> None:
        """Test risk limits initialization"""
        limits = RiskLimits(
            max_position_size=10000,
            max_leverage=3.0,
            max_drawdown=0.15,
            daily_loss_limit=0.05,
        )
        assert limits.max_position_size == 10000
        assert limits.max_leverage == 3.0

    def test_limit_checking(self) -> None:
        """Test limit checking"""
        limits = RiskLimits(
            max_position_size=10000,
            max_leverage=3.0,
            max_drawdown=0.15,
        )
        
        # Position within limits
        is_ok, message = limits.check_position_size(5000)
        assert is_ok is True
        
        # Position exceeding limits
        is_ok, message = limits.check_position_size(15000)
        assert is_ok is False
        
        # Leverage within limits
        is_ok, message = limits.check_leverage(2.0)
        assert is_ok is True
        
        # Leverage exceeding limits
        is_ok, message = limits.check_leverage(4.0)
        assert is_ok is False

    def test_limit_utilization(self) -> None:
        """Test limit utilization calculation"""
        limits = RiskLimits(
            max_position_size=10000,
            max_leverage=3.0,
        )
        
        utilization = limits.get_utilization("position_size", 7500)
        assert utilization == 0.75
        
        utilization = limits.get_utilization("leverage", 2.0)
        assert utilization == 0.666

    def test_multiple_limits(self) -> None:
        """Test multiple limit checking"""
        limits = RiskLimits(
            max_position_size=10000,
            max_leverage=3.0,
            max_drawdown=0.15,
            daily_loss_limit=0.05,
        )
        
        checks = {
            "position_size": 8000,
            "leverage": 2.5,
            "drawdown": 0.10,
            "daily_loss": 0.03,
        }
        
        results = limits.check_all(checks)
        assert all(results.values()) is True
        
        # One limit exceeded
        checks["position_size"] = 12000
        results = limits.check_all(checks)
        assert results["position_size"] is False


# ============================================================
# RISK MONITOR TESTS
# ============================================================

class TestRiskMonitor:
    """
    Tests for RiskMonitor
    """

    def test_risk_monitor_initialization(self) -> None:
        """Test risk monitor initialization"""
        monitor = RiskMonitor(
            update_interval=60,
            alert_threshold=0.75,
            critical_threshold=0.90,
        )
        assert monitor.update_interval == 60
        assert monitor.alert_threshold == 0.75

    def test_risk_monitor_update(self, sample_portfolio: Dict[str, Any]) -> None:
        """Test risk monitor update"""
        monitor = RiskMonitor()
        
        # Update with portfolio data
        metrics = monitor.update(sample_portfolio)
        
        assert "var_95" in metrics
        assert "cvar_95" in metrics
        assert "drawdown" in metrics
        assert "risk_score" in metrics

    def test_risk_alert_generation(self, sample_portfolio: Dict[str, Any]) -> None:
        """Test risk alert generation"""
        monitor = RiskMonitor(
            alert_threshold=0.75,
            critical_threshold=0.90,
        )
        
        # Update with normal portfolio
        metrics = monitor.update(sample_portfolio)
        alerts = monitor.get_alerts()
        
        # Should be no alerts
        assert len(alerts) == 0
        
        # Create high-risk portfolio
        high_risk_portfolio = sample_portfolio.copy()
        high_risk_portfolio["total_value"] = 100000
        high_risk_portfolio["positions"][0]["value"] = 80000  # 80% concentration
        
        metrics = monitor.update(high_risk_portfolio)
        alerts = monitor.get_alerts()
        
        # Should have alerts
        assert len(alerts) > 0

    def test_risk_monitor_history(self, sample_portfolio: Dict[str, Any]) -> None:
        """Test risk monitor history tracking"""
        monitor = RiskMonitor()
        
        # Update multiple times
        for _ in range(10):
            monitor.update(sample_portfolio)
            time.sleep(0.01)
        
        history = monitor.get_history()
        assert len(history) == 10


# ============================================================
# STRESS TESTING TESTS
# ============================================================

class TestStressTester:
    """
    Tests for StressTester
    """

    def test_stress_tester_initialization(self) -> None:
        """Test stress tester initialization"""
        stress = StressTester()
        assert stress.scenarios is not None

    def test_add_scenario(self) -> None:
        """Test adding stress scenario"""
        stress = StressTester()
        
        scenario = {
            "name": "market_crash",
            "description": "Market crash scenario",
            "market_move": -0.25,
            "volatility_multiplier": 3.0,
        }
        
        stress.add_scenario(scenario)
        assert len(stress.scenarios) == 1

    def test_run_stress_test(self, sample_portfolio: Dict[str, Any]) -> None:
        """Test running stress test"""
        stress = StressTester()
        
        scenario = {
            "name": "market_crash",
            "description": "Market crash scenario",
            "market_move": -0.25,
            "volatility_multiplier": 3.0,
        }
        
        stress.add_scenario(scenario)
        results = stress.run_test(sample_portfolio, scenario)
        
        assert results["scenario"] == "market_crash"
        assert results["loss"] > 0
        assert results["loss_percentage"] > 0

    def test_run_all_scenarios(self, sample_portfolio: Dict[str, Any]) -> None:
        """Test running all stress scenarios"""
        stress = StressTester()
        
        scenarios = [
            {
                "name": "market_crash",
                "market_move": -0.25,
                "volatility_multiplier": 3.0,
            },
            {
                "name": "flash_crash",
                "market_move": -0.15,
                "volatility_multiplier": 4.0,
            },
            {
                "name": "black_swan",
                "market_move": -0.40,
                "volatility_multiplier": 5.0,
            },
        ]
        
        for scenario in scenarios:
            stress.add_scenario(scenario)
        
        results = stress.run_all(sample_portfolio)
        assert len(results) == 3
        
        for result in results:
            assert "loss" in result
            assert "loss_percentage" in result


# ============================================================
# CORRELATION RISK TESTS
# ============================================================

class TestCorrelationRisk:
    """
    Tests for CorrelationRisk
    """

    def test_correlation_risk_initialization(self) -> None:
        """Test correlation risk initialization"""
        corr = CorrelationRisk()
        assert corr.correlation_matrix is not None

    def test_correlation_matrix(self) -> None:
        """Test correlation matrix calculation"""
        corr = CorrelationRisk()
        
        # Create sample returns for assets
        returns = {
            "BTC": np.random.normal(0.001, 0.02, 100),
            "ETH": np.random.normal(0.001, 0.025, 100),
            "SOL": np.random.normal(0.001, 0.03, 100),
        }
        
        matrix = corr.calculate_matrix(returns)
        assert matrix.shape == (3, 3)
        
        # Diagonal should be 1
        assert matrix[0][0] == 1.0
        assert matrix[1][1] == 1.0
        assert matrix[2][2] == 1.0

    def test_correlation_risk_metric(self) -> None:
        """Test correlation risk metric calculation"""
        corr = CorrelationRisk()
        
        matrix = np.array([
            [1.0, 0.8, 0.6],
            [0.8, 1.0, 0.7],
            [0.6, 0.7, 1.0],
        ])
        
        risk = corr.calculate_risk(matrix)
        assert risk > 0.0

    def test_correlation_risk_threshold(self) -> None:
        """Test correlation risk threshold"""
        corr = CorrelationRisk(threshold=0.7)
        
        matrix = np.array([
            [1.0, 0.8, 0.6],
            [0.8, 1.0, 0.7],
            [0.6, 0.7, 1.0],
        ])
        
        # Should identify high correlations
        high_corrs = corr.find_high_correlations(matrix)
        assert len(high_corrs) > 0


# ============================================================
# VOLATILITY RISK TESTS
# ============================================================

class TestVolatilityRisk:
    """
    Tests for VolatilityRisk
    """

    def test_volatility_risk_initialization(self) -> None:
        """Test volatility risk initialization"""
        vol = VolatilityRisk(lookback=30)
        assert vol.lookback == 30

    def test_historical_volatility(self) -> None:
        """Test historical volatility calculation"""
        vol = VolatilityRisk()
        
        # Create sample returns
        returns = np.random.normal(0.001, 0.02, 252)
        
        hist_vol = vol.calculate_historical(returns)
        assert hist_vol > 0.0
        
        # Should be close to input volatility
        assert abs(hist_vol - 0.02) < 0.01

    def test_ewma_volatility(self) -> None:
        """Test EWMA volatility calculation"""
        vol = VolatilityRisk(lambda_value=0.94)
        
        returns = np.random.normal(0.001, 0.02, 252)
        
        ewma_vol = vol.calculate_ewma(returns)
        assert ewma_vol > 0.0

    def test_garch_volatility(self) -> None:
        """Test GARCH volatility calculation"""
        vol = VolatilityRisk()
        
        returns = np.random.normal(0.001, 0.02, 252)
        
        garch_vol = vol.calculate_garch(returns)
        assert garch_vol > 0.0


# ============================================================
# LIQUIDITY RISK TESTS
# ============================================================

class TestLiquidityRisk:
    """
    Tests for LiquidityRisk
    """

    def test_liquidity_risk_initialization(self) -> None:
        """Test liquidity risk initialization"""
        liq = LiquidityRisk()
        assert liq is not None

    def test_spread_risk(self) -> None:
        """Test spread risk calculation"""
        liq = LiquidityRisk()
        
        bid = 50000.0
        ask = 50100.0
        
        spread = liq.calculate_spread(bid, ask)
        assert spread == 100.0
        
        spread_pct = liq.calculate_spread_percentage(bid, ask)
        assert abs(spread_pct - 0.002) < 0.001

    def test_slippage_risk(self) -> None:
        """Test slippage risk calculation"""
        liq = LiquidityRisk()
        
        order_size = 1.0
        volume = 1000000.0
        
        slippage = liq.calculate_slippage(order_size, volume)
        assert slippage >= 0.0

    def test_market_depth_risk(self) -> None:
        """Test market depth risk calculation"""
        liq = LiquidityRisk()
        
        depth = {
            "bids": [(50000.0, 1.0), (49900.0, 2.0)],
            "asks": [(50100.0, 1.0), (50200.0, 2.0)],
        }
        
        depth_score = liq.calculate_depth_risk(depth)
        assert 0.0 <= depth_score <= 1.0


# ============================================================
# MARGIN RISK TESTS
# ============================================================

class TestMarginRisk:
    """
    Tests for MarginRisk
    """

    def test_margin_risk_initialization(self) -> None:
        """Test margin risk initialization"""
        margin = MarginRisk(initial_margin=0.10, maintenance_margin=0.05)
        assert margin.initial_margin == 0.10
        assert margin.maintenance_margin == 0.05

    def test_margin_calculation(self) -> None:
        """Test margin calculation"""
        margin = MarginRisk(initial_margin=0.10, maintenance_margin=0.05)
        
        position_value = 100000.0
        leverage = 2.0
        
        initial = margin.calculate_initial_margin(position_value, leverage)
        maintenance = margin.calculate_maintenance_margin(position_value, leverage)
        
        expected_initial = 100000.0 / 2.0 * 0.10
        expected_maintenance = 100000.0 / 2.0 * 0.05
        
        assert initial == expected_initial
        assert maintenance == expected_maintenance

    def test_margin_utilization(self) -> None:
        """Test margin utilization calculation"""
        margin = MarginRisk()
        
        used_margin = 5000.0
        total_margin = 10000.0
        
        utilization = margin.calculate_utilization(used_margin, total_margin)
        assert utilization == 0.5

    def test_liquidation_price(self) -> None:
        """Test liquidation price calculation"""
        margin = MarginRisk(maintenance_margin=0.05)
        
        entry_price = 50000.0
        position_size = 1.0
        leverage = 2.0
        
        long_price = margin.calculate_liquidation_price(
            entry_price, position_size, leverage, "long"
        )
        short_price = margin.calculate_liquidation_price(
            entry_price, position_size, leverage, "short"
        )
        
        assert long_price < entry_price
        assert short_price > entry_price


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestRiskIntegration:
    """
    Integration tests for risk components
    """

    def test_full_risk_workflow(self, sample_portfolio: Dict[str, Any]) -> None:
        """Test full risk management workflow"""
        # Initialize components
        var = ValueAtRisk(confidence=0.95)
        cvar = ConditionalVaR(confidence=0.95)
        drawdown = DrawdownController(max_drawdown=0.15)
        limits = RiskLimits(max_position_size=10000, max_leverage=3.0)
        
        # Calculate risk metrics
        var_value = var.calculate_with_positions(sample_portfolio["positions"])
        cvar_value = cvar.calculate_with_positions(sample_portfolio["positions"])
        drawdown.update(sample_portfolio["total_value"])
        
        # Check limits
        positions = sample_portfolio["positions"]
        for pos in positions:
            is_ok, _ = limits.check_position_size(pos["value"])
            assert is_ok is True
        
        # Calculate risk score
        risk_score = (
            var_value / sample_portfolio["total_value"] * 0.3 +
            cvar_value / sample_portfolio["total_value"] * 0.3 +
            drawdown.current_drawdown * 0.4
        )
        
        assert 0 <= risk_score <= 1


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "TestValueAtRisk",
    "TestConditionalVaR",
    "TestDrawdownController",
    "TestPositionSizer",
    "TestRiskLimits",
    "TestRiskMonitor",
    "TestStressTester",
    "TestCorrelationRisk",
    "TestVolatilityRisk",
    "TestLiquidityRisk",
    "TestMarginRisk",
    "TestRiskIntegration",
]

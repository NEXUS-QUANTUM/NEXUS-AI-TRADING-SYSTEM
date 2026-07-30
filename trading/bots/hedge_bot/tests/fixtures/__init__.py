# trading/bots/hedge_bot/tests/fixtures/__init__.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Test Fixtures Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Test Fixtures Module

This module provides comprehensive test fixtures for the NEXUS Hedge Bot
testing suite. It includes data loaders, fixture factories, and utility
functions for creating test data.

The fixtures module supports:
- Loading test data from files (YAML, CSV, JSON)
- Creating mock objects for testing
- Generating synthetic test data
- Fixture factories for common test objects
- Database fixtures
- Exchange fixtures
- Market data fixtures
- Portfolio fixtures
- Strategy fixtures
- Risk fixtures
- Configuration fixtures
"""

import os
import json
import csv
import yaml
import logging
import random
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable, Generator
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import pytest
from unittest.mock import Mock, MagicMock, patch

# Try to import optional dependencies
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS AND PATHS
# ============================================================

FIXTURES_DIR = Path(__file__).parent

# Fixture file mapping
FIXTURE_FILES = {
    "config_test": "config_test.yaml",
    "correlation_matrix": "correlation_matrix.csv",
    "market_data": "market_data.csv",
    "portfolio_data": "portfolio_data.json",
}

# ============================================================
# DATA LOADERS
# ============================================================

class FixtureLoader:
    """
    Test fixture loader
    
    Loads test data from various file formats and provides
    utilities for accessing and manipulating test data.
    """
    
    _instance = None
    _cache: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.fixtures_dir = FIXTURES_DIR
        self._loaded = False
        
    def load_all(self) -> None:
        """Load all test fixtures"""
        if self._loaded:
            return
            
        self._load_config_fixtures()
        self._load_correlation_fixtures()
        self._load_market_data_fixtures()
        self._load_portfolio_fixtures()
        
        self._loaded = True
        logger.info(f"Loaded all test fixtures from {self.fixtures_dir}")
    
    def _load_config_fixtures(self) -> None:
        """Load configuration test fixtures"""
        config_path = self.fixtures_dir / "config_test.yaml"
        if config_path.exists():
            with open(config_path, "r") as f:
                self._cache["config"] = yaml.safe_load(f)
                
    def _load_correlation_fixtures(self) -> None:
        """Load correlation matrix test fixtures"""
        corr_path = self.fixtures_dir / "correlation_matrix.csv"
        if corr_path.exists():
            if HAS_PANDAS:
                self._cache["correlation_matrix"] = pd.read_csv(corr_path, index_col=0)
            else:
                with open(corr_path, "r") as f:
                    reader = csv.DictReader(f)
                    data = [row for row in reader]
                    self._cache["correlation_matrix"] = data
                    
    def _load_market_data_fixtures(self) -> None:
        """Load market data test fixtures"""
        market_path = self.fixtures_dir / "market_data.csv"
        if market_path.exists():
            if HAS_PANDAS:
                self._cache["market_data"] = pd.read_csv(market_path, parse_dates=["timestamp"])
            else:
                with open(market_path, "r") as f:
                    reader = csv.DictReader(f)
                    data = [row for row in reader]
                    self._cache["market_data"] = data
                    
    def _load_portfolio_fixtures(self) -> None:
        """Load portfolio test fixtures"""
        portfolio_path = self.fixtures_dir / "portfolio_data.json"
        if portfolio_path.exists():
            with open(portfolio_path, "r") as f:
                self._cache["portfolio"] = json.load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a fixture by key"""
        self.load_all()
        return self._cache.get(key, default)
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration fixtures"""
        return self.get("config", {})
    
    def get_correlation_matrix(self) -> Any:
        """Get correlation matrix fixtures"""
        return self.get("correlation_matrix", [])
    
    def get_market_data(self) -> Any:
        """Get market data fixtures"""
        return self.get("market_data", [])
    
    def get_portfolio_data(self) -> Dict[str, Any]:
        """Get portfolio data fixtures"""
        return self.get("portfolio", {})
    
    def clear_cache(self) -> None:
        """Clear the fixture cache"""
        self._cache.clear()
        self._loaded = False


# ============================================================
# FIXTURE FACTORIES
# ============================================================

class FixtureFactory:
    """
    Factory for creating test fixtures
    """
    
    @staticmethod
    def create_market_data(
        symbol: str = "BTC/USDT",
        start_date: datetime = None,
        end_date: datetime = None,
        num_points: int = 100,
        base_price: float = 50000.0,
        volatility: float = 0.02,
        trend: float = 0.001,
        random_seed: int = 42
    ) -> List[Dict[str, Any]]:
        """
        Create synthetic market data
        
        Args:
            symbol: Trading pair symbol
            start_date: Start date
            end_date: End date
            num_points: Number of data points
            base_price: Starting price
            volatility: Daily volatility
            trend: Daily trend
            random_seed: Random seed for reproducibility
        
        Returns:
            List of market data dictionaries
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=num_points)
        
        random.seed(random_seed)
        if HAS_NUMPY:
            np.random.seed(random_seed)
        
        data = []
        current_price = base_price
        
        for i in range(num_points):
            timestamp = start_date + timedelta(minutes=i * 60)
            
            # Generate price movement with random walk + trend
            if HAS_NUMPY:
                change = np.random.normal(trend, volatility)
            else:
                change = random.gauss(trend, volatility)
            
            # Calculate OHLC
            open_price = current_price
            close_price = open_price * (1 + change)
            high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, volatility * 0.5)))
            low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, volatility * 0.5)))
            
            # Generate volume
            if HAS_NUMPY:
                volume = int(np.random.lognormal(12, 0.5))
            else:
                volume = int(random.lognormvariate(12, 0.5))
            
            data.append({
                "timestamp": timestamp.isoformat(),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": volume,
                "symbol": symbol,
            })
            
            current_price = close_price
        
        return data
    
    @staticmethod
    def create_position(
        symbol: str = "BTC/USDT",
        side: str = "long",
        quantity: float = 1.0,
        entry_price: float = 50000.0,
        current_price: float = 52000.0,
        status: str = "open"
    ) -> Dict[str, Any]:
        """
        Create a position fixture
        
        Args:
            symbol: Trading pair symbol
            side: Position side (long, short)
            quantity: Position quantity
            entry_price: Entry price
            current_price: Current price
            status: Position status
        
        Returns:
            Position dictionary
        """
        pnl = (current_price - entry_price) * quantity
        if side == "short":
            pnl = (entry_price - current_price) * quantity
            
        return {
            "id": f"pos_{random.randint(100000, 999999)}",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": current_price,
            "unrealized_pnl": round(pnl, 2),
            "unrealized_pnl_percent": round(pnl / (entry_price * quantity), 4),
            "value": round(quantity * current_price, 2),
            "status": status,
            "created_at": datetime.now().isoformat(),
        }
    
    @staticmethod
    def create_order(
        symbol: str = "BTC/USDT",
        side: str = "buy",
        order_type: str = "limit",
        quantity: float = 1.0,
        price: float = 50000.0,
        status: str = "filled"
    ) -> Dict[str, Any]:
        """
        Create an order fixture
        
        Args:
            symbol: Trading pair symbol
            side: Order side (buy, sell)
            order_type: Order type
            quantity: Order quantity
            price: Order price
            status: Order status
        
        Returns:
            Order dictionary
        """
        return {
            "id": f"ord_{random.randint(100000, 999999)}",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "price": price,
            "filled_quantity": quantity if status == "filled" else 0.0,
            "status": status,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    
    @staticmethod
    def create_portfolio(
        positions: List[Dict[str, Any]] = None,
        initial_balance: float = 100000.0,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Create a portfolio fixture
        
        Args:
            positions: List of positions
            initial_balance: Initial balance
            currency: Portfolio currency
        
        Returns:
            Portfolio dictionary
        """
        if positions is None:
            positions = []
            
        total_value = initial_balance
        for pos in positions:
            total_value += pos.get("unrealized_pnl", 0)
            
        return {
            "id": f"portfolio_{random.randint(100000, 999999)}",
            "currency": currency,
            "initial_balance": initial_balance,
            "current_balance": total_value,
            "total_value": total_value,
            "total_pnl": total_value - initial_balance,
            "total_pnl_percent": (total_value - initial_balance) / initial_balance,
            "positions": positions,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    
    @staticmethod
    def create_strategy(
        name: str = "delta_hedging",
        status: str = "running",
        hedge_ratio: float = 0.50,
        positions: int = 5
    ) -> Dict[str, Any]:
        """
        Create a strategy fixture
        
        Args:
            name: Strategy name
            status: Strategy status
            hedge_ratio: Hedge ratio
            positions: Number of positions
        
        Returns:
            Strategy dictionary
        """
        return {
            "name": name,
            "status": status,
            "metrics": {
                "hedge_ratio": hedge_ratio,
                "effective_hedge": hedge_ratio * 0.95,
                "volatility": 0.20,
                "correlation": 0.65,
            },
            "positions": {
                "total": positions,
                "hedge": int(positions * 0.4),
            },
            "performance": {
                "daily_pnl": random.randint(-1000, 1000),
                "cumulative_pnl": random.randint(10000, 50000),
                "peak_value": 120000.0,
            },
            "last_update": datetime.now().isoformat(),
        }
    
    @staticmethod
    def create_risk_metrics(
        var_95: float = 25000.0,
        var_99: float = 40000.0,
        cvar_95: float = 35000.0,
        max_drawdown: float = 0.08,
        margin_utilization: float = 0.45
    ) -> Dict[str, Any]:
        """
        Create risk metrics fixture
        
        Args:
            var_95: 95% VaR
            var_99: 99% VaR
            cvar_95: 95% CVaR
            max_drawdown: Maximum drawdown
            margin_utilization: Margin utilization
        
        Returns:
            Risk metrics dictionary
        """
        return {
            "var_95": var_95,
            "var_99": var_99,
            "cvar_95": cvar_95,
            "expected_shortfall": cvar_95 * 0.95,
            "max_drawdown": max_drawdown,
            "current_drawdown": max_drawdown * 0.3,
            "margin_utilization": margin_utilization,
            "liquidation_risk": 0.15,
            "risk_score": 0.35,
            "sharpe_ratio": 1.85,
            "sortino_ratio": 2.10,
            "calmar_ratio": 1.65,
        }


# ============================================================
# MOCK OBJECT FACTORIES
# ============================================================

class MockFactory:
    """
    Factory for creating mock objects for testing
    """
    
    @staticmethod
    def create_mock_exchange() -> Mock:
        """Create a mock exchange"""
        mock = Mock()
        
        # Configure mock methods
        mock.get_ticker.return_value = {
            "symbol": "BTC/USDT",
            "bid": 50000.0,
            "ask": 50100.0,
            "last": 50050.0,
            "volume": 1000000.0,
        }
        
        mock.get_order_book.return_value = {
            "bids": [[50000.0, 1.0], [49900.0, 2.0]],
            "asks": [[50100.0, 1.0], [50200.0, 2.0]],
        }
        
        mock.get_balance.return_value = {
            "BTC": 1.0,
            "USDT": 50000.0,
        }
        
        mock.place_order.return_value = {
            "order_id": "ord_123456",
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 1.0,
            "price": 50000.0,
            "status": "filled",
        }
        
        mock.get_position.return_value = {
            "symbol": "BTC/USDT",
            "side": "long",
            "quantity": 1.0,
            "entry_price": 50000.0,
            "current_price": 52000.0,
            "unrealized_pnl": 2000.0,
        }
        
        mock.get_all_positions.return_value = []
        
        mock.get_historical_data.return_value = []
        
        mock.get_health_status.return_value = {
            "status": "healthy",
            "connected": True,
            "last_check": datetime.now().isoformat(),
        }
        
        return mock
    
    @staticmethod
    def create_mock_risk_manager() -> Mock:
        """Create a mock risk manager"""
        mock = Mock()
        
        mock.calculate_var.return_value = 25000.0
        mock.calculate_cvar.return_value = 35000.0
        mock.calculate_drawdown.return_value = 0.08
        mock.calculate_risk_score.return_value = 0.35
        mock.check_limits.return_value = {"status": "healthy", "breaches": []}
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    @staticmethod
    def create_mock_portfolio() -> Mock:
        """Create a mock portfolio"""
        mock = Mock()
        
        mock.get_total_value.return_value = 125000.0
        mock.get_positions.return_value = []
        mock.get_allocation.return_value = {"crypto": 0.5, "equity": 0.3}
        mock.get_performance.return_value = {"sharpe": 1.85, "returns": []}
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    @staticmethod
    def create_mock_strategy() -> Mock:
        """Create a mock strategy"""
        mock = Mock()
        
        mock.generate_signal.return_value = {"type": "buy", "confidence": 0.8}
        mock.execute_signal.return_value = {"order_id": "ord_123456", "status": "filled"}
        mock.get_status.return_value = {"status": "running", "positions": 5}
        mock.get_performance.return_value = {"pnl": 10000.0, "win_rate": 0.65}
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    @staticmethod
    def create_mock_database() -> Mock:
        """Create a mock database"""
        mock = Mock()
        
        mock.execute_query.return_value = []
        mock.get_connection.return_value = None
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    @staticmethod
    def create_mock_redis() -> Mock:
        """Create a mock Redis client"""
        mock = Mock()
        
        mock.get.return_value = None
        mock.set.return_value = True
        mock.delete.return_value = 1
        mock.publish.return_value = 1
        mock.subscribe.return_value = None
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    @staticmethod
    def create_mock_notifier() -> Mock:
        """Create a mock notifier"""
        mock = Mock()
        
        mock.send_email.return_value = True
        mock.send_telegram.return_value = True
        mock.send_slack.return_value = True
        mock.send_push.return_value = True
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock


# ============================================================
# PYTEST FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def fixture_loader() -> FixtureLoader:
    """Pytest fixture for FixtureLoader"""
    return FixtureLoader()


@pytest.fixture(scope="session")
def fixture_factory() -> FixtureFactory:
    """Pytest fixture for FixtureFactory"""
    return FixtureFactory()


@pytest.fixture(scope="session")
def mock_factory() -> MockFactory:
    """Pytest fixture for MockFactory"""
    return MockFactory()


@pytest.fixture
def sample_market_data() -> List[Dict[str, Any]]:
    """Pytest fixture for sample market data"""
    factory = FixtureFactory()
    return factory.create_market_data(
        symbol="BTC/USDT",
        num_points=24,
        base_price=50000.0,
        volatility=0.01,
        trend=0.0005
    )


@pytest.fixture
def sample_position() -> Dict[str, Any]:
    """Pytest fixture for sample position"""
    factory = FixtureFactory()
    return factory.create_position(
        symbol="BTC/USDT",
        side="long",
        quantity=1.0,
        entry_price=50000.0,
        current_price=52000.0
    )


@pytest.fixture
def sample_portfolio(sample_position) -> Dict[str, Any]:
    """Pytest fixture for sample portfolio"""
    factory = FixtureFactory()
    return factory.create_portfolio(
        positions=[sample_position],
        initial_balance=100000.0
    )


@pytest.fixture
def sample_strategy() -> Dict[str, Any]:
    """Pytest fixture for sample strategy"""
    factory = FixtureFactory()
    return factory.create_strategy(
        name="delta_hedging",
        status="running",
        hedge_ratio=0.50,
        positions=5
    )


@pytest.fixture
def sample_risk_metrics() -> Dict[str, Any]:
    """Pytest fixture for sample risk metrics"""
    factory = FixtureFactory()
    return factory.create_risk_metrics()


@pytest.fixture
def mock_exchange() -> Mock:
    """Pytest fixture for mock exchange"""
    return MockFactory.create_mock_exchange()


@pytest.fixture
def mock_risk_manager() -> Mock:
    """Pytest fixture for mock risk manager"""
    return MockFactory.create_mock_risk_manager()


@pytest.fixture
def mock_portfolio() -> Mock:
    """Pytest fixture for mock portfolio"""
    return MockFactory.create_mock_portfolio()


@pytest.fixture
def mock_strategy() -> Mock:
    """Pytest fixture for mock strategy"""
    return MockFactory.create_mock_strategy()


@pytest.fixture
def mock_database() -> Mock:
    """Pytest fixture for mock database"""
    return MockFactory.create_mock_database()


@pytest.fixture
def mock_redis() -> Mock:
    """Pytest fixture for mock Redis"""
    return MockFactory.create_mock_redis()


@pytest.fixture
def mock_notifier() -> Mock:
    """Pytest fixture for mock notifier"""
    return MockFactory.create_mock_notifier()


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def get_fixture(key: str, default: Any = None) -> Any:
    """Get a fixture by key"""
    loader = FixtureLoader()
    return loader.get(key, default)


def get_config_fixtures() -> Dict[str, Any]:
    """Get configuration fixtures"""
    return get_fixture("config", {})


def get_correlation_fixtures() -> Any:
    """Get correlation matrix fixtures"""
    return get_fixture("correlation_matrix", [])


def get_market_data_fixtures() -> Any:
    """Get market data fixtures"""
    return get_fixture("market_data", [])


def get_portfolio_fixtures() -> Dict[str, Any]:
    """Get portfolio fixtures"""
    return get_fixture("portfolio", {})


def create_test_portfolio(positions: int = 5) -> Dict[str, Any]:
    """Create a test portfolio with random positions"""
    factory = FixtureFactory()
    pos_list = []
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOT/USDT"]
    sides = ["long", "short"]
    statuses = ["open", "closed"]
    
    for i in range(positions):
        symbol = symbols[i % len(symbols)]
        side = random.choice(sides)
        quantity = round(random.uniform(0.1, 2.0), 2)
        entry_price = round(random.uniform(40000, 60000), 2)
        current_price = round(entry_price * (1 + random.uniform(-0.1, 0.1)), 2)
        status = random.choice(statuses)
        
        pos = factory.create_position(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            status=status
        )
        pos_list.append(pos)
    
    return factory.create_portfolio(
        positions=pos_list,
        initial_balance=random.uniform(50000, 200000)
    )


def create_test_market_data(
    symbol: str = "BTC/USDT",
    days: int = 30,
    base_price: float = 50000.0,
    volatility: float = 0.02
) -> List[Dict[str, Any]]:
    """Create test market data"""
    factory = FixtureFactory()
    return factory.create_market_data(
        symbol=symbol,
        num_points=days * 24,
        base_price=base_price,
        volatility=volatility,
        trend=random.uniform(-0.001, 0.001)
    )


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Classes
    "FixtureLoader",
    "FixtureFactory",
    "MockFactory",
    
    # Pytest fixtures
    "fixture_loader",
    "fixture_factory",
    "mock_factory",
    "sample_market_data",
    "sample_position",
    "sample_portfolio",
    "sample_strategy",
    "sample_risk_metrics",
    "mock_exchange",
    "mock_risk_manager",
    "mock_portfolio",
    "mock_strategy",
    "mock_database",
    "mock_redis",
    "mock_notifier",
    
    # Convenience functions
    "get_fixture",
    "get_config_fixtures",
    "get_correlation_fixtures",
    "get_market_data_fixtures",
    "get_portfolio_fixtures",
    "create_test_portfolio",
    "create_test_market_data",
    
    # Constants
    "FIXTURES_DIR",
    "FIXTURE_FILES",
]

# ============================================================
# INITIALIZATION
# ============================================================

# Auto-load fixtures on import
try:
    _loader = FixtureLoader()
    _loader.load_all()
    logger.info("Test fixtures auto-loaded successfully")
except Exception as e:
    logger.error(f"Failed to auto-load test fixtures: {e}")

# ============================================================
# END OF MODULE
# ============================================================

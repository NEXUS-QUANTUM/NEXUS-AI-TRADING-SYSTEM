# trading/bots/hedge_bot/tests/__init__.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Test Suite
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Test Suite - Full Version

This module provides a comprehensive test suite for the NEXUS Hedge Bot
system. It includes unit tests, integration tests, performance tests,
and scenario-based tests for all components.

The test suite covers:
- Core components
- Strategy implementations
- Risk management
- Execution engine
- Portfolio management
- Data providers
- AI/ML components
- API endpoints
- WebSocket communication
- Database operations
- Cache management
- Monitoring and logging
- Configuration management
- Security and compliance
- Market data processing
- Order execution
- Position management
- PnL calculation
- Performance optimization
- Error handling
- Recovery procedures
- Stress testing
- Scenario analysis
- Correlation analysis
- Volatility analysis
- Liquidity analysis
- Margin analysis
"""

import os
import sys
import json
import yaml
import csv
import logging
import random
import time
import asyncio
import threading
import multiprocessing
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union, Callable, Generator
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from functools import wraps
from contextlib import contextmanager
from decimal import Decimal
import hashlib

# ============================================================
# PACKAGE METADATA
# ============================================================

__version__ = "2.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__license__ = "Proprietary"
__status__ = "Production"

# ============================================================
# PROJECT ROOT SETUP
# ============================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================
# TEST CONFIGURATION
# ============================================================

@dataclass
class TestConfig:
    """Test configuration"""
    debug: bool = False
    log_level: str = "INFO"
    timeout: int = 30
    retry_count: int = 3
    parallel: bool = True
    coverage: bool = True
    fixtures_dir: str = str(Path(__file__).parent / "fixtures")
    output_dir: str = "test_output"
    environment: str = "testing"
    run_slow_tests: bool = False
    run_performance_tests: bool = False
    run_integration_tests: bool = True
    run_unit_tests: bool = True
    seed: int = 42
    max_failures: int = 10
    verbosity: int = 1
    capture_logs: bool = True
    save_results: bool = True

    @classmethod
    def from_env(cls) -> "TestConfig":
        """Create config from environment variables"""
        return cls(
            debug=os.environ.get("TEST_DEBUG", "false").lower() == "true",
            log_level=os.environ.get("TEST_LOG_LEVEL", "INFO"),
            timeout=int(os.environ.get("TEST_TIMEOUT", "30")),
            retry_count=int(os.environ.get("TEST_RETRY_COUNT", "3")),
            parallel=os.environ.get("TEST_PARALLEL", "true").lower() == "true",
            coverage=os.environ.get("TEST_COVERAGE", "true").lower() == "true",
            fixtures_dir=os.environ.get("TEST_FIXTURES_DIR", str(Path(__file__).parent / "fixtures")),
            output_dir=os.environ.get("TEST_OUTPUT_DIR", "test_output"),
            environment=os.environ.get("TEST_ENVIRONMENT", "testing"),
            run_slow_tests=os.environ.get("TEST_RUN_SLOW", "false").lower() == "true",
            run_performance_tests=os.environ.get("TEST_RUN_PERFORMANCE", "false").lower() == "true",
            run_integration_tests=os.environ.get("TEST_RUN_INTEGRATION", "true").lower() == "true",
            run_unit_tests=os.environ.get("TEST_RUN_UNIT", "true").lower() == "true",
            seed=int(os.environ.get("TEST_SEED", "42")),
            max_failures=int(os.environ.get("TEST_MAX_FAILURES", "10")),
            verbosity=int(os.environ.get("TEST_VERBOSITY", "1")),
            capture_logs=os.environ.get("TEST_CAPTURE_LOGS", "true").lower() == "true",
            save_results=os.environ.get("TEST_SAVE_RESULTS", "true").lower() == "true",
        )


# Load configuration
TEST_CONFIG = TestConfig.from_env()

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

class TestLogger:
    """Test logger with structured logging"""
    
    def __init__(self, name: str = "test"):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Setup logger"""
        level = getattr(logging, TEST_CONFIG.log_level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        if TEST_CONFIG.capture_logs:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ))
            self.logger.addHandler(handler)
    
    def debug(self, msg: str, **kwargs) -> None:
        """Log debug message"""
        self.logger.debug(self._format(msg, **kwargs))
    
    def info(self, msg: str, **kwargs) -> None:
        """Log info message"""
        self.logger.info(self._format(msg, **kwargs))
    
    def warning(self, msg: str, **kwargs) -> None:
        """Log warning message"""
        self.logger.warning(self._format(msg, **kwargs))
    
    def error(self, msg: str, **kwargs) -> None:
        """Log error message"""
        self.logger.error(self._format(msg, **kwargs))
    
    def critical(self, msg: str, **kwargs) -> None:
        """Log critical message"""
        self.logger.critical(self._format(msg, **kwargs))
    
    def _format(self, msg: str, **kwargs) -> str:
        """Format log message with context"""
        if kwargs:
            context = " ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"{msg} | {context}"
        return msg


# ============================================================
# TEST HELPERS
# ============================================================

class TestHelper:
    """
    Comprehensive test helper utilities
    """
    
    _instance = None
    _cache = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.logger = TestLogger("test_helper")
        self.fixtures_dir = Path(TEST_CONFIG.fixtures_dir)
        self.output_dir = Path(TEST_CONFIG.output_dir)
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure required directories exist"""
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    # ============================================================
    # DATA LOADING
    # ============================================================
    
    def load_test_data(self, filename: str) -> Any:
        """
        Load test data from file
        
        Args:
            filename: Name of the test data file
            
        Returns:
            Loaded test data
        """
        cache_key = f"data_{filename}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        path = self.fixtures_dir / filename
        
        if not path.exists():
            self.logger.warning(f"Test data file not found: {path}")
            return None
        
        try:
            ext = path.suffix.lower()
            
            if ext == ".json":
                with open(path, "r") as f:
                    data = json.load(f)
            elif ext in [".yaml", ".yml"]:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
            elif ext == ".csv":
                with open(path, "r") as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
            elif ext == ".txt":
                with open(path, "r") as f:
                    data = f.read()
            else:
                with open(path, "r") as f:
                    data = f.read()
            
            self._cache[cache_key] = data
            self.logger.debug(f"Loaded test data: {filename}")
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to load test data: {filename}", error=str(e))
            return None
    
    def save_test_data(self, filename: str, data: Any) -> bool:
        """
        Save test data to file
        
        Args:
            filename: Name of the file
            data: Data to save
            
        Returns:
            True if successful
        """
        path = self.output_dir / filename
        
        try:
            ext = path.suffix.lower()
            
            if ext == ".json":
                with open(path, "w") as f:
                    json.dump(data, f, indent=2, default=str)
            elif ext in [".yaml", ".yml"]:
                with open(path, "w") as f:
                    yaml.dump(data, f, default_flow_style=False)
            elif ext == ".csv":
                with open(path, "w") as f:
                    if data and isinstance(data, list):
                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)
            else:
                with open(path, "w") as f:
                    f.write(str(data))
            
            self.logger.debug(f"Saved test data: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save test data: {filename}", error=str(e))
            return False
    
    # ============================================================
    # DATA GENERATION
    # ============================================================
    
    def generate_market_data(
        self,
        symbol: str = "BTC/USDT",
        num_points: int = 100,
        start_price: float = 50000.0,
        volatility: float = 0.02,
        trend: float = 0.0001,
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate synthetic market data
        
        Args:
            symbol: Trading pair symbol
            num_points: Number of data points
            start_price: Starting price
            volatility: Daily volatility
            trend: Daily trend
            seed: Random seed for reproducibility
            
        Returns:
            List of market data points
        """
        if seed is None:
            seed = TEST_CONFIG.seed
        
        random.seed(seed)
        np.random.seed(seed)
        
        data = []
        price = start_price
        
        for i in range(num_points):
            change = np.random.normal(trend, volatility)
            price = price * (1 + change)
            
            data.append({
                "symbol": symbol,
                "timestamp": (datetime.now() - timedelta(minutes=num_points - i)).isoformat(),
                "open": round(price * (1 - random.uniform(0, 0.005)), 2),
                "high": round(price * (1 + random.uniform(0, 0.01)), 2),
                "low": round(price * (1 - random.uniform(0, 0.01)), 2),
                "close": round(price, 2),
                "volume": int(random.uniform(100000, 1000000)),
            })
        
        return data
    
    def generate_positions(self, num_positions: int = 5) -> List[Dict[str, Any]]:
        """
        Generate synthetic positions
        
        Args:
            num_positions: Number of positions to generate
            
        Returns:
            List of positions
        """
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOT/USDT"]
        sides = ["long", "short"]
        statuses = ["open", "closed"]
        
        positions = []
        for i in range(num_positions):
            symbol = symbols[i % len(symbols)]
            side = random.choice(sides)
            quantity = round(random.uniform(0.1, 2.0), 2)
            entry_price = round(random.uniform(40000, 60000), 2)
            current_price = round(entry_price * (1 + random.uniform(-0.1, 0.1)), 2)
            
            pnl = (current_price - entry_price) * quantity
            if side == "short":
                pnl = (entry_price - current_price) * quantity
            
            positions.append({
                "id": f"pos_{i+1:03d}",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "current_price": current_price,
                "unrealized_pnl": round(pnl, 2),
                "unrealized_pnl_percent": round(pnl / (entry_price * quantity) * 100, 2),
                "value": round(quantity * current_price, 2),
                "status": random.choice(statuses),
                "created_at": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
            })
        
        return positions
    
    def generate_orders(self, num_orders: int = 5) -> List[Dict[str, Any]]:
        """
        Generate synthetic orders
        
        Args:
            num_orders: Number of orders to generate
            
        Returns:
            List of orders
        """
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOT/USDT"]
        sides = ["buy", "sell"]
        types = ["limit", "market", "stop_limit"]
        statuses = ["pending", "filled", "partially_filled", "cancelled", "rejected"]
        
        orders = []
        for i in range(num_orders):
            symbol = symbols[i % len(symbols)]
            side = random.choice(sides)
            order_type = random.choice(types)
            quantity = round(random.uniform(0.1, 2.0), 2)
            price = round(random.uniform(40000, 60000), 2)
            
            orders.append({
                "id": f"ord_{i+1:03d}",
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "quantity": quantity,
                "price": price,
                "filled_quantity": round(quantity * random.uniform(0, 1), 2) if random.random() > 0.5 else 0,
                "status": random.choice(statuses),
                "time_in_force": random.choice(["GTC", "IOC", "FOK"]),
                "created_at": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat(),
            })
        
        return orders
    
    def generate_portfolio(self, initial_balance: float = 100000.0) -> Dict[str, Any]:
        """
        Generate synthetic portfolio
        
        Args:
            initial_balance: Initial portfolio balance
            
        Returns:
            Portfolio data
        """
        positions = self.generate_positions(random.randint(3, 8))
        total_value = initial_balance
        
        for pos in positions:
            total_value += pos.get("unrealized_pnl", 0)
        
        return {
            "id": f"portfolio_{int(time.time())}",
            "name": "Test Portfolio",
            "currency": "USD",
            "initial_balance": initial_balance,
            "current_balance": round(total_value, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_value - initial_balance, 2),
            "total_pnl_percent": round((total_value - initial_balance) / initial_balance * 100, 2),
            "positions": positions,
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 90))).isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    
    # ============================================================
    # MOCK CREATION
    # ============================================================
    
    def create_mock_exchange(self) -> Mock:
        """Create a mock exchange"""
        mock = Mock()
        
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
        
        mock.get_balance.return_value = {"USDT": 100000.0, "BTC": 1.0}
        
        mock.place_order.return_value = {
            "order_id": "ord_123456",
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 1.0,
            "price": 50000.0,
            "status": "filled",
        }
        
        mock.cancel_order.return_value = {
            "order_id": "ord_123456",
            "status": "cancelled",
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
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    def create_mock_risk_manager(self) -> Mock:
        """Create a mock risk manager"""
        mock = Mock()
        
        mock.calculate_var.return_value = 25000.0
        mock.calculate_cvar.return_value = 35000.0
        mock.calculate_drawdown.return_value = 0.08
        mock.calculate_risk_score.return_value = 0.35
        mock.check_limits.return_value = {"status": "healthy", "breaches": []}
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    def create_mock_portfolio_manager(self) -> Mock:
        """Create a mock portfolio manager"""
        mock = Mock()
        
        mock.get_total_value.return_value = 125000.0
        mock.get_positions.return_value = []
        mock.get_allocation.return_value = {"crypto": 0.5, "equity": 0.3}
        mock.get_performance.return_value = {"sharpe": 1.85, "returns": []}
        mock.rebalance.return_value = {"trades": []}
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    def create_mock_strategy(self) -> Mock:
        """Create a mock strategy"""
        mock = Mock()
        
        mock.generate_signal.return_value = {"type": "buy", "confidence": 0.8}
        mock.execute.return_value = {"order_id": "ord_123456", "status": "filled"}
        mock.get_status.return_value = {"status": "running", "positions": 5}
        mock.get_performance.return_value = {"pnl": 10000.0, "win_rate": 0.65}
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    def create_mock_database(self) -> Mock:
        """Create a mock database"""
        mock = Mock()
        
        mock.execute_query.return_value = []
        mock.get_connection.return_value = None
        mock.get_health_status.return_value = {"status": "healthy"}
        mock.insert_trade.return_value = True
        mock.insert_position.return_value = True
        
        return mock
    
    def create_mock_cache(self) -> Mock:
        """Create a mock cache"""
        mock = Mock()
        
        mock.get.return_value = None
        mock.set.return_value = True
        mock.delete.return_value = 1
        mock.clear.return_value = True
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    def create_mock_predictor(self) -> Mock:
        """Create a mock predictor"""
        mock = Mock()
        
        mock.predict.return_value = {"direction": "up", "confidence": 0.8}
        mock.predict_price.return_value = 51000.0
        mock.predict_volatility.return_value = 0.20
        mock.predict_correlation.return_value = 0.65
        mock.train.return_value = True
        mock.get_health_status.return_value = {"status": "healthy"}
        
        return mock
    
    # ============================================================
    # CONTEXT MANAGERS
    # ============================================================
    
    @contextmanager
    def temp_environment(self, env_vars: Dict[str, str]) -> Generator[Dict[str, str], None, None]:
        """
        Temporarily set environment variables
        
        Args:
            env_vars: Dictionary of environment variables to set
            
        Yields:
            Original environment variables
        """
        original = {}
        try:
            for key, value in env_vars.items():
                original[key] = os.environ.get(key)
                os.environ[key] = value
            yield original
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    
    @contextmanager
    def temp_config(self, config_updates: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """
        Temporarily update test configuration
        
        Args:
            config_updates: Configuration updates
            
        Yields:
            Original configuration
        """
        original = {}
        try:
            for key, value in config_updates.items():
                if hasattr(TEST_CONFIG, key):
                    original[key] = getattr(TEST_CONFIG, key)
                    setattr(TEST_CONFIG, key, value)
            yield original
        finally:
            for key, value in original.items():
                setattr(TEST_CONFIG, key, value)
    
    @contextmanager
    def temp_override(self, obj: Any, attr: str, value: Any) -> Generator[Any, None, None]:
        """
        Temporarily override an attribute
        
        Args:
            obj: Object to override
            attr: Attribute name
            value: New value
            
        Yields:
            Original value
        """
        original = getattr(obj, attr)
        try:
            setattr(obj, attr, value)
            yield original
        finally:
            setattr(obj, attr, original)
    
    # ============================================================
    # DECORATORS
    # ============================================================
    
    @staticmethod
    def retry_on_failure(max_retries: int = 3, delay: float = 0.5) -> Callable:
        """
        Decorator to retry a test on failure
        
        Args:
            max_retries: Maximum number of retries
            delay: Delay between retries in seconds
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries:
                            time.sleep(delay * (attempt + 1))
                raise last_exception
            return wrapper
        return decorator
    
    @staticmethod
    def timeout(seconds: int) -> Callable:
        """
        Decorator to timeout a test
        
        Args:
            seconds: Timeout in seconds
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                import signal
                
                def handler(signum, frame):
                    raise TimeoutError(f"Test timed out after {seconds} seconds")
                
                signal.signal(signal.SIGALRM, handler)
                signal.alarm(seconds)
                try:
                    return func(*args, **kwargs)
                finally:
                    signal.alarm(0)
            return wrapper
        return decorator
    
    @staticmethod
    def skip_if(condition: bool, reason: str = "") -> Callable:
        """
        Decorator to skip a test if condition is true
        
        Args:
            condition: Condition to skip
            reason: Skip reason
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if condition:
                    pytest.skip(reason or f"Test skipped: {func.__name__}")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def benchmark(iterations: int = 100) -> Callable:
        """
        Decorator to benchmark a test function
        
        Args:
            iterations: Number of iterations
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                import time
                times = []
                for _ in range(iterations):
                    start = time.time()
                    result = func(*args, **kwargs)
                    times.append(time.time() - start)
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                print(f"\nBenchmark: {func.__name__}")
                print(f"  Iterations: {iterations}")
                print(f"  Average: {avg_time:.4f}s")
                print(f"  Min: {min_time:.4f}s")
                print(f"  Max: {max_time:.4f}s")
                return result
            return wrapper
        return decorator


# ============================================================
# TEST CASE BASE CLASS
# ============================================================

class TestCase:
    """
    Base test case class with common functionality
    """
    
    def __init__(self):
        self.logger = TestLogger(self.__class__.__name__)
        self.helper = TestHelper()
        self.test_data = {}
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def setup(self) -> None:
        """Setup method - called before each test"""
        self.start_time = time.time()
        self.logger.info(f"Starting test: {self.__class__.__name__}")
    
    def teardown(self) -> None:
        """Teardown method - called after each test"""
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        self.logger.info(f"Completed test: {self.__class__.__name__} ({duration:.2f}s)")
    
    def assert_true(self, condition: bool, message: str = "") -> None:
        """Assert condition is true"""
        assert condition, message or "Expected True but got False"
    
    def assert_false(self, condition: bool, message: str = "") -> None:
        """Assert condition is false"""
        assert not condition, message or "Expected False but got True"
    
    def assert_equal(self, actual: Any, expected: Any, message: str = "") -> None:
        """Assert actual equals expected"""
        assert actual == expected, message or f"Expected {expected} but got {actual}"
    
    def assert_not_equal(self, actual: Any, expected: Any, message: str = "") -> None:
        """Assert actual does not equal expected"""
        assert actual != expected, message or f"Expected {actual} != {expected}"
    
    def assert_raises(self, exception: Exception, func: Callable, *args, **kwargs) -> None:
        """Assert that a function raises an exception"""
        try:
            func(*args, **kwargs)
            raise AssertionError(f"Expected {exception.__name__} but no exception was raised")
        except exception:
            pass
    
    def assert_between(self, value: float, min_val: float, max_val: float, message: str = "") -> None:
        """Assert value is between min and max"""
        assert min_val <= value <= max_val, message or f"Value {value} is not between {min_val} and {max_val}"
    
    def assert_approx(self, actual: float, expected: float, tolerance: float = 0.001, message: str = "") -> None:
        """Assert actual is approximately equal to expected"""
        assert abs(actual - expected) <= tolerance, message or f"Expected {expected} ± {tolerance} but got {actual}"
    
    def assert_not_none(self, value: Any, message: str = "") -> None:
        """Assert value is not None"""
        assert value is not None, message or "Expected value not to be None"
    
    def assert_is_instance(self, obj: Any, cls: type, message: str = "") -> None:
        """Assert object is instance of class"""
        assert isinstance(obj, cls), message or f"Expected {obj} to be instance of {cls}"


# ============================================================
# ASYNC TEST UTILITIES
# ============================================================

class AsyncTestHelper:
    """
    Async test utilities
    """
    
    @staticmethod
    async def wait_for_condition(
        condition: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.1
    ) -> bool:
        """
        Wait for a condition to become true
        
        Args:
            condition: Function to check
            timeout: Timeout in seconds
            interval: Check interval in seconds
            
        Returns:
            True if condition became true, False if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if condition():
                return True
            await asyncio.sleep(interval)
        return False
    
    @staticmethod
    async def wait_for_event(
        event: asyncio.Event,
        timeout: float = 5.0
    ) -> bool:
        """
        Wait for an event
        
        Args:
            event: Event to wait for
            timeout: Timeout in seconds
            
        Returns:
            True if event was set, False if timeout
        """
        try:
            await asyncio.wait_for(event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
    
    @staticmethod
    def run_async_test(coro) -> Any:
        """Run an async test"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    @staticmethod
    def async_test(func: Callable) -> Callable:
        """Decorator for async test functions"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return AsyncTestHelper.run_async_test(func(*args, **kwargs))
        return wrapper


# ============================================================
# PERFORMANCE METRICS
# ============================================================

@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    name: str
    iterations: int
    total_time: float
    average_time: float
    min_time: float
    max_time: float
    operations_per_second: float
    memory_used: float
    cpu_used: float
    
    @classmethod
    def from_times(cls, name: str, times: List[float], memory: float = 0, cpu: float = 0) -> "PerformanceMetrics":
        """Create metrics from timing data"""
        total = sum(times)
        avg = total / len(times)
        return cls(
            name=name,
            iterations=len(times),
            total_time=total,
            average_time=avg,
            min_time=min(times),
            max_time=max(times),
            operations_per_second=1.0 / avg if avg > 0 else 0,
            memory_used=memory,
            cpu_used=cpu,
        )


class PerformanceProfiler:
    """
    Performance profiler
    """
    
    def __init__(self):
        self.metrics = []
        self.current_measurements = []
    
    @contextmanager
    def measure(self, name: str):
        """
        Measure performance of a code block
        
        Args:
            name: Name of the measurement
            
        Yields:
            None
        """
        start = time.time()
        yield
        duration = time.time() - start
        self.current_measurements.append((name, duration))
    
    def profile(self, func: Callable, iterations: int = 100) -> PerformanceMetrics:
        """
        Profile a function
        
        Args:
            func: Function to profile
            iterations: Number of iterations
            
        Returns:
            Performance metrics
        """
        times = []
        for _ in range(iterations):
            start = time.time()
            func()
            times.append(time.time() - start)
        
        return PerformanceMetrics.from_times(func.__name__, times)
    
    def get_report(self) -> Dict[str, Any]:
        """Get performance report"""
        return {
            "metrics": self.metrics,
            "total_tests": len(self.metrics),
            "generated_at": datetime.now().isoformat(),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Configuration
    "TEST_CONFIG",
    "TestConfig",
    
    # Logging
    "TestLogger",
    "setup_test_logging",
    
    # Helpers
    "TestHelper",
    "AsyncTestHelper",
    
    # Base class
    "TestCase",
    
    # Performance
    "PerformanceMetrics",
    "PerformanceProfiler",
    
    # Metadata
    "__version__",
    "__author__",
    "__copyright__",
    "__license__",
    "__status__",
    "PROJECT_ROOT",
]

# ============================================================
# INITIALIZATION
# ============================================================

# Setup logging
def setup_test_logging(level: str = "INFO") -> None:
    """Setup test logging"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Remove existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Reduce noise from third-party libraries
    for lib in ["urllib3", "requests", "asyncio", "websockets"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


# Initialize logging
setup_test_logging(TEST_CONFIG.log_level)

# Create required directories
output_dir = Path(TEST_CONFIG.output_dir)
output_dir.mkdir(parents=True, exist_ok=True)

fixtures_dir = Path(TEST_CONFIG.fixtures_dir)
fixtures_dir.mkdir(parents=True, exist_ok=True)

# Initialize random seed
random.seed(TEST_CONFIG.seed)
try:
    import numpy as np
    np.random.seed(TEST_CONFIG.seed)
except ImportError:
    pass

# ============================================================
# PYTEST CONFIGURATION
# ============================================================

# Register custom markers
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line("markers", "benchmark: mark test as benchmark")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "slow: mark test as slow test")
    config.addinivalue_line("markers", "asyncio: mark test as async test")
    config.addinivalue_line("markers", "stress: mark test as stress test")
    config.addinivalue_line("markers", "scenario: mark test as scenario test")


# ============================================================
# END OF MODULE
# ============================================================

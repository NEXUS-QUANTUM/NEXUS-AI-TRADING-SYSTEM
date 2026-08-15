"""
Swing Bot Tests Package
========================

This package contains all unit and integration tests for the Swing Bot trading system.
Test modules are organized by component and include fixtures for testing.

Test Structure:
- fixtures/: Test data and configuration fixtures
- test_core.py: Core engine and component tests
- test_strategies.py: Trading strategy tests
- test_risk.py: Risk management tests
- test_sniper_bot.py: Sniper bot tests
- test_models.py: Data model tests
- test_monitoring.py: Monitoring and alerting tests
- test_performance.py: Performance tests
- test_benchmark.py: Benchmark tests
- test_integration.py: Integration tests
"""

import os
import sys
import pytest
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Test configuration
TEST_CONFIG = {
    'test_environment': 'test',
    'debug': True,
    'log_level': 'DEBUG',
    'data_dir': Path(__file__).parent / 'fixtures',
    'temp_dir': Path('/tmp/swing_bot_tests'),
    'timeout': 30,
    'retry_count': 3,
}

# Version information
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"


def setup_test_environment():
    """Setup test environment."""
    # Create temporary directories
    temp_dir = TEST_CONFIG['temp_dir']
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Set environment variables for testing
    os.environ['TEST_ENV'] = 'true'
    os.environ['DEBUG'] = 'true'
    os.environ['LOG_LEVEL'] = 'DEBUG'


def cleanup_test_environment():
    """Cleanup test environment."""
    import shutil
    
    temp_dir = TEST_CONFIG['temp_dir']
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)


# Setup and teardown hooks for pytest
def pytest_configure(config):
    """Configure pytest."""
    setup_test_environment()
    
    # Register custom markers
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "benchmark: mark test as benchmark"
    )
    config.addinivalue_line(
        "markers",
        "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers",
        "stress: mark test as stress test"
    )
    config.addinivalue_line(
        "markers",
        "unit: mark test as unit test"
    )


def pytest_unconfigure(config):
    """Cleanup after pytest."""
    cleanup_test_environment()


# Import test modules for easy access
from .fixtures import (
    FixtureLoader,
    fixture_loader,
    get_config_fixture,
    get_market_data_fixture,
    get_market_data_df_fixture,
    get_level_test_fixture,
    get_target_test_fixture,
)

from . import test_core
from . import test_strategies
from . import test_risk
from . import test_sniper_bot
from . import test_models
from . import test_monitoring
from . import test_performance
from . import test_benchmark
from . import test_integration


# Test suite configuration
TEST_SUITES = {
    'unit': [
        test_core,
        test_models,
        test_strategies,
    ],
    'integration': [
        test_integration,
        test_risk,
        test_sniper_bot,
        test_monitoring,
    ],
    'performance': [
        test_performance,
        test_benchmark,
    ],
    'all': None,  # All tests
}


def run_tests(suite: str = 'unit', verbose: bool = True):
    """
    Run a specific test suite.
    
    Args:
        suite: Test suite to run ('unit', 'integration', 'performance', 'all')
        verbose: Enable verbose output
    
    Returns:
        Test result
    """
    import pytest
    
    if suite not in TEST_SUITES:
        raise ValueError(f"Unknown test suite: {suite}. Choose from {list(TEST_SUITES.keys())}")
    
    test_paths = []
    
    if suite == 'all':
        test_paths = [str(Path(__file__).parent)]
    elif TEST_SUITES[suite]:
        for module in TEST_SUITES[suite]:
            test_paths.append(str(Path(module.__file__).parent / module.__name__.split('.')[-1]))
    else:
        test_paths = [str(Path(__file__).parent)]
    
    args = []
    if verbose:
        args.append('-v')
    
    if suite == 'unit':
        args.append('-m unit')
    elif suite == 'integration':
        args.append('-m integration')
    elif suite == 'performance':
        args.append('-m performance')
    
    args.extend(test_paths)
    
    return pytest.main(args)


# Export all test modules and utilities
__all__ = [
    # Configuration
    'TEST_CONFIG',
    'setup_test_environment',
    'cleanup_test_environment',
    
    # Fixtures
    'FixtureLoader',
    'fixture_loader',
    'get_config_fixture',
    'get_market_data_fixture',
    'get_market_data_df_fixture',
    'get_level_test_fixture',
    'get_target_test_fixture',
    
    # Test modules
    'test_core',
    'test_strategies',
    'test_risk',
    'test_sniper_bot',
    'test_models',
    'test_monitoring',
    'test_performance',
    'test_benchmark',
    'test_integration',
    
    # Test suite utilities
    'TEST_SUITES',
    'run_tests',
    
    # Version info
    '__version__',
    '__author__',
    '__copyright__',
]


# Run setup automatically when module is imported
setup_test_environment()


if __name__ == "__main__":
    # Run all tests when module is executed directly
    sys.exit(run_tests('all', verbose=True))

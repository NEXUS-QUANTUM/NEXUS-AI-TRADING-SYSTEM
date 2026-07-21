"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Test Suite
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Suite de tests complète pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import os
import sys
import pytest
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

# ============================================================
# PACKAGE METADATA
# ============================================================
__version__ = "2.0.0"
__author__ = "NEXUS QUANTUM TEAM"
__description__ = "Suite de tests pour le bot d'arbitrage NEXUS"

# ============================================================
# LOGGING CONFIGURATION
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# TEST CONFIGURATION
# ============================================================

class TestConfig:
    """Configuration des tests"""
    
    # Chemins
    TESTS_DIR = Path(__file__).parent
    FIXTURES_DIR = TESTS_DIR / "fixtures"
    ROOT_DIR = TESTS_DIR.parent.parent.parent.parent
    
    # Fichiers de fixtures
    CONFIG_FILE = FIXTURES_DIR / "config_test.yaml"
    MARKET_DATA_FILE = FIXTURES_DIR / "market_data.csv"
    TEST_DATA_FILE = FIXTURES_DIR / "test_data.json"
    
    # Paramètres de test
    TIMEOUT = 60  # seconds
    RETRY_COUNT = 3
    PARALLEL_WORKERS = 4
    
    # Environnement
    ENV = os.environ.get("TEST_ENV", "testing")
    DEBUG = os.environ.get("TEST_DEBUG", "false").lower() == "true"
    
    # Exclusions
    EXCLUDED_TESTS = [
        # "test_slow_performance",  # Exemple
    ]
    
    # Marquage
    MARKERS = {
        "unit": "Tests unitaires",
        "integration": "Tests d'intégration",
        "performance": "Tests de performance",
        "benchmark": "Tests de benchmark",
        "slow": "Tests lents",
        "fast": "Tests rapides",
        "smoke": "Tests de fumée",
        "regression": "Tests de régression",
        "security": "Tests de sécurité",
        "stress": "Tests de stress",
    }

# ============================================================
# TEST UTILITIES
# ============================================================

class TestUtils:
    """Utilitaires pour les tests"""
    
    @staticmethod
    def get_test_data_path(filename: str) -> Path:
        """Récupère le chemin d'un fichier de test"""
        return TestConfig.FIXTURES_DIR / filename
    
    @staticmethod
    def load_test_file(filename: str, mode: str = 'r') -> Any:
        """Charge un fichier de test"""
        path = TestUtils.get_test_data_path(filename)
        with open(path, mode, encoding='utf-8') as f:
            if filename.endswith('.json'):
                import json
                return json.load(f)
            elif filename.endswith('.yaml') or filename.endswith('.yml'):
                import yaml
                return yaml.safe_load(f)
            elif filename.endswith('.csv'):
                import csv
                return list(csv.DictReader(f))
            else:
                return f.read()
    
    @staticmethod
    def save_test_file(filename: str, data: Any, mode: str = 'w'):
        """Sauvegarde un fichier de test"""
        path = TestUtils.get_test_data_path(filename)
        with open(path, mode, encoding='utf-8') as f:
            if filename.endswith('.json'):
                import json
                json.dump(data, f, indent=2, default=str)
            elif filename.endswith('.yaml') or filename.endswith('.yml'):
                import yaml
                yaml.dump(data, f, default_flow_style=False)
            elif filename.endswith('.csv'):
                import csv
                if data and isinstance(data, list):
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
            else:
                f.write(str(data))
    
    @staticmethod
    def generate_test_data(size: int = 100) -> List[Dict[str, Any]]:
        """Génère des données de test"""
        import random
        data = []
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT']
        
        for i in range(size):
            symbol = random.choice(symbols)
            price = random.uniform(1000, 50000)
            volume = random.uniform(0.1, 100)
            timestamp = datetime.now() - timedelta(minutes=random.randint(0, 1000))
            
            data.append({
                'id': f'test_{i:06d}',
                'symbol': symbol,
                'price': round(price, 2),
                'volume': round(volume, 2),
                'timestamp': timestamp.isoformat(),
                'bid': round(price * 0.999, 2),
                'ask': round(price * 1.001, 2),
                'spread': round(price * 0.002, 2),
            })
        
        return data
    
    @staticmethod
    def assert_dict_contains(container: Dict, expected: Dict):
        """Vérifie que le dictionnaire contient les clés/valeurs attendues"""
        for key, value in expected.items():
            assert key in container, f"Clé '{key}' manquante"
            if isinstance(value, dict) and isinstance(container[key], dict):
                TestUtils.assert_dict_contains(container[key], value)
            else:
                assert container[key] == value, f"Valeur incorrecte pour '{key}': attendu {value}, obtenu {container[key]}"
    
    @staticmethod
    def assert_list_contains(container: List, expected: Any):
        """Vérifie que la liste contient l'élément attendu"""
        assert expected in container, f"Élément '{expected}' non trouvé dans la liste"
    
    @staticmethod
    def measure_time(func, *args, **kwargs) -> tuple:
        """Mesure le temps d'exécution d'une fonction"""
        import time
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        return result, (end - start) * 1000  # ms
    
    @staticmethod
    def retry_on_failure(func, retries: int = 3, delay: int = 1):
        """Réessaye une fonction en cas d'échec"""
        import time
        for attempt in range(retries):
            try:
                return func()
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(delay * (attempt + 1))

# ============================================================
# PYTEST CONFIGURATION
# ============================================================

def pytest_configure(config):
    """Configure pytest"""
    # Enregistrer les marqueurs
    for marker, description in TestConfig.MARKERS.items():
        config.addinivalue_line("markers", f"{marker}: {description}")
    
    # Configurer le logging
    if TestConfig.DEBUG:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    logger.info(f"Test suite configured - Environment: {TestConfig.ENV}, Debug: {TestConfig.DEBUG}")

def pytest_collection_modifyitems(config, items):
    """Modifie la collection des tests"""
    # Appliquer les exclusions
    for item in items[:]:
        if any(excluded in item.nodeid for excluded in TestConfig.EXCLUDED_TESTS):
            items.remove(item)
            logger.info(f"Excluded test: {item.nodeid}")
    
    # Ajouter des marqueurs automatiques
    for item in items:
        if "test_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "test_performance" in item.nodeid or "test_benchmark" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        if "test_arbitrage_bot" in item.nodeid:
            item.add_marker(pytest.mark.smoke)
        if "test_security" in item.nodeid:
            item.add_marker(pytest.mark.security)

# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Configuration de test"""
    return TestConfig.__dict__

@pytest.fixture(scope="session")
def test_utils() -> TestUtils:
    """Utilitaires de test"""
    return TestUtils()

@pytest.fixture(scope="function")
def temp_dir() -> Path:
    """Répertoire temporaire pour les tests"""
    import tempfile
    import shutil
    temp_dir = Path(tempfile.mkdtemp(prefix="nexus_test_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture(scope="function")
def mock_environment():
    """Mock de l'environnement"""
    import os
    original_env = os.environ.copy()
    os.environ["TEST_MODE"] = "true"
    os.environ["NEXUS_ENV"] = "testing"
    yield
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture(scope="function")
def capture_logs(caplog):
    """Capture les logs"""
    caplog.set_level(logging.DEBUG)
    return caplog

# ============================================================
# TEST HELPERS
# ============================================================

class TestHelpers:
    """Helpers pour les tests"""
    
    @staticmethod
    def create_test_exchange(name: str = "Test Exchange") -> Any:
        """Crée un exchange de test"""
        from trading.bots.arbitrage_bot.tests.fixtures.exchange_mock import MockExchange
        exchange = MockExchange(name)
        exchange.start_market()
        return exchange
    
    @staticmethod
    def create_test_bot(config: Optional[Dict] = None) -> Any:
        """Crée un bot de test"""
        from trading.bots.arbitrage_bot import ArbitrageBot
        if config is None:
            config = TestUtils.load_test_file("config_test.yaml")
        return ArbitrageBot(config)
    
    @staticmethod
    def wait_for_condition(condition_func, timeout: int = 10, interval: float = 0.1):
        """Attend qu'une condition soit vraie"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            if condition_func():
                return True
            time.sleep(interval)
        return False

# ============================================================
# TEST SUITE DEFINITION
# ============================================================

class TestSuite:
    """Définition de la suite de tests"""
    
    # Liste des modules de test
    TEST_MODULES = [
        "test_arbitrage_bot",
        "test_benchmark",
        "test_data",
        "test_detectors",
        "test_exchanges",
        "test_executors",
        "test_integration",
        "test_models",
        "test_monitoring",
        "test_performance",
        "test_risk",
        "test_strategies",
    ]
    
    @classmethod
    def get_test_modules(cls) -> List[str]:
        """Récupère la liste des modules de test"""
        return cls.TEST_MODULES
    
    @classmethod
    def get_test_count(cls) -> int:
        """Récupère le nombre total de tests"""
        import pytest
        import subprocess
        result = subprocess.run(
            ["pytest", "--collect-only", "-q", str(TestConfig.TESTS_DIR)],
            capture_output=True,
            text=True
        )
        lines = result.stdout.strip().split('\n')
        # La dernière ligne contient le nombre total
        if lines:
            last_line = lines[-1]
            if 'collected' in last_line:
                return int(last_line.split()[0])
        return 0
    
    @classmethod
    def run_tests(cls, markers: Optional[List[str]] = None, 
                  exclude_markers: Optional[List[str]] = None,
                  verbose: bool = False,
                  parallel: bool = False) -> int:
        """Exécute les tests"""
        import pytest
        
        args = [str(TestConfig.TESTS_DIR)]
        
        if markers:
            args.extend(["-m", " and ".join(markers)])
        
        if exclude_markers:
            args.extend(["-m", f"not {' and not '.join(exclude_markers)}"])
        
        if verbose:
            args.append("-v")
        
        if parallel:
            args.extend(["-n", str(TestConfig.PARALLEL_WORKERS)])
        
        args.append("--tb=short")
        
        return pytest.main(args)

# ============================================================
# MODULE IMPORTS
# ============================================================

# Importer les fixtures pour les rendre disponibles
from .fixtures import *

# Importer les tests pour les rendre disponibles
from .test_arbitrage_bot import *
from .test_benchmark import *
from .test_data import *
from .test_detectors import *
from .test_exchanges import *
from .test_executors import *
from .test_integration import *
from .test_models import *
from .test_monitoring import *
from .test_performance import *
from .test_risk import *
from .test_strategies import *

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Version
    '__version__',
    '__author__',
    '__description__',
    
    # Classes
    'TestConfig',
    'TestUtils',
    'TestHelpers',
    'TestSuite',
    
    # Fixtures
    'test_config',
    'test_utils',
    'temp_dir',
    'mock_environment',
    'capture_logs',
    
    # Helpers
    'TestHelpers',
    
    # Fonctions
    'pytest_configure',
    'pytest_collection_modifyitems',
]

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Exécuter les tests
    import sys
    sys.exit(TestSuite.run_tests(verbose=True))

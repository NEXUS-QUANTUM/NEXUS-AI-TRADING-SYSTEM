"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Test Fixtures
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Fixtures de test pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
import pytest

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# FIXTURE PATHS
# ============================================================

FIXTURES_DIR = Path(__file__).parent
CONFIG_FILE = FIXTURES_DIR / "config_test.yaml"
MARKET_DATA_FILE = FIXTURES_DIR / "market_data.csv"
TEST_DATA_FILE = FIXTURES_DIR / "test_data.json"

# ============================================================
# FIXTURE LOADERS
# ============================================================

class FixtureLoader:
    """Chargeur de fixtures pour les tests"""
    
    def __init__(self):
        self.fixtures_dir = FIXTURES_DIR
        self._cache: Dict[str, Any] = {}
    
    def load_config(self) -> Dict[str, Any]:
        """Charge la configuration de test"""
        cache_key = "config"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        self._cache[cache_key] = config
        return config
    
    def load_test_data(self) -> Dict[str, Any]:
        """Charge les données de test"""
        cache_key = "test_data"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with open(TEST_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self._cache[cache_key] = data
        return data
    
    def load_market_data(self) -> List[Dict[str, Any]]:
        """Charge les données de marché"""
        cache_key = "market_data"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        data = []
        with open(MARKET_DATA_FILE, 'r', encoding='utf-8') as f:
            # Skip header
            lines = f.readlines()[1:]
            for line in lines:
                if line.strip():
                    parts = line.strip().split(',')
                    if len(parts) >= 10:
                        data.append({
                            'timestamp': parts[0],
                            'symbol': parts[1],
                            'open': float(parts[2]),
                            'high': float(parts[3]),
                            'low': float(parts[4]),
                            'close': float(parts[5]),
                            'volume': float(parts[6]),
                            'quote_volume': float(parts[7]),
                            'trades': int(parts[8]) if len(parts) > 8 else 0
                        })
        
        self._cache[cache_key] = data
        return data
    
    def get_orders(self) -> Dict[str, List[Dict[str, Any]]]:
        """Récupère les ordres de test"""
        data = self.load_test_data()
        return data.get('orders', {})
    
    def get_balances(self) -> Dict[str, Dict[str, float]]:
        """Récupère les soldes de test"""
        data = self.load_test_data()
        return data.get('balances', {})
    
    def get_tickers(self) -> Dict[str, Dict[str, Any]]:
        """Récupère les tickers de test"""
        data = self.load_test_data()
        return data.get('tickers', {})
    
    def get_order_books(self) -> Dict[str, Dict[str, List[List[float]]]]:
        """Récupère les carnets d'ordres de test"""
        data = self.load_test_data()
        return data.get('order_books', {})
    
    def get_trades(self) -> List[Dict[str, Any]]:
        """Récupère les trades de test"""
        data = self.load_test_data()
        return data.get('trades', [])
    
    def get_arbitrage_opportunities(self) -> List[Dict[str, Any]]:
        """Récupère les opportunités d'arbitrage de test"""
        data = self.load_test_data()
        return data.get('arbitrage_opportunities', [])
    
    def get_triangular_opportunities(self) -> List[Dict[str, Any]]:
        """Récupère les opportunités triangulaires de test"""
        data = self.load_test_data()
        return data.get('triangular_opportunities', [])
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """Récupère les alertes de test"""
        data = self.load_test_data()
        return data.get('alerts', [])
    
    def get_system_status(self) -> Dict[str, Any]:
        """Récupère le statut système de test"""
        data = self.load_test_data()
        return data.get('system_status', {})
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Récupère les métriques de performance de test"""
        data = self.load_test_data()
        return data.get('performance_metrics', {})
    
    def clear_cache(self):
        """Vide le cache"""
        self._cache.clear()
    
    def get_all_fixtures(self) -> Dict[str, Any]:
        """Récupère toutes les fixtures"""
        return {
            'config': self.load_config(),
            'test_data': self.load_test_data(),
            'market_data': self.load_market_data(),
            'orders': self.get_orders(),
            'balances': self.get_balances(),
            'tickers': self.get_tickers(),
            'order_books': self.get_order_books(),
            'trades': self.get_trades(),
            'arbitrage_opportunities': self.get_arbitrage_opportunities(),
            'triangular_opportunities': self.get_triangular_opportunities(),
            'alerts': self.get_alerts(),
            'system_status': self.get_system_status(),
            'performance_metrics': self.get_performance_metrics()
        }

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_fixture_loader: Optional[FixtureLoader] = None

def get_fixture_loader() -> FixtureLoader:
    """Récupère le chargeur de fixtures (singleton)"""
    global _fixture_loader
    if _fixture_loader is None:
        _fixture_loader = FixtureLoader()
    return _fixture_loader

# ============================================================
# PYTEST FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def fixture_loader() -> FixtureLoader:
    """Fixture pour le chargeur de fixtures"""
    return get_fixture_loader()

@pytest.fixture(scope="session")
def test_config(fixture_loader: FixtureLoader) -> Dict[str, Any]:
    """Fixture pour la configuration de test"""
    return fixture_loader.load_config()

@pytest.fixture(scope="session")
def test_data(fixture_loader: FixtureLoader) -> Dict[str, Any]:
    """Fixture pour les données de test"""
    return fixture_loader.load_test_data()

@pytest.fixture(scope="session")
def market_data(fixture_loader: FixtureLoader) -> List[Dict[str, Any]]:
    """Fixture pour les données de marché"""
    return fixture_loader.load_market_data()

@pytest.fixture(scope="session")
def test_orders(fixture_loader: FixtureLoader) -> Dict[str, List[Dict[str, Any]]]:
    """Fixture pour les ordres de test"""
    return fixture_loader.get_orders()

@pytest.fixture(scope="session")
def test_balances(fixture_loader: FixtureLoader) -> Dict[str, Dict[str, float]]:
    """Fixture pour les soldes de test"""
    return fixture_loader.get_balances()

@pytest.fixture(scope="session")
def test_tickers(fixture_loader: FixtureLoader) -> Dict[str, Dict[str, Any]]:
    """Fixture pour les tickers de test"""
    return fixture_loader.get_tickers()

@pytest.fixture(scope="session")
def test_order_books(fixture_loader: FixtureLoader) -> Dict[str, Dict[str, List[List[float]]]]:
    """Fixture pour les carnets d'ordres de test"""
    return fixture_loader.get_order_books()

@pytest.fixture(scope="session")
def test_trades(fixture_loader: FixtureLoader) -> List[Dict[str, Any]]:
    """Fixture pour les trades de test"""
    return fixture_loader.get_trades()

@pytest.fixture(scope="session")
def test_arbitrage_opportunities(fixture_loader: FixtureLoader) -> List[Dict[str, Any]]:
    """Fixture pour les opportunités d'arbitrage de test"""
    return fixture_loader.get_arbitrage_opportunities()

@pytest.fixture(scope="session")
def test_triangular_opportunities(fixture_loader: FixtureLoader) -> List[Dict[str, Any]]:
    """Fixture pour les opportunités triangulaires de test"""
    return fixture_loader.get_triangular_opportunities()

@pytest.fixture(scope="session")
def test_alerts(fixture_loader: FixtureLoader) -> List[Dict[str, Any]]:
    """Fixture pour les alertes de test"""
    return fixture_loader.get_alerts()

@pytest.fixture(scope="session")
def test_system_status(fixture_loader: FixtureLoader) -> Dict[str, Any]:
    """Fixture pour le statut système de test"""
    return fixture_loader.get_system_status()

@pytest.fixture(scope="session")
def test_performance_metrics(fixture_loader: FixtureLoader) -> Dict[str, Any]:
    """Fixture pour les métriques de performance de test"""
    return fixture_loader.get_performance_metrics()

@pytest.fixture(scope="session")
def all_fixtures(fixture_loader: FixtureLoader) -> Dict[str, Any]:
    """Fixture pour toutes les fixtures"""
    return fixture_loader.get_all_fixtures()

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_symbol_pairs() -> List[str]:
    """Récupère la liste des paires de trading"""
    data = get_fixture_loader().load_test_data()
    return list(data.get('tickers', {}).keys())

def get_exchanges() -> List[str]:
    """Récupère la liste des exchanges"""
    config = get_fixture_loader().load_config()
    return list(config.get('exchanges', {}).keys())

def get_strategies() -> List[str]:
    """Récupère la liste des stratégies"""
    config = get_fixture_loader().load_config()
    return list(config.get('strategies', {}).keys())

def get_assets() -> List[str]:
    """Récupère la liste des actifs"""
    balances = get_fixture_loader().get_balances()
    return list(balances.keys())

def get_symbol(symbol: str) -> Dict[str, Any]:
    """Récupère les données d'un symbole"""
    tickers = get_fixture_loader().get_tickers()
    return tickers.get(symbol, {})

def get_order_book(symbol: str) -> Dict[str, List[List[float]]]:
    """Récupère le carnet d'ordres d'un symbole"""
    order_books = get_fixture_loader().get_order_books()
    return order_books.get(symbol, {'bids': [], 'asks': []})

def get_balance(asset: str) -> Dict[str, float]:
    """Récupère le solde d'un actif"""
    balances = get_fixture_loader().get_balances()
    return balances.get(asset, {'free': 0.0, 'locked': 0.0, 'total': 0.0, 'usd_value': 0.0})

def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    """Récupère un ordre par son ID"""
    orders = get_fixture_loader().get_orders()
    for order_list in orders.values():
        for order in order_list:
            if order.get('id') == order_id:
                return order
    return None

def get_trade(trade_id: str) -> Optional[Dict[str, Any]]:
    """Récupère un trade par son ID"""
    trades = get_fixture_loader().get_trades()
    for trade in trades:
        if trade.get('id') == trade_id:
            return trade
    return None

def get_opportunity(opportunity_id: str) -> Optional[Dict[str, Any]]:
    """Récupère une opportunité par son ID"""
    opportunities = get_fixture_loader().get_arbitrage_opportunities()
    for opp in opportunities:
        if opp.get('id') == opportunity_id:
            return opp
    return None

def get_alert(alert_id: str) -> Optional[Dict[str, Any]]:
    """Récupère une alerte par son ID"""
    alerts = get_fixture_loader().get_alerts()
    for alert in alerts:
        if alert.get('id') == alert_id:
            return alert
    return None

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Paths
    'FIXTURES_DIR',
    'CONFIG_FILE',
    'MARKET_DATA_FILE',
    'TEST_DATA_FILE',
    
    # Classes
    'FixtureLoader',
    
    # Functions
    'get_fixture_loader',
    'get_symbol_pairs',
    'get_exchanges',
    'get_strategies',
    'get_assets',
    'get_symbol',
    'get_order_book',
    'get_balance',
    'get_order',
    'get_trade',
    'get_opportunity',
    'get_alert',
    
    # Pytest fixtures
    'fixture_loader',
    'test_config',
    'test_data',
    'market_data',
    'test_orders',
    'test_balances',
    'test_tickers',
    'test_order_books',
    'test_trades',
    'test_arbitrage_opportunities',
    'test_triangular_opportunities',
    'test_alerts',
    'test_system_status',
    'test_performance_metrics',
    'all_fixtures',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Test fixtures module initialized")

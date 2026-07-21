"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests unitaires et d'intégration pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import sys

# Ajouter le chemin du projet
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import du module à tester
from trading.bots.arbitrage_bot import ArbitrageBot
from trading.bots.arbitrage_bot.core.arbitrage_engine import ArbitrageEngine
from trading.bots.arbitrage_bot.core.exchange_manager import ExchangeManager
from trading.bots.arbitrage_bot.core.strategy_manager import StrategyManager
from trading.bots.arbitrage_bot.core.risk_manager import RiskManager
from trading.bots.arbitrage_bot.core.execution_engine import ExecutionEngine
from trading.bots.arbitrage_bot.core.market_data import MarketData
from trading.bots.arbitrage_bot.core.notification_manager import NotificationManager
from trading.bots.arbitrage_bot.config import ConfigLoader

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    fixture_loader,
    test_config,
    test_data,
    market_data,
    test_orders,
    test_balances,
    test_tickers,
    test_order_books,
    test_trades,
    test_arbitrage_opportunities,
    test_triangular_opportunities,
    test_alerts,
    test_system_status,
    test_performance_metrics,
    all_fixtures
)

from trading.bots.arbitrage_bot.tests.fixtures.exchange_mock import (
    MockExchange,
    MockExchangeFactory,
    OrderSide,
    OrderType,
    OrderStatus
)

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# TEST CONFIGURATION
# ============================================================

@pytest.fixture
def mock_exchange():
    """Fixture pour un mock exchange"""
    exchange = MockExchange("Test Exchange")
    exchange.start_market()
    yield exchange
    exchange.stop_market()

@pytest.fixture
def mock_exchanges():
    """Fixture pour plusieurs mock exchanges"""
    exchange1 = MockExchange("Exchange 1")
    exchange2 = MockExchange("Exchange 2")
    exchange1.start_market()
    exchange2.start_market()
    yield [exchange1, exchange2]
    exchange1.stop_market()
    exchange2.stop_market()

@pytest.fixture
def arbitrage_bot(test_config):
    """Fixture pour le bot d'arbitrage"""
    bot = ArbitrageBot(test_config)
    return bot

@pytest.fixture
def arbitrage_engine():
    """Fixture pour le moteur d'arbitrage"""
    return ArbitrageEngine()

@pytest.fixture
def exchange_manager():
    """Fixture pour le gestionnaire d'exchanges"""
    return ExchangeManager()

@pytest.fixture
def strategy_manager():
    """Fixture pour le gestionnaire de stratégies"""
    return StrategyManager()

@pytest.fixture
def risk_manager():
    """Fixture pour le gestionnaire de risques"""
    return RiskManager()

@pytest.fixture
def execution_engine():
    """Fixture pour le moteur d'exécution"""
    return ExecutionEngine()

@pytest.fixture
def market_data():
    """Fixture pour les données de marché"""
    return MarketData()

@pytest.fixture
def notification_manager():
    """Fixture pour le gestionnaire de notifications"""
    return NotificationManager()

# ============================================================
# ARBITRAGE BOT TESTS
# ============================================================

class TestArbitrageBot:
    """Tests pour le bot d'arbitrage"""

    def test_initialization(self, arbitrage_bot):
        """Test l'initialisation du bot"""
        assert arbitrage_bot is not None
        assert arbitrage_bot.config is not None
        assert arbitrage_bot.running is False

    def test_start_stop(self, arbitrage_bot):
        """Test le démarrage et l'arrêt du bot"""
        # Démarrer le bot
        arbitrage_bot.start()
        assert arbitrage_bot.running is True
        
        # Arrêter le bot
        arbitrage_bot.stop()
        assert arbitrage_bot.running is False

    @pytest.mark.asyncio
    async def test_async_operations(self, arbitrage_bot):
        """Test les opérations asynchrones"""
        # Démarrer le bot
        await arbitrage_bot.async_start()
        assert arbitrage_bot.running is True
        
        # Exécuter une opération
        result = await arbitrage_bot.async_scan_opportunities()
        assert result is not None
        
        # Arrêter le bot
        await arbitrage_bot.async_stop()
        assert arbitrage_bot.running is False

    def test_config_loading(self, arbitrage_bot, test_config):
        """Test le chargement de la configuration"""
        config = arbitrage_bot.get_config()
        assert config is not None
        assert config['bot']['environment'] == 'testing'

    def test_strategy_activation(self, arbitrage_bot):
        """Test l'activation des stratégies"""
        strategies = arbitrage_bot.get_strategies()
        assert len(strategies) > 0
        assert 'cross_exchange' in strategies
        assert 'triangular' in strategies

# ============================================================
# EXCHANGE MANAGER TESTS
# ============================================================

class TestExchangeManager:
    """Tests pour le gestionnaire d'exchanges"""

    def test_initialization(self, exchange_manager):
        """Test l'initialisation"""
        assert exchange_manager is not None
        assert len(exchange_manager.get_exchanges()) == 0

    def test_add_exchange(self, exchange_manager, mock_exchange):
        """Test l'ajout d'un exchange"""
        exchange_manager.add_exchange(mock_exchange)
        exchanges = exchange_manager.get_exchanges()
        assert len(exchanges) == 1
        assert exchanges[0].name == "Test Exchange"

    def test_remove_exchange(self, exchange_manager, mock_exchange):
        """Test la suppression d'un exchange"""
        exchange_manager.add_exchange(mock_exchange)
        exchange_manager.remove_exchange("Test Exchange")
        exchanges = exchange_manager.get_exchanges()
        assert len(exchanges) == 0

    def test_get_exchange_by_name(self, exchange_manager, mock_exchange):
        """Test la récupération d'un exchange par nom"""
        exchange_manager.add_exchange(mock_exchange)
        exchange = exchange_manager.get_exchange("Test Exchange")
        assert exchange is not None
        assert exchange.name == "Test Exchange"

    def test_get_all_balances(self, exchange_manager, mock_exchange):
        """Test la récupération des soldes"""
        exchange_manager.add_exchange(mock_exchange)
        balances = exchange_manager.get_all_balances()
        assert len(balances) > 0
        assert 'USDT' in balances

    @pytest.mark.asyncio
    async def test_update_prices(self, exchange_manager, mock_exchange):
        """Test la mise à jour des prix"""
        exchange_manager.add_exchange(mock_exchange)
        await exchange_manager.update_prices()
        
        symbols = exchange_manager.get_symbols()
        assert len(symbols) > 0
        for symbol in symbols:
            price = exchange_manager.get_price(symbol)
            assert price > 0

# ============================================================
# ARBITRAGE ENGINE TESTS
# ============================================================

class TestArbitrageEngine:
    """Tests pour le moteur d'arbitrage"""

    def test_initialization(self, arbitrage_engine):
        """Test l'initialisation"""
        assert arbitrage_engine is not None

    def test_scan_opportunities(self, arbitrage_engine, mock_exchanges):
        """Test le scan des opportunités"""
        # Ajouter les exchanges
        for exchange in mock_exchanges:
            arbitrage_engine.add_exchange(exchange)
        
        # Scanner les opportunités
        opportunities = arbitrage_engine.scan_opportunities()
        
        assert opportunities is not None
        # Vérifier que les opportunités ont la bonne structure
        for opp in opportunities:
            assert 'pair' in opp
            assert 'exchange_a' in opp
            assert 'exchange_b' in opp
            assert 'price_a' in opp
            assert 'price_b' in opp
            assert 'spread' in opp
            assert 'profit' in opp

    def test_calculate_spread(self, arbitrage_engine):
        """Test le calcul du spread"""
        spread = arbitrage_engine.calculate_spread(100.0, 101.0)
        assert spread == 1.0
        
        spread = arbitrage_engine.calculate_spread(100.0, 99.0)
        assert spread == -1.0

    def test_calculate_profit(self, arbitrage_engine):
        """Test le calcul du profit"""
        profit = arbitrage_engine.calculate_profit(100.0, 101.0, 1.0)
        assert profit > 0
        
        profit = arbitrage_engine.calculate_profit(100.0, 99.0, 1.0)
        assert profit < 0

    def test_validate_opportunity(self, arbitrage_engine):
        """Test la validation des opportunités"""
        opportunity = {
            'pair': 'BTC/USDT',
            'exchange_a': 'Exchange 1',
            'exchange_b': 'Exchange 2',
            'price_a': 100.0,
            'price_b': 101.0,
            'spread': 1.0,
            'profit': 0.9,
            'profit_percent': 0.009
        }
        
        is_valid = arbitrage_engine.validate_opportunity(opportunity)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_execute_opportunity(self, arbitrage_engine, mock_exchanges):
        """Test l'exécution d'une opportunité"""
        for exchange in mock_exchanges:
            arbitrage_engine.add_exchange(exchange)
        
        # Créer une opportunité simulée
        opportunity = {
            'pair': 'BTC/USDT',
            'exchange_a': 'Exchange 1',
            'exchange_b': 'Exchange 2',
            'price_a': 45000.0,
            'price_b': 45100.0,
            'spread': 100.0,
            'profit': 95.0,
            'profit_percent': 0.0021,
            'volume': 0.5
        }
        
        result = await arbitrage_engine.execute_opportunity(opportunity)
        assert result is True

# ============================================================
# STRATEGY MANAGER TESTS
# ============================================================

class TestStrategyManager:
    """Tests pour le gestionnaire de stratégies"""

    def test_initialization(self, strategy_manager):
        """Test l'initialisation"""
        assert strategy_manager is not None
        assert len(strategy_manager.get_strategies()) == 0

    def test_add_strategy(self, strategy_manager):
        """Test l'ajout d'une stratégie"""
        strategy = {
            'name': 'Test Strategy',
            'type': 'cross_exchange',
            'enabled': True,
            'parameters': {'min_profit': 0.01}
        }
        strategy_manager.add_strategy(strategy)
        strategies = strategy_manager.get_strategies()
        assert len(strategies) == 1
        assert strategies[0]['name'] == 'Test Strategy'

    def test_remove_strategy(self, strategy_manager):
        """Test la suppression d'une stratégie"""
        strategy = {
            'name': 'Test Strategy',
            'type': 'cross_exchange',
            'enabled': True
        }
        strategy_manager.add_strategy(strategy)
        strategy_manager.remove_strategy('Test Strategy')
        strategies = strategy_manager.get_strategies()
        assert len(strategies) == 0

    def test_enable_disable_strategy(self, strategy_manager):
        """Test l'activation/désactivation d'une stratégie"""
        strategy = {
            'name': 'Test Strategy',
            'type': 'cross_exchange',
            'enabled': False
        }
        strategy_manager.add_strategy(strategy)
        
        strategy_manager.enable_strategy('Test Strategy')
        assert strategy_manager.get_strategy('Test Strategy')['enabled'] is True
        
        strategy_manager.disable_strategy('Test Strategy')
        assert strategy_manager.get_strategy('Test Strategy')['enabled'] is False

    def test_get_active_strategies(self, strategy_manager):
        """Test la récupération des stratégies actives"""
        strategies = [
            {'name': 'Strategy 1', 'type': 'cross_exchange', 'enabled': True},
            {'name': 'Strategy 2', 'type': 'triangular', 'enabled': False},
            {'name': 'Strategy 3', 'type': 'statistical', 'enabled': True}
        ]
        
        for strategy in strategies:
            strategy_manager.add_strategy(strategy)
        
        active = strategy_manager.get_active_strategies()
        assert len(active) == 2
        assert active[0]['name'] == 'Strategy 1'
        assert active[1]['name'] == 'Strategy 3'

    @pytest.mark.asyncio
    async def test_execute_strategies(self, strategy_manager, mock_exchanges):
        """Test l'exécution des stratégies"""
        # Ajouter les exchanges
        for exchange in mock_exchanges:
            strategy_manager.add_exchange(exchange)
        
        # Ajouter une stratégie
        strategy = {
            'name': 'Test Strategy',
            'type': 'cross_exchange',
            'enabled': True,
            'parameters': {
                'min_profit': 0.001,
                'max_spread': 0.10,
                'min_volume': 10
            }
        }
        strategy_manager.add_strategy(strategy)
        
        # Exécuter les stratégies
        results = await strategy_manager.execute_strategies()
        assert len(results) > 0

# ============================================================
# RISK MANAGER TESTS
# ============================================================

class TestRiskManager:
    """Tests pour le gestionnaire de risques"""

    def test_initialization(self, risk_manager):
        """Test l'initialisation"""
        assert risk_manager is not None
        assert risk_manager.get_risk_level() == 'medium'

    def test_set_risk_level(self, risk_manager):
        """Test la définition du niveau de risque"""
        risk_manager.set_risk_level('high')
        assert risk_manager.get_risk_level() == 'high'
        
        risk_manager.set_risk_level('low')
        assert risk_manager.get_risk_level() == 'low'

    def test_calculate_position_size(self, risk_manager):
        """Test le calcul de la taille de position"""
        # Test avec différents niveaux de risque
        risk_manager.set_risk_level('low')
        size = risk_manager.calculate_position_size(10000.0, 0.01)
        assert size <= 100.0  # 1% de 10000
        
        risk_manager.set_risk_level('high')
        size = risk_manager.calculate_position_size(10000.0, 0.01)
        assert size >= 200.0  # 2% de 10000

    def test_check_drawdown(self, risk_manager):
        """Test la vérification du drawdown"""
        # Simuler un historique de PnL
        pnl_history = [100, 200, 300, 250, 200, 150]
        drawdown = risk_manager.calculate_drawdown(pnl_history)
        assert drawdown > 0
        
        # Vérifier le seuil de drawdown
        is_exceeded = risk_manager.check_drawdown(pnl_history, 0.2)
        assert is_exceeded is True

    def test_validate_trade(self, risk_manager):
        """Test la validation d'un trade"""
        trade = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'quantity': 0.5,
            'price': 45000.0,
            'risk': 0.01
        }
        
        is_valid = risk_manager.validate_trade(trade)
        assert is_valid is True
        
        # Test avec un trade trop risqué
        trade['risk'] = 0.05
        is_valid = risk_manager.validate_trade(trade)
        assert is_valid is False

    def test_apply_stop_loss(self, risk_manager):
        """Test l'application du stop loss"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 44500.0,
            'quantity': 0.5
        }
        
        stop_price = risk_manager.calculate_stop_loss(position, 0.02)
        assert stop_price < position['entry_price']
        
        # Vérifier si le stop loss est déclenché
        should_stop = risk_manager.check_stop_loss(position, 0.02)
        assert should_stop is True

    def test_apply_take_profit(self, risk_manager):
        """Test l'application du take profit"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 46000.0,
            'quantity': 0.5
        }
        
        take_price = risk_manager.calculate_take_profit(position, 0.03)
        assert take_price > position['entry_price']
        
        # Vérifier si le take profit est déclenché
        should_take = risk_manager.check_take_profit(position, 0.03)
        assert should_take is True

# ============================================================
# EXECUTION ENGINE TESTS
# ============================================================

class TestExecutionEngine:
    """Tests pour le moteur d'exécution"""

    def test_initialization(self, execution_engine):
        """Test l'initialisation"""
        assert execution_engine is not None
        assert len(execution_engine.get_orders()) == 0

    def test_create_order(self, execution_engine, mock_exchange):
        """Test la création d'un ordre"""
        execution_engine.add_exchange(mock_exchange)
        
        order = execution_engine.create_order(
            symbol='BTC/USDT',
            side='BUY',
            order_type='LIMIT',
            quantity=0.5,
            price=45000.0
        )
        
        assert order is not None
        assert order['symbol'] == 'BTC/USDT'
        assert order['side'] == 'BUY'
        assert order['quantity'] == 0.5

    def test_cancel_order(self, execution_engine, mock_exchange):
        """Test l'annulation d'un ordre"""
        execution_engine.add_exchange(mock_exchange)
        
        # Créer un ordre
        order = execution_engine.create_order(
            symbol='BTC/USDT',
            side='BUY',
            order_type='LIMIT',
            quantity=0.5,
            price=45000.0
        )
        
        # Annuler l'ordre
        result = execution_engine.cancel_order(order['id'])
        assert result is True

    def test_get_order_status(self, execution_engine, mock_exchange):
        """Test la récupération du statut d'un ordre"""
        execution_engine.add_exchange(mock_exchange)
        
        # Créer un ordre
        order = execution_engine.create_order(
            symbol='BTC/USDT',
            side='BUY',
            order_type='LIMIT',
            quantity=0.5,
            price=45000.0
        )
        
        # Récupérer le statut
        status = execution_engine.get_order_status(order['id'])
        assert status is not None
        assert status in ['NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED']

    @pytest.mark.asyncio
    async def test_execute_order(self, execution_engine, mock_exchange):
        """Test l'exécution d'un ordre"""
        execution_engine.add_exchange(mock_exchange)
        
        # Créer un ordre au marché
        order = execution_engine.create_order(
            symbol='BTC/USDT',
            side='BUY',
            order_type='MARKET',
            quantity=0.5
        )
        
        # Exécuter l'ordre
        result = await execution_engine.execute_order(order['id'])
        assert result is True
        
        # Vérifier le statut
        status = execution_engine.get_order_status(order['id'])
        assert status == 'FILLED'

# ============================================================
# MARKET DATA TESTS
# ============================================================

class TestMarketData:
    """Tests pour les données de marché"""

    def test_initialization(self, market_data):
        """Test l'initialisation"""
        assert market_data is not None

    def test_get_price(self, market_data, mock_exchange):
        """Test la récupération du prix"""
        market_data.add_exchange(mock_exchange)
        
        price = market_data.get_price('BTC/USDT', 'Test Exchange')
        assert price > 0

    def test_get_ticker(self, market_data, mock_exchange):
        """Test la récupération du ticker"""
        market_data.add_exchange(mock_exchange)
        
        ticker = market_data.get_ticker('BTC/USDT', 'Test Exchange')
        assert ticker is not None
        assert 'bid' in ticker
        assert 'ask' in ticker
        assert 'last' in ticker

    def test_get_order_book(self, market_data, mock_exchange):
        """Test la récupération du carnet d'ordres"""
        market_data.add_exchange(mock_exchange)
        
        order_book = market_data.get_order_book('BTC/USDT', 'Test Exchange')
        assert order_book is not None
        assert 'bids' in order_book
        assert 'asks' in order_book
        assert len(order_book['bids']) > 0
        assert len(order_book['asks']) > 0

    def test_get_klines(self, market_data, mock_exchange):
        """Test la récupération des bougies"""
        market_data.add_exchange(mock_exchange)
        
        klines = market_data.get_klines('BTC/USDT', '1m', 10)
        assert len(klines) == 10
        for kline in klines:
            assert 'open' in kline
            assert 'high' in kline
            assert 'low' in kline
            assert 'close' in kline
            assert 'volume' in kline

    @pytest.mark.asyncio
    async def test_subscribe_websocket(self, market_data, mock_exchange):
        """Test l'abonnement WebSocket"""
        market_data.add_exchange(mock_exchange)
        
        async def on_ticker(data):
            assert data is not None
        
        await market_data.subscribe_websocket('BTC/USDT', on_ticker)
        assert 'BTC/USDT' in market_data.get_subscriptions()

# ============================================================
# NOTIFICATION MANAGER TESTS
# ============================================================

class TestNotificationManager:
    """Tests pour le gestionnaire de notifications"""

    def test_initialization(self, notification_manager):
        """Test l'initialisation"""
        assert notification_manager is not None

    def test_send_notification(self, notification_manager):
        """Test l'envoi d'une notification"""
        notification = {
            'type': 'INFO',
            'message': 'Test notification',
            'severity': 'info',
            'timestamp': datetime.now().isoformat()
        }
        
        result = notification_manager.send_notification(notification)
        assert result is True

    def test_add_channel(self, notification_manager):
        """Test l'ajout d'un canal"""
        channel = {
            'name': 'Test Channel',
            'type': 'console',
            'enabled': True
        }
        
        notification_manager.add_channel(channel)
        channels = notification_manager.get_channels()
        assert len(channels) == 1
        assert channels[0]['name'] == 'Test Channel'

    def test_remove_channel(self, notification_manager):
        """Test la suppression d'un canal"""
        channel = {
            'name': 'Test Channel',
            'type': 'console',
            'enabled': True
        }
        
        notification_manager.add_channel(channel)
        notification_manager.remove_channel('Test Channel')
        channels = notification_manager.get_channels()
        assert len(channels) == 0

    def test_get_active_channels(self, notification_manager):
        """Test la récupération des canaux actifs"""
        channels = [
            {'name': 'Channel 1', 'type': 'console', 'enabled': True},
            {'name': 'Channel 2', 'type': 'telegram', 'enabled': False},
            {'name': 'Channel 3', 'type': 'slack', 'enabled': True}
        ]
        
        for channel in channels:
            notification_manager.add_channel(channel)
        
        active = notification_manager.get_active_channels()
        assert len(active) == 2
        assert active[0]['name'] == 'Channel 1'
        assert active[1]['name'] == 'Channel 3'

# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestIntegration:
    """Tests d'intégration"""

    @pytest.mark.asyncio
    async def test_full_arbitrage_flow(self, mock_exchanges, test_config):
        """Test le flux complet d'arbitrage"""
        # Initialiser les composants
        exchange_manager = ExchangeManager()
        strategy_manager = StrategyManager()
        risk_manager = RiskManager()
        execution_engine = ExecutionEngine()
        market_data = MarketData()
        notification_manager = NotificationManager()
        
        # Ajouter les exchanges
        for exchange in mock_exchanges:
            exchange_manager.add_exchange(exchange)
            market_data.add_exchange(exchange)
            execution_engine.add_exchange(exchange)
        
        # Ajouter une stratégie
        strategy = {
            'name': 'Cross Exchange',
            'type': 'cross_exchange',
            'enabled': True,
            'parameters': {
                'min_profit': 0.001,
                'max_spread': 0.10,
                'min_volume': 10
            }
        }
        strategy_manager.add_strategy(strategy)
        
        # Scanner les opportunités
        opportunities = []
        for strategy in strategy_manager.get_active_strategies():
            opps = await strategy_manager.execute_strategy(strategy)
            opportunities.extend(opps)
        
        assert len(opportunities) > 0
        
        # Valider les opportunités
        validated = []
        for opp in opportunities:
            if risk_manager.validate_opportunity(opp):
                validated.append(opp)
        
        assert len(validated) > 0
        
        # Exécuter les opportunités
        for opp in validated[:5]:  # Limiter pour les tests
            result = await execution_engine.execute_opportunity(opp)
            assert result is True
            
            # Envoyer une notification
            notification = {
                'type': 'EXECUTION',
                'message': f"Trade executed: {opp['pair']}",
                'severity': 'info',
                'timestamp': datetime.now().isoformat()
            }
            notification_manager.send_notification(notification)

    @pytest.mark.asyncio
    async def test_error_recovery(self, mock_exchanges):
        """Test la récupération d'erreurs"""
        # Simuler une erreur de connexion
        exchange = mock_exchanges[0]
        exchange.market_running = False
        
        # Tenter de récupérer les données
        try:
            price = exchange.get_price('BTC/USDT')
            assert price is not None
        except Exception as e:
            # Vérifier que l'erreur est gérée
            assert str(e) is not None
            
            # Tenter de reconnecter
            exchange.start_market()
            time.sleep(0.5)
            
            # Vérifier que les données sont disponibles
            price = exchange.get_price('BTC/USDT')
            assert price > 0

    def test_performance_benchmark(self, mock_exchanges):
        """Test des performances"""
        import time
        
        # Mesurer le temps de scan des opportunités
        engine = ArbitrageEngine()
        for exchange in mock_exchanges:
            engine.add_exchange(exchange)
        
        start_time = time.time()
        opportunities = engine.scan_opportunities()
        end_time = time.time()
        
        scan_time = end_time - start_time
        assert scan_time < 1.0  # Moins de 1 seconde
        
        # Vérifier le nombre d'opportunités
        assert len(opportunities) > 0

# ============================================================
# EDGE CASES TESTS
# ============================================================

class TestEdgeCases:
    """Tests des cas limites"""

    def test_empty_market_data(self):
        """Test avec des données de marché vides"""
        market_data = MarketData()
        price = market_data.get_price('BTC/USDT', 'Test Exchange')
        assert price == 0.0
        
        ticker = market_data.get_ticker('BTC/USDT', 'Test Exchange')
        assert ticker is None

    def test_zero_profit_opportunity(self, arbitrage_engine):
        """Test une opportunité avec profit nul"""
        opportunity = {
            'pair': 'BTC/USDT',
            'exchange_a': 'Exchange 1',
            'exchange_b': 'Exchange 2',
            'price_a': 100.0,
            'price_b': 100.0,
            'spread': 0.0,
            'profit': 0.0,
            'profit_percent': 0.0
        }
        
        is_valid = arbitrage_engine.validate_opportunity(opportunity)
        assert is_valid is False

    def test_negative_profit_opportunity(self, arbitrage_engine):
        """Test une opportunité avec profit négatif"""
        opportunity = {
            'pair': 'BTC/USDT',
            'exchange_a': 'Exchange 1',
            'exchange_b': 'Exchange 2',
            'price_a': 101.0,
            'price_b': 100.0,
            'spread': -1.0,
            'profit': -0.95,
            'profit_percent': -0.0095
        }
        
        is_valid = arbitrage_engine.validate_opportunity(opportunity)
        assert is_valid is False

    def test_insufficient_balance(self, risk_manager):
        """Test l'insuffisance de solde"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'quantity': 1000.0,
            'balance': 100.0
        }
        
        is_valid = risk_manager.validate_trade(position)
        assert is_valid is False

    def test_max_positions_reached(self, risk_manager):
        """Test la limite de positions atteinte"""
        # Simuler 10 positions actives
        for i in range(10):
            risk_manager.add_position({'id': f'pos_{i}'})
        
        can_add = risk_manager.can_add_position()
        assert can_add is False

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

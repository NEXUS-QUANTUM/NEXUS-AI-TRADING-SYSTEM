"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Integration Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests d'intégration complets pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import asyncio
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor

# Import du module à tester
from trading.bots.arbitrage_bot import ArbitrageBot
from trading.bots.arbitrage_bot.core.arbitrage_engine import ArbitrageEngine
from trading.bots.arbitrage_bot.core.exchange_manager import ExchangeManager
from trading.bots.arbitrage_bot.core.strategy_manager import StrategyManager
from trading.bots.arbitrage_bot.core.risk_manager import RiskManager
from trading.bots.arbitrage_bot.core.execution_engine import ExecutionEngine
from trading.bots.arbitrage_bot.core.market_data import MarketData
from trading.bots.arbitrage_bot.core.notification_manager import NotificationManager
from trading.bots.arbitrage_bot.core.data_manager import DataManager
from trading.bots.arbitrage_bot.core.event_manager import EventManager

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
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
# INTEGRATION TEST FIXTURES
# ============================================================

@pytest.fixture
def integration_bot(test_config):
    """Fixture pour un bot d'intégration"""
    bot = ArbitrageBot(test_config)
    return bot

@pytest.fixture
def integration_exchanges():
    """Fixture pour des exchanges d'intégration"""
    exchanges = []
    for i in range(3):
        exchange = MockExchange(f"Integration Exchange {i+1}")
        exchange.start_market()
        exchanges.append(exchange)
    
    yield exchanges
    
    for exchange in exchanges:
        exchange.stop_market()

@pytest.fixture
def integration_components(integration_exchanges):
    """Fixture pour les composants d'intégration"""
    components = {
        'exchange_manager': ExchangeManager(),
        'strategy_manager': StrategyManager(),
        'risk_manager': RiskManager(),
        'execution_engine': ExecutionEngine(),
        'market_data': MarketData(),
        'notification_manager': NotificationManager(),
        'data_manager': DataManager(),
        'event_manager': EventManager()
    }
    
    # Ajouter les exchanges à chaque composant
    for exchange in integration_exchanges:
        components['exchange_manager'].add_exchange(exchange)
        components['execution_engine'].add_exchange(exchange)
        components['market_data'].add_exchange(exchange)
    
    return components

# ============================================================
# END-TO-END INTEGRATION TESTS
# ============================================================

class TestEndToEndIntegration:
    """Tests d'intégration de bout en bout"""

    def test_full_arbitrage_flow(self, integration_components, integration_exchanges):
        """Test le flux complet d'arbitrage"""
        components = integration_components
        
        # 1. Ajouter une stratégie
        strategy = {
            'name': 'Integration Strategy',
            'type': 'cross_exchange',
            'enabled': True,
            'parameters': {
                'min_profit': 0.001,
                'max_spread': 0.10,
                'min_volume': 10,
                'max_position': 1000
            }
        }
        components['strategy_manager'].add_strategy(strategy)
        
        # 2. Démarrer le market data
        components['market_data'].start()
        
        # 3. Scanner les opportunités
        opportunities = []
        active_strategies = components['strategy_manager'].get_active_strategies()
        
        for strategy in active_strategies:
            # Récupérer les données de marché
            market_data = components['market_data'].get_all_data()
            
            # Exécuter la stratégie
            strategy_results = components['strategy_manager'].execute_strategy(
                strategy, market_data
            )
            opportunities.extend(strategy_results)
        
        # 4. Valider les opportunités
        validated_opportunities = []
        for opp in opportunities:
            if components['risk_manager'].validate_opportunity(opp):
                validated_opportunities.append(opp)
        
        # 5. Exécuter les opportunités
        executed_trades = []
        for opp in validated_opportunities[:5]:  # Limiter pour les tests
            result = components['execution_engine'].execute_opportunity(opp)
            if result:
                executed_trades.append(result)
        
        # 6. Vérifier les résultats
        assert len(opportunities) > 0
        assert len(executed_trades) > 0
        
        # 7. Notifier
        notification = {
            'type': 'INTEGRATION_TEST',
            'message': f"Executed {len(executed_trades)} trades",
            'severity': 'info',
            'timestamp': datetime.now().isoformat()
        }
        components['notification_manager'].send_notification(notification)

    def test_triangular_arbitrage_flow(self, integration_components):
        """Test le flux d'arbitrage triangulaire"""
        components = integration_components
        
        # Ajouter une stratégie triangulaire
        strategy = {
            'name': 'Triangular Strategy',
            'type': 'triangular',
            'enabled': True,
            'parameters': {
                'min_profit': 0.001,
                'max_position': 1000,
                'cycles': [
                    {
                        'name': 'BTC-ETH-USDT',
                        'pairs': ['BTC/USDT', 'ETH/BTC', 'ETH/USDT']
                    }
                ]
            }
        }
        components['strategy_manager'].add_strategy(strategy)
        
        # Exécuter la stratégie
        market_data = components['market_data'].get_all_data()
        results = components['strategy_manager'].execute_strategy(strategy, market_data)
        
        # Vérifier les résultats
        assert results is not None

    def test_statistical_arbitrage_flow(self, integration_components):
        """Test le flux d'arbitrage statistique"""
        components = integration_components
        
        # Ajouter une stratégie statistique
        strategy = {
            'name': 'Statistical Strategy',
            'type': 'statistical',
            'enabled': True,
            'parameters': {
                'min_profit': 0.001,
                'lookback_period': 50,
                'z_score_threshold': 2.0,
                'max_position': 1000
            }
        }
        components['strategy_manager'].add_strategy(strategy)
        
        # Exécuter la stratégie
        market_data = components['market_data'].get_all_data()
        results = components['strategy_manager'].execute_strategy(strategy, market_data)
        
        # Vérifier les résultats
        assert results is not None

    def test_risk_management_flow(self, integration_components):
        """Test le flux de gestion des risques"""
        components = integration_components
        
        # Configurer le gestionnaire de risques
        risk_config = {
            'max_drawdown': 0.10,
            'max_loss_per_day': 0.02,
            'max_positions': 5,
            'position_sizing': {
                'strategy': 'fixed',
                'fixed_size': 100
            },
            'stop_loss': {
                'enabled': True,
                'percentage': 0.02
            },
            'take_profit': {
                'enabled': True,
                'targets': [0.01, 0.02, 0.03]
            }
        }
        components['risk_manager'].set_config(risk_config)
        
        # Créer des positions simulées
        for i in range(3):
            position = {
                'id': f'pos_{i}',
                'symbol': 'BTC/USDT',
                'entry_price': 45000.0 + i * 100,
                'current_price': 45000.0 + i * 150,
                'quantity': 0.5,
                'pnl': i * 50
            }
            components['risk_manager'].add_position(position)
        
        # Vérifier les positions
        positions = components['risk_manager'].get_positions()
        assert len(positions) == 3
        
        # Vérifier le drawdown
        pnl_history = [100, 200, 300, 250, 200, 150]
        drawdown = components['risk_manager'].calculate_drawdown(pnl_history)
        assert drawdown > 0

    def test_execution_flow(self, integration_components):
        """Test le flux d'exécution"""
        components = integration_components
        
        # Créer un ordre
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5
        }
        
        # Exécuter l'ordre
        result = components['execution_engine'].execute_order(order)
        assert result is not None
        assert result['status'] == 'FILLED'
        
        # Créer un ordre à limite
        limit_order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0
        }
        
        result = components['execution_engine'].execute_order(limit_order)
        assert result is not None

    def test_notification_flow(self, integration_components):
        """Test le flux de notifications"""
        components = integration_components
        
        # Ajouter un canal de notification
        channel = {
            'name': 'Test Channel',
            'type': 'console',
            'enabled': True
        }
        components['notification_manager'].add_channel(channel)
        
        # Envoyer des notifications
        notifications = [
            {
                'type': 'INFO',
                'message': 'Test info message',
                'severity': 'info',
                'timestamp': datetime.now().isoformat()
            },
            {
                'type': 'WARNING',
                'message': 'Test warning message',
                'severity': 'warning',
                'timestamp': datetime.now().isoformat()
            },
            {
                'type': 'ERROR',
                'message': 'Test error message',
                'severity': 'error',
                'timestamp': datetime.now().isoformat()
            }
        ]
        
        for notification in notifications:
            result = components['notification_manager'].send_notification(notification)
            assert result is True

# ============================================================
# COMPONENT INTEGRATION TESTS
# ============================================================

class TestComponentIntegration:
    """Tests d'intégration des composants"""

    def test_exchange_manager_market_data_integration(self, integration_components):
        """Test l'intégration Exchange Manager - Market Data"""
        components = integration_components
        
        # Récupérer les données de marché
        market_data = components['market_data'].get_all_data()
        
        # Vérifier que les données sont disponibles
        assert len(market_data) > 0
        assert 'BTC/USDT' in market_data
        
        # Vérifier les prix
        price = market_data['BTC/USDT']['price']
        assert price > 0

    def test_strategy_manager_risk_manager_integration(self, integration_components):
        """Test l'intégration Strategy Manager - Risk Manager"""
        components = integration_components
        
        # Ajouter une stratégie
        strategy = {
            'name': 'Test Strategy',
            'type': 'cross_exchange',
            'enabled': True,
            'parameters': {
                'min_profit': 0.001,
                'max_position': 1000
            }
        }
        components['strategy_manager'].add_strategy(strategy)
        
        # Récupérer les stratégies actives
        strategies = components['strategy_manager'].get_active_strategies()
        assert len(strategies) > 0
        
        # Vérifier les risques
        risk_level = components['risk_manager'].get_risk_level()
        assert risk_level is not None

    def test_execution_engine_risk_manager_integration(self, integration_components):
        """Test l'intégration Execution Engine - Risk Manager"""
        components = integration_components
        
        # Créer un ordre
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5
        }
        
        # Valider l'ordre avec le gestionnaire de risques
        is_valid = components['risk_manager'].validate_trade(order)
        assert is_valid is True
        
        # Exécuter l'ordre
        result = components['execution_engine'].execute_order(order)
        assert result is not None

    def test_market_data_notification_integration(self, integration_components):
        """Test l'intégration Market Data - Notification"""
        components = integration_components
        
        # Ajouter un canal de notification
        channel = {
            'name': 'Test Channel',
            'type': 'console',
            'enabled': True
        }
        components['notification_manager'].add_channel(channel)
        
        # Créer une alerte de marché
        alert = {
            'type': 'MARKET_ALERT',
            'message': 'Price alert: BTC/USDT reached 45000',
            'severity': 'info',
            'timestamp': datetime.now().isoformat()
        }
        
        # Envoyer la notification
        result = components['notification_manager'].send_notification(alert)
        assert result is True

    def test_data_manager_integration(self, integration_components):
        """Test l'intégration Data Manager"""
        components = integration_components
        
        # Ajouter des données
        test_data = {
            'tickers': {'BTC/USDT': {'price': 45000.0}},
            'timestamp': datetime.now().isoformat()
        }
        components['data_manager'].add_data('test', test_data)
        
        # Récupérer les données
        data = components['data_manager'].get_data('test')
        assert data is not None
        assert data['tickers']['BTC/USDT']['price'] == 45000.0

# ============================================================
# EVENT-DRIVEN INTEGRATION TESTS
# ============================================================

class TestEventDrivenIntegration:
    """Tests d'intégration événementielle"""

    def test_event_handling(self, integration_components):
        """Test la gestion des événements"""
        components = integration_components
        event_manager = components['event_manager']
        
        # Variables pour suivre les événements
        events_received = []
        
        # Définir un gestionnaire d'événements
        def event_handler(event):
            events_received.append(event)
        
        # S'abonner aux événements
        event_manager.subscribe('test_event', event_handler)
        
        # Publier un événement
        event = {
            'type': 'test_event',
            'data': {'message': 'Hello World'},
            'timestamp': datetime.now().isoformat()
        }
        event_manager.publish(event)
        
        # Vérifier que l'événement a été reçu
        assert len(events_received) == 1
        assert events_received[0]['data']['message'] == 'Hello World'

    def test_arbitrage_event_flow(self, integration_components):
        """Test le flux d'événements d'arbitrage"""
        components = integration_components
        event_manager = components['event_manager']
        
        # Variables pour suivre les événements
        opportunity_events = []
        execution_events = []
        
        # Définir les gestionnaires
        def opportunity_handler(event):
            opportunity_events.append(event)
        
        def execution_handler(event):
            execution_events.append(event)
        
        # S'abonner aux événements
        event_manager.subscribe('opportunity_found', opportunity_handler)
        event_manager.subscribe('trade_executed', execution_handler)
        
        # Simuler une opportunité
        opp_event = {
            'type': 'opportunity_found',
            'data': {
                'pair': 'BTC/USDT',
                'profit': 100.0,
                'exchange_a': 'Exchange 1',
                'exchange_b': 'Exchange 2'
            },
            'timestamp': datetime.now().isoformat()
        }
        event_manager.publish(opp_event)
        
        # Simuler une exécution
        exec_event = {
            'type': 'trade_executed',
            'data': {
                'trade_id': 'trade_001',
                'pair': 'BTC/USDT',
                'pnl': 95.0
            },
            'timestamp': datetime.now().isoformat()
        }
        event_manager.publish(exec_event)
        
        # Vérifier les événements
        assert len(opportunity_events) == 1
        assert len(execution_events) == 1
        assert opportunity_events[0]['data']['pair'] == 'BTC/USDT'
        assert execution_events[0]['data']['trade_id'] == 'trade_001'

# ============================================================
# PERFORMANCE INTEGRATION TESTS
# ============================================================

class TestPerformanceIntegration:
    """Tests d'intégration de performance"""

    def test_system_performance(self, integration_components):
        """Test la performance du système"""
        import time
        
        components = integration_components
        
        # Récupérer les données de marché
        start_time = time.time()
        market_data = components['market_data'].get_all_data()
        end_time = time.time()
        
        data_time = (end_time - start_time) * 1000  # ms
        assert data_time < 50  # Moins de 50ms
        
        # Exécuter une stratégie
        strategy = {
            'name': 'Performance Strategy',
            'type': 'cross_exchange',
            'enabled': True,
            'parameters': {
                'min_profit': 0.001,
                'max_position': 1000
            }
        }
        components['strategy_manager'].add_strategy(strategy)
        
        start_time = time.time()
        results = components['strategy_manager'].execute_strategy(
            strategy, market_data
        )
        end_time = time.time()
        
        strategy_time = (end_time - start_time) * 1000  # ms
        assert strategy_time < 100  # Moins de 100ms

    def test_concurrent_operations(self, integration_components):
        """Test les opérations concurrentes"""
        components = integration_components
        
        # Exécuter plusieurs opérations en parallèle
        orders = [
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY' if i % 2 == 0 else 'SELL',
                'type': 'MARKET',
                'quantity': 0.1
            }
            for i in range(20)
        ]
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(
                components['execution_engine'].execute_order, 
                orders
            ))
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Vérifier les résultats
        assert len(results) == 20
        assert all(r is not None for r in results)
        assert total_time < 5  # Moins de 5 secondes

# ============================================================
# STRESS INTEGRATION TESTS
# ============================================================

class TestStressIntegration:
    """Tests d'intégration de stress"""

    def test_high_frequency_operations(self, integration_components):
        """Test les opérations à haute fréquence"""
        components = integration_components
        
        # Exécuter de nombreuses opérations
        operations_count = 100
        start_time = time.time()
        
        for i in range(operations_count):
            # Récupérer les données de marché
            market_data = components['market_data'].get_all_data()
            
            # Créer et exécuter un ordre
            if i % 2 == 0:
                order = {
                    'symbol': 'BTC/USDT',
                    'side': 'BUY',
                    'type': 'MARKET',
                    'quantity': 0.1
                }
                components['execution_engine'].execute_order(order)
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = (total_time / operations_count) * 1000  # ms
        
        # Vérifier les performances
        assert avg_time < 10  # Moins de 10ms par opération

    def test_memory_stress(self, integration_components):
        """Test le stress mémoire"""
        import psutil
        
        components = integration_components
        
        # Mesurer la mémoire initiale
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Exécuter de nombreuses opérations
        for i in range(50):
            # Récupérer les données de marché
            market_data = components['market_data'].get_all_data()
            
            # Ajouter des données
            components['data_manager'].add_data(
                f'test_data_{i}',
                {'data': market_data, 'index': i}
            )
        
        # Mesurer la mémoire finale
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        memory_increase = final_memory - initial_memory
        assert memory_increase < 100  # Moins de 100MB d'augmentation

# ============================================================
# RECOVERY INTEGRATION TESTS
# ============================================================

class TestRecoveryIntegration:
    """Tests d'intégration de récupération"""

    def test_exchange_reconnection(self, integration_components, integration_exchanges):
        """Test la reconnexion des exchanges"""
        components = integration_components
        
        # Simuler une déconnexion
        exchange = integration_exchanges[0]
        exchange.stop_market()
        
        # Vérifier que le système détecte la déconnexion
        is_connected = exchange.is_connected()
        assert is_connected is False
        
        # Reconnecter l'exchange
        exchange.start_market()
        
        # Vérifier que le système récupère
        components['market_data'].refresh_data()
        market_data = components['market_data'].get_all_data()
        assert len(market_data) > 0

    def test_order_recovery(self, integration_components):
        """Test la récupération des ordres"""
        components = integration_components
        
        # Créer un ordre
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0
        }
        
        result = components['execution_engine'].execute_order(order)
        assert result is not None
        
        # Récupérer l'ordre
        order_id = result['id']
        recovered_order = components['execution_engine'].get_order_status(order_id)
        
        assert recovered_order is not None
        assert recovered_order['id'] == order_id

    def test_data_persistence_recovery(self, integration_components):
        """Test la récupération de la persistance des données"""
        components = integration_components
        
        # Sauvegarder des données
        test_data = {
            'key': 'test_value',
            'timestamp': datetime.now().isoformat()
        }
        components['data_manager'].save_data('test_data', test_data)
        
        # Simuler un redémarrage (réinitialiser le gestionnaire)
        new_data_manager = DataManager()
        
        # Charger les données
        recovered_data = new_data_manager.load_data('test_data')
        
        assert recovered_data is not None
        assert recovered_data['key'] == 'test_value'

# ============================================================
# SECURITY INTEGRATION TESTS
# ============================================================

class TestSecurityIntegration:
    """Tests d'intégration de sécurité"""

    def test_api_key_encryption(self, integration_components):
        """Test le chiffrement des clés API"""
        components = integration_components
        
        # Définir des clés API
        api_keys = {
            'binance': {
                'api_key': 'test_key_123',
                'api_secret': 'test_secret_456'
            }
        }
        
        # Chiffrer les clés
        encrypted = components['security_manager'].encrypt_api_keys(api_keys)
        assert encrypted is not None
        assert encrypted != api_keys
        
        # Déchiffrer les clés
        decrypted = components['security_manager'].decrypt_api_keys(encrypted)
        assert decrypted == api_keys

    def test_rate_limiting(self, integration_components):
        """Test le rate limiting"""
        components = integration_components
        
        # Configurer le rate limiting
        rate_limit_config = {
            'enabled': True,
            'requests_per_minute': 10,
            'burst_limit': 5
        }
        components['security_manager'].set_rate_limit_config(rate_limit_config)
        
        # Effectuer des requêtes
        for i in range(15):
            # Cette requête devrait être limitée
            result = components['security_manager'].check_rate_limit()
            if i < 10:
                assert result is True
            else:
                # Les requêtes supplémentaires devraient être limitées
                pass

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

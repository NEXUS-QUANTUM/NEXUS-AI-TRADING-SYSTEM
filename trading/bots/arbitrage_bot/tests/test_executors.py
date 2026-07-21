"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Executors Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests des exécuteurs d'ordres pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor

# Import du module à tester
from trading.bots.arbitrage_bot.executors.base_executor import BaseExecutor
from trading.bots.arbitrage_bot.executors.market_executor import MarketExecutor
from trading.bots.arbitrage_bot.executors.limit_executor import LimitExecutor
from trading.bots.arbitrage_bot.executors.smart_executor import SmartExecutor
from trading.bots.arbitrage_bot.executors.batch_executor import BatchExecutor
from trading.bots.arbitrage_bot.executors.executor_factory import ExecutorFactory
from trading.bots.arbitrage_bot.executors.executor_manager import ExecutorManager

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    test_data,
    test_orders,
    test_trades,
    test_balances
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
# BASE EXECUTOR TESTS
# ============================================================

class TestBaseExecutor:
    """Tests pour l'exécuteur de base"""

    @pytest.fixture
    def base_executor(self):
        """Fixture pour un exécuteur de base"""
        return BaseExecutor()

    def test_initialization(self, base_executor):
        """Test l'initialisation"""
        assert base_executor is not None
        assert base_executor.is_running() is False

    def test_start_stop(self, base_executor):
        """Test le démarrage/arrêt"""
        base_executor.start()
        assert base_executor.is_running() is True
        
        base_executor.stop()
        assert base_executor.is_running() is False

    def test_set_config(self, base_executor):
        """Test la configuration"""
        config = {'timeout': 30, 'retry_attempts': 3}
        base_executor.set_config(config)
        assert base_executor.get_config() == config

    def test_validate_order(self, base_executor):
        """Test la validation d'un ordre"""
        # Ordre valide
        valid_order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0
        }
        assert base_executor.validate_order(valid_order) is True
        
        # Ordre invalide
        invalid_order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT'
        }
        assert base_executor.validate_order(invalid_order) is False

# ============================================================
# MARKET EXECUTOR TESTS
# ============================================================

class TestMarketExecutor:
    """Tests pour l'exécuteur au marché"""

    @pytest.fixture
    def market_executor(self):
        """Fixture pour un exécuteur au marché"""
        config = {
            'timeout': 10,
            'retry_attempts': 3,
            'max_slippage': 0.005
        }
        return MarketExecutor(config)

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Test Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, market_executor):
        """Test l'initialisation"""
        assert market_executor is not None
        assert market_executor.get_type() == 'market'

    def test_execute_order(self, market_executor, mock_exchange):
        """Test l'exécution d'un ordre au marché"""
        market_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5
        }
        
        result = market_executor.execute_order(order)
        assert result is not None
        assert result['status'] == 'FILLED'
        assert result['filled_quantity'] == 0.5

    def test_execute_with_slippage(self, market_executor, mock_exchange):
        """Test l'exécution avec slippage"""
        market_executor.add_exchange(mock_exchange)
        
        # Modifier le prix pour simuler un slippage
        mock_exchange.set_price('BTC/USDT', 45000.0)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5
        }
        
        result = market_executor.execute_order(order)
        assert result is not None
        # Le prix exécuté devrait être proche du prix du marché
        assert abs(result['avg_price'] - 45000.0) < 100

    def test_execute_order_rejected(self, market_executor, mock_exchange):
        """Test l'exécution d'un ordre rejeté"""
        market_executor.add_exchange(mock_exchange)
        
        # Simuler un solde insuffisant
        mock_exchange.set_balance('USDT', 100.0)  # Pas assez pour 0.5 BTC à 45000
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5
        }
        
        result = market_executor.execute_order(order)
        assert result is not None
        assert result['status'] == 'REJECTED'

    @pytest.mark.asyncio
    async def test_async_execute(self, market_executor, mock_exchange):
        """Test l'exécution asynchrone"""
        market_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5
        }
        
        result = await market_executor.async_execute_order(order)
        assert result is not None
        assert result['status'] == 'FILLED'

# ============================================================
# LIMIT EXECUTOR TESTS
# ============================================================

class TestLimitExecutor:
    """Tests pour l'exécuteur à limite"""

    @pytest.fixture
    def limit_executor(self):
        """Fixture pour un exécuteur à limite"""
        config = {
            'timeout': 30,
            'retry_attempts': 3,
            'max_price_deviation': 0.02
        }
        return LimitExecutor(config)

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Test Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, limit_executor):
        """Test l'initialisation"""
        assert limit_executor is not None
        assert limit_executor.get_type() == 'limit'

    def test_execute_order(self, limit_executor, mock_exchange):
        """Test l'exécution d'un ordre à limite"""
        limit_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0
        }
        
        result = limit_executor.execute_order(order)
        assert result is not None
        assert result['status'] in ['NEW', 'PARTIALLY_FILLED', 'FILLED']

    def test_execute_with_price_deviation(self, limit_executor, mock_exchange):
        """Test l'exécution avec déviation de prix"""
        limit_executor.add_exchange(mock_exchange)
        
        # Définir le prix du marché
        mock_exchange.set_price('BTC/USDT', 46000.0)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0
        }
        
        result = limit_executor.execute_order(order)
        # L'ordre ne devrait pas être rempli car le prix est trop éloigné
        assert result['status'] == 'NEW'

    def test_cancel_order(self, limit_executor, mock_exchange):
        """Test l'annulation d'un ordre"""
        limit_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0
        }
        
        result = limit_executor.execute_order(order)
        assert result is not None
        
        # Annuler l'ordre
        cancel_result = limit_executor.cancel_order(result['id'])
        assert cancel_result is True

    @pytest.mark.asyncio
    async def test_async_execute(self, limit_executor, mock_exchange):
        """Test l'exécution asynchrone"""
        limit_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0
        }
        
        result = await limit_executor.async_execute_order(order)
        assert result is not None

# ============================================================
# SMART EXECUTOR TESTS
# ============================================================

class TestSmartExecutor:
    """Tests pour l'exécuteur intelligent"""

    @pytest.fixture
    def smart_executor(self):
        """Fixture pour un exécuteur intelligent"""
        config = {
            'timeout': 30,
            'retry_attempts': 3,
            'max_slippage': 0.005,
            'max_price_deviation': 0.02,
            'iceberg_size': 0.1,
            'twap_duration': 60
        }
        return SmartExecutor(config)

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Test Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, smart_executor):
        """Test l'initialisation"""
        assert smart_executor is not None
        assert smart_executor.get_type() == 'smart'

    def test_execute_market_order(self, smart_executor, mock_exchange):
        """Test l'exécution d'un ordre au marché intelligent"""
        smart_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5,
            'smart_strategy': 'iceberg'
        }
        
        result = smart_executor.execute_order(order)
        assert result is not None
        assert result['status'] == 'FILLED'

    def test_execute_limit_order(self, smart_executor, mock_exchange):
        """Test l'exécution d'un ordre à limite intelligent"""
        smart_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0,
            'smart_strategy': 'twap'
        }
        
        result = smart_executor.execute_order(order)
        assert result is not None

    def test_iceberg_execution(self, smart_executor, mock_exchange):
        """Test l'exécution iceberg"""
        smart_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 1.0,
            'price': 45000.0,
            'smart_strategy': 'iceberg',
            'iceberg_size': 0.1
        }
        
        result = smart_executor.execute_order(order)
        assert result is not None

    def test_twap_execution(self, smart_executor, mock_exchange):
        """Test l'exécution TWAP"""
        smart_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 1.0,
            'smart_strategy': 'twap',
            'twap_duration': 30,
            'twap_slices': 10
        }
        
        result = smart_executor.execute_order(order)
        assert result is not None

    @pytest.mark.asyncio
    async def test_async_execute(self, smart_executor, mock_exchange):
        """Test l'exécution asynchrone"""
        smart_executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5,
            'smart_strategy': 'iceberg'
        }
        
        result = await smart_executor.async_execute_order(order)
        assert result is not None

# ============================================================
# BATCH EXECUTOR TESTS
# ============================================================

class TestBatchExecutor:
    """Tests pour l'exécuteur par lots"""

    @pytest.fixture
    def batch_executor(self):
        """Fixture pour un exécuteur par lots"""
        config = {
            'max_batch_size': 10,
            'timeout': 30,
            'retry_attempts': 3
        }
        return BatchExecutor(config)

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Test Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, batch_executor):
        """Test l'initialisation"""
        assert batch_executor is not None
        assert batch_executor.get_type() == 'batch'

    def test_execute_batch(self, batch_executor, mock_exchange):
        """Test l'exécution d'un lot d'ordres"""
        batch_executor.add_exchange(mock_exchange)
        
        orders = [
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'type': 'MARKET',
                'quantity': 0.1
            },
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'type': 'LIMIT',
                'quantity': 0.2,
                'price': 45000.0
            },
            {
                'symbol': 'ETH/USDT',
                'side': 'SELL',
                'type': 'MARKET',
                'quantity': 1.0
            }
        ]
        
        results = batch_executor.execute_batch(orders)
        assert len(results) == 3
        assert all(result['status'] in ['FILLED', 'NEW'] for result in results)

    def test_batch_with_partial_fill(self, batch_executor, mock_exchange):
        """Test l'exécution d'un lot avec remplissage partiel"""
        batch_executor.add_exchange(mock_exchange)
        
        orders = [
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'type': 'LIMIT',
                'quantity': 1.0,
                'price': 45000.0
            },
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'type': 'MARKET',
                'quantity': 0.5
            }
        ]
        
        results = batch_executor.execute_batch(orders)
        assert len(results) == 2
        
        # Le premier ordre peut être partiellement rempli ou non
        # Le deuxième devrait être rempli
        for result in results:
            if result['type'] == 'MARKET':
                assert result['status'] == 'FILLED'

    def test_batch_with_errors(self, batch_executor, mock_exchange):
        """Test l'exécution d'un lot avec des erreurs"""
        batch_executor.add_exchange(mock_exchange)
        
        # Simuler un solde insuffisant
        mock_exchange.set_balance('USDT', 100.0)
        
        orders = [
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'type': 'MARKET',
                'quantity': 0.5
            },
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'type': 'LIMIT',
                'quantity': 0.1,
                'price': 45000.0
            }
        ]
        
        results = batch_executor.execute_batch(orders)
        assert len(results) == 2
        # Au moins un ordre devrait être rejeté
        assert any(result['status'] == 'REJECTED' for result in results)

    @pytest.mark.asyncio
    async def test_async_execute_batch(self, batch_executor, mock_exchange):
        """Test l'exécution asynchrone d'un lot"""
        batch_executor.add_exchange(mock_exchange)
        
        orders = [
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'type': 'MARKET',
                'quantity': 0.1
            },
            {
                'symbol': 'ETH/USDT',
                'side': 'SELL',
                'type': 'MARKET',
                'quantity': 1.0
            }
        ]
        
        results = await batch_executor.async_execute_batch(orders)
        assert len(results) == 2

# ============================================================
# EXECUTOR FACTORY TESTS
# ============================================================

class TestExecutorFactory:
    """Tests pour la fabrique d'exécuteurs"""

    def test_create_executor(self):
        """Test la création d'un exécuteur"""
        # Créer un exécuteur au marché
        executor = ExecutorFactory.create_executor('market')
        assert executor is not None
        assert executor.get_type() == 'market'
        
        # Créer un exécuteur à limite
        executor = ExecutorFactory.create_executor('limit')
        assert executor is not None
        assert executor.get_type() == 'limit'
        
        # Créer un exécuteur intelligent
        executor = ExecutorFactory.create_executor('smart')
        assert executor is not None
        assert executor.get_type() == 'smart'
        
        # Créer un exécuteur par lots
        executor = ExecutorFactory.create_executor('batch')
        assert executor is not None
        assert executor.get_type() == 'batch'

    def test_create_with_config(self):
        """Test la création avec configuration"""
        config = {'timeout': 30, 'retry_attempts': 5}
        executor = ExecutorFactory.create_executor('market', config)
        assert executor is not None
        assert executor.get_config()['timeout'] == 30

    def test_invalid_executor_type(self):
        """Test la création d'un type invalide"""
        with pytest.raises(ValueError):
            ExecutorFactory.create_executor('invalid_type')

    def test_register_executor(self):
        """Test l'enregistrement d'un exécuteur"""
        class CustomExecutor(BaseExecutor):
            def get_type(self):
                return 'custom'
            
            def execute_order(self, order):
                return {'status': 'FILLED'}
        
        ExecutorFactory.register_executor('custom', CustomExecutor)
        executor = ExecutorFactory.create_executor('custom')
        assert executor is not None
        assert executor.get_type() == 'custom'

    def test_get_available_executors(self):
        """Test la récupération des exécuteurs disponibles"""
        executors = ExecutorFactory.get_available_executors()
        assert 'market' in executors
        assert 'limit' in executors
        assert 'smart' in executors
        assert 'batch' in executors

# ============================================================
# EXECUTOR MANAGER TESTS
# ============================================================

class TestExecutorManager:
    """Tests pour le gestionnaire d'exécuteurs"""

    @pytest.fixture
    def executor_manager(self):
        """Fixture pour le gestionnaire d'exécuteurs"""
        return ExecutorManager()

    @pytest.fixture
    def mock_executor(self):
        """Fixture pour un exécuteur mocké"""
        executor = Mock()
        executor.get_type.return_value = 'market'
        executor.is_running.return_value = False
        return executor

    def test_initialization(self, executor_manager):
        """Test l'initialisation"""
        assert executor_manager is not None
        assert len(executor_manager.get_executors()) == 0

    def test_add_executor(self, executor_manager, mock_executor):
        """Test l'ajout d'un exécuteur"""
        executor_manager.add_executor(mock_executor)
        executors = executor_manager.get_executors()
        assert len(executors) == 1

    def test_remove_executor(self, executor_manager, mock_executor):
        """Test la suppression d'un exécuteur"""
        executor_manager.add_executor(mock_executor)
        executor_manager.remove_executor('market')
        executors = executor_manager.get_executors()
        assert len(executors) == 0

    def test_get_executor(self, executor_manager, mock_executor):
        """Test la récupération d'un exécuteur"""
        executor_manager.add_executor(mock_executor)
        executor = executor_manager.get_executor('market')
        assert executor is not None

    def test_start_all(self, executor_manager, mock_executor):
        """Test le démarrage de tous les exécuteurs"""
        executor_manager.add_executor(mock_executor)
        executor_manager.start_all()
        mock_executor.start.assert_called_once()

    def test_stop_all(self, executor_manager, mock_executor):
        """Test l'arrêt de tous les exécuteurs"""
        executor_manager.add_executor(mock_executor)
        executor_manager.stop_all()
        mock_executor.stop.assert_called_once()

    def test_execute_order(self, executor_manager, mock_executor):
        """Test l'exécution d'un ordre"""
        executor_manager.add_executor(mock_executor)
        mock_executor.execute_order.return_value = {'status': 'FILLED'}
        
        order = {'symbol': 'BTC/USDT', 'side': 'BUY', 'type': 'MARKET', 'quantity': 0.5}
        result = executor_manager.execute_order('market', order)
        
        assert result is not None
        mock_executor.execute_order.assert_called_once_with(order)

    def test_execute_order_invalid_executor(self, executor_manager):
        """Test l'exécution avec un exécuteur invalide"""
        order = {'symbol': 'BTC/USDT', 'side': 'BUY', 'type': 'MARKET', 'quantity': 0.5}
        
        with pytest.raises(ValueError):
            executor_manager.execute_order('invalid', order)

# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestExecutorIntegration:
    """Tests d'intégration des exécuteurs"""

    def test_full_execution_flow(self, mock_exchange):
        """Test le flux complet d'exécution"""
        # Créer les exécuteurs
        market_executor = MarketExecutor()
        limit_executor = LimitExecutor()
        smart_executor = SmartExecutor()
        
        # Ajouter l'exchange
        market_executor.add_exchange(mock_exchange)
        limit_executor.add_exchange(mock_exchange)
        smart_executor.add_exchange(mock_exchange)
        
        # Exécuter un ordre au marché
        market_order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5
        }
        market_result = market_executor.execute_order(market_order)
        assert market_result['status'] == 'FILLED'
        
        # Exécuter un ordre à limite
        limit_order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'LIMIT',
            'quantity': 0.5,
            'price': 45000.0
        }
        limit_result = limit_executor.execute_order(limit_order)
        assert limit_result is not None
        
        # Exécuter un ordre intelligent
        smart_order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5,
            'smart_strategy': 'iceberg'
        }
        smart_result = smart_executor.execute_order(smart_order)
        assert smart_result['status'] == 'FILLED'

    @pytest.mark.asyncio
    async def test_async_execution_flow(self, mock_exchange):
        """Test le flux d'exécution asynchrone"""
        executor = MarketExecutor()
        executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.5
        }
        
        result = await executor.async_execute_order(order)
        assert result['status'] == 'FILLED'

    def test_concurrent_execution(self, mock_exchange):
        """Test l'exécution concurrente"""
        executor = MarketExecutor()
        executor.add_exchange(mock_exchange)
        
        # Exécuter plusieurs ordres en parallèle
        orders = [
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY' if i % 2 == 0 else 'SELL',
                'type': 'MARKET',
                'quantity': 0.1 + i * 0.05
            }
            for i in range(10)
        ]
        
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(executor.execute_order, orders))
        
        assert len(results) == 10
        assert all(r['status'] == 'FILLED' for r in results)

# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestExecutorPerformance:
    """Tests de performance des exécuteurs"""

    def test_execution_performance(self, mock_exchange):
        """Test la performance d'exécution"""
        import time
        
        executor = MarketExecutor()
        executor.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.1
        }
        
        # Mesurer le temps d'exécution
        start_time = time.time()
        
        for _ in range(50):
            result = executor.execute_order(order)
            assert result['status'] == 'FILLED'
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 50 * 1000  # ms
        
        # Moins de 5ms par exécution en moyenne
        assert avg_time < 5

    def test_batch_execution_performance(self, mock_exchange):
        """Test la performance d'exécution par lots"""
        import time
        
        executor = BatchExecutor()
        executor.add_exchange(mock_exchange)
        
        orders = [
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY' if i % 2 == 0 else 'SELL',
                'type': 'MARKET',
                'quantity': 0.1
            }
            for i in range(20)
        ]
        
        # Mesurer le temps d'exécution
        start_time = time.time()
        
        for _ in range(10):
            results = executor.execute_batch(orders)
            assert len(results) == 20
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 10 * 1000  # ms
        
        # Moins de 50ms par lot en moyenne
        assert avg_time < 50

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

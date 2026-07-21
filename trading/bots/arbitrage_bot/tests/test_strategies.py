"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Strategies Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests des stratégies d'arbitrage pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Import du module à tester
from trading.bots.arbitrage_bot.strategies.base_strategy import BaseStrategy
from trading.bots.arbitrage_bot.strategies.cross_exchange_strategy import CrossExchangeStrategy
from trading.bots.arbitrage_bot.strategies.triangular_strategy import TriangularStrategy
from trading.bots.arbitrage_bot.strategies.statistical_strategy import StatisticalStrategy
from trading.bots.arbitrage_bot.strategies.flash_loan_strategy import FlashLoanStrategy
from trading.bots.arbitrage_bot.strategies.cross_chain_strategy import CrossChainStrategy
from trading.bots.arbitrage_bot.strategies.strategy_factory import StrategyFactory
from trading.bots.arbitrage_bot.strategies.strategy_manager import StrategyManager

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    test_data,
    test_orders,
    test_trades,
    test_tickers,
    test_order_books,
    test_arbitrage_opportunities,
    test_triangular_opportunities
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
# BASE STRATEGY TESTS
# ============================================================

class TestBaseStrategy:
    """Tests pour la stratégie de base"""

    @pytest.fixture
    def base_strategy(self):
        """Fixture pour une stratégie de base"""
        return BaseStrategy()

    def test_initialization(self, base_strategy):
        """Test l'initialisation"""
        assert base_strategy is not None
        assert base_strategy.is_enabled() is True
        assert base_strategy.get_name() == "Base Strategy"

    def test_enable_disable(self, base_strategy):
        """Test l'activation/désactivation"""
        base_strategy.enable()
        assert base_strategy.is_enabled() is True
        
        base_strategy.disable()
        assert base_strategy.is_enabled() is False

    def test_set_parameters(self, base_strategy):
        """Test la définition des paramètres"""
        params = {
            'min_profit': 0.001,
            'max_spread': 0.10,
            'max_position': 1000
        }
        base_strategy.set_parameters(params)
        assert base_strategy.get_parameters() == params

    def test_validate_parameters(self, base_strategy):
        """Test la validation des paramètres"""
        params = {
            'min_profit': 0.001,
            'max_spread': 0.10,
            'max_position': 1000
        }
        is_valid = base_strategy.validate_parameters(params)
        assert is_valid is True

# ============================================================
# CROSS EXCHANGE STRATEGY TESTS
# ============================================================

class TestCrossExchangeStrategy:
    """Tests pour la stratégie cross-exchange"""

    @pytest.fixture
    def cross_exchange_strategy(self):
        """Fixture pour la stratégie cross-exchange"""
        params = {
            'min_profit': 0.001,
            'max_spread': 0.10,
            'min_volume': 10,
            'max_position': 1000,
            'min_time_between_trades': 10,
            'max_trades_per_minute': 5
        }
        return CrossExchangeStrategy(params)

    @pytest.fixture
    def mock_exchanges(self):
        """Fixture pour des mock exchanges"""
        exchanges = []
        for i in range(3):
            exchange = MockExchange(f"Exchange_{i+1}")
            exchange.start_market()
            exchanges.append(exchange)
        yield exchanges
        for exchange in exchanges:
            exchange.stop_market()

    def test_initialization(self, cross_exchange_strategy):
        """Test l'initialisation"""
        assert cross_exchange_strategy is not None
        assert cross_exchange_strategy.get_type() == 'cross_exchange'
        assert cross_exchange_strategy.get_name() == 'Cross Exchange Arbitrage'

    def test_add_exchange(self, cross_exchange_strategy, mock_exchanges):
        """Test l'ajout d'un exchange"""
        for exchange in mock_exchanges:
            cross_exchange_strategy.add_exchange(exchange)
        
        exchanges = cross_exchange_strategy.get_exchanges()
        assert len(exchanges) == len(mock_exchanges)

    def test_scan_opportunities(self, cross_exchange_strategy, mock_exchanges):
        """Test le scan des opportunités"""
        for exchange in mock_exchanges:
            cross_exchange_strategy.add_exchange(exchange)
        
        opportunities = cross_exchange_strategy.scan_opportunities()
        assert opportunities is not None
        assert len(opportunities) > 0
        
        for opp in opportunities:
            assert 'pair' in opp
            assert 'exchange_a' in opp
            assert 'exchange_b' in opp
            assert 'price_a' in opp
            assert 'price_b' in opp
            assert 'spread' in opp
            assert 'profit' in opp
            assert opp['profit'] > 0

    def test_calculate_spread(self, cross_exchange_strategy):
        """Test le calcul du spread"""
        spread = cross_exchange_strategy.calculate_spread(100.0, 101.0)
        assert spread == 1.0
        
        spread = cross_exchange_strategy.calculate_spread(100.0, 99.0)
        assert spread == -1.0

    def test_calculate_profit(self, cross_exchange_strategy):
        """Test le calcul du profit"""
        profit = cross_exchange_strategy.calculate_profit(100.0, 101.0, 1.0)
        assert profit > 0
        
        profit = cross_exchange_strategy.calculate_profit(100.0, 99.0, 1.0)
        assert profit < 0

    def test_validate_opportunity(self, cross_exchange_strategy):
        """Test la validation d'une opportunité"""
        opportunity = {
            'pair': 'BTC/USDT',
            'exchange_a': 'Exchange 1',
            'exchange_b': 'Exchange 2',
            'price_a': 100.0,
            'price_b': 101.0,
            'spread': 1.0,
            'profit': 0.95,
            'profit_percent': 0.0095,
            'volume': 100
        }
        
        is_valid = cross_exchange_strategy.validate_opportunity(opportunity)
        assert is_valid is True

    def test_execute_opportunity(self, cross_exchange_strategy, mock_exchanges):
        """Test l'exécution d'une opportunité"""
        for exchange in mock_exchanges:
            cross_exchange_strategy.add_exchange(exchange)
        
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
        
        result = cross_exchange_strategy.execute_opportunity(opportunity)
        assert result is True

    def test_get_statistics(self, cross_exchange_strategy, mock_exchanges):
        """Test la récupération des statistiques"""
        for exchange in mock_exchanges:
            cross_exchange_strategy.add_exchange(exchange)
        
        # Scannez quelques opportunités
        for _ in range(3):
            cross_exchange_strategy.scan_opportunities()
        
        stats = cross_exchange_strategy.get_statistics()
        assert stats is not None
        assert 'total_opportunities' in stats
        assert 'total_trades' in stats
        assert 'total_profit' in stats
        assert 'win_rate' in stats

# ============================================================
# TRIANGULAR STRATEGY TESTS
# ============================================================

class TestTriangularStrategy:
    """Tests pour la stratégie triangulaire"""

    @pytest.fixture
    def triangular_strategy(self):
        """Fixture pour la stratégie triangulaire"""
        params = {
            'min_profit': 0.001,
            'max_position': 1000,
            'cycles': [
                {
                    'name': 'BTC-ETH-USDT',
                    'pairs': ['BTC/USDT', 'ETH/BTC', 'ETH/USDT']
                },
                {
                    'name': 'SOL-BTC-USDT',
                    'pairs': ['SOL/USDT', 'BTC/SOL', 'BTC/USDT']
                }
            ]
        }
        return TriangularStrategy(params)

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Test Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, triangular_strategy):
        """Test l'initialisation"""
        assert triangular_strategy is not None
        assert triangular_strategy.get_type() == 'triangular'
        assert len(triangular_strategy.get_cycles()) == 2

    def test_add_cycle(self, triangular_strategy):
        """Test l'ajout d'un cycle"""
        cycle = {
            'name': 'ADA-BTC-USDT',
            'pairs': ['ADA/USDT', 'BTC/ADA', 'BTC/USDT']
        }
        triangular_strategy.add_cycle(cycle)
        cycles = triangular_strategy.get_cycles()
        assert len(cycles) == 3

    def test_scan_opportunities(self, triangular_strategy, mock_exchange):
        """Test le scan des opportunités"""
        triangular_strategy.add_exchange(mock_exchange)
        
        opportunities = triangular_strategy.scan_opportunities()
        assert opportunities is not None

    def test_calculate_triangular_profit(self, triangular_strategy):
        """Test le calcul du profit triangulaire"""
        prices = {
            'BTC/USDT': 45000.0,
            'ETH/BTC': 0.0667,
            'ETH/USDT': 3000.0
        }
        
        profit, rate = triangular_strategy.calculate_triangular_profit(
            prices,
            ['BTC/USDT', 'ETH/BTC', 'ETH/USDT']
        )
        
        assert profit is not None

    def test_validate_opportunity(self, triangular_strategy):
        """Test la validation d'une opportunité"""
        opportunity = {
            'cycle': 'BTC-ETH-USDT',
            'pairs': ['BTC/USDT', 'ETH/BTC', 'ETH/USDT'],
            'profit': 0.008,
            'profit_percent': 0.8,
            'exchange': 'Test Exchange'
        }
        
        is_valid = triangular_strategy.validate_opportunity(opportunity)
        assert is_valid is True

    def test_execute_opportunity(self, triangular_strategy, mock_exchange):
        """Test l'exécution d'une opportunité"""
        triangular_strategy.add_exchange(mock_exchange)
        
        opportunity = {
            'cycle': 'BTC-ETH-USDT',
            'pairs': ['BTC/USDT', 'ETH/BTC', 'ETH/USDT'],
            'profit': 0.008,
            'profit_percent': 0.8,
            'exchange': 'Test Exchange',
            'quantities': {
                'BTC/USDT': 0.5,
                'ETH/BTC': 0.033,
                'ETH/USDT': 1.5
            }
        }
        
        result = triangular_strategy.execute_opportunity(opportunity)
        assert result is True

# ============================================================
# STATISTICAL STRATEGY TESTS
# ============================================================

class TestStatisticalStrategy:
    """Tests pour la stratégie statistique"""

    @pytest.fixture
    def statistical_strategy(self):
        """Fixture pour la stratégie statistique"""
        params = {
            'min_profit': 0.001,
            'lookback_period': 50,
            'cointegration_confidence': 0.95,
            'z_score_threshold': 2.0,
            'half_life': 20,
            'max_position': 1000
        }
        return StatisticalStrategy(params)

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Test Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, statistical_strategy):
        """Test l'initialisation"""
        assert statistical_strategy is not None
        assert statistical_strategy.get_type() == 'statistical'

    def test_add_pair(self, statistical_strategy):
        """Test l'ajout d'une paire"""
        pair = {
            'pair1': 'BTC/USDT',
            'pair2': 'ETH/USDT',
            'hedge_ratio': 0.5,
            'min_profit': 0.001,
            'max_position': 1000
        }
        statistical_strategy.add_pair(pair)
        pairs = statistical_strategy.get_pairs()
        assert len(pairs) == 1

    def test_calculate_cointegration(self, statistical_strategy):
        """Test le calcul de la cointégration"""
        # Créer deux séries corrélées
        np.random.seed(42)
        x = np.cumsum(np.random.randn(100))
        y = 0.8 * x + 0.2 * np.cumsum(np.random.randn(100))
        
        cointegration = statistical_strategy.calculate_cointegration(x, y)
        assert cointegration is not None
        assert 'cointegrated' in cointegration
        assert 'confidence' in cointegration
        assert 'hedge_ratio' in cointegration

    def test_calculate_z_score(self, statistical_strategy):
        """Test le calcul du z-score"""
        # Créer des données avec une moyenne connue
        data = np.random.normal(0, 1, 100)
        z_scores = statistical_strategy.calculate_z_score(data)
        
        assert len(z_scores) == len(data)
        assert abs(np.mean(z_scores)) < 0.5

    def test_scan_opportunities(self, statistical_strategy, mock_exchange):
        """Test le scan des opportunités"""
        statistical_strategy.add_exchange(mock_exchange)
        statistical_strategy.add_pair({
            'pair1': 'BTC/USDT',
            'pair2': 'ETH/USDT',
            'hedge_ratio': 0.5,
            'min_profit': 0.001,
            'max_position': 1000
        })
        
        opportunities = statistical_strategy.scan_opportunities()
        assert opportunities is not None

    def test_execute_opportunity(self, statistical_strategy, mock_exchange):
        """Test l'exécution d'une opportunité"""
        statistical_strategy.add_exchange(mock_exchange)
        
        opportunity = {
            'pair1': 'BTC/USDT',
            'pair2': 'ETH/USDT',
            'hedge_ratio': 0.5,
            'z_score': 2.5,
            'profit': 0.01,
            'profit_percent': 1.0,
            'exchange': 'Test Exchange'
        }
        
        result = statistical_strategy.execute_opportunity(opportunity)
        assert result is True

# ============================================================
# FLASH LOAN STRATEGY TESTS
# ============================================================

class TestFlashLoanStrategy:
    """Tests pour la stratégie de flash loan"""

    @pytest.fixture
    def flash_loan_strategy(self):
        """Fixture pour la stratégie de flash loan"""
        params = {
            'min_profit': 0.02,
            'max_loan_size': 1000000,
            'gas_limit': 1000000,
            'max_gas_price': 200,
            'platforms': ['aave', 'dydx', 'uniswap']
        }
        return FlashLoanStrategy(params)

    def test_initialization(self, flash_loan_strategy):
        """Test l'initialisation"""
        assert flash_loan_strategy is not None
        assert flash_loan_strategy.get_type() == 'flash_loan'

    def test_add_platform(self, flash_loan_strategy):
        """Test l'ajout d'une plateforme"""
        flash_loan_strategy.add_platform('compound')
        platforms = flash_loan_strategy.get_platforms()
        assert 'compound' in platforms

    def test_calculate_gas_cost(self, flash_loan_strategy):
        """Test le calcul du coût en gas"""
        gas_cost = flash_loan_strategy.calculate_gas_cost(100000, 100)
        assert gas_cost > 0
        
        gas_cost = flash_loan_strategy.calculate_gas_cost(500000, 200)
        assert gas_cost > 0

    def test_calculate_profit_after_gas(self, flash_loan_strategy):
        """Test le calcul du profit après gas"""
        profit = flash_loan_strategy.calculate_profit_after_gas(3000, 500)
        assert profit == 2500
        
        profit = flash_loan_strategy.calculate_profit_after_gas(1000, 1500)
        assert profit < 0

    def test_validate_opportunity(self, flash_loan_strategy):
        """Test la validation d'une opportunité"""
        opportunity = {
            'pair': 'WETH/USDT',
            'amount': 100000,
            'profit': 3000,
            'gas_cost': 500,
            'platform': 'aave'
        }
        
        is_valid = flash_loan_strategy.validate_opportunity(opportunity)
        assert is_valid is True

# ============================================================
# CROSS CHAIN STRATEGY TESTS
# ============================================================

class TestCrossChainStrategy:
    """Tests pour la stratégie cross-chain"""

    @pytest.fixture
    def cross_chain_strategy(self):
        """Fixture pour la stratégie cross-chain"""
        params = {
            'min_profit': 0.015,
            'max_position': 100000,
            'bridge_timeout': 120,
            'bridges': ['anycall', 'wormhole', 'multichain']
        }
        return CrossChainStrategy(params)

    def test_initialization(self, cross_chain_strategy):
        """Test l'initialisation"""
        assert cross_chain_strategy is not None
        assert cross_chain_strategy.get_type() == 'cross_chain'

    def test_add_bridge(self, cross_chain_strategy):
        """Test l'ajout d'un bridge"""
        cross_chain_strategy.add_bridge('axelar')
        bridges = cross_chain_strategy.get_bridges()
        assert 'axelar' in bridges

    def test_calculate_bridge_fee(self, cross_chain_strategy):
        """Test le calcul des frais de bridge"""
        fee = cross_chain_strategy.calculate_bridge_fee(10000, 'wormhole')
        assert fee > 0
        
        fee = cross_chain_strategy.calculate_bridge_fee(50000, 'anycall')
        assert fee > 0

    def test_validate_transfer(self, cross_chain_strategy):
        """Test la validation d'un transfert"""
        transfer = {
            'from_chain': 'ethereum',
            'to_chain': 'polygon',
            'amount': 10000,
            'bridge': 'wormhole'
        }
        
        is_valid = cross_chain_strategy.validate_transfer(transfer)
        assert is_valid is True

# ============================================================
# STRATEGY FACTORY TESTS
# ============================================================

class TestStrategyFactory:
    """Tests pour la fabrique de stratégies"""

    def test_create_strategy(self):
        """Test la création d'une stratégie"""
        # Créer une stratégie cross-exchange
        strategy = StrategyFactory.create_strategy('cross_exchange')
        assert strategy is not None
        assert strategy.get_type() == 'cross_exchange'
        
        # Créer une stratégie triangulaire
        strategy = StrategyFactory.create_strategy('triangular')
        assert strategy is not None
        assert strategy.get_type() == 'triangular'
        
        # Créer une stratégie statistique
        strategy = StrategyFactory.create_strategy('statistical')
        assert strategy is not None
        assert strategy.get_type() == 'statistical'
        
        # Créer une stratégie flash loan
        strategy = StrategyFactory.create_strategy('flash_loan')
        assert strategy is not None
        assert strategy.get_type() == 'flash_loan'
        
        # Créer une stratégie cross-chain
        strategy = StrategyFactory.create_strategy('cross_chain')
        assert strategy is not None
        assert strategy.get_type() == 'cross_chain'

    def test_create_with_params(self):
        """Test la création avec paramètres"""
        params = {'min_profit': 0.001, 'max_spread': 0.10}
        strategy = StrategyFactory.create_strategy('cross_exchange', params)
        assert strategy is not None
        assert strategy.get_parameters()['min_profit'] == 0.001

    def test_invalid_strategy_type(self):
        """Test la création d'un type invalide"""
        with pytest.raises(ValueError):
            StrategyFactory.create_strategy('invalid_type')

    def test_register_strategy(self):
        """Test l'enregistrement d'une stratégie"""
        class CustomStrategy(BaseStrategy):
            def get_type(self):
                return 'custom'
            
            def scan_opportunities(self):
                return []
        
        StrategyFactory.register_strategy('custom', CustomStrategy)
        strategy = StrategyFactory.create_strategy('custom')
        assert strategy is not None
        assert strategy.get_type() == 'custom'

    def test_get_available_strategies(self):
        """Test la récupération des stratégies disponibles"""
        strategies = StrategyFactory.get_available_strategies()
        assert 'cross_exchange' in strategies
        assert 'triangular' in strategies
        assert 'statistical' in strategies
        assert 'flash_loan' in strategies
        assert 'cross_chain' in strategies

# ============================================================
# STRATEGY MANAGER TESTS
# ============================================================

class TestStrategyManager:
    """Tests pour le gestionnaire de stratégies"""

    @pytest.fixture
    def strategy_manager(self):
        """Fixture pour le gestionnaire de stratégies"""
        return StrategyManager()

    def test_initialization(self, strategy_manager):
        """Test l'initialisation"""
        assert strategy_manager is not None
        assert len(strategy_manager.get_strategies()) == 0

    def test_add_strategy(self, strategy_manager):
        """Test l'ajout d'une stratégie"""
        strategy = StrategyFactory.create_strategy('cross_exchange')
        strategy_manager.add_strategy(strategy)
        strategies = strategy_manager.get_strategies()
        assert len(strategies) == 1

    def test_remove_strategy(self, strategy_manager):
        """Test la suppression d'une stratégie"""
        strategy = StrategyFactory.create_strategy('cross_exchange')
        strategy_manager.add_strategy(strategy)
        strategy_manager.remove_strategy('cross_exchange')
        strategies = strategy_manager.get_strategies()
        assert len(strategies) == 0

    def test_get_strategy(self, strategy_manager):
        """Test la récupération d'une stratégie"""
        strategy = StrategyFactory.create_strategy('cross_exchange')
        strategy_manager.add_strategy(strategy)
        retrieved = strategy_manager.get_strategy('cross_exchange')
        assert retrieved is not None
        assert retrieved.get_type() == 'cross_exchange'

    def test_enable_disable_strategy(self, strategy_manager):
        """Test l'activation/désactivation d'une stratégie"""
        strategy = StrategyFactory.create_strategy('cross_exchange')
        strategy_manager.add_strategy(strategy)
        
        strategy_manager.enable_strategy('cross_exchange')
        assert strategy_manager.is_enabled('cross_exchange') is True
        
        strategy_manager.disable_strategy('cross_exchange')
        assert strategy_manager.is_enabled('cross_exchange') is False

    def test_get_active_strategies(self, strategy_manager):
        """Test la récupération des stratégies actives"""
        strategies = [
            StrategyFactory.create_strategy('cross_exchange'),
            StrategyFactory.create_strategy('triangular'),
            StrategyFactory.create_strategy('statistical')
        ]
        
        for strategy in strategies:
            strategy_manager.add_strategy(strategy)
        
        strategy_manager.enable_strategy('cross_exchange')
        strategy_manager.enable_strategy('triangular')
        strategy_manager.disable_strategy('statistical')
        
        active = strategy_manager.get_active_strategies()
        assert len(active) == 2
        assert active[0].get_type() == 'cross_exchange'
        assert active[1].get_type() == 'triangular'

# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestStrategyIntegration:
    """Tests d'intégration des stratégies"""

    def test_multiple_strategies_execution(self, mock_exchanges):
        """Test l'exécution de multiples stratégies"""
        # Créer les stratégies
        strategies = {
            'cross_exchange': StrategyFactory.create_strategy('cross_exchange'),
            'triangular': StrategyFactory.create_strategy('triangular'),
            'statistical': StrategyFactory.create_strategy('statistical')
        }
        
        # Ajouter les exchanges
        for exchange in mock_exchanges:
            for strategy in strategies.values():
                strategy.add_exchange(exchange)
        
        # Configurer les paramètres
        strategies['cross_exchange'].set_parameters({
            'min_profit': 0.001,
            'max_spread': 0.10,
            'min_volume': 10
        })
        
        strategies['triangular'].set_parameters({
            'min_profit': 0.001,
            'cycles': [
                {
                    'name': 'BTC-ETH-USDT',
                    'pairs': ['BTC/USDT', 'ETH/BTC', 'ETH/USDT']
                }
            ]
        })
        
        strategies['statistical'].set_parameters({
            'min_profit': 0.001,
            'lookback_period': 50,
            'z_score_threshold': 2.0
        })
        
        # Exécuter les stratégies
        all_opportunities = []
        for name, strategy in strategies.items():
            opportunities = strategy.scan_opportunities()
            all_opportunities.extend(opportunities)
            logger.info(f"{name}: {len(opportunities)} opportunities")
        
        # Vérifier qu'au moins une stratégie trouve des opportunités
        assert len(all_opportunities) > 0

    def test_strategy_execution_flow(self, mock_exchanges):
        """Test le flux d'exécution des stratégies"""
        # Créer une stratégie
        strategy = StrategyFactory.create_strategy('cross_exchange')
        
        # Ajouter les exchanges
        for exchange in mock_exchanges:
            strategy.add_exchange(exchange)
        
        # Configurer les paramètres
        strategy.set_parameters({
            'min_profit': 0.001,
            'max_spread': 0.10,
            'min_volume': 10,
            'max_position': 1000
        })
        
        # Scanner les opportunités
        opportunities = strategy.scan_opportunities()
        assert len(opportunities) > 0
        
        # Valider les opportunités
        validated = []
        for opp in opportunities:
            if strategy.validate_opportunity(opp):
                validated.append(opp)
        
        assert len(validated) > 0
        
        # Exécuter les opportunités
        executed = 0
        for opp in validated[:3]:  # Limiter pour les tests
            result = strategy.execute_opportunity(opp)
            if result:
                executed += 1
        
        assert executed > 0

# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestStrategyPerformance:
    """Tests de performance des stratégies"""

    def test_scan_performance(self, cross_exchange_strategy, mock_exchanges):
        """Test la performance de scan"""
        import time
        
        for exchange in mock_exchanges:
            cross_exchange_strategy.add_exchange(exchange)
        
        # Mesurer le temps de scan
        start_time = time.time()
        for _ in range(100):
            opportunities = cross_exchange_strategy.scan_opportunities()
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 100 * 1000  # ms
        logger.info(f"Average scan time: {avg_time:.2f}ms")
        
        assert avg_time < 50  # Moins de 50ms

    def test_validation_performance(self, cross_exchange_strategy):
        """Test la performance de validation"""
        import time
        
        opportunity = {
            'pair': 'BTC/USDT',
            'exchange_a': 'Exchange 1',
            'exchange_b': 'Exchange 2',
            'price_a': 100.0,
            'price_b': 101.0,
            'spread': 1.0,
            'profit': 0.95,
            'profit_percent': 0.0095,
            'volume': 100
        }
        
        # Mesurer le temps de validation
        start_time = time.time()
        for _ in range(1000):
            is_valid = cross_exchange_strategy.validate_opportunity(opportunity)
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 1000 * 1000  # ms
        logger.info(f"Average validation time: {avg_time:.3f}ms")
        
        assert avg_time < 1  # Moins de 1ms

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

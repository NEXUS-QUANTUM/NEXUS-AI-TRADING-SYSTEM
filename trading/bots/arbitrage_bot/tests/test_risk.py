"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Risk Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests de gestion des risques pour le bot d'arbitrage
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
from trading.bots.arbitrage_bot.risk.risk_manager import RiskManager
from trading.bots.arbitrage_bot.risk.position_sizer import PositionSizer
from trading.bots.arbitrage_bot.risk.stop_loss_manager import StopLossManager
from trading.bots.arbitrage_bot.risk.take_profit_manager import TakeProfitManager
from trading.bots.arbitrage_bot.risk.circuit_breaker import CircuitBreaker
from trading.bots.arbitrage_bot.risk.drawdown_controller import DrawdownController
from trading.bots.arbitrage_bot.risk.var_calculator import VaRCalculator
from trading.bots.arbitrage_bot.risk.risk_metrics import RiskMetrics
from trading.bots.arbitrage_bot.risk.risk_reporter import RiskReporter
from trading.bots.arbitrage_bot.risk.risk_config import RiskConfig

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    test_data,
    test_orders,
    test_trades,
    test_balances,
    test_performance_metrics
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
# RISK MANAGER TESTS
# ============================================================

class TestRiskManager:
    """Tests pour le gestionnaire de risques"""

    @pytest.fixture
    def risk_manager(self):
        """Fixture pour le gestionnaire de risques"""
        config = {
            'max_drawdown': 0.15,
            'daily_loss_limit': 0.05,
            'weekly_loss_limit': 0.10,
            'max_positions': 10,
            'max_positions_per_pair': 3,
            'max_positions_per_exchange': 5
        }
        return RiskManager(config)

    def test_initialization(self, risk_manager):
        """Test l'initialisation"""
        assert risk_manager is not None
        assert risk_manager.get_risk_level() == 'medium'
        assert len(risk_manager.get_positions()) == 0

    def test_set_risk_level(self, risk_manager):
        """Test la définition du niveau de risque"""
        risk_manager.set_risk_level('low')
        assert risk_manager.get_risk_level() == 'low'
        
        risk_manager.set_risk_level('high')
        assert risk_manager.get_risk_level() == 'high'
        
        risk_manager.set_risk_level('aggressive')
        assert risk_manager.get_risk_level() == 'aggressive'

    def test_add_position(self, risk_manager):
        """Test l'ajout d'une position"""
        position = {
            'id': 'pos_001',
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 46000.0,
            'quantity': 0.5,
            'side': 'BUY'
        }
        
        risk_manager.add_position(position)
        positions = risk_manager.get_positions()
        assert len(positions) == 1
        assert positions[0]['id'] == 'pos_001'

    def test_remove_position(self, risk_manager):
        """Test la suppression d'une position"""
        position = {
            'id': 'pos_001',
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 46000.0,
            'quantity': 0.5
        }
        
        risk_manager.add_position(position)
        risk_manager.remove_position('pos_001')
        positions = risk_manager.get_positions()
        assert len(positions) == 0

    def test_calculate_drawdown(self, risk_manager):
        """Test le calcul du drawdown"""
        # Simuler un historique de PnL
        pnl_history = [100, 200, 300, 250, 200, 150, 175, 225]
        drawdown = risk_manager.calculate_drawdown(pnl_history)
        
        assert drawdown > 0
        assert drawdown <= 1.0

    def test_check_drawdown_limit(self, risk_manager):
        """Test la vérification des limites de drawdown"""
        # Simuler un historique de PnL avec un drawdown important
        pnl_history = [100, 200, 300, 250, 200, 150, 100, 50]
        
        # Vérifier avec un seuil bas
        is_exceeded = risk_manager.check_drawdown_limit(pnl_history, 0.20)
        assert is_exceeded is True
        
        # Vérifier avec un seuil haut
        is_exceeded = risk_manager.check_drawdown_limit(pnl_history, 0.50)
        assert is_exceeded is False

    def test_validate_trade(self, risk_manager):
        """Test la validation d'un trade"""
        # Trade valide
        valid_trade = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'quantity': 0.5,
            'price': 45000.0,
            'risk': 0.01
        }
        assert risk_manager.validate_trade(valid_trade) is True
        
        # Trade invalide (trop risqué)
        invalid_trade = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'quantity': 5.0,
            'price': 45000.0,
            'risk': 0.05
        }
        assert risk_manager.validate_trade(invalid_trade) is False

    def test_calculate_position_size(self, risk_manager):
        """Test le calcul de la taille de position"""
        # Test avec différents niveaux de risque
        risk_manager.set_risk_level('low')
        size = risk_manager.calculate_position_size(10000.0, 0.01)
        assert size <= 100.0
        
        risk_manager.set_risk_level('high')
        size = risk_manager.calculate_position_size(10000.0, 0.01)
        assert size >= 200.0

    def test_get_portfolio_risk(self, risk_manager):
        """Test le calcul du risque du portefeuille"""
        # Ajouter quelques positions
        for i in range(3):
            position = {
                'id': f'pos_{i}',
                'symbol': 'BTC/USDT',
                'entry_price': 45000.0 + i * 100,
                'current_price': 45000.0 + i * 150,
                'quantity': 0.5,
                'pnl': i * 50
            }
            risk_manager.add_position(position)
        
        portfolio_risk = risk_manager.get_portfolio_risk()
        assert portfolio_risk is not None
        assert 'total_pnl' in portfolio_risk
        assert 'total_risk' in portfolio_risk
        assert 'positions_count' in portfolio_risk

    def test_monitor_positions(self, risk_manager):
        """Test le monitoring des positions"""
        # Ajouter des positions
        for i in range(3):
            position = {
                'id': f'pos_{i}',
                'symbol': 'BTC/USDT',
                'entry_price': 45000.0,
                'current_price': 45000.0 + i * 100,
                'quantity': 0.5,
                'pnl': i * 50
            }
            risk_manager.add_position(position)
        
        # Monitorer les positions
        alerts = risk_manager.monitor_positions()
        assert alerts is not None

# ============================================================
# POSITION SIZER TESTS
# ============================================================

class TestPositionSizer:
    """Tests pour le calculateur de taille de position"""

    @pytest.fixture
    def position_sizer(self):
        """Fixture pour le calculateur de taille de position"""
        config = {
            'strategy': 'adaptive',
            'fixed_size': 1000,
            'max_size': 50000,
            'min_size': 100,
            'kelly_fraction': 0.25,
            'volatility_factor': 0.5,
            'adaptive_factor': 0.3
        }
        return PositionSizer(config)

    def test_initialization(self, position_sizer):
        """Test l'initialisation"""
        assert position_sizer is not None
        assert position_sizer.get_strategy() == 'adaptive'

    def test_calculate_fixed_size(self, position_sizer):
        """Test le calcul de taille fixe"""
        position_sizer.set_strategy('fixed')
        size = position_sizer.calculate_size(10000.0, 0.01)
        assert size == 1000.0

    def test_calculate_kelly_size(self, position_sizer):
        """Test le calcul de taille Kelly"""
        position_sizer.set_strategy('kelly')
        # Simuler un historique de trades
        trades = [{'pnl': 100}, {'pnl': -50}, {'pnl': 150}, {'pnl': -30}]
        size = position_sizer.calculate_kelly_size(10000.0, trades)
        assert size >= 0

    def test_calculate_volatility_size(self, position_sizer):
        """Test le calcul de taille basé sur la volatilité"""
        position_sizer.set_strategy('volatility')
        size = position_sizer.calculate_volatility_size(10000.0, 0.02)
        assert size > 0

    def test_calculate_adaptive_size(self, position_sizer):
        """Test le calcul de taille adaptative"""
        position_sizer.set_strategy('adaptive')
        size = position_sizer.calculate_adaptive_size(10000.0, 0.01, 0.02)
        assert size > 0

    def test_apply_limits(self, position_sizer):
        """Test l'application des limites"""
        size = position_sizer.apply_limits(100000.0)
        assert size <= 50000.0
        
        size = position_sizer.apply_limits(10.0)
        assert size >= 100.0

# ============================================================
# STOP LOSS MANAGER TESTS
# ============================================================

class TestStopLossManager:
    """Tests pour le gestionnaire de stop loss"""

    @pytest.fixture
    def stop_loss_manager(self):
        """Fixture pour le gestionnaire de stop loss"""
        config = {
            'enabled': True,
            'type': 'trailing',
            'percentage': 0.02,
            'trailing_offset': 0.01,
            'min_trailing': 0.005,
            'max_trailing': 0.05,
            'dynamic_factor': 0.5
        }
        return StopLossManager(config)

    def test_initialization(self, stop_loss_manager):
        """Test l'initialisation"""
        assert stop_loss_manager is not None
        assert stop_loss_manager.is_enabled() is True

    def test_calculate_stop_loss(self, stop_loss_manager):
        """Test le calcul du stop loss"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 45500.0,
            'quantity': 0.5
        }
        
        stop_price = stop_loss_manager.calculate_stop_loss(position)
        assert stop_price < position['entry_price']

    def test_check_stop_loss(self, stop_loss_manager):
        """Test la vérification du stop loss"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 44000.0,
            'quantity': 0.5
        }
        
        should_stop = stop_loss_manager.check_stop_loss(position)
        assert should_stop is True
        
        # Position avec prix supérieur
        position['current_price'] = 46000.0
        should_stop = stop_loss_manager.check_stop_loss(position)
        assert should_stop is False

    def test_trailing_stop(self, stop_loss_manager):
        """Test le trailing stop"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 46000.0,
            'quantity': 0.5,
            'highest_price': 46000.0
        }
        
        stop_price = stop_loss_manager.calculate_trailing_stop(position)
        assert stop_price < position['current_price']

    def test_dynamic_stop_loss(self, stop_loss_manager):
        """Test le stop loss dynamique"""
        stop_loss_manager.set_type('dynamic')
        
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 45500.0,
            'quantity': 0.5
        }
        
        stop_price = stop_loss_manager.calculate_dynamic_stop(position)
        assert stop_price < position['entry_price']

# ============================================================
# TAKE PROFIT MANAGER TESTS
# ============================================================

class TestTakeProfitManager:
    """Tests pour le gestionnaire de take profit"""

    @pytest.fixture
    def take_profit_manager(self):
        """Fixture pour le gestionnaire de take profit"""
        config = {
            'enabled': True,
            'type': 'multiple',
            'targets': [0.01, 0.02, 0.03, 0.05],
            'allocation': [0.25, 0.25, 0.25, 0.25],
            'trailing_activation': 0.015
        }
        return TakeProfitManager(config)

    def test_initialization(self, take_profit_manager):
        """Test l'initialisation"""
        assert take_profit_manager is not None
        assert take_profit_manager.is_enabled() is True

    def test_calculate_take_profit(self, take_profit_manager):
        """Test le calcul du take profit"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 45500.0,
            'quantity': 0.5
        }
        
        targets = take_profit_manager.calculate_take_profit(position)
        assert len(targets) > 0
        for target in targets:
            assert target['price'] > position['entry_price']

    def test_check_take_profit(self, take_profit_manager):
        """Test la vérification du take profit"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 45500.0,
            'quantity': 0.5,
            'filled_quantity': 0.0
        }
        
        should_take, target = take_profit_manager.check_take_profit(position)
        assert should_take is True
        assert target is not None

    def test_multiple_targets(self, take_profit_manager):
        """Test les multiples targets"""
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 46000.0,
            'quantity': 1.0,
            'filled_quantity': 0.0
        }
        
        targets = take_profit_manager.calculate_take_profit(position)
        assert len(targets) == 4
        assert targets[0]['price'] < targets[1]['price']

    def test_trailing_take_profit(self, take_profit_manager):
        """Test le take profit trailing"""
        take_profit_manager.set_type('trailing')
        
        position = {
            'symbol': 'BTC/USDT',
            'entry_price': 45000.0,
            'current_price': 46000.0,
            'quantity': 0.5,
            'highest_price': 46000.0
        }
        
        target = take_profit_manager.calculate_trailing_target(position)
        assert target > position['entry_price']

# ============================================================
# CIRCUIT BREAKER TESTS
# ============================================================

class TestCircuitBreaker:
    """Tests pour le circuit breaker"""

    @pytest.fixture
    def circuit_breaker(self):
        """Fixture pour le circuit breaker"""
        config = {
            'enabled': True,
            'consecutive_failures': 5,
            'failure_window': 60,
            'cooldown_period': 300,
            'max_failures_per_hour': 20,
            'max_failures_per_day': 100
        }
        return CircuitBreaker(config)

    def test_initialization(self, circuit_breaker):
        """Test l'initialisation"""
        assert circuit_breaker is not None
        assert circuit_breaker.is_enabled() is True
        assert circuit_breaker.get_status() == 'CLOSED'

    def test_record_failure(self, circuit_breaker):
        """Test l'enregistrement d'un échec"""
        circuit_breaker.record_failure()
        assert circuit_breaker.get_failure_count() == 1
        
        circuit_breaker.record_failure()
        assert circuit_breaker.get_failure_count() == 2

    def test_record_success(self, circuit_breaker):
        """Test l'enregistrement d'un succès"""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.get_failure_count() == 2
        
        circuit_breaker.record_success()
        assert circuit_breaker.get_failure_count() == 0

    def test_trip_circuit(self, circuit_breaker):
        """Test le déclenchement du circuit breaker"""
        # Simuler des échecs consécutifs
        for i in range(5):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.get_status() == 'OPEN'

    def test_reset_circuit(self, circuit_breaker):
        """Test la réinitialisation du circuit breaker"""
        # Déclencher le circuit
        for i in range(5):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.get_status() == 'OPEN'
        
        # Réinitialiser
        circuit_breaker.reset()
        assert circuit_breaker.get_status() == 'CLOSED'
        assert circuit_breaker.get_failure_count() == 0

    def test_check_circuit(self, circuit_breaker):
        """Test la vérification du circuit"""
        # Circuit fermé
        can_execute = circuit_breaker.check_circuit()
        assert can_execute is True
        
        # Déclencher le circuit
        for i in range(5):
            circuit_breaker.record_failure()
        
        can_execute = circuit_breaker.check_circuit()
        assert can_execute is False

# ============================================================
# DRAWDOWN CONTROLLER TESTS
# ============================================================

class TestDrawdownController:
    """Tests pour le contrôleur de drawdown"""

    @pytest.fixture
    def drawdown_controller(self):
        """Fixture pour le contrôleur de drawdown"""
        config = {
            'enabled': True,
            'max_drawdown_daily': 0.05,
            'max_drawdown_weekly': 0.10,
            'max_drawdown_monthly': 0.15,
            'action': 'reduce',
            'reduce_factor': 0.5,
            'recovery_threshold': 0.03
        }
        return DrawdownController(config)

    def test_initialization(self, drawdown_controller):
        """Test l'initialisation"""
        assert drawdown_controller is not None
        assert drawdown_controller.is_enabled() is True

    def test_calculate_current_drawdown(self, drawdown_controller):
        """Test le calcul du drawdown actuel"""
        # Simuler un historique de PnL
        pnl_history = [100, 200, 300, 250, 200, 150, 175, 225]
        drawdown = drawdown_controller.calculate_current_drawdown(pnl_history)
        assert drawdown > 0

    def test_check_drawdown_limit(self, drawdown_controller):
        """Test la vérification des limites de drawdown"""
        pnl_history = [100, 200, 300, 250, 200, 150, 100, 50]
        
        # Vérifier la limite quotidienne
        is_exceeded = drawdown_controller.check_daily_limit(pnl_history)
        assert is_exceeded is True
        
        # Vérifier la limite hebdomadaire
        is_exceeded = drawdown_controller.check_weekly_limit(pnl_history)
        assert is_exceeded is True

    def test_get_drawdown_report(self, drawdown_controller):
        """Test la récupération du rapport de drawdown"""
        pnl_history = [100, 200, 300, 250, 200, 150, 175, 225]
        report = drawdown_controller.get_drawdown_report(pnl_history)
        
        assert report is not None
        assert 'current_drawdown' in report
        assert 'max_drawdown' in report
        assert 'drawdown_duration' in report

    def test_recovery_plan(self, drawdown_controller):
        """Test le plan de récupération"""
        # Simuler un drawdown
        pnl_history = [100, 200, 300, 250, 200, 150, 100, 50]
        
        plan = drawdown_controller.get_recovery_plan(pnl_history)
        assert plan is not None
        assert 'reduction_percentage' in plan
        assert 'expected_recovery_time' in plan

# ============================================================
# VAR CALCULATOR TESTS
# ============================================================

class TestVaRCalculator:
    """Tests pour le calculateur de VaR"""

    @pytest.fixture
    def var_calculator(self):
        """Fixture pour le calculateur de VaR"""
        config = {
            'confidence_level': 0.95,
            'time_horizon': 1,
            'calculation_method': 'historical',
            'historical_window': 365,
            'monte_carlo_simulations': 10000
        }
        return VaRCalculator(config)

    def test_initialization(self, var_calculator):
        """Test l'initialisation"""
        assert var_calculator is not None
        assert var_calculator.get_confidence_level() == 0.95

    def test_calculate_historical_var(self, var_calculator):
        """Test le calcul de la VaR historique"""
        # Simuler des rendements
        returns = np.random.normal(0, 0.02, 1000)
        var = var_calculator.calculate_historical_var(returns)
        assert var > 0

    def test_calculate_monte_carlo_var(self, var_calculator):
        """Test le calcul de la VaR Monte Carlo"""
        var_calculator.set_method('monte_carlo')
        
        # Simuler des paramètres
        mean_return = 0.001
        std_return = 0.02
        initial_value = 10000
        
        var = var_calculator.calculate_monte_carlo_var(
            initial_value, mean_return, std_return
        )
        assert var > 0

    def test_calculate_cvar(self, var_calculator):
        """Test le calcul de la CVaR"""
        # Simuler des rendements
        returns = np.random.normal(0, 0.02, 1000)
        var, cvar = var_calculator.calculate_var_cvar(returns)
        
        assert var > 0
        assert cvar > 0
        assert cvar >= var

    def test_calculate_var_with_portfolio(self, var_calculator):
        """Test le calcul de la VaR avec un portefeuille"""
        # Simuler un portefeuille
        portfolio = {
            'assets': ['BTC', 'ETH', 'SOL'],
            'weights': [0.5, 0.3, 0.2],
            'returns': [
                np.random.normal(0, 0.02, 100),
                np.random.normal(0, 0.025, 100),
                np.random.normal(0, 0.03, 100)
            ]
        }
        
        var = var_calculator.calculate_portfolio_var(portfolio)
        assert var > 0

# ============================================================
# RISK METRICS TESTS
# ============================================================

class TestRiskMetrics:
    """Tests pour les métriques de risque"""

    @pytest.fixture
    def risk_metrics(self):
        """Fixture pour les métriques de risque"""
        return RiskMetrics()

    def test_initialization(self, risk_metrics):
        """Test l'initialisation"""
        assert risk_metrics is not None

    def test_calculate_sharpe_ratio(self, risk_metrics):
        """Test le calcul du Sharpe ratio"""
        returns = [0.01, 0.02, -0.01, 0.015, 0.005, 0.02, -0.005, 0.01]
        sharpe = risk_metrics.calculate_sharpe_ratio(returns, 0.02)
        assert sharpe is not None

    def test_calculate_sortino_ratio(self, risk_metrics):
        """Test le calcul du Sortino ratio"""
        returns = [0.01, 0.02, -0.01, 0.015, 0.005, 0.02, -0.005, 0.01]
        sortino = risk_metrics.calculate_sortino_ratio(returns, 0.02)
        assert sortino is not None

    def test_calculate_calmar_ratio(self, risk_metrics):
        """Test le calcul du Calmar ratio"""
        returns = [0.01, 0.02, -0.01, 0.015, 0.005, 0.02, -0.005, 0.01]
        calmar = risk_metrics.calculate_calmar_ratio(returns)
        assert calmar is not None

    def test_calculate_max_drawdown(self, risk_metrics):
        """Test le calcul du drawdown maximum"""
        returns = [100, 200, 300, 250, 200, 150, 175, 225]
        drawdown = risk_metrics.calculate_max_drawdown(returns)
        assert drawdown > 0

    def test_calculate_profit_factor(self, risk_metrics):
        """Test le calcul du profit factor"""
        trades = [
            {'pnl': 100, 'type': 'win'},
            {'pnl': -50, 'type': 'loss'},
            {'pnl': 150, 'type': 'win'},
            {'pnl': -30, 'type': 'loss'}
        ]
        profit_factor = risk_metrics.calculate_profit_factor(trades)
        assert profit_factor > 0

    def test_get_all_metrics(self, risk_metrics):
        """Test la récupération de toutes les métriques"""
        returns = [0.01, 0.02, -0.01, 0.015, 0.005, 0.02, -0.005, 0.01]
        trades = [
            {'pnl': 100, 'type': 'win'},
            {'pnl': -50, 'type': 'loss'},
            {'pnl': 150, 'type': 'win'},
            {'pnl': -30, 'type': 'loss'}
        ]
        
        metrics = risk_metrics.get_all_metrics(returns, trades, 0.02)
        assert 'sharpe_ratio' in metrics
        assert 'sortino_ratio' in metrics
        assert 'calmar_ratio' in metrics
        assert 'profit_factor' in metrics
        assert 'max_drawdown' in metrics

# ============================================================
# RISK REPORTER TESTS
# ============================================================

class TestRiskReporter:
    """Tests pour le rapporteur de risques"""

    @pytest.fixture
    def risk_reporter(self):
        """Fixture pour le rapporteur de risques"""
        return RiskReporter()

    def test_initialization(self, risk_reporter):
        """Test l'initialisation"""
        assert risk_reporter is not None

    def test_generate_daily_report(self, risk_reporter):
        """Test la génération du rapport quotidien"""
        data = {
            'positions': [
                {'symbol': 'BTC/USDT', 'pnl': 100},
                {'symbol': 'ETH/USDT', 'pnl': -50}
            ],
            'trades': [
                {'symbol': 'BTC/USDT', 'pnl': 50},
                {'symbol': 'ETH/USDT', 'pnl': -30}
            ],
            'risk_metrics': {
                'sharpe_ratio': 1.5,
                'max_drawdown': 0.05
            }
        }
        
        report = risk_reporter.generate_daily_report(data)
        assert report is not None
        assert 'date' in report
        assert 'summary' in report
        assert 'positions' in report

    def test_generate_risk_summary(self, risk_reporter):
        """Test la génération du résumé des risques"""
        data = {
            'current_drawdown': 0.03,
            'daily_loss': 0.01,
            'weekly_loss': 0.02,
            'monthly_loss': 0.05,
            'positions_count': 5,
            'total_risk': 0.08
        }
        
        summary = risk_reporter.generate_risk_summary(data)
        assert summary is not None
        assert 'risk_level' in summary
        assert 'status' in summary
        assert 'recommendations' in summary

    def test_generate_alert_report(self, risk_reporter):
        """Test la génération du rapport d'alertes"""
        alerts = [
            {'type': 'drawdown', 'severity': 'warning', 'message': 'Drawdown exceeded 5%'},
            {'type': 'loss', 'severity': 'critical', 'message': 'Daily loss exceeded 2%'}
        ]
        
        report = risk_reporter.generate_alert_report(alerts)
        assert report is not None
        assert 'total_alerts' in report
        assert 'by_severity' in report

# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestRiskIntegration:
    """Tests d'intégration des risques"""

    def test_full_risk_flow(self, risk_manager, mock_exchange):
        """Test le flux complet de gestion des risques"""
        # Ajouter des positions
        for i in range(3):
            position = {
                'id': f'pos_{i}',
                'symbol': 'BTC/USDT',
                'entry_price': 45000.0 + i * 100,
                'current_price': 45000.0 + i * 150,
                'quantity': 0.5,
                'pnl': i * 50
            }
            risk_manager.add_position(position)
        
        # Vérifier les positions
        positions = risk_manager.get_positions()
        assert len(positions) == 3
        
        # Calculer le risque du portefeuille
        portfolio_risk = risk_manager.get_portfolio_risk()
        assert portfolio_risk is not None
        
        # Vérifier les limites de drawdown
        pnl_history = [100, 200, 300, 250, 200, 150]
        drawdown = risk_manager.calculate_drawdown(pnl_history)
        assert drawdown > 0
        
        # Valider un trade
        trade = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'quantity': 0.5,
            'price': 45000.0,
            'risk': 0.01
        }
        is_valid = risk_manager.validate_trade(trade)
        assert is_valid is True

    def test_risk_monitoring_flow(self, risk_manager):
        """Test le flux de monitoring des risques"""
        # Ajouter des positions
        for i in range(3):
            position = {
                'id': f'pos_{i}',
                'symbol': 'BTC/USDT',
                'entry_price': 45000.0,
                'current_price': 45000.0 + i * 100,
                'quantity': 0.5,
                'pnl': i * 50
            }
            risk_manager.add_position(position)
        
        # Monitorer les positions
        alerts = risk_manager.monitor_positions()
        assert alerts is not None
        
        # Vérifier les alertes
        if alerts:
            for alert in alerts:
                assert 'type' in alert
                assert 'message' in alert
                assert 'severity' in alert

# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestRiskPerformance:
    """Tests de performance des risques"""

    def test_risk_calculation_performance(self, risk_manager):
        """Test la performance des calculs de risque"""
        import time
        
        # Ajouter de nombreuses positions
        for i in range(100):
            position = {
                'id': f'pos_{i}',
                'symbol': 'BTC/USDT',
                'entry_price': 45000.0 + i * 10,
                'current_price': 45000.0 + i * 15,
                'quantity': 0.5,
                'pnl': i * 5
            }
            risk_manager.add_position(position)
        
        # Mesurer le temps de calcul du risque
        start_time = time.time()
        portfolio_risk = risk_manager.get_portfolio_risk()
        end_time = time.time()
        
        calculation_time = (end_time - start_time) * 1000  # ms
        assert calculation_time < 100  # Moins de 100ms

    def test_drawdown_calculation_performance(self, risk_manager):
        """Test la performance des calculs de drawdown"""
        import time
        
        # Simuler un long historique de PnL
        pnl_history = [i * 10 for i in range(1000)]
        pnl_history[500:600] = [x - 1000 for x in pnl_history[500:600]]
        
        # Mesurer le temps de calcul du drawdown
        start_time = time.time()
        drawdown = risk_manager.calculate_drawdown(pnl_history)
        end_time = time.time()
        
        calculation_time = (end_time - start_time) * 1000  # ms
        assert calculation_time < 50  # Moins de 50ms

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

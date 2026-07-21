"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Models Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests des modèles de données pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import asdict, fields

# Import des modèles
from trading.bots.arbitrage_bot.models.base import BaseModel
from trading.bots.arbitrage_bot.models.order import Order, OrderSide, OrderType, OrderStatus, TimeInForce
from trading.bots.arbitrage_bot.models.trade import Trade
from trading.bots.arbitrage_bot.models.position import Position
from trading.bots.arbitrage_bot.models.balance import Balance
from trading.bots.arbitrage_bot.models.ticker import Ticker
from trading.bots.arbitrage_bot.models.order_book import OrderBook
from trading.bots.arbitrage_bot.models.kline import Kline
from trading.bots.arbitrage_bot.models.opportunity import Opportunity, OpportunityType, OpportunityStatus
from trading.bots.arbitrage_bot.models.strategy import Strategy, StrategyType, StrategyStatus
from trading.bots.arbitrage_bot.models.risk import RiskMetrics, RiskLevel
from trading.bots.arbitrage_bot.models.config import Config
from trading.bots.arbitrage_bot.models.notification import Notification, NotificationSeverity, NotificationType
from trading.bots.arbitrage_bot.models.user import User, UserRole, UserStatus
from trading.bots.arbitrage_bot.models.exchange import Exchange, ExchangeType, ExchangeStatus
from trading.bots.arbitrage_bot.models.market import Market, MarketType, MarketStatus

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# BASE MODEL TESTS
# ============================================================

class TestBaseModel:
    """Tests pour le modèle de base"""

    def test_initialization(self):
        """Test l'initialisation"""
        model = BaseModel()
        assert model is not None
        assert model.created_at is not None
        assert model.updated_at is not None

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        model = BaseModel()
        data = model.to_dict()
        assert isinstance(data, dict)
        assert 'created_at' in data
        assert 'updated_at' in data

    def test_from_dict(self):
        """Test la création depuis un dictionnaire"""
        data = {
            'id': 'test_123',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        model = BaseModel.from_dict(data)
        assert model.id == 'test_123'

    def test_to_json(self):
        """Test la conversion en JSON"""
        model = BaseModel()
        json_str = model.to_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert 'created_at' in data

    def test_from_json(self):
        """Test la création depuis JSON"""
        json_str = json.dumps({
            'id': 'test_123',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
        model = BaseModel.from_json(json_str)
        assert model.id == 'test_123'

    def test_validate(self):
        """Test la validation"""
        model = BaseModel()
        is_valid = model.validate()
        assert is_valid is True

# ============================================================
# ORDER MODEL TESTS
# ============================================================

class TestOrderModel:
    """Tests pour le modèle Order"""

    def test_initialization(self):
        """Test l'initialisation"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0
        )
        assert order is not None
        assert order.symbol == 'BTC/USDT'
        assert order.side == OrderSide.BUY
        assert order.quantity == 0.5
        assert order.price == 45000.0

    def test_create_market_order(self):
        """Test la création d'un ordre au marché"""
        order = Order.create_market_order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=0.5
        )
        assert order.order_type == OrderType.MARKET
        assert order.price is None

    def test_create_limit_order(self):
        """Test la création d'un ordre à limite"""
        order = Order.create_limit_order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=0.5,
            price=45000.0
        )
        assert order.order_type == OrderType.LIMIT
        assert order.price == 45000.0

    def test_calculate_cost(self):
        """Test le calcul du coût"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0
        )
        cost = order.calculate_cost()
        assert cost == 22500.0

    def test_calculate_fee(self):
        """Test le calcul des frais"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0,
            fee_rate=0.001
        )
        fee = order.calculate_fee()
        assert fee == 22.5

    def test_is_filled(self):
        """Test la vérification du remplissage"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0,
            status=OrderStatus.FILLED
        )
        assert order.is_filled() is True

    def test_is_active(self):
        """Test la vérification de l'activité"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0,
            status=OrderStatus.NEW
        )
        assert order.is_active() is True

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0
        )
        data = order.to_dict()
        assert data['symbol'] == 'BTC/USDT'
        assert data['side'] == 'BUY'
        assert data['quantity'] == 0.5

# ============================================================
# TRADE MODEL TESTS
# ============================================================

class TestTradeModel:
    """Tests pour le modèle Trade"""

    def test_initialization(self):
        """Test l'initialisation"""
        trade = Trade(
            id='trade_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            price=45000.0,
            quantity=0.5,
            cost=22500.0,
            fee=22.5,
            fee_asset='USDT'
        )
        assert trade is not None
        assert trade.id == 'trade_001'
        assert trade.symbol == 'BTC/USDT'
        assert trade.price == 45000.0

    def test_calculate_pnl(self):
        """Test le calcul du P&L"""
        trade = Trade(
            id='trade_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            price=45000.0,
            quantity=0.5,
            cost=22500.0,
            fee=22.5,
            fee_asset='USDT'
        )
        pnl = trade.calculate_pnl(46000.0)
        assert pnl == 500.0

    def test_calculate_return(self):
        """Test le calcul du retour"""
        trade = Trade(
            id='trade_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            price=45000.0,
            quantity=0.5,
            cost=22500.0,
            fee=22.5,
            fee_asset='USDT'
        )
        return_pct = trade.calculate_return(46000.0)
        assert return_pct == 0.0222

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        trade = Trade(
            id='trade_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            price=45000.0,
            quantity=0.5,
            cost=22500.0,
            fee=22.5,
            fee_asset='USDT'
        )
        data = trade.to_dict()
        assert data['id'] == 'trade_001'
        assert data['symbol'] == 'BTC/USDT'
        assert data['price'] == 45000.0

# ============================================================
# POSITION MODEL TESTS
# ============================================================

class TestPositionModel:
    """Tests pour le modèle Position"""

    def test_initialization(self):
        """Test l'initialisation"""
        position = Position(
            id='pos_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            entry_price=45000.0,
            quantity=0.5,
            current_price=46000.0
        )
        assert position is not None
        assert position.symbol == 'BTC/USDT'
        assert position.entry_price == 45000.0

    def test_calculate_pnl(self):
        """Test le calcul du P&L"""
        position = Position(
            id='pos_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            entry_price=45000.0,
            quantity=0.5,
            current_price=46000.0
        )
        pnl = position.calculate_pnl()
        assert pnl == 500.0

    def test_calculate_return(self):
        """Test le calcul du retour"""
        position = Position(
            id='pos_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            entry_price=45000.0,
            quantity=0.5,
            current_price=46000.0
        )
        return_pct = position.calculate_return()
        assert return_pct == 0.0222

    def test_update_price(self):
        """Test la mise à jour du prix"""
        position = Position(
            id='pos_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            entry_price=45000.0,
            quantity=0.5,
            current_price=46000.0
        )
        position.update_price(47000.0)
        assert position.current_price == 47000.0

    def test_is_profitable(self):
        """Test la vérification de profitabilité"""
        position = Position(
            id='pos_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            entry_price=45000.0,
            quantity=0.5,
            current_price=46000.0
        )
        assert position.is_profitable() is True

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        position = Position(
            id='pos_001',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            entry_price=45000.0,
            quantity=0.5,
            current_price=46000.0
        )
        data = position.to_dict()
        assert data['symbol'] == 'BTC/USDT'
        assert data['entry_price'] == 45000.0

# ============================================================
# BALANCE MODEL TESTS
# ============================================================

class TestBalanceModel:
    """Tests pour le modèle Balance"""

    def test_initialization(self):
        """Test l'initialisation"""
        balance = Balance(
            asset='BTC',
            free=1.5,
            locked=0.5,
            total=2.0
        )
        assert balance is not None
        assert balance.asset == 'BTC'
        assert balance.free == 1.5
        assert balance.locked == 0.5

    def test_calculate_available(self):
        """Test le calcul du disponible"""
        balance = Balance(
            asset='BTC',
            free=1.5,
            locked=0.5,
            total=2.0
        )
        available = balance.calculate_available()
        assert available == 1.5

    def test_update(self):
        """Test la mise à jour"""
        balance = Balance(
            asset='BTC',
            free=1.5,
            locked=0.5,
            total=2.0
        )
        balance.update(free=2.0, locked=1.0)
        assert balance.free == 2.0
        assert balance.locked == 1.0
        assert balance.total == 3.0

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        balance = Balance(
            asset='BTC',
            free=1.5,
            locked=0.5,
            total=2.0
        )
        data = balance.to_dict()
        assert data['asset'] == 'BTC'
        assert data['free'] == 1.5

# ============================================================
# TICKER MODEL TESTS
# ============================================================

class TestTickerModel:
    """Tests pour le modèle Ticker"""

    def test_initialization(self):
        """Test l'initialisation"""
        ticker = Ticker(
            symbol='BTC/USDT',
            bid=44950.0,
            ask=45050.0,
            last=45000.0,
            volume=1250.5,
            high=45200.0,
            low=44800.0,
            change=100.0,
            change_percent=0.22
        )
        assert ticker is not None
        assert ticker.symbol == 'BTC/USDT'
        assert ticker.bid == 44950.0

    def test_calculate_spread(self):
        """Test le calcul du spread"""
        ticker = Ticker(
            symbol='BTC/USDT',
            bid=44950.0,
            ask=45050.0,
            last=45000.0,
            volume=1250.5
        )
        spread = ticker.calculate_spread()
        assert spread == 100.0

    def test_update(self):
        """Test la mise à jour"""
        ticker = Ticker(
            symbol='BTC/USDT',
            bid=44950.0,
            ask=45050.0,
            last=45000.0,
            volume=1250.5
        )
        ticker.update(bid=45000.0, ask=45100.0, last=45050.0)
        assert ticker.bid == 45000.0
        assert ticker.ask == 45100.0
        assert ticker.last == 45050.0

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        ticker = Ticker(
            symbol='BTC/USDT',
            bid=44950.0,
            ask=45050.0,
            last=45000.0,
            volume=1250.5
        )
        data = ticker.to_dict()
        assert data['symbol'] == 'BTC/USDT'
        assert data['bid'] == 44950.0

# ============================================================
# OPPORTUNITY MODEL TESTS
# ============================================================

class TestOpportunityModel:
    """Tests pour le modèle Opportunity"""

    def test_initialization(self):
        """Test l'initialisation"""
        opportunity = Opportunity(
            id='opp_001',
            pair='BTC/USDT',
            type=OpportunityType.CROSS_EXCHANGE,
            exchange_a='Binance',
            exchange_b='Coinbase',
            price_a=45000.0,
            price_b=45100.0,
            spread=100.0,
            profit=95.0,
            profit_percent=0.0021,
            volume=1.5,
            status=OpportunityStatus.PENDING
        )
        assert opportunity is not None
        assert opportunity.pair == 'BTC/USDT'
        assert opportunity.profit == 95.0

    def test_calculate_profit(self):
        """Test le calcul du profit"""
        opportunity = Opportunity(
            pair='BTC/USDT',
            type=OpportunityType.CROSS_EXCHANGE,
            exchange_a='Binance',
            exchange_b='Coinbase',
            price_a=45000.0,
            price_b=45100.0,
            volume=1.5
        )
        profit = opportunity.calculate_profit()
        assert profit == 150.0

    def test_validate(self):
        """Test la validation"""
        opportunity = Opportunity(
            pair='BTC/USDT',
            type=OpportunityType.CROSS_EXCHANGE,
            exchange_a='Binance',
            exchange_b='Coinbase',
            price_a=45000.0,
            price_b=45100.0,
            volume=1.5
        )
        is_valid = opportunity.validate()
        assert is_valid is True

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        opportunity = Opportunity(
            pair='BTC/USDT',
            type=OpportunityType.CROSS_EXCHANGE,
            exchange_a='Binance',
            exchange_b='Coinbase',
            price_a=45000.0,
            price_b=45100.0
        )
        data = opportunity.to_dict()
        assert data['pair'] == 'BTC/USDT'
        assert data['price_a'] == 45000.0

# ============================================================
# STRATEGY MODEL TESTS
# ============================================================

class TestStrategyModel:
    """Tests pour le modèle Strategy"""

    def test_initialization(self):
        """Test l'initialisation"""
        strategy = Strategy(
            id='strat_001',
            name='Cross Exchange Arbitrage',
            type=StrategyType.CROSS_EXCHANGE,
            status=StrategyStatus.ACTIVE,
            parameters={
                'min_profit': 0.001,
                'max_spread': 0.10,
                'max_position': 1000
            }
        )
        assert strategy is not None
        assert strategy.name == 'Cross Exchange Arbitrage'
        assert strategy.type == StrategyType.CROSS_EXCHANGE

    def test_validate_parameters(self):
        """Test la validation des paramètres"""
        strategy = Strategy(
            id='strat_001',
            name='Cross Exchange Arbitrage',
            type=StrategyType.CROSS_EXCHANGE,
            parameters={
                'min_profit': 0.001,
                'max_spread': 0.10,
                'max_position': 1000
            }
        )
        is_valid = strategy.validate_parameters()
        assert is_valid is True

    def test_is_active(self):
        """Test la vérification de l'activité"""
        strategy = Strategy(
            id='strat_001',
            name='Test Strategy',
            type=StrategyType.CROSS_EXCHANGE,
            status=StrategyStatus.ACTIVE
        )
        assert strategy.is_active() is True

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        strategy = Strategy(
            id='strat_001',
            name='Test Strategy',
            type=StrategyType.CROSS_EXCHANGE,
            parameters={'min_profit': 0.001}
        )
        data = strategy.to_dict()
        assert data['name'] == 'Test Strategy'
        assert data['type'] == 'CROSS_EXCHANGE'

# ============================================================
# RISK METRICS MODEL TESTS
# ============================================================

class TestRiskMetricsModel:
    """Tests pour le modèle RiskMetrics"""

    def test_initialization(self):
        """Test l'initialisation"""
        risk = RiskMetrics(
            total_pnl=10000.0,
            total_trades=100,
            win_rate=0.65,
            sharpe_ratio=1.8,
            max_drawdown=0.05,
            var_95=0.02,
            cvar_95=0.03,
            risk_level=RiskLevel.MEDIUM
        )
        assert risk is not None
        assert risk.total_pnl == 10000.0
        assert risk.win_rate == 0.65

    def test_calculate_sharpe_ratio(self):
        """Test le calcul du Sharpe ratio"""
        risk = RiskMetrics()
        returns = [0.01, 0.02, -0.01, 0.015, 0.005, 0.02, -0.005, 0.01]
        sharpe = risk.calculate_sharpe_ratio(returns, 0.02)
        assert sharpe is not None

    def test_calculate_drawdown(self):
        """Test le calcul du drawdown"""
        risk = RiskMetrics()
        returns = [100, 200, 300, 250, 200, 150, 175, 225]
        drawdown = risk.calculate_drawdown(returns)
        assert drawdown > 0

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        risk = RiskMetrics(
            total_pnl=10000.0,
            win_rate=0.65,
            risk_level=RiskLevel.MEDIUM
        )
        data = risk.to_dict()
        assert data['total_pnl'] == 10000.0
        assert data['risk_level'] == 'MEDIUM'

# ============================================================
# NOTIFICATION MODEL TESTS
# ============================================================

class TestNotificationModel:
    """Tests pour le modèle Notification"""

    def test_initialization(self):
        """Test l'initialisation"""
        notification = Notification(
            id='notif_001',
            type=NotificationType.INFO,
            severity=NotificationSeverity.INFO,
            title='Test Notification',
            message='This is a test notification',
            source='test'
        )
        assert notification is not None
        assert notification.title == 'Test Notification'
        assert notification.severity == NotificationSeverity.INFO

    def test_is_read(self):
        """Test la vérification de lecture"""
        notification = Notification(
            id='notif_001',
            type=NotificationType.INFO,
            severity=NotificationSeverity.INFO,
            title='Test Notification',
            message='This is a test notification'
        )
        assert notification.is_read() is False
        notification.mark_as_read()
        assert notification.is_read() is True

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        notification = Notification(
            id='notif_001',
            type=NotificationType.INFO,
            severity=NotificationSeverity.INFO,
            title='Test Notification',
            message='This is a test notification'
        )
        data = notification.to_dict()
        assert data['title'] == 'Test Notification'
        assert data['type'] == 'INFO'

# ============================================================
# USER MODEL TESTS
# ============================================================

class TestUserModel:
    """Tests pour le modèle User"""

    def test_initialization(self):
        """Test l'initialisation"""
        user = User(
            id='user_001',
            username='test_user',
            email='test@example.com',
            role=UserRole.USER,
            status=UserStatus.ACTIVE
        )
        assert user is not None
        assert user.username == 'test_user'
        assert user.role == UserRole.USER

    def test_has_permission(self):
        """Test la vérification des permissions"""
        user = User(
            id='user_001',
            username='test_user',
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE
        )
        assert user.has_permission('manage_users') is True

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        user = User(
            id='user_001',
            username='test_user',
            email='test@example.com',
            role=UserRole.USER
        )
        data = user.to_dict()
        assert data['username'] == 'test_user'
        assert data['role'] == 'USER'

# ============================================================
# EXCHANGE MODEL TESTS
# ============================================================

class TestExchangeModel:
    """Tests pour le modèle Exchange"""

    def test_initialization(self):
        """Test l'initialisation"""
        exchange = Exchange(
            id='exchange_001',
            name='Binance',
            type=ExchangeType.CEX,
            status=ExchangeStatus.CONNECTED,
            api_key='test_key',
            api_secret='test_secret'
        )
        assert exchange is not None
        assert exchange.name == 'Binance'
        assert exchange.type == ExchangeType.CEX

    def test_is_connected(self):
        """Test la vérification de connexion"""
        exchange = Exchange(
            id='exchange_001',
            name='Binance',
            type=ExchangeType.CEX,
            status=ExchangeStatus.CONNECTED
        )
        assert exchange.is_connected() is True

    def test_to_dict(self):
        """Test la conversion en dictionnaire"""
        exchange = Exchange(
            id='exchange_001',
            name='Binance',
            type=ExchangeType.CEX,
            status=ExchangeStatus.CONNECTED
        )
        data = exchange.to_dict()
        assert data['name'] == 'Binance'
        assert data['type'] == 'CEX'

# ============================================================
# SERIALIZATION TESTS
# ============================================================

class TestSerialization:
    """Tests de sérialisation des modèles"""

    def test_json_serialization(self):
        """Test la sérialisation JSON"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0
        )
        
        # Sérialiser
        json_str = order.to_json()
        assert isinstance(json_str, str)
        
        # Désérialiser
        new_order = Order.from_json(json_str)
        assert new_order.symbol == order.symbol
        assert new_order.side == order.side
        assert new_order.quantity == order.quantity

    def test_pickle_serialization(self):
        """Test la sérialisation Pickle"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0
        )
        
        # Sérialiser
        pickled = pickle.dumps(order)
        assert isinstance(pickled, bytes)
        
        # Désérialiser
        new_order = pickle.loads(pickled)
        assert new_order.symbol == order.symbol
        assert new_order.side == order.side
        assert new_order.quantity == order.quantity

    def test_dict_serialization(self):
        """Test la sérialisation en dictionnaire"""
        order = Order(
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=45000.0
        )
        
        # Sérialiser
        data = order.to_dict()
        assert isinstance(data, dict)
        
        # Désérialiser
        new_order = Order.from_dict(data)
        assert new_order.symbol == order.symbol
        assert new_order.side == order.side
        assert new_order.quantity == order.quantity

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

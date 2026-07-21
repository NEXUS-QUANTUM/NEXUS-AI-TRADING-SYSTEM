"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Exchange Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests des exchanges et de l'intégration des exchanges pour le bot d'arbitrage
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

# Import du module à tester
from trading.bots.arbitrage_bot.exchanges.base_exchange import BaseExchange
from trading.bots.arbitrage_bot.exchanges.binance_exchange import BinanceExchange
from trading.bots.arbitrage_bot.exchanges.bybit_exchange import BybitExchange
from trading.bots.arbitrage_bot.exchanges.coinbase_exchange import CoinbaseExchange
from trading.bots.arbitrage_bot.exchanges.kraken_exchange import KrakenExchange
from trading.bots.arbitrage_bot.exchanges.kucoin_exchange import KuCoinExchange
from trading.bots.arbitrage_bot.exchanges.okx_exchange import OKXExchange
from trading.bots.arbitrage_bot.exchanges.exchange_factory import ExchangeFactory
from trading.bots.arbitrage_bot.exchanges.exchange_manager import ExchangeManager

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    test_data,
    test_tickers,
    test_order_books,
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
# BASE EXCHANGE TESTS
# ============================================================

class TestBaseExchange:
    """Tests pour la classe de base des exchanges"""

    @pytest.fixture
    def base_exchange(self):
        """Fixture pour un exchange de base"""
        return BaseExchange("Test Exchange")

    def test_initialization(self, base_exchange):
        """Test l'initialisation"""
        assert base_exchange is not None
        assert base_exchange.name == "Test Exchange"
        assert base_exchange.is_connected() is False

    def test_connect_disconnect(self, base_exchange):
        """Test la connexion/déconnexion"""
        # Connecter
        base_exchange.connect()
        assert base_exchange.is_connected() is True
        
        # Déconnecter
        base_exchange.disconnect()
        assert base_exchange.is_connected() is False

    def test_set_credentials(self, base_exchange):
        """Test la définition des identifiants"""
        credentials = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'passphrase': 'test_passphrase'
        }
        
        base_exchange.set_credentials(credentials)
        assert base_exchange.get_credentials() == credentials

    def test_get_symbols(self, base_exchange):
        """Test la récupération des symboles"""
        symbols = base_exchange.get_symbols()
        assert symbols is not None

    def test_get_price(self, base_exchange):
        """Test la récupération du prix"""
        # En mode non connecté, devrait retourner 0
        price = base_exchange.get_price('BTC/USDT')
        assert price == 0.0

    def test_get_balance(self, base_exchange):
        """Test la récupération du solde"""
        balance = base_exchange.get_balance()
        assert balance is not None

# ============================================================
# BINANCE EXCHANGE TESTS
# ============================================================

class TestBinanceExchange:
    """Tests pour l'exchange Binance"""

    @pytest.fixture
    def binance_exchange(self):
        """Fixture pour un exchange Binance"""
        config = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'testnet': True,
            'testnet_url': 'https://testnet.binance.vision'
        }
        return BinanceExchange(config)

    def test_initialization(self, binance_exchange):
        """Test l'initialisation"""
        assert binance_exchange is not None
        assert binance_exchange.name == "Binance"
        assert binance_exchange.is_testnet() is True

    def test_get_symbols(self, binance_exchange):
        """Test la récupération des symboles"""
        # Simuler une réponse API
        with patch('trading.bots.arbitrage_bot.exchanges.binance_exchange.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'symbols': [
                    {'symbol': 'BTCUSDT', 'baseAsset': 'BTC', 'quoteAsset': 'USDT'},
                    {'symbol': 'ETHUSDT', 'baseAsset': 'ETH', 'quoteAsset': 'USDT'}
                ]
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            symbols = binance_exchange.get_symbols()
            assert len(symbols) > 0
            assert 'BTC/USDT' in symbols

    def test_format_symbol(self, binance_exchange):
        """Test le formatage des symboles"""
        # Format Binance: BTCUSDT
        formatted = binance_exchange.format_symbol('BTC/USDT')
        assert formatted == 'BTCUSDT'
        
        # Format standard: BTC/USDT
        standard = binance_exchange.format_standard_symbol('BTCUSDT')
        assert standard == 'BTC/USDT'

    def test_create_order(self, binance_exchange):
        """Test la création d'un ordre"""
        with patch('trading.bots.arbitrage_bot.exchanges.binance_exchange.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                'orderId': '123456',
                'symbol': 'BTCUSDT',
                'side': 'BUY',
                'type': 'LIMIT',
                'price': '45000.00',
                'origQty': '0.50000000',
                'status': 'NEW'
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            order = binance_exchange.create_order(
                symbol='BTC/USDT',
                side='BUY',
                order_type='LIMIT',
                quantity=0.5,
                price=45000.0
            )
            
            assert order is not None
            assert order['orderId'] == '123456'
            assert order['symbol'] == 'BTCUSDT'

    def test_get_order_status(self, binance_exchange):
        """Test la récupération du statut d'un ordre"""
        with patch('trading.bots.arbitrage_bot.exchanges.binance_exchange.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'orderId': '123456',
                'symbol': 'BTCUSDT',
                'status': 'FILLED',
                'executedQty': '0.50000000'
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            status = binance_exchange.get_order_status('123456')
            assert status is not None
            assert status['status'] == 'FILLED'

    def test_cancel_order(self, binance_exchange):
        """Test l'annulation d'un ordre"""
        with patch('trading.bots.arbitrage_bot.exchanges.binance_exchange.requests.delete') as mock_delete:
            mock_response = Mock()
            mock_response.json.return_value = {
                'orderId': '123456',
                'symbol': 'BTCUSDT',
                'status': 'CANCELED'
            }
            mock_response.status_code = 200
            mock_delete.return_value = mock_response
            
            result = binance_exchange.cancel_order('123456')
            assert result is True

# ============================================================
# BYBIT EXCHANGE TESTS
# ============================================================

class TestBybitExchange:
    """Tests pour l'exchange Bybit"""

    @pytest.fixture
    def bybit_exchange(self):
        """Fixture pour un exchange Bybit"""
        config = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'testnet': True,
            'testnet_url': 'https://api-testnet.bybit.com'
        }
        return BybitExchange(config)

    def test_initialization(self, bybit_exchange):
        """Test l'initialisation"""
        assert bybit_exchange is not None
        assert bybit_exchange.name == "Bybit"
        assert bybit_exchange.is_testnet() is True

    def test_format_symbol(self, bybit_exchange):
        """Test le formatage des symboles"""
        # Format Bybit: BTCUSDT
        formatted = bybit_exchange.format_symbol('BTC/USDT')
        assert formatted == 'BTCUSDT'
        
        # Format standard: BTC/USDT
        standard = bybit_exchange.format_standard_symbol('BTCUSDT')
        assert standard == 'BTC/USDT'

    def test_get_websocket_url(self, bybit_exchange):
        """Test la récupération de l'URL WebSocket"""
        url = bybit_exchange.get_websocket_url()
        assert 'wss://' in url
        assert 'bybit' in url

# ============================================================
# COINBASE EXCHANGE TESTS
# ============================================================

class TestCoinbaseExchange:
    """Tests pour l'exchange Coinbase"""

    @pytest.fixture
    def coinbase_exchange(self):
        """Fixture pour un exchange Coinbase"""
        config = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'passphrase': 'test_passphrase',
            'sandbox': True,
            'sandbox_url': 'https://api-public.sandbox.exchange.coinbase.com'
        }
        return CoinbaseExchange(config)

    def test_initialization(self, coinbase_exchange):
        """Test l'initialisation"""
        assert coinbase_exchange is not None
        assert coinbase_exchange.name == "Coinbase"
        assert coinbase_exchange.is_sandbox() is True

    def test_format_symbol(self, coinbase_exchange):
        """Test le formatage des symboles"""
        # Format Coinbase: BTC-USD
        formatted = coinbase_exchange.format_symbol('BTC/USDT')
        assert formatted == 'BTC-USD'
        
        # Format standard: BTC/USDT
        standard = coinbase_exchange.format_standard_symbol('BTC-USD')
        assert standard == 'BTC/USD'  # Coinbase utilise USD comme quote

    def test_get_fee(self, coinbase_exchange):
        """Test la récupération des frais"""
        with patch('trading.bots.arbitrage_bot.exchanges.coinbase_exchange.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'maker_fee_rate': '0.0040',
                'taker_fee_rate': '0.0060'
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            fees = coinbase_exchange.get_fees()
            assert fees is not None
            assert fees['maker'] == 0.004
            assert fees['taker'] == 0.006

# ============================================================
# KRAKEN EXCHANGE TESTS
# ============================================================

class TestKrakenExchange:
    """Tests pour l'exchange Kraken"""

    @pytest.fixture
    def kraken_exchange(self):
        """Fixture pour un exchange Kraken"""
        config = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'sandbox': True
        }
        return KrakenExchange(config)

    def test_initialization(self, kraken_exchange):
        """Test l'initialisation"""
        assert kraken_exchange is not None
        assert kraken_exchange.name == "Kraken"
        assert kraken_exchange.is_sandbox() is True

    def test_format_symbol(self, kraken_exchange):
        """Test le formatage des symboles"""
        # Format Kraken: XBTUSD
        formatted = kraken_exchange.format_symbol('BTC/USD')
        assert formatted == 'XBTUSD'
        
        # Format standard: BTC/USD
        standard = kraken_exchange.format_standard_symbol('XBTUSD')
        assert standard == 'BTC/USD'

    def test_get_order_book(self, kraken_exchange):
        """Test la récupération du carnet d'ordres"""
        with patch('trading.bots.arbitrage_bot.exchanges.kraken_exchange.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'result': {
                    'XXBTZUSD': {
                        'bids': [['45000.0', '1.5']],
                        'asks': [['45100.0', '2.0']]
                    }
                }
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            order_book = kraken_exchange.get_order_book('BTC/USD')
            assert order_book is not None
            assert len(order_book['bids']) > 0
            assert len(order_book['asks']) > 0

# ============================================================
# KUCOIN EXCHANGE TESTS
# ============================================================

class TestKuCoinExchange:
    """Tests pour l'exchange KuCoin"""

    @pytest.fixture
    def kucoin_exchange(self):
        """Fixture pour un exchange KuCoin"""
        config = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'passphrase': 'test_passphrase',
            'sandbox': True
        }
        return KuCoinExchange(config)

    def test_initialization(self, kucoin_exchange):
        """Test l'initialisation"""
        assert kucoin_exchange is not None
        assert kucoin_exchange.name == "KuCoin"
        assert kucoin_exchange.is_sandbox() is True

    def test_format_symbol(self, kucoin_exchange):
        """Test le formatage des symboles"""
        # Format KuCoin: BTC-USDT
        formatted = kucoin_exchange.format_symbol('BTC/USDT')
        assert formatted == 'BTC-USDT'
        
        # Format standard: BTC/USDT
        standard = kucoin_exchange.format_standard_symbol('BTC-USDT')
        assert standard == 'BTC/USDT'

    def test_get_server_time(self, kucoin_exchange):
        """Test la récupération de l'heure du serveur"""
        with patch('trading.bots.arbitrage_bot.exchanges.kucoin_exchange.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'data': {'serverTime': 1704067200000}
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            server_time = kucoin_exchange.get_server_time()
            assert server_time is not None
            assert isinstance(server_time, int)

# ============================================================
# OKX EXCHANGE TESTS
# ============================================================

class TestOKXExchange:
    """Tests pour l'exchange OKX"""

    @pytest.fixture
    def okx_exchange(self):
        """Fixture pour un exchange OKX"""
        config = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'passphrase': 'test_passphrase',
            'sandbox': True
        }
        return OKXExchange(config)

    def test_initialization(self, okx_exchange):
        """Test l'initialisation"""
        assert okx_exchange is not None
        assert okx_exchange.name == "OKX"
        assert okx_exchange.is_sandbox() is True

    def test_format_symbol(self, okx_exchange):
        """Test le formatage des symboles"""
        # Format OKX: BTC-USDT
        formatted = okx_exchange.format_symbol('BTC/USDT')
        assert formatted == 'BTC-USDT'
        
        # Format standard: BTC/USDT
        standard = okx_exchange.format_standard_symbol('BTC-USDT')
        assert standard == 'BTC/USDT'

    def test_get_instruments(self, okx_exchange):
        """Test la récupération des instruments"""
        with patch('trading.bots.arbitrage_bot.exchanges.okx_exchange.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'data': [
                    {'instId': 'BTC-USDT', 'instType': 'SPOT'},
                    {'instId': 'ETH-USDT', 'instType': 'SPOT'}
                ]
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            instruments = okx_exchange.get_instruments()
            assert len(instruments) > 0
            assert 'BTC-USDT' in instruments

# ============================================================
# EXCHANGE FACTORY TESTS
# ============================================================

class TestExchangeFactory:
    """Tests pour la fabrique d'exchanges"""

    def test_create_exchange(self):
        """Test la création d'un exchange"""
        # Créer un exchange Binance
        exchange = ExchangeFactory.create_exchange('binance')
        assert exchange is not None
        assert exchange.name == "Binance"
        
        # Créer un exchange Bybit
        exchange = ExchangeFactory.create_exchange('bybit')
        assert exchange is not None
        assert exchange.name == "Bybit"
        
        # Créer un exchange Coinbase
        exchange = ExchangeFactory.create_exchange('coinbase')
        assert exchange is not None
        assert exchange.name == "Coinbase"
        
        # Créer un exchange Kraken
        exchange = ExchangeFactory.create_exchange('kraken')
        assert exchange is not None
        assert exchange.name == "Kraken"
        
        # Créer un exchange KuCoin
        exchange = ExchangeFactory.create_exchange('kucoin')
        assert exchange is not None
        assert exchange.name == "KuCoin"
        
        # Créer un exchange OKX
        exchange = ExchangeFactory.create_exchange('okx')
        assert exchange is not None
        assert exchange.name == "OKX"

    def test_create_with_config(self):
        """Test la création avec configuration"""
        config = {'api_key': 'test_key', 'api_secret': 'test_secret'}
        exchange = ExchangeFactory.create_exchange('binance', config)
        assert exchange is not None
        assert exchange.get_credentials()['api_key'] == 'test_key'

    def test_invalid_exchange_type(self):
        """Test la création d'un type invalide"""
        with pytest.raises(ValueError):
            ExchangeFactory.create_exchange('invalid_exchange')

    def test_get_available_exchanges(self):
        """Test la récupération des exchanges disponibles"""
        exchanges = ExchangeFactory.get_available_exchanges()
        assert 'binance' in exchanges
        assert 'bybit' in exchanges
        assert 'coinbase' in exchanges
        assert 'kraken' in exchanges
        assert 'kucoin' in exchanges
        assert 'okx' in exchanges

# ============================================================
# EXCHANGE MANAGER TESTS
# ============================================================

class TestExchangeManager:
    """Tests pour le gestionnaire d'exchanges"""

    @pytest.fixture
    def exchange_manager(self):
        """Fixture pour le gestionnaire d'exchanges"""
        return ExchangeManager()

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        return MockExchange("Test Exchange")

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

    def test_get_exchange(self, exchange_manager, mock_exchange):
        """Test la récupération d'un exchange"""
        exchange_manager.add_exchange(mock_exchange)
        exchange = exchange_manager.get_exchange("Test Exchange")
        assert exchange is not None
        assert exchange.name == "Test Exchange"

    def test_get_all_balances(self, exchange_manager, mock_exchange):
        """Test la récupération de tous les soldes"""
        exchange_manager.add_exchange(mock_exchange)
        balances = exchange_manager.get_all_balances()
        assert len(balances) > 0
        assert 'USDT' in balances

    def test_get_all_prices(self, exchange_manager, mock_exchange):
        """Test la récupération de tous les prix"""
        exchange_manager.add_exchange(mock_exchange)
        prices = exchange_manager.get_all_prices()
        assert len(prices) > 0
        assert 'BTC/USDT' in prices

    def test_get_all_tickers(self, exchange_manager, mock_exchange):
        """Test la récupération de tous les tickers"""
        exchange_manager.add_exchange(mock_exchange)
        tickers = exchange_manager.get_all_tickers()
        assert len(tickers) > 0
        assert 'BTC/USDT' in tickers

    def test_connect_all(self, exchange_manager, mock_exchange):
        """Test la connexion de tous les exchanges"""
        exchange_manager.add_exchange(mock_exchange)
        exchange_manager.connect_all()
        
        for exchange in exchange_manager.get_exchanges():
            assert exchange.is_connected() is True

    def test_disconnect_all(self, exchange_manager, mock_exchange):
        """Test la déconnexion de tous les exchanges"""
        exchange_manager.add_exchange(mock_exchange)
        exchange_manager.connect_all()
        exchange_manager.disconnect_all()
        
        for exchange in exchange_manager.get_exchanges():
            assert exchange.is_connected() is False

# ============================================================
# MOCK EXCHANGE TESTS
# ============================================================

class TestMockExchange:
    """Tests pour le mock exchange"""

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Mock Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, mock_exchange):
        """Test l'initialisation"""
        assert mock_exchange is not None
        assert mock_exchange.name == "Mock Exchange"
        assert mock_exchange.is_connected() is True

    def test_get_price(self, mock_exchange):
        """Test la récupération du prix"""
        price = mock_exchange.get_price('BTC/USDT')
        assert price > 0

    def test_get_ticker(self, mock_exchange):
        """Test la récupération du ticker"""
        ticker = mock_exchange.get_ticker('BTC/USDT')
        assert ticker is not None
        assert 'bid' in ticker
        assert 'ask' in ticker
        assert 'last' in ticker

    def test_get_order_book(self, mock_exchange):
        """Test la récupération du carnet d'ordres"""
        order_book = mock_exchange.get_order_book('BTC/USDT')
        assert order_book is not None
        assert 'bids' in order_book
        assert 'asks' in order_book
        assert len(order_book['bids']) > 0
        assert len(order_book['asks']) > 0

    def test_create_order(self, mock_exchange):
        """Test la création d'un ordre"""
        order = mock_exchange.create_order(
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

    def test_cancel_order(self, mock_exchange):
        """Test l'annulation d'un ordre"""
        # Créer un ordre
        order = mock_exchange.create_order(
            symbol='BTC/USDT',
            side='BUY',
            order_type='LIMIT',
            quantity=0.5,
            price=45000.0
        )
        
        # Annuler l'ordre
        result = mock_exchange.cancel_order(order['id'])
        assert result is True

    def test_get_balance(self, mock_exchange):
        """Test la récupération du solde"""
        balance = mock_exchange.get_balance()
        assert balance is not None
        assert 'USDT' in balance

    def test_get_orders(self, mock_exchange):
        """Test la récupération des ordres"""
        # Créer quelques ordres
        for i in range(3):
            mock_exchange.create_order(
                symbol='BTC/USDT',
                side='BUY' if i % 2 == 0 else 'SELL',
                order_type='LIMIT',
                quantity=0.5 + i * 0.1,
                price=45000.0 + i * 100
            )
        
        orders = mock_exchange.get_orders()
        assert len(orders) >= 3

    def test_get_trades(self, mock_exchange):
        """Test la récupération des trades"""
        trades = mock_exchange.get_trades('BTC/USDT')
        assert trades is not None

# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestExchangeIntegration:
    """Tests d'intégration des exchanges"""

    def test_multiple_exchanges(self):
        """Test l'utilisation de plusieurs exchanges"""
        # Créer plusieurs mock exchanges
        exchange1 = MockExchange("Exchange 1")
        exchange2 = MockExchange("Exchange 2")
        exchange1.start_market()
        exchange2.start_market()
        
        try:
            # Vérifier les prix
            price1 = exchange1.get_price('BTC/USDT')
            price2 = exchange2.get_price('BTC/USDT')
            
            # Les prix peuvent être différents
            assert price1 > 0
            assert price2 > 0
            
            # Les tickers
            ticker1 = exchange1.get_ticker('BTC/USDT')
            ticker2 = exchange2.get_ticker('BTC/USDT')
            
            assert ticker1 is not None
            assert ticker2 is not None
            
        finally:
            exchange1.stop_market()
            exchange2.stop_market()

    def test_exchange_manager_with_mock(self):
        """Test le gestionnaire d'exchanges avec des mock exchanges"""
        manager = ExchangeManager()
        
        # Créer des mock exchanges
        exchange1 = MockExchange("Mock 1")
        exchange2 = MockExchange("Mock 2")
        exchange1.start_market()
        exchange2.start_market()
        
        try:
            # Ajouter les exchanges
            manager.add_exchange(exchange1)
            manager.add_exchange(exchange2)
            
            # Vérifier les soldes
            balances = manager.get_all_balances()
            assert len(balances) > 0
            
            # Vérifier les prix
            prices = manager.get_all_prices()
            assert len(prices) > 0
            
            # Vérifier les tickers
            tickers = manager.get_all_tickers()
            assert len(tickers) > 0
            
        finally:
            exchange1.stop_market()
            exchange2.stop_market()

    @pytest.mark.asyncio
    async def test_async_exchange_operations(self):
        """Test les opérations asynchrones sur les exchanges"""
        exchange = MockExchange("Async Exchange")
        exchange.start_market()
        
        try:
            # Récupération asynchrone du prix
            price = await exchange.async_get_price('BTC/USDT')
            assert price > 0
            
            # Récupération asynchrone du ticker
            ticker = await exchange.async_get_ticker('BTC/USDT')
            assert ticker is not None
            
            # Création asynchrone d'un ordre
            order = await exchange.async_create_order(
                symbol='BTC/USDT',
                side='BUY',
                order_type='LIMIT',
                quantity=0.5,
                price=45000.0
            )
            assert order is not None
            
        finally:
            exchange.stop_market()

# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestExchangePerformance:
    """Tests de performance des exchanges"""

    def test_price_fetch_performance(self):
        """Test la performance de récupération des prix"""
        import time
        
        exchange = MockExchange("Performance Exchange")
        exchange.start_market()
        
        try:
            # Mesurer le temps de récupération
            start_time = time.time()
            
            for _ in range(100):
                price = exchange.get_price('BTC/USDT')
                assert price > 0
            
            end_time = time.time()
            avg_time = (end_time - start_time) / 100 * 1000  # ms
            
            # Moins de 10ms par récupération en moyenne
            assert avg_time < 10
            
        finally:
            exchange.stop_market()

    def test_order_creation_performance(self):
        """Test la performance de création d'ordres"""
        import time
        
        exchange = MockExchange("Performance Exchange")
        exchange.start_market()
        
        try:
            # Mesurer le temps de création
            start_time = time.time()
            
            for i in range(100):
                order = exchange.create_order(
                    symbol='BTC/USDT',
                    side='BUY' if i % 2 == 0 else 'SELL',
                    order_type='LIMIT',
                    quantity=0.5,
                    price=45000.0 + i
                )
                assert order is not None
            
            end_time = time.time()
            avg_time = (end_time - start_time) / 100 * 1000  # ms
            
            # Moins de 5ms par création en moyenne
            assert avg_time < 5
            
        finally:
            exchange.stop_market()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

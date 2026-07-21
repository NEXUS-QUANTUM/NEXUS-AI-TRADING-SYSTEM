"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Detectors Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests des détecteurs d'opportunités pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import asyncio
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock

# Import du module à tester
from trading.bots.arbitrage_bot.detectors.base_detector import BaseDetector
from trading.bots.arbitrage_bot.detectors.cross_exchange_detector import CrossExchangeDetector
from trading.bots.arbitrage_bot.detectors.triangular_detector import TriangularDetector
from trading.bots.arbitrage_bot.detectors.statistical_detector import StatisticalDetector
from trading.bots.arbitrage_bot.detectors.flash_loan_detector import FlashLoanDetector
from trading.bots.arbitrage_bot.detectors.cross_chain_detector import CrossChainDetector
from trading.bots.arbitrage_bot.detectors.detector_factory import DetectorFactory

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    test_data,
    test_tickers,
    test_order_books,
    test_trades,
    test_arbitrage_opportunities
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
# BASE DETECTOR TESTS
# ============================================================

class TestBaseDetector:
    """Tests pour le détecteur de base"""

    def test_initialization(self):
        """Test l'initialisation"""
        detector = BaseDetector()
        assert detector is not None
        assert detector.is_enabled() is True

    def test_enable_disable(self):
        """Test l'activation/désactivation"""
        detector = BaseDetector()
        
        detector.enable()
        assert detector.is_enabled() is True
        
        detector.disable()
        assert detector.is_enabled() is False

    def test_set_config(self):
        """Test la configuration"""
        detector = BaseDetector()
        config = {'threshold': 0.01, 'timeout': 30}
        
        detector.set_config(config)
        assert detector.get_config() == config

    def test_validate_opportunity(self):
        """Test la validation d'une opportunité"""
        detector = BaseDetector()
        
        # Opportunité valide
        opportunity = {
            'pair': 'BTC/USDT',
            'exchange_a': 'Exchange 1',
            'exchange_b': 'Exchange 2',
            'price_a': 100.0,
            'price_b': 101.0,
            'spread': 1.0,
            'profit': 0.95,
            'profit_percent': 0.0095
        }
        assert detector.validate_opportunity(opportunity) is True
        
        # Opportunité invalide
        invalid = {'pair': 'BTC/USDT', 'price_a': 100.0}
        assert detector.validate_opportunity(invalid) is False

# ============================================================
# CROSS EXCHANGE DETECTOR TESTS
# ============================================================

class TestCrossExchangeDetector:
    """Tests pour le détecteur cross-exchange"""

    @pytest.fixture
    def detector(self):
        """Fixture pour le détecteur"""
        config = {
            'min_profit': 0.001,
            'max_spread': 0.10,
            'min_volume': 10,
            'max_position': 1000
        }
        return CrossExchangeDetector(config)

    @pytest.fixture
    def mock_exchanges(self):
        """Fixture pour des mock exchanges"""
        exchange1 = MockExchange("Exchange 1")
        exchange2 = MockExchange("Exchange 2")
        exchange1.start_market()
        exchange2.start_market()
        yield [exchange1, exchange2]
        exchange1.stop_market()
        exchange2.stop_market()

    def test_initialization(self, detector):
        """Test l'initialisation"""
        assert detector is not None
        assert detector.get_type() == 'cross_exchange'

    def test_detect_opportunities(self, detector, mock_exchanges):
        """Test la détection des opportunités"""
        # Ajouter les exchanges
        for exchange in mock_exchanges:
            detector.add_exchange(exchange)
        
        # Détecter les opportunités
        opportunities = detector.detect_opportunities()
        
        assert opportunities is not None
        assert len(opportunities) > 0
        
        # Vérifier la structure des opportunités
        for opp in opportunities:
            assert 'pair' in opp
            assert 'exchange_a' in opp
            assert 'exchange_b' in opp
            assert 'price_a' in opp
            assert 'price_b' in opp
            assert 'spread' in opp
            assert 'profit' in opp
            assert 'profit_percent' in opp
            assert opp['profit'] > 0

    def test_detect_with_min_profit_threshold(self, detector, mock_exchanges):
        """Test la détection avec seuil de profit minimum"""
        for exchange in mock_exchanges:
            detector.add_exchange(exchange)
        
        # Définir un seuil très élevé
        detector.set_config({'min_profit': 0.5})  # 50%
        
        opportunities = detector.detect_opportunities()
        # Aucune opportunité ne devrait être trouvée
        assert len(opportunities) == 0

    def test_calculate_spread(self, detector):
        """Test le calcul du spread"""
        spread = detector.calculate_spread(100.0, 101.0)
        assert spread == 1.0
        
        spread = detector.calculate_spread(100.0, 99.0)
        assert spread == -1.0

    def test_calculate_profit(self, detector):
        """Test le calcul du profit"""
        profit = detector.calculate_profit(100.0, 101.0, 1.0)
        assert profit > 0
        
        profit = detector.calculate_profit(100.0, 99.0, 1.0)
        assert profit < 0

    def test_get_best_opportunities(self, detector, mock_exchanges):
        """Test la récupération des meilleures opportunités"""
        for exchange in mock_exchanges:
            detector.add_exchange(exchange)
        
        opportunities = detector.detect_opportunities()
        best = detector.get_best_opportunities(opportunities, 3)
        
        assert len(best) <= 3
        if len(best) > 1:
            # Vérifier que les opportunités sont triées par profit décroissant
            for i in range(len(best) - 1):
                assert best[i]['profit'] >= best[i+1]['profit']

    @pytest.mark.asyncio
    async def test_async_detect(self, detector, mock_exchanges):
        """Test la détection asynchrone"""
        for exchange in mock_exchanges:
            detector.add_exchange(exchange)
        
        opportunities = await detector.async_detect_opportunities()
        assert len(opportunities) > 0

# ============================================================
# TRIANGULAR DETECTOR TESTS
# ============================================================

class TestTriangularDetector:
    """Tests pour le détecteur triangulaire"""

    @pytest.fixture
    def detector(self):
        """Fixture pour le détecteur"""
        config = {
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
        return TriangularDetector(config)

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Test Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, detector):
        """Test l'initialisation"""
        assert detector is not None
        assert detector.get_type() == 'triangular'

    def test_detect_opportunities(self, detector, mock_exchange):
        """Test la détection des opportunités"""
        detector.add_exchange(mock_exchange)
        
        opportunities = detector.detect_opportunities()
        
        assert opportunities is not None
        # Les opportunités triangulaires peuvent être rares sur un seul exchange
        # avec des données simulées, donc on ne vérifie pas la longueur

    def test_calculate_triangular_profit(self, detector):
        """Test le calcul du profit triangulaire"""
        # Simuler des prix pour un cycle triangulaire
        prices = {
            'BTC/USDT': 45000.0,
            'ETH/BTC': 0.0667,  # 3000/45000
            'ETH/USDT': 3000.0
        }
        
        profit, rate = detector.calculate_triangular_profit(
            prices,
            ['BTC/USDT', 'ETH/BTC', 'ETH/USDT']
        )
        
        # Le profit devrait être proche de 0 (aucun arbitrage)
        assert abs(profit) < 0.01

    def test_calculate_triangular_arbitrage(self, detector):
        """Test le calcul de l'arbitrage triangulaire"""
        # Simuler des prix avec une opportunité d'arbitrage
        prices = {
            'BTC/USDT': 45000.0,
            'ETH/BTC': 0.0670,  # 3015/45000 (légèrement surévalué)
            'ETH/USDT': 3000.0
        }
        
        opportunity = detector.calculate_triangular_arbitrage(
            prices,
            'BTC-ETH-USDT',
            ['BTC/USDT', 'ETH/BTC', 'ETH/USDT']
        )
        
        if opportunity:
            assert opportunity['profit'] > 0

    @pytest.mark.asyncio
    async def test_async_detect(self, detector, mock_exchange):
        """Test la détection asynchrone"""
        detector.add_exchange(mock_exchange)
        
        opportunities = await detector.async_detect_opportunities()
        assert opportunities is not None

# ============================================================
# STATISTICAL DETECTOR TESTS
# ============================================================

class TestStatisticalDetector:
    """Tests pour le détecteur statistique"""

    @pytest.fixture
    def detector(self):
        """Fixture pour le détecteur"""
        config = {
            'min_profit': 0.001,
            'lookback_period': 50,
            'cointegration_confidence': 0.95,
            'z_score_threshold': 2.0,
            'half_life': 20,
            'max_position': 1000
        }
        return StatisticalDetector(config)

    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange"""
        exchange = MockExchange("Test Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()

    def test_initialization(self, detector):
        """Test l'initialisation"""
        assert detector is not None
        assert detector.get_type() == 'statistical'

    def test_calculate_cointegration(self, detector):
        """Test le calcul de la cointégration"""
        # Créer deux séries corrélées
        np.random.seed(42)
        x = np.cumsum(np.random.randn(100))
        y = 0.8 * x + 0.2 * np.cumsum(np.random.randn(100))
        
        cointegration = detector.calculate_cointegration(x, y)
        assert 'cointegrated' in cointegration
        assert 'confidence' in cointegration
        assert 'hedge_ratio' in cointegration

    def test_calculate_z_score(self, detector):
        """Test le calcul du z-score"""
        # Créer des données avec une moyenne connue
        data = np.random.normal(0, 1, 100)
        z_scores = detector.calculate_z_score(data)
        
        assert len(z_scores) == len(data)
        assert abs(np.mean(z_scores)) < 0.5

    def test_detect_statistical_opportunity(self, detector, mock_exchange):
        """Test la détection d'opportunité statistique"""
        detector.add_exchange(mock_exchange)
        
        # Obtenir des données historiques
        klines1 = mock_exchange.get_klines('BTC/USDT', '1m', 100)
        klines2 = mock_exchange.get_klines('ETH/USDT', '1m', 100)
        
        prices1 = [k.close for k in klines1]
        prices2 = [k.close for k in klines2]
        
        opportunity = detector.detect_opportunity('BTC/USDT', 'ETH/USDT', prices1, prices2)
        
        if opportunity:
            assert opportunity['type'] == 'statistical'
            assert 'hedge_ratio' in opportunity
            assert 'z_score' in opportunity

    @pytest.mark.asyncio
    async def test_async_detect(self, detector, mock_exchange):
        """Test la détection asynchrone"""
        detector.add_exchange(mock_exchange)
        
        opportunities = await detector.async_detect_opportunities()
        assert opportunities is not None

# ============================================================
# FLASH LOAN DETECTOR TESTS
# ============================================================

class TestFlashLoanDetector:
    """Tests pour le détecteur de flash loan"""

    @pytest.fixture
    def detector(self):
        """Fixture pour le détecteur"""
        config = {
            'min_profit': 0.02,
            'max_loan_size': 1000000,
            'gas_limit': 1000000,
            'max_gas_price': 200,
            'platforms': ['aave', 'dydx', 'uniswap']
        }
        return FlashLoanDetector(config)

    def test_initialization(self, detector):
        """Test l'initialisation"""
        assert detector is not None
        assert detector.get_type() == 'flash_loan'

    def test_calculate_gas_cost(self, detector):
        """Test le calcul du coût en gas"""
        gas_cost = detector.calculate_gas_cost(100000, 100)
        assert gas_cost > 0
        
        gas_cost = detector.calculate_gas_cost(500000, 200)
        assert gas_cost > 0

    def test_validate_flash_loan(self, detector):
        """Test la validation d'un flash loan"""
        # Flash loan valide
        valid = {
            'pair': 'WETH/USDT',
            'amount': 100000,
            'profit': 3000,
            'gas_cost': 500
        }
        assert detector.validate_flash_loan(valid) is True
        
        # Flash loan invalide (profit trop faible)
        invalid = {
            'pair': 'WETH/USDT',
            'amount': 100000,
            'profit': 100,
            'gas_cost': 500
        }
        assert detector.validate_flash_loan(invalid) is False

    def test_calculate_profit_after_gas(self, detector):
        """Test le calcul du profit après gas"""
        profit = detector.calculate_profit_after_gas(3000, 500)
        assert profit == 2500
        
        profit = detector.calculate_profit_after_gas(1000, 1500)
        assert profit < 0

# ============================================================
# CROSS CHAIN DETECTOR TESTS
# ============================================================

class TestCrossChainDetector:
    """Tests pour le détecteur cross-chain"""

    @pytest.fixture
    def detector(self):
        """Fixture pour le détecteur"""
        config = {
            'min_profit': 0.015,
            'max_position': 100000,
            'bridge_timeout': 120,
            'bridges': ['anycall', 'wormhole', 'multichain']
        }
        return CrossChainDetector(config)

    def test_initialization(self, detector):
        """Test l'initialisation"""
        assert detector is not None
        assert detector.get_type() == 'cross_chain'

    def test_calculate_bridge_fee(self, detector):
        """Test le calcul des frais de bridge"""
        fee = detector.calculate_bridge_fee(10000, 'wormhole')
        assert fee > 0
        
        fee = detector.calculate_bridge_fee(50000, 'anycall')
        assert fee > 0

    def test_validate_bridge_transfer(self, detector):
        """Test la validation d'un transfert bridge"""
        # Transfert valide
        valid = {
            'from_chain': 'ethereum',
            'to_chain': 'polygon',
            'amount': 10000,
            'bridge': 'wormhole'
        }
        assert detector.validate_bridge_transfer(valid) is True
        
        # Transfert invalide (montant trop élevé)
        invalid = {
            'from_chain': 'ethereum',
            'to_chain': 'polygon',
            'amount': 200000,
            'bridge': 'wormhole'
        }
        assert detector.validate_bridge_transfer(invalid) is False

# ============================================================
# DETECTOR FACTORY TESTS
# ============================================================

class TestDetectorFactory:
    """Tests pour la fabrique de détecteurs"""

    def test_create_detector(self):
        """Test la création d'un détecteur"""
        # Créer un détecteur cross-exchange
        detector = DetectorFactory.create_detector('cross_exchange')
        assert detector is not None
        assert detector.get_type() == 'cross_exchange'
        
        # Créer un détecteur triangulaire
        detector = DetectorFactory.create_detector('triangular')
        assert detector is not None
        assert detector.get_type() == 'triangular'
        
        # Créer un détecteur statistique
        detector = DetectorFactory.create_detector('statistical')
        assert detector is not None
        assert detector.get_type() == 'statistical'
        
        # Créer un détecteur flash loan
        detector = DetectorFactory.create_detector('flash_loan')
        assert detector is not None
        assert detector.get_type() == 'flash_loan'

    def test_create_with_config(self):
        """Test la création avec configuration"""
        config = {'min_profit': 0.005, 'max_spread': 0.15}
        detector = DetectorFactory.create_detector('cross_exchange', config)
        assert detector is not None
        assert detector.get_config()['min_profit'] == 0.005

    def test_invalid_detector_type(self):
        """Test la création d'un type invalide"""
        with pytest.raises(ValueError):
            DetectorFactory.create_detector('invalid_type')

    def test_register_detector(self):
        """Test l'enregistrement d'un détecteur"""
        class CustomDetector(BaseDetector):
            def get_type(self):
                return 'custom'
            
            def detect_opportunities(self):
                return []
        
        DetectorFactory.register_detector('custom', CustomDetector)
        detector = DetectorFactory.create_detector('custom')
        assert detector is not None
        assert detector.get_type() == 'custom'

    def test_get_available_detectors(self):
        """Test la récupération des détecteurs disponibles"""
        detectors = DetectorFactory.get_available_detectors()
        assert 'cross_exchange' in detectors
        assert 'triangular' in detectors
        assert 'statistical' in detectors
        assert 'flash_loan' in detectors
        assert 'cross_chain' in detectors

# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestDetectorIntegration:
    """Tests d'intégration des détecteurs"""

    def test_multiple_detectors(self, mock_exchanges):
        """Test l'utilisation de plusieurs détecteurs"""
        # Créer les détecteurs
        detectors = {
            'cross_exchange': DetectorFactory.create_detector('cross_exchange'),
            'triangular': DetectorFactory.create_detector('triangular'),
            'statistical': DetectorFactory.create_detector('statistical')
        }
        
        # Ajouter les exchanges
        for exchange in mock_exchanges:
            for detector in detectors.values():
                detector.add_exchange(exchange)
        
        # Détecter les opportunités
        all_opportunities = []
        for name, detector in detectors.items():
            opportunities = detector.detect_opportunities()
            all_opportunities.extend(opportunities)
            logger.info(f"{name}: {len(opportunities)} opportunities")
        
        # Vérifier qu'au moins un détecteur trouve des opportunités
        assert len(all_opportunities) > 0

    @pytest.mark.asyncio
    async def test_async_multiple_detectors(self, mock_exchanges):
        """Test l'utilisation asynchrone de plusieurs détecteurs"""
        detectors = {
            'cross_exchange': DetectorFactory.create_detector('cross_exchange'),
            'triangular': DetectorFactory.create_detector('triangular'),
            'statistical': DetectorFactory.create_detector('statistical')
        }
        
        for exchange in mock_exchanges:
            for detector in detectors.values():
                detector.add_exchange(exchange)
        
        # Détecter les opportunités en parallèle
        tasks = []
        for detector in detectors.values():
            tasks.append(detector.async_detect_opportunities())
        
        results = await asyncio.gather(*tasks)
        
        total_opportunities = sum(len(r) for r in results)
        assert total_opportunities > 0

    def test_detector_priority(self, mock_exchanges):
        """Test la priorité des détecteurs"""
        # Créer les détecteurs avec différentes priorités
        detector1 = DetectorFactory.create_detector('cross_exchange')
        detector2 = DetectorFactory.create_detector('triangular')
        detector3 = DetectorFactory.create_detector('statistical')
        
        # Ajouter les exchanges
        for exchange in mock_exchanges:
            detector1.add_exchange(exchange)
            detector2.add_exchange(exchange)
            detector3.add_exchange(exchange)
        
        # Détecter les opportunités
        opportunities1 = detector1.detect_opportunities()
        opportunities2 = detector2.detect_opportunities()
        opportunities3 = detector3.detect_opportunities()
        
        # Les détecteurs cross-exchange devraient trouver plus d'opportunités
        # que les détecteurs statistiques dans des données simulées
        assert len(opportunities1) >= len(opportunities3)

# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestDetectorPerformance:
    """Tests de performance des détecteurs"""

    def test_detection_performance(self, mock_exchanges):
        """Test la performance de détection"""
        import time
        
        detector = DetectorFactory.create_detector('cross_exchange')
        for exchange in mock_exchanges:
            detector.add_exchange(exchange)
        
        # Mesurer le temps de détection
        start_time = time.time()
        opportunities = detector.detect_opportunities()
        end_time = time.time()
        
        detection_time = end_time - start_time
        assert detection_time < 1.0  # Moins d'1 seconde
        
        logger.info(f"Detection time: {detection_time:.3f}s for {len(opportunities)} opportunities")

    def test_memory_usage(self, mock_exchanges):
        """Test l'utilisation mémoire"""
        import psutil
        
        detector = DetectorFactory.create_detector('cross_exchange')
        for exchange in mock_exchanges:
            detector.add_exchange(exchange)
        
        # Mesurer la mémoire avant
        memory_before = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Détecter les opportunités
        opportunities = detector.detect_opportunities()
        
        # Mesurer la mémoire après
        memory_after = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        memory_used = memory_after - memory_before
        assert memory_used < 100  # Moins de 100MB
        
        logger.info(f"Memory usage: {memory_used:.1f}MB for {len(opportunities)} opportunities")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

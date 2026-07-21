"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Performance Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests de performance et d'optimisation pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import asyncio
import time
import json
import psutil
import gc
import tracemalloc
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import cProfile
import pstats
import io

# Import du module à tester
from trading.bots.arbitrage_bot import ArbitrageBot
from trading.bots.arbitrage_bot.core.arbitrage_engine import ArbitrageEngine
from trading.bots.arbitrage_bot.core.exchange_manager import ExchangeManager
from trading.bots.arbitrage_bot.core.strategy_manager import StrategyManager
from trading.bots.arbitrage_bot.core.risk_manager import RiskManager
from trading.bots.arbitrage_bot.core.execution_engine import ExecutionEngine
from trading.bots.arbitrage_bot.core.market_data import MarketData
from trading.bots.arbitrage_bot.core.data_manager import DataManager

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    test_config,
    test_data,
    test_orders,
    test_trades,
    test_balances
)
from trading.bots.arbitrage_bot.tests.fixtures.exchange_mock import (
    MockExchange,
    MockExchangeFactory
)

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# PERFORMANCE BENCHMARK CLASS
# ============================================================

class PerformanceBenchmark:
    """Classe de benchmark de performance"""
    
    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
        self.start_time = None
        self.end_time = None
        
    def start(self):
        """Démarre le benchmark"""
        self.start_time = time.time()
        tracemalloc.start()
        
    def stop(self) -> Dict[str, Any]:
        """Arrête le benchmark et retourne les résultats"""
        self.end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        return {
            'duration': self.end_time - self.start_time,
            'memory_current': current / 1024 / 1024,  # MB
            'memory_peak': peak / 1024 / 1024,  # MB
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent
        }
    
    def measure(self, func, *args, **kwargs) -> Tuple[Any, Dict[str, Any]]:
        """Mesure les performances d'une fonction"""
        self.start()
        try:
            result = func(*args, **kwargs)
            stats = self.stop()
            return result, stats
        except Exception as e:
            self.stop()
            raise e

# ============================================================
# PERFORMANCE TEST FIXTURES
# ============================================================

@pytest.fixture
def performance_benchmark():
    """Fixture pour le benchmark de performance"""
    return PerformanceBenchmark()

@pytest.fixture
def performance_config():
    """Fixture pour la configuration de performance"""
    return {
        'iterations': 100,
        'concurrent_operations': 50,
        'data_points': 10000,
        'timeout': 60,
        'memory_limit': 1024 * 1024 * 1024,  # 1GB
        'cpu_limit': 80,  # 80%
        'latency_limit': 100,  # 100ms
        'throughput_limit': 1000  # ops/sec
    }

# ============================================================
# LATENCY TESTS
# ============================================================

class TestLatency:
    """Tests de latence"""

    def test_market_data_latency(self, performance_benchmark, mock_exchange):
        """Test la latence des données de marché"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        def get_data():
            price = market_data.get_price('BTC/USDT', 'Test Exchange')
            ticker = market_data.get_ticker('BTC/USDT', 'Test Exchange')
            order_book = market_data.get_order_book('BTC/USDT', 'Test Exchange')
            return price, ticker, order_book
        
        # Mesurer la latence
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            get_data()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
        
        logger.info(f"Market Data Latency - Avg: {avg_latency:.2f}ms, P95: {p95_latency:.2f}ms, P99: {p99_latency:.2f}ms")
        
        assert avg_latency < 10  # Moins de 10ms en moyenne
        assert p95_latency < 50  # Moins de 50ms pour 95%

    def test_order_execution_latency(self, performance_benchmark, mock_exchange):
        """Test la latence d'exécution des ordres"""
        execution_engine = ExecutionEngine()
        execution_engine.add_exchange(mock_exchange)
        
        order = {
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': 0.1
        }
        
        # Mesurer la latence d'exécution
        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            result = execution_engine.execute_order(order)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms
            assert result['status'] == 'FILLED'
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        logger.info(f"Order Execution Latency - Avg: {avg_latency:.2f}ms, P95: {p95_latency:.2f}ms")
        
        assert avg_latency < 20  # Moins de 20ms en moyenne
        assert p95_latency < 100  # Moins de 100ms pour 95%

    def test_strategy_execution_latency(self, performance_benchmark, mock_exchange):
        """Test la latence d'exécution des stratégies"""
        strategy_manager = StrategyManager()
        strategy_manager.add_exchange(mock_exchange)
        
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
        
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        data = market_data.get_all_data()
        
        # Mesurer la latence de la stratégie
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            results = strategy_manager.execute_strategy(strategy, data)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms
        
        avg_latency = sum(latencies) / len(latencies)
        
        logger.info(f"Strategy Execution Latency - Avg: {avg_latency:.2f}ms")
        
        assert avg_latency < 50  # Moins de 50ms en moyenne

# ============================================================
# THROUGHPUT TESTS
# ============================================================

class TestThroughput:
    """Tests de débit"""

    def test_market_data_throughput(self, performance_benchmark, mock_exchange):
        """Test le débit des données de marché"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        def get_data():
            return market_data.get_price('BTC/USDT', 'Test Exchange')
        
        # Mesurer le débit
        start = time.perf_counter()
        count = 0
        while time.perf_counter() - start < 1.0:
            get_data()
            count += 1
        
        throughput = count / 1.0  # ops/sec
        
        logger.info(f"Market Data Throughput: {throughput:.0f} ops/sec")
        
        assert throughput > 100  # Plus de 100 opérations par seconde

    def test_order_execution_throughput(self, performance_benchmark, mock_exchange):
        """Test le débit d'exécution des ordres"""
        execution_engine = ExecutionEngine()
        execution_engine.add_exchange(mock_exchange)
        
        def execute_order():
            order = {
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'type': 'MARKET',
                'quantity': 0.01
            }
            return execution_engine.execute_order(order)
        
        # Mesurer le débit
        start = time.perf_counter()
        count = 0
        while time.perf_counter() - start < 1.0:
            execute_order()
            count += 1
        
        throughput = count / 1.0  # ops/sec
        
        logger.info(f"Order Execution Throughput: {throughput:.0f} ops/sec")
        
        assert throughput > 50  # Plus de 50 opérations par seconde

    def test_arbitrage_scan_throughput(self, performance_benchmark, mock_exchange):
        """Test le débit de scan d'arbitrage"""
        engine = ArbitrageEngine()
        engine.add_exchange(mock_exchange)
        
        # Mesurer le débit de scan
        start = time.perf_counter()
        count = 0
        while time.perf_counter() - start < 1.0:
            opportunities = engine.scan_opportunities()
            count += 1
        
        throughput = count / 1.0  # ops/sec
        
        logger.info(f"Arbitrage Scan Throughput: {throughput:.0f} scans/sec")
        
        assert throughput > 10  # Plus de 10 scans par seconde

# ============================================================
# MEMORY TESTS
# ============================================================

class TestMemory:
    """Tests de mémoire"""

    def test_memory_usage_under_load(self, performance_benchmark, mock_exchange):
        """Test l'utilisation mémoire sous charge"""
        import tracemalloc
        tracemalloc.start()
        
        # Créer de nombreux objets
        objects = []
        for i in range(10000):
            objects.append({
                'id': i,
                'data': 'x' * 100,
                'timestamp': datetime.now().isoformat()
            })
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        memory_mb = current / 1024 / 1024
        peak_mb = peak / 1024 / 1024
        
        logger.info(f"Memory Usage - Current: {memory_mb:.2f}MB, Peak: {peak_mb:.2f}MB")
        
        assert memory_mb < 100  # Moins de 100MB
        assert peak_mb < 200  # Moins de 200MB de pic

    def test_memory_leak_detection(self, performance_benchmark):
        """Test la détection de fuites mémoire"""
        import tracemalloc
        tracemalloc.start()
        
        # Effectuer des opérations répétées
        for i in range(1000):
            data = {
                'id': i,
                'timestamp': datetime.now().isoformat(),
                'data': 'x' * 1000
            }
            # Simuler un traitement
            processed = json.dumps(data)
            json.loads(processed)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        memory_increase = current / 1024 / 1024
        
        logger.info(f"Memory Increase: {memory_increase:.2f}MB")
        
        assert memory_increase < 50  # Moins de 50MB d'augmentation

    def test_cache_memory_efficiency(self, performance_benchmark):
        """Test l'efficacité mémoire du cache"""
        from trading.bots.arbitrage_bot.core.cache_manager import CacheManager
        
        cache = CacheManager(max_size=1000)
        
        # Remplir le cache
        for i in range(2000):
            cache.set(f'key_{i}', {'data': 'x' * 1000, 'index': i})
        
        # Vérifier la taille du cache
        size = cache.get_size()
        memory_usage = cache.get_memory_usage()
        
        logger.info(f"Cache Size: {size}, Memory Usage: {memory_usage:.2f}MB")
        
        assert size <= 1000  # Ne devrait pas dépasser la taille maximale
        assert memory_usage < 50  # Moins de 50MB

# ============================================================
# CPU TESTS
# ============================================================

class TestCPU:
    """Tests de CPU"""

    def test_cpu_usage_under_load(self, performance_benchmark):
        """Test l'utilisation CPU sous charge"""
        import time
        
        # Effectuer des opérations CPU-intensives
        def cpu_intensive_task():
            result = 0
            for i in range(1000000):
                result += i * i
            return result
        
        start_time = time.time()
        
        # Exécuter en parallèle
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(cpu_intensive_task) for _ in range(4)]
            results = [f.result() for f in futures]
        
        end_time = time.time()
        duration = end_time - start_time
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        logger.info(f"CPU Usage: {cpu_percent}%, Duration: {duration:.2f}s")
        
        assert cpu_percent < 80  # Moins de 80% d'utilisation

    def test_concurrent_operation_efficiency(self, performance_benchmark, mock_exchange):
        """Test l'efficacité des opérations concurrentes"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        def get_data():
            return market_data.get_price('BTC/USDT', 'Test Exchange')
        
        # Mesurer l'efficacité avec différents nombres de threads
        results = {}
        for workers in [1, 2, 4, 8]:
            start = time.perf_counter()
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(get_data) for _ in range(100)]
                results_list = [f.result() for f in futures]
            
            end = time.perf_counter()
            duration = end - start
            throughput = 100 / duration
            
            results[workers] = {
                'duration': duration,
                'throughput': throughput
            }
            
            logger.info(f"Workers: {workers}, Duration: {duration:.3f}s, Throughput: {throughput:.0f} ops/sec")
        
        # Vérifier que l'augmentation du nombre de workers améliore le débit
        assert results[8]['throughput'] > results[1]['throughput']

# ============================================================
# OPTIMIZATION TESTS
# ============================================================

class TestOptimization:
    """Tests d'optimisation"""

    def test_caching_optimization(self, performance_benchmark, mock_exchange):
        """Test l'optimisation du cache"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        # Sans cache
        start = time.perf_counter()
        for _ in range(100):
            price = market_data.get_price('BTC/USDT', 'Test Exchange')
        end = time.perf_counter()
        without_cache = end - start
        
        # Avec cache
        market_data.enable_cache()
        start = time.perf_counter()
        for _ in range(100):
            price = market_data.get_price('BTC/USDT', 'Test Exchange')
        end = time.perf_counter()
        with_cache = end - start
        
        improvement = ((without_cache - with_cache) / without_cache) * 100
        
        logger.info(f"Cache Optimization - Without: {without_cache:.3f}s, With: {with_cache:.3f}s, Improvement: {improvement:.1f}%")
        
        assert improvement > 50  # Amélioration de plus de 50%

    def test_batch_processing_optimization(self, performance_benchmark, mock_exchange):
        """Test l'optimisation du traitement par lots"""
        execution_engine = ExecutionEngine()
        execution_engine.add_exchange(mock_exchange)
        
        orders = [
            {
                'symbol': 'BTC/USDT',
                'side': 'BUY' if i % 2 == 0 else 'SELL',
                'type': 'MARKET',
                'quantity': 0.01
            }
            for i in range(100)
        ]
        
        # Sans batch
        start = time.perf_counter()
        for order in orders:
            execution_engine.execute_order(order)
        end = time.perf_counter()
        without_batch = end - start
        
        # Avec batch
        execution_engine.enable_batch_processing()
        start = time.perf_counter()
        execution_engine.execute_batch(orders)
        end = time.perf_counter()
        with_batch = end - start
        
        improvement = ((without_batch - with_batch) / without_batch) * 100
        
        logger.info(f"Batch Processing Optimization - Without: {without_batch:.3f}s, With: {with_batch:.3f}s, Improvement: {improvement:.1f}%")
        
        assert improvement > 30  # Amélioration de plus de 30%

    def test_connection_pool_optimization(self, performance_benchmark):
        """Test l'optimisation du pool de connexions"""
        from trading.bots.arbitrage_bot.core.connection_pool import ConnectionPool
        
        pool = ConnectionPool(max_size=10)
        
        # Sans pool
        start = time.perf_counter()
        for _ in range(100):
            conn = pool.create_connection()
            conn.execute("SELECT 1")
            conn.close()
        end = time.perf_counter()
        without_pool = end - start
        
        # Avec pool
        pool.start()
        start = time.perf_counter()
        for _ in range(100):
            conn = pool.get_connection()
            conn.execute("SELECT 1")
            pool.release_connection(conn)
        end = time.perf_counter()
        with_pool = end - start
        
        improvement = ((without_pool - with_pool) / without_pool) * 100
        
        logger.info(f"Connection Pool Optimization - Without: {without_pool:.3f}s, With: {with_pool:.3f}s, Improvement: {improvement:.1f}%")
        
        assert improvement > 40  # Amélioration de plus de 40%

# ============================================================
# SCALABILITY TESTS
# ============================================================

class TestScalability:
    """Tests de scalabilité"""

    def test_scalability_with_exchanges(self, performance_benchmark):
        """Test la scalabilité avec le nombre d'exchanges"""
        def create_exchange_count(count):
            exchanges = []
            for i in range(count):
                exchange = MockExchange(f"Exchange_{i}")
                exchange.start_market()
                exchanges.append(exchange)
            return exchanges
        
        def test_with_exchanges(count):
            exchanges = create_exchange_count(count)
            engine = ArbitrageEngine()
            for exchange in exchanges:
                engine.add_exchange(exchange)
            
            start = time.perf_counter()
            opportunities = engine.scan_opportunities()
            end = time.perf_counter()
            
            for exchange in exchanges:
                exchange.stop_market()
            
            return end - start, len(opportunities)
        
        # Tester avec différents nombres d'exchanges
        results = {}
        for count in [1, 2, 4, 8]:
            duration, opp_count = test_with_exchanges(count)
            results[count] = {
                'duration': duration,
                'opportunities': opp_count,
                'ops_per_second': 1 / duration if duration > 0 else 0
            }
            logger.info(f"Exchanges: {count}, Duration: {duration:.3f}s, Opportunities: {opp_count}")
        
        # Vérifier la scalabilité
        for count in [2, 4, 8]:
            ratio = results[count]['duration'] / results[1]['duration']
            expected_ratio = count  # Devrait augmenter linéairement
            
            # Tolérance de 50%
            assert ratio < expected_ratio * 1.5

    def test_scalability_with_data_volume(self, performance_benchmark):
        """Test la scalabilité avec le volume de données"""
        from trading.bots.arbitrage_bot.core.data_processor import DataProcessor
        
        processor = DataProcessor()
        
        def test_with_data_size(size):
            data = [
                {
                    'symbol': f'ASSET_{i % 10}',
                    'price': 100 + i,
                    'volume': i * 10,
                    'timestamp': datetime.now().isoformat()
                }
                for i in range(size)
            ]
            
            start = time.perf_counter()
            processed = processor.process_data(data)
            end = time.perf_counter()
            
            return end - start, len(processed)
        
        # Tester avec différentes tailles de données
        results = {}
        for size in [1000, 5000, 10000, 50000]:
            duration, processed_count = test_with_data_size(size)
            results[size] = {
                'duration': duration,
                'processed': processed_count,
                'items_per_second': processed_count / duration if duration > 0 else 0
            }
            logger.info(f"Data Size: {size}, Duration: {duration:.3f}s, Processed: {processed_count}")
        
        # Vérifier la scalabilité
        for size in [5000, 10000, 50000]:
            ratio = results[size]['duration'] / results[1000]['duration']
            expected_ratio = size / 1000
            
            # Tolérance de 50%
            assert ratio < expected_ratio * 1.5

# ============================================================
# PROFILE TESTS
# ============================================================

class TestProfiling:
    """Tests de profiling"""

    def test_cpu_profiling(self, performance_benchmark):
        """Test le profiling CPU"""
        import cProfile
        import pstats
        import io
        
        def test_function():
            result = 0
            for i in range(10000):
                result += i * i
                if i % 1000 == 0:
                    time.sleep(0.001)
            return result
        
        # Profiler la fonction
        profiler = cProfile.Profile()
        profiler.enable()
        
        for _ in range(10):
            test_function()
        
        profiler.disable()
        
        # Analyser les résultats
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats('cumtime')
        stats.print_stats(10)
        
        output = stream.getvalue()
        logger.info(f"CPU Profile:\n{output}")
        
        assert 'test_function' in output

    def test_memory_profiling(self, performance_benchmark):
        """Test le profiling mémoire"""
        import tracemalloc
        
        def memory_intensive_function():
            data = []
            for i in range(1000):
                data.append({
                    'id': i,
                    'data': 'x' * 1000,
                    'timestamp': datetime.now().isoformat()
                })
            return data
        
        tracemalloc.start()
        
        # Exécuter la fonction plusieurs fois
        for _ in range(10):
            memory_intensive_function()
        
        # Analyser la mémoire
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        tracemalloc.stop()
        
        # Vérifier que la mémoire est correctement gérée
        total_memory = sum(stat.size for stat in top_stats[:10])
        memory_mb = total_memory / 1024 / 1024
        
        logger.info(f"Memory Profile - Top 10: {memory_mb:.2f}MB")
        
        assert memory_mb < 100  # Moins de 100MB

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

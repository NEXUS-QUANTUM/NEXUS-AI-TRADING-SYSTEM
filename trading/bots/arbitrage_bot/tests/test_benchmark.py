"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Benchmark Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests de performance et benchmark pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import asyncio
import time
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import psutil
import gc

# Import du module à tester
from trading.bots.arbitrage_bot import ArbitrageBot
from trading.bots.arbitrage_bot.core.arbitrage_engine import ArbitrageEngine
from trading.bots.arbitrage_bot.core.exchange_manager import ExchangeManager
from trading.bots.arbitrage_bot.core.strategy_manager import StrategyManager
from trading.bots.arbitrage_bot.core.risk_manager import RiskManager
from trading.bots.arbitrage_bot.core.execution_engine import ExecutionEngine
from trading.bots.arbitrage_bot.core.market_data import MarketData
from trading.bots.arbitrage_bot.tests.fixtures.exchange_mock import MockExchange, MockExchangeFactory

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# BENCHMARK CONFIGURATION
# ============================================================

BENCHMARK_CONFIG = {
    'iterations': 100,
    'warmup_iterations': 10,
    'concurrent_operations': 50,
    'data_points': 1000,
    'timeout': 60,
    'memory_threshold': 1024 * 1024 * 1024,  # 1GB
    'cpu_threshold': 80,  # 80%
    'latency_threshold': 100,  # 100ms
}

# ============================================================
# BENCHMARK RESULTS
# ============================================================

class BenchmarkResult:
    """Résultats de benchmark"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = 0
        self.iterations = 0
        self.success_count = 0
        self.failure_count = 0
        self.timings: List[float] = []
        self.memory_usage: List[float] = []
        self.cpu_usage: List[float] = []
        self.errors: List[str] = []
        
    def start(self):
        self.start_time = time.time()
        
    def stop(self):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        
    def add_timing(self, timing: float):
        self.timings.append(timing)
        self.iterations += 1
        
    def add_success(self):
        self.success_count += 1
        
    def add_failure(self, error: str = None):
        self.failure_count += 1
        if error:
            self.errors.append(error)
            
    def add_memory_usage(self, memory: float):
        self.memory_usage.append(memory)
        
    def add_cpu_usage(self, cpu: float):
        self.cpu_usage.append(cpu)
        
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        if not self.timings:
            return {
                'name': self.name,
                'duration': self.duration,
                'iterations': self.iterations,
                'success_count': self.success_count,
                'failure_count': self.failure_count,
                'success_rate': 0,
                'avg_latency': 0,
                'min_latency': 0,
                'max_latency': 0,
                'p50_latency': 0,
                'p95_latency': 0,
                'p99_latency': 0,
                'avg_memory': 0,
                'avg_cpu': 0,
                'errors': self.errors
            }
            
        sorted_timings = sorted(self.timings)
        
        return {
            'name': self.name,
            'duration': self.duration,
            'iterations': self.iterations,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': self.success_count / self.iterations if self.iterations > 0 else 0,
            'avg_latency': statistics.mean(self.timings),
            'min_latency': min(self.timings),
            'max_latency': max(self.timings),
            'p50_latency': sorted_timings[int(len(sorted_timings) * 0.50)],
            'p95_latency': sorted_timings[int(len(sorted_timings) * 0.95)],
            'p99_latency': sorted_timings[int(len(sorted_timings) * 0.99)],
            'avg_memory': statistics.mean(self.memory_usage) if self.memory_usage else 0,
            'avg_cpu': statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
            'errors': self.errors
        }

# ============================================================
# BENCHMARK SUITE
# ============================================================

class BenchmarkSuite:
    """Suite de benchmarks"""
    
    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.config = BENCHMARK_CONFIG
        
    def run_benchmark(self, name: str, func, *args, **kwargs) -> BenchmarkResult:
        """Exécute un benchmark"""
        result = BenchmarkResult(name)
        
        # Warmup
        for _ in range(self.config['warmup_iterations']):
            try:
                func(*args, **kwargs)
            except Exception:
                pass
        
        # Benchmark
        result.start()
        
        for i in range(self.config['iterations']):
            try:
                # Mesurer les performances système
                memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                cpu = psutil.cpu_percent(interval=0.1)
                
                start_time = time.time()
                func(*args, **kwargs)
                end_time = time.time()
                
                timing = (end_time - start_time) * 1000  # ms
                
                result.add_timing(timing)
                result.add_success()
                result.add_memory_usage(memory)
                result.add_cpu_usage(cpu)
                
            except Exception as e:
                result.add_failure(str(e))
        
        result.stop()
        self.results.append(result)
        
        return result
    
    async def run_async_benchmark(self, name: str, func, *args, **kwargs) -> BenchmarkResult:
        """Exécute un benchmark asynchrone"""
        result = BenchmarkResult(name)
        
        # Warmup
        for _ in range(self.config['warmup_iterations']):
            try:
                await func(*args, **kwargs)
            except Exception:
                pass
        
        # Benchmark
        result.start()
        
        for i in range(self.config['iterations']):
            try:
                memory = psutil.Process().memory_info().rss / 1024 / 1024
                cpu = psutil.cpu_percent(interval=0.1)
                
                start_time = time.time()
                await func(*args, **kwargs)
                end_time = time.time()
                
                timing = (end_time - start_time) * 1000
                
                result.add_timing(timing)
                result.add_success()
                result.add_memory_usage(memory)
                result.add_cpu_usage(cpu)
                
            except Exception as e:
                result.add_failure(str(e))
        
        result.stop()
        self.results.append(result)
        
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Récupère le résumé des benchmarks"""
        summary = {
            'total_benchmarks': len(self.results),
            'total_iterations': sum(r.iterations for r in self.results),
            'total_success': sum(r.success_count for r in self.results),
            'total_failure': sum(r.failure_count for r in self.results),
            'overall_success_rate': 0,
            'results': [r.get_stats() for r in self.results]
        }
        
        total_iterations = summary['total_iterations']
        if total_iterations > 0:
            summary['overall_success_rate'] = summary['total_success'] / total_iterations
            
        return summary
    
    def print_results(self):
        """Affiche les résultats"""
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)
        
        for result in self.results:
            stats = result.get_stats()
            print(f"\n📊 {stats['name']}")
            print("-" * 40)
            print(f"  Duration:          {stats['duration']:.2f}s")
            print(f"  Iterations:        {stats['iterations']}")
            print(f"  Success Rate:      {stats['success_rate']*100:.1f}%")
            print(f"  Avg Latency:       {stats['avg_latency']:.2f}ms")
            print(f"  Min Latency:       {stats['min_latency']:.2f}ms")
            print(f"  Max Latency:       {stats['max_latency']:.2f}ms")
            print(f"  P50 Latency:       {stats['p50_latency']:.2f}ms")
            print(f"  P95 Latency:       {stats['p95_latency']:.2f}ms")
            print(f"  P99 Latency:       {stats['p99_latency']:.2f}ms")
            print(f"  Avg Memory:        {stats['avg_memory']:.1f}MB")
            print(f"  Avg CPU:           {stats['avg_cpu']:.1f}%")
            if stats['errors']:
                print(f"  Errors:            {len(stats['errors'])}")
                for error in stats['errors'][:3]:
                    print(f"    - {error[:100]}")
        
        print("\n" + "=" * 80)

# ============================================================
# BENCHMARK TESTS
# ============================================================

@pytest.mark.benchmark
class TestBenchmark:
    """Tests de benchmark"""

    @pytest.fixture
    def benchmark_suite(self):
        """Fixture pour la suite de benchmarks"""
        return BenchmarkSuite()
    
    @pytest.fixture
    def mock_exchange(self):
        """Fixture pour un mock exchange optimisé"""
        exchange = MockExchange("Benchmark Exchange")
        exchange.start_market()
        yield exchange
        exchange.stop_market()
    
    @pytest.fixture
    def arbitrage_engine(self, mock_exchange):
        """Fixture pour le moteur d'arbitrage"""
        engine = ArbitrageEngine()
        engine.add_exchange(mock_exchange)
        return engine
    
    # ============================================================
    # PERFORMANCE BENCHMARKS
    # ============================================================
    
    def test_market_data_benchmark(self, benchmark_suite, mock_exchange):
        """Benchmark des données de marché"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        def get_market_data():
            price = market_data.get_price('BTC/USDT', 'Benchmark Exchange')
            ticker = market_data.get_ticker('BTC/USDT', 'Benchmark Exchange')
            order_book = market_data.get_order_book('BTC/USDT', 'Benchmark Exchange')
            return price, ticker, order_book
        
        result = benchmark_suite.run_benchmark(
            "Market Data Operations",
            get_market_data
        )
        
        # Vérifications
        stats = result.get_stats()
        assert stats['success_rate'] > 0.95
        assert stats['avg_latency'] < BENCHMARK_CONFIG['latency_threshold']
        
    def test_arbitrage_scan_benchmark(self, benchmark_suite, arbitrage_engine):
        """Benchmark du scan d'arbitrage"""
        def scan_opportunities():
            return arbitrage_engine.scan_opportunities()
        
        result = benchmark_suite.run_benchmark(
            "Arbitrage Scan",
            scan_opportunities
        )
        
        stats = result.get_stats()
        assert stats['success_rate'] > 0.95
        assert stats['avg_latency'] < BENCHMARK_CONFIG['latency_threshold'] * 2
        
    def test_order_creation_benchmark(self, benchmark_suite, mock_exchange):
        """Benchmark de la création d'ordres"""
        execution_engine = ExecutionEngine()
        execution_engine.add_exchange(mock_exchange)
        
        def create_order():
            return execution_engine.create_order(
                symbol='BTC/USDT',
                side='BUY',
                order_type='LIMIT',
                quantity=0.5,
                price=45000.0
            )
        
        result = benchmark_suite.run_benchmark(
            "Order Creation",
            create_order
        )
        
        stats = result.get_stats()
        assert stats['success_rate'] > 0.95
        assert stats['avg_latency'] < BENCHMARK_CONFIG['latency_threshold']
        
    def test_risk_calculation_benchmark(self, benchmark_suite):
        """Benchmark des calculs de risque"""
        risk_manager = RiskManager()
        
        positions = [
            {
                'symbol': 'BTC/USDT',
                'entry_price': 45000.0 + i * 100,
                'current_price': 45000.0 + i * 150,
                'quantity': 0.5,
                'pnl': i * 50
            }
            for i in range(50)
        ]
        
        def calculate_risk():
            total_risk = 0
            for position in positions:
                risk = risk_manager.calculate_position_risk(position)
                total_risk += risk
            return total_risk
        
        result = benchmark_suite.run_benchmark(
            "Risk Calculation",
            calculate_risk
        )
        
        stats = result.get_stats()
        assert stats['success_rate'] > 0.95
        assert stats['avg_latency'] < BENCHMARK_CONFIG['latency_threshold']
        
    @pytest.mark.asyncio
    async def test_async_operations_benchmark(self, benchmark_suite, mock_exchange):
        """Benchmark des opérations asynchrones"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        async def async_get_data():
            price = await market_data.async_get_price('BTC/USDT', 'Benchmark Exchange')
            ticker = await market_data.async_get_ticker('BTC/USDT', 'Benchmark Exchange')
            return price, ticker
        
        result = await benchmark_suite.run_async_benchmark(
            "Async Market Data",
            async_get_data
        )
        
        stats = result.get_stats()
        assert stats['success_rate'] > 0.95
        assert stats['avg_latency'] < BENCHMARK_CONFIG['latency_threshold']
        
    # ============================================================
    # CONCURRENT BENCHMARKS
    # ============================================================
    
    def test_concurrent_requests_benchmark(self, benchmark_suite, mock_exchange):
        """Benchmark des requêtes concurrentes"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        def concurrent_requests():
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for _ in range(50):
                    future = executor.submit(
                        market_data.get_price,
                        'BTC/USDT',
                        'Benchmark Exchange'
                    )
                    futures.append(future)
                
                results = [f.result() for f in futures]
                return results
        
        result = benchmark_suite.run_benchmark(
            "Concurrent Requests",
            concurrent_requests
        )
        
        stats = result.get_stats()
        assert stats['success_rate'] > 0.95
        assert stats['avg_latency'] < BENCHMARK_CONFIG['latency_threshold'] * 5
        
    @pytest.mark.asyncio
    async def test_async_concurrent_benchmark(self, benchmark_suite, mock_exchange):
        """Benchmark des requêtes concurrentes asynchrones"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        async def async_concurrent():
            tasks = []
            for _ in range(50):
                task = market_data.async_get_price('BTC/USDT', 'Benchmark Exchange')
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            return results
        
        result = await benchmark_suite.run_async_benchmark(
            "Async Concurrent Requests",
            async_concurrent
        )
        
        stats = result.get_stats()
        assert stats['success_rate'] > 0.95
        assert stats['avg_latency'] < BENCHMARK_CONFIG['latency_threshold'] * 3
        
    # ============================================================
    # MEMORY BENCHMARKS
    # ============================================================
    
    def test_memory_usage_benchmark(self, benchmark_suite, mock_exchange):
        """Benchmark de l'utilisation mémoire"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        def memory_intensive_operation():
            # Créer beaucoup de données
            data = []
            for i in range(1000):
                ticker = market_data.get_ticker('BTC/USDT', 'Benchmark Exchange')
                order_book = market_data.get_order_book('BTC/USDT', 'Benchmark Exchange')
                data.append({
                    'ticker': ticker,
                    'order_book': order_book,
                    'timestamp': datetime.now().isoformat()
                })
            return data
        
        result = benchmark_suite.run_benchmark(
            "Memory Usage",
            memory_intensive_operation
        )
        
        stats = result.get_stats()
        assert stats['success_rate'] > 0.95
        assert stats['avg_memory'] < BENCHMARK_CONFIG['memory_threshold'] / 1024 / 1024  # MB
        
    # ============================================================
    # STRESS BENCHMARKS
    # ============================================================
    
    def test_stress_benchmark(self, benchmark_suite, mock_exchange):
        """Benchmark de stress"""
        execution_engine = ExecutionEngine()
        execution_engine.add_exchange(mock_exchange)
        
        def stress_operation():
            # Créer et annuler des ordres en boucle
            orders = []
            for i in range(10):
                order = execution_engine.create_order(
                    symbol='BTC/USDT',
                    side='BUY' if i % 2 == 0 else 'SELL',
                    order_type='LIMIT',
                    quantity=0.5,
                    price=45000.0 + i
                )
                orders.append(order)
            
            for order in orders:
                execution_engine.cancel_order(order['id'])
            
            return len(orders)
        
        result = benchmark_suite.run_benchmark(
            "Stress Test",
            stress_operation
        )
        
        stats = result.get_stats()
        assert stats['success_rate'] > 0.90
        assert stats['avg_latency'] < BENCHMARK_CONFIG['latency_threshold'] * 10
        
    # ============================================================
    # SCALABILITY BENCHMARKS
    # ============================================================
    
    def test_scalability_benchmark(self, benchmark_suite):
        """Benchmark de scalabilité"""
        def create_exchanges(count: int) -> List[MockExchange]:
            exchanges = []
            for i in range(count):
                exchange = MockExchange(f"Exchange_{i}")
                exchange.start_market()
                exchanges.append(exchange)
            return exchanges
        
        def test_with_exchanges(count: int):
            exchanges = create_exchanges(count)
            engine = ArbitrageEngine()
            for exchange in exchanges:
                engine.add_exchange(exchange)
            
            opportunities = engine.scan_opportunities()
            
            for exchange in exchanges:
                exchange.stop_market()
            
            return len(opportunities)
        
        # Tester avec différents nombres d'exchanges
        results = []
        for count in [1, 2, 4, 8]:
            result = benchmark_suite.run_benchmark(
                f"Scalability_{count}_exchanges",
                test_with_exchanges,
                count
            )
            results.append(result.get_stats())
        
        # Vérifier la scalabilité
        for i in range(1, len(results)):
            # Le temps ne devrait pas augmenter plus que proportionnellement
            ratio = results[i]['avg_latency'] / results[i-1]['avg_latency']
            expected_ratio = 2.0  # Double des exchanges
            assert ratio < expected_ratio * 1.5  # Tolérance de 50%

    # ============================================================
    # PERFORMANCE COMPARISON
    # ============================================================
    
    def test_sync_vs_async_benchmark(self, benchmark_suite, mock_exchange):
        """Benchmark comparatif synchrone vs asynchrone"""
        market_data = MarketData()
        market_data.add_exchange(mock_exchange)
        
        def sync_operation():
            return market_data.get_price('BTC/USDT', 'Benchmark Exchange')
        
        async def async_operation():
            return await market_data.async_get_price('BTC/USDT', 'Benchmark Exchange')
        
        # Benchmark synchrone
        sync_result = benchmark_suite.run_benchmark(
            "Sync Operations",
            sync_operation
        )
        
        # Benchmark asynchrone
        async_result = benchmark_suite.run_async_benchmark(
            "Async Operations",
            async_operation
        )
        
        sync_stats = sync_result.get_stats()
        async_stats = async_result.get_stats()
        
        # L'asynchrone devrait être au moins aussi rapide
        assert async_stats['avg_latency'] <= sync_stats['avg_latency'] * 1.2

# ============================================================
# PERFORMANCE REPORT
# ============================================================

def generate_performance_report(benchmark_suite: BenchmarkSuite) -> str:
    """Génère un rapport de performance"""
    summary = benchmark_suite.get_summary()
    
    report = []
    report.append("=" * 80)
    report.append("PERFORMANCE BENCHMARK REPORT")
    report.append("=" * 80)
    report.append(f"\nDate: {datetime.now().isoformat()}")
    report.append(f"Total Benchmarks: {summary['total_benchmarks']}")
    report.append(f"Total Iterations: {summary['total_iterations']}")
    report.append(f"Success Rate: {summary['overall_success_rate']*100:.1f}%")
    
    report.append("\n" + "-" * 40)
    report.append("DETAILED RESULTS")
    report.append("-" * 40)
    
    for result in summary['results']:
        report.append(f"\n📊 {result['name']}")
        report.append(f"  Success Rate:     {result['success_rate']*100:.1f}%")
        report.append(f"  Avg Latency:      {result['avg_latency']:.2f}ms")
        report.append(f"  P95 Latency:      {result['p95_latency']:.2f}ms")
        report.append(f"  P99 Latency:      {result['p99_latency']:.2f}ms")
        report.append(f"  Avg Memory:       {result['avg_memory']:.1f}MB")
        report.append(f"  Avg CPU:          {result['avg_cpu']:.1f}%")
    
    # Vérifications des seuils
    report.append("\n" + "-" * 40)
    report.append("THRESHOLD VERIFICATION")
    report.append("-" * 40)
    
    all_passed = True
    for result in summary['results']:
        if result['avg_latency'] > BENCHMARK_CONFIG['latency_threshold']:
            report.append(f"⚠️  {result['name']}: Latency threshold exceeded ({result['avg_latency']:.1f}ms > {BENCHMARK_CONFIG['latency_threshold']}ms)")
            all_passed = False
        else:
            report.append(f"✅ {result['name']}: Passed")
    
    if all_passed:
        report.append("\n✅ All benchmarks passed!")
    else:
        report.append("\n❌ Some benchmarks failed threshold checks")
    
    report.append("\n" + "=" * 80)
    
    return "\n".join(report)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Exécuter les benchmarks
    suite = BenchmarkSuite()
    
    # Créer un mock exchange
    exchange = MockExchange("Benchmark Exchange")
    exchange.start_market()
    
    # Exécuter les benchmarks
    test = TestBenchmark()
    
    # Market Data
    test.test_market_data_benchmark(suite, exchange)
    
    # Arbitrage Scan
    engine = ArbitrageEngine()
    engine.add_exchange(exchange)
    test.test_arbitrage_scan_benchmark(suite, engine)
    
    # Order Creation
    test.test_order_creation_benchmark(suite, exchange)
    
    # Risk Calculation
    test.test_risk_calculation_benchmark(suite)
    
    # Afficher les résultats
    suite.print_results()
    
    # Générer le rapport
    report = generate_performance_report(suite)
    print(report)
    
    # Sauvegarder le rapport
    with open("benchmark_report.txt", "w") as f:
        f.write(report)
    
    exchange.stop_market()

"""
tests/performance/test_cache_perf.py

NEXUS AI Trading System - Cache Performance Tests

This module uses pytest-benchmark to measure the performance of the caching layer,
including Redis and MemoryCache implementations. It tests:

- Cache set and get operations
- Cache performance under concurrent access
- Cache hit vs miss latency
- Cache key generation overhead
- Cache invalidation
- TTL expiration handling
- Serialization/deserialization overhead
- Cache warmup performance

These benchmarks help ensure the caching layer can handle production load and
identify performance regressions.

Usage:
    pytest tests/performance/test_cache_perf.py -v --benchmark-autosave
    pytest tests/performance/test_cache_perf.py -v --benchmark-compare

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import pytest
import random
import string
import concurrent.futures
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock

from backend.core.cache import Cache, RedisCache, MemoryCache
from backend.core.cache import cached, cache_key, cache_invalidate, cache_clear


# ----- Helper functions -----

def generate_random_data(size: int = 1024) -> Dict[str, Any]:
    """Generate random dictionary data of approximately `size` bytes."""
    num_keys = max(1, size // 50)
    data = {}
    for i in range(num_keys):
        key = ''.join(random.choices(string.ascii_letters, k=10))
        value = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        data[key] = value
    return data


# ----- Fixtures -----

@pytest.fixture(scope="function")
def memory_cache():
    """Provide a MemoryCache instance."""
    return MemoryCache()


@pytest.fixture(scope="function")
def redis_cache():
    """Provide a RedisCache instance (uses real Redis if available, else mock)."""
    # Try to connect to Redis; if not available, return a mock or fallback.
    try:
        cache = RedisCache()
        # Check if Redis is reachable by setting a test key
        cache.set("_perf_test", "ok", ttl=1)
        val = cache.get("_perf_test")
        if val == "ok":
            return cache
        else:
            # Fallback to MemoryCache
            return MemoryCache()
    except Exception:
        # If Redis is not available, use MemoryCache (or mock)
        return MemoryCache()


@pytest.fixture(scope="function")
def test_data_small():
    """Small test data (~100 bytes)."""
    return {"id": 123, "name": "test", "value": 42.5}


@pytest.fixture(scope="function")
def test_data_medium():
    """Medium test data (~1KB)."""
    return generate_random_data(1024)


@pytest.fixture(scope="function")
def test_data_large():
    """Large test data (~10KB)."""
    return generate_random_data(10240)


# ----- Cache get/set benchmarks -----

class TestCacheGetSet:
    """Benchmark basic cache get and set operations."""

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    @pytest.mark.parametrize("data_fixture", ["test_data_small", "test_data_medium", "test_data_large"])
    def test_cache_set(self, benchmark, request, cache_fixture, data_fixture):
        """Benchmark setting data in cache."""
        cache = request.getfixturevalue(cache_fixture)
        data = request.getfixturevalue(data_fixture)
        key = "test_set_key"

        @benchmark
        def _set():
            cache.set(key, data, ttl=60)
            return True

        # Ensure the key is set
        cache.set(key, data)
        # Clean up
        cache.delete(key)

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    @pytest.mark.parametrize("data_fixture", ["test_data_small", "test_data_medium", "test_data_large"])
    def test_cache_get(self, benchmark, request, cache_fixture, data_fixture):
        """Benchmark getting data from cache."""
        cache = request.getfixturevalue(cache_fixture)
        data = request.getfixturevalue(data_fixture)
        key = "test_get_key"
        cache.set(key, data, ttl=60)

        @benchmark
        def _get():
            result = cache.get(key)
            return result

        cache.delete(key)

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    def test_cache_get_miss(self, benchmark, request, cache_fixture):
        """Benchmark getting a non-existent key (cache miss)."""
        cache = request.getfixturevalue(cache_fixture)
        key = "non_existent_key"

        @benchmark
        def _get_miss():
            result = cache.get(key)
            return result

        # Result should be None; we just benchmark the time.

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    def test_cache_set_existing(self, benchmark, request, cache_fixture):
        """Benchmark updating an existing key."""
        cache = request.getfixturevalue(cache_fixture)
        key = "update_key"
        cache.set(key, {"value": "old"}, ttl=60)
        new_data = {"value": "new", "timestamp": time.time()}

        @benchmark
        def _update():
            cache.set(key, new_data, ttl=60)
            return True

        cache.delete(key)


# ----- Cache serialization/deserialization benchmarks -----

class TestCacheSerialization:
    """Benchmark serialization/deserialization overhead in cache."""

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    @pytest.mark.parametrize("data_size", [100, 1000, 10000])
    def test_serialization_overhead(self, benchmark, request, cache_fixture, data_size):
        """Benchmark serialization overhead when caching complex objects."""
        cache = request.getfixturevalue(cache_fixture)
        data = generate_random_data(data_size)
        key = "serialization_key"

        @benchmark
        def _set_serialized():
            # The cache implementation may serialize; we measure the total set time.
            cache.set(key, data, ttl=60)

        cache.delete(key)

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    @pytest.mark.parametrize("data_size", [100, 1000, 10000])
    def test_deserialization_overhead(self, benchmark, request, cache_fixture, data_size):
        """Benchmark deserialization overhead when retrieving complex objects."""
        cache = request.getfixturevalue(cache_fixture)
        data = generate_random_data(data_size)
        key = "deserialization_key"
        cache.set(key, data, ttl=60)

        @benchmark
        def _get_deserialized():
            result = cache.get(key)
            return result

        cache.delete(key)


# ----- Concurrent cache access benchmarks -----

class TestCacheConcurrency:
    """Benchmark cache performance under concurrent access."""

    def measure_concurrent(
        self,
        cache,
        num_workers: int,
        num_ops_per_worker: int,
        operation: str,
        data=None,
    ) -> Dict[str, float]:
        """
        Measure concurrent cache operations.
        Returns throughput (ops/s) and average latency.
        """
        key = "concurrent_key"
        if operation == "set":
            data = data or {"value": 42}
            def worker():
                for _ in range(num_ops_per_worker):
                    cache.set(key, data, ttl=60)
        elif operation == "get":
            # Pre-populate
            cache.set(key, {"value": 42}, ttl=300)
            def worker():
                for _ in range(num_ops_per_worker):
                    cache.get(key)
        elif operation == "mixed":
            cache.set(key, {"value": 42}, ttl=300)
            def worker():
                for _ in range(num_ops_per_worker):
                    if random.random() > 0.5:
                        cache.get(key)
                    else:
                        cache.set(key, {"value": random.randint(1, 100)}, ttl=60)
        else:
            raise ValueError(f"Unknown operation: {operation}")

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker) for _ in range(num_workers)]
            for f in concurrent.futures.as_completed(futures):
                f.result()
        elapsed = time.perf_counter() - start
        total_ops = num_workers * num_ops_per_worker
        throughput = total_ops / elapsed if elapsed > 0 else 0
        avg_latency = elapsed / total_ops if total_ops > 0 else 0
        return {"throughput": throughput, "avg_latency": avg_latency, "elapsed": elapsed}

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    @pytest.mark.parametrize("num_workers", [1, 5, 10, 25])
    def test_concurrent_set(self, benchmark, request, cache_fixture, num_workers):
        """Benchmark concurrent set operations."""
        cache = request.getfixturevalue(cache_fixture)
        data = {"value": 42}
        key = "concurrent_set_key"

        @benchmark
        def _concurrent_set():
            # We'll use the measure_concurrent method, but benchmark will time the whole thing.
            result = self.measure_concurrent(cache, num_workers, 20, "set", data)
            return result

        cache.delete(key)

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    @pytest.mark.parametrize("num_workers", [1, 5, 10, 25])
    def test_concurrent_get(self, benchmark, request, cache_fixture, num_workers):
        """Benchmark concurrent get operations."""
        cache = request.getfixturevalue(cache_fixture)
        key = "concurrent_get_key"
        cache.set(key, {"value": 42}, ttl=300)

        @benchmark
        def _concurrent_get():
            result = self.measure_concurrent(cache, num_workers, 20, "get")
            return result

        cache.delete(key)

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    @pytest.mark.parametrize("num_workers", [1, 5, 10, 25])
    def test_concurrent_mixed(self, benchmark, request, cache_fixture, num_workers):
        """Benchmark mixed get/set operations."""
        cache = request.getfixturevalue(cache_fixture)
        key = "concurrent_mixed_key"
        cache.set(key, {"value": 42}, ttl=300)

        @benchmark
        def _concurrent_mixed():
            result = self.measure_concurrent(cache, num_workers, 20, "mixed")
            return result

        cache.delete(key)


# ----- Cache invalidation benchmarks -----

class TestCacheInvalidation:
    """Benchmark cache invalidation performance."""

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    def test_cache_delete(self, benchmark, request, cache_fixture):
        """Benchmark deleting a key from cache."""
        cache = request.getfixturevalue(cache_fixture)
        key = "delete_key"
        cache.set(key, "value", ttl=60)

        @benchmark
        def _delete():
            cache.delete(key)

        # Ensure it's deleted
        assert cache.get(key) is None

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    def test_cache_clear(self, benchmark, request, cache_fixture):
        """Benchmark clearing all cache keys (flush)."""
        cache = request.getfixturevalue(cache_fixture)
        # Pre-populate some keys
        for i in range(10):
            cache.set(f"clear_key_{i}", i, ttl=60)

        @benchmark
        def _clear():
            cache.clear()

        # Verify all keys are gone
        for i in range(10):
            assert cache.get(f"clear_key_{i}") is None

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    @pytest.mark.parametrize("num_keys", [10, 100, 500])
    def test_bulk_invalidation(self, benchmark, request, cache_fixture, num_keys):
        """Benchmark invalidating many keys at once."""
        cache = request.getfixturevalue(cache_fixture)
        keys = [f"bulk_key_{i}" for i in range(num_keys)]
        for k in keys:
            cache.set(k, "value", ttl=60)

        @benchmark
        def _bulk_delete():
            for k in keys:
                cache.delete(k)

        # Verify
        for k in keys:
            assert cache.get(k) is None


# ----- Cache key generation benchmarks -----

class TestCacheKeyGeneration:
    """Benchmark cache key generation overhead."""

    def test_simple_key(self, benchmark):
        """Benchmark simple string key generation."""
        def _gen():
            return f"prefix_{123}_{'test'}"
        benchmark(_gen)

    def test_complex_key(self, benchmark):
        """Benchmark complex key generation with multiple parts."""
        def _gen():
            return cache_key("prefix", "arg1", "arg2", kw="value", another="extra")
        benchmark(_gen)

    def test_key_with_large_args(self, benchmark):
        """Benchmark key generation with large arguments."""
        large_arg = "".join(random.choices(string.ascii_letters, k=1000))
        def _gen():
            return cache_key("prefix", large_arg, "suffix")
        benchmark(_gen)

    def test_key_with_dict(self, benchmark):
        """Benchmark key generation with dictionary parameters."""
        d = {"a": 1, "b": 2, "c": {"d": 3}}
        def _gen():
            return cache_key("prefix", d)
        benchmark(_gen)


# ----- Cache hit/miss performance (realistic) -----

class TestCacheHitMiss:
    """Benchmark realistic hit/miss scenarios with TTL."""

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    def test_cache_hit_ratio_50(self, benchmark, request, cache_fixture):
        """Benchmark with 50% cache hit rate."""
        cache = request.getfixturevalue(cache_fixture)
        # Pre-fill half the keys
        for i in range(50):
            cache.set(f"hitmiss_key_{i}", i, ttl=300)

        def _access():
            key = f"hitmiss_key_{random.randint(0, 99)}"
            return cache.get(key)

        @benchmark
        def _mixed_access():
            total = 0
            hits = 0
            for _ in range(100):
                val = _access()
                total += 1
                if val is not None:
                    hits += 1
            return hits / total

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    def test_cache_hit_ratio_10(self, benchmark, request, cache_fixture):
        """Benchmark with 10% cache hit rate."""
        cache = request.getfixturevalue(cache_fixture)
        for i in range(10):
            cache.set(f"hitmiss_10_key_{i}", i, ttl=300)

        def _access():
            key = f"hitmiss_10_key_{random.randint(0, 99)}"
            return cache.get(key)

        @benchmark
        def _low_hit():
            total = 0
            hits = 0
            for _ in range(100):
                val = _access()
                total += 1
                if val is not None:
                    hits += 1
            return hits / total


# ----- TTL expiration benchmarks -----

class TestCacheTTL:
    """Benchmark TTL expiration handling (overhead)."""

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    def test_ttl_expired_get(self, benchmark, request, cache_fixture):
        """Benchmark get of an expired key (should be None but with TTL check)."""
        cache = request.getfixturevalue(cache_fixture)
        key = "expired_key"
        cache.set(key, "value", ttl=1)  # Short TTL
        time.sleep(1.5)  # Wait for expiration

        @benchmark
        def _get_expired():
            return cache.get(key)

        # Should return None
        assert cache.get(key) is None

    @pytest.mark.parametrize("cache_fixture", ["memory_cache", "redis_cache"])
    def test_ttl_check_overhead(self, benchmark, request, cache_fixture):
        """Benchmark overhead of TTL check for existing keys."""
        cache = request.getfixturevalue(cache_fixture)
        key = "ttl_check_key"
        cache.set(key, "value", ttl=60)

        @benchmark
        def _ttl_check():
            # This may vary by implementation; we just call get
            return cache.get(key)

        cache.delete(key)


# ----- Cache performance under stress -----

class TestCacheStress:
    """Stress tests for cache under heavy load (not benchmarked individually)."""

    def test_cache_stress_set_get(self):
        """Run a stress test with many operations and measure overall time."""
        # We'll use a MemoryCache for speed; this is a sanity test.
        cache = MemoryCache()
        num_ops = 10000
        start = time.perf_counter()
        for i in range(num_ops):
            key = f"stress_key_{i}"
            cache.set(key, {"value": i, "data": generate_random_data(100)}, ttl=60)
        for i in range(num_ops):
            key = f"stress_key_{i}"
            val = cache.get(key)
            assert val is not None
        elapsed = time.perf_counter() - start
        throughput = (2 * num_ops) / elapsed if elapsed > 0 else 0
        print(f"\nStress test: {2*num_ops} ops in {elapsed:.2f}s, throughput {throughput:.2f} ops/s")
        # No assertion, just for performance observation.

    def test_redis_connection_benchmark(self):
        """Benchmark Redis connection time (if Redis is available)."""
        try:
            cache = RedisCache()
            start = time.perf_counter()
            cache.ping()
            elapsed = time.perf_counter() - start
            print(f"\nRedis ping latency: {elapsed*1000:.2f}ms")
        except Exception as e:
            print(f"Redis not available: {e}")


# ----- Report generation -----

def test_generate_cache_performance_report():
    """
    Generate a comprehensive cache performance report comparing MemoryCache and RedisCache.
    This runs all key operations and logs results.
    """
    import time
    import json
    from datetime import datetime

    def run_test(cache, name, data_size=1024):
        data = generate_random_data(data_size)
        key = "report_key"
        results = {}

        # Set
        start = time.perf_counter()
        for _ in range(100):
            cache.set(key, data, ttl=60)
        elapsed = time.perf_counter() - start
        results["set_100"] = elapsed / 100

        # Get
        cache.set(key, data, ttl=300)
        start = time.perf_counter()
        for _ in range(100):
            cache.get(key)
        elapsed = time.perf_counter() - start
        results["get_100"] = elapsed / 100

        # Delete
        start = time.perf_counter()
        for _ in range(100):
            cache.delete(key)
        elapsed = time.perf_counter() - start
        results["delete_100"] = elapsed / 100

        # Concurrent (10 workers, 50 ops each)
        def worker():
            for _ in range(50):
                cache.get(key)
        import concurrent.futures
        cache.set(key, data, ttl=300)
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            for f in futures:
                f.result()
        elapsed = time.perf_counter() - start
        results["concurrent_500"] = elapsed / 500

        return results

    memory_results = run_test(MemoryCache(), "MemoryCache")
    try:
        redis_cache = RedisCache()
        redis_results = run_test(redis_cache, "RedisCache")
    except Exception:
        redis_results = None

    print("\n" + "="*60)
    print("CACHE PERFORMANCE COMPARISON REPORT")
    print("="*60)
    print(f"{'Operation':<20} {'MemoryCache (ms)':<20} {'RedisCache (ms)':<20}")
    print("-"*60)
    for op in memory_results:
        mem_val = memory_results[op] * 1000
        if redis_results:
            redis_val = redis_results[op] * 1000
            print(f"{op:<20} {mem_val:>18.3f} {redis_val:>18.3f}")
        else:
            print(f"{op:<20} {mem_val:>18.3f} {'N/A':>18}")
    print("="*60)

    # Save report
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"cache_perf_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "MemoryCache": memory_results,
            "RedisCache": redis_results if redis_results else "unavailable",
        }, f, indent=2)
    print(f"Report saved to {report_path}")

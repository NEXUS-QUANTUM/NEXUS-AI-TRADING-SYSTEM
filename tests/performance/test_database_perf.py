
"""
tests/performance/test_database_perf.py

NEXUS AI Trading System - Database Performance Tests

This module uses pytest-benchmark to measure the performance of database
operations, including:

- Model creation (users, portfolios, positions, orders)
- Query performance (selects, joins, aggregates)
- Bulk inserts
- Relationship queries (eager vs lazy loading)
- Pagination performance
- Transaction handling
- Connection pool behavior
- Index usage and query optimization
- Migration performance (schema changes)

These benchmarks help identify database bottlenecks and track performance
regressions over time.

Usage:
    pytest tests/performance/test_database_perf.py -v --benchmark-autosave
    pytest tests/performance/test_database_perf.py -v --benchmark-compare

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import time
import json
import pytest
import random
import concurrent.futures
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.pool import NullPool, QueuePool

from backend.core.database import Base
from backend.models.user import User
from backend.models.portfolio import Portfolio
from backend.models.position import Position
from backend.models.order import Order
from backend.models.broker_account import BrokerAccount
from backend.models.subscription import Subscription, SubscriptionPlan
from backend.models.ai_model import AIModel
from backend.models.ai_prediction import AIPrediction
from backend.models.risk import RiskLimit
from backend.models.audit_log import AuditLog
from backend.models.trade import Trade

from tests.performance.conftest import (
    perf_db,
    perf_db_session,
    perf_test_user,
    perf_test_portfolio,
    perf_test_broker,
    perf_test_positions,
    perf_test_orders,
    perf_benchmark_rounds,
    perf_benchmark_iterations,
)


# ----- Helper functions -----

def generate_users(count: int, base_email: str = "perf_user_{}@example.com") -> List[User]:
    """Generate a list of User objects for bulk insert."""
    from backend.security.auth import get_password_hash
    users = []
    for i in range(count):
        user = User(
            id=f"perf-user-{i}-{random.randint(1000, 9999)}",
            email=base_email.format(i),
            first_name=f"Perf{i}",
            last_name="User",
            hashed_password=get_password_hash("PerfTest@123"),
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
        )
        users.append(user)
    return users


def generate_positions(portfolio_id: str, broker_id: str, count: int) -> List[Position]:
    """Generate a list of Position objects for bulk insert."""
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "SPY", "QQQ", "JPM", "V", "WMT"]
    positions = []
    for i in range(count):
        pos = Position(
            portfolio_id=portfolio_id,
            broker_account_id=broker_id,
            symbol=random.choice(symbols),
            quantity=random.randint(1, 1000),
            entry_price=random.uniform(10, 1000),
            current_price=random.uniform(10, 1000),
            side=random.choice(["long", "short"]),
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 365)),
            updated_at=datetime.utcnow(),
        )
        positions.append(pos)
    return positions


def generate_orders(portfolio_id: str, broker_id: str, count: int) -> List[Order]:
    """Generate a list of Order objects for bulk insert."""
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX"]
    statuses = ["open", "filled", "cancelled", "partially_filled"]
    orders = []
    for i in range(count):
        order = Order(
            portfolio_id=portfolio_id,
            broker_account_id=broker_id,
            symbol=random.choice(symbols),
            side=random.choice(["buy", "sell"]),
            order_type=random.choice(["market", "limit", "stop"]),
            quantity=random.randint(1, 100),
            filled_quantity=0,
            price=random.uniform(50, 500),
            limit_price=random.uniform(50, 500) if random.random() > 0.5 else None,
            stop_price=random.uniform(50, 500) if random.random() > 0.5 else None,
            status=random.choice(statuses),
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            updated_at=datetime.utcnow(),
        )
        orders.append(order)
    return orders


# ----- Fixtures for different data sizes -----

@pytest.fixture(scope="function")
def db_engine():
    """Create a database engine with a connection pool for performance testing."""
    db_url = os.getenv("PERF_DATABASE_URL", "sqlite:///./perf_test.db")
    engine = create_engine(db_url, pool_size=20, max_overflow=40, echo=False)
    return engine


@pytest.fixture(scope="function")
def db_session_pool(db_engine):
    """Create a session for performance testing."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def large_portfolio(perf_db_session, perf_test_user, perf_test_broker):
    """Create a portfolio with many positions and orders for performance testing."""
    portfolio = Portfolio(
        user_id=perf_test_user.id,
        name="Large Performance Portfolio",
        total_balance=10000000.0,
        available_balance=9000000.0,
        currency="USD",
        created_at=datetime.utcnow(),
    )
    perf_db_session.add(portfolio)
    perf_db_session.commit()
    perf_db_session.refresh(portfolio)

    # Generate many positions (e.g., 1000)
    positions = generate_positions(portfolio.id, perf_test_broker.id, 1000)
    perf_db_session.bulk_save_objects(positions)
    perf_db_session.commit()

    # Generate many orders (e.g., 2000)
    orders = generate_orders(portfolio.id, perf_test_broker.id, 2000)
    perf_db_session.bulk_save_objects(orders)
    perf_db_session.commit()

    return portfolio


# ----- Model creation benchmarks -----

class TestModelCreation:
    """Benchmark individual and bulk model creation."""

    def test_create_single_user(self, benchmark, db_session_pool: Session):
        """Benchmark creating a single user."""
        from backend.security.auth import get_password_hash

        @benchmark
        def _create_user():
            user = User(
                id=f"bench-user-{int(time.time()*1000)}",
                email=f"bench_{int(time.time()*1000)}@example.com",
                first_name="Bench",
                last_name="User",
                hashed_password=get_password_hash("Test@123"),
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow(),
            )
            db_session_pool.add(user)
            db_session_pool.commit()
            return user

        # Clean up
        if _create_user:
            db_session_pool.delete(_create_user)
            db_session_pool.commit()

    def test_create_single_portfolio(self, benchmark, db_session_pool: Session, perf_test_user: User):
        """Benchmark creating a single portfolio."""
        @benchmark
        def _create_portfolio():
            portfolio = Portfolio(
                user_id=perf_test_user.id,
                name="Bench Portfolio",
                total_balance=100000.0,
                available_balance=100000.0,
                currency="USD",
                created_at=datetime.utcnow(),
            )
            db_session_pool.add(portfolio)
            db_session_pool.commit()
            return portfolio

        # Clean up
        if _create_portfolio:
            db_session_pool.delete(_create_portfolio)
            db_session_pool.commit()

    def test_bulk_insert_users(self, benchmark, db_session_pool: Session):
        """Benchmark bulk inserting 100 users."""
        count = 100
        users = generate_users(count, f"bulk_perf_{{}}@example.com")

        @benchmark
        def _bulk_insert():
            db_session_pool.bulk_save_objects(users)
            db_session_pool.commit()

        # Clean up
        for user in users:
            db_session_pool.delete(user)
        db_session_pool.commit()

    def test_bulk_insert_positions(self, benchmark, db_session_pool: Session, perf_test_portfolio: Portfolio, perf_test_broker: BrokerAccount):
        """Benchmark bulk inserting 500 positions."""
        count = 500
        positions = generate_positions(perf_test_portfolio.id, perf_test_broker.id, count)

        @benchmark
        def _bulk_insert():
            db_session_pool.bulk_save_objects(positions)
            db_session_pool.commit()

        # Clean up
        for pos in positions:
            db_session_pool.delete(pos)
        db_session_pool.commit()


# ----- Query performance benchmarks -----

class TestQueryPerformance:
    """Benchmark various query patterns."""

    def test_query_single_user_by_id(self, benchmark, db_session_pool: Session, perf_test_user: User):
        """Benchmark querying a single user by ID."""
        @benchmark
        def _query_user():
            user = db_session_pool.query(User).filter(User.id == perf_test_user.id).first()
            return user

        assert _query_user is not None

    def test_query_users_with_filter(self, benchmark, db_session_pool: Session):
        """Benchmark querying users with a filter condition."""
        # Ensure there are some users
        count = 50
        users = generate_users(count, f"filter_perf_{{}}@example.com")
        db_session_pool.bulk_save_objects(users)
        db_session_pool.commit()

        @benchmark
        def _filter_users():
            results = db_session_pool.query(User).filter(User.email.like("%filter_perf%")).all()
            return results

        # Clean up
        for user in users:
            db_session_pool.delete(user)
        db_session_pool.commit()

    def test_query_portfolio_with_positions(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark querying portfolio with positions (lazy loading)."""
        @benchmark
        def _query_portfolio():
            portfolio = db_session_pool.query(Portfolio).filter(Portfolio.id == large_portfolio.id).first()
            # Access positions to trigger lazy load
            count = len(portfolio.positions)
            return count

    def test_query_portfolio_with_positions_eager(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark querying portfolio with positions (eager loading)."""
        @benchmark
        def _query_eager():
            portfolio = db_session_pool.query(Portfolio).options(joinedload(Portfolio.positions)).filter(Portfolio.id == large_portfolio.id).first()
            count = len(portfolio.positions)
            return count

    def test_query_positions_with_symbol_filter(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark querying positions filtered by symbol."""
        @benchmark
        def _filter_positions():
            results = db_session_pool.query(Position).filter(
                Position.portfolio_id == large_portfolio.id,
                Position.symbol == "AAPL"
            ).all()
            return len(results)

    def test_query_orders_with_date_range(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark querying orders within a date range."""
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()

        @benchmark
        def _date_range():
            results = db_session_pool.query(Order).filter(
                Order.portfolio_id == large_portfolio.id,
                Order.created_at.between(start_date, end_date)
            ).all()
            return len(results)

    def test_query_orders_with_join(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark querying orders with a join to portfolio."""
        @benchmark
        def _join_query():
            results = db_session_pool.query(Order, Portfolio).join(Portfolio, Order.portfolio_id == Portfolio.id).filter(
                Portfolio.id == large_portfolio.id,
                Order.status == "open"
            ).all()
            return len(results)


# ----- Aggregation and reporting queries -----

class TestAggregationQueries:
    """Benchmark aggregation and reporting queries."""

    def test_count_positions_by_portfolio(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark counting positions grouped by portfolio."""
        @benchmark
        def _count_positions():
            results = db_session_pool.query(
                Position.portfolio_id,
                Position.symbol,
                func.count(Position.id).label("count")
            ).group_by(Position.portfolio_id, Position.symbol).all()
            return len(results)

    def test_summary_performance(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark portfolio summary aggregation."""
        @benchmark
        def _portfolio_summary():
            summary = db_session_pool.query(
                func.sum(Position.quantity * Position.current_price).label("total_value"),
                func.sum(Position.quantity * (Position.current_price - Position.entry_price)).label("total_pnl"),
            ).filter(Position.portfolio_id == large_portfolio.id).first()
            return summary

    def test_aggregate_by_symbol(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark aggregation by symbol."""
        @benchmark
        def _aggregate_by_symbol():
            results = db_session_pool.query(
                Position.symbol,
                func.sum(Position.quantity).label("total_quantity"),
                func.avg(Position.current_price).label("avg_price"),
            ).filter(Position.portfolio_id == large_portfolio.id).group_by(Position.symbol).all()
            return len(results)


# ----- Bulk operations benchmarks -----

class TestBulkOperations:
    """Benchmark bulk operations (updates, deletes)."""

    def test_bulk_update_positions(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark bulk updating positions."""
        @benchmark
        def _bulk_update():
            positions = db_session_pool.query(Position).filter(
                Position.portfolio_id == large_portfolio.id,
                Position.symbol.in_(["AAPL", "MSFT", "GOOGL"])
            ).all()
            for pos in positions:
                pos.current_price = pos.current_price * 1.01
            db_session_pool.commit()

    def test_bulk_delete_orders(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark bulk deleting orders by status."""
        # Ensure there are some orders to delete
        # We'll create some cancelled orders
        cancelled_orders = generate_orders(large_portfolio.id, "cancelled", 100)
        db_session_pool.bulk_save_objects(cancelled_orders)
        db_session_pool.commit()

        @benchmark
        def _bulk_delete():
            deleted = db_session_pool.query(Order).filter(
                Order.portfolio_id == large_portfolio.id,
                Order.status == "cancelled"
            ).delete()
            db_session_pool.commit()
            return deleted

        # Clean up if any remain
        db_session_pool.query(Order).filter(
            Order.portfolio_id == large_portfolio.id,
            Order.status == "cancelled"
        ).delete()
        db_session_pool.commit()


# ----- Transaction performance -----

class TestTransactionPerformance:
    """Benchmark transaction handling performance."""

    def test_single_transaction_with_commits(self, benchmark, db_session_pool: Session, perf_test_user: User):
        """Benchmark a transaction with multiple commits."""
        @benchmark
        def _transaction():
            # Create a portfolio
            portfolio = Portfolio(
                user_id=perf_test_user.id,
                name="Trans Portfolio",
                total_balance=10000.0,
                available_balance=10000.0,
                currency="USD",
                created_at=datetime.utcnow(),
            )
            db_session_pool.add(portfolio)
            db_session_pool.commit()

            # Create positions
            positions = generate_positions(portfolio.id, "some_broker_id", 10)
            db_session_pool.bulk_save_objects(positions)
            db_session_pool.commit()

            # Update portfolio balance
            portfolio.total_balance = 9000.0
            db_session_pool.commit()

            return portfolio

        # Clean up
        if _transaction:
            db_session_pool.delete(_transaction)
            db_session_pool.commit()

    def test_transaction_with_savepoints(self, benchmark, db_session_pool: Session, perf_test_user: User):
        """Benchmark transaction with savepoints (nested transactions)."""
        @benchmark
        def _nested_transaction():
            # Create a portfolio
            portfolio = Portfolio(
                user_id=perf_test_user.id,
                name="Nested Portfolio",
                total_balance=10000.0,
                available_balance=10000.0,
                currency="USD",
                created_at=datetime.utcnow(),
            )
            db_session_pool.add(portfolio)

            # Savepoint 1
            sp1 = db_session_pool.begin_nested()
            # Add a position
            pos = Position(
                portfolio_id=portfolio.id,
                broker_account_id="some_broker_id",
                symbol="AAPL",
                quantity=10,
                entry_price=150.0,
                current_price=150.0,
                side="long",
                created_at=datetime.utcnow(),
            )
            db_session_pool.add(pos)
            sp1.commit()  # Savepoint committed

            # Savepoint 2
            sp2 = db_session_pool.begin_nested()
            # Add another position
            pos2 = Position(
                portfolio_id=portfolio.id,
                broker_account_id="some_broker_id",
                symbol="MSFT",
                quantity=5,
                entry_price=300.0,
                current_price=300.0,
                side="long",
                created_at=datetime.utcnow(),
            )
            db_session_pool.add(pos2)
            sp2.rollback()  # Rollback savepoint (MSFT not saved)

            db_session_pool.commit()
            return portfolio

        # Clean up
        if _transaction:
            db_session_pool.delete(_transaction)
            db_session_pool.commit()


# ----- Connection pool benchmarks -----

class TestConnectionPool:
    """Benchmark connection pool behavior."""

    def test_connection_acquire_release(self, benchmark, db_engine):
        """Benchmark acquiring and releasing connections from the pool."""
        @benchmark
        def _acquire_release():
            with db_engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).scalar()
                return result

    @pytest.mark.parametrize("pool_size", [5, 20, 50])
    def test_connection_pool_concurrent(self, benchmark, pool_size):
        """Benchmark concurrent connection acquisition."""
        engine = create_engine(
            os.getenv("PERF_DATABASE_URL", "sqlite:///./perf_test.db"),
            pool_size=pool_size,
            max_overflow=pool_size * 2,
            pool_timeout=30,
        )

        def _acquire():
            with engine.connect() as conn:
                return conn.execute(text("SELECT 1")).scalar()

        @benchmark
        def _concurrent():
            with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
                futures = [executor.submit(_acquire) for _ in range(pool_size * 2)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                return len(results)


# ----- Query plan and optimization benchmarks -----

class TestQueryOptimization:
    """Benchmark query optimization patterns."""

    def test_inefficient_vs_efficient_query(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Compare inefficient vs efficient query patterns."""
        # Inefficient: N+1 queries
        @benchmark
        def _inefficient_query():
            portfolios = db_session_pool.query(Portfolio).filter(Portfolio.id == large_portfolio.id).all()
            total = 0
            for p in portfolios:
                total += len(p.positions)
            return total

        # Efficient: joined load
        @benchmark
        def _efficient_query():
            portfolios = db_session_pool.query(Portfolio).options(joinedload(Portfolio.positions)).filter(Portfolio.id == large_portfolio.id).all()
            total = 0
            for p in portfolios:
                total += len(p.positions)
            return total

    def test_index_usage_query(self, benchmark, db_session_pool: Session, large_portfolio: Portfolio):
        """Benchmark query with and without index usage."""
        # Query on indexed column (created_at)
        @benchmark
        def _indexed_query():
            results = db_session_pool.query(Order).filter(
                Order.created_at > datetime.utcnow() - timedelta(days=30)
            ).all()
            return len(results)

        # Query on non-indexed column (order_type)
        @benchmark
        def _non_indexed_query():
            results = db_session_pool.query(Order).filter(
                Order.order_type == "limit"
            ).all()
            return len(results)


# ----- Migration performance (if alembic is available) -----

class TestMigrationPerformance:
    """Benchmark migration execution time."""

    @pytest.mark.skip(reason="Migration performance tests require alembic setup")
    def test_migration_upgrade(self, benchmark):
        """Benchmark Alembic upgrade performance."""
        pass

    @pytest.mark.skip(reason="Migration performance tests require alembic setup")
    def test_migration_downgrade(self, benchmark):
        """Benchmark Alembic downgrade performance."""
        pass


# ----- Report generation -----

def test_generate_database_performance_report():
    """
    Generate a comprehensive report of database performance benchmarks.
    This runs a series of operations and records times in a report.
    """
    import time
    import json
    from datetime import datetime
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("PERF_DATABASE_URL", "sqlite:///./perf_test.db")
    engine = create_engine(db_url, pool_size=10, echo=False)
    SessionLocal = sessionmaker(bind=engine)

    results = {}

    # Test 1: Model creation
    session = SessionLocal()
    start = time.perf_counter()
    user = User(
        id=f"report-user-{int(time.time()*1000)}",
        email=f"report_{int(time.time()*1000)}@example.com",
        first_name="Report",
        last_name="User",
        hashed_password="hash",
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    elapsed = time.perf_counter() - start
    results["create_user"] = elapsed * 1000  # ms

    # Clean up
    session.delete(user)
    session.commit()

    # Test 2: Bulk insert
    users = generate_users(100, f"bulk_report_{{}}@example.com")
    start = time.perf_counter()
    session.bulk_save_objects(users)
    session.commit()
    elapsed = time.perf_counter() - start
    results["bulk_insert_100_users"] = elapsed * 1000

    # Clean up
    for u in users:
        session.delete(u)
    session.commit()

    # Test 3: Query with filter
    users = generate_users(50, f"query_report_{{}}@example.com")
    session.bulk_save_objects(users)
    session.commit()

    start = time.perf_counter()
    results_query = session.query(User).filter(User.email.like("%query_report%")).all()
    elapsed = time.perf_counter() - start
    results["filter_query_50_users"] = elapsed * 1000

    # Clean up
    for u in users:
        session.delete(u)
    session.commit()

    # Test 4: Complex join (if data exists)
    # We'll skip if not available

    session.close()

    print("\n" + "="*60)
    print("DATABASE PERFORMANCE REPORT")
    print("="*60)
    for op, ms in results.items():
        print(f"{op:30s} {ms:10.2f} ms")
    print("="*60)

    # Save report
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"database_perf_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }, f, indent=2)
    print(f"Report saved to {report_path}")

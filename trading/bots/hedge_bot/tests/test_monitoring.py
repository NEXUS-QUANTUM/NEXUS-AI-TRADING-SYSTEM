# trading/bots/hedge_bot/tests/test_monitoring.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Monitoring Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Monitoring Tests

This module provides comprehensive tests for the monitoring and observability
components of the NEXUS Hedge Bot system. It covers metrics collection,
alerting, logging, health checks, and performance monitoring.

The test suite covers:
- Metrics collection and aggregation
- Alert generation and notification
- Health check execution
- Log management and analysis
- Performance monitoring
- Dashboard data generation
- System monitoring
- Application monitoring
- Business monitoring
- Security monitoring
"""

import os
import sys
import json
import time
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock

import pytest
import pytest_asyncio

# Import monitoring components
from trading.bots.hedge_bot.monitoring.metrics import MetricsCollector, Metric, MetricType
from trading.bots.hedge_bot.monitoring.alerts import AlertManager, Alert, AlertSeverity, AlertStatus
from trading.bots.hedge_bot.monitoring.health import HealthChecker, HealthCheck, HealthStatus
from trading.bots.hedge_bot.monitoring.logging import LogManager, LogEntry, LogLevel
from trading.bots.hedge_bot.monitoring.performance import PerformanceMonitor
from trading.bots.hedge_bot.monitoring.dashboard import DashboardGenerator

# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture
def metrics_collector() -> MetricsCollector:
    """Create metrics collector instance"""
    return MetricsCollector()


@pytest.fixture
def alert_manager() -> AlertManager:
    """Create alert manager instance"""
    return AlertManager()


@pytest.fixture
def health_checker() -> HealthChecker:
    """Create health checker instance"""
    return HealthChecker()


@pytest.fixture
def log_manager() -> LogManager:
    """Create log manager instance"""
    return LogManager()


@pytest.fixture
def performance_monitor() -> PerformanceMonitor:
    """Create performance monitor instance"""
    return PerformanceMonitor()


@pytest.fixture
def dashboard_generator() -> DashboardGenerator:
    """Create dashboard generator instance"""
    return DashboardGenerator()


# ============================================================
# METRICS TESTS
# ============================================================

class TestMetricsCollector:
    """
    Tests for MetricsCollector
    """

    def test_metrics_collector_initialization(self, metrics_collector: MetricsCollector) -> None:
        """Test metrics collector initialization"""
        assert metrics_collector is not None
        assert metrics_collector.metrics is not None
        assert metrics_collector.collectors is not None

    def test_register_metric(self, metrics_collector: MetricsCollector) -> None:
        """Test metric registration"""
        metric = Metric(
            name="test_metric",
            type=MetricType.GAUGE,
            description="Test metric",
            unit="percent",
        )
        metrics_collector.register_metric(metric)
        assert "test_metric" in metrics_collector.metrics

    def test_record_metric(self, metrics_collector: MetricsCollector) -> None:
        """Test metric recording"""
        metric = Metric(
            name="test_gauge",
            type=MetricType.GAUGE,
            description="Test gauge",
        )
        metrics_collector.register_metric(metric)
        
        metrics_collector.record_metric("test_gauge", 42.0)
        data = metrics_collector.get_metric("test_gauge")
        assert data["value"] == 42.0

    def test_record_counter(self, metrics_collector: MetricsCollector) -> None:
        """Test counter metric recording"""
        metric = Metric(
            name="test_counter",
            type=MetricType.COUNTER,
            description="Test counter",
        )
        metrics_collector.register_metric(metric)
        
        metrics_collector.record_metric("test_counter", 1)
        metrics_collector.record_metric("test_counter", 2)
        data = metrics_collector.get_metric("test_counter")
        assert data["value"] == 3

    def test_record_histogram(self, metrics_collector: MetricsCollector) -> None:
        """Test histogram metric recording"""
        metric = Metric(
            name="test_histogram",
            type=MetricType.HISTOGRAM,
            description="Test histogram",
        )
        metrics_collector.register_metric(metric)
        
        metrics_collector.record_metric("test_histogram", 10)
        metrics_collector.record_metric("test_histogram", 20)
        metrics_collector.record_metric("test_histogram", 30)
        
        data = metrics_collector.get_metric("test_histogram")
        assert data["count"] == 3
        assert data["min"] == 10
        assert data["max"] == 30
        assert data["sum"] == 60
        assert data["mean"] == 20.0

    def test_get_all_metrics(self, metrics_collector: MetricsCollector) -> None:
        """Test getting all metrics"""
        metric1 = Metric(name="metric1", type=MetricType.GAUGE)
        metric2 = Metric(name="metric2", type=MetricType.COUNTER)
        
        metrics_collector.register_metric(metric1)
        metrics_collector.register_metric(metric2)
        
        metrics_collector.record_metric("metric1", 10)
        metrics_collector.record_metric("metric2", 5)
        
        all_metrics = metrics_collector.get_all_metrics()
        assert len(all_metrics) == 2
        assert all_metrics["metric1"]["value"] == 10
        assert all_metrics["metric2"]["value"] == 5

    def test_aggregate_metrics(self, metrics_collector: MetricsCollector) -> None:
        """Test metric aggregation"""
        metric = Metric(
            name="test_aggregate",
            type=MetricType.GAUGE,
            description="Test aggregate",
        )
        metrics_collector.register_metric(metric)
        
        for i in range(10):
            metrics_collector.record_metric("test_aggregate", i)
        
        stats = metrics_collector.aggregate_metric("test_aggregate")
        assert stats["count"] == 10
        assert stats["min"] == 0
        assert stats["max"] == 9
        assert stats["mean"] == 4.5
        assert stats["sum"] == 45

    def test_metrics_export(self, metrics_collector: MetricsCollector) -> None:
        """Test metrics export"""
        metric = Metric(name="test_export", type=MetricType.GAUGE)
        metrics_collector.register_metric(metric)
        metrics_collector.record_metric("test_export", 42.0)
        
        exported = metrics_collector.export_metrics()
        assert "test_export" in exported
        assert exported["test_export"]["value"] == 42.0


# ============================================================
# ALERT TESTS
# ============================================================

class TestAlertManager:
    """
    Tests for AlertManager
    """

    def test_alert_manager_initialization(self, alert_manager: AlertManager) -> None:
        """Test alert manager initialization"""
        assert alert_manager is not None
        assert alert_manager.alerts is not None
        assert alert_manager.rules is not None
        assert alert_manager.notifiers is not None

    def test_create_alert(self, alert_manager: AlertManager) -> None:
        """Test alert creation"""
        alert = Alert(
            name="test_alert",
            description="Test alert",
            severity=AlertSeverity.WARNING,
            condition="metric > 100",
        )
        alert_manager.create_alert(alert)
        assert "test_alert" in alert_manager.alerts

    def test_trigger_alert(self, alert_manager: AlertManager) -> None:
        """Test alert triggering"""
        def mock_notifier(alert: Alert) -> None:
            alert.notified = True
        
        alert = Alert(
            name="test_trigger",
            description="Test trigger",
            severity=AlertSeverity.CRITICAL,
            condition="metric > 100",
            notifiers=[mock_notifier],
        )
        alert_manager.create_alert(alert)
        
        # Trigger alert
        alert_manager.trigger_alert("test_trigger", {"metric": 150})
        assert alert_manager.alerts["test_trigger"].status == AlertStatus.TRIGGERED
        assert alert_manager.alerts["test_trigger"].notified is True

    def test_resolve_alert(self, alert_manager: AlertManager) -> None:
        """Test alert resolution"""
        alert = Alert(
            name="test_resolve",
            description="Test resolve",
            severity=AlertSeverity.WARNING,
            condition="metric > 100",
        )
        alert_manager.create_alert(alert)
        
        # Trigger alert
        alert_manager.trigger_alert("test_resolve", {"metric": 150})
        assert alert_manager.alerts["test_resolve"].status == AlertStatus.TRIGGERED
        
        # Resolve alert
        alert_manager.resolve_alert("test_resolve")
        assert alert_manager.alerts["test_resolve"].status == AlertStatus.RESOLVED

    def test_alert_conditions(self, alert_manager: AlertManager) -> None:
        """Test alert conditions"""
        def condition(metrics: Dict[str, Any]) -> bool:
            return metrics.get("value", 0) > 100
        
        alert = Alert(
            name="test_condition",
            description="Test condition",
            severity=AlertSeverity.WARNING,
            condition=condition,
        )
        alert_manager.create_alert(alert)
        
        # Check condition
        assert alert_manager.check_condition("test_condition", {"value": 50}) is False
        assert alert_manager.check_condition("test_condition", {"value": 150}) is True

    def test_multiple_notifiers(self, alert_manager: AlertManager) -> None:
        """Test multiple notifiers"""
        notifier1_called = False
        notifier2_called = False
        
        def notifier1(alert: Alert) -> None:
            nonlocal notifier1_called
            notifier1_called = True
        
        def notifier2(alert: Alert) -> None:
            nonlocal notifier2_called
            notifier2_called = True
        
        alert = Alert(
            name="test_notifiers",
            description="Test notifiers",
            severity=AlertSeverity.CRITICAL,
            condition="metric > 100",
            notifiers=[notifier1, notifier2],
        )
        alert_manager.create_alert(alert)
        
        alert_manager.trigger_alert("test_notifiers", {"metric": 150})
        assert notifier1_called is True
        assert notifier2_called is True

    def test_alert_history(self, alert_manager: AlertManager) -> None:
        """Test alert history"""
        alert = Alert(
            name="test_history",
            description="Test history",
            severity=AlertSeverity.WARNING,
            condition="metric > 100",
        )
        alert_manager.create_alert(alert)
        
        # Trigger and resolve multiple times
        alert_manager.trigger_alert("test_history", {"metric": 150})
        alert_manager.resolve_alert("test_history")
        alert_manager.trigger_alert("test_history", {"metric": 200})
        
        history = alert_manager.get_alert_history("test_history")
        assert len(history) == 4  # 2 trigger + 2 resolve

    def test_alert_acknowledge(self, alert_manager: AlertManager) -> None:
        """Test alert acknowledgment"""
        alert = Alert(
            name="test_acknowledge",
            description="Test acknowledge",
            severity=AlertSeverity.WARNING,
            condition="metric > 100",
        )
        alert_manager.create_alert(alert)
        
        alert_manager.trigger_alert("test_acknowledge", {"metric": 150})
        alert_manager.acknowledge_alert("test_acknowledge", "test_user")
        
        assert alert_manager.alerts["test_acknowledge"].status == AlertStatus.ACKNOWLEDGED
        assert alert_manager.alerts["test_acknowledge"].acknowledged_by == "test_user"


# ============================================================
# HEALTH CHECK TESTS
# ============================================================

class TestHealthChecker:
    """
    Tests for HealthChecker
    """

    def test_health_checker_initialization(self, health_checker: HealthChecker) -> None:
        """Test health checker initialization"""
        assert health_checker is not None
        assert health_checker.checks is not None
        assert health_checker.results is not None

    def test_register_check(self, health_checker: HealthChecker) -> None:
        """Test check registration"""
        def check_func() -> HealthStatus:
            return HealthStatus.HEALTHY
        
        health_check = HealthCheck(
            name="test_check",
            check_func=check_func,
            interval=60,
        )
        health_checker.register_check(health_check)
        assert "test_check" in health_checker.checks

    def test_run_check(self, health_checker: HealthChecker) -> None:
        """Test check execution"""
        def check_func() -> HealthStatus:
            return HealthStatus.HEALTHY
        
        health_check = HealthCheck(
            name="test_run",
            check_func=check_func,
            interval=60,
        )
        health_checker.register_check(health_check)
        
        result = health_checker.run_check("test_run")
        assert result == HealthStatus.HEALTHY

    def test_run_all_checks(self, health_checker: HealthChecker) -> None:
        """Test running all checks"""
        def healthy_check() -> HealthStatus:
            return HealthStatus.HEALTHY
        
        def degraded_check() -> HealthStatus:
            return HealthStatus.DEGRADED
        
        health_checker.register_check(HealthCheck("healthy", healthy_check))
        health_checker.register_check(HealthCheck("degraded", degraded_check))
        
        results = health_checker.run_all_checks()
        assert results["healthy"] == HealthStatus.HEALTHY
        assert results["degraded"] == HealthStatus.DEGRADED

    def test_check_timeout(self, health_checker: HealthChecker) -> None:
        """Test check timeout"""
        import time
        
        def slow_check() -> HealthStatus:
            time.sleep(2)
            return HealthStatus.HEALTHY
        
        health_check = HealthCheck(
            name="slow_check",
            check_func=slow_check,
            interval=60,
            timeout=1,
        )
        health_checker.register_check(health_check)
        
        result = health_checker.run_check("slow_check")
        assert result == HealthStatus.UNHEALTHY  # Should timeout

    def test_check_retry(self, health_checker: HealthChecker) -> None:
        """Test check retry"""
        attempt_count = 0
        
        def flaky_check() -> HealthStatus:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise Exception("Temporary failure")
            return HealthStatus.HEALTHY
        
        health_check = HealthCheck(
            name="flaky_check",
            check_func=flaky_check,
            interval=60,
            retry_count=2,
        )
        health_checker.register_check(health_check)
        
        result = health_checker.run_check("flaky_check")
        assert result == HealthStatus.HEALTHY
        assert attempt_count == 2

    def test_check_status_aggregation(self, health_checker: HealthChecker) -> None:
        """Test health status aggregation"""
        health_checker.register_check(HealthCheck("check1", lambda: HealthStatus.HEALTHY))
        health_checker.register_check(HealthCheck("check2", lambda: HealthStatus.DEGRADED))
        health_checker.register_check(HealthCheck("check3", lambda: HealthStatus.HEALTHY))
        
        overall = health_checker.get_overall_status()
        assert overall == HealthStatus.DEGRADED


# ============================================================
# LOG MANAGER TESTS
# ============================================================

class TestLogManager:
    """
    Tests for LogManager
    """

    def test_log_manager_initialization(self, log_manager: LogManager) -> None:
        """Test log manager initialization"""
        assert log_manager is not None
        assert log_manager.logs is not None
        assert log_manager.handlers is not None

    def test_add_log(self, log_manager: LogManager) -> None:
        """Test log addition"""
        log_entry = LogEntry(
            level=LogLevel.INFO,
            message="Test message",
            source="test_module",
        )
        log_manager.add_log(log_entry)
        assert len(log_manager.logs) == 1

    def test_add_log_with_context(self, log_manager: LogManager) -> None:
        """Test log addition with context"""
        log_entry = LogEntry(
            level=LogLevel.ERROR,
            message="Error occurred",
            source="test_module",
            context={"error": "Test error", "user": "test_user"},
        )
        log_manager.add_log(log_entry)
        
        saved_log = log_manager.logs[0]
        assert saved_log.context["error"] == "Test error"
        assert saved_log.context["user"] == "test_user"

    def test_get_logs_by_level(self, log_manager: LogManager) -> None:
        """Test getting logs by level"""
        log_manager.add_log(LogEntry(level=LogLevel.INFO, message="Info 1", source="test"))
        log_manager.add_log(LogEntry(level=LogLevel.ERROR, message="Error 1", source="test"))
        log_manager.add_log(LogEntry(level=LogLevel.INFO, message="Info 2", source="test"))
        
        info_logs = log_manager.get_logs_by_level(LogLevel.INFO)
        assert len(info_logs) == 2
        
        error_logs = log_manager.get_logs_by_level(LogLevel.ERROR)
        assert len(error_logs) == 1

    def test_get_logs_by_source(self, log_manager: LogManager) -> None:
        """Test getting logs by source"""
        log_manager.add_log(LogEntry(level=LogLevel.INFO, message="Test 1", source="module1"))
        log_manager.add_log(LogEntry(level=LogLevel.ERROR, message="Test 2", source="module2"))
        log_manager.add_log(LogEntry(level=LogLevel.INFO, message="Test 3", source="module1"))
        
        module1_logs = log_manager.get_logs_by_source("module1")
        assert len(module1_logs) == 2

    def test_get_logs_by_time_range(self, log_manager: LogManager) -> None:
        """Test getting logs by time range"""
        now = datetime.now()
        
        log_manager.add_log(LogEntry(
            level=LogLevel.INFO,
            message="Old log",
            source="test",
            timestamp=now - timedelta(hours=2),
        ))
        log_manager.add_log(LogEntry(
            level=LogLevel.INFO,
            message="New log",
            source="test",
            timestamp=now - timedelta(minutes=30),
        ))
        
        recent_logs = log_manager.get_logs_by_time_range(
            start=now - timedelta(hours=1),
            end=now,
        )
        assert len(recent_logs) == 1
        assert recent_logs[0].message == "New log"

    def test_log_handler(self, log_manager: LogManager) -> None:
        """Test log handler"""
        handler_called = False
        
        def test_handler(log_entry: LogEntry) -> None:
            nonlocal handler_called
            handler_called = True
        
        log_manager.add_handler(test_handler)
        log_manager.add_log(LogEntry(level=LogLevel.INFO, message="Test", source="test"))
        
        assert handler_called is True

    def test_log_export(self, log_manager: LogManager) -> None:
        """Test log export"""
        log_manager.add_log(LogEntry(level=LogLevel.INFO, message="Test 1", source="test"))
        log_manager.add_log(LogEntry(level=LogLevel.ERROR, message="Test 2", source="test"))
        
        exported = log_manager.export_logs()
        assert len(exported) == 2
        assert exported[0]["message"] == "Test 1"
        assert exported[1]["message"] == "Test 2"


# ============================================================
# PERFORMANCE MONITOR TESTS
# ============================================================

class TestPerformanceMonitor:
    """
    Tests for PerformanceMonitor
    """

    def test_performance_monitor_initialization(self, performance_monitor: PerformanceMonitor) -> None:
        """Test performance monitor initialization"""
        assert performance_monitor is not None
        assert performance_monitor.metrics is not None
        assert performance_monitor.timers is not None

    def test_start_timer(self, performance_monitor: PerformanceMonitor) -> None:
        """Test timer start"""
        timer_id = performance_monitor.start_timer("test_operation")
        assert timer_id in performance_monitor.timers
        assert performance_monitor.timers[timer_id]["start"] is not None

    def test_stop_timer(self, performance_monitor: PerformanceMonitor) -> None:
        """Test timer stop"""
        timer_id = performance_monitor.start_timer("test_operation")
        time.sleep(0.1)
        duration = performance_monitor.stop_timer(timer_id)
        
        assert duration > 0
        assert duration < 1.0
        assert "test_operation" in performance_monitor.metrics

    def test_measure_function(self, performance_monitor: PerformanceMonitor) -> None:
        """Test function measurement"""
        @performance_monitor.measure("test_function")
        def test_func() -> str:
            time.sleep(0.05)
            return "result"
        
        result = test_func()
        assert result == "result"
        
        metrics = performance_monitor.get_metrics("test_function")
        assert metrics["count"] == 1
        assert metrics["min"] > 0
        assert metrics["max"] > 0
        assert metrics["mean"] > 0

    def test_measure_async_function(self, performance_monitor: PerformanceMonitor) -> None:
        """Test async function measurement"""
        @performance_monitor.measure("test_async")
        async def test_async_func() -> str:
            await asyncio.sleep(0.05)
            return "result"
        
        import asyncio
        result = asyncio.run(test_async_func())
        assert result == "result"
        
        metrics = performance_monitor.get_metrics("test_async")
        assert metrics["count"] == 1

    def test_get_performance_report(self, performance_monitor: PerformanceMonitor) -> None:
        """Test performance report generation"""
        # Record some metrics
        for i in range(5):
            timer_id = performance_monitor.start_timer("test_op")
            time.sleep(0.01)
            performance_monitor.stop_timer(timer_id)
        
        report = performance_monitor.get_performance_report()
        assert "test_op" in report
        assert report["test_op"]["count"] == 5
        assert report["test_op"]["mean"] > 0

    def test_performance_thresholds(self, performance_monitor: PerformanceMonitor) -> None:
        """Test performance thresholds"""
        threshold_called = False
        
        def threshold_callback(metric: str, value: float, threshold: float) -> None:
            nonlocal threshold_called
            threshold_called = True
        
        performance_monitor.set_threshold("slow_op", 0.1, threshold_callback)
        
        # Record slow operation
        timer_id = performance_monitor.start_timer("slow_op")
        time.sleep(0.2)
        performance_monitor.stop_timer(timer_id)
        
        assert threshold_called is True


# ============================================================
# DASHBOARD TESTS
# ============================================================

class TestDashboardGenerator:
    """
    Tests for DashboardGenerator
    """

    def test_dashboard_generator_initialization(self, dashboard_generator: DashboardGenerator) -> None:
        """Test dashboard generator initialization"""
        assert dashboard_generator is not None
        assert dashboard_generator.widgets is not None
        assert dashboard_generator.layout is not None

    def test_add_widget(self, dashboard_generator: DashboardGenerator) -> None:
        """Test widget addition"""
        dashboard_generator.add_widget(
            name="test_widget",
            type="chart",
            data={"value": 42},
        )
        assert "test_widget" in dashboard_generator.widgets

    def test_generate_dashboard(self, dashboard_generator: DashboardGenerator) -> None:
        """Test dashboard generation"""
        dashboard_generator.add_widget(
            name="widget1",
            type="metric",
            data={"value": 100, "label": "Total PnL"},
        )
        dashboard_generator.add_widget(
            name="widget2",
            type="chart",
            data={"series": [1, 2, 3, 4, 5]},
        )
        
        dashboard = dashboard_generator.generate_dashboard()
        assert "widgets" in dashboard
        assert len(dashboard["widgets"]) == 2
        assert dashboard["widgets"][0]["name"] == "widget1"

    def test_widget_types(self, dashboard_generator: DashboardGenerator) -> None:
        """Test different widget types"""
        widget_types = ["metric", "chart", "table", "status", "alert"]
        
        for widget_type in widget_types:
            dashboard_generator.add_widget(
                name=f"widget_{widget_type}",
                type=widget_type,
                data={"test": "data"},
            )
        
        widgets = dashboard_generator.get_widgets()
        assert len(widgets) == len(widget_types)

    def test_dashboard_layout(self, dashboard_generator: DashboardGenerator) -> None:
        """Test dashboard layout"""
        dashboard_generator.set_layout({
            "rows": 3,
            "columns": 2,
            "grid": [
                [{"widget": "widget1", "span": 2}],
                [{"widget": "widget2", "span": 1}, {"widget": "widget3", "span": 1}],
            ]
        })
        
        layout = dashboard_generator.get_layout()
        assert layout["rows"] == 3
        assert layout["columns"] == 2
        assert len(layout["grid"]) == 2

    def test_export_dashboard(self, dashboard_generator: DashboardGenerator) -> None:
        """Test dashboard export"""
        dashboard_generator.add_widget(
            name="export_widget",
            type="metric",
            data={"value": 42},
        )
        
        exported = dashboard_generator.export_dashboard()
        assert "widgets" in exported
        assert exported["widgets"][0]["name"] == "export_widget"


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestMonitoringIntegration:
    """
    Integration tests for monitoring components
    """

    def test_metrics_alert_integration(self) -> None:
        """Test metrics and alert integration"""
        metrics = MetricsCollector()
        alerts = AlertManager()
        
        # Create metric
        metric = Metric(name="test_metric", type=MetricType.GAUGE)
        metrics.register_metric(metric)
        
        # Create alert
        alert = Alert(
            name="high_metric",
            description="Metric is too high",
            severity=AlertSeverity.CRITICAL,
            condition=lambda m: m.get("test_metric", 0) > 100,
        )
        alerts.create_alert(alert)
        
        # Record metric and check alert
        metrics.record_metric("test_metric", 150)
        metric_value = metrics.get_metric("test_metric")["value"]
        
        # Check alert condition
        condition_met = alert.condition({"test_metric": metric_value})
        assert condition_met is True
        
        # Trigger alert
        alerts.trigger_alert("high_metric", {"test_metric": metric_value})
        assert alerts.alerts["high_metric"].status == AlertStatus.TRIGGERED

    def test_health_log_integration(self) -> None:
        """Test health and log integration"""
        health = HealthChecker()
        logs = LogManager()
        
        def check_with_logging() -> HealthStatus:
            logs.add_log(LogEntry(
                level=LogLevel.INFO,
                message="Running health check",
                source="health_checker",
            ))
            return HealthStatus.HEALTHY
        
        health.register_check(HealthCheck("test_check", check_with_logging))
        health.run_check("test_check")
        
        # Verify log was added
        health_logs = logs.get_logs_by_source("health_checker")
        assert len(health_logs) == 1
        assert health_logs[0].message == "Running health check"

    def test_performance_dashboard_integration(self) -> None:
        """Test performance and dashboard integration"""
        performance = PerformanceMonitor()
        dashboard = DashboardGenerator()
        
        # Measure operations
        timer_id = performance.start_timer("api_call")
        time.sleep(0.05)
        performance.stop_timer(timer_id)
        
        # Get performance metrics
        metrics = performance.get_metrics("api_call")
        
        # Add to dashboard
        dashboard.add_widget(
            name="api_performance",
            type="chart",
            data={
                "series": [metrics["min"], metrics["mean"], metrics["max"]],
                "labels": ["Min", "Mean", "Max"],
            },
        )
        
        # Generate dashboard
        dashboard_data = dashboard.generate_dashboard()
        assert len(dashboard_data["widgets"]) == 1
        assert dashboard_data["widgets"][0]["name"] == "api_performance"


# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestMonitoringPerformance:
    """
    Performance tests for monitoring components
    """

    def test_metrics_performance(self) -> None:
        """Test metrics performance"""
        metrics = MetricsCollector()
        
        # Register metric
        metric = Metric(name="perf_test", type=MetricType.COUNTER)
        metrics.register_metric(metric)
        
        start = time.time()
        for i in range(10000):
            metrics.record_metric("perf_test", 1)
        duration = time.time() - start
        
        assert duration < 0.5, f"Metrics recording too slow: {duration:.3f}s"

    def test_alert_performance(self) -> None:
        """Test alert performance"""
        alerts = AlertManager()
        
        # Create alert
        alert = Alert(
            name="perf_alert",
            description="Performance test",
            severity=AlertSeverity.WARNING,
            condition=lambda m: m.get("value", 0) > 100,
        )
        alerts.create_alert(alert)
        
        start = time.time()
        for i in range(1000):
            if i % 2 == 0:
                alerts.trigger_alert("perf_alert", {"value": 150})
            else:
                alerts.resolve_alert("perf_alert")
        duration = time.time() - start
        
        assert duration < 0.5, f"Alert operations too slow: {duration:.3f}s"


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "TestMetricsCollector",
    "TestAlertManager",
    "TestHealthChecker",
    "TestLogManager",
    "TestPerformanceMonitor",
    "TestDashboardGenerator",
    "TestMonitoringIntegration",
    "TestMonitoringPerformance",
]

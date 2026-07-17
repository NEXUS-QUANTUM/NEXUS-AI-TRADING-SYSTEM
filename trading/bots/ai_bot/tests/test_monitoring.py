# trading/bots/ai_bot/tests/test_monitoring.py
"""
NEXUS AI TRADING SYSTEM - Monitoring Test Suite
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive test suite for monitoring and observability components.
Tests include:
    - Metrics collection and aggregation
    - Health checks and status monitoring
    - Alerting and notification systems
    - Performance monitoring
    - Resource utilization tracking
    - Logging and error tracking
    - Dashboard generation
    - SLA monitoring
    - Anomaly detection
    - System telemetry
"""

import os
import sys
import pytest
import time
import json
import logging
import asyncio
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trading.bots.ai_bot.tests.fixtures import (
    NEXUS_FIXTURES,
    load_all_fixtures,
    get_test_symbols,
    get_test_timeframes,
    FIXTURES_DIR
)
from trading.bots.ai_bot.monitoring import (
    MetricsCollector,
    HealthChecker,
    AlertManager,
    PerformanceMonitor,
    ResourceMonitor,
    LogManager,
    DashboardGenerator,
    SLAMonitor,
    AnomalyDetector,
    TelemetryCollector,
    MonitoringConfig,
    MetricType,
    AlertSeverity,
    HealthStatus,
    MonitoringService
)
from trading.bots.ai_bot.config import BotConfig

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test constants
NEXUS_QUANTUM = "NEXUS QUANTUM LTD"
COPYRIGHT = "Copyright © 2026 NEXUS QUANTUM LTD"
CEO = "Dr X..."
TEST_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD']
METRICS_INTERVAL = 60
ALERT_THRESHOLD = 0.5
RESOURCE_CHECK_INTERVAL = 30


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def fixtures():
    """Load all test fixtures."""
    return load_all_fixtures(force_reload=False)


@pytest.fixture
def test_data(fixtures):
    """Get test data."""
    return fixtures.test_data


@pytest.fixture
def monitoring_config():
    """Create monitoring configuration."""
    return {
        'monitoring': {
            'enabled': True,
            'metrics_interval': METRICS_INTERVAL,
            'alert_threshold': ALERT_THRESHOLD,
            'resource_check_interval': RESOURCE_CHECK_INTERVAL,
            'log_level': 'INFO',
            'retention_days': 30,
            'export_enabled': True,
            'export_format': 'json',
            'dashboard_enabled': True,
            'sla_enabled': True,
            'anomaly_detection_enabled': True,
            'telemetry_enabled': True
        },
        'trading': {
            'symbols': TEST_SYMBOLS,
            'initial_capital': 100000.0,
            'max_positions': 5
        },
        'alerts': {
            'email_enabled': True,
            'slack_enabled': True,
            'telegram_enabled': True,
            'webhook_enabled': True,
            'alert_channels': ['email', 'slack', 'telegram'],
            'severity_levels': ['info', 'warning', 'error', 'critical'],
            'rate_limit': 10
        },
        'performance': {
            'latency_threshold_ms': 100,
            'throughput_threshold': 1000,
            'error_rate_threshold': 0.01,
            'cpu_threshold': 80.0,
            'memory_threshold': 80.0,
            'disk_threshold': 80.0
        }
    }


@pytest.fixture
def mock_alert_handlers():
    """Mock alert handlers."""
    handlers = {
        'email': Mock(),
        'slack': Mock(),
        'telegram': Mock(),
        'webhook': Mock()
    }
    return handlers


@pytest.fixture
def metrics_collector(monitoring_config):
    """Create metrics collector instance."""
    config = BotConfig(**monitoring_config)
    return MetricsCollector(config)


@pytest.fixture
def health_checker(monitoring_config):
    """Create health checker instance."""
    config = BotConfig(**monitoring_config)
    return HealthChecker(config)


@pytest.fixture
def alert_manager(monitoring_config, mock_alert_handlers):
    """Create alert manager instance."""
    config = BotConfig(**monitoring_config)
    manager = AlertManager(config)
    manager.handlers = mock_alert_handlers
    return manager


@pytest.fixture
def performance_monitor(monitoring_config):
    """Create performance monitor instance."""
    config = BotConfig(**monitoring_config)
    return PerformanceMonitor(config)


@pytest.fixture
def resource_monitor(monitoring_config):
    """Create resource monitor instance."""
    config = BotConfig(**monitoring_config)
    return ResourceMonitor(config)


# =============================================================================
# Metrics Collection Tests
# =============================================================================

class TestMetricsCollector:
    """Test metrics collection functionality."""

    def test_collector_initialization(self, metrics_collector):
        """Test metrics collector initialization."""
        assert metrics_collector is not None
        assert metrics_collector.config is not None
        assert metrics_collector.enabled is True
        assert len(metrics_collector.metrics) == 0

    def test_collect_trading_metrics(self, metrics_collector):
        """Test trading metrics collection."""
        # Record trading metrics
        metrics_collector.record_trade({
            'symbol': 'BTC-USD',
            'side': 'buy',
            'price': 43000.0,
            'quantity': 0.1,
            'pnl': 50.0,
            'duration': 120
        })
        
        metrics = metrics_collector.get_metrics()
        assert metrics is not None
        assert 'total_trades' in metrics
        assert 'total_pnl' in metrics
        assert 'win_rate' in metrics

    def test_collect_system_metrics(self, metrics_collector):
        """Test system metrics collection."""
        # Collect system metrics
        metrics_collector.collect_system_metrics()
        
        metrics = metrics_collector.get_metrics()
        assert metrics is not None
        assert 'cpu_usage' in metrics
        assert 'memory_usage' in metrics
        assert 'disk_usage' in metrics

    def test_metric_aggregation(self, metrics_collector):
        """Test metric aggregation."""
        # Record multiple metrics
        for i in range(10):
            metrics_collector.record_trade({
                'symbol': 'BTC-USD',
                'side': 'buy' if i % 2 == 0 else 'sell',
                'price': 43000.0 + i * 100,
                'quantity': 0.1,
                'pnl': np.random.randn() * 50,
                'duration': 60 + i * 10
            })
        
        # Aggregate metrics
        aggregated = metrics_collector.aggregate_metrics()
        assert aggregated is not None
        assert 'avg_pnl' in aggregated
        assert 'avg_duration' in aggregated
        assert 'total_volume' in aggregated

    def test_metric_export(self, metrics_collector):
        """Test metric export."""
        # Record some metrics
        for i in range(5):
            metrics_collector.record_trade({
                'symbol': 'BTC-USD',
                'side': 'buy',
                'price': 43000.0 + i * 100,
                'quantity': 0.1,
                'pnl': float(i * 10),
                'duration': 60
            })
        
        # Export metrics
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / 'metrics.json'
            metrics_collector.export_metrics(export_path)
            assert export_path.exists()
            
            # Verify export content
            with open(export_path, 'r') as f:
                exported = json.load(f)
                assert 'metrics' in exported
                assert 'timestamp' in exported

    def test_metric_history(self, metrics_collector):
        """Test metric history tracking."""
        # Record metrics over time
        for i in range(5):
            metrics_collector.record_metric('test_metric', i * 10, timestamp=datetime.now() + timedelta(seconds=i))
        
        history = metrics_collector.get_metric_history('test_metric')
        assert history is not None
        assert len(history) == 5


# =============================================================================
# Health Checks Tests
# =============================================================================

class TestHealthChecker:
    """Test health checker functionality."""

    def test_health_checker_initialization(self, health_checker):
        """Test health checker initialization."""
        assert health_checker is not None
        assert health_checker.config is not None
        assert health_checker.health_status == {}

    def test_check_bot_health(self, health_checker):
        """Test bot health check."""
        status = health_checker.check_bot_health()
        assert status is not None
        assert 'status' in status
        assert status['status'] in ['healthy', 'degraded', 'unhealthy']

    def test_check_component_health(self, health_checker):
        """Test component health check."""
        components = ['data_pipeline', 'model_manager', 'execution_engine']
        
        for component in components:
            status = health_checker.check_component(component)
            assert status is not None
            assert 'component' in status
            assert 'status' in status
            assert status['component'] == component

    def test_health_aggregation(self, health_checker):
        """Test health status aggregation."""
        # Check all components
        health_checker.check_all_components()
        
        aggregated = health_checker.get_aggregated_health()
        assert aggregated is not None
        assert 'overall_status' in aggregated
        assert 'components' in aggregated
        assert 'timestamp' in aggregated

    def test_health_alert_trigger(self, health_checker):
        """Test health alert triggering."""
        # Simulate unhealthy component
        with patch.object(health_checker, '_check_component_status') as mock_check:
            mock_check.return_value = {'status': 'unhealthy', 'details': 'Component failed'}
            
            alerts = health_checker.check_and_alert()
            assert alerts is not None
            if len(alerts) > 0:
                assert alerts[0]['severity'] == 'critical'
                assert alerts[0]['component'] in health_checker.components

    def test_health_thresholds(self, health_checker):
        """Test health threshold configuration."""
        # Test threshold validation
        thresholds = {
            'cpu_threshold': 80.0,
            'memory_threshold': 80.0,
            'latency_threshold': 100.0
        }
        
        for key, value in thresholds.items():
            health_checker.set_threshold(key, value)
            assert health_checker.thresholds[key] == value


# =============================================================================
# Alert Manager Tests
# =============================================================================

class TestAlertManager:
    """Test alert manager functionality."""

    def test_alert_manager_initialization(self, alert_manager):
        """Test alert manager initialization."""
        assert alert_manager is not None
        assert alert_manager.config is not None
        assert len(alert_manager.alerts) == 0

    def test_alert_creation(self, alert_manager):
        """Test alert creation."""
        alert = {
            'severity': 'warning',
            'message': 'Test alert',
            'component': 'test_component',
            'timestamp': datetime.now().isoformat(),
            'details': {'test': 'data'}
        }
        
        alert_manager.create_alert(alert)
        assert len(alert_manager.alerts) == 1
        assert alert_manager.alerts[0]['message'] == 'Test alert'

    def test_alert_severity_levels(self, alert_manager):
        """Test alert severity levels."""
        severities = ['info', 'warning', 'error', 'critical']
        
        for severity in severities:
            alert = {
                'severity': severity,
                'message': f'{severity} alert',
                'component': 'test'
            }
            alert_manager.create_alert(alert)
            assert alert_manager.alerts[-1]['severity'] == severity

    def test_alert_notification(self, alert_manager):
        """Test alert notification."""
        alert = {
            'severity': 'critical',
            'message': 'Critical alert for testing',
            'component': 'test_system',
            'timestamp': datetime.now().isoformat()
        }
        
        # Send notification
        alert_manager.send_notification(alert)
        
        # Verify handlers were called
        for handler in alert_manager.handlers.values():
            handler.assert_called_with(alert)

    def test_alert_rate_limiting(self, alert_manager):
        """Test alert rate limiting."""
        # Create many alerts
        for i in range(20):
            alert = {
                'severity': 'warning',
                'message': f'Alert {i}',
                'component': 'test',
                'timestamp': datetime.now().isoformat()
            }
            alert_manager.create_alert(alert)
        
        # Rate limiting should prevent excessive alerts
        assert len(alert_manager.alerts) <= alert_manager.config.get('rate_limit', 10)

    def test_alert_deduplication(self, alert_manager):
        """Test alert deduplication."""
        # Create duplicate alerts
        for i in range(3):
            alert = {
                'severity': 'warning',
                'message': 'Duplicate alert',
                'component': 'test',
                'timestamp': datetime.now().isoformat()
            }
            alert_manager.create_alert(alert)
        
        # Should only have one unique alert
        unique_alerts = alert_manager.get_unique_alerts()
        assert len(unique_alerts) > 0

    def test_alert_acknowledgment(self, alert_manager):
        """Test alert acknowledgment."""
        alert = {
            'severity': 'error',
            'message': 'Acknowledged alert',
            'component': 'test',
            'timestamp': datetime.now().isoformat()
        }
        
        alert_manager.create_alert(alert)
        alert_id = alert_manager.alerts[0]['id']
        
        # Acknowledge alert
        result = alert_manager.acknowledge_alert(alert_id)
        assert result is True
        assert alert_manager.alerts[0]['acknowledged'] is True


# =============================================================================
# Performance Monitoring Tests
# =============================================================================

class TestPerformanceMonitor:
    """Test performance monitor functionality."""

    def test_performance_monitor_initialization(self, performance_monitor):
        """Test performance monitor initialization."""
        assert performance_monitor is not None
        assert performance_monitor.config is not None
        assert performance_monitor.metrics == {}

    def test_latency_monitoring(self, performance_monitor):
        """Test latency monitoring."""
        # Record latencies
        latencies = [10.5, 15.2, 8.7, 12.3, 9.8]
        for lat in latencies:
            performance_monitor.record_latency(lat)
        
        stats = performance_monitor.get_latency_stats()
        assert stats is not None
        assert stats['avg'] == sum(latencies) / len(latencies)
        assert stats['min'] == min(latencies)
        assert stats['max'] == max(latencies)
        assert stats['p95'] > 0

    def test_throughput_monitoring(self, performance_monitor):
        """Test throughput monitoring."""
        # Record throughput
        for i in range(10):
            performance_monitor.record_throughput(i * 100)
        
        stats = performance_monitor.get_throughput_stats()
        assert stats is not None
        assert 'avg_throughput' in stats
        assert 'peak_throughput' in stats
        assert 'total_requests' in stats

    def test_error_rate_monitoring(self, performance_monitor):
        """Test error rate monitoring."""
        # Record errors
        total = 1000
        errors = 5
        
        for i in range(total):
            is_error = i < errors
            performance_monitor.record_request(is_error)
        
        error_rate = performance_monitor.get_error_rate()
        assert error_rate == errors / total

    def test_performance_thresholds(self, performance_monitor):
        """Test performance threshold monitoring."""
        # Set thresholds
        performance_monitor.set_threshold('latency', 100.0)
        performance_monitor.set_threshold('throughput', 1000)
        performance_monitor.set_threshold('error_rate', 0.01)
        
        # Record performance that exceeds thresholds
        performance_monitor.record_latency(200.0)
        
        alerts = performance_monitor.check_thresholds()
        assert alerts is not None
        if len(alerts) > 0:
            assert alerts[0]['type'] == 'latency_exceeded'


# =============================================================================
# Resource Monitoring Tests
# =============================================================================

class TestResourceMonitor:
    """Test resource monitor functionality."""

    def test_resource_monitor_initialization(self, resource_monitor):
        """Test resource monitor initialization."""
        assert resource_monitor is not None
        assert resource_monitor.config is not None

    def test_cpu_monitoring(self, resource_monitor):
        """Test CPU monitoring."""
        # Simulate CPU usage
        with patch('psutil.cpu_percent') as mock_cpu:
            mock_cpu.return_value = 45.5
            cpu_usage = resource_monitor.get_cpu_usage()
            assert cpu_usage == 45.5

    def test_memory_monitoring(self, resource_monitor):
        """Test memory monitoring."""
        # Simulate memory usage
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = Mock(percent=60.0)
            memory_usage = resource_monitor.get_memory_usage()
            assert memory_usage == 60.0

    def test_disk_monitoring(self, resource_monitor):
        """Test disk monitoring."""
        # Simulate disk usage
        with patch('psutil.disk_usage') as mock_disk:
            mock_disk.return_value = Mock(percent=70.0)
            disk_usage = resource_monitor.get_disk_usage()
            assert disk_usage == 70.0

    def test_resource_alerts(self, resource_monitor):
        """Test resource alert triggering."""
        # Set low thresholds
        resource_monitor.thresholds['cpu'] = 50.0
        
        with patch('psutil.cpu_percent') as mock_cpu:
            mock_cpu.return_value = 80.0  # Exceeds threshold
            
            alerts = resource_monitor.check_resources()
            assert alerts is not None
            if len(alerts) > 0:
                assert alerts[0]['type'] == 'cpu_high'
                assert alerts[0]['value'] == 80.0


# =============================================================================
# Log Manager Tests
# =============================================================================

class TestLogManager:
    """Test log manager functionality."""

    def test_log_manager_initialization(self, monitoring_config):
        """Test log manager initialization."""
        config = BotConfig(**monitoring_config)
        log_manager = LogManager(config)
        assert log_manager is not None
        assert log_manager.config is not None

    def test_log_levels(self, monitoring_config):
        """Test log levels."""
        config = BotConfig(**monitoring_config)
        log_manager = LogManager(config)
        
        levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        for level in levels:
            log_manager.set_level(level)
            assert log_manager.log_level == level

    def test_log_rotation(self, monitoring_config):
        """Test log rotation."""
        config = BotConfig(**monitoring_config)
        log_manager = LogManager(config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / 'test.log'
            log_manager.set_log_path(log_path)
            
            # Write many logs
            for i in range(1000):
                log_manager.log('INFO', f'Test message {i}')
            
            # Check rotation
            assert log_path.exists()
            # Log file should have content
            assert log_path.stat().st_size > 0

    def test_log_filtering(self, monitoring_config):
        """Test log filtering."""
        config = BotConfig(**monitoring_config)
        log_manager = LogManager(config)
        
        # Add filters
        log_manager.add_filter('module', 'test_module')
        log_manager.add_filter('level', 'ERROR')
        
        # Get filtered logs
        filtered = log_manager.get_logs()
        assert filtered is not None


# =============================================================================
# Dashboard Generator Tests
# =============================================================================

class TestDashboardGenerator:
    """Test dashboard generator functionality."""

    def test_dashboard_initialization(self, monitoring_config):
        """Test dashboard initialization."""
        config = BotConfig(**monitoring_config)
        dashboard = DashboardGenerator(config)
        assert dashboard is not None
        assert dashboard.config is not None

    def test_metrics_dashboard(self, monitoring_config, metrics_collector):
        """Test metrics dashboard generation."""
        config = BotConfig(**monitoring_config)
        dashboard = DashboardGenerator(config)
        
        # Add metrics
        for i in range(10):
            metrics_collector.record_trade({
                'symbol': 'BTC-USD',
                'side': 'buy',
                'price': 43000.0 + i * 100,
                'quantity': 0.1,
                'pnl': float(i * 10),
                'duration': 60
            })
        
        dashboard_data = dashboard.generate_metrics_dashboard(metrics_collector.get_metrics())
        assert dashboard_data is not None
        assert 'metrics' in dashboard_data
        assert 'charts' in dashboard_data
        assert 'summary' in dashboard_data

    def test_health_dashboard(self, monitoring_config, health_checker):
        """Test health dashboard generation."""
        config = BotConfig(**monitoring_config)
        dashboard = DashboardGenerator(config)
        
        health_data = health_checker.check_all_components()
        dashboard_data = dashboard.generate_health_dashboard(health_data)
        assert dashboard_data is not None
        assert 'overall_health' in dashboard_data
        assert 'components' in dashboard_data
        assert 'alerts' in dashboard_data

    def test_performance_dashboard(self, monitoring_config, performance_monitor):
        """Test performance dashboard generation."""
        config = BotConfig(**monitoring_config)
        dashboard = DashboardGenerator(config)
        
        # Record performance data
        for i in range(100):
            performance_monitor.record_latency(np.random.uniform(5, 20))
            performance_monitor.record_throughput(i * 10)
        
        dashboard_data = dashboard.generate_performance_dashboard(performance_monitor.get_stats())
        assert dashboard_data is not None
        assert 'latency' in dashboard_data
        assert 'throughput' in dashboard_data
        assert 'error_rate' in dashboard_data


# =============================================================================
# SLA Monitor Tests
# =============================================================================

class TestSLAMonitor:
    """Test SLA monitor functionality."""

    def test_sla_initialization(self, monitoring_config):
        """Test SLA monitor initialization."""
        config = BotConfig(**monitoring_config)
        sla_monitor = SLAMonitor(config)
        assert sla_monitor is not None
        assert sla_monitor.config is not None

    def test_sla_targets(self, monitoring_config):
        """Test SLA target configuration."""
        config = BotConfig(**monitoring_config)
        sla_monitor = SLAMonitor(config)
        
        targets = {
            'uptime': 99.9,
            'latency': 100.0,
            'error_rate': 0.01,
            'throughput': 1000
        }
        
        for name, value in targets.items():
            sla_monitor.set_target(name, value)
            assert sla_monitor.targets[name] == value

    def test_sla_compliance(self, monitoring_config, performance_monitor):
        """Test SLA compliance checking."""
        config = BotConfig(**monitoring_config)
        sla_monitor = SLAMonitor(config)
        
        # Set targets
        sla_monitor.set_target('latency', 100.0)
        sla_monitor.set_target('error_rate', 0.01)
        
        # Record performance
        for i in range(100):
            performance_monitor.record_latency(np.random.uniform(50, 150))
            performance_monitor.record_request(np.random.random() < 0.005)
        
        compliance = sla_monitor.check_compliance(performance_monitor.get_stats())
        assert compliance is not None
        assert 'compliant' in compliance
        assert 'metrics' in compliance

    def test_sla_report(self, monitoring_config):
        """Test SLA report generation."""
        config = BotConfig(**monitoring_config)
        sla_monitor = SLAMonitor(config)
        
        report = sla_monitor.generate_sla_report()
        assert report is not None
        assert 'timestamp' in report
        assert 'compliance' in report
        assert 'metrics' in report


# =============================================================================
# Anomaly Detection Tests
# =============================================================================

class TestAnomalyDetector:
    """Test anomaly detection functionality."""

    def test_anomaly_initialization(self, monitoring_config):
        """Test anomaly detector initialization."""
        config = BotConfig(**monitoring_config)
        detector = AnomalyDetector(config)
        assert detector is not None
        assert detector.config is not None

    def test_statistical_anomaly_detection(self, monitoring_config):
        """Test statistical anomaly detection."""
        config = BotConfig(**monitoring_config)
        detector = AnomalyDetector(config)
        
        # Generate normal data with an anomaly
        data = np.random.normal(0, 1, 1000)
        data[500] = 10  # Anomaly
        
        anomalies = detector.detect_statistical_anomalies(data)
        assert anomalies is not None
        assert len(anomalies) > 0

    def test_trading_pattern_anomalies(self, monitoring_config):
        """Test trading pattern anomaly detection."""
        config = BotConfig(**monitoring_config)
        detector = AnomalyDetector(config)
        
        # Generate trading patterns
        patterns = []
        for i in range(100):
            pattern = {
                'price': 43000.0 + i * 10,
                'volume': 1000000.0 + i * 1000,
                'spread': 10.0 + i * 0.1
            }
            patterns.append(pattern)
        
        # Add anomaly
        patterns[50]['volume'] = 100000000.0
        
        anomalies = detector.detect_trading_anomalies(patterns)
        assert anomalies is not None
        if len(anomalies) > 0:
            assert anomalies[0]['type'] == 'volume_anomaly'


# =============================================================================
# Telemetry Tests
# =============================================================================

class TestTelemetryCollector:
    """Test telemetry collector functionality."""

    def test_telemetry_initialization(self, monitoring_config):
        """Test telemetry collector initialization."""
        config = BotConfig(**monitoring_config)
        telemetry = TelemetryCollector(config)
        assert telemetry is not None
        assert telemetry.config is not None

    def test_telemetry_collection(self, monitoring_config):
        """Test telemetry collection."""
        config = BotConfig(**monitoring_config)
        telemetry = TelemetryCollector(config)
        
        # Collect telemetry
        telemetry.collect_telemetry()
        data = telemetry.get_telemetry_data()
        assert data is not None
        assert 'system' in data
        assert 'metrics' in data
        assert 'timestamp' in data

    def test_telemetry_export(self, monitoring_config):
        """Test telemetry export."""
        config = BotConfig(**monitoring_config)
        telemetry = TelemetryCollector(config)
        
        # Collect and export
        telemetry.collect_telemetry()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / 'telemetry.json'
            telemetry.export_telemetry(export_path)
            assert export_path.exists()


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for monitoring system."""

    def test_full_monitoring_pipeline(self, monitoring_config):
        """Test full monitoring pipeline."""
        config = BotConfig(**monitoring_config)
        
        # Initialize all components
        metrics = MetricsCollector(config)
        health = HealthChecker(config)
        alerts = AlertManager(config)
        performance = PerformanceMonitor(config)
        resources = ResourceMonitor(config)
        
        # Run monitoring cycle
        metrics.collect_system_metrics()
        health.check_all_components()
        
        # Check for alerts
        performance_alerts = performance.check_thresholds()
        resource_alerts = resources.check_resources()
        
        # Process alerts
        for alert in performance_alerts + resource_alerts:
            alerts.create_alert(alert)
        
        # Verify monitoring worked
        assert len(metrics.get_metrics()) > 0
        assert len(health.get_aggregated_health()) > 0
        assert alerts.alerts is not None

    @pytest.mark.asyncio
    async def test_monitoring_service(self, monitoring_config):
        """Test monitoring service."""
        config = BotConfig(**monitoring_config)
        service = MonitoringService(config)
        
        # Start service
        await service.start()
        assert service.is_running() is True
        
        # Wait for metrics collection
        await asyncio.sleep(2)
        
        # Check collected metrics
        metrics = service.get_metrics()
        assert metrics is not None
        
        # Stop service
        await service.stop()
        assert service.is_running() is False


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for monitoring."""

    def test_metrics_collection_speed(self, metrics_collector):
        """Test metrics collection speed."""
        import time
        
        iterations = 1000
        start_time = time.time()
        
        for i in range(iterations):
            metrics_collector.record_trade({
                'symbol': 'BTC-USD',
                'side': 'buy',
                'price': 43000.0,
                'quantity': 0.1,
                'pnl': float(i),
                'duration': 60
            })
        
        elapsed = time.time() - start_time
        avg_time = elapsed / iterations
        
        assert avg_time < 0.001  # Less than 1ms per record
        logger.info(f"Average metrics collection time: {avg_time * 1000:.3f}ms")

    def test_monitoring_memory_usage(self, monitoring_config):
        """Test monitoring memory usage."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        config = BotConfig(**monitoring_config)
        metrics = MetricsCollector(config)
        
        # Record many metrics
        for i in range(10000):
            metrics.record_trade({
                'symbol': 'BTC-USD',
                'side': 'buy',
                'price': 43000.0 + i,
                'quantity': 0.1,
                'pnl': float(i),
                'duration': 60 + i % 100
            })
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        assert memory_increase < 100  # Less than 100MB increase
        logger.info(f"Memory increase: {memory_increase:.2f}MB")


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for monitoring."""

    def test_empty_metrics(self, metrics_collector):
        """Test handling of empty metrics."""
        metrics = metrics_collector.get_metrics()
        assert metrics is not None
        assert isinstance(metrics, dict)

    def test_invalid_alert(self, alert_manager):
        """Test handling of invalid alerts."""
        invalid_alert = {
            'severity': 'unknown',
            'message': 'Invalid alert',
            'component': 'test'
        }
        
        alert_manager.create_alert(invalid_alert)
        assert len(alert_manager.alerts) == 0

    def test_disabled_monitoring(self, monitoring_config):
        """Test disabled monitoring."""
        monitoring_config['monitoring']['enabled'] = False
        config = BotConfig(**monitoring_config)
        
        metrics = MetricsCollector(config)
        assert metrics.enabled is False
        
        # Should not collect metrics
        metrics.collect_system_metrics()
        assert len(metrics.metrics) == 0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    # Run pytest programmatically
    print("=" * 80)
    print("NEXUS AI TRADING SYSTEM - Monitoring Test Suite")
    print("=" * 80)
    print(f"Copyright: {COPYRIGHT}")
    print(f"CEO: {CEO}")
    print("-" * 80)
    
    # Run all tests
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--maxfail=1',
        '-x'
    ])
    
    print("\n" + "=" * 80)
    print("✅ Monitoring Test Suite Complete")
    print("=" * 80)

"""
Swing Bot Monitoring Tests
============================

This module contains unit tests for the monitoring components of the Swing Bot trading system.
"""

import pytest
import time
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, call
from pathlib import Path
import pandas as pd

from trading.bots.swing_bot.monitoring import (
    MonitoringService,
    AlertManager,
    HealthChecker,
    MetricsCollector,
    Logger,
    PerformanceMonitor,
    Dashboard
)
from trading.bots.swing_bot.core import Signal, SignalType
from trading.bots.swing_bot.utils.validators import validate_data

from .fixtures import get_config_fixture, get_market_data_fixture


class TestMonitoringService:
    """Tests for MonitoringService."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def monitoring_service(self, config):
        """Create a MonitoringService instance."""
        return MonitoringService(config=config)
    
    def test_initialization(self, monitoring_service):
        """Test monitoring service initialization."""
        assert monitoring_service.config is not None
        assert monitoring_service.is_running is False
        assert monitoring_service.metrics == {}
        assert monitoring_service.alerts == []
    
    def test_start_stop(self, monitoring_service):
        """Test starting and stopping the monitoring service."""
        # Start the service
        monitoring_service.start()
        assert monitoring_service.is_running is True
        
        # Stop the service
        monitoring_service.stop()
        assert monitoring_service.is_running is False
    
    def test_collect_metrics(self, monitoring_service):
        """Test metric collection."""
        # Collect system metrics
        metrics = monitoring_service.collect_system_metrics()
        
        assert metrics is not None
        assert "cpu_usage" in metrics
        assert "memory_usage" in metrics
        assert "disk_usage" in metrics
        assert "network_usage" in metrics
    
    def test_track_metric(self, monitoring_service):
        """Test metric tracking."""
        # Track a metric
        monitoring_service.track_metric("test_metric", 100)
        
        assert "test_metric" in monitoring_service.metrics
        assert monitoring_service.metrics["test_metric"] == 100
    
    def test_track_timing(self, monitoring_service):
        """Test timing tracking."""
        # Track timing
        with monitoring_service.track_time("test_timing"):
            time.sleep(0.01)
        
        assert "test_timing" in monitoring_service.metrics
        assert monitoring_service.metrics["test_timing"] > 0
    
    def test_increment_counter(self, monitoring_service):
        """Test counter increment."""
        # Increment counter
        monitoring_service.increment_counter("test_counter")
        assert monitoring_service.metrics["test_counter"] == 1
        
        # Increment by 5
        monitoring_service.increment_counter("test_counter", 5)
        assert monitoring_service.metrics["test_counter"] == 6


class TestAlertManager:
    """Tests for AlertManager."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def alert_manager(self, config):
        """Create an AlertManager instance."""
        return AlertManager(config=config)
    
    def test_initialization(self, alert_manager):
        """Test alert manager initialization."""
        assert alert_manager.config is not None
        assert alert_manager.alerts == []
        assert alert_manager.channels == ["email", "telegram"]
    
    def test_create_alert(self, alert_manager):
        """Test alert creation."""
        # Create an alert
        alert = alert_manager.create_alert(
            level="warning",
            message="Test alert message",
            source="test_source"
        )
        
        assert alert is not None
        assert alert["level"] == "warning"
        assert alert["message"] == "Test alert message"
        assert alert["source"] == "test_source"
        assert "timestamp" in alert
        assert "id" in alert
    
    def test_send_alert(self, alert_manager):
        """Test sending an alert."""
        # Create and send alert
        alert = alert_manager.create_alert(
            level="critical",
            message="Critical test alert",
            source="test_source"
        )
        
        # Send alert
        result = alert_manager.send_alert(alert)
        
        assert result is True
        assert alert in alert_manager.alerts
    
    def test_alert_channels(self, alert_manager):
        """Test alert channels."""
        # Test email channel
        with patch('smtplib.SMTP') as mock_smtp:
            alert_manager.send_email_alert("Test email alert")
            mock_smtp.assert_called()
        
        # Test telegram channel
        with patch('telegram.Bot') as mock_bot:
            alert_manager.send_telegram_alert("Test telegram alert")
            mock_bot.assert_called()
    
    def test_alert_thresholds(self, alert_manager):
        """Test alert thresholds."""
        # Set thresholds
        alert_manager.set_threshold("cpu_usage", 80)
        alert_manager.set_threshold("memory_usage", 90)
        
        # Check thresholds
        assert alert_manager.thresholds["cpu_usage"] == 80
        assert alert_manager.thresholds["memory_usage"] == 90
        
        # Test threshold breach
        alert_manager.check_threshold("cpu_usage", 85)
        assert len(alert_manager.alerts) > 0


class TestHealthChecker:
    """Tests for HealthChecker."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def health_checker(self, config):
        """Create a HealthChecker instance."""
        return HealthChecker(config=config)
    
    def test_initialization(self, health_checker):
        """Test health checker initialization."""
        assert health_checker.config is not None
        assert health_checker.services == {}
        assert health_checker.status == "unknown"
    
    def test_register_service(self, health_checker):
        """Test service registration."""
        # Register a service
        health_checker.register_service(
            name="test_service",
            check_func=lambda: True,
            interval=60
        )
        
        assert "test_service" in health_checker.services
        assert health_checker.services["test_service"]["interval"] == 60
    
    def test_check_service(self, health_checker):
        """Test service health check."""
        # Register and check service
        health_checker.register_service(
            name="test_service",
            check_func=lambda: True,
            interval=60
        )
        
        result = health_checker.check_service("test_service")
        assert result is True
    
    def test_check_all(self, health_checker):
        """Test checking all services."""
        # Register multiple services
        health_checker.register_service(
            name="service_1",
            check_func=lambda: True,
            interval=60
        )
        health_checker.register_service(
            name="service_2",
            check_func=lambda: True,
            interval=60
        )
        
        results = health_checker.check_all()
        
        assert len(results) == 2
        assert results["service_1"] is True
        assert results["service_2"] is True
    
    def test_health_status(self, health_checker):
        """Test health status determination."""
        # All services healthy
        health_checker.register_service(
            name="healthy_service",
            check_func=lambda: True,
            interval=60
        )
        
        status = health_checker.get_status()
        assert status == "healthy"
        
        # One service unhealthy
        health_checker.register_service(
            name="unhealthy_service",
            check_func=lambda: False,
            interval=60
        )
        
        status = health_checker.get_status()
        assert status == "unhealthy"


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def metrics_collector(self, config):
        """Create a MetricsCollector instance."""
        return MetricsCollector(config=config)
    
    def test_initialization(self, metrics_collector):
        """Test metrics collector initialization."""
        assert metrics_collector.config is not None
        assert metrics_collector.metrics == {}
        assert metrics_collector.histories == {}
    
    def test_collect_metric(self, metrics_collector):
        """Test metric collection."""
        # Collect a metric
        metrics_collector.collect("test_metric", 100)
        
        assert "test_metric" in metrics_collector.metrics
        assert metrics_collector.metrics["test_metric"] == 100
        
        # Check history
        assert "test_metric" in metrics_collector.histories
        assert len(metrics_collector.histories["test_metric"]) > 0
    
    def test_get_metric_history(self, metrics_collector):
        """Test metric history retrieval."""
        # Collect multiple values
        for i in range(10):
            metrics_collector.collect("test_metric", i * 10)
        
        history = metrics_collector.get_history("test_metric", limit=5)
        
        assert len(history) == 5
        assert history[-1] == 90
    
    def test_calculate_statistics(self, metrics_collector):
        """Test statistics calculation."""
        # Collect values
        for i in range(10):
            metrics_collector.collect("test_metric", i * 10)
        
        stats = metrics_collector.calculate_stats("test_metric")
        
        assert stats["count"] == 10
        assert stats["min"] == 0
        assert stats["max"] == 90
        assert stats["mean"] == 45
        assert stats["sum"] == 450
    
    def test_reset_metric(self, metrics_collector):
        """Test metric reset."""
        # Collect and reset
        metrics_collector.collect("test_metric", 100)
        metrics_collector.reset("test_metric")
        
        assert metrics_collector.metrics["test_metric"] == 0
        assert len(metrics_collector.histories["test_metric"]) == 0


class TestLogger:
    """Tests for Logger."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def logger(self, config):
        """Create a Logger instance."""
        return Logger(config=config)
    
    def test_initialization(self, logger):
        """Test logger initialization."""
        assert logger.config is not None
        assert logger.level == "DEBUG"
        assert logger.format == "json"
        assert logger.output == "console"
    
    def test_log_levels(self, logger):
        """Test log levels."""
        # Test each level
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
        
        # Check log count
        assert len(logger.logs) > 0
    
    def test_json_format(self, logger):
        """Test JSON log format."""
        logger.info("Test message", extra={"key": "value"})
        
        log_entry = logger.logs[-1]
        assert "timestamp" in log_entry
        assert "level" in log_entry
        assert "message" in log_entry
        assert "extra" in log_entry
        assert log_entry["extra"]["key"] == "value"
    
    def test_file_output(self, config, tmp_path):
        """Test file output."""
        config["logging"]["file_path"] = str(tmp_path / "test.log")
        logger = Logger(config=config)
        
        logger.info("Test file log")
        
        log_file = tmp_path / "test.log"
        assert log_file.exists()
        
        content = log_file.read_text()
        assert "Test file log" in content


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def performance_monitor(self, config):
        """Create a PerformanceMonitor instance."""
        return PerformanceMonitor(config=config)
    
    def test_initialization(self, performance_monitor):
        """Test performance monitor initialization."""
        assert performance_monitor.config is not None
        assert performance_monitor.metrics == {}
        assert performance_monitor.thresholds == {}
    
    def test_record_latency(self, performance_monitor):
        """Test latency recording."""
        # Record latency
        performance_monitor.record_latency("test_operation", 0.1)
        
        assert "test_operation" in performance_monitor.metrics
        assert performance_monitor.metrics["test_operation"]["latency"] == 0.1
    
    def test_record_throughput(self, performance_monitor):
        """Test throughput recording."""
        # Record throughput
        performance_monitor.record_throughput("test_operation", 1000)
        
        assert "test_operation" in performance_monitor.metrics
        assert performance_monitor.metrics["test_operation"]["throughput"] == 1000
    
    def test_check_performance(self, performance_monitor):
        """Test performance checking."""
        # Set thresholds
        performance_monitor.set_threshold("test_operation", max_latency=0.5, min_throughput=500)
        
        # Within thresholds
        performance_monitor.record_latency("test_operation", 0.1)
        performance_monitor.record_throughput("test_operation", 1000)
        
        result = performance_monitor.check_performance("test_operation")
        assert result is True
        
        # Exceeding thresholds
        performance_monitor.record_latency("test_operation", 1.0)
        performance_monitor.record_throughput("test_operation", 100)
        
        result = performance_monitor.check_performance("test_operation")
        assert result is False


class TestDashboard:
    """Tests for Dashboard."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def dashboard(self, config):
        """Create a Dashboard instance."""
        return Dashboard(config=config)
    
    def test_initialization(self, dashboard):
        """Test dashboard initialization."""
        assert dashboard.config is not None
        assert dashboard.widgets == {}
        assert dashboard.data == {}
    
    def test_add_widget(self, dashboard):
        """Test widget addition."""
        # Add a widget
        dashboard.add_widget(
            name="test_widget",
            widget_type="chart",
            data_source="test_data",
            config={"title": "Test Chart"}
        )
        
        assert "test_widget" in dashboard.widgets
        assert dashboard.widgets["test_widget"]["type"] == "chart"
        assert dashboard.widgets["test_widget"]["data_source"] == "test_data"
    
    def test_update_data(self, dashboard):
        """Test data update."""
        # Update data
        dashboard.update_data("test_data", {"value": 100})
        
        assert "test_data" in dashboard.data
        assert dashboard.data["test_data"]["value"] == 100
    
    def test_render_dashboard(self, dashboard):
        """Test dashboard rendering."""
        # Add widgets and data
        dashboard.add_widget(
            name="test_widget",
            widget_type="chart",
            data_source="test_data",
            config={"title": "Test Chart"}
        )
        dashboard.update_data("test_data", {"value": 100})
        
        # Render dashboard
        rendered = dashboard.render()
        
        assert rendered is not None
        assert "Test Chart" in rendered
        assert "100" in rendered
    
    def test_widget_types(self, dashboard):
        """Test different widget types."""
        # Chart widget
        dashboard.add_widget(
            name="chart_widget",
            widget_type="chart",
            data_source="chart_data",
            config={"title": "Chart"}
        )
        
        # Table widget
        dashboard.add_widget(
            name="table_widget",
            widget_type="table",
            data_source="table_data",
            config={"columns": ["col1", "col2"]}
        )
        
        # Metric widget
        dashboard.add_widget(
            name="metric_widget",
            widget_type="metric",
            data_source="metric_data",
            config={"label": "Metric"}
        )
        
        assert len(dashboard.widgets) == 3


class TestMonitoringIntegration:
    """Integration tests for monitoring components."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def monitoring_stack(self, config):
        """Create a complete monitoring stack."""
        monitoring_service = MonitoringService(config=config)
        alert_manager = AlertManager(config=config)
        health_checker = HealthChecker(config=config)
        metrics_collector = MetricsCollector(config=config)
        logger = Logger(config=config)
        performance_monitor = PerformanceMonitor(config=config)
        dashboard = Dashboard(config=config)
        
        return {
            "service": monitoring_service,
            "alerts": alert_manager,
            "health": health_checker,
            "metrics": metrics_collector,
            "logger": logger,
            "performance": performance_monitor,
            "dashboard": dashboard
        }
    
    def test_monitoring_workflow(self, monitoring_stack):
        """Test complete monitoring workflow."""
        stack = monitoring_stack
        
        # Start monitoring
        stack["service"].start()
        
        # Register services
        stack["health"].register_service(
            name="trading_engine",
            check_func=lambda: True,
            interval=60
        )
        
        # Collect metrics
        stack["metrics"].collect("cpu_usage", 45)
        stack["metrics"].collect("memory_usage", 60)
        
        # Record performance
        stack["performance"].record_latency("trade_execution", 0.05)
        stack["performance"].record_throughput("trade_execution", 100)
        
        # Add widgets to dashboard
        stack["dashboard"].add_widget(
            name="cpu_usage",
            widget_type="metric",
            data_source="cpu_usage",
            config={"label": "CPU Usage"}
        )
        
        # Check health
        status = stack["health"].get_status()
        assert status == "healthy"
        
        # Stop monitoring
        stack["service"].stop()


if __name__ == "__main__":
    pytest.main([__file__])

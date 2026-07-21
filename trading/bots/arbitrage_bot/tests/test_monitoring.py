"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Monitoring Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests de monitoring et de surveillance pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import asyncio
import time
import json
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor

# Import du module à tester
from trading.bots.arbitrage_bot.monitoring.health_check import HealthCheck
from trading.bots.arbitrage_bot.monitoring.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.monitoring.alert_manager import AlertManager
from trading.bots.arbitrage_bot.monitoring.log_analyzer import LogAnalyzer
from trading.bots.arbitrage_bot.monitoring.performance_monitor import PerformanceMonitor
from trading.bots.arbitrage_bot.monitoring.system_monitor import SystemMonitor
from trading.bots.arbitrage_bot.monitoring.trade_monitor import TradeMonitor
from trading.bots.arbitrage_bot.monitoring.exchange_monitor import ExchangeMonitor
from trading.bots.arbitrage_bot.monitoring.notification_monitor import NotificationMonitor

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    test_data,
    test_system_status,
    test_performance_metrics,
    test_orders,
    test_trades,
    test_alerts
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
# HEALTH CHECK TESTS
# ============================================================

class TestHealthCheck:
    """Tests pour le contrôle de santé"""

    @pytest.fixture
    def health_check(self):
        """Fixture pour le contrôle de santé"""
        return HealthCheck()

    def test_initialization(self, health_check):
        """Test l'initialisation"""
        assert health_check is not None
        assert health_check.is_healthy() is True

    def test_check_system(self, health_check):
        """Test la vérification du système"""
        result = health_check.check_system()
        assert result is not None
        assert 'status' in result
        assert result['status'] == 'healthy'

    def test_check_database(self, health_check):
        """Test la vérification de la base de données"""
        with patch('trading.bots.arbitrage_bot.monitoring.health_check.get_db_connection') as mock_db:
            mock_db.return_value = Mock()
            result = health_check.check_database()
            assert result is not None
            assert 'status' in result

    def test_check_exchanges(self, health_check, mock_exchange):
        """Test la vérification des exchanges"""
        health_check.add_exchange(mock_exchange)
        result = health_check.check_exchanges()
        assert result is not None
        assert len(result) > 0

    def test_check_memory(self, health_check):
        """Test la vérification de la mémoire"""
        result = health_check.check_memory()
        assert result is not None
        assert 'total' in result
        assert 'available' in result
        assert 'percent' in result

    def test_check_cpu(self, health_check):
        """Test la vérification du CPU"""
        result = health_check.check_cpu()
        assert result is not None
        assert 'percent' in result
        assert 'cores' in result

    def test_check_disk(self, health_check):
        """Test la vérification du disque"""
        result = health_check.check_disk()
        assert result is not None
        assert 'total' in result
        assert 'used' in result
        assert 'free' in result

    def test_check_network(self, health_check):
        """Test la vérification du réseau"""
        result = health_check.check_network()
        assert result is not None
        assert 'status' in result

    def test_run_all_checks(self, health_check):
        """Test l'exécution de toutes les vérifications"""
        results = health_check.run_all_checks()
        assert results is not None
        assert 'system' in results
        assert 'memory' in results
        assert 'cpu' in results

    def test_get_health_report(self, health_check):
        """Test la récupération du rapport de santé"""
        report = health_check.get_health_report()
        assert report is not None
        assert 'status' in report
        assert 'timestamp' in report
        assert 'checks' in report

# ============================================================
# METRICS COLLECTOR TESTS
# ============================================================

class TestMetricsCollector:
    """Tests pour le collecteur de métriques"""

    @pytest.fixture
    def metrics_collector(self):
        """Fixture pour le collecteur de métriques"""
        return MetricsCollector()

    def test_initialization(self, metrics_collector):
        """Test l'initialisation"""
        assert metrics_collector is not None
        assert len(metrics_collector.get_metrics()) == 0

    def test_collect_system_metrics(self, metrics_collector):
        """Test la collecte des métriques système"""
        metrics = metrics_collector.collect_system_metrics()
        assert metrics is not None
        assert 'cpu_percent' in metrics
        assert 'memory_percent' in metrics
        assert 'disk_usage' in metrics

    def test_collect_exchange_metrics(self, metrics_collector, mock_exchange):
        """Test la collecte des métriques d'exchange"""
        metrics_collector.add_exchange(mock_exchange)
        metrics = metrics_collector.collect_exchange_metrics()
        assert metrics is not None
        assert len(metrics) > 0

    def test_collect_trade_metrics(self, metrics_collector):
        """Test la collecte des métriques de trading"""
        metrics = metrics_collector.collect_trade_metrics()
        assert metrics is not None
        assert 'total_trades' in metrics
        assert 'successful_trades' in metrics
        assert 'failed_trades' in metrics

    def test_collect_performance_metrics(self, metrics_collector):
        """Test la collecte des métriques de performance"""
        metrics = metrics_collector.collect_performance_metrics()
        assert metrics is not None
        assert 'avg_latency' in metrics
        assert 'max_latency' in metrics
        assert 'throughput' in metrics

    def test_collect_all_metrics(self, metrics_collector):
        """Test la collecte de toutes les métriques"""
        metrics = metrics_collector.collect_all_metrics()
        assert metrics is not None
        assert 'system' in metrics
        assert 'trade' in metrics
        assert 'performance' in metrics

    def test_start_stop_collection(self, metrics_collector):
        """Test le démarrage/arrêt de la collecte"""
        metrics_collector.start_collection()
        assert metrics_collector.is_collecting() is True
        
        metrics_collector.stop_collection()
        assert metrics_collector.is_collecting() is False

    def test_get_metric_history(self, metrics_collector):
        """Test la récupération de l'historique des métriques"""
        # Ajouter quelques métriques
        for i in range(10):
            metrics_collector.add_metric(f'test_metric_{i}', i * 10)
        
        history = metrics_collector.get_metric_history('test_metric_5')
        assert len(history) > 0

# ============================================================
# ALERT MANAGER TESTS
# ============================================================

class TestAlertManager:
    """Tests pour le gestionnaire d'alertes"""

    @pytest.fixture
    def alert_manager(self):
        """Fixture pour le gestionnaire d'alertes"""
        return AlertManager()

    def test_initialization(self, alert_manager):
        """Test l'initialisation"""
        assert alert_manager is not None
        assert len(alert_manager.get_alerts()) == 0

    def test_add_alert_rule(self, alert_manager):
        """Test l'ajout d'une règle d'alerte"""
        rule = {
            'name': 'High CPU Usage',
            'condition': 'cpu_percent > 80',
            'severity': 'warning',
            'action': 'notify'
        }
        alert_manager.add_alert_rule(rule)
        rules = alert_manager.get_alert_rules()
        assert len(rules) == 1
        assert rules[0]['name'] == 'High CPU Usage'

    def test_remove_alert_rule(self, alert_manager):
        """Test la suppression d'une règle d'alerte"""
        rule = {'name': 'Test Rule', 'condition': 'test > 0'}
        alert_manager.add_alert_rule(rule)
        alert_manager.remove_alert_rule('Test Rule')
        rules = alert_manager.get_alert_rules()
        assert len(rules) == 0

    def test_check_alerts(self, alert_manager):
        """Test la vérification des alertes"""
        # Ajouter une règle
        rule = {
            'name': 'High CPU',
            'condition': 'cpu_percent > 80',
            'severity': 'warning'
        }
        alert_manager.add_alert_rule(rule)
        
        # Vérifier avec des métriques
        metrics = {'cpu_percent': 85}
        triggered = alert_manager.check_alerts(metrics)
        assert len(triggered) > 0

    def test_send_alert(self, alert_manager):
        """Test l'envoi d'une alerte"""
        alert = {
            'type': 'warning',
            'message': 'Test alert message',
            'severity': 'warning',
            'timestamp': datetime.now().isoformat()
        }
        result = alert_manager.send_alert(alert)
        assert result is True

    def test_get_active_alerts(self, alert_manager):
        """Test la récupération des alertes actives"""
        # Ajouter quelques alertes
        for i in range(3):
            alert_manager.add_alert({
                'id': f'alert_{i}',
                'message': f'Test alert {i}',
                'severity': 'warning',
                'active': True
            })
        
        active = alert_manager.get_active_alerts()
        assert len(active) == 3

    def test_acknowledge_alert(self, alert_manager):
        """Test l'acquittement d'une alerte"""
        alert = {
            'id': 'alert_001',
            'message': 'Test alert',
            'severity': 'warning',
            'active': True
        }
        alert_manager.add_alert(alert)
        alert_manager.acknowledge_alert('alert_001')
        alerts = alert_manager.get_alerts()
        assert alerts[0]['acknowledged'] is True

# ============================================================
# LOG ANALYZER TESTS
# ============================================================

class TestLogAnalyzer:
    """Tests pour l'analyseur de logs"""

    @pytest.fixture
    def log_analyzer(self):
        """Fixture pour l'analyseur de logs"""
        return LogAnalyzer()

    def test_initialization(self, log_analyzer):
        """Test l'initialisation"""
        assert log_analyzer is not None

    def test_analyze_logs(self, log_analyzer):
        """Test l'analyse des logs"""
        # Créer des logs de test
        logs = [
            {'level': 'INFO', 'message': 'Test info message', 'timestamp': datetime.now().isoformat()},
            {'level': 'WARNING', 'message': 'Test warning message', 'timestamp': datetime.now().isoformat()},
            {'level': 'ERROR', 'message': 'Test error message', 'timestamp': datetime.now().isoformat()}
        ]
        
        analysis = log_analyzer.analyze_logs(logs)
        assert analysis is not None
        assert 'total_entries' in analysis
        assert 'error_count' in analysis
        assert 'warning_count' in analysis

    def test_find_patterns(self, log_analyzer):
        """Test la recherche de motifs"""
        logs = [
            {'message': 'Error: Connection failed'},
            {'message': 'Error: Timeout'},
            {'message': 'Success: Connected'}
        ]
        
        patterns = log_analyzer.find_patterns(logs, ['Error', 'Success'])
        assert len(patterns) > 0

    def test_detect_anomalies(self, log_analyzer):
        """Test la détection d'anomalies"""
        logs = [
            {'message': 'Normal operation', 'timestamp': datetime.now().isoformat()}
            for _ in range(10)
        ]
        # Ajouter une anomalie
        logs.append({
            'message': 'CRITICAL: System failure',
            'timestamp': datetime.now().isoformat()
        })
        
        anomalies = log_analyzer.detect_anomalies(logs)
        assert len(anomalies) > 0

    def test_generate_report(self, log_analyzer):
        """Test la génération de rapport"""
        logs = [
            {'level': 'INFO', 'message': 'Test message', 'timestamp': datetime.now().isoformat()}
            for _ in range(5)
        ]
        logs.append({'level': 'ERROR', 'message': 'Error message', 'timestamp': datetime.now().isoformat()})
        
        report = log_analyzer.generate_report(logs)
        assert report is not None
        assert 'summary' in report
        assert 'statistics' in report

# ============================================================
# PERFORMANCE MONITOR TESTS
# ============================================================

class TestPerformanceMonitor:
    """Tests pour le moniteur de performance"""

    @pytest.fixture
    def performance_monitor(self):
        """Fixture pour le moniteur de performance"""
        return PerformanceMonitor()

    def test_initialization(self, performance_monitor):
        """Test l'initialisation"""
        assert performance_monitor is not None
        assert performance_monitor.is_monitoring() is False

    def test_start_stop_monitoring(self, performance_monitor):
        """Test le démarrage/arrêt du monitoring"""
        performance_monitor.start_monitoring()
        assert performance_monitor.is_monitoring() is True
        
        performance_monitor.stop_monitoring()
        assert performance_monitor.is_monitoring() is False

    def test_measure_latency(self, performance_monitor):
        """Test la mesure de la latence"""
        # Mesurer la latence d'une opération
        def test_operation():
            time.sleep(0.01)
            return True
        
        latency = performance_monitor.measure_latency(test_operation)
        assert latency > 0

    def test_measure_throughput(self, performance_monitor):
        """Test la mesure du débit"""
        # Mesurer le débit d'une opération
        def test_operation():
            return True
        
        throughput = performance_monitor.measure_throughput(test_operation, 100)
        assert throughput > 0

    def test_get_performance_metrics(self, performance_monitor):
        """Test la récupération des métriques de performance"""
        metrics = performance_monitor.get_performance_metrics()
        assert metrics is not None
        assert 'avg_latency' in metrics
        assert 'max_latency' in metrics
        assert 'throughput' in metrics

    def test_set_thresholds(self, performance_monitor):
        """Test la définition des seuils"""
        thresholds = {
            'latency': 100,
            'throughput': 1000,
            'error_rate': 0.01
        }
        performance_monitor.set_thresholds(thresholds)
        assert performance_monitor.get_thresholds() == thresholds

    def test_check_performance_alerts(self, performance_monitor):
        """Test la vérification des alertes de performance"""
        thresholds = {'latency': 100}
        performance_monitor.set_thresholds(thresholds)
        
        # Simuler des métriques de performance
        metrics = {'avg_latency': 150}
        alerts = performance_monitor.check_performance_alerts(metrics)
        assert len(alerts) > 0

# ============================================================
# SYSTEM MONITOR TESTS
# ============================================================

class TestSystemMonitor:
    """Tests pour le moniteur système"""

    @pytest.fixture
    def system_monitor(self):
        """Fixture pour le moniteur système"""
        return SystemMonitor()

    def test_initialization(self, system_monitor):
        """Test l'initialisation"""
        assert system_monitor is not None

    def test_monitor_cpu(self, system_monitor):
        """Test le monitoring du CPU"""
        cpu_stats = system_monitor.monitor_cpu()
        assert cpu_stats is not None
        assert 'percent' in cpu_stats
        assert 'cores' in cpu_stats

    def test_monitor_memory(self, system_monitor):
        """Test le monitoring de la mémoire"""
        memory_stats = system_monitor.monitor_memory()
        assert memory_stats is not None
        assert 'total' in memory_stats
        assert 'available' in memory_stats
        assert 'percent' in memory_stats

    def test_monitor_disk(self, system_monitor):
        """Test le monitoring du disque"""
        disk_stats = system_monitor.monitor_disk()
        assert disk_stats is not None
        assert 'total' in disk_stats
        assert 'used' in disk_stats
        assert 'free' in disk_stats

    def test_monitor_network(self, system_monitor):
        """Test le monitoring du réseau"""
        network_stats = system_monitor.monitor_network()
        assert network_stats is not None
        assert 'bytes_sent' in network_stats
        assert 'bytes_recv' in network_stats

    def test_monitor_processes(self, system_monitor):
        """Test le monitoring des processus"""
        process_stats = system_monitor.monitor_processes()
        assert process_stats is not None
        assert 'total' in process_stats
        assert 'running' in process_stats

    def test_get_system_health(self, system_monitor):
        """Test la récupération de la santé système"""
        health = system_monitor.get_system_health()
        assert health is not None
        assert 'status' in health
        assert 'timestamp' in health

    def test_get_system_report(self, system_monitor):
        """Test la récupération du rapport système"""
        report = system_monitor.get_system_report()
        assert report is not None
        assert 'cpu' in report
        assert 'memory' in report
        assert 'disk' in report
        assert 'network' in report

# ============================================================
# TRADE MONITOR TESTS
# ============================================================

class TestTradeMonitor:
    """Tests pour le moniteur de trades"""

    @pytest.fixture
    def trade_monitor(self):
        """Fixture pour le moniteur de trades"""
        return TradeMonitor()

    def test_initialization(self, trade_monitor):
        """Test l'initialisation"""
        assert trade_monitor is not None

    def test_monitor_trades(self, trade_monitor):
        """Test le monitoring des trades"""
        # Ajouter quelques trades
        for i in range(5):
            trade_monitor.add_trade({
                'id': f'trade_{i}',
                'symbol': 'BTC/USDT',
                'pnl': i * 10,
                'status': 'success' if i % 2 == 0 else 'failed'
            })
        
        stats = trade_monitor.monitor_trades()
        assert stats is not None
        assert 'total_trades' in stats
        assert 'successful_trades' in stats
        assert 'failed_trades' in stats

    def test_monitor_pnl(self, trade_monitor):
        """Test le monitoring du P&L"""
        # Ajouter quelques trades
        for i in range(10):
            trade_monitor.add_trade({
                'id': f'trade_{i}',
                'symbol': 'BTC/USDT',
                'pnl': i * 5 - 10,
                'status': 'success'
            })
        
        pnl_stats = trade_monitor.monitor_pnl()
        assert pnl_stats is not None
        assert 'total_pnl' in pnl_stats
        assert 'avg_pnl' in pnl_stats
        assert 'max_pnl' in pnl_stats
        assert 'min_pnl' in pnl_stats

    def test_monitor_win_rate(self, trade_monitor):
        """Test le monitoring du taux de victoire"""
        # Ajouter quelques trades
        for i in range(20):
            trade_monitor.add_trade({
                'id': f'trade_{i}',
                'symbol': 'BTC/USDT',
                'pnl': i * 10 if i % 3 != 0 else -i * 5,
                'status': 'success' if i % 3 != 0 else 'failed'
            })
        
        win_rate = trade_monitor.monitor_win_rate()
        assert win_rate is not None
        assert 0 <= win_rate <= 1

    def test_detect_anomalies(self, trade_monitor):
        """Test la détection d'anomalies"""
        # Ajouter des trades normaux
        for i in range(10):
            trade_monitor.add_trade({
                'id': f'trade_{i}',
                'symbol': 'BTC/USDT',
                'pnl': i * 5,
                'status': 'success'
            })
        
        # Ajouter un trade anormal
        trade_monitor.add_trade({
            'id': 'trade_anomaly',
            'symbol': 'BTC/USDT',
            'pnl': 10000,
            'status': 'success'
        })
        
        anomalies = trade_monitor.detect_anomalies()
        assert len(anomalies) > 0

    def test_get_trade_report(self, trade_monitor):
        """Test la récupération du rapport de trades"""
        # Ajouter quelques trades
        for i in range(5):
            trade_monitor.add_trade({
                'id': f'trade_{i}',
                'symbol': 'BTC/USDT',
                'pnl': i * 10,
                'status': 'success'
            })
        
        report = trade_monitor.get_trade_report()
        assert report is not None
        assert 'summary' in report
        assert 'statistics' in report

# ============================================================
# EXCHANGE MONITOR TESTS
# ============================================================

class TestExchangeMonitor:
    """Tests pour le moniteur d'exchanges"""

    @pytest.fixture
    def exchange_monitor(self):
        """Fixture pour le moniteur d'exchanges"""
        return ExchangeMonitor()

    def test_initialization(self, exchange_monitor):
        """Test l'initialisation"""
        assert exchange_monitor is not None

    def test_monitor_exchange(self, exchange_monitor, mock_exchange):
        """Test le monitoring d'un exchange"""
        exchange_monitor.add_exchange(mock_exchange)
        stats = exchange_monitor.monitor_exchange('Test Exchange')
        assert stats is not None
        assert 'status' in stats
        assert 'latency' in stats

    def test_monitor_all_exchanges(self, exchange_monitor):
        """Test le monitoring de tous les exchanges"""
        # Créer plusieurs exchanges
        for i in range(3):
            exchange = MockExchange(f"Exchange {i}")
            exchange.start_market()
            exchange_monitor.add_exchange(exchange)
        
        stats = exchange_monitor.monitor_all_exchanges()
        assert len(stats) == 3

    def test_check_health(self, exchange_monitor, mock_exchange):
        """Test la vérification de santé"""
        exchange_monitor.add_exchange(mock_exchange)
        health = exchange_monitor.check_health('Test Exchange')
        assert health is not None
        assert 'healthy' in health

    def test_detect_issues(self, exchange_monitor, mock_exchange):
        """Test la détection de problèmes"""
        exchange_monitor.add_exchange(mock_exchange)
        issues = exchange_monitor.detect_issues()
        assert issues is not None

# ============================================================
# NOTIFICATION MONITOR TESTS
# ============================================================

class TestNotificationMonitor:
    """Tests pour le moniteur de notifications"""

    @pytest.fixture
    def notification_monitor(self):
        """Fixture pour le moniteur de notifications"""
        return NotificationMonitor()

    def test_initialization(self, notification_monitor):
        """Test l'initialisation"""
        assert notification_monitor is not None

    def test_monitor_notifications(self, notification_monitor):
        """Test le monitoring des notifications"""
        # Ajouter quelques notifications
        for i in range(5):
            notification_monitor.add_notification({
                'id': f'notif_{i}',
                'type': 'INFO' if i % 2 == 0 else 'ERROR',
                'message': f'Test notification {i}',
                'timestamp': datetime.now().isoformat()
            })
        
        stats = notification_monitor.monitor_notifications()
        assert stats is not None
        assert 'total' in stats
        assert 'by_type' in stats

    def test_monitor_delivery(self, notification_monitor):
        """Test le monitoring de la livraison"""
        # Ajouter quelques notifications
        for i in range(5):
            notification_monitor.add_notification({
                'id': f'notif_{i}',
                'delivered': i % 2 == 0,
                'timestamp': datetime.now().isoformat()
            })
        
        stats = notification_monitor.monitor_delivery()
        assert stats is not None
        assert 'delivered' in stats
        assert 'failed' in stats

    def test_get_notification_report(self, notification_monitor):
        """Test la récupération du rapport de notifications"""
        # Ajouter quelques notifications
        for i in range(5):
            notification_monitor.add_notification({
                'id': f'notif_{i}',
                'type': 'INFO',
                'message': f'Test notification {i}',
                'timestamp': datetime.now().isoformat()
            })
        
        report = notification_monitor.get_notification_report()
        assert report is not None
        assert 'summary' in report
        assert 'statistics' in report

# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestMonitoringIntegration:
    """Tests d'intégration du monitoring"""

    def test_full_monitoring_flow(self):
        """Test le flux complet de monitoring"""
        # Créer tous les moniteurs
        health_check = HealthCheck()
        metrics_collector = MetricsCollector()
        alert_manager = AlertManager()
        system_monitor = SystemMonitor()
        
        # Démarrer le monitoring
        metrics_collector.start_collection()
        system_monitor.start_monitoring()
        
        try:
            # Collecter des métriques
            metrics = metrics_collector.collect_all_metrics()
            assert metrics is not None
            
            # Vérifier la santé
            health = health_check.run_all_checks()
            assert health is not None
            
            # Vérifier les alertes
            alerts = alert_manager.check_alerts(metrics)
            
            # Obtenir les rapports
            system_report = system_monitor.get_system_report()
            assert system_report is not None
            
        finally:
            metrics_collector.stop_collection()
            system_monitor.stop_monitoring()

    def test_monitoring_with_bot(self, integration_bot):
        """Test le monitoring avec le bot"""
        # Démarrer le bot
        integration_bot.start()
        
        # Créer un moniteur
        monitor = SystemMonitor()
        
        # Monitorer pendant quelques secondes
        time.sleep(2)
        
        # Récupérer le rapport
        report = monitor.get_system_report()
        assert report is not None
        
        # Arrêter le bot
        integration_bot.stop()

# ============================================================
# PERFORMANCE TESTS
# ============================================================

class TestMonitoringPerformance:
    """Tests de performance du monitoring"""

    def test_collection_overhead(self):
        """Test le surcoût de la collecte"""
        collector = MetricsCollector()
        
        # Mesurer le temps de collecte
        start_time = time.time()
        for _ in range(100):
            metrics = collector.collect_all_metrics()
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 100 * 1000  # ms
        assert avg_time < 10  # Moins de 10ms

    def test_alert_checking_performance(self):
        """Test la performance de vérification des alertes"""
        alert_manager = AlertManager()
        
        # Ajouter de nombreuses règles
        for i in range(50):
            alert_manager.add_alert_rule({
                'name': f'Rule_{i}',
                'condition': f'metric_{i} > {i * 10}',
                'severity': 'warning'
            })
        
        # Créer des métriques
        metrics = {f'metric_{i}': i * 15 for i in range(50)}
        
        # Mesurer le temps de vérification
        start_time = time.time()
        for _ in range(100):
            triggered = alert_manager.check_alerts(metrics)
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 100 * 1000  # ms
        assert avg_time < 50  # Moins de 50ms

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# trading/bots/hedge_bot/hedge_bot_data_grafana.py
# Advanced Grafana Integration & Monitoring Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Grafana Integration Module - Module d'intégration avancé avec Grafana pour le Hedge Bot.
Fournit des capacités de monitoring, de visualisation, d'alerting et d'analyse des performances
pour l'ensemble du système de hedging via des dashboards interactifs et des métriques en temps réel.
"""

import asyncio
import json
import time
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import aiohttp
import aiohttp.client_exceptions
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_grafana")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult, DecisionType
)


# ============== ENUMS & TYPES ==============

class GrafanaPanelType(Enum):
    """Types de panneaux Grafana."""
    GRAPH = "graph"
    STAT = "stat"
    TABLE = "table"
    GAUGE = "gauge"
    BAR_GAUGE = "bargauge"
    PIE_CHART = "piechart"
    HEATMAP = "heatmap"
    LOGS = "logs"
    TRACE = "trace"
    ALERT_LIST = "alertlist"
    TEXT = "text"
    DASHBOARD_LIST = "dashboardlist"
    NEWS = "news"


class GrafanaDataSource(Enum):
    """Sources de données Grafana."""
    PROMETHEUS = "prometheus"
    LOKI = "loki"
    TEMPO = "tempo"
    ELASTICSEARCH = "elasticsearch"
    INFLUXDB = "influxdb"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    CLOUDWATCH = "cloudwatch"
    AZURE = "azuremonitor"
    STACKDRIVER = "stackdriver"
    GRAPHITE = "graphite"
    OPEN_TSDB = "opentsdb"


class GrafanaAlertSeverity(Enum):
    """Sévérité des alertes Grafana."""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    NONE = "none"


# ============== DATA MODELS ==============

@dataclass
class GrafanaDashboard:
    """Modèle de dashboard Grafana."""
    dashboard_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    uid: str = ""
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    timezone: str = "browser"
    refresh: str = "30s"
    panels: List[Dict[str, Any]] = field(default_factory=list)
    templating: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "dashboard_id": self.dashboard_id,
            "uid": self.uid,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "timezone": self.timezone,
            "refresh": self.refresh,
            "panels": self.panels,
            "templating": self.templating,
            "variables": self.variables,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "active": self.active
        }


@dataclass
class GrafanaAlert:
    """Modèle d'alerte Grafana."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    message: str = ""
    severity: GrafanaAlertSeverity = GrafanaAlertSeverity.WARNING
    condition: str = ""
    frequency: str = "60s"
    for_duration: str = "5m"
    annotations: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    dashboard_uid: Optional[str] = None
    panel_id: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


@dataclass
class GrafanaMetric:
    """Métrique pour Grafana."""
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dimensions: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metric_type: str = "gauge"  # gauge, counter, histogram, summary
    unit: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class GrafanaEngineInterface(ABC):
    """Interface abstraite pour le moteur Grafana."""
    
    @abstractmethod
    async def create_dashboard(self, dashboard: GrafanaDashboard) -> str:
        """Crée un dashboard Grafana."""
        pass
    
    @abstractmethod
    async def send_metric(self, metric: GrafanaMetric) -> bool:
        """Envoie une métrique à Grafana."""
        pass
    
    @abstractmethod
    async def create_alert(self, alert: GrafanaAlert) -> str:
        """Crée une alerte Grafana."""
        pass


# ============== IMPLÉMENTATION ==============

class GrafanaEngine(GrafanaEngineInterface):
    """
    Moteur d'intégration Grafana avancé pour le Hedge Bot.
    Gère les dashboards, les métriques, les alertes et les visualisations.
    """
    
    def __init__(
        self,
        url: str,
        api_key: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Gestion des dashboards
        self._dashboards: Dict[str, GrafanaDashboard] = {}
        self._dashboards_lock = threading.RLock()
        
        # Gestion des alertes
        self._alerts: Dict[str, GrafanaAlert] = {}
        self._alerts_lock = threading.RLock()
        
        # Gestion des métriques
        self._metrics_cache: Dict[str, List[GrafanaMetric]] = {}
        self._metrics_lock = threading.RLock()
        
        # Queue des métriques
        self._metric_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "dashboards_created": 0,
            "alerts_created": 0,
            "metrics_sent": 0,
            "metrics_failed": 0,
            "dashboard_views": 0,
            "alert_triggers": 0
        }
        
        # Métriques système
        self._system_metrics: Dict[str, float] = {}
        
        # État
        self._is_running = False
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        logger.info("GrafanaEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "batch_size": 100,
            "flush_interval": 5,
            "metric_timeout": 30,
            "retry_count": 3,
            "retry_delay": 1.0,
            "default_data_source": GrafanaDataSource.PROMETHEUS,
            "organization_id": 1,
            "dashboard_ttl": 3600,
            "alert_check_interval": 60,
            "enable_compression": True,
            "max_metrics_per_batch": 1000,
            "dashboard_template_dir": "./grafana/dashboards"
        }
    
    async def start(self) -> None:
        """Démarre le moteur Grafana."""
        logger.info("GrafanaEngine starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=self.config["metric_timeout"])
        )
        
        # Chargement des dashboards existants
        await self._load_dashboards()
        
        # Chargement des alertes existantes
        await self._load_alerts()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._metric_processor())
        asyncio.create_task(self._alert_checker_loop())
        asyncio.create_task(self._dashboard_updater_loop())
        
        logger.info("GrafanaEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur Grafana."""
        logger.info("GrafanaEngine stopping...")
        self._is_running = False
        
        # Vidage des queues
        await self._flush_metrics()
        
        # Fermeture de la session
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("GrafanaEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_dashboard(self, dashboard: GrafanaDashboard) -> str:
        """Crée un dashboard Grafana."""
        with self._dashboards_lock:
            self._dashboards[dashboard.dashboard_id] = dashboard
            self._stats["dashboards_created"] += 1
        
        try:
            # Construction du payload Grafana
            payload = {
                "dashboard": {
                    "id": None,
                    "uid": dashboard.uid or dashboard.dashboard_id,
                    "title": dashboard.title,
                    "description": dashboard.description,
                    "tags": dashboard.tags,
                    "timezone": dashboard.timezone,
                    "refresh": dashboard.refresh,
                    "panels": dashboard.panels,
                    "templating": dashboard.templating,
                    "version": dashboard.version,
                    "schemaVersion": 16,
                    "time": {
                        "from": "now-6h",
                        "to": "now"
                    }
                },
                "overwrite": True,
                "message": dashboard.metadata.get("message", "Updated via API")
            }
            
            # Envoi à Grafana
            await self._send_dashboard(payload)
            
            logger.info(f"Dashboard created: {dashboard.title} (uid={dashboard.uid})")
            return dashboard.dashboard_id
            
        except Exception as e:
            logger.error(f"Dashboard creation error: {e}")
            raise
    
    async def send_metric(self, metric: GrafanaMetric) -> bool:
        """Envoie une métrique à Grafana."""
        try:
            # Mise en queue
            await self._metric_queue.put(metric)
            
            # Mise à jour du cache
            with self._metrics_lock:
                if metric.name not in self._metrics_cache:
                    self._metrics_cache[metric.name] = []
                self._metrics_cache[metric.name].append(metric)
                
                # Limitation du cache
                if len(self._metrics_cache[metric.name]) > 10000:
                    self._metrics_cache[metric.name] = self._metrics_cache[metric.name][-10000:]
            
            return True
            
        except Exception as e:
            self._stats["metrics_failed"] += 1
            logger.error(f"Metric send error: {e}")
            return False
    
    async def create_alert(self, alert: GrafanaAlert) -> str:
        """Crée une alerte Grafana."""
        with self._alerts_lock:
            self._alerts[alert.alert_id] = alert
            self._stats["alerts_created"] += 1
        
        try:
            # Construction de l'alerte
            alert_payload = {
                "title": alert.name,
                "message": alert.message,
                "severity": alert.severity.value,
                "condition": alert.condition,
                "frequency": alert.frequency,
                "for": alert.for_duration,
                "annotations": alert.annotations,
                "labels": alert.labels,
                "dashboardUid": alert.dashboard_uid,
                "panelId": alert.panel_id
            }
            
            # Envoi à Grafana
            await self._send_alert(alert_payload)
            
            logger.info(f"Alert created: {alert.name}")
            return alert.alert_id
            
        except Exception as e:
            logger.error(f"Alert creation error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - MÉTRIQUES ==========
    
    async def _metric_processor(self) -> None:
        """Traite les métriques en batch."""
        while self._is_running:
            try:
                metrics = []
                start_time = time.time()
                
                # Collecte des métriques
                while len(metrics) < self.config["batch_size"]:
                    try:
                        metric = await asyncio.wait_for(
                            self._metric_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        metrics.append(metric)
                    except asyncio.TimeoutError:
                        break
                
                if metrics:
                    # Envoi des métriques
                    await self._send_metrics_batch(metrics)
                
                # Gestion du temps restant
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                
            except Exception as e:
                logger.error(f"Metric processor error: {e}")
                await asyncio.sleep(1)
    
    async def _send_metrics_batch(self, metrics: List[GrafanaMetric]) -> bool:
        """Envoie un batch de métriques."""
        try:
            # Construction du payload
            payload = []
            
            for metric in metrics:
                # Format Prometheus
                metric_data = {
                    "name": metric.name,
                    "timestamp": int(metric.timestamp.timestamp() * 1000),
                    "value": metric.value,
                    "tags": metric.dimensions.copy()
                }
                
                # Ajout des tags
                if metric.tags:
                    metric_data["tags"]["tags"] = ",".join(metric.tags)
                
                payload.append(metric_data)
            
            # Envoi à Grafana (format Prometheus)
            # URL: /api/prometheus/remote_write
            prometheus_data = self._format_prometheus_metrics(payload)
            
            async with self._session.post(
                f"{self.url}/api/prometheus/remote_write",
                data=prometheus_data,
                headers={"Content-Type": "application/x-protobuf"}
            ) as response:
                if response.status in [200, 202]:
                    self._stats["metrics_sent"] += len(metrics)
                    logger.debug(f"Sent {len(metrics)} metrics to Grafana")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Error sending metrics: {response.status} - {error_text}")
                    self._stats["metrics_failed"] += len(metrics)
                    return False
                    
        except Exception as e:
            logger.error(f"Metrics batch error: {e}")
            self._stats["metrics_failed"] += len(metrics)
            return False
    
    def _format_prometheus_metrics(self, metrics: List[Dict]) -> bytes:
        """Formate les métriques pour Prometheus."""
        # Dans un système réel, on utiliserait le format Protobuf de Prometheus
        # Simulation simple en JSON
        return json.dumps(metrics).encode()
    
    async def _flush_metrics(self) -> None:
        """Vide la queue des métriques."""
        metrics = []
        while not self._metric_queue.empty():
            try:
                metric = self._metric_queue.get_nowait()
                metrics.append(metric)
            except asyncio.QueueEmpty:
                break
        
        if metrics:
            await self._send_metrics_batch(metrics)
    
    # ========== MÉTHODES PRIVÉES - DASHBOARDS ==========
    
    async def _send_dashboard(self, payload: Dict[str, Any]) -> bool:
        """Envoie un dashboard à Grafana."""
        try:
            async with self._session.post(
                f"{self.url}/api/dashboards/db",
                json=payload
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"Dashboard sent successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Dashboard send error: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Dashboard send error: {e}")
            return False
    
    async def _load_dashboards(self) -> None:
        """Charge les dashboards existants."""
        try:
            async with self._session.get(f"{self.url}/api/dashboards") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for item in data:
                        dashboard = self._deserialize_dashboard(item)
                        if dashboard:
                            with self._dashboards_lock:
                                self._dashboards[dashboard.dashboard_id] = dashboard
                    
                    logger.info(f"Loaded {len(self._dashboards)} dashboards")
                
        except Exception as e:
            logger.error(f"Load dashboards error: {e}")
    
    def _deserialize_dashboard(self, data: Dict) -> Optional[GrafanaDashboard]:
        """Désérialise un dashboard."""
        try:
            dashboard = data.get("dashboard", {})
            return GrafanaDashboard(
                uid=dashboard.get("uid", str(uuid.uuid4())),
                title=dashboard.get("title", ""),
                description=dashboard.get("description", ""),
                tags=dashboard.get("tags", []),
                timezone=dashboard.get("timezone", "browser"),
                refresh=dashboard.get("refresh", "30s"),
                panels=dashboard.get("panels", []),
                templating=dashboard.get("templating", {}),
                variables=dashboard.get("templating", {}).get("list", []),
                version=dashboard.get("version", 1),
                metadata=dashboard.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Deserialize dashboard error: {e}")
            return None
    
    async def _dashboard_updater_loop(self) -> None:
        """Boucle de mise à jour des dashboards."""
        while self._is_running:
            await asyncio.sleep(self.config["dashboard_ttl"])
            
            try:
                # Mise à jour des dashboards actifs
                with self._dashboards_lock:
                    for dashboard in self._dashboards.values():
                        if dashboard.active:
                            # Mise à jour du dashboard
                            dashboard.updated_at = datetime.now(timezone.utc)
                            
                            # Mise à jour dans Grafana
                            payload = {
                                "dashboard": dashboard.to_dict(),
                                "overwrite": True
                            }
                            await self._send_dashboard(payload)
                
            except Exception as e:
                logger.error(f"Dashboard updater error: {e}")
    
    # ========== MÉTHODES PRIVÉES - ALERTES ==========
    
    async def _send_alert(self, alert_payload: Dict[str, Any]) -> bool:
        """Envoie une alerte à Grafana."""
        try:
            async with self._session.post(
                f"{self.url}/api/alerting/alert",
                json=alert_payload
            ) as response:
                if response.status in [200, 201]:
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Alert send error: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Alert send error: {e}")
            return False
    
    async def _load_alerts(self) -> None:
        """Charge les alertes existantes."""
        try:
            async with self._session.get(f"{self.url}/api/alerting/alerts") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for item in data:
                        alert = self._deserialize_alert(item)
                        if alert:
                            with self._alerts_lock:
                                self._alerts[alert.alert_id] = alert
                    
                    logger.info(f"Loaded {len(self._alerts)} alerts")
                
        except Exception as e:
            logger.error(f"Load alerts error: {e}")
    
    def _deserialize_alert(self, data: Dict) -> Optional[GrafanaAlert]:
        """Désérialise une alerte."""
        try:
            return GrafanaAlert(
                name=data.get("name", ""),
                message=data.get("message", ""),
                severity=GrafanaAlertSeverity(data.get("severity", "warning")),
                condition=data.get("condition", ""),
                frequency=data.get("frequency", "60s"),
                for_duration=data.get("for", "5m"),
                annotations=data.get("annotations", {}),
                labels=data.get("labels", {}),
                metadata=data.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Deserialize alert error: {e}")
            return None
    
    async def _alert_checker_loop(self) -> None:
        """Boucle de vérification des alertes."""
        while self._is_running:
            await asyncio.sleep(self.config["alert_check_interval"])
            
            try:
                # Vérification des alertes
                # Dans un système réel, on vérifierait l'état des alertes
                pass
                
            except Exception as e:
                logger.error(f"Alert checker error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_dashboard(self, dashboard_id: str) -> Optional[GrafanaDashboard]:
        """Récupère un dashboard."""
        with self._dashboards_lock:
            return self._dashboards.get(dashboard_id)
    
    async def get_dashboards(self, active_only: bool = True) -> List[GrafanaDashboard]:
        """Récupère les dashboards."""
        with self._dashboards_lock:
            dashboards = list(self._dashboards.values())
            if active_only:
                dashboards = [d for d in dashboards if d.active]
            return dashboards
    
    async def get_alert(self, alert_id: str) -> Optional[GrafanaAlert]:
        """Récupère une alerte."""
        with self._alerts_lock:
            return self._alerts.get(alert_id)
    
    async def get_alerts(self, active_only: bool = True) -> List[GrafanaAlert]:
        """Récupère les alertes."""
        with self._alerts_lock:
            alerts = list(self._alerts.values())
            if active_only:
                alerts = [a for a in alerts if a.active]
            return alerts
    
    async def get_metrics(self, metric_name: str, limit: int = 100) -> List[GrafanaMetric]:
        """Récupère les métriques."""
        with self._metrics_lock:
            return self._metrics_cache.get(metric_name, [])[-limit:]
    
    async def create_trading_dashboard(self, symbol: str) -> GrafanaDashboard:
        """Crée un dashboard de trading."""
        panels = [
            # Panel de prix
            {
                "id": 1,
                "title": f"{symbol} Price",
                "type": "graph",
                "targets": [
                    {
                        "expr": f"{symbol}_price",
                        "legendFormat": "Price"
                    },
                    {
                        "expr": f"{symbol}_sma_20",
                        "legendFormat": "SMA 20"
                    },
                    {
                        "expr": f"{symbol}_sma_50",
                        "legendFormat": "SMA 50"
                    }
                ]
            },
            # Panel de volume
            {
                "id": 2,
                "title": f"{symbol} Volume",
                "type": "graph",
                "targets": [
                    {
                        "expr": f"{symbol}_volume",
                        "legendFormat": "Volume"
                    }
                ]
            },
            # Panel de RSI
            {
                "id": 3,
                "title": f"{symbol} RSI",
                "type": "graph",
                "targets": [
                    {
                        "expr": f"{symbol}_rsi",
                        "legendFormat": "RSI"
                    }
                ]
            },
            # Panel de position
            {
                "id": 4,
                "title": "Position",
                "type": "stat",
                "targets": [
                    {
                        "expr": "position_size",
                        "legendFormat": "Size"
                    }
                ]
            },
            # Panel de PnL
            {
                "id": 5,
                "title": "PnL",
                "type": "stat",
                "targets": [
                    {
                        "expr": "pnl_total",
                        "legendFormat": "Total PnL"
                    }
                ]
            },
            # Panel de risque
            {
                "id": 6,
                "title": "Risk Metrics",
                "type": "table",
                "targets": [
                    {
                        "expr": "risk_metrics",
                        "legendFormat": "Risk"
                    }
                ]
            }
        ]
        
        dashboard = GrafanaDashboard(
            uid=f"trading_{symbol.lower()}",
            title=f"Trading Dashboard - {symbol}",
            description=f"Real-time trading dashboard for {symbol}",
            tags=["trading", "hedge", symbol],
            panels=panels,
            templating={
                "list": [
                    {
                        "name": "symbol",
                        "type": "query",
                        "query": f"label_values({symbol})"
                    }
                ]
            }
        )
        
        await self.create_dashboard(dashboard)
        return dashboard
    
    async def create_hedge_dashboard(self) -> GrafanaDashboard:
        """Crée un dashboard de hedging."""
        panels = [
            # Panel d'exposition
            {
                "id": 1,
                "title": "Hedge Exposure",
                "type": "graph",
                "targets": [
                    {
                        "expr": "hedge_exposure_total",
                        "legendFormat": "Total Exposure"
                    },
                    {
                        "expr": "hedge_exposure_vega",
                        "legendFormat": "Vega Exposure"
                    },
                    {
                        "expr": "hedge_exposure_delta",
                        "legendFormat": "Delta Exposure"
                    }
                ]
            },
            # Panel de grecques
            {
                "id": 2,
                "title": "Greeks",
                "type": "stat",
                "targets": [
                    {
                        "expr": "greeks_delta",
                        "legendFormat": "Delta"
                    },
                    {
                        "expr": "greeks_gamma",
                        "legendFormat": "Gamma"
                    },
                    {
                        "expr": "greeks_vega",
                        "legendFormat": "Vega"
                    },
                    {
                        "expr": "greeks_theta",
                        "legendFormat": "Theta"
                    }
                ]
            },
            # Panel de performance
            {
                "id": 3,
                "title": "Hedge Performance",
                "type": "graph",
                "targets": [
                    {
                        "expr": "hedge_performance_pnl",
                        "legendFormat": "PnL"
                    },
                    {
                        "expr": "hedge_performance_sharpe",
                        "legendFormat": "Sharpe"
                    }
                ]
            },
            # Panel de volatilité
            {
                "id": 4,
                "title": "Volatility Analysis",
                "type": "heatmap",
                "targets": [
                    {
                        "expr": "volatility_surface",
                        "legendFormat": "Vol Surface"
                    }
                ]
            }
        ]
        
        dashboard = GrafanaDashboard(
            uid="hedge_dashboard",
            title="Hedge Bot Dashboard",
            description="Comprehensive hedge bot monitoring dashboard",
            tags=["hedge", "monitoring"],
            panels=panels
        )
        
        await self.create_dashboard(dashboard)
        return dashboard
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._dashboards_lock:
            self._stats["dashboard_count"] = len(self._dashboards)
        with self._alerts_lock:
            self._stats["alert_count"] = len(self._alerts)
        with self._metrics_lock:
            self._stats["metric_count"] = sum(len(m) for m in self._metrics_cache.values())
        
        return self._stats.copy()


# ============== DASHBOARD BUILDER ==============

class DashboardBuilder:
    """
    Constructeur de dashboards Grafana.
    Facilite la création de dashboards complexes.
    """
    
    def __init__(self):
        self._dashboard = {
            "panels": [],
            "templating": {"list": []}
        }
        self._panel_id = 1
    
    def add_graph_panel(
        self,
        title: str,
        queries: List[Dict[str, Any]],
        grid_pos: Optional[Dict[str, int]] = None
    ) -> 'DashboardBuilder':
        """Ajoute un panel graphique."""
        panel = {
            "id": self._panel_id,
            "title": title,
            "type": "graph",
            "targets": queries,
            "gridPos": grid_pos or {"h": 8, "w": 12, "x": 0, "y": 0}
        }
        self._dashboard["panels"].append(panel)
        self._panel_id += 1
        return self
    
    def add_stat_panel(
        self,
        title: str,
        query: Dict[str, Any],
        grid_pos: Optional[Dict[str, int]] = None
    ) -> 'DashboardBuilder':
        """Ajoute un panel statistique."""
        panel = {
            "id": self._panel_id,
            "title": title,
            "type": "stat",
            "targets": [query],
            "gridPos": grid_pos or {"h": 4, "w": 4, "x": 0, "y": 0}
        }
        self._dashboard["panels"].append(panel)
        self._panel_id += 1
        return self
    
    def add_table_panel(
        self,
        title: str,
        query: Dict[str, Any],
        grid_pos: Optional[Dict[str, int]] = None
    ) -> 'DashboardBuilder':
        """Ajoute un panel tableau."""
        panel = {
            "id": self._panel_id,
            "title": title,
            "type": "table",
            "targets": [query],
            "gridPos": grid_pos or {"h": 8, "w": 12, "x": 0, "y": 0}
        }
        self._dashboard["panels"].append(panel)
        self._panel_id += 1
        return self
    
    def add_heatmap_panel(
        self,
        title: str,
        query: Dict[str, Any],
        grid_pos: Optional[Dict[str, int]] = None
    ) -> 'DashboardBuilder':
        """Ajoute un panel heatmap."""
        panel = {
            "id": self._panel_id,
            "title": title,
            "type": "heatmap",
            "targets": [query],
            "gridPos": grid_pos or {"h": 8, "w": 12, "x": 0, "y": 0}
        }
        self._dashboard["panels"].append(panel)
        self._panel_id += 1
        return self
    
    def add_variable(
        self,
        name: str,
        query: str,
        label: Optional[str] = None
    ) -> 'DashboardBuilder':
        """Ajoute une variable."""
        variable = {
            "name": name,
            "type": "query",
            "query": query,
            "label": label or name,
            "includeAll": True,
            "multi": True
        }
        self._dashboard["templating"]["list"].append(variable)
        return self
    
    def build(self) -> Dict[str, Any]:
        """Construit le dashboard."""
        return self._dashboard


# ============== FACTORY ==============

class GrafanaFactory:
    """Factory pour créer des composants Grafana."""
    
    @staticmethod
    async def create_engine(
        url: str,
        api_key: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> GrafanaEngine:
        """Crée un moteur Grafana."""
        engine = GrafanaEngine(
            url=url,
            api_key=api_key,
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_builder() -> DashboardBuilder:
        """Crée un constructeur de dashboards."""
        return DashboardBuilder()


# ============== EXPORT ==============

__all__ = [
    "GrafanaPanelType",
    "GrafanaDataSource",
    "GrafanaAlertSeverity",
    "GrafanaDashboard",
    "GrafanaAlert",
    "GrafanaMetric",
    "GrafanaEngineInterface",
    "GrafanaEngine",
    "DashboardBuilder",
    "GrafanaFactory"
]

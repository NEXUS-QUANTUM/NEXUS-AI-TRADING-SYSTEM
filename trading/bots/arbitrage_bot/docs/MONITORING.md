# NEXUS AI Trading System - Monitoring Guide

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Architecture de Monitoring](#architecture-de-monitoring)
3. [Métriques Collectées](#métriques-collectées)
4. [Configuration de Prometheus](#configuration-de-prometheus)
5. [Configuration de Grafana](#configuration-de-grafana)
6. [Alertes](#alertes)
7. [Logs](#logs)
8. [Tracing](#tracing)
9. [Health Checks](#health-checks)
10. [Tableaux de Bord](#tableaux-de-bord)
11. [Bonnes Pratiques](#bonnes-pratiques)
12. [Exemples](#exemples)

---

## Introduction

Le monitoring est essentiel pour garantir la fiabilité et la performance du NEXUS AI Trading System. Ce guide détaille l'infrastructure de monitoring, les métriques collectées, et les procédures d'alerte.

### Architecture de Monitoring

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEXUS AI Trading System                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  Prometheus   │           │  Loki         │           │  Tempo        │
│  Metrics      │           │  Logs         │           │  Traces       │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Grafana                                       │
│                          (Dashboard & Alerts)                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Métriques Collectées

### Métriques Système

```yaml
system_metrics:
  # CPU
  cpu:
    - "cpu_usage_percent"
    - "cpu_load_avg_1m"
    - "cpu_load_avg_5m"
    - "cpu_load_avg_15m"
  
  # Mémoire
  memory:
    - "memory_usage_percent"
    - "memory_used_bytes"
    - "memory_available_bytes"
    - "memory_total_bytes"
  
  # Disque
  disk:
    - "disk_usage_percent"
    - "disk_used_bytes"
    - "disk_free_bytes"
    - "disk_total_bytes"
  
  # Réseau
  network:
    - "network_bytes_sent"
    - "network_bytes_recv"
    - "network_packets_sent"
    - "network_packets_recv"
```

### Métriques Application

```yaml
application_metrics:
  # Trading
  trading:
    - "trades_total"
    - "trades_successful"
    - "trades_failed"
    - "trades_pnl_total"
    - "trades_win_rate"
    - "trades_volume"
    - "trades_latency"
    - "trades_slippage"
  
  # Stratégies
  strategies:
    - "strategies_active"
    - "opportunities_detected"
    - "opportunities_executed"
    - "strategy_pnl"
    - "strategy_win_rate"
  
  # Exchanges
  exchanges:
    - "exchange_connections"
    - "exchange_latency"
    - "exchange_requests"
    - "exchange_errors"
    - "exchange_balance"
  
  # Risques
  risk:
    - "risk_drawdown"
    - "risk_var"
    - "risk_cvar"
    - "risk_positions"
    - "risk_exposure"
```

### Métriques Performance

```yaml
performance_metrics:
  # API
  api:
    - "api_requests_total"
    - "api_requests_duration_seconds"
    - "api_requests_errors"
    - "api_requests_success_rate"
  
  # WebSocket
  websocket:
    - "websocket_connections"
    - "websocket_messages_received"
    - "websocket_messages_sent"
    - "websocket_errors"
  
  # Base de Données
  database:
    - "db_connections"
    - "db_queries"
    - "db_query_duration"
    - "db_errors"
  
  # Cache
  cache:
    - "cache_hits"
    - "cache_misses"
    - "cache_hit_rate"
    - "cache_size"
```

---

## Configuration de Prometheus

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'nexus'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - "rules/*.yml"

scrape_configs:
  # Backend API
  - job_name: 'nexus-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'backend'
  
  # WebSocket Service
  - job_name: 'nexus-websocket'
    static_configs:
      - targets: ['websocket:8001']
    metrics_path: '/metrics'
  
  # PostgreSQL
  - job_name: 'postgresql'
    static_configs:
      - targets: ['postgres-exporter:9187']
  
  # Redis
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
  
  # Node (System)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Règles de Recording

```yaml
# rules/recording.yml
groups:
  - name: recording_rules
    rules:
      - record: nexus:trades:rate1m
        expr: rate(trades_total[1m])
      
      - record: nexus:trades:success_rate
        expr: trades_successful / trades_total
      
      - record: nexus:api:latency_p95
        expr: histogram_quantile(0.95, sum(rate(api_requests_duration_bucket[5m])) by (le))
      
      - record: nexus:cache:hit_rate
        expr: cache_hits / (cache_hits + cache_misses)
```

### Règles d'Alerte

```yaml
# rules/alerts.yml
groups:
  - name: nexus_alerts
    rules:
      # System
      - alert: HighCPUUsage
        expr: cpu_usage_percent > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"
      
      - alert: HighMemoryUsage
        expr: memory_usage_percent > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}%"
      
      # Trading
      - alert: LowWinRate
        expr: trades_win_rate < 0.40
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Low win rate"
          description: "Win rate is {{ $value }}%"
      
      - alert: HighDrawdown
        expr: risk_drawdown > 0.10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High drawdown"
          description: "Drawdown is {{ $value }}%"
      
      # API
      - alert: HighAPILatency
        expr: api_requests_duration_seconds > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency"
          description: "API latency is {{ $value }}s"
      
      - alert: HighAPIErrorRate
        expr: api_requests_errors / api_requests_total > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate"
          description: "API error rate is {{ $value }}%"
      
      # Exchanges
      - alert: ExchangeDisconnected
        expr: exchange_connections == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Exchange disconnected"
          description: "Exchange connection lost"
      
      # Database
      - alert: DatabaseDown
        expr: db_connections == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database is down"
          description: "No database connections"
```

---

## Configuration de Grafana

### Datasources

```yaml
# datasources.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      timeInterval: 15s
      queryTimeout: 30s
  
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    jsonData:
      maxLines: 1000
  
  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
```

### Dashboards

```json
{
  "dashboard": {
    "id": null,
    "title": "NEXUS Trading Dashboard",
    "tags": ["nexus", "trading"],
    "timezone": "browser",
    "panels": [
      {
        "title": "PNL Evolution",
        "type": "graph",
        "targets": [
          {
            "expr": "trades_pnl_total",
            "legendFormat": "Total PNL"
          }
        ],
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8}
      },
      {
        "title": "Trade Volume",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(trades_total[5m])",
            "legendFormat": "Trades/min"
          }
        ],
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8}
      },
      {
        "title": "Win Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "trades_win_rate",
            "legendFormat": "Win Rate"
          }
        ],
        "gridPos": {"x": 0, "y": 8, "w": 4, "h": 4}
      },
      {
        "title": "Drawdown",
        "type": "stat",
        "targets": [
          {
            "expr": "risk_drawdown",
            "legendFormat": "Drawdown"
          }
        ],
        "gridPos": {"x": 4, "y": 8, "w": 4, "h": 4}
      },
      {
        "title": "Sharpe Ratio",
        "type": "stat",
        "targets": [
          {
            "expr": "sharpe_ratio",
            "legendFormat": "Sharpe Ratio"
          }
        ],
        "gridPos": {"x": 8, "y": 8, "w": 4, "h": 4}
      },
      {
        "title": "System Health",
        "type": "graph",
        "targets": [
          {
            "expr": "cpu_usage_percent",
            "legendFormat": "CPU"
          },
          {
            "expr": "memory_usage_percent",
            "legendFormat": "Memory"
          }
        ],
        "gridPos": {"x": 0, "y": 12, "w": 12, "h": 8}
      },
      {
        "title": "Opportunities",
        "type": "graph",
        "targets": [
          {
            "expr": "opportunities_detected",
            "legendFormat": "Detected"
          },
          {
            "expr": "opportunities_executed",
            "legendFormat": "Executed"
          }
        ],
        "gridPos": {"x": 12, "y": 12, "w": 12, "h": 8}
      }
    ],
    "refresh": "10s",
    "time": {"from": "now-6h", "to": "now"}
  }
}
```

---

## Alertes

### Configuration Alertmanager

```yaml
# alertmanager.yml
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      continue: true
    - match:
        severity: warning
      receiver: 'warning'

receivers:
  - name: 'default'
    email_configs:
      - to: 'alerts@nexustradingia.com'
        from: 'alertmanager@nexustradingia.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alertmanager@nexustradingia.com'
        auth_identity: 'alertmanager@nexustradingia.com'
        auth_password: '${SMTP_PASSWORD}'
  
  - name: 'critical'
    webhook_configs:
      - url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        send_resolved: true
    email_configs:
      - to: 'critical@nexustradingia.com'
  
  - name: 'warning'
    email_configs:
      - to: 'warnings@nexustradingia.com'
```

### Alertes par Canal

```yaml
alert_channels:
  # 1. Slack
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
    channel: "#alerts"
    username: "Nexus Alert"
    icon_emoji: ":warning:"
  
  # 2. Email
  email:
    enabled: true
    to: "alerts@nexustradingia.com"
    from: "alertmanager@nexustradingia.com"
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
  
  # 3. PagerDuty
  pagerduty:
    enabled: true
    integration_key: "YOUR_PAGERDUTY_KEY"
    severity: "critical"
  
  # 4. Telegram
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
```

---

## Logs

### Configuration Loki

```yaml
# loki-config.yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
  replication_factor: 1
  path_prefix: /tmp/loki

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /tmp/loki/boltdb-shipper-active
    cache_location: /tmp/loki/boltdb-shipper-cache
    cache_ttl: 24h
    shared_store: filesystem
  filesystem:
    directory: /tmp/loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: false
  retention_period: 0s
```

### Promtail Configuration

```yaml
# promtail-config.yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: nexus
    static_configs:
      - targets: [localhost]
        labels:
          job: nexus
          __path__: /var/log/nexus/*.log
    pipeline_stages:
      - json:
          expressions:
            timestamp: timestamp
            level: level
            message: message
      - timestamp:
          source: timestamp
          format: RFC3339
      - labels:
          level:
```

---

## Tracing

### Configuration Tempo

```yaml
# tempo-config.yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    jaeger:
      protocols:
        thrift_http:
          endpoint: 0.0.0.0:14268
        thrift_binary:
          endpoint: 0.0.0.0:6832
        thrift_compact:
          endpoint: 0.0.0.0:6831

ingester:
  trace_idle_period: 10s
  max_block_bytes: 1_000_000
  max_block_duration: 5m

compactor:
  compaction:
    compaction_window: 1h
    max_block_bytes: 100_000_000
    block_retention: 24h

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal
```

### Instrumentation

```python
# tracing.py
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def setup_tracing(service_name: str = "nexus-trading"):
    """Configure le tracing"""
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })
    
    tracer_provider = TracerProvider(resource=resource)
    
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger",
        agent_port=6831,
    )
    
    span_processor = BatchSpanProcessor(jaeger_exporter)
    tracer_provider.add_span_processor(span_processor)
    
    trace.set_tracer_provider(tracer_provider)
    
    return trace.get_tracer(__name__)

# Utilisation
tracer = setup_tracing()

with tracer.start_as_current_span("trade_execution"):
    # Code de trading
    with tracer.start_as_current_span("order_validation"):
        validate_order()
    with tracer.start_as_current_span("order_execution"):
        execute_order()
```

---

## Health Checks

### Endpoints Health

```python
# health.py
from fastapi import APIRouter
from typing import Dict, Any
import psutil
import time

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check complet"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "2.0.0",
        "components": {
            "api": {
                "status": "healthy",
                "uptime": time.time() - start_time
            },
            "database": await check_database(),
            "redis": await check_redis(),
            "exchanges": await check_exchanges(),
        },
        "system": {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent
        }
    }

@router.get("/health/live")
async def liveness_check() -> Dict[str, str]:
    """Liveness probe"""
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness_check() -> Dict[str, str]:
    """Readiness probe"""
    return {"status": "ready"}
```

---

## Tableaux de Bord

### Dashboard Trading

```json
{
  "dashboard": {
    "title": "NEXUS Trading Dashboard",
    "panels": [
      {
        "title": "PNL",
        "type": "singlestat",
        "targets": [
          {
            "expr": "trades_pnl_total"
          }
        ],
        "valueName": "current"
      },
      {
        "title": "Trades",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(trades_total[1m])"
          }
        ]
      },
      {
        "title": "Win Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "trades_win_rate * 100"
          }
        ],
        "valueName": "current",
        "unit": "percent"
      },
      {
        "title": "Drawdown",
        "type": "singlestat",
        "targets": [
          {
            "expr": "risk_drawdown * 100"
          }
        ],
        "valueName": "current",
        "unit": "percent"
      },
      {
        "title": "Sharpe Ratio",
        "type": "singlestat",
        "targets": [
          {
            "expr": "sharpe_ratio"
          }
        ],
        "valueName": "current"
      },
      {
        "title": "System Health",
        "type": "graph",
        "targets": [
          {
            "expr": "cpu_usage_percent",
            "legendFormat": "CPU"
          },
          {
            "expr": "memory_usage_percent",
            "legendFormat": "Memory"
          },
          {
            "expr": "disk_usage_percent",
            "legendFormat": "Disk"
          }
        ]
      }
    ]
  }
}
```

---

## Bonnes Pratiques

### Métriques

1. **Nommage Cohérent**
   ```yaml
   ✅ trades_pnl_total
   ✅ trades_win_rate
   ✅ trades_volume
   
   ❌ pnl
   ❌ win
   ❌ vol
   ```

2. **Labels Utiles**
   ```yaml
   ✅ trades_total{exchange="binance",symbol="BTC/USDT"}
   ✅ trades_total{strategy="cross_exchange"}
   
   ❌ trades_total{}
   ```

3. **Unités Standardisées**
   ```yaml
   ✅ trades_latency_seconds
   ✅ trades_volume_dollars
   
   ❌ trades_latency
   ❌ trades_volume
   ```

### Alertes

1. **Seuils Pertinents**
   ```yaml
   ✅ cpu_usage > 80%
   ✅ memory_usage > 80%
   ✅ disk_usage > 90%
   
   ❌ cpu_usage > 0%
   ```

2. **Durées Appropriées**
   ```yaml
   ✅ for: 5m
   ✅ for: 10m
   
   ❌ for: 0s
   ```

3. **Descriptions Claires**
   ```yaml
   ✅ "CPU usage is {{ $value }}%"
   ✅ "Memory usage is {{ $value }}%"
   
   ❌ "High CPU"
   ```

---

## Exemples

### Exemple Complet

```python
# monitoring_setup.py
import prometheus_client
from prometheus_client import Counter, Gauge, Histogram, Summary

# Métriques Trading
trades_total = Counter('trades_total', 'Total trades')
trades_successful = Counter('trades_successful', 'Successful trades')
trades_failed = Counter('trades_failed', 'Failed trades')
trades_pnl_total = Gauge('trades_pnl_total', 'Total PNL')
trades_win_rate = Gauge('trades_win_rate', 'Win rate')
trades_latency = Histogram('trades_latency_seconds', 'Trade latency')

# Métriques Système
cpu_usage = Gauge('cpu_usage_percent', 'CPU usage')
memory_usage = Gauge('memory_usage_percent', 'Memory usage')
disk_usage = Gauge('disk_usage_percent', 'Disk usage')

# Métriques API
api_requests = Counter('api_requests_total', 'Total API requests')
api_errors = Counter('api_errors_total', 'Total API errors')
api_duration = Histogram('api_duration_seconds', 'API duration')

# Exemple d'utilisation
def record_trade(success: bool, pnl: float, latency: float):
    trades_total.inc()
    
    if success:
        trades_successful.inc()
    else:
        trades_failed.inc()
    
    trades_pnl_total.set(pnl)
    trades_win_rate.set(trades_successful._value / trades_total._value)
    trades_latency.observe(latency)

# Démarrer le serveur metrics
prometheus_client.start_http_server(9090)

print("Monitoring started on port 9090")
```

---

## 📚 Ressources Additionnelles

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Loki Documentation](https://grafana.com/docs/loki/latest/)
- [Tempo Documentation](https://grafana.com/docs/tempo/latest/)

---

## 📞 Support

Pour toute question ou problème, veuillez contacter:

- **Email**: support@nexustradingia.com
- **Discord**: [Nexus Trading IA](https://discord.gg/nexustradingia)
- **Telegram**: [@NexusTradingIA](https://t.me/NexusTradingIA)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

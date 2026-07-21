# NEXUS AI Trading System - Configuration Guide

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Structure de Configuration](#structure-de-configuration)
3. [Configuration du Bot](#configuration-du-bot)
4. [Configuration des Exchanges](#configuration-des-exchanges)
5. [Configuration des Stratégies](#configuration-des-stratégies)
6. [Configuration des Risques](#configuration-des-risques)
7. [Configuration de l'Exécution](#configuration-de-lexécution)
8. [Configuration des Données de Marché](#configuration-des-données-de-marché)
9. [Configuration des Métriques](#configuration-des-métriques)
10. [Configuration des Logs](#configuration-des-logs)
11. [Configuration de la Base de Données](#configuration-de-la-base-de-données)
12. [Configuration du Cache](#configuration-du-cache)
13. [Configuration des Notifications](#configuration-des-notifications)
14. [Configuration de l'API](#configuration-de-lapi)
15. [Configuration WebSocket](#configuration-websocket)
16. [Configuration du Monitoring](#configuration-du-monitoring)
17. [Configuration du Scheduler](#configuration-du-scheduler)
18. [Configuration de la Sécurité](#configuration-de-la-sécurité)
19. [Configuration de la Conformité](#configuration-de-la-conformité)
20. [Variables d'Environnement](#variables-denvironnement)
21. [Exemples de Configuration](#exemples-de-configuration)

---

## Introduction

Le système NEXUS AI Trading utilise un fichier de configuration YAML centralisé pour gérer tous les aspects du bot d'arbitrage. Ce guide détaille chaque section de la configuration et fournit des exemples pour vous aider à configurer le système selon vos besoins.

### 📁 Fichiers de Configuration

| Fichier | Description |
|---------|-------------|
| `config/default_config.yaml` | Configuration par défaut |
| `config/development_config.yaml` | Configuration de développement |
| `config/production_config.yaml` | Configuration de production |
| `config/staging_config.yaml` | Configuration de staging |
| `config/arbitrage_config.yaml` | Configuration principale |

### 🔄 Ordre de Chargement

1. Configuration par défaut
2. Configuration du fichier spécifié
3. Variables d'environnement (override)
4. Paramètres de ligne de commande

---

## Structure de Configuration

### Structure Générale

```yaml
# ============================================================
# NEXUS AI TRADING SYSTEM - Arbitrage Bot Configuration
# ============================================================

bot:
  # Identité du bot
  id: "arbitrage-bot-001"
  name: "NEXUS Arbitrage Bot"
  version: "2.0.0"
  environment: "production"  # development | staging | production
  instance: "prod-001"
  deployment: "kubernetes"

general:
  # Paramètres généraux
  enabled: true
  debug: false
  log_level: "info"
  timezone: "UTC"
  max_concurrent_operations: 20

exchanges:
  # Configuration des exchanges
  binance:
    enabled: true
    api:
      key: "${BINANCE_API_KEY}"
      secret: "${BINANCE_API_SECRET}"

strategies:
  # Configuration des stratégies
  cross_exchange:
    enabled: true
    min_profit_threshold: 0.005

risk_management:
  # Configuration des risques
  enabled: true
  max_drawdown: 0.15

execution:
  # Configuration de l'exécution
  enabled: true
  mode: "smart"
```

---

## Configuration du Bot

```yaml
bot:
  id: "arbitrage-bot-001"
  name: "NEXUS Arbitrage Bot"
  version: "2.0.0"
  description: "Bot d'arbitrage algorithmique avancé"
  environment: "production"
  instance: "prod-001"
  deployment: "kubernetes"
  region: "eu-west-1"
  cluster: "nexus-prod"
```

### Paramètres

| Paramètre | Type | Description | Valeur par défaut |
|-----------|------|-------------|-------------------|
| `id` | string | Identifiant unique du bot | `"arbitrage-bot-001"` |
| `name` | string | Nom du bot | `"NEXUS Arbitrage Bot"` |
| `version` | string | Version du bot | `"2.0.0"` |
| `description` | string | Description du bot | `"Bot d'arbitrage algorithmique avancé"` |
| `environment` | enum | Environnement (`development`, `staging`, `production`) | `"production"` |
| `instance` | string | Nom de l'instance | `"prod-001"` |
| `deployment` | string | Type de déploiement | `"kubernetes"` |
| `region` | string | Région de déploiement | `"eu-west-1"` |
| `cluster` | string | Nom du cluster | `"nexus-prod"` |

---

## Configuration Générale

```yaml
general:
  enabled: true
  debug: false
  log_level: "info"
  timezone: "UTC"
  locale: "en_US"
  max_concurrent_operations: 20
  operation_timeout: 30
  retry_attempts: 5
  retry_delay: 5
  shutdown_timeout: 30
  startup_timeout: 60
  health_check_interval: 10
  enable_profiling: false
  enable_metrics: true
  enable_tracing: true
  graceful_shutdown: true
  emergency_stop: true
```

### Paramètres

| Paramètre | Type | Description | Valeur par défaut |
|-----------|------|-------------|-------------------|
| `enabled` | boolean | Activer le bot | `true` |
| `debug` | boolean | Mode debug | `false` |
| `log_level` | enum | Niveau de log (`debug`, `info`, `warning`, `error`) | `"info"` |
| `timezone` | string | Fuseau horaire | `"UTC"` |
| `locale` | string | Locale | `"en_US"` |
| `max_concurrent_operations` | integer | Nombre max d'opérations simultanées | `20` |
| `operation_timeout` | integer | Timeout des opérations (secondes) | `30` |
| `retry_attempts` | integer | Nombre de tentatives | `5` |
| `retry_delay` | integer | Délai entre les tentatives (secondes) | `5` |
| `shutdown_timeout` | integer | Timeout d'arrêt (secondes) | `30` |
| `startup_timeout` | integer | Timeout de démarrage (secondes) | `60` |
| `health_check_interval` | integer | Intervalle de health check (secondes) | `10` |
| `enable_profiling` | boolean | Activer le profiling | `false` |
| `enable_metrics` | boolean | Activer les métriques | `true` |
| `enable_tracing` | boolean | Activer le tracing | `true` |
| `graceful_shutdown` | boolean | Arrêt gracieux | `true` |
| `emergency_stop` | boolean | Arrêt d'urgence | `true` |

---

## Configuration des Exchanges

### Structure Générale

```yaml
exchanges:
  binance:
    enabled: true
    name: "Binance"
    type: "cex"
    priority: 1
    tier: "premium"
    production_ready: true
    
    api:
      key: "${BINANCE_API_KEY}"
      secret: "${BINANCE_API_SECRET}"
      passphrase: ""
    
    endpoints:
      rest: "https://api.binance.com"
      websocket: "wss://stream.binance.com:9443/ws"
    
    rate_limits:
      requests_per_second: 50
      orders_per_second: 10
    
    options:
      use_spot: true
      use_futures: true
      use_margin: false
    
    trading_pairs:
      spot:
        - "BTC/USDT"
        - "ETH/USDT"
      futures:
        - "BTC/USDT"
        - "ETH/USDT"
    
    fee:
      maker: 0.001
      taker: 0.001
      futures_maker: 0.0002
      futures_taker: 0.0004
      discount: 0.25
      discount_asset: "BNB"
    
    min_order_size:
      BTC_USDT: 0.0001
      default: 0.001
    
    lot_size:
      BTC_USDT: 0.00001
      default: 0.0001
    
    security:
      withdraw_whitelist: true
      ip_whitelist: true
      api_key_permissions:
        - "spot"
        - "futures"
    
    markets:
      - "spot"
      - "futures"
    
    features:
      - "limit_orders"
      - "market_orders"
      - "stop_orders"
      - "trailing_stop_orders"
      - "oco_orders"
      - "iceberg_orders"
    
    websocket_streams:
      - "depth"
      - "trade"
      - "kline"
      - "ticker"
    
    klines:
      intervals:
        - "1m"
        - "5m"
        - "15m"
        - "1h"
        - "4h"
        - "1d"
      max_limit: 1000
    
    maintenance:
      scheduled_downtime: true
      weekly_maintenance: "Sunday 06:00 UTC"
      notification_channels:
        - "telegram"
        - "email"
```

### Exchanges Supportés

| Exchange | Type | Testnet/Sandbox | Documentation |
|----------|------|-----------------|---------------|
| Binance | CEX | ✅ | [Binance API](https://binance-docs.github.io/apidocs/) |
| Bybit | CEX | ✅ | [Bybit API](https://bybit-exchange.github.io/docs/) |
| Coinbase | CEX | ✅ | [Coinbase API](https://docs.cloud.coinbase.com/) |
| Kraken | CEX | ✅ | [Kraken API](https://docs.kraken.com/) |
| KuCoin | CEX | ✅ | [KuCoin API](https://docs.kucoin.com/) |
| OKX | CEX | ✅ | [OKX API](https://www.okx.com/docs/) |
| Gate.io | CEX | ✅ | [Gate.io API](https://www.gate.io/docs/) |
| Uniswap | DEX | ✅ | [Uniswap API](https://docs.uniswap.org/) |
| PancakeSwap | DEX | ✅ | [PancakeSwap API](https://docs.pancakeswap.finance/) |

---

## Configuration des Stratégies

### Cross-Exchange Arbitrage

```yaml
strategies:
  cross_exchange:
    enabled: true
    name: "Cross-Exchange Arbitrage"
    description: "Exploite les différences de prix entre les exchanges"
    type: "arbitrage"
    priority: 1
    
    parameters:
      min_profit_threshold: 0.005
      max_spread_percentage: 0.15
      min_volume_threshold: 1000
      max_position_size: 50000
      execution_timeout: 30
      max_execution_attempts: 3
      min_time_between_trades: 10
      max_trades_per_minute: 5
      slippage_tolerance: 0.002
    
    profit_optimization:
      enabled: true
      type: "adaptive"
      min_profit_adjustment: 0.001
      max_profit_adjustment: 0.01
      adjustment_period: 60
      volatility_factor: 0.5
    
    pairs:
      - pair: "BTC/USDT"
        min_profit: 0.008
        max_spread: 0.20
        min_volume: 5000
        max_position: 50000
        priority: 1
        exchanges:
          - "binance"
          - "bybit"
          - "coinbase"
    
    risk:
      max_drawdown: 0.05
      max_loss_per_trade: 0.01
      max_loss_per_day: 0.02
      max_consecutive_losses: 3
      stop_loss: 0.02
      take_profit: 0.03
    
    execution:
      order_type: "limit"
      order_timeout: 30
      fill_or_kill: false
      post_only: true
      reduce_only: false
    
    filters:
      min_liquidity: 5000
      max_slippage: 0.005
      min_order_book_depth: 10
      max_order_book_spread: 0.002
```

### Triangular Arbitrage

```yaml
strategies:
  triangular:
    enabled: true
    name: "Triangular Arbitrage"
    type: "arbitrage"
    priority: 2
    
    parameters:
      min_profit_threshold: 0.008
      max_position_size: 30000
      execution_timeout: 25
      max_execution_attempts: 3
      min_time_between_trades: 10
      slippage_tolerance: 0.003
    
    cycles:
      - name: "BTC-ETH-USDT"
        pairs:
          - "BTC/USDT"
          - "ETH/BTC"
          - "ETH/USDT"
        min_profit: 0.008
        max_position: 30000
        priority: 1
        exchanges:
          - "binance"
          - "bybit"
      
      - name: "SOL-BTC-USDT"
        pairs:
          - "SOL/USDT"
          - "BTC/SOL"
          - "BTC/USDT"
        min_profit: 0.010
        max_position: 20000
        priority: 2
        exchanges:
          - "binance"
          - "bybit"
          - "kucoin"
```

### Statistical Arbitrage

```yaml
strategies:
  statistical:
    enabled: true
    name: "Statistical Arbitrage"
    type: "statistical_arbitrage"
    priority: 3
    
    parameters:
      min_profit_threshold: 0.010
      lookback_period: 100
      cointegration_confidence: 0.95
      z_score_threshold: 2.0
      half_life: 20
      max_position_size: 20000
      min_time_between_trades: 15
      max_trades_per_day: 20
    
    model:
      type: "cointegration"
      methods:
        - "engle_granger"
        - "johansen"
        - "kalman_filter"
      update_frequency: 3600
      retrain_frequency: 86400
    
    indicators:
      - name: "z_score"
        period: 20
        threshold: 2.0
      - name: "moving_average"
        period: 50
        type: "sma"
    
    pairs:
      - pair1: "BTC/USDT"
        pair2: "ETH/USDT"
        hedge_ratio: 0.5
        min_profit: 0.010
        max_position: 20000
        priority: 1
        exchanges:
          - "binance"
          - "bybit"
```

---

## Configuration des Risques

```yaml
risk_management:
  enabled: true
  max_drawdown: 0.15
  daily_loss_limit: 0.05
  weekly_loss_limit: 0.10
  max_positions: 10
  max_positions_per_pair: 3
  max_positions_per_exchange: 5
  
  position_sizing:
    strategy: "adaptive"
    fixed_size: 1000
    max_position_size: 50000
    min_position_size: 100
    kelly_fraction: 0.25
    volatility_factor: 0.5
    adaptive_factor: 0.3
  
  stop_loss:
    enabled: true
    type: "trailing"
    percentage: 0.02
    trailing_offset: 0.01
    min_trailing: 0.005
    max_trailing: 0.05
    dynamic_factor: 0.5
  
  take_profit:
    enabled: true
    type: "multiple"
    targets:
      - 0.01
      - 0.02
      - 0.03
      - 0.05
    allocation:
      - 0.25
      - 0.25
      - 0.25
      - 0.25
    trailing_activation: 0.015
  
  circuit_breaker:
    enabled: true
    consecutive_failures: 5
    failure_window: 60
    cooldown_period: 300
    max_failures_per_hour: 20
    max_failures_per_day: 100
  
  drawdown_protection:
    enabled: true
    max_drawdown_daily: 0.05
    max_drawdown_weekly: 0.10
    max_drawdown_monthly: 0.15
    action: "reduce"
    reduce_factor: 0.5
    recovery_threshold: 0.03
```

---

## Configuration de l'Exécution

```yaml
execution:
  enabled: true
  mode: "smart"
  order_types:
    - "market"
    - "limit"
    - "stop_loss"
    - "take_profit"
    - "trailing_stop"
    - "oco"
    - "iceberg"
    - "twap"
  
  order_routing:
    enabled: true
    strategy: "smart"
    max_slippage: 0.005
    min_liquidity: 5000
    max_route_depth: 3
  
  batch_execution:
    enabled: true
    max_batch_size: 10
    batch_timeout: 5
    batch_delay: 1
  
  timeout:
    order: 30
    execution: 60
    settlement: 120
    broadcast: 10
  
  retry:
    enabled: true
    max_attempts: 3
    delay: 2
    backoff: 2.0
    max_delay: 30
  
  validation:
    enabled: true
    check_balance: true
    check_limits: true
    check_risk: true
    check_market: true
```

---

## Configuration des Données de Marché

```yaml
market_data:
  enabled: true
  source: "aggregated"
  providers:
    - "binance"
    - "bybit"
    - "coinbase"
    - "kraken"
    - "kucoin"
    - "okx"
    - "gateio"
  
  tickers:
    update_interval: 1
    batch_size: 100
    cache_ttl: 5
  
  order_book:
    update_interval: 5
    depth: 100
    cache_ttl: 10
  
  candles:
    enabled: true
    intervals:
      - "1m"
      - "5m"
      - "15m"
      - "1h"
      - "4h"
      - "1d"
    retention: 1000
    cache_ttl: 60
  
  websocket:
    enabled: true
    reconnect_attempts: 10
    reconnect_delay: 5
    heartbeat_interval: 30
    ping_timeout: 10
    max_retries: 10
  
  quality:
    min_volume: 1000
    min_trades: 10
    max_age: 30
    require_websocket: true
```

---

## Configuration des Métriques

```yaml
metrics:
  enabled: true
  collection_interval: 10
  retention: 86400
  aggregation_interval: 60
  
  metrics:
    - "pnl"
    - "trades"
    - "volume"
    - "win_rate"
    - "sharpe_ratio"
    - "max_drawdown"
    - "profit_factor"
    - "avg_profit"
    - "avg_loss"
    - "avg_trade_duration"
    - "execution_latency"
    - "order_fill_rate"
    - "slippage"
    - "fee_cost"
    - "opportunity_rate"
    - "success_rate"
    - "calmar_ratio"
    - "sortino_ratio"
    - "omega_ratio"
  
  reporting:
    enabled: true
    interval: 3600
    format: "json"
    output: "api"
  
  alerts:
    enabled: true
    channels:
      - "telegram"
      - "email"
      - "slack"
      - "webhook"
      - "pagerduty"
    min_interval: 60
```

---

## Configuration des Logs

```yaml
logging:
  enabled: true
  level: "info"
  format: "json"
  colorize: false
  
  outputs:
    - type: "console"
      enabled: true
      colorize: false
      format: "json"
    
    - type: "file"
      enabled: true
      path: "/var/log/nexus/arbitrage.log"
      max_size: 104857600
      max_files: 30
      format: "json"
      compress: true
    
    - type: "elasticsearch"
      enabled: true
      host: "${ELASTICSEARCH_HOST}"
      port: 9200
      index: "nexus-arbitrage-prod"
      ssl: true
      username: "${ELASTICSEARCH_USER}"
      password: "${ELASTICSEARCH_PASSWORD}"
    
    - type: "loki"
      enabled: true
      host: "${LOKI_HOST}"
      port: 3100
      labels:
        service: "arbitrage-bot"
        environment: "production"
        version: "2.0.0"
  
  fields:
    service: "arbitrage-bot"
    environment: "production"
    version: "2.0.0"
    instance: "prod-001"
    cluster: "nexus-prod"
  
  filters:
    - "trace_id"
    - "span_id"
    - "request_id"
```

---

## Configuration de la Base de Données

```yaml
database:
  enabled: true
  type: "timescaledb"
  host: "${DB_HOST}"
  port: 5432
  name: "nexus_arbitrage"
  user: "${DB_USER}"
  password: "${DB_PASSWORD}"
  
  pool_size: 20
  max_overflow: 40
  timeout: 30
  pool_recycle: 3600
  pool_pre_ping: true
  
  ssl:
    enabled: true
    mode: "verify-full"
    ca: "/etc/ssl/certs/ca-certificates.crt"
    cert: "/etc/ssl/certs/client.crt"
    key: "/etc/ssl/private/client.key"
  
  backups:
    enabled: true
    interval: 86400
    retention: 30
    path: "s3://${BACKUP_BUCKET}/database/"
    compress: true
    encryption: true
  
  migrations:
    enabled: true
    auto_run: false
    path: "./migrations/prod"
    table: "schema_migrations"
    validate: true
  
  queries:
    timeout: 60
    max_rows: 100000
  
  timescaledb:
    enabled: true
    chunk_interval: "1 day"
    compression: true
    retention: "90 days"
    policies:
      - compression
      - retention
      - reorder
```

---

## Configuration du Cache

```yaml
cache:
  enabled: true
  type: "redis"
  host: "${REDIS_HOST}"
  port: 6379
  password: "${REDIS_PASSWORD}"
  db: 0
  
  pool:
    max_connections: 20
    min_connections: 5
  
  ttl:
    tickers: 60
    order_books: 30
    candles: 300
    opportunities: 10
    metrics: 300
    config: 600
  
  compression:
    enabled: true
    algorithm: "zstd"
    level: 3
  
  invalidation:
    strategy: "time"
    max_size: 10000
  
  monitoring:
    enabled: true
    hit_rate_alert: 0.70
    miss_rate_alert: 0.30
```

---

## Configuration des Notifications

```yaml
notifications:
  enabled: true
  
  channels:
    telegram:
      enabled: true
      bot_token: "${TELEGRAM_BOT_TOKEN}"
      chat_id: "${TELEGRAM_CHAT_ID}"
      parse_mode: "HTML"
      disable_notification: false
    
    slack:
      enabled: true
      webhook_url: "${SLACK_WEBHOOK_URL}"
      channel: "#arbitrage"
      username: "Nexus Arbitrage Bot"
      icon_emoji: ":robot_face:"
    
    email:
      enabled: true
      smtp_host: "${SMTP_HOST}"
      smtp_port: 587
      username: "${SMTP_USERNAME}"
      password: "${SMTP_PASSWORD}"
      from: "arbitrage@nexustradingia.com"
      to:
        - "alerts@nexustradingia.com"
        - "team@nexustradingia.com"
      cc:
        - "monitoring@nexustradingia.com"
    
    webhook:
      enabled: true
      url: "${WEBHOOK_URL}"
      headers:
        Authorization: "Bearer ${WEBHOOK_TOKEN}"
        Content-Type: "application/json"
    
    pagerduty:
      enabled: true
      integration_key: "${PAGERDUTY_KEY}"
      severity: "critical"
  
  events:
    - "opportunity"
    - "execution"
    - "alert"
    - "error"
    - "status_change"
    - "daily_report"
    - "weekly_report"
    - "monthly_report"
    - "performance_alert"
    - "risk_alert"
    - "system_alert"
```

---

## Configuration de l'API

```yaml
api:
  enabled: true
  host: "0.0.0.0"
  port: 8000
  prefix: "/api/v1"
  workers: 4
  reload: false
  
  cors:
    enabled: true
    origins:
      - "https://nexustradingia.com"
      - "https://app.nexustradingia.com"
    methods:
      - "GET"
      - "POST"
      - "PUT"
      - "DELETE"
      - "OPTIONS"
    headers:
      - "Authorization"
      - "Content-Type"
    credentials: true
    max_age: 86400
  
  rate_limit:
    enabled: true
    requests_per_minute: 120
    burst: 30
    store: "redis"
    key_prefix: "rate_limit:api"
  
  authentication:
    enabled: true
    type: "jwt"
    jwt_secret: "${JWT_SECRET}"
    token_expiry: 3600
    refresh_token_expiry: 86400
    api_key_header: "X-API-Key"
    api_keys:
      - user: "admin"
        key: "${ADMIN_API_KEY}"
      - user: "service"
        key: "${SERVICE_API_KEY}"
      - user: "monitoring"
        key: "${MONITORING_API_KEY}"
  
  documentation:
    enabled: true
    path: "/docs"
    title: "NEXUS Arbitrage Bot API"
    version: "2.0.0"
    description: "API pour le bot d'arbitrage - Production"
```

---

## Configuration WebSocket

```yaml
websocket:
  enabled: true
  host: "0.0.0.0"
  port: 8001
  path: "/ws"
  
  max_connections: 1000
  max_message_size: 1048576
  ping_interval: 30
  ping_timeout: 10
  max_pong_latency: 20
  
  authentication:
    enabled: true
    type: "jwt"
    header: "Authorization"
    query_param: "token"
  
  channels:
    - "opportunities"
    - "executions"
    - "metrics"
    - "alerts"
    - "status"
    - "performance"
    - "risk"
    - "logs"
    - "system"
  
  compression:
    enabled: true
    algorithm: "permessage-deflate"
    level: 3
  
  monitoring:
    enabled: true
    connection_log: true
    message_log: false
```

---

## Configuration du Monitoring

```yaml
monitoring:
  enabled: true
  
  prometheus:
    enabled: true
    port: 9090
    path: "/metrics"
    namespace: "nexus"
    subsystem: "arbitrage"
    labels:
      environment: "production"
      version: "2.0.0"
      instance: "prod-001"
      cluster: "nexus-prod"
  
  grafana:
    enabled: true
    host: "${GRAFANA_HOST}"
    port: 3000
    dashboard_id: "nexus-arbitrage-prod"
    datasource: "prometheus"
    api_key: "${GRAFANA_API_KEY}"
  
  health_check:
    enabled: true
    interval: 15
    path: "/health"
    timeout: 10
    checks:
      - "database"
      - "cache"
      - "exchanges"
      - "websocket"
      - "api"
      - "disk"
      - "memory"
  
  alerts:
    enabled: true
    rules:
      - name: "high_latency"
        condition: "execution_latency > 1000ms"
        severity: "warning"
        duration: "1m"
        action: "notify"
      
      - name: "critical_latency"
        condition: "execution_latency > 3000ms"
        severity: "critical"
        duration: "30s"
        action: "notify,escalate"
      
      - name: "high_error_rate"
        condition: "error_rate > 0.05"
        severity: "critical"
        duration: "1m"
        action: "notify,escalate"
      
      - name: "high_drawdown"
        condition: "drawdown > 0.10"
        severity: "warning"
        duration: "5m"
        action: "notify,reduce"
      
      - name: "critical_drawdown"
        condition: "drawdown > 0.15"
        severity: "critical"
        duration: "1m"
        action: "notify,stop"
    
    cooldown: 60
```

---

## Configuration du Scheduler

```yaml
scheduler:
  enabled: true
  timezone: "UTC"
  max_workers: 5
  thread_pool: 10
  
  jobs:
    - name: "opportunity_scanner"
      enabled: true
      interval: 1
      timeout: 30
      max_retries: 3
      priority: 1
      description: "Scanne les opportunités d'arbitrage"
    
    - name: "performance_reporter"
      enabled: true
      schedule: "0 */6 * * *"
      timeout: 300
      max_retries: 3
      priority: 2
      description: "Génère les rapports de performance"
    
    - name: "daily_cleanup"
      enabled: true
      schedule: "0 0 * * *"
      timeout: 600
      max_retries: 3
      priority: 3
      description: "Nettoie les données obsolètes"
    
    - name: "health_check"
      enabled: true
      interval: 60
      timeout: 30
      max_retries: 3
      priority: 1
      description: "Vérifie la santé du système"
    
    - name: "backup_rotation"
      enabled: true
      schedule: "0 2 * * *"
      timeout: 1800
      max_retries: 3
      priority: 3
      description: "Rotation des backups"
    
    - name: "risk_recalculation"
      enabled: true
      interval: 300
      timeout: 60
      max_retries: 3
      priority: 2
      description: "Recalcule les métriques de risque"
```

---

## Configuration de la Sécurité

```yaml
security:
  enabled: true
  
  encryption:
    enabled: true
    algorithm: "AES-256-GCM"
    key: "${ENCRYPTION_KEY}"
    salt: "${ENCRYPTION_SALT}"
    key_rotation_days: 90
  
  api_keys:
    encryption: true
    rotation: 90
    min_length: 32
    max_length: 64
  
  ip_whitelist:
    enabled: true
    ips:
      - "10.0.0.0/8"
      - "172.16.0.0/12"
      - "192.168.0.0/16"
  
  rate_limiting:
    enabled: true
    requests_per_minute: 120
    burst_limit: 60
    storage: "redis"
    key_prefix: "rate_limit:security"
  
  ssl:
    enabled: true
    cert: "/etc/ssl/certs/nexus.crt"
    key: "/etc/ssl/private/nexus.key"
    ca: "/etc/ssl/certs/ca-bundle.crt"
    verify: true
  
  audit:
    enabled: true
    log_level: "info"
    retention: 2555
    path: "/var/log/nexus/audit.log"
    encryption: true
```

---

## Configuration de la Conformité

```yaml
compliance:
  enabled: true
  
  regulations:
    - "MIFID_II"
    - "KYC"
    - "AML"
    - "GDPR"
    - "FCA"
  
  reporting:
    enabled: true
    interval: "daily"
    format: "pdf"
    path: "s3://${REPORT_BUCKET}/compliance/"
    encryption: true
    recipients:
      - "compliance@nexustradingia.com"
      - "legal@nexustradingia.com"
  
  audit:
    enabled: true
    log_level: "info"
    retention: 2555
    path: "/var/log/nexus/compliance.log"
    encryption: true
    signing: true
  
  limits:
    max_trade_size: 50000
    max_daily_trades: 100
    max_position_size: 100000
    max_daily_volume: 1000000
    max_leverage: 3
```

---

## Variables d'Environnement

### Variables Requises

```bash
# Configuration Générale
NEXUS_ENV=production
NEXUS_DEBUG=false
NEXUS_CONFIG_PATH=config/arbitrage_config.yaml

# Base de Données
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nexus_arbitrage
DB_USER=postgres
DB_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password

# API
JWT_SECRET=your_jwt_secret
ADMIN_API_KEY=your_admin_key
SERVICE_API_KEY=your_service_key
MONITORING_API_KEY=your_monitoring_key

# Clés API des Exchanges
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret
BYBIT_API_KEY=your_bybit_key
BYBIT_API_SECRET=your_bybit_secret
COINBASE_API_KEY=your_coinbase_key
COINBASE_API_SECRET=your_coinbase_secret

# Notifications
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
SLACK_WEBHOOK_URL=your_slack_webhook
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Monitoring
GRAFANA_API_KEY=your_grafana_key
PAGERDUTY_KEY=your_pagerduty_key

# Stockage
BACKUP_BUCKET=your_backup_bucket
REPORT_BUCKET=your_report_bucket
LOG_BUCKET=your_log_bucket
```

### Variables Optionnelles

```bash
# Performance
NEXUS_MAX_CONCURRENT_OPERATIONS=20
NEXUS_OPERATION_TIMEOUT=30
NEXUS_RETRY_ATTEMPTS=5

# Logging
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_USER=elastic
ELASTICSEARCH_PASSWORD=your_password
LOKI_HOST=localhost
LOKI_PORT=3100

# Monitoring
GRAFANA_HOST=localhost
GRAFANA_PORT=3000

# Sécurité
ENCRYPTION_KEY=your_encryption_key
ENCRYPTION_SALT=your_encryption_salt
```

---

## Exemples de Configuration

### Configuration de Base (Development)

```yaml
bot:
  id: "arbitrage-bot-dev-001"
  name: "NEXUS Arbitrage Bot (Dev)"
  version: "2.0.0-dev"
  environment: "development"

general:
  enabled: true
  debug: true
  log_level: "debug"
  max_concurrent_operations: 5

exchanges:
  binance:
    enabled: true
    api:
      key: "${BINANCE_TESTNET_API_KEY}"
      secret: "${BINANCE_TESTNET_API_SECRET}"
    endpoints:
      rest: "https://testnet.binance.vision/api"

strategies:
  cross_exchange:
    enabled: true
    parameters:
      min_profit_threshold: 0.001
      max_spread_percentage: 0.30

risk_management:
  enabled: true
  max_drawdown: 0.30
  daily_loss_limit: 0.15

execution:
  enabled: true
  mode: "simple"
```

### Configuration de Production

```yaml
bot:
  id: "arbitrage-bot-prod-001"
  name: "NEXUS Arbitrage Bot"
  version: "2.0.0"
  environment: "production"

general:
  enabled: true
  debug: false
  log_level: "info"
  max_concurrent_operations: 20

exchanges:
  binance:
    enabled: true
    api:
      key: "${BINANCE_API_KEY}"
      secret: "${BINANCE_API_SECRET}"
    endpoints:
      rest: "https://api.binance.com"

strategies:
  cross_exchange:
    enabled: true
    parameters:
      min_profit_threshold: 0.005
      max_spread_percentage: 0.15

risk_management:
  enabled: true
  max_drawdown: 0.15
  daily_loss_limit: 0.05

execution:
  enabled: true
  mode: "smart"
```

### Configuration de Staging

```yaml
bot:
  id: "arbitrage-bot-staging-001"
  name: "NEXUS Arbitrage Bot (Staging)"
  version: "2.0.0-staging"
  environment: "staging"

general:
  enabled: true
  debug: true
  log_level: "info"
  max_concurrent_operations: 10

exchanges:
  binance:
    enabled: true
    api:
      key: "${BINANCE_TESTNET_API_KEY}"
      secret: "${BINANCE_TESTNET_API_SECRET}"
    endpoints:
      rest: "https://testnet.binance.vision/api"

strategies:
  cross_exchange:
    enabled: true
    parameters:
      min_profit_threshold: 0.003
      max_spread_percentage: 0.20

risk_management:
  enabled: true
  max_drawdown: 0.20
  daily_loss_limit: 0.10

execution:
  enabled: true
  mode: "smart"
```

### Configuration de Test

```yaml
bot:
  id: "arbitrage-bot-test-001"
  name: "NEXUS Arbitrage Bot (Test)"
  version: "2.0.0-test"
  environment: "testing"

general:
  enabled: true
  debug: true
  log_level: "debug"
  max_concurrent_operations: 3

exchanges:
  mock_exchange:
    enabled: true
    name: "Mock Exchange"
    type: "cex"

strategies:
  cross_exchange:
    enabled: true
    parameters:
      min_profit_threshold: 0.001
      max_spread_percentage: 0.50

risk_management:
  enabled: true
  max_drawdown: 0.30
  daily_loss_limit: 0.15

execution:
  enabled: true
  mode: "simple"
```

---

## 📚 Ressources Additionnelles

- [Guide de Démarrage Rapide](GETTING_STARTED.md)
- [Guide des Stratégies](STRATEGIES.md)
- [Guide de Gestion des Risques](RISK_MANAGEMENT.md)
- [Guide de Déploiement](DEPLOYMENT.md)
- [Guide de Développement](DEVELOPMENT.md)
- [Référence API](API.md)
- [FAQ](FAQ.md)

---

## 📞 Support

Pour toute question ou problème, veuillez contacter:

- **Email**: support@nexustradingia.com
- **Discord**: [Nexus Trading IA](https://discord.gg/nexustradingia)
- **Telegram**: [@NexusTradingIA](https://t.me/NexusTradingIA)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

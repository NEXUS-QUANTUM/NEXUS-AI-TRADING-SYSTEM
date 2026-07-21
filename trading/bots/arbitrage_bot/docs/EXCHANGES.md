```markdown
# NEXUS AI Trading System - Exchanges Guide

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Exchanges Supportés](#exchanges-supportés)
3. [Configuration des Exchanges](#configuration-des-exchanges)
4. [Modes de Trading](#modes-de-trading)
5. [Types d'Ordres](#types-dordres)
6. [Frais et Commissions](#frais-et-commissions)
7. [Limites et Rate Limiting](#limites-et-rate-limiting)
8. [WebSocket Streaming](#websocket-streaming)
9. [Testnet et Sandbox](#testnet-et-sandbox)
10. [Sécurité](#sécurité)
11. [Troubleshooting](#troubleshooting)

---

## Introduction

Le NEXUS AI Trading System supporte une large gamme d'exchanges de cryptomonnaies, incluant les exchanges centralisés (CEX), décentralisés (DEX), et les plateformes de trading forex et actions. Ce guide détaille la configuration et l'utilisation de chaque exchange.

### Architecture d'Intégration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEXUS AI Trading System                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Exchange Manager                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Adapter     │           │   Adapter     │           │   Adapter     │
│   Binance     │           │   Bybit       │           │   Coinbase    │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Exchange API                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Exchanges Supportés

### Exchanges Centralisés (CEX)

| Exchange | Type | Testnet | Documentation | Support |
|----------|------|---------|---------------|---------|
| **Binance** | Spot, Futures, Margin | ✅ | [API Docs](https://binance-docs.github.io/apidocs/) | Premium |
| **Bybit** | Spot, Futures, Options | ✅ | [API Docs](https://bybit-exchange.github.io/docs/) | Premium |
| **Coinbase** | Spot | ✅ | [API Docs](https://docs.cloud.coinbase.com/) | Standard |
| **Kraken** | Spot, Futures | ✅ | [API Docs](https://docs.kraken.com/) | Standard |
| **KuCoin** | Spot, Futures | ✅ | [API Docs](https://docs.kucoin.com/) | Standard |
| **OKX** | Spot, Futures, Options | ✅ | [API Docs](https://www.okx.com/docs/) | Standard |
| **Gate.io** | Spot, Futures | ✅ | [API Docs](https://www.gate.io/docs/) | Standard |
| **Bitget** | Spot, Futures | ✅ | [API Docs](https://www.bitget.com/docs/) | Standard |
| **Deribit** | Futures, Options | ✅ | [API Docs](https://docs.deribit.com/) | Premium |
| **BitMEX** | Futures | ✅ | [API Docs](https://www.bitmex.com/api/) | Standard |
| **Gemini** | Spot | ✅ | [API Docs](https://docs.gemini.com/) | Standard |
| **Bitstamp** | Spot | ✅ | [API Docs](https://www.bitstamp.net/api/) | Standard |

### Exchanges Décentralisés (DEX)

| Exchange | Blockchain | Version | Documentation | Support |
|----------|------------|---------|---------------|---------|
| **Uniswap** | Ethereum, Polygon, Arbitrum | V2, V3 | [Docs](https://docs.uniswap.org/) | Premium |
| **PancakeSwap** | BSC, Ethereum | V2 | [Docs](https://docs.pancakeswap.finance/) | Standard |
| **SushiSwap** | Multi-chaînes | V2 | [Docs](https://docs.sushi.com/) | Standard |
| **Curve** | Ethereum, Polygon | StableSwap | [Docs](https://curve.readthedocs.io/) | Standard |
| **Balancer** | Ethereum, Polygon | V2 | [Docs](https://docs.balancer.fi/) | Standard |
| **1inch** | Multi-chaînes | V5 | [Docs](https://docs.1inch.io/) | Premium |

### Forex

| Exchange | Type | Documentation | Support |
|----------|------|---------------|---------|
| **OANDA** | Spot | [API Docs](https://developer.oanda.com/) | Premium |
| **FXCM** | Spot | [API Docs](https://www.fxcm.com/markets/) | Standard |
| **IG** | Spot | [API Docs](https://www.ig.com/api) | Standard |
| **Pepperstone** | Spot | [API Docs](https://pepperstone.com/api) | Standard |
| **Dukascopy** | Spot | [API Docs](https://www.dukascopy.com/api) | Premium |

### Actions

| Exchange | Type | Documentation | Support |
|----------|------|---------------|---------|
| **Alpaca** | Stocks, ETFs | [API Docs](https://alpaca.markets/docs/) | Premium |
| **TradeStation** | Stocks, Options | [API Docs](https://www.tradestation.com/api/) | Standard |
| **Interactive Brokers** | Stocks, Futures, Forex | [API Docs](https://www.interactivebrokers.com/api/) | Premium |
| **E*TRADE** | Stocks, Options | [API Docs](https://developer.etrade.com/) | Standard |
| **Schwab** | Stocks, Options | [API Docs](https://developer.schwab.com/) | Premium |

---

## Configuration des Exchanges

### Configuration Générale

```yaml
exchanges:
  binance:
    enabled: true
    name: "Binance"
    type: "cex"
    priority: 1
    tier: "premium"
    
    api:
      key: "${BINANCE_API_KEY}"
      secret: "${BINANCE_API_SECRET}"
      passphrase: ""
    
    endpoints:
      rest: "https://api.binance.com"
      websocket: "wss://stream.binance.com:9443/ws"
      futures: "https://fapi.binance.com"
    
    rate_limits:
      requests_per_second: 50
      orders_per_second: 10
      websocket_connections: 10
      websocket_subscriptions: 1024
    
    options:
      use_spot: true
      use_futures: true
      use_margin: false
      use_options: false
    
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
    
    security:
      withdraw_whitelist: true
      ip_whitelist: true
      api_key_permissions:
        - "spot"
        - "futures"
```

### Configuration Testnet

```yaml
exchanges:
  binance:
    enabled: true
    name: "Binance Testnet"
    type: "cex"
    priority: 1
    
    api:
      key: "${BINANCE_TESTNET_API_KEY}"
      secret: "${BINANCE_TESTNET_API_SECRET}"
    
    endpoints:
      rest: "https://testnet.binance.vision/api"
      websocket: "wss://testnet.binance.vision/ws"
      futures: "https://testnet.binance.vision/fapi"
    
    options:
      use_spot: true
      use_futures: true
```

### Configuration DEX

```yaml
exchanges:
  uniswap:
    enabled: true
    name: "Uniswap"
    type: "dex"
    priority: 10
    
    blockchain: "ethereum"
    chains:
      - "ethereum"
      - "polygon"
      - "arbitrum"
    
    api:
      key: "${UNISWAP_API_KEY}"
    
    endpoints:
      rest: "https://api.uniswap.com"
      websocket: "wss://ws.uniswap.com"
    
    options:
      use_v2: true
      use_v3: true
      use_optimism: false
      use_arbitrum: false
      use_polygon: false
    
    trading_pairs:
      - "WETH/USDT"
      - "WBTC/USDT"
      - "USDC/USDT"
    
    fee:
      maker: 0.003
      taker: 0.003
    
    liquidity:
      min_liquidity: 10000
      max_slippage: 0.01
      deadline: 600
    
    gas:
      max_gas_price: 200
      gas_limit: 1000000
      priority_fee: 1
```

---

## Modes de Trading

### Spot Trading

```yaml
exchanges:
  binance:
    options:
      use_spot: true
    
    trading_pairs:
      spot:
        - "BTC/USDT"
        - "ETH/USDT"
        - "BNB/USDT"
```

### Futures Trading

```yaml
exchanges:
  binance:
    options:
      use_futures: true
      use_dual_side_position: true
    
    trading_pairs:
      futures:
        - "BTC/USDT"
        - "ETH/USDT"
        - "BNB/USDT"
    
    fee:
      futures_maker: 0.0002
      futures_taker: 0.0004
```

### Margin Trading

```yaml
exchanges:
  binance:
    options:
      use_margin: true
      use_isolated_margin: true
      use_cross_margin: false
    
    trading_pairs:
      margin:
        - "BTC/USDT"
        - "ETH/USDT"
```

### Options Trading

```yaml
exchanges:
  deribit:
    options:
      use_options: true
    
    trading_pairs:
      options:
        - "BTC-PERPETUAL"
        - "ETH-PERPETUAL"
```

---

## Types d'Ordres

### Ordres Supportés

| Type | Description | Support |
|------|-------------|---------|
| **Market** | Exécution immédiate au prix du marché | ✅ |
| **Limit** | Exécution à un prix spécifique | ✅ |
| **Stop** | Déclenchement à un prix stop | ✅ |
| **Stop Limit** | Stop + Limit combiné | ✅ |
| **Trailing Stop** | Stop suiveur | ✅ |
| **OCO** | One-Cancels-Other | ✅ |
| **Iceberg** | Ordres fractionnés | ✅ |
| **TWAP** | Time-Weighted Average Price | ✅ |
| **Post Only** | Ajout uniquement au carnet | ✅ |
| **Reduce Only** | Réduction de position seulement | ✅ |
| **Close Position** | Fermeture de position | ✅ |

### Exemple d'Ordre Market

```python
order = exchange.create_order(
    symbol='BTC/USDT',
    side='BUY',
    type='MARKET',
    quantity=0.5
)
```

### Exemple d'Ordre Limit

```python
order = exchange.create_order(
    symbol='BTC/USDT',
    side='BUY',
    type='LIMIT',
    quantity=0.5,
    price=45000.0
)
```

### Exemple d'Ordre Stop

```python
order = exchange.create_order(
    symbol='BTC/USDT',
    side='SELL',
    type='STOP',
    quantity=0.5,
    stop_price=44000.0
)
```

### Exemple d'Ordre Trailing Stop

```python
order = exchange.create_order(
    symbol='BTC/USDT',
    side='SELL',
    type='TRAILING_STOP',
    quantity=0.5,
    trailing_stop_offset=0.02  # 2%
)
```

### Exemple d'Ordre OCO

```python
order = exchange.create_order(
    symbol='BTC/USDT',
    side='BUY',
    type='OCO',
    quantity=0.5,
    price=45000.0,
    stop_price=44000.0,
    take_profit=46000.0
)
```

---

## Frais et Commissions

### Frais par Exchange

| Exchange | Maker | Taker | Futures Maker | Futures Taker | Discount |
|----------|-------|-------|---------------|---------------|----------|
| Binance | 0.100% | 0.100% | 0.020% | 0.040% | 25% (BNB) |
| Bybit | 0.100% | 0.100% | 0.020% | 0.055% | - |
| Coinbase | 0.400% | 0.600% | - | - | - |
| Kraken | 0.160% | 0.260% | - | - | - |
| KuCoin | 0.100% | 0.100% | 0.020% | 0.060% | - |
| OKX | 0.100% | 0.100% | 0.020% | 0.050% | - |
| Gate.io | 0.200% | 0.200% | 0.050% | 0.070% | - |
| Uniswap | 0.300% | 0.300% | - | - | - |

### Frais de DEX

| DEX | Frais | Type |
|-----|-------|------|
| Uniswap V2 | 0.30% | LP Fee |
| Uniswap V3 | 0.05-1% | LP Fee |
| PancakeSwap | 0.25% | LP Fee |
| SushiSwap | 0.30% | LP Fee |
| Curve | 0.04% | LP Fee |
| Balancer | 0.05-0.10% | LP Fee |

---

## Limites et Rate Limiting

### Binance

```yaml
rate_limits:
  requests_per_second: 50
  orders_per_second: 10
  websocket_connections: 10
  websocket_subscriptions: 1024
```

### Bybit

```yaml
rate_limits:
  requests_per_second: 30
  orders_per_second: 5
  websocket_connections: 10
  websocket_subscriptions: 500
```

### Coinbase

```yaml
rate_limits:
  requests_per_second: 20
  orders_per_second: 5
  websocket_connections: 5
  websocket_subscriptions: 100
```

### Kraken

```yaml
rate_limits:
  requests_per_second: 15
  orders_per_second: 3
  websocket_connections: 5
  websocket_subscriptions: 100
```

### KuCoin

```yaml
rate_limits:
  requests_per_second: 40
  orders_per_second: 10
  websocket_connections: 10
  websocket_subscriptions: 300
```

### OKX

```yaml
rate_limits:
  requests_per_second: 25
  orders_per_second: 5
  websocket_connections: 10
  websocket_subscriptions: 200
```

---

## WebSocket Streaming

### Endpoints WebSocket

| Exchange | WebSocket URL |
|----------|---------------|
| Binance | `wss://stream.binance.com:9443/ws` |
| Bybit | `wss://stream.bybit.com/v5/public/spot` |
| Coinbase | `wss://ws-feed.pro.coinbase.com` |
| Kraken | `wss://ws.kraken.com` |
| KuCoin | `wss://ws-api.kucoin.com/endpoint` |
| OKX | `wss://ws.okx.com:8443/ws/v5/public` |
| Gate.io | `wss://ws.gate.io/v4` |
| Uniswap | `wss://ws.uniswap.com` |

### Streams Supportés

| Stream | Binance | Bybit | Coinbase | Kraken | KuCoin | OKX |
|--------|---------|-------|----------|--------|--------|-----|
| Depth | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Trade | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kline | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ticker | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Book Ticker | ✅ | ✅ | ✅ | - | - | - |
| Mark Price | ✅ | ✅ | - | - | - | ✅ |
| Agg Trade | ✅ | - | - | - | - | - |

### Exemple de Subscription

```python
# Subscribe to depth stream
websocket.subscribe(
    stream='depth',
    symbol='BTC/USDT',
    callback=on_depth_update
)

# Subscribe to trade stream
websocket.subscribe(
    stream='trade',
    symbol='BTC/USDT',
    callback=on_trade_update
)

# Subscribe to kline stream
websocket.subscribe(
    stream='kline',
    symbol='BTC/USDT',
    interval='1m',
    callback=on_kline_update
)
```

---

## Testnet et Sandbox

### Testnet Binance

```bash
# Environment variables
BINANCE_TESTNET_API_KEY=your_testnet_key
BINANCE_TESTNET_API_SECRET=your_testnet_secret

# Endpoints
REST: https://testnet.binance.vision/api
WebSocket: wss://testnet.binance.vision/ws
Futures: https://testnet.binance.vision/fapi
```

### Testnet Bybit

```bash
# Environment variables
BYBIT_TESTNET_API_KEY=your_testnet_key
BYBIT_TESTNET_API_SECRET=your_testnet_secret

# Endpoints
REST: https://api-testnet.bybit.com
WebSocket: wss://stream-testnet.bybit.com/v5/public/spot
Futures: https://api-testnet.bybit.com/v5
```

### Sandbox Coinbase

```bash
# Environment variables
COINBASE_SANDBOX_API_KEY=your_sandbox_key
COINBASE_SANDBOX_API_SECRET=your_sandbox_secret
COINBASE_SANDBOX_PASSPHRASE=your_sandbox_passphrase

# Endpoints
REST: https://api-public.sandbox.exchange.coinbase.com
WebSocket: wss://ws-feed-public.sandbox.exchange.coinbase.com
```

---

## Sécurité

### Bonnes Pratiques

1. **Utiliser des clés API restreintes**
   - Limiter les permissions
   - Whitelist IP
   - Rotation régulière

2. **Chiffrement**
   - Chiffrer les clés API
   - Utiliser des variables d'environnement
   - Ne pas hardcoder les clés

3. **Monitoring**
   - Surveiller l'activité des clés
   - Détecter les anomalies
   - Alertes en temps réel

### Configuration Sécurisée

```yaml
security:
  api_keys:
    encryption: true
    rotation: 90  # jours
    min_length: 32
    max_length: 64
  
  ip_whitelist:
    enabled: true
    ips:
      - "10.0.0.0/8"
      - "172.16.0.0/12"
      - "192.168.0.0/16"
  
  audit:
    enabled: true
    log_level: "info"
    retention: 2555  # jours
    path: "/var/log/nexus/audit.log"
    encryption: true
```

---

## Troubleshooting

### Problèmes Courants

| Problème | Cause | Solution |
|----------|-------|----------|
| Connexion échouée | Clés API invalides | Vérifier les clés |
| Rate limit | Trop de requêtes | Réduire la fréquence |
| Ordre rejeté | Fond insuffisant | Vérifier le solde |
| WebSocket déconnecté | Timeout | Reconnecter automatiquement |
| Slippage excessif | Volatilité élevée | Ajuster le slippage |

### Debug

```python
# Activer le debug
import logging
logging.basicConfig(level=logging.DEBUG)

# Voir les logs détaillés
exchange.set_debug(True)

# Tester la connexion
exchange.test_connection()

# Obtenir le statut
status = exchange.get_status()
```

### Logs

```bash
# Voir les logs des exchanges
tail -f /var/log/nexus/exchanges.log

# Voir les logs WebSocket
tail -f /var/log/nexus/websocket.log

# Voir les logs d'erreur
tail -f /var/log/nexus/errors.log
```

---

## Support

### Contact

- **Email**: support@nexustradingia.com
- **Discord**: [Nexus Trading IA](https://discord.gg/nexustradingia)
- **Telegram**: [@NexusTradingIA](https://t.me/NexusTradingIA)
- **GitHub**: [NEXUS-QUANTUM](https://github.com/NEXUS-QUANTUM)

### Documentation

- [Guide de Configuration](CONFIGURATION.md)
- [Guide des Stratégies](STRATEGIES.md)
- [Guide de Déploiement](DEPLOYMENT.md)
- [Référence API](API.md)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

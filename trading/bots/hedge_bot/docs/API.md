# NEXUS Hedge Bot API Documentation
Version: 2.0.0
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Configuration API](#configuration-api)
4. [Trading API](#trading-api)
5. [Strategy API](#strategy-api)
6. [Risk Management API](#risk-management-api)
7. [Portfolio API](#portfolio-api)
8. [WebSocket API](#websocket-api)
9. [Error Handling](#error-handling)
10. [Rate Limiting](#rate-limiting)

---

## Overview

The NEXUS Hedge Bot provides a comprehensive REST API and WebSocket API for managing automated hedging strategies, monitoring positions, and controlling risk. All endpoints are designed to be secure, efficient, and easy to integrate.

### Base URL

```
Production:  https://api.nexusquantum.com/v1
Staging:     https://api.staging.nexusquantum.com/v1
Development: http://localhost:8000/v1
```

### API Versioning

All endpoints are versioned with `/v1/` prefix. Breaking changes will be introduced in new API versions.

### Content Type

All requests and responses use JSON format:

```
Content-Type: application/json
Accept: application/json
```

---

## Authentication

### JWT Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

### Obtaining a Token

#### Login

```
POST /auth/login
```

**Request Body:**
```json
{
    "username": "trader@nexusquantum.com",
    "password": "your_password",
    "two_factor_code": "123456"  // Optional
}
```

**Response:**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 3600
}
```

#### Refresh Token

```
POST /auth/refresh
```

**Request Body:**
```json
{
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response:**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600
}
```

#### Logout

```
POST /auth/logout
```

**Response:**
```json
{
    "message": "Logged out successfully"
}
```

---

## Configuration API

### Get Configuration

```
GET /config
```

**Response:**
```json
{
    "bot": {
        "id": "nexus_hedge_bot",
        "name": "NEXUS Hedge Bot",
        "version": "2.0.0",
        "environment": "production",
        "enabled": true,
        "active": true
    },
    "exchange": {
        "name": "binance",
        "type": "spot",
        "sandbox": false,
        "pairs": ["BTC/USDT", "ETH/USDT"]
    },
    "trading": {
        "order": {
            "type": "limit",
            "max_order_size": 10000,
            "min_order_size": 100,
            "slippage_tolerance": 0.001
        },
        "position": {
            "max_positions": 15,
            "max_leverage": 3.0,
            "target_hedge_ratio": 0.50
        }
    },
    "risk_management": {
        "limits": {
            "max_drawdown": 0.15,
            "daily_loss_limit": 0.05,
            "max_leverage": 3.0
        }
    }
}
```

### Update Configuration

```
PATCH /config
```

**Request Body:**
```json
{
    "bot": {
        "environment": "staging"
    },
    "trading": {
        "position": {
            "max_leverage": 2.5
        }
    }
}
```

**Response:**
```json
{
    "message": "Configuration updated successfully",
    "updated_fields": ["bot.environment", "trading.position.max_leverage"]
}
```

### Get Configuration Section

```
GET /config/{section}
```

**Path Parameters:**
- `section`: Configuration section (e.g., `bot`, `exchange`, `trading`, `risk_management`)

**Response:**
```json
{
    "trading": {
        "order": {
            "type": "limit",
            "max_order_size": 10000
        }
    }
}
```

### Reload Configuration

```
POST /config/reload
```

**Response:**
```json
{
    "message": "Configuration reloaded successfully",
    "loaded_files": ["/opt/config/default_config.yaml"],
    "load_time": "2026-07-30T10:30:00Z"
}
```

---

## Trading API

### Get All Positions

```
GET /trading/positions
```

**Query Parameters:**
- `status`: Filter by status (open, closed, all)
- `symbol`: Filter by trading pair
- `limit`: Maximum number of positions to return

**Response:**
```json
{
    "positions": [
        {
            "id": "pos_123456",
            "symbol": "BTC/USDT",
            "side": "long",
            "quantity": 1.0,
            "entry_price": 50000.00,
            "current_price": 52000.00,
            "unrealized_pnl": 2000.00,
            "unrealized_pnl_percent": 4.00,
            "status": "open",
            "created_at": "2026-07-30T09:00:00Z"
        }
    ],
    "total": 5,
    "limit": 100
}
```

### Get Position Details

```
GET /trading/positions/{position_id}
```

**Response:**
```json
{
    "id": "pos_123456",
    "symbol": "BTC/USDT",
    "side": "long",
    "quantity": 1.0,
    "entry_price": 50000.00,
    "current_price": 52000.00,
    "unrealized_pnl": 2000.00,
    "unrealized_pnl_percent": 4.00,
    "realized_pnl": 500.00,
    "total_pnl": 2500.00,
    "status": "open",
    "created_at": "2026-07-30T09:00:00Z",
    "updated_at": "2026-07-30T10:00:00Z",
    "stop_loss": 48500.00,
    "take_profit": 55000.00
}
```

### Get All Orders

```
GET /trading/orders
```

**Query Parameters:**
- `status`: Filter by status (pending, filled, cancelled, rejected)
- `symbol`: Filter by trading pair
- `limit`: Maximum number of orders to return

**Response:**
```json
{
    "orders": [
        {
            "id": "ord_789012",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "quantity": 1.0,
            "price": 50000.00,
            "filled_quantity": 1.0,
            "status": "filled",
            "created_at": "2026-07-30T09:00:00Z",
            "filled_at": "2026-07-30T09:00:05Z"
        }
    ],
    "total": 10,
    "limit": 100
}
```

### Place Order

```
POST /trading/orders
```

**Request Body:**
```json
{
    "symbol": "BTC/USDT",
    "side": "buy",
    "type": "limit",
    "quantity": 1.0,
    "price": 50000.00,
    "time_in_force": "GTC",
    "client_order_id": "my_order_001"
}
```

**Response:**
```json
{
    "id": "ord_789012",
    "symbol": "BTC/USDT",
    "side": "buy",
    "type": "limit",
    "quantity": 1.0,
    "price": 50000.00,
    "status": "pending",
    "created_at": "2026-07-30T10:30:00Z"
}
```

### Cancel Order

```
DELETE /trading/orders/{order_id}
```

**Response:**
```json
{
    "message": "Order cancelled successfully",
    "order_id": "ord_789012"
}
```

### Get Trade History

```
GET /trading/history
```

**Query Parameters:**
- `start_date`: Start date (ISO 8601)
- `end_date`: End date (ISO 8601)
- `symbol`: Filter by trading pair
- `limit`: Maximum number of trades to return

**Response:**
```json
{
    "trades": [
        {
            "id": "trade_456789",
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 1.0,
            "price": 50000.00,
            "fee": 50.00,
            "pnl": 0.00,
            "timestamp": "2026-07-30T09:00:00Z"
        }
    ],
    "total": 50,
    "limit": 100
}
```

---

## Strategy API

### Get Strategy Status

```
GET /strategy/status
```

**Response:**
```json
{
    "name": "delta_hedging",
    "status": "running",
    "environment": "production",
    "is_running": true,
    "metrics": {
        "hedge_ratio": 0.50,
        "effective_hedge": 0.48,
        "volatility": 0.22,
        "correlation": 0.65
    },
    "positions": {
        "total": 5,
        "hedge": 3
    },
    "performance": {
        "daily_pnl": 1500.00,
        "cumulative_pnl": 25000.00,
        "peak_value": 125000.00
    },
    "last_update": "2026-07-30T10:30:00Z"
}
```

### Start Strategy

```
POST /strategy/start
```

**Request Body:**
```json
{
    "strategy_name": "delta_hedging",
    "parameters": {
        "hedge_ratio": 0.50,
        "rebalance_interval": 15
    }
}
```

**Response:**
```json
{
    "message": "Strategy started successfully",
    "strategy_name": "delta_hedging",
    "status": "running"
}
```

### Stop Strategy

```
POST /strategy/stop
```

**Request Body:**
```json
{
    "strategy_name": "delta_hedging",
    "emergency": false
}
```

**Response:**
```json
{
    "message": "Strategy stopped successfully",
    "strategy_name": "delta_hedging",
    "status": "stopped"
}
```

### Get Strategy Parameters

```
GET /strategy/parameters
```

**Response:**
```json
{
    "hedge_ratio": 0.50,
    "hedge_threshold": 0.01,
    "rebalance_interval": 15,
    "max_hedge_position": 0.80,
    "min_hedge_position": 0.20,
    "volatility_lookback": 30,
    "correlation_lookback": 60
}
```

### Update Strategy Parameters

```
PATCH /strategy/parameters
```

**Request Body:**
```json
{
    "hedge_ratio": 0.55,
    "rebalance_interval": 10
}
```

**Response:**
```json
{
    "message": "Strategy parameters updated successfully",
    "updated_parameters": ["hedge_ratio", "rebalance_interval"]
}
```

### Get Strategy Performance

```
GET /strategy/performance
```

**Query Parameters:**
- `period`: Performance period (day, week, month, quarter, year)
- `metric`: Specific metric to retrieve

**Response:**
```json
{
    "period": "month",
    "total_return": 0.08,
    "annualized_return": 0.25,
    "sharpe_ratio": 1.8,
    "sortino_ratio": 2.2,
    "calmar_ratio": 1.5,
    "max_drawdown": 0.12,
    "win_rate": 0.65,
    "profit_factor": 1.8,
    "avg_win": 0.04,
    "avg_loss": 0.02
}
```

---

## Risk Management API

### Get Risk Metrics

```
GET /risk/metrics
```

**Response:**
```json
{
    "var_95": 25000.00,
    "var_99": 40000.00,
    "cvar_95": 35000.00,
    "expected_shortfall": 32000.00,
    "current_drawdown": 0.05,
    "max_drawdown": 0.12,
    "margin_utilization": 0.45,
    "liquidation_risk": 0.15,
    "risk_score": 0.35
}
```

### Get Risk Limits

```
GET /risk/limits
```

**Response:**
```json
{
    "max_drawdown": 0.15,
    "daily_loss_limit": 0.05,
    "weekly_loss_limit": 0.10,
    "monthly_loss_limit": 0.15,
    "max_leverage": 3.0,
    "max_exposure": 1000000.00,
    "max_position_size": 10000.00,
    "max_correlation": 0.70
}
```

### Update Risk Limits

```
PATCH /risk/limits
```

**Request Body:**
```json
{
    "max_drawdown": 0.12,
    "daily_loss_limit": 0.04
}
```

**Response:**
```json
{
    "message": "Risk limits updated successfully",
    "updated_limits": ["max_drawdown", "daily_loss_limit"]
}
```

### Run Stress Test

```
POST /risk/stress-test
```

**Request Body:**
```json
{
    "scenario": "market_crash",
    "parameters": {
        "market_move": -0.25,
        "volatility_multiplier": 3.0
    }
}
```

**Response:**
```json
{
    "scenario": "market_crash",
    "current_value": 100000.00,
    "stressed_value": 75000.00,
    "loss": 25000.00,
    "loss_percentage": 0.25,
    "risk_metrics": {
        "var_95": 35000.00,
        "cvar_95": 40000.00
    }
}
```

---

## Portfolio API

### Get Portfolio Summary

```
GET /portfolio/summary
```

**Response:**
```json
{
    "total_value": 125000.00,
    "available_cash": 25000.00,
    "invested_value": 100000.00,
    "daily_pnl": 1500.00,
    "daily_pnl_percent": 0.012,
    "total_pnl": 25000.00,
    "total_pnl_percent": 0.25,
    "allocation": {
        "cryptocurrency": 0.40,
        "forex": 0.20,
        "equity": 0.30,
        "commodity": 0.10
    },
    "diversification_score": 0.72
}
```

### Get Portfolio Allocation

```
GET /portfolio/allocation
```

**Response:**
```json
{
    "assets": [
        {
            "symbol": "BTC/USDT",
            "value": 50000.00,
            "allocation": 0.40,
            "target_allocation": 0.35,
            "deviation": 0.05
        },
        {
            "symbol": "ETH/USDT",
            "value": 25000.00,
            "allocation": 0.20,
            "target_allocation": 0.25,
            "deviation": -0.05
        }
    ],
    "herfindahl_hirschman_index": 0.18,
    "diversification_score": 0.72
}
```

### Rebalance Portfolio

```
POST /portfolio/rebalance
```

**Request Body:**
```json
{
    "target_allocation": {
        "BTC/USDT": 0.35,
        "ETH/USDT": 0.25,
        "SOL/USDT": 0.15,
        "ADA/USDT": 0.10,
        "DOT/USDT": 0.10,
        "AVAX/USDT": 0.05
    },
    "execute": true
}
```

**Response:**
```json
{
    "message": "Portfolio rebalanced successfully",
    "trades": [
        {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.5,
            "estimated_price": 50000.00
        },
        {
            "symbol": "ETH/USDT",
            "side": "sell",
            "quantity": 1.0,
            "estimated_price": 2500.00
        }
    ],
    "estimated_cost": 500.00
}
```

---

## WebSocket API

### Connection

```
wss://api.nexusquantum.com/ws/v1
```

### Authentication

```
{
    "type": "auth",
    "token": "your_jwt_token"
}
```

### Subscribe to Market Data

```
{
    "type": "subscribe",
    "channel": "market_data",
    "symbols": ["BTC/USDT", "ETH/USDT"],
    "interval": 1000  // milliseconds
}
```

### Subscribe to Position Updates

```
{
    "type": "subscribe",
    "channel": "positions"
}
```

### Subscribe to Trade Updates

```
{
    "type": "subscribe",
    "channel": "trades"
}
```

### Subscribe to Strategy Updates

```
{
    "type": "subscribe",
    "channel": "strategy_updates"
}
```

### WebSocket Message Format

**Market Data:**
```json
{
    "type": "market_data",
    "symbol": "BTC/USDT",
    "bid": 49950.00,
    "ask": 50050.00,
    "last": 50000.00,
    "volume": 1500.00,
    "timestamp": "2026-07-30T10:30:00Z"
}
```

**Position Update:**
```json
{
    "type": "position_update",
    "position": {
        "id": "pos_123456",
        "symbol": "BTC/USDT",
        "side": "long",
        "quantity": 1.0,
        "entry_price": 50000.00,
        "current_price": 52000.00,
        "unrealized_pnl": 2000.00
    }
}
```

**Trade Update:**
```json
{
    "type": "trade_update",
    "trade": {
        "id": "trade_456789",
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 1.0,
        "price": 50000.00,
        "timestamp": "2026-07-30T10:30:00Z"
    }
}
```

### Unsubscribe

```
{
    "type": "unsubscribe",
    "channel": "market_data",
    "symbols": ["BTC/USDT"]
}
```

---

## Error Handling

### Error Response Format

```json
{
    "error": {
        "code": "INVALID_REQUEST",
        "message": "The request is invalid",
        "details": {
            "field": "quantity",
            "reason": "Must be greater than 0"
        },
        "timestamp": "2026-07-30T10:30:00Z",
        "request_id": "req_123456"
    }
}
```

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Error Codes

| Code | Description |
|------|-------------|
| `AUTH_FAILED` | Authentication failed |
| `TOKEN_EXPIRED` | JWT token expired |
| `INVALID_REQUEST` | Invalid request parameters |
| `RESOURCE_NOT_FOUND` | Requested resource not found |
| `RATE_LIMIT_EXCEEDED` | Rate limit exceeded |
| `INSUFFICIENT_BALANCE` | Insufficient balance |
| `POSITION_LIMIT_EXCEEDED` | Position limit exceeded |
| `RISK_LIMIT_EXCEEDED` | Risk limit exceeded |
| `STRATEGY_ERROR` | Strategy execution error |
| `EXCHANGE_ERROR` | Exchange communication error |
| `INTERNAL_ERROR` | Internal server error |

---

## Rate Limiting

### General Rate Limits

| Endpoint Category | Requests per Minute |
|-------------------|-------------------|
| Public endpoints | 60 |
| Authenticated endpoints | 120 |
| Trading endpoints | 60 |
| Strategy endpoints | 30 |
| WebSocket connections | 10 |

### Rate Limit Headers

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 2026-07-30T10:35:00Z
```

### Rate Limit Exceeded Response

```json
{
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Rate limit exceeded. Please try again later.",
        "retry_after": 60,
        "timestamp": "2026-07-30T10:30:00Z"
    }
}
```

---

## Changelog

### Version 2.0.0 (2026-07-30)

- Complete API overhaul
- Added WebSocket support
- Enhanced error handling
- Improved rate limiting
- Added configuration management endpoints
- Added risk management endpoints
- Enhanced strategy control
- Added portfolio rebalancing

### Version 1.0.0 (2026-01-01)

- Initial API release
- Basic trading operations
- Position management
- Strategy execution

---

## Support

For API support, contact:

- Email: support@nexusquantum.com
- Documentation: https://docs.nexusquantum.com
- Status: https://status.nexusquantum.com

---

## License

Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

This API is proprietary and confidential. Unauthorized use, copying, or distribution is prohibited.

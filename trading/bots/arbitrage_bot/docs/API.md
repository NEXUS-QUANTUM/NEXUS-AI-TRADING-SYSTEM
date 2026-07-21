# NEXUS AI TRADING - ARBITRAGE BOT API DOCUMENTATION

**Version:** 3.0.0
**Copyright:** © 2026 NEXUS QUANTUM LTD - All Rights Reserved
**CEO:** Dr X... - Majority Shareholder

---

## 📋 TABLE DES MATIÈRES

1. [Introduction](#introduction)
2. [Authentification](#authentification)
3. [Endpoints API](#endpoints-api)
4. [WebSocket API](#websocket-api)
5. [Modèles de Données](#modeles-de-donnees)
6. [Codes d'Erreur](#codes-derreur)
7. [Rate Limiting](#rate-limiting)
8. [Exemples](#exemples)

---

## INTRODUCTION

L'API du bot d'arbitrage NEXUS permet de gérer, configurer et surveiller les bots d'arbitrage sur plusieurs exchanges. Elle offre des fonctionnalités complètes de trading automatisé, de gestion des risques et d'analyse de performance.

### Base URL

```
https://api.nexustradingia.com/v1/arbitrage
```

### Environnements

| Environnement | URL |
|---------------|-----|
| Production | `https://api.nexustradingia.com/v1/arbitrage` |
| Staging | `https://staging-api.nexustradingia.com/v1/arbitrage` |
| Development | `https://dev-api.nexustradingia.com/v1/arbitrage` |

---

## AUTHENTIFICATION

### API Key Authentication

Toutes les requêtes doivent inclure une clé API dans l'en-tête:

```http
X-API-Key: votre_clé_api
X-API-Signature: signature_hmac_sha256
X-API-Timestamp: 1640995200000
```

### Génération de Signature

```python
import hmac
import hashlib
import time

def generate_signature(api_secret, payload, timestamp):
    message = f"{timestamp}{payload}"
    signature = hmac.new(
        api_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature
```

### JWT Authentication

```http
Authorization: Bearer votre_jwt_token
```

---

## ENDPOINTS API

### 🔹 BOTS

#### Créer un Bot

```http
POST /bots
```

**Body:**

```json
{
    "name": "Arbitrage Bot 1",
    "exchanges": ["BINANCE", "COINBASE"],
    "symbols": ["BTC/USDT", "ETH/USDT"],
    "config": {
        "min_profit_threshold": 0.005,
        "max_position_size": 1000,
        "min_position_size": 100,
        "max_slippage": 0.01,
        "stop_loss": 0.02,
        "take_profit": 0.05
    }
}
```

**Response:**

```json
{
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Arbitrage Bot 1",
    "status": "idle",
    "created_at": "2026-01-15T10:00:00Z",
    "config": { ... }
}
```

#### Récupérer tous les Bots

```http
GET /bots
```

**Query Parameters:**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `status` | string | Filtrer par statut (idle, running, paused, stopped) |
| `exchange` | string | Filtrer par exchange |
| `symbol` | string | Filtrer par symbole |
| `limit` | integer | Nombre de résultats (défaut: 100) |
| `offset` | integer | Décalage (défaut: 0) |

**Response:**

```json
{
    "bots": [
        {
            "bot_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Arbitrage Bot 1",
            "status": "running",
            "performance": {
                "total_pnl": 1250.50,
                "win_rate": 0.68,
                "total_trades": 245
            }
        }
    ],
    "total": 1,
    "limit": 100,
    "offset": 0
}
```

#### Récupérer un Bot

```http
GET /bots/{bot_id}
```

**Response:**

```json
{
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Arbitrage Bot 1",
    "status": "running",
    "config": { ... },
    "state": {
        "current_state": "SCANNING",
        "last_update": "2026-01-15T10:00:00Z"
    },
    "performance": {
        "total_pnl": 1250.50,
        "win_rate": 0.68,
        "total_trades": 245,
        "total_volume": 125000.00,
        "total_fees": 125.50,
        "max_drawdown": 0.08,
        "sharpe_ratio": 1.45
    },
    "positions": [
        {
            "position_id": "660e8400-e29b-41d4-a716-446655440001",
            "symbol": "BTC/USDT",
            "side": "long",
            "entry_price": 50000.00,
            "current_price": 52000.00,
            "unrealized_pnl": 400.00
        }
    ]
}
```

#### Mettre à jour un Bot

```http
PUT /bots/{bot_id}
```

**Body:**

```json
{
    "name": "Arbitrage Bot 1 - Updated",
    "config": {
        "min_profit_threshold": 0.007,
        "max_position_size": 1500
    }
}
```

#### Supprimer un Bot

```http
DELETE /bots/{bot_id}
```

#### Démarrer un Bot

```http
POST /bots/{bot_id}/start
```

**Response:**

```json
{
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "message": "Bot démarré avec succès"
}
```

#### Mettre en Pause un Bot

```http
POST /bots/{bot_id}/pause
```

#### Reprendre un Bot

```http
POST /bots/{bot_id}/resume
```

#### Arrêter un Bot

```http
POST /bots/{bot_id}/stop
```

---

### 🔹 OPPORTUNITÉS

#### Récupérer les Opportunités

```http
GET /opportunities
```

**Query Parameters:**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `bot_id` | string | ID du bot (optionnel) |
| `symbol` | string | Symbole (optionnel) |
| `min_profit` | float | Profit minimum (optionnel) |
| `limit` | integer | Nombre de résultats (défaut: 50) |
| `sort` | string | Tri: `profit`, `timestamp` |

**Response:**

```json
{
    "opportunities": [
        {
            "opportunity_id": "770e8400-e29b-41d4-a716-446655440002",
            "symbol": "BTC/USDT",
            "buy_exchange": "BINANCE",
            "sell_exchange": "COINBASE",
            "buy_price": 50000.00,
            "sell_price": 50250.00,
            "profit": 250.00,
            "profit_percent": 0.005,
            "timestamp": "2026-01-15T10:00:00Z",
            "status": "pending"
        }
    ],
    "total": 1
}
```

---

### 🔹 POSITIONS

#### Récupérer les Positions

```http
GET /positions
```

**Query Parameters:**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `bot_id` | string | ID du bot (optionnel) |
| `status` | string | Statut (open, closed) |
| `symbol` | string | Symbole (optionnel) |
| `limit` | integer | Nombre de résultats (défaut: 50) |

**Response:**

```json
{
    "positions": [
        {
            "position_id": "660e8400-e29b-41d4-a716-446655440001",
            "bot_id": "550e8400-e29b-41d4-a716-446655440000",
            "symbol": "BTC/USDT",
            "side": "long",
            "entry_price": 50000.00,
            "current_price": 52000.00,
            "quantity": 0.1,
            "unrealized_pnl": 200.00,
            "realized_pnl": 0.00,
            "opened_at": "2026-01-15T09:00:00Z",
            "status": "open"
        }
    ],
    "total": 1
}
```

#### Fermer une Position

```http
POST /positions/{position_id}/close
```

**Body:**

```json
{
    "exit_price": 52500.00,
    "quantity": 0.1
}
```

---

### 🔹 ORDRES

#### Récupérer les Ordres

```http
GET /orders
```

**Query Parameters:**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `bot_id` | string | ID du bot (optionnel) |
| `status` | string | Statut (pending, open, filled, cancelled) |
| `symbol` | string | Symbole (optionnel) |
| `limit` | integer | Nombre de résultats (défaut: 50) |

**Response:**

```json
{
    "orders": [
        {
            "order_id": "880e8400-e29b-41d4-a716-446655440003",
            "bot_id": "550e8400-e29b-41d4-a716-446655440000",
            "exchange": "BINANCE",
            "symbol": "BTC/USDT",
            "side": "buy",
            "order_type": "limit",
            "price": 50000.00,
            "quantity": 0.1,
            "status": "filled",
            "filled_at": "2026-01-15T09:01:00Z"
        }
    ]
}
```

---

### 🔹 PERFORMANCE

#### Récupérer les Performances

```http
GET /performance/{bot_id}
```

**Query Parameters:**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `period` | string | Période: `1h`, `24h`, `7d`, `30d`, `90d`, `1y` |

**Response:**

```json
{
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "period": "30d",
    "metrics": {
        "total_pnl": 1250.50,
        "total_trades": 245,
        "win_rate": 0.68,
        "profit_factor": 1.45,
        "total_volume": 125000.00,
        "total_fees": 125.50,
        "max_drawdown": 0.08,
        "sharpe_ratio": 1.45,
        "sortino_ratio": 1.20,
        "calmar_ratio": 0.85
    },
    "by_day": [
        {
            "date": "2026-01-15",
            "pnl": 45.50,
            "trades": 12
        }
    ],
    "by_symbol": [
        {
            "symbol": "BTC/USDT",
            "pnl": 850.00,
            "trades": 120
        }
    ]
}
```

---

### 🔹 CONFIGURATION

#### Récupérer la Configuration

```http
GET /config
```

**Response:**

```json
{
    "risk_limits": {
        "max_position_size": 10000,
        "max_exposure": 0.5,
        "max_drawdown": 0.15,
        "max_daily_loss": 1000
    },
    "exchanges": {
        "BINANCE": {
            "enabled": true,
            "api_url": "https://api.binance.com"
        },
        "COINBASE": {
            "enabled": true,
            "api_url": "https://api.coinbase.com"
        }
    }
}
```

#### Mettre à jour la Configuration

```http
PUT /config
```

---

### 🔹 RISQUE

#### Récupérer l'Évaluation des Risques

```http
GET /risk/{bot_id}
```

**Response:**

```json
{
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "total_risk_score": 35.5,
    "risk_level": "medium",
    "assessments": [
        {
            "risk_type": "market",
            "risk_level": "medium",
            "score": 45.0,
            "probability": 0.4,
            "impact": 0.6,
            "description": "Volatilité élevée détectée"
        }
    ]
}
```

---

## WEBSOCKET API

### Connexion

```javascript
const ws = new WebSocket('wss://api.nexustradingia.com/v1/arbitrage/ws');
```

### Authentification

```javascript
ws.send(JSON.stringify({
    type: 'auth',
    api_key: 'votre_clé_api',
    signature: 'signature_hmac_sha256',
    timestamp: Date.now()
}));
```

### Souscription

```javascript
ws.send(JSON.stringify({
    type: 'subscribe',
    channels: [
        'opportunities',
        'positions',
        'orders',
        'performance'
    ],
    bot_id: '550e8400-e29b-41d4-a716-446655440000'
}));
```

### Messages Reçus

```json
{
    "type": "opportunity",
    "data": {
        "opportunity_id": "770e8400-e29b-41d4-a716-446655440002",
        "symbol": "BTC/USDT",
        "profit_percent": 0.005,
        "timestamp": "2026-01-15T10:00:00Z"
    }
}
```

```json
{
    "type": "position_update",
    "data": {
        "position_id": "660e8400-e29b-41d4-a716-446655440001",
        "unrealized_pnl": 200.00,
        "current_price": 52000.00
    }
}
```

```json
{
    "type": "order_update",
    "data": {
        "order_id": "880e8400-e29b-41d4-a716-446655440003",
        "status": "filled",
        "filled_quantity": 0.1
    }
}
```

```json
{
    "type": "risk_alert",
    "data": {
        "severity": "warning",
        "message": "Drawdown dépassé",
        "metric": "max_drawdown",
        "current_value": 0.12,
        "threshold": 0.10
    }
}
```

---

## MODÈLES DE DONNÉES

### BotConfig

```json
{
    "bot_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "string",
    "exchanges": ["BINANCE", "COINBASE"],
    "symbols": ["BTC/USDT", "ETH/USDT"],
    "min_profit_threshold": 0.005,
    "max_position_size": 1000,
    "min_position_size": 100,
    "max_slippage": 0.01,
    "stop_loss": 0.02,
    "take_profit": 0.05,
    "trailing_stop": 0.01,
    "max_concurrent_trades": 5,
    "timeout_seconds": 30,
    "retry_attempts": 3
}
```

### Performance

```json
{
    "total_pnl": 1250.50,
    "total_trades": 245,
    "win_rate": 0.68,
    "profit_factor": 1.45,
    "total_volume": 125000.00,
    "total_fees": 125.50,
    "max_drawdown": 0.08,
    "sharpe_ratio": 1.45,
    "sortino_ratio": 1.20,
    "calmar_ratio": 0.85,
    "average_trade": 5.10,
    "best_trade": 45.00,
    "worst_trade": -12.50
}
```

### RiskAssessment

```json
{
    "assessment_id": "990e8400-e29b-41d4-a716-446655440004",
    "risk_type": "market",
    "risk_level": "medium",
    "score": 45.0,
    "probability": 0.4,
    "impact": 0.6,
    "severity": 0.5,
    "description": "Volatilité élevée détectée",
    "recommendations": [
        "Réduire l'exposition",
        "Utiliser des stop-loss"
    ],
    "metrics": {
        "volatility": 0.35,
        "drawdown": 0.08
    }
}
```

---

## CODES D'ERREUR

| Code | Description |
|------|-------------|
| 400 | Bad Request - Paramètres invalides |
| 401 | Unauthorized - Authentification requise |
| 403 | Forbidden - Permissions insuffisantes |
| 404 | Not Found - Ressource non trouvée |
| 429 | Too Many Requests - Rate limit dépassé |
| 500 | Internal Server Error - Erreur serveur |
| 503 | Service Unavailable - Service indisponible |

### Détails des Erreurs

```json
{
    "error": {
        "code": 400,
        "message": "Paramètre invalide",
        "details": {
            "field": "min_profit_threshold",
            "reason": "Doit être entre 0.001 et 0.1"
        }
    }
}
```

---

## RATE LIMITING

| Limite | Valeur |
|--------|--------|
| Requêtes par seconde | 10 |
| Requêtes par minute | 100 |
| Requêtes par heure | 1000 |

**Headers:**

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640998800
```

---

## EXEMPLES

### Python

```python
import requests
import hmac
import hashlib
import time

API_KEY = "votre_clé_api"
API_SECRET = "votre_clé_secrète"
BASE_URL = "https://api.nexustradingia.com/v1/arbitrage"

def create_bot(name, exchanges, symbols, config):
    timestamp = str(int(time.time() * 1000))
    payload = json.dumps({
        "name": name,
        "exchanges": exchanges,
        "symbols": symbols,
        "config": config
    })
    
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        f"{timestamp}{payload}".encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "X-API-Key": API_KEY,
        "X-API-Signature": signature,
        "X-API-Timestamp": timestamp,
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/bots",
        headers=headers,
        data=payload
    )
    
    return response.json()

# Exemple d'utilisation
bot = create_bot(
    name="Mon Bot",
    exchanges=["BINANCE", "COINBASE"],
    symbols=["BTC/USDT"],
    config={
        "min_profit_threshold": 0.005,
        "max_position_size": 1000
    }
)

print(f"Bot créé: {bot['bot_id']}")
```

### JavaScript

```javascript
const axios = require('axios');
const crypto = require('crypto');

const API_KEY = 'votre_clé_api';
const API_SECRET = 'votre_clé_secrète';
const BASE_URL = 'https://api.nexustradingia.com/v1/arbitrage';

async function createBot(name, exchanges, symbols, config) {
    const timestamp = Date.now();
    const payload = JSON.stringify({
        name,
        exchanges,
        symbols,
        config
    });
    
    const signature = crypto
        .createHmac('sha256', API_SECRET)
        .update(`${timestamp}${payload}`)
        .digest('hex');
    
    const response = await axios.post(
        `${BASE_URL}/bots`,
        payload,
        {
            headers: {
                'X-API-Key': API_KEY,
                'X-API-Signature': signature,
                'X-API-Timestamp': timestamp,
                'Content-Type': 'application/json'
            }
        }
    );
    
    return response.data;
}

// Exemple d'utilisation
createBot(
    'Mon Bot',
    ['BINANCE', 'COINBASE'],
    ['BTC/USDT'],
    {
        min_profit_threshold: 0.005,
        max_position_size: 1000
    }
).then(bot => {
    console.log(`Bot créé: ${bot.bot_id}`);
});
```

### cURL

```bash
# Création d'un bot
curl -X POST https://api.nexustradingia.com/v1/arbitrage/bots \
  -H "X-API-Key: votre_clé_api" \
  -H "X-API-Signature: votre_signature" \
  -H "X-API-Timestamp: 1640995200000" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mon Bot",
    "exchanges": ["BINANCE", "COINBASE"],
    "symbols": ["BTC/USDT"],
    "config": {
      "min_profit_threshold": 0.005,
      "max_position_size": 1000
    }
  }'

# Démarrer un bot
curl -X POST https://api.nexustradingia.com/v1/arbitrage/bots/{bot_id}/start \
  -H "X-API-Key: votre_clé_api" \
  -H "X-API-Signature: votre_signature" \
  -H "X-API-Timestamp: 1640995200000"

# Récupérer les opportunités
curl -X GET https://api.nexustradingia.com/v1/arbitrage/opportunities?limit=10 \
  -H "X-API-Key: votre_clé_api" \
  -H "X-API-Signature: votre_signature" \
  -H "X-API-Timestamp: 1640995200000"
```

---

## CONTACT & SUPPORT

| Contact | Email |
|---------|-------|
| Support | support@nexustradingia.com |
| Développement | dev@nexustradingia.com |
| Sécurité | security@nexustradingia.com |

---

**© 2026 NEXUS QUANTUM LTD - All Rights Reserved**
**CEO: Dr X... - Majority Shareholder**

---

*Documentation générée le 2026-01-15 - Version 3.0.0*
```

---

## 📊 **RÉSUMÉ DE LA DOCUMENTATION**

| Section | Contenu |
|---------|---------|
| **Authentification** | API Key, JWT, Signature HMAC |
| **Bots** | CRUD, Start, Pause, Resume, Stop |
| **Opportunités** | Récupération, Filtrage, WebSocket |
| **Positions** | Récupération, Fermeture, WebSocket |
| **Ordres** | Récupération, Statut, WebSocket |
| **Performance** | Métriques, Périodes, Analyse |
| **Risque** | Évaluation, Alertes, WebSocket |
| **WebSocket** | Connexion, Souscription, Messages |
| **Rate Limiting** | Limites, Headers, Gestion |

---

**© 2026 NEXUS QUANTUM LTD - All Rights Reserved**
**CEO: Dr X... - Majority Shareholder**

# NEXUS AI Trading System - Getting Started Guide

## 🚀 Introduction

Bienvenue dans le NEXUS AI Trading System ! Ce guide vous aidera à démarrer rapidement avec le système de trading algorithmique avancé. Vous apprendrez à installer, configurer et exécuter le bot d'arbitrage en quelques minutes.

### 📋 Prérequis

Avant de commencer, assurez-vous d'avoir les éléments suivants :

| Composant | Version | Vérification |
|-----------|---------|--------------|
| **Python** | 3.10+ | `python --version` |
| **Docker** | 20.10+ | `docker --version` |
| **Docker Compose** | 2.0+ | `docker-compose --version` |
| **Git** | 2.30+ | `git --version` |
| **Node.js** | 18+ | `node --version` |

### ⚡ Installation Rapide

```bash
# 1. Cloner le repository
git clone https://github.com/NEXUS-QUANTUM/NEXUS-AI-TRADING-SYSTEM.git
cd NEXUS-AI-TRADING-SYSTEM

# 2. Installer les dépendances Python
pip install -r requirements.txt

# 3. Installer les dépendances Node.js (pour le frontend)
npm install --prefix apps/web

# 4. Configurer l'environnement
cp .env.example .env

# 5. Éditer le fichier .env avec vos clés API
nano .env
```

### 🏗️ Structure du Projet

```
NEXUS-AI-TRADING-SYSTEM/
├── trading/                    # Core trading modules
│   └── bots/
│       └── arbitrage_bot/      # Arbitrage bot
│           ├── core/           # Core components
│           ├── strategies/     # Trading strategies
│           ├── exchanges/      # Exchange integrations
│           ├── risk/           # Risk management
│           ├── utils/          # Utilities
│           └── docs/           # Documentation
├── apps/                       # Frontend applications
│   ├── web/                    # Web dashboard
│   ├── mobile/                 # Mobile app
│   └── desktop/                # Desktop app
├── config/                     # Configuration files
├── deployments/                # Deployment files
├── docs/                       # Documentation
└── tests/                      # Test suite
```

---

## 🔧 Configuration de Base

### 1. Configuration du Bot

Créez un fichier de configuration `config/arbitrage_config.yaml` :

```yaml
# Configuration de base du bot
bot:
  id: "arbitrage-bot-001"
  name: "NEXUS Arbitrage Bot"
  version: "2.0.0"
  environment: "development"
  instance: "local-001"

# Paramètres généraux
general:
  enabled: true
  debug: true
  log_level: "debug"
  timezone: "UTC"
  max_concurrent_operations: 5

# Configuration des exchanges
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
    options:
      use_spot: true
      use_futures: false
    trading_pairs:
      spot:
        - "BTC/USDT"
        - "ETH/USDT"
        - "BNB/USDT"

# Configuration des stratégies
strategies:
  cross_exchange:
    enabled: true
    name: "Cross-Exchange Arbitrage (Test)"
    type: "arbitrage"
    priority: 1
    parameters:
      min_profit_threshold: 0.001
      max_spread_percentage: 0.30
      min_volume_threshold: 10
      max_position_size: 1000
    pairs:
      - pair: "BTC/USDT"
        min_profit: 0.001
        max_spread: 0.30
        exchanges:
          - "binance"
          - "bybit"

# Configuration de la gestion des risques
risk_management:
  enabled: true
  max_drawdown: 0.20
  daily_loss_limit: 0.10
  max_positions: 3
  position_sizing:
    strategy: "fixed"
    fixed_size: 100
    max_position_size: 1000

# Configuration de l'exécution
execution:
  enabled: true
  mode: "simple"
  order_types:
    - "market"
    - "limit"
  order_routing:
    enabled: false
    max_slippage: 0.01
  timeout:
    order: 15
    execution: 30

# Configuration de l'API
api:
  enabled: true
  host: "0.0.0.0"
  port: 8000
  prefix: "/api/v1"
  authentication:
    enabled: false
  documentation:
    enabled: true

# Configuration des logs
logging:
  enabled: true
  level: "debug"
  format: "text"
  outputs:
    - type: "console"
      enabled: true
      colorize: true
    - type: "file"
      enabled: true
      path: "/tmp/nexus-arbitrage.log"
      max_size: 1048576
      max_files: 5
```

### 2. Variables d'Environnement

Créez un fichier `.env` :

```bash
# Environnement
NEXUS_ENV=development
NEXUS_DEBUG=true
NEXUS_CONFIG_PATH=config/arbitrage_config.yaml

# Binance Testnet
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_API_SECRET=your_testnet_api_secret

# Bybit Testnet
BYBIT_TESTNET_API_KEY=your_testnet_api_key
BYBIT_TESTNET_API_SECRET=your_testnet_api_secret

# Base de Données (optionnel)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nexus_arbitrage
DB_USER=postgres
DB_PASSWORD=password

# Redis (optionnel)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=password
```

---

## 🚀 Démarrage du Bot

### Méthode 1: En Local (Python)

```bash
# Démarrer le bot
python trading/bots/arbitrage_bot/arbitrage_bot.py --config config/arbitrage_config.yaml

# Avec debug
python trading/bots/arbitrage_bot/arbitrage_bot.py --config config/arbitrage_config.yaml --debug

# Avec environnement spécifique
NEXUS_ENV=production python trading/bots/arbitrage_bot/arbitrage_bot.py
```

### Méthode 2: Avec Docker Compose

```bash
# Démarrer tous les services
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Arrêter les services
docker-compose down
```

### Méthode 3: Avec Kubernetes

```bash
# Déployer sur Kubernetes
kubectl apply -k deployments/kubernetes/

# Voir les pods
kubectl get pods -n nexus

# Voir les logs
kubectl logs -f deployment/nexus-backend -n nexus
```

---

## 📊 Vérification du Fonctionnement

### 1. Health Check

```bash
# Vérifier que le bot est en vie
curl http://localhost:8000/health

# Réponse attendue
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2026-01-01T00:00:00Z",
  "uptime": 123.45
}
```

### 2. Statut du Bot

```bash
# Récupérer le statut
curl http://localhost:8000/api/v1/bot/status

# Réponse attendue
{
  "instance": "arbitrage-bot-001",
  "running": true,
  "initialized": true,
  "start_time": "2026-01-01T00:00:00Z",
  "uptime": 123.45,
  "env": "development",
  "version": "2.0.0"
}
```

### 3. Métriques

```bash
# Récupérer les métriques
curl http://localhost:8000/api/v1/metrics

# Réponse attendue
{
  "timestamp": "2026-01-01T00:00:00Z",
  "metrics": {
    "trades": {"total": 0, "successful": 0, "failed": 0},
    "pnl": {"total": 0, "today": 0},
    "opportunities": {"total": 0, "executed": 0},
    "system": {"cpu": 15.2, "memory": 256.5}
  }
}
```

### 4. Tableau de Bord

Accédez au tableau de bord web :

```bash
# Ouvrir dans le navigateur
open http://localhost:8500

# Ou utiliser l'API
curl http://localhost:8500/api/status
```

---

## 🎯 Premier Trade

### Via API REST

```bash
# Créer un trade test
curl -X POST http://localhost:8000/api/v1/trades \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "side": "BUY",
    "quantity": 0.001,
    "order_type": "MARKET"
  }'

# Réponse attendue
{
  "id": "trade_001",
  "symbol": "BTC/USDT",
  "side": "BUY",
  "quantity": 0.001,
  "price": 45000.0,
  "status": "FILLED",
  "timestamp": "2026-01-01T00:00:00Z"
}
```

### Via WebSocket

```javascript
// Se connecter au WebSocket
const ws = new WebSocket('ws://localhost:8001/ws');

// S'abonner aux trades
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'trades'
  }));
};

// Écouter les trades
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Trade:', data);
};
```

---

## 🐛 Dépannage Rapide

### Problèmes Courants

| Problème | Solution |
|----------|----------|
| **Le bot ne démarre pas** | Vérifier les logs : `tail -f logs/arbitrage.log` |
| **Connexion API échouée** | Vérifier les clés API dans `.env` |
| **Rate limiting** | Réduire `max_concurrent_operations` |
| **Base de données** | Vérifier `DB_HOST` et `DB_PASSWORD` |
| **Redis** | Vérifier `REDIS_HOST` et `REDIS_PASSWORD` |
| **Port déjà utilisé** | Changer `api.port` dans la configuration |

### Logs Utiles

```bash
# Voir les logs du bot
tail -f /tmp/nexus-arbitrage.log

# Voir les logs des exchanges
tail -f logs/exchanges.log

# Voir les logs des stratégies
tail -f logs/strategies.log

# Voir les logs du système
tail -f logs/system.log
```

---

## 📚 Prochaines Étapes

### 1. Configuration Avancée

- [Configuration des Exchanges](EXCHANGES.md)
- [Configuration des Stratégies](STRATEGIES.md)
- [Configuration des Risques](RISK_MANAGEMENT.md)

### 2. Développement

- [Créer une Stratégie Personnalisée](DEVELOPMENT.md)
- [Ajouter un Nouvel Exchange](DEVELOPMENT.md)
- [API Reference](API.md)

### 3. Déploiement

- [Déploiement sur AWS](DEPLOYMENT.md)
- [Déploiement sur Azure](DEPLOYMENT.md)
- [Déploiement sur GCP](DEPLOYMENT.md)
- [Déploiement sur Kubernetes](DEPLOYMENT.md)

### 4. Optimisation

- [Optimisation des Stratégies](STRATEGIES.md#optimization)
- [Optimisation des Performances](TROUBLESHOOTING.md#performance)

---

## 🔒 Bonnes Pratiques

### Sécurité

1. **JAMAIS** partager vos clés API
2. **TOUJOURS** utiliser des variables d'environnement
3. **TOUJOURS** tester sur testnet avant production
4. **TOUJOURS** sauvegarder les configurations
5. **TOUJOURS** monitorer les logs

### Performance

1. **TOUJOURS** utiliser des connexions persistantes
2. **TOUJOURS** mettre en cache les données fréquentes
3. **TOUJOURS** utiliser des batch requests
4. **TOUJOURS** optimiser les requêtes

### Monitoring

1. **TOUJOURS** monitorer les métriques
2. **TOUJOURS** configurer des alertes
3. **TOUJOURS** loguer les erreurs
4. **TOUJOURS** faire des health checks

---

## 📞 Support

### Contact

| Type | Contact |
|------|---------|
| **Support Client** | support@nexustradingia.com |
| **Support Technique** | dev@nexustradingia.com |
| **Urgence** | emergency@nexustradingia.com |

### Canaux

| Plateforme | Handle | URL |
|------------|--------|-----|
| **Discord** | `Nexus Trading IA` | discord.gg/nexustradingia |
| **Telegram** | `@NexusTradingIA` | t.me/NexusTradingIA |
| **GitHub** | `@NEXUS-QUANTUM` | github.com/NEXUS-QUANTUM |

---

## 📖 Ressources

### Documentation

- [Guide de Configuration](CONFIGURATION.md)
- [Guide des Stratégies](STRATEGIES.md)
- [Guide des Risques](RISK_MANAGEMENT.md)
- [Guide des Exchanges](EXCHANGES.md)
- [Guide de Déploiement](DEPLOYMENT.md)
- [Guide de Dépannage](TROUBLESHOOTING.md)

### Vidéos

- [Tutoriel d'Installation](https://youtube.com/@NexusQuantum)
- [Démo du Bot](https://youtube.com/@NexusQuantum)
- [Explication des Stratégies](https://youtube.com/@NexusQuantum)

---

## ✅ Checklist de Démarrage

- [ ] Cloner le repository
- [ ] Installer les dépendances
- [ ] Configurer `.env`
- [ ] Configurer `arbitrage_config.yaml`
- [ ] Tester la connexion aux exchanges
- [ ] Démarrer le bot en mode test
- [ ] Vérifier les logs
- [ ] Tester un trade
- [ ] Monitorer les métriques
- [ ] Configurer les alertes
- [ ] Démarrer en production

---

## 🎉 Félicitations !

Vous avez réussi à installer et démarrer le NEXUS AI Trading System. Le système est maintenant prêt à être configuré pour vos besoins spécifiques.

### Prochaines Actions

1. ✅ **Configurer les exchanges** - [Guide des Exchanges](EXCHANGES.md)
2. ✅ **Configurer les stratégies** - [Guide des Stratégies](STRATEGIES.md)
3. ✅ **Configurer les risques** - [Guide des Risques](RISK_MANAGEMENT.md)
4. ✅ **Optimiser les performances** - [Guide de Performance](TROUBLESHOOTING.md)
5. ✅ **Déployer en production** - [Guide de Déploiement](DEPLOYMENT.md)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

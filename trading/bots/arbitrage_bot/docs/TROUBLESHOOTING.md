# NEXUS AI Trading System - Troubleshooting Guide

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Problèmes Courants](#problèmes-courants)
3. [Erreurs et Solutions](#erreurs-et-solutions)
4. [Logs et Debug](#logs-et-debug)
5. [Performance](#performance)
6. [Connectivité](#connectivité)
7. [Exchanges](#exchanges)
8. [Stratégies](#stratégies)
9. [Exécution](#exécution)
10. [Base de Données](#base-de-données)
11. [Cache](#cache)
12. [Monitoring](#monitoring)
13. [Sécurité](#sécurité)
14. [Déploiement](#déploiement)
15. [FAQ](#faq)

---

## Introduction

Ce guide de dépannage vous aidera à résoudre les problèmes courants rencontrés lors de l'utilisation du NEXUS AI Trading System. Nous couvrons les erreurs, les solutions, les outils de debug et les meilleures pratiques.

### Niveaux de Dépannage

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Troubleshooting Levels                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Basic       │           │   Advanced    │           │   Expert      │
│   User        │           │   Developer   │           │   Admin       │
└───────────────┘           └───────────────┘           └───────────────┘
```

---

## Problèmes Courants

### 1. Le bot ne démarre pas

**Symptômes:**
- Le bot ne répond pas
- Message d'erreur au démarrage
- Processus se termine immédiatement

**Solutions:**

```bash
# 1. Vérifier les prérequis
python --version  # Python 3.10+
docker --version
docker-compose --version

# 2. Vérifier la configuration
python -c "import yaml; yaml.safe_load(open('config/arbitrage_config.yaml'))"

# 3. Vérifier les variables d'environnement
env | grep NEXUS
env | grep API_KEY

# 4. Vérifier les logs
tail -f /var/log/nexus/arbitrage.log
```

### 2. Problèmes de connexion aux exchanges

**Symptômes:**
- Erreur de connexion API
- Timeouts
- Rate limiting

**Solutions:**

```bash
# 1. Vérifier les clés API
curl -X GET "https://api.binance.com/api/v3/ping"
curl -X GET "https://api.binance.com/api/v3/account" -H "X-MBX-APIKEY: $BINANCE_API_KEY"

# 2. Vérifier le rate limiting
# Réduire la fréquence des requêtes
grep -r "requests_per_second" config/

# 3. Vérifier les endpoints
curl -I https://api.binance.com
curl -I https://api.bybit.com
```

### 3. Erreurs de trading

**Symptômes:**
- Ordres rejetés
- Slippage excessif
- Positions non exécutées

**Solutions:**

```python
# 1. Vérifier les balances
balance = exchange.get_balance()
print(balance)

# 2. Vérifier les limites
limits = exchange.get_limits('BTC/USDT')
print(limits)

# 3. Vérifier le statut du marché
market_status = exchange.get_market_status('BTC/USDT')
print(market_status)
```

---

## Erreurs et Solutions

### Erreurs Générales

| Code | Erreur | Cause | Solution |
|------|--------|-------|----------|
| 1000 | Configuration invalide | Fichier YAML mal formé | Vérifier la syntaxe YAML |
| 1001 | Clé API manquante | Variable d'environnement non définie | Définir la variable d'environnement |
| 1002 | Connexion échouée | Problème réseau | Vérifier la connectivité |
| 1003 | Timeout | Latence réseau | Augmenter le timeout |
| 1004 | Memory Error | Mémoire insuffisante | Augmenter la mémoire |

### Erreurs de Trading

| Code | Erreur | Cause | Solution |
|------|--------|-------|----------|
| 2000 | Balance insuffisante | Fonds insuffisants | Déposer des fonds |
| 2001 | Ordre rejeté | Paramètres invalides | Vérifier les paramètres |
| 2002 | Slippage excessif | Volatilité élevée | Augmenter la tolérance |
| 2003 | Position fermée | Stop loss déclenché | Ajuster le stop loss |
| 2004 | Ordre expiré | Temps écoulé | Réduire le temps d'expiration |

### Erreurs de Système

| Code | Erreur | Cause | Solution |
|------|--------|-------|----------|
| 3000 | Base de données | Connexion perdue | Redémarrer le service |
| 3001 | Cache | Redis hors ligne | Redémarrer Redis |
| 3002 | File d'attente | Queue pleine | Augmenter la taille |
| 3003 | WebSocket | Déconnexion | Reconnecter |
| 3004 | API | Service indisponible | Vérifier l'état |

---

## Logs et Debug

### Activer les Logs

```python
# Python
import logging
logging.basicConfig(level=logging.DEBUG)

# YAML
logging:
  level: "debug"
  format: "json"
  outputs:
    - type: "console"
      enabled: true
    - type: "file"
      enabled: true
      path: "/var/log/nexus/arbitrage.log"
```

### Analyse des Logs

```bash
# Voir les logs en temps réel
tail -f /var/log/nexus/arbitrage.log

# Filtrer par niveau
grep "ERROR" /var/log/nexus/arbitrage.log
grep "WARNING" /var/log/nexus/arbitrage.log

# Filtrer par composant
grep "exchange_manager" /var/log/nexus/arbitrage.log
grep "strategy_manager" /var/log/nexus/arbitrage.log

# Analyser les logs JSON
cat /var/log/nexus/arbitrage.log | jq 'select(.level=="ERROR")'
```

### Debugging Avancé

```python
# Activer le debug des composants
import sys
sys.path.append('/path/to/project')

import trading.bots.arbitrage_bot as bot
bot.set_debug(True)

# Profiler le code
import cProfile
cProfile.run('bot.run()')

# Tracer l'exécution
import trace
tracer = trace.Trace(
    ignoredirs=[sys.prefix, sys.exec_prefix],
    trace=0,
    count=1
)
tracer.run('bot.run()')
```

---

## Performance

### Problèmes de Performance

| Problème | Symptômes | Solutions |
|----------|-----------|-----------|
| CPU élevé | Processeur > 80% | Réduire les threads, optimiser le code |
| Mémoire élevée | RAM > 80% | Augmenter la mémoire, vider le cache |
| Latence élevée | Réponse > 100ms | Optimiser les requêtes, augmenter les ressources |
| Throughput faible | < 100 ops/sec | Paralléliser, augmenter les workers |

### Optimisation

```yaml
# Configuration de performance
performance:
  # Threads
  max_workers: 10
  thread_pool_size: 20
  
  # Cache
  cache:
    enabled: true
    max_size: 10000
    ttl: 300
  
  # Batch
  batch:
    enabled: true
    size: 100
    timeout: 5
  
  # Connection Pool
  connection_pool:
    max_connections: 50
    min_connections: 10
    timeout: 30
```

### Monitoring des Performances

```bash
# CPU et mémoire
top -u nexus
htop
ps aux | grep python

# I/O
iotop
iostat -x 1

# Réseau
iftop
nethogs
ss -tulpn

# Profiling
python -m cProfile -o profile.out script.py
python -m pstats profile.out
```

---

## Connectivité

### Problèmes Réseau

| Problème | Cause | Solution |
|----------|-------|----------|
| DNS | Résolution échouée | Vérifier /etc/resolv.conf |
| Proxy | Proxy bloqué | Configurer le proxy |
| Firewall | Ports bloqués | Ouvrir les ports |
| SSL | Certificat invalide | Vérifier les certificats |

### Tester la Connectivité

```bash
# Ping
ping -c 4 api.binance.com
ping -c 4 api.bybit.com

# Traceroute
traceroute api.binance.com

# Ports
nc -zv api.binance.com 443
nc -zv api.bybit.com 443

# SSL
openssl s_client -connect api.binance.com:443
```

### Configuration Réseau

```yaml
network:
  # DNS
  dns_servers:
    - "8.8.8.8"
    - "1.1.1.1"
  
  # Proxy
  proxy:
    enabled: false
    http: "http://proxy:8080"
    https: "https://proxy:8080"
  
  # Timeouts
  timeout:
    connection: 10
    read: 30
    write: 30
  
  # Retry
  retry:
    attempts: 3
    delay: 5
    backoff: 2.0
```

---

## Exchanges

### Problèmes par Exchange

#### Binance

| Problème | Cause | Solution |
|----------|-------|----------|
| 418 | IP bloquée | Attendre ou changer IP |
| 429 | Rate limit | Réduire les requêtes |
| -1000 | Erreur interne | Réessayer plus tard |
| -1021 | Timestamp | Synchroniser l'horloge |

```bash
# Synchroniser l'horloge
sudo ntpdate -u pool.ntp.org
sudo timedatectl set-timezone UTC
```

#### Bybit

| Problème | Cause | Solution |
|----------|-------|----------|
| 10001 | Erreur de signature | Vérifier la clé API |
| 10002 | Rate limit | Réduire les requêtes |
| 10003 | Paramètres invalides | Vérifier les paramètres |

#### Coinbase

| Problème | Cause | Solution |
|----------|-------|----------|
| 401 | Clé invalide | Vérifier la clé API |
| 403 | IP non whitelistée | Ajouter l'IP |
| 429 | Rate limit | Réduire les requêtes |

---

## Stratégies

### Problèmes de Stratégies

| Problème | Cause | Solution |
|----------|-------|----------|
| Pas d'opportunités | Seuils trop stricts | Ajuster les paramètres |
| Trop d'opportunités | Seuils trop lâches | Augmenter les seuils |
| Performance faible | Paramètres sous-optimaux | Optimiser les paramètres |
| Erreurs d'exécution | Problèmes de trading | Vérifier les ordres |

### Optimisation des Stratégies

```python
from trading.bots.arbitrage_bot.optimization import StrategyOptimizer

# Optimiser les paramètres
optimizer = StrategyOptimizer(
    strategy_type='cross_exchange',
    objective='sharpe_ratio',
    iterations=500
)

# Définir la plage
optimizer.add_parameter('min_profit', [0.001, 0.005, 0.01, 0.02])
optimizer.add_parameter('max_spread', [0.10, 0.15, 0.20, 0.25])

# Exécuter
best_params, best_score = optimizer.optimize()
print(f"Best: {best_params}")
```

---

## Exécution

### Problèmes d'Ordres

| Problème | Cause | Solution |
|----------|-------|----------|
| Ordre non exécuté | Manque de liquidité | Changer d'ordre |
| Ordre partiel | Liquidité partielle | Accepter le partiel |
| Ordre annulé | Timeout | Réessayer |
| Slippage élevé | Volatilité | Augmenter la tolérance |

### Vérification des Ordres

```python
# Vérifier le statut
order = execution_engine.get_order(order_id)
print(order['status'])
print(order['filled_quantity'])

# Annuler l'ordre
execution_engine.cancel_order(order_id)

# Modifier l'ordre
execution_engine.modify_order(order_id, price=new_price, quantity=new_qty)
```

---

## Base de Données

### Problèmes de Base de Données

| Problème | Cause | Solution |
|----------|-------|----------|
| Connexion échouée | Paramètres invalides | Vérifier la configuration |
| Query lente | Index manquant | Ajouter des indexes |
| Corruption | Panne | Restaurer la sauvegarde |
| Espace insuffisant | Disque plein | Nettoyer ou agrandir |

### Maintenance

```sql
-- Vérifier la connexion
SELECT 1;

-- Vérifier les sessions
SELECT pid, usename, application_name, client_addr, state 
FROM pg_stat_activity;

-- Vérifier les index
SELECT schemaname, tablename, indexname, indexdef 
FROM pg_indexes 
WHERE schemaname = 'public';

-- Vérifier la taille
SELECT pg_database_size('nexus_arbitrage') / 1024 / 1024 / 1024 AS size_gb;

-- VACUUM
VACUUM ANALYZE;
```

---

## Cache

### Problèmes de Cache

| Problème | Cause | Solution |
|----------|-------|----------|
| Cache miss | TTL trop court | Augmenter le TTL |
| Cache full | Capacité insuffisante | Augmenter la taille |
| Connexion échouée | Redis hors ligne | Redémarrer Redis |
| Performance lente | Latence réseau | Optimiser le réseau |

### Redis Commands

```bash
# Voir les stats
redis-cli INFO stats

# Voir la mémoire
redis-cli INFO memory

# Voir les clés
redis-cli KEYS "nexus:*"

# Vider le cache
redis-cli FLUSHDB

# Monitorer
redis-cli MONITOR
```

---

## Monitoring

### Problèmes de Monitoring

| Problème | Cause | Solution |
|----------|-------|----------|
| Pas de métriques | Collecteur arrêté | Redémarrer |
| Alertes fausses | Seuils trop stricts | Ajuster les seuils |
| Dashboard vide | Données manquantes | Vérifier la collecte |
| Performance impact | Collecte trop fréquente | Réduire la fréquence |

### Vérification du Monitoring

```bash
# Vérifier Prometheus
curl http://localhost:9090/api/v1/query?query=up

# Vérifier Grafana
curl http://localhost:3000/api/health

# Vérifier les métriques
curl http://localhost:8000/metrics
```

---

## Sécurité

### Problèmes de Sécurité

| Problème | Cause | Solution |
|----------|-------|----------|
| Clé API compromise | Fuite | Révoquer et régénérer |
| Accès non autorisé | Permissions | Réviser les rôles |
| Injection SQL | Entrées non validées | Valider les entrées |
| XSS | Échappement insuffisant | Échapper les sorties |

### Sécurisation

```python
# Valider les entrées
from trading.bots.arbitrage_bot.utils import validate_input

def secure_endpoint(request):
    # Valider les entrées
    validated = validate_input(request)
    
    # Utiliser des paramètres
    result = process(validated)
    
    # Loguer l'accès
    audit.log('access', validated)
    
    return result
```

---

## Déploiement

### Problèmes de Déploiement

| Problème | Cause | Solution |
|----------|-------|----------|
| Build échoué | Dépendances manquantes | Installer les dépendances |
| Container crash | Configuration invalide | Vérifier la configuration |
| Service indisponible | Port utilisé | Changer de port |
| Rollback | Déploiement instable | Revenir à la version précédente |

### Commandes de Déploiement

```bash
# Docker
docker-compose up -d
docker-compose logs -f
docker-compose down

# Kubernetes
kubectl apply -f deployments/
kubectl get pods -n nexus
kubectl logs -f deployment/nexus-backend -n nexus
kubectl rollout undo deployment/nexus-backend -n nexus

# Rollback
kubectl rollout history deployment/nexus-backend -n nexus
kubectl rollout undo deployment/nexus-backend --to-revision=2 -n nexus
```

---

## FAQ

### Général

**Q: Le bot ne démarre pas, que faire?**
R: Vérifier les logs, la configuration, et les variables d'environnement.

**Q: Comment augmenter la performance?**
R: Optimiser la configuration, augmenter les ressources, paralléliser.

**Q: Comment sauvegarder le système?**
R: Utiliser les scripts de backup, configurer les backups automatiques.

### Trading

**Q: Pourquoi mes ordres sont rejetés?**
R: Vérifier les balances, les limites, et les paramètres des ordres.

**Q: Comment réduire le slippage?**
R: Utiliser des ordres limit, réduire la taille des ordres.

**Q: Pourquoi les stratégies ne trouvent pas d'opportunités?**
R: Ajuster les seuils, vérifier la connectivité, et la liquidité.

### Technique

**Q: Comment activer le debug?**
R: Définir NEXUS_DEBUG=true ou configurer le niveau de log.

**Q: Comment monitorer le système?**
R: Utiliser Prometheus et Grafana pour le monitoring.

**Q: Comment gérer les mises à jour?**
R: Utiliser le système de versioning et les scripts de migration.

---

## 📚 Ressources Additionnelles

- [Guide de Configuration](CONFIGURATION.md)
- [Guide de Déploiement](DEPLOYMENT.md)
- [Guide de Monitoring](MONITORING.md)
- [Guide de Sécurité](SECURITY.md)
- [Référence API](API.md)

---

## 📞 Support

Pour toute question ou problème, veuillez contacter:

- **Email**: support@nexustradingia.com
- **Discord**: [Nexus Trading IA](https://discord.gg/nexustradingia)
- **Telegram**: [@NexusTradingIA](https://t.me/NexusTradingIA)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

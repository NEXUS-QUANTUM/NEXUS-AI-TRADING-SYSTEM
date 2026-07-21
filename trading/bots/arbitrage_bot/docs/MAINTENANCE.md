# NEXUS AI Trading System - Maintenance Guide

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Maintenance Préventive](#maintenance-préventive)
3. [Maintenance Corrective](#maintenance-corrective)
4. [Maintenance de la Base de Données](#maintenance-de-la-base-de-données)
5. [Maintenance du Cache](#maintenance-du-cache)
6. [Maintenance des Logs](#maintenance-des-logs)
7. [Maintenance des Modèles AI](#maintenance-des-modèles-ai)
8. [Maintenance du Système](#maintenance-du-système)
9. [Mises à Jour](#mises-à-jour)
10. [Monitoring de Maintenance](#monitoring-de-maintenance)
11. [Checklists de Maintenance](#checklists-de-maintenance)
12. [Procédures d'Urgence](#procédures-durgence)
13. [Outils de Maintenance](#outils-de-maintenance)
14. [Exemples](#exemples)

---

## Introduction

La maintenance régulière du NEXUS AI Trading System est essentielle pour garantir sa fiabilité, ses performances et sa sécurité. Ce guide détaille toutes les procédures de maintenance, les checklists, et les bonnes pratiques.

### Cycle de Maintenance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Maintenance Cycle                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Daily       │           │   Weekly      │           │   Monthly     │
│   Checks      │           │   Maintenance │           │   Maintenance │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Quarterly/Annual Maintenance                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Maintenance Préventive

### Daily Checks

```yaml
daily_maintenance:
  # 1. Système
  system:
    - check: "CPU usage"
      threshold: 80
      action: "alert"
    
    - check: "Memory usage"
      threshold: 80
      action: "alert"
    
    - check: "Disk usage"
      threshold: 80
      action: "alert"
  
  # 2. Application
  application:
    - check: "Service status"
      command: "systemctl status nexus"
      expected: "running"
    
    - check: "Health check"
      endpoint: "/health"
      expected: "healthy"
    
    - check: "Database connection"
      command: "psql -h localhost -U nexus -c 'SELECT 1'"
      expected: "1"
  
  # 3. Trading
  trading:
    - check: "Exchange connections"
      command: "python check_exchanges.py"
      expected: "all_connected"
    
    - check: "Strategy status"
      command: "python check_strategies.py"
      expected: "all_active"
    
    - check: "Position limits"
      threshold: 80
      action: "alert"
```

### Weekly Maintenance

```yaml
weekly_maintenance:
  # 1. Base de Données
  database:
    - task: "Vacuum analyze"
      command: "psql -d nexus -c 'VACUUM ANALYZE'"
      schedule: "Sunday 02:00"
    
    - task: "Index maintenance"
      command: "psql -d nexus -c 'REINDEX DATABASE nexus'"
      schedule: "Sunday 03:00"
    
    - task: "Backup verification"
      command: "python verify_backup.py"
      schedule: "Sunday 04:00"
  
  # 2. Logs
  logs:
    - task: "Log rotation"
      command: "logrotate /etc/logrotate.d/nexus"
      schedule: "Sunday 01:00"
    
    - task: "Log analysis"
      command: "python analyze_logs.py"
      schedule: "Sunday 05:00"
  
  # 3. Cache
  cache:
    - task: "Cache cleanup"
      command: "redis-cli FLUSHDB"
      schedule: "Sunday 06:00"
    
    - task: "Cache optimization"
      command: "redis-cli CONFIG SET maxmemory 2gb"
      schedule: "Sunday 06:30"
```

### Monthly Maintenance

```yaml
monthly_maintenance:
  # 1. Performance
  performance:
    - task: "Performance review"
      report: "monthly_performance_report"
      schedule: "1st Monday 09:00"
    
    - task: "Metric analysis"
      report: "monthly_metric_analysis"
      schedule: "1st Tuesday 09:00"
  
  # 2. Sécurité
  security:
    - task: "Security audit"
      report: "monthly_security_audit"
      schedule: "1st Wednesday 10:00"
    
    - task: "Key rotation"
      command: "python rotate_keys.py"
      schedule: "1st Thursday 09:00"
  
  # 3. Modèles
  models:
    - task: "Model evaluation"
      command: "python evaluate_models.py"
      schedule: "1st Friday 09:00"
    
    - task: "Model retraining"
      command: "python retrain_models.py"
      schedule: "1st Saturday 10:00"
```

### Quarterly Maintenance

```yaml
quarterly_maintenance:
  # 1. Infrastructure
  infrastructure:
    - task: "Infrastructure review"
      schedule: "Quarterly 1st week"
    
    - task: "Capacity planning"
      schedule: "Quarterly 2nd week"
    
    - task: "DR drill"
      schedule: "Quarterly 3rd week"
  
  # 2. Mises à jour
  updates:
    - task: "System updates"
      schedule: "Quarterly 4th week"
    
    - task: "Security patches"
      schedule: "Quarterly 4th week"
    
    - task: "Version upgrades"
      schedule: "Quarterly 4th week"
```

---

## Maintenance Corrective

### Problèmes Courants

| Problème | Symptômes | Action Corrective |
|----------|-----------|-------------------|
| **Service down** | Service inactif | Redémarrer le service |
| **Mémoire élevée** | > 80% utilisation | Augmenter la mémoire, vider le cache |
| **Disque plein** | > 90% utilisation | Nettoyer les logs, archiver |
| **Latence élevée** | > 100ms réponse | Optimiser les requêtes |
| **Erreurs** | Logs d'erreur | Analyser et corriger |

### Scripts de Correction

```bash
#!/bin/bash
# fix_common_issues.sh

# 1. Redémarrer les services
restart_services() {
    echo "Restarting services..."
    sudo systemctl restart nexus-backend
    sudo systemctl restart nexus-websocket
    sudo systemctl restart nexus-frontend
}

# 2. Nettoyer le cache
clean_cache() {
    echo "Cleaning cache..."
    redis-cli FLUSHDB
}

# 3. Nettoyer les logs
clean_logs() {
    echo "Cleaning logs..."
    find /var/log/nexus -name "*.log" -mtime +30 -delete
}

# 4. Vérifier la base de données
check_database() {
    echo "Checking database..."
    psql -h localhost -U nexus -d nexus_arbitrage -c "SELECT 1" || \
        echo "Database connection failed!"
}

# 5. Vérifier les exchanges
check_exchanges() {
    echo "Checking exchanges..."
    python check_exchanges.py
}
```

---

## Maintenance de la Base de Données

### PostgreSQL Maintenance

```sql
-- 1. Vérifier la santé
SELECT 
    datname,
    pg_database_size(datname) / 1024 / 1024 / 1024 as size_gb,
    blks_hit,
    blks_read,
    tup_returned,
    tup_fetched,
    tup_inserted,
    tup_updated,
    tup_deleted
FROM pg_stat_database;

-- 2. Vérifier les connexions
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query
FROM pg_stat_activity;

-- 3. Vérifier les locks
SELECT 
    locktype,
    relation::regclass,
    mode,
    granted,
    pid
FROM pg_locks
WHERE NOT granted;

-- 4. Vérifier la taille des tables
SELECT 
    schemaname,
    tablename,
    pg_total_relation_size(schemaname||'.'||tablename) / 1024 / 1024 / 1024 as size_gb
FROM pg_tables
ORDER BY size_gb DESC;

-- 5. Vérifier les indexes
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes;
```

### TimescaleDB Maintenance

```sql
-- 1. Vérifier les chunks
SELECT 
    hypertable_name,
    chunk_name,
    range_start,
    range_end,
    chunk_size
FROM timescaledb_information.chunks;

-- 2. Compression
SELECT compress_chunk('_timescaledb_internal._hyper_1_1_chunk');

-- 3. Décompression
SELECT decompress_chunk('_timescaledb_internal._hyper_1_1_chunk');

-- 4. Vérifier la compression
SELECT 
    chunk_name,
    compression_status,
    compression_rate
FROM timescaledb_information.compression_settings;

-- 5. Drop chunks anciens
SELECT drop_chunks('candles', INTERVAL '90 days');
```

### Backup et Recovery

```bash
#!/bin/bash
# db_maintenance.sh

# 1. Backup
backup_database() {
    DATE=$(date +%Y%m%d_%H%M%S)
    pg_dump -h localhost -U nexus -d nexus_arbitrage > /backups/nexus_$DATE.sql
    gzip /backups/nexus_$DATE.sql
}

# 2. Restore
restore_database() {
    gunzip -c $1 | psql -h localhost -U nexus -d nexus_arbitrage
}

# 3. Vacuum
vacuum_database() {
    psql -h localhost -U nexus -d nexus_arbitrage -c "VACUUM ANALYZE"
}

# 4. Reindex
reindex_database() {
    psql -h localhost -U nexus -d nexus_arbitrage -c "REINDEX DATABASE nexus_arbitrage"
}

# 5. Check
check_database() {
    psql -h localhost -U nexus -d nexus_arbitrage -c "SELECT 1"
}
```

---

## Maintenance du Cache

### Redis Maintenance

```bash
# 1. Vérifier le statut
redis-cli INFO stats

# 2. Vérifier la mémoire
redis-cli INFO memory

# 3. Vérifier les clients
redis-cli CLIENT LIST

# 4. Vider le cache
redis-cli FLUSHDB

# 5. Sauvegarder
redis-cli SAVE

# 6. Défragmentation
redis-cli MEMORY PURGE

# 7. Monitorer
redis-cli MONITOR
```

### Configuration Redis

```bash
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
```

---

## Maintenance des Logs

### Rotation des Logs

```bash
# /etc/logrotate.d/nexus
/var/log/nexus/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 nexus nexus
    postrotate
        systemctl reload nexus
    endscript
}
```

### Analyse des Logs

```python
# log_analyzer.py
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

class LogAnalyzer:
    """Analyseur de logs"""
    
    def __init__(self, log_dir: str = "/var/log/nexus"):
        self.log_dir = Path(log_dir)
        self.errors = defaultdict(int)
        self.warnings = defaultdict(int)
        self.patterns = {
            'error': re.compile(r'ERROR|CRITICAL'),
            'warning': re.compile(r'WARNING'),
            'info': re.compile(r'INFO'),
            'timeout': re.compile(r'timeout|timed out'),
            'connection': re.compile(r'connection|connect'),
        }
    
    def analyze(self):
        """Analyse les logs"""
        for log_file in self.log_dir.glob("*.log"):
            with open(log_file, 'r') as f:
                for line in f:
                    for name, pattern in self.patterns.items():
                        if pattern.search(line):
                            self.errors[name] += 1
        
        return {
            'errors': dict(self.errors),
            'warnings': dict(self.warnings),
            'total_lines': sum(self.errors.values()) + sum(self.warnings.values())
        }
```

---

## Maintenance des Modèles AI

### Évaluation des Modèles

```python
# model_evaluation.py
import torch
from pathlib import Path
import numpy as np

class ModelEvaluator:
    """Évaluateur de modèles AI"""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.metrics = {}
    
    def evaluate_model(self, model_path: Path):
        """Évalue un modèle"""
        # Charger le modèle
        model = torch.load(model_path)
        
        # Évaluer
        metrics = {
            'accuracy': np.random.random(),  # Simulé
            'precision': np.random.random(),
            'recall': np.random.random(),
            'f1': np.random.random(),
        }
        
        return metrics
    
    def evaluate_all(self):
        """Évalue tous les modèles"""
        results = {}
        
        for model_file in self.models_dir.glob("*.pth"):
            results[model_file.name] = self.evaluate_model(model_file)
        
        return results
```

### Retraining des Modèles

```python
# model_retraining.py
import torch
from pathlib import Path
from datetime import datetime

class ModelRetrainer:
    """Retraineur de modèles AI"""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.training_data = None
    
    def prepare_data(self):
        """Prépare les données d'entraînement"""
        # Charger les données
        pass
    
    def retrain_model(self, model_name: str):
        """Retraine un modèle"""
        # Charger le modèle existant
        model_path = self.models_dir / model_name
        model = torch.load(model_path)
        
        # Entraîner
        print(f"Retraining {model_name}...")
        
        # Sauvegarder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_path = self.models_dir / f"{model_name}_v{timestamp}.pth"
        torch.save(model, new_path)
        print(f"Model saved: {new_path}")
    
    def retrain_all(self):
        """Retraine tous les modèles"""
        for model_file in self.models_dir.glob("*.pth"):
            self.retrain_model(model_file.name)
```

---

## Maintenance du Système

### Système Linux

```bash
#!/bin/bash
# system_maintenance.sh

# 1. Mise à jour
update_system() {
    apt update && apt upgrade -y
}

# 2. Nettoyage
clean_system() {
    apt autoclean
    apt autoremove -y
    docker system prune -f
}

# 3. Vérification des logs
check_logs() {
    journalctl -u nexus -n 100 --no-pager
}

# 4. Vérification des services
check_services() {
    systemctl status nexus
    systemctl status postgresql
    systemctl status redis
}

# 5. Vérification du réseau
check_network() {
    ping -c 4 api.binance.com
    ping -c 4 api.bybit.com
}
```

### Docker Maintenance

```bash
# 1. Vérifier les containers
docker ps -a

# 2. Voir les logs
docker logs -f nexus-backend

# 3. Nettoyer
docker system prune -f
docker volume prune -f

# 4. Mettre à jour les images
docker pull nexus/backend:latest
docker pull nexus/frontend:latest

# 5. Redémarrer
docker-compose restart
```

---

## Mises à Jour

### Procédure de Mise à Jour

```yaml
update_procedure:
  # 1. Préparation
  preparation:
    - step: "Backup current system"
      command: "./backup_all.sh"
      duration: 30  # minutes
    
    - step: "Notify users"
      command: "./notify_update.sh"
      duration: 5
  
  # 2. Mise à jour
  update:
    - step: "Pull latest code"
      command: "git pull origin main"
      duration: 5
    
    - step: "Install dependencies"
      command: "pip install -r requirements.txt"
      duration: 10
    
    - step: "Run migrations"
      command: "python manage.py migrate"
      duration: 15
    
    - step: "Build new images"
      command: "docker-compose build"
      duration: 20
  
  # 3. Déploiement
  deployment:
    - step: "Stop old services"
      command: "docker-compose down"
      duration: 5
    
    - step: "Start new services"
      command: "docker-compose up -d"
      duration: 10
    
    - step: "Verify deployment"
      command: "./healthcheck.sh"
      duration: 5
  
  # 4. Post-déploiement
  post_deployment:
    - step: "Monitor for 1 hour"
      command: "./monitor.sh"
      duration: 60
```

### Rollback

```bash
#!/bin/bash
# rollback.sh

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: ./rollback.sh <version>"
    exit 1
fi

echo "Rolling back to version $VERSION..."

# 1. Restaurer les images
docker tag nexus/backend:$VERSION nexus/backend:latest
docker tag nexus/frontend:$VERSION nexus/frontend:latest

# 2. Redémarrer
docker-compose up -d

# 3. Vérifier
./healthcheck.sh

echo "Rollback completed"
```

---

## Monitoring de Maintenance

### Tableau de Bord

```yaml
maintenance_dashboard:
  panels:
    - title: "System Health"
      type: "status"
      checks:
        - "CPU usage"
        - "Memory usage"
        - "Disk usage"
        - "Service status"
    
    - title: "Database Health"
      type: "status"
      checks:
        - "Connection status"
        - "Replication lag"
        - "Query performance"
        - "Table sizes"
    
    - title: "Log Summary"
      type: "logs"
      sources:
        - "/var/log/nexus/*.log"
      alert_on: "ERROR"
```

### Alertes de Maintenance

```yaml
maintenance_alerts:
  # 1. Système
  system:
    - name: "high_cpu"
      condition: "cpu > 80%"
      severity: "warning"
      action: "notify"
    
    - name: "high_memory"
      condition: "memory > 80%"
      severity: "warning"
      action: "notify"
    
    - name: "disk_full"
      condition: "disk > 90%"
      severity: "critical"
      action: "notify,cleanup"
  
  # 2. Application
  application:
    - name: "service_down"
      condition: "service == stopped"
      severity: "critical"
      action: "notify,restart"
    
    - name: "database_down"
      condition: "database == down"
      severity: "critical"
      action: "notify,recover"
  
  # 3. Trading
  trading:
    - name: "exchange_offline"
      condition: "exchange == offline"
      severity: "warning"
      action: "notify,reconnect"
    
    - name: "strategy_error"
      condition: "error_rate > 5%"
      severity: "warning"
      action: "notify"
```

---

## Checklists de Maintenance

### Daily Checklist

```markdown
# 📋 Daily Maintenance Checklist

## ✅ System
- [ ] Check CPU usage (< 80%)
- [ ] Check Memory usage (< 80%)
- [ ] Check Disk usage (< 80%)
- [ ] Check service status (all running)
- [ ] Review error logs

## ✅ Trading
- [ ] Check exchange connections
- [ ] Check strategy performance
- [ ] Check positions and PnL
- [ ] Check opportunities

## ✅ Security
- [ ] Check API keys status
- [ ] Check failed login attempts
- [ ] Review security alerts
```

### Weekly Checklist

```markdown
# 📋 Weekly Maintenance Checklist

## ✅ Database
- [ ] Run VACUUM ANALYZE
- [ ] Check replication status
- [ ] Review slow queries
- [ ] Check backup integrity

## ✅ System
- [ ] Apply security patches
- [ ] Clean old logs
- [ ] Check system updates
- [ ] Review performance metrics

## ✅ Trading
- [ ] Review strategy performance
- [ ] Adjust parameters if needed
- [ ] Check market conditions
- [ ] Review risk metrics
```

### Monthly Checklist

```markdown
# 📋 Monthly Maintenance Checklist

## ✅ Performance
- [ ] Generate monthly report
- [ ] Analyze performance metrics
- [ ] Review strategy effectiveness
- [ ] Plan optimizations

## ✅ Security
- [ ] Audit user accounts
- [ ] Rotate API keys
- [ ] Review access logs
- [ ] Update security policies

## ✅ Infrastructure
- [ ] Review resource usage
- [ ] Plan capacity upgrades
- [ ] Test DR procedures
- [ ] Update documentation
```

---

## Procédures d'Urgence

### Incident Response

```yaml
incident_response:
  # 1. Détection
  detection:
    - source: "monitoring_alerts"
    - source: "user_reports"
    - source: "log_analysis"
  
  # 2. Évaluation
  evaluation:
    - step: "Assess impact"
      duration: 5  # minutes
    
    - step: "Identify root cause"
      duration: 15
  
  # 3. Résolution
  resolution:
    - step: "Apply fix"
      duration: 30
    
    - step: "Verify resolution"
      duration: 10
  
  # 4. Post-incident
  post_incident:
    - step: "Document incident"
      duration: 30
    
    - step: "Implement improvements"
      duration: 60
```

### Contacts d'Urgence

```yaml
emergency_contacts:
  - role: "Primary Contact"
    name: "John Doe"
    phone: "+1-555-123-4567"
    email: "john.doe@nexustradingia.com"
  
  - role: "Secondary Contact"
    name: "Jane Smith"
    phone: "+1-555-987-6543"
    email: "jane.smith@nexustradingia.com"
  
  - role: "Database Admin"
    name: "Bob Johnson"
    phone: "+1-555-456-7890"
    email: "bob.johnson@nexustradingia.com"
```

---

## Outils de Maintenance

### Scripts Utilitaires

```python
# maintenance_tools.py
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

class MaintenanceTools:
    """Outils de maintenance"""
    
    @staticmethod
    def get_system_health() -> dict:
        """Récupère la santé du système"""
        return {
            'cpu': psutil.cpu_percent(),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'services': MaintenanceTools.check_services(),
        }
    
    @staticmethod
    def check_services() -> dict:
        """Vérifie les services"""
        services = ['nexus-backend', 'nexus-websocket', 'postgresql', 'redis']
        status = {}
        
        for service in services:
            result = subprocess.run(
                ['systemctl', 'is-active', service],
                capture_output=True,
                text=True
            )
            status[service] = result.stdout.strip() == 'active'
        
        return status
    
    @staticmethod
    def cleanup_logs(days: int = 30):
        """Nettoie les logs anciens"""
        log_dir = Path("/var/log/nexus")
        for log_file in log_dir.glob("*.log"):
            if log_file.stat().st_mtime < time.time() - days * 86400:
                log_file.unlink()
                print(f"Removed: {log_file}")
    
    @staticmethod
    def rotate_keys():
        """Rotation des clés API"""
        # Générer de nouvelles clés
        pass
```

---

## Exemples

### Exemple Complet

```python
# maintenance_manager.py
import schedule
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MaintenanceManager:
    """Gestionnaire de maintenance"""
    
    def __init__(self):
        self.tasks = []
        self.results = []
        
        # Planifier les tâches
        self.schedule_tasks()
    
    def schedule_tasks(self):
        """Planifie les tâches de maintenance"""
        # Daily
        schedule.every().day.at("00:00").do(self.daily_maintenance)
        schedule.every().day.at("02:00").do(self.backup_database)
        schedule.every().day.at("03:00").do(self.cleanup_logs)
        
        # Weekly
        schedule.every().sunday.at("02:00").do(self.weekly_maintenance)
        schedule.every().sunday.at("04:00").do(self.vacuum_database)
        
        # Monthly
        schedule.every().month.at("01:00").do(self.monthly_maintenance)
        schedule.every().month.at("02:00").do(self.rotate_keys)
    
    def daily_maintenance(self):
        """Maintenance quotidienne"""
        logger.info("Running daily maintenance...")
        self.results.append({
            'task': 'daily_maintenance',
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
    
    def weekly_maintenance(self):
        """Maintenance hebdomadaire"""
        logger.info("Running weekly maintenance...")
        self.results.append({
            'task': 'weekly_maintenance',
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
    
    def monthly_maintenance(self):
        """Maintenance mensuelle"""
        logger.info("Running monthly maintenance...")
        self.results.append({
            'task': 'monthly_maintenance',
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
    
    def backup_database(self):
        """Backup de la base de données"""
        logger.info("Backing up database...")
        self.results.append({
            'task': 'backup_database',
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
    
    def cleanup_logs(self):
        """Nettoyer les logs"""
        logger.info("Cleaning up logs...")
        self.results.append({
            'task': 'cleanup_logs',
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
    
    def vacuum_database(self):
        """VACUUM de la base de données"""
        logger.info("Vacuuming database...")
        self.results.append({
            'task': 'vacuum_database',
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
    
    def rotate_keys(self):
        """Rotation des clés"""
        logger.info("Rotating keys...")
        self.results.append({
            'task': 'rotate_keys',
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
    
    def run(self):
        """Exécute la boucle de maintenance"""
        logger.info("Maintenance manager started")
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    def get_report(self) -> dict:
        """Récupère le rapport de maintenance"""
        return {
            'tasks': self.tasks,
            'results': self.results[-100:],  # Derniers 100 résultats
            'total_tasks': len(self.results),
            'success_rate': len([r for r in self.results if r['status'] == 'success']) / len(self.results) if self.results else 0,
        }

# Utilisation
if __name__ == "__main__":
    manager = MaintenanceManager()
    
    try:
        manager.run()
    except KeyboardInterrupt:
        print("Maintenance manager stopped")
```

---

## 📚 Ressources Additionnelles

- [Guide de Configuration](CONFIGURATION.md)
- [Guide de Déploiement](DEPLOYMENT.md)
- [Guide de Monitoring](MONITORING.md)
- [Guide de Sécurité](SECURITY.md)
- [Guide de Backup](BACKUP.md)

---

## 📞 Support

Pour toute question ou problème, veuillez contacter:

- **Email**: support@nexustradingia.com
- **Discord**: [Nexus Trading IA](https://discord.gg/nexustradingia)
- **Telegram**: [@NexusTradingIA](https://t.me/NexusTradingIA)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

# NEXUS AI Trading System - Backup and Recovery Guide

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Types de Backups](#types-de-backups)
3. [Backup de la Base de Données](#backup-de-la-base-de-données)
4. [Backup des Fichiers de Configuration](#backup-des-fichiers-de-configuration)
5. [Backup des Logs](#backup-des-logs)
6. [Backup des Modèles AI](#backup-des-modèles-ai)
7. [Backup des Données de Marché](#backup-des-données-de-marché)
8. [Stratégies de Backup](#stratégies-de-backup)
9. [Recovery](#recovery)
10. [Disaster Recovery](#disaster-recovery)
11. [Automation](#automation)
12. [Monitoring des Backups](#monitoring-des-backups)
13. [Sécurité des Backups](#sécurité-des-backups)
14. [Exemples](#exemples)

---

## Introduction

La sauvegarde et la récupération sont essentielles pour garantir la continuité des opérations du NEXUS AI Trading System. Ce guide détaille les stratégies de backup, les procédures de récupération et les bonnes pratiques.

### Architecture de Backup

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEXUS AI Trading System                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Database    │           │   Files       │           │   Models      │
│   Backup      │           │   Backup      │           │   Backup      │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Backup Storage (S3/Cloud)                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Types de Backups

### Backups Système

```yaml
backup_types:
  # 1. Base de Données
  database:
    enabled: true
    type: "full"  # full, incremental, differential
    frequency: "daily"
    retention: 30  # jours
    compression: true
    encryption: true
  
  # 2. Fichiers de Configuration
  config:
    enabled: true
    type: "full"
    frequency: "daily"
    retention: 90  # jours
    files:
      - "config/*.yaml"
      - "config/*.json"
      - ".env"
  
  # 3. Logs
  logs:
    enabled: true
    type: "full"
    frequency: "weekly"
    retention: 90  # jours
    files:
      - "logs/*.log"
  
  # 4. Modèles AI
  models:
    enabled: true
    type: "full"
    frequency: "weekly"
    retention: 180  # jours
    files:
      - "models/*.pth"
      - "models/*.onnx"
  
  # 5. Données de Marché
  market_data:
    enabled: true
    type: "full"
    frequency: "weekly"
    retention: 90  # jours
    files:
      - "data/market/*.csv"
      - "data/market/*.parquet"
```

---

## Backup de la Base de Données

### PostgreSQL/TimescaleDB

```bash
#!/bin/bash
# backup_database.sh

# Configuration
BACKUP_DIR="/backups/postgres"
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="nexus_arbitrage"
DB_USER="nexus"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/nexus_$DATE.sql.gz"

# Créer le répertoire
mkdir -p $BACKUP_DIR

# Backup complet
pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME \
  --format=custom \
  --file=$BACKUP_FILE \
  --verbose

# Vérifier le backup
if [ $? -eq 0 ]; then
    echo "Backup completed: $BACKUP_FILE"
    # Compresser
    gzip $BACKUP_FILE
else
    echo "Backup failed!"
    exit 1
fi

# Supprimer les backups anciens
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### Backup avec pg_dumpall

```bash
#!/bin/bash
# backup_all_databases.sh

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/all_databases_$DATE.sql.gz"

# Backup de toutes les bases
pg_dumpall -h localhost -U postgres | gzip > $BACKUP_FILE

# Vérifier
if [ $? -eq 0 ]; then
    echo "All databases backup completed: $BACKUP_FILE"
else
    echo "Backup failed!"
    exit 1
fi
```

### Backup TimescaleDB

```sql
-- Backup avec compression
\timing
\copy (SELECT * FROM candles) TO '/backups/candles.csv' CSV HEADER;

-- Backup des chunks
SELECT * FROM timescaledb_information.chunks;
```

---

## Backup des Fichiers de Configuration

### Script de Backup

```bash
#!/bin/bash
# backup_config.sh

BACKUP_DIR="/backups/config"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/config_$DATE.tar.gz"

# Créer le répertoire
mkdir -p $BACKUP_DIR

# Backup des fichiers de configuration
tar -czf $BACKUP_FILE \
    config/ \
    .env \
    .env.example \
    docker-compose.yml \
    docker-compose.override.yml

# Vérifier
if [ $? -eq 0 ]; then
    echo "Config backup completed: $BACKUP_FILE"
else
    echo "Config backup failed!"
    exit 1
fi

# Supprimer les backups anciens
find $BACKUP_DIR -name "config_*.tar.gz" -mtime +90 -delete
```

### Backup des Configurations Kubernetes

```bash
#!/bin/bash
# backup_k8s_config.sh

BACKUP_DIR="/backups/k8s"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/k8s_config_$DATE.yaml"

# Backup de toutes les ressources
kubectl get all --all-namespaces -o yaml > $BACKUP_FILE

# Backup des ConfigMaps et Secrets
kubectl get configmaps --all-namespaces -o yaml >> $BACKUP_FILE
kubectl get secrets --all-namespaces -o yaml >> $BACKUP_FILE
```

---

## Backup des Logs

### Script de Backup

```bash
#!/bin/bash
# backup_logs.sh

BACKUP_DIR="/backups/logs"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/logs_$DATE.tar.gz"

# Créer le répertoire
mkdir -p $BACKUP_DIR

# Backup des logs
tar -czf $BACKUP_FILE \
    logs/ \
    /var/log/nexus/

# Vérifier
if [ $? -eq 0 ]; then
    echo "Logs backup completed: $BACKUP_FILE"
else
    echo "Logs backup failed!"
    exit 1
fi

# Compresser les logs existants
find logs/ -name "*.log" -exec gzip {} \;
```

### Rotation des Logs

```yaml
# logrotate.conf
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

---

## Backup des Modèles AI

### Script de Backup

```bash
#!/bin/bash
# backup_models.sh

BACKUP_DIR="/backups/models"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/models_$DATE.tar.gz"

# Créer le répertoire
mkdir -p $BACKUP_DIR

# Backup des modèles
tar -czf $BACKUP_FILE \
    models/ \
    ai/checkpoints/

# Vérifier
if [ $? -eq 0 ]; then
    echo "Models backup completed: $BACKUP_FILE"
else
    echo "Models backup failed!"
    exit 1
fi

# Supprimer les backups anciens
find $BACKUP_DIR -name "models_*.tar.gz" -mtime +180 -delete
```

### Backup des Modèles avec Versioning

```python
# backup_models.py
import shutil
from pathlib import Path
from datetime import datetime

def backup_models():
    """Backup des modèles AI"""
    models_dir = Path("models")
    backup_dir = Path("backups/models")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Créer le répertoire
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Copier les modèles
    for model_file in models_dir.glob("*.pth"):
        backup_path = backup_dir / f"{model_file.stem}_{timestamp}{model_file.suffix}"
        shutil.copy2(model_file, backup_path)
        print(f"Backup: {backup_path}")
    
    # Supprimer les backups anciens
    for backup in sorted(backup_dir.glob("*.pth"))[:-10]:
        backup.unlink()
        print(f"Removed old backup: {backup}")

if __name__ == "__main__":
    backup_models()
```

---

## Backup des Données de Marché

### Script de Backup

```bash
#!/bin/bash
# backup_market_data.sh

BACKUP_DIR="/backups/market_data"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/market_data_$DATE.tar.gz"

# Créer le répertoire
mkdir -p $BACKUP_DIR

# Backup des données de marché
tar -czf $BACKUP_FILE \
    data/market/ \
    data/historical/

# Vérifier
if [ $? -eq 0 ]; then
    echo "Market data backup completed: $BACKUP_FILE"
else
    echo "Market data backup failed!"
    exit 1
fi

# Supprimer les backups anciens
find $BACKUP_DIR -name "market_data_*.tar.gz" -mtime +90 -delete
```

---

## Stratégies de Backup

### Backup Complet

```yaml
backup_strategies:
  full:
    enabled: true
    schedule: "0 2 * * *"  # Tous les jours à 2h
    retention: 30  # jours
    compression: true
    encryption: true
    storage: "s3://nexus-backups/full/"
```

### Backup Incrémental

```yaml
backup_strategies:
  incremental:
    enabled: true
    schedule: "0 */6 * * *"  # Toutes les 6 heures
    retention: 7  # jours
    base: "full"
    storage: "s3://nexus-backups/incremental/"
```

### Backup Différentiel

```yaml
backup_strategies:
  differential:
    enabled: true
    schedule: "0 */12 * * *"  # Toutes les 12 heures
    retention: 14  # jours
    base: "full"
    storage: "s3://nexus-backups/differential/"
```

### Backup Continu

```yaml
backup_strategies:
  continuous:
    enabled: true
    type: "streaming"
    interval: 60  # secondes
    retention: 1  # jour
    storage: "s3://nexus-backups/continuous/"
```

---

## Recovery

### Recovery de la Base de Données

```bash
#!/bin/bash
# restore_database.sh

BACKUP_FILE=$1
DB_NAME="nexus_arbitrage"
DB_USER="nexus"

# Vérifier le fichier
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Restaurer
gunzip -c $BACKUP_FILE | psql -U $DB_USER -d $DB_NAME

# Vérifier
if [ $? -eq 0 ]; then
    echo "Database restored: $BACKUP_FILE"
else
    echo "Restore failed!"
    exit 1
fi
```

### Recovery des Fichiers

```bash
#!/bin/bash
# restore_files.sh

BACKUP_FILE=$1
RESTORE_DIR="/tmp/restore"

# Créer le répertoire
mkdir -p $RESTORE_DIR

# Restaurer
tar -xzf $BACKUP_FILE -C $RESTORE_DIR

# Copier les fichiers
cp -r $RESTORE_DIR/config/ ./
cp -r $RESTORE_DIR/logs/ ./
cp $RESTORE_DIR/.env ./

# Nettoyer
rm -rf $RESTORE_DIR
```

### Recovery des Modèles

```python
# restore_models.py
import shutil
from pathlib import Path

def restore_models(backup_file: str):
    """Restaurer les modèles AI"""
    models_dir = Path("models")
    backup_dir = Path("backups/models")
    
    # Vérifier le fichier
    if not backup_file.exists():
        print(f"Backup file not found: {backup_file}")
        return
    
    # Restaurer
    shutil.unpack_archive(backup_file, models_dir)
    print(f"Models restored from: {backup_file}")

if __name__ == "__main__":
    restore_models(Path("backups/models_20260101_120000.tar.gz"))
```

---

## Disaster Recovery

### Plan de Recovery

```yaml
disaster_recovery:
  plan:
    name: "NEXUS Disaster Recovery Plan"
    version: "1.0"
    priority: "critical"
    
  recovery_points:
    - type: "point_in_time"
      frequency: "hourly"
      retention: 24  # heures
    
    - type: "daily"
      retention: 30  # jours
    
    - type: "weekly"
      retention: 52  # semaines
    
    - type: "monthly"
      retention: 12  # mois
  
  procedures:
    - step: 1
      action: "Assess the situation"
      duration: 5  # minutes
    
    - step: 2
      action: "Activate DR team"
      duration: 10
    
    - step: 3
      action: "Restore infrastructure"
      duration: 30
    
    - step: 4
      action: "Restore data from backup"
      duration: 60
    
    - step: 5
      action: "Verify system integrity"
      duration: 15
    
    - step: 6
      action: "Resume operations"
      duration: 10
  
  contacts:
    - role: "DR Coordinator"
      name: "John Doe"
      phone: "+1-555-123-4567"
      email: "john.doe@nexustradingia.com"
    
    - role: "Database Admin"
      name: "Jane Smith"
      phone: "+1-555-987-6543"
      email: "jane.smith@nexustradingia.com"
```

### Script de Recovery

```bash
#!/bin/bash
# disaster_recovery.sh

echo "=== NEXUS Disaster Recovery ==="
echo "1. Assessing situation..."
sleep 5

echo "2. Activating DR team..."
sleep 5

echo "3. Restoring infrastructure..."
sleep 5

echo "4. Restoring database..."
./restore_database.sh /backups/latest.sql.gz

echo "5. Restoring files..."
./restore_files.sh /backups/latest.tar.gz

echo "6. Restoring models..."
python restore_models.py /backups/latest_models.tar.gz

echo "7. Verifying system..."
./healthcheck.sh

echo "8. Resuming operations..."
systemctl start nexus

echo "=== Recovery Complete ==="
```

---

## Automation

### Cron Jobs

```bash
# /etc/cron.d/nexus-backup

# Backup quotidien à 2h
0 2 * * * root /scripts/backup_database.sh
0 3 * * * root /scripts/backup_config.sh

# Backup hebdomadaire à 4h le dimanche
0 4 * * 0 root /scripts/backup_logs.sh
0 5 * * 0 root /scripts/backup_models.sh

# Backup mensuel à 6h le 1er du mois
0 6 1 * * root /scripts/backup_market_data.sh
```

### Systemd Timers

```bash
# /etc/systemd/system/nexus-backup.timer
[Unit]
Description=Nexus Backup Timer

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# /etc/systemd/system/nexus-backup.service
[Unit]
Description=Nexus Backup Service

[Service]
Type=oneshot
ExecStart=/scripts/backup_all.sh
User=nexus
Group=nexus

[Install]
WantedBy=multi-user.target
```

### Python Automation

```python
# backup_automation.py
import schedule
import time
from pathlib import Path

def backup_database():
    """Backup automatique de la base de données"""
    print("Starting database backup...")
    # Code de backup

def backup_config():
    """Backup automatique de la configuration"""
    print("Starting config backup...")
    # Code de backup

def backup_models():
    """Backup automatique des modèles"""
    print("Starting models backup...")
    # Code de backup

# Planification
schedule.every().day.at("02:00").do(backup_database)
schedule.every().day.at("03:00").do(backup_config)
schedule.every().sunday.at("04:00").do(backup_models)

# Boucle principale
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Monitoring des Backups

### Métriques

```yaml
backup_monitoring:
  metrics:
    - "backup_size"
    - "backup_duration"
    - "backup_success_rate"
    - "backup_failure_count"
    - "storage_usage"
    - "backup_age"
  
  thresholds:
    max_backup_age: 86400  # 24 heures
    min_backup_success_rate: 0.95
    max_backup_duration: 3600  # 1 heure
  
  alerts:
    - name: "backup_failed"
      condition: "backup_success_rate < 0.95"
      severity: "critical"
      action: "notify"
    
    - name: "backup_old"
      condition: "backup_age > 86400"
      severity: "warning"
      action: "notify"
```

### Script de Monitoring

```bash
#!/bin/bash
# monitor_backups.sh

BACKUP_DIR="/backups"
ALERT_EMAIL="admin@nexustradingia.com"

# Vérifier le dernier backup
LAST_BACKUP=$(find $BACKUP_DIR -name "*.sql.gz" -type f -printf "%T@ %p\n" | sort -n | tail -1 | cut -d' ' -f2-)
BACKUP_AGE=$(( $(date +%s) - $(stat -c %Y $LAST_BACKUP) ))

# Vérifier l'âge
if [ $BACKUP_AGE -gt 86400 ]; then
    echo "Last backup is older than 24 hours: $BACKUP_AGE seconds"
    echo "Last backup: $LAST_BACKUP"
    echo "Alerting..."
    # Envoyer une alerte
fi

# Vérifier la taille
BACKUP_SIZE=$(du -h $LAST_BACKUP | cut -f1)
echo "Backup size: $BACKUP_SIZE"
```

---

## Sécurité des Backups

### Chiffrement

```bash
#!/bin/bash
# encrypt_backup.sh

BACKUP_FILE=$1
KEY_FILE="/keys/backup.key"

# Générer la clé si elle n'existe pas
if [ ! -f "$KEY_FILE" ]; then
    openssl rand -base64 32 > $KEY_FILE
fi

# Chiffrer
openssl enc -aes-256-cbc -salt -in $BACKUP_FILE -out $BACKUP_FILE.enc -pass file:$KEY_FILE

# Supprimer le fichier non chiffré
rm $BACKUP_FILE
```

### Stockage Sécurisé

```yaml
backup_storage:
  # Stockage local
  local:
    enabled: true
    path: "/backups/"
    encryption: true
    permissions: "0600"
  
  # Stockage S3
  s3:
    enabled: true
    bucket: "nexus-backups"
    region: "eu-west-1"
    encryption: true
    lifecycle:
      transition: 30  # jours
      expiration: 365  # jours
  
  # Stockage hors-site
  offsite:
    enabled: true
    type: "sftp"
    host: "backup.nexustradingia.com"
    port: 22
    username: "backup"
    path: "/backups/"
    encryption: true
```

---

## Exemples

### Exemple Complet

```python
# backup_manager.py
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BackupManager:
    """Gestionnaire de backups"""
    
    def __init__(self, backup_dir: str = "/backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = {
            'database': {
                'enabled': True,
                'frequency': 'daily',
                'retention': 30,
            },
            'config': {
                'enabled': True,
                'frequency': 'daily',
                'retention': 90,
            },
            'models': {
                'enabled': True,
                'frequency': 'weekly',
                'retention': 180,
            }
        }
    
    def backup_database(self) -> bool:
        """Backup de la base de données"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"database_{timestamp}.sql.gz"
            
            # Commande pg_dump
            cmd = f"pg_dump -h localhost -U nexus -d nexus_arbitrage | gzip > {backup_file}"
            subprocess.run(cmd, shell=True, check=True)
            
            logger.info(f"Database backup created: {backup_file}")
            
            # Nettoyer les anciens
            self._cleanup("database", self.config['database']['retention'])
            
            return True
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return False
    
    def backup_config(self) -> bool:
        """Backup de la configuration"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"config_{timestamp}.tar.gz"
            
            # Créer l'archive
            shutil.make_archive(
                str(backup_file.with_suffix('')),
                'gztar',
                root_dir='.',
                base_dir='config'
            )
            
            logger.info(f"Config backup created: {backup_file}")
            
            # Nettoyer les anciens
            self._cleanup("config", self.config['config']['retention'])
            
            return True
        except Exception as e:
            logger.error(f"Config backup failed: {e}")
            return False
    
    def backup_models(self) -> bool:
        """Backup des modèles AI"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"models_{timestamp}.tar.gz"
            
            # Créer l'archive
            shutil.make_archive(
                str(backup_file.with_suffix('')),
                'gztar',
                root_dir='.',
                base_dir='models'
            )
            
            logger.info(f"Models backup created: {backup_file}")
            
            # Nettoyer les anciens
            self._cleanup("models", self.config['models']['retention'])
            
            return True
        except Exception as e:
            logger.error(f"Models backup failed: {e}")
            return False
    
    def _cleanup(self, prefix: str, retention: int):
        """Nettoyer les anciens backups"""
        backups = sorted(self.backup_dir.glob(f"{prefix}_*.tar.gz"))
        backups.extend(self.backup_dir.glob(f"{prefix}_*.sql.gz"))
        
        if len(backups) > retention:
            for backup in backups[:-retention]:
                backup.unlink()
                logger.info(f"Removed old backup: {backup}")
    
    def restore_database(self, backup_file: str) -> bool:
        """Restaurer la base de données"""
        try:
            backup_path = self.backup_dir / backup_file
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Commande de restauration
            cmd = f"gunzip -c {backup_path} | psql -U nexus -d nexus_arbitrage"
            subprocess.run(cmd, shell=True, check=True)
            
            logger.info(f"Database restored from: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False
    
    def run_all(self) -> Dict[str, bool]:
        """Exécuter tous les backups"""
        results = {
            'database': self.backup_database(),
            'config': self.backup_config(),
            'models': self.backup_models(),
        }
        
        return results

# Utilisation
if __name__ == "__main__":
    manager = BackupManager()
    results = manager.run_all()
    print("Backup results:", results)
```

---

## 📚 Ressources Additionnelles

- [Guide de Configuration](CONFIGURATION.md)
- [Guide de Déploiement](DEPLOYMENT.md)
- [Guide de Monitoring](MONITORING.md)
- [Guide de Sécurité](SECURITY.md)

---

## 📞 Support

Pour toute question ou problème, veuillez contacter:

- **Email**: support@nexustradingia.com
- **Discord**: [Nexus Trading IA](https://discord.gg/nexustradingia)
- **Telegram**: [@NexusTradingIA](https://t.me/NexusTradingIA)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

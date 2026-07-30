# NEXUS Hedge Bot Deployment Guide
Version: 2.0.0
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

## Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Deployment Methods](#deployment-methods)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Cloud Deployment](#cloud-deployment)
7. [AWS Deployment](#aws-deployment)
8. [GCP Deployment](#gcp-deployment)
9. [Azure Deployment](#azure-deployment)
10. [Local Development](#local-development)
11. [Configuration](#configuration)
12. [Database Setup](#database-setup)
13. [Monitoring Setup](#monitoring-setup)
14. [Security Setup](#security-setup)
15. [Backup and Recovery](#backup-and-recovery)
16. [Scaling](#scaling)
17. [Troubleshooting](#troubleshooting)
18. [Best Practices](#best-practices)

---

## Overview

This guide provides comprehensive instructions for deploying the NEXUS Hedge Bot across various environments. The system is designed to be containerized and cloud-native, supporting multiple deployment strategies.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LOAD BALANCER (NGINX)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│   API Gateway │         │  WebSocket    │         │   Dashboard   │
│   (FastAPI)   │         │   Service     │         │   (Next.js)   │
└───────────────┘         └───────────────┘         └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│    Trading    │         │      AI       │         │    Risk       │
│    Engine     │◄────────┤   Prediction  │─────────│   Management  │
└───────────────┘         └───────────────┘         └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │      Message Bus (Redis)      │
                    └───────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│   PostgreSQL  │         │   TimescaleDB │         │   ClickHouse  │
│   (Primary)   │         │  (Time Series)│         │  (Analytics)  │
└───────────────┘         └───────────────┘         └───────────────┘
```

---

## System Requirements

### Hardware Requirements

| Component | Development | Staging | Production |
|-----------|-------------|---------|------------|
| CPU | 2 cores | 4 cores | 8+ cores |
| RAM | 4 GB | 8 GB | 16+ GB |
| Storage | 50 GB | 100 GB | 500+ GB |
| Network | 100 Mbps | 1 Gbps | 10 Gbps |

### Software Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.12+ | Core runtime |
| Docker | 24.0+ | Containerization |
| Docker Compose | 2.20+ | Local orchestration |
| Kubernetes | 1.28+ | Production orchestration |
| PostgreSQL | 16+ | Primary database |
| TimescaleDB | 2.12+ | Time-series data |
| Redis | 7.2+ | Cache and message bus |
| ClickHouse | 23.12+ | Analytics |
| Nginx | 1.24+ | Reverse proxy |
| Prometheus | 2.48+ | Monitoring |
| Grafana | 10.0+ | Visualization |

### Network Requirements

| Port | Service | Purpose |
|------|---------|---------|
| 80 | Nginx | HTTP traffic |
| 443 | Nginx | HTTPS traffic |
| 8000 | API Gateway | Internal API |
| 3000 | Dashboard | Web interface |
| 5432 | PostgreSQL | Database |
| 6379 | Redis | Cache |
| 9090 | Prometheus | Metrics |
| 3000 | Grafana | Monitoring UI |
| 8080 | WebSocket | Real-time updates |

---

## Deployment Methods

### Method Comparison

| Method | Use Case | Complexity | Scalability |
|--------|----------|------------|-------------|
| Docker Compose | Development, Testing | Low | Limited |
| Kubernetes | Production, Staging | High | Excellent |
| AWS EKS | Production | Medium | Excellent |
| GCP GKE | Production | Medium | Excellent |
| Azure AKS | Production | Medium | Excellent |

---

## Docker Deployment

### Prerequisites

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version
```

### Docker Images

```bash
# Build images
docker build -t nexus-hedge-bot:latest -f docker/backend/Dockerfile .
docker build -t nexus-hedge-bot-dashboard:latest -f docker/frontend/Dockerfile .
docker build -t nexus-hedge-bot-ai:latest -f docker/ai-engine/Dockerfile .
docker build -t nexus-hedge-bot-risk:latest -f docker/risk-engine/Dockerfile .

# Tag images
docker tag nexus-hedge-bot:latest nexusquantum/hedge-bot:2.0.0
docker tag nexus-hedge-bot-dashboard:latest nexusquantum/hedge-bot-dashboard:2.0.0
docker tag nexus-hedge-bot-ai:latest nexusquantum/hedge-bot-ai:2.0.0
docker tag nexus-hedge-bot-risk:latest nexusquantum/hedge-bot-risk:2.0.0

# Push to registry
docker push nexusquantum/hedge-bot:2.0.0
docker push nexusquantum/hedge-bot-dashboard:2.0.0
docker push nexusquantum/hedge-bot-ai:2.0.0
docker push nexusquantum/hedge-bot-risk:2.0.0
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: timescale/timescaledb:2.12.0-pg16
    container_name: nexus-postgres
    environment:
      POSTGRES_DB: nexus_trading
      POSTGRES_USER: nexus
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexus -d nexus_trading"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7.2-alpine
    container_name: nexus-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # API Gateway
  api:
    image: nexusquantum/hedge-bot:2.0.0
    container_name: nexus-api
    environment:
      - ENVIRONMENT=${ENVIRONMENT}
      - DATABASE_URL=postgresql://nexus:${POSTGRES_PASSWORD}@postgres:5432/nexus_trading
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - EXCHANGE_API_KEY=${EXCHANGE_API_KEY}
      - EXCHANGE_API_SECRET=${EXCHANGE_API_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
      - ./models:/app/models
      - ./logs:/app/logs

  # AI Prediction Engine
  ai-engine:
    image: nexusquantum/hedge-bot-ai:2.0.0
    container_name: nexus-ai
    environment:
      - ENVIRONMENT=${ENVIRONMENT}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
      - MODEL_PATH=/app/models/hedge_model.pkl
    depends_on:
      - redis
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

  # Risk Engine
  risk-engine:
    image: nexusquantum/hedge-bot-risk:2.0.0
    container_name: nexus-risk
    environment:
      - ENVIRONMENT=${ENVIRONMENT}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/2
      - DATABASE_URL=postgresql://nexus:${POSTGRES_PASSWORD}@postgres:5432/nexus_trading
    depends_on:
      - postgres
      - redis
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs

  # WebSocket Service
  websocket:
    image: nexusquantum/hedge-bot:2.0.0
    container_name: nexus-websocket
    command: uvicorn app.websocket:app --host 0.0.0.0 --port 8080 --reload
    environment:
      - ENVIRONMENT=${ENVIRONMENT}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/3
    depends_on:
      - redis
    ports:
      - "8080:8080"

  # Dashboard (Next.js)
  dashboard:
    image: nexusquantum/hedge-bot-dashboard:2.0.0
    container_name: nexus-dashboard
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
      - NEXT_PUBLIC_WS_URL=ws://websocket:8080
    ports:
      - "3000:3000"

  # Nginx Reverse Proxy
  nginx:
    image: nginx:1.24-alpine
    container_name: nexus-nginx
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - ./nginx/conf.d:/etc/nginx/conf.d
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
      - dashboard
      - websocket

volumes:
  postgres_data:
  redis_data:
```

### Start Services

```bash
# Create .env file
cat > .env << EOF
ENVIRONMENT=production
POSTGRES_PASSWORD=secure_password_here
REDIS_PASSWORD=secure_password_here
EXCHANGE_API_KEY=your_api_key
EXCHANGE_API_SECRET=your_api_secret
EOF

# Start services
docker-compose up -d

# Verify services
docker-compose ps
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

---

## Kubernetes Deployment

### Prerequisites

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify installations
kubectl version --client
helm version
```

### Helm Chart

```yaml
# helm/nexus-hedge-bot/values.yaml
replicaCount: 3

image:
  repository: nexusquantum/hedge-bot
  tag: 2.0.0
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8000

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.nexusquantum.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - hosts:
        - api.nexusquantum.com
      secretName: nexus-tls

resources:
  limits:
    cpu: 1000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

postgresql:
  enabled: true
  auth:
    postgresPassword: secure_password
    database: nexus_trading
    username: nexus
    password: secure_password
  primary:
    persistence:
      size: 100Gi
    resources:
      limits:
        cpu: 2000m
        memory: 4Gi
      requests:
        cpu: 1000m
        memory: 2Gi

redis:
  enabled: true
  auth:
    password: secure_password
  master:
    persistence:
      size: 10Gi
    resources:
      limits:
        cpu: 500m
        memory: 1Gi
      requests:
        cpu: 250m
        memory: 512Mi

monitoring:
  enabled: true
  prometheus:
    enabled: true
    serviceMonitor:
      enabled: true
  grafana:
    enabled: true
    dashboard:
      enabled: true

logging:
  enabled: true
  loki:
    enabled: true
  promtail:
    enabled: true
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace nexus

# Add Helm repositories
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install dependencies
helm install nexus-postgres bitnami/postgresql -f helm/postgresql-values.yaml -n nexus
helm install nexus-redis bitnami/redis -f helm/redis-values.yaml -n nexus
helm install nexus-prometheus prometheus-community/kube-prometheus-stack -f helm/prometheus-values.yaml -n nexus
helm install nexus-loki grafana/loki-stack -f helm/loki-values.yaml -n nexus

# Install hedge bot
helm install nexus-hedge-bot ./helm/nexus-hedge-bot -f helm/values.yaml -n nexus

# Verify deployment
kubectl get pods -n nexus
kubectl get services -n nexus
kubectl get ingress -n nexus

# Update deployment
helm upgrade nexus-hedge-bot ./helm/nexus-hedge-bot -f helm/values.yaml -n nexus

# Uninstall
helm uninstall nexus-hedge-bot -n nexus
```

---

## Cloud Deployment

### AWS Deployment (EKS)

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Create EKS cluster
eksctl create cluster \
  --name nexus-hedge-bot \
  --region us-east-1 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 10 \
  --managed

# Configure kubectl
aws eks update-kubeconfig --region us-east-1 --name nexus-hedge-bot

# Deploy using Helm
helm install nexus-hedge-bot ./helm/nexus-hedge-bot -f helm/aws-values.yaml -n nexus --create-namespace
```

### GCP Deployment (GKE)

```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Create GKE cluster
gcloud container clusters create nexus-hedge-bot \
  --zone us-central1-a \
  --machine-type n1-standard-4 \
  --num-nodes 3 \
  --enable-autoscaling \
  --min-nodes 3 \
  --max-nodes 10

# Configure kubectl
gcloud container clusters get-credentials nexus-hedge-bot --zone us-central1-a

# Deploy using Helm
helm install nexus-hedge-bot ./helm/nexus-hedge-bot -f helm/gcp-values.yaml -n nexus --create-namespace
```

### Azure Deployment (AKS)

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login

# Create AKS cluster
az aks create \
  --resource-group nexus-rg \
  --name nexus-hedge-bot \
  --node-count 3 \
  --node-vm-size Standard_DS3_v2 \
  --enable-cluster-autoscaler \
  --min-count 3 \
  --max-count 10

# Configure kubectl
az aks get-credentials --resource-group nexus-rg --name nexus-hedge-bot

# Deploy using Helm
helm install nexus-hedge-bot ./helm/nexus-hedge-bot -f helm/azure-values.yaml -n nexus --create-namespace
```

---

## Local Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/NEXUS-QUANTUM/NEXUS-AI-TRADING-SYSTEM.git
cd NEXUS-AI-TRADING-SYSTEM

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Create .env file
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python scripts/init_db.py

# Run migrations
alembic upgrade head

# Start services
docker-compose -f docker-compose.dev.yml up -d

# Run application
python -m trading.bots.hedge_bot.main
```

### Development with Hot Reload

```bash
# API development
uvicorn trading.bots.hedge_bot.api.main:app --reload --port 8000

# Dashboard development
cd apps/web
npm install
npm run dev

# AI engine development
python -m trading.bots.hedge_bot.ai.main

# Risk engine development
python -m trading.bots.hedge_bot.risk.main
```

---

## Database Setup

### PostgreSQL Initialization

```sql
-- Create database
CREATE DATABASE nexus_trading;

-- Create user
CREATE USER nexus WITH PASSWORD 'secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE nexus_trading TO nexus;

-- Connect to database
\c nexus_trading

-- Create schema
CREATE SCHEMA nexus;

-- Set search path
ALTER USER nexus SET search_path TO nexus, public;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### TimescaleDB Setup

```sql
-- Create hypertable for trades
CREATE TABLE trades (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20),
    side VARCHAR(10),
    quantity DECIMAL,
    price DECIMAL,
    fee DECIMAL,
    pnl DECIMAL,
    timestamp TIMESTAMPTZ
);

SELECT create_hypertable('trades', 'timestamp');

-- Create hypertable for market data
CREATE TABLE market_data (
    symbol VARCHAR(20),
    bid DECIMAL,
    ask DECIMAL,
    last DECIMAL,
    volume DECIMAL,
    timestamp TIMESTAMPTZ
);

SELECT create_hypertable('market_data', 'timestamp');

-- Create hypertable for positions
CREATE TABLE positions (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20),
    side VARCHAR(10),
    quantity DECIMAL,
    entry_price DECIMAL,
    current_price DECIMAL,
    unrealized_pnl DECIMAL,
    timestamp TIMESTAMPTZ
);

SELECT create_hypertable('positions', 'timestamp');
```

---

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'nexus-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'nexus-ai'
    static_configs:
      - targets: ['ai-engine:8001']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'nexus-risk'
    static_configs:
      - targets: ['risk-engine:8002']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']
    scrape_interval: 10s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
    scrape_interval: 10s
```

### Grafana Dashboards

```json
{
  "dashboard": {
    "id": null,
    "title": "NEXUS Hedge Bot Monitoring",
    "tags": ["nexus", "hedge-bot"],
    "timezone": "UTC",
    "panels": [
      {
        "id": 1,
        "title": "Hedge Ratio",
        "type": "graph",
        "targets": [
          {
            "expr": "hedge_ratio{strategy='delta_hedging'}",
            "legendFormat": "Hedge Ratio"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "Portfolio Value",
        "type": "graph",
        "targets": [
          {
            "expr": "portfolio_value",
            "legendFormat": "Portfolio Value"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      },
      {
        "id": 3,
        "title": "Risk Metrics",
        "type": "stat",
        "targets": [
          {
            "expr": "var_95",
            "legendFormat": "VaR 95%"
          },
          {
            "expr": "max_drawdown",
            "legendFormat": "Max Drawdown"
          }
        ],
        "gridPos": {"h": 6, "w": 12, "x": 0, "y": 8}
      },
      {
        "id": 4,
        "title": "Trade Volume",
        "type": "bargauge",
        "targets": [
          {
            "expr": "trade_volume",
            "legendFormat": "Trade Volume"
          }
        ],
        "gridPos": {"h": 6, "w": 12, "x": 12, "y": 8}
      }
    ]
  }
}
```

---

## Security Setup

### SSL/TLS Configuration

```bash
# Generate SSL certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/nexus.key \
  -out /etc/nginx/ssl/nexus.crt \
  -subj "/C=GB/ST=London/L=London/O=NEXUS QUANTUM/CN=nexusquantum.com"

# Or use Let's Encrypt
certbot --nginx -d nexusquantum.com -d api.nexusquantum.com
```

### Firewall Configuration

```bash
# UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# IP Whitelist
sudo ufw allow from 192.168.1.0/24 to any port 5432
sudo ufw allow from 192.168.1.0/24 to any port 6379
```

---

## Backup and Recovery

### Automated Backup

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups/nexus"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup PostgreSQL
pg_dump -h localhost -U nexus nexus_trading > ${BACKUP_DIR}/postgres_${DATE}.sql

# Backup Redis
redis-cli --rdb ${BACKUP_DIR}/redis_${DATE}.rdb

# Backup Configuration
tar -czf ${BACKUP_DIR}/config_${DATE}.tar.gz /opt/nexus-trading/config

# Backup Models
tar -czf ${BACKUP_DIR}/models_${DATE}.tar.gz /opt/nexus-trading/models

# Upload to S3
aws s3 sync ${BACKUP_DIR} s3://nexus-backups/$(date +%Y/%m/%d/)

# Clean old backups
find ${BACKUP_DIR} -type f -mtime +30 -delete
```

### Recovery Procedures

```bash
# Restore PostgreSQL
psql -h localhost -U nexus nexus_trading < postgres_backup.sql

# Restore Redis
redis-cli --rdb redis_backup.rdb

# Restore Configuration
tar -xzf config_backup.tar.gz -C /

# Restart Services
docker-compose restart
```

---

## Scaling

### Horizontal Scaling

```yaml
# Kubernetes HPA configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: nexus-hedge-bot-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nexus-hedge-bot
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Vertical Scaling

```yaml
# Vertical Pod Autoscaler
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: nexus-hedge-bot-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nexus-hedge-bot
  updatePolicy:
    updateMode: Auto
```

---

## Troubleshooting

### Common Issues

#### Database Connection Issues

```bash
# Check PostgreSQL status
docker-compose logs postgres

# Test connection
psql -h localhost -U nexus -d nexus_trading -c "SELECT 1"

# Reset database
docker-compose down -v
docker-compose up -d postgres
python scripts/init_db.py
```

#### Exchange API Issues

```bash
# Check API connectivity
python scripts/test_exchange.py

# Verify API keys
echo $EXCHANGE_API_KEY
echo $EXCHANGE_API_SECRET

# Reset rate limits
redis-cli DEL rate_limit:*
```

#### Memory Issues

```bash
# Check memory usage
docker stats
kubectl top pods

# Adjust memory limits
# In docker-compose.yml or Kubernetes values.yaml

# Clear cache
redis-cli FLUSHALL
```

---

## Best Practices

### Security

1. **Never commit secrets to Git**
   - Use environment variables
   - Use Vault or AWS Secrets Manager
   - Encrypt sensitive data

2. **Least Privilege Principle**
   - Use read-only API keys when possible
   - Limit access to specific IPs
   - Use service accounts with minimal permissions

3. **Regular Updates**
   - Keep all dependencies updated
   - Apply security patches regularly
   - Monitor security advisories

### Monitoring

1. **Set up alerts for critical metrics**
   - API response time > 1s
   - Error rate > 1%
   - Memory usage > 80%
   - Disk space < 20%

2. **Log everything**
   - Use structured logging (JSON format)
   - Include correlation IDs
   - Set appropriate log levels

3. **Regular health checks**
   - Liveness probes
   - Readiness probes
   - End-to-end testing

### Performance

1. **Use connection pooling**
   - Database connections
   - Redis connections
   - HTTP connections

2. **Implement caching**
   - Redis for frequent queries
   - CDN for static assets
   - Cache API responses

3. **Optimize database**
   - Create appropriate indexes
   - Use read replicas for analytics
   - Implement query optimization

### Deployment

1. **Use blue-green deployments**
   - Zero downtime
   - Easy rollback
   - Safe testing

2. **Implement CI/CD**
   - Automated testing
   - Automated builds
   - Automated deployments

3. **Document everything**
   - Configuration
   - Architecture
   - Runbooks

---

## Support

For deployment support:

- Email: support@nexusquantum.com
- Documentation: https://docs.nexusquantum.com
- Status Page: https://status.nexusquantum.com
- GitHub Issues: https://github.com/NEXUS-QUANTUM/NEXUS-AI-TRADING-SYSTEM/issues

---

## Copyright

Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

This document is proprietary and confidential. Unauthorized use, copying, or distribution is prohibited.

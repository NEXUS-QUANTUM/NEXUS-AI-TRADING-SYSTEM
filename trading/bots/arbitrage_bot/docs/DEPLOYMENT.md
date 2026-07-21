# NEXUS AI Trading System - Deployment Guide

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Prérequis](#prérequis)
3. [Déploiement Docker](#déploiement-docker)
4. [Déploiement Kubernetes](#déploiement-kubernetes)
5. [Déploiement AWS](#déploiement-aws)
6. [Déploiement Azure](#déploiement-azure)
7. [Déploiement GCP](#déploiement-gcp)
8. [Configuration Multi-Cloud](#configuration-multi-cloud)
9. [Monitoring et Logging](#monitoring-et-logging)
10. [CI/CD Pipeline](#cicd-pipeline)
11. [Sécurité](#sécurité)
12. [Backup et Recovery](#backup-et-recovery)
13. [Scaling](#scaling)
14. [Maintenance](#maintenance)
15. [Troubleshooting](#troubleshooting)

---

## Introduction

Ce guide détaille les procédures de déploiement du NEXUS AI Trading System dans différents environnements. Nous couvrons les déploiements Docker, Kubernetes, et les principaux fournisseurs de cloud (AWS, Azure, GCP).

### Architecture Cible

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Load Balancer (NGINX)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API Gateway (Kong/NGINX)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  Backend API  │           │  WebSocket    │           │  Dashboard    │
│   (FastAPI)   │           │  Service      │           │  (Next.js)    │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Message Queue (Redis)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  Arbitrage    │           │  Execution    │           │  Market Data  │
│  Engine       │           │  Engine       │           │  Service      │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Database (PostgreSQL/TimescaleDB)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Prérequis

### Logiciels Requis

| Logiciel | Version | Description |
|----------|---------|-------------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Orchestration multi-containers |
| Kubernetes | 1.24+ | Orchestration container |
| Helm | 3.10+ | Package manager Kubernetes |
| Terraform | 1.3+ | Infrastructure as Code |
| Python | 3.10+ | Langage principal |
| Node.js | 18+ | Frontend |
| PostgreSQL | 14+ | Base de données |
| Redis | 7+ | Cache et queue |

### Ressources Minimum

| Environment | CPU | Memory | Storage | Network |
|-------------|-----|--------|---------|---------|
| Development | 2 cores | 4 GB | 20 GB | 100 Mbps |
| Staging | 4 cores | 8 GB | 50 GB | 1 Gbps |
| Production | 8 cores | 16 GB | 100 GB | 10 Gbps |
| High Availability | 16 cores | 32 GB | 500 GB | 10 Gbps |

### Comptes Requis

- Docker Hub account (ou autre registry)
- Cloud provider account (AWS, Azure, GCP)
- Domain name (optional)
- SSL/TLS certificate

---

## Déploiement Docker

### Structure des Fichiers

```
deployments/docker/
├── docker-compose.yml
├── docker-compose.override.yml
├── docker-compose.prod.yml
├── .env
├── .env.example
├── nginx/
│   ├── nginx.conf
│   └── sites-enabled/
├── backend/
│   └── Dockerfile
├── frontend/
│   └── Dockerfile
├── websocket/
│   └── Dockerfile
├── ai-engine/
│   └── Dockerfile
├── execution-engine/
│   └── Dockerfile
├── market-data/
│   └── Dockerfile
├── risk-engine/
│   └── Dockerfile
└── postgres/
    └── Dockerfile
```

### Docker Compose (Development)

```yaml
# docker-compose.yml
version: '3.8'

services:
  # PostgreSQL
  postgres:
    image: timescale/timescaledb:2.10-pg14
    container_name: nexus-postgres
    environment:
      POSTGRES_DB: nexus_arbitrage
      POSTGRES_USER: nexus
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexus"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - nexus-network

  # Redis
  redis:
    image: redis:7-alpine
    container_name: nexus-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - nexus-network

  # Backend API
  backend:
    build:
      context: ../../
      dockerfile: deployments/docker/backend/Dockerfile
    container_name: nexus-backend
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=nexus_arbitrage
      - DB_USER=nexus
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - NEXUS_ENV=${NEXUS_ENV:-development}
      - NEXUS_DEBUG=${NEXUS_DEBUG:-true}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ../../:/app
    command: uvicorn trading.bots.arbitrage_bot.arbitrage_bot_api:app --host 0.0.0.0 --port 8000 --reload
    networks:
      - nexus-network

  # WebSocket Service
  websocket:
    build:
      context: ../../
      dockerfile: deployments/docker/websocket/Dockerfile
    container_name: nexus-websocket
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    ports:
      - "8001:8001"
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - nexus-network

  # Dashboard Frontend
  frontend:
    build:
      context: ../../
      dockerfile: deployments/docker/frontend/Dockerfile
    container_name: nexus-frontend
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
      - NEXT_PUBLIC_WS_URL=ws://websocket:8001
    ports:
      - "3000:3000"
    depends_on:
      - backend
      - websocket
    networks:
      - nexus-network

  # Nginx Proxy
  nginx:
    build:
      context: ../../
      dockerfile: deployments/docker/nginx/Dockerfile
    container_name: nexus-nginx
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
      - websocket
      - frontend
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/sites-enabled:/etc/nginx/sites-enabled:ro
      - ./ssl:/etc/nginx/ssl:ro
    networks:
      - nexus-network

networks:
  nexus-network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
```

### Fichier .env

```env
# Environment
NEXUS_ENV=development
NEXUS_DEBUG=true

# Database
DB_PASSWORD=nexus_password

# Redis
REDIS_PASSWORD=redis_password

# API Keys
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret
BYBIT_API_KEY=your_bybit_key
BYBIT_API_SECRET=your_bybit_secret

# Notifications
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
SLACK_WEBHOOK_URL=your_slack_webhook

# JWT
JWT_SECRET=your_jwt_secret
ADMIN_API_KEY=your_admin_key
```

### Commandes Docker

```bash
# Build et start
docker-compose up -d --build

# Voir les logs
docker-compose logs -f

# Arrêter
docker-compose down

# Arrêter et supprimer les volumes
docker-compose down -v

# Voir le statut
docker-compose ps

# Exécuter une commande dans un container
docker-compose exec backend python manage.py migrate
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  postgres:
    image: timescale/timescaledb:2.10-pg14
    restart: always
    environment:
      POSTGRES_DB: nexus_arbitrage
      POSTGRES_USER: nexus
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexus"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - nexus-network

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 2gb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - nexus-network

  backend:
    build:
      context: ../../
      dockerfile: deployments/docker/backend/Dockerfile
    restart: always
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=nexus_arbitrage
      - DB_USER=nexus
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - NEXUS_ENV=production
      - NEXUS_DEBUG=false
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: gunicorn -w 4 -k uvicorn.workers.UvicornWorker trading.bots.arbitrage_bot.arbitrage_bot_api:app --bind 0.0.0.0:8000
    networks:
      - nexus-network

  # ... autres services
```

---

## Déploiement Kubernetes

### Structure des Fichiers

```
deployments/kubernetes/
├── base/
│   ├── configmap.yaml
│   ├── secrets.yaml
│   └── namespace.yaml
├── services/
│   ├── backend.yaml
│   ├── websocket.yaml
│   ├── frontend.yaml
│   ├── postgres.yaml
│   └── redis.yaml
├── deployments/
│   ├── backend.yaml
│   ├── websocket.yaml
│   ├── frontend.yaml
│   ├── ai-engine.yaml
│   ├── execution-engine.yaml
│   ├── market-data.yaml
│   └── risk-engine.yaml
├── ingress/
│   └── ingress.yaml
├── hpa/
│   ├── backend-hpa.yaml
│   ├── websocket-hpa.yaml
│   └── frontend-hpa.yaml
├── kustomization.yaml
└── README.md
```

### Kustomization

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: nexus

resources:
  - base/namespace.yaml
  - base/configmap.yaml
  - base/secrets.yaml
  - services/backend.yaml
  - services/websocket.yaml
  - services/frontend.yaml
  - services/postgres.yaml
  - services/redis.yaml
  - deployments/backend.yaml
  - deployments/websocket.yaml
  - deployments/frontend.yaml
  - deployments/ai-engine.yaml
  - deployments/execution-engine.yaml
  - deployments/market-data.yaml
  - deployments/risk-engine.yaml
  - ingress/ingress.yaml
  - hpa/backend-hpa.yaml
  - hpa/websocket-hpa.yaml
  - hpa/frontend-hpa.yaml

configMapGenerator:
  - name: nexus-config
    envs:
      - .env

secretGenerator:
  - name: nexus-secrets
    envs:
      - .env.secrets

images:
  - name: nexus-backend
    newName: nexus/backend
    newTag: latest
  - name: nexus-websocket
    newName: nexus/websocket
    newTag: latest
  - name: nexus-frontend
    newName: nexus/frontend
    newTag: latest
```

### Déploiement Backend

```yaml
# deployments/backend.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nexus-backend
  namespace: nexus
  labels:
    app: nexus
    component: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nexus
      component: backend
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: nexus
        component: backend
    spec:
      containers:
      - name: backend
        image: nexus/backend:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        envFrom:
        - configMapRef:
            name: nexus-config
        - secretRef:
            name: nexus-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: logs
          mountPath: /var/log/nexus
      volumes:
      - name: config
        configMap:
          name: nexus-config
      - name: logs
        persistentVolumeClaim:
          claimName: nexus-logs-pvc
```

### Service Backend

```yaml
# services/backend.yaml
apiVersion: v1
kind: Service
metadata:
  name: nexus-backend
  namespace: nexus
  labels:
    app: nexus
    component: backend
spec:
  selector:
    app: nexus
    component: backend
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  - name: metrics
    port: 9090
    targetPort: 9090
  type: ClusterIP
```

### HPA Backend

```yaml
# hpa/backend-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: nexus-backend-hpa
  namespace: nexus
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nexus-backend
  minReplicas: 2
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

### Ingress

```yaml
# ingress/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nexus-ingress
  namespace: nexus
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.nexustradingia.com
    - app.nexustradingia.com
    - ws.nexustradingia.com
    secretName: nexus-tls
  rules:
  - host: api.nexustradingia.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nexus-backend
            port:
              number: 8000
  - host: app.nexustradingia.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nexus-frontend
            port:
              number: 3000
  - host: ws.nexustradingia.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nexus-websocket
            port:
              number: 8001
```

### Commandes Kubernetes

```bash
# Appliquer la configuration
kubectl apply -k deployments/kubernetes/

# Voir les ressources
kubectl get all -n nexus

# Voir les logs
kubectl logs -f deployment/nexus-backend -n nexus

# Scale
kubectl scale deployment nexus-backend --replicas=5 -n nexus

# Rollback
kubectl rollout undo deployment/nexus-backend -n nexus

# Port-forward
kubectl port-forward deployment/nexus-backend 8000:8000 -n nexus
```

---

## Déploiement AWS

### Architecture AWS

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Route 53 (DNS)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CloudFront (CDN)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Application Load Balancer (ALB)                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  ECS/Fargate  │           │  ECS/Fargate  │           │  ECS/Fargate  │
│   Backend     │           │  WebSocket    │           │  Frontend     │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             ElastiCache (Redis)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RDS (PostgreSQL/TimescaleDB)                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Terraform AWS

```hcl
# providers.tf
provider "aws" {
  region = var.aws_region
}

# VPC
resource "aws_vpc" "nexus" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "nexus-vpc"
  }
}

# Subnets
resource "aws_subnet" "nexus_public" {
  count = 2

  vpc_id                  = aws_vpc.nexus.id
  cidr_block              = cidrsubnet(aws_vpc.nexus.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "nexus-public-${count.index}"
  }
}

resource "aws_subnet" "nexus_private" {
  count = 2

  vpc_id                  = aws_vpc.nexus.id
  cidr_block              = cidrsubnet(aws_vpc.nexus.cidr_block, 8, count.index + 2)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "nexus-private-${count.index}"
  }
}

# RDS
resource "aws_db_instance" "nexus" {
  identifier     = "nexus-database"
  engine         = "postgres"
  engine_version = "14.5"
  instance_class = "db.r6g.large"
  
  allocated_storage     = 100
  storage_encrypted     = true
  storage_type         = "gp3"
  
  db_name  = "nexus_arbitrage"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.nexus_rds.id]
  db_subnet_group_name   = aws_db_subnet_group.nexus.name
  
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  enabled_cloudwatch_logs_exports = ["postgresql"]
  
  tags = {
    Name = "nexus-database"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "nexus" {
  cluster_id           = "nexus-redis"
  engine              = "redis"
  node_type           = "cache.t3.medium"
  num_cache_nodes     = 1
  parameter_group_name = "default.redis7"
  port                = 6379
  
  subnet_group_name = aws_elasticache_subnet_group.nexus.name
  security_group_ids = [aws_security_group.nexus_redis.id]
  
  tags = {
    Name = "nexus-redis"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "nexus" {
  name = "nexus-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition - Backend
resource "aws_ecs_task_definition" "nexus_backend" {
  family                   = "nexus-backend"
  network_mode            = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                    = "1024"
  memory                 = "2048"
  execution_role_arn     = aws_iam_role.ecs_execution.arn
  task_role_arn          = aws_iam_role.ecs_task.arn
  
  container_definitions = jsonencode([
    {
      name  = "backend"
      image = "${var.ecr_repository}/nexus-backend:${var.image_tag}"
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      
      environment = [
        { name = "DB_HOST", value = aws_db_instance.nexus.address },
        { name = "DB_PORT", value = "5432" },
        { name = "DB_NAME", value = "nexus_arbitrage" },
        { name = "DB_USER", value = var.db_username },
        { name = "REDIS_HOST", value = aws_elasticache_cluster.nexus.cache_nodes[0].address },
        { name = "REDIS_PORT", value = "6379" },
        { name = "NEXUS_ENV", value = "production" },
        { name = "NEXUS_DEBUG", value = "false" }
      ]
      
      secrets = [
        {
          name      = "DB_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.nexus_db_password.arn}:password::"
        },
        {
          name      = "REDIS_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.nexus_redis_password.arn}:password::"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/nexus-backend"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }
      
      healthCheck = {
        command = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval = 30
        timeout = 5
        retries = 3
      }
    }
  ])
}

# Application Load Balancer
resource "aws_lb" "nexus" {
  name               = "nexus-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.nexus_alb.id]
  subnets           = aws_subnet.nexus_public[*].id
  
  tags = {
    Name = "nexus-alb"
  }
}

# ECS Service
resource "aws_ecs_service" "nexus_backend" {
  name            = "nexus-backend"
  cluster         = aws_ecs_cluster.nexus.id
  task_definition = aws_ecs_task_definition.nexus_backend.arn
  desired_count   = 3
  launch_type     = "FARGATE"
  
  network_configuration {
    security_groups  = [aws_security_group.nexus_ecs.id]
    subnets          = aws_subnet.nexus_private[*].id
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.nexus_backend.arn
    container_name   = "backend"
    container_port   = 8000
  }
  
  deployment_controller {
    type = "ECS"
  }
  
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}
```

---

## Déploiement Azure

### Architecture Azure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Azure Front Door                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Application Gateway                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  Azure Container│           │  Azure Container│           │  Azure Container│
│   Apps        │           │   Apps        │           │   Apps        │
│   Backend     │           │   WebSocket   │           │   Frontend    │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Azure Cache for Redis                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Azure Database for PostgreSQL                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Terraform Azure

```hcl
# providers.tf
provider "azurerm" {
  features {}
}

# Resource Group
resource "azurerm_resource_group" "nexus" {
  name     = "nexus-trading"
  location = var.azure_location
}

# PostgreSQL
resource "azurerm_postgresql_flexible_server" "nexus" {
  name                   = "nexus-database"
  resource_group_name    = azurerm_resource_group.nexus.name
  location              = azurerm_resource_group.nexus.location
  version               = "14"
  administrator_login   = var.db_username
  administrator_password = var.db_password
  
  sku_name = "B_Standard_B1ms"
  
  storage_mb = 102400
  
  backup_retention_days = 30
  
  tags = {
    environment = "production"
  }
}

# Redis Cache
resource "azurerm_redis_cache" "nexus" {
  name                = "nexus-redis"
  location            = azurerm_resource_group.nexus.location
  resource_group_name = azurerm_resource_group.nexus.name
  capacity            = 1
  family              = "C"
  sku_name            = "Standard"
  
  redis_configuration {
    maxmemory_reserved = 50
    maxmemory_delta   = 20
  }
}

# Container Registry
resource "azurerm_container_registry" "nexus" {
  name                = "nexustrading"
  resource_group_name = azurerm_resource_group.nexus.name
  location            = azurerm_resource_group.nexus.location
  sku                 = "Premium"
  admin_enabled       = true
  
  georeplications {
    location = "westeurope"
  }
}

# Container App Environment
resource "azurerm_container_app_environment" "nexus" {
  name                = "nexus-env"
  resource_group_name = azurerm_resource_group.nexus.name
  location            = azurerm_resource_group.nexus.location
  
  log_analytics_workspace_id = azurerm_log_analytics_workspace.nexus.id
}

# Container App - Backend
resource "azurerm_container_app" "nexus_backend" {
  name                = "nexus-backend"
  container_app_environment_id = azurerm_container_app_environment.nexus.id
  resource_group_name = azurerm_resource_group.nexus.name
  revision_mode       = "Single"
  
  template {
    container {
      name   = "backend"
      image  = "${azurerm_container_registry.nexus.login_server}/nexus-backend:latest"
      cpu    = 0.5
      memory = "1Gi"
      
      env {
        name  = "DB_HOST"
        value = azurerm_postgresql_flexible_server.nexus.fqdn
      }
      
      env {
        name  = "DB_NAME"
        value = "nexus_arbitrage"
      }
      
      env {
        name  = "DB_USER"
        value = var.db_username
      }
      
      env {
        name  = "REDIS_HOST"
        value = azurerm_redis_cache.nexus.hostname
      }
      
      env {
        name  = "REDIS_PORT"
        value = "6379"
      }
      
      env {
        name  = "NEXUS_ENV"
        value = "production"
      }
      
      env {
        name  = "NEXUS_DEBUG"
        value = "false"
      }
    }
  }
  
  ingress {
    target_port = 8000
    external_enabled = true
    
    traffic_weight {
      latest_revision = true
      weight          = 100
    }
  }
}
```

---

## Déploiement GCP

### Architecture GCP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Cloud CDN                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Load Balancer                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  Google Cloud │           │  Google Cloud │           │  Google Cloud │
│   Run         │           │   Run         │           │   Run         │
│   Backend     │           │   WebSocket   │           │   Frontend    │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Memorystore (Redis)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Cloud SQL (PostgreSQL)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Terraform GCP

```hcl
# providers.tf
provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
}

# VPC
resource "google_compute_network" "nexus" {
  name                    = "nexus-vpc"
  auto_create_subnetworks = false
}

# Subnets
resource "google_compute_subnetwork" "nexus" {
  name          = "nexus-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.nexus.id
}

# Cloud SQL
resource "google_sql_database_instance" "nexus" {
  name             = "nexus-database"
  database_version = "POSTGRES_14"
  region           = var.gcp_region
  
  settings {
    tier              = "db-custom-2-7680"
    disk_size         = 100
    disk_autoresize   = true
    disk_type         = "PD_SSD"
    
    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }
    
    ip_configuration {
      ipv4_enabled    = true
      private_network = google_compute_network.nexus.id
      
      authorized_networks {
        name  = "allow-all"
        value = "0.0.0.0/0"
      }
    }
  }
}

# Memorystore Redis
resource "google_redis_instance" "nexus" {
  name           = "nexus-redis"
  tier           = "STANDARD_HA"
  memory_size_gb = 5
  region         = var.gcp_region
  
  redis_configs = {
    maxmemory-policy = "allkeys-lru"
  }
}

# Cloud Run - Backend
resource "google_cloud_run_service" "nexus_backend" {
  name     = "nexus-backend"
  location = var.gcp_region
  
  template {
    spec {
      containers {
        image = "gcr.io/${var.gcp_project}/nexus-backend:latest"
        
        ports {
          container_port = 8000
        }
        
        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }
        
        env {
          name  = "DB_HOST"
          value = google_sql_database_instance.nexus.public_ip_address
        }
        
        env {
          name  = "DB_NAME"
          value = "nexus_arbitrage"
        }
        
        env {
          name  = "DB_USER"
          value = var.db_username
        }
        
        env {
          name  = "REDIS_HOST"
          value = google_redis_instance.nexus.host
        }
        
        env {
          name  = "REDIS_PORT"
          value = "6379"
        }
        
        env {
          name  = "NEXUS_ENV"
          value = "production"
        }
        
        env {
          name  = "NEXUS_DEBUG"
          value = "false"
        }
        
        env {
          name  = "DB_PASSWORD"
          value = var.db_password
        }
      }
    }
  }
  
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Cloud Run IAM
resource "google_cloud_run_service_iam_member" "nexus_backend" {
  service  = google_cloud_run_service.nexus_backend.name
  location = google_cloud_run_service.nexus_backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
```

---

## Configuration Multi-Cloud

### Terraform Multi-Cloud

```hcl
# main.tf
terraform {
  required_version = ">= 1.0"
  
  backend "s3" {
    bucket = "nexus-terraform-state"
    key    = "multi-cloud/terraform.tfstate"
    region = "eu-west-1"
  }
}

# AWS Provider
provider "aws" {
  region = var.aws_region
  alias  = "aws"
}

# Azure Provider
provider "azurerm" {
  features {}
  alias = "azure"
}

# GCP Provider
provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
  alias   = "gcp"
}

# Route53 DNS
resource "aws_route53_zone" "nexus" {
  name = "nexustradingia.com"
}

# DNS Records
resource "aws_route53_record" "nexus" {
  zone_id = aws_route53_zone.nexus.zone_id
  name    = "api.nexustradingia.com"
  type    = "A"
  
  alias {
    name                   = var.primary_alb_dns
    zone_id                = var.primary_alb_zone_id
    evaluate_target_health = true
  }
}

# Health Checks
resource "aws_route53_health_check" "nexus" {
  fqdn              = "api.nexustradingia.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30
}
```

---

## Monitoring et Logging

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'nexus-backend'
    static_configs:
      - targets: ['nexus-backend:8000']
    metrics_path: '/metrics'
    
  - job_name: 'nexus-websocket'
    static_configs:
      - targets: ['nexus-websocket:8001']
    
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
    
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### Grafana Dashboards

```json
{
  "dashboard": {
    "id": 1,
    "title": "NEXUS Trading Dashboard",
    "panels": [
      {
        "title": "PNL Evolution",
        "type": "graph",
        "targets": [
          {
            "expr": "nexus_trades_pnl_total",
            "legendFormat": "Total PNL"
          }
        ]
      },
      {
        "title": "Trade Volume",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(nexus_trades_total[5m])",
            "legendFormat": "Trades/min"
          }
        ]
      },
      {
        "title": "System Health",
        "type": "stat",
        "targets": [
          {
            "expr": "nexus_health_status",
            "legendFormat": "Status"
          }
        ]
      }
    ]
  }
}
```

---

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        run: |
          pytest --cov=trading --cov-report=html
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker images
        run: |
          docker build -t nexus-backend -f deployments/docker/backend/Dockerfile .
          docker build -t nexus-frontend -f deployments/docker/frontend/Dockerfile .
      
      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      - name: Push images
        run: |
          docker tag nexus-backend ${{ secrets.DOCKER_USERNAME }}/nexus-backend:latest
          docker tag nexus-frontend ${{ secrets.DOCKER_USERNAME }}/nexus-frontend:latest
          docker push ${{ secrets.DOCKER_USERNAME }}/nexus-backend:latest
          docker push ${{ secrets.DOCKER_USERNAME }}/nexus-frontend:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Kubernetes
        uses: azure/setup-kubectl@v3
        with:
          version: 'latest'
      
      - name: Set up kubeconfig
        run: |
          mkdir -p $HOME/.kube
          echo "${{ secrets.KUBE_CONFIG }}" > $HOME/.kube/config
      
      - name: Deploy
        run: |
          kubectl set image deployment/nexus-backend backend=${{ secrets.DOCKER_USERNAME }}/nexus-backend:latest -n nexus
          kubectl set image deployment/nexus-frontend frontend=${{ secrets.DOCKER_USERNAME }}/nexus-frontend:latest -n nexus
          kubectl rollout status deployment/nexus-backend -n nexus
          kubectl rollout status deployment/nexus-frontend -n nexus
```

---

## Sécurité

### SSL/TLS Configuration

```bash
# Generate SSL certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/nexus.key \
  -out /etc/ssl/certs/nexus.crt \
  -subj "/C=GB/ST=London/L=London/O=NEXUS/CN=nexustradingia.com"

# Generate DH parameters
openssl dhparam -out /etc/ssl/private/dhparam.pem 2048
```

### Network Security

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: nexus-network-policy
  namespace: nexus
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: nexus
    ports:
    - protocol: TCP
      port: 8000
    - protocol: TCP
      port: 8001
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53
    - protocol: UDP
      port: 53
```

---

## Backup et Recovery

### Database Backup

```bash
# Backup script
#!/bin/bash
BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/nexus_$DATE.sql.gz"

# Create backup
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | gzip > $BACKUP_FILE

# Upload to S3
aws s3 cp $BACKUP_FILE s3://$BACKUP_BUCKET/postgres/

# Delete old backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### Disaster Recovery

```yaml
# dr.yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: nexus-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"
  template:
    includedNamespaces:
    - nexus
    ttl: 720h
    storageLocation: default
    volumeSnapshotLocations:
    - default
```

---

## Maintenance

### Health Checks

```bash
#!/bin/bash
# healthcheck.sh

# Check API
curl -f http://localhost:8000/health || exit 1

# Check WebSocket
curl -f http://localhost:8001/health || exit 1

# Check Database
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1" || exit 1

# Check Redis
redis-cli -h $REDIS_HOST ping || exit 1

echo "All services are healthy"
```

### Rollback Procedure

```bash
# Kubernetes rollback
kubectl rollout undo deployment/nexus-backend -n nexus

# Docker rollback
docker-compose down
docker-compose up -d

# Database rollback
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f /backups/nexus_rollback.sql
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Database connection failed | Check DB_HOST, DB_USER, DB_PASSWORD |
| Redis connection failed | Check REDIS_HOST, REDIS_PASSWORD |
| API not responding | Check logs: `kubectl logs -f deployment/nexus-backend` |
| WebSocket disconnections | Check network policies and firewall |
| High latency | Scale up replicas: `kubectl scale deployment nexus-backend --replicas=5` |
| Memory leak | Check metrics: `kubectl top pods -n nexus` |

### Debug Commands

```bash
# Get pod logs
kubectl logs -f deployment/nexus-backend -n nexus

# Get pod details
kubectl describe pod <pod-name> -n nexus

# Get events
kubectl get events -n nexus --sort-by='.lastTimestamp'

# Port forwarding
kubectl port-forward deployment/nexus-backend 8000:8000 -n nexus

# Execute command in pod
kubectl exec -it <pod-name> -n nexus -- /bin/bash

# Get resource usage
kubectl top pods -n nexus
kubectl top nodes
```

### Support Contacts

- **Technical Support**: support@nexustradingia.com
- **Emergency**: emergency@nexustradingia.com
- **Discord**: [Nexus Trading IA](https://discord.gg/nexustradingia)
- **Telegram**: [@NexusTradingIA](https://t.me/NexusTradingIA)

---

*© 2026 NEXUS QUANTUM LTD - Tous droits réservés*

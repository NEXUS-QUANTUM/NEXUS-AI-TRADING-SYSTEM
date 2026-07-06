# ============================================
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD
# CEO: Dr X... - Majority Shareholder
# ============================================
# Makefile - Commandes pour le développement
# ============================================

# ============================================
# VARIABLES
# ============================================
PYTHON := python3
PIP := pip
DOCKER := docker
DOCKER_COMPOSE := docker-compose
NPM := npm
YARN := yarn
POETRY := poetry
BLACK := black
ISORT := isort
FLAKE8 := flake8
MYPY := mypy
PRETTIER := prettier
ESLINT := eslint
PYTEST := pytest

PROJECT_NAME := NEXUS-AI-TRADING-SYSTEM
PROJECT_VERSION := 1.0.0
DOCKER_IMAGE := nexus-ai-trading
DOCKER_TAG := latest

# ============================================
# COULEURS
# ============================================
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
BLUE := \033[0;34m
PURPLE := \033[0;35m
CYAN := \033[0;36m
NC := \033[0m

# ============================================
# HELP
# ============================================
.PHONY: help
help: ## Affiche cette aide
	@printf "${CYAN}"
	@echo "════════════════════════════════════════════════════════════════════════════════"
	@echo "  NEXUS AI TRADING SYSTEM - Makefile Commands"
	@echo "  Version: ${PROJECT_VERSION}"
	@echo "════════════════════════════════════════════════════════════════════════════════"
	@printf "${NC}"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "${GREEN}%-30s${NC} %s\n", $$1, $$2}'
	@printf "\n"

# ============================================
# INITIALISATION
# ============================================
.PHONY: init
init: ## Initialise le projet
	@printf "${CYAN}🚀 Initialisation du projet...${NC}\n"
	./init_project.sh
	@printf "${GREEN}✅ Projet initialisé${NC}\n"

.PHONY: setup
setup: ## Configure l'environnement
	@printf "${CYAN}🔧 Configuration de l'environnement...${NC}\n"
	@if [ ! -f .env ]; then cp .env.example .env; fi
	@printf "${GREEN}✅ Environnement configuré${NC}\n"

# ============================================
# DOCKER
# ============================================
.PHONY: docker-build
docker-build: ## Construit les images Docker
	@printf "${CYAN}🐳 Construction des images Docker...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml build
	@printf "${GREEN}✅ Images construites${NC}\n"

.PHONY: docker-up
docker-up: ## Démarre les services Docker
	@printf "${CYAN}🐳 Démarrage des services...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml up -d
	@printf "${GREEN}✅ Services démarrés${NC}\n"

.PHONY: docker-down
docker-down: ## Arrête les services Docker
	@printf "${CYAN}🐳 Arrêt des services...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml down
	@printf "${GREEN}✅ Services arrêtés${NC}\n"

.PHONY: docker-logs
docker-logs: ## Affiche les logs Docker
	@printf "${CYAN}🐳 Logs Docker...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml logs -f

.PHONY: docker-clean
docker-clean: ## Nettoie les conteneurs Docker
	@printf "${CYAN}🐳 Nettoyage Docker...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml down -v --rmi all
	@printf "${GREEN}✅ Nettoyage terminé${NC}\n"

.PHONY: docker-restart
docker-restart: docker-down docker-up ## Redémarre les services Docker

.PHONY: docker-ps
docker-ps: ## Liste les conteneurs Docker
	@printf "${CYAN}🐳 Conteneurs en cours...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml ps

.PHONY: docker-shell
docker-shell: ## Ouvre un shell dans le conteneur backend
	@printf "${CYAN}🐳 Shell Docker...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml exec backend /bin/bash

# ============================================
# BACKEND
# ============================================
.PHONY: backend-install
backend-install: ## Installe les dépendances backend
	@printf "${CYAN}📦 Installation des dépendances Python...${NC}\n"
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	@printf "${GREEN}✅ Dépendances installées${NC}\n"

.PHONY: backend-run
backend-run: ## Lance le serveur backend
	@printf "${CYAN}🚀 Lancement du serveur backend...${NC}\n"
	$(PYTHON) backend/main.py

.PHONY: backend-dev
backend-dev: ## Lance le serveur backend en mode développement
	@printf "${CYAN}🚀 Lancement du serveur backend (dev)...${NC}\n"
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: backend-test
backend-test: ## Exécute les tests backend
	@printf "${CYAN}🧪 Exécution des tests backend...${NC}\n"
	$(PYTEST) -v --cov=backend --cov-report=html

.PHONY: backend-lint
backend-lint: ## Lint le code backend
	@printf "${CYAN}🔍 Linting backend...${NC}\n"
	$(FLAKE8) backend/
	$(MYPY) backend/
	@printf "${GREEN}✅ Linting terminé${NC}\n"

.PHONY: backend-format
backend-format: ## Formate le code backend
	@printf "${CYAN}🎨 Formatage du code backend...${NC}\n"
	$(BLACK) backend/
	$(ISORT) backend/
	@printf "${GREEN}✅ Formatage terminé${NC}\n"

.PHONY: backend-migrate
backend-migrate: ## Exécute les migrations
	@printf "${CYAN}📊 Migration de la base de données...${NC}\n"
	alembic upgrade head
	@printf "${GREEN}✅ Migration terminée${NC}\n"

.PHONY: backend-migrate-make
backend-migrate-make: ## Crée une nouvelle migration
	@printf "${CYAN}📊 Création d'une migration...${NC}\n"
	alembic revision --autogenerate
	@printf "${GREEN}✅ Migration créée${NC}\n"

.PHONY: backend-shell
backend-shell: ## Ouvre un shell Python
	@printf "${CYAN}🐍 Shell Python...${NC}\n"
	$(PYTHON) -c "import IPython; IPython.terminal.ipapp.launch_new_instance()"

# ============================================
# FRONTEND
# ============================================
.PHONY: frontend-install
frontend-install: ## Installe les dépendances frontend
	@printf "${CYAN}📦 Installation des dépendances Node.js...${NC}\n"
	cd apps/web && $(NPM) install
	@printf "${GREEN}✅ Dépendances installées${NC}\n"

.PHONY: frontend-dev
frontend-dev: ## Lance le serveur frontend en développement
	@printf "${CYAN}🚀 Lancement du serveur frontend...${NC}\n"
	cd apps/web && $(NPM) run dev

.PHONY: frontend-build
frontend-build: ## Construit le frontend
	@printf "${CYAN}🔨 Build du frontend...${NC}\n"
	cd apps/web && $(NPM) run build
	@printf "${GREEN}✅ Build terminé${NC}\n"

.PHONY: frontend-test
frontend-test: ## Exécute les tests frontend
	@printf "${CYAN}🧪 Tests frontend...${NC}\n"
	cd apps/web && $(NPM) run test

.PHONY: frontend-lint
frontend-lint: ## Lint le frontend
	@printf "${CYAN}🔍 Linting frontend...${NC}\n"
	cd apps/web && $(ESLINT) .
	@printf "${GREEN}✅ Linting terminé${NC}\n"

.PHONY: frontend-format
frontend-format: ## Formate le frontend
	@printf "${CYAN}🎨 Formatage du frontend...${NC}\n"
	cd apps/web && $(PRETTIER) --write .
	@printf "${GREEN}✅ Formatage terminé${NC}\n"

# ============================================
# AI
# ============================================
.PHONY: ai-train
ai-train: ## Entraîne les modèles IA
	@printf "${CYAN}🧠 Entraînement des modèles IA...${NC}\n"
	$(PYTHON) ai/training/trainer.py
	@printf "${GREEN}✅ Entraînement terminé${NC}\n"

.PHONY: ai-predict
ai-predict: ## Exécute les prédictions IA
	@printf "${CYAN}🧠 Prédictions IA...${NC}\n"
	$(PYTHON) ai/prediction/predictor.py
	@printf "${GREEN}✅ Prédictions terminées${NC}\n"

.PHONY: ai-test
ai-test: ## Teste les modèles IA
	@printf "${CYAN}🧪 Tests IA...${NC}\n"
	$(PYTEST) ai/tests/
	@printf "${GREEN}✅ Tests terminés${NC}\n"

# ============================================
# TRADING
# ============================================
.PHONY: trading-backtest
trading-backtest: ## Exécute un backtest
	@printf "${CYAN}📊 Backtest...${NC}\n"
	$(PYTHON) trading/backtesting/backtest_engine.py
	@printf "${GREEN}✅ Backtest terminé${NC}\n"

.PHONY: trading-paper
trading-paper: ## Lance le paper trading
	@printf "${CYAN}📊 Paper trading...${NC}\n"
	$(PYTHON) trading/paper-trading/paper_engine.py
	@printf "${GREEN}✅ Paper trading démarré${NC}\n"

# ============================================
# TESTS
# ============================================
.PHONY: test
test: backend-test frontend-test ai-test ## Exécute tous les tests
	@printf "${GREEN}✅ Tous les tests exécutés${NC}\n"

.PHONY: test-integration
test-integration: ## Exécute les tests d'intégration
	@printf "${CYAN}🧪 Tests d'intégration...${NC}\n"
	$(PYTEST) tests/integration/ -v
	@printf "${GREEN}✅ Tests d'intégration terminés${NC}\n"

.PHONY: test-e2e
test-e2e: ## Exécute les tests end-to-end
	@printf "${CYAN}🧪 Tests E2E...${NC}\n"
	cd apps/web && $(NPM) run test:e2e
	@printf "${GREEN}✅ Tests E2E terminés${NC}\n"

.PHONY: test-coverage
test-coverage: ## Génère le rapport de couverture
	@printf "${CYAN}📊 Couverture des tests...${NC}\n"
	$(PYTEST) --cov=backend --cov-report=html
	cd apps/web && $(NPM) run test:coverage
	@printf "${GREEN}✅ Rapport de couverture généré${NC}\n"

# ============================================
# FORMATAGE & LINTING
# ============================================
.PHONY: format
format: backend-format frontend-format ## Formate tout le code
	@printf "${GREEN}✅ Code formaté${NC}\n"

.PHONY: lint
lint: backend-lint frontend-lint ## Lint tout le code
	@printf "${GREEN}✅ Linting terminé${NC}\n"

.PHONY: check
check: format lint test ## Vérifie tout le code
	@printf "${GREEN}✅ Toutes les vérifications sont passées${NC}\n"

# ============================================
# BASE DE DONNÉES
# ============================================
.PHONY: db-reset
db-reset: ## Réinitialise la base de données
	@printf "${CYAN}📊 Réinitialisation de la base de données...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml down postgres
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml up -d postgres
	sleep 5
	$(MAKE) backend-migrate
	@printf "${GREEN}✅ Base de données réinitialisée${NC}\n"

.PHONY: db-seed
db-seed: ## Remplit la base de données avec des données de test
	@printf "${CYAN}📊 Seed de la base de données...${NC}\n"
	$(PYTHON) backend/database/seeders/main_seeder.py
	@printf "${GREEN}✅ Seed terminé${NC}\n"

.PHONY: db-backup
db-backup: ## Sauvegarde la base de données
	@printf "${CYAN}📊 Sauvegarde de la base de données...${NC}\n"
	$(DOCKER) exec -t postgres pg_dump -U nexus nexus_ai > backup_$$(date +%Y%m%d_%H%M%S).sql
	@printf "${GREEN}✅ Sauvegarde terminée${NC}\n"

# ============================================
# CLEAN
# ============================================
.PHONY: clean
clean: ## Nettoie les fichiers temporaires
	@printf "${CYAN}🧹 Nettoyage des fichiers temporaires...${NC}\n"
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf .next node_modules dist build
	rm -rf *.pyc *.pyo
	rm -rf .coverage coverage.xml htmlcov
	rm -rf .vscode-test
	@printf "${GREEN}✅ Nettoyage terminé${NC}\n"

.PHONY: clean-all
clean-all: clean docker-clean ## Nettoie tout
	@printf "${CYAN}🧹 Nettoyage complet...${NC}\n"
	rm -rf venv .venv
	rm -rf .cache
	rm -rf data/cache data/logs data/models
	@printf "${GREEN}✅ Nettoyage complet terminé${NC}\n"

# ============================================
# SERVICES
# ============================================
.PHONY: start
start: ## Démarre tous les services
	@printf "${CYAN}🚀 Démarrage des services...${NC}\n"
	./start_nexus.sh
	@printf "${GREEN}✅ Services démarrés${NC}\n"

.PHONY: stop
stop: ## Arrête tous les services
	@printf "${CYAN}🛑 Arrêt des services...${NC}\n"
	./stop_nexus.sh
	@printf "${GREEN}✅ Services arrêtés${NC}\n"

.PHONY: restart
restart: stop start ## Redémarre tous les services
	@printf "${GREEN}✅ Services redémarrés${NC}\n"

.PHONY: status
status: ## Vérifie le statut des services
	@printf "${CYAN}📊 Statut des services...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml ps
	@printf "\n"
	@printf "${CYAN}🌐 Services:${NC}\n"
	@printf "  🔌 API:          http://localhost:8000\n"
	@printf "  📝 API Docs:     http://localhost:8000/docs\n"
	@printf "  📊 Dashboard:    http://localhost:3000\n"
	@printf "  📈 Monitoring:   http://localhost:3001\n"
	@printf "  📊 Grafana:      http://localhost:3001\n"
	@printf "  📈 Prometheus:   http://localhost:9090\n"
	@printf "  🐘 PostgreSQL:   localhost:5432\n"
	@printf "  🚀 Redis:        localhost:6379\n"

# ============================================
# GIT
# ============================================
.PHONY: git-push
git-push: ## Push vers GitHub
	@printf "${CYAN}📤 Push vers GitHub...${NC}\n"
	git add .
	git status
	@printf "${YELLOW}Voulez-vous committer ? (y/N)${NC} "
	read -r answer; \
	if [ "$$answer" = "y" ] || [ "$$answer" = "Y" ]; then \
		read -p "Message de commit: " msg; \
		git commit -m "$$msg"; \
		git push origin main; \
	fi
	@printf "${GREEN}✅ Push terminé${NC}\n"

# ============================================
# PRODUCTION
# ============================================
.PHONY: prod-build
prod-build: ## Construit pour la production
	@printf "${CYAN}🔨 Build de production...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml build
	@printf "${GREEN}✅ Build terminé${NC}\n"

.PHONY: prod-up
prod-up: ## Démarre la production
	@printf "${CYAN}🚀 Démarrage de la production...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml up -d
	@printf "${GREEN}✅ Production démarrée${NC}\n"

.PHONY: prod-down
prod-down: ## Arrête la production
	@printf "${CYAN}🛑 Arrêt de la production...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml down
	@printf "${GREEN}✅ Production arrêtée${NC}\n"

# ============================================
# MONITORING
# ============================================
.PHONY: monitoring-up
monitoring-up: ## Démarre le monitoring
	@printf "${CYAN}📊 Démarrage du monitoring...${NC}\n"
	$(DOCKER_COMPOSE) -f configs/monitoring/docker-compose.monitoring.yml up -d
	@printf "${GREEN}✅ Monitoring démarré${NC}\n"

.PHONY: monitoring-down
monitoring-down: ## Arrête le monitoring
	@printf "${CYAN}📊 Arrêt du monitoring...${NC}\n"
	$(DOCKER_COMPOSE) -f configs/monitoring/docker-compose.monitoring.yml down
	@printf "${GREEN}✅ Monitoring arrêté${NC}\n"

# ============================================
# KUBERNETES
# ============================================
.PHONY: k8s-deploy
k8s-deploy: ## Déploie sur Kubernetes
	@printf "${CYAN}☸️ Déploiement Kubernetes...${NC}\n"
	kubectl apply -f deployments/production/k8s/
	@printf "${GREEN}✅ Déploiement terminé${NC}\n"

.PHONY: k8s-delete
k8s-delete: ## Supprime le déploiement Kubernetes
	@printf "${CYAN}☸️ Suppression du déploiement...${NC}\n"
	kubectl delete -f deployments/production/k8s/
	@printf "${GREEN}✅ Suppression terminée${NC}\n"

# ============================================
# CERTIFICATS SSL
# ============================================
.PHONY: ssl-generate
ssl-generate: ## Génère les certificats SSL
	@printf "${CYAN}🔒 Génération des certificats SSL...${NC}\n"
	./infrastructure/nginx/ssl/generate-ssl.sh
	@printf "${GREEN}✅ Certificats générés${NC}\n"

# ============================================
# LOGS
# ============================================
.PHONY: logs
logs: ## Affiche les logs de tous les services
	@printf "${CYAN}📋 Logs des services...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml logs -f

.PHONY: logs-backend
logs-backend: ## Affiche les logs du backend
	@printf "${CYAN}📋 Logs du backend...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml logs -f backend

.PHONY: logs-frontend
logs-frontend: ## Affiche les logs du frontend
	@printf "${CYAN}📋 Logs du frontend...${NC}\n"
	$(DOCKER_COMPOSE) -f docker-compose.dev.yml logs -f frontend

# ============================================
# DOCUMENTATION
# ============================================
.PHONY: docs-build
docs-build: ## Construit la documentation
	@printf "${CYAN}📚 Construction de la documentation...${NC}\n"
	cd docs && mkdocs build
	@printf "${GREEN}✅ Documentation construite${NC}\n"

.PHONY: docs-serve
docs-serve: ## Lance le serveur de documentation
	@printf "${CYAN}📚 Lancement du serveur de documentation...${NC}\n"
	cd docs && mkdocs serve

# ============================================
# RELEASE
# ============================================
.PHONY: release
release: ## Crée une nouvelle release
	@printf "${CYAN}📦 Création de la release...${NC}\n"
	@read -p "Version (ex: 1.0.0): " version; \
	read -p "Message de release: " msg; \
	git tag -a "v$$version" -m "$$msg"; \
	git push origin "v$$version"; \
	gh release create "v$$version" --title "Release v$$version" --notes "$$msg"
	@printf "${GREEN}✅ Release créée${NC}\n"

# ============================================
# BUILD ALL
# ============================================
.PHONY: build-all
build-all: ## Construit tout le projet
	@printf "${CYAN}🔨 Build du projet complet...${NC}\n"
	$(MAKE) docker-build
	$(MAKE) frontend-build
	@printf "${GREEN}✅ Build terminé${NC}\n"

# ============================================
# DEV ALL
# ============================================
.PHONY: dev-all
dev-all: ## Lance tout en mode développement
	@printf "${CYAN}🚀 Lancement en mode développement...${NC}\n"
	$(MAKE) docker-up
	$(MAKE) backend-dev &
	$(MAKE) frontend-dev &
	@printf "${GREEN}✅ Services démarrés${NC}\n"

# ============================================
# DEFAULT
# ============================================
.DEFAULT_GOAL := help

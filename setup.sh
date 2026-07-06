#!/bin/bash
# ============================================
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD
# CEO: Dr X... - Majority Shareholder
# ============================================
# Script de configuration du projet
# ============================================

set -e

# ============================================
# COULEURS
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# ============================================
# VARIABLES
# ============================================
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${PROJECT_ROOT}/setup.log"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_DIR="${HOME}/nexus_backup_${TIMESTAMP}"

# ============================================
# BANNIÈRE
# ============================================
show_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                  ║"
    echo "║   ███████╗███████╗████████╗██╗   ██╗██████╗                                     ║"
    echo "║   ██╔════╝██╔════╝╚══██╔══╝██║   ██║██╔══██╗                                    ║"
    echo "║   ███████╗█████╗     ██║   ██║   ██║██████╔╝                                    ║"
    echo "║   ╚════██║██╔══╝     ██║   ██║   ██║██╔═══╝                                     ║"
    echo "║   ███████║███████╗   ██║   ╚██████╔╝██║                                         ║"
    echo "║   ╚══════╝╚══════╝   ╚═╝    ╚═════╝ ╚═╝                                         ║"
    echo "║                                                                                  ║"
    echo "║                    NEXUS AI TRADING SYSTEM                                        ║"
    echo "║                    Copyright © 2026 NEXUS QUANTUM LTD                             ║"
    echo "║                    CEO: Dr X... - Majority Shareholder                            ║"
    echo "║                                                                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ============================================
# FONCTIONS
# ============================================
log() {
    echo -e "${GREEN}[✓]${NC} $1"
    echo "[✓] $1" >> "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    echo "[✗] $1" >> "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[ℹ]${NC} $1"
    echo "[ℹ] $1" >> "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
    echo "[⚠] $1" >> "$LOG_FILE"
}

log_section() {
    echo -e "\n${PURPLE}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}  $1${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════════════════════════════════════${NC}\n"
    echo "$1" >> "$LOG_FILE"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 n'est pas installé"
        return 1
    else
        log "$1 installé: $(command -v $1)"
        return 0
    fi
}

create_backup() {
    if [ -d "$1" ]; then
        log_info "Création d'une sauvegarde de $1..."
        mkdir -p "$BACKUP_DIR"
        cp -r "$1" "$BACKUP_DIR/"
        log "Sauvegarde créée dans $BACKUP_DIR"
    fi
}

# ============================================
# VÉRIFICATION DES PRÉREQUIS
# ============================================
check_prerequisites() {
    log_section "📋 VÉRIFICATION DES PRÉREQUIS"
    
    local missing=0
    
    # Python
    if ! check_command python3; then
        missing=$((missing+1))
    else
        log "Python version: $(python3 --version)"
    fi
    
    # PIP
    if ! check_command pip3; then
        missing=$((missing+1))
    else
        log "PIP version: $(pip3 --version)"
    fi
    
    # Docker
    if ! check_command docker; then
        missing=$((missing+1))
    else
        log "Docker version: $(docker --version)"
    fi
    
    # Docker Compose
    if ! check_command docker-compose; then
        missing=$((missing+1))
    else
        log "Docker Compose version: $(docker-compose --version)"
    fi
    
    # Node
    if ! check_command node; then
        missing=$((missing+1))
    else
        log "Node version: $(node --version)"
    fi
    
    # NPM
    if ! check_command npm; then
        missing=$((missing+1))
    else
        log "NPM version: $(npm --version)"
    fi
    
    # Git
    if ! check_command git; then
        missing=$((missing+1))
    else
        log "Git version: $(git --version)"
    fi
    
    # Make
    if ! check_command make; then
        missing=$((missing+1))
    else
        log "Make version: $(make --version)"
    fi
    
    # Curl
    if ! check_command curl; then
        missing=$((missing+1))
    else
        log "Curl version: $(curl --version | head -1)"
    fi
    
    # Wget
    if ! check_command wget; then
        missing=$((missing+1))
    else
        log "Wget version: $(wget --version | head -1)"
    fi
    
    if [ $missing -gt 0 ]; then
        log_error "$missing prérequis manquants. Veuillez les installer avant de continuer."
        exit 1
    fi
    
    log "✅ Tous les prérequis sont satisfaits"
}

# ============================================
# CONFIGURATION DE L'ENVIRONNEMENT
# ============================================
setup_environment() {
    log_section "⚙️ CONFIGURATION DE L'ENVIRONNEMENT"
    
    # Fichier .env
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log "Fichier .env créé à partir de .env.example"
        else
            log_warning "Fichier .env.example non trouvé"
        fi
    else
        log_info "Fichier .env existant conservé"
    fi
    
    # Édition du .env si demandé
    echo -e "\n${YELLOW}Voulez-vous éditer le fichier .env maintenant ? (o/N)${NC}"
    read -r answer
    if [[ $answer =~ ^[Oo]$ ]]; then
        ${EDITOR:-nano} .env
        log "Fichier .env édité"
    fi
    
    # Permissions
    log_info "Configuration des permissions..."
    chmod 600 .env 2>/dev/null || log_warning "Impossible de changer les permissions de .env"
    chmod +x *.sh 2>/dev/null || log_warning "Impossible de rendre les scripts exécutables"
    log "Permissions configurées"
    
    # Configuration Git
    log_info "Configuration de Git..."
    git config core.fileMode false
    git config pull.rebase false
    log "Git configuré"
    
    # Configuration des hooks
    if [ -d ".git/hooks" ]; then
        log_info "Installation des hooks Git..."
        cp -r .github/hooks/* .git/hooks/ 2>/dev/null || log_warning "Aucun hook trouvé"
        chmod +x .git/hooks/* 2>/dev/null || log_warning "Impossible de rendre les hooks exécutables"
        log "Hooks Git installés"
    fi
}

# ============================================
# CRÉATION DES DOSSIERS
# ============================================
create_directories() {
    log_section "📁 CRÉATION DES DOSSIERS"
    
    # Dossiers de données
    for d in data/cache data/logs data/models data/market-data data/backups data/snapshots; do
        if [ ! -d "$d" ]; then
            mkdir -p "$d"
            log "Dossier créé: $d"
        else
            log_info "Dossier existe déjà: $d"
        fi
    done
    
    # Dossiers backend
    for d in backend/uploads/avatars backend/uploads/documents backend/uploads/trading backend/logs; do
        if [ ! -d "$d" ]; then
            mkdir -p "$d"
            log "Dossier créé: $d"
        else
            log_info "Dossier existe déjà: $d"
        fi
    done
    
    # Dossiers de logs
    for d in logs/archive; do
        if [ ! -d "$d" ]; then
            mkdir -p "$d"
            log "Dossier créé: $d"
        else
            log_info "Dossier existe déjà: $d"
        fi
    done
    
    # Dossiers de configuration
    for d in configs/development configs/production configs/staging configs/security; do
        if [ ! -d "$d" ]; then
            mkdir -p "$d"
            log "Dossier créé: $d"
        else
            log_info "Dossier existe déjà: $d"
        fi
    done
    
    # Dossiers de tests
    for d in tests/unit tests/integration tests/e2e tests/performance tests/security; do
        if [ ! -d "$d" ]; then
            mkdir -p "$d"
            log "Dossier créé: $d"
        else
            log_info "Dossier existe déjà: $d"
        fi
    done
    
    # Dossiers de scripts
    for d in scripts/backup scripts/deploy scripts/install scripts/migration scripts/monitoring; do
        if [ ! -d "$d" ]; then
            mkdir -p "$d"
            log "Dossier créé: $d"
        else
            log_info "Dossier existe déjà: $d"
        fi
    done
    
    log "✅ Dossiers créés"
}

# ============================================
# INSTALLATION DES DÉPENDANCES
# ============================================
install_dependencies() {
    log_section "📦 INSTALLATION DES DÉPENDANCES"
    
    # Python
    if [ -f "requirements.txt" ]; then
        log_info "Installation des dépendances Python..."
        pip3 install -r requirements.txt
        log "Dépendances Python installées"
    fi
    
    if [ -f "requirements-dev.txt" ]; then
        log_info "Installation des dépendances de développement..."
        pip3 install -r requirements-dev.txt
        log "Dépendances de développement installées"
    fi
    
    # Node
    if [ -d "apps/web" ]; then
        log_info "Installation des dépendances Node.js..."
        cd apps/web
        npm install
        cd ../..
        log "Dépendances Node.js installées"
    fi
    
    # Poetry
    if [ -f "pyproject.toml" ]; then
        if command -v poetry &> /dev/null; then
            log_info "Installation via Poetry..."
            poetry install
            log "Dépendances Poetry installées"
        else
            log_warning "Poetry non installé. Installation manuelle requise."
        fi
    fi
    
    log "✅ Dépendances installées"
}

# ============================================
# INITIALISATION DES BASES DE DONNÉES
# ============================================
setup_databases() {
    log_section "🗄️ INITIALISATION DES BASES DE DONNÉES"
    
    # Docker up
    log_info "Démarrage des conteneurs Docker..."
    docker-compose -f docker-compose.dev.yml up -d postgres timescaledb mongodb redis
    sleep 10
    log "Conteneurs démarrés"
    
    # Attente de PostgreSQL
    log_info "Attente de PostgreSQL..."
    for i in {1..30}; do
        if docker exec -t nexus_postgres_dev pg_isready -U nexus &> /dev/null; then
            log "PostgreSQL est prêt"
            break
        fi
        sleep 2
    done
    
    # Attente de TimescaleDB
    log_info "Attente de TimescaleDB..."
    for i in {1..30}; do
        if docker exec -t nexus_timescaledb_dev pg_isready -U nexus &> /dev/null; then
            log "TimescaleDB est prêt"
            break
        fi
        sleep 2
    done
    
    # Attente de MongoDB
    log_info "Attente de MongoDB..."
    for i in {1..30}; do
        if docker exec -t nexus_mongodb_dev mongosh --eval 'db.runCommand({ping: 1})' &> /dev/null; then
            log "MongoDB est prêt"
            break
        fi
        sleep 2
    done
    
    # Migrations
    log_info "Exécution des migrations..."
    if [ -f "backend/core/database.py" ]; then
        python3 -c "from backend.core.database import init_db; init_db()" 2>/dev/null || log_warning "Erreur lors des migrations"
        log "Migrations exécutées"
    else
        log_warning "Fichier de migration non trouvé"
    fi
    
    # Seed
    if [ -f "backend/database/seeders/main_seeder.py" ]; then
        log_info "Remplissage des données de base..."
        python3 -c "from backend.database.seeders.main_seeder import seed; seed()" 2>/dev/null || log_warning "Erreur lors du seed"
        log "Données de base insérées"
    else
        log_warning "Fichier de seed non trouvé"
    fi
    
    log "✅ Bases de données initialisées"
}

# ============================================
# BUILD FRONTEND
# ============================================
build_frontend() {
    log_section "🔨 BUILD FRONTEND"
    
    if [ -d "apps/web" ]; then
        log_info "Build du frontend..."
        cd apps/web
        if [ -f "package.json" ]; then
            npm run build || log_warning "Erreur lors du build du frontend"
            log "Frontend build terminé"
        else
            log_warning "package.json non trouvé dans apps/web"
        fi
        cd ../..
    else
        log_warning "Dossier apps/web non trouvé"
    fi
    
    log "✅ Frontend build terminé"
}

# ============================================
# VÉRIFICATION FINALE
# ============================================
final_check() {
    log_section "✅ VÉRIFICATION FINALE"
    
    log_info "Vérification des services..."
    docker-compose -f docker-compose.dev.yml ps || log_warning "Erreur lors de la vérification des services"
    
    log_info "Vérification des versions..."
    log "Python: $(python3 --version)"
    log "Node: $(node --version)"
    log "Docker: $(docker --version)"
    log "Docker Compose: $(docker-compose --version)"
    
    log_info "Vérification des endpoints..."
    sleep 5
    curl -s http://localhost:8000/health > /dev/null && log "API: ✅ OK" || log_warning "API: ❌ Non accessible"
    curl -s http://localhost:3000 > /dev/null && log "Frontend: ✅ OK" || log_warning "Frontend: ❌ Non accessible"
    
    log "✅ Vérification terminée"
}

# ============================================
# AFFICHAGE DES INFORMATIONS FINALES
# ============================================
show_final_info() {
    log_section "🚀 INFORMATIONS FINALES"
    
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                  ║"
    echo "║   ✅ CONFIGURATION TERMINÉE AVEC SUCCÈS                                          ║"
    echo "║                                                                                  ║"
    echo "║   📁 Projet: NEXUS AI TRADING SYSTEM                                             ║"
    echo "║   📂 Chemin: $PROJECT_ROOT                                                       ║"
    echo "║                                                                                  ║"
    echo "║   🔗 Services disponibles:                                                       ║"
    echo "║   ├─ 🔌 API:          http://localhost:8000                                     ║"
    echo "║   ├─ 📝 API Docs:     http://localhost:8000/docs                                ║"
    echo "║   ├─ 📊 Frontend:     http://localhost:3000                                     ║"
    echo "║   ├─ 📈 Monitoring:   http://localhost:3001                                     ║"
    echo "║   ├─ 🐘 PostgreSQL:   localhost:5432                                            ║"
    echo "║   ├─ 📈 TimescaleDB:  localhost:5433                                            ║"
    echo "║   ├─ 🍃 MongoDB:      localhost:27017                                           ║"
    echo "║   └─ 🚀 Redis:        localhost:6379                                            ║"
    echo "║                                                                                  ║"
    echo "║   📋 Commandes disponibles:                                                      ║"
    echo "║   ├─ ./start_nexus.sh     → Démarrer les services                               ║"
    echo "║   ├─ ./stop_nexus.sh      → Arrêter les services                                ║"
    echo "║   ├─ make help            → Aide Makefile                                       ║"
    echo "║   └─ source venv/bin/activate → Activer l'environnement Python                  ║"
    echo "║                                                                                  ║"
    echo "║   📚 Documentation: https://docs.nexustradingia.com                              ║"
    echo "║   🔗 GitHub: https://github.com/NEXUS-QUANTUM/NEXUS-AI-TRADING-SYSTEM            ║"
    echo "║                                                                                  ║"
    echo "║   📅 Copyright © 2026 NEXUS QUANTUM LTD                                          ║"
    echo "║   👑 CEO: Dr X... - Majority Shareholder                                         ║"
    echo "║                                                                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "\n${GREEN}🚀 Pour démarrer:${NC}"
    echo -e "  ${YELLOW}cd $PROJECT_ROOT${NC}"
    echo -e "  ${YELLOW}./start_nexus.sh${NC}"
    echo -e "\n${BLUE}📝 Logs: $LOG_FILE${NC}"
}

# ============================================
# MENU PRINCIPAL
# ============================================
main() {
    # Création du dossier de logs
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    
    show_banner
    
    log_info "Démarrage de la configuration à $(date)"
    log_info "Log file: $LOG_FILE"
    
    # Menu interactif
    echo -e "\n${CYAN}Que voulez-vous faire ?${NC}"
    echo "1) Configuration complète (recommandé)"
    echo "2) Vérifier les prérequis seulement"
    echo "3) Configurer l'environnement seulement"
    echo "4) Installer les dépendances seulement"
    echo "5) Initialiser la base de données seulement"
    echo "6) Build le frontend seulement"
    echo "7) Quitter"
    echo ""
    read -p "Votre choix (1-7): " choice
    
    case $choice in
        1)
            check_prerequisites
            setup_environment
            create_directories
            install_dependencies
            setup_databases
            build_frontend
            final_check
            show_final_info
            ;;
        2)
            check_prerequisites
            ;;
        3)
            setup_environment
            create_directories
            ;;
        4)
            install_dependencies
            ;;
        5)
            setup_databases
            ;;
        6)
            build_frontend
            ;;
        7)
            echo -e "${GREEN}Au revoir !${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Choix invalide.${NC}"
            exit 1
            ;;
    esac
    
    echo -e "\n${GREEN}✅ Configuration terminée !${NC}"
    echo -e "${BLUE}📝 Logs disponibles dans: $LOG_FILE${NC}"
}

# ============================================
# EXÉCUTION
# ============================================
main "$@"

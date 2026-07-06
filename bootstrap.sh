#!/bin/bash
# ============================================
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD
# CEO: Dr X... - Majority Shareholder
# ============================================
# Script de bootstrap - Installation complète
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
PROJECT_NAME="NEXUS-AI-TRADING-SYSTEM"
PROJECT_PATH="${HOME}/${PROJECT_NAME}"
LOG_FILE="${PROJECT_PATH}/bootstrap.log"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_DIR="${HOME}/nexus_backup_${TIMESTAMP}"

# ============================================
# BANNIÈRE
# ============================================
show_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                   ║"
    echo "║   ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗    █████╗ ██╗    ████████╗██████╗   ║"
    echo "║   ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝   ██╔══██╗██║    ╚══██╔══╝██╔══██╗  ║"
    echo "║   ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗   ███████║██║       ██║   ██████╔╝  ║"
    echo "║   ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║   ██╔══██║██║       ██║   ██╔══██╗  ║"
    echo "║   ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║   ██║  ██║███████╗  ██║   ██║  ██║  ║"
    echo "║   ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝  ╚═╝╚══════╝  ╚═╝   ╚═╝  ╚═╝  ║"
    echo "║                                                                                   ║"
    echo "║                    NEXUS AI TRADING SYSTEM                                        ║"
    echo "║                    Copyright © 2026 NEXUS QUANTUM LTD                             ║"
    echo "║                    CEO: Dr X... - Majority Shareholder                            ║"
    echo "║                                                                                   ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════════════╝"
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
# PRÉREQUIS
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
    
    if [ $missing -gt 0 ]; then
        log_error "$missing prérequis manquants. Veuillez les installer avant de continuer."
        exit 1
    fi
    
    log "✅ Tous les prérequis sont satisfaits"
}

# ============================================
# INSTALLATION DES DÉPENDANCES
# ============================================
install_dependencies() {
    log_section "📦 INSTALLATION DES DÉPENDANCES"
    
    # Mise à jour des paquets
    log_info "Mise à jour des paquets système..."
    sudo apt update || log_warning "Impossible de mettre à jour les paquets"
    sudo apt upgrade -y || log_warning "Impossible de mettre à jour les paquets"
    
    # Installation des dépendances système
    log_info "Installation des dépendances système..."
    sudo apt install -y \
        build-essential \
        curl \
        wget \
        git \
        make \
        cmake \
        pkg-config \
        libssl-dev \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
        libpng-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libwebp-dev \
        tk-dev \
        tcl-dev \
        libopenblas-dev \
        libatlas-base-dev \
        liblapack-dev \
        gfortran \
        || log_warning "Certaines dépendances système n'ont pas pu être installées"
    
    # Poetry
    if ! command -v poetry &> /dev/null; then
        log_info "Installation de Poetry..."
        curl -sSL https://install.python-poetry.org | python3 -
        export PATH="$HOME/.local/bin:$PATH"
        log "Poetry installé"
    else
        log "Poetry déjà installé"
    fi
    
    # Yarn
    if ! command -v yarn &> /dev/null; then
        log_info "Installation de Yarn..."
        npm install -g yarn
        log "Yarn installé"
    else
        log "Yarn déjà installé"
    fi
    
    # Docker
    if ! command -v docker &> /dev/null; then
        log_info "Installation de Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
        log "Docker installé"
    else
        log "Docker déjà installé"
    fi
    
    # Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_info "Installation de Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        log "Docker Compose installé"
    else
        log "Docker Compose déjà installé"
    fi
    
    log "✅ Dépendances installées"
}

# ============================================
# CLONAGE DU PROJET
# ============================================
clone_project() {
    log_section "📁 CLONAGE DU PROJET"
    
    if [ -d "$PROJECT_PATH" ]; then
        log_warning "Le projet existe déjà dans $PROJECT_PATH"
        read -p "Voulez-vous le réinstaller ? (o/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Oo]$ ]]; then
            create_backup "$PROJECT_PATH"
            rm -rf "$PROJECT_PATH"
            log "Projet supprimé"
        else
            log_info "Utilisation du projet existant"
            cd "$PROJECT_PATH"
            git pull
            return 0
        fi
    fi
    
    log_info "Clonage du projet..."
    git clone https://github.com/NEXUS-QUANTUM/NEXUS-AI-TRADING-SYSTEM.git "$PROJECT_PATH"
    cd "$PROJECT_PATH"
    log "Projet cloné avec succès"
}

# ============================================
# CONFIGURATION
# ============================================
setup_configuration() {
    log_section "⚙️ CONFIGURATION"
    
    # Création des dossiers
    log_info "Création des dossiers..."
    mkdir -p data/{cache,logs,models,market-data,backups}
    mkdir -p backend/uploads/{avatars,documents,trading}
    mkdir -p backend/logs
    mkdir -p .secrets
    log "Dossiers créés"
    
    # Configuration de l'environnement
    log_info "Configuration de l'environnement..."
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log "Fichier .env créé à partir de .env.example"
        else
            log_warning "Fichier .env.example non trouvé"
        fi
    else
        log_info "Fichier .env existant conservé"
    fi
    
    # Permissions
    log_info "Configuration des permissions..."
    chmod 600 .env 2>/dev/null || log_warning "Impossible de changer les permissions de .env"
    chmod +x *.sh 2>/dev/null || log_warning "Impossible de rendre les scripts exécutables"
    log "Permissions configurées"
    
    # Configuration Git
    log_info "Configuration de Git..."
    git config core.fileMode false
    log "Git configuré"
}

# ============================================
# INSTALLATION DES DÉPENDANCES PYTHON
# ============================================
install_python_dependencies() {
    log_section "🐍 INSTALLATION DES DÉPENDANCES PYTHON"
    
    # Virtual Environment
    log_info "Création de l'environnement virtuel..."
    python3 -m venv venv
    source venv/bin/activate
    log "Environnement virtuel créé"
    
    # Mise à jour de PIP
    log_info "Mise à jour de PIP..."
    pip install --upgrade pip
    log "PIP mis à jour"
    
    # Installation des dépendances
    log_info "Installation des dépendances Python..."
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt
        log "Dépendances principales installées"
    fi
    
    if [ -f requirements-dev.txt ]; then
        pip install -r requirements-dev.txt
        log "Dépendances de développement installées"
    fi
    
    log "✅ Dépendances Python installées"
}

# ============================================
# INSTALLATION DES DÉPENDANCES NODE
# ============================================
install_node_dependencies() {
    log_section "⚡ INSTALLATION DES DÉPENDANCES NODE"
    
    if [ -d "apps/web" ]; then
        log_info "Installation des dépendances Node.js..."
        cd apps/web
        npm install
        cd ../..
        log "Dépendances Node.js installées"
    else
        log_warning "Dossier apps/web non trouvé"
    fi
    
    log "✅ Dépendances Node installées"
}

# ============================================
# INITIALISATION DES BASES DE DONNÉES
# ============================================
setup_databases() {
    log_section "🗄️ INITIALISATION DES BASES DE DONNÉES"
    
    # Docker up
    log_info "Démarrage des conteneurs Docker..."
    docker-compose -f docker-compose.dev.yml up -d postgres redis
    sleep 5
    log "Conteneurs démarrés"
    
    # Attente de PostgreSQL
    log_info "Attente de PostgreSQL..."
    for i in {1..30}; do
        if docker exec -t postgres pg_isready -U nexus &> /dev/null; then
            log "PostgreSQL est prêt"
            break
        fi
        sleep 2
    done
    
    # Migrations
    log_info "Exécution des migrations..."
    source venv/bin/activate
    python -c "from backend.core.database import init_db; init_db()" 2>/dev/null || log_warning "Erreur lors des migrations"
    log "Migrations exécutées"
    
    # Seed
    log_info "Remplissage des données de base..."
    python -c "from backend.database.seeders.main_seeder import seed; seed()" 2>/dev/null || log_warning "Erreur lors du seed"
    log "Données de base insérées"
    
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
        npm run build || log_warning "Erreur lors du build du frontend"
        cd ../..
        log "Frontend build terminé"
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
    echo "║   ✅ BOOTSTRAP TERMINÉ AVEC SUCCÈS                                               ║"
    echo "║                                                                                  ║"
    echo "║   📁 Projet: $PROJECT_NAME                                                       ║"
    echo "║   📂 Chemin: $PROJECT_PATH                                                       ║"
    echo "║                                                                                  ║"
    echo "║   🔗 Services disponibles:                                                       ║"
    echo "║   ├─ 🔌 API:          http://localhost:8000                                      ║"
    echo "║   ├─ 📝 API Docs:     http://localhost:8000/docs                                 ║"
    echo "║   ├─ 📊 Frontend:     http://localhost:3000                                      ║"
    echo "║   ├─ 📈 Monitoring:   http://localhost:3001                                      ║"
    echo "║   ├─ 🐘 PostgreSQL:   localhost:5432                                             ║"
    echo "║   └─ 🚀 Redis:        localhost:6379                                             ║"
    echo "║                                                                                  ║"
    echo "║   📋 Commandes disponibles:                                                      ║"
    echo "║   ├─ ./start_nexus.sh     → Démarrer les services                                ║"
    echo "║   ├─ ./stop_nexus.sh      → Arrêter les services                                 ║"
    echo "║   ├─ make help            → Aide Makefile                                        ║"
    echo "║   └─ source venv/bin/activate → Activer l'environnement Python                   ║"
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
    echo -e "  ${YELLOW}cd $PROJECT_PATH${NC}"
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
    
    log_info "Démarrage du bootstrap à $(date)"
    log_info "Log file: $LOG_FILE"
    
    # Menu interactif
    echo -e "\n${CYAN}Que voulez-vous faire ?${NC}"
    echo "1) Installation complète (recommandé)"
    echo "2) Vérifier les prérequis seulement"
    echo "3) Installer les dépendances seulement"
    echo "4) Initialiser le projet existant"
    echo "5) Quitter"
    echo ""
    read -p "Votre choix (1-5): " choice
    
    case $choice in
        1)
            check_prerequisites
            install_dependencies
            clone_project
            setup_configuration
            install_python_dependencies
            install_node_dependencies
            setup_databases
            build_frontend
            final_check
            show_final_info
            ;;
        2)
            check_prerequisites
            ;;
        3)
            install_dependencies
            ;;
        4)
            cd "$PROJECT_PATH" 2>/dev/null || { log_error "Projet non trouvé"; exit 1; }
            setup_configuration
            install_python_dependencies
            install_node_dependencies
            setup_databases
            build_frontend
            final_check
            show_final_info
            ;;
        5)
            echo -e "${GREEN}Au revoir !${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Choix invalide.${NC}"
            exit 1
            ;;
    esac
    
    echo -e "\n${GREEN}✅ Bootstrap terminé !${NC}"
    echo -e "${BLUE}📝 Logs disponibles dans: $LOG_FILE${NC}"
}

# ============================================
# EXÉCUTION
# ============================================
main "$@"

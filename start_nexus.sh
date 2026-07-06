#!/bin/bash
# ============================================
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD
# CEO: Dr X... - Majority Shareholder
# ============================================
# Script de démarrage complet de NEXUS
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
LOG_FILE="${PROJECT_ROOT}/nexus.log"
PID_FILE="${PROJECT_ROOT}/.nexus.pid"
ENV_FILE="${PROJECT_ROOT}/.env"

# ============================================
# BANNIÈRE
# ============================================
show_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                  ║"
    echo "║   ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗    █████╗ ██╗    ████████╗██████╗ ║"
    echo "║   ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝   ██╔══██╗██║    ╚══██╔══╝██╔══██╗║"
    echo "║   ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗   ███████║██║       ██║   ██████╔╝║"
    echo "║   ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║   ██╔══██║██║       ██║   ██╔══██╗║"
    echo "║   ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║   ██║  ██║███████╗  ██║   ██║  ██║║"
    echo "║   ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝  ╚═╝╚══════╝  ╚═╝   ╚═╝  ╚═╝║"
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

check_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

write_pid() {
    echo $$ > "$PID_FILE"
}

cleanup() {
    rm -f "$PID_FILE"
}

# ============================================
# LOAD ENV
# ============================================
load_env() {
    if [ -f "$ENV_FILE" ]; then
        log_info "Chargement des variables d'environnement..."
        set -a
        source "$ENV_FILE"
        set +a
        log "Variables d'environnement chargées"
    else
        log_warning "Fichier .env non trouvé, utilisation des variables par défaut"
    fi
}

# ============================================
# VÉRIFICATION DES PRÉREQUIS
# ============================================
check_prerequisites() {
    log_section "📋 VÉRIFICATION DES PRÉREQUIS"
    
    # Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker n'est pas installé"
        log_info "Veuillez installer Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    log "Docker version: $(docker --version)"
    
    # Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose n'est pas installé"
        log_info "Veuillez installer Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    log "Docker Compose version: $(docker-compose --version)"
    
    # Python
    if ! command -v python3 &> /dev/null; then
        log_warning "Python n'est pas installé (le backend pourrait ne pas fonctionner)"
    else
        log "Python version: $(python3 --version)"
    fi
    
    # Node
    if ! command -v node &> /dev/null; then
        log_warning "Node n'est pas installé (le frontend pourrait ne pas fonctionner)"
    else
        log "Node version: $(node --version)"
    fi
    
    log "✅ Prérequis vérifiés"
}

# ============================================
# DÉMARRAGE DES SERVICES DOCKER
# ============================================
start_docker_services() {
    log_section "🐳 DÉMARRAGE DES SERVICES DOCKER"
    
    if [ -f "docker-compose.dev.yml" ]; then
        log_info "Démarrage des services Docker..."
        docker-compose -f docker-compose.dev.yml up -d
        
        # Attente que les services soient prêts
        log_info "Attente que les services soient prêts..."
        sleep 10
        
        # Vérification des services
        docker-compose -f docker-compose.dev.yml ps
        log "✅ Services Docker démarrés"
    else
        log_warning "Fichier docker-compose.dev.yml non trouvé"
    fi
}

# ============================================
# DÉMARRAGE DU BACKEND
# ============================================
start_backend() {
    log_section "🚀 DÉMARRAGE DU BACKEND"
    
    if [ -d "backend" ] && [ -f "backend/main.py" ]; then
        log_info "Démarrage du backend..."
        
        # Activer l'environnement virtuel si existant
        if [ -d "venv" ]; then
            source venv/bin/activate
            log "Environnement virtuel activé"
        fi
        
        # Démarrer le backend en arrière-plan
        if [ "$APP_ENV" = "production" ] || [ "$APP_ENV" = "prod" ]; then
            log_info "Démarrage en mode production..."
            nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4 > backend.log 2>&1 &
            BACKEND_PID=$!
            log "Backend démarré (PID: $BACKEND_PID)"
        else
            log_info "Démarrage en mode développement..."
            nohup uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
            BACKEND_PID=$!
            log "Backend démarré en mode développement (PID: $BACKEND_PID)"
        fi
        
        # Attendre que le backend soit prêt
        log_info "Attente du backend..."
        for i in {1..30}; do
            if curl -s http://localhost:8000/health > /dev/null 2>&1; then
                log "Backend est prêt"
                break
            fi
            sleep 1
        done
        log "✅ Backend démarré"
    else
        log_warning "Backend non trouvé"
    fi
}

# ============================================
# DÉMARRAGE DU FRONTEND
# ============================================
start_frontend() {
    log_section "🚀 DÉMARRAGE DU FRONTEND"
    
    if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then
        log_info "Démarrage du frontend..."
        cd apps/web
        
        if [ "$APP_ENV" = "production" ] || [ "$APP_ENV" = "prod" ]; then
            log_info "Démarrage en mode production..."
            nohup npm start > frontend.log 2>&1 &
            FRONTEND_PID=$!
            log "Frontend démarré (PID: $FRONTEND_PID)"
        else
            log_info "Démarrage en mode développement..."
            nohup npm run dev > frontend.log 2>&1 &
            FRONTEND_PID=$!
            log "Frontend démarré en mode développement (PID: $FRONTEND_PID)"
        fi
        
        cd ../..
        log "✅ Frontend démarré"
    else
        log_warning "Frontend non trouvé"
    fi
}

# ============================================
# DÉMARRAGE DU MONITORING
# ============================================
start_monitoring() {
    log_section "📊 DÉMARRAGE DU MONITORING"
    
    if [ -f "configs/monitoring/docker-compose.monitoring.yml" ]; then
        log_info "Démarrage du monitoring..."
        docker-compose -f configs/monitoring/docker-compose.monitoring.yml up -d
        log "✅ Monitoring démarré"
    else
        log_warning "Monitoring non configuré"
    fi
}

# ============================================
# VÉRIFICATION FINALE
# ============================================
final_check() {
    log_section "✅ VÉRIFICATION FINALE"
    
    log_info "Vérification des services..."
    
    # Vérifier le backend
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log "Backend: ✅ OK (http://localhost:8000)"
    else
        log_warning "Backend: ❌ Non accessible"
    fi
    
    # Vérifier le frontend
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        log "Frontend: ✅ OK (http://localhost:3000)"
    else
        log_warning "Frontend: ❌ Non accessible"
    fi
    
    # Vérifier les services Docker
    docker-compose -f docker-compose.dev.yml ps 2>/dev/null || log_warning "Impossible de vérifier les services Docker"
    
    log "✅ Vérification terminée"
}

# ============================================
# AFFICHAGE DES INFORMATIONS
# ============================================
show_info() {
    log_section "📊 INFORMATIONS DES SERVICES"
    
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                  ║"
    echo "║   ✅ NEXUS AI TRADING SYSTEM DÉMARRÉ                                             ║"
    echo "║                                                                                  ║"
    echo "║   🔗 SERVICES DISPONIBLES:                                                       ║"
    echo "║                                                                                  ║"
    echo "║   📊 Frontend:        http://localhost:3000                                      ║"
    echo "║   🔌 API:             http://localhost:8000                                      ║"
    echo "║   📝 API Docs:        http://localhost:8000/docs                                 ║"
    echo "║   📋 API Redoc:       http://localhost:8000/redoc                                ║"
    echo "║   📈 Monitoring:      http://localhost:3001                                      ║"
    echo "║   📊 Grafana:         http://localhost:3001                                      ║"
    echo "║   📈 Prometheus:      http://localhost:9090                                      ║"
    echo "║   📝 Loki:            http://localhost:3100                                      ║"
    echo "║   🔍 Tempo:           http://localhost:3200                                      ║"
    echo "║   🐘 PostgreSQL:      localhost:5432                                             ║"
    echo "║   📈 TimescaleDB:     localhost:5433                                             ║"
    echo "║   🍃 MongoDB:         localhost:27017                                            ║"
    echo "║   🚀 Redis:           localhost:6379                                             ║"
    echo "║   🐳 Redis Insight:   http://localhost:5540                                      ║"
    echo "║   🐘 PGAdmin:         http://localhost:5050                                      ║"
    echo "║                                                                                  ║"
    echo "║   📋 COMMANDES:                                                                  ║"
    echo "║   ├─ ./stop_nexus.sh      → Arrêter les services                                ║"
    echo "║   ├─ docker-compose logs -f → Voir les logs                                     ║"
    echo "║   └─ make help            → Aide Makefile                                       ║"
    echo "║                                                                                  ║"
    echo "║   📚 Documentation: https://docs.nexustradingia.com                              ║"
    echo "║   🔗 GitHub: https://github.com/NEXUS-QUANTUM/NEXUS-AI-TRADING-SYSTEM            ║"
    echo "║                                                                                  ║"
    echo "║   📅 Copyright © 2026 NEXUS QUANTUM LTD                                          ║"
    echo "║   👑 CEO: Dr X... - Majority Shareholder                                         ║"
    echo "║                                                                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ============================================
# ARRÊT DES SERVICES
# ============================================
stop_services() {
    log_section "🛑 ARRÊT DES SERVICES"
    
    # Arrêter le backend
    if [ -n "$BACKEND_PID" ] && ps -p "$BACKEND_PID" > /dev/null 2>&1; then
        log_info "Arrêt du backend (PID: $BACKEND_PID)..."
        kill -TERM "$BACKEND_PID" 2>/dev/null || kill -KILL "$BACKEND_PID" 2>/dev/null
        log "Backend arrêté"
    fi
    
    # Arrêter le frontend
    if [ -n "$FRONTEND_PID" ] && ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
        log_info "Arrêt du frontend (PID: $FRONTEND_PID)..."
        kill -TERM "$FRONTEND_PID" 2>/dev/null || kill -KILL "$FRONTEND_PID" 2>/dev/null
        log "Frontend arrêté"
    fi
    
    # Arrêter les services Docker
    if [ -f "docker-compose.dev.yml" ]; then
        log_info "Arrêt des services Docker..."
        docker-compose -f docker-compose.dev.yml down
        log "Services Docker arrêtés"
    fi
    
    # Nettoyer le PID
    cleanup
    log "✅ Services arrêtés"
}

# ============================================
# MENU PRINCIPAL
# ============================================
main() {
    # Trapper les signaux
    trap cleanup EXIT INT TERM
    
    # Création du dossier de logs
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    
    show_banner
    
    log_info "Démarrage de NEXUS AI TRADING SYSTEM à $(date)"
    log_info "Log file: $LOG_FILE"
    
    # Vérifier si déjà en cours d'exécution
    if check_pid; then
        log_warning "NEXUS est déjà en cours d'exécution (PID: $(cat $PID_FILE))"
        read -p "Voulez-vous le redémarrer ? (o/N) " -r
        if [[ $REPLY =~ ^[Oo]$ ]]; then
            stop_services
            sleep 2
        else
            exit 0
        fi
    fi
    
    write_pid
    
    # Charger les variables d'environnement
    load_env
    
    # Menu interactif
    echo -e "\n${CYAN}Que voulez-vous faire ?${NC}"
    echo "1) Démarrer NEXUS (complet - recommandé)"
    echo "2) Démarrer NEXUS (production)"
    echo "3) Démarrer seulement les services Docker"
    echo "4) Démarrer seulement le backend"
    echo "5) Démarrer seulement le frontend"
    echo "6) Démarrer le monitoring"
    echo "7) Arrêter NEXUS"
    echo "8) Voir les logs"
    echo "9) Quitter"
    echo ""
    read -p "Votre choix (1-9): " choice
    
    case $choice in
        1)
            log_info "Démarrage de NEXUS (mode développement)..."
            check_prerequisites
            start_docker_services
            start_backend
            start_frontend
            start_monitoring
            final_check
            show_info
            ;;
        2)
            log_info "Démarrage de NEXUS (mode production)..."
            APP_ENV=production
            check_prerequisites
            start_docker_services
            start_backend
            start_frontend
            start_monitoring
            final_check
            show_info
            ;;
        3)
            log_info "Démarrage des services Docker..."
            check_prerequisites
            start_docker_services
            final_check
            show_info
            ;;
        4)
            log_info "Démarrage du backend..."
            check_prerequisites
            start_docker_services
            start_backend
            final_check
            show_info
            ;;
        5)
            log_info "Démarrage du frontend..."
            check_prerequisites
            start_frontend
            final_check
            show_info
            ;;
        6)
            log_info "Démarrage du monitoring..."
            check_prerequisites
            start_monitoring
            final_check
            show_info
            ;;
        7)
            stop_services
            ;;
        8)
            log_section "📋 LOGS"
            if [ -f "$LOG_FILE" ]; then
                tail -f "$LOG_FILE"
            else
                log_warning "Fichier de logs non trouvé"
            fi
            ;;
        9)
            echo -e "${GREEN}Au revoir !${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Choix invalide.${NC}"
            exit 1
            ;;
    esac
    
    echo -e "\n${GREEN}✅ NEXUS AI TRADING SYSTEM est en cours d'exécution !${NC}"
    echo -e "${BLUE}📝 Logs disponibles dans: $LOG_FILE${NC}"
    echo -e "${YELLOW}🛑 Pour arrêter: ./stop_nexus.sh${NC}"
    
    # Garder le script en cours d'exécution
    echo -e "\n${YELLOW}Appuyez sur Ctrl+C pour arrêter${NC}"
    wait
}

# ============================================
# EXÉCUTION
# ============================================
main "$@"

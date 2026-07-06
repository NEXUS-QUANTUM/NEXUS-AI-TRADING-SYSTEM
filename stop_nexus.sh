#!/bin/bash
# ============================================
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD
# CEO: Dr X... - Majority Shareholder
# ============================================
# Script d'arrêt complet de NEXUS
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
LOG_FILE="${PROJECT_ROOT}/nexus_stop.log"
PID_FILE="${PROJECT_ROOT}/.nexus.pid"

# ============================================
# BANNIÈRE
# ============================================
show_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                  ║"
    echo "║   ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗    ███████╗████████╗ ██████╗ ██████╗║"
    echo "║   ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝    ██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗║"
    echo "║   ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗    ███████╗   ██║   ██║   ██║██████╔╝║"
    echo "║   ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║    ╚════██║   ██║   ██║   ██║██╔═══╝ ║"
    echo "║   ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║    ███████║   ██║   ╚██████╔╝██║     ║"
    echo "║   ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ╚══════╝   ╚═╝    ╚═════╝ ╚═╝     ║"
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

# ============================================
# ARRÊT DU BACKEND
# ============================================
stop_backend() {
    log_section "🛑 ARRÊT DU BACKEND"
    
    # Trouver les processus backend
    BACKEND_PIDS=$(ps aux | grep -E "uvicorn|gunicorn|backend\.main" | grep -v grep | awk '{print $2}' || echo "")
    
    if [ -n "$BACKEND_PIDS" ]; then
        log_info "Arrêt du backend (PID: $BACKEND_PIDS)..."
        for pid in $BACKEND_PIDS; do
            kill -TERM "$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
        done
        log "Backend arrêté"
    else
        log_info "Aucun processus backend trouvé"
    fi
}

# ============================================
# ARRÊT DU FRONTEND
# ============================================
stop_frontend() {
    log_section "🛑 ARRÊT DU FRONTEND"
    
    # Trouver les processus frontend
    FRONTEND_PIDS=$(ps aux | grep -E "next|npm run dev|react-scripts|node.*next" | grep -v grep | awk '{print $2}' || echo "")
    
    if [ -n "$FRONTEND_PIDS" ]; then
        log_info "Arrêt du frontend (PID: $FRONTEND_PIDS)..."
        for pid in $FRONTEND_PIDS; do
            kill -TERM "$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
        done
        log "Frontend arrêté"
    else
        log_info "Aucun processus frontend trouvé"
    fi
}

# ============================================
# ARRÊT DE L'IA WORKER
# ============================================
stop_ai_worker() {
    log_section "🧠 ARRÊT DE L'IA WORKER"
    
    # Trouver les processus AI worker
    AI_PIDS=$(ps aux | grep -E "celery|ai\.worker|ai-worker" | grep -v grep | awk '{print $2}' || echo "")
    
    if [ -n "$AI_PIDS" ]; then
        log_info "Arrêt de l'IA worker (PID: $AI_PIDS)..."
        for pid in $AI_PIDS; do
            kill -TERM "$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
        done
        log "IA worker arrêté"
    else
        log_info "Aucun processus IA worker trouvé"
    fi
}

# ============================================
# ARRÊT DES SERVICES DOCKER
# ============================================
stop_docker_services() {
    log_section "🐳 ARRÊT DES SERVICES DOCKER"
    
    # Arrêter les services de développement
    if [ -f "docker-compose.dev.yml" ]; then
        log_info "Arrêt des services Docker développement..."
        docker-compose -f docker-compose.dev.yml down
        log "Services Docker développement arrêtés"
    else
        log_warning "Fichier docker-compose.dev.yml non trouvé"
    fi
    
    # Arrêter les services de production
    if [ -f "docker-compose.prod.yml" ]; then
        log_info "Arrêt des services Docker production..."
        docker-compose -f docker-compose.prod.yml down
        log "Services Docker production arrêtés"
    else
        log_warning "Fichier docker-compose.prod.yml non trouvé"
    fi
}

# ============================================
# ARRÊT DU MONITORING
# ============================================
stop_monitoring() {
    log_section "📊 ARRÊT DU MONITORING"
    
    if [ -f "configs/monitoring/docker-compose.monitoring.yml" ]; then
        log_info "Arrêt du monitoring..."
        docker-compose -f configs/monitoring/docker-compose.monitoring.yml down
        log "Monitoring arrêté"
    else
        log_warning "Monitoring non configuré"
    fi
}

# ============================================
# NETTOYAGE
# ============================================
cleanup() {
    log_section "🧹 NETTOYAGE"
    
    # Supprimer le fichier PID
    if [ -f "$PID_FILE" ]; then
        rm -f "$PID_FILE"
        log "Fichier PID supprimé"
    fi
    
    # Nettoyer les fichiers temporaires
    log_info "Nettoyage des fichiers temporaires..."
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".ruff_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.log" -type f -size +100M -exec truncate -s 0 {} + 2>/dev/null || true
    log "Fichiers temporaires nettoyés"
    
    # Nettoyer les logs anciens
    log_info "Nettoyage des logs anciens..."
    find . -name "*.log.*" -type f -mtime +30 -delete 2>/dev/null || true
    log "Logs anciens nettoyés"
}

# ============================================
# NETTOYAGE DOCKER
# ============================================
docker_cleanup() {
    log_section "🐳 NETTOYAGE DOCKER"
    
    log_info "Nettoyage des conteneurs Docker..."
    docker container prune -f 2>/dev/null || log_warning "Impossible de nettoyer les conteneurs"
    
    log_info "Nettoyage des images Docker..."
    docker image prune -f 2>/dev/null || log_warning "Impossible de nettoyer les images"
    
    log_info "Nettoyage des volumes Docker..."
    docker volume prune -f 2>/dev/null || log_warning "Impossible de nettoyer les volumes"
    
    log_info "Nettoyage des réseaux Docker..."
    docker network prune -f 2>/dev/null || log_warning "Impossible de nettoyer les réseaux"
    
    log "Nettoyage Docker terminé"
}

# ============================================
# VÉRIFICATION FINALE
# ============================================
final_check() {
    log_section "✅ VÉRIFICATION FINALE"
    
    log_info "Vérification des processus restants..."
    
    # Vérifier les processus backend
    if ps aux | grep -E "uvicorn|gunicorn|backend\.main" | grep -v grep > /dev/null 2>&1; then
        log_warning "Des processus backend sont encore en cours d'exécution"
    else
        log "✅ Aucun processus backend restant"
    fi
    
    # Vérifier les processus frontend
    if ps aux | grep -E "next|npm run dev|react-scripts" | grep -v grep > /dev/null 2>&1; then
        log_warning "Des processus frontend sont encore en cours d'exécution"
    else
        log "✅ Aucun processus frontend restant"
    fi
    
    # Vérifier les conteneurs Docker
    if docker ps -a --filter "name=nexus" --format "table {{.Names}}" | grep -v NAMES | grep -q .; then
        log_warning "Des conteneurs Nexus sont encore présents"
        docker ps -a --filter "name=nexus"
    else
        log "✅ Aucun conteneur Nexus restant"
    fi
    
    log "✅ Vérification terminée"
}

# ============================================
# AFFICHAGE DES INFORMATIONS
# ============================================
show_info() {
    log_section "📊 INFORMATIONS D'ARRÊT"
    
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                  ║"
    echo "║   ✅ NEXUS AI TRADING SYSTEM ARRÊTÉ                                              ║"
    echo "║                                                                                  ║"
    echo "║   📋 Services arrêtés:                                                           ║"
    echo "║   ├─ ✅ Backend                                                                  ║"
    echo "║   ├─ ✅ Frontend                                                                 ║"
    echo "║   ├─ ✅ IA Worker                                                                ║"
    echo "║   ├─ ✅ Services Docker                                                          ║"
    echo "║   ├─ ✅ Monitoring                                                               ║"
    echo "║   └─ ✅ Fichiers temporaires nettoyés                                            ║"
    echo "║                                                                                  ║"
    echo "║   🚀 Pour redémarrer:                                                            ║"
    echo "║   └─ ./start_nexus.sh                                                            ║"
    echo "║                                                                                  ║"
    echo "║   📅 Copyright © 2026 NEXUS QUANTUM LTD                                          ║"
    echo "║   👑 CEO: Dr X... - Majority Shareholder                                         ║"
    echo "║                                                                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ============================================
# MENU PRINCIPAL
# ============================================
main() {
    # Création du dossier de logs
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    
    show_banner
    
    log_info "Arrêt de NEXUS AI TRADING SYSTEM à $(date)"
    log_info "Log file: $LOG_FILE"
    
    # Menu interactif
    echo -e "\n${CYAN}Que voulez-vous faire ?${NC}"
    echo "1) Arrêter NEXUS (complet - recommandé)"
    echo "2) Arrêter NEXUS (complet + nettoyage Docker)"
    echo "3) Arrêter seulement le backend"
    echo "4) Arrêter seulement le frontend"
    echo "5) Arrêter seulement l'IA worker"
    echo "6) Arrêter seulement les services Docker"
    echo "7) Arrêter seulement le monitoring"
    echo "8) Arrêter et nettoyer complètement"
    echo "9) Quitter"
    echo ""
    read -p "Votre choix (1-9): " choice
    
    case $choice in
        1)
            log_info "Arrêt complet de NEXUS..."
            stop_backend
            stop_frontend
            stop_ai_worker
            stop_docker_services
            stop_monitoring
            cleanup
            final_check
            show_info
            ;;
        2)
            log_info "Arrêt complet de NEXUS avec nettoyage Docker..."
            stop_backend
            stop_frontend
            stop_ai_worker
            stop_docker_services
            stop_monitoring
            cleanup
            docker_cleanup
            final_check
            show_info
            ;;
        3)
            log_info "Arrêt du backend..."
            stop_backend
            log "✅ Backend arrêté"
            ;;
        4)
            log_info "Arrêt du frontend..."
            stop_frontend
            log "✅ Frontend arrêté"
            ;;
        5)
            log_info "Arrêt de l'IA worker..."
            stop_ai_worker
            log "✅ IA worker arrêté"
            ;;
        6)
            log_info "Arrêt des services Docker..."
            stop_docker_services
            log "✅ Services Docker arrêtés"
            ;;
        7)
            log_info "Arrêt du monitoring..."
            stop_monitoring
            log "✅ Monitoring arrêté"
            ;;
        8)
            log_info "Arrêt et nettoyage complet..."
            stop_backend
            stop_frontend
            stop_ai_worker
            stop_docker_services
            stop_monitoring
            cleanup
            docker_cleanup
            final_check
            show_info
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
    
    echo -e "\n${GREEN}✅ NEXUS AI TRADING SYSTEM arrêté !${NC}"
    echo -e "${BLUE}📝 Logs disponibles dans: $LOG_FILE${NC}"
    echo -e "${YELLOW}🚀 Pour redémarrer: ./start_nexus.sh${NC}"
}

# ============================================
# EXÉCUTION
# ============================================
main "$@"

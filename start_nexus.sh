#!/bin/bash
# ============================================
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD
# CEO: Dr X... - Majority Shareholder
# ============================================

set -e

echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                   ║"
echo "║              NEXUS AI TRADING SYSTEM                              ║"
echo "║              Copyright © 2026 NEXUS QUANTUM LTD                   ║"
echo "║              CEO: Dr X... - Majority Shareholder                  ║"
echo "║                                                                   ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

if [ ! -f .env ]; then
    echo "❌ Fichier .env manquant. Exécutez ./init_project.sh"
    exit 1
fi

source .env 2>/dev/null || true

echo "🚀 Démarrage de NEXUS AI TRADING SYSTEM..."
docker-compose -f docker-compose.dev.yml up -d --build
sleep 5
docker-compose -f docker-compose.dev.yml ps

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                   ║"
echo "║   ✅ NEXUS AI TRADING SYSTEM DÉMARRÉ                             ║"
echo "║                                                                   ║"
echo "║   📊 Dashboard: http://localhost:3000                            ║"
echo "║   🔌 API: http://localhost:8000                                  ║"
echo "║   📝 API Docs: http://localhost:8000/docs                        ║"
echo "║   📊 Monitoring: http://localhost:3001                           ║"
echo "║                                                                   ║"
echo "║   📋 Logs: docker-compose -f docker-compose.dev.yml logs -f      ║"
echo "║   🛑 Stop: ./stop_nexus.sh                                       ║"
echo "║                                                                   ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"

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

echo "🛑 Arrêt de NEXUS AI TRADING SYSTEM..."
docker-compose -f docker-compose.dev.yml down
echo "✅ Services arrêtés"

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                   ║"
echo "║   ✅ NEXUS AI TRADING SYSTEM ARRÊTÉ                              ║"
echo "║                                                                   ║"
echo "║   🚀 ./start_nexus.sh                                           ║"
echo "║                                                                   ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"

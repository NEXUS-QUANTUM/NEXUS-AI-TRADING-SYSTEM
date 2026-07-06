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

echo "[1/7] Vérification des prérequis..."
for cmd in python3 docker docker-compose git node npm; do
    if ! command -v $cmd &> /dev/null; then
        echo "❌ $cmd n'est pas installé"
        exit 1
    fi
done
echo "✅ Tous les prérequis sont satisfaits"

echo "[2/7] Installation des dépendances Python..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
echo "✅ Dépendances Python installées"

echo "[3/7] Installation des dépendances Node.js..."
cd apps/web
npm install
cd ../..
echo "✅ Dépendances Node.js installées"

echo "[4/7] Configuration de l'environnement..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Fichier .env créé"
else
    echo "ℹ️ Fichier .env existant conservé"
fi

echo "[5/7] Initialisation des bases de données..."
docker-compose -f docker-compose.dev.yml up -d postgres redis
echo "✅ Bases de données initialisées"

echo "[6/7] Création des dossiers..."
for d in data/cache data/logs data/models data/market-data backend/uploads/avatars backend/uploads/documents backend/uploads/trading; do
    mkdir -p "$d"
done
echo "✅ Dossiers créés"

echo "[7/7] Migration de la base de données..."
source venv/bin/activate
python -c "from backend.core.database import init_db; init_db()" 2>/dev/null || echo "⚠️ Migration manuelle requise"
echo "✅ Migration terminée"

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                                                                   ║"
echo "║   ✅ INITIALISATION TERMINÉE                                     ║"
echo "║                                                                   ║"
echo "║   📁 $(pwd)                                                      ║"
echo "║   🐍 $(python3 --version)                                        ║"
echo "║   📦 $(docker --version)                                         ║"
echo "║   ⚡ $(node --version)                                           ║"
echo "║                                                                   ║"
echo "║   🚀 ./start_nexus.sh                                           ║"
echo "║                                                                   ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"

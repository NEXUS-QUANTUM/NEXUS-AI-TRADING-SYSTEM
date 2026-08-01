# trading/bots/hedge_bot/hedge_bot_portfolio.py
# Advanced Portfolio Management & Performance Tracking Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Portfolio Module - Module avancé de gestion de portefeuille et de suivi des performances
pour le Hedge Bot. Gère l'allocation d'actifs, le suivi des performances, le PnL, les rapports,
l'analyse de risque et l'optimisation du portefeuille de hedging.
"""

import asyncio
import json
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_portfolio")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult, OrderStatus
)


# ============== ENUMS & TYPES ==============

class PortfolioType(Enum):
    """Types de portefeuille."""
    HEDGE = "hedge"                    # Portefeuille de hedging
    INVESTMENT = "investment"          # Portefeuille d'investissement
    TRADING = "trading"                # Portefeuille de trading
    COMPOSITE = "composite"            # Portefeuille composite
    PAPER = "paper"                    # Portefeuille papier (simulation)


class AllocationType(Enum):
    """Types d'allocation."""
    DYNAMIC = "dynamic"                # Allocation dynamique
    STATIC = "static"                  # Allocation statique
    TACTICAL = "tactical"              # Allocation tactique
    STRATEGIC = "strategic"            # Allocation stratégique
    RISK_PARITY = "risk_parity"        # Parité des risques


class PerformanceMetric(Enum):
    """Métriques de performance."""
    TOTAL_RETURN = "total_return"
    ANNUALIZED_RETURN = "annualized_return"
    VOLATILITY = "volatility"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_VALUE = "expected_value"
    CALMAR_RATIO = "calmar_ratio"


# ============== DATA MODELS ==============

@dataclass
class Portfolio:
    """Modèle de portefeuille."""
    portfolio_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    portfolio_type: PortfolioType = PortfolioType.HEDGE
    allocation_type: AllocationType = AllocationType.DYNAMIC
    assets: Dict[str, float] = field(default_factory=dict)  # symbol -> quantity
    cash: float = 0.0
    total_value: float = 0.0
    initial_capital: float = 0.0
    current_capital: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class PortfolioSnapshot:
    """Snapshot de portefeuille."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_value: float = 0.0
    cash: float = 0.0
    assets: Dict[str, Dict[str, float]] = field(default_factory=dict)
    pnl: float = 0.0
    pnl_percent: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioReport:
    """Rapport de portefeuille."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str = ""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    snapshots: List[PortfolioSnapshot] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, float] = field(default_factory=dict)
    risk_analysis: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationConfig:
    """Configuration d'allocation."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str = ""
    target_allocation: Dict[str, float] = field(default_factory=dict)  # symbol -> target weight
    min_allocation: Dict[str, float] = field(default_factory=dict)
    max_allocation: Dict[str, float] = field(default_factory=dict)
    rebalance_threshold: float = 0.02
    rebalance_frequency: int = 86400  # 1 day
    risk_target: float = 0.02
    max_leverage: float = 2.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


# ============== INTERFACES ==============

class PortfolioManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de portefeuille."""
    
    @abstractmethod
    async def create_portfolio(self, config: Dict[str, Any]) -> Portfolio:
        """Crée un portefeuille."""
        pass
    
    @abstractmethod
    async def update_portfolio(self, portfolio_id: str, prices: Dict[str, float]) -> Portfolio:
        """Met à jour un portefeuille."""
        pass
    
    @abstractmethod
    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Récupère un portefeuille."""
        pass


# ============== IMPLÉMENTATION ==============

class PortfolioManager(PortfolioManagerInterface):
    """
    Gestionnaire de portefeuille avancé pour le Hedge Bot.
    Gère l'allocation, le suivi des performances et l'analyse de risque.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des portefeuilles
        self._portfolios: Dict[str, Portfolio] = {}
        self._portfolios_lock = threading.RLock()
        
        # Gestion des snapshots
        self._snapshots: Dict[str, List[PortfolioSnapshot]] = defaultdict(list)
        self._snapshots_lock = threading.RLock()
        
        # Gestion des rapports
        self._reports: Dict[str, PortfolioReport] = {}
        self._reports_lock = threading.RLock()
        
        # Gestion des allocations
        self._allocations: Dict[str, AllocationConfig] = {}
        self._allocations_lock = threading.RLock()
        
        # Cache des prix
        self._price_cache: Dict[str, float] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "portfolios_created": 0,
            "snapshots_taken": 0,
            "reports_generated": 0,
            "rebalances_performed": 0,
            "total_pnl": 0.0,
            "avg_portfolio_size": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PortfolioManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_portfolio_type": PortfolioType.HEDGE,
            "default_allocation_type": AllocationType.DYNAMIC,
            "snapshot_interval": 60,
            "report_interval": 86400,
            "rebalance_threshold": 0.02,
            "risk_free_rate": 0.02,
            "target_volatility": 0.15,
            "max_leverage": 2.0,
            "min_position_size": 0.01,
            "max_position_size": 0.5,
            "enable_auto_rebalance": True,
            "enable_performance_tracking": True
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire de portefeuille."""
        logger.info("PortfolioManager starting...")
        self._is_running = True
        
        # Chargement des portefeuilles
        await self._load_portfolios()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._snapshot_loop())
        asyncio.create_task(self._rebalance_loop())
        asyncio.create_task(self._report_generator())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PortfolioManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de portefeuille."""
        logger.info("PortfolioManager stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("PortfolioManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_portfolio(self, config: Dict[str, Any]) -> Portfolio:
        """Crée un portefeuille."""
        portfolio = Portfolio(
            name=config.get("name", f"Portfolio_{uuid.uuid4().hex[:8]}"),
            portfolio_type=PortfolioType(config.get("portfolio_type", "hedge")),
            allocation_type=AllocationType(config.get("allocation_type", "dynamic")),
            assets=config.get("assets", {}),
            cash=config.get("cash", 0.0),
            initial_capital=config.get("initial_capital", 0.0),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        # Calcul de la valeur initiale
        portfolio.total_value = await self._calculate_portfolio_value(portfolio)
        portfolio.current_capital = portfolio.initial_capital or portfolio.total_value
        
        with self._portfolios_lock:
            self._portfolios[portfolio.portfolio_id] = portfolio
            self._stats["portfolios_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"portfolio:{portfolio.portfolio_id}",
                portfolio.to_dict(),
                DataType.PORTFOLIO
            )
        
        logger.info(f"Portfolio created: {portfolio.name} (id={portfolio.portfolio_id})")
        return portfolio
    
    async def update_portfolio(self, portfolio_id: str, prices: Dict[str, float]) -> Portfolio:
        """Met à jour un portefeuille."""
        with self._portfolios_lock:
            portfolio = self._portfolios.get(portfolio_id)
            if not portfolio:
                raise ValueError(f"Portfolio {portfolio_id} not found")
            
            # Mise à jour des prix
            for symbol, price in prices.items():
                if symbol in portfolio.assets:
                    portfolio.assets[symbol] = portfolio.assets[symbol]
                # Mise à jour du cache
                with self._cache_lock:
                    self._price_cache[symbol] = price
            
            # Mise à jour de la valeur
            total_value = await self._calculate_portfolio_value(portfolio)
            
            # Mise à jour du PnL
            old_value = portfolio.total_value
            portfolio.total_value = total_value
            
            # Calcul du PnL non réalisé
            portfolio.unrealized_pnl = total_value - portfolio.current_capital
            portfolio.realized_pnl = 0  # À calculer à partir des trades
            portfolio.pnl = portfolio.unrealized_pnl + portfolio.realized_pnl
            portfolio.pnl_percent = (portfolio.pnl / portfolio.current_capital) * 100 if portfolio.current_capital > 0 else 0
            
            # Mise à jour des métriques de performance
            if self.config["enable_performance_tracking"]:
                portfolio.performance_metrics = await self._calculate_performance_metrics(portfolio)
                portfolio.risk_metrics = await self._calculate_risk_metrics(portfolio)
            
            portfolio.updated_at = datetime.now(timezone.utc)
            
            return portfolio
    
    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Récupère un portefeuille."""
        with self._portfolios_lock:
            return self._portfolios.get(portfolio_id)
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    async def _calculate_portfolio_value(self, portfolio: Portfolio) -> float:
        """Calcule la valeur totale du portefeuille."""
        total_value = portfolio.cash
        
        for symbol, quantity in portfolio.assets.items():
            price = await self._get_price(symbol)
            if price:
                total_value += quantity * price
        
        return total_value
    
    async def _get_price(self, symbol: str) -> Optional[float]:
        """Récupère le prix d'un actif."""
        # Vérification du cache
        with self._cache_lock:
            if symbol in self._price_cache:
                return self._price_cache[symbol]
        
        # Récupération depuis le data manager
        if self.data_manager:
            price_data = await self.data_manager.retrieve(
                f"market:{symbol}:price",
                DataType.MARKET
            )
            if price_data:
                price = price_data.get("price")
                with self._cache_lock:
                    self._price_cache[symbol] = price
                return price
        
        return None
    
    async def _calculate_performance_metrics(self, portfolio: Portfolio) -> Dict[str, float]:
        """Calcule les métriques de performance."""
        metrics = {}
        
        if portfolio.initial_capital <= 0:
            return metrics
        
        # Total Return
        metrics["total_return"] = portfolio.pnl / portfolio.initial_capital
        
        # Annualized Return (simplifié)
        days = (datetime.now(timezone.utc) - portfolio.created_at).days
        if days > 0:
            metrics["annualized_return"] = (1 + metrics["total_return"]) ** (365 / days) - 1
        
        # Volatility (à partir des rendements historiques)
        returns = await self._get_historical_returns(portfolio)
        if returns:
            metrics["volatility"] = np.std(returns) * np.sqrt(252)
            metrics["sharpe_ratio"] = (metrics["annualized_return"] - self.config["risk_free_rate"]) / metrics["volatility"] if metrics["volatility"] > 0 else 0
        
        # Win Rate (à partir des trades)
        trades = await self._get_trades(portfolio)
        if trades:
            winning = sum(1 for t in trades if t.get("pnl", 0) > 0)
            metrics["win_rate"] = winning / len(trades) if trades else 0
        
        return metrics
    
    async def _calculate_risk_metrics(self, portfolio: Portfolio) -> Dict[str, float]:
        """Calcule les métriques de risque."""
        metrics = {}
        
        # Max Drawdown
        snapshots = await self._get_snapshots(portfolio.portfolio_id)
        if snapshots:
            values = [s.total_value for s in snapshots]
            peak = values[0]
            max_drawdown = 0
            
            for value in values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak if peak > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)
            
            metrics["max_drawdown"] = max_drawdown
            metrics["current_drawdown"] = (peak - values[-1]) / peak if peak > 0 else 0
        
        # Var (Value at Risk)
        returns = await self._get_historical_returns(portfolio)
        if returns and len(returns) > 20:
            metrics["var_95"] = np.percentile(returns, 5)
            metrics["var_99"] = np.percentile(returns, 1)
            metrics["cvar_95"] = np.mean([r for r in returns if r < metrics["var_95"]])
        
        # Beta
        if portfolio.assets:
            # Calcul du beta par rapport au marché (simplifié)
            metrics["beta"] = 1.0
        
        return metrics
    
    async def _get_historical_returns(self, portfolio: Portfolio) -> List[float]:
        """Récupère les rendements historiques."""
        # Dans un système réel, on récupérerait l'historique des prix
        return []
    
    async def _get_trades(self, portfolio: Portfolio) -> List[Dict]:
        """Récupère les trades du portefeuille."""
        # Dans un système réel, on récupérerait les trades depuis le data manager
        return []
    
    async def _get_snapshots(self, portfolio_id: str) -> List[PortfolioSnapshot]:
        """Récupère les snapshots d'un portefeuille."""
        with self._snapshots_lock:
            return self._snapshots.get(portfolio_id, [])
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _snapshot_loop(self) -> None:
        """Boucle de snapshots périodiques."""
        while self._is_running:
            await asyncio.sleep(self.config["snapshot_interval"])
            
            try:
                with self._portfolios_lock:
                    for portfolio in self._portfolios.values():
                        # Récupération des prix
                        prices = {}
                        for symbol in portfolio.assets:
                            price = await self._get_price(symbol)
                            if price:
                                prices[symbol] = price
                        
                        # Mise à jour du portefeuille
                        if prices:
                            updated = await self.update_portfolio(portfolio.portfolio_id, prices)
                            
                            # Création du snapshot
                            snapshot = PortfolioSnapshot(
                                portfolio_id=portfolio.portfolio_id,
                                total_value=updated.total_value,
                                cash=updated.cash,
                                assets={symbol: {"quantity": q, "price": await self._get_price(symbol)} for symbol, q in updated.assets.items()},
                                pnl=updated.pnl,
                                pnl_percent=updated.pnl_percent,
                                metrics=updated.performance_metrics
                            )
                            
                            with self._snapshots_lock:
                                self._snapshots[portfolio.portfolio_id].append(snapshot)
                                self._stats["snapshots_taken"] += 1
                
            except Exception as e:
                logger.error(f"Snapshot loop error: {e}")
    
    async def _rebalance_loop(self) -> None:
        """Boucle de rééquilibrage automatique."""
        if not self.config["enable_auto_rebalance"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["report_interval"])
            
            try:
                with self._allocations_lock:
                    for allocation in self._allocations.values():
                        if not allocation.active:
                            continue
                        
                        # Vérification du portefeuille
                        with self._portfolios_lock:
                            portfolio = self._portfolios.get(allocation.portfolio_id)
                            if not portfolio:
                                continue
                        
                        # Calcul des déviations
                        await self._check_rebalance(allocation, portfolio)
                
            except Exception as e:
                logger.error(f"Rebalance loop error: {e}")
    
    async def _check_rebalance(self, allocation: AllocationConfig, portfolio: Portfolio) -> None:
        """Vérifie si un rééquilibrage est nécessaire."""
        # Calcul des poids actuels
        current_weights = {}
        for symbol, quantity in portfolio.assets.items():
            price = await self._get_price(symbol)
            if price:
                value = quantity * price
                current_weights[symbol] = value / portfolio.total_value if portfolio.total_value > 0 else 0
        
        # Vérification des déviations
        for symbol, target_weight in allocation.target_allocation.items():
            current_weight = current_weights.get(symbol, 0)
            deviation = abs(current_weight - target_weight)
            
            if deviation > allocation.rebalance_threshold:
                logger.info(f"Rebalance needed for {symbol}: target={target_weight:.2%}, current={current_weight:.2%}")
                # Dans un système réel, on exécuterait le rééquilibrage
                self._stats["rebalances_performed"] += 1
                break
    
    async def _report_generator(self) -> None:
        """Génère des rapports périodiques."""
        while self._is_running:
            await asyncio.sleep(self.config["report_interval"])
            
            try:
                with self._portfolios_lock:
                    for portfolio in self._portfolios.values():
                        report = await self.generate_report(portfolio.portfolio_id)
                        
                        with self._reports_lock:
                            self._reports[report.report_id] = report
                            self._stats["reports_generated"] += 1
                        
                        # Stockage du rapport
                        if self.data_manager:
                            await self.data_manager.store(
                                f"portfolio:report:{report.report_id}",
                                report.to_dict(),
                                DataType.REPORT
                            )
                
            except Exception as e:
                logger.error(f"Report generator error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._portfolios_lock:
                    self._stats["total_portfolios"] = len(self._portfolios)
                    total_value = sum(p.total_value for p in self._portfolios.values())
                    self._stats["total_value"] = total_value
                    self._stats["avg_portfolio_size"] = total_value / len(self._portfolios) if self._portfolios else 0
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "portfolio:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_portfolios(self) -> None:
        """Charge les portefeuilles existants."""
        try:
            if self.data_manager:
                portfolios_data = await self.data_manager.retrieve(
                    "portfolios:all",
                    DataType.PORTFOLIO
                )
                
                if portfolios_data:
                    for p_dict in portfolios_data:
                        portfolio = self._deserialize_portfolio(p_dict)
                        if portfolio:
                            with self._portfolios_lock:
                                self._portfolios[portfolio.portfolio_id] = portfolio
            
            logger.info(f"Loaded {len(self._portfolios)} portfolios")
            
        except Exception as e:
            logger.error(f"Load portfolios error: {e}")
    
    def _deserialize_portfolio(self, data: Dict) -> Optional[Portfolio]:
        """Désérialise un portefeuille."""
        try:
            return Portfolio(
                portfolio_id=data.get("portfolio_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                portfolio_type=PortfolioType(data.get("portfolio_type", "hedge")),
                allocation_type=AllocationType(data.get("allocation_type", "dynamic")),
                assets=data.get("assets", {}),
                cash=data.get("cash", 0.0),
                total_value=data.get("total_value", 0.0),
                initial_capital=data.get("initial_capital", 0.0),
                current_capital=data.get("current_capital", 0.0),
                pnl=data.get("pnl", 0.0),
                pnl_percent=data.get("pnl_percent", 0.0),
                realized_pnl=data.get("realized_pnl", 0.0),
                unrealized_pnl=data.get("unrealized_pnl", 0.0),
                performance_metrics=data.get("performance_metrics", {}),
                risk_metrics=data.get("risk_metrics", {}),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing portfolio: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_portfolios(self) -> List[Portfolio]:
        """Récupère les portefeuilles."""
        with self._portfolios_lock:
            return list(self._portfolios.values())
    
    async def get_snapshots(self, portfolio_id: str, limit: int = 100) -> List[PortfolioSnapshot]:
        """Récupère les snapshots d'un portefeuille."""
        with self._snapshots_lock:
            snapshots = self._snapshots.get(portfolio_id, [])
            return snapshots[-limit:]
    
    async def get_report(self, report_id: str) -> Optional[PortfolioReport]:
        """Récupère un rapport."""
        with self._reports_lock:
            return self._reports.get(report_id)
    
    async def generate_report(self, portfolio_id: str) -> PortfolioReport:
        """Génère un rapport de portefeuille."""
        with self._portfolios_lock:
            portfolio = self._portfolios.get(portfolio_id)
            if not portfolio:
                raise ValueError(f"Portfolio {portfolio_id} not found")
        
        snapshots = await self.get_snapshots(portfolio_id)
        
        report = PortfolioReport(
            portfolio_id=portfolio_id,
            snapshots=snapshots,
            summary={
                "total_value": portfolio.total_value,
                "cash": portfolio.cash,
                "assets": len(portfolio.assets),
                "pnl": portfolio.pnl,
                "pnl_percent": portfolio.pnl_percent
            },
            performance=portfolio.performance_metrics,
            risk_analysis=portfolio.risk_metrics,
            recommendations=await self._generate_recommendations(portfolio)
        )
        
        with self._reports_lock:
            self._reports[report.report_id] = report
            self._stats["reports_generated"] += 1
        
        return report
    
    async def _generate_recommendations(self, portfolio: Portfolio) -> List[str]:
        """Génère des recommandations pour le portefeuille."""
        recommendations = []
        
        # Recommandations basées sur les métriques
        if portfolio.performance_metrics.get("sharpe_ratio", 0) < 0.5:
            recommendations.append("Sharpe ratio is below 0.5. Consider improving risk-adjusted returns.")
        
        if portfolio.risk_metrics.get("max_drawdown", 0) > 0.2:
            recommendations.append("Max drawdown exceeds 20%. Consider reducing risk exposure.")
        
        if portfolio.risk_metrics.get("var_95", 0) < -0.02:
            recommendations.append("VaR(95%) exceeds 2%. Consider reducing position sizes.")
        
        if len(portfolio.assets) < 3:
            recommendations.append("Portfolio is not well diversified. Consider adding more assets.")
        
        return recommendations
    
    async def create_allocation(self, config: AllocationConfig) -> str:
        """Crée une configuration d'allocation."""
        with self._allocations_lock:
            self._allocations[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"portfolio:allocation:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Allocation config created: {config.config_id}")
        return config.config_id
    
    async def get_allocation(self, config_id: str) -> Optional[AllocationConfig]:
        """Récupère une configuration d'allocation."""
        with self._allocations_lock:
            return self._allocations.get(config_id)
    
    async def get_allocations(self, portfolio_id: str) -> List[AllocationConfig]:
        """Récupère les allocations d'un portefeuille."""
        with self._allocations_lock:
            return [a for a in self._allocations.values() if a.portfolio_id == portfolio_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._portfolios_lock:
            self._stats["total_portfolios"] = len(self._portfolios)
        
        return self._stats.copy()


# ============== PORTFOLIO OPTIMIZER ==============

class PortfolioOptimizer:
    """
    Optimiseur de portefeuille.
    Optimise l'allocation pour maximiser le rendement ajusté au risque.
    """
    
    def __init__(self, manager: PortfolioManager):
        self.manager = manager
    
    async def optimize(self, portfolio_id: str, constraints: Dict[str, Any]) -> Dict[str, float]:
        """Optimise l'allocation du portefeuille."""
        portfolio = await self.manager.get_portfolio(portfolio_id)
        if not portfolio:
            return {}
        
        # Optimisation simplifiée
        # Dans un système réel, on utiliserait des algorithmes d'optimisation
        target_weights = {}
        
        # Allocation par égalité de risque
        n_assets = len(portfolio.assets) if portfolio.assets else 1
        equal_weight = 1.0 / n_assets
        
        for symbol in portfolio.assets:
            target_weights[symbol] = equal_weight
        
        return target_weights


# ============== FACTORY ==============

class PortfolioManagerFactory:
    """Factory pour créer des composants de gestion de portefeuille."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PortfolioManager:
        """Crée un gestionnaire de portefeuille."""
        manager = PortfolioManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager
    
    @staticmethod
    def create_optimizer(manager: PortfolioManager) -> PortfolioOptimizer:
        """Crée un optimiseur de portefeuille."""
        return PortfolioOptimizer(manager)


# ============== EXPORT ==============

__all__ = [
    "PortfolioType",
    "AllocationType",
    "PerformanceMetric",
    "Portfolio",
    "PortfolioSnapshot",
    "PortfolioReport",
    "AllocationConfig",
    "PortfolioManagerInterface",
    "PortfolioManager",
    "PortfolioOptimizer",
    "PortfolioManagerFactory"
]

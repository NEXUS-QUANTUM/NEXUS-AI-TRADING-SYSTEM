# trading/bots/hedge_bot/hedge_bot_position_sizer.py
# Advanced Position Sizing & Risk Allocation Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Position Sizer Module - Module avancé de dimensionnement des positions et d'allocation
des risques pour le Hedge Bot. Gère le sizing des positions, l'allocation du capital,
le risk per trade, le Kelly criterion, et l'optimisation du sizing pour les stratégies de hedging.
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
logger = get_logger("hedge_bot_position_sizer")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class SizingMethod(Enum):
    """Méthodes de dimensionnement."""
    FIXED = "fixed"                    # Taille fixe
    PERCENTAGE = "percentage"          # Pourcentage du capital
    KELLY = "kelly"                    # Kelly Criterion
    FRACTIONAL_KELLY = "fractional_kelly"  # Kelly fractionnaire
    RISK_PARITY = "risk_parity"        # Parité des risques
    VOLATILITY_BASED = "volatility_based"  # Basé sur la volatilité
    ATR_BASED = "atr_based"            # Basé sur l'ATR
    PYRAMIDING = "pyramiding"          # Pyramiding
    MARTINGALE = "martingale"          # Martingale
    ANTI_MARTINGALE = "anti_martingale"  # Anti-martingale
    OPTIMAL_F = "optimal_f"            # Optimal f


class RiskMetric(Enum):
    """Métriques de risque."""
    VAR = "var"                        # Value at Risk
    CVAR = "cvar"                      # Conditional VaR
    DRAWDOWN = "drawdown"              # Drawdown
    VOLATILITY = "volatility"          # Volatilité
    SHARPE = "sharpe"                  # Sharpe Ratio
    SORTINO = "sortino"                # Sortino Ratio
    CALMAR = "calmar"                  # Calmar Ratio


class PositionType(Enum):
    """Types de positions."""
    LONG = "long"
    SHORT = "short"
    HEDGE = "hedge"
    SCALP = "scalp"
    SWING = "swing"
    POSITION = "position"


# ============== DATA MODELS ==============

@dataclass
class PositionSizing:
    """Dimensionnement de position."""
    sizing_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    position_type: PositionType = PositionType.LONG
    method: SizingMethod = SizingMethod.PERCENTAGE
    capital: float = 0.0
    risk_per_trade: float = 0.02
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    size: float = 0.0
    units: float = 0.0
    leverage: float = 1.0
    risk_amount: float = 0.0
    potential_loss: float = 0.0
    potential_gain: float = 0.0
    risk_reward_ratio: float = 0.0
    kelly_fraction: float = 0.0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SizingConfig:
    """Configuration de dimensionnement."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    method: SizingMethod = SizingMethod.PERCENTAGE
    default_risk: float = 0.02
    max_risk: float = 0.05
    min_risk: float = 0.005
    capital_allocation: float = 0.5
    kelly_factor: float = 0.25
    volatility_lookback: int = 20
    atr_period: int = 14
    atr_multiplier: float = 2.0
    max_leverage: float = 2.0
    min_position_size: float = 0.01
    max_position_size: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class RiskMetrics:
    """Métriques de risque."""
    metrics_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    volatility: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class PositionSizerInterface(ABC):
    """Interface abstraite pour le dimensionneur de positions."""
    
    @abstractmethod
    async def calculate_size(self, config: SizingConfig, context: Dict[str, Any]) -> PositionSizing:
        """Calcule la taille de la position."""
        pass
    
    @abstractmethod
    async def calculate_risk_metrics(self, symbol: str) -> RiskMetrics:
        """Calcule les métriques de risque."""
        pass
    
    @abstractmethod
    async def optimize_sizing(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Optimise le dimensionnement."""
        pass


# ============== IMPLÉMENTATION ==============

class PositionSizer(PositionSizerInterface):
    """
    Dimensionneur de positions avancé pour le Hedge Bot.
    Gère le sizing des positions et l'allocation des risques.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des dimensionnements
        self._sizings: Dict[str, PositionSizing] = {}
        self._sizings_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, SizingConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Gestion des métriques de risque
        self._risk_metrics: Dict[str, RiskMetrics] = {}
        self._risk_lock = threading.RLock()
        
        # Cache des calculs
        self._calc_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "sizings_calculated": 0,
            "risk_metrics_calculated": 0,
            "optimizations_performed": 0,
            "avg_position_size": 0.0,
            "avg_risk_amount": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PositionSizer initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_method": SizingMethod.PERCENTAGE,
            "default_risk": 0.02,
            "max_risk": 0.05,
            "min_risk": 0.005,
            "capital_allocation": 0.5,
            "kelly_factor": 0.25,
            "volatility_lookback": 20,
            "atr_period": 14,
            "atr_multiplier": 2.0,
            "max_leverage": 2.0,
            "min_position_size": 0.01,
            "max_position_size": 0.5,
            "var_confidence": 0.95,
            "cvar_confidence": 0.99,
            "cache_size": 1000,
            "enable_cache": True
        }
    
    async def start(self) -> None:
        """Démarre le dimensionneur de positions."""
        logger.info("PositionSizer starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PositionSizer started")
    
    async def stop(self) -> None:
        """Arrête le dimensionneur de positions."""
        logger.info("PositionSizer stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("PositionSizer stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def calculate_size(self, config: SizingConfig, context: Dict[str, Any]) -> PositionSizing:
        """Calcule la taille de la position."""
        self._stats["sizings_calculated"] += 1
        
        try:
            symbol = context.get("symbol", "")
            entry_price = context.get("entry_price", 0.0)
            stop_loss = context.get("stop_loss", 0.0)
            take_profit = context.get("take_profit", 0.0)
            capital = context.get("capital", 0.0)
            
            # Validation
            if entry_price <= 0:
                raise ValueError("Invalid entry price")
            
            if stop_loss <= 0:
                raise ValueError("Invalid stop loss")
            
            # Calcul selon la méthode
            if config.method == SizingMethod.FIXED:
                size = await self._calculate_fixed(config, context)
            elif config.method == SizingMethod.PERCENTAGE:
                size = await self._calculate_percentage(config, context)
            elif config.method == SizingMethod.KELLY:
                size = await self._calculate_kelly(config, context)
            elif config.method == SizingMethod.FRACTIONAL_KELLY:
                size = await self._calculate_fractional_kelly(config, context)
            elif config.method == SizingMethod.VOLATILITY_BASED:
                size = await self._calculate_volatility_based(config, context)
            elif config.method == SizingMethod.ATR_BASED:
                size = await self._calculate_atr_based(config, context)
            elif config.method == SizingMethod.RISK_PARITY:
                size = await self._calculate_risk_parity(config, context)
            else:
                size = await self._calculate_percentage(config, context)
            
            # Création du dimensionnement
            sizing = PositionSizing(
                symbol=symbol,
                position_type=PositionType(context.get("position_type", "long")),
                method=config.method,
                capital=capital,
                risk_per_trade=config.default_risk,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                size=size,
                units=size / entry_price if entry_price > 0 else 0,
                leverage=context.get("leverage", 1.0),
                risk_amount=size * (entry_price - stop_loss) / entry_price if entry_price > 0 else 0,
                potential_loss=size * (entry_price - stop_loss) / entry_price if entry_price > 0 else 0,
                potential_gain=size * (take_profit - entry_price) / entry_price if take_profit > 0 and entry_price > 0 else 0,
                risk_reward_ratio=(take_profit - entry_price) / (entry_price - stop_loss) if take_profit > 0 and stop_loss > 0 and entry_price > 0 else 0,
                confidence=context.get("confidence", 0.5)
            )
            
            # Stockage
            with self._sizings_lock:
                self._sizings[sizing.sizing_id] = sizing
            
            # Mise à jour des statistiques
            self._stats["avg_position_size"] = (
                self._stats["avg_position_size"] * 0.9 + size * 0.1
            )
            self._stats["avg_risk_amount"] = (
                self._stats["avg_risk_amount"] * 0.9 + sizing.risk_amount * 0.1
            )
            
            logger.info(f"Position sizing calculated for {symbol}: size={size:.2f}, risk={sizing.risk_amount:.2f}")
            return sizing
            
        except Exception as e:
            logger.error(f"Sizing error: {e}")
            raise
    
    async def calculate_risk_metrics(self, symbol: str) -> RiskMetrics:
        """Calcule les métriques de risque."""
        self._stats["risk_metrics_calculated"] += 1
        
        try:
            # Récupération des données historiques
            if not self.data_manager:
                raise ValueError("Data manager not available")
            
            # Dans un système réel, on récupérerait les données historiques
            returns = np.random.normal(0, 0.02, 252)
            
            # Calcul des métriques
            var_95 = np.percentile(returns, 5)
            var_99 = np.percentile(returns, 1)
            
            # CVaR
            cvar_95 = np.mean(returns[returns <= var_95]) if len(returns[returns <= var_95]) > 0 else 0
            cvar_99 = np.mean(returns[returns <= var_99]) if len(returns[returns <= var_99]) > 0 else 0
            
            volatility = np.std(returns)
            
            # Drawdown
            cumulative = np.cumprod(1 + returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = np.min(drawdown)
            
            # Sharpe ratio
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
            
            # Sortino ratio
            downside = returns[returns < 0]
            sortino_ratio = np.mean(returns) / np.std(downside) * np.sqrt(252) if len(downside) > 0 and np.std(downside) > 0 else 0
            
            # Calmar ratio
            calmar_ratio = np.mean(returns) * 252 / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # Création des métriques
            metrics = RiskMetrics(
                symbol=symbol,
                var_95=var_95,
                var_99=var_99,
                cvar_95=cvar_95,
                cvar_99=cvar_99,
                volatility=volatility,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio
            )
            
            with self._risk_lock:
                self._risk_metrics[symbol] = metrics
            
            logger.info(f"Risk metrics calculated for {symbol}")
            return metrics
            
        except Exception as e:
            logger.error(f"Risk metrics error: {e}")
            raise
    
    async def optimize_sizing(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Optimise le dimensionnement."""
        self._stats["optimizations_performed"] += 1
        
        try:
            # Analyse des performances historiques
            historical_returns = strategy.get("historical_returns", [])
            win_rate = strategy.get("win_rate", 0.5)
            avg_win = strategy.get("avg_win", 0.02)
            avg_loss = strategy.get("avg_loss", 0.01)
            
            # Calcul du Kelly optimal
            if win_rate > 0 and avg_win > 0 and avg_loss > 0:
                kelly = win_rate / avg_loss - (1 - win_rate) / avg_win
                kelly = max(0, min(1, kelly))
            else:
                kelly = 0.25
            
            # Kelly fractionnaire
            fractional_kelly = kelly * 0.25
            
            # Optimisation du sizing
            optimal_risk = min(0.05, max(0.005, fractional_kelly))
            
            return {
                "optimal_risk": optimal_risk,
                "kelly_fraction": kelly,
                "fractional_kelly": fractional_kelly,
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "recommended_size": optimal_risk * 0.5,
                "max_size": optimal_risk * 2.0
            }
            
        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return {"error": str(e)}
    
    # ========== MÉTHODES PRIVÉES - SIZING ==========
    
    async def _calculate_fixed(self, config: SizingConfig, context: Dict[str, Any]) -> float:
        """Taille fixe."""
        return context.get("fixed_size", 1000.0)
    
    async def _calculate_percentage(self, config: SizingConfig, context: Dict[str, Any]) -> float:
        """Pourcentage du capital."""
        capital = context.get("capital", 0.0)
        risk_pct = config.default_risk
        return capital * risk_pct
    
    async def _calculate_kelly(self, config: SizingConfig, context: Dict[str, Any]) -> float:
        """Kelly Criterion."""
        win_rate = context.get("win_rate", 0.5)
        avg_win = context.get("avg_win", 0.02)
        avg_loss = context.get("avg_loss", 0.01)
        
        if avg_loss > 0 and avg_win > 0:
            kelly = win_rate / avg_loss - (1 - win_rate) / avg_win
            kelly = max(0, min(1, kelly))
        else:
            kelly = 0.25
        
        capital = context.get("capital", 0.0)
        return capital * kelly
    
    async def _calculate_fractional_kelly(self, config: SizingConfig, context: Dict[str, Any]) -> float:
        """Kelly fractionnaire."""
        win_rate = context.get("win_rate", 0.5)
        avg_win = context.get("avg_win", 0.02)
        avg_loss = context.get("avg_loss", 0.01)
        
        if avg_loss > 0 and avg_win > 0:
            kelly = win_rate / avg_loss - (1 - win_rate) / avg_win
            kelly = max(0, min(1, kelly))
        else:
            kelly = 0.25
        
        fractional = kelly * config.kelly_factor
        capital = context.get("capital", 0.0)
        return capital * fractional
    
    async def _calculate_volatility_based(self, config: SizingConfig, context: Dict[str, Any]) -> float:
        """Basé sur la volatilité."""
        volatility = context.get("volatility", 0.02)
        capital = context.get("capital", 0.0)
        risk_pct = config.default_risk
        
        # Ajustement du risque en fonction de la volatilité
        adjusted_risk = risk_pct * (0.02 / max(volatility, 0.001))
        adjusted_risk = min(config.max_risk, max(config.min_risk, adjusted_risk))
        
        return capital * adjusted_risk
    
    async def _calculate_atr_based(self, config: SizingConfig, context: Dict[str, Any]) -> float:
        """Basé sur l'ATR."""
        atr = context.get("atr", 0.01)
        entry_price = context.get("entry_price", 100.0)
        capital = context.get("capital", 0.0)
        risk_pct = config.default_risk
        
        if atr <= 0:
            return capital * risk_pct
        
        # Calcul de la taille basée sur l'ATR
        atr_pct = atr / entry_price
        size = capital * risk_pct / atr_pct
        size = min(capital * config.max_position_size, size)
        
        return size
    
    async def _calculate_risk_parity(self, config: SizingConfig, context: Dict[str, Any]) -> float:
        """Parité des risques."""
        correlations = context.get("correlations", {})
        volatilities = context.get("volatilities", {})
        capital = context.get("capital", 0.0)
        
        # Simplification: utilisation de la volatilité
        if volatilities:
            avg_vol = np.mean(list(volatilities.values()))
            size = capital * config.default_risk / avg_vol if avg_vol > 0 else 0
            return min(capital * config.max_position_size, size)
        
        return capital * config.default_risk
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._calc_cache) > self.config["cache_size"]:
                        keys = list(self._calc_cache.keys())
                        for key in keys[:len(self._calc_cache) - self.config["cache_size"]]:
                            del self._calc_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._sizings_lock:
                    self._stats["total_sizings"] = len(self._sizings)
                with self._risk_lock:
                    self._stats["total_risk_metrics"] = len(self._risk_metrics)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "sizer:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_sizing(self, sizing_id: str) -> Optional[PositionSizing]:
        """Récupère un dimensionnement."""
        with self._sizings_lock:
            return self._sizings.get(sizing_id)
    
    async def get_sizings(self) -> List[PositionSizing]:
        """Récupère les dimensionnements."""
        with self._sizings_lock:
            return list(self._sizings.values())
    
    async def create_config(self, config: SizingConfig) -> str:
        """Crée une configuration de dimensionnement."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"sizer:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Sizing config created: {config.name}")
        return config.config_id
    
    async def get_config(self, config_id: str) -> Optional[SizingConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    async def get_configs(self) -> List[SizingConfig]:
        """Récupère les configurations."""
        with self._configs_lock:
            return list(self._configs.values())
    
    async def get_risk_metrics(self, symbol: str) -> Optional[RiskMetrics]:
        """Récupère les métriques de risque."""
        with self._risk_lock:
            return self._risk_metrics.get(symbol)
    
    async def get_all_risk_metrics(self) -> List[RiskMetrics]:
        """Récupère toutes les métriques de risque."""
        with self._risk_lock:
            return list(self._risk_metrics.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._sizings_lock:
            self._stats["total_sizings"] = len(self._sizings)
        with self._risk_lock:
            self._stats["total_risk_metrics"] = len(self._risk_metrics)
        
        return self._stats.copy()


# ============== POSITION SIZING OPTIMIZER ==============

class PositionSizingOptimizer:
    """
    Optimiseur de dimensionnement de positions.
    Optimise le sizing pour maximiser le rendement ajusté au risque.
    """
    
    def __init__(self, sizer: PositionSizer):
        self.sizer = sizer
    
    async def optimize_portfolio(self, symbols: List[str], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Optimise le dimensionnement d'un portefeuille."""
        # Calcul des métriques de risque
        risk_metrics = {}
        for symbol in symbols:
            metrics = await self.sizer.calculate_risk_metrics(symbol)
            risk_metrics[symbol] = metrics
        
        # Optimisation de l'allocation
        total_risk = sum(metrics.volatility for metrics in risk_metrics.values())
        
        allocation = {}
        for symbol, metrics in risk_metrics.items():
            if total_risk > 0:
                allocation[symbol] = metrics.volatility / total_risk
            else:
                allocation[symbol] = 1.0 / len(symbols)
        
        return {
            "allocation": allocation,
            "risk_metrics": risk_metrics,
            "total_risk": total_risk,
            "optimal_weights": allocation
        }


# ============== FACTORY ==============

class PositionSizerFactory:
    """Factory pour créer des composants de dimensionnement."""
    
    @staticmethod
    async def create_sizer(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PositionSizer:
        """Crée un dimensionneur de positions."""
        sizer = PositionSizer(
            data_manager=data_manager,
            config=config
        )
        await sizer.start()
        return sizer
    
    @staticmethod
    def create_optimizer(sizer: PositionSizer) -> PositionSizingOptimizer:
        """Crée un optimiseur de dimensionnement."""
        return PositionSizingOptimizer(sizer)


# ============== EXPORT ==============

__all__ = [
    "SizingMethod",
    "RiskMetric",
    "PositionType",
    "PositionSizing",
    "SizingConfig",
    "RiskMetrics",
    "PositionSizerInterface",
    "PositionSizer",
    "PositionSizingOptimizer",
    "PositionSizerFactory"
]

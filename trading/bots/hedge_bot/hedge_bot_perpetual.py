# trading/bots/hedge_bot/hedge_bot_perpetual.py
# Advanced Perpetual Futures & Funding Rate Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Perpetual Module - Module avancé de gestion des futures perpétuels et des taux de funding
pour le Hedge Bot. Gère les positions sur les perpétuels, le calcul des taux de funding,
l'optimisation des coûts de financement, et les stratégies de hedging avec les perpétuels.
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
logger = get_logger("hedge_bot_perpetual")

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

class PerpetualPosition(Enum):
    """Types de positions perpétuelles."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class FundingRate(Enum):
    """Modes de calcul du taux de funding."""
    PREDICTIVE = "predictive"          # Prédictif (basé sur les prévisions)
    REAL_TIME = "real_time"            # Temps réel
    HISTORICAL = "historical"          # Historique
    AVERAGE = "average"                # Moyenne


class PerpetualStrategy(Enum):
    """Stratégies perpétuelles."""
    HEDGE = "hedge"                    # Hedging
    ARBITRAGE = "arbitrage"            # Arbitrage funding rate
    BASKET = "basket"                  # Panier de perpétuels
    CASH_AND_CARRY = "cash_and_carry"  # Cash and carry
    DYNAMIC = "dynamic"                # Dynamique


# ============== DATA MODELS ==============

@dataclass
class PerpetualPosition:
    """Position perpétuelle."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    position_type: PerpetualPosition = PerpetualPosition.LONG
    entry_price: float = 0.0
    current_price: float = 0.0
    quantity: float = 0.0
    leverage: float = 1.0
    margin: float = 0.0
    liquidation_price: float = 0.0
    funding_rate: float = 0.0
    funding_rate_paid: float = 0.0
    funding_rate_received: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    strategy: PerpetualStrategy = PerpetualStrategy.HEDGE


@dataclass
class FundingRateData:
    """Données de taux de funding."""
    data_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    funding_rate: float = 0.0
    predicted_rate: float = 0.0
    historical_rate: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    interval: int = 8  # heures
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerpetualConfig:
    """Configuration perpétuelle."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    symbols: List[str] = field(default_factory=list)
    max_leverage: float = 10.0
    min_leverage: float = 1.0
    max_position_size: float = 1000000
    funding_rate_threshold: float = 0.0001
    funding_rate_check_interval: int = 3600
    auto_hedge: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


# ============== INTERFACES ==============

class PerpetualEngineInterface(ABC):
    """Interface abstraite pour le moteur perpétuel."""
    
    @abstractmethod
    async def open_position(self, config: Dict[str, Any]) -> PerpetualPosition:
        """Ouvre une position perpétuelle."""
        pass
    
    @abstractmethod
    async def close_position(self, position_id: str) -> bool:
        """Ferme une position perpétuelle."""
        pass
    
    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> FundingRateData:
        """Récupère le taux de funding."""
        pass
    
    @abstractmethod
    async def calculate_funding_cost(self, position: PerpetualPosition) -> float:
        """Calcule le coût de funding."""
        pass


# ============== IMPLÉMENTATION ==============

class PerpetualEngine(PerpetualEngineInterface):
    """
    Moteur perpétuel avancé pour le Hedge Bot.
    Gère les positions sur les perpétuels et les taux de funding.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des positions
        self._positions: Dict[str, PerpetualPosition] = {}
        self._positions_lock = threading.RLock()
        
        # Gestion des taux de funding
        self._funding_rates: Dict[str, FundingRateData] = {}
        self._funding_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, PerpetualConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Cache des prix
        self._price_cache: Dict[str, float] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "positions_opened": 0,
            "positions_closed": 0,
            "funding_rate_checks": 0,
            "total_funding_paid": 0.0,
            "total_funding_received": 0.0,
            "net_funding_cost": 0.0,
            "avg_leverage": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PerpetualEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_leverage": 3.0,
            "max_leverage": 10.0,
            "min_leverage": 1.0,
            "funding_rate_check_interval": 3600,
            "funding_rate_threshold": 0.0001,
            "auto_hedge": True,
            "max_position_size": 1000000,
            "min_position_size": 0.01,
            "default_strategy": PerpetualStrategy.HEDGE,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_auto_funding": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur perpétuel."""
        logger.info("PerpetualEngine starting...")
        self._is_running = True
        
        # Chargement des positions
        await self._load_positions()
        
        # Chargement des configurations
        await self._load_configs()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._funding_rate_monitor())
        asyncio.create_task(self._auto_hedge_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PerpetualEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur perpétuel."""
        logger.info("PerpetualEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("PerpetualEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def open_position(self, config: Dict[str, Any]) -> PerpetualPosition:
        """Ouvre une position perpétuelle."""
        self._stats["positions_opened"] += 1
        
        symbol = config.get("symbol", "")
        position_type = PerpetualPosition(config.get("position_type", "long"))
        quantity = config.get("quantity", 0.0)
        leverage = config.get("leverage", 3.0)
        entry_price = config.get("entry_price", 0.0)
        
        # Validation
        if entry_price <= 0:
            raise ValueError("Invalid entry price")
        
        if quantity <= 0:
            raise ValueError("Invalid quantity")
        
        if leverage > self.config["max_leverage"]:
            raise ValueError(f"Leverage exceeds maximum: {leverage}")
        
        # Création de la position
        position = PerpetualPosition(
            symbol=symbol,
            position_type=position_type,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            margin=quantity * entry_price / leverage,
            liquidation_price=self._calculate_liquidation_price(entry_price, leverage, position_type),
            funding_rate=await self._get_current_funding_rate(symbol),
            strategy=PerpetualStrategy(config.get("strategy", "hedge")),
            metadata=config.get("metadata", {})
        )
        
        with self._positions_lock:
            self._positions[position.position_id] = position
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"perpetual:position:{position.position_id}",
                position.to_dict(),
                DataType.POSITION
            )
        
        logger.info(f"Perpetual position opened: {symbol} {position_type.value} qty={quantity} lev={leverage}x")
        return position
    
    async def close_position(self, position_id: str) -> bool:
        """Ferme une position perpétuelle."""
        with self._positions_lock:
            position = self._positions.get(position_id)
            if not position:
                return False
        
        # Mise à jour du PnL
        current_price = await self._get_current_price(position.symbol)
        if current_price:
            if position.position_type == PerpetualPosition.LONG:
                position.pnl = (current_price - position.entry_price) * position.quantity * position.leverage
            else:
                position.pnl = (position.entry_price - current_price) * position.quantity * position.leverage
            
            position.pnl_percent = (position.pnl / position.margin) * 100
        
        self._stats["positions_closed"] += 1
        self._stats["avg_leverage"] = (
            self._stats["avg_leverage"] * 0.9 + position.leverage * 0.1
        )
        
        # Suppression de la position
        with self._positions_lock:
            del self._positions[position_id]
        
        logger.info(f"Perpetual position closed: {position.symbol} pnl={position.pnl:.2f}")
        return True
    
    async def get_funding_rate(self, symbol: str) -> FundingRateData:
        """Récupère le taux de funding."""
        self._stats["funding_rate_checks"] += 1
        
        # Vérification du cache
        with self._funding_lock:
            if symbol in self._funding_rates:
                data = self._funding_rates[symbol]
                age = (datetime.now(timezone.utc) - data.timestamp).total_seconds()
                if age < self.config["funding_rate_check_interval"]:
                    return data
        
        # Récupération du taux
        funding_data = await self._fetch_funding_rate(symbol)
        
        with self._funding_lock:
            self._funding_rates[symbol] = funding_data
        
        return funding_data
    
    async def calculate_funding_cost(self, position: PerpetualPosition) -> float:
        """Calcule le coût de funding."""
        funding_rate = await self.get_funding_rate(position.symbol)
        
        # Calcul du coût de funding
        position_value = position.quantity * position.current_price
        funding_cost = position_value * funding_rate.funding_rate
        
        # Ajustement selon la position
        if position.position_type == PerpetualPosition.LONG:
            funding_cost = -funding_cost  # Les longs paient quand le taux est positif
        
        return funding_cost
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    def _calculate_liquidation_price(self, entry_price: float, leverage: float, position_type: PerpetualPosition) -> float:
        """Calcule le prix de liquidation."""
        if position_type == PerpetualPosition.LONG:
            return entry_price * (1 - 1 / leverage)
        else:
            return entry_price * (1 + 1 / leverage)
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Récupère le prix actuel."""
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
    
    async def _get_current_funding_rate(self, symbol: str) -> float:
        """Récupère le taux de funding actuel."""
        funding_data = await self.get_funding_rate(symbol)
        return funding_data.funding_rate
    
    async def _fetch_funding_rate(self, symbol: str) -> FundingRateData:
        """Récupère le taux de funding depuis la source."""
        # Simulation de taux de funding
        # Dans un système réel, on interrogerait l'exchange
        
        # Taux de funding aléatoire entre -0.001 et 0.001
        rate = np.random.uniform(-0.001, 0.001)
        
        return FundingRateData(
            symbol=symbol,
            funding_rate=rate,
            predicted_rate=rate * 1.1,
            historical_rate=rate * 0.9
        )
    
    # ========== MÉTHODES PRIVÉES - MONITORING ==========
    
    async def _funding_rate_monitor(self) -> None:
        """Monitor les taux de funding."""
        while self._is_running:
            await asyncio.sleep(self.config["funding_rate_check_interval"])
            
            try:
                with self._positions_lock:
                    for position in self._positions.values():
                        # Mise à jour du taux de funding
                        funding_data = await self.get_funding_rate(position.symbol)
                        position.funding_rate = funding_data.funding_rate
                        
                        # Mise à jour du coût de funding
                        funding_cost = await self.calculate_funding_cost(position)
                        
                        if funding_cost > 0:
                            position.funding_rate_received += funding_cost
                            self._stats["total_funding_received"] += funding_cost
                        else:
                            position.funding_rate_paid += abs(funding_cost)
                            self._stats["total_funding_paid"] += abs(funding_cost)
                        
                        self._stats["net_funding_cost"] += funding_cost
                
            except Exception as e:
                logger.error(f"Funding rate monitor error: {e}")
    
    async def _auto_hedge_loop(self) -> None:
        """Boucle de hedging automatique."""
        if not self.config["auto_hedge"]:
            return
        
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._positions_lock:
                    for position in self._positions.values():
                        # Vérification du taux de funding
                        funding_rate = position.funding_rate
                        
                        if abs(funding_rate) > self.config["funding_rate_threshold"]:
                            # Ajustement du hedging
                            logger.info(f"Funding rate threshold exceeded for {position.symbol}: {funding_rate:.6f}")
                            
                            # Dans un système réel, on ajusterait les positions
                            await self._adjust_hedge(position)
                
            except Exception as e:
                logger.error(f"Auto-hedge loop error: {e}")
    
    async def _adjust_hedge(self, position: PerpetualPosition) -> None:
        """Ajuste le hedging en fonction du taux de funding."""
        # Simulation d'ajustement
        logger.info(f"Adjusting hedge for {position.symbol}")
        self._stats["positions_opened"] += 1
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_positions(self) -> None:
        """Charge les positions existantes."""
        try:
            if self.data_manager:
                positions_data = await self.data_manager.retrieve(
                    "perpetual:positions",
                    DataType.POSITION
                )
                
                if positions_data:
                    for p_dict in positions_data:
                        position = self._deserialize_position(p_dict)
                        if position:
                            with self._positions_lock:
                                self._positions[position.position_id] = position
            
            logger.info(f"Loaded {len(self._positions)} perpetual positions")
            
        except Exception as e:
            logger.error(f"Load positions error: {e}")
    
    async def _load_configs(self) -> None:
        """Charge les configurations."""
        try:
            if self.data_manager:
                configs_data = await self.data_manager.retrieve(
                    "perpetual:configs",
                    DataType.CONFIG
                )
                
                if configs_data:
                    for c_dict in configs_data:
                        config = self._deserialize_config(c_dict)
                        if config:
                            with self._configs_lock:
                                self._configs[config.config_id] = config
            
            logger.info(f"Loaded {len(self._configs)} perpetual configs")
            
        except Exception as e:
            logger.error(f"Load configs error: {e}")
    
    def _deserialize_position(self, data: Dict) -> Optional[PerpetualPosition]:
        """Désérialise une position."""
        try:
            return PerpetualPosition(
                position_id=data.get("position_id", str(uuid.uuid4())),
                symbol=data.get("symbol", ""),
                position_type=PerpetualPosition(data.get("position_type", "long")),
                entry_price=data.get("entry_price", 0.0),
                current_price=data.get("current_price", 0.0),
                quantity=data.get("quantity", 0.0),
                leverage=data.get("leverage", 1.0),
                margin=data.get("margin", 0.0),
                liquidation_price=data.get("liquidation_price", 0.0),
                funding_rate=data.get("funding_rate", 0.0),
                funding_rate_paid=data.get("funding_rate_paid", 0.0),
                funding_rate_received=data.get("funding_rate_received", 0.0),
                pnl=data.get("pnl", 0.0),
                pnl_percent=data.get("pnl_percent", 0.0),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                strategy=PerpetualStrategy(data.get("strategy", "hedge"))
            )
        except Exception as e:
            logger.error(f"Error deserializing position: {e}")
            return None
    
    def _deserialize_config(self, data: Dict) -> Optional[PerpetualConfig]:
        """Désérialise une configuration."""
        try:
            return PerpetualConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                symbols=data.get("symbols", []),
                max_leverage=data.get("max_leverage", 10.0),
                min_leverage=data.get("min_leverage", 1.0),
                max_position_size=data.get("max_position_size", 1000000),
                funding_rate_threshold=data.get("funding_rate_threshold", 0.0001),
                funding_rate_check_interval=data.get("funding_rate_check_interval", 3600),
                auto_hedge=data.get("auto_hedge", True),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing config: {e}")
            return None
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._positions_lock:
                    self._stats["total_positions"] = len(self._positions)
                    total_value = sum(p.quantity * p.current_price for p in self._positions.values())
                    self._stats["total_exposure"] = total_value
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "perpetual:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_position(self, position_id: str) -> Optional[PerpetualPosition]:
        """Récupère une position."""
        with self._positions_lock:
            return self._positions.get(position_id)
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[PerpetualPosition]:
        """Récupère les positions."""
        with self._positions_lock:
            positions = list(self._positions.values())
            if symbol:
                positions = [p for p in positions if p.symbol == symbol]
            return positions
    
    async def get_funding_data(self, symbol: str) -> Optional[FundingRateData]:
        """Récupère les données de funding."""
        with self._funding_lock:
            return self._funding_rates.get(symbol)
    
    async def create_config(self, config: PerpetualConfig) -> str:
        """Crée une configuration."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"perpetual:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Perpetual config created: {config.name}")
        return config.config_id
    
    async def get_config(self, config_id: str) -> Optional[PerpetualConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._positions_lock:
            self._stats["total_positions"] = len(self._positions)
        
        return self._stats.copy()


# ============== FUNDING RATE ARBITRAGE ==============

class FundingRateArbitrage:
    """
    Arbitrage de taux de funding.
    Optimise les positions en fonction des taux de funding.
    """
    
    def __init__(self, engine: PerpetualEngine):
        self.engine = engine
    
    async def analyze_opportunities(self) -> List[Dict[str, Any]]:
        """Analyse les opportunités d'arbitrage."""
        opportunities = []
        
        # Récupération des taux de funding
        symbols = await self._get_available_symbols()
        
        for symbol in symbols:
            funding_data = await self.engine.get_funding_data(symbol)
            if not funding_data:
                continue
            
            # Analyse du taux de funding
            rate = funding_data.funding_rate
            
            if rate > 0.0005:
                # Taux de funding élevé -> vendre (short)
                opportunities.append({
                    "symbol": symbol,
                    "action": "short",
                    "funding_rate": rate,
                    "confidence": min(1.0, rate / 0.001),
                    "expected_return": rate * 8  # 8 heures
                })
            elif rate < -0.0005:
                # Taux de funding bas -> acheter (long)
                opportunities.append({
                    "symbol": symbol,
                    "action": "long",
                    "funding_rate": rate,
                    "confidence": min(1.0, abs(rate) / 0.001),
                    "expected_return": abs(rate) * 8
                })
        
        return opportunities
    
    async def _get_available_symbols(self) -> List[str]:
        """Récupère les symboles disponibles."""
        # Dans un système réel, on récupérerait les symboles depuis l'exchange
        return ["BTC-USDT", "ETH-USDT", "SOL-USDT", "AVAX-USDT"]


# ============== FACTORY ==============

class PerpetualFactory:
    """Factory pour créer des composants perpétuels."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PerpetualEngine:
        """Crée un moteur perpétuel."""
        engine = PerpetualEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_arbitrage(engine: PerpetualEngine) -> FundingRateArbitrage:
        """Crée un arbitrage de taux de funding."""
        return FundingRateArbitrage(engine)


# ============== EXPORT ==============

__all__ = [
    "PerpetualPosition",
    "FundingRate",
    "PerpetualStrategy",
    "PerpetualPosition",
    "FundingRateData",
    "PerpetualConfig",
    "PerpetualEngineInterface",
    "PerpetualEngine",
    "FundingRateArbitrage",
    "PerpetualFactory"
]

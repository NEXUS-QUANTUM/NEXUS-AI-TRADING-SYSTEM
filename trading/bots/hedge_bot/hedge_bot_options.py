# trading/bots/hedge_bot/hedge_bot_options.py
# Advanced Options Trading & Strategy Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Options Module - Module avancé de trading d'options et de gestion des stratégies
pour le Hedge Bot. Gère le trading d'options, les stratégies complexes, le pricing,
les grecques, et le hedging des positions optionnelles.
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
from scipy.stats import norm

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_options")

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

class OptionType(Enum):
    """Types d'options."""
    CALL = "call"
    PUT = "put"


class OptionStyle(Enum):
    """Styles d'options."""
    EUROPEAN = "european"
    AMERICAN = "american"
    EXOTIC = "exotic"


class OptionStrategy(Enum):
    """Stratégies d'options."""
    SINGLE = "single"                  # Achat/vente simple
    COVERED = "covered"                # Covered call / protective put
    STRADDLE = "straddle"              # Straddle
    STRANGLE = "strangle"              # Strangle
    SPREAD = "spread"                  # Spread
    IRON_CONDOR = "iron_condor"        # Iron Condor
    BUTTERFLY = "butterfly"            # Butterfly
    CALENDAR = "calendar"              # Calendar spread
    DIAGONAL = "diagonal"              # Diagonal spread
    COLLAR = "collar"                  # Collar
    VERTICAL = "vertical"              # Vertical spread
    HORIZONTAL = "horizontal"          # Horizontal spread
    HEDGE = "hedge"                    # Options hedging


class OptionStatus(Enum):
    """Statuts des options."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
    EXERCISED = "exercised"
    CANCELLED = "cancelled"


# ============== DATA MODELS ==============

@dataclass
class OptionContract:
    """Contrat d'option."""
    option_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    option_type: OptionType = OptionType.CALL
    strike: float = 0.0
    expiration: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    premium: float = 0.0
    quantity: int = 1
    style: OptionStyle = OptionStyle.EUROPEAN
    status: OptionStatus = OptionStatus.PENDING
    entry_price: float = 0.0
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    greeks: Dict[str, float] = field(default_factory=dict)
    strategy: OptionStrategy = OptionStrategy.SINGLE
    underlying_price: float = 0.0
    implied_volatility: float = 0.0
    days_to_expiry: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    hedge_ratio: float = 0.0
    position_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "option_id": self.option_id,
            "symbol": self.symbol,
            "option_type": self.option_type.value,
            "strike": self.strike,
            "expiration": self.expiration.isoformat(),
            "premium": self.premium,
            "quantity": self.quantity,
            "style": self.style.value,
            "status": self.status.value,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "greeks": self.greeks,
            "strategy": self.strategy.value,
            "underlying_price": self.underlying_price,
            "implied_volatility": self.implied_volatility,
            "days_to_expiry": self.days_to_expiry,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "metadata": self.metadata,
            "tags": self.tags,
            "hedge_ratio": self.hedge_ratio,
            "position_id": self.position_id
        }


@dataclass
class OptionStrategyConfig:
    """Configuration de stratégie d'options."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: OptionStrategy = OptionStrategy.SINGLE
    legs: List[Dict[str, Any]] = field(default_factory=list)
    target_delta: float = 0.5
    target_gamma: float = 0.0
    target_vega: float = 0.0
    max_premium: float = 1000.0
    min_premium: float = 0.0
    expiration_range: Tuple[int, int] = (7, 30)
    strike_range: Tuple[float, float] = (0.9, 1.1)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class OptionGreeks:
    """Grecques d'options."""
    greeks_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    option_id: str = ""
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    iv: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class OptionsEngineInterface(ABC):
    """Interface abstraite pour le moteur d'options."""
    
    @abstractmethod
    async def create_contract(self, config: Dict[str, Any]) -> OptionContract:
        """Crée un contrat d'option."""
        pass
    
    @abstractmethod
    async def calculate_greeks(self, option: OptionContract) -> OptionGreeks:
        """Calcule les grecques."""
        pass
    
    @abstractmethod
    async def execute_strategy(self, strategy: OptionStrategyConfig) -> List[OptionContract]:
        """Exécute une stratégie d'options."""
        pass
    
    @abstractmethod
    async def close_contract(self, option_id: str) -> bool:
        """Ferme un contrat d'option."""
        pass


# ============== IMPLÉMENTATION ==============

class OptionsEngine(OptionsEngineInterface):
    """
    Moteur d'options avancé pour le Hedge Bot.
    Gère le trading d'options et les stratégies complexes.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des contrats
        self._contracts: Dict[str, OptionContract] = {}
        self._contracts_lock = threading.RLock()
        
        # Gestion des stratégies
        self._strategies: Dict[str, OptionStrategyConfig] = {}
        self._strategies_lock = threading.RLock()
        
        # Gestion des grecques
        self._greeks_cache: Dict[str, OptionGreeks] = {}
        self._greeks_lock = threading.RLock()
        
        # Cache des prix
        self._price_cache: Dict[str, float] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "contracts_created": 0,
            "contracts_closed": 0,
            "strategies_executed": 0,
            "total_premium": 0.0,
            "total_pnl": 0.0,
            "avg_iv": 0.0,
            "avg_delta": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("OptionsEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_option_style": OptionStyle.EUROPEAN,
            "default_strategy": OptionStrategy.SINGLE,
            "max_contracts": 1000,
            "min_premium": 0.01,
            "max_premium": 10000,
            "risk_free_rate": 0.02,
            "default_iv": 0.2,
            "greeks_cache_ttl": 3600,
            "price_cache_ttl": 60,
            "enable_auto_hedge": True,
            "hedge_threshold": 0.05,
            "max_legs": 10,
            "expiration_buffer": 7
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'options."""
        logger.info("OptionsEngine starting...")
        self._is_running = True
        
        # Chargement des contrats
        await self._load_contracts()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._greeks_updater())
        asyncio.create_task(self._expiration_monitor())
        asyncio.create_task(self._auto_hedge_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("OptionsEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'options."""
        logger.info("OptionsEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("OptionsEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_contract(self, config: Dict[str, Any]) -> OptionContract:
        """Crée un contrat d'option."""
        self._stats["contracts_created"] += 1
        
        contract = OptionContract(
            symbol=config.get("symbol", ""),
            option_type=OptionType(config.get("option_type", "call")),
            strike=config.get("strike", 0.0),
            expiration=config.get("expiration", datetime.now(timezone.utc) + timedelta(days=30)),
            premium=config.get("premium", 0.0),
            quantity=config.get("quantity", 1),
            style=OptionStyle(config.get("style", "european")),
            strategy=OptionStrategy(config.get("strategy", "single")),
            underlying_price=config.get("underlying_price", 0.0),
            implied_volatility=config.get("implied_volatility", 0.2),
            hedge_ratio=config.get("hedge_ratio", 0.0),
            position_id=config.get("position_id"),
            metadata=config.get("metadata", {})
        )
        
        # Calcul des jours jusqu'à expiration
        contract.days_to_expiry = max(0, (contract.expiration - datetime.now(timezone.utc)).days)
        
        # Calcul des grecques
        greeks = await self.calculate_greeks(contract)
        contract.greeks = {
            "delta": greeks.delta,
            "gamma": greeks.gamma,
            "vega": greeks.vega,
            "theta": greeks.theta,
            "rho": greeks.rho
        }
        
        # Détermination du statut
        contract.status = OptionStatus.OPEN
        
        with self._contracts_lock:
            self._contracts[contract.option_id] = contract
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"option:{contract.option_id}",
                contract.to_dict(),
                DataType.OPTION
            )
        
        # Mise à jour des statistiques
        self._stats["total_premium"] += contract.premium
        
        logger.info(f"Option contract created: {contract.symbol} {contract.option_type.value} strike={contract.strike}")
        return contract
    
    async def calculate_greeks(self, option: OptionContract) -> OptionGreeks:
        """Calcule les grecques."""
        # Vérification du cache
        with self._greeks_lock:
            if option.option_id in self._greeks_cache:
                cached = self._greeks_cache[option.option_id]
                age = (datetime.now(timezone.utc) - cached.timestamp).total_seconds()
                if age < self.config["greeks_cache_ttl"]:
                    return cached
        
        # Calcul Black-Scholes
        S = option.underlying_price or 100.0
        K = option.strike
        T = option.days_to_expiry / 365.0
        r = self.config["risk_free_rate"]
        sigma = option.implied_volatility or self.config["default_iv"]
        
        if T <= 0:
            # Option expirée
            greeks = OptionGreeks(
                option_id=option.option_id,
                delta=0.0,
                gamma=0.0,
                vega=0.0,
                theta=0.0,
                rho=0.0,
                iv=sigma
            )
        else:
            d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            nd1 = norm.cdf(d1)
            nd2 = norm.cdf(d2)
            pdf_d1 = norm.pdf(d1)
            
            if option.option_type == OptionType.CALL:
                delta = nd1
                theta = (-S * pdf_d1 * sigma / (2 * math.sqrt(T)) 
                        - r * K * math.exp(-r * T) * nd2) / 365
            else:
                delta = nd1 - 1
                theta = (-S * pdf_d1 * sigma / (2 * math.sqrt(T)) 
                        + r * K * math.exp(-r * T) * (1 - nd2)) / 365
            
            gamma = pdf_d1 / (S * sigma * math.sqrt(T))
            vega = S * pdf_d1 * math.sqrt(T) / 100
            rho = K * T * math.exp(-r * T) * nd2 / 100 if option.option_type == OptionType.CALL else -K * T * math.exp(-r * T) * (1 - nd2) / 100
            
            greeks = OptionGreeks(
                option_id=option.option_id,
                delta=delta,
                gamma=gamma,
                vega=vega,
                theta=theta,
                rho=rho,
                iv=sigma
            )
        
        with self._greeks_lock:
            self._greeks_cache[option.option_id] = greeks
        
        return greeks
    
    async def execute_strategy(self, strategy: OptionStrategyConfig) -> List[OptionContract]:
        """Exécute une stratégie d'options."""
        self._stats["strategies_executed"] += 1
        
        contracts = []
        
        for leg in strategy.legs:
            # Création du contrat
            contract_config = {
                "symbol": leg.get("symbol", ""),
                "option_type": leg.get("option_type", "call"),
                "strike": leg.get("strike", 0.0),
                "expiration": leg.get("expiration", datetime.now(timezone.utc) + timedelta(days=30)),
                "quantity": leg.get("quantity", 1),
                "strategy": strategy.strategy.value,
                "hedge_ratio": leg.get("hedge_ratio", 0.0)
            }
            
            contract = await self.create_contract(contract_config)
            contracts.append(contract)
        
        logger.info(f"Strategy executed: {strategy.strategy.value} with {len(contracts)} legs")
        return contracts
    
    async def close_contract(self, option_id: str) -> bool:
        """Ferme un contrat d'option."""
        with self._contracts_lock:
            contract = self._contracts.get(option_id)
            if not contract or contract.status in [OptionStatus.CLOSED, OptionStatus.EXPIRED]:
                return False
            
            # Mise à jour du PnL
            contract.pnl = (contract.current_price - contract.entry_price) * contract.quantity
            contract.pnl_percent = (contract.pnl / contract.entry_price) * 100 if contract.entry_price > 0 else 0
            contract.status = OptionStatus.CLOSED
            contract.closed_at = datetime.now(timezone.utc)
            
            self._stats["contracts_closed"] += 1
            self._stats["total_pnl"] += contract.pnl
        
        logger.info(f"Option contract closed: {option_id} pnl={contract.pnl:.2f}")
        return True
    
    # ========== MÉTHODES PRIVÉES - MONITORING ==========
    
    async def _greeks_updater(self) -> None:
        """Met à jour les grecques périodiquement."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._contracts_lock:
                    for contract in self._contracts.values():
                        if contract.status == OptionStatus.OPEN:
                            # Mise à jour des grecques
                            greeks = await self.calculate_greeks(contract)
                            contract.greeks = {
                                "delta": greeks.delta,
                                "gamma": greeks.gamma,
                                "vega": greeks.vega,
                                "theta": greeks.theta,
                                "rho": greeks.rho
                            }
                
            except Exception as e:
                logger.error(f"Greeks updater error: {e}")
    
    async def _expiration_monitor(self) -> None:
        """Monitor les expirations."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                now = datetime.now(timezone.utc)
                
                with self._contracts_lock:
                    for contract in self._contracts.values():
                        if contract.status == OptionStatus.OPEN:
                            # Mise à jour des jours jusqu'à expiration
                            contract.days_to_expiry = max(0, (contract.expiration - now).days)
                            
                            # Expiration
                            if contract.days_to_expiry <= 0:
                                contract.status = OptionStatus.EXPIRED
                                await self._handle_expiration(contract)
                
            except Exception as e:
                logger.error(f"Expiration monitor error: {e}")
    
    async def _handle_expiration(self, contract: OptionContract) -> None:
        """Gère l'expiration d'un contrat."""
        # Dans un système réel, on gérerait l'exercice automatique
        logger.info(f"Option expired: {contract.option_id}")
    
    async def _auto_hedge_loop(self) -> None:
        """Boucle de hedging automatique."""
        if not self.config["enable_auto_hedge"]:
            return
        
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._contracts_lock:
                    for contract in self._contracts.values():
                        if contract.status == OptionStatus.OPEN:
                            # Vérification du delta
                            delta = contract.greeks.get("delta", 0)
                            
                            if abs(delta) > self.config["hedge_threshold"]:
                                # Dans un système réel, on exécuterait un hedge
                                logger.info(f"Auto-hedge triggered for {contract.option_id}: delta={delta:.2f}")
                
            except Exception as e:
                logger.error(f"Auto-hedge loop error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._contracts_lock:
                    self._stats["total_contracts"] = len(self._contracts)
                    open_contracts = len([c for c in self._contracts.values() if c.status == OptionStatus.OPEN])
                    self._stats["open_contracts"] = open_contracts
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "options:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_contracts(self) -> None:
        """Charge les contrats existants."""
        try:
            if self.data_manager:
                contracts_data = await self.data_manager.retrieve(
                    "options:contracts",
                    DataType.OPTION
                )
                
                if contracts_data:
                    for c_dict in contracts_data:
                        contract = self._deserialize_contract(c_dict)
                        if contract:
                            with self._contracts_lock:
                                self._contracts[contract.option_id] = contract
            
            logger.info(f"Loaded {len(self._contracts)} option contracts")
            
        except Exception as e:
            logger.error(f"Load contracts error: {e}")
    
    def _deserialize_contract(self, data: Dict) -> Optional[OptionContract]:
        """Désérialise un contrat."""
        try:
            return OptionContract(
                option_id=data.get("option_id", str(uuid.uuid4())),
                symbol=data.get("symbol", ""),
                option_type=OptionType(data.get("option_type", "call")),
                strike=data.get("strike", 0.0),
                expiration=datetime.fromisoformat(data.get("expiration", datetime.now(timezone.utc).isoformat())),
                premium=data.get("premium", 0.0),
                quantity=data.get("quantity", 1),
                style=OptionStyle(data.get("style", "european")),
                status=OptionStatus(data.get("status", "pending")),
                entry_price=data.get("entry_price", 0.0),
                current_price=data.get("current_price", 0.0),
                pnl=data.get("pnl", 0.0),
                pnl_percent=data.get("pnl_percent", 0.0),
                greeks=data.get("greeks", {}),
                strategy=OptionStrategy(data.get("strategy", "single")),
                underlying_price=data.get("underlying_price", 0.0),
                implied_volatility=data.get("implied_volatility", 0.0),
                days_to_expiry=data.get("days_to_expiry", 0),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                closed_at=datetime.fromisoformat(data.get("closed_at")) if data.get("closed_at") else None,
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                hedge_ratio=data.get("hedge_ratio", 0.0),
                position_id=data.get("position_id")
            )
        except Exception as e:
            logger.error(f"Error deserializing contract: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_contract(self, option_id: str) -> Optional[OptionContract]:
        """Récupère un contrat."""
        with self._contracts_lock:
            return self._contracts.get(option_id)
    
    async def get_contracts(self, status: Optional[OptionStatus] = None) -> List[OptionContract]:
        """Récupère les contrats."""
        with self._contracts_lock:
            contracts = list(self._contracts.values())
            if status:
                contracts = [c for c in contracts if c.status == status]
            return contracts
    
    async def create_strategy_config(self, config: OptionStrategyConfig) -> str:
        """Crée une configuration de stratégie."""
        with self._strategies_lock:
            self._strategies[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"options:strategy:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Options strategy config created: {config.name}")
        return config.config_id
    
    async def get_strategy_config(self, config_id: str) -> Optional[OptionStrategyConfig]:
        """Récupère une configuration de stratégie."""
        with self._strategies_lock:
            return self._strategies.get(config_id)
    
    async def exercise_option(self, option_id: str) -> bool:
        """Exerce une option."""
        with self._contracts_lock:
            contract = self._contracts.get(option_id)
            if not contract or contract.status != OptionStatus.OPEN:
                return False
            
            # Vérification de l'expiration
            if contract.days_to_expiry > 0:
                return False
            
            # Exercice
            contract.status = OptionStatus.EXERCISED
            contract.closed_at = datetime.now(timezone.utc)
            
            # Calcul du PnL
            if contract.option_type == OptionType.CALL:
                payoff = max(contract.underlying_price - contract.strike, 0)
            else:
                payoff = max(contract.strike - contract.underlying_price, 0)
            
            contract.pnl = payoff * contract.quantity - contract.premium
            
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._contracts_lock:
            self._stats["total_contracts"] = len(self._contracts)
        
        return self._stats.copy()


# ============== OPTIONS STRATEGY BUILDER ==============

class OptionsStrategyBuilder:
    """
    Constructeur de stratégies d'options.
    Facilite la création de stratégies complexes.
    """
    
    def __init__(self):
        self._strategy = OptionStrategyConfig()
        self._legs = []
    
    def name(self, name: str) -> 'OptionsStrategyBuilder':
        """Définit le nom."""
        self._strategy.name = name
        return self
    
    def strategy(self, strategy: OptionStrategy) -> 'OptionsStrategyBuilder':
        """Définit la stratégie."""
        self._strategy.strategy = strategy
        return self
    
    def leg(self, **kwargs) -> 'OptionsStrategyBuilder':
        """Ajoute une jambe."""
        self._legs.append(kwargs)
        return self
    
    def call(self, symbol: str, strike: float, expiration: datetime, **kwargs) -> 'OptionsStrategyBuilder':
        """Ajoute un call."""
        leg = {
            "symbol": symbol,
            "option_type": "call",
            "strike": strike,
            "expiration": expiration,
            **kwargs
        }
        return self.leg(**leg)
    
    def put(self, symbol: str, strike: float, expiration: datetime, **kwargs) -> 'OptionsStrategyBuilder':
        """Ajoute un put."""
        leg = {
            "symbol": symbol,
            "option_type": "put",
            "strike": strike,
            "expiration": expiration,
            **kwargs
        }
        return self.leg(**leg)
    
    def target_delta(self, delta: float) -> 'OptionsStrategyBuilder':
        """Définit le delta cible."""
        self._strategy.target_delta = delta
        return self
    
    def max_premium(self, premium: float) -> 'OptionsStrategyBuilder':
        """Définit le premium maximum."""
        self._strategy.max_premium = premium
        return self
    
    def build(self) -> OptionStrategyConfig:
        """Construit la stratégie."""
        self._strategy.legs = self._legs
        return self._strategy


# ============== FACTORY ==============

class OptionsFactory:
    """Factory pour créer des composants d'options."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> OptionsEngine:
        """Crée un moteur d'options."""
        engine = OptionsEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_strategy_builder() -> OptionsStrategyBuilder:
        """Crée un constructeur de stratégies."""
        return OptionsStrategyBuilder()


# ============== EXPORT ==============

__all__ = [
    "OptionType",
    "OptionStyle",
    "OptionStrategy",
    "OptionStatus",
    "OptionContract",
    "OptionStrategyConfig",
    "OptionGreeks",
    "OptionsEngineInterface",
    "OptionsEngine",
    "OptionsStrategyBuilder",
    "OptionsFactory"
]

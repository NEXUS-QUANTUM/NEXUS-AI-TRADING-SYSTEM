"""
NEXUS AI TRADING SYSTEM - Hedge Bot Core Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Module core du bot de couverture - Version complète
"""

# ============================================================
# PACKAGE METADATA
# ============================================================
__version__ = "2.0.0"
__author__ = "NEXUS QUANTUM TEAM"
__description__ = "Module core complet du bot de couverture NEXUS"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__license__ = "Proprietary"

# ============================================================
# IMPORTS
# ============================================================
import os
import sys
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import asyncio
import time

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# PACKAGE INFO
# ============================================================

PACKAGE_INFO = {
    "version": __version__,
    "author": __author__,
    "description": __description__,
    "copyright": __copyright__,
    "license": __license__,
}

# ============================================================
# ENUMS - HEDGE TYPES
# ============================================================

class HedgeType(Enum):
    """Types de couverture"""
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    THETA = "theta"
    RHO = "rho"
    BETA = "beta"
    CURRENCY = "currency"
    INTEREST_RATE = "interest_rate"
    VOLATILITY = "volatility"
    DURATION = "duration"
    CONVEXITY = "convexity"
    PORTFOLIO = "portfolio"
    SECTOR = "sector"
    FACTOR = "factor"
    CUSTOM = "custom"
    DYNAMIC = "dynamic"
    STATIC = "static"

class HedgeDirection(Enum):
    """Directions de couverture"""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    BIDIRECTIONAL = "bidirectional"

class HedgeStatus(Enum):
    """Statuts de couverture"""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class HedgePriority(Enum):
    """Priorités de couverture"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    OPTIONAL = 5

class HedgeFrequency(Enum):
    """Fréquences de couverture"""
    CONTINUOUS = "continuous"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"

# ============================================================
# ENUMS - INSTRUMENTS
# ============================================================

class InstrumentType(Enum):
    """Types d'instruments"""
    SPOT = "spot"
    FUTURES = "futures"
    OPTIONS = "options"
    SWAPS = "swaps"
    FORWARDS = "forwards"
    PERPETUAL = "perpetual"
    ETF = "etf"
    BOND = "bond"
    STOCK = "stock"
    COMMODITY = "commodity"
    FOREX = "forex"
    INDEX = "index"

class OptionType(Enum):
    """Types d'options"""
    CALL = "call"
    PUT = "put"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    SPREAD = "spread"
    COLLAR = "collar"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"

# ============================================================
# ENUMS - RISK
# ============================================================

class RiskType(Enum):
    """Types de risque"""
    MARKET = "market"
    CREDIT = "credit"
    LIQUIDITY = "liquidity"
    OPERATIONAL = "operational"
    COUNTERPARTY = "counterparty"
    REGULATORY = "regulatory"
    SYSTEMIC = "systemic"
    TAIL = "tail"
    BASIS = "basis"
    MODEL = "model"
    LEGAL = "legal"
    REPUTATIONAL = "reputational"

class RiskLevel(Enum):
    """Niveaux de risque"""
    NONE = 0
    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5
    EXTREME = 6

# ============================================================
# DATA CLASSES - HEDGE INSTRUMENTS
# ============================================================

@dataclass
class HedgeInstrument:
    """Instrument de couverture"""
    id: str
    symbol: str
    exchange: str
    type: InstrumentType
    price: float
    volume: float
    bid: float
    ask: float
    spread: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'type': self.type.value,
            'price': self.price,
            'volume': self.volume,
            'bid': self.bid,
            'ask': self.ask,
            'spread': self.spread,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HedgeInstrument':
        """Crée depuis un dictionnaire"""
        return cls(
            id=data['id'],
            symbol=data['symbol'],
            exchange=data['exchange'],
            type=InstrumentType(data['type']),
            price=data['price'],
            volume=data['volume'],
            bid=data['bid'],
            ask=data['ask'],
            spread=data['spread'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data.get('metadata', {}),
        )

@dataclass
class HedgeOption:
    """Option de couverture"""
    id: str
    underlying: str
    strike: float
    expiry: datetime
    option_type: OptionType
    premium: float
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'underlying': self.underlying,
            'strike': self.strike,
            'expiry': self.expiry.isoformat(),
            'option_type': self.option_type.value,
            'premium': self.premium,
            'implied_volatility': self.implied_volatility,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho,
            'metadata': self.metadata,
        }

@dataclass
class HedgeFuture:
    """Future de couverture"""
    id: str
    underlying: str
    expiry: datetime
    price: float
    basis: float
    open_interest: int
    volume: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'underlying': self.underlying,
            'expiry': self.expiry.isoformat(),
            'price': self.price,
            'basis': self.basis,
            'open_interest': self.open_interest,
            'volume': self.volume,
            'metadata': self.metadata,
        }

# ============================================================
# DATA CLASSES - HEDGE POSITIONS
# ============================================================

@dataclass
class HedgePosition:
    """Position de couverture"""
    id: str
    instrument: HedgeInstrument
    direction: HedgeDirection
    size: float
    entry_price: float
    current_price: float
    status: HedgeStatus
    entry_time: datetime
    last_update: datetime
    pnl: float = 0.0
    pnl_percent: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_pnl(self, current_price: Optional[float] = None):
        """Met à jour le P&L de la position"""
        if current_price is not None:
            self.current_price = current_price
        
        if self.direction == HedgeDirection.LONG:
            self.pnl = (self.current_price - self.entry_price) * self.size
        elif self.direction == HedgeDirection.SHORT:
            self.pnl = (self.entry_price - self.current_price) * self.size
        else:
            self.pnl = 0.0
        
        if self.entry_price != 0:
            self.pnl_percent = (self.pnl / (self.entry_price * self.size)) * 100
        
        self.last_update = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'instrument': self.instrument.to_dict(),
            'direction': self.direction.value,
            'size': self.size,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'status': self.status.value,
            'entry_time': self.entry_time.isoformat(),
            'last_update': self.last_update.isoformat(),
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'metadata': self.metadata,
        }

@dataclass
class HedgePortfolio:
    """Portefeuille de couverture"""
    id: str
    name: str
    positions: List[HedgePosition] = field(default_factory=list)
    total_value: float = 0.0
    total_pnl: float = 0.0
    total_risk: float = 0.0
    hedge_ratio: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_position(self, position: HedgePosition):
        """Ajoute une position au portefeuille"""
        self.positions.append(position)
        self.updated_at = datetime.now()
        self._update_metrics()
    
    def remove_position(self, position_id: str):
        """Supprime une position du portefeuille"""
        self.positions = [p for p in self.positions if p.id != position_id]
        self.updated_at = datetime.now()
        self._update_metrics()
    
    def _update_metrics(self):
        """Met à jour les métriques du portefeuille"""
        self.total_value = sum(p.current_price * p.size for p in self.positions)
        self.total_pnl = sum(p.pnl for p in self.positions)
        self.total_risk = sum(abs(p.pnl) for p in self.positions) / len(self.positions) if self.positions else 0
        
        # Calcul du ratio de couverture
        long_exposure = sum(p.size * p.current_price for p in self.positions if p.direction == HedgeDirection.LONG)
        short_exposure = sum(p.size * p.current_price for p in self.positions if p.direction == HedgeDirection.SHORT)
        self.hedge_ratio = short_exposure / long_exposure if long_exposure > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'name': self.name,
            'positions': [p.to_dict() for p in self.positions],
            'total_value': self.total_value,
            'total_pnl': self.total_pnl,
            'total_risk': self.total_risk,
            'hedge_ratio': self.hedge_ratio,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata,
        }

# ============================================================
# DATA CLASSES - HEDGE STRATEGIES
# ============================================================

@dataclass
class HedgeStrategy:
    """Stratégie de couverture"""
    id: str
    name: str
    type: HedgeType
    priority: HedgePriority
    frequency: HedgeFrequency
    description: str = ""
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'priority': self.priority.value,
            'frequency': self.frequency.value,
            'description': self.description,
            'enabled': self.enabled,
            'parameters': self.parameters,
            'conditions': self.conditions,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

@dataclass
class HedgeSignal:
    """Signal de couverture"""
    id: str
    strategy_id: str
    instrument: HedgeInstrument
    direction: HedgeDirection
    size: float
    price: float
    confidence: float
    timestamp: datetime
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    executed: bool = False
    execution_price: Optional[float] = None
    execution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'strategy_id': self.strategy_id,
            'instrument': self.instrument.to_dict(),
            'direction': self.direction.value,
            'size': self.size,
            'price': self.price,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason,
            'metadata': self.metadata,
            'executed': self.executed,
            'execution_price': self.execution_price,
            'execution_time': self.execution_time.isoformat() if self.execution_time else None,
        }

# ============================================================
# DATA CLASSES - METRICS & ANALYSIS
# ============================================================

@dataclass
class HedgeMetrics:
    """Métriques de couverture"""
    hedge_ratio: float
    hedge_effectiveness: float
    residual_risk: float
    cost: float
    pnl: float
    exposure: float
    var_95: float
    cvar_95: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'hedge_ratio': self.hedge_ratio,
            'hedge_effectiveness': self.hedge_effectiveness,
            'residual_risk': self.residual_risk,
            'cost': self.cost,
            'pnl': self.pnl,
            'exposure': self.exposure,
            'var_95': self.var_95,
            'cvar_95': self.cvar_95,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'metadata': self.metadata,
        }

@dataclass
class HedgeAnalysis:
    """Analyse de couverture"""
    timestamp: datetime
    portfolio: HedgePortfolio
    metrics: HedgeMetrics
    risk_factors: Dict[str, float]
    correlations: Dict[str, float]
    recommendations: List[str]
    warnings: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'portfolio': self.portfolio.to_dict(),
            'metrics': self.metrics.to_dict(),
            'risk_factors': self.risk_factors,
            'correlations': self.correlations,
            'recommendations': self.recommendations,
            'warnings': self.warnings,
            'metadata': self.metadata,
        }

# ============================================================
# DATA CLASSES - CONFIGURATION
# ============================================================

@dataclass
class HedgeConfig:
    """Configuration de couverture"""
    enabled: bool = True
    max_positions: int = 50
    max_exposure: float = 1000000.0
    hedge_ratio_target: float = 0.5
    hedge_ratio_min: float = 0.3
    hedge_ratio_max: float = 0.7
    rebalance_threshold: float = 0.05
    auto_hedge: bool = True
    auto_rebalance: bool = True
    auto_stop_loss: bool = True
    default_instruments: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'enabled': self.enabled,
            'max_positions': self.max_positions,
            'max_exposure': self.max_exposure,
            'hedge_ratio_target': self.hedge_ratio_target,
            'hedge_ratio_min': self.hedge_ratio_min,
            'hedge_ratio_max': self.hedge_ratio_max,
            'rebalance_threshold': self.rebalance_threshold,
            'auto_hedge': self.auto_hedge,
            'auto_rebalance': self.auto_rebalance,
            'auto_stop_loss': self.auto_stop_loss,
            'default_instruments': self.default_instruments,
            'metadata': self.metadata,
        }

@dataclass
class InstrumentConfig:
    """Configuration d'instrument"""
    symbol: str
    exchange: str
    type: InstrumentType
    min_size: float
    max_size: float
    tick_size: float
    fee_maker: float
    fee_taker: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'type': self.type.value,
            'min_size': self.min_size,
            'max_size': self.max_size,
            'tick_size': self.tick_size,
            'fee_maker': self.fee_maker,
            'fee_taker': self.fee_taker,
            'metadata': self.metadata,
        }

@dataclass
class RiskConfig:
    """Configuration de risque"""
    max_drawdown: float = 0.15
    max_loss_per_day: float = 0.05
    max_loss_per_week: float = 0.10
    max_loss_per_month: float = 0.15
    var_confidence: float = 0.95
    stop_loss_percent: float = 0.02
    take_profit_percent: float = 0.03
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'max_drawdown': self.max_drawdown,
            'max_loss_per_day': self.max_loss_per_day,
            'max_loss_per_week': self.max_loss_per_week,
            'max_loss_per_month': self.max_loss_per_month,
            'var_confidence': self.var_confidence,
            'stop_loss_percent': self.stop_loss_percent,
            'take_profit_percent': self.take_profit_percent,
            'metadata': self.metadata,
        }

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_hedge_type_description(hedge_type: HedgeType) -> str:
    """Récupère la description d'un type de couverture"""
    descriptions = {
        HedgeType.DELTA: "Couverture contre les variations de prix",
        HedgeType.GAMMA: "Couverture contre la convexité",
        HedgeType.VEGA: "Couverture contre la volatilité",
        HedgeType.THETA: "Couverture contre la décroissance temporelle",
        HedgeType.RHO: "Couverture contre les taux d'intérêt",
        HedgeType.BETA: "Couverture contre le marché",
        HedgeType.CURRENCY: "Couverture contre les devises",
        HedgeType.INTEREST_RATE: "Couverture contre les taux d'intérêt",
        HedgeType.VOLATILITY: "Couverture contre la volatilité",
        HedgeType.DURATION: "Couverture de durée",
        HedgeType.CONVEXITY: "Couverture de convexité",
        HedgeType.PORTFOLIO: "Couverture de portefeuille",
        HedgeType.SECTOR: "Couverture sectorielle",
        HedgeType.FACTOR: "Couverture factorielle",
        HedgeType.CUSTOM: "Couverture personnalisée",
        HedgeType.DYNAMIC: "Couverture dynamique",
        HedgeType.STATIC: "Couverture statique"
    }
    return descriptions.get(hedge_type, "Type inconnu")

def get_risk_level_description(risk_level: RiskLevel) -> str:
    """Récupère la description d'un niveau de risque"""
    descriptions = {
        RiskLevel.NONE: "Aucun risque",
        RiskLevel.VERY_LOW: "Risque très faible",
        RiskLevel.LOW: "Risque faible",
        RiskLevel.MEDIUM: "Risque moyen",
        RiskLevel.HIGH: "Risque élevé",
        RiskLevel.VERY_HIGH: "Risque très élevé",
        RiskLevel.EXTREME: "Risque extrême"
    }
    return descriptions.get(risk_level, "Niveau inconnu")

def validate_hedge_config(config: HedgeConfig) -> Tuple[bool, List[str]]:
    """Valide une configuration de couverture"""
    errors = []
    
    if config.hedge_ratio_target < config.hedge_ratio_min:
        errors.append("hedge_ratio_target cannot be less than hedge_ratio_min")
    if config.hedge_ratio_target > config.hedge_ratio_max:
        errors.append("hedge_ratio_target cannot be greater than hedge_ratio_max")
    if config.max_positions < 1:
        errors.append("max_positions must be at least 1")
    if config.max_exposure < 0:
        errors.append("max_exposure cannot be negative")
    
    return len(errors) == 0, errors

# ============================================================
# BASE HEDGE CLASS
# ============================================================

class BaseHedge:
    """
    Classe de base pour la couverture
    
    Fournit les fonctionnalités communes à toutes les stratégies de couverture
    """
    
    def __init__(
        self,
        config: Optional[HedgeConfig] = None,
        name: str = "BaseHedge"
    ):
        """
        Initialise la couverture de base
        
        Args:
            config: Configuration de couverture
            name: Nom de la couverture
        """
        self.name = name
        self.config = config or HedgeConfig()
        self.positions: List[HedgePosition] = []
        self.strategies: List[HedgeStrategy] = []
        self.signals: List[HedgeSignal] = []
        self.metrics: Optional[HedgeMetrics] = None
        self._lock = threading.RLock()
        self._running = False
        self._initialized = False
        
        logger.info(f"BaseHedge '{name}' initialized")
    
    def initialize(self) -> bool:
        """
        Initialise la couverture
        
        Returns:
            bool: True si initialisé
        """
        if self._initialized:
            return True
        
        try:
            # Valider la configuration
            valid, errors = validate_hedge_config(self.config)
            if not valid:
                logger.error(f"Invalid configuration: {errors}")
                return False
            
            self._initialized = True
            logger.info(f"BaseHedge '{self.name}' initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            return False
    
    def start(self) -> bool:
        """
        Démarre la couverture
        
        Returns:
            bool: True si démarrée
        """
        if self._running:
            return True
        
        if not self._initialized:
            if not self.initialize():
                return False
        
        self._running = True
        logger.info(f"BaseHedge '{self.name}' started")
        return True
    
    def stop(self) -> bool:
        """
        Arrête la couverture
        
        Returns:
            bool: True si arrêtée
        """
        if not self._running:
            return True
        
        self._running = False
        logger.info(f"BaseHedge '{self.name}' stopped")
        return True
    
    def add_position(self, position: HedgePosition) -> bool:
        """
        Ajoute une position de couverture
        
        Args:
            position: Position à ajouter
            
        Returns:
            bool: True si ajoutée
        """
        with self._lock:
            if len(self.positions) >= self.config.max_positions:
                logger.warning(f"Max positions reached: {self.config.max_positions}")
                return False
            
            self.positions.append(position)
            logger.info(f"Position added: {position.id}")
            return True
    
    def remove_position(self, position_id: str) -> bool:
        """
        Supprime une position de couverture
        
        Args:
            position_id: ID de la position
            
        Returns:
            bool: True si supprimée
        """
        with self._lock:
            initial_count = len(self.positions)
            self.positions = [p for p in self.positions if p.id != position_id]
            
            if len(self.positions) < initial_count:
                logger.info(f"Position removed: {position_id}")
                return True
            
            logger.warning(f"Position not found: {position_id}")
            return False
    
    def get_positions(self) -> List[HedgePosition]:
        """
        Récupère toutes les positions
        
        Returns:
            List[HedgePosition]: Positions
        """
        with self._lock:
            return self.positions.copy()
    
    def get_active_positions(self) -> List[HedgePosition]:
        """
        Récupère les positions actives
        
        Returns:
            List[HedgePosition]: Positions actives
        """
        with self._lock:
            return [p for p in self.positions if p.status == HedgeStatus.ACTIVE]
    
    def calculate_metrics(self) -> HedgeMetrics:
        """
        Calcule les métriques de couverture
        
        Returns:
            HedgeMetrics: Métriques calculées
        """
        with self._lock:
            if not self.positions:
                return HedgeMetrics(0,0,0,0,0,0,0,0,0,0,0,0)
            
            # Calculer l'exposition totale
            total_long = sum(p.size * p.current_price for p in self.positions if p.direction == HedgeDirection.LONG)
            total_short = sum(p.size * p.current_price for p in self.positions if p.direction == HedgeDirection.SHORT)
            total_exposure = total_long - total_short
            
            # Calculer le ratio de couverture
            hedge_ratio = abs(total_short) / abs(total_long) if abs(total_long) > 0 else 0
            
            # Calculer le P&L total
            total_pnl = sum(p.pnl for p in self.positions)
            
            # Calculer l'efficacité de la couverture
            hedge_effectiveness = 1 - (abs(total_pnl) / (abs(total_long) + abs(total_short))) if (abs(total_long) + abs(total_short)) > 0 else 0
            
            # Calculer le risque résiduel
            residual_risk = abs(total_exposure)
            
            # Calculer le coût
            cost = sum(abs(p.entry_price * p.size) * 0.001 for p in self.positions)  # Simulation
            
            return HedgeMetrics(
                hedge_ratio=hedge_ratio,
                hedge_effectiveness=hedge_effectiveness,
                residual_risk=residual_risk,
                cost=cost,
                pnl=total_pnl,
                exposure=total_exposure,
                var_95=0.02,
                cvar_95=0.03,
                max_drawdown=0.15,
                sharpe_ratio=0.5,
                sortino_ratio=0.4,
                calmar_ratio=0.3
            )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Récupère le statut de la couverture
        
        Returns:
            Dict[str, Any]: Statut
        """
        return {
            'name': self.name,
            'running': self._running,
            'initialized': self._initialized,
            'positions_count': len(self.positions),
            'active_positions': len(self.get_active_positions()),
            'config': self.config.to_dict(),
            'metrics': self.calculate_metrics().to_dict() if self.positions else None,
        }

# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_hedge_instrument(
    symbol: str,
    exchange: str,
    instrument_type: InstrumentType,
    price: float,
    **kwargs
) -> HedgeInstrument:
    """
    Crée un instrument de couverture
    
    Args:
        symbol: Symbole
        exchange: Exchange
        instrument_type: Type d'instrument
        price: Prix
        **kwargs: Arguments supplémentaires
        
    Returns:
        HedgeInstrument: Instrument créé
    """
    return HedgeInstrument(
        id=f"{symbol}_{exchange}_{int(time.time())}",
        symbol=symbol,
        exchange=exchange,
        type=instrument_type,
        price=price,
        volume=kwargs.get('volume', 0),
        bid=kwargs.get('bid', price * 0.999),
        ask=kwargs.get('ask', price * 1.001),
        spread=kwargs.get('spread', price * 0.002),
        metadata=kwargs.get('metadata', {})
    )

def create_hedge_position(
    instrument: HedgeInstrument,
    direction: HedgeDirection,
    size: float,
    entry_price: float
) -> HedgePosition:
    """
    Crée une position de couverture
    
    Args:
        instrument: Instrument
        direction: Direction
        size: Taille
        entry_price: Prix d'entrée
        
    Returns:
        HedgePosition: Position créée
    """
    return HedgePosition(
        id=f"pos_{instrument.symbol}_{int(time.time())}",
        instrument=instrument,
        direction=direction,
        size=size,
        entry_price=entry_price,
        current_price=entry_price,
        status=HedgeStatus.ACTIVE,
        entry_time=datetime.now(),
        last_update=datetime.now()
    )

# ============================================================
# MODULE INFORMATION
# ============================================================

def get_module_info() -> Dict[str, Any]:
    """
    Récupère les informations du module
    
    Returns:
        Dict[str, Any]: Informations du module
    """
    return {
        **PACKAGE_INFO,
        "classes": {
            "BaseHedge": BaseHedge.__doc__,
            "HedgeInstrument": HedgeInstrument.__doc__,
            "HedgeOption": HedgeOption.__doc__,
            "HedgeFuture": HedgeFuture.__doc__,
            "HedgePosition": HedgePosition.__doc__,
            "HedgePortfolio": HedgePortfolio.__doc__,
            "HedgeStrategy": HedgeStrategy.__doc__,
            "HedgeSignal": HedgeSignal.__doc__,
            "HedgeMetrics": HedgeMetrics.__doc__,
            "HedgeAnalysis": HedgeAnalysis.__doc__,
        },
        "enums": {
            "HedgeType": [e.value for e in HedgeType],
            "HedgeDirection": [e.value for e in HedgeDirection],
            "HedgeStatus": [e.value for e in HedgeStatus],
            "HedgePriority": [e.value for e in HedgePriority],
            "HedgeFrequency": [e.value for e in HedgeFrequency],
            "InstrumentType": [e.value for e in InstrumentType],
            "OptionType": [e.value for e in OptionType],
            "RiskType": [e.value for e in RiskType],
            "RiskLevel": [e.value for e in RiskLevel],
        },
        "helper_functions": [
            "get_hedge_type_description",
            "get_risk_level_description",
            "validate_hedge_config",
            "create_hedge_instrument",
            "create_hedge_position",
        ]
    }

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Version
    '__version__',
    '__author__',
    '__description__',
    '__copyright__',
    '__license__',
    
    # Enums
    'HedgeType',
    'HedgeDirection',
    'HedgeStatus',
    'HedgePriority',
    'HedgeFrequency',
    'InstrumentType',
    'OptionType',
    'RiskType',
    'RiskLevel',
    
    # Data Classes
    'HedgeInstrument',
    'HedgeOption',
    'HedgeFuture',
    'HedgePosition',
    'HedgePortfolio',
    'HedgeStrategy',
    'HedgeSignal',
    'HedgeMetrics',
    'HedgeAnalysis',
    'HedgeConfig',
    'InstrumentConfig',
    'RiskConfig',
    
    # Base Class
    'BaseHedge',
    
    # Helper Functions
    'get_hedge_type_description',
    'get_risk_level_description',
    'validate_hedge_config',
    'create_hedge_instrument',
    'create_hedge_position',
    
    # Module Info
    'get_module_info',
    'PACKAGE_INFO',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info(f"Hedge Bot Core module initialized (v{__version__})")
logger.info(f"Available hedge types: {[e.value for e in HedgeType]}")
logger.info(f"Available instrument types: {[e.value for e in InstrumentType]}")

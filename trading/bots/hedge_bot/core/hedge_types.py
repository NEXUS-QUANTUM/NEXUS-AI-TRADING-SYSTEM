"""
NEXUS AI TRADING SYSTEM - Hedge Bot Types
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Types de couverture pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS - HEDGE TYPES
# ============================================================

class HedgeType(Enum):
    """Types de couverture"""
    # Couverture de base
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    THETA = "theta"
    RHO = "rho"
    
    # Couverture avancée
    BETA = "beta"
    CURRENCY = "currency"
    INTEREST_RATE = "interest_rate"
    VOLATILITY = "volatility"
    DURATION = "duration"
    CONVEXITY = "convexity"
    
    # Couverture de portefeuille
    PORTFOLIO = "portfolio"
    SECTOR = "sector"
    FACTOR = "factor"
    
    # Couverture personnalisée
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

class OptionType(Enum):
    """Types d'options"""
    CALL = "call"
    PUT = "put"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    SPREAD = "spread"
    COLLAR = "collar"

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

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums - Hedge Types
    'HedgeType',
    'HedgeDirection',
    'HedgeStatus',
    'HedgePriority',
    'HedgeFrequency',
    
    # Enums - Instruments
    'InstrumentType',
    'OptionType',
    
    # Enums - Risk
    'RiskType',
    'RiskLevel',
    
    # Data Classes - Instruments
    'HedgeInstrument',
    'HedgeOption',
    'HedgeFuture',
    
    # Data Classes - Positions
    'HedgePosition',
    'HedgePortfolio',
    
    # Data Classes - Strategies
    'HedgeStrategy',
    'HedgeSignal',
    
    # Data Classes - Metrics
    'HedgeMetrics',
    'HedgeAnalysis',
    
    # Data Classes - Configuration
    'HedgeConfig',
    'InstrumentConfig',
    'RiskConfig',
    
    # Helper Functions
    'get_hedge_type_description',
    'get_risk_level_description',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Hedge types module initialized")

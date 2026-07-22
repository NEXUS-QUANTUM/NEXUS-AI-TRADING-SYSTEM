"""
NEXUS AI TRADING SYSTEM - Hedge Bot Perpetual Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de contrats perpétuels pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import math
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import numpy as np

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class PerpetualType(Enum):
    """Types de contrats perpétuels"""
    LINEAR = "linear"       # USDT margined
    INVERSE = "inverse"     # Coin margined
    QUANTO = "quanto"       # Quanto margined

class PerpetualSide(Enum):
    """Côtés des contrats perpétuels"""
    LONG = "long"
    SHORT = "short"

class PerpetualStatus(Enum):
    """Statuts des contrats perpétuels"""
    ACTIVE = "active"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"
    PAUSED = "paused"
    SETTLED = "settled"

class FundingRateMode(Enum):
    """Modes de taux de financement"""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    EXCHANGE = "exchange"
    CUSTOM = "custom"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PerpetualContract:
    """Contrat perpétuel"""
    id: str
    symbol: str
    exchange: str
    type: PerpetualType
    leverage: float
    side: PerpetualSide
    size: float
    entry_price: float
    current_price: float
    mark_price: float
    liquidation_price: float
    margin: float
    unrealized_pnl: float
    realized_pnl: float
    funding_rate: float
    next_funding_time: datetime
    status: PerpetualStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FundingRate:
    """Taux de financement"""
    symbol: str
    rate: float
    timestamp: datetime
    predicted_rate: Optional[float] = None
    premium: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerpetualMetrics:
    """Métriques des contrats perpétuels"""
    total_size: float
    total_margin: float
    total_pnl: float
    total_funding: float
    avg_leverage: float
    liquidation_risk: float
    funding_cost: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerpetualConfig:
    """Configuration des contrats perpétuels"""
    enabled: bool = True
    default_leverage: float = 1.0
    max_leverage: float = 10.0
    min_leverage: float = 1.0
    margin_rate: float = 0.10  # 10%
    maintenance_margin: float = 0.05  # 5%
    funding_rate_interval: int = 3600  # 1 hour
    max_funding_rate: float = 0.01  # 1%
    auto_hedge: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# PERPETUAL MANAGER
# ============================================================

class PerpetualManager:
    """
    Gestionnaire de contrats perpétuels pour le bot de couverture
    
    Gère les positions perpétuelles, les taux de financement et les risques
    """
    
    def __init__(
        self,
        config: Optional[PerpetualConfig] = None,
        update_interval: int = 10,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de contrats perpétuels
        
        Args:
            config: Configuration
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or PerpetualConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Contrats
        self.contracts: Dict[str, PerpetualContract] = {}
        self.active_contracts: Dict[str, PerpetualContract] = {}
        self.closed_contracts: Dict[str, PerpetualContract] = {}
        
        # Taux de financement
        self.funding_rates: Dict[str, List[FundingRate]] = defaultdict(list)
        self.current_funding_rates: Dict[str, FundingRate] = {}
        
        # Métriques
        self.metrics: Optional[PerpetualMetrics] = None
        
        # Statistiques
        self.stats = {
            'total_contracts': 0,
            'active_contracts': 0,
            'closed_contracts': 0,
            'liquidated_contracts': 0,
            'total_size': 0.0,
            'total_margin': 0.0,
            'total_pnl': 0.0,
            'total_funding': 0.0,
            'avg_leverage': 0.0,
            'funding_cost': 0.0,
        }
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'contract_opened': [],
            'contract_updated': [],
            'contract_closed': [],
            'funding_paid': [],
            'liquidation': [],
            'margin_call': [],
        }
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Capital
        self.capital: float = 10000.0
        
        # Démarrer le monitoring
        if enable_monitoring and update_interval > 0:
            self.start()
        
        logger.info("PerpetualManager initialized")
    
    # ============================================================
    # CONTRACT MANAGEMENT
    # ============================================================
    
    def open_contract(
        self,
        symbol: str,
        exchange: str,
        side: PerpetualSide,
        size: float,
        entry_price: float,
        leverage: Optional[float] = None,
        contract_type: PerpetualType = PerpetualType.LINEAR,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PerpetualContract:
        """
        Ouvre un contrat perpétuel
        
        Args:
            symbol: Symbole
            exchange: Exchange
            side: Côté
            size: Taille
            entry_price: Prix d'entrée
            leverage: Levier
            contract_type: Type de contrat
            metadata: Métadonnées
            
        Returns:
            PerpetualContract: Contrat ouvert
        """
        with self._lock:
            # Calculer le levier
            if leverage is None:
                leverage = self.config.default_leverage
            
            leverage = min(leverage, self.config.max_leverage)
            leverage = max(leverage, self.config.min_leverage)
            
            # Calculer la marge
            margin = size * entry_price / leverage
            
            # Prix de liquidation
            liquidation_price = self._calculate_liquidation_price(
                entry_price=entry_price,
                leverage=leverage,
                side=side,
                margin=margin
            )
            
            # Taux de financement
            funding_rate = self._get_funding_rate(symbol)
            next_funding = self._get_next_funding_time()
            
            contract = PerpetualContract(
                id=f"perp_{int(time.time())}_{symbol}",
                symbol=symbol,
                exchange=exchange,
                type=contract_type,
                leverage=leverage,
                side=side,
                size=size,
                entry_price=entry_price,
                current_price=entry_price,
                mark_price=entry_price,
                liquidation_price=liquidation_price,
                margin=margin,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                funding_rate=funding_rate,
                next_funding_time=next_funding,
                status=PerpetualStatus.ACTIVE,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata=metadata or {}
            )
            
            self.contracts[contract.id] = contract
            self.active_contracts[contract.id] = contract
            self.stats['total_contracts'] += 1
            self.stats['active_contracts'] += 1
            self.stats['total_size'] += size
            self.stats['total_margin'] += margin
            
            self._update_stats()
            self._trigger_event('contract_opened', contract)
            
            logger.info(f"Perpetual contract opened: {symbol} - {side.value} - {size} @ {entry_price:.2f} - {leverage:.1f}x")
            return contract
    
    def _calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: float,
        side: PerpetualSide,
        margin: float
    ) -> float:
        """
        Calcule le prix de liquidation
        
        Args:
            entry_price: Prix d'entrée
            leverage: Levier
            side: Côté
            margin: Marge
            
        Returns:
            float: Prix de liquidation
        """
        if side == PerpetualSide.LONG:
            liquidation_price = entry_price * (1 - 1 / leverage)
        else:
            liquidation_price = entry_price * (1 + 1 / leverage)
        
        return liquidation_price
    
    def update_contract(
        self,
        contract_id: str,
        current_price: float,
        mark_price: Optional[float] = None
    ) -> bool:
        """
        Met à jour un contrat perpétuel
        
        Args:
            contract_id: ID du contrat
            current_price: Prix actuel
            mark_price: Prix mark
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                return False
            
            if contract.status != PerpetualStatus.ACTIVE:
                return False
            
            contract.current_price = current_price
            contract.mark_price = mark_price or current_price
            contract.updated_at = datetime.now()
            
            # Calculer le P&L
            if contract.side == PerpetualSide.LONG:
                contract.unrealized_pnl = (current_price - contract.entry_price) * contract.size
            else:
                contract.unrealized_pnl = (contract.entry_price - current_price) * contract.size
            
            # Vérifier la liquidation
            if self._check_liquidation(contract):
                self._liquidate_contract(contract_id)
                return True
            
            # Vérifier l'appel de marge
            margin_ratio = contract.margin / (contract.size * current_price)
            if margin_ratio < self.config.maintenance_margin:
                self._trigger_event('margin_call', contract)
                self._add_alert(
                    f"Margin call: {contract.symbol} - {margin_ratio:.1%} margin remaining",
                    "warning"
                )
            
            # Vérifier le taux de financement
            if datetime.now() >= contract.next_funding_time:
                self._pay_funding(contract_id)
            
            self._trigger_event('contract_updated', contract)
            return True
    
    def _check_liquidation(self, contract: PerpetualContract) -> bool:
        """
        Vérifie si le contrat doit être liquidé
        
        Args:
            contract: Contrat à vérifier
            
        Returns:
            bool: True si liquidation
        """
        if contract.side == PerpetualSide.LONG:
            if contract.current_price <= contract.liquidation_price:
                return True
        else:
            if contract.current_price >= contract.liquidation_price:
                return True
        
        return False
    
    def _liquidate_contract(self, contract_id: str) -> bool:
        """
        Liquide un contrat perpétuel
        
        Args:
            contract_id: ID du contrat
            
        Returns:
            bool: True si liquidé
        """
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                return False
            
            contract.status = PerpetualStatus.LIQUIDATED
            contract.updated_at = datetime.now()
            
            self.active_contracts.pop(contract_id, None)
            self.closed_contracts[contract_id] = contract
            self.stats['active_contracts'] -= 1
            self.stats['closed_contracts'] += 1
            self.stats['liquidated_contracts'] += 1
            
            self._update_stats()
            self._trigger_event('liquidation', contract)
            
            self._add_alert(
                f"Contract liquidated: {contract.symbol} @ {contract.current_price:.2f}",
                "critical"
            )
            
            logger.warning(f"Contract liquidated: {contract_id}")
            return True
    
    def close_contract(self, contract_id: str) -> bool:
        """
        Ferme un contrat perpétuel
        
        Args:
            contract_id: ID du contrat
            
        Returns:
            bool: True si fermé
        """
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                return False
            
            contract.status = PerpetualStatus.CLOSED
            contract.updated_at = datetime.now()
            
            # Enregistrer le P&L réalisé
            contract.realized_pnl = contract.unrealized_pnl
            
            self.active_contracts.pop(contract_id, None)
            self.closed_contracts[contract_id] = contract
            self.stats['active_contracts'] -= 1
            self.stats['closed_contracts'] += 1
            self.stats['total_pnl'] += contract.realized_pnl
            
            self._update_stats()
            self._trigger_event('contract_closed', contract)
            
            logger.info(f"Contract closed: {contract_id} - PNL: {contract.realized_pnl:.2f}")
            return True
    
    def get_contract(self, contract_id: str) -> Optional[PerpetualContract]:
        """
        Récupère un contrat perpétuel
        
        Args:
            contract_id: ID du contrat
            
        Returns:
            Optional[PerpetualContract]: Contrat
        """
        return self.contracts.get(contract_id)
    
    def get_active_contracts(self) -> List[PerpetualContract]:
        """
        Récupère les contrats actifs
        
        Returns:
            List[PerpetualContract]: Contrats actifs
        """
        return list(self.active_contracts.values())
    
    # ============================================================
    # FUNDING RATE MANAGEMENT
    # ============================================================
    
    def _get_funding_rate(self, symbol: str) -> float:
        """
        Récupère le taux de financement
        
        Args:
            symbol: Symbole
            
        Returns:
            float: Taux de financement
        """
        # Simuler le taux de financement
        # À implémenter avec des données réelles
        return 0.0001  # 0.01%
    
    def _get_next_funding_time(self) -> datetime:
        """
        Récupère la prochaine date de financement
        
        Returns:
            datetime: Prochaine date de financement
        """
        return datetime.now() + timedelta(hours=1)
    
    def _pay_funding(self, contract_id: str) -> bool:
        """
        Paie le financement d'un contrat
        
        Args:
            contract_id: ID du contrat
            
        Returns:
            bool: True si payé
        """
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                return False
            
            # Calculer le montant du financement
            funding_amount = contract.size * contract.current_price * contract.funding_rate
            
            # Mettre à jour le contrat
            contract.unrealized_pnl -= funding_amount
            contract.funding_rate = self._get_funding_rate(contract.symbol)
            contract.next_funding_time = self._get_next_funding_time()
            
            self.stats['total_funding'] += funding_amount
            self.stats['funding_cost'] += abs(funding_amount)
            
            self._trigger_event('funding_paid', contract)
            
            logger.debug(f"Funding paid: {contract_id} - {funding_amount:.4f}")
            return True
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
    
    def calculate_metrics(self) -> PerpetualMetrics:
        """
        Calcule les métriques des contrats perpétuels
        
        Returns:
            PerpetualMetrics: Métriques calculées
        """
        with self._lock:
            active = list(self.active_contracts.values())
            if not active:
                return PerpetualMetrics(0,0,0,0,0,0,0)
            
            total_size = sum(c.size for c in active)
            total_margin = sum(c.margin for c in active)
            total_pnl = sum(c.unrealized_pnl for c in active)
            total_funding = self.stats['total_funding']
            
            avg_leverage = sum(c.leverage for c in active) / len(active) if active else 0
            
            # Risque de liquidation
            liquidation_risk = 0.0
            for contract in active:
                if contract.side == PerpetualSide.LONG:
                    distance = contract.current_price - contract.liquidation_price
                else:
                    distance = contract.liquidation_price - contract.current_price
                
                if distance > 0:
                    risk = 1 / (1 + distance / contract.current_price * 100)
                    liquidation_risk = max(liquidation_risk, risk)
            
            # Coût de financement
            funding_cost = sum(
                c.size * c.current_price * c.funding_rate
                for c in active
            )
            
            metrics = PerpetualMetrics(
                total_size=total_size,
                total_margin=total_margin,
                total_pnl=total_pnl,
                total_funding=total_funding,
                avg_leverage=avg_leverage,
                liquidation_risk=liquidation_risk,
                funding_cost=funding_cost
            )
            
            self.metrics = metrics
            return metrics
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        metrics = self.calculate_metrics()
        self.stats.update({
            'total_size': metrics.total_size,
            'total_margin': metrics.total_margin,
            'total_pnl': metrics.total_pnl,
            'total_funding': metrics.total_funding,
            'avg_leverage': metrics.avg_leverage,
            'funding_cost': metrics.funding_cost,
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            return self.stats.copy()
    
    def get_report(self) -> Dict[str, Any]:
        """
        Récupère un rapport
        
        Returns:
            Dict[str, Any]: Rapport
        """
        metrics = self.calculate_metrics()
        
        return {
            'timestamp': time.time(),
            'stats': self.get_stats(),
            'metrics': {
                'total_size': metrics.total_size,
                'total_margin': metrics.total_margin,
                'total_pnl': metrics.total_pnl,
                'total_funding': metrics.total_funding,
                'avg_leverage': metrics.avg_leverage,
                'liquidation_risk': metrics.liquidation_risk,
                'funding_cost': metrics.funding_cost,
            },
            'active_contracts': [
                {
                    'id': c.id,
                    'symbol': c.symbol,
                    'side': c.side.value,
                    'size': c.size,
                    'leverage': c.leverage,
                    'entry_price': c.entry_price,
                    'current_price': c.current_price,
                    'unrealized_pnl': c.unrealized_pnl,
                    'liquidation_price': c.liquidation_price,
                    'funding_rate': c.funding_rate,
                }
                for c in self.active_contracts.values()
            ],
            'funding_rates': [
                {
                    'symbol': s,
                    'rate': fr[-1].rate if fr else 0,
                    'timestamp': fr[-1].timestamp.isoformat() if fr else None,
                }
                for s, fr in self.funding_rates.items()
            ],
            'alerts': self.alerts[-10:],
        }
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on(self, event: str, callback: Callable):
        """
        Enregistre un callback
        
        Args:
            event: Événement
            callback: Fonction de callback
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _trigger_event(self, event: str, data: Any):
        """
        Déclenche un événement
        
        Args:
            event: Événement
            data: Données
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # ============================================================
    # ALERTS
    # ============================================================
    
    def _add_alert(self, message: str, severity: str = "info"):
        """
        Ajoute une alerte
        
        Args:
            message: Message
            severity: Sévérité
        """
        alert = {
            'timestamp': time.time(),
            'severity': severity,
            'message': message,
        }
        self.alerts.append(alert)
        
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    # ============================================================
    # MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            return
        
        self._running = True
        self._update_task = threading.Thread(target=self._update_loop, daemon=True)
        self._update_task.start()
        
        logger.info("PerpetualManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("PerpetualManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_contracts()
                self._check_funding()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_contracts(self):
        """Met à jour les contrats"""
        # À implémenter avec les prix réels
        pass
    
    def _check_funding(self):
        """Vérifie les taux de financement"""
        now = datetime.now()
        for contract in self.active_contracts.values():
            if now >= contract.next_funding_time:
                self._pay_funding(contract.id)

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_perpetual_manager: Optional[PerpetualManager] = None

def get_perpetual_manager(
    config: Optional[PerpetualConfig] = None
) -> PerpetualManager:
    """
    Récupère le gestionnaire de contrats perpétuels (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        PerpetualManager: Gestionnaire de contrats perpétuels
    """
    global _perpetual_manager
    if _perpetual_manager is None:
        _perpetual_manager = PerpetualManager(config)
    return _perpetual_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'PerpetualType',
    'PerpetualSide',
    'PerpetualStatus',
    'FundingRateMode',
    'PerpetualContract',
    'FundingRate',
    'PerpetualMetrics',
    'PerpetualConfig',
    'PerpetualManager',
    'get_perpetual_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Perpetual manager module initialized")

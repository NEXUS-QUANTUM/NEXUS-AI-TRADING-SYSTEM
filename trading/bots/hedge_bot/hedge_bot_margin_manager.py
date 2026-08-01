# trading/bots/hedge_bot/hedge_bot_margin_manager.py
# Advanced Margin Management & Collateral Optimization Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Margin Manager Module - Module avancé de gestion de marge et d'optimisation des collatéraux
pour le Hedge Bot. Gère les exigences de marge, le collateral, l'appel de marge,
l'optimisation des garanties, et la gestion des risques pour les positions de hedging.
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
logger = get_logger("hedge_bot_margin_manager")

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

class MarginType(Enum):
    """Types de marge."""
    INITIAL = "initial"
    MAINTENANCE = "maintenance"
    VARIATION = "variation"
    ISOLATED = "isolated"
    CROSS = "cross"
    PORTFOLIO = "portfolio"


class CollateralType(Enum):
    """Types de collatéral."""
    CASH = "cash"
    STOCKS = "stocks"
    BONDS = "bonds"
    CRYPTO = "crypto"
    COMMODITIES = "commodities"
    FIAT = "fiat"
    STABLECOINS = "stablecoins"


class MarginStatus(Enum):
    """Statuts de marge."""
    HEALTHY = "healthy"
    WARNING = "warning"
    MARGIN_CALL = "margin_call"
    LIQUIDATION = "liquidation"
    CLOSED = "closed"


# ============== DATA MODELS ==============

@dataclass
class MarginAccount:
    """Compte de marge."""
    account_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    total_equity: float = 0.0
    total_margin: float = 0.0
    free_margin: float = 0.0
    used_margin: float = 0.0
    margin_level: float = 0.0
    maintenance_margin: float = 0.0
    initial_margin: float = 0.0
    margin_type: MarginType = MarginType.CROSS
    status: MarginStatus = MarginStatus.HEALTHY
    collaterals: List[Dict[str, Any]] = field(default_factory=list)
    positions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_margin_call: Optional[datetime] = None
    liquidation_price: float = 0.0


@dataclass
class MarginPosition:
    """Position de marge."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    symbol: str = ""
    side: str = ""  # long, short
    quantity: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    notional_value: float = 0.0
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    liquidation_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    margin_used: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MarginCall:
    """Appel de marge."""
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    type: MarginType = MarginType.MAINTENANCE
    amount: float = 0.0
    required_amount: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deadline: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    status: str = "pending"  # pending, resolved, expired, liquidated
    notification_sent: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollateralOptimization:
    """Optimisation de collatéral."""
    optimization_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    current_collaterals: List[Dict[str, Any]] = field(default_factory=list)
    optimized_collaterals: List[Dict[str, Any]] = field(default_factory=list)
    efficiency_gain: float = 0.0
    cost_reduction: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class MarginManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de marge."""
    
    @abstractmethod
    async def create_account(self, config: Dict[str, Any]) -> MarginAccount:
        """Crée un compte de marge."""
        pass
    
    @abstractmethod
    async def calculate_margin(self, position: MarginPosition) -> Dict[str, float]:
        """Calcule les exigences de marge."""
        pass
    
    @abstractmethod
    async def check_margin_level(self, account_id: str) -> MarginStatus:
        """Vérifie le niveau de marge."""
        pass
    
    @abstractmethod
    async def add_collateral(self, account_id: str, collateral: Dict[str, Any]) -> bool:
        """Ajoute un collatéral."""
        pass


# ============== IMPLÉMENTATION ==============

class MarginManager(MarginManagerInterface):
    """
    Gestionnaire de marge avancé pour le Hedge Bot.
    Gère les exigences de marge, le collateral et les appels de marge.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des comptes
        self._accounts: Dict[str, MarginAccount] = {}
        self._accounts_lock = threading.RLock()
        
        # Gestion des positions
        self._positions: Dict[str, MarginPosition] = {}
        self._positions_lock = threading.RLock()
        
        # Gestion des appels de marge
        self._margin_calls: Dict[str, MarginCall] = {}
        self._calls_lock = threading.RLock()
        
        # Gestion des optimisations
        self._optimizations: Dict[str, CollateralOptimization] = {}
        self._opt_lock = threading.RLock()
        
        # Cache des prix
        self._price_cache: Dict[str, float] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "accounts_created": 0,
            "positions_tracked": 0,
            "margin_calls_issued": 0,
            "margin_calls_resolved": 0,
            "liquidations_performed": 0,
            "total_margin_used": 0.0,
            "avg_margin_level": 0.0,
            "collateral_efficiency": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("MarginManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_margin_type": MarginType.CROSS,
            "initial_margin_rate": 0.1,
            "maintenance_margin_rate": 0.05,
            "margin_call_threshold": 1.2,
            "liquidation_threshold": 1.05,
            "warning_threshold": 1.5,
            "collateral_optimization_interval": 3600,
            "margin_check_interval": 60,
            "max_leverage": 10.0,
            "min_collateral_ratio": 0.8,
            "auto_add_collateral": True,
            "auto_liquidation": False
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire de marge."""
        logger.info("MarginManager starting...")
        self._is_running = True
        
        # Chargement des comptes
        await self._load_accounts()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._margin_monitor())
        asyncio.create_task(self._collateral_optimizer())
        asyncio.create_task(self._price_updater())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("MarginManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de marge."""
        logger.info("MarginManager stopping...")
        self._is_running = False
        
        # Sauvegarde des comptes
        await self._save_accounts()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("MarginManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_account(self, config: Dict[str, Any]) -> MarginAccount:
        """Crée un compte de marge."""
        account = MarginAccount(
            user_id=config.get("user_id", str(uuid.uuid4())),
            margin_type=MarginType(config.get("margin_type", "cross")),
            initial_margin=config.get("initial_margin", 10000.0),
            maintenance_margin=config.get("maintenance_margin", 5000.0),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        with self._accounts_lock:
            self._accounts[account.account_id] = account
            self._stats["accounts_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"margin:account:{account.account_id}",
                account.to_dict(),
                DataType.ACCOUNT
            )
        
        logger.info(f"Margin account created: {account.account_id}")
        return account
    
    async def calculate_margin(self, position: MarginPosition) -> Dict[str, float]:
        """Calcule les exigences de marge."""
        # Calcul de la valeur notionnelle
        notional_value = position.quantity * position.current_price
        
        # Calcul de la marge initiale
        initial_margin = notional_value * self.config["initial_margin_rate"]
        
        # Calcul de la marge de maintenance
        maintenance_margin = notional_value * self.config["maintenance_margin_rate"]
        
        # Calcul du prix de liquidation
        liquidation_price = self._calculate_liquidation_price(
            position.entry_price,
            position.side,
            position.quantity,
            maintenance_margin
        )
        
        return {
            "initial_margin": initial_margin,
            "maintenance_margin": maintenance_margin,
            "notional_value": notional_value,
            "liquidation_price": liquidation_price,
            "leverage": notional_value / initial_margin if initial_margin > 0 else 0
        }
    
    async def check_margin_level(self, account_id: str) -> MarginStatus:
        """Vérifie le niveau de marge."""
        with self._accounts_lock:
            account = self._accounts.get(account_id)
            if not account:
                return MarginStatus.CLOSED
        
        # Calcul du niveau de marge
        margin_level = account.total_equity / account.total_margin if account.total_margin > 0 else 0
        
        # Détermination du statut
        if margin_level > self.config["warning_threshold"]:
            status = MarginStatus.HEALTHY
        elif margin_level > self.config["margin_call_threshold"]:
            status = MarginStatus.WARNING
        elif margin_level > self.config["liquidation_threshold"]:
            status = MarginStatus.MARGIN_CALL
        else:
            status = MarginStatus.LIQUIDATION
        
        # Mise à jour du compte
        account.margin_level = margin_level
        account.status = status
        
        return status
    
    async def add_collateral(self, account_id: str, collateral: Dict[str, Any]) -> bool:
        """Ajoute un collatéral."""
        with self._accounts_lock:
            account = self._accounts.get(account_id)
            if not account:
                return False
            
            # Ajout du collatéral
            account.collaterals.append(collateral)
            
            # Mise à jour de l'équité
            account.total_equity += collateral.get("value", 0)
            
            account.updated_at = datetime.now(timezone.utc)
            return True
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    def _calculate_liquidation_price(
        self,
        entry_price: float,
        side: str,
        quantity: float,
        maintenance_margin: float
    ) -> float:
        """Calcule le prix de liquidation."""
        if side == "long":
            liquidation_price = entry_price * (1 - maintenance_margin / (entry_price * quantity))
        else:
            liquidation_price = entry_price * (1 + maintenance_margin / (entry_price * quantity))
        
        return liquidation_price
    
    async def _get_current_price(self, symbol: str) -> float:
        """Récupère le prix actuel."""
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
                price = price_data.get("price", 0.0)
                with self._cache_lock:
                    self._price_cache[symbol] = price
                return price
        
        return 0.0
    
    # ========== MÉTHODES PRIVÉES - MONITORING ==========
    
    async def _margin_monitor(self) -> None:
        """Monitor les niveaux de marge."""
        while self._is_running:
            await asyncio.sleep(self.config["margin_check_interval"])
            
            try:
                with self._accounts_lock:
                    for account in self._accounts.values():
                        # Vérification du niveau de marge
                        status = await self.check_margin_level(account.account_id)
                        
                        # Gestion des appels de marge
                        if status == MarginStatus.MARGIN_CALL:
                            await self._handle_margin_call(account)
                        elif status == MarginStatus.LIQUIDATION:
                            await self._handle_liquidation(account)
                
            except Exception as e:
                logger.error(f"Margin monitor error: {e}")
    
    async def _handle_margin_call(self, account: MarginAccount) -> None:
        """Gère un appel de marge."""
        # Création de l'appel de marge
        margin_call = MarginCall(
            account_id=account.account_id,
            amount=account.total_margin - account.total_equity,
            required_amount=account.total_margin * 0.2
        )
        
        with self._calls_lock:
            self._margin_calls[margin_call.call_id] = margin_call
            self._stats["margin_calls_issued"] += 1
        
        # Notification
        logger.warning(f"Margin call issued for account {account.account_id}: {margin_call.amount:.2f}")
        
        # Si auto_add_collateral est activé
        if self.config["auto_add_collateral"]:
            # Dans un système réel, on ajouterait automatiquement du collatéral
            pass
        
        # Envoi de notification
        if self.data_manager:
            await self.data_manager.store(
                f"margin:call:{margin_call.call_id}",
                margin_call.to_dict(),
                DataType.ALERT
            )
    
    async def _handle_liquidation(self, account: MarginAccount) -> None:
        """Gère la liquidation."""
        logger.warning(f"Liquidation triggered for account {account.account_id}")
        
        # Dans un système réel, on exécuterait la liquidation
        self._stats["liquidations_performed"] += 1
        
        # Fermeture des positions
        # Mise à jour du compte
        account.status = MarginStatus.CLOSED
    
    async def _collateral_optimizer(self) -> None:
        """Optimise les collatéraux périodiquement."""
        while self._is_running:
            await asyncio.sleep(self.config["collateral_optimization_interval"])
            
            try:
                with self._accounts_lock:
                    for account in self._accounts.values():
                        # Optimisation du collatéral
                        optimization = await self._optimize_collateral(account)
                        
                        with self._opt_lock:
                            self._optimizations[optimization.optimization_id] = optimization
                        
                        # Application des optimisations
                        if optimization.recommendations:
                            logger.info(f"Collateral optimization for {account.account_id}: {len(optimization.recommendations)} recommendations")
                
            except Exception as e:
                logger.error(f"Collateral optimizer error: {e}")
    
    async def _optimize_collateral(self, account: MarginAccount) -> CollateralOptimization:
        """Optimise le collatéral d'un compte."""
        # Analyse des collatéraux actuels
        current_collaterals = account.collaterals.copy()
        
        # Optimisation simplifiée
        optimized_collaterals = []
        efficiency_gain = 0.0
        cost_reduction = 0.0
        recommendations = []
        
        # Simulation d'optimisation
        if current_collaterals:
            # Tri par efficacité
            sorted_collaterals = sorted(
                current_collaterals,
                key=lambda c: c.get("efficiency", 0.5),
                reverse=True
            )
            
            optimized_collaterals = sorted_collaterals[:len(sorted_collaterals) // 2]
            efficiency_gain = 0.1
            cost_reduction = 0.05
            
            recommendations = [
                "Replace low-efficiency collaterals with higher-efficiency ones",
                "Consider using stablecoins for better capital efficiency",
                "Diversify collateral types to reduce correlation risk"
            ]
        
        return CollateralOptimization(
            account_id=account.account_id,
            current_collaterals=current_collaterals,
            optimized_collaterals=optimized_collaterals,
            efficiency_gain=efficiency_gain,
            cost_reduction=cost_reduction,
            recommendations=recommendations
        )
    
    async def _price_updater(self) -> None:
        """Met à jour les prix en cache."""
        while self._is_running:
            await asyncio.sleep(10)
            
            try:
                if self.data_manager:
                    # Récupération des prix pour tous les symboles
                    for symbol in await self._get_symbols():
                        price = await self._get_current_price(symbol)
                        with self._cache_lock:
                            self._price_cache[symbol] = price
                
            except Exception as e:
                logger.error(f"Price updater error: {e}")
    
    async def _get_symbols(self) -> List[str]:
        """Récupère la liste des symboles."""
        symbols = set()
        
        with self._positions_lock:
            for position in self._positions.values():
                symbols.add(position.symbol)
        
        return list(symbols)
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_accounts(self) -> None:
        """Charge les comptes existants."""
        try:
            if self.data_manager:
                accounts_data = await self.data_manager.retrieve(
                    "margin:accounts",
                    DataType.ACCOUNT
                )
                
                if accounts_data:
                    for a_dict in accounts_data:
                        account = self._deserialize_account(a_dict)
                        if account:
                            with self._accounts_lock:
                                self._accounts[account.account_id] = account
            
            logger.info(f"Loaded {len(self._accounts)} margin accounts")
            
        except Exception as e:
            logger.error(f"Load accounts error: {e}")
    
    async def _save_accounts(self) -> None:
        """Sauvegarde les comptes."""
        try:
            if self.data_manager:
                with self._accounts_lock:
                    for account in self._accounts.values():
                        await self.data_manager.store(
                            f"margin:account:{account.account_id}",
                            account.to_dict(),
                            DataType.ACCOUNT
                        )
            
            logger.info("Margin accounts saved")
            
        except Exception as e:
            logger.error(f"Save accounts error: {e}")
    
    def _deserialize_account(self, data: Dict) -> Optional[MarginAccount]:
        """Désérialise un compte."""
        try:
            return MarginAccount(
                account_id=data.get("account_id", str(uuid.uuid4())),
                user_id=data.get("user_id", ""),
                total_equity=data.get("total_equity", 0.0),
                total_margin=data.get("total_margin", 0.0),
                free_margin=data.get("free_margin", 0.0),
                used_margin=data.get("used_margin", 0.0),
                margin_level=data.get("margin_level", 0.0),
                maintenance_margin=data.get("maintenance_margin", 0.0),
                initial_margin=data.get("initial_margin", 0.0),
                margin_type=MarginType(data.get("margin_type", "cross")),
                status=MarginStatus(data.get("status", "healthy")),
                collaterals=data.get("collaterals", []),
                positions=data.get("positions", []),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                last_margin_call=datetime.fromisoformat(data.get("last_margin_call")) if data.get("last_margin_call") else None,
                liquidation_price=data.get("liquidation_price", 0.0)
            )
        except Exception as e:
            logger.error(f"Error deserializing account: {e}")
            return None
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._accounts_lock:
                    self._stats["total_accounts"] = len(self._accounts)
                    total_margin = sum(a.total_margin for a in self._accounts.values())
                    self._stats["total_margin_used"] = total_margin
                    
                    avg_level = np.mean([a.margin_level for a in self._accounts.values()]) if self._accounts else 0
                    self._stats["avg_margin_level"] = avg_level
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "margin:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_account(self, account_id: str) -> Optional[MarginAccount]:
        """Récupère un compte."""
        with self._accounts_lock:
            return self._accounts.get(account_id)
    
    async def get_accounts(self) -> List[MarginAccount]:
        """Récupère les comptes."""
        with self._accounts_lock:
            return list(self._accounts.values())
    
    async def get_position(self, position_id: str) -> Optional[MarginPosition]:
        """Récupère une position."""
        with self._positions_lock:
            return self._positions.get(position_id)
    
    async def get_positions(self, account_id: str) -> List[MarginPosition]:
        """Récupère les positions d'un compte."""
        with self._positions_lock:
            return [p for p in self._positions.values() if p.account_id == account_id]
    
    async def get_margin_call(self, call_id: str) -> Optional[MarginCall]:
        """Récupère un appel de marge."""
        with self._calls_lock:
            return self._margin_calls.get(call_id)
    
    async def get_margin_calls(self, account_id: str) -> List[MarginCall]:
        """Récupère les appels de marge d'un compte."""
        with self._calls_lock:
            return [c for c in self._margin_calls.values() if c.account_id == account_id]
    
    async def resolve_margin_call(self, call_id: str) -> bool:
        """Résout un appel de marge."""
        with self._calls_lock:
            margin_call = self._margin_calls.get(call_id)
            if not margin_call or margin_call.status != "pending":
                return False
            
            margin_call.status = "resolved"
            self._stats["margin_calls_resolved"] += 1
            return True
    
    async def get_collateral_optimization(self, account_id: str) -> Optional[CollateralOptimization]:
        """Récupère l'optimisation de collatéral."""
        with self._opt_lock:
            for opt in self._optimizations.values():
                if opt.account_id == account_id:
                    return opt
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._accounts_lock:
            self._stats["total_accounts"] = len(self._accounts)
        
        return self._stats.copy()


# ============== MARGIN CALCULATOR ==============

class MarginCalculator:
    """
    Calculateur de marge avancé.
    Calcule les exigences de marge pour différents produits.
    """
    
    @staticmethod
    def calculate_futures_margin(
        contract_size: float,
        price: float,
        quantity: float,
        initial_margin_rate: float,
        maintenance_margin_rate: float
    ) -> Dict[str, float]:
        """Calcule la marge pour les futures."""
        notional_value = contract_size * price * quantity
        
        return {
            "initial_margin": notional_value * initial_margin_rate,
            "maintenance_margin": notional_value * maintenance_margin_rate,
            "notional_value": notional_value
        }
    
    @staticmethod
    def calculate_options_margin(
        strike: float,
        premium: float,
        quantity: float,
        option_type: str,
        underlying_price: float
    ) -> Dict[str, float]:
        """Calcule la marge pour les options."""
        # Simulation de calcul de marge
        if option_type == "call":
            margin = strike * quantity * 0.1
        else:
            margin = strike * quantity * 0.1
        
        return {
            "initial_margin": margin,
            "maintenance_margin": margin * 0.5,
            "premium": premium * quantity
        }
    
    @staticmethod
    def calculate_spot_margin(
        price: float,
        quantity: float,
        leverage: float
    ) -> Dict[str, float]:
        """Calcule la marge pour le spot."""
        notional_value = price * quantity
        margin = notional_value / leverage
        
        return {
            "initial_margin": margin,
            "maintenance_margin": margin * 0.5,
            "notional_value": notional_value,
            "leverage": leverage
        }


# ============== FACTORY ==============

class MarginManagerFactory:
    """Factory pour créer des composants de gestion de marge."""
    
    @staticmethod
    async def create_manager(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MarginManager:
        """Crée un gestionnaire de marge."""
        manager = MarginManager(
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager
    
    @staticmethod
    def create_calculator() -> MarginCalculator:
        """Crée un calculateur de marge."""
        return MarginCalculator()


# ============== EXPORT ==============

__all__ = [
    "MarginType",
    "CollateralType",
    "MarginStatus",
    "MarginAccount",
    "MarginPosition",
    "MarginCall",
    "CollateralOptimization",
    "MarginManagerInterface",
    "MarginManager",
    "MarginCalculator",
    "MarginManagerFactory"
]

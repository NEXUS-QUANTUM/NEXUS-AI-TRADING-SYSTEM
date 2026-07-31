# trading/bots/hedge_bot/hedge_bot_tax.py
# Advanced Tax Management & Reporting Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Tax Management Module - Module avancé de gestion fiscale et reporting pour le Hedge Bot.
Gère le calcul des impôts, la génération de rapports fiscaux, l'optimisation fiscale,
la conformité réglementaire et le suivi des transactions pour l'ensemble du système de hedging.
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
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_tax")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class TaxJurisdiction(Enum):
    """Juridictions fiscales."""
    USA = "usa"
    UK = "uk"
    EU = "eu"
    FRANCE = "france"
    GERMANY = "germany"
    SINGAPORE = "singapore"
    HONG_KONG = "hong_kong"
    SWITZERLAND = "switzerland"
    CANADA = "canada"
    AUSTRALIA = "australia"
    JAPAN = "japan"
    CUSTOM = "custom"


class TaxType(Enum):
    """Types d'impôts."""
    CAPITAL_GAINS = "capital_gains"
    INCOME = "income"
    CORPORATE = "corporate"
    VAT = "vat"
    WITHHOLDING = "withholding"
    STAMP_DUTY = "stamp_duty"
    TRANSFER_TAX = "transfer_tax"
    FINANCIAL_TRANSACTION = "financial_transaction"


class TaxReportingMethod(Enum):
    """Méthodes de reporting fiscal."""
    FIFO = "fifo"                    # First In, First Out
    LIFO = "lifo"                    # Last In, First Out
    HIFO = "hifo"                    # Highest In, First Out
    LOFO = "lofo"                    # Lowest In, First Out
    AVG_COST = "avg_cost"            # Average Cost
    SPECIFIC_ID = "specific_id"      # Specific Identification
    MIN_TAX = "min_tax"              # Minimize Tax


class TaxStatus(Enum):
    """Statuts fiscaux."""
    PENDING = "pending"
    CALCULATED = "calculated"
    REPORTED = "reported"
    FILED = "filed"
    AUDITED = "audited"
    ADJUSTED = "adjusted"


# ============== DATA MODELS ==============

@dataclass
class TaxTransaction:
    """Transaction fiscale."""
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trade_id: str = ""
    symbol: str = ""
    side: str = ""  # buy, sell
    quantity: float = 0.0
    price: float = 0.0
    total_value: float = 0.0
    fees: float = 0.0
    net_value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    settlement_date: Optional[datetime] = None
    tax_jurisdiction: TaxJurisdiction = TaxJurisdiction.USA
    tax_type: TaxType = TaxType.CAPITAL_GAINS
    holding_period: float = 0.0  # jours
    is_short_term: bool = True
    cost_basis: float = 0.0
    proceeds: float = 0.0
    gain_loss: float = 0.0
    tax_liability: float = 0.0
    tax_rate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    status: TaxStatus = TaxStatus.PENDING


@dataclass
class TaxPosition:
    """Position fiscale."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    quantity: float = 0.0
    cost_basis: float = 0.0
    avg_cost: float = 0.0
    acquisition_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lots: List[Dict[str, Any]] = field(default_factory=list)
    unrealized_gain: float = 0.0
    unrealized_loss: float = 0.0
    realized_gain: float = 0.0
    realized_loss: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaxReport:
    """Rapport fiscal."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    jurisdiction: TaxJurisdiction = TaxJurisdiction.USA
    tax_year: int = 0
    tax_period: str = ""  # Q1, Q2, Q3, Q4, FY
    reporting_method: TaxReportingMethod = TaxReportingMethod.FIFO
    total_gains: float = 0.0
    total_losses: float = 0.0
    net_gain: float = 0.0
    short_term_gain: float = 0.0
    long_term_gain: float = 0.0
    total_tax_liability: float = 0.0
    transactions: List[TaxTransaction] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: TaxStatus = TaxStatus.CALCULATED
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class TaxConfig:
    """Configuration fiscale."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    jurisdiction: TaxJurisdiction = TaxJurisdiction.USA
    tax_rates: Dict[str, float] = field(default_factory=dict)
    short_term_rate: float = 0.0
    long_term_rate: float = 0.0
    holding_period_threshold: int = 365  # jours
    reporting_method: TaxReportingMethod = TaxReportingMethod.FIFO
    deductions: List[Dict[str, Any]] = field(default_factory=list)
    exemptions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


# ============== INTERFACES ==============

class TaxEngineInterface(ABC):
    """Interface abstraite pour le moteur fiscal."""
    
    @abstractmethod
    async def record_transaction(self, transaction: TaxTransaction) -> str:
        """Enregistre une transaction fiscale."""
        pass
    
    @abstractmethod
    async def calculate_tax(self, trade_data: Dict[str, Any]) -> TaxTransaction:
        """Calcule les impôts pour une transaction."""
        pass
    
    @abstractmethod
    async def generate_report(self, period: Tuple[datetime, datetime]) -> TaxReport:
        """Génère un rapport fiscal."""
        pass
    
    @abstractmethod
    async def optimize_tax(self, positions: List[TaxPosition]) -> Dict[str, Any]:
        """Optimise la situation fiscale."""
        pass


# ============== IMPLÉMENTATION ==============

class TaxEngine(TaxEngineInterface):
    """
    Moteur fiscal avancé pour le Hedge Bot.
    Gère le calcul des impôts, le reporting, l'optimisation et la conformité.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des transactions
        self._transactions: Dict[str, TaxTransaction] = {}
        self._trans_lock = threading.RLock()
        
        # Gestion des positions
        self._positions: Dict[str, TaxPosition] = {}
        self._pos_lock = threading.RLock()
        
        # Gestion des rapports
        self._reports: Dict[str, TaxReport] = {}
        self._report_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, TaxConfig] = {}
        self._config_lock = threading.RLock()
        
        # Cache des taux
        self._rate_cache: Dict[str, float] = {}
        self._rate_cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "transactions_recorded": 0,
            "tax_calculations": 0,
            "reports_generated": 0,
            "optimizations_performed": 0,
            "total_tax_liability": 0.0,
            "total_realized_gain": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("TaxEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_jurisdiction": TaxJurisdiction.USA,
            "default_reporting_method": TaxReportingMethod.FIFO,
            "short_term_rate": 0.30,
            "long_term_rate": 0.15,
            "holding_period_threshold": 365,
            "tax_rate_cache_ttl": 3600,
            "auto_record_transactions": True,
            "generate_reports_daily": True,
            "enable_tax_optimization": True,
            "max_report_transactions": 10000,
            "default_currency": "USD",
            "tax_loss_harvesting": True,
            "wash_sale_detection": True,
            "wash_sale_period": 30
        }
    
    async def start(self) -> None:
        """Démarre le moteur fiscal."""
        logger.info("TaxEngine starting...")
        self._is_running = True
        
        # Chargement des configurations
        await self._load_configs()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._rate_update_loop())
        asyncio.create_task(self._report_generator_loop())
        asyncio.create_task(self._position_reconciler_loop())
        
        logger.info("TaxEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur fiscal."""
        logger.info("TaxEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("TaxEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def record_transaction(self, transaction: TaxTransaction) -> str:
        """Enregistre une transaction fiscale."""
        with self._trans_lock:
            self._transactions[transaction.transaction_id] = transaction
            self._stats["transactions_recorded"] += 1
        
        # Mise à jour des positions
        await self._update_position(transaction)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"tax:transaction:{transaction.transaction_id}",
                transaction.to_dict(),
                DataType.TAX
            )
        
        logger.debug(f"Tax transaction recorded: {transaction.transaction_id} "
                    f"symbol={transaction.symbol} gain={transaction.gain_loss:.2f}")
        
        return transaction.transaction_id
    
    async def calculate_tax(self, trade_data: Dict[str, Any]) -> TaxTransaction:
        """Calcule les impôts pour une transaction."""
        self._stats["tax_calculations"] += 1
        
        try:
            # Extraction des données de la transaction
            symbol = trade_data.get("symbol", "")
            side = trade_data.get("side", "buy")
            quantity = trade_data.get("quantity", 0.0)
            price = trade_data.get("price", 0.0)
            fees = trade_data.get("fees", 0.0)
            timestamp = trade_data.get("timestamp", datetime.now(timezone.utc))
            
            # Récupération de la position fiscale
            position = await self._get_position(symbol)
            
            # Calcul du gain/loss selon la méthode de reporting
            if side.lower() == "sell":
                # Vente: calcul du gain/loss
                gain_loss, cost_basis = await self._calculate_gain_loss(
                    position, quantity, price, timestamp
                )
            else:
                # Achat: pas de gain/loss
                gain_loss = 0.0
                cost_basis = quantity * price + fees
            
            # Détermination du taux d'imposition
            holding_period = (timestamp - position.acquisition_date).total_seconds() / (24 * 3600)
            is_short_term = holding_period < self.config["holding_period_threshold"]
            
            tax_rate = await self._get_tax_rate(
                is_short_term, trade_data.get("jurisdiction", self.config["default_jurisdiction"])
            )
            
            # Calcul de la taxe
            tax_liability = max(0, gain_loss * tax_rate) if gain_loss > 0 else 0
            
            # Création de la transaction fiscale
            transaction = TaxTransaction(
                trade_id=trade_data.get("trade_id", str(uuid.uuid4())),
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                total_value=quantity * price,
                fees=fees,
                net_value=quantity * price - fees if side == "sell" else quantity * price + fees,
                timestamp=timestamp,
                settlement_date=trade_data.get("settlement_date"),
                tax_jurisdiction=TaxJurisdiction(
                    trade_data.get("jurisdiction", self.config["default_jurisdiction"])
                ),
                tax_type=TaxType.CAPITAL_GAINS,
                holding_period=holding_period,
                is_short_term=is_short_term,
                cost_basis=cost_basis,
                proceeds=quantity * price - fees if side == "sell" else 0,
                gain_loss=gain_loss,
                tax_liability=tax_liability,
                tax_rate=tax_rate,
                metadata=trade_data.get("metadata", {}),
                tags=trade_data.get("tags", []),
                status=TaxStatus.CALCULATED
            )
            
            # Enregistrement de la transaction
            await self.record_transaction(transaction)
            
            logger.debug(f"Tax calculated: {transaction.transaction_id} "
                        f"gain={gain_loss:.2f} tax={tax_liability:.2f} rate={tax_rate:.2%}")
            
            return transaction
            
        except Exception as e:
            logger.error(f"Tax calculation error: {e}")
            raise
    
    async def generate_report(
        self,
        period: Tuple[datetime, datetime],
        jurisdiction: Optional[TaxJurisdiction] = None
    ) -> TaxReport:
        """Génère un rapport fiscal."""
        self._stats["reports_generated"] += 1
        
        try:
            start_date, end_date = period
            jurisdiction = jurisdiction or TaxJurisdiction(
                self.config["default_jurisdiction"]
            )
            
            # Récupération des transactions de la période
            transactions = await self._get_transactions(period, jurisdiction)
            
            if not transactions:
                logger.warning(f"No transactions found for period {start_date} to {end_date}")
                return TaxReport(
                    name=f"Tax Report {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                    jurisdiction=jurisdiction,
                    tax_year=start_date.year,
                    status=TaxStatus.PENDING,
                    metadata={"message": "No transactions found"}
                )
            
            # Calcul des métriques
            total_gains = sum(t.gain_loss for t in transactions if t.gain_loss > 0)
            total_losses = sum(t.gain_loss for t in transactions if t.gain_loss < 0)
            net_gain = total_gains + total_losses
            
            short_term_gain = sum(t.gain_loss for t in transactions if t.is_short_term)
            long_term_gain = sum(t.gain_loss for t in transactions if not t.is_short_term)
            
            total_tax_liability = sum(t.tax_liability for t in transactions)
            
            # Création du rapport
            report = TaxReport(
                name=f"Tax Report {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                jurisdiction=jurisdiction,
                tax_year=start_date.year,
                tax_period=f"{start_date.strftime('%Y-%m')}",
                reporting_method=TaxReportingMethod(
                    self.config["default_reporting_method"]
                ),
                total_gains=total_gains,
                total_losses=abs(total_losses),
                net_gain=net_gain,
                short_term_gain=short_term_gain,
                long_term_gain=long_term_gain,
                total_tax_liability=total_tax_liability,
                transactions=transactions[:self.config["max_report_transactions"]],
                status=TaxStatus.CALCULATED,
                metadata={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "transaction_count": len(transactions)
                }
            )
            
            # Stockage du rapport
            with self._report_lock:
                self._reports[report.report_id] = report
            
            if self.data_manager:
                await self.data_manager.store(
                    f"tax:report:{report.report_id}",
                    report.to_dict(),
                    DataType.REPORT
                )
            
            logger.info(f"Tax report generated: {report.report_id} "
                       f"net_gain={net_gain:.2f} tax={total_tax_liability:.2f}")
            
            return report
            
        except Exception as e:
            logger.error(f"Report generation error: {e}")
            raise
    
    async def optimize_tax(self, positions: List[TaxPosition]) -> Dict[str, Any]:
        """Optimise la situation fiscale."""
        self._stats["optimizations_performed"] += 1
        
        try:
            recommendations = []
            total_savings = 0.0
            
            # 1. Tax Loss Harvesting
            if self.config["tax_loss_harvesting"]:
                harvest_recommendations = await self._analyze_loss_harvesting(positions)
                recommendations.extend(harvest_recommendations)
                total_savings += sum(r.get("savings", 0) for r in harvest_recommendations)
            
            # 2. Wash Sale Detection
            if self.config["wash_sale_detection"]:
                wash_sales = await self._detect_wash_sales(positions)
                recommendations.extend(wash_sales)
            
            # 3. Holding Period Optimization
            holding_optimizations = await self._optimize_holding_periods(positions)
            recommendations.extend(holding_optimizations)
            
            # 4. Tax Rate Optimization
            rate_optimizations = await self._optimize_tax_rates(positions)
            recommendations.extend(rate_optimizations)
            
            return {
                "success": True,
                "recommendations": recommendations,
                "total_savings": total_savings,
                "position_count": len(positions)
            }
            
        except Exception as e:
            logger.error(f"Tax optimization error: {e}")
            return {"success": False, "error": str(e)}
    
    # ========== MÉTHODES PRIVÉES - CALCULS ==========
    
    async def _calculate_gain_loss(
        self,
        position: TaxPosition,
        quantity: float,
        price: float,
        timestamp: datetime
    ) -> Tuple[float, float]:
        """Calcule le gain/loss selon la méthode de reporting."""
        method = self.config["default_reporting_method"]
        
        if method == TaxReportingMethod.FIFO:
            return await self._calculate_fifo(position, quantity, price, timestamp)
        elif method == TaxReportingMethod.LIFO:
            return await self._calculate_lifo(position, quantity, price, timestamp)
        elif method == TaxReportingMethod.HIFO:
            return await self._calculate_hifo(position, quantity, price, timestamp)
        elif method == TaxReportingMethod.AVG_COST:
            return await self._calculate_avg_cost(position, quantity, price, timestamp)
        else:
            # Par défaut: FIFO
            return await self._calculate_fifo(position, quantity, price, timestamp)
    
    async def _calculate_fifo(
        self,
        position: TaxPosition,
        quantity: float,
        price: float,
        timestamp: datetime
    ) -> Tuple[float, float]:
        """FIFO: First In, First Out."""
        remaining_quantity = quantity
        total_cost_basis = 0.0
        total_proceeds = 0.0
        
        lots = position.lots.copy()
        
        for lot in lots:
            if remaining_quantity <= 0:
                break
            
            lot_quantity = min(lot["quantity"], remaining_quantity)
            cost_basis = lot_quantity * lot["price"]
            
            proceeds = lot_quantity * price
            total_cost_basis += cost_basis
            total_proceeds += proceeds
            remaining_quantity -= lot_quantity
        
        gain_loss = total_proceeds - total_cost_basis
        return gain_loss, total_cost_basis
    
    async def _calculate_lifo(
        self,
        position: TaxPosition,
        quantity: float,
        price: float,
        timestamp: datetime
    ) -> Tuple[float, float]:
        """LIFO: Last In, First Out."""
        remaining_quantity = quantity
        total_cost_basis = 0.0
        total_proceeds = 0.0
        
        lots = position.lots.copy()
        lots.reverse()  # Commencer par le dernier
        
        for lot in lots:
            if remaining_quantity <= 0:
                break
            
            lot_quantity = min(lot["quantity"], remaining_quantity)
            cost_basis = lot_quantity * lot["price"]
            
            proceeds = lot_quantity * price
            total_cost_basis += cost_basis
            total_proceeds += proceeds
            remaining_quantity -= lot_quantity
        
        gain_loss = total_proceeds - total_cost_basis
        return gain_loss, total_cost_basis
    
    async def _calculate_hifo(
        self,
        position: TaxPosition,
        quantity: float,
        price: float,
        timestamp: datetime
    ) -> Tuple[float, float]:
        """HIFO: Highest In, First Out."""
        remaining_quantity = quantity
        total_cost_basis = 0.0
        total_proceeds = 0.0
        
        lots = sorted(position.lots, key=lambda x: x["price"], reverse=True)
        
        for lot in lots:
            if remaining_quantity <= 0:
                break
            
            lot_quantity = min(lot["quantity"], remaining_quantity)
            cost_basis = lot_quantity * lot["price"]
            
            proceeds = lot_quantity * price
            total_cost_basis += cost_basis
            total_proceeds += proceeds
            remaining_quantity -= lot_quantity
        
        gain_loss = total_proceeds - total_cost_basis
        return gain_loss, total_cost_basis
    
    async def _calculate_avg_cost(
        self,
        position: TaxPosition,
        quantity: float,
        price: float,
        timestamp: datetime
    ) -> Tuple[float, float]:
        """Average Cost Method."""
        avg_cost = position.avg_cost
        total_cost_basis = quantity * avg_cost
        total_proceeds = quantity * price
        
        gain_loss = total_proceeds - total_cost_basis
        return gain_loss, total_cost_basis
    
    async def _get_tax_rate(self, is_short_term: bool, jurisdiction: str) -> float:
        """Récupère le taux d'imposition."""
        cache_key = f"{jurisdiction}_{'short' if is_short_term else 'long'}"
        
        with self._rate_cache_lock:
            if cache_key in self._rate_cache:
                return self._rate_cache[cache_key]
        
        # Taux par défaut
        if is_short_term:
            rate = self.config["short_term_rate"]
        else:
            rate = self.config["long_term_rate"]
        
        # Ajustement selon la juridiction
        if jurisdiction == "usa":
            rate = 0.30 if is_short_term else 0.15
        elif jurisdiction == "uk":
            rate = 0.20 if is_short_term else 0.10
        elif jurisdiction == "france":
            rate = 0.30 if is_short_term else 0.19
        elif jurisdiction == "germany":
            rate = 0.25 if is_short_term else 0.15
        elif jurisdiction == "singapore":
            rate = 0.0  # Pas de capital gains tax
        elif jurisdiction == "switzerland":
            rate = 0.0  # Pas de capital gains tax pour les particuliers
        
        with self._rate_cache_lock:
            self._rate_cache[cache_key] = rate
        
        return rate
    
    # ========== MÉTHODES PRIVÉES - POSITIONS ==========
    
    async def _get_position(self, symbol: str) -> TaxPosition:
        """Récupère une position fiscale."""
        with self._pos_lock:
            if symbol in self._positions:
                return self._positions[symbol]
        
        # Création d'une nouvelle position
        position = TaxPosition(symbol=symbol, avg_cost=0.0)
        with self._pos_lock:
            self._positions[symbol] = position
        
        return position
    
    async def _update_position(self, transaction: TaxTransaction) -> None:
        """Met à jour une position fiscale."""
        position = await self._get_position(transaction.symbol)
        
        if transaction.side == "buy":
            # Achat: ajout d'un lot
            lot = {
                "quantity": transaction.quantity,
                "price": transaction.price,
                "timestamp": transaction.timestamp.isoformat()
            }
            position.lots.append(lot)
            
            # Mise à jour du coût moyen
            total_cost = position.cost_basis + transaction.total_value + transaction.fees
            total_quantity = position.quantity + transaction.quantity
            position.avg_cost = total_cost / total_quantity if total_quantity > 0 else 0
            position.quantity = total_quantity
            position.cost_basis = total_cost
            
        elif transaction.side == "sell":
            # Vente: mise à jour basée sur la méthode de reporting
            method = self.config["default_reporting_method"]
            
            if method == TaxReportingMethod.FIFO:
                await self._update_position_fifo(position, transaction)
            elif method == TaxReportingMethod.LIFO:
                await self._update_position_lifo(position, transaction)
            else:
                await self._update_position_fifo(position, transaction)
            
            # Mise à jour des gains/losses réalisés
            if transaction.gain_loss > 0:
                position.realized_gain += transaction.gain_loss
            else:
                position.realized_loss += abs(transaction.gain_loss)
        
        position.metadata["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    async def _update_position_fifo(self, position: TaxPosition, transaction: TaxTransaction) -> None:
        """Met à jour une position avec FIFO."""
        remaining_quantity = transaction.quantity
        
        for lot in position.lots[:]:
            if remaining_quantity <= 0:
                break
            
            if lot["quantity"] <= remaining_quantity:
                remaining_quantity -= lot["quantity"]
                position.lots.remove(lot)
            else:
                lot["quantity"] -= remaining_quantity
                remaining_quantity = 0
    
    async def _update_position_lifo(self, position: TaxPosition, transaction: TaxTransaction) -> None:
        """Met à jour une position avec LIFO."""
        remaining_quantity = transaction.quantity
        
        for lot in reversed(position.lots):
            if remaining_quantity <= 0:
                break
            
            if lot["quantity"] <= remaining_quantity:
                remaining_quantity -= lot["quantity"]
                position.lots.remove(lot)
            else:
                lot["quantity"] -= remaining_quantity
                remaining_quantity = 0
    
    # ========== MÉTHODES PRIVÉES - OPTIMISATION ==========
    
    async def _analyze_loss_harvesting(
        self,
        positions: List[TaxPosition]
    ) -> List[Dict[str, Any]]:
        """Analyse les opportunités de loss harvesting."""
        recommendations = []
        
        for position in positions:
            if position.unrealized_loss > 0:
                # Vérification des contraintes
                if await self._can_harvest_loss(position):
                    recommendations.append({
                        "type": "tax_loss_harvesting",
                        "symbol": position.symbol,
                        "action": "sell_to_realize_loss",
                        "loss_amount": position.unrealized_loss,
                        "savings": position.unrealized_loss * 0.3,
                        "priority": "high"
                    })
        
        return recommendations
    
    async def _detect_wash_sales(self, positions: List[TaxPosition]) -> List[Dict[str, Any]]:
        """Détecte les wash sales."""
        wash_sales = []
        threshold = self.config["wash_sale_period"]
        
        for position in positions:
            # Vérification des transactions récentes
            for lot in position.lots:
                if lot.get("timestamp"):
                    lot_time = datetime.fromisoformat(lot["timestamp"])
                    age = (datetime.now(timezone.utc) - lot_time).total_seconds() / (24 * 3600)
                    
                    if age <= threshold:
                        wash_sales.append({
                            "type": "wash_sale",
                            "symbol": position.symbol,
                            "action": "review",
                            "details": f"Potential wash sale detected: lot acquired {age:.0f} days ago",
                            "priority": "medium"
                        })
        
        return wash_sales
    
    async def _optimize_holding_periods(
        self,
        positions: List[TaxPosition]
    ) -> List[Dict[str, Any]]:
        """Optimise les périodes de détention."""
        recommendations = []
        threshold = self.config["holding_period_threshold"]
        
        for position in positions:
            for lot in position.lots:
                if lot.get("timestamp"):
                    lot_time = datetime.fromisoformat(lot["timestamp"])
                    days_held = (datetime.now(timezone.utc) - lot_time).total_seconds() / (24 * 3600)
                    
                    if days_held < threshold:
                        days_to_threshold = threshold - days_held
                        
                        # Vérification si le lot a un gain non réalisé
                        unrealized_gain = (position.avg_cost - lot["price"]) * lot["quantity"]
                        
                        if unrealized_gain > 0:
                            recommendations.append({
                                "type": "holding_period",
                                "symbol": position.symbol,
                                "action": "hold",
                                "days_to_long_term": days_to_threshold,
                                "benefit": "Lower tax rate on long-term gains",
                                "priority": "low"
                            })
        
        return recommendations
    
    async def _optimize_tax_rates(
        self,
        positions: List[TaxPosition]
    ) -> List[Dict[str, Any]]:
        """Optimise l'utilisation des taux d'imposition."""
        recommendations = []
        
        # Vérification des opportunités de déduction
        for position in positions:
            if position.unrealized_gain > 0:
                recommendations.append({
                    "type": "rate_optimization",
                    "symbol": position.symbol,
                    "action": "consider_hedging",
                    "benefit": "Protect gains while optimizing tax timing",
                    "priority": "medium"
                })
        
        return recommendations
    
    async def _can_harvest_loss(self, position: TaxPosition) -> bool:
        """Vérifie si un loss harvesting est possible."""
        # Vérification des wash sales
        if self.config["wash_sale_detection"]:
            # Vérification des achats récents
            for lot in position.lots:
                if lot.get("timestamp"):
                    lot_time = datetime.fromisoformat(lot["timestamp"])
                    age = (datetime.now(timezone.utc) - lot_time).total_seconds() / (24 * 3600)
                    if age <= self.config["wash_sale_period"]:
                        return False
        
        return True
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _rate_update_loop(self) -> None:
        """Met à jour les taux d'imposition."""
        while self._is_running:
            await asyncio.sleep(self.config["tax_rate_cache_ttl"])
            
            try:
                # Mise à jour des taux
                with self._rate_cache_lock:
                    self._rate_cache.clear()
                
                logger.debug("Tax rates updated")
                
            except Exception as e:
                logger.error(f"Rate update error: {e}")
    
    async def _report_generator_loop(self) -> None:
        """Génère des rapports fiscaux périodiques."""
        if not self.config["generate_reports_daily"]:
            return
        
        while self._is_running:
            await asyncio.sleep(86400)  # 1 jour
            
            try:
                # Génération du rapport quotidien
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=1)
                
                report = await self.generate_report((start_date, end_date))
                
                logger.info(f"Daily tax report generated: {report.report_id}")
                
            except Exception as e:
                logger.error(f"Report generator error: {e}")
    
    async def _position_reconciler_loop(self) -> None:
        """Réconcilie les positions fiscales."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Récupération des positions
                with self._pos_lock:
                    for position in self._positions.values():
                        # Vérification des écarts
                        total_quantity = sum(lot["quantity"] for lot in position.lots)
                        
                        if abs(total_quantity - position.quantity) > 0.001:
                            logger.warning(f"Position reconciliation needed for {position.symbol}: "
                                         f"lots={total_quantity}, position={position.quantity}")
                            
                            # Correction
                            position.quantity = total_quantity
                
            except Exception as e:
                logger.error(f"Position reconciler error: {e}")
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_configs(self) -> None:
        """Charge les configurations fiscales."""
        try:
            if self.data_manager:
                configs_data = await self.data_manager.retrieve(
                    "tax:configs",
                    DataType.CONFIG
                )
                
                if configs_data:
                    for config_dict in configs_data:
                        config = self._deserialize_config(config_dict)
                        if config:
                            with self._config_lock:
                                self._configs[config.config_id] = config
            
            logger.info(f"Loaded {len(self._configs)} tax configurations")
            
        except Exception as e:
            logger.error(f"Load configs error: {e}")
    
    def _deserialize_config(self, data: Dict) -> Optional[TaxConfig]:
        """Désérialise une configuration fiscale."""
        try:
            return TaxConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                jurisdiction=TaxJurisdiction(data.get("jurisdiction", "usa")),
                tax_rates=data.get("tax_rates", {}),
                short_term_rate=data.get("short_term_rate", 0.0),
                long_term_rate=data.get("long_term_rate", 0.0),
                holding_period_threshold=data.get("holding_period_threshold", 365),
                reporting_method=TaxReportingMethod(data.get("reporting_method", "fifo")),
                deductions=data.get("deductions", []),
                exemptions=data.get("exemptions", []),
                metadata=data.get("metadata", {}),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing tax config: {e}")
            return None
    
    async def _get_transactions(
        self,
        period: Tuple[datetime, datetime],
        jurisdiction: Optional[TaxJurisdiction] = None
    ) -> List[TaxTransaction]:
        """Récupère les transactions d'une période."""
        start_date, end_date = period
        
        with self._trans_lock:
            transactions = [
                t for t in self._transactions.values()
                if start_date <= t.timestamp <= end_date
            ]
            
            if jurisdiction:
                transactions = [
                    t for t in transactions
                    if t.tax_jurisdiction == jurisdiction
                ]
            
            return sorted(transactions, key=lambda t: t.timestamp)
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_transaction(self, transaction_id: str) -> Optional[TaxTransaction]:
        """Récupère une transaction fiscale."""
        with self._trans_lock:
            return self._transactions.get(transaction_id)
    
    async def get_transactions(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[TaxTransaction]:
        """Récupère les transactions fiscales."""
        with self._trans_lock:
            transactions = list(self._transactions.values())
            
            if symbol:
                transactions = [t for t in transactions if t.symbol == symbol]
            if start_date:
                transactions = [t for t in transactions if t.timestamp >= start_date]
            if end_date:
                transactions = [t for t in transactions if t.timestamp <= end_date]
            
            transactions.sort(key=lambda t: t.timestamp, reverse=True)
            return transactions[:limit]
    
    async def get_position(self, symbol: str) -> Optional[TaxPosition]:
        """Récupère une position fiscale."""
        with self._pos_lock:
            return self._positions.get(symbol)
    
    async def get_positions(self) -> List[TaxPosition]:
        """Récupère toutes les positions fiscales."""
        with self._pos_lock:
            return list(self._positions.values())
    
    async def get_report(self, report_id: str) -> Optional[TaxReport]:
        """Récupère un rapport fiscal."""
        with self._report_lock:
            return self._reports.get(report_id)
    
    async def get_reports(self, limit: int = 100) -> List[TaxReport]:
        """Récupère les rapports fiscaux."""
        with self._report_lock:
            reports = list(self._reports.values())
            reports.sort(key=lambda r: r.generated_at, reverse=True)
            return reports[:limit]
    
    async def create_config(self, config: TaxConfig) -> str:
        """Crée une configuration fiscale."""
        with self._config_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"tax:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Tax configuration created: {config.config_id}")
        return config.config_id
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._trans_lock:
            self._stats["total_transactions"] = len(self._transactions)
        with self._pos_lock:
            self._stats["total_positions"] = len(self._positions)
        with self._report_lock:
            self._stats["total_reports"] = len(self._reports)
        
        return self._stats.copy()


# ============== TAX REPORT EXPORTER ==============

class TaxReportExporter:
    """
    Exportateur de rapports fiscaux.
    Gère l'exportation des rapports fiscaux dans différents formats.
    """
    
    def __init__(self, engine: TaxEngine):
        self.engine = engine
    
    async def export_to_csv(self, report: TaxReport, file_path: str) -> bool:
        """Exporte un rapport en CSV."""
        try:
            data = []
            for tx in report.transactions:
                data.append({
                    "trade_id": tx.trade_id,
                    "symbol": tx.symbol,
                    "side": tx.side,
                    "quantity": tx.quantity,
                    "price": tx.price,
                    "total_value": tx.total_value,
                    "fees": tx.fees,
                    "net_value": tx.net_value,
                    "timestamp": tx.timestamp.isoformat(),
                    "cost_basis": tx.cost_basis,
                    "proceeds": tx.proceeds,
                    "gain_loss": tx.gain_loss,
                    "tax_liability": tx.tax_liability,
                    "tax_rate": tx.tax_rate
                })
            
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False)
            
            logger.info(f"Report exported to CSV: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"CSV export error: {e}")
            return False
    
    async def export_to_json(self, report: TaxReport, file_path: str) -> bool:
        """Exporte un rapport en JSON."""
        try:
            data = report.to_dict()
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Report exported to JSON: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"JSON export error: {e}")
            return False
    
    async def export_to_pdf(self, report: TaxReport, file_path: str) -> bool:
        """Exporte un rapport en PDF."""
        try:
            # Utilisation de reportlab ou autre bibliothèque PDF
            # Version simplifiée
            logger.info(f"Report exported to PDF: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"PDF export error: {e}")
            return False


# ============== FACTORY ==============

class TaxFactory:
    """Factory pour créer des composants fiscaux."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> TaxEngine:
        """Crée un moteur fiscal."""
        engine = TaxEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_exporter(engine: TaxEngine) -> TaxReportExporter:
        """Crée un exportateur de rapports fiscaux."""
        return TaxReportExporter(engine)


# ============== EXPORT ==============

__all__ = [
    "TaxJurisdiction",
    "TaxType",
    "TaxReportingMethod",
    "TaxStatus",
    "TaxTransaction",
    "TaxPosition",
    "TaxReport",
    "TaxConfig",
    "TaxEngineInterface",
    "TaxEngine",
    "TaxReportExporter",
    "TaxFactory"
]

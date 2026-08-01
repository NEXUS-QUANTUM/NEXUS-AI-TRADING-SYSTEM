# trading/bots/hedge_bot/hedge_bot_liquidation_manager.py
# Advanced Liquidation Management & Risk Prevention Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Liquidation Manager Module - Module avancé de gestion des liquidations et de prévention
des risques pour le Hedge Bot. Gère la prévention des liquidations, la gestion des positions
à risque, les alertes de liquidation, et les stratégies de récupération.
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
logger = get_logger("hedge_bot_liquidation_manager")

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
from trading.bots.hedge_bot.hedge_bot_margin_manager import (
    MarginAccount, MarginPosition, MarginStatus, MarginManager
)


# ============== ENUMS & TYPES ==============

class LiquidationRisk(Enum):
    """Niveaux de risque de liquidation."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    IMMINENT = "imminent"


class LiquidationAction(Enum):
    """Actions de liquidation."""
    NONE = "none"
    REDUCE_POSITION = "reduce_position"
    ADD_COLLATERAL = "add_collateral"
    CLOSE_POSITION = "close_position"
    HEDGE = "hedge"
    REBALANCE = "rebalance"
    EMERGENCY_CLOSE = "emergency_close"


class LiquidationStatus(Enum):
    """Statuts de liquidation."""
    MONITORING = "monitoring"
    WARNING = "warning"
    ACTIVE = "active"
    RECOVERING = "recovering"
    RESOLVED = "resolved"
    LIQUIDATED = "liquidated"


# ============== DATA MODELS ==============

@dataclass
class LiquidationRiskAssessment:
    """Évaluation du risque de liquidation."""
    assessment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    position_id: str = ""
    symbol: str = ""
    risk_level: LiquidationRisk = LiquidationRisk.SAFE
    risk_score: float = 0.0
    liquidation_price: float = 0.0
    current_price: float = 0.0
    distance_to_liquidation: float = 0.0
    margin_level: float = 0.0
    required_margin: float = 0.0
    available_margin: float = 0.0
    recommended_action: LiquidationAction = LiquidationAction.NONE
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class LiquidationEvent:
    """Événement de liquidation."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    position_id: str = ""
    symbol: str = ""
    type: str = ""  # warning, imminent, partial, full
    liquidation_price: float = 0.0
    executed_price: float = 0.0
    quantity: float = 0.0
    status: LiquidationStatus = LiquidationStatus.MONITORING
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class LiquidationPrevention:
    """Prévention de liquidation."""
    prevention_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    strategy: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    effectiveness: float = 0.0
    implemented_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class LiquidationManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de liquidations."""
    
    @abstractmethod
    async def assess_risk(self, position: MarginPosition) -> LiquidationRiskAssessment:
        """Évalue le risque de liquidation."""
        pass
    
    @abstractmethod
    async def monitor_positions(self) -> List[LiquidationRiskAssessment]:
        """Monitor les positions pour les risques de liquidation."""
        pass
    
    @abstractmethod
    async def execute_prevention(self, assessment: LiquidationRiskAssessment) -> bool:
        """Exécute une stratégie de prévention."""
        pass
    
    @abstractmethod
    async def handle_liquidation(self, event: LiquidationEvent) -> bool:
        """Gère un événement de liquidation."""
        pass


# ============== IMPLÉMENTATION ==============

class LiquidationManager(LiquidationManagerInterface):
    """
    Gestionnaire de liquidations avancé pour le Hedge Bot.
    Gère la prévention, la détection et la gestion des liquidations.
    """
    
    def __init__(
        self,
        margin_manager: MarginManager,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.margin_manager = margin_manager
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des évaluations
        self._assessments: Dict[str, LiquidationRiskAssessment] = {}
        self._assessments_lock = threading.RLock()
        
        # Gestion des événements
        self._events: Dict[str, LiquidationEvent] = {}
        self._events_lock = threading.RLock()
        
        # Gestion des préventions
        self._preventions: Dict[str, LiquidationPrevention] = {}
        self._preventions_lock = threading.RLock()
        
        # Cache des prix
        self._price_cache: Dict[str, float] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "assessments_performed": 0,
            "warnings_issued": 0,
            "preventions_executed": 0,
            "liquidations_handled": 0,
            "prevention_success_rate": 0.0,
            "positions_liquidated": 0,
            "avg_risk_score": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("LiquidationManager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "risk_thresholds": {
                "critical": 0.1,
                "high": 0.2,
                "medium": 0.4,
                "low": 0.6
            },
            "monitoring_interval": 10,
            "prevention_check_interval": 5,
            "auto_prevention": True,
            "max_prevention_attempts": 3,
            "hedge_ratio": 0.5,
            "emergency_close_threshold": 0.05,
            "recovery_interval": 60,
            "enable_auto_hedge": True,
            "enable_auto_reduce": True,
            "notification_enabled": True,
            "history_retention_days": 30
        }
    
    async def start(self) -> None:
        """Démarre le gestionnaire de liquidations."""
        logger.info("LiquidationManager starting...")
        self._is_running = True
        
        # Chargement des évaluations
        await self._load_assessments()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._prevention_loop())
        asyncio.create_task(self._recovery_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("LiquidationManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de liquidations."""
        logger.info("LiquidationManager stopping...")
        self._is_running = False
        
        # Sauvegarde des données
        await self._save_data()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("LiquidationManager stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def assess_risk(self, position: MarginPosition) -> LiquidationRiskAssessment:
        """Évalue le risque de liquidation."""
        self._stats["assessments_performed"] += 1
        
        # Récupération du prix actuel
        current_price = await self._get_current_price(position.symbol)
        
        # Calcul de la distance jusqu'à la liquidation
        distance = (position.liquidation_price - current_price) / current_price
        
        # Calcul du score de risque
        risk_score = await self._calculate_risk_score(position, current_price, distance)
        
        # Détermination du niveau de risque
        risk_level = self._determine_risk_level(risk_score)
        
        # Détermination de l'action recommandée
        recommended_action = self._determine_action(risk_level, position)
        
        # Création de l'évaluation
        assessment = LiquidationRiskAssessment(
            account_id=position.account_id,
            position_id=position.position_id,
            symbol=position.symbol,
            risk_level=risk_level,
            risk_score=risk_score,
            liquidation_price=position.liquidation_price,
            current_price=current_price,
            distance_to_liquidation=distance,
            margin_level=position.margin_used / position.initial_margin if position.initial_margin > 0 else 0,
            required_margin=position.maintenance_margin,
            available_margin=position.margin_used - position.maintenance_margin,
            recommended_action=recommended_action,
            metadata={
                "position_size": position.quantity,
                "entry_price": position.entry_price,
                "leverage": position.notional_value / position.initial_margin if position.initial_margin > 0 else 0
            }
        )
        
        # Stockage de l'évaluation
        with self._assessments_lock:
            self._assessments[assessment.assessment_id] = assessment
        
        # Mise à jour des statistiques
        self._stats["avg_risk_score"] = (
            self._stats["avg_risk_score"] * 0.9 + risk_score * 0.1
        )
        
        # Si risque élevé, génération d'une alerte
        if risk_level in [LiquidationRisk.HIGH, LiquidationRisk.CRITICAL, LiquidationRisk.IMMINENT]:
            await self._issue_warning(assessment)
        
        return assessment
    
    async def monitor_positions(self) -> List[LiquidationRiskAssessment]:
        """Monitor les positions pour les risques de liquidation."""
        assessments = []
        
        # Récupération de toutes les positions
        positions = await self._get_all_positions()
        
        for position in positions:
            try:
                assessment = await self.assess_risk(position)
                assessments.append(assessment)
            except Exception as e:
                logger.error(f"Assessment error for position {position.position_id}: {e}")
        
        return assessments
    
    async def execute_prevention(self, assessment: LiquidationRiskAssessment) -> bool:
        """Exécute une stratégie de prévention."""
        self._stats["preventions_executed"] += 1
        
        try:
            # Sélection de la stratégie
            action = assessment.recommended_action
            
            if action == LiquidationAction.REDUCE_POSITION:
                return await self._reduce_position(assessment)
            elif action == LiquidationAction.ADD_COLLATERAL:
                return await self._add_collateral(assessment)
            elif action == LiquidationAction.HEDGE:
                return await self._hedge_position(assessment)
            elif action == LiquidationAction.REBALANCE:
                return await self._rebalance_portfolio(assessment)
            elif action == LiquidationAction.EMERGENCY_CLOSE:
                return await self._emergency_close(assessment)
            else:
                return False
                
        except Exception as e:
            logger.error(f"Prevention error: {e}")
            return False
    
    async def handle_liquidation(self, event: LiquidationEvent) -> bool:
        """Gère un événement de liquidation."""
        self._stats["liquidations_handled"] += 1
        
        with self._events_lock:
            self._events[event.event_id] = event
        
        try:
            # Gestion selon le type d'événement
            if event.type == "warning":
                return await self._handle_warning(event)
            elif event.type == "imminent":
                return await self._handle_imminent(event)
            elif event.type == "partial":
                return await self._handle_partial_liquidation(event)
            elif event.type == "full":
                return await self._handle_full_liquidation(event)
            else:
                return False
                
        except Exception as e:
            logger.error(f"Liquidation handling error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - RISK ==========
    
    async def _calculate_risk_score(self, position: MarginPosition, current_price: float, distance: float) -> float:
        """Calcule le score de risque."""
        # Facteurs de risque
        factors = {
            "distance": max(0, min(1, 1 - abs(distance))),
            "volatility": await self._get_volatility(position.symbol),
            "leverage": min(1, position.notional_value / position.initial_margin if position.initial_margin > 0 else 1),
            "margin_usage": position.margin_used / position.initial_margin if position.initial_margin > 0 else 1,
            "position_size": min(1, position.quantity / 1000)
        }
        
        # Poids des facteurs
        weights = {
            "distance": 0.4,
            "volatility": 0.2,
            "leverage": 0.2,
            "margin_usage": 0.1,
            "position_size": 0.1
        }
        
        # Score pondéré
        risk_score = sum(factors[k] * weights[k] for k in factors)
        
        return min(1.0, risk_score)
    
    def _determine_risk_level(self, risk_score: float) -> LiquidationRisk:
        """Détermine le niveau de risque."""
        thresholds = self.config["risk_thresholds"]
        
        if risk_score > 1 - thresholds["critical"]:
            return LiquidationRisk.IMMINENT
        elif risk_score > 1 - thresholds["high"]:
            return LiquidationRisk.CRITICAL
        elif risk_score > 1 - thresholds["medium"]:
            return LiquidationRisk.HIGH
        elif risk_score > 1 - thresholds["low"]:
            return LiquidationRisk.MEDIUM
        else:
            return LiquidationRisk.LOW
    
    def _determine_action(self, risk_level: LiquidationRisk, position: MarginPosition) -> LiquidationAction:
        """Détermine l'action recommandée."""
        if risk_level == LiquidationRisk.IMMINENT:
            return LiquidationAction.EMERGENCY_CLOSE
        elif risk_level == LiquidationRisk.CRITICAL:
            return LiquidationAction.CLOSE_POSITION
        elif risk_level == LiquidationRisk.HIGH:
            return LiquidationAction.REDUCE_POSITION
        elif risk_level == LiquidationRisk.MEDIUM:
            return LiquidationAction.HEDGE
        else:
            return LiquidationAction.NONE
    
    # ========== MÉTHODES PRIVÉES - PRÉVENTION ==========
    
    async def _reduce_position(self, assessment: LiquidationRiskAssessment) -> bool:
        """Réduit une position à risque."""
        logger.info(f"Reducing position {assessment.position_id}")
        
        # Calcul de la quantité à réduire
        reduction_ratio = 0.5
        if assessment.risk_level == LiquidationRisk.CRITICAL:
            reduction_ratio = 0.7
        elif assessment.risk_level == LiquidationRisk.HIGH:
            reduction_ratio = 0.3
        
        # Dans un système réel, on exécuterait l'ordre de réduction
        return True
    
    async def _add_collateral(self, assessment: LiquidationRiskAssessment) -> bool:
        """Ajoute du collatéral."""
        logger.info(f"Adding collateral for {assessment.account_id}")
        
        # Dans un système réel, on ajouterait du collatéral
        return True
    
    async def _hedge_position(self, assessment: LiquidationRiskAssessment) -> bool:
        """Hedge une position à risque."""
        logger.info(f"Hedging position {assessment.position_id}")
        
        # Dans un système réel, on exécuterait le hedge
        return True
    
    async def _rebalance_portfolio(self, assessment: LiquidationRiskAssessment) -> bool:
        """Rééquilibre le portefeuille."""
        logger.info(f"Rebalancing portfolio for {assessment.account_id}")
        
        # Dans un système réel, on exécuterait le rééquilibrage
        return True
    
    async def _emergency_close(self, assessment: LiquidationRiskAssessment) -> bool:
        """Ferme une position en urgence."""
        logger.warning(f"Emergency closing position {assessment.position_id}")
        
        # Dans un système réel, on fermerait la position en urgence
        self._stats["positions_liquidated"] += 1
        return True
    
    # ========== MÉTHODES PRIVÉES - ÉVÉNEMENTS ==========
    
    async def _issue_warning(self, assessment: LiquidationRiskAssessment) -> None:
        """Émet un avertissement."""
        self._stats["warnings_issued"] += 1
        
        logger.warning(f"Liquidation risk warning: {assessment.symbol} - {assessment.risk_level.value}")
        
        # Stockage de l'avertissement
        event = LiquidationEvent(
            account_id=assessment.account_id,
            position_id=assessment.position_id,
            symbol=assessment.symbol,
            type="warning",
            liquidation_price=assessment.liquidation_price,
            status=LiquidationStatus.WARNING
        )
        
        with self._events_lock:
            self._events[event.event_id] = event
        
        # Notification
        if self.config["notification_enabled"]:
            await self._notify_warning(assessment)
    
    async def _handle_warning(self, event: LiquidationEvent) -> bool:
        """Gère un avertissement."""
        # Évaluation du risque
        position = await self._get_position(event.position_id)
        if not position:
            return False
        
        assessment = await self.assess_risk(position)
        
        # Exécution de la prévention
        if self.config["auto_prevention"]:
            return await self.execute_prevention(assessment)
        
        return True
    
    async def _handle_imminent(self, event: LiquidationEvent) -> bool:
        """Gère une liquidation imminente."""
        logger.critical(f"Imminent liquidation: {event.symbol}")
        
        # Action urgente
        position = await self._get_position(event.position_id)
        if not position:
            return False
        
        assessment = await self.assess_risk(position)
        return await self.execute_prevention(assessment)
    
    async def _handle_partial_liquidation(self, event: LiquidationEvent) -> bool:
        """Gère une liquidation partielle."""
        logger.warning(f"Partial liquidation: {event.symbol} - {event.quantity}")
        
        # Mise à jour de la position
        # Dans un système réel, on mettrait à jour la position
        return True
    
    async def _handle_full_liquidation(self, event: LiquidationEvent) -> bool:
        """Gère une liquidation complète."""
        logger.error(f"Full liquidation: {event.symbol}")
        
        # Mise à jour du statut
        event.status = LiquidationStatus.LIQUIDATED
        event.resolved_at = datetime.now(timezone.utc)
        
        # Dans un système réel, on gérerait la liquidation complète
        return True
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _monitoring_loop(self) -> None:
        """Boucle de monitoring."""
        while self._is_running:
            await asyncio.sleep(self.config["monitoring_interval"])
            
            try:
                await self.monitor_positions()
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
    
    async def _prevention_loop(self) -> None:
        """Boucle de prévention."""
        while self._is_running:
            await asyncio.sleep(self.config["prevention_check_interval"])
            
            try:
                # Vérification des positions à risque élevé
                with self._assessments_lock:
                    high_risk = [
                        a for a in self._assessments.values()
                        if a.risk_level in [LiquidationRisk.HIGH, LiquidationRisk.CRITICAL, LiquidationRisk.IMMINENT]
                    ]
                
                for assessment in high_risk:
                    if self.config["auto_prevention"]:
                        await self.execute_prevention(assessment)
                
            except Exception as e:
                logger.error(f"Prevention loop error: {e}")
    
    async def _recovery_loop(self) -> None:
        """Boucle de récupération."""
        while self._is_running:
            await asyncio.sleep(self.config["recovery_interval"])
            
            try:
                # Récupération des positions liquidées
                with self._events_lock:
                    liquidated = [
                        e for e in self._events.values()
                        if e.status == LiquidationStatus.LIQUIDATED
                    ]
                
                # Dans un système réel, on exécuterait des stratégies de récupération
                
            except Exception as e:
                logger.error(f"Recovery loop error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._assessments_lock:
                    self._stats["total_assessments"] = len(self._assessments)
                with self._events_lock:
                    self._stats["total_events"] = len(self._events)
                    active_events = len([e for e in self._events.values() if e.status not in [LiquidationStatus.RESOLVED, LiquidationStatus.LIQUIDATED]])
                    self._stats["active_events"] = active_events
                
                # Taux de succès des préventions
                if self._stats["preventions_executed"] > 0:
                    success_rate = self._stats.get("positions_liquidated", 0) / self._stats["preventions_executed"]
                    self._stats["prevention_success_rate"] = 1 - success_rate
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "liquidation:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_assessments(self) -> None:
        """Charge les évaluations existantes."""
        try:
            if self.data_manager:
                assessments_data = await self.data_manager.retrieve(
                    "liquidation:assessments",
                    DataType.ASSESSMENT
                )
                
                if assessments_data:
                    for a_dict in assessments_data:
                        assessment = self._deserialize_assessment(a_dict)
                        if assessment:
                            with self._assessments_lock:
                                self._assessments[assessment.assessment_id] = assessment
            
            logger.info(f"Loaded {len(self._assessments)} risk assessments")
            
        except Exception as e:
            logger.error(f"Load assessments error: {e}")
    
    async def _save_data(self) -> None:
        """Sauvegarde les données."""
        try:
            if self.data_manager:
                with self._assessments_lock:
                    for assessment in self._assessments.values():
                        await self.data_manager.store(
                            f"liquidation:assessment:{assessment.assessment_id}",
                            assessment.to_dict(),
                            DataType.ASSESSMENT
                        )
                
                with self._events_lock:
                    for event in self._events.values():
                        await self.data_manager.store(
                            f"liquidation:event:{event.event_id}",
                            event.to_dict(),
                            DataType.EVENT
                        )
            
            logger.info("Liquidation data saved")
            
        except Exception as e:
            logger.error(f"Save data error: {e}")
    
    def _deserialize_assessment(self, data: Dict) -> Optional[LiquidationRiskAssessment]:
        """Désérialise une évaluation."""
        try:
            return LiquidationRiskAssessment(
                assessment_id=data.get("assessment_id", str(uuid.uuid4())),
                account_id=data.get("account_id", ""),
                position_id=data.get("position_id", ""),
                symbol=data.get("symbol", ""),
                risk_level=LiquidationRisk(data.get("risk_level", "safe")),
                risk_score=data.get("risk_score", 0.0),
                liquidation_price=data.get("liquidation_price", 0.0),
                current_price=data.get("current_price", 0.0),
                distance_to_liquidation=data.get("distance_to_liquidation", 0.0),
                margin_level=data.get("margin_level", 0.0),
                required_margin=data.get("required_margin", 0.0),
                available_margin=data.get("available_margin", 0.0),
                recommended_action=LiquidationAction(data.get("recommended_action", "none")),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing assessment: {e}")
            return None
    
    # ========== MÉTHODES UTILITAIRES ==========
    
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
    
    async def _get_all_positions(self) -> List[MarginPosition]:
        """Récupère toutes les positions."""
        # Dans un système réel, on récupérerait les positions depuis le margin manager
        return []
    
    async def _get_position(self, position_id: str) -> Optional[MarginPosition]:
        """Récupère une position."""
        # Dans un système réel, on récupérerait la position depuis le margin manager
        return None
    
    async def _get_volatility(self, symbol: str) -> float:
        """Récupère la volatilité."""
        # Simulation de volatilité
        return 0.2
    
    async def _notify_warning(self, assessment: LiquidationRiskAssessment) -> None:
        """Notifie un avertissement."""
        logger.info(f"Liquidation warning notification: {assessment.symbol} - {assessment.risk_level.value}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_assessment(self, assessment_id: str) -> Optional[LiquidationRiskAssessment]:
        """Récupère une évaluation."""
        with self._assessments_lock:
            return self._assessments.get(assessment_id)
    
    async def get_assessments(self, account_id: str) -> List[LiquidationRiskAssessment]:
        """Récupère les évaluations d'un compte."""
        with self._assessments_lock:
            return [a for a in self._assessments.values() if a.account_id == account_id]
    
    async def get_event(self, event_id: str) -> Optional[LiquidationEvent]:
        """Récupère un événement."""
        with self._events_lock:
            return self._events.get(event_id)
    
    async def get_events(self, account_id: str) -> List[LiquidationEvent]:
        """Récupère les événements d'un compte."""
        with self._events_lock:
            return [e for e in self._events.values() if e.account_id == account_id]
    
    async def get_prevention(self, prevention_id: str) -> Optional[LiquidationPrevention]:
        """Récupère une prévention."""
        with self._preventions_lock:
            return self._preventions.get(prevention_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._assessments_lock:
            self._stats["total_assessments"] = len(self._assessments)
        with self._events_lock:
            self._stats["total_events"] = len(self._events)
        
        return self._stats.copy()


# ============== FACTORY ==============

class LiquidationManagerFactory:
    """Factory pour créer des composants de gestion de liquidations."""
    
    @staticmethod
    async def create_manager(
        margin_manager: MarginManager,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LiquidationManager:
        """Crée un gestionnaire de liquidations."""
        manager = LiquidationManager(
            margin_manager=margin_manager,
            data_manager=data_manager,
            config=config
        )
        await manager.start()
        return manager


# ============== EXPORT ==============

__all__ = [
    "LiquidationRisk",
    "LiquidationAction",
    "LiquidationStatus",
    "LiquidationRiskAssessment",
    "LiquidationEvent",
    "LiquidationPrevention",
    "LiquidationManagerInterface",
    "LiquidationManager",
    "LiquidationManagerFactory"
]

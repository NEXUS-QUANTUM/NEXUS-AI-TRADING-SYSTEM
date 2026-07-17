"""
NEXUS AI TRADING SYSTEM - Order Router for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/execution/order_router.py
Description: Routeur d'ordres intelligent pour le bot AI.
             Supporte le routage vers multiples brokers/exchanges,
             la sélection dynamique des meilleurs prix, la gestion
             de la liquidité, le fallback automatique, et l'optimisation
             des coûts d'exécution.
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import threading

import numpy as np

from trading.brokers.base import Broker
from trading.brokers.broker_factory import BrokerFactory
from trading.bots.ai_bot.execution.order_executor import OrderConfig, OrderExecutionResult, OrderExecutionStatus
from shared.exceptions import OrderRoutingError
from shared.helpers.trading_helpers import validate_symbol

# Configuration du logging
logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Stratégies de routage."""
    BEST_PRICE = "best_price"           # Meilleur prix
    FASTEST = "fastest"                 # Plus rapide
    CHEAPEST = "cheapest"               # Moins cher (frais)
    MOST_LIQUID = "most_liquid"         # Plus liquide
    FIXED = "fixed"                     # Broker fixe
    ROUND_ROBIN = "round_robin"         # Répartition circulaire
    WEIGHTED = "weighted"               # Répartition pondérée
    ADAPTIVE = "adaptive"               # Adaptatif
    SMART = "smart"                     # Intelligent (combinaison)


class BrokerStatus(Enum):
    """Statut d'un broker."""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    UNKNOWN = "unknown"


@dataclass
class BrokerInfo:
    """
    Informations sur un broker.
    """
    name: str
    broker: Broker
    status: BrokerStatus = BrokerStatus.UNKNOWN
    latency_ms: float = 0.0
    success_rate: float = 1.0
    last_used: Optional[datetime] = None
    error_count: int = 0
    total_orders: int = 0
    
    # Frais
    maker_fee: float = 0.001  # 0.1%
    taker_fee: float = 0.001  # 0.1%
    
    # Liquidité
    liquidity_score: float = 1.0
    volume_24h: float = 0.0
    
    # Métriques de performance
    avg_execution_time: float = 0.0
    fill_rate: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'name': self.name,
            'status': self.status.value,
            'latency_ms': round(self.latency_ms, 2),
            'success_rate': round(self.success_rate, 4),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'error_count': self.error_count,
            'total_orders': self.total_orders,
            'maker_fee': self.maker_fee,
            'taker_fee': self.taker_fee,
            'liquidity_score': round(self.liquidity_score, 4),
            'volume_24h': self.volume_24h,
            'avg_execution_time': round(self.avg_execution_time, 4),
            'fill_rate': round(self.fill_rate, 4)
        }


@dataclass
class RouteDecision:
    """
    Décision de routage.
    """
    broker_name: str
    score: float
    reason: str
    estimated_cost: float = 0.0
    estimated_time: float = 0.0
    confidence: float = 1.0


@dataclass
class RouterConfig:
    """
    Configuration du routeur.
    """
    # Stratégie de routage
    strategy: RoutingStrategy = RoutingStrategy.SMART
    
    # Poids des critères (pour SMART)
    weight_price: float = 0.3
    weight_latency: float = 0.2
    weight_cost: float = 0.2
    weight_liquidity: float = 0.2
    weight_reliability: float = 0.1
    
    # Paramètres de performance
    update_interval: float = 60.0  # secondes
    cache_ttl: float = 5.0  # secondes
    max_latency_ms: float = 100.0
    
    # Paramètres de fallback
    fallback_enabled: bool = True
    fallback_timeout: float = 5.0
    max_retries: int = 3
    
    # Paramètres de monitoring
    enable_monitoring: bool = True
    log_routing: bool = True
    save_metrics: bool = True
    
    # Paramètres de sécurité
    require_authentication: bool = True
    require_balance_check: bool = True
    
    def __post_init__(self):
        """Validation des paramètres."""
        # Normalisation des poids
        total = (self.weight_price + self.weight_latency + 
                 self.weight_cost + self.weight_liquidity + 
                 self.weight_reliability)
        if total > 0:
            self.weight_price /= total
            self.weight_latency /= total
            self.weight_cost /= total
            self.weight_liquidity /= total
            self.weight_reliability /= total
        
        if self.update_interval < 1:
            raise OrderRoutingError("update_interval doit être >= 1")
        
        if self.cache_ttl < 0.1:
            raise OrderRoutingError("cache_ttl doit être >= 0.1")


class OrderRouter:
    """
    Routeur d'ordres intelligent.
    """
    
    def __init__(self, config: Optional[RouterConfig] = None):
        """
        Initialise le routeur d'ordres.
        
        Args:
            config: Configuration du routeur.
        """
        self.config = config or RouterConfig()
        
        # Brokers
        self._brokers: Dict[str, BrokerInfo] = {}
        self._broker_factory = BrokerFactory()
        
        # Cache
        self._price_cache: Dict[str, Dict[str, float]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        # Statistiques
        self._routing_history: deque = deque(maxlen=10000)
        self._stats = {
            'total_routes': 0,
            'successful_routes': 0,
            'failed_routes': 0,
            'avg_score': 0.0
        }
        
        # État
        self._running = False
        self._lock = threading.Lock()
        self._update_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_route_selected': [],
            'on_route_failed': [],
            'on_broker_update': [],
            'on_broker_error': []
        }
        
        logger.info("OrderRouter initialisé")
        logger.info(f"Stratégie: {self.config.strategy.value}")
    
    # ============================================================
    # GESTION DES BROKERS
    # ============================================================
    
    def register_broker(
        self,
        name: str,
        broker: Broker,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Enregistre un broker.
        
        Args:
            name: Nom du broker.
            broker: Instance du broker.
            config: Configuration supplémentaire.
        """
        broker_info = BrokerInfo(
            name=name,
            broker=broker,
            status=BrokerStatus.ONLINE
        )
        
        # Mise à jour avec la configuration
        if config:
            if 'maker_fee' in config:
                broker_info.maker_fee = config['maker_fee']
            if 'taker_fee' in config:
                broker_info.taker_fee = config['taker_fee']
            if 'liquidity_score' in config:
                broker_info.liquidity_score = config['liquidity_score']
        
        self._brokers[name] = broker_info
        
        logger.info(f"Broker enregistré: {name}")
    
    def unregister_broker(self, name: str) -> bool:
        """
        Désenregistre un broker.
        
        Args:
            name: Nom du broker.
            
        Returns:
            True si désenregistré.
        """
        if name in self._brokers:
            del self._brokers[name]
            logger.info(f"Broker désenregistré: {name}")
            return True
        return False
    
    def get_broker(self, name: str) -> Optional[Broker]:
        """
        Récupère un broker par son nom.
        
        Args:
            name: Nom du broker.
            
        Returns:
            Instance du broker ou None.
        """
        if name in self._brokers:
            return self._brokers[name].broker
        return None
    
    def get_broker_info(self, name: str) -> Optional[BrokerInfo]:
        """
        Récupère les informations d'un broker.
        
        Args:
            name: Nom du broker.
            
        Returns:
            Informations du broker ou None.
        """
        return self._brokers.get(name)
    
    def get_all_brokers(self) -> List[BrokerInfo]:
        """
        Récupère tous les brokers.
        
        Returns:
            Liste des informations des brokers.
        """
        return list(self._brokers.values())
    
    # ============================================================
    # ROUTAGE
    # ============================================================
    
    async def route_order(
        self,
        order: OrderConfig,
        exclude_brokers: Optional[List[str]] = None
    ) -> RouteDecision:
        """
        Route un ordre vers le meilleur broker.
        
        Args:
            order: Ordre à router.
            exclude_brokers: Brokers à exclure.
            
        Returns:
            Décision de routage.
        """
        logger.info(f"Routage de l'ordre {order.id}")
        
        # Récupération des brokers disponibles
        available_brokers = self._get_available_brokers(exclude_brokers)
        
        if not available_brokers:
            raise OrderRoutingError("Aucun broker disponible")
        
        # Évaluation des brokers
        decisions = await self._evaluate_brokers(order, available_brokers)
        
        if not decisions:
            raise OrderRoutingError("Aucune décision de routage possible")
        
        # Sélection de la meilleure décision
        best_decision = self._select_best_decision(decisions)
        
        # Logging
        if self.config.log_routing:
            logger.info(f"Route sélectionnée: {best_decision.broker_name} "
                       f"(score={best_decision.score:.3f}, {best_decision.reason})")
        
        # Mise à jour des statistiques
        self._routing_history.append({
            'order_id': order.id,
            'broker': best_decision.broker_name,
            'score': best_decision.score,
            'timestamp': datetime.now()
        })
        self._stats['total_routes'] += 1
        
        # Notification
        self._notify_callbacks('on_route_selected', {
            'order_id': order.id,
            'decision': best_decision.__dict__
        })
        
        return best_decision
    
    async def execute_routed_order(
        self,
        order: OrderConfig,
        route: RouteDecision,
        timeout: Optional[float] = None
    ) -> OrderExecutionResult:
        """
        Exécute un ordre via le broker routé.
        
        Args:
            order: Ordre à exécuter.
            route: Décision de routage.
            timeout: Timeout d'exécution.
            
        Returns:
            Résultat d'exécution.
        """
        broker_info = self._brokers.get(route.broker_name)
        if not broker_info:
            raise OrderRoutingError(f"Broker {route.broker_name} non trouvé")
        
        try:
            # Mise à jour du broker
            broker_info.last_used = datetime.now()
            broker_info.total_orders += 1
            
            # Exécution via le broker
            start_time = time.time()
            result = await broker_info.broker.execute_order(order)
            execution_time = time.time() - start_time
            
            # Mise à jour des métriques
            broker_info.avg_execution_time = (
                broker_info.avg_execution_time * (broker_info.total_orders - 1) +
                execution_time
            ) / broker_info.total_orders
            
            if result.status == OrderExecutionStatus.FILLED:
                broker_info.success_rate = (
                    broker_info.success_rate * 0.9 + 0.1
                )
                self._stats['successful_routes'] += 1
            else:
                broker_info.error_count += 1
                self._stats['failed_routes'] += 1
            
            # Notification
            self._notify_callbacks('on_broker_update', broker_info.to_dict())
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur d'exécution via {route.broker_name}: {e}")
            
            # Fallback
            if self.config.fallback_enabled:
                logger.info(f"Fallback pour l'ordre {order.id}")
                return await self._fallback_execution(order, route.broker_name)
            
            raise OrderRoutingError(f"Erreur d'exécution: {e}")
    
    async def _fallback_execution(
        self,
        order: OrderConfig,
        failed_broker: str
    ) -> OrderExecutionResult:
        """
        Exécution de fallback.
        
        Args:
            order: Ordre à exécuter.
            failed_broker: Nom du broker qui a échoué.
            
        Returns:
            Résultat d'exécution.
        """
        # Exclure le broker qui a échoué
        exclude_brokers = [failed_broker]
        
        for attempt in range(self.config.max_retries):
            try:
                # Nouveau routage
                route = await self.route_order(order, exclude_brokers=exclude_brokers)
                result = await self.execute_routed_order(order, route)
                return result
            except Exception as e:
                logger.warning(f"Tentative de fallback {attempt + 1} échouée: {e}")
                if attempt < self.config.max_retries - 1:
                    exclude_brokers.append(route.broker_name)
                await asyncio.sleep(1)
        
        raise OrderRoutingError("Fallback échoué")
    
    # ============================================================
    # ÉVALUATION DES BROKERS
    # ============================================================
    
    async def _evaluate_brokers(
        self,
        order: OrderConfig,
        brokers: List[BrokerInfo]
    ) -> List[RouteDecision]:
        """
        Évalue les brokers pour un ordre.
        
        Args:
            order: Ordre à évaluer.
            brokers: Liste des brokers disponibles.
            
        Returns:
            Liste des décisions de routage.
        """
        decisions = []
        
        for broker_info in brokers:
            try:
                # Évaluation selon la stratégie
                if self.config.strategy == RoutingStrategy.BEST_PRICE:
                    score = await self._score_best_price(broker_info, order)
                elif self.config.strategy == RoutingStrategy.FASTEST:
                    score = await self._score_fastest(broker_info, order)
                elif self.config.strategy == RoutingStrategy.CHEAPEST:
                    score = await self._score_cheapest(broker_info, order)
                elif self.config.strategy == RoutingStrategy.MOST_LIQUID:
                    score = await self._score_most_liquid(broker_info, order)
                elif self.config.strategy == RoutingStrategy.ROUND_ROBIN:
                    score = await self._score_round_robin(broker_info, order)
                elif self.config.strategy == RoutingStrategy.WEIGHTED:
                    score = await self._score_weighted(broker_info, order)
                elif self.config.strategy in [RoutingStrategy.ADAPTIVE, RoutingStrategy.SMART]:
                    score = await self._score_smart(broker_info, order)
                else:  # FIXED
                    score = 1.0 if len(brokers) == 1 else 0.5
                
                # Création de la décision
                decision = RouteDecision(
                    broker_name=broker_info.name,
                    score=score,
                    reason=self._get_routing_reason(broker_info, order)
                )
                
                decisions.append(decision)
                
            except Exception as e:
                logger.error(f"Erreur d'évaluation pour {broker_info.name}: {e}")
                continue
        
        return sorted(decisions, key=lambda x: x.score, reverse=True)
    
    async def _score_best_price(
        self,
        broker_info: BrokerInfo,
        order: OrderConfig
    ) -> float:
        """
        Score basé sur le meilleur prix.
        
        Args:
            broker_info: Informations du broker.
            order: Ordre.
            
        Returns:
            Score.
        """
        # Récupération du prix
        price = await self._get_broker_price(broker_info, order.symbol)
        
        # Score inversement proportionnel au prix
        max_price = 1000.0  # Valeur par défaut
        return max(0, 1 - (price / max_price))
    
    async def _score_fastest(
        self,
        broker_info: BrokerInfo,
        order: OrderConfig
    ) -> float:
        """
        Score basé sur la latence.
        
        Args:
            broker_info: Informations du broker.
            order: Ordre.
            
        Returns:
            Score.
        """
        latency = broker_info.latency_ms
        
        if latency <= 10:
            return 1.0
        elif latency <= 50:
            return 0.8
        elif latency <= 100:
            return 0.6
        elif latency <= 200:
            return 0.4
        else:
            return 0.2
    
    async def _score_cheapest(
        self,
        broker_info: BrokerInfo,
        order: OrderConfig
    ) -> float:
        """
        Score basé sur les frais.
        
        Args:
            broker_info: Informations du broker.
            order: Ordre.
            
        Returns:
            Score.
        """
        # Utiliser le taker fee pour les market orders
        fee = broker_info.taker_fee
        
        # Score inversement proportionnel aux frais
        max_fee = 0.01  # 1%
        return max(0, 1 - (fee / max_fee))
    
    async def _score_most_liquid(
        self,
        broker_info: BrokerInfo,
        order: OrderConfig
    ) -> float:
        """
        Score basé sur la liquidité.
        
        Args:
            broker_info: Informations du broker.
            order: Ordre.
            
        Returns:
            Score.
        """
        return broker_info.liquidity_score
    
    async def _score_round_robin(
        self,
        broker_info: BrokerInfo,
        order: OrderConfig
    ) -> float:
        """
        Score en round-robin.
        
        Args:
            broker_info: Informations du broker.
            order: Ordre.
            
        Returns:
            Score.
        """
        # Score basé sur le nombre d'ordres traités
        return 1.0 / (broker_info.total_orders + 1)
    
    async def _score_weighted(
        self,
        broker_info: BrokerInfo,
        order: OrderConfig
    ) -> float:
        """
        Score pondéré.
        
        Args:
            broker_info: Informations du broker.
            order: Ordre.
            
        Returns:
            Score.
        """
        # Poids des critères
        return (
            (1 - broker_info.taker_fee) * 0.4 +
            (1 - broker_info.latency_ms / 1000) * 0.3 +
            broker_info.success_rate * 0.3
        )
    
    async def _score_smart(
        self,
        broker_info: BrokerInfo,
        order: OrderConfig
    ) -> float:
        """
        Score intelligent.
        
        Args:
            broker_info: Informations du broker.
            order: Ordre.
            
        Returns:
            Score.
        """
        # Composants du score
        price_score = await self._score_best_price(broker_info, order)
        latency_score = await self._score_fastest(broker_info, order)
        cost_score = await self._score_cheapest(broker_info, order)
        liquidity_score = await self._score_most_liquid(broker_info, order)
        reliability_score = broker_info.success_rate
        
        # Score pondéré
        return (
            self.config.weight_price * price_score +
            self.config.weight_latency * latency_score +
            self.config.weight_cost * cost_score +
            self.config.weight_liquidity * liquidity_score +
            self.config.weight_reliability * reliability_score
        )
    
    def _select_best_decision(
        self,
        decisions: List[RouteDecision]
    ) -> RouteDecision:
        """
        Sélectionne la meilleure décision.
        
        Args:
            decisions: Liste des décisions.
            
        Returns:
            Meilleure décision.
        """
        # Score maximum
        best = max(decisions, key=lambda x: x.score)
        
        # Si le score est très faible, utiliser le premier disponible
        if best.score < 0.1:
            return decisions[0]
        
        return best
    
    def _get_routing_reason(
        self,
        broker_info: BrokerInfo,
        order: OrderConfig
    ) -> str:
        """
        Génère une raison pour le routage.
        
        Args:
            broker_info: Informations du broker.
            order: Ordre.
            
        Returns:
            Raison du routage.
        """
        reasons = []
        
        if self.config.strategy == RoutingStrategy.BEST_PRICE:
            reasons.append("Meilleur prix")
        elif self.config.strategy == RoutingStrategy.FASTEST:
            reasons.append(f"Latence: {broker_info.latency_ms:.1f}ms")
        elif self.config.strategy == RoutingStrategy.CHEAPEST:
            reasons.append(f"Frais: {broker_info.taker_fee:.4%}")
        elif self.config.strategy == RoutingStrategy.MOST_LIQUID:
            reasons.append(f"Liquidité: {broker_info.liquidity_score:.3f}")
        elif self.config.strategy == RoutingStrategy.SMART:
            reasons.extend([
                f"Prix: {broker_info.latency_ms:.1f}ms",
                f"Frais: {broker_info.taker_fee:.4%}",
                f"Liquidité: {broker_info.liquidity_score:.3f}"
            ])
        
        return " | ".join(reasons) if reasons else "Routage standard"
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def _get_available_brokers(
        self,
        exclude_brokers: Optional[List[str]] = None
    ) -> List[BrokerInfo]:
        """
        Récupère les brokers disponibles.
        
        Args:
            exclude_brokers: Brokers à exclure.
            
        Returns:
            Liste des brokers disponibles.
        """
        exclude = set(exclude_brokers or [])
        available = []
        
        for name, info in self._brokers.items():
            if name in exclude:
                continue
            
            if info.status == BrokerStatus.ONLINE:
                available.append(info)
            elif info.status == BrokerStatus.DEGRADED:
                # Tolérer les brokers dégradés si nécessaire
                available.append(info)
        
        return available
    
    async def _get_broker_price(
        self,
        broker_info: BrokerInfo,
        symbol: str
    ) -> float:
        """
        Récupère le prix d'un broker.
        
        Args:
            broker_info: Informations du broker.
            symbol: Symbole.
            
        Returns:
            Prix.
        """
        # Vérification du cache
        cache_key = f"{broker_info.name}_{symbol}"
        if cache_key in self._price_cache:
            timestamp = self._cache_timestamps.get(cache_key)
            if timestamp and (datetime.now() - timestamp).seconds < self.config.cache_ttl:
                return self._price_cache[cache_key]
        
        try:
            # Récupération via le broker
            ticker = await broker_info.broker.get_ticker(symbol)
            price = ticker.get('last_price', 100.0)
            
            # Mise en cache
            self._price_cache[cache_key] = price
            self._cache_timestamps[cache_key] = datetime.now()
            
            return price
            
        except Exception as e:
            logger.warning(f"Erreur de prix pour {broker_info.name}: {e}")
            return 100.0  # Valeur par défaut
    
    async def update_broker_status(self) -> None:
        """
        Met à jour le statut des brokers.
        """
        logger.info("Mise à jour du statut des brokers")
        
        for name, info in self._brokers.items():
            try:
                # Vérification de la connexion
                is_connected = await info.broker.is_connected()
                
                if is_connected:
                    info.status = BrokerStatus.ONLINE
                else:
                    info.status = BrokerStatus.OFFLINE
                
                # Mise à jour de la latence
                start_time = time.time()
                await info.broker.ping()
                info.latency_ms = (time.time() - start_time) * 1000
                
            except Exception as e:
                logger.error(f"Erreur de mise à jour pour {name}: {e}")
                info.status = BrokerStatus.OFFLINE
                info.error_count += 1
        
        # Notification
        self._notify_callbacks('on_broker_update', {
            name: info.to_dict() for name, info in self._brokers.items()
        })
    
    async def _update_loop(self) -> None:
        """
        Boucle de mise à jour.
        """
        while self._running:
            try:
                await self.update_broker_status()
                await asyncio.sleep(self.config.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans la boucle de mise à jour: {e}")
                await asyncio.sleep(10)
    
    # ============================================================
    # GESTION DU CYCLE DE VIE
    # ============================================================
    
    async def start(self) -> None:
        """
        Démarre le routeur.
        """
        if self._running:
            logger.warning("Routeur déjà en cours d'exécution")
            return
        
        self._running = True
        
        logger.info("Démarrage du routeur")
        
        # Mise à jour initiale
        await self.update_broker_status()
        
        # Démarrage de la boucle de mise à jour
        self._update_task = asyncio.create_task(self._update_loop())
        
        logger.info("Routeur démarré")
    
    async def stop(self) -> None:
        """
        Arrête le routeur.
        """
        if not self._running:
            logger.warning("Routeur déjà arrêté")
            return
        
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            await asyncio.gather(self._update_task, return_exceptions=True)
        
        logger.info("Routeur arrêté")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques.
        
        Returns:
            Statistiques du routeur.
        """
        return {
            **self._stats,
            'brokers': {
                name: info.to_dict() for name, info in self._brokers.items()
            },
            'routing_history': list(self._routing_history)[-100:]
        }
    
    def get_broker_status(self) -> Dict[str, str]:
        """
        Retourne le statut des brokers.
        
        Returns:
            Statut des brokers.
        """
        return {
            name: info.status.value for name, info in self._brokers.items()
        }
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on_route_selected(self, callback: Callable) -> None:
        """Ajoute un callback pour la sélection de route."""
        self._callbacks['on_route_selected'].append(callback)
    
    def on_route_failed(self, callback: Callable) -> None:
        """Ajoute un callback pour l'échec de route."""
        self._callbacks['on_route_failed'].append(callback)
    
    def on_broker_update(self, callback: Callable) -> None:
        """Ajoute un callback pour les mises à jour des brokers."""
        self._callbacks['on_broker_update'].append(callback)
    
    def on_broker_error(self, callback: Callable) -> None:
        """Ajoute un callback pour les erreurs des brokers."""
        self._callbacks['on_broker_error'].append(callback)
    
    def _notify_callbacks(self, event: str, data: Any) -> None:
        """
        Notifie les callbacks.
        
        Args:
            event: Nom de l'événement.
            data: Données.
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Erreur dans le callback {event}: {e}")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_order_router(
    strategy: str = "smart",
    **kwargs
) -> OrderRouter:
    """
    Crée un routeur d'ordres.
    
    Args:
        strategy: Stratégie de routage.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du routeur.
    """
    strategy_map = {
        'best_price': RoutingStrategy.BEST_PRICE,
        'fastest': RoutingStrategy.FASTEST,
        'cheapest': RoutingStrategy.CHEAPEST,
        'most_liquid': RoutingStrategy.MOST_LIQUID,
        'fixed': RoutingStrategy.FIXED,
        'round_robin': RoutingStrategy.ROUND_ROBIN,
        'weighted': RoutingStrategy.WEIGHTED,
        'adaptive': RoutingStrategy.ADAPTIVE,
        'smart': RoutingStrategy.SMART
    }
    
    config = RouterConfig(
        strategy=strategy_map.get(strategy, RoutingStrategy.SMART),
        **kwargs
    )
    return OrderRouter(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'OrderRouter',
    'RouterConfig',
    'BrokerInfo',
    'BrokerStatus',
    'RouteDecision',
    'RoutingStrategy',
    'create_order_router'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

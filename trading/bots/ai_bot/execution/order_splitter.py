"""
NEXUS AI TRADING SYSTEM - Order Splitter for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/execution/order_splitter.py
Description: Splitter d'ordres intelligent pour le bot AI.
             Supporte le fractionnement des ordres en multiples lots,
             la gestion du slippage, l'optimisation de l'impact sur le marché,
             et les stratégies de split adaptatives.
"""

import asyncio
import logging
import math
import random
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

import numpy as np

from trading.bots.ai_bot.execution.order_executor import OrderConfig, OrderExecutionResult, OrderExecutionStatus
from shared.exceptions import OrderSplitError
from shared.helpers.number_helpers import round_decimal

# Configuration du logging
logger = logging.getLogger(__name__)


class SplitStrategy(Enum):
    """Stratégies de fractionnement."""
    EQUAL = "equal"                      # Parts égales
    EXPONENTIAL = "exponential"          # Taille exponentielle
    RANDOM = "random"                    # Taille aléatoire
    ADAPTIVE = "adaptive"                # Adaptatif
    VOLUME_BASED = "volume_based"        # Basé sur le volume
    TIME_BASED = "time_based"            # Basé sur le temps
    SMART = "smart"                      # Intelligent


@dataclass
class SplitConfig:
    """
    Configuration du splitter.
    """
    # Stratégie de split
    strategy: SplitStrategy = SplitStrategy.EQUAL
    
    # Paramètres de split
    min_parts: int = 2
    max_parts: int = 10
    min_part_size: float = 0.01
    max_part_size: float = 1000.0
    target_part_size: Optional[float] = None
    
    # Paramètres de temps
    min_interval: float = 0.1  # secondes
    max_interval: float = 60.0  # secondes
    default_interval: float = 1.0  # secondes
    
    # Paramètres de volume
    volume_window: int = 20
    volume_multiplier: float = 1.0
    
    # Paramètres adaptatifs
    adaptive_threshold: float = 0.001  # 0.1%
    adaptive_window: int = 10
    
    # Paramètres de performance
    use_async: bool = True
    parallel_execution: bool = False
    max_parallel_parts: int = 5
    
    # Paramètres de monitoring
    enable_monitoring: bool = True
    log_splitting: bool = True
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.min_parts < 1:
            raise OrderSplitError("min_parts doit être >= 1")
        
        if self.max_parts < self.min_parts:
            raise OrderSplitError("max_parts doit être >= min_parts")
        
        if self.min_part_size <= 0:
            raise OrderSplitError("min_part_size doit être > 0")
        
        if self.max_part_size < self.min_part_size:
            raise OrderSplitError("max_part_size doit être >= min_part_size")
        
        if self.target_part_size and self.target_part_size < self.min_part_size:
            raise OrderSplitError("target_part_size doit être >= min_part_size")


@dataclass
class SplitDecision:
    """
    Décision de fractionnement.
    """
    total_quantity: float
    part_sizes: List[float]
    part_intervals: List[float]
    strategy: SplitStrategy
    total_parts: int
    estimated_time: float
    estimated_impact: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'total_quantity': self.total_quantity,
            'part_sizes': self.part_sizes,
            'part_intervals': self.part_intervals,
            'strategy': self.strategy.value,
            'total_parts': self.total_parts,
            'estimated_time': self.estimated_time,
            'estimated_impact': self.estimated_impact
        }


@dataclass
class SplitResult:
    """
    Résultat du fractionnement.
    """
    order_id: str
    total_quantity: float
    executed_quantity: float
    part_results: List[OrderExecutionResult]
    avg_price: float
    total_cost: float
    execution_time: float
    slippage: float
    status: OrderExecutionStatus
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'order_id': self.order_id,
            'total_quantity': self.total_quantity,
            'executed_quantity': self.executed_quantity,
            'part_results': [r.to_dict() for r in self.part_results],
            'avg_price': self.avg_price,
            'total_cost': self.total_cost,
            'execution_time': self.execution_time,
            'slippage': self.slippage,
            'status': self.status.value,
            'errors': self.errors
        }


class OrderSplitter:
    """
    Splitter d'ordres intelligent.
    """
    
    def __init__(self, config: Optional[SplitConfig] = None):
        """
        Initialise le splitter d'ordres.
        
        Args:
            config: Configuration du splitter.
        """
        self.config = config or SplitConfig()
        
        # Historique
        self._split_history: deque = deque(maxlen=1000)
        self._volume_history: deque = deque(maxlen=self.config.volume_window)
        self._execution_times: deque = deque(maxlen=100)
        
        # Statistiques
        self._stats = {
            'total_splits': 0,
            'total_parts': 0,
            'avg_parts': 0.0,
            'avg_execution_time': 0.0,
            'success_rate': 1.0
        }
        
        # État
        self._running = False
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'on_split_start': [],
            'on_part_complete': [],
            'on_split_complete': [],
            'on_split_error': []
        }
        
        logger.info("OrderSplitter initialisé")
        logger.info(f"Stratégie: {self.config.strategy.value}")
        logger.info(f"Parts: {self.config.min_parts} - {self.config.max_parts}")
    
    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================
    
    async def split_order(
        self,
        order: OrderConfig,
        executor: Any,  # OrderExecutor
        strategy: Optional[SplitStrategy] = None
    ) -> SplitResult:
        """
        Fractionne et exécute un ordre.
        
        Args:
            order: Ordre à fractionner.
            executor: Exécuteur d'ordres.
            strategy: Stratégie de split (optionnelle).
            
        Returns:
            Résultat du fractionnement.
        """
        logger.info(f"Fractionnement de l'ordre {order.id} (quantité: {order.quantity})")
        
        # Sélection de la stratégie
        split_strategy = strategy or self.config.strategy
        
        # Décision de fractionnement
        decision = self._make_split_decision(order.quantity, split_strategy)
        
        # Notification
        self._notify_callbacks('on_split_start', {
            'order_id': order.id,
            'decision': decision.to_dict()
        })
        
        # Exécution des parts
        part_results = []
        errors = []
        total_executed = 0
        total_cost = 0.0
        
        start_time = datetime.now()
        
        for i, (size, interval) in enumerate(zip(decision.part_sizes, decision.part_intervals)):
            try:
                # Création de l'ordre partiel
                part_order = OrderConfig(
                    id=f"{order.id}_part_{i}",
                    symbol=order.symbol,
                    side=order.side,
                    quantity=size,
                    price=order.price,
                    order_type=order.order_type,
                    time_in_force=order.time_in_force,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                    max_slippage=order.max_slippage,
                    execution_strategy=order.execution_strategy,
                    metadata={'parent_order': order.id, 'part_index': i}
                )
                
                # Exécution de la part
                result = await executor.execute_order(part_order, wait_for_fill=True)
                part_results.append(result)
                
                total_executed += result.executed_quantity
                total_cost += result.total_cost
                
                # Notification
                self._notify_callbacks('on_part_complete', {
                    'order_id': order.id,
                    'part_index': i,
                    'result': result.to_dict()
                })
                
                # Attente avant la prochaine part
                if i < len(decision.part_sizes) - 1:
                    await asyncio.sleep(interval)
                
            except Exception as e:
                error_msg = f"Part {i} échouée: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._notify_callbacks('on_split_error', {
                    'order_id': order.id,
                    'part_index': i,
                    'error': str(e)
                })
                
                # Continuer ou arrêter selon la stratégie
                if split_strategy in [SplitStrategy.SMART, SplitStrategy.ADAPTIVE]:
                    logger.warning(f"Arrêt du split après échec part {i}")
                    break
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Résultat final
        result = SplitResult(
            order_id=order.id,
            total_quantity=order.quantity,
            executed_quantity=total_executed,
            part_results=part_results,
            avg_price=total_cost / total_executed if total_executed > 0 else 0,
            total_cost=total_cost,
            execution_time=execution_time,
            slippage=self._calculate_slippage(order, part_results),
            status=OrderExecutionStatus.FILLED if total_executed >= order.quantity * 0.99 else OrderExecutionStatus.PARTIALLY_FILLED,
            errors=errors
        )
        
        # Mise à jour des statistiques
        self._update_stats(result)
        
        # Notification
        self._notify_callbacks('on_split_complete', result.to_dict())
        
        logger.info(f"Split terminé: {total_executed}/{order.quantity} exécutés, {len(errors)} erreurs")
        
        return result
    
    # ============================================================
    # DÉCISION DE FRACTIONNEMENT
    # ============================================================
    
    def _make_split_decision(
        self,
        quantity: float,
        strategy: SplitStrategy
    ) -> SplitDecision:
        """
        Prend une décision de fractionnement.
        
        Args:
            quantity: Quantité totale.
            strategy: Stratégie de split.
            
        Returns:
            Décision de fractionnement.
        """
        # Détermination du nombre de parts
        n_parts = self._determine_parts(quantity, strategy)
        
        # Taille des parts
        part_sizes = self._calculate_part_sizes(quantity, n_parts, strategy)
        
        # Intervalles entre les parts
        part_intervals = self._calculate_intervals(part_sizes, strategy)
        
        # Estimation du temps
        estimated_time = sum(part_intervals)
        
        # Estimation de l'impact
        estimated_impact = self._estimate_impact(part_sizes, strategy)
        
        return SplitDecision(
            total_quantity=quantity,
            part_sizes=part_sizes,
            part_intervals=part_intervals,
            strategy=strategy,
            total_parts=n_parts,
            estimated_time=estimated_time,
            estimated_impact=estimated_impact
        )
    
    def _determine_parts(
        self,
        quantity: float,
        strategy: SplitStrategy
    ) -> int:
        """
        Détermine le nombre de parts.
        
        Args:
            quantity: Quantité totale.
            strategy: Stratégie de split.
            
        Returns:
            Nombre de parts.
        """
        # Taille cible
        if self.config.target_part_size:
            n = math.ceil(quantity / self.config.target_part_size)
            return min(max(n, self.config.min_parts), self.config.max_parts)
        
        # Stratégies
        if strategy == SplitStrategy.EQUAL:
            return self._determine_parts_equal(quantity)
        elif strategy == SplitStrategy.EXPONENTIAL:
            return self._determine_parts_exponential(quantity)
        elif strategy == SplitStrategy.ADAPTIVE:
            return self._determine_parts_adaptive(quantity)
        elif strategy == SplitStrategy.VOLUME_BASED:
            return self._determine_parts_volume(quantity)
        elif strategy == SplitStrategy.TIME_BASED:
            return self._determine_parts_time(quantity)
        elif strategy == SplitStrategy.SMART:
            return self._determine_parts_smart(quantity)
        else:  # RANDOM
            return self._determine_parts_random(quantity)
    
    def _determine_parts_equal(self, quantity: float) -> int:
        """Détermine les parts égales."""
        # Taille de part basée sur la quantité
        if quantity <= 10:
            return min(3, self.config.max_parts)
        elif quantity <= 100:
            return min(5, self.config.max_parts)
        elif quantity <= 1000:
            return min(8, self.config.max_parts)
        else:
            return self.config.max_parts
    
    def _determine_parts_exponential(self, quantity: float) -> int:
        """Détermine les parts exponentielles."""
        # Plus de parts pour les grandes quantités
        n = int(math.log(quantity + 1) * 2)
        return min(max(n, self.config.min_parts), self.config.max_parts)
    
    def _determine_parts_adaptive(self, quantity: float) -> int:
        """Détermine les parts adaptatives."""
        # Basé sur la volatilité du marché
        volatility = self._get_market_volatility()
        
        if volatility > 0.02:  # Volatilité élevée
            return self.config.max_parts
        elif volatility > 0.01:  # Volatilité moyenne
            return (self.config.min_parts + self.config.max_parts) // 2
        else:  # Volatilité faible
            return self.config.min_parts
    
    def _determine_parts_volume(self, quantity: float) -> int:
        """Détermine les parts basées sur le volume."""
        avg_volume = self._get_average_volume()
        
        if avg_volume > quantity * 10:  # Volume élevé
            return self.config.min_parts
        elif avg_volume > quantity * 2:  # Volume moyen
            return (self.config.min_parts + self.config.max_parts) // 2
        else:  # Volume faible
            return self.config.max_parts
    
    def _determine_parts_time(self, quantity: float) -> int:
        """Détermine les parts basées sur le temps."""
        # Basé sur la durée estimée
        estimated_duration = quantity / 10  # 10 unités par seconde
        max_duration = 60  # 1 minute max
        
        parts = math.ceil(estimated_duration / 10)  # Une part toutes les 10 secondes
        return min(max(parts, self.config.min_parts), self.config.max_parts)
    
    def _determine_parts_smart(self, quantity: float) -> int:
        """Détermine les parts intelligentes."""
        # Combinaison de facteurs
        scores = []
        
        # Facteur quantité
        q_score = min(1, quantity / 1000)
        scores.append(q_score * 0.3)
        
        # Facteur volatilité
        vol = self._get_market_volatility()
        v_score = min(1, vol / 0.05)
        scores.append(v_score * 0.3)
        
        # Facteur volume
        avg_vol = self._get_average_volume()
        vol_ratio = avg_vol / quantity if quantity > 0 else 1
        vol_score = min(1, 1 / vol_ratio)
        scores.append(vol_score * 0.2)
        
        # Facteur spread
        spread = self._get_market_spread()
        s_score = min(1, spread / 0.01)
        scores.append(s_score * 0.2)
        
        # Score total
        total_score = sum(scores)
        
        # Nombre de parts
        n_parts = int(self.config.min_parts + (self.config.max_parts - self.config.min_parts) * total_score)
        return min(max(n_parts, self.config.min_parts), self.config.max_parts)
    
    def _determine_parts_random(self, quantity: float) -> int:
        """Détermine les parts aléatoires."""
        return random.randint(self.config.min_parts, self.config.max_parts)
    
    def _calculate_part_sizes(
        self,
        quantity: float,
        n_parts: int,
        strategy: SplitStrategy
    ) -> List[float]:
        """
        Calcule la taille des parts.
        
        Args:
            quantity: Quantité totale.
            n_parts: Nombre de parts.
            strategy: Stratégie de split.
            
        Returns:
            Liste des tailles de parts.
        """
        if strategy == SplitStrategy.EQUAL:
            return [quantity / n_parts] * n_parts
        
        elif strategy == SplitStrategy.EXPONENTIAL:
            # Taille exponentielle croissante
            sizes = []
            remaining = quantity
            
            for i in range(n_parts - 1):
                ratio = 1.5 ** i
                size = quantity * ratio / sum(1.5 ** j for j in range(n_parts))
                size = min(size, remaining - self.config.min_part_size * (n_parts - i - 1))
                sizes.append(size)
                remaining -= size
            
            sizes.append(remaining)
            return [round_decimal(s) for s in sizes]
        
        elif strategy == SplitStrategy.RANDOM:
            # Taille aléatoire
            weights = np.random.dirichlet(np.ones(n_parts))
            sizes = [quantity * w for w in weights]
            return [round_decimal(s) for s in sizes]
        
        elif strategy == SplitStrategy.ADAPTIVE:
            # Taille adaptative basée sur les conditions de marché
            volatility = self._get_market_volatility()
            
            if volatility > 0.02:
                # Volatilité élevée -> petites parts
                return self._calculate_part_sizes(quantity, n_parts, SplitStrategy.EQUAL)
            else:
                # Volatilité faible -> grandes parts
                return self._calculate_part_sizes(quantity, max(2, n_parts // 2), SplitStrategy.EQUAL)
        
        elif strategy == SplitStrategy.VOLUME_BASED:
            # Taille basée sur le volume
            avg_volume = self._get_average_volume()
            target_size = avg_volume * self.config.volume_multiplier / n_parts
            target_size = min(max(target_size, self.config.min_part_size), self.config.max_part_size)
            
            sizes = []
            remaining = quantity
            
            for i in range(n_parts - 1):
                size = min(target_size, remaining - self.config.min_part_size * (n_parts - i - 1))
                sizes.append(round_decimal(size))
                remaining -= size
            
            sizes.append(round_decimal(remaining))
            return sizes
        
        elif strategy == SplitStrategy.SMART:
            # Taille intelligente
            # Mélange d'égal et d'exponentiel
            base_sizes = self._calculate_part_sizes(quantity, n_parts, SplitStrategy.EQUAL)
            
            # Ajout de variation
            for i in range(len(base_sizes)):
                variation = random.uniform(0.8, 1.2)
                base_sizes[i] *= variation
            
            # Normalisation
            total = sum(base_sizes)
            base_sizes = [s * quantity / total for s in base_sizes]
            
            return [round_decimal(s) for s in base_sizes]
        
        else:  # TIME_BASED
            # Taille égale
            return [quantity / n_parts] * n_parts
    
    def _calculate_intervals(
        self,
        part_sizes: List[float],
        strategy: SplitStrategy
    ) -> List[float]:
        """
        Calcule les intervalles entre les parts.
        
        Args:
            part_sizes: Tailles des parts.
            strategy: Stratégie de split.
            
        Returns:
            Liste des intervalles.
        """
        n_parts = len(part_sizes)
        
        if n_parts <= 1:
            return [0.0]
        
        if strategy == SplitStrategy.EQUAL:
            return [self.config.default_interval] * (n_parts - 1)
        
        elif strategy == SplitStrategy.EXPONENTIAL:
            # Intervalles exponentiels
            intervals = []
            for i in range(n_parts - 1):
                interval = self.config.default_interval * (1.5 ** i)
                intervals.append(min(interval, self.config.max_interval))
            return intervals
        
        elif strategy == SplitStrategy.ADAPTIVE:
            # Intervalles adaptatifs
            volatility = self._get_market_volatility()
            
            if volatility > 0.02:
                # Volatilité élevée -> intervalles courts
                return [self.config.min_interval] * (n_parts - 1)
            elif volatility > 0.01:
                # Volatilité moyenne
                return [self.config.default_interval] * (n_parts - 1)
            else:
                # Volatilité faible -> intervalles longs
                return [self.config.max_interval] * (n_parts - 1)
        
        elif strategy == SplitStrategy.VOLUME_BASED:
            # Intervalles basés sur le volume
            avg_volume = self._get_average_volume()
            interval_base = self.config.default_interval * (1000 / (avg_volume + 1))
            interval_base = min(max(interval_base, self.config.min_interval), self.config.max_interval)
            return [interval_base] * (n_parts - 1)
        
        elif strategy == SplitStrategy.SMART:
            # Intervalles intelligents
            intervals = []
            for i in range(n_parts - 1):
                # Intervalle basé sur la taille de la part
                size_ratio = part_sizes[i] / sum(part_sizes)
                interval = self.config.default_interval * (1 + size_ratio)
                interval = min(max(interval, self.config.min_interval), self.config.max_interval)
                intervals.append(interval)
            return intervals
        
        else:  # RANDOM, TIME_BASED
            # Intervalles aléatoires ou basés sur le temps
            return [random.uniform(self.config.min_interval, self.config.max_interval) for _ in range(n_parts - 1)]
    
    def _estimate_impact(
        self,
        part_sizes: List[float],
        strategy: SplitStrategy
    ) -> float:
        """
        Estime l'impact sur le marché.
        
        Args:
            part_sizes: Tailles des parts.
            strategy: Stratégie de split.
            
        Returns:
            Estimation de l'impact.
        """
        total_size = sum(part_sizes)
        avg_volume = self._get_average_volume()
        
        if avg_volume == 0:
            return 1.0
        
        # Impact proportionnel à la taille relative
        impact = total_size / (avg_volume * 10)
        
        # Réduction par le split
        split_factor = 1 / len(part_sizes)
        impact *= split_factor
        
        return min(impact, 0.1)  # Max 10% d'impact
    
    def _calculate_slippage(
        self,
        order: OrderConfig,
        part_results: List[OrderExecutionResult]
    ) -> float:
        """
        Calcule le slippage total.
        
        Args:
            order: Ordre original.
            part_results: Résultats des parts.
            
        Returns:
            Slippage total.
        """
        if not part_results:
            return 0.0
        
        total_slippage = 0.0
        total_quantity = 0.0
        
        for result in part_results:
            total_slippage += abs(result.slippage) * result.executed_quantity
            total_quantity += result.executed_quantity
        
        if total_quantity == 0:
            return 0.0
        
        return total_slippage / total_quantity
    
    # ============================================================
    # MÉTHODES DE MARCHÉ
    # ============================================================
    
    def _get_market_volatility(self) -> float:
        """
        Récupère la volatilité du marché.
        
        Returns:
            Volatilité estimée.
        """
        # Simuler la volatilité
        return random.uniform(0.005, 0.03)
    
    def _get_average_volume(self) -> float:
        """
        Récupère le volume moyen.
        
        Returns:
            Volume moyen.
        """
        # Simuler le volume
        return random.uniform(100, 10000)
    
    def _get_market_spread(self) -> float:
        """
        Récupère le spread du marché.
        
        Returns:
            Spread estimé.
        """
        # Simuler le spread
        return random.uniform(0.0001, 0.001)
    
    # ============================================================
    # STATISTIQUES
    # ============================================================
    
    def _update_stats(self, result: SplitResult) -> None:
        """
        Met à jour les statistiques.
        
        Args:
            result: Résultat du split.
        """
        self._split_history.append(result)
        self._stats['total_splits'] += 1
        self._stats['total_parts'] += len(result.part_results)
        
        # Moyenne
        self._stats['avg_parts'] = (
            self._stats['avg_parts'] * (self._stats['total_splits'] - 1) +
            len(result.part_results)
        ) / self._stats['total_splits']
        
        self._stats['avg_execution_time'] = (
            self._stats['avg_execution_time'] * (self._stats['total_splits'] - 1) +
            result.execution_time
        ) / self._stats['total_splits']
        
        # Taux de succès
        if result.executed_quantity >= result.total_quantity * 0.99:
            self._stats['success_rate'] = (
                self._stats['success_rate'] * (self._stats['total_splits'] - 1) + 1
            ) / self._stats['total_splits']
        else:
            self._stats['success_rate'] = (
                self._stats['success_rate'] * (self._stats['total_splits'] - 1) + 0
            ) / self._stats['total_splits']
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques.
        
        Returns:
            Statistiques du splitter.
        """
        return {
            **self._stats,
            'history_length': len(self._split_history),
            'config': {
                'strategy': self.config.strategy.value,
                'min_parts': self.config.min_parts,
                'max_parts': self.config.max_parts
            }
        }
    
    def reset(self) -> None:
        """
        Réinitialise le splitter.
        """
        self._split_history.clear()
        self._volume_history.clear()
        self._execution_times.clear()
        self._stats = {
            'total_splits': 0,
            'total_parts': 0,
            'avg_parts': 0.0,
            'avg_execution_time': 0.0,
            'success_rate': 1.0
        }
        
        logger.info("OrderSplitter réinitialisé")
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on_split_start(self, callback: Callable) -> None:
        """Ajoute un callback pour le début du split."""
        self._callbacks['on_split_start'].append(callback)
    
    def on_part_complete(self, callback: Callable) -> None:
        """Ajoute un callback pour la fin d'une part."""
        self._callbacks['on_part_complete'].append(callback)
    
    def on_split_complete(self, callback: Callable) -> None:
        """Ajoute un callback pour la fin du split."""
        self._callbacks['on_split_complete'].append(callback)
    
    def on_split_error(self, callback: Callable) -> None:
        """Ajoute un callback pour les erreurs de split."""
        self._callbacks['on_split_error'].append(callback)
    
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

def create_order_splitter(
    strategy: str = "equal",
    min_parts: int = 2,
    max_parts: int = 10,
    **kwargs
) -> OrderSplitter:
    """
    Crée un splitter d'ordres.
    
    Args:
        strategy: Stratégie de split.
        min_parts: Nombre minimum de parts.
        max_parts: Nombre maximum de parts.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du splitter.
    """
    strategy_map = {
        'equal': SplitStrategy.EQUAL,
        'exponential': SplitStrategy.EXPONENTIAL,
        'random': SplitStrategy.RANDOM,
        'adaptive': SplitStrategy.ADAPTIVE,
        'volume_based': SplitStrategy.VOLUME_BASED,
        'time_based': SplitStrategy.TIME_BASED,
        'smart': SplitStrategy.SMART
    }
    
    config = SplitConfig(
        strategy=strategy_map.get(strategy, SplitStrategy.EQUAL),
        min_parts=min_parts,
        max_parts=max_parts,
        **kwargs
    )
    return OrderSplitter(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'OrderSplitter',
    'SplitConfig',
    'SplitDecision',
    'SplitResult',
    'SplitStrategy',
    'create_order_splitter'
]

# ============================================================
# FIN DU FICHIER
# ============================================================

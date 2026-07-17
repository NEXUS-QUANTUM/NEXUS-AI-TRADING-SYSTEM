"""
NEXUS AI TRADING SYSTEM - Market Simulator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/backtesting/simulator.py
Description: Simulateur de marché pour le backtesting et le paper trading.
             Supporte la simulation d'ordres, le slippage, les commissions,
             la liquidité et l'impact sur le marché.
"""

import logging
import time
import random
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
import asyncio

import numpy as np
import pandas as pd

from trading.backtesting.data_provider import DataProvider
from trading.portfolio.position_manager import PositionManager
from trading.risk_management.position_sizer import PositionSizer
from trading.brokers.base import Order, OrderSide, OrderType, OrderStatus
from shared.helpers.number_helpers import round_decimal
from shared.helpers.trading_helpers import (
    calculate_slippage, calculate_commission,
    validate_order, normalize_symbol
)
from shared.constants.trading_constants import (
    DEFAULT_SLIPPAGE, DEFAULT_COMMISSION,
    MAX_POSITION_SIZE, MIN_POSITION_SIZE
)
from shared.exceptions import (
    SimulationError, InsufficientLiquidityError,
    OrderExecutionError, InvalidOrderError
)

# Configuration du logging
logger = logging.getLogger(__name__)


@dataclass
class SimulationConfig:
    """
    Configuration du simulateur de marché.
    """
    # Paramètres de base
    symbol: str
    initial_price: float
    initial_capital: float = 100000.0
    
    # Paramètres de simulation
    time_step: str = '1h'  # Timeframe de simulation
    max_steps: int = 100000
    warmup_steps: int = 100
    
    # Paramètres d'exécution
    slippage_pct: float = DEFAULT_SLIPPAGE
    commission_pct: float = DEFAULT_COMMISSION
    commission_fixed: float = 0.0
    
    # Paramètres de liquidité
    order_book_depth: int = 10  # Profondeur du carnet d'ordres
    liquidity_multiplier: float = 1.0  # Multiplicateur de liquidité
    market_impact_pct: float = 0.001  # Impact sur le marché par unité
    
    # Paramètres de volatilité
    volatility_model: str = 'gaussian'  # 'gaussian', 'garch', 'stochastic'
    volatility_params: Dict[str, Any] = field(default_factory=dict)
    
    # Paramètres de données
    use_historical_data: bool = True
    data_provider: Optional[DataProvider] = None
    
    # Paramètres avancés
    allow_short_selling: bool = True
    allow_margin: bool = False
    margin_rate: float = 0.5  # 50% margin
    min_balance: float = 100.0
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.initial_price <= 0:
            raise SimulationError("initial_price doit être > 0")
        
        if self.initial_capital <= 0:
            raise SimulationError("initial_capital doit être > 0")
        
        if self.slippage_pct < 0:
            raise SimulationError("slippage_pct doit être >= 0")
        
        if self.commission_pct < 0:
            raise SimulationError("commission_pct doit être >= 0")


@dataclass
class OrderBookEntry:
    """
    Entrée du carnet d'ordres.
    """
    price: float
    volume: float
    side: str  # 'bid' ou 'ask'
    order_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'price': self.price,
            'volume': self.volume,
            'side': self.side,
            'order_id': self.order_id
        }


@dataclass
class SimulationTick:
    """
    Un tick de simulation.
    """
    timestamp: datetime
    price: float
    volume: float
    bid: float
    ask: float
    spread: float
    open: float
    high: float
    low: float
    close: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'volume': self.volume,
            'bid': self.bid,
            'ask': self.ask,
            'spread': self.spread,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close
        }


class MarketSimulator:
    """
    Simulateur de marché avancé.
    """
    
    def __init__(self, config: SimulationConfig):
        """
        Initialise le simulateur de marché.
        
        Args:
            config: Configuration de la simulation.
        """
        self.config = config
        self.current_step = 0
        self.current_time = datetime.now()
        
        # État du marché
        self.current_price = config.initial_price
        self.historical_prices: List[float] = [config.initial_price]
        self.returns: List[float] = []
        
        # Carnet d'ordres
        self.bids: List[OrderBookEntry] = []
        self.asks: List[OrderBookEntry] = []
        self._update_order_book(config.initial_price)
        
        # Données historiques
        self.historical_data: Optional[pd.DataFrame] = None
        self.data_index = 0
        
        # Positions simulées
        self.positions: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []
        
        # Métriques de performance
        self.total_volume = 0
        self.total_trades = 0
        self.balance = config.initial_capital
        self.holdings = 0
        self.equity_curve: List[float] = [config.initial_capital]
        
        # Configuration du logger
        logger.info("MarketSimulator initialisé")
        logger.info(f"Symbole: {config.symbol}")
        logger.info(f"Prix initial: ${config.initial_price:.4f}")
        logger.info(f"Capital initial: ${config.initial_capital:,.2f}")
        
        # Chargement des données historiques
        if config.use_historical_data:
            self._load_historical_data()
    
    # ============================================================
    # GESTION DU MARCHÉ
    # ============================================================
    
    def _load_historical_data(self) -> None:
        """
        Charge les données historiques pour la simulation.
        """
        try:
            provider = self.config.data_provider or DataProvider()
            
            # Calcul des dates
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * 2)  # 2 ans de données
            
            data = provider.get_historical_data(
                symbol=self.config.symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=self.config.time_step
            )
            
            if not data.empty:
                self.historical_data = data
                logger.info(f"Données historiques chargées: {len(data)} bars")
            else:
                logger.warning("Aucune donnée historique disponible, utilisation de données synthétiques")
                self.historical_data = None
                
        except Exception as e:
            logger.warning(f"Erreur de chargement des données historiques: {e}")
            self.historical_data = None
    
    def _update_order_book(self, price: float) -> None:
        """
        Met à jour le carnet d'ordres.
        
        Args:
            price: Prix actuel.
        """
        depth = self.config.order_book_depth
        liquidity = self.config.liquidity_multiplier
        
        # Bids (en dessous du prix)
        self.bids = []
        for i in range(1, depth + 1):
            spread_factor = 1 - (i * 0.001 / depth)
            bid_price = price * spread_factor
            volume = random.uniform(10, 100) * liquidity * (depth - i + 1) / depth
            self.bids.append(OrderBookEntry(bid_price, volume, 'bid'))
        
        # Asks (au-dessus du prix)
        self.asks = []
        for i in range(1, depth + 1):
            spread_factor = 1 + (i * 0.001 / depth)
            ask_price = price * spread_factor
            volume = random.uniform(10, 100) * liquidity * (depth - i + 1) / depth
            self.asks.append(OrderBookEntry(ask_price, volume, 'ask'))
        
        # Trier par prix
        self.bids.sort(key=lambda x: x.price, reverse=True)
        self.asks.sort(key=lambda x: x.price)
    
    def _generate_price(self, tick: float) -> float:
        """
        Génère le prochain prix.
        
        Args:
            tick: Tick de simulation.
            
        Returns:
            Nouveau prix.
        """
        # Si des données historiques sont disponibles
        if self.historical_data is not None and self.data_index < len(self.historical_data):
            row = self.historical_data.iloc[self.data_index]
            self.data_index += 1
            
            # Utiliser le prix réel
            if 'close' in row:
                return row['close']
            elif 'price' in row:
                return row['price']
        
        # Sinon, génération synthétique
        if self.config.volatility_model == 'gaussian':
            # Mouvement brownien
            mu = 0.0001  # Drift journalier
            sigma = 0.01  # Volatilité journalière
            dt = 1 / 252  # Pas de temps
            return self.current_price * np.exp(
                (mu - 0.5 * sigma ** 2) * dt +
                sigma * np.sqrt(dt) * np.random.normal(0, 1)
            )
            
        elif self.config.volatility_model == 'garch':
            # GARCH(1,1)
            alpha = self.config.volatility_params.get('alpha', 0.1)
            beta = self.config.volatility_params.get('beta', 0.85)
            omega = self.config.volatility_params.get('omega', 0.01)
            
            # Calcul de la volatilité conditionnelle
            if len(self.returns) > 1:
                last_return = self.returns[-1]
                last_vol = self.config.volatility_params.get('last_vol', 0.01)
                vol_sq = omega + alpha * last_return**2 + beta * last_vol**2
                vol = np.sqrt(vol_sq)
                self.config.volatility_params['last_vol'] = vol
            else:
                vol = 0.01
            
            # Génération du prix
            dt = 1 / 252
            return self.current_price * np.exp(
                (0.0001 - 0.5 * vol**2) * dt +
                vol * np.sqrt(dt) * np.random.normal(0, 1)
            )
            
        elif self.config.volatility_model == 'stochastic':
            # Modèle de volatilité stochastique (Heston-like)
            kappa = 2.0  # Vitesse de retour
            theta = 0.01  # Volatilité moyenne
            xi = 0.5  # Volatilité de la volatilité
            
            # Mise à jour de la volatilité
            if hasattr(self, '_vol'):
                vol_sq = self._vol**2 + kappa * (theta - self._vol**2) * 0.004 + xi * self._vol * np.sqrt(0.004) * np.random.normal(0, 1)
                self._vol = np.sqrt(max(vol_sq, 0.0001))
            else:
                self._vol = np.sqrt(theta)
            
            # Génération du prix
            dt = 1 / 252
            return self.current_price * np.exp(
                (0.0001 - 0.5 * self._vol**2) * dt +
                self._vol * np.sqrt(dt) * np.random.normal(0, 1)
            )
        
        else:
            # Volatilité constante
            sigma = self.config.volatility_params.get('sigma', 0.01)
            dt = 1 / 252
            return self.current_price * np.exp(
                (0.0001 - 0.5 * sigma**2) * dt +
                sigma * np.sqrt(dt) * np.random.normal(0, 1)
            )
    
    def _generate_volume(self) -> float:
        """
        Génère un volume de trading.
        
        Returns:
            Volume simulé.
        """
        # Volume basé sur une distribution log-normale
        base_volume = 1000 * self.config.liquidity_multiplier
        volume = base_volume * np.exp(
            np.random.normal(0, 0.5)
        )
        return max(10, volume)
    
    # ============================================================
    # GESTION DES ORDRES
    # ============================================================
    
    def submit_order(
        self,
        side: str,
        quantity: float,
        order_type: str = 'market',
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Soumet un ordre de trading.
        
        Args:
            side: 'buy' ou 'sell'
            quantity: Quantité à trader
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            price: Prix (pour limit/stop orders)
            stop_price: Prix de déclenchement (stop orders)
            limit_price: Prix limite (stop-limit orders)
            
        Returns:
            Dictionnaire contenant les détails de l'ordre.
            
        Raises:
            InvalidOrderError: Si l'ordre est invalide.
            InsufficientLiquidityError: Si la liquidité est insuffisante.
        """
        # Validation
        quantity = abs(quantity)
        if quantity <= 0:
            raise InvalidOrderError("La quantité doit être positive")
        
        if side not in ['buy', 'sell']:
            raise InvalidOrderError(f"Side invalide: {side}")
        
        # Vérification de la liquidité
        if not self._check_liquidity(side, quantity, price):
            raise InsufficientLiquidityError(
                f"Liquidité insuffisante pour {side} {quantity}"
            )
        
        # Exécution de l'ordre
        order_id = f"SIM_{int(time.time())}_{self.total_trades}"
        
        if order_type == 'market':
            return self._execute_market_order(side, quantity, order_id)
        
        elif order_type == 'limit':
            if price is None:
                raise InvalidOrderError("Prix requis pour les ordres limit")
            return self._execute_limit_order(side, quantity, price, order_id)
        
        elif order_type == 'stop':
            if stop_price is None:
                raise InvalidOrderError("Stop price requis pour les ordres stop")
            return self._execute_stop_order(side, quantity, stop_price, order_id)
        
        elif order_type == 'stop_limit':
            if stop_price is None or limit_price is None:
                raise InvalidOrderError("Stop et limit price requis pour les stop-limit")
            return self._execute_stop_limit_order(
                side, quantity, stop_price, limit_price, order_id
            )
        
        else:
            raise InvalidOrderError(f"Type d'ordre invalide: {order_type}")
    
    def _execute_market_order(
        self,
        side: str,
        quantity: float,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Exécute un ordre au marché.
        
        Args:
            side: 'buy' ou 'sell'
            quantity: Quantité
            order_id: ID de l'ordre
            
        Returns:
            Détails de l'ordre exécuté.
        """
        # Prix d'exécution
        if side == 'buy':
            execution_price = self._get_best_ask() or self.current_price
        else:
            execution_price = self._get_best_bid() or self.current_price
        
        # Slippage
        execution_price = calculate_slippage(
            price=execution_price,
            side=side,
            volume=quantity,
            slippage_pct=self.config.slippage_pct
        )
        
        # Commission
        commission = calculate_commission(
            price=execution_price,
            volume=quantity,
            commission_pct=self.config.commission_pct,
            commission_fixed=self.config.commission_fixed
        )
        
        # Impact sur le marché
        impact = self._calculate_market_impact(side, quantity, execution_price)
        execution_price += impact if side == 'buy' else -impact
        
        # Exécution
        total_cost = execution_price * quantity + commission
        
        if side == 'buy':
            if self.balance < total_cost:
                raise InsufficientLiquidityError(
                    f"Fonds insuffisants: besoin de ${total_cost:.2f}, "
                    f"disponible: ${self.balance:.2f}"
                )
            self.balance -= total_cost
            self.holdings += quantity
        else:
            if self.holdings < quantity:
                if self.config.allow_short_selling:
                    # Short selling
                    self.holdings -= quantity
                    self.balance += execution_price * quantity - commission
                else:
                    raise InsufficientLiquidityError(
                        f"Holdings insuffisants: {self.holdings} < {quantity}"
                    )
            else:
                self.holdings -= quantity
                self.balance += execution_price * quantity - commission
        
        # Enregistrement
        order = {
            'order_id': order_id,
            'side': side,
            'quantity': quantity,
            'execution_price': execution_price,
            'commission': commission,
            'total_cost': total_cost,
            'timestamp': self.current_time,
            'type': 'market',
            'status': 'filled'
        }
        
        self.trades.append(order)
        self.total_trades += 1
        self.total_volume += quantity
        
        # Mise à jour du carnet d'ordres
        self._update_order_book(execution_price)
        
        logger.debug(
            f"Ordre market exécuté: {side} {quantity:.4f} @ ${execution_price:.4f}"
        )
        
        return order
    
    def _execute_limit_order(
        self,
        side: str,
        quantity: float,
        limit_price: float,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Exécute un ordre limit.
        
        Args:
            side: 'buy' ou 'sell'
            quantity: Quantité
            limit_price: Prix limite
            order_id: ID de l'ordre
            
        Returns:
            Détails de l'ordre exécuté.
        """
        execution_price = limit_price
        
        # Vérification du prix
        if side == 'buy' and limit_price >= self.current_price:
            # Le prix limite est atteint
            pass
        elif side == 'sell' and limit_price <= self.current_price:
            pass
        else:
            # L'ordre n'est pas exécuté
            return {
                'order_id': order_id,
                'side': side,
                'quantity': quantity,
                'limit_price': limit_price,
                'timestamp': self.current_time,
                'type': 'limit',
                'status': 'pending'
            }
        
        # Commission
        commission = calculate_commission(
            price=execution_price,
            volume=quantity,
            commission_pct=self.config.commission_pct,
            commission_fixed=self.config.commission_fixed
        )
        
        # Exécution
        total_cost = execution_price * quantity + commission
        
        if side == 'buy':
            if self.balance < total_cost:
                return {
                    'order_id': order_id,
                    'side': side,
                    'quantity': quantity,
                    'limit_price': limit_price,
                    'timestamp': self.current_time,
                    'type': 'limit',
                    'status': 'rejected'
                }
            self.balance -= total_cost
            self.holdings += quantity
        else:
            if self.holdings < quantity and not self.config.allow_short_selling:
                return {
                    'order_id': order_id,
                    'side': side,
                    'quantity': quantity,
                    'limit_price': limit_price,
                    'timestamp': self.current_time,
                    'type': 'limit',
                    'status': 'rejected'
                }
            self.holdings -= quantity
            self.balance += execution_price * quantity - commission
        
        order = {
            'order_id': order_id,
            'side': side,
            'quantity': quantity,
            'execution_price': execution_price,
            'commission': commission,
            'total_cost': total_cost,
            'timestamp': self.current_time,
            'type': 'limit',
            'status': 'filled'
        }
        
        self.trades.append(order)
        self.total_trades += 1
        self.total_volume += quantity
        
        return order
    
    def _execute_stop_order(
        self,
        side: str,
        quantity: float,
        stop_price: float,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Exécute un ordre stop.
        
        Args:
            side: 'buy' ou 'sell'
            quantity: Quantité
            stop_price: Prix de déclenchement
            order_id: ID de l'ordre
            
        Returns:
            Détails de l'ordre exécuté.
        """
        # Vérification du déclenchement
        if side == 'buy' and self.current_price >= stop_price:
            # Déclenché -> devient market order
            return self._execute_market_order(side, quantity, order_id)
        elif side == 'sell' and self.current_price <= stop_price:
            # Déclenché -> devient market order
            return self._execute_market_order(side, quantity, order_id)
        
        # Non déclenché
        return {
            'order_id': order_id,
            'side': side,
            'quantity': quantity,
            'stop_price': stop_price,
            'timestamp': self.current_time,
            'type': 'stop',
            'status': 'pending'
        }
    
    def _execute_stop_limit_order(
        self,
        side: str,
        quantity: float,
        stop_price: float,
        limit_price: float,
        order_id: str
    ) -> Dict[str, Any]:
        """
        Exécute un ordre stop-limit.
        
        Args:
            side: 'buy' ou 'sell'
            quantity: Quantité
            stop_price: Prix de déclenchement
            limit_price: Prix limite
            order_id: ID de l'ordre
            
        Returns:
            Détails de l'ordre exécuté.
        """
        # Vérification du déclenchement
        triggered = False
        if side == 'buy' and self.current_price >= stop_price:
            triggered = True
        elif side == 'sell' and self.current_price <= stop_price:
            triggered = True
        
        if triggered:
            # Devient un ordre limit
            return self._execute_limit_order(side, quantity, limit_price, order_id)
        
        return {
            'order_id': order_id,
            'side': side,
            'quantity': quantity,
            'stop_price': stop_price,
            'limit_price': limit_price,
            'timestamp': self.current_time,
            'type': 'stop_limit',
            'status': 'pending'
        }
    
    def _check_liquidity(
        self,
        side: str,
        quantity: float,
        price: Optional[float] = None
    ) -> bool:
        """
        Vérifie si la liquidité est suffisante.
        
        Args:
            side: 'buy' ou 'sell'
            quantity: Quantité demandée
            price: Prix (optionnel)
            
        Returns:
            True si la liquidité est suffisante.
        """
        # Vérification de la profondeur
        if side == 'buy':
            # Vérifier les asks disponibles
            total_available = sum(ask.volume for ask in self.asks)
            return total_available >= quantity * 0.5  # Au moins 50% de la quantité
        else:
            # Vérifier les bids disponibles
            total_available = sum(bid.volume for bid in self.bids)
            return total_available >= quantity * 0.5
    
    def _get_best_bid(self) -> Optional[float]:
        """
        Retourne le meilleur bid.
        
        Returns:
            Meilleur prix bid ou None.
        """
        if self.bids:
            return self.bids[0].price
        return None
    
    def _get_best_ask(self) -> Optional[float]:
        """
        Retourne le meilleur ask.
        
        Returns:
            Meilleur prix ask ou None.
        """
        if self.asks:
            return self.asks[0].price
        return None
    
    def _calculate_market_impact(
        self,
        side: str,
        quantity: float,
        price: float
    ) -> float:
        """
        Calcule l'impact sur le marché.
        
        Args:
            side: 'buy' ou 'sell'
            quantity: Quantité
            price: Prix
            
        Returns:
            Impact sur le prix.
        """
        if not self.config.market_impact_pct:
            return 0.0
        
        # Impact proportionnel à la taille de l'ordre
        impact = price * self.config.market_impact_pct * (quantity / 1000)
        return min(impact, price * 0.01)  # Limiter à 1%
    
    # ============================================================
    # BOUCLE DE SIMULATION
    # ============================================================
    
    def step(self) -> Optional[SimulationTick]:
        """
        Avance d'un pas de simulation.
        
        Returns:
            SimulationTick du pas courant ou None si terminé.
        """
        if self.current_step >= self.config.max_steps:
            return None
        
        # Mise à jour du temps
        delta = self._get_time_delta()
        self.current_time += delta
        self.current_step += 1
        
        # Génération du prix
        old_price = self.current_price
        new_price = self._generate_price(self.current_step)
        
        # Si le nouveau prix est invalide, garder l'ancien
        if np.isnan(new_price) or new_price <= 0:
            new_price = old_price * (1 + random.uniform(-0.01, 0.01))
        
        self.current_price = new_price
        self.historical_prices.append(new_price)
        
        # Calcul du rendement
        if old_price > 0:
            ret = (new_price - old_price) / old_price
            self.returns.append(ret)
        
        # Génération du volume
        volume = self._generate_volume()
        
        # Mise à jour du carnet d'ordres
        self._update_order_book(new_price)
        
        # Calcul de l'equity
        equity = self.balance + self.holdings * new_price
        self.equity_curve.append(equity)
        
        # Création du tick
        tick = SimulationTick(
            timestamp=self.current_time,
            price=new_price,
            volume=volume,
            bid=self._get_best_bid() or new_price * 0.999,
            ask=self._get_best_ask() or new_price * 1.001,
            spread=(self._get_best_ask() or new_price * 1.001) - (self._get_best_bid() or new_price * 0.999),
            open=old_price,
            high=max(old_price, new_price),
            low=min(old_price, new_price),
            close=new_price
        )
        
        return tick
    
    def _get_time_delta(self) -> timedelta:
        """
        Retourne le delta de temps pour un pas.
        
        Returns:
            Timedelta correspondant.
        """
        mapping = {
            '1s': timedelta(seconds=1),
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1),
            '1w': timedelta(days=7),
            '1M': timedelta(days=30)
        }
        return mapping.get(self.config.time_step, timedelta(hours=1))
    
    def run_simulation(
        self,
        steps: Optional[int] = None,
        callback: Optional[callable] = None
    ) -> List[SimulationTick]:
        """
        Exécute la simulation sur plusieurs pas.
        
        Args:
            steps: Nombre de pas (None = max_steps).
            callback: Fonction de callback appelée à chaque pas.
            
        Returns:
            Liste des ticks de simulation.
        """
        if steps is None:
            steps = self.config.max_steps
        
        ticks = []
        
        logger.info(f"Démarrage de la simulation: {steps} pas")
        
        for i in range(steps):
            tick = self.step()
            if tick is None:
                break
            
            ticks.append(tick)
            
            if callback:
                callback(tick, i, steps)
            
            if (i + 1) % 1000 == 0:
                logger.info(f"Progression: {i+1}/{steps}")
        
        logger.info(f"Simulation terminée: {len(ticks)} ticks")
        return ticks
    
    # ============================================================
    # STATISTIQUES ET ANALYSE
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la simulation.
        
        Returns:
            Statistiques de simulation.
        """
        initial = self.config.initial_capital
        final = self.equity_curve[-1] if self.equity_curve else initial
        
        total_return = (final - initial) / initial if initial > 0 else 0
        
        # Volatilité
        returns = np.array(self.returns) if self.returns else np.array([0])
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        
        # Drawdown
        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
        
        # Sharpe ratio
        risk_free = 0.02
        excess_returns = returns - risk_free / 252
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if len(excess_returns) > 1 else 0
        
        return {
            'steps': self.current_step,
            'initial_price': self.config.initial_price,
            'final_price': self.current_price,
            'price_change': (self.current_price - self.config.initial_price) / self.config.initial_price,
            'initial_capital': initial,
            'final_capital': final,
            'total_return': total_return,
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'total_trades': self.total_trades,
            'total_volume': self.total_volume,
            'final_holdings': self.holdings,
            'final_balance': self.balance,
            'current_price': self.current_price,
            'bid': self._get_best_bid(),
            'ask': self._get_best_ask(),
            'spread': (self._get_best_ask() or 0) - (self._get_best_bid() or 0)
        }
    
    def get_equity_curve(self) -> List[float]:
        """
        Retourne la courbe de capitaux.
        
        Returns:
            Liste des valeurs d'equity.
        """
        return self.equity_curve.copy()
    
    def get_trades(self) -> List[Dict[str, Any]]:
        """
        Retourne l'historique des trades.
        
        Returns:
            Liste des trades.
        """
        return self.trades.copy()
    
    def reset(self) -> None:
        """
        Réinitialise la simulation.
        """
        self.current_step = 0
        self.current_price = self.config.initial_price
        self.historical_prices = [self.config.initial_price]
        self.returns = []
        self.trades = []
        self.balance = self.config.initial_capital
        self.holdings = 0
        self.equity_curve = [self.config.initial_capital]
        self.total_volume = 0
        self.total_trades = 0
        self.data_index = 0
        
        self._update_order_book(self.config.initial_price)
        
        logger.info("Simulation réinitialisée")
    
    # ============================================================
    # EXPORTATION
    # ============================================================
    
    def export_simulation(self, filepath: str) -> None:
        """
        Exporte les résultats de la simulation.
        
        Args:
            filepath: Chemin du fichier de sortie.
        """
        data = {
            'config': {
                'symbol': self.config.symbol,
                'initial_price': self.config.initial_price,
                'initial_capital': self.config.initial_capital,
                'time_step': self.config.time_step,
                'max_steps': self.config.max_steps
            },
            'statistics': self.get_statistics(),
            'equity_curve': self.equity_curve,
            'prices': self.historical_prices,
            'trades': self.trades
        }
        
        # Sauvegarde en JSON
        import json
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Simulation exportée: {filepath}")


# Fonctions utilitaires
def create_simulator(
    symbol: str,
    initial_price: float,
    initial_capital: float = 100000.0,
    **kwargs
) -> MarketSimulator:
    """
    Fonction utilitaire pour créer un simulateur.
    
    Args:
        symbol: Symbole à simuler.
        initial_price: Prix initial.
        initial_capital: Capital initial.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Simulateur de marché.
    """
    config = SimulationConfig(
        symbol=symbol,
        initial_price=initial_price,
        initial_capital=initial_capital,
        **kwargs
    )
    return MarketSimulator(config)


# Exportation
__all__ = [
    'MarketSimulator',
    'SimulationConfig',
    'SimulationTick',
    'OrderBookEntry',
    'create_simulator'
]

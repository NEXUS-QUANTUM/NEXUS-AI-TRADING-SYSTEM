"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Exchange Mock for Testing
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Mock d'exchange pour les tests unitaires et d'intégration
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading
import logging

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================
class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"

class OrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class TimeInForce(Enum):
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    GTD = "GTD"  # Good Till Date

class ExchangeError(Enum):
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVALID_ORDER = "INVALID_ORDER"
    INSUFFICIENT_LIQUIDITY = "INSUFFICIENT_LIQUIDITY"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    SYSTEM_ERROR = "SYSTEM_ERROR"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Order:
    """Représentation d'un ordre"""
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: float = 0.0
    avg_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    client_order_id: Optional[str] = None
    trailing_stop_offset: Optional[float] = None
    reduce_only: bool = False
    post_only: bool = False
    reject_reason: Optional[str] = None
    fee: float = 0.0
    fee_asset: str = "USDT"
    pnl: float = 0.0
    tags: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Balance:
    """Représentation d'un solde"""
    asset: str
    free: float = 0.0
    locked: float = 0.0
    total: float = 0.0
    usd_value: float = 0.0

@dataclass
class Ticker:
    """Représentation d'un ticker"""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    quote_volume: float
    high: float
    low: float
    change: float
    change_percent: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class OrderBook:
    """Représentation d'un carnet d'ordres"""
    symbol: str
    bids: List[List[float]]  # [[price, quantity], ...]
    asks: List[List[float]]  # [[price, quantity], ...]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Trade:
    """Représentation d'un trade"""
    id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: float
    cost: float
    fee: float
    fee_asset: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Kline:
    """Représentation d'une bougie"""
    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int
    timestamp: datetime = field(default_factory=datetime.now)

# ============================================================
# MOCK EXCHANGE
# ============================================================

class MockExchange:
    """
    Exchange simulé pour les tests
    
    Cette classe simule un exchange de cryptomonnaies avec:
    - Carnet d'ordres dynamique
    - Exécution d'ordres
    - Gestion des balances
    - Historique des trades
    - Simulation de marché
    """
    
    def __init__(self, name: str = "Mock Exchange", initial_balance: Dict[str, float] = None):
        """
        Initialise le mock exchange
        
        Args:
            name: Nom de l'exchange
            initial_balance: Solde initial par actif
        """
        self.name = name
        self.initial_balance = initial_balance or {
            "USDT": 100000.0,
            "BTC": 10.0,
            "ETH": 100.0,
            "SOL": 1000.0,
            "ADA": 100000.0,
            "DOT": 10000.0,
            "AVAX": 1000.0,
            "MATIC": 100000.0,
            "LINK": 1000.0,
            "XRP": 100000.0,
            "DOGE": 1000000.0,
            "UNI": 1000.0,
            "ATOM": 1000.0,
            "NEAR": 1000.0,
            "ARB": 10000.0,
            "OP": 10000.0,
            "INJ": 1000.0,
            "SUI": 10000.0,
        }
        
        # État
        self.balances = {asset: Balance(asset=asset, free=amount, locked=0.0, total=amount) 
                        for asset, amount in self.initial_balance.items()}
        
        self.orders: Dict[str, Order] = {}
        self.order_id_counter = 0
        self.trades: List[Trade] = []
        self.trade_id_counter = 0
        
        # Carnet d'ordres simulé
        self.order_book = {
            "BTC/USDT": {"bids": [], "asks": []},
            "ETH/USDT": {"bids": [], "asks": []},
            "SOL/USDT": {"bids": [], "asks": []},
            "ADA/USDT": {"bids": [], "asks": []},
            "DOT/USDT": {"bids": [], "asks": []},
            "AVAX/USDT": {"bids": [], "asks": []},
            "MATIC/USDT": {"bids": [], "asks": []},
            "LINK/USDT": {"bids": [], "asks": []},
            "XRP/USDT": {"bids": [], "asks": []},
            "DOGE/USDT": {"bids": [], "asks": []},
            "UNI/USDT": {"bids": [], "asks": []},
            "ATOM/USDT": {"bids": [], "asks": []},
            "NEAR/USDT": {"bids": [], "asks": []},
            "ARB/USDT": {"bids": [], "asks": []},
            "OP/USDT": {"bids": [], "asks": []},
            "INJ/USDT": {"bids": [], "asks": []},
            "SUI/USDT": {"bids": [], "asks": []},
        }
        
        # Ticker simulé
        self.tickers: Dict[str, Ticker] = {}
        self._init_tickers()
        
        # Simulation de marché
        self.market_running = False
        self.market_thread = None
        self.base_prices = {
            "BTC/USDT": 45000.0,
            "ETH/USDT": 3000.0,
            "SOL/USDT": 150.0,
            "ADA/USDT": 0.5,
            "DOT/USDT": 7.0,
            "AVAX/USDT": 35.0,
            "MATIC/USDT": 0.8,
            "LINK/USDT": 15.0,
            "XRP/USDT": 0.6,
            "DOGE/USDT": 0.08,
            "UNI/USDT": 7.0,
            "ATOM/USDT": 10.0,
            "NEAR/USDT": 4.0,
            "ARB/USDT": 1.8,
            "OP/USDT": 3.5,
            "INJ/USDT": 35.0,
            "SUI/USDT": 2.0,
        }
        
        self.current_prices = self.base_prices.copy()
        self.volatility = 0.002  # 0.2% par tick
        
        # WebSocket simulé
        self.ws_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.ws_running = False
        self.ws_thread = None
        
        # Logs
        self.logs: List[Dict[str, Any]] = []
        
        logger.info(f"MockExchange '{name}' initialized with {len(self.balances)} assets")
    
    def _init_tickers(self):
        """Initialise les tickers"""
        for symbol in self.base_prices:
            price = self.base_prices[symbol]
            self.tickers[symbol] = Ticker(
                symbol=symbol,
                bid=price * 0.999,
                ask=price * 1.001,
                last=price,
                volume=random.uniform(100, 1000),
                quote_volume=price * random.uniform(100, 1000),
                high=price * 1.02,
                low=price * 0.98,
                change=0.0,
                change_percent=0.0
            )
    
    def _update_tickers(self):
        """Met à jour les tickers"""
        for symbol in self.tickers:
            price = self.current_prices[symbol]
            old_price = self.tickers[symbol].last
            change = price - old_price
            change_percent = (change / old_price) * 100 if old_price != 0 else 0
            
            self.tickers[symbol].bid = price * 0.999
            self.tickers[symbol].ask = price * 1.001
            self.tickers[symbol].last = price
            self.tickers[symbol].high = max(self.tickers[symbol].high, price)
            self.tickers[symbol].low = min(self.tickers[symbol].low, price)
            self.tickers[symbol].change = change
            self.tickers[symbol].change_percent = change_percent
            self.tickers[symbol].volume += random.uniform(1, 10)
            self.tickers[symbol].timestamp = datetime.now()
    
    def _update_order_book(self, symbol: str):
        """Met à jour le carnet d'ordres"""
        if symbol not in self.order_book:
            return
        
        price = self.current_prices[symbol]
        spread = price * 0.001  # 0.1% spread
        depth = 20
        
        # Créer des ordres bid (achat)
        bids = []
        for i in range(depth):
            bid_price = price - spread - (i * spread * 0.5)
            quantity = random.uniform(0.1, 1.0) * (1 + i * 0.1)
            bids.append([bid_price, quantity])
        
        # Créer des ordres ask (vente)
        asks = []
        for i in range(depth):
            ask_price = price + spread + (i * spread * 0.5)
            quantity = random.uniform(0.1, 1.0) * (1 + i * 0.1)
            asks.append([ask_price, quantity])
        
        self.order_book[symbol] = {"bids": bids, "asks": asks}
    
    def _generate_price(self) -> float:
        """Génère une nouvelle variation de prix"""
        # Mouvement brownien avec volatilité
        random_walk = random.gauss(0, self.volatility)
        return 1 + random_walk
    
    def _market_simulation(self):
        """Simule le marché en arrière-plan"""
        while self.market_running:
            try:
                # Mettre à jour les prix
                for symbol in self.current_prices:
                    change = self._generate_price()
                    self.current_prices[symbol] *= change
                    self.current_prices[symbol] = max(self.current_prices[symbol], 0.0001)
                
                # Mettre à jour les tickers
                self._update_tickers()
                
                # Mettre à jour les carnets d'ordres
                for symbol in self.order_book:
                    self._update_order_book(symbol)
                
                # Simuler des trades aléatoires
                if random.random() < 0.1:
                    symbol = random.choice(list(self.current_prices.keys()))
                    side = random.choice([OrderSide.BUY, OrderSide.SELL])
                    price = self.current_prices[symbol]
                    quantity = random.uniform(0.01, 1.0)
                    
                    trade = Trade(
                        id=f"trade_{self.trade_id_counter}",
                        symbol=symbol,
                        side=side,
                        price=price,
                        quantity=quantity,
                        cost=price * quantity,
                        fee=price * quantity * 0.001,
                        fee_asset="USDT",
                        timestamp=datetime.now()
                    )
                    self.trade_id_counter += 1
                    self.trades.append(trade)
                
                # Exécuter les ordres en attente
                self._process_orders()
                
                # Log
                self._log("info", f"Market simulation tick - {len(self.orders)} orders pending")
                
                time.sleep(0.1)  # 10 ticks par seconde
                
            except Exception as e:
                self._log("error", f"Market simulation error: {str(e)}")
                time.sleep(1)
    
    def _process_orders(self):
        """Traite les ordres en attente"""
        to_remove = []
        
        for order_id, order in self.orders.items():
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED]:
                to_remove.append(order_id)
                continue
            
            # Vérifier l'expiration
            if order.time_in_force == TimeInForce.GTD and order.expires_at:
                if datetime.now() > order.expires_at:
                    order.status = OrderStatus.EXPIRED
                    to_remove.append(order_id)
                    self._log("info", f"Order {order_id} expired")
                    continue
            
            # Vérifier le statut
            price = self.current_prices.get(order.symbol, 0)
            
            if order.type == OrderType.MARKET:
                # Ordre au marché - exécution immédiate
                self._execute_order(order_id, price)
                to_remove.append(order_id)
                
            elif order.type == OrderType.LIMIT:
                # Ordre limité
                if order.side == OrderSide.BUY:
                    if price <= order.price:
                        self._execute_order(order_id, price)
                        to_remove.append(order_id)
                else:  # SELL
                    if price >= order.price:
                        self._execute_order(order_id, price)
                        to_remove.append(order_id)
                        
            elif order.type == OrderType.STOP:
                # Ordre stop
                if order.side == OrderSide.BUY:
                    if price >= order.stop_price:
                        self._execute_order(order_id, price)
                        to_remove.append(order_id)
                else:  # SELL
                    if price <= order.stop_price:
                        self._execute_order(order_id, price)
                        to_remove.append(order_id)
                        
            elif order.type == OrderType.TRAILING_STOP:
                # Ordre trailing stop
                if order.trailing_stop_offset is not None:
                    highest = order.tags.get("highest_price", price)
                    lowest = order.tags.get("lowest_price", price)
                    
                    if order.side == OrderSide.SELL:
                        if price > highest:
                            highest = price
                            order.tags["highest_price"] = highest
                        if price <= highest * (1 - order.trailing_stop_offset):
                            self._execute_order(order_id, price)
                            to_remove.append(order_id)
                    else:  # BUY
                        if price < lowest:
                            lowest = price
                            order.tags["lowest_price"] = lowest
                        if price >= lowest * (1 + order.trailing_stop_offset):
                            self._execute_order(order_id, price)
                            to_remove.append(order_id)
        
        # Nettoyer les ordres terminés
        for order_id in to_remove:
            if order_id in self.orders:
                del self.orders[order_id]
    
    def _execute_order(self, order_id: str, execution_price: float):
        """Exécute un ordre"""
        order = self.orders.get(order_id)
        if not order:
            return
        
        # Vérifier le solde
        if order.side == OrderSide.BUY:
            required = execution_price * order.quantity
            quote_asset = self._get_quote_asset(order.symbol)
            
            if self.balances.get(quote_asset, Balance(asset=quote_asset)).free < required:
                order.status = OrderStatus.REJECTED
                order.reject_reason = "INSUFFICIENT_BALANCE"
                self._log("warning", f"Order {order_id} rejected: Insufficient balance")
                return
            
            # Débiter le compte
            self._debit(quote_asset, required)
            # Créditer l'actif de base
            self._credit(order.symbol.split('/')[0], order.quantity)
            
        else:  # SELL
            base_asset = order.symbol.split('/')[0]
            
            if self.balances.get(base_asset, Balance(asset=base_asset)).free < order.quantity:
                order.status = OrderStatus.REJECTED
                order.reject_reason = "INSUFFICIENT_BALANCE"
                self._log("warning", f"Order {order_id} rejected: Insufficient balance")
                return
            
            # Débiter l'actif de base
            self._debit(base_asset, order.quantity)
            # Créditer le compte
            quote_asset = self._get_quote_asset(order.symbol)
            self._credit(quote_asset, execution_price * order.quantity)
        
        # Mettre à jour l'ordre
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_price = execution_price
        order.updated_at = datetime.now()
        
        # Ajouter le trade
        trade = Trade(
            id=f"trade_{self.trade_id_counter}",
            symbol=order.symbol,
            side=order.side,
            price=execution_price,
            quantity=order.quantity,
            cost=execution_price * order.quantity,
            fee=execution_price * order.quantity * 0.001,
            fee_asset="USDT",
            timestamp=datetime.now()
        )
        self.trade_id_counter += 1
        self.trades.append(trade)
        
        self._log("info", f"Order {order_id} executed at {execution_price}")
    
    def _debit(self, asset: str, amount: float):
        """Débite un montant d'un actif"""
        if asset in self.balances:
            self.balances[asset].free -= amount
            self.balances[asset].total -= amount
            if self.balances[asset].free < 0:
                self.balances[asset].free = 0
            if self.balances[asset].total < 0:
                self.balances[asset].total = 0
    
    def _credit(self, asset: str, amount: float):
        """Crédite un montant d'un actif"""
        if asset not in self.balances:
            self.balances[asset] = Balance(asset=asset, free=0.0, locked=0.0, total=0.0)
        self.balances[asset].free += amount
        self.balances[asset].total += amount
    
    def _get_quote_asset(self, symbol: str) -> str:
        """Récupère l'actif de quote"""
        return symbol.split('/')[1] if '/' in symbol else "USDT"
    
    def _get_base_asset(self, symbol: str) -> str:
        """Récupère l'actif de base"""
        return symbol.split('/')[0] if '/' in symbol else symbol
    
    def _log(self, level: str, message: str):
        """Ajoute un log"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "exchange": self.name
        }
        self.logs.append(log_entry)
        
        if level == "error":
            logger.error(f"[{self.name}] {message}")
        elif level == "warning":
            logger.warning(f"[{self.name}] {message}")
        else:
            logger.info(f"[{self.name}] {message}")
    
    # ============================================================
    # PUBLIC API METHODS
    # ============================================================
    
    def start_market(self):
        """Démarre la simulation de marché"""
        if not self.market_running:
            self.market_running = True
            self.market_thread = threading.Thread(target=self._market_simulation)
            self.market_thread.daemon = True
            self.market_thread.start()
            self._log("info", "Market simulation started")
    
    def stop_market(self):
        """Arrête la simulation de marché"""
        self.market_running = False
        if self.market_thread:
            self.market_thread.join(timeout=2)
        self._log("info", "Market simulation stopped")
    
    def get_price(self, symbol: str) -> float:
        """Récupère le prix actuel d'un symbole"""
        return self.current_prices.get(symbol, 0.0)
    
    def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Récupère le ticker d'un symbole"""
        return self.tickers.get(symbol)
    
    def get_order_book(self, symbol: str, depth: int = 20) -> Optional[OrderBook]:
        """Récupère le carnet d'ordres"""
        if symbol not in self.order_book:
            return None
        
        book = self.order_book[symbol]
        return OrderBook(
            symbol=symbol,
            bids=book["bids"][:depth],
            asks=book["asks"][:depth]
        )
    
    def create_order(self, symbol: str, side: str, order_type: str, quantity: float,
                    price: Optional[float] = None, stop_price: Optional[float] = None,
                    time_in_force: str = "GTC", client_order_id: Optional[str] = None,
                    trailing_stop_offset: Optional[float] = None,
                    reduce_only: bool = False, post_only: bool = False) -> Order:
        """
        Crée un ordre
        
        Args:
            symbol: Symbole de trading
            side: BUY ou SELL
            order_type: MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP
            quantity: Quantité
            price: Prix (requis pour LIMIT, STOP_LIMIT)
            stop_price: Prix stop (requis pour STOP, STOP_LIMIT)
            time_in_force: GTC, IOC, FOK, GTD
            client_order_id: ID client personnalisé
            trailing_stop_offset: Offset pour trailing stop
            reduce_only: Réduire uniquement
            post_only: Post only
        
        Returns:
            Order: L'ordre créé
        """
        # Valider le symbole
        if symbol not in self.current_prices:
            raise ValueError(f"Invalid symbol: {symbol}")
        
        # Valider le type d'ordre
        try:
            side_enum = OrderSide(side)
            type_enum = OrderType(order_type)
            tif_enum = TimeInForce(time_in_force)
        except ValueError as e:
            raise ValueError(f"Invalid order parameters: {e}")
        
        # Valider les prix selon le type
        if type_enum in [OrderType.LIMIT, OrderType.STOP_LIMIT] and price is None:
            raise ValueError(f"Price required for {order_type} order")
        
        if type_enum in [OrderType.STOP, OrderType.STOP_LIMIT] and stop_price is None:
            raise ValueError(f"Stop price required for {order_type} order")
        
        if type_enum == OrderType.TRAILING_STOP and trailing_stop_offset is None:
            raise ValueError("Trailing stop offset required for TRAILING_STOP order")
        
        # Créer l'ordre
        self.order_id_counter += 1
        order_id = f"order_{self.order_id_counter}"
        
        order = Order(
            id=order_id,
            symbol=symbol,
            side=side_enum,
            type=type_enum,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=tif_enum,
            client_order_id=client_order_id,
            trailing_stop_offset=trailing_stop_offset,
            reduce_only=reduce_only,
            post_only=post_only,
            tags={
                "highest_price": self.current_prices[symbol],
                "lowest_price": self.current_prices[symbol]
            }
        )
        
        # Pour les ordres GTD
        if tif_enum == TimeInForce.GTD:
            order.expires_at = datetime.now() + timedelta(days=1)
        
        self.orders[order_id] = order
        
        self._log("info", f"Order {order_id} created: {side} {quantity} {symbol} {order_type}")
        
        return order
    
    def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre"""
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED]:
            return False
        
        order.status = OrderStatus.CANCELED
        order.updated_at = datetime.now()
        
        self._log("info", f"Order {order_id} canceled")
        return True
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Récupère un ordre"""
        return self.orders.get(order_id)
    
    def get_orders(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Order]:
        """Récupère les ordres"""
        result = list(self.orders.values())
        
        if symbol:
            result = [o for o in result if o.symbol == symbol]
        
        if status:
            try:
                status_enum = OrderStatus(status)
                result = [o for o in result if o.status == status_enum]
            except ValueError:
                pass
        
        return result
    
    def get_balance(self, asset: Optional[str] = None) -> Union[Dict[str, Balance], Optional[Balance]]:
        """Récupère les soldes"""
        if asset:
            return self.balances.get(asset)
        return self.balances.copy()
    
    def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Trade]:
        """Récupère l'historique des trades"""
        result = self.trades
        if symbol:
            result = [t for t in result if t.symbol == symbol]
        return result[-limit:]
    
    def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[Kline]:
        """Récupère les bougies"""
        # Simuler des bougies
        klines = []
        price = self.current_prices[symbol]
        
        for i in range(limit):
            timestamp = datetime.now() - timedelta(minutes=limit - i)
            volatility = random.uniform(-0.02, 0.02)
            open_price = price * (1 + random.uniform(-0.01, 0.01))
            close_price = open_price * (1 + volatility)
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.01))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.01))
            
            klines.append(Kline(
                symbol=symbol,
                interval=interval,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=random.uniform(10, 100),
                quote_volume=close_price * random.uniform(10, 100),
                trades=random.randint(1, 50),
                timestamp=timestamp
            ))
            price = close_price
        
        return klines
    
    def get_websocket_url(self) -> str:
        """Récupère l'URL WebSocket"""
        return f"wss://mock.{self.name.lower().replace(' ', '')}.exchange/ws"
    
    def set_price(self, symbol: str, price: float):
        """Définit le prix d'un symbole (pour les tests)"""
        if symbol in self.current_prices:
            self.current_prices[symbol] = price
            self._update_tickers()
            self._update_order_book(symbol)
    
    def set_balance(self, asset: str, amount: float):
        """Définit le solde d'un actif (pour les tests)"""
        if asset in self.balances:
            self.balances[asset].free = amount
            self.balances[asset].total = amount
        else:
            self.balances[asset] = Balance(asset=asset, free=amount, locked=0.0, total=amount)
    
    def set_volatility(self, volatility: float):
        """Définit la volatilité (pour les tests)"""
        self.volatility = max(0.0001, volatility)
    
    def reset(self):
        """Réinitialise l'exchange (pour les tests)"""
        self.balances = {asset: Balance(asset=asset, free=amount, locked=0.0, total=amount)
                        for asset, amount in self.initial_balance.items()}
        self.orders = {}
        self.order_id_counter = 0
        self.trades = []
        self.trade_id_counter = 0
        self.current_prices = self.base_prices.copy()
        self.logs = []
        self._init_tickers()
        for symbol in self.order_book:
            self._update_order_book(symbol)
        self._log("info", "Exchange reset")

# ============================================================
# MOCK EXCHANGE FACTORY
# ============================================================

class MockExchangeFactory:
    """Fabrique de mock exchanges"""
    
    _instances: Dict[str, MockExchange] = {}
    
    @classmethod
    def create(cls, name: str = "Mock Exchange", initial_balance: Dict[str, float] = None) -> MockExchange:
        """Crée ou récupère un mock exchange"""
        if name not in cls._instances:
            cls._instances[name] = MockExchange(name, initial_balance)
        return cls._instances[name]
    
    @classmethod
    def get(cls, name: str = "Mock Exchange") -> Optional[MockExchange]:
        """Récupère un mock exchange"""
        return cls._instances.get(name)
    
    @classmethod
    def reset_all(cls):
        """Réinitialise tous les mock exchanges"""
        for instance in cls._instances.values():
            instance.reset()
    
    @classmethod
    def stop_all(cls):
        """Arrête tous les mock exchanges"""
        for instance in cls._instances.values():
            if instance.market_running:
                instance.stop_market()

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'TimeInForce',
    'ExchangeError',
    'Order',
    'Balance',
    'Ticker',
    'OrderBook',
    'Trade',
    'Kline',
    'MockExchange',
    'MockExchangeFactory',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Mock exchange module initialized")

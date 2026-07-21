"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Executor
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Exécuteur d'ordres pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from collections import defaultdict
import json

# Imports internes
from .core.exchange_manager import ExchangeManager
from .core.execution_engine import ExecutionEngine
from .core.risk_manager import RiskManager
from .core.data_manager import DataManager
from .core.cache_manager import CacheManager

from .utils import (
    async_retry,
    async_timeout,
    get_cache_manager,
    NumberFormatter,
    StatisticsUtils,
)

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# EXECUTOR
# ============================================================

class ArbitrageBotExecutor:
    """
    Exécuteur d'ordres pour le bot d'arbitrage
    
    Gère l'exécution des ordres, le routage intelligent,
    le batching et le monitoring des ordres
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
        max_slippage: float = 0.01,
        enable_batch: bool = True,
        batch_size: int = 10,
        batch_timeout: float = 5.0
    ):
        """
        Initialise l'exécuteur
        
        Args:
            config_path: Chemin de la configuration
            max_retries: Nombre maximum de tentatives
            retry_delay: Délai entre les tentatives
            timeout: Timeout
            max_slippage: Slippage maximum
            enable_batch: Activer le batching
            batch_size: Taille des lots
            batch_timeout: Timeout des lots
        """
        self.config_path = config_path or "config/arbitrage_config.yaml"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.max_slippage = max_slippage
        self.enable_batch = enable_batch
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        # Configuration
        self.config = None
        self._load_config()
        
        # Composants
        self._init_components()
        
        # Cache
        self.cache = get_cache_manager()
        
        # État
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.trades: List[Dict[str, Any]] = []
        self.batch_orders: List[Dict[str, Any]] = []
        self.batch_task = None
        self._running = False
        
        # Statistiques
        self.stats = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'total_trades': 0,
            'total_volume': 0,
            'total_pnl': 0,
            'avg_latency': 0,
            'fill_rate': 0,
            'slippage': 0,
        }
        
        logger.info("Executor initialized")
    
    def _load_config(self):
        """Charge la configuration"""
        try:
            loader = ConfigLoader(self.config_path)
            self.config = loader.load()
            logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _init_components(self):
        """Initialise les composants"""
        self.components = {
            'exchange_manager': ExchangeManager(self.config),
            'execution_engine': ExecutionEngine(self.config),
            'risk_manager': RiskManager(self.config),
            'data_manager': DataManager(),
        }
        
        logger.info("Components initialized")
    
    # ============================================================
    # ORDER EXECUTION
    # ============================================================
    
    async def execute_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Exécute un ordre
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole
            side: Côté (BUY/SELL)
            quantity: Quantité
            order_type: Type d'ordre
            price: Prix (pour les ordres limit)
            stop_price: Prix stop (pour les ordres stop)
            reduce_only: Réduire uniquement
            client_order_id: ID client
            tags: Tags supplémentaires
            
        Returns:
            Dict[str, Any]: Résultat de l'ordre
        """
        order_id = client_order_id or str(uuid.uuid4())[:8]
        
        # Préparer l'ordre
        order = {
            'id': order_id,
            'exchange': exchange,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'type': order_type,
            'price': price,
            'stop_price': stop_price,
            'reduce_only': reduce_only,
            'client_order_id': client_order_id,
            'tags': tags or {},
            'status': 'PENDING',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
        
        # Ajouter à la liste
        self.orders[order_id] = order
        self.stats['total_orders'] += 1
        
        try:
            # Valider l'ordre
            validation = await self._validate_order(order)
            if not validation['valid']:
                order['status'] = 'REJECTED'
                order['error'] = validation['error']
                self.stats['failed_orders'] += 1
                return order
            
            # Exécuter avec retry
            result = await self._execute_with_retry(order)
            
            # Mettre à jour l'ordre
            order.update(result)
            order['updated_at'] = datetime.now().isoformat()
            
            if result['status'] == 'FILLED':
                self.stats['successful_orders'] += 1
                self.stats['total_trades'] += 1
                self.stats['total_volume'] += quantity
                self.stats['total_pnl'] += result.get('pnl', 0)
                
                # Ajouter aux trades
                self.trades.append(order)
            else:
                self.stats['failed_orders'] += 1
            
            return order
            
        except Exception as e:
            order['status'] = 'ERROR'
            order['error'] = str(e)
            self.stats['failed_orders'] += 1
            logger.error(f"Order execution error: {e}")
            return order
    
    async def _validate_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide un ordre
        
        Args:
            order: Ordre à valider
            
        Returns:
            Dict[str, Any]: Résultat de la validation
        """
        # Vérifier le solde
        exchange_name = order['exchange']
        exchange_obj = self.components['exchange_manager'].get_exchange(exchange_name)
        if not exchange_obj:
            return {'valid': False, 'error': f"Exchange not found: {exchange_name}"}
        
        balance = await exchange_obj.async_get_balance()
        symbol = order['symbol']
        side = order['side']
        quantity = order['quantity']
        
        # Vérifier la paire de trading
        if symbol not in exchange_obj.get_symbols():
            return {'valid': False, 'error': f"Symbol not available: {symbol}"}
        
        # Vérifier le solde pour les ordres d'achat
        if side == 'BUY':
            quote_asset = symbol.split('/')[1]
            required = quantity * order.get('price', 0)
            
            if quote_asset not in balance:
                return {'valid': False, 'error': f"Balance not available for {quote_asset}"}
            
            if balance[quote_asset]['free'] < required:
                return {'valid': False, 'error': f"Insufficient balance: {required} {quote_asset}"}
        
        # Vérifier le solde pour les ordres de vente
        elif side == 'SELL':
            base_asset = symbol.split('/')[0]
            
            if base_asset not in balance:
                return {'valid': False, 'error': f"Balance not available for {base_asset}"}
            
            if balance[base_asset]['free'] < quantity:
                return {'valid': False, 'error': f"Insufficient balance: {quantity} {base_asset}"}
        
        return {'valid': True}
    
    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def _execute_with_retry(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exécute un ordre avec retry
        
        Args:
            order: Ordre à exécuter
            
        Returns:
            Dict[str, Any]: Résultat de l'ordre
        """
        exchange_name = order['exchange']
        exchange_obj = self.components['exchange_manager'].get_exchange(exchange_name)
        
        if not exchange_obj:
            raise Exception(f"Exchange not found: {exchange_name}")
        
        # Obtenir le prix actuel
        ticker = await exchange_obj.async_get_ticker(order['symbol'])
        if not ticker:
            raise Exception(f"Ticker not available: {order['symbol']}")
        
        current_price = ticker.get('last', 0)
        
        # Vérifier le slippage
        if order['type'] == 'MARKET':
            if order['side'] == 'BUY':
                execution_price = current_price * (1 + self.max_slippage)
            else:
                execution_price = current_price * (1 - self.max_slippage)
        else:
            execution_price = order.get('price', current_price)
        
        # Exécuter l'ordre
        result = await exchange_obj.async_create_order(
            symbol=order['symbol'],
            side=order['side'],
            order_type=order['type'],
            quantity=order['quantity'],
            price=execution_price,
            stop_price=order.get('stop_price'),
            reduce_only=order.get('reduce_only', False),
        )
        
        # Ajouter les métadonnées
        result['exchange'] = exchange_name
        result['symbol'] = order['symbol']
        result['client_order_id'] = order.get('client_order_id')
        result['tags'] = order.get('tags', {})
        
        return result
    
    # ============================================================
    # BATCH EXECUTION
    # ============================================================
    
    async def execute_batch(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Exécute un lot d'ordres
        
        Args:
            orders: Liste des ordres
            
        Returns:
            List[Dict[str, Any]]: Résultats des ordres
        """
        if not self.enable_batch:
            # Exécuter séquentiellement
            results = []
            for order in orders:
                result = await self.execute_order(**order)
                results.append(result)
            return results
        
        # Batching
        results = []
        batch = []
        
        for order in orders:
            batch.append(order)
            
            if len(batch) >= self.batch_size:
                batch_results = await self._execute_batch(batch)
                results.extend(batch_results)
                batch = []
        
        if batch:
            batch_results = await self._execute_batch(batch)
            results.extend(batch_results)
        
        return results
    
    async def _execute_batch(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Exécute un lot d'ordres
        
        Args:
            orders: Liste des ordres
            
        Returns:
            List[Dict[str, Any]]: Résultats des ordres
        """
        # Grouper par exchange
        by_exchange = defaultdict(list)
        for order in orders:
            by_exchange[order.get('exchange', 'default')].append(order)
        
        # Exécuter en parallèle
        tasks = []
        for exchange, exchange_orders in by_exchange.items():
            for order in exchange_orders:
                task = self.execute_order(**order)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results
    
    # ============================================================
    # ORDER MANAGEMENT
    # ============================================================
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Annule un ordre
        
        Args:
            order_id: ID de l'ordre
            
        Returns:
            bool: True si annulé
        """
        if order_id not in self.orders:
            logger.warning(f"Order not found: {order_id}")
            return False
        
        order = self.orders[order_id]
        exchange_name = order['exchange']
        exchange_obj = self.components['exchange_manager'].get_exchange(exchange_name)
        
        if not exchange_obj:
            logger.warning(f"Exchange not found: {exchange_name}")
            return False
        
        try:
            result = await exchange_obj.async_cancel_order(order_id)
            order['status'] = 'CANCELED'
            order['updated_at'] = datetime.now().isoformat()
            return True
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le statut d'un ordre
        
        Args:
            order_id: ID de l'ordre
            
        Returns:
            Optional[Dict[str, Any]]: Statut de l'ordre
        """
        if order_id not in self.orders:
            return None
        
        order = self.orders[order_id]
        exchange_name = order['exchange']
        exchange_obj = self.components['exchange_manager'].get_exchange(exchange_name)
        
        if not exchange_obj:
            return order
        
        try:
            status = await exchange_obj.async_get_order_status(order_id)
            order.update(status)
            order['updated_at'] = datetime.now().isoformat()
            return order
        except Exception as e:
            logger.error(f"Get order status error: {e}")
            return order
    
    # ============================================================
    # TRADE MANAGEMENT
    # ============================================================
    
    def get_trades(
        self,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère les trades
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole
            side: Côté
            status: Statut
            start_date: Date de début
            end_date: Date de fin
            
        Returns:
            List[Dict[str, Any]]: Trades
        """
        trades = self.trades.copy()
        
        # Filtrer
        if exchange:
            trades = [t for t in trades if t.get('exchange') == exchange]
        if symbol:
            trades = [t for t in trades if t.get('symbol') == symbol]
        if side:
            trades = [t for t in trades if t.get('side') == side]
        if status:
            trades = [t for t in trades if t.get('status') == status]
        if start_date:
            trades = [t for t in trades if t.get('created_at', '') >= start_date]
        if end_date:
            trades = [t for t in trades if t.get('created_at', '') <= end_date]
        
        return trades
    
    def get_orders(
        self,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère les ordres
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole
            status: Statut
            start_date: Date de début
            end_date: Date de fin
            
        Returns:
            List[Dict[str, Any]]: Ordres
        """
        orders = list(self.orders.values())
        
        # Filtrer
        if exchange:
            orders = [o for o in orders if o.get('exchange') == exchange]
        if symbol:
            orders = [o for o in orders if o.get('symbol') == symbol]
        if status:
            orders = [o for o in orders if o.get('status') == status]
        if start_date:
            orders = [o for o in orders if o.get('created_at', '') >= start_date]
        if end_date:
            orders = [o for o in orders if o.get('created_at', '') <= end_date]
        
        return orders
    
    # ============================================================
    # PERFORMANCE METRICS
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        total_orders = self.stats['total_orders']
        successful_orders = self.stats['successful_orders']
        
        return {
            'total_orders': total_orders,
            'successful_orders': successful_orders,
            'failed_orders': self.stats['failed_orders'],
            'total_trades': self.stats['total_trades'],
            'total_volume': self.stats['total_volume'],
            'total_pnl': self.stats['total_pnl'],
            'avg_pnl': self.stats['total_pnl'] / self.stats['total_trades'] if self.stats['total_trades'] > 0 else 0,
            'success_rate': successful_orders / total_orders if total_orders > 0 else 0,
            'fill_rate': self.stats['fill_rate'],
            'avg_latency': self.stats['avg_latency'],
            'slippage': self.stats['slippage'],
            'active_orders': len([o for o in self.orders.values() if o.get('status') in ['PENDING', 'NEW', 'PARTIALLY_FILLED']]),
        }

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot Executor")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default="config/arbitrage_config.yaml"
    )
    parser.add_argument(
        "-e", "--exchange",
        help="Exchange name",
        default="binance"
    )
    parser.add_argument(
        "-s", "--symbol",
        help="Symbol",
        default="BTC/USDT"
    )
    parser.add_argument(
        "-q", "--quantity",
        help="Quantity",
        type=float,
        default=0.01
    )
    parser.add_argument(
        "-S", "--side",
        help="Side (BUY/SELL)",
        choices=["BUY", "SELL"],
        default="BUY"
    )
    parser.add_argument(
        "-t", "--type",
        help="Order type",
        choices=["MARKET", "LIMIT"],
        default="MARKET"
    )
    parser.add_argument(
        "-p", "--price",
        help="Price (for LIMIT orders)",
        type=float,
        default=None
    )
    
    args = parser.parse_args()
    
    # Créer l'exécuteur
    executor = ArbitrageBotExecutor(
        config_path=args.config
    )
    
    # Exécuter un ordre
    async def run():
        result = await executor.execute_order(
            exchange=args.exchange,
            symbol=args.symbol,
            side=args.side,
            quantity=args.quantity,
            order_type=args.type,
            price=args.price
        )
        
        print("\n" + "=" * 60)
        print("ORDER RESULT")
        print("=" * 60)
        print(f"Order ID:      {result['id']}")
        print(f"Exchange:      {result['exchange']}")
        print(f"Symbol:        {result['symbol']}")
        print(f"Side:          {result['side']}")
        print(f"Quantity:      {result['quantity']}")
        print(f"Type:          {result['type']}")
        print(f"Price:         {result.get('price', 'N/A')}")
        print(f"Status:        {result['status']}")
        print(f"Filled:        {result.get('filled_quantity', 0)}")
        print(f"Avg Price:     {result.get('avg_price', 'N/A')}")
        print(f"Created:       {result['created_at']}")
        print("=" * 60)
    
    asyncio.run(run())

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ArbitrageBotExecutor',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()

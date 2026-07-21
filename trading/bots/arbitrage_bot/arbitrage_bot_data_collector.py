"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Data Collector
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Collecteur de données pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import json
import csv
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from collections import deque
import threading
import queue

# Imports internes
from .core.exchange_manager import ExchangeManager
from .core.market_data import MarketData
from .core.data_manager import DataManager
from .core.cache_manager import CacheManager
from .config import ConfigLoader

from .utils import (
    async_retry,
    async_timeout,
    get_queue_manager,
    get_cache_manager,
)

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# DATA COLLECTOR
# ============================================================

class ArbitrageBotDataCollector:
    """
    Collecteur de données pour le bot d'arbitrage
    
    Collecte, stocke et gère les données de marché
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        data_dir: Optional[str] = None,
        collect_tickers: bool = True,
        collect_order_books: bool = True,
        collect_candles: bool = True,
        collect_trades: bool = True,
        collect_opportunities: bool = True,
        max_queue_size: int = 10000,
        flush_interval: int = 60,
        batch_size: int = 1000
    ):
        """
        Initialise le collecteur de données
        
        Args:
            config_path: Chemin de la configuration
            data_dir: Répertoire des données
            collect_tickers: Collecter les tickers
            collect_order_books: Collecter les carnets d'ordres
            collect_candles: Collecter les bougies
            collect_trades: Collecter les trades
            collect_opportunities: Collecter les opportunités
            max_queue_size: Taille maximale de la file d'attente
            flush_interval: Intervalle de vidage en secondes
            batch_size: Taille des lots
        """
        self.config_path = config_path or "config/arbitrage_config.yaml"
        self.data_dir = Path(data_dir) if data_dir else Path("data/collected")
        
        self.collect_tickers = collect_tickers
        self.collect_order_books = collect_order_books
        self.collect_candles = collect_candles
        self.collect_trades = collect_trades
        self.collect_opportunities = collect_opportunities
        
        self.max_queue_size = max_queue_size
        self.flush_interval = flush_interval
        self.batch_size = batch_size
        
        # Créer les répertoires
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "tickers").mkdir(exist_ok=True)
        (self.data_dir / "order_books").mkdir(exist_ok=True)
        (self.data_dir / "candles").mkdir(exist_ok=True)
        (self.data_dir / "trades").mkdir(exist_ok=True)
        (self.data_dir / "opportunities").mkdir(exist_ok=True)
        
        # Configuration
        self.config = None
        self._load_config()
        
        # Composants
        self._init_components()
        
        # Files d'attente
        self.queues = {
            'tickers': queue.Queue(maxsize=max_queue_size),
            'order_books': queue.Queue(maxsize=max_queue_size),
            'candles': queue.Queue(maxsize=max_queue_size),
            'trades': queue.Queue(maxsize=max_queue_size),
            'opportunities': queue.Queue(maxsize=max_queue_size),
        }
        
        # État
        self._running = False
        self._collecting = False
        self._flush_thread = None
        self._stats = {
            'collected_tickers': 0,
            'collected_order_books': 0,
            'collected_candles': 0,
            'collected_trades': 0,
            'collected_opportunities': 0,
            'queue_sizes': {},
            'start_time': None,
            'last_flush': None,
        }
        
        logger.info("DataCollector initialized")
    
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
            'market_data': MarketData(self.config),
            'data_manager': DataManager(),
            'cache_manager': get_cache_manager(),
            'queue_manager': get_queue_manager(),
        }
        
        # Connecter les exchanges
        self.components['exchange_manager'].connect_all()
        
        logger.info("Components initialized")
    
    # ============================================================
    # COLLECTION METHODS
    # ============================================================
    
    def start(self):
        """Démarre la collecte"""
        if self._running:
            logger.warning("Data collector already running")
            return
        
        self._running = True
        self._collecting = True
        self._stats['start_time'] = datetime.now()
        
        # Démarrer le thread de vidage
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        
        # Démarrer les collecteurs
        logger.info("Data collector started")
    
    def stop(self):
        """Arrête la collecte"""
        if not self._running:
            logger.warning("Data collector not running")
            return
        
        self._running = False
        self._collecting = False
        
        # Vider les files
        self._flush_all()
        
        logger.info("Data collector stopped")
    
    def _flush_loop(self):
        """Boucle de vidage"""
        while self._running:
            try:
                time.sleep(self.flush_interval)
                self._flush_all()
            except Exception as e:
                logger.error(f"Flush loop error: {e}")
    
    def _flush_all(self):
        """Vide toutes les files d'attente"""
        for data_type, q in self.queues.items():
            self._flush_queue(data_type, q)
        
        self._stats['last_flush'] = datetime.now()
    
    def _flush_queue(self, data_type: str, q: queue.Queue):
        """
        Vide une file d'attente
        
        Args:
            data_type: Type de données
            q: File d'attente
        """
        if q.empty():
            return
        
        items = []
        try:
            while not q.empty() and len(items) < self.batch_size:
                items.append(q.get_nowait())
                q.task_done()
        except queue.Empty:
            pass
        
        if items:
            self._save_items(data_type, items)
            self._stats['queue_sizes'][data_type] = q.qsize()
    
    def _save_items(self, data_type: str, items: List[Dict[str, Any]]):
        """
        Sauvegarde des données
        
        Args:
            data_type: Type de données
            items: Données à sauvegarder
        """
        if not items:
            return
        
        try:
            # Format date pour le nom de fichier
            date_str = datetime.now().strftime("%Y%m%d")
            filename = self.data_dir / data_type / f"{date_str}.csv"
            
            # Convertir en DataFrame
            df = pd.DataFrame(items)
            
            # Ajouter des métadonnées
            df['collected_at'] = datetime.now().isoformat()
            
            # Sauvegarder
            if filename.exists():
                # Ajouter au fichier existant
                existing = pd.read_csv(filename)
                df = pd.concat([existing, df], ignore_index=True)
                df.drop_duplicates(subset=['timestamp', 'symbol'], keep='last', inplace=True)
            
            df.to_csv(filename, index=False)
            
            # Mettre à jour les statistiques
            stat_key = f"collected_{data_type}"
            self._stats[stat_key] = self._stats.get(stat_key, 0) + len(items)
            
            logger.debug(f"Saved {len(items)} {data_type} to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save {data_type}: {e}")
    
    # ============================================================
    # COLLECTION FUNCTIONS
    # ============================================================
    
    async def collect_ticker(self, exchange: str, symbol: str):
        """
        Collecte un ticker
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole
        """
        if not self._collecting:
            return
        
        try:
            # Récupérer les données
            exchange_obj = self.components['exchange_manager'].get_exchange(exchange)
            if not exchange_obj:
                logger.warning(f"Exchange not found: {exchange}")
                return
            
            ticker = await exchange_obj.async_get_ticker(symbol)
            if not ticker:
                return
            
            # Ajouter à la file d'attente
            ticker_data = {
                'timestamp': datetime.now().isoformat(),
                'exchange': exchange,
                'symbol': symbol,
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'last': ticker.get('last', 0),
                'volume': ticker.get('volume', 0),
                'high': ticker.get('high', 0),
                'low': ticker.get('low', 0),
                'change': ticker.get('change', 0),
                'change_percent': ticker.get('change_percent', 0),
            }
            
            try:
                self.queues['tickers'].put_nowait(ticker_data)
            except queue.Full:
                logger.warning(f"Tickers queue full, dropping data")
            
        except Exception as e:
            logger.error(f"Failed to collect ticker {exchange} {symbol}: {e}")
    
    async def collect_order_book(self, exchange: str, symbol: str, depth: int = 10):
        """
        Collecte un carnet d'ordres
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole
            depth: Profondeur
        """
        if not self._collecting:
            return
        
        try:
            # Récupérer les données
            exchange_obj = self.components['exchange_manager'].get_exchange(exchange)
            if not exchange_obj:
                logger.warning(f"Exchange not found: {exchange}")
                return
            
            order_book = await exchange_obj.async_get_order_book(symbol, depth)
            if not order_book:
                return
            
            # Ajouter à la file d'attente
            order_book_data = {
                'timestamp': datetime.now().isoformat(),
                'exchange': exchange,
                'symbol': symbol,
                'bids': json.dumps(order_book.get('bids', [])[:depth]),
                'asks': json.dumps(order_book.get('asks', [])[:depth]),
                'depth': depth,
            }
            
            try:
                self.queues['order_books'].put_nowait(order_book_data)
            except queue.Full:
                logger.warning(f"Order books queue full, dropping data")
            
        except Exception as e:
            logger.error(f"Failed to collect order book {exchange} {symbol}: {e}")
    
    async def collect_candle(
        self,
        exchange: str,
        symbol: str,
        interval: str = "1m",
        limit: int = 100
    ):
        """
        Collecte des bougies
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole
            interval: Intervalle
            limit: Nombre de bougies
        """
        if not self._collecting:
            return
        
        try:
            # Récupérer les données
            exchange_obj = self.components['exchange_manager'].get_exchange(exchange)
            if not exchange_obj:
                logger.warning(f"Exchange not found: {exchange}")
                return
            
            candles = await exchange_obj.async_get_klines(symbol, interval, limit)
            if not candles:
                return
            
            for candle in candles:
                candle_data = {
                    'timestamp': datetime.fromtimestamp(candle[0]/1000).isoformat(),
                    'exchange': exchange,
                    'symbol': symbol,
                    'interval': interval,
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'volume': candle[5],
                    'collected_at': datetime.now().isoformat(),
                }
                
                try:
                    self.queues['candles'].put_nowait(candle_data)
                except queue.Full:
                    logger.warning(f"Candles queue full, dropping data")
                    break
            
        except Exception as e:
            logger.error(f"Failed to collect candles {exchange} {symbol}: {e}")
    
    async def collect_trades(self, exchange: str, symbol: str, limit: int = 100):
        """
        Collecte des trades
        
        Args:
            exchange: Nom de l'exchange
            symbol: Symbole
            limit: Nombre de trades
        """
        if not self._collecting:
            return
        
        try:
            # Récupérer les données
            exchange_obj = self.components['exchange_manager'].get_exchange(exchange)
            if not exchange_obj:
                logger.warning(f"Exchange not found: {exchange}")
                return
            
            trades = await exchange_obj.async_get_trades(symbol, limit)
            if not trades:
                return
            
            for trade in trades:
                trade_data = {
                    'timestamp': datetime.fromtimestamp(trade[0]/1000).isoformat(),
                    'exchange': exchange,
                    'symbol': symbol,
                    'price': trade[1],
                    'quantity': trade[2],
                    'side': 'BUY' if trade[3] else 'SELL',
                    'collected_at': datetime.now().isoformat(),
                }
                
                try:
                    self.queues['trades'].put_nowait(trade_data)
                except queue.Full:
                    logger.warning(f"Trades queue full, dropping data")
                    break
            
        except Exception as e:
            logger.error(f"Failed to collect trades {exchange} {symbol}: {e}")
    
    def collect_opportunity(self, opportunity: Dict[str, Any]):
        """
        Collecte une opportunité d'arbitrage
        
        Args:
            opportunity: Données de l'opportunité
        """
        if not self._collecting:
            return
        
        try:
            opportunity_data = {
                'timestamp': datetime.now().isoformat(),
                'symbol': opportunity.get('symbol', ''),
                'exchange_a': opportunity.get('exchange_a', ''),
                'exchange_b': opportunity.get('exchange_b', ''),
                'price_a': opportunity.get('price_a', 0),
                'price_b': opportunity.get('price_b', 0),
                'spread': opportunity.get('spread', 0),
                'profit': opportunity.get('profit', 0),
                'profit_percent': opportunity.get('profit_percent', 0),
                'volume': opportunity.get('volume', 0),
                'executed': opportunity.get('executed', False),
                'collected_at': datetime.now().isoformat(),
            }
            
            try:
                self.queues['opportunities'].put_nowait(opportunity_data)
            except queue.Full:
                logger.warning(f"Opportunities queue full, dropping data")
            
        except Exception as e:
            logger.error(f"Failed to collect opportunity: {e}")
    
    # ============================================================
    # BATCH COLLECTION
    # ============================================================
    
    async def collect_all(
        self,
        exchanges: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None
    ):
        """
        Collecte toutes les données
        
        Args:
            exchanges: Liste des exchanges
            symbols: Liste des symboles
        """
        if not self._collecting:
            return
        
        exchanges = exchanges or ["binance", "bybit", "coinbase"]
        symbols = symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOT/USDT"]
        
        tasks = []
        
        for exchange in exchanges:
            for symbol in symbols:
                if self.collect_tickers:
                    tasks.append(self.collect_ticker(exchange, symbol))
                
                if self.collect_order_books:
                    tasks.append(self.collect_order_book(exchange, symbol))
                
                if self.collect_candles:
                    tasks.append(self.collect_candle(exchange, symbol))
                
                if self.collect_trades:
                    tasks.append(self.collect_trades(exchange, symbol))
        
        # Exécuter en parallèle
        await asyncio.gather(*tasks)
    
    # ============================================================
    # DATA EXPORT
    # ============================================================
    
    def export_data(
        self,
        data_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        format: str = 'csv'
    ) -> Path:
        """
        Exporte les données collectées
        
        Args:
            data_type: Type de données
            start_date: Date de début
            end_date: Date de fin
            format: Format d'export
            
        Returns:
            Path: Chemin du fichier exporté
        """
        data_dir = self.data_dir / data_type
        
        if not data_dir.exists():
            logger.warning(f"No data found for {data_type}")
            return None
        
        # Lire tous les fichiers
        dfs = []
        for file_path in data_dir.glob("*.csv"):
            try:
                df = pd.read_csv(file_path)
                dfs.append(df)
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
        
        if not dfs:
            logger.warning(f"No data found for {data_type}")
            return None
        
        # Combiner les données
        df = pd.concat(dfs, ignore_index=True)
        df.drop_duplicates(subset=['timestamp', 'symbol'], keep='last', inplace=True)
        
        # Filtrer par date
        if start_date:
            df = df[df['timestamp'] >= start_date]
        if end_date:
            df = df[df['timestamp'] <= end_date]
        
        # Exporter
        export_dir = self.data_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        
        filename = f"{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if format == 'csv':
            file_path = export_dir / f"{filename}.csv"
            df.to_csv(file_path, index=False)
        elif format == 'json':
            file_path = export_dir / f"{filename}.json"
            df.to_json(file_path, orient='records', indent=2)
        elif format == 'parquet':
            file_path = export_dir / f"{filename}.parquet"
            df.to_parquet(file_path)
        else:
            file_path = export_dir / f"{filename}.csv"
            df.to_csv(file_path, index=False)
        
        logger.info(f"Exported {len(df)} records to {file_path}")
        return file_path
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        queue_sizes = {
            name: q.qsize()
            for name, q in self.queues.items()
        }
        
        return {
            'running': self._running,
            'collecting': self._collecting,
            'start_time': self._stats.get('start_time'),
            'last_flush': self._stats.get('last_flush'),
            'queues': queue_sizes,
            'collected': {
                'tickers': self._stats.get('collected_tickers', 0),
                'order_books': self._stats.get('collected_order_books', 0),
                'candles': self._stats.get('collected_candles', 0),
                'trades': self._stats.get('collected_trades', 0),
                'opportunities': self._stats.get('collected_opportunities', 0),
            },
            'data_dir': str(self.data_dir),
            'data_size': sum(f.stat().st_size for f in self.data_dir.rglob('*') if f.is_file()) / (1024 * 1024),  # MB
        }

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot Data Collector")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default="config/arbitrage_config.yaml"
    )
    parser.add_argument(
        "-d", "--data-dir",
        help="Data directory",
        default="data/collected"
    )
    parser.add_argument(
        "-e", "--exchanges",
        help="Exchanges to collect from",
        nargs="+",
        default=["binance", "bybit", "coinbase"]
    )
    parser.add_argument(
        "-s", "--symbols",
        help="Symbols to collect",
        nargs="+",
        default=["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    )
    parser.add_argument(
        "-i", "--interval",
        help="Collection interval in seconds",
        type=int,
        default=60
    )
    parser.add_argument(
        "--no-tickers",
        help="Disable ticker collection",
        action="store_true"
    )
    parser.add_argument(
        "--no-order-books",
        help="Disable order book collection",
        action="store_true"
    )
    parser.add_argument(
        "--no-candles",
        help="Disable candle collection",
        action="store_true"
    )
    parser.add_argument(
        "--no-trades",
        help="Disable trade collection",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Créer le collecteur
    collector = ArbitrageBotDataCollector(
        config_path=args.config,
        data_dir=args.data_dir,
        collect_tickers=not args.no_tickers,
        collect_order_books=not args.no_order_books,
        collect_candles=not args.no_candles,
        collect_trades=not args.no_trades,
    )
    
    # Démarrer la collecte
    collector.start()
    
    # Exécuter la collecte
    asyncio.run(collector.collect_all(args.exchanges, args.symbols))
    
    # Afficher les statistiques
    stats = collector.get_stats()
    print("\n" + "=" * 60)
    print("DATA COLLECTOR STATISTICS")
    print("=" * 60)
    print(f"Running:           {stats['running']}")
    print(f"Collecting:        {stats['collecting']}")
    print(f"Start Time:        {stats['start_time']}")
    print(f"Data Directory:    {stats['data_dir']}")
    print(f"Data Size:         {stats['data_size']:.2f} MB")
    print("\nCollected:")
    for key, value in stats['collected'].items():
        print(f"  {key}: {value}")
    print("\nQueue Sizes:")
    for key, value in stats['queues'].items():
        print(f"  {key}: {value}")
    print("=" * 60)
    
    # Garder le collecteur actif
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    collector.stop()

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ArbitrageBotDataCollector',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()

"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Detector
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Détecteur d'opportunités d'arbitrage pour le bot
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from collections import defaultdict
import json

# Imports internes
from .core.exchange_manager import ExchangeManager
from .core.market_data import MarketData
from .core.data_manager import DataManager
from .core.cache_manager import CacheManager

from .utils import (
    async_retry,
    async_timeout,
    get_cache_manager,
    StatisticsUtils,
)

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# DETECTOR
# ============================================================

class ArbitrageBotDetector:
    """
    Détecteur d'opportunités d'arbitrage
    
    Détecte les opportunités d'arbitrage cross-exchange, triangulaire,
    statistique, et flash loan
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        min_profit_percent: float = 0.001,
        min_volume: float = 100,
        max_spread: float = 0.02,
        lookback_period: int = 100,
        z_score_threshold: float = 2.0,
        cointegration_confidence: float = 0.95
    ):
        """
        Initialise le détecteur
        
        Args:
            config_path: Chemin de la configuration
            min_profit_percent: Profit minimum en pourcentage
            min_volume: Volume minimum
            max_spread: Spread maximum
            lookback_period: Période de lookback
            z_score_threshold: Seuil de z-score
            cointegration_confidence: Confiance de cointégration
        """
        self.config_path = config_path or "config/arbitrage_config.yaml"
        self.min_profit_percent = min_profit_percent
        self.min_volume = min_volume
        self.max_spread = max_spread
        self.lookback_period = lookback_period
        self.z_score_threshold = z_score_threshold
        self.cointegration_confidence = cointegration_confidence
        
        # Configuration
        self.config = None
        self._load_config()
        
        # Composants
        self._init_components()
        
        # Cache
        self.cache = get_cache_manager()
        
        # Données
        self.prices: Dict[str, Dict[str, float]] = {}
        self.order_books: Dict[str, Dict[str, Any]] = {}
        self.tickers: Dict[str, Dict[str, Any]] = {}
        self.historical_prices: Dict[str, List[float]] = defaultdict(list)
        
        # Opportunités
        self.opportunities: List[Dict[str, Any]] = []
        self.executed_opportunities: List[Dict[str, Any]] = []
        
        # Statistiques
        self.stats = {
            'total_opportunities': 0,
            'cross_exchange': 0,
            'triangular': 0,
            'statistical': 0,
            'flash_loan': 0,
            'cross_chain': 0,
            'executed': 0,
            'failed': 0,
        }
        
        logger.info("Detector initialized")
    
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
        }
        
        logger.info("Components initialized")
    
    # ============================================================
    # DATA UPDATE
    # ============================================================
    
    async def update_data(self):
        """Met à jour les données de marché"""
        # Récupérer les tickers
        for exchange in self.components['exchange_manager'].get_exchanges():
            exchange_name = exchange.name
            self.tickers[exchange_name] = {}
            
            for symbol in exchange.get_symbols():
                ticker = await exchange.async_get_ticker(symbol)
                if ticker:
                    self.tickers[exchange_name][symbol] = ticker
                    self.prices[exchange_name] = self.prices.get(exchange_name, {})
                    self.prices[exchange_name][symbol] = ticker.get('last', 0)
                    
                    # Mettre à jour l'historique
                    self.historical_prices[f"{exchange_name}:{symbol}"].append(ticker.get('last', 0))
                    if len(self.historical_prices[f"{exchange_name}:{symbol}"]) > self.lookback_period * 2:
                        self.historical_prices[f"{exchange_name}:{symbol}"].pop(0)
        
        # Récupérer les carnets d'ordres
        for exchange in self.components['exchange_manager'].get_exchanges():
            exchange_name = exchange.name
            self.order_books[exchange_name] = {}
            
            for symbol in exchange.get_symbols()[:5]:  # Limiter pour la performance
                order_book = await exchange.async_get_order_book(symbol, 10)
                if order_book:
                    self.order_books[exchange_name][symbol] = order_book
        
        logger.debug("Data updated")
    
    # ============================================================
    # CROSS-EXCHANGE ARBITRAGE
    # ============================================================
    
    async def detect_cross_exchange_opportunities(self) -> List[Dict[str, Any]]:
        """
        Détecte les opportunités cross-exchange
        
        Returns:
            List[Dict[str, Any]]: Opportunités détectées
        """
        opportunities = []
        
        # Parcourir les symboles
        symbols = set()
        for exchange_prices in self.prices.values():
            symbols.update(exchange_prices.keys())
        
        for symbol in symbols:
            # Récupérer les prix par exchange
            exchange_prices = {}
            for exchange, prices in self.prices.items():
                if symbol in prices:
                    exchange_prices[exchange] = prices[symbol]
            
            if len(exchange_prices) < 2:
                continue
            
            # Trouver le meilleur prix d'achat et de vente
            min_price = min(exchange_prices.values())
            max_price = max(exchange_prices.values())
            
            if max_price <= min_price:
                continue
            
            # Calculer le spread
            spread = max_price - min_price
            spread_percent = spread / min_price
            
            # Vérifier les conditions
            if spread_percent < self.min_profit_percent:
                continue
            
            # Vérifier le volume
            volume = await self._get_volume(symbol)
            if volume < self.min_volume:
                continue
            
            # Vérifier le spread maximum
            if spread_percent > self.max_spread:
                continue
            
            # Créer l'opportunité
            buy_exchange = min(exchange_prices, key=exchange_prices.get)
            sell_exchange = max(exchange_prices, key=exchange_prices.get)
            
            opportunity = {
                'type': 'cross_exchange',
                'symbol': symbol,
                'buy_exchange': buy_exchange,
                'sell_exchange': sell_exchange,
                'buy_price': exchange_prices[buy_exchange],
                'sell_price': exchange_prices[sell_exchange],
                'spread': spread,
                'spread_percent': spread_percent,
                'profit_percent': spread_percent * 0.95,  # 5% de frais
                'volume': volume,
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',
            }
            
            opportunities.append(opportunity)
            self.stats['cross_exchange'] += 1
        
        return opportunities
    
    async def _get_volume(self, symbol: str) -> float:
        """Récupère le volume d'un symbole"""
        total_volume = 0
        
        for exchange, tickers in self.tickers.items():
            if symbol in tickers:
                total_volume += tickers[symbol].get('volume', 0)
        
        return total_volume
    
    # ============================================================
    # TRIANGULAR ARBITRAGE
    # ============================================================
    
    async def detect_triangular_opportunities(self) -> List[Dict[str, Any]]:
        """
        Détecte les opportunités triangulaires
        
        Returns:
            List[Dict[str, Any]]: Opportunités détectées
        """
        opportunities = []
        
        # Cycles triangulaires
        cycles = [
            ['BTC/USDT', 'ETH/BTC', 'ETH/USDT'],
            ['SOL/USDT', 'BTC/SOL', 'BTC/USDT'],
            ['ADA/USDT', 'BTC/ADA', 'BTC/USDT'],
            ['DOT/USDT', 'ETH/DOT', 'ETH/USDT'],
        ]
        
        for exchange, prices in self.prices.items():
            for cycle in cycles:
                try:
                    # Vérifier que toutes les paires sont disponibles
                    if not all(pair in prices for pair in cycle):
                        continue
                    
                    # Calculer le profit
                    rate1 = prices[cycle[0]]
                    rate2 = prices[cycle[1]]
                    rate3 = prices[cycle[2]]
                    
                    # Acheter, convertir, vendre
                    profit = (1 / rate1) * rate2 * rate3 - 1
                    
                    if profit > self.min_profit_percent:
                        opportunity = {
                            'type': 'triangular',
                            'exchange': exchange,
                            'cycle': cycle,
                            'rates': [rate1, rate2, rate3],
                            'profit_percent': profit,
                            'timestamp': datetime.now().isoformat(),
                            'status': 'pending',
                        }
                        
                        opportunities.append(opportunity)
                        self.stats['triangular'] += 1
                        
                except Exception as e:
                    logger.debug(f"Triangular calculation error: {e}")
        
        return opportunities
    
    # ============================================================
    # STATISTICAL ARBITRAGE
    # ============================================================
    
    async def detect_statistical_opportunities(self) -> List[Dict[str, Any]]:
        """
        Détecte les opportunités statistiques
        
        Returns:
            List[Dict[str, Any]]: Opportunités détectées
        """
        opportunities = []
        
        # Paires corrélées
        pairs = [
            ('BTC/USDT', 'ETH/USDT'),
            ('SOL/USDT', 'ADA/USDT'),
            ('DOT/USDT', 'AVAX/USDT'),
            ('MATIC/USDT', 'LINK/USDT'),
        ]
        
        for exchange, prices in self.prices.items():
            for pair1, pair2 in pairs:
                if pair1 not in prices or pair2 not in prices:
                    continue
                
                # Récupérer l'historique
                key1 = f"{exchange}:{pair1}"
                key2 = f"{exchange}:{pair2}"
                
                prices1 = self.historical_prices[key1][-self.lookback_period:]
                prices2 = self.historical_prices[key2][-self.lookback_period:]
                
                if len(prices1) < self.lookback_period or len(prices2) < self.lookback_period:
                    continue
                
                # Calculer le spread
                spread = [p1 - p2 for p1, p2 in zip(prices1, prices2)]
                mean_spread = np.mean(spread)
                std_spread = np.std(spread)
                
                if std_spread == 0:
                    continue
                
                # Calculer le z-score actuel
                current_spread = prices[pair1] - prices[pair2]
                z_score = (current_spread - mean_spread) / std_spread
                
                # Vérifier le seuil
                if abs(z_score) < self.z_score_threshold:
                    continue
                
                # Créer l'opportunité
                opportunity = {
                    'type': 'statistical',
                    'exchange': exchange,
                    'pair1': pair1,
                    'pair2': pair2,
                    'current_spread': current_spread,
                    'mean_spread': mean_spread,
                    'std_spread': std_spread,
                    'z_score': z_score,
                    'threshold': self.z_score_threshold,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'pending',
                }
                
                opportunities.append(opportunity)
                self.stats['statistical'] += 1
        
        return opportunities
    
    # ============================================================
    # FLASH LOAN ARBITRAGE
    # ============================================================
    
    async def detect_flash_loan_opportunities(self) -> List[Dict[str, Any]]:
        """
        Détecte les opportunités de flash loan
        
        Returns:
            List[Dict[str, Any]]: Opportunités détectées
        """
        opportunities = []
        
        # Paires DEX
        dex_pairs = [
            ('WETH/USDT', 'Uniswap', 'Sushiswap'),
            ('WBTC/USDT', 'Uniswap', 'Curve'),
            ('USDC/USDT', 'Curve', 'Balancer'),
        ]
        
        for pair, dex1, dex2 in dex_pairs:
            # Simuler les prix DEX
            price1 = await self._get_dex_price(pair, dex1)
            price2 = await self._get_dex_price(pair, dex2)
            
            if price1 is None or price2 is None:
                continue
            
            spread = abs(price1 - price2)
            spread_percent = spread / min(price1, price2)
            
            if spread_percent > self.min_profit_percent:
                opportunity = {
                    'type': 'flash_loan',
                    'pair': pair,
                    'dex1': dex1,
                    'dex2': dex2,
                    'price1': price1,
                    'price2': price2,
                    'spread': spread,
                    'spread_percent': spread_percent,
                    'profit_percent': spread_percent * 0.9,  # 10% de gas
                    'timestamp': datetime.now().isoformat(),
                    'status': 'pending',
                }
                
                opportunities.append(opportunity)
                self.stats['flash_loan'] += 1
        
        return opportunities
    
    async def _get_dex_price(self, pair: str, dex: str) -> Optional[float]:
        """Récupère le prix d'un DEX"""
        # Simuler les prix DEX
        # En production, interroger les DEX via leurs APIs
        base_prices = {
            'WETH/USDT': 3000.0,
            'WBTC/USDT': 45000.0,
            'USDC/USDT': 1.0,
        }
        
        base_price = base_prices.get(pair, 0)
        if base_price == 0:
            return None
        
        # Ajouter une variation aléatoire
        variation = np.random.normal(0, 0.001)
        return base_price * (1 + variation)
    
    # ============================================================
    # CROSS-CHAIN ARBITRAGE
    # ============================================================
    
    async def detect_cross_chain_opportunities(self) -> List[Dict[str, Any]]:
        """
        Détecte les opportunités cross-chain
        
        Returns:
            List[Dict[str, Any]]: Opportunités détectées
        """
        opportunities = []
        
        # Paires cross-chain
        cross_pairs = [
            ('ETH-USDC', 'Ethereum', 'Polygon'),
            ('USDC-USDT', 'Ethereum', 'BSC'),
            ('DAI-USDC', 'Ethereum', 'Arbitrum'),
        ]
        
        for pair, chain1, chain2 in cross_pairs:
            # Simuler les prix cross-chain
            price1 = await self._get_cross_chain_price(pair, chain1)
            price2 = await self._get_cross_chain_price(pair, chain2)
            
            if price1 is None or price2 is None:
                continue
            
            spread = abs(price1 - price2)
            spread_percent = spread / min(price1, price2)
            
            if spread_percent > self.min_profit_percent:
                opportunity = {
                    'type': 'cross_chain',
                    'pair': pair,
                    'chain1': chain1,
                    'chain2': chain2,
                    'price1': price1,
                    'price2': price2,
                    'spread': spread,
                    'spread_percent': spread_percent,
                    'profit_percent': spread_percent * 0.85,  # 15% de frais de bridge
                    'timestamp': datetime.now().isoformat(),
                    'status': 'pending',
                }
                
                opportunities.append(opportunity)
                self.stats['cross_chain'] += 1
        
        return opportunities
    
    async def _get_cross_chain_price(self, pair: str, chain: str) -> Optional[float]:
        """Récupère le prix cross-chain"""
        # Simuler les prix cross-chain
        # En production, interroger les prix via des oracles ou APIs
        base_prices = {
            'ETH-USDC': 3000.0,
            'USDC-USDT': 1.0,
            'DAI-USDC': 1.0,
        }
        
        base_price = base_prices.get(pair, 0)
        if base_price == 0:
            return None
        
        # Ajouter une variation aléatoire
        variation = np.random.normal(0, 0.002)
        return base_price * (1 + variation)
    
    # ============================================================
    # OPPORTUNITY EXECUTION
    # ============================================================
    
    async def execute_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """
        Exécute une opportunité d'arbitrage
        
        Args:
            opportunity: Opportunité à exécuter
            
        Returns:
            bool: True si exécuté
        """
        try:
            logger.info(f"Executing {opportunity['type']} opportunity: {opportunity}")
            
            # Simuler l'exécution
            success = np.random.random() > 0.1  # 90% de succès
            
            if success:
                opportunity['status'] = 'executed'
                opportunity['executed_at'] = datetime.now().isoformat()
                self.executed_opportunities.append(opportunity)
                self.stats['executed'] += 1
                logger.info(f"Opportunity executed successfully")
                return True
            else:
                opportunity['status'] = 'failed'
                opportunity['error'] = 'Execution failed'
                self.stats['failed'] += 1
                logger.warning(f"Opportunity execution failed")
                return False
            
        except Exception as e:
            opportunity['status'] = 'failed'
            opportunity['error'] = str(e)
            self.stats['failed'] += 1
            logger.error(f"Opportunity execution error: {e}")
            return False
    
    # ============================================================
    # MAIN DETECTION
    # ============================================================
    
    async def detect_opportunities(self) -> List[Dict[str, Any]]:
        """
        Détecte toutes les opportunités
        
        Returns:
            List[Dict[str, Any]]: Opportunités détectées
        """
        # Mettre à jour les données
        await self.update_data()
        
        # Détecter les opportunités
        opportunities = []
        
        # Cross-exchange
        cross_exchange = await self.detect_cross_exchange_opportunities()
        opportunities.extend(cross_exchange)
        
        # Triangulaire
        triangular = await self.detect_triangular_opportunities()
        opportunities.extend(triangular)
        
        # Statistique
        statistical = await self.detect_statistical_opportunities()
        opportunities.extend(statistical)
        
        # Flash loan
        flash_loan = await self.detect_flash_loan_opportunities()
        opportunities.extend(flash_loan)
        
        # Cross-chain
        cross_chain = await self.detect_cross_chain_opportunities()
        opportunities.extend(cross_chain)
        
        # Filtrer et trier
        opportunities = self._filter_opportunities(opportunities)
        opportunities = self._sort_opportunities(opportunities)
        
        # Mettre à jour les statistiques
        self.stats['total_opportunities'] = len(opportunities)
        self.opportunities = opportunities
        
        return opportunities
    
    def _filter_opportunities(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtre les opportunités
        
        Args:
            opportunities: Opportunités à filtrer
            
        Returns:
            List[Dict[str, Any]]: Opportunités filtrées
        """
        filtered = []
        
        for opp in opportunities:
            # Vérifier le profit minimum
            if opp.get('profit_percent', 0) < self.min_profit_percent:
                continue
            
            # Vérifier le volume
            if opp.get('volume', 0) < self.min_volume:
                continue
            
            # Vérifier le spread maximum
            if opp.get('spread_percent', 0) > self.max_spread:
                continue
            
            filtered.append(opp)
        
        return filtered
    
    def _sort_opportunities(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Trie les opportunités par profit
        
        Args:
            opportunities: Opportunités à trier
            
        Returns:
            List[Dict[str, Any]]: Opportunités triées
        """
        return sorted(
            opportunities,
            key=lambda x: x.get('profit_percent', 0),
            reverse=True
        )
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'total_opportunities': self.stats['total_opportunities'],
            'by_type': {
                'cross_exchange': self.stats['cross_exchange'],
                'triangular': self.stats['triangular'],
                'statistical': self.stats['statistical'],
                'flash_loan': self.stats['flash_loan'],
                'cross_chain': self.stats['cross_chain'],
            },
            'executed': self.stats['executed'],
            'failed': self.stats['failed'],
            'success_rate': self.stats['executed'] / (self.stats['executed'] + self.stats['failed']) if (self.stats['executed'] + self.stats['failed']) > 0 else 0,
            'latest_opportunities': self.opportunities[:10],
        }

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot Detector")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default="config/arbitrage_config.yaml"
    )
    parser.add_argument(
        "-m", "--min-profit",
        help="Minimum profit percentage",
        type=float,
        default=0.001
    )
    parser.add_argument(
        "-v", "--min-volume",
        help="Minimum volume",
        type=float,
        default=100
    )
    parser.add_argument(
        "-s", "--max-spread",
        help="Maximum spread",
        type=float,
        default=0.02
    )
    parser.add_argument(
        "--interval",
        help="Detection interval in seconds",
        type=int,
        default=5
    )
    
    args = parser.parse_args()
    
    # Créer le détecteur
    detector = ArbitrageBotDetector(
        config_path=args.config,
        min_profit_percent=args.min_profit,
        min_volume=args.min_volume,
        max_spread=args.max_spread
    )
    
    # Exécuter la détection
    async def run():
        while True:
            try:
                opportunities = await detector.detect_opportunities()
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Detected {len(opportunities)} opportunities")
                
                for opp in opportunities[:5]:
                    print(f"  {opp['type']}: {opp.get('symbol', opp.get('pair', 'N/A'))} - {opp.get('profit_percent', 0)*100:.2f}%")
                
                if opportunities:
                    # Exécuter la meilleure opportunité
                    best = opportunities[0]
                    print(f"\nExecuting best opportunity...")
                    await detector.execute_opportunity(best)
                
                await asyncio.sleep(args.interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Detection error: {e}")
                await asyncio.sleep(args.interval)
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopping detector...")
    
    # Afficher les statistiques
    stats = detector.get_stats()
    print("\n" + "=" * 60)
    print("DETECTOR STATISTICS")
    print("=" * 60)
    print(f"Total Opportunities:  {stats['total_opportunities']}")
    print(f"Executed:             {stats['executed']}")
    print(f"Failed:               {stats['failed']}")
    print(f"Success Rate:         {stats['success_rate']*100:.1f}%")
    print("\nBy Type:")
    for key, value in stats['by_type'].items():
        print(f"  {key}: {value}")
    print("=" * 60)

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ArbitrageBotDetector',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()

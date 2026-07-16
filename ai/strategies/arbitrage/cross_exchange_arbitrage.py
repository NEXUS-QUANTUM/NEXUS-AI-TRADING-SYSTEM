# ai/strategies/arbitrage/cross_exchange_arbitrage.py
"""
NEXUS AI TRADING SYSTEM - Cross-Exchange Arbitrage Strategy
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import websocket
    import threading
    import json
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ExchangePrice:
    """Prix sur un exchange"""
    exchange: str
    symbol: str
    bid: float
    ask: float
    timestamp: datetime
    volume: float = 0.0

    def spread(self) -> float:
        return self.ask - self.bid

    def mid_price(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass
class ArbitrageOpportunity:
    """Opportunit� d'arbitrage"""
    buy_exchange: str
    sell_exchange: str
    symbol: str
    buy_price: float
    sell_price: float
    spread: float
    spread_percent: float
    profit: float
    profit_percent: float
    timestamp: datetime
    volume: float = 0.0
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'buy_exchange': self.buy_exchange,
            'sell_exchange': self.sell_exchange,
            'symbol': self.symbol,
            'buy_price': self.buy_price,
            'sell_price': self.sell_price,
            'spread': self.spread,
            'spread_percent': self.spread_percent,
            'profit': self.profit,
            'profit_percent': self.profit_percent,
            'timestamp': self.timestamp.isoformat(),
            'volume': self.volume,
            'confidence': self.confidence,
        }


@dataclass
class CrossExchangeArbitrageConfig:
    """Configuration pour Cross-Exchange Arbitrage"""
    exchanges: List[str] = field(default_factory=lambda: ['binance', 'coinbase', 'kraken', 'bybit'])
    symbols: List[str] = field(default_factory=lambda: ['BTC-USD', 'ETH-USD', 'SOL-USD'])
    min_spread_percent: float = 0.1  # 0.1%
    max_position_size: float = 10000.0
    min_position_size: float = 100.0
    max_slippage: float = 0.001  # 0.1%
    fee_rate: float = 0.001  # 0.1%
    update_interval: float = 1.0  # secondes
    max_age: float = 5.0  # secondes
    use_websocket: bool = True
    risk_free_rate: float = 0.02
    max_exposure: float = 0.5
    min_confidence: float = 0.7
    execution_timeout: float = 10.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchanges': self.exchanges,
            'symbols': self.symbols,
            'min_spread_percent': self.min_spread_percent,
            'max_position_size': self.max_position_size,
            'min_position_size': self.min_position_size,
            'max_slippage': self.max_slippage,
            'fee_rate': self.fee_rate,
            'update_interval': self.update_interval,
            'max_age': self.max_age,
            'use_websocket': self.use_websocket,
            'risk_free_rate': self.risk_free_rate,
            'max_exposure': self.max_exposure,
            'min_confidence': self.min_confidence,
            'execution_timeout': self.execution_timeout,
        }


class CrossExchangeArbitrage:
    """
    Strat�gie d'arbitrage entre exchanges.

    Features:
    - Multi-exchange price monitoring
    - Real-time arbitrage detection
    - Automatic execution
    - Risk management
    - Performance tracking

    Example:
        ```python
        config = CrossExchangeArbitrageConfig(
            exchanges=['binance', 'coinbase'],
            symbols=['BTC-USD'],
            min_spread_percent=0.1
        )
        strategy = CrossExchangeArbitrage(config)

        # Start monitoring
        strategy.start()

        # Get opportunities
        opportunities = strategy.get_opportunities()
        ```
    """

    def __init__(self, config: Optional[CrossExchangeArbitrageConfig] = None):
        self.config = config or CrossExchangeArbitrageConfig()
        self.prices: Dict[str, Dict[str, ExchangePrice]] = {}
        self.opportunities: List[ArbitrageOpportunity] = []
        self.executed_trades: List[Dict[str, Any]] = []
        self.is_running = False
        self._thread = None
        self._lock = threading.Lock()

        # Initialisation des structures de prix
        for exchange in self.config.exchanges:
            self.prices[exchange] = {}

        logger.info(f"CrossExchangeArbitrage initialis�")

    def start(self):
        """D�marre la surveillance des prix"""
        if self.is_running:
            logger.warning("D�j� en cours d'ex�cution")
            return

        self.is_running = True

        if self.config.use_websocket and WEBSOCKET_AVAILABLE:
            self._start_websocket()
        else:
            self._start_polling()

        logger.info("Surveillance d�marr�e")

    def stop(self):
        """Arr�te la surveillance"""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Surveillance arr�t�e")

    def _start_websocket(self):
        """D�marre les WebSockets pour les prix en temps r�el"""
        # Impl�mentation simplifi�e
        # Dans la pratique, utiliser les WebSockets des exchanges
        def websocket_thread():
            while self.is_running:
                self._update_prices()
                self._detect_opportunities()
                time.sleep(self.config.update_interval)

        self._thread = threading.Thread(target=websocket_thread, daemon=True)
        self._thread.start()

    def _start_polling(self):
        """D�marre le polling des prix"""
        def polling_thread():
            while self.is_running:
                self._update_prices()
                self._detect_opportunities()
                time.sleep(self.config.update_interval)

        self._thread = threading.Thread(target=polling_thread, daemon=True)
        self._thread.start()

    def _update_prices(self):
        """Met � jour les prix depuis les exchanges"""
        # Simulation de prix
        for exchange in self.config.exchanges:
            for symbol in self.config.symbols:
                base_price = self._get_base_price(symbol)
                price = self._simulate_price(base_price, exchange)

                with self._lock:
                    self.prices[exchange][symbol] = ExchangePrice(
                        exchange=exchange,
                        symbol=symbol,
                        bid=price * 0.999,
                        ask=price * 1.001,
                        timestamp=datetime.now(),
                        volume=np.random.uniform(100, 1000),
                    )

    def _get_base_price(self, symbol: str) -> float:
        """Retourne le prix de base pour un symbole"""
        base_prices = {
            'BTC-USD': 50000.0,
            'ETH-USD': 3000.0,
            'SOL-USD': 100.0,
        }
        return base_prices.get(symbol, 1000.0)

    def _simulate_price(self, base_price: float, exchange: str) -> float:
        """Simule un prix pour un exchange"""
        # Variation al�atoire
        variation = np.random.normal(0, 0.001)
        # Biais sp�cifique � l'exchange
        exchange_biases = {
            'binance': 0.0005,
            'coinbase': -0.0003,
            'kraken': 0.0002,
            'bybit': -0.0004,
        }
        bias = exchange_biases.get(exchange, 0)

        return base_price * (1 + variation + bias)

    def _detect_opportunities(self):
        """D�tecte les opportunit�s d'arbitrage"""
        with self._lock:
            self.opportunities = []

            for symbol in self.config.symbols:
                # R�cup�ration des prix pour tous les exchanges
                symbol_prices = []
                for exchange in self.config.exchanges:
                    if symbol in self.prices[exchange]:
                        price = self.prices[exchange][symbol]
                        if (datetime.now() - price.timestamp).seconds < self.config.max_age:
                            symbol_prices.append(price)

                if len(symbol_prices) < 2:
                    continue

                # Recherche des meilleurs prix
                buy_price = min(symbol_prices, key=lambda x: x.ask)
                sell_price = max(symbol_prices, key=lambda x: x.bid)

                # Calcul du spread
                spread = sell_price.bid - buy_price.ask
                spread_percent = (spread / buy_price.ask) * 100

                # V�rification du seuil minimum
                if spread_percent >= self.config.min_spread_percent:
                    # Calcul du profit
                    volume = min(
                        self.config.max_position_size,
                        sell_price.volume,
                        buy_price.volume
                    )

                    if volume >= self.config.min_position_size:
                        # Frais
                        fee_buy = volume * self.config.fee_rate
                        fee_sell = volume * self.config.fee_rate

                        gross_profit = (sell_price.bid - buy_price.ask) * volume
                        net_profit = gross_profit - fee_buy - fee_sell

                        if net_profit > 0:
                            opportunity = ArbitrageOpportunity(
                                buy_exchange=buy_price.exchange,
                                sell_exchange=sell_price.exchange,
                                symbol=symbol,
                                buy_price=buy_price.ask,
                                sell_price=sell_price.bid,
                                spread=spread,
                                spread_percent=spread_percent,
                                profit=net_profit,
                                profit_percent=(net_profit / (buy_price.ask * volume)) * 100,
                                timestamp=datetime.now(),
                                volume=volume,
                                confidence=self._calculate_confidence(buy_price, sell_price),
                            )
                            self.opportunities.append(opportunity)

    def _calculate_confidence(self, buy_price: ExchangePrice, sell_price: ExchangePrice) -> float:
        """Calcule le niveau de confiance d'une opportunit�"""
        # Facteurs de confiance
        factors = []

        # 1. Fra�cheur des donn�es
        age = (datetime.now() - buy_price.timestamp).seconds
        factors.append(max(0, 1 - age / self.config.max_age))

        # 2. Liquidit�
        factors.append(min(1, buy_price.volume / 1000))
        factors.append(min(1, sell_price.volume / 1000))

        # 3. Profondeur du carnet
        # (simul�)
        factors.append(0.8)

        # Confiance moyenne
        confidence = np.mean(factors)

        return min(1, max(0, confidence))

    def get_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Retourne les opportunit�s d'arbitrage.

        Returns:
            List[ArbitrageOpportunity]: Opportunit�s
        """
        with self._lock:
            return self.opportunities.copy()

    def get_best_opportunity(self) -> Optional[ArbitrageOpportunity]:
        """
        Retourne la meilleure opportunit�.

        Returns:
            Optional[ArbitrageOpportunity]: Meilleure opportunit�
        """
        opportunities = self.get_opportunities()
        if not opportunities:
            return None

        # Filtrer par confiance
        valid = [o for o in opportunities if o.confidence >= self.config.min_confidence]
        if not valid:
            return None

        # Meilleur profit
        return max(valid, key=lambda x: x.profit)

    def execute(self, opportunity: ArbitrageOpportunity) -> Dict[str, Any]:
        """
        Ex�cute une opportunit� d'arbitrage.

        Args:
            opportunity: Opportunit� � ex�cuter

        Returns:
            Dict[str, Any]: R�sultat de l'ex�cution
        """
        if opportunity.confidence < self.config.min_confidence:
            return {'status': 'rejected', 'reason': 'low_confidence'}

        # Simulation d'ex�cution
        import time
        time.sleep(0.5)

        # V�rification des prix
        buy_price = self.prices[opportunity.buy_exchange].get(opportunity.symbol)
        sell_price = self.prices[opportunity.sell_exchange].get(opportunity.symbol)

        if not buy_price or not sell_price:
            return {'status': 'failed', 'reason': 'price_not_available'}

        # Simulation de slippage
        slippage = np.random.uniform(0, self.config.max_slippage)
        execution_price_buy = buy_price.ask * (1 + slippage)
        execution_price_sell = sell_price.bid * (1 - slippage)

        # Calcul du profit r�el
        volume = opportunity.volume
        gross_profit = (execution_price_sell - execution_price_buy) * volume
        fees = volume * self.config.fee_rate * 2
        net_profit = gross_profit - fees

        trade = {
            'status': 'executed' if net_profit > 0 else 'partial',
            'buy_exchange': opportunity.buy_exchange,
            'sell_exchange': opportunity.sell_exchange,
            'symbol': opportunity.symbol,
            'volume': volume,
            'buy_price': execution_price_buy,
            'sell_price': execution_price_sell,
            'gross_profit': gross_profit,
            'fees': fees,
            'net_profit': net_profit,
            'timestamp': datetime.now(),
            'opportunity': opportunity.to_dict(),
        }

        self.executed_trades.append(trade)

        logger.info(f"Trade ex�cut�: {trade['symbol']} - Profit: ${net_profit:.2f}")

        return trade

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances de la strat�gie.

        Returns:
            Dict[str, Any]: Performances
        """
        if not self.executed_trades:
            return {
                'total_trades': 0,
                'total_profit': 0.0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
            }

        profits = [t['net_profit'] for t in self.executed_trades]
        wins = [p for p in profits if p > 0]

        return {
            'total_trades': len(self.executed_trades),
            'total_profit': sum(profits),
            'win_rate': len(wins) / len(profits) if profits else 0.0,
            'avg_profit': np.mean(profits) if profits else 0.0,
            'max_profit': max(profits) if profits else 0.0,
            'min_profit': min(profits) if profits else 0.0,
            'total_volume': sum(t['volume'] for t in self.executed_trades),
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la strat�gie.

        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'is_running': self.is_running,
            'exchanges': self.config.exchanges,
            'symbols': self.config.symbols,
            'opportunities_count': len(self.opportunities),
            'trades_count': len(self.executed_trades),
            'best_opportunity': self.get_best_opportunity().to_dict() if self.get_best_opportunity() else None,
        }

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde la strat�gie.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegard�e
        """
        try:
            import pickle
            import os

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'executed_trades': self.executed_trades,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Strat�gie sauvegard�e: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'CrossExchangeArbitrage':
        """
        Charge une strat�gie.

        Args:
            filepath: Chemin du fichier

        Returns:
            CrossExchangeArbitrage: Strat�gie charg�e
        """
        try:
            import pickle

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = CrossExchangeArbitrageConfig(**data['config'])
            strategy = cls(config)

            strategy.executed_trades = data.get('executed_trades', [])

            logger.info(f"Strat�gie charg�e: {filepath}")
            return strategy

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_cross_exchange_arbitrage(
    exchanges: List[str] = None,
    symbols: List[str] = None,
    min_spread_percent: float = 0.1,
    **kwargs
) -> CrossExchangeArbitrage:
    """
    Factory pour cr�er une strat�gie d'arbitrage cross-exchange.

    Args:
        exchanges: Liste des exchanges
        symbols: Liste des symboles
        min_spread_percent: Spread minimum en pourcentage
        **kwargs: Arguments suppl�mentaires

    Returns:
        CrossExchangeArbitrage: Strat�gie d'arbitrage
    """
    if exchanges is None:
        exchanges = ['binance', 'coinbase', 'kraken', 'bybit']

    if symbols is None:
        symbols = ['BTC-USD', 'ETH-USD', 'SOL-USD']

    config = CrossExchangeArbitrageConfig(
        exchanges=exchanges,
        symbols=symbols,
        min_spread_percent=min_spread_percent,
        **kwargs
    )
    return CrossExchangeArbitrage(config)


__all__ = [
    'CrossExchangeArbitrage',
    'CrossExchangeArbitrageConfig',
    'ExchangePrice',
    'ArbitrageOpportunity',
    'create_cross_exchange_arbitrage',
]
